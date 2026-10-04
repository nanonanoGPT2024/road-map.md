```yaml
---
title: "Bab 01 Modul 01: Docs-as-Code Paradigm, Structured Authoring, dan Automated Delivery Pipelines"
module_id: "TW-MOD-01"
track: "technical-writer"
prerequisites:
  - "Pemahaman dasar Git (branching, pull request, merge)"
  - "Familiaritas dengan terminal/CLI Linux atau macOS"
  - "Pengetahuan sintaks dasar Markdown atau markup language serupa"
target_audience: "Technical Writers, Documentation Engineers, Developer Advocates, Software Engineers"
tags: ["docs-as-code", "vale", "markdownlint", "ci-cd", "structured-authoring", "static-site-generators"]
version: "1.0.0"
---
```

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

- **Menganalisis** defisiensi sistem dokumentasi berbasis WYSIWYG/Wiki tradisional dan merumuskan arsitektur transisi menuju paradigma *Docs-as-Code*.
- **Merancang** sistem dokumentasi terstruktur (*Structured Authoring*) menggunakan lightweight markup (Markdown/MDX/AsciiDoc) dengan pemisahan tegas antara *content*, *presentation*, dan *metadata*.
- **Mengonfigurasi** *automated prose linters* (Vale) dan *structural linters* (markdownlint) untuk menegakkan *style guide* dan konsistensi terminologi secara deterministik.
- **Mengimplementasikan** pipeline CI/CD dokumentasi yang mencakup validasi sintaks, verifikasi tautan rusak (*link checking*), pengujian *code snippet*, dan kompilasi *Static Site Generator* (SSG).
- **Mengevaluasi** risiko *documentation drift* dan mengintegrasikan pengujian unit dokumentasi langsung ke dalam *software delivery lifecycle* (SDLC).

---

### 2. Concept

Dokumentasi teknis adalah artifak rekayasa perangkat lunak kelas satu (*first-class engineering artifact*). Paradigma **Docs-as-Code (DaC)** memperlakukan penulisan, pengelolaan, dan pengiriman dokumentasi dengan metodologi, kultur, dan infrastruktur yang identik dengan kode sumber perangkat lunak:

```
[Software Development]               [Documentation Lifecycle]
Source Code Repository       <--->   Documentation Repository / Monorepo
Branching & Pull Request     <--->   Drafting & Peer Technical Review
Compilers & Linters          <--->   Prose Linters (Vale) & Markup Linters
Unit & Integration Testing   <--->   Link Checkers, Code Snippet Exec Tests
Binary Build & Artifacts     <--->   Static Site Generator (Docusaurus/Hugo)
Deployment to Prod (CI/CD)   <--->   Automated Invalidation & CDN Delivery
```

Dalam model mental Docs-as-Code:
1. **Repository adalah Single Source of Truth (SSoT):** Tidak ada artifak dokumentasi yang hidup di luar version control (Git). Draft tidak disimpan di Google Docs atau Confluence privat; draft adalah *feature branch* atau *draft pull request*.
2. **Review bersifat peer-driven & programmatic:** Penjaminan mutu bahasa dan struktur dilakukan di level mesin (*linters*) sebelum meminta *cognitive effort* dari reviewer manusia melalui Pull Request review.
3. **Dokumentasi terikat dengan rilis kode:** Dokumentasi versi *major*, *minor*, dan *patch* dirilis secara atomik bersamaan dengan rilis biner perangkat lunak untuk mencegah ketidakcocokan informasi (*API drift*).

---

### 3. Why It Matters

Secara historis, dokumentasi dikelola dalam *siloed wikis* (Confluence, Notion) atau dokumen biner tertutup (MS Word, PDF). Pendekatan ini memicu kegagalan sistemik dalam engineering organizations:

*   **Documentation Drift:** Kode mengalami iterasi di Git, sementara dokumentasi di wiki tertinggal berbulan-bulan karena berada di luar jalur *commit* engineer.
*   **Zero Automated Verification:** Tidak ada mekanisme bawaan untuk mendeteksi *broken links*, struktur heading yang melanggar hierarki aksesibilitas, atau contoh kode yang sudah usang (*deprecated*).
*   **Gagal Skala saat Kolaborasi:** Wiki tidak mendukung alur kerja percabangan (*branching*), tinjauan baris-per-baris (*line-by-line diff review*), atau *rollback* yang bersih saat fitur dibatalkan sebelum *merge* ke `main`.
*   **Dampak Finansial:** Menurut studi kontekstual dari Stripe dan GitHub, *bad documentation & API drift* menyumbang hingga 33% waktu terbuang dari kapasitas rekayasa harian insinyur perangkat lunak dalam investigasi bug yang ternyata merupakan kesalahan dokumen.

Menerapkan Docs-as-Code menurunkan *Mean Time to Documentation (MTTD)*, mengeliminasi drift melalui validasi CI, dan menyelaraskan ekosistem kerja *technical writer* langsung di dalam siklus hidup pengembangan sistem.

---

### 4. What It Is

Sistem Docs-as-Code modern terdiri dari empat komponen struktural:

```
+-------------------------------------------------------------------------------+
|                       DOCS-AS-CODE ARCHITECTURE LAYER                         |
+-------------------------------------------------------------------------------+
| 1. Authoring Layer                                                            |
|    - Format    : Markdown (CommonMark/GFM), MDX, atau AsciiDoc               |
|    - Metadata  : YAML/TOML Frontmatter (Title, ID, Tags, Version)             |
|    - Editor    : VS Code, Neovim, JetBrains (ditunjang LSP & Snippets)        |
+-------------------------------------------------------------------------------+
| 2. Quality Assurance Layer (Linting & Testing)                                |
|    - Syntax & Formatting : markdownlint, Prettier                             |
|    - Style & Prose       : Vale (menegakkan Google/Microsoft/Custom Style)    |
|    - Integrity           : lychee (link verification), cspell (typos)         |
|    - Code Correctness    : doctest, runme, tuttle (snippet execution)         |
+-------------------------------------------------------------------------------+
| 3. Engine / Compilation Layer                                                 |
|    - Static Site Gen     : Docusaurus, MkDocs (Material), Starlight (Astro)   |
|    - API Doc Engines     : Redoc, Swagger UI, Mintlify                        |
|    - Asset Optimization  : SVGO, Sharp (WebP/AVIF generation)                 |
+-------------------------------------------------------------------------------+
| 4. Distribution Layer                                                         |
|    - CI/CD Orchestration : GitHub Actions, GitLab CI, Argo Workflows          |
|    - Hosting / Edge      : Cloudflare Pages, AWS S3 + CloudFront, Vercel      |
|    - Search Indexing     : Algolia DocSearch, Pagefind (Local/WASM)           |
+-------------------------------------------------------------------------------+
```

---

### 5. How It Works

Siklus hidup operasional penulisan dokumen berbasis Docs-as-Code bekerja melalui alur deterministik berikut:

```
[Writer/Engineer]
       │
       ▼
 1. Git Branch ────────► Buat branch: `docs/feat-payment-retry-strategy`
       │
       ▼
 2. Local Authoring ───► Tulis teks MDX + Frontmatter
       │                 Run pre-commit hook (Husky/lint-staged)
       │                 ↳ markdownlint & Vale pass locally
       │
       ▼
 3. Push & Open PR ────► Triggers GitHub Actions / GitLab CI Runner
       │
       ▼
 4. Automated CI Run:
       ├─ Step A: Check Prose Quality (Vale)
       ├─ Step B: Check Markup Structural Validity (markdownlint)
       ├─ Step C: Validate Hyperlinks (lychee)
       ├─ Step D: Execute Code Blocks (Verify code doesn't panic)
       └─ Step E: Build SSG Static Artifacts (Docusaurus/Hugo)
       │
       ▼
 5. Ephemeral Preview ─► CI mem-build ephemeral preview URL (misal: Cloudflare Pages preview)
       │                 Reviewer (SME/Tech Lead) memvalidasi substansi teknis
       │
       ▼
 6. Approval & Merge ──► PR di-merge ke branch `main`
       │
       ▼
 7. Production Deploy ─► Production webhook aktif: Artifacts terdistribusi ke CDN,
                         Search engine di-reindex secara atomik via Algolia/Pagefind.
```

---

### 6. ASCII Architecture / Process Diagram

```
                 DEVELOPER / TECHNICAL WRITER WORKSTATION
┌────────────────────────────────────────────────────────────────────────┐
│ IDE (VS Code)                                                          │
│  ├── Document.md (YAML Frontmatter + Content)                          │
│  ├── .vale.ini (Config) ──> Vale CLI (Local Prose Analysis)           │
│  └── .markdownlint.json ──> markdownlint CLI (Structural Check)        │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │ git push origin feat/api-v2-docs
                                     ▼
                      REMOTE GIT REPOSITORY (GITHUB / GITLAB)
┌────────────────────────────────────────────────────────────────────────┐
│ Pull Request Event Triggered                                           │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │ Webhook Trigger
                                     ▼
                   CONTINUOUS INTEGRATION RUNNER (CI ENGINE)
┌────────────────────────────────────────────────────────────────────────┐
│                                                                        │
│  STAGE 1: Static Analysis                                              │
│  ┌──────────────────────┐  ┌─────────────────────┐  ┌────────────────┐ │
│  │ markdownlint-cli2    │  │ Vale Linter         │  │ cspell         │ │
│  │ (Fail on syntax bug) │  │ (Fail on Style/Tone)│  │ (Fail on typo) │ │
│  └──────────┬───────────┘  └──────────┬──────────┘  └────────┬───────┘ │
│             └───────────────────┬─────┴──────────────────────┘         │
│                                 ▼                                      │
│  STAGE 2: Integrity & Code Execution                                  │
│  ┌───────────────────────────────────────────────┐                     │
│  │ lychee (Network Link Check: status != 404)    │                     │
│  ├───────────────────────────────────────────────┤                     │
│  │ doctest / ts-node (Execute code snippets)     │                     │
│  └──────────────────────┬────────────────────────┘                     │
│                         ▼                                              │
│  STAGE 3: Static Compilation                                           │
│  ┌───────────────────────────────────────────────┐                     │
│  │ SSG Build (Docusaurus / MkDocs / Hugo)        │                     │
│  │ Inputs: Raw Markdown + Config + Assets        │                     │
│  │ Outputs: Clean HTML/CSS/JS Directory (dist/)  │                     │
│  └──────────────────────┬────────────────────────┘                     │
│                         ▼                                              │
│  STAGE 4: Deployment & Invalidation                                    │
│  ┌───────────────────────────────────────────────┐                     │
│  │ Upload to S3 Bucket / Cloudflare Pages        │                     │
│  │ Trigger CDN Cache Invalidation                │                     │
│  │ Update Algolia / Pagefind Search Index        │                     │
│  └───────────────────────────────────────────────┘                     │
└────────────────────────────────────────────────────────────────────────┘
```

---

### 7. Core Implementation Pattern 1: Deterministic Prose Linting Engine (Vale)

Vale memvalidasi gaya penulisan layaknya compiler memvalidasi sintaks kode. Kita mendefinisikan ruleset formal untuk melarang jargon, kalimat pasif berlebihan, atau terminologi non-standar.

#### File Konfigurasi: `.vale.ini`
```ini
StylesPath = .github/styles
MinAlertLevel = suggestion

[formats]
mdx = md

[*.md]
BasedOnStyles = Vale, InternalStyle

# Paksa rule tertentu gagal pada level error
InternalStyle.GenderNeutral = error
InternalStyle.Terminology = error
Vale.Spelling = warning
Vale.PassiveVoice = suggestion
```

#### Custom Rule: `.github/styles/InternalStyle/Terminology.yml`
```yaml
extends: substitution
message: "Gunakan terminologi standar: '%s' alih-alih '%s'"
link: "https://internal.wiki/styleguide/terminology"
level: error
ignorecase: true
swap:
  whitelist: allowlist
  blacklist: denylist
  slave: secondary
  master: primary
  kill: terminate
  auth: authentication
```

#### Custom Rule: `.github/styles/InternalStyle/GenderNeutral.yml`
```yaml
extends: existence
message: "Hindari kata ganti gender spesifik '%s'. Gunakan 'they', 'the user', atau struktur pasif objektif."
level: error
ignorecase: true
tokens:
  - he
  - she
  - his
  - her
  - him
```

---

### 8. Core Implementation Pattern 2: Markdown Structural Linting Engine

Untuk menjaga keseragaman format, heading nesting yang benar (penting untuk Screen Reader / WCAG AAA), dan format list seragam, gunakan `markdownlint`.

#### File Konfigurasi: `.markdownlint.json`
```json
{
  "default": true,
  "MD013": false,
  "MD033": {
    "allowed_elements": ["kbd", "details", "summary", "Tabs", "TabItem"]
  },
  "MD024": {
    "siblings_only": true
  },
  "MD025": {
    "level": 1,
    "front_matter_title": "^title\\s*:"
  },
  "MD029": {
    "style": "ordered"
  },
  "MD041": false
}
```

---

### 9. Simple Example: Terstruktur vs Tidak Terstruktur

#### BAD (Format Tradisional / Ad-Hoc Markdown)
```markdown
# Panduan Server
Disini kita akan menyalakan server. User harus memasukkan login mereka he must login first.
Terus install tools ini:
* curl
* git
Lalu jalankan command berikut:
`npm start`
Kalau error klik link ini: http://localhost:8080/internal-wiki/docs
```
*Masalah:* Tidak memiliki metadata frontmatter, menggunakan kata ganti gender spesifik (*he*), menggunakan tautan internal yang rentan mati (*localhost*), dan hierarki penjelasan tidak jelas.

#### GOOD (Structured Markdown with Frontmatter & Semantic Design)
```markdown
---
id: server-initialization
title: Panduan Inisialisasi Server Produksi
sidebar_label: Inisialisasi Server
description: Petunjuk langkah demi langkah untuk mengonfigurasi dan menjalankan runtime server API.
last_updated: 2026-03-31
status: stable
---

Modul ini mendokumentasikan prosedur bootstrap server backend pada lingkungan staging dan produksi.

## Prasyarat Lingkungan

Sebelum memulai eksekusi, pastikan dependensi biner berikut telah terpasang pada host environment:

- **cURL:** Minimal versi `7.88.0`
- **Node.js Runtime:** Versi LTS `22.x`
- **Git Client:** Minimal versi `2.40.0`

## Menjalankan Server

1. Buka terminal lalu eksekusi instalasi dependensi:
   ```bash
   npm clean-install --production
   ```
2. Jalankan runtime server:
   ```bash
   npm start
   ```

:::note Informasi Keamanan
Pastikan seluruh variabel lingkungan (`.env`) telah tervalidasi menggunakan skema Vault sebelum memanggil skrip `start`.
:::
```

---

### 10. Practical Production Example: Production-Ready GitHub Actions Pipeline

Pipeline berikut memverifikasi dokumen secara otomatis pada setiap *Pull Request*: mengecek Markdown style, menjalankan *prose linting* via Vale, memverifikasi tidak ada URL yang putus via Lychee, dan melakukan tes build halaman web.

#### Workflow File: `.github/workflows/docs-validation.yml`
```yaml
name: "Docs Quality & Integration CI"

on:
  pull_request:
    branches: ["main", "release/*"]
    paths:
      - "docs/**"
      - ".github/workflows/docs-validation.yml"
      - ".vale.ini"
      - ".markdownlint.json"
  push:
    branches: ["main"]
    paths:
      - "docs/**"

permissions:
  contents: read
  pull-requests: write

jobs:
  lint-structure:
    name: "Structural Linting (markdownlint)"
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Execute markdownlint-cli2
        uses: DavidAnson/markdownlint-cli2-action@v16
        with:
          globs: "docs/**/*.md"
          config: ".markdownlint.json"

  lint-prose:
    name: "Style Guide & Prose (Vale)"
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Run Vale Action
        uses: errata-ai/vale-action@v2
        with:
          files: 'docs'
          vale_flags: "--minAlertLevel=warning"
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  verify-links:
    name: "Hyperlink Integrity (Lychee)"
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Run Lychee Link Checker
        uses: lycheeverse/lychee-action@v1.9.0
        with:
          args: "--verbose --no-progress --exclude-mail docs/**/*.md"
          fail: true
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  build-test:
    name: "Static Engine Compilation Test"
    runs-on: ubuntu-latest
    needs: [lint-structure, lint-prose, verify-links]
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: 'npm'

      - name: Install Dependencies
        run: npm ci

      - name: Compile Static Site
        run: npm run build
        env:
          NODE_ENV: production
```

---

### 11. Anti-Patterns & Misconceptions

| Anti-Pattern | Mengapa Salah | Rekomendasi Solusi |
| :--- | :--- | :--- |
| **Wiki-Only Documentation** (e.g., Atlassian Confluence tanpa sinkronisasi) | Terisolasi dari PR review kode sumber; menyebabkan fragmentasi versi dan *zero tracking* perubahan arsitektur secara real-time. | Migrasikan dokumentasi arsitektural dan user-facing ke Git repository bersama atau monorepo khusus docs. |
| **Silent Code Block Rot** | Snippet kode ditulis secara manual di teks markdown tanpa adanya pengujian, sehingga kode gagal dieksekusi oleh developer yang membacanya. | Gunakan tool seperti `tuttle` atau `markdown-code-runner` untuk mengeksekusi code snippet dalam CI sebelum merge. |
| **Unversioned Static Documentation** | Dokumentasi hanya merefleksikan branch `main` terbaru, membingungkan pengguna yang masih memakai dependensi versi API sebelumnya. | Implementasikan engine SSG yang mendukung *content versioning* (misal: fitur multi-version Docusaurus). |
| **Manual Style Guide Enforcement** | Menghabiskan waktu engineering lead untuk mengoreksi kapitalisasi, tanda baca, dan format kalimat dalam PR review. | Alihkan seluruh pengecekan mekanistik ke Prose Linter (Vale). Reviewer manusia hanya fokus pada akurasi logika teknis. |
| **Massive Monolithic Documents** | File tunggal berisi ribuan baris instruksi teknis yang membuat *merge conflict* sering terjadi. | Terapkan modularitas konten: pecah dokumen menjadi artikel-artikel kecil berbasis konsep atomik (*Topic-Based Authoring*). |

---

### 12. Trade-offs & Engineering Decisions

Dalam mengadopsi Docs-as-Code, technical writer dan engineering manager harus mengambil keputusan desain arsitektur tooling:

```
FORMAT SELECTION TRADE-OFF MATRIX

Criteria              Markdown (CommonMark)    MDX (Markdown + JSX)     AsciiDoc
──────────────────────────────────────────────────────────────────────────────────
Extensibility         Rendah                   Tinggi (Komponen UI)     Sangat Tinggi
Learning Curve        Sangat Rendah (Universal) Sedang (Butuh JS/React)  Sedang (Sintaks unik)
Tooling Ecosystem     Masif                    Masif di Frontend        Terisolasi (Ruby/Java)
Parsing Performance   Ekstrem Cepat            Sedang (AST Compilation) Cepat
Best Suited For       API Reference umum,      Modern Developer Portals Enterprise Specs,
                      README repositories      & Interactive Guides     O'Reilly/Buku Teknis
```

#### Monorepo vs. Polyrepo Documentation Strategy

*   **Docs in Same Repo (Monorepo with Code):**
    *   *Kelebihan:* Engineer dapat memperbarui kode dan dokumentasi dalam *single atomic pull request*. Mencegah desinkronisasi.
    *   *Kekurangan:* Akses kontributor dokumentasi non-engineer terhalang permission repo kode; CI run dokumentasi dapat memicu/terpicu oleh test kode yang lama.
*   **Decoupled Docs Repository (Dedicated Docs Repo):**
    *   *Kelebihan:* Isolasi total siklus rilis penulisan, kemudahan governance akses technical writer, kecepatan proses CI SSG.
    *   *Kekurangan:* Rawan terjadi desinkronisasi rilis kode dan dokumentasi; membutuhkan integrasi git-submodule atau webhook silang repo.

---

### 13. Failure Modes & Edge Cases

*   **CI Rate-Limiting pada Link Checker:**
    *   *Gejala:* Pipeline CI tiba-tiba gagal pada step `lychee` dengan error HTTP `429 Too Many Requests` ke domain GitHub atau external API.
    *   *Mitigasi:* Tambahkan flag rate limit pada linter, berikan token autentikasi GitHub ke CLI runner, dan cache status tautan eksternal menggunakan file cache lokal artifact CI.
*   **Vale Grammar Engine False Positives:**
    *   *Gejala:* Vale memblokir merge PR karena mendeteksi istilah teknis baru (misal: "Kubernetes pod autoscaling") sebagai *Passive Voice* atau typo.
    *   *Mitigasi:* Definisikan file `accept.txt` lokal (vocab dictionary) per repository untuk mendaftarkan istilah teknis internal perusahaan agar diabaikan oleh spelling checks.
*   **Broken Client-Side Routing via Invalid Slug:**
    *   *Gejala:* Halaman sukses ter-compile di CI, namun menghasilkan 404 / blank page saat diakses via URL di browser production.
    *   *Mitigasi:* Hindari penggunaan karakter non-ASCII, spasi, atau simbol dalam penamaan file markdown atau properti frontmatter `slug`.

---

### 14. Performance & Operational Considerations

1.  **Static Site Build Times:**
    *   Pada repositori dokumentasi skala besar (>5.000 file markdown), engine berbasis Node.js dapat mengalami *out-of-memory* (OOM).
    *   *Solusi:* Gunakan SSG generasi baru berbasis arsitektur Go/Rust (Hugo, Astro/Starlight) atau terapkan *incremental static regeneration* (ISR).
2.  **Asset Optimization Strategy:**
    *   Gambar tangkapan layar (screenshot) resolusi tinggi memperlambat *First Contentful Paint (FCP)*.
    *   *Pipeline Requirement:* Tambahkan otomatisasi kompresi gambar pada pre-commit hook atau CI pipeline yang mengubah PNG/JPEG ke WebP/AVIF secara transparan.

---

### 15. Security & Compliance Implications

*   **Penyusupan Kredensial & Secrets:** Engineer sering tanpa sengaja menempelkan *API keys*, JWT token aktual, atau IP address server internal ke dalam contoh kode markdown.
    *   *Tindakan Preventif:* Terapkan scanner deteksi rahasia (seperti `gitleaks` atau `trufflehog`) ke dalam pipeline verifikasi dokumen.
*   **Data Privasi (PII) dalam Tangkapan Layar:** Screenshot antarmuka dashboard administrasi berisiko membocorkan nama, email, atau transaksi nasabah.
    *   *Tindakan Preventif:* Vale rule untuk mendeteksi nomor kartu kredit (*Luhn algorithm regex*), nomor telepon, atau data sintetis wajib diterapkan di staging CI.
*   **Lisensi Konten Eksternal:** Menyalin snippet dokumentasi dari library pihak ketiga dapat melanggar lisensi open-source (misal: GPL vs MIT).

---

### 16. Verification & Testing Strategies

Uji validasi dokumentasi harus diperlakukan setara dengan *Pyramid Testing*:

```
               /\
              /  \      Manual SME Review (Peer Review via PR)
             /    \     ---------------------------------------
            /      \    End-to-End Build & Visual Regression
           /        \   ---------------------------------------
          /          \  Hyperlink Integrity & Executable Snippets
         /────────────\ ---------------------------------------
        / Static Syntax\ Linter (Vale, markdownlint, cspell)
```

#### Skrip Verifikasi Lokal (Developer Pre-commit Check)
Pastikan setiap writer dapat menjalankan tes deterministik di terminal workstation mereka:

```bash
# 1. Jalankan linter markdown
npx markdownlint-cli2 "docs/**/*.md"

# 2. Jalankan prose linter
vale docs/

# 3. Jalankan verifikasi tautan lokal
lychee --offline docs/**/*.md

# 4. Tes kompilasi SSG lokal
npm run build
```

---

### 17. Best Practices Checklist

#### Day 1 Setup
- [ ] Inisialisasi file `.markdownlint.json` pada root direktori repository.
- [ ] Inisialisasi folder `.github/styles` dan file konfigurasi `.vale.ini`.
- [ ] Tambahkan vocabulary dictionary khusus repo di `.github/styles/config/vocabularies/Internal/accept.txt`.
- [ ] Buat file template `template-guide.md` dengan frontmatter terstandarisasi.

#### Production Pipeline
- [ ] Integrasikan `markdownlint-cli2` dan `vale` di GitHub Actions/GitLab CI.
- [ ] Pasang step link verification (`lychee`) dengan penanganan error rate-limiting.
- [ ] Lindungi branch utama (`main`) via Branch Protection Rules: PR tidak dapat di-merge jika status checks CI docs gagal.
- [ ] Pastikan ephemeral preview URL terbuat otomatis untuk setiap Pull Request.

#### Maintenance
- [ ] Lakukan review berkala terhadap false-positive alert pada Vale dictionary.
- [ ] Audit dan bersihkan dokumen yang di-deprecate melalui redirect rules engine SSG.
- [ ] Monitor ukuran build artifact static docs agar tidak membengkak melampaui batas wajar.

---

### 18. Recommended Tooling & Ecosystem Map

```
CATEGORY             TOOLS                             FUNGSI UTAMA
──────────────────────────────────────────────────────────────────────────────────────────
Markup Standard      CommonMark, MDX, AsciiDoc         Format sumber dokumentasi
Prose Linter         Vale                              Penegakan style guide bahasa teknis
Markup Linter        markdownlint-cli2                 Penegakan sintaks dan struktur heading
Link Checker         lychee, markdown-link-check       Deteksi 404 pada URL lokal & eksternal
Spelling Linter      cspell                            Pemeriksa saltik (typo) terminologi kode
Documentation SSG    Docusaurus, MkDocs Material,      Kompilasi berkas markdown ke web portal
                     Starlight (Astro), Nextra
API Spec Tools       Redocly CLI, Stoplight Elements   Validasi dan rendering OpenAPI/Swagger
Secret Scanner       Gitleaks                          Pencegahan kebocoran secret pada dokumen
```

---

### 19. Self-Assessment & Hands-On Challenge

#### Pertanyaan Evaluasi Pemahaman

1. **Analisis Arsitektural:** Mengapa penulisan dokumentasi dalam format WYSIWYG atau Wiki korporat tradisional rentan terhadap masalah *API Drift* jika dibandingkan dengan model Docs-as-Code?
2. **Desain Linter:** Anda diminta melarang penggunaan kata "gampang", "mudah", atau "simple" dalam dokumentasi karena dianggap bias dan meremehkan kurva belajar pembaca. Bagaimana rancangan spesifikasi rule Vale YAML untuk kebutuhan tersebut?
3. **Pipeline Failure:** Jelaskan apa yang terjadi jika linter mendeteksi *inconsistent heading levels* (misal: melompat dari `## Level 2` langsung ke `#### Level 4`) pada dokumen berkategori public facing? Mengapa markdownlint menandai kondisi ini sebagai pelanggaran berat?

---

#### Hands-On Challenge: Membangun Production Linter Suite

**Skenario:**
Anda bertindak sebagai Lead Documentation Engineer pada startup fintech. Anda ditugaskan membangun pipeline standarisasi penulisan sebelum tim teknis merilis API Payment Gateway.

**Tugas Anda:**
1. Buat direktori project baru dengan struktur berikut:
   ```text
   docs-pipeline/
   ├── .github/
   │   └── styles/
   │       └── TechCorp/
   │           ├── InclusiveLanguage.yml
   │           └── NoHypeWords.yml
   ├── docs/
   │   └── payment-guide.md
   ├── .markdownlint.json
   └── .vale.ini
   ```
2. Konfigurasikan `.markdownlint.json` dengan ketentuan:
   * Heading 1 (`#`) hanya boleh muncul satu kali per dokumen.
   * Tidak boleh ada trailing space di akhir baris.
3. Buat rule Vale `NoHypeWords.yml` yang akan melempar status **error** bila menemukan kata: `super-fast`, `ultra-secure`, `magically`, atau `effortless`.
4. Buat file `docs/payment-guide.md` yang sengaja memicu salah satu rule tersebut, lalu jalankan Vale di terminal Anda dan tangani hingga return code bernilai `0` (clean).

**Kriteria Keberhasilan:**
* File `.vale.ini` dapat memetakan folder style tanpa *parsing error*.
* Menjalankan perintah `vale docs/payment-guide.md` di terminal berhasil mengidentifikasi kata terlarang dan memberikan substitusi atau instruksi perbaikan yang jelas.
* Menjalankan perintah `markdownlint-cli2 "docs/**/*.md"` berhasil memvalidasi hierarki dokumen tanpa adanya syntax warning.