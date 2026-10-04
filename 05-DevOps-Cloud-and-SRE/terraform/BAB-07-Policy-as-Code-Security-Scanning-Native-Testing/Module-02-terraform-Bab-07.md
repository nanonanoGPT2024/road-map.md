# BAB 07: Policy-as-Code, Security Scanning & Native Testing
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

1. **Mendesain dan Mengimplementasikan Arsitektur Policy-as-Code (PaC) Berskala Enterprise**: Membangun *governance gate* deterministik menggunakan Open Policy Agent (OPA/Rego) dan Trivy/Checkov yang memvalidasi *abstract syntax tree* (AST) serta representasi JSON dari *Terraform execution plan*.
2. **Menguasai Native Testing Framework (`terraform test`)**: Mengimplementasikan pengujian unit, integrasi, dan skenario kegagalan sintetis (*negative assertions*) menggunakan sintaks `.tftest.hcl` bawaan Terraform v1.6+, lengkap dengan *mock provider* dan *state overriding*.
3. **Mengotomatisasi DevSecOps Shift-Left Pipeline**: Menyusun alur CI/CD bertingkat (*multi-stage gate*) yang mengeksekusi *static analysis*, *mocked unit testing*, *plan-time policy enforcement*, dan *vulnerability scanning* dengan SLA eksekusi pipeline di bawah 5 menit.
4. **Mengelola Mitigasi dan Penanganan "Unknown Values"**: Memecahkan anomali evaluasi kebijakan yang disebabkan oleh nilai komputasi run-time (*computed attributes*) pada fase perencanaan Terraform.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:

*   **Terraform Core Internals**: Siklus hidup *state*, *dependency graph construction* (DAG), dan perbedaan semantik antara *Configuration*, *State*, dan *Execution Plan*.
*   **JSON Processing & Querying**: Memahami struktur skema output `terraform show -json` (khususnya blok `resource_changes`, `configuration`, dan `planned_values`).
*   **Logika Deklaratif & Set Theory**: Pemahaman dasar mengenai evaluasi *rule-based* (seperti Datalog/Prolog) untuk mempermudah penulisan OPA/Rego.
*   **CI/CD Pipeline Architecture**: Pengalaman mengonfigurasi GitHub Actions, GitLab CI, atau Azure DevOps.

---

### 3. Concept & Internal Architecture

Implementasi pengujian dan kepatuhan infrastruktur modern di Terraform beroperasi pada tiga layer representasi data:

```
[HCL Code (.tf)] 
       │
       ▼ (Syntax & Static Structure)
┌────────────────────────────────────────────────────────┐
│ Layer 1: Static AST Analysis (Checkov, Trivy, TFLint) │
└────────────────────────────────────────────────────────┘
       │
       ▼ (CLI Engine: terraform init & graph compile)
┌────────────────────────────────────────────────────────┐
│ Layer 2: Native Test Engine (`terraform test`)         │
│  - Mock Providers (Tanpa Cloud API Call)               │
│  - Ephemeral Memory State                              │
└────────────────────────────────────────────────────────┘
       │
       ▼ (terraform plan -out=tfplan.binary)
       │ (terraform show -json tfplan.binary > plan.json)
┌────────────────────────────────────────────────────────┐
│ Layer 3: Plan-Time Policy-as-Code (OPA / Rego)         │
│  - Evaluasi Resource Changes                           │
│  - Evaluasi Computed vs Known Values                   │
│  - Blast Radius & Blast Budget Enforcement             │
└────────────────────────────────────────────────────────┘
```

#### A. Anatomi JSON Execution Plan (`terraform show -json`)

Ketika Terraform menyusun rencana eksekusi, Terraform melakukan serialisasi DAG ke dalam format JSON dengan tiga node utama yang dianalisis oleh Policy Engine:

1.  `configuration`: Merefleksikan kode HCL statis termasuk ekspresi yang belum dievaluasi, variabel, dan referensi modul.
2.  `planned_values`: State proyeksi akhir dari seluruh infrastruktur jika *plan* diaplikasikan. Atribut yang bergantung pada output cloud API yang belum dibuat akan ditandai atau dihilangkan.
3.  `resource_changes`: Array perubahan inkremental yang berisi metadata:
    *   `actions`: Array aksi yang akan dilakukan (`["create"]`, `["update"]`, `["delete", "create"]` untuk replace, atau `["no-op"]`).
    *   `before`: Nilai atribut sebelum plan dijalankan (berasal dari *current state*).
    *   `after`: Nilai atribut yang diproyeksikan.
    *   `after_unknown`: Peta boolean yang menandai apakah suatu atribut bernilai *computed* (misal: ID subnet baru yang baru didapat setelah VPC dibuat).

Engine OPA mengevaluasi node `resource_changes` untuk memastikan integritas perubahan:

$$\forall r \in \text{resource\_changes}, \quad \text{action}(r) \cap \{\text{create}, \text{update}\} \neq \emptyset \implies \text{validate}(r.\text{after})$$

#### B. Internal Engine `terraform test`

Mulai Terraform 1.6, HashiCorp mengintegrasikan *test harness native* langsung ke dalam Terraform core engine. Berbeda dengan tools eksternal seperti Terratest yang mengeksekusi Go binary via cloud provider API riil, `terraform test`:

1.  **Mengisolasi State**: Setiap file `.tftest.hcl` dieksekusi dalam memori (*in-memory state*) yang bersifat sementara (*ephemeral*). State langsung dimusnahkan setelah pengujian selesai.
2.  **Mendukung Mock Provider (v1.7+)**: Engine Terraform dapat mengabaikan inisialisasi provider asli dan menyuntikkan *synthesized data* langsung ke DAG. Ini menghilangkan latensi jaringan, kebutuhan autentikasi cloud API, dan biaya provisi infrastruktur selama fase verifikasi logika modul.
3.  **Eksekusi Berurutan via Run Blocks**: Blok `run` bertindak seperti langkah pengujian (*test assertion steps*) yang dapat mempertahankan state antar-blok atau mengisolasinya menggunakan perintah `command = plan` atau `command = apply`.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Code Review Manual & Terratest) | Pendekatan Modern (Native Test + OPA + Static Scan) |
| :--- | :--- | :--- |
| **Feedback Loop** | 2 - 48 jam (menunggu reviewer atau eksekusi cloud provisioning nyata). | < 2 menit dalam pipeline lokal / CI runner. |
| **Infrastruktur Biaya**| Tinggi (Terratest membuat resource AWS/GCP riil lalu menghancurkannya; risiko *orphan resources* tinggi). | **Nol** untuk unit tests (berjalan via mock provider dan static plan evaluation). |
| **Coverage Scope** | Seringkali hanya menguji skenario "happy path" karena biaya provisi infrastruktur nyata. | Komprehensif: Menguji ribuan permutasi input, batasan boundary CIDR, dan skenario penolakan (*negative tests*). |
| **Enforcement Point**| *Soft governance* via human review; inkonsisten dan rentan *human error*. | *Hard gate enforcement*: Eksekusi dibatalkan otomatis via exit code `1` jika melanggar kebijakan. |

*   **Static Scanning (Checkov/Trivy)**: Berfungsi menganalisis miskonfigurasi keamanan statis yang diketahui (misal: port 22 terbuka ke `0.0.0.0/0`, unencrypted EBS).
*   **Native Testing (`terraform test`)**: Berfungsi memverifikasi kebenaran fungsional logika HCL, *input validation*, output *computed*, dan orkestrasi internal modul.
*   **Policy-as-Code (OPA/Rego)**: Berfungsi menegakkan aturan bisnis tingkat organisasi (misal: batas biaya/blast radius, kepatuhan penamaan multi-region, restriksi IAM permission boundaries).

---

### 5. How (Workflow Detail)

Alur pipeline produksi mengimplementasikan teknik "Shift-Left Verification" bertingkat:

```
[Developer Git Push]
         │
         ├───> [1. Pre-commit Phase]
         │        ├── terraform fmt -check
         │        ├── terraform validate
         │        └── tflint / checkov (local scan)
         │
         ├───> [2. Fast-Feedback Unit Tests]
         │        └── terraform test (Mock Providers, Command: plan)
         │
         ├───> [3. Integration Unit Tests]
         │        └── terraform test (Isolated Sandbox Env, Command: apply)
         │
         ├───> [4. Speculative Plan Generation]
         │        ├── terraform plan -out=tfplan.binary
         │        └── terraform show -json tfplan.binary > tfplan.json
         │
         └───> [5. Enterprise Policy & Security Gate]
                  ├── OPA / Conftest evaluation over tfplan.json
                  └── Trivy / Checkov scan over tfplan.json
                           │
                 [All Checks Passed?]
                  ├── YES ──> Allow PR Merge & Trigger CD Apply
                  └── NO  ──> Pipeline Broken (Exit 1) + Post PR Comment
```

1.  **Fase 1 (Pre-commit)**: Eksekusi format check dan linter statis secara lokal untuk menyaring *syntax error* dan anti-pattern mendasar.
2.  **Fase 2 (Unit Testing dengan Mock)**: Mengeksekusi file `.tftest.hcl` menggunakan `mock_provider`. Menguji seluruh percabangan kondisi logika (`count`, `for_each`, `can()`) tanpa koneksi ke cloud provider.
3.  **Fase 3 (Integration Tests)**: Menjalankan skenario *end-to-end* berskala kecil pada akun *ephemeral/sandbox* terisolasi.
4.  **Fase 4 (Plan Serialisasi)**: Menghasilkan binary plan dan mengubahnya menjadi format JSON yang canonical untuk dikonsumsi oleh tool pihak ketiga.
5.  **Fase 5 (Gate Policy Enforcement)**: OPA mengevaluasi `tfplan.json`. Jika ada pelanggaran dengan *severity* `CRITICAL` atau `HIGH`, exit code non-zero di-trigger, menghentikan deployment sebelum *state lock* atau perubahan cloud terjadi.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Keamanan Bandar Udara Enterprise

*   **Static Scanner (TFLint/Trivy)** = *CCTV & Body Temperature Thermal Camera*. Memeriksa secara pasif apakah penumpang membawa atribut fisik yang berbahaya secara kasat mata sejak pintu masuk bandara.
*   **Native Testing (`terraform test`)** = *Simulasi Penerbangan / Pilot Cockpit Check*. Memastikan semua instrumen dan sistem hidrolik bekerja harmonis sesuai rencana operasi sebelum pesawat diizinkan bergerak ke landasan pacu.
*   **Policy-as-Code (OPA/Rego)** = *Pemeriksaan Dokumen Imigrasi & Bea Cukai*. Memeriksa izin legalitas, kuota barang bawaan, dan kesesuaian paspor dengan database regulasi negara sebelum cap visa keberangkatan diberikan.

#### Diagram Interaksi Evaluasi Plan-Time

```
                                 TERRAFORM ENGINE & OPA INTERACTION
  ┌────────────────────────────────────────────────────────────────────────────────────────┐
  │                                                                                        │
  │   main.tf ──────┐                                                                      │
  │   variables.tf ─┼──> [ terraform plan ] ──> tfplan.binary                             │
  │                 │                                │                                     │
  │                 │                                ▼                                     │
  │                 │                    [ terraform show -json ]                          │
  │                 │                                │                                     │
  │                 ▼                                ▼                                     │
  │          [ AST Parser ]                     tfplan.json                                │
  │                 │                                │                                     │
  │                 ▼                                ▼                                     │
  │        ┌─────────────────┐             ┌──────────────────┐                            │
  │        │ Trivy / Checkov │             │  OPA Engine /    │                            │
  │        │  (Static AST)   │             │  Conftest CLI    │ <── enterprise_rules.rego  │
  │        └────────┬────────┘             └────────┬─────────┘                            │
  │                 │                               │                                      │
  │                 ▼                               ▼                                      │
  │           Static Issues                   Policy Violations                            │
  │                 │                               │                                      │
  │                 └───────────────┬───────────────┘                                      │
  │                                 ▼                                                      │
  │                    ┌─────────────────────────┐                                         │
  │                    │ Decision Gate Manager   │                                         │
  │                    └────────────┬────────────┘                                         │
  │                                 │                                                      │
  │                 ┌───────────────┴───────────────┐                                      │
  │                 ▼                               ▼                                      │
  │           [ Exit Code 0 ]                 [ Exit Code 1 ]                              │
  │           (Merge Allowed)              (Block Deployment)                              │
  │                                                                                        │
  └────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Native Unit Testing dengan Mock Provider

Struktur direktori:
```text
├── main.tf
└── tests
    └── bucket_validation.tftest.hcl
```

`main.tf`:
```hcl
variable "environment" {
  type        = string
  description = "Target deployment environment"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "bucket_prefix" {
  type        = string
  description = "Prefix for the S3 bucket name"
}

resource "aws_s3_bucket" "audit_logs" {
  bucket = "${var.bucket_prefix}-${var.environment}-audit-log"

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

output "bucket_arn" {
  value       = aws_s3_bucket.audit_logs.arn
  description = "The ARN of the provisioned bucket"
}
```

`tests/bucket_validation.tftest.hcl`:
```hcl
mock_provider "aws" {}

# Unit test 1: Validasi penamaan bucket pada production
run "verify_prod_bucket_naming" {
  command = plan

  variables {
    environment   = "prod"
    bucket_prefix = "corp-fintech"
  }

  assert {
    condition     = aws_s3_bucket.audit_logs.bucket == "corp-fintech-prod-audit-log"
    error_message = "Bucket name did not match expected production convention."
  }

  assert {
    condition     = aws_s3_bucket.audit_logs.tags["Environment"] == "prod"
    error_message = "Incorrect Environment tag applied."
  }
}

# Unit test 2: Negative test memastikan invalid input gagal
run "verify_invalid_environment_rejected" {
  command = plan

  variables {
    environment   = "invalid_env"
    bucket_prefix = "corp-fintech"
  }

  expect_failures = [
    var.environment
  ]
}
```

Eksekusi:
```bash
$ terraform test
tests/bucket_validation.tftest.hcl... in progress
  run "verify_prod_bucket_naming"... success
  run "verify_invalid_environment_rejected"... success
tests/bucket_validation.tftest.hcl... tearing down
All tests passed.
```

---

#### B. Practical Example: Production-Grade S3 Module dengan Enkripsi KMS, State Overrides, & OPA Guardrails

##### 1. Modul Infrastruktur (`main.tf`)
```hcl
terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
  }
}

variable "environment" {
  type = string
}

variable "kms_master_key_id" {
  type        = string
  description = "Customer Managed Key (CMK) ARN for SSE-KMS"
}

resource "aws_s3_bucket" "data_lake" {
  bucket        = "corp-datalake-${var.environment}-tier1"
  force_destroy = var.environment == "prod" ? false : true

  tags = {
    Environment = var.environment
    DataClass   = "Confidential"
    Compliance  = "PCI-DSS"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "kms_encryption" {
  bucket = aws_s3_bucket.data_lake.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = var.kms_master_key_id
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "enforce_pab" {
  bucket = aws_s3_bucket.data_lake.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

output "s3_id" {
  value = aws_s3_bucket.data_lake.id
}
```

##### 2. Native Multi-Run Test dengan Data Source Overrides (`tests/s3_security_suite.tftest.hcl`)
```hcl
mock_provider "aws" {
  mock_data "aws_kms_key" {
    defaults = {
      arn = "arn:aws:kms:ap-southeast-1:112233445566:key/abc-123-mock"
    }
  }
}

# Step 1: Validasi struktur plan dan enkripsi KMS wajib
run "evaluate_kms_encryption_plan" {
  command = plan

  variables {
    environment       = "prod"
    kms_master_key_id = "arn:aws:kms:ap-southeast-1:112233445566:key/abc-123-mock"
  }

  assert {
    condition     = aws_s3_bucket_server_side_encryption_configuration.kms_encryption.rule[0].apply_server_side_encryption_by_default[0].sse_algorithm == "aws:kms"
    error_message = "Security compliance failed: S3 must enforce aws:kms encryption."
  }

  assert {
    condition     = aws_s3_bucket_public_access_block.enforce_pab.block_public_acls == true
    error_message = "Security compliance failed: Public Access Block is incomplete."
  }
}

# Step 2: Validasi pencegahan force_destroy pada production
run "prevent_force_destroy_in_prod" {
  command = plan

  variables {
    environment       = "prod"
    kms_master_key_id = "arn:aws:kms:ap-southeast-1:112233445566:key/abc-123-mock"
  }

  assert {
    condition     = aws_s3_bucket.data_lake.force_destroy == false
    error_message = "Disaster Recovery violation: force_destroy must be false in production environments."
  }
}
```

##### 3. Advanced Enterprise OPA Rego Policy (`policies/s3_guardrails.rego`)
Kebijakan ini mengevaluasi `resource_changes` dari file `tfplan.json`, memverifikasi keberadaan KMS encryption, public access block, dan proteksi dari deletion cascade pada environment production:

```rego
package terraform.security

import future.keywords.in

default allow = false

# Whitelist environment yang valid
valid_environments := ["dev", "staging", "prod"]

# Koleksi seluruh pelanggaran
violations[msg] {
    some resource in input.resource_changes
    resource.type == "aws_s3_bucket"
    "create" in resource.change.actions
    
    env := resource.change.after.tags.Environment
    not env in valid_environments
    
    msg := sprintf("Resource '%v' has invalid Environment tag '%v'. Must be one of %v", [
        resource.address, env, valid_environments
    ])
}

violations[msg] {
    some resource in input.resource_changes
    resource.type == "aws_s3_bucket"
    resource.change.after.tags.Environment == "prod"
    resource.change.after.force_destroy == true
    
    msg := sprintf("CRITICAL: Resource '%v' sets force_destroy=true in production!", [
        resource.address
    ])
}

# Verifikasi relasi: Tiap s3 bucket yang dibuat wajib memiliki Public Access Block
violations[msg] {
    some bucket in input.resource_changes
    bucket.type == "aws_s3_bucket"
    "create" in bucket.change.actions
    
    pab_associated := [pab | 
        some pab in input.resource_changes
        pab.type == "aws_s3_bucket_public_access_block"
        pab.change.after.bucket == bucket.change.after.bucket
        pab.change.after.block_public_acls == true
        pab.change.after.block_public_policy == true
        pab.change.after.ignore_public_acls == true
        pab.change.after.restrict_public_buckets == true
    ]
    
    count(pab_associated) == 0
    msg := sprintf("COMPLIANCE VIOLATION: Bucket '%v' does not have an attached fully-restricted aws_s3_bucket_public_access_block.", [
        bucket.address
    ])
}

# Izinkan apply hanya bila tidak ada satupun pelanggaran
allow {
    count(violations) == 0
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks
Sebuah institusi perbankan digital multinasional memiliki 450+ developer yang terbagi dalam 60 tim produk otonom. Organisasi menggunakan model Terraform terdistribusi (masing-masing tim mengelola AWS infrastructure modul sendiri) dengan deploy cadence rata-rata 180 PR per hari.

#### Permasalahan (Root Cause)
1.  **Lead Time Lambat**: Tim Cloud Security Reviewer menjadi *bottleneck*. Rata-rata waktu tunggu manual approval untuk perubahan infrastruktur memakan waktu 36 jam.
2.  **Audit Drift & Security Incidents**: Terjadi insiden keamanan di mana engineer secara tidak sengaja membuka Security Group RDS Postgres (`0.0.0.0/0`) pada fase debugging darurat dan men-deploy-nya ke staging/production. Tim reviewer gagal mendeteksi hal tersebut di antara 1.200 baris perubahan `terraform plan`.
3.  **Biaya Uji Coba Eksplosif**: Tim menggunakan modul *Terratest* yang membuat VPC nyata, NAT Gateway, dan database RDS saat CI berjalan. Biaya AWS untuk testing sementara mencapai $14.000/bulan hanya untuk *spun-up-and-destroy resources*, belum termasuk overhead waktu pipeline (25 menit per build).

#### Solusi Arsitektural
1.  **Implementasi Full Shift-Left Pipeline**:
    *   Mengganti 80% suite *Terratest* dengan `terraform test` menggunakan **Mock Providers**. Waktu unit testing terpangkas dari 25 menit menjadi 18 detik.
    *   Menghilangkan ketergantungan cloud credential pada fase awal CI pipeline.
2.  **Penerapan Two-Tier Policy Enforcement**:
    *   **Tier 1 (Trivy Static AST Scanner)**: Dijalankan via pre-commit hook dan CI runner untuk mendeteksi common CVEs serta static anti-patterns.
    *   **Tier 2 (OPA Engine pada Serialized Plan)**: Setiap pull request secara otomatis menghasilkan `plan.json`. OPA mengevaluasi aturan institusional: pembatasan ukuran instance EC2/RDS, pemaksaan tag PCI-DSS, validasi mutlak tidak adanya CIDR `0.0.0.0/0` pada ingress port non-HTTP/HTTPS, serta kalkulasi *Blast Radius* (maksimal modifikasi 15 resource per pipeline PR tanpa approval VP of Engineering).

#### Hasil Metrik (Setelah 6 Bulan)
*   **Pipeline SLA**: Turun dari 25 menit menjadi **3 menit 45 detik**.
*   **Security Incidents**: **0 miskonfigurasi lolos** ke staging maupun production selama periode audit 180 hari.
*   **AWS Cost Reduction**: Penghematan langsung sebesar **$14.000/bulan** dari pemangkasan provisioning pengujian sementara.
*   **Engineering Lead Time**: Waktu deployment PR turun dari 36 jam menjadi **di bawah 30 menit** (full automated clearance).

---

### 9. Trade-offs

| Kategori | Pendekatan Terpilih | Alternatif | Analisis Trade-off |
| :--- | :--- | :--- | :--- |
| **Testing Paradigm** | `terraform test` dengan Mock Provider | Terratest (Go Framework) | **Mocking Provider**: Sangat cepat (sub-detik), zero-cost, tidak butuh API credentials. **Kelemahan**: Tidak dapat menguji kompatibilitas aktual dari parameter cloud API eksternal (misal: format string ARN IAM role yang valid menurut regex AWS). Terratest memberikan verifikasi real-world 100%, namun lambat dan mahal. |
| **Policy Language** | OPA (Rego) | HashiCorp Sentinel | **OPA**: Standar terbuka (*vendor-agnostic*), dapat dipakai lintas stack (Kubernetes, Envoy, Terraform, CI/CD). Komunitas besar dan ekosistem tooling kaya (Conftest). **Sentinel**: Integrasi *native* sempurna ke dalam HCP Terraform / Terraform Enterprise, namun menyebabkan *vendor lock-in* dan berlisensi komersial. |
| **Scan Execution** | JSON Execution Plan Analysis | HCL AST Code Analysis | **JSON Plan Analysis**: Memperoleh nilai variabel hasil komputasi dan modul internal secara presisi. **Kelemahan**: Memerlukan eksekusi `terraform init` dan `terraform plan` terlebih dahulu yang membutuhkan waktu serta autentikasi state. **HCL Scan**: Cepat dieksekusi secara instan, namun buta terhadap dynamic logic (`for_each`, lookup map, template expressions). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Masalah Anomali `(known after apply)` pada Evaluasi OPA
*   **Gejala**: OPA Policy melempar error atau salah mendeteksi pelanggaran (`false positive` atau `false negative`) pada resource baru yang merujuk pada resource lain (contoh: `security_group_id = aws_security_group.web.id`).
*   **Penyebab Root**: Di fase *plan*, atribut `.id` dari resource yang belum dibuat bernilai `null` di dalam objek `after`, dan ditandai `true` di dalam objek `after_unknown`.
*   **Solusi**: Tulis rule Rego yang secara defensif memeriksa node `after_unknown`.
    ```rego
    # Safe inspection pattern
    is_attribute_secure(resource, attr_name) {
        # Jika nilai sudah diketahui (known), validasi nilainya
        resource.change.after[attr_name] == true
    } else {
        # Jika nilainya unknown, periksa apakah nilainya dihitung run-time
        resource.change.after_unknown[attr_name] == true
    }
    ```

#### 2. Mock Provider Schema Drift pada `terraform test`
*   **Gejala**: `terraform test` melempar error: `Error: Provider produced invalid schema during mock execution`.
*   **Penyebab Root**: Schema mock provider tidak sinkron dengan provider versi riil yang didefinisikan pada blok `required_providers`, atau Anda menggunakan *computed attributes* yang tidak disediakan default-nya oleh mock framework.
*   **Solusi**: Definisikan blok `mock_data` secara eksplisit untuk menyediakan baseline response bagi atribut yang dibutuhkan blok downstream:
    ```hcl
    mock_provider "aws" {
      mock_data "aws_subnet" {
        defaults = {
          id  = "subnet-0123456789abcdef0"
          arn = "arn:aws:ec2:ap-southeast-1:112233445566:subnet/subnet-0123456789abcdef0"
        }
      }
    }
    ```

#### 3. Conftest / OPA Exit Codes Bypass
*   **Gejala**: Pipeline CI/CD tetap berjalan hijau (*pass*) meskipun OPA mengeluarkan daftar pelanggaran kebijakan.
*   **Penyebab Root**: CLI Conftest atau OPA dijalankan tanpa flag penegakan kegagalan atau pipe bash menutupi exit code non-zero (`opa eval ... | jq` mengembalikan exit code `0` dari jq).
*   **Solusi**: Aktifkan `set -o pipefail` di shell script CI/CD Anda, dan gunakan flag standar `--fail` atau eksekusi conftest dengan format direktori terstruktur:
    ```bash
    set -euo pipefail
    conftest test tfplan.json --policy policies/ --fail-on-warn
    ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan Minimal Dual-Layer Validation**: Pasang static linter (Checkov/TFLint) di layer pre-commit, dan OPA/Conftest di layer PR Pipeline.
- [ ] **Pisahkan Unit Test dan Integration Test**:
  - Beri akhiran file unit test: `.unit.tftest.hcl` (selalu gunakan `mock_provider` dan `command = plan`).
  - Beri akhiran file integration test: `.integ.tftest.hcl` (hanya dijalankan di staging sandbox dengan `command = apply`).
- [ ] **Gunakan Structured Output (SARIF) di CI/CD**: Konversi hasil scan Checkov/Trivy ke format SARIF (*Static Analysis Results Interchange Format*) agar otomatis terintegrasi dengan GitHub Code Scanning Security Alerts.
- [ ] **Isolasi Policy As Code dalam Repository Terpusat**: Hindari menyalin (*copy-paste*) file `.rego` di setiap repo infrastruktur. Gunakan fitur remote policy pulling (misalnya: OCI registry atau `conftest pull git::...`).
- [ ] **Enforce Exception Handling/Exemptions Berbasis Waktu**: Jika sebuah modul membutuhkan bypass kebijakan (misal: membuka port tertentu untuk migrasi legacy), gunakan metadata exception berbatas waktu (*TTL*) yang tercatat di commit history:
  ```json
  "metadata": {
    "exception_expires": "2025-06-30T00:00:00Z",
    "ticket": "SEC-8492"
  }
  ```
- [ ] **Terapkan Blast Radius Limits**: Evaluasi total penghapusan (`delete` action) di OPA. Batalkan deployment secara otomatis jika deletion count > 5 tanpa approval multi-party.

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun struktur pengujian komprehensif lengkap: sebuah modul network, suite `terraform test`, dan sebuah policy Rego pemblokir subnets publik tanpa tag keamanan.

#### Langkah 1: Inisialisasi Workspace
```bash
mkdir -p hands-on/m02/{tests,policies}
cd hands-on/m02/
```

#### Langkah 2: Buat Modul Infrastruktur (`main.tf`)
Simpan file berikut di `hands-on/m02/main.tf`:
```hcl
terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
  }
}

variable "cidr_block" {
  type        = string
  description = "Primary IPv4 CIDR for the VPC"
  default     = "10.0.0.0/16"
}

variable "environment" {
  type        = string
  description = "Target deployment environment"
}

resource "aws_vpc" "main" {
  cidr_block           = var.cidr_block
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "vpc-${var.environment}"
    Environment = var.environment
  }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.cidr_block, 4, 1)
  map_public_ip_on_launch = true

  tags = {
    Name        = "subnet-${var.environment}-public"
    Environment = var.environment
    Tier        = "Public"
  }
}

output "vpc_id" {
  value = aws_vpc.main.id
}

output "public_subnet_id" {
  value = aws_subnet.public.id
}
```

#### Langkah 3: Buat Unit Testing Berbasis Mock (`tests/vpc_suite.tftest.hcl`)
Simpan file berikut di `hands-on/m02/tests/vpc_suite.tftest.hcl`:
```hcl
mock_provider "aws" {}

run "verify_vpc_math_and_subnets" {
  command = plan

  variables {
    cidr_block  = "172.16.0.0/16"
    environment = "staging"
  }

  assert {
    condition     = aws_vpc.main.cidr_block == "172.16.0.0/16"
    error_message = "VPC CIDR did not match passed input variable."
  }

  assert {
    condition     = aws_subnet.public.cidr_block == "172.16.16.0/20"
    error_message = "Subnet calculation formula (cidrsubnet) produced an unexpected CIDR."
  }

  assert {
    condition     = aws_subnet.public.map_public_ip_on_launch == true
    error_message = "Public subnet must have map_public_ip_on_launch configured to true."
  }
}
```

Uji eksekusi modul native test Anda:
```bash
terraform init
terraform test
```

#### Langkah 4: Tulis Policy OPA Pemblokir Public IP Liar (`policies/network_policy.rego`)
Simpan file berikut di `hands-on/m02/policies/network_policy.rego`:
```rego
package terraform.network

import future.keywords.in

default allow = false

violations[msg] {
    some resource in input.resource_changes
    resource.type == "aws_subnet"
    "create" in resource.change.actions
    
    # Deteksi subnet publik
    resource.change.after.map_public_ip_on_launch == true
    
    # Pastikan tag Tier didefinisikan secara eksplisit sebagai Public
    tier := resource.change.after.tags.Tier
    tier != "Public"
    
    msg := sprintf("SECURITY BREACH: Resource '%v' maps public IPs but is not tagged with Tier='Public'. Detected Tier='%v'", [
        resource.address, tier
    ])
}

violations[msg] {
    some resource in input.resource_changes
    resource.type == "aws_vpc"
    "create" in resource.change.actions
    
    resource.change.after.enable_dns_hostnames != true
    msg := sprintf("ARCH-VIOLATION: VPC '%v' must have enable_dns_hostnames set to true.", [resource.address])
}

allow {
    count(violations) == 0
}
```

#### Langkah 5: Eksekusi Serialisasi Plan dan Evaluasi Kebijakan
Jalankan instruksi berikut di terminal:
```bash
# Generate binary plan
terraform plan -var="environment=prod" -out=tfplan.binary

# Konversi binary plan menjadi format standar JSON
terraform show -json tfplan.binary > tfplan.json

# Evaluasi menggunakan OPA CLI
opa eval --data policies/network_policy.rego --input tfplan.json "data.terraform.network.violations"
opa eval --data policies/network_policy.rego --input tfplan.json "data.terraform.network.allow"
```

Pastikan output OPA mengembalikan `data.terraform.network.allow = true` dan array violations kosong `[]`.

---

### 13. Exercise

#### Tingkat: Easy
1. Tambahkan sebuah blok penegasan (`assert`) baru pada `tests/vpc_suite.tftest.hcl` yang memvalidasi bahwa tag `Environment` pada resource `aws_vpc.main` selalu bernilai huruf kecil (*lowercase*), menggunakan fungsi bawaan Terraform `lower()`.

#### Tingkat: Medium
2. Buat file policy Rego baru (`policies/tagging_compliance.rego`) yang memvalidasi bahwa **seluruh** resource yang akan di-*create* di dalam `tfplan.json` (apapun tipe resourcenya) wajib memiliki minimal 3 tag berikut: `Environment`, `ManagedBy`, dan `CostCenter`. Tampilkan address dari resource yang melanggar di dalam pesan eror.

#### Tingkat: Hard
3. Modifikasi `main.tf` untuk menambahkan resource `aws_security_group` dengan ingress block dinamis. Tuliskan file `.tftest.hcl` yang mengevaluasi skenario *computed values*: gunakan blok `override_resource` untuk menyuntikkan ID VPC sintetis dan uji apakah rule keamanan menolak parameter port yang salah ketika nilai `environment == "prod"`.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Platform Security Engineer di sebuah konglomerasi finansial. Organisasi Anda menerapkan regulasi ketat mengenai *Blast Radius Prevention*:

1. **Persyaratan Kebijakan**:
   * Tim infrastruktur dilarang keras melakukan operasi yang mengakibatkan `delete` lebih dari **3 resource** dalam satu pipeline execution, KECUALI commit message mengandung token bypass khusus berformat `[EMERGENCY-OVERRIDE-<TICKET_ID>]`.
   * Jika ada resource tipe `aws_iam_role` atau `aws_iam_policy` yang dihapus, action **wajib selalu digagalkan** tanpa memandang adanya token override.
   * Modul S3 bucket dilarang menggunakan enkripsi bawaan `AES256`; seluruh bucket wajib menggunakan `aws:kms`.

**Tugas Arsitektural**:
* Susun satu unit file kebijakan OPA Rego (`blast_radius_gate.rego`) yang mengonsumsi metadata commit git bersamaan dengan `tfplan.json`.
* Susun sebuah skrip Bash/Pipeline runner idempotent yang mengkombinasikan static security scan Checkov, serialisasi plan Terraform, dan eksekusi OPA, dengan syarat: jika pipeline gagal, ia harus menghasilkan ringkasan berformat Markdown ke stdout yang siap dikirimkan sebagai komentar automated GitHub PR.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Konseptual & Menengah

1. **Pada fase lifecycle mana engine `terraform test` beroperasi saat Anda menetapkan `command = plan` di dalam sebuah blok `run`?**
   * A. Menghubungi API cloud provider secara riil dan membuat resource sementara di akun sandbox.
   * B. Mengompilasi konfigurasi ke dalam DAG, menginjeksi mock provider (jika didefinisikan), memvalidasi logika HCL, dan mengevaluasi assert block pada memory state tanpa menyentuh network cloud.
   * C. Mengunduh production state terbaru dari backend remote S3 lalu memodifikasi lock file.
   * D. Mengonversi seluruh blok HCL menjadi policy Rego secara otomatis.

2. **Apa signifikansi node `after_unknown` pada representasi JSON dari `terraform plan`?**
   * A. Menyimpan riwayat perubahan state yang rusak atau korup.
   * B. Menyimpan daftar variabel yang belum didefinisikan pada file `terraform.tfvars`.
   * C. Menandai daftar atribut yang nilainya belum dapat ditentukan sebelum resource benar-benar dibuat oleh cloud provider pada fase apply.
   * D. Menyimpan informasi kredensial rahasia yang dienkripsi oleh Terraform engine.

3. **Mengapa pemeriksaan keamanan statis berbasis HCL AST murni (seperti scan regex direktori sederhana) tidak memadai untuk pipeline infrastruktur modern?**
   * A. Karena tool statis AST tidak bisa membaca file berformat `.tf`.
   * B. Karena evaluasi statis tidak dapat memecahkan dynamic expressions, local values, interpolasi ternary, dan resource yang dibentuk via `for_each` atau `count`.
   * C. Karena HashiCorp telah mematikan parser AST pada Terraform versi 1.0 ke atas.
   * D. Karena file HCL selalu dienkripsi saat disimpan di sistem file lokal.

4. **Fitur apa yang ditambahkan pada Terraform v1.7+ untuk mempercepat eksekusi unit test modular tanpa kredensial cloud?**
   * A. Terratest Binary Wrapper
   * B. Mock Providers (`mock_provider`) dan Data Overrides
   * C. Direct Local-Exec Containerization
   * D. Sentinel Cloud Linker

5. **Di dalam engine OPA Rego, apa implikasi logis dari pendefinisian beberapa rule dengan nama set yang sama, seperti `violations[msg] { ... }`?**
   * A. Rule yang didefinisikan terakhir akan me-overwrite rule yang didefinisikan lebih awal.
   * B. Engine OPA melempar syntax collision error.
   * C. Bersifat disjungtif (logika **OR**): Setiap blok rule yang kondisinya terpenuhi akan menambahkan elemen baru ke dalam himpunan (*set*) `violations`.
   * D. Bersifat konjungtif (logika **AND**): Seluruh kondisi di semua blok wajib terpenuhi agar salah satu pesan masuk ke set.

#### B. Pertanyaan Lanjutan & Skenario

6. **Manakah dari pola penulisan Rego berikut yang paling efisien dan tepat untuk memfilter hanya resource yang akan dibuat atau diubah pada Terraform Plan?**
   * A. `resource := input.resource_changes[_]; resource.change.actions == "create"`
   * B. `some resource in input.resource_changes; valid_actions := ["create", "update"]; some action in resource.change.actions; action in valid_actions`
   * C. `resource := input.resource_changes; count(resource.change.actions) > 0`
   * D. `input.resource_changes.actions == ["create", "apply"]`

7. **Kapan Anda sebaiknya memilih native `terraform test` dibandingkan suite pengujian eksternal seperti `Terratest` (Go-based)?**
   * A. Saat Anda perlu menguji apakah subnet AWS Anda benar-benar dapat merutekan traffic ICMP secara fisik di AWS backbone.
   * B. Saat Anda membutuhkan integrasi pengujian modul lokal secara mandiri, cepat, deklaratif, terisolasi, dan tanpa biaya cloud API call.
   * C. Saat pengujian membutuhkan verifikasi database payload PostgreSQL nyata pasca-bootstrap instance.
   * D. Saat infrastruktur hanya ditulis menggunakan shell script murni.

8. **Bagaimana cara mencegah pipeline CI/CD membocorkan secret/sensitif output saat mengeksekusi `terraform show -json`?**
   * A. Format JSON Terraform secara default menghapus seluruh data bertanda `sensitive`.
   * B. Membersihkan (sanitizing) file `tfplan.json` atau memastikan pipeline runner berjalan di isolated memory ephemeral agent dan tidak mem-publish artifact JSON ke publik artifact repository.
   * C. Mengubah ekstensi file menjadi `.binary` agar tidak bisa dibaca manusia.
   * D. Menonaktifkan evaluasi OPA untuk resource database.

9. **Jika pada sebuah file `.tftest.hcl`, blok run pertama gagal dieksekusi karena *assertion failure*, apa yang secara default terjadi pada blok-blok run berikutnya di bawahnya?**
   * A. Engine Terraform tetap melanjutkan blok berikutnya tanpa gangguan.
   * B. Seluruh pengujian dihentikan secara instan (*fail-fast*) dan blok selanjutnya dilewati (*skipped*).
   * C. Engine Terraform menghapus backend state remote.
   * D. Provider AWS langsung menghapus resource terkait di cloud.

10. **Apa perbedaan mendasar antara direktif `mock_provider` dan `override_resource` pada framework `terraform test`?**
    * A. `mock_provider` memalsukan seluruh provider execution, sedangkan `override_resource` menimpa atribut dari resource spesifik tertentu dengan data sintetis konstan.
    * B. Keduanya adalah alias yang identik dan dapat dipertukarkan secara bebas.
    * C. `override_resource` hanya dapat digunakan untuk data sources, bukan resource nyata.
    * D. `mock_provider` memerlukan instalasi plugin Go eksternal di folder root.

#### C. Skenario Kasus Produksi

11. **Skenario 1**: Sebuah tim engineer melaporkan bahwa pipeline CI mereka menghasilkan status sukses (*green*), padahal file OPA mereka berisi aturan untuk memblokir instance type `m5.metal`. Saat diinvestigasi, engineer tersebut menggunakan dynamic instance type sizing via map lookup: `instance_type = var.sizes[var.env]`. Variabel `env` diatur melalui environment variable runner CI `TF_VAR_env="prod"`. Mengapa OPA gagal mendeteksi keberadaan instance `m5.metal`?
    * A. OPA tidak mendukung inspeksi data string.
    * B. File `plan.json` yang dikirim ke OPA dieksekusi tanpa menyertakan variabel runtime (misal: `terraform plan` tanpa membaca environment variables CI runner), sehingga atribut `instance_type` bernilai default fallback atau unknown.
    * C. Engine Rego secara default selalu mengembalikan nilai boolean `true`.
    * D. Checkov otomatis mematikan OPA jika mendeteksi lookup map.

12. **Skenario 2**: Anda menjalankan `terraform test` pada modul internal yang menggunakan data source `aws_ami` untuk mencari AMI Ubuntu terbaru. Pengujian gagal di runner CI yang tidak memiliki akses internet dengan pesan: `Error: configuring Terraform AWS Provider: no valid credential sources found`. Bagaimana Anda memperbaiki test suite ini tanpa memberikan AWS credentials ke CI runner?
    * A. Menambahkan `mock_provider "aws"` yang dilengkapi dengan blok `mock_data "aws_ami"` yang menyediakan default value ID sintetis (misal: `id = "ami-0123456789mock"`).
    * B. Memberikan policy IAM `AdministratorAccess` pada runner CI.
    * C. Menghapus data source `aws_ami` dari modul utama.
    * D. Mengganti sistem operasi runner CI menjadi Ubuntu.

13. **Skenario 3**: Sebuah institusi finansial mewajibkan validasi bahwa seluruh disk EBS pada resource `aws_instance` dienkripsi dengan KMS customer managed key (CMK). Namun di HCL, beberapa engineer mendefinisikan disk via blok `root_block_device`, dan yang lain menggunakan resource terpisah `aws_ebs_volume` yang dihubungkan via `aws_volume_attachment`. Bagaimana arsitektur aturan OPA/Rego yang komprehensif untuk menangani dualitas skema ini?
    * A. Aturan Rego hanya perlu memeriksa `aws_ebs_volume` karena Terraform otomatis mengubah `root_block_device` menjadi resource tersebut.
    * B. Menolak penggunaan blok `root_block_device` secara mutlak melalui regex HCL scanner.
    * C. Menyusun dua rule evaluasi terpisah di Rego: Rule pertama mengiterasi atribut `root_block_device` di bawah resource tipe `aws_instance`, dan Rule kedua mengiterasi resource tipe `aws_ebs_volume`, memastikan kedua jalur memiliki atribut enkripsi KMS bernilai valid.
    * D. Hal tersebut mustahil ditangani via OPA dan wajib divalidasi manual via code review.

---

### Kunci Jawaban & Pembahasan Quiz

1. **B**: Engine `terraform test` dengan `command = plan` mengompilasi DAG secara in-memory, menginjeksi mock provider (menghindari API cloud), mengevaluasi kalkulasi internal HCL, dan menjalankan evaluasi assertion pada state sementara.
2. **C**: `after_unknown` adalah peta boolean penting yang mengidentifikasi atribut-atribut yang nilainya hanya akan diketahui setelah eksekusi provisi selesai (contoh: ID yang digenerate oleh cloud provider).
3. **B**: Static analysis murni pada HCL mentah tidak mampu mengevaluasi logika resolusi ekspresi kompleks, pembacaan variabel, modulasi berlapis, ataupun manipulasi koleksi data run-time.
4. **B**: Terraform v1.7 memperkenalkan native provider mocking (`mock_provider`) dan pemalsuan data source (`mock_data`), membebaskan unit testing dari latensi dan kebutuhan otentikasi jaringan eksternal.
5. **C**: Di Rego, mendefinisikan beberapa rule body dengan nama assignment/set yang identik setara dengan operator logika OR (disjungtif).
6. **B**: Pola ini mengecek secara aman apakah aksi mutasi (`create` atau `update`) terkandung dalam array `resource.change.actions` sebelum memeriksa payload `after`.
7. **B**: Native testing sangat optimal untuk pengujian logika internal modul yang terisolasi, deterministik, cepat, dan zero-cost.
8. **B**: File JSON plan berisikan representasi data lengkap yang mencakup informasi sensitif dalam format plain-text jika atribut tidak di-masking secara benar di remote backend; runner wajib mengamankan file ini di memory pipeline terisolasi.
9. **B**: Secara default, alur eksekusi `.tftest.hcl` bersifat berurutan dan menghentikan pengujian jika ada blok run yang gagal demi menghindari kegagalan cascade (*fail-fast*).
10. **A**: `mock_provider` bekerja pada level provider interface (memalsukan respons semua resource provider tersebut), sedangkan `override_resource` menggantikan instance resource tertentu secara presisi.
11. **B**: Jika proses serialisasi plan dijalankan tanpa menyuntikkan file/env variabel yang tepat, nilai ekspresi yang bergantung pada variabel tersebut tidak akan terevaluasi sesuai konteks production.
12. **A**: Penambahan blok `mock_data` pada `mock_provider` menginstruksikan Terraform engine untuk mensimulasikan respons data source tanpa memerlukan konektivitas cloud maupun API credentials.
13. **C**: Karena Terraform mengizinkan resource diekspresikan baik secara inline (*nested blocks*) maupun secara modular/independen (*discrete resources*), arsitektur policy enterprise wajib menginspeksi kedua representasi data tersebut untuk mencegah celah keamanan (*security loopholes*).

---

### 16. Summary

Implementasi **Policy-as-Code, Security Scanning, dan Native Testing** mentransformasi manajemen infrastruktur dari model operasional reaktif (*detect-and-fix post-provisioning*) menjadi model preventif deterministik (*shift-left preventive governance*).

*   **Native Testing (`terraform test`)** berperan sebagai lini pertahanan pertama, menguji fungsionalitas, logika percabangan, dan validasi input modul menggunakan mock provider berkecepatan tinggi tanpa biaya infrastruktur.
*   **Static Scanning (Trivy/Checkov)** bertindak sebagai pemindai postur keamanan dasar yang menyaring anti-pattern umum pada level representasi kode statis.
*   **Policy-as-Code (OPA/Rego)** beroperasi pada serialisasi JSON *execution plan*, bertindak sebagai *gatekeeper* kedaulatan arsitektur yang menegakkan aturan tata kelola, batasan finansial/blast radius, dan regulasi kepatuhan institusional secara mutlak sebelum perubahan diaplikasikan ke ekosistem cloud produksi.