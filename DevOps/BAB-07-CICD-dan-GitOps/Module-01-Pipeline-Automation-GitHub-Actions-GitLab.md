# Module 01: Automated Pipeline dengan GitHub Actions & GitLab CI

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar akan mampu:
1. Memahami perbedaan fundamental antara **Continuous Integration (CI)**, **Continuous Delivery (CD)**, dan **Continuous Deployment**.
2. Merancang alur kerja pipeline otomatis (*Automated Workflows*) menggunakan event triggers, matrix builds, dan dependencies (`needs`).
3. Mengamankan kredensial pipeline menggunakan **OIDC (OpenID Connect)** tanpa menyimpan static long-lived cloud keys.
4. Mengoptimalkan kecepatan build melalui strategi artifact caching, dependency pinning, dan self-hosted vs cloud-hosted runners.

---

## 2. Prerequisite
- Memahami alur kerja Git (branching, commits, pull requests, semantic tags).
- Memahami build image Docker dari [BAB 03 Module 02](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-03-Containerization-Docker/Module-02-Optimasi-Dockerfile-Multi-Stage-Volume-Compose.md).

---

## 3. Concept
Sebelum era CI/CD, merilis software ke production adalah mimpi buruk (*Integration Hell*):
- Developer menggabungkan cabang kode yang sudah berumur 2 bulan secara manual.
- Software di-test manual oleh tim QA selama 1 minggu.
- Di hari rilis (biasanya Jumat malam), SysAdmin menyalin file zip via FTP/SSH langsung ke server. Jika terjadi bug, rollback memakan waktu berjam-jam.

**CI/CD Pipeline** mengubah proses manual yang rapuh ini menjadi **jalur perakitan pabrik otomatis (*Automated Assembly Line*)**:
- **Continuous Integration (CI)**: Setiap kali developer melakukan `git push` atau membuat Pull Request, pipeline otomatis menyalakan runner virtual, mengompilasi kode, menjalankan linter, dan mengeksekusi ratusan unit test dalam hitungan detik. Jika 1 test gagal, PR tidak boleh di-merge.
- **Continuous Delivery (CD)**: Setelah kode lolos uji di branch `main`, pipeline otomatis membangun Docker image, memindai celah keamanan, dan men-deploy ke environment Staging, siap dirilis ke Production dengan satu klik persetujuan.
- **Continuous Deployment**: Langkah rilis ke Production dilakukan 100% otomatis tanpa campur tangan manusia jika seluruh test lulus.

---

## 4. Why?
Mengapa CI/CD adalah jantung dari filosofi DevOps?
1. **Kecepatan Inovasi (Deployment Frequency)**: Perusahaan dapat merilis fitur baru puluhan kali per hari dengan percaya diri, bukan lagi 3 bulan sekali.
2. **Pendeteksian Dini Cacat (Shift-Left Testing)**: Bug ditemukan 5 menit setelah kode ditulis oleh developer di laptopnya, bukan 3 minggu kemudian setelah dirilis ke pelanggan.
3. **Keterlacakan & Auditabilitas**: Setiap rilis di server production terikat langsung dengan nomor Git Commit SHA yang spesifik.

---

## 5. What?
Komponen penting dalam GitHub Actions & GitLab CI:
- **Workflows / Pipelines**: Definisi otomasi dalam format YAML (`.github/workflows/*.yml` atau `.gitlab-ci.yml`).
- **Events / Triggers**: Pemicu eksekusi (contoh: `push`, `pull_request`, `release`, `schedule / cron`).
- **Jobs & Stages**: Kumpulan langkah yang berjalan di mesin virtual terpisah. Secara default berjalan paralel, atau sekuensial menggunakan `needs: [test, lint]`.
- **Runners**: Mesin eksekutor tempat script dijalankan (GitHub-Hosted Runners seperti `ubuntu-latest` atau Self-Hosted Runners di VPS sendiri).
- **Artifacts & Caching**: Menyimpan artefak hasil build antar-job dan meng-cache direktori dependensi (`~/.npm`, `~/.m2`).

---

## 6. How?
Alur kerja tipikal sebuah Enterprise CI/CD Pipeline:

```text
[ Developer Push Commit ke Branch "feature/payment" ]
                          │
                          ▼
            [ STAGE 1: CODE INTEGRITY ]
        ├── Job: Linting (ESLint / Flake8)
        ├── Job: Secret Scan (Gitleaks)
        └── Job: Unit Tests (Jest / PyTest / Go Test)
                          │
                   (Lulus Semua?)
                          │
                          ▼
            [ STAGE 2: CONTAINER PACKAGING ]
        ├── Job: Docker Multi-Stage Build
        ├── Job: Security Scan Image (Trivy CVE Checker)
        └── Job: Push ke Container Registry (ECR / GHCR / Harbor)
                          │
                          ▼
            [ STAGE 3: ENVIRONMENT DELIVERY ]
        ├── Deploy ke Staging Environment (Otomatis)
        ├── Run End-to-End Integration Tests
        └── Deploy ke Production Environment (Manual Approval / Auto-deploy)
```

---

## 7. Analogy
Bayangkan **CI/CD Pipeline** seperti **Jalur Perakitan Mobil di Pabrik Otomotif**:
- Pekerja (Developer) memasang pintu mobil baru (menulis kode).
- Sebelum mobil meluncur ke jalan raya, mobil melewati stasiun otomatis:
  - *Stasiun 1 (Linting)*: Sensor mengukur apakah engsel pintu terpasang lurus.
  - *Stasiun 2 (Crash Test / Unit Tests)*: Pintu dibanting 100 kali untuk memastikan tidak copot.
  - *Stasiun 3 (Cat & Pelindung Karat / Docker Packaging)*: Mobil disemprot cat pelindung.
- Jika ada 1 baut yang kendor di stasiun manapun, ban berjalan seketika berhenti (*Pipeline Red/Fail*). Mobil cacat tidak akan pernah sampai ke dealer (*Production*).

---

## 8. Diagram
```text
+-------------------------------------------------------------+
|                      GITHUB REPOSITORY                      |
+-------------------------------------------------------------+
           |
           | git push (Event: pull_request)
           v
+-------------------------------------------------------------+
|                     RUNNER VIRTUAL MACHINE                  |
|                                                             |
|  [ Job 1: Test & Lint ] ──(Success)──> [ Job 2: Build OCI ] |
|  - npm test                            - docker build       |
|  - trivy fs .                          - docker push        |
+-------------------------------------------------------------+
                                                │
                                                | Push Image
                                                v
+-----------------------+          +--------------------------+
|  KUBERNETES CLUSTER   | <======  | CONTAINER REGISTRY (GHCR)|
|  (Deploy new version) |  (Pull)  |  myapp:sha-8f921ab       |
+-----------------------+          +--------------------------+
```

---

## 9. Simple Example
Workflow GitHub Actions lengkap (`.github/workflows/ci.yml`):

```yaml
name: CI/CD Production Pipeline

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    name: Unit Test & Security Scan
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'

      - name: Install Dependencies
        run: npm ci

      - name: Run Linter
        run: npm run lint

      - name: Run Unit Tests
        run: npm test -- --coverage

  build-and-push:
    name: Build & Push Docker Image
    needs: test # Hanya jalan jika job 'test' lulus!
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' # Hanya jalan di branch main
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: actions/setup-buildx-action@v3

      - name: Login to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build & Push Image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ghcr.io/${{ github.repository }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

---

## 10. Practical Example
Penggunaan OIDC (*OpenID Connect*) untuk autentikasi ke cloud tanpa menyimpan API key statis:

```yaml
# Mengizinkan GitHub Runner menukar token OIDC dengan IAM Role AWS
permissions:
  id-token: write # Wajib untuk OIDC
  contents: read

steps:
  - name: Configure AWS Credentials via OIDC
    uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: arn:aws:iam::123456789012:role/GitHubActionsDeployerRole
      aws-region: ap-southeast-1
```
*Dengan OIDC, tidak ada lagi `AWS_ACCESS_KEY_ID` berumur panjang yang berisiko bocor!*

---

## 11. Real World Example
### Kasus: Kebocoran AWS Key Akibat Hardcoded Secrets di Log CI/CD
1. Seorang developer menulis command debugging di pipeline: `env` atau `printenv` untuk melihat variabel runner.
2. Output log mencetak seluruh `AWS_SECRET_ACCESS_KEY`.
3. Repository tersebut bersifat public open-source, dan log build dapat dibaca siapa saja di internet.
4. Bot penambang kripto mendeteksi key tersebut dalam waktu 90 detik, membuat 50 instance EC2 GPU besar, dan menghasilkan tagihan $12.000 dalam 4 jam.
5. **Solusi SRE**:
   - Ganti seluruh autentikasi static access key dengan **OIDC Federated Identity**.
   - Gunakan secret scanner (seperti Gitleaks atau Trufflehog) di step awal pipeline untuk membatalkan build jika ada token yang tidak sengaja tercetak.

---

## 12. Trade-offs
| Tipe Runner | Cloud-Hosted Runners (GitHub / GitLab SaaS) | Self-Hosted Runners (VPS / K8s Sendiri) |
|---|---|---|
| **Pemeliharaan** | Nol (Dikelola penuh oleh GitHub/GitLab) | Tinggi (Harus update OS, security patch, Docker) |
| **Keamanan** | Lingkungan sekali pakai bersih (*Ephemeral VM*) | Rentan cross-build contamination jika tidak di-sandbox |
| **Biaya** | Gratis kuota terbatas; berbayar per menit setelahnya | Biaya flat bulanan server VPS |
| **Akses Jaringan Privat** | Butuh VPN / IP allowlist untuk akses database internal | Berada langsung di dalam private VPC perusahaan |

---

## 13. When To Use
- Gunakan **GitHub Actions / GitLab CI**: Untuk setiap repository kode perangkat lunak, mulai dari library kecil hingga monorepo enterprise.
- Gunakan **Matrix Builds**: Saat perlu menguji aplikasi di beberapa versi runtime sekaligus (misal menguji library di Node 18, Node 20, dan Node 22).

---

## 14. When NOT To Use
- Jangan gunakan pipeline CI/CD aplikasi untuk menjalankan tugas backup database berdurasi 12 jam (gunakan cron/orchestration engine khusus seperti Airflow atau Systemd timers).

---

## 15. Common Mistakes
1. **Menyimpan Long-Lived Static Cloud Keys**: Menyimpan AWS Root Access Key di GitHub Secrets alih-alih menggunakan OIDC role assumption.
2. **Tidak Mengunci Action Version (Dependency Pinning)**: Menggunakan `uses: actions/checkout@main` alih-alih tag versi `v4` atau SHA commit hash. Jika maintainer action tersebut diretas, script berbahaya dapat disuntikkan ke pipeline Anda (*Supply Chain Attack*).
3. **Mengabaikan Cache Invalidation**: Meng-cache folder `node_modules` tanpa menyertakan hash dari `package-lock.json` sebagai cache key, menyebabkan dependensi baru gagal terinstal.

---

## 16. Best Practices
### Must Have
- Selalu pisahkan job `test` dan job `deploy` menggunakan `needs: [test]`.
- Kunci versi GitHub Actions menggunakan SHA komit atau versi rilis spesifik (`actions/checkout@v4`).
- Terapkan OIDC untuk seluruh komunikasi pipeline ke cloud provider (AWS, GCP, Azure).

### Recommended
- Gunakan Docker Buildx dengan cache engine GitHub Actions (`type=gha`) untuk mempercepat build image.
- Batasi permission token pipeline seminimal mungkin (`permissions: contents: read`).

### Avoid / Overengineering
- Jangan menjalankan pipeline CI penuh (termasuk e2e test 30 menit) pada setiap kali developer mengetik draf commit; jalankan test berat hanya saat PR dibuka atau di-merge ke branch utama.

---

## 17. Troubleshooting
| Gejala | Kemungkinan Penyebab | Solusi |
|---|---|---|
| Pipeline gagal: `npm: command not found` | Step setup runtime belum dijalankan sebelum perintah | Tambahkan step `actions/setup-node` sebelum step `run: npm` |
| Docker build gagal: `no space left on device` di runner | Ukuran image atau cache builder melebihi kuota disk runner (14GB di GitHub) | Hapus toolchain yang tidak terpakai (Android SDK, .NET) di awal workflow |
| Job deploy berjalan padahal unit test gagal | Parameter `needs:` tidak didefinisikan sehingga semua job berjalan paralel | Tambahkan `needs: [test]` pada job deployment |

---

## 18. Exercise
1. Buat file `.github/workflows/lint.yml` sederhana yang mengecek format kode menggunakan linter.
2. Konfigurasikan cache dependensi agar step install tidak mengunduh paket ulang jika lockfile tidak berubah.

---

## 19. Challenge
Rancang arsitektur simulasi **CI/CD Pipeline Engine**:
- Simulasikan engine yang menerima DAG Jobs (Lint -> Test -> Docker Build -> Deploy).
- Jika Job Test gagal (exit code non-zero), gagalkan seluruh pipeline dan pastikan Job Deploy **tidak pernah dieksekusi**.
- Hitung metrik durasi waktu eksekusi setiap stage.

---

## 20. Summary
- CI/CD mengotomatiskan siklus pengujian dan rilis kode dari commit lokal hingga server production.
- Keamanan pipeline wajib ditegakkan menggunakan OIDC, dependency pinning, dan scanning celah keamanan container.
- Pipeline yang cepat dan andal adalah kunci utama produktivitas tim software engineering modern.
- Modul praktikum lab dapat dijalankan langsung di [hands-on/m01/cicd_pipeline_runner.js](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-07-CICD-dan-GitOps/hands-on/m01/cicd_pipeline_runner.js).
