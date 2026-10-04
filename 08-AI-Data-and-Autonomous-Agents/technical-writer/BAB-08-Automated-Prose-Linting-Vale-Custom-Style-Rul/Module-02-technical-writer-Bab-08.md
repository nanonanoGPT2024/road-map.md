# Kurikulum Enterprise: Technical Writer & Documentation Engineering
## Kategori: 08-AI-Data-and-Autonomous-Agents
### BAB 08: Automated Prose Linting: Vale & Custom Style Rules
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik pada level Enterprise Documentation Architect / Senior Technical Writer diharapkan mampu:
1. **Menganalisis dan Memetakan Arsitektur Internal Vale**: Menguraikan mekanisme *AST parsing*, *scoping engine*, dan *linear-time regex tokenization* yang mendasari eksekusi aturan pada Vale.
2. **Merancang Custom Style Rules Kompleks**: Mengembangkan aturan *prose linting* modular berbasis format YAML menggunakan berbagai ekstensi titik (*extension points*: `existence`, `substitution`, `occurrence`, `repetition`, `consistency`, `conditional`, `script`).
3. **Mengisolasi dan Memvalidasi Dialek Markdown/MDX Modern**: Mengonfigurasi penanganan sintaks non-standar (MDX embedded JSX components, Hugo shortcodes, frontmatter kustom) tanpa merusak integritas *Abstract Syntax Tree* (AST).
4. **Membangun Sistem Distribusi Style Enterprise**: Merancang arsitektur distribusi *style guide* tersentralisasi berbasis Git/S3/Vale Package Manager untuk ratusan repositori mikrosistem dalam ekosistem *Docs-as-Code*.
5. **Mengimplementasikan CI/CD Gating & Delta Linting**: Mengintegrasikan Vale ke dalam pipeline GitHub Actions/GitLab CI dengan strategi *delta-linting* (hanya memeriksa *git diff*) dan anotasi otomatis langsung ke *Pull Request review interface*.

---

### 2. Prerequisite
Untuk mengikuti modul tingkat lanjut ini secara efektif, peserta wajib menguasai:
* Pemahaman fundamental CLI Vale (instalasi, inisialisasi `.vale.ini`, perintah dasar `vale <path>`).
* Penguasaan Regular Expressions (RegEx) tingkat lanjut berbasis mesin **RE2** (Google syntax), termasuk pemahaman keterbatasan non-backtracking engine.
* Konsep *Docs-as-Code*: Git branching strategy, semantic versioning, Markdown/CommonMark/MDX specs, dan Abstract Syntax Trees (AST).
* Arsitektur CI/CD: Pipeline declarative (GitHub Actions / GitLab CI), Docker containerization, dan Webhook/PR review mechanics.
* Shell scripting tingkat menengah (Bash/POSIX) dan manipulasi teks terstruktur (JSON/YAML) via `jq` / `yq`.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Siklus Hidup Eksekusi Mesin Vale (Vale Engine Lifecycle)
Vale tidak memproses dokumentasi sebagai teks datar mentah (*raw string*). Untuk memvalidasi tata bahasa dan gaya penulisan secara presisi tanpa menghasilkan alarm palsu (*false positives*) pada blok kode atau metadata, Vale mengoperasikan pipeline berlapis:

```
[File Dokumen (.md, .mdx, .adoc)]
           │
           ▼
┌──────────────────────────────────────────────┐
│  Phase 1: Ingestion & Format Detection       │
│  - Identifikasi format berbasis ekstensi     │
│  - Pemisahan Frontmatter (YAML/TOML/JSON)    │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  Phase 2: AST Parsing & Tokenization         │
│  - Menggunakan parser Go (Goldmark dll.)     │
│  - Memetakan elemen teks ke Node AST         │
│  - Penandaan Block & Inline Boundaries       │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  Phase 3: Scoping & Masking Engine           │
│  - Mengabaikan elemen non-prosa (Code, HTML) │
│  - Transformasi Node AST -> Vale Scopes      │
│  - Penanganan Token Transform (MDX, JSX)     │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  Phase 4: Concurrent Rule Dispatcher         │
│  - Eksekusi Goroutines paralel per aturan    │
│  - Injeksi Kamus Accept/Reject               │
│  - Linear Execution Engine (Google RE2)      │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  Phase 5: Diagnostics Aggregation & Export   │
│  - Pengurutan temuan berbasis baris & kolom  │
│  - Output: CLI, JSON, SARIF, Reviewdog API   │
└──────────────────────────────────────────────┘
```

1. **Ingestion & Format Detection**: Vale membaca konfigurasi global `.vale.ini`, menentukan parser dokumen yang relevan (misalnya *Goldmark* untuk Markdown, *Chroma* untuk syntax highlighting awareness, atau parser khusus AsciiDoc).
2. **AST Parsing & Tokenization**: File diubah menjadi struktur hierarki node AST. Setiap elemen (Heading 1, Paragraph, ListItem, CodeBlock, InlineCode) dialokasikan sebagai node terpisah dengan offset posisi baris (*line*) dan kolom (*column*).
3. **Scoping & Masking Engine**: Bagian yang dikecualikan (seperti blok kode ` ```go ... ``` ` atau inline code `` `nil` ``) diganti dengan token representasi sementara (*masking*) agar tidak diperiksa oleh aturan prosa, kecuali aturan tersebut secara eksplisit menargetkan scope tersebut.
4. **Rule Dispatching & Extension Point Routing**: Vale menjalankan evaluasi berbasis konkurensi (memanfaatkan *Go channels/goroutines*). Setiap aturan YAML dikompilasi sesuai tipe ekstensi (`existence`, `substitution`, `repetition`, dll.) dan dieksekusi terhadap teks yang telah di-scope.
5. **Linear RE2 Engine Matching**: Vale secara ketat menggunakan pustaka reguler ekspresi Go bawaan (`regexp`), yang mengimplementasikan spesifikasi Google RE2. Karakteristik penting:
   * **Bebas Catastrophic Backtracking**: Kompleksitas komputasi dijamin linear $O(n)$ terhadap panjang dokumen.
   * **Tidak Mendukung Backreferences dan Lookarounds**: Konstruksi seperti `(?<=foo)bar` atau `(foo)(?=bar)` tidak didukung secara natif dan harus diselesaikan menggunakan pemisahan scope (*scoping logic*) atau capture groups tersegregasi.

#### 3.2 Vale Scope Hierarchy & Taxonomies
Vale mendefinisikan *scope* sebagai target semantik di mana aturan diterapkan. Pemahaman scope sangat krusial dalam pembuatan aturan produksi:

* `raw`: Seluruh teks file mentah sebelum diproses AST (digunakan untuk validasi frontmatter atau struktur file global).
* `text`: Seluruh teks prosa yang telah dibersihkan dari sintaks Markdown, tanpa struktur hierarki.
* `summary`: Prosa per unit paragraf/blok.
* `paragraph`: Blok paragraf standar (`<p>`).
* `sentence`: Unit kalimat diskrit yang dipotong oleh algoritma segmentasi Vale (berbasis punktuasi dan singkatan umum).
* `heading`: Semua level heading (`<h1>` s.d. `<h6>`). Dapat dispesifikkan menjadi `heading.h1`, `heading.h2`, dst.
* `table.header`, `table.cell`: Sel dalam tabel Markdown.
* `list`: Blok daftar urut atau tidak urut (`<ul>`, `<ol>`).
* `alt`: Teks alternatif pada elemen gambar (`![alt text](url)`).

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Manual Editorial / NLP Generik) | Pendekatan Modern Docs-as-Code (Vale Engine) |
| :--- | :--- | :--- |
| **Kecepatan Umpan Balik** | Hari hingga minggu; review manual bergantung pada ketersediaan Technical Editor. | Detik; tervalidasi di local pre-commit hook atau status check CI/CD. |
| **Skalabilitas** | $O(N)$ biaya personil seiring bertambahnya jumlah tim rekayasa perangkat lunak. | $O(1)$ penambahan biaya; ribuan PR divalidasi otomatis secara paralel. |
| **Konsistensi Penegakan** | Subjektif; editor yang berbeda dapat memiliki preferensi personal yang berlawanan. | Deterministik; seluruh aturan dikodekan (*Code-as-Style*) dan terikat version control. |
| **Interferensi Sintaks** | Tools seperti Grammarly sering memodifikasi atau mengeluhkan variabel kode/sintaks MDX. | *AST-aware*; mengabaikan code blocks, inline tags, dan shortcodes secara native. |
| **Dukungan Domain Khusus** | Sulit mengajarkan terminologi kepemilikan (*proprietary*) enterprise secara tersentralisasi. | Mendukung *vocabularies* kustom (`accept.txt` & `reject.txt`) dengan segmentasi per proyek. |

---

### 5. How (Workflow detail)

Alur kerja operasional penegakan gaya penulisan skala enterprise:

```
[Developer / Technical Writer]
          │
  (1) Menulis Dokumen (.mdx / .md)
          │
          ▼
[Git Pre-commit Hook]  ──(Trigger CLI Local)──> [Vale Local Engine]
          │                                            │
       (Lolos)                                (Peringatan & Error)
          ▼                                            │
[Push to Feature Branch]                               ▼
          │                                   [Perbaikan Mandiri]
          ▼
[Pull Request (PR) Dibuka]
          │
          ▼
[CI/CD Pipeline: GitHub Actions Runner]
          │
          ├─► (A) Fetch Vale Enterprise Package (Git / Release Asset)
          ├─► (B) Hitung Git Diff terhadap `main` branch (Delta-linting)
          ├─► (C) Eksekusi Vale CLI dengan Output JSON/SARIF
          │
          ▼
[Reviewdog / Vale Action Parser]
          │
  (Dianotasikan Langsung pada Baris PR Diff)
          │
          ▼
[Gating Policy Check]
  ├── Terdapat Status Error   ──> Block PR Merge
  └── Hanya Warning / Suggest ──> Izinkan Merge (Kecuali Mode Strict)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
Bayangkan Vale sebagai **Compiler Clang-Tidy atau ESLint, namun khusus untuk bahasa manusia**. 
* ESLint membaca kode Javascript, memecahnya menjadi AST (*ESTree*), dan memastikan Anda tidak meninggalkan variabel yang tidak terpakai atau gaya penulisan *camelCase* yang rusak.
* Vale membaca prosa Markdown, memecahnya menjadi AST (*Prose-AST*), mengabaikan blok kode internal, dan memastikan Anda tidak menulis istilah usang, menggunakan *passive voice* berlebihan, atau melanggar identitas merek enterprise.

#### Diagram Scoping & Token Masking
```
Konten Dokumen Asli (Markdown):
# Panduan Penggunaan API
Gunakan fungsi `init_session()` untuk memulai. **PERHATIAN**: Jgn mematikan server.

                       │
                       ▼ Transformasi AST & Masking
Node Headings:
[ "Panduan Penggunaan API" ] ──► Diuji terhadap aturan Heading Case

Node Paragraph (Masked):
[ "Gunakan fungsi █CODE_MASK_0█ untuk memulai. " ] ──► Diuji terhadap Pola Bahasa
[ "█STRONG_MASK_1█: Jgn mematikan server." ]       ──► Diuji terhadap Kata Terlarang ("Jgn")

Node Code (Ignored):
[ `init_session()` ] ──► DILEWATI (Tidak memicu false-positive ejaan/tata bahasa)
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Konfigurasi Dasar dan Aturan Deteksi Singkatan Informal
Skenario: Mencegah penggunaan kata singkatan bahasa Indonesia non-formal dalam dokumentasi teknik.

**File:** `.vale.ini`
```ini
StylesPath = styles
MinAlertLevel = suggestion

[*.md]
BasedOnStyles = InternalDocs
```

**File:** `styles/InternalDocs/InformalAbbreviation.yml`
```yaml
extends: substitution
message: "Hindari singkatan informal '%s', gunakan kata baku '%s'."
link: "https://wiki.corp.internal/style-guide/kata-baku"
level: error
scope: text
ignorecase: true
swap:
  jgn: jangan
  bisa: dapat
  tp: tetapi
  krn: karena
  dgn: dengan
```

#### 7.2 Practical Example: Aturan Lanjutan Skala Enterprise (Multi-line, Scripting & Conditional)

Skenario: 
1. Validasi penamaan produk resmi (`Enterprise Platform Core`).
2. Deteksi sintaks *Passive Voice* lanjutan dalam bahasa Inggris teknik.
3. Deteksi URL non-HTTPS dan IP Hardcoded dalam teks dokumentasi.

**File Konfigurasi Tingkat Lanjut:** `.vale.ini`
```ini
StylesPath = styles
MinAlertLevel = warning

# Registrasi Vocabulary Enterprise
Vocab = EngineeringTerm

Packages = Google, RedHat

[formats]
mdx = md

[*.{md,mdx}]
BasedOnStyles = Vale, EnterpriseVoice

# Mengabaikan blok shortcode kustom dan komponen React/MDX
BlockIgnores = (?s) *(<Alert.*?>.*?</Alert>), \
(?s) *({{< figure .*? >}})

# Mengabaikan inline placeholder seperti {VARIABLE_NAME}
TokenIgnores = ({[A-Z0-9_]+})
```

**File Aturan 1: Deteksi Produk Enterprise (Tipe `consistency`)**
Menjamin nama brand tidak ditulis bervariasi di berbagai bagian dokumen (misal: "CorpCloud" vs "Corp Cloud").

**File:** `styles/EnterpriseVoice/BrandConsistency.yml`
```yaml
extends: consistency
message: "Penggunaan istilah merek '%s' tidak konsisten dengan temuan sebelumnya '%s'."
level: error
scope: text
nonword: false
either:
  - CorpCloud Engine
  - Corp-Cloud Engine
  - Corp Cloud Engine
```

**File Aturan 2: Deteksi Passive Voice dengan Pengecualian Kontekstual (Tipe `existence`)**
Mendeteksi pola aux + verb-ed dengan isolasi RE2.

**File:** `styles/EnterpriseVoice/PassiveVoice.yml`
```yaml
extends: existence
message: "Hindari penggunaan kalimat pasif: '%s'. Prioritaskan gaya penulisan aktif."
level: warning
scope: sentence
ignorecase: true
tokens:
  - '\b(?:am|are|is|was|were|be|been|being)\s+(?:[a-z]+ed|written|done|made|built|configured|deployed)\b'
```

**File Aturan 3: Kondisional Kompleks (Tipe `conditional`)**
Memastikan jika sebuah fitur dilabeli `[Deprecated]`, instruksi alternatif (`Gunakan ...`) harus disertakan dalam paragraf yang sama.

**File:** `styles/EnterpriseVoice/DeprecationNotice.yml`
```yaml
extends: conditional
message: "Blok Deprecated terdeteksi tanpa menyertakan referensi migrasi atau instruksi pengganti."
level: error
scope: paragraph
# Memastikan jika first token ada, second token WAJIB ada
first: '(?i)\[(?:DEPRECATED|USANG)\]'
second: '(?i)(?:gunakan|ganti dengan|referensi|migrasi ke)\s+\b'
exceptions:
  - '(?i)tidak ada pengganti'
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks & Skala Kasus
* **Organisasi**: Bank Digital Skala Multinasional (FinTech Core Engine).
* **Lingkungan**: Monorepo Documentation-as-Code dengan 40.000+ file Markdown & OpenAPI spec.
* **Kontributor**: 1.200+ Software Engineers dan 35 Technical Writers.
* **Tantangan Masalah**:
  1. Kontributor sering menaruh istilah keamanan usang seperti `whitelist/blacklist` dan `master/slave` yang melanggar audit kepatuhan industri finansial.
  2. Dokumentasi API publik secara tidak sengaja memuat endpoint staging/internal seperti `https://staging-internal.bank.co.id`.
  3. Laporan review PR lambat karena Technical Editor membuang 60% kapasitas kerja hanya untuk memperbaiki kapitalisasi heading dan nama akronim.
  4. CI pipeline memakan waktu lebih dari 25 menit jika Vale mengecek seluruh direktori secara menyeluruh (*full crawl*).

#### Solusi Arsitektur Produksi
1. **Pemisahan Paket Style Terpusat**:
   Gaya penulisan diisolasi ke dalam repositori independen `enterprise-vale-styles` yang mempublikasikan rilis bertag `vX.Y.Z.zip` ke Private AWS S3 Bucket. Repositori target mengonsumsi paket via konfigurasi `.vale.ini`:
   ```ini
   Packages = https://artifacts.bank.internal/vale/EnterpriseVoice-v2.1.0.zip
   ```
2. **Delta-Linting CI Optimization**:
   Menulis script eksekusi CI yang membandingkan perubahan berkas pada cabang target (`origin/main`) menggunakan perintah `git diff --name-only --diff-filter=ACMR`. Vale hanya dijalankan pada file-file yang terdampak.
3. **Penerapan Multi-Level Severity**:
   * `suggestion`: Tampil sebagai anotasi PR, tidak menggagalkan status build (contoh: rekomendasi kata yang lebih ringkas).
   * `warning`: Peringatan gaya penulisan internal (contoh: kalimat pasif).
   * `error`: Pelanggaran kepatuhan (contoh: non-inclusive language, insecure staging URLs). PR diblokir secara otomatis dari *merging*.

#### Metrik Keberhasilan (Hasil Pasca Implementasi)
* Waktu eksekusi linting pada PR CI/CD terpangkas dari **25 menit** menjadi **18 detik** (peningkatan efisiensi 98,8%).
* Insiden kebocoran URL staging internal pada API Docs Publik berkurang menjadi **0 insiden**.
* *Time-to-merge* untuk pull request teknis meningkat dari rata-rata 3 hari menjadi **kurang dari 4 jam**, membebaskan technical editor untuk fokus pada substansi arsitektural.

---

### 9. Trade-offs

Mengadopsi prose-linting berbasis compiler memerlukan kompromi rekayasa:

| Keputusan Arsitektur | Keuntungan | Biaya / Konsekuensi Negatif | Mitigasi |
| :--- | :--- | :--- | :--- |
| **Linear Engine (Go RE2) vs PCRE** | Eksekusi aman secara deterministik, memori konstan, kebal terhadap serangan DoS berbasis regex (*Catastrophic Backtracking*). | Tidak ada dukungan *lookarounds* (`(?<=...)`, `(?!...)`) dan *backreferences*. | Dekonstruksi aturan ke tingkat `scope` yang lebih granular atau gunakan ekstensi tipe `conditional`/`script`. |
| **Delta Linting vs Full Repository Scan** | CI/CD sangat cepat; developer mendapatkan umpan balik dalam hitungan detik saat membuka PR. | Perubahan aturan baru tidak tervalidasi secara instan pada dokumen lama yang tidak diedit (*legacy debt*). | Jadwalkan *Nightly Cron Job* untuk memvalidasi *Full Repository Scan* dan mempublikasikan laporan utang teknis. |
| **Strict Gating (Error blocks PR) vs Permissive (Warning only)** | Memaksa kepatuhan standar 100%; dokumen publik selalu bersih dan terstandardisasi. | Resistensi pengembang meningkat drastis jika terlalu banyak aturan trivial yang memblokir rilis fitur mendesak. | Batasi level `error` hanya untuk isu keamanan, legalitas, kepatuhan inklusif, dan nama entitas inti. |
| **AST Masking vs Raw Parsing** | Menghilangkan *false positives* pada syntax kode, math block, dan komentar. | Risiko salah *masking* pada sintaks dialek kustom non-standar (misalnya komponen JSX nested kompleks). | Pembuatan regex `BlockIgnores` terisolasi yang diuji secara ketat via automated test suite. |

---

### 10. Common Mistakes & Troubleshooting

#### Kasus 1: Aturan RegEx Mengandung Lookaround Menyebabkan Fatal Panic di Vale
* **Gejala**: Vale berhenti mendadak saat inisialisasi dengan pesan error: `error parsing regexp: invalid or unsupported Perl syntax: '(?!'`.
* **Akar Masalah**: Penulis aturan mencoba menggunakan *negative lookahead* khas PCRE/Python/JavaScript yang ditolak oleh Go RE2 engine.
* **Solusi**: Ganti strategi. Alih-alih mengecualikan kata di dalam satu regex, gunakan fitur `exceptions` bawaan Vale YAML:
  ```yaml
  # SALAH:
  # regex: '\bFoo(?!Bar)\b'
  
  # BENAR:
  extends: existence
  message: "Gunakan 'FooBar', bukan 'Foo' mandiri."
  tokens:
    - '\bFoo\b'
  exceptions:
    - '\bFooBar\b'
  ```

#### Kasus 2: Komponen MDX/JSX Tercecer dan Memecah Kalimat AST
* **Gejala**: Kalimat terputus di tengah jalan, memicu aturan *SentenceLength* atau *Capitalization* palsu pada baris kode React seperti `<Callout type="info">`.
* **Akar Masalah**: Vale menganggap `<Callout>` sebagai baris teks biasa karena ekstensi file didaftarkan murni sebagai Markdown standard.
* **Solusi**: Tambahkan konfigurasi `BlockIgnores` di `.vale.ini`:
  ```ini
  [*.mdx]
  BlockIgnores = (?s)(<[A-Z][A-Za-z0-9]*(\s+.*?|\s*)>.*?</[A-Z][A-Za-z0-9]*>), \
  (?s)(<[A-Z][A-Za-z0-9]*(\s+.*?|\s*)/>)
  ```

#### Kasus 3: Vocabulary Directory Tidak Diakui di Remote CI Environment
* **Gejala**: Aturan lokal berjalan sukses, namun di CI/CD build menghasilkan ribuan kegagalan kata ejaan (*spelling error*) yang seharusnya telah di-whitelist.
* **Akar Masalah**: File `accept.txt` berada di folder yang diabaikan `.gitignore`, atau path `Vocab` pada `.vale.ini` tidak mencantumkan nama folder secara eksplisit dan sensitif huruf kapital (*case-sensitive mismatch* pada Linux CI runner vs macOS dev machine).
* **Solusi**: Pastikan struktur `styles/config/vocabularies/<Vocab_Name>/accept.txt` ter-commit dengan benar dan path didefinisikan konsisten dalam huruf kecil.

---

### 11. Best Practices (Production Checklist)

- [ ] **Linearity Check**: Pastikan tidak ada aturan regex kustom yang menyebabkan pemindaian rekursif tak berujung (Gunakan alat validasi RE2 internal).
- [ ] **Fail-Safe CI Strategy**: Tentukan apakah CI harus gagal (*exit code 1*) hanya pada tingkat `error`, sedangkan `warning` hanya memberi anotasi tanpa memblokir PR (`vale --minAlertLevel=error`).
- [ ] **Isolated Vocabularies**: Pisahkan perbendaharaan kata menjadi domain-spesifik (misal: `styles/config/vocabularies/Fintech/accept.txt` dan `styles/config/vocabularies/InternalTech/accept.txt`).
- [ ] **SemVer Rules Distribution**: Setiap perubahan aturan style guide enterprise harus memicu rilis semantic versioning untuk mencegah kerusakan tak terduga (*breaking build*) pada repositori hilir.
- [ ] **Scope Minimization**: Jangan pernah menggunakan `scope: raw` jika aturan hanya berlaku untuk paragraf; selalu pilih tingkat semantik paling spesifik (`heading`, `sentence`, dsb.).
- [ ] **Dynamic Token Masking**: Daftarkan seluruh inline code syntax macro framework dokumentasi Anda (misal Docusaurus, Astro Starlight, Nextra) ke dalam `TokenIgnores` pada `.vale.ini`.

---

### 12. Hands-on Practice

Panduan langkah demi langkah implementasi sistem enterprise linter pada path lokal: `hands-on/m02/`.

#### Langkah 1: Inisialisasi Workspace
```bash
mkdir -p hands-on/m02/styles/EnterpriseSecurity
mkdir -p hands-on/m02/styles/config/vocabularies/CoreDomain
cd hands-on/m02
```

#### Langkah 2: Buat Konfigurasi Master Vale (`.vale.ini`)
Simpan berkas berikut pada `hands-on/m02/.vale.ini`:
```ini
StylesPath = styles
MinAlertLevel = suggestion

Vocab = CoreDomain

[formats]
mdx = md

[*.{md,mdx}]
BasedOnStyles = EnterpriseSecurity

TokenIgnores = (\$\{.*?\})
```

#### Langkah 3: Definisikan Whitelist Kata Legal Domain (`accept.txt`)
Simpan berkas berikut pada `hands-on/m02/styles/config/vocabularies/CoreDomain/accept.txt`:
```text
Kubernetes
Microservice
OAuth2
PostgreSQL
Fintech
API Gateway
```

#### Langkah 4: Tulis Aturan Deteksi Terminologi Tidak Inklusif
Simpan aturan berikut pada `hands-on/m02/styles/EnterpriseSecurity/InclusiveLanguage.yml`:
```yaml
extends: substitution
message: "Istilah '%s' tidak memenuhi standar inklusivitas industri. Ganti dengan '%s'."
link: "https://inclusivenaming.org/"
level: error
scope: text
ignorecase: true
swap:
  whitelist: allowlist
  black list: deny list
  blacklist: denylist
  master: primary / main
  slave: secondary / replica
```

#### Langkah 5: Tulis Aturan Validasi Credential Leak Prevention
Simpan aturan berikut pada `hands-on/m02/styles/EnterpriseSecurity/SecretLeak.yml`:
```yaml
extends: existence
message: "Pola teks menyerupai Secret Key atau Private Credential terdeteksi: '%s'!"
level: error
scope: raw
tokens:
  - '(?i)(?:bearer\s+[a-z0-9\-_]{30,})'
  - '(?i)(?:AKIA[0-9A-Z]{16})'
  - '(?i)(?:ghp_[a-zA-Z0-9]{36})'
```

#### Langkah 6: Siapkan Berkas Markdown Pengujian
Simpan berkas berikut pada `hands-on/m02/docs-sample.md`:
```markdown
# Panduan Arsitektur Database

Untuk konfigurasi database, sistem kita menggunakan arsitektur master dan slave.
Pastikan semua IP aplikasi masuk ke dalam whitelist database server.

Token pengujian staging adalah Bearer secret_live_token_abc123456789012345678901234567890.
Arsitektur kita dibangun di atas Kubernetes dan Microservice cluster.
```

#### Langkah 7: Eksekusi dan Verifikasi Diagnostik
Jalankan perintah linting berikut dari direktori `hands-on/m02`:
```bash
vale docs-sample.md
```

**Hasil Ekspektasi Output:**
```text
docs-sample.md:3:48:EnterpriseSecurity.InclusiveLanguage:Istilah 'master' tidak memenuhi standar inklusivitas industri. Ganti dengan 'primary / main'.
docs-sample.md:3:59:EnterpriseSecurity.InclusiveLanguage:Istilah 'slave' tidak memenuhi standar inklusivitas industri. Ganti dengan 'secondary / replica'.
docs-sample.md:4:40:EnterpriseSecurity.InclusiveLanguage:Istilah 'whitelist' tidak memenuhi standar inklusivitas industri. Ganti dengan 'allowlist'.
docs-sample.md:6:33:EnterpriseSecurity.SecretLeak:Pola teks menyerupai Secret Key atau Private Credential terdeteksi: 'Bearer secret_live_token_abc123456789012345678901234567890'!

✖ 4 errors, 0 warnings and 0 suggestions in 1 file.
```

---

### 13. Exercise

#### Tingkat: Easy
1. **Objektif**: Buat aturan gaya penulisan bernama `HeadingPunctuation.yml` di dalam direktori `styles/EnterpriseFormat/`.
2. **Kriteria Spesifikasi**:
   * Menargetkan `scope: heading`.
   * Memastikan tidak ada tanda titik (`.`), titik dua (`:`), atau titik koma (`;`) di akhir baris judul heading level mana pun.
   * Tingkat keparahan (*level*): `warning`.

#### Tingkat: Medium
1. **Objektif**: Buat aturan penggantian istilah (`substitution`) bernama `TechnicalJargon.yml`.
2. **Kriteria Spesifikasi**:
   * Mendeteksi kata-kata tidak profesional seperti: "gampang", "sangat mudah", "tinggal klik", "simply", "obviously".
   * Memberikan pesan kontekstual bahwa dokumentasi harus berorientasi instruksional netral tanpa asumsi bias kapabilitas pembaca.
   * Abaikan pemeriksaan jika kata-kata tersebut berada di dalam *quote block* (`blockquote`).

#### Tingkat: Hard
1. **Objektif**: Bangun arsitektur aturan konsistensi identitas (`consistency`) bernama `AsyncNaming.yml` sekaligus konfigurasi GitHub Actions workflow `.github/workflows/docs-lint.yml`.
2. **Kriteria Spesifikasi**:
   * Memvalidasi bahwa seluruh monorepo tidak boleh mencampurkan istilah "asynchronous" dan "async" di dalam satu file Markdown yang sama.
   * Workflow GitHub Actions harus mengimplementasikan delta-linting: hanya memindai berkas yang ditambahkan/diubah (`added/modified`) pada Pull Request, mengekspor hasil ke format SARIF, dan mengunggahnya ke GitHub Security Alerts tab.

---

### 14. Challenge

**Studi Kasus Skenario Terdistribusi:**
Anda adalah Principal Documentation Engineer di platform Cloud Enterprise terkemuka. Dokumentasi perusahaan sedang bermigrasi dari *monolithic static site generator* ke Next.js MDX monorepo yang memuat lebih dari 150.000 file dokumentasi produk. 

Terdapat masalah besar:
1. Dokumentasi memuat *JSX Custom Tags* kompleks bertingkat seperti:
   ```jsx
   <Tabs>
     <TabItem value="bash">
       <CodeSnippet lang="bash" runnable={true}>
          curl -H "Auth: {AUTH_TOKEN}" https://api.corp.com/v1
       </CodeSnippet>
     </TabItem>
   </Tabs>
   ```
2. Engine Vale saat ini hancur (*crash*) saat mencoba memetakan AST karena tag JSX bertingkat memicu ambiguitas parsing Markdown.
3. Tim Keamanan Perusahaan menuntut agar **Zero Private IP Address (RFC 1918)** dipublikasikan dalam contoh dokumentasi (misal: IP `10.x.x.x`, `172.16-31.x.x`, `192.168.x.x`), kecuali IP khusus dokumentasi resmi (RFC 5737: `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`).

**Tugas Anda:**
Rancang strategi rekayasa komprehensif yang mencakup:
* Konfigurasi regex `BlockIgnores` presisi tanpa merusak parsing teks yang ada di dalam child components.
* Buat aturan Vale `existence` murni RE2 untuk memblokir RFC 1918 private IPv4 addresses namun tetap mengizinkan alamat dummy RFC 5737 secara deterministik tanpa false positive.
* Rancang arsitektur pipeline CI/CD yang mampu mengeksekusi pemeriksaan pada monorepo 150.000 file tersebut dengan SLA eksekusi maksimal **60 detik** per PR. Tuliskan arsitektur logis dan spesifikasi konfigurasinya!

---

### 15. Quiz Evaluasi Pemahaman

#### Soal Basic (Pilihan Ganda & Penjelasan Singkat)
1. **Mengapa Vale menggunakan pustaka regular expression Google RE2 dan bukan PCRE (Perl Compatible Regular Expressions)?**
   * A. Karena PCRE berbayar dan berlisensi tertutup.
   * B. Karena RE2 menjamin waktu eksekusi linear $O(n)$ dan kebal terhadap Catastrophic Backtracking (ReDoS).
   * C. Karena RE2 mendukung fitur lookbehind assertion lebih lengkap daripada PCRE.
   * D. Karena RE2 ditulis dalam bahasa Go murni sedangkan PCRE tidak bisa diintegrasikan.
   * *Jawaban:* **B**. RE2 menjamin komputasi waktu linier sebanding dengan ukuran input dokumen, mencegah parser macet akibat backtracking eksponensial.

2. **Ekstensi titik (*extension point*) manakah pada aturan Vale yang digunakan untuk menjamin keseragaman penulisan istilah di seluruh dokumen (misal: mencegah penulisan "front-end" dan "frontend" secara bercampur)?**
   * A. `existence`
   * B. `substitution`
   * C. `consistency`
   * D. `occurrence`
   * *Jawaban:* **C**. Ekstensi `consistency` melacak instansiasi pertama yang muncul dan memberikan peringatan jika variasi alternatifnya ditemukan di bagian lain dalam dokumen yang sama.

3. **Di mana lokasi penyimpanan default perbendaharaan kata (*vocabulary*) `accept.txt` lokal jika Vale membaca style dari direktori `styles`?**
   * A. `styles/Vocabularies/<Nama_Vocab>/accept.txt`
   * B. `styles/config/vocabularies/<Nama_Vocab>/accept.txt`
   * C. `.vale/vocab/<Nama_Vocab>/accept.txt`
   * D. `styles/accept.txt`
   * *Jawaban:* **B**. Sesuai struktur resmi sistem Vale, vocabularies wajib berada pada path internal `styles/config/vocabularies/<Nama_Vocab>/`.

4. **Scope manakah yang harus ditargetkan jika Anda ingin menguji seluruh blok daftar Markdown (`<ul>` atau `<ol>`) secara kolektif?**
   * A. `text`
   * B. `raw`
   * C. `list`
   * D. `paragraph`
   * *Jawaban:* **C**. Scope `list` membatasi pengujian pada elemen container daftar dan elemen item di dalamnya.

5. **Apa fungsi dari parameter `TokenIgnores` pada file `.vale.ini`?**
   * A. Menghapus file teks dari daftar pemindaian.
   * B. Mengabaikan baris string inline yang cocok dengan pola regex tanpa merusak tokenisasi AST di sekitarnya.
   * C. Menutup koneksi jaringan saat linting berjalan.
   * D. Mengabaikan seluruh blok paragraf.
   * *Jawaban:* **B**. `TokenIgnores` digunakan untuk menyamarkan (masking) token inline seperti variabel template `${VAR}` agar dilewati oleh linter.

---

#### Soal Intermediate (Analisis Kasus & Algoritma Engine)
6. **Perhatikan cuplikan aturan berikut:**
   ```yaml
   extends: existence
   scope: sentence
   tokens:
     - '(?i)\b(sangat|amat|sekali)\b'
   ```
   **Jika dokumen target berisi: "Fitur ini sangat penting sekali.", berapa banyak alarm yang akan dibangkitkan oleh Vale dan mengapa?**
   * A. 1 alarm, karena scope sentence hanya melaporkan error pertama.
   * B. 2 alarm, karena ekstensi `existence` mengevaluasi setiap kecocokan token individual secara independen di sepanjang kalimat.
   * C. 0 alarm, karena kata "sekali" membatalkan kata "sangat".
   * D. Terjadi runtime error karena kata kunci ganda.
   * *Jawaban:* **B**. Ekstensi `existence` memindai seluruh kemunculan token di dalam scope. Kalimat tersebut memiliki dua token cocok ("sangat" dan "sekali"), sehingga membangkitkan 2 alert diagnostik terpisah dengan koordinat kolom masing-masing.

7. **Bagaimana arsitektur Vale menangani file bertipe MDX yang menyematkan frontmatter YAML dan tag komponen React?**
   * A. Vale mengubah seluruh file menjadi HTML murni menggunakan Webpack sebelum memindai.
   * B. Vale memisahkan frontmatter menggunakan raw delimiters `---`, memetakan sisa dokumen ke Markdown AST, dan mem-bypass tag komponen via regex mask `BlockIgnores`.
   * C. Vale mengeksekusi kode React menggunakan NodeJS runtime terlebih dahulu.
   * D. Vale tidak mendukung MDX sama sekali.
   * *Jawaban:* **B**. Vale natively mengisolasi frontmatter, memproses markup inti via compiler markdown, dan memanfaatkan masking rule pengguna untuk komponen non-standar.

8. **Anda ingin membuat aturan penulisan judul (heading) dengan konvensi Sentence case (hanya huruf pertama judul dan nama produk yang kapital). Jika scope diatur ke `heading`, mengapa Anda sebaiknya menyertakan parameter `match: $title` alih-alih regex regex murni manual?**
   * A. Karena regex manual tidak dapat membedakan string ASCII.
   * B. Karena parameter built-in Vale memanfaatkan algoritma parsing kapitalisasi bahasa manusia internal yang terintegrasi langsung dengan vocabulary list `accept.txt`.
   * C. Karena regex murni di Go RE2 dilarang pada scope heading.
   * D. Karena opsi `match: $title` mempercepat komputasi hingga 100 kali lipat.
   * *Jawaban:* **B**. Vale menyediakan transformasi bawaan `$title`, `$sentence`, `$lower`, `$upper` yang cerdas terhadap pengecualian kata di vocab `accept.txt`.

9. **Jika pada `.vale.ini` terdapat konfigurasi:**
   ```ini
   MinAlertLevel = error
   ```
   **Apa implikasi langsungnya terhadap eksekusi pipeline CI/CD?**
   * A. Laporan alert berstatus `suggestion` dan `warning` akan sepenuhnya diabaikan dari komputasi dan tidak akan memicu non-zero exit code.
   * B. CI/CD akan gagal jika ada peringatan berstatus `warning`.
   * C. Vale akan berhenti membaca aturan bertipe `substitution`.
   * D. Semua berkas akan ditandai error secara paksa.
   * *Jawaban:* **A**. `MinAlertLevel` memfilter output engine. Tingkat alert di bawah ambang batas yang ditentukan tidak akan dipancarkan ke output stream diagnostik.

10. **Apa perbedaan fungsional mendasar antara extension point `substitution` dan `repetition`?**
    * A. `substitution` digunakan untuk kata tunggal, `repetition` untuk multi-paragraf.
    * B. `substitution` mengganti token terlarang dengan padanan yang benar; `repetition` mendeteksi pengulangan kata berurutan yang identik yang tidak disengaja (misal: "pada pada").
    * C. `substitution` memerlukan akses internet; `repetition` berjalan lokal.
    * D. `repetition` hanya berlaku pada scope `code`.
    * *Jawaban:* **B**. `repetition` memiliki algoritma internal yang dirancang khusus untuk mendeteksi token duplikat berturut-turut dengan toleransi penanganan batas baris/tanda baca.

---

#### Soal Kasus Produksi Skala Enterprise
11. **Skenario Produksi 1 (Monorepo Latency Optimization):**
    Sebuah repositori enterprise memiliki 80.000 file dokumentasi. Eksekusi `vale .` pada local machine menghabiskan waktu 8 menit dan memakan RAM 12 GB. Tim QA ingin mengintegrasikan Vale ke dalam Pre-commit hook developer tanpa menimbulkan delay lebih dari 3 detik.
    *Tindakan arsitektur manakah yang paling presisi untuk menyelesaikan masalah ini?*
    * **Solusi & Rasionalisasi:** Konfigurasikan hook (misal via `husky` atau framework `pre-commit`) untuk mengeksekusi Vale **hanya pada staged files** menggunakan perintah:
      ```bash
      git diff --cached --name-only --diff-filter=ACM "*.md" "*.mdx" | xargs -r vale
      ```
      Ini membatasi proses parsing AST hanya pada berkas yang sedang dimodifikasi secara lokal (biasanya 1–3 berkas), sehingga eksekusi selesai dalam waktu <1 detik tanpa memindai sisa repositori.

12. **Skenario Produksi 2 (False-Positive Suppression pada Code Samples):**
    Dokumentasi integrasi Payment Gateway memuat ribuan baris instruksi payload JSON dan Bash command di dalam Markdown. Developer mengeluh bahwa aturan deteksi singkatan dan terminologi merek Vale melaporkan ratusan error yang berasal dari dalam blok JSON dan variabel shell.
    *Tindakan manakah yang harus diambil pada level konfigurasi engine?*
    * **Solusi & Rasionalisasi:** Periksa konfigurasi scope pada aturan yang bermasalah. Pastikan aturan tersebut tidak menggunakan `scope: raw`. Ubah ke `scope: text` atau `scope: paragraph`. Selain itu, pastikan syntax code block pada dokumen Markdown terformat valid menggunakan triple backticks (```json ... ```) agar Goldmark AST parser mengklasifikasikan blok tersebut sebagai `FencedCodeBlock` yang secara otomatis di-mask oleh Vale.

13. **Skenario Produksi 3 (Cross-Repository Style Drift):**
    Perusahaan memiliki 50 repositori mikrosistem yang masing-masing mendokumentasikan API service-nya sendiri. Setiap repositori meng-copy folder `styles/` secara manual 6 bulan lalu. Saat ini, pedoman legal perusahaan telah diperbarui, namun 45 repositori lainnya masih menggunakan style lama yang menghasilkan output inkonsisten.
    *Rancang pola distribusi style yang scalable untuk memecahkan style drift ini!*
    * **Solusi & Rasionalisasi:** Hentikan praktik manual copying (*anti-pattern*). Bangun repositori pusat `docs-style-hub`. Konfigurasikan pipeline rilis GitHub untuk mem-package direktori styles menjadi file zip terkompresi dengan semantic release. Pada 50 repositori microservice, perbarui `.vale.ini` untuk merujuk pada package terpusat:
      ```ini
      Packages = https://github.com/corp-org/docs-style-hub/releases/download/v2.0.0/EnterpriseVoice.zip
      BasedOnStyles = EnterpriseVoice
      ```
      Sertakan perintah `vale sync` pada pipeline CI di setiap repositori sebelum menjalankan `vale lint`.

---

### 16. Summary

1. **Vale adalah AST-Aware Prose Compiler**: Vale membedakan dirinya dari spell-checker konvensional dengan membedah dokumen ke dalam format Abstract Syntax Tree (AST), memungkinkan pemisahan tegas antara teks prosa manusia, metadata, dan blok kode teknis.
2. **Karakteristik Engine RE2**: Eksekusi aturan regex pada Vale bergantung pada Google RE2 engine yang mengeliminasi risiko *Catastrophic Backtracking* ($O(n)$ linear complexity), namun menuntut rekayasa aturan tanpa *lookarounds* melalui pemanfaatan cerdas scope semantik, exception lists, dan extension points.
3. **Pilar Extension Points**: Fleksibilitas kustomisasi Vale bertumpu pada declarative YAML extension points (`existence`, `substitution`, `consistency`, `occurrence`, `repetition`, `conditional`, dan `script`) yang memetakan logika pemeriksaan gaya penulisan tanpa memerlukan kompilasi ulang biner.
4. **Docs-as-Code Scalability**: Pada implementasi skala enterprise, Vale harus diarsitektursikan secara modular: mendistribusikan style terpusat via *Vale Packages/Sync*, meminimalkan latensi eksekusi via *Git Delta Linting*, dan menegakkan tata kelola kualitas dokumentasi via automated status checks di CI/CD pull request workflows.