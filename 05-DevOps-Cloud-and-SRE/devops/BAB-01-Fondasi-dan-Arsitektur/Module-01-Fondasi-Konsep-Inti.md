# Bab 01: Paradigma & Fondasi Rekayasa DevOps
## Modul 01: Dekonstruksi Silo, Paradigma CAMS/CALMS, dan SDLC Berbasis Otomasi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
*   **Menganalisis** friksi struktural antara *Software Engineering* (Dev) dan *System Administration/Operations* (Ops) menggunakan pendekatan *Theory of Constraints*.
*   **Mengimplementasikan** kerangka kerja CAMS (*Culture, Automation, Measurement, Sharing*) ke dalam alur kerja rekayasa perangkat lunak modern.
*   **Mengukur** performa rekayasa sistem berbasis metrik standar industri DORA (*Deployment Frequency, Lead Time for Changes, Change Failure Rate, Time to Restore Service*).
*   **Merancang** siklus hidup *Software Development Life Cycle* (SDLC) tertutup (*closed-loop*) dengan prinsip *Shift-Left Testing* dan otomatisasi pipeline berbasis Git.
*   **Mengevaluasi** risiko antipattern "DevOps Silo" dan merancang mitigasi struktural pada organisasi rekayasa perangkat lunak.

---

### 2. Conceptual Overview
Secara historis, rekayasa perangkat lunak menderita disparitas insentif fundamental:
*   **Tim Pengembang (Dev):** Diinsentifkan untuk memaksimalkan *laju perubahan (velocity & throughput)* fitur baru ke pasar.
*   **Tim Operasional (Ops):** Diinsentifkan untuk menjaga *stabilitas (uptime & availability)* dan meminimalisasi *mean time between failures* (MTBF) dengan membatasi perubahan sistem.

```
       TRADISIONAL (SILOED)                  MODERN (DEVOPS LOOP)
 +-----------------------------+        +-----------------------------+
 |       Development           |        |                             |
 | [Velocity / Change Focus]   |        |    Plan ----> Code          |
 +--------------+--------------+        |     ^          |            |
                | (Wall of     |        |     |          v            |
                v  Confusion)  |        |  Monitor     Build          |
 +-----------------------------+        |     ^          |            |
 |       Operations            |        |     |          v            |
 | [Stability / Uptime Focus]  |        |   Operate <-- Deploy        |
 +-----------------------------+        +-----------------------------+
```

DevOps bukanlah sekadar kumpulan *tooling* (seperti Docker atau Kubernetes), bukan sebuah jabatan tunggal (*job title*), dan bukan tim terisolasi baru. **DevOps adalah paradigma sosio-teknikal** yang menyatukan orang, proses, dan produk guna menghantarkan nilai secara berkelanjutan kepada pengguna akhir. Pendekatan ini mengatasi *Wall of Confusion* dengan mendistribusikan tanggung jawab kepemilikan sistem (*shared ownership*) di sepanjang siklus hidup aplikasi.

---

### 3. Why It Matters
Tanpa penerapan DevOps yang disiplin:
1.  **Lead Time Tinggi:** Perubahan kode memakan waktu berminggu-minggu hingga berbulan-bulan untuk mencapai produksi akibat penyerahan (*hand-off*) manual antar-divisi.
2.  **Blast Radius Masif:** Rilis dilakukan secara periodik dalam ukuran sangat besar (*infrequent batch releases*), meningkatkan probabilitas kegagalan sistem secara katastropik saat deployment.
3.  **Finger-Pointing Culture:** Ketika insiden *outage* terjadi di *production*, investigasi bergeser dari penyelesaian masalah sistemik ke pencarian kambing hitam (*blame culture*).
4.  **Ketidakteraturan State Operasional:** Terjadi *configuration drift* antara server *staging* dan *production* akibat provisioning manual, menyebabkan anomali *"it works on my machine"*.

---

### 4. What Is It?
Secara formal, DevOps mencakup dua pilar fundamental: **Framework CAMS/CALMS** dan **Metrik Kinerja DORA**.

#### Kerangka Kerja CAMS / CALMS
*   **Culture:** Transformasi dari akuntabilitas terisolasi ke *shared responsibility* ("You build it, you run it"). Membangun lingkungan kerja *blameless post-mortem*.
*   **Automation:** Mengeliminasi intervensi manual (toil) melalui pipeline CI/CD, *Infrastructure as Code* (IaC), dan *automated testing*.
*   **Lean:** Meminimalisasi *work in progress* (WIP), memperkecil *batch size*, serta mempercepat siklus *feedback loop*.
*   **Measurement:** Pengambilan keputusan berbasis telemetri dan metrik observabilitas (*metrics, logs, traces*), bukan opini.
*   **Sharing:** Transparansi dokumentasi, visibilitas kode operasional, dan diseminasi pengetahuan lintas domain.

#### DORA Metrics (DevOps Research and Assessment)
Empat metrik kuantitatif penentu efektivitas implementasi DevOps:

| Metrik | Deskripsi | Target Elite Performer |
| :--- | :--- | :--- |
| **Deployment Frequency (DF)** | Seberapa sering kode berhasil dideploy ke *production*. | Beberapa kali per hari (*on-demand*) |
| **Lead Time for Changes (LTFC)** | Durasi dari *commit* pertama hingga berjalan di *production*. | Kurang dari 1 jam |
| **Change Failure Rate (CFR)** | Persentase deployment yang memicu kegagalan sistem / degradasi layanan. | 0% – 15% |
| **Time to Restore Service (TTRS)** | Waktu yang dibutuhkan untuk memulihkan layanan pasca-insiden (*Mean Time to Recovery*). | Kurang dari 1 jam |

---

### 5. How It Works
DevOps mengonversi SDLC linier (Waterfall) menjadi siklus iteratif kontinu dengan umpan balik cepat (*fast feedback loops*):

```
[Developer Machine]
       │
       ▼ (1. Git Commit & Push)
[Source Control Management (Git)]
       │
       ▼ (2. Webhook Event Trigger)
[Continuous Integration (CI Engine)]
       ├─ Linting & Static Code Analysis (SonarQube)
       ├─ Unit & Integration Testing
       ├─ Security Scan (SAST / Dependency Check)
       └─ Artifact Packaging (Docker Build)
       │
       ▼ (3. Artifact Registration)
[Container / Artifact Registry]
       │
       ▼ (4. Continuous Delivery / GitOps)
[Staging Environment] ──(Automated E2E Tests)──► [Production Deployment]
                                                        │
                                                        ▼ (5. Telemetry)
                                               [Monitoring & APM]
                                                        │
                                                        └─► Feedback to Dev
```

1.  **Shift-Left:** Menjalankan pengujian fungsional, performa, dan keamanan sedini mungkin dalam siklus rilis (sejak tahap commit lokal dan CI).
2.  **Immutable Infrastructure:** Modifikasi pada sistem tidak dilakukan langsung pada runtime server (*in-place updates*), melainkan dengan merilis artefak baru (misal: image container baru) menggantikan yang lama.
3.  **Fast Feedback Loop:** Jika tahap *build*, *test*, atau *security* gagal, pipeline langsung berhenti (*fail-fast*), dan insinyur segera menerima notifikasi dalam hitungan menit.

---

### 6. Architecture / Flow Diagram
Arsitektur interaksi antara Tim Rekayasa, Pipeline Otomasi, dan Lingkungan Runtime:

```
+---------------------------------------------------------------------------------------+
| SIKLUS CONTINUOUS DELIVERY & FEEDBACK LOOP                                           |
+---------------------------------------------------------------------------------------+

 DEV REALM                 AUTOMATION ENGINE (CI/CD)               OPS/RUNTIME REALM
+------------+            +---------------------------+           +--------------------+
|  Engineer  |            | Runner / Pipeline Worker  |           | Production Cluster |
+-----+------+            +-------------+-------------+           +---------+----------+
      |                                 |                                   |
      | 1. git push                     |                                   |
      v                                 |                                   |
+------------+    2. Webhook            |                                   |
| Git Server | ------------------------>|                                   |
+------------+                          |                                   |
                                        v                                   |
                          +---------------------------+                     |
                          | Stage 1: Static Analysis  |                     |
                          | (lint, syntax, secrets)   |                     |
                          +-------------+-------------+                     |
                                        |                                   |
                                        v                                   |
                          +---------------------------+                     |
                          | Stage 2: Automated Tests  |                     |
                          | (unit, integration)       |                     |
                          +-------------+-------------+                     |
                                        |                                   |
                                        v                                   |
                          +---------------------------+                     |
                          | Stage 3: Build & Package  |                     |
                          | (immutable container)     |                     |
                          +-------------+-------------+                     |
                                        |                                   |
                                        | 3. Push Image                     v
                                        +--------------------------> +-----------------+
                                                                     | Registry / OCI  |
                                                                     +--------+--------+
                                                                              |
                                        4. Trigger CD / Orchestration         | 5. Pull
                                        +-------------------------------------+
                                        |
                                        v
                                  +------------+                  +--------------------+
                                  | Deploy Job | ---------------> | Live Workload / K8s|
                                  +------------+   Rollout Spec   +---------+----------+
                                                                            |
                                        6. Telemetry Data                   v
   +------------------------------------------------------------------------+
   | (Logs, Metrics, Prometheus Alerts, Tracing)
   v
+-------------+
| Monitoring  | === Feedback (Lead Time, MTTR, Logs) ===> Loop kembali ke Dev
+-------------+
```

---

### 7. Core Primitives & Terminology
*   **Pipeline:** Urutan instruksi otomatis yang dijalankan oleh runner (CI/CD engine) dari kompilasi hingga deployment.
*   **Artifact:** Hasil kompilasi/paket software terisolasi yang siap dijalankan (misal: Docker Image, JAR, binary executable).
*   **Continuous Integration (CI):** Praktik menggabungkan kode ke branch utama secara reguler, di mana setiap integrasi divalidasi otomatis oleh build dan test.
*   **Continuous Delivery (CD):** Kemampuan untuk merilis perubahan kode yang lolos pipeline ke target environment secara otomatis, dengan eksekusi rilis ke production yang dapat dipicu manual (*1-click*).
*   **Continuous Deployment:** Evolusi dari Continuous Delivery di mana *setiap* perubahan yang lolos pengujian pipeline langsung diterapkan ke production tanpa intervensi manusia sama sekali.
*   **Toil:** Pekerjaan operasional yang bersifat manual, repetitif, dapat diotomatisasi, minim nilai teknis jangka panjang, dan membesar seiring pertumbuhan skala sistem.

---

### 8. Simple Code Example: Automasi Linting dan Verifikasi Standar Git
Skrip bash ini mendemonstrasikan implementasi *feedback loop* lokal pertama pada mesin developer menggunakan *Git Pre-commit Hook*. Skrip ini memblokir proses *commit* jika terdapat pelanggaran kode atau file konfigurasi ilegal.

Simpan skrip ini di `.git/hooks/pre-commit` dan berikan izin eksekusi (`chmod +x .git/hooks/pre-commit`).

```bash
#!/usr/bin/env bash
# ==============================================================================
# Git Pre-commit Hook: Local Quality Gate & Secret Leak Protection
# ==============================================================================
set -euo pipefail

echo "==> [Pre-commit] Memulai validasi kualitas kode lokal..."

# 1. Cek apakah ada private key atau token yang tidak sengaja ter-stage
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM)

if [ -z "$STAGED_FILES" ]; then
    echo "==> [Pre-commit] Tidak ada file yang di-stage. Melewati pengujian."
    exit 0
fi

# Cek kebocoran file sensitif
for FILE in $STAGED_FILES; do
    if [[ "$FILE" =~ \.(pem|key|env|pfx)$ ]]; then
        echo "ERROR: Upaya commit file sensitif terdeteksi: $FILE" >&2
        echo "Tindakan: Batalkan stage file ini dan tambahkan ke .gitignore." >&2
        exit 1
    fi
done

# 2. Validasi format sintaks shell script (jika ada file shell script)
for FILE in $STAGED_FILES; do
    if [[ "$FILE" =~ \.sh$ ]] && [ -f "$FILE" ]; then
        if command -v shellcheck >/dev/null 2>&1; then
            echo "--> Memeriksa $FILE dengan shellcheck..."
            shellcheck "$FILE"
        else
            echo "WARNING: shellcheck tidak ditemukan. Lewati verifikasi shell."
        fi
    fi
done

echo "==> [Pre-commit] Semua validasi lolos. Melanjutkan commit."
exit 0
```

---

### 9. Step-by-Step Implementation Walkthrough
Untuk membangun ekosistem DevOps dasar dari status nol:

1.  **Sentralisasi Version Control:** Seluruh aset rekayasa wajib berada di Git. Ini mencakup kode aplikasi, skrip infrastruktur, skrip database, manifest Kubernetes, dan pipeline definitions.
2.  **Definisikan Strategi Branching:** Terapkan model sederhana seperti *Trunk-Based Development* untuk mencegah integrasi branch yang menumpuk lama (*long-lived branches*).
3.  **Terapkan Continuous Integration (CI):**
    *   Buat file definisi pipeline yang dieksekusi setiap ada `Pull Request` (PR).
    *   Jalankan pemeriksaan statis (*linter* dan *type check*).
    *   Jalankan *unit test suite*.
    *   Tolak PR jika pipeline gagal (*Required Status Checks*).
4.  **Standarisasi Lingkungan Eksekusi Menggunakan Kontainer:**
    *   Buat `Dockerfile` yang merefleksikan runtime identik dari dev hingga production.
    *   Gunakan teknik *multi-stage builds* untuk meminimalkan ukuran image.
5.  **Bangun Delivery Pipeline Otomatis:**
    *   Bangun image container dan berikan tag berupa hash commit Git yang unik (bukan tag `:latest`).
    *   Deploy image tersebut ke staging environment secara otomatis setelah integrasi branch utama (`main`).

---

### 10. Production-Grade / Practical Example
Berikut adalah implementasi pipeline CI/CD produksi menggunakan **GitHub Actions** untuk aplikasi berbasis Go/Node yang mematuhi prinsip *Build Once, Deploy Anywhere*, keamanan terintegrasi, dan pencegahan *artifact tampering*.

Simpan sebagai `.github/workflows/production-pipeline.yml`:

```yaml
name: Production Quality Gate & Delivery Engine

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

permissions:
  contents: read
  security-events: write

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  code-hygiene-and-test:
    name: Code Hygiene & Automated Testing
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Go runtime
        uses: actions/setup-go@v5
        with:
          go-version: '1.22'
          check-latest: true

      - name: Run Dependency Vulnerability Check
        run: |
          go install golang.org/x/vuln/cmd/govulncheck@latest
          govulncheck ./...

      - name: Execute Unit and Race Detection Tests
        run: |
          go test -v -race -coverprofile=coverage.txt -covermode=atomic ./...

      - name: Upload Test Coverage
        uses: actions/upload-artifact@v4
        with:
          name: test-coverage-report
          path: coverage.txt
          retention-days: 7

  container-build-and-security:
    name: Build & Scan Immutable Container
    needs: [code-hygiene-and-test]
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Container Image Locally for Scanning
        uses: docker/build-push-action@v5
        with:
          context: .
          load: true
          tags: internal-app:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Run Trivy Vulnerability Scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: internal-app:${{ github.sha }}
          format: 'table'
          exit-code: '1' # Membatalkan build jika ditemukan vulnerability HIGH atau CRITICAL
          ignore-unfixed: true
          vuln-type: 'os,library'
          severity: 'CRITICAL,HIGH'

  deploy-staging:
    name: Continuous Deployment to Staging
    needs: [container-build-and-security]
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment:
      name: staging
      url: https://staging.internal.domain
    steps:
      - name: Check out deployment manifest
        uses: actions/checkout@v4

      - name: Trigger Rolling Deployment (Mock)
        run: |
          echo "Deploying Artifact Tag: ${{ github.sha }} to Staging"
          # Di lingkungan nyata, integrasikan dengan k8s deployment/GitOps sync repo
          # kubectl set image deployment/app app=registry.domain/app:${{ github.sha }}
```

---

### 11. Edge Cases, Failure Modes & Antipatterns

| Antipattern | Mekanisme Kegagalan | Solusi Rekayasa |
| :--- | :--- | :--- |
| **"DevOps Silo" (DevOps Team Anti-pattern)** | Membentuk tim "DevOps" baru yang duduk di antara Dev dan Ops. Menghasilkan *dua* dinding friksi baru, bukan meruntuhkannya. | Ubah peran tim DevOps menjadi **Platform Engineering** yang menyediakan alat bantu swalayan (*internal developer platform*). |
| **Flaky Tests in CI** | Test suite yang terkadang berhasil, terkadang gagal tanpa perubahan kode. Menyebabkan developer mengabaikan kegagalan pipeline (*alert fatigue*). | Karantina tes yang *flaky*, jadikan kegagalan CI sebagai prioritas P0, dan implementasikan pengujian terisolasi bebas dependensi eksternal. |
| **Waterfall CI/CD** | Pipeline yang membutuhkan waktu berjam-jam (misal > 60 menit) karena mengeksekusi semua tes end-to-end yang lambat pada setiap *commit*. | Pisahkan tes: jalankan unit test secara cepat di PR (<5 menit). Jadwalkan tes integrasi/E2E berat secara asinkron atau berkala. |
| **Configuration Drift** | Server diubah manual melalui koneksi SSH saat *incident emergency*, membuat kode repositori tidak sinkron dengan sistem live. | Cabut akses SSH langsung ke server produksi. Terapkan prinsip bahwa semua perubahan runtime wajib melalui pipeline git (*GitOps*). |

---

### 12. Performance & Optimization Considerations
Untuk mempertahankan metrik DORA yang optimal, durasi eksekusi pipeline CI/CD harus ditekan:
*   **Docker Layer Caching:** Urutkan instruksi `Dockerfile` dari yang paling jarang berubah (instalasi OS dependency) ke yang paling sering berubah (kode sumber aplikasi).
*   **CI Engine Caching:** Manfaatkan dependensi caching lokal (seperti `actions/cache` untuk folder `node_modules` atau `~/.cache/go-build`).
*   **Parallel Execution:** Bagi pengujian menjadi *test shards* yang berjalan paralel di beberapa runner terpisah.
*   **Target Metrik Pipeline:** Feedback loop CI lokal harus selesai di bawah 3 menit; pipeline deployment staging penuh tidak boleh melebihi 10 menit.

---

### 13. Security & Compliance Implications (DevSecOps)
*   **Shift-Left Security:** Analisis keamanan diimplementasikan pada tahap awal, bukan sebagai audit manual di akhir kuartal.
*   **Static Application Security Testing (SAST):** Analisis kerentanan langsung pada *source code* (misal: injeksi SQL, input sanitization).
*   **Software Bill of Materials (SBOM):** Pembuatan daftar manifes seluruh pustaka pihak ketiga yang digunakan untuk menanggulangi kerentanan supply chain (seperti kasus Log4Shell).
*   **Secrets Detection:** Implementasi proteksi pada Git hook dan CI pipeline untuk mendeteksi token AWS, API keys, atau credential yang tidak sengaja tertulis pada kode (*trufflehog*, *gitleaks*).

---

### 14. Trade-offs & Alternatives

| Pendekatan | Keuntungan | Kerugian | Konteks Penggunaan |
| :--- | :--- | :--- | :--- |
| **Trunk-Based Development** | Mengeliminasi *merge hell*, integrasi terjadi setiap hari, feedback sangat cepat. | Butuh disiplin tinggi dan *Feature Flags* agar kode setengah matang tidak merusak sistem. | Tim dengan otomatisasi testing matang dan deployment frekuensi tinggi. |
| **GitFlow** | Struktur branch kaku (`release/*`, `hotfix/*`), isolasi fitur lebih teratur. | Lead Time tinggi, risiko *merge conflict* masif, memperlambat DORA LTFC. | Sistem legacy dengan jadwal rilis terjadwal (misal perangkat lunak on-premise embedded). |
| **In-House CI vs Managed SaaS** | Kontrol penuh atas sekuriti data dan biaya compute pipeline skala besar. | Beban pemeliharaan infrastruktur runner tinggi (*toil* bagi tim platform). | Regulasi kepatuhan finansial tinggi (On-premise) vs Kecepatan iterasi startup (SaaS). |

---

### 15. Best Practices & Operational Rules
*   **Aturan 1 (Golden Rule of Build):** *Build artifact* hanya dilakukan tepat satu kali. Artefak yang sama harus dipromosikan dari Staging ke Production tanpa proses *rebuild* (hanya inject variabel lingkungan / config map).
*   **Aturan 2 (Zero Manual Changes):** Jangan pernah menjalankan perintah modifikasi langsung di server produksi via SSH. Jika perubahan tidak tercatat di repositori Git, perubahan tersebut dianggap ilegal.
*   **Aturan 3 (Fail-Fast CI):** Jalankan proses tercepat dan paling sering gagal terlebih dahulu: *Linter/Format Check -> Unit Test -> Security Scan -> Docker Build -> Integration Test*.
*   **Aturan 4 (Blameless Post-Mortem):** Kegagalan manusia adalah gejala dari desain sistem yang rapuh. Setiap kegagalan rilis harus menghasilkan evaluasi akar masalah (*Root Cause Analysis*) dan otomatisasi pencegahan baru, bukan teguran personal.

---

### 16. Verification & Testing Strategies
Untuk memvalidasi bahwa fondasi DevOps berfungsi dengan baik pada sistem rekayasa Anda, jalankan evaluasi berikut:

1.  **Smoke Testing Pipeline:**
    Uji apakah pipeline dapat mendeteksi kesalahan sintaks sederhana dan menghentikan proses rilis secara deterministik:
    ```bash
    # Buat branch uji coba
    git checkout -b test/pipeline-failure-check
    # Simulasikan syntax error sengaja
    echo "malformed syntax" >> ./main.go
    git commit -am "test: deliberate failure for CI"
    git push origin test/pipeline-failure-check
    # Verifikasi bahwa job CI Anda GAGAL dan menolak merge PR
    ```

2.  **Audit Metrik Deployment:**
    *   Hitung berapa lama waktu yang dibutuhkan dari `git merge main` hingga traffic dialihkan ke container baru.
    *   Jika waktu tunggu melebihi 15 menit, bedah komponen pipeline yang menjadi bottleneck menggunakan *flame graph* atau analisis dependensi CI step.

---

### 17. Real-World Troubleshooting Scenarios

#### Masalah: "Pipeline CI Lolos, Tapi Deployment di Staging Error 500"
*   **Gejala:** Pipeline GitHub Actions/GitLab CI berwarna hijau, tapi aplikasi *crash-looping* segera setelah menerima trafik di staging.
*   **Akar Masalah (Root Cause):** Dependensi implisit pada environment lokal. Aplikasi membaca variabel konfigurasi database yang ada di lingkungan build/test, namun konfigurasi tersebut absen di *runtime environment* staging (*environment variable mismatch*).
*   **Langkah Resolusi:**
    1.  Terapkan metodologi *Twelve-Factor App* (Factor III: Config).
    2.  Buat skema validasi konfigurasi saat aplikasi melakukan *bootstrapping* (gunakan *pydantic*, *zod*, atau *validator* struktural lainnya). Jika environment variable kritis tidak tersedia, buat aplikasi langsung melempar fatal exit dengan pesan eksplisit:
    ```go
    // Contoh pencegahan boot jika env tidak lengkap
    func checkConfig() {
        if os.Getenv("DATABASE_URL") == "" {
            log.Fatal("FATAL: DATABASE_URL environment variable is required")
        }
    }
    ```
    3.  Tambahkan langkah *Health Check Endpoint* (`/healthz`) pada pipeline deployment yang menunggu hingga kontainer merespons status `HTTP 200 OK` sebelum menyatakan deployment berhasil.

---

### 18. Hands-on Lab: Membangun CI Smoke Test Engine Sederhana
Tujuan: Membangun pipeline lokal berbasis CLI yang bertindak sebagai quality gate mandiri sebelum developer melakukan push ke repositori sentral.

#### Langkah 1: Buat Struktur Project
```bash
mkdir -p devops-lab-01/{src,scripts}
cd devops-lab-01
```

#### Langkah 2: Buat Skrip Aplikasi Sederhana (`src/app.py`)
```python
import sys

def add(a: int, b: int) -> int:
    return a + b

if __name__ == "__main__":
    if add(2, 3) != 5:
        print("CRITICAL: Logic failure")
        sys.exit(1)
    print("Application OK")
    sys.exit(0)
```

#### Langkah 3: Buat Unit Test (`src/test_app.py`)
```python
import unittest
from app import add

class TestMath(unittest.TestCase):
    def test_addition(self):
        self.assertEqual(add(10, 5), 15)

if __name__ == '__main__':
    unittest.main()
```

#### Langkah 4: Buat Verification Runner Script (`scripts/run-ci.sh`)
```bash
#!/usr/bin/env bash
set -e

echo "=== STAGE 1: Syntax Analysis ==="
python3 -m py_compile src/app.py src/test_app.py
echo "Status: PASSED"

echo "=== STAGE 2: Automated Testing ==="
python3 -m unittest discover -s src -p "test_*.py"
echo "Status: PASSED"

echo "=== STAGE 3: Build Verification ==="
python3 src/app.py
echo "Status: PASSED"

echo "=== ALL CHECKS PASSED: Sistem Siap di-deploy ==="
```

Uji eksekusi lokal:
```bash
chmod +x scripts/run-ci.sh
./scripts/run-ci.sh
```

---

### 19. Summary
*   DevOps adalah penyelarasan budaya, proses, dan teknologi untuk memecahkan friksi antara kecepatan pengembangan dan stabilitas operasional.
*   Framework **CAMS/CALMS** menyediakan landasan transformasi non-teknis dan teknis, sementara metrik **DORA** bertindak sebagai standar kuantitatif performa rekayasa sistem.
*   Konsep **Shift-Left** dan **Immutable Infrastructure** merupakan inti teknis untuk mengurangi *blast radius* dan meniadakan *configuration drift*.
*   Tim DevOps yang efektif berfokus pada pembangunan infrastruktur dan pipeline sebagai layanan internal (*Platform Engineering*), bukan menjadi silo baru yang menangani rilis secara manual.

---

### 20. Next Steps
Pada **Modul 02: Version Control System (Git) & Branching Strategies untuk CI/CD**, kita akan membedah secara mendalam:
*   Mekanisme internal Git: Directed Acyclic Graph (DAG), Objects, References, dan Blob storage.
*   Implementasi teknis *Trunk-Based Development* vs *Feature Branching*.
*   Strategi resolusi *merge conflict* pada skala ratusan engineer, serta arsitektur *Branch Protection Rules* untuk menjamin integritas pipeline.