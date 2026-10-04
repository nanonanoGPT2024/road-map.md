# BAB 03: Standar Industri (Google Developer & Microsoft Style Guide)
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Membedakan** secara granular filosofi arsitektur dokumentasi antara *Google Developer Documentation Style Guide* (GDDSG) dan *Microsoft Writing Style Guide* (MWSG), khususnya dalam konteks dokumentasi sistem *AI, Data, and Autonomous Agents*.
- **Mendesain dan Mengimplementasikan** sistem tata kelola *Docs-as-Code* berbasis *Abstract Syntax Tree* (AST) linter menggunakan Vale untuk menegakkan aturan gaya bahasa industri secara otomatis.
- **Mengembangkan Aturan Kustom (*Custom Style Rules*)** berbasis regex dan pola struktural Markdown untuk mendeteksi deviasi tata bahasa, kalimat pasif, istilah ambigu, dan pelanggaran inklusivitas teknis.
- **Mengintegrasikan Pipeline CI/CD** untuk validasi dokumentasi teknis berkinerja tinggi yang memblokir regresi gaya (*style regression*) pada repositori berskala *enterprise*.
- **Mengoptimalkan Dokumentasi untuk Konsumsi Ganda (*Dual-Target Audience*)**: Pengembang manusia (*human developers*) dan *Large Language Models* (LLM/Agentic RAG) guna meminimalkan ambiguitas semantik pada *knowledge base*.

---

### 2. Prerequisite
Untuk menyerap materi ini secara optimal, peserta wajib menguasai:
- **Git & GitOps Workflow**: Pemahaman mendalam tentang branching strategies, PR workflows, dan pre-commit hooks.
- **Markdown & Extended Syntax**: CommonMark, GFM (GitHub Flavored Markdown), serta struktur frontmatter YAML.
- **Regular Expressions (PCRE)**: Regex tingkat lanjut (lookahead, lookbehind, non-capturing groups).
- **Dasar CI/CD**: Konfigurasi workflow GitHub Actions atau GitLab CI.
- **Pemahaman Konseptual Modul 01**: Familiaritas dasar dengan taksonomi dokumen (Tutorials, How-Tos, Reference, Explanation - Divio Framework).

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi standar industri tidak dapat diserahkan semata-mata pada inspeksi manual (*peer review*). Di tingkat enterprise, kepatuhan terhadap GDDSG dan MWSG harus diabstraksikan menjadi arsitektur komputasional yang dapat diuji (*testable*), deterministik, dan dapat diskalakan.

#### Perbandingan Filosofi: Google vs. Microsoft

| Parameter Teknis | Google Developer Documentation Style Guide | Microsoft Writing Style Guide | Implikasi pada Sistem AI / Data |
| :--- | :--- | :--- | :--- |
| **Fokus Sasaran** | Engineer-first, open-source contributors, API consumers. | Enterprise users, multi-level developers, platform operators. | Google lebih cocok untuk low-level SDK/API; Microsoft unggul pada cloud portal dan integrasi solusi. |
| **Voice & Tone** | Objektif, presisi tinggi, netral, sangat minim metafora. | Hangat, kolaboratif, profesional, berorientasi solusi (*empathetic*). | GDDSG menurunkan entropi token pada context window LLM; MWSG mempermudah onboarding engineer junior. |
| **Penulisan Instruksi** | Berorientasi tugas langsung (*imperative mood*), hilangkan redundansi kata. | Mengarahkan berbasis skenario (*action-oriented*), ramah pengguna. | GDDSG: "Run the binary."<br>MWSG: "To start the service, select **Run**." |
| **Second Person** | Gunakan "you" secara terukur; hindari "we" (kecuali platform action). | Prioritaskan "you"; "we" dihindari kecuali mewakili Microsoft secara legal. | Konsistensi sudut pandang penting agar parser RAG tidak bingung menentukan subjek eksekutor. |
| **Kapitalisasi Judul** | Sentence case (hanya huruf pertama dan *proper noun* kapital). | Sentence case (sejak versi modern; migrasi dari Title case). | Standar global kini konvergen pada *sentence case* untuk kemudahan *tokenization*. |

#### Arsitektur Parsing AST pada Linter Dokumentasi (Vale Engine)

Secara internal, penerapan standar ini tidak bergantung pada pencarian string biasa. Linter industri seperti Vale mengurai dokumen Markdown menjadi representasi pohon sintaksis abstrak (*Abstract Syntax Tree* - AST).

```
                 Dokumen Markdown Mentah (.md)
                              │
                              ▼
                     [ CommonMark Parser ]
                              │
                              ▼
               Pohon Sintaksis Abstrak (AST)
       ┌──────────────────────┼──────────────────────┐
       ▼                      ▼                      ▼
  Node: Heading          Node: Paragraph        Node: CodeBlock
  (Tipe: Title)          (Tipe: Text)           (Tipe: Raw/Pre)
       │                      │                      │
       ├─ [Rule: Sentence]    ├─ [Rule: Passive]     └─ [Rule: NoLint]
       │  (Cek Sentence       │  (Deteksi Bentuk         (Dikecualikan
       │   Case)              │   Pasif via regex)        dari analisis)
       │                      │
       ▼                      ▼
  Vale Diagnostics Engine (Aggregator Kesalahan)
                              │
                              ▼
                  Output Standar (CLI / JSON)
```

Proses eksekusi linter:
1. **Tokenisasi & Parsing**: CommonMark engine memecah dokumen menjadi AST nodes (blok teks, inline code, tautan, heading, list).
2. **Context Filtering**: Engine menentukan cakupan node yang relevan. Aturan gramatikal (misal: pelarangan kalimat pasif) hanya diterapkan pada node `paragraph` atau `list`, dan secara otomatis melewati node `codeblock` serta `inline code` guna menghindari *false positive*.
3. **Regex & Extension Execution**: Pola *rule definition* (YAML) dieksekusi terhadap konten teks bersih (*clean text*) dalam node target.
4. **Action Mapping**: Pelanggaran dipetakan ke tingkat keparahan: `suggestion`, `warning`, atau `error`, yang kemudian dikonversi menjadi exit code CI/CD atau anotasi pada pull request.

---

### 4. Why & What

#### Mengapa Standardisasi Diperlukan?
1. **Reduksi Cognitive Load**: Ketidakkonsistenan terminologi (misal: pertukaran kata "booting", "initializing", "starting", "spinning up" untuk satu proses yang sama) memperlambat pemahaman teknis dan meningkatkan risiko kesalahan eksekusi pada level operasional (*incident rate* naik).
2. **RAG (Retrieval-Augmented Generation) Optimization**: Model bahasa (LLM) yang mengindeks dokumentasi enterprise yang tidak konsisten akan menghasilkan representasi vektor (embeddings) yang terdispersi secara buruk (*high semantic variance*). Hal ini menyebabkan halusinasi pada internal agent pendukung engineer.
3. **Kepatuhan Legal & Inklusivitas**: Istilah non-inklusif (seperti "master/slave", "whitelist/blacklist", "kill process") melanggar standar modern kepatuhan korporat global.

#### Apa yang Dibangun?
Arsitektur penjaminan mutu dokumentasi terotomatisasi (*Automated Quality Assurance for Documentation Pipeline*) yang mengintegrasikan:
- Kamus istilah terpadu (*Enterprise Taxonomy Dictionary*).
- Paket aturan formal berbasis GDDSG dan MWSG.
- Gerbang verifikasi (*Quality Gates*) pada level lokal (*pre-commit*) dan server (*CI/CD Pipelines*).

---

### 5. How (Workflow Detail)

Alur kerja penulisan dan penjaminan mutu dokumentasi mengikuti siklus hidup berikut:

```
[ Engineer/Writer ]
       │
       ▼ (Menulis / Mengubah Dokumen)
[ Local Machine ] ──> Trigger: Git Commit
       │
       ▼ (Git Hook)
[ Pre-commit Runner ] ──> Eksekusi: Vale Local Scan (Diff Only)
       │
   [Lolos?] ──No──> Abort Commit & Tampilkan Baris Kesalahan
       │
      Yes
       ▼
[ Git Push to Remote ]
       │
       ▼ Trigger: Pull Request
[ CI/CD Pipeline Engine ]
       │
       ├─ Step 1: Checkout Repositori
       ├─ Step 2: Sinkronisasi Vale Styles/Vocab Package
       ├─ Step 3: Eksekusi Vale Linting (Full Scope / PR Changes)
       ├─ Step 4: Markdown AST Structural Link Check
       └─ Step 5: Post Annotations ke GitHub/GitLab PR
       │
   [Lolos?] ──No──> Block PR Merge (Status: Failed)
       │
      Yes
       ▼
[ PR Approved & Merged ] ──> Automated Build & Publish to Production Portal
```

---

### 6. Analogy & Diagram ASCII

#### Analogi
Bayangkan menulis dokumentasi seperti merancang sebuah sirkuit listrik cetak (PCB).
- **Markdown** adalah papan PCB dan jalur tembaganya.
- **Kata-kata dan Kalimat** adalah komponen aktif (resistor, kapasitor, IC).
- **Google/Microsoft Style Guide** adalah spesifikasi toleransi kelistrikan (tegangan maksimum, jarak antar konduktor).
- **Vale / Linter** adalah mesin *Automated Optical Inspection* (AOI) di pabrik perakitan. Jika resistor dipasang terbalik (kalimat pasif) atau tegangan berlebih (menggunakan istilah ambigu seperti "mudah" atau "tentunya"), mesin AOI langsung menghentikan ban berjalan sebelum produk sampai ke tangan konsumen.

#### Diagram Topologi Arsitektur CI/CD Multi-Repo

```
+---------------------------------------------------------------------------------+
|               CENTRAL REPO: "enterprise-docs-engineering-standard"              |
|                                                                                 |
|  - Vale Rules (Google-Extended, Microsoft-Extended)                            |
|  - Enterprise Shared Vocabulary (accept.txt, reject.txt)                        |
|  - Release Management (Semantic Versioning: v1.4.0)                             |
+----------------------------------------+----------------------------------------+
                                         │
                         Distribusi Paket via GitHub Releases / OCI
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        ▼                                ▼                                ▼
+--------------------+         +--------------------+         +--------------------+
|  Agent-Core Repos  |         | Data-Pipeline Repo |         | Developer-Portal   |
|                    |         |                    |         |                    |
|  .vale.ini         |         |  .vale.ini         |         |  .vale.ini         |
|  (Sync to v1.4.0)  |         |  (Sync to v1.4.0)  |         |  (Sync to v1.4.0)  |
|  CI: vale --minAlert|        |  CI: vale --minAlert|        |  CI: vale --minAlert|
|      error         |         |      error         |         |      error         |
+--------------------+         +--------------------+         +--------------------+
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Konfigurasi `.vale.ini` Minimalis

```ini
StylesPath = styles
MinAlertLevel = suggestion

Packages = Google

[*]
BasedOnStyles = Vale, Google
```

#### Practical Example: Konfigurasi Enterprise Production-Ready

Struktur konfigurasi tingkat lanjut yang mengintegrasikan standar Google dengan kustomisasi internal khusus sistem AI/Autonomous Agents.

##### File: `.vale.ini`
```ini
StylesPath = .github/styles
MinAlertLevel = warning

# Mengambil paket eksternal resmi
Packages = Google, Readability, proselint

Vocab = EnterpriseAI

[formats]
mdx = md

[*.md]
BasedOnStyles = Vale, Google, EnterpriseAI

# Override aturan bawaan Google sesuai toleransi korporat
Google.WordList = NO
Google.Passive = error
Google.FirstPerson = error
Google.Exclamation = error

# Tambahkan aturan custom enterprise
EnterpriseAI.DeterministicInstructions = error
EnterpriseAI.InclusiveTerminology = error
EnterpriseAI.AIAgentNomenclature = error

# Kecualikan bagian tertentu dari validasi ketat
[*(CHANGELOG|RELEASE_NOTES).md]
Google.Passive = suggestion
EnterpriseAI.DeterministicInstructions = NO
```

##### File: `.github/styles/EnterpriseAI/DeterministicInstructions.yml`
Aturan untuk mencegah instruksi non-deterministik pada panduan teknis agent.

```yaml
extends: existence
message: "Hindari frasa ambigu '%s'. Berikan parameter metrik atau instruksi deterministik langsung."
link: "https://handbook.enterprise.internal/style-guide#determinism"
level: error
scope: paragraph
raw:
  - '(?i)\bcukup mudah\b'
  - '(?i)\bdengan cepat\b'
  - '(?i)\bhanya perlu\b'
  - '(?i)\btinggal jalankan\b'
  - '(?i)\bmungkin membutuhkan waktu\b'
  - '(?i)\bsecara sederhana\b'
```

##### File: `.github/styles/EnterpriseAI/AIAgentNomenclature.yml`
Aturan penyeragaman istilah domain *Autonomous Agents & Data Engineering* sesuai GDDSG.

```yaml
extends: substitution
message: "Gunakan istilah resmi '%s' alih-alih '%s' untuk menjaga konsistensi RAG."
link: "https://handbook.enterprise.internal/glossary"
level: error
scope: text
ignorecase: true
swap:
  prompt template: prompt template
  vector database: vector database
  hallucinating: generating inaccurate responses
  black box: opaque model
  sanity check: validation check
  master node: primary node
  slave agent: subordinate agent
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Kasus
Platform AI Enterprise "SynapseData" mengelola lebih dari 45 repositori *microservices* dan SDK untuk orkestrasi *autonomous agents*. Tim engineering terdiri dari 350+ engineer lintas negara. Dokumentasi teknis terdistribusi langsung di repositori masing-masing (*Doc-as-Code*).

#### Permasalahan
1. **API Ingestion Error**: SDK docs sering menggunakan istilah berganti-ganti ("API Key", "Secret Token", "Auth Token", "Client Secret"). Engineer integrator mengalami failure rate 18% pada integrasi pertama.
2. **Degradasi Kualitas RAG**: Chatbot support internal (berbasis LLM) yang membaca dokumentasi teknis menghasilkan halusinasi akibat dokumen internal sarat kalimat pasif ambigu (contoh: *"The state is saved periodically"* tanpa kejelasan apakah ini dilakukan oleh worker agent, Redis, atau cron controller).
3. **Review Fatigue**: Staff Tech Writer menghabiskan 65% kapasitas kerja hanya untuk memperbaiki kapitalisasi heading (*Title Case* vs *Sentence Case*) dan typo terminologi pada Pull Request engineer.

#### Solusi Arsitektural
1. **Centralized Style Repository**: Membangun repositori tunggal `synapse-docs-governance` yang mendistribusikan rule pack Vale versi semantik via GitHub Releases.
2. **Dual-Gate Enforcement**:
   - *Shift-Left*: Husky + Lint-staged dipasang di level repositori lokal, menjalankan `vale --ext=.md` hanya pada file yang diubah (*staged files*).
   - *CI Verification*: GitHub Actions workflow paralel yang menjalankan Vale check dengan format anotasi review otomatis langsung pada baris kode PR.
3. **Refactoring Terminologi AI**: Mewajibkan seluruh dokumen instruksi agent menggunakan active voice + imperative verb sesuai GDDSG.

#### Hasil Terukur (Metrics Post-Implementation)
- **Review Cycle Time**: Durasi *turnaround* review dokumen teknis berkurang dari rata-rata 3.2 hari kerja menjadi 4 jam.
- **First-Time Integration Failure**: Berkurang dari 18% ke 2.4% dalam kurun waktu 90 hari.
- **RAG Accuracy**: *Retrieval precision* chatbot engineering internal meningkat dari 62% menjadi 89% karena kalimat pasif turun hingga di bawah 1% dari total *corpus*.

---

### 9. Trade-offs (Analisis Keputusan Teknis)

| Pendekatan | Keuntungan | Kerugian / Risiko | Mitigasi |
| :--- | :--- | :--- | :--- |
| **Strict Blocking CI Gate (Exit 1 on Error)** | Jaminan kepatuhan 100%; repositori dokumentasi selalu steril dari deviasi standar. | Berpotensi menghambat velocity engineer; risiko penolakan (*pushback*) dari tim developer. | Terapkan level `warning` selama fase transisi (30 hari pertama). Hanya aktifkan level `error` untuk pelanggaran kritikal (nomenklatur, inklusivitas). |
| **Monolithic Rules vs Distributed Rules** | Pengelolaan satu pintu; pembaruan instan ke seluruh organisasi. | Dependensi jaringan saat CI run; potensi *breaking changes* masal jika update aturan tidak *backward-compatible*. | Gunakan version pinning berbasis semver pada konfigurasi `.vale.ini` di masing-masing repositori konsumen. |
| **Aggressive Passive Voice Filter** | Kalimat menjadi sangat direct, menghilangkan keraguan subjek tindakan, optimal untuk LLM. | Dokumen terasa kaku; penulisan penjelasan arsitektural kompleks (*Explanation docs*) menjadi sulit. | Batasi aturan `Passive: error` hanya pada direktori `how-to/` dan `api/`. Gunakan `Passive: suggestion` untuk direktori `concepts/` atau `architecture/`. |
| **Regex-based Rules vs Custom AST Code** | Cepat ditulis, mudah dipelihara via YAML sederhana. | Tidak memiliki pemahaman semantik konteks yang mendalam (*context blindness*), rawan false positive. | Eksploitasi fitur `scope` pada Vale secara granular (pisahkan `sentence`, `paragraph`, `heading`, `raw`). |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum (Anti-Patterns)
1. **Regresi Regex Tanpa Boundaries**: Menulis regex `(?i)slave` yang secara tidak sengaja memicu flag pada kata valid seperti `slavic` atau `autoload_slave_records()`.
   *Solusi*: Wajib sertakan word boundaries `\b` -> `(?i)\bslave\b`.
2. **Tidak Mengabaikan Frontmatter dan Code Blocks**: Linter memeriksa metadata Jekyll/Hugo/Docusaurus sehingga build CI gagal karena format ID atau tanggal.
   *Solusi*: Definisikan parser settings pada `.vale.ini` untuk melewati frontmatter.
3. **Vocabulary Collision**: Memasukkan kata baru ke *accept list* umum tanpa segregasi domain, yang mengaburkan typo di modul lain.

#### Panduan Troubleshooting Lapangan

##### Isu 1: CI Build Timeout saat Menjalankan Vale pada Repositori Besar
- **Gejala**: GitHub Actions runner mengalami hang atau timeout (>15 menit) saat mengeksekusi step Vale.
- **Penyebab**: Vale memproses seluruh riwayat berkas tanpa caching atau regex mengalami *catastrophic backtracking*.
- **Investigasi & Resolusi**:
  1. Jalankan profiling lokal: `vale --debug . > debug.log`.
  2. Batasi inspeksi CI hanya pada berkas yang berubah menggunakan parameter reviewdog atau git diff:
     ```bash
     git diff --name-only origin/main HEAD -- '*.md' | xargs vale --config=.vale.ini
     ```

##### Isu 2: False Positive pada Inline Code Snippets
- **Gejala**: Vale memicu *error* "Avoid passive voice" pada blok kode atau perintah CLI seperti `kubectl get pods --sort-by='.metadata.creationTimestamp'`.
- **Penyebab**: Konfigurasi scope tidak mengabaikan tag `code` secara eksplisit.
- **Investigasi & Resolusi**: Pastikan aturan YAML menggunakan `scope: paragraph` atau tambahkan proteksi inline pada Markdown:
  ```markdown
  <!-- vale EnterpriseAI.DeterministicInstructions = NO -->
  Jalankan perintah berikut jika proses booting dirasa lambat.
  <!-- vale EnterpriseAI.DeterministicInstructions = YES -->
  ```

---

### 11. Best Practices (Production Checklist)

#### Pre-flight Configuration
- [ ] Aturan gaya dikunci menggunakan tag rilis semantik (*semantic release tag*), bukan branch `main`.
- [ ] Berkas `.vale.ini` berada di root repositori dengan konfigurasi fallback format yang jelas.
- [ ] Kamus kosa kata (*Vocab*) dipisahkan secara struktural: `accept.txt` (whitelist istilah internal) dan `reject.txt` (istilah yang dilarang keras).

#### Pipeline Optimization
- [ ] Pre-commit hooks (`husky` / `pre-commit`) dipasang untuk mendeteksi error sebelum *push*.
- [ ] Eksekusi linter di CI dipatok target eksekusi < 30 detik untuk incremental changes.
- [ ] Linter terintegrasi dengan anotator PR (misal: GitHub Checks API / Reviewdog) sehingga engineer tidak perlu membaca output log mentah di tab CI.

#### Standard Enforcement
- [ ] Sentence case diberlakukan secara ketat pada semua heading level 1 sampai 6.
- [ ] Kalimat pasif dibatasi hingga maksimum 3% dari total volume kata per dokumen.
- [ ] Seluruh tautan API berstatus absolut atau diverifikasi lewat *link checker action* paralel.

---

### 12. Hands-on Practice

Implementasikan pipeline standardisasi dokumentasi berbasis Vale di dalam folder workspace berikut: `hands-on/m02/`.

#### Langkah 1: Inisialisasi Struktur Direktori
Jalankan di terminal Anda:
```bash
mkdir -p hands-on/m02/.github/styles/Enterprise/
mkdir -p hands-on/m02/.github/styles/Vocab/AI-Platform/
mkdir -p hands-on/m02/docs/
cd hands-on/m02
```

#### Langkah 2: Buat Kamus Kosakata Khusus (Vocab)

File: `.github/styles/Vocab/AI-Platform/accept.txt`
```text
Kubernetes
LangChain
LlamaIndex
PostgreSQL
OpenAI
VectorDB
gRPC
DevOps
APIs
```

File: `.github/styles/Vocab/AI-Platform/reject.txt`
```text
blacklist
whitelist
master
slave
sanity-check
```

#### Langkah 3: Definisikan Custom Style Rules

File: `.github/styles/Enterprise/HeadingSentenceCase.yml`
```yaml
extends: capitalization
message: "'%s' harus menggunakan sentence case sesuai Google Style Guide."
link: "https://developers.google.com/style/capitalization"
level: error
scope: heading
match: $title
exceptions:
  - Kubernetes
  - PostgreSQL
  - LangChain
  - LlamaIndex
  - gRPC
```

File: `.github/styles/Enterprise/PassiveVoiceCheck.yml`
```yaml
extends: existence
message: "Gunakan kalimat aktif. Ubah konstruksi pasif '%s' menjadi imperatif atau tunjukkan subjek pelaksana."
link: "https://developers.google.com/style/voice"
level: error
scope: paragraph
raw:
  - '(?i)\b(?:is|are|was|were|been|being)\s+([a-z]+ed)\b'
  - '(?i)\bdi-(?:eksekusi|jalankan|buat|hapus|baca)\b'
```

#### Langkah 4: Tulis Konfigurasi Pusat `.vale.ini`

File: `.vale.ini`
```ini
StylesPath = .github/styles
MinAlertLevel = warning

Vocab = AI-Platform

[*.md]
BasedOnStyles = Enterprise

Enterprise.HeadingSentenceCase = error
Enterprise.PassiveVoiceCheck = error
```

#### Langkah 5: Buat Dokumen Pengujian (Mengandung Pelanggaran)

File: `docs/agent-deployment.md`
```markdown
# Autonomous Agent Setup And Deployment Guide

This document explains how agents are executed by the cluster.

## Architecture Of The System

The subordinate agent is started automatically. Before launching, a sanity-check must be performed by the developer. It is recommended that you check the vector database.
```

#### Langkah 6: Eksekusi Validasi
Pastikan binary Vale sudah terinstal pada workstation Anda (`brew install vale` atau `apt install vale`).

Jalankan perintah:
```bash
vale docs/agent-deployment.md
```

**Ekspektasi Output Terminal**:
```text
 1:3   error  'Autonomous Agent Setup  Enterprise.HeadingSentenceCase
              And Deployment Guide'
              harus menggunakan
              sentence case sesuai
              Google Style Guide.
 3:37  error  Gunakan kalimat aktif.   Enterprise.PassiveVoiceCheck
              Ubah konstruksi pasif
              'are executed' menjadi
              imperatif atau tunjukkan
              subjek pelaksana.
 5:4   error  'Architecture Of The     Enterprise.HeadingSentenceCase
              System' harus
              menggunakan sentence
              case sesuai Google
              Style Guide.
 7:5   error  'subordinate'            AI-Platform.reject
 7:29  error  Gunakan kalimat aktif.   Enterprise.PassiveVoiceCheck
              Ubah konstruksi pasif
              'is started' menjadi
              imperatif atau tunjukkan
              subjek pelaksana.
 7:60  error  'sanity-check'           AI-Platform.reject
 7:84  error  Gunakan kalimat aktif.   Enterprise.PassiveVoiceCheck
              Ubah konstruksi pasif
              'be performed' menjadi
              imperatif atau tunjukkan
              subjek pelaksana.
```

#### Langkah 7: Refaktor Dokumen Sesuai Standar
Ubah `docs/agent-deployment.md` menjadi:

```markdown
# Autonomous agent setup and deployment guide

This document explains how the cluster executes autonomous agents.

## Architecture of the system

The control plane starts the worker agent automatically. Before launching, validate the agent configuration. We recommend that you check the VectorDB instance.
```

Jalankan kembali:
```bash
vale docs/agent-deployment.md
```
*Hasil: 0 errors, 0 warnings. Lolos validasi enterprise.*

---

### 13. Exercise

#### Level Easy
1. Tambahkan pengecualian (*exception*) untuk singkatan "SLA", "SDK", dan "LLM" pada aturan `.github/styles/Enterprise/HeadingSentenceCase.yml`.
2. Uji aturan tersebut terhadap heading `# Configuring the LLM SDK to meet enterprise SLA`. Pastikan tidak memunculkan *false positive*.

#### Level Medium
1. Buat aturan Vale baru `.github/styles/Enterprise/NoGenderedPronouns.yml` yang mendeteksi penggunaan kata ganti orang ketiga berbasis gender (*he, she, his, her, him*) pada seluruh node Markdown, dan merekomendasikan penggunaan bentuk inklusif (*they, them, their*) sesuai Microsoft Style Guide.
2. Integrasikan aturan ini dengan level keparahan `error`.

#### Level Hard
1. Buat custom rule berbasis Vale Scripting/Regex yang memvalidasi bahwa setiap blok kode Bash (```` ```bash ````) tidak boleh mengandung karakter shell prompt (`$` atau `#`) di awal baris perintah eksekusi, merujuk pada standar Google Style Guide yang mewajibkan kode mudah di-copy-paste secara langsung oleh pengguna.

---

### 14. Challenge

**Skenario**:
Anda memimpin arsitektur dokumentasi pada platform *Autonomous Multi-Agent Swarm Orchestration*. Tim developer terbiasa menggunakan istilah non-deterministik dan gaya penulisan informal pada berkas *Architecture Decision Records* (ADR) dan *API Specs*. 

**Tantangan**:
1. Buat sebuah pipeline validasi Docs-as-Code modular lengkap di GitHub Actions (`.github/workflows/docs-gate.yml`) yang:
   - Menjalankan Vale secara selektif hanya pada berkas `docs/**` dan `*.md` yang termodifikasi di Pull Request.
   - Menggunakan format output Google SARIF (*Static Analysis Results Interchange Format*) untuk diunggah langsung ke tab *Security & Code Scanning* repositori GitHub.
   - Memiliki fail-safe: Jika PR menyentuh folder `docs/architecture-concepts/`, tingkat keparahan kalimat pasif diturunkan (*downgraded*) menjadi `warning`, namun jika menyentuh folder `docs/api-reference/` atau `docs/tutorials/`, tingkat keparahan pasif dinaikkan menjadi `error` absolut yang memblokir proses *merging*.
2. Seluruh aturan harus dibungkus dalam *Dockerized Action runner* agar developer lokal dapat mereproduksi hasil validasi CI identik 100% menggunakan satu perintah CLI.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Berdasarkan Google Developer Documentation Style Guide, manakah penulisan heading yang benar?
   - A. `# Deploying Your First Microservice To Production`
   - B. `# Deploying your first microservice to production`
   - C. `# Deploying Your First Microservice to Production`
   - D. `# Deploying your First Microservice To Production`

2. Mengapa kalimat pasif (*passive voice*) dihindari secara ketat pada dokumentasi teknis modern?
   - A. Karena kalimat pasif membutuhkan token memori LLM lebih sedikit.
   - B. Karena kalimat pasif sering kali menyembunyikan aktor/subjek pengeksekusi instruksi.
   - C. Karena markdown parser tidak mendukung rendering kalimat pasif.
   - D. Karena Google Search Console melakukan de-indexing pada dokumen berkalimat pasif.

3. Di mana letak perbedaan utama antara Google Style Guide dan Microsoft Style Guide terkait *Tone*?
   - A. Google condong lebih hangat dan ramah pengguna; Microsoft fokus pada netralitas mutlak.
   - B. Google lebih fokus pada keringkasan presisi bagi developer; Microsoft mengedepankan empati dan pendekatan berorientasi solusi.
   - C. Google mewajibkan penggunaan sudut pandang orang pertama jamak ("we"); Microsoft melarangnya.
   - D. Tidak ada perbedaan signifikan sama sekali antara kedua panduan.

4. Pada arsitektur Vale, komponen apa yang bertanggung jawab memecah Markdown menjadi node semantik?
   - A. Regular Expression Parser Engine
   - B. Markdown Abstract Syntax Tree (AST) Converter
   - C. Vocabulary Filter
   - D. Output Formatter

5. Manakah istilah yang dianjurkan untuk menggantikan kata "whitelist" demi mematuhi pedoman inklusivitas industri?
   - A. Approved list / Allowlist
   - B. Safe catalogue
   - C. Accepted passlist
   - D. Positive register

#### Bagian 2: Intermediate (Pilihan Ganda & Analisis Sintaks)
6. Perhatikan konfigurasi `.vale.ini` berikut:
   ```ini
   [*.{md}]
   Google.Passive = error
   Transform = docx
   ```
   Apa kesalahan fatal pada baris ekstensi di atas jika bertujuan melinting seluruh Markdown file secara rekursif?
   - A. Format penulisan harus berupa `[*.md]` tanpa kurung kurawal berlebih agar pola glob parser terbaca valid pada seluruh sistem OS.
   - B. Nilai `Transform` tidak valid karena Vale tidak mendukung format Microsoft Word.
   - C. `Google.Passive` tidak boleh disetel ke `error`.
   - D. Perlu menambahkan tanda kutip dua pada path direktori.

7. Mengapa aturan linter gramatikal tidak boleh diterapkan pada node berkategori `codeblock`?
   - A. Codeblock mengandung karakter binary yang merusak runtime regex.
   - B. Codeblock merepresentasikan sintaks program, command CLI, atau payload data yang kerap melanggar aturan sintaksis bahasa manusia.
   - C. Engine AST Vale akan secara otomatis crash jika membaca sintaks JSON di dalam markdown.
   - D. Aturan Google Style Guide hanya memvalidasi heading level 1.

8. Dalam context-augmented indexing (RAG), bagaimana dokumentasi yang konsisten terhadap Microsoft/Google style meningkatkan performa retrieval?
   - A. Mengurangi latensi parsing JSON di database relasional.
   - B. Memperkecil varians semantik dalam ruang vektor embeddings, mempermudah kalkulasi kedekatan kosinus (*cosine similarity*).
   - C. Mengompres ukuran dokumen mentah menjadi separuhnya.
   - D. Menjamin dokumen terbaca secara instan tanpa perlu tokenisasi.

9. Kapan penggunaan sudut pandang "we" secara eksplisit diizinkan dalam Google Developer Documentation Style Guide?
   - A. Saat menjelaskan langkah-langkah instalasi software pihak ketiga.
   - B. Saat memberikan rekomendasi subjektif arsitektur sistem.
   - C. Saat platform atau sistem melakukan aksi komputasi secara otomatis atas nama pengguna.
   - D. Tidak pernah diizinkan dalam kondisi apa pun.

10. Apa fungsi dari konfigurasi `Vocab` pada direktori Styles Vale?
    - A. Untuk mengompilasi library eksternal C++ ke dalam Vale.
    - B. Untuk mendefinisikan whitelist istilah teknis internal (`accept.txt`) dan blacklist istilah yang ditolak (`reject.txt`) tanpa perlu menulis rule regex manual.
    - C. Untuk mengontrol lokalisasi bahasa (misal: otomatis menerjemahkan Inggris ke Indonesia).
    - D. Untuk menentukan lisensi opensource proyek dokumentasi.

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario A**: Tim Data Engineering Anda merilis SDK baru. Dalam file `README.md`, tertulis:
    > *"To setup the pipeline, the configuration file must be modified by the engineer, and then you just simply spin up the cluster."*
    Sebutkan 3 pelanggaran spesifik terhadap Google Developer Documentation Style Guide pada kalimat di atas dan bagaimana restrukturisasi kalimat yang benar!

12. **Skenario B**: Pipeline CI di GitHub Actions gagal mengeksekusi step Vale dengan log:
    `fatal: pathspec 'docs/' did not match any files`.
    Setelah diinvestigasi, repositori tersebut menggunakan sparse-checkout pada aksi runner. Tindakan arsitektural apa yang harus diimplementasikan pada konfigurasi workflow agar Vale tetap dapat berjalan secara efisien tanpa melakukan *full clone* berukuran ratusan gigabyte?

13. **Skenario C**: Organisasi Anda memiliki repositori monorepo dengan ribuan dokumen Markdown lama. Ketika aturan baru `Google.Passive = error` diaktifkan di level root, terdapat 4.200 error yang menyebabkan seluruh proses development terblokir total. Bagaimana strategi staging (*remediation phase*) yang paling tepat secara engineering tanpa membatalkan standar tersebut?

---

### Kunci Jawaban & Evaluasi

#### Kunci Bagian 1
1. **B** — GDDSG menetapkan *Sentence case* untuk judul dan heading (hanya huruf pertama kalimat dan proper nouns yang menggunakan huruf kapital).
2. **B** — Kalimat pasif mengaburkan subjek yang bertanggung jawab menjalankan aksi, meningkatkan ambiguitas teknis.
3. **B** — GDDSG berorientasi pada objektivitas teknis ringkas untuk developer; MWSG lebih mengedepankan tone suportif, berorientasi solusi, dan ramah pengguna enterprise.
4. **B** — Markdown AST Converter memetakan teks mentah menjadi representasi hierarkis elemen CommonMark.
5. **A** — *Allowlist* atau *Approved list* adalah pengganti resmi yang disepakati industri teknologi untuk menggantikan *whitelist*.

#### Kunci Bagian 2
6. **A** — Glob syntax yang salah seperti `[*.{md}]` dapat menyebabkan pattern matcher gagal mendeteksi berkas `.md` pada beberapa implementasi runner OS. Format baku adalah `[*.md]`.
7. **B** — Blok kode berisi perintah mesin/logika pemrograman yang tidak mengikuti aturan gramatikal bahasa natural manusia; melintingnya menghasilkan *false positives* masif.
8. **B** — Kosakata yang konsisten dan struktur gramatikal yang rapi menurunkan variansi vektor semantik pada proses *embedding*, sehingga meningkatkan akurasi *retrieval* model RAG.
9. **C** — Google memperbolehkan "we" hanya jika merujuk pada aksi platform (contoh: *"In this release, we deprecated the v1 API"*), bukan panduan instruksi personal.
10. **B** — Fitur `Vocab` mempermudah pengelolaan daftar kata yang diterima (*accepted*) dan ditolak (*rejected*) tanpa beban konfigurasi regex berlebih.

#### Kunci Bagian 3 (Pedoman Jawaban)
11. **Analisis Skenario A**:
    - *Pelanggaran 1*: Kalimat pasif (*"must be modified by the engineer"*).
    - *Pelanggaran 2*: Penggunaan kata condescending/ambigu (*"just simply"*).
    - *Pelanggaran 3*: Ketidakkonsistenan sudut pandang (*shifting from third person to second person "you"*).
    - *Restrukturisasi yang benar*: 
      > *"To set up the pipeline, modify the configuration file, and then start the cluster."*
12. **Analisis Skenario B**:
    - Konfigurasikan GitHub Actions checkout step dengan parameter `sparse-checkout`:
      ```yaml
      - uses: actions/checkout@v4
        with:
          sparse-checkout: |
            docs
            .github
          sparse-checkout-cone-mode: false
      ```
    - Pastikan direktori `docs` dan `.github` diikutsertakan secara eksplisit sebelum memanggil CLI runner Vale.
13. **Analisis Skenario C**:
    - **Langkah 1**: Terapkan *Baseline Approach*. Generate berkas baseline Vale (`vale --output=line . > .vale-baseline.txt`) agar CI mengabaikan error warisan (*legacy errors*).
    - **Langkah 2**: Turunkan level aturan di level root menjadi `warning` (`Google.Passive = warning`).
    - **Langkah 3**: Buat *scoped enforcement*: Terapkan `Google.Passive = error` secara progresif hanya pada berkas atau folder baru/aktif, misalnya menggunakan file pattern `[docs/new-features/*.md]`.
    - **Langkah 4**: Agendakan program refaktor berkala per sprint untuk melunasi utang teknis dokumentasi (*documentation debt*) tersebut secara terukur.

---

### 16. Summary

1. **Standardisasi adalah Rekayasa Perangkat Lunak**: Standardisasi dokumentasi skala enterprise bukan sekadar preferensi estetika bahasa, melainkan kebutuhan komputasi sistem modern (*system clarity*, integritas ingest RAG, dan kecepatan adopsi API).
2. **Google vs. Microsoft**: Google memimpin dalam presisi teknis, directness, dan gaya *engineer-first*; Microsoft memimpin dalam empati, kejelasan berorientasi solusi enterprise, dan alur kerja kolaboratif.
3. **Automasi Berbasis AST**: Inspeksi manual tidak memiliki reliabilitas tinggi di skala industri. Vale Engine memungkinkan penguraian Markdown menjadi AST untuk memastikan aturan gaya diperiksa secara deterministik tanpa merusak elemen kode.
4. **Shift-Left Docs Governance**: Mengintegrasikan linter dokumentasi ke dalam siklus *pre-commit* dan *CI/CD Quality Gates* mencegah degradasi kualitas informasi sedini mungkin di level pengembang sebelum merge ke *production branch*.