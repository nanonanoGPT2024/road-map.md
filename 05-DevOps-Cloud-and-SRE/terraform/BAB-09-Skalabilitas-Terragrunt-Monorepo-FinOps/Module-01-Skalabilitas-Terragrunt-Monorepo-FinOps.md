# Bab 09: Skalabilitas Skala Besar: Terragrunt & Monorepo Patterns

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengimplementasikan arsitektur *Don't Repeat Yourself* (DRY) pada skala enterprise menggunakan Terragrunt.
- Mengelola konfigurasi `terragrunt.hcl`, blok `include`, blok `dependency`, serta mocking outputs untuk validasi decoupling.
- Menata struktur repositori menggunakan pola standar industri: pemisahan `infrastructure-modules` dan `infrastructure-live` dalam monorepo.
- Mereduksi *blast radius* secara radikal melalui isolasi state Terraform per komponen, region, dan environment.
- Mengintegrasikan analisis biaya otomatis (*shift-left FinOps*) menggunakan Infracost ke dalam alur pipeline CI/CD.
- Menerapkan tata kelola penandaan sumber daya (*resource tagging governance*) secara seragam melalui *root configuration inheritance* guna mempermudah pelacakan alokasi biaya (*cost allocation*).

---

## 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib memahami:
- Sintaksis dasar HashiCorp Configuration Language (HCL2), pembuatan custom module, penanganan variable, dan output values.
- Pengelolaan Terraform Remote State (S3 backend, GCS backend, DynamoDB state locking).
- Konsep dasar Directed Acyclic Graph (DAG) dalam siklus evaluasi dependensi Terraform.
- Dasar pipeline CI/CD (GitHub Actions, GitLab CI) dan penggunaan antarmuka baris perintah (CLI).
- Konsep dasar FinOps: penganggaran cloud, model penetapan harga unit sumber daya (compute, storage, transfer data).

---

## 3. Concept
Dalam ekosistem enterprise yang mengelola puluhan akun cloud, ratusan virtual private cloud (VPC), dan ribuan microservices, penggunaan Terraform murni (*vanilla*) sering kali menimbulkan duplikasi kode backend, provider, dan variabel yang masif. 

**Terragrunt** adalah *thin wrapper* untuk Terraform yang menyediakan kakas bawaan untuk:
1. Menjaga konfigurasi backend dan provider tetap DRY (*Don't Repeat Yourself*).
2. Mengorkestrasi dependensi antar-modul tanpa menggabungkan state mereka ke dalam satu state file raksasa (*monolithic state*).
3. Mengisolasi kegagalan infrastruktur sehingga perubahan pada satu komponen tidak merusak komponen lainnya (*Blast Radius Reduction*).
4. Menjalankan audit tata kelola biaya (FinOps) dan kepatuhan tag secara terpusat sebelum kode dideploy ke target cloud.

---

## 4. Why
Pendekatan Terraform konvensional pada skala enterprise kerap menghadapi kendala fatal:
- **Duplikasi Konfigurasi Backend**: Setiap direktori lingkungan (`dev`, `staging`, `prod`) harus mendefinisikan blok `terraform { backend "s3" { ... } }` berulang kali. Perubahan enkripsi backend atau bucket audit memaksa refactoring di ratusan file.
- **State Monolitik & Blast Radius Raksasa**: Menggabungkan VPC, database, dan Kubernetes cluster dalam satu direktori tunggal menghasilkan file `terraform.tfstate` berukuran puluhan megabyte. Eksekusi `terraform apply` memakan waktu berjam-jam, meningkatkan risiko *lock contention*, dan satu kesalahan sintaksis dapat menghancurkan seluruh infrastruktur bisnis.
- **Biaya Tak Terkendali (*Uncontrolled Cloud Spend*)**: Ketiadaan gerbang FinOps terintegrasi memungkinkan *engineer* secara tidak sengaja menginstansiasi node group Kubernetes dengan tipe instans berbiaya tinggi tanpa peringatan sebelum provision terjadi.
- **Fragmentasi Tagging**: Ketidakseragaman penamaan tag seperti `Environment`, `Env`, `cost_center`, atau `CostCenter` mempersulit tim Finance dalam mengalokasikan pengeluaran cloud.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Arsitektur Terragrunt
Terragrunt beroperasi di atas Terraform. Ketika mengeksekusi `terragrunt run-all apply`, Terragrunt:
1. Membaca pohon direktori dan mem-parsing seluruh file `terragrunt.hcl`.
2. Mengompilasi dependensi antar-modul menjadi Directed Acyclic Graph (DAG).
3. Mengunduh source module (dari Git repo atau path lokal) ke dalam direktori kerja `.terragrunt-cache`.
4. Menghasilkan (*generate*) konfigurasi Terraform internal (`backend.tf`, `provider.tf`) secara dinamis.
5. Mengeksekusi binary `terraform` secara terurut berdasarkan tingkat dependensi DAG.

### 5.2 Anatomi Konfigurasi `terragrunt.hcl`
Beberapa blok fundamental dalam Terragrunt meliputi:

- **`terraform { source = "..." }`**: Menentukan lokasi modul Terraform reusable yang akan di-checkout.
- **`include "root" { path = find_in_parent_folders() }`**: Mewarisi konfigurasi global (remote state, global provider, global tags) dari hierarki direktori induk.
- **`dependency "nama_dep" { config_path = "..." }`**: Mengambil output state dari modul lain yang terisolasi secara aman. Terragrunt mengekstraksi metadata output tanpa perlu menghubungkan internal file `.tfstate`.
- **`mock_outputs`**: Nilai *dummy* yang digunakan selama perintah `terragrunt validate` atau `terragrunt plan` ketika modul dependensi belum di-apply di lingkungan baru.
- **`generate`**: Memaksa Terragrunt untuk membuat file `.tf` secara dinamis pada runtime sebelum Terraform dieksekusi.

### 5.3 Monorepo Pattern: Live vs Modules
Standar enterprise memisahkan repositori atau direktori menjadi dua domain utama:
1. **`infrastructure-modules`**: Berisi modul murni Terraform (Resource definitions, variables, outputs). Bersifat stateless, parameterized, dan tidak mengandung hardcoded value akun atau lingkungan.
2. **`infrastructure-live`**: Berisi deklarasi Terragrunt (`terragrunt.hcl`). Merepresentasikan topologi aktual lingkungan cloud: akun, region, komponen, dan parameter nilai input konkret.

### 5.4 Blast Radius Reduction
Mengurangi *blast radius* dilakukan dengan memecah state file berdasarkan:
- Tingkat Akun Cloud: Akun Core/Shared vs Staging vs Production.
- Tingkat Region: `us-east-1` vs `ap-southeast-1`.
- Tingkat Siklus Hidup Sumber Daya:
  - *Foundation* (VPC, Subnet, Direct Connect) - Jarang berubah.
  - *Platform* (EKS Cluster, RDS, ElastiCache) - Siklus rilis mingguan.
  - *Application Infrastructure* (IAM Roles, SQS, S3 Buckets) - Siklus rilis harian/jam.

Dengan pemisahan ini, `terraform apply` untuk deployment SQS queue hanya mengunci state file SQS tersebut, memakan waktu 10 detik, dan tidak memiliki akses mutasi terhadap routing table VPC inti.

### 5.5 FinOps Shift-Left via Infracost
Infracost menganalisis kode Terraform atau Terragrunt dan memetakan komponen infrastruktur ke Infracost Cloud Pricing API. Pada skema monorepo:
- Terragrunt menghasilkan output plan JSON (`terragrunt run-all plan --out=plan.tfplan`).
- Infracost mengompilasi seluruh `plan.tfplan` dan menampilkan delta biaya (contoh: +$450.00/bulan) langsung pada Pull Request.
- Kebijakan anggaran (*guardrails*) dapat memblokir deployment jika delta biaya melebihi threshold tanpa otorisasi FinOps.

---

## 6. How
Implementasi hierarki Terragrunt monorepo dilakukan melalui tahapan:
1. **Definisikan Root Configuration**: Buat `terragrunt.hcl` pada root `infrastructure-live` yang berisi generator remote state S3/DynamoDB dan AWS Provider dengan tagging global.
2. **Definisikan Context Variables**: Buat file `account.hcl`, `region.hcl`, dan `env.hcl` di masing-masing direktori hierarki untuk menginjeksi variabel kontekstual secara otomatis via fungsi `read_terragrunt_config`.
3. **Konfigurasi Node Leaf Modul**: Buat `terragrunt.hcl` pada tingkat leaf (contoh: `infrastructure-live/prod/ap-southeast-1/network/vpc/terragrunt.hcl`) yang mereferensikan modul dan mengonsumsi dependensi.
4. **Validasi Dependency Graph**: Eksekusi perintah `terragrunt graph-dependencies` untuk meninjau keterkaitan modul.
5. **FinOps CI Automation**: Konfigurasikan GitHub Actions untuk menginjeksi Infracost CLI dan membandingkan *baseline cost* dengan *proposed branch cost*.

---

## 7. Analogy
Bayangkan Anda mengelola operasional armada kapal kontainer raksasa:
- **Pendekatan State Monolitik**: Seluruh barang muatan (kontainer mesin, barang elektronik, bahan kimia) diikat mati menjadi satu blok baja masif. Jika tali pengikat bahan kimia putus di tengah badai, seluruh kapal miring dan tenggelam (*single point of failure*, *high blast radius*).
- **Pendekatan Terragrunt + Modul Terisolasi**: Setiap kargo disimpan di dalam kontainer standar ISO yang kedap air dan terkunci di slotnya masing-masing. Jika terjadi kerusakan di kontainer kargo nomor 42, kontainer nomor 101 tidak terpengaruh sama sekali (*isolated state*). Kontainer-kontainer ini diatur oleh sistem logistik terpusat (*Terragrunt DAG orchestration*) yang tahu kontainer mana yang harus diturunkan terlebih dahulu ke dermaga tanpa membongkar seluruh isi kapal.

---

## 8. Diagram (ASCII)

### Pola Hierarki Monorepo (Infrastructure-Live)

```text
infrastructure-live/
├── terragrunt.hcl              <-- [Root] Remote state, AWS provider, Default tags
├── account-prod.hcl            <-- Context: AWS Account ID, Account Alias
│
├── ap-southeast-1/
│   ├── region.hcl              <-- Context: Region = "ap-southeast-1"
│   │
│   ├── production/
│   │   ├── env.hcl             <-- Context: Environment = "production"
│   │   │
│   │   ├── network/
│   │   │   └── vpc/
│   │   │       └── terragrunt.hcl  <-- Produces: vpc_id, private_subnets
│   │   │
│   │   ├── data-storage/
│   │   │   └── rds-postgres/
│   │   │       └── terragrunt.hcl  <-- Depends on: network/vpc
│   │   │
│   │   └── compute/
│   │       └── eks-cluster/
│   │           └── terragrunt.hcl  <-- Depends on: network/vpc
```

### DAG Dependency & Isolation Flow

```text
[network/vpc]  ---> State: s3://prod-state/network/vpc/terraform.tfstate
       │
       ├── (Exposes outputs: vpc_id, subnets)
       │
       ▼
 ┌────────────────────────────────────────┐
 │                                        │
 ▼                                        ▼
[compute/eks-cluster]            [data-storage/rds-postgres]
State: s3://.../eks.tfstate      State: s3://.../rds.tfstate
 (Blast Radius Terisolasi)        (Blast Radius Terisolasi)
```

---

## 9. Simple Example
Implementasi blok `include` dan `generate` pada Terragrunt root level untuk memastikan remote state backend dan default tags terdefinisi secara terpusat:

```hcl
# File: infrastructure-live/terragrunt.hcl

# 1. Konfigurasi Remote State Dinamis
remote_state {
  backend = "s3"
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
  config = {
    bucket         = "corp-tf-state-${get_aws_account_id()}"
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = "ap-southeast-1"
    encrypt        = true
    dynamodb_table = "corp-tf-locks"
  }
}

# 2. Injeksi Global AWS Provider dengan Default Tags
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "aws" {
  region = "ap-southeast-1"
  default_tags {
    tags = {
      ManagedBy   = "Terragrunt"
      CostCenter  = "Core-Infra-9921"
      Repository  = "github.com/enterprise/infrastructure-live"
    }
  }
}
EOF
}
```

---

## 10. Practical Example (Konfigurasi Hands-on Lengkap)

### 10.1 Konfigurasi Root: `infrastructure-live/terragrunt.hcl`
```hcl
# infrastructure-live/terragrunt.hcl
locals {
  # Ekstraksi variabel hierarki direktori
  account_vars = read_terragrunt_config(find_in_parent_folders("account.hcl"))
  region_vars  = read_terragrunt_config(find_in_parent_folders("region.hcl"))
  env_vars     = read_terragrunt_config(find_in_parent_folders("env.hcl"))

  account_id   = local.account_vars.locals.account_id
  aws_region   = local.region_vars.locals.aws_region
  environment  = local.env_vars.locals.environment
}

remote_state {
  backend = "s3"
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
  config = {
    bucket         = "corp-tfstate-${local.account_id}-${local.aws_region}"
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = local.aws_region
    encrypt        = true
    dynamodb_table = "corp-tflocks-${local.aws_region}"
  }
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "aws" {
  region = "${local.aws_region}"
  default_tags {
    tags = {
      Environment = "${local.environment}"
      Provisioner = "Terragrunt"
      ManagedBy   = "CloudPlatformTeam"
    }
  }
}
EOF
}

# Teruskan local context ke modul turunan
inputs = merge(
  local.account_vars.locals,
  local.region_vars.locals,
  local.env_vars.locals,
)
```

### 10.2 Konfigurasi VPC Leaf: `infrastructure-live/prod/ap-southeast-1/network/vpc/terragrunt.hcl`
```hcl
# infrastructure-live/prod/ap-southeast-1/network/vpc/terragrunt.hcl
include "root" {
  path = find_in_parent_folders()
}

terraform {
  source = "git::https://github.com/terraform-aws-modules/terraform-aws-vpc.git?ref=v5.1.2"
}

inputs = {
  name = "prod-vpc-main"
  cidr = "10.100.0.0/16"

  azs             = ["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"]
  private_subnets = ["10.100.1.0/24", "10.100.2.0/24", "10.100.3.0/24"]
  public_subnets  = ["10.100.101.0/24", "10.100.102.0/24", "10.100.103.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = false

  tags = {
    Tier = "Network-Core"
  }
}
```

### 10.3 Konfigurasi RDS Leaf dengan Dependency: `infrastructure-live/prod/ap-southeast-1/data/rds/terragrunt.hcl`
```hcl
# infrastructure-live/prod/ap-southeast-1/data/rds/terragrunt.hcl
include "root" {
  path = find_in_parent_folders()
}

terraform {
  source = "git::https://github.com/terraform-aws-modules/terraform-aws-rds.git?ref=v6.2.0"
}

# Deklarasi dependensi langsung ke komponen VPC
dependency "vpc" {
  config_path = "../../network/vpc"

  # Mock outputs untuk 'terragrunt plan' atau 'validate' saat vpc belum di-apply
  mock_outputs = {
    vpc_id          = "vpc-00000000000000000"
    private_subnets = ["subnet-00000000", "subnet-11111111"]
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

inputs = {
  identifier = "prod-pg-primary"

  engine               = "postgres"
  engine_version       = "15.4"
  family               = "postgres15"
  major_engine_version = "15"
  instance_class       = "db.r6g.xlarge"

  allocated_storage     = 100
  max_allocated_storage = 500

  subnet_ids             = dependency.vpc.outputs.private_subnets
  vpc_security_group_ids = []

  multi_az               = true
  deletion_protection    = true
  skip_final_snapshot    = false

  parameters = [
    {
      name  = "rds.force_ssl"
      value = "1"
    }
  ]
}
```

### 10.4 FinOps Pipeline Configuration (`.github/workflows/finops.yml`)
```yaml
name: "Terragrunt FinOps Guardrails"

on:
  pull_request:
    branches: [ main ]

jobs:
  infracost:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - name: Checkout Source
        uses: actions/checkout@v4

      - name: Setup Infracost
        uses: infracost/actions/setup@v2
        with:
          api-key: ${{ secrets.INFRACOST_API_KEY }}

      - name: Setup Terraform & Terragrunt
        uses: autero1/action-terragrunt@v3
        with:
          terragrunt-version: 0.54.0

      - name: Generate Infracost Cost Baseline
        run: |
          infracost breakdown --path=infrastructure-live/prod/ap-southeast-1/data/rds \
            --format=json \
            --out-file=/tmp/infracost.json

      - name: Post FinOps Comment
        uses: infracost/actions/comment@v1
        with:
          path: /tmp/infracost.json
          behavior: update
```

---

## 11. Real World Example
Sebuah institusi perbankan regional memigrasikan infrastruktur core banking dari datacenter on-premise ke AWS. Awalnya mereka menggunakan satu root Terraform folder untuk satu environment. 
- **Permasalahan**: Eksekusi `terraform plan` memakan waktu 47 menit karena memeriksa ribuan resource sekaligus. Saat seorang insinyur melakukan update pada Security Group aplikasi, *typo* pada CIDR block memicu penghapusan routing subnet database, menghentikan layanan ATM selama 3 jam (*catastrophic blast radius*).
- **Solusi dengan Terragrunt & Monorepo**:
  1. Memecah infrastruktur ke dalam struktur monorepo dengan modul independen (`vpc`, `rds`, `eks-core`, `app-workloads`).
  2. Waktu eksekusi deployment service aplikasi turun dari 47 menit menjadi 90 detik.
  3. Mengaktifkan Infracost pada CI GitHub Actions: mendeteksi upaya provision RDS instance class yang salah (`db.m5.24xlarge` alih-alih `db.m5.large`) pada tahap Pull Request, mencegah pemborosan biaya cloud sebesar $12,000 per bulan sebelum sempat ter-apply.

---

## 12. Trade-offs
Berikut analisis konsekuensi teknis penggunaan Terragrunt:

| Dimensi | Vanilla Terraform Monolith | Terragrunt Monorepo Pattern |
| :--- | :--- | :--- |
| **Blast Radius** | Sangat Tinggi (Satu file state untuk semua komponen). | Sangat Rendah (State terisolasi per leaf node). |
| **Eksekusi Konkuren** | Buruk (State lock memblokir seluruh tim). | Tinggi (State lock hanya memblokir komponen spesifik). |
| **Kompleksitas Tooling**| Rendah (Hanya membutuhkan binary `terraform`). | Menengah-Tinggi (Memerlukan binary `terragrunt` & parsing layer). |
| **Tracing Dependency** | Native via Terraform resource graph. | Perlu konfigurasi blok `dependency` dan `mock_outputs`. |
| **CI/CD Orchestration** | Sederhana (`terraform plan/apply`). | Memerlukan command `run-all` dengan kalkulasi DAG cache. |
| **Overhead Kode** | Duplikasi tinggi pada blok backend & provider. | Sangat DRY via root include dan dynamic generation. |

---

## 13. When To Use
Pola ini tepat digunakan saat:
- Mengelola multi-account cloud enterprise (contoh: AWS Organizations dengan puluhan Sub-Accounts).
- Organisasi memiliki beberapa tier lingkungan terpisah (`dev`, `qa`, `staging`, `prod`) dengan spesifikasi arsitektur identik namun skala kapasitas berbeda.
- Beberapa tim fungsional (Network Team, Platform Team, App Team) mengelola lapisan infrastruktur yang berbeda namun saling bergantung.
- Diperlukan standarisasi governance tag dan remote state locking yang wajib ditaati oleh seluruh insinyur cloud.

---

## 14. When NOT To Use
Hindari pola ini jika:
- **Proyek Kecil/Skala Startup Awal**: Jika infrastruktur hanya terdiri dari 1 VPC, 2 VM, dan 1 RDS, overhead Terragrunt menambah kompleksitas yang tidak sebanding (*over-engineering*).
- **Tim Belum Menguasai Dasar Terraform**: Terragrunt mengabstraksi pemanggilan Terraform. Jika insinyur belum memahami siklus hidup state dan evaluasi HCL murni, troubleshooting Terragrunt error caching akan membingungkan.
- **Infrastruktur Sepenuhnya Homogen via Terraform Cloud/Enterprise Workspace**: Jika Anda telah menggunakan Terraform Cloud Workspaces dengan dynamic variable sets dan Run Triggers bawaan, sebagian fitur orkestrasi Terragrunt telah terfasilitasi.

---

## 15. Common Mistakes
1. **Pola Circular Dependency**: Modul A bergantung pada Modul B, dan Modul B bergantung pada Modul A. Hal ini menyebabkan Terragrunt DAG deadlock saat mengeksekusi `terragrunt run-all apply`.
2. **Lupa Mendefinisikan `mock_outputs`**: Tanpa `mock_outputs`, eksekusi `terragrunt run-all plan` di environment baru yang masih kosong akan langsung gagal karena dependensi upstream belum memiliki state output nyata.
3. **Penyalahgunaan Flag `terragrunt run-all destroy`**: Menjalankan perintah ini pada root folder tanpa proteksi termination protection akan menghapus seluruh infrastruktur organisasi sekaligus.
4. **Hardcoding Account ID dan Region di Modul Leaf**: Menuliskan ID statis alih-alih memanfaatkan pembacaan dinamis lewat `read_terragrunt_config(find_in_parent_folders("..."))`.
5. **Mengabaikan `.terragrunt-cache` pada `.gitignore`**: Memasukkan direktori `.terragrunt-cache` ke dalam Git history, menyebabkan ukuran repositori membengkak drastis.

---

## 16. Best Practices
- **Prinsip Immutability pada Source Modul**: Selalu gunakan Git semantic tags pada `terraform.source` (contoh: `?ref=v2.4.1`), jangan pernah menggunakan `?ref=main` di lingkungan produksi.
- **Konvensi Default Tag Terpusat**: Terapkan tag wajib (`Environment`, `Owner`, `CostCenter`, `ManagedBy`, `ComplianceScope`) di root `terragrunt.hcl` menggunakan fitur AWS Provider `default_tags`.
- **Gunakan Terragrunt CLI Flags Secara Konsisten**: 
  - Gunakan `--terragrunt-parallelism` untuk membatasi konkurensi agar tidak terkena rate-limiting AWS API.
  - Gunakan `--terragrunt-non-interactive` dalam automation pipeline.
- **Isolasi State Storage Per Akun**: Gunakan akun audit/log terpisah untuk S3 remote state bucket, atau minimal pisahkan IAM role permissions untuk state locking.
- **Audit FinOps Shift-Left**: Pasang threshold Infracost pada CI. Gagalkan build Pull Request jika terdeteksi peningkatan biaya tanpa label `finops-approved`.

---

## 17. Troubleshooting

### Kasus 1: Error `ModuleNotFound` atau Sinkronisasi Cache Rusak
- **Gejala**: Terragrunt terus menjalankan versi modul yang lama meskipun git tag telah diubah.
- **Penyebab**: Cache lokal pada `.terragrunt-cache` korup atau tidak ter-refresh.
- **Solusi**:
  ```bash
  find . -type d -name ".terragrunt-cache" -prune -exec rm -rf {} +
  terragrunt init -reconfigure
  ```

### Kasus 2: Dependency Output Bernilai Kosong Saat `plan`
- **Gejala**: `Error: Unsupported attribute: dependency.vpc.outputs.vpc_id is not set`.
- **Penyebab**: Modul vpc belum pernah di-deploy, dan `mock_outputs` belum dikonfigurasi pada blok `dependency`.
- **Solusi**: Tambahkan blok `mock_outputs` dan `mock_outputs_allowed_terraform_commands`:
  ```hcl
  dependency "vpc" {
    config_path = "../vpc"
    mock_outputs = {
      vpc_id = "mock-vpc-id-12345"
    }
    mock_outputs_allowed_terraform_commands = ["validate", "plan"]
  }
  ```

### Kasus 3: AWS API Rate Limiting / ThrottlingException Saat `run-all`
- **Gejala**: Terragrunt melempar error `RequestLimitExceeded` ketika mengeksekusi puluhan modul sekaligus.
- **Penyebab**: Terragrunt menjalankan proses paralel secara agresif secara default.
- **Solusi**: Batasi konkurensi paralel thread runner:
  ```bash
  terragrunt run-all apply --terragrunt-parallelism 4
  ```

---

## 18. Exercise
Skenario Praktik Mandiri:
1. Susun struktur folder monorepo:
   - `root/terragrunt.hcl`
   - `root/prod/env.hcl`
   - `root/prod/ap-southeast-1/region.hcl`
   - `root/prod/ap-southeast-1/app/terragrunt.hcl`
2. Konfigurasikan root `terragrunt.hcl` agar menghasilkan `backend.tf` secara otomatis dengan path remote state dinamis sesuai subfolder masing-masing.
3. Jalankan sintaks evaluasi tanpa eksekusi langsung ke cloud provider untuk memverifikasi bahwa file `backend.tf` ter-generate dengan target state key yang unik.

---

## 19. Challenge
Rancang arsitektur monorepo skala enterprise dengan batasan berikut:
- Terdapat 3 lingkungan: `dev`, `staging`, `production`.
- Terdapat 2 region: `us-east-1` dan `ap-southeast-1`.
- Komponen: Network (VPC), Data (DynamoDB), Services (ECS Microservices).
- Syarat Khusus:
  1. Layanan ECS Microservice di `production` hanya boleh membaca referensi VPC melalui blok `dependency`.
  2. Semua resource harus memiliki penandaan (*tagging*) wajib: `Environment`, `DataClassification`, `CostCenter`.
  3. Konfigurasikan file pipeline deklaratif (GitHub Actions) yang mengeksekusi linting, verifikasi tag via custom parsing, pengecekan Infracost delta cost breakdown, dan menerapkan eksekusi bertahap (*staged rollout*): dev -> staging -> prod.

---

## 20. Summary
- **Terragrunt** mengeliminasi boilerplate duplikasi kode Terraform dengan memusatkan definisi backend dan provider.
- Pemisahan repositori menjadi **`infrastructure-modules`** (kontrak logika infrastruktur) dan **`infrastructure-live`** (konfigurasi instansiasi lingkungan) menciptakan batas operasional yang rapi dan terukur.
- **Blast Radius** diminimalisir secara optimal dengan memecah state file berdasarkan komponen granular. Modul berkomunikasi menggunakan kontrak output via blok `dependency` tanpa perlu menggabungkan file state.
- Integrasi **Infracost** dan penegakan **Default Tagging Governance** menghadirkan kapabilitas FinOps tingkat lanjut (*shift-left FinOps*), memungkinkan visibilitas dan kontrol pengeluaran cloud sejak tahapan Pull Request.

---