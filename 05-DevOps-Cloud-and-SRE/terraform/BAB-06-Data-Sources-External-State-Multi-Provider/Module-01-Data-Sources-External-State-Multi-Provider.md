# Module 01: Data Sources, External State & Multi-Provider Architecture

## 1. Learning Objective
Setelah menyelesaikan modul ini, engineer mampu:
- Menguasai siklus hidup (*lifecycle*) dan evaluasi Directed Acyclic Graph (DAG) dari Terraform Data Sources.
- Mengimplementasikan komunikasi lintas *stack* secara aman menggunakan `terraform_remote_state` dan mengevaluasi alternatif *loose-coupling* (SSM/Consul).
- Merancang arsitektur multi-wilayah (*multi-region*) dan multi-akun (*multi-account*) dalam satu *root module* menggunakan Provider Aliasing.
- Mengintegrasikan HashiCorp Vault Provider untuk injeksi *dynamic secrets* dan manajemen *ephemeral credentials*.
- Memanfaatkan data source `http` dan `external` sebagai *escape hatch* integrasi sistem legacy tanpa merusak determinisme deklaratif Terraform.

---

## 2. Prerequisite
Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- **State Management Fundamental**: Memahami format JSON `terraform.tfstate`, manipulasi `terraform state mv/rm`, dan state locking via DynamoDB/GCS.
- **Terraform Expressions & Functions**: Penggunaan `lookup`, `try`, `can`, `jsondecode`, dan *splat syntax*.
- **Cloud IAM & Networking**: Konsep VPC Peering, Transit Gateway, IAM Cross-Account Role Assumption, dan AWS CLI profile resolution.
- **Keamanan Secrets Management**: Dasar-dasar enkripsi *at-rest*, *in-transit*, prinsip *least privilege*, serta siklus rotasi token Vault.

---

## 3. Concept
Terraform didesain secara deklaratif untuk merekonsiliasi keadaan aktual (*actual state*) terhadap keadaan yang diinginkan (*desired state*). Namun, sistem enterprise nyata tidak berdiri sendiri dalam satu *state file* monolitik. Diperlukan abstraksi untuk:
1. **Membaca status infrastruktur yang dikelola di luar kontrol deklarasi modul saat ini** (*Read-only consumption* via Data Sources).
2. **Menghubungkan dependensi modular tingkat tinggi** (*Core Networking* $\rightarrow$ *Kubernetes Cluster* $\rightarrow$ *Application Workloads*) tanpa menyatukan *blast radius* kegagalan.
3. **Mendistribusikan deklarasi infrastruktur ke berbagai boundary geografis atau perizinan** (*Provider Aliasing*).
4. **Mencegah kebocoran rahasia statis ke dalam state file** melalui abstraksi mesin rahasia dinamis (*Dynamic Vault Engine*).
5. **Menjembatani limitasi ekosistem provider** melalui protokol *External IPC (Inter-Process Communication)* berbasis JSON.

---

## 4. Why
Mengapa arsitektur ini krusial dalam rekayasa keandalan sistem (SRE) dan Platform Engineering?
- **Reduksi Blast Radius**: Memecah infrastruktur monolitik menjadi *decoupled stacks*. Kerusakan atau *lock conflict* pada modul database aplikasi tidak melumpuhkan core VPC network.
- **High Availability & Disaster Recovery (DR)**: Provider aliasing memungkinkan orkestrasi paralel komponen primer (*active*) dan sekunder (*passive*) lintas region dalam satu alur eksekusi deterministik.
- **Eliminasi Long-Lived Static Credentials**: Menggunakan Vault provider mengeliminasi risiko bocornya kredensial IAM/Database statis di `.tfstate`, menggantikannya dengan kredensial dengan masa berlaku pendek (*short-lived leases*).
- **Interoperabilitas Sistem Non-Terraform**: Modul infrastruktur seringkali membutuhkan metadata dari CMDB lawas, internal IPAM API, atau pipeline hybrid. Data source `http` dan `external` menutup celah fungsionalitas tersebut.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Siklus Hidup dan Evaluasi DAG Data Source
Data source dieksekusi dengan membaca (*reading*) metadata infrastruktur tanpa mengelola *lifecycle* CRUD (Create, Read, Update, Delete) dari target tersebut.
- **Refresh Phase Evaluation**: Secara default, jika argumen data source bernilai statis atau diketahui (*known*) sebelum eksekusi, data source dievaluasi saat fase `terraform refresh` / `terraform plan`.
- **Apply Phase Deferral**: Jika argumen query data source bergantung pada output resource terkelola yang belum di-*apply* (misal: ID dari instance baru), evaluasi ditunda (*deferred*) ke fase `apply`. Hal ini memicu tanda `(known after apply)` pada atribut data source.
- **Implicit vs Explicit Dependency**: Penggunaan `depends_on` pada data source memaksa penundaan evaluasi ke fase `apply`, membatalkan optimasi pembacaan paralel pada fase `plan`.

### 5.2 Cross-Stack Reference via `terraform_remote_state`
Data source `terraform_remote_state` membaca *state snapshot* dari backend remote (S3, GCS, Consul, TF Cloud).
- **Mekanisme**: Membaca root-level `outputs` dari state target. Atribut internal yang tidak diekspos sebagai output tidak dapat diakses.
- **Tantangan Keamanan (Security Risk)**: `terraform_remote_state` memerlukan akses baca langsung ke file `.tfstate` target. Karena state file memuat semua data secara plain text, akses ini mengekspos seluruh data sensitif root module target kepada modul pemanggil.
- **Alternatif Modern**: Parameter Store (AWS SSM), HashiCorp Consul KV, atau API Registry untuk memutus ketergantungan direct read akses terhadap raw state storage.

### 5.3 Provider Aliasing: Multi-Region & Multi-Account Execution
Secara bawaan, sebuah provider instansiasi memiliki konfigurasi global implisit (*default provider*). Untuk mengarahkan resource ke target berbeda:
- **Deklarasi Alias**: Menggunakan meta-argumen `alias` di dalam blok `provider`.
- **Injeksi Child Module**: Provider eksplisit tidak diwariskan secara otomatis jika child module membutuhkan alias berbeda. Pemetaan dilakukan melalui blok `providers = { aws.alias_target = aws.alias_sumber }`.

```hcl
# Injeksi provider ke child module
module "vpc_peering_cross_region" {
  source = "./modules/vpc-peering"
  providers = {
    aws.requester = aws.primary
    aws.accepter  = aws.secondary
  }
}
```

### 5.4 HashiCorp Vault Provider & Dynamic Ephemeral Credentials
Vault Provider berinteraksi dengan Vault API engine (`/v1/secret/`, `/v1/database/creds/`, `/v1/aws/creds/`).
- **Autentikasi**: AppRole, Kubernetes Service Account token, atau OIDC/JWT.
- **Lease Lifecycle**: Token yang di-*issue* memiliki TTL (Time-To-Live). Terraform menggunakan kredensial ini untuk memprovisioning resource, kemudian membuang kredensial setelah eksekusi selesai (*ephemeral lifetime*).

### 5.5 HTTP & External Data Sources
- **`data "http"`**: Melakukan HTTP GET/POST terhadap REST endpoint. Mengembalikan respons mentah (`body`) dan `status_code`. Dapat diparsing menggunakan `jsondecode()`.
- **`data "external"`**: Menjalankan subprocess biner lokal via stdin/stdout.
  - *Protokol Kontrak*: Input dikirim via stdin berupa JSON string map (`map[string]string`). Output harus dikembalikan via stdout berupa flat JSON string map (`map[string]string`). Karakter non-JSON pada stdout menyebabkan parsing failure instan.

---

## 6. How
Implementasi dilakukan dengan memisahkan *state responsibilities*:
1. Root network diisolasi ke dalam state terpisah.
2. Root database dan workload mengonsumsi data via `terraform_remote_state` atau parameter store.
3. Arsitektur multi-region dikonfigurasi melalui aliasing pada root module dan di-mapping ke child module.
4. Integrasi Vault dilakukan dengan mengonfigurasi provider Vault, mereferensikan path dynamic engine, dan menyuntikkannya ke provider downstream (misal: PostgreSQL Provider).

---

## 7. Analogy
Bayangkan sebuah bandara internasional:
- **Resource Block**: Kontraktor yang membangun landasan pacu baru dari nol.
- **Data Source**: Pemandu Lalu Lintas Udara (ATC) yang membaca sensor anemometer (kecepatan angin) yang sudah terpasang; ATC tidak membuat sensor, hanya membaca nilainya untuk mengambil keputusan pendaratan.
- **`terraform_remote_state`**: Lemari arsip bersama. Departemen Logistik membaca dokumen blue-print dari Departemen Sipil untuk mengetahui kapasitas landasan pacu.
- **Provider Alias**: Terminal 1 (Region Utama, Jakarta) dan Terminal 2 (Region Sekunder, Singapura) yang dikelola oleh satu Direktur Operasional dengan tim ground-handling lokal yang berbeda di tiap terminal.
- **Vault Provider**: Kunci magnetik digital sekali pakai yang diterbitkan sekuriti untuk teknisi pemeliharaan, yang otomatis hangus setelah 30 menit.

---

## 8. Diagram (ASCII)

```
                       +-----------------------------------+
                       |    Root Module (Master Orchestration)
                       +-----------------------------------+
                         |                 |             |
           +-------------+                 |             +-------------+
           | (Provider aws.primary)        | (Provider aws.dr)         | (Provider vault)
           v                               v                           v
+-----------------------+      +-----------------------+      +--------------------+
|  AWS ap-southeast-1   |      |  AWS ap-southeast-3   |      | HashiCorp Vault API|
|  (Singapore Region)   |      |  (Jakarta Region)     |      | (Secrets Engine)   |
+-----------------------+      +-----------------------+      +--------------------+
|  VPC Primary          |<-----+  VPC Disaster Recovery|                 |
|  10.100.0.0/16        | Peering |  10.200.0.0/16     |                 |
+-----------------------+      +-----------------------+                 |
           ^                                                             |
           | Read Remote Output via S3 State Storage                     | Dynamic DB Creds
           |                                                             v
+-----------------------------+                       +-----------------------------+
| Stack: Data Storage Tier    |                       | Provider: postgresql        |
| - terraform_remote_state.net|<----------------------| (Uses Vault dynamic user/pw)|
+-----------------------------+                       +-----------------------------+
```

---

## 9. Simple Example

Query AMI Ubuntu resmi terbaru menggunakan native data source filtering:

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
  region = "ap-southeast-1"
}

data "aws_ami" "ubuntu_latest" {
  most_recent = true
  owners      = ["099720109477"] # Canonical ID

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

output "resolved_ami_id" {
  description = "AMI ID terbaru yang di-resolve secara dinamis saat phase plan/apply"
  value       = data.aws_ami.ubuntu_latest.id
}
```

---

## 10. Practical Example (Konfigurasi CLI / Terraform / Kode Hands-on)

Arsitektur Multi-Region VPC Peering dengan injeksi Dynamic Secrets via HashiCorp Vault.

### File: `providers.tf`
```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    vault = {
      source  = "hashicorp/vault"
      version = "~> 3.20"
    }
  }
}

# Provider Primer (Singapura)
provider "aws" {
  alias  = "primary"
  region = "ap-southeast-1"
}

# Provider Sekunder / DR (Jakarta)
provider "aws" {
  alias  = "dr"
  region = "ap-southeast-3"
}

# Vault Provider
provider "vault" {
  address = "http://vault.internal.corp:8200"
  # VAULT_TOKEN dibaca otomatis dari environment variable runtime
}
```

### File: `cross_stack_and_secrets.tf`
```hcl
# 1. Cross-stack state access membaca network base
data "terraform_remote_state" "networking" {
  backend = "s3"
  config = {
    bucket = "corp-tf-state-secure-prod"
    key    = "network/terraform.tfstate"
    region = "ap-southeast-1"
  }
}

# 2. Vault dynamic database credential engine
data "vault_database_connection" "prod_db" {
  name = "aurora-postgres-cluster"
}

data "vault_generic_secret" "dynamic_creds" {
  path = "database/creds/tf-workload-role"
}

# 3. HTTP Data Source untuk dynamic external IP lookup
data "http" "deployer_public_ip" {
  url = "https://checkip.amazonaws.com"
  request_headers = {
    Accept = "text/plain"
  }
}

# 4. External Data Source: Menjalankan Custom IPC Sanitizer
data "external" "host_telemetry" {
  program = ["python3", "${path.module}/scripts/get_telemetry.py"]
  query = {
    cluster_id = "prod-eks-01"
    environment = "production"
  }
}
```

### File: `networking_multiregion.tf`
```hcl
# Provision VPC Primer via Provider Primary
resource "aws_vpc" "primary_vpc" {
  provider             = aws.primary
  cidr_block           = "10.100.0.0/16"
  enable_dns_hostnames = true

  tags = {
    Name    = "vpc-primary-ap-southeast-1"
    Deployer = chomp(data.http.deployer_public_ip.response_body)
  }
}

# Provision VPC Sekunder via Provider DR
resource "aws_vpc" "dr_vpc" {
  provider             = aws.dr
  cidr_block           = "10.200.0.0/16"
  enable_dns_hostnames = true

  tags = {
    Name        = "vpc-dr-ap-southeast-3"
    BaselineNet = data.terraform_remote_state.networking.outputs.vpc_mesh_id
  }
}

# Peering Requestor (Primary Region)
resource "aws_vpc_peering_connection" "primary_to_dr" {
  provider    = aws.primary
  vpc_id      = aws_vpc.primary_vpc.id
  peer_vpc_id = aws_vpc.dr_vpc.id
  peer_region = "ap-southeast-3"
  auto_accept = false

  tags = {
    Name = "peering-sg-jkt"
  }
}

# Peering Accepter (DR Region)
resource "aws_vpc_peering_connection_accepter" "dr_accepter" {
  provider                  = aws.dr
  vpc_peering_connection_id = aws_vpc_peering_connection.primary_to_dr.id
  auto_accept               = true

  tags = {
    Name = "peering-sg-jkt-accepter"
  }
}
```

---

## 11. Real World Example
Sebuah unicorn fintech Indonesia menerapkan pemisahan tugas (*Segregation of Duties* / SoD) yang ketat. Tim Core Infrastructure mengelola akun AWS Landing Zone `Core-Networking` (CIDR allocation, DirectConnect, Transit Gateway). Tim Engineering mengelola akun AWS `Application-Production`.

Tim Engineering tidak memiliki izin IAM untuk membaca atau memodifikasi Route Tables di akun Networking. Untuk mengintegrasikan backend aplikasi mereka:
1. **Network Stack Deployment**: Tim Networking menerbitkan output ID Transit Gateway Attachment dan Subnet IDs ke AWS SSM Parameter Store dengan akses *read* lintas-akun.
2. **Dynamic VPC Attachment**: Modul Terraform Tim Engineering tidak menggunakan `terraform_remote_state` (mencegah terbacanya file state Core Net yang berisi secrets internal), melainkan data source `aws_ssm_parameter` lintas akun.
3. **Vault Database Engine**: Modul database Terraform tidak menetapkan master password database, melainkan mendelegasikan rotasi kredensial ke Vault Dynamic AWS/DB Secrets Engine. Setiap kali Terraform apply berjalan di CI/CD, kredensial PostgreSQL dibuat dengan TTL 1 jam, digunakan untuk apply schema/user, dan Vault mencabutnya (*lease revoked*) jika pipeline selesai.

---

## 12. Trade-offs

| Pendekatan | Keuntungan | Kerugian / Risiko |
| :--- | :--- | :--- |
| **`terraform_remote_state`** | Sangat mudah diimplementasikan, *native support*, tidak perlu dependensi third-party. | **Tight Coupling**: Mengikat format output antar state. **Keamanan**: Memerlukan akses baca penuh ke seluruh file target state (potensial *privilege escalation*). |
| **Parameter Store / KV (SSM/Consul)** | **Loose Coupling**: Interface jelas berbasis schema key-value. **Granular IAM**: Izin akses dapat dibatasi per parameter via IAM policy. | Menambah layer infrastruktur eksternal. Perubahan state tidak sinkron secara atomik (*eventual consistency lag*). |
| **Provider Aliasing (Single Root)** | Atomisitas tinggi: Orkestrasi multi-region multi-account selesai dalam satu kali run `terraform apply`. | **Blast Radius**: Jika plan gagal di satu region, keseluruhan siklus deployment tertahan. Kompleksitas refactoring tinggi. |
| **Split Root Modules (Multi Pipeline)**| Isolasi total: Kegagalan region A tidak mempengaruhi pipeline region B. | State drift: Sinkronisasi antar region memerlukan pipeline orchestrator eksternal (GitHub Actions/Spacelift/Terragrunt). |
| **Data Source `external`** | Skalabilitas integrasi tak terbatas; bahasa pemrograman apapun yang menghasilkan JSON dapat digunakan. | **Non-portable**: Bergantung pada biner lokal runtime (Python, Bash, jq). Sulit di-audit dalam skala enterprise CI/CD runners. |

---

## 13. When To Use
- Gunakan **Data Sources** ketika Anda harus membaca konfigurasi resource yang dikelola oleh tim lain, dikelola oleh platform luar (misal: AWS Managed Services), atau dibuat pada siklus provisioning yang berbeda.
- Gunakan **Provider Aliasing** ketika membangun pola Multi-Region Disaster Recovery, Active-Active Cross-Region Meshes, atau Cross-Account Resource Sharing (misal: RAM - Resource Access Manager).
- Gunakan **Vault Provider** pada pipeline CI/CD produksi di mana penyimpanan kredensial database/cloud statis di repository maupun state storage dilarang secara kepatuhan audit (SOC2, ISO27001, PCI-DSS).

---

## 14. When NOT To Use
- Jangan gunakan **`terraform_remote_state`** jika modul pemanggil dan modul target memiliki tingkat klasifikasi keamanan data yang berbeda (*high-trust* vs *low-trust*).
- Jangan gunakan **Data Source `external`** jika fungsionalitas tersebut dapat dicapai menggunakan native provider. Data source eksternal adalah jalan pintas terakhir (*escape hatch*) karena berpotensi merusak determinisme deklaratif infrastruktur.
- Jangan gunakan **Provider Aliasing** jika region/akun tersebut memiliki siklus rilis yang independen. Pisahkan menjadi direktori/root module independen untuk menjaga blast radius tetap minimal.

---

## 15. Common Mistakes
1. **Siklus Evaluasi Dini Data Source (`depends_on` Missing)**: Mencoba membaca resource baru via data source tanpa ketergantungan eksplisit, menyebabkan error *resource not found* saat fase initial apply.
2. **Ketergantungan Kuat Terhadap Output State**: Mengubah nama `output` pada module infrastruktur core tanpa memperhitungkan module downstream yang membaca via `terraform_remote_state`, memicu `KeyError` seketika pada pipeline downstream.
3. **Kebocoran Secrets State via `terraform_remote_state`**: Memberikan izin IAM `s3:GetObject` pada seluruh bucket state kepada developer, yang memungkinkan mereka membaca password database plaintext yang diekspos di root module lain.
4. **Non-Standard Stdin/Stdout pada Data Source External**: Mencetak log debug (`print("Connecting...")`) ke stdout pada skrip external data source, yang merusak parsing JSON parser Terraform (`invalid JSON response`).
5. **Konfigurasi Provider Diduplikasi di Modul Anak**: Mendeklarasikan blok `provider "aws" { ... }` lengkap di dalam child module, bukan mengeksposnya lewat blok konfigurasi proxy `configuration_aliases`.

---

## 16. Best Practices
1. **Gunakan Proxy Provider Aliases di Child Module**:
   ```hcl
   terraform {
     required_providers {
       aws = {
         source                = "hashicorp/aws"
         configuration_aliases = [aws.primary, aws.dr]
       }
     }
   }
   ```
2. **Terapkan Data Source Caching Strategis**: Hindari querying data source yang memindai ribuan resource pada setiap `plan` (seperti `aws_instances` tanpa filter spesifik) untuk mencegah *API Rate Limiting* (AWS ThrottlingException).
3. **Gunakan Interface Kontrak (Decoupled Layer)**: Gunakan AWS SSM Parameter Store atau HashiCorp Consul untuk transfer metadata antar-stack daripada direct `terraform_remote_state`.
4. **Redact Sensitive Outputs**: Gunakan atribut `sensitive = true` pada output yang bersumber dari Vault data sources untuk meminimalisasi eksploitasi visual pada log CI/CD runner.

---

## 17. Troubleshooting

### Kasus 1: Evaluasi Data Source Gagal dengan Error "Resource Not Found"
- **Penyebab**: Data source berjalan pada fase `plan` sebelum resource target dibuat oleh blok resource pada root yang sama atau stack yang belum selesai di-*apply*.
- **Solusi**: Tambahkan meta-argument `depends_on = [aws_resource.target]` pada blok data source untuk memaksa penundaan evaluasi (*deferred read*) ke fase `apply`.

### Kasus 2: Error "External program exited with status 1 / unexpected EOF"
- **Penyebab**: Skrip pada `data "external"` mencetak trace error atau warning ke stdout alih-alih stderr, atau exit dengan return code non-zero.
- **Solusi**: Arahkan seluruh log operasional skrip ke `stderr` (`sys.stderr.write(...)` di Python). Pastikan hanya valid single-line/multi-line JSON map yang dicetak ke `stdout`.

### Kasus 3: Provider Alias Initialization Error "missing provider configuration"
- **Penyebab**: Child module memerlukan provider dengan alias, tetapi pemanggil (*root module*) tidak mendefinisikan blok `providers` eksplisit saat memanggil modul.
- **Solusi**: Pastikan pemanggilan module memiliki blok:
  ```hcl
  module "my_service" {
    source    = "./modules/service"
    providers = {
      aws = aws.primary
    }
  }
  ```

---

## 18. Exercise
1. Tuliskan sebuah konfigurasi Terraform yang mendefinisikan dua provider AWS: region `us-east-1` (Virginia) dan `eu-central-1` (Frankfurt).
2. Buat sebuah data source `aws_availability_zones` untuk masing-masing provider tersebut.
3. Cetak daftar AZ dari kedua region tersebut secara bersamaan menggunakan output block.

---

## 19. Challenge
Rancang arsitektur Terraform multi-tier:
- Buat modul root yang membaca CIDR VPC dari mock endpoint API internal menggunakan `data "http"` atau `data "external"`.
- Validasi CIDR tersebut, kemudian delegasikan pembuatan subnet publik ke provider AWS region A, dan pembuatan subnet Disaster Recovery ke provider AWS region B.
- Gunakan data source `vault_generic_secret` untuk menarik metadata tags environment rahasia dan tempelkan tags tersebut ke seluruh resource lintas region.
- Pastikan tidak ada data sensitif yang bocor ke console log output.

---

## 20. Summary
- **Data Sources** bertindak sebagai gerbang *read-only* bagi Terraform untuk mengintegrasikan konteks komputasi eksternal ke dalam DAG dependency graph secara deklaratif.
- Evaluasi data source dapat terjadi pada fase `plan` atau ditunda ke fase `apply` tergantung ketersediaan argumen dependensinya.
- **`terraform_remote_state`** memberikan solusi cepat integrasi antar-stack, namun membawa overhead *tight-coupling* dan risiko keamanan; SSM/Consul menyediakan isolasi yang lebih superior.
- **Provider Aliasing** adalah fondasi orkestrasi skala enterprise untuk skenario multi-region, multi-account, dan hybrid-cloud dalam boundary deklarasi tunggal.
- Integrasi **Vault** dan **External Data Sources** memastikan Terraform dapat memenuhi standar keamanan *zero-static-secrets* dan interoperabilitas sistem tingkat lanjut.

---