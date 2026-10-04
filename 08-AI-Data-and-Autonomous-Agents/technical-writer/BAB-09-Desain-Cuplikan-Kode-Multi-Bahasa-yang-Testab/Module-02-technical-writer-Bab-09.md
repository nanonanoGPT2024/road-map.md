# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 09: Desain Cuplikan Kode Multi-Bahasa yang Testable**  
**Jalur: AI, Data, and Autonomous Agents — Technical Writing & Documentation Engineering**

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Mendesain Arsitektur *Doc-as-Code* Multi-Bahasa**: Membangun topologi pipeline yang mengekstrak, menguji, dan menyinkronkan cuplikan kode (*code snippets*) secara otomatis antara repositori SDK polyglot dan portal dokumentasi pengembang (*developer portal*).
- **Mengimplementasikan Transklusi Berbasis Tag & AST**: Mengembangkan mesin ekstraksi kode yang memanfaatkan *Abstract Syntax Tree* (AST) dan *marker tokens* (`[START region]` / `[END region]`) tanpa merusak sintaks asli, inferensi tipe, atau *linter* kode sumber.
- **Mengotomatisasi Pengujian Snippet Skala Enterprise**: Menjalankan *matrix testing* terisolasi untuk bahasa Go, TypeScript, dan Python menggunakan runner kontainer sementara (*ephemeral runner*), *mock server*, dan injeksi kredensial dinamis.
- **Mendeteksi dan Memitigasi *Documentation Drift***: Menerapkan mekanisme CI/CD gate berbasis Git diff dan checksum semantic untuk mencegah publikasi dokumentasi ketika sampel kode gagal dikompilasi atau diverifikasi terhadap API spec (OpenAPI/gRPC).

---

## 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Pemrograman Multi-Bahasa Tingkat Menengah**: Sintaks dasar, manajemen dependensi, dan *testing framework* pada Python (Pytest), Node.js/TypeScript (Vitest/Jest), dan Go (`testing` package).
- **Containerization & CI/CD Pipelines**: Docker, Docker Compose, GitHub Actions runner, serta manipulasi volume dan env variables.
- **Prinsip Dasar Docs-as-Code**: Markdown/MDX, static site generators (Docusaurus/Nextra/Astro Starlight), dan Git branching workflow.
- **Konsep API Mocking**: Pemahaman tentang HTTP stubbing, WireMock, Prism (OpenAPI), atau server mock berbasis contract test.

---

## 3. Concept & Internal Architecture

Dokumentasi teknis kelas enterprise menolak model penulisan manual di mana sampel kode disalin langsung (*copy-pasted*) ke dalam file Markdown. Pendekatan manual menyebabkan degradasi kualitas berupa **documentation drift** (kondisi di mana dokumentasi menyimpang dari perilaku sistem aktual akibat perubahan SDK atau *breaking change* pada API publik).

### Arsitektur "Single Source of Truth" (SSOT) Snippet Testing

Arsitektur produksi modern memisahkan penulisan dokumentasi menjadi tiga lapisan terisolasi:

1. **Testable Codebase Repository (Source of Truth)**:
   Setiap sampel kode merupakan program mandiri (*fully compileable and executable unit*) atau modul tes fungsional yang berada di repositori SDK resmi. Kode ini dilengkapi dependensi nyata, *unit assertion*, dan penanda wilayah (*region markers*).
2. **Extraction & Normalization Engine**:
   Mesin CLI (*parser*) membaca berkas sumber, mengurai AST untuk memverifikasi validitas sintaksis, mengekstrak blok kode di antara token batas, menormalkan indentasi (*dedent*), dan menghasilkan manifes JSON terindeks.
3. **Target Documentation Layer (Transclusion & Rendering)**:
   *Static Site Generator* (SSG) atau MDX engine membaca manifes kode atau mereferensikan berkas via custom macro (misalnya: `<CodeSnippet file="auth_client.py" region="client-init" />`), menggantikan tag secara otomatis pada saat *build-time*.

```
+-----------------------------------------------------------------------------------+
|                        SDK REPOSITORY (Source of Truth)                           |
|                                                                                   |
|  [python/tests/test_auth.py]       [go/auth/auth_test.go]       [ts/src/auth.test.ts]  |
|   +---------------------+        +---------------------+       +--------------------+ |
|   | # [START init]      |        | // [START init]     |       | // [START init]    | |
|   | client = Client()   |        | client := New()     |       | const c = new C(); | |
|   | # [END init]        |        | // [END init]       |       | // [END init]      | |
|   +---------------------+        +---------------------+       +--------------------+ |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|               PIPELINE: EPHEMERAL TESTING & AST VALIDATION ENGINE                 |
|                                                                                   |
|   1. Local WireMock / Prism Container Mock Server Spun Up                         |
|   2. Polyglot Matrix Test (pytest, go test, npm test) Executed                     |
|   3. PASS? -> Trigger Extraction CLI; FAIL? -> Block PR Merge                     |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                     SNIPPET HARVESTER & NORMALIZATION CLI                         |
|                                                                                   |
|   - Strip Boilerplate & Hidden Setup Lines                                        |
|   - Re-indent Snippets based on Base Indentation Level                            |
|   - Generate docs/snippets.json with Hash Signatures                              |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                   DEVELOPER PORTAL BUILD PIPELINE (MDX / SSG)                     |
|                                                                                   |
|   Markdown Source:                                                                |
|   ```python                                                                       |
|   <!-- embed: python/tests/test_auth.py:init -->                                  |
|   ```                                                                             |
|   Transclusion Plugin injects verified, compiled code into static production site  |
+-----------------------------------------------------------------------------------+
```

### Mekanisme AST-Preserving Region Extraction

Penggunaan *comment markers* mentah dapat menghasilkan kode yang rusak jika developer salah menempatkan tag di tengah-tengah blok leksikal (misalnya, di dalam *expression statement*). Mesin AST modern memvalidasi bahwa blok kode yang diekstrak membentuk simpul (*node*) sintaksis yang utuh sebelum mengizinkan proses injeksi ke dalam dokumentasi.

---

## 4. Why & What

| Dimensi | Manual Copy-Paste Documentation | Automated Transcluded Snippet Architecture |
| :--- | :--- | :--- |
| **Akurasi Kode** | Rendah. Berisiko tinggi mengalami error sintaksis (*syntax drift*). | 100% tervalidasi. Kode wajib lolos uji kompilasi dan eksekusi pada CI. |
| **Beban Perawatan** | Eksponensial seiring bertambahnya bahasa SDK ($O(N \times M)$). | Konstan ($O(1)$ untuk tim teknis dokumentasi). Update otomatis mengikuti SDK. |
| **Kredensial & Secrets** | Rentan membocorkan token nyata atau konfigurasi *hardcoded*. | Aman. Menggunakan environment variables terisolasi pada test harness. |
| **Developer Experience** | Frustrasi tinggi saat sampel kode *copy-paste* menghasilkan `undefined`. | *Frictionless onboarding*. Sampel kode dapat langsung disalin dan dijalankan. |

---

## 5. How (Workflow Detail)

Alur kerja transklusi kode multi-bahasa dari penulisan hingga deployment:

```
[Developer edits SDK code] 
          │
          ▼
[Commit & Push to Feature Branch]
          │
          ▼
[CI Matrix: Run Unit & Integration Tests against Mock API]
    ├── Python: pytest tests/snippets/
    ├── Go: go test ./snippets/...
    └── TypeScript: npm run test:snippets
          │
     (All Pass?)
     ├── NO  ──> [Fail Pipeline with Diagnostic Log]
     └── YES ──> [Run snippet-extractor CLI]
                      │
                      ▼
         [Generate AST-Validated Snippet Manifest]
                      │
                      ▼
         [Git Submodule Sync / API Dispatch to Doc Repo]
                      │
                      ▼
         [Documentation Build: Transclude Snippets into MDX]
                      │
                      ▼
         [Deploy Developer Portal to Staging/Production]
```

---

## 6. Analogy & Architecture Diagram

### Analogi: Dapur Restoran Bintang Lima vs. Buku Resep Manual

Bayangkan buku resep (*documentation*) yang mencantumkan takaran dan suhu oven yang salah ketik. Pengunjung (*developer*) yang mencoba resep tersebut akan mendapati makanannya hangus. 

Arsitektur *testable snippet* bekerja seperti dapur uji coba modern: setiap resep yang dicetak ke dalam buku adalah rekaman *video dan log* dari koki yang baru saja selesai memasak hidangan tersebut secara nyata menggunakan bahan yang ada. Jika hidangan gagal dimasak di dapur uji coba (*CI pipeline gagal*), buku resep dilarang dicetak (*build deployment ditahan*).

```
Dapur Uji Coba (SDK Repo)               Penerbitan Buku Resep (Doc Portal)
┌────────────────────────────┐          ┌────────────────────────────┐
│ def test_create_order():   │          │ # Membuat Pesanan Baru     │
│   # [START recipe]         │          │                            │
│   order = Order(qty=2)     │ ───────> │ ```python                  │
│   assert order.cook()      │          │ order = Order(qty=2)       │
│   # [END recipe]           │          │ ```                        │
└────────────────────────────┘          └────────────────────────────┘
         Verified by                             Read by
     Continuous Testing                    External Developers
```

---

## 7. Implementation Examples

### 7.1. Simple Example: Marked Python Source Code

Kode sumber asli yang dapat diuji (`sdk/python/tests/test_snippets.py`):

```python
"""Sample test suite demonstrating snippet isolation."""
import os
import pytest
from payment_sdk import Client, PaymentIntent

def test_charge_lifecycle():
    api_key = os.getenv("TEST_API_KEY", "mock_key_12345")
    
    # [START payment_create_intent]
    client = Client(api_key=api_key)
    
    intent = client.payment_intents.create(
        amount=5000,
        currency="usd",
        payment_method_types=["card"],
        idempotency_key="snippet_run_txn_001"
    )
    # [END payment_create_intent]
    
    # Assertions run in CI, but are omitted from documentation extraction
    assert intent.status == "requires_payment_method"
    assert intent.amount == 5000
```

---

### 7.2. Practical Example: Enterprise Multi-Language Extractor & Verifier Engine

Berikut adalah implementasi *pipeline utility* berbasis Python (`tools/snippet_engine.py`) yang menangani ekstraksi *whitespace-normalized*, verifikasi integritas tanda tag, dan injeksi berkas MDX secara otomatis.

```python
#!/usr/bin/env python3
"""
Enterprise Code Snippet Transclusion Engine.
Author: Platform Documentation Engineering Team.
"""

import sys
import re
import os
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional

START_REGEX = re.compile(r"^[ \t]*(?://|#|/\*|<!--)[ \t]*\[START\s+([a-zA-Z0-9_-]+)\]")
END_REGEX = re.compile(r"^[ \t]*(?://|#|/\*|<!--)[ \t]*\[END\s+([a-zA-Z0-9_-]+)\]")
TRANSCLUDE_MARKER = re.compile(
    r"^[ \t]*<!--\s*transclude:\s*([a-zA-Z0-9_.-]+)\s+snippet:([a-zA-Z0-9_-]+)\s*-->",
    re.MULTILINE
)

class SnippetExtractor:
    def __init__(self, search_dir: str):
        self.search_dir = Path(search_dir)
        self.registry: Dict[str, Dict[str, str]] = {}

    def extract_from_file(self, file_path: Path) -> None:
        """Parses a file line by line to extract marked regions."""
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        active_regions: Dict[str, List[str]] = {}
        file_key = file_path.name

        for line_no, line in enumerate(lines, 1):
            start_match = START_REGEX.search(line)
            if start_match:
                tag = start_match.group(1)
                if tag in active_regions:
                    raise ValueError(f"Duplicate START tag '{tag}' at {file_path}:{line_no}")
                active_regions[tag] = []
                continue

            end_match = END_REGEX.search(line)
            if end_match:
                tag = end_match.group(1)
                if tag not in active_regions:
                    raise ValueError(f"Unmatched END tag '{tag}' at {file_path}:{line_no}")
                
                # Normalize and register snippet
                extracted_code = self._normalize_indentation(active_regions[tag])
                if file_key not in self.registry:
                    self.registry[file_key] = {}
                self.registry[file_key][tag] = extracted_code
                del active_regions[tag]
                continue

            # Record lines to all currently active regions
            for tag in active_regions:
                active_regions[tag].append(line)

        if active_regions:
            unclosed = list(active_regions.keys())
            raise ValueError(f"Unclosed snippet region(s) in {file_path}: {unclosed}")

    def _normalize_indentation(self, lines: List[str]) -> str:
        """Removes common leading indentation while preserving relative layout."""
        while lines and lines[0].strip() == "":
            lines.pop(0)
        while lines and lines[-1].strip() == "":
            lines.pop()

        if not lines:
            return ""

        # Calculate minimum indentation of non-empty lines
        non_empty = [line for line in lines if line.strip()]
        if not non_empty:
            return ""

        min_indent = min(len(line) - len(line.lstrip(" ")) for line in non_empty)
        normalized = [line[min_indent:] if len(line) >= min_indent else line for line in lines]
        return "".join(normalized)

    def scan_all(self, extensions: List[str]) -> None:
        for ext in extensions:
            for p in self.search_dir.rglob(f"*.{ext}"):
                self.extract_from_file(p)

    def save_manifest(self, output_file: str) -> None:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(self.registry, f, indent=2)


class TransclusionEngine:
    def __init__(self, manifest_file: str):
        with open(manifest_file, "r", encoding="utf-8") as f:
            self.registry = json.load(f)

    def transclude_markdown(self, doc_file: Path) -> str:
        """Replaces snippet transclusion comments with source of truth code."""
        with open(doc_file, "r", encoding="utf-8") as f:
            content = f.read()

        def replacer(match):
            file_name = match.group(1)
            tag = match.group(2)

            file_data = self.registry.get(file_name)
            if not file_data:
                raise KeyError(f"Transclusion Error: File '{file_name}' not in manifest.")
            
            snippet = file_data.get(tag)
            if not snippet:
                raise KeyError(f"Transclusion Error: Tag '{tag}' not found in '{file_name}'.")

            # Preserve the transclusion comment above the injected code for traceability
            return f"<!-- transclude: {file_name} snippet:{tag} -->\n{snippet.rstrip()}"

        updated_content = TRANSCLUDE_MARKER.sub(replacer, content)
        return updated_content


def main():
    parser = argparse.ArgumentParser(description="Snippet Extraction and Transclusion Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Extraction subcommand
    extract_parser = subparsers.add_parser("extract")
    extract_parser.add_argument("--source", required=True, help="SDK test codebase directory")
    extract_parser.add_argument("--out", required=True, help="Output manifest.json path")
    extract_parser.add_argument("--exts", default="py,go,ts,js", help="Comma-separated extensions")

    # Ingestion subcommand
    inject_parser = subparsers.add_parser("inject")
    inject_parser.add_argument("--manifest", required=True, help="Input manifest.json path")
    inject_parser.add_argument("--docs", required=True, help="Target markdown files directory")

    args = parser.parse_args()

    if args.command == "extract":
        extractor = SnippetExtractor(args.source)
        extractor.scan_all(args.exts.split(","))
        extractor.save_manifest(args.out)
        print(f"Extraction successful: Manifest saved to {args.out}")

    elif args.command == "inject":
        engine = TransclusionEngine(args.manifest)
        doc_dir = Path(args.docs)
        for md_file in doc_dir.rglob("*.md"):
            new_text = engine.transclude_markdown(md_file)
            with open(md_file, "w", encoding="utf-8") as f:
                f.write(new_text)
            print(f"Transcluded: {md_file}")


if __name__ == "__main__":
    main()
```

---

## 8. Real World Case Study: Payment Processing Enterprise (Stripe/Adyen Style)

### Konteks Permasalahan
Sebuah institusi fintech multinasional mengelola SDK resmi dalam 6 bahasa (Python, Go, Node.js, Java, Ruby, C#). Rata-rata tim dokumentasi menerima **40+ tiket komplain per bulan** dari developer eksternal karena sampel kode di portal dokumentasi gagal dijalankan (*outdated signatures*, *missing required idempotency headers*, dan *unhandled API error states*).

### Arsitektur Solusi
Tim Platform Documentation merekayasa ulang arsitektur dokumentasi dengan strategi:
1. **Isolated Submodule Monorepo**: Kode sampel dipindahkan sepenuhnya ke dalam repositori masing-masing SDK di bawah folder standar: `tests/documentation/`.
2. **Ephemeral Contract Validation**: Setiap commit di repositori SDK menjalankan container ephemeral berisi [Prism Mock Server](https://stoplight.io/open-source/prism). Prism memvalidasi *request payload* dan *headers* yang dikirimkan oleh snippet terhadap OpenAPI Specification (OAS) v3.1 resmi.
3. **Automated Cross-Repo Sync**: Ketika pipeline SDK lolos:
   - File biner `snippet-extractor` mengekstrak blok regional dan menyimpannya ke `manifest.json`.
   - GitHub Actions memicu event `repository_dispatch` ke repositori Portal Dokumentasi.
   - Portal Dokumentasi menjalankan transklusi dan membuka *Automated PR* jika terdeteksi diff kode.

### Metrik Hasil Transformasi
- **Dokumentasi Usang**: Turun dari $28\%$ menjadi $0\%$ (drift sepenuhnya dieliminasi).
- **Waktu Resolusi Breaking Changes**: Dipercepat dari **7 hari kerja** menjadi **25 menit** (segera setelah SDK lolos build, dokumentasi otomatis diperbarui via PR otomatis).
- **Customer Support Deflection**: Tiket komplain terkait sampel kode API berkurang sebesar $94\%$ dalam kuartal pertama.

---

## 9. Trade-Offs & Edge Cases

| Pilihan Pendekatan | Keuntungan | Kerugian & Konsekuensi | Mitigasi Engineering |
| :--- | :--- | :--- | :--- |
| **AST-Based Extraction vs. Regex Markers** | Mendeteksi *incomplete syntax blocks* dan deklarasi tipe secara semantik. | Parsing AST bergantung pada parser tiap bahasa (overhead tinggi; setup runtime kompleks). | Gunakan parser AST di level SDK, sementara pipeline docs cukup mengonsumsi intermediate manifest JSON. |
| **Live Backend vs. Containerized Mock API** | Snippet menguji integritas jaringan nyata dan state database produksi. | Flaky network, biaya infrastruktur tinggi, data pollution, dan latensi CI sangat lambat. | Standardisasi pengujian snippet menggunakan *deterministic contract mock* (Prism, MSW, WireMock). |
| **Build-Time Transclusion vs. Runtime Client Fetch** | Zero-latency rendering, SEO optimal, Markdown kompatibel di semua renderer. | File static documentation membengkak jika terdapat puluhan ribu snippet varian bahasa. | Terapkan bundle splitting per tab bahasa dan kompresi gzip/brotli di level CDN edge worker. |

---

## 10. Common Mistakes & Troubleshooting

### 1. The "Hidden Setup Leak"
*Kesalahan*: Menampilkan kode inisialisasi lingkungan (misal: parsing command-line args, TLS certificate loading) di dalam snippet dokumentasi yang ditujukan bagi pemula.  
*Solusi*: Bungkus instruksi setup dalam test setup fixtures atau letakkan di luar marker `[START]` dan `[END]`. Hanya tampilkan logika inti (*core intent*) pada dokumentasi.

### 2. Async Lifecycle & Hanging Snippet Tests
*Kesalahan*: Menjalankan snippet asynchronous (Node.js/Go goroutines) tanpa *timeout control* atau *wait groups*, menyebabkan CI runner mengalami freeze/deadlock tak terbatas.  
*Solusi*: Terapkan parameter timeout yang ketat pada konfigurasi runner testing:
```json
// package.json snippet runner test config
{
  "test:snippets": "vitest run --test-timeout=3000 --bail=1"
}
```

### 3. Whitespace & Indentation Collapse
*Kesalahan*: Memotong kode dari dalam metode kelas (*nested class method*), sehingga saat disalin ke Markdown, indentasi dimulai dari spasi ke-8. Hal ini merusak format bahasa berbasis *whitespace-sensitive* seperti Python dan YAML.  
*Solusi*: Gunakan algoritma *left-dedent normalization* berbasis minimum leading space seperti yang diimplementasikan pada fungsi `_normalize_indentation` di Bab 7.2.

---

## 11. Best Practices & Production Checklist

### Pre-Commit / Local Development
- [ ] Tag penanda wilayah menggunakan sintaks baku: `[START namespace_snippet_name]` dan `[END namespace_snippet_name]`.
- [ ] Sampel kode multi-bahasa menggunakan skema penamaan region yang identik di semua bahasa (misal: `create_user_quickstart`).
- [ ] Snippet diverifikasi berjalan mandiri tanpa variabel global terselubung.

### CI/CD Pipeline
- [ ] Mock server API spec (OpenAPI/gRPC) dijalankan di level loopback lokal runner.
- [ ] Linter bahasa SDK dijalankan secara ketat (misal: `mypy --strict`, `golangci-lint`, `eslint`).
- [ ] Skrip deteksi tag memvalidasi tidak ada unclosed markers atau duplikasi identitas region.
- [ ] Deteksi *drift*: Pipeline memblokir merge PR SDK jika terjadi perubahan signature tanpa memperbarui cuplikan kode dokumentasi.

### Portal Rendering Engine
- [ ] Injeksi transklusi bersifat idempotent: eksekusi berulang tidak menduplikasi teks atau merusak Markdown asli.
- [ ] Setiap blok kode dilengkapi metadata copy-button dan tautan langsung ke file sumber di GitHub/GitLab SDK.

---

## 12. Hands-on Practice: Membangun Snippet Test Harness

Simpan seluruh artefak praktikum ini di direktori: `hands-on/m02/`

### Struktur Direktori
```
hands-on/m02/
├── docs/
│   └── quickstart.md
├── sdk/
│   ├── python/
│   │   ├── requirements.txt
│   │   └── test_client.py
│   └── typescript/
│       ├── package.json
│       └── client.test.ts
└── tools/
    └── snippet_engine.py
```

### Langkah 1: Persiapan Target Markdown (`docs/quickstart.md`)
Buat file dokumentasi yang siap menerima transklusi:

```markdown
# Panduan Inisialisasi Klien API

Gunakan contoh berikut untuk menginisialisasi sesi SDK Anda:

=== "Python"
```python
<!-- transclude: test_client.py snippet:client_init -->
```

=== "TypeScript"
```typescript
<!-- transclude: client.test.ts snippet:client_init -->
```
```

### Langkah 2: Pembuatan SDK Python Berbasis Region (`sdk/python/test_client.py`)
```python
import pytest

class MockAPIClient:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.active = True

def test_sdk_init():
    # [START client_init]
    from mock_sdk import MockAPIClient

    client = MockAPIClient(endpoint="https://api.domain.internal/v1")
    # [END client_init]
    
    assert client.active is True
```

### Langkah 3: Eksekusi Tooling
Jalankan ekstraksi dan injeksi menggunakan CLI dari Seksi 7.2:

```bash
# 1. Ekstrak kode SDK ke manifest
python3 tools/snippet_engine.py extract --source ./sdk --out ./manifest.json

# 2. Periksa hasil manifest.json
cat ./manifest.json

# 3. Transklusikan snippet yang lolos verifikasi ke dalam dokumen
python3 tools/snippet_engine.py inject --manifest ./manifest.json --docs ./docs

# 4. Verifikasi perubahan pada docs/quickstart.md
cat ./docs/quickstart.md
```

---

## 13. Exercises

### Level: Easy
Buat ekspresi reguler (*regular expression*) pada unit parser yang mampu mendeteksi penanda region untuk berkas konfigurasi YAML dan shell script:
- Pola: `# [START region_id]` dan `# [END region_id]`.
- Pastikan whitespace sebelum tanda `#` ditoleransi.
*Kriteria Sukses*: Regex mengembalikan string ID region secara presisi dari input: `"   #  [START custom_config_v1]  "`.

### Level: Medium
Modifikasi fungsi `_normalize_indentation` pada `snippet_engine.py` untuk menangani tab karakter (`\t`) dengan mengonversinya menjadi 4 spasi standar secara deterministik sebelum proses penghitungan indentasi minimum dilakukan.
*Kriteria Sukses*: Potongan kode yang mengandung variasi campuran spasi dan tab dapat dide-indentasi secara konsisten tanpa menghasilkan indentasi baris negatif atau *IndexError*.

### Level: Hard
Tulis skrip GitHub Actions workflow (`.github/workflows/verify-snippets.yml`) yang:
1. Menjalankan container mock Prism OpenAPI v3.1 di background service.
2. Mengeksekusi Pytest pada direktori `sdk/python/` dan Vitest pada `sdk/typescript/`.
3. Menjalankan mesin transklusi untuk mendeteksi apakah berkas Markdown di `docs/` tertinggal (*stale*).
4. Menolak (*exit status 1*) jika ditemukan diff antara isi dokumentasi hasil build dengan file di dalam repositori Git.
*Kriteria Sukses*: Workflow berhasil mengeksekusi semua tahapan dan memunculkan error deskriptif jika ada developer yang memodifikasi SDK tanpa menyinkronkan dokumen.

---

## 14. Real-World Architectural Challenge

**Konteks Kasus**:  
Platform Autonomous Agents Anda memiliki API streaming berbasis WebSocket dan gRPC. Klien SDK (Go, Python, TypeScript) menggunakan koneksi streaming dua arah (*bidirectional streaming*) yang memerlukan kredensial sesi *ephemeral* dan listener event non-blokir (*event loops*).

**Masalah Arsitektural**:  
Saat ini, contoh kode dokumentasi sering mengalami *deadlock* saat diuji di CI karena program snippet menunggu pesan masuk (*incoming stream messages*) yang tidak pernah dikirim oleh mock HTTP biasa. Akibatnya, tim teknis documentation terpaksa menandai cuplikan kode tersebut dengan tag `// nolint` dan mengabaikan pengujian snippet di CI. Hal ini menyebabkan $45\%$ dari kode streaming di portal publik rusak akibat perubahan protokol protobuf v2.

**Tugas Rekayasa**:  
Rancang arsitektur menyeluruh *Snippet Testing Harness for Asynchronous Bidirectional Streaming*:
1. Rancang topologi infrastruktur CI/CD untuk menyimulasikan server streaming gRPC/WebSocket lokal secara deterministik.
2. Tentukan pola isolasi kode: bagaimana cara menulis cuplikan kode yang mendemonstrasikan konsumsi streaming secara natural bagi pembaca, namun memiliki mekanisme internal *auto-termination* (misal: via context timeout atau interrupt signal injection) agar tes dapat selesai dalam $<2$ detik di CI.
3. Rancang mekanisme pelaporan jika ada salah satu bahasa yang mengalami *event leakage* atau *unhandled channel closing*.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)

1. Mengapa teknik manual *copy-paste* sampel kode dilarang dalam standar modern Documentation Engineering?  
   A. Meningkatkan penggunaan memori server portal dokumentasi.  
   B. Menimbulkan risiko *documentation drift* dan ketidaksesuaian sintaks yang tidak terdeteksi.  
   C. Mengurangi kecepatan kompilasi static site generator secara signifikan.  
   D. Menghalangi mesin pencari (SEO) mengindeks kode sumber.  
   *Jawaban*: **B**. Salin-tempel manual meniadakan keterkaitan siklus hidup antara kode yang dapat dikompilasi dengan representasi teks di dokumentasi.

2. Fungsi utama dari algoritma *left-dedent normalization* dalam ekstraksi cuplikan kode adalah:  
   A. Menghilangkan seluruh spasi di dalam baris kode.  
   B. Menghapus whitespace dasar yang berlebihan tanpa merusak struktur indentasi relatif blok kode.  
   C. Mengonversi semua baris kode ke format single-line minified.  
   D. Mengubah otomatis indentasi spasi menjadi tab.  
   *Jawaban*: **B**. Kode yang diekstrak dari dalam metode kelas akan memiliki indentasi awal yang tinggi. De-indentasi mengembalikan margin kiri ke kolom 0 tanpa merusak relasi indentasi internal.

3. Apa bahaya utama menempatkan tanda `[START]` dan `[END]` langsung di dalam berkas Markdown alih-alih di berkas kode sumber SDK?  
   A. Berkas Markdown tidak dapat dibaca oleh pembaca tunanetra.  
   B. Berkas Markdown tidak dieksekusi oleh test runner SDK, sehingga kode di dalamnya tidak diuji secara riil.  
   C. Markdown parser akan selalu mengubah tag komentar menjadi tag HTML raw.  
   D. Tidak ada pengaruh sama sekali terhadap pipeline.  
   *Jawaban*: **B**. Jika tag diletakkan di Markdown, kode tersebut terisolasi dari *compiler* dan *unit testing framework* native SDK.

4. Token `[START snippet_id]` sebaiknya dibungkus dalam bentuk:  
   A. Sintaks variabel khusus bahasa pemrograman.  
   B. Komentar native sesuai sintaks bahasa sumber (misal: `#` untuk Python, `//` untuk Go/TS).  
   C. String literal di dalam badan fungsi.  
   D. Komentar HTML tanpa memandang jenis bahasa pemrograman.  
   *Jawaban*: **B**. Penggunaan komentar native mencegah error kompilasi dan memungkinkan linter/formatter SDK bekerja normal tanpa modifikasi konfigurasi parser.

5. Apa fungsi dari ephemeral mock server (seperti Prism atau WireMock) dalam CI snippet testing?  
   A. Menyediakan antarmuka visual GUI untuk tim technical writer.  
   B. Menggantikan backend produksi dengan server lokal yang meniru kontrak respons API secara deterministik.  
   C. Menyimpan file manifest JSON hasil ekstraksi ke CDN.  
   D. Mengurangi kebutuhan memori pada static site generator.  
   *Jawaban*: **B**. Ephemeral mock server menjamin snippet dapat berjalan mandiri, cepat, dan deterministik tanpa memerlukan koneksi jaringan eksternal atau mutasi database riil.

---

### Bagian 2: Intermediate (Pilihan Ganda & Analisis Kasus Singkat)

6. Sebuah pipeline ekstraksi snippet melempar error: `Unmatched END tag 'auth_login' at line 42`. Apa akar masalah yang paling mungkin?  
   A. File sumber menggunakan encoding non-UTF8.  
   B. Tag `[END auth_login]` didefinisikan tanpa pasangan `[START auth_login]` sebelumnya di berkas yang sama.  
   C. Versi compiler bahasa SDK sudah usang.  
   D. Mesin Static Site Generator kehabisan memori heap.  
   *Jawaban*: **B**. Logika parser mendeteksi instruksi penutup untuk identitas region yang belum pernah didaftarkan atau dibuka oleh tag `[START]`.

7. Perhatikan potongan kode Go berikut:
   ```go
   // [START client_make_call]
   ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
   defer cancel()
   res, err := client.ExecuteQuery(ctx, req)
   // [END client_make_call]
   if err != nil {
       t.Fatalf("Failed to execute: %v", err)
   }
   ```
   Mengapa assertion `t.Fatalf` sengaja diletakkan **di luar** batas region `client_make_call`?  
   A. Agar developer yang menyalin kode dari dokumentasi tidak mendapatkan dependensi pada testing framework `testing.T`.  
   B. Karena `t.Fatalf` menyebabkan compiler Go gagal mengompilasi snippet.  
   C. Go tidak mengizinkan tanda komentar di dekat pemanggilan fungsi fatal.  
   D. Mengurangi penggunaan spasi pada portal dokumentasi.  
   *Jawaban*: **A**. Pustaka testing adalah boilerplate teknis pengujian internal. Pengguna dokumentasi hanya membutuhkan logika operasional SDK, bukan penanganan test assertion internal.

8. Dalam sistem terdistribusi, strategi apa yang paling efektif untuk menyinkronkan repositori dokumentasi ketika terjadi rilis SDK baru di repositori terpisah?  
   A. Menginstruksikan developer membuat pull request manual ke repositori dokumentasi.  
   B. Menjalankan *scheduled cron job* tiap 24 jam untuk memeriksa diff Git secara global.  
   C. Memanfaatkan webhook `repository_dispatch` pada event rilis SDK untuk memicu ekstraksi dan pembuatan automated PR di repositori dokumentasi.  
   D. Menyimpan seluruh repositori SDK dan portal dokumentasi dalam satu branch yang sama.  
   *Jawaban*: **C**. Pola *event-driven continuous integration* via webhook dispatch menjamin sinkronisasi instan tanpa jeda polling cron dan tanpa intervensi manual manusia.

9. Jika kita menggunakan static site generator modern, risiko utama dari melakukan transklusi snippet secara murni di sisi *client-side browser* via `fetch()` adalah:  
   A. Kode tidak dapat diwarnai (*syntax highlighting*) oleh Prism/Shiki.  
   B. Terjadi *layout shift* (CLS), penurunan skor SEO karena konten tidak ada pada static HTML, dan potensi blokir CORS.  
   C. File kode sumber SDK harus diunggah ke branch publik portal dokumentasi.  
   D. Tidak ada framework yang mendukung JavaScript di browser.  
   *Jawaban*: **B**. Fetch dinamis di runtime browser merusak Web Vitals (CLS tinggi), memperlambat First Contentful Paint (FCP), dan menghambat web scraper mesin pencari membaca sampel kode secara native.

10. Ketika menguji snippet multi-bahasa yang memerlukan kredensial autentikasi, pendekatan mana yang mematuhi prinsip keamanan enterprise?  
    A. Menggunakan API key produksi nyata yang disamarkan (*obfuscated*) menggunakan Base64.  
    B. Menyediakan kredensial dummy melalui environment variables yang disuntikkan oleh Secret Manager pada CI runner terisolasi.  
    C. Menginstruksikan pengujian snippet untuk mengabaikan tahap autentikasi HTTP dengan bypass TLS.  
    D. Menuliskan token akses secara langsung pada baris pertama berkas pengujian.  
    *Jawaban*: **B**. Kredensial tidak boleh ada dalam plaintext kode sumber. Environment variables terisolasi di runner memastikan kode dapat dieksekusi saat pengujian tanpa membocorkan rahasia ke publik.

---

### Bagian 3: Skenario Kasus Produksi

#### Skenario 1: The Broken Import Cascade
Sebuah perusahaan merefaktor SDK Node.js mereka dari CommonJS (`require`) ke ECMAScript Modules (`import`). Kode pengujian di repo SDK lolos validasi, namun portal dokumentasi menampilkan blok kode dengan variabel yang tidak didefinisikan:
```javascript
// Tampilan di portal:
const client = new PaymentClient({ token });
await client.pay();
```
Pengguna komplain bahwa sampel kode menghasilkan error: `ReferenceError: PaymentClient is not defined`.  
*Pertanyaan*: Apa kegagalan arsitektur yang terjadi pada konfigurasi region snippet, dan bagaimana solusinya?  
*Solusi*: Tag region `[START]` ditaruh di bawah baris `import { PaymentClient } from '@corp/sdk';`. Meskipun baris import penting dihilangkan untuk menghemat ruang pada snippet kecil, ketiadaan konteks modul membuat pengguna pemula bingung.  
*Perbaikan Arsitektur*: Terapkan arsitektur multi-region atau region transklusi bertingkat: gunakan region terpisah untuk deklarasi import (`[START import_decl]`) dan satukan ke dalam Markdown menggunakan sistem tab composable, atau tambahkan metadata banner otomatis pada SSG yang mencantumkan dependensi impor yang diperlukan secara presisi.

#### Skenario 2: The Latency Choke on Documentation Monorepo Build
Repositori portal dokumentasi enterprise mengimpor 12.000 snippet dari 8 repositori SDK via Git submodules. Setiap kali terjadi push commit dokumentasi, proses SSG memakan waktu 48 menit karena harus membaca dan mengekstrak ribuan file sumber mentah secara berulang.  
*Pertanyaan*: Bagaimana Anda merekayasa ulang arsitektur build ini agar waktu build dokumentasi turun di bawah 3 menit?  
*Solusi*: 
1. Pindahkan tanggung jawab ekstraksi ke repositori masing-masing SDK (decentralized compilation). Repositori SDK menerbitkan artefak terkompilasi berupa file tunggal `snippets-manifest.json` yang di-versioning pada setiap rilis/merge.
2. Repositori dokumentasi tidak lagi menarik keseluruhan source tree SDK via git submodule, melainkan hanya mengunduh 8 file manifes JSON via CDN/GitHub Releases API.
3. SSG melakukan transklusi berbasis kamus in-memory ($O(1)$ lookup time per snippet), mengeliminasi ribuan operasi file I/O disk traversal.

#### Skenario 3: Cross-Language Semantic Inconsistency
Dalam panduan "Membuat Agen AI Baru", kode Python menggunakan parameter `timeout=30`, sedangkan kode Go menggunakan `timeout := 30 * time.Second`, dan kode TypeScript tidak menyertakan konfigurasi timeout sama sekali sehingga defaultnya bernilai `infinity`. Inkonsistensi ini lolos CI karena masing-masing SDK menguji snippetnya secara terpisah.  
*Pertanyaan*: Mekanisme validasi apa yang harus diterapkan di pipeline arsitektur untuk menjamin keselarasan semantik lintas bahasa?  
*Solusi*: Terapkan **Contract-Driven Cross-Snippet Metadata Testing**. Selain mengeksekusi tes native tiap bahasa, sertakan file metadata deskriptif (misal: `create_agent.meta.yaml`) yang menetapkan *invariant contract assertions* (seperti payload parameter wajib, range timeout, status kembalian). Sebelum dokumen dipublikasikan, sebuah pipeline *Cross-SDK Validator* mencocokkan payload JSON/HTTP log hasil eksekusi snippet di tiap runner terhadap kontrak skema tersebut. Jika salah satu bahasa menghasilkan network trace yang menyimpang, pipeline akan memblokir deployment.

---

## 16. Summary

- **Dokumentasi Modern adalah Perangkat Lunak**: Cuplikan kode pada dokumentasi teknis kelas enterprise harus diperlakukan setara dengan kode produksi: memiliki siklus pengujian, validasi tipe, linting otomatis, dan integrasi CI/CD.
- **Transklusi Berbasis Tag Mengeliminasi Drift**: Pemisahan tegas antara repositori kode (*source of truth*) dan repositori portal (*presentation layer*) yang dihubungkan melalui penanda wilayah regional dan AST extractor menjamin 100% akurasi kode yang ditampilkan ke pengembang eksternal.
- **Pentingnya Normalisasi Deterministik**: Manipulasi indentasi, pemotongan boilerplate setup pengujian, serta sanitasi token rahasia harus ditangani secara otomatis pada lapisan ekstraksi sebelum diinjeksikan ke dalam format Markdown/MDX.
- **Resiliensi Skala Besar Menggunakan Manifest JSON**: Mengurangi beban build time pada sistem dokumentasi berskala besar dapat dicapai dengan mendistribusikan ekstraksi ke level repositori SDK masing-masing dan hanya mentransfer file manifes terkompresi ke mesin *Static Site Generator*.