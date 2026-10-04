## SEKSI 01 — IDENTITAS MODUL

* **Modul ID:** `GGB-01-10`
* **Nama Kurikulum:** Git & GitHub Core Foundations for Professional Software Engineers
* **Kategori:** `01-Core-Foundations`
* **Bab:** 10 — Otomasi Dasar CI/CD Menggunakan GitHub Actions
* **Modul:** 01 — Pipeline CI Fundamental: Workflows, Jobs, Steps, dan Runners
* **Prasyarat:**
  * Pemahaman mendalam tentang branching Git (`git checkout`, `git switch`, `git merge`).
  * Pemahaman siklus GitHub Pull Request dan Branch Protection Rules (Bab 09).
  * Penguasaan dasar format data YAML (syntax, identasi, list, mapping).
  * Pemahaman eksekusi command line interface (CLI) Linux/POSIX.
* **Target Tingkat Kemahiran:** Beginner to Intermediate
* **Estimasi Waktu Penyelesaian:** 120 Menit (Teori: 45 Menit, Hands-on Lab: 75 Menit)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis Paradigma CI/CD (C4 - Analysis):** Membedakan batasan tanggung jawab antara *Continuous Integration* (CI) dan *Continuous Delivery/Deployment* (CD) dalam siklus hidup pengembangan perangkat lunak modern.
2. **Membangun Workflow YAML GitHub Actions (C3 - Application):** Mengonfigurasi file workflow sintaksis `.github/workflows/*.yml` secara presisi tanpa kesalahan identasi atau parsing struktur data.
3. **Mengonfigurasi Event Triggers (C3 - Application):** Mengatur kondisi pemicu pipeline otomatis secara spesifik berdasarkan kejadian Git (`push`, `pull_request`, penargetan branch spesifik, path filtering).
4. **Mengorkestrasikan Eksekusi Jobs dan Steps (C4 - Analysis):** Merancang tahapan eksekusi task berurutan maupun paralel, menggunakan runner virtual machine GitHub-hosted, community actions (`uses:`), dan shell scripts (`run:`).
5. **Mengintegrasikan Branch Protection dengan Automated Status Checks (C5 - Evaluation):** Mengunci branch utama (`main`) agar mewajibkan kelulusan pengujian CI sebelum operasi merge diizinkan.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       +----------------------------------+
                       |          GitHub Events           |
                       |  (push, pull_request, schedule)  |
                       +-----------------+----------------+
                                         |
                                         v Triggers
                       +-----------------+----------------+
                       |             Workflow             |
                       | (.github/workflows/*.yml file)   |
                       +-----------------+----------------+
                                         |
                       +-----------------+----------------+
                       |               Jobs               |
                       |  (Parallel by default, depends)  |
                       +-----------------+----------------+
                                         |
                                         v Runs on
                       +-----------------+----------------+
                       |        Runner Environment        |
                       | (ubuntu-latest, windows, macos)  |
                       +-----------------+----------------+
                                         |
                         Executes an ordered sequence of
                                         |
                                         v
                       +-----------------+----------------+
                       |              Steps               |
                       +-----------------+----------------+
                                         |
                   +---------------------+---------------------+
                   |                                           |
                   v                                           v
      +------------------------+                  +------------------------+
      |      Action Task       |                  |      Shell Command     |
      | (uses: actions/setup*) |                  |   (run: npm test/lint) |
      +------------------------+                  +------------------------+
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Sebelum era otomasi CI/CD, proses verifikasi integritas kode perangkat lunak bertumpu pada disiplin manual masing-masing pengembang. Paradigma manual ini menimbulkan sejumlah kegagalan sistemik:

1. **Sindrom *"Works on My Machine"*:** Pengembang memverifikasi kode di lingkungan lokal yang memiliki variasi dependensi, versi runtime, sistem operasi, dan environment variables yang tidak identik dengan lingkungan produksi.
2. **Feedback Loop yang Lambat:** Bug kompilasi, pelanggaran standarisasi kode (*linting errors*), atau kegagalan *unit test* baru terdeteksi berhari-hari setelah kode diintegrasikan ke branch utama, meningkatkan biaya remediasi (*cost of repair*) secara eksponensial.
3. **Kelelahan Tim Peer-Review:** Peninjau kode (*reviewer*) menghabiskan waktu kognitif yang berharga untuk memeriksa kesalahan sintaksis atau menjalankan tes manual, alih-alih berfokus pada arsitektur, keamanan, dan logika bisnis.

GitHub Actions mentransformasikan repositori Git dari media penyimpanan kode pasif menjadi sistem orkestrasi aktif. Melalui GitHub Actions, setiap operasi integrasi diverifikasi secara deterministik pada mesin runner virtual yang bersih (*ephemeral*). Hal ini menjamin standar kualitas kode ditegakkan secara absolut oleh mesin sebelum sebuah baris kode diizinkan masuk ke branch produksi.

---

## SEKSI 05 — APA ITU (WHAT)

**GitHub Actions** adalah platform *Continuous Integration and Continuous Delivery* (CI/CD) yang terintegrasi secara *native* di dalam ekosistem GitHub. Platform ini memungkinkan pengembang mengotomatisasi kompilasi kode, eksekusi test suite, pembuatan rilis, hingga deployment aplikasi berbasis *event* repositori.

### Komponen Inti Arsitektur GitHub Actions:

* **Workflow:** Prosedur otomatisasi yang didefinisikan dalam format YAML dan disimpan di direktori `.github/workflows/`. Repositori dapat memiliki lebih dari satu workflow yang menjalankan tugas berbeda.
* **Event:** Kejadian spesifik di dalam repositori yang memicu eksekusi workflow secara otomatis (misalnya: `git push`, pembuatan `pull_request`, rilis baru, atau jadwal berbasis `cron`).
* **Job:** Sekumpulan *step* yang dieksekusi di dalam instans runner yang sama. Secara default, jika workflow memiliki beberapa job, job-job tersebut akan berjalan secara paralel kecuali ditentukan dependensinya (`needs:`).
* **Step:** Tugas individual yang dieksekusi secara berurutan di dalam sebuah job. Step dapat menjalankan perintah terminal (`run:`) atau mengonsumsi action terenkapsulasi (`uses:`).
* **Action:** Modul aplikasi portabel yang dapat digunakan kembali (*reusable standalone application*) yang mengeksekusi tugas kompleks, misalnya mengkloning repositori (`actions/checkout`) atau menyiapkan runtime bahasa pemrograman (`actions/setup-node`).
* **Runner:** Server tervirtualisasi (VM) atau kontainer terisolasi yang mendengarkan event workflow, mengeksekusi job, dan melaporkan status hasilnya kembali ke GitHub. Runner dapat disediakan langsung oleh GitHub (*GitHub-hosted*) atau server milik organisasi Anda sendiri (*Self-hosted*).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

Siklus hidup eksekusi GitHub Actions beroperasi melalui serangkaian tahapan berikut:

```
[ Git Push / PR ] 
       │
       ▼
 1. Webhook Notification
       │
       ▼
 2. Event Evaluation Engine (.github/workflows/*.yml)
       │
       ▼
 3. Runner Allocation (Provisioning VM: ubuntu-latest)
       │
       ▼
 4. Workspace Preparation
       │
       ▼
 5. Sequential Step Execution
       │  ├─ Action: actions/checkout
       │  ├─ Action: Setup Environment
       │  ├─ Run: Dependency Installation
       │  └─ Run: Test Suite
       ▼
 6. Teardown & Log Streaming
       │
       ▼
 7. Commit Status API Update (Pass/Fail)
```

1. **Trigering Event:** Pengembang melakukan `git push` atau membuka `pull_request`. GitHub API menangkap event tersebut dan mengevaluasi seluruh file YAML pada direktori `.github/workflows/`.
2. **Evaluasi Filter:** GitHub memeriksa apakah event memenuhi kriteria filter (misalnya: event `push` hanya pada branch `main`, atau perubahan hanya pada path `src/**`). Jika cocok, workflow diantrekan (*queued*).
3. **Runner Provisioning:** GitHub mengalokasikan mesin virtual terisolasi yang baru (*fresh ephemeral VM*). Setiap job mendapatkan VM terpisah.
4. **Eksekusi Workspace:** Runner mengunduh konteks environment, melakukan clone repositori melalui action `checkout`, dan mengeksekusi step satu per satu secara sekuensial. Jika ada step yang mengembalikan exit code non-zero (`!= 0`), step berikutnya otomatis dibatalkan, dan job ditandai sebagai `failed`.
5. **Reporting & Cleanup:** Status eksekusi (`success` atau `failure`) dikirimkan kembali melalui GitHub Checks API, menampilkan tanda centang hijau atau silang merah di sebelah commit hash dan Pull Request. Setelah selesai, VM runner dihancurkan demi keamanan data.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

Berikut adalah alur arsitektur interaksi antara GitHub Event, Runner VM terisolasi, dan evaluasi Status Check pada Pull Request:

```
+-------------------------------------------------------------------------------+
| GITHUB PLATFORM                                                               |
|                                                                               |
|  Local Machine                 GitHub Remote Repo                             |
|  +-------------+               +-------------------------------------------+  |
|  | git push    | ------------> | Event: pull_request (to branch: main)     |  |
|  +-------------+               +---------------------+---------------------+  |
|                                                      | triggers               |
|                                                      v                        |
|                                +-------------------------------------------+  |
|                                | .github/workflows/ci.yml                  |  |
|                                +---------------------+---------------------+  |
|                                                      | dispatches             |
+------------------------------------------------------|------------------------+
                                                       |
                                                       v
+-------------------------------------------------------------------------------+
| RUNNER VIRTUAL MACHINE (ubuntu-latest ephemeral instance)                     |
|                                                                               |
|  Job: "run-tests"                                                             |
|  +-------------------------------------------------------------------------+  |
|  | STEP 1: actions/checkout@v4                                             |  |
|  | - Mengunduh salinan repositori commit target ke /home/runner/work       |  |
|  +------------------------------------+------------------------------------+  |
|                                       | exit 0                                |
|                                       v                                       |
|  +-------------------------------------------------------------------------+  |
|  | STEP 2: actions/setup-node@v4 (or python/go/etc)                        |  |
|  | - Menyiapkan runtime binary & inject PATH environment variable          |  |
|  +------------------------------------+------------------------------------+  |
|                                       | exit 0                                |
|                                       v                                       |
|  +-------------------------------------------------------------------------+  |
|  | STEP 3: Dependency Resolution (npm ci / pip install)                    |  |
|  | - Mengunduh external dependencies berbasis lockfile deterministik       |  |
|  +------------------------------------+------------------------------------+  |
|                                       | exit 0                                |
|                                       v                                       |
|  +-------------------------------------------------------------------------+  |
|  | STEP 4: Test Suite Execution (npm test / pytest)                        |  |
|  | - Mengeksekusi unit test & capture status exit code                     |  |
|  +------------------------------------+------------------------------------+  |
|                                       |                                       |
+---------------------------------------|---------------------------------------+
                                        | Exit Code Evaluation (0 = Pass, 1 = Fail)
                                        v
+-------------------------------------------------------------------------------+
| GITHUB STATUS CHECKS ENGINE                                                   |
|                                                                               |
|  Pull Request Interface:                                                      |
|  [x] Continuous Integration / run-tests — All checks have passed              |
|  [ MERGE PULL REQUEST BUTTON: ENABLED ]                                       |
+-------------------------------------------------------------------------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Workflow minimal berikut mendemonstrasikan sintaks dasar, eksekusi perintah shell, dan pemicu push.

### File: `.github/workflows/smoke-test.yml`

```yaml
name: Smoke Test Pipeline

# Menentukan event pemicu workflow
on:
  push:
    branches:
      - main
  pull_request:
    branches:
      - main

# Mendefinisikan kumpulan pekerjaan (jobs)
jobs:
  health-check:
    name: Execute System Diagnostics
    runs-on: ubuntu-latest

    steps:
      - name: Print Execution Context
        run: |
          echo "Memulai diagnostik environment runner."
          echo "Pemicu Event: ${{ github.event_name }}"
          echo "Branch Git: ${{ github.ref }}"
          echo "Commit SHA: ${{ github.sha }}"

      - name: Verify OS and Kernel Information
        run: |
          uname -a
          cat /etc/os-release | grep PRETTY_NAME
          python3 --version
          node --version
```

### Penjelasan Baris per Baris:

* `name: Smoke Test Pipeline`: Nama workflow yang akan dirender pada antarmuka web GitHub Actions.
* `on:`: Mendefinisikan event apa saja yang mengaktifkan workflow ini.
* `push` / `pull_request`: Workflow hanya bereaksi terhadap push dan pembukaan/pembaruan Pull Request yang menargetkan branch `main`.
* `jobs:`: Blok akar yang menampung seluruh pekerjaan yang akan dieksekusi.
* `health-check:`: Identifier unik (Job ID) dari job yang bersangkutan.
* `name: Execute System Diagnostics`: Nama deskriptif job yang tampil di UI visual GitHub.
* `runs-on: ubuntu-latest`: Memerintahkan GitHub untuk memfasilitasi VM berbasis sistem operasi Ubuntu LTS terbaru.
* `steps:`: Daftar instruksi sekuensial yang harus dieksekusi di dalam runner.
* `name: ...`: Label deskripsi untuk masing-masing step.
* `run: |`: Mengeksekusi blok skrip multi-baris pada shell default runner (`bash` pada Ubuntu).
* `${{ github.* }}`: Sintaks ekspresi GitHub Actions untuk mengakses variabel konteks bawaan (metadata runtime).

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut adalah pipeline CI level produksi untuk aplikasi berbasis Node.js yang memverifikasi standarisasi kode (*linting*), menjalankan automated test suite, dan memanfaatkan fungsionalitas caching dependensi.

### File: `.github/workflows/node-ci.yml`

```yaml
name: Continuous Integration - Web Service

on:
  push:
    branches:
      - main
      - 'releases/**'
    paths-ignore:
      - '**.md'
      - 'docs/**'
  pull_request:
    branches:
      - main
    paths-ignore:
      - '**.md'
      - 'docs/**'

# Membatalkan eksekusi pipeline lama jika ada commit baru pada branch/PR yang sama
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint-and-format:
    name: Code Quality & Linting
    runs-on: ubuntu-latest
    steps:
      - name: Source Code Checkout
        uses: actions/checkout@v4

      - name: Initialize Node.js Runtime
        uses: actions/setup-node@v4
        with:
          node-version: 20.x
          cache: 'npm'

      - name: Deterministic Dependency Installation
        run: npm ci

      - name: Run Linter Validation
        run: npm run lint

  automated-tests:
    name: Test Suite Execution
    needs: lint-and-format # Job dependency: Hanya berjalan jika lint-and-format lulus
    runs-on: ubuntu-latest
    strategy:
      matrix:
        node-version: [18.x, 20.x] # Menguji aplikasi di berbagai versi Node.js
    steps:
      - name: Source Code Checkout
        uses: actions/checkout@v4

      - name: Initialize Node.js Environment (${{ matrix.node-version }})
        uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node-version }}
          cache: 'npm'

      - name: Install Dependencies
        run: npm ci

      - name: Run Unit & Integration Tests
        run: npm test -- --coverage
        env:
          CI: true
          NODE_ENV: test
```

### Analisis Fitur Lanjutan:

1. **`paths-ignore`:** Menghemat kuota runner dengan tidak memicu pipeline jika perubahan commit hanya melibatkan file dokumentasi Markdown (`.md`).
2. **`concurrency` dengan `cancel-in-progress: true`:** Jika pengembang melakukan push revisi commit baru saat pipeline commit lama sedang berjalan, pipeline lama otomatis dihentikan seketika. Ini menghemat resource secara signifikan.
3. **`uses: actions/checkout@v4`:** Action resmi dari GitHub untuk mengkloning repositori ke runner workspace. Tanpa step ini, runner VM berada dalam kondisi kosong tanpa kode aplikasi Anda.
4. **`cache: 'npm'` pada `actions/setup-node`:** Mengaktifkan mekanisme caching otomatis untuk folder cache global npm, mempercepat durasi step `npm ci` dari menit menjadi hitungan detik.
5. **`needs: lint-and-format`:** Menerapkan Directed Acyclic Graph (DAG). Job `automated-tests` tidak akan dialokasikan runner jika tahap linting kode terbukti gagal.
6. **`strategy.matrix`:** Menjalankan 2 sub-job paralel secara simultan untuk memvalidasi kompatibilitas lintas versi Node.js (18.x dan 20.x).

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Arsitektural | Opsi A: GitHub-Hosted Runners | Opsi B: Self-Hosted Runners |
| :--- | :--- | :--- |
| **Beban Pemeliharaan** | **Nol:** GitHub mengelola provisioning VM, keamanan OS kernel, dan rotasi mesin. | **Tinggi:** Tim internal harus mengelola patching OS, skalabilitas, dan hardening runtime. |
| **Isolasi Keamanan** | **Tinggi:** Setiap job berjalan di VM *ephemeral* yang langsung dihancurkan setelah selesai. | **Rentan:** State persistent dapat memicu risiko kontaminasi artifact dan security breach antar-job jika tidak di-containerisasi dengan tepat. |
| **Kinerja & Resource** | Resource standar (2 Core vCPU, 7GB RAM). Kurang fleksibel untuk beban komputasi masif. | Beban komputasi dapat disesuaikan (GPU khusus, memory besar, arsitektur hardware custom). |
| **Biaya Operasional** | Gratis untuk repositori publik. Mengonsumsi limit menit berbayar pada repositori privat. | Tidak ada biaya menit dari GitHub, tetapi ada biaya infrastruktur server sendiri (AWS EC2, on-prem bare-metal). |
| **Akses Jaringan Privat** | Butuh VPN/IP Whitelisting yang kompleks untuk menyentuh database privat internal. | Dapat langsung ditaruh di dalam subnet VPC lokal perusahaan. |

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan Versi Action yang Eksplisit (Pinning):** Jangan pernah menggunakan branch mengambang seperti `uses: actions/checkout@main`. Gunakan full commit hash (SHA) untuk proteksi keamanan maksimal (`uses: actions/checkout@a5ac7e5...`) atau minimal rilis major terverifikasi (`actions/checkout@v4`).
2. **Gunakan `npm ci` Alih-alih `npm install`:** Perintah `npm ci` menjamin dependency tree diinstal secara mutlak persis sesuai file `package-lock.json`, mematikan kemampuan modifikasi lockfile di lingkungan CI.
3. **Posisikan Step Caching di Tahap Awal:** Selalu konfigurasikan caching untuk package managers (npm, pip, maven) guna meminimalkan latensi build dan menghemat bandwidth jaringan eksternal.
4. **Terapkan Prinsip Least Privilege:** Batasi permissions token repositori (`GITHUB_TOKEN`) dengan mendeklarasikannya di tingkat atas file workflow:
   ```yaml
   permissions:
     contents: read
     pull-requests: write
   ```
5. **Tentukan Timeout Eksplisit:** Cegah proses yang hang menghabiskan seluruh kuota menit komputasi akun Anda dengan menambahkan konfigurasi timeout:
   ```yaml
   jobs:
     test:
       runs-on: ubuntu-latest
       timeout-minutes: 15 # Mematikan job otomatis jika berjalan lebih dari 15 menit
   ```

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Pelanggaran Aturan Sintaksis Identasi YAML
YAML sangat sensitif terhadap karakter spasi (whitespaces). Mencampurkan karakter tabulasi (*tab*) dengan spasi atau indentasi yang meleset 1 karakter akan menyebabkan workflow ditolak secara total dengan pesan error: `YAML parse error`.
* **Solusi:** Konfigurasikan code editor (VS Code) dengan extension YAML linter dan atur indentasi otomatis menggunakan 2 spasi.

### 2. Lupa Menjalankan Step `actions/checkout`
Pengembang pemula sering kali langsung memanggil `run: npm test` atau eksekusi script tanpa memanggil `actions/checkout`. Runner VM yang bersih tidak membawa salinan kode repositori secara otomatis.
* **Gejala:** Muncul error terminal `npm ERR! enoent ENOENT: no such file or directory, open 'package.json'`.

### 3. Mengabaikan Perbedaan Huruf Besar/Kecil (*Case Sensitivity*) pada Path File
Banyak pengembang bekerja di platform macOS atau Windows yang file system-nya *case-insensitive*, sementara default runner GitHub Actions (`ubuntu-latest`) menggunakan Linux ext4 yang murni *case-sensitive*.
* **Gejala:** Kode aplikasi berhasil diuji di lokal, tetapi gagal saat dieksekusi di GitHub Actions dengan pesan error modul tidak ditemukan (`Cannot find module './Component'`).

### 4. Hardcoding Kredensial dan Secret Sensitif
Menuliskan API token, database password, atau private keys secara langsung di dalam file YAML repositori. File ini dapat dibaca oleh publik atau siapa pun yang memiliki akses baca repositori.
* **Solusi:** Simpan nilai sensitif pada menu **Settings > Secrets and variables > Actions**, lalu rujuk via sintaksis variabel `${{ secrets.NAMA_SECRET }}`.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Latihan:
Anda ditugaskan membuat gerbang otomatisasi CI sederhana untuk repositori proyek. Pipeline harus memvalidasi integritas file konfigurasi sistem sebelum diizinkan merge ke branch `main`.

### Langkah 1: Inisialisasi Repositori Lokal
Buka terminal dan buat repositori proyek lokal baru:
```bash
mkdir exercise-gh-actions
cd exercise-gh-actions
git init
git branch -M main
```

### Langkah 2: Buat Skrip Pengujian Sederhana
Buat file target pengujian bernama `validator.sh`:
```bash
cat << 'EOF' > validator.sh
#!/usr/bin/env bash
set -e

echo "Memeriksa integritas sistem..."
if [ -f "config.json" ]; then
    echo "[PASS] File config.json ditemukan."
    exit 0
else
    echo "[FAIL] File config.json TIDAK ditemukan!"
    exit 1
fi
EOF

chmod +x validator.sh
```

### Langkah 3: Konfigurasi File Workflow GitHub Actions
Buat struktur direktori `.github/workflows` dan definisikan alur CI:
```bash
mkdir -p .github/workflows
cat << 'EOF' > .github/workflows/verify-system.yml
name: File Integrity CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  validate-files:
    runs-on: ubuntu-latest
    steps:
      - name: Clone Repository Content
        uses: actions/checkout@v4

      - name: Execute Shell Validator
        run: ./validator.sh
EOF
```

### Langkah 4: Commit dan Simulasikan Kondisi Gagal (Failure State)
```bash
git add .
git commit -m "feat: initial commit with validator and ci workflow"
# Hubungkan ke remote GitHub Anda
# git remote add origin https://github.com/<username>/exercise-gh-actions.git
# git push -u origin main
```
*Amati pada tab **Actions** di repositori GitHub Anda. Job akan **FAIL** (merah) karena `config.json` belum dibuat, menghasilkan status exit code 1.*

### Langkah 5: Perbaiki Masalah (Self-Healing) dan Verifikasi Keberhasilan
```bash
# Buat file konfigurasi yang dibutuhkan skrip
echo '{"status": "production-ready", "version": "1.0.0"}' > config.json

git add config.json
git commit -m "fix: provide missing config.json required by validator"
git push origin main
```
*Buka kembali tab **Actions** di repositori GitHub. Sebuah workflow run baru akan terpicu secara otomatis dan menghasilkan status **SUCCESS** (centang hijau).*

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan-pertanyaan berikut untuk memvalidasi pemahaman teknis Anda:

1. **Secara default, jika sebuah workflow memiliki 3 buah job yang berbeda, bagaimanakah cara GitHub Actions mengeksekusinya?**
   * A. Secara berurutan sesuai urutan penulisan baris di file YAML.
   * B. Secara acak bergantung ketersediaan runner.
   * C. Secara paralel dan independen di mesin runner terpisah.
   * D. Bergantian menunggu job pertama selesai sepenuhnya.

2. **Perhatikan cuplikan YAML berikut. Kapan step ini akan dieksekusi?**
   ```yaml
   - name: Clear Temporary Artifacts
     run: rm -rf ./dist
     if: failure()
   ```
   * A. Selalu dieksekusi terlepas dari status step sebelumnya.
   * B. Hanya dieksekusi jika ada step sebelumnya di dalam job yang sama mengalami kegagalan.
   * C. Dieksekusi jika repositori dihapus dari GitHub.
   * D. Step ini tidak valid dan akan memicu sintaks error.

3. **Mengapa perintah `uses: actions/checkout@v4` hampir selalu menjadi step pertama dalam sebagian besar pipeline software CI?**
   * A. Untuk mengalokasikan lisensi Ubuntu runner.
   * B. Karena runner bawaan GitHub tidak memiliki memori workspace.
   * C. Untuk mengunduh kode dari repositori Git ke dalam file system lokal milik runner.
   * D. Untuk mengautentikasi akun GitHub pengguna yang melakukan push.

4. **Bagaimana cara mencegah sebuah job di GitHub Actions terus berjalan tanpa henti (infinite loop) yang berpotensi menghabiskan kuota menit organisasi?**
   * A. Menghapus repositori secara otomatis.
   * B. Mengatur properti `timeout-minutes` pada tingkat job.
   * C. GitHub Actions otomatis mematikan semua script setelah 30 detik.
   * D. Menulis script `exit 0` di awal workflow.

5. **Apa fungsi dari sintaks `strategy: matrix:` pada konfigurasi job?**
   * A. Mengenkripsi environment variables secara dua arah.
   * B. Membuat visualisasi grafik dependency build di GitHub UI.
   * C. Mengizinkan satu definisi job dijalankan berulang kali secara paralel dengan variasi variabel konfigurasi yang berbeda (misalnya: OS atau versi bahasa).
   * D. Menghubungkan repositori lokal secara peer-to-peer dengan runner.

---

### Kunci Jawaban & Evaluasi:
1. **C** — Secara default semua job berjalan paralel jika runner tersedia. Ketergantungan sekuensial hanya terbentuk jika kita mendefinisikan kunci `needs:`.
2. **B** — Karakteristik `if: failure()` adalah kondisional bawaan untuk menjalankan skrip fallback/cleanup jika terdeteksi status error sebelumnya.
3. **C** — Runner VM yang disediakan GitHub adalah lingkungan baru (*clean OS*) yang tidak memiliki konteks kode sumber sampai action `actions/checkout` dipanggil.
4. **B** — Properti `timeout-minutes` merupakan pengaman wajib untuk membatasi waktu eksekusi maksimal sebuah job.
5. **C** — Matrix build dirancang untuk menghindari duplikasi kode YAML dengan mengizinkan eksekusi paralel dari satu konfigurasi terhadap multipel versi runtime/OS.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Dokumentasi Resmi GitHub Actions:** [https://docs.github.com/en/actions](https://docs.github.com/en/actions)
* **GitHub Actions Workflow Syntax Reference:** [https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
* **GitHub Actions Marketplace:** [https://github.com/marketplace?type=actions](https://github.com/marketplace?type=actions)
* **Security Hardening Guide for GitHub Actions:** [https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
* **Buku:** *"GitHub Actions in Action"* oleh John Arundel (Manning Publications).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **Definisi:** GitHub Actions adalah platform otomasi terintegrasi yang mengeksekusi pipeline pengujian dan rilis berbasis siklus kejadian (*event-driven*) repositori.
2. **Hierarki File:** Workflow didefinisikan dalam format YAML di direktori `.github/workflows/`. Hierarki eksekusi terdiri atas: **Workflow** $\rightarrow$ **Jobs** $\rightarrow$ **Steps** $\rightarrow$ **Actions/Commands**.
3. **Isolasi Runner:** Setiap job dieksekusi di dalam mesin virtual atau kontainer terisolasi (*ephemeral VM*). File repositori harus diambil secara eksplisit melalui `actions/checkout`.
4. **Efisiensi Eksekusi:** Gunakan event filtering (`branches`, `paths`), mekanika pembatalan redundansi (`concurrency`), dan *matrix strategy* untuk menjaga eksekusi pipeline tetap cepat dan hemat biaya.
5. **Integritas Branch:** GitHub Actions berfungsi sebagai gerbang validasi (*gatekeeper*) utama. Melalui fitur *Branch Protection Rules*, commit yang menyebabkan status pipeline gagal (*red*) dilarang melakukan integrasi (*merge*) ke branch produksi.

---

## SEKSI 17 — GLOSARIUM

* **Artifact:** File atau koleksi file (misalnya: file binary, file `.zip`, laporan cakupan tes/coverage) yang dihasilkan selama eksekusi job yang dapat disimpan dan diunduh setelah runner dihancurkan.
* **CI (Continuous Integration):** Praktik rekayasa perangkat lunak di mana anggota tim mengintegrasikan kode mereka ke repositori bersama secara reguler, diverifikasi oleh sistem kompilasi dan pengujian otomatis.
* **Concurrency:** Mekanisme untuk mengontrol dan membatasi eksekusi simultan dari workflow atau job yang sama, berguna untuk membatalkan build lama yang sudah usang.
* **Ephemeral Runner:** Mesin runner yang dibuat sementara untuk satu kali eksekusi job dan langsung dihancurkan (*teardown*) setelah job selesai demi integritas keamanan.
* **Exit Code:** Kode numerik standar sistem operasi yang dikembalikan oleh proses saat selesai. Nilai `0` merepresentasikan kesuksesan (*success*), sedangkan nilai selain nol (`1-255`) mengindikasikan kegagalan (*error/failure*).
* **Matrix Build:** Fitur eksekusi paralel yang secara otomatis membuat beberapa variasi job berdasarkan parameter kombinasi yang ditentukan (misalnya: kombinasi OS `[ubuntu, windows]` dan Node `[18, 20]`).
* **Workflow Dispatch:** Event manual yang memungkinkan pengguna menjalankan workflow secara langsung via tombol UI GitHub atau panggilan REST API.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Pencegahan Error Pemula:** Pastikan peserta memahami bahwa tab indentasi adalah musuh utama format YAML. Wajibkan peserta menggunakan ekstensi *YAML* di VS Code yang secara eksplisit mengonversi Tab menjadi 2 Spasi.
* **Manajemen Kuota Menit:** Untuk repositori publik, GitHub Actions bersifat gratis tanpa batas menit normal (mengikuti batasan wajar). Namun, jika peserta membuat repositori *private*, ingatkan bahwa ada limit kuota gratis bulanan (biasanya 2.000 menit/bulan). Latih peserta menerapkan `paths-ignore` dan `concurrency: cancel-in-progress: true` sejak awal.
* **Pemberian Analogi Konsep:** 
  * *Workflow* = Buku instruksi resep makanan.
  * *Runner* = Dapur bersih yang disewa.
  * *Job* = Menu hidangan tertentu (misal: "Membuat Sup").
  * *Step* = Langkah memotong sayur, merebus air.
  * *Action* = Alat masak siap pakai (misal: "Blender otomatis").
* **Debug Strategi:** Jika pipeline peserta gagal tanpa log yang jelas, instruksikan mereka untuk mengaktifkan Runner Diagnostic Logging dengan membuat Secret bernama `ACTIONS_RUNNER_DEBUG` bernilai `true`.

---

## SEKSI 19 — CHANGELOG & VERSI

| Versi | Tanggal Rilis | Penulis / Maintainer | Catatan Perubahan |
| :--- | :--- | :--- | :--- |
| `v1.0.0` | 2024-03-30 | Lead Curriculum Architect | Rilis kurikulum awal. Mencakup konsep fundamental CI, integrasi syntax YAML v4, dan skenario latihan integrasi file system. |
| `v1.1.0` | 2024-04-15 | Senior Technical Reviewer | Pembaruan standar aksi runner ke node-20 environment runtime, penambahan konfigurasi `concurrency`, dan diagram ASCII mendalam. |

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** [Bab 09 Module 01 — Kolaborasi Tim: Pull Request, Code Review, dan Branch Protection Rules](../01-09-pull-requests-and-reviews/)
* **Modul Saat Ini:** **Bab 10 Module 01 — Otomasi Dasar CI/CD Menggunakan GitHub Actions**
* **Modul Berikutnya:** [Bab 11 Module 01 — Git Tagging, Rilis Perangkat Lunak, dan Semantic Versioning](../01-11-tags-releases-and-semver/)