# Module 01: Cloud Security, Governance & Regulatory Compliance

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengoperasikan arsitektur multi-account berbasis AWS Organizations dan AWS Control Tower dengan segregasi boundary yang ketat.
- Mengimplementasikan mekanisme deteksi ancaman (*threat detection*) dan agregasi postur keamanan secara terpusat menggunakan Amazon GuardDuty dan AWS Security Hub.
- Menerapkan kontrol proteksi data *at-rest* menggunakan AWS Key Management Service (KMS) dengan teknik Envelope Encryption dan Customer Managed Keys (CMK), serta rotasi kredensial otomatis melalui AWS Secrets Manager.
- Menegakkan perimeter pertahanan layer aplikasi (Layer 7) dan mitigasi serangan DDoS skala besar menggunakan AWS WAF dan AWS Shield Advanced.
- Mengotomatisasi audit kepatuhan regulasi (*regulatory compliance audit*) secara kontinu menggunakan AWS Config Rules dan Conformance Packs.

## 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib memahami:
- Arsitektur dasar AWS Identity and Access Management (IAM): Role, Policy Evaluation Logic, Permission Boundary, dan Trust Relationship.
- Jaringan AWS VPC tingkat lanjut: Routing, Internet/NAT Gateway, VPC Flow Logs, VPC Endpoints (PrivateLink).
- Kriptografi fundamental: Symmetric Encryption (AES-GCM), Asymmetric Encryption (RSA/ECC), Hashing, Digital Signature, dan Public Key Infrastructure (PKI).
- Pemahaman protokol OSI Layer 3/4 (TCP/UDP, SYN Flood, UDP Reflection) dan Layer 7 (HTTP/HTTPS, SQL Injection, Cross-Site Scripting).
- Kemampuan membaca dan menulis sintaks HashiCorp Configuration Language (HCL / Terraform) tingkat menengah.

## 3. Concept
Cloud Security, Governance, and Regulatory Compliance pada AWS adalah integrasi sistemik dari kontrol administratif, teknis, dan operasional untuk mengamankan data, workload, dan identitas di seluruh siklus hidup cloud (*cloud lifecycle*). Konsep ini beroperasi berdasarkan *AWS Shared Responsibility Model*, di mana AWS bertanggung jawab atas *Security of the Cloud* (komputasi fisik, storage, database, fasilitas data center global), sedangkan konsumen bertanggung jawab penuh atas *Security in the Cloud* (enkripsi data, arsitektur jaringan, manajemen akses/identitas, konfigurasi OS/aplikasi, dan kepatuhan terhadap regulasi industri seperti PCI-DSS, ISO/IEC 27001, HIPAA, atau GDPR).

Governance modern di AWS tidak lagi dijalankan melalui audit manual sporadis, melainkan melalui *Continuous Compliance-as-Code* dan *Preventive/Detective Guardrails* yang terotomatisasi di level multi-account.

## 4. Why
Mengelola keamanan cloud secara terdesentralisasi atau manual pada skala enterprise memicu berbagai risiko fatal:
- **Misconfiguration Drift:** Tanpa guardrail otomatis, developer dapat secara tidak sengaja membuka bucket S3 ke publik atau mengizinkan port database (3306/5432) terekspos ke `0.0.0.0/0`.
- **Blast Radius yang Tak Terkontrol:** Menggabungkan workload Production, Staging, dan Sandbox ke dalam satu AWS Account memperbesar risiko kompromi data kredensial; jika satu instance sandbox diretas, penyerang memiliki rute lateral langsung ke database production.
- **Audit Fatigue & Regulatory Penalties:** Penilaian audit manual memakan waktu berbulan-bulan dan langsung usang setelah laporan selesai dibuat, berisiko terkena sanksi hukum dari regulator keuangan atau privasi data.
- **Credential Sprawl:** Menyimpan API key, token, dan password database langsung di dalam kode aplikasi atau environment variables statis mempermudah kebocoran kredensial melalui repository source code publik.

## 5. What (Deep-Dive Teknis Lengkap)

### A. Multi-Account Governance: AWS Organizations & AWS Control Tower
AWS Organizations mengelompokkan akun-akun AWS ke dalam struktur hirarkis berupa Root, Organizational Units (OU), dan Member Accounts.
- **Service Control Policies (SCPs):** Merupakan guardrails preventif JSON yang menetapkan *maximum available permissions* untuk IAM user/role di dalam sebuah akun atau OU. SCP tidak pernah memberikan izin (*grant permission*), melainkan bertindak sebagai filter batas atas (*allow list* atau *explicit deny*). SCP mengabaikan status IAM Administrator di akun anak (`Member Account`), bahkan *root user* di akun anak tunduk pada SCP.
- **AWS Control Tower:** Orkestrator otomatis untuk landing zone multi-account yang menerapkan *best practices* AWS Well-Architected Framework. Control Tower mengotomatisasi provisioning akun melalui Account Factory, mengonfigurasi AWS IAM Identity Center (Single Sign-On), serta mendistribusikan guardrail (Preventive via SCP, Detective via AWS Config, dan Proactive via CloudFormation Hooks).

```
Structure Hierarchy:
Root
├── Core / Security OU
│   ├── Log Archive Account (Centralized S3 for CloudTrail, Config)
│   └── Security Tooling Account (GuardDuty Delegated Admin, Security Hub)
└── Workloads OU
    ├── Production Account
    └── Non-Production Account
```

### B. Intelligent Threat Detection & Aggregation: GuardDuty & Security Hub
- **Amazon GuardDuty:** Layanan continuous threat detection yang memanfaatkan machine learning, anomaly detection, dan integrated threat intelligence (Proofpoint, CrowdStrike, internal AWS intel). GuardDuty beroperasi secara non-intrusif pada level control plane; layanan ini tidak membutuhkan agent pada EC2/ECS karena menganalisis metadata stream dari:
  - AWS CloudTrail Event Logs & CloudTrail Management Events.
  - VPC Flow Logs.
  - DNS Query Logs.
  - S3 Data Event Logs, EKS Audit Logs, EBS Volume Data (Malware Protection), dan RDS Login Activity.
- **AWS Security Hub:** Platform Cloud Security Posture Management (CSPM) yang mengonsolidasi, menilai, dan memprioritaskan temuan keamanan (*findings*) dari GuardDuty, Inspector, Macie, IAM Access Analyzer, AWS Firewall Manager, serta partner pihak ketiga. Security Hub mengonversi seluruh temuan ke dalam format standar: AWS Security Finding Format (ASFF) dan melakukan continuous automated security checks berdasarkan standard industri:
  - AWS Foundational Security Best Practices (AFSBP).
  - CIS AWS Foundations Benchmark (v1.2.0, v1.4.0, v3.0.0).
  - Payment Card Industry Data Security Standard (PCI-DSS).

### C. Cryptographic Controls: AWS KMS & Secrets Manager
- **AWS Key Management Service (KMS):** Layanan managed HSM bersertifikasi FIPS 140-2/3 Level 3 yang mengontrol lifecycle cryptographic keys.
  - **KMS Key Types:** AWS Managed Keys (default, lifecycle diatur AWS), Customer Managed Keys (CMK - rotasi tahunan/manual, policy dikendalikan pengguna), dan Custom Key Store (CloudHSM / External Key Store).
  - **Envelope Encryption Pattern:** Digunakan untuk mengenkripsi data berukuran besar tanpa mentransmisikan data mentah ke KMS API (menghindari bottleneck jaringan dan limit kuota KMS Request per detik).
    1. Aplikasi memanggil API KMS: `GenerateDataKey(KeyId, KeySpec='AES_256')`.
    2. KMS mengembalikan dua objek: **Plaintext Data Key** dan **Ciphertext Data Key** (terenkripsi oleh CMK Root Key).
    3. Aplikasi menggunakan Plaintext Data Key untuk mengenkripsi data lokal via algoritma lokal (misal AES-256-GCM).
    4. Aplikasi segera menghapus Plaintext Data Key dari memory (*zero-out* memory).
    5. Aplikasi menyimpan Ciphertext Data Key bersama-sama dengan Ciphertext Data (disimpan sebagai metadata paket).
    6. Saat dekripsi: Aplikasi mengirim Ciphertext Data Key ke KMS via API `Decrypt`, menerima kembali Plaintext Data Key, lalu mendekripsi data lokal.

- **AWS Secrets Manager:** Layanan khusus untuk menyimpan database credentials, API tokens, dan OAuth secrets secara terenkripsi (via KMS CMK) dengan kapabilitas **Automatic Rotation** menggunakan AWS Lambda functions tanpa downtime aplikasi.

### D. Layer-7 & Edge Perimeter Defense: AWS WAF & AWS Shield
- **AWS WAF (Web Application Firewall):** Dideploy pada Amazon CloudFront, AWS Application Load Balancer (ALB), Amazon API Gateway, atau AWS AppSync.
  - Menerapkan inspeksi HTTP/HTTPS traffic menggunakan **Web Access Control Lists (Web ACL)**.
  - Terdiri dari: AWS Managed Rules (Core Rule Set/CRS, SQLi, PHP/Java exploits), Bot Control, Fraud Control (Account Takeover Prevention/ATP), IP Reputation Lists, dan Custom Regex/Rate-based Rules.
  - Rate-based rules memblokir IP yang melebihi ambang batas pemanggilan (misal: > 500 request per 5 menit).
- **AWS Shield:**
  - **AWS Shield Standard:** Otomatis aktif untuk seluruh pelanggan AWS tanpa biaya tambahan; memitigasi serangan DDoS Layer 3/4 yang umum (SYN floods, ACK floods, UDP reflection attacks) pada perimeter edge.
  - **AWS Shield Advanced:** Layanan berbayar enterprise yang menyediakan: proteksi deterministik pada CloudFront, Route 53, ALB, dan Global Accelerator; visibilitas metrik real-time; akses 24/7 ke AWS Shield Response Team (SRT) untuk mitigasi manual; dan **DDoS Cost Protection** (mengganti biaya lonjakan resource komputasi/bandwidth akibat serangan DDoS).

### E. Continuous Audit & Compliance: AWS Config & Conformance Packs
- **AWS Config:** Layanan yang terus-menerus merekam perubahan konfigurasi resource AWS (Resource Inventory, Configuration History, dan Configuration Change Notifications).
  - **Config Rules:** Mengevaluasi apakah resource compliant atau non-compliant terhadap baseline (contoh: rule `s3-bucket-public-read-prohibited`, `encrypted-volumes`).
  - **Remediation Actions:** Mengintegrasikan AWS Systems Manager (SSM) Automation Documents untuk secara otomatis memulihkan resource non-compliant (misal: otomatis mengaktifkan S3 Public Access Block saat terdeteksi publik).
- **Conformance Packs:** Kumpulan template CloudFormation YAML yang merangkum paket aturan AWS Config dan Remediation Actions yang dipetakan langsung ke regulasi formal (misalnya Conformance Pack untuk NIST-800-53, PCI-DSS, atau HIPAA). Conformance Pack dapat dideploy serentak ke ratusan akun di bawah AWS Organizations secara tersentralisasi via Organization Conformance Packs.

## 6. How
Implementasi governance dan security posture di AWS dilakukan melalui pendekatan terstruktur:
1. **Bootstrap Landing Zone:** Aktifkan AWS Organizations pada Management Account. Delegasikan Security Administrator ke Security Tooling Account untuk GuardDuty, Security Hub, dan AWS Config.
2. **Setup Isolation Boundaries:** Buat Core OUs (Security, Infrastructure) dan Business Workload OUs (Prod, Non-Prod). Terapkan SCP ketat pada Root/OU level untuk membatasi region (`aws:RequestedRegion`), memblokir perubahan pada CloudTrail/Config/GuardDuty, dan menonaktifkan pembuatan access key root.
3. **Sentralisasi Data Key Management & Auditing:**
   - Deploy Customer Managed Keys (CMK) dengan Resource-based Key Policies yang membatasi hak akses dekripsi hanya pada specific role/service.
   - Aktifkan rotasi kunci otomatis tahunan (`Automatic Key Rotation`).
4. **Deploy Perimeter Defense:**
   - Buat regional/global WAF Web ACL dengan kumpulan AWS Managed Rules dan Rate-limit rules.
   - Asosiasikan Web ACL ke Application Load Balancer atau CloudFront distribution.
5. **Enforce Continuous Governance:**
   - Deploy AWS Config Organization Rules dan Conformance Pack (contoh: Operational Best Practices for CIS AWS Foundations Benchmark).
   - Buat EventBridge Rules untuk mendengarkan temuan GuardDuty High-Severity (>7.0) dan mengeksekusi Lambda remediation function.

## 7. Analogy
Bayangkan membangun sebuah kompleks perumahan multinasional berkeamanan tinggi:
- **AWS Organizations & OU:** Denah kluster perumahan. Ada kluster Direksi/Administrasi (Security OU), kluster Hunian Utama (Production OU), dan kluster Fasilitas Umum (Sandbox OU).
- **Service Control Policies (SCPs):** Peraturan tata tertib kawasan yang mengikat secara mutlak. "Dilarang memelihara hewan buas" atau "Tinggi bangunan tidak boleh lebih dari 2 lantai". Walaupun Anda pemilik sah rumah (IAM Admin), Anda tidak bisa melanggar batas hukum kawasan ini.
- **AWS KMS & Envelope Encryption:** Kotak brankas bank dan amplop segel. Dokumen rahasia Anda yang sangat tebal (Data) disegel di rumah menggunakan gembok biasa (Data Key). Kunci gembok tersebut dimasukkan ke dalam amplop titanium berpassword digital (Encrypted Data Key) yang kuncinya hanya disimpan di brankas pusat bank Swiss (KMS HSM). Anda tidak pernah membawa dokumen tebal ke bank, cukup meminta bank membukakan amplop kuncinya saja.
- **AWS WAF & Shield:** Penjaga pos gerbang utama. Shield adalah gerbang anti-tabrakan truk kontainer (DDoS L3/4). WAF adalah petugas security yang memeriksa ID card, barang bawaan, gerak-gerik mencurigakan, dan mencocokkan wajah pengunjung dengan daftar buronan interpol (L7 WAF rules).
- **GuardDuty & Security Hub:** Sistem kamera CCTV AI dan command center satpam. CCTV (GuardDuty) menganalisis pola lalu lintas kendaraan dan gerak-gerik mencurigakan tanpa mengganggu aktivitas warga. Seluruh alarm dari detektor asap, sensor pintu, dan CCTV dikumpulkan di satu layar monitor command center (Security Hub).
- **AWS Config & Conformance Packs:** Inspektur standar bangunan yang berpatroli 24/7. Setiap kali seseorang merenovasi rumah (misal: mengganti pintu kayu menjadi pintu kaca transparan tanpa gorden), inspektur mencatat pelanggaran dan langsung memanggil tukang untuk memasang tirai penutup (Remediation).

## 8. Diagram (ASCII)

```
+----------------------------------------------------------------------------------------------------+
|                                      AWS Organizations Root                                        |
|                       [SCP: Enforce TLS, Deny Unapproved Regions, Deny Root Key]                   |
+--------------------------------------------------+-------------------------------------------------+
                                                   |
       +-------------------------------------------+------------------------------------------+
       |                                                                                      |
+------v------------------------------------+                         +-----------------------v-----------------------+
|          Security OU                      |                         |              Workloads OU                     |
|  +-------------------------------------+  |                         |  +-----------------------------------------+  |
|  |   Security Tooling Account          |  |  Delegated Admin Sync   |  |   Production Account                    |  |
|  |                                     |<=============================>|                                         |  |
|  |   - AWS Security Hub (Aggregator)   |  |   Findings / Compliance |  |   - VPC Flow Logs / DNS Queries / CloudTrail |
|  |   - Amazon GuardDuty (Master)       |  |                         |  |   - Amazon GuardDuty (Detector Member)      |  |
|  |   - AWS Config Aggregator           |  |                         |  |   - AWS Config (Local Recorder)             |  |
|  +-------------------------------------+  |                         |  +--------------------+--------------------+  |
|                                           |                         |                       |                       |
|  +-------------------------------------+  |                         |                       | Ingress Traffic       |
|  |   Log Archive Account               |  |                         |                       v                       |
|  |   - Central S3 Bucket (Write Once)  |  |                         |              +-----------------+              |
|  |     (CloudTrail & Config Logs)      |  |                         |              | AWS Shield Adv. |              |
|  +-------------------------------------+  |                         |              +--------+--------+              |
+-------------------------------------------+                         |                       |                       |
                                                                      |                       v                       |
                                                                      |              +-----------------+              |
                                                                      |              |     AWS WAF     |              |
                                                                      |              +--------+--------+              |
                                                                      |                       |                       |
                                                                      |                       v                       |
                                                                      |              +-----------------+              |
                                                                      |              | Application LB  |              |
                                                                      |              +--------+--------+              |
                                                                      |                       |                       |
                                                                      |                       v                       |
                                                                      |              +-----------------+              |
                                                                      |              | ECS / EKS Pods  |              |
                                                                      |              +--------+--------+              |
                                                                      |                       |                       |
                                                                      |       +---------------+---------------+       |
                                                                      |       v                               v       |
                                                                      | +------------+                 +------------+ |
                                                                      | |   AWS KMS  | (Envelope Enc)  |   Secrets  | |
                                                                      | |    (CMK)   |================>|   Manager  | |
                                                                      | +------------+                 +------------+ |
                                                                      |                                               |
                                                                      +-----------------------------------------------+
```

## 9. Simple Example
Penerapan Service Control Policy (SCP) paling mendasar untuk mencegah seluruh akun di bawah sebuah OU menonaktifkan GuardDuty atau AWS Config:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PreventSecurityDisabling",
      "Effect": "Deny",
      "Action": [
        "guardduty:DeleteDetector",
        "guardduty:DisassociateFromMasterAccount",
        "guardduty:StopMonitoringMembers",
        "config:DeleteConfigRule",
        "config:DeleteConfigurationRecorder",
        "config:StopConfigurationRecorder"
      ],
      "Resource": "*"
    }
  ]
}
```
*Catatan:* Sekalipun user di akun anak memiliki privilege `AdministratorAccess` (`*:*`), kebijakan SCP ini secara instan melakukan intercept dan mengembalikan response `AccessDeniedException` jika ada upaya menghentikan layanan keamanan tersebut.

## 10. Practical Example (Konfigurasi CLI / Terraform)

Berikut adalah blueprint Terraform production-grade yang mengimplementasikan:
1. Customer Managed Key (CMK) dengan envelope encryption policy.
2. AWS WAFv2 Web ACL dengan Managed Rule Sets dan Rate Limiting.
3. AWS Config Rule untuk audit enkripsi storage.

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

data "aws_caller_identity" "current" {}

# -------------------------------------------------------------------
# 1. AWS KMS: Customer Managed Key (CMK)
# -------------------------------------------------------------------
resource "aws_kms_key" "app_cmk" {
  description             = "CMK for Production Application Encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Id      = "key-policy-production"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions Root"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow SRE and App Role Decrypt/Encrypt"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/AppExecutionRole"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Environment = "Production"
    ManagedBy   = "Terraform"
  }
}

resource "aws_kms_alias" "app_cmk_alias" {
  name          = "alias/app-prod-encryption"
  target_key_id = aws_kms_key.app_cmk.key_id
}

# -------------------------------------------------------------------
# 2. AWS WAFv2: Regional Web ACL for Load Balancers
# -------------------------------------------------------------------
resource "aws_wafv2_web_acl" "prod_waf" {
  name        = "prod-core-waf-acl"
  description = "Layer-7 Protection Web ACL with AWS Managed Rules and Rate Limit"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  # Rule 1: IP Rate-Limiting Rule (Block IPs hitting > 1000 requests per 5 mins)
  rule {
    name     = "RateLimit1000Requests"
    priority = 1

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = 1000
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "RateLimit1000RequestsMetric"
      sampled_requests_enabled   = true
    }
  }

  # Rule 2: Common Rule Set (AWS Managed)
  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedCommonRuleSetMetric"
      sampled_requests_enabled   = true
    }
  }

  # Rule 3: Known Bad Inputs / SQL Injection (AWS Managed)
  rule {
    name     = "AWSManagedRulesSQLiRuleSet"
    priority = 3

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedSQLiRuleSetMetric"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "ProductionCoreWafAclMetric"
    sampled_requests_enabled   = true
  }
}

# -------------------------------------------------------------------
# 3. AWS Config Rule: Audit RDS Storage Encryption
# -------------------------------------------------------------------
resource "aws_config_config_rule" "rds_storage_encrypted" {
  name        = "rds-storage-encrypted"
  description = "Checks whether RDS DB instances have storage encryption enabled."

  source {
    owner             = "AWS"
    source_identifier = "RDS_STORAGE_ENCRYPTED"
  }

  depends_on = [aws_wafv2_web_acl.prod_waf]
}
```

## 11. Real World Example
Sebuah institusi perbankan digital di Asia Tenggara memproses lebih dari 10 juta transaksi per hari dan tunduk pada regulasi OJK serta standar PCI-DSS Level 1.

**Arsitektur Implementasi:**
1. **Multi-Account:** Dikelola menggunakan AWS Control Tower dengan 4 OU utama: `Core` (Log Archive, Security Tooling), `Workloads` (Fintech-Core-Prod, Fintech-Core-Staging), `SharedServices` (CI/CD, Core Networking), dan `Sandbox`.
2. **KMS & Envelope Encryption:** Setiap transaksi finansial dan data Personally Identifiable Information (PII) seperti KTP dan nomor rekening dienkripsi di level aplikasi sebelum masuk ke Amazon Aurora PostgreSQL. Aplikasi memanggil `kms:GenerateDataKey` ke KMS CMK khusus per divisi, lalu payload dienkripsi dengan AES-GCM-256. Plaintext data key dimusnahkan secara langsung dari memori JVM.
3. **Database Credentials:** Kredensial Aurora tidak pernah diketahui oleh developer. AWS Secrets Manager mengelola username/password dan terintegrasi dengan Lambda untuk rotasi otomatis setiap 30 hari pada pukul 02:00 AM.
4. **Perimeter:** CloudFront dipasangi AWS Shield Advanced dan WAF. WAF mengaktifkan Bot Control dan Fraud Control (Account Takeover Prevention) untuk melindungi endpoint `/api/v1/auth/login` dari serangan *credential stuffing*.
5. **Continuous Audit:** AWS Config Conformance Pack untuk PCI-DSS v3.2.1 di-deploy secara organisasi ke seluruh akun. Setiap kali seorang teknisi secara sengaja atau tidak sengaja melonggarkan Security Group (membuka port 22 ke publik), AWS Config mendeteksi status `NON_COMPLIANT`, mentrigger EventBridge, dan menjalankan Systems Manager Automation untuk otomatis me-revoke aturan egress/ingress berbahaya tersebut dalam waktu < 45 detik.

## 12. Trade-offs

| Aspek | Pilihan A | Pilihan B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **AWS KMS Key Type** | AWS Managed Key | Customer Managed Key (CMK) | AWS Managed Key bebas biaya bulanan per-key, tetapi tidak dapat dirotasi secara on-demand, key policy tidak bisa diubah kustom, dan tidak bisa di-audit spesifik. CMK membutuhkan biaya \$1/bulan per-key ditambah biaya request API, tetapi wajib digunakan untuk pemenuhan regulasi ketat (rotasi terkontrol, audit trails CloudTrail, granular policy). |
| **WAF Deployment** | CloudFront (Edge) | Application Load Balancer (Regional) | WAF di CloudFront memblokir traffic berbahaya sebelum menyentuh infrastruktur VPC internal, menghemat bandwidth VPC. Namun, jika ada private internal API di dalam VPC yang tidak menggunakan CloudFront, WAF harus dideploy secara regional di ALB. |
| **GuardDuty Inspection** | Standard Log Sources Only | Standard + Extended (EKS, Lambda, S3, RDS, EBS) | Menyalakan extended threat detection memberikan visibilitas mendalam ke malware volume EBS dan audit container, tetapi dapat menaikkan biaya analisis log bulanan secara substansial pada volume workload tinggi. |
| **Multi-Account Boundary** | Single Account (Logical Boundary via IAM & Tag) | Multi-Account (AWS Organizations) | Single Account lebih sederhana dari segi deployment jaringan/konektivitas, namun memiliki blast radius tak terbatas jika akun terkompromi. Multi-Account memisahkan billing dan security radius secara fisik, namun menuntut overhead operational jaringan (Transit Gateway, PrivateLink) yang kompleks. |

## 13. When To Use
- Gunakan **AWS Organizations & Control Tower** sejak hari pertama ketika organisasi memiliki lebih dari 1 tim engineering atau mengelola lingkungan berbeda (Production, Staging, Development).
- Gunakan **Envelope Encryption (KMS)** jika volume data yang dienkripsi berukuran lebih dari 4 KB (limit maksimal enkripsi payload langsung via KMS API `Encrypt`).
- Gunakan **AWS Secrets Manager** ketika data rahasia membutuhkan lifecycle terotomatisasi (rotasi kredensial berkala ke RDS, Redshift, atau DocumentDB).
- Gunakan **AWS Shield Advanced** jika bisnis Anda memiliki profil risiko tinggi terhadap kerugian finansial saat downtime (misal: fintech, e-commerce sale event) dan memerlukan proteksi finansial terhadap spike biaya DDoS serta akses langsung ke tim mitigasi respons AWS (SRT).

## 14. When NOT To Use
- Jangan gunakan **AWS Shield Advanced** untuk startup tahap awal dengan arsitektur non-kritis; biaya langganan dasar (\$3,000/bulan dengan komitmen 1 tahun) tidak ekonomis. AWS Shield Standard + AWS WAF rate-limiting sudah memadai untuk sebagian besar skenario standar.
- Jangan gunakan **KMS Direct API Encryption** (`kms:Encrypt`) untuk mengenkripsi file video, file backup, atau dataset analitik besar; gunakan teknik Envelope Encryption atau serahkan pada enkripsi native S3 bucket (SSE-KMS).
- Jangan gunakan **AWS Secrets Manager** untuk konfigurasi aplikasi non-sensitif (misal: URL endpoint pihak ketiga, timeout settings, UI theme strings); gunakan AWS Systems Manager Parameter Store (tipe Standard string) yang gratis.

## 15. Common Mistakes
1. **Mengabaikan Root Account Security:** Tidak mengaktifkan MFA hardware pada Root Account di AWS Organizations Management Account dan membiarkan access key aktif pada akun root.
2. **KMS Key Policy Terlalu Longgar:** Memberikan izin `"Principal": {"AWS": "*"}` pada KMS Key Policy dengan asumsi bahwa IAM Policy di akun anak akan membatasi aksesnya. Key Policy adalah otorisasi dasar; jika Key Policy mengizinkan root account, maka kontrol berpindah ke IAM policy, namun jika Key Policy salah dikonfigurasi mengizinkan wildcard principal tanpa condition, data dapat terbuka luas.
3. **WAF Block Action Tanpa Testing (Count Mode):** Langsung mengaktifkan action `BLOCK` pada AWS Managed Rules WAF di production tanpa menjalankan fase evaluasi `COUNT` terlebih dahulu, mengakibatkan valid API payload (seperti XML/JSON kompleks yang mirip pola SQL injection) terblokir dan menimbulkan insiden produksi (*false positive*).
4. **Log Storage di Akun yang Sama:** Menyimpan audit logs (CloudTrail, VPC Flow Logs, Config) di dalam S3 bucket pada akun production yang sama. Jika akun production terkena compromise di level administrator, penyerang dapat menghapus rekaman log untuk menutupi jejak forensik. Log wajib dialirkan ke dedicated *Log Archive Account*.

## 16. Best Practices
1. **Terapkan SCP Deny List Global:** Gunakan SCP untuk menonaktifkan seluruh AWS Region yang tidak digunakan oleh bisnis perusahaan guna memitigasi provisioning resource tersembunyi oleh penyerang.
2. **Aktifkan AWS Security Hub & GuardDuty Secara Terpusat:** Manfaatkan fitur Delegated Administrator pada Organizations sehingga seluruh temuan dari ratusan akun anggota otomatis diagregasi ke Security Tooling Account.
3. **Enforce KMS Separation of Duties:** Pisahkan secara tegas antara Key Administrator (role yang boleh memodifikasi policy, rotasi, disable key, tetapi tidak boleh melakukan `kms:Decrypt`) dan Key User/Application (role yang boleh melakukan `kms:Decrypt` / `kms:GenerateDataKey` tetapi tidak boleh mengubah policy atau menghapus key).
4. **Gunakan Conformance Packs untuk CI/CD Pipeline:** Periksa template CloudFormation atau Terraform terhadap aturan AWS Config secara proaktif sebelum proses merge ke branch utama menggunakan tool seperti `cfn-guard` atau `tfsec/trivy`.

## 17. Troubleshooting

### Problem 1: `AccessDeniedException` saat Service atau IAM Role Memanggil KMS API
- **Gejala:** Aplikasi memunculkan error: `User: arn:aws:iam::111122223333:role/AppRole is not authorized to perform: kms:Decrypt on resource: arn:aws:kms:...`
- **Penyebab:** KMS CMK membutuhkan otorisasi ganda jika IAM role dan KMS key berada di akun berbeda, atau KMS Key Policy tidak mendaftarkan IAM Role tersebut secara eksplisit.
- **Diagnosa & Solusi:**
  1. Periksa KMS Key Policy. Pastikan ada statement yang mengizinkan aksi `kms:Decrypt` untuk ARN `arn:aws:iam::111122223333:role/AppRole`.
  2. Jika Key Policy mendelegasikan ke akun (`arn:aws:iam::111122223333:root`), periksa IAM Identity Policy yang terpasang pada `AppRole`. Pastikan IAM policy memiliki permission `kms:Decrypt` ke resource ARN key tersebut.
  3. Periksa apakah terdapat KMS Grants aktif atau kondisi pembatasan context (`kms:EncryptionContext`). Jika saat enkripsi disertakan Encryption Context, saat dekripsi context yang sama persis wajib disertakan.

### Problem 2: WAF Memblokir Request Valid Pengguna (False Positive)
- **Gejala:** Klien menerima HTTP response `403 Forbidden` dengan response header `X-AMZN-Waf-Action: block`.
- **Penyebab:** Aturan pada managed ruleset (misal: `AWS-AWSManagedRulesCommonRuleSet`) mendeteksi pola request yang cocok dengan signature serangan, padahal data tersebut sah (misal payload markdown yang mengandung tag HTML atau karakter SQL-like).
- **Diagnosa & Solusi:**
  1. Masuk ke AWS WAF Console -> Web ACLs -> Sampled Requests atau CloudWatch Logs.
  2. Cari log request dengan status `BLOCK`. Identifikasi nama rule spesifik yang memicu pemblokiran (misal `SizeRestrictions_BODY` atau `CrossSiteScripting_BODY`).
  3. Buka konfigurasi Web ACL, edit Managed Rule Group tersebut, dan ubah action rule spesifik yang memicu false positive menjadi **Override to Count**.
  4. Alternatif: Tambahkan Rule Exception menggunakan Custom Rule dengan priority lebih tinggi yang mengizinkan spesifik URI path tersebut sebelum dievaluasi oleh Managed Rule Group.

## 18. Exercise
Skenario: Buatlah Service Control Policy (SCP) via AWS CLI / JSON untuk menegakkan aturan tata kelola berikut pada seluruh member account:
1. Menolak izin untuk menghapus S3 Bucket Access Points dan S3 Block Public Access di tingkat akun.
2. Membatasi agar deployment infrastruktur hanya diizinkan di region `ap-southeast-1` (Singapore) dan `ap-southeast-3` (Jakarta).
3. Pastikan SCP mengabaikan layanan global (IAM, Route 53, CloudFront) agar tidak terjadi outage sistemik.

## 19. Challenge
Implementasikan pipeline deteksi dan remediasi terotomatisasi secara end-to-end:
1. Buat custom AWS Config Rule yang memeriksa apakah Security Group mengizinkan ingress port 22 (SSH) dari `0.0.0.0/0`.
2. Buat Amazon EventBridge Rule yang mendengarkan event perubahan status kepatuhan AWS Config dari `COMPLIANT` menjadi `NON_COMPLIANT`.
3. Integrasikan EventBridge dengan AWS Systems Manager (SSM) Automation Document untuk mencabut (*revoke*) ingress rule port 22 tersebut secara otomatis dari Security Group terkait dalam tempo kurang dari 1 menit.
4. Publikasikan notifikasi insiden dan detail remediasi ke topik Amazon SNS yang terhubung ke kanal komunikasi tim DevOps/SRE.

## 20. Summary
- **Tata Kelola Skala Besar:** AWS Organizations dan Control Tower menyediakan isolasi multi-account yang kokoh melalui SCPs yang berperan sebagai guardrail preventif absolut.
- **Deteksi Cerdas Terpusat:** Amazon GuardDuty mendeteksi ancaman tanpa agent berbasis telemetry analitik, sementara AWS Security Hub mengonsolidasikan postur keamanan dan audit compliance terhadap standar industri (CIS, PCI-DSS).
- **Kriptografi & Rahasia:** AWS KMS mengamankan enkripsi skala masif menggunakan pola Envelope Encryption untuk efisiensi komputasi dan jaringan. AWS Secrets Manager melengkapi proteksi data sensitif dengan kapabilitas rotasi kredensial otomatis.
- **Ketahanan Perimeter:** Lapisan edge dan L7 diamankan secara sinergis melalui integrasi AWS WAF (inspeksi payload HTTP dan mitigasi eksploitasi web) dan AWS Shield Advanced (mitigasi serangan volumetrik L3/4 dan proteksi finansial).
- **Kepatuhan Kontinu:** AWS Config dan Conformance Packs mengubah proses audit manual yang lambat menjadi evaluasi otomatis berkelanjutan yang dipadukan dengan remediasi instan berbasis event-driven architecture.

---