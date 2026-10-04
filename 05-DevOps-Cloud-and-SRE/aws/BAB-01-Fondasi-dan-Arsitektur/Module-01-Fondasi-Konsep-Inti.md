# Bab 01: AWS Cloud Foundations & Global Infrastructure Architecture
## Module 01: Global Infrastructure, Shared Responsibility Model, dan IAM Core Foundations

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis** topologi AWS Global Infrastructure (Regions, Availability Zones, Local Zones, dan Edge Locations) untuk merancang arsitektur sistem yang memenuhi Service Level Agreement (SLA) minimal 99.99%.
- **Mendekonstruksi** batasan AWS Shared Responsibility Model pada lapisan IaaS, PaaS, dan SaaS guna memitigasi celah keamanan kepatuhan (*compliance gap*).
- **Mengimplementasikan** fondasi identitas menggunakan AWS Identity and Access Management (IAM) berbasis prinsip *Least Privilege* dan *Zero Trust Architecture*.
- **Menuliskan** Infrastructure as Code (IaC) menggunakan Terraform untuk mengotomatisasi struktur dasar IAM Policy, IAM Role, dan Service Control Policies (SCP).

---

### 2. Concept
AWS Global Infrastructure adalah fondasi fisik dan logis terdistribusi secara global yang memungkinkan eksekusi beban kerja komputasi, penyimpanan, dan jaringan dengan latensi rendah serta redundansi tinggi. Memahami infrastruktur ini bukan sekadar menghafal lokasi data center, melainkan memahami isolasi *fault domains* (domain kegagalan).

Tiga pilar fisik/logis utama meliputi:
1. **Region**: Wilayah geografis terisolasi yang berisi minimal tiga Availability Zones (AZ) terpisah.
2. **Availability Zone (AZ)**: Satu atau lebih data center diskret dengan redundansi daya, pendingin, dan jaringan fisik independen, terhubung melalui jaringan *ultra-low latency private metro fiber*.
3. **Edge Network (CloudFront PoPs / Points of Presence)**: Titik distribusi konten global untuk *caching*, mitigasi DDoS (AWS Shield), dan komputasi di *edge* (Lambda@Edge, CloudFront Functions).

Konsep ini diikat oleh **AWS Shared Responsibility Model**, sebuah kontrak operasional yang mendefinisikan batas tanggung jawab mutlak antara AWS ("Security *OF* the Cloud") dan Pelanggan ("Security *IN* the Cloud").

---

### 3. Why It Matters
Kegagalan memahami batasan infrastruktur dan model tanggung jawab AWS secara berulang menjadi akar penyebab insiden fatal di industri:
- **Kegagalan Disaster Recovery (DR)**: Menganggap *multi-datacenter* lokal setara dengan Multi-AZ di AWS sering kali menyebabkan *single point of failure* (SPOF) pada level *networking plane*.
- **Pelanggaran Data Skala Masif**: Lebih dari 80% insiden kebocoran data di cloud terjadi bukan karena eksploitasi pada hypervisor AWS, melainkan miskonfigurasi IAM (Security *IN* the Cloud) seperti *wildcard permissions* (`"Action": "*"`) dan kunci akses jangka panjang (*long-lived access keys*) yang bocor.
- **Latensi Tinggi dan Pemborosan Finansial**: Pemilihan Region yang salah memicu penalti latensi jaringan (RTT tinggi) dan biaya egress data (*data transfer out*) yang eksponensial.

---

### 4. What It Is (Deep-Dive Teknis)

#### A. Anatomi AWS Region dan AZ
Setiap Region memiliki kode penamaan standar (contoh: `ap-southeast-1` untuk Singapura, `ap-southeast-3` untuk Jakarta). Di dalam sebuah region:
- **AZ Independence**: Jarak antar-AZ dirancang cukup jauh (biasanya puluhan kilometer) untuk mencegah bencana alam tunggal (misal: banjir, gempa bumi lokal, putusnya pasokan listrik regional) melumpuhkan lebih dari satu AZ, namun cukup dekat (< 1-2 ms *round-trip time*) untuk memungkinkan replikasi data sinkron.
- **AZ Randomization**: Untuk mendistribusikan beban secara merata di seluruh kapasitas fisik, AWS memetakan kode AZ (misal `ap-southeast-1a`) secara acak ke pengenal fisik (*AZ ID*, misal `apse1-az1`) untuk setiap akun AWS yang berbeda.

#### B. The Shared Responsibility Spectrum
Tanggung jawab bergeser secara dinamis tergantung pada model komputasi yang dipilih:

| Layer Arsitektur | IaaS (EC2) | PaaS (RDS, Elastic Beanstalk) | Serverless / SaaS (Lambda, S3, DynamoDB) |
| :--- | :--- | :--- | :--- |
| **Akses Pelanggan & Data IAM** | Pelanggan | Pelanggan | Pelanggan |
| **Aplikasi / Kode** | Pelanggan | Pelanggan | Pelanggan |
| **Sistem Operasi & Patching** | Pelanggan | **AWS** | **AWS** |
| **Konfigurasi Database Engine**| Pelanggan | Pelanggan / AWS Bersama | **AWS** |
| **Network & Firewall (VPC/SG)** | Pelanggan | Pelanggan | **AWS** (IAM & Resource Policies) |
| **Hypervisor & Fisik Hardware** | **AWS** | **AWS** | **AWS** |

---

### 5. How It Works (Mekanisme Internal IAM & Evaluasi Kebijakan)

Saat sebuah entitas (User, Role, Federated Identity) melakukan API call ke AWS, request tersebut melewati alur evaluasi otorisasi yang deterministik:

```
[Incoming API Request: Action, Resource, Context]
                       │
                       ▼
         ┌───────────────────────────┐
         │ Is there an Explicit DENY?│ ──(YES)──► [ DENY ACCESS ]
         └───────────────────────────┘
                       │ (NO)
                       ▼
         ┌───────────────────────────┐
         │ Organizations SCP Allow?  │ ──(NO)───► [ DENY ACCESS ]
         └───────────────────────────┘
                       │ (YES)
                       ▼
         ┌───────────────────────────┐
         │ Resource-based Policy OK? │ ──(YES)──► [ ALLOW ACCESS ]*
         └───────────────────────────┘
                       │ (NO/Not Present)
                       ▼
         ┌───────────────────────────┐
         │ IAM Identity-based Policy?│ ──(NO)───► [ DENY ACCESS (Implicit) ]
         └───────────────────────────┘
                       │ (YES - Explicit Allow)
                       ▼
         ┌───────────────────────────┐
         │  Permissions Boundary OK? │ ──(NO)───► [ DENY ACCESS ]
         └───────────────────────────┘
                       │ (YES)
                       ▼
         ┌───────────────────────────┐
         │   Session Policy Allow?   │ ──(NO)───► [ DENY ACCESS ]
         └───────────────────────────┘
                       │ (YES)
                       ▼
               [ ALLOW ACCESS ]
```
*\*Catatan: Jika ada boundary atau SCP, evaluasi eksplisit ALLOW tetap harus melewati gerbang tersebut.*

1. **Default Deny**: Semua request secara bawaan ditolak (*implicit deny*).
2. **Explicit Deny Precedence**: Satu saja instruksi `"Effect": "Deny"` di level mana pun (SCP, Boundary, Identity Policy, Resource Policy) akan langsung membatalkan seluruh izin evaluasi.
3. **Short-Term Credentials via AWS STS**: IAM Role tidak memiliki kredensial permanen. Instance EC2 atau Pod Kubernetes menggunakan instance metadata / OIDC token untuk memanggil AWS Security Token Service (STS) dan menerima pasangan Access Key ID, Secret Access Key, dan Session Token sementara dengan masa kedaluwarsa (15 menit - 12 jam).

---

### 6. System Architecture Diagram

Berikut arsitektur Multi-AZ High-Availability yang mendistribusikan beban secara independen di atas fondasi AWS Global Infrastructure:

```
+-----------------------------------------------------------------------------------+
| AWS Cloud (Region: ap-southeast-1)                                                |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | VPC: 10.0.0.0/16                                                            |
|  |                                                                             |
|  |  +-----------------------------------+   +--------------------------------+ |  |
|  |  | Availability Zone A               |   | Availability Zone B            | |  |
|  |  | (AZ-ID: apse1-az1)                |   | (AZ-ID: apse1-az2)             | |  |
|  |  |                                   |   |                                | |  |
|  |  |  [Public Subnet A: 10.0.1.0/24]   |   |  [Public Subnet B: 10.0.2.0/24]| |  |
|  |  |  +-----------------------------+  |   |  +---------------------------+ | |  |
|  |  |  | Application Load Balancer   |◀═╪═══╪═▶| ALB Node (Cross-Zone)     | | |  |
|  |  |  +--------------┬--------------+  |   |  +-------------┬-------------+ | |  |
|  |  +-----------------┼-----------------+   +----------------┼---------------+ |  |
|  |                    │                                      │                 |  |
|  |                    ▼                                      ▼                 |  |
|  |  +-----------------┴-----------------+   +----------------┴---------------+ |  |
|  |  |  [Private Subnet A: 10.0.10.0/24] |   |  [Private Subnet B: 10.0.20.0/24| |  |
|  |  |  +-----------------------------+  |   |  +---------------------------+ | |  |
|  |  |  | EC2 App Instance (Role)     |  |   |  | EC2 App Instance (Role)   | | |  |
|  |  |  +--------------┬--------------+  |   |  +-------------┬-------------+ | |  |
|  |  +-----------------┼-----------------+   +----------------┼---------------+ |  |
|  |                    │ (Synchronous Replication)            │                 |  |
|  |                    ▼                                      ▼                 |  |
|  |  +-----------------┴-----------------+   +----------------┴---------------+ |  |
|  |  |  [Database Subnet A: 10.0.100.0]  |   |  [Database Subnet B: 10.0.101.0| |  |
|  |  |  +-----------------------------+  |   |  +---------------------------+ | |  |
|  |  |  | Amazon RDS Master           |══╪═══╪═▶| Amazon RDS Standby (Replica)  | |
|  |  |  +-----------------------------+  |   |  +---------------------------+ | |  |
|  |  +-----------------------------------+   +--------------------------------+ |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

### 7. Component Breakdown

1. **Virtual Private Cloud (VPC)**: Jaringan virtual terisolasi secara logis milik akun AWS Anda. Mencakup alokasi blok CIDR IPv4/IPv6.
2. **Subnets (Public vs Private)**: 
   - *Public*: Memiliki route tabel yang mengarah ke Internet Gateway (IGW).
   - *Private*: Tidak memiliki rute langsung ke IGW; akses outbound internet dialirkan melalui NAT Gateway yang berada di public subnet.
3. **Availability Zones**: Entitas fisik tempat subnet dialokasikan. Subnet tidak bisa melintasi batas AZ (*subnet is bound to a single AZ*).
4. **IAM Role**: Identitas dengan izin terdefinisi yang dapat diasumsikan (*assume*) oleh layanan AWS, user federasi, atau aplikasi, memutus kebiasaan hardcoding API credentials.
5. **Security Groups**: Firewall virtual *stateful* di tingkat instans yang mengontrol lalu lintas masuk (*inbound*) dan keluar (*outbound*).

---

### 8. Simple Code / Config Example

#### Contoh Kebijakan IAM: Least Privilege S3 Read-Only Policy Terbatas pada Bucket Tertentu
File: `s3_read_policy.json`
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListBucketContents",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::production-financial-reports-2024"
    },
    {
      "Sid": "ReadBucketObjects",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::production-financial-reports-2024/*"
    }
  ]
}
```

Uji validasi JSON Policy melalui AWS CLI:
```bash
aws iam create-policy \
    --policy-name ProductionFinancialReportsReadOnly \
    --policy-document file://s3_read_policy.json \
    --description "Akses read-only khusus bucket laporan keuangan"
```

---

### 9. Practical / Production-Ready Example (Terraform HCL)

Contoh produksi berikut membuat IAM Role untuk instans backend EC2, menerapkan prinsip *no static keys*, membatasi operasi hanya pada DynamoDB di Region lokal, serta menolak akses non-TLS.

```hcl
# main.tf

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

# 1. Trust Policy: Menentukan entitas mana yang dapat meng-assume Role ini
data "aws_iam_policy_document" "ec2_trust_policy" {
  statement {
    sid     = "EC2AssumeRolePolicy"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "app_backend_role" {
  name                 = "AppBackendServiceRole"
  assume_role_policy   = data.aws_iam_policy_document.ec2_trust_policy.json
  max_session_duration = 3600 # 1 jam

  tags = {
    Environment = "Production"
    ManagedBy   = "Terraform"
  }
}

# 2. Permission Policy: Pembatasan ketat terhadap resource dan kondisi jaringan
data "aws_iam_policy_document" "dynamodb_restricted_access" {
  statement {
    sid    = "AllowDynamoDBItemOperations"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:Query"
    ]
    resources = [
      "arn:aws:dynamodb:ap-southeast-1:*:table/CustomerOrders"
    ]
  }

  statement {
    sid    = "EnforceSecureTransport"
    effect = "Deny"
    actions = [
      "dynamodb:*"
    ]
    resources = [
      "arn:aws:dynamodb:ap-southeast-1:*:table/CustomerOrders"
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_iam_policy" "backend_dynamo_policy" {
  name        = "BackendDynamoDBAccessPolicy"
  description = "Akses least-privilege ke tabel CustomerOrders dengan penegakan TLS"
  policy      = data.aws_iam_policy_document.dynamodb_restricted_access.json
}

# 3. Attachment Policy ke Role
resource "aws_iam_role_policy_attachment" "backend_attachment" {
  role       = aws_iam_role.app_backend_role.name
  policy_arn = aws_iam_policy.backend_dynamo_policy.arn
}

# 4. Instance Profile untuk di-attach ke Compute Engine (EC2)
resource "aws_iam_instance_profile" "app_instance_profile" {
  name = "AppBackendInstanceProfile"
  role = aws_iam_role.app_backend_role.name
}
```

---

### 10. Step-by-Step Implementation Guide

Berikut alur audit dan implementasi pengerasan kontrol akun AWS dari nol:

1. **Amankan Akun AWS Root**:
   - Pasang Hardware Token MFA (YubiKey) atau Virtual MFA pada akun Root.
   - Kunci/Hapus Root Access Key:
     ```bash
     aws iam delete-access-key --user-name root --access-key-id AKIAIOSFODNN7EXAMPLE
     ```
   - Hentikan penggunaan akun Root untuk operasi sehari-hari.

2. **Setup IAM Identity Center (AWS Single Sign-On)**:
   - Aktifkan IAM Identity Center di level AWS Organizations.
   - Hubungkan Identity Provider (IdP) eksternal (Google Workspace, Okta, atau Azure AD via SAML 2.0).

3. **Deploy IAM Password Policy yang Ketat (Jika IAM Users lokal terpaksa digunakan)**:
   ```bash
   aws iam update-account-password-policy \
       --minimum-password-length 14 \
       --require-symbols \
       --require-numbers \
       --require-uppercase-characters \
       --require-lowercase-characters \
       --allow-users-to-change-password \
       --max-password-age 90 \
       --password-reuse-prevention 5
   ```

4. **Aktifkan AWS CloudTrail di Seluruh Region (Multi-Region Trail)**:
   - Buat audit logging immutable untuk merekam semua request AWS API:
     ```bash
     aws cloudtrail create-trail \
         --name global-management-events \
         --s3-bucket-name central-audit-logs-production-bucket \
         --is-multi-region-trail \
         --enable-log-file-validation
     
     aws cloudtrail start-logging --name global-management-events
     ```

---

### 11. Edge Cases & Failure Modes

1. **AWS STS Throttling pada High-Concurrency Burst**:
   - *Problem*: Ribuan microservice pods dieksekusi bersamaan, semuanya meminta temporary credential (`sts:AssumeRole`) serentak, memicu status code `429 Too Many Requests (Rate Exceeded)`.
   - *Mitigasi*: Implementasikan credential caching di layer SDK aplikasi dan gunakan *exponential backoff with full jitter* saat melakukan call ke endpoint regional STS (`sts.ap-southeast-1.amazonaws.com`), bukan endpoint global (`sts.amazonaws.com`).

2. **Policy Evaluation Boundary Edge Case**:
   - Jika developer membuat Policy Identity yang mengizinkan `s3:*`, namun akun developer dibatasi oleh *IAM Permissions Boundary* yang hanya mengizinkan `dynamodb:*`, maka panggilan API ke S3 akan menghasilkan `403 Access Denied`.
   - *Aturan*: Hak akses efektif adalah interseksi (potongan himpunan) antara Permission Boundary dan Identity-based Policy.

3. **Ketergantungan Tersembunyi pada Single AZ (Cross-AZ Dependency Failure)**:
   - Sebuah API dijalankan di Multi-AZ, tetapi database read-write-nya hanya satu instans di AZ-A tanpa sinkronisasi otomatis. Ketika AZ-A mengalami degradasi daya, seluruh aplikasi Multi-AZ tetap lumpuh total (*cascading failure*).

---

### 12. Trade-offs & Analysis

| Pendekatan | Keuntungan | Kerugian | Skenario Penggunaan yang Tepat |
| :--- | :--- | :--- | :--- |
| **Multi-Region Active-Active** | Resiliensi terhadap kegagalan total seluruh Region; Latensi super rendah untuk user global. | Biaya sangat tinggi (biaya data transfer cross-region); Kompleksitas konsistensi data (*split-brain risks*). | Sistem finansial perbankan tier-0, healthcare kritis. |
| **Multi-AZ Single-Region** | Latensi replikasi sub-milidetik; Failover otomatis; Biaya transfer data terjangkau. | Rentan jika seluruh geographic region mengalami kendala katastropik (*force majeure*). | Standar de-facto untuk 95% beban kerja enterprise modern. |
| **Static IAM Access Keys** | Sangat mudah dikonfigurasi pada tools legacy yang tidak mendukung STS. | Risiko keamanan kritis; Rawan terekspos di repo Git publik; Rotasi manual rumit. | **Sangat Dilarang** di produksi (gunakan IAM Roles / OIDC). |
| **IAM Roles via STS (Federation/OIDC)** | Tanpa rotasi manual; Kredensial kedaluwarsa otomatis; Traceability tinggi di CloudTrail. | Membutuhkan arsitektur Identity Provider yang matang; Implementasi awal lebih kompleks. | Standar arsitektur industri untuk CI/CD (GitHub Actions) dan workload. |

---

### 13. Best Practices & Guidelines

- **Enforce Service-Linked Roles**: Biarkan layanan AWS mengelola interaksi antar-layanan melalui IAM Service-Linked Roles daripada membuat role manual tanpa kendali.
- **Aktifkan AWS Organizations Service Control Policies (SCP)**: Tetapkan *guardrails* yang mencegah IAM Administrator di level child-account menonaktifkan CloudTrail, menghapus enkripsi S3, atau membuat instans di luar Region yang ditentukan.
- **Terapkan Condition Keys**: Gunakan kondisi ketat dalam policy seperti:
  - `aws:PrincipalArn`: Memvalidasi identitas penyeru.
  - `aws:SourceVpc`: Mengunci eksekusi IAM policy hanya dari dalam VPC tertentu.
  - `aws:SecureTransport`: Menolak koneksi yang tidak terenkripsi TLS 1.2+.

---

### 14. Security & Compliance Considerations

- **SOC 2, ISO 27001, PCI-DSS Alignment**:
  - Di bawah Shared Responsibility Model, AWS menyediakan laporan kepatuhan fisik/hardware via **AWS Artifact**. Anda berkewajiban membuktikan audit trail (*CloudTrail logs*), enkripsi *at-rest* (menggunakan KMS CMK), dan enkripsi *in-transit* di hadapan auditor.
- **KMS Envelope Encryption**: Seluruh data yang disimpan di AWS Storage (S3, EBS, RDS) harus menggunakan Customer Master Keys (CMK) dengan rotasi otomatis tahunan.
- **Blast Radius Reduction**: Pisahkan lingkungan produksi, staging, dan development ke dalam Akun AWS yang berbeda di bawah satu AWS Organization (*Multi-Account Strategy*). Jangan pernah menaruh instans Production dan Development dalam satu VPC.

---

### 15. Cost & Resource Optimization

1. **Cross-AZ Data Transfer Charges**:
   - Transfer data di dalam AZ yang sama via private IP bernilai **$0.00 / GB**.
   - Transfer data lintas AZ (Cross-AZ Data Transfer) dalam Region yang sama dikenakan biaya **$0.01 / GB** di kedua arah (in/out). 
   - *Optimasi*: Buat traffic chatty (misal Redis caching node) berada dalam satu AZ yang sama dengan aplikasi pemroses, dan gunakan Multi-AZ hanya untuk alur replikasi asinkron dan redundansi failover.
2. **NAT Gateway Idle Costs vs VPC Endpoints**:
   - Jika aplikasi Anda di private subnet hanya perlu mengakses S3 atau DynamoDB, hindari merutekan data melalui NAT Gateway ($0.045/jam + $0.045/GB transfer).
   - Gunakan **Gateway VPC Endpoints** (S3 & DynamoDB) yang disediakan secara **gratis** tanpa biaya pemrosesan data.

---

### 16. Anti-Patterns

#### Anti-Pattern: The "God Mode" IAM Policy
```json
// SANGAT DILARANG DI LINGKUNGAN APAPUN
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "*",
      "Resource": "*"
    }
  ]
}
```
- **Masalah**: Mengabaikan segmentasi akses. Jika kredensial ini bocor, penyerang memiliki kendali penuh atas akun AWS, mampu menghapus cadangan data, menyandera database, dan menguras kuota komputasi untuk crypto-mining.
- **Solusi**: Terapkan IAM Access Analyzer untuk menganalisis log CloudTrail dan menghasilkan policy yang hanya mencantumkan aksi yang benar-benar pernah dieksekusi aplikasi.

---

### 17. Troubleshooting & Debugging

#### Masalah: Aplikasi mendapatkan error `AccessDenied` saat mencoba menulis ke S3 Bucket
1. **Langkah 1: Identifikasi Caller Identity via AWS CLI**:
   Pastikan identitas yang digunakan oleh aplikasi adalah identitas yang dimaksud:
   ```bash
   aws sts get-caller-identity
   ```
   *Output mencakup `UserId`, `Account`, dan `Arn`.*

2. **Langkah 2: Gunakan IAM Policy Simulator**:
   Simulasikan pemanggilan API untuk memverifikasi apakah Identity Policy memblokir aksi tersebut:
   ```bash
   aws iam simulate-principal-policy \
       --policy-source-arn arn:aws:iam::123456789012:role/AppBackendServiceRole \
       --action-names s3:PutObject \
       --resource-arns arn:aws:s3:::target-bucket-name/test-file.txt
   ```

3. **Langkah 3: Periksa Bucket Policy dan KMS**:
   Jika simulator menyatakan `allowed`, periksa konfigurasi S3:
   - Apakah ada S3 Bucket Policy yang memiliki statement `Deny` eksplisit?
   - Apakah object dienkripsi dengan KMS? Jika ya, apakah IAM Role memiliki izin `kms:GenerateDataKey` dan `kms:Decrypt` pada KMS Key ARN terkait?

---

### 18. Real-world Case Study

**Skenario**: Startup FinTech "PayFast" mengalami insiden di mana kunci AWS Access Key milik developer bocor ke publik repository GitHub.
- **Dampak**: Dalam waktu 11 menit, bot penyerang memanfaatkan API untuk meluncurkan 50 instans EC2 GPU `g4dn.metal` di region Frankfurt dan Sao Paulo untuk cryptomining, memicu tagihan $14,000 dalam 6 jam.
- **Akar Masalah**:
  1. Penggunaan IAM User dengan Long-lived API Credentials alih-alih IAM Roles.
  2. Akun developer tidak dibatasi Permissions Boundary.
  3. Tidak ada Service Control Policy (SCP) yang melarang pembuatan instans di region non-operasional (PayFast hanya beroperasi di Singapura).
- **Resolusi Pascainsiden**:
  1. Revokasi instan semua sesi aktif melalui STS:
     ```bash
     aws iam put-user-policy --user-name CompromisedDev \
       --policy-name DenyAll --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Deny","Action":"*","Resource":"*"}]}'
     ```
  2. Implementasi **SCP Region Restrict** di AWS Organizations untuk memblokir operasi di luar `ap-southeast-1`:
     ```json
     {
       "Version": "2012-10-17",
       "Statement": [
         {
           "Sid": "DenyAllOutsideSingapore",
           "Effect": "Deny",
           "NotAction": [
             "iam:*",
             "organizations:*",
             "route53:*",
             "cloudfront:*",
             "support:*"
           ],
           "Resource": "*",
           "Condition": {
             "StringNotEquals": {
               "aws:RequestedRegion": [
                 "ap-southeast-1"
               ]
             }
           }
         }
       ]
     }
     ```
  3. Migrasi total CI/CD ke GitHub Actions OIDC (OpenID Connect), menghapus 100% hardcoded AWS Keys dari seluruh ekosistem engineering.

---

### 19. Summary & Key Takeaways

1. **AWS Global Infrastructure** terstruktur dari isolasi fisik: Region menyediakan pemisahan geografis, Availability Zone memberikan redundansi toleransi bencana lokal tanpa penalti latensi masif.
2. **Shared Responsibility Model** adalah batas hukum dan operasional: AWS menjamin keamanan infrastruktur dasar (*hardware, hypervisor, fasilitas*), Anda wajib mengamankan data, konfigurasi jaringan, patch OS (IaaS), dan akses identitas (IAM).
3. **IAM Policy Logic**: Evaluasi kebijakan selalu berakar pada *Explicit Deny wins over Explicit Allow*, dan *Implicit Deny by default*.
4. **Zero Static Credentials**: Tinggalkan IAM Users dengan static Access Keys. Gunakan IAM Roles, AWS STS, dan OpenID Connect (OIDC) identity federation untuk semua beban kerja modern.

---

### 20. Self-Assessment / Hands-on Challenge

#### Hands-on Challenge
Rancang arsitektur keamanan IAM menggunakan Terraform dengan spesifikasi berikut:
1. Buat IAM Role bernama `DataProcessorRole` yang hanya dapat di-assume oleh service `lambda.amazonaws.com`.
2. Buat IAM Policy terpisah yang mengizinkan operasi pembacaan (`s3:GetObject`) hanya jika:
   - Request diarahkan ke bucket `arn:aws:s3:::audit-pipeline-bucket/*`.
   - Koneksi wajib menggunakan protokol aman (`aws:SecureTransport: true`).
   - Tanggal eksekusi API terjadi sebelum `2026-01-01T00:00:00Z` (Gunakan Condition Operator `DateLessThan`).
3. Hubungkan Policy tersebut ke `DataProcessorRole`.

#### Pertanyaan Evaluasi Diri
1. Jika sebuah IAM User memiliki policy yang mengizinkan `ec2:TerminateInstances` pada instance `i-12345`, namun SCP di level AWS Organizations menetapkan `Deny` untuk `ec2:TerminateInstances` pada semua resource, apakah user tersebut dapat menghapus instans? Mengapa?
2. Mengapa meletakkan dua server EC2 pada dua AZ yang berbeda di dalam satu Region memberikan perlindungan ketersediaan (*availability*) yang lebih tinggi daripada meletakkan dua server pada dua data center privat lokal yang berbeda di kota yang sama?
3. Sebutkan perbedaan struktural antara IAM Permission Boundary dan IAM Session Policy dalam siklus evaluasi STS.