# Bab 02: Tooling Landscape & Agentic Workspaces
## Modul 01: Core Architecture of Agentic Workspaces & Tool Harnesses

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Mengimplementasikan (C4 & C6)** arsitektur *Agentic Workspace Harness* deterministik berbasis event-driven untuk menjembatani Large Language Models (LLM) dengan *operating system* lokal/container.
- **Mengintegrasikan (C3)** protokol standar industri seperti *Model Context Protocol* (MCP) berbasis JSON-RPC 2.0 untuk melakukan decoupling antara model reasoning dan eksekusi tool.
- **Membangun (C6)** mekanisme isolasi eksekusi sandboxed (filesystem & shell) dengan kapabilitas *fail-safe verification*, mitigasi destructive side-effects, dan *state rollback*.
- **Mengevaluasi dan Mengatasi (C5)** kegagalan umum autonomous agent seperti *infinite tool invocation loops*, *context pollution*, dan *context window exhaustion*.

---

### 2. Concept Overview
Paradigma rekayasa perangkat lunak telah bergeser dari *passive auto-completion* (seperti tab-completion berbasis transformer) menuju **Agentic Workspaces**—lingkungan di mana LLM bertindak sebagai *cognitive runtime* yang mengarahkan siklus hidup *software engineering* (analisis, penulisan kode, pengetesan, debugging) secara semi-otonom melalui teknik yang dipopulerkan sebagai *vibe-coding*. 

Dalam arsitektur *vibe-coding* profesional, developer tidak mengetik baris demi baris sintaks, melainkan mengarahkan *intent* arsitektural dan membiarkan *Autonomous Agent Harness* memanipulasi workspace secara iteratif.

```
+-----------------------------------------------------------------------+
|                             MENTAL MODEL                              |
|                                                                       |
|   Passive Assistant (Copilot):                                        |
|   Developer ---> [ IDE Editor ] <---> [ Language Server / Autocomplete ]
|                                                                       |
|   Agentic Workspace (Vibe-Coding Platform):                           |
|   Developer ---> (Intent / Goal)                                      |
|                        |                                              |
|                        v                                              |
|              [ Agentic Orchestrator ]                                 |
|               ^                    |                                  |
|  Context /    | Observation        | Action / Tool Invocation         |
|  Diagnostics  |                    v                                  |
|         [ MCP Host / Harness Isolation Boundary ]                     |
|           /            |            \                                 |
|          v             v             v                                |
|    [ Filesystem ]  [ Terminal ]  [ Language Server ]                  |
|    (Atomic Diff)   (Sandbox)     (AST / Diagnostics)                  |
+-----------------------------------------------------------------------+
```

Konsep inti dari *Agentic Workspace Harness* mencakup:
1. **The Model Context Protocol (MCP)**: Standar terbuka yang memformalkan pertukaran konteks antara LLM (client) dan data sources / execution tools (servers).
2. **Context Synthesis & Differential State**: Kemampuan workspace menyajikan state direktori dan file dalam bentuk representasi ringkas (AST, ctags, git diff) guna menghemat *token window*.
3. **Deterministic Sandbox Harness**: Lapisan abstraksi eksekusi yang mencegah operasi berbahaya (e.g., `rm -rf /`, unbounded resource fork bomb) serta menjamin idempotensi dari setiap *tool invocation*.

---

### 3. Why It Matters
Tanpa arsitektur harness yang kokoh, "vibe-coding" dengan cepat bertransformasi menjadi *technical debt nightmare* dan instabilitas produksi:
- **Destructive Execution**: Agent LLM yang diberi akses shell mentah tanpa sandbox dapat menghapus partisi, menimpa branch git lokal tanpa commit, atau memicu kebocoran kredensial environment variable.
- **Silent Degradation & Hallucination Drift**: Agent sering kali mengasumsikan keberhasilan sintaks tanpa melakukan pengetesan unit test atau static analysis (LSP). Hal ini menyebabkan kompilasi gagal yang baru disadari setelah berjam-jam pengembangan.
- **Context Poisoning**: Output stdout/stderr yang tidak difilter (misalnya dump file biner atau stack trace 10.000 baris) akan memenuhi seluruh konteks LLM, memicu kegagalan reasoning (*lost-in-the-middle phenomenon*), serta meningkatkan biaya inferensi secara eksponensial.

Standar enterprise membutuhkan *reproducible, audited, and isolated agentic execution boundaries*.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut memetakan aliran instruksi, isolasi sandbox, dan manajemen state dalam runtime Agentic Workspace berbasis Model Context Protocol (MCP):

```
+------------------------------------------------------------------------------------+
|                                AGENTIC WORKSPACE                                   |
|                                                                                    |
|  +--------------------+        JSON-RPC 2.0 (stdio / SSE)    +------------------+  |
|  |                    | <==================================> |                  |  |
|  |  LLM Orchestrator  |                                      |  MCP Host Router |  |
|  |  (Reasoning Engine)| <---------- Context Invalidation --- |                  |  |
|  +--------------------+                                      +------------------+  |
|           |                                                            |           |
|           | Function Call Request                                      | Dispatches|
|           v                                                            v           |
|  +-------------------------------------------------------------------------------+ |
|  |                         EXECUTION HARNESS BOUNDARY                            | |
|  |                                                                               | |
|  |  +------------------------+  +----------------------+  +--------------------+ | |
|  |  |   Filesystem Adapter   |  |   Command Sandbox    |  |   LSP Diagnostic   | | |
|  |  |                        |  |                      |  |   Analyzer         | | |
|  |  | - Atomic Write Buffer  |  | - PTY Session Pool   |  | - AST Node Parser  | | |
|  |  | - Reversible Git Patch |  | - Process Watchdog   |  | - Error Diagnostic | | |
|  |  | - Path Jail (/sandbox) |  | - Safe Subprocess    |  | - Definition Index | | |
|  |  +------------------------+  +----------------------+  +--------------------+ | |
|  |               |                         |                         |           | |
|  +---------------+-------------------------+-------------------------+-----------+ |
|                  |                         |                         |             |
|                  v                         v                         v             |
|       +------------------------------------------------------------------+         |
|       |                   ISOLATED OPERATING SYSTEM                      |         |
|       |     (Virtual Filesystem / Namespace / Restricted Subprocess)     |         |
|       +------------------------------------------------------------------+         |
+------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Model Context Protocol (MCP) Wire Mechanics
MCP mengabstraksikan fungsi eksternal ke dalam tiga entitas:
1. **Prompts**: Template terstruktur untuk bootstrap workflow.
2. **Resources**: Data pasif yang hanya dapat dibaca (*read-only state*, e.g., file content, database schema).
3. **Tools**: Fungsi komputasi yang memiliki *side-effects* yang dapat dipanggil oleh LLM (e.g., compile code, execute shell, create directory).

Komunikasi mengandalkan JSON-RPC 2.0 via `stdio` (pipe lokal) atau Server-Sent Events (SSE). 

Format JSON-RPC 2.0 Tool Invocation:
```json
// Request dari LLM Orchestrator ke Tool Provider:
{
  "jsonrpc": "2.0",
  "id": "req-9842",
  "method": "tools/call",
  "params": {
    "name": "workspace_write_file",
    "arguments": {
      "path": "src/services/auth.py",
      "content": "def authenticate():\n    return True\n"
    }
  }
}

// Respon dari Harness Boundary:
{
  "jsonrpc": "2.0",
  "id": "req-9842",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "File src/services/auth.py written successfully. AST verification passed. 0 syntax errors."
      }
    ],
    "isError": false
  }
}
```

#### B. Filesystem Jail & Atomic Change Verification
Agent tidak boleh menulis langsung ke disk host tanpa verifikasi. Harness harus menggunakan mekanisme **Two-Phase Write**:
1. Tulis perubahan ke *ephemeral memory buffer* atau staging directory.
2. Lakukan *AST validation check* (misalnya lewat modul python `ast` atau parser language-specific). Jika parser melempar syntax error, operasi dibatalkan dan error stack dikembalikan ke LLM untuk re-prompting (*self-correction*).
3. Buat differential git commit hash untuk memfasilitasi *one-step rollback*.

#### C. Command Sandbox Execution & Output Truncation
Eksekusi terminal rawan loop tak terbatas (misalnya server blocking `npm start` atau `uvicorn` tanpa detach). Command sandbox wajib memberlakukan:
- **PTY Emulation & Non-Blocking Streams**: Menangkap interleaved stdout/stderr secara real-time.
- **Strict Wall-Clock Timeout**: Terminasi paksa (`SIGKILL`) bila proses melewati threshold batas waktu (default 30 detik untuk step deterministik).
- **Dual-Ring Context Buffer**: Memotong output besar dengan algoritma *head-and-tail sliding window*: menyimpan $N$ baris pertama dan $M$ baris terakhir seraya mengeliminasi bagian tengah untuk menghemat konteks tanpa kehilangan error signature.

---

### 6. Production-Ready Code Implementation

Berikut implementasi lengkap dari **Agentic Workspace Harness Engine** dalam Python 3.12 modern. Modul ini menerapkan *sandboxing*, *atomic file patching dengan verifikasi AST*, dan *safe command execution* yang sepenuhnya *type-hinted* serta mengikuti *clean architecture principles*.

```python
"""
agentic_workspace_harness.py
Arsitektur Enterprise Agentic Workspace Harness berbasis Asyncio.
Mendukung Tool Decoupling, Path Virtualization, Dynamic Sandboxing, dan Atomic AST Verification.
"""

from __future__ import annotations

import ast
import asyncio
import os
import pathlib
import shlex
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


# =====================================================================
# Domain Exceptions
# =====================================================================
class WorkspaceSecurityViolation(Exception):
    """Dilempar saat tool mencoba melanggar boundary direktori sandbox."""
    pass


class CompilationSyntaxError(Exception):
    """Dilempar saat kode yang dihasilkan agen gagal melewati validasi AST."""
    pass


class CommandExecutionTimeout(Exception):
    """Dilempar jika eksekusi shell sandbox melewati batas timeout."""
    pass


# =====================================================================
# Value Objects & Result Envelopes
# =====================================================================
@dataclass(frozen=True)
class ExecutionResult:
    stdout: str
    stderr: str
    exit_code: int
    truncated: bool

    def is_successful(self) -> bool:
        return self.exit_code == 0


@dataclass(frozen=True)
class ToolResponse:
    success: bool
    output: str
    error: Optional[str] = None


# =====================================================================
# Core Workspace Harness Implementation
# =====================================================================
class AgenticWorkspaceHarness:
    """
    Mengontrol batas eksekusi (sandbox) untuk file system dan CLI environment.
    Menghilangkan celah destructive operation dan context window exhaustion.
    """

    def __init__(
        self,
        workspace_root: pathlib.Path,
        max_output_bytes: int = 16_384,  # 16 KB context limit
        execution_timeout_sec: float = 30.0,
    ) -> None:
        self.workspace_root = workspace_root.resolve()
        self.max_output_bytes = max_output_bytes
        self.execution_timeout_sec = execution_timeout_sec
        self._ensure_sandbox_exists()

    def _ensure_sandbox_exists(self) -> None:
        if not self.workspace_root.exists():
            self.workspace_root.mkdir(parents=True, exist_ok=True)

    def _resolve_and_jail_path(self, relative_path: str) -> pathlib.Path:
        """
        Menjamin path traversal attack (misal '../../etc/passwd')
        dinetralkan dan dibatasi strictly di dalam workspace_root.
        """
        target_path = (self.workspace_root / relative_path).resolve()
        if not target_path.is_relative_to(self.workspace_root):
            raise WorkspaceSecurityViolation(
                f"Akses ditolak: Operasi path '{relative_path}' melompat ke luar root sandboxing."
            )
        return target_path

    def _truncate_output(self, raw_bytes: bytes) -> Tuple[str, bool]:
        """
        Mengimplementasikan Head-and-Tail Truncation untuk melindungi context window LLM.
        """
        if len(raw_bytes) <= self.max_output_bytes:
            return raw_bytes.decode("utf-8", errors="replace"), False

        half_limit = self.max_output_bytes // 2
        head = raw_bytes[:half_limit].decode("utf-8", errors="replace")
        tail = raw_bytes[-half_limit:].decode("utf-8", errors="replace")
        
        truncated_text = (
            f"{head}\n\n"
            f"[... OUTPUT DIHAPUS: DITRUNCATE KARENA MELEBIHI {self.max_output_bytes} BYTES ...]\n\n"
            f"{tail}"
        )
        return truncated_text, True

    # -----------------------------------------------------------------
    # Tool: Atomic File System Mutations with Verification
    # -----------------------------------------------------------------
    async def safe_write_file(self, relative_path: str, content: str) -> ToolResponse:
        """
        Menulis file secara atomik di dalam sandbox. Jika ekstensi adalah .py,
        lakukan validasi AST parser sebelum menyimpan secara permanen.
        """
        try:
            target_path = self._resolve_and_jail_path(relative_path)
            
            # Verifikasi Sintaksis Deterministik untuk file Python
            if target_path.suffix == ".py":
                try:
                    ast.parse(content, filename=relative_path)
                except SyntaxError as e:
                    raise CompilationSyntaxError(
                        f"AST Validation Failed pada line {e.lineno}, offset {e.offset}: {e.msg}"
                    ) from e

            # Siapkan parent directory jika belum ada
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Atomic Write via Temporary Staging File
            temp_target = target_path.with_suffix(f"{target_path.suffix}.tmp.{os.urandom(4).hex()}")
            
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, temp_target.write_text, content, "utf-8")
            
            # Atomic swap (POSIX rename is atomic)
            await loop.run_in_executor(None, temp_target.replace, target_path)

            return ToolResponse(
                success=True,
                output=f"File '{relative_path}' berhasil ditulis secara atomik. Verifikasi AST sukses."
            )

        except (WorkspaceSecurityViolation, CompilationSyntaxError) as operational_err:
            return ToolResponse(
                success=False,
                output="",
                error=f"[Operational Error]: {str(operational_err)}"
            )
        except Exception as system_err:
            return ToolResponse(
                success=False,
                output="",
                error=f"[System Error]: Gagal mengeksekusi operasi penulisan: {str(system_err)}"
            )

    async def safe_read_file(self, relative_path: str) -> ToolResponse:
        """Membaca isi file dari dalam boundary sandbox."""
        try:
            target_path = self._resolve_and_jail_path(relative_path)
            if not target_path.exists():
                return ToolResponse(
                    success=False,
                    output="",
                    error=f"File tidak ditemukan: '{relative_path}'"
                )

            loop = asyncio.get_running_loop()
            content = await loop.run_in_executor(None, target_path.read_text, "utf-8")
            return ToolResponse(success=True, output=content)

        except WorkspaceSecurityViolation as sec_err:
            return ToolResponse(success=False, output="", error=str(sec_err))
        except Exception as ex:
            return ToolResponse(success=False, output="", error=f"I/O Read Error: {str(ex)}")

    # -----------------------------------------------------------------
    # Tool: Sandboxed Shell Execution
    # -----------------------------------------------------------------
    async def safe_execute_command(self, raw_command: str) -> ToolResponse:
        """
        Mengeksekusi command line di bawah working directory sandbox
        dengan batas timeout dan pembatasan buffer output.
        """
        # Parsing command token untuk mencegah command injection tidak terduga
        try:
            cmd_args = shlex.split(raw_command)
            if not cmd_args:
                return ToolResponse(success=False, output="", error="Command kosong.")

            # Hard-blocker: Melarang perintah eksplisit yang merusak integritas lingkungan
            blocked_binaries = {"rm", "dd", "mkfs", "shutdown", "reboot"}
            if cmd_args[0] in blocked_binaries and "-rf" in cmd_args:
                return ToolResponse(
                    success=False,
                    output="",
                    error=f"Panggilan binary '{cmd_args[0]}' dengan flags destruktif dilarang oleh policy harness."
                )

            process = await asyncio.create_subprocess_exec(
                cmd_args[0],
                *cmd_args[1:],
                cwd=str(self.workspace_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                # Hilangkan akses langsung ke environment sensitif jika di production
                env={**os.environ, "AGENT_WORKSPACE": str(self.workspace_root)},
            )

            try:
                stdout_data, stderr_data = await asyncio.wait_for(
                    process.communicate(), timeout=self.execution_timeout_sec
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()
                raise CommandExecutionTimeout(
                    f"Eksekusi melebihi batas {self.execution_timeout_sec} detik dan dihentikan paksa (SIGKILL)."
                )

            stdout_str, stdout_trunc = self._truncate_output(stdout_data)
            stderr_str, stderr_trunc = self._truncate_output(stderr_data)

            execution = ExecutionResult(
                stdout=stdout_str,
                stderr=stderr_str,
                exit_code=process.returncode if process.returncode is not None else -1,
                truncated=stdout_trunc or stderr_trunc,
            )

            summary = (
                f"Exit Code: {execution.exit_code}\n"
                f"Stdout:\n{execution.stdout}\n"
                f"Stderr:\n{execution.stderr}"
            )
            
            return ToolResponse(
                success=execution.is_successful(),
                output=summary,
                error=None if execution.is_successful() else f"Proses keluar dengan status non-zero: {execution.exit_code}"
            )

        except CommandExecutionTimeout as timeout_err:
            return ToolResponse(success=False, output="", error=str(timeout_err))
        except FileNotFoundError:
            return ToolResponse(
                success=False, output="", error=f"Executable tidak ditemukan di sistem: {cmd_args[0]}"
            )
        except Exception as ex:
            return ToolResponse(
                success=False, output="", error=f"Kesalahan fatal pada runtime eksekutor: {str(ex)}"
            )


# =====================================================================
# MCP-like Dispatch Router
# =====================================================================
class AgenticToolDispatcher:
    """
    Router yang memetakan RPC Action dari agent menuju internal Harness.
    """

    def __init__(self, harness: AgenticWorkspaceHarness) -> None:
        self.harness = harness
        self.registered_tools = {
            "write_file": self._handle_write,
            "read_file": self._handle_read,
            "execute_command": self._handle_exec,
        }

    async def dispatch(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        handler = self.registered_tools.get(tool_name)
        if not handler:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method '{tool_name}' tidak ditemukan."},
            }

        result: ToolResponse = await handler(arguments)
        return {
            "jsonrpc": "2.0",
            "result": {
                "success": result.success,
                "payload": result.output,
                "error": result.error,
            },
        }

    async def _handle_write(self, args: Dict[str, Any]) -> ToolResponse:
        return await self.harness.safe_write_file(args["path"], args["content"])

    async def _handle_read(self, args: Dict[str, Any]) -> ToolResponse:
        return await self.harness.safe_read_file(args["path"])

    async def _handle_exec(self, args: Dict[str, Any]) -> ToolResponse:
        return await self.harness.safe_execute_command(args["command"])
```

---

### 7. Edge Cases & Failure Modes

Setiap *Agentic Workspace* diuji ketahanannya pada skenario kegagalan operasional (*corner cases*):

1. **Jailbreak Path Traversal via Symlinks**:
   - *Mode Kegagalan*: Agent membuat symlink di dalam sandbox yang mengarah ke `/root/.ssh/id_rsa`, kemudian memanggil `read_file` pada symlink tersebut.
   - *Mitigasi*: Resolusi path harus memanggil `.resolve()` pada filesystem host dan memvalidasi `target_path.is_relative_to(sandbox_root)`. Jika resolved path berada di luar, batalkan eksekusi segera.

2. **Recursive Tool Hallucination Loop**:
   - *Mode Kegagalan*: Agent menghasilkan sintaks error yang sama berulang kali. Agent membaca error, mencoba memperbaiki, namun menghasilkan variasi error sintaks yang sama terus-menerus hingga token habis.
   - *Mitigasi*: Pasang **Finite State Circuit Breaker**. Jika perbaikan file yang sama gagal lebih dari 3 kali berturut-turut, freeze eksekusi dan minta intervensi manual dari *Human-in-the-loop* (HITL).

3. **Silent Background Daemon Leak**:
   - *Mode Kegagalan*: Agent mengeksekusi script yang men-spawn background process (e.g., `python -m http.server &`). Ketika harness menyelesaikan timeout execution, background process tertinggal (*zombie process*) dan mengunci port.
   - *Mitigasi*: Spawn subprocess dalam Process Group terisolasi (`os.setsid`) dan eksekusi `os.killpg(os.getpgid(p.pid), signal.SIGTERM)` saat proses selesai atau dibatalkan.

4. **Output Flooding (Stdout DoS)**:
   - *Mode Kegagalan*: Perintah seperti `cat /dev/urandom` atau infinite print loop membanjiri buffer I/O hingga RAM server habis (*OOM Crash*).
   - *Mitigasi*: Terapkan pembatasan ukuran stream langsung di level chunk buffer (Stream reader slicing) sebelum dikonversi menjadi string Python.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektural | Pilihan A: Local Host Process (Subprocess/PTY) | Pilihan B: Containerized Sandbox (Docker/Podman) | Pilihan C: WebAssembly Sandbox (Wasmtime/Extism) |
| :--- | :--- | :--- | :--- |
| **Tingkat Isolasi** | Rendah (Hanya Path Traversal Guard & OS permissions) | Tinggi (Namespace kernel & cgroups terpisah) | Ekstrem (Memory boundary terisolasi total) |
| **Startup Latency** | Instan (< 5ms) | Lambat hingga Medium (100ms - 2s) | Sangat Cepat (< 1ms) |
| **Fleksibilitas Tool** | Penuh (Bisa akses compiler, shell native) | Fleksibel (Tergantung base image Docker) | Sangat Terbatas (Hanya binary yang dikompilasi ke WASM) |
| **Overhead Sumber Daya**| Sangat Rendah | Sedang (Membutuhkan runtime Docker/Daemon) | Sangat Rendah (Lightweight) |
| **Target Penggunaan** | Desktop IDE (Cursor/Windsurf vibe-coding lokal) | Multi-tenant SaaS Cloud Agent Workspaces | Edge Functions / Client-side Plugin Tooling |

---

### 9. Best Practices & Standard Industri

1. **Prinsip Least Privilege**: Workspace sandbox harus berjalan di bawah user non-root OS dengan permission terbatas pada direktori kerja proyek.
2. **Deterministic Context Snapshot**: Sebelum agent melakukan batch tool execution, simpan git tree hash:
   ```bash
   git status --porcelain
   git stash create
   ```
   Hal ini memungkinkan rollback instan jika hasil coding agen merusak struktur proyek.
3. **AST-Driven Invalidation**: Jangan biarkan LLM mengandalkan `exit_code` shell saja untuk memvalidasi syntax. Gunakan language server parser (misal: AST parsing atau `ruff check`) di level harness sebelum eksekusi commit.
4. **Token Budget Awareness**: Format output tool secara ringkas. Hindari JSON verbose jika string sederhana sudah mencukupi. Berikan LLM indikasi status terkompresi: `OK (200ms) - 14 lines modified`.

---

### 10. Hands-on Lab Exercise

#### Skenario:
Anda ditugaskan membangun harness validasi mandiri (*self-healing workspace*) yang menginstruksikan agent untuk membuat microservice matematika sederhana, menguji kodenya menggunakan `safe_execute_command`, menangkap error sintaks, dan memverifikasi perbaikan hingga sukses.

#### Langkah 1: Persiapan Lingkungan
Buat direktori sandbox terisolasi:
```bash
mkdir -p /tmp/agent_sandbox
cd /tmp/agent_sandbox
```

#### Langkah 2: Eksekusi Test Runner Script
Simpan kode harness dari Section 6 ke dalam file `agentic_workspace_harness.py`. Buat script runner `run_lab.py` berikut untuk menguji *self-correction loop*:

```python
"""
run_lab.py
Laboratorium Hands-on: Menguji respons harness terhadap syntax error
dan mitigasi otomatis path jailbreak.
"""

import asyncio
import pathlib
from agentic_workspace_harness import AgenticWorkspaceHarness, AgenticToolDispatcher

async def main():
    sandbox_dir = pathlib.Path("/tmp/agent_sandbox/project_alpha")
    harness = AgenticWorkspaceHarness(workspace_root=sandbox_dir)
    dispatcher = AgenticToolDispatcher(harness=harness)

    print("=== TEST 1: Path Traversal Attack (Security Jail) ===")
    attack_payload = {
        "path": "../../etc/evil.py",
        "content": "print('hacked')"
    }
    res = await dispatcher.dispatch("write_file", attack_payload)
    print("Respon:", res["result"])

    print("\n=== TEST 2: Deteksi Kerusakan Sintaks Python (AST Guard) ===")
    invalid_code_payload = {
        "path": "calculator.py",
        "content": "def add(a, b)\n    return a + b"  # Hilang titik dua (Syntax Error)
    }
    res = await dispatcher.dispatch("write_file", invalid_code_payload)
    print("Respon:", res["result"])

    print("\n=== TEST 3: Perbaikan Kode Valid (Self-Healing) ===")
    valid_code_payload = {
        "path": "calculator.py",
        "content": "def add(a: int, b: int) -> int:\n    return a + b\n\nif __name__ == '__main__':\n    print(f'Result: {add(10, 5)}')\n"
    }
    res = await dispatcher.dispatch("write_file", valid_code_payload)
    print("Respon:", res["result"])

    print("\n=== TEST 4: Eksekusi CLI Terisolasi di Sandbox ===")
    exec_payload = {
        "command": "python3 calculator.py"
    }
    res = await dispatcher.dispatch("execute_command", exec_payload)
    print("Respon:")
    print(res["result"]["payload"])

if __name__ == "__main__":
    asyncio.run(main())
```

#### Langkah 3: Menjalankan dan Memverifikasi Output
Jalankan harness:
```bash
python3 run_lab.py
```

#### Kriteria Keberhasilan (Verification Checklist):
- [x] **Test 1** menghasilkan response error: `[Operational Error]: Akses ditolak: Operasi path ... melompat ke luar root sandboxing.`
- [x] **Test 2** menggagalkan penulisan dan mencetak: `AST Validation Failed pada line 1, offset 14: expected ':'`. File `calculator.py` tidak tertulis di disk.
- [x] **Test 3** sukses menulis file secara atomik dan lolos verifikasi sintaksis AST.
- [x] **Test 4** menghasilkan `Exit Code: 0` dan output terminal menangkap string `Result: 15`. Direktori `/tmp/agent_sandbox/project_alpha/calculator.py` dapat dieksekusi tanpa leak process.