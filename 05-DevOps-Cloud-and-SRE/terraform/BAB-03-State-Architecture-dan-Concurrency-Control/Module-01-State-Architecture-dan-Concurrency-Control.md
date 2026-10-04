# Bab 03 / Modul 01: State Architecture & Concurrency Control

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Membedah dan menganalisis struktur internal JSON schema dari Terraform State file (`lineage`, `serial`, `terraform_version`, dan resource metadata).
- Mengonfigurasi dan mengamankan Remote State Backend enterprise-grade menggunakan Amazon S3 dengan DynamoDB state locking, Azure Blob Storage, dan Google Cloud Storage (GCS).
- Menguasai mekanisme Concurrency Control, deteksi race conditions, serta resolusi kebuntuan status (*deadlock* dan *stale locks*) menggunakan CLI `force-unlock`.
- Melakukan manipulasi state secara presisi melalui perintah CLI tingkat lanjut: `state list`, `state show`, `state mv`, `state rm`, `state pull`, dan `state push` tanpa memicu destruksi infrastruktur riil.
- Mengimplementasikan tata kelola keamanan state file, mitigasi plain-text secret exposure, dan enkripsi state baik pada level rest/transit maupun native encryption (Terraform v1.4+).

---

## 2. Prerequisite
Sebelum mempelajari modul ini, Anda wajib memahami:
- Alur kerja deklaratif dasar Terraform: `terraform init`, `plan`, `apply`, dan `destroy`.
- Model konfigurasi provider dan resource HCL (HashiCorp Configuration Language).
- Prinsip dasar Identity and Access Management (IAM) pada minimal satu cloud provider publik (AWS IAM, Azure RBAC, atau GCP IAM).
- Pengetahuan fundamental mengenai format serialisasi data JSON dan mekanisme HTTP/REST API locks.

---

## 3. Concept
Dalam ekosistem Terraform, **State** adalah representasi faktual dari infrastruktur dunia nyata yang dipetakan langsung ke file konfigurasi kode Anda. State bukan sekadar cache lokal, melainkan sebuah basis data transaksional tunggal (*single source of truth*) yang digunakan oleh Terraform Engine untuk:
1. Memetakan deklarasi resource HCL ke identitas resource spesifik di API provider (misalnya, memetakan `aws_instance.web` ke instance ID `i-0abcd1234ef56789a`).
2. Melacak metadata dependensi kompleks yang tidak terekam secara eksplisit pada atribut cloud resource.
3. Mengoptimalkan performa evaluasi plan berskala ribuan resource melalui caching atribut, sehingga meminimalkan latensi API cloud provider.

Karena Terraform beroperasi secara deklaratif dengan membandingkan *Desired State* (kode HCL), *Current State* (pembacaan refresh via API cloud), dan *Recorded State* (state file), integritas dari state file ini bersifat mutlak. Jika dua operator atau pipeline CI/CD mencoba memodifikasi state yang sama secara simultan tanpa koordinasi, akan terjadi **Race Condition** yang dapat merusak file JSON state (*state corruption*) atau memicu duplikasi/penghapusan resource di cloud provider.

Oleh karena itu, arsitektur state modern memisahkan penyimpanan state (*Remote Backend*) dan koordinasi konkurensi (*Distributed State Locking*), memastikan eksekusi Terraform bersifat ACID-like (*Atomicity, Consistency, Isolation, Durability*).

---

## 4. Why
Mengapa arsitektur state dan kontrol konkurensi krusial bagi SRE dan DevOps Engineer?

1. **Pencegahan Bencana Konkurensi (Split-Brain & Race Conditions):**
   Tanpa mekanisme penguncian (*locking*), jika dua runner CI/CD mengeksekusi `terraform apply` secara bersamaan, pembaruan state terakhir akan menimpa (*overwrite*) pembaruan sebelumnya. Hal ini merusak pelacakan resource ID dan memicu *orphan resources* yang terus mengonsumsi anggaran cloud tanpa terpantau.
2. **Refactoring Tanpa Downtime:**
   Ketika arsitektur infrastruktur bertumbuh, Anda harus memecah konfigurasi monolitik menjadi modul-modul independen. Tanpa penguasaan perintah mutasi state (`terraform state mv`), refactoring kode akan dianggap oleh Terraform Engine sebagai instruksi "hapus resource lama lalu buat resource baru", memicu destruksi database atau server produksi.
3. **Pencegahan Kebocoran Rahasia (Secrets Leakage):**
   State file menyimpan seluruh atribut resource dalam format JSON mentah tanpa proteksi default. Atribut sensitif seperti private key TLS, token API, dan password database tersimpan secara *plain-text*. Kegagalan mengamankan remote state file sama dengan membocorkan seluruh kredensial root infrastruktur Anda.
4. **Resiliensi Operasional Pipeline:**
   Ketika pipeline eksekusi crash di tengah proses akibat network timeout atau runner SIGKILL, lock file di backend sering kali tertinggal dalam kondisi aktif (*stale lock*). Pemahaman mendalam mengenai lock token dan mitigasi deadlock memungkinkan pemulihan pipeline secara cepat dan terukur tanpa mengorbankan konsistensi state.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Anatomi Internal Terraform State JSON Schema
Terraform State disimpan dalam format file JSON strictly-typed. Berikut adalah representasi struktur internal (State Schema v4):

```json
{
  "version": 4,
  "terraform_version": "1.8.5",
  "serial": 42,
  "lineage": "b7d2f98e-49b1-4f8e-a226-c56b02a92b23",
  "outputs": {},
  "resources": [
    {
      "mode": "managed",
      "type": "aws_s3_bucket",
      "name": "data_lake",
      "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
      "instances": [
        {
          "schema_version": 0,
          "attributes": {
            "arn": "arn:aws:s3:::corp-data-lake-prod",
            "bucket": "corp-data-lake-prod",
            "id": "corp-data-lake-prod",
            "tags": {
              "Environment": "Production"
            }
          },
          "sensitive_attributes": [],
          "private": "bnVsbA=="
        }
      ]
    }
  ],
  "check_results": null
}
```

Metadata Kunci:
- **`version`**: Versi format schema internal state Terraform (saat ini v4 sejak Terraform 0.12).
- **`terraform_version`**: Versi binary Terraform yang terakhir kali memodifikasi state ini. Mencegah downgrade versi (Terraform menolak membaca state yang ditulis oleh versi yang lebih baru).
- **`lineage`**: UUID acak unik yang dihasilkan saat state pertama kali diinisialisasi. Lineage memastikan bahwa dua state file yang berbeda tidak digabungkan secara tidak sengaja. Jika `lineage` pada remote backend tidak cocok dengan eksekusi lokal, Terraform akan membatalkan operasi.
- **`serial`**: Integer monotonik yang bertambah 1 setiap kali terjadi mutasi state berhasil. Digunakan sebagai mekanisme *optimistic concurrency check*. Jika Terraform mendeteksi `serial` di backend lebih tinggi dari state lokal yang sedang diproses, operasi write ditolak.
- **`resources`**: Array resource yang dikelola, membedakan antara `mode: "managed"` (`resource` block) dan `mode: "data"` (`data` block). Di dalamnya terdapat objek `instances`, menyimpan state atribut aktual, metadata dependensi (`dependencies`), dan status pembuatan/penghapusan (`status: "tainted"` jika ada).

### 5.2 Remote State Backends: Perbandingan Mendalam

| Fitur / Parameter | AWS S3 + DynamoDB | Azure Blob Storage | Google Cloud Storage (GCS) |
| :--- | :--- | :--- | :--- |
| **Backend Identifier** | `s3` | `azurerm` | `gcs` |
| **Storage Element** | S3 Bucket Object (`.tfstate`) | Blob Container (`.tfstate`) | Cloud Storage Bucket Object |
| **Locking Mechanism** | Distributed via DynamoDB Table (`LockID` primary key) | Native Lease Blob API (`x-ms-lease-action: acquire`) | Native Object Preconditions (`if-generation-match`) |
| **Durability SLA** | 99.999999999% (11 9's) | 99.999999999% (11 9's) | 99.999999999% (11 9's) |
| **Encryption at Rest** | SSE-S3, SSE-KMS, Customer Key | Azure Storage SSE, KMS-managed | Google Default Encryption, CMEK |
| **Audit Logging** | AWS CloudTrail + S3 Server Access Logs | Azure Monitor + Storage Analytics | GCP Cloud Audit Logs |

### 5.3 Mekanisme State Locking dan Concurrency
Locking adalah jaminan isolasi mutual-exclusion (Mutex). Saat perintah `terraform plan` (dengan refresh) atau `terraform apply` diinisiasi:

1. **Acquire Lock**: Terraform mengirimkan request penulisan metadata kunci ke mekanisme backend.
   - Pada AWS S3 + DynamoDB, Terraform menulis sebuah item ke tabel DynamoDB dengan primary key `LockID`:
     ```json
     {
       "LockID": {"S": "bucket-name/path/to/terraform.tfstate-md5"},
       "Info": {
         "S": "{\"ID\":\"e4a1f6c2-0749-813f-bf83-05b1c8f1e62a\",\"Operation\":\"OperationTypeApply\",\"Info\":\"\",\"Who\":\"runner@ci-node-04\",\"Version\":\"1.8.5\",\"Created\":\"2025-01-15T10:00:00Z\",\"Path\":\"bucket-name/path/to/terraform.tfstate\"}"
       }
     }
     ```
   - Operasi ini menggunakan DynamoDB *Conditional Writes* (`attribute_not_exists(LockID)`). Jika record sudah ada, penulisan gagal dengan HTTP status 400 (`ConditionalCheckFailedException`), dan proses mengembalikan error: `Error acquiring the state lock`.
2. **Execute Operation**: Terraform Engine mengeksekusi refresh, perbandingan DAG graph, dan API provider invocation.
3. **Release Lock**: Setelah state baru dengan nomor `serial` baru ditulis ke S3, Terraform menghapus item `LockID` dari DynamoDB.

#### Deadlocks dan Penanganan Stale Locks
Deadlock terjadi ketika runner CI/CD menerima sinyal pemutusan paksa (misal `SIGKILL`, VM preemption, network disconnect total) sebelum langkah *Release Lock* tereksekusi. Record penguncian tetap tertinggal di DynamoDB/Blob.
Untuk mengatasinya, CLI menyediakan:
```bash
terraform force-unlock <LOCK-ID>
```
*Aturan Mutlak:* Perintah `force-unlock` **hanya boleh** dieksekusi setelah memvalidasi secara manual bahwa TIDAK ADA proses CI/CD atau operator lain yang sedang menjalankan apply pada state tersebut. Mengeksekusi `force-unlock` pada apply yang sedang berjalan aktif akan merusak state secara permanen.

### 5.4 State Manipulation via CLI
Manipulasi langsung terhadap file `.tfstate` via teks editor dilarang keras karena risiko merusak checksum, validasi schema, dan penomoran serial. Gunakan CLI toolchain:

- `terraform state list [options] [address...]`: Menginspeksi resource address yang saat ini tercatat di dalam state.
- `terraform state show <address>`: Menampilkan seluruh atribut JSON dari suatu resource tertentu secara terstruktur.
- `terraform state mv <source> <destination>`: Mengubah alamat resource tanpa menghancurkan objek fisik di cloud. Digunakan untuk:
  - Mengganti nama resource HCL.
  - Memindahkan resource dari modul *root* ke *child module*.
  - Migrasi resource antar state file berbeda (`terraform state mv -state-out=...`).
- `terraform state rm <address>`: Menghapus resource dari pelacakan state file tanpa mengeksekusi API delete ke cloud provider (*unmanage resource*).
- `terraform state pull`: Mengunduh state saat ini dari remote backend dan mencetaknya ke `stdout` (berguna untuk backup lokal atau automasi audit).
- `terraform state push <file>`: Mengunggah state lokal ke remote backend secara manual. Memerlukan verifikasi serial dan lineage yang ketat (bisa dipaksa dengan `-force`, namun sangat berisiko).

### 5.5 Sensitive Data dan Enkripsi State File
Masalah struktural terbesar dalam Terraform: **State file menyimpan secret secara plain-text**. Resource seperti `aws_db_instance`, `tls_private_key`, atau `vault_generic_secret` menyimpan master password atau private key dalam atribut JSON tanpa hashing atau masking.

Mitigasi Berjenjang:
1. **Server-Side Encryption (Rest & Transit):**
   Backend S3/Azure/GCS wajib menggunakan Customer Managed Keys (AWS KMS, Azure Key Vault, GCP Cloud KMS) dengan kebijakan rotasi otomatis dan restriksi ketat `kms:Decrypt`.
2. **Strict IAM RBAC:**
   Akses langsung ke Storage Bucket dan State Path harus diblokir untuk seluruh engineer. Hanya runner service identity (CI/CD role) yang memiliki izin `s3:GetObject`, `s3:PutObject`, dan `dynamodb:*`.
3. **Native Terraform State Encryption (Terraform v1.4+ / OpenTofu):**
   Penggunaan blok konfigurasi `encryption` native yang mengenkripsi payload state sebelum dikirimkan ke backend menggunakan provider KMS atau PBKDF2/AES-GCM.

---

## 6. How
Berikut adalah alur implementasi Remote State Architecture standar produksi:

1. **Bootstraping Remote State Storage:**
   Deploy bucket S3 dan DynamoDB table melalui pipeline fondasi atau CloudFormation/CLI terpisah sebelum proyek infrastruktur utama diinisialisasi.
2. **Definisikan Backend Block pada Konfigurasi Terraform:**
   Buat file `backend.tf` yang mendefinisikan bucket S3, key path spesifik, region, DynamoDB lock table, dan KMS Key ID.
3. **Migrasi State Lokal ke Remote:**
   Jalankan `terraform init -migrate-state` untuk mentransfer data state lokal eksisting ke remote backend secara aman.
4. **Verifikasi Enkripsi dan Mutex Lock:**
   Uji skenario lock dengan menjalankan `terraform plan` di dua terminal terpisah secara simultan.

---

## 7. Analogy
Bayangkan Terraform State sebagai **Buku Besar Tanah (Land Registry)** di kantor pertanahan:
- **Cloud Infrastructure** adalah tanah dan bangunan fisik yang nyata.
- **Terraform Configuration (HCL)** adalah cetak biru arsitektur bangunan yang Anda ajukan.
- **State File (`.tfstate`)** adalah sertifikat dan catatan kepemilikan resmi yang mencatat bahwa bangunan di koordinat X dimiliki oleh kavling Y.
- **Remote Backend** adalah brankas anti-kebakaran di kantor pertanahan tempat buku besar disimpan.
- **DynamoDB State Lock** adalah **Tanda Antrean Tunggal** di loket pertanahan. Hanya satu notaris yang boleh membuka buku besar pada satu waktu. Jika notaris A sedang menulis, notaris B harus menunggu di luar. Jika notaris A pingsan saat menulis (*crash*), kepala loket harus memverifikasi bahwa notaris A benar-benar sudah dievakuasi sebelum memanggil notaris B (*force-unlock*).

---

## 8. Diagram (ASCII)

### Siklus Concurrency Control dan State Locking

```
+-----------------------------------------------------------------------------------+
|                                OPERATOR / CI PIPELINE                             |
|       Terminal A: "terraform apply"             Terminal B: "terraform apply"     |
+-----------------------------------------------------------------------------------+
                         |                                          |
        (1) Acquire Lock |                         (1) Acquire Lock |
                         v                                          v
+-----------------------------------------------------------------------------------+
|                        DISTRIBUTED LOCK ENGINE (DynamoDB)                         |
|                                                                                   |
|   Record: LockID = "corp/prod/state-md5"                                          |
|   Holder: Terminal A (ID: e4a1f6c2...)                                            |
|                                                                                   |
|   [Terminal A -> SUCCEEDED]                   [Terminal B -> FAILED / REJECTED]   |
+-----------------------------------------------------------------------------------+
             |                                              |
             | Proceed                                      | Wait / Abort
             v                                              v
+-----------------------------+           +-----------------------------------------+
|    TERRAFORM ENGINE (A)     |           |          TERRAFORM ENGINE (B)           |
|                             |           |                                         |
| 1. Read Remote State        |           | Output Error:                           |
| 2. Provider API Refresh     |           | "Error: Error acquiring the state lock: |
| 3. Compute DAG Graph Diffs  |           |  ConditionalCheckFailedException..."    |
| 4. Execute Cloud Mutations  |           | Process exits with exit code != 0       |
+-----------------------------+           +-----------------------------------------+
             |
             | (Write New State with serial + 1)
             v
+-----------------------------------------------------------------------------------+
|                       REMOTE STORAGE BACKEND (Amazon S3)                          |
|                                                                                   |
|   Object: corp/prod/terraform.tfstate                                             |
|   Metadata: version=4, serial=43, lineage=b7d2f98e...                             |
|   Encryption: AWS KMS (SSE-KMS)                                                   |
+-----------------------------------------------------------------------------------+
             |
             | (Success Write)
             v
+-----------------------------------------------------------------------------------+
|                        DISTRIBUTED LOCK ENGINE (DynamoDB)                         |
|                                                                                   |
|   (2) Release Lock: DELETE item where LockID = "corp/prod/state-md5"              |
|   Status: UNLOCKED                                                                |
+-----------------------------------------------------------------------------------+
```

---

## 9. Simple Example
Konfigurasi sederhana backend lokal versus konfigurasi remote backend pada AWS:

```hcl
# backend.tf - Mengonfigurasi remote state di AWS S3 dengan DynamoDB locking
terraform {
  required_version = ">= 1.5.0"
  
  backend "s3" {
    bucket         = "production-terraform-states-bucket"
    key            = "networking/vpc/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "terraform-state-lock-table"
    encrypt        = true
  }
}
```

Inisialisasi backend:
```bash
terraform init
```

---

## 10. Practical Example (Konfigurasi CLI / Terraform / Kode Hands-on)

### Skenario: Setup Komprehensif S3 Backend + DynamoDB Table + State Manipulation & Locking Test

#### 10.1 Kode Terraform untuk Bootstrap Backend Infrastructure (`bootstrap/main.tf`)
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

# KMS Key untuk enkripsi state file
resource "aws_kms_key" "terraform_state_key" {
  description             = "KMS Key for Terraform State Storage"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Environment = "Core-Infra"
    ManagedBy   = "Terraform"
  }
}

# S3 Bucket untuk State Storage
resource "aws_s3_bucket" "terraform_state" {
  bucket        = "acme-corp-prod-tfstate-ap-southeast-1"
  force_destroy = false

  lifecycle {
    prevent_destroy = true
  }
}

# Versi S3 Bucket Wajib Diaktifkan untuk Histori State
resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Server-side Encryption menggunakan KMS
resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.terraform_state_key.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

# Blokir seluruh akses publik ke state bucket
resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# DynamoDB Table untuk Distributed Locking
resource "aws_dynamodb_table" "terraform_locks" {
  name         = "acme-corp-prod-tflocks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = {
    Environment = "Core-Infra"
    ManagedBy   = "Terraform"
  }
}
```

#### 10.2 Konfigurasi Root Module Pengguna Backend (`app/main.tf`)
```hcl
terraform {
  required_version = ">= 1.5.0"
  
  backend "s3" {
    bucket         = "acme-corp-prod-tfstate-ap-southeast-1"
    key            = "services/payment-gateway/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "acme-corp-prod-tflocks"
    encrypt        = true
  }

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

resource "aws_sqs_queue" "primary_queue" {
  name                      = "payment-processing-queue"
  delay_seconds             = 0
  max_message_size          = 262144
  message_retention_seconds = 86400
}
```

#### 10.3 CLI Hands-on: Demonstrasi Mutasi State Tanpa Downtime
```bash
# 1. Inisialisasi dan deploy resource awal
terraform init
terraform apply -auto-approve

# 2. Periksa daftar resource di dalam remote state
terraform state list
# Output:
# aws_sqs_queue.primary_queue

# 3. Tampilkan detail data yang terekam pada remote state
terraform state show aws_sqs_queue.primary_queue

# 4. Melakukan Refactoring HCL: Mengubah nama resource block di HCL
# Ubah `aws_sqs_queue.primary_queue` menjadi `aws_sqs_queue.payment_pipeline`
# Jika langsung menjalankan plan, Terraform akan menghapus queue lama dan membuat queue baru!
# Lakukan state move untuk memperbarui pointer tanpa destruksi fisik:
terraform state mv aws_sqs_queue.primary_queue aws_sqs_queue.payment_pipeline
# Output:
# Move "aws_sqs_queue.primary_queue" to "aws_sqs_queue.payment_pipeline"
# Successfully moved 1 object(s).

# 5. Verifikasi bahwa tidak ada destruksi
terraform plan
# Output:
# No changes. Your infrastructure matches the configuration.

# 6. Menghapus resource dari pelacakan Terraform tanpa menghapus objek di AWS
terraform state rm aws_sqs_queue.payment_pipeline
# Output:
# Removed aws_sqs_queue.payment_pipeline
# Successfully removed 1 resource instance(s).
```

---

## 11. Real World Example
### Studi Kasus: Pemecahan Monolithic State 8.000 Resource Menjadi Micro-States pada Fintech Tier-1

#### Masalah:
Sebuah perusahaan perbankan digital memiliki file `terraform.tfstate` monolitik seukuran 45 MB yang mengelola 8.000+ resource (VPC, EKS, RDS, IAM, S3, Security Groups). Setiap eksekusi `terraform plan` memakan waktu 45 menit akibat API rate-limiting dari AWS. Selain itu, 40 orang engineer sering mengalami kebuntuan locking DynamoDB, menghentikan deployment seluruh divisi.

#### Solusi Arsitektural:
State dipecah menjadi 4 domain terisolasi:
1. `core-network.tfstate` (VPC, Subnet, Transit Gateway)
2. `compute-platform.tfstate` (EKS Clusters, Worker Nodes)
3. `data-layer.tfstate` (RDS Postgres, Redis ElastiCache)
4. `applications.tfstate` (Helm releases, IAM roles)

#### Eksekusi Migrasi State Tanpa Re-creation:
Tim platform mengunduh state menggunakan `terraform state pull`, lalu memindahkan resource secara programmatic menggunakan `terraform state mv` cross-state migration:

```bash
# 1. Tarik state monolitik lokal
terraform state pull > monolith.tfstate

# 2. Pindahkan RDS instance keluar dari monolith ke file data-layer
terraform state mv \
  -state=monolith.tfstate \
  -state-out=data-layer.tfstate \
  aws_db_instance.core_database \
  aws_db_instance.core_database

# 3. Pindahkan resource ke direktori baru yang memiliki backend terpisah
cd ../layers/data-layer
terraform init
terraform state push ../../migration/data-layer.tfstate

# 4. Verifikasi isolasi plan di layer baru
terraform plan
# Hasil: No changes. RDS instance ID berhasil diadopsi tanpa memicu reboot atau terminasi database!
```

#### Hasil:
- Waktu eksekusi `terraform plan` turun drastis dari 45 menit menjadi 40 detik per domain.
- Blast radius berkurang drastis: insiden kesalahan konfigurasi pada layer aplikasi tidak lagi berisiko menghapus database atau routing VPC.
- Concurrency contention antar engineer berkurang hingga 95%.

---

## 12. Trade-offs
Memilih arsitektur remote state dan tingkat granularitas state melibatkan trade-off teknis:

- **Monolithic State vs Micro-States:**
  - *Monolithic State*: Keuntungan referensi data antar-resource mudah (cukup referensi langsung `aws_vpc.main.id`). Kerugian: Waktu refresh sangat lambat, lock contention tinggi, blast radius catastrophic jika state korup.
  - *Micro-States*: Keuntungan isolasi kegagalan sempurna, eksekusi super cepat, lock isolation per tim. Kerugian: Membutuhkan data sharing overhead menggunakan `terraform_remote_state` data sources atau SSM Parameter Store / Consul.
- **Strict Locking vs Skip Locking (`-lock=false`):**
  - Mengabaikan lock (`terraform plan -lock=false`) mempercepat eksekusi read-only di pipeline audit. Namun, jika digunakan pada `apply`, berisiko tinggi memicu race condition yang merusak state serial integrity.
- **Client-Side Native Encryption vs Backend SSE-KMS:**
  - Enkripsi native Terraform v1.4+ mengamankan secret di memori sebelum keluar ke jaringan. Namun, memperkenalkan dependensi manajemen passphrase/key lokal yang jika hilang mengakibatkan state tidak dapat didekripsi selamanya (*unrecoverable data loss*).

---

## 13. When To Use
Gunakan Remote State dengan Concurrency Locking saat:
- Infrastruktur dikelola oleh lebih dari 1 orang atau dieksekusi otomatis via pipeline CI/CD (GitHub Actions, GitLab CI, Atlantis, Terraform Cloud).
- Mengelola resource produksi yang membutuhkan auditabilitas tingkat tinggi, enkripsi wajib, dan backup snapshot otomatis (*S3 Object Versioning*).
- Memisahkan arsitektur lingkungan (*Dev, Staging, Prod*) dan domain sistem (*Networking, Database, K8s*) untuk membatasi akses hak istimewa (Least Privilege).

---

## 14. When NOT To Use
Jangan gunakan konfigurasi Remote State kompleks saat:
- Pengujian modul terisolasi (*unit testing*) menggunakan `terraform-exec` atau framework testing lokal ephemeral yang langsung dihancurkan dalam hitungan detik.
- Eksperimen lokal yang bersifat *throwaway* tanpa dependensi cloud eksternal. (Gunakan backend default `local` untuk skenario ini).

---

## 15. Common Mistakes
1. **Mengabaikan S3 Bucket Versioning:**
   Tidak mengaktifkan versioning pada S3 bucket remote state. Saat terjadi korupsi file JSON state atau kesalahan `terraform state push -force`, state lama tertimpa permanen dan tidak bisa di-rollback.
2. **Commit File `.tfstate` ke Repository Git:**
   Menyimpan file state lokal di Git repository publik maupun privat. Hal ini langsung mengekspos semua secret, private key, dan arsitektur internal ke riwayat commit Git.
3. **Mengeksekusi `force-unlock` Tanpa Verifikasi:**
   Menjalankan `terraform force-unlock` begitu melihat pesan error penguncian, tanpa memeriksa apakah ada pipeline Jenkins/GitLab yang sedang berjalan lambat di background. Hal ini menyebabkan dua proses apply menulis secara bersamaan dan merusak state serial.
4. **Hardcoding Secret di Variabel Konfigurasi Backend:**
   Menuliskan access key dan secret key cloud langsung di dalam blok `backend "s3"`. Konfigurasi backend seharusnya kosong (*partial configuration*) dan diinjeksi via environment variables (`AWS_ACCESS_KEY_ID`, `AWS_ROLE_ARN`).

---

## 16. Best Practices
1. **Enforce S3 Versioning & Lifecycle Deletion Protection:**
   Aktifkan *S3 Object Versioning* dan aktifkan MFA Delete atau Lifecycle Glacier Backup untuk snapshot file state historis.
2. **KMS Customer-Managed Keys (CMK) dengan Rotasi:**
   Gunakan KMS key terpisah khusus Terraform State dengan enkripsi SSE-KMS, bukan SSE-S3 default, untuk mengontrol granularitas siapa yang bisa melakukan `kms:Decrypt`.
3. **IAM Least Privilege Policy:**
   Terapkan IAM policy ketat: pengembang biasa hanya diberikan akses `s3:GetObject` pada environment non-produksi, dan hanya pipeline automation role yang memiliki hak `s3:PutObject` serta `dynamodb:*` di produksi.
4. **Implementasikan Micro-States via Directory/Workspace:**
   Pisahkan state file per layer (Network, Platform, App) dan per Environment (Dev, Prod) sehingga ukuran satu file state tidak melebihi 100-200 resource.
5. **Simpan Backup State Sebelum Operasi Mutasi:**
   Selalu jalankan `terraform state pull > state-backup-$(date +%s).json` sebelum mengeksekusi operasi `state mv` atau `state rm`.

---

## 17. Troubleshooting
Panduan mitigasi kendala operasional state:

### Kasus A: "Error: Error acquiring the state lock"
*Indikasi:*
```text
Error: Error acquiring the state lock
Lock Info:
  ID:        a8b3879d-327a-8f0a-0498-75e119ff0894
  Path:      acme-corp-tfstate/prod/terraform.tfstate
  Operation: OperationTypeApply
  Who:       runner@github-runner-vm-02
  Created:   2025-01-15 04:12:00.123456789 +0000 UTC
```
*Langkah Remediasi:*
1. Hubungi pemegang lock yang tercatat di atribut `Who`, atau periksa job ID di CI/CD runner.
2. Jika terbukti bahwa proses tersebut telah mati (*crashed* / dibatalkan paksa), buka kunci menggunakan ID yang ditampilkan:
   ```bash
   terraform force-unlock a8b3879d-327a-8f0a-0498-75e119ff0894
   ```
3. Jika backend DynamoDB gagal merespons, verifikasi secara manual isi tabel DynamoDB via AWS CLI:
   ```bash
   aws dynamodb get-item \
     --table-name acme-corp-prod-tflocks \
     --key '{"LockID": {"S": "acme-corp-tfstate/prod/terraform.tfstate-md5"}}'
   ```

### Kasus B: State File Corrupted / Invalid JSON
*Indikasi:* Eksekusi `terraform plan` mengembalikan error: `Error loading state: state data in S3 does not look like a valid state file (failed to decode JSON)`.
*Langkah Remediasi:*
1. Akses S3 Bucket Versioning via AWS Management Console atau CLI.
2. Temukan versi state terakhir yang valid sebelum crash:
   ```bash
   aws s3api list-object-versions --bucket acme-corp-prod-tfstate-ap-southeast-1 --prefix services/payment-gateway/
   ```
3. Pulihkan (*restore*) versi sebelumnya atau unduh versi tersebut dan dorong secara paksa:
   ```bash
   aws s3api get-object --bucket <BUCKET> --key <KEY> --version-id <VALID_VERSION_ID> recovered_state.json
   terraform state push recovered_state.json
   ```

### Kasus C: "State Lineage Mismatch"
*Indikasi:* Terjadi saat mencoba melakukan `terraform state push` atau mengubah remote backend:
`Error: State lineage mismatch. Expected lineage b7d2..., got c8e4...`
*Penyebab:* Anda mencoba menimpa state dari arsitektur atau infrastruktur yang sama sekali berbeda.
*Langkah Remediasi:* Verifikasi kembali path backend S3 key Anda. Jangan gunakan parameter `-force` kecuali Anda sedang melakukan disaster recovery terencana dan yakin bahwa state lama memang harus dihapus secara menyeluruh.

---

## 18. Exercise
Selesaikan instruksi berikut:
1. Konfigurasikan secara lokal sebuah module Terraform yang mendefinisikan 3 resource dummy menggunakan provider `local` (misalnya 3 buah `local_file` dengan nama file: `app.conf`, `db.conf`, `cache.conf`).
2. Jalankan `terraform apply` untuk membuat resource dan menginisialisasi state lokal.
3. Gunakan perintah `terraform state mv` untuk memindahkan resource `local_file.cache` ke dalam child module baru bernama `module.storage.local_file.cache`.
4. Jalankan `terraform plan` dan buktikan bahwa Terraform melaporkan: `0 to add, 0 to change, 0 to destroy`.
5. Hapus pelacakan `local_file.db` dari state menggunakan `terraform state rm` tanpa menghapus file fisiknya di disk Anda.

---

## 19. Challenge
**Scenario:**
Anda adalah Lead Platform Engineer di sebuah startup unicorn. Terjadi insiden di mana engineer junior menjalankan commit script `apply` yang terhenti paksa di CI/CD, meninggalkan state dalam kondisi terkuci (stale lock). Pada saat yang sama, seorang engineer lain tidak sengaja meregistrasikan kredensial database produksi berupa master password di dalam resource HCL yang terekam pada state file.

**Tugas Anda:**
1. Rancang arsitektur S3 Remote Backend + DynamoDB Lock yang dilengkapi Terraform 1.4+ Native State Client-Side Encryption block menggunakan AES-GCM.
2. Tuliskan runbook operasional CLI step-by-step untuk:
   - Melepaskan stale lock secara aman.
   - Mengambil state via `terraform state pull`.
   - Mengidentifikasi plain-text password di dalam JSON state.
   - Melakukan sanitasi/redaksi tanpa merusak serial integrity dan format schema v4.
   - Mendorong kembali state yang telah bersih ke S3 bucket menggunakan `terraform state push`.

---

## 20. Summary
- Terraform State bukan sekadar cache, melainkan basis data deklaratif transaksional yang memetakan kode HCL ke entitas API cloud fisik.
- Schema State v4 bergantung pada kombinasi `lineage` (identitas unik state) dan `serial` (urutan mutasi monotonik) untuk menjamin integritas ACID-like.
- Remote State Backend (S3, Azure Blob, GCS) wajib dipadukan dengan mekanisme distributed lock (DynamoDB, Native Blob Leases) untuk mencegah kerusakan state akibat race conditions.
- Deadlock dan stale locks dapat diatasi menggunakan `terraform force-unlock <LOCK-ID>` dengan verifikasi ketat bahwa runner telah sepenuhnya non-aktif.
- CLI mutasi state (`state mv`, `state rm`, `state pull`, `state push`) adalah instrumen utama SRE untuk refactoring arsitektur tanpa downtime dan tanpa destruksi infrastruktur riil.
- Enkripsi multi-lapis (At-Rest, In-Transit, IAM Policy least-privilege, dan Client-Side State Encryption) adalah prasyarat mutlak untuk melindungi secret yang terekam pada file state.