# BAB 01 - Fondasi dan Arsitektur
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi: Autonomous Technical Writer Agent

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik enterprise diharapkan mampu:
1. **Menganalisis dan Merancang** arsitektur *Autonomous Technical Writer Agent* berbasis multi-agent/tool-use yang mengintegrasikan *Abstract Syntax Tree* (AST) parser, Git diff engine, dan *Context-Aware Retrieval-Augmented Generation* (RAG).
2. **Mengimplementasikan** pipeline otomatisasi dokumentasi berbasis *Docs-as-Code* yang memvalidasi kebenaran kode (*code-to-doc consistency*), mendeteksi *semantic drift*, dan menghasilkan Markdown/OpenAPI/ADR secara deterministik.
3. **Mengoperasikan** sistem *continuous documentation* pada skala enterprise dengan mekanisme *guardrails*, mitigasi halusinasi teknis, linting semantik, dan integrasi CI/CD GitOps.
4. **Mengevaluasi trade-off** antara latensi inferensi, konsumsi token LLM, akurasi faktual, dan biaya komputasi pada pemrosesan monorepo berskala jutaan baris kode (LoC).

---

### 2. Prerequisite
Untuk mengikuti modul ini secara optimal, peserta wajib memahami:
*   **Python 3.11+ Core**: Asyncio, static typing (`mypy`), Pydantic V2, metaprogramming.
*   **Software Engineering Principles**: Abstract Syntax Trees (AST), Git internals (tree objects, diff hunk parsing), OpenAPI 3.x spec, Markdown AST.
*   **Agentic Frameworks & LLM Patterns**: Tool calling/Function calling, Structured Outputs (JSON Schema enforcement), Semantic Search & Vector Embeddings.
*   **DevOps/GitOps**: GitHub Actions/GitLab CI, pre-commit hooks, Docker containerization.

---

### 3. Concept & Internal Architecture (Mendalam)

Sistem dokumentasi tradisional sering kali mengalami *documentation rot* (kondisi di mana dokumentasi tertinggal dari implementasi kode aktual). *Autonomous Technical Writer Agent* bukan sekadar skrip pembungkus prompt LLM sederhana, melainkan sistem rekayasa perangkat lunak otonom yang memadukan komputasi deterministik (AST parsing, compiler symbol analysis) dengan pemodelan probabilistik (LLM-based context synthesis).

```
+---------------------------------------------------------------------------------------+
|                       Autonomous Technical Writer Core Engine                         |
+---------------------------------------------------------------------------------------+
|  [Ingestion Engine]                                                                   |
|   +-------------------+    +--------------------+    +-----------------------------+  |
|   | Git Diff / Hunks  |    | Tree-sitter Parser |    | Symbol Resolution Table     |  |
|   +---------+---------+    +---------+----------+    +--------------+--------------+  |
|             |                        |                              |                 |
|             +------------------------+------------------------------+                 |
|                                      |                                                |
|                                      v                                                |
|  [Context Aggregation & Graph Construction]                                           |
|   +--------------------------------------------------------------------------------+  |
|   | Code-Doc Semantic Dependency Graph (Call Graph, Type Defs, Test Assertions)   |  |
|   +----------------------------------+---------------------------------------------+  |
|                                      |                                                |
|                                      v                                                |
|  [Agentic Reasoning & Synthesis Loop]                                                 |
|   +-------------------+    +--------------------+    +-----------------------------+  |
|   | Planner Agent     |--->| Writer Agent       |--->| Critic / Verifier Agent     |  |
|   | (Impact Analysis) |    | (Markdown Synth)   |    | (AST & Type Check against   |  |
|   +-------------------+    +--------------------+    |  generated code snippets)   |  |
|                                      ^               +--------------+--------------+  |
|                                      |                              |                 |
|                                      +--- [Correction Feedback] ----+ (Loop if invalid)|
|                                                                     |                 |
|                                                                     v (Pass)          |
|  [Deterministic Gatekeeper]                                                           |
|   +--------------------------------------------------------------------------------+  |
|   | Vale Linter (Prose) + Markdownlint + Link Verification + OpenAPI Schema Validator|
|   +----------------------------------+---------------------------------------------+  |
|                                      |                                                |
|                                      v                                                |
|  [GitOps Delivery Engine]                                                             |
|   +--------------------------------------------------------------------------------+  |
|   | Git Tree Mutation -> Automated Pull Request / Branch Injection                 |  |
|   +--------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------+
```

#### Komponen Arsitektur Inti:
1. **Structural AST Extraction (Tree-sitter)**: Mengurai source code menjadi AST node tanpa mengeksekusi kode. Menangkap perubahan tanda tangan fungsi, mutasi tipe data, docstrings usang, dan anotasi dependensi secara deterministik.
2. **Context Resolution Graph**: Mengaitkan potongan kode (*code hunks*) dengan konteks yang lebih luas: unit test terkait, implementasi interface, callers/callees, dan dokumentasi yang telah ada di repositori.
3. **Multi-Agent Deliberation Network**:
   *   **Planner/Diff Analyzer**: Menentukan file dokumentasi mana (API references, guides, architecture diagrams, runbooks) yang terdampak oleh pull request.
   *   **Technical Scribe (Writer)**: Menghasilkan pembaruan dokumentasi berbasis *structured schema* yang ditentukan secara ketat.
   *   **Code-Doc Compiler & Validator (Critic)**: Memeriksa apakah snippet kode yang dihasilkan dalam dokumentasi valid secara sintaksis dan dapat dieksekusi (*doctest assertion*).
4. **Deterministic Validation Boundary**: Memastikan teks hasil generasi tunduk pada aturan enterprise (gaya bahasa, inklusivitas istilah, validitas referensi link) menggunakan linter non-LLM (`vale`, `markdownlint`) sebelum menyentuh repositori.

---

### 4. Why & What

| Dimensi | Dokumentasi Manual Tradisional | Pendekatan LLM Naif (Zero-shot Copypaste) | Autonomous Technical Writer Agent |
| :--- | :--- | :--- | :--- |
| **Keandalan Faktual** | Tinggi (selama manusia teliti), namun rentan *human error*. | Rendah. Rawan halusinasi parameter dan dependensi phantom. | Deterministik. Mengunci tipe data via AST dan runtime/unit-test assertions. |
| **Sinkronisasi (Freshness)** | Lambat. Dokumentasi sering tertinggal beberapa sprint. | Manual. Bergantung pada engineer yang ingat menjalankan prompt. | Real-time. Terintegrasi ke CI/CD pipeline setiap terjadi merge/PR. |
| **Skalabilitas** | Buruk. Memerlukan puluhan technical writer untuk ribuan microservices. | Terbatas oleh konteks window dan format keluaran yang tidak konsisten. | Sangat Tinggi. Mampu memproses jutaan diff secara asinkronus dan otomatis. |
| **Standardisasi Gaya** | Memerlukan manual peer review yang melelahkan. | Acak-acakan; output berubah-ubah setiap run. | Konsisten. Dipagari Style Guide Engine (Vale) dan Pydantic contracts. |

---

### 5. How (Workflow Detail)

Alur kerja autonomous documentation engine diatur dalam langkah-langkah presisi berikut:

```
[Git Commit/PR] 
      │
      ▼
(Step 1: Ingestion) ──────► Parse Git Diff, Ekstrak AST via Tree-sitter
      │
      ▼
(Step 2: Impact Analysis) ─► Petakan node AST yang berubah ke Document Dependency Graph
      │
      ▼
(Step 3: RAG Retrieval) ──► Ambil kontekstualisasi: Existing Docs, Interface, Unit Tests
      │
      ▼
(Step 4: Generation Loop) ─► Writer LLM membuat draf patch dokumen (Markdown/OpenAPI)
      │
      ▼
(Step 5: Code Verification)► Critic mengekstrak codeblock dokumen -> AST syntax parse
      │                      │
      │ (Gagal)              ▼ (Sukses)
      └────────── Refine ─── (Step 6: Prose Linting) ──► Vale CLI / Formatting checks
                                    │
                                    ▼ (Sukses)
                             (Step 7: Delivery) ──────► Commit patch / Buka PR otomatis
```

1. **Ingestion & AST Tokenization**: CI webhook memicu pipeline pada commit baru. Git diff dianalisis; hanya node bahasa (misal: Python, TypeScript, Go) yang diurai melalui *Tree-sitter* untuk mendeteksi perubahan semantik (bukan sekadar whitespace).
2. **Impact Graph Mapping**: Sistem menentukan dokumen mana yang terdampak. Jika `OrderService.checkout()` berubah tanda tangan parameternya, sistem menandai `docs/api/checkout.md` dan `docs/tutorials/quickstart.md`.
3. **Retrieval of Surrounding Context**: System RAG berbasis hybrid search (BM25 + Dense Vector) mengambil unit test terkait dan docstring lama untuk memberikan *grounding context* kepada LLM.
4. **Agentic Generation with Strict Contracts**: Writer Agent mengeksekusi generasi teks terstruktur berbasis schema Pydantic, menghasilkan representasi Unified Diff format untuk file Markdown target.
5. **Static Code Block Verification**: Dokumen yang dihasilkan diekstrak blok kodenya. Tool critic memvalidasi bahwa blok kode dalam docstring/markdown valid secara sintaksis dan parameter yang digunakan sesuai dengan signature fungsi pada kode sumber baru.
6. **Linter & Style Boundary Execution**: Eksekusi CLI tool non-AI (Vale, markdownlint) terhadap markdown yang dihasilkan untuk memastikan voice, tone, dan formatting compliant.
7. **GitOps Ingestion**: Dokumen yang telah divalidasi dikomit langsung ke PR branch atau dibuatkan PR baru via GitHub API dengan label `automated-docs`.

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
Bayangkan sebuah **Ruang Sidang Redaksi Surat Kabar Modern**:
*   **Git Diff & AST Parser** adalah *Reporter Investigasi*: Mereka hanya membawa fakta mentah dan bukti fisik ("Fungsi `calculate_tax` bertambah parameter `country_code: str`").
*   **Context Graph / RAG** adalah *Arsiparis*: Mengambil dokumen lama, kliping koran lama, dan aturan hukum terkait topik tersebut.
*   **Writer Agent** adalah *Jurnalis*: Menulis draf berita yang mudah dipahami, runut, dan teknis berdasarkan bukti dari Reporter dan Arsiparis.
*   **Critic Agent** adalah *Fakta-Checker*: Menguji ulang setiap klaim dan kutipan; jika jurnalis menulis contoh kode yang salah ketik, naskah dikembalikan ke meja jurnalis.
*   **Vale / Formatter Linter** adalah *Korektor Bahasa & Percetakan*: Memastikan ejaan, tanda baca, dan tata letak cetak telah sesuai standar koran sebelum masuk mesin cetak (*Git Repo*).

#### Architectural Interaction Diagram

```
+------------------------------------------------------------------------------------+
|                                PULL REQUEST / COMMIT                               |
+------------------------------------------------------------------------------------+
                                          │
                                          ▼
                      +---------------------------------------+
                      |         GitDiffASTExtractor           |
                      |  (Tree-sitter Python/TS C-Bindings)   |
                      +---------------------------------------+
                                          │
                  [Structured AST Deltas & Symbol Changes]
                                          │
                                          ▼
                      +---------------------------------------+
                      |       Context Graph Resolution        |
                      | (Retrieves: Tests, Interfaces, Usages)|
                      +---------------------------------------+
                                          │
                         [Rich Context Payload (JSON)]
                                          │
                                          ▼
                      +---------------------------------------+
                      |       Planner Agent (LLM Core)        |
                      | - Identifikasi Dokumen Terdampak      |
                      | - Rencana Mutasi Dokumen              |
                      +---------------------------------------+
                                          │
                              [Documentation Action Plan]
                                          │
                                          ▼
+------------------------------------------------------------------------------------+
|                         REACTIVE AGENT GENERATION LOOP                             |
|                                                                                    |
|      +----------------------------------------------------------------------+      |
|      |                        Writer Agent (LLM)                            |      |
|      |            Menghasilkan Markdown Patch / API Specification           |      |
|      +----------------------------------------------------------------------+      |
|                                         │                                          |
|                                  [Draft Markdown]                                  |
|                                         │                                          |
|                                         ▼                                          |
|      +----------------------------------------------------------------------+      |
|      |                   Critic Agent (Deterministic Tester)                |      |
|      | - Ekstraksi ```python blocks -> PyAST Validation                     |      |
|      | - Memastikan parameter cocok 1:1 dengan Ingestion Engine             |      |
|      +----------------------------------------------------------------------+      |
|                      │                                      │                      |
|                  [INVALID]                              [VALID]                    |
|                      │                                      │                      |
|                      └─── (Kirim Error Diagnostics) ────────┘                      |
+------------------------------------------------------------------------------------+
                                          │
                                    [Clean Patch]
                                          │
                                          ▼
                      +---------------------------------------+
                      |      Deterministic Style Gateways     |
                      |   - Vale (Prose & Syntax Linting)     |
                      |   - Link Checker (Dead URLs)          |
                      +---------------------------------------+
                                          │
                                       [PASS]
                                          │
                                          ▼
                      +---------------------------------------+
                      |           GitOps Deployer             |
                      |  - GitHub API / PR Generation         |
                      |  - Direct Branch Commit               |
                      +---------------------------------------+
```

---

### 7. Simple Example & Practical Example (Standar Industri)

#### A. Simple Example: AST Function Signature Delta Parser
Contoh dasar parsing AST Python secara deterministik untuk menangkap perbedaan signature yang harus dipublikasikan ke docstring/markdown.

```python
# simple_ast_extractor.py
import ast
from typing import Dict, Any

def extract_signatures(code_content: str) -> Dict[str, Dict[str, Any]]:
    """Mengekstrak tanda tangan fungsi dari kode Python menggunakan AST bawaan."""
    tree = ast.parse(code_content)
    signatures = {}
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            args = [arg.arg for arg in node.args.args]
            returns = ast.unparse(node.returns) if node.returns else "None"
            signatures[node.name] = {
                "args": args,
                "returns": returns,
                "docstring": ast.get_docstring(node)
            }
    return signatures

if __name__ == "__main__":
    code = """
def calculate_vat(amount: float, rate: float = 0.11) -> float:
    '''Hitung PPN dari jumlah transaksi.'''
    return amount * rate
"""
    result = extract_signatures(code)
    print("Parsed Metadata:", result)
```

#### B. Practical Enterprise Example: Autonomous Documentation Pipeline
Implementasi end-to-end dengan Pydantic V2, OpenAI Structured Outputs, tree validation, dan deterministic mock feedback loop.

```python
# autonomous_doc_writer.py
from __future__ import annotations
import ast
import json
import os
import sys
from typing import List, Optional
from pydantic import BaseModel, Field

# Mocking external LLM Client via interface contract
class LLMMessage(BaseModel):
    role: str
    content: str

class DocumentationPatch(BaseModel):
    target_file: str = Field(description="Path relatif file dokumentasi yang diubah")
    patch_summary: str = Field(description="Ringkasan pembaruan dokumentasi")
    updated_markdown: str = Field(description="Konten Markdown utuh yang telah diperbarui")
    generated_code_examples: List[str] = Field(description="Daftar blok kode yang disertakan dalam Markdown")

class ASTCriticReport(BaseModel):
    is_valid: bool
    errors: List[str] = Field(default_factory=list)

class CriticEngine:
    """Mesin deterministik penjamin kebenaran kode pada dokumentasi."""
    
    @staticmethod
    def validate_python_snippets(snippets: List[str]) -> ASTCriticReport:
        errors = []
        for idx, snippet in enumerate(snippets):
            clean_snippet = snippet.strip()
            if clean_snippet.startswith("```python"):
                clean_snippet = clean_snippet.removeprefix("```python")
            if clean_snippet.endswith("```"):
                clean_snippet = clean_snippet.removesuffix("```")
            
            try:
                ast.parse(clean_snippet)
            except SyntaxError as e:
                errors.append(f"Snippet #{idx+1} SyntaxError: {str(e)} -> Kode:\n{clean_snippet}")
                
        return ASTCriticReport(is_valid=len(errors) == 0, errors=errors)

class MockLLMProvider:
    """Simulasi pemanggilan model LLM mutakhir dengan determinisme terstruktur."""
    
    @staticmethod
    def generate_documentation_patch(
        diff: str, 
        context: str, 
        critique_feedback: Optional[str] = None
    ) -> DocumentationPatch:
        # Simulasi output LLM terstruktur
        if critique_feedback:
            # Perbaikan jika ada feedback dari critic engine
            corrected_example = "def run():\n    service = PaymentService()\n    return service.pay(amount=100.0, currency='IDR')"
        else:
            # Contoh cacat sintaksis sengaja untuk menguji critic loop
            corrected_example = "def run():\n    service = PaymentService(\n    return service.pay(100.0"

        return DocumentationPatch(
            target_file="docs/api/payment.md",
            patch_summary="Update signature for PaymentService.pay method with currency support.",
            updated_markdown=f"""# Payment Service Documentation

Update terbaru mendukung multi-currency.

### Contoh Penggunaan:
```python
{corrected_example}
```
""",
            generated_code_examples=[f"```python\n{corrected_example}\n```"]
        )

class AutonomousTechnicalWriter:
    def __init__(self, max_refinement_loops: int = 3):
        self.critic = CriticEngine()
        self.max_loops = max_refinement_loops

    def process_change(self, code_diff: str, context: str) -> DocumentationPatch:
        feedback: Optional[str] = None
        
        for iteration in range(self.max_loops):
            print(f"[Agent] Menjalankan sintesis dokumentasi (Iterasi {iteration + 1})...")
            draft = MockLLMProvider.generate_documentation_patch(code_diff, context, feedback)
            
            # Critic phase
            print("[Critic] Memvalidasi kebenaran sintaksis contoh kode dokumentasi...")
            report = self.critic.validate_python_snippets(draft.generated_code_examples)
            
            if report.is_valid:
                print("[Critic] Validasi AST lolos secara deterministik.")
                return draft
            
            print(f"[Critic] Validasi gagal! Menemukan {len(report.errors)} kesalahan. Mengembalikan ke agen...")
            feedback = "\n".join(report.errors)
        
        raise RuntimeError("Autonomous Technical Writer gagal mencapai konvergensi sintaksis yang valid.")

if __name__ == "__main__":
    diff_input = """
--- a/services/payment.py
+++ b/services/payment.py
@@ -10,3 +10,3 @@ class PaymentService:
-    def pay(self, amount: float):
+    def pay(self, amount: float, currency: str = 'USD'):
    """
    context_data = "PaymentService menangani gateway pembayaran internal."
    
    orchestrator = AutonomousTechnicalWriter(max_refinement_loops=3)
    final_patch = orchestrator.process_change(diff_input, context_data)
    
    print("\n================ FINAL VERIFIED DOCUMENTATION ================")
    print(f"Target File: {final_patch.target_file}")
    print(f"Summary    : {final_patch.patch_summary}")
    print(f"Markdown Content:\n{final_patch.updated_markdown}")
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks & Skala:
*   **Perusahaan**: Global Fintech Decacorn.
*   **Arsitektur**: Monorepo terdistribusi dengan 650+ Microservices (Go, Python, TypeScript).
*   **Volume**: ~1.200 Pull Request per hari dengan 450 pengembang aktif.
*   **Masalah Utama**: API drift merajalela. Tanda tangan gRPC dan REST endpoints dimutasi tanpa memperbarui Swagger/OpenAPI docs dan Portal Pengembang internal. Akibatnya, tim integrasi front-end dan mitra pihak ketiga mengalami rata-rata 38 *breaking change incidents* per kuartal.

#### Solusi Implementasi:
Sistem mendesain ulang CI/CD dengan menyematkan **Agentic Documentation Gatekeeper**:
1. **GitHub Action Runner Step**:
   *   Menggunakan `tree-sitter-cli` untuk mengekstrak mutasi struct Go dan Pydantic models.
   *   Jika diff mengandung perubahan model tanpa perubahan dokumentasi pendamping di direktori `docs/`, *Workflow* menahan status check PR dan mendelegasikan tugas ke autonomous writer cluster.
2. **Cluster Worker (Celery + Redis + Claude 3.5 Sonnet / GPT-4o)**:
   *   Worker membaca schema proto/Go AST diff.
   *   Mengambil OpenAPI spec lama dan menghasilkan pull request branch baru berupa file `.diff` dokumentasi langsung ke PR developer.
   *   Dokumentasi diverifikasi menggunakan linter internal: `spectral lint` untuk OpenAPI dan `vale` untuk panduan teks.
3. **Hasil & Metrik Produksi**:
   *   **Incident Reduction**: Insiden breaking-change integrasi turun 89% dalam 6 bulan.
   *   **Time-to-Doc**: Waktu yang dihabiskan engineer menulis boilerplate documentation berkurang dari ~4 jam/minggu per insinyur menjadi 0 (hanya review hasil automasi).
   *   **Coverage**: Dokumentasi API sinkron 99,8% terhadap production release artifacts.

---

### 9. Trade-offs

| Parameter Desain | Pilihan A: Deterministic AST Only | Pilihan B: Pure Generative LLM | Pilihan C: Hybrid Agentic + AST Guardrail (Rekomendasi) |
| :--- | :--- | :--- | :--- |
| **Akurasi Kode** | 100% (Kompiler tidak berbohong) | 65% - 85% (Rentan halusinasi nama method/argumen) | 99.5% (LLM mensintesis penjelasan, AST memverifikasi) |
| **Kualitas Narasi & Konteks** | Sangat Rendah (Hanya listing schema/tanda tangan mekanis) | Sangat Tinggi (Bahasa manusia natural, analogi jelas) | Tinggi & Terstruktur (Bahasa luwes dengan struktur baku) |
| **Latensi Pipeline** | < 1 detik | 5 - 15 detik | 10 - 45 detik (Tergantung loop verifikasi kritik) |
| **Biaya Token / Operasional** | $0 (Lokal CPU compute) | Tinggi ($$$ per commit/PR) | Terukur (Penyaringan diff berbasis AST sebelum panggil LLM) |
| **Toleransi Kompleksitas** | Sulit merangkum relasi inter-service | Mudah merangkum dependensi konseptual | Memerlukan Context Graph untuk menyeimbangkan token |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Ingestion Context Window Explosion
*   **Gejala**: Out-of-memory (OOM) atau error token limit LLM saat memproses PR berskala masif (misal: refactoring ribuan file).
*   **Akar Masalah**: Memasukkan raw `git diff` monorepo langsung ke prompt tanpa chunking atau filtering file non-dokumenter (lockfiles, generated code).
*   **Solusi**: Terapkan filter ketat sebelum konsumsi agent:
    ```bash
    git diff --name-only | grep -E '\.(py|ts|go|rs)$' | grep -v '_test'
    ```
    Hanya parsing semantic AST symbol changes, buang whitespace dan komentar formatting.

#### 2. Infinite PR Generation Loop
*   **Gejala**: Agent membuat PR update dokumen -> CI berjalan pada branch dokumen -> Agent mendeteksi perubahan -> Agent mencoba mendokumentasikan dokumen -> Infinite loop.
*   **Akar Masalah**: Kurangnya ignorasi metadata commit bot.
*   **Solusi**: Pasang guard rail pada CI webhook:
    ```yaml
    if: "!contains(github.event.head_commit.author.name, '[bot]')"
    ```

#### 3. Hallucinated Imports in Documentation Code Blocks
*   **Gejala**: Developer menyalin contoh kode dari dokumentasi, namun kode gagal dijalankan karena modul fiktif.
*   **Akar Masalah**: Temperature model terlalu tinggi (> 0.2) saat mode penulisan teknis atau prompt tidak melampirkan context import map.
*   **Solusi**:
    *   Set LLM `temperature=0.0`.
    *   Critic agent harus memvalidasi import symbol terhadap `sys.modules` atau `pyproject.toml` menggunakan AST validation.

---

### 11. Best Practices (Production Checklist)

- [ ] **Deterministic AST Pre-filtering**: Jangan panggil LLM jika perubahan kode hanya berupa whitespace, optimasi baris internal privat, atau mutasi variabel lokal tanpa perubahan API signature.
- [ ] **Strict Typing via Schemas**: Terapkan Pydantic V2 / JSON Schema Structured Outputs pada setiap interaksi LLM untuk memastikan payload dokumentasi dapat diparsing mesin.
- [ ] **Sandboxed Snippet Parsing**: Setiap blok kode yang dihasilkan dalam draf Markdown wajib diparsing oleh parser bahasa target (misal: `ast.parse` untuk Python, `tsc --noEmit` untuk TypeScript) sebelum diizinkan merge.
- [ ] **Style Linters in Loop**: Gunakan tool deterministik seperti `Vale` (untuk prose grammar & branding), `markdownlint` (untuk struktur Heading), dan `Spectra` (untuk OpenAPI) sebagai quality gate non-AI.
- [ ] **Semantic Diff Generation**: Tulis output dalam bentuk patch yang presisi atau target file update, jangan me-rewrite seluruh dokumen monolitik untuk meminimalisasi merge conflict.
- [ ] **Telemetry & Tracing**: Pasang OpenTelemetry tracing pada setiap agent call untuk memantau token usage, latency critic-loop, dan rasio rejection rate validator.

---

### 12. Hands-on Practice

Buat dan operasikan project autonomous doc-writer mini pada lingkungan lokal Anda. Ikuti tahapan terstruktur berikut:

#### Task 1: Setup Workspace & Dependencies
Simpan seluruh file di direktori: `hands-on/m02/`

```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
python3 -m venv venv
source venv/bin/activate
pip install pydantic==2.6.4 tree-sitter==0.21.3 tree-sitter-languages==1.10.2
```

#### Task 2: Implementasi Deterministic Python AST Extractor
Simpan kode berikut sebagai `hands-on/m02/ast_extractor.py`:

```python
import ast
from typing import Dict, Any

class CodeAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.stats: Dict[str, Any] = {"classes": {}, "functions": {}}

    def visit_ClassDef(self, node: ast.ClassDef):
        class_methods = {}
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                class_methods[item.name] = {
                    "args": [arg.arg for arg in item.args.args if arg.arg != "self"],
                    "docstring": ast.get_docstring(item)
                }
        self.stats["classes"][node.name] = {
            "methods": class_methods,
            "docstring": ast.get_docstring(node)
        }
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Top-level functions only
        if isinstance(getattr(node, 'parent', None), ast.Module):
            self.stats["functions"][node.name] = {
                "args": [arg.arg for arg in node.args.args],
                "docstring": ast.get_docstring(node)
            }
        self.generic_visit(node)

def analyze_codebase(source_code: str) -> Dict[str, Any]:
    tree = ast.parse(source_code)
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node  # inject parent reference
    analyzer = CodeAnalyzer()
    analyzer.visit(tree)
    return self_clean(analyzer.stats)

def self_clean(data):
    return json.loads(json.dumps(data))

if __name__ == "__main__":
    import json
    sample_code = """
class BillingRouter:
    '''Routing transaksi penagihan enterprise.'''
    def route_payment(self, invoice_id: str, provider: str = 'stripe') -> bool:
        '''Proses pembayaran invoice dengan provider tertentu.'''
        return True
"""
    print(json.dumps(analyze_codebase(sample_code), indent=2))
```

#### Task 3: Eksekusi dan Verifikasi
Jalankan skrip ekstraksi:
```bash
python hands-on/m02/ast_extractor.py
```
Pastikan keluaran JSON menangkap parameter `invoice_id` dan `provider` secara sempurna.

---

### 13. Exercise

#### Level 1 - Easy
Modifikasi skrip `hands-on/m02/ast_extractor.py` agar mampu mengekstrak tipe kembalian (*return type annotations*) dari setiap method/fungsi, dan menampilkannya pada output JSON.

#### Level 2 - Medium
Bangun script `hands-on/m02/markdown_validator.py` yang menggunakan regular expression atau parser markdown untuk mengekstrak seluruh blok kode ` ```python ... ``` ` dari sebuah file markdown, lalu validasi sintaksisnya menggunakan `ast.parse()`. Jika ada kesalahan sintaksis, laporkan nomor baris dari file markdown tersebut.

#### Level 3 - Hard
Rancang pipeline mini `hands-on/m02/pipeline.py` yang:
1. Menerima input dua string: `old_code` dan `new_code`.
2. Menggunakan modul `difflib` untuk membuat patch diff.
3. Menggunakan AST extractor untuk mendeteksi perubahan parameter.
4. Menjalankan LLM agent mock yang secara otomatis memutakhirkan contoh Markdown dan memastikan blok kode yang dihasilkan 100% valid secara sintaksis lewat loop validator.

---

### 14. Challenge

**Skenario**: Anda adalah Staff AI Platform Engineer pada platform open-source banking engine. Repositori memiliki 10.000 file Python dengan integrasi FastAPI.
**Problem**: Pengembang sering mengubah metadata schema Pydantic (misal: menambahkan constraint `Field(gt=0, le=100)`) dan response status codes pada decorator route `@app.post(...)`, namun dokumentasi manual di direktori `/docs/api/v2` tidak pernah disinkronkan.

**Objektif Tantangan**:
Rancang dan bangun arsitektur sistem autonomus lengkap (Python script modular) yang mampu:
1. Mengidentifikasi seluruh endpoint FastAPI dari parsing AST tanpa menjalankan runtime server (`uvicorn`).
2. Menghasilkan spesifikasi OpenAPI 3.1 valid (JSON/YAML) murni dari kompilasi AST + docstring semantik.
3. Menguji *backward-compatibility* skema baru terhadap dokumen lama: jika ada field wajib yang dihapus, agen **WAJIB** menolak menghasilkan dokumen dan mengembalikan *breaking-change alert* dengan penjelasan teknis mendalam.
4. Mengimplementasikan Critic Agent yang memverifikasi bahwa contoh cURL command yang disertakan dalam dokumentasi memiliki field JSON yang persis dengan schema model Pydantic yang bersangkutan.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Apa peran utama *Tree-sitter* atau *AST Parser* dalam arsitektur Autonomous Technical Writer?
   * A. Membuat antarmuka pengguna grafis untuk membaca dokumen.
   * B. Mengurai kode secara deterministik ke dalam node sintaksis tanpa perlu mengeksekusi kode tersebut.
   * C. Menghitung jumlah kata dalam dokumen Markdown.
   * D. Menjalankan model machine learning berbasis PyTorch.
   *(Jawaban yang benar: B)*

2. Mengapa pendekatan zero-shot LLM tanpa guardrail dilarang untuk pembuatan dokumentasi API enterprise?
   * A. Karena LLM tidak mendukung teks Markdown.
   * B. LLM terlalu lambat untuk membaca string diff.
   * C. Risiko tinggi terjadinya halusinasi nama method, argumen fiktif, dan tipe data yang tidak valid.
   * D. LLM hanya bisa membaca bahasa Inggris.
   *(Jawaban yang benar: C)*

3. Pada format Git diff, baris yang diawali dengan tanda `+` menandakan:
   * A. Baris kode yang dihapus dari commit sebelumnya.
   * B. Baris komentar yang diabaikan compiler.
   * C. Baris kode baru yang ditambahkan ke repositori.
   * D. Error fatal dalam repository index.
   *(Jawaban yang benar: C)*

4. Tool deterministik non-LLM yang umum digunakan dalam pipeline produksi untuk menegakkan prose style guide dan terminologi korporat adalah:
   * A. Vale
   * B. Webpack
   * C. Memcached
   * D. Gunicorn
   *(Jawaban yang benar: A)*

5. Konsep "Docs-as-Code" berarti:
   * A. Menulis seluruh kode program di dalam file `.txt`.
   * B. Menyimpan, mengelola, me-review, dan merilis dokumentasi dengan workflow, tool, dan version control yang sama dengan source code.
   * C. Mengompilasi dokumentasi menjadi file binary `.exe`.
   * D. Mengizinkan AI menulis kode program tanpa pengawasan manusia.
   *(Jawaban yang benar: B)*

---

#### Bagian 2: Intermediate (Pilihan Ganda & Analisis Arsitektur)
6. Manakah langkah yang paling efektif untuk mencegah terjadinya *infinite loop* PR dokumentasi pada CI/CD?
   * A. Menghapus tool CI/CD dari sistem repositori.
   * B. Menambahkan aturan filter commit author untuk mengabaikan commit dari identitas bot dokumentasi.
   * C. Menjalankan agent hanya pada hari libur.
   * D. Membatasi ukuran file markdown maksimal 5 baris.
   *(Jawaban yang benar: B)*

7. Dalam arsitektur Multi-Agent Technical Writer, apa tanggung jawab utama dari *Critic Agent*?
   * A. Melakukan negosiasi harga API token dengan penyedia LLM.
   * B. Memverifikasi draf dokumentasi terhadap aturan deterministik, memeriksa validitas sintaks kode contoh, dan memberi umpan balik revisi ke Writer Agent.
   * C. Menghapus dokumentasi lama yang tidak dibaca user.
   * D. Menulis ulang seluruh backend logic sistem.
   *(Jawaban yang benar: B)*

8. Mengapa temperature LLM harus disetel ke nilai mendekati `0.0` pada agent dokumentasi teknis?
   * A. Agar model menghasilkan bahasa yang puitis dan kreatif.
   * B. Untuk meminimalkan keacakan (stochasticity) dan memaksimalkan reproduktibilitas output serta kepatuhan skema faktual.
   * C. Untuk menurunkan konsumsi daya kartu grafis (GPU) sebesar 90%.
   * D. Agar model dapat menghasilkan output lebih panjang tanpa batas.
   *(Jawaban yang benar: B)*

9. Jika sebuah PR mengubah 2.000 file akibat perubahan lisensi copyright, bagaimana Ingestion Engine harus bereaksi?
   * A. Mengirimkan seluruh 2.000 file diff ke context window LLM.
   * B. Mematikan server CI secara paksa.
   * C. Melakukan AST/Semantic hashing filter untuk mendeteksi bahwa tidak ada node fungsional/simbol yang berubah, lalu membatalkan proses dokumentasi tanpa memanggil LLM.
   * D. Membuat 2.000 file dokumentasi baru secara terpisah.
   *(Jawaban yang benar: C)*

10. Apa kelemahan utama mengandalkan regex sederhana dibandingkan AST parser dalam menganalisis signature fungsi pada codebase modern?
    * A. Regex membutuhkan lisensi berbayar enterprise.
    * B. Regex rapuh terhadap multi-line arguments, decorators, type hints yang kompleks, dan komentar di dalam signature.
    * C. Regex tidak bisa dijalankan di sistem operasi Linux.
    * D. Regex mengeksekusi kode berbahaya secara otomatis.
    *(Jawaban yang benar: B)*

---

#### Bagian 3: Skenario Kasus Produksi

11. **Skenario Kasus 1**:
    Tim Core Platform melaporkan bahwa Autonomous Technical Writer Agent Anda secara berkala menghasilkan contoh kode Python di dalam file Markdown yang memiliki syntax invalid (misal: unclosed parentheses atau argumen yang tertinggal). 
    *Pertanyaan*: Rancang strategi arsitektural multi-layer untuk mengeliminasi insiden ini sebelum pull request dibuat oleh agen!
    *Kunci Jawaban Solusi Enterprise*:
    *   Terapkan *Deterministic Code Extraction Guardrail*: Pasang layer interceptor yang membaca regex/AST Markdown blocks, mengisolasi semua blok ` ```python `, dan mengalirkannya ke `ast.parse()`.
    *   Terapkan *Feedback Iteration Loop*: Jika `ast.parse()` melempar exception `SyntaxError`, serahkan traceback error tersebut kembali ke LLM sebagai instruksi koreksi otomatis (Critic Loop).
    *   Terapkan *Strict Fallback*: Jika setelah 3 kali iterasi snippet kode tetap tidak valid, batalkan pembuatan PR dan kirim alert ke telemetry system (Slack/PagerDuty) alih-alih merilis dokumen cacat.

12. **Skenario Kasus 2**:
    Pada sebuah monorepo skala besar, biaya token OpenAI melonjak tajam ($15,000/bulan) akibat pipeline documentation running pada setiap commit di semua branch feature developer.
    *Pertanyaan*: Optimasi arsitektural apa yang wajib dilakukan untuk memangkas biaya hingga lebih dari 80% tanpa mengorbankan kualitas dokumentasi?
    *Kunci Jawaban Solusi Enterprise*:
    *   *Event Boundary Re-architecture*: Pindahkan trigger eksekusi dari *every commit* menjadi *PR marked as ready for review* atau *merge to main/release branch*.
    *   *Deterministic AST Diff Gate*: Gunakan Tree-sitter untuk membandingkan AST tree lama dan baru. Jika hash dari AST exported symbols (fungsi publik, class publik, API routes) tidak berubah, batalkan pipeline sebelum menyentuh LLM (Zero LLM Token Cost).
    *   *Local/Smaller Model Triage*: Gunakan open-source LLM lokal berbobot kecil (misal: Llama 3 8B / Qwen 2.5 Coder via vLLM) untuk fase klasifikasi/impact analysis, dan hanya gunakan model frontier (GPT-4o/Claude 3.5 Sonnet) untuk sintesis narasi akhir jika dokumen berkategori tier-1 (Public API).

13. **Skenario Kasus 3**:
    Dokumentasi publik perusahaan Anda mengalami insiden keamanan: Agent Autonomous Technical Writer secara tidak sengaja mempublikasikan nilai `API_KEY_SECRET` dan URL staging database internal ke dalam contoh panduan API di portal dokumentasi publik.
    *Pertanyaan*: Analisis di titik mana kegagalan pipeline terjadi dan rancang mekanisme pencegahan permanennya!
    *Kunci Jawaban Solusi Enterprise*:
    *   *Root Cause*: LLM memproses test file / config mock yang berisi nilai rahasia atau mengekstrak env sample lalu menyalinnya secara mentah ke narasi dokumentasi tanpa sanitasi output.
    *   *Prevention Architecture*:
        1. Pasang alat *Secret Scanner* deterministik (seperti `TruffleHog` atau `Gitleaks`) pada teks output draf Markdown sebelum memasuki pipeline git commit.
        2. Terapkan *Regex Masking Sanitizer* otomatis terhadap pola-pola kritis (AWS keys, JWT tokens, connection strings, internal domain URL).
        3. Berikan *System Prompt Guardrail* ketat: "DILARANG menggunakan string rahasia nyata; wajib menggunakan placeholder standar RFC (contoh: `https://api.example.com`, `<YOUR_API_KEY>`)".

---

### 16. Summary

Autonomous Technical Writer Agent dalam ekosistem AI & Autonomous Agents kelas enterprise merupakan pergeseran paradigma fundamental dari pembaruan dokumentasi manual menuju **Continuous Semantic Documentation**. 

Keberhasilan implementasi arsitektur ini bertumpu pada **tiga pilar non-negotiable**:
1. **Determinisme Struktural**: Menggunakan parser berbasis kompilasi (Tree-sitter/AST) untuk memahami topologi perubahan kode secara akurat dan memfilter diff yang tidak relevan sebelum mengonsumsi token LLM.
2. **Multi-Agent Verification Loop**: Memisahkan peran antara pembuat draf (*Writer*) dan penguji kode (*Critic*), di mana setiap kode contoh yang dipublikasikan wajib lolos uji sintaksis dan kontrak data secara deterministik.
3. **Docs-as-Code Integration**: Mengalirkan hasil dokumentasi langsung ke ekosistem developer (Git, PR review, linters seperti Vale dan Spectral), memastikan dokumentasi berevolusi serentak dengan kode sumber tanpa friksi operasional.