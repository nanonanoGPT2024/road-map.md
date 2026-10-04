# Bab 09: Desain Cuplikan Kode Multi-Bahasa yang Testable (Module 01)

## 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
* **Menganalisis dan Memitigasi *Documentation Drift*:** Mengidentifikasi titik kegagalan di mana perubahan SDK atau API Autonomous Agent/LLM menyebabkan cuplikan kode (*code snippets*) pada dokumentasi menjadi usang atau *broken*.
* **Merancang Arsitektur *Code-First Documentation*:** Mengonstruksi alur kerja *Single Source of Truth* (SSoT) menggunakan strategi ekstraksi kode berbasis Abstract Syntax Tree (AST) dan *marker-tagging*, bukan salin-tempel manual ke Markdown/MDX.
* **Mengimplementasikan Deterministic Mocking untuk Agen Stokastik:** Mengisolasi dependensi eksternal (penyedia LLM, Vector Database, panggilan RPC agen) untuk menjamin stabilitas eksekusi pengujian cuplikan kode tanpa *flakiness*.
* **Membangun Polyglot Doc-Testing CI/CD Pipeline:** Mengotomatiskan validasi kompilasi, eksekusi, dan asersi keluaran untuk cuplikan kode dalam Python, TypeScript, dan Go dalam alur continuous integration.
* **Memvalidasi *Idiomatic Parity*:** Menilai konsistensi fungsional antar-bahasa seraya mempertahankan konvensi idiomatik lokal masing-masing ekosistem (misal: `async/await` vs `goroutine` vs generator).

---

## 2. Concept Overview

Dalam rekayasa sistem *AI, Data, and Autonomous Agents*, dokumentasi teknis bukan sekadar materi bacaan pasif, melainkan antarmuka terdepan pengembang (*Developer Experience* / DevEx). Tantangan terbesar pada domain ini adalah tingginya laju perubahan API (misalnya rilis model baru, perubahan skema *function calling*, dan orkestrasi *streaming state*).

```
   TRADITIONAL (FRAGILE)                     TESTABLE (CODE-FIRST)
+--------------------------+             +--------------------------+
|      Markdown File       |             | Tested Codebase (Python/ |
|  ```python               |             |     TypeScript/Go)       |
|  agent.run() # Unchecked |             |  // [snippet-id: start]  |
|  ```                     |             |  agent.Run()             |
+--------------------------+             |  // [snippet-id: end]    |
             |                           +--------------------------+
             v (Manual Copy-Paste)                     |
+--------------------------+                           v (Automated AST Extraction)
|   Production Docs Site   |             +--------------------------+
|  (Silently broken on SDK |             |      Markdown / MDX      |
|         updates)         |             |   Transcluded Snippet    |
+--------------------------+             +--------------------------+
```

### Paradigma *Code-First* vs *Doc-First*
1. **Doc-First (Anti-Pattern):** Kode ditulis langsung di dalam blok Markdown (` ```python `). Cuplikan ini tidak memiliki dependensi eksplisit, tidak dapat dikompilasi langsung oleh *compiler/linter*, dan rentan terhadap *silent syntax errors*.
2. **Code-First (Target Skenario):** Kode ditulis dalam berkas sumber yang valid (`.py`, `.ts`, `.go`), dieksekusi di bawah *test harness* bersama unit tests, lalu diekstraksi secara programmatic ke dalam berkas dokumentasi melalui parser penanda (*marker*) atau inspeksi AST (*Abstract Syntax Tree*).

### Non-Deterministic Output Problem pada Sistem Agen
Sistem berbasis LLM menghasilkan keluaran yang probabilistik. Menguji cuplikan kode dokumentasi yang bergantung pada pemanggilan model secara langsung (*live inference*) memicu dua masalah fatal:
* **Flaky Tests:** Kegagalan pengujian akibat variasi kata pada respons, bukan kesalahan sintaksis atau logika SDK.
* **Eksekusi Lambat dan Mahal:** Biaya token API dan latensi jaringan yang tinggi pada setiap *commit* dokumentasi.

Oleh karena itu, arsitektur *testable snippet* modern mengimplementasikan teknik **Deterministic Context Injection** atau **Semantic Mocking Engine** pada level SDK/klien HTTP mock.

---

## 3. Why It Matters

Ketika mengintegrasikan sistem agen otonom—misalnya *Agentic RAG* atau *Multi-Agent Router*—kesalahan kecil pada dokumentasi membawa dampak katastropik:

* **Erosi Kepercayaan Pengembang:** Survei industri menunjukkan lebih dari 65% pengembang meninggalkan SDK atau API pihak ketiga jika cuplikan kode di dokumentasi cepat saji (*Quickstart*) gagal berjalan pada percobaan pertama (*Time to First Hello World* > 10 menit).
* **Tingginya Beban Dukungan Teknis (*Support Ticket Spikes*):** Perubahan tanda tangan fungsi dari `agent.invoke(query: str)` menjadi `agent.invoke(input: AgentInput)` yang tidak disinkronkan ke dokumentasi dapat melipatgandakan tiket eskalasi developer ke tim rekayasa sistem.
* **Degradasi Dependensi Multi-Bahasa:** Pada platform enterprise, SDK umumnya disediakan dalam tiga bahasa utama: Python (lingkungan saintifik/AI), TypeScript (antarmuka web/edge), dan Go (sistem backend/konektor performa tinggi). Tanpa harness otomatis, menjaga kesetaraan perilaku (*behavioral parity*) lintas ketiga bahasa ini membutuhkan koordinasi manual yang memakan waktu dan rentan eror.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur pemrosesan dari penulisan kode sumber terverifikasi hingga produksi situs dokumentasi:

```
[ Developer SDK Repo ]
  |-- test/snippets/python/agent_stream_test.py
  |-- test/snippets/typescript/agent_stream.test.ts
  |-- test/snippets/go/agent_stream_test.go
          |
          v (Doc-Test Runner Phase)
+----------------------------------------------------------------+
| CI Test Harness: Synthetic Execution & Isolation               |
|  - Mock Agent Runtime (Intercept LLM calls, return fixed JSON) |
|  - Pytest / Vitest / Go Test validation                        |
|  - Output Capture (STDOUT, Tool Calls)                         |
+----------------------------------------------------------------+
          |
          | (If All Tests Green)
          v
+----------------------------------------------------------------+
| Snippet Transclusion Engine (CLI / Pre-processor)             |
|  - Parse AST & Marker Tags (e.g. # [region: run_agent])        |
|  - Elide Boilerplate (Hide imports/mocks if needed)            |
|  - Synthesize Multi-Tab MDX Snippet Components                 |
+----------------------------------------------------------------+
          |
          v
[ Docs Platform Build Pipeline ]
  |-- docs/modules/agent-streaming.mdx
          |
          v
[ Published Production Docs Platform ]
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### A. Marker-Based Transclusion vs AST Parsing
Untuk memisahkan kode persiapan (*setup/mock*) dari kode utama yang relevan bagi pembaca, digunakan pendekatan bertingkat:

1. **Tag Penanda (*Region Markers*):**
   Komentar khusus ditempatkan di kode pengujian:
   * Python: `# [region: quickstart]` dan `# [endregion: quickstart]`
   * TypeScript: `// [region: quickstart]` dan `// [endregion: quickstart]`
   * Go: `// [region: quickstart]` dan `// [endregion: quickstart]`
2. **AST-Driven Elision:**
   Transclusion Engine membaca AST untuk menghapus baris mock dan assertions, memastikan pengguna hanya melihat pemanggilan API murni, sementara seluruh berkas tetap dapat diuji sepenuhnya oleh runtime pengujian standar.

### B. Arsitektur Mocking Agen Deterministik
Agar kode cuplikan dapat dieksekusi tanpa kunci API asli atau jaringan eksternal, kita menginjeksikan layer transportasi HTTP tiruan (*Mock Transport Layer*) atau menggunakan *protocol abstraction*.

```
+---------------------+      Calls      +-----------------------+
| Doc Snippet Routine | ---------------> | Local SDK Client      |
+---------------------+                 +-----------------------+
                                                    |
                                      Uses Mock Transport Layer
                                                    v
                                        +-----------------------+
                                        | Deterministic Engine  |
                                        | - Matches Route/Payload|
                                        | - Returns Mock Token  |
                                        |   Stream & Tool Calls |
                                        +-----------------------+
```

### C. Menjaga Idiomatic Parity
Setiap bahasa menangani asinkronitas dan *streaming* secara berbeda:
* **Python:** Menggunakan *Asynchronous Generators* (`async for chunk in agent.stream()`).
* **TypeScript:** Menggunakan *Async Iterables* (`for await (const chunk of agent.stream())`).
* **Go:** Menggunakan *Channels* (`for chunk := range agent.Stream(ctx)`).

Pengujian harus memvalidasi bahwa idiom ini diuji sesuai runtime standar masing-masing bahasa tanpa memaksakan translasi sintaksis mentah yang canggung (*unidiomatic code*).

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi sistem Doc-Testing lengkap yang mencakup:
1. **Transclusion Engine Engine (`doc_engine.py`):** Mengekstrak, membersihkan, dan menguji cuplikan kode dari fail uji sumber.
2. **Python Snippet Test (`test_agent_doc.py`):** Cuplikan runnable yang menguji agen otonom dengan semantic mock engine.
3. **TypeScript Snippet Spec (`agent_doc.spec.ts`):** Ekuivalen berorientasi TypeScript.

### File 1: `doc_engine.py` (Snippet Processing Engine)

```python
"""
doc_engine.py - Production-Grade Snippet Extractor and Doc-Testing Engine.
Extracts marked code regions and validates structural and syntactic sanity.
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ExtractedSnippet:
    region_id: str
    language: str
    source_file: Path
    content: str
    line_start: int
    line_end: int


class SnippetExtractionError(Exception):
    """Raised when snippet extraction violates format or constraints."""


class SnippetEngine:
    REGION_START_PATTERN = re.compile(
        r"^(?:\/\/|#)\s*\[region:\s*([a-zA-Z0-9_\-]+)\]"
    )
    REGION_END_PATTERN = re.compile(
        r"^(?:\/\/|#)\s*\[endregion:\s*([a-zA-Z0-9_\-]+)\]"
    )

    SUPPORTED_LANGUAGES = {
        ".py": "python",
        ".ts": "typescript",
        ".js": "javascript",
        ".go": "go",
    }

    def extract_from_file(self, file_path: Path) -> Dict[str, ExtractedSnippet]:
        if not file_path.is_file():
            raise FileNotFoundError(f"Source file not found: {file_path}")

        lang = self.SUPPORTED_LANGUAGES.get(file_path.suffix)
        if not lang:
            return {}

        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        snippets: Dict[str, ExtractedSnippet] = {}
        active_regions: Dict[str, int] = {}
        buffer: Dict[str, List[str]] = {}

        for line_idx, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Check region start
            start_match = self.REGION_START_PATTERN.match(stripped)
            if start_match:
                region_id = start_match.group(1)
                if region_id in active_regions:
                    raise SnippetExtractionError(
                        f"Duplicate region '{region_id}' opened at {file_path}:{line_idx}"
                    )
                active_regions[region_id] = line_idx
                buffer[region_id] = []
                continue

            # Check region end
            end_match = self.REGION_END_PATTERN.match(stripped)
            if end_match:
                region_id = end_match.group(1)
                if region_id not in active_regions:
                    raise SnippetExtractionError(
                        f"Unmatched region closing tag '{region_id}' at {file_path}:{line_idx}"
                    )
                start_line = active_regions.pop(region_id)
                snippet_body = "\n".join(buffer.pop(region_id))

                # Normalize indentation
                cleaned_body = self._dedent_snippet(snippet_body)

                # Validate syntax if Python
                if lang == "python":
                    self._validate_python_ast(cleaned_body, region_id)

                snippets[region_id] = ExtractedSnippet(
                    region_id=region_id,
                    language=lang,
                    source_file=file_path,
                    content=cleaned_body,
                    line_start=start_line,
                    line_end=line_idx,
                )
                continue

            # Append content to all currently open regions
            for region_id in active_regions:
                buffer[region_id].append(line)

        if active_regions:
            unclosed = list(active_regions.keys())
            raise SnippetExtractionError(
                f"Unclosed regions detected in {file_path}: {unclosed}"
            )

        return snippets

    @staticmethod
    def _dedent_snippet(code: str) -> str:
        """Dedent snippet code cleanly while preserving relative indentation."""
        lines = code.split("\n")
        # Filter empty lines for calculating min indentation
        non_empty_indents = [
            len(line) - len(line.lstrip(" "))
            for line in lines
            if line.strip()
        ]
        if not non_empty_indents:
            return ""
        min_indent = min(non_empty_indents)
        return "\n".join(
            line[min_indent:] if len(line) >= min_indent else line
            for line in lines
        ).strip()

    @staticmethod
    def _validate_python_ast(code: str, region_id: str) -> None:
        """Verifies that the extracted snippet is syntactically valid Python."""
        try:
            ast.parse(code)
        except SyntaxError as exc:
            # If parsing fails directly, wrap in an async function to allow standalone 'await'
            wrapped_code = f"async def __snippet_wrapper__():\n" + "\n".join(
                f"    {line}" for line in code.splitlines()
            )
            try:
                ast.parse(wrapped_code)
            except SyntaxError:
                raise SnippetExtractionError(
                    f"Snippet region '{region_id}' is not syntactically valid Python: {exc}"
                ) from exc


def main() -> None:
    engine = SnippetEngine()
    test_file = Path("test_agent_doc.py")
    if not test_file.exists():
        print(f"File {test_file} not found. Run in proper directory.", file=sys.stderr)
        sys.exit(1)

    try:
        snippets = engine.extract_from_file(test_file)
        print(f"[OK] Successfully extracted {len(snippets)} snippets.")
        for name, snippet in snippets.items():
            print(f"--- REGION: {name} ({snippet.language}) ---")
            print(snippet.content)
            print("-" * 40)
    except SnippetExtractionError as err:
        print(f"[ERROR] Extraction failed: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

### File 2: `test_agent_doc.py` (Runnable Polyglot Source - Python)

```python
"""
test_agent_doc.py - Full test file containing runnable and testable agent snippet.
Demonstrates mock injection for deterministic execution in CI.
"""

from __future__ import annotations

import asyncio
import pytest
from typing import AsyncGenerator, Dict, Any


# --- SDK Mock Layer (Simulating Autonomous Agent Framework) ---
class AgentResponse:
    def __init__(self, message: str, tool_called: bool = False):
        self.message = message
        self.tool_called = tool_called


class AutonomousAgent:
    def __init__(self, name: str, memory_backend: str = "local"):
        self.name = name
        self.memory_backend = memory_backend

    async def run_stream(self, prompt: str) -> AsyncGenerator[Dict[str, Any], None]:
        # Deterministic simulation of agent thinking and tool output
        tokens = ["Thought: Analyzing data.", " Action: QueryVectorDB.", " Result: Success."]
        for token in tokens:
            await asyncio.sleep(0.01)  # Micro-latency simulation
            yield {"token": token, "done": False}
        yield {"token": "", "done": True, "final_answer": "Analysis complete."}


# --- Doc Test Suite ---
@pytest.mark.asyncio
async def test_agent_streaming_doc_snippet() -> None:
    # Set up deterministic isolation
    agent_id = "analyst-agent-01"

    # The region below is extracted into developer documentation
    # [region: agent_streaming_quickstart]
    agent = AutonomousAgent(name=agent_id, memory_backend="in-memory")

    collected_tokens: list[str] = []
    async for chunk in agent.run_stream(prompt="Analyze system logs."):
        if not chunk["done"]:
            collected_tokens.append(chunk["token"])
        else:
            final_output = chunk["final_answer"]
    # [endregion: agent_streaming_quickstart]

    # Snippet assertions (guarantees doc claims hold true)
    assert len(collected_tokens) == 3
    assert final_output == "Analysis complete."
    assert "".join(collected_tokens).startswith("Thought: Analyzing data.")
```

### File 3: `agent_doc.spec.ts` (Runnable Polyglot Source - TypeScript)

```typescript
/**
 * agent_doc.spec.ts - TypeScript implementation for snippet transclusion.
 * Fully compatible with Vitest or Jest.
 */

import { describe, it, expect } from 'vitest';

// --- Type Definitions & Simulated SDK ---
interface StreamChunk {
  token: string;
  done: boolean;
  finalAnswer?: string;
}

class AutonomousAgent {
  constructor(
    public readonly name: string,
    public readonly memoryBackend: 'in-memory' | 'redis' = 'in-memory'
  ) {}

  async *runStream(prompt: string): AsyncGenerator<StreamChunk, void, unknown> {
    const tokens = ['Thought: Analyzing data.', ' Action: QueryVectorDB.', ' Result: Success.'];
    for (const token of tokens) {
      yield { token, done: false };
    }
    yield { token: '', done: true, finalAnswer: 'Analysis complete.' };
  }
}

describe('Documentation: Agent Streaming', () => {
  it('should stream tokens deterministically according to doc snippet', async () => {
    const agentId = 'analyst-agent-01';

    // [region: ts_agent_streaming_quickstart]
    const agent = new AutonomousAgent(agentId, 'in-memory');

    const collectedTokens: string[] = [];
    let finalOutput = '';

    for await (const chunk of agent.runStream('Analyze system logs.')) {
      if (!chunk.done) {
        collectedTokens.push(chunk.token);
      } else if (chunk.finalAnswer) {
        finalOutput = chunk.finalAnswer;
      }
    }
    // [endregion: ts_agent_streaming_quickstart]

    // Doc assertions
    expect(collectedTokens).toHaveLength(3);
    expect(finalOutput).toBe('Analysis complete.');
    expect(collectedTokens.join('')).toContain('Action: QueryVectorDB.');
  });
});
```

---

## 7. Edge Cases & Failure Modes

| Edge Case / Mode Kegagalan | Akar Masalah | Mekanisme Mitigasi Rekayasa |
| :--- | :--- | :--- |
| **Snippet Menghilangkan Setup Konfigurasi (*Elided Code*)** | Cuplikan kode dokumentasi membutuhkan inisialisasi kredensial (API Key), namun mengeksposnya pada dokumen membuat materi menjadi bertele-tele. | Buat struktur wrapper eksplisit. Gunakan penanda khusus (misal: `# [region: imports]` dan `# [region: main]`) lalu sambungkan kembali saat transklusi, atau berikan nilai mock *placeholder* seperti `"sk-fake-test-key-000000"`. |
| **Stochastic LLM Output Divergence** | Eksekusi SDK memanggil backend LLM nyata yang mengembalikan teks yang bervariasi secara leksikal. | Larang *live network calls* dalam doc-test CI. Wajibkan injeksi layer transport tiruan (*Mock HTTP / RPC transport*) yang merespons dengan struktur token identik. |
| **Divergensi Asinkronitas Lintas Bahasa** | Python menggunakan *coroutine* yang perlu ditutup secara eksplisit saat generator dibatalkan, sementara Go menggunakan *context cancellation*. | Tambahkan pengujian pembersihan resource (*cleanup assertion*) pada unit test pengiring cuplikan dokumen guna mencegah kebocoran koneksi di background. |
| **AST Parse Errors pada Partial Snippets** | Blok kode yang diekstrak hanya memuat potongan kecil (misal: hanya tubuh fungsi tanpa definisi `def`). | Terapkan fallback AST parsial (*AST wrapping heuristics*): Bungkus potongan kode dalam fungsi sintesis sebelum melempar error parsial parsing. |
| **Runtime Deadlocks pada CI Docs Runner** | Streaming generator tertahan selamanya karena stream token tidak pernah mengirimkan sinyal `done: true`. | Tetapkan `timeout` ketat (maksimum 3000ms) di tingkat harness runner untuk setiap *doc-test*. |

---

## 8. Trade-offs & Alternatif Solusi

Setiap strategi penyusunan cuplikan kode dokumentasi memiliki kompromi arsitektural yang berbeda:

```
                  Complexity vs. Maintainability
  High |
       |                                   [AST Transclusion Engine]
       |                                      (Pendekatan Modul Ini)
       |
       |                [Jupyter / MyST]
       |
       |  [Doc-First Copy-Paste]
  Low  +------------------------------------------------------------>
       Low                                                      High
                             Engine Reliability
```

| Pendekatan | Kelebihan | Kelemahan | Skenario Penggunaan Terbaik |
| :--- | :--- | :--- | :--- |
| **Manual Copy-Paste (Doc-First)** | * Zero tooling setup.<br>* Penulis leluasa memotong kode. | * Tingkat kegagalan sangat tinggi (*drift*).<br>* Tidak ada jaminan sintaks valid. | *Throwaway prototype*, catatan internal informal. |
| **Jupyter / MyST Notebooks** | * Sangat intuitif untuk saintis data.<br>* Menyimpan *rich outputs* & grafik. | * Buruk untuk multi-bahasa non-Python.<br>* Diff Git kotor karena format JSON internal. | Dokumentasi model riset AI & analisis eksploratif. |
| **Code-First AST Transclusion (Metode Modul Ini)** | * 100% testable di CI standar.<br>* Mendukung multi-bahasa seragam.<br>* IDE linting & typechecking otomatis. | * Perlu perkakas custom/CLI ekstraktor.<br>* Penulis teknis harus paham struktur repositori kode. | **SDK Enterprise, Agen Produksi, Platform API Publik.** |

---

## 9. Best Practices & Standard Industri

1. **Semantic Version-Locked Snippets:**
   Sematkan metadata versi SDK pada setiap blok cuplikan secara otomatis:
   ```markdown
   <!-- Generated by DocEngine v2.4 from test_agent_doc.py -->
   ```
2. **Deterministic Mock Injections via Fixtures:**
   Gunakan dependensi injeksi (*Interface injection*) pada *constructor* agen SDK Anda. Hindari pengujian dokumentasi yang melakukan *monkey-patching* global secara agresif karena dapat mencemari *test harness* bahasa lain.
3. **No Hidden State Fallacy:**
   Jika sebuah cuplikan kode membutuhkan inisialisasi variabel tertentu agar dapat dipahami pembaca, buat penanda *foldable* / *collapsible* pada Markdown (misal: `<details><summary>Import & Inisialisasi</summary>...`), bukan menghilangkannya sama sekali dari berkas uji.
4. **Strict Polyglot Parity Checks:**
   Terapkan aturan linimasa CI: *Pull Request* yang memperbarui cuplikan kode Python wajib menyertakan verifikasi atau pembaruan pada cuplikan TypeScript dan Go yang setara.

---

## 10. Hands-on Lab Exercise

### Skenario Lab
Anda ditugaskan merancang pipa doc-testing otomatis untuk SDK agen AI baru: **`AgentMatrix`**. SDK ini mengekspos metode pemanggilan agen streaming. Anda harus menyiapkan file uji Python, mengekstrak kodenya menggunakan parser berbasis region, dan memvalidasi bahwa cuplikan yang dihasilkan siap dirender ke platform dokumentasi.

### Langkah 1: Persiapan Lingkungan
Buat direktori proyek dan pasang dependensi yang diperlukan:
```bash
mkdir -p doc-testing-lab/src doc-testing-lab/tests
cd doc-testing-lab
python -m venv .venv
source .venv/bin/activate  # Di Windows: .venv\Scripts\activate
pip install pytest
```

### Langkah 2: Buat Skrip Engine Transklusi
Simpan kode dari **File 1 (`doc_engine.py`)** ke dalam root direktori lab Anda.

### Langkah 3: Buat Berkas Pengujian Kode SDK
Simpan kode dari **File 2 (`test_agent_doc.py`)** ke dalam direktori `tests/test_agent_doc.py`.

### Langkah 4: Jalankan Test Harness
Pastikan cuplikan kode valid secara fungsional menggunakan pytest:
```bash
pytest -v tests/test_agent_doc.py
```
*Output yang diharapkan:*
```text
tests/test_agent_doc.py::test_agent_streaming_doc_snippet PASSED [100%]
```

### Langkah 5: Eksekusi Ekstraksi Cuplikan Kode
Modifikasi direktori berkas target di `doc_engine.py` ke `tests/test_agent_doc.py`, lalu jalankan:
```bash
python doc_engine.py
```
*Output yang diharapkan:*
```text
[OK] Successfully extracted 1 snippets.
--- REGION: agent_streaming_quickstart (python) ---
agent = AutonomousAgent(name=agent_id, memory_backend="in-memory")

collected_tokens: list[str] = []
async for chunk in agent.run_stream(prompt="Analyze system logs."):
    if not chunk["done"]:
        collected_tokens.append(chunk["token"])
    else:
        final_output = chunk["final_answer"]
----------------------------------------
```

### Langkah 6: Pengujian Kegagalan Sintaksis (*Negative Test Case*)
1. Edit berkas `tests/test_agent_doc.py`.
2. Hapus tanda titik dua (`:`) pada pernyataan `async for chunk in agent.run_stream(...)` di dalam blok penanda.
3. Jalankan kembali `python doc_engine.py`.
4. Amati bahwa `doc_engine.py` melempar `SnippetExtractionError` karena terjadi pelanggaran AST, mencegah cuplikan rusak terbit ke situs dokumentasi. Revert perubahan setelah selesai.