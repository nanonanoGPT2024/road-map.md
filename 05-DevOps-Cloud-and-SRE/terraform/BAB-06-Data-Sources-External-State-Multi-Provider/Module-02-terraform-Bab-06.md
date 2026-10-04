# BAB 06: Data Sources, External State, & Multi-Provider
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengimplementasikan pola arsitektur IaC modular dengan pemisahan dependensi menggunakan *remote state data sources* dan alternatif modern berbasis *Service Catalog / Parameter Store*.
- Merancang dan mengelola arsitektur *multi-provider* heterogen (antar-region, antar-akun AWS via `AssumeRole`, serta orkestrasi lintas platform seperti AWS, Cloudflare, dan Datadog) menggunakan `provider aliases` dan `configuration_aliases`.
- Menganalisis *lifecycle* eksekusi Directed Acyclic Graph (DAG) Terraform saat memproses *data sources*, mengevaluasi perbedaan antara evaluasi pada fase `refresh/plan` vs `apply`.
- Menerapkan mitigasi keamanan terhadap kebocoran data sensitif (*sensitive attribute exposure*) yang diwariskan dari pembacaan state eksternal.
- Mengisolasi *blast radius* infrastruktur berskala enterprise menggunakan strategi *state decoupling* bertingkat (Network -> Compute -> Application).

---

### 2. Prerequisites
Sebelum mempelajari modul ini, Anda harus memahami:
- Sintaksis dasar HCL (*HashiCorp Configuration Language*), deklarasi resource, dan manipulasi variabel/output.
- Konsep dasar Terraform State, locking mechanism via DynamoDB/GCS, dan enkripsi state at-rest/in-transit.
- Konfigurasi autentikasi IAM role/cross-account assume role pada cloud provider (khususnya AWS).
- Dasar-dasar networking cloud: VPC, Subnet, Route Table, CIDR, dan DNS public/private.

---

### 3. Concept & Internal Architecture

#### A. Arsitektur Komunikasi Provider & Lifecycle Data Source
Terraform Core berkomunikasi dengan Terraform Provider Plugin melalui *Remote Procedure Call* (RPC) berbasis protokol gRPC. Ketika sebuah *data source* dideklarasikan:

```
+-----------------------------------------------------------------------+
|                           Terraform Core                              |
|                                                                       |
|  1. Parse Configuration (.tf)                                         |
|  2. Build Dependency Graph (DAG)                                      |
|  3. Determine Evaluation Phase (Compile-time vs Runtime)               |
+-----------------------------------+-----------------------------------+
                                    |
                            gRPC    | (ReadDataSource RPC)
                                    v
+-----------------------------------------------------------------------+
|                       Terraform Provider Plugin                       |
|                       (e.g., terraform-provider-aws)                  |
|                                                                       |
|  1. Translate HCL filters to Cloud API Request                        |
|  2. Execute API Call (e.g., ec2:DescribeVpcs)                         |
|  3. Validate & Map Response to Schema Types                           |
|  4. Inject back to Core State Engine                                  |
+-----------------------------------------------------------------------+
```

Perilaku evaluasi *Data Source* terbagi menjadi dua fase:
1. **Refresh/Plan Phase (Static Query):** Terjadi jika seluruh argumen dari *data source* sudah diketahui secara statis (*statically known*) sebelum eksekusi. Terraform langsung memanggil cloud provider API pada fase `terraform plan`. Nilai data source tersedia untuk menghitung rencana perubahan dependensi di resource hilir.
2. **Apply Phase (Dynamic Query / Delayed Read):** Jika argumen dari *data source* bergantung pada *computed attribute* dari resource lain yang belum dibuat (misal: ID VPC baru yang baru akan terbuat pada fase `apply`), evaluasi *data source* ditunda hingga fase `terraform apply`. Konsekuensi: resource hilir yang bergantung pada data source tersebut akan berstatus `(known after apply)` selama fase plan, sehingga validasi drift dan *pre-flight checks* tidak dapat dievaluasi secara presisi sebelum eksekusi.

#### B. Internal State Access: `terraform_remote_state`
Data source `terraform_remote_state` menggunakan backend driver untuk membuka akses *read-only* ke file state terpisah. 
- Terraform Core membaca raw JSON/binary snapshot dari remote backend (misal: S3 Bucket).
- Parser mendekode hanya blok `outputs` dari root module state target.
- **Batasan Arsitektural:** Akses terhadap remote state memerlukan permission level storage (misal: `s3:GetObject`), yang memberikan akses membaca **seluruh isi state file target**, bukan hanya output yang diekspos. Jika state target menyimpan resource yang memiliki atribut sensitif (seperti password DB atau private key), IAM principal pembaca dapat mengekstrak atribut tersebut via raw state meskipun tidak diekspos di root output.

#### C. Multi-Provider Orchestration
Secara internal, Terraform membangun node terpisah di dalam DAG untuk setiap instansiasi provider:
- **Default Provider:** Digunakan secara implisit oleh seluruh resource yang tipe-nya cocok dengan prefix provider (`aws_*` -> `provider "aws"` default).
- **Aliased Provider:** Diidentifikasi dengan format `aws.<alias>`. Resource harus mereferensikan provider ini secara eksplisit menggunakan meta-argument `provider = aws.<alias>`.
- **Module Configuration Aliases:** Ketika provider di-pass ke child module, Terraform memetakan referensi provider secara eksplisit melalui blok `configuration_aliases` di dalam `terraform { required_providers { ... } }`. Module tidak boleh mengonfigurasi provider block secara internal (*in-module provider anti-pattern*), melainkan harus menerima instansiasi dari root module untuk menghindari *state locking lifecycle bugs* saat operasi `destroy`.

---

### 4. Why & What

| Dimensi | Pendekatan Monolitik | Remote State Decoupling | Service Catalog / Parameter Store |
| :--- | :--- | :--- | :--- |
| **Definisi** | Seluruh infra (VPC, DB, K8s, App) dalam 1 root state. | State dipisah modular, dependensi dibaca via `terraform_remote_state`. | State dipisah total, dependensi diekspos via AWS SSM / Consul KV. |
| **Blast Radius** | **Kritis (Tinggi).** Kesalahan pada resource web app bisa merusak VPC. | **Moderat.** State VPC terisolasi dari state deployment app. | **Minimal.** Isolasi penuh antar-domain engineering. |
| **State Lock Contention** | Sangat sering bentrok; pipeline CI/CD mengantre lama. | Rendah; CI/CD network terpisah dari CI/CD compute. | Nyaris nol; dependency decoupling murni via API external. |
| **Security Risk** | Memerlukan full admin IAM role untuk pipeline. | Reader state memiliki akses membaca raw secret di remote S3. | State permissions terisolasi; akses SSM dikontrol via granular IAM. |
| **Evaluasi DAG** | Sangat lambat (ribuan node resource per plan/apply). | Cepat secara parsial; dependensi statis di-cache. | Cepat; dependensi dievaluasi secara dinamis via API native. |

---

### 5. How (Workflow Detail)

Alur kerja arsitektur multi-provider dengan multi-state dependency injection:

```
[Repo 01: Core Network]
       |
  (terraform apply)
       |
       +---> [AWS S3: network.tfstate] 
       |        ^
       |        | (Read via terraform_remote_state)
       +---> [AWS SSM Parameter Store: /platform/network/vpc_id]
                ^
                | (Read via data.aws_ssm_parameter)
[Repo 02: Platform Compute]
       |
  (terraform plan)
       |
       +---> Evaluasi Default Provider (Primary Region: ap-southeast-1)
       +---> Evaluasi Aliased Provider (Secondary Region: us-east-1)
       +---> Evaluasi Cross-Account Provider (Network Account via IAM AssumeRole)
       |
  (terraform apply)
       |
       +---> [EC2 / ALB / DNS Orchestrated across Regions & Accounts]
```

Tahapan eksekusi:
1. **Pemisahan Boundary State:** Layer fondasi (Networking, IAM) dieksekusi terlebih dahulu. Konfigurasi penting diekspor sebagai Module Outputs atau dipublikasikan ke Parameter Store/Vault.
2. **Deklarasi Multi-Provider:** Root module mendefinisikan provider default dan aliased provider (misal: primary AWS, secondary AWS DR, Cloudflare CDN, Datadog Monitoring).
3. **Passing Provider ke Child Module:** Provider diteruskan ke child module menggunakan map metadata `providers = { aws.source = aws, aws.destination = aws.replica }`.
4. **Dependensi Inversi:** Child module membaca atribut jaringan hulu menggunakan `data.aws_ssm_parameter` atau `data.terraform_remote_state` dengan locking bypass (`workspace_key_prefix` terisolasi).

---

### 6. Analogy & Diagram ASCII

#### Analogi Arsitektur
Bayangkan membangun gedung perkantoran:
- **Monolitik:** Kontraktor fondasi, instalatur listrik, dan desainer interior bekerja pada satu lembar cetak biru fisik yang sama secara bersamaan. Jika desainer interior menumpahkan kopi (syntax error/state lock), kontraktor fondasi berhenti bekerja.
- **Multi-State Decoupled:** Kontraktor fondasi menyelesaikan pekerjaannya, lalu mencetak spesifikasi ukuran tiang ke papan pengumuman publik (*SSM / Remote State*). Kontraktor interior membaca papan pengumuman tersebut tanpa perlu membawa cetak biru fondasi, dan mereka tidak bisa merusak struktur fondasi.
- **Multi-Provider:** Mandor utama bekerja sama dengan sub-kontraktor lokal di Jakarta (*AWS Jakarta*), konsultan proteksi kebakaran dari Singapura (*AWS Singapore*), dan perusahaan keamanan gerbang pintu masuk (*Cloudflare*), mengarahkan mereka secara tersinkronisasi dari satu meja kendali.

```
                           +----------------------------------------+
                           |           Root Configuration           |
                           +-------------------+--------------------+
                                               |
                     +-------------------------+-------------------------+
                     |                                                   |
           providers = { aws = aws }                        providers = { aws = aws.dr }
                     |                                                   |
                     v                                                   v
      +-----------------------------+                     +-----------------------------+
      | Module: Compute Primary     |                     | Module: Compute Disaster Rec|
      | Region: ap-southeast-1      |                     | Region: ap-southeast-2      |
      | State: compute.tfstate      |                     | State: compute.tfstate      |
      +--------------+--------------+                     +--------------+--------------+
                     |                                                   |
                     | Reads Dependency                                  | Reads Dependency
                     v                                                   v
      +---------------------------------------------------------------------------------+
      |                           Data Source Ingestion Layer                           |
      |   (data.aws_ssm_parameter.vpc_id OR data.terraform_remote_state.network)        |
      +---------------------------------------------------------------------------------+
                                               |
                                               v
                                +------------------------------+
                                |  Foundation State Storage    |
                                |  (network/terraform.tfstate) |
                                +------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Dynamic Data Source Filtering with Fallback Logic
Mengambil VPC default dan subnet secara dinamis tanpa melakukan *hardcoding* ID.

```hcl
# versions.tf
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
  }
}

provider "aws" {
  region = "ap-southeast-1"
}

# Dynamic Data Source Lookup
data "aws_vpc" "selected" {
  default = false
  tags = {
    Environment = "production"
    Tier        = "network-core"
  }
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.selected.id]
  }

  tags = {
    Type = "private"
  }
}

# Metadata Inspection
data "aws_subnet" "details" {
  for_each = toset(data.aws_subnets.private.ids)
  id       = each.value
}

output "private_subnet_cidrs" {
  description = "Pemetaan subnet ID terhadap alokasi CIDR block"
  value       = { for id, s in data.aws_subnet.details : id => s.cidr_block }
}
```

#### B. Practical Example: Heterogeneous Multi-Provider Orchestration
Orkestrasi AWS Infrastructure (Cross-Region) terintegrasi dengan Cloudflare DNS routing.

```hcl
# versions.tf
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.20"
    }
  }
}

# 1. Primary AWS Provider (ap-southeast-1)
provider "aws" {
  alias  = "primary"
  region = "ap-southeast-1"
  default_tags {
    tags = {
      ManagedBy = "Terraform"
      Region    = "Primary"
    }
  }
}

# 2. Secondary AWS Provider (ap-southeast-2 - Disaster Recovery)
provider "aws" {
  alias  = "dr"
  region = "ap-southeast-2"
  default_tags {
    tags = {
      ManagedBy = "Terraform"
      Region    = "DisasterRecovery"
    }
  }
}

# 3. Third-Party Provider: Cloudflare
provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

variable "cloudflare_api_token" {
  type      = string
  sensitive = true
}

variable "domain_name" {
  type    = string
  default = "enterprise-mesh.internal"
}

variable "cloudflare_zone_id" {
  type    = string
}

# Data source dari remote state jaringan via modern SSM approach
data "aws_ssm_parameter" "primary_alb_dns" {
  provider = aws.primary
  name     = "/infra/primary/alb_dns_name"
}

data "aws_ssm_parameter" "dr_alb_dns" {
  provider = aws.dr
  name     = "/infra/dr/alb_dns_name"
}

# Resource deployment memanfaatkan Multi-Provider
resource "cloudflare_record" "primary_edge" {
  zone_id = var.cloudflare_zone_id
  name    = "app"
  content = data.aws_ssm_parameter.primary_alb_dns.value
  type    = "CNAME"
  proxied = true
  ttl     = 1 # Automatic when proxied
}

resource "cloudflare_record" "dr_edge_failover" {
  zone_id = var.cloudflare_zone_id
  name    = "dr-app"
  content = data.aws_ssm_parameter.dr_alb_dns.value
  type    = "CNAME"
  proxied = true
  ttl     = 1
}

output "global_ingress_routing" {
  value = {
    cname_primary = cloudflare_record.primary_edge.hostname
    cname_dr      = cloudflare_record.dr_edge_failover.hostname
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Arsitektur Shared Services Hub-and-Spoke Multinasional FinTech
**Permasalahan:**
Perusahaan perbankan digital memiliki kebijakan *segregasi multi-akun AWS*:
1. `Account 100-Core-Network`: Mengelola Transit Gateway (TGW) dan Cloudflare Edge.
2. `Account 200-Production-Core`: Mengelola Payment Engine Microservices.
3. `Account 300-Audit-Monitoring`: Mengelola Datadog Agent, VPC Flow Logs S3 Bucket, dan SIEM Central.

Tim Infrastructure Platform harus menyediakan infrastruktur microservices di akun `Production-Core`, menghubungkan VPC produksinya ke Transit Gateway di akun `Core-Network`, dan secara otomatis mendaftarkan VPC Flow Logs ke akun `Audit-Monitoring` serta membuat monitor alert di Datadog, **seluruhnya dalam satu alur pipeline CI/CD yang atomic tanpa cross-state blast-radius**.

#### Solusi Arsitektur
Gunakan modul yang mengonsumsi **Multi-Provider cross-account** menggunakan instansiasi `assume_role` dinamis, serta mengonsumsi data layer jaringan menggunakan `terraform_remote_state` dengan validasi hash state.

```hcl
# providers.tf
terraform {
  required_version = ">= 1.6.0"
  backend "s3" {
    bucket         = "corp-tfstate-ap-southeast-1-prod"
    key            = "compute/payment-engine/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "corp-tflocks"
    encrypt        = true
  }
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
    datadog = {
      source  = "DataDog/datadog"
      version = "~> 3.35"
    }
  }
}

# Target Deployment: Account 200 (Production Core)
provider "aws" {
  region = "ap-southeast-1"
  assume_role {
    role_arn     = "arn:aws:iam::200000000000:role/TerraformPipelineExecutionRole"
    session_name = "TerraformPaymentDeployment"
  }
}

# Cross-Account Provider: Account 100 (Core Network - TGW Access)
provider "aws" {
  alias  = "network_hub"
  region = "ap-southeast-1"
  assume_role {
    role_arn     = "arn:aws:iam::100000000000:role/TerraformTgwAttachmentCrossAccountRole"
    session_name = "TerraformTgwAttachment"
  }
}

# Third-Party Provider: Datadog
provider "datadog" {
  api_key = var.datadog_api_key
  app_key = var.datadog_app_key
}

variable "datadog_api_key" { type = string; sensitive = true }
variable "datadog_app_key" { type = string; sensitive = true }

# 1. Mengambil referensi arsitektur jaringan secara aman via Remote State
data "terraform_remote_state" "network" {
  backend = "s3"
  config = {
    bucket = "corp-tfstate-ap-southeast-1-shared"
    key    = "network/hub-tgw/terraform.tfstate"
    region = "ap-southeast-1"
  }
}

# 2. Pembuatan VPC di Account 200 (Default Provider)
resource "aws_vpc" "payment_vpc" {
  cidr_block           = "10.200.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "prod-payment-vpc"
  }
}

resource "aws_subnet" "payment_app" {
  vpc_id            = aws_vpc.payment_vpc.id
  cidr_block        = "10.200.1.0/24"
  availability_zone = "ap-southeast-1a"

  tags = {
    Name = "prod-payment-subnet-1a"
  }
}

# 3. TGW Attachment: Memerlukan resource di Account 200, 
#    dan otorisasi/acceptance di Account 100 via Aliased Provider
resource "aws_ec2_transit_gateway_vpc_attachment" "payment_to_hub" {
  transit_gateway_id = data.terraform_remote_state.network.outputs.tgw_id
  vpc_id             = aws_vpc.payment_vpc.id
  subnet_ids         = [aws_subnet.payment_app.id]

  tags = {
    Name = "tgw-attachment-payment-prod"
  }
}

# Transit Gateway Route Table Propagation (Dijalankan di akun 100 via provider network_hub)
resource "aws_ec2_transit_gateway_route" "route_to_payment" {
  provider                       = aws.network_hub
  destination_cidr_block         = aws_vpc.payment_vpc.cidr_block
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.payment_to_hub.id
  transit_gateway_route_table_id = data.terraform_remote_state.network.outputs.tgw_route_table_id
}

# 4. Monitoring Integration via Datadog Provider
resource "datadog_monitor" "payment_gateway_health" {
  name               = "Payment VPC Connectivity Drift"
  type               = "service check"
  message            = "Konektivitas TGW untuk Payment VPC mengalami degradasi! @pagerduty-infra"
  query              = "\"aws.ec2.tgw_attachment.status\".over(\"attachment:${aws_ec2_transit_gateway_vpc_attachment.payment_to_hub.id}\").by(\"*\").last(2).count_by_status()"
  notify_no_data     = true
  renotify_interval  = 60
  
  tags = ["env:production", "domain:payments", "managed-by:terraform"]
}
```

---

### 9. Trade-offs

#### 1. Performance vs Latency
- Menggunakan banyak *data sources* dinamis (`data "aws_*"`) meningkatkan *execution time* pada `terraform plan` secara eksponensial karena Terraform harus mengeksekusi puluhan API calls secara sekuensial atau terikat rate-limit API AWS (HTTP 429 Throttling).
- *Trade-off:* Mengganti dynamic data source dengan referensi langsung via Remote State atau hardcoded variables menaikkan performa `plan` hingga 70%, namun mengurangi fleksibilitas adaptasi otomatis terhadap perubahan eksternal.

#### 2. Scalability vs Complexity (State Decoupling)
- Memecah 1 root state besar menjadi 10 layer state independen mengurangi ukuran DAG dan mempercepat waktu apply secara masif.
- *Trade-off:* Kompleksitas pipeline CI/CD meningkat drastis. Diperlukan dependensi bertingkat (*orchestration tools* seperti Terragrunt, Atlantis, atau GitHub Actions matrices) untuk memicu apply berurutan (`network` -> `iam` -> `storage` -> `compute`).

#### 3. Security vs Blast Radius (`terraform_remote_state` vs Parameter Store)
- `terraform_remote_state` memerlukan akses S3 `s3:GetObject` ke state target. Jika bucket state tersebut menyimpan secret dari komponen lain, tim app berpotensi membaca state sensitif tersebut.
- *Trade-off:* Menggunakan AWS SSM Parameter Store memotong akses baca ke state backend S3 dan menerapkan RBAC super ketat berbasis IAM ARN parameter, tetapi membatasi throughput deployment akibat batasan standard SSM rate limits (40 req/sec) dan size limit (4KB per Standard parameter, 8KB Advanced).

---

### 10. Common Mistakes & Troubleshooting

#### Kasus 1: "Cycle Error" Saat Menggunakan Multi-Provider Dependency
- **Symptom:**
  ```text
  Error: Cycle: provider["registry.terraform.io/hashicorp/aws"].dr, 
  aws_vpc.dr_primary, data.aws_ssm_parameter.target_config
  ```
- **Root Cause:** Resource penyedia data bergantung pada provider yang konfigurasinya bergantung pada output resource lain dalam DAG yang sama (*circular dependency*).
- **Remediasi:** Pastikan atribut dalam deklarasi `provider "aws" { ... }` (seperti `assume_role`, `region`) hanya mengonsumsi static input variables atau local values yang bersifat statis, bukan berasal dari resource runtime Terraform.

#### Kasus 2: Sensitive Attribute Propagation Block
- **Symptom:**
  ```text
  Error: Output refers to sensitive values
  ...
  To make this value available, mark the output with sensitive = true.
  ```
- **Root Cause:** Data source mengambil metadata dari resource yang ditandai sensitif oleh provider (seperti database password atau KMS key cipher). Terraform 1.x secara agresif melarang data sensitif diekspos di root module tanpa penandaan eksplisit.
- **Remediasi:** Tandai block output dengan `sensitive = true`, atau gunakan fungsi `nonsensitive()` hanya jika data tersebut telah diverifikasi secara kriptografis aman dari pembocoran.
  ```hcl
  output "db_connection_string" {
    value     = "server=${data.aws_db_instance.primary.endpoint};"
    sensitive = true # Wajib diaktifkan
  }
  ```

#### Kasus 3: Dynamic Data Source "Known After Apply" Failure
- **Symptom:**
  ```text
  Error: Invalid count argument
  on main.tf line 45:
     count = length(data.aws_subnets.dynamic.ids)
  The "count" value depends on resource attributes that cannot be determined until apply.
  ```
- **Root Cause:** Dynamic data source menerima parameter dari resource yang baru dibuat di root module yang sama, sehingga evaluasi data source dipindahkan ke phase `apply`. Evaluasi iterasi (`count` atau `for_each`) memerlukan evaluasi list/map secara pasti pada phase `plan`.
- **Remediasi:** Jangan gabungkan pembuatan resource dan dynamic data search atas resource baru tersebut di dalam satu execution layer. Pisahkan menjadi modul bertingkat atau gunakan referensi *direct HCL resource attribute chaining* (`aws_subnet.this[*].id`) daripada memanggil `data.aws_subnets`.

---

### 11. Best Practices (Production Checklist)

- [ ] **State Boundary Enforcement:** State dipisahkan berdasarkan tim dan siklus hidup (misal: `00-bootstrap`, `10-network`, `20-database`, `30-compute`). Satu root state tidak boleh memiliki lebih dari 150 total resource.
- [ ] **Zero Hardcoded Cross-State Credentials:** Kredensial assume role dan remote state access tidak boleh ditulis secara eksplisit; gunakan environment variables pipeline (`AWS_ROLE_ARN`) atau OpenID Connect (OIDC).
- [ ] **No In-Module Provider Declarations:** Provider block hanya boleh ada di **Root Module**. Child module hanya boleh mendeklarasikan interface provider melalui `configuration_aliases`.
- [ ] **Strict Output Filtering:** Output pada level jaringan hanya boleh mengekspos atribut ID dan non-sensitif. Hindari mengekspor raw attributes seluruh object (`value = aws_db_instance.primary` adalah anti-pattern; gunakan `value = aws_db_instance.primary.id`).
- [ ] **Explicit Remote State Read Permission:** Bucket remote state harus diproteksi dengan S3 Bucket Policy yang melarang akses dari IAM role non-admin secara eksplisit, kecuali path folder `outputs/` yang di-proxy via Parameter Store/Vault.
- [ ] **Provider Version Pinning:** Selalu lakukan locking strict provider version pada level minor (`~> 5.30.0`) dalam `terraform.lock.hcl` untuk menghindari breaking changes pada schema RPC data source.

---

### 12. Hands-on Practice

Simulasi deployment arsitektur multi-provider: Primary deployment di Region Jakarta (`ap-southeast-1`) dan Secondary deployment di Singapore (`ap-southeast-1` -> DR `ap-southeast-2`), serta interkoneksi data source.

#### Struktur Direktori
Simpan implementasi ini di folder: `hands-on/m02/`
```text
hands-on/m02/
├── backend.tf
├── versions.tf
├── variables.tf
├── main.tf
├── outputs.tf
└── modules/
    └── regional_service/
        ├── main.tf
        ├── variables.tf
        └── outputs.tf
```

#### Langkah 1: Inisialisasi File `versions.tf`
```hcl
# hands-on/m02/versions.tf
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
  }
}
```

#### Langkah 2: Inisialisasi Provider Multi-Region di `main.tf`
```hcl
# hands-on/m02/main.tf
provider "aws" {
  region = "ap-southeast-1"
  default_tags {
    tags = {
      Environment = "HandsOn-M02"
      Owner       = "Platform-Team"
    }
  }
}

provider "aws" {
  alias  = "dr"
  region = "ap-southeast-2"
  default_tags {
    tags = {
      Environment = "HandsOn-M02-DR"
      Owner       = "Platform-Team"
    }
  }
}

# Fetch availability zones secara dinamis per region
data "aws_availability_zones" "primary" {
  state = "available"
}

data "aws_availability_zones" "dr" {
  provider = aws.dr
  state    = "available"
}

# Module Primary
module "service_primary" {
  source = "./modules/regional_service"
  providers = {
    aws = aws
  }

  vpc_cidr          = "10.10.0.0/16"
  subnet_cidr       = "10.10.1.0/24"
  availability_zone = data.aws_availability_zones.primary.names[0]
  deployment_label  = "primary-jkt"
}

# Module Secondary (DR)
module "service_dr" {
  source = "./modules/regional_service"
  providers = {
    aws = aws.dr
  }

  vpc_cidr          = "10.20.0.0/16"
  subnet_cidr       = "10.20.1.0/24"
  availability_zone = data.aws_availability_zones.dr.names[0]
  deployment_label  = "secondary-syd"
}
```

#### Langkah 3: Definisikan Modul Anak di `modules/regional_service/`
```hcl
# hands-on/m02/modules/regional_service/variables.tf
variable "vpc_cidr" { type = string }
variable "subnet_cidr" { type = string }
variable "availability_zone" { type = string }
variable "deployment_label" { type = string }

# hands-on/m02/modules/regional_service/main.tf
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      configuration_aliases = [ aws ]
    }
  }
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "vpc-${var.deployment_label}"
  }
}

resource "aws_subnet" "this" {
  vpc_id            = aws_vpc.this.id
  cidr_block        = var.subnet_cidr
  availability_zone = var.availability_zone

  tags = {
    Name = "subnet-${var.deployment_label}"
  }
}

# Menyimpan metadata VPC ID ke SSM Parameter lokal di region terkait
resource "aws_ssm_parameter" "vpc_id" {
  name        = "/services/${var.deployment_label}/vpc_id"
  description = "Identifier VPC untuk cluster downstream"
  type        = "String"
  value       = aws_vpc.this.id
  overwrite   = true
}

# hands-on/m02/modules/regional_service/outputs.tf
output "vpc_id" {
  value = aws_vpc.this.id
}

output "ssm_vpc_param_name" {
  value = aws_ssm_parameter.vpc_id.name
}
```

#### Langkah 4: Tampilkan Output Agregat di Root
```hcl
# hands-on/m02/outputs.tf
output "mesh_topology" {
  value = {
    primary = {
      vpc_id   = module.service_primary.vpc_id
      ssm_path = module.service_primary.ssm_vpc_param_name
    }
    dr = {
      vpc_id   = module.service_dr.vpc_id
      ssm_path = module.service_dr.ssm_vpc_param_name
    }
  }
}
```

#### Langkah 5: Eksekusi dan Verifikasi
Jalankan perintah berikut di dalam terminal:
```bash
cd hands-on/m02/
terraform init
terraform validate
terraform plan -out=tfplan.binary
terraform apply tfplan.binary
```

---

### 13. Exercise

#### Level Easy
Tuliskan satu blok deklarasi *data source* `aws_ami` untuk mendapatkan Ubuntu 22.04 LTS official image terbaru dari Canonical (`099720109477`) yang menggunakan arsitektur `x86_64` dan tipe virtualisasi `hvm`.

#### Level Medium
Buat sebuah konfigurasi root Terraform yang menggunakan dua instansiasi provider AWS dengan region berbeda (`us-east-1` dan `eu-west-1`). Deklarasikan satu S3 bucket di `us-east-1`, lalu gunakan dynamic data source di `eu-west-1` untuk mengekstrak bucket ARN tersebut dan menjadikannya policy statement pada sebuah IAM Role di region `eu-west-1`.

#### Level Hard
Rancang modul berulang (*reusable module*) yang menerima `configuration_aliases = [aws.src, aws.dst]`. Modul tersebut harus membuat *VPC Peering Connection* di mana requester berada di `aws.src` dan accepter berada di `aws.dst`. Modul harus secara otomatis membuat dan menerima koneksi peering tersebut serta mengonfigurasi rute bolak-balik pada route table kedua sisi menggunakan data source routing lookup dinamis.

---

### 14. Challenge

**Skenario Kasus Produksi Riil:**
Sebuah enterprise fintech ingin mengotomatiskan deployment multi-cloud edge routing. 
- Cloud Provider Utama: AWS (Akun Shared Network, region `ap-southeast-1`).
- CDN / Edge Security Provider: Cloudflare.
- External State: Konfigurasi Core Database berada di backend Terraform Cloud/Enterprise milik tim DBA terpisah dengan workspace name `core-databases-prod`.

**Instruksi Tantangan:**
1. Bangun konfigurasi Terraform terisolasi tanpa hardcoded parameter.
2. Gunakan `terraform_remote_state` atau query parameter store untuk mendapatkan endpoint Aurora PostgreSQL dari workspace DBA.
3. Buat Internal Load Balancer di AWS yang merutekan traffic ke IP database tersebut.
4. Gunakan provider Cloudflare untuk membuat Cloudflare Spectrum Application (TCP proxying) yang memetakan traffic port `5432` dari `db-proxy.enterprise.com` ke public endpoint AWS Network Load Balancer.
5. Konfigurasikan seluruh pipeline menggunakan zero-trust principles: Module tidak boleh memaparkan output plain-text credentials sama sekali. Jika workspace DBA memperbarui credential password, state lokal tidak boleh gagal (*fail-safe dependency evaluation*).

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1. Apa yang membedakan evaluasi data source pada fase `plan` dan fase `apply`?
2. Mengapa mendeklarasikan blok `provider` di dalam *child module* (in-module provider) dianggap sebagai bad practice (*anti-pattern*) oleh HashiCorp?
3. Mengapa atribut `configuration_aliases` wajib dideklarasikan di dalam blok `required_providers` ketika modul menggunakan aliased provider?
4. Apa resiko keamanan terbesar dari penggunaan `data "terraform_remote_state"` jika dibandingkan dengan query metadata via API (misal SSM atau HashiCorp Consul)?
5. Perintah apa yang dapat memaksa Terraform untuk memperbarui cache lokal data source tanpa melakukan perubahan pada resource lain?

#### Pertanyaan Intermediate
6. Bagaimana cara menangani kegagalan `terraform plan` saat sebuah dynamic data source bergantung pada atribut resource yang baru dibuat di root module yang sama?
7. Dalam arsitektur multi-provider cross-account, komponen IAM apa saja yang wajib dikonfigurasi agar provider sekunder dapat melakukan provisioning resource di akun AWS target?
8. Bagaimana perilaku Terraform ketika sebuah data source menghasilkan lebih dari satu match/result (misal `data.aws_ami` menemukan 3 image dengan tag yang identik) tanpa ada filter sorting?
9. Apa fungsi argumen `allow_merge` atau filtering lanjutan pada `data.terraform_remote_state` ketika digunakan bersama Terraform Enterprise/Cloud workspaces?
10. Bagaimana Anda mereferensikan provider non-default saat menggunakan resource meta-argument `for_each` pada module call?

#### Skenario Kasus Produksi
11. **Skenario 1:** Tim infra Anda memecah satu state monolitik sebesar 800 resource menjadi 4 state independen. Ketika pipeline network dijalankan dan menghapus sebuah subnet lama yang tidak terpakai, pipeline compute yang berjalan 1 jam kemudian *crash* dengan error `ResourceNotFound` saat membaca remote state. Jelaskan mengapa hal ini terjadi dan bagaimana strategi rilis *contract-based output* yang benar!
12. **Skenario 2:** Sebuah perusahaan memiliki sistem disaster recovery aktif-pasif. Provider AWS `dr` di-pass ke child module. Saat uji coba pemadaman region primary terjadi, Terraform CLI gagal menginisialisasi provider primary (`AWS Connection Timeout`), menyebabkan seluruh eksekusi plan untuk DR module ikut terblokir total. Bagaimana mengatasinya?
13. **Skenario 3:** Pipeline CI/CD Anda memicu error `AccessDenied` pada evaluasi `data.terraform_remote_state` target, padahal target output yang dibaca hanyalah subnet ID yang bersifat publik. Selidiki apa yang salah pada permission IAM pipeline tersebut pada layer S3 backend!

---

#### Kunci Jawaban & Evaluasi

##### Jawaban Basic
1. Data source dievaluasi saat `plan` jika seluruh argumen input telah diketahui secara statis (*statically known*). Jika argumen bergantung pada atribut resource yang belum dibuat (*computed*), evaluasinya ditunda hingga fase `apply`.
2. Provider dalam modul menyebabkan bug pada lifecycle inheritance, mempersulit penghapusan modul (`destroy`), dan menghambat penggunaan meta-arguments seperti `count` atau `for_each` pada modul tersebut.
3. Karena modul anak harus mendeklarasikan ekspektasi provider interface yang diterimanya dari root module secara eksplisit agar DAG compiler Terraform dapat memetakan provider instance secara tepat.
4. Data source `terraform_remote_state` membaca raw state file secara menyeluruh. Siapa pun yang memiliki izin membaca backend state file S3 tersebut dapat membaca seluruh credential/secret di dalamnya, meskipun atribut tersebut tidak diekspos di root module outputs.
5. `terraform refresh` atau mengeksekusi `terraform plan -refresh-only`.

##### Jawaban Intermediate
6. Pecah boundary layer ke dalam modul terpisah yang dieksekusi bertingkat (orchestration decoupling), atau gunakan *direct attribute references* (`aws_resource.name.id`) alih-alih mencoba mencari resource yang belum selesai dibuat melalui dynamic data source.
7. Diperlukan *Trust Relationship* pada IAM Role di akun target yang mengizinkan IAM User/Role dari akun asal untuk melakukan aksi `sts:AssumeRole`, serta IAM Policy di akun asal yang mengizinkan aksi `sts:AssumeRole` ke target ARN tersebut.
8. Provider akan melemparkan exception error (`Multiple matches found`), dan eksekusi Terraform akan langsung berhenti (halt). Solusinya adalah menyetel argumen seperti `most_recent = true` atau menambahkan filter yang lebih spesifik.
9. Memungkinkan pengambilan snapshot state terisolasi tanpa memicu dependensi eksekusi workspace locking yang dapat menahan alur build CI/CD runner lain.
10. Tentukan di dalam blok `providers` module:
    ```hcl
    module "compute" {
      for_each  = var.regions
      source    = "./module"
      providers = {
        aws = aws.target_alias
      }
    }
    ```

##### Jawaban Skenario Kasus Produksi
11. **Analisis Akar Masalah:** Tim compute bergantung langsung pada ID fisik subnet lama via output remote state. Terjadi *breaking change* pada kontrak output saat subnet dihapus di layer networking.  
    **Strategi Remedi (Contract-Based Deployment):** Terapkan siklus hidup *Deprecation Phase*.  
    1. Buat subnet baru tanpa menghapus subnet lama.  
    2. Publikasikan output baru (`subnet_ids_v2`).  
    3. Update consumer (Compute layer) agar beralih ke `subnet_ids_v2`.  
    4. Setelah compute layer berhasil diaplikasikan ke production, lakukan deployment network tahap kedua untuk menghapus subnet lama.
12. **Analisis Akar Masalah:** Terraform Core secara default memvalidasi koneksi dan memanggil `refresh` terhadap **seluruh** provider yang dideklarasikan di root module, bahkan jika beberapa resource tidak diubah. Kegagalan autentikasi di provider primary mematikan DAG graph compiler secara total.  
    **Strategi Remedi:** Pisahkan direktori konfigurasi root menjadi dua state/workspace independen: `production-primary/` dan `production-dr/`. Hindari menggabungkan dua region inti dalam satu state execution jika salah satu region dirancang untuk bertahan saat region lainnya mati total (*failure-isolation domain principle*).
13. **Analisis Akar Masalah:** Driver backend S3 untuk data source `terraform_remote_state` tidak memiliki pemahaman parsial atas format data. Operasi data source ini setara dengan menjalankan `s3:GetObject` pada file `.tfstate` target.  
    **Strategi Remedi:** Berikan izin `s3:GetObject` pada object key state target di bucket policy backend. Namun, pendekatan enterprise yang lebih aman adalah memindahkan pertukaran output publik tersebut ke **AWS SSM Parameter Store** di mana IAM Policy granular (`ssm:GetParameter`) dapat diberikan tanpa mengekspos raw state file yang sensitif.

---

### 16. Summary
- **Data Source Execution Phases:** Evaluasi data source sangat bergantung pada kepastian argumen inputnya (Compile-time vs Apply-time runtime lookup).
- **Blast Radius Reduction:** Mengisolasi arsitektur enterprise ke dalam state boundaries bertingkat sangat krusial guna mengeliminasi state locking contention dan meminimalisir risiko kesalahan massal.
- **Modern State Decoupling:** Penggunaan `data.terraform_remote_state` membawa risiko keamanan data eksposur secara struktural; SSM Parameter Store, Consul, atau Vault lebih disarankan untuk *cross-module data injection*.
- **Provider Architecture:** Pisahkan root-level instantiation dari modul logic menggunakan `alias` dan `configuration_aliases`. Pola arsitektur multi-provider memungkinkan kontrol lintas akun IAM dan integrasi pihak ketiga (Edge CDN & Observability) secara deterministik dan deklaratif.