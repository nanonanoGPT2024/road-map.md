## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `DEV-FOUND-08-01`
* **Nama Modul**: Infrastructure as Code (IaC) Fundamentals & Architecture
* **Kategori**: `01-Core-Foundations`
* **Prasyarat**: 
  * Pemahaman dasar sistem operasi Linux (`DEV-FOUND-01`)
  * Penguasaan Version Control System / Git (`DEV-FOUND-04`)
  * Pemahaman dasar jaringan komputer dan protokol internet (`DEV-FOUND-06`)
* **Tingkat Kesulitan**: Intermediate (DevOps Beginner Track)
* **Estimasi Waktu**: 6–8 Jam Pembelajaran Mandiri / Praktikum
* **Target Tools**: Terraform / OpenTofu, Git, Docker (sebagai target provider lokal)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis (C4)** perbedaan mendasar antara pengelolaan infrastruktur tradisional (ClickOps / Imperatif) dengan paradigma modern *Infrastructure as Code* (Deklaratif).
2. **Menjelaskan (C2)** siklus hidup state management, konsep konvergensi (*reconciliation loop*), serta prinsip *idempotency* dalam orkestrasi infrastruktur.
3. **Mengimplementasikan (C3)** pipeline penyediaan (*provisioning*) infrastruktur sederhana secara otomatis menggunakan sintaks HashiCorp Configuration Language (HCL).
4. **Mengevaluasi (C5)** dampak *configuration drift* dan memilih strategi mitigasi yang tepat melalui pemeriksaan state dan audit VCS.
5. **Mendesain (C6)** struktur modul IaC modular yang aman, mematuhi standar *least privilege*, serta memisahkan variabel sensitif secara terenkripsi.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       [ INFRASTRUCTURE AS CODE ]
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         ▼                                                   ▼
  [ Paradigma & Desain ]                             [ Siklus Hidup Eksekusi ]
   ├── Deklaratif vs Imperatif                        ├── Desired State (HCL Code)
   ├── Idempotency                                    ├── Actual State (Cloud/Platform)
   ├── Immutable vs Mutable                           ├── State File (Mapping Core)
   └── Anti-Pattern: ClickOps                         └── Reconciliation Loop (Drift Mitigation)
         │                                                   │
         └─────────────────────────┬─────────────────────────┘
                                   ▼
                        [ Praktik Operasional ]
                         ├── State Locking (Concurreny Control)
                         ├── Modularity & Blast Radius Reduction
                         └── Secret Management & Security Hygiene
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Sebelum munculnya IaC, infrastruktur dikelola melalui GUI web console penyedia cloud atau eksekusi serangkaian shell script ad-hoc tanpa pelacakan versi. Metode ini lazim disebut sebagai **ClickOps**. 

ClickOps membawa risiko sistemik dalam rekayasa perangkat lunak modern:

1. **Snowflake Servers**: Infrastruktur menjadi unik dan tidak dapat direproduksi. Ketika server down, teknisi tidak mengetahui konfigurasi pasti yang pernah dipasang secara manual.
2. **Configuration Drift**: Perbedaan status antara environment Development, Staging, dan Production yang memicu kegagalan deployment tanpa indikasi jelas.
3. **Ketiadaan Audit Trail**: Ketiadaan jejak digital mengenai *siapa* yang mengubah konfigurasi, *apa* yang diubah, dan *mengapa* perubahan dilakukan.
4. **Human Error**: Kesalahan manusia (typo konfigurasi, salah memilih subnet, salah menghapus resource) saat operasional darurat.
5. **Skalabilitas Nol**: Membuat 100 virtual machine dengan konfigurasi identik membutuhkan waktu berhari-hari secara manual, sementara bisnis menuntut provisioning dalam hitungan menit.

Dengan **Infrastructure as Code**, infrastruktur diperlakukan setara dengan kode aplikasi: tersimpan dalam Version Control System (VCS), diuji melalui automated testing, direview melalui Pull Request (PR), dan di-deploy melalui pipeline CI/CD otomatis.

---

## SEKSI 05 — APA ITU (WHAT)

**Infrastructure as Code (IaC)** adalah praktik rekayasa perangkat lunak untuk mengelola, menyediakan (*provisioning*), dan mengonfigurasi infrastruktur komputasi (server, jaringan, load balancer, database managed, storage) menggunakan file definisi yang terbaca oleh mesin (*machine-readable definition files*), bukan konfigurasi manual atau perkakas interaktif.

### Taksonomi IaC

| Dimensi | Provisioning Engine | Configuration Management |
| :--- | :--- | :--- |
| **Fokus Utama** | Membangun fondasi infrastruktur (VPC, VM, Storage, Subnet, DNS). | Mengonfigurasi OS dan aplikasi di dalam instance yang sudah ada. |
| **Tools Populer** | Terraform, OpenTofu, AWS CloudFormation, Pulumi. | Ansible, Puppet, Chef, SaltStack. |
| **Filosofi State** | Immutable Infrastructure (Hancurkan dan buat baru jika ada perubahan arsitektur). | Mutable Infrastructure (Modifikasi server berjalan secara in-place). |
| **Pendekatan** | Dominan Deklaratif. | Hybrid (Deklaratif & Prosedural). |

### Tiga Pilar Fundamental IaC

1. **Declarative Specification**: Anda mendefinisikan *apa* hasil akhir yang diinginkan (*Desired State*), bukan *bagaimana* urutan langkah untuk mencapainya (*Execution Steps*). Engine IaC yang bertanggung jawab menghitung selisih dan melakukan kalkulasi dependensi.
2. **Idempotency**: Properti di mana operasi eksekusi dapat dijalankan berulang kali dengan input yang sama, tanpa mengubah hasil di luar status awal yang telah tercapai. Jika infrastruktur target sudah sesuai kode, tidak ada perubahan yang dieksekusi ($f(f(x)) = f(x)$).
3. **Single Source of Truth**: Kode di repository Git adalah representasi absolut dari arsitektur sistem. Perubahan pada lingkungan produksi di luar Git dianggap anomali/pelanggaran operasional.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

Engine deklaratif modern (seperti Terraform/OpenTofu) beroperasi menggunakan model sinkronisasi status melalui komponen berikut:

```
[ Developer ] 
      │ (1) Write HCL Code
      ▼
[ Git Repository ]
      │ (2) Pull / Trigger
      ▼
[ IaC Engine (Terraform/OpenTofu) ]
      ├── A. Parse & Dependency Graph Construction (Directed Acyclic Graph)
      ├── B. Refresh: Query Provider API -> Dapatkan "Current State"
      ├── C. Diff Calculation: Bandingkan "Desired State" vs "Current State"
      └── D. Execution Plan Generation
            │
            ├─► (3) Persetujuan Operator (Approval)
            │
            ▼
      [ Provider Engine (Plugins) ]
            │ (4) Eksekusi REST/gRPC Calls
            ▼
      [ Cloud / Target Platform (AWS, GCP, K8s, Docker) ]
            │ (5) Mengembalikan Status Baru
            ▼
      [ Update State File (*.tfstate) ]
```

### 1. Directed Acyclic Graph (DAG) Engine
Engine membaca semua file berekstensi `.tf`, memetakan dependensi antar-resource (misalnya: resource Subnet membutuhkan VPC ID, maka VPC harus dibuat terlebih dahulu), dan menyusun DAG. Resource yang tidak saling bergantung akan dieksekusi secara konkuren (*parallel processing*).

### 2. State Mapping & Reconciliation
File state (`terraform.tfstate`) berfungsi sebagai jembatan pemetaan antara resource abstrak di kode dengan ID nyata resource di cloud/platform API (misal: `aws_instance.web` dipetakan ke ID fisik `i-0a1b2c3d4e5f6g`). 

Proses rekonsiliasi memiliki 3 skenario:
* **Create**: Terdefinisi di kode, belum ada di state/realita.
* **Update**: Ada di kode dan realita, tetapi parameternya berbeda (misal: ukuran memory diubah).
* **Destroy**: Dihapus dari kode, tetapi masih tercatat di state/realita.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

Berikut adalah alur reconcilation engine dan deteksi drift:

```
+-------------------------------------------------------------------------------+
|                             RECONCILIATION ENGINE                             |
+-------------------------------------------------------------------------------+

   [ DESIRED STATE ]                [ CURRENT STATE ]             [ ACTUAL REALITY ]
   (File .tf di Git)             (File terraform.tfstate)         (Infrastruktur Cloud)
           │                                 │                              │
           │                                 │    1. Provider API Read      │
           │                                 │ <────────────────────────────┤
           │                                 │    (Refresh actual data)     │
           │                                 │                              │
           │                                 ▼                              │
           │                       [ REFRESHED STATE ]                      │
           │                                 │                              │
           │ 2. Bandingkan Desired           │                              │
           │    terhadap Refreshed           │                              │
           ▼                                 ▼                              │
     +---------------------------------------------+                        │
     |             CALCULATE DIFF MATRIX           |                        │
     |                                             |                        │
     |  A. Desired == Refreshed  => No Operation   |                        │
     |  B. Desired != Refreshed  => Plan In-Place  |                        │
     |  C. Not in Desired        => Plan Destroy   |                        │
     |  D. Not in Refreshed      => Plan Create    |                        │
     +---------------------------------------------+                        │
                            │                                               │
                            ▼                                               │
                     [ EXECUTION PLAN ]                                     │
                     (Output Diff +/-/~)                                    │
                            │                                               │
                            │ 3. Apply Plan via Cloud APIs                  │
                            ├──────────────────────────────────────────────>│
                            │                                               │
                            ▼                                               ▼
     +---------------------------------------------+              +-------------------+
     |              UPDATE STATE FILE              |              | INFRASTRUKTUR     |
     | Sinkronkan metadata ID Cloud ke State Lokal |              | BERUBAH KE STATUS |
     | Menyimpan checksum & integritas arsitektur  |              | DESIRED TERBARU   |
     +---------------------------------------------+              +-------------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Contoh ini menunjukkan cara mendefinisikan infrastruktur lokal menggunakan provider Docker dengan Terraform/OpenTofu, tanpa memerlukan kredensial cloud eksternal.

### 1. Struktur Direktori
```text
iac-simple-demo/
├── main.tf
└── versions.tf
```

### 2. Kode `versions.tf`
File ini mengunci versi engine dan provider yang digunakan guna menjamin konsistensi eksekusi.

```hcl
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0.1"
    }
  }
}

provider "docker" {
  # Menggunakan socket lokal Docker daemon default
  host = "unix:///var/run/docker.sock"
}
```

### 3. Kode `main.tf`
Mendefinisikan status yang diinginkan: sebuah container Nginx yang berjalan di port host 8080.

```hcl
# Mengunduh image dari Docker Hub (Desired State: Nginx Alpine latest)
resource "docker_image" "nginx" {
  name         = "nginx:alpine"
  keep_locally = false
}

# Membuat dan menjalankan container
resource "docker_container" "web_server" {
  image = docker_image.nginx.image_id
  name  = "production-web-server"

  ports {
    internal = 80
    external = 8080
  }
}
```

### 4. Eksekusi Perintah

```bash
# 1. Inisialisasi: Mengunduh plugin provider yang dibutuhkan
terraform init

# 2. Perencanaan: Melihat kalkulasi perubahan (Diff Engine)
terraform plan

# 3. Penerapan: Eksekusi pembuatan resource
terraform apply -auto-approve

# 4. Validasi: Periksa container yang dibuat via CLI Docker
docker ps --filter "name=production-web-server"

# 5. Penghancuran: Menghapus semua resource yang terkelola secara bersih
terraform destroy -auto-approve
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus Produksi: Penyediaan arsitektur jaringan Virtual Private Cloud (VPC), Subnet, Security Group, dan sebuah Compute Node untuk lingkungan Staging yang sepenuhnya terparameterisasi (*reusable*).

### 1. Struktur Folder
```text
enterprise-iac-infra/
├── environments/
│   └── staging/
│       ├── main.tf
│       ├── terraform.tfvars
│       ├── variables.tf
│       └── outputs.tf
```

### 2. File: `variables.tf`
Definisi tipe data dan batasan konfigurasi (input validation).

```hcl
variable "environment" {
  type        = string
  description = "Nama environment operasional"
  default     = "staging"

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Environment harus salah satu dari: development, staging, production."
  }
}

variable "network_cidr" {
  type        = string
  description = "CIDR Block utama untuk VPC"
  default     = "10.50.0.0/16"
}

variable "subnet_cidr" {
  type        = string
  description = "CIDR Block untuk Workload Subnet"
  default     = "10.50.10.0/24"
}

variable "app_port" {
  type        = number
  description = "Port aplikasi yang diizinkan masuk melalui firewall"
  default     = 80
}
```

### 3. File: `main.tf`
Logika deklaratif resource provider AWS (Mock / Real API compliant).

```hcl
terraform {
  required_version = ">= 1.6.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Di lingkungan nyata, state disimpan di backend S3 dengan DynamoDB Locking
  backend "local" {
    path = "terraform.tfstate"
  }
}

provider "aws" {
  region = "ap-southeast-1"
  default_tags {
    tags = {
      Environment = var.environment
      ManagedBy   = "Terraform"
      Module      = "Core-Network-Compute"
    }
  }
}

# 1. Isolasi Jaringan
resource "aws_vpc" "core_vpc" {
  cidr_block           = var.network_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.environment}-vpc"
  }
}

resource "aws_subnet" "public_subnet" {
  vpc_id                  = aws_vpc.core_vpc.id
  cidr_block              = var.subnet_cidr
  map_public_ip_on_launch = true
  availability_zone       = "ap-southeast-1a"

  tags = {
    Name = "${var.environment}-public-subnet"
  }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.core_vpc.id

  tags = {
    Name = "${var.environment}-igw"
  }
}

resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.core_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = {
    Name = "${var.environment}-public-rt"
  }
}

resource "aws_route_table_association" "public_assoc" {
  subnet_id      = aws_subnet.public_subnet.id
  route_table_id = aws_route_table.public_rt.id
}

# 2. Lapisan Keamanan (Firewall / Security Group)
resource "aws_security_group" "web_sg" {
  name        = "${var.environment}-web-sg"
  description = "Akses inbound HTTP dan seluruh akses egress keluar"
  vpc_id      = aws_vpc.core_vpc.id

  ingress {
    description = "Izinkan akses HTTP publik"
    from_port   = var.app_port
    to_port     = var.app_port
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Izinkan semua lalu lintas keluar"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 3. Instance Compute
data "aws_ami" "ubuntu_lts" {
  most_recent = true
  owners      = ["099720109477"] # Canonical ID

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

resource "aws_instance" "web_node" {
  ami                    = data.aws_ami.ubuntu_lts.id
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.public_subnet.id
  vpc_security_group_ids = [aws_security_group.web_sg.id]

  user_data = <<-EOF
              #!/bin/bash
              echo "Server Active: ${var.environment}" > /var/www/html/index.html
              systemctl restart nginx || true
              EOF

  tags = {
    Name = "${var.environment}-application-host"
  }
}
```

### 4. File: `outputs.tf`
Mengembalikan atribut resource setelah eksekusi untuk diintegrasikan dengan sistem downstream.

```hcl
output "vpc_id" {
  description = "ID dari VPC yang berhasil dibuat"
  value       = aws_vpc.core_vpc.id
}

output "instance_public_ip" {
  description = "IP Publik dari instance Compute"
  value       = aws_instance.web_node.public_ip
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Pendekatan / Fitur | Keuntungan | Kerugian & Batasan |
| :--- | :--- | :--- |
| **Deklaratif (e.g., HCL)** | Sistem otomatis mengelola order dependensi. Engine menangani penghapusan (*destroy*) secara cerdas saat kode dihapus. | Lebih sulit menulis logika kondisional kompleks, loop rekursif, atau manipulasi data multi-dimensi. |
| **Imperatif (e.g., AWS CDK, Pulumi)** | Menggunakan bahasa pemrograman native (TypeScript, Python, Go); integrasi unit testing native. | Abstraksi dapat mengaburkan pemahaman tentang resource API asli. Kompleksitas *build step* dan dependency runtime meningkat. |
| **Monolithic State** | Mudah dikonfigurasi pada tahap awal; semua resource saling referensi langsung. | **Blast Radius tinggi**: Kesalahan pada satu resource dapat merusak seluruh infrastruktur. Eksekusi `plan`/`apply` menjadi sangat lambat. |
| **Modular Micro-States** | Isolasi risiko tinggi. Waktu eksekusi cepat. Hak akses IAM dapat dibagi per tim. | Membutuhkan integrasi dependensi manual menggunakan `data remote_state` atau SSM Parameter Store. |

---

## SEKSI 11 — BEST PRACTICES

1. **Remote State Locking**: Jangan pernah menyimpan file status secara lokal atau di repository Git. Simpan di object storage terenkripsi (misal: AWS S3, GCS) yang dipadukan dengan mekanisme lock atomik (misal: DynamoDB) untuk mencegah *race condition* eksekusi bersamaan.
2. **Kecilkan Blast Radius**: Pisahkan arsitektur ke dalam layer terpisah:
   * Layer 01: Core Networking (VPC, Subnet, Peering).
   * Layer 02: Persistence / Databases (RDS, Redis).
   * Layer 03: Compute / Services (EKS, EC2, ECS).
3. **Immutability Principle**: Hindari modifikasi konfigurasi di level instance (SSH in-place update). Jika versi baru aplikasi atau patch OS dirilis, bangun Image baru (menggunakan Packer) dan deploy instance baru menggantikan instance lama (*Blue/Green* atau *Rolling Deployment*).
4. **Enkripsi File State**: State file menyimpan output resource secara *plaintext*, termasuk password database, secret key, atau token API. Aktifkan enkripsi *at-rest* (AES-256 / KMS) dan batasi hak baca state via IAM policy strictly.
5. **Linting dan Static Code Analysis**: Pasang perkakas validasi pada tahap pre-commit dan CI pipeline:
   * `terraform fmt -check` (Standardisasi format)
   * `tflint` (Mendeteksi potensi kesalahan arsitektur cloud provider)
   * `checkov` atau `tfsec` (Audit keamanan untuk mencegah miskonfigurasi port terbuka, unencrypted storage).

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Commit File `.tfstate` ke Git**:
   * *Problem*: File state berisi seluruh parameter rahasia (*plain text*) dan akan memicu *merge conflict* permanen jika ada dua orang mengeditnya bersamaan.
   * *Fix*: Tambahkan `*.tfstate`, `*.tfstate.backup`, dan `.terraform/` ke dalam `.gitignore`.

2. **Melakukan Perubahan Manual via Web GUI (Drift Injection)**:
   * *Problem*: Seorang engineer mengubah rule firewall langsung di AWS Console saat troubleshooting darurat. Saat pipeline IaC dijalankan berikutnya, perubahan darurat tersebut akan dihapus/di-override oleh engine IaC, berpotensi memicu insiden ulang.
   * *Fix*: Jika terpaksa mengubah via GUI, segera lakukan sinkronisasi ke kode IaC lalu jalankan `terraform refresh` atau impor perubahan tersebut ke dalam kode sebelum sesi kerja selesai.

3. **Mengabaikan Pengecekan `terraform plan`**:
   * *Problem*: Menjalankan `terraform apply -auto-approve` secara buta. Jika ada perubahan nama resource atau modifikasi parameter kritis (seperti `allocated_storage` tanpa feature autoscale), provider mungkin akan menghancurkan (*destroy*) instance lama dan membuat yang baru, menyebabkan *unplanned downtime* dan kehilangan data.
   * *Fix*: Selalu telaah output plan, pastikan tidak ada indikasi: `# aws_instance.db will be destroyed and recreated`.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Inisialisasi dan Inspeksi Resource Lokal (30 Menit)
* **Tujuan**: Memahami relasi file konfigurasi lokal, instalasi provider, dan pembuatan state file.
* **Instruksi**:
  1. Buat direktori baru `exercise-local`.
  2. Definisikan provider `local` (menggunakan resource `local_file`).
  3. Konfigurasikan output berupa random UUID menggunakan provider `random`.
  4. Jalankan `terraform init`, `terraform plan`, dan `terraform apply`.
  5. Buka isi file `terraform.tfstate`, temukan nilai checksum dan relasi resource yang baru dibuat.

### Latihan 2: Modularisasi Variabel Dinamis (45 Menit)
* **Tujuan**: Membuat modul yang dapat digunakan berulang kali dengan konfigurasi parameter berbeda.
* **Instruksi**:
  1. Buat modul bernama `local-directory-structure`.
  2. Modul harus menerima array of string `subdirectories = ["logs", "data", "backup"]`.
  3. Modul bertugas membuat folder dan file placeholder `keep.txt` di dalam masing-masing direktori menggunakan perulangan `for_each`.
  4. Panggil modul ini dua kali dengan list folder yang berbeda.

### Latihan 3: Tantangan Deteksi dan Resolusi Drift (60 Menit)
* **Tujuan**: Mengalami insiden configuration drift dan menyelesaikannya sesuai kaidah engineering IaC.
* **Instruksi**:
  1. Jalankan konfigurasi Docker container (dari Seksi 08).
  2. Buka terminal eksternal, hentikan container secara manual menggunakan Docker CLI natif: `docker stop production-web-server && docker rm production-web-server`.
  3. Jalankan `terraform plan` tanpa mengubah file kode HCL. Amati bagaimana Terraform mendeteksi ketiadaan container fisik tersebut.
  4. Eksekusi `terraform apply` untuk merekonsiliasi sistem kembali ke status deklaratif yang didefinisikan.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

### Pertanyaan Evaluasi

1. **Apa yang dimaksud dengan sifat *Idempotent* pada sistem IaC?**
   * A. Eksekusi kode harus dilakukan satu kali saja selama siklus proyek.
   * B. Kemampuan mengeksekusi kode berkali-kali dengan input yang sama tanpa menghasilkan efek samping tak terduga setelah status target tercapai.
   * C. Kemampuan merestart server secara otomatis jika terjadi lonjakan trafik.
   * D. Proses enkripsi otomatis seluruh secret dalam file konfigurasi.

2. **Mengapa menyimpan `terraform.tfstate` di dalam repository publik Git merupakan celah keamanan kritikal?**
   * A. Karena file `.tfstate` memperlambat proses commit Git.
   * B. Karena Git tidak dapat melacak file berbasis JSON.
   * C. Karena file `.tfstate` menyimpan seluruh atribut resource termasuk database credentials dan private key dalam bentuk plaintext.
   * D. Karena file `.tfstate` akan otomatis terhapus saat branch di-merge.

3. **Komponen apa yang digunakan oleh engine IaC deklaratif untuk menentukan urutan pembuatan resource yang saling bergantung?**
   * A. Round Robin Scheduling Algorithm.
   * B. Directed Acyclic Graph (DAG).
   * C. Linear Queue FIFO.
   * D. Blockchain Validation Engine.

4. **Kapan kondisi `Configuration Drift` terjadi dalam ekosistem cloud?**
   * A. Ketika developer mengupdate dependensi library aplikasi pada file `package.json`.
   * B. Ketika status riil infrastruktur di cloud menyimpang dari status yang didefinisikan di kode IaC akibat intervensi manual di luar sistem IaC.
   * C. Ketika hard disk server mengalami fragmentasi data.
   * D. Ketika pipeline CI/CD kehabisan kuota eksekusi bulanan.

---

### Kunci Jawaban & Rasional

1. **B** — Idempotensi menjamin determinisme status. Jika lingkungan sudah berada pada kondisi yang diinginkan, eksekusi berulang tidak akan mengubah status apa pun.
2. **C** — State file wajib menyimpan seluruh atribut balikan dari cloud provider. Jika Anda membuat instance RDS, master password-nya tersimpan secara plaintext di dalam state file tersebut.
3. **B** — Engine IaC membangun Directed Acyclic Graph (DAG) untuk menganalisis node mana yang tidak memiliki dependensi sehingga dapat dibuat secara paralel, dan node mana yang harus menunggu pembuatan node induknya.
4. **B** — Configuration Drift adalah kondisi desinkronisasi di mana status infrastruktur fisik aktual telah termodifikasi secara manual tanpa pembaruan padanannya pada codebase deklaratif.

---

### Self-Assessment Checklist
* [ ] Saya mampu menjelaskan perbedaan filosofis antara Ansible (Config Management) dan Terraform (Provisioning).
* [ ] Saya mengerti konsekuensi fatal jika state locking tidak diaktifkan pada tim multi-kontributor.
* [ ] Saya dapat membaca perbedaan (*diff*) output perintah `plan` (simbol `+`, `~`, `-`).
* [ ] Saya tidak pernah lagi menyimpan API key cloud provider di dalam file kode sumber lokal secara hardcoded.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1. **Dokumentasi Resmi**:
   * HashiCorp Terraform Documentation: `https://developer.hashicorp.com/terraform/docs`
   * OpenTofu Documentation (Linux Foundation): `https://opentofu.org/docs/`
2. **Buku Rujukan Standar Industri**:
   * *Terraform: Up & Running: Writing Infrastructure as Code* (3rd Edition) oleh Yevgeniy Brikman.
   * *Infrastructure as Code: Dynamic Systems for the Cloud Era* (2nd Edition) oleh Kief Morris.
3. **Standar Keamanan**:
   * CIS Controls for Cloud Infrastructure Baseline.
   * Terraform Security Best Practices by Bridgecrew.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

* **Infrastructure as Code (IaC)** memigrasikan pola operasi infrastruktur dari intervensi manual (ClickOps) menjadi pendekatan berbasis kode yang dapat diuji, direview, dan dilacak melalui VCS.
* Pendekatan **Deklaratif** membebaskan operator dari menyusun algoritma eksekusi berurutan; operator cukup mendefinisikan *desired end-state*, sementara IaC engine menyusun DAG execution plan secara otomatis.
* **State File** adalah representasi sentral yang memetakan kode deklaratif terhadap ID resource di target API. Mengamankan, mengenkripsi, dan mengunci file ini secara remote adalah syarat mutlak lingkungan kolaboratif.
* **Idempotency** memastikan eksekusi pipeline yang konsisten dan dapat diprediksi tanpa memicu duplikasi atau *downtime* yang tidak diinginkan.
* Disiplin operasi IaC mewajibkan seluruh modifikasi status melewati proses PR review di Git guna memusnahkan potensi **Configuration Drift**.

---

## SEKSI 17 — GLOSARIUM

* **Idempotency**: Properti matematika dan ilmu komputer di mana sebuah operasi menghasilkan hasil akhir yang identik, terlepas dari berapa kali operasi tersebut diulang.
* **Configuration Drift**: Pergeseran status antara infrastruktur nyata yang sedang beroperasi dengan spesifikasi arsitektur yang tertulis di repository kode.
* **State File**: Basis data metadata lokal/remote yang memetakan resource IaC dengan identitas resource aktual di penyedia infrastruktur.
* **Blast Radius**: Tingkat keparahan atau cakupan dampak kerusakan yang dialami seluruh sistem apabila sebuah komponen infrastruktur gagal atau salah dikonfigurasi.
* **Directed Acyclic Graph (DAG)**: Struktur data grafik terarah tanpa siklus berulang, digunakan untuk mengurai rantai ketergantungan antar-komponen secara presisi.
* **ClickOps**: Istilah peyoratif industri untuk konfigurasi infrastruktur melalui klik-klik GUI web console yang tidak terlacak, tidak terulang, dan rentan human-error.
* **Reconciliation Loop**: Siklus berkelanjutan yang bertugas membandingkan state aktual dengan state yang diinginkan, kemudian menjalankan aksi korektif jika ditemukan perbedaan.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Analogi Pengajaran**: Gunakan analogi "Cetak Biru Arsitektur Bangunan" vs "Instruksi Tukang Bangunan Hari Demi Hari". Deklaratif IaC adalah cetak biru akhir: jika jendela sudah ada di posisi yang benar, tukang tidak akan membongkar jendela tersebut; tukang hanya akan membangun apa yang kurang.
* **Mitigasi Hambatan Pemula**: 
  * Jangan langsung membawa peserta ke AWS/GCP pada pertemuan pertama. Kendala kartu kredit, tagihan bocor (*billing surprise*), dan manajemen IAM policy yang rumit seringkali mengalihkan fokus peserta dari konsep fundamental IaC.
  * Gunakan provider Docker lokal atau provider `local_file` (seperti di Seksi 08 dan 13) agar peserta memahami pembacaan file `.tfstate` dan kalkulasi diff tanpa friksi kredensial cloud eksternal.
* **Poin Penekanan Mutlak**: Tanamkan sejak dini bahwa file `.tfstate` BUKAN file yang boleh di-commit ke Git. Buat simulasi langsung kegagalan merge conflict state untuk mendemonstrasikan bahayanya.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0** (Tanggal: 2024-03-29)
  * Pembuatan rilis modul awal untuk track `devops-beginner`.
  * Integrasi kurikulum berbasis Terraform v1.6+ dan OpenTofu.
  * Penyusunan modul praktikum lokal menggunakan Docker provider dan AWS compliant stack.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `DEV-FOUND-07-01: Networking & Security Architecture for Cloud-Native Environments`
* **Modul Saat Ini**: `DEV-FOUND-08-01: Infrastructure as Code (IaC) Fundamentals & Architecture`
* **Modul Berikutnya**: `DEV-FOUND-08-02: Configuration Management & Automation with Ansible`
* **Indeks Jalur Belajar**: `01-Core-Foundations / Track Overview`