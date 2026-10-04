# Kurikulum Enterprise: Terraform Core Engine & State Architecture
**Kategori:** 05-DevOps-Cloud-and-SRE  
**Bab 03:** BAB-03-State-Architecture-dan-Concurrency-Control  
**Modul 02:** Deep Dive, Implementasi Lanjutan & Arsitektur Produksi  

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- **Menganalisis Anatomi State:** Membedah struktur JSON internal Terraform state (`version`, `serial`, `lineage`, `resources`, `schema_version`) untuk diagnosa korupsi state dan pelacakan dependensi resource graph.
- **Menguasai Distributed Locking Engine:** Memahami siklus hidup mutual exclusion (Mutex) berbasis backend remote (AWS S3 + DynamoDB / HashiCorp Consul / GCS) guna mencegah race condition pada pipeline CI/CD konkuren.
- **Mendesain Pola Dekomposisi Micro-State:** Mentransformasikan arsitektur *monolithic state* (ribuan resource) menjadi *isolated micro-states* berbasis domain/lifecycle untuk meminimalkan *blast radius* dan waktu eksekusi run-time.
- **Mengeksekusi State Refactoring Tingkat Lanjut:** Melakukan refactoring topologi infrastruktur tanpa downtime menggunakan deklaratif block `moved`, manipulasi CLI tingkat rendah (`state mv`, `state rm`, `import`), serta perbaikan *lineage mismatch*.
- **Menerapkan Defense-in-Depth State Security:** Mengamankan state file dari kebocoran secret (plain-text attributes) menggunakan KMS Envelope Encryption, IAM least privilege, dan *ephemeral execution runtimes*.

---

## 2. Prerequisites
- **Teoretis:** Pemahaman siklus hidup Terraform CLI (`init`, `plan`, `apply`, `destroy`), dependency graph dasar, dan arsitektur Client-Server Cloud API.
- **Praktikal:** 
  - Kemahiran navigasi AWS CLI / Cloud Shell.
  - Pemahaman format data JSON tingkat lanjut (jq parsing).
  - Akses administratif ke AWS Account dengan hak membuat S3, DynamoDB, KMS, dan IAM Role.
  - Terraform binary versi $\ge$ 1.5.x (mendukung declarative `import` and `moved` blocks).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Anatomi Internal File State (`terraform.tfstate`)
Terraform state bukanlah sekadar cache; ini adalah *single source of truth* yang memetakan deklarasi konfigurasi (HCL) ke metadata resource riil di cloud provider (ID unik, ARN, atribut internal).

```json
{
  "version": 4,
  "terraform_version": "1.8.0",
  "serial": 42,
  "lineage": "c8b417e2-4981-4286-9dc5-d5c2a13809ef",
  "outputs": {},
  "resources": [
    {
      "mode": "managed",
      "type": "aws_instance",
      "name": "primary_db",
      "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
      "instances": [
        {
          "schema_version": 1,
          "attributes": {
            "id": "i-0abcd1234ef567890",
            "arn": "arn:aws:ec2:ap-southeast-1:112233445566:instance/i-0abcd1234ef567890",
            "instance_type": "m6i.large",
            "private_ip": "10.0.1.45",
            "tags": { "Env": "production" }
          },
          "sensitive_attributes": [],
          "private": "eyJlMmJmYjczMC1lY2FhLTExZTYtOGY4OC0zNDM2M2JjN2M0YzAiOnsiY3JlYXRlIjo2MDAwMDAwMDAwMDAsImRlbGV0ZSI6MTIwMDAwMDAwMDAwMCwidXBkYXRlIjo2MDAwMDAwMDAwMDB9LCJzY2hlbWFfdmVyc2lvbiI6IjEifQ=="
        }
      ]
    }
  ],
  "check_results": null
}
```

Metrik dan parameter kunci dalam state file:
1. **`lineage` (UUIDv4):** Identifier global unik yang di-generate pada inisialisasi awal suatu state. Jika dua state memiliki `lineage` berbeda, Terraform menolak operasi penggabungan (*merge*) untuk mencegah *split-brain*.
2. **`serial` (Monotonically Increasing Integer):** Sequence counter. Setiap kali `apply` berhasil mengubah state, nilai `serial` dinaikkan ($n+1$). Remote backend memvalidasi: $Serial_{incoming} > Serial_{remote}$. Jika tidak, mutasi ditolak (mencegah *stale write*).
3. **`private` (Base64 Encoded Payload):** Metadata spesifik provider (misalnya waktu timeout pembuatan resource, checksum schema versi lama) yang diperlukan provider saat mengeksekusi operasi CRUD.
4. **`schema_version`:** Versi skema resource provider. Jika provider di-upgrade dan memperkenalkan migrasi schema, Terraform menggunakan nilai ini untuk menjalankan fungsi migrasi state provider (*State Upgrade Hook*).

---

### 3.2 Concurrency Control & Distributed Locking Mechanism
Ketika Terraform mengeksekusi operasi `plan` atau `apply` dengan remote backend yang mendukung locking (contoh: AWS S3 + DynamoDB):

1. **Lock Acquisition Request:** Terraform menghitung SHA256 dari path konfigurasi dan state. Terraform mengirim operasi `PutItem` ke DynamoDB dengan conditional expression:
   $$\text{attribute\_not\_exists}(LockID)$$
2. **Lock Record Schema:**
   - **`LockID` (String, Hash Key):** Path unik state file, misalnya `<bucket-name>/<state-path>/terraform.tfstate-md5`.
   - **`Info` (String JSON Payload):**
     ```json
     {
       "ID": "f90df265-d069-42b4-5339-10cf35e98516",
       "Operation": "OperationTypeApply",
       "Info": "",
       "Who": "runner-01@runner-pod-774f9d",
       "Version": "1.8.0",
       "Created": "2024-03-20T08:15:30.123456Z",
       "Path": "production/ap-southeast-1/core-network/terraform.tfstate"
     }
     ```
3. **Mutual Exclusion (Mutex) Validation:**
   - Jika `PutItem` berhasil $\to$ Lock aktif didapatkan.
   - Jika `ConditionalCheckFailedException` dilempar oleh DynamoDB $\to$ Terraform langsung menghentikan proses (*fail-fast*) dengan pesan: *"Error acquiring the state lock"*, menampilkan metadata `Who` dan `ID` dari entri yang mengunci.
4. **Release Sequence:** Setelah state di-push ke S3 (dengan serial baru), Terraform mengirim `DeleteItem` dengan kunci `LockID` yang cocok dengan ID transaksi lock-nya.

---

## 4. Why & What: State Isolation & Concurrency

### Mengapa State Perlu Diproteksi dan Diisolasi?
- **Race Condition Mutasi Cloud:** Dua runner CI/CD mengeksekusi perubahan subnet secara paralel. Runner A menghapus subnet; Runner B membuat interface di subnet tersebut. Tanpa locking, API state cloud provider dan local memory runner akan mengalami *unrecoverable divergence*.
- **Blast Radius Monolithic State:** State file yang menampung 3.000 resource membutuhkan waktu 20 menit hanya untuk fase `Refresh` (memeriksa API cloud satu per satu). Selain itu, satu kesalahan HCL pada layer network dapat merusak atau menggagalkan provisioning layer database atau compute.
- **Sensitive Data Leakage:** Secara default, Terraform menyimpan *semua* atribut resource dalam format plain-text JSON di dalam state, termasuk database password, TLS private keys, dan API tokens yang di-generate via providers (seperti `random_password` atau `tls_private_key`).

### Solusi Arsitektur
Dekomposisi state menjadi **Micro-State Domains** yang terikat via *Contract Interfaces* (State Read-Only atau Dynamic Lookup via SSM Parameter Store / Consul):

```
[ Domain: Network ]  --(Exports SSM IDs)-->  [ Domain: Data Storage ]
        |                                             |
  (State File A)                                (State File B)
  (Blast Radius: Rendah)                       (Blast Radius: Rendah)
```

---

## 5. How: Siklus Transaksi State Engine (Workflow Detail)

```
      TERRAFORM CLIENT                    BACKEND (S3)               LOCK ENGINE (DDB)
             │                                 │                             │
    (1)      ├── Acquire Lock (PutItem) ────────────────────────────────────>│
             │   [Condition: LockID does not exist]                          │
             │<── 200 OK (Lock Aquired) ─────────────────────────────────────┤
             │                                 │                             │
    (2)      ├── Read State (GetObject) ──────>│                             │
             │<── Return terraform.tfstate ────┤                             │
             │                                 │                             │
    (3)      ├─┐ Cloud API Refresh             │                             │
             │ ├─ Compute Plan Delta           │                             │
             │ ├─ Execute CRUD API Calls       │                             │
             │ └─ Increment Serial (n+1)       │                             │
             │                                 │                             │
    (4)      ├── Write State (PutObject) ─────>│                             │
             │   [Payload: Updated State]      │                             │
             │<── 200 OK (Persisted) ──────────┤                             │
             │                                 │                             │
    (5)      ├── Release Lock (DeleteItem) ─────────────────────────────────>│
             │<── 200 OK (Unlocked) ─────────────────────────────────────────┤
```

Tahapan eksekusi:
1. **Lock Phase:** Evaluasi atomik di DynamoDB.
2. **Fetch Phase:** Download state snapshot dari S3, deserialisasi JSON ke in-memory graph.
3. **Execution Phase:** Provider merekonsiliasi delta graph dengan target Cloud Provider API. Serialization JSON baru dibuat, `serial` dinaikkan secara inkremental, `lineage` dipertahankan identik.
4. **Commit Phase:** Upload state atomik ke S3 via enkripsi SSE-KMS. S3 Object Versioning secara otomatis mengarsipkan state lama.
5. **Unlock Phase:** Hapus item kunci di DynamoDB.

---

## 6. Analogi & Arsitektur ASCII

### Analogi
Pikirkan Terraform State Engine seperti **Database Transaction Log (WAL) dengan Distributed Two-Phase Locking (2PL)**.
- **State File:** Database snapshot.
- **DynamoDB Lock:** Kunci eksklusif baris transaksi (`SELECT ... FOR UPDATE`).
- **Serial Number:** LSN (Log Sequence Number) atau Transaction ID.
- Jika dua DBA mencoba menjalankan `ALTER TABLE` pada skema yang sama secara paralel, lock manager akan menahan atau membatalkan sesi kedua demi mencegah korupsi tabel.

### Diagram Arsitektur Isolasi State Perusahaan (Tiered Lifecycle Architecture)

```
+------------------------------------------------------------------------------------+
|                               AWS ORGANIZATIONS                                   |
|                                                                                    |
|  +---------------------------+   State Lock & Data Read   +---------------------+  |
|  |     Shared Core Infra     |--------------------------->|  S3: tf-state-prod  |  |
|  |     (VPC, DirectConnect)  |<===========================|  DDB: tf-locks-prod |  |
|  +---------------------------+   Encrypted via KMS        +---------------------+  |
|               │                                                                    |
|               │ Publishes Subnet IDs & Route Table IDs to AWS Systems Manager      |
|               ▼                                                                    |
|  +---------------------------+   Dynamic Data Source      +---------------------+  |
|  |     Data Tier Platform    |--------------------------->|  S3: tf-state-data  |  |
|  |     (RDS, Aurora, ElastiC)|<===========================|  DDB: tf-locks-data |  |
|  +---------------------------+   No direct state-file coupling+-----------------+  |
|               │                                                                    |
|               │ Publishes Cluster Endpoints to SSM                                 |
|               ▼                                                                    |
|  +---------------------------+   Dynamic Data Source      +---------------------+  |
|  |     Compute / App Tier    |--------------------------->|  S3: tf-state-apps  |  |
|  |     (EKS, ECS, Autoscale) |<===========================|  DDB: tf-locks-apps |  |
|  +---------------------------+                            +---------------------+  |
+------------------------------------------------------------------------------------+
```

---

## 7. Simple & Practical Implementation

### 7.1 Simple Example: Backend Setup Standar (Baseline)

```hcl
# backend-simple.tf
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "corp-tfstate-ap-southeast-1-prod"
    key            = "simple/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "corp-tflocks-prod"
    encrypt        = true
  }
}
```

---

### 7.2 Practical Example: Enterprise Hardened Backend & State Refactoring

Arsitektur produksi ini mencakup:
1. Bucket S3 dengan enkripsi AWS KMS CMK (Customer Managed Key), penolakan koneksi Non-TLS, dan Object Versioning.
2. DynamoDB dengan Point-In-Time Recovery (PITR).
3. Penggunaan deklaratif `moved` block untuk zero-downtime resource refactoring (mengubah resource flat menjadi module tanpa menghapus dan membuat ulang infrastruktur nyata).

#### Bagian A: Enterprise S3 Backend Engine Definition

```hcl
# backend-bootstrap/main.tf
provider "aws" {
  region = "ap-southeast-1"
}

# KMS Key untuk enkripsi State
resource "aws_kms_key" "state_encryption" {
  description             = "KMS CMK dedicated for Terraform State S3 & DynamoDB storage"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Environment = "Management"
    Purpose     = "TerraformStateEncryption"
  }
}

resource "aws_kms_alias" "state_encryption_alias" {
  name          = "alias/terraform-state-key"
  target_key_id = aws_kms_key.state_encryption.key_id
}

# S3 State Bucket
resource "aws_s3_bucket" "state_bucket" {
  bucket        = "corp-tfstate-production-secure-root"
  force_destroy = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "state_versioning" {
  bucket = aws_s3_bucket.state_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state_sse" {
  bucket = aws_s3_bucket.state_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.state_encryption.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "state_pab" {
  bucket                  = aws_s3_bucket.state_bucket.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Bucket Policy: Paksa TLS 1.2+ & Tolak Unencrypted Transport
resource "aws_s3_bucket_policy" "enforce_tls_policy" {
  bucket = aws_s3_bucket.state_bucket.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnforceTLSRequestsOnly"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.state_bucket.arn,
          "${aws_s3_bucket.state_bucket.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}

# DynamoDB Lock Table
resource "aws_dynamodb_table" "state_locks" {
  name         = "corp-tflocks-production-secure"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.state_encryption.arn
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Environment = "Management"
    Purpose     = "TerraformConcurrencyLocking"
  }
}
```

#### Bagian B: Consumer Workspace dengan Deklaratif Refactoring (`moved` block)

Studi kasus: Resource `aws_security_group.app_sg` sebelumnya dideklarasikan secara flat, kini harus dipindahkan ke dalam submodule internal `module.networking_security` tanpa destruksi fisik resource di AWS.

```hcl
# main.tf (Consumer Project)
terraform {
  required_version = ">= 1.5.0"
  
  backend "s3" {
    bucket         = "corp-tfstate-production-secure-root"
    key            = "network-layer/ap-southeast-1/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "corp-tflocks-production-secure"
    kms_key_id     = "arn:aws:kms:ap-southeast-1:112233445566:alias/terraform-state-key"
    encrypt        = true
  }
}

# Deklarasi refactoring state secara deklaratif (Terraform >= 1.1)
# Mencegah: Destroy and Re-create
moved {
  from = aws_security_group.app_sg
  to   = module.networking_security.aws_security_group.app_sg
}

module "networking_security" {
  source = "./modules/security"
  vpc_id = "vpc-0123456789abcdef0"
}
```

---

## 8. Real-World Case Study: Enterprise Scale State Splitting

### Skenario & Masalah
PT FinTech Nusantara memiliki monolith state file (`production-all.tfstate`) yang menampung **2.400 resources**:
- Execution run-time `terraform plan` memakan waktu **28 menit**.
- Cloud Provider API rate limiting (AWS CloudWatch & EC2 ThrottlingExceptions).
- Terjadi insiden: Developer mengubah rule Route53 internal, namun bug syntax di module ElastiCache memicu kegagalan eksekusi dan deadlock status DynamoDB lock selama 4 jam.
- Blast radius terlalu besar; 4 squad engineer berebut satu state lock yang sama.

### Solusi Dekomposisi Terisolasi
Tim SRE memecah arsitektur menjadi 3 state terisolasi secara horizontal:
1. `core-network.tfstate` (VPC, Transit Gateway, Subnets, DirectConnect) -> Serial rendah, frekuensi perubahan jarang ($< 1 \text{x / bulan}$).
2. `core-platform-storage.tfstate` (Aurora RDS, ElastiCache Redis, S3 buckets) -> Frekuensi perubahan menengah.
3. `kubernetes-workloads.tfstate` (EKS NodeGroups, Helm Addons) -> Frekuensi perubahan tinggi ($> 50 \text{x / hari}$).

### Strategi Integrasi Data: dynamic lookup vs `terraform_remote_state`
Alih-alih menggunakan `terraform_remote_state` data source (yang mengekspos seluruh isi state upstream ke downstream, melanggar prinsip least privilege), digunakan **AWS Systems Manager (SSM) Parameter Store Contract**:

```
[Layer 1: Network Project]
         │
         ▼
 Writes SSM Parameter: /infra/network/vpc_id
         │
         ▼
[Layer 2: Storage Project]
 Reads Data Source: aws_ssm_parameter.vpc_id
```

```hcl
# Layer 1: Expose output contract ke SSM
resource "aws_ssm_parameter" "vpc_id_contract" {
  name        = "/contracts/network/ap-southeast-1/vpc_id"
  type        = "String"
  value       = aws_vpc.main.id
  description = "Source of truth VPC ID for downstream platform projects"
  overwrite   = true
}

# Layer 2: Downstream Workspace membaca parameter (Loose Coupling)
data "aws_ssm_parameter" "vpc_id" {
  name = "/contracts/network/ap-southeast-1/vpc_id"
}

resource "aws_security_group" "db_sg" {
  name        = "db-access-layer"
  vpc_id      = data.aws_ssm_parameter.vpc_id.value
  description = "Bound to Core Network via SSM Contract"
}
```

### Hasil Pasca Migrasi
- Run-time eksekusi rata-rata turun dari **28 menit** menjadi **45 detik** pada layer platform/kubernetes.
- Eliminasi penuh API rate-limiting via AWS Throttling.
- Zero state lock contention antar squad.

---

## 9. Trade-Off Analysis

| Parameter | Monolithic State File | Micro-States (`terraform_remote_state`) | Micro-States (Decoupled Contracts via SSM/Vault) |
| :--- | :--- | :--- | :--- |
| **Blast Radius** | **Kritis (Tinggi).** Kerusakan state mematikan seluruh ekosistem infra. | **Rendah.** Terisolasi per direktori/layer state. | **Minimal.** Terisolasi total pada level resource dan data plane. |
| **Execution Latency** | **Sangat Buruk.** Waktu linear terhadap total sumber daya ($O(N)$ API latency). | **Sangat Cepat.** Hanya me-refresh target layer domain. | **Sangat Cepat.** Hanya me-refresh target layer domain. |
| **Concurrency / Contention**| **Tinggi.** Seluruh squad terhambat satu lock table DynamoDB. | **Rendah.** Lock terjadi per domain state individual. | **Zero Contention.** State lifecycle sepenuhnya independen. |
| **Access Control (IAM)** | **Sulit.** Hak akses Read/Write all-or-nothing ke seluruh resource. | **Rentan.** State upstream mengekspos semua atribut ke downstream. | **Aman.** Prinsip Least Privilege; consumer hanya membaca output spesifik. |
| **Operational Overhead**| Rendah saat awal, meningkat secara eksponensial seiring skala infra. | Sedang; butuh dependensi pipeline orchestration yang presisi. | Sedang-Tinggi; butuh standardisasi tata kelola skema key contract. |

---

## 10. Common Mistakes & Production Troubleshooting

### Mistake 1: Manual State Poisoning via Local Editing
- **Anti-pattern:** Mengedit file `terraform.tfstate` lokal secara manual menggunakan teks editor untuk membetulkan nama atau metadata ARN, lalu mem-push-nya kembali ke remote backend.
- **Dampak:** Hash checksum invalid, nilai `serial` tidak sinkron, dan formatting JSON merusak tree internal parser HashiCorp Core.
- **Solusi:** Selalu gunakan perintah `terraform state rm`, `terraform state mv`, atau manipulasi metadata via `terraform import`.

### Mistake 2: Stale Concurrency Lock (Pipeline Crashes)
- **Gejala:** Pipeline CI/CD terbunuh mendadak (*OOM Kill* atau *Timeout*). Run berikutnya memunculkan error:
  ```
  Error: Error acquiring the state lock: ConditionalCheckFailedException: The conditional request failed
  Lock Info:
    ID:        a1b2c3d4-e5f6-7890-abcd-1234567890ef
    Path:      corp-tfstate/terraform.tfstate
    Operation: OperationTypeApply
    Who:       gitlab-runner@runner-01
  ```
- **Troubleshooting & Remediasi Aman:**
  1. Verifikasi silang ke infrastructure runner: pastikan TIDAK ADA proses Terraform yang sedang berjalan untuk ID tersebut.
  2. Buka DynamoDB Console atau jalankan via CLI:
     ```bash
     aws dynamodb get-item \
       --table-name corp-tflocks-production-secure \
       --key '{"LockID": {"S": "corp-tfstate/terraform.tfstate-md5"}}'
     ```
  3. Lepaskan kunci secara terkontrol menggunakan ID transaksi spesifik:
     ```bash
     terraform force-unlock a1b2c3d4-e5f6-7890-abcd-1234567890ef
     ```
  4. *PERINGATAN:* Jangan pernah menghapus row DynamoDB secara manual jika Anda tidak yakin proses pipeline sudah benar-benar mati.

### Mistake 3: State Lineage Mismatch
- **Gejala:** State file ditimpa atau backend menolak sinkronisasi dengan pesan:
  ```
  Error: State lineage does not match: remote has lineage X, local has lineage Y
  ```
- **Akar Masalah:** Developer melakukan inisialisasi ulang (`terraform init`) dengan state lokal baru ke backend yang sudah berisi data project lain tanpa sinkronisasi migrasi state.
- **Remediasi:** Pastikan bucket backend benar. Jika workspace memang harus dimigrasikan ke lineage remote, tarik remote state terlebih dahulu:
  ```bash
  terraform state pull > upstream-state.json
  # Verifikasi integritas lineage pada file upstream-state.json
  ```

---

## 11. Best Practices (Production Checklist)

- [ ] **Enforce Backend Locking:** Wajib mengaktifkan `dynamodb_table` (AWS), GCS Lock, atau Azure Blob Lease pada konfigurasi backend.
- [ ] **KMS Envelope Encryption:** Selalu simpan state dengan Customer Managed Key (CMK) dengan rotasi otomatis aktif.
- [ ] **S3 Object Versioning & Object Lock:** Aktifkan S3 Versioning untuk rollback instan saat terjadi korupsi data. Tambahkan MFA Delete untuk lingkungan *Critical-Production*.
- [ ] **Least Privilege Backend IAM Policies:** Pipeline deployment role hanya memiliki akses `s3:GetObject`, `s3:PutObject` ke prefix spesifik (bukan global wildcards).
- [ ] **No Secrets in Plain-Text:** Hindari resource penampung secret yang disimpan dalam state. Gunakan dynamic integrations (misal: AWS Secrets Manager, HashiCorp Vault Secrets Engine) langsung pada run-time bootstrap resource.
- [ ] **Automated State Drift Detection:** Jalankan pipeline scheduled `terraform plan -detailed-exitcode` harian tanpa apply untuk mendeteksi drift tanpa lock kontinyu.
- [ ] **Declarative over Imperative Refactoring:** Prioritaskan penggunaan blok HCL `moved {}` daripada perintah manual CLI `terraform state mv` agar sejarah refactoring terlacak di version control (Git).

---

## 12. Hands-on Practice: Simulating Lock Contention & State Operations

Simpan seluruh file praktikum ini di direktori: `hands-on/m02/`

### File Setup 1: `hands-on/m02/backend-infra.tf`
Script bootstrapping backend remote lokal (simulasi target backend).

```hcl
provider "aws" {
  region = "ap-southeast-1"
}

resource "random_id" "suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "lab_state" {
  bucket        = "lab-tfstate-${random_id.suffix.hex}"
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "lab_state" {
  bucket = aws_s3_bucket.lab_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_dynamodb_table" "lab_locks" {
  name         = "lab-tflocks-${random_id.suffix.hex}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }
}

output "state_bucket_name" {
  value = aws_s3_bucket.lab_state.bucket
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.lab_locks.name
}
```

### File Setup 2: `hands-on/m02/workload/main.tf`
Target implementasi backend locking dan resource sleep untuk memicu simulasi race condition.

```hcl
terraform {
  required_version = ">= 1.5.0"
  backend "s3" {
    # Nilai diisi setelah backend-infra selesai di-apply
    bucket         = "REPLACE_WITH_BUCKET_NAME"
    key            = "workload/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "REPLACE_WITH_DDB_TABLE_NAME"
  }
}

provider "aws" {
  region = "ap-southeast-1"
}

# Resource tiruan yang memakan waktu apply lama
resource "null_resource" "long_running_task" {
  provisioner "local-exec" {
    command = "sleep 45"
  }
}

resource "aws_ssm_parameter" "system_metric" {
  name  = "/lab/m02/status"
  type  = "String"
  value = "Operational"
}
```

### Langkah Instruksi Hands-on

1. **Inisialisasi & Buat Backend Engine:**
   ```bash
   cd hands-on/m02/
   terraform init
   terraform apply -auto-approve
   # Catat output: state_bucket_name dan dynamodb_table_name
   ```

2. **Konfigurasi Workload Directory:**
   ```bash
   cd workload/
   # Ubah konfigurasi backend "s3" dengan nama bucket & dynamodb table dari step 1
   terraform init
   ```

3. **Simulasi Collision Race Condition (Terminal Multi-Session):**
   - **Terminal 1:** Jalankan apply:
     ```bash
     terraform apply -auto-approve
     ```
     *(Proses akan terhenti selama 45 detik pada null_resource).*
   - **Terminal 2:** Segera jalankan apply secara bersamaan saat Terminal 1 masih aktif:
     ```bash
     terraform apply -auto-approve
     ```
   - **Observasi Output Terminal 2:**
     Perhatikan kegagalan seketika dari Terraform Lock Manager:
     ```
     Error: Error acquiring the state lock
     Lock Info:
       Operation: OperationTypeApply
       ...
     ```

4. **Investigasi Kunci via AWS CLI:**
   ```bash
   aws dynamodb scan --table-name <NAMA_DYNAMODB_DARI_STEP_1>
   # Bedah payload JSON Lock Info yang tersimpan di field LockID
   ```

5. **Praktik State Refactoring via CLI:**
   Pindahkan resource `aws_ssm_parameter.system_metric` ke identifier baru tanpa regenerasi di cloud provider:
   ```bash
   terraform state mv aws_ssm_parameter.system_metric aws_ssm_parameter.system_metric_v2
   ```
   Buka file `main.tf`, ubah label deklarasi resource dari `system_metric` menjadi `system_metric_v2`. Jalankan `terraform plan` dan validasi bahwa sistem melaporkan:
   `No changes. Your infrastructure matches the configuration.`

---

## 13. Exercises

### Level Easy
Tarik salinan binary remote state aktif ke file JSON lokal, parsing menggunakan tool CLI `jq`, lalu ekstrak nilai `serial` dan `lineage`-nya.  
*Petunjuk Verifikasi:* Gunakan `terraform state pull | jq '{serial: .serial, lineage: .lineage}'`.

### Level Medium
Diberikan konfigurasi di mana suatu resource `aws_s3_bucket.legacy_logs` telah dihapus dari file `.tf`, tetapi resource fisik di cloud *tidak boleh* dihancurkan. Hapus referensi resource tersebut dari monitoring state engine tanpa memicu penghapusan API di AWS.  
*Petunjuk Verifikasi:* Gunakan `terraform state rm`. Jalankan `terraform plan` untuk memastikan tidak ada perintah destroy ke S3 bucket bersangkutan.

### Level Hard
Sebuah state file mengalami desinkronisasi. Resource `aws_security_group.ingress_web` tercatat di AWS, namun hilang sepenuhnya dari file `terraform.tfstate` lokal akibat force un-lock atau interrupt signal yang terputus. Buat blok kode HCL kosong dan gunakan fitur **declarative import block** (Terraform $\ge$ 1.5) untuk mengimpor kembali resource fisik tersebut ke dalam state file secara utuh dan terverifikasi bersih saat dieksekusi via `terraform plan`.

---

## 14. Enterprise Challenge (Real-World Disaster Recovery)

### Studi Kasus
Terjadi kegagalan jaringan saat deploy darurat di lingkungan production. Administrator AWS menemukan:
1. State file lokal di bucket remote terpotong (*0 bytes corruption*) akibat race condition pada runner yang tidak mengonfigurasi DynamoDB lock table dengan benar.
2. Production traffic sedang berjalan pada puluhan VPC, RDS Aurora Cluster, dan EKS cluster yang tidak lagi terlacak oleh file state.
3. Versi S3 Object Versioning secara tidak sengaja dimatikan seminggu sebelumnya oleh audit IAM yang salah sasaran.

### Tugas Tantangan
Rancang dan dokumentasikan **SOP (Standard Operating Procedure) State Reconstruction Plan**:
- Bagaimana Anda membangun kembali state file baru yang utuh dari nol untuk infrastruktur yang masih aktif tersebut?
- Bagaimana Anda mengotomasi pembuatan file konfigurasi HCL dan pengisian state secara bersamaan menggunakan Terraform declarative generation (`terraform plan -generate-config-out=generated.tf`)?
- Bagaimana Anda memvalidasi bahwa state hasil rekonstruksi memiliki konfigurasi $100\%$ drift-free dari resource nyata tanpa memicu insiden *re-create* (destroy and recreate) pada database production?

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Soal)
1. **Apa fungsi utama dari atribut `lineage` di dalam file state Terraform?**
   - A. Menghitung berapa kali resource diubah.
   - B. UUID unik yang mengidentifikasi siklus hidup state dan mencegah penggabungan dua state yang berbeda identitas.
   - C. Menyimpan string enkripsi KMS.
   - D. Menunjukkan versi provider HashiCorp.
   *Jawaban:* B. Lineage adalah UUID statis yang dibuat saat state pertama kali lahir.

2. **Atribut apa dalam file state JSON yang otomatis bertambah nilainya ($+1$) setiap mutasi berhasil diaplikasikan?**
   - A. `version`
   - B. `lineage`
   - C. `serial`
   - D. `schema_version`
   *Jawaban:* C. `serial` adalah counter inkremental monotonik.

3. **Operasi DynamoDB apa yang digunakan oleh backend S3 Terraform untuk mengunci state secara atomik?**
   - A. `BatchWriteItem`
   - B. `PutItem` dengan conditional expression checking ketiadaan item.
   - C. `UpdateItem` tanpa kondisi.
   - D. `Scan` tabel secara periodik.
   *Jawaban:* B. Menggunakan conditional write atomik untuk mencegah overwrite race condition.

4. **Manakah blok HCL yang direkomendasikan sejak Terraform 1.1 untuk memindahkan identifier resource di HCL tanpa menghancurkan resource fisik?**
   - A. `migrated {}`
   - B. `state {}`
   - C. `moved {}`
   - D. `transfer {}`
   *Jawaban:* C. Blok `moved` memungkinkan refactoring dideklarasikan langsung di kode.

5. **Apa dampak langsung jika kita tidak mengonfigurasi DynamoDB table pada backend S3 di lingkungan multi-user CI/CD?**
   - A. State file akan otomatis disimpan di hard disk runner.
   - B. Terbukanya risiko korupsi state dan race condition jika dua pipeline berjalan bersamaan.
   - C. S3 akan menolak upload file state karena enkripsi gagal.
   - D. Performa Terraform plan menjadi dua kali lebih lambat.
   *Jawaban:* B. Tanpa lock engine, tidak ada mutual exclusion.

---

### Bagian 2: Intermediate (5 Soal)
6. **Perintah `terraform force-unlock <LOCK-ID>` harus digunakan hanya ketika...**
   - A. `terraform apply` gagal karena syntax error pada kode HCL.
   - B. State lock tersisa akibat runner deployment mati mendadak dan telah dikonfirmasi tidak ada proses terraform lain yang aktif.
   - C. Developer ingin menjalankan deploy tanpa harus menunggu review Pull Request selesai.
   - D. Nilai serial di file state lokal lebih rendah daripada di remote backend.
   *Jawaban:* B. Force unlock adalah intervensi manual berbahaya yang hanya boleh dijalankan jika proses pengunci terbukti sudah non-aktif.

7. **Mengapa integrasi antar-arsitektur micro-state lebih disarankan menggunakan dynamic lookup (misal: AWS SSM / HashiCorp Vault) daripada `terraform_remote_state`?**
   - A. Dynamic lookup tidak memerlukan koneksi jaringan internet.
   - B. `terraform_remote_state` mengharuskan consumer memiliki hak baca ke seluruh state upstream, mengekspos data sensitif dan memperbesar coupling.
   - C. `terraform_remote_state` tidak kompatibel dengan AWS S3.
   - D. SSM Parameter store gratis sedangkan state file berbayar.
   *Jawaban:* B. Prinsip least privilege; membaca state upstream berarti dapat membaca seluruh output dan atribut internal upstream yang sensitif.

8. **Saat melakukan `terraform state rm aws_instance.web`, apa yang terjadi pada server EC2 fisik di AWS?**
   - A. Instance EC2 langsung terminated oleh AWS API.
   - B. Instance EC2 di-stop secara otomatis.
   - C. Instance EC2 tetap menyala normal, tetapi kontrolnya dilepas sepenuhnya dari state Terraform.
   - D. Instance EC2 di-snapshot menjadi AMI sebelum dimatikan.
   *Jawaban:* C. `state rm` hanya memutus ikatan pelacakan metadata dari state file tanpa mengirim panggilan API destruksi ke cloud provider.

9. **Jika ada modifikasi manual di AWS Console pada security group (state drift), kapan Terraform mendeteksi perubahan tersebut?**
   - A. Hanya saat perintah `terraform destroy` dijalankan.
   - B. Pada fase `Refresh` di siklus `plan` atau `apply` saat memanggil read API provider.
   - C. Saat instance di-restart.
   - D. Terraform tidak bisa mendeteksi perubahan yang dibuat dari console AWS.
   *Jawaban:* B. Fase Refresh meng-query status riil dari Cloud Provider API dan membandingkannya dengan in-memory graph.

10. **Apa kegunaan dari atribut `sensitive_attributes: []` pada instance state JSON?**
    - A. Mengenkripsi S3 bucket secara hardware.
    - B. Daftar path atribut yang nilainya disembunyikan dari output log konsol CLI guna mencegah kebocoran informasi kredensial.
    - C. Otomatis menghapus password setiap 30 hari.
    - D. Menandai bahwa resource harus dihapus menggunakan otentikasi MFA.
    *Jawaban:* B. Terraform melacak path atribut yang dideklarasikan sebagai `sensitive = true` agar tidak di-print di output konsol.

---

### Bagian 3: Skenario Kasus Produksi (3 Soal)

11. **Skenario:** Tim platform Anda mendapati error berikut saat pipeline deploy EKS dijalankan:
    `Error: Provider produced inconsistent final plan: When expanding plan to include new values to be set in configuration, a change to aws_eks_cluster.main.version was detected.`  
    Setelah diinvestigasi, ternyata versi Kubernetes di AWS Console telah di-upgrade secara manual oleh tim security semalam sebelumnya tanpa mengubah file HCL.  
    **Tindakan arsitektur mitigasi apa yang paling tepat untuk mengatasi hal ini secara aman tanpa rollback cluster?**
    - A. Hapus instance EKS dari AWS console lalu apply ulang via Terraform.
    - B. Jalankan `terraform apply -target=aws_eks_cluster.main` secara paksa.
    - C. Sinkronisasikan versi di file deklarasi HCL dengan versi riil di AWS Console, jalankan `terraform refresh`, lalu validasi clean plan.
    - D. Hapus file `terraform.tfstate` dari S3 bucket dan lakukan `init`.
    *Jawaban:* C. Deklarasi HCL harus diperbarui menyamai kondisi real-world yang sah agar state refresh dan graph validator mencapai konvergensi konsisten.

12. **Skenario:** Anda diminta menurunkan waktu eksekusi pipeline CI/CD monolithic Terraform yang mengelola 1.500 resources. Analisis tracing menunjukkan 85% waktu habis pada panggilan API AWS EC2 Describe* selama fase plan. Pipeline berjalan 40 kali sehari.  
    **Strategi arsitektural jangka pendek paling efektif tanpa mengubah struktur kode secara masif adalah...**
    - A. Menggunakan flag `-refresh=false` pada perintah `plan` di pipeline rutin dan menjalankan scheduled job audit drift terpisah dengan refresh aktif.
    - B. Mengganti semua backend S3 menjadi local file.
    - C. Mematikan S3 bucket versioning.
    - D. Mengubah DynamoDB billing mode dari On-Demand ke Provisioned.
    *Jawaban:* A. Melewati fase refresh (`-refresh=false`) mempercepat plan karena Terraform mempercayai state yang ada; drift audit dipindahkan ke pipeline monitoring terpisah.

13. **Skenario:** Seorang junior engineer melakukan merge PR yang berisi blok deklarasi bucket S3 baru. Namun, bucket dengan nama yang sama persis ternyata telah dibuat secara manual di AWS Console oleh tim DevOps minggu lalu. Saat pipeline dijalankan, proses gagal dengan error: `BucketAlreadyOwnedByYou`.  
    **Langkah deklaratif paling modern (Terraform $\ge$ 1.5) untuk menyelesaikan masalah ini tanpa downtime atau re-creation adalah...**
    - A. Mengganti nama bucket baru di kode HCL.
    - B. Menggunakan block deklaratif `import { to = aws_s3_bucket.new_bucket id = "nama-bucket-eksisting" }` di dalam file HCL.
    - C. Menghapus manual bucket yang ada di console AWS.
    - D. Melakukan force unlock pada DynamoDB table.
    *Jawaban:* B. Fitur native `import` block memungkinkan adopsi resource eksisting secara deklaratif dan aman melalui alur code review standar.

---

## 16. Summary
- **State File adalah Relational Graph:** File state bukan sekadar catatan riwayat, melainkan representasi matematis dari resource graph yang memetakan HCL ke cloud reality. Integritasnya dijaga oleh parameter `lineage` dan `serial`.
- **Distributed Lock adalah Mutex Vital:** Mengombinasikan AWS S3 dengan DynamoDB conditional write memastikan bahwa tidak ada dua proses yang dapat memanipulasi state file pada saat yang sama.
- **Dekomposisi adalah Kunci Skalabilitas:** Arsitektur state perusahaan harus didekomposisi berdasarkan *lifecycle domains* (Network, Platform, Compute) guna meminimalkan blast radius dan degradasi performa akibat API rate limiting.
- **Contract-Based Loose Coupling:** Hindari kopling ketat melalui `terraform_remote_state`. Gunakan parameter store atau service discovery (seperti AWS SSM atau Vault) untuk mengekspos atribut antar-state secara decoupled dan aman.
- **Modern Refactoring:** Manfaatkan deklarasi HCL tingkat lanjut seperti `moved` blocks dan `import` blocks untuk memigrasikan atau mengadopsi infrastruktur tanpa downtime dan tanpa risiko korupsi state secara manual.