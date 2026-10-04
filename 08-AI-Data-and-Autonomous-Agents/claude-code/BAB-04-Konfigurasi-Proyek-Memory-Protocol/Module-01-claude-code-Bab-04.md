# BAB 04: Konfigurasi Proyek & Memory Protocol (Modul 01)
**Kategori:** 08-AI-Data-and-Autonomous-Agents  
**Track:** Claude Code Engineering  
**Level:** Advanced / Enterprise-Grade  

---

## 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- **Menganalisis dan Mengimplementasikan** hierarki resolusi konfigurasi Claude Code (`Global` $\to$ `Project Root` $\to$ `Local Directory Override`) dengan preseden deterministik tanpa ambiguitas runtime.
- **Merancang dan Mengoptimasi** memory protocol berbasis berkas Markdown (`CLAUDE.md`) dan dynamic context capture di bawah batas anggaran token (*token budget*) $\le 2.5\%$ dari batas konteks model aktif.
- **Membangun Context Pruning & Compaction Engine** yang memitigasi degradasi *attention span* (*Lost in the Middle effect*) pada sesi interaksi otonom multi-turn.
- **Mengintegrasikan Fail-Safe Memory Recovery** yang mampu mendeteksi desinkronisasi konteks akibat rotasi *git branch* atau modifikasi file eksternal secara asinkron.

---

## 2. Concept Overview (Mental Model & Teori Inti)

Claude Code bukanlah sekadar antarmuka LLM berbasis terminal; ia adalah sebuah **Stateful Autonomous Coding Agent**. Agen ini beroperasi menggunakan arsitektur *Episodic State Machine* yang merekonsiliasi input manusia, abstraksi *tool execution*, dan representasi kondisi repositori ke dalam satu *Context Window* terbatas.

```
       +-------------------------------------------------------+
       |                  Agentic State Loop                   |
       |                                                       |
Input ---> [Config Resolution] -> [Context Compilation]        |
                                           |                   |
                                           v                   |
                                  [Model Reasoning]            |
                                           |                   |
Response <--- [State Update] <--- [Tool Execution] <-----------+
```

### Mental Model: Tiga Lapisan Memori Agen
1. **Static Epistemic Memory (Instruksi Dasar & Aturan Proyek):** Berada di `CLAUDE.md` dan file konfigurasi statis. Bersifat deterministik, *read-only* selama sesi berlangsung, dan diinjeksi pada *root prompt* atau *system prompt extension*.
2. **Working Dynamic Memory (Execution Graph & Scratchpad):** Berupa *in-memory event log* yang melacak riwayat pemanggilan tool, pembacaan file, keluaran bash, serta diff yang belum di-commit.
3. **Persistent Episodic Memory (Cross-session Persistence):** Berkas state `.claude/` yang menyimpan riwayat ringkasan sesi lampau, *project-specific indexing cache*, dan preferensi lingkungan pengguna lokal.

Masalah utama pada agen otonom adalah **Entropy Konteks**: seiring bertambahnya langkah eksekusi (baca file, eksekusi tes, parsing stack trace), rasio *Signal-to-Noise* (SNR) dalam *context window* menurun drastis. Memory Protocol Claude Code bertindak sebagai *deterministic governor* yang mengatur bagaimana informasi lama dipadatkan (*compacted*), informasi statis dipertahankan (*pinned*), dan informasi usang dibuang (*purged*).

---

## 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Pada repositori monorepo enterprise berskala jutaan baris kode (LOC):
- **Token Bleed & Biaya Ekstrem:** Membiarkan Claude Code membaca seluruh codebase tanpa konfigurasi batasan (*ignore rules*) dan *project guide* yang terstruktur menyebabkan konsumsi token melesat ke batas limit (200k+ token per *turn*), meningkatkan latensi inferensi hingga $>30$ detik, dan memboroskan biaya API.
- **Context Pollution & Hallucination Drift:** Ketika compiler log setebal 2.000 baris masuk ke context window secara mentah tanpa pruning, *attention weight* model terhadap aturan arsitektur utama melemah. Agen mulai melanggar standar coding tim, mengimpor dependensi terlarang, atau memodifikasi file di luar cakupan tugas.
- **Developer State Desynchronization:** Jika developer berganti branch `feature/auth` ke `hotfix/billing`, tanpa memory invalidation protocol yang adaptif, agen akan beroperasi menggunakan mental model dari branch sebelumnya, memicu modifikasi file hantu (*stale file conflicts*).

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut memvisualisasikan bagaimana Claude Code Engine memproses konfigurasi dan mengompilasi context window secara deterministik sebelum melakukan inferensi ke Anthropic Claude API.

```
[System Host Environment]
  │
  ├── 1. Global Config (~/.claude.json, ~/.claude/)
  │      └── API Keys, Global Tool Permissions, User Preferences
  │
  ├── 2. Project Base Config (<repo-root>/.claude/config.json)
  │      └── Lint Commands, Test Runners, Security Boundaries
  │
  ├── 3. Project Memory Contract (<repo-root>/CLAUDE.md)
  │      └── Architecture Rules, Style Guides, Common Workflows
  │
  └── 4. Local Override (<repo-root>/.claude/config.local.json)
         └── Developer-specific tooling, Local port mapping
                       │
                       ▼
         +───────────────────────────+
         | Configuration Multiplexer |
         |   (Hierarchy Resolution)  |
         +─────────────┬─────────────+
                       │
                       ▼
         +───────────────────────────+
         | Context Compaction Engine | ◄─── [.claudeignore / .gitignore]
         |  - Token Budget Auditor   |
         |  - Scratchpad Consolidator| ◄─── [Dynamic Tool Outputs & Diffs]
         |  - Sliding-Window Pruner  |
         +─────────────┬─────────────+
                       │
                       ▼
         +───────────────────────────+
         |   Assembled Prompt Payload|
         |  [System] (Rules + Memory)|
         |  [History] (Compact Turns)|
         |  [Latest Observation]     |
         +─────────────┬─────────────+
                       │
                       ▼
          [Anthropic Claude API Engine]
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### A. Hierarchical Configuration Resolution
Claude Code menerapkan evaluasi konfigurasi berbasis *monotonic override*:

$$\text{Final Config} = \text{Default} \oplus C_{\text{global}} \oplus C_{\text{project}} \oplus C_{\text{local}} \oplus C_{\text{cli\_args}}$$

Dimana operator $\oplus$ adalah operasi *deep-merge* dengan prioritas sisi kanan menimpa (*override*) sisi kiri:
1. **Default Engine Rules:** Hardcoded fallback values di binary CLI.
2. **Global Config (`~/.claude.json`):** Berlaku di seluruh mesin developer.
3. **Project Config (`.claude/config.json`):** Diterapkan via version control (Git) untuk seluruh tim.
4. **Project Memory (`CLAUDE.md`):** High-level operational contract (instruksi natural language + command targets).
5. **Local Override (`.claude/config.local.json`):** Diabaikan oleh Git, spesifik untuk mesin lokal developer.
6. **Explicit CLI Flags (`--dangerously-skip-permissions`, dll):** Prioritas mutlak saat runtime.

### B. `CLAUDE.md` Structural Protocol
`CLAUDE.md` dievaluasi bukan sebagai dokumentasi pasif, melainkan sebagai **Deterministic System Extension**. Agar token efisien, ia harus mengikuti skema formal berikut:

```markdown
# Repository Guidelines & Operational Context

## Build & Test Commands
- Build: `pnpm run build`
- Typecheck: `pnpm run typecheck`
- Unit Tests: `pnpm vitest run <file>`
- Single Test: `pnpm vitest run tests/unit/auth.test.ts`

## Code Style & Architecture Boundaries
- Strict Types: Dilarang menggunakan `any`. Gunakan `unknown` + Zod schema validation.
- Concurrency: Gunakan async/await, hindari raw Promise constructors.
- Error Handling: Gunakan Result pattern via `neverthrow`. Lempar exceptions HANYA pada unrecoverable system crash.

## Directory Layout & Key Boundaries
- `src/core/`: Zero-dependency domain logic.
- `src/infra/`: I/O, DB, Network operations. Dilarang diimpor langsung oleh `src/core/`.
```

### C. Token Budgeting & Compaction Algorithm
Claude Code membagi batas konteks menjadi alokasi terisolasi:

| Komponen Konteks | Alokasi Anggaran Max | Karakteristik Retensi |
| :--- | :--- | :--- |
| **System Instruction Base** | 2,000 Token | Statis, *Immutable* |
| **Project Rules (`CLAUDE.md`)** | 3,000 Token | Statis, Dipotong jika melebihi kuota |
| **Environment & Git Context** | 1,500 Token | Dinamis, Ter-update tiap turn |
| **Tool Execution History** | 150,000+ Token | Dinamis, Menjadi subjek *compaction* |
| **Reserved Output Space** | 8,000 Token | Ruang generasi respons model |

Jika `Tool Execution History` melampaui ambang batas ($80\%$ dari total window), algoritma **Context Compaction** dijalankan:
1. **Terminal Output Pruning:** Output tool berbasis stdout besar (>50 baris) dipotong menjadi format ringkas: baris 1-10 + `[... N baris dipotong ...] ` + 10 baris terakhir.
2. **Ephemeral Observation Dropping:** Riwayat file inspection (`readFile`) yang tidak berujung pada perubahan dibersihkan dari percakapan masa lalu, menyisakan jejak metadata sederhana: `Checked <path>, no changes needed`.
3. **Diff Summarization:** State diff yang panjang diringkas menjadi daftar berkas terisolasi dan ringkasan fungsional AST mutation.

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi Python 3.12+ tingkat enterprise untuk **Configuration Multiplexer & Memory Protocol Context Manager**, lengkap dengan strictly typed Pydantic models, context compaction, dan file-watching hash checks.

```python
"""
Claude Code Configuration Multiplexer & Memory Protocol Context Manager.
Memenuhi standar PEP 8, Fully Typed, Asyncio-compliant.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field, ValidationError

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ClaudeMemoryProtocol")


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class ProjectRulesConfig(BaseModel):
    """Skema validasi untuk subset konfigurasi formal dari .claude/config.json"""
    lint_command: Optional[str] = Field(default=None, description="Perintah linter proyek")
    test_command: Optional[str] = Field(default=None, description="Perintah pengujian utama")
    max_token_budget_memory: int = Field(default=3000, description="Maksimum token untuk memory rules")
    disallowed_directories: List[str] = Field(
        default_factory=lambda: [".git", "node_modules", "dist", "build", ".venv"],
        description="Direktori yang tidak boleh diakses oleh runtime context engine"
    )
    enforce_strict_types: bool = Field(default=True, description="Flag enforce type safety")


@dataclass(frozen=True)
class MemorySnapshot:
    raw_content: str
    sha256_hash: str
    token_estimate: int
    is_truncated: bool


class ConfigurationMultiplexer:
    """
    Menyelesaikan hierarki konfigurasi: Global -> Project -> Local Override.
    Menerapkan dynamic fallback parsing.
    """

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root.resolve()
        self.global_config_path = Path.home() / ".claude.json"
        self.project_config_path = self.workspace_root / ".claude" / "config.json"
        self.local_override_path = self.workspace_root / ".claude" / "config.local.json"

    def _read_json_safe(self, path: Path) -> Dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Gagal memuat konfigurasi dari {path}: {str(e)}. Fallback ke default.")
            return {}

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        merged = base.copy()
        for key, value in override.items():
            if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                merged[key] = self._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    def resolve_effective_config(self) -> ProjectRulesConfig:
        """Menggabungkan semua strata konfigurasi menjadi konfigurasi final tervoidasi."""
        global_cfg = self._read_json_safe(self.global_config_path)
        project_cfg = self._read_json_safe(self.project_config_path)
        local_cfg = self._read_json_safe(self.local_override_path)

        merged_stage1 = self._deep_merge(global_cfg, project_cfg)
        final_merged = self._deep_merge(merged_stage1, local_cfg)

        try:
            return ProjectRulesConfig(**final_merged)
        except ValidationError as ve:
            logger.error(f"Validasi konfigurasi gagal, memulihkan ke konfigurasi default: {ve}")
            return ProjectRulesConfig()


class MemoryProtocolManager:
    """
    Mengelola siklus hidup context memory:
    - CLAUDE.md parsing & compaction
    - Token budget verification
    - In-memory event scratchpad management
    """

    CHAR_TO_TOKEN_RATIO: float = 3.8  # Heuristik aproksimasi konservatif model Claude

    def __init__(self, workspace_root: Path, config: ProjectRulesConfig):
        self.workspace_root = workspace_root
        self.config = config
        self.claude_md_path = self.workspace_root / "CLAUDE.md"
        self._last_snapshot: Optional[MemorySnapshot] = None
        self._scratchpad_events: List[Dict[str, str]] = []

    def _calculate_token_estimate(self, text: str) -> int:
        return int(len(text) / self.CHAR_TO_TOKEN_RATIO)

    def _compute_sha256(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def load_memory_contract(self) -> MemorySnapshot:
        """
        Memuat berkas CLAUDE.md, menerapkan truncating deterministik
        jika melewati token budget yang dialokasikan.
        """
        if not self.claude_md_path.is_file():
            logger.info("File CLAUDE.md tidak ditemukan. Menggunakan fallback zero-memory contract.")
            empty_hash = self._compute_sha256("")
            self._last_snapshot = MemorySnapshot("", empty_hash, 0, False)
            return self._last_snapshot

        try:
            with open(self.claude_md_path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            logger.error(f"Gagal membaca CLAUDE.md: {e}")
            return MemorySnapshot("", self._compute_sha256(""), 0, False)

        raw_tokens = self._calculate_token_estimate(content)
        max_tokens = self.config.max_token_budget_memory

        if raw_tokens > max_tokens:
            logger.warning(
                f"Memory Token Exhaustion: CLAUDE.md terdeteksi ~{raw_tokens} tokens. "
                f"Batas adalah {max_tokens}. Menjalankan Truncation Protocol."
            )
            # Pangkas berdasarkan alokasi karakter
            allowed_chars = int(max_tokens * self.CHAR_TO_TOKEN_RATIO)
            truncated_content = (
                content[:allowed_chars]
                + "\n\n<!-- WARNING: CLAUDE.md TRUNCATED DUE TO TOKEN BUDGET OVERFLOW -->"
            )
            snapshot = MemorySnapshot(
                raw_content=truncated_content,
                sha256_hash=self._compute_sha256(truncated_content),
                token_estimate=max_tokens,
                is_truncated=True
            )
        else:
            snapshot = MemorySnapshot(
                raw_content=content,
                sha256_hash=self._compute_sha256(content),
                token_estimate=raw_tokens,
                is_truncated=False
            )

        self._last_snapshot = snapshot
        return snapshot

    def append_scratchpad(self, role: str, observation: str) -> None:
        """Menambahkan event ke dynamic working memory scratchpad."""
        self._scratchpad_events.append({"role": role, "content": observation})

    def compact_working_memory(self, max_allowed_events: int = 10) -> None:
        """
        Algoritma Lossy Context Compaction:
        Meringkas event log eksekusi jika turn melebihi threshold tertentu.
        """
        if len(self._scratchpad_events) <= max_allowed_events:
            return

        logger.info("Mengompilasi dynamic memory scratchpad (Context Pruning Running)...")
        retained_tail = self._scratchpad_events[-max_allowed_events:]
        evicted_count = len(self._scratchpad_events) - max_allowed_events

        # Meringkas event yang dibuang
        summary_event = {
            "role": "system",
            "content": f"[COMPACTION AGENT]: {evicted_count} operasi tool terdahulu diringkas. Fokus pada instruksi terakhir."
        }
        self._scratchpad_events = [summary_event] + retained_tail

    def compile_system_prompt_payload(self) -> str:
        """
        Menyusun final dynamic system context untuk diinjeksi ke Anthropic API.
        """
        snapshot = self.load_memory_contract()
        payload_segments: List[str] = [
            "=== SYSTEM ARCHITECTURE RULES ===",
            snapshot.raw_content,
            "\n=== RUNTIME CONTEXT & ENVIRONMENT ===",
            f"Workspace Path: {self.workspace_root}",
            f"Lint Target: {self.config.lint_command or 'None specified'}",
            f"Test Target: {self.config.test_command or 'None specified'}",
            f"Enforce Strict Types: {self.config.enforce_strict_types}",
            "\n=== EPISODIC WORKING MEMORY ==="
        ]

        for idx, event in enumerate(self._scratchpad_events):
            payload_segments.append(f"[{event['role'].upper()}]: {event['content']}")

        return "\n".join(payload_segments)


# ==============================================================================
# Simulation & Demonstration Runtime
# ==============================================================================
async def main() -> None:
    temp_dir = Path("/tmp/claude_engine_workspace")
    temp_claude_dir = temp_dir / ".claude"
    temp_claude_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Setup Mock Project Config
        project_config_file = temp_claude_dir / "config.json"
        project_config_file.write_text(json.dumps({
            "lint_command": "cargo clippy -- -D warnings",
            "test_command": "cargo test --workspace",
            "max_token_budget_memory": 500,
            "enforce_strict_types": True
        }))

        # 2. Setup Mock Local Override Config (Local Developer Context)
        local_override_file = temp_claude_dir / "config.local.json"
        local_override_file.write_text(json.dumps({
            "test_command": "cargo nextest run"  # Menimpa default team config
        }))

        # 3. Setup Mock CLAUDE.md dengan instruksi substansial
        claude_md_file = temp_dir / "CLAUDE.md"
        claude_md_file.write_text(
            "# Rust Enterprise Monorepo Rules\n"
            "- Always use anyhow::Result for CLI interfaces.\n"
            "- Never suppress warnings via #[allow(warnings)].\n"
            "- All network operations must define explicit Tokio timeout bounds.\n"
            + ("\n- Rule: Avoid manual memory leaks via Box::leak." * 100) # Inject token load
        )

        # 4. Resolve System Configuration
        multiplexer = ConfigurationMultiplexer(workspace_root=temp_dir)
        effective_config = multiplexer.resolve_effective_config()
        
        logger.info(f"Resolved Test Command: {effective_config.test_command}")
        assert effective_config.test_command == "cargo nextest run", "Override logic failure!"

        # 5. Initialize Memory Protocol Engine
        memory_mgr = MemoryProtocolManager(workspace_root=temp_dir, config=effective_config)
        snapshot = memory_mgr.load_memory_contract()
        logger.info(f"Snapshot Is Truncated: {snapshot.is_truncated}")
        logger.info(f"Snapshot Estimated Tokens: {snapshot.token_estimate}")

        # 6. Simulate Dynamic Event Accumulation & Context Compaction
        for i in range(15):
            memory_mgr.append_scratchpad("tool_output", f"Reading directory segment chunk_{i}. Found 12 files.")
        
        # Verify compaction
        memory_mgr.compact_working_memory(max_allowed_events=5)
        
        # Compile System Prompt Payload
        final_payload = memory_mgr.compile_system_prompt_payload()
        logger.info("Final Compiled System Prompt Payload Generated Successfully.")
        print("\n--- SAMPLE SYSTEM PROMPT PAYLOAD (TRUNCATED PREVIEW) ---")
        print(final_payload[:800] + "\n... [TRUNCATED] ...\n" + final_payload[-300:])

    finally:
        # Cleanup mock files
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 7. Edge Cases & Failure Modes

Dalam lingkungan enterprise, memory pipeline dapat mengalami anomali berikut:

### 1. The Circular Symlink Explosion
- **Skenario:** Repositori berisi symbolic link direktori yang mereferensikan parent root (`node_modules` atau data storage pipeline).
- **Dampak:** Engine context loader memindai direktori tanpa henti, memicu `RecursionError` atau konsumsi memory tak hingga (*out-of-memory error*).
- **Mitigasi:** Resolusi path menggunakan `Path.resolve()` dengan deteksi inode unik (`os.stat(p).st_ino`) serta hard-limit path traversal depth ($d \le 8$).

### 2. Context Poisoning via Rogue Git Branch Switch
- **Skenario:** Developer mengeksekusi `git checkout legacy-v1` di terminal terpisah saat sesi Claude Code sedang aktif. Sesi masih menyimpan snapshot AST dan referensi modul dari branch `feature-v2`.
- **Dampak:** Agen menghasilkan kode menggunakan antarmuka API modern yang belum ada pada branch legacy, memicu compile failure terus-menerus.
- **Mitigasi:** Claude Memory Protocol wajib mendaftarkan *file-watcher* pada `.git/HEAD`. Begitu SHA-1 commit berubah, seluruh `Working Dynamic Memory` otomatis diinvalidasi (*flushed*), dan model diinstruksikan melakukan rekonsiliasi state via `git status`.

### 3. Asymmetric Compaction Loss (Lost Architectural Context)
- **Skenario:** Tool output menghasilkan puluhan trace log fatal, mendorong context window melakukan compactor eviction terhadap instruksi awal `CLAUDE.md`.
- **Dampak:** Agen kehilangan informasi static constraints (misal: "Jangan sentuh database production"), memicu aksi berbahaya.
- **Mitigasi:** Skema *Pinned System Boundaries*. Static rules `CLAUDE.md` dilarang masuk ke array dynamic context yang dapat dieviction; ia diisolasi secara khusus pada level `System Message Level 0`.

---

## 8. Trade-offs & Alternatif Solusi

| Pendekatan Memory | Kelebihan | Kekurangan | Trade-off Score (Skenario CLI Agent) |
| :--- | :--- | :--- | :--- |
| **Deterministic Markdown (`CLAUDE.md`)** | Zero overhead dependensi, didukung Git versioning, transparan bagi developer, deterministik. | Kapasitas penyimpanan terbatas oleh token limit, parsing semi-terstruktur. | **9.5/10 (Optimal untuk Developer Workflows)** |
| **Local Vector DB (RAG via Chroma / SQLite-VSS)** | Mampu menampung jutaan LOC repositori, pencarian semantik fleksibel. | Non-deterministik, latensi inferensi bertambah (embedding latency), retrieval miss merusak reliabilitas logika kompilasi. | **5.0/10 (Overkill & Rapuh untuk Code Reasoning Lokal)** |
| **Graph-based Code AST Indexer** | Sangat akurat dalam memahami relasi simbolik dependensi antar modul. | Biaya indexing berat saat *cold boot*, tidak efisien menangkap instruksi natural language tim. | **7.0/10 (Cocok sebagai Tool Pendukung, Bukan Memory Hub)** |

---

## 9. Best Practices & Standard Industri

1. **Aturan 2.000 Token:** Pertahankan ukuran total file `CLAUDE.md` di bawah 2.000 token (~7.500 karakter). Jika codebase Anda kompleks, gunakan pemisahan modular via subfolder (misal: `docs/architecture/claude-rules/`) dan referensikan path-nya alih-alih menyalin seluruh teks.
2. **Definisikan Command dengan Deterministik:** Jangan tulis instruksi abstrak seperti *"Jalankan unit tests yang relevan"*. Tulis perintah absolut:
   ```markdown
   - Test Single File: pnpm jest --runTestsByPath <target-path>
   - Lint Fix: pnpm eslint --fix <target-path>
   ```
3. **Automasi Pembersihan `.claude/` via `.gitignore`:**
   Pastikan file konfigurasi lokal dan state cache tidak bocor ke remote repo:
   ```gitignore
   # .gitignore
   .claude/config.local.json
   .claude/memory/
   .claude/index.db
   ```
4. **CI Memory Linter:** Pasang pre-commit hook atau GitHub Actions workflow yang memverifikasi integritas syntax dan batasan token `CLAUDE.md`:
   ```bash
   # Quick CLI Check
   python -c "assert len(open('CLAUDE.md').read()) < 10000, 'CLAUDE.md melebihi batas enterprise!'"
   ```

---

## 10. Hands-on Lab Exercise

### Skenario
Anda bertugas menyiapkan repositori TypeScript (Next.js 14 Monorepo) dengan pipeline Claude Code yang stabil, deterministik, dan terlindungi dari *token exhaustion*.

### Langkah-Langkah Pengerjaan

#### Langkah 1: Inisialisasi Struktur Konfigurasi Repositori
Jalankan di terminal root project Anda:
```bash
mkdir -p .claude
touch CLAUDE.md .claude/config.json .claude/config.local.json
```

#### Langkah 2: Buat Team Configuration File
Buka `.claude/config.json` dan tetapkan batasan operasional tim:
```json
{
  "lint_command": "pnpm lint",
  "test_command": "pnpm test:unit",
  "max_token_budget_memory": 2500,
  "disallowed_directories": [
    ".next",
    "coverage",
    "public/static"
  ],
  "enforce_strict_types": true
}
```

#### Langkah 3: Definisikan Kontrak Operasional di `CLAUDE.md`
Isi file `CLAUDE.md` dengan instruksi terstruktur:
```markdown
# Monorepo Core Directives

## Quick Execution Commands
- Build: `pnpm build`
- Unit Test Target: `pnpm vitest run [filepath]`
- Typecheck: `pnpm tsc --noEmit`

## Architecture Isolation
- Next.js Server Components dilarang mengimpor module dari `client/`
- Database layer HANYA boleh diakses dari `packages/database`

## Code Hygiene
- Dilarang keras menggunakan `eval()`, `any`, atau `@ts-ignore`.
- Gunakan schema parsing `zod` di semua layer network boundaries.
```

#### Langkah 4: Terapkan Local Developer Override
Untuk mesin lokal Anda yang menggunakan custom binary path, ubah `.claude/config.local.json`:
```json
{
  "test_command": "pnpm vitest run --reporter=verbose"
}
```

#### Langkah 5: Pengujian Memory Protocol Execution
Jalankan engine demonstrasi memory pipeline (dari implementasi Section 6):
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pydantic
python path/to/memory_protocol_engine.py
```

### Kriteria Verifikasi
1. **Verifikasi Output Override:** Engine harus mencetak `Resolved Test Command: pnpm vitest run --reporter=verbose`, membuktikan bahwa `config.local.json` berhasil menimpa `.claude/config.json`.
2. **Uji Token Boundary:** Gandakan teks pada `CLAUDE.md` hingga mencapai >15.000 karakter, lalu jalankan kembali skrip. Engine harus mengeluarkan peringatan `Memory Token Exhaustion` dan secara otomatis memotong file dengan penanda komentar `<!-- WARNING: CLAUDE.md TRUNCATED -->` tanpa mematikan runtime.