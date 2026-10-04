# Module 01: Enterprise Module Architecture & Reusability

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang arsitektur modul Terraform berbasis prinsip *Single Responsibility Principle* (SRP) dan *Composable Modules* untuk skala enterprise.
- Membedakan secara tegas batas arsitektural (*architectural boundary*) antara *Root Module* dan *Child Modules*.
- Mengimplementasikan strategi rilis modul menggunakan *Semantic Versioning* (SemVer) yang terintegrasi dengan Git tagging dan pipeline CI/CD.
- Memilih, mengonfigurasi, dan mengoperasikan *Module Registry* (Public vs Private Registry seperti Terraform Cloud, HashiCorp HCP Terraform, GitLab Package Registry, atau AWS S3/CodeCommit).
- Membangun *Input Variable Validation* yang ketat menggunakan custom validation rules (`regex`, `contains`, `can`) dan merancang *Output Architecture* yang aman dari kebocoran data sensitif (*sensitive data exposure*).
- Menentukan batas *Encapsulation vs Exposure* guna mencegah *leaky abstraction* pada abstraksi infrastruktur multi-lingkungan (*multi-tenant / multi-environment*).

---

## 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib memahami:
- Sintaksis dasar HashiCorp Configuration Language (HCL2) dan blok konfigurasi Terraform (`terraform`, `provider`, `resource`, `variable`, `output`, `locals`).
- Siklus hidup eksekusi Terraform (`init`, `plan`, `apply`, `destroy`).
- Manajemen state file Terraform dan remote backend locking (S3/DynamoDB atau GCS/Cloud Storage).
- Alur kerja Git dasar: branching, merging, dan Git tagging (`git tag -a vX.Y.Z`).
- Konsep dasar jaringan dan keamanan cloud (VPC, Subnet, CIDR, IAM role/policy).

---

## 3. Concept
Dalam ekosistem enterprise, Terraform tidak boleh ditulis secara monolitik dalam satu folder flat. Pendekatan flat mengakibatkan *blast radius* yang sangat luas, duplikasi kode (copy-paste engineering), dan ketidakmampuan menerapkan *governance policy*.

**Enterprise Module Architecture** adalah paradigma rekayasa infrastruktur yang mengisolasi komponen-komponen infrastruktur menjadi blok bangunan mandiri (*building blocks*), dapat diuji (*testable*), memiliki versi (*version-controlled*), dan dapat dikomposisikan ulang (*composable*). 

Modul di Terraform dikelompokkan ke dalam dua spektrum:
1. **Resource Modules (L1 / Building Block)**: Pembungkus tipis di atas resource tunggal atau kumpulan resource yang terikat sangat erat (misal: satu AWS VPC beserta route table-nya, atau satu Cloud SQL Instance). Modul ini sangat generik dan reusable.
2. **Infrastructure/Pattern Modules (L2 / Composed Pattern)**: Modul komposit yang menggabungkan beberapa L1 modules untuk membentuk blueprint arsitektur spesifik (misal: "Microservice Web Tier" yang menggabungkan VPC module, ECS module, dan ALB module).

```
+-----------------------------------------------------------------------+
| Root Module (Live Environment: Production / Staging)                  |
|  - Menyediakan credentials provider                                   |
|  - Memasok nilai input spesifik environment ke Child Module           |
+---------------------------------------------------+-------------------+
                                                    |
                                                    | calls via Git/Registry
                                                    v
+---------------------------------------------------+-------------------+
| Child Module (Reusable Pattern / L2)                                  |
|  - Mengomposisikan Resource Modules                                   |
|  - Enkapsulasi business logic dan guardrails                          |
+-------------------+-------------------------------+-------------------+
                    |                               |
       calls via Git/Registry          calls via Git/Registry
                    v                               v
+-------------------+---------------+   +-----------+-------------------+
| Resource Module A (L1: VPC)       |   | Resource Module B (L1: DB)    |
| - Pure infrastructure primitives  |   | - Pure infrastructure primitives|
+-----------------------------------+   +-------------------------------+
```

---

## 4. Why
Tanpa arsitektur modul yang terstandardisasi, organisasi enterprise menghadapi tantangan berikut:
1. **Configuration Drift & Duplication**: Tim A dan Tim B menulis resource VPC dengan konfigurasi routing, NACL, dan logging yang berbeda, memicu celah keamanan dan pemborosan biaya.
2. **Uncontrolled Blast Radius**: Modul monolitik menyebabkan ketergantungan antar-resource yang rumit; perubahan pada satu security group dapat memicu rekreasi database secara tidak sengaja.
3. **Dependency Hell Tanpa SemVer**: Menggunakan modul langsung dari branch `main` pada Git repository pihak ketiga atau internal menyebabkan perubahan breaking change langsung merusak pipeline deployment tim lain.
4. **Leaky Abstractions**: Membuka seluruh atribut internal resource ke luar modul merusak modularitas dan menyulitkan refaktorisasi internal tanpa merusak konfigurasi pemanggil (*caller*).
5. **Kepatuhan Regulasi (Compliance by Default)**: Di perbankan atau sistem kesehatan (HIPAA, PCI-DSS), enkripsi at-rest, private access, dan logging audit harus di-enforce di tingkat modul, bukan diserahkan kepada kebijakan engineer perorangan.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Single Responsibility Principle (SRP) & Composable Modules
Setiap modul harus memiliki satu alasan untuk berubah (*one reason to change*).
- **Anti-Pattern**: Sebuah modul bernama `terraform-aws-full-app` yang membuat VPC, EKS, RDS, S3, dan Route53 sekaligus. Jika ada update pada versi Kubernetes, modul database juga ikut ter-deploy dan berisiko mengalami lock state atau drift.
- **Best Practice (Composable)**:
  - Modul 1: `terraform-aws-network` (hanya VPC, Subnet, Route Table, NAT Gateway).
  - Modul 2: `terraform-aws-data-layer` (hanya RDS instance, subnet group, parameter group).
  - Keduanya dihubungkan di Root Module dengan mengalirkan output modul 1 (`module.network.vpc_id`, `module.network.private_subnet_ids`) ke input modul 2.

### 5.2 Root Module vs Child Modules
- **Root Module**: Direktori tempat `terraform apply` dieksekusi. Merupakan instansiasi konkret untuk environment tertentu (misal: `environments/production/`). Root module mendefinisikan backend remote state, provider configurations, dan memetakan variabel dari environment ke child modules.
- **Child Module**: Modul yang dipanggil di dalam blok `module "..." {}`. Child module **tidak boleh** mendefinisikan backend block dan **tidak boleh** mendefinisikan hardcoded provider configuration dengan credentials/profile. Child module hanya mendeklarasikan dependensi provider melalui blok `terraform.required_providers`.

### 5.3 Semantic Versioning (SemVer)
Modul didistribusikan menggunakan format `vX.Y.Z`:
- **MAJOR (X)**: Perubahan yang tidak backward-compatible (misal: penggantian nama variable required, penghapusan resource, restrukturisasi state path).
- **MINOR (Y)**: Penambahan fitur baru yang backward-compatible (misal: variable opsional baru dengan default value, penambahan output baru).
- **PATCH (Z)**: Perbaikan bug backward-compatible (misal: perbaikan deskripsi, logic sanitasi lokal, perbaikan typo).

### 5.4 Module Registry (Public vs Private)
- **Public Registry**: `registry.terraform.io`. Cocok untuk modul open-source komunitas.
- **Private Registry**: 
  - Terraform Cloud / HCP Terraform: Format source `app.terraform.io/<org-name>/<module-name>/<provider>`.
  - Self-hosted / Git-based Private Registry: Format source `git::https://gitlab.corp.internal/cloud-platform/terraform-aws-rds.git?ref=v2.1.0`.
  - Keuntungan Private Registry: Dukungan dependency resolution otomatis, semantic versioning matching (`~> 2.0`), auto-generated visual documentation, dan RBAC enterprise.

### 5.5 Input Validation Architecture
Validasi input dilakukan menggunakan atribut `validation` di dalam blok `variable`. Setiap blok validation wajib memiliki:
- `condition`: Ekspresi boolean yang mengevaluasi nilai input (harus mengembalikan `true` agar valid).
- `error_message`: Pesan kegagalan yang jelas dan preskriptif, menjelaskan apa yang salah dan format yang diharapkan.

### 5.6 Encapsulation vs Exposure
- **Encapsulation**: Sembunyikan detail implementasi. Jangan mengekspos ID security group internal jika tidak perlu dimodifikasi oleh root module. Gunakan *sensible defaults*.
- **Exposure**: Hanya ekspos data yang diperlukan downstream modules via `output`.
- **Sensitive Guard**: Selalu tandai output kredensial, connection strings, atau private keys dengan `sensitive = true` untuk mencegah kebocoran pada console output dan CI/CD execution logs.

---

## 6. How
Proses perancangan modul enterprise terstruktur:
1. **Analisis Kebutuhan**: Pisahkan komponen stateful (database, storage) dari stateless (compute, load balancer).
2. **Definisikan File Structure**:
   ```
   terraform-provider-modulename/
   ├── .gitignore
   ├── README.md
   ├── main.tf
   ├── variables.tf
   ├── outputs.tf
   ├── versions.tf
   └── examples/
       ├── basic/
       └── complete/
   ```
3. **Tulis `versions.tf`**: Definisikan `required_version` minimum untuk Terraform dan `required_providers`.
4. **Implementasikan Validasi di `variables.tf`**: Cegah input invalid sebelum `terraform plan` berinteraksi dengan API Cloud.
5. **Minimalkan Output di `outputs.tf`**: Gunakan pola *Named Outputs* dan berikan deskripsi eksplisit.
6. **Lakukan Tagging Git SemVer**: Publikasikan rilis menggunakan Git tag yang terproteksi.

---

## 7. Analogy
Bayangkan sebuah modul Terraform sebagai **Komponen Audio Hi-Fi Modular**:
- **Resource Module (L1)** adalah sebuah *amplifier chip* atau *speaker driver*. Komponen ini memiliki spesifikasi voltase input yang sangat presisi (Input Validation). Komponen ini tidak peduli apakah ia akan dipasang di radio mobil atau sound system konser.
- **Pattern Module (L2)** adalah unit *Active Studio Monitor Speaker*, yang merakit amplifier, speaker cone, dan crossover filter menjadi satu kesatuan fungsional.
- **Root Module** adalah *kamar kontrol studio musik Anda*. Di sinilah Anda mencolokkan kabel daya ke stopkontak dinding (Provider Configuration), memilih input audio (Variables), dan mengoneksikan kabel antar speaker (Downstream Orchestration).
- Jika pabrik mengubah jack input dari 3.5mm menjadi XLR tanpa pemberitahuan (*Breaking Change tanpa SemVer Major*), kabel studio Anda tidak akan bisa dicolokkan sama sekali (*deployment failure*).

---

## 8. Diagram (ASCII)

### Siklus Integrasi Modul Enterprise
```
+----------------------------------------------------------------------------------+
|                            VCS (GitLab / GitHub)                                 |
|                                                                                  |
|   Repo: terraform-aws-rds-module                                                 |
|   Tags: [ v1.0.0 ] -> [ v1.1.0 ] -> [ v2.0.0 (BREAKING) ]                        |
+----------------------------------------+-----------------------------------------+
                                         |
                                         | Webhook / Sync
                                         v
+----------------------------------------------------------------------------------+
|                    Enterprise Module Registry (Private)                          |
|                                                                                  |
|   Module: app.terraform.io/enterprise-corp/database/aws                          |
|   Available Versions: 1.0.0, 1.1.0, 2.0.0                                        |
+----------------------------------------+-----------------------------------------+
                                         |
               +-------------------------+-------------------------+
               | Source Pinning: ~> 1.1.0                          | Source Pinning: 2.0.0
               v                                                   v
+-------------------------------+                 +--------------------------------+
| Staging Root Module           |                 | Production Root Module         |
| (environments/staging)        |                 | (environments/production)      |
| - Safely upgraded to 1.1.0    |                 | - Pinned to 2.0.0 after test   |
| - Consumes v1 contracts       |                 | - Migrated to v2 contract      |
+-------------------------------+                 +--------------------------------+
```

### Arsitektur Enkapsulasi vs Exposure
```
                CALLER (Root Module / Live Environment)
                         |                  ^
  Input Variables        |                  |  Outputs
  (Strictly Validated)   |                  |  (Sanitized & Controlled)
                         v                  |
+--------------------------------------------------------------------+
| CHILD MODULE (Black Box Enkapsulasi)                               |
|                                                                    |
|   +-------------------+                     +------------------+   |
|   | Local Resources   | <--- internal ----> | Local Variables  |   |
|   | - AWS Subnet      |      dependency     | - Computed CIDRs |   |
|   | - Route Table     |                     +------------------+   |
|   +-------------------+                                            |
|             |                                                      |
|             v (Resource Creation)                                  |
|   +-------------------+                                            |
|   | aws_db_instance   | ---> [ Sensitive Password ] (SUPPRESSED)   |
|   +-------------------+ ---> [ Connection String  ] (EXPOSED-SENS) |
+--------------------------------------------------------------------+
```

---

## 9. Simple Example
Contoh child module sederhana untuk Resource Module S3 Bucket dengan enkapsulasi enkripsi dan validasi naming.

### `modules/secure_bucket/variables.tf`
```hcl
variable "bucket_name" {
  type        = string
  description = "Nama bucket S3 yang harus diawali dengan prefix 'ent-' dan hanya berisi karakter alfanumerik serta tanda hubung."

  validation {
    condition     = can(regex("^ent-[a-z0-9-]+$", var.bucket_name))
    error_message = "Prefix bucket wajib 'ent-' dan hanya huruf kecil, angka, atau tanda hubung yang diizinkan."
  }
}

variable "environment" {
  type        = string
  description = "Lingkungan runtime target."

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Nilai environment harus salah satu dari: development, staging, production."
  }
}
```

### `modules/secure_bucket/main.tf`
```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

resource "aws_s3_bucket" "this" {
  bucket = var.bucket_name

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# Enkapsulasi: Enkripsi selalu diaktifkan, tidak dapat diubah oleh root module
resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
```

### `modules/secure_bucket/outputs.tf`
```hcl
output "bucket_arn" {
  value       = aws_s3_bucket.this.arn
  description = "Amazon Resource Name (ARN) dari bucket S3 yang terbuat."
}

output "bucket_domain_name" {
  value       = aws_s3_bucket.this.bucket_domain_name
  description = "FQDN dari bucket S3."
}
```

---

## 10. Practical Example (Konfigurasi CLI / Terraform / Hands-on)

Berikut adalah implementasi modul komposit enterprise: **Network Layer Module** yang memisahkan public/private subnet dan mengontrol exposure gateway.

### File Structure
```
infra-modules/
└── modules/
    └── aws_network_tier/
        ├── versions.tf
        ├── variables.tf
        ├── main.tf
        └── outputs.tf
```

### File: `modules/aws_network_tier/versions.tf`
```hcl
terraform {
  required_version = ">= 1.5.0, < 2.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.20"
    }
  }
}
```

### File: `modules/aws_network_tier/variables.tf`
```hcl
variable "vpc_cidr" {
  type        = string
  description = "CIDR block utama untuk Virtual Private Cloud."

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "vpc_cidr harus berupa format IPv4 CIDR notation yang valid (contoh: 10.0.0.0/16)."
  }
}

variable "availability_zones" {
  type        = list(string)
  description = "Daftar Availability Zones target."

  validation {
    condition     = length(var.availability_zones) >= 2
    error_message = "High Availability mewajibkan minimal 2 Availability Zones."
  }
}

variable "enable_nat_gateway" {
  type        = bool
  default     = true
  description = "Flag boolean untuk menentukan apakah NAT Gateway dibuat di public subnet."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Metadata tags tambahan."
}
```

### File: `modules/aws_network_tier/main.tf`
```hcl
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(var.tags, {
    Name = "vpc-${terraform.workspace}"
  })
}

resource "aws_internet_gateway" "gw" {
  vpc_id = aws_vpc.main.id

  tags = merge(var.tags, {
    Name = "igw-${terraform.workspace}"
  })
}

# Subnetting otomatis menggunakan fungsi cidrsubnet
resource "aws_subnet" "public" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = merge(var.tags, {
    Name = "subnet-public-${var.availability_zones[count.index]}"
    Tier = "Public"
  })
}

resource "aws_subnet" "private" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + length(var.availability_zones))
  availability_zone = var.availability_zones[count.index]

  tags = merge(var.tags, {
    Name = "subnet-private-${var.availability_zones[count.index]}"
    Tier = "Private"
  })
}

resource "aws_eip" "nat" {
  count  = var.enable_nat_gateway ? 1 : 0
  domain = "vpc"

  tags = merge(var.tags, {
    Name = "eip-nat"
  })
}

resource "aws_nat_gateway" "nat" {
  count         = var.enable_nat_gateway ? 1 : 0
  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.public[0].id

  tags = merge(var.tags, {
    Name = "nat-gateway"
  })

  depends_on = [aws_internet_gateway.gw]
}
```

### File: `modules/aws_network_tier/outputs.tf`
```hcl
output "vpc_id" {
  value       = aws_vpc.main.id
  description = "Identifier unik dari VPC yang dibuat."
}

output "vpc_cidr" {
  value       = aws_vpc.main.cidr_block
  description = "CIDR range yang dialokasikan pada VPC."
}

output "public_subnet_ids" {
  value       = aws_subnet.public[*].id
  description = "Daftar ID untuk seluruh public subnets."
}

output "private_subnet_ids" {
  value       = aws_subnet.private[*].id
  description = "Daftar ID untuk seluruh private subnets."
}

output "nat_gateway_ip" {
  value       = var.enable_nat_gateway ? aws_eip.nat[0].public_ip : null
  description = "Public IP address dari NAT Gateway (null jika dinonaktifkan)."
}
```

### Pemanggilan di Root Module (`live/production/main.tf`)
```hcl
provider "aws" {
  region = "ap-southeast-1"
}

module "network" {
  source = "../../modules/aws_network_tier"

  vpc_cidr           = "10.100.0.0/16"
  availability_zones = ["ap-southeast-1a", "ap-southeast-1b"]
  enable_nat_gateway = true

  tags = {
    CostCenter  = "Core-Infra-9901"
    Environment = "Production"
  }
}

output "prod_vpc_id" {
  value = module.network.vpc_id
}
```

---

## 11. Real World Example
Sebuah institusi fintech skala nasional memiliki standar regulasi OJK/Bank Indonesia di mana semua database RDS PostgreSQL dilarang terekspos ke internet publik, wajib mengaktifkan Storage Encryption via AWS KMS Customer Managed Key (CMK), dan rotasi password dikelola via AWS Secrets Manager.

Arsitektur modul enterprise yang diimplementasikan:
1. **L1 KMS Module**: Mengelola CMK dengan rotasi otomatis 1 tahun sekali.
2. **L1 Subnet Group Module**: Mengelompokkan subnet privat terisolasi.
3. **L2 Enterprise RDS Module**: Mengomposisikan modul KMS, Subnet Group, dan AWS RDS Instance. Modul ini membungkus password di dalam AWS Secrets Manager dan **tidak pernah mengembalikan plaintext password** sebagai output modul.

```hcl
# outputs.tf pada Enterprise RDS Module
output "db_endpoint" {
  value       = aws_db_instance.db.endpoint
  description = "Endpoint koneksi RDS instance."
}

output "db_secret_arn" {
  value       = aws_secretsmanager_secret.db_credentials.arn
  description = "ARN dari AWS Secrets Manager yang menyimpan kredensial database."
}

# Plaintext password disembunyikan total
# Klien downstream wajib mengambilnya via AWS IAM Role ke Secrets Manager
```

Hasil audit keamanan: 0 temuan Plaintext Credential Exposure pada log state dan pipeline CI.

---

## 12. Trade-offs

| Aspek | Modul Monolitik Flat | Fine-Grained Composable Modules |
| :--- | :--- | :--- |
| **Reusability** | Sangat Rendah (Copy-Paste) | Sangat Tinggi (Digunakan lintas tim) |
| **Kompleksitas Awal** | Rendah (Cepat di awal) | Tinggi (Butuh desain interface & contracts) |
| **Maintenance Overhead** | Tinggi seiring berjalannya waktu | Rendah, perubahan terisolasi per versi |
| **Pipeline Run Time** | Lama (Plan seluruh resource cloud) | Cepat (Hanya merencanakan slice modul) |
| **Blast Radius Risiko** | Ekstrem (Seluruh sistem terdampak) | Minimal (Terkurung pada modul spesifik) |
| **State File Size** | Sangat besar (Rawan race condition) | Terfragmentasi dengan aman |

---

## 13. When To Use
- Ketika infrastruktur digunakan oleh lebih dari satu tim atau lebih dari satu deployment environment (*dev, uat, prod*).
- Ketika Anda ingin menerapkan standarisasi keamanan terpusat (*Centralized Security Guardrails*).
- Ketika siklus hidup komponen berbeda (misal: siklus hidup Network berubah 6 bulan sekali, sedangkan siklus hidup EKS Pod/Compute berubah tiap hari).
- Ketika organisasi membangun arsitektur Platform Engineering berbasis *Internal Developer Platform* (IDP).

---

## 14. When NOT To Use
- **One-off PoC (Proof of Concept)**: Ketika membuat prototipe sekali pakai yang akan dihapus dalam 48 jam.
- **Micro-wrapper Anti-pattern**: Membungkus resource tunggal yang hanya memiliki 2 baris parameter tanpa menambahkan validasi logika bisnis, default value standar, atau tagging mandatory (contoh: membuat modul hanya untuk `aws_s3_bucket_acl`). Ini hanya menambah boilerplate (*cognitive load* tinggi).
- **Proyek Mahasiswa/Pribadi Skala Mikro**: Jika infrastruktur hanya terdiri dari 1 EC2 instance dan 1 Security Group, abstraksi modul hanya menimbulkan friksi yang tidak perlu.

---

## 15. Common Mistakes
1. **Hardcoding Provider di Child Module**:
   ```hcl
   # SALAH: Didalam Child Module
   provider "aws" {
     region = "us-east-1"
   }
   ```
   *Dampak*: Modul tidak bisa digunakan di region lain oleh pemanggil dan menimbulkan crash saat manipulasi multi-region provider.
2. **Missing SemVer Pinning**:
   ```hcl
   # SALAH: Mengarah langsung ke branch default
   module "vpc" {
     source = "git::https://github.com/org/terraform-aws-vpc.git"
   }
   ```
   *Dampak*: Ketika maintainer modul melakukan commit breaking change ke branch `main`, pipeline production pemanggil akan langsung rusak tanpa peringatan.
3. **Leaky Abstraction (Mengabaikan Enkapsulasi)**:
   Meneruskan variabel raw yang tidak divalidasi dan membuka akses parameter internal low-level cloud provider secara langsung sehingga menyulitkan migrasi arsitektur di masa depan.
4. **Mengekspos Secret secara Plaintext pada Output**:
   Lupa menyematkan `sensitive = true` pada variabel output yang membawa connection string atau generated passwords.

---

## 16. Best Practices
1. **Semantic Version Pinning**: Selalu kunci versi modul pada Root Module menggunakan constraint operator:
   ```hcl
   module "vpc" {
     source  = "app.terraform.io/corp/vpc/aws"
     version = "~> 2.1.0" # Hanya patch updates otomatis diizinkan
   }
   ```
2. **Defensive Input Validation**: Validasi setiap variable dengan custom regex, batas integer, atau validasi fungsional (`can()`, `cidrhost()`, `regex()`).
3. **Minimal Output Surface Area**: Hanya ekspos data yang terbukti dibutuhkan oleh child module lain atau root module.
4. **Automated Testing & Linting**: Validasi format kode (`terraform fmt -check`), linting sintaks (`tflint`), dan security scanner (`trivy` / `checkov`) pada repositori modul sebelum tag git dirilis.
5. **Standardized Directory Structure**: Sediakan folder `examples/` di repositori modul untuk memudahkan onboarding engineer lain.

---

## 17. Troubleshooting

### Problem 1: Circular Dependency Between Modules
- **Gejala**: Error `Cycle: module.app -> module.database -> module.app`.
- **Root Cause**: Modul database membutuhkan `security_group_id` dari modul app, sedangkan modul app membutuhkan `db_endpoint` dari modul database.
- **Solusi**: Pisahkan resource penghubung (misalnya Security Group Rule) ke luar kedua modul tersebut, atau tempatkan di Root Module agar dependensi mengalir secara searah (*Directed Acyclic Graph*).

### Problem 2: Provider Version Conflict
- **Gejala**: `Error: Unresolvable provider configuration: Provider aws is required by module.network with version ~> 4.0, but root module requires >= 5.0`.
- **Root Cause**: Child module memiliki constraint versi yang terlalu kaku (*overly strict*).
- **Solusi**: Longgarkan constraint versi di `versions.tf` child module: gunakan operator `>= 4.0.0, < 6.0.0` untuk fleksibilitas caller.

### Problem 3: Sensitive Output Blocked in CI Logs
- **Gejala**: Terraform melempar error: `Output refers to sensitive values and must be marked as sensitive`.
- **Root Cause**: Output mengambil referensi dari resource yang memiliki atribut sensitive (misal: `aws_iam_access_key.secret`).
- **Solusi**: Tambahkan blok `sensitive = true` pada blok `output` yang bersangkutan.

---

## 18. Exercise
Buatlah sebuah Resource Module mandiri bernama `terraform-aws-secure-s3` dengan kriteria:
1. Menerima variabel `bucket_name` yang divalidasi harus lowercase, tidak boleh mengandung spasi, dan memiliki panjang antara 3 hingga 63 karakter.
2. Menerima variabel `lifecycle_glacier_transition_days` (tipe `number`) dengan validasi nilainya harus lebih besar dari atau sama dengan `30` hari.
3. Mengonfigurasi enkripsi wajib menggunakan AES256.
4. Mengembalikan output `bucket_arn` dan `kms_key_id` (jika menggunakan custom KMS).
5. Buat struktur file lengkap: `versions.tf`, `variables.tf`, `main.tf`, `outputs.tf`.

---

## 19. Challenge
Rancang arsitektur modul enterprise **3-Tier Application Blueprint**:
- Buat sebuah pattern module bernama `blueprint-webapp-aws` yang mengomposisikan:
  1. Virtual Private Cloud (Network Module)
  2. Compute Autoscaling Group (Web Tier Module)
  3. Relational Database Service (RDS Postgres Module)
- **Aturan Ketat**:
  - Web Tier tidak boleh berkomunikasi langsung dengan Database menggunakan Public IP.
  - Modul RDS tidak boleh menerima password via plaintext variable; password harus di-generate via provider `random_password` atau AWS Secrets Manager di dalam modul.
  - Implementasikan conditional logic: jika variable `enable_multi_az` bernilai `true`, pastikan validasi memeriksa bahwa minimal ada 3 Availability Zones yang dipasok ke modul jaringan.
  - Sediakan file validasi otomatis menggunakan skrip CI/CD atau test harness linter.

---

## 20. Summary
Arsitektur modul Terraform enterprise bukan sekadar memecah file `.tf` ke dalam folder. Ini adalah disiplin rekayasa perangkat lunak yang menuntut:
- **Pemisahan Peran**: Root module menentukan *apa yang akan di-deploy dan di mana*, sedangkan Child module menentukan *bagaimana standar infrastruktur dibangun*.
- **Kontrak Antarmuka Stabil**: Menggunakan input validation defensif dan output sanitization yang ketat.
- **Manajemen Siklus Hidup Dependensi**: Penguncian versi berbasis Semantic Versioning (SemVer) untuk mencegah kegagalan pipeline tak terduga.
- **Kepatuhan dan Keamanan Terenkapsulasi**: Standar keamanan di-embed langsung ke dalam modul, memastikan kepatuhan regulasi industri secara *de facto* bagi seluruh tim pengembang.