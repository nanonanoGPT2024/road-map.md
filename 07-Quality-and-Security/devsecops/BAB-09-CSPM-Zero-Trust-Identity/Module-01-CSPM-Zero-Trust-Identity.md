# Bab 09 Module 01: Cloud Security Posture Management (CSPM) & Zero Trust Identity

---

## 1. Identitas Modul

* **Track**: DevSecOps
* **Kategori**: 07-Quality-and-Security
* **Bab**: 09 Module 01
* **Tingkat Kesulitan**: Lanjutan (Advanced)
* **Prasyarat**:
  * Pemahaman mendalam tentang arsitektur public cloud (AWS IAM, GCP IAM, Azure AD/Entra ID).
  * Penguasaan orkestrasi container berbasis Kubernetes (Pod lifecycle, ServiceAccount, mutating admission controllers).
  * Pemahaman protokol kriptografi web: OAuth 2.0, OpenID Connect (OIDC), JSON Web Tokens (JWT), dan Public Key Infrastructure (PKI).
  * Pengalaman menggunakan Infrastructure as Code (Terraform/OpenTofu) dan Bash scripting.
* **Estimasi Waktu**: 4 Jam

---

## 2. Learning Objectives

Setelah menyelesaikan modul ini, peserta didik mampu:

* **LO-01**: Mengidentifikasi dan menganalisis postur keamanan cloud multi-cloud secara otomatis menggunakan standar kepatuhan industri (CIS Benchmarks, NIST SP 800-53, ISO 27001).
* **LO-02**: Mengonfigurasi dan mengeksekusi engine audit statis dan dinamis berbasis CSPM (*Prowler* dan *ScoutSuite*) dalam pipeline continuous compliance.
* **LO-03**: Menghitung dan mereduksi *entitlement gap* (perbedaan antara izin yang diberikan dan izin yang benar-benar digunakan) melalui metodologi Cloud Infrastructure Entitlement Management (CIEM).
* **LO-04**: Mengimplementasikan prinsip IAM Least Privilege menggunakan IAM Condition Keys, Permission Boundaries, dan Service Control Policies (SCP) / GCP Organization Policies.
* **LO-05**: Merancang arsitektur Zero Trust Identity untuk beban kerja cloud tanpa menggunakan kredensial statis berumur panjang (*long-lived static credentials*).
* **LO-06**: Mengonfigurasi Workload Identity Federation end-to-end antara Kubernetes cluster lokal/cloud dan AWS IAM menggunakan IAM Roles for Service Accounts (IRSA).
* **LO-07**: Mengonfigurasi GCP Workload Identity Federation menggunakan OIDC token exchange (RFC 8693) untuk beban kerja di luar Google Cloud.
* **LO-08**: Menguji ketahanan arsitektur workload identity terhadap serangan Metadata Service Abuse (SSRF pada IMDSv1/v2) dan token theft.

---

## 3. Concept Map & Architecture Diagram

```
+---------------------------------------------------------------------------------------------------+
|                                  ENTERPRISE MULTI-CLOUD CONTROL PLANE                             |
+---------------------------------------------------------------------------------------------------+
                                                  |
           +--------------------------------------+--------------------------------------+
           |                                                                             |
           v                                                                             v
+-------------------------------+                                             +-------------------------------+
|  CSPM & CIEM AUDIT LAYER      |                                             |  ZERO TRUST IDENTITY ENGINE   |
+-------------------------------+                                             +-------------------------------+
| [ScoutSuite]   [Prowler]      |                                             | [OIDC Discovery Endpoint]     |
|       |            |          |                                             | (https://oidc.eks.../keys)    |
|       v            v          |                                             +---------------+---------------+
| Multi-Cloud API Ingestion     |                                                             |
| (AWS Config, GCP Asset Inv)   |                                                             v
|       |                       |                                             +-------------------------------+
|       v                       |                                             | Cloud STS / Identity Pool     |
| [Policy Evaluation Engine]    |                                             | - AWS STS: AssumeRoleWithWebId|
| - CIS Benchmarks v3.0         |                                             | - GCP STS: Token Exchange     |
| - Least Privilege Delta Calc  |                                             +---------------+---------------+
+---------------+---------------+                                                             |
                |                                                                             | Temporary Short-Lived
                v                                                                             | Credentials (Token)
+-------------------------------+                                                             v
| SIEM / Security Lake / Alert  |                                             +-------------------------------+
| (DefectDojo / Jira / AWS SH)  |                                             | Pod / Workload Runtime        |
+-------------------------------+                                             | (K8s Projected Token Vol)     |
                                                                              +-------------------------------+

+---------------------------------------------------------------------------------------------------+
| WORKLOAD IDENTITY FEDERATION: OIDC TOKEN EXCHANGE FLOW                                           |
+---------------------------------------------------------------------------------------------------+

 [Pod: ServiceAccount] -----(1. Injects Projected OIDC JWT)-----> [K8s Pod Runtime]
                                                                        |
                                                               (2. Exchanges JWT)
                                                                        |
                                                                        v
 [Cloud IAM Role] <----(4. Returns Temp Cloud Token)----- [Cloud STS / Identity Provider]
        |                                                               |
        |                                                    (3. Validates Signature)
        |                                                               |
        +---------------------------------------------------------------+
                                        |
                                        v
                            [JWKS Endpoint (K8s OIDC)]
```

---

## 4. Mengapa Ini Penting

Dalam infrastruktur cloud-native modern, batas keamanan perimeter tradisional berbasis jaringan (firewall, IP whitelisting, VPN) telah runtuh. Paradigma telah bergeser ke **Identity as the Primary Security Perimeter**. 

Faktor risiko kritis yang mendorong kebutuhan materi ini meliputi:
1. **Proliferasi Kredensial Statis**: Penggunaan `AWS_ACCESS_KEY_ID` atau GCP Service Account JSON Key pada lingkungan aplikasi sering kali berujung pada kebocoran kunci di repositori Git, artefak container, log CI/CD, atau memori container. Kredensial statis tidak memiliki mekanisme rotasi otomatis bawaan dan memiliki masa aktif tidak terbatas.
2. **Entitlement Creep**: Developer dan DevOps engineer cenderung menggunakan kebijakan wildcard (`"Action": "*"`, `"Resource": "*"`) untuk menghindari hambatan operasional saat *deployment*. Akibatnya, 95% akun cloud memiliki lebih dari 80% izin yang tidak pernah digunakan, memberikan ruang gerak lateral (*lateral movement*) yang masif bagi penyerang.
3. **Misconfiguration Drift**: Kecepatan *deployment* berbasis microservices menyebabkan konfigurasi cloud menyimpang (*drift*) secara kontinu dari standar kepatuhan. Tanpa CSPM otomatis, celah seperti S3 bucket publik, port administratif terbuka (0.0.0.0/0 port 22/3389), atau deaktivasi CloudTrail baru terdeteksi berbulan-bulan setelah insiden terjadi.
4. **Kepatuhan Regulasi**: Kerangka kerja industri seperti PCI-DSS v4.0, SOC 2 Type II, ISO/IEC 27001:2022, dan HIPAA secara eksplisit mewajibkan inventarisasi aset berkelanjutan, penegakan prinsip hak akses terendah (*least privilege*), pemusatan audit log, serta eliminasi kredensial statis.

---

## 5. Apa Itu Konsep

### Cloud Security Posture Management (CSPM)
CSPM adalah metodologi dan kelas perkakas keamanan otomatis yang bertugas mengidentifikasi, mengukur, dan memperbaiki risiko konfigurasi serta kepatuhan pada control plane infrastruktur cloud. CSPM bekerja secara non-intrusif melalui API penyedia cloud (read-only) untuk mengevaluasi status konfigurasi terhadap standar industri seperti Center for Internet Security (CIS) Benchmarks.

### Cloud Infrastructure Entitlement Management (CIEM)
CIEM adalah disiplin keamanan yang berfokus pada manajemen siklus hidup dan tata kelola hak istimewa identitas (manusia maupun mesin/workload) di lingkungan cloud. CIEM menganalisis relasi kompleks antara *Identity* (User, Group, Role), *Entitlement* (Action/Permissions), dan *Resource* (S3, RDS, Compute) untuk menghitung selisih antara *granted permissions* dan *used permissions*, lalu merekomendasikan kebijakan IAM yang benar-benar menerapkan Least Privilege.

### Zero Trust Identity & Workload Identity Federation
Zero Trust Identity adalah paradigma yang mengasumsikan jaringan selalu dalam kondisi terkompromi dan menolak kepercayaan implisit berdasarkan lokasi jaringan fisik maupun logis. Setiap permintaan akses harus diautentikasi dan diotorisasi secara eksplisit, kontekstual, dan terus-menerus.

Workload Identity Federation adalah implementasi Zero Trust untuk identitas mesin (*machine identity*). Mekanisme ini meniadakan kebutuhan kredensial statis berumur panjang dengan cara menukar token identitas pihak ketiga (misalnya JWT OIDC bertanda tangan kriptografis dari Kubernetes cluster atau GitHub Actions) menjadi kredensial cloud sementara (*ephemeral token*) melalui Security Token Service (STS).

---

## 6. Bagaimana Cara Kerjanya

### 6.1. Mekanisme Audit CSPM & CIEM
1. **API Polling & Event Ingestion**: CSPM engine (seperti Prowler atau ScoutSuite) menggunakan kredensial audit dengan hak baca (`ReadOnlyAccess` atau `SecurityAudit`) untuk memanggil API manajemen cloud (e.g., `aws ec2 describe-security-groups`, `gcloud compute firewall-rules list`).
2. **Abstract Syntax Tree (AST) & Graph Evaluation**: Status konfigurasi diubah menjadi model data seragam. Evaluator membandingkan state terhadap assertion logic (contoh: memastikan atribut `publicAccessBlockConfiguration.blockPublicAcls == true`).
3. **IAM Log Parsing (CIEM)**: CIEM engine memproses log aktivitas (AWS CloudTrail, GCP Cloud Audit Logs) dan API Access Analyzer untuk mengekstraksi event `eventSource` dan `eventName` yang benar-benar dieksekusi oleh identitas tertentu selama interval waktu observasi (biasanya 90 hari).
4. **Diff Calculation**: CIEM memetakan izin JSON yang terpasang pada policy identitas terhadap riwayat panggilan API aktual, memotong semua tindakan API yang tidak pernah dipanggil, dan menghasilkan JSON policy yang dipangkas (*pruned*).

### 6.2. Mekanisme Kriptografi Workload Identity (AWS IRSA & GCP WIF)
Proses federasi identitas berbasis OIDC mengikuti alur berikut:

1. **Inisialisasi OpenID Provider**:
   Kubernetes API Server bertindak sebagai OIDC Identity Provider (IdP). Cluster mengekspos endpoint OIDC discovery publik:
   * Discovery Document: `https://<k8s-oidc-endpoint>/.well-known/openid-configuration`
   * JSON Web Key Set (JWKS): `https://<k8s-oidc-endpoint>/keys` (berisi public key RSA/ECDSA untuk verifikasi tanda tangan).
2. **Projected Service Account Token Injection**:
   Saat Pod dideklarasikan dengan `ServiceAccount` tertentu, Pod Admission Controller Kubernetes menginjeksi projected volume berisi OIDC JSON Web Token (JWT) yang ditandatangani oleh private key Kubernetes API server. Token ini memiliki claim terikat:
   * `iss` (Issuer): URL endpoint OIDC cluster K8s.
   * `sub` (Subject): Identitas spesifik workload (`system:serviceaccount:<namespace>:<serviceaccount-name>`).
   * `aud` (Audience): Identifier target (contoh: `sts.amazonaws.com`).
   * `exp` (Expiration): Waktu kedaluwarsa pendek (default 1 jam).
3. **Federation Handshake via STS**:
   SDK cloud di dalam Pod membaca JWT dari disk lokal (misalnya path `/var/run/secrets/eks.amazonaws.com/serviceaccount/token`), kemudian memanggil AWS STS via aksi `AssumeRoleWithWebIdentity` atau GCP STS via OAuth 2.0 Token Exchange (`urn:ietf:params:oauth:grant-type:token-exchange`).
4. **Verifikasi Kriptografis Cloud STS**:
   Layanan STS cloud mengunduh JWKS dari endpoint OIDC Kubernetes publik, memverifikasi validitas tanda tangan digital pada JWT, dan memvalidasi kecocokan claim `iss`, `sub`, dan `aud` dengan Trust Policy/Workload Identity Pool Provider.
5. **Penerbitan Ephemeral Credentials**:
   Jika validasi lolos, STS mengembalikan kumpulan kredensial sementara berumur pendek (15 menit hingga 1 jam):
   * AWS: `AccessKeyId`, `SecretAccessKey`, `SessionToken`.
   * GCP: Google OAuth 2.0 `access_token`.

---

## 7. Perbandingan Paradigma / Taksonomi Matriks

### Matriks Paradigma Keamanan Cloud

| Dimensi | CSPM | CIEM | CWPP (Cloud Workload Protection) | Identity Federation |
| :--- | :--- | :--- | :--- | :--- |
| **Fokus Utama** | Control plane & API configuration | Identity, Roles, & Permissions | Runtime container, host OS, kernel | Autentikasi mesin ke mesin (Zero Trust) |
| **Target Operasi** | Konfigurasi Cloud Provider | IAM Policies, Entitlement Drift | Proses sistem, memori, system calls | Token exchange, kredensial ephemeral |
| **Vektor Ancaman** | Bucket publik, firewall terbuka | Privilege escalation, hak akses berlebih | Remote Code Execution, malware, crypto-mining | Credential leakage, token theft, replay attack |
| **Instrumen Kerja** | Prowler, ScoutSuite, AWS Security Hub | AWS IAM Access Analyzer, Ermetic | Falco, Wiz runtime agent, Prisma Cloud | OIDC, AWS IRSA, GCP Workload Identity |
| **Frekuensi Analisis**| Periodik / Event-driven | Periodik / Continuous behavioral | Real-time continuous (in-kernel) | Real-time pada saat API invocation |

### Matriks Solusi Pemindaian Kepatuhan Multi-Cloud

| Fitur | Prowler | ScoutSuite |
| :--- | :--- | :--- |
| **Bahasa Utama** | Python (Prowler v3/v4 rewritten in Python) | Python |
| **Cakupan Cloud** | AWS, Azure, GCP, Kubernetes | AWS, Azure, GCP, Alibaba Cloud, Oracle Cloud |
| **Framework Kepatuhan**| CIS Benchmarks, NIST 800-53, PCI-DSS, SOC2, ENS | CIS Benchmarks, rule engine kustom |
| **Output Format** | JSON, CSV, HTML, JUnit-XML, AWS Security Hub (ASFF) | HTML report interaktif, JSON |
| **Integrasi Pipeline** | Sangat baik (native CLI exit codes, containerized runner) | Sedang (lebih ditujukan untuk snapshot reporting manual) |
| **Deteksi CIEM** | Menyediakan pemeriksaan IAM mendalam terotomatisasi | Menampilkan relasi visual objek IAM, analisis statis |

---

## 8. Analisis Mendalam Attack Surface & Vector Matrix

```
+---------------------------------------------------------------------------------------------------+
|               ATTACK SURFACE: CLOUD CONTROL PLANE & IDENTITY INTERFACES                           |
+---------------------------------------------------------------------------------------------------+
  [A] Cloud Provider API (Control Plane Drift, Missing MFA, Permissive ACL)
  [B] Instance Metadata Service (IMDSv1 SSRF -> Node Role Credentials Compromise)
  [C] K8s Projected Volume (Local Pod Token Exfiltration -> Cross-Account API Abuse)
  [D] Overprivileged IAM Policies (iam:PassRole, iam:CreatePolicyVersion -> Lateral Escalation)
  [E] OIDC Trust Policy Misconfiguration (Wildcard `*` in Subject -> Cross-Namespace Impersonation)
```

### Attack Vector Matrix (Berdasarkan MITRE ATT&CK for Cloud)

| ID MITRE | Taktik | Teknik / Vektor Serangan | Mekanisme Eksploitasi | Mitigasi Ketat |
| :--- | :--- | :--- | :--- | :--- |
| **T1078.004** | Initial Access | Valid Accounts: Cloud Accounts | Pencurian AWS Access Key statis dari file konfigurasi git commit atau image container publik. | Hapus static keys; implementasikan OIDC Workload Identity Federation secara eksklusif. |
| **T1552.005** | Credential Access | Cloud Instance Metadata API | Eksploitasi kerentanan SSRF pada aplikasi web untuk memanggil endpoint IMDSv1 (`http://169.254.169.254/latest/meta-data/iam/security-credentials/`) guna mencuri role instance worker node. | Paksa penggunaan IMDSv2 (`HttpTokens=required`, `HttpPutResponseHopLimit=1`) dan pisahkan role node dari role pod melalui IRSA. |
| **T1098.003** | Persistence | Additional Cloud Credentials | Penyerang menggunakan izin `iam:CreateAccessKey` pada Service Account terkompromi untuk membuat pintu belakang akses persisten. | Terapkan SCP untuk melarang pembuatan access key secara mandiri; jalankan alert CSPM jika key baru dibuat. |
| **T1548** | Privilege Escalation | Abuse IAM `iam:PassRole` & `iam:CreatePolicyVersion` | Identitas dengan hak terbatas memiliki izin `iam:PassRole` ke role administratif dan mengaitkannya ke instance compute atau Lambda baru. | Terapkan Permission Boundaries pada seluruh identitas; larang kombinasi `iam:PassRole` tanpa pembatasan `Resource` spesifik. |
| **T1099** | Defense Evasion | Modify Cloud Infrastructure Logging | Penyerang mematikan AWS CloudTrail atau GCP Cloud Audit Logs (`cloudtrail:StopLogging`) untuk menghapus jejak forensik. | Kunci CloudTrail menggunakan multi-account organization setup; amankan penyimpanan S3 dengan Object Lock (WORM). |

---

## 9. Code Example Sederhana: Basic IRSA Trust Policy & Kubernetes Manifest

Konfigurasi minimal berikut menghubungkan ServiceAccount Kubernetes dengan AWS IAM Role menggunakan protokol OIDC, membatasi hak akses role hanya untuk Pod di namespace tertentu.

### 1. File: `aws-trust-policy.json`
Policy ini menentukan bahwa hanya ServiceAccount `payment-service-sa` dalam namespace `production` yang diizinkan melakukan assume role.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::112233445566:oidc-provider/oidc.eks.ap-southeast-1.amazonaws.com/id/EXAMPLED3B9A45B1C701B4B6F8E9C2A1"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "oidc.eks.ap-southeast-1.amazonaws.com/id/EXAMPLED3B9A45B1C701B4B6F8E9C2A1:aud": "sts.amazonaws.com",
          "oidc.eks.ap-southeast-1.amazonaws.com/id/EXAMPLED3B9A45B1C701B4B6F8E9C2A1:sub": "system:serviceaccount:production:payment-service-sa"
        }
      }
    }
  ]
}
```

### 2. File: `k8s-workload.yaml`
Manifest Kubernetes yang mendefinisikan ServiceAccount dengan anotasi ARN Role AWS, serta deployment yang mengonsumsi ServiceAccount tersebut.

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: payment-service-sa
  namespace: production
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::112233445566:role/PaymentServiceS3ReadRole
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-processor
  namespace: production
spec:
  replicas: 1
  selector:
    matchLabels:
      app: payment-processor
  template:
    metadata:
      labels:
        app: payment-processor
    spec:
      serviceAccountName: payment-service-sa
      containers:
      - name: processor
        image: alpine:3.19
        command: ["sleep", "3600"]
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          runAsNonRoot: true
          runAsUser: 10001
          capabilities:
            drop:
              - ALL
```

---

## 10. Code Example Lanjutan: Production-Ready Terraform untuk GCP Workload Identity Federation & Prowler Pipeline

### 1. Terraform Enterprise GCP Workload Identity Federation (`main.tf`)
Contoh ini mengonfigurasi federasi OIDC antara pipeline CI/CD (GitHub Actions) dan GCP Service Account dengan pembatasan claim berbasis atribut repositori tanpa menggunakan file JSON service account key.

```hcl
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.15.0"
    }
  }
}

variable "project_id" {
  type        = string
  description = "Target GCP Project ID"
}

variable "github_repo" {
  type        = string
  description = "Format: 'organization/repository'"
  default     = "enterprise-corp/secure-pipeline"
}

# 1. Workload Identity Pool
resource "google_iam_workload_identity_pool" "github_pool" {
  project                   = var.project_id
  workload_identity_pool_id = "gh-actions-pool"
  display_name              = "GitHub Actions Identity Pool"
  description               = "Zero Trust Identity Pool for CI/CD pipelines"
  disabled                  = false
}

# 2. OIDC Provider Binding ke GitHub
resource "google_iam_workload_identity_pool_provider" "github_provider" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "gh-actions-provider"
  display_name                       = "GitHub OIDC Provider"
  
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  attribute_condition = "assertion.repository == '${var.github_repo}' && assertion.ref == 'refs/heads/main'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# 3. Dedicated Least-Privilege GCP Service Account
resource "google_service_account" "ci_deployer" {
  project      = var.project_id
  account_id   = "sa-ci-deployer"
  display_name = "Automated CI/CD Deployer Service Account"
}

# 4. IAM Policy Binding: Mengizinkan OIDC Pool meng-impersonate Service Account
resource "google_service_account_iam_member" "workload_identity_user" {
  service_account_id = google_service_account.ci_deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.repository/${var.github_repo}"
}

# 5. Pemberian Izin Terbatas (Hanya Storage Object Creator, bukan Admin)
resource "google_project_iam_member" "artifact_publisher" {
  project = var.project_id
  role    = "roles/storage.objectCreator"
  member  = "serviceAccount:${google_service_account.ci_deployer.email}"
}

output "workload_identity_provider_name" {
  value = google_iam_workload_identity_pool_provider.github_provider.name
}

output "service_account_email" {
  value = google_service_account.ci_deployer.email
}
```

### 2. Enterprise Prowler CI/CD Automation (`prowler-pipeline.sh`)
Script bash ini mengotomatiskan audit CSPM kepatuhan CIS AWS v3.0, memfilter temuan berstatus `FAIL` dengan tingkat keparahan `CRITICAL`, serta menghentikan pipeline (exit code 1) jika terjadi pelanggaran postur kritis.

```bash
#!/usr/bin/env bash
set -euo pipefail

# Variabel Operasional
PROWLER_VERSION="4.1.0"
REPORT_DIR="./security-reports"
OUTPUT_FILENAME="prowler-compliance-cis-$(date +%Y%m%d%H%M%S)"
CIS_COMPLIANCE_FRAMEWORK="cis_aws_foundations_benchmark_v3.0.0"

mkdir -p "${REPORT_DIR}"

echo "[INFO] Menjalankan Prowler Engine versi: ${PROWLER_VERSION}"
echo "[INFO] Framework yang dievaluasi: ${CIS_COMPLIANCE_FRAMEWORK}"

# Eksekusi Prowler dalam Container Ephemeral menggunakan kredensial STS lingkungan
docker run --rm \
  --name prowler-audit-job \
  -e AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}" \
  -e AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}" \
  -e AWS_SESSION_TOKEN="${AWS_SESSION_TOKEN}" \
  -e AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-ap-southeast-1}" \
  -v "${PWD}/${REPORT_DIR}:/home/prowler/output" \
  "toniblyx/prowler:${PROWLER_VERSION}" \
  aws \
  --compliance "${CIS_COMPLIANCE_FRAMEWORK}" \
  --output-modes json-asff,json,csv,html \
  --output-filename "${OUTPUT_FILENAME}" \
  --output-directory /home/prowler/output \
  --status FAIL

JSON_REPORT="${REPORT_DIR}/${OUTPUT_FILENAME}.json"

if [ ! -f "${JSON_REPORT}" ]; then
  echo "[ERROR] Laporan audit ${JSON_REPORT} tidak ditemukan."
  exit 2
fi

echo "[INFO] Memproses temuan kritis menggunakan jq..."

CRITICAL_FAILURES=$(jq '[.[] | select(.Status == "FAIL" and .Severity == "critical")] | length' "${JSON_REPORT}")
HIGH_FAILURES=$(jq '[.[] | select(.Status == "FAIL" and .Severity == "high")] | length' "${JSON_REPORT}")

echo "=================================================="
echo "          HASIL POSTUR KEPATUHAN AWAL             "
echo "=================================================="
echo "Critical Severity Failures : ${CRITICAL_FAILURES}"
echo "High Severity Failures     : ${HIGH_FAILURES}"
echo "Laporan lengkap tersedia di: ${REPORT_DIR}/${OUTPUT_FILENAME}.html"
echo "=================================================="

# Evaluasi Quality Gate Kepatuhan
if [ "${CRITICAL_FAILURES}" -gt 0 ]; then
  echo "[CRITICAL GATE BREACH] Ditemukan ${CRITICAL_FAILURES} kegagalan kritis CIS Benchmark!"
  jq -r '.[] | select(.Status == "FAIL" and .Severity == "critical") | "ID: \(.CheckID) | Resource: \(.ResourceID) | Deskripsi: \(.StatusExtended)"' "${JSON_REPORT}"
  exit 1
fi

echo "[SUCCESS] Postur cloud memenuhi batas minimum kualitas keamanan."
exit 0
```

---

## 11. Diagram Alur Serangan & Mitigasi

### Skenario: Penetrasi SSRF Menuju Pengambilalihan Cloud Role

```
====================================================================================================
JALUR SERANGAN: TANPA WORKLOAD IDENTITY & CSPM (IMDSv1 & Static Privileges)
====================================================================================================

[ Penyerang ] 
      |
      | (1) HTTP Request dengan Payload SSRF
      v
[ Vulnerable App Container ] 
      |
      | (2) GET /latest/meta-data/iam/security-credentials/ (IMDSv1: No Token Required)
      v
[ EC2 IMDSv1 Engine ] 
      |
      | (3) Merespons dengan Kredensial Worker Node (Overprivileged Instance Role)
      v
[ Vulnerable App Container ] 
      |
      | (4) Ekstraksi AccessKey, SecretKey, SessionToken
      v
[ Penyerang ] 
      |
      | (5) Melakukan API Abuse: Mengakses S3 Terlarang, Eksfiltrasi Database, Eskalasi Lateral
      v
[ Enterprise Cloud Infrastructure (Data Exfiltrated / Resources Abused) ]


====================================================================================================
JALUR TERMITIGASI: DENGAN WORKLOAD IDENTITY (IRSA), IMDSv2, & CSPM GATING
====================================================================================================

[ Penyerang ] 
      |
      | (1) HTTP Request dengan Payload SSRF
      v
[ Hardened App Container ] 
      |
      | (2) GET /latest/meta-data/iam/security-credentials/
      v
[ EC2 IMDSv2 Engine ] 
      |
      | (3) HTTP 401 Unauthorized (IMDSv2 Wajib Melalui Header: X-aws-ec2-metadata-token)
      |     *Hop Limit = 1: Mencegah request traversal dari container network namespace*
      X [Serangan Terhenti di Lapisan Host]
      |
      |-- (Alternatif Skenario: Attacker Mencoba Membaca Token Lokal dari Pod)
      v
[ File Token OIDC K8s: /var/run/secrets/eks.amazonaws.com/serviceaccount/token ]
      |
      | (4) Akses Ditolak jika Container dijalankan sebagai Non-Root dengan SecurityContext ketat
      | (5) Jika token dicuri, attacker memanggil AWS STS -> AssumeRoleWithWebIdentity
      v
[ AWS Security Token Service (STS) ]
      |
      | (6) STS memvalidasi OIDC Subject: Hanya menerima Pod dengan namespace spesifik
      | (7) Izin Role menerapkan CIEM Least Privilege: Hanya aksi S3:PutObject pada folder 'incoming/'
      v
[ Target S3 Bucket ] (Aksi lateral diblokir total, Security Hub membunyikan alert)
```

---

## 12. Trade-offs & Security vs Usability / Performance

| Parameter | Kebijakan Terlalu Ketat (Strict Security) | Kebijakan Terlalu Longgar (Maximum Usability) | Titik Ekuilibrium Rekayasa (DevSecOps Optimal) |
| :--- | :--- | :--- | :--- |
| **Durasi Token Ephemeral** | 15 menit (Paling aman, meminimalkan jendela replay attack). | 12 jam (Mengurangi overhead STS, aplikasi jarang me-refresh token). | **1 Jam dengan mekanisme refresh proaktif otomatis** via background SDK routine. |
| **Granularitas IAM Resource** | Resource ARN spesifik hingga level UUID file individual. | Resource ARN wildcard (`arn:aws:s3:::*/*`). | **Resource ARN berbasis prefix environment & namespace** (e.g., `...:bucket/prod-${app}/*`). |
| **Frekuensi Scanning CSPM** | Continuous scan setiap 5 menit via API polling. | Weekly / Monthly batch audit. | **Event-Driven CSPM** (Audit via AWS EventBridge/CloudTrail logs secara real-time) dikombinasikan dengan Full Scan harian. |
| **Overhead Komputasi OIDC** | Overhead TLS handshake dan komputasi verifikasi JWKS pada setiap pod startup. | Nol overhead (menyimpan plain text static access keys di ConfigMap). | **JWKS caching layer** pada API server / Cloud Provider STS untuk mengeliminasi latency token exchange. |

---

## 13. Edge Cases & Complex Failure Modes

1. **OIDC Provider JWKS Key Rotation Desynchronization**:
   Kubernetes API server merotasi public key signing OIDC secara berkala. Jika cache JWKS pada cloud STS lambat memperbarui key set, STS akan menolak token baru dari pod dengan pesan kegagalan verifikasi tanda tangan kriptografis (`InvalidIdentityTokenException`), mengakibatkan seluruh pod yang baru di-*deploy* mengalami *crash-loop* atau gagal mengakses database.
2. **IMDSv2 Network Hop Limit pada Topology Calico/Cilium CNI**:
   Penetapan `HttpPutResponseHopLimit=1` pada instans cloud dirancang agar request paket IP yang melewati virtual bridge/CNI (hop bertambah menjadi 2) secara otomatis di-*drop*. Namun, jika pod arsitektur *hostNetwork: true* atau node agent (seperti daemon CNI) memerlukan akses IMDS, konfigurasi ini dapat memutus konektivitas jaringan internal node. Pengaturan hop limit harus disesuaikan secara selektif (nilai `2` untuk overlay networks tertentu).
3. **Cross-Account OIDC Trust Loop**:
   Workload Identity Federation yang dikonfigurasi melintasi akun AWS (Cluster di Akun A, Role di Akun B) rentan mengalami kegagalan propagasi jika ARN Trust Policy mengandalkan resource OIDC Provider akun target tanpa deklarasi Trust Provider di Akun A secara bidirectional.
4. **IAM Eventual Consistency Delay**:
   Pembaruan kebijakan IAM di AWS membutuhkan waktu propagasi ke seluruh edge data center global (hingga 10-30 detik). Pipeline otomatis yang membuat role federasi kemudian langsung mengeksekusi test assertion di region lain dapat menerima status `AccessDenied` palsu akibat latensi konsistensi data IAM.

---

## 14. Anti-Patterns & Common Vulnerabilities

### Anti-Pattern 1: Penggunaan Wildcard `*` pada OIDC Subject String
* **Bentuk Buruk**:
  ```json
  "Condition": {
    "StringLike": {
      "oidc.eks.ap-southeast-1.amazonaws.com/id/EXAMPLE:sub": "system:serviceaccount:*"
    }
  }
  ```
* **Dampak**: Semua Pod di cluster Kubernetes dari namespace apa pun (termasuk namespace pengujian atau namespace penyerang) dapat mengambil alih (*assume*) role tersebut.
* **Remediasi**: Tentukan secara eksplisit format namespace dan nama ServiceAccount (`system:serviceaccount:production:payment-app`).

### Anti-Pattern 2: Penyimpanan JSON Service Account Key di Container Image
* **Bentuk Buruk**: Menjalankan instruksi Dockerfile `COPY gcp-sa-key.json /app/credentials.json` dan mengatur environment variable `GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json`.
* **Dampak**: Kunci statis dapat diekstraksi oleh siapa pun yang memiliki hak baca ke image registry, tersimpan di image layers history, dan tidak dapat dicabut tanpa merusak seluruh instance aplikasi yang sedang berjalan.
* **Remediasi**: Mengaktifkan GCP Workload Identity Federation; biarkan Google Client Library mengambil token otomatis melalui Metadata Server emulator.

### Anti-Pattern 3: Kombinasi `iam:PassRole` Tanpa `iam:PassedToService` Restriction
* **Bentuk Buruk**: Memberikan izin `iam:PassRole` dengan `"Resource": "*"` kepada developer atau role CI/CD.
* **Dampak**: Pengguna dapat mengaitkan role istimewa milik entitas lain ke fungsi Lambda atau instans EC2 baru yang mereka kontrol, menghasilkan eskalasi hak akses menjadi administrator penuh.
* **Remediasi**: Batasi `iam:PassRole` dengan klausa `Condition` ketat menggunakan `iam:PassedToService` yang diizinkan (misalnya hanya `ec2.amazonaws.com`).

---

## 15. Best Practices & Enterprise Remediation Guide

```
+---------------------------------------------------------------------------------------------------+
|                        ENTERPRISE REMEDIATION DECISION TREE (CIEM / IAM)                          |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                   Apakah Identitas adalah Mesin?
                                                  |
                         +------------------------+------------------------+
                         | YA                                              | TIDAK (Manusia)
                         v                                                 v
         Apakah Berjalan di Cloud Asli?                         Gunakan Single Sign-On (SSO)
                         |                                      + Enforce Hardware MFA (FIDO2)
           +-------------+-------------+                        + Session Duration < 8 Jam
           | YA                        | TIDAK
           v                           v
Gunakan Native Identity        Gunakan Workload Identity
(AWS IRSA / GCP Workload Id)   Federation (OIDC RFC 8693)
           |                           |
           +-------------+-------------+
                         |
                         v
     Jalankan Analisis CIEM (Evaluasi 90 Hari Aktivitas)
                         |
           +-------------+-------------+
           | Gap Terdeteksi?
           v
 Pangkas Unused Actions dari JSON Policy
 Pasang Permission Boundary & Service Control Policy (SCP)
 Nonaktifkan / Hapus Semua Kunci Akses Statis
```

### Remediation Checklist
1. **Audit Statis Periodik**: Eksekusi Prowler dalam CI/CD pipeline untuk setiap perubahan Terraform/IaC sebelum merger ke branch *production*.
2. **Audit Kredensial Statis**: Jalankan query CIEM bulanan untuk menemukan access keys yang tidak digunakan selama > 30 hari atau berumur > 90 hari, lalu otomatiskan penonaktifan via script/Lambda.
3. **Penegakan IMDSv2 Global**: Aktifkan flag berikut pada seluruh instans EC2 via AWS CLI:
   ```bash
   aws ec2 modify-instance-metadata-options \
     --instance-id i-0123456789abcdef0 \
     --http-tokens required \
     --http-put-response-hop-limit 1 \
     --http-endpoint enabled
   ```
4. **Isolasi Service Control Policy (SCP)**: Larang anggota organisasi membuat AWS IAM User baru atau Access Key baru secara manual di level root AWS Organizations.

---

## 16. Hands-on Lab Step-by-Step

### Skenario Lab
Anda ditugaskan mengaudit akun AWS baru yang terindikasi memiliki celah konfigurasi, menjalankan pemindaian kepatuhan CSPM otomatis dengan Prowler, dan mengonfigurasi federasi identitas Kubernetes tanpa kunci statis.

### Tahap 1: Persiapan Lingkungan dan Scanning via Prowler
Buka terminal workstation Anda dan jalankan audit awal postur IAM:

```bash
# 1. Konfigurasi direktori kerja
mkdir -p ~/cloud-security-lab && cd ~/cloud-security-lab

# 2. Jalankan audit spesifik service IAM menggunakan Prowler via Docker
docker run --rm -ti \
  --name prowler-scan \
  -e AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}" \
  -e AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}" \
  -e AWS_SESSION_TOKEN="${AWS_SESSION_TOKEN:-}" \
  -e AWS_DEFAULT_REGION="ap-southeast-1" \
  -v "${PWD}/prowler-output:/home/prowler/output" \
  toniblyx/prowler:latest \
  aws \
  --services iam \
  --output-modes json,html \
  --output-filename lab-iam-posture
```

### Tahap 2: Menganalisis Temuan Audit
Ekstrak temuan kredensial statis dan wildcard admin:

```bash
# Ekstrak temuan berstatus FAIL pada pemeriksaan IAM
jq -r '.[] | select(.Status == "FAIL") | "Check: \(.CheckID) | Resource: \(.ResourceArn) | Risk: \(.StatusExtended)"' \
  prowler-output/lab-iam-posture.json | tee flagged-vulnerabilities.txt

# Verifikasi temuan iam_user_access_key_old atau iam_root_hardware_mfa_enabled
cat flagged-vulnerabilities.txt
```

### Tahap 3: Implementasi AWS IRSA (Workload Identity)
Gantikan penggunaan access key statis aplikasi dengan IRSA.

```bash
# 1. Tentukan variabel identitas
CLUSTER_NAME="secure-enterprise-k8s"
AWS_REGION="ap-southeast-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
OIDC_ISSUER=$(aws eks describe-cluster --name "${CLUSTER_NAME}" --region "${AWS_REGION}" --query "cluster.identity.oidc.issuer" --output text | sed 's|https://||')

echo "OIDC Issuer: ${OIDC_ISSUER}"

# 2. Siapkan File Trust Relationship Policy
cat <<EOF > irsa-trust-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::${ACCOUNT_ID}:oidc-provider/${OIDC_ISSUER}"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "${OIDC_ISSUER}:aud": "sts.amazonaws.com",
          "${OIDC_ISSUER}:sub": "system:serviceaccount:security-lab:audit-agent-sa"
        }
      }
    }
  ]
}
EOF

# 3. Buat IAM Role Terbatas
aws iam create-role \
  --role-name "SecureAuditAgentRole" \
  --assume-role-policy-document file://irsa-trust-policy.json \
  --description "Role khusus untuk audit agent via IRSA OIDC"

# 4. Pasang Policy Izin Read-Only Spesifik (Least Privilege)
aws iam attach-role-policy \
  --role-name "SecureAuditAgentRole" \
  --policy-arn "arn:aws:iam::aws:policy/SecurityAudit"
```

### Tahap 4: Verifikasi Kredensial Ephemeral di Dalam Pod
Deploy workload uji coba dan verifikasi bahwa pod tidak memiliki AWS Access Key hardcoded, melainkan mengonsumsi projected token.

```bash
# 1. Buat Namespace dan ServiceAccount Kubernetes
kubectl create namespace security-lab --dry-run=client -o yaml | kubectl apply -f -

cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ServiceAccount
metadata:
  name: audit-agent-sa
  namespace: security-lab
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::${ACCOUNT_ID}:role/SecureAuditAgentRole
---
apiVersion: v1
kind: Pod
metadata:
  name: irsa-verification-pod
  namespace: security-lab
spec:
  serviceAccountName: audit-agent-sa
  containers:
  - name: aws-cli
    image: amazon/aws-cli:latest
    command: ["sleep", "3600"]
    env:
      - name: AWS_ROLE_ARN
        value: arn:aws:iam::${ACCOUNT_ID}:role/SecureAuditAgentRole
      - name: AWS_WEB_IDENTITY_TOKEN_FILE
        value: /var/run/secrets/eks.amazonaws.com/serviceaccount/token
EOF

# 2. Tunggu Pod Running
kubectl wait --namespace security-lab --for=condition=Ready pod/irsa-verification-pod --timeout=60s

# 3. Eksekusi STS get-caller-identity di dalam container untuk pembuktian identitas
echo "[VERIFIKASI] Memeriksa identitas aktif di dalam Pod:"
kubectl exec -n security-lab -ti irsa-verification-pod -- aws sts get-caller-identity

# HASIL YANG DIHARAPKAN:
# Arn harus berformat: arn:aws:sts::ACCOUNT_ID:assumed-role/SecureAuditAgentRole/botocore-session-...
```

---

## 17. Real-World Case Study & Incident Analysis Enterprise

### Insiden: Kebocoran Data Capital One (2019)
* **Konteks**: Pencurian data lebih dari 100 juta data nasabah dari AWS S3.
* **Vektor Serangan**: Penyerang mengeksploitasi celah SSRF (Server-Side Request Forgery) pada instance ModSecurity WAF yang berjalan di instans AWS EC2.
* **Mekanisme Eskalasi**:
  1. Penyerang mengarahkan request aplikasi internal untuk menghubungi AWS IMDSv1 di `http://169.254.169.254/latest/meta-data/iam/security-credentials/`.
  2. Karena IMDSv1 tidak memerlukan header token sesi, aplikasi merespons dengan mengembalikan kredensial sementara dari role EC2 instance (`*****WAF-Role`).
  3. **Kegagalan CIEM/Least Privilege**: Role instance EC2 tersebut memiliki hak istimewa berlebih (*overprivileged*) yang mencakup perintah `s3:ListBuckets`, `s3:GetObject` ke seluruh bucket penyimpanan S3 korporat, bukan hanya bucket log lokal WAF.
  4. Penyerang melakukan enumerasi lebih dari 700 S3 buckets dan mengeksfiltrasi database sensifit.

### Evaluasi & Solusi Pasca-Insiden Berbasis Modul Ini
1. **Penerapan IMDSv2 Wajib**: Dengan IMDSv2, serangan SSRF tersebut akan gagal karena IMDSv2 mengharuskan *HTTP PUT* untuk mengambil token sesi dengan header khusus (`X-aws-ec2-metadata-token-ttl-seconds`), yang umumnya diblokir oleh eksploitasi SSRF standar berbasis *HTTP GET*.
2. **Eliminasi Node-Level Privileges**: Apabila aplikasi tersebut menggunakan arsitektur container dengan Workload Identity Federation (IRSA), instance worker node sama sekali tidak memerlukan role yang memiliki akses ke S3, membatasi blast radius penyerang.
3. **Penerapan CSPM Gating**: Kebijakan S3 bucket yang terlalu luas dan instance role yang tidak patuh akan teridentifikasi secara harian oleh rule CSPM seperti `iam_role_administrator_access` dan langsung diremediasi secara otomatis.

---

## 18. Quiz Pemahaman & Challenge

### Pertanyaan Evaluasi

1. Mengapa mekanisme token exchange berbasis OIDC (Workload Identity) secara fundamental lebih aman dibandingkan mendistribusikan AWS IAM Access Keys atau Service Account JSON Key via Kubernetes Secrets?
   * A. Karena token OIDC disimpan permanen di database etcd Kubernetes.
   * B. Karena token OIDC berumur pendek, tidak memerlukan rotasi manual, tidak dapat digunakan di luar konteks audience/issuer yang ditentukan, dan tidak disimpan sebagai artefak statis.
   * C. Karena token OIDC mengenkripsi seluruh payload container saat proses runtime.
   * D. Karena token OIDC menonaktifkan kebutuhan autentikasi ke Security Token Service.

2. Pada implementasi AWS IRSA, peran kritis apa yang dijalankan oleh Kubernetes API Server Discovery Endpoint (`/.well-known/openid-configuration`)?
   * A. Menerbitkan Access Key dan Secret Key kepada Pod secara langsung.
   * B. Mengontrol jalannya mutating admission webhook untuk mengubah image pod.
   * C. Menyediakan lokasi publik JWKS (public keys) agar AWS STS dapat memvalidasi keaslian tanda tangan digital pada JWT token yang dibawa oleh Pod.
   * D. Mengizinkan komunikasi SSH antar node worker di dalam VPC.

3. Dalam evaluasi CIEM, jika sebuah Service Account memiliki policy dengan hak izin 40 aksi S3, namun riwayat log audit (CloudTrail) selama 90 hari terakhir hanya mencatat pemanggilan `s3:GetObject` dan `s3:PutObject`, tindakan remediator yang benar adalah:
   * A. Menghapus Service Account secara permanen dari cloud.
   * B. Menambahkan izin `s3:*` untuk memastikan ketersediaan akses darurat di masa depan.
   * C. Mengubah inline/managed policy untuk membatasi hak akses hanya pada `s3:GetObject` dan `s3:PutObject` untuk resource ARN yang terbukti diakses.
   * D. Mengalihkan otentikasi Service Account ke Basic HTTP Authentication.

4. Celah keamanan apa yang muncul jika dalam Trust Policy AWS IRSA, kondisi `Condition` ditulis sebagai:
   `"StringEquals": { "oidc.eks...:aud": "sts.amazonaws.com" }` tanpa mendeklarasikan klausa assertion untuk claim `sub`?
   * A. Token ditolak secara otomatis oleh AWS STS karena kekurangan sintaks JSON.
   * B. Seluruh Pod dari namespace mana pun dan cluster mana pun yang mempercayai OIDC provider tersebut dapat mengambil alih role yang sama (*cross-workload identity impersonation*).
   * C. Kubernetes API server mengalami kehabisan memori (*out of memory*).
   * D. IMDSv2 akan otomatis aktif secara paksa pada worker node.

5. Manakah konfigurasi IMDS yang paling aman untuk mencegah eksploitasi kredensial instance cloud via serangan SSRF dari dalam microservice container?
   * A. `HttpTokens=optional`, `HttpPutResponseHopLimit=2`
   * B. `HttpTokens=required`, `HttpPutResponseHopLimit=1`
   * C. `HttpEndpoint=disabled`, `HttpTokens=optional`
   * D. `HttpTokens=required`, `HttpPutResponseHopLimit=4`

### Kunci Jawaban
1. **B** — Karakteristik kredensial ephemeral dengan audience, issuer, dan sub claim mengeliminasi risiko kebocoran data statis jangka panjang.
2. **C** — STS cloud memerlukan JWKS publik dari cluster K8s untuk memverifikasi secara asimetris bahwa token memang diterbitkan dan ditandatangani oleh cluster K8s yang sah.
3. **C** — Prinsip eliminasi *entitlement gap* dalam CIEM adalah memangkas hak akses tidak terpakai dan mempertahankan hanya aksi yang terbukti dibutuhkan.
4. **B** — Tanpa pembatasan spesifik pada claim `sub` (`system:serviceaccount:<ns>:<sa>`), setiap entitas yang berhasil mendapatkan token OIDC dari provider tersebut dapat melakukan assume role.
5. **B** — `HttpTokens=required` mewajibkan IMDSv2, dan `HopLimit=1` mencegah paket token melompat keluar dari layer interface jaringan container.

### Hands-on Challenge
* **Skenario**: Anda diberikan sebuah arsitektur microservice di mana Container A (berjalan di cluster GKE) perlu menulis file audit log ke AWS S3 bucket pada Akun AWS korporat yang berbeda, tanpa menggunakan credential statis di cloud mana pun.
* **Tugas Arsitektur**:
  1. Rancang alur otentikasi bertingkat: K8s Service Account Token -> GCP STS -> AWS STS AssumeRoleWithWebIdentity (Federasi Multicloud).
  2. Tulis Trust Policy AWS IAM yang memverifikasi bahwa penerbit token adalah Google Workload Identity Provider atau OIDC GKE target.
  3. Konfigurasi Service Control Policy (SCP) yang melarang pod mengubah header metadata AWS.

---

## 19. Summary & Key Takeaways

* **CSPM** adalah instrumen pengawasan postur konfigurasi cloud yang melakukan audit berkelanjutan terhadap kepatuhan standar industri (seperti CIS Benchmarks) untuk mencegah miskonfigurasi terbuka pada control plane.
* **CIEM** mengatasi krisis hak akses berlebih (*entitlement creep*) dengan membandingkan izin yang didefinisikan (*granted*) terhadap izin yang benar-benar dieksekusi (*used*), memangkas celah eskalasi hak istimewa secara matematis.
* Penggunaan **kredensial statis (Access Keys / JSON Service Account Keys)** pada workload modern adalah **anti-pattern tingkat tinggi** yang harus sepenuhnya digantikan oleh **Workload Identity Federation**.
* Protokol **AWS IRSA** dan **GCP Workload Identity** memanfaatkan standar **OpenID Connect (OIDC)** dan **RFC 8693 Token Exchange** untuk menginjeksi kredensial jangka pendek (*ephemeral*) ke dalam Pod secara otomatis tanpa intervensi manual.
* Pengerasan **IMDSv2** dengan penetapan `HopLimit=1` adalah mitigasi wajib untuk memutus rantai serangan berbasis SSRF dari kompromi beban kerja kontainer ke tingkat control plane cloud.

---

## 20. Referensi Resmi & Standar Keamanan

* **NIST SP 800-207**: *Zero Trust Architecture* (National Institute of Standards and Technology).
* **Center for Internet Security (CIS)**:
  * *CIS Amazon Web Services Foundations Benchmark v3.0.0*.
  * *CIS Google Cloud Platform Foundation Benchmark v3.0.0*.
  * *CIS Kubernetes Benchmark v1.8.0*.
* **IETF RFC Standards**:
  * *RFC 7519: JSON Web Token (JWT)*.
  * *RFC 8693: OAuth 2.0 Token Exchange*.
* **MITRE ATT&CK Matrix for Cloud**: Taktik dan Teknik *Privilege Escalation, Credential Access, Defense Evasion*.
* **Dokumentasi Resmi Vendor**:
  * AWS IAM Documentation: *IAM Roles for Service Accounts (IRSA)*.
  * Google Cloud Architecture Center: *Workload Identity Federation Deep-Dive*.
  * Prowler Security Documentation: *Open-Source Security Assessment, Auditing, Hardening and Incident Response Tool*.