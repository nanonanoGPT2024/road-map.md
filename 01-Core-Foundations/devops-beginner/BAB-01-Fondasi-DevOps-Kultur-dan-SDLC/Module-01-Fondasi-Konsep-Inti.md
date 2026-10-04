# Bab 01 Module 01: Pengenalan DevOps: Paradigma, Kultur, dan The Three Ways

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- **Menganalisis (C4)** akar penyebab inefisiensi sistemik pada model pengiriman perangkat lunak tradisional (*Waterfall/Siloed Agile*) menggunakan prinsip *Theory of Constraints*.
- **Membedakan (C4)** secara kritis antara adopsi DevOps yang berpusat pada kapabilitas kultural-organisasional versus adopsi superfisial yang hanya berorientasi pada perangkat lunak (*toolchain-only*).
- **Mengevaluasi (C5)** alur kerja rekayasa perangkat lunak (*Value Stream*) berdasarkan prinsip *The Three Ways* (Gene Kim et al.).
- **Mengukur (C5)** performa operasional tim menggunakan 4 metrik kunci DORA (*DevOps Research and Assessment*): *Lead Time for Changes*, *Deployment Frequency*, *Change Failure Rate*, dan *Time to Restore Service*.
- **Mengimplementasikan (C3)** *feedback loop* otomatis berbasis skrip shell dan Git hook untuk mereduksi *hand-off friction* antara kode sumber dan eksekusi deployment.

---

### 2. Concept Overview
DevOps adalah paradigma rekayasa perangkat lunak dan manajemen operasional yang menyatukan pengembangan (*Development*) dan operasi sistem (*Operations*) ke dalam siklus hidup berkelanjutan dengan akuntabilitas bersama (*shared ownership*). DevOps bukan sekadar repositori skrip otomatisasi atau jabatan kerja baru, melainkan integrasi mendalam dari tiga pilar: **People (Kultur)**, **Process (Metodologi)**, dan **Products (Toolchain)**.

```
+-------------------------------------------------------------------------+
|                                DEVOPS                                   |
|                                                                         |
|  +--------------------+   +---------------------+   +----------------+  |
|  |       PEOPLE       |   |       PROCESS       |   |    PRODUCTS    |  |
|  | - Kultur Blameless |   | - Feedback Loop     |   | - CI/CD        |  |
|  | - Shared Ownership | * | - Small Batch Sizes | * | - IaC          |  |
|  | - Empathy          |   | - Continuous Flow   |   | - Observability|  |
|  +--------------------+   +---------------------+   +----------------+  |
+-------------------------------------------------------------------------+
```

Konsep inti DevOps berakar pada pemahaman bahwa stabilitas sistem dan kecepatan inovasi bukanlah dua hal yang saling meniadakan (*zero-sum game*), melainkan dua hasil yang saling memperkuat jika didukung oleh kapabilitas otomasi, telemetri, dan budaya eksperimentasi.

---

### 3. Why This Matters
Dalam model organisasi teknologi tradisional, terdapat pemisahan struktural yang memicu konflik kepentingan inheren (*The Wall of Confusion*):
- **Tim Development** diukur berdasarkan kecepatan meluncurkan fitur baru (*velocity/change*).
- **Tim Operations** diukur berdasarkan stabilitas, uptime, dan ketersediaan sistem (*zero downtime/no change*).

Ketegangan sistemik ini menyebabkan:
1. **Lead Time yang Sangat Panjang:** Perubahan kode memerlukan waktu berbulan-bulan untuk sampai ke lingkungan produksi karena rantai birokrasi, peninjauan manual, dan hand-off antar departemen.
2. **Blast Radius yang Masif:** Rilis perangkat lunak dilakukan dalam *batch* besar (*big-bang releases*), meningkatkan risiko kegagalan katastropik saat deployment.
3. **High Mean Time to Recovery (MTTR):** Ketika insiden terjadi di lingkungan produksi, tim saling melempar kesalahan (*finger-pointing*) akibat minimnya konteks bersama dan absennya telemetri terintegrasi.
4. **Degradasi Moral Tim:** Siklus kerja yang sarat krisis (*firefighting mode*), *burnout*, dan gesekan antar departemen yang merusak retensi talenta rekayasa.

Adopsi DevOps meruntuhkan hambatan ini dengan menyelaraskan metrik keberhasilan seluruh entitas teknik menuju satu tujuan tunggal: memberikan nilai (*business value*) kepada pengguna akhir secara cepat, aman, dan berkelanjutan.

---

### 4. What It Is vs What It Isn't

| Karakteristik | What It Is (DevOps Sejati) | What It Isn't (Miskonsepsi Umum) |
|---|---|---|
| **Struktur Tim** | Tanggung jawab bersama (*cross-functional shared ownership*). | Pembentukan departemen terisolasi baru bernama "Tim DevOps". |
| **Fokus Utama** | Optimasi aliran nilai (*Value Stream*), kultur, dan proses. | Pembelian dan instalasi lisensi toolchain mahal (Jenkins, K8s, Terraform) semata. |
| **Operasionalisasi** | Pengembang bertanggung jawab atas kode hingga ke fase *runtime* (*You build it, you run it*). | Tim operasional disuruh menulis skrip automasi tanpa mengubah alur kerja rilis. |
| **Manajemen Insiden** | Retrospektif *blameless*, pembelajaran sistemik dari kegagalan. | Mencari akar penyebab pada kesalahan individu (*human error*) lalu memberi hukuman. |
| **Ukuran Rilis** | Rilis dalam *batch* kecil (*incremental updates*), frekuensi harian atau per jam. | Rilis monolitik skala masif tiap kuartal dengan pengujian manual selama dua minggu. |

---

### 5. How It Works Under The Hood
Fondasi operasional DevOps dibangun di atas kerangka kerja **The Three Ways**:

```
[Development] ---> (Aliran Cepat / Fast Flow) ---> [Operations]
    Aliran 1: The First Way (Systems Thinking / Left-to-Right Flow)

[Development] <--- (Umpan Balik / Telemetry) <--- [Operations]
    Aliran 2: The Second Way (Amplify Feedback Loops / Right-to-Left)

[        Eksperimentasi & Pembelajaran Berkelanjutan Berulang         ]
    Aliran 3: The Third Way (Culture of Continual Experimentation)
```

#### Aliran Pertama: Systems Thinking (Left-to-Right Flow)
Prinsip ini berfokus pada percepatan aliran kerja dari kiri (Konsep/Development) ke kanan (Operasional/Produksi). Tujuannya adalah meminimalkan waktu tunggu (*idle time*) dan *batch size*.
- **Mekanisme Kerja:** Setiap unit kode dipecah menjadi *commit* kecil. Kode melewati pipeline otomatis (Linting -> Unit Test -> Security Scan -> Build Artifact) tanpa intervensi manual.
- **Batasan Sistem (*Theory of Constraints*):** Menemukan *bottleneck* tunggal terbesar pada sistem alur rilis (misalnya: pengujian regresi manual yang memakan waktu 3 hari) dan mengoptimasi titik tersebut sebelum menyentuh komponen lain.

#### Aliran Kedua: Amplify Feedback Loops (Right-to-Left Flow)
Prinsip ini membangun putaran umpan balik yang cepat dan konstan dari kanan (Produksi) kembali ke kiri (Development).
- **Mekanisme Kerja:** Sistem operasional memancarkan telemetri (metrik, log, tracing). Ketika sebuah defek terjadi di produksi, peringatan terotomasi (*alerting*) dialirkan langsung ke insinyur yang menulis kode dalam hitungan detik. 
- **Penerapan Teknis:** Jika *canary release* menghasilkan lonjakan HTTP 5xx sebesar 1%, sistem *auto-rollback* langsung terpicu, dan informasi diagnostik langsung dikirimkan ke kanal komunikasi tim rekayasa.

#### Aliran Ketiga: Culture of Continual Experimentation and Learning
Prinsip ini menciptakan iklim organisasional yang mendorong pengambilan risiko terkontrol, alokasi waktu untuk perbaikan teknis (*technical debt reduction*), dan pembelajaran dari anomali.
- **Mekanisme Kerja:** Injeksi kegagalan terencana (*Chaos Engineering*), pelaksanaan analisis pasca-insiden (*Blameless Post-mortem*), serta pengulangan praktik darurat melalui *GameDay exercises*.

---

### 6. Architecture & System Flow

Perbandingan arsitektural antara pendekatan tradisional (*Silo*) dan model loop tertutup DevOps (*Continuous Delivery Loop*):

#### A. Tradisional Siloed Model (The Wall of Confusion)
```
+---------------+                    ||                    +----------------+
|  DEVELOPMENT  |                    ||                    |   OPERATIONS   |
|               |                    ||                    |                |
| [Write Code]  |                    ||                    | [Receive War]  |
|       |       |                    ||                    |       |        |
| [Build Local] |   Hand-off Ticket  ||   Manual Approval  | [Deploy Script]|
|       v       | -----------------> || -----------------> |       v        |
| [Throw Artifact                    ||                    | [Manual Monitor|
|  over the Wall]                    ||                    |  & Blame Devs] |
+---------------+                    ||                    +----------------+
                        THE WALL OF CONFUSION
```

#### B. DevOps Continuous Feedback Loop
```
   +----------------------------------------------------------------+
   |                                                                |
   v                                                                |
+-------------+       +-------------+       +---------------+       |
| 1. PLAN     | ----> | 2. CODE     | ----> | 3. BUILD      |       |
| Product/Jira|       | Git VCS     |       | Automated CI  |       |
+-------------+       +-------------+       +---------------+       |
                                                    |               |
                                                    v               |
+-------------+       +-------------+       +---------------+       |
| 6. MONITOR  | <---- | 5. DEPLOY   | <---- | 4. TEST       |       |
| Prometheus/ |       | CD Engine / |       | Automated Unit|       |
| OpenTelemetry       | ArgoCD/K8s  |       | & Integration |       |
+-------------+       +-------------+       +---------------+       |
       |                                                            |
       +================ Telemetry & Feedback ======================+
```

---

### 7. Core Terminology
1. **Value Stream:** Rangkaian aktivitas terpadu yang dieksekusi suatu organisasi untuk mengonversi konsep/hipotesis bisnis menjadi perangkat lunak fungsional yang menghasilkan nilai bagi pengguna.
2. **Lead Time for Changes:** Durasi waktu yang dibutuhkan dari sebuah *commit* kode masuk ke repositori hingga kode tersebut berjalan secara aman di lingkungan produksi.
3. **Deployment Frequency:** Tingkat frekuensi organisasi berhasil mendeploy kode ke lingkungan produksi (misal: per bulan, per minggu, atau multipel per hari).
4. **Change Failure Rate (CFR):** Persentase deployment ke produksi yang membutuhkan remediasi segera (misal: hotfix, rollback, patch darurat).
5. **Time to Restore Service (MTTR):** Rata-rata durasi yang dihabiskan untuk memulihkan layanan sistem ketika terjadi insiden pemadaman atau degradasi performa di produksi.
6. **CALMS Framework:** Akronim dari *Culture, Automation, Lean, Measurement, Sharing*; panduan konseptual untuk mengukur kematangan adopsi DevOps.
7. **Shift-Left:** Praktik memindahkan tahapan pengujian, validasi keamanan (*security*), dan integrasi sedini mungkin ke dalam siklus hidup rekayasa (mendekati fase penulisan kode).
8. **Blameless Post-Mortem:** Analisis pasca-insiden yang berfokus pada kerapuhan sistem (*systemic vulnerability*) dan proses, bukan menghukum kesalahan manusia.

---

### 8. Simple Analogy / Mental Model
Bayangkan sebuah **Dapur Restoran Bintang Lima**:
- **Pendekatan Silo Tradisional:** Koki (*Development*) memasak makanan sesuai resep baru tanpa pernah melihat ruang makan. Setelah matang, makanan diletakkan di atas konter lalu ditinggal pergi. Pelayan (*Operations*) bertugas membawakan makanan tersebut ke pelanggan. Jika rasa makanan terlalu asin atau piringnya jatuh, pelayan disalahkan oleh manajer restoran. Koki menyalahkan pelayan karena terlalu lambat menyajikan, sementara pelayan menyalahkan koki karena menyajikan makanan yang tidak matang merata. Pelanggan kecewa, waktu tunggu meja meningkat tajam.
- **Pendekatan DevOps:** Koki dan pelayan bekerja dalam satu tim terintegrasi. Mereka mendesain menu bersama. Dapur menggunakan konveyor otomatis kecil yang langsung menyajikan porsi uji rasa (*small batches*). Koki dapat melihat langsung ekspresi pelanggan melalui jendela terbuka (*telemetry*). Jika seorang pelanggan alergi terhadap bahan tertentu, sistem inventaris dan pelayan segera memberi notifikasi langsung ke stasiun koki (*immediate feedback loop*). Setiap ada piring jatuh, tim berkumpul bukan untuk memecat pelayan, melainkan mengevaluasi tata letak lantai dapur yang licin (*blameless culture*).

---

### 9. Step-by-Step Implementation Guide

Untuk memahami pergeseran dari proses rilis manual ke aliran berbasis DevOps (*The First Way*), kita akan membangun pipeline validasi lokal otomatis menggunakan Git Hooks dan Shell script. Tujuannya adalah memvalidasi kode sebelum diizinkan masuk ke repositori (mencegah defek mengalir ke kanan).

#### Prerequisites
- Sistem Operasi berbasis POSIX (Linux/macOS atau WSL pada Windows).
- Git terinstal (`git --version` >= 2.30).
- Bash shell (`/bin/bash`).

#### Langkah 1: Inisialisasi Repositori Sandboxing
Buat direktori baru dan inisialisasi repositori Git:
```bash
mkdir devops-pipeline-lab
cd devops-pipeline-lab
git init
```

#### Langkah 2: Buat Skrip Aplikasi Tiruan dan Uji Kualitas
Buat script simulasi aplikasi (`app.sh`) dan skrip pengujian integritas (`test.sh`).
```bash
cat << 'EOF' > app.sh
#!/usr/bin/env bash
set -euo pipefail

APP_VERSION="1.0.0"

function start_application() {
    echo "Starting Core Engine version ${APP_VERSION}..."
    return 0
}

start_application
EOF
chmod +x app.sh
```

```bash
cat << 'EOF' > test.sh
#!/usr/bin/env bash
set -euo pipefail

echo "==> Running Automated System Tests..."
if grep -q "APP_VERSION=\"\"" app.sh; then
    echo "ERROR: Version string cannot be empty!" >&2
    exit 1
fi

if ! bash -n app.sh; then
    echo "ERROR: Syntax validation failed!" >&2
    exit 1
fi

echo "==> All Tests Passed Successfully."
exit 0
EOF
chmod +x test.sh
```

#### Langkah 3: Implementasikan Shift-Left Quality Gate (Git Pre-Commit Hook)
Gunakan Git Hook untuk mencegah developer melakukan commit jika pengujian otomatis gagal.
```bash
cat << 'EOF' > .git/hooks/pre-commit
#!/usr/bin/env bash
set -euo pipefail

echo "--- [PHASE: Pre-Commit Quality Gate Triggered] ---"
if ! ./test.sh; then
    echo "REJECTED: Aliran kerja diblokir karena pengujian gagal." >&2
    echo "Perbaiki kesalahan sebelum mengalirkan kode ke upstream." >&2
    exit 1
fi
echo "--- [PHASE: Quality Gate Passed] ---"
EOF
chmod +x .git/hooks/pre-commit
```

#### Langkah 4: Validasi Aliran Sukses
Lakukan commit kode yang valid:
```bash
git add app.sh test.sh
git commit -m "feat: initial commit with integrated test harness"
```
*Ekspektasi Output:*
```text
--- [PHASE: Pre-Commit Quality Gate Triggered] ---
==> Running Automated System Tests...
==> All Tests Passed Successfully.
--- [PHASE: Quality Gate Passed] ---
[master (root-commit) 40e1b2f] feat: initial commit with integrated test harness
 2 files changed, 27 insertions(+)
 create mode 100755 app.sh
 create mode 100755 test.sh
```

#### Langkah 5: Validasi Penghentian Aliran Ketika Terjadi Defek
Uji apakah *quality gate* benar-benar menghentikan defek:
```bash
# Injeksi bug: ubah versi menjadi kosong
sed -i 's/APP_VERSION="1.0.0"/APP_VERSION=""/' app.sh

# Coba lakukan commit perubahan cacat ini
git add app.sh
git commit -m "break: introduced critical version flaw"
```
*Ekspektasi Output:*
```text
--- [PHASE: Pre-Commit Quality Gate Triggered] ---
==> Running Automated System Tests...
ERROR: Version string cannot be empty!
REJECTED: Aliran kerja diblokir karena pengujian gagal.
Perbaiki kesalahan sebelum mengalirkan kode ke upstream.
```
Commit berhasil dibatalkan secara deterministik sebelum menyentuh remote branch.

#### Langkah 6: Rollback dan Pemulihan
Kembalikan perubahan ke kondisi stabil:
```bash
git checkout app.sh
```

---

### 10. Practical Code / Configuration Example

Berikut adalah pipeline CI/CD GitHub Actions terstandarisasi untuk mendemonstrasikan implementasi The First Way (validasi alur cepat) dan The Second Way (notifikasi kegagalan). 

Simpan berkas berikut pada path `.github/workflows/ci-pipeline.yml`:

```yaml
name: Production Quality & Delivery Engine

on:
  push:
    branches:
      - main
  pull_request:
    branches:
      - main

permissions:
  contents: read
  pull-requests: write

jobs:
  static-analysis:
    name: Code Quality and Linting
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4

      - name: ShellCheck Lint Verification
        run: |
          echo "Starting ShellCheck Static Analysis..."
          shellcheck app.sh test.sh

  integration-test:
    name: Integration Testing
    needs: static-analysis
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4

      - name: Execute Automated Test Suite
        run: |
          chmod +x test.sh app.sh
          ./test.sh

  dora-telemetry:
    name: Feedback & Telemetry Loop
    needs: [static-analysis, integration-test]
    runs-on: ubuntu-latest
    if: always()
    steps:
      - name: Send Telemetry on Failure
        if: ${{ contains(needs.*.result, 'failure') }}
        run: |
          echo "ALERT: Pipeline execution failed! Metric CFR potentially affected."
          echo "Triggering direct feedback to engineer: ${{ github.actor }}"
          # Di lingkungan nyata, baris ini mengirimkan webhook ke Slack/OpsGenie/PagerDuty

      - name: Send Telemetry on Success
        if: ${{ !contains(needs.*.result, 'failure') && !contains(needs.*.result, 'cancelled') }}
        run: |
          echo "SUCCESS: Pipeline completed clean. Ready for continuous deployment."
```

#### Line-by-Line Breakdown:
- `on: push: branches: [main]` & `pull_request`: Menerapkan integrasi berkelanjutan (*Continuous Integration*), memastikan setiap penggabungan kode dicek secara otomatis sebelum integrasi selesai.
- `permissions: contents: read`: Memenuhi prinsip keamanan *least privilege*, mencegah pipeline melakukan aksi tak terotorisasi.
- `needs: static-analysis`: Memastikan alur kerja bersifat serial jika dependensi logis diperlukan; menghemat *compute resources* jika analisis statis awal sudah gagal.
- `shellcheck app.sh test.sh`: Pengecekan statis (*shift-left linting*) untuk mendeteksi potensi *bug*, kesalahan memori, atau perilaku destruktif tanpa menjalankan program.
- `if: always()`: Memastikan *job* telemetri dieksekusi secara deterministik terlepas dari status *upstream jobs* (apakah berhasil, gagal, atau dibatalkan).
- `contains(needs.*.result, 'failure')`: Merupakan implementasi The Second Way; mendeteksi kegagalan sistemik dan menyalurkan telemetri insiden ke pihak pengembang secara langsung (*fast feedback*).

---

### 11. Common Anti-Patterns & Pitfalls

#### 1. DevOps Silo (The "DevOps Team" Anti-Pattern)
- **Misconception:** Manajemen membuat unit baru bernama "Departemen DevOps" di antara Tim Dev dan Tim Ops.
- **Detection:** Tim Dev melempar kode ke Tim DevOps, lalu Tim DevOps yang membuat Dockerfile, skrip CI/CD, dan mengoperasikannya.
- **Fix:** Bubarkan silo tersebut. Alokasikan praktisi DevOps sebagai *Enablement Team* atau *Platform Team* yang bertugas membangun sistem internal (*Internal Developer Platform/IDP*) agar para pengembang aplikasi dapat mendeploy kode mereka secara mandiri (*self-service*).

#### 2. Tools-First Cargo Culting
- **Misconception:** "Jika kita memakai Kubernetes dan Jenkins, kita sudah mengadopsi DevOps."
- **Detection:** Sistem menggunakan infrastruktur mutakhir, namun frekuensi rilis masih per tiga bulan, dan rilis membutuhkan 14 tanda tangan persetujuan manajerial manual via surel.
- **Fix:** Fokus pada perbaikan metrik alur proses (*Process Lead Time*) dan otomatisasi *governance* sebelum melakukan migrasi arsitektur komputasi.

#### 3. No-Ops Fallacy
- **Misconception:** DevOps berarti memecat seluruh tim Operations karena developer sekarang dapat menjalankan semuanya sendiri.
- **Detection:** Pengembang mengabaikan perencanaan kapasitas, tata kelola kepatuhan data, dan sistem cadangan (*backup-recovery*), yang akhirnya memicu pemadaman layanan masif saat beban puncak.
- **Fix:** Libatkan tim operasional sebagai arsitek keandalan (*Site Reliability Engineers/SRE*) yang mendesain reliabilitas, observabilitas, dan ketahanan infrastruktur platform.

---

### 12. Performance & Security Considerations

#### Metrik Kinerja Proses (Process Performance)
- **Batch Size Reduction:** Mengurangi ukuran perubahan dari 10.000 baris kode menjadi 100-200 baris kode per commit memangkas risiko kegagalan sistem secara non-linear dan mempercepat penelusuran regresi (*git bisect*).
- **Pipeline Optimization:** Cache dependensi aplikasi (seperti layer Docker, modul Go/Node) pada pipeline CI/CD untuk memastikan waktu eksekusi *feedback loop* developer berada di bawah 10 menit.

#### Security Integration (Shift-Left DevSecOps)
- Jangan memperlakukan pengujian keamanan (*security audit*) sebagai gerbang manual di akhir siklus pengembangan.
- Pasang pemindai SAST (*Static Application Security Testing*) dan SCA (*Software Composition Analysis*) langsung ke dalam pipeline otomatis (misalnya: Trivy, Snyk, Semgrep).
- Kunci integritas rantai pasokan perangkat lunak (*software supply chain*) dengan menandatangani image container secara kriptografis menggunakan Cosign/Sigstore saat lolos pengujian build.

---

### 13. Real-World Production Scenario

#### Kasus: "The Black Friday Freeze" pada FinTech X
- **Insiden:** Seminggu menjelang ajang promosi belanja terbesar, FinTech X memberlakukan *Code Freeze* selama sebulan. Tim operasional mengunci seluruh deployment. Dua hari sebelum acara, ditemukan celah keamanan kritis pada sistem pembayaran yang harus ditambal (*patched*).
- **Aksi Cacat Tanpa DevOps:** Tim development membuat perbaikan darurat (*hotfix*), tetapi tidak ada pipeline yang aktif karena sistem dibekukan. Tim Ops mencoba menyalin biner secara manual ke 40 server produksi pada pukul 02:00 pagi. Salah satu pustaka dinamis (*shared library*) tidak cocok pada 8 server, memicu galat `Segmentation Fault`. Load balancer terus mengarahkan trafik ke server yang rusak. Terjadi pemadaman total (*total outage*) selama 6 jam.
- **Triage & Root Cause Analysis:**
  - *Root Cause:* Tidak adanya konsistensi artefak rilis antara *staging* dan produksi, ketiadaan pipeline deployment terotomasi yang berulang, serta fragmentasi komunikasi antar tim yang memicu human-error saat eksekusi manual.
- **Mitigasi Berbasis DevOps:**
  1. *Immutable Infrastructure:* Gunakan artefak yang sama (kontainer OCI) dari tahap commit hingga produksi.
  2. *Automated Canary Deployment:* Gunakan traffic-routing otomatis (misalnya melalui Service Mesh / Ingress Controller). Rilis patch ke 2% pengguna terlebih dahulu, pantau telemetri metrik error rate selama 5 menit.
  3. Jika HTTP error 5xx naik > 0.05%, sistem otomatis memutar balik (*rollback*) lalu lintas data secara instan tanpa intervensi manusia.

---

### 14. Trade-Off Analysis

| Keputusan Pendekatan | Keuntungan Utama | Kompensasi / Kerugian (Trade-off) | Rekomendasi Kontekstual |
|---|---|---|---|
| **Otonomi Total Dev (No Governance)** | Kecepatan rilis ekstrem; *lead time* instan. | Potensi kerentanan keamanan dan fragmentasi konfigurasi infrastruktur. | Prototyping awal atau startup tahap eksplorasi pasar (pre-seed). |
| **Strict Change Advisory Board (CAB Manual)** | Mengurangi risiko perubahan yang tidak terkoordinasi secara visual. | *Lead time* hancur; developer cenderung menumpuk perubahan menjadi *batch* masif. | Lingkungan regulasi perbankan inti generasi lama (namun harus dimigrasi ke *automated compliance*). |
| **Platform Engineering / Internal Developer Platform (IDP)** | Menyediakan *golden path*; mengawinkan kecepatan dan keamanan secara terotomasi. | Biaya investasi awal yang tinggi dan kebutuhan insinyur platform yang kompeten. | Organisasi dengan skala rekayasa menengah ke atas (> 30 insinyur perangkat lunak). |

---

### 15. Edge Cases & Boundary Conditions

1. **Sistem Warisan Berbasis Monolitik Tanpa Automated Tests:**
   - *Problem:* Penerapan pipeline *Continuous Delivery* secara murni gagal karena tidak ada unit test, dan sistem terlalu rapuh untuk dideploy berkali-kali dalam sehari.
   - *Penanganan:* Jangan langsung memecah kode menjadi *microservices*. Terapkan teknik *Strangler Fig Pattern*. Mulai dengan membungkus monolit dengan *integration tests* terluar (black-box), lalu buat jalur rilis terotomasi untuk modul-modul independen baru.
2. **Kepatuhan Regulasi Finansial Ketat (Separation of Duties - SoD):**
   - *Problem:* Regulasi seperti PCI-DSS atau SOX melarang orang yang menulis kode untuk mendeploy kode yang sama ke lingkungan produksi.
   - *Penanganan:* Jangan kembali ke model *ticket-based hand-off* manual. Pisahkan izin melalui kriptografi dan pipeline. Developer dapat men-trigger deployment via Git Merge Request yang membutuhkan *peer-review approval* terverifikasi. Eksekusi deployment dilakukan secara eksklusif oleh *Service Account* sistem CI/CD, sehingga tidak ada campur tangan manusia langsung pada mesin produksi.

---

### 16. Best Practices Checklist

#### Kultur & Organisasi
- [ ] Menerapkan analisis *Blameless Post-Mortem* pada setiap kegagalan produksi (maksimal 48 jam pasca insiden).
- [ ] Menghapus dewan persetujuan manual lintas fungsi (*Manual CAB*) dan menggantinya dengan verifikasi kebijakan terotomasi (*Policy-as-Code*).
- [ ] Mengukur dan mengevaluasi 4 Metrik DORA secara berkala tiap kuartal.

#### Proses & Aliran Kerja
- [ ] Batasi ukuran commit; idealnya setiap perubahan selesai dan digabungkan dalam kurun waktu kurang dari 24 jam (*Trunk-Based Development*).
- [ ] Terapkan prinsip *Stop-the-Line mentality* (Andon Cord): Jika pipeline utama gagal, prioritas seluruh tim adalah memperbaikinya sebelum menulis kode baru.

#### Otomasi & Telemetri
- [ ] Semua konfigurasi sistem, pipeline, dan infrastruktur harus disimpan sebagai kode (*Everything as Code*) di bawah kontrol versi Git.
- [ ] Logging, Metrik, dan Tracing terhubung ke sistem alert terpadu yang memicu rollback otomatis jika terjadi anomali pasca deployment.

---

### 17. Self-Assessment Exercises

#### A. Skenario Desain Arsitektur Proses
Sebuah tim e-commerce melakukan deployment setiap dua minggu sekali pada tengah malam hari Sabtu, sering kali memicu *overtime* hingga Minggu pagi karena terjadi kegagalan sinkronisasi skema database. 
- **Pertanyaan:** Rancanglah strategi transformasi 3-langkah menggunakan prinsip *The Three Ways* untuk mengubah alur rilis ini menjadi deployment siang hari (*normal working hours deployment*) tanpa *downtime*.
- **Kriteria Evaluasi:** Solusi harus memuat (1) reduksi *batch size*, (2) teknik pemisahan deployment dari rilis fitur (misal: *Feature Flags*), dan (3) otomatisasi pengujian migrasi basis data.

#### B. Perhitungan Metrik DORA
Sebuah startup memiliki data berikut selama 30 hari:
- Total deploy ke produksi: 6 kali.
- Rata-rata waktu dari push kode hingga live: 72 jam.
- Dari 6 deployment, 2 deployment memicu insiden sistem mati (*crash*) dan harus di-rollback.
- Waktu yang dibutuhkan untuk memulihkan sistem yang crash tersebut adalah masing-masing 4 jam dan 2 jam.
- **Tugas:** Hitung metrik DORA Startup tersebut:
  1. *Deployment Frequency*
  2. *Lead Time for Changes*
  3. *Change Failure Rate*
  4. *Time to Restore Service*
  Berdasarkan standar DORA, tentukan apakah startup ini masuk kategori *Low, Medium, High,* atau *Elite Performer*.

#### C. Debugging Skenario: Menemukan Hambatan Alur Kerja
Audit skrip pipeline fiktif berikut yang menyebabkan kegagalan kultur di mana tim Dev membenci sistem automasi karena feedback loop yang terlalu lambat:
```bash
# Skenario script CI lambat
run_full_e2e_tests_against_real_browsers() # Memakan waktu 3 jam
run_unit_tests()                            # Memakan waktu 30 detik
run_static_analysis()                       # Memakan waktu 15 detik
```
- **Tugas:** Susun ulang urutan dan jelaskan rasionalisasinya berdasarkan prinsip *Fast Feedback Loop*.

---

### 18. Troubleshooting Guide

#### Isu 1: Resistensi Developer terhadap Kegagalan Pipeline ("Test Flakiness")
- **Gejala:** Developer mengabaikan alarm kegagalan pipeline CI/CD dan melakukan *force-merge* kode cacat ke branch utama.
- **Akar Masalah:** Adanya tes yang tidak deterministik (*flaky tests*) yang kadang lulus dan kadang gagal tanpa ada perubahan kode. Hal ini merusak kepercayaan (*trust*) terhadap *quality gate*.
- **Resolusi:**
  1. Karantina segera tes yang terbukti *flaky* keluar dari *blocking pipeline*.
  2. Tempatkan tes tersebut pada *non-blocking background pipeline* hingga diperbaiki.
  3. Tegakkan aturan ketat: Kegagalan pipeline utama (*blocking*) adalah insiden level tim yang harus langsung diselesaikan.

#### Isu 2: Terjadinya Pembentukan Budaya Menyalahkan (*Blame Game*) saat Insiden
- **Gejala:** Saat terjadi pemadaman sistem, kanal komunikasi dipenuhi pertanyaan seperti "Siapa yang terakhir mengedit berkas ini?" atau "Siapa yang menjalankan perintah ini?".
- **Akar Masalah:** Manajemen menerapkan tindakan hukuman atas kegagalan teknis, memicu perilaku penyembunyian masalah dan hilangnya transparansi.
- **Resolusi:**
  1. Ubah format retrospektif insiden menjadi *Blameless Post-Mortem*.
  2. Modifikasi pertanyaan peninjauan insiden: Jangan tanya *siapa*, tanyakan: *"Kondisi apa yang memungkinkan sistem membiarkan aksi tersebut dieksekusi?"* atau *"Bagaimana sistem proteksi kita gagal mendeteksi galat tersebut lebih awal?"*.

---

### 19. Next Steps & Recommended Reading

#### Modul Selanjutnya
- **Bab 01 Module 02: Version Control Deep Dive & Trunk-Based Development:** Mempelajari strategi percabangan (*branching strategy*) yang menghilangkan *merge hell* dan menjadi akselerator utama implementasi CI/CD modern.

#### Referensi Wajib
1. *The Phoenix Project: A Novel about IT, DevOps, and Helping Your Business Win* - Gene Kim, Kevin Behr, George Spafford.
2. *Accelerate: The Science of Lean Software and DevOps* - Nicole Forsgren, Jez Humble, Gene Kim (Referensi otoritatif statistik DORA).
3. *The DevOps Handbook* - Gene Kim, Jez Humble, Patrick Debois, John Willis.
4. *Site Reliability Engineering: How Google Runs Production Systems* - Betsy Beyer et al.

---

### 20. Quick Reference / Cheat Sheet

#### 4 DORA Metrics Benchmarks (State of DevOps Standard)
```
+---------------------+-------------------+---------------------+
| Metrik              | Elite Performer   | Low Performer       |
+---------------------+-------------------+---------------------+
| Deployment Freq     | On-demand (multi) | Antara 1 bln - 6 bln|
| Lead Time for Change| < 1 jam           | Antara 1 bln - 6 bln|
| Time to Restore     | < 1 jam           | > 1 minggu          |
| Change Failure Rate | 0% - 15%          | 46% - 60%           |
+---------------------+-------------------+---------------------+
```

#### CALMS Checklist Ringkas
- **C (Culture):** Kolaborasi aktif, empati, akuntabilitas tanpa rasa takut (*psychological safety*).
- **A (Automation):** Otomasi tugas repetitif bernilai rendah; hindari intervensi manual pada rilis.
- **L (Lean):** Gunakan ukuran batch kecil, batasi *Work In Progress* (WIP), dan hilangkan limbah (*waste*).
- **M (Measurement):** Ukur segalanya: sistem, proses bisnis, dan waktu aliran tim (telemetri & metrik DORA).
- **S (Sharing):** Dokumentasi terbuka, alat bersama, transparansi lintas departemen, dan penyebaran ilmu.

#### The Three Ways Formula
$$\text{Way 1: Accelerate Flow} \implies \text{Reduce Batch Size} + \text{Eliminate Bottlenecks}$$
$$\text{Way 2: Amplify Feedback} \implies \text{Push Telemetry to Developers} + \text{Shorten Detection Time}$$
$$\text{Way 3: Experimentation} \implies \text{Inject Faults} + \text{Transform Accidents into Institutional Knowledge}$$