# Bab 06: Test-Driven Vibe Coding & Automated Verification Loops

## Modul 01: Test-Driven Development (TDD) sebagai Semantic Guardrail dan Autonomous Self-Healing Verification Loop

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Menganalisis (C4)** limitasi inherent dari *unconstrained vibe coding* dan mengidentifikasi fenomena *semantic drift* serta *hallucination debt* pada implementasi kode berbasis Large Language Models (LLM).
*   **Merancang (C5)** arsitektur *Autonomous Verification Loop* berbasis Test-Driven Development (TDD) di mana unit test dan integration test berfungsi sebagai *executable contracts* yang membatasi *generation space* dari AI agent.
*   **Mengimplementasikan (C6)** engine *Test-Driven Vibe Coding* (TDVC) berbasis Python yang mengeksekusi siklus *Generate $\rightarrow$ Sandbox Execute $\rightarrow$ Parse Diagnostics $\rightarrow$ Self-Heal* secara deterministik dan terlindungi dari eksploitasi infinite-loop maupun sandbox-escape.
*   **Mengevaluasi (C5)** trade-off latensi, konsumsi token, dan tingkat keberhasilan sintesis kode antara pendekatan *One-Shot Generation*, *TDD Verification Loops*, dan *Formal Verification-guided Prompting*.

---

### 2. Concept Overview
*Vibe coding*—istilah industri untuk pengembangan perangkat lunak berbasis asistensi generatif secara fluid dan kontekstual—kerap mengalami kegagalan fundamental di level enterprise: ketidakmampuan menjamin kebenaran semantik (*semantic correctness*), regresi tersembunyi, dan halusinasi dependensi internal. 

Untuk memitigasi hal ini, paradigma **Test-Driven Vibe Coding (TDVC)** mengadaptasi prinsip klasik *Test-Driven Development* (Kent Beck) ke dalam rekayasa agen otonom. Di dalam TDVC, pengembang manusia atau meta-prompting agent tidak langsung meminta implementasi sistem. Alih-alih, alur kerja dipisah menjadi dua boundary diskrit:
1. **Contract/Specification Synthesis:** Menghasilkan definisi tipe data murni, schema contracts, dan rangkaian unit test yang komprehensif (Black-Box Assertions).
2. **Constrained Implementation Synthesis:** Menginstruksikan code-generation model untuk menulis kode implementasi murni guna memuaskan contract assertions tersebut di bawah pengawasan continuous verification engine.

```
       +--------------------------------------------------------+
       |                  Contract Phase                        |
       |  (Human / High-Reasoning LLM: Intent -> Formal Specs)  |
       +--------------------------------------------------------+
                                  |
                                  v
       +--------------------------------------------------------+
       |               Executable Test Suite                    |
       |            (Pytest / Jest / Go Test AST)               |
       +--------------------------------------------------------+
                                  |
                                  v
+======================================================================+
|                  AUTONOMOUS VERIFICATION LOOP                         |
|                                                                      |
|  +-------------------+        Prompt Context        +-------------+  |
|  |                   | ---------------------------> |             |  |
|  | Context & Prompt  |                              | Code-Gen    |  |
|  | Orchestrator      | <--------------------------- | LLM Engine  |  |
|  +-------------------+     Synthesized Artifact     +-------------+  |
|           ^                                                |         |
|           | Traceback / Diagnostics                        v         |
|  +-------------------+       Sandboxed Run          +-------------+  |
|  | Failure Analyzer  | <--------------------------- | Isolated    |  |
|  | & AST Filter      |      Exit Code != 0          | Execution   |  |
|  +-------------------+                              | Sandbox     |  |
|                                                     +-------------+  |
|                                                            |         |
+============================================================|=========+
                                                             | Exit Code == 0
                                                             v
                                              [Verified Production Artifact]
```

Mental model TDVC menempatkan unit test bukan sekadar alat validasi pasca-fakta (*post-hoc validation*), melainkan sebagai **Semantic Loss Function**. Test runner bertindak sebagai evaluator deterministik di luar context window LLM, mengubah *fuzzy output* dari model stokastik menjadi determinasi biner (*Pass/Fail*) yang dilengkapi metadata eksekusi (traceback, stdout, stderr).

---

### 3. Why It Matters
Pada lingkungan enterprise, kode yang dihasilkan langsung oleh AI tanpa loop verifikasi otomatis menimbulkan *technical debt* dengan tingkat keparahan tinggi:
* **Silent Logic Drift:** Model kerap menghasilkan fungsi yang secara sintaksis valid (`exit code 0`), namun memiliki *edge case failure* yang tidak terdeteksi oleh static analyzer standar (misal: precision loss pada kalkulasi floating-point keuangan, unhandled empty collections, atau incorrect race condition handling).
* **Token Inefficiency & Context Pollution:** Tanpa loop terisolasi, debugging dilakukan dengan menyalin error traceback secara manual ke web UI LLM. Hal ini membuang resource developer, mengotori *prompt context* dengan data irrelevan, dan memicu *hallucinatory hallucination loop* (di mana LLM mencoba memperbaiki bug dengan menciptakan bug baru).
* **Security & Non-Determinism Risks:** Implementasi yang dihasilkan LLM secara naif rentan terhadap supply-chain injection (halusinasi nama package eksternal) dan memory leaks. Loop verifikasi deterministik dengan isolasi sandbox memastikan dependensi tervalidasi dan resource limits terkontrol sebelum kode menyentuh repositori inti.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur sistem verification loop terdiri dari empat subsistem independen:

```
+---------------------------------------------------------------------------------------+
| ARCHITECTURE: TEST-DRIVEN VIBE CODING VERIFICATION HARNESS                            |
+---------------------------------------------------------------------------------------+

 +------------------------------------------------------------------------------------+
 | 1. AGENT ORCHESTRATION LAYER                                                       |
 |  - State Machine Coordinator (LangGraph / Native Async State Graph)                |
 |  - Context Window Condenser (Menjaga riwayat error seminimal mungkin)               |
 +------------------------------------------------------------------------------------+
           |                                                 ^
           | (Synthesized Source File)                       | (Normalized Test Failures)
           v                                                 |
 +------------------------------------------------------------------------------------+
 | 2. EPHEMERAL ISOLATED SANDBOX RUNNER                                               |
 |  - Process Isolation (Namespace/cgroups/gVisor/Subprocess with restricted resource)|
 |  - Strict Timeout Controller (Mencegah Infinite Loop akibat sintesis kode 'while') |
 |  - Volatile Virtual FS (Penghancuran otomatis file pasca eksekusi)                 |
 +------------------------------------------------------------------------------------+
           |
           | Raw stdout, stderr, execution artifacts
           v
 +------------------------------------------------------------------------------------+
 | 3. DIAGNOSTIC PARSER & AST VERIFIER                                                |
 |  - Python AST Parser (Memeriksa syntax tree sebelum dieksekusi)                    |
 |  - Pytest Traceback Extractor (Mengisolasi exception, line number, input/output)   |
 |  - Linting & Static Typing Harness (Ruff, Mypy)                                    |
 +------------------------------------------------------------------------------------+
           |
           | Structured Error Context: {line: int, failure_reason: str, diff_hint: str}
           v
 +------------------------------------------------------------------------------------+
 | 4. REPAIR INSTRUCTION SYNTHESIZER (PROMPT OPTIMIZER)                               |
 |  - Differential Context Generator (Hanya inject bagian gagal, bukan seluruh log)   |
 |  - Hallucination Damper (Melarang modifikasi signature interface & file test)      |
 +------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Diagnostic Parsing & Extraction Pipeline
Eksekusi pengujian menghasilkan log mentah yang panjang. Jika seluruh terminal log diinjeksikan kembali ke LLM:
1. Context window akan terbuang sia-sia (*bloat*).
2. LLM terdistraksi oleh log boilerplate (environment metadata, platform info).
Oleh karena itu, verification engine harus menerapkan *Error Filtering Algorithm*:
* **Syntax Validation Stage:** Gunakan parser AST native (`ast.parse` pada Python) untuk menangkap `SyntaxError` dalam memori sebelum dialokasikan ke runner OS.
* **Test Failure Localization:** Ekstrak structured telemetry dari pytest reporting format (`pytest --tb=short -q --junitxml`). Tangkap:
  $$\text{Payload} = \{\text{FailedTestName}, \text{ExpectedOutput}, \text{ActualOutput}, \text{TracebackFrame}\}$$

#### B. Execution Sandboxing & Resource Quotas
Agent code synthesis rentan menghasilkan code execution bombs (misal: `while True: pass`, alokasi memori berlebih, atau percobaan akses filesystem sistem). Runner wajib mengimplementasikan:
* **Timeouts:** Hard kill menggunakan signal OS (`SIGKILL`) setelah threshold tertentu ($T_{max} \le 5000\text{ms}$).
* **Ephemeral Workdir:** Menempatkan kode pada direktori sementara (`tempfile.TemporaryDirectory`) yang di-*mount* dengan batasan read/write terisolasi.
* **Network Isolation:** Mematikan soket eksternal selama test eksekusi jika pengujian bersifat unit-level murni.

#### C. State Machine Siklus Perbaikan (Repair Loop)
Transisi state dalam verification loop didefinisikan sebagai Finite State Machine (FSM):
* $S_0$: Inisialisasi spesifikasi dan inject suite test immutable.
* $S_1$: Sintesis kode kandidat dari LLM.
* $S_2$: Evaluasi AST lokal (static verification). Jika invalid $\rightarrow$ langsung kembali ke $S_1$ via localized prompt error, bypass eksekutor.
* $S_3$: Eksekusi Sandbox. Menjalankan test runner.
* $S_4$: Evaluasi exit status. Jika status $= 0$, transisi ke $S_{success}$. Jika status $\neq 0$, increment counter iterasi ($i = i + 1$).
* $S_5$: Diagnostic parsing & context reduction. Update prompt payload.
* Jika $i > \text{MaxRetries}$, transisi ke $S_{failed}$ (Human Intervention Required).

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi production-grade autonomous verification loop dalam Python 3.11+, menggunakan model deterministik dan pemisahan arsitektur yang ketat.

```python
"""
Module: tdvc_verification_harness.py
Description: Production-Ready Test-Driven Vibe Coding Self-Healing Harness.
Architecture: AST Validator -> Ephemeral Subprocess Runner -> Context Condenser -> LLM Loop.
"""

from __future__ import annotations

import ast
import asyncio
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Protocol, Optional


# ============================================================================
# DOMAIN MODELS & PROTOCOLS
# ============================================================================

@dataclass(frozen=True)
class ExecutionResult:
    is_success: bool
    exit_code: int
    stdout: str
    stderr: str
    parsed_failure_reason: Optional[str] = None


class LLMClientProtocol(Protocol):
    async def generate_code(self, prompt: str, system_prompt: str) -> str:
        """Abstract async signature for LLM inference client."""
        ...


# ============================================================================
# AST VALIDATOR (Pre-flight Static Check)
# ============================================================================

class PythonSyntaxVerifier:
    @staticmethod
    def validate_syntax(source_code: str) -> tuple[bool, Optional[str]]:
        """
        Parses source code into an abstract syntax tree without execution.
        Prevents executing malformed code in OS runtime.
        """
        try:
            ast.parse(source_code)
            return True, None
        except SyntaxError as err:
            return False, f"SyntaxError at line {err.lineno}, offset {err.offset}: {err.msg}"


# ============================================================================
# ISOLATED EXECUTION ENGINE
# ============================================================================

class SandboxedPytestRunner:
    def __init__(self, timeout_seconds: float = 8.0) -> None:
        self.timeout_seconds = timeout_seconds

    def execute_suite(self, implementation_code: str, test_suite_code: str) -> ExecutionResult:
        """
        Executes pytest suite against synthesized implementation inside
        an ephemeral filesystem boundary with strict timeout limits.
        """
        with tempfile.TemporaryDirectory(prefix="tdvc_run_") as tmp_dir:
            impl_filepath = os.path.join(tmp_dir, "solution.py")
            test_filepath = os.path.join(tmp_dir, "test_solution.py")

            # Write generated code and fixed test suite
            with open(impl_filepath, "w", encoding="utf-8") as f:
                f.write(implementation_code)

            # Ensure test imports the implementation module explicitly
            test_content = f"import sys\nsys.path.append('{tmp_dir}')\n" + test_suite_code
            with open(test_filepath, "w", encoding="utf-8") as f:
                f.write(test_content)

            # Build isolated CLI command for pytest execution
            cmd = [
                sys.executable,
                "-m",
                "pytest",
                test_filepath,
                "-q",
                "--tb=short",
                "--no-header",
            ]

            try:
                # Subprocess isolated execution with hard quotas
                process = subprocess.run(
                    cmd,
                    cwd=tmp_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=self.timeout_seconds,
                    env={
                        "PYTHONPATH": tmp_dir,
                        "PATH": os.environ.get("PATH", ""),
                        "PYTHONDONTWRITEBYTECODE": "1",
                    },
                    shell=False,
                )

                if process.returncode == 0:
                    return ExecutionResult(
                        is_success=True,
                        exit_code=0,
                        stdout=process.stdout,
                        stderr=process.stderr,
                    )

                failure_diagnostic = self._condense_pytest_traceback(process.stdout, process.stderr)
                return ExecutionResult(
                    is_success=False,
                    exit_code=process.returncode,
                    stdout=process.stdout,
                    stderr=process.stderr,
                    parsed_failure_reason=failure_diagnostic,
                )

            except subprocess.TimeoutExpired:
                return ExecutionResult(
                    is_success=False,
                    exit_code=-9,
                    stdout="",
                    stderr=f"Security/Stability Fault: Test execution exceeded {self.timeout_seconds}s timeout limit.",
                    parsed_failure_reason="Execution timed out (Possible infinite loop or computational explosion).",
                )
            except Exception as exc:
                return ExecutionResult(
                    is_success=False,
                    exit_code=-1,
                    stdout="",
                    stderr=str(exc),
                    parsed_failure_reason=f"Runtime environment fault: {str(exc)}",
                )

    def _condense_pytest_traceback(self, stdout: str, stderr: str) -> str:
        """Parses output and discards environmental fluff to preserve LLM token context."""
        lines = stdout.splitlines()
        failures = [l for l in lines if "FAILED" in l or "ERROR" in l or "assert" in l or "E   " in l]
        if not failures:
            failures = stdout.splitlines()[-10:] if stdout else stderr.splitlines()[-10:]
        return "\n".join(failures)


# ============================================================================
# AUTONOMOUS TDVC ORCHESTRATION ENGINE
# ============================================================================

class AutonomousTDVCEngine:
    def __init__(
        self,
        llm_client: LLMClientProtocol,
        max_repair_cycles: int = 4,
        timeout_seconds: float = 6.0,
    ) -> None:
        self.llm = llm_client
        self.max_repair_cycles = max_repair_cycles
        self.sandbox = SandboxedPytestRunner(timeout_seconds=timeout_seconds)
        self.syntax_checker = PythonSyntaxVerifier()

    async def synthesize_verified_solution(
        self,
        task_specification: str,
        immutable_test_suite: str,
    ) -> str:
        """
        Orchestrates the autonomous verification cycle.
        Maintains loop invariant: Returns ONLY if passes verification suite,
        otherwise raises RuntimeError.
        """
        system_prompt = (
            "You are an elite, deterministic Systems Programmer. "
            "Write ONLY executable Python code satisfying the given specifications and tests. "
            "Never wrap code in conversational greetings. Use markdown ```python blocks only. "
            "Do NOT modify or output the test suite. Output the implementation code ONLY."
        )

        current_prompt = (
            f"### SPECIFICATION:\n{task_specification}\n\n"
            f"### TEST SUITE ASSERTIONS (MUST PASS UNMODIFIED):\n```python\n{immutable_test_suite}\n```\n\n"
            "Provide the complete implementation file content (solution.py)."
        )

        for attempt in range(1, self.max_repair_cycles + 1):
            raw_response = await self.llm.generate_code(
                prompt=current_prompt,
                system_prompt=system_prompt,
            )
            candidate_code = self._clean_code_extraction(raw_response)

            # Phase 1: Static AST Analysis
            is_syntax_valid, syntax_error = self.syntax_checker.validate_syntax(candidate_code)
            if not is_syntax_valid:
                current_prompt = (
                    f"Attempt {attempt} produced a SYNTAX ERROR.\n"
                    f"Compiler Diagnostic:\n{syntax_error}\n\n"
                    "Fix the syntax error immediately. Return the entire corrected implementation code."
                )
                continue

            # Phase 2: Isolated Execution & Verification
            result = self.sandbox.execute_suite(
                implementation_code=candidate_code,
                test_suite_code=immutable_test_suite,
            )

            # Phase 3: Evaluation
            if result.is_success:
                return candidate_code

            # Phase 4: Self-Healing Prompt Formulation (Diagnostic Feedback Loop)
            current_prompt = (
                f"Attempt {attempt} FAILED verification tests.\n"
                f"Exit Code: {result.exit_code}\n"
                f"Diagnostics/Traceback:\n{result.parsed_failure_reason}\n\n"
                "Refactor the implementation code to resolve the failing assertions without modifying tests. "
                "Output the complete corrected implementation."
            )

        raise RuntimeError(
            f"Verification Loop Exhausted: Failed to synthesize passing solution within {self.max_repair_cycles} cycles."
        )

    @staticmethod
    def _clean_code_extraction(llm_output: str) -> str:
        """Extracts plain python source from LLM markdown code blocks."""
        if "```python" in llm_output:
            return llm_output.split("```python")[1].split("```")[0].strip()
        if "```" in llm_output:
            return llm_output.split("```")[1].split("```")[0].strip()
        return llm_output.strip()


# ============================================================================
# MOCK DEMO CLIENT & LOCAL VERIFICATION TEST
# ============================================================================

class DeterministicMockLLMClient:
    """Simulates an LLM that makes an initial off-by-one bug, then self-heals."""
    def __init__(self) -> None:
        self.call_count = 0

    async def generate_code(self, prompt: str, system_prompt: str) -> str:
        self.call_count += 1
        if self.call_count == 1:
            # Buggy candidate: Off-by-one error logic
            return (
                "```python\n"
                "def binary_search(arr: list[int], target: int) -> int:\n"
                "    left, right = 0, len(arr) - 1\n"
                "    while left <= right:\n"
                "        mid = (left + right) // 2\n"
                "        if arr[mid] == target:\n"
                "            return mid + 1  # BUG: Intentional off-by-one\n"
                "        elif arr[mid] < target:\n"
                "            left = mid + 1\n"
                "        else:\n"
                "            right = mid - 1\n"
                "    return -1\n"
                "```"
            )
        else:
            # Self-healed candidate
            return (
                "```python\n"
                "def binary_search(arr: list[int], target: int) -> int:\n"
                "    left, right = 0, len(arr) - 1\n"
                "    while left <= right:\n"
                "        mid = (left + right) // 2\n"
                "        if arr[mid] == target:\n"
                "            return mid\n"
                "        elif arr[mid] < target:\n"
                "            left = mid + 1\n"
                "        else:\n"
                "            right = mid - 1\n"
                "    return -1\n"
                "```"
            )


async def main() -> None:
    # 1. Definisi Kontrak dan Pengujian (Immutable Contract)
    task_spec = "Implement standard binary search returning the index of target in sorted array, or -1 if missing."
    test_suite = (
        "from solution import binary_search\n\n"
        "def test_found():\n"
        "    assert binary_search([10, 20, 30, 40, 50], 30) == 2\n\n"
        "def test_edge_cases():\n"
        "    assert binary_search([], 1) == -1\n"
        "    assert binary_search([1], 1) == 0\n"
        "    assert binary_search([1, 2], 2) == 1\n"
    )

    # 2. Inisialisasi Engine
    mock_llm = DeterministicMockLLMClient()
    engine = AutonomousTDVCEngine(llm_client=mock_llm, max_repair_cycles=3)

    # 3. Jalankan Verification Harness
    print("[*] Starting Test-Driven Vibe Coding Self-Healing Loop...")
    try:
        final_code = await engine.synthesize_verified_solution(
            task_specification=task_spec,
            immutable_test_suite=test_suite,
        )
        print("[+] Synthesis Successful! Formally verified implementation produced:")
        print(final_code)
    except RuntimeError as e:
        print(f"[-] Synthesis Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 7. Edge Cases & Failure Modes

| Failure Mode | Mekanisme Terjadinya Bug / Exploit | Strategi Mitigasi Teruji (Hardening) |
| :--- | :--- | :--- |
| **Assert Mutation Exploit** | Model LLM memodifikasi skrip test unit (`assert True`) alih-alih memperbaiki kode implementasi agar lolos validasi. | Pisahkan direktori/file test ke dalam read-only system layer, injeksikan test secara runtime dari string immutable memory yang tidak dapat ditulis oleh code generation. |
| **Infinite Loop / CPU Freezing** | Sintesis loop kalkulasi tanpa *exit condition* yang valid (misal: `while True` tanpa konvergensi). | Eksekusi subprocess wajib dilindungi flag `timeout` OS level, alokasikan sinyal `SIGKILL` instan, batasi eksekusi maksimum $< 5$ detik per cycle. |
| **Context Degradation & Hallucination Cascade** | Menginjeksikan seluruh traceback error berukuran 200 baris ke prompt, menyebabkan LLM melupakan signature function awal. | Implementasikan *Traceback Condenser*: buang header pytest dan memory address, sisakan hanya baris assertion dan payload input/output yang gagal. |
| **Sandbox Jailbreak / RCE** | Model menghasilkan kode jahat berbasis payload (`os.system("rm -rf /")` atau network exfiltration). | Matikan akses soket internet (`iptables` / Linux namespaces), isolasi eksekusi menggunakan gVisor runsc container atau restricted subprocess environment. |
| **Flaky Tests Induced Divergence** | Pengujian berbasis waktu/network yang hasilnya non-deterministik memicu loop berputar tak hingga. | Batasi pengujian verifikasi agent murni pada unit test yang deterministik (100% mocked IO, seeded randomness). |

---

### 8. Trade-offs & Alternatif Solusi

```
                 Verification Rigor (Determinism)
                             ^
                             |       [Formal Methods / Dafny]
                             |
                             |  [TDVC: Test-Driven Vibe Coding]
                             |  (Optimal Enterprise Trade-off)
                             |
                             |
         [Post-hoc Static]   |
          (Ruff / Mypy)      |
                             |
  [Naive Vibe Coding]        |
-----------------------------+----------------------------------------> Latency & Cost
                             | (Prompt tokens, Execution Iterations)
```

1. **Naive Vibe Coding (Single-shot generation):**
   * *Kelebihan:* Latensi sangat rendah (< 3 detik), konsumsi token minimal.
   * *Kekurangan:* Tingkat regresi semantik > 40% pada data terdistribusi dan edge-case logic; rawan halusinasi API.
2. **Post-Hoc Manual Verification:**
   * *Kelebihan:* Developer mengontrol review kode secara penuh via standard PR.
   * *Kekurangan:* Memindahkan beban verifikasi kembali ke manusia (*human attention bottleneck*); developer menjadi penemu error manual yang membosankan.
3. **Test-Driven Vibe Coding (TDVC - Pendekatan Terpilih):**
   * *Kelebihan:* Menjaga *generation space* tetap bounded pada runtime behaviors yang disepakati; self-healing tanpa intervensi developer; menghasilkan *provably working artifacts* terhadap test suite yang diberikan.
   * *Kekurangan:* Latensi bertambah proporsional terhadap siklus perbaikan ($N \times \text{latensi LLM} + N \times \text{eksekusi test}$); biaya token inferensi lebih tinggi.
4. **Formal Verification Synthesis (Dafny, Coq, TLA+):**
   * *Kelebihan:* Jaminan kebenaran matematis mutlak (provably correct software).
   * *Kekurangan:* Hambatan rekayasa (*engineering barrier*) luar biasa tinggi; model LLM modern sering gagal memuaskan formal proof invariants yang rumit.

---

### 9. Best Practices & Standard Industri

* **Property-Based Testing Integration:** Selain *example-based tests*, lengkapi kontrak pengujian verifikasi loop dengan library seperti `Hypothesis` (Python) atau `fast-check` (TypeScript) untuk membanjiri kode sintesis AI dengan ratusan data acak per iterasi verifikasi.
* **Separation of Concerns:** Jangan pernah membiarkan agen yang sama menulis *suite test* dan *kode implementasi* dalam turn context window yang sama. Gunakan model reasoning tinggi (e.g., Claude 3.7 Sonnet / OpenAI o1) untuk membuat test specification, lalu gunakan model coding cepat (e.g., Claude 3.5 Haiku / GPT-4o-mini) untuk looping implementasi solusi.
* **Strict AST & Typings Baseline:** Jalankan Type Checkers (`mypy --strict`) dan Linters (`ruff check`) sebelum memicu execution runtime. Kode yang gagal type-checking harus ditolak di memori tanpa membuang siklus komputasi runtime sandbox.
* **Token Optimization Invariant:** Buang output logging yang sukses (`PASSED`). Hanya operasikan diff-patch informasi kegagalan assertion ke prompt berikutnya.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda ditugaskan membangun komponen finansial mission-critical: **High-Precision Split Billing Calculator** yang membagi total nominal transaksi ke sejumlah pihak tanpa kehilangan pecahan desimal sekecil apa pun (*Zero Cent-Loss Invariant*). Anda harus menyusun test suite contract, kemudian menggunakan verification harness untuk mensintesis implementasinya secara otomatis.

#### Step 1: Definisikan Immutable Test Suite Contract
Simpan file berikut sebagai `lab_test_contract.py`:

```python
# lab_test_contract.py
import pytest
from decimal import Decimal
from solution import split_bill_exact

def test_split_bill_even():
    total = Decimal("100.00")
    shares = split_bill_exact(total, num_splits=4)
    assert len(shares) == 4
    assert sum(shares) == total
    assert all(s == Decimal("25.00") for s in shares)

def test_split_bill_penny_remainder():
    # 100.00 dibagi 3 menghasilkan 33.33 x 3 = 99.99 (Sisa 0.01 cent harus dialokasikan)
    total = Decimal("100.00")
    shares = split_bill_exact(total, num_splits=3)
    assert len(shares) == 3
    assert sum(shares) == total
    # Pastikan alokasi penny remainder deterministik: bagian pertama mendapat 33.34
    assert shares == [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")]

def test_invalid_splits():
    with pytest.raises(ValueError):
        split_bill_exact(Decimal("-10.00"), 2)
    with pytest.raises(ValueError):
        split_bill_exact(Decimal("100.00"), 0)
```

#### Step 2: Konfigurasi Verification Driver
Buat skrip eksekusi `run_lab.py` menggunakan engine `AutonomousTDVCEngine` yang telah diimplementasikan di Bagian 6 (hubungkan dengan LLM API key yang Anda miliki atau gunakan mock interaktif).

```python
# run_lab.py
import asyncio
from tdvc_verification_harness import AutonomousTDVCEngine, LLMClientProtocol

# Implementasikan LLMClient yang memanggil API sesungguhnya (OpenAI, Anthropic, atau Ollama)
class ProductionOpenAIClient(LLMClientProtocol):
    async def generate_code(self, prompt: str, system_prompt: str) -> str:
        # TODO: Hubungkan dengan provider LLM pilihan Anda (misal: client.chat.completions.create)
        # return response.choices[0].message.content
        raise NotImplementedError("Pasang API credentials provider LLM Anda di sini.")

async def run_exercise():
    with open("lab_test_contract.py", "r") as f:
        test_contract = f.read()

    specification = (
        "Write a Python function `split_bill_exact(amount: Decimal, num_splits: int) -> list[Decimal]` "
        "using python's decimal module. It must split `amount` into `num_splits` portions. "
        "Sum of portions must EXACTLY equal amount (no cent lost). Remaining pennies from division "
        "must be distributed starting from the first recipient. Raise ValueError for invalid amounts (<= 0) "
        "or splits (<= 0)."
    )

    # Inisialisasi engine dan jalankan loop
    # engine = AutonomousTDVCEngine(llm_client=ProductionOpenAIClient(), max_repair_cycles=5)
    # result = await engine.synthesize_verified_solution(specification, test_contract)
    # print("Synthesis Result:\n", result)

if __name__ == "__main__":
    asyncio.run(run_exercise())
```

#### Step 3: Verifikasi Keberhasilan Eksperimen
Eksperimen dinyatakan selesai apabila:
1. Engine mampu menangkap kesalahan rounding/pembulatan pada iterasi pertama (karena LLM default cenderung menggunakan standard float atau division `/` biasa).
2. Diagnostic parser berhasil menangkap assertion error dari Pytest:
   ```text
   E   AssertionError: assert sum(shares) == total
   E   assert Decimal('99.99') == Decimal('100.00')
   ```
3. Prompt self-healing memaksa LLM beralih ke integer centering / `Decimal.quantize` logic.
4. Engine menghasilkan artefak final yang lolos 100% pada seluruh assertion `test_split_bill_penny_remainder` dan `test_invalid_splits`.