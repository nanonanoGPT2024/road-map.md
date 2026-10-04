# Kurikulum Code Review & System Architecture
## Kategori 06: Architecture and System Design
### Bab 04: Otomasi, Pengujian Statis, & Guardrails Rekayasa Perangkat Lunak

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** CR-ENG-04-01
* **Nama Modul:** Otomasi: Linting, SAST, & Pre-Review Pipelines
* **Sub-Judul:** Eliminasi Nitpicks dengan Linters, Formatters, Git Hooks, DangerJS, Semgrep, SonarQube, dan Automated Guardrails di CI/CD
* **Level:** Advanced / Professional Software Engineer & Engineering Lead
* **Prasyarat:**
  * Pemahaman mendalam tentang siklus hidup Git (Hooks, Plumbing vs Porcelain commands).
  * Pengalaman mengonfigurasi pipeline CI/CD (GitHub Actions, GitLab CI, dsb.).
  * Pemahaman fundamental konsep Abstract Syntax Tree (AST) dan kerentanan keamanan perangkat lunak (OWASP Top 10).
* **Estimasi Waktu Belajar:** 4 Jam (Teori, Konfigurasi Sistem, Hands-On Lab)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Mendiagnosis & Mengeliminasi "Reviewer Fatigue":** Mengidentifikasi dan memindahkan 100% verifikasi kosmetik (style, whitespace, import ordering) serta potensi syntax/logic error deterministik dari kapasitas kognitif manusia ke mesin.
2. **Merancang Shift-Left Automation Architecture:** Mengonfigurasi strategi bertingkat (*tiered checks*) mulai dari Local Pre-commit (Lefthook/Husky + lint-staged) hingga Cloud CI/CD gate.
3. **Mengimplementasikan AST-based Static Application Security Testing (SAST):** Menulis *custom rules* Semgrep untuk mendeteksi anti-pattern arsitektur dan celah keamanan sebelum PR diserahkan ke reviewer.
4. **Mengotomatisasi Konteks PR Menggunakan DangerJS:** Memprogram bot feedback yang secara otomatis memvalidasi deskripsi PR, membatasi ukuran changeset (*PR size limit*), mendeteksi hilangnya file migrasi atau unit test, dan mengaudit *breaking changes*.
5. **Menetapkan SonarQube Quality Gates yang Rigid:** Mengonfigurasi parameter *Zero New Technical Debt*, Cognitive Complexity threshold, serta integrasi status check wajib pada branch protection rules.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       [SIKLUS PERUBAHAN KODE (SHIFT-LEFT)]
                                       │
       ┌───────────────────────────────┴───────────────────────────────┐
       ▼                                                               ▼
[LOCAL ENVIRONMENT]                                            [CI/CD PIPELINE]
  │                                                              │
  ├─► IDE Integration (LSP, On-Save)                             ├─► Orchestration (GitHub Actions)
  │     └─► Formatting: Prettier, Biome                            │     ├─► Concurrency & Path Filtering
  │     └─► Fast Lint: ESLint, Ruff                                │     └─► Artifact Caching
  │                                                              │
  └─► Local Git Hooks (Lefthook / Husky)                         ├─► Pull Request Bot (DangerJS)
        └─► lint-staged (Diff-only parsing)                      │     ├─► Enforce PR Size & PR Description
        └─► Secret Detection (Gitleaks)                          │     ├─► Warn missing tests / changelog
        └─► Conventional Commits (commitlint)                    │
                                                                 ├─► SAST & Pattern Engine (Semgrep)
                                                                 │     ├─► Custom Org Rules (Anti-patterns)
                                                                 │     └─► OWASP / CWE Signatures
                                                                 │
                                                                 └─► Deep Analysis (SonarQube)
                                                                       ├─► Cognitive vs Cyclomatic Complexity
                                                                       ├─► Code Coverage & Duplication
                                                                       └─► Hard Quality Gate (Pass/Fail)
                                                                 │
                                                                 ▼
                                                  [MANUAL CODE REVIEW HUMAN-CENTRIC]
                                                    └─ Focus: System Design & Business Logic
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Salah satu kegagalan terbesar dalam kultur *engineering* adalah menghabiskan kapasitas kognitif insinyur senior untuk memberikan komentar seperti:
> *"Tolong tambahkan baris kosong di sini."*
> *"Variabel ini camelCase, bukan snake_case."*
> *"Method ini sebaiknya diberi logging."*
> *"Apakah input ini sudah disanitasi dari SQL Injection?"*

Fenomena ini dikenal sebagai **Bikeshedding (Law of Triviality)**: anggota tim cenderung memberikan proporsi perhatian yang tidak seimbang pada hal-hal sepele yang mudah dinilai, daripada arsitektur sistem, konkurensi, idempotensi, dan logika domain.

Ketika reviewer manusia dipaksa membaca 1.500 baris kode yang tercampur aduk antara *formatting*, perubahan dependensi, dan logika bisnis baru, kemampuan otak untuk memetakan *edge cases* menurun drastis (*reviewer cognitive fatigue*). 

Dengan mengimplementasikan **Automated Pre-Review Pipeline**:
1. **Zero Human Nitpicks:** Seluruh aspek stilistik, standardisasi penamaan, dan *code smells* deterministik diselesaikan oleh mesin.
2. **Reviewer Focus:** Reviewer hanya menganalisis hal-hal non-deterministik: *Apakah domain model ini merefleksikan bounded context yang benar? Apakah state transition ini aman dari race condition?*
3. **Turnaround Time (TAT) Turun Drastis:** Waktu tunggu PR turun dari hitungan hari ke hitungan jam karena bolak-balik komentar terkait formatting dieliminasi sepenuhnya.

---

## SEKSI 05 — APA ITU (WHAT)

Pre-Review Automation adalah ekosistem alat dan kebijakan terotomatisasi yang dijalankan dari workstation lokal hingga pipeline CI/CD untuk memastikan bahwa **tidak ada kode yang dapat dilihat atau di-review oleh manusia kecuali kode tersebut telah lolos dari serangkaian validasi otomatis deterministik**.

Komponen-komponen utamanya mencakup:
* **Linters & Formatters:** Parser berbasis Abstract Syntax Tree (AST) yang memeriksa kepatuhan sintaksis, gaya penulisan, dan potensi bug lokal tanpa menjalankan runtime (misal: Prettier, ESLint, Biome, Ruff, Golangci-lint).
* **Git Hooks:** Skrip siklus hidup Git yang mencegat eksekusi developer pada fase *pre-commit* atau *pre-push* untuk memblokir kode yang melanggar aturan sebelum masuk ke *remote repository*.
* **PR Meta-Automation (DangerJS):** Framework otomatisasi berbasis Node.js yang membaca metadata PR (diff, metrics, label, author, title) dan menyematkan komentar langsung ke PR untuk menegakkan tata kelola (*governance*).
* **Lightweight SAST (Semgrep):** Static Application Security Testing modern yang menggunakan pencocokan pola sintaksis deklaratif langsung pada AST, memungkinkan pembuatan aturan keamanan custom dalam hitungan menit.
* **Continuous Code Quality & Security Platform (SonarQube):** Platform analisis mendalam yang mengukur *cognitive complexity*, *technical debt ratio*, *code duplication*, serta cakupan pengujian melalui *Quality Gates*.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

Pipeline otomatis bekerja dalam **arsitektur pertahanan berlapis (Layered Defense Strategy)**. Semakin ke kiri (Shift-Left), feedback harus semakin cepat. Semakin ke kanan (Cloud CI), pengujian berjalan semakin komprehensif.

```
+-------------------------------------------------------------------------------+
| LAYER 1: IDE / Developer Workstation                                          |
| Trigger: On File Save / Keystroke                                             |
| Tools: LSP, Formatters (Prettier/Biome), Language Linters                    |
| Execution Speed: < 100ms                                                      |
+-------------------------------------------------------------------------------+
                                      │
                                      ▼ (git commit)
+-------------------------------------------------------------------------------+
| LAYER 2: Local Pre-Commit Hooks                                               |
| Trigger: git commit (intercepted by Lefthook/Husky)                           |
| Tools: lint-staged (AST parsing ONLY on modified files), commitlint, Gitleaks |
| Execution Speed: < 2-5 seconds                                                |
+-------------------------------------------------------------------------------+
                                      │
                                      ▼ (git push / Open PR)
+-------------------------------------------------------------------------------+
| LAYER 3: Pull Request Pre-Flight & Metadata Guardrails                        |
| Trigger: GitHub Actions (pull_request event)                                  |
| Tools: DangerJS, PR Labeler, Size Validator                                   |
| Execution Speed: < 30 seconds                                                 |
+-------------------------------------------------------------------------------+
                                      │
                                      ▼ (Parallel CI Execution)
+-------------------------------------------------------------------------------+
| LAYER 4: Deep Analysis & Security Verification                                |
| Trigger: Automated CI Matrix                                                  |
| Tools: Semgrep (SAST), SonarQube Scanner (Quality Gate), Unit/Contract Tests   |
| Execution Speed: 2 - 8 minutes                                                |
+-------------------------------------------------------------------------------+
                                      │
                         [STATUS CHECKS PASSED?]
                                      │
                    ┌─────────────────┴─────────────────┐
                    │ YES                               │ NO
                    ▼                                   ▼
      [Assign Human Reviewers]                  [Block Merge]
  - Focus on Architecture & Domain         - Automated comment with stack trace
  - Zero syntax/style discussion           - Developer fixes issues locally
```

### 1. Mekanisme Parser AST
Linter dan SAST tidak menggunakan Regex sederhana (*kecuali untuk pola trivial*). Linter mengonversi source code teks menjadi struktur hierarki pohon yang merepresentasikan struktur program secara gramatikal (Abstract Syntax Tree). 

Misalnya ekspresi:
```javascript
const user = eval(req.body.input);
```
Dikonversi menjadi AST Node: `VariableDeclaration` -> `VariableDeclarator` -> `CallExpression` (callee: `Identifier(eval)`, arguments: `[MemberExpression]`). SAST rule mengidentifikasi simpul `CallExpression` di mana `callee.name === 'eval'`, menandainya sebagai kerentanan kritis, terlepas dari spasi atau format penulisan kode.

### 2. Differensiasi Analisis Git (lint-staged)
Menjalankan linter di seluruh repositori (*full project scan*) pada setiap *commit* memakan waktu menit hingga jam pada monorepo. Git hooks modern mengekstrak staging index:
```bash
git diff --cached --name-only --diff-filter=ACMR
```
Hanya file yang berstatus Added (A), Copied (C), Modified (M), atau Renamed (R) yang dikirim ke linter. Hal ini menjaga durasi pre-commit di bawah 3 detik.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

Berikut adalah alur data dan eksekusi rinci dari interaksi antara Developer, Git Hook, CI Runner, DangerJS, Semgrep, SonarQube, dan GitHub Branch Protection Rules:

```
+--------------------------------------------------------------------------------------------------------------------+
|                                      END-TO-END AUTOMATED GUARDRAIL PIPELINE                                       |
+--------------------------------------------------------------------------------------------------------------------+

  DEVELOPER                 LOCAL HOOKS (Lefthook)         REMOTE GIT REPO               CI RUNNER (GitHub Actions)
      │                                │                          │                                  │
      │ 1. git commit -m "feat: pay"   │                          │                                  │
      ├───────────────────────────────►│                          │                                  │
      │                                │ 2. Run Gitleaks (diff)   │                                  │
      │                                │ 3. Run lint-staged       │                                  │
      │                                │    (Prettier/ESLint)     │                                  │
      │                                │ 4. Run commitlint        │                                  │
      │                                │                          │                                  │
      │    [Success: Local Pass]       │                          │                                  │
      │◄───────────────────────────────┤                          │                                  │
      │                                │                          │                                  │
      │ 5. git push origin feat/pay    │                          │                                  │
      ├──────────────────────────────────────────────────────────►│                                  │
      │                                                           │                                  │
      │ 6. Open Pull Request                                      │                                  │
      ├──────────────────────────────────────────────────────────►│ 7. Trigger Webhook               │
      │                                                           ├─────────────────────────────────►│
      │                                                           │                                  │
      │                                                           │          [PARALLEL EXECUTION]    │
      │                                                           │   ┌──────────────────────────────┴──────────┐
      │                                                           │   │                                         │
      │                                                           │   ▼ JOB A: DangerJS                         ▼ JOB B: Security & Quality
      │                                                           │   - PR Size Metric Check                    - Semgrep CLI (AST Rules)
      │                                                           │   - Test Changes Detection                  - SonarQube Scanner
      │                                                           │   - Semantic PR Name Check                  - Unit & Integration Test
      │                                                           │   │                                         │
      │                                                           │   └──────────────┬──────────────────────────┘
      │                                                           │                  │
      │                                                           │                  ▼
      │                                                           │   [EVALUATION: Aggregated Matrix]
      │                                                           │                  │
      │                                                           │ 8. Update PR     │
      │                                                           │    Check Run     │
      │                                                           │◄─────────────────┤
      │                                                           │                  │
      │                                 9. Post Bot Feedback      │                  │
      │                                    (Inline Warnings)      │                  │
      │◄──────────────────────────────────────────────────────────┼──────────────────┘
      │
      ▼
+────────────────────────────────────────────────────────────────────────────────────────────────────────────────----+
| BRANCH PROTECTION RULE EVALUATION                                                                                  |
+────────────────────────────────────────────────────────────────────────────────────────────────────────────────----+
|                                                                                                                    |
|   Checks Required:                                                                                                 |
|   [✓] danger/pr-metadata .............................................................. PASSED                     |
|   [✓] security/semgrep-sast ........................................................... PASSED                     |
|   [✓] quality/sonarqube-gate .......................................................... PASSED                     |
|   [✓] continuous-integration/tests ................................................... PASSED                     |
|                                                                                                                    |
|   [STATUS: ALL AUTOMATED GATES CLEAR] ──► Human Reviewers Auto-Assigned (CODEOWNERS)                               |
+────────────────────────────────────────────────────────────────────────────────────────────────────────────────----+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah implementasi minimal konfigurasi Git Hook menggunakan **Lefthook** (alternatif modern yang jauh lebih cepat dibandingkan Husky karena berbasis Go dengan eksekusi paralel native) yang dipadukan dengan pembersihan otomatis.

### `lefthook.yml` (Konfigurasi Root)
```yaml
# File: lefthook.yml
pre-commit:
  parallel: true
  commands:
    gitleaks:
      tags: security
      run: gitleaks protect --staged --verbose --redact
    lint-and-format:
      tags: style
      glob: "*.{js,ts,jsx,tsx,json,md}"
      run: npx @biomejs/biome check --write --no-errors-on-unmatched --staged {staged_files}
      stage_fixed: true

commit-msg:
  commands:
    "commitlint":
      run: npx --no -- commitlint --edit {1}
```

### Apa yang Terjadi di Balik Layar?
1. Saat pengembang menjalankan `git commit`:
   * Job `gitleaks` memindai memori *staging area* untuk mencari token AWS, private key, atau signature token berisiko tinggi. Jika ada, commit digagalkan seketika.
   * Secara paralel (`parallel: true`), `biome` memeriksa file yang berubah, memformatnya sesuai aturan organisasi, dan memasukkan kembali file yang diformat ke *staging area* (`stage_fixed: true`).
2. Setelah hook pre-commit sukses, hook `commit-msg` memicu `commitlint` untuk memvalidasi apakah pesan commit memenuhi spesifikasi Conventional Commits (misal: `feat: add payment gateway webhook handler`).

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Di bawah ini adalah konfigurasi pipeline level enterprise yang mengintegrasikan DangerJS, Custom Semgrep Rules, SonarQube, dan GitHub Actions Pipeline yang siap pakai.

### 1. Custom SAST Rule: `semgrep-custom-rules.yml`
Mendeteksi anti-pattern arsitektural: Developer dilarang memanggil database query langsung dari Controller layer. Harus lewat Service/Repository layer.

```yaml
# File: .semgrep/architecture-rules.yml
rules:
  - id: controller-direct-db-access
    languages: [typescript, javascript]
    message: >-
      PELANGGARAN ARSITEKTUR: Jangan mengakses Database Client secara langsung di dalam Controller. 
      Rujuk ke Repository Pattern atau Service Layer untuk mematuhi Clean Architecture.
    severity: ERROR
    metadata:
      category: architecture
      cwe: "CWE-1068"
    patterns:
      - pattern-inside: |
          class $CONTROLLER extends BaseController { ... }
      - pattern-either:
          - pattern: prisma.$MODEL.$METHOD(...)
          - pattern: this.db.$METHOD(...)
          - pattern: getRepository($ENTITY)

  - id: ban-raw-sql-concatenation
    languages: [typescript, javascript]
    message: >-
      POTENSI SQL INJECTION: Ditemukan konkatenasi string dinamis pada query mentah. 
      Gunakan parameterized query (Template Literals yang disanitasi).
    severity: ERROR
    metadata:
      category: security
      cwe: "CWE-89"
      owasp: "A03:2021-Injection"
    patterns:
      - pattern-either:
          - pattern: $DB.query(`... ${$VAR} ...`)
          - pattern: $DB.query($STR + $VAR)
```

### 2. Dangerfile Enterprise: `dangerfile.ts`
Menegakkan guardrails operasional, batasan ukuran PR, dan kepatuhan pengujian.

```typescript
// File: dangerfile.ts
import { danger, warn, fail, message } from "danger";

export default async function () {
  const pr = danger.github.pr;
  const modifiedFiles = danger.git.modified_files;
  const createdFiles = danger.git.created_files;
  const allChangedFiles = [...modifiedFiles, ...createdFiles];

  // 1. Guardrail Ukuran PR (PR Size Guardrail)
  const MAX_CHANGES_THRESHOLD = 500;
  const totalChanges = pr.additions + pr.deletions;
  
  if (totalChanges > MAX_CHANGES_THRESHOLD) {
    warn(
      `⚠️ PR ini memuat ${totalChanges} baris perubahan (Limit: ${MAX_CHANGES_THRESHOLD}). ` +
      `Pertimbangkan untuk memecah PR ini menjadi bagian-bagian kecil (Micro-PRs) ` +
      `untuk mempertahankan ketelitian reviewer dan meminimalkan cognitive overload.`
    );
  }

  // 2. Enforce PR Body Template Compliance
  if (!pr.body || pr.body.length < 50) {
    fail("❌ Deskripsi PR terlalu pendek atau kosong. Mohon isi penjelasan konteks, Root Cause Analysis, dan langkah testing.");
  }

  // 3. Verifikasi Keberadaan Unit Testing
  const hasAppChanges = allChangedFiles.some((path) => path.startsWith("src/"));
  const hasTestChanges = allChangedFiles.some((path) => 
    path.includes(".test.") || path.includes(".spec.") || path.startsWith("tests/")
  );

  if (hasAppChanges && !hasTestChanges) {
    warn("⚠️ Ada modifikasi fungsional di `src/`, namun tidak ada penambahan atau pembaruan file tes (`*.spec.ts` / `*.test.ts`).");
  }

  // 4. Critical File Alteration Watchdog (Database Migrations & Lockfiles)
  const touchesMigrations = allChangedFiles.some((path) => path.includes("prisma/migrations/"));
  const touchesSchema = allChangedFiles.some((path) => path.endsWith("schema.prisma"));

  if (touchesSchema && !touchesMigrations) {
    fail("❌ Anda mengubah `schema.prisma` tetapi tidak menyertakan file migrasi di folder `prisma/migrations/`. Jalankan `prisma migrate dev`.");
  }

  // 5. Dependency Manifest vs Lockfile Integrity
  const touchesPackageJson = allChangedFiles.includes("package.json");
  const touchesLockfile = allChangedFiles.includes("pnpm-lock.yaml");

  if (touchesPackageJson && !touchesLockfile) {
    fail("❌ `package.json` diubah tanpa menyertakan pembaruan pada `pnpm-lock.yaml`.");
  }

  message(`Analisis otomatis selesai. ${allChangedFiles.length} file dianalisis.`);
}
```

### 3. Orchestration CI Pipeline: `.github/workflows/pre-review-pipeline.yml`

```yaml
# File: .github/workflows/pre-review-pipeline.yml
name: Pre-Review Engineering Guardrails

on:
  pull_request:
    types: [opened, synchronize, reopened]

concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true

jobs:
  metadata-guardrails:
    name: Metadata Guardrails (DangerJS)
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Setup Node.js Runtime
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: "npm"

      - name: Install Dependencies
        run: npm ci

      - name: Execute DangerJS
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: npx danger ci --dangerfile dangerfile.ts

  semgrep-sast:
    name: Security & Architecture (Semgrep)
    runs-on: ubuntu-latest
    container:
      image: returntocorp/semgrep
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Run Semgrep Custom & Community Rules
        run: >-
          semgrep scan 
          --config .semgrep/architecture-rules.yml 
          --config "p/owasp-top-ten" 
          --error 
          --metrics=off

  sonarqube-analysis:
    name: Deep Inspection (SonarQube)
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository (Full History for Blame/Analysis)
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Node.js Runtime
        uses: actions/setup-node@v4
        with:
          node-version: 20

      - name: Install & Run Unit Tests with Coverage
        run: |
          npm ci
          npm run test:coverage

      - name: SonarQube Scan
        uses: sonarsource/sonarqube-scan-action@v2
        env:
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
          SONAR_HOST_URL: ${{ secrets.SONAR_HOST_URL }}
        with:
          args: >
            -Dsonar.projectKey=my-org_backend-service
            -Dsonar.sources=src
            -Dsonar.tests=src,tests
            -Dsonar.test.inclusions=**/*.test.ts,**/*.spec.ts
            -Dsonar.javascript.lcov.reportPaths=coverage/lcov.info
            -Dsonar.qualitygate.wait=true
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Aspek | Local Git Hooks (Lefthook/Husky) | Cloud CI Pipeline (GitHub Actions) |
| :--- | :--- | :--- |
| **Execution Latency** | **Sangat Cepat (< 3 detik).** Feedback instan saat developer mengetik perintah commit. | **Sedang hingga Lambat (1–5 menit).** Menunggu provisioning runner, checkout, download cache. |
| **Bypassability (Integritas)** | **Mudah di-bypass.** Developer dapat menjalankan `git commit --no-verify` kapan saja. | **Mutlak/Non-bypassable.** Dikunci secara kriptografis oleh server branch protection rules. |
| **Resource Footprint** | Mengonsumsi resource lokal mesin pengembang (RAM/CPU throttling pada laptop spek rendah). | Resource terisolasi di cloud runners; biaya server CI bertambah seiring frekuensi PR. |
| **Context Availability** | Sempit. Hanya melihat staged diff, sulit membaca konteks metadata PR (misal: reviewer, labels, PR body). | Sangat Luas. Akses penuh ke GitHub API, PR diff global, artifact build, historical analysis. |

### DangerJS vs Static Check Biasa
DangerJS menyediakan fleksibilitas berbasis Javascript API untuk memeriksa **metadata PR**, bukan sekadar teks file. Namun, DangerJS membutuhkan token API GitHub dengan permission membaca/menulis komentar PR (`pull-requests: write`). Kerentanannya: eksekusi dari untrusted fork PR berpotensi membocorkan context token jika tidak diisolasi menggunakan *workflow run limits*.

### Semgrep vs SonarQube
* **Semgrep:** Sangat cepat, berfokus pada analisis *AST pattern-matching* instan dan mudah dikustomisasi (*Rule as Code*). Sangat baik untuk Shift-Left blocking di pipeline pull-request.
* **SonarQube:** Berat, membutuhkan runtime build penuh dan parsing coverage file, tetapi unggul dalam *holistic cross-file taint analysis*, kalkulasi cognitive complexity, dan pengukuran akumulasi technical debt jangka panjang.

---

## SEKSI 11 — BEST PRACTICES

1. **Jadikan Pipeline Deterministik:** Pipeline linter dan SAST tidak boleh memiliki ketergantungan jaringan yang tidak terkunci (*unlocked external deps*). Gunakan *fixed container versions* atau *lockfiles* yang ketat.
2. **Pisahkan Job Cepat dan Job Berat (Parallel Job Splitting):**
   * Tahap 1: Fast Linters, DangerJS, Formatting (< 60s)
   * Tahap 2: SAST (Semgrep) (< 2 menit)
   * Tahap 3: Unit Tests + SonarQube Scan (< 5-8 menit)
   Jika Tahap 1 gagal, langsung hentikan eksekusi sebelum menjalankan container pengujian yang memakan waktu dan biaya.
3. **Terapkan 'Zero New Technical Debt' pada Quality Gate:**
   Jangan menuntut repositori legacy memiliki coverage 100% secara retroaktif. Alih-alih demikian, setel parameter SonarQube: **New Code Period**. Kode baru yang ditambahkan di PR wajib memiliki 0 blocker issue, 0 security hotspot, dan coverage $\ge 85\%$.
4. **Jadikan Error Messages Bersifat Solutif (Actionable Feedback):**
   Pesan error dari custom rules harus menginstruksikan perbaikan secara eksplisit:
   * *Buruk:* `Error: Direct database connection not allowed.`
   * *Baik:* `Error: Terdeteksi inisialisasi DbContext langsung di UserControl.ts:42. Silakan inject UserRepository via constructor injection.`
5. **Caching Dependencies Secara Agresif:** Simpan direktori `node_modules`, `~/.cache/semgrep`, dan sonar cache antar runner run untuk menghemat waktu download sebesar 60-80%.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Menjalankan Linter Global di Pre-Commit Hook:**
   Menjalankan `eslint .` pada hook commit lokal di repositori yang memiliki 10.000 file. Hasilnya: commit memakan waktu 40 detik. Developer akan frustrasi dan membiasakan diri menggunakan `git commit -n` (`--no-verify`), merusak seluruh filosofi guardrail lokal.
2. **False-Positive Fatigue Tanpa Mekanisme Escape Hatch:**
   Membuat SAST rule yang terlalu sensitif sehingga memunculkan banyak peringatan keliru (*false positive*). Jika tidak ada mekanisme *suppression* terverifikasi (misal: comment inline `// nosemgrep: rule-id` disertai alasan mandatory), developer akan mulai mengabaikan seluruh hasil analisis.
3. **Mencampuradukkan Formatting dan Logic Review dalam Satu PR:**
   Developer menjalankan formatter global pada file legacy yang sedang diperbaiki logika bisnisnya. Hasilnya: diff membengkak menjadi 2.000 baris padahal logic fix hanya 3 baris. Pipeline harus membatasi PR seperti ini, atau tim harus mewajibkan "Formatting PR" terpisah secara penuh dari "Feature/Fix PR".
4. **Mengabaikan Path Filtering di CI:**
   Memicu seluruh pipeline SonarQube dan Integration Test saat developer hanya mengubah file dokumentasi (`README.md` atau `docs/*`). Konfigurasikan `paths-ignore` di GitHub Actions.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario:
Anda ditunjuk sebagai Technical Architect di sebuah fintech. Tim sering melewatkan review keamanan di PR, di mana developer sering menggunakan `console.log` berisi data sensitif di production, dan melupakan testing pada modul core payment.

### Tugas Anda:
1. **Latihan 1 (Lefthook Setup):**
   Buat file `lefthook.yml` yang:
   * Memvalidasi file staged `.ts` menggunakan linter.
   * Memeriksa apakah ada kata `console.log` yang tertinggal di staging area, dan batalkan commit jika ditemukan.
2. **Latihan 2 (DangerJS Scripting):**
   Tulis file `dangerfile.ts` yang mendeteksi perubahan pada file di dalam folder `src/payments/`. Jika ada perubahan pada folder tersebut, DangerJS harus mewajibkan:
   * Minimal 2 orang reviewer dari tim `payment-core` (tag tim di pesan comment).
   * File `src/payments/audit.log.ts` ikut disentuh/dimodifikasi.
3. **Latihan 3 (Custom Semgrep Rule):**
   Tulis file Semgrep YAML yang memblokir penulisan token otentikasi hardcoded: setiap assignment string literal yang cocok dengan format JWT (`ey...`) ke variabel bernama apa pun harus di-flag sebagai Severity: ERROR.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Apa perbedaan mendasar antara Abstract Syntax Tree (AST) scanning dan Regex-based scanning pada tools SAST?**
   * A. AST scanning hanya bekerja pada file JSON, sedangkan Regex bekerja pada binary.
   * B. AST scanning memahami konteks gramatikal kode (scope variabel, tipe node, dependensi sintaksis) terlepas dari spasi atau formatting, sementara Regex hanya mencocokkan pola string mentah yang rentan terhadap false-positive.
   * C. Regex scanning jauh lebih lambat tetapi mampu mendeteksi taint-flow secara inter-procedural.
   * D. AST scanning mengeksekusi kode secara live (dynamic runtime), sedangkan Regex mengeksekusi kode saat compile-time.

2. **Mengapa eksekusi linting lokal sebaiknya dikonfigurasi melalui `lint-staged` daripada mengeksekusi linter global pada pre-commit hook?**
   * A. Karena lint-staged membatasi eksekusi linter hanya pada file yang diindeks oleh staging Git, menjaga durasi eksekusi hook tetap dalam hitungan detik.
   * B. Karena lint-staged secara otomatis mengunggah perubahan ke remote server.
   * C. Karena linter global tidak mendukung bahasa TypeScript.
   * D. Karena Git melarang eksekusi proses yang memakan memori lebih dari 50MB di local hook.

3. **Kapan DangerJS dieksekusi dalam siklus hidup software delivery?**
   * A. Di komputer developer sesaat sebelum perintah `git push` dijalankan.
   * B. Di lingkungan runtime server produksi untuk mengaudit crash log.
   * C. Di pipeline CI/CD saat event Pull Request dipicu, untuk mengevaluasi konteks metadata PR terhadap standar organisasi.
   * D. Di dalam database engine saat proses migrasi data berjalan.

4. **Metrik apa yang dievaluasi oleh SonarQube Cognitive Complexity yang membedakannya dari Cyclomatic Complexity konvensional?**
   * A. Jumlah baris murni tanpa komentar (*Lines of Code excluding comments*).
   * B. Kompleksitas visual berdasarkan berapa banyak indentasi dan pemutusan alur linear yang secara nyata meningkatkan beban kognitif manusia dalam memahami fungsi tersebut.
   * C. Jumlah dependensi third-party yang diimpor oleh modul.
   * D. Kecepatan eksekusi CPU saat fungsi tersebut dijalankan pada benchmark test.

5. **Apa risiko arsitektural jika sebuah organisasi hanya mengandalkan pre-commit hook lokal tanpa automated guardrails di CI server?**
   * A. Repositori akan kehabisan ruang disk karena file hook lokal terlalu besar.
   * B. Branch protection rules akan menolak merge secara otomatis.
   * C. Standar rekayasa perangkat lunak tidak dapat dijamin integritasnya, karena local hooks dapat dilewati secara sepihak oleh pengembang menggunakan argumen `--no-verify`.
   * D. DangerJS tidak bisa mengirim webhook ke Slack.

---

### Kunci Jawaban Self-Assessment:
* **1: B** — AST mengurai representasi gramatikal bahasa pemrograman, sehingga perubahan kosmetik (seperti baris baru atau spasi) tidak mengacaukan deteksi pola keamanan atau logic bug.
* **2: A** — Memproses seluruh repositori saat local commit tidak *scalable*. `lint-staged` membatasi cakupan hanya pada file yang sedang di-commit saat itu.
* **3: C** — DangerJS didesain untuk berjalan di CI runner saat PR dibuka atau diperbarui, memungkinkannya menginspeksi diff, author, PR description, labels, dan memberi komentar via bot.
* **4: B** — Berbeda dengan Cyclomatic Complexity yang sekadar menghitung jumlah percabangan matematis ($B = E - N + 2P$), Cognitive Complexity memberikan bobot lebih berat pada percabangan bersarang (*nested structures*) yang membingungkan alur baca developer.
* **5: C** — Local hook sepenuhnya berada di bawah kendali developer. Integritas sistem hanya bisa ditegakkan secara absolut melalui server-side enforcement (Branch Protection di CI).

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Dokumentasi Resmi & Whitepapers:**
  * *Semgrep Documentation & Rule Syntax Guide:* https://semgrep.dev/docs/
  * *DangerJS Official Handbook:* https://danger.systems/js/
  * *SonarQube Cognitive Complexity Whitepaper (G. Ann Campbell):* https://www.sonarsource.com/docs/CognitiveComplexity.pdf
  * *Lefthook Fast Git Hooks Manager:* https://github.com/evilmartians/lefthook
* **Buku Referensi Rekayasa Perangkat Lunak:**
  * Titus Winters, Tom Manshreck, Hyrum Wright (2020). *Software Engineering at Google: Lessons Learned from Programming Over Time*. O'Reilly Media. (Khusus Bab: "Static Analysis" dan "Code Review").
  * Martin Fowler (2018). *Refactoring: Improving the Design of Existing Code (2nd Edition)*. Addison-Wesley Professional.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **Shift-Left Philosophy:** Deteksi dini adalah strategi paling hemat biaya dalam rekayasa perangkat lunak. Masalah yang tertangkap di level IDE atau Pre-Commit berharga murah; masalah yang tertangkap saat Manual Review membuang waktu senior engineer; masalah yang lolos ke Production berharga sangat mahal.
2. **Peran Mesin vs Manusia:**
   * **Mesin (Linters, DangerJS, Semgrep, SonarQube):** Memvalidasi formatting, pola sintaksis, celah keamanan deterministik, cakupan test, konvensi penamaan commit, dan metrik ukuran PR.
   * **Manusia (Code Reviewers):** Menganalisis *architectural fitness*, keselarasan logika bisnis (*domain correctness*), mitigasi race condition tingkat tinggi, abstraksi data, dan maintainability jangka panjang.
3. **Pilar Guardrails Otomatis:**
   * *Layer 1 (Local):* Kecepatan feedback instan menggunakan Lefthook + lint-staged.
   * *Layer 2 (PR Meta):* Tata kelola PR, batas baris kode, dan audit integrasi menggunakan DangerJS.
   * *Layer 3 (Deep Analysis):* AST-based SAST menggunakan Semgrep dan verifikasi Quality Gate mutlak menggunakan SonarQube di lingkungan CI/CD.
4. **Zero Tolerance for Nitpicks:** Melalui otomatisasi pipeline yang rigid, tim engineering dapat memberantas kultur debat kusir kosmetik dan beralih ke diskusi arsitektur bernilai tinggi.

---

## SEKSI 17 — GLOSARIUM

* **Abstract Syntax Tree (AST):** Struktur data pohon hierarkis yang merepresentasikan struktur sintaksis dari kode sumber yang diurai oleh parser compiler/linter.
* **Bikeshedding:** Kecenderungan manusia untuk menghabiskan waktu memperdebatkan hal-hal sepele yang tidak penting (seperti style coding) sambil mengabaikan isu-isu arsitektural yang rumit dan mendasar.
* **Cognitive Complexity:** Metrik pengukuran seberapa sulit suatu blok alur kode untuk dipahami oleh nalar manusia, berbeda dengan Cyclomatic Complexity yang mengukur testabilitas matematis.
* **Conventional Commits:** Standar penulisan pesan commit terstruktur (`type(scope): subject`) yang memudahkan pembuatan changelog dan versioning otomatis.
* **Quality Gate:** Kumpulan ambang batas kondisi (threshold) yang harus dipenuhi oleh sebuah build/PR sebelum kode diizinkan untuk di-merge ke branch utama (misal: coverage $\ge 80\%$, zero blocker bugs).
* **Shift-Left:** Praktik memindahkan langkah verifikasi, pengujian, dan analisis keamanan sedini mungkin ke fase awal siklus pengembangan perangkat lunak.
* **Static Application Security Testing (SAST):** Metodologi analisis keamanan white-box yang memeriksa kode sumber aplikasi dari celah kerentanan tanpa menjalankan program secara aktual.
* **Taint Analysis:** Teknik analisis aliran program untuk memeriksa apakah input data dari pengguna yang tidak terpercaya (*tainted source*) dapat mengalir ke fungsi eksekusi kritis (*sink*) tanpa sanitasi yang memadai.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Pedoman Fasilitasi:**
  * Saat membawakan modul ini, jangan biarkan peserta terjebak dalam perdebatan "alat mana yang terbaik" (misal: Husky vs Lefthook, atau ESLint vs Biome). Fokuskan diskusi pada **arsitektur pipeline** dan **boundary pemisahan tugas**.
  * Demonstrasikan secara live di layar: Lakukan commit yang memuat credential AWS palsu atau string SQL injection. Tunjukkan bagaimana commit tersebut diblokir seketika di workstation lokal dan di CI runner.
* **Titik Kritis Pemahaman (Common Aha! Moments):**
  * Peserta biasanya terkejut mengetahui bahwa Semgrep dapat menulis custom rule untuk arsitektur internal mereka (misal: melarang pemanggilan package X dari modul Y) hanya dengan 10 baris YAML tanpa perlu memahami compiler internal yang rumit.
* **Mitigasi Masalah Teknis Saat Sesi Lab:**
  * Pastikan Docker runtime sudah terinstal di mesin peserta jika mereka ingin menjalankan Semgrep CLI atau SonarQube secara lokal.
  * Berikan token GitHub sementara dengan hak akses terbatas untuk pengujian DangerJS di repository sandbox.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 2.0.0 (Maret 2025):**
  * Migrasi rekomendasi Git Hooks dari Husky klasik ke Lefthook untuk eksekusi paralel performa tinggi.
  * Penambahan materi penulisan Custom AST Rules menggunakan Semgrep YAML engine.
  * Pembaruan script DangerJS ke versi modern berbasis TypeScript.
  * Rekonseptualisasi metrik dari Cyclomatic Complexity ke Cognitive Complexity sesuai standar SonarSource modern.
* **Versi 1.0.0 (Januari 2024):**
  * Rilis modul inisial: Konfigurasi dasar ESLint, Prettier, Husky, dan GitHub Actions workflow.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:**
  * `CR-ENG-03-03`: Metodologi Review Kode Skala Besar (Micro-PR vs Stacked PRs vs Trunk-Based Development)
* **Modul Saat Ini:**
  * `CR-ENG-04-01`: Otomasi: Linting, SAST, & Pre-Review Pipelines
* **Modul Berikutnya:**
  * `CR-ENG-04-02`: Dynamic Analysis, Mutation Testing, & Contract Verification di Review Pipeline
* **Repositori Lab Hands-On:**
  * `github.com/enterprise-curriculum/cr-automated-guardrails-lab` *(Internal Sandboxed Repository)*