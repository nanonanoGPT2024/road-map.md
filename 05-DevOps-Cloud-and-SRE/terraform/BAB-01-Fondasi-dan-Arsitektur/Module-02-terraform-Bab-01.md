# BAB 01: Fondasi dan Arsitektur
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengurai cara kerja internal Terraform Core dan Provider Plugins melalui protokol gRPC (go-plugin).
- Membedah siklus hidup *state file*, mekanisme *distributed state locking*, manipulasi memori lokal vs remote storage, serta algoritma resolusi konkurensi.
- Menguasai evaluasi graf eksekusi (*Directed Acyclic Graph* / DAG) untuk mendeteksi *circular dependency*, optimasi *parallelism traversal*, dan pemetaan sumber daya dinamis.
- Mengimplementasikan pola arsitektur *production-ready* berskala enterprise yang mengisolasi *blast radius* menggunakan multi-layer, multi-account, dan *remote state backends* terenkripsi.
- Menulis kode HCL2 tingkat lanjut memanfaatkan validasi tipe ketat, *dynamic blocks*, *custom validation*, dan kontrol *lifecycle* eksplisit.
- Menghitung, memitigasi, dan mengoperasionasikan trade-off performa, biaya API Cloud, skalabilitas state, serta risiko operasional di lingkungan berdaya beban tinggi.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib memahami:
- Sintaksis dasar HCL2 (deklarasi `resource`, `variable`, `output`, `locals`, `provider`).
- Siklus hidup dasar perintah CLI: `terraform init`, `plan`, `apply`, `destroy`.
- Pengetahuan fondasi arsitektur cloud (minimal satu cloud: AWS/GCP/Azure) terkait IAM, VPC, Object Storage, dan KMS.
- Konsep dasar protokol RPC/gRPC, serialisasi JSON, dan struktur data *Directed Acyclic Graph* (DAG).
- Pengoperasian terminal Linux/macOS tingkat lanjut (SSH, environment variables, jq, curl).

---

### 3. Concept & Internal Architecture

Arsitektur Terraform mengadopsi pola *decoupled client-server model* pada satu mesin lokal menggunakan arsitektur modular yang memisahkan logika parsing/state dengan logika eksekusi API platform cloud.

```
+-------------------------------------------------------------------------+
|                             TERRAFORM CORE                              |
|                                                                         |
|  +--------------------+   +-------------------+   +------------------+  |
|  | Configuration CLI  |-->| AST Construction  |-->| DAG Engine       |  |
|  | Parser (HCL2)      |   | Evaluation Engine |   | (Graph Walk)     |  |
|  +--------------------+   +-------------------+   +------------------+  |
|                                     |                       |           |
|                                     v                       v           |
|                           +-------------------+   +------------------+  |
|                           | State Management  |   | Concurrency      |  |
|                           | Engine (In-Memory)|   | Pool (Parallel)  |  |
|                           +-------------------+   +------------------+  |
+-------------------------------------|-----------------------|-----------+
                                      | Local Unix Socket     |
                                      | or Named Pipe (RPC)   |
                                      v (gRPC via go-plugin)  v
+-------------------------------------------------------------------------+
|                            PROVIDER PLUGINS                             |
|                                                                         |
|  +------------------------+                  +-----------------------+  |
|  | Provider: AWS          |                  | Provider: Vault       |  |
|  | - Schema Definition    |                  | - Schema Definition   |  |
|  | - CRUD Resource Hooks  |                  | - CRUD Resource Hooks |  |
|  +-----------|------------+                  +-----------|-----------+  |
+--------------|-------------------------------------------|--------------+
               | HTTPS REST/gRPC                           | HTTPS/mTLS
               v                                           v
    [ Target: AWS APIs ]                         [ Target: Vault API ]
```

#### A. Pemisahan Terraform Core dan Provider Plugins
Terraform tidak mendistribusikan pustaka vendor cloud secara monolitik. Ekosistem ini terbelah menjadi dua subsistem independen:
1. **Terraform Core**:
   - Ditulis murni dalam Go (`hashicorp/terraform`).
   - Bertanggung jawab memvalidasi sintaksis HCL, membangun AST (*Abstract Syntax Tree*), menyusun graf ketergantungan (*Dependency Graph*), mengelola file *state*, mendeteksi *drift*, dan menentukan delta perubahan (*plan diff calculation*).
   - Core sama sekali tidak mengetahui cara membuat AWS EC2, GCP Bucket, atau Cloudflare DNS.
2. **Provider Plugins**:
   - Berdiri sebagai binary executable terpisah yang diunduh pada fase `terraform init` ke direktori `.terraform/providers/`.
   - Menggunakan pustaka `hashicorp/go-plugin` untuk berkomunikasi dengan Core melalui interface RPC/gRPC melintasi *loopback unix socket* atau *named pipes*.
   - Mengimplementasikan antarmuka *CRUD framework* (`Create`, `Read`, `Update`, `Delete`) spesifik untuk API target. Core mengirimkan *payload intent* yang telah di-parse, dan plugin mengonversinya menjadi panggilan REST/gRPC ke vendor cloud.

#### B. Anatomi State Engine, Lineage, Serial, dan Locking
*State* bukan sekadar catatan riwayat konfigurasi, melainkan *lookup index* bidirectional yang memetakan identifier internal Terraform ke identitas unik resource pada vendor cloud.

Struktur JSON State mencakup metadata esensial:
- **`format_version`**: Versi skema engine state.
- **`terraform_version`**: Versi engine yang menulis state tersebut.
- **`serial`**: Integer berurutan naik (*incremented on write*). Core menolak operasi jika serial remote lebih tinggi dari serial local session untuk mencegah *stale state overwriting*.
- **`lineage`**: UUID unik yang dihasilkan saat inisialisasi state pertama kali. Jika dua state memiliki ID lineage berbeda, Terraform memblokir migrasi untuk mencegah data corruption lintas project.
- **Mekanisme Locking**: Saat fase `plan` (opsional lock) atau `apply` (wajib lock) dijalankan, Core memanggil backend plugin untuk mengunci state. Pada AWS S3 backend, locking dieksekusi dengan menulis entitas pada tabel AWS DynamoDB yang memegang atribut:
  - `LockID`: Berisi `<bucket-name>/<path-to-state>-md5`
  - `Info`: JSON berisi ID proses, host asal, user, dan timestamp lock dibuat.
  Jika tabel mengembalikan error `ConditionalCheckFailedException`, Terraform CLI menghentikan proses (*fail-fast*) guna melindungi state dari *race condition*.

#### C. Directed Acyclic Graph (DAG) & Algoritma Topological Traversal
Terraform mengeksekusi sumber daya menggunakan pendekatan graf asiklik terarah (DAG):
1. **Konstruksi Graf**: Setiap blok `resource`, `data`, `variable`, dan `provider` dipetakan sebagai sebuah *node*. Ketergantungan eksplisit (via `depends_on`) atau implisit (via ekspresi interpolasi atribut referensi seperti `aws_subnet.main.id`) dipetakan sebagai *edge* berarah ($U \rightarrow V$ berarti node $U$ harus selesai dievaluasi sebelum node $V$).
2. **Validasi Asiklik**: Engine menggunakan algoritma *Tarjan's strongly connected components* atau modifikasi DFS untuk mendeteksi *cycle*. Jika ada siklus dependensi (contoh: Resource A butuh Resource B, dan Resource B butuh Resource A), Core menolak eksekusi sebelum mengeksekusi API calls.
3. **Graph Walking & Parallelism**: Engine mengurai graf menggunakan *Topological Sort*. Node independen (akar) dieksekusi secara konkuren. Default konparalelan adalah 10 goroutine worker pool (`-parallelism=10`). Goroutine membaca channel antrean dan mengirim instruksi gRPC ke provider plugin yang relevan secara asinkron.

---

### 4. Why & What

| Dimensi | Pendekatan Monolitik / Skrip Ad-hoc (Bash/CLI) | Pendekatan Enterprise Terraform (Decoupled HCL Engine) |
| :--- | :--- | :--- |
| **State Resolution** | Mengandalkan polling manual ke Cloud API; lambat, rawan *rate-limit*, dan tidak ada sumber *drift* absolut. | *State mapping* deterministik. Core tahu resource mana yang dibuat oleh Terraform dan mana yang dibuat di luar ekosistem. |
| **Concurrency Control** | Rawan tabrakan; jika dua pipeline mengeksekusi skrip bersamaan, terjadi tumpang tindih alokasi resource (*split-brain*). | *Distributed State Locking* otomatis via backend engine (DynamoDB, GCS, Blob Storage, Terraform Cloud). |
| **Dependency Management**| Harus diatur manual via sekuensial bash sleep atau skrip pengecekan kesiapan (looping curl). | Diatur secara matematis oleh DAG Engine. Dependensi implisit dieksekusi paralel secara maksimal tanpa kode tambahan. |
| **Blast Radius Isolation**| Seluruh resource seringkali berada dalam satu file skrip masif; bug pada satu baris merusak seluruh infrastruktur. | Isolasi direktori modular, multi-state, dan *remote state referencing* membatasi dampak destruksi pada domain terisolasi. |

**Apa yang terjadi pada saat `terraform plan`?**
1. Terraform Core memanggil provider untuk melakukan tahap `Read` (Reconciliation Phase) terhadap seluruh resource yang terdaftar pada state file.
2. Provider mengembalikan status aktual (*Current Real-world State*) via API.
3. Core membandingkan *Current State* dengan kode HCL (*Desired State*).
4. Core mengkalkulasi selisihnya (*Diff calculation*) dan menyusun rencana tindakan: `+` create, `~` update in-place, `-` destroy, `+/-` destroy and re-create.
5. Menghasilkan *speculative plan* tanpa mengubah infrastruktur fisik maupun memodifikasi state disk.

---

### 5. How (Workflow Detail)

Alur kerja production pipeline automasi Terraform diatur dengan disiplin ketat tanpa eksekusi langsung dari mesin lokal engineer (*No local apply from developer laptop*):

```
+-------------------------------------------------------------------------------------------------------+
|                                    CI/CD PIPELINE ORCHESTRATION                                       |
|                                                                                                       |
| [1. Git Commit]                                                                                       |
|        |                                                                                              |
|        v                                                                                              |
| [2. Pre-Flight Validation]                                                                            |
|        |--> `terraform fmt -check` (Format enforcement)                                               |
|        |--> `terraform validate` (Syntax and internal types verification)                             |
|        |--> `tflint` & `trivy / checkov` (Static analysis, linting, security scanning)                |
|        |                                                                                              |
|        v                                                                                              |
| [3. Initialization & Locking Phase]                                                                  |
|        |--> `terraform init -backend-config=...` (Load backend state provider)                       |
|        |--> Fetch Provider Plugins (gRPC binaries from private/public registry)                       |
|        |                                                                                              |
|        v                                                                                              |
| [4. State Refresh & Graph Construction]                                                              |
|        |--> Acquire DynamoDB State Lock                                                               |
|        |--> Graph Walking: Refresh state against target APIs                                          |
|        |                                                                                              |
|        v                                                                                              |
| [5. Plan Generation & Artefact Storing]                                                              |
|        |--> `terraform plan -out=tfplan.binary` (Serialize exact deterministic mutations)             |
|        |--> Release DynamoDB State Lock                                                               |
|        |--> Push `tfplan.binary` to encrypted ephemeral CI artifact storage                          |
|        |                                                                                              |
|        v                                                                                              |
| [6. Manual Approval Gate / Policy Checks (OPA/Sentinel)]                                              |
|        |--> Scan `tfplan` against cost estimation & security boundaries                               |
|        |--> Human Reviewers approve production changes                                                |
|        |                                                                                              |
|        v                                                                                              |
| [7. Apply Phase]                                                                                      |
|        |--> Acquire DynamoDB State Lock                                                               |
|        |--> `terraform apply tfplan.binary` (Strictly execute stored binary plan)                     |
|        |--> Topological DAG traversal mutations (Resource API calls via gRPC)                         |
|        |--> Increment serial, persist updated state to S3/Backend bucket                              |
|        |--> Release DynamoDB State Lock                                                               |
+-------------------------------------------------------------------------------------------------------+
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitek, Kontraktor, dan Blueprint Bangunan
- **Terraform Core** adalah **Konsultan Manajemen Konstruksi (MK)**. Ia membaca cetak biru arsitektur (File HCL), mengingat sejarah pembangunan gedung lantai per lantai (State File), dan menyusun jadwal kerja yang logis (DAG: fondasi harus selesai sebelum tiang beton dibuat). MK tidak bisa memasang pipa ledeng atau mengecor semen sendiri.
- **Provider Plugin** adalah **Mandor Spesialis (Sub-kontraktor)**. Mandor AWS paham cara memanggil truk semen AWS; Mandor Cloudflare paham instalasi kaca jendela Cloudflare. MK berkomunikasi dengan para mandor melalui walkie-talkie standar (protokol gRPC).
- **State File** adalah **As-Built Drawing** (buku log fisik gedung). Jika as-built drawing hilang atau dirusak, MK tidak tahu apakah kabel di balik dinding bervoltase tinggi atau sudah dimatikan, memicu risiko fatal jika ada renovasi lanjutan.
- **State Lock** adalah **Gembok Papan Sirkuit (LOTO - Lockout/Tagout)**. Hanya satu mandor yang boleh mengubah sistem kelistrikan pada satu waktu; mandor lain dilarang menyentuh panel sampai gembok dibuka.

```
       CONCURRENCY RESOLUTION TIMELINE (DYNAMO-LOCK)

Pipeline A (Apply)                       DynamoDB Mutex                      Pipeline B (Plan/Apply)
       |                                       |                                       |
  [00:00] Init & Pre-flight                   |                                  [00:00] Init
       |                                       |                                       |
  [00:01] Acquire Lock ----------------------> |                                       |
       |                              [STATUS: LOCKED by A]                            |
  [00:02] Start Refresh & Plan                 | <---------------------- [00:02] Try Acquire Lock
       |                                       |                                       |
       |                                       | --(ConditionalCheckFailed)----------> X [FAIL FAST]
       |                                       |                        "Error: State locked by A.
       |                                       |                         Lock ID: 2bf81b1c-..."
  [00:05] Resource Provisioning (DAG Walk)     |
       |                                       |
  [00:08] Apply Successful                     |
       |                                       |
  [00:09] Write State (Serial: n+1)            |
       |                                       |
  [00:10] Release Lock ----------------------> |
                                      [STATUS: UNLOCKED]
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Fundamental Syntax & Lifecycle Block
Menunjukkan kontrol eksplisit destruksi dan pembuatan ulang resource serta pengecekan variabel dasar.

```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4.0"
    }
  }
}

variable "environment" {
  type        = string
  description = "Target deployment environment"
  default     = "staging"

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Environment must be either 'staging' or 'production'."
  }
}

resource "local_file" "config" {
  filename = "${path.module}/generated_config_${var.environment}.json"
  content = jsonencode({
    env       = var.environment
    timestamp = timestamp()
  })

  lifecycle {
    # Mencegah downtime dengan memvalidasi node baru aktif sebelum node lama dimusnahkan
    create_before_destroy = true
    
    # Abaikan perubahan timestamp agar tidak memicu rotasi tak perlu pada plan berikutnya
    ignore_changes = [
      content
    ]
  }
}

output "config_file_path" {
  value       = local_file.config.filename
  description = "Path to generated configuration file"
}
```

#### B. Practical Example: Enterprise-Grade Network Isolation Module
Contoh produksi yang menggunakan tipe data kompleks (*structural typing*), *dynamic blocks*, *custom preconditions/postconditions*, dan arsitektur provider AWS terkini.

```hcl
# versions.tf
terraform {
  required_version = ">= 1.6.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30.0"
    }
  }

  backend "s3" {
    bucket         = "corp-tfstate-production-ap-southeast-1"
    key            = "networking/vpc/terraform.tfstate"
    region         = "ap-southeast-1"
    encrypt        = true
    dynamodb_table = "corp-tflock-production"
  }
}

# variables.tf
variable "vpc_cidr" {
  type        = string
  description = "The IPv4 CIDR block for the VPC"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr)) && split("/", var.vpc_cidr)[1] == "16"
    error_message = "VPC CIDR must be a valid IPv4 CIDR block with a /16 prefix size."
  }
}

variable "subnet_topology" {
  type = map(object({
    cidr_block        = string
    availability_zone = string
    is_public         = bool
    tags              = map(string)
  }))
  description = "Map of subnet configurations with structural type constraints"

  validation {
    condition = alltrue([
      for k, v in var.subnet_topology : can(cidrhost(v.cidr_block, 0))
    ])
    error_message = "All subnet configurations must supply a valid cidr_block."
  }
}

# locals.tf
locals {
  common_tags = {
    OrchestratedBy = "Terraform-Enterprise"
    ManagedBy      = "CloudPlatformTeam"
    Repository     = "git@github.com:corp/infrastructure-live.git"
  }
}

# main.tf
resource "aws_vpc" "core" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local_common_tags, {
    Name = "vpc-core-production"
  })

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_subnet" "managed_subnets" {
  for_each = var.subnet_topology

  vpc_id            = aws_vpc.core.id
  cidr_block        = each.value.cidr_block
  availability_zone = each.value.availability_zone

  map_public_ip_on_launch = each.value.is_public

  tags = merge(local.common_tags, each.value.tags, {
    Name = each.key
  })

  # Validasi ketersediaan subnet dalam jangkauan CIDR VPC
  lifecycle {
    precondition {
      condition     = can(cidrsubnet(aws_vpc.core.cidr_block, 8, 0))
      error_message = "Core VPC CIDR is invalid for subnet allocation."
    }
    postcondition {
      condition     = self.vpc_id == aws_vpc.core.id
      error_message = "The allocated subnet must belong to the created core VPC."
    }
  }
}

# Dynamic Block Security Group Example
variable "security_group_ingress_rules" {
  type = list(object({
    port        = number
    proto       = string
    cidr_blocks = list(string)
    description = string
  }))
  default = [
    {
      port        = 443
      proto       = "tcp"
      cidr_blocks = ["10.0.0.0/8"]
      description = "Allow TLS from internal network"
    }
  ]
}

resource "aws_security_group" "core_endpoints" {
  name_prefix = "vpc-endpoints-sg-"
  description = "Security group for VPC Interface Endpoints"
  vpc_id      = aws_vpc.core.id

  dynamic "ingress" {
    for_each = var.security_group_ingress_rules
    content {
      description = ingress.value.description
      from_port   = ingress.value.port
      to_port     = ingress.value.port
      protocol    = ingress.value.proto
      cidr_blocks = ingress.value.cidr_blocks
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

# outputs.tf
output "vpc_id" {
  value       = aws_vpc.core.id
  description = "ID of the core production VPC"
}

output "subnet_ids_map" {
  value = {
    for k, v in aws_subnet.managed_subnets : k => v.id
  }
  description = "Map of allocated subnet names to Subnet AWS IDs"
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Penataan Ulang Arsitektur Multi-Account AWS Fintech Scale (FinCorp)
- **Kondisi Awal**: FinCorp mengelola infrastruktur melalui satu repository Terraform tunggal (Monolitik State). State file berukuran 120MB memuat 2.800 resource dari 14 domain mikroservis, database RDS Aurora, dan modul jaringan VPC, disimpan dalam satu file `s3://fincorp-prod/terraform.tfstate`.
- **Insiden Fatal**:
  1. Waktu eksekusi `terraform plan` memakan waktu 48 menit karena serialisasi pembacaan AWS API rate-limit (`ThrottlingException`).
  2. Saat ada *hotfix* DNS Cloudflare di repo tersebut, seorang engineer mengeksekusi apply dan secara tidak sengaja memicu re-creation modul AWS IAM Roles global karena state drift di luar jangkauannya. Seluruh sistem *payment gateway* offline selama 2 jam (*Blast radius* kolosal).

#### Solusi Arsitektural:
1. **Dekomposisi Multi-State (Blast Radius Isolation)**:
   Membongkar monolitik state menjadi beberapa root module independen berdasarkan batas domain dan tingkat perubahan (*change cadence*):
   - `core-network` (diupdate 6 bulan sekali)
   - `identity-access` (diupdate 1 bulan sekali)
   - `shared-compute-eks` (diupdate 2 minggu sekali)
   - `app-payment-service` (diupdate harian via pipeline mikroservis)
2. **Implementasi State Cross-Referencing**:
   Alih-alih menggunakan `data "terraform_remote_state"` yang membuka akses baca seluruh file state lain (berisiko membocorkan credential dalam output state), FinCorp mengimplementasikan parameter store berbasis AWS SSM Parameter Store / HashiCorp Vault. Output Network dipublikasikan ke SSM:
   ```
   /fincorp/network/prod/vpc_id = "vpc-0abc123"
   /fincorp/network/prod/subnets/private_a = "subnet-0xyz789"
   ```
   Modul compute hanya membaca data store SSM tersebut menggunakan `data "aws_ssm_parameter"`.
3. **Hasil Optimasi**:
   - `terraform plan` domain compute turun dari 48 menit ke 45 detik.
   - Blast radius terisolasi 100%. Kegagalan pada deployment layer aplikasi tidak memiliki hak akses/kemampuan untuk menyentuh Core VPC maupun DB RDS.

---

### 9. Trade-offs

| Aspek | Pendekatan Monolitik State | Multi-Layer Micro-State | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **API Latency & Refresh Time** | **Sangat Buruk**: Skala linear terhadap total resource. Rentan AWS rate-limiting. | **Optimal**: Refresh hanya mengeksekusi subset kecil resource yang relevan. | Micro-state menuntut deployment berurutan (*orchestrated pipeline*) jika ada dependensi horizontal. |
| **State File Concurrency** | **Tinggi Kontensi**: Developer tim A memblokir tim B karena DynamoDB lock dipegang global. | **Nol Kontensi**: Tim Network dan Tim Compute berjalan di pipeline lock yang berbeda. | Menambah kompleksitas CI/CD; butuh orchestrator seperti Atlantis, Spacelift, atau Terraform Cloud. |
| **Data Sharing Overhead** | **Trivial**: Semua resource saling membaca langsung via dependensi atribut HCL lokal. | **Perlu Broker Data**: Butuh SSM Parameter Store, Consul, atau Data Sources eksplisit. | Arsitektur data sharing menjadi *eventually consistent*; rotasi data upstream butuh sinkronisasi downstream. |
| **Cost & Complexity (Dynamo/S3)**| **Murah & Sederhana**: 1 bucket, 1 tabel DynamoDB, 1 konfigurasi backend. | **Overhead Manajemen**: Puluhan bucket/folder backend, strict IAM permission matrix. | Biaya komputasi S3/Dynamo naik marginal, tetapi terbayar lunas oleh efisiensi jam kerja engineer. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Fatal `count` pada Array Index Refactoring
- **Anti-Pattern**: Menggunakan `count` dengan input list strings:
  ```hcl
  # JANGAN LAKUKAN INI DI PRODUKSI UNTUK RESOURCE KRITIKAL
  variable "subnets" {
    default = ["subnet-a", "subnet-b", "subnet-c"]
  }
  resource "aws_subnet" "list" {
    count      = length(var.subnets)
    cidr_block = "10.0.${count.index}.0/24"
  }
  ```
- **Masalah**: Jika elemen `"subnet-a"` dihapus dari array tengah/depan, `count.index` akan bergeser. Terraform menandai `subnet-b` dihancurkan dan dibuat ulang menjadi `subnet-a`, merusak database/workload aktif di dalamnya!
- **Solusi**: Selalu gunakan `for_each` dengan *unique set/map keys*:
  ```hcl
  resource "aws_subnet" "mapped" {
    for_each   = toset(var.subnets)
    cidr_block = ...
  }
  ```

#### 2. DynamoDB Lock Hanging (Error: `ConditionalCheckFailedException`)
- **Penyebab**: Pipeline CI/CD terputus secara mendadak (pod terminated, OOMKilled, atau dibatalkan paksa saat `terraform apply` sedang berjalan). Lock pada DynamoDB tertinggal.
- **Troubleshooting Step**:
  1. Cek log CI/CD untuk memastikan TIDAK ADA instance terraform lain yang sedang berjalan.
  2. Ekstrak `Lock Info Info ID` dari pesan error:
     ```bash
     Error acquiring the state lock: ConditionalCheckFailedException: ...
     Lock Info:
       ID:        e37d5704-5f56-42bb-85bb-685ebefb0981
       Path:      corp-tfstate/terraform.tfstate
       Who:       runner@ci-node-04
       Created:   2026-03-30 08:30:00.123456789 UTC
     ```
  3. Lakukan unlock manual secara aman:
     ```bash
     terraform force-unlock -force e37d5704-5f56-42bb-85bb-685ebefb0981
     ```

#### 3. State Drift akibat Out-of-Band Modification
- **Gejala**: Resource diubah manual via Cloud Web Console. Saat `terraform plan`, Terraform mendeteksi diff tak terduga dan mencoba mengembalikan konfigurasi atau recreate resource.
- **Troubleshooting Step**:
  1. Jalankan target plan untuk mengisolasi resource yang bermasalah:
     ```bash
     terraform plan -target=aws_security_group.core_endpoints -refresh-only
     ```
  2. Amati diff antara konfigurasi lokal vs remote.
  3. Gunakan `terraform apply -refresh-only` jika perubahan out-of-band ingin diadopsi ke dalam state file tanpa memodifikasi real-world infrastructure (selaraskan konfigurasi HCL setelahnya).

---

### 11. Best Practices (Production Checklist)

- [ ] **State Storage Encryption**: Aktifkan S3 Server-Side Encryption (SSE-KMS) dengan KMS Customer Managed Key (CMK) independen.
- [ ] **State Versioning**: Aktifkan object versioning wajib pada S3 state bucket untuk memungkinkan *point-in-time recovery* jika terjadi korupsi file state.
- [ ] **State Bucket Public Access Block**: Aktifkan S3 Public Access Block 100% dan batasi akses S3 bucket via IAM Policy hanya ke ARN execution role CI/CD.
- [ ] **Immutability of Plans**: Simpan artefak `terraform plan -out=tfplan` dan jadikan artefak tersebut satu-satunya basis input untuk perintah `terraform apply tfplan`.
- [ ] **No Secrets in Plaintext State**: Hindari mereferensikan raw database password di HCL. Gunakan data block HashiCorp Vault, AWS Secrets Manager, atau KMS-encrypted payloads.
- [ ] **Pinning Versioning Ketat**: Gunakan operator pesimistik `~>` untuk provider version dan kunci Terraform Core version ke versi minor spesifik (`~> 1.6.0`).
- [ ] **Strict Blast Radius**: Batasi maksimal 100–150 resource per root module / state file.
- [ ] **Execution Parallelism Bounds**: Di sistem enterprise berskala besar, batasi flag concurrency (`-parallelism=5`) saat memodifikasi resource yang memicu *heavy cloud rate-limits* (misalnya API AWS CloudFront atau IAM).

---

### 12. Hands-on Practice

Buat dan simpan struktur file berikut pada direktori kerja: `hands-on/m02/`

#### Langkah 1: Inisialisasi Direktori Proyek
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

#### Langkah 2: Setup Infrastruktur Mocking dengan Localstack / HashiCorp Null & Local Provider
Buat file `main.tf`:
```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2.0"
    }
  }
}

variable "services" {
  type = map(object({
    port        = number
    environment = string
    allocated   = bool
  }))
  default = {
    auth = {
      port        = 8080
      environment = "production"
      allocated   = true
    }
    billing = {
      port        = 8081
      environment = "production"
      allocated   = true
    }
    reporting = {
      port        = 8082
      environment = "staging"
      allocated   = false
    }
  }
}

locals {
  active_services = {
    for k, v in var.services : k => v if v.allocated && v.environment == "production"
  }
}

resource "local_file" "service_manifest" {
  for_each = local.active_services

  filename = "${path.module}/manifests/${each.key}-service.json"
  content = jsonencode({
    service_name = each.key
    listen_port  = each.value.port
    cluster_env  = each.value.environment
    metadata = {
      managed_by = "terraform-m02-lab"
      sha        = sha256("${each.key}-${each.value.port}")
    }
  })

  lifecycle {
    postcondition {
      condition     = fileexists(self.filename)
      error_message = "File manifest was not successfully materialized on disk."
    }
  }
}

resource "null_resource" "audit_trail" {
  depends_on = [local_file.service_manifest]

  triggers = {
    service_keys = join(",", keys(local.active_services))
  }

  provisioner "local-exec" {
    command = "echo 'Audit: Active production services deployed at' $(date) 'Keys: ${join(",", keys(local.active_services))}' >> deploy.log"
  }
}

output "deployed_manifest_paths" {
  value = {
    for k, v in local_file.service_manifest : k => v.filename
  }
}
```

#### Langkah 3: Eksekusi Lifecycle & Validasi Internal Engine
Jalankan runtutan instruksi berikut di terminal:

```bash
# 1. Inisialisasi provider plugins
terraform init

# 2. Periksa graf dependensi DAG (Render ke format dot)
terraform graph > dag.dot
echo "Graphviz DOT file generated. Render with: dot -Tpng dag.dot -o dag.png"

# 3. Validasi konfigurasi secara statis
terraform validate

# 4. Generate plan biner deterministik
terraform plan -out=execution.tfplan

# 5. Lakukan inspeksi plan biner menggunakan sub-command show
terraform show -json execution.tfplan | jq '.resource_changes[] | {address: .address, actions: .change.actions}'

# 6. Terapkan plan biner
terraform apply execution.tfplan

# 7. Verifikasi file hasil deploy dan log audit
cat deploy.log
cat manifests/auth-service.json | jq .
cat manifests/billing-service.json | jq .

# 8. Cek status state file lokal
terraform state list
terraform state show local_file.service_manifest[\"auth\"]
```

---

### 13. Exercise

#### Level: Easy
1. Dari file `hands-on/m02/main.tf`, tambahkan satu servis baru `analytics` pada variabel `services` dengan port `8083`, environment `production`, dan allocated `true`.
2. Jalankan `terraform plan` dan verifikasi bahwa hanya 1 resource baru yang akan di-*create* tanpa mengubah atau menghancurkan servis `auth` dan `billing`.

#### Level: Medium
1. Ubah definisi `local.active_services` agar memvalidasi port: Semua port yang valid harus bernilai di atas `1024` dan di bawah `65535`.
2. Tambahkan block `precondition` pada `local_file.service_manifest` yang memvalidasi bahwa `each.key` tidak boleh berakhiran dengan kata `-test`.
3. Demonstrasikan kegagalan evaluasi preconditions tersebut dengan memasukkan data variabel yang tidak valid.

#### Level: Hard
1. Buat skrip manipulasi state lanjutan.
2. Tanpa menghapus file manifest di sistem lokal, lakukan operasi `terraform state rm` untuk mengeluarkan resource `local_file.service_manifest["billing"]` dari kontrol state.
3. Jalankan `terraform plan`. Amati apa yang dilakukan Terraform.
4. Gunakan perintah `terraform import` untuk memasukkan kembali file fisik `manifests/billing-service.json` ke dalam state tanpa merusak konfigurasi berjalan.

---

### 14. Challenge

**Skenario**:
Sebuah perusahaan enterprise mengalami reorganisasi arsitektur. Anda diminta menggabungkan dua root module terpisah: `module-network-prod` dan `module-security-prod` yang selama ini memiliki state file terpisah di S3 bucket yang berbeda, menjadi satu arsitektur terpadu *Composite Root Module*. 

Kondisi & Batasan:
- Tidak boleh ada downtime jaringan sama sekali pada VPC dan Security Group live.
- Operasi ini TIDAK BOLEH memicu penghancuran resource (`destroy`) maupun pembuatan ulang (`re-create`).
- Skenario harus diselesaikan murni menggunakan manipulasi tingkat lanjut Terraform State CLI (`terraform state mv`, state storage cross-pulling, atau HCL2 `moved` blocks yang diperkenalkan di Terraform 1.1+).
- Tuliskan rancangan dokumen langkah kerja (*Runbook* eksekusi) serta sintaks deklarasi blok `moved` untuk memetakan alamat resource:
  - Dari state asal: `aws_security_group.alb`
  - Menjadi alamat baru di composite state: `module.security.aws_security_group.alb`

Tantangan ini menguji keahlian Anda memanipulasi graf internal dan memori state Terraform tanpa merusak infrastruktur produksi aktif.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Protokol apa yang digunakan oleh Terraform Core untuk berkomunikasi secara asinkron/sinkron dengan binary executable Provider Plugin?
   - A. WebSockets
   - B. gRPC melalui go-plugin
   - C. Raw TCP socket dengan pesan XML
   - D. HTTP REST JSON standar

2. Apa fungsi dari nilai `serial` pada struktur file state JSON Terraform?
   - A. Menunjukkan berapa kali CLI Terraform di-install di mesin host.
   - B. Angka integer yang bertambah setiap kali state berhasil ditulis, untuk mendeteksi penimpaan state usang (*stale writes*).
   - C. Identifier unik untuk memetakan akun cloud vendor.
   - D. Jumlah total node pada Directed Acyclic Graph (DAG).

3. Apa implikasi penggunaan flag `-parallelism=20` pada command `terraform apply`?
   - A. Menurunkan konsumsi memori lokal Terraform Core sebesar 50%.
   - B. Meningkatkan kuota maksimum resource pada akun Cloud Provider secara otomatis.
   - C. Membuka hingga 20 goroutine concurrent traversal workers, yang mempercepat deployment namun meningkatkan risiko terkena API rate-limiting/throttling.
   - D. Membagi eksekusi state locking ke dalam 20 sub-tabel database DynamoDB.

4. Kapan waktu yang tepat untuk memanfaatkan blok siklus hidup `create_before_destroy = true`?
   - A. Saat membuat resource storage S3 bucket agar data lama tidak terhapus.
   - B. Saat memperbarui resource yang mewajibkan zero-downtime, di mana pengganti baru harus online sebelum resource lama ditarik dari peredaran.
   - C. Saat menghapus cluster database secara permanen.
   - D. Hanya saat menggunakan backend lokal.

5. Blok deklarasi manakah yang dievaluasi sebelum Terraform mengeksekusi operasi pembuatan atau pembaruan konfigurasi pada resource target?
   - A. `postcondition`
   - B. `precondition`
   - C. `output`
   - D. `check`

---

#### Bagian 2: Intermediate (Pilihan Ganda & Analisis Kasus Singkat)
6. Manakah konfigurasi yang benar dan aman untuk mencegah penghancuran sebuah database production akibat ketidaksengajaan eksekusi operator pipeline?
   - A. `lifecycle { ignore_changes = all }`
   - B. `lifecycle { prevent_destroy = true }`
   - C. `lifecycle { no_destroy = true }`
   - D. Mengubah file state menjadi Read-Only di OS level.

7. Perhatikan kode berikut:
   ```hcl
   variable "rules" {
     type = list(string)
     default = ["admin", "dev"]
   }
   resource "aws_iam_role" "role" {
     count = length(var.rules)
     name  = var.rules[count.index]
   }
   ```
   Jika variabel `rules` diubah menjadi `["sec", "admin", "dev"]`, apa tindakan yang akan dilakukan Terraform Engine saat `apply`?
   - A. Membuat 1 role baru bernama `sec` di index terakhir tanpa memodifikasi index lain.
   - B. Memperbarui role index 0 dari `admin` menjadi `sec`, role index 1 dari `dev` menjadi `admin`, dan membuat role baru index 2 `dev`.
   - C. Menggagalkan eksekusi karena penambahan array index dilarang.
   - D. Menghapus semua role yang ada dan membuat 3 role baru dari awal.

8. Apa kelemahan utama dari membagikan data antar-state menggunakan blok `data "terraform_remote_state"` di organisasi enterprise?
   - A. Memperlambat proses `terraform validate`.
   - B. Membutuhkan hak akses baca (`read access`) ke seluruh isi target state file, yang berpotensi membocorkan output sensitif/rahasia ke tim non-otoritas.
   - C. Tidak mendukung backend AWS S3.
   - D. Tidak dapat mengembalikan tipe data string.

9. Jika proses `terraform plan -refresh-only` dijalankan, modifikasi apa yang terjadi pada arsitektur?
   - A. Memaksa cloud vendor untuk mencocokkan konfigurasi dengan file HCL.
   - B. Membaca kondisi aktual infrastruktur dan memperbarui file state lokal/remote tanpa mengubah konfigurasi HCL maupun real-world infrastructure.
   - C. Menghapus konfigurasi yang tidak terdaftar di file state.
   - D. Mengosongkan seluruh isi tabel DynamoDB lock.

10. Apa kegunaan utama atribut `lineage` pada header state file?
    - A. Memvalidasi bahwa file state tetap berada dalam garis sejarah (*lineage*) proyek yang sama dan bukan file state dari workspace/proyek lain yang tertukar secara tidak sengaja.
    - B. Mengenkripsi payload state dengan private key milik vendor cloud.
    - C. Menentukan versi minimum binary Terraform CLI.
    - D. Menghitung jumlah commit git pengubah state file.

---

#### Bagian 3: Skenario Kasus Produksi (Esai Analitis / Problem-Solving)

11. **Skenario Rate-Limiting Skala Masif**:
    Pipeline CI/CD Terraform di perusahaan Anda mengelola 1.800 resource AWS dalam satu workspace. Setiap kali jadwal berkala *drift-detection* dijalankan setiap 30 menit, AWS API melempar error `RequestLimitExceeded` / `ThrottlingException` pada layer VPC dan EC2 calls, menyebabkan build pipeline gagal (fail status).
    - *Tugas Anda*: Jelaskan tiga langkah strategis teknis arsitektur dan eksekusi Terraform CLI yang harus diterapkan untuk memitigasi isu tersebut tanpa mematikan fitur drift-detection!

12. **Skenario State Locking Deadlock**:
    Sebuah deployment darurat dihentikan paksa (kill -9) oleh engineer karena koneksi VPN kantor drop saat perintah `terraform apply` sedang berada di tengah-tengah alokasi load balancer. State terkunci di DynamoDB. Rekan engineer lain panik dan ingin menghapus row langsung dari AWS Console DynamoDB.
    - *Tugas Anda*: Analisis risiko dari tindakan menghapus row langsung via AWS Console DynamoDB! Berikan rekomendasi langkah operasional presisi (*standard operating procedure*) yang seharusnya dijalankan oleh tim SRE menggunakan Terraform CLI tooling.

13. **Skenario Refactoring Tanpa Downtime**:
    Tim Anda memutuskan untuk memigrasikan deklarasi 5 virtual network subnets dari pola monolitik `count` ke pola `for_each` pada root module aktif yang terhubung dengan ribuan traffic container.
    - *Tugas Anda*: Tuliskan kode mapping blok `moved` (Terraform 1.1+) untuk mentransformasikan alamat state dari index lama: `aws_subnet.internal[0]` (yang merepresentasikan "app-subnet") ke alamat resource baru: `aws_subnet.internal["app-subnet"]`! Terangkan bagaimana engine DAG memproses instruksi ini pada saat evaluasi plan.

---

### 16. Summary

1. **Arsitektur Terpisah (Decoupled Core vs Providers)**:
   Terraform Core bertanggung jawab mengolah sintaks HCL, menyusun Directed Acyclic Graph (DAG), dan menghitung mutasi state (*diff engine*). Komunikasi ke platform vendor diserahkan sepenuhnya ke modul *Provider Plugins* terisolasi yang dihubungkan melalui interface RPC/gRPC berkinerja tinggi.
2. **State Sebagai Titik Tunggal Kebenaran (*Single Source of Truth*)**:
   State memetakan metadata abstrak HCL ke ID sumber daya fisik di cloud vendor. Integritas state dijaga ketat oleh UUID `lineage`, integer inkremental `serial`, serta distributed mutex lock (seperti DynamoDB) untuk mencegah malapetaka *race conditions* dan *state corruption*.
3. **Isolasi Blast Radius Adalah Keharusan Arsitektur**:
   Mengelola ribuan infrastruktur dalam satu root module atau satu file state monolitik adalah anti-pattern enterprise fatal. Arsitektur produksi harus didekomposisi menjadi lapisan-lapisan independen (*Layered Architecture*) yang terhubung melalui data broker abstrak (seperti SSM Parameter Store atau Vault).
4. **HCL2 Enterprise Features Menjamin Robustness**:
   Penggunaan tipe data struktural ketat (`object({...})`), `for_each` dibandingkan `count`, penambahan `precondition` & `postcondition`, serta pemanfaatan blok `moved` memastikan perubahan infrastruktur dapat diaudit, terprediksi (*deterministic*), dan aman dari pemusnahan tidak disengaja.