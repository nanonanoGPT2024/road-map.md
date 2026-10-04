# Bab 01 Module 01: Fondasi Infrastructure as Code & Arsitektur Terraform Engine

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis (C4)** perbedaan mendasar antara paradigma *Declarative* (Terraform) dan *Imperative* (CLI/SDK/Ansible) dalam konteks determinisme dan konvergensi state infrastruktur.
- **Mendekonstruksi (C4)** arsitektur internal Terraform Core, termasuk siklus evaluasi konfigurasi, komputasi *Directed Acyclic Graph* (DAG), dan abstraksi Provider berbasis RPC.
- **Mengimplementasikan (C3)** pipeline eksekusi infrastruktur dasar menggunakan Terraform (`init`, `plan`, `apply`) dengan isolasi state lokal maupun remote secara deterministik.
- **Mengevaluasi (C5)** risiko *state drift*, konkurensi eksekusi, serta implikasi performa dari ukuran dependency graph pada infrastruktur cloud berskala enterprise.

---

### 2. Concept Explanation
Terraform adalah platform *Infrastructure as Code* (IaC) yang bersifat deklaratif, agnostik terhadap cloud provider, dan digerakkan oleh *state machine*. 

Secara konseptual, Terraform membagi dunia infrastruktur menjadi dua bagian:
1. **Desired State (Target):** Didefinisikan oleh engineer melalui HashiCorp Configuration Language (HCL).
2. **Current State (Aktual):** Kondisi fisik/logis dari resource yang berjalan di cloud provider/infrastruktur target.

Di antara kedua dunia tersebut terdapat **Terraform State** (`terraform.tfstate`), sebuah berkas pemetaan skema yang bertindak sebagai *source of truth* metadata internal. Terraform bekerja bukan sebagai mesin eksekusi langkah-demi-langkah (skrip), melainkan sebuah *reconciliation engine*. 

```
[ Desired State (HCL) ] <---+
                             |---> [ Reconciliation Engine (Diff & Graph) ] ---> [ Actions: Create/Update/Delete ]
[ Current State (Cloud) ] <-+
```

Ketika konfigurasi dieksekusi, Terraform membaca konfigurasi HCL, menyegarkan (*refresh*) status resource dari API provider, membandingkannya dengan state file, menghitung *diff* kalkulatif, dan menghasilkan execution plan yang menggaransi sistem mencapai desired state dengan jumlah langkah minimal tanpa efek samping destruktif yang tidak disengaja.

---

### 3. Why It Matters
Dalam rekayasa sistem modern, pengelolaan infrastruktur via GUI console ("ClickOps") atau shell script kustom memperkenalkan kelemahan fatal:
- **Konfigurasi Non-Deterministik:** Human error saat deployment manual menyebabkan perbedaan konfigurasi antar environment (Dev, Staging, Prod).
- **Zero Traceability:** Ketiadaan jejak audit git yang memvalidasi siapa, kapan, dan mengapa suatu subnet, firewall, atau cluster dimodifikasi.
- **MTTR (Mean Time To Recovery) Tinggi:** Kegagalan fatal pada data center/region membutuhkan rekonfigurasi manual yang memakan waktu berjam-jam hingga berhari-hari.
- **Scalability Ceiling:** Manajemen ribuan resource cloud melintasi berbagai region mustahil diorkestrasi secara konsisten tanpa otomatisasi berbasis kode.

Terraform menyelesaikan tantangan ini dengan mengkodifikasi infrastruktur, memungkinkan penerapan praktik *Software Engineering* (Git version control, code review, automated testing, CI/CD) langsung pada lapisan perangkat keras virtual dan cloud services.

---

### 4. What Problem It Solves
Pendekatan lama (legacy provisioning) mengandalkan:
1. **Skrip Imperatif (Bash, AWS CLI, Python SDK):** Mengharuskan developer menuliskan *bagaimana* mencapai suatu kondisi (misal: "periksa apakah VPC ada; jika tidak, buat; lalu tunggu; lalu buat subnet"). Jika skrip gagal di tengah jalan, status sistem menjadi *inconsistent* dan tidak memiliki mekanisme rollback atau resume native.
2. **Configuration Management Tooling (Ansible, Chef) untuk Provisioning:** Walaupun Ansible idempoten untuk konfigurasi OS/software, ia tidak memiliki tracking lifecycle state yang granular untuk melacak dependensi resource cloud yang saling bertaut secara hierarkis (orphaned resources sering tertinggal).

| Fitur / Karakteristik | Imperative Approach (Bash/CLI/Python) | Declarative IaC (Terraform) |
| :--- | :--- | :--- |
| **Model State** | Stateless / Manual Check | Stateful (`.tfstate` engine-tracked) |
| **Paradigma** | *How to execute* (Urutan langkah) | *What should exist* (Status akhir) |
| **Idempotency** | Rentan gagal / Butuh logic rumit manual | Native (Built-in via core engine) |
| **Dependency Resolution**| Manual sequencing oleh engineer | Otomatis via Directed Acyclic Graph (DAG) |
| **Drift Detection** | Sangat sulit (harus custom code) | Otomatis melalui `terraform plan` |

---

### 5. How It Works: Architectural Internals
Arsitektur Terraform secara internal terbelah menjadi dua komponen decoupled yang berkomunikasi melalui **gRPC**:

```
+-----------------------------------------------------------------------+
|                           TERRAFORM CORE                              |
|  - HCL Configuration Parsing & Interpolation                          |
|  - Directed Acyclic Graph (DAG) Engine                                |
|  - State Management & Diff Computation                                |
+-----------------------------------------------------------------------+
                                  |
                           (gRPC over IPC)
                                  v
+-----------------------------------------------------------------------+
|                         TERRAFORM PROVIDERS                           |
|  - Provider Schema Definition                                         |
|  - Resource Lifecycle Implementations (CRUD)                          |
|  - Upstream Cloud API Clients (AWS, GCP, Azure, K8s, Vault)           |
+-----------------------------------------------------------------------+
```

#### A. Terraform Core
Ditulis dalam bahasa Go, core bertanggung jawab atas:
- **Parser HCL:** Mengurai file `.tf` menjadi Abstract Syntax Tree (AST).
- **Graph Builder:** Mengonstruksi dependensi antar resource menjadi **Directed Acyclic Graph (DAG)**. Simpul (node) merepresentasikan resource, dan edge merepresentasikan ketergantungan (misal: Subnet membutuhkan referensi VPC ID). Core mendeteksi *cycle error* (dependensi melingkar) sebelum panggilan API apa pun dilakukan.
- **Differencing Engine:** Membandingkan state lama (`tfstate`), konfigurasi HCL baru, dan data runtime aktual untuk memetakan operasi: `No-op`, `Create`, `Update-in-Place`, atau `Destroy-and-Recreate`.

#### B. Terraform Providers
Provider adalah binary eksternal yang diunduh secara independen saat `terraform init`. Core bertindak sebagai supervisor yang mengeksekusi plugin provider sebagai child process. 
- Provider mengimplementasikan CRUD interface via gRPC:
  - `CreateResource(req, resp)`
  - `ReadResource(req, resp)`
  - `UpdateResource(req, resp)`
  - `DeleteResource(req, resp)`
- Core tidak mengetahui detail API cloud; ia hanya mengirimkan perintah abstrak seperti *"Terapkan konfigurasi subnet ini ke provider AWS"*. Plugin provider menerjemahkannya menjadi HTTP REST API calls ke AWS SDK.

#### C. Siklus Hidup Eksekusi (Lifecycle Execution)
1. **`terraform init`**: Menginisialisasi direktori kerja. Menentukan, mengunduh, dan memvalidasi plugin provider ke `.terraform/providers/`. Mengonfigurasi backend state.
2. **`terraform plan`**: 
   - Core menginstruksikan Provider mengeksekusi `ReadResource` terhadap semua item di state file (*Refresh Phase*).
   - Core membangun DAG.
   - Core membandingkan data runtime vs HCL, lalu membuat spek perubahan (Plan) ke memori atau file disk.
3. **`terraform apply`**:
   - Memvalidasi Plan.
   - Core menelusuri DAG secara konkurensi (default hingga 10 worker paralel via `-parallelism=10`).
   - Core memanggil RPC `Create`/`Update`/`Delete` pada Provider sesuai urutan topologis graph.
   - Menulis perubahan hasil mutasi API ke *State File* secara atomik.

---

### 6. Architecture Diagram

Berikut visualisasi aliran data, komponen internal, interaksi plugin via gRPC, dan mutasi State:

```
[ User Workstation / CI/CD Runner ]
   |
   | (1) Executes: terraform apply
   v
+-------------------------------------------------------------+
| Terraform Core Engine                                       |
|                                                             |
|  +----------------+     Builds      +--------------------+  |
|  | Config (*.tf)  | --------------> | Graph Engine (DAG) |  |
|  +----------------+                 +--------------------+  |
|          |                                    |             |
|          v Computes Diff                      v Walk Nodes  |
|  +----------------+ Reads/Writes    +--------------------+  |
|  | State Engine   | <-------------> | Execution Engine   |  |
|  +----------------+                 +--------------------+  |
+---------^-------------------------------------|-------------+
          |                                     |
(Persist) | (State Backend)                     | (gRPC Calls)
          v                                     v
+-------------------+                 +--------------------+
| S3 + DynamoDB     |                 | Provider Plugin    |
| (State & Locks)   |                 | (e.g. AWS Core)    |
+-------------------+                 +--------------------+
                                                |
                                                | (HTTPS REST / JSON)
                                                v
                                      +--------------------+
                                      | Cloud Infrastructure|
                                      | (VPC, EC2, RDS)    |
                                      +--------------------+
```

---

### 7. Simple Code Example
Berikut contoh dasar struktur deklarasi Terraform lokal yang memvalidasi konsep resource, provider, dan variabel:

```hcl
# File: main.tf

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4.0"
    }
  }
}

provider "local" {}

variable "environment" {
  type        = string
  default     = "development"
  description = "Target environment identifier"
}

resource "local_file" "config_output" {
  filename        = "${path.module}/build/runtime_config.json"
  content         = jsonencode({
    env       = var.environment
    timestamp = timestamp()
    managed_by = "terraform-engine"
  })
  file_permission = "0640"
}

output "generated_file_path" {
  description = "Absolute path of the provisioned configuration file"
  value       = local_file.config_output.filename
}
```

---

### 8. Practical Real-World Example
Berikut arsitektur foundational cloud networking di AWS yang mendemonstrasikan resolusi graph implisit, dynamic subnetting dengan fungsi bawaan (`cidrsubnet`), dan tagging standar industri.

```hcl
# File: versions.tf
terraform {
  required_version = ">= 1.5.0, < 2.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# File: variables.tf
variable "aws_region" {
  type        = string
  default     = "ap-southeast-1"
  description = "Region AWS untuk deployment"
}

variable "base_vpc_cidr" {
  type        = string
  default     = "10.100.0.0/16"
  description = "CIDR block utama VPC"
  validation {
    condition     = can(cidrhost(var.base_vpc_cidr, 0))
    error_message = "Nilai base_vpc_cidr harus valid IPv4 CIDR block."
  }
}

variable "environment" {
  type        = string
  default     = "production"
  description = "Nama deployment environment"
}

# File: network.tf
provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Environment = var.environment
      ManagedBy   = "Terraform"
      Project     = "CoreInfrastructure"
    }
  }
}

# Core VPC Resource
resource "aws_vpc" "primary" {
  cidr_block           = var.base_vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.environment}-primary-vpc"
  }
}

# Data source untuk mengambil AZ yang aktif secara dinamis
data "aws_availability_zones" "available" {
  state = "available"
}

# Public Subnets yang terikat dependensi implisit ke aws_vpc.primary.id
resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.primary.id
  cidr_block              = cidrsubnet(var.base_vpc_cidr, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.environment}-public-subnet-${count.index + 1}"
    Tier = "Public"
  }
}

# File: outputs.tf
output "vpc_id" {
  description = "ID dari primary VPC yang dibuat"
  value       = aws_vpc.primary.id
}

output "public_subnet_ids" {
  description = "List ID subnet publik yang dihasilkan"
  value       = aws_subnet.public[*].id
}
```

---

### 9. Trade-offs & Alternatives

| Kriteria | Terraform (HCL) | OpenTofu | Pulumi | AWS CloudFormation | Ansible |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Lisensi** | BSL 1.1 (Non-OSI) | MPL 2.0 (Open Source) | Apache 2.0 | Proprietary (AWS) | GPL 3.0 |
| **Bahasa Pemrograman** | Domain-Specific (HCL) | Domain-Specific (HCL) | General (Go, TS, Python)| JSON/YAML | YAML |
| **State Handling** | External/Remote State | External/Remote State | Cloud-managed / Remote | Otomatis diatur AWS | Stateless / In-memory |
| **Multi-Cloud** | Luas & Sangat Matang | Kompatibel Terraform | Luas & Sangat Matang | Eksklusif AWS | Mengandalkan modules |
| **Kompleksitas Abstraksi**| Terbatas (declarative limits) | Terbatas (declarative) | Tinggi (Full OOP control) | Terbatas | Menengah |

- **Terraform vs Pulumi:** Pulumi memungkinkan testing native, loop, dan abstraksi class berkat bahasa seperti TypeScript/Go, namun membutuhkan disiplin software engineering ketat untuk menghindari kompleksitas kode yang berlebihan. Terraform dengan HCL membatasi kompleksitas komputasi, menjadikannya lebih mudah diaudit oleh tim DevOps/Infra.
- **Terraform vs Ansible:** Ansible optimal untuk manajemen konfigurasi *in-instance* (install package, setting config file). Menggunakan Ansible untuk memelihara siklus hidup cloud networking memicu risiko *state desynchronization* yang masif.

---

### 10. Best Practices & Anti-patterns

#### Recommended (DO)
- **Gunakan Remote Backend dengan Distributed Locking:** Simpan state di AWS S3 + DynamoDB locking, Google GCS, atau Terraform Cloud.
- **Pin Versi Provider & Core:** Kunci versi menggunakan semantic versioning constraint (`~> x.y`) untuk mencegah *breaking changes* tak terduga saat `terraform init`.
- **Gunakan Descriptive Variable & Input Validation:** Implementasikan blok `validation` pada setiap variabel untuk menangkap kesalahan ketik sebelum `terraform plan` dikirim ke cloud API.
- **Jalankan `terraform fmt` dan `terraform validate` di CI:** Pastikan standarisasi sintaksis dan deteksi error internal secara otomatis sebelum fase review kode.

#### Anti-patterns (DON'T)
- **Monolithic State:** Menyimpan seluruh infrastruktur perusahaan (networking, databases, kubernetes cluster, application services) ke dalam SATU file state tunggal. Hal ini memperlambat running time graph dan meningkatkan radius dampak kerusakan (*blast radius*).
- **Hardcoding Resources Attribute:** Menulis string statis seperti `vpc-0123456789abcdef` secara eksplisit, alih-alih merujuk dependensi via output resource/data source.
- **Manual Modifikasi State File:** Mengedit berkas `.tfstate` secara manual menggunakan teks editor. Hal ini merusak *checksum* integrasi state dan memicu korupsi data. Gunakan CLI `terraform state <subcommand>` secara eksklusif.

---

### 11. Security Considerations
1. **Plaintext Secrets dalam State File:**
   - Terraform State menyimpan SELURUH atribut resource dalam format JSON **unencrypted** di disk penyimpanan state (termasuk nilai `sensitive = true`, database credentials, dan private keys).
   - *Mitigasi:* Wajib mengenkripsi backend penyimpanan (*SSE-KMS* di S3) dan batasi hak akses backend via IAM policy berbasis prinsip *Least Privilege*. Hindari menghasilkan raw password di Terraform jika secret manager cloud (Vault, AWS Secrets Manager) dapat menangani siklus hidupnya.
2. **Pemberian Hak Akses Eksekusi (IAM Privileges):**
   - CI/CD runner dilarang menggunakan access key dengan privilege `AdministratorAccess` tanpa batas.
   - *Mitigasi:* Gunakan mekanisme OpenID Connect (OIDC) federation antara CI platform (GitHub Actions, GitLab CI) dan cloud provider untuk menukar short-lived token dengan role berbasis IAM boundaries.
3. **Konkurensi Tanpa State Locking:**
   - Dua eksekusi `terraform apply` yang berjalan bersamaan tanpa locking akan menimpa berkas state secara balapan (*race condition*), berpotensi menduplikasi resource atau merusak tracking state.

---

### 12. Performance & Scalability Considerations
- **Eksplosi Latensi Graph (Graph Explosion):**
  - Ketika sebuah state memuat lebih dari 500-1000 resource, fase `Refresh` pada `terraform plan` akan lambat karena harus mengirim ratusan HTTPS call serial/paralel ke API cloud provider.
  - *Solusi:* Potong arsitektur infrastruktur menjadi beberapa *layer state terisolasi* (misal: `01-network`, `02-database`, `03-compute`) menggunakan arsitektur modular yang dihubungkan melalui `terraform_remote_state` atau SSM/Parameter Store.
- **API Rate Limiting & Throttling:**
  - Deployment paralel yang masif (`-parallelism=n`) dapat memicu throttling dari cloud control plane (misal: AWS CloudTrail mengembalikan error `RateExceeded`).
  - *Tuning:* Set batas default konkurensi DAG engine ke angka konservatif (misal `-parallelism=5`) jika berjalan pada akun cloud enterprise dengan kuota API terbatas.

---

### 13. Edge Cases, Gotchas & Limitations
1. **Dynamic Dependent Count/ForEach Limitations:**
   - Nilai dari argumen `count` atau `for_each` **harus sudah diketahui sebelum siklus komputasi runtime dimulai** (sebelum resource API dieksekusi). 
   - *Gotcha:* Anda TIDAK BISA menggunakan output dari resource A yang belum dibuat untuk menghitung jumlah iterasi `count` pada resource B.
2. **Circular Dependencies (Siklus Dependensi Terlarang):**
   - Resource Security Group A mengizinkan trafik dari SG B, sementara SG B mengizinkan trafik dari SG A. Jika dideklarasikan inline, Core Graph Engine akan melempar error `Cycle: aws_security_group.a, aws_security_group.b`.
   - *Solusi:* Deklarasikan resource aturan secara atomik menggunakan resource terpisah (misal: `aws_security_group_rule`).
3. **State Drift Tidak Otomatis Terkoreksi Jika Resource Dihapus Luar Pita:**
   - Jika resource dihapus secara destruktif manual di console cloud, beberapa provider API mengembalikan respon `404 Not Found`. Terraform Core menangani ini dengan membuangnya dari state dan membuat ulang. Namun, jika resource dimodifikasi propertinya di luar pita (*in-place update* via console), dan properti tersebut berstatus `ignore_changes`, Terraform akan mengabaikan perbedaan tersebut selamanya.

---

### 14. Debugging & Troubleshooting Guide
Terraform menyediakan instrumentasi logging mendalam yang dikontrol via variabel environment:

#### 1. Setup Logging Granular
```bash
# Aktifkan level logging detail (TRACE, DEBUG, INFO, WARN, ERROR)
export TF_LOG=TRACE

# Tentukan path file output log agar terminal tidak terdistorsi
export TF_LOG_PATH="./terraform_debug.log"
```

#### 2. Metodologi Diagnostik
- **Tracing State Lock Stale:**
  - Gejala: `Error: Error acquiring the state lock: ConditionalCheckFailedException`.
  - Diagnosa: Eksekusi sebelumnya mati mendadak (killed/segfault) tanpa merilis lock ID.
  - Remediasi: Eksekusi `terraform force-unlock <LOCK-ID>` setelah mengonfirmasi tidak ada proses terraform apply lain yang sedang berjalan.
- **Validasi State Drift:**
  - Eksekusi: `terraform plan -refresh-only`
  - Perintah ini mendeteksi perubahan kondisi infrastruktur riil terhadap state tanpa mengusulkan tindakan update apapun ke desired state HCL.
- **State Surgery (Penataan Ulang State):**
  ```bash
  # Melihat daftar resource yang tersimpan di state
  terraform state list

  # Melihat detail satu resource
  terraform state show aws_vpc.primary

  # Menghapus resource dari state TANPA menghancurkan fisiknya di cloud (untrack)
  terraform state rm aws_vpc.primary
  ```

---

### 15. Testing & Validation Techniques
Pipelines Terraform modern mengimplementasikan beberapa lapisan *Quality Gate*:

1. **Static Analysis & Formatting:**
   ```bash
   terraform fmt -check -recursive
   terraform validate
   tflint --init && tflint
   ```
2. **Security Scanning (SAST):**
   Gunakan tools opensource seperti `tfsec` atau `checkov` untuk mengevaluasi kerentanan keamanan sebelum deploy:
   ```bash
   tfsec .
   ```
3. **Native Terraform Test Framework (Mulai v1.6.0+):**
   Tulis file pengujian sintetis (`tests/network_test.tftest.hcl`):
   ```hcl
   run "verify_vpc_cidr" {
     command = plan

     assert {
       condition     = aws_vpc.primary.cidr_block == "10.100.0.0/16"
       error_message = "VPC CIDR block menyimpang dari standar corporate."
     }
   }
   ```
   Eksekusi menggunakan binary bawaan:
   ```bash
   terraform test
   ```

---

### 16. Migration / Modernization: Moving from ClickOps
Untuk mengadopsi infrastruktur legacy yang dibuat manual via GUI Cloud Console ke dalam pengelolaan Terraform:

1. **Tulis Deklarasi Skelet HCL:**
   Buat blok resource kosong yang mewakili resource legacy:
   ```hcl
   resource "aws_s3_bucket" "legacy_assets" {
     # Properti akan diisi setelah import selesai
     bucket = "company-legacy-assets-bucket"
   }
   ```
2. **Import Resource ke State:**
   Jalankan sub-command import untuk menarik status fisik ke dalam state file:
   ```bash
   terraform import aws_s3_bucket.legacy_assets company-legacy-assets-bucket
   ```
3. **Modern Approach (Terraform v1.5+ `import` Block):**
   Alih-alih CLI imperative, deklarasikan langsung di HCL:
   ```hcl
   import {
     to = aws_s3_bucket.legacy_assets
     id = "company-legacy-assets-bucket"
   }
   ```
   Jalankan generator konfigurasi otomatis:
   ```bash
   terraform plan -generate-config-out=generated_bucket.tf
   ```
   Ini akan mengotomatisasi penulisan HCL dari resource cloud riil, mencegah human error.

---

### 17. Real-world Failure Scenario (Post-Mortem Style)

#### Incident Summary
Pada tanggal 12 Oktober, deployment otomatis pipeline merusak database cluster production (`db-aurora-cluster`), mengakibatkan downtime selama 47 menit dan kegagalan transaksi senilai puluhan ribu dolar.

#### Root Cause Analysis (RCA)
- Seorang engineer mengubah nama resource (logical identifier) di file `.tf` dari `resource "aws_rds_cluster" "db"` menjadi `resource "aws_rds_cluster" "primary_db"`.
- Core Engine memperlakukan penggantian nama blok HCL ini sebagai **penghapusan resource lama** (`Destroy`) dan **pembuatan resource baru** (`Create`), bukan pengubahan nama internal.
- Karena parameter `deletion_protection = false` terkonfigurasi, `terraform apply` langsung memanggil API `DeleteDBCluster` ke cloud provider.

#### Remediation & Recovery
- Operasi segera dihentikan via AWS IAM revocation. Database dipulihkan menggunakan restore point-in-time snapshot RDS otomatis.
- **Penerapan Fitur `moved` block:**
  Untuk kasus refactoring nama resource HCL tanpa memicu siklus recreate, wajib menggunakan blok `moved`:
  ```hcl
  moved {
    from = aws_rds_cluster.db
    to   = aws_rds_cluster.primary_db
  }
  ```
  Blok ini menginstruksikan Core Engine untuk memperbarui alamat node pada `.tfstate` tanpa menyentuh API cloud provider (`No-op` infrastruktur fisik).
- Ditambahkan guardrail `prevent_destroy`:
  ```hcl
  lifecycle {
    prevent_destroy = true
  }
  ```

---

### 18. Optimization Playbook
Gunakan checklist tindakan ini untuk menjaga eksekusi Terraform cepat, stabil, dan terukur:

```
[OPTIMIZATION PLAYBOOK]
├── 1. Optimasi Dependensi (Graph Latency)
│   ├── Pisahkan state file monolitik menjadi unit per-lingkungan / per-layer.
│   └── Hindari penggunaan dependensi eksplisit 'depends_on' jika referensi implisit (attribut chaining) sudah mencukupi.
├── 2. Optimasi CLI & I/O
│   ├── Gunakan '-parallelism=n' (Uji nilai optimum antara 10-30 pada CI runners performa tinggi).
│   └── Pasang backend cache provider lokal: TF_PLUGIN_CACHE_DIR="$HOME/.terraform.d/plugin-cache".
├── 3. Eliminasi State Bottleneck
│   ├── Hindari eksekusi 'terraform plan' menyeluruh bila hanya menguji satu resource.
│   └── Gunakan 'terraform plan -target=resource.name' HANYA saat kondisi perbaikan darurat.
└── 4. State Storage Hygiene
    ├── Aktifkan S3 Object Versioning pada bucket state file untuk rollback instan saat file rusak.
    └── Konfigurasi Lifecycle Rule untuk menghapus versi non-current state setelah 90 hari.
```

---

### 19. Interactive Knowledge Check

#### Q1. Apa perbedaan mendasar antara dependensi implisit dan eksplisit di Terraform, dan mana yang direkomendasikan?
A. Dependensi implisit menggunakan argumen `depends_on`, diutamakan karena mudah dibaca.  
B. Dependensi implisit terbentuk secara otomatis saat satu resource mereferensikan atribut dari resource lain; ini direkomendasikan karena memungkinkan Terraform memetakan DAG seoptimal mungkin.  
C. Dependensi eksplisit lebih aman karena provider secara manual memaksa jeda 10 detik antar API calls.  
D. Dependensi eksplisit dibangun menggunakan dynamic blocks; dependensi implisit dilarang dalam arsitektur modern.

#### Q2. Sebuah perubahan nama resource HCL dari `aws_instance.web` ke `aws_instance.app` akan menyebabkan Terraform Core:
A. Mengubah nama instans virtual machine di AWS console tanpa downtime.  
B. Menghapus (*destroy*) instans lama dan membuat (*create*) instans baru, kecuali diintervensi oleh blok `moved` atau migrasi manual via `terraform state mv`.  
C. Melempar error kompilasi karena satu ID cloud tidak boleh memiliki dua identitas HCL.  
D. Mengabaikan perubahan konfigurasi tersebut karena spesifikasi mesin tidak berubah.

#### Q3. Mengapa menyimpan secret credential database secara langsung pada variable Terraform lalu menampilkannya via output resource sangat berisiko, meskipun variabel ditandai `sensitive = true`?
A. Karena variabel `sensitive` memperlambat waktu parsing AST.  
B. Karena parameter `sensitive = true` hanya menyembunyikan nilai dari tampilan log konsol/terminal; nilai raw tetap tertulis utuh dalam bentuk teks biasa di dalam file `.tfstate`.  
C. Karena AWS IAM akan memblokir otomatis setiap variabel bertanda sensitif.  
D. Karena enkripsi state hanya berlaku pada local backend dan tidak aktif di remote backend.

---

### Kunci Jawaban & Troubleshooting Lab

#### Jawaban:
1. **B** — Dependensi implisit memungkinkan Directed Acyclic Graph (DAG) Engine memetakan dan menjalankan proses kreasi resource secara non-blocking paralel sejauh rantai referensi terpenuhi.
2. **B** — Mengubah logical ID resource pada HCL memutus relasi pemetaan state lama; Core Engine menganggap resource lama hilang dari desired state dan resource baru ditambahkan.
3. **B** — Atribut `sensitive = true` hanyalah proteksi UI layer agar teks tidak bocor di output CLI/CI pipeline log. File `.tfstate` selalu memuat representasi nilai asli dari state atribut tersebut.

#### Troubleshooting Lab (Hands-on Mini-Challenge)
**Problem Statement:**  
Jalankan skrip berikut di terminal lokal Anda. Perhatikan apa yang salah saat `terraform apply` dijalankan:

```hcl
resource "local_file" "a" {
  filename = "${path.module}/file_a.txt"
  content  = local_file.b.content
}

resource "local_file" "b" {
  filename = "${path.module}/file_b.txt"
  content  = local_file.a.content
}
```

**Diagnosa & Solusi:**
- *Analisis:* Kode di atas akan memicu kegagalan fatal pada Graph Builder Engine: `Error: Cycle: local_file.a, local_file.b`. Node resource `a` membutuhkan output data `b`, sementara node resource `b` mereferensikan output data `a`. 
- *Remediasi:* Pecahkan siklus tertutup tersebut dengan mengabstraksi input dasar ke dalam sebuah variabel independen atau resource ketiga yang menjadi *single source of truth*, sehingga aliran DAG berjalan linier searah tanpa loop.

---

### 20. Summary & Next Steps
Modul ini telah mengupas pondasi arsitektur internal Terraform Engine:
- **Paradigma Deklaratif:** Kita mendefinisikan *desired state*; Terraform merekonsiliasikannya dengan *current state*.
- **Terraform Core vs Providers:** Core bertindak sebagai komputator logika graph dan state reconciler; Provider bertindak sebagai adaptor API berbasis protokol gRPC.
- **State File:** Jantung kebenaran (*source of truth*) metadata resource yang harus dilindungi secara ketat, di-lock saat konkurensi, dan diisolasi guna meminimalisir blast radius.

**Langkah Selanjutnya:**  
Pada **Bab 01 Module 02**, kita akan mendalami secara mendalam sintaksis lanjutan HashiCorp Configuration Language (HCL): ekspresi kondisional, dynamic blocks, manipulasi koleksi kompleks (`for`, `splat`), dan perancangan *Custom Module* berskala enterprise yang dapat digunakan kembali (*reusable*).