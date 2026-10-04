# BAB 05: Enterprise Module Architecture & Reusability
## MODUL 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

1. **Merancang Arsitektur Modular Skala Enterprise**: Menerapkan pola *Atomic Module* (komponen tunggal terisolasi) dan *Composite/Facade Module* (orkestrasi multi-komponen) sesuai prinsip *Separation of Concerns* (SoC) dan *Single Responsibility Principle* (SRP).
2. **Mengimplementasikan Provider Inversion & Multi-Provider Aliasing**: Mengeliminasi deklarasi *hardcoded provider* di dalam *child module* dan mengimplementasikan `configuration_aliases` untuk orkestrasi multi-region serta multi-account yang deterministik.
3. **Membangun Kontrak Validasi Lanjutan**: Mengamankan *input/output boundary* modul menggunakan *custom variable validation*, `precondition`, dan `postcondition` berbasis HCL2 untuk mencegah *misconfiguration* sebelum fasa deployment.
4. **Menerapkan Zero-Downtime Module Refactoring**: Mengeksekusi rekonstruksi struktur modul produksi tanpa memicu *recreation* destruktif terhadap sumber daya (*state thrashing*) menggunakan deklaratif `moved` blocks.
5. **Mengotomatisasi Native Module Testing**: Mengonfigurasi dan menjalankan *integration & unit testing* modul secara deklaratif menggunakan fitur bawaan Terraform Test framework (`.tftest.hcl`).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:

* **Dasar Terraform Engine**: Siklus kerja `init`, `plan`, `apply`, `destroy`, dan manipulasi Terraform State.
* **HCL2 Primitives**: Ekspresi kondisional (`ternary`), manipulasi tipe kompleks (`object`, `map`, `list(set)`), *for expressions*, dan *splat syntax*.
* **Dasar Cloud Networking**: Konsep VPC, CIDR block slicing, routing table, NAT Gateway, dan Security Group (AWS/GCP/Azure).
* **Terraform CLI**: Versi $\ge$ 1.6.x (wajib untuk dukungan penuh blok `test` dan `moved` lintas modul).

---

### 3. Concept & Internal Architecture

Arsitektur modul enterprise bukan sekadar memisahkan kode HCL ke dalam beberapa direktori. Arsitektur ini adalah pembentukan batas isolasi (*boundary isolation*) yang dievaluasi oleh Terraform Core melalui *Directed Acyclic Graph* (DAG).

```
                      +-----------------------------+
                      |      Root Module (main)     |
                      |  - Injeksi Root Provider    |
                      |  - Orkestrasi Environment   |
                      +--------------+--------------+
                                     |
              +----------------------+----------------------+
              | Provider Aliases:                           |
              |   aws.us_east_1                             | Provider Default:
              |   aws.eu_central_1                          |   aws.primary
              v                                             v
+-------------------------------+             +-------------------------------+
| Composite/Facade Module       |             | Composite/Facade Module       |
| (Edge Networking & CDN)       |             | (Core App & Data Layer)       |
+---------------+---------------+             +---------------+---------------+
                |                                             |
        +-------+-------+                             +-------+-------+
        v               v                             v               v
+---------------+---------------+             +---------------+---------------+
| Atomic Module | Atomic Module |             | Atomic Module | Atomic Module |
| (ACM Cert)    | (CloudFront)  |             | (VPC Subnets) | (RDS Cluster) |
+---------------+---------------+             +---------------+---------------+
```

#### A. Directed Acyclic Graph (DAG) Resolution pada Nested Modules
Terraform Core membangun dependency graph dengan menyisipkan node dari *child module* ke dalam root DAG:
1. **Expansion Phase**: Setiap pemanggilan `module "foo"` di-*expand*. Jika modul menggunakan `for_each` atau `count`, Terraform menduplikasi sub-graph modul tersebut sebanyak instansiasi yang didefinisikan.
2. **Variable Wiring**: Nilai diteruskan dari *parent* ke *child* sebagai node dependensi. *Child module* tidak dapat membaca variabel *parent* kecuali dioper secara eksplisit melalui argumen modul.
3. **Provider Inheritance**: Secara *default*, child module mewarisi provider dari parent module. Namun, mendefinisikan blok `provider` di dalam child module dianggap sebagai *anti-pattern berat* karena memecah kemampuan Terraform untuk memprediksi destruksi sumber daya (*reverse dependency analysis*).

#### B. Dynamic Blocks dan Evaluasi Konfigurasi Kolektif
Penggunaan `dynamic` block di dalam atomic module mengonstruksi nested block secara programatis berdasarkan koleksi data (*map/list of objects*). Terraform mengevaluasi iterator pada dynamic block di fasa kompilasi graph:
* Setiap elemen dalam iterator menghasilkan satu blok HCL yang valid.
* Nilai kosong (`[]` atau `null`) menyebabkan blok tersebut diabaikan total, mempertahankan idempotensi resource.

#### C. Validation & Contract Enforcement Lifecycle
Terraform mengeksekusi validasi kontrak data dalam tiga tahapan siklus:
1. **Variable Validation (`validation` block)**: Dievaluasi pada fasa awal *Plan* sebelum konfigurasi dieksekusi terhadap real world API. Tidak dapat merujuk ke atribut resource yang baru diketahui setelah *apply* (`known after apply`).
2. **Preconditions (`precondition` block)**: Dievaluasi sesaat sebelum resource atau data source dieksekusi. Dapat mengevaluasi dependensi lain yang sudah berstatus konkrit.
3. **Postconditions (`postcondition` block)**: Dievaluasi sesaat setelah resource selesai dibuat/dimodifikasi. Menginspeksi atribut aktual dari API cloud provider untuk memastikan *state integrity* (misal: memeriksa apakah VPC peering status benar-benar `active`).

---

### 4. Why & What

| Dimensi | Anti-Pattern: Monolithic/Ad-hoc Module | Best Practice: Enterprise Scalable Module |
| :--- | :--- | :--- |
| **Provider Assignment** | Provider dikonfigurasi langsung di dalam modul anak (`provider "aws" { region = ... }`). Menyebabkan modul terkunci, gagal dalam operasi `destroy`, dan melanggar portabilitas. | Provider diinjeksi dari Root Module menggunakan `configuration_aliases`. Modul anak bersifat agnostik terhadap region dan kredensial. |
| **Fleksibilitas Desain** | Hardcoding parameter jaringan, naming convention statis, ketergantungan implisit antar-resource. | Input berbasis objek terstruktur (`type = object(...)`), dynamic blocks, dan *feature toggling* via ternary condition. |
| **Integritas Kontrak** | Tipe data didefinisikan secara longgar (`type = any`), ketiadaan validasi logika input. | Tipe data strict (`type = object({ ... })`), *custom validation rules* berbasis regex/koleksi, `precondition`/`postcondition`. |
| **Siklus Refactoring** | Memindahkan resource ke modul baru mengharuskan penghapusan state manual (`state rm`) dan impor ulang (`import`), memicu downtime. | Refactoring deklaratif menggunakan `moved` blocks. State dipetakan ulang otomatis tanpa mutasi fisik pada infrastruktur. |
| **Quality Assurance** | Validasi manual dengan `terraform plan` di environment staging. Rawan *human error*. | Test terisolasi menggunakan native `terraform test` (`.tftest.hcl`) yang menguji skenario positif, negatif, dan destruksi state tiruan. |

---

### 5. How (Workflow Detail)

Alur kerja pengembangan modul enterprise terstandarisasi:

```
[Contract Definition]
         |
         v
[TDD: .tftest.hcl Formulation] <---+ (Gagal Test)
         |                         |
         v                         |
[HCL Implementation]               |
  - Atomic Resource Mapping        |
  - Validation & Preconditions     |
         |                         |
         v                         |
[Execution: terraform test] -------+
         | (Lolos Test)
         v
[Refactoring via moved blocks]
         |
         v
[Semantic Version Release (Git Tag)]
         |
         v
[Consumption in Composite Root]
```

1. **Definisi Kontrak (API Boundary)**: Menentukan schema input (`variables.tf`) dan output (`outputs.tf`).
2. **Formulasi Test (TDD)**: Menulis skenario pengujian pada berkas `tests/*.tftest.hcl` sebelum menulis logika infrastruktur secara penuh.
3. **Implementasi HCL**: Menulis resource logic, menerapkan `configuration_aliases` untuk multi-provider, dynamic blocks, serta `validation` rule.
4. **Verifikasi Test**: Menjalankan command `terraform test`. Terraform membuat infrastruktur ephemeral (atau melakukan evaluasi mock) dan mengeksekusi assertion.
5. **State Refactoring Deployment**: Jika modul mengalami perubahan path struktural, tambahkan deklarasi `moved { from = ... to = ... }` untuk memastikan migrasi resource mulus bagi para konsumer modul.
6. **Tagging & Distribusi**: Menerapkan Git semantic versioning (`vX.Y.Z`). Parent module hanya boleh mereferensikan modul melalui tag release yang *immutable*.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Berorientasi Objek & Dependency Injection
Pikirkan Root Module sebagai sebuah **Application Container** (seperti Spring Boot atau NestJS), Composite Module sebagai **Domain Service Layer**, dan Atomic Module sebagai **Data Access Object (DAO)** atau **Micro-component Library**.

* **Root Module**: Mengonfigurasi koneksi database, kredensial, dan env-vars (Providers), lalu menginjeksikannya ke dalam class.
* **Child Module**: Tidak boleh membuat koneksi databasenya sendiri secara *hardcoded* (tidak boleh mendefinisikan instance provider). Modul anak menerima *interface* (Provider Aliases) melalui teknik *Dependency Injection*.

#### Diagram Interaksi Multi-Tier Module & Provider Routing

```
================ ROOT CONTEXT (main.tf) =================
  Provider "aws" { alias = "primary"  } // us-east-1
  Provider "aws" { alias = "secondary"} // eu-central-1
                            |
  +-------------------------+-------------------------+
  | Injeksi Provider                                  | Injeksi Provider
  v                                                   v
+-------------------------------+   +-------------------------------+
| module "network_us"           |   | module "network_eu"           |
| providers = {                 |   | providers = {                 |
|   aws = aws.primary           |   |   aws = aws.secondary         |
| }                             |   | }                             |
|                               |   |                               |
|   +-----------------------+   |   |   +-----------------------+   |
|   | Child: aws_vpc        |   |   |   | Child: aws_vpc        |   |
|   | Child: aws_subnet (xN)|   |   |   | Child: aws_subnet (xN)|   |
|   +-----------------------+   |   |   +-----------------------+   |
+-------------------------------+   +-------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Atomic Module dengan Contract Validation
Contoh modul atomic untuk membuat AWS S3 Bucket terisolasi dengan validasi penamaan standar korporat dan postcondition enkripsi.

```hcl
# modules/s3_atomic/variables.tf
variable "bucket_name" {
  type        = string
  description = "Nama S3 bucket. Wajib mengikuti format: corp-<env>-<app>-<suffix>."

  validation {
    condition     = can(regex("^corp-(dev|stage|prod)-[a-z0-9]+-[a-z0-9]+$", variable.bucket_name))
    error_message = "bucket_name tidak valid. Wajib diawali 'corp-', env ('dev'/'stage'/'prod'), dan karakter alfanumerik huruf kecil dipisahkan tanda strip (-)."
  }
}

variable "force_destroy" {
  type        = bool
  default     = false
  description = "Proteksi penghapusan data secara paksa."
}

# modules/s3_atomic/main.tf
resource "aws_s3_bucket" "this" {
  bucket        = var.bucket_name
  force_destroy = var.force_destroy

  lifecycle {
    prevent_destroy = false # Set true untuk proteksi penuh di environment non-ephemeral
    postcondition {
      condition     = self.bucket_domain_name != ""
      error_message = "Bucket gagal diprovisi dengan domain name valid oleh AWS API."
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# modules/s3_atomic/outputs.tf
output "bucket_id" {
  value       = aws_s3_bucket.this.id
  description = "Identifier S3 Bucket."
}

output "bucket_arn" {
  value       = aws_s3_bucket.this.arn
  description = "ARN dari S3 Bucket yang telah diamankan."
}
```

---

#### B. Practical Enterprise Example: Composite Network Facade Module
Arsitektur tingkat produksi: Sebuah composite module yang membungkus VPC, Subnetting dengan Dynamic Allocation, Route Tables, serta Provider Aliasing untuk Edge Invalidation / Cross-Region Inspection.

##### Struktur Direktori
```
modules/enterprise_networking/
├── main.tf
├── variables.tf
├── outputs.tf
└── versions.tf
```

##### 1. versions.tf (Deklarasi Provider Alias Dependency Inversion)
```hcl
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
      # Deklarasi ekspektasi alias yang harus dioper dari pemanggil (Root)
      configuration_aliases = [
        aws.primary,
        aws.edge_accelerator
      ]
    }
  }
}
```

##### 2. variables.tf (Advanced Object Schema & Pre-validations)
```hcl
variable "network_topology" {
  type = object({
    vpc_cidr             = string
    enable_dns_hostnames = bool
    enable_dns_support   = bool
    subnets = map(object({
      cidr_block        = string
      availability_zone = string
      is_public         = bool
    }))
  })
  description = "Topologi spesifikasi VPC dan Subnets."

  validation {
    condition     = can(cidrnetmask(var.network_topology.vpc_cidr))
    error_message = "vpc_cidr harus berupa string CIDR IPv4 yang valid (misal: 10.0.0.0/16)."
  }

  validation {
    condition     = length(var.network_topology.subnets) >= 2
    error_message = "Arsitektur Enterprise mewajibkan minimal 2 subnet untuk ketersediaan High Availability."
  }
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Metadata tag resource."
}
```

##### 3. main.tf (Dynamic Implementation, Separation, Pre/Post-conditions)
```hcl
# Resource VPC Utama dieksekusi menggunakan provider primary
resource "aws_vpc" "core" {
  provider             = aws.primary
  cidr_block           = var.network_topology.vpc_cidr
  enable_dns_hostnames = var.network_topology.enable_dns_hostnames
  enable_dns_support   = var.network_topology.enable_dns_support

  tags = merge(
    var.tags,
    {
      Name = "corp-core-vpc"
      ManagedBy = "Terraform-Enterprise-Module"
    }
  )

  lifecycle {
    precondition {
      condition     = tonumber(split("/", var.network_topology.vpc_cidr)[1]) <= 20
      error_message = "CIDR block VPC terlalu sempit (subnet mask > /20). Kapasitas IP tidak memadai untuk skala Enterprise."
    }
  }
}

# Subnets diekspansi secara deterministik menggunakan for_each
resource "aws_subnet" "managed_subnets" {
  for_each          = var.network_topology.subnets
  provider          = aws.primary
  vpc_id            = aws_vpc.core.id
  cidr_block        = each.value.cidr_block
  availability_zone = each.value.availability_zone

  map_public_ip_on_launch = each.value.is_public

  tags = merge(
    var.tags,
    {
      Name = "corp-subnet-${each.key}"
      Tier = each.value.is_public ? "Public" : "Private"
    }
  )

  lifecycle {
    postcondition {
      condition     = can(regex("^${aws_vpc.core.cidr_block[0]}", self.cidr_block))
      error_message = "Alokasi CIDR Subnet ${each.key} berada di luar jangkauan blok CIDR VPC."
    }
  }
}

# Edge WAF Rule yang dipaksa deploy di region global/us-east-1 via provider alias aws.edge_accelerator
resource "aws_wafv2_ip_set" "edge_inspection" {
  provider           = aws.edge_accelerator
  name               = "edge-allowlist-${aws_vpc.core.id}"
  description        = "IP Allowlist untuk edge proxy yang mereferensikan core VPC"
  scope              = "CLOUDFRONT"
  ip_address_version = "IPV4"
  addresses          = ["192.0.2.0/24"]

  tags = var.tags
}
```

##### 4. outputs.tf (Unified Data Contract)
```hcl
output "vpc_id" {
  value       = aws_vpc.core.id
  description = "ID dari VPC yang berhasil diprovisi."
}

output "private_subnet_ids" {
  value = [
    for k, v in aws_subnet.managed_subnets : v.id if !var.network_topology.subnets[k].is_public
  ]
  description = "Daftar ID Subnet Private untuk isolasi tier data/komputasi."
}

output "public_subnet_ids" {
  value = [
    for k, v in aws_subnet.managed_subnets : v.id if var.network_topology.subnets[k].is_public
  ]
  description = "Daftar ID Subnet Public untuk tier ingress/load balancer."
}

output "edge_ip_set_arn" {
  value       = aws_wafv2_ip_set.edge_inspection.arn
  description = "ARN dari Edge WAF IP Set yang berada di region edge provider."
}
```

##### 5. Penerapan pada Root Module (Konsumsi)
```hcl
# root/main.tf
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  alias  = "tokyo"
  region = "ap-northeast-1"
}

provider "aws" {
  alias  = "virginia"
  region = "us-east-1"
}

module "enterprise_network" {
  source = "./modules/enterprise_networking"

  providers = {
    aws.primary          = aws.tokyo
    aws.edge_accelerator = aws.virginia
  }

  network_topology = {
    vpc_cidr             = "10.100.0.0/16"
    enable_dns_hostnames = true
    enable_dns_support   = true
    subnets = {
      "app-1a" = {
        cidr_block        = "10.100.1.0/24"
        availability_zone = "ap-northeast-1a"
        is_public         = false
      },
      "app-1c" = {
        cidr_block        = "10.100.2.0/24"
        availability_zone = "ap-northeast-1c"
        is_public         = false
      },
      "public-1a" = {
        cidr_block        = "10.100.10.0/24"
        availability_zone = "ap-northeast-1a"
        is_public         = true
      }
    }
  }

  tags = {
    Environment = "production"
    CostCenter  = "infrastructure-core"
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Zero-Downtime State Refactoring Pasca Restrukturisasi Monolith ke Multi-Module (PT FinTech Payment Gateway)

* **Konteks**: Platform pemrosesan transaksi FinTech memiliki 1 codebase monolithic Terraform state berukuran 18 MB yang menampung 450 resource. Tim engineering memutuskan untuk mengekstrak VPC, NAT Gateways, dan Database Cluster ke dalam Composite Reusable Modules independen guna standarisasi multi-region DR.
* **Tantangan**: Pemindahan deklarasi resource HCL ke modul terpisah (`module.core_network.aws_vpc.this`) menyebabkan Terraform mengevaluasi pemindahan tersebut sebagai operasi *destroy-and-recreate*. Downtime pada core routing table dan NAT Gateway berarti memutus traffic payment gateway aktif (potensi kerugian finansial ~IDR 400 Juta/menit).
* **Solusi**: Penggunaan deklaratif **HCL `moved` blocks** di dalam kode untuk restrukturisasi state secara *in-place* tanpa intervensi `terraform state mv` manual lewat CLI yang rawan *human error*.

##### Eksekusi Refactoring

Sebelum refactoring, resource berada langsung di Root Level:
```hcl
# Versi Monolithic Sebelumnya (Root Level)
resource "aws_vpc" "production" {
  cidr_block = "172.16.0.0/16"
  # ...
}

resource "aws_nat_gateway" "gw" {
  allocation_id = "eipalloc-0123456789abcdef"
  # ...
}
```

Setelah modularisasi, engineer mengekstrak logic ke `modules/vpc` dan memanggilnya via `module "network"`. Untuk mencegah destruksi, engineer menambahkan deklarasi pemetaan berikut pada berkas `refactors.tf`:

```hcl
# refactors.tf (Ditaruh di Root Module)
moved {
  from = aws_vpc.production
  to   = module.network.aws_vpc.core
}

moved {
  from = aws_nat_gateway.gw
  to   = module.network.aws_nat_gateway.nat["primary"]
}
```

Hasil eksekusi `terraform plan`:
```text
Terraform will perform the following actions:

  # aws_vpc.production has moved to module.network.aws_vpc.core
    ~ resource "aws_vpc" "core" {
        id = "vpc-0abcd1234ef56789a"
        # (semua konfigurasi state dipertahankan, zero recreation)
      }

  # aws_nat_gateway.gw has moved to module.network.aws_nat_gateway.nat["primary"]
    ~ resource "aws_nat_gateway" "nat" {
        id = "nat-0987654321fedcba0"
      }

Plan: 0 to add, 0 to change, 0 to destroy.
```
*Hasil*: State berhasil dipetakan ke dalam arsitektur nested module baru tanpa ada satu pun socket network yang terputus di fasa *Apply*.

---

### 9. Trade-offs

Mengadopsi pola enterprise module memperkenalkan konsekuensi arsitektural yang harus dikalkulasi:

| Aspek Arsitektural | Keuntungan (Pros) | Biaya / Trade-off (Cons) |
| :--- | :--- | :--- |
| **Abstraksi Composite (Facade)** | Kompleksitas internal cloud disembunyikan dari developer; *golden path* keamanan dan tagging otomatis di-enforce seragam di seluruh organisasi. | **Abstraction Leaking**: Jika developer membutuhkan parameter spesifik yang belum diekspos oleh modul facade, mereka terblokir (*bottleneck* pada maintainer modul). |
| **Granular Atomic Modules** | Reusability sangat tinggi; modul atomic (misal: S3, IAM) mudah diuji (*unit testable*) secara terisolasi dengan state yang kecil. | **Graph Traversal Overhead & Latency**: Semakin banyak modul yang di-*nesting*, waktu parsing Terraform DAG meningkat drastis saat eksekusi `terraform plan`. |
| **Strict Type Constraints (`object`)** | Kontrak parameter sangat ketat, kesalahan terdeteksi dini di CLI sebelum interaksi cloud provider. | **Breaking Changes Cascading**: Perubahan schema kecil pada object dapat memecahkan kompatibilitas ke banyak root module konsumer, mewajibkan version pinning ketat. |
| **In-Module Validations & Preconditions** | Mencegah state corruption akibat miskonfigurasi logic deployment. | Menghambat fleksibilitas saat ada skenario *exception* (misal: migrasi legacy infrastructure yang melanggar aturan standard naming baru). |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Menaruh Blok `provider` di Dalam Child Module
* **Gejala**: Error `Error: Module does not support provider configuration` saat menjalankan operasi atau state deletion gagal karena ketergantungan terbalik.
* **Akar Masalah**: Deklarasi `provider "aws" { ... }` langsung di child module. Child module tidak boleh mengatur instansiasi provider; modul anak hanya boleh mendefinisikan *interface*.
* **Solusi**: Gunakan blok `proxy provider` lewat `configuration_aliases` pada child module, lalu injeksikan dari parent:
  ```hcl
  # Child module versions.tf
  terraform {
    required_providers {
      aws = {
        source                = "hashicorp/aws"
        configuration_aliases = [aws.target_region]
      }
    }
  }
  ```

#### Kesalahan 2: State Thrashing Akibat Penggunaan `count` Berdasarkan List Indeks
* **Gejala**: Terraform mendeteksi penghapusan dan pembuatan ulang puluhan subnet saat satu item di tengah list dihapus.
* **Akar Masalah**: Penggunaan `count = length(var.subnets)` di mana resource diberi alamat indeks numerik (`aws_subnet.this[0]`, `aws_subnet.this[1]`). Mengubah urutan array menyebabkan *index shift*.
* **Solusi**: Migrasi secara wajib ke `for_each` dengan input berbasis `map` atau `set(string)`. Kunci map mempertahankan identitas deterministik:
  ```hcl
  # modules/subnet/main.tf
  resource "aws_subnet" "this" {
    for_each          = { for s in var.subnets : s.name => s }
    cidr_block        = each.value.cidr
    availability_zone = each.value.az
  }
  ```

#### Kesalahan 3: Missing `moved` Blocks saat Mengubah Identifier `for_each`
* **Gejala**: Muncul status: `Plan: 2 to add, 2 to destroy` saat mengganti nama key pada map.
* **Solusi**: Gunakan `moved` block untuk memetakan key lama ke key baru:
  ```hcl
  moved {
    from = aws_subnet.this["legacy-subnet-a"]
    to   = aws_subnet.this["tier-web-1a"]
  }
  ```

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebagai *quality gate* sebelum merilis modul enterprise ke private registry:

* [ ] **Root Decoupling**: Child module bebas 100% dari deklarasi blok `provider {}`. Provider hanya didefinisikan lewat `configuration_aliases`.
* [ ] **Pinning Strict Engine & Provider**: Tentukan range kompatibilitas versi modul:
  ```hcl
  terraform {
    required_version = ">= 1.6.0, < 2.0.0"
    required_providers {
      aws = {
        source  = "hashicorp/aws"
        version = ">= 5.0, < 6.0"
      }
    }
  }
  ```
* [ ] **Type Safety & Descriptions**: Semua variable wajib mendefinisikan `type`, `description`, dan `nullable = false` (jika non-opsional).
* [ ] **Contract Validations**: Minimal terdapat 1 custom validation rule pada setiap parameter network, security, atau naming convention.
* [ ] **Self-Containment Output**: Mengembalikan output berupa IDs, ARNs, dan attributes fungsional yang memungkinkan chaining ke modul lain tanpa modul pemanggil membaca data source tambahan.
* [ ] **Lifecycle Pre/Postconditions**: Implementasikan `postcondition` untuk memastikan *eventual consistency* cloud resource (misal: validasi status VPC Peering / EKS Cluster OIDC Issuer).
* [ ] **Zero Hardcoded Secrets**: Tidak ada plain-text string untuk credential, token, atau IP eksternal sensitif.
* [ ] **Immutable Release Tagging**: Rilis modul menggunakan Git Tag SemVer (contoh: `v1.2.0`). Hindari mereferensikan branch seperti `main` atau `master` dari root environment.

---

### 12. Hands-on Practice

Dalam praktikum ini, Anda akan membangun sebuah composite module enterprise lengkap dengan arsitektur folder modular dan native HCL integration test.

#### Struktur Direktori Lab
```
hands-on/m02/
├── modules/
│   └── secure_storage/
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       └── versions.tf
├── tests/
│   └── secure_storage.tftest.hcl
└── main.tf
```

#### Langkah 1: Buat Direktori Kerja
```bash
mkdir -p hands-on/m02/modules/secure_storage hands-on/m02/tests
cd hands-on/m02
```

#### Langkah 2: Definisikan versions.tf Modul Anak
Tuliskan ke `modules/secure_storage/versions.tf`:
```hcl
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
      configuration_aliases = [aws.storage_provider]
    }
  }
}
```

#### Langkah 3: Definisikan variables.tf Modul Anak
Tuliskan ke `modules/secure_storage/variables.tf`:
```hcl
variable "namespace" {
  type        = string
  description = "Application context identifier (3-8 alfanumerik huruf kecil)."
  validation {
    condition     = can(regex("^[a-z0-9]{3,8}$", var.namespace))
    error_message = "namespace wajib berupa 3-8 karakter alfanumerik kecil."
  }
}

variable "environment" {
  type        = string
  description = "Target deployment environment."
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment harus salah satu dari: dev, staging, prod."
  }
}

variable "enable_versioning" {
  type        = bool
  default     = true
  description = "Status bucket versioning."
}
```

#### Langkah 4: Definisikan main.tf & outputs.tf Modul Anak
Tuliskan ke `modules/secure_storage/main.tf`:
```hcl
resource "aws_s3_bucket" "this" {
  provider      = aws.storage_provider
  bucket        = "corp-${var.environment}-${var.namespace}-data"
  force_destroy = var.environment != "prod"

  lifecycle {
    postcondition {
      condition     = self.arn != ""
      error_message = "ARN S3 Bucket kosong, provisi gagal."
    }
  }
}

resource "aws_s3_bucket_versioning" "this" {
  provider = aws.storage_provider
  bucket   = aws_s3_bucket.this.id
  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Suspended"
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  provider                = aws.storage_provider
  bucket                  = aws_s3_bucket.this.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

Tuliskan ke `modules/secure_storage/outputs.tf`:
```hcl
output "bucket_name" {
  value       = aws_s3_bucket.this.bucket
  description = "Nama tergenerasi S3 bucket."
}

output "bucket_arn" {
  value       = aws_s3_bucket.this.arn
  description = "ARN dari S3 bucket."
}
```

#### Langkah 5: Buat Automated Unit Test Menggunakan Terraform Test Framework
Tuliskan ke `tests/secure_storage.tftest.hcl`:
```hcl
# Inisialisasi Mock Provider
mock_provider "aws" {
  alias = "storage_provider"
}

# Test Run 1: Validasi Skenario Normal (Positive Test)
run "verify_bucket_naming_logic" {
  command = plan

  providers = {
    aws.storage_provider = aws.storage_provider
  }

  variables {
    namespace         = "payment"
    environment       = "prod"
    enable_versioning = true
  }

  assert {
    condition     = module.secure_storage.bucket_name == "corp-prod-payment-data"
    error_message = "Format penamaan bucket tidak sesuai standar korporat."
  }
}

# Test Run 2: Validasi Penolakan Environment Tidak Sah (Negative Test)
run "expect_failure_on_invalid_env" {
  command = plan

  providers = {
    aws.storage_provider = aws.storage_provider
  }

  variables {
    namespace   = "payment"
    environment = "sandbox" # Tidak ada di allowlist (dev, staging, prod)
  }

  expect_failures = [
    var.environment
  ]
}
```

#### Langkah 6: Hubungkan ke Root main.tf dan Eksekusi Test
Tuliskan ke `hands-on/m02/main.tf`:
```hcl
provider "aws" {
  region = "ap-southeast-1"
}

module "secure_storage" {
  source = "./modules/secure_storage"

  providers = {
    aws.storage_provider = aws
  }

  namespace   = "payment"
  environment = "dev"
}
```

Jalankan pengujian kontrak secara terisolasi tanpa menyentuh real API:
```bash
terraform init
terraform test
```

Eksekusi yang berhasil akan menampilkan output:
```text
tests/secure_storage.tftest.hcl... in progress
  run "verify_bucket_naming_logic"... pass
  run "expect_failure_on_invalid_env"... pass
tests/secure_storage.tftest.hcl... tearing down
All 2 tests passed.
```

---

### 13. Exercise

#### Level: Easy
Buat module atomic `modules/security_group` yang menerima input list of objects:
```hcl
ingress_rules = list(object({
  port        = number
  protocol    = string
  cidr_blocks = list(string)
  description = string
}))
```
*Tugas*: Implementasikan `dynamic "ingress"` block di dalam resource `aws_security_group` dan tambahkan validasi agar port yang diinput berada di rentang 1 - 65535.

#### Level: Medium
Kembangkan module composite untuk AWS KMS Key.
*Tugas*:
1. Menerima flag boolean `enable_key_rotation`.
2. Gunakan `lifecycle { postcondition { ... } }` untuk mengevaluasi bahwa jika key dibuat di environment `prod`, atribut `enable_key_rotation` wajib bernilai `true`. Jika false, gagalkan fasa `apply`.

#### Level: Hard
Buat modul abstraksi database multi-tier (Primary-Replica) yang menerima `replica_count`.
*Tugas*:
1. Modul harus mengimplementasikan Provider Inversion untuk dua region berbeda (Region Primary dan Region Failover).
2. Jika `replica_count > 0`, instansiasikan instance read-replica di provider failover menggunakan `count` atau `for_each` dinamis.
3. Rancang output yang menghasilkan `connection_string_read_write` dan daftar `connection_strings_read_only` tanpa mengekspos master password (gunakan sensitive attribute flag).

---

### 14. Challenge

**Skenario**: Enterprise Mesh Transit Gateway Architecture.
Sebuah konglomerasi menuntut Anda membuat **Global WAN Gateway Module** yang mengabstraksi perutean lintas 3 Region AWS (contoh: Tokyo, Frankfurt, N. Virginia).
1. Modul ini adalah Composite Module tunggal yang harus mengonsumsi 3 provider alias berbeda: `aws.region_asia`, `aws.region_europe`, `aws.region_us`.
2. Modul harus menerima *topology matrix map* yang mendefinisikan *peering requirement* antar region secara dinamis (tidak boleh hardcoded 3 peering).
3. Anda **wajib** mendesain integrasi peering tersebut sedemikian rupa sehingga jika salah satu region dihapus dari map topologi, Terraform tidak melakukan state destruction terhadap region yang tidak berubah.
4. Terapkan custom assertions pada `.tftest.hcl` yang menguji bahwa CIDR block routing table antar peering Transit Gateway tidak mengalami *overlapping*.

*Catatan Tantangan*: Tidak disediakan *boilerplate* kode instan untuk challenge ini. Rancang hierarki file, skema DAG provider, dan dynamic peering matrix secara mandiri menggunakan prinsip-prinsip yang telah dipelajari di Modul ini.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa deklarasi blok `provider "aws" {}` di dalam child module dilarang keras dalam standar arsitektur Terraform enterprise?
   * A. Karena child module tidak memiliki hak akses memanggil API AWS secara teknis.
   * B. Mengakibatkan child module gagal mewarisi token authentication runtime.
   * C. Merusak DAG dependency tree, menyebabkan masalah pada penghapusan resource, dan mencegah modul dikonfigurasi ulang secara dinamis oleh parent.
   * D. Mengakibatkan Terraform State terkunci secara permanen saat `terraform init`.

2. Fungsi utama dari argumen `configuration_aliases` pada blok `required_providers` di dalam child module adalah...
   * A. Memberikan nama alias pada variabel lokal modul.
   * B. Mendeklarasikan interface provider eksplisit yang wajib diinjeksi oleh caller (root) module.
   * C. Mengubah tipe credential cloud dari IAM User menjadi Federated Web Identity.
   * D. Mempercepat kompilasi graf dependensi modul saat eksekusi `terraform validate`.

3. Kapan custom validation rule pada suatu variable (`validation { condition = ... }`) dievaluasi oleh Terraform engine?
   * A. Pada saat `terraform apply` setelah resource berhasil diprovisi.
   * B. Pada saat pembentukan status graph awal di fasa parsing (early planning), sebelum kalkulasi status resource aktual.
   * C. Hanya saat menjalankan unit test melalui `terraform test`.
   * D. Saat state lock berhasil diakuisisi di Terraform Enterprise backend.

4. Apa perbedaan utama antara penggunaan `count` dan `for_each` dalam perancangan child module?
   * A. `count` hanya bekerja untuk tipe data string, sedangkan `for_each` hanya untuk angka.
   * B. `count` mengidentifikasi resource berdasarkan indeks numerik terurut (rawan state destruction saat array bergeser), sedangkan `for_each` mengidentifikasi resource berdasarkan key unik map/set.
   * C. `for_each` dieksekusi paralel, sedangkan `count` dieksekusi secara sekuensial.
   * D. `count` tidak dapat membaca variabel lokal, sedangkan `for_each` wajib membaca variabel lokal.

5. Apa fungsi dari blok deklaratif `moved {}` yang dirilis pada Terraform engine modern?
   * A. Memindahkan file `.tf` dari satu folder direktori ke direktori lain secara otomatis di OS.
   * B. Melakukan migrasi resource antar cloud provider (misal: AWS VPC ke Azure VNet).
   * C. Memetakan ulang alamat identifier resource di dalam state file tanpa melakukan destruksi dan provisi ulang infrastruktur fisik.
   * D. Menghapus resource dari state file secara diam-diam.

##### Kunci Jawaban Basic
1. **C** — Child module yang menginisialisasi provider memutus DAG engine, mengacaukan kalkulasi reverse teardown, dan membatasi reusability modul.
2. **B** — `configuration_aliases` menetapkan placeholder alias provider yang harus disuplai oleh parent context via blok `providers = { ... }`.
3. **B** — Variable validation dievaluasi di awal, sehingga kesalahan format/tipe langsung ditolak sebelum Terraform memanggil API remote cloud.
4. **B** — Perubahan urutan data pada `count` memicu *unwanted destruction/recreation*; `for_each` mengikat resource secara deterministik pada string key.
5. **C** — `moved` block adalah state-refactoring deklaratif yang memindahkan pointer resource address di state file tanpa sentuhan manual CLI.

---

#### B. Pertanyaan Intermediate
1. Perhatikan potongan kode berikut:
   ```hcl
   resource "aws_eip" "nat" {
     count = var.enable_nat ? 1 : 0
   }
   output "nat_ip" {
     value = aws_eip.nat[0].public_ip
   }
   ```
   Apa yang terjadi jika variabel `enable_nat = false` saat dieksekusi?
   * A. Output bernilai string kosong `""`.
   * B. Terraform berhenti dengan error runtime: `Index [0] out of bounds for count of 0`.
   * C. Terraform mengonversi output menjadi tipe data boolean `false`.
   * D. Terraform melewati evaluasi blok output secara otomatis.

2. Bagaimana cara paling tepat merefactor output pada soal nomor 1 agar tidak memicu error saat `enable_nat = false`?
   * A. Menggunakan `value = aws_eip.nat.*.public_ip` (menghasilkan list, kosong jika disable).
   * B. Menggunakan operator `try(aws_eip.nat[0].public_ip, null)` atau `one(aws_eip.nat[*].public_ip)`.
   * C. Menambahkan lifecycle `ignore_changes` pada resource EIP.
   * D. Jawaban A dan B benar secara arsitektural.

3. Kapan sebuah evaluasi `postcondition` pada resource block dijalankan oleh Terraform?
   * A. Tepat sebelum resource API request dikirim ke endpoint cloud.
   * B. Setelah konfigurasi resource diterapkan, mengevaluasi state atribut aktual yang dikembalikan oleh API penyedia cloud.
   * C. Bersamaan dengan validasi variable input di root module.
   * D. Hanya saat Terraform mengalami panic error untuk memicu rollback.

4. Anda ingin mengeksekusi integration test terhadap atomic module tanpa mengeluarkan biaya provisioning real cloud infrastructure dan tanpa kredensial aktif. Pendekatan native apa yang harus digunakan pada `.tftest.hcl`?
   * A. Menggunakan parameter `mock_provider` di dalam skenario test.
   * B. Menghubungkan test ke LocalStack emulator via docker bridge secara manual.
   * C. Menambahkan `dry_run = true` pada blok `run`.
   * D. Menjalankan test dengan flag CLI `terraform test -skip-apply`.

5. Di dalam modul berskala besar, atribut apa yang wajib ditambahkan pada deklarasi sensitive output (seperti output connection string yang memuat credential) agar tidak terekspos secara polos di CLI logs?
   * A. `protected = true`
   * B. `encrypted = true`
   * C. `sensitive = true`
   * D. `mask_output = true`

##### Kunci Jawaban Intermediate
1. **B** — Jika `count = 0`, array `aws_eip.nat` kosong. Mengakses indeks numerik `[0]` secara hardcoded memicu error out of bounds.
2. **D** — Menggunakan splat operator `[*]` mengembalikan list kosong tanpa error, dan fungsi `one()` mengonversi elemen tunggal dari splat menjadi scalar/null dengan aman.
3. **B** — `postcondition` dievaluasi sesaat setelah resource dibuat/diubah untuk mengonfirmasi atribut respon backend cloud memenuhi kriteria integritas.
4. **A** — Fitur `mock_provider` pada native Terraform Test framework (Terraform 1.7+) memungkinkan simulasi respon data provider tanpa provisi fisik nyata.
5. **C** — Penanda `sensitive = true` menginstruksikan Terraform Core untuk menyamarkan nilai variabel/output sebagai `(sensitive value)` pada console output dan logs.

---

#### C. Skenario Kasus Produksi

##### Kasus 1
**Konteks**: Tim Anda memiliki reusable module `modules/database_cluster`. Salah satu dev merancang modul dengan hardcoded provider AWS Region:
```hcl
# modules/database_cluster/main.tf
provider "aws" {
  region = "ap-southeast-1"
}
resource "aws_rds_cluster" "primary" { ... }
```
Saat modul ini dipanggil berkali-kali oleh root module untuk deployment multi-region (Singapura dan Tokyo), tim ops mendapati error fatal: `Providers cannot be declared inside child modules`. Modul juga gagal dieksekusi saat root ingin mendelegasikan provisi ke Tokyo (`ap-northeast-1`).
* **Pertanyaan**: Jelaskan transformasi kode yang wajib dilakukan pada child module dan root module agar modul tersebut sepenuhnya agnostik terhadap region dan kompatibel dengan arsitektur multi-region root!
* **Solusi Arsitektural**:
  1. Hapus seluruh blok `provider "aws" { ... }` dari direktori `modules/database_cluster/`.
  2. Buka `modules/database_cluster/versions.tf`, tambahkan interface deklarasi alias:
     ```hcl
     terraform {
       required_providers {
         aws = {
           source                = "hashicorp/aws"
           configuration_aliases = [aws.db_target]
         }
       }
     }
     ```
  3. Perbarui seluruh resource database di modul agar merujuk ke provider alias:
     ```hcl
     resource "aws_rds_cluster" "primary" {
       provider = aws.db_target
       # ...
     }
     ```
  4. Di root module, inisialisasi provider konkret untuk Tokyo dan hubungkan ke alias child module:
     ```hcl
     provider "aws" {
       alias  = "tokyo_engine"
       region = "ap-northeast-1"
     }

     module "database_tokyo" {
       source    = "./modules/database_cluster"
       providers = {
         aws.db_target = aws.tokyo_engine
       }
     }
     ```

##### Kasus 2
**Konteks**: Arsitek enterprise Anda menolak PR (Pull Request) pada Composite Networking Module karena input variabel `vpc_subnets` didesain sebagai berikut:
```hcl
variable "vpc_subnets" {
  type = list(string) # Berisi daftar CIDR blocks: ["10.0.1.0/24", "10.0.2.0/24"]
}
```
Penolakan didasarkan pada risiko pemadaman jaringan (*network outage*) jika engineer di kemudian hari menghapus subnet pertama di list.
* **Pertanyaan**: Mengapa desain list tersebut berbahaya bagi infrastruktur produksi, dan bagaimana skema rancangan variabel yang harus diubah untuk mencapai kekebalan state (*state drift immutability*)?
* **Solusi Arsitektural**:
  * *Bahaya*: Jika child module mengeksekusi provisi subnet menggunakan `count = length(var.vpc_subnets)`, alamat resource di state file terikat ke indeks numerik: `aws_subnet.this[0]`, `aws_subnet.this[1]`. Jika subnet indeks 0 dihapus, subnet indeks 1 akan bergeser statusnya menjadi indeks 0. Terraform akan **menghancurkan (destroy)** subnet yang tersisa dan membuatnya kembali dari nol, memutus traffic database/workload aktif.
  * *Rancangan Perbaikan*: Ubah schema menjadi `map(object)` di mana setiap subnet memiliki *unique immutable key*:
    ```hcl
    variable "vpc_subnets" {
      type = map(object({
        cidr_block = string
        az         = string
        is_public  = bool
      }))
    }
    ```
    Dan di dalam modul, resource diikat menggunakan `for_each`:
    ```hcl
    resource "aws_subnet" "this" {
      for_each          = var.vpc_subnets
      cidr_block        = each.value.cidr_block
      availability_zone = each.value.az
      # Subnet terikat pada nama key map (contoh: "app-tier-1a"), kebal terhadap pergeseran array
    }
    ```

##### Kasus 3
**Konteks**: Perusahaan baru saja merilis aturan audit ketat: Seluruh modul S3 bucket tidak boleh memperbolehkan unencrypted bucket object dan wajib memblokir akses publik. Namun, tim keamanan menemukan ada tim produk yang menonaktifkan fitur enkripsi modul via override input (`enable_encryption = false`).
* **Pertanyaan**: Bagaimana cara memaksakan aturan keamanan ini di level kode modul itu sendiri, sehingga pipeline CI/CD Terraform akan otomatis menggagalkan execution plan jika parameter tersebut diutak-atik, tanpa bergantung pada scanning tools eksternal?
* **Solusi Arsitektural**:
  Terapkan kombinasi **Custom Variable Validation** dan **Resource Lifecycle Precondition**:
  1. Hapus variabel yang mengizinkan override bypass (seperti boolean `enable_encryption`), atau jika variabel tersebut wajib ada, pasang validasi ketat:
     ```hcl
     variable "enable_encryption" {
       type        = bool
       default     = true
       description = "Wajib selalu bernilai true pada arsitektur Enterprise."

       validation {
         condition     = var.enable_encryption == true
         error_message = "Audit Compliance Error: Menonaktifkan enkripsi bucket melanggar kebijakan keamanan korporat."
       }
     }
     ```
  2. Tambahkan `precondition` pada resource enkripsi untuk memastikan tidak ada konfigurasi lokal yang membypass modul:
     ```hcl
     resource "aws_s3_bucket_server_side_encryption_configuration" "enforce" {
       bucket = aws_s3_bucket.this.id

       rule {
         apply_server_side_encryption_by_default {
           sse_algorithm = "AES256"
         }
       }

       lifecycle {
         precondition {
           condition     = var.enable_encryption
           error_message = "Enkripsi bucket gagal diterapkan pada fasa pre-flight plan."
         }
       }
     }
     ```

---

### 16. Summary

Implementasi arsitektur modul enterprise menuntut kedisiplinan desain yang jauh melampaui scripting deklaratif biasa:

1. **Inversion of Control**: Modul anak berkinerja tinggi tidak pernah menentukan koneksi infrastruktur mereka sendiri. Dengan memanfaatkan `configuration_aliases`, modul mendelegasikan dependensi provider sepenuhnya ke root context.
2. **Defensive API Boundary**: Memanfaatkan HCL2 strict object types, custom validation rules, serta assertions `precondition`/`postcondition` menciptakan gerbang pengaman yang mendeteksi kesalahan konfigurasi sebelum interaksi fisik dengan Cloud API terjadi.
3. **State Preservation**: Menghindari pengindeksan array `count` untuk alokasi resource dinamis, dan memilih `for_each` dengan kunci unik deterministik. Menggunakan HCL `moved` blocks saat modul mengalami refaktorisasi internal guna menjamin zero-downtime migration.
4. **Automated Verification**: Perancangan modul enterprise modern mewajibkan validasi arsitektur terisolasi menggunakan native `terraform test` framework untuk memastikan kontrak I/O selalu terpenuhi secara terukur.