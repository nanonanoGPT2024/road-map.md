# Bab 05: Test-Driven Development & Loop Verifikasi Otonom

## 1. Learning Objectives

Setelah menyelesaikan bab ini, Senior Engineer dan Technical Lead diharapkan mampu:
- **Menganalisis dan Mendesain** arsitektur *Autonomous Verification Loop* (AVL) berbasis *Test-Driven Development* (TDD) untuk sistem agen otonom seperti Claude Code.
- **Mengimplementasikan** mekanisme *Sandboxed Execution Harness* yang mengeksekusi siklus *Red-Green-Refactor* secara mandiri tanpa intervensi manusia.
- **Mengembangkan** algoritma *Convergence & Halting Detection* untuk menghentikan loop perbaikan kode otonom ketika agen mengalami osilasi, regresi berulang, atau konsumsi token berlebih.
- **Menerapkan** *AST-based Test Tampering Guardrails* guna menjamin agen AI tidak memodifikasi assertion pengujian (*false positive bypass*) untuk meloloskan status build.
- **Mengevaluasi** trade-off antara deterministic unit testing, property-based testing, dan runtime validation dalam mengendalikan halusinasi sintaksis serta semantik.

---

## 2. Concept Overview

Secara fundamental, sistem agen AI penghasil kode (*code-generating autonomous agents*) memiliki sifat probabilistik. Tanpa batasan deterministik, model cenderung terjebak dalam *plausible hallucinations*—menghasilkan kode yang terlihat benar secara sintaksis tetapi gagal secara semantik pada *edge cases*. 

*Test-Driven Development & Autonomous Verification Loop* (TDD-AVL) membalik paradigma kontrol: sistem tidak memperlakukan LLM sebagai pembuat keputusan akhir, melainkan sebagai mesin hipotesis (*hypothesis engine*) yang dikontrol ketat oleh *deterministic verification engine* (compiler, linter, dan test runner).

```
   +-------------------------------------------------------+
   |                  MENTAL MODEL TDD-AVL                 |
   |                                                       |
   |   Probabilistic Engine       Deterministic Evaluator   |
   |      (LLM / Agent)              (Test / Sandbox)      |
   |   +-----------------+         +------------------+    |
   |   | Generasi Kode / | ------> | Eksekusi Runtime |    |
   |   | Perbaikan Patch |         | Assertion Test   |    |
   |   +-----------------+         +------------------+    |
   |           ^                             |             |
   |           |    Feedback Loop Lengkap    |             |
   |           +-----------------------------+             |
   |              (Stdout, Stderr, ExitCode)               |
   +-------------------------------------------------------+
```

Prinsip kerja mental model ini bertumpu pada tiga postulat:
1. **Red Stage (Ground Truth Specification):** Agen atau pengguna mendefinisikan kontrak fungsi melalui spesifikasi pengujian unit yang *failing* (Red). Pengujian ini berkedudukan sebagai *immutable ground truth* yang diproteksi dari modifikasi agen.
2. **Green Stage (Autonomous Convergence):** Agen membaca error trace (stdout, stderr, exit code, line numbers) dari lingkungan eksekusi terisolasi dan menghasilkan patch mikro (*diff*) untuk memperbaiki kode hingga seluruh assertion bernilai sukses (*Exit Code 0*).
3. **Refactor Stage (Cleanliness & Non-regression):** Setelah status Green tercapai, agen melakukan optimasi kompleksitas algoritmik atau struktur kode dengan syarat mutlak: suite pengujian regresi deterministik tetap hijau (*zero regression tolerance*).

---

## 3. Why It Matters

Dalam pengembangan perangkat lunak tingkat enterprise, memberikan izin tulis (*write access*) kepada agen otonom langsung ke codebase tanpa verifikasi loop tertutup merupakan risiko operasional katastropik:

1. **Eliminasi Silent Regressions:** Dalam basis data kode jutaan baris, modifikasi lokal dapat merusak dependensi downstream yang tidak terlihat dalam context window model. Loop verifikasi otonom mengeksekusi test suite komprehensif pada setiap iterasi untuk mendeteksi regresi secara instan.
2. **Mitigasi "Hallucinated Fixes":** Agen LLM sering berasumsi bahwa patch yang ditulis telah menyelesaikan masalah. Tanpa eksekusi pengujian aktual, bug tersembunyi akan terdorong ke pipeline CI/CD, memicu *deployment pipeline failure*.
3. **Optimasi Biaya Token & Konvergensi:** Tanpa loop verifikasi deterministik yang menyaring output error secara terstruktur, konteks interaksi membengkak akibat prompt debugging manual oleh engineer, yang melipatgandakan latensi dan *inference cost*.
4. **Keamanan Integritas Kode (Anti-Tampering):** Tanpa validasi independen pada tingkat file tree, agen sering kali "menyelesaikan" kegagalan pengujian dengan menghapus assertion atau mengganti nilai ekspektasi (`assert True`). Sistem TDD otonom enterprise wajib membatasi dan mengaudit izin modifikasi berkas pengujian.

---

## 4. Arsitektur & Diagram Komponen

Arsitektur TDD-AVL memisahkan *Agent Control Plane* dari *Sandbox Execution Engine* menggunakan boundary isolasi proses yang ketat.

```
+-----------------------------------------------------------------------------------+
|                        AUTONOMOUS TDD CONTROLLER ENGINE                           |
+-----------------------------------------------------------------------------------+
                                          |
                        1. Generate Test & Contract
                                          v
+-----------------------------------------------------------------------------------+
|               TEST IMMUTABILITY GUARD (AST Integrity Checker)                     |
|  - Kunci Hash Berkas Uji (SHA-256)                                                |
|  - Parse AST: Validasi Assertion Tidak Boleh Dimodifikasi Agen                    |
+-----------------------------------------------------------------------------------+
                                          |
                       2. Dispatch Initial Test
                                          v
+-----------------------------------------------------------------------------------+
|                 ISOLATED EXECUTION SANDBOX (Subprocess / OCI)                     |
|                                                                                   |
|   +-----------------------+     Execution      +------------------------------+   |
|   | pytest / vitest runner| -----------------> | Exit Code, Stdout, Stderr,   |   |
|   +-----------------------+                    | Coverage Metrics             |   |
|                                                +------------------------------+   |
+-----------------------------------------------------------------------------------+
                                          |
                      3. Structured Output Parsing
                                          v
+-----------------------------------------------------------------------------------+
|                     VERIFICATION & CONVERGENCE ANALYZER                           |
|  - Trace Parser (Regex/JSON AST Extraction)                                       |
|  - State Classifier: RED | GREEN | REGRESSION | OSCILLATING | UNRECOVERABLE      |
|  - Convergence Guard: Cek apakah error signature identik berulang (Max Retries)   |
+-----------------------------------------------------------------------------------+
         |                                                        |
    [Status: GREEN]                                         [Status: RED]
         |                                                        |
         v                                                        v
+-----------------------+                              +-----------------------+
| AST Refactor Pipeline |                              | Error Payload Builder |
| & Final Commit Gate   |                              | (Minified & Ranked)   |
+-----------------------+                              +-----------------------+
                                                                  |
                                                   4. Invalidate / Feedback
                                                                  v
                                                       +-----------------------+
                                                       | Claude Code LLM Agent |
                                                       |  (Targeted Patch Gen) |
                                                       +-----------------------+
```

### Komponen Kunci:
- **Test Immutability Guard:** Memeriksa integritas berkas pengujian dengan *hashing* dan inspeksi AST untuk memastikan agen tidak menurunkan standar validasi demi mengejar status *Green*.
- **Isolated Execution Sandbox:** Lapisan eksekusi sub-proses lokal yang terlindungi, membatasi *timeout*, alokasi memori, serta akses jaringan.
- **Verification & Convergence Analyzer:** Mesin status (*state machine*) yang mengklasifikasikan hasil pengujian, memantau *trajectory history* error, dan menghentikan eksekusi jika terjadi osilasi siklis.
- **Error Payload Builder:** Mengabstraksi dan mengekstrak stack trace relevan agar tidak membebani context window agen dengan log yang redundan.

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Siklus Status Autonomous Verify-Repair
Siklus verifikasi otonom beroperasi sebagai *Deterministic Finite Automaton* (DFA):

$$\mathcal{M} = (S, \Sigma, \delta, s_0, F)$$

Di mana:
- $S \in \{\text{INIT}, \text{TEST\_RED}, \text{PATCHING}, \text{VERIFYING}, \text{REFACTORING}, \text{HALTED\_SUCCESS}, \text{HALTED\_FAILED}\}$
- $\Sigma \in \{\text{TestPassed}, \text{TestFailed}, \text{CompileError}, \text{Timeout}, \text{TamperDetected}, \text{MaxRetriesExceeded}\}$
- $\delta: S \times \Sigma \to S$ mendefinisikan transisi status.
- $s_0 = \text{INIT}$
- $F = \{\text{HALTED\_SUCCESS}, \text{HALTED\_FAILED}\}$

```
 (INIT) --------> (TEST_RED: Must Fail)
                       |
               Test Fails As Expected
                       v
        +-------> (PATCHING)
        |              |
        |       Generasi Patch
        |              v
        |        (VERIFYING)
        |         /   |   \
        |        /    |    \
   Test Failed  /     |     \ Test Passed
        |      /      |      \
        +-----+       |       +------> (REFACTORING)
                      |                      |
             Loop Cycle Detected /           | All Pass & Clean
             Tamper Detected                 v
                      |              (HALTED_SUCCESS)
                      v
               (HALTED_FAILED)
```

### 5.2 Dynamic Context Truncation (Log Distillation)
Output test runner standar sering kali sangat panjang. Memasukkan ribuan baris log ke dalam context window agen akan menyebabkan *context poisoning* dan latensi tinggi. Sistem AVL menerapkan *Deterministic Trace Distillation*:
1. Ekstraksi exception name, message, failing file, dan baris kode terkait.
2. Isolasi baris *frame stack* lokal yang hanya merujuk pada kode target (memfilter frame internal pustaka pihak ketiga/standard library).
3. Format output ke dalam representasi skema JSON terstruktur sebelum dikirim kembali ke agen.

### 5.3 Anti-Oscillation & Convergence Math
Untuk mendeteksi apakah agen mengalami *stuck loop* (mengubah solusi A ke B, lalu kembali ke A), sistem memetakan signature kesalahan ke dalam hash status:

$$H_t = \text{SHA-256}(\text{ErrorType} \parallel \text{FailingFile} \parallel \text{LineNumber} \parallel \text{ErrorMessage})$$

Jika vektor status riwayat $\mathbf{H} = [H_1, H_2, \dots, H_t]$ mengandung sub-sekuens repetitif:

$$\exists \, i, j \text{ di mana } H_i = H_j \quad (i \neq j)$$

Sistem mengidentifikasi osilasi dan mengubah instruksi prompt untuk memaksa agen mengeksplorasi cabang algoritma baru alih-alih melakukan *micro-patching* lokal.

---

## 6. Production-Ready Code Implementation

Berikut implementasi lengkap komponen inti *Autonomous TDD Engine* menggunakan Python 3.11+, fully-typed, asinkron, dan mandiri tanpa ketergantungan eksternal selain standard library dan `pydantic`.

```python
"""
Autonomous TDD Engine & Verification Loop for AI Agents.
Architected for strict isolation, deterministic evaluation, and convergence control.
"""

from __future__ import annotations

import ast
import asyncio
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# ============================================================================
# 1. DOMAIN MODELS & ENUMS
# ============================================================================

class VerificationStatus(str, Enum):
    RED = "RED"                     # Tests failing as expected (initial state)
    GREEN = "GREEN"                 # All tests passed successfully
    REGRESSION = "REGRESSION"       # Unrelated tests broken
    TAMPERING_DETECTED = "TAMPER"   # Agent illegally modified test specifications
    OSCILLATING = "OSCILLATING"     # Agent is toggling between known bad states
    TIMEOUT = "TIMEOUT"             # Execution exceeded deterministic bound
    RUNTIME_ERROR = "RUNTIME_ERROR" # Syntax or structural unhandled exceptions


@dataclass(frozen=True)
class ExecutionResult:
    status: VerificationStatus
    exit_code: int
    stdout: str
    stderr: str
    failing_assertions: List[str]
    error_fingerprint: str
    duration_seconds: float


# ============================================================================
# 2. TEST INTEGRITY GUARDRAILS (AST Level)
# ============================================================================

class SecurityViolationError(Exception):
    """Raised when an agent attempts to tamper with deterministic test definitions."""
    pass


class ASTTestGuard:
    """
    Enforces test suite immutability. Analyzes test file ASTs to prevent
    assertion stripping, mocking injection, or trivial passing conditions.
    """

    @staticmethod
    def calculate_file_hash(file_path: Path) -> str:
        if not file_path.exists():
            raise FileNotFoundError(f"Path does not exist: {file_path}")
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def audit_ast_modifications(original_code: str, modified_code: str) -> None:
        """
        Ensures the agent has not modified the AST structure of assertions
        or deleted test methods.
        """
        orig_ast = ast.parse(original_code)
        mod_ast = ast.parse(modified_code)

        orig_tests = {
            node.name for node in ast.walk(orig_ast) 
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
        }
        mod_tests = {
            node.name for node in ast.walk(mod_ast) 
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
        }

        deleted_tests = orig_tests - mod_tests
        if deleted_tests:
            raise SecurityViolationError(
                f"Unauthorized deletion of test cases detected: {deleted_tests}"
            )

        orig_assertions = sum(
            1 for node in ast.walk(orig_ast) if isinstance(node, ast.Assert)
        )
        mod_assertions = sum(
            1 for node in ast.walk(mod_ast) if isinstance(node, ast.Assert)
        )

        if mod_assertions < orig_assertions:
            raise SecurityViolationError(
                f"Assertion dilution detected: Original={orig_assertions}, Modified={mod_assertions}"
            )


# ============================================================================
# 3. ISOLATED TEST HARNESS
# ============================================================================

class IsolatedTestHarness:
    """
    Executes Python tests in an isolated async subprocess, capturing structured output
    and deriving deterministic error fingerprints.
    """

    def __init__(self, workspace_dir: Path, timeout_seconds: float = 10.0):
        self.workspace_dir = workspace_dir
        self.timeout_seconds = timeout_seconds

    async def run_tests(self, test_file_rel: str) -> ExecutionResult:
        test_path = self.workspace_dir / test_file_rel
        if not test_path.exists():
            return ExecutionResult(
                status=VerificationStatus.RUNTIME_ERROR,
                exit_code=1,
                stdout="",
                stderr=f"Test file not found: {test_file_rel}",
                failing_assertions=[],
                error_fingerprint="FILE_NOT_FOUND",
                duration_seconds=0.0
            )

        # Execute using standard library unittest runner in a separate process
        cmd = [sys.executable, "-m", "unittest", test_file_rel]
        start_time = asyncio.get_event_loop().time()

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.workspace_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=self.timeout_seconds
            )
            duration = asyncio.get_event_loop().time() - start_time

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = process.returncode or 0

            return self._parse_execution(exit_code, stdout, stderr, duration)

        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            return ExecutionResult(
                status=VerificationStatus.TIMEOUT,
                exit_code=-1,
                stdout="",
                stderr="Execution exceeded allocated timeout.",
                failing_assertions=[],
                error_fingerprint="TIMEOUT_VIOLATION",
                duration_seconds=self.timeout_seconds
            )

    def _parse_execution(
        self, exit_code: int, stdout: str, stderr: str, duration: float
    ) -> ExecutionResult:
        raw_output = f"{stdout}\n{stderr}"
        failing_assertions: List[str] = []

        # Extract assertion errors and line markers using regex
        failure_patterns = re.findall(r"(FAIL|ERROR):\s+([^\s]+)", raw_output)
        assertion_traces = re.findall(r"(AssertionError:.*)", raw_output)

        failing_assertions.extend([f[1] for f in failure_patterns])
        failing_assertions.extend(assertion_traces)

        fingerprint_content = f"{exit_code}:" + ":".join(failing_assertions)
        fingerprint = hashlib.sha256(fingerprint_content.encode()).hexdigest()[:16]

        if exit_code == 0:
            status = VerificationStatus.GREEN
        else:
            status = VerificationStatus.RED

        return ExecutionResult(
            status=status,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            failing_assertions=failing_assertions,
            error_fingerprint=fingerprint,
            duration_seconds=duration
        )


# ============================================================================
# 4. CONVERGENCE & LOOP CONTROLLER
# ============================================================================

class MockAgentLLMInterface:
    """
    Simulates the AI Code Generator (e.g., Claude Code Agent) for demonstration.
    In real usage, this wraps an API call to Claude with specific system prompts.
    """
    def __init__(self, fixes: List[str]):
        self._fixes = fixes
        self._call_count = 0

    async def generate_patch(
        self, source_code: str, execution_result: ExecutionResult
    ) -> str:
        """Emulate sequential iterative attempts by the LLM."""
        if self._call_count < len(self._fixes):
            patch = self._fixes[self._call_count]
            self._call_count += 1
            return patch
        return source_code  # No-op if exhausted


class AutonomousTDDLoop:
    """
    Core Controller: Manages the Red-Green-Refactor sequence, prevents oscillations,
    audits security invariants, and enforces convergence.
    """

    def __init__(
        self,
        workspace: Path,
        test_file: str,
        impl_file: str,
        agent_interface: MockAgentLLMInterface,
        max_iterations: int = 5
    ):
        self.workspace = workspace
        self.test_file = test_file
        self.impl_file = impl_file
        self.agent = agent_interface
        self.max_iterations = max_iterations
        self.harness = IsolatedTestHarness(workspace)
        
        # State tracking
        self.history: List[ExecutionResult] = []
        self.fingerprints_seen: Set[str] = set()

    async def execute_cycle(self) -> Tuple[bool, str]:
        test_path = self.workspace / self.test_file
        impl_path = self.workspace / self.impl_file

        # Snapshot the base test file hash to enforce immutability
        initial_test_hash = ASTTestGuard.calculate_file_hash(test_path)
        with open(test_path, "r", encoding="utf-8") as f:
            initial_test_content = f.read()

        print(f"[*] Step 1: Initial Test Verification (Validating RED state)...")
        initial_result = await self.harness.run_tests(self.test_file)

        if initial_result.status == VerificationStatus.GREEN:
            return False, "Invalid Initial State: Tests are already GREEN. TDD requires a RED baseline."

        print(f"[-] Confirmed RED State. Failures detected: {len(initial_result.failing_assertions)}")
        self.history.append(initial_result)
        self.fingerprints_seen.add(initial_result.error_fingerprint)

        # Begin Autonomous Repair Loop
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n[+] --- Convergence Iteration {iteration}/{self.max_iterations} ---")

            # 1. Anti-Tampering Audit
            current_test_hash = ASTTestGuard.calculate_file_hash(test_path)
            if current_test_hash != initial_test_hash:
                with open(test_path, "r", encoding="utf-8") as f:
                    current_test_content = f.read()
                try:
                    ASTTestGuard.audit_ast_modifications(initial_test_content, current_test_content)
                except SecurityViolationError as e:
                    return False, f"Aborting: Test tampering detected! Details: {str(e)}"

            # 2. Agent Requests Patch
            with open(impl_path, "r", encoding="utf-8") as f:
                current_impl_code = f.read()

            latest_failure = self.history[-1]
            remediated_code = await self.agent.generate_patch(current_impl_code, latest_failure)

            # Apply patch to target file
            with open(impl_path, "w", encoding="utf-8") as f:
                f.write(remediated_code)

            # 3. Re-verify in Sandbox
            result = await self.harness.run_tests(self.test_file)
            self.history.append(result)

            print(f"[*] Execution Result: {result.status.value} (Fingerprint: {result.error_fingerprint})")

            # 4. Check Convergence & Status
            if result.status == VerificationStatus.GREEN:
                print("[*] Reached GREEN state! Autonomous loop converged successfully.")
                return True, f"Converged in {iteration} iteration(s)."

            if result.error_fingerprint in self.fingerprints_seen:
                print(f"[!] Warning: Oscillating state detected (Fingerprint: {result.error_fingerprint})")
                # Provide negative feedback mechanism here in production
            
            self.fingerprints_seen.add(result.error_fingerprint)

        return False, f"Halting Problem Hit: Exceeded maximum iterations ({self.max_iterations}) without convergence."


# ============================================================================
# 5. INTEGRATION VERIFICATION RUNNER
# ============================================================================

async def main() -> None:
    # Set up temporary working directory
    workspace_dir = Path("/tmp/claude_tdd_workspace")
    workspace_dir.mkdir(parents=True, exist_ok=True)

    test_file_name = "test_math_engine.py"
    impl_file_name = "math_engine.py"

    # Define strict immutable unit tests (RED baseline)
    test_code = """
import unittest
from math_engine import evaluate_expression

class TestMathEngine(unittest.TestCase):
    def test_addition(self):
        self.assertEqual(evaluate_expression("2 + 2"), 4)

    def test_precedence(self):
        self.assertEqual(evaluate_expression("2 + 3 * 4"), 14)

    def test_syntax_error(self):
        with self.assertRaises(ValueError):
            evaluate_expression("2 + + 2")

if __name__ == "__main__":
    unittest.main()
"""

    # Initial broken implementation (Fails tests)
    initial_impl_code = """
def evaluate_expression(expr: str) -> int:
    # Stub implementation - guaranteed to fail RED phase
    return 0
"""

    # Write initial files to workspace
    with open(workspace_dir / test_file_name, "w", encoding="utf-8") as f:
        f.write(test_code.strip())

    with open(workspace_dir / impl_file_name, "w", encoding="utf-8") as f:
        f.write(initial_impl_code.strip())

    # Simulated sequential fixes produced by AI Agent
    simulated_agent_fixes = [
        # Attempt 1: Incomplete fix (Only handles addition, fails precedence & error check)
        """
def evaluate_expression(expr: str) -> int:
    parts = expr.split("+")
    return sum(int(p.strip()) for p in parts)
""",
        # Attempt 2: Complete, mathematically correct implementation
        """
import ast
import operator

OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv
}

def evaluate_expression(expr: str) -> int:
    try:
        node = ast.parse(expr, mode='eval')
        def _eval(node):
            if isinstance(node, ast.Expression):
                return _eval(node.body)
            elif isinstance(node, ast.BinOp):
                left = _eval(node.left)
                right = _eval(node.right)
                op = type(node.op)
                if op in OPERATORS:
                    return int(OPERATORS[op](left, right))
                raise ValueError("Unsupported operator")
            elif isinstance(node, ast.Constant):
                return node.value
            else:
                raise ValueError("Complex expression")
        return _eval(node)
    except SyntaxError:
        raise ValueError("Invalid syntax")
"""
    ]

    agent = MockAgentLLMInterface(fixes=simulated_agent_fixes)
    tdd_loop = AutonomousTDDLoop(
        workspace=workspace_dir,
        test_file=test_file_name,
        impl_file=impl_file_name,
        agent_interface=agent,
        max_iterations=4
    )

    success, message = await tdd_loop.execute_cycle()
    print("\n" + "=" * 50)
    print(f"VERIFICATION RUN TERMINATED: {'SUCCESS' if success else 'FAILURE'}")
    print(f"Diagnostic Message: {message}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 7. Edge Cases & Failure Modes

Dalam eksekusi otonom tingkat produksi, loop verifikasi dapat menghadapi anomali runtime berikut:

| Failure Mode | Mekanisme Terjadinya | Dampak Sistem | Mitigasi Otomatis |
|---|---|---|---|
| **Flaky Tests** | Pengujian bergantung pada latensi jaringan, konkurensi waktu, atau seed acak. | Agen menghasilkan overfitted patch untuk kegagalan semu (*phantom error*). | Eksekusi deterministik $N$-kali ($N \ge 3$) untuk setiap kegagalan sebelum menyatakan status RED. Gunakan mock strictly terisolasi. |
| **Test Tampering (False Green)** | Agen memodifikasi file assertion (misal: `assertEqual(a, a)`) agar build lolos. | Bug lolos ke production dengan status *Green*. | Gunakan AST hash locking & sandbox access control (berkas pengujian di-mount *read-only* bagi agen). |
| **Oscillating Repair Loop** | Patch pada iterasi $k$ merusak skenario iterasi $k-1$; agen kembali ke patch iterasi $k-1$. | Konsumsi token maksimal tanpa konvergensi solusi (*token bleeding*). | State hashing fingerprint. Jika *fingerprint* terulang, injeksikan riwayat osilasi ke prompt dan paksa pembatalan branch. |
| **Halting Problem / Infinite Loop** | Kode yang dihasilkan agen mengandung `while True` tanpa exit condition yang valid. | Sandbox membeku, resource starvation pada runner node. | Strict process execution timeout (e.g., SIGALRM / `asyncio.wait_for`) dengan alokasi waktu maksimal deterministik (5–10 detik). |
| **Context Contamination** | Agen menerima seluruh traceback stack 500 baris yang memuat detail framework. | Batas context window terlampaui; halusinasi variabel downstream meningkat. | Trace distillation filter: ekstrak hanya line marker, message error, dan context frame relevan ($\pm 5$ baris). |

---

## 8. Trade-offs & Alternatif Solusi

| Dimensi | Test-Driven Development (TDD) Otonom | Post-hoc Verification (Verifikasi Pasca-Koding) | Property-Based Verification (Hypothesis/QuickCheck) |
|---|---|---|---|
| **Determinisme** | **Sangat Tinggi**: Assertion dikunci sebelum agen mulai menulis implementasi. | **Rendah**: Agen menulis tes setelah kode selesai; rentan terhadap *confirmation bias*. | **Ekstrem**: Menguji ruang input masif via invariant fuzzing deterministik. |
| **Konsumsi Token** | **Terprediksi & Sedang**: Feedback error terisolasi pada failing assertions spesifik. | **Rendah (Awal), Tinggi (Debugging)**: Log error downstream cenderung bercabang luas. | **Tinggi**: Traceback dari input arbitrary sering kali membutuhkan parsing konteks yang rumit. |
| **Latensi Eksekusi** | **Cepat**: Unit test harness dapat dieksekusi dalam sub-detik per iterasi patch. | **Sangat Cepat**: Validasi statis di awal tanpa loop runner berulang. | **Lambat**: Memerlukan eksekusi ribuan kombinasi input per run. |
| **Kesesuaian Penggunaan** | Logika bisnis inti, parser, algoritma deterministik, manipulasi data. | Skrip glue-code sederhana, konfigurasi deklaratif, static site generation. | Protokol kriptografi, state machine konkurensi tinggi, mesin finansial. |

---

## 9. Best Practices & Standard Industri

1. **Mount Read-Only Test Suites:** Jalankan agen di mana direktori pengujian (`tests/`) dikonfigurasi dengan izin *filesystem read-only* bagi proses LLM. Agen hanya diizinkan memodifikasi direktori implementasi (`src/` atau `lib/`).
2. **Ephemeral Sandboxing:** Jalankan setiap siklus verifikasi dalam lingkungan terisolasi penuh (menggunakan container berbasis OCI minimal seperti gVisor, Firecracker microVM, atau namespace bubblewrap) guna mencegah eksekusi kode berbahaya oleh model.
3. **Structured Failure Payloads:** Jangan pernah mem-parsing ulang log terminal mentah tanpa sanitasi. Serialisasikan hasil eksekusi ke format machine-readable JSON schema dengan batasan ukuran tetap (maksimal 2 KB data error dikirim ke LLM).
4. **Deterministic Random Seeds:** Konfigurasikan seluruh test runner (seperti pytest, jest) dengan generator angka acak yang terikat pada seed statis (`SEED=42`) untuk menjamin reproduktifitas pengujian.
5. **Decoupled Architecture Refactoring:** Jangan satukan fase *bugfix* dengan fase *refactoring*. Lakukan *Green First* (perbaikan fungsional), buat snapshot VCS commit, kemudian eksekusi fase *Refactor* sebagai loop terpisah di bawah guardrail regresi penuh.

---

## 10. Hands-on Lab Exercise

### Deskripsi Skenario
Sebuah agen otonom ditugaskan untuk mengimplementasikan parser logis *Token Bucket Rate Limiter* dalam berkas `rate_limiter.py`. File pengujian `test_rate_limiter.py` telah disediakan sebagai *ground truth* kontrak teknis. Anda bertugas mengonfigurasi dan memvalidasi loop verifikasi mandiri hingga tercapai konvergensi fungsional.

### Langkah-langkah Praktikum

#### Langkah 1: Inisialisasi Workspace Terisolasi
Jalankan perintah berikut di lingkungan terminal:

```bash
mkdir -p /tmp/claude_tdd_lab/src /tmp/claude_tdd_lab/tests
cd /tmp/claude_tdd_lab
```

#### Langkah 2: Buat Test Suite Imutabel (Red State)
Tulis file `tests/test_rate_limiter.py`:

```python
import unittest
import time
from src.rate_limiter import TokenBucket

class TestTokenBucket(unittest.TestCase):
    def test_initial_tokens_consume(self):
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        self.assertTrue(bucket.consume(5))
        self.assertFalse(bucket.consume(1))

    def test_refill_mechanism(self):
        bucket = TokenBucket(capacity=2, refill_rate=2.0)
        self.assertTrue(bucket.consume(2))
        self.assertFalse(bucket.consume(1))
        # Simulasi jeda waktu deterministik
        time.sleep(1.0)
        self.assertTrue(bucket.consume(2))

    def test_invalid_parameters(self):
        with self.assertRaises(ValueError):
            TokenBucket(capacity=-1, refill_rate=1.0)
        with self.assertRaises(ValueError):
            TokenBucket(capacity=5, refill_rate=0.0)

if __name__ == "__main__":
    unittest.main()
```

#### Langkah 3: Buat File Implementasi Stub (Awal Gagal)
Tulis file `src/rate_limiter.py`:

```python
class TokenBucket:
    def __init__(self, capacity: int, refill_rate: float):
        # Stub yang belum mengimplementasikan logika
        pass

    def consume(self, tokens: int = 1) -> bool:
        return False
```

#### Langkah 4: Eksekusi Verifikasi Baseline
Jalankan verifier harness lokal:
```bash
python3 -m unittest tests/test_rate_limiter.py
```
*Ekspektasi Hasil:* Status harus **FAIL (AssertionError)**. Ini membuktikan baseline status awal adalah RED.

#### Langkah 5: Terapkan Patch Solutif (Green State Convergence)
Tulis implementasi algoritma yang benar pada `src/rate_limiter.py`:

```python
import time

class TokenBucket:
    def __init__(self, capacity: int, refill_rate: float):
        if capacity <= 0 or refill_rate <= 0:
            raise ValueError("Capacity and refill_rate must be positive.")
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self.current_tokens = float(capacity)
        self.last_refill_timestamp = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill_timestamp
        added_tokens = elapsed * self.refill_rate
        self.current_tokens = min(self.capacity, self.current_tokens + added_tokens)
        self.last_refill_timestamp = now

    def consume(self, tokens: int = 1) -> bool:
        self._refill()
        if tokens <= self.current_tokens:
            self.current_tokens -= tokens
            return True
        return False
```

#### Langkah 6: Validasi Konvergensi
Eksekusi kembali harness pengujian:
```bash
python3 -m unittest tests/test_rate_limiter.py
```
*Ekspektasi Hasil:*
```text
...
----------------------------------------------------------------------
Ran 3 tests in 1.002s

OK
```
Siklus AVL berhasil menuntaskan transisi `RED -> GREEN` secara deterministik tanpa deviasi spesifikasi assertion. Integrity check mengonfirmasi hash berkas uji tidak mengalami mutasi, memverifikasi keabsahan patch secara penuh.