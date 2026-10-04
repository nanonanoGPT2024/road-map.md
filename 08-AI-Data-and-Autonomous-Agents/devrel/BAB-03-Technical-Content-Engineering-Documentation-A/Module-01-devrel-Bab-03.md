# Bab 03: Technical Content Engineering & Documentation Architecture
## Module 01: AI-Native Documentation Architecture & Continuous Code Verification Pipeline

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Membangun Arsitektur Dual-Audience Documentation**: Merancang sistem dokumentasi teknis yang dioptimalkan secara simultan untuk pembaca manusia (software engineer) dan *autonomous agentic consumers* (seperti Cursor, Devin, Claude Code) menggunakan standar `llms.txt` dan skema *markdown AST*.
- **Mengimplementasikan Automated Snippet Verification Pipeline**: Membangun sistem Continuous Integration (CI) berbasis Python untuk mengekstrak, mengisolasi, dan memvalidasi sintaks serta *runtime execution* dari seluruh blok kode (Python/Bash) di dalam dokumentasi Markdown secara deterministik.
- **Mengeliminasi Non-Deterministic Doc Rot**: Menerapkan pola *mocking* dan *snapshot testing* untuk API model AI (LLM inference, vector retrieval) agar pengujian dokumentasi tidak bergantung pada kuota eksternal, latensi jaringan, atau perubahan bobot model (*stochastic drift*).
- **Merancang Machine-Readable Context Ingestion**: Mengembangkan *generator* metadata otomatis yang memetakan relasi dependensi, versi SDK, dan *context window budget* ke dalam format struktural terkompresi untuk konsumsi LLM.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Dokumentasi modern pada ekosistem **AI, Data, & Autonomous Agents** tidak lagi sekadar katalog teks statis berbasis HTML. Kita berada pada era **Dual-Audience Paradigm**:

```
                  ┌────────────────────────────────────────┐
                  │       Single Source of Truth           │
                  │        (Markdown / MDX / Markdoc)      │
                  └──────────────────┬─────────────────────┘
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
    ┌─────────────────────────┐             ┌─────────────────────────┐
    │     Human Developer     │             │ Autonomous Coding Agent │
    │  (Visual, Navigable,    │             │  (Dense, Token-Optimal, │
    │   Conceptual, Diátaxis) │             │   Deterministically Valid)
    └─────────────────────────┘             └─────────────────────────┘
```

#### Mental Model: The Executable Spec
Dokumentasi teknis untuk AI SDK dan platform agen harus diperlakukan sebagai **kompilasi spesifikasi yang dapat dieksekusi (*Executable Specification*)**. Jika sebuah *quickstart* atau *cookbook snippet* menghasilkan *runtime error*, dokumentasi tersebut diklasifikasikan sebagai *broken build*, bukan sekadar *typo*.

#### Tantangan Unik Dokumentasi AI & Data Platform:
1. **High API Velocity & Semantic Drift**: SDK LLM (seperti LangChain, LlamaIndex, atau vendor native SDK) merilis perubahan API minor/patch yang kerap merusak kompatibilitas mundur (*backward compatibility*).
2. **Non-Deterministic Outputs**: Contoh kode yang memanggil model AI menghasilkan respons probabilistik. Memverifikasi kode tersebut via CI memerlukan pemisahan ketat antara *execution correctness* (apakah *pipeline* berjalan tanpa error) dan *assertive exact matching* (yang pasti gagal karena variasi output token).
3. **Agent Consumption Efficiency**: Agen otonom membaca dokumentasi melalui *context window*. Format web tradisional (penuh dengan tag HTML, CSS, script pelacak, dan navigasi DOM yang redundan) membuang *context budget* berharga dan meningkatkan risiko halusinasi sintaksis.

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Pada tingkat enterprise, kegagalan dokumentasi teknis pada platform AI berdampak langsung pada metrik bisnis dan operasional:

- **Time-to-First-Token (TTFT) / Time-to-Hello-World**: Pengembang yang menghadapi *AttributeError* pada *quickstart* resmi dalam 5 menit pertama memiliki tingkat *drop-off* sebesar >60% (Developer Churn).
- **Agent Hallucination Amplification**: Ketika autonomous agent (misal, Cursor atau Copilot Workspace) membaca dokumentasi usang yang masih mereferensikan argumen yang telah di-*deprecated*, agen tersebut akan menghasilkan kode usang secara persisten, membingungkan teknisi, dan memicu banjir tiket bantuan (*support burden*).
- **Security Vulnerabilities via Copy-Paste**: Snippet yang tidak diverifikasi secara berkala sering kali meninggalkan *anti-patterns*, seperti hardcoded credential placeholders yang ambigu, insecure deserialization, atau kegagalan penanganan *rate limiting* yang memicu kegagalan sistem downstream.

Membangun arsitektur *Continuous Documentation Verification* (DocOps) memastikan setiap baris kode yang tampil di portal publik identik dengan status fungsional SDK pada commit Git terkini.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan end-to-end pipeline: dari commit dokumentasi di Git, validasi blok kode dalam sandbox terisolasi, pembuatan representasi visual untuk manusia, hingga kompilasi metadata `llms.txt` untuk agen otonom.

```
+---------------------------------------------------------------------------------------+
|                               DOCS-AS-CODE REPOSITORY                                 |
|  /docs/**/*.md  |  /snippets/**/*.py  |  metadata.yaml  |  spectral.yaml             |
+-------------------------------------------+-------------------------------------------+
                                            |
                                  Git Push / Pull Request
                                            |
                                            v
+---------------------------------------------------------------------------------------+
|                                CI/CD VALIDATION PIPELINE                              |
|                                                                                       |
|   +---------------------+    AST Parsing      +-----------------------------------+   |
|   | Markdown Parser     | ------------------> | Snippet Extraction Engine         |   |
|   | (markdown-it / AST) |                     | - Python, Bash, JSON Blocks       |   |
|   +---------------------+                     +-----------------+-----------------+   |
|                                                                 |                     |
|                                                                 v                     |
|   +-------------------------------------------------------------+-----------------+   |
|   |                     EPHEMERAL EXECUTION SANDBOX                               |   |
|   |                                                                               |   |
|   |  +------------------------+  IPC / Env Inject   +--------------------------+  |   |
|   |  | Local Mock LLM Server  | <-----------------> | Async Subprocess Runner  |  |   |
|   |  | (Deterministic Payload)|                     | (Memory/Timeout Bounds)  |  |   |
|   |  +------------------------+                     +-------------+------------+  |   |
|   +---------------------------------------------------------------|---------------+   |
|                                                                   |                   |
|                                     Execution Passed              |                   |
+-------------------------------------------------------------------|-------------------+
                                                                    v
                       +--------------------------------------------+-------------------+
                       |                                                                |
                       v                                                                v
+---------------------------------------------+   +---------------------------------------------+
|           HUMAN-FACING PIPELINE             |   |            AGENT-FACING PIPELINE            |
|                                             |   |                                             |
|  +---------------------------------------+  |   |  +---------------------------------------+  |
|  | Static Site Generator (Docusaurus/    |  |   |  | Semantic Context Compiler             |  |
|  | Nextra/Mintlify)                      |  |   |  | - Strips noise, unifies schema        |  |
|  +-------------------+-------------------+  |   |  +-------------------+-------------------+  |
|                      |                      |   |                      |                      |
|                      v                      |   |                      v                      |
|  +---------------------------------------+  |   |  +---------------------------------------+  |
|  | Production Docs Portal                |  |   |  | Distribution Endpoints:               |  |
|  | (HTML, Interactive Wasm Playground)   |  |   |  | - /.well-known/llms.txt               |  |
|  |                                       |  |   |  | - /llms-full.txt                      |  |
|  +---------------------------------------+  |   |  +---------------------------------------+  |
+---------------------------------------------+   +---------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Abstraction Syntax Tree (AST) Snippet Extraction
Validasi dokumentasi modern tidak menggunakan *regex matching* biasa. Parsing dilakukan menggunakan engine AST (seperti `markdown-it-py` atau library AST CommonMark) untuk membangun nodus dokumen:
- Mengidentifikasi nodus berjenis `fence` (kode berpagar triple-backtick).
- Memeriksa atribut `info string` (misalnya: `python title="example.py" execution="true" env="sandbox"`).
- Menyusun blok-blok parsial (yang sering dipecah untuk keperluan naratif) menjadi satu modul yang dapat dieksekusi (*virtual script compilation*).

#### B. Isolasi Eksekusi & Mocking Determinisme
Agar pipeline CI cepat, murah, dan aman:
1. **Process Sandboxing**: Snippet dijalankan dalam sub-proses dengan limitasi sumber daya ketat (`ulimit` untuk memori, pembatasan network egress, dan timeout 10-15 detik).
2. **Provider Virtualization**: Library seperti `pytest-mock` atau interceptor HTTP (misal: `responses` / `httpx-mock`) disuntikkan secara dinamis ke runtime snippet. Panggilan ke endpoint model AI seperti `https://api.openai.com/v1/chat/completions` dibelokkan ke *dummy response matrix* lokal. Hal ini menjamin bahwa kegagalan CI murni disebabkan oleh *syntax error*, *import resolution failure*, atau *API contract breakage*, bukan masalah ketersediaan layanan vendor.

#### C. Standar `llms.txt` Architecture
Diformulasikan untuk standardisasi konsumsi agen (serupa dengan `robots.txt` untuk crawler mesin pencari), arsitektur `llms.txt` membagi dokumentasi menjadi dua tier:
1. **Manifest File (`/llms.txt`)**: Dokumen ringkas terstruktur Markdown yang memuat nama proyek, deskripsi singkat, ringkasan konsep inti, dan daftar URL kanonikal beserta ringkasan fungsinya.
2. **Full Ingestion File (`/llms-full.txt`)**: Gabungan seluruh file Markdown dokumentasi yang telah dibersihkan dari artefak visual (gambar base64, styling khusus, komponen React kompleks) dengan penandaan struktur hierarki yang jelas.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi pipeline pengujian dokumentasi enterprise dan generator `llms.txt` menggunakan **Python 3.11+**. Pipeline ini mengurai markdown, mengekstrak blok kode yang ditandai, menjalankannya di sandbox terisolasi dengan penanganan mock LLM, lalu menghasilkan artefak `llms.txt`.

#### Struktur Direktori Proyek:
```text
docops-engine/
├── core/
│   ├── __init__.py
│   ├── extractor.py
│   ├── runner.py
│   └── agent_manifest.py
├── tests/
│   └── test_sample_doc.md
└── main.py
```

#### File: `core/extractor.py`
```python
"""
Ekstraktor AST Markdown untuk mengambil blok kode executable.
"""
from dataclasses import dataclass
from typing import List, Dict, Optional
import markdown_it
from markdown_it.token import Token

@dataclass(frozen=True)
class CodeSnippet:
    file_path: str
    language: str
    code: str
    line_number: int
    metadata: Dict[str, str]

class MarkdownASTExtractor:
    def __init__(self):
        # Inisialisasi parser CommonMark standar
        self.md = markdown_it.MarkdownIt("commonmark", {"enable": ["table"]})

    def parse_file(self, file_path: str) -> List[CodeSnippet]:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        tokens: List[Token] = self.md.parse(content)
        snippets: List[CodeSnippet] = []

        for token in tokens:
            if token.type == "fence":
                info_parts = token.info.strip().split()
                if not info_parts:
                    continue
                
                language = info_parts[0].lower()
                metadata = {}

                # Ekstraksi metadata kustom (format: key="value")
                for part in info_parts[1:]:
                    if "=" in part:
                        k, v = part.split("=", 1)
                        metadata[k] = v.strip('"\'')

                # Filter hanya blok yang ditandai untuk dieksekusi atau default python
                if metadata.get("execute", "true").lower() == "true":
                    snippets.append(
                        CodeSnippet(
                            file_path=file_path,
                            language=language,
                            code=token.content,
                            line_number=token.map[0] if token.map else 0,
                            metadata=metadata
                        )
                    )
        return snippets
```

#### File: `core/runner.py`
```python
"""
Sandbox Execution Engine untuk snippet kode Python dengan Mocking Interception.
"""
import sys
import subprocess
import tempfile
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class ExecutionResult:
    snippet_file: str
    line_number: int
    is_success: bool
    stdout: str
    stderr: str
    exit_code: int

class PythonSandboxRunner:
    def __init__(self, timeout_seconds: int = 15):
        self.timeout_seconds = timeout_seconds

    def _inject_runtime_harness(self, original_code: str) -> str:
        """
        Menyuntikkan mock interceptor untuk API AI (contoh: OpenAI/Anthropic SDK)
        secara dinamis ke dalam kode sebelum dieksekusi, sehingga validasi CI 
        tidak memakan kuota token nyata.
        """
        harness = """
import sys
from unittest.mock import MagicMock

# Mock framework API LLM umum secara universal
class MockLLMResponse:
    def __init__(self, text="Mocked AI completion response"):
        self.choices = [MagicMock(message=MagicMock(content=text))]
        self.text = text

try:
    import openai
    openai.chat.completions.create = MagicMock(return_value=MockLLMResponse())
except ImportError:
    pass

# User Code Dimulai di Sini:
"""
        return harness + "\n" + original_code

    def execute(self, snippet_file: str, line_number: int, code: str) -> ExecutionResult:
        wrapped_code = self._inject_runtime_harness(code)

        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as temp_file:
            temp_file.write(wrapped_code)
            temp_path = temp_file.name

        try:
            # Jalankan kode di subprocess independen dengan isolasi environment
            env = os.environ.copy()
            env["PYTHONPATH"] = os.getcwd()
            env["CI_DOCS_VERIFICATION"] = "1"

            process = subprocess.run(
                [sys.executable, temp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=env
            )

            return ExecutionResult(
                snippet_file=snippet_file,
                line_number=line_number,
                is_success=(process.returncode == 0),
                stdout=process.stdout,
                stderr=process.stderr,
                exit_code=process.returncode
            )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                snippet_file=snippet_file,
                line_number=line_number,
                is_success=False,
                stdout="",
                stderr=f"FATAL: Snippet execution timed out after {self.timeout_seconds}s.",
                exit_code=-1
            )
        except Exception as e:
            return ExecutionResult(
                snippet_file=snippet_file,
                line_number=line_number,
                is_success=False,
                stdout="",
                stderr=f"Runtime infrastructure error: {str(e)}",
                exit_code=-2
            )
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
```

#### File: `core/agent_manifest.py`
```python
"""
Generator manifest kontekstual agentic (llms.txt) dari dokumen yang tervalidasi.
"""
import os
from typing import List, Dict

class AgentManifestGenerator:
    def __init__(self, project_name: str, base_url: str, description: str):
        self.project_name = project_name
        self.base_url = base_url.rstrip("/")
        self.description = description
        self.sections: Dict[str, List[Dict[str, str]]] = {}

    def add_document(self, category: str, title: str, relative_path: str, summary: str):
        if category not in self.sections:
            self.sections[category] = []
        self.sections[category].append({
            "title": title,
            "url": f"{self.base_url}/{relative_path.lstrip('/')}",
            "summary": summary
        })

    def render_llms_txt(self) -> str:
        """
        Menghasilkan output terstruktur sesuai standar spesifikasi llms.txt.
        """
        lines = [
            f"# {self.project_name}",
            f"> {self.description}",
            ""
        ]

        for category, docs in self.sections.items():
            lines.append(f"## {category}")
            for doc in docs:
                lines.append(f"- [{doc['title']}]({doc['url']}): {doc['summary']}")
            lines.append("")

        return "\n".join(lines)
```

#### File: `main.py`
```python
"""
CLI Execution Orchestrator untuk DocOps.
"""
import sys
import glob
from core.extractor import MarkdownASTExtractor
from core.runner import PythonSandboxRunner
from core.agent_manifest import AgentManifestGenerator

def run_pipeline():
    extractor = MarkdownASTExtractor()
    runner = PythonSandboxRunner(timeout_seconds=10)
    manifest = AgentManifestGenerator(
        project_name="Autonomous Engine SDK",
        base_url="https://docs.agentic-enterprise.internal",
        description="Comprehensive developer platform documentation for AI Agents and Vector Orchestration."
    )

    markdown_files = glob.glob("tests/**/*.md", recursive=True)
    if not markdown_files:
        print("No markdown files detected.")
        sys.exit(0)

    total_snippets = 0
    failed_snippets = 0

    print("=== STARTING DOCUMENTATION CODE VERIFICATION ===")

    for doc_path in markdown_files:
        snippets = extractor.parse_file(doc_path)
        # Register ke manifest agent
        manifest.add_document(
            category="Core APIs",
            title=doc_path.replace(".md", "").capitalize(),
            relative_path=doc_path,
            summary="System operations, agent bootstrap sequence, and context handling."
        )

        for snippet in snippets:
            if snippet.language == "python":
                total_snippets += 1
                result = runner.execute(
                    snippet_file=snippet.file_path,
                    line_number=snippet.line_number,
                    code=snippet.code
                )

                if result.is_success:
                    print(f"[\033[92mPASS\033[0m] {result.snippet_file} (Line {result.line_number})")
                else:
                    failed_snippets += 1
                    print(f"[\033[91mFAIL\033[0m] {result.snippet_file} (Line {result.line_number})")
                    print(f"   Exit Code: {result.exit_code}")
                    print(f"   Error Log:\n{result.stderr}")

    print("\n=== GENERATING AGENT MANIFEST (llms.txt) ===")
    llms_txt_content = manifest.render_llms_txt()
    with open("llms.txt", "w", encoding="utf-8") as f:
        f.write(llms_txt_content)
    print("llms.txt successfully written to root directory.\n")

    print(f"Verification Summary: {total_snippets} total, {failed_snippets} failed.")
    if failed_snippets > 0:
        print("[\033[91mBUILD FAILED\033[0m] Documentation snippets broke runtime verification.")
        sys.exit(1)
    else:
        print("[\033[92mBUILD SUCCESS\033[0m] All code examples verified deterministically.")
        sys.exit(0)

if __name__ == "__main__":
    run_pipeline()
```

---

### 7. Edge Cases & Failure Modes

Berikut tabel mitigasi teknis untuk kegagalan validasi dokumentasi pada sistem enterprise:

| Failure Mode | Mekanisme Terjadinya | Mitigasi Arsitektur |
| :--- | :--- | :--- |
| **Snippet Dependency Interdependence** | Snippet 2 membutuhkan output variabel atau koneksi objek dari Snippet 1 di subbab yang sama. | Gunakan penanda state grouping AST: `fence python group="session_auth"`. Engine mengeksekusi snippet dalam container state yang sama secara sekuensial. |
| **Silent API Drift (Stochastic)** | SDK merubah tipe parameter (misal: `dict` menjadi `BaseModel`), namun kode masih lolos parsing sintaksis. | Wajibkan *static type checking* (`mypy` / `pyright`) dijalankan secara otomatis pada snippet sebelum sandbox runtime. |
| **Destructive Command Snippet** | Dokumen Bash memuat perintah destruktif seperti `rm -rf /data` atau `drop_database()`. | Enforce static AST security linting. Gunakan restricted system privileges (container rootless non-privileged) dan mock disk operations. |
| **Token Budget Overrun on Agents** | Dokumen tutorial terlalu panjang (>8000 token) sehingga gagal dimuat oleh autonomous agent context. | Validasi build time token counter: CI memunculkan peringatan jika sebuah file Markdown melebihi limit representasi token konteks (default: 4000 token). |

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan arsitektur dokumentasi membawa implikasi desain:

```
                  Documentation Execution Strategies
                
    [In-Process Mock Runner]  ◄───[Balance Point]───►  [Full-Stack Docker Sandbox]
    Fast (< 1s per snippet)                           Slow (> 30s per run)
    Low Infrastructure Cost                           High Compute Cost
    Limited Realism                                   100% Behavioral Realism
```

- **Alternative 1: In-Process Subprocess Runner + Mock (Solusi Terpilih)**
  - *Pros*: Waktu eksekusi sangat cepat, cocok untuk pull-request gating langsung di GitHub Actions tanpa instance runner berbayar tinggi.
  - *Cons*: Mocking mungkin tidak merefleksikan perubahan behavior server-side minor jika skema mock tidak disinkronisasikan otomatis dengan OpenAPI/Protobuf registry.

- **Alternative 2: Ephemeral Docker Compose Sandbox (Heavy Test)**
  - *Pros*: Menjalankan Redis/Postgres/Qdrant riil serta emulator LLM lokal (seperti Ollama).
  - *Cons*: Memperlambat feedback loop developer dari detik menjadi 10-15 menit per PR dokumentasi; meningkatkan biaya CI secara eksponensial.

- **Alternative 3: Static Assertion Only (Linting & AST only)**
  - *Pros*: Paling cepat, hanya memeriksa sintaks parsing tanpa eksekusi.
  - *Cons*: Gagal menangkap error kritis seperti pemanggilan metode yang telah dihapus (*method not found*), dependensi yang hilang, atau kegagalan konfigurasi runtime.

---

### 9. Best Practices & Standar Industri

1. **Strukturasi Konten Menggunakan Framework Diátaxis**:
   - **Tutorials**: Berorientasi pembelajaran (end-to-end), wajib executable secara deterministik.
   - **How-To Guides**: Berorientasi penyelesaian masalah operasional spesifik.
   - **Reference**: Deskripsi teknis API yang dihasilkan otomatis (*autogenerated*) langsung dari code annotations/docstrings.
   - **Explanation**: Konseptual, pemahaman arsitektur tingkat tinggi (minimalkan code block yang mudah usang).

2. **Semantic Compression untuk Agent Endpoints (`llms.txt`)**:
   - Jangan masukkan navigasi header, footer, cookie consent, atau elemen styling HTML.
   - Berikan definisi input-output type secara eksplisit pada setiap contoh API.
   - Definisikan batasan *rate limit*, *context token size*, dan *error code taxonomy* pada dokumen manifest.

3. **Versioning Parity**:
   - Terapkan Branching Documentation yang berkorelasi 1:1 dengan Major/Minor release core SDK (misalnya: branch docs `v1.2.x` menguji kode terhadap rilis SDK `v1.2.x`).

---

### 10. Hands-on Lab Exercise

#### Skenario:
Anda bertindak sebagai Principal DevRel Engineer di platform startup AI Agents. Tim engineering baru saja merilis SDK v2.0 yang menghapus argumen `temperature` dari constructor client dan memindahkannya ke dalam parameter method `generate()`. Dokumentasi saat ini mengalami *doc rot* dan membuat autonomous coding agent gagal mengintegrasikan SDK.

#### Task 1: Setup Environment
Buat struktur direktori dan file dokumen yang rusak:

```bash
mkdir -p docops-lab/tests docops-lab/core
cd docops-lab
pip install markdown-it-py
```

Buat file dokumentasi yang bermasalah di `tests/quickstart.md`:

```markdown
# Agent Quickstart

Welcome to the AI Agent SDK. Use this code to initialize your runner.

```python execute="true"
import sys

class AgentClient:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API Key must be provided.")
        self.api_key = api_key

    def generate(self, prompt: str, temperature: float = 0.7) -> str:
        return f"Response for: {prompt} with temp {temperature}"

# BUGGY CODE: Constructor does not accept temperature in v2.0!
client = AgentClient(api_key="demo-key", temperature=0.5)
print(client.generate(prompt="Hello World"))
```
```

#### Task 2: Implementasi & Eksekusi Pipeline
1. Salin kode arsitektur dari **Section 6** ke direktori masing-masing (`core/extractor.py`, `core/runner.py`, `core/agent_manifest.py`, dan `main.py`).
2. Jalankan pipeline DocOps:

```bash
python main.py
```

**Ekspektasi Output Terminal:**
```text
=== STARTING DOCUMENTATION CODE VERIFICATION ===
[FAIL] tests/quickstart.md (Line 7)
   Exit Code: 1
   Error Log:
TypeError: AgentClient.__init__() got an unexpected keyword argument 'temperature'

=== GENERATING AGENT MANIFEST (llms.txt) ===
llms.txt successfully written to root directory.

Verification Summary: 1 total, 1 failed.
[BUILD FAILED] Documentation snippets broke runtime verification.
```

#### Task 3: Remediasi Dokumentasi
Buka `tests/quickstart.md` dan perbaiki blok kode agar sesuai dengan kontrak arsitektur:

```markdown
```python execute="true"
import sys

class AgentClient:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API Key must be provided.")
        self.api_key = api_key

    def generate(self, prompt: str, temperature: float = 0.7) -> str:
        return f"Response for: {prompt} with temp {temperature}"

# FIXED: Temperature correctly configured inside the generate call
client = AgentClient(api_key="demo-key")
print(client.generate(prompt="Hello World", temperature=0.5))
```
```

Jalankan kembali pipeline:
```bash
python main.py
```

**Ekspektasi Output Akhir:**
```text
=== STARTING DOCUMENTATION CODE VERIFICATION ===
[PASS] tests/quickstart.md (Line 7)

=== GENERATING AGENT MANIFEST (llms.txt) ===
llms.txt successfully written to root directory.

Verification Summary: 1 total, 0 failed.
[BUILD SUCCESS] All code examples verified deterministically.
```

Periksa file `llms.txt` yang dihasilkan:
```bash
cat llms.txt
```
Pastikan link kanonikal dan struktur markdown terkompilasi dengan bersih, siap dikonsumsi oleh autonomous agent context pipelines.