# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 08: Cloud Security, Governance, & Regulatory Compliance**  
**Kategori: 05-DevOps-Cloud-and-SRE**

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan mampu:
1. **Merancang & Mengimplementasikan Multi-Account Governance**: Membangun hierarki AWS Organizations dengan guardrail Service Control Policies (SCPs) berlapis, Tag Policies, dan delegasi administrasi tanpa memicu dependensi sirkular.
2. **Menguasai Kriptografi Lanjutan & AWS KMS**: Mengimplementasikan arsitektur *Envelope Encryption*, Cross-Account KMS Key Grants, Key Rotation terkelola, serta integrasi AWS CloudHSM/Custom Key Store untuk standar kepatuhan FIPS 140-2 Level 3.
3. **Mengonstruksi Zero-Trust Identity via ABAC & Permission Boundaries**: Membatasi eskalasi privilese menggunakan Attribute-Based Access Control (ABAC), Session Policies, dan IAM Permissions Boundaries pada pipeline CI/CD serta dynamic worker workloads.
4. **Membangun Event-Driven Security Remediation Pipeline**: Mengotomatisasi siklus deteksi hingga remediasi secara *near-real-time* (< 30 detik) menggunakan AWS Config Conformance Packs, Security Hub, Amazon EventBridge, dan AWS Systems Manager (SSM) Automation Runbooks.
5. **Mengevaluasi Kepatuhan Regulasi (Compliance-as-Code)**: Mengoperasikan framework continuous compliance untuk PCI-DSS v4.0, SOC 2 Tipe II, dan ISO/IEC 27001 menggunakan rule AWS Config kustom dan Audit Manager.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, engineer harus menguasai:
- Pemahaman solid tentang AWS Core Services: VPC, EC2, S3, IAM dasar (Identity-based vs Resource-based policies).
- Pengalaman menulis dan membaca sintaks Infrastructure as Code (IaC) menggunakan Terraform/OpenTofu (v1.5+).
- Pemahaman dasar tentang algoritma kriptografi simetris (AES-256-GCM) dan asimetris (RSA/ECC), serta konsep Public Key Infrastructure (PKI).
- Kemampuan membaca dan menulis script otomasi menggunakan Python 3.11+ (Boto3 SDK).
- Pengetahuan operasional CLI (AWS CLI v2, `jq`, `curl`, OpenSSL).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Mekanisme Internal Evaluasi Kebijakan IAM (The Authorization Engine)
Evaluasi otorisasi di AWS adalah sistem deterministik bertingkat yang dievaluasi setiap kali API call dilakukan. Mesin evaluasi AWS Policy mengikuti alur ketat:
1. **Explicit Deny Evaluation**: Jika ada satu pernyataan `Deny` yang cocok di konteks evaluasi mana pun, hasil akhirnya mutlak `Deny`.
2. **Service Control Policies (SCPs)**: Membatasi izin maksimum untuk akun anggota dalam AWS Organization. SCP tidak pernah memberikan izin (`Allow` pada SCP hanya berfungsi sebagai filter/whitelist izin maksimum).
3. **Resource-Based Policies**: Mengevaluasi kebijakan yang melekat langsung pada resource (contoh: S3 Bucket Policy, KMS Key Policy). Jika resource policy memberikan akses eksplisit ke prinsipal, akses dapat langsung diberikan kecuali dibatasi oleh SCP atau Permissions Boundary.
4. **IAM Permissions Boundaries**: Berfungsi sebagai kuota izin maksimum untuk IAM User atau Role. Jika prinsipal mencoba menjalankan aksi yang diizinkan oleh Identity Policy namun di luar Permissions Boundary, aksi akan di-*deny*.
5. **Session Policies**: Diterapkan saat prinsipal melakukan assume role via STS (`AssumeRole`, `AssumeRoleWithSAML`, atau `AssumeRoleWithWebIdentity`). Interseksi antara Identity Policy role dan Session Policy menentukan izin akhir.
6. **Identity-Based Policies**: Kebijakan yang melekat pada IAM User, Group, atau Role.
7. **Implicit Deny**: Jika tidak ada satupun evaluasi eksplisit `Allow` yang tercapai, request secara *default* ditolak (*default-deny model*).

```
                 +-----------------------------------+
                 |        Incoming API Request       |
                 +-----------------+-----------------+
                                   |
                                   v
                 +-----------------------------------+
                 |    Any Explicit DENY in Tree?     |---- YES ----> [ EXPLICIT DENY ]
                 +-----------------+-----------------+
                                   | NO
                                   v
                 +-----------------------------------+
                 |   Within SCP Max Permissions?     |---- NO -----> [ IMPLICIT DENY ]
                 +-----------------+-----------------+
                                   | YES
                                   v
                 +-----------------------------------+
                 |   Cross-Account Request Evaluation|
                 |   (Resource vs Identity Trust)    |
                 +-----------------+-----------------+
                                   |
           +-----------------------+-----------------------+
           |                                               |
           v (Same-Account)                                v (Cross-Account)
  +--------------------------------+              +--------------------------------+
  | Resource Policy = ALLOW?       |              | Identity AND Resource Policy   |
  | (e.g., S3 Bucket, KMS Key)     |              | Both MUST evaluate to ALLOW?   |
  +-------+----------------+-------+              +-------+----------------+-------+
          | YES            | NO                           | YES            | NO
          |                v                              |                v
          |      +-------------------+                    |          [ IMPLICIT DENY ]
          |      | Identity Policy?  |                    |
          |      +---+-----------+---+                    |
          |          | YES       | NO                     |
          |          |           +----------------------->|
          v          v                                    |
  +--------------------------------+                      |
  | Within Permission Boundary?    |<---------------------+
  +-------+----------------+-------+
          | YES            | NO
          v                +-----------------------------> [ IMPLICIT DENY ]
  +--------------------------------+
  | Within Session Policy?         |
  +-------+----------------+-------+
          | YES            | NO
          v                +-----------------------------> [ IMPLICIT DENY ]
   [ EXPLICIT ALLOW ]
```

#### B. Internal Cryptographic Engine: AWS KMS & Envelope Encryption
AWS Key Management Service (KMS) memanfaatkan Hardware Security Module (HSM) FIPS 140-2/3 Level 3 yang terspesialisasi. KMS tidak pernah mengekspor Customer Master Key (CMK / KMS Key) dalam bentuk plain text keluar dari boundary HSM.

Untuk mengenkripsi data berukuran besar (misalnya objek S3 > 4 KB atau volume EBS), KMS menggunakan pola **Envelope Encryption**:
1. Aplikasi klien mengirimkan request `GenerateDataKey` ke KMS API dengan menentukan KMS Key ID dan Key Spec (misal: `AES_256`).
2. HSM KMS menghasilkan Data Key (DK) acak 256-bit berkecepatan tinggi.
3. HSM menyalin DK tersebut:
   - Satu salinan dibiarkan dalam bentuk **Plaintext Data Key**.
   - Salinan kedua dienkripsi menggunakan Root Key (KMS Key) di dalam HSM, menghasilkan **Ciphertext Data Key (Encrypted Data Key)**.
4. Keduanya dikembalikan ke aplikasi pemanggil melalui kanal TLS terenkripsi.
5. Aplikasi menggunakan Plaintext Data Key untuk mengenkripsi payload data lokal secara simetris menggunakan algoritma lokal (misal: AES-256-GCM).
6. **Tahap Kritis**: Aplikasi menghapus (*zero-out*) Plaintext Data Key dari memori RAM.
7. Aplikasi menyimpan Ciphertext Data Key bersamaan dengan data terenkripsi (sebagai metadata atau appended header).
8. Saat dekripsi: Aplikasi mengirim Ciphertext Data Key ke KMS via API `Decrypt`. KMS HSM mendekripsi ciphertext tersebut menggunakan KMS Key yang sama dan mengembalikan Plaintext Data Key ke aplikasi untuk membuka data.

#### C. Continuous Compliance-as-Code & Automated Remediation Loop
Sistem deteksi modern tidak bergantung pada cron audit mingguan. AWS Config mencatat perubahan status (*Configuration Item* / CI) dari resource secara *event-driven*. Setiap modifikasi resource memicu evaluasi Config Rule (bisa AWS Managed Rule atau Custom Rule berbasis Guard/Lambda).
- Ketika status resource beralih ke `NON_COMPLIANT`, AWS Config memancarkan event ke AWS EventBridge bus.
- AWS Security Hub mengonsolidasikan temuan (*Findings*) dalam format standar **AWS Security Finding Format (ASFF)**.
- EventBridge mengeksekusi routing pattern yang ditargetkan ke SSM Automation Documents atau Lambda Functions untuk melakukan remediasi mekanis (misalnya: memutus public access block pada S3, mengisolasi security group, atau mematikan IAM Access Key yang bocor).

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Legacy Cloud Security) | Enterprise Production Standard (DevSecOps) |
| :--- | :--- | :--- |
| **Batas Akun (Account Boundaries)** | Single-Account dengan multi-VPC dipisahkan tag environment (`dev`, `staging`, `prod`). | Multi-Account Architecture via AWS Organizations & Control Tower; pemisahan akun berdasarkan blast-radius isolasi fisik. |
| **Kepatuhan (Compliance)** | Point-in-time snapshot audit via spreadsheet setiap kuartal atau tahunan. | Continuous Compliance-as-Code real-time; drift detection otomatis via AWS Config & Audit Manager. |
| **Manajemen Kunci (KMS)** | Menggunakan default AWS Managed Keys (`aws/s3`, `aws/ebs`) dengan rotasi tak terkontrol. | Customer Managed Keys (CMK) dengan rotasi otomatis, Custom Key Policy strictly scoped, Cross-Account Grants, dan BYOK. |
| **Otorisasi (IAM)** | Static Role Assignment; penambahan policy manual yang berujung pada *Role Bloat* dan akumulasi privilese. | Dynamic ABAC (Attribute-Based Access Control) menggunakan tag `Environment`, `Department`, dan `Project` + Strict Permissions Boundaries. |
| **Respons Insiden** | Manual alert triage lewat email, engineer login via SSH/Bastion untuk mematikan port. | Event-driven automated containment (< 60 detik) via EventBridge, SSM Automation, dan zero-human console access policy. |

---

### 5. How (Workflow Detail)

Alur Operasional Automated Detective & Responsive Control pada Arsitektur Produksi:

```
[ Developer / CI/CD ]
         |
         | 1. Modifikasi Resource (misal: Membuat S3 tanpa Enkripsi)
         v
[ AWS CloudTrail Engine ]
         |
         | 2. Menangkap Write API Call (s3:CreateBucket)
         v
[ AWS Config Engine ]
         |
         | 3. Merekam Perubahan State Resource (Configuration Item)
         | 4. Evaluasi terhadap Rule: 's3-bucket-server-side-encryption-enabled'
         v
   { Status: NON_COMPLIANT }
         |
         | 5. Publikasi State Change Event
         v
[ AWS Security Hub ] (Format: ASFF)
         |
         | 6. Finding Diteruskan ke Event Bus
         v
[ Amazon EventBridge Default Bus ]
         |
         | 7. Pattern Matching Rule:
         |    source: "aws.securityhub"
         |    finding.Compliance.Status: "FAILED"
         |    finding.Title: "S3.4 S3 buckets should have server-side encryption enabled"
         v
+--------+---------------------------------------+
|                                                |
v Target 1                                       v Target 2
[ SSM Automation Runbook / Lambda Engine ]       [ Security Operations Center ]
|                                                |
| 8. Enforce AWS KMS Encryption                  | 9. Slack / PagerDuty Alert
| 9. Audit Event via CloudTrail                  |    dengan context ID & status
v                                                v
[ Resource COMPLIANT ]                    [ Ticket Auto-Resolved ]
```

1. **Detection Phase**: Resource diubah melalui API/IaC. CloudTrail mencatat event dan meneruskannya ke AWS Config.
2. **Evaluation Phase**: AWS Config menjalankan aturan evaluasi secara sinkron/asinkron. Dalam hitungan detik, resource ditandai sebagai `NON_COMPLIANT`.
3. **Consolidation Phase**: Security Hub menyerap status dari Config, mengalokasikannya ke compliance framework (CIS AWS Foundations Benchmark v3.0 / PCI-DSS), dan merilis finding berformat ASFF.
4. **Ingestion & Routing Phase**: EventBridge mencocokkan pattern JSON finding. Aturan rule menyaring tingkat keparahan (*Severity: HIGH/CRITICAL*).
5. **Remediation Phase**: EventBridge memicu AWS Systems Manager (SSM) Automation Execution atau Lambda function idempotensi tinggi untuk mengaplikasikan konfigurasi enkripsi standar secara paksa.
6. **Audit & Notification Phase**: Eksekusi tindakan remediasi dicatat kembali ke CloudTrail untuk jejak audit, dan ringkasan eksekusi dikirim ke kanal PagerDuty/Slack SecOps.

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
Bayangkan sebuah **Gedung Konsulat Diplomatik Berkunci Ganda**:
- **AWS Organizations & SCPs** adalah batas wilayah yurisdiksi diplomatik. Jika hukum federal melarang senjata api dibawa masuk, tidak ada duta besar atau konsulat lokal yang dapat mengizinkannya di ruangan mereka, apa pun otorisasi lokal yang mereka buat.
- **IAM Permission Boundary** adalah *surat tugas diplomatik*. Duta besar dapat memberikan wewenang kepada stafnya, tetapi kekuasaan staf tidak akan pernah melampaui apa yang tertera di surat mandat tugas tersebut.
- **KMS Envelope Encryption** adalah *brankas diplomatik berantai*. Anda memiliki tas diplomatik berisi berkas rahasia tebal (Payload Data). Anda menguncinya dengan gembok kecil (Data Key). Kunci dari gembok kecil tersebut dimasukkan ke dalam brankas baja tahan ledak di lantai bawah tanah konsulat (HSM / KMS Key) yang tidak pernah bisa dipindahkan oleh siapa pun.

#### Arsitektur Produksi: Multi-Account Security & Centralized KMS

```
+--------------------------------------------------------------------------------------------------------+
|                                         AWS ROOT ORGANIZATION                                          |
|  [ SCP: Deny Leave Org, Deny Disable CloudTrail/Config, Deny Unapproved Regions (Strict Guardrails) ]  |
+---------------------------------------------------+----------------------------------------------------+
                                                    |
         +------------------------------------------+------------------------------------------+
         |                                                                                     |
         v                                                                                     v
+------------------------------------+                               +------------------------------------+
|     CORE SECURITY ACCOUNT          |                               |       PRODUCTION WORKLOAD          |
|                                    |                               |             ACCOUNT                |
|  +------------------------------+  |                               |                                    |
|  | AWS KMS CMK (Central Vault)  |  |                               |  +------------------------------+  |
|  | - Strict Key Policy          |  |  Cross-Account KMS Decrypt    |  | Workload Pod / Lambda Worker |  |
|  | - Auto-rotation: Enabled     |  |==============================>|  | - Assumes Workload Role      |  |
|  | - Grant: Prod Role Only      |  |  (Via KMS Grant / Key Policy) |  | - Boundary Enforced          |  |
|  +------------------------------+  |                               |  +--------------+---------------+  |
|                 ^                  |                               |                 |                  |
|                 |                  |                               |                 v Writes Encrypted |
|  +--------------+---------------+  |                               |  +------------------------------+  |
|  | AWS Security Hub / GuardDuty |  |                               |  | S3 Enterprise Data Lake / EBS|  |
|  | (Delegated Administrator)    |  |                               |  | - Encrypted with Core KMS    |  |
|  +--------------^---------------+  |                               |  +------------------------------+  |
|                 | Aggregated       |                               |                 |                  |
|                 | Findings         |                               |                 | Emits State      |
|                 |                  |                               |                 v                  |
|  +--------------+---------------+  |   Remediation Command (SSM)   |  +------------------------------+  |
|  | EventBridge Event Bus Engine |=================================>|  | AWS Config Managed Rules     |  |
|  +------------------------------+  |                               |  +------------------------------+  |
+------------------------------------+                               +------------------------------------+
```

---

### 7. Simple Example & Practical Example

Berikut implementasi production-grade menggunakan Terraform (IaC) dan Python untuk membangun:
1. **Service Control Policy (SCP)** ketat anti-tampering.
2. **KMS Multi-Account Central Key** dengan Key Policy berbasis prinsip least-privilege.
3. **IAM Permissions Boundary** untuk membatasi eskalasi privilese.
4. **Lambda Auto-Remediation Function** untuk S3 Public Access Block.

#### A. Terraform: Advanced Governance Architecture (`main.tf`)

```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
  }
}

# ------------------------------------------------------------------------------------------------------
# 1. SERVICE CONTROL POLICY (GUARDRAIL PADA AWS ORGANIZATIONS)
# ------------------------------------------------------------------------------------------------------
resource "aws_organizations_policy" "guardrail_tamper_defense" {
  name        = "GuardrailTamperDefense"
  description = "Mencegah penonaktifan CloudTrail, GuardDuty, dan Config di akun anak"
  type        = "SERVICE_CONTROL_POLICY"

  content = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "DenySecurityServiceTampering"
        Effect   = "Deny"
        Action   = [
          "cloudtrail:DeleteTrail",
          "cloudtrail:StopLogging",
          "cloudtrail:UpdateTrail",
          "config:DeleteConfigRule",
          "config:DeleteConfigurationRecorder",
          "config:StopConfigurationRecorder",
          "guardduty:DeleteDetector",
          "guardduty:DisassociateFromMasterAccount",
          "guardduty:UpdateDetector"
        ]
        Resource = "*"
        Condition = {
          "ArnNotLike" = {
            "aws:PrincipalArn" = [
              "arn:aws:iam::*:role/aws-service-role/*",
              "arn:aws:iam::*:role/BreakGlassAdminRole"
            ]
          }
        }
      },
      {
        Sid      = "DenyUnapprovedRegions"
        Effect   = "Deny"
        NotAction = [
          "a4b:*", "acm:*", "aws-marketplace:*", "aws-portal:*", "budgets:*",
          "ce:*", "chime:*", "cloudfront:*", "config:*", "cur:*",
          "directconnect:*", "ec2:DescribeRegions", "guardduty:*", "iam:*",
          "kms:*", "networkmanager:*", "organizations:*", "pricing:*",
          "route53:*", "route53domains:*", "s3:GetAccountPublicAccessBlock",
          "s3:ListAllMyBuckets", "shield:*", "sts:*", "support:*", "trustedadvisor:*"
        ]
        Resource = "*"
        Condition = {
          "StringNotEquals" = {
            "aws:RequestedRegion" = ["ap-southeast-1", "ap-southeast-3"]
          }
        }
      }
    ]
  })
}

# ------------------------------------------------------------------------------------------------------
# 2. ADVANCED CENTRAL KMS KEY DENGAN CROSS-ACCOUNT DELEGATION
# ------------------------------------------------------------------------------------------------------
data "aws_caller_identity" "current" {}

resource "aws_kms_key" "production_vault_key" {
  description             = "Production Master Vault Key for Cross-Account Cryptographic Operations"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  multi_region            = false

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EnableRootAdminPermissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowKmsAdminAdministration"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/SecOpsKeyAdminRole"
        }
        Action = [
          "kms:Create*", "kms:Describe*", "kms:Enable*", "kms:List*",
          "kms:Put*", "kms:Update*", "kms:Revoke*", "kms:Disable*",
          "kms:Get*", "kms:Delete*", "kms:TagResource", "kms:UntagResource",
          "kms:ScheduleKeyDeletion", "kms:CancelKeyDeletion"
        ]
        Resource = "*"
      },
      {
        Sid    = "AllowCrossAccountUsageForProductionWorkloads"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::222233334444:role/ProductionWorkloadAppRole" # Production Account Role
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = [
              "s3.ap-southeast-1.amazonaws.com",
              "ebs.ap-southeast-1.amazonaws.com"
            ]
          }
        }
      }
    ]
  })
}

resource "aws_kms_alias" "production_vault_alias" {
  name          = "alias/enterprise-prod-vault"
  target_key_id = aws_kms_key.production_vault_key.key_id
}

# ------------------------------------------------------------------------------------------------------
# 3. IAM PERMISSIONS BOUNDARY UNTUK CI/CD & DELEGATED ADMINS
# ------------------------------------------------------------------------------------------------------
resource "aws_iam_policy" "pipeline_boundary" {
  name        = "PipelineExecutionBoundary"
  description = "Boundary batas maksimal privilese yang dapat dialokasikan oleh CI/CD pipeline"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowGeneralScopedServices"
        Effect = "Allow"
        Action = [
          "s3:*",
          "ec2:*",
          "lambda:*",
          "rds:*",
          "dynamodb:*",
          "logs:*"
        ]
        Resource = "*"
      },
      {
        Sid    = "DenyIAMModificationsUnlessBoundaryApplied"
        Effect = "Deny"
        Action = [
          "iam:CreateUser",
          "iam:CreateRole",
          "iam:PutRolePolicy",
          "iam:AttachRolePolicy"
        ]
        Resource = "*"
        Condition = {
          "StringNotEquals" = {
            "iam:PermissionsBoundary" = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/PipelineExecutionBoundary"
          }
        }
      },
      {
        Sid      = "DenyBoundaryBypass"
        Effect   = "Deny"
        Action   = [
          "iam:DeleteRolePermissionsBoundary",
          "iam:DeleteUserPermissionsBoundary"
        ]
        Resource = "*"
      }
    ]
  })
}
```

#### B. Remediation Lambda: Python (`remediate_s3_public_access.py`)
Fungsi Python ini dirancang untuk dijalankan oleh EventBridge ketika Security Hub mendeteksi bucket S3 yang terbuka untuk publik (Finding: `S3.1`).

```python
import os
import json
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')

def lambda_handler(event, context):
    """
    Idempotent Automated Remediation Handler:
    Menutup S3 Public Access secara instan begitu terdeteksi non-compliant.
    """
    logger.info("Menerima EventBridge Event: %s", json.dumps(event))
    
    try:
        # Parsing payload ASFF dari Security Hub via EventBridge
        detail = event.get('detail', {})
        findings = detail.get('findings', [])
        
        if not findings:
            logger.warning("Tidak ada findings yang teridentifikasi dalam payload.")
            return {"status": "NOOP", "reason": "Empty findings"}

        for finding in findings:
            finding_id = finding.get('Id')
            compliance = finding.get('Compliance', {}).get('Status')
            
            if compliance != 'FAILED':
                logger.info("Finding %s status bukan FAILED. Melewati.", finding_id)
                continue
            
            for resource in finding.get('Resources', []):
                if resource.get('Type') == 'AwsS3Bucket':
                    bucket_arn = resource.get('Id')
                    bucket_name = bucket_arn.split(':::')[-1]
                    
                    logger.info("Memulai remediasi untuk bucket yang tidak aman: %s", bucket_name)
                    
                    # Terapkan S3 Account/Bucket Public Access Block ketat
                    s3_client.put_public_access_block(
                        Bucket=bucket_name,
                        PublicAccessBlockConfiguration={
                            'BlockPublicAcls': True,
                            'IgnorePublicAcls': True,
                            'BlockPublicPolicy': True,
                            'RestrictPublicBuckets': True
                        }
                    )
                    
                    logger.info("Remediasi Berhasil: Public Access Block aktif pada %s", bucket_name)
                    
        return {"status": "SUCCESS", "message": "Semua resource non-compliant berhasil diremediasi."}
        
    except ClientError as e:
        logger.error("AWS Boto3 ClientError pada saat remediasi: %s", str(e), exc_info=True)
        raise e
    except Exception as exc:
        logger.critical("Fatal runtime exception: %s", str(exc), exc_info=True)
        raise exc
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario Kasus: MegaPay FinTech (Core-Banking API Gateway Migration)
- **Karakteristik Skala**: 45.000 Transaksi per Detik (TPS), multi-region (Singapura `ap-southeast-1` dan Jakarta `ap-southeast-3`), beroperasi di bawah regulasi ketat PCI-DSS v4.0 Level 1 dan Bank Indonesia / OJK framework.
- **Kondisi Awal**: 
  - Arsitektur AWS semi-monolitik dengan 3 akun besar (*Dev*, *Staging*, *Prod*).
  - Enkripsi database Aurora PostgreSQL dan bucket S3 transaksi menggunakan AWS Managed Key standar (`aws/rds` dan `aws/s3`).
  - Tim pengembang memiliki privilese `AdministratorAccess` pada IAM Role untuk mempercepat *debugging*. Sering terjadi *configuration drift* di mana port inbound database 5432 terbuka ke subnet publik secara tidak sengaja via security group.
  - Audit log CloudTrail disimpan dalam S3 bucket lokal di masing-masing akun, dan ditemukan insiden di mana log secara manual dihapus oleh engineer saat tracing kesalahan.

#### Implementasi Solusi & Rekayasa Arsitektur
1. **Multi-Account Landing Zone Restructuring**:
   - Membangun AWS Control Tower dengan 5 Organizational Units (OU): `Core` (Log Archive & Audit), `Security`, `Workloads-Prod`, `Workloads-NonProd`, dan `Sandbox`.
   - Mengalokasikan AWS Audit Manager dan GuardDuty delegated administrator ke Core Security Account.
2. **KMS Cryptographic Blast Radius Segregation**:
   - Mengganti seluruh default key dengan Customer Managed Keys (CMK) dengan *explicit separation of duties*: Admin KMS (SecOps) tidak memiliki hak akses data (`kms:Decrypt` di-*deny* untuk peran admin), sementara Microservice Application Role hanya memiliki hak `kms:GenerateDataKey` dan `kms:Decrypt` via *Encryption Context* ketat:
   ```json
   "Condition": {
     "StringEquals": {
       "kms:EncryptionContext:Department": "CoreBanking",
       "kms:EncryptionContext:Classification": "Restricted-Financial"
     }
   }
   ```
3. **Immutability Log Pipeline**:
   - CloudTrail di seluruh akun organisasi dipusatkan ke Log Archive Account.
   - S3 Bucket Log Archive dipersenjatai dengan **S3 Object Lock** dalam mode `COMPLIANCE` selama 7 tahun (WORM - *Write Once, Read Many*) untuk memenuhi PCI-DSS v4.0 Requirement 10.5.4. SCP memblokir total aksi `s3:DeleteBucketPolicy`, `s3:PutLifecycleConfiguration`, dan `s3:DeleteObject*`.
4. **Autonomous Remediation Loop**:
   - Menerapkan Config Conformance Pack untuk PCI-DSS v4.0.
   - Setiap modifikasi Security Group yang membuka inbound port rentan (`0.0.0.0/0` ke port 22, 3389, atau 5432) ditangkap dalam < 5 detik oleh EventBridge, yang langsung memicu SSM Document `AWS-DisablePublicAccessForSecurityGroup` secara mekanis tanpa intervensi manusia.

#### Dampak Operasional & Kepatuhan
- Penurunan durasi Mean Time to Detect (MTTD) dari 3 minggu (siklus audit manual) menjadi 1,8 detik.
- Penurunan Mean Time to Remediate (MTTR) insiden exposure publik dari rata-rata 4 jam kerja menjadi < 15 detik.
- Keberhasilan melalui audit PCI-DSS v4.0 tanpa ada temuan *High/Critical Non-Conformity*.

---

### 9. Trade-offs

| Aspek Arsitektur | Pilihan Desain A (Ketegasan Maksimum / Zero-Trust) | Pilihan Desain B (Kecepatan / Dev-Agility) | Analisis Trade-off Engineering |
| :--- | :--- | :--- | :--- |
| **KMS Encryption Strategy** | Customer Managed Key (CMK) multi-account terdedikasi per mikroservis dengan KMS Grants & Encryption Context. | AWS Managed Keys bawaan AWS (`aws/s3`, `aws/ebs`). | **Cost & Quota Limits vs Granularity**: Opsi A menambah biaya baseline KMS key ($1/key/bulan) dan rentan terkena KMS API Throttling limits (default 10.000–50.000 req/sec per region), namun menyediakan audit trail granular dan pemisahan wewenang mutlak. Opsi B gratis dan bebas throttling, tetapi tidak memenuhi PCI-DSS HSM separation requirements. |
| **Automated Remediation Loop** | Blocking / Restrictive Auto-Remediation (misal: otomatis cabut IAM credentials atau putuskan network security group). | Alerting Only via PagerDuty / Slack (Human-in-the-loop triage). | **Availability vs Security Blast Radius**: Remediasi otomatis dapat memicu *cascading outage* jika aturan salah mendeteksi traffic produksi yang sah sebagai anomali (false positive). Alerting only sepenuhnya aman dari risiko downtime, namun membuka celah eksploitasi serangan (*window of vulnerability*). |
| **IAM Permission Boundaries** | Memaksa setiap role CI/CD dan Lambda memiliki batasan Permission Boundary eksplisit. | IAM Managed Policies standard (`PowerUserAccess`, `ReadOnlyAccess`). | **Operational Complexity vs Privilege Escalation**: Permission Boundary memerlukan pipeline maintenance tinggi: developer harus mendefinisikan boundary yang kompatibel untuk setiap microservice baru. Namun, ini memotong 100% risiko developer membuat privilege escalation role menjadi root. |
| **Multi-Region Inspection** | AWS Network Firewall terpusat via Transit Gateway dengan inspection VPC di seluruh active regions. | Distributed Security Group dan VPC peering point-to-point. | **Latency & Infrastructure Cost vs Deep Packet Inspection**: Opsi A menambah latency inspeksi paket stateful (1-3 ms per hop) dan biaya firewall endpoint/data processing yang sangat mahal, namun menyediakan proteksi IDS/IPS Layer 7 terpadu. |

---

### 10. Common Mistakes & Troubleshooting

#### Skenario 1: Terkunci Permanen dari KMS Key Policy (KMS Deadlock)
- **Penyebab**: Membuat KMS CMK dengan Key Policy yang mengisolasi Role atau User tertentu menggunakan ARN spesifik (misal: `arn:aws:iam::111122223333:role/AdminRole`), kemudian Role tersebut terhapus tanpa sengaja. Akun root tidak disertakan dalam policy. Akibatnya, tidak ada identitas lain di dunia yang dapat memodifikasi Key Policy tersebut.
- **Deteksi**: Muncul error `AccessDeniedException` bahkan saat akun root mencoba memanggil `kms:PutKeyPolicy`.
- **Troubleshooting & Remediasi**:
  - Selalu pastikan klausul Root Principal diikutsertakan dalam setiap Key Policy:
    ```json
    {
      "Sid": "RootEnablement",
      "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::<ACCOUNT_ID>:root" },
      "Action": "kms:*",
      "Resource": "*"
    }
    ```
  - *Catatan Kritis*: Jika deadlock telah terjadi dan akun root tidak memiliki hak akses, Anda **wajib** membuka tiket darurat ke AWS Enterprise Support; secara teknis tidak ada API bypass untuk kondisi ini.

#### Skenario 2: Kerentanan Confused Deputy pada AssumeRole Lintas Akun
- **Penyebab**: Sebuah IAM Role lintas akun (`CrossAccountAuditRole`) dibuat untuk di-*assume* oleh SaaS third-party vendor tanpa mewajibkan parameter `sts:ExternalId`. Vendor disusupi, atau attacker memanfaatkan tenant ID vendor untuk mengakses akun target Anda.
- **Deteksi**: AWS CloudTrail mencatat event `sts:AssumeRole` dari IP vendor tanpa adanya field `externalId` di `requestParameters`.
- **Troubleshooting & Remediasi**:
  - Perbaiki trust relationship IAM role dengan mewajibkan conditional check:
    ```json
    {
      "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::VENDOR_ACCOUNT_ID:root" },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "0e84bfa4-8cf1-45df-bbad-90146e9df52c"
        }
      }
    }
    ```

#### Skenario 3: Loop Infinite Eksekusi Otomasi Remediasi
- **Penyebab**: Aturan Config mengevaluasi bahwa resource `NON_COMPLIANT`. Remediation Lambda berjalan dan mengubah resource, namun payload perubahan tidak memenuhi kriteria Config Rule seutuhnya, atau Config Rule membutuhkan waktu 3-5 menit untuk mencatat *state* baru. Akibatnya, Config memicu event non-compliant lagi, mengeksekusi Lambda kembali secara rekursif hingga Lambda timeout / bill shock.
- **Deteksi**: Lonjakan drastis pada metrik `Invocations` dan `Errors` pada AWS Lambda di CloudWatch Metrics, serta ratusan revisi Configuration Item pada AWS Config history.
- **Troubleshooting**:
  - Gunakan `aws sts decode-authorization-message` jika Lambda gagal mengaplikasikan atribut:
    ```bash
    aws sts decode-authorization-message --encoded-message "<ENCODED_BLOB>" --query DecodedMessage --output text | jq .
    ```
  - Implementasikan idempotensi ketat dan *exponential backoff check* pada script Python sebelum mengeksekusi mutasi state. Periksa apakah nilai konfigurasi saat ini sudah sesuai sebelum menembakkan API write.

---

### 11. Best Practices (Production Checklist)

#### 1. Identity and Access Management (IAM) & Governance
- [ ] Root account tidak memiliki Access Key aktif, dilindungi Hardware MFA (FIDO2 WebAuthn), dan akses darurat Break-Glass dikonfigurasi dengan alarm CloudWatch.
- [ ] Seluruh role CI/CD didelegasikan menggunakan IAM Roles for GitHub Actions / GitLab CI via OpenID Connect (OIDC) federated identity tanpa kredensial statis.
- [ ] IAM Permissions Boundary diterapkan wajib pada seluruh peran provisioning delegasi (*Delegated Administrators*).
- [ ] SCP diterapkan di level Root dan OU AWS Organizations untuk memblokir penonaktifan security tooling dan membatasi region operasional (*Region Inoculation*).

#### 2. Kriptografi & Perlindungan Data
- [ ] Rotasi kunci otomatis (`enable_key_rotation = true`) aktif pada seluruh KMS CMK.
- [ ] Gunakan Encryption Context secara deterministik pada setiap API write data sensitif ke KMS.
- [ ] S3 Bucket memblokir enkripsi non-KMS via Bucket Policy (menolak `s3:PutObject` jika header `x-amz-server-side-encryption` bukan `aws:kms`).
- [ ] S3 Object Lock (mode `COMPLIANCE`) diaktifkan untuk immutable audit trail logging buckets.

#### 3. Deteksi & Respons Insiden
- [ ] AWS GuardDuty aktif di seluruh region operasional dengan delegated administrator di Security Account.
- [ ] AWS Security Hub mengaktifkan standar AWS Foundational Security Best Practices (FSBP) dan CIS AWS Foundations Benchmark.
- [ ] AWS Config Recorder aktif mencatat semua resource types (Global & Regional) dengan retensi history terpusat.
- [ ] Event-driven remediation runbook diimplementasikan dengan mekanisme Circuit Breaker (Dead-Letter Queues / DLQ pada EventBridge).

---

### 12. Hands-on Practice

Struktur direktori lab untuk disimpan di `hands-on/m02/`:
```
hands-on/m02/
├── Makefile
├── modules/
│   ├── config_rule/
│   │   ├── main.tf
│   │   └── variables.tf
│   └── remediation_engine/
│       ├── lambda_src/
│       │   └── index.py
│       ├── main.tf
│       └── variables.tf
├── main.tf
├── outputs.tf
├── terraform.tfvars
└── variables.tf
```

#### Langkah-langkah Implementasi Praktikum:

##### Langkah 1: Inisialisasi Workspace
```bash
mkdir -p hands-on/m02/modules/config_rule hands-on/m02/modules/remediation_engine/lambda_src
cd hands-on/m02/
```

##### Langkah 2: Buat Source Code Lambda Remediasi
Tulis file `hands-on/m02/modules/remediation_engine/lambda_src/index.py`:
```python
import json
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)
ec2 = boto3.client('ec2')

def handler(event, context):
    logger.info("Executing automated remediation for Security Group...")
    try:
        detail = event.get('detail', {})
        resource_id = detail.get('requestParameters', {}).get('groupId')
        
        if not resource_id:
            logger.error("No GroupId found in event.")
            return {"status": "FAILED", "reason": "No GroupId"}

        # Revoke inbound SSH from 0.0.0.0/0
        logger.info(f"Revoking quad-zero SSH ingress on {resource_id}")
        ec2.revoke_security_group_ingress(
            GroupId=resource_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 22,
                    'ToPort': 22,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                }
            ]
        )
        return {"status": "SUCCESS", "revoked_group": resource_id}
    except Exception as e:
        logger.error(f"Error executing revoke: {str(e)}")
        raise e
```

##### Langkah 3: Konfigurasi Sub-Module Remediasi (`modules/remediation_engine/main.tf`)
```hcl
variable "kms_key_arn" { type = string }

resource "aws_iam_role" "lambda_exec_role" {
  name = "SecOps-AutoRemediate-SG-Role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_policy" "lambda_policy" {
  name = "SecOps-AutoRemediate-SG-Policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = [
          "ec2:DescribeSecurityGroups",
          "ec2:RevokeSecurityGroupIngress"
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda_src"
  output_path = "${path.module}/lambda.zip"
}

resource "aws_lambda_function" "remediation_func" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "SecOps_RevokePublicSSH"
  role             = aws_iam_role.lambda_exec_role.arn
  handler          = "index.handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = "python3.11"
  timeout          = 30
}

output "lambda_arn" {
  value = aws_lambda_function.remediation_func.arn
}
```

##### Langkah 4: Hubungkan ke EventBridge & Root Config (`main.tf`)
```hcl
provider "aws" {
  region = var.aws_region
}

resource "aws_kms_key" "lab_key" {
  description             = "Hands-on M02 Security Key"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

module "remediation" {
  source      = "./modules/remediation_engine"
  kms_key_arn = aws_kms_key.lab_key.arn
}

resource "aws_cloudwatch_event_rule" "sg_ssh_rule" {
  name        = "CaptureInsecureSGModification"
  description = "Mendeteksi AuthorizeSecurityGroupIngress dengan port 22 terbuka ke publik"

  event_pattern = jsonencode({
    source      = ["aws.ec2"],
    detail-type = ["AWS API Call via CloudTrail"],
    detail = {
      eventSource = ["ec2.amazonaws.com"],
      eventName   = ["AuthorizeSecurityGroupIngress"],
      requestParameters = {
        ipPermissions = {
          items = {
            fromPort = [22],
            ipRanges = {
              items = {
                cidrIp = ["0.0.0.0/0"]
              }
            }
          }
        }
      }
    }
  })
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.sg_ssh_rule.name
  target_id = "TriggerLambdaRemediation"
  arn       = module.remediation.lambda_arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = module.remediation.lambda_arn
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.sg_ssh_rule.arn
}
```

##### Langkah 5: Buat File Pendukung (`variables.tf` dan `Makefile`)
`variables.tf`:
```hcl
variable "aws_region" {
  type    = string
  default = "ap-southeast-1"
}
```

`Makefile`:
```makefile
.PHONY: init plan apply test-exploit destroy

init:
	terraform init

plan:
	terraform plan -out=tfplan.binary

apply:
	terraform apply tfplan.binary

test-exploit:
	@echo "Membuat Security Group yang sengaja melanggar aturan compliance..."
	@VPC_ID=$$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text); \
	SG_ID=$$(aws ec2 create-security-group --group-name "vulnerable-test-sg-$$(date +%s)" --description "Test compliance auto-remediate" --vpc-id $$VPC_ID --query "GroupId" --output text); \
	echo "Security Group Dibuat: $$SG_ID"; \
	echo "Membuka Port 22 ke 0.0.0.0/0 via AWS CLI..."; \
	aws ec2 authorize-security-group-ingress --group-id $$SG_ID --protocol tcp --port 22 --cidr 0.0.0.0/0; \
	echo "Menunggu trigger EventBridge dan eksekusi Lambda (15 detik)..."; \
	sleep 15; \
	echo "Memverifikasi apakah ingress SSH 0.0.0.0/0 berhasil dihapus secara otomatis:"; \
	aws ec2 describe-security-groups --group-ids $$SG_ID --query "SecurityGroups[0].IpPermissions" --output json; \
	echo "Membersihkan Vulnerable SG..."; \
	aws ec2 delete-security-group --group-id $$SG_ID

destroy:
	terraform destroy -auto-approve
```

##### Langkah 6: Eksekusi dan Verifikasi Lab
```bash
make init
make plan
make apply
make test-exploit
```
Amati output `make test-exploit`. Output JSON pada `IpPermissions` akan menampilkan array kosong `[]`, yang membuktikan bahwa ingress port 22 dari `0.0.0.0/0` telah dicabut secara mekanis oleh Lambda. Setelah selesai, jalankan `make destroy`.

---

### 13. Exercise

#### Level Easy
- **Tugas**: Tambahkan IAM Role policy ke deployment lab di atas yang membatasi agar Developer Role hanya bisa meluncurkan EC2 instance jika diberi tag `Environment = Production` atau `Environment = Development`.
- **Kriteria Keberhasilan**: Evaluasi simulasi IAM policy via AWS CLI menghasilkan `ImplicitDeny` jika API `ec2:RunInstances` dipanggil tanpa blok tag yang disyaratkan.

#### Level Medium
- **Tugas**: Modifikasi KMS Key Policy pada `hands-on/m02/` untuk mewajibkan *MFA Session Context* (`aws:MultiFactorAuthPresent: true`) pada pemanggilan API kriptografi asimetris `kms:Sign` dan `kms:Verify`.
- **Kriteria Keberhasilan**: Request penandatanganan payload digital via AWS CLI menggunakan kredensial non-MFA ditolak dengan pesan `AccessDeniedException`.

#### Level Hard
- **Tugas**: Bangun integrasi lintas akun menggunakan Terraform di mana AWS Config Recorder di Akun Workload (`Akun B`) memancarkan finding ke EventBridge bus di Akun Sentral Security (`Akun A`). Di `Akun A`, Step Function mengevaluasi severity finding: jika `CRITICAL`, ia mengasumsikan peran diagnostik di `Akun B` via IAM STS, mencabut instance profile EC2 yang terdampak, dan memasang isolasi Network ACL (NACL) darurat.
- **Kriteria Keberhasilan**: Skenario zero-touch automated quarantine tereksekusi penuh dari Akun A ke Akun B dalam waktu < 20 detik setelah event diterbitkan.

---

### 14. Challenge

**Studi Kasus: Sovereign FinTech Zero-Trust KMS & Dynamic Isolation System**
Sebuah bank digital multinasional memiliki regulasi perlindungan data perbankan yang menetapkan:
1. **Zero Clear-Text Exposure**: Data kredensial pengguna yang tersimpan di Amazon Aurora tidak boleh dapat dibaca bahkan oleh Systems Administrator atau Database Administrator (DBA) yang memiliki hak akses `rds-admin` atau root access ke OS host.
2. **KMS Multi-Region High-Availability & Locality**: Kunci enkripsi harus aktif di dua region (`ap-southeast-1` dan `ap-southeast-3`). Jika terjadi bencana di Region 1, failover ke Region 2 tidak boleh memerlukan dekripsi dan enkripsi ulang seluruh isi database (*In-place Cross-Region Decryption*).
3. **Dynamic Just-In-Time (JIT) Break-Glass Access**: Jika engineer memerlukan akses darurat ke database saat insiden SEV-1, mereka harus mengajukan approval token. Role break-glass hanya valid selama maksimal 60 menit, dibatasi oleh STS Session Policy dinamis yang mengunci akses ke satu IP CIDR tertentu, dan seluruh aktivitas query database harus ditandatangani menggunakan asymmetric key pair yang terisolasi di AWS KMS.

**Spesifikasi Teknis Tantangan**:
- Rancang arsitektur implementasi IaC Terraform lengkap untuk skenario ini tanpa menggunakan modul pihak ketiga tak tepercaya.
- Buat skema Key Policy multi-region dengan KMS Multi-Region Replica Keys.
- Tulis pseudocode atau Python handler yang memvalidasi integrasi STS Session Policy dinamis dan KMS Client-Side Envelope Encryption.
- *Aturan Main*: Tidak boleh ada hardcoded secret, tidak boleh menggunakan wildcard (`*`) pada `Action` di Key Policy, dan seluruh privilege escalation vector harus ditutup rapat.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apa perbedaan mendasar antara Service Control Policy (SCP) dengan IAM Identity-Based Policy?
   - A. SCP memberikan hak akses operasional kepada pengguna di root account.
   - B. SCP berfungsi sebagai filter batas maksimum izin (*guardrail*) untuk akun anggota dan tidak pernah memberikan izin secara langsung.
   - C. SCP hanya berlaku untuk resource S3 dan RDS, sedangkan Identity Policy berlaku untuk semua resource.
   - D. SCP menimpa (*override*) explicit deny yang didefinisikan pada Identity-Based Policy.

2. Mengapa metode Envelope Encryption lebih disukai daripada langsung mengirimkan seluruh payload file besar ke API `kms:Encrypt`?
   - A. Karena KMS tidak mendukung enkripsi simetris.
   - B. Karena API `kms:Encrypt` memiliki batasan payload maksimum 4 KB per request.
   - C. Karena Envelope Encryption tidak memerlukan Customer Master Key (CMK).
   - D. Karena Envelope Encryption berjalan sepenuhnya tanpa menggunakan CPU lokal.

3. Apa konsekuensi teknis jika Anda mengaktifkan rotasi kunci otomatis pada Customer Managed KMS Key (CMK)?
   - A. Seluruh ciphertext lama yang pernah dienkripsi otomatis didekripsi dan dienkripsi ulang.
   - B. Kunci lama dihapus, sehingga data lama tidak dapat didekripsi lagi.
   - C. KMS mempertahankan backing key lama untuk proses dekripsi data lama, dan menggunakan cryptographic backing key baru hanya untuk operasi enkripsi baru.
   - D. Key ARN dan Key ID berubah menjadi string baru setiap tahun.

4. Ketika terjadi konflik evaluasi kebijakan di mana sebuah aksi memiliki evaluasi `Allow` pada Identity-Based Policy dan evaluasi `Deny` pada Resource-Based Policy, apa keputusan akhir dari AWS Authorization Engine?
   - A. `Allow`, karena Identity Policy memiliki prioritas lebih tinggi.
   - B. `Deny`, karena prinsip Explicit Deny selalu menganulir izin apa pun di seluruh hierarchy tree.
   - C. Evaluasi diteruskan ke AWS Organizations SCP untuk voting mayoritas.
   - D. `Allow`, asalkan request dilakukan dari dalam VPC yang sama.

5. Apa fungsi utama dari IAM Permissions Boundary?
   - A. Memblokir akses IP address di luar rentang corporate network.
   - B. Mengatur batas kuota jumlah role yang dapat dibuat dalam satu akun AWS.
   - C. Menetapkan izin maksimum yang dapat dimiliki oleh sebuah IAM Identity (User atau Role), mencegah eskalasi privilese saat membuat policy baru.
   - D. Melakukan rotasi otomatis terhadap password IAM User setiap 90 hari.

#### B. Pertanyaan Intermediate
6. Bagaimana cara mencegah kerentanan keamanan *Confused Deputy Problem* saat mengizinkan layanan SaaS pihak ketiga mengasumsikan IAM Role di akun AWS Anda?
   - A. Menggunakan IP Whitelisting pada Policy Statement.
   - B. Mewajibkan conditional check string `sts:ExternalId` yang unik dan rahasia pada Trust Relationship Policy IAM Role.
   - C. Menghapus permission boundary pada IAM Role tersebut.
   - D. Mengubah Role menjadi IAM User dengan static access keys.

7. Manakah konfigurasi Key Policy KMS berikut yang memberikan kontrol administratif penuh kepada akun tanpa risiko terkunci (*deadlock*) jika suatu IAM Role terhapus?
   - A. Menjadikan Principal bernilai `"AWS": "*"` tanpa condition block.
   - B. Mengizinkan aksi `kms:*` dengan Principal root akun: `"AWS": "arn:aws:iam::<ACCOUNT_ID>:root"`.
   - C. Menambahkan ARN dari seluruh IAM User yang ada ke dalam Key Policy.
   - D. Mengalokasikan Principal ke AWS Service Role default.

8. Dalam arsitektur multi-account, sebuah workload di Akun A ingin membaca objek terenkripsi di S3 Bucket milik Akun B. Bucket tersebut dienkripsi menggunakan KMS CMK milik Akun B. Komponen otorisasi apa saja yang wajib terpenuhi?
   - A. Cukup S3 Bucket Policy di Akun B mengizinkan Akun A.
   - B. Identity Policy di Akun A mengizinkan `s3:GetObject` dan `kms:Decrypt`, S3 Bucket Policy di Akun B mengizinkan Akun A, dan KMS Key Policy di Akun B mengizinkan Akun A untuk `kms:Decrypt`.
   - C. Workload di Akun A harus melakukan disable encryption terlebih dahulu sebelum memanggil `s3:GetObject`.
   - D. Objek harus disalin (*re-encrypt*) ke Akun A menggunakan AWS DataSync tanpa memerlukan KMS permission.

9. Apa perbedaan esensial antara AWS Config Rule bertipe `Change-Triggered` (Event-Based) dengan `Periodic` (Schedule-Based)?
   - A. Change-Triggered dievaluasi saat Configuration Item berubah akibat panggilan API, sedangkan Periodic dievaluasi pada interval waktu tertentu (misal: 24 jam).
   - B. Change-Triggered hanya berjalan untuk EC2, sedangkan Periodic untuk seluruh resource.
   - C. Change-Triggered memerlukan GuardDuty, sedangkan Periodic memerlukan Inspector.
   - D. Periodic berjalan lebih cepat (< 1 detik) dibandingkan Change-Triggered.

10. Ketika sebuah Session Policy diterapkan bersamaan dengan API call `sts:AssumeRole`, bagaimana AWS mengevaluasi izin akhir (*effective permissions*) dari sesi tersebut?
    - A. Menggabungkan seluruh izin (*Union*) dari Identity Policy Role dan Session Policy.
    - B. Mengambil irisan (*Intersection*) di mana suatu aksi harus diizinkan secara eksplisit oleh Identity Policy Role DAN Session Policy.
    - C. Session Policy menimpa (*override*) sepenuhnya seluruh Identity Policy Role.
    - D. Identity Policy Role diabaikan dan hanya SCP yang dievaluasi.

#### C. Skenario Kasus Produksi
11. Tim DevOps melaporkan bahwa aplikasi microservice di EKS gagal melakukan `kms:GenerateDataKey` setelah Anda menambahkan sebuah Service Control Policy (SCP) baru di level Organizational Unit (OU). Padahal, IAM Role pod memiliki Identity Policy `AdministratorAccess` dan KMS Key Policy memiliki izin eksplisit. Apa langkah audit sistematis untuk mengidentifikasi penyebabnya?
    - A. Langsung menghapus seluruh SCP di level root.
    - B. Memeriksa CloudTrail Event untuk error `AccessDenied`, mendekripsi context via `aws sts decode-authorization-message`, dan memeriksa apakah ada `Deny` eksplisit pada SCP baru (misal: pembatasan Region via condition `aws:RequestedRegion` atau tidak di-whitelist-nya aksi KMS).
    - C. Me-restart cluster Kubernetes EKS worker nodes.
    - D. Menghapus dan membuat ulang KMS Key.

12. Pipeline CI/CD Anda yang menggunakan Terraform tiba-tiba gagal saat menjalankan perintah `terraform apply` untuk membuat IAM Role baru bagi engineer tim data. Pesan kesalahan menyatakan: `AccessDenied: User is not authorized to perform: iam:CreateRole with an explicit deny`. Namun, tidak ada SCP Deny yang melarang `iam:CreateRole`. Mengapa ini terjadi?
    - A. Kuota hard-limit IAM Role pada akun telah terlampaui.
    - B. IAM Identity yang digunakan pipeline memiliki Permissions Boundary yang mewajibkan setiap Role baru menyertakan Permissions Boundary spesifik, namun kode Terraform membuat Role tanpa menyertakan argumen `permissions_boundary`.
    - C. AWS IAM sedang mengalami downtime regional.
    - D. Kredensial CI/CD kedaluwarsa tepat saat API call dieksekusi.

13. GuardDuty mendeteksi adanya aktivitas transmisi data mencurigakan dari sebuah EC2 instance ke IP address command-and-control (C2) yang terdaftar dalam daftar ancaman (*Finding: UnauthorizedAccess:EC2/MaliciousIPCaller.Custom*). Anda diinstruksikan mengonfigurasi arsitektur auto-remediation yang mengisolasi instance tersebut dari jaringan tanpa mematikannya (*live forensic ready*). Bagaimana alur perancangan yang benar?
    - A. EventBridge menangkap finding GuardDuty -> Menembakkan sinyal ke Lambda -> Lambda memanggil API `ec2:TerminateInstances`.
    - B. EventBridge menangkap finding GuardDuty berstatus High -> Memicu SSM Automation Runbook -> SSM mengganti Security Group instance dengan Security Group isolasi (Inbound/Outbound kosong), mencabut IAM Instance Profile, dan membuat EBS snapshot volume untuk analisis forensik digital.
    - C. GuardDuty secara default otomatis mematikan kartu jaringan instance tanpa memerlukan konfigurasi tambahan.
    - D. Mengirim pesan webhook ke kanal Slack engineer agar engineer login via SSH untuk mengecek log secara manual.

---

### Kunci Jawaban & Pembahasan Evaluasi

#### A. Basic
1. **B** — SCP bertindak sebagai guardrail batas izin maksimum (*authorization ceiling*) pada AWS Organizations. SCP tidak pernah memberikan hak eksekusi langsung ke user; user tetap memerlukan Identity-Based Policy yang mengizinkan aksi tersebut di dalam batas izin SCP.
2. **B** — KMS HSM dioptimalkan untuk cryptographic operation berkecepatan tinggi dengan payload data kecil. API KMS dibatasi maksimal 4 KB. Untuk payload data yang lebih besar, aplikasi harus memanfaatkan Envelope Encryption dengan Data Key lokal.
3. **C** — Rotasi otomatis pada KMS CMK tidak menghancurkan backing key sebelumnya. KMS menyimpan material kunci lama secara internal agar data historis tetap bisa didekripsi secara transparan, sementara backing key baru otomatis digunakan untuk mengenkripsi data baru.
4. **B** — Sesuai hierarki evaluasi AWS Authorization Engine, klausul `Explicit Deny` mutlak menganulir `Allow` apa pun di layer mana pun (SCP, Resource Policy, Identity Policy, Boundary).
5. **C** — Permissions Boundary berfungsi sebagai pagari batas izin maksimum sebuah IAM Entity. Sangat penting untuk delegated administration agar user/role tidak bisa meningkatkan privilesenya sendiri (*privilege escalation*).

#### B. Intermediate
6. **B** — Parameter rahasia `sts:ExternalId` mencegah skenario Confused Deputy di mana vendor third-party diperdaya penyerang untuk mengeksekusi aksi lintas akun ke target konsumen yang berbeda menggunakan role vendor yang sama.
7. **B** — Mendelegasikan hak akses ke Root account (`arn:aws:iam::<ACCOUNT_ID>:root`) memastikan bahwa kontrol key didelegasikan ke mesin IAM akun tersebut. Jika role spesifik terhapus, admin akun root tetap dapat memperbarui Key Policy melalui IAM policy.
8. **B** — Akses lintas akun (*Cross-Account*) mewajibkan otorisasi dua sisi: Identity Policy di Akun pemanggil harus mengizinkan, DAN Resource Policies (baik S3 Bucket Policy maupun KMS Key Policy) di akun pemilik resource harus secara eksplisit mengizinkan akun pemanggil.
9. **A** — Change-Triggered rule dievaluasi sesaat setelah ada event mutasi state resource yang dicatat oleh Configuration Recorder, sedangkan Periodic rule dievaluasi berdasarkan frekuensi cron yang terjadwal.
10. **B** — Session policy bekerja dengan prinsip evaluasi *Intersection* (irisan logis). Prinsipal hanya memperoleh izin yang didefinisikan secara simultan di Identity-Based Policy role DAN Session Policy tersebut.

#### C. Skenario Kasus Produksi
11. **B** — Pendekatan sistematis dimulai dari decoding pesan error otorisasi via CloudTrail. Seringkali SCP baru memberlakukan Region Inoculation (hanya region tertentu yang diizinkan), dan jika request API KMS internal tertaut ke region lain yang tidak dikecualikan, aksi tersebut akan terkena Explicit Deny dari SCP.
12. **B** — Ini adalah pola desain IAM Permission Boundary standar produksi. Developer/pipeline seringkali diizinkan membuat Role HANYA JIKA role yang dibuat tersebut dilekatkan `permissions_boundary` tertentu (kondisi `StringEquals: iam:PermissionsBoundary`). Jika kode IaC lupa mendefinisikan boundary tersebut, evaluasi IAM menghasilkan Explicit Deny.
13. **B** — Isolasi forensik menuntut mesin tetap menyala (*live memory intact*) agar bukti volatilitas RAM tidak hilang (tidak di-terminate atau di-stop). Mengganti Security Group ke group isolasi tanpa rule (inbound/outbound kosong) menghentikan komunikasi C2 sembari mengizinkan investigator melakukan akuisisi disk snapshot.

---

### 16. Summary

Implementasi cloud security kelas enterprise menuntut peralihan fundamental dari konfigurasi manual (*click-ops*) dan audit retrospektif menuju paradigma **Continuous Governance, Defense-in-Depth, dan Automated Remediation**.

1. **Governance Boundary**: AWS Organizations yang diperkuat Service Control Policies (SCPs) menetapkan batasan mutlak yang tidak dapat ditembus oleh administrator lokal akun anak sekalipun.
2. **Least Privilege & Blast Radius Control**: Arsitektur Zero-Trust diwujudkan dengan memadukan IAM Permissions Boundaries, ABAC dinamis, dan pemisahan akun fisik berdasarkan fungsi lingkungan kerja.
3. **Cryptographic Rigor**: AWS KMS Customer Managed Keys dengan mekanisme Envelope Encryption menjamin data terisolasi secara kriptografis, mencegah eksposur data mentah, dan memenuhi standar regulasi global (PCI-DSS v4.0, SOC 2, ISO 27001).
4. **Event-Driven Resilience**: Deteksi continuous compliance melalui AWS Config dan Security Hub yang dipadukan dengan Amazon EventBridge dan SSM/Lambda memungkinkan ekosistem cloud melakukan *self-healing* terhadap celah keamanan dalam hitungan detik.