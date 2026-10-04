# Bab 08: Production GitOps & Enterprise CI/CD Automation

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengoperasikan alur kerja GitOps tingkat enterprise untuk Terraform menggunakan pendekatan Pull Request (PR) automation (Atlantis) dan TACOs (Terraform Automation and Collaboration Software seperti Spacelift dan env0).
- Membangun pipeline CI/CD skala produksi dengan GitHub Actions Matrix untuk mengelola multi-environment (`dev`, `staging`, `prod`) secara terisolasi dan paralel.
- Membedakan implementasi teknis dan implikasi keamanan antara *Speculative Plans* (pre-merge PR validation) dan *Real Applies* (post-merge execution via OIDC).
- Membangun sistem *Drift Detection* otomatis berbasis cron pipeline untuk mendeteksi deviasi *out-of-band* antara state Terraform dan infrastruktur riil.
- Mengonfigurasi mekanisme *Role-based Approval Gates*, *concurrency locks*, dan *state protection* guna mencegah race condition pada perubahan infrastruktur kritis.

---

## 2. Prerequisite
Sebelum mempelajari modul ini, Anda harus memahami:
- Sintaksis dasar dan lanjutan Terraform HCL (Variables, Outputs, Modules, Backends).
- Konsep State Management (Remote State S3/GCS, State Locking dengan DynamoDB/Consul).
- Konsep dasar Git (Branching strategy, Pull Requests, Merge strategies, Webhooks).
- Dasar-dasar pipeline CI/CD (GitHub Actions workflow syntax, jobs, steps, environment secrets).
- Konsep Identity and Access Management (IAM) Cloud Provider, khususnya AWS IAM Roles dan OpenID Connect (OIDC) Federated Identity.

---

## 3. Concept
Dalam lingkungan enterprise, eksekusi perintah `terraform apply` langsung dari mesin lokal insinyur (laptop) adalah anti-pattern kritis yang melanggar prinsip *least privilege*, *traceability*, dan *immutability*. GitOps untuk Infrastructure as Code (IaC) memosisikan Git repository sebagai *single source of truth* definitif untuk seluruh status infrastruktur yang diinginkan (*desired state*).

Sistem GitOps mengotomatisasi siklus hidup eksekusi Terraform melalui webhook yang merespons aktivitas pada Git repository:
1. **Speculative Execution**: Ketika PR dibuka, pipeline memicu `terraform plan` non-destruktif dan mengunggah hasilnya sebagai komentar PR.
2. **Peer Review & Policy Enforcement**: Tim mereview perubahan visual HCL beserta kalkulasi biaya dan kepatuhan kebijakan (Open Policy Agent/Sentinel).
3. **Controlled Apply**: Eksekusi `terraform apply` dilakukan baik melalui bot komentar PR (`atlantis apply`) atau otomatis setelah PR di-merge ke branch utama melalui pipeline runner dengan otentikasi berbasis token kriptografis jangka pendek (OIDC), bukan kredensial permanen.

---

## 4. Why
Mengapa model eksekusi CI/CD dan GitOps ini mutlak diperlukan di tingkat enterprise?
- **Pemberantasan "Works on My Machine"**: Menghilangkan diskrepansi versi Terraform CLI, provider binary cache, dan environment variables lokal antar developer.
- **Auditability & Compliance (SOC2/ISO27001)**: Setiap perubahan pada infrastruktur terikat pada commit SHA, disetujui oleh minimal satu reviewer resmi, dan terekam di audit log Git serta CI runner.
- **Eliminasi Long-Lived Static Credentials**: Penggunaan CI/CD berbasis OIDC meniadakan kebutuhan menyimpan `AWS_ACCESS_KEY_ID` dan `AWS_SECRET_ACCESS_KEY` statis di secrets repository, memitigasi risiko kebocoran kredensial berizin tinggi.
- **Pencegahan State Inconsistency & Concurrency Collisions**: Sistem GitOps menyediakan antrean terkoordinasi (*queue locks*) per *working directory* atau workspace, mencegah dua pipeline memodifikasi state yang sama secara simultan.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 GitOps Platforms: Atlantis vs TACOs (Spacelift, env0)
Terdapat dua filosofi utama dalam GitOps Terraform:

```
+-----------------------------------------------------------------------------------+
|                        PILIHAN ARSITEKTUR GITOPS TERRAFORM                        |
+-------------------------------------+---------------------------------------------+
| Self-Hosted / PR-Centric (Atlantis) | Managed TACOs (Spacelift, env0, HCP TF)     |
+-------------------------------------+---------------------------------------------+
| * Berjalan di Kubernetes/VM sendiri | * Cloud SaaS / Private Worker Hybrid        |
| * Komunikasi via komentar PR Git    | * UI tersentralisasi & Webhook otomatis     |
| * State locking native via PR lock  | * Context sharing, Dynamic Worker Pools     |
| * Low cost, high operational burden | * Advanced RBAC, OPA built-in, Cost module  |
| * Perlu akses ingress untuk webhook | * Audit logging siap pakai, SOC2 compliant  |
+-------------------------------------+---------------------------------------------+
```

1. **Atlantis**: Aplikasi Go open-source mandiri yang mendengarkan webhook dari GitHub/GitLab. Developer berinteraksi via komentar:
   - `atlantis plan -d environments/production`
   - `atlantis apply -d environments/production`
   Atlantis mengunci direktori/workspace pada level PR sehingga PR lain tidak dapat memodifikasi path yang sama sampai PR pertama selesai di-merge atau lock dilepas.
2. **Spacelift**: Engine orkestrasi yang memperlakukan IaC sebagai directed acyclic graph (DAG). Spacelift mendukung dependensi antar-stack (Stack Dependencies), integrasi OPA native, dan *Private Runners* di VPC pengguna.
3. **env0**: Menekankan pada manajemen lingkungan ephemeral, *cost management/attribution* per PR, dan eksekusi custom pipeline (mendukung Terragrunt, Pulumi, shell scripting kustom secara native).

### 5.2 Speculative Plans vs Real Applies
- **Speculative Plan**: Eksekusi `terraform plan` terhadap kode cabang fitur (PR branch) yang dikombinasikan secara temporer dengan basis branch target (`merge ref`). Tujuannya adalah memprediksi mutasi infrastruktur tanpa menyimpan plan file biner ke backend permanen dan **tanpa** izin untuk mengubah infrastruktur nyata.
- **Real Apply**: Eksekusi `terraform apply <plan_artifact>` yang dijalankan pasca-merge atau setelah explicit approval. Menggunakan file plan biner yang dihasilkan dari step sebelumnya untuk menjamin idempotensi deterministik (*guaranteed execution plan*).

### 5.3 OIDC (OpenID Connect) Passwordless Authentication
Daripada menyimpan AWS Access Keys di GitHub Actions Secrets, GitHub Actions bertindak sebagai OIDC Identity Provider (IdP):
1. Runner GitHub Actions meminta OpenID Connect ID Token JWT bertanda tangan digital dari GitHub IdP.
2. Token JWT berisi klaim identitas (`aud`, `sub` seperti `repo:my-org/my-repo:ref:refs/heads/main`).
3. Runner menukar token ini ke AWS Security Token Service (STS) menggunakan `sts:AssumeRoleWithWebIdentity`.
4. AWS memvalidasi token dan menerbitkan temporary credentials (berlaku 15-60 menit) dengan cakupan IAM Role tertentu.

### 5.4 Drift Detection
Drift terjadi ketika seseorang melakukan modifikasi manual melalui Cloud Console atau API di luar kendali Terraform. Drift Detection diimplementasikan sebagai pipeline cron periodik (misal: setiap malam pukul 02:00 UTC):
1. Mengambil state terkini dari remote backend.
2. Mengeksekusi `terraform plan -detailed-exitcode -no-color`.
3. Menilai exit code:
   - `0`: Succeeded, diff kosong (tidak ada drift).
   - `1`: Error teknis / konfigurasi rusak.
   - `2`: Succeeded, terdapat diff infrastruktur (**Drift Terdeteksi**).
4. Jika exit code = `2`, pipeline mengirim alert ke Slack/PagerDuty atau membuat GitHub Issue otomatis.

---

## 6. How
Implementasi workflow GitOps enterprise mencakup:
1. **Konfigurasi Server Atlantis (`repos.yaml`)**: Mengatur project requirements, branch protection enforcement, dan custom workflow steps.
2. **Pembuatan Workflow GitHub Actions**: Menyiapkan pipeline matrix untuk `plan` saat PR dan `apply` saat commit masuk ke branch utama.
3. **Enforcement Environment Approval Rules**: Memanfaatkan GitHub Environments protection rules untuk approval manual sebelum step produksi dieksekusi.
4. **Implementasi Drift Cron**: Pipeline terjadwal dengan notifikasi webhook terarah.

---

## 7. Analogy
Bayangkan proses pengajuan rancang bangun arsitektur di dunia nyata:
- **Speculative Plan**: Cetak biru 3D yang diajukan oleh arsitek (developer) ke dinas tata kota (peer reviewer). Cetak biru ini menampilkan simulasi struktur bangunan baru tanpa merusak sebidang tanah pun.
- **Role-based Approval Gates**: Dinas tata kota dan dinas pemadam kebakaran wajib membubuhkan stempel tanda tangan basah di formulir perizinan sebelum ekskavator diizinkan masuk lokasi proyek.
- **Real Apply**: Kontraktor utama turun ke lapangan membawa salinan cetak biru berstempel resmi untuk mulai mengecor beton. Tidak ada perubahan desain yang boleh dilakukan di lapangan saat pengerjaan fisik berlangsung.
- **Drift Detection**: Inspektur kota yang datang patroli rutin setiap pekan. Jika ada pemilik toko yang menambah kanopi ilegal tanpa izin, inspektur mencatat pelanggaran tersebut dan menuntut agar kanopi dibongkar atau cetak biru resmi direvisi.

---

## 8. Diagram (ASCII)

```
           GITOPS WORKFLOW: PULL REQUEST CYCLE HINGGA PRODUCTION APPLY

+------------------+
| Developer Workst.|
| git push branch  |
+--------+---------+
         |
         v
+------------------+         Webhook        +-------------------------+
| GitHub/GitLab PR | ---------------------> | Atlantis / GHA Runner   |
| (Feature Branch) |                        | (Speculative Plan)      |
+------------------+                        +------------+------------+
         ^                                               |
         |                   Post Plan Comment           |
         +-----------------------------------------------+
         |
         v
+------------------+         Review Pass    +-------------------------+
| Security / Lead  | ---------------------> | PR Approved & Merged to |
| Code Review      |                        | main branch             |
+------------------+                        +------------+------------+
                                                         |
                                                         v
                                            +-------------------------+
                                            | Real Apply Job          |
                                            | (GHA / TACO Pipeline)   |
                                            +------------+------------+
                                                         |
                                                         v
                                            +-------------------------+
                                            | Environment Gate:       |
                                            | Production Manual Check |
                                            +------------+------------+
                                                         | Approved
                                                         v
                                            +-------------------------+
                                            | AWS STS (OIDC Auth)     |
                                            | Temporary Token Issued  |
                                            +------------+------------+
                                                         |
                                                         v
                                            +-------------------------+
                                            | terraform apply         |
                                            | -> Cloud Infrastructure |
                                            | -> Remote State Updated |
                                            +-------------------------+
```

---

## 9. Simple Example
Sebuah repository Atlantis sederhana memerlukan file konfigurasi repositori bernama `atlantis.yaml` pada root repository.

```yaml
# atlantis.yaml
version: 3
automerge: false
parallel_plan: true
parallel_apply: false
projects:
- name: staging-network
  dir: environments/staging
  workspace: default
  terraform_version: v1.8.0
  autoplan:
    when_modified: ["*.tf", "*.tfvars"]
    enabled: true
  apply_requirements: [approved, mergeable]

- name: production-network
  dir: environments/production
  workspace: default
  terraform_version: v1.8.0
  autoplan:
    when_modified: ["*.tf", "*.tfvars"]
    enabled: true
  apply_requirements: [approved, mergeable]
```

---

## 10. Practical Example (Konfigurasi CLI / Terraform / GitHub Actions)

### 10.1 GitHub Actions Matrix Pipeline untuk Multi-Environment
Di bawah ini adalah file workflow produksi GitHub Actions (`.github/workflows/terraform-matrix.yml`) yang menangani linting, speculative plans paralel di lingkungan non-prod dan prod, serta apply terkendali menggunakan environment gates.

```yaml
name: "Terraform Multi-Env Matrix CI/CD"

on:
  push:
    branches:
      - main
    paths:
      - "environments/**"
      - "modules/**"
  pull_request:
    branches:
      - main
    paths:
      - "environments/**"
      - "modules/**"

permissions:
  id-token: write # Diperlukan untuk OIDC AWS STS
  contents: read
  pull-requests: write # Diperlukan untuk posting komentar plan

jobs:
  matrix-plan:
    name: "Plan (${{ matrix.environment }})"
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        environment: [staging, production]
    defaults:
      run:
        working-directory: environments/${{ matrix.environment }}
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.8.0

      - name: Configure AWS Credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-actions-tf-${{ matrix.environment }}
          aws-region: ap-southeast-1

      - name: Terraform Init
        run: terraform init

      - name: Terraform Format Check
        run: terraform fmt -check

      - name: Terraform Validate
        run: terraform validate

      - name: Terraform Speculative Plan
        id: plan
        run: |
          terraform plan -no-color -out=tfplan-${{ matrix.environment }} > plan_output.txt
        continue-on-error: false

      - name: Archive Terraform Plan Artifact
        uses: actions/upload-artifact@v4
        with:
          name: tfplan-${{ matrix.environment }}
          path: environments/${{ matrix.environment }}/tfplan-${{ matrix.environment }}
          retention-days: 1

      - name: Comment Plan Output on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const planText = fs.readFileSync('environments/${{ matrix.environment }}/plan_output.txt', 'utf8');
            const maxChars = 60000;
            const truncatedPlan = planText.length > maxChars ? planText.substring(0, maxChars) + "\n...[TRUNCATED]" : planText;
            const output = `### Environment: \`${{ matrix.environment }}\` Plan Result
            #### Status: \`${{ steps.plan.outcome }}\`
            <details><summary>Tampilkan Execution Plan</summary>

            \`\`\`hcl
            ${truncatedPlan}
            \`\`\`

            </details>
            *Pusher: @${{ github.actor }}, Action: \`${{ github.event_name }}\`*`;

            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: output
            })

  apply-staging:
    name: "Apply (staging)"
    needs: [matrix-plan]
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    environment: staging
    defaults:
      run:
        working-directory: environments/staging
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.8.0

      - name: Download Plan Artifact
        uses: actions/download-artifact@v4
        with:
          name: tfplan-staging
          path: environments/staging

      - name: Configure AWS Credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-actions-tf-staging
          aws-region: ap-southeast-1

      - name: Terraform Init
        run: terraform init

      - name: Terraform Real Apply
        run: terraform apply -auto-approve tfplan-staging

  apply-production:
    name: "Apply (production)"
    needs: [apply-staging]
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    environment: production # Mengharuskan manual approval di repo Settings -> Environments
    defaults:
      run:
        working-directory: environments/production
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.8.0

      - name: Download Plan Artifact
        uses: actions/download-artifact@v4
        with:
          name: tfplan-production
          path: environments/production

      - name: Configure AWS Credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-actions-tf-production
          aws-region: ap-southeast-1

      - name: Terraform Init
        run: terraform init

      - name: Terraform Real Apply
        run: terraform apply -auto-approve tfplan-production
```

### 10.2 Drift Detection Pipeline (`.github/workflows/drift-detection.yml`)
Workflow cron harian untuk mendeteksi drift tanpa mengubah infrastruktur.

```yaml
name: "Scheduled Drift Detection"

on:
  schedule:
    # Berjalan setiap hari pada pukul 02:00 UTC (09:00 WIB)
    - cron: "0 2 * * *"
  workflow_dispatch: # Memungkinkan eksekusi manual via dashboard GitHub

permissions:
  id-token: write
  contents: read
  issues: write

jobs:
  detect-drift:
    name: "Drift Scan (${{ matrix.env }})"
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        env: [staging, production]
    defaults:
      run:
        working-directory: environments/${{ matrix.env }}
    steps:
      - name: Checkout Source
        uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.8.0

      - name: Configure AWS Credentials via OIDC
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-actions-tf-${{ matrix.env }}
          aws-region: ap-southeast-1

      - name: Terraform Init
        run: terraform init

      - name: Check for Drift
        id: drift_check
        run: |
          set +e
          terraform plan -detailed-exitcode -no-color > drift_report.txt
          EXIT_CODE=$?
          echo "exit_code=$EXIT_CODE" >> $GITHUB_OUTPUT
          set -e

          if [ $EXIT_CODE -eq 0 ]; then
            echo "Status: Tidak ada drift. State sinkron dengan real world."
          elif [ $EXIT_CODE -eq 2 ]; then
            echo "Status: DRIFT TERDETEKSI! Terdapat perubahan out-of-band."
          else
            echo "Status: Terraform Plan mengalami error eksekusi teknis."
            exit $EXIT_CODE
          fi

      - name: File GitHub Issue if Drift Detected
        if: steps.drift_check.outputs.exit_code == '2'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const driftBody = fs.readFileSync('environments/${{ matrix.env }}/drift_report.txt', 'utf8');
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: `[ALERT] Drift Terdeteksi pada Environment: ${{ matrix.env }}`,
              body: `Drift terdeteksi pada eksekusi audit harian.\n\n\`\`\`hcl\n${driftBody.substring(0, 60000)}\n\`\`\``
            });
```

---

## 11. Real World Example
Sebuah bank digital di Asia Tenggara mengelola 45 microservices yang masing-masing memiliki modul database Amazon Aurora dan cache Redis.

### Arsitektur yang Diterapkan:
1. **GitHub Enterprise Server + Self-hosted Runners**: GitHub runner ditempatkan di private VPC tanpa access key permanen.
2. **Atlantis untuk Pull Requests**: Developer memvalidasi parameter sizing RDS langsung di komentar PR. Atlantis bertindak sebagai gerbang pertama untuk memastikan modul memenuhi batasan ukuran instance.
3. **Open Policy Agent (OPA) Conftest Step**: Sebelum plan lolos, OPA memeriksa apakah parameter `storage_encrypted` bernilai `true` dan `backup_retention_period >= 7`.
4. **Staging Auto-Apply, Prod Gated Apply**: Ketika PR di-merge ke branch `main`:
   - Environment `staging` segera menjalankan apply.
   - Environment `production` memicu notifikasi ke Slack channel `#infra-change-approval`. Dua orang Senior Staff SRE wajib mengklik tombol **Review deployments** di GitHub sebelum eksekusi apply dilakukan.

---

## 12. Trade-offs

| Aspek | PR-Driven Automation (Atlantis) | CI/CD Matrix Pipeline (GitHub Actions) | Enterprise TACOs (Spacelift/env0) |
|---|---|---|---|
| **Biaya Lisensi** | Gratis (Open Source) | Sesuai runner minutes GitHub | Mahal (Berbasis User / Concurrency / Run) |
| **Operasional Overhead** | Tinggi (Host, update, scaling container Atlantis sendiri) | Nol (Managed Runner) atau Rendah (Self-hosted) | Rendah (Managed Control Plane) |
| **State Locking** | Level PR / Workspace interaktif via komentar | Dikelola native oleh backend Terraform (DynamoDB) | Terkelola terpusat dengan antrean run canggih |
| **Kebijakan & Governance**| Perlu integrasi custom bash / hook | Menggunakan workflow step terpisah | Native integration (OPA, Rego, Guardrails) |
| **Keamanan Kredensial** | Server Atlantis memegang IAM roles untuk semua env | OIDC granular per environment/job | OIDC atau granular STS per worker pool |

---

## 13. When To Use
Gunakan arsitektur GitOps dan Enterprise CI/CD ini ketika:
- Anggota tim engineering yang berinteraksi dengan IaC berjumlah lebih dari 3 orang.
- Organisasi wajib mematuhi standar kepatuhan regulasi finansial atau privasi data (PCI-DSS, SOC2, HIPAA).
- Terdapat multi-tier infrastructure lifecycle (`staging` -> `production`) yang membutuhkan jaminan dependensi antar layer.
- Tim SRE membutuhkan visibilitas absolut atas perubahan resource sebelum dieksekusi ke cloud.

---

## 14. When NOT To Use
Hindari kompleksitas pipeline ini jika:
- Anda sedang melakukan *rapid prototyping / Proof-of-Concept (PoC)* mandiri yang dibuang dalam waktu 24 jam.
- Infrastruktur sepenuhnya lokal (misalnya menggunakan Minikube atau Vagrant) tanpa target shared remote state.
- Tidak ada anggota tim teknis yang memiliki kapabilitas memelihara OIDC trust relationship dan webhook security.

---

## 15. Common Mistakes
1. **Apply Berdasarkan Source Code, Bukan Plan File**:
   *Kesalahan*: Menjalankan `terraform apply -auto-approve` langsung di main branch tanpa menyuplai artifak plan binary dari step PR.
   *Dampak*: Jika seseorang melakukan merge lain di saat bersamaan, apa yang di-apply di production bisa berbeda signifikan dari apa yang direview di PR.
2. **Kredensial Statis Permanen di Secrets**:
   *Kesalahan*: Mengisi `AWS_SECRET_ACCESS_KEY` di repo secret.
   *Dampak*: Kredensial tidak pernah dirotasi dan jika runner bocor, cloud target terekspos tanpa jejak identitas runner spesifik.
3. **Tidak Menangani Concurrency Race Condition**:
   *Kesalahan*: Mengizinkan dua workflow GitHub Actions berjalan bersamaan pada branch yang sama untuk modul yang sama tanpa mekanisme lock/concurrency group.
   *Dampak*: Terjadi kegagalan Terraform State Lock (`Error acquiring the state lock`).
4. **Mengabaikan Plan Exit Code**:
   *Kesalahan*: Menganggap exit code `2` pada drift detection sebagai error teknis pipeline.
   *Dampak*: Pipeline ditandai failed/broken, padahal exit code `2` berarti plan sukses dan drift terdeteksi.

---

## 16. Best Practices
- **Manfaatkan Concurrency Groups di GitHub Actions**:
  ```yaml
  concurrency:
    group: terraform-${{ matrix.environment }}
    cancel-in-progress: false # Jangan batalkan apply yang sedang berjalan!
  ```
- **Simpan Plan Binary Secara Terenkripsi**:
  File plan Terraform mengandung nilai plaintext dari variabel sensitive. Pastikan retention time artifact seminimal mungkin (misal: 1 hari) dan permission runner dibatasi ketat.
- **Terapkan Branch Protection Rules**:
  Branch `main` wajib:
  - Require status checks to pass before merging (`matrix-plan`).
  - Require branches to be up to date before merging.
  - Require signed commits.
  - Require pull request reviews (minimal 1 approved review dari tim SRE/DevOps).

---

## 17. Troubleshooting
1. **Error: `Invalid Identity Token (OIDC)` pada AWS STS**:
   - *Penyebab*: Sub claim pada IAM Role Trust Policy tidak cocok dengan repository atau branch.
   - *Solusi*: Verifikasi Trust Policy IAM Role. Pastikan format StringEquals sesuai:
     ```json
     "token.actions.githubusercontent.com:sub": "repo:<org>/<repo>:ref:refs/heads/main"
     ```
2. **Error acquiring the state lock**:
   - *Penyebab*: Pipeline sebelumnya terputus secara mendadak atau ada engineer yang menjalankan plan lokal tanpa melepaskan lock DynamoDB.
   - *Solusi*: Ambil Lock ID dari error log, validasi tidak ada proses aktif lain, kemudian jalankan `terraform force-unlock <LOCK-ID>`.
3. **Plan Comments Truncated / Gagal Diposting ke PR**:
   - *Penyebab*: GitHub REST API memiliki batas maksimal payload body komentar (65.536 karakter).
   - *Solusi*: Lakukan slicing string output maksimal 60.000 karakter dan sertakan artefak log lengkap via job upload.

---

## 18. Exercise
1. Buat branch baru dari template repositori infrastruktur Anda.
2. Tambahkan tag baru pada sebuah modul (misal `Environment = "audit-test"`).
3. Buat PR, periksa apakah workflow Speculative Plan berhasil memicu dan mencetak perbedaan HCL ke komentar PR Anda.
4. Lakukan modifikasi out-of-band via AWS CLI (misal mengubah description sebuah Security Group). Jalankan workflow drift detection manual (`workflow_dispatch`) dan amati apakah issue baru berhasil dibuat di repositori Anda.

---

## 19. Challenge
Rancang arsitektur pipeline GitHub Actions yang memvalidasi biaya infrastruktur sebelum approval diberikan:
- Integrasikan binary `infracost` di antara step `terraform plan` dan posting komentar PR.
- Atur condition rule: Jika estimasi kenaikan biaya bulanan infrastruktur melebihi $500 USD, pipeline wajib secara otomatis menambahkan label `high-cost-impact` pada PR dan memerlukan *review approval* tambahan dari user dengan role FinOps.

---

## 20. Summary
- GitOps pada Terraform mengubah Git repository menjadi single control plane deterministik untuk seluruh lifecycle infrastruktur.
- Speculative Plans menjamin visibilitas risiko perubahan tanpa modifikasi infrastruktur, sedangkan Real Apply pasca-merge menjamin idempotensi eksekusi berbasis artefak.
- Penggunaan AWS OIDC mengeliminasi risiko kebocoran static token credential di pipeline CI/CD.
- Drift detection periodik adalah komponen vital GitOps untuk menangkap dan merekonsiliasi perubahan out-of-band yang merusak keandalan Terraform State.