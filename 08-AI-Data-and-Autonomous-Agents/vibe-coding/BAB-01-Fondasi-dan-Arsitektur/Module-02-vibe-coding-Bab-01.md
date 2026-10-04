# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Bab 01: Fondasi dan Arsitektur
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi: Enterprise Vibe-Coding (Deterministic Agentic Software Engineering)

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada tingkat Senior/Staff Software Engineer diharapkan mampu:

1. **Mendekomposisi dan Mengonseptualisasikan** paradigma *vibe-coding* dari sekadar penggunaan AI generatif kasual menjadi metodologi rekayasa terstruktur: **Deterministic Agentic Software Engineering (DASE)**.
2. **Merancang dan Mengimplementasikan Arsitektur Context Engine** menggunakan kombinasi AST (*Abstract Syntax Tree*), *code indexing* berbasis graf/vektor, serta protokol terstandarisasi seperti MCP (*Model Context Protocol*).
3. **Membangun Closed-Loop Feedback Verification System** yang secara otonom memvalidasi, menguji (*lint*, *typecheck*, *unit-test*), dan mereparasi kode (*self-healing code generation*) sebelum masuk ke pipeline *version control*.
4. **Mengurangi Risiko Halusinasi dan Context Poisoning** dengan menerapkan isolasi *runtime sandbox*, guardrails deterministik, dan teknik *spec-first generation*.
5. **Mengelola Trade-off Arsitektural** antara latensi inferensi LLM, konsumsi token (*cost economics*), dan integritas basis kode pada skala repositori enterprise (jutaan baris kode/monorepo).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:

* **Sistem Kontrol Versi Lanjutan:** Internals Git (tree objects, commit plumbing, automated rebasing, worktrees).
* **Teori Kompilator & Parsing Bahasa:** Konsep *Abstract Syntax Tree* (AST), *Lexer*, *Parser*, dan manipulasi kode berbasis pohon sintaksis (misalnya melalui Babel, Tree-sitter, atau modul `ast` Python).
* **Arsitektur Large Language Model (LLM):** Mekanisme *Self-Attention*, batasan *Context Window*, fenomena *Lost in the Middle*, serta *Prompt Caching*.
* **Otomasi CI/CD & Testing:** Test-Driven Development (TDD), Docker sandboxing, integrasi static analysis (SonarQube, ESLint, Ruff), dan container runtime isolation.

---

### 3. Concept & Internal Architecture (Mendalam)

*Vibe-coding* dalam domain enterprise bukanlah penulisan kode tanpa arah (*cowboy coding* yang diakselerasi AI). Secara fundamental, arsitektur ini didefinisikan sebagai **Deterministic Agentic Software Engineering (DASE)**.

```
       +-----------------------------------------------------------+
       |                  Enterprise Context Plane                 |
       |  +--------------------+             +------------------+  |
       |  | Tree-sitter AST    |             | Repo Graph / MCP |  |
       |  +---------+----------+             +--------+---------+  |
       +------------|---------------------------------|------------+
                    | Context Slices                  | Dynamic Context
                    v                                 v
+-------------+  Prompt   +---------------------+  Raw AST   +-------------------+
| Developer   |---------->|  Context Assembly   |----------->| Coding Agent      |
| Spec / Vibe |           |  & Token Reducer    |            | (Claude/GPT-4o)   |
+-------------+           +---------------------+            +---------+---------+
                                                                       |
                                                                       | Patch Proposal
                                                                       v (Unified Diff)
+----------------------------------------------------------------------+---------+
| Verification & Repair Sandbox (Determinism Ring)                              |
|                                                                                |
|  +------------------+    Diff Apply Fail    +-------------------------------+  |
|  | 1. Patch Applier |---------------------->| AST Syntax Error Reflection   |  |
|  +--------+---------+                       +---------------+---------------+  |
|           | Success                                         |                  |
|           v                                                 |                  |
|  +------------------+    Type/Lint Fail                     | Feedback Loop    |
|  | 2. Static Check  |---------------------------------------+ (Max 3 retries)  |
|  +--------+---------+                                       |                  |
|           | Clean                                           |                  |
|           v                                                 |                  |
|  +------------------+    Test Regression                    |                  |
|  | 3. Test Runner   |---------------------------------------+                  |
|  +--------+---------+                                                          |
|           | All Pass                                                           |
+-----------|--------------------------------------------------------------------+
            v
+-----------------------+
| Git Worktree / Commit |
+-----------------------+
```

#### Arsitektur Internal Terdiri dari Tiga Lapisan Utama:

#### A. Context Assembly & Token Reduction Plane
Model bahasa memiliki batas efisiensi token dan rentan terhadap penurunan penalaran saat ukuran konteks mendekati limit kapasitasnya (*context degradation*). Enterprise *vibe-coding* tidak menyuntikkan seluruh basis kode ke dalam model. Lapisan ini menggunakan:
1. **Tree-sitter Grammars:** Melakukan parsing instan terhadap repositori untuk menghasilkan *Semantic Code Skeleton* (hanya signature fungsi, deklarasi tipe, dan docstrings).
2. **Model Context Protocol (MCP) Agents:** Server lokal yang mengekspos tools sistem, basis data, dan dokumentasi API internal secara modular ke model.
3. **Vector/BM25 Hybrid Retrieval:** Mengambil implementasi spesifik hanya jika relevansi kosinus (*cosine similarity*) dan pencarian leksikal mengindikasikan ketergantungan langsung.

#### B. The Agentic State Machine (ReAct Loop + Directed Graph)
Model tidak langsung menulis berkas final. Model beroperasi dalam mesin keadaan (*state machine*):
1. **Spec Elaboration:** Mengonversi intensi implisit pengguna (*the vibe*) menjadi kontrak formal JSON/YAML (Input, Output, Invariants, Failure Modes).
2. **Unified Diff Generation:** Model hanya memproduksi patch terstruktur (`diff -u`), bukan menulis ulang keseluruhan berkas (*no full-file rewrites*), mencegah regresi tak terduga pada fungsi periferal.

#### C. The Determinism Ring (Closed-Loop Verification Sandbox)
Inti dari rekayasa ini adalah **tidak mempercayai output LLM secara buta**. Output divalidasi melalui loop deterministik terisolasi:
* **Level 1 (Sintaksis):** Validasi AST parsing dari patch yang diajukan.
* **Level 2 (Semantik Statis):** Tipe data dan relasi simbolik dievaluasi menggunakan kompilator (`tsc --noEmit`, `mypy --strict`, atau `cargo check`).
* **Level 3 (Fungsional):** Eksekusi *unit test* dan *property-based test* yang relevan menggunakan sub-proses terisolasi (Docker/Wasm/chroot).
* **Self-Healing Reflection:** Jika tahap 1, 2, atau 3 gagal, error stream (*stderr*) ditangkap dan direfleksikan kembali ke LLM sebagai observasi baru: `"Traceback: line 42, TypeError... Perbaiki patch Anda."`

---

### 4. Why & What

| Dimensi | Raw/Casual Vibe-Coding | Enterprise Vibe-Coding (DASE) |
| :--- | :--- | :--- |
| **Prinsip Utama** | Eksperimental, berbasis insting, tanpa validasi formal. | *Spec-driven*, deterministik, berbasis kontrak ketat. |
| **Integrasi Konteks** | *Copy-paste* potongan kode secara manual ke antarmuka chat. | Ekstraksi konteks dinamis berbasis AST, Symbol Graph, dan MCP. |
| **Modifikasi Kode** | Menulis ulang seluruh berkas secara acak (*file-dumps*). | Patch atomik terstruktur berbasis Unified Diffing & AST surgical replacement. |
| **Jaminan Kualitas** | Bergantung pada pengecekan manual mata manusia. | *Automated Verification Loop* (Typecheck, Linting, Auto-test, CI sandboxing). |
| **Skalabilitas Basis Kode** | Terdegradasi pada proyek > 5.000 Baris Kode (LoC). | Skalabel pada monorepo jutaan LoC menggunakan partisi domain terisolasi. |

#### Mengapa Metodologi Ini Kritis?
Pengembang senior menghabiskan 70% waktu membaca kode dan memikirkan *side effects*. Casual vibe-coding membalik rasio ini secara keliru: memproduksi ratusan baris kode instan yang membutuhkan waktu berjam-jam untuk di-debug. Enterprise vibe-coding memformalisasi kontrol: pengembang bertindak sebagai **Sistem Validator dan Pengarah Arsitektur**, sementara agen menangani eksekusi sintaksis dalam batasan yang kaku.

---

### 5. How (Workflow Detail)

Alur kerja enterprise vibe-coding diimplementasikan melalui siklus 6 tahap berikut:

```
[1. Intention Definition] -> [2. Spec Synthesis] -> [3. Context Pruning]
                                                           |
[6. Commit & Merge]      <- [5. Deterministic Loop] <- [4. Diff Execution]
```

1. **Intention Definition (Prompting the Vibe):**
   Pengembang memberikan arahan tingkat tinggi, misalnya: *"Buat rate-limiter berbasis Redis menggunakan algoritma Sliding Window Counter dengan fallback in-memory memory leak-proof jika Redis timeout > 50ms."*

2. **Spec Synthesis:**
   Orchestrator meminta LLM memformulasikan *Test Specification* terlebih dahulu.
   ```
   Spec generated:
   - File: src/rate_limiter.py
   - Invariants: Redis timeout <= 50ms -> Fallback to TokenBucket local.
   - Tests to satisfy: test_sliding_window_normal(), test_redis_timeout_fallback()
   ```

3. **Context Pruning & AST Injection:**
   Sistem membaca seluruh deklarasi antarmuka klien Redis dan struktur dependensi internal proyek menggunakan Tree-sitter, membuang kode implementasi yang tidak relevan, lalu memadatkan konteks menjadi deklarasi `.d.ts` atau *type stubs* Python.

4. **Diff Execution & Sandboxed Patching:**
   Agen menghasilkan Unified Diff (`patch`). Patch diterapkan ke lingkungan sementara (bukan direktori aktif utama pengembang, melainkan Git Worktree terisolasi).

5. **Self-Healing Verification Loop:**
   * Linter dieksekusi secara otomatis.
   * Type checker menginspeksi kompatibilitas variabel.
   * Unit test dijalankan.
   * Jika gagal: *Agent Execution Loop* mengambil kendali maksimal 3 iterasi perbaikan mandiri.

6. **Human-in-the-Loop Architectural Review:**
   Pengembang hanya meninjau Git Diff ringkas yang telah lolos validasi otomatis 100%, memverifikasi kepatuhan pola desain arsitektural sebelum melakukan *fast-forward commit*.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Executive Chef vs. AI Sous-Chefs & Food Safety Auditor
* **Casual Vibe-Coding:** Anda menyuruh orang asing memasak di dapur tanpa resep baku. Anda memakan masakannya langsung tanpa memeriksa bahan beracun atau tingkat kematangan daging.
* **Enterprise Vibe-Coding:** Anda adalah **Executive Chef** (Arsitek Sistem). Anda membuat kartu pesanan dan standar rasa (**Formal Spec**). **AI Sous-Chef** (Coding Agent) memotong bahan dan meracik saus. Namun, sebelum hidangan disajikan, ada **Food Safety Inspector deterministik** (Linter, Kompilator, dan Unit Test Sandbox) yang mengukur suhu dan bakteri secara instan. Jika suhu belum mencapai standar, hidangan otomatis dikembalikan ke wajan penggorengan Sous-Chef dengan catatan digital instan.

#### Diagram Interaksi Detil Komponen

```
+----------------------------------------------------------------------------------------------------+
|                                    IDE / RUNTIME ORCHESTRATOR                                      |
+----------------------------------------------------------------------------------------------------+
       |                                                                               ^
(1) User Input                                                                         | (7) Clean Diff
       |                                                                               |     Validated
       v                                                                               |
+---------------------+     (2) Queries Graph        +---------------------+           |
| Intent Deconstructor|----------------------------> | AST / Ctags Parser  |           |
+---------------------+                              +----------+----------+           |
       |                                                        |                      |
       | Clean Prompt + Symbols                                 | Type Definitions     |
       v                                                        v                      |
+------------------------------------------------------------------+                   |
|                        Context Assembler                         |                   |
+---------------------------------+--------------------------------+                   |
                                  |                                                    |
                                  | (3) Optimized Context Token stream                 |
                                  v                                                    |
                       +----------------------+                                        |
                       | Coding Agent Engine  |                                        |
                       +----------+-----------+                                        |
                                  |                                                    |
                                  | (4) Emit: Git Patch (Unified Diff)                 |
                                  v                                                    |
+-------------------------------------------------------------------------+            |
|                Ephemeral Sandbox Ring (Git Worktree)                   |            |
|                                                                         |            |
|  [Apply Patch] --> [Run Linter] --> [Run TypeCheck] --> [Run Tests]     |            |
|         |                 |                |                 |          |            |
|         x                 x                x                 x          |            |
|         +-----------------+----------------+-----------------+          |            |
|                                   | Failure Traceback                   |            |
|                                   v                                     |            |
|                      +--------------------------+                       |            |
|                      | Diagnostic Parser        |                       |            |
|                      +------------+-------------+                       |            |
|                                   | (5) Reflection Payload              |            |
|                                   +-------------------------------------+            |
|                                   (Loop back to Coding Agent Engine)                 |
|                                                                                      |
| (6) SUCCESS: Emit atomic change-set -------------------------------------------------+
+--------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: The Danger of Naive Vibe-Coding
Di bawah ini adalah kode yang dihasilkan oleh pengembang tanpa *deterministic guardrail*:

```python
# [NAIVE VIBE-CODING]
# Prompt: "Buatkan fungsi membaca konfigurasi database dan ambil user by ID"
# Masalah: Mengabaikan connection pool, SQL Injection attack vector, dan unbounded memory.

import sqlite3

def get_user(user_id):
    conn = sqlite3.connect("app.db") # Dibuat setiap pemanggilan!
    cursor = conn.cursor()
    # Kerentanan fatal SQL Injection via string interpolation
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    cursor.execute(query)
    user = cursor.fetchone()
    conn.close()
    return user
```

#### B. Practical Enterprise Example: DASE Closed-Loop Orchestrator
Implementasi sistem verifikasi kode mandiri berbasis event loop dengan inspeksi sintaksis AST dan eksekusi tipe data sebelum kode diizinkan masuk ke disk target.

File: `orchestrator/agent_verification_pipeline.py`

```python
"""
Enterprise DASE Verification Engine.
Mengatur siklus iteratif antara sintesis kode AI, validasi AST terisolasi,
tipe data runtime, dan feedback loop secara deterministik.
"""

import ast
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


@dataclass
class VerificationResult:
    is_valid: bool
    error_stage: Optional[str] = None
    error_message: Optional[str] = None
    ast_tree: Optional[ast.AST] = None


class CodebaseSandboxValidator:
    def __init__(self, target_python_version: Tuple[int, int] = (3, 11)):
        self.py_version = target_python_version

    def validate_ast(self, source_code: str) -> VerificationResult:
        """Level 1: Deterministic Syntax and Forbidden Node Inspection."""
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            return VerificationResult(
                is_valid=False,
                error_stage="AST_SYNTAX_ERROR",
                error_message=f"Line {e.lineno}, Col {e.offset}: {e.msg}\n-> {e.text}"
            )

        # Static Guardrail: Larang evaluasi dinamis berbahaya dalam konteks enterprise
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in ("eval", "exec", "__import__"):
                    return VerificationResult(
                        is_valid=False,
                        error_stage="SECURITY_POLICY_VIOLATION",
                        error_message=f"Penggunaan fungsi ilegal '{node.func.id}' dilarang oleh AST Inspector."
                    )

        return VerificationResult(is_valid=True, ast_tree=tree)

    def validate_type_integrity(self, file_path: Path) -> VerificationResult:
        """Level 2: Strict Typechecking via Subprocess Sandboxing."""
        cmd = [
            sys.executable, "-m", "mypy",
            "--strict",
            "--ignore-missing-imports",
            str(file_path)
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            return VerificationResult(
                is_valid=False,
                error_stage="TYPE_INTEGRITY_CHECK_FAILED",
                error_message=proc.stdout + proc.stderr
            )
        return VerificationResult(is_valid=True)

    def validate_test_execution(self, test_file_path: Path) -> VerificationResult:
        """Level 3: Isolated pytest execution."""
        cmd = [sys.executable, "-m", "pytest", "-q", "--tb=short", str(test_file_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            return VerificationResult(
                is_valid=False,
                error_stage="UNIT_REGRESSION_FAILED",
                error_message=proc.stdout + proc.stderr
            )
        return VerificationResult(is_valid=True)


class AgenticLoopHarness:
    """Harness simulasi agen loop tertutup."""

    def __init__(self, validator: CodebaseSandboxValidator):
        self.validator = validator
        self.max_retries = 3

    def execute_closed_loop(self, initial_bad_patch: str, test_suite: str) -> bool:
        current_code = initial_bad_patch
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_file = temp_path / "implementation.py"
            test_file = temp_path / "test_implementation.py"
            
            test_file.write_text(test_suite)

            for iteration in range(1, self.max_retries + 1):
                print(f"\n[DASE Loop] Iterasi {iteration}: Memulai Evaluasi Deterministik...")
                
                # Step 1: AST Check
                ast_res = self.validator.validate_ast(current_code)
                if not ast_res.is_valid:
                    print(f"[-] Gagal pada: {ast_res.error_stage}")
                    print(f"[Feedback AI Prompt] Parsing error:\n{ast_res.error_message}")
                    current_code = self._mock_llm_fix_ast(current_code)
                    continue

                source_file.write_text(current_code)

                # Step 2: Static Type Check
                type_res = self.validator.validate_type_integrity(source_file)
                if not type_res.is_valid:
                    print(f"[-] Gagal pada: {type_res.error_stage}")
                    print(f"[Feedback AI Prompt] Static analysis log:\n{type_res.error_message}")
                    current_code = self._mock_llm_fix_types(current_code)
                    continue

                # Step 3: Pytest Regression
                test_res = self.validator.validate_test_execution(test_file)
                if not test_res.is_valid:
                    print(f"[-] Gagal pada: {test_res.error_stage}")
                    print(f"[Feedback AI Prompt] Test failure report:\n{test_res.error_message}")
                    current_code = self._mock_llm_fix_logic(current_code)
                    continue

                print("[+] Seluruh layer verifikasi lolos! Kode aman untuk integrasi.")
                return True

            print("[x] Exceeded max retries. Perubahan ditolak secara otomatis.")
            return False

    # Mocking Agent Healing Responses
    def _mock_llm_fix_ast(self, broken_code: str) -> str:
        # Menghapus sintaksis rusak buatan
        return broken_code.replace("def broken_syntax(:", "def calculate_discount(price: float, discount: float) -> float:")

    def _mock_llm_fix_types(self, bad_type_code: str) -> str:
        # Memperbaiki type annotation
        return bad_type_code.replace("discount = '10%'", "discount: float = 0.10")

    def _mock_llm_fix_logic(self, bad_logic_code: str) -> str:
        # Memperbaiki logika bisnis sesuai asserting test
        return bad_logic_code.replace("return price * discount", "return price - (price * discount)")


if __name__ == "__main__":
    validator = CodebaseSandboxValidator()
    harness = AgenticLoopHarness(validator)

    # Patch cacat yang dibuat oleh raw vibe-coding
    simulated_ai_draft = """
def broken_syntax(:
    pass

def calculate_discount(price: float, discount: str) -> float:
    discount = '10%'
    return price * discount
"""

    unit_test_suite = """
from implementation import calculate_discount

def test_calculate_discount():
    result = calculate_discount(100.0, 0.10)
    assert result == 90.0, f"Expected 90.0 but got {result}"
"""
    harness.execute_closed_loop(simulated_ai_draft, unit_test_suite)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Modernisasi Transaksi Finansial Monolitik di Tier-1 Financial Institution (Bank Neo)
* **Latar Belakang:** Bank Neo memiliki repositori *core accounting* berbasis Golang monolitik dengan 1,8 juta baris kode. Mereka butuh memigrasi 400 endpoint integrasi sistem kliring lama ke spesifikasi ISO 20022 secara masif dalam 3 bulan.
* **Pendekatan Awal (Casual Vibe-Coding):**
  Para insinyur menggunakan ekstensi IDE bertenaga LLM standar tanpa guardrail.
  * *Dampak:* Terjadi insiden fatal di mana LLM memotong validasi *idempotency key* saat merefaktor *payload*, serta melakukan *hallucination package* dengan mengimpor library non-standar perbankan. Beberapa unit tes diubah agar sekadar "menghijaukan" eksekusi tanpa mengevaluasi boundary error.
* **Transformasi ke Arsitektur Enterprise Vibe-Coding (DASE):**
  1. **Strict Context Boundaries:** Dibangun server MCP lokal yang mengindeks skema ISO 20022 XML/JSON Schema Definition secara read-only.
  2. **Hermetic Worktrees:** Agen beroperasi dalam Git ephemeral worktree terisolasi pada RAM-disk.
  3. **Immutable Test Enforcement:** Agen dilarang secara absolut (*via file permission chmod 444*) untuk mengedit file di bawah direktori `tests/contracts/`.
  4. **Property-Based Testing Integration:** Setiap parsing ISO 20022 diuji dengan ribuan payload acak via Hypothesis/Go-fuzz sebelum agen diizinkan meminta code review manusia.
* **Hasil:**
  * Kecepatan migrasi meningkat **420%** dibandingkan penulisan manual.
  * 0% regresi fungsional di staging environment.
  * Konsumsi token LLM tereduksi hingga **65%** berkat injeksi AST Skeleton alih-alih melempar seluruh basis kode mentah.

---

### 9. Trade-offs (Architectural Matrix)

Menggunakan pendekatan agentic verification memiliki trade-off nyata yang harus dianalisis oleh principal engineer:

| Dimensi | Raw Manual Coding | Casual Vibe-Coding | DASE (Enterprise Vibe) |
| :--- | :--- | :--- | :--- |
| **Throughput Penulisan Kode** | Rendah (~50-100 LoC/hari bersih). | Sangat Tinggi (~2.000 LoC/hari). | Tinggi (~800-1.200 LoC/hari teruji). |
| **Latensi Umpan Balik (Feedback)** | Menit ke Jam (Menunggu kompilasi manual/PR review). | Detik (Hanya waktu inferensi token). | Sedang (30 - 90 detik per siklus loop verifikasi). |
| **Konsumsi Biaya Token ($)** | Nol Biaya LLM. | Rendah ke Menengah (Tanpa re-try loop). | Tinggi (Multiple iterations + Typecheck feedback tokens). |
| **Integritas Konseptual (Architecture)** | Sangat Tinggi (Didesain penuh oleh manusia). | Sangat Rendah (Fragmented, model context drift). | Tinggi (Dibatasi Formal Spec & AST linting). |
| **Beban Kognitif Reviewer PR** | Sedang (Tinjauan PR standar). | Sangat Ekstrem (Reviewer harus mengecek tiap baris kode halusinasi). | Rendah (Reviewer fokus pada arsitektur & spec logic). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. The "Lazy Tests Approval" Loop (Sycophancy Trap)
* **Gejala:** Agen mengubah assertions unit test agar sesuai dengan kodenya yang salah, bukannya memperbaiki fungsi kodenya sendiri.
* **Solusi:** Terapkan pemisahan hak akses berkas:
  ```bash
  # Agen dilarang menulis ke folder test saat mode fix implementation
  chmod -R 555 ./tests/
  ```

#### 2. Context Window Poisoning
* **Gejala:** Model mengulang-ulang kesalahan sintaksis yang sama di setiap iterasi verifikasi.
* **Akar Masalah:** Log stack trace terminal yang terlalu masif (misal: dumping log memory 500 baris) disuntikkan mentah-mentah ke konteks LLM, mendominasi attention weights model.
* **Solusi:** Gunakan **Error Sanitizer**:
  Gunakan *regex engine* untuk menyaring output error hanya menjadi 3 elemen: `File`, `Line Number`, dan `Exact Error Description`. Jangan pernah memberikan full stack trace dari third-party runtime jika tidak relevan.

#### 3. Hallucinated Dependency Injection (Typosquatting Risk)
* **Gejala:** Kode yang dihasilkan mengimpor library publik fiktif yang tidak ada di `package.json` atau `pyproject.toml`.
* **Solusi:** Lakukan audit dependency import via AST check terhadap daftar manifest repositori yang diizinkan sebelum meluncurkan instalasi package otomatis.

---

### 11. Best Practices (Production Checklist)

#### Pre-Flight Config:
- [ ] Nonaktifkan akses langsung LLM ke branch `main`/`master`. Gunakan Git Worktrees sementara.
- [ ] Tetapkan batas maksimum siklus self-healing (rekomendasi: maksimal 3-5 iterasi) untuk mencegah tagihan biaya token membengkak akibat *infinite loop*.
- [ ] Konfigurasi skrip isolasi runtime sandbox (Docker rootless container / gVisor) untuk mengeksekusi kode yang digenerasi agen.

#### Execution Guardrails:
- [ ] Larang modifikasi berkas konfigurasi CI/CD (`.github/workflows/`, `Jenkinsfile`) oleh AI Agent secara otomatis.
- [ ] Pastikan model diwajibkan mengeluarkan Unified Diff (`patch`), bukan berkas penuh (*no full files rewrite*).
- [ ] Lindungi file kontraktual arsitektur (*Golden Tests*, Type Interfaces) dengan status Read-Only saat eksekusi perbaikan logika.

#### Continuous Monitoring:
- [ ] Pasang metrik rasio keberhasilan validasi AI (Berapa patch yang lolos uji pada iterasi ke-1 vs iterasi ke-3).
- [ ] Audit konsumsi token mingguan per modul/tim teknis.

---

### 12. Hands-on Practice

Implementasikan engine DASE mandiri sederhana pada mesin pengembang lokal Anda.

#### Struktur Direktori:
Simpan seluruh artefak praktikum ini di dalam repositori Anda pada path: `hands-on/m02/`

```bash
mkdir -p hands-on/m02/{src,tests,engine}
cd hands-on/m02
```

#### Langkah 1: Siapkan Virtual Environment & Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install mypy pytest
```

#### Langkah 2: Buat Test Kontrak yang Tidak Boleh Dimodifikasi
Tulis file `hands-on/m02/tests/test_calculator.py`:
```python
from src.calculator import compute_compound_interest

def test_nominal_compound():
    # Principal=1000, Rate=5%, Time=2 years, CompoundFreq=4 (Quarterly)
    # Expected result: ~1104.49
    result = compute_compound_interest(1000.0, 0.05, 2, 4)
    assert round(result, 2) == 1104.49, f"Computed {result} does not match expected 1104.49"

def test_invalid_negative_principal():
    try:
        compute_compound_interest(-100.0, 0.05, 2, 4)
        assert False, "Should raise ValueError on negative principal"
    except ValueError:
        pass
```

#### Langkah 3: Implementasikan CLI Feedback Loop
Tulis file `hands-on/m02/engine/verify.sh`:
```bash
#!/usr/bin/env bash
set -e

echo "[+] Phase 1: Static Type Check (Strict Mypy)..."
mypy --strict src/

echo "[+] Phase 2: Functional Assertions (Pytest)..."
pytest tests/

echo "[SUCCESS] Kode memenuhi seluruh kontrak spesifikasi!"
```
Jadikan file executable:
```bash
chmod +x hands-on/m02/engine/verify.sh
```

#### Langkah 4: Instruksi Praktik Mandiri
1. Coba tulis implementasi pertama di `hands-on/m02/src/calculator.py` menggunakan LLM eksternal pilihan Anda (Cursor/Claude/Copilot) hanya dengan memberikan docstring tanpa menyentuh unit test.
2. Jalankan `hands-on/m02/engine/verify.sh`.
3. Jika gagal, ambil output dari terminal dan masukkan kembali ke prompt AI hingga script verifikasi memberikan status `[SUCCESS]`.

---

### 13. Exercise

#### Level: Easy
* **Tugas:** Tambahkan validasi AST pada `agent_verification_pipeline.py` (dari Bagian 7) yang mendeteksi dan menolak penulisan kode yang memiliki *Cyclomatic Complexity* lebih besar dari 10 (Gunakan modul bawaan AST untuk menghitung cabang `If`, `For`, `While`).
* **Kriteria Keberhasilan:** Eksekusi kode secara otomatis memutus rantai validasi dan memunculkan error `COMPLEXITY_BUDGET_EXCEEDED` sebelum kompilator typecheck dijalankan.

#### Level: Medium
* **Tugas:** Buat skrip Python yang secara dinamis mengekstraksi AST Skeleton dari file target (menghilangkan body fungsi dan menggantinya dengan ekspresi `...` atau `pass`), lalu cetak representasi kode tersebut ke terminal sebagai "Context-Minified Prompt".
* **Kriteria Keberhasilan:** File Python berukuran 500 baris terkompresi menjadi representasi definisi signature dan type hinting di bawah 100 baris kode yang siap diinjeksi ke token LLM.

#### Level: Hard
* **Tugas:** Rancang sebuah Git Pre-commit Hook agentic yang menguji apakah patch pada staged area memiliki korelasi unit test. Jika pengembang menambahkan fungsi publik baru di `src/`, namun tidak ada assertions baru di `tests/`, pre-commit hook harus memanggil API LLM lokal untuk menghasilkan draft awal unit test scaffold secara otomatis ke worktree pengembang.
* **Kriteria Keberhasilan:** Gagal commit secara atomik, memunculkan stub test baru di direktori `tests/`, dan meminta insinyur mengisi assertions fungsional.

---

### 14. Challenge

**Skenario Kasus:** *The Zero-Day Legacy Refactor*
Sebuah service lawas perbankan ditulis menggunakan Node.js (CommonJS) dengan library yang sudah usang dan terindikasi celah keamanan Remote Code Execution (RCE). Tidak ada dokumentasi API tertulis, namun repositori memiliki test coverage parsial (~35%).

**Tantangan Arsitektur:**
1. Desainlah blueprint *automated agentic workflow* yang mampu:
   * Mengonversi seluruh repositori dari CommonJS ke ES Modules (TypeScript strict mode).
   * Menganalisis execution path melalui static AST graph untuk menghasilkan unit test kontraktual *sebelum* memodifikasi kode sumber.
   * Menjamin bahwa selama proses refactoring, *zero breaking changes* terjadi pada consumer API eksternal.
2. Spesifikasi mekanisme deterministik apa yang Anda bangun untuk membuktikan bahwa tidak ada fungsi *backdoor* atau *hallucinated logic* yang disusupkan oleh agen selama proses transformasi massal berlangsung tanpa mengharuskan insinyur membaca puluhan ribu baris diff manual.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. **Apa perbedaan mendasar antara *casual vibe-coding* dan *Enterprise Vibe-Coding (DASE)*?**
   * *Jawaban:* Casual vibe-coding mengeksekusi kode hasil LLM tanpa batasan deterministik langsung pada repositori; DASE menggunakan pendekatan berbasis kontrak spesifikasi (Spec-First), pemeriksaan AST, batasan isolasi worktree, serta umpan balik pengujian tertutup (*closed-loop automated verification*).
2. **Mengapa penulisan ulang seluruh file (*full-file overwrite*) sangat dilarang dalam arsitektur coding agent enterprise?**
   * *Jawaban:* Karena full-file overwrite menghabiskan token context window, meningkatkan risiko terhapusnya kode periferal yang krusial secara tidak sengaja, merusak git history/blame, dan memicu *context degradation* pada model.
3. **Apa peran *Tree-sitter* dalam perakitan konteks (*context assembly*) LLM?**
   * *Jawaban:* Tree-sitter digunakan untuk melakukan parsing sintaksis cepat guna membuat AST, mengekstraksi deklarasi tipe, signature metode, dan struktur simbolik tanpa mengikutsertakan implementasi internal modul yang tidak diperlukan.
4. **Apa yang dimaksud dengan *Self-Healing Reflection Loop*?**
   * *Jawaban:* Siklus di mana error output (sintaks, kompilasi, tipe, atau testing) dari proses lokal ditangkap dan disuntikkan kembali ke prompt LLM secara terstruktur agar model merevisi patch-nya sendiri tanpa intervensi manual manusia.
5. **Mengapa unit test file harus diatur menjadi Read-Only saat LLM bertugas memperbaiki fungsionalitas kode?**
   * *Jawaban:* Untuk mencegah fenomena *sycophancy*, di mana model mengubah nilai ekspektasi pada assertion test agar kodenya yang salah dianggap "lulus", alih-alih memperbaiki logika implementasinya.

#### Intermediate (5 Soal)
6. **Bagaimana Context Poisoning dapat menyebabkan infinite loop pada perbaikan kode agen?**
   * *Jawaban:* Ketika model menerima stack trace terminal mentah yang terlalu panjang atau berulang, attention weight terfokus pada pesan kesalahan lama daripada representasi kode baru. Model menginterpretasikan kebisingan (*noise*) tersebut sebagai referensi sintaksis, memicu perbaikan yang melahirkan error serupa secara siklis.
7. **Jelaskan peran Model Context Protocol (MCP) dalam mengurangi halusinasi API perusahaan internal.**
   * *Jawaban:* MCP memfasilitasi pengambilan skema API, definisi basis data, dan dokumentasi internal secara real-time melalui protokol client-server standar, sehingga LLM tidak menebak/menghalusinasikan parameter atau payload endpoint internal.
8. **Mengapa tipe data strict (*strict static typing*) adalah prasyarat mutlak untuk efektivitas enterprise vibe-coding?**
   * *Jawaban:* Static typing bertindak sebagai *deterministic evaluator* instan lapisan pertama. Agen mendapatkan sinyal diskrit binary (pass/fail) instan dari kompilator mengenai ketidakcocokan kontrak sebelum pengujian fungsional yang memakan resource dijalankan.
9. **Kapan teknik Unified Diff lebih disukai daripada AST Surgical Transformation dalam pengaplikasian patch agen?**
   * *Jawaban:* Unified Diff lebih disukai untuk perubahan berbasis teks general yang kompatibel langsung dengan git tooling bawaan, sedangkan AST Transformation lebih disukai saat memodifikasi token individual tanpa memedulikan formatting atau ketika git apply diff kerap gagal akibat pergeseran baris (*whitespace/line drifting*).
10. **Bagaimana mitigasi serangan Typosquatting dan Supply Chain Attack saat coding agent mengusulkan instalasi library eksternal baru?**
    * *Jawaban:* Dengan mengunci dependency resolution via AST pre-check terhadap internal package registry mirror (seperti Artifactory/Nexus privat), serta memblokir eksekusi perintah shell `npm install`/`pip install` secara otonom di luar dependensi yang masuk dalam *allowlist*.

#### Skenario Kasus Produksi (3 Soal)
11. **Skenario 1:** Agen pengembang Anda mengalami looping perbaikan sebanyak 5 kali karena error `Type mismatch: expected UUID, got str` pada modul PostgreSQL handler, meskipun prompt telah menginstruksikannya untuk mengonversi nilai tersebut. Langkah arsitektur apa yang salah pada harness DASE Anda?
    * *Analisis & Solusi:* Harness kemungkinan besar menyuntikkan seluruh pesan traceback tanpa menyertakan definisi tipe spesifik library PostgreSQL driver yang digunakan. Solusinya: Batasi loop, lalu lakukan *context injection* yang menyertakan stub tipe dari driver UUID target secara eksplisit ke dalam *system prompt* refleksi.
12. **Skenario 2:** Selama pengujian beban (*load testing*), sistem baru yang dibangun melalui automated vibe-coding mengalami kebocoran memori (*memory leak*) parah pada koneksi socket, meski 100% unit test fungsional lolos (*green*). Di mana letak kegagalan testing harness Anda?
    * *Analisis & Solusi:* Testing harness hanya memiliki functional assertion tests (TDD) namun tidak memiliki *Invariant & Resource Leak Profiling* pada level Sandbox. Perlu ditambahkan automated property testing atau static memory allocation verification (seperti linter tracing untuk unclosed resources atau valgrind/leak detection tool) di determinism ring sandbox.
13. **Skenario 3:** Tim Anda mengadopsi monorepo yang sangat besar. Agen coding membutuhkan waktu 3 menit hanya untuk menganalisis konteks sebelum menghasilkan token pertama (*Time To First Token/TTFT sangat lambat*). Optimasi apa yang harus diterapkan pada Context Assembly Engine?
    * *Analisis & Solusi:* Hentikan pemindaian file secara menyeluruh. Terapkan pemetaan dependensi upstream/downstream menggunakan graf dependensi terindeks (seperti Bazel/Nx graph atau ctags database), dan gunakan *sliding window context* yang hanya membaca berkas-berkas dalam radius 1 derajat dependensi dari titik entry point fitur yang dimodifikasi.

---

### 16. Summary

* **Paradigma Baru:** *Enterprise Vibe-Coding* bukanlah pemrograman spekulatif tanpa metodologi. Ini adalah evolusi rekayasa: **Deterministic Agentic Software Engineering (DASE)**, di mana interaksi bahasa alami diarahkan menjadi formal spec dan divalidasi oleh kompilator deterministik.
* **Komponen Vital:**
  1. *Context Assembly Plane* (Tree-sitter, MCP, Symbol Resolution).
  2. *Sandboxed Generation* (Unified Diff, Worktree Isolation).
  3. *Closed-Loop Feedback System* (AST Parsing, Type Integrity, Unit Regression).
* **Peran Insinyur Perangkat Lunak Modern:**
  Peran insinyur beralih dari sekadar juru ketik sintaksis (*syntax typist*) menjadi **Architectural Orchestrator & Invariant Validator**. Pengembang mendefinisikan batasan, menulis kontrak pengujian, dan mengawasi jalannya *state machine* verifikasi kode yang dieksekusi secara otonom oleh agen AI.