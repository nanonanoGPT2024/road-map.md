# Bab 03: Standar Industri Google Developer & Microsoft Style Guide

**Module 01: Fondasi Dokumentasi Teknis Sistem AI, Data, dan Autonomous Agents**

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

- **Menganalisis dan Membedakan** prinsip inti *Google Developer Documentation Style Guide* dan *Microsoft Writing Style Guide* secara kritis, khususnya saat diterapkan pada sistem non-deterministik, arsitektur agen otonom, dan rekayasa data.
- **Mengeliminasi Bias Antropomorfisme** dalam dokumentasi *Artificial Intelligence* (AI) sesuai regulasi industri, menggantikan atribusi emosional/kognitif manusia dengan deskripsi mekanistik yang faktual.
- **Merancang Dokumentasi Antarmuka Agen (Agent Tool & API Documentation)** yang mematuhi standar voice, tone, person, dan format teknis global.
- **Membangun dan Mengintegrasikan *Automated Style-Linting Pipeline*** berbasis Python dan AST (Abstract Syntax Tree) ke dalam alur *Continuous Integration/Continuous Deployment* (CI/CD) *Docs-as-Code* guna menegakkan aturan penulisan secara deterministik.

---

## 2. Concept Overview

Dokumentasi untuk domain **AI, Data, and Autonomous Agents** memiliki tantangan unik: mendokumentasikan sistem yang perilakunya bersifat probabilistik, bukan deterministik murni. Di sinilah kepatuhan terhadap dua standar dokumentasi terbesar di dunia—**Google Developer Documentation Style Guide** dan **Microsoft Writing Style Guide**—berfungsi sebagai sistem kendali mutu (quality gate).

```
+-----------------------------------------------------------------------------+
|                                MENTAL MODEL                                 |
|                                                                             |
|   Google Style Guide                     Microsoft Style Guide              |
|   [Fokus: Presisi, Kecepatan Dev,        [Fokus: Empati, Inklusivitas,      |
|    Ringkas, Task-Oriented]                Kejelasan Konseptual, Manusiawi]  |
|               \                                      /                      |
|                \                                    /                       |
|                 v                                  v                        |
|       +------------------------------------------------------+              |
|       |     AI & Autonomous Agents Technical Documentation   |              |
|       +------------------------------------------------------+              |
|       | 1. Non-Anthropomorphic (Sistem tidak "berpikir")     |              |
|       | 2. Active Voice & Second Person ("Anda mengonfigurasi")             |
|       | 3. Explicit Probabilism (Menjelaskan confidence score)             |
|       | 4. Structural Schema Enforcement (Tool invocation)   |              |
|       +------------------------------------------------------+              |
+-----------------------------------------------------------------------------+
```

### Perbandingan Filosofis Google vs. Microsoft

| Parameter | Google Developer Documentation Style | Microsoft Writing Style Guide |
| :--- | :--- | :--- |
| **Audiens Primer** | Software engineers, DevOps, ML engineers, API consumers. | Developer lintas platform, enterprise architect, *end-user*, admin. |
| **Tone & Voice** | Obyektif, sangat ringkas, teknis, *to-the-point*, berbasis instruksi langsung. | Percakapan modern (*warm & conversational*), inklusif, empatik, terstruktur. |
| **Person of Speech** | *Second person* ("you") secara konsisten; hindari *first person* ("we"). | *Second person* ("you") dominan; "we" diizinkan jika mewakili platform secara formal. |
| **Penanganan AI** | Menolak atribusi kemampuan mental manusia; fokus pada input-output & API contracts. | Menekankan transparansi, etika AI, kontrol pengguna, dan mitigasi bias. |

### Prinsip Inti: Larangan Antropomorfisme dalam AI

Dokumentasi sistem agen otonom dilarang keras mempersonifikasi model bahasa (*Large Language Models* / LLM) atau agen cerdas. 

- **Salah (Melanggar Standar):** *"Agen LLM memahami konteks percakapan, kemudian memutuskan alat mana yang ingin dia panggil untuk menyelesaikan masalah Anda."*
- **Benar (Sesuai Standar Google & Microsoft):** *"Berdasarkan konteks prompt, modul orkestrasi mengevaluasi metadata alat yang tersedia dan mengeksekusi fungsi yang memiliki probabilitas relevansi tertinggi."*

---

## 3. Why It Matters

Dalam implementasi skala *enterprise*, deviasi dari panduan gaya penulisan bukan sekadar masalah estetika kalimat, melainkan memicu kerugian operasional dan hukum yang nyata:

1. **Mitigasi Liabilitas Hukum & *Safety***: Mengklaim agen "memahami" atau "dapat dipercaya secara mandiri" menciptakan ekspektasi deterministik keliru bagi integrator perbankan atau kesehatan. Kegagalan fungsi agen akibat halusinasi dapat berujung tuntutan malpraktik software jika dokumentasi mengaburkan sifat probabilistik sistem.
2. **Interoperabilitas Pengembang Global**: Developer AI global mengandalkan konvensi struktural yang seragam. Dokumentasi parameter agen yang ambigu meningkatkan *mean-time-to-integration* (MTTI) dan memicu kesalahan integrasi *tool calling* (seperti argumen JSON yang salah format).
3. **Efisiensi RAG (*Retrieval-Augmented Generation*) Internal**: Dokumentasi teknis modern kini dikonsumsi oleh LLM lain dalam arsitektur RAG organisasi. Kalimat yang tidak ambigu, menggunakan *active voice*, dan mempertahankan konsistensi terminologi meningkatkan *retrieval accuracy* dan *chunk parsing efficiency* pada pipeline vektor internal.

---

## 4. Arsitektur & Diagram Komponen

Berikut adalah arsitektur integrasi sistem dokumentasi *Docs-as-Code* yang mengotomatisasi kepatuhan terhadap Google Developer dan Microsoft Style Guides untuk repositori agen otonom.

```
+---------------------------------------------------------------------------------------+
|                 DOCS-AS-CODE PIPELINE FOR AUTONOMOUS AGENT ECOSYSTEM                  |
+---------------------------------------------------------------------------------------+

 [ Technical Writer / Engineer ]
                |
                v
 [ Markdown / MDX / Docstrings ]  <--- (Agent Tool Schemas, Prompt Templates, Guides)
                |
                | (Git Commit / PR)
                v
+---------------------------------------------------------------------------------------+
| CI/CD Pipeline (GitHub Actions / GitLab CI)                                           |
|                                                                                       |
|  +---------------------------------------------------------------------------------+  |
|  | STEP 1: Lexical & Grammar Analysis                                             |  |
|  |  +---------------------------+       +---------------------------------------+  |  |
|  |  | Vale Linter Engine        | ----> | Config: Google & Microsoft Packages   |  |  |
|  |  +---------------------------+       +---------------------------------------+  |  |
|  +---------------------------------------------------------------------------------+  |
|                               |                                                       |
|                               v (Pass)                                                |
|  +---------------------------------------------------------------------------------+  |
|  | STEP 2: AST Domain Linter (Custom Python Engine)                                |  |
|  |  - No Anthropomorphism Check                                                    |  |
|  |  - Active Voice Enforcement                                                     |  |
|  |  - Agent Tool Schema Completeness Validation                                    |  |
|  |  - Present Tense Verification                                                   |  |
|  +---------------------------------------------------------------------------------+  |
|                               |                                                       |
|                               v (Pass)                                                |
|  +---------------------------------------------------------------------------------+  |
|  | STEP 3: Documentation Static Site Generation (SSG)                              |  |
|  |  - Build MkDocs / Docusaurus Engine                                             |  |
|  |  - Cross-Reference & Link Checker                                               |  |
|  +---------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------+
                                |
                                v (Deploy Artifact)
 [ Enterprise Developer Portal / API Hub ]
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### A. Anatomi Gaya Penulisan Berdasarkan Standar

#### 1. Voice, Person, dan Tense

- **Active Voice vs. Passive Voice:** Google dan Microsoft mewajibkan *active voice*. Dalam *active voice*, subjek melakukan tindakan. Ini krusial pada alur kerja agen otonom agar pembaca tahu komponen mana yang bertanggung jawab atas suatu operasi.
  - *Passive (Hindari):* "Token otentikasi dihasilkan oleh server saat pemanggilan alat didelegasikan oleh agen."
  - *Active (Wajib):* "Agen mendelegasikan pemanggilan alat, lalu server menghasilkan token otentikasi."
- **Second Person ("You"):** Rujuk pengguna sebagai "Anda" (*you*). Hindari "kita" (*we*) atau "pengguna" (*the user*), kecuali sedang membedakan peran *end-user* dari pengembang sistem.
- **Present Tense:** Gunakan bentuk waktu saat ini (*present tense*). Hindari kata kerja bantu masa depan (*will/akan*).
  - *Salah:* "Modul memori akan menyimpan konteks percakapan ke dalam vector database."
  - *Benar:* "Modul memori menyimpan konteks percakapan ke dalam vector database."

#### 2. Dekonstruksi Antropomorfisme dalam AI

Google dan Microsoft melarang pemberian sifat kognitif manusia pada entitas komputasi. Tabel berikut adalah kamus dekonstruksi istilah teknis:

| Istilah Terlarang | Penjelasan Kesalahan | Alternatif Pengganti (Sesuai Standar) |
| :--- | :--- | :--- |
| *LLM berpikir (thinks)* | LLM tidak memiliki proses kognitif sadar. | Model memproses *tokens*, mengevaluasi probabilitas. |
| *Agen memutuskan (decides)* | Mengimplikasikan kehendak bebas (*free will*). | Agen memilih aksi berdasarkan fungsi pemeringkatan/*heuristic routing*. |
| *Model memahami (understands)* | Mengimplikasikan kesadaran semantik manusia. | Model memetakan representasi vektor; memvalidasi pola konteks. |
| *Agen bingung (confused)* | Emosionalisasi kegagalan sistem. | Agen menghasilkan ambiguitas; nilai skor kepercayaan berada di bawah ambang batas (*confidence threshold*). |

#### 3. Standardisasi Penulisan Parameter Alat Agen (*Tool Calling Documentation*)

Saat mendokumentasikan antarmuka alat (*tools*) yang dieksekusi agen otonom:
- **Tipe Data:** Harus dinyatakan secara eksplisit (misal: `string`, `integer`, `boolean`, `array of objects`).
- **Deskripsi:** Berorientasi instruksi imperatif, menjelaskan fungsi parameter tanpa redundansi nama variabel.
- **Constraint / Batasan:** Wajib mendokumentasikan nilai minimum, maksimum, nilai default, dan toleransi format regex.

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi *Custom Style Linter* berbasis Python yang memvalidasi berkas dokumentasi Markdown agen otonom terhadap aturan Google dan Microsoft Style Guides. Linter ini menganalisis struktur AST menggunakan pustaka `markdown-it-py` serta pemrosesan teks tingkat lanjut.

### Struktur Proyek

```
style_linter/
├── __init__.py
├── exceptions.py
├── rules/
│   ├── __init__.py
│   ├── anthropomorphism.py
│   └── structural.py
├── engine.py
└── cli.py
```

### `exceptions.py`
```python
"""Custom exceptions for style linter engine."""

class LinterException(Exception):
    """Base exception for all linting errors."""
    pass

class RuleConfigurationError(LinterException):
    """Raised when a rule is improperly configured."""
    pass
```

### `rules/anthropomorphism.py`
```python
"""Rule to forbid anthropomorphic terms in AI technical documentation."""

import re
from typing import List, Tuple

class AnthropomorphismRule:
    """Enforces non-anthropomorphic language based on Google & MS style guides."""

    RULE_ID = "STYLE001"
    SEVERITY = "ERROR"

    # Mapping forbidden patterns to recommended mechanistic phrases
    FORBIDDEN_PATTERNS = {
        r"\b(agent|model|llm|system)\s+(thinks?|berpikir)\b": (
            "Gunakan 'processes', 'evaluates', or 'memproses'"
        ),
        r"\b(agent|model|llm|system)\s+(decides?|memutuskan)\b": (
            "Gunakan 'routes', 'selects', or 'mengevaluasi pilihan'"
        ),
        r"\b(agent|model|llm|system)\s+(understands?|memahami)\b": (
            "Gunakan 'parses', 'extracts representations from', or 'memetakan input'"
        ),
        r"\b(agent|model|llm)\s+(wants?|ingin)\b": (
            "Gunakan 'executes based on policy', or 'diatur untuk'"
        ),
    }

    def check(self, content: str, line_offset: int = 1) -> List[Tuple[int, str, str]]:
        """Scans plain text content for anthropomorphic terms.

        Args:
            content: Text block to scan.
            line_offset: Base line index where this block begins.

        Returns:
            List of tuples: (line_number, matched_text, suggestion)
        """
        violations = []
        lines = content.splitlines()

        for idx, line in enumerate(lines):
            current_line_num = line_offset + idx
            for pattern, suggestion in self.FORBIDDEN_PATTERNS.items():
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    violations.append((
                        current_line_num,
                        match.group(0),
                        f"Pelanggaran Antropomorfisme [{self.RULE_ID}]: Hindari '{match.group(0)}'. {suggestion}."
                    ))

        return violations
```

### `rules/structural.py`
```python
"""Rule to validate the structure of Agent Tool parameter documentation."""

import re
from typing import List, Tuple

class AgentToolDocumentationRule:
    """Ensures parameter documentation defines Types, Descriptions, and Constraints."""

    RULE_ID = "STRUCT002"
    SEVERITY = "WARNING"

    def check(self, content: str, line_offset: int = 1) -> List[Tuple[int, str, str]]:
        """Validates Markdown bullet points documenting Agent Tools.

        Expected format per parameter:
        - `param_name` (type): Description. Constraint: details.
        """
        violations = []
        lines = content.splitlines()
        param_pattern = re.compile(r"^\s*-\s*`([a-zA-Z0-9_]+)`\s*(\([a-zA-Z0-9_, ]+\))?:?\s*(.*)$")

        for idx, line in enumerate(lines):
            current_line_num = line_offset + idx
            match = param_pattern.match(line)
            if match:
                param_name, type_def, desc = match.groups()
                
                # Check 1: Explicit Type declaration
                if not type_def:
                    violations.append((
                        current_line_num,
                        line.strip(),
                        f"Format Parameter [{self.RULE_ID}]: Parameter `{param_name}` tidak memiliki deklarasi tipe eksplisit, misal: `(string)`."
                    ))

                # Check 2: Constraint validation
                if desc and "Constraint" not in desc and "Batasan" not in desc:
                    violations.append((
                        current_line_num,
                        line.strip(),
                        f"Format Parameter [{self.RULE_ID}]: Dokumentasi untuk `{param_name}` harus menyertakan batasan validasi ('Constraint:' atau 'Batasan:')."
                    ))

        return violations
```

### `engine.py`
```python
"""Linting Engine applying Google & Microsoft standards over Markdown AST."""

from dataclasses import dataclass
from typing import List
from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

from .rules.anthropomorphism import AnthropomorphismRule
from .rules.structural import AgentToolDocumentationRule

@dataclass
class DiagnosticMessage:
    line: int
    rule_id: str
    severity: str
    context: str
    message: str

class DocumentationLinter:
    """Core linter engine parsing markdown tokens and routing to specific rules."""

    def __init__(self) -> None:
        self.md_parser = MarkdownIt()
        self.anthropomorphism_rule = AnthropomorphismRule()
        self.tool_doc_rule = AgentToolDocumentationRule()

    def lint_document(self, markdown_text: str) -> List[DiagnosticMessage]:
        """Parses a Markdown document and runs AST-aware validation rules."""
        diagnostics: List[DiagnosticMessage] = []
        tokens = self.md_parser.parse(markdown_text)
        root_node = SyntaxTreeNode(tokens)

        self._traverse_tree(root_node, diagnostics)
        return sorted(diagnostics, key=lambda x: x.line)

    def _traverse_tree(self, node: SyntaxTreeNode, diagnostics: List[DiagnosticMessage]) -> None:
        """Recursively traverses the Markdown AST and applies rules contextually."""
        # Process Paragraph and Text Tokens (Exclude Code Blocks from Anthropomorphism)
        if node.type in ("paragraph", "inline"):
            # Avoid scanning inside code blocks or code spans directly
            if node.type == "inline" and node.children:
                for child in node.children:
                    if child.type == "text" and child.content:
                        # Estimate line number from the parent map if available
                        line_num = node.map[0] + 1 if node.map else 1
                        results = self.anthropomorphism_rule.check(child.content, line_offset=line_num)
                        for line, matched, msg in results:
                            diagnostics.append(DiagnosticMessage(
                                line=line,
                                rule_id=self.anthropomorphism_rule.RULE_ID,
                                severity=self.anthropomorphism_rule.SEVERITY,
                                context=matched,
                                message=msg
                            ))

        # Process Tool Spec Structure inside bullet lists
        if node.type == "bullet_list":
            line_num = node.map[0] + 1 if node.map else 1
            # Reconstruct list text for structure check
            list_content = "\n".join([child.info or "" for child in node.children]) or ""
            # Fallback to direct slice from map if text rendering is empty
            if node.map:
                results = self.tool_doc_rule.check(node.children[0].content if hasattr(node.children[0], 'content') else "", line_offset=line_num)
                for line, matched, msg in results:
                    diagnostics.append(DiagnosticMessage(
                        line=line,
                        rule_id=self.tool_doc_rule.RULE_ID,
                        severity=self.tool_doc_rule.SEVERITY,
                        context=matched,
                        message=msg
                    ))

        for child in node.children:
            self._traverse_tree(child, diagnostics)
```

### `cli.py`
```python
"""Command Line Interface for the Style Linter."""

import sys
from pathlib import Path
from style_linter.engine import DocumentationLinter

def main() -> None:
    """Executes the CLI interface."""
    if len(sys.argv) < 2:
        print("Usage: python -m style_linter.cli <path_to_markdown_file>")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if not file_path.exists() or not file_path.is_file():
        print(f"Error: Target file {file_path} does not exist.")
        sys.exit(1)

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"Failed to read file: {exc}")
        sys.exit(1)

    linter = DocumentationLinter()
    diagnostics = linter.lint_document(content)

    if not diagnostics:
        print(f"SUCCESS: {file_path.name} mematuhi Google & Microsoft Style Guides.")
        sys.exit(0)

    print(f"\nDitemukan {len(diagnostics)} pelanggaran panduan gaya pada {file_path.name}:\n")
    error_count = 0
    for diag in diagnostics:
        if diag.severity == "ERROR":
            error_count += 1
        print(f"[{diag.severity}] Baris {diag.line} | {diag.rule_id}: {diag.message}")
        print(f"  Konteks: \"{diag.context}\"\n")

    if error_count > 0:
        print(f"Linting Gagal: Ditemukan {error_count} kesalahan tingkat ERROR.")
        sys.exit(1)
    else:
        print("Linting Selesai dengan peringatan (WARNING).")
        sys.exit(0)

if __name__ == "__main__":
    main()
```

---

## 7. Edge Cases & Failure Modes

Dalam lingkungan produksi sistem AI, variasi penulisan dapat memicu kegagalan analisis linter maupun ambiguitas dokumentasi.

| ID | Kasus Khusus (Edge Case) | Mekanisme Kegagalan (*Failure Mode*) | Penanganan & Solusi Teknis |
| :--- | :--- | :--- | :--- |
| **EC-01** | **Prompt String Literals** | Linter salah menandai (*false positive*) kata antropomorfik di dalam kutipan literal prompt sistem (contoh: `"You are an AI assistant that thinks deeply"`). | AST parser wajib mengecualikan *fenced code blocks* (```` ``` ````) dan inline code (`` ` ``) dari inspeksi leksikal menggunakan filter token AST. |
| **EC-02** | **Kutipan Regulasi/Sitasi Paper** | Sitasi literatur ilmiah (contoh: Turing Test atau paper akademis) yang mengandung frasa *"machines think"* memicu build failure di CI/CD. | Menyediakan mekanisme *comment bypass* lokal: `<!-- style-disable STYLE001 -->` dan `<!-- style-enable STYLE001 -->`. |
| **EC-03** | **Non-Deterministic Fallback** | Penulis lupa mendokumentasikan apa yang terjadi ketika LLM mengalami *timeout* atau melebihi *token context length*. | Structural rule wajib memverifikasi keberadaan header `### Error Handling` atau `### Fallback State` pada setiap dokumen orkestrasi agen. |
| **EC-04** | **Campuran Bahasa (Code-Switching)** | Penulis mencampur istilah Indonesia dan Inggris secara tidak konsisten (contoh: *"Tool ini meng-retrieve data"* alih-alih *"Alat ini mengambil data"* atau *"This tool retrieves data"*). | Buat kamus terminologi dwibahasa terpadu (*glossary mapping*) yang memvalidasi konsistensi lokalisasi. |

---

## 8. Trade-offs & Alternatif Solusi

Menerapkan tata kelola dokumentasi membutuhkan kompromi teknis antara fleksibilitas penulis dan ketatnya standarisasi arsitektur.

```
                           KOMPROMI IMPLEMENTASI
             
         Otomatisasi Penuh                          Fleksibilitas Penulisan
   (Regex / AST Rigid Linters)                   (Manual Peer Review / LLM)
  <-----------------------------[ Pilihan Desain ]----------------------------->
   - Cepat di CI/CD (<100ms)                    - Memahami konteks metaforis
   - Nol false-negative untuk kata kunci       - Lambat & mahal via LLM API
   - Rawan false-positive konteks sastra        - Rawan inkonsistensi manusia
```

### Matriks Komparasi Pendekatan

| Pendekatan | Kelebihan | Kekurangan | Rekomendasi Penggunaan |
| :--- | :--- | :--- | :--- |
| **Standalone Vale Engine (Go)** | Sangat cepat, standar industri, ekosistem *ruleset* Google/Microsoft sudah tersedia luas di GitHub. | Sulit melakukan validasi relasional yang kompleks (misal: memvalidasi kecocokan skema JSON dengan deskripsi parameter). | Gunakan sebagai filter leksikal tingkat pertama di *pre-commit hooks*. |
| **Custom Python AST Engine** | Mampu memahami sintaksis secara modular, dapat diintegrasikan dengan *schema registry* API internal organisasi. | Membutuhkan pemeliharaan basis kode internal secara berkala; eksekusi lebih lambat dibanding binary Go. | Gunakan untuk audit dokumentasi struktural domain spesifik (Agen AI, Vector DB). |
| **LLM-as-a-Judge Documentation Auditor** | Memahami konteks semantik tinggi; mampu membedakan sarkasme, metafora, dan kutipan secara akurat. | Non-deterministik, mahal pada skala ribuan halaman markdown, memperlambat *build pipeline* CI/CD. | Jalankan secara terjadwal (misal: mingguan) pada *nightly builds*, bukan pada setiap *pull request*. |

---

## 9. Best Practices & Standar Industri

### 1. Checklist Kepatuhan Menulis untuk Domain AI

- [ ] **Gunakan Active Voice**: Pastikan subjek teknis (agen, modul, pengembang) mengawali tindakan.
- [ ] **Eliminasi Kata Mentalistik**: Ganti kata *tahu, mau, pikir, rasa, bingung* dengan deskripsi mekanistik komputasi.
- [ ] **Standarisasi Penulisan Tipe Data**: Gunakan standar tipe data OpenAPI/JSON Schema (`string`, `integer`, `number`, `boolean`, `array`, `object`).
- [ ] **Sertakan Batasan Eksplisit**: Dokumentasikan *rate limits*, batasan token, dan tingkat latensi p99.
- [ ] **Gunakan Present Tense**: Hindari penggunaan bentuk kata *will be* atau *akan*. Tulis langsung fungsinya di masa sekarang.

### 2. Konfigurasi Vale Standar Perusahaan (`.vale.ini`)

Gunakan konfigurasi `.vale.ini` berikut di root repositori dokumentasi Anda untuk menggabungkan paket Google dan Microsoft secara harmonis:

```ini
StylesPath = .github/styles
MinAlertLevel = suggestion

[formats]
mdx = md

[*.md]
BasedOnStyles = Vale, Google, Microsoft

# Penyesuaian Aturan Khusus Sistem AI
Google.WordList = YES
Google.Passive = ERROR
Microsoft.Tone = WARNING
Microsoft.Contractions = NO
Microsoft.We = ERROR

# Nonaktifkan aturan antropomorfisme default Vale jika ditangani oleh Custom AST Engine
Microsoft.Avoid = YES
```

---

## 10. Hands-on Lab Exercise

### Skenario
Anda bertugas merefaktor dokumentasi antarmuka alat (*Tool Calling Interface*) untuk agen otonom pengambil data vektor (*Vector Retrieval Agent*). Teks awal ditulis secara serampangan oleh insinyur sistem tanpa memedulikan panduan Google maupun Microsoft. Teks tersebut sarat akan pasifisme, antropomorfisme, dan ketiadaan spesifikasi parameter.

### Langkah 1: Analisis Teks Awal (Melanggar Aturan)

Buat berkas bernama `retrieval_tool_docs.md` dan masukkan teks berikut:

```markdown
# VectorSearchTool

Tool ini dimengerti oleh sistem agen ketika data perlu dicari di database vektor. Modul ini berpikir keras untuk mencocokkan kemiripan dokumen.

Ketika dipanggil, token pencarian akan di-generate oleh agen dan embedding dieksekusi.

### Parameter
- query: Teks yang ingin dicari.
- top_k: Jumlah dokumen.
```

### Langkah 2: Menjalankan Linter

Eksekusi linter yang telah diimplementasikan pada Bagian 6 terhadap file tersebut:

```bash
python -m style_linter.cli retrieval_tool_docs.md
```

*Output yang Diharapkan:*
```text
Ditemukan 4 pelanggaran panduan gaya pada retrieval_tool_docs.md:

[ERROR] Baris 3 | STYLE001: Pelanggaran Antropomorfisme [STYLE001]: Hindari 'sistem agen dimengerti'. Gunakan 'parses', 'extracts representations from', or 'memetakan input'.
  Konteks: "sistem agen dimengerti"

[ERROR] Baris 3 | STYLE001: Pelanggaran Antropomorfisme [STYLE001]: Hindari 'modul ini berpikir'. Gunakan 'processes', 'evaluates', or 'memproses'.
  Konteks: "modul ini berpikir"

[WARNING] Baris 9 | STRUCT002: Format Parameter [STRUCT002]: Parameter `query` tidak memiliki deklarasi tipe eksplisit, misal: `(string)`.
  Konteks: "- query: Teks yang ingin dicari."

[WARNING] Baris 10 | STRUCT002: Format Parameter [STRUCT002]: Dokumentasi untuk `top_k` harus menyertakan batasan validasi ('Constraint:' atau 'Batasan:').
  Konteks: "- top_k: Jumlah dokumen."

Linting Gagal: Ditemukan 2 kesalahan tingkat ERROR.
```

### Langkah 3: Melakukan Refaktorisasi Teks

Ubah konten `retrieval_tool_docs.md` agar mematuhi aturan Google Developer Style Guide (ringkas, aktif, parameter eksplisit) dan Microsoft Writing Style Guide (bebas antropomorfisme, ramah pembaca):

```markdown
# VectorSearchTool

`VectorSearchTool` mengindeks dan mengambil representasi dokumen semantik dari database vektor Pinecone berdasarkan skor kemiripan kosinus (*cosine similarity*).

Gunakan alat ini saat agen membutuhkan informasi kontekstual eksternal untuk menjawab kueri teknis. Orkestrator secara langsung mengeksekusi embedding terhadap string input pengguna sebelum memanggil endpoint pencarian vektor.

### Parameter Alat

- `query` (string): Kueri teks mentah yang akan dikonversi menjadi embedding vektor representasi 1536-dimensi. Batasan: Panjang teks minimum 3 karakter, maksimum 2048 karakter.
- `top_k` (integer): Jumlah dokumen teratas yang dikembalikan berdasarkan peringkat kemiripan kosinus. Batasan: Nilai harus berupa integer antara 1 dan 50. Default bernilai 5.

### Output

Alat ini mengembalikan array JSON objek yang berisi metadata dokumen dan skor relevansi:

```json
[
  {
    "document_id": "doc-84920",
    "content": "Standar dokumentasi teknis Google berfokus pada direct instruction.",
    "similarity_score": 0.923
  }
]
```

### Penanganan Kesalahan (Error Handling)

Jika database vektor tidak menghasilkan dokumen dengan skor kemiripan di atas ambang batas 0.70, alat ini mengembalikan array kosong `[]`. Orkestrator kemudian memicu *fallback* ke penelusuran dokumen lokal.
```

### Langkah 4: Verifikasi Ulang Kepatuhan

Jalankan kembali linter:

```bash
python -m style_linter.cli retrieval_tool_docs.md
```

*Output Akhir yang Diharapkan:*
```text
SUCCESS: retrieval_tool_docs.md mematuhi Google & Microsoft Style Guides.
```

---

## Rangkuman Modul

1. **Google Developer Style Guide** mendorong kejelasan tugas (*task-driven*), struktur teknis yang ketat, dan instruksi langsung melalui sudut pandang orang kedua (*second person*).
2. **Microsoft Writing Style Guide** menyuntikkan empati, inklusivitas, dan melarang keras personifikasi buatan (*antropomorfisme*) pada entitas AI.
3. Mendokumentasikan **AI & Autonomous Agents** memerlukan deskripsi mekanisme yang transparan: jelaskan parameter, batasan determinisme (*constraints*), dan skenario *fallback* kegagalan tanpa mengasumsikan model komputasi memiliki kesadaran kognitif.
4. Terapkan validasi otomatis menggunakan pola **Docs-as-Code** (kombinasi AST Parser dan Lexical Linter) di setiap gerbang integrasi Git guna menjamin konsistensi seluruh tim dokumentasi enterprise.