## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Pembelajaran**: Core Foundations DevOps
*   **Kategori**: `01-Core-Foundations`
*   **Bab**: `06 — Continuous Integration`
*   **Modul**: `01 — Fondasi Continuous Integration: Arsitektur, Pipeline, dan Otomasi Verifikasi`
*   **Kode Modul**: `CF-DEV-06-01`
*   **Tingkat Kesulitan**: Beginner to Intermediate
*   **Estimasi Waktu Penyelesaian**: 180 Menit (3 Jam)
*   **Prasyarat**: 
    *   Memahami Version Control System berbasis Git (Branching, Merging, Pull Request).
    *   Familiar dengan Command-Line Interface (Bash/POSIX Shell).
    *   Memahami konsep dasar kompilasi, build runtime (Node.js/Python/Go), dan pengujian perangkat lunak (*unit testing*).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1.  **Menganalisis** akar permasalahan integrasi perangkat lunak tradisional (*Integration Hell*) dan merumuskan solusi berbasis paradigma *Continuous Integration* (CI).
2.  **Menjelaskan** arsitektur dasar sistem CI, meliputi interaksi antara *Code Repository*, *Webhook Event*, *CI Orchestrator*, *Runner/Agent*, dan *Artifact Storage*.
3.  **Mengonfigurasi dan Membangun** pipeline CI otomatis yang mencakup tahapan *code checkout*, *dependency caching*, *static analysis/linting*, *automated test execution*, dan *artifact generation*.
4.  **Mengimplementasikan** strategi penanganan kegagalan (*fail-fast mechanism*) dan pelaporan umpan balik cepat (*fast feedback loop*) dalam lingkungan pengembangan kolaboratif.
5.  **Mendeteksi dan Memitigasi** *anti-patterns* CI, seperti *flaky tests*, *slow pipeline bottleneck*, dan *unclean build environments*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       [Continuous Integration Core]
                                     |
    +--------------------------------+--------------------------------+
    |                                |                                |
[Prinsip Dasar]            [Komponen Arsitektur]              [Tahapan Pipeline]
    |                                |                                |
    +-- Single Source of Truth       +-- Source Code (VCS)            +-- Trigger & Checkout
    +-- Frequent Merging             +-- Webhook Receiver             +-- Setup Environment
    +-- Automated Self-Testing       +-- CI Coordinator/Server        +-- Static Code Analysis
    +-- Ephemeral Execution          +-- Runners/Agents (Worker)      +-- Unit & Integration Tests
    +-- Fast Feedback Loop           +-- Artifact Repository          +-- Build & Package
                                                                      +-- Report Status Check
```

Peta alur ketergantungan konseptual:
1.  **Version Control System (VCS)** bertindak sebagai pemicu (*trigger* event).
2.  Event dikirimkan ke **CI Server** untuk dievaluasi terhadap definisi deklaratif pipeline.
3.  Server menugaskan pekerjaan kepada **Runner terisolasi (Ephemeral Worker)**.
4.  Runner mengeksekusi pipeline: Validasi sintaks $\rightarrow$ Build dependencies $\rightarrow$ Run Tests $\rightarrow$ Evaluasi exit code.
5.  Hasil akhir dilaporkan kembali ke VCS sebagai **Status Check** (Pass/Fail) untuk menentukan kelayakan *merge*.

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Secara historis, tim pengembangan software bekerja dalam cabang (*feature branch*) yang berumur panjang (minggu hingga bulan). Ketika cabang-cabang tersebut digabungkan ke cabang utama (*main/trunk*), tim menghadapi fenomena yang disebut **Integration Hell**:
*   Ratusan konflik kode yang saling tumpang tindih.
*   Perubahan fungsi yang merusak (*break*) dependensi modul lain secara tak terduga.
*   Waktu debug yang memakan waktu berhari-hari hingga berminggu-minggu menjelang rilis.

Berdasarkan laporan *State of DevOps (DORA)*, tim berkinerja tinggi (*elite performers*) mengintegrasikan kode mereka ke *trunk* beberapa kali sehari. 

Continuous Integration menggeser deteksi kegagalan sejauh mungkin ke kiri (*Shift-Left Testing*). Semakin awal suatu *bug* terdeteksi:
*   **Biaya perbaikan (Cost of Defect)** menjadi eksponensial lebih murah. Menemukan regresi pada saat Pull Request (menit setelah kode ditulis) membutuhkan biaya dan waktu 10-100x lebih rendah dibanding memperbaikinya setelah berada di lingkungan produksi.
*   **Integritas Main Branch Terjaga**: Cabang utama selalu berada dalam status *deployable* (siap dirilis kapan saja).
*   **Kepercayaan Diri Tim Meningkat**: Penghapusan keraguan "apakah kode saya merusak sistem yang ada?" berkat otomasi verifikasi deterministik.

---

## SEKSI 05 — APA ITU (WHAT)

**Continuous Integration (CI)** adalah praktik rekayasa perangkat lunak di mana anggota tim mengintegrasikan pekerjaan mereka ke dalam *mainline* repositori bersama secara reguler (minimal sekali atau beberapa kali per hari), di mana setiap integrasi diverifikasi secara otomatis oleh sistem build dan pengujian mandiri untuk mendeteksi kesalahan secepat mungkin.

### Empat Pilar Fondasi CI:
1.  **Single Source of Truth**: Seluruh kode, konfigurasi infrastruktur, skrip build, dan skema pengujian dikelola dalam satu sistem kontrol versi (VCS).
2.  **Automated Build**: Proses kompilasi dan perakitan software harus dapat dijalankan melalui satu perintah tanpa intervensi manual (menggunakan build tool seperti npm, Gradle, Maven, Go CLI, make).
3.  **Self-Testing Build**: Kode harus memiliki cakupan tes otomatis (Unit Test, Integration Test) yang dieksekusi secara otomatis oleh CI runner. Jika ada tes yang gagal, build dianggap gagal secara absolut.
4.  **Ephemeral & Hermetic Environment**: Setiap pengujian harus dijalankan dalam lingkungan yang bersih, terisolasi, dan dapat direproduksi dari nol (misalnya container Docker atau VM instan), bebas dari sisa eksekusi sebelumnya (*side effects*).

### Perbedaan CI, CD (Delivery), dan CD (Deployment):

| Kategori | Definisi Lingkup | Output Akhir | Pemicu Deploy ke Production |
| :--- | :--- | :--- | :--- |
| **Continuous Integration (CI)** | Integrasi, Linting, Build, Automated Testing | Artefak terverifikasi (Binary, Container Image, Package) | N/A (Hanya verifikasi integrasi) |
| **Continuous Delivery (CD)** | CI + Persiapan deployment otomatis ke staging/pre-prod | Artefak siap rilis di staging | Manual Approval (Klik tombol release) |
| **Continuous Deployment (CD)** | CI + Otomasi penuh tanpa gerbang manual ke production | Kode berjalan di end-user production | Otomatis setelah lulus semua tahap test |

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

Pipeline CI beroperasi berdasarkan siklus hidup deterministik yang dipicu oleh suatu kejadian (*event-driven architecture*).

### Tahapan Siklus Hidup Eksekusi CI:

```
[ Developer ] --(1. Push/PR)--> [ VCS (GitHub/GitLab) ]
                                         |
                                (2. Webhook Event)
                                         v
                                  [ CI Controller ]
                                         |
                          (3. Dispatch Job & Context)
                                         v
                            [ Isolated Runner / Pod ]
                                         |
                 +-----------------------+-----------------------+
                 |                       |                       |
          (a. Checkout)          (b. Resolve Dep)       (c. Static Lint)
                 |                       |                       |
                 +-----------------------+-----------------------+
                                         |
                 +-----------------------+-----------------------+
                 |                       |                       |
          (d. Unit Test)         (e. Build Binary)      (f. Archive Art.)
                 |                       |                       |
                 +-----------------------+-----------------------+
                                         |
                               (4. Send Exit Status)
                                         v
           [ Pull Request Status: SUCCESS (0) or FAILURE (!= 0) ]
```

1.  **Triggering (Pemicu)**:
    Developer menjalankan `git push` ke repositori remote (misal: GitHub/GitLab) atau membuat *Pull Request* (PR). Platform VCS mendeteksi event ini dan menembakkan HTTP POST Webhook payload ke sistem CI (misal: GitHub Actions, GitLab CI, Jenkins).
2.  **Job Scheduling & Allocation**:
    CI Controller menerima webhook, membaca file konfigurasi pipeline (misal: `.github/workflows/ci.yml`), dan mengalokasikan eksekusi pekerjaan ke *Worker Agent* (Runner) yang cocok dengan kriteria (*label/OS/resources*).
3.  **Workspace Initialization & Checkout**:
    Runner mempersiapkan *workspace* kosong (menggunakan container runtime atau VM). Runner mengeksekusi `git clone` atau `git fetch` terhadap commit SHA spesifik yang memicu pipeline.
4.  **Dependency Resolution & Caching**:
    CI mengunduh dependensi eksternal yang dibutuhkan oleh aplikasi. Mekanisme caching berbasis *hash key* (misal: `package-lock.json`, `go.sum`, `pom.xml`) diaktifkan untuk menghindari *download* ulang paket yang tidak berubah, memangkas waktu eksekusi.
5.  **Static Analysis & Linting**:
    Kode dievaluasi tanpa dieksekusi (*static code analysis*) menggunakan linter (ESLint, Flake8, GolangCI-Lint) dan scanner keamanan (SonarQube, Trivy, GitLeaks) untuk memastikan kepatuhan gaya kode dan ketiadaan kerentanan/kredensial yang bocor.
6.  **Compilation & Automated Testing**:
    Kode dikompilasi (jika menggunakan bahasa terkompilasi). Runner mengeksekusi rangkaian *unit test* dan *integration test*. Runner memantau nilai balikan (*exit code*) proses:
    *   `Exit Code 0`: Sukses / Lulus.
    *   `Exit Code != 0`: Gagal. Pipeline langsung dibatalkan (*Fail-Fast*).
7.  **Artifact Archiving & Reporting**:
    Jika pengujian sukses, artefak hasil build (Docker Image, ZIP, Binary) dikirimkan ke Artifact Registry. Status akhir (lulus/gagal beserta log eksekusi) dilaporkan kembali ke VCS melalui Commit Status API.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

Berikut adalah arsitektur aliran interaksi CI Engine, Webhook, Runner, dan State Transition:

```
+-----------------------------------------------------------------------------------------------+
|                                ARSITEKTUR ALIRAN SISTEM CI                                    |
+-----------------------------------------------------------------------------------------------+

[ DEVELOPER ]
      |
      |  (1) git push origin feature-branch
      v
+-----------------------+
|  VCS (e.g., GitHub)   |
|  +-----------------+  |
|  | Webhook Engine  |--+---(2) HTTP POST Payload (commit SHA, branch, ref)
+-----------------------+   |
                            v
            +-------------------------------+
            |     CI ORCHESTRATOR / API     |
            |  (Parse Workflow Definition)  |
            +-------------------------------+
                            |
                 (3) Schedule & Queue Job
                            |
                            v
            +-------------------------------+
            |     AGENT POOL / RUNNER       |
            |  (Docker Container / VM)      |
            +-------------------------------+
            | [STATE: PENDING]              |
            |  1. Provision Virtual Env     |
            |                               |
            | [STATE: RUNNING]              |
            |  2. git clone --depth=1 repo  |
            |  3. Restore Cache (~/.npm)    |
            |  4. npm ci (Install Dep)      |
            |  5. npm run lint              |
            |     +-- Exit 0 -> Lanjut      |
            |     +-- Exit 1 -> [FAIL EXIT] |
            |  6. npm test (Unit/Mock Tests)|
            |     +-- Exit 0 -> Lanjut      |
            |     +-- Exit 1 -> [FAIL EXIT] |
            |  7. npm run build             |
            |                               |
            | [STATE: FINALIZING]           |
            |  8. Upload Artifact / Cache   |
            |  9. Tear-down Environment     |
            +-------------------------------+
                            |
                 (4) Report Exit Code (0/1)
                            |
                            v
            +-------------------------------+
            |      VCS API INTEGRATION      |
            |  (Commit Status Checks API)   |
            +-------------------------------+
                            |
       +--------------------+--------------------+
       |                                         |
       v                                         v
 [ STATUS: SUCCESS (0) ]                   [ STATUS: FAILURE (!= 0) ]
       |                                         |
  Merge PR Enabled                         Block PR Merge
  Notify Developer via Slack               Notify Developer (Action Needed)
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Simulasi CI Runner lokal menggunakan Bash script murni. Script ini mereplikasi logika yang dijalankan oleh agen CI di cloud: memeriksa status, mengeksekusi tahapan secara sekuensial, dan menerapkan prinsip *fail-fast* menggunakan POSIX exit code.

### Script: `local-ci-runner.sh`

```bash
#!/usr/bin/env bash
# local-ci-runner.sh: Simulasi runner CI lokal dengan mekanisme fail-fast.

# Mengaktifkan proteksi:
# -e: Berhenti langsung jika ada perintah yang menghasilkan exit code non-zero.
# -u: Berhenti jika ada variabel yang belum didefinisikan.
# -o pipefail: Pipeline gagal jika ada perintah di dalam pipeline yang gagal.
set -euo pipefail

echo "=========================================="
echo ">> [CI STAGE 1/4]: Environment Setup"
echo "=========================================="
BUILD_DIR="./.build_workspace"
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"
echo "Workspace dialokasikan di ${BUILD_DIR}"

echo "=========================================="
echo ">> [CI STAGE 2/4]: Static Code Linting"
echo "=========================================="
# Simulasi linter: Memeriksa apakah ada file shell script yang tidak lolos sintaks
for script in *.sh; do
    if [ -f "$script" ]; then
        echo "Validasi sintaks: $script"
        bash -n "$script" || {
            echo "ERROR: Linting gagal pada file $script" >&2
            exit 1
        }
    fi
done
echo "Hasil Linting: PASSED"

echo "=========================================="
echo ">> [CI STAGE 3/4]: Automated Unit Tests"
echo "=========================================="
# Simulasi test execution
RUN_TEST_MOCK() {
    # Fungsi uji dummy: Menguji operasi logika aritmatika
    local expected=42
    local actual=$(( 40 + 2 ))
    
    if [ "$expected" -ne "$actual" ]; then
        return 1
    fi
    return 0
}

if RUN_TEST_MOCK; then
    echo "Test Case 01 (Math Logic): PASSED"
else
    echo "Test Case 01 (Math Logic): FAILED" >&2
    exit 2
fi

echo "=========================================="
echo ">> [CI STAGE 4/4]: Build & Packaging"
echo "=========================================="
tar -czf "${BUILD_DIR}/application-artifact.tar.gz" --exclude=".build_workspace" .
echo "Artefak berhasil dibuat: ${BUILD_DIR}/application-artifact.tar.gz"

echo "=========================================="
echo ">> CI PIPELINE STATUS: SUCCESS (All stages passed)"
echo "=========================================="
exit 0
```

### Cara Menjalankan:
```bash
chmod +x local-ci-runner.sh
./local-ci-runner.sh
echo "Exit Code Pipeline: $?"
```

Jika salah satu tahap gagal (misal: buat error sintaks pada script), script akan langsung berhenti pada baris kesalahan tanpa mengeksekusi tahapan berikutnya (*fail-fast*), dan nilai `$?` akan bernilai selain 0.

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut adalah pipeline CI standar industri untuk REST API berbasis Node.js/TypeScript menggunakan **GitHub Actions**. Pipeline ini mencakup:
*   Trigger pada `push` ke branch utama dan `pull_request`.
*   *Concurrency Control* (membatalkan pipeline lama jika ada push baru pada PR yang sama).
*   *Dependency Caching* otomatis.
*   *Parallel Execution* / *Matrix Testing* di berbagai versi Node.js.
*   Linter, Type Check, Security Audit, Unit Test, dan Artifact Archiving.

### File: `.github/workflows/ci.yml`

```yaml
name: Continuous Integration Pipeline

on:
  push:
    branches:
      - main
      - develop
  pull_request:
    branches:
      - main
      - develop

# Batalkan build yang sedang berjalan jika ada commit baru di PR yang sama
concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true

jobs:
  code-quality:
    name: Code Quality & Security Audit
    runs-on: ubuntu-22.04
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4

      - name: Setup Node.js Runtime
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'

      - name: Install Dependencies
        run: npm ci --prefer-offline

      - name: Execute Linter (ESLint)
        run: npm run lint

      - name: Static Type Check (TypeScript Compiler)
        run: npm run typecheck

      - name: Security Vulnerability Scan
        run: npm audit --audit-level=high

  test-matrix:
    name: Unit & Integration Tests (Node ${{ matrix.node-version }})
    needs: code-quality # Tahap ini hanya berjalan jika code-quality lolos
    runs-on: ubuntu-22.04
    strategy:
      fail-fast: true
      matrix:
        node-version: [18.x, 20.x]

    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4

      - name: Setup Node.js Runtime ${{ matrix.node-version }}
        uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node-version }}
          cache: 'npm'

      - name: Install Dependencies
        run: npm ci

      - name: Execute Automated Test Suite
        run: npm test -- --coverage
        env:
          CI: true
          NODE_ENV: test

      - name: Upload Coverage Results
        uses: actions/upload-artifact@v4
        if: matrix.node-version == '20.x' # Hanya simpan coverage dari runtime utama
        with:
          name: code-coverage-report
          path: coverage/
          retention-days: 7

  build-artifact:
    name: Compile & Package Application
    needs: test-matrix
    runs-on: ubuntu-22.04
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4

      - name: Setup Node.js Runtime
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'

      - name: Install Production Dependencies Only
        run: npm ci

      - name: Build Production Assets
        run: npm run build

      - name: Archive Production Build
        uses: actions/upload-artifact@v4
        with:
          name: production-build-dist
          path: dist/
          retention-days: 14
```

### Penjelasan Bagian Kritis:
*   `npm ci`: Digunakan sebagai pengganti `npm install`. `npm ci` menghapus direktori `node_modules` lokal dan menginstal dependensi secara strictly deterministik berdasarkan `package-lock.json`.
*   `concurrency`: Menghemat komputasi. Jika developer melakukan *push* tiga kali berturut-turut pada PR yang sama, build 1 dan 2 dibatalkan secara otomatis, hanya build 3 yang dijalankan hingga selesai.
*   `needs: [code-quality]`: Mendefinisikan DAG (*Directed Acyclic Graph*), memastikan pengujian intensif tidak membuang sumber daya runner jika standar kualitas kode dasar (*lint*) gagal.

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Membangun pipeline CI menuntut kompromi antara kecepatan, biaya, dan tingkat kepastian (*confidence*).

| Parameter | Opsi A | Opsi B | Analisis Komparasi Teknis |
| :--- | :--- | :--- | :--- |
| **Runner Infrastructure** | **Cloud-Hosted Runners** (GitHub/GitLab SaaS) | **Self-Hosted Runners** (EC2, K8s Pods) | Cloud-hosted membebaskan biaya maintenance infrastruktur namun mahal pada beban kerja masif. Self-hosted lebih murah pada skala besar dan mendukung akses intranet privat, tetapi menuntut overhead manajemen OS, security patching, dan auto-scaling agent. |
| **Pipeline Breadth** | **Exhaustive Testing** (Unit, Integration, E2E, Load) | **Fast-Feedback Testing** (Lint, Unit Test, Smoke Test) | Menjalankan seluruh *suite* E2E pada setiap commit memberikan tingkat keyakinan 99%, namun pipeline dapat memakan waktu 45+ menit (menghambat kecepatan developer). Praktik terbaik: Jalankan Unit/Lint pada PR (<5 menit), jadwalkan E2E pada *Nightly Build* atau saat *Merge*. |
| **Dependency Strategy** | **Clean Fetch Every Build** | **Aggressive Caching** | Clean fetch menjamin 100% isolasi tanpa cache poisoning, namun membebani bandwidth dan durasi pipeline. Caching memangkas durasi build hingga 70%, namun berisiko memunculkan bug semu jika *cache key invalidation* tidak dikonfigurasi dengan presisi. |
| **Monorepo Strategy** | **Global Trigger** (Jalankan semua test) | **Path Filtering** (Uji modul yang berubah) | Global trigger aman tetapi tidak terukur (*unscalable*). *Path-filtering* (misal: hanya build service `/auth` jika direktori `/auth/**` disentuh) wajib diterapkan pada arsitektur monorepo untuk mencegah antrean runner membengkak. |

---

## SEKSI 11 — BEST PRACTICES

1.  **Pertahankan Batas Waktu Pipeline di Bawah 10 Menit**:
    Jika pipeline CI berjalan lebih dari 10 menit, developer akan beralih ke tugas lain (*context switching*), mengabaikan kegagalan build, dan menunda perbaikan. Optimalkan dengan paralelisasi, caching, dan pemangkasan dependensi.
2.  **Perlakukan Build yang Gagal sebagai P0 (Prioritas Tertinggi)**:
    Sesuai filosofi *Toyota Andon Cord*, jika cabang utama patah (*broken build*), seluruh tim harus menghentikan pengerjaan fitur baru dan segera memperbaikinya (*Fix or Revert within 10 minutes*).
3.  **Terapkan Prinsip Immutability dan Hermetic Builds**:
    Hindari dependensi dinamis yang mengunduh versi tidak terkunci (contoh anti-pattern: `npm install package@latest` atau `curl https://installer.sh | bash` tanpa pinned version/hash). Gunakan *lockfiles* (`package-lock.json`, `poetry.lock`, `Cargo.lock`).
4.  **Terapkan Trunk-Based Development**:
    Hindari *feature branch* yang berumur lebih dari 1-2 hari. Integrasikan kode dalam skala potongan kecil (*atomic commits*) untuk mengurangi probabilitas konflik integrasi.
5.  **Gunakan Ephemeral Environment**:
    Setiap build wajib berjalan dalam container atau VM sekali pakai yang langsung dihancurkan setelah eksekusi selesai untuk mencegah kontaminasi antar-build (*state leakage*).

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Mentolerir *Flaky Tests*
*   **Gejala**: Tes terkadang lulus dan terkadang gagal tanpa ada perubahan kode (biasanya akibat *race conditions*, ketergantungan urutan eksekusi, atau latensi jaringan eksternal).
*   **Dampak Buruk**: Developer kehilangan kepercayaan pada CI, mengabaikan hasil merah, dan secara membabi-buta menekan tombol *"Re-run job"* hingga berhasil.
*   **Remediasi**: Karantina (*quarantine*) tes flaky dari pipeline utama ke jalur investigasi terpisah. Jangan biarkan tes yang tidak konsisten memblokir jalur integrasi atau melatih developer mengabaikan kegagalan.

### 2. Menyimpan Kredensial Langsung di dalam Skrip CI
*   **Gejala**: Meng-hardcode API keys, password database, atau SSH private key di dalam file `ci.yml`.
*   **Dampak Buruk**: Kredensial terekspos ke seluruh anggota tim yang memiliki hak baca ke repositori atau tercetak pada build logs.
*   **Remediasi**: Gunakan Secret Manager platform (GitHub Secrets, GitLab Masked Variables, HashiCorp Vault) dan pastikan runner me-masking teks rahasia pada log keluaran standard (*stdout*).

### 3. Pipeline Mengunduh Dependensi Tanpa Caching
*   **Gejala**: Setiap kali commit di-push, runner mengunduh 1 GB file `node_modules` atau dependency wheel dari internet.
*   **Dampak Buruk**: Durasi build membengkak secara masif dan rentan gagal jika penyedia paket pihak ketiga mengalami *rate-limiting* atau *downtime*.
*   **Remediasi**: Gunakan action cache (`actions/cache` atau integrasi bawaan platform) dengan mengunci hash kunci cache ke lockfile dependensi.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Membangun Verifikasi Sintaks dan Unit Test Lokal via Pre-push Hook
*   **Tujuan**: Membangun mekanisme pertahanan pertama CI pada level workstation lokal sebelum kode mencapai remote VCS.
*   **Instruksi**:
    1.  Buka repositori Git lokal Anda.
    2.  Buat file executable di `.git/hooks/pre-push`.
    3.  Tuliskan script Bash yang memeriksa apakah ada penanda debugging yang tertinggal (misal: `console.log` atau `debugger` pada file `.js`/`.ts` yang dimodifikasi) dan jalankan unit test lokal.
    4.  Cegah push (`exit 1`) jika uji coba lokal gagal.

### Latihan 2: Mengonfigurasi Caching Dependensi pada Pipeline CI
*   **Tujuan**: Mengurangi durasi pipeline CI minimal 50% menggunakan teknik caching direktori.
*   **Skenario**: Anda memiliki aplikasi Python yang membutuhkan dependensi berat (`pytest`, `requests`, `pandas`).
*   **Instruksi**:
    1.  Tulis konfigurasi GitHub Actions workflow `.github/workflows/python-ci.yml`.
    2.  Gunakan action `actions/cache@v4` untuk menargetkan path `~/.cache/pip`.
    3.  Tentukan `key` cache berbasis kombinasi: `${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}`.
    4.  Bandingkan durasi build pertama (*cache miss*) dengan build kedua (*cache hit*).

### Latihan 3: Mengimplementasikan Fail-Fast Matrix Build
*   **Tujuan**: Memverifikasi aplikasi terhadap variasi platform runtime secara simultan dan efisien.
*   **Instruksi**:
    1.  Rancang matrix build yang menguji aplikasi pada 3 sistem operasi yang berbeda (`ubuntu-latest`, `windows-latest`, `macos-latest`).
    2.  Aktifkan opsi `strategy: fail-fast: true`.
    3.  Simulasikan error yang hanya terjadi pada target OS `windows-latest`.
    4.  Amati dan catat bagaimana CI orchestrator segera membatalkan eksekusi pada OS lain saat salah satu node matrix gagal.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

### Pertanyaan Pilihan Ganda

#### 1. Manakah dari pernyataan berikut yang secara akurat merepresentasikan tujuan inti dari Continuous Integration?
A. Mengotomasi proses deployment sistem langsung ke server produksi tanpa pengawasan developer.  
B. Menghilangkan kebutuhan untuk menulis unit test melalui verifikasi fungsional berbasis AI.  
C. Mengintegrasikan perubahan kode ke cabang utama secara frekuen dan memverifikasi integritasnya melalui build dan pengujian terotomasi.  
D. Mengunci repositori kode agar developer hanya dapat melakukan merge seminggu sekali secara terkontrol.

#### 2. Sebuah job CI mengalami kegagalan pada tahap static analysis (linter), namun developer bersikeras bahwa fitur bisnis baru di kodenya berfungsi normal. Berdasarkan filosofi CI modern, tindakan apa yang harus diambil?
A. Mematikan linter pada pipeline agar fitur dapat segera di-merge ke branch utama.  
B. Menolak pull request dan memblokir merge hingga seluruh pelanggaran kode pada linter diperbaiki.  
C. Mengizinkan merge secara manual dengan persetujuan manajer proyek, lalu mengabaikan peringatan linter.  
D. Menghapus status check pada branch protection rule repository.

#### 3. Mengapa perintah `npm ci` lebih direkomendasikan untuk digunakan di dalam pipeline CI dibandingkan perintah `npm install`?
A. Karena `npm ci` secara otomatis memperbarui dependensi ke versi rilis terbaru secara daring.  
B. Karena `npm ci` mengabaikan file `package-lock.json` untuk mempercepat instalasi.  
C. Karena `npm ci` menyediakan instalasi yang deterministik dan konsisten dengan menghapus direktori dependensi yang ada dan hanya merujuk pada `package-lock.json`.  
D. Karena `npm ci` tidak membutuhkan koneksi internet dan tidak memverifikasi checksum paket.

#### 4. Apa yang dimaksud dengan istilah "Flaky Test" dalam ekosistem automated testing pipeline?
A. Pengujian yang memerlukan waktu eksekusi lebih dari 1 jam.  
B. Pengujian yang menghasilkan status yang berbeda-beda (kadang lulus, kadang gagal) pada commit kode yang identik tanpa ada perubahan apapun.  
C. Pengujian yang sengaja dibuat gagal untuk menguji responsibilitas alert monitoring.  
D. Pengujian yang menguji fitur yang belum diimplementasikan di kode produksi.

#### 5. Jika developer A melakukan commit baru pada sebuah Pull Request saat pipeline build untuk commit sebelumnya di PR tersebut masih berlangsung, konfigurasi CI apa yang paling efisien untuk diterapkan?
A. Membiarkan kedua pipeline berjalan hingga selesai untuk redundansi data log.  
B. Menggunakan mekanisme `concurrency` dengan pembatalan otomatis (*cancel-in-progress*) untuk mematikan job lama dan membebaskan runner.  
C. Menolak commit kedua secara otomatis hingga pipeline pertama selesai.  
D. Mematikan worker runner secara mendadak melalui restart server CI.

---

### Kunci Jawaban & Pembahasan
1.  **C** — Konsep dasar CI berfokus pada frekuensi integrasi kode ke branch utama dengan verifikasi otomatis (build + test) secara instan.
2.  **B** — Kualitas kode, standar arsitektur, dan keamanan yang diatur oleh linter adalah bagian dari kontrak kualitas yang tidak boleh ditawar; meloloskan kode cacat gaya atau sintaks akan meningkatkan technical debt.
3.  **C** — `npm ci` (Clean Install) bersifat deterministik; jika ada ketidakcocokan antara `package.json` dan `package-lock.json`, ia akan menghasilkan error, menjamin apa yang diuji di CI persis dengan apa yang ditulis developer.
4.  **B** — Flaky test adalah tes non-deterministik yang merusak reliabilitas sinyal CI dan harus segera dikarantina dan diperbaiki.
5.  **B** — Membatalkan build yang sudah usang (*stale builds*) menghemat biaya komputasi runner dan mempercepat umpan balik pada commit terbaru yang relevan.

---

### Rubrik Penilaian Mandiri

| Tingkat Pemahaman | Kriteria Evaluasi Mandiri |
| :--- | :--- |
| **Dasar (Novice)** | Mengerti definisi CI, mampu menjelaskan perbedaan CI dan CD, memahami fungsi exit code 0 dan non-zero pada otomasi shell. |
| **Menengah (Competent)** | Mampu menulis skrip pipeline CI deklaratif (GitHub Actions/GitLab CI), mengimplementasikan dependency caching, dan menghubungkan status check dengan branch protection rule. |
| **Mahir (Expert)** | Mampu mendiagnosis bottleneck durasi pipeline, menyusun Directed Acyclic Graph (DAG) bertingkat, mengelola runner ephemeral mandiri, dan menyelesaikan problem flaky tests secara terstruktur. |

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

### Dokumentasi Resmi
*   [GitHub Actions Core Concepts & Syntax Reference](https://docs.github.com/en/actions)
*   [GitLab CI/CD Pipeline Architecture Documentation](https://docs.gitlab.com/ee/ci/)
*   [Martin Fowler: Continuous Integration Original Thesis](https://martinfowler.com/articles/continuousIntegration.html)

### Buku Rekomendasi
*   *Continuous Delivery: Reliable Software Releases through Build, Test, and Deployment Automation* — Jez Humble & David Farley (Addison-Wesley Professional).
*   *Accelerate: The Science of Lean Software and DevOps* — Nicole Forsgren, Jez Humble, & Gene Kim (IT Revolution Press).

### Standar Industri
*   [DORA (DevOps Research and Assessment) Core Capabilities: Continuous Integration](https://dora.dev/devops-capabilities/technical/continuous-integration/)

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

Continuous Integration (CI) adalah fondasi paling krusial dalam siklus hidup DevOps modern. CI memecahkan patologi *Integration Hell* melalui otomatisasi verifikasi setiap perubahan kode secara independen dan cepat. 

Komponen utama CI bertumpu pada interaksi harmonis antara:
1.  **Event Webhook** dari repositori Git.
2.  **CI Orchestrator** yang bertindak sebagai pengendali tugas.
3.  **Ephemeral Runners** yang bertugas mengeksekusi instruksi build dalam lingkungan terisolasi.

Kunci keberhasilan implementasi CI bukan sekadar "memiliki pipeline yang berjalan", melainkan memastikan:
*   Pipeline memberikan umpan balik cepat (<10 menit).
*   Kondisi deterministik terjamin melalui isolasi dan manajemen dependensi yang ketat (`lockfiles`).
*   Tim memegang disiplin untuk segera memperbaiki *broken build* sebagai prioritas utama.

---

## SEKSI 17 — GLOSARIUM

*   **Artifact**: Berkas biner, arsip terkompresi, atau image terpaket (misal: `.jar`, `.tar.gz`, Docker Image) yang dihasilkan oleh proses build yang berhasil dan siap untuk diuji lebih lanjut atau disebarkan.
*   **Concurrency**: Kemampuan sistem CI untuk mengelola dan membatasi eksekusi paralel dari alur kerja yang sama untuk menghemat sumber daya komputasi.
*   **Deterministic Build**: Karakteristik proses perakitan kode di mana input yang sama selalu menghasilkan output biner yang sama secara presisi, terlepas dari kapan atau pada mesin mana kode tersebut dikompilasi.
*   **Fail-Fast**: Pola desain di mana sistem segera menghentikan seluruh operasi dan mengembalikan status gagal seketika setelah kegagalan pertama terdeteksi, tanpa membuang waktu menyelesaikan langkah berikutnya.
*   **Flaky Test**: Uji perangkat lunak otomatis yang menunjukkan hasil yang tidak konsisten (bisa lolos atau gagal secara acak) pada commit kode yang sama.
*   **Hermetic Environment**: Lingkungan eksekusi build yang sepenuhnya mandiri, terisolasi, dan tidak bergantung pada konfigurasi atau dependensi luar yang tidak dideklarasikan secara eksplisit.
*   **Runner / Agent**: Mesin virtual atau container komputasi yang menerima instruksi dari server CI untuk menjalankan perintah-perintah pipeline.
*   **Trunk-Based Development**: Strategi percabangan kontrol versi di mana semua developer menggabungkan kode mereka ke satu cabang bersama ("trunk" atau "main") secara rutin, menghindari *long-lived branches*.

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Poin Penekanan Materi:
*   Pastikan siswa memahami bahwa **CI adalah praktik budaya dan metodologi kerja**, bukan sekadar "menggunakan Jenkins atau GitHub Actions". Memiliki file `.github/workflows/ci.yml` tetapi hanya melakukan merge sebulan sekali bukanlah Continuous Integration.
*   Tekankan arti penting dari nilai **Exit Code**. Mahasiswa pemula sering kali membuat build script yang gagal tetapi mengembalikan exit code `0`, sehingga sistem CI keliru menganggap build berhasil (*false positive*).

### Jebakan Umum Peserta Didik (Common Traps):
*   Siswa sering mencampuradukkan dependensi runtime (`dependencies`) dan dependensi pengujian (`devDependencies`), menyebabkan ukuran artefak produksi membengkak secara tidak perlu.
*   Siswa sering lupa mendefinisikan timeout pada job CI mereka. Jika terjadi *infinite loop* pada unit test, runner akan berjalan terus hingga batas kuota penagihan cloud habis. **Selalu ajarkan penggunaan parameter `timeout-minutes`**.

### Panduan Alokasi Sesi Praktik (Total 180 Menit):
*   **00 - 30m**: Teori, arsitektur event-driven CI, dan pembedahan *Integration Hell*.
*   **30 - 60m**: Bedah anatomi script runner shell lokal (Seksi 08) dan pemahaman mendalam tentang exit codes.
*   **60 - 120m**: Praktik langsung membuat workflow GitHub Actions untuk aplikasi nyata (Seksi 09 & Seksi 13 Latihan 1 & 2).
*   **120 - 150m**: Eksperimen troubleshooting broken build, menangani flaky test, dan matrix testing (Seksi 13 Latihan 3).
*   **150 - 180m**: Evaluasi kuis interaktif, tinjauan arsitektur, dan sesi tanya-jawab.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi**: `1.0.0` (Production Stable)
*   **Tanggal Rilis**: 2025-01-15
*   **Penulis**: Tim Kurikulum Core Foundations DevOps
*   **Catatan Perubahan**:
    *   *v1.0.0*: Rilis kurikulum perdana. Struktur 20-seksi terstandarisasi, penambahan diagram arsitektur ASCII sistemik, skrip implementasi lokal POSIX, workflow GitHub Actions Node.js/TypeScript produksi, serta latihan hands-on komprehensif.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya**: `CF-DEV-05-02 — Advanced Git Workflows, Branching Strategies, and Semantic Versioning`
*   **Modul Saat Ini**: `CF-DEV-06-01 — Fondasi Continuous Integration: Arsitektur, Pipeline, dan Otomasi Verifikasi`
*   **Modul Berikutnya**: `CF-DEV-06-02 — Continuous Delivery & Deployment: Release Automation, Strategies, and Artifact Management`