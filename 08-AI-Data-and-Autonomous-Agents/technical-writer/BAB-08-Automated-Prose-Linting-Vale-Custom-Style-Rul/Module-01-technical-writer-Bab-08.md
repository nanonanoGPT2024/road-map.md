# Bab 08: Automated Prose Linting Menggunakan Vale & Custom Style Rules

## Modul 01: Arsitektur Prose Linting & Implementasi Custom Rule Engine

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis Arsitektur Internal Vale**: Menguraikan alur eksekusi Vale dari parsing Abstract Syntax Tree (AST), pemetaan *scope*, hingga evaluasi token secara deterministik.
- **Mengembangkan Custom Style Rules**: Menulis dan memvalidasi aturan berbasis YAML (`existence`, `substitution`, `occurrence`, `repetition`, `consistency`, dan `script`) dengan kepatuhan sintaks 100%.
- **Mengimplementasikan Rule Berbasis Regex & NLP Extension**: Membangun aturan linting semantik tingkat lanjut menggunakan kombinasi regular expression engine (RE2) dan skrip ekstensi eksternal.
- **Mengintegrasikan CI/CD Quality Gate**: Membangun pipeline otomatisasi (GitHub Actions/GitLab CI) yang memvalidasi repositori multi-format (Markdown, AsciiDoc, MDX) dengan ambang batas zero false-positive.
- **Mengoptimalkan Token Ingestion untuk RAG/Agent Datasets**: Memastikan konsistensi penulisan teknis guna meminimalisasi *entropy* dan ambiguitas semantik pada korpus data yang digunakan oleh model AI/Autonomous Agents.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Prose linting adalah proses statis untuk menganalisis teks bahasa alami (*prose*) terhadap sekumpulan aturan gaya penulisan (*style guides*), kejelasan sintaksis, konsistensi terminologi, dan struktur dokumen. Berbeda dengan *source code linter* (seperti ESLint atau Ruff) yang bekerja pada sintaksis bahasa formal dengan ambiguitas minimal, prose linter menghadapi tantangan ambiguitas bahasa alami dan keberagaman format dokumen teknis (Markdown, MDX, reStructuredText, AsciiDoc).

```
[ Mental Model: Source Code Linting vs. Prose Linting ]

Source Code:   Source File -> Lexer/Parser -> AST -> Static Rule Visitor -> Diagnostics
Prose (Vale):  Markup File -> Format Converter -> Scoped HTML/AST -> Block/Span Tokenizer -> Extensible Rule Engine -> Diagnostics
```

Vale mengadopsi pendekatan *syntax-aware, command-line tool* yang ditulis dalam bahasa Go. Vale tidak memperlakukan dokumen sebagai *raw string* satu dimensi. Sebaliknya, Vale:
1. Mengonversi format dokumen target ke representasi HTML-AST internal.
2. Mengisolasi elemen non-prose (seperti `code blocks`, `inline code`, `frontmatter`, `HTML tags`, dan `URLs`).
3. Memetakan teks ke dalam *scopes* struktural (misalnya: `heading`, `paragraph`, `table.cell`, `list.item`).
4. Menerapkan rule engine deklaratif berbasis YAML pada cakupan (*scope*) yang ditentukan secara presisi.

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Pada skala enterprise dan era autonomous data pipelines, dokumentasi teknis bukan lagi sekadar artefak manusia; ia merupakan dataset pelatihan (*fine-tuning*) dan korpus knowledge base (*Retrieval-Augmented Generation* / RAG) untuk agen AI.

1. **Ambiguitas Terminologi & Halusinasi AI**: Penggunaan istilah teknis yang tidak konsisten (misal: saling berganti antara *API Gateway*, *API Proxy*, dan *Edge Service* untuk merujuk objek yang sama) meningkatkan dispersi vektor embedding pada sistem RAG. Akibatnya, agen otonom menghasilkan resolusi *tool-calling* yang keliru.
2. **Skalabilitas Kontributor Open-Source & Tim Terdistribusi**: Menjaga konsistensi ribuan halaman dokumentasi dari ratusan *software engineer* mustahil dilakukan secara manual melalui *peer review*. Editor manusia mengalami *cognitive fatigue*, sedangkan Vale mengeksekusi ratusan validasi per detik secara deterministik.
3. **Pemberlakuan Style Guide Industri Secara Terukur**: Mengonversi panduan tebal seperti *Google Developer Documentation Style Guide* atau *Microsoft Writing Style Guide* menjadi guardrail otomatis yang gagal secara eksplisit (*exit code non-zero*) pada level Pull Request sebelum *merge*.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur pemrosesan end-to-end Vale dari *source document* mentah hingga penegakan CI/CD pipeline:

```
+-----------------------------------------------------------------------------+
|                          Vale Execution Pipeline                            |
+-----------------------------------------------------------------------------+
                                       |
                   [Input: .md, .mdx, .adoc, .rst]
                                       v
                     +-----------------------------------+
                     |   Document Format Parser (Go)     |
                     | (Blackfriday, Goldmark, Asciidoctor)
                     +-----------------------------------+
                                       |
                      (HTML-AST & Block Normalization)
                                       v
+-----------------------------------------------------------------------------+
|                       Scope Extractor & Masking Engine                      |
|  - Raw Text Blocks Isolated                                                 |
|  - Inline/Block Code Masked (<code>...</code> -> raw placeholder)           |
|  - Frontmatter Stripped / Evaluated Separately                              |
+-----------------------------------------------------------------------------+
             |                                              |
     (Block-level Scopes)                          (Span-level Scopes)
    [heading, paragraph, li]                     [strong, em, inline-code]
             \                                              /
              +---------------------+----------------------+
                                    |
                                    v
+-----------------------------------------------------------------------------+
|                         Pattern Matcher (YAML Engine)                       |
|                                                                             |
|  +------------------+  +-------------------+  +--------------------------+  |
|  | Existence Rules  |  | Substitution Rules|  | Consistency/Occurrence   |  |
|  | (Regex Match)    |  | (Token Exchange)  |  | (State Tracking AcrossDoc|  |
|  +------------------+  +-------------------+  +--------------------------+  |
|  +-----------------------------------------------------------------------+  |
|  | Script Rules (Extensible via internal Boa / Go Plugins)               |  |
|  +-----------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------+
                                    |
                        (Collected Diagnostics)
                                    v
+-----------------------------------------------------------------------------+
|                            Diagnostics Reporter                             |
|  - Output Formats: CLI (Line:Col), JSON, Reviewdog, SARIF                   |
|  - Exit Codes: 0 (Success), 1 (Warnings/Errors based on thresholds)         |
+-----------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Scoping Mechanism: Block vs. Span
Vale memisahkan parsing menjadi dua hierarki lingkup (*scope*):
- **Block Scope**: Mencakup unit teks struktural penuh. Contoh: `paragraph`, `heading`, `table.cell`, `blockquote`. Rule bertipe `occurrence` atau `readability` beroperasi pada tingkat ini untuk mengukur metrik seperti panjang kalimat, metrik Flesch-Kincaid, atau jumlah kata pasif.
- **Span Scope**: Mencakup fragmen teks di dalam blok, seperti kata, frasa, atau elemen inline (`code`, `a`, `strong`). Aturan `substitution` dan `existence` umumnya dievaluasi pada tingkat span setelah elemen non-target (seperti inline code ` `code` `) diproteksi (*masked*).

#### 5.2 Tokenization dan Boundary Evaluation
Vale memanfaatkan Go regular expression engine (`regexp`), yang mengimplementasikan sintaks RE2. Karakteristik RE2 adalah eksekusi berbasis waktu linier $O(n)$ terhadap ukuran input, mencegah kerentanan *Regular Expression Denial of Service* (ReDoS).

Tantangan utama pada tokenisasi bahasa adalah batasan kata (*word boundary* `\b`). Pada terminologi teknis yang mengandung tanda baca (misal: `Node.js`, `.NET`, `c++`), `\b` konvensional gagal bekerja secara konsisten. Vale mengatasi hal ini dengan mengizinkan *non-word boundary assertions* dan *lookaround logic* terstruktur di dalam definisi rule YAML.

#### 5.3 Rule Types Archetypes
Vale mendefinisikan sejumlah *rule types* inti:
- **`existence`**: Mendeteksi keberadaan pola token tertentu (misalnya, melarang kata pengisi/filler words).
- **`substitution`**: Mendeteksi pola dan memetakan alternatif solusinya (misalnya, memetakan *whitelist* terminologi resmi).
- **`occurrence`**: Mengontrol batasan kemunculan suatu token dalam scope tertentu (misal: maksimal satu tanda seru per dokumen).
- **`repetition`**: Mendeteksi pengulangan kata yang tidak sengaja (misal: "the the", "in in").
- **`consistency`**: Memastikan konsistensi penulisan suatu istilah di seluruh dokumen (misal: memilih konsisten antara *front-end* vs *frontend*).
- **`capitalization`**: Menegakkan *Title Case*, *sentence case*, atau *ALL CAPS* pada heading berdasarkan kamus part-of-speech.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi enterprise style enforcement yang mencakup:
1. Konfigurasi sentral `.vale.ini`.
2. Custom Vocabularies (*Accept* dan *Reject* list).
3. Custom Style Rules (YAML).
4. Automasi Python Test Runner untuk memverifikasi rule correctness sebelum deployment.

#### 6.1 Struktur Direktori Standar
```text
docs-root/
├── .vale.ini
├── styles/
│   └── EnterpriseDocs/
│       ├── WordChoice.yml
│       ├── TechnicalTermsConsistency.yml
│       ├── HeadingPunctuation.yml
│       └── LatencyMetrics.yml
│   └── Vocab/
│       └── Technical/
│           ├── accept.txt
│           └── reject.txt
└── tests/
    └── test_vale_rules.py
```

#### 6.2 Konfigurasi Global: `.vale.ini`
```ini
StylesPath = styles
MinAlertLevel = suggestion

# Deklarasi Vocabulary Package aktif
Vocab = Technical

# Format target parsing
[*.{md,mdx}]

# Aktifkan rule suite kustom
BasedOnStyles = EnterpriseDocs

# Skiping komponen khusus MDX/React & Code Blocks
TokenIgnores = (<\/?[A-Z][a-zA-Z0-9]*(?:\s+[^>]+)*\/?>), (\{/\*[\s\S]*?\*/\})
BlockIgnores = (?s)(<pre.*?>.*?<\/pre>), (?s)(import\s+.*?from\s+['"].*?['"];?)

# Penyesuaian Level bawaan
EnterpriseDocs.HeadingPunctuation = error
EnterpriseDocs.TechnicalTermsConsistency = error
EnterpriseDocs.WordChoice = warning
EnterpriseDocs.LatencyMetrics = suggestion
```

#### 6.3 Rule 1: `styles/EnterpriseDocs/WordChoice.yml` (`substitution`)
Menegakkan terminologi standar enterprise dan melarang jargon tidak formal.

```yaml
extends: substitution
message: "Gunakan terminologi resmi '%s' alih-alih '%s' untuk menjaga presisi dokumentasi."
link: "https://handbook.enterprise.internal/style/word-choice"
level: error
scope: paragraph
ignorecase: false
swap:
  (?i)e\.g\.?: 'for example,'
  (?i)i\.e\.?: 'that is,'
  (?i)auth0-token: 'JWT token'
  (?i)whitelist: 'allowlist'
  (?i)blacklist: 'denylist'
  (?i)master/slave: 'primary/replica'
  (?i)kill the process: 'terminate the process'
```

#### 6.4 Rule 2: `styles/EnterpriseDocs/LatencyMetrics.yml` (`existence`)
Memastikan penulisan unit latensi dan kapasitas sistem mengikuti standar SI dan konsisten (mencegah format "10ms", "10 ms.", atau "10 milli-seconds").

```yaml
extends: existence
message: "Format penulisan latensi tidak valid: '%s'. Gunakan pemisah spasi tunggal dan simbol SI standar (contoh: '10 ms', '2.5 s')."
level: error
scope: text
raw:
  - '\b\d+\s?(?:milli(?:second|sec)s?|ms\.)\b'
  - '\b\d+ms\b'
  - '\b\d+s\b'
```

#### 6.5 Rule 3: `styles/EnterpriseDocs/HeadingPunctuation.yml` (`existence`)
Memastikan judul (*headings*) tidak diakhiri tanda titik, tanda tanya, atau titik dua yang memecah konsistensi struktur navigasi dokumen.

```yaml
extends: existence
message: "Heading tidak boleh diakhiri dengan tanda baca '%s'."
level: error
scope: heading
raw:
  - '[\.\:\;]$'
```

#### 6.6 Vocabularies
`styles/Vocab/Technical/accept.txt`:
```text
Kubernetes
etcd
gRPC
OAuth2
OpenID
Redis
PostgreSQL
systemd
```

`styles/Vocab/Technical/reject.txt`:
```text
K8s
Grpc
postgres
```

#### 6.7 Automasi Test Suite Rule Engine: `tests/test_vale_rules.py`
Skrip Python ini berfungsi untuk memvalidasi bahwa aturan Vale menangkap eror target secara akurat (*true positive*) dan tidak menghasilkan eror pada kalimat yang valid (*true negative*).

```python
"""
Vale Rule Validation Harness.
Menjalankan binary Vale terhadap fixtures teks programatik menggunakan subprocess.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class LintDiagnostic:
    line: int
    column: int
    message: str
    rule: str
    severity: str


class ValeRunner:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration not found at: {config_path}")

    def execute_lint(self, content: str, ext: str = ".md") -> List[LintDiagnostic]:
        with tempfile.NamedTemporaryFile("w+", suffix=ext, delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
            try:
                tmp_file.write(content)
                tmp_file.flush()

                cmd = [
                    "vale",
                    "--config",
                    str(self.config_path.resolve()),
                    "--output=JSON",
                    str(tmp_path.resolve()),
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False
                )

                # Vale mengembalikan returncode 1 jika ditemukan error
                if result.returncode not in (0, 1):
                    raise RuntimeError(f"Vale runtime failure: {result.stderr}")

                raw_output: Dict[str, Any] = json.loads(result.stdout) if result.stdout.strip() else {}
                file_reports = raw_output.get(str(tmp_path.resolve()), [])

                return [
                    LintDiagnostic(
                        line=diag["Line"],
                        column=diag["Span"][0],
                        message=diag["Message"],
                        rule=diag["Check"],
                        severity=diag["Severity"],
                    )
                    for diag in file_reports
                ]
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()


def run_unit_tests() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    vale_config = repo_root / ".vale.ini"
    runner = ValeRunner(config_path=vale_config)

    print("[+] Memulai Assertion Engine Vale Rules...")

    # Test Case 1: Inklusivitas & Terminologi
    bad_text = "You must whitelist the IP and kill the process immediately."
    diagnostics = runner.execute_lint(bad_text)
    assert any("allowlist" in d.message for d in diagnostics), "Gagal mendeteksi 'whitelist'"
    assert any("terminate the process" in d.message for d in diagnostics), "Gagal mendeteksi 'kill the process'"
    print("[PASS] Assertion 1: WordChoice (Substitution) berhasil menangkap pelanggaran.")

    # Test Case 2: Metrik Latensi (Existence)
    bad_latency = "The p99 response time is around 250ms under heavy load."
    diagnostics = runner.execute_lint(bad_latency)
    assert any("EnterpriseDocs.LatencyMetrics" == d.rule for d in diagnostics), "Gagal mendeteksi '250ms'"
    
    good_latency = "The p99 response time is around 250 ms under heavy load."
    diagnostics_good = runner.execute_lint(good_latency)
    assert not any("EnterpriseDocs.LatencyMetrics" == d.rule for d in diagnostics_good), "False-positive pada '250 ms'"
    print("[PASS] Assertion 2: LatencyMetrics berhasil memvalidasi format string.")

    # Test Case 3: Heading Punctuation
    bad_heading = "# Architecture Setup Overview.\n\nContent here."
    diagnostics_heading = runner.execute_lint(bad_heading)
    assert any("EnterpriseDocs.HeadingPunctuation" == d.rule for d in diagnostics_heading), "Gagal mendeteksi titik di akhir heading."
    print("[PASS] Assertion 3: HeadingPunctuation berhasil mengisolasi terminal dot.")

    print("[SUCCESS] Seluruh assertion testing suite lulus 100%.")


if __name__ == "__main__":
    run_unit_tests()
```

---

### 7. Edge Cases & Failure Modes

Dalam lingkungan produksi skala besar, kegagalan prose linter umumnya berpusat pada benturan parsing AST dan kesalahan token scoping:

#### 7.1 Inline Code & Link Anchors Traversal
- **Problem**: Vale dapat mengevaluasi terminologi terlarang di dalam inline code block (misalnya: referensi API eksternal `curl --whitelist` atau `def blacklist_ips():`).
- **Mitigasi**: Pastikan rule menggunakan `scope: paragraph` dan mengabaikan tag `code`. Vale secara default mengonversi ` `text` ` menjadi `<code>text</code>` dan memproteksinya dari scope teks umum. Jangan gunakan `scope: raw` jika aturan hanya ditujukan untuk prosa bahasa alami.

#### 7.2 MDX Component Attributes Collisions
- **Problem**: Penggunaan komponen React/JSX di dalam Markdown (MDX) seperti `<Callout title="Whitelist Status">` memicu error parser Blackfriday/Goldmark karena atribut XML diurai sebagai teks biasa.
- **Mitigasi**: Definisikan konfigurasi `TokenIgnores` pada `.vale.ini` menggunakan ekspresi reguler yang mengisolasi komponen tag JSX sebelum pipeline matching dijalankan.

#### 7.3 False Positives pada Hex Strings dan Hash Kriptografi
- **Problem**: Commit hashes (misal: `7fa3b2c`), signature SHA-256, atau string Base64 yang tidak diisolasi dalam backtick akan dideteksi sebagai *spelling errors* atau melanggar aturan terminologi.
- **Mitigasi**: Implementasikan regex pattern universal pada file konfigurasi `IgnoredScopes` atau masukkan regex pendeteksi hash pada `TokenIgnores`:
  ```ini
  TokenIgnores = (\b[0-9a-f]{7,40}\b)
  ```

#### 7.4 Non-Zero Exit Code Pipeline Choking
- **Problem**: Pengenalan rule baru dengan severity `error` pada repositori legacy yang memiliki 10.000+ file akan langsung memutus seluruh deployment pipeline (CI *hard-failing*).
- **Mitigasi**: Gunakan strategi *gradual degradation*: rilis rule baru dengan status `level: suggestion` atau `level: warning`. Manfaatkan argumen flag CLI `--minAlertLevel=error` pada CI runner untuk hanya memblokir PR jika terdapat error kritis.

---

### 8. Trade-offs & Alternatif Solusi

Setiap tool prose linting memiliki kompromi desain arsitektural tersendiri:

| Metrik / Fitur | Vale | Textlint | Proselint | LLM-as-a-Judge (GPT-4 / Claude) |
| :--- | :--- | :--- | :--- | :--- |
| **Runtime & Performance** | Sangat Cepat (Native Go Binary, ~10k wps) | Moderat (Node.js runtime, parsing berbasis AST) | Lambat (Python native, regex-heavy) | Sangat Lambat (Network I/O bound, ratusan ms per request) |
| **Determinisme** | 100% Deterministik | 100% Deterministik | 100% Deterministik | Non-deterministik (Fluktuatif walau `temp=0`) |
| **Konfigurasi Rule** | Deklaratif YAML (Zero-code) | JavaScript/TypeScript Modules | Hardcoded Python Modules | System Prompt / In-context learning |
| **Konteks Sintaksis Markup** | Luas (Markdown, MDX, AsciiDoc, RST, HTML) | Luas via Markdown AST plugins | Terbatas (Fokus plain-text) | Sangat Luas (Multimodal / Textual) |
| **Biaya Eksekusi (Cost)** | $0 (Open Source, Local Compute) | $0 (Open Source, Local Compute) | $0 (Open Source, Local Compute) | Berbayar per token API ($$$) |
| **Pemahaman Semantik Mendalam** | Terbatas (Bergantung pada pola Regex/Grammar) | Terbatas (Aturan berbasis AST Node) | Rendah (Heuristik gaya klasik) | Sangat Tinggi (Memahami intonasi, sarkasme, konteks logis) |

**Analisis Keputusan**:
Gunakan **Vale** sebagai Quality Gate lini pertama (*L1-Deterministic Gate*) di CI/CD untuk menyaring 95% kesalahan mekanis, kepatuhan terminologi, dan konsistensi brand. Gunakan **LLM-as-a-Judge** hanya pada tahapan *asynchronous review* (L2) untuk menganalisis kepadatan informasi, koherensi logika tingkat tinggi, dan nada tulisan (*tone and voice*).

---

### 9. Best Practices & Standar Industri

1. **Atomic Rule Scope**: Buat satu file YAML untuk satu fungsionalitas unik. Jangan menggabungkan aturan kapitalisasi dan aturan substitusi terminologi dalam satu file yang sama.
2. **Actionable Diagnostic Messages**: Pastikan parameter `message` pada YAML memberikan rekomendasi korektif yang jelas dan menyertakan URL dokumentasi internal standar perusahaan (`link: ...`).
3. **Repository-as-Code Rule Syncing**: Simpan style guide pada repositori terpusat (misalnya `enterprise-vale-styles`). Tarik paket aturan ke repositori target menggunakan fitur *Package Syncing* Vale:
   ```ini
   # .vale.ini
   Packages = https://github.com/enterprise-org/vale-rules/releases/download/v1.2.0/EnterpriseDocs.zip
   StylesPath = styles
   ```
4. **Pre-Commit Integration**: Eksekusi pengujian secara lokal sebelum kode dikirimkan ke remote repository guna mengurangi beban CI compute:
   ```yaml
   # .pre-commit-config.yaml
   repos:
     - repo: https://github.com/errata-ai/vale
       rev: v3.0.5
       hooks:
         - id: vale
           files: \.(md|mdx|adoc)$
   ```

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda adalah Lead Technical Architect pada platform analitik data AI. Dokumentasi teknis sistem Anda memiliki banyak inkonsistensi penulisan format metrik performa dan istilah arsitektur. Anda ditugaskan untuk mengimplementasikan custom rule Vale guna menegakkan standar penulisan secara lokal dan mengotomatisasikannya di GitHub Actions CI.

#### Langkah 1: Setup Workspace & Install Vale
```bash
mkdir vale-lab && cd vale-lab
mkdir -p styles/Enterprise/Vocab/Tech styles/Enterprise/rules

# Verifikasi instalasi binary Vale (minimal v3.0.0+)
vale --version
```

#### Langkah 2: Buat Vocabulary & Acceptance List
Buat file `styles/Enterprise/Vocab/Tech/accept.txt`:
```text
vectordb
Pinecone
LangChain
LlamaIndex
checkpointing
```

Buat file `styles/Enterprise/Vocab/Tech/reject.txt`:
```text
vector-database
pinecone-db
langchain-framework
```

#### Langkah 3: Definisikan Rule Larangan Kata Subjektif (`styles/Enterprise/rules/NoHypeWords.yml`)
Dokumentasi teknis harus objektif. Larang penggunaan kata-kata pemasaran (*hype words*).

```yaml
extends: existence
message: "Hindari kata hiperbolis/subjektif '%s'. Tunjukkan data performa alih-alih klaim tanpa bukti."
level: error
scope: text
ignorecase: true
tokens:
  - blazing fast
  - effortlessly
  - ultra-reliable
  - industry-leading
  - magical
```

#### Langkah 4: Hubungkan Konfigurasi `.vale.ini`
Di root folder `vale-lab/.vale.ini`:
```ini
StylesPath = styles
MinAlertLevel = suggestion

Vocab = Tech

[*.md]
BasedOnStyles = Enterprise
```

#### Langkah 5: Buat File Markdown Berisi Masalah (`docs/test_doc.md`)
```markdown
# High Performance Ingestion Pipeline.

Our architecture leverages an ultra-reliable ingestion worker to synchronize data. 
The vector-database receives payloads effortless and processes them blazing fast.

Ensure you enable checkpointing before executing the batch job.
```

#### Langkah 6: Jalankan Validasi dan Analisis Hasil
Jalankan perintah linter berikut di terminal:

```bash
vale docs/test_doc.md
```

**Ekspektasi Output Terminal**:
```text
docs/test_doc.md
 1:37  error  Hindari kata hiperbolis/subjektif 'ultra-reliable'. Tunjukkan data performa alih-alih klaim tanpa bukti.  Enterprise.NoHypeWords
 3:5   error  Use 'vectordb' instead of 'vector-database'.                                                                Tech.reject
 4:47  error  Hindari kata hiperbolis/subjektif 'blazing fast'. Tunjukkan data performa alih-alih klaim tanpa bukti.    Enterprise.NoHypeWords

✖ 3 errors, 0 warnings, 0 suggestions in 1 file.
```

#### Langkah 7: Otomatisasi GitHub Actions CI Workflow
Buat `.github/workflows/documentation-gate.yml`:

```yaml
name: Documentation Linting Gate

on:
  pull_request:
    paths:
      - '**.md'
      - '**.mdx'

jobs:
  prose-lint:
    name: Execute Vale Rule Engine
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code Repository
        uses: actions/checkout@v4

      - name: Setup Vale CLI
        uses: errata-ai/vale-action@v2
        with:
          version: 3.0.5
          vale_flags: "--minAlertLevel=error"
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Langkah-langkah di atas mengonfigurasi pipeline otomatisasi menyeluruh yang mengevaluasi integritas sintaksis, mematuhi prinsip deterministik, dan siap dioperasikan dalam lingkungan produksi berskala besar.