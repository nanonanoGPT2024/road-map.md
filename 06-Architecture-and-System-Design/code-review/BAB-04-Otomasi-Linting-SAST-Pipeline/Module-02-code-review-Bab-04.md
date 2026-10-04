# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Topik: Code Review (Kategori: 06-Architecture-and-System-Design)
### BAB 04: Otomasi Linting, SAST, dan Pipeline Quality Gate
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, *Staff/Principal Engineer* dan *DevSecOps Architect* diharapkan mampu:

1. **Merancang Arsitektur Differential Static Analysis**: Mengembangkan sistem *automated code review* yang menganalisis perbedaan sintaksis (*diff-aware AST*) secara inkremental tanpa memindai seluruh *monorepo* pada setiap *commit*.
2. **Menulis Custom Security Engine Rules**: Mengabstraksikan pola kerentanan spesifik enterprise ke dalam aturan deklaratif (Semgrep/CodeQL) untuk mendeteksi *insecure deserialization*, *IDOR*, dan kebocoran *credential context* secara deterministik.
3. **Membangun Pipeline Aggregation Multi-Scanner berbasis SARIF**: Mengintegrasikan, mendeduplikasi, dan menormalkan temuan dari linter, SAST, SCA, dan *secret scanner* ke dalam satu format standar (*OASIS SARIF*) untuk memblokir *Pull Request* secara terukur.
4. **Mengoptimalkan Latensi Eksekusi CI/CD**: Mereduksi durasi evaluasi *quality gate* hingga di bawah 3 menit pada basis kode berskala jutaan baris (LoC) menggunakan teknik *dynamic path filtering*, *remote execution caching*, dan *parallel shard orchestration*.
5. **Menerapkan Zero-Trust Review Architecture**: Memastikan integritas artefak kode dan pipeline melalui penandatanganan kriptografis (*cosign*/*sigstore*), mitigasi manipulasi branch (*branch protection rule bypass prevention*), dan pembatasan izin (*least privilege IAM scopes*).

---

### 2. Prerequisite

Sebelum menelaah modul ini, peserta wajib menguasai:
* Pemahaman mendalam tentang struktur data *Abstract Syntax Tree* (AST) dan *Control Flow Graph* (CFG).
* Kemahiran dalam orkestrasi pipeline CI/CD modern (GitHub Actions, GitLab CI, atau Tekton Pipelines).
* Pemahaman model ancaman OWASP Top 10 API & Web (khususnya *Broken Object Level Authorization*, *Injection*, dan *Sensitive Data Exposure*).
* Kemampuan dasar dalam membaca dan memodifikasi format pertukaran data keamanan: JSON, YAML, dan OASIS SARIF v2.1.0.
* Pemahaman operasional Git internals (plumbing commands: `git rev-parse`, `git diff-tree`, `git merge-base`).

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi otomatisasi *code review* pada skala enterprise tidak sekadar mengeksekusi CLI linter pada *runner* virtual, melainkan membangun *distributed analysis engine* yang bekerja secara asinkron dan deterministik.

```
+---------------------------------------------------------------------------------------------------------+
|                                    ENTERPRISE CODE REVIEW PIPELINE ENGINE                               |
+---------------------------------------------------------------------------------------------------------+
                                                     |
                                   (1) Git Push / Pull Request Event
                                                     v
                         +-------------------------------------------------------+
                         |       Event Dispatcher & Workload Orchestrator        |
                         |  - Git Merge-Base Detection (`HEAD...origin/main`)    |
                         |  - Sparse Checkout / Target Path Filtering            |
                         +-------------------------------------------------------+
                                                     |
         +-------------------------------------------+-------------------------------------------+
         |                                           |                                           |
         v                                           v                                           v
+-------------------+                       +-------------------+                       +-------------------+
|  LINTER SHARD     |                       |    SAST SHARD     |                       |    SCA / SECRET   |
| (GolangC / ESLint)|                       | (Semgrep / CodeQL)|                       | (Trivy / Gitleaks)|
+-------------------+                       +-------------------+                       +-------------------+
  - Cached AST Parse                          - Deep Dataflow Analysis                    - Lockfile Parsing
  - Changed Lines Diff Filter                 - Taint Tracking                            - Entropy Scan
         |                                           |                                           |
         +-------------------------------------------+-------------------------------------------+
                                                     |
                                        (2) Emisi Hasil (SARIF Output)
                                                     v
                         +-------------------------------------------------------+
                         |        SARIF Ingestion & Aggregation Engine           |
                         |  - Fingerprinting (Deduplikasi via `partialFingerprint`|
                         |  - Baseline Matching (Suppress legacy issues)         |
                         |  - Policy Engine (OPA / Rego Enforcement)             |
                         +-------------------------------------------------------+
                                                     |
                                        (3) Gating Decision Evaluation
                                                     v
                         +-------------------------------------------------------+
                         |                Automated Feedback Loop                |
                         |  - Non-blocking Inline Review Comments (Info/Warn)    |
                         |  - Hard-Gate Block (PR Status Check = Failed)         |
                         |  - Metrics telemetry sink to Datadog/Prometheus      |
                         +-------------------------------------------------------+
```

#### Komponen Internal Arsitektur:

1. **AST & Control Flow Graph (CFG) Parsing**:
   Alih-alih melakukan pencocokan string berbasis RegEx biasa yang rentan terhadap *false positive*, *scanner* berbasis AST memecah kode menjadi node token sintaksis. Engine SAST tingkat lanjut kemudian mengompilasi AST menjadi CFG untuk menelusuri aliran data (*taint tracking*) dari *Source* (input pengguna yang belum divalidasi) menuju *Sink* (fungsi berbahaya seperti *SQL Execution* atau *System Exec*).

2. **Differential Static Analysis (Diff-Aware Execution)**:
   Pada basis data kode masif, pemindaian menyeluruh (*full scan*) membutuhkan waktu puluhan menit hingga berjam-jam. Differential Static Analysis membatasi evaluasi hanya pada *ancestor graph* terdekat menggunakan:
   $$\Delta_{files} = \text{git diff} --name-only \ (\text{merge-base}(PR_{head}, Target_{base}), PR_{head})$$
   Engine SAST memetakan $\Delta_{files}$ ke dalam AST dan mengevaluasi batasan aturan hanya jika *source* atau *sink* berada di dalam baris yang berubah, atau jika relasi semantiknya terpengaruh oleh commit tersebut.

3. **SARIF Aggregation & Deduplication**:
   *Static Analysis Results Interchange Format* (SARIF) adalah format standar JSON OASIS. Enterprise pipeline mengonsolidasikan beragam *output* linter menjadi satu model domain terpadu. Pada tahap agregasi, engine menghitung *fingerprint* unik untuk setiap temuan menggunakan algoritma hashing kontekstual:
   $$\text{Fingerprint} = \text{SHA256}(\text{RuleID} + \text{NormalizedFilePath} + \text{SurroundingASTContext})$$
   Hal ini mencegah munculnya peringatan ganda ketika baris kode bergeser akibat penambahan baris baru di atasnya.

4. **Zero-Trust Review Attestation**:
   Pipelines tidak boleh berasumsi bahwa kode yang diuji pada runner adalah kode yang disetujui. Pipeline menghasilkan bukti kriptografis (*cryptographic attestation*) bahwa rangkaian tes dan scanner lolos verifikasi menggunakan identitas OIDC penyedia Git (seperti GitHub/GitLab Workload Identity Federation).

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional | Enterprise Automated Review Architecture |
| :--- | :--- | :--- |
| **Cakupan Pemindaian** | Full-scan setiap commit (lambat, membebani runner). | *Differential Scan* berbasis graph dependensi dan baris yang terdampak. |
| **Logika Aturan** | Rule generik bawaan vendor (*one-size-fits-all*). | Rule kustom (*in-house declarative AST*) yang disesuaikan dengan SDK internal. |
| **Mekanisme Umpan Balik** | Ratusan halaman log teks pada konsol CI/CD. | *SARIF Injection* langsung sebagai komentar pada baris target PR. |
| **Manajemen False Positive** | Pengecualian manual via komentar `// nolint` di kode. | *Baseline hashing* terpusat dengan masa kedaluwarsa (*time-to-live exception*). |
| **Keandalan & Skalabilitas** | Satu pipeline monolitik yang dijalankan berurutan. | *Sharded parallel execution* berbasis path filter dengan komputasi terdistribusi. |

#### Mengapa Arsitektur Ini Kritis?
Beban kognitif seorang *human code reviewer* meningkat secara eksponensial seiring bertambahnya ukuran tim dan kompleksitas sistem. Ketika *reviewer* dipaksa mencari masalah trivial seperti *style guide*, *null pointer dereference*, atau konfigurasi injeksi dependensi yang salah, fokus mereka teralihkan dari evaluasi arsitektur, konkurensi, dan logika bisnis. Otomasi pipeline bertindak sebagai garis pertahanan pertama (*Tier-1 Quality Gate*), memastikan bahwa kode yang masuk ke tahap peninjauan manusia telah memenuhi standar keamanan sintaksis, semantik, dan integritas dasar secara mutlak.

---

### 5. How (Workflow Detail)

Alur kerja evaluasi otomatis tingkat enterprise dirancang melalui urutan tahap berikut:

```
[Developer Push]
       │
       ▼
[Webhook Verification] ──► Validasi Payload & Identitas OIDC
       │
       ▼
[Metadata Calculation]
  ├── Hitung Merge-Base: BASE=$(git merge-base origin/main HEAD)
  ├── Ekstraksi Affected Files: git diff --name-only $BASE HEAD
  └── Filter Jalur Berdasarkan Pola (Glob Routing)
       │
       ├─────────────────────────┬─────────────────────────┐
       ▼                         ▼                         ▼
[Track A: Linter]         [Track B: SAST]          [Track C: Secret/SCA]
(ESLint, Go Vet)        (Semgrep Deep-Taint)        (Trivy, Gitleaks)
  - Restore AST Cache       - Parse Rules Internal     - Scan Dependency Diffs
  - Inkremental Eval        - Diff-Aware Analysis      - Entropy Evaluation
       │                         │                         │
       └─────────────────────────┼─────────────────────────┘
                                 │
                                 ▼
                     [SARIF Collector & Parser]
                       - Normalisasi URI File
                       - Inject Git Commit SHA
                       - Filter "Baseline Accepted Issues"
                                 │
                                 ▼
                    [OPA Policy Engine Evaluation]
                       - Hitung Ambang Batas Severity
                       - Block jika: High/Critical > 0
                       - Warn jika: Medium > 3
                                 │
                                 ▼
                     [PR Annotation Dispatcher]
                       - Update Status Check API
                       - Mutasi Komentar PR (Add/Update/Resolve)
```

1. **Trigger Phase**: Webhook menerima event `pull_request.synchronize`. Runner CI mengaktifkan identitas berbasis token OIDC berumur pendek (*short-lived token*).
2. **Context Determination**: Pipeline membandingkan `merge-base` target branch terhadap `head commit`. Hanya berkas yang diubah yang dialokasikan ke dalam matriks pekerja (*worker shards*).
3. **Parallel Sharding Execution**:
   * *Shard 1*: Menjalankan linter bahasa spesifik dengan cache yang dipetakan pada hash *lockfile*.
   * *Shard 2*: Menjalankan *Semgrep AST engine* menggunakan aturan keamanan proprietary enterprise.
   * *Shard 3*: Menjalankan analisis dependensi *Supply Chain* terhadap manifest yang termutasi.
4. **SARIF Consolidation**: Menggabungkan seluruh artefak `.sarif` dari runner terdistribusi ke satu runner agregator.
5. **Policy Enforcement via Open Policy Agent (OPA)**: Mengevaluasi output SARIF gabungan terhadap aturan bisnis (misalnya: *“Blokir commit jika terdapat CVE severity High dengan skor CVSS > 7.0 tanpa mitigasi eksplisit”*).
6. **PR Surface Feedback**: Memetakan baris temuan SARIF ke GitHub Checks/GitLab Discussion API, lalu mempublikasikan komentar secara terstruktur pada diff terkait.

---

### 6. Analogy & Diagram ASCII

Bayangkan sistem pemeriksaan keamanan di bandara internasional:

```
Pemeriksaan Bandara Tradisional:
[Semua Penumpang] ──► [Antrean Tunggal] ──► [Bongkar Seluruh Koper] ──► [Sangat Lambat (Bottleneck)]

Arsitektur Enterprise Automated Code Review:
[Semua Penumpang] ──► [Smart Profiling] ──► [Biometrik & Tiket Valid?] ──► Gagal? Tolak di Awal
                                │
               ┌────────────────┴────────────────┐
               ▼                                 ▼
      [Bagasi Baru/Berubah]             [Bagasi Transit/Lama]
               │                                 │
               ▼                                 ▼
   [Scanner Sinar-X Spesifik]              [Bypass Cepat]
   (Deteksi Logika Bahaya Saja)             (Sudah Terverifikasi)
               │                                 │
               └────────────────┬────────────────┘
                                │
                                ▼
         [Security Gate: Clearance Terpadu (SARIF)]
```

* **Full Scan Tradisional** ibarat membongkar seluruh isi koper setiap penumpang, bahkan untuk penumpang transit yang tidak pernah keluar ruang tunggu.
* **Differential Automated Review** memverifikasi identitas secara otomatis, melacak bagasi mana yang mengalami perubahan isi fisik sejak pemeriksaan terakhir, dan memindainya menggunakan sinar-X presisi tinggi pada bagian yang berubah saja.

---

### 7. Simple Example & Practical Example

#### A. Contoh Sederhana: Custom Semgrep Rule untuk Mendeteksi Insecure Logging
Aturan deklaratif untuk memblokir pencatatan data sensitif (PII/Kredensial) ke dalam log aplikasi.

```yaml
# rules/security/no-sensitive-logging.yaml
rules:
  - id: prevent-sensitive-data-logging
    patterns:
      - pattern-either:
          - pattern: $LOGGER.info(..., $CRED, ...)
          - pattern: $LOGGER.error(..., $CRED, ...)
          - pattern: $LOGGER.debug(..., $CRED, ...)
      - metavariable-regex:
          metavariable: $CRED
          regex: (?i).*(password|secret|token|apikey|authorization|creditcard).*
    message: "Terdeteksi potensi kebocoran PII/Kredensial pada logging variable: $CRED. Gunakan masking sebelum log."
    languages: [go, python, javascript, typescript]
    severity: ERROR
```

#### B. Contoh Praktis: Pipeline GitHub Actions Enterprise Lengkap
Implementasi workflow CI/CD tingkat produksi: memindai kode secara inkremental, mengeksekusi *Semgrep*, mengagregasi SARIF, dan memblokir *Pull Request* jika terjadi pelanggaran fatal.

```yaml
# .github/workflows/enterprise-code-review-gate.yml
name: Enterprise Quality & Security Gate

on:
  pull_request:
    branches: [main, release/*]
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write
  security-events: write
  checks: write

concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true

jobs:
  differential-metadata:
    name: Determine Changed Paths
    runs-on: ubuntu-latest
    outputs:
      has_code_changes: ${{ steps.filter.outputs.backend }}
      base_sha: ${{ steps.base.outputs.base_sha }}
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Resolve Dynamic Base Commit
        id: base
        run: |
          # Dapatkan titik potong (merge-base) historis terdekat
          BASE_COMMIT=$(git merge-base origin/${{ github.base_ref }} HEAD)
          echo "base_sha=${BASE_COMMIT}" >> $GITHUB_OUTPUT

      - name: Paths Filter
        id: filter
        uses: dorny/paths-filter@v3
        with:
          base: ${{ steps.base.outputs.base_sha }}
          filters:
            backend:
              - '**/*.go'
              - '**/*.py'
              - '**/*.ts'
              - '**/go.mod'
              - '**/package.json'

  sast-analysis:
    name: Differential SAST Scanner
    needs: [differential-metadata]
    if: needs.differential-metadata.outputs.has_code_changes == 'true'
    runs-on: ubuntu-latest
    container:
      image: returntocorp/semgrep:1.78.0
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Run Differential Semgrep Engine
        env:
          BASE_SHA: ${{ needs.differential-metadata.outputs.base_sha }}
        run: |
          echo "Memulai analisis differensial dari ${BASE_SHA} ke HEAD..."
          
          # Eksekusi scanning hanya terhadap perubahan dengan baseline git
          semgrep scan \
            --config=rules/security/ \
            --config=p/owasp-top-ten \
            --baseline-commit="${BASE_SHA}" \
            --sarif \
            --output=semgrep-results.sarif \
            --verbose

      - name: Upload SAST Artifact
        uses: actions/upload-artifact@v4
        with:
          name: sast-sarif-report
          path: semgrep-results.sarif

  gate-enforcement:
    name: Quality Gate Evaluation
    needs: [sast-analysis]
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Download SARIF Artifact
        uses: actions/download-artifact@v4
        with:
          name: sast-sarif-report

      - name: Upload to GitHub Security Tab (SARIF Ingestion)
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: semgrep-results.sarif
          category: semgrep-differential-gate

      - name: Strict Threshold Gatekeeper (Python Processor)
        shell: python
        run: |
          import json
          import sys

          try:
              with open('semgrep-results.sarif', 'r') as f:
                  data = json.load(f)
          except FileNotFoundError:
              print("File SARIF tidak ditemukan, membatalkan pemeriksaan.")
              sys.exit(1)

          critical_issues = 0
          high_issues = 0
          runs = data.get('runs', [])

          for run in runs:
              results = run.get('results', [])
              for res in results:
                  level = res.get('level', 'warning').lower()
                  rule_id = res.get('ruleId', 'unknown')
                  msg = res.get('message', {}).get('text', '')
                  
                  if level == 'error':
                      critical_issues += 1
                      print(f"::error file={res['locations'][0]['physicalLocation']['artifactLocation']['uri']},title={rule_id}::{msg}")
                  elif level == 'warning':
                      high_issues += 1
                      print(f"::warning file={res['locations'][0]['physicalLocation']['artifactLocation']['uri']},title={rule_id}::{msg}")

          print(f"\nRingkasan Temuan: Critical/Error={critical_issues}, Warning={high_issues}")

          if critical_issues > 0:
              print(f"PENOLAKAN PR: Ditemukan {critical_issues} pelanggaran level ERROR/CRITICAL.")
              sys.exit(1)
          
          print("Quality gate disetujui. Melanjutkan pipeline merge.")
          sys.exit(0)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Insiden Penetrasi FinTech "BankPay" (50 Juta Transaksi/Hari)
* **Konteks**: BankPay memiliki arsitektur monorepo backend Golang yang memuat 4,5 juta baris kode dengan kontribusi harian lebih dari 200 engineer.
* **Insiden**: Sebuah PR sederhana yang memodifikasi endpoint transfer disetujui oleh dua *peer reviewer*. Namun, terdapat kerentanan *Broken Object Level Authorization* (BOLA/IDOR). Parameter `account_id` diambil langsung dari JSON payload pengguna dan diinjeksikan ke dalam SQL query tanpa validasi relasi terhadap token sesi `sub` milik JWT.
* **Dampak**: Kerugian finansial signifikan sebelum celah keamanan berhasil ditambal, serta investigasi regulatori yang menuntut pembekuan fitur selama satu minggu.
* **Evaluasi Kegagalan Manual Review**: Human reviewer berasumsi fungsi `service.ExecuteTransfer()` telah memverifikasi kepemilikan akun, sementara penulis PR mengira validasi dilakukan pada API gateway middleware. Tidak ada pihak yang memverifikasi alur propagasi data tersebut.

#### Solusi Implementasi Automasi Lanjutan:
1. **Penerapan Taint-Tracking Rules Kustom pada Semgrep**:
   Tim SecOps BankPay membangun aturan kustom berorientasi *Source-to-Sink analysis* yang melacak variabel dari konteks controller:

   ```yaml
   rules:
     - id: go-missing-jwt-ownership-validation
       languages: [go]
       severity: ERROR
       message: "Konteks transaksi mengikat langsung ID tanpa verifikasi AuthClaimsContext."
       mode: taint
       pattern-sources:
         - pattern: func($CTX context.Context, $REQ *TransferRequest) ...
       pattern-sanitizers:
         - pattern: auth.ValidateAccountOwnership($CTX, ...)
       pattern-sinks:
         - pattern: db.ExecContext($CTX, "UPDATE accounts SET balance ...", ...)
   ```

2. **Infrastruktur Sharded Differential Scanner**:
   * CI runner dikonfigurasi menggunakan cluster Kubernetes mandiri (*Self-hosted K8s Runners*).
   * Pemindaian dioptimalkan menggunakan *differential base targeting*. Waktu rata-rata scan turun drastis dari **28 menit** (full AST scan) menjadi **1 menit 45 detik** (diff scan).
3. **Hasil Pascaimplementasi**:
   * Menangkap 14 potensi insiden IDOR serupa dalam waktu tiga bulan pertama di lingkungan pra-merge.
   * Tingkat *false positive* ditekan hingga < 3% melalui penyempurnaan `pattern-sanitizers`.

---

### 9. Trade-offs (Analisis Kompromi)

Membangun pipeline automasi review memerlukan perimbangan arsitektural yang cermat di berbagai dimensi:

```
                  TINGKAT KETATNYA ATURAN (PRECISION)
                                ▲
                                │   * Area Ideal (Rule Kustom Enterprise)
                                │   Rendah False Positive, Pipeline Cepat
                                │
                                │
        * AST Regex Scan        │        * Deep Interprocedural SAST
        Cepat, tapi False       │        Analisis Sangat Akurat,
        Positive Sangat Tinggi  │        tapi Pipeline Lambat (Timeouts)
  ◄─────────────────────────────┼─────────────────────────────►
  RENDAH (LATENSI MINIMAL)       │       TINGGI (LATENSI BESAR)
                                │
                                │   * Tanpa Quality Gate
                                │   Commit Cepat, Risiko Bencana Produksi
                                ▼
                   LATENSI EKSEKUSI PIPELINE CI/CD
```

| Pendekatan / Keputusan | Keuntungan | Kerugian & Batasan Teknis | Dampak Biaya & Komputasi |
| :--- | :--- | :--- | :--- |
| **Shallow Regex Scanners** (e.g., Flake8, RegEx Match) | Waktu pemrosesan kilat (< 10 detik). Ringan terhadap konsumsi memori runner. | Buta terhadap konteks aliran data (*zero context awareness*). Menghasilkan noise tinggi. | Sangat Rendah. Runner micro standar sudah memadai. |
| **Deep Interprocedural SAST** (e.g., CodeQL Full Path) | Menangkap eksploitasi multi-file yang kompleks secara matematis. | Analisis Graph memakan memori masif (16GB+ RAM) dan waktu komputasi 30-60 menit. | Sangat Tinggi. Runner spesifikasi komputasi tinggi; berisiko menurunkan *developer velocity*. |
| **Differential Syntactic Scan** (e.g., Semgrep Diff/Custom) | Kompromi ideal: scanning dalam hitungan detik, presisi tinggi pada baris perubahan. | Rentan melewatkan celah jika perubahan fungsi di File A merusak invariants di File B tanpa modifikasi di File B. | Sedang. Memerlukan strategi caching artefak dan sinkronisasi baseline commit. |
| **Strict Hard-Gate Blocking** | Menjamin 0% regresi kode bermasalah masuk ke trunk branch. | *Developer friction* meningkat drastis jika ada aturan edge-case yang memblokir PR darurat (*hotfix*). | Risiko bisnis: waktu mitigasi incident melambat jika mekanisme bypass (*break-glass*) tidak disiapkan. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Fatal Evaluasi Base Commit pada CI/CD
* **Gejala**: Pipeline memindai ribuan berkas lama yang tidak relevan dengan PR, atau sebaliknya: tidak mendeteksi perubahan sama sekali (`Empty Diff`).
* **Akar Masalah**: Menggunakan `git diff HEAD~1` pada commit merge sementara (*ephemeral merge commit*) yang dihasilkan otomatis oleh GitHub Actions.
* **Solusi Perbaikan**: Gunakan kalkulasi `merge-base` secara eksplisit:
  ```bash
  # SALAH: Hanya mengambil commit terakhir dari branch PR
  git diff --name-only HEAD~1

  # BENAR: Mengambil delta murni antara trunk target dan feature branch
  TARGET_BRANCH="origin/${{ github.base_ref }}"
  MERGE_BASE=$(git merge-base ${TARGET_BRANCH} HEAD)
  git diff --name-only ${MERGE_BASE} HEAD
  ```

#### 2. Matriks Run Terlalu Banyak Menghasilkan False Positive Alert Spams
* **Gejala**: Komentar bot membanjiri PR dengan lusinan pesan peringatan minor, membuat engineer mengabaikan seluruh hasil analisis (*alert fatigue*).
* **Solusi**: Terapkan stratifikasi level penanganan SARIF:
  * Level **Error** = Langsung blokir PR (*Hard Gate*), buat *blocking inline review*.
  * Level **Warning** = Tampilkan *collapsible summary table* di deskripsi utama PR tanpa memblokir merge.
  * Level **Note/Info** = Simpan hanya di *security tab internal / log artifact*, tidak ditampilkan di halaman PR.

#### 3. Kehabisan Memori (OOM Killer) pada Pemindaian Dependency Monorepo
* **Gejala**: Step SAST tiba-tiba mati dengan *Exit Code 137*.
* **Solusi Troubleshooting**:
  1. Batasi kedalaman analisis traversal: atur flag `--max-target-bytes=5000000` (lewati berkas *generated* berukuran gigantik).
  2. Tambahkan alokasi swap space virtual pada GitHub Runner via runner setup script.
  3. Konfigurasi file `.semgrepignore` atau `.scannerignore` untuk mengecualikan berkas mock, artefak kompilasi (`dist/`, `vendor/`, `build/`), dan snapshot tes.

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum merilis automasi pipeline ke repository production:

- [ ] **Deterministic Git History**: Runner mengeksekusi `git fetch --depth=0` atau mengambil riwayat yang cukup hingga `merge-base` target branch dapat dipastikan secara matematis.
- [ ] **Ephemeral & Sandboxed Runners**: Pemindaian kode dijalankan di container terisolasi tanpa akses menulis (*read-only*) ke branch target atau secrets deployment produksi.
- [ ] **Short-Lived OIDC Authentication**: Komunikasi antara scanner ke platform internal (SonarQube, DefectDojo) tidak menggunakan token statis, melainkan verifikasi identitas token OIDC GitHub/GitLab.
- [ ] **Least Privilege GitHub Tokens**: Scope token pipeline dibatasi seminimal mungkin:
  ```yaml
  permissions:
    contents: read
    pull-requests: write
    security-events: write
  ```
- [ ] **Dynamic Timeouts**: Setiap proses analisis wajib memiliki batas waktu eksekusi tegas (`timeout-minutes: 10`) untuk mencegah hanging process yang memakan antrean runner.
- [ ] **SARIF Normalization**: Path file dalam laporan SARIF dinormalkan agar selalu relatif terhadap *repository root* (`src/main.go`, bukan `/home/runner/work/.../src/main.go`).
- [ ] **Break-Glass Mechanism**: Tersedia prosedur bypass yang teraudit (misalnya label PR `security-override` yang membutuhkan persetujuan minimal dari *Principal Security Engineer*) untuk rilis darurat (*production hotfix*).

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun sebuah custom differential SAST engine modular lengkap dengan rule kustom, parser agregasi, dan validator baseline.

#### Struktur Direktori:
Simpan seluruh artefak ini di direktori: `hands-on/m02/`
```
hands-on/m02/
├── .rules/
│   └── secure-sql.yaml
├── src/
│   ├── database.py
│   └── vulnerable.py
├── scripts/
│   └── diff_scanner.sh
└── validator/
    └── sarif_enforcer.py
```

#### Langkah 1: Siapkan Aturan Custom Semgrep
Tulis aturan deteksi injeksi SQL dinamis untuk dialek Python.

```yaml
# hands-on/m02/.rules/secure-sql.yaml
rules:
  - id: python-raw-sql-concatenation
    languages: [python]
    severity: ERROR
    message: "Terdeteksi pembuatan kueri SQL menggunakan string formatting / f-string. Gunakan parameter binding."
    patterns:
      - pattern-either:
          - pattern: $DB.execute(f"...{$VAR}...")
          - pattern: $DB.execute("..." % ($VAR))
          - pattern: $DB.execute("...".format($VAR))
          - pattern: $CURSOR.execute(f"...{$VAR}...")
```

#### Langkah 2: Buat Kode Sumber Target (Good vs Bad)

```python
# hands-on/m02/src/vulnerable.py
import sqlite3

def get_user_bad(cursor, user_id):
    # Pelanggaran: Menggunakan f-string di cursor.execute
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    return cursor.execute(query).fetchall()

def get_user_good(cursor, user_id):
    # Aman: Menggunakan parameterized query
    query = "SELECT * FROM users WHERE id = ?"
    return cursor.execute(query, (user_id,)).fetchall()
```

#### Langkah 3: Buat Bash Engine untuk Differential Analysis

```bash
#!/usr/bin/env bash
# hands-on/m02/scripts/diff_scanner.sh
set -euo pipefail

TARGET_BRANCH=${1:-"main"}
OUTPUT_SARIF="hands-on/m02/scan-output.sarif"

echo "=== MENGHITUNG PERBEDAAN GIT TERHADAP $TARGET_BRANCH ==="

# Simulasikan identifikasi file yang berubah jika dijalankan secara lokal
CHANGED_FILES=$(git diff --name-only "${TARGET_BRANCH}"...HEAD -- 'hands-on/m02/src/*.py' || true)

if [ -z "$CHANGED_FILES" ]; then
    echo "[INFO] Tidak ada file Python yang termutasi. Menjalankan fallback ke seluruh src directory."
    TARGET_SCAN="hands-on/m02/src/"
else
    echo "[INFO] File yang terdampak:"
    echo "$CHANGED_FILES"
    TARGET_SCAN="$CHANGED_FILES"
fi

echo "=== MENJALANKAN SEMGREP DENGAN RULES INTERNAL ==="
semgrep scan \
    --config="hands-on/m02/.rules/" \
    --sarif \
    --output="$OUTPUT_SARIF" \
    $TARGET_SCAN

echo "[SUKSES] Analisis selesai. Output tersimpan di $OUTPUT_SARIF"
```

#### Langkah 4: Buat Policy Gate Enforcer Menggunakan Python

```python
#!/usr/bin/env python3
# hands-on/m02/validator/sarif_enforcer.py
import json
import sys
import os

def evaluate_sarif(sarif_path: str, max_critical: int = 0, max_warnings: int = 2):
    if not os.path.exists(sarif_path):
        print(f"Error: Target file {sarif_path} tidak ditemukan.")
        sys.exit(1)

    with open(sarif_path, "r", encoding="utf-8") as f:
        sarif_data = json.load(f)

    critical_count = 0
    warning_count = 0
    violations = []

    for run in sarif_data.get("runs", []):
        for result in run.get("results", []):
            rule_id = result.get("ruleId", "UNKNOWN_RULE")
            level = result.get("level", "warning").lower()
            msg = result.get("message", {}).get("text", "")
            
            locations = result.get("locations", [])
            loc_str = "Unknown location"
            if locations:
                phys = locations[0].get("physicalLocation", {})
                uri = phys.get("artifactLocation", {}).get("uri", "")
                line = phys.get("region", {}).get("startLine", 0)
                loc_str = f"{uri}:{line}"

            entry = f"[{level.upper()}] Rule: {rule_id} di {loc_str} -> {msg}"
            violations.append(entry)

            if level == "error":
                critical_count += 1
            elif level == "warning":
                warning_count += 1

    print("=== HASIL EVALUASI QUALITY GATE ===")
    for v in violations:
        print(v)
    print("-----------------------------------")
    print(f"Total Errors/Critical: {critical_count} (Limit: {max_critical})")
    print(f"Total Warnings        : {warning_count} (Limit: {max_warnings})")

    if critical_count > max_critical:
        print("\n[FAILED] Pipeline dihentikan: Ambang batas pelanggaran Critical terlampaui!")
        sys.exit(1)

    if warning_count > max_warnings:
        print("\n[FAILED] Pipeline dihentikan: Terlalu banyak temuan level Warning!")
        sys.exit(1)

    print("\n[PASSED] Seluruh kriteria evaluasi terpenuhi. PR disetujui untuk merge.")
    sys.exit(0)

if __name__ == "__main__":
    sarif_file = sys.argv[1] if len(sys.argv) > 1 else "hands-on/m02/scan-output.sarif"
    evaluate_sarif(sarif_file)
```

#### Langkah Pengujian:
1. Pastikan executable izin telah diatur:
   ```bash
   chmod +x hands-on/m02/scripts/diff_scanner.sh
   chmod +x hands-on/m02/validator/sarif_enforcer.py
   ```
2. Jalankan scanner untuk memproduksi SARIF:
   ```bash
   ./hands-on/m02/scripts/diff_scanner.sh HEAD
   ```
3. Evaluasi file SARIF menggunakan validator:
   ```bash
   python3 hands-on/m02/validator/sarif_enforcer.py hands-on/m02/scan-output.sarif
   ```
   *Ekspektasi*: Program keluar dengan `sys.exit(1)` karena menemukan kerentanan SQL formatting di `hands-on/m02/src/vulnerable.py`.

---

### 13. Exercise

Kerjakan skenario latihan berikut untuk memperkuat pemahaman operasional:

#### Level Easy
Tulis sebuah aturan Semgrep tunggal (`.yaml`) yang mendeteksi penggunaan package `crypto/md5` atau `crypto/sha1` pada kode Golang, karena algoritma hashing tersebut sudah tidak aman secara kriptografis (*broken collision resistance*).

#### Level Medium
Buat sebuah script Python standalone yang mem-parsing file format SARIF v2.1.0, lalu mengonversi setiap temuan menjadi format Markdown Table yang siap di-post sebagai rangkuman komentar PR di GitHub API:
* Kolom tabel: `Rule ID`, `Severity`, `File Location`, `Line`, dan `Recommended Mitigation`.

#### Level Hard
Rancang arsitektur pipeline menggunakan Docker Compose yang menjalankan dua container lokal yang saling terisolasi:
1. **Container A (Runner)**: Melakukan clone repositori lokal dan memproduksi SARIF.
2. **Container B (OPA Gatekeeper Daemon)**: Menerima file SARIF melalui request HTTP POST, mengevaluasi kebijakan berbasis berkas `.rego` internal, dan mengembalikan respons HTTP `200 OK` jika PR boleh lolos atau `403 Forbidden` lengkap dengan rincian kegagalan evaluasi.

---

### 14. Challenge

**Skenario**: Anda adalah Enterprise Architect di sebuah institusi perbankan dengan arsitektur monorepo 10 juta baris kode Java & Kotlin. Tim Anda memiliki target SLA evaluasi PR maksimal **3 menit**. 

Setiap kali engineer membuat PR:
1. Scanner lama menghabiskan waktu 45 menit karena membaca seluruh dependensi class paths (*whole-program resolution*).
2. Jika ada vulnerability lama (*legacy technical debt* dari 5 tahun lalu) pada berkas yang disentuh, developer yang bersangkutan menolak memperbaikinya karena merasa itu bukan kode yang mereka ubah (*boy scout rule* tidak dapat dipaksakan untuk rilis darurat).

**Tugas Arsitektur**:
Rancang dokumen arsitektur komprehensif (lengkap dengan pseudocode/flowchart/diagram runner) yang menjawab:
* Bagaimana mendesain **Contextual AST Caching** yang menyimpan state kompilasi class graph di memori/storage terdistribusi (Redis/S3/MinIO) antar commit?
* Bagaimana mengimplementasikan algoritma **Precise Line Blame Attribution** yang membaca SARIF hasil scan dan mencocokkannya dengan `git blame --incremental`, sehingga:
  * Jika temuan berada di baris yang diubah oleh pembuat PR $\to$ Blokir (*Hard Gate*).
  * Jika temuan berada di baris yang tidak disentuh oleh pembuat PR (meskipun berada di berkas yang sama) $\to$ Abaikan atau mutasikan ke *Silent Technical Debt Registry*.
* Sajikan solusi ini tanpa bergantung pada vendor cloud tertutup (wajib *vendor-agnostic* menggunakan OSS tooling).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)

1. Apa perbedaan mendasar antara analisis statis berbasis RegEx murni dengan analisis berbasis Abstract Syntax Tree (AST)?
   * A. RegEx memahami semantic tipe data variabel, sedangkan AST hanya mengenali teks mentah.
   * B. AST mengurai kode menjadi struktur hierarki pohon sintaksis bahasa, sedangkan RegEx hanya mencocokkan pola string linear tanpa konteks logika program.
   * C. AST hanya bisa digunakan untuk bahasa pemrograman bertipe statis seperti Java dan Go.
   * D. RegEx membutuhkan compiler untuk mengeksekusi kode sebelum scanning dimulai.

2. Standar industri OASIS SARIF v2.1.0 dirancang terutama untuk mengatasi masalah apa?
   * A. Kompilasi otomatis kode program lintas platform.
   * B. Format biner terkompresi untuk mempercepat eksekusi unit test.
   * C. Interoperabilitas format output laporan analisis statis dari berbagai vendor scanner yang berbeda ke dalam satu format standar.
   * D. Manajemen token otentikasi zero-trust pada cluster Kubernetes.

3. Manakah perintah Git yang paling tepat untuk menentukan batas dasar (*base ancestor*) analisis differensial pada Pull Request?
   * A. `git log -n 1`
   * B. `git diff HEAD~1`
   * C. `git merge-base origin/main HEAD`
   * D. `git rebase --onto`

4. Mengapa pipeline automasi *code review* sebaiknya menghindari token GitHub dengan cakupan `repo:status` yang berumur panjang (*long-lived personal access tokens*)?
   * A. Token berumur panjang membatasi kecepatan download dependensi pihak ketiga.
   * B. Melanggar prinsip *Least Privilege* dan berisiko memicu eskalasi hak akses (*lateral movement*) jika runner dieksploitasi oleh kode berbahaya.
   * C. Engine SARIF menolak token yang tidak menggunakan enkripsi RSA 4096-bit.
   * D. Git tidak mendukung autentikasi HTTPS menggunakan personal access token.

5. Dalam terminologi SAST Taint Analysis, apa yang dimaksud dengan istilah *Sink*?
   * A. Titik masuk input dari user, seperti parameter URL atau payload HTTP POST.
   * B. Fungsi atau proses validasi dan sanitasi yang membersihkan input berbahaya.
   * C. Titik eksekusi sensitif/kritis dalam aplikasi di mana data yang tidak aman dapat memicu kerentanan sistem.
   * D. Cache internal yang menyimpan dependensi library secara sementara.

---

#### Bagian 2: Intermediate (Pilihan Ganda)

6. Pada integrasi CI/CD tingkat lanjut, apa fungsi atribut `partialFingerprints` pada skema format SARIF?
   * A. Mengenkripsi payload laporan hasil scan agar tidak bisa dibaca oleh unauthorized user.
   * B. Menghasilkan tanda tangan hash berbasis konteks logika kode untuk melacak identitas temuan yang sama meskipun nomor baris bergeser akibat pengeditan file.
   * C. Menghitung penggunaan memori runner selama eksekusi scanner berlangsung.
   * D. Menyimpan checksum SHA256 dari commit author untuk melacak performa developer.

7. Perhatikan potongan aturan Semgrep berikut:
   ```yaml
   patterns:
     - pattern: $DB.Query($QUERY, ...)
     - pattern-not: $DB.Query("...", ...)
   ```
   Tujuan dari sintaks `pattern-not` di atas adalah:
   * A. Memastikan parameter `$QUERY` hanya menerima format string konstan tanpa injeksi variabel dinamis.
   * B. Memblokir seluruh query database bertipe string literal.
   * C. Menghilangkan *false positive* jika query database menggunakan string literal murni yang aman dari SQL Injection.
   * D. Menginstruksikan Semgrep agar memindai file konfigurasi non-Go.

8. Mengapa teknik *Sparse Checkout* atau *Path Filtering* sangat kritikal pada arsitektur monorepo berskala besar?
   * A. Mencegah developer lain melihat kode sensitif di branch yang sama.
   * B. Mengurangi latensi I/O disk dan waktu komputasi CI/CD dengan hanya memproses sub-pohon direktori yang terdampak oleh commit terkait.
   * C. Memaksa engine compiler untuk memproduksi artefak microservices secara independen.
   * D. Menjamin database schema terisolasi secara kriptografis.

9. Jika SARIF Ingestion Engine mendeteksi sebuah *Finding* baru pada PR, namun finding tersebut memiliki hash fingerprint yang identik dengan daftar *Accepted Technical Debt Baseline*, tindakan apa yang harus diambil oleh Quality Gate yang benar?
   * A. Menolak PR seketika (*fail-closed*) sampai seluruh hutang teknis dibersihkan.
   * B. Menghapus kode yang mengandung finding secara otomatis tanpa intervensi manusia.
   * C. Mengizinkan PR lolos (*suppress/pass*) untuk commit tersebut tanpa memicu *PR blocking*, sembari mencatat metriknya ke dashboard monitoring SecOps.
   * D. Mematikan fitur SAST pada branch repository tersebut.

10. Apa risiko keamanan utama jika step automated review di GitHub Actions dieksekusi dengan trigger event `pull_request_target` pada repositori bertipe *public fork*?
    * A. Pipeline akan selalu gagal mengeksekusi tes unit karena batasan kuota runner.
    * B. Kode dari pull request fork yang belum diverifikasi berpotensi mengeksekusi script berbahaya dengan akses ke token repositori induk (*pwn request*).
    * C. Format SARIF tidak akan terbaca oleh dashboard keamanan GitHub.
    * D. Git merge-base akan otomatis mengunci target branch ke status *read-only*.

---

#### Bagian 3: Skenario Kasus Produksi (Uraian Analitis)

11. **Skenario Kasus 1**:
    Tim Core Banking merilis pembaruan arsitektur pada middleware autentikasi. Setelah branch di-merge ke `main`, seluruh pipeline pada 80 Pull Request tim lain yang sedang terbuka tiba-tiba berstatus **FAILED** pada tahap SAST Check, padahal mereka tidak menyentuh middleware tersebut. 
    * Pertanyaan: Mengapa anomali ini dapat terjadi pada differential analysis, dan bagaimana solusi arsitektural untuk mengisolasi kegagalan agar tidak memblokir PR tim lain yang tidak terkait?

12. **Skenario Kasus 2**:
    Sebuah tim machine learning enterprise memasukkan model file berukuran 2 GB (`.bin` / `.onnx`) ke dalam pull request mereka. Runner SAST mendadak mengalami *Crash Loop* (Exit Code 137) dan membuat seluruh siklus review terhenti total.
    * Pertanyaan: Konfigurasi arsitektural apa saja yang harus dipasang pada level Git LFS, runner, dan scanner engine untuk memitigasi terulangnya masalah ini secara permanen?

13. **Skenario Kasus 3**:
    Hasil audit independen menunjukkan bahwa sebuah celah keamanan Zero-Day lolos ke production karena developer menambahkan anotasi bypass inline `// nosec` atau `# nosec` pada kode berbahaya mereka, sehingga scanner mengabaikan baris tersebut saat PR diuji.
    * Pertanyaan: Rancang mekanisme tata kelola (*governance policy*) dan arsitektur verifikasi otomatis untuk mencegah penyalahgunaan bypass komentar tanpa otorisasi formal dari tim SecOps!

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian 1: Basic
1. **B** - AST merepresentasikan struktur logika kode hierarkis sehingga scanner dapat memahami variabel, tipe data, dan scope alur eksekusi, bukan sekadar pencocokan string teks seperti RegEx.
2. **C** - SARIF diciptakan oleh konsorsium OASIS sebagai bahasa/format standar bersama agar semua tooling analisis statis menghasilkan format output terstruktur yang seragam.
3. **C** - `git merge-base` mencari *common ancestor* terakhir antara dua branch yang berbeda secara deterministik.
4. **B** - Personal Access Token yang bocor pada runner ephemeral dapat digunakan oleh penyerang untuk mengeksploitasi seluruh repositori enterprise. OIDC short-lived token adalah mitigasi yang benar.
5. **C** - Sink adalah lokasi fungsi akhir di mana data dieksekusi (contoh: pemanggilan database query, sistem eksekusi shell, atau deserializer data).

#### Bagian 2: Intermediate
6. **B** - Fingerprint berbasis struktur AST lokal memungkinkan identifikasi issue yang persisten meskipun nomor baris bergeser ke atas/bawah akibat penambahan teks lain.
7. **C** - `pattern-not` digunakan untuk mengecualikan string konstan statis yang tidak membawa risiko SQL Injection, sehingga menekan angka *false positive*.
8. **B** - *Sparse Checkout* dan *Path Filtering* membatasi unduhan dan evaluasi hanya pada pohon kode yang termutasi, memangkas konsumsi bandwidth dan durasi analisis.
9. **C** - Baseline governance memperbolehkan issue lama yang sudah terdokumentasi (*legacy debt*) agar tidak menghambat delivery, sembari tetap mencatat metriknya.
10. **B** - Event `pull_request_target` berjalan dalam konteks hak akses base repository induk, sehingga penyerang dari public fork dapat mengeksekusi payload malicious yang mencuri *repo secrets*.

#### Bagian 3: Solusi Skenario Kasus Produksi
11. **Panduan Solusi Skenario 1**:
    * *Penyebab*: Pipeline differential kemungkinan menghitung diff terhadap commit `HEAD` dari `origin/main` yang baru di-update. Perubahan pada middleware mengubah context invariant secara global pada base class.
    * *Solusi*: Runner harus mengunci evaluasi pada commit *snapshot target* saat PR dibuat atau menggunakan rebase check virtual. Pisahkan evaluasi rules ke dalam dua kategori: *Module-Boundary Rules* (hanya dievaluasi jika file modul berubah) dan *Local-Scope Rules*.
12. **Panduan Solusi Skenario 2**:
    * Konfigurasi `.scannerignore` untuk mengecualikan ekstensi binary besar secara ketat (`*.onnx`, `*.bin`, `*.weights`, `*.parquet`).
    * Pasang *pre-receive hook* atau GitHub Push Protection yang memblokir berkas berukuran di atas batasan tertentu (> 50 MB) agar tidak masuk ke Git tree.
    * Atur flag scanner: `semgrep --max-target-bytes=5MB` untuk melindungi runner dari kehabisan memori jika ada file besar yang lolos.
13. **Panduan Solusi Skenario 3**:
    * Implementasikan *Meta-Linter* atau *Policy Check (OPA)* yang memindai penambahan komentar bypass (`nosec`, `nolint`, `semgrep-ignore`) di dalam file pull request diff.
    * Jika ditemukan penambahan bypass tag, pipeline secara otomatis memicu kewajiban approval tambahan (*CODEOWNERS verification*) dari tim `SecOps-Architects` dan membatalkan auto-merge privilege hingga tag bypass tersebut di-sign off secara kriptografis.

---

### 16. Summary

Implementasi *automated code review* kelas enterprise adalah pilar utama dalam modern software engineering architecture yang menghubungkan produktivitas developer dengan kepatuhan sistem keamanan (*shifting left*). Dengan menerapkan analisis differensial berbasis AST, arsitektur pipeline terhindar dari pemindaian redundan yang membebani resource komputasi dan memperlambat throughput release. 

Standarisasi melalui format OASIS SARIF v2.1.0 memberikan fleksibilitas integrasi multi-scanner tingkat tinggi, menyatukan linter bahasa, SAST mendalam, penelusuran kebocoran kredensial, dan SCA dalam satu gerbang kendali kebijakan (*Quality Gate*) yang koheren. Melalui tata kelola aturan deklaratif yang presisi, mitigasi *false positive* berbasis baseline hashing, dan pengamanan lingkungan eksekusi pipeline berbasis Zero-Trust, organisasi mampu menegakkan standar rekayasa perangkat lunak yang tangguh, aman, dan dapat diskalakan hingga ke jutaan baris kode secara konsisten.