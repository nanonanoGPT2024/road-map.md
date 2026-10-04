# BAB 08: Production GitOps dan Enterprise CI/CD Automation
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Mengimplementasikan Arsitektur GitOps Enterprise** untuk Terraform menggunakan pola *pull-based* (Atlantis/Flux/Spacelift) vs *push-based* (GitHub Actions/GitLab CI dengan OIDC federation).
- **Mengeliminasi Kredensial Statis (Zero Long-Lived Credentials)** melalui integrasi OpenID Connect (OIDC) ke AWS IAM, Azure Active Directory, atau GCP Workload Identity Federation.
- **Mengorkestrasi State Locking & Concurrency Management** pada repositori multi-lingkungan dan monorepo skala ribuan *workspace* tanpa menimbulkan *deadlock* atau *race condition*.
- **Membangun Pipeline Automated Shift-Left Security & Policy-as-Code** menggunakan Open Policy Agent (OPA/Rego) atau HashiCorp Sentinel untuk validasi *blast radius*, biaya (*Infracost*), dan kerentanan (*Trivy*/*Checkov*) sebelum *apply*.
- **Mendesain Mekanisme Automated Drift Detection & Self-Healing** terjadwal yang mengisolasi anomali infrastruktur tanpa memicu gangguan pada beban kerja aktif.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib memahami:
- Konsep dasar Terraform: State management, modul, *backends* S3/DynamoDB atau GCS, dan *workspaces*.
- Pengoperasian Git lanjutan: Branching strategy (Trunk-based vs GitFlow), merge queue, Git hooks, dan Pull Request (PR) lifecycle.
- Pemahaman protokol identitas modern: OAuth 2.0 dan JSON Web Token (JWT) pada arsitektur OpenID Connect (OIDC).
- Dasar-dasar pipeline CI/CD: Runner/Agent architecture, secrets management, dan container runtime.

---

### 3. Concept & Internal Architecture

Implementasi Terraform pada skala enterprise tidak boleh mengandalkan eksekusi dari workstation lokal pengembang. Arsitektur produksi GitOps memusatkan eksekusi pada *execution engines* yang terisolasi, terorkestrasi, dan diaudit secara ketat.

```
                    ARARSITEKTUR GITOPS TERRAFORM ENTERPRISE (OIDC & RUNNER)

+------------------+         Pull Request          +-----------------------+
|  Engineer Work-  | ----------------------------> | VCS (GitHub / GitLab) |
|     station      |                               +-----------------------+
+------------------+                                      |         ^
                                   Webhook / Workflow Trigger       | Post PR Plan
                                                          v         | Comment
+-------------------------------------------------------------------+--------------------+
| CI/CD Runner / Atlantis Engine (Isolasi Jaringan VPC Privatis)                         |
|                                                                                        |
|  1. Lint & Format check (`terraform fmt`, `tflint`)                                    |
|  2. Security Scan (`checkov`, `trivy`)                                                 |
|  3. Cost Estimation (`infracost breakdown`)                                            |
|  4. OIDC Token Exchange:                                                               |
|     +------------------+       Exchange JWT       +----------------------+             |
|     | Runner Ephemeral | -----------------------> | Cloud IAM IdP (OIDC) |             |
|     |      Token       | <----------------------- | Assumed STS Role     |             |
|     +------------------+    Temporary Token (1h)  +----------------------+             |
|  5. Execution Engine:                                                                  |
|     `terraform plan -out=tfplan`                                                       |
|  6. Policy-as-Code Gate:                                                               |
|     `conftest test tfplan.json` (Validasi Blast Radius & Resource Limits)              |
+-------------------------------------------------------------------+--------------------+
                                                                    |
                                        PR Merge (Main Branch)      | Auto-apply / Approval
                                                                    v
+------------------+       Distributed Lock Check  +-------------------------------------+
| Remote State &   | <===========================> | Cloud Provider API Target           |
| Distributed Lock |   (State Locked via DynamoDB) | (AWS / GCP / Azure Resources)       |
+------------------+                               +-------------------------------------+
```

#### Komponen Inti Arsitektur Produksi:
1. **OIDC Federation Engine:** Menghilangkan `AWS_ACCESS_KEY_ID` dan `AWS_SECRET_ACCESS_KEY` dari *secret store* CI/CD. Runner meminta JWT token jangka pendek bertanda tangan digital dari VCS (GitHub/GitLab), lalu menukarkannya via AWS STS (`sts:AssumeRoleWithWebIdentity`) menjadi kredensial berdurasi 15–60 menit. Validasi ketat dilakukan pada *claims* token: `sub` (repository, branch, environment), `aud`, dan `iss`.
2. **State Concurrency & Mutex Management:** Pada monorepo berskala besar dengan ratusan *root modules*, eksekusi paralel dapat memicu konflik. Mesin GitOps mengisolasi eksekusi per direktori dengan mengunci *distributed lock* (DynamoDB/Consul) dan menerapkan *matrix builds* dengan *dependency DAG* terurut.
3. **Speculative Plan & Blast Radius Analytics:** Ketika PR dibuka, pipeline mengompilasi *speculative execution plan*. Plan ini dikonversi ke format JSON (`terraform show -json tfplan > tfplan.json`) untuk dianalisis oleh Policy-as-Code engine:
   - Menghitung rasio destruksi: `(delete_count) / (create_count + update_count + delete_count)`.
   - Menolak eksekusi otomatis jika penghapusan mencakup *stateful resources* (RDS, S3, IAM Roles sensitif) tanpa bypass manual multi-approver.
4. **Drift Detection Synchronization Loop:** Runner terjadwal mengeksekusi `terraform plan -detailed-exitcode -refresh-only` di luar jam sibuk. Exit code `2` menandakan adanya perubahan *out-of-band* (drift). Pipeline secara otomatis membuka *incident ticket* atau menginisiasi PR rekonsiliasi.

---

### 4. Why & What

| Dimensi | Pendekatan Tradisional (Local/Shared CI) | GitOps Enterprise (OIDC + Policy-as-Code) |
| :--- | :--- | :--- |
| **Manajemen Kredensial** | Static Long-lived Keys (Beresiko bocor di logs) | Short-lived OIDC Tokens (Kadaluarsa otomatis < 1 jam) |
| **Visibilitas Perubahan** | Log lokal developer, tidak transparan | Hasil `plan` otomatis dikomentari di Pull Request |
| **Tata Kelola (Governance)** | Manual peer review, rentan human error | Automated Policy Gates (OPA/Rego) memblokir PR non-compliant |
| **Audit & Kepatuhan** | Sulit membuktikan siapa mengeksekusi apa | Audit trail Git commit, signature OIDC, dan immutable CI logs |
| **State Lock Deadlock** | Terkunci manual, butuh `force-unlock` berisiko | Auto-lock timeout terisolasi per branch/PR workspace |

#### Anti-Pattern yang Dieliminasi:
- **The "Works on My Machine" Infrastructure:** Perbedaan versi biner Terraform atau provider plugins lokal yang merusak struktur state file.
- **The Rogue Apply:** Rekayasa manual di konsol cloud yang tidak tercatat di Git, berujung pada hilangnya konfigurasi saat tim lain menjalankan `terraform apply`.
- **Secret Sprawl:** Kredensial administrator cloud tersimpan di puluhan workstation engineer dan variabel CI/CD statis.

---

### 5. How (Workflow Detail)

Alur kerja GitOps end-to-end dari pembuatan kode hingga deployment produksi:

1. **Fase Authoring & Pre-commit:**
   - Engineer membuat branch `feat/aurora-database`.
   - Git hook lokal menjalankan `pre-commit run` yang mengeksekusi `terraform fmt -check`, `tflint`, dan `detect-secrets`.

2. **Fase Pull Request & Speculative Plan:**
   - PR dibuka mengarah ke branch `main`.
   - CI Runner dipicu, mengontak Identity Provider via OIDC untuk mengasumsikan peran IAM read-only.
   - Pipeline menjalankan:
     ```bash
     terraform init -backend=true
     terraform plan -no-color -out=tfplan.binary
     terraform show -json tfplan.binary > tfplan.json
     ```
   - Infracost menganalisis `tfplan.json` dan mempublikasikan estimasi lonjakan biaya bulanan ke komentar PR.
   - Conftest/OPA mengevaluasi aturan kepatuhan terhadap `tfplan.json`. Jika ada pelanggaran keamanan tingkat tinggi, pipeline berstatus **Failed**.
   - Output *plan summary* diformat secara rapi dan diposting sebagai komentar pada PR.

3. **Fase Approval & Merge:**
   - Tech Lead dan Security Engineer mereviu kode dan hasil output plan.
   - PR di-merge ke branch `main` menggunakan strategi *Squash and Merge*.

4. **Fase Production Apply:**
   - Pipeline branch `main` aktif.
   - OIDC menukarkan token dengan hak akses `TerraformDeployerRole` (Write privileges).
   - Terraform menerapkan konfigurasi secara deterministik:
     ```bash
     terraform apply -auto-approve -input=false tfplan.binary
     ```
   - Pipeline memverifikasi state, mempublikasikan metrik status deployment ke sistem monitoring (Prometheus/DataDog), dan melepaskan lock.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengadilan Hukum & Dokumen Akta Notaris
- **VCS (Git PR)** adalah *Pengajuan Berkas Gugatan/Akta*. Siapapun dapat membaca draf rancangannya, namun berkas tersebut belum berkekuatan hukum.
- **Speculative Plan & Policy Scan** adalah *Sidang Verifikasi Berkas*. Hakim (OPA/Conftest) memeriksa pasal-pasal hukum untuk memastikan tidak ada klausul yang melanggar konstitusi (regulasi keamanan enterprise).
- **OIDC STS Token** adalah *Surat Kuasa Sementara Bermaterai*. Notaris tidak memberikan kunci brankas selamanya; ia hanya memberikan izin masuk ruangan selama 30 menit khusus untuk agenda yang disepakati.
- **Terraform Apply via Runner** adalah *Penandatanganan dan Eksekusi Akta*. Hanya panitera resmi (Runner GitOps) yang berhak menuliskan hasil akta ke buku besar negara (Cloud State). Developer tidak boleh menulis sendiri di buku besar tersebut.

```
                      SIKLUS PULL-REQUEST TERRAFORM GITOPS

  Developer             GitHub PR               CI Pipeline Engine             AWS Cloud
     |                      |                           |                          |
     |--- 1. Git Push ----->|                           |                          |
     |    (Open PR)         |--- 2. Webhook Trigger --->|                          |
     |                      |                           |--- 3. OIDC Request ----->|
     |                      |                           |<-- 4. Temporary STS -----|
     |                      |                           |                          |
     |                      |                           |--- 5. Run Speculative -->|
     |                      |                           |       `terraform plan`   |
     |                      |                           |<-- 6. Read Cloud State --|
     |                      |                           |                          |
     |                      |                           |--- 7. Run OPA Checks     |
     |                      |<-- 8. Post Plan/Cost -----|    (Halt if violation)   |
     |                      |       PR Comment          |                          |
     |                      |                           |                          |
     |--- 9. PR Approved -->|                           |                          |
     |    & Merged          |--- 10. Trigger Apply ---->|                          |
     |                      |    (main branch)          |--- 11. OIDC Write Req -->|
     |                      |                           |<-- 12. Write STS Token --|
     |                      |                           |                          |
     |                      |                           |--- 13. `terraform apply`>|
     |                      |                           |<-- 14. Resources Mutated-|
     |                      |<-- 15. Report Success ----|                          |
```

---

### 7. Simple Example & Practical Example

#### A. Konfigurasi Trust Policy AWS IAM Role untuk GitHub Actions OIDC
Konfigurasi ini memastikan AWS hanya mempercayai repositori tertentu, branch tertentu, dan memvalidasi `aud` claim.

```hcl
# File: oidc_federation.tf

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "github_organization" {
  type        = string
  description = "Organisasi GitHub Enterprise"
  default     = "enterprise-corp"
}

variable "github_repository" {
  type        = string
  description = "Nama repositori untuk infrastruktur"
  default     = "core-infrastructure"
}

# 1. Daftarkan GitHub OIDC Provider ke AWS IAM jika belum ada
resource "aws_iam_openid_connect_provider" "github_actions" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1", "1c5824a9f704e763814418a95213b2465f4c40f4"]
}

# 2. IAM Role untuk Pull Request (Read-Only / Speculative Plan)
resource "aws_iam_role" "tf_plan_role" {
  name = "gh-actions-tf-plan"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github_actions.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" : "sts.amazonaws.com"
          }
          StringLike = {
            # Boleh diasumsikan oleh PR dari repo ini
            "token.actions.githubusercontent.com:sub" : "repo:${var.github_organization}/${var.github_repository}:pull_request"
          }
        }
      }
    ]
  })
}

# 3. IAM Role untuk Apply di Branch Main (Privileged Mutation)
resource "aws_iam_role" "tf_apply_role" {
  name = "gh-actions-tf-apply"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github_actions.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" : "sts.amazonaws.com",
            # Hanya branch main resmi yang boleh apply
            "token.actions.githubusercontent.com:sub" : "repo:${var.github_organization}/${var.github_repository}:ref:refs/heads/main"
          }
        }
      }
    ]
  })
}
```

#### B. Pipeline Produksi GitHub Actions dengan Security Policy Gate & Blast Radius Protection

```yaml
# File: .github/workflows/terraform-pipeline.yml
name: "Terraform Production GitOps Pipeline"

on:
  pull_request:
    branches: [ "main" ]
  push:
    branches: [ "main" ]

permissions:
  id-token: write   # Wajib untuk autentikasi OIDC
  contents: read    # Untuk checkout code
  pull-requests: write # Untuk menulis komentar plan ke PR

jobs:
  plan:
    name: "Speculative Plan & Security Validation"
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.6.6"

      - name: Setup Open Policy Agent (Conftest)
        run: |
          wget https://github.com/open-policy-agent/conftest/releases/download/v0.45.0/conftest_0.45.0_Linux_x86_64.tar.gz
          tar xzf conftest_0.45.0_Linux_x86_64.tar.gz
          sudo mv conftest /usr/local/bin/

      - name: Configure AWS Credentials via OIDC (Plan Role)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/gh-actions-tf-plan
          aws-region: ap-southeast-1
          audience: sts.amazonaws.com

      - name: Terraform Init
        run: terraform init

      - name: Terraform Plan
        id: plan
        run: |
          terraform plan -no-color -out=tfplan.binary
          terraform show -json tfplan.binary > tfplan.json

      - name: Policy as Code Gate (OPA/Conftest)
        run: |
          # Evaluasi policy di folder ./policy/
          conftest test tfplan.json --policy ./policy/

      - name: Comment Plan on PR
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const output = `#### Terraform Plan Status: ✅ Success
            *Pushed by: @${{ github.actor }}*
            *Action: \`${{ github.event_name }}\`*
            
            Policy Check passed via Conftest.`;
            
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: output
            });

  apply:
    name: "Production Execution Gate"
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production # Mewajibkan manual approval lewat GitHub Environment Protection Rules
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.6.6"

      - name: Configure AWS Credentials via OIDC (Apply Role)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/gh-actions-tf-apply
          aws-region: ap-southeast-1
          audience: sts.amazonaws.com

      - name: Terraform Init
        run: terraform init

      - name: Terraform Apply
        run: terraform apply -auto-approve -input=false
```

#### C. Aturan Policy-as-Code Rego (Blast Radius Gate)
Mencegah destruksi resource database produksi atau penghapusan lebih dari 3 resource sekaligus tanpa eskalasi tim arsitektur.

```rego
# File: policy/blast_radius.rego
package terraform.analysis

import future.keywords.in

default allow = false

# Dapatkan list semua resource changes
resource_deletions := [res | 
    res := input.resource_changes[_]
    "delete" in res.change.actions
]

# Larang destruksi resource database
deny_database_deletion {
    some res in resource_deletions
    res.type in ["aws_db_instance", "aws_rds_cluster"]
}

# Blast Radius Threshold: Tidak boleh menghapus > 3 resource dalam satu kali apply
blast_radius_exceeded {
    count(resource_deletions) > 3
}

# Evaluasi final
allow {
    not deny_database_deletion
    not blast_radius_exceeded
}

# Pesan penolakan terperinci
violation[msg] {
    deny_database_deletion
    msg := "POLICY VIOLATION: Penghapusan resource Database (RDS) melalui GitOps pipeline dilarang keras!"
}

violation[msg] {
    blast_radius_exceeded
    msg := sprintf("POLICY VIOLATION: Blast radius terlampaui. Jumlah resource dihapus: %d (Maksimum toleransi: 3)", [count(resource_deletions)])
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Bank Digital Multinasional (Skala: 1.200 Microservices, 40 Akun AWS)
- **Tantangan:** Bank memigrasikan infrastruktur core banking ke arsitektur multi-account AWS. Awalnya, tim DevOps mengizinkan eksekusi via Jenkins terpusat dengan *shared static IAM access keys*.
- **Insiden Keamanan:** Kredensial *root-deployer* Jenkins terekspos di log artifact build. Terjadi insiden di mana konfigurasi *Security Group* VPC staging terhapus karena *race condition* eksekusi bersamaan oleh dua engineer yang menjalankan `terraform apply` paralel tanpa distributed state locking yang tersinkronisasi.
- **Solusi Arsitektur:**
  1. **Migrasi ke OIDC Identity Federation:** Menghapus seluruh access key statis. Setiap runner ephemeral GitHub Actions Enterprise dipetakan ke role spesifik per akun AWS berdasarkan path direktori repositori:
     - Directory `accounts/payment-prod/` hanya dapat mengasumsikan role di AWS Account `987654321012`.
  2. **Implementasi Strict Monorepo Execution Concurrency:**
     Menggunakan matriks GitHub Actions yang dikombinasikan dengan wrapper script untuk parsing `git diff --name-only` guna mengidentifikasi *affected workspace*, diiringi locking via AWS DynamoDB table tersendiri.
  3. **Multi-Stage Guardrails:** Mengintegrasikan Infracost dan Conftest OPA. Jika estimasi biaya naik lebih dari $500/bulan atau ada tindakan `aws_iam_policy` yang mengizinkan wildcard `*`, merge PR secara mekanis diblokir hingga ada persetujuan tertulis dari CISO.
- **Hasil:** Waktu penyelesaian deployment berkurang dari 4 jam (antrean manual) menjadi 15 menit dengan 100% jejak audit kepatuhan ISO 27001 dan SOC2 Tipe II terpenuhi. Tidak ada lagi insiden *stale state* atau *unlocked conflict*.

---

### 9. Trade-offs

```
                                  SPEKTRUM ARSITEKTUR GITOPS TERRAFORM

             PULL-BASED GITOPS                                       PUSH-BASED PIPELINE
          (Atlantis / Spacelift)                                 (GitHub Actions / GitLab CI)
  <----------------------------------------------------------------------------------------->
  [+] State Drift rekonsiliasi instan                    [+] Native dengan ekosistem repo VCS
  [+] Server terisolasi di private network               [+] Tanpa manajemen server orkestrasi
  [-] Butuh maintain runner compute cluster              [-] Membutuhkan OIDC IDP endpoint publik
  [-] Setup webhooks kompleks skala ribuan repo          [-] Butuh implementasi lock manual di monorepo
```

1. **Pull-Based (cth. Atlantis Dedicated) vs Push-Based (cth. GitHub Actions OIDC):**
   - *Pull-Based Engine* menjaga state plan tetap berada di dalam network VPC internal. Namun, memerlukan biaya operasional tinggi untuk *maintain high availability* instance Atlantis dan storage log-nya.
   - *Push-Based Engine* tidak memerlukan dedicated compute yang terus menyala (*serverless runners*), menghemat biaya bulanan, namun membutuhkan setup OIDC dan eksposur API cloud ke GitHub IP ranges (kecuali memakai self-hosted ephemeral runners).

2. **Monorepo vs Multi-repo:**
   - *Monorepo:* Kemudahan visualisasi dependensi lintas modul dan standardisasi linter. Trade-off: CI trigger overhead tinggi, butuh *path-based filtering*, risiko *contention lock* pada shared resources.
   - *Multi-repo:* Isolasi blast radius sempurna. Trade-off: Redundansi kode pipeline, manajemen version tagging modul yang rumit, dan kesulitan memvalidasi breaking changes secara holistik.

---

### 10. Common Mistakes & Troubleshooting

#### 1. Masalah: `InvalidIdentityToken: OpenIDConnect provider's HTTPS certificate cannot be verified`
- **Penyebab:** Thumbprint dari OIDC identity provider (GitHub Actions) kedaluwarsa atau berubah. AWS IAM memerlukan thumbprint sertifikat SSL root CA dari URL OIDC.
- **Solusi:** Jangan bergantung pada static hardcoded thumbprints yang lama. AWS sekarang memvalidasi sertifikat GitHub Actions menggunakan thumbprint intermediate root certificate terbaru dari DigiCert. Daftarkan kedua thumbprint resmi GitHub di konfigurasi provider IAM.

#### 2. Masalah: State Lock Terkunci Permanen (`Error acquiring the state lock: ConditionalCheckFailedException`)
- **Penyebab:** CI runner mati mendadak (OOM killed atau timeout GitHub Actions) di tengah-tengah `terraform apply`, meninggalkan ID lock di DynamoDB.
- **Investigasi & Solusi:**
  1. Jangan langsung menghapus entry di DynamoDB secara manual via konsol AWS!
  2. Dapatkan `Lock Info: ID` dari log runner yang crash: `e.g., info: "b89a8dc8-1111-2222-3333-890abcdef123"`.
  3. Jalankan unlock terkontrol via CI pipeline khusus (atau role darurat):
     ```bash
     terraform force-unlock b89a8dc8-1111-2222-3333-890abcdef123
     ```
  4. Lakukan sanitasi state: `terraform refresh` untuk memastikan kondisi aktual sinkron sebelum pipeline berikutnya berjalan.

#### 3. Masalah: `WebIdentityErr: failed to retrieve credentials / OpenIDConnectProvider URL not authorized`
- **Penyebab:** Kesalahan pada penulisan claim `sub` di assume role policy AWS IAM. Format penulisan string regex sensitif terhadap huruf besar-kecil dan karakter titik dua.
- **Pengecekan:**
  ```bash
  # Salah (typo di pull_request atau repo path):
  "token.actions.githubusercontent.com:sub": "repo:Enterprise-Corp/infra:pull_request"
  
  # Benar (sesuai case-sensitive nama repositori GitHub persis):
  "token.actions.githubusercontent.com:sub": "repo:enterprise-corp/infra:pull_request"
  ```

---

### 11. Best Practices (Production Checklist)

Gunakan daftar checklist ini sebagai *readiness gate* sebelum merilis pipeline Terraform GitOps ke produksi:

- [ ] **Kredensial:** Long-lived static access keys (IAM User keys) 100% dinonaktifkan; seluruh koneksi memanfaatkan OIDC AssumeRoleWithWebIdentity.
- [ ] **Durasi Kredensial:** STS token dibatasi maksimum 1 jam (`MaxSessionDuration: 3600`).
- [ ] **Plan Output Protection:** Output file `tfplan.binary` dievaluasi di step OPA/Sentinel dalam keadaan terisolasi dan tidak diunggah ke *unencrypted public artifacts storage*.
- [ ] **State Backend Locking:** State locking aktif menggunakan DynamoDB Table (AWS), Blob Lease (Azure), atau Object Lock (GCP).
- [ ] **Branch Protection Rules:** Branch `main` mewajibkan:
  - Minimal 2 code reviewers (salah satunya Tim Platform/DevOps).
  - Status check pipeline OPA & spec plan wajib sukses (*Required Status Checks*).
  - Linier Git history (*Squash and merge* atau *Rebase*).
- [ ] **Concurrency Limit:** Set concurrency group di CI workflow (`concurrency: ${{ github.workflow }}-${{ github.ref }}`) agar apply tidak bertabrakan jika dua PR di-merge berurutan.
- [ ] **Cost Governance:** Tool estimasi biaya (*Infracost*) memblokir kenaikan biaya tak terduga (*budget threshold policies*).
- [ ] **Automated Drift Detection:** Cron job terjadwal berjalan setiap malam untuk memeriksa desinkronisasi arsitektur nyata dengan state file.

---

### 12. Hands-on Practice

Target Praktikum: Membangun konfigurasi lokal teruji untuk disiapkan ke direktori `hands-on/m02/` yang menguji integrasi OPA Conftest terhadap output Terraform Plan JSON.

#### Langkah 1: Persiapan Struktur Direktori
Buka terminal dan bangun struktur direktori praktikum berikut:
```bash
mkdir -p hands-on/m02/policy
cd hands-on/m02
```

#### Langkah 2: Buat File Infrastruktur Terraform
Buat file `main.tf` yang mensimulasikan pembuatan security group dan resource S3 dengan potensi pelanggaran keamanan:
```hcl
# File: hands-on/m02/main.tf
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region                      = "ap-southeast-1"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  access_key                  = "mock_key"
  secret_key                  = "mock_secret"
}

# Resource 1: S3 Bucket tanpa enkripsi (Non-compliant)
resource "aws_s3_bucket" "data_lake" {
  bucket = "enterprise-confidential-bucket-001"
}

# Resource 2: Security Group membuka SSH ke publik (Vulnerable)
resource "aws_security_group" "allow_ssh" {
  name        = "allow_ssh_public"
  description = "Akses SSH publik"

  ingress {
    description = "SSH dari dunia luar"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # Melanggar Policy!
  }
}
```

#### Langkah 3: Definisikan Policy Engine Rego
Buat file aturan di `policy/security.rego`:
```rego
# File: hands-on/m02/policy/security.rego
package terraform.security

import future.keywords.in

default allow = false

# Aturan 1: Deteksi SSH terbuka ke publik (0.0.0.0/0)
deny_ssh_open_to_world[msg] {
    some res in input.resource_changes
    res.type == "aws_security_group"
    some ingress in res.change.after.ingress
    "0.0.0.0/0" in ingress.cidr_blocks
    ingress.from_port <= 22
    ingress.to_port >= 22
    msg := sprintf("SECURITY VIOLATION: Security Group '%v' membuka SSH port 22 ke 0.0.0.0/0!", [res.name])
}

# Aturan 2: S3 Bucket harus mengonfigurasi Server Side Encryption
# (Dalam kasus ini memverifikasi bahwa plan menyertakan resource aws_s3_bucket_server_side_encryption_configuration)
deny_unencrypted_s3[msg] {
    some res in input.resource_changes
    res.type == "aws_s3_bucket"
    bucket_address := res.address
    
    # Cek apakah ada konfigurasi enkripsi terkait
    encryption_configs := [enc |
        enc := input.resource_changes[_]
        enc.type == "aws_s3_bucket_server_side_encryption_configuration"
        enc.change.after.bucket == bucket_address
    ]
    count(encryption_configs) == 0
    msg := sprintf("SECURITY VIOLATION: Bucket '%v' tidak memiliki konfigurasi aws_s3_bucket_server_side_encryption_configuration!", [res.name])
}

# Gatekeeper Allow logic
allow {
    count(deny_ssh_open_to_world) == 0
    count(deny_unencrypted_s3) == 0
}
```

#### Langkah 4: Eksekusi Validasi Lokal
Jalankan kompilasi plan tanpa provisioning fisik cloud untuk memvalidasi engine policy:
```bash
# Inisialisasi provider
terraform init

# Buat binary plan tiruan
terraform plan -out=tfplan.binary

# Konversi binary plan ke standard JSON format
terraform show -json tfplan.binary > tfplan.json

# Uji menggunakan conftest (Install conftest terlebih dahulu jika belum terpasang)
conftest test tfplan.json --policy ./policy/
```
*Expected Output:* Conftest akan mengeluarkan exit code non-zero dan mencetak 2 violation messages yang didefinisikan pada file `security.rego`.

---

### 13. Exercises

#### Level Easy
Konfigurasikan pipeline script CI (Bash) yang mengevaluasi format kode Terraform (`terraform fmt -check`) dan validasi sintaksis modul (`terraform validate`). Pipeline harus langsung keluar (*exit code 1*) dan membatalkan proses berikutnya jika terdeteksi berkas HCL yang tidak rapi.

#### Level Medium
Buat sebuah file policy OPA Rego (`policy/tags.rego`) yang memvalidasi bahwa setiap resource yang mendukung *tagging* (misal: `aws_instance`, `aws_vpc`, `aws_s3_bucket`) wajib memiliki tag minimal: `Environment` (nilainya harus salah satu dari: `dev`, `staging`, `prod`) dan `CostCenter` (format regex: `CC-[0-9]{4}`). Gagalkan *speculative plan* jika resource tidak memiliki tag tersebut.

#### Level Hard
Rancang arsitektur pipeline GitHub Actions multi-environment (Dev, Staging, Prod) dengan pola *Trunk-Based Development*. Ketentuan:
1. Merge ke branch `main` tidak boleh langsung menerapkan perubahan ke akun `Production`.
2. Pipeline otomatis melakukan `apply` ke lingkungan `Staging`.
3. Setelah sukses di `Staging`, pipeline menunggu *Approval* interaktif dari Security Lead via GitHub Environment Protection.
4. Ketika disetujui, runner menukar token OIDC baru untuk IAM Role akun `Production` dan menjalankan apply menggunakan state lock terpisah.

---

### 14. Challenge

**Studi Kasus: Monorepo Orchestration Deadlock & State Drift Race Condition**

**Latar Belakang Kasus:**
Perusahaan Anda memiliki monorepo Terraform berskala enterprise dengan struktur direktori sebagai berikut:
```
infrastruktur/
├── modules/
│   ├── networking/
│   └── eks_cluster/
└── environments/
    ├── dev/
    ├── staging/
    └── prod/
```
Tiga tim terpisah melakukan merge 3 Pull Request yang berbeda secara bersamaan ke branch `main`:
- **PR 1:** Menambahkan subnet baru di `environments/prod/networking`.
- **PR 2:** Melakukan resize node pool EKS di `environments/prod/eks_cluster`. Modul ini mereferensikan subnet ID dari output state `environments/prod/networking` menggunakan data source `terraform_remote_state`.
- **PR 3:** Melakukan security patching Security Group di `environments/prod/networking`.

**Masalah Kritis:**
Pipeline CI/CD menjalankan ketiga workflow apply secara paralel menggunakan runner berbeda. Terjadi tabrakan state lock di DynamoDB backend untuk direktori `networking`, sementara pipeline modul `eks_cluster` gagal dieksekusi (*crash*) karena membaca subnet output lama dari state yang belum selesai dimutasi oleh PR 1. Terjadi status *inconsistent state* dan rollback otomatis tidak tersedia di level cloud.

**Tantangan Arsitektur Anda:**
1. Rancang algoritma deteksi dependensi (DAG execution engine) di dalam orchestrator CI/CD Anda yang secara otomatis mengantrekan (*queue*) apply secara serial untuk modul yang memiliki dependensi state, namun tetap mengeksekusi modul independen secara paralel.
2. Definisikan mekanisme OIDC role scoping agar PR dari folder `environments/dev/` mustahil memiliki permissions untuk memanipulasi lock atau state file milik `environments/prod/`.
3. Susun mekanisme pemulihan (*disaster recovery pipeline*) ketika sebuah apply terputus di tengah jalan sehingga remote state tidak tersandera oleh *dangling lock*.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Basic (5 Pertanyaan)

1. **Apa perbedaan mendasar antara OIDC federation dan hardcoded IAM User Access Keys pada pipeline CI/CD?**
   - A. OIDC lebih lambat karena harus selalu membuat user baru di konsol IAM.
   - B. OIDC menggunakan token JWT sementara yang kadaluarsa otomatis tanpa menyimpan kredensial statis di runner.
   - C. IAM Access Keys lebih aman karena disimpan di GitHub Encrypted Secrets.
   - D. OIDC tidak memerlukan permissions IAM role di cloud provider.
   *(Jawaban: B — OIDC menukar JWT sementara berdurasi pendek, meniadakan risiko kebocoran static keys).*

2. **Perintah Terraform apa yang paling krusial dijalankan untuk menghasilkan artefak yang dapat dianalisis oleh Policy-as-Code engine (seperti OPA)?**
   - A. `terraform validate -json`
   - B. `terraform show -json <binary_plan_file>`
   - C. `terraform state pull > state.json`
   - D. `terraform output -json`
   *(Jawaban: B — `terraform show -json` mengubah binary execution plan menjadi format JSON yang memuat detail resource_changes).*

3. **Mengapa file `tfplan` sebaiknya di-generate saat Pull Request dan digunakan kembali saat Apply, bukan menjalankan `terraform apply` langsung dari kode mentah?**
   - A. Agar proses apply berjalan tanpa koneksi internet.
   - B. Agar ukuran repository Git tidak membengkak.
   - C. Untuk menjamin determinisme: apa yang diverifikasi dan disetujui di PR adalah hal yang persis dieksekusi di cloud, menghindari race condition.
   - D. Karena perintah `terraform apply` tidak mendukung eksekusi tanpa file plan.
   *(Jawaban: C — Memastikan determinisme antara apa yang direviu manusia/policy dan apa yang diaplikasikan ke server).*

4. **Apa fungsi utama dari claim `sub` (*Subject*) pada konfigurasi IAM Trust Policy OIDC?**
   - A. Menentukan password database cloud.
   - B. Membatasi penukaran token hanya untuk repositori, branch, atau event Git tertentu secara spesifik.
   - C. Mengatur durasi idle timeout dari runner CI.
   - D. Menentukan besaran memory runner container.
   *(Jawaban: B — Claim `sub` membatasi identitas pemanggil, mencegah repo lain mengasumsikan role yang sama).*

5. **Apa indikasi teknis bahwa Terraform mendeteksi adanya *state lock contention*?**
   - A. Error HTTP 404 Not Found.
   - B. Error `ConditionalCheckFailedException` dari backend locking (misal DynamoDB).
   - C. State file otomatis terhapus dari bucket.
   - D. Terraform meminta konfirmasi `yes` secara berulang-ulang.
   *(Jawaban: B — Locking mechanism menggunakan conditional check write; jika lock ID masih ada, exception ini akan dilempar).*

---

#### Bagian B: Intermediate (5 Pertanyaan)

6. **Dalam arsitektur Push-based CI/CD monorepo, apa risiko terbesar dari menjalankan `terraform apply` secara paralel tanpa path-filtering yang ketat?**
   - A. GitHub Actions akan menolak koneksi secara permanen.
   - B. Terjadi state lock conflict atau inkonsistensi referensi data output antar modul dependen.
   - C. Format file `.tf` akan tertimpa otomatis menjadi `.json`.
   - D. Kredensial OIDC otomatis di-revoke oleh cloud provider.
   *(Jawaban: B — Tabrakan lock dan dependensi lintas modul yang tidak tersinkronisasi dapat merusak reliabilitas deployment).*

7. **Pada tools Policy-as-Code seperti Conftest (Rego), apa arti dari struktur data `input.resource_changes[_].change.actions`?**
   - A. Daftar nama branch Git yang diizinkan melakukan deploy.
   - B. Nilai IP Address dari Cloud Provider.
   - C. Array tindakan Terraform terhadap resource tersebut, seperti `["create"]`, `["update"]`, atau `["delete"]`.
   - D. Log histori perubahan commit developer.
   *(Jawaban: C — Array ini mengindikasikan lifecycle action yang akan diterapkan Terraform pada resource terkait).*

8. **Bagaimana cara paling aman menangani *Terraform drift* yang terjadi karena perubahan manual darurat di AWS console?**
   - A. Langsung jalankan `terraform apply -auto-approve` dari lokal engineer.
   - B. Hapus resource dari kode HCL agar tidak bentrok.
   - C. Jalankan `terraform plan -refresh-only` via pipeline, validasi perbedaan, update kode HCL agar sesuai kondisi riil, lalu merge via PR standar.
   - D. Matikan fitur drift detection di cloud.
   *(Jawaban: C — Rekonsiliasi drift harus melalui audit trail PR standar dengan merefleksikan perubahan nyata ke kode HCL).*

9. **Mengapa thumbprint SHA-1 OIDC GitHub Actions harus didaftarkan di IAM OpenID Connect Provider AWS?**
   - A. Untuk mengenkripsi state file di S3.
   - B. Untuk memverifikasi sertifikat SSL endpoint GitHub Actions sehingga AWS memercayai autentisitas server penanda tangan JWT.
   - C. Untuk membatasi IP address GitHub Actions runner.
   - D. Sebagai API token pembayaran layanan AWS.
   *(Jawaban: B — AWS memerlukan trust anchor sertifikat SSL CA provider guna memverifikasi validitas token HTTPS endpoint).*

10. **Apa implikasi penggunaan `concurrency: ${{ github.workflow }}-${{ github.ref }}` pada GitHub Actions workflow untuk Terraform apply?**
    - A. Membatasi runner agar hanya bisa dipakai oleh satu developer.
    - B. Mencegah race condition dengan membatalkan atau mengantrekan eksekusi apply yang dipicu secara simultan pada branch yang sama.
    - C. Mempercepat koneksi jaringan runner ke AWS.
    - D. Membagi eksekusi file plan ke dalam 5 node terpisah.
    *(Jawaban: B — Memastikan eksekusi pipeline apply pada target branch berjalan serial dan tidak tumpang tindih).*

---

#### Bagian C: Skenario Kasus Produksi (3 Pertanyaan Kompleks)

11. **Skenario 1:**
    Sebuah PR disetujui untuk menghapus load balancer lama. Namun, pipeline apply di branch `main` gagal di tengah jalan dengan error:
    `ResourceInUse: Target group is currently in use by a listener rule`.
    State lock DynamoDB tertinggal dan pipeline berikutnya macet. Sebagai Platform Engineer, langkah remediasi apa yang harus Anda lakukan sesuai urutan tata kelola yang benar tanpa merusak integritas state produksi?
    - **Solusi Rekayasa:**
      1. Kunci antrean pipeline PR lain secara manual untuk mencegah eksekusi baru.
      2. Identifikasi identitas lock: Ambil lock ID dari pesan error runner yang macet.
      3. Jalankan `terraform force-unlock <LOCK_ID>` via runner pipeline administrasi khusus (bukan manual di AWS DynamoDB console) guna menjaga audit trail.
      4. Investigasi root cause: Periksa dependensi siklik atau ordering failure di HCL (listener rule harus dihapus sebelum target group).
      5. Ajukan PR koreksi kode yang menambahkan `depends_on` secara eksplisit atau menghapus listener rule terlebih dahulu, lalu merge untuk melanjutkan apply hingga state bersih.

12. **Skenario 2:**
    Perusahaan Anda menerapkan aturan keamanan finansial: *“Tidak ada anggota tim teknis yang boleh memiliki akses tulis (write) langsung ke AWS IAM Role produksi.”* Namun, tim DevOps tetap dituntut melakukan provisioning infrastruktur baru secara dinamis menggunakan Terraform. Bagaimana Anda mendesain arsitektur otorisasi GitOps untuk memenuhi aturan ini?
    - **Solusi Rekayasa:**
      1. Cabut seluruh policy `iam:*` dari semua developer dan DevOps workstation/user credentials.
      2. Konfigurasikan OIDC Identity Federation di AWS IAM. Buat Role `TerraformExecutionRole` dengan permissions provisioning yang dibutuhkan.
      3. Definisikan `assume_role_policy` yang mengunci strictly claim: `"token.actions.githubusercontent.com:sub": "repo:org/infra-repo:ref:refs/heads/main"`.
      4. Terapkan *Branch Protection* di GitHub: Branch `main` wajib lolos review minimal dari 2 Principal Engineer dan Security Lead.
      5. Developer hanya memiliki akses write ke branch fitur lokal dan pull request. Hanya pipeline ephemeral GitHub runner yang mengeksekusi peran tulis ke cloud via token OIDC bertanda tangan.

13. **Skenario 3:**
    Dalam audit kepatuhan SOC2, auditor menemukan bahwa developer dapat memasukkan kredensial AWS rahasia di dalam variabel lokal atau melakukan *privilege escalation* dengan menambahkan role admin di kode HCL mereka sendiri tanpa terdeteksi sebelum merge. Rancang sistem pertahanan *Defense-in-Depth* pada pipeline GitOps untuk memitigasi celah ini.
    - **Solusi Rekayasa:**
      1. **Shift-Left Static Scanning:** Pasang tool `gitleaks` dan `checkov` di GitHub Actions PR stage untuk menggagalkan pipeline jika terdeteksi raw credentials atau konfigurasi IAM wildcards (`*`).
      2. **Policy-as-Code Enforcement (OPA/Sentinel):** Terjemahkan `tfplan` menjadi JSON. Evaluasi aturan: Tolak PR jika ada penambahan resource `aws_iam_*` yang melampirkan policy `AdministratorAccess` atau jika parameter `Statement.Action` mengandung `iam:*` tanpa persetujuan Tim IAM Khusus via CODEOWNERS.
      3. **Permission Boundaries:** Tetapkan `permissions_boundary` wajib pada semua modul IAM buatan developer di pipeline apply, sehingga role baru yang dibuat tidak akan pernah bisa mengekskalasi hak akses melebihi batas batas aman enterprise.

---

### 16. Summary

Implementasi GitOps enterprise untuk Terraform memindahkan beban tata kelola (*governance*), determinisme, dan keamanan dari workstation lokal developer ke sistem orkestrasi otomatis yang terisolasi. 

Pilar utama produksi ini bertumpu pada **eliminasi kredensial statis via OIDC**, **pembatasan blast radius menggunakan automated policy evaluation (OPA/Conftest)**, dan **manajemen konkurensi state locking yang terdisiplin**. 

Dengan menjadikan Pull Request sebagai *single source of truth* dan *single audit trail*, organisasi tidak hanya mencapai kecepatan rilis infrastruktur yang terukur, namun juga memastikan bahwa standard kepatuhan keamanan dan anggaran finansial tervalidasi secara absolut sebelum ada satu pun byte infrastruktur di cloud yang dimutasi.