# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 09: Skalabilitas, Terragrunt, Monorepo, & FinOps**  
**Kategori: 05-DevOps-Cloud-and-SRE / Terraform**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Principal Engineer / Platform Engineer diharapkan mampu:

1. **Mendesain dan Mengorkestrasi Multi-Account Architecture**: Mengimplementasikan arsitektur *monorepo* modular berbasis Terragrunt yang menopang multi-region dan multi-account AWS/GCP tanpa duplikasi kode (*Don't Repeat Yourself / DRY* backend & provider).
2. **Menguasai Terragrunt Directed Acyclic Graph (DAG) Execution**: Mengelola resolusi dependensi antar-komponen via blok `dependency`, mengendalikan `mock_outputs` untuk *isolated testing*, serta mencegah *circular dependency*.
3. **Mengintegrasikan Automated FinOps Shift-Left**: Membangun *cost-governance guardrails* di pipeline CI/CD menggunakan Infracost dan Open Policy Agent (OPA), melakukan *budget gating*, serta menetapkan ambang batas deviasi biaya operasional (*cost drift*).
4. **Menerapkan Advanced State Locking & Blast Radius Isolation**: Memecah arsitektur monolithic state menjadi micro-state terisolasi dengan zero state lock contention di lingkungan *high-concurrency engineering team*.

---

## 2. Prerequisite

Sebelum mendalami materi ini, praktisi wajib menguasai:

- **Terraform Core Fundamentals**: State locking, remote backends (S3/GCS + DynamoDB/Cloud Storage Locks), lifecycle rules, dynamic blocks, dan structural typing.
- **Terragrunt Basic Concepts**: Dasar hierarki `terragrunt.hcl`, konsep include (`find_in_parent_folders()`), serta perbedaannya dengan vanilla Terraform modules.
- **FinOps Framework Basics**: Prinsip atribusi biaya cloud, model alokasi biaya berbasis *Tagging/Labeling Taxonomy*, serta konsep *Unit Economics*.
- **Tools Requirements**:
  - Terraform CLI `>= 1.6.x`
  - Terragrunt CLI `>= 0.55.x`
  - Infracost CLI `>= 0.10.x`
  - TFLint `>= 0.50.x`
  - Git `>= 2.40.x`

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Terragrunt Engine Under the Hood

Terragrunt bukan sekadar pembungkus (*wrapper*) tipis di atas Terraform; Terragrunt bertindak sebagai **HCL Orchestration Engine & State Interceptor**. 

```
+-------------------------------------------------------------------------------+
|                             TERRAGRUNT RUN-ALL                                |
+-------------------------------------------------------------------------------+
                                      |
         [1] Parse Config AST (Dynamic HCL Evaluation via zclconf/go-cty)
                                      |
         [2] Construct Directed Acyclic Graph (DAG) via Dependency Blocks
                                      |
         [3] Toposort DAG & Parallel Thread Pool Allocation (Worker Pool)
                                      |
         +----------------------------+----------------------------+
         |                                                         |
 [Node: VPC Base]                                          [Node: KMS Keys]
         |                                                         |
         v                                                         v
 [Terraform Execution Engine]                              [Terraform Execution Engine]
   - Generate: provider.tf                                   - Generate: provider.tf
   - Generate: backend.tf                                    - Generate: backend.tf
   - Inject State to Temp Directory                          - Inject State to Temp Directory
     (~/.terragrunt-cache/...)                                 (~/.terragrunt-cache/...)
   - Execute: terraform apply                                - Execute: terraform apply
         |                                                         |
         +----------------------------+----------------------------+
                                      |
                         [Pull Remote State Outputs]
                       (Read S3/GCS JSON State directly)
                                      |
                                      v
                               [Node: EKS Cluster]
                                      |
                                      v
                        [Node: Microservices / Apps]
```

#### Komponen Internal Terragrunt:
1. **Dynamic AST Evaluation**: Saat Terragrunt dijalankan, ia mengevaluasi hierarki file HCL menggunakan engine Go `go-cty`. Variabel lokal, fungsi native Terragrunt (`read_terragrunt_config()`, `run_cmd()`, `get_env()`), dan file turunan digabungkan (*deep merge*) ke dalam satu representasi memori.
2. **DAG Construction & Topological Sort**: Terragrunt memindai seluruh blok `dependency` dalam sub-direktori, memetakan rantai *parent-child*, lalu menyusun graf dependensi terarah tanpa siklus (*acyclic*). Jika terdapat siklus (Node A membutuhkan Node B, Node B membutuhkan Node A), proses langsung dihentikan sebelum Terraform diinisialisasi.
3. **Cache & File Interception (`.terragrunt-cache`)**: Terragrunt tidak pernah mengeksekusi modul langsung di direktori sumber. Direktori kerja dialokasikan ke `~/.terragrunt-cache/<hash>/...`. File backend, provider kustom, dan variabel diinjeksikan secara dinamis menggunakan blok `generate`.
4. **State Interception**: Saat modul dependensi dideklarasikan (`dependency "vpc" { config_path = "../vpc" }`), Terragrunt **tidak menjalankan `terraform output` via shell sub-process**. Terragrunt langsung membaca state file dari target backend (misal: S3 Bucket API atau GCS API) secara langsung, melakukan *unmarshaling* file state JSON, dan menginjeksi output tersebut sebagai `inputs` pada modul pemanggil. Hal ini mengeliminasi latensi inisialisasi modul dependen secara masif.

---

## 4. Why & What

| Dimensi Arsitektur | Vanilla Terraform Monorepo | Terragrunt-Orchestrated Monorepo |
| :--- | :--- | :--- |
| **Penyimpanan State** | Monolithic State File atau State per Direktori dengan duplikasi deklarasi backend manual. | State file terfragmentasi per komponen (*micro-states*) dengan deklarasi backend terpusat (*DRY root config*). |
| **Provider Drift & Konfigurasi** | Setiap sub-folder wajib memiliki deklarasi `provider.tf` duplikat; risiko versi tidak seragam sangat tinggi. | Blok `generate` terpusat di root; seluruh sub-modul mewarisi konfigurasi provider dan tag global secara identik. |
| **Dependency Passing** | Menggunakan resource `terraform_remote_state` yang rapuh, memerlukan konfigurasi backend manual ganda, dan lambat. | Blok `dependency` *native*: validasi tipe ketat, parsing state langsung dari storage backend, dukungan *mocking* untuk testing. |
| **Blast Radius** | Sangat besar. Kegagalan apply pada 1 resource berisiko mengunci (*lock*) seluruh infrastruktur organisasi. | Sangat terisolasi. Kegagalan pada komponen aplikasi tidak mengganggu *lifecycle* VPC atau Storage inti. |
| **FinOps Guardrails** | Manual review atau parsing plan JSON lambat di level root yang memakan waktu timeout di pipeline CI/CD. | Pre-execution *Cost Gating* terisolasi per modul/komponen; metrik kalkulasi biaya paralel via Infracost. |

---

## 5. How: Workflow Detail

Implementasi enterprise pipeline Terragrunt + FinOps dijalankan dengan state machine berikut:

```
[Developer Git Push]
         |
         v
[CI/CD Runner: Atlantis / GitHub Actions]
         |
         +--> 1. Terragrunt Validate-Inputs & HCL Format Check
         |
         +--> 2. Run TFLint on Canonical Code Modules
         |
         +--> 3. Terragrunt Plan (Outputs Plan JSON to /tmp)
         |
         +--> 4. FinOps Engine (Infracost) Interception:
         |         * Parse Plan JSON
         |         * Query Cloud Cost API (AWS/GCP/Azure)
         |         * Compare Against Master Branch Baseline
         |         * Calculate Monthly Delta ($ & %)
         |
         +--> 5. Cost Policy Enforcement (Open Policy Agent / Infracost Guards):
         |         * Rule: Delta > $500/bulan? --> Block Auto-Merge, Require VP Sign-off
         |         * Rule: Tag "CostCenter" missing? --> Hard Failure
         |
         +--> 6. Post FinOps Breakdown to Pull Request Comment
         |
    [PR Approved]
         |
         v
[Terragrunt Apply Orchestration via DAG Thread Pool]
         |
         +--> 7. Emit Real-time Audit Metric to Datadog/CloudWatch
```

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem
Bayangkan **Vanilla Terraform Monorepo** sebagai sebuah *kapal kontainer raksasa terpadu*. Jika ruang mesin bocor atau terbakar (kegagalan state lock, syntax error, kesalahan resource update), seluruh kapal berhenti berlayar, mengancam ribuan kargo lainnya di atas kapal tersebut.

Sebaliknya, **Terragrunt Monorepo dengan Micro-States** adalah *armada kapal tongkang modular independen* yang ditarik oleh sistem pemandu navigasi otomatis (*tugboat fleet*). Jika satu tongkang kontainer logistik aplikasi bermasalah, tongkang bahan bakar (VPC/Database/KMS) tetap berlayar aman tanpa terganggu. FinOps engine bertindak sebagai petugas bea cukai di setiap dermaga yang memverifikasi muatan tagihan sebelum kapal diizinkan melanjutkan perjalanan.

### Struktur Arsitektur Monorepo Enterprise

```
infrastructure-live/ (Monorepo)
├── root.hcl                          # Root config: Provider generation & Remote backend
├── accounts/
│   ├── production/
│   │   ├── account.hcl               # Account ID, AWS Profile, Master Tags
│   │   ├── ap-southeast-1/
│   │   │   ├── region.hcl            # Region specific vars
│   │   │   ├── network/
│   │   │   │   └── vpc/
│   │   │   │       └── terragrunt.hcl
│   │   │   ├── security/
│   │   │   │   └── kms/
│   │   │   │       └── terragrunt.hcl
│   │   │   └── compute/
│   │   │       └── eks-cluster/
│   │   │           └── terragrunt.hcl
│   │   └── us-east-1/
│   │       └── ...
│   └── staging/
│       └── ...
└── modules/ (Internal Module Registry / Git Submodules)
    ├── vpc/
    ├── kms/
    └── eks/
```

---

## 7. Simple Example & Practical Example

Berikut adalah implementasi konfigurasi produksi yang merepresentasikan standar industri.

### 7.1 Root Configuration (`root.hcl`)

File ini menjadi *single source of truth* untuk backend state, dynamic provider configuration, dan global tagging.

```hcl
# File: root.hcl
locals {
  account_vars = read_terragrunt_config(find_in_parent_folders("account.hcl"))
  region_vars  = read_terragrunt_config(find_in_parent_folders("region.hcl"))

  account_id   = local.account_vars.locals.account_id
  account_name = local.account_vars.locals.account_name
  aws_region   = local.region_vars.locals.aws_region

  # Standard Enterprise FinOps Tagging Matrix
  default_tags = merge(
    local.account_vars.locals.tags,
    local.region_vars.locals.tags,
    {
      ManagedBy   = "Terragrunt"
      Repo        = "git@github.com:enterprise/infrastructure-live.git"
      Provisioned = "Infrastructure-As-Code"
    }
  )
}

# Generate AWS Provider dinamis di setiap child module
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30.0"
    }
  }
}

provider "aws" {
  region              = "${local.aws_region}"
  allowed_account_ids = ["${local.account_id}"]

  default_tags {
    tags = ${jsonencode(local.default_tags)}
  }
}
EOF
}

# Remote State Backend Configuration (S3 + DynamoDB State Locking)
remote_state {
  backend = "s3"
  config = {
    encrypt        = true
    bucket         = "ent-tfstate-${local.account_name}-${local.aws_region}"
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = local.aws_region
    dynamodb_table = "ent-tflocks-${local.account_name}"
  }
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
}
```

### 7.2 Environment & Region Variable Definitions

```hcl
# File: accounts/production/account.hcl
locals {
  account_name   = "production"
  account_id     = "112233445566"
  environment    = "prod"
  
  tags = {
    Environment = "production"
    DataClass   = "Confidential"
    CostCenter  = "CC-1092-PROD"
  }
}
```

```hcl
# File: accounts/production/ap-southeast-1/region.hcl
locals {
  aws_region = "ap-southeast-1"
  tags = {
    Region = "ap-southeast-1"
  }
}
```

### 7.3 Base Module: KMS Key Component

```hcl
# File: accounts/production/ap-southeast-1/security/kms/terragrunt.hcl
include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "tfr:///terraform-aws-modules/kms/aws?version=2.1.0"
}

inputs = {
  description             = "EKS Cluster Master Envelope Encryption Key"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  aliases = ["alias/prod-eks-master-key"]

  # FinOps tag validation
  tags = {
    Tier = "Security-Infrastructure"
  }
}
```

### 7.4 Dependent Module: EKS Cluster dengan Dependency Interception & Mocking

File ini menunjukkan cara Terragrunt mengonsumsi output dari KMS dan VPC, dengan `mock_outputs` agar unit test dan plan parsial tetap berjalan mulus tanpa modul KMS harus di-apply terlebih dahulu.

```hcl
# File: accounts/production/ap-southeast-1/compute/eks-cluster/terragrunt.hcl
include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "tfr:///terraform-aws-modules/eks/aws?version=19.21.0"
}

# Dependency 1: VPC
dependency "vpc" {
  config_path = "../../network/vpc"

  mock_outputs = {
    vpc_id          = "vpc-00000000000000000"
    private_subnets = ["subnet-00000000", "subnet-11111111"]
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

# Dependency 2: KMS
dependency "kms" {
  config_path = "../../security/kms"

  mock_outputs = {
    key_arn = "arn:aws:kms:ap-southeast-1:112233445566:key/00000000-0000-0000-0000-000000000000"
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

inputs = {
  cluster_name    = "prod-core-banking-eks"
  cluster_version = "1.28"

  vpc_id                         = dependency.vpc.outputs.vpc_id
  subnet_ids                     = dependency.vpc.outputs.private_subnets
  cluster_endpoint_public_access = false

  # KMS Secret Encryption Configuration
  cluster_encryption_config = {
    provider_key_arn = dependency.kms.outputs.key_arn
    resources        = ["secrets"]
  }

  eks_managed_node_groups = {
    general_workload = {
      min_size       = 3
      max_size       = 10
      desired_size   = 3
      instance_types = ["m6i.xlarge"]
      capacity_type  = "ON_DEMAND"

      labels = {
        WorkloadClass = "CoreBanking"
      }

      tags = {
        CostCenter = "CC-1092-EKS-COMPUTE"
      }
    }
  }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Konteks Skenario: Arsitektur Migrasi Bank Digital
Sebuah bank digital memiliki 80+ modul Terraform monolitik dalam 1 file state raksasa (ukuran `terraform.tfstate` > 45 MB). Masalah yang dialami:
- Durasi eksekusi `terraform plan` memakan waktu **42 menit**.
- Terjadi *state locking contention*: 1 engineer melakukan apply, memblokir 35 engineer lainnya di tim platform.
- Tim engineering tanpa sengaja merilis instans Amazon OpenSearch berbiaya tinggi tanpa kalkulasi biaya, menyebabkan *cloud bill spike* sebesar **$14.000** dalam satu bulan tagihan.

### Solusi Arsitektur
1. **Dekomposisi Monolit ke Terragrunt DAG**: State 45 MB dipecah menjadi 42 *micro-states* independen berbasis dependensi komponen (`network` -> `security` -> `storage` -> `kubernetes` -> `apps`).
2. **FinOps CI/CD Gate**: Integrasi `infracost` di PR pipeline untuk membandingkan perbedaan biaya terhadap target branch (`main`).
3. **Automated Budget Guardrail Policy**: Menggunakan rule OPA (Rego) untuk menolak merger jika kenaikan biaya melampaui toleransi ambang batas (Threshold > 10% atau > $1.000/bulan) tanpa otorisasi FinOps Lead.

### Konfigurasi FinOps CI Pipeline (`.github/workflows/infracost-gate.yml`)

```yaml
name: "Terragrunt FinOps Guardrail"

on:
  pull_request:
    paths:
      - 'accounts/**'

jobs:
  finops-cost-audit:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - name: Checkout Source
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Terraform & Terragrunt
        uses: autero1/action-terragrunt@v3
        with:
          terragrunt-version: 0.55.1
          terraform-version: 1.6.6

      - name: Setup Infracost
        uses: infracost/actions/setup@v2
        with:
          api-key: ${{ secrets.INFRACOST_API_KEY }}

      - name: Generate Infracost Baseline (Target Branch)
        run: |
          git checkout ${{ github.base_ref }}
          infracost breakdown --path=accounts/production/ap-southeast-1 \
            --format=json \
            --out-file=/tmp/infracost-base.json

      - name: Generate Infracost Current Diff (Pull Request)
        run: |
          git checkout ${{ github.head_ref }}
          infracost diff --path=accounts/production/ap-southeast-1 \
            --compare-to=/tmp/infracost-base.json \
            --format=json \
            --out-file=/tmp/infracost-diff.json

      - name: Evaluate FinOps Gate Policies
        id: finops-guard
        run: |
          DIFF_AMOUNT=$(jq -r '(.diffTotalMonthlyCost // 0) | tonumber' /tmp/infracost-diff.json)
          PERCENT_DIFF=$(jq -r '(.diffPercentMonthlyCost // 0) | tonumber' /tmp/infracost-diff.json)
          echo "Delta Biaya: \$$DIFF_AMOUNT per bulan"
          
          # Ambang batas hard stop: Kenaikan > $500 atau > 15%
          if (( $(echo "$DIFF_AMOUNT > 500" | bc -l) )) || (( $(echo "$PERCENT_DIFF > 15" | bc -l) )); then
            echo "::error::Budget Breach! Perubahan infrastruktur ini menaikkan biaya cloud melebihi threshold aman!"
            exit 1
          fi

      - name: Post Comment to PR
        if: always()
        run: |
          infracost comment github --path=/tmp/infracost-diff.json \
            --repo=$GITHUB_REPOSITORY \
            --github-token=${{ secrets.GITHUB_TOKEN }} \
            --pull-request=${{ github.event.pull_request.number }} \
            --behavior=update
```

---

## 9. Trade-offs (Analisis Arsitektur)

| Aspek | Pilihan Monolithic State (Vanilla) | Pilihan Terragrunt Modular DAG | Trade-off Impact |
| :--- | :--- | :--- | :--- |
| **Execution Latency** | Tunggal, tapi linear lambat seiring bertambahnya jumlah resource. | Sangat cepat per sub-modul, namun inisialisasi cold-start `run-all` membutuhkan komputasi memori & CPU yang tinggi. | Pada environment masif (1.000+ modul), `terragrunt run-all plan` membutuhkan resource CI runner minimal 8-core CPU / 16GB RAM. |
| **DAG Dependency Overhead** | Eksplisit dideklarasikan via `depends_on` antar-resource langsung di HCL. | Terdistribusi via file path `dependency { config_path = "..." }`. | Kesalahan konfigurasi path berisiko menyebabkan miskonfigurasi urutan penghapusan (*destroy order*). |
| **Toolchain Complexity & Lock-in** | Nol tooling tambahan. Hanya native Terraform CLI. | Bergantung pada binary Terragrunt dan Terraform. | Developer onboard training curve bertambah. Engine CI/CD harus mengisolasi binary runtime Terragrunt. |
| **FinOps Visibility** | Parsial; kalkulasi biaya monolitik sering kali gagal / timeout saat parsing plan JSON besar. | Tergranulasi sempurna; breakdown FinOps dapat diarahkan spesifik ke sub-folder per unit bisnis. | Memerlukan sinkronisasi mapping tagging yang ketat agar kalkulasi biaya Infracost valid. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Circular Dependency Deadlock
- **Gejala**: Terragrunt melempar error `Circular dependency detected: Module A -> Module B -> Module A`.
- **Root Cause**: Terjadi referensi silang antar dua modul. Misal: Modul Security Group membutuhkan ID Subnet VPC, namun Modul VPC membutuhkan ID Security Group untuk VPC Endpoint.
- **Solusi Troubleshooting**: Pisahkan *interdependent resource* ke modul independen tier ke-3 (misal: buat modul terpisah `accounts/production/network/vpc-endpoints` yang bergantung pada kedua modul tersebut).

### 10.2 Mock Outputs Bocor ke Production (`mock_outputs` Leak)
- **Gejala**: Database atau ingress controller menerima subnet `subnet-00000000` saat dieksekusi di pipeline apply.
- **Root Cause**: Deklarasi `mock_outputs_allowed_terraform_commands` mencakup command `apply`.
- **Solusi**: Batasi izin mock output HANYA untuk perintah read-only:
  ```hcl
  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init"]
  ```

### 10.3 State Locking Race Condition pada Remote State S3/DynamoDB
- **Gejala**: `Error acquiring the state lock: ConditionalCheckFailedException`.
- **Root Cause**: Eksekusi paralel `terragrunt run-all apply` terhadap child modules yang secara tidak sengaja memodifikasi state bucket yang sama tanpa partition key unik.
- **Solusi**: Pastikan evaluasi konfigurasi remote state path selalu menyertakan ekspresi `path_relative_to_include()`:
  ```hcl
  key = "${path_relative_to_include()}/terraform.tfstate"
  ```

---

## 11. Best Practices (Production Checklist)

- [ ] **Zero Hardcoded Identifiers**: Seluruh ARN, VPC ID, Subnet ID, dan KMS Key ID wajib ditarik dinamis melalui deklarasi `dependency` atau Data Sources.
- [ ] **Enforce Deep-Merge Tagging**: Tag wajib (`Environment`, `CostCenter`, `ManagedBy`, `Owner`, `Project`) diinjeksi via `default_tags` root provider.
- [ ] **Restrict `mock_outputs`**: Jangan pernah menyertakan `apply` ke dalam `mock_outputs_allowed_terraform_commands`.
- [ ] **Parallelism Control**: Atur batas paralelisme eksekusi Terragrunt di pipeline CI/CD (`--terragrunt-parallelism 4`) guna mencegah API rate limit throttling dari cloud provider.
- [ ] **Lock Terragrunt & Terraform Versions**: Sematkan versi Terraform di blok `generate` dan versi Terragrunt di file configuration guard.
- [ ] **FinOps Pull Request Gating**: Terapkan Infracost minimum delta verification di setiap trigger pull-request ke master/main.

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun struktur repositori Terragrunt enterprise di direktori `hands-on/m02/`, menyusun dependensi VPC -> KMS -> S3 Bucket terenkripsi, dan melakukan audit biaya dengan Infracost.

### Step 1: Inisialisasi Direktori Proyek

```bash
mkdir -p hands-on/m02/live/production/ap-southeast-1/security/kms
mkdir -p hands-on/m02/live/production/ap-southeast-1/storage/secure-bucket
cd hands-on/m02/live
```

### Step 2: Konfigurasi Root Engine (`hands-on/m02/live/root.hcl`)

```hcl
locals {
  aws_region = "ap-southeast-1"
  account_id = "123456789012"
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite"
  contents  = <<EOF
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30.0"
    }
  }
}

provider "aws" {
  region = "${local.aws_region}"
  default_tags {
    tags = {
      Environment = "production"
      CostCenter  = "CC-DATA-OPS"
      ManagedBy   = "Terragrunt"
    }
  }
}
EOF
}

remote_state {
  backend = "local"
  config = {
    path = "${get_parent_terragrunt_dir()}/terraform.tfstate.d/${path_relative_to_include()}/terraform.tfstate"
  }
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite"
  }
}
```

### Step 3: Modul KMS (`hands-on/m02/live/production/ap-southeast-1/security/kms/terragrunt.hcl`)

```hcl
include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "tfr:///terraform-aws-modules/kms/aws?version=2.1.0"
}

inputs = {
  description             = "Storage Encryption Master Key"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  aliases                 = ["alias/storage-master-key"]
}
```

### Step 4: Modul Storage Dependent (`hands-on/m02/live/production/ap-southeast-1/storage/secure-bucket/terragrunt.hcl`)

```hcl
include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "tfr:///terraform-aws-modules/s3-bucket/aws?version=3.15.1"
}

dependency "kms" {
  config_path = "../../security/kms"

  mock_outputs = {
    key_arn = "arn:aws:kms:ap-southeast-1:123456789012:key/mocked-uuid-for-plan"
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

inputs = {
  bucket        = "ent-compliance-audit-log-bucket-unique-09"
  force_destroy = false

  server_side_encryption_configuration = {
    rule = {
      apply_server_side_encryption_by_default = {
        kms_master_key_id = dependency.kms.outputs.key_arn
        sse_algorithm     = "aws:kms"
      }
    }
  }
}
```

### Step 5: Eksekusi Validasi Dependensi Graf

```bash
cd hands-on/m02/live/production/ap-southeast-1/storage/secure-bucket
terragrunt plan
```
*Amati bagaimana Terragrunt menginjeksi mock output ARN tanpa error dependensi gagal.*

---

## 13. Exercise

### Level Easy
1. Modifikasi file `root.hcl` pada latihan praktikum untuk menambahkan tag global baru: `ComplianceFramework = "PCI-DSS-3.2"`.
2. Validasi dengan menjalankan `terragrunt render-active-config` pada modul `kms` untuk memastikan blok konfigurasi provider di-generate dengan tag baru tersebut.

### Level Medium
1. Buat direktori modul baru `hands-on/m02/live/production/ap-southeast-1/network/vpc`.
2. Deklarasikan modul VPC sederhana (CIDR `10.0.0.0/16`) menggunakan modul upstream `terraform-aws-modules/vpc/aws`.
3. Tambahkan dependensi VPC ini ke dalam modul `secure-bucket` agar bucket policy hanya mengizinkan akses dari VPC Endpoint milik VPC tersebut (Gunakan `mock_outputs` untuk `vpc_id`).

### Level Hard
1. Buat rule FinOps menggunakan pipeline shell script lokal yang membaca output dari `infracost breakdown --path=hands-on/m02/live/production --format=json`.
2. Jika ada resource yang tidak memiliki tag `CostCenter`, gagalkan eksekusi dengan return code status `1` dan cetak pesan error spesifik yang mengidentifikasi resource pelanggar.

---

## 14. Challenge

**Skenario**: Perusahaan FinTech tempat Anda bekerja akan mengimplementasikan skema Multi-Region Disaster Recovery (Active/Passive) antara `ap-southeast-1` (Primary) dan `ap-southeast-3` (Secondary).

**Tantangan Rekayasa**:
1. Rancang hierarki folder Terragrunt monorepo yang mampu mereplikasi seluruh layer (Network, Security, Compute) ke region sekunder dengan *zero duplication* logika module inputs.
2. Gunakan `include` engine dan *deep-merge strategy* Terragrunt untuk melakukan override terhadap parameter instance-type (Production Primary menggunakan `m6i.2xlarge`, Disaster Recovery menggunakan `m6i.large`).
3. Buat skema konfigurasi Infracost baseline multi-region yang memverifikasi bahwa total pengeluaran Region Secondary tidak boleh melebihi 40% dari total pengeluaran Region Primary.

*Selesaikan tanpa menduplikasi kode deklarasi resource Terraform sama sekali.*

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Konsep Dasar (5 Pertanyaan)

1. **Bagaimana Terragrunt mengeksekusi dependensi saat perintah `terragrunt run-all apply` dijalankan?**
   - A. Mengeksekusi modul secara alfabetis sesuai nama folder.
   - B. Menyusun Directed Acyclic Graph (DAG) berdasarkan blok `dependency` lalu mengeksekusi modul independen secara paralel.
   - C. Menggabungkan seluruh file `.tf` menjadi satu file monolithic raksasa sebelum eksekusi.
   - D. Menjalankan perintah secara acak melalui thread pool.
   - *Kunci*: **B** | *Rasional*: Terragrunt membaca blok `dependency` di setiap modul, menyusun DAG via Topological Sort, dan menjalankan eksekusi paralel pada node-node graf yang tidak memiliki dependensi aktif yang belum terselesaikan.

2. **Apa fungsi utama dari parameter `mock_outputs_allowed_terraform_commands`?**
   - A. Mengizinkan pemalsuan nilai output saat Terraform Apply agar resource dibuat lebih cepat.
   - B. Membatasi pemakaian data tiruan (mock) hanya pada sub-perintah yang bersifat read-only/dry-run seperti `plan` atau `validate`.
   - C. Menghapus state backend ketika output tidak ditemukan.
   - D. Menyembunyikan sensitive output dari log CI/CD.
   - *Kunci*: **B** | *Rasional*: Parameter ini mencegah mock data diterapkan ke infrastruktur nyata saat eksekusi `apply`, namun tetap memfasilitasi syntax/graph linting saat eksekusi `plan`.

3. **Mengapa penggunaan `terraform_remote_state` murni dianggap anti-pattern jika dibandingkan dengan blok `dependency` milik Terragrunt?**
   - A. `terraform_remote_state` tidak didukung oleh penyedia cloud AWS.
   - B. `terraform_remote_state` tidak memiliki skema validasi tipe dan mengharuskan modul hilir bergantung pada inisialisasi modul hulu.
   - C. Terragrunt tidak mengenali sintaks HCL native.
   - D. `terraform_remote_state` mewajibkan permission admin IAM penuh.
   - *Kunci*: **B** | *Rasional*: `terraform_remote_state` membaca raw untyped state data dan tidak membangun graf dependensi eksekusi otomatis seperti blok `dependency` Terragrunt.

4. **Kapan blok `generate` dengan opsi `if_exists = "overwrite_terragrunt"` memicu penulisan file?**
   - A. Setiap kali Terragrunt dijalankan, menimpa file target jika file tersebut di-generate oleh Terragrunt sebelumnya.
   - B. Hanya saat file target belum ada di direktori kerja.
   - C. Hanya jika ukuran file target bernilai 0 byte.
   - D. Terragrunt akan melempar fatal error jika file target telah ditemukan.
   - *Kunci*: **A** | *Rasional*: Nilai `"overwrite_terragrunt"` secara spesifik menimpa file lama HANYA jika file tersebut memuat tanda tangan metadata generator Terragrunt.

5. **Apa indikator utama terjadinya *State Locking Contention* dalam tim platform berskala besar?**
   - A. Biaya tagihan cloud meningkat secara eksponensial.
   - B. Terjadinya kegagalan pipeline dengan pesan `ConditionalCheckFailedException` pada tabel DynamoDB locks.
   - C. Checksum module hash tidak cocok pada folder cache.
   - D. Infracost gagal melakukan kalkulasi tagihan.
   - *Kunci*: **B** | *Rasional*: DynamoDB digunakan sebagai tabel state-lock backend S3. Kesalahan konkurensi terjadi ketika dua proses apply mencoba mendapatkan lock ID secara simultan pada state file yang sama.

---

### Bagian B: Konsep Intermediate (5 Pertanyaan)

6. **Pada arsitektur monorepo Terragrunt, fungsi native apakah yang paling tepat digunakan untuk mewarisi konfigurasi dari file konfigurasi lingkungan (`env.hcl`) tanpa mengorbankan portabilitas?**
   - A. `file("../env.hcl")`
   - B. `read_terragrunt_config(find_in_parent_folders("env.hcl"))`
   - C. `templatefile("env.hcl", {})`
   - D. `run_cmd("cat", "env.hcl")`
   - *Kunci*: **B** | *Rasional*: `read_terragrunt_config` mengevaluasi HCL context secara dinamis, sementara `find_in_parent_folders` menelusuri hierarki pohon direktori secara rekursif ke atas.

7. **Bagaimana Infracost menghitung *Cost Drift* secara akurat pada pipeline Pull Request?**
   - A. Menghubungi tagihan kartu kredit perusahaan secara langsung via Webhook.
   - B. Membandingkan baseline plan JSON cabang utama (`target branch`) dengan plan JSON dari perubahan cabang fitur (`PR branch`).
   - C. Menghitung jumlah baris kode HCL yang ditambahkan pada repositori.
   - D. Mengambil data real-time dari AWS Cost Explorer API saat apply berlangsung.
   - *Kunci*: **B** | *Rasional*: Infracost melakukan parsing offline terhadap representasi graph resource Terraform plan JSON, lalu mengalikan spesifikasi hardware terhadap Cloud Pricing API secara deterministik.

8. **Jika Modul A bergantung pada Modul B, dan Modul B diubah konfigurasinya, strategi eksekusi apa yang dilakukan perintah `terragrunt run-all plan`?**
   - A. Hanya memvalidasi Modul A.
   - B. Mengeksekusi pemindaian seluruh direktori dari root, mengompilasi DAG, dan memvalidasi Modul B terlebih dahulu sebelum Modul A.
   - C. Langsung melakukan apply otomatis pada Modul B tanpa intervensi.
   - D. Menghapus state file Modul A untuk memastikan konsistensi.
   - *Kunci*: **B** | *Rasional*: `run-all` mengompilasi seluruh pohon graf, memetakan bahwa Modul A berada di hilir (*downstream*) dari Modul B, sehingga memproses Modul B terlebih dahulu.

9. **Apa dampak performa dari penggunaan direktori kerja `.terragrunt-cache` pada mesin CI/CD yang bersifat ephemeral (destroy-on-finish)?**
   - A. Mempercepat eksekusi tanpa latensi download modul.
   - B. Menimbulkan latensi *cold-start* karena Terragrunt harus men-download modul provider dan upstream repo di setiap run baru.
   - C. Mengakibatkan state corruption jika cache tidak di-commit ke Git.
   - D. Menyebabkan binary memory leak pada kernel OS runner.
   - *Kunci*: **B** | *Rasional*: Ephemeral runners membersihkan file lokal setelah job selesai, sehingga proses downloading provider dan module mirroring harus diulang kecuali jika direktori cache dipetakan ke network storage caching layer.

10. **Bagaimana cara menegakkan FinOps Tagging Policy secara imperatif agar developer tidak dapat mem-bypass kewajiban deklarasi tag `CostCenter`?**
    - A. Mengirimkan email manual setiap hari Jumat kepada engineer yang melanggar.
    - B. Mengombinasikan `default_tags` di root provider generator Terragrunt dengan OPA/Rego policy assertion di pipeline CI.
    - C. Mengunci repositori git secara permanen.
    - D. Menghapus secara otomatis resource yang dibuat tanpa tag via AWS Lambda setiap jam.
    - *Kunci*: **B** | *Rasional*: Menerapkan *defense-in-depth*: Root provider menginjeksi default tag secara deklaratif, dan OPA memvalidasi Plan JSON secara preventif (*shift-left enforcement*) sebelum izin merge/apply diberikan.

---

### Bagian C: Kasus Skenario Produksi (3 Pertanyaan Kompleks)

11. **Skenario Deployment Concurrency:**  
    Platform Engineering team yang beranggotakan 20 orang menjalankan perintah `terragrunt run-all apply` pada root environment staging secara bersamaan dari mesin lokal masing-masing. Terjadi *deadlock* dan kegagalan massal. Solusi arsitektural mana yang paling tepat dan permanen untuk mencegah insiden ini di masa depan?
    - A. Memperbesar kapasitas IOPS DynamoDB state locking table ke 5.000 WCU/RCU.
    - B. Melarang eksekusi `run-all apply` dari mesin lokal, mencabut write-access IAM developer ke cloud state, dan memusatkan seluruh orkestrasi perubahan via pipeline terpusat yang memiliki FIFO queue (misal: Atlantis / GitHub Actions concurrency groups).
    - C. Mengubah konfigurasi state locking dari DynamoDB ke file lock lokal via NFS share.
    - D. Membagi 1 akun staging menjadi 20 sub-account untuk setiap developer.
    - *Kunci*: **B** | *Rasional*: Masalah utamanya adalah eksekusi terdistribusi tanpa koordinasi (*uncontrolled concurrency*). Solusi kelas enterprise adalah mengalihkan wewenang eksekusi mutasi state ke execution plane terpusat yang menerapkan serialisasi antrean (FIFO execution).

12. **Skenario FinOps Cost Explode:**  
    Tim Data Engineering mengajukan PR yang menambahkan EMR cluster baru. Analisis Infracost melaporkan kenaikan biaya sebesar $4.500/bulan (melebihi limit aman tim sebesar $1.000/bulan). Namun, deployment ini bersifat mendesak (*emergency*) untuk memproses data laporan audit regulasi perbankan. Mekanisme pipeline governance apa yang harus disediakan arsitektur DevOps?
    - A. Developer mengubah script Infracost agar tidak mendeteksi resource EMR.
    - B. Menerapkan pola *Break-Glass / Exception Flow*: Pipeline mendeteksi pelanggaran biaya, memblokir merge otomatis, namun menyediakan hook integrasi manual approval yang membutuhkan digital signature approval dari FinOps Lead / VP of Engineering via pull-request label/chatops.
    - C. Memaksa developer membuat EMR di personal credit card.
    - D. Mematikan seluruh cluster staging untuk menghemat biaya agar kuota mencukupi.
    - *Kunci*: **B** | *Rasional*: Arsitektur FinOps enterprise tidak boleh bersifat kaku (*rigid*). Harus tersedia mekanisme tata kelola pengecualian (*governance exception path*) yang transparan dan terdokumentasi secara legal-audit (*audit trail*).

13. **Skenario Degradasi Latensi Terragrunt:**  
    Sebuah monorepo Terragrunt memiliki 600 micro-state folder. Eksekusi `terragrunt run-all plan` membutuhkan waktu lebih dari 1 jam di pipeline CI/CD, meskipun engineer hanya mengubah konfigurasi single file di layer aplikasi paling hilir. Bagaimana cara mengoptimalkan performa ini ke level SLA < 3 menit?
    - A. Menggabungkan kembali 600 micro-state folder menjadi 1 file state tunggal.
    - B. Mengabaikan perintah `run-all` dan mengimplementasikan Git-aware change-detection (`git diff --name-only`) pada CI pipeline, sehingga Terragrunt HANYA dieksekusi spesifik pada direktori yang berubah beserta graf dependensi hilirnya via flag `--terragrunt-working-dir`.
    - C. Menghapus histori commit repository Git.
    - D. Mengubah cloud region ke region yang memiliki latensi jaringan terendah.
    - *Kunci*: **B** | *Rasional*: Menjalankan `run-all` pada seluruh repositori untuk perubahan parsial adalah anti-pattern optimasi. Menggunakan *selective graph execution* berbasis diff analisis memangkas latensi dari $O(N)$ total monorepo menjadi $O(k)$ direktori yang terdampak langsung.

---

## 16. Summary

Implementasi arsitektur **Terragrunt Enterprise Monorepo** yang dikombinasikan dengan **FinOps Shift-Left Governance** menjawab kelemahan skalabilitas vanilla Terraform pada organisasi tingkat tinggi:

1. **DRY Configuration Engine**: Penghapusan total duplikasi blok backend dan provider melalui delegasi dinamis `root.hcl` dan modular input passing.
2. **Blast Radius Minimization**: Fragmentasi arsitektur menjadi *micro-states* terisolasi yang dihubungkan melalui *DAG Dependency Injection* mengeliminasi risiko *monolithic state locking contention*.
3. **FinOps as Code**: Integrasi Infracost dan OPA guardrails mengubah proses audit finansial dari model reaktif (*pasca-billing*) menjadi model preventif (*pra-merge PR*), melindungi anggaran cloud enterprise secara deterministik.
4. **Targeted CI/CD Orchestration**: Menyeimbangkan isolasi dependensi dengan strategi *git-aware change detection* menghasilkan kecepatan deployment tinggi tanpa mengorbankan stabilitas operasional.