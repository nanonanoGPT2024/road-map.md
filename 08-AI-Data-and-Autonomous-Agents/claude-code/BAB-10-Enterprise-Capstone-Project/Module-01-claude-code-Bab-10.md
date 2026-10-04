# Bab 10: Enterprise Capstone Project Module 01 — Autonomous Security Remediation & Architecture Refactoring Engine

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang dan Mengimplementasikan Arsitektur Agen Otonom Tingkat Enterprise**: Membangun *agentic system* berbasis Claude (Claude 3.5 Sonnet / Claude Code Engine) yang mampu menavigasi, memahami dependensi lintas berkas (*cross-file dependency graph*), dan memodifikasi *codebase* skala jutaan baris kode secara deterministik.
- **Mengintegrasikan Model Context Protocol (MCP) Custom Server**: Membangun *custom* MCP server yang mengekspos utilitas analisis *Abstract Syntax Tree* (AST), *sandboxed terminal execution*, dan *git atomic workspace manipulation*.
- **Mengembangkan Deterministic Validation & Self-Healing Loop**: Menerapkan siklus verifikasi otomatis berbasis *test-driven feedback* (linting, static type checking, unit tests) dengan algoritma *backtracking* saat terjadi regresi fungsional atau kegagalan kompilasi.
- **Mengelola Mitigasi Risiko Eksekusi Kode Otonom**: Menerapkan *sandboxing* berbasis container (atau sekat OS-level), isolasi hak akses (*least privilege*), deteksi *hallucinated dependencies*, dan proteksi terhadap serangan *indirect prompt injection* yang disematkan dalam komentar kode atau commit message.

---

## 2. Concept Overview

Sistem agen pengubah kode enterprise (*autonomous refactoring agent*) bukan sekadar pemanggilan model bahasa (*LLM call*) dengan instruksi penyuntingan teks. Pendekatan berbasis pencarian teks mentah (*naive string replacement*) dipastikan gagal pada basis kode nyata karena ambiguitas penamaan, perubahan dependensi transisi, dan ketidakmampuan memvalidasi semantik kompilasi.

### Mental Model

Bayangkan agen sebagai seorang *Principal Staff Software Engineer* yang bekerja di *isolated branch*:
1. **Perception**: Membaca kode bukan sebagai teks murni, melainkan sebagai graf dependensi berarah (*directed dependency graph*) dan struktur sintaksis (*Abstract Syntax Tree*).
2. **Reasoning & Planning**: Menemukan kerentanan (misal: *SQL Injection*, *Insecure Deserialization*, atau *untyped dynamic parameters*), memetakan dampaknya ke *call-sites* hulu dan hilir, kemudian merumuskan rencana patching multi-fase (*Atomic Change Plan*).
3. **Execution**: Menulis ulang berkas menggunakan manipulasi AST terarah atau *unified diff patches* presisi tinggi melalui antarmuka *Model Context Protocol* (MCP).
4. **Verification**: Mengeksekusi linter, transpiler, dan *test harness* di dalam *sandbox*. Jika verifikasi gagal, pesan kesalahan dikembalikan ke model sebagai observasi loop berikutnya (*self-correction*).
5. **Finalization**: Melakukan *atomic git commit* yang mematuhi standar *Conventional Commits* dan memproduksi *remediation report* lengkap.

```
       +-----------------------------------------------------------+
       |                  Enterprise SentinelRefactor              |
       |                      (The Orchestrator)                   |
       +-----------------------------+-----------------------------+
                                     |
                [Model Context Protocol (MCP) Interface]
                                     |
       +-----------------------------+-----------------------------+
       |                             |                             |
+------v-------+              +------v------+              +-------v------+
| AST Engine   |              | Sandboxed   |              | Git Atomic   |
| (Tree-sitter/|              | Environment |              | Workspace    |
| Python AST)  |              | (Execution) |              | (Rollback)   |
+--------------+              +-------------+              +--------------+
```

---

## 3. Why It Matters

Di lingkungan enterprise kontemporer:
- **Technical Debt & Vulnerabilities at Scale**: Ribuan repositori mikroservis sering kali tertahan pada versi dependensi lawas atau memiliki kerentanan zero-day (misal: migrasi dari library logging rentan, atau standardisasi sanitasi input DB). Memperbaikinya secara manual memakan waktu ribuan *engineering hours*.
- **Human Error in Monotonous Refactoring**: Mengubah signature fungsi inti yang dipanggil oleh 400 modul berbeda sangat rentan *human error*. Agen yang digerakkan oleh Claude Code Engine mampu mengeksekusi operasi mekanis ini secara deterministik.
- **Strict Compliance & Zero Tolerance for Broken Builds**: Enterprise tidak dapat mentoleransi *code generator* yang merusak *build pipeline*. Agen harus menjamin bahwa setiap PR (*Pull Request*) yang diajukan telah lolos uji *static analysis*, *type checking* (misal: `mypy` / `tsc`), dan *regression suite*.

---

## 4. Arsitektur & Diagram Komponen

Arsitektur terdiri dari empat sub-sistem utama:
1. **Core Agent Orchestrator**: Mengelola *ReAct* loop, state transaksi, akumulasi token, serta terminasi kondisional.
2. **MCP Tooling Server**: Menyediakan toolset terisolasi yang dapat dipanggil Claude melalui protokol JSON-RPC standar MCP.
3. **AST Static Analyzer**: Melakukan verifikasi struktur sebelum dan sesudah modifikasi kode guna memastikan struktur modul tidak rusak secara semantik.
4. **Sandboxed Verification Subsystem**: Menjalankan *test suite* dan *type-checker* pada *isolated ephemeral container* atau subprocess dengan *timeout* ketat dan pembatasan resource (cgroups).

### Diagram Alur Agen (ASCII)

```
+-----------------------------------------------------------------------------------+
|                               USER INVOCATION                                     |
|         "Refactor repository to patch CVE-XXXX and enforce Strict Typing"         |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                        ORCHESTRATOR INITIALIZATION                                |
|  - Parse AST & Build Dependency Graph                                             |
|  - Create Ephemeral Git Workspace: git checkout -b security/patch-cve             |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
           +======================================================+
           |               RECURSIVE AGENTIC REPAIR LOOP          |
           |                                                      |
           |  +------------------------------------------------+  |
           |  | Claude 3.5 Sonnet / Code Engine                |  |
           |  | - Evaluates workspace state                    |  |
           |  | - Emits MCP Tool Calls (read/write/diff/exec)  |  |
           |  +-----------------------+------------------------+  |
           |                          |                           |
           |                          | (Tool Call: Patch Code)   |
           |                          v                           |
           |  +------------------------------------------------+  |
           |  | MCP Server: apply_ast_patch                    |  |
           |  | - Validates AST syntax pre-write               |  |
           |  | - Writes change to ephemeral disk              |  |
           |  +-----------------------+------------------------+  |
           |                          |                           |
           |                          | (Tool Call: Run Tests)    |
           |                          v                           |
           |  +------------------------------------------------+  |
           |  | Sandboxed Execution Runner                     |  |
           |  | - Execute: pytest / mypy / ruff                |  |
           |  +-----------------------+------------------------+  |
           |                          |                           |
           |              +-----------v------------+              |
           |              | Did all checks PASS?   |              |
           |              +-----------+------------+              |
           |                          |                           |
           |            NO            |            YES            |
           |     +--------------------+--------------------+      |
           |     |                                         |      |
           |     v                                         v      |
           | [Format error output]                  [Break Loop]  |
           | [Feed back to Claude Context]                        |
           | (Max Retries: 5)                                     |
           +======================================================+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                               FINAL COMMIT & AUDIT                                |
|  - Verify zero git regression via: git diff --check                               |
|  - Generate Cryptographic Attestation / SBOM Hash                                 |
|  - Commit: "fix(security): resolve vulnerability via verified AST patch"         |
+-----------------------------------------------------------------------------------+
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### A. Model Context Protocol (MCP) Interfacing
Alih-alih menyuntikkan seluruh isi *codebase* ke dalam *system prompt* (yang menghabiskan batas *context window* dan menyebabkan degradasi performa/penalaran), arsitektur ini menggunakan protokol MCP berbasis JSON-RPC:
- **`read_file_range`**: Membaca fungsi atau kelas spesifik berdasarkan baris mulai dan selesai hasil pemetaan AST.
- **`apply_patch`**: Menerapkan perubahan berbasis *unified diff* terstruktur.
- **`run_verification`**: Memicu pengujian sintaks, tipe data, dan fungsionalitas di lingkungan *sandbox*.

### B. AST Integrity Validation Layer
Salah satu kegagalan terbesar LLM dalam modifikasi kode adalah menghasilkan *syntax error* halus (seperti kurung tutup yang hilang, *indentation mismatch*, atau *shadowed variable imports*). Sistem mengimplementasikan *pre-write hook* menggunakan modul AST bawaan bahasa target. Jika string kode yang dihasilkan oleh Claude tidak dapat di-*parse* menjadi AST valid, operasi penulisan berkas dibatalkan secara atomik, dan pesan parser error langsung dilemparkan kembali ke model sebagai *Tool Error*.

### C. Context Pruning & Tool Result Truncation
Keluaran eksekusi tes sering kali sangat panjang (misal: *stack trace* ribuan baris). Jika dibiarkan mentah, hal ini mencemari *context window*. Engine mengimplementasikan algoritma reduksi:
1. Menyaring ANSI escape sequences.
2. Memotong baris tengah jika log melebihi ambang batas (misal: maksimal 100 baris: 30 baris awal, penanda truncate, 70 baris akhir yang memuat *root cause exception*).

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi sistematis **Enterprise SentinelRefactor Core Engine** menggunakan Python 3.12, SDK resmi `anthropic`, `pydantic` V2 untuk validasi data struktural, dan integrasi AST.

### Struktur Proyek
```text
sentinel_refactor/
├── __init__.py
├── agent.py               # Orchestration & Agentic Loop
├── ast_guard.py           # AST Static Validator
├── mcp_tools.py           # Tool definitions & Local Execution
└── schemas.py             # Pydantic schemas
```

#### `schemas.py`
```python
from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field

class ToolExecutionResult(BaseModel):
    success: bool
    stdout: str = ""
    stderr: str = ""
    error_code: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

class FilePatchRequest(BaseModel):
    file_path: str = Field(..., description="Target relative file path")
    content: str = Field(..., description="The complete updated file content")
    expected_md5: Optional[str] = Field(None, description="Pre-patch MD5 checksum for concurrency check")

class VerificationRequest(BaseModel):
    test_command: str = Field(default="pytest tests/", description="Test command to run")
    typecheck_command: str = Field(default="mypy .", description="Typecheck command to run")
```

#### `ast_guard.py`
```python
import ast
import logging
from typing import Tuple

logger = logging.getLogger("SentinelAST")

class ASTGuard:
    """Memvalidasi integritas sintaksis kode Python secara deterministik sebelum persistensi ke disk."""

    @staticmethod
    def validate_python_code(code_str: str) -> Tuple[bool, str]:
        """
        Melakukan parsing AST.
        Mengembalikan tuple: (is_valid: bool, error_message: str).
        """
        try:
            ast.parse(code_str)
            return True, ""
        except SyntaxError as se:
            err_msg = f"SyntaxError pada baris {se.lineno}, kolom {se.offset}: {se.msg}\nBaris: {se.text}"
            logger.warning(f"AST validation failed: {err_msg}")
            return False, err_msg
        except Exception as e:
            return False, f"Unexpected error during AST parse: {str(e)}"
```

#### `mcp_tools.py`
```python
import os
import subprocess
import hashlib
from pathlib import Path
from typing import Dict, Any, List
from ast_guard import ASTGuard
from schemas import ToolExecutionResult

class LocalCodeWorkspace:
    """Implementasi backend toolset MCP untuk manipulasi berkas dan eksekusi terisolasi."""

    def __init__(self, workspace_root: Path):
        self.root = workspace_root.resolve()
        if not self.root.exists():
            raise ValueError(f"Workspace directory {self.root} tidak ditemukan.")

    def _resolve_safe_path(self, relative_path: str) -> Path:
        target = (self.root / relative_path).resolve()
        if not target.is_relative_to(self.root):
            raise PermissionError(f"Directory Traversal Terdeteksi: Akses ke {relative_path} ditolak.")
        return target

    def read_file(self, file_path: str) -> ToolExecutionResult:
        try:
            target = self._resolve_safe_path(file_path)
            if not target.exists():
                return ToolExecutionResult(success=False, stderr=f"File not found: {file_path}", error_code=404)
            content = target.read_text(encoding="utf-8")
            return ToolExecutionResult(success=True, stdout=content)
        except Exception as e:
            return ToolExecutionResult(success=False, stderr=str(e), error_code=500)

    def write_file(self, file_path: str, content: str) -> ToolExecutionResult:
        try:
            target = self._resolve_safe_path(file_path)
            
            # Jika berkas Python, jalankan AST Guard terlebih dahulu
            if target.suffix == ".py":
                is_valid, err = ASTGuard.validate_python_code(content)
                if not is_valid:
                    return ToolExecutionResult(
                        success=False,
                        stderr=f"AST Integrity Rejection: Modifikasi menghasilkan syntax error:\n{err}",
                        error_code=422
                    )

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            file_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
            return ToolExecutionResult(
                success=True, 
                stdout=f"Successfully written {file_path}",
                metadata={"md5": file_hash}
            )
        except Exception as e:
            return ToolExecutionResult(success=False, stderr=str(e), error_code=500)

    def run_command(self, command: str, timeout_seconds: int = 45) -> ToolExecutionResult:
        """Menjalankan instruksi shell dalam direktori workspace dengan isolasi timeout."""
        try:
            # Proteksi dasar terhadap command chaining berbahaya
            forbidden = [";", "&&", "||", "|", "`", "$("]
            if any(char in command for char in forbidden):
                return ToolExecutionResult(
                    success=False,
                    stderr=f"Command execution error: Karakter shell majemuk dilarang demi keamanan sandboxing.",
                    error_code=403
                )

            args = command.strip().split()
            if not args:
                return ToolExecutionResult(success=False, stderr="Empty command", error_code=400)

            process = subprocess.run(
                args,
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False
            )
            return ToolExecutionResult(
                success=(process.returncode == 0),
                stdout=process.stdout[-3000:] if len(process.stdout) > 3000 else process.stdout,
                stderr=process.stderr[-3000:] if len(process.stderr) > 3000 else process.stderr,
                error_code=process.returncode
            )
        except subprocess.TimeoutExpired:
            return ToolExecutionResult(
                success=False,
                stderr=f"Execution Timed Out: Batas waktu {timeout_seconds} detik terlampaui.",
                error_code=124
            )
        except Exception as e:
            return ToolExecutionResult(success=False, stderr=str(e), error_code=500)

# Definisi Skema Tool sesuai Claude Function/Tool Calling Spec
TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "name": "read_file",
        "description": "Membaca seluruh isi berkas dari workspace berdasarkan path relatif.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path relatif berkas dari root repositori"}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "write_file",
        "description": "Menulis atau mengganti seluruh isi berkas di workspace. Integritas sintaksis divalidasi via AST.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path relatif berkas"},
                "content": {"type": "string", "description": "Konten baru berkas secara lengkap"}
            },
            "required": ["file_path", "content"]
        }
    },
    {
        "name": "run_test_suite",
        "description": "Mengeksekusi test runner (misal pytest atau unittests) untuk memvalidasi perubahan.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Perintah pengujian yang akan dieksekusi, misal: 'pytest'"}
            },
            "required": ["command"]
        }
    }
]
```

#### `agent.py`
```python
import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from anthropic import Anthropic
from mcp_tools import LocalCodeWorkspace, TOOLS_SCHEMA

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Orchestrator")

class EnterpriseRefactorAgent:
    def __init__(self, workspace_path: str, api_key: str):
        self.workspace = LocalCodeWorkspace(Path(workspace_path))
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-3-5-sonnet-20241022"
        self.max_iterations = 6

    def _execute_tool(self, name: str, inputs: Dict[str, Any]) -> str:
        logger.info(f"Tool invocation: {name} with args: {list(inputs.keys())}")
        if name == "read_file":
            res = self.workspace.read_file(inputs["file_path"])
        elif name == "write_file":
            res = self.workspace.write_file(inputs["file_path"], inputs["content"])
        elif name == "run_test_suite":
            res = self.workspace.run_command(inputs["command"])
        else:
            return json.dumps({"error": f"Tool '{name}' tidak dikenali."})

        return json.dumps({
            "success": res.success,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "error_code": res.error_code
        })

    def run(self, task_instruction: str) -> bool:
        """
        Menjalankan Agentic Loop berbasis Tool-Use dengan penanganan multi-turn
        hingga tugas selesai atau mencapai batas iterasi maksimum.
        """
        system_prompt = (
            "Anda adalah Senior Principal Software Engineer & Autonomous Code Agent.\n"
            "Tugas Anda: Memperbaiki kerentanan atau melakukan refaktorisasi pada workspace tanpa merusak fungsionalitas yang ada.\n"
            "Pedoman Mutlak:\n"
            "1. Selalu periksa kode sebelum dan sesudah perubahan.\n"
            "2. Setiap patch HARUS divalidasi dengan mengeksekusi test harness menggunakan tool 'run_test_suite'.\n"
            "3. Jika pengujian gagal, analisa stacktrace dan lakukan *self-correction* segera.\n"
            "4. Jika perbaikan telah berhasil diverifikasi oleh unit tests, berikan pesan akhir Anda tanpa memanggil tool lagi."
        )

        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": task_instruction}
        ]

        for step in range(1, self.max_iterations + 1):
            logger.info(f"--- Siklus Iterasi Agen #{step} ---")

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
                tools=TOOLS_SCHEMA,
                temperature=0.0
            )

            # Parsing respons Claude
            tool_calls = [block for block in response.content if block.type == "tool_use"]
            text_blocks = [block.text for block in response.content if block.type == "text"]

            if text_blocks:
                logger.info(f"Claude Output:\n{text_blocks[0]}")

            # Simpan respons asisten ke riwayat percakapan
            messages.append({"role": "assistant", "content": response.content})

            # Jika tidak ada tool yang dipanggil, agen memutuskan tugas selesai
            if not tool_calls:
                logger.info("Agen menyelesaikan tugas secara otonom.")
                return True

            # Tangani setiap pemanggilan tool
            tool_results = []
            for tool_call in tool_calls:
                result_str = self._execute_tool(tool_call.name, tool_call.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_call.id,
                    "content": result_str
                })

            # Masukkan hasil tool execution sebagai respons user berikutnya
            messages.append({"role": "user", "content": tool_results})

        logger.error("Batas iterasi maksimum tercapai tanpa konvergensi sukses.")
        return False

if __name__ == "__main__":
    import sys
    # Demonstrasi inisialisasi aman
    api_key_env = os.getenv("ANTHROPIC_API_KEY")
    if not api_key_env:
        print("Set ANTHROPIC_API_KEY environment variable.", file=sys.stderr)
        sys.exit(1)

    # Path simulasi workspace
    workspace_dir = Path("/tmp/sample_repo")
    workspace_dir.mkdir(parents=True, exist_ok=True)
    
    # Inisialisasi berkas rentan untuk pengujian
    vulnerable_code = '''
def execute_query(db_conn, user_input):
    # RENTAN TERHADAP SQL INJECTION
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = '" + user_input + "'")
    return cursor.fetchall()
'''
    (workspace_dir / "db_ops.py").write_text(vulnerable_code)
    
    test_code = '''
from unittest.mock import MagicMock
from db_ops import execute_query

def test_execute_query():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    
    execute_query(mock_conn, "alice")
    # Verifikasi pemanggilan berparameter
    mock_cursor.execute.assert_called_once_with(
        "SELECT * FROM users WHERE username = %s", ("alice",)
    )
'''
    (workspace_dir / "test_db.py").write_text(test_code)

    agent = EnterpriseRefactorAgent(str(workspace_dir), api_key_env)
    success = agent.run(
        "Periksa file 'db_ops.py' terhadap kerentanan SQL Injection. "
        "Ubah agar menggunakan parameterized queries. "
        "Validasi perbaikan Anda dengan menjalankan tool 'run_test_suite' dengan perintah: 'pytest test_db.py'."
    )

    print(f"Status Remediasi: {'SUKSES' if success else 'GAGAL'}")
```

---

## 7. Edge Cases & Failure Modes

Pada implementasi level enterprise, kegagalan agen harus dipagari dengan proteksi berlapis:

| Failure Mode | Mekanisme Deteksi | Recovery Action / Fallback |
| :--- | :--- | :--- |
| **Hallucinated Package Import** | AST mendeteksi modul asing yang tidak ada di `pyproject.toml` / `requirements.txt`. | Batalkan proses penulisan. Berikan error: `E01: Dependency X is not declared in project lockfile.` |
| **Context Window Exhaustion** | Ukuran array pesan mendekati 80% dari batas konteks model. | Lakukan pemangkasan riwayat (*sliding-window compaction*); buang `stdout` lama hasil tes, pertahankan hanya status sukses/gagal terakhir dan ringkasan diff berkas. |
| **Endless Self-Correction Loop** | Agen mencoba memperbaiki error tes yang sama secara berulang (> 3 kali pada baris identik). | *Circuit breaker* aktif: hentikan iterasi, pulihkan workspace ke commit awal via `git checkout -- .`, dan tandai tugas membutuhkan tinjauan manual (*Human-in-the-Loop*). |
| **Path Traversal Escape** | Masukan tool menyertakan `../../etc/passwd` atau symlink menuju luar root repo. | `_resolve_safe_path` memicu `PermissionError` secara lokal tanpa menyentuh disk. |
| **Destructive Command Injection** | Masukan prompt atau tool menginstruksikan `rm -rf /` atau piping eksternal (`curl \| sh`). | Filter sintaksis command regex sebelum `subprocess.run`; blokir semua *shell wildcards* dan operator eksekusi majemuk. |

---

## 8. Trade-offs & Alternatif Solusi

### 1. Unified Diff vs. Full-File Replacement
- **Unified Diff (Patching)**:
  - *Kelebihan*: Hemat konsumsi token secara drastis, cepat.
  - *Kelemahan*: LLM kerap keliru menghitung nomor baris offset konteks, menyebabkan kegagalan patch (`patch rejected: fuzz factor too high`).
  - *Keputusan Arsitektur*: Untuk berkas kecil hingga menengah (< 500 baris), *Full-File Rewrite* yang dipagari oleh **AST Guard** jauh lebih stabil dan deterministik secara operasional di production. Untuk berkas masif (> 2000 baris), gunakan *Method-level extraction & rewrite*.

### 2. Subprocess Isolation vs. Ephemeral Containers (Docker/Firecracker)
- **Subprocess Isolation**:
  - *Kelebihan*: Latensi rendah (< 5ms startup).
  - *Kelemahan*: Lemah dari segi keamanan ekstrim jika kode yang diuji berisi malicious execution hooks.
  - *Keputusan Arsitektur*: Gunakan Subprocess *hanya* jika repo berasal dari lingkungan internal yang tepercaya; wajib gunakan ephemeral container (seperti microVM Firecracker atau Docker stateless) untuk kode yang bersumber dari public pull request.

---

## 9. Best Practices & Standard Industri

1. **Idempotent Tool Execution**: Pastikan setiap tool call MCP bersifat idempoten. Jika perintah eksekusi tes diulang dengan input sama tanpa perubahan disk, hasil harus identik.
2. **Git Atomic Commits**: Jangan biarkan agen melakukan manipulasi langsung ke branch produksi. Seluruh modifikasi agen harus berada pada branch sementara bertaraf *throwaway*:
   ```bash
   git checkout -b agent/fix-${CVE_ID}-${TIMESTAMP}
   ```
3. **Structured System Prompts dengan Few-Shot AST Corrections**: Berikan contoh konkret bagaimana kesalahan sintaks AST dipulihkan secara elegan pada context awal agen.
4. **SemVer & Contract Protection**: Pastikan modifikasi kode tidak menghapus anotasi `@deprecated` atau mengubah tipe return dari *public API surface* yang dapat merusak konsumen hilir (*downstream consumers*).

---

## 10. Hands-on Lab Exercise

### Skenario Lab
Anda ditugaskan membuat sebuah skrip otonom berbasis `EnterpriseRefactorAgent` yang mampu mendeteksi penggunaan fungsi hashing `hashlib.md5` yang tidak aman pada berkas autentikasi enterprise, lalu memperbaikinya menjadi algoritma hashing modern yang dilengkapi *salt* (seperti `hashlib.sha256` dengan salt terpasang), serta memastikan seluruh tes tetap berjalan hijau (*pass*).

### Langkah-langkah Praktik

#### Langkah 1: Siapkan Direktori Workspace
```bash
mkdir -p /tmp/enterprise_lab/tests
cd /tmp/enterprise_lab
```

#### Langkah 2: Buat Modul Autentikasi yang Rentan (`auth.py`)
```python
# /tmp/enterprise_lab/auth.py
import hashlib

def hash_user_password(password: str) -> str:
    """Fungsi hashing rentan (MD5) tanpa salt."""
    return hashlib.md5(password.encode('utf-8')).hexdigest()

def verify_password(raw_password: str, stored_hash: str) -> bool:
    return hash_user_password(raw_password) == stored_hash
```

#### Langkah 3: Buat Unit Test Suite (`tests/test_auth.py`)
```python
# /tmp/enterprise_lab/tests/test_auth.py
import pytest
from auth import hash_user_password, verify_password

def test_hashing_security():
    hashed = hash_user_password("SuperSecret123")
    # MD5 menghasilkan 32 karakter hex. SHA256 menghasilkan 64 karakter hex.
    assert len(hashed) == 64, "Hashing harus menghasilkan output 64-karakter SHA-256!"

def test_password_verification():
    raw = "ValidPassword_456"
    hashed = hash_user_password(raw)
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword", hashed) is False
```

#### Langkah 4: Eksekusi Agen
Jalankan file orkestrator Python yang telah Anda buat di bagian 6:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python3 -c '
from agent import EnterpriseRefactorAgent
agent = EnterpriseRefactorAgent("/tmp/enterprise_lab", "'$ANTHROPIC_API_KEY'")
agent.run("Periksa auth.py. Ganti algoritma MD5 dengan SHA256 agar mematuhi standar FIPS. Verifikasi dengan menjalankan pytest tests/test_auth.py.")
'
```

#### Langkah 5: Verifikasi Hasil Remediasi
Periksa diff hasil pembaruan yang dibuat oleh Claude:
```bash
git diff /tmp/enterprise_lab/auth.py
```
*Expected Output: Perubahan dari `hashlib.md5` ke `hashlib.sha256`, dan unit test `pytest tests/test_auth.py` menunjukkan status PASS.*