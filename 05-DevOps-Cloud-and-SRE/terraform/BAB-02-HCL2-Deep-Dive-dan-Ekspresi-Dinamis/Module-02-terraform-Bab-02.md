# BAB 02: HCL2 Deep Dive dan Ekspresi Dinamis
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis Internal HCL2 Engine**: Membedah bagaimana HashiCorp Configuration Language v2 (HCL2) mem-parsing AST (*Abstract Syntax Tree*), mengevaluasi *scope*, serta memetakan struktur data ke tipe data primitif dan kompleks melalui library `zclconf/go-cty`.
2. **Menguasai Metaprogramming & Koleksi Kompleks**: Mengimplementasikan ekspresi `for`, operator splat (`[*]`), fungsi `flatten()`, `merge()`, dan `lookup()` untuk mentransformasi struktur data bersarang (*nested data structures*) menjadi konfigurasi infrastruktur deklaratif yang optimal.
3. **Mengotomatisasi Blok Bersarang via Dynamic Blocks**: Merancang dan mengimplementasikan `dynamic` blocks secara aman dengan iterator kustom, menjaga keterbacaan kode (*readability*), dan menghindari antipola *over-engineering*.
4. **Menerapkan Guardrail Kontrak Data**: Membangun *schema enforcement* tingkat enterprise menggunakan kombinasi `type constraints` mendalam (`object`, `tuple`, `optional()`), custom `validation` blocks, serta `lifecycle` preconditions dan postconditions.
5. **Mengoptimalkan Kinerja Graph Execution**: Mengidentifikasi dan memitigasi dampak komputasi dari ekspresi dinamis yang kompleks terhadap directed acyclic graph (DAG) Terraform untuk mencegah *plan-time degradation* dan *memory bloat*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:

*   **Dasar Siklus Hidup Terraform**: Pemahaman solid terhadap alur `init`, `plan`, `apply`, `refresh`, dan `destroy`.
*   **HCL Fundamental**: Sintaks deklarasi `resource`, `data`, `variable`, `output`, dan `locals`.
*   **Struktur Data & Algoritma Dasar**: Pemahaman tentang Hash Map, List, Set, Direct Addressing, serta manipulasi *key-value*.
*   **Networking & Cloud Architecture Dasar**: Konsep CIDR, Subnetting, Security Group, Route Table, dan multi-tier VPC (AWS/GCP/Azure).
*   **Tooling**: Terraform CLI v1.5.0 atau lebih baru terpasang pada lingkungan lokal.

---

### 3. Concept & Internal Architecture

HCL2 bukan sekadar format konfigurasi statis seperti JSON atau YAML; HCL2 adalah bahasa konfigurasi deklaratif dengan *type system* statis dan *expression engine* berbasis functional programming.

```
+-----------------------------------------------------------------------+
|                       HCL2 Evaluation Pipeline                        |
+-----------------------------------------------------------------------+
|  1. Source Code (.tf)                                                 |
|     |                                                                 |
|     v                                                                 |
|  2. Lexer & Scanner (Token Stream)                                    |
|     |                                                                 |
|     v                                                                 |
|  3. Parser (Abstract Syntax Tree / AST: hcl.File, hcl.Block, etc.)     |
|     |                                                                 |
|     v                                                                 |
|  4. Schema Validation (Provider & Core Schema Check)                  |
|     |                                                                 |
|     v                                                                 |
|  5. Evaluation Context (EvalContext)                                  |
|     +--> Variables, Locals, Resource Attributes (`cty.Value`)         |
|     |                                                                 |
|     v                                                                 |
|  6. Graph Construction & Dynamic Expansion                            |
|     +--> Dynamic blocks expanded into concrete provider arguments     |
|     +--> DAG Walk & Evaluation via `zclconf/go-cty`                  |
+-----------------------------------------------------------------------+
```

#### A. Mesin Tipifikasi: `go-cty`

Di balik layar, Terraform Core menggunakan library Go bernama `zclconf/go-cty` untuk merepresentasikan seluruh nilai. Setiap ekspresi HCL2 dievaluasi menjadi sebuah `cty.Value` yang memiliki:
1.  **Type Signature**: Primitif (`cty.String`, `cty.Number`, `cty.Bool`) atau Kompleks (`cty.List`, `cty.Set`, `cty.Map`, `cty.Tuple`, `cty.Object`).
2.  **Value State**: Nilai riil, `cty.NullVal` (null), atau `cty.UnknownVal` (nilai yang baru diketahui setelah fase apply/runtime, misalnya ID resource cloud yang belum dibuat).

Perbedaan mendasar antara koleksi struktural dan koleksi standar:
*   **List vs Tuple**: `list(string)` mengharuskan setiap elemen bertipe `string`. `tuple([string, number, bool])` mengizinkan elemen dengan tipe berbeda pada indeks tertentu secara deterministik.
*   **Map vs Object**: `map(string)` memiliki elemen dengan nilai homogen dan key bebas bertipe string. `object({ name = string, port = number })` mengunci key yang diwajibkan serta tipe spesifik untuk masing-masing atribut.

#### B. Dynamic Block Lifecycle & AST Expansion

Blok `dynamic` dirancang untuk memecahkan keterbatasan konstruksi atribut bertingkat (*nested blocks* yang didefinisikan oleh provider schema). Sebuah provider schema membedakan:
*   **Arguments**: Nilai yang langsung dipetakan ke atribut (misal: `ami = "ami-123"`).
*   **Blocks**: Struktur sub-deklarasi yang memiliki identitas internal (misal: `ingress {}` dalam `aws_security_group`).

Pada saat parsing AST:
1. Terraform menemukan blok `dynamic "ingress"`.
2. Evaluasi HCL2 membaca ekspresi `for_each`. Jika koleksi belum diketahui (*unknown value* karena bergantung pada resource lain yang belum dibuat), maka blok dynamic tidak dapat diekspansi secara utuh pada fase `plan`, menghasilkan tanda `(known after apply)`.
3. Jika koleksi sudah ter-resolve (*known*), parser mengiterasi koleksi dan menduplikasi sub-blok AST sesuai jumlah iterasi, menyuntikkan variabel iterator (default: nama blok) ke dalam local evaluation context.

---

### 4. Why & What

| Fitur / Konsep | Mengapa Dibutuhkan (Why) | Apa Karakteristiknya (What) |
| :--- | :--- | :--- |
| **First-Class Expressions** | HCL1 mengharuskan pembungkusan string `${var.foo}` yang rentan error dan sulit dibaca. | HCL2 mengevaluasi variabel, fungsi, dan operasi aritmatika/logika langsung tanpa interpolasi pembungkus. |
| **`for` Expressions** | Menghindari duplikasi deklarasi resource saat mentransformasi list of objects menjadi maps untuk `for_each`. | Konstruksi fungsional seperti list/map comprehension pada Python: `[for x in list : x.id]` atau `{for x in list : x.key => x.val}`. |
| **Dynamic Blocks** | Provider tertentu mendefinisikan konfigurasi kompleks sebagai *nested blocks*, bukan argument map/list. Menghindari copy-paste block puluhan kali. | Meta-argument yang menginstruksikan Terraform Core untuk menghasilkan *repeating structural blocks* berdasarkan koleksi data. |
| **Structural Constraints (`object`, `optional()`)** | Mencegah bug integrasi di level root module dengan memvalidasi skema payload data sedini mungkin. | Type system yang memvalidasi *shape* data input secara ketat, memungkinkan deklarasi default value per-atribut via `optional(type, default)`. |
| **Preconditions & Postconditions** | Mengisolasi kegagalan pada batasan bisnis (*business invariant*) sebelum modifikasi infrastruktur terlanjur dieksekusi. | Kontrak lifecycle eksekusi yang memeriksa keabsahan *state* sebelum (pre) atau setelah (post) resource dieksekusi oleh provider engine. |

---

### 5. How: Workflow Detail

Proses evaluasi ekspresi dinamis saat eksekusi CLI mengikuti alur berikut:

```
[CLI: terraform plan]
        |
        v
[Phase 1: Decode Configurations]
        |---> Bind Variables to Type Constraints
        |---> Validate variable `validation {}` blocks
        v
[Phase 2: Local & Expression Evaluation]
        |---> Compute `locals {}` (Flattening, Merging, Conditionals)
        |---> Evaluate splat expressions & for loops
        v
[Phase 3: Schema Conformance & Graph Construction]
        |---> Match attributes against Provider Schema
        |---> Resolve `dynamic` blocks into Provider Blocks
        |---> Construct DAG (Resource Nodes, Variable Nodes, Provider Nodes)
        v
[Phase 4: Precondition Check]
        |---> Evaluate `lifecycle.precondition` on graph traversal
        |     (Halt if condition is false)
        v
[Phase 5: State Diff Generation]
        |---> Interrogate Cloud APIs via Provider Plugin (RPC)
        |---> Evaluate `lifecycle.postcondition` against API responses
        v
[Output Execution Plan]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Kompiler
Bayangkan Anda sedang menulis fungsi pada bahasa berorientasi objek yang menerima input JSON tidak beraturan.
*   **HCL1** ibarat Anda mem-parse JSON secara manual sebagai raw string, lalu melakukan `substring()` dan *type casting* manual yang rawan `NullPointerException`.
*   **HCL2 Engine** ibarat menggunakan framework modern dengan *strict serialization* (seperti Pydantic di Python atau Serde di Rust). Variabel di-deserialize ke dalam *struct* dengan tipe data ketat.
*   **Dynamic Blocks** bertindak seperti generator *macro*: alih-alih Anda menulis kode boilerplate berulang-ulang, macro akan mengiterasi array data dan menyuntikkan template AST secara programatis sebelum AST tersebut diproses oleh execution engine.

#### Diagram Transformasi Data AST

```
Raw Input Data (Array of Subnet Definitions):
[
  { name = "web", az = "us-east-1a", cidr = "10.0.1.0/24" },
  { name = "api", az = "us-east-1b", cidr = "10.0.2.0/24" }
]
                             |
                             v
              HCL2 `for` Expression Transformation:
       { for s in var.subnets : s.name => s if s.az != "us-east-1c" }
                             |
                             v
Evaluated Map (CTY Object Value Context):
{
  "web" = { az = "us-east-1a", cidr = "10.0.1.0/24" },
  "api" = { az = "us-east-1b", cidr = "10.0.2.0/24" }
}
                             |
                             v
           Directed Acyclic Graph (DAG) Expansion:
         +-----------------------------------------+
         |  aws_subnet.this["web"]                 |
         |  (CIDR: 10.0.1.0/24, AZ: us-east-1a)    |
         +-----------------------------------------+
         |  aws_subnet.this["api"]                 |
         |  (CIDR: 10.0.2.0/24, AZ: us-east-1b)    |
         +-----------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Ekspresi Koleksi & Transformasi HCL2

```hcl
# Deklarasi input collections
locals {
  raw_ports = [80, 443, 8080, 80, 22, 9000]

  # 1. Deduplikasi menggunakan toset()
  unique_ports = toset(local.raw_ports)

  # 2. List Comprehension dengan filter kondisional
  secure_ports = [for port in local.unique_ports : port if port != 22]

  # 3. Map Comprehension mentransformasikan list menjadi key-value
  port_metadata = {
    for port in local.secure_ports : "port_${port}" => {
      number    = port
      is_tls    = port == 443 ? true : false
      log_level = port > 1024 ? "DEBUG" : "INFO"
    }
  }

  # 4. Splat Expression untuk mengekstrak atribut tertentu
  all_numbers = local.secure_ports[*]
}

output "processed_ports" {
  value = local.port_metadata
}
```

#### B. Practical Example: Production Security Group Engine dengan Dynamic Block & Strict Contracts

Konfigurasi berikut mendefinisikan modul security group dengan parsing aturan berlapis, validasi input otomatis, pemecahan range IP menggunakan `flatten`, dan penerapan `precondition`.

```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "security_group_matrix" {
  type = object({
    name        = string
    description = string
    vpc_id      = string
    rules = list(object({
      description = string
      port        = number
      protocol    = string
      cidrs       = list(string)
      monitoring  = optional(bool, false)
    }))
  })
  description = "Spesifikasi konfigurasi Security Group perusahaan."

  # Custom validation untuk integritas data
  validation {
    condition = (
      can(regex("^sg-[a-z0-9]+$", var.security_group_matrix.vpc_id)) || 
      can(regex("^vpc-[a-z0-9]+$", var.security_group_matrix.vpc_id))
    )
    error_message = "VPC ID harus valid dan diawali dengan 'vpc-' atau 'sg-'."
  }

  validation {
    condition = alltrue([
      for r in var.security_group_matrix.rules : r.port >= 1 && r.port <= 65535
    ])
    error_message = "Seluruh port rule harus berada di rentang valid (1 - 65535)."
  }
}

locals {
  # Ekstraksi dan sanitasi input rule
  normalized_rules = [
    for rule in var.security_group_matrix.rules : {
      description = rule.description
      port        = rule.port
      protocol    = lower(rule.protocol)
      cidrs       = distinct(rule.cidrs)
      monitoring  = rule.monitoring
    }
  ]
}

resource "aws_security_group" "matrix_sg" {
  name        = var.security_group_matrix.name
  description = var.security_group_matrix.description
  vpc_id      = var.security_group_matrix.vpc_id

  # Dynamic block dengan custom iterator
  dynamic "ingress" {
    for_each = local.normalized_rules
    iterator = rule_item
    content {
      description = rule_item.value.description
      from_port   = rule_item.value.port
      to_port     = rule_item.value.port
      protocol    = rule_item.value.protocol
      cidr_blocks = rule_item.value.cidrs
    }
  }

  egress {
    description = "Default deny all egress unless explicitly configured"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    # Memastikan security group tidak dibuat jika CIDR 0.0.0.0/0 diberikan ke port manajemen (SSH/RDP)
    precondition {
      condition = !anytrue(flatten([
        for r in var.security_group_matrix.rules : [
          for c in r.cidrs : contains([22, 3389], r.port) && c == "0.0.0.0/0"
        ]
      ]))
      error_message = "PELANGGARAN KEAMANAN: CIDR 0.0.0.0/0 dilarang keras untuk port 22 (SSH) atau 3389 (RDP)."
    }
  }

  tags = {
    Name      = var.security_group_matrix.name
    ManagedBy = "Terraform-Enterprise-Core"
  }
}
```

---

### 8. Real World Case Study: Enterprise Scale

#### Skenario Kasus
Bank Mega Digital sedang bermigrasi ke AWS Transit Gateway (TGW) untuk menghubungkan 60 VPC microservices ke Shared Services VPC. Setiap VPC memiliki kebutuhan rute yang berbeda-beda (*inspection*, *direct-peered*, atau *egress-only*).

#### Masalah Arsitektur
Sebelumnya, insinyur cloud menduplikasi blok resource `aws_route` satu per satu. Saat jumlah rute mencapai 400+, terjadi:
1.  **State File Bloat**: Pembengkakan ukuran file state sebesar 45 MB.
2.  **API Rate Limiting**: `terraform plan` memakan waktu 18 menit karena ribuan panggilan AWS DescribeRoute API secara linear.
3.  **Human Error**: Konflik rute tumpang tindih (*overlapping CIDR*) lolos ke staging environment karena tidak adanya schema validation engine di level kode HCL.

#### Solusi Menggunakan HCL2 Metaprogramming
Membangun modul Route Table Generator terpusat yang:
1.  Mengonsumsi matriks konfigurasi hierarkis (VPC -> Route Tables -> Routes).
2.  Memvalidasi benturan CIDR (*non-overlapping*) sebelum eksekusi via HCL `validation`.
3.  Menggunakan *Projection Expression* dan `flatten()` untuk memetakan matriks 3 dimensi menjadi *single-dimensional map* yang deterministik, kompatibel dengan `for_each` tingkat resource.

```hcl
variable "network_manifest" {
  type = map(object({
    vpc_id = string
    route_tables = map(object({
      routes = list(object({
        destination_cidr = string
        target_tgw_id    = optional(string)
        target_nat_id    = optional(string)
      }))
    }))
  }))
}

locals {
  # Flatten matriks bersarang 3 lapis: Manifest -> VPC -> Route Table -> Route
  flattened_routes = merge([
    for vpc_key, vpc_val in var.network_manifest : merge([
      for rt_key, rt_val in vpc_val.route_tables : {
        for idx, route in rt_val.routes :
        "${vpc_key}.${rt_key}.${route.destination_cidr}" => {
          route_table_key  = "${vpc_key}.${rt_key}"
          destination_cidr = route.destination_cidr
          target_tgw_id    = route.target_tgw_id
          target_nat_id    = route.target_nat_id
        }
      }
    ]...)
  ]...)
}

# Pembuatan rute terkontrol dengan for_each
resource "aws_route" "enterprise_routes" {
  for_each = local.flattened_routes

  # Asumsi modul ini menerima ID Route Table dari map dependency
  route_table_id         = data.aws_route_table.resolved[each.value.route_table_key].id
  destination_cidr_block = each.value.destination_cidr

  transit_gateway_id = each.value.target_tgw_id
  nat_gateway_id     = each.value.target_nat_id

  lifecycle {
    precondition {
      condition     = !(each.value.target_tgw_id != null && each.value.target_nat_id != null)
      error_message = "Route ke ${each.value.destination_cidr} tidak boleh mendefinisikan TGW dan NAT Gateway secara bersamaan."
    }
  }
}
```

#### Hasil
*   Waktu `terraform plan` berkurang dari 18 menit menjadi 1 menit 45 detik.
*   Duplikasi kode tereliminasi sebesar 82%.
*   Deteksi dini konflik parameter sebelum Terraform mengirim payload ke AWS API via runtime `precondition`.

---

### 9. Trade-offs: Analisis Komparasi

| Parameter Arsitektur | Dynamic Blocks & Metaprogramming | Standalone Granular Resources |
| :--- | :--- | :--- |
| **Parsing & Graph Performance** | Penambahan kalkulasi AST & ekspansi memory in-memory pada Terraform CLI. Namun, resource node pada DAG lebih terkonsolidasi. | Sangat ringan pada parser AST, namun memperbesar node DAG secara linear sehingga memperlambat kalkulasi dependency walk. |
| **Blast Radius** | **Tinggi**. Mengubah logika lokal pada `for_each` atau dynamic block dapat mengubah struktur puluhan resource sekaligus secara tidak sengaja. | **Rendah**. Modifikasi pada resource terpisah hanya berdampak langsung pada target tersebut. |
| **Maintainability & DRY** | Mengurangi repetisi kode secara masif. Konfigurasi sentral cukup diubah dari file variabel. | Pelanggaran prinsip DRY. Modifikasi atribut mengharuskan find-and-replace di banyak file. |
| **Troubleshooting & Diff Clarity** | Output `terraform plan` dapat menjadi sangat panjang dan sulit dilacak jika terjadi cascading replacement (*force new resource*). | Diff bersih dan jelas. Setiap baris rencana perubahan langsung memetakan blok resource statis aslinya. |
| **Flexibility vs Complexity** | Sangat fleksibel, namun berisiko masuk ke jurang *code obfuscation* jika logika `flatten/merge` bertingkat lebih dari 3 lapis. | Kaku, redundan, namun ramah bagi engineer junior (*low cognitive overhead*). |

---

### 10. Common Mistakes & Troubleshooting

#### Kasus 1: Ingress/Egress Dynamic Block Menggunakan List Kosong Alih-alih Menghindari Blok
*   **Gejala**: Security Group kehilangan seluruh inline ingress rules, atau justru me-reset rule yang dikelola di luar state.
*   **Penyebab**: Memberikan nilai `for_each = []` pada sub-blok dynamic menyebabkan provider mengevaluasi blok tersebut sebagai instruksi deklaratif "harus bernilai kosong" alih-alih mengabaikannya.
*   **Solusi**: Pastikan apakah resource menggunakan standalone resource (`aws_security_group_rule`) atau inline dynamic block. Hindari mencampur keduanya pada satu target security group.

#### Kasus 2: Error "The 'for_each' value depends on resource attributes that cannot be determined until apply"
*   **Gejala**:
    ```
    Error: Invalid for_each argument
    The "for_each" map includes keys derived from resource attributes that cannot be determined until apply.
    ```
*   **Penyebab**: Menggunakan output runtime (misalnya ID subnet baru) sebagai *key* pada ekspresi `for_each`. Kunci dari map/set pada `for_each` harus sudah diketahui secara deterministik (*known*) pada fase refresh/plan.
*   **Solusi**: Gunakan identifier stabil (seperti logical names/slugs dari variabel input) sebagai *key*, dan gunakan atribut dinamis/runtime hanya sebagai *value*.

```hcl
# SALAH: Subnet ID belum ada pada fase plan awal
resource "aws_route" "bad" {
  for_each       = toset([for s in aws_subnet.new : s.id])
  route_table_id = aws_route_table.main.id
}

# BENAR: Menggunakan logical key yang sudah pasti (misal: "subnet-a", "subnet-b")
resource "aws_route" "good" {
  for_each       = var.subnet_manifest # Key bernilai statis dari konfigurasi
  route_table_id = aws_route_table.main.id
  subnet_id      = aws_subnet.new[each.key].id
}
```

#### Kasus 3: Type Mismatch pada Ternary Operator
*   **Gejala**: `Error: Inconsistent conditional result types`.
*   **Penyebab**: Percabangan `condition ? true_val : false_val` mengembalikan tipe data struktural yang tidak setara (misalnya branches mengembalikan satu `object` dengan 3 key dan cabang lain dengan 4 key).
*   **Solusi**: Pastikan kedua cabang mengembalikan skema tipe data yang identik secara struktural atau bungkus kedua tipe dengan konversi eksplisit.

---

### 11. Best Practices & Production Checklist

- [ ] **Strict Typing Obligatory**: Dilarang menggunakan tipe `any` pada root module. Gunakan `object({...})` dengan batasan tipe yang eksplisit.
- [ ] **Opt-in Attributes dengan Default**: Manfaatkan `optional(type, default_value)` untuk atribut sekunder agar parameter input tetap ringkas.
- [ ] **Validasi Semantik Input**: Tulis minimal satu blok `validation` untuk setiap variabel kompleks guna mencegah input string kosong, CIDR invalid, atau port di luar rentang.
- [ ] **Kunci for_each Deterministik**: Jangan pernah memetakan index list (`0, 1, 2`) ke dalam `for_each`. Jika urutan list berubah, Terraform akan menghancurkan dan membangun ulang resource secara keliru. Gunakan string unique identifier sebagai key.
- [ ] **Batas Kompleksitas Ekspresi**: Batasi fungsi transformasi bersarang (*nested functional operations*) maksimal 2 layer pada `locals`. Jika butuh transformasi lebih rumit, pisahkan ke dalam beberapa `locals` intermediate terpisah untuk mempermudah debugging AST.
- [ ] **Isolasi State Blast Radius**: Jangan satukan puluhan dynamic blocks yang mengontrol infrastruktur global ke dalam satu root state. Pisahkan state berdasarkan boundary domain arsitektur.

---

### 12. Hands-on Practice

Implementasikan modul enterprise yang dapat dikompilasi secara nyata. Simpan seluruh file di bawah direktori `hands-on/m02/`.

#### Struktur Direktori
```
hands-on/m02/
├── versions.tf
├── variables.tf
├── locals.tf
├── main.tf
├── outputs.tf
└── terraform.tfvars
```

#### `versions.tf`
```hcl
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
  region = var.aws_region
}
```

#### `variables.tf`
```hcl
variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "Region AWS untuk penempatan resource."
}

variable "environment" {
  type        = string
  description = "Environment identifier (prd, stg, dev)."

  validation {
    condition     = contains(["prd", "stg", "dev"], var.environment)
    error_message = "Environment harus salah satu dari: prd, stg, dev."
  }
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block utama VPC."

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "Parameter vpc_cidr harus berupa format CIDR IPv4 yang valid."
  }
}

variable "tier_definitions" {
  type = map(object({
    cidr_offset  = number
    az_index     = number
    is_public    = optional(bool, false)
    egress_ports = list(number)
  }))
  description = "Definisi subnets tier dan policy port egress."
}
```

#### `locals.tf`
```hcl
locals {
  # Mengambil daftar availability zones yang tersedia
  azs = ["${var.aws_region}a", "${var.aws_region}b", "${var.aws_region}c"]

  # Hitung CIDR subnet secara dinamis berdasarkan kalkulasi cidrsubnet
  computed_subnets = {
    for tier_name, tier_config in var.tier_definitions : tier_name => {
      cidr_block = cidrsubnet(var.vpc_cidr, 4, tier_config.cidr_offset)
      az         = local.azs[tier_config.az_index]
      is_public  = tier_config.is_public
      ports      = distinct(tier_config.egress_ports)
    }
  }
}
```

#### `main.tf`
```hcl
resource "aws_vpc" "enterprise_vpc" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "${var.environment}-enterprise-vpc"
    Environment = var.environment
  }
}

resource "aws_subnet" "tiers" {
  for_each = local.computed_subnets

  vpc_id                  = aws_vpc.enterprise_vpc.id
  cidr_block              = each.value.cidr_block
  availability_zone       = each.value.az
  map_public_ip_on_launch = each.value.is_public

  tags = {
    Name        = "${var.environment}-${each.key}-subnet"
    Tier        = each.key
    Environment = var.environment
  }

  lifecycle {
    postcondition {
      condition     = self.availability_zone == each.value.az
      error_message = "Subnet dibuat pada Availability Zone yang salah dari yang ditargetkan."
    }
  }
}

resource "aws_security_group" "dynamic_tier_sg" {
  name        = "${var.environment}-tier-firewall"
  description = "Security group dengan port egress berbasis iterasi tier"
  vpc_id      = aws_vpc.enterprise_vpc.id

  # Dynamic block ekspansi untuk port egress
  dynamic "egress" {
    for_each = flatten([
      for tier_name, tier_data in local.computed_subnets : [
        for port in tier_data.ports : {
          tier = tier_name
          port = port
        }
      ]
    ])

    content {
      description = "Egress port ${egress.value.port} for tier ${egress.value.tier}"
      from_port   = egress.value.port
      to_port     = egress.value.port
      protocol    = "tcp"
      cidr_blocks = [local.computed_subnets[egress.value.tier].cidr_block]
    }
  }

  tags = {
    Name = "${var.environment}-sg"
  }
}
```

#### `outputs.tf`
```hcl
output "vpc_id" {
  value       = aws_vpc.enterprise_vpc.id
  description = "VPC ID yang berhasil dibuat."
}

output "subnet_matrix" {
  value = {
    for k, v in aws_subnet.tiers : k => {
      id         = v.id
      cidr_block = v.cidr_block
      az         = v.availability_zone
    }
  }
  description = "Metadata subnet yang dihasilkan dari HCL2 projection."
}
```

#### `terraform.tfvars`
```hcl
aws_region  = "us-east-1"
environment = "prd"
vpc_cidr    = "10.100.0.0/16"

tier_definitions = {
  web = {
    cidr_offset  = 1
    az_index     = 0
    is_public    = true
    egress_ports = [80, 443]
  }
  app = {
    cidr_offset  = 2
    az_index     = 1
    is_public    = false
    egress_ports = [8080, 5432]
  }
  db = {
    cidr_offset  = 3
    az_index     = 2
    is_public    = false
    egress_ports = [5432]
  }
}
```

#### Langkah Eksekusi Hands-on
```bash
# 1. Masuk ke direktori latihan
cd hands-on/m02/

# 2. Inisialisasi provider
terraform init

# 3. Lakukan validasi sintaks dan skema
terraform validate

# 4. Amati graph execution dan evaluasi ekspresi dinamis
terraform plan

# 5. Eksekusi infrastruktur
terraform apply -auto-approve

# 6. Periksa output hasil evaluasi map projection
terraform output subnet_matrix

# 7. Bersihkan resource kembali
terraform destroy -auto-approve
```

---

### 13. Exercise

#### Level: Easy
Diberikan sebuah variabel berupa list IP address: `["10.0.0.1", "192.168.1.1", "10.0.0.2", "172.16.0.1"]`.
Tuliskan blok `locals` dengan ekspresi `for` yang menyaring dan hanya menghasilkan IP address yang diawali dengan segmen `"10.0."`.

#### Level: Medium
Tuliskan resource `aws_security_group` yang memanfaatkan blok `dynamic "ingress"` untuk mengurai input variabel list of objects berikut:
```hcl
variable "firewall_rules" {
  type = list(object({
    ports       = list(number)
    cidr_blocks = list(string)
  }))
}
```
*Syarat*: Gunakan fungsi `flatten()` pada ekspresi `for_each` di dalam blok dynamic tersebut agar setiap kombinasi satu port dan kumpulan CIDR menghasilkan blok `ingress` tersendiri.

#### Level: Hard
Rancang sebuah modul yang menerima variabel kompleks berupa konfigurasi *multi-account route propagation*. Modul harus:
1. Menerima map dari VPC peering configurations yang memiliki nested list route targets.
2. Memvalidasi bahwa tidak ada route target yang memiliki `destination_cidr = "0.0.0.0/0"` di dalam data input menggunakan block `validation`.
3. Menggunakan `lifecycle.precondition` pada resource untuk mengecek apakah panjang key dari map input minimal berjumlah 2 (memastikan high availability peering).

---

### 14. Challenge

Anda adalah Principal DevOps Engineer pada sebuah platform SaaS berskala besar. Sistem Anda membutuhkan *Dynamic Service Endpoint Provisioner*.

**Spesifikasi Kasus**:
* Anda menerima satu payload data hierarkis terpadu yang memuat deklarasi 15 layanan microservices. Masing-masing layanan dapat mengekspos sejumlah *endpoints* HTTP/gRPC dengan variasi port, environment variable, dan health check paths yang berbeda-beda.
* Sebagian microservices bersifat `internal` (hanya boleh terhubung ke subnet privat) dan sebagian bersifat `public` (terhubung ke public ALB).
* **Tantangan**: 
  1. Anda dilarang mendeklarasikan `aws_lb_target_group` dan `aws_lb_listener_rule` secara hardcoded satu per satu. Seluruhnya harus dibangun dari satu resource terpusat menggunakan ekspresi transformasi HCL2 tingkat lanjut (`flatten`, `merge`, `for` loop filter, dan type projection).
  2. Implementasikan mekanisme **assertion** menggunakan `lifecycle.precondition` dan `postcondition`: Jika service bertipe `public` tetapi health check path-nya mengarah ke endpoint debug (`/debug/*` atau `/admin/*`), proses plan/apply harus langsung digagalkan seketika oleh Terraform Core engine sebelum API request menyentuh cloud provider.
  3. Konfigurasi harus sepenuhnya aman dari kondisi `drift` dan tidak memicu siklus `recreate` acak ketika urutan elemen array dalam variabel masukan diubah oleh tim pengembang.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. **Apa perbedaan mendasar antara `tuple` dan `list` pada sistem tipe data HCL2?**
   * A. `list` dapat menampung elemen dengan tipe berbeda, sedangkan `tuple` harus homogen.
   * B. `list` memiliki ukuran tetap, sedangkan `tuple` dinamis.
   * C. `list` mensyaratkan tipe data elemen seragam (homogen), sedangkan `tuple` mengizinkan urutan elemen dengan tipe data berbeda (heterogen).
   * D. Tidak ada perbedaan, keduanya adalah sinonim di HCL2.

2. **Fungsi utama dari meta-argument `dynamic` pada HCL2 adalah:**
   * A. Membuat resource secara kondisional berdasarkan boolean flag.
   * B. Menghasilkan sub-blok bersarang (*nested blocks*) secara dinamis berdasarkan iterasi koleksi.
   * C. Mengubah nilai variabel saat fase runtime eksekusi cloud.
   * D. Mempercepat proses download provider plugin.

3. **Ekspresi splat `aws_instance.worker[*].id` setara fungsinya dengan:**
   * A. `[for x in aws_instance.worker : x.id]`
   * B. `{for x in aws_instance.worker : x => x.id}`
   * C. `aws_instance.worker.id`
   * D. `toset(aws_instance.worker.id)`

4. **Kapan blok `validation` pada sebuah `variable` dievaluasi oleh Terraform?**
   * A. Hanya saat perintah `terraform destroy` dijalankan.
   * B. Pada fase awal evaluasi configuration loading saat `terraform plan` atau `terraform apply` dimulai.
   * C. Setelah cloud provider selesai membuat resource.
   * D. Hanya saat file `.tfstate` diperbarui.

5. **Apa fungsi dari atribut `iterator` di dalam sebuah blok `dynamic`?**
   * A. Menghentikan looping saat kondisi tertentu terpenuhi.
   * B. Mengatur urutan sorting dari ascending ke descending.
   * C. Menentukan nama variabel sementara yang merepresentasikan elemen yang sedang diiterasi (menggantikan nama default dari blok dynamic).
   * D. Menentukan batas maksimal eksekusi loop.

---

#### Intermediate (5 Soal)
6. **Perhatikan ekspresi berikut:**
   ```hcl
   { for k, v in var.apps : k => v.port if v.active }
   ```
   **Apa hasil dari ekspresi di atas jika `var.apps` adalah sebuah map?**
   * A. List berisi port dari aplikasi yang aktif.
   * B. Map baru yang hanya menyertakan aplikasi dengan `active = true`, dengan nilai berupa nomor port-nya.
   * C. Tuple berisi seluruh key dan value dari `var.apps`.
   * D. Error karena ekspresi `if` dilarang di dalam map comprehension.

7. **Mengapa penggunaan output resource yang belum dibuat dilarang sebagai key pada ekspresi `for_each`?**
   * A. Karena cloud provider menolak string yang dihasilkan secara dinamis.
   * B. Karena HCL2 engine membutuhkan key `for_each` yang statis dan deterministik pada fase evaluasi graph sebelum modifikasi resource dijalankan.
   * C. Karena `for_each` hanya menerima tipe data integer angka murni.
   * D. Karena hal tersebut akan otomatis menghapus file `.tfstate`.

8. **Apa perbedaan antara `lifecycle.precondition` dan `lifecycle.postcondition`?**
   * A. `precondition` dievaluasi sebelum resource dievaluasi/dibuat, sedangkan `postcondition` dievaluasi setelah resource selesai dibuat atau di-refresh dari data state.
   * B. `precondition` hanya untuk data source, sedangkan `postcondition` hanya untuk resource.
   * C. `precondition` memicu warning, sedangkan `postcondition` memicu critical error.
   * D. `precondition` dijalankan di sisi client, `postcondition` dieksekusi di sisi remote cloud API.

9. **Fungsi bawaan HCL manakah yang paling tepat digunakan untuk meratakan matriks list of lists multidimensi menjadi satu list tunggal satu dimensi?**
   * A. `compact()`
   * B. `flatten()`
   * C. `concat()`
   * D. `coalesce()`

10. **Bagaimana cara mendefinisikan nilai default pada atribut bertingkat di dalam `object` type constraint sejak Terraform 1.3?**
    * A. Menggunakan blok `default_value {}` di bawah deklarasi variabel.
    * B. Menggunakan fungsi `coalesce()` pada locals.
    * C. Menggunakan modifier `optional(type, default)`.
    * D. Atribut dalam object constraint tidak dapat memiliki default value parsial.

---

#### Production Scenarios (3 Soal)

11. **Skenario 1**:
    Tim Anda mengalami kendala di mana perintah `terraform plan` pada modul network memakan waktu hingga 25 menit. Modul tersebut menggunakan satu resource `aws_security_group` yang memuat blok `dynamic "ingress"` dengan 450 baris CIDR yang dihitung secara fungsional menggunakan nested loop `for` dan parsing regex.
    **Langkah remediasi teknis manakah yang paling arsitektural dan tepat sasaran?**
    * A. Menaikkan batas ukuran memori pada mesin pelaksana (runner) CI/CD.
    * B. Menghilangkan seluruh dynamic blocks dan mendekomposisi aturan ke dalam standalone resource `aws_security_group_rule` yang dikelompokkan berdasarkan port/protokol, serta memisahkan perhitungannya dari parsing regex inline.
    * C. Menjalankan Terraform dengan parameter `-parallelism=100`.
    * D. Mengubah provider AWS ke versi legacy HCL1.

12. **Skenario 2**:
    Sebuah tim audit mewajibkan bahwa semua bucket Amazon S3 di environment produksi harus memiliki enkripsi berbasis AWS KMS (`aws:kms`), dan dilarang keras menggunakan enkripsi default `AES256`.
    **Di manakah letak implementasi HCL2 guardrail yang paling aman agar plan langsung gagal jika ada engineer yang mencoba menggunakan `AES256`?**
    * A. Pada blok `variable "encryption_algorithm"` menggunakan blok `validation`.
    * B. Pada resource `aws_s3_bucket_server_side_encryption_configuration` menggunakan blok `lifecycle.precondition` atau `postcondition` yang memeriksa atribut SSE algorithm.
    * C. Pada file output modul menggunakan ternary operator.
    * D. Pada file `terraform.tfvars`.

13. **Skenario 3**:
    Anda memiliki data input berikut:
    ```hcl
    variable "workloads" {
      type = map(object({
        env   = string
        nodes = list(string)
      }))
    }
    ```
    Anda ingin membuat resource cluster instances menggunakan `for_each`. Instance butuh identifier yang stabil tanpa memicu re-creation massal ketika ada satu node yang disisipkan di awal list.
    **Transformasi `locals` manakah yang paling deterministik dan memenuhi kriteria produksi?**
    * A.
      ```hcl
      locals {
        instances = flatten([
          for app_name, app_val in var.workloads : [
            for idx, node in app_val.nodes : {
              id = "${app_name}-${idx}"
            }
          ]
        ])
      }
      ```
    * B.
      ```hcl
      locals {
        instances = merge([
          for app_name, app_val in var.workloads : {
            for node in app_val.nodes :
            "${app_name}/${node}" => {
              app  = app_name
              node = node
              env  = app_val.env
            }
          }
        ]...)
      }
      ```
    * C.
      ```hcl
      locals {
        instances = {
          for app_name, app_val in var.workloads :
          app_name => app_val.nodes[0]
        }
      }
      ```
    * D.
      ```hcl
      locals {
        instances = toset(var.workloads[*].nodes)
      }
      ```

---

#### Kunci Jawaban Evaluasi

1. **C** — `list` mengharuskan tipe homogen (`list(string)`), sedangkan `tuple` mengizinkan elemen dengan skema heterogen pada urutan yang pasti (`tuple([string, number])`).
2. **B** — `dynamic` digunakan khusus untuk mereplikasi blok konfigurasi bersarang (*nested blocks*) berdasarkan isi koleksi.
3. **A** — Legacy Splat maupun Full Splat operator `[*].id` adalah padanan sintaks fungsional untuk list comprehension `[for x in list : x.id]`.
4. **B** — Validasi variabel dievaluasi sangat awal saat proses decoding konfigurasi berlangsung, sebelum dependency graph diselesaikan.
5. **C** — Secara default iterator dinamai sesuai nama blok dynamic, namun `iterator = custom_name` memungkinkan kustomisasi identifier variabel iterasi.
6. **B** — Sintaks `{ for k, v in map : k => v.port if v.active }` adalah standar map comprehension yang memfilter key-value berdasarkan kondisi boolean.
7. **B** — Kunci dari `for_each` menentukan identitas node pada Directed Acyclic Graph (DAG). Jika nilainya baru diketahui pada fase apply (*unknown*), Terraform tidak dapat memetakan dependency graph saat perencanaan (*plan*).
8. **A** — `precondition` dievaluasi sebelum blok dieksekusi (memvalidasi input/state dependensi), sedangkan `postcondition` memverifikasi hasil state setelah modifikasi resource dilakukan oleh provider.
9. **B** — `flatten()` menerima list of lists dan meratakannya menjadi array linear satu dimensi.
10. **C** — Sejak HCL2 pada Terraform 1.3, deklarasi atribut opsional pada struct dilakukan dengan `optional(tipe, default_value)`.
11. **B** — 450 dynamic blocks dalam satu resource menyebabkan beban ekstrim pada AST parser memory dan provider payload size. Menguraikannya menjadi standalone resource individual membagi beban komputasi dan memperjelas diff execution graph.
12. **B** — `lifecycle` precondition/postcondition mengunci kepatuhan langsung pada level resource spesifik terlepas dari mana nilai variabel tersebut dialirkan.
13. **B** — Menggunakan gabungan natural key string `${app_name}/${node}` sebagai map key menjamin determinisme unik. Opsi A buruk karena menggunakan indeks array yang rentan shift-recreation jika urutan array berubah.

---

### 16. Summary

*   **HCL2 Core Architecture**: HCL2 mengonversi konfigurasi mentah menjadi AST yang diverifikasi secara ketat terhadap *schema provider* menggunakan sistem tipe `zclconf/go-cty`.
*   **Collection Transformations**: Penggunaan ekspresi `for`, filter `if`, operator splat `[*]`, dan fungsi transformasi seperti `flatten()` serta `merge()` adalah pilar utama metaprogramming untuk mengelola topologi infrastruktur modern berskala besar.
*   **Dynamic Blocks Control**: Blok `dynamic` memecahkan masalah repetisi pada atribut bertingkat (*nested blocks*), namun harus diterapkan secara bijak untuk mencegah *graph calculation explosion* dan pembengkakan file state.
*   **Enforcement & Guardrails**: Penerapan `object` validation yang dikombinasikan dengan `optional(default)`, serta `lifecycle` assertions (`precondition` dan `postcondition`) memungkinkan implementasi *defensive infrastructure engineering* langsung di level bahasa sebelum instruksi diteruskan ke cloud provider.