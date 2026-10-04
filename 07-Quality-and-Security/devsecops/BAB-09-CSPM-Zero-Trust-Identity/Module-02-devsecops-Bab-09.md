# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 09: CSPM, Zero Trust, & Cloud Identity Engineering**
**Jalur Pembelajaran: DevSecOps (07-Quality-and-Security)**

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Merancang dan mengoperasikan arsitektur **Cloud Security Posture Management (CSPM)** dan **Cloud Infrastructure Entitlement Management (CIEM)** secara otomatis pada lingkungan *multi-cloud* dan *hybrid*.
- Mengeliminasi 100% *long-lived credentials* pada siklus hidup CI/CD dan runtime beban kerja (*workloads*) menggunakan standar **SPIFFE/SPIRE** dan **OpenID Connect (OIDC) Workload Identity Federation**.
- Mengimplementasikan **Policy-as-Code (PaC)** menggunakan Open Policy Agent (OPA) dan Rego untuk evaluasi kepatuhan (*compliance*) secara preventif di pipeline dan reaktif di tingkat infrastruktur *runtime*.
- Membangun *event-driven continuous remediation loop* yang memitigasi *configuration drift* dan eskalasi hak akses (*privilege escalation*) dalam waktu di bawah 60 detik tanpa mengganggu ketersediaan layanan (*zero-downtime*).

---

## 2. Prerequisite
Peserta wajib memiliki pemahaman mendalam pada domain berikut:
- **Cloud Infrastructure & Networking**: AWS/GCP IAM core concepts (Role Assumption, Trust Policies, Service Accounts, VPC Endpoints, Mutual TLS).
- **Container & Orchestration**: Kubernetes internals (ServiceAccount tokens, Mutating/Validating Admission Webhooks, CRI/CNI).
- **IaC & Tooling**: Terraform/OpenTofu level menengah (state management, dynamic blocks), GitOps workflows (ArgoCD/Flux).
- **Security Foundations**: Public Key Infrastructure (PKI), X.509 certificates, OAuth 2.0 / OIDC specifications, JSON Web Tokens (JWT).

---

## 3. Concept & Internal Architecture (Mendalam)

Implementasi Zero Trust pada lapisan infrastruktur cloud menuntut perubahan paradigma dari perimeter berbasis IP menjadi perimeter berbasis identitas kriptografis (*cryptographic identity*), hak akses kontekstual (*context-aware access*), dan continuous verification.

### 3.1 Arsitektur Internal CSPM & Continuous Compliance Engine
Mesin CSPM modern tidak lagi hanya mengandalkan *polling* API periodik yang lambat dan membebani rate limit cloud provider. Arsitektur CSPM enterprise modern berbasis **Event-Driven Graph Model**:

```
+---------------------------------------------------------------------------------------------------+
|                                EVENT-DRIVEN GRAPH-BASED CSPM ENGINE                               |
+---------------------------------------------------------------------------------------------------+
                                                                                                     
   +------------------+     CloudTrail / Audit Logs                                                 
   | Cloud Resources  |----------------------------------+                                          
   | (S3, IAM, K8s)   |                                  |                                          
   +------------------+                                  v                                          
             |                                +----------------------+                              
      State  | Mutations                      | EventBridge / PubSub |                              
             v                                +----------------------+                              
   +------------------+                                  |                                          
   | Cloud Asset API  |                                  v                                          
   | (Asset Inventory)|                       +----------------------+                              
   +------------------+                       | Stream Processor     |                              
             |                                | (Kafka / Flink / Go) |                              
             | Sync Snapshot                  +----------------------+                              
             v                                           |                                          
   +-----------------------------------------------------+                                          
   |                                                                                                
   v                                                                                                
+----------------------+         Policy Query          +-----------------------+                    
| Dynamic Graph Engine | <---------------------------- | Open Policy Agent     |                    
| (Neo4j / Amazon      |                               | (Rego Engine)         |                    
|  Neptune / In-Memory)| ----------------------------> | Evaluates AST Rules   |                    
+----------------------+        Graph Traversal        +-----------------------+                    
          |                                                        |                                
          v                                                        v                                
+------------------------------------------------------------------------------+                    
| Risk Vector Calculation: Effective Permissions, Blast Radius, Drift Finding |                    
+------------------------------------------------------------------------------+                    
          |                                                        |                                
    Alert | (P1/P0)                                                | Auto-Remediate                 
          v                                                        v                                
+----------------------+                               +-----------------------+                    
| SIEM / Security Data |                               | Step Functions / Go   |                    
| Lake (Splunk/SnowFlk)|                               | Idempotent Worker     |                    
+----------------------+                               +-----------------------+                    
```

1. **Ingestion & Topology Graphing**: Setiap mutasi resource memicu *event* (misal: AWS CloudTrail via EventBridge). Event tersebut dinormalisasi ke dalam *directed acyclic graph* (DAG) yang merepresentasikan relasi: `Identity -> Role -> Policy -> Resource -> Data Class`.
2. **Effective Entitlements Calculation (CIEM Engine)**: Analisis kombinatorial terhadap Service Control Policies (SCP), IAM Permissions Boundary, Group Policies, Session Policies, dan Resource-Based Policies. Tujuannya adalah mengidentifikasi *implicit access* dan *lateral movement paths*.
3. **Continuous Policy Enforcement**: Aturan OPA Rego dievaluasi terhadap node graf. Jika suatu node bertentangan dengan *baseline*, *alert* deterministik dan payload remediasi segera diterbitkan.

### 3.2 SPIFFE/SPIRE: The Zero Trust Workload Identity Standard
Zero Trust Workload Identity menghapus ketergantungan pada kredensial statis (API keys, IAM secret keys). 
- **SPIFFE ID**: URI standar terstruktur yang mengidentifikasi beban kerja secara unik, contoh: `spiffe://prod.internal.net/ns/payment/sa/checkout-service`.
- **SVID (SPIFFE Verifiable Identity Document)**: Kredensial kriptografis dalam bentuk sertifikat X.509 (X509-SVID) atau token JWT (JWT-SVID) berumur pendek (*short-lived*, misal 10–60 menit).
- **SPIRE Server & Agent**:
  - `SPIRE Server` mengelola *trust bundle*, memvalidasi registrasi node, dan mengotorisasi penerbitan SVID.
  - `SPIRE Agent` berjalan sebagai daemon lokal (DaemonSet di K8s), mengatestasi beban kerja (*Workload Attestation*) menggunakan kernel metadata (PID, UID, cgroups, K8s namespace/serviceAccount), lalu menyuntikkan SVID via domain socket IPC (Workload API) ke dalam memori aplikasi tanpa menyentuh disk.

---

## 4. Why & What

| Dimensi | Pendekatan Tradisional (Perimeter/Static) | Pendekatan Enterprise Zero Trust & Modern CSPM |
| :--- | :--- | :--- |
| **Identitas Workload** | IAM Access Keys statis disimpan di GitHub Secrets atau Kubernetes Secret (`.env`, configmap). Rentan kebocoran. | Identitas ephemeral berbasis atestasi kriptografis (OIDC Federation, SPIFFE/SPIRE SVIDs) dengan TTL pendek (< 1 jam). |
| **Pemeriksaan Postur (CSPM)** | Audit manual berbasis checklist bulanan atau scanner statis batch 24 jam sekali. | Continuous Graph-based Drift Detection berbasis *stream events*. Latensi deteksi < 10 detik. |
| **Hak Akses (IAM/CIEM)** | Role "Super Admin" atau wildcard permissions (`s3:*`, `iam:*`) demi kemudahan operasional. | Hak akses terkalkulasi dinamis (*least-privilege*), *just-in-time* (JIT) access, mitigasi *toxic combinations*. |
| **Remediasi** | Tiket JIRA manual yang ditinjau berminggu-minggu; drift dibiarkan menumpuk. | *Automated Policy-driven Remediation* via serverless worker untuk pelanggaran fatal (misal: S3 Public Access). |

---

## 5. How (Workflow Detail)

### Alur Kerja: Zero Trust CI/CD OIDC to Multi-Cloud
Diagram ini mengilustrasikan eliminasi total static keys pada eksekusi deployment Terraform dari CI/CD:

```
[GitHub Actions Runner]        [GitHub OIDC IdP]           [AWS STS / Cloud IAM]          [Cloud Provider Target]
         |                             |                             |                             |
         | 1. Minta OIDC Token         |                             |                             |
         |---------------------------->|                             |                             |
         |                             |                             |                             |
         | 2. Kembalikan Signed JWT    |                             |                             |
         |<----------------------------|                             |                             |
         |                             |                             |                             |
         | 3. AssumeRoleWithWebIdentity(JWT, RoleARN)                |                             |
         |---------------------------------------------------------->|                             |
         |                                                           |                             |
         |                             4. Validasi Signature & Claims|                             |
         |                             |  - iss: token.actions.githubusercontent.com               |
         |                             |  - aud: sts.amazonaws.com   |                             |
         |                             |  - sub: repo:org/repo:ref...|                             |
         |                                                           |                             |
         | 5. Terbitkan Short-Lived Session Credentials (15 Menit)   |                             |
         |<----------------------------------------------------------|                             |
         |                                                                                         |
         | 6. Jalankan Terraform Deploy (Gunakan Token Ephemeral)                                  |
         |---------------------------------------------------------------------------------------->|
```

### Alur Kerja: Continuous Graph CSPM Remediation
1. Pengembang mengubah bucket S3 menjadi `Public Read` via AWS Console (Drift).
2. AWS CloudTrail mencatat event `PutBucketAcl` atau `PutBucketPolicy` dan mengirimkannya ke Amazon EventBridge.
3. EventBridge mengeksekusi routing pattern yang memicu AWS Step Functions.
4. Step Functions memanggil OPA Engine untuk mengevaluasi apakah bucket tersebut memiliki anotasi pengecualian formal (*exemption*).
5. Jika tidak ada pengecualian yang sah, Lambda Remediation Worker memanggil API `PutPublicAccessBlock` dengan parameter strict blocking.
6. Notifikasi terstruktur dipublikasikan ke SIEM dan kanal Slack DevSecOps beserta audit log ID.

---

## 6. Analogy & Diagram ASCII

### Analogi Kartu Akses Hotel Ephemeral
- **Static Credentials**: Kunci fisik kuningan yang dibuat sekali dan diberikan ke karyawan. Jika hilang atau diduplikasi oleh pihak tidak bertanggung jawab, penyerang dapat masuk ke seluruh ruangan kapan saja tanpa jejak.
- **Zero Trust OIDC / SPIFFE**: Kartu akses digital NFC hotel dengan enkripsi dinamis. Kartu ini hanya aktif jika sistem mengenali wajah karyawan di meja resepsionis (Workload Attestation), hanya bisa membuka kamar lantai 4 (Least Privilege), dan kodenya hangus secara otomatis setiap 15 menit.

```
       +-----------------------------------------------------------+
       |                TRADITIONAL PERIMETER SECURITY             |
       |                                                           |
       |   +---------------+                                       |
       |   | Hard Outer    |    (Once inside, unrestricted         |
       |   | Firewalls/VPN |     lateral movement occurs)          |
       |   +---------------+                                       |
       |           \                                               |
       |            v                                              |
       |      [DB] <=======> [App Svc] <=======> [Payment Svc]     |
       |            (Static Password)    (Static Keys)             |
       +-----------------------------------------------------------+

                                    VS

       +-----------------------------------------------------------+
       |                 ZERO TRUST ARCHITECTURE (ZTA)             |
       |                                                           |
       |   Explicit Verification on Every Transaction:             |
       |   1. Who are you? (Cryptographic Workload Attestation)    |
       |   2. Are you authorized RIGHT NOW? (Continuous OPA/CIEM)  |
       |   3. Minimal blast radius (Mutual TLS + Micro-segment)    |
       |                                                           |
       |   +---------+        mTLS SVID        +---------+         |
       |   | App Svc | ----------------------> | Pay Svc |         |
       |   +---------+                         +---------+         |
       |        ^                                   ^              |
       |        | (Local Domain Socket)             |              |
       |   +-------------+                     +-------------+     |
       |   | SPIRE Agent |                     | SPIRE Agent |     |
       |   +-------------+                     +-------------+     |
       +-----------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: OPA Rego Policy untuk Validasi Enkripsi S3 (Static Rule)
Pemeriksaan konfigurasi statis berbasis OPA untuk mencegah deployment bucket tanpa KMS Customer Managed Keys (CMK).

```rego
package cloud.aws.storage

default allow = false

# Allow hanya jika server_side_encryption_configuration terdefinisi dengan KMS
allow {
    count(violation) == 0
}

violation[msg] {
    bucket := input.resource.aws_s3_bucket[name]
    not bucket.server_side_encryption_configuration
    msg := sprintf("S3 Bucket '%v' wajib mendefinisikan server_side_encryption_configuration.", [name])
}

violation[msg] {
    sse := input.resource.aws_s3_bucket[name].server_side_encryption_configuration.rule.apply_server_side_encryption_by_default
    sse.sse_algorithm != "aws:kms"
    msg := sprintf("S3 Bucket '%v' menggunakan algoritma enkripsi lemah '%v'. Wajib menggunakan 'aws:kms'.", [name, sse.sse_algorithm])
}
```

### 7.2 Practical Example: Enterprise-Grade Workload Identity Federation (Terraform)
Konfigurasi OIDC Role AWS yang diikat secara presisi ke repositori GitHub Actions tertentu tanpa kredensial statis.

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

variable "github_org" {
  type        = string
  description = "Organisasi GitHub Enterprise"
  default     = "enterprise-core"
}

variable "github_repo" {
  type        = string
  description = "Nama repositori GitHub"
  default     = "payment-gateway"
}

# 1. OpenID Connect Provider untuk GitHub Actions (Idempotent)
data "tls_certificate" "github_actions" {
  url = "https://token.actions.githubusercontent.com/.well-known/openid-configuration"
}

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.github_actions.certificates[0].sha1_fingerprint]
}

# 2. IAM Role dengan AssumeRole Trust Policy Terbatas Ketat
resource "aws_iam_role" "cicd_workload_identity" {
  name        = "github-actions-payment-gateway-deployer"
  description = "Role Zero Trust untuk deployment CI/CD tanpa static secret"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" : "sts.amazonaws.com"
          }
          StringLike = {
            # Mengunci asumsi role HANYA dari branch 'main' di repo spesifik
            "token.actions.githubusercontent.com:sub" : "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/main"
          }
        }
      }
    ]
  })

  max_session_duration = 3600 # 1 Jam Maksimal
}

# 3. Principle of Least Privilege: Role Policy terikat
resource "aws_iam_role_policy" "deploy_permissions" {
  name = "PaymentGatewayDeployRestrictedPolicy"
  role = aws_iam_role.cicd_workload_identity.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowECSUpdateOnly"
        Effect = "Allow"
        Action = [
          "ecs:UpdateService",
          "ecs:DescribeServices"
        ]
        Resource = "arn:aws:ecs:*:*:service/production-cluster/payment-service"
      }
    ]
  })
}
```

### 7.3 Practical Example: Automated Remediation Engine (Go Lambda)
Fungsi Go tingkat produksi yang dipicu oleh EventBridge CSPM drift untuk memblokir akses publik pada Amazon S3 secara deterministik.

```go
// cmd/remediate/main.go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"
	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	s3types "github.com/aws/aws-sdk-go-v2/service/s3/types"
)

type S3ClientAPI interface {
	PutPublicAccessBlock(ctx context.Context, params *s3.PutPublicAccessBlockInput, optFns ...func(*s3.Options)) (*s3.PutPublicAccessBlockOutput, error)
}

type RemediationEngine struct {
	s3Client S3ClientAPI
	logger   *slog.Logger
}

func (r *RemediationEngine) HandleSecurityEvent(ctx context.Context, event events.CloudWatchEvent) error {
	r.logger.Info("Menganalisis security drift event", "source", event.Source, "id", event.ID)

	var detail map[string]interface{}
	if err := json.Unmarshal(event.Detail, &detail); err != nil {
		return fmt.Errorf("gagal unmarshal event detail: %w", err)
	}

	requestParams, ok := detail["requestParameters"].(map[string]interface{})
	if !ok {
		return fmt.Errorf("payload CloudTrail tidak memuat requestParameters")
	}

	bucketName, ok := requestParams["bucketName"].(string)
	if !ok || bucketName == "" {
		return fmt.Errorf("nama bucket target tidak ditemukan dalam event")
	}

	r.logger.Warn("Pelanggaran Postur Terdeteksi: Bucket S3 Terbuka Publik! Memulai Remediasi Otomatis", "bucket", bucketName)

	// Idempotent Remediation: Menerapkan Strict Public Access Block
	_, err := r.s3Client.PutPublicAccessBlock(ctx, &s3.PutPublicAccessBlockInput{
		Bucket: aws.String(bucketName),
		PublicAccessBlockConfiguration: &s3types.PublicAccessBlockConfiguration{
			BlockPublicAcls:       aws.Bool(true),
			BlockPublicPolicy:     aws.Bool(true),
			IgnorePublicAcls:      aws.Bool(true),
			RestrictPublicBuckets: aws.Bool(true),
		},
	})
	if err != nil {
		r.logger.Error("Gagal meremediasi bucket posture", "bucket", bucketName, "error", err)
		return err
	}

	r.logger.Info("Remediasi Berhasil: Public Access Block Diterapkan", "bucket", bucketName)
	return nil
}

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	cfg, err := config.LoadDefaultConfig(context.Background())
	if err != nil {
		logger.Error("Gagal memuat AWS SDK config", "error", err)
		os.Exit(1)
	}

	engine := &RemediationEngine{
		s3Client: s3.NewFromConfig(cfg),
		logger:   logger,
	}

	lambda.Start(engine.HandleSecurityEvent)
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Bank FinTech Skala Regional (120+ Microservices, 15 Juta Transaksi/Hari)
* **Status Awal (Masalah)**:
  - Terdapat 400+ IAM Users pada akun AWS produksi dengan static access keys berumur rata-rata 480 hari.
  - Sebuah access key developer bocor ke pastebin publik, mengakibatkan penyerang memutar (*spinning up*) instans GPU ilegal dan mencoba eksfiltrasi snapshot Amazon RDS.
  - Audit menemukan 1.200 role yang memiliki izin `s3:*` atau `administratorAccess` karena tidak adanya platform CIEM.
* **Arsitektur Solusi DevSecOps**:
  1. **IAM Sanitization via OIDC & SPIFFE**:
     - Menghapus 100% IAM User static keys dalam waktu 60 hari.
     - Mengimplementasikan GitHub Actions OIDC Federation untuk CI/CD.
     - Mengimplementasikan SPIFFE/SPIRE pada cluster Amazon EKS. Setiap pod backend berkomunikasi ke RDS Postgres via short-lived AWS IAM database authentication tokens yang diminta menggunakan X509-SVID, bukan password statis di Kubernetes Secret.
  2. **Autonomous CIEM Engine**:
     - Menjalankan open-source engine analitik IAM berbasis Graf yang mengidentifikasi *dormant entitlements* (izin yang tidak terpakai selama 90 hari) secara otomatis.
     - CIEM Engine menghasilkan pull-request otomatis ke repositori Terraform infrastruktur untuk mengecilkan (*prune*) *wildcard permissions* ke level ARN spesifik.
  3. **Event-Driven CSPM**:
     - Mengintegrasikan AWS CloudTrail -> Amazon EventBridge -> Open Policy Agent Engine -> Lambda Auto-Remediator.
     - Setiap Security Group yang dibuka dengan port `0.0.0.0/0` selain port 443/80 pada Elastic Load Balancer dihapus (*revoked*) secara instan dalam waktu 8 detik.
* **Hasil Pengukuran (Metrics)**:
  - **Attack Surface**: Zero permanent credentials di seluruh cluster EKS dan pipeline CI/CD.
  - **Mean Time to Remediate (MTTR)**: Turun dari **14 hari** (proses approval manual tiket JIRA) menjadi **12 detik** (otomatis).
  - **Compliance Audit Score**: Nilai kepatuhan PCI-DSS 4.0 dan ISO 27001 naik dari 64% menjadi 99.8%.

---

## 9. Trade-offs

| Aspek Arsitektur | Keuntungan | Biaya / Trade-off | Mitigasi Engineering |
| :--- | :--- | :--- | :--- |
| **Short-Lived OIDC / SVID Tokens** | Menghilangkan risiko kebocoran static credential jangka panjang. Audit log sangat akurat. | Ketergantungan tinggi pada ketersediaan Identity Provider (IdP). Latensi regenerasi token. | Menggunakan caching token in-memory lokal dengan fallback renewal interval (misal: refresh token saat masa aktif tinggal 20%). |
| **Automated CSPM Remediation** | Menutup celah eksploitasi dalam hitungan detik (*near real-time*). | Risiko pemutusan operasional mendadak (*blast radius*) jika terjadi *false positive* pada sistem kritis. | Mode "Audit-Only" (Shadow Mode) selama 30 hari pertama sebelum beralih ke "Active Auto-Remediation"; sertakan *dry-run engine*. |
| **Graph-based CIEM Analysis** | Mampu memetakan *chained privilege escalation paths* yang tidak terlihat oleh linter biasa. | Menghabiskan resource komputasi tinggi; biaya pemeliharaan infrastruktur database graf (Neptune/Neo4j). | Menggunakan event-driven delta updates daripada melakukan full-graph re-indexing setiap jam. |

---

## 10. Common Mistakes & Troubleshooting

### Kesalahan Umum 1: Mengabaikan Validasi Claim `sub` pada OIDC Trust Policy
* **Symptom**: Pengembang mengonfigurasi OIDC provider AWS untuk GitHub, namun hanya menetapkan condition `StringEquals: { "aud": "sts.amazonaws.com" }` tanpa memvalidasi atribut `sub` (subject).
* **Impact**: **Critical Vulnerability**. Siapa pun di dunia yang memiliki akun GitHub dapat membuat GitHub Action, menggunakan provider ARN tersebut, dan mengasumsikan role IAM produksi Anda.
* **Root Cause & Fix**: Atribut `sub` wajib memvalidasi nama organisasi dan repositori secara eksplisit:
  ```json
  "Condition": {
    "StringEquals": {
      "token.actions.githubusercontent.com:sub": "repo:my-secure-org/my-target-repo:ref:refs/heads/main"
    }
  }
  ```

### Kesalahan Umum 2: Cascading Failure Akibat Auto-Remediation Loop
* **Symptom**: Lambda remediator mengubah suatu konfigurasi resource, perubahan tersebut memicu CloudTrail event baru, yang kembali memicu Lambda remediator secara rekursif (infinite bill shock & resource locking).
* **Impact**: Rate limiting AWS CloudTrail, biaya komputasi membengkak drastis, logging platform terbebani.
* **Fix**: Evaluasi metadata event (`userIdentity.arn`). Jika pemanggil event mutasi adalah ARN dari Service Role Remediation Lambda itu sendiri, *short-circuit* (langsung return nil dan abaikan pemrosesan).

### Panduan Troubleshooting: SVID Attestation Failure pada SPIRE
Jika Pod gagal mendapatkan identity dari SPIRE Agent Workload API:
1. Periksa path Unix Domain Socket yang di-*mount* ke dalam Pod:
   ```bash
   ls -la /run/spire/sockets/agent.sock
   ```
2. Jalankan binary `spire-agent api fetch` dari dalam container untuk memeriksa respons error spesifik:
   ```bash
   /opt/spire/bin/spire-agent api fetch x509 -socketPath /run/spire/sockets/agent.sock
   ```
3. Jika keluar error `Caller is not attested`:
   - Validasi selector pod di SPIRE Server (`k8s:ns:<namespace>`, `k8s:sa:<serviceaccount>`).
   - Pastikan Kubelet Read-Only Port atau Token Review API dapat diakses oleh SPIRE Agent untuk memverifikasi PID dari kernel.

---

## 11. Best Practices (Production Checklist)

### Fase Desain & Arsitektur
- [ ] Tidak ada lagi `AWS_ACCESS_KEY_ID` atau secret token jangka panjang yang disimpan di GitHub Secrets, GitLab CI Variables, ataupun Terraform state.
- [ ] Batasi masa hidup sesi (*maximum session duration*) dari assume-role OIDC maksimal 1 jam untuk pipeline, dan 15 menit untuk tugas eksekusi berkala.
- [ ] Seluruh workload compute (Kubernetes Pods, Nomad allocations, VM) harus memperoleh hak akses cloud menggunakan IAM Role via Service Account / Workload Identity.

### Fase Implementasi Kebijakan (Policy Enforcement)
- [ ] Menerapkan OPA Gatekeeper / Kyverno pada Kubernetes Admission Controller untuk memblokir container yang berjalan dengan flag `securityContext.privileged: true`.
- [ ] Menerapkan AWS Service Control Policies (SCPs) di tingkat Organization untuk memblokir penonaktifan guardrail (contoh: melarang `cloudtrail:StopLogging` dan `guardduty:DeleteDetector`).
- [ ] Menjalankan CSPM engine secara hybrid: *Static PaC* di pipeline Git pull-request + *Continuous Event-Driven* di live cloud state.

### Fase Operasional & Pemantauan
- [ ] Logging tersentralisasi untuk seluruh transaksi assume role berbasis OIDC dengan metrik anomali (misal: penyerapan kredensial di luar IP range CI runner resmi).
- [ ] Menerapkan circuit-breaker pada Lambda Remediation untuk mencegah *mass teardown* jika terjadi *misconfigured policy*.

---

## 12. Hands-on Practice

Buat seluruh struktur pengujian di direktori `hands-on/m02/`.

```bash
mkdir -p hands-on/m02/{policies,iac,remediator}
cd hands-on/m02/
```

### Langkah 1: Tulis Kebijakan OPA untuk Mendeteksi IAM Privilege Escalation
Simpan file berikut di `policies/iam_check.rego`:

```rego
package devsecops.iam

default allow = false

# Definisi action berbahaya yang memungkinkan eskalasi hak akses lateral
dangerous_actions := [
    "iam:CreatePolicyVersion",
    "iam:SetDefaultPolicyVersion",
    "iam:PassRole",
    "iam:CreateAccessKey",
    "iam:AttachUserPolicy",
    "iam:AttachRolePolicy"
]

allow {
    count(escalation_risks) == 0
}

escalation_risks[msg] {
    statement := input.Statement[_]
    statement.Effect == "Allow"
    
    # Periksa apakah action berbahaya ada di dalam statement
    action := statement.Action[_]
    dangerous_actions[_] == action
    
    # Periksa apakah Resource menggunakan Wildcard
    statement.Resource == "*"
    
    msg := sprintf("CRITICAL: Ditemukan resiko privilege escalation! Action '%v' diberikan ke Resource '*'", [action])
}
```

### Langkah 2: Buat Mock State yang Melanggar Kebijakan
Simpan file payload di `policies/mock_payload.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "iam:CreateAccessKey"
      ],
      "Resource": "*"
    }
  ]
}
```

### Langkah 3: Eksekusi Evaluasi Kebijakan menggunakan OPA CLI
Jalankan evaluasi langsung dari terminal untuk memverifikasi penolakan:

```bash
# Unduh binary OPA jika belum ada
# curl -L -o opa https://openpolicyagent.org/downloads/latest/opa_linux_amd64 && chmod +x opa

opa eval --data policies/iam_check.rego \
         --input policies/mock_payload.json \
         "data.devsecops.iam.escalation_risks"
```

*Expected Output*: Muncul pesan peringatan deteksi privilege escalation pada `iam:CreateAccessKey`.

---

## 13. Exercise

### Level Easy
Tuliskan satu aturan OPA Rego (`hands-on/m02/policies/ec2_check.rego`) yang memvalidasi bahwa setiap resource AWS Security Group (`aws_security_group`) yang membuka port inbound `22` (SSH) tidak boleh memiliki `cidr_blocks` bernilai `0.0.0.0/0`.
- Uji aturan tersebut menggunakan payload JSON sintetis dengan nilai `cidr_blocks: ["0.0.0.0/0"]` (harus gagal) dan `cidr_blocks: ["10.0.0.0/16"]` (harus lolos).

### Level Medium
Rancang konfigurasi Terraform (`hands-on/m02/iac/workload_id.tf`) yang mengonfigurasi Kubernetes ServiceAccount Token Projection pada Amazon EKS untuk memetakan ServiceAccount `backend-api` di namespace `finance` ke AWS IAM Role menggunakan fitur AWS IAM Roles for Service Accounts (IRSA). Kebijakan IAM role hanya boleh mengizinkan operasi read-only ke satu DynamoDB table: `arn:aws:dynamodb:*:*:table/Transactions`.

### Level Hard
Buat script Go atau Python yang berfungsi sebagai mock EventBridge Stream Processor. Script ini membaca stream log CloudTrail lokal, mendeteksi mutasi IAM Role di mana trust policy diubah untuk mengizinkan principal eksternal (misal: ARN AWS account lain yang bukan whitelist organisasi), dan menghasilkan output payload tindakan remediasi yang mengembalikan trust policy tersebut ke baseline state.

---

## 14. Challenge (Tantangan Studi Kasus Kompleks)

**Konteks**:
Perusahaan perbankan digital tempat Anda bekerja sedang memperluas platformnya ke arsitektur multi-cloud aktif (AWS & GCP). Beban kerja microservices terdistribusi di Amazon EKS dan Google Kubernetes Engine (GKE). Setiap pod di GKE perlu memanggil resource database Amazon DynamoDB di AWS secara langsung dengan latensi minimal tanpa transit VPN layer 7 proxy. Di sisi lain, dewan kepatuhan melarang keras adanya penyimpanan static IAM credential di manapun (termasuk Secret Manager).

**Tugas Rekayasa**:
1. Rancang arsitektur federasi identitas murni (*Native Cross-Cloud Workload Identity Federation*) yang memungkinkan Pod di GKE mengasumsikan role IAM di AWS secara aman menggunakan OIDC token yang ditandatangani oleh Google IdP.
2. Definisikan file OPA Rego yang mengaudit trust policy di AWS untuk memastikan tidak ada celah di mana sembarang Pod GKE di project GCP non-perbankan dapat mengasumsikan role tersebut (hanya project ID terotorisasi, namespace `banking`, dan ServiceAccount `settlement-worker`).
3. Buat failure recovery flow: jika Google OIDC metadata endpoint mengalami *degradation/downtime*, rancang protokol fallback identitas beban kerja agar sistem pembayaran tidak mengalami pemadaman total, dengan tetap mempertahankan audit trail Zero Trust.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic (Pilihan Ganda)

1. Mengapa penggunaan *long-lived static access keys* pada CI/CD dianggap sebagai anti-pattern kritis dalam arsitektur modern?
   - A. Menurunkan latensi network saat deployment
   - B. Memiliki risiko tinggi terekspos dalam logs, commit history, serta sulit dirotasi secara instan tanpa downtime
   - C. Membutuhkan format file XML yang tidak didukung Linux modern
   - D. Menghabiskan kuota network bandwidth cloud provider

2. Komponen utama dari SPIFFE standard yang merepresentasikan format identifier terstruktur adalah:
   - A. SVID
   - B. SPIFFE ID
   - C. SPIRE Node Attestor
   - D. Workload API

3. Dalam implementasi GitHub Actions OIDC dengan AWS IAM, field klaim manakah yang wajib divalidasi pada IAM AssumeRole Trust Policy untuk mencegah asumsi role dari sembarang repositori publik?
   - A. `aud`
   - B. `sub`
   - C. `iss`
   - D. `exp`

4. Apa fungsi utama dari solusi CIEM (*Cloud Infrastructure Entitlement Management*) dibandingkan CSPM biasa?
   - A. Mengaudit performa CPU dan RAM pada Virtual Machine
   - B. Melakukan analisis mendalam terhadap relasi izin identitas, *effective permissions*, dan memangkas hak akses berlebih (*least privilege*)
   - C. Mengatur penagihan biaya billing antar divisi
   - D. Menggantikan peran firewall physical di datacenter

5. Mekanisme pengiriman SVID dari SPIRE Agent ke aplikasi lokal dilakukan melalui:
   - A. TCP Port 80 HTTP biasa
   - B. Unix Domain Socket (Workload API)
   - C. Cloud Object Storage Bucket
   - D. Git Repository commit hook

---

### 15.2 Pertanyaan Intermediate (Pilihan Ganda & Analisis)

6. Sebuah cluster Kubernetes menggunakan Admission Controller untuk menegakkan Zero Trust. Ketika OPA Gatekeeper berada dalam kondisi crash atau webhook timeout, parameter konfigurasi `failurePolicy` apa yang harus dihindari jika sistem mengedepankan keamanan mutlak (*fail-closed*)?
   - A. `failurePolicy: Fail`
   - B. `failurePolicy: Ignore`
   - C. `failurePolicy: Reject`
   - D. `failurePolicy: Enforce`

7. Pada model evaluasi AWS IAM, jika sebuah IAM Policy tingkat Role memberikan `Allow` pada tindakan `s3:GetObject`, namun pada tingkat Service Control Policy (SCP) di level AWS Organizations didefinisikan `Deny` untuk tindakan yang sama, bagaimana hasil evaluasi akhir?
   - A. Diizinkan (`Allow`) karena permission pada Role lebih spesifik daripada Organization
   - B. Ditolak (`Deny`) karena explicit Deny pada sembarang level evaluasi akan membatalkan seluruh izin
   - C. Menggantung (*Timeout*)
   - D. Diizinkan bersyarat (*Conditional Allow*)

8. Mengapa metode polling periodik (misal: tiap 1 jam) tidak cukup memadai untuk arsitektur CSPM enterprise modern?
   - A. API cloud provider tidak mendukung format output JSON
   - B. Polling periodik membuka celah *vulnerability window* yang lebar di mana penyerang dapat mengeksploitasi celah miskonfigurasi dan menghapus jejak sebelum scanner berjalan
   - C. Polling periodik menghapus state Terraform secara otomatis
   - D. Polling periodik membutuhkan hak akses root di semua server aplikasi

9. Perhatikan potongan policy OPA Rego berikut:
   ```rego
   package security.iam
   deny {
       input.action == "iam:PassRole"
       not input.resource_tags["Environment"] == "Production"
   }
   ```
   Kapan policy di atas menghasilkan nilai `deny` (pelanggaran)?
   - A. Hanya jika action bukan `iam:PassRole`
   - B. Jika action adalah `iam:PassRole` DAN tag Environment bernilai "Production"
   - C. Jika action adalah `iam:PassRole` DAN tag Environment TIDAK bernilai "Production"
   - D. Jika action adalah `iam:PassRole` terlepas dari nilai tag apapun

10. Dalam SPIFFE/SPIRE, istilah *Node Attestation* merujuk pada:
    - A. Proses di mana aplikasi mengautentikasi user via form login web
    - B. Proses verifikasi identitas mesin host/node tempat SPIRE Agent berjalan kepada SPIRE Server sebelum SVID diterbitkan
    - C. Proses enkripsi hard disk pada server fisik
    - D. Proses pengecekan git commit signing pada repositori source code

---

### 15.3 Skenario Kasus Produksi (Analisis Praktis)

11. **Skenario 1**:
    Tim platform Anda menerapkan *Event-Driven CSPM Auto-Remediation* menggunakan AWS Lambda untuk mencabut Security Group rule port 22 jika dibuka ke `0.0.0.0/0`. Suatu hari, engineer jaringan secara manual membuka port 22 untuk *break-glass emergency*. Lambda mencabutnya dalam 5 detik. Engineer tersebut membukanya kembali, memicu loop hingga Lambda mencapai batas concurrency limit dan memblokir fungsi bisnis serverless lainnya di akun tersebut.
    *Pertanyaan*: Rancang perbaikan arsitektural komprehensif pada pipeline CSPM tersebut untuk menangani skenario *break-glass* darurat tanpa menyebabkan *concurrency starvation* atau infinite loops.

12. **Skenario 2**:
    Hasil audit CIEM menunjukkan bahwa sebuah Role aplikasi mikroservis backend pembayaran memiliki lebih dari 300 permissions yang tidak pernah dipanggil selama 180 hari terakhir, namun tetap membutuhkan hak menulis ke bucket penyimpanan audit transaksi setiap akhir bulan.
    *Pertanyaan*: Bagaimana metodologi dan pipeline teknis yang harus Anda terapkan untuk merampingkan role tersebut menuju *least-privilege* tanpa berisiko merusak proses akhir bulan yang bersifat kritikal?

13. **Skenario 3**:
    Cluster Kubernetes perusahaan berjalan di datacenter on-premise, namun ingin mengonsumsi layanan AWS KMS untuk melakukan dekripsi data sensitif tanpa menggunakan static AWS IAM credentials pada konfigurasi pod.
    *Pertanyaan*: Gambarkan rantai verifikasi kriptografis (*cryptographic verification chain*) yang harus dibangun antara on-premise cluster dengan AWS STS menggunakan standar SPIFFE/SPIRE dan OIDC Identity Provider on-premise.

---

### Kunci Jawaban Quiz

#### 15.1 Basic
1. **B** — Kredensial statis memiliki masa hidup tanpa batas jika tidak dirotasi, rentan disusupi melalui log, file teks, atau leak repositori.
2. **B** — SPIFFE ID adalah URI unik yang membedakan identitas beban kerja secara kriptografis.
3. **B** — Klaim `sub` (subject) menentukan identitas spesifik repositori dan konteks eksekusi git ref di GitHub Actions.
4. **B** — CIEM berfokus spesifik pada analisa graf hak akses, mitigasi over-privileged roles, dan *toxic combinations*.
5. **B** — Menggunakan Workload API yang ditransmisikan via Unix Domain Socket lokal untuk mengeliminasi eksposur network.

#### 15.2 Intermediate
6. **B** — `failurePolicy: Ignore` akan meloloskan seluruh resource jika webhook crash, sehingga melemahkan postur keamanan (*fail-open*).
7. **B** — Pada logika evaluasi AWS IAM, *explicit Deny* selalu mengalahkan *explicit Allow*.
8. **B** — Latensi deteksi 1 jam memberikan *attacker window* luas untuk mengeksekusi serangan otomasi pasca-miskonfigurasi.
9. **C** — Policy `deny` aktif jika action sama dengan `iam:PassRole` DAN tag `Environment` bukan "Production".
10. **B** — Node attestation memvalidasi keabsahan node komputasi tempat SPIRE Agent bertugas kepada SPIRE Server.

#### 15.3 Skenario Kasus Produksi (Panduan Solusi Evaluator)
11. **Solusi Skenario 1**:
    - **Reserved Concurrency**: Alokasikan limit terisolasi pada Lambda CSPM Remediation (misal: concurrency limit = 5) agar tidak menguras pool concurrency global akun.
    - **Tag-based Exemption (Break-Glass Protocol)**: Modifikasi logika Lambda agar mengecek tag pada Security Group. Jika terdapat tag `EmergencyAccess=Active` dengan expiration timestamp yang ditandatangani oleh approval manager, Lambda mengabaikan remediasi selama masa validitas tersebut.
    - **Rate-Limiting & Alerting**: Tambahkan counter di ElastiCache/DynamoDB; jika resource yang sama diremediasi lebih dari 3 kali dalam 5 menit, hentikan remediasi otomatis untuk resource tersebut dan eskalasikan alarm P0 ke Incident Response Team.
12. **Solusi Skenario 2**:
    - **Continuous Access Observation**: Gunakan IAM Access Advisor dan AWS CloudTrail log parsing (Athena/CloudWatch Insights) dengan observasi minimal 365 hari untuk menangkap proses berkala tahunan/bulanan.
    - **Automated Policy Synthesis**: Ekstrak kumpulan event spesifik role tersebut, lalu gunakan tools seperti `iamlive` atau AWS Access Analyzer untuk men-generate inline policy yang hanya memuat action yang benar-benar terpanggil.
    - **Canary Policy Deployment**: Pisahkan perampingan menjadi dua tahap. Terapkan AWS Permissions Boundary yang secara perlahan memangkas action non-aktif, sembari memasang alert jika ada event `AccessDenied` pada log CloudTrail sebelum policy benar-benar dihapus secara permanen di Terraform.
13. **Solusi Skenario 3**:
    - Bangun internal OIDC Identity Provider (misal: Keycloak, Dex, atau SPIRE OIDC Discovery Provider) di datacenter on-premise yang terekspos secara aman ke internet/public via custom domain terverifikasi.
    - Daftarkan public thumbprint SSL cert IdP on-premise tersebut sebagai Identity Provider di AWS IAM.
    - Pod on-premise meminta short-lived JWT-SVID dari SPIRE Agent lokal.
    - Pod on-premise memanggil `sts:AssumeRoleWithWebIdentity` ke AWS STS menggunakan JWT-SVID tersebut. AWS STS memverifikasi signature token ke OIDC IdP on-premise, lalu menerbitkan temporary AWS credentials yang memungkinkan Pod memanggil AWS KMS API secara langsung tanpa static keys.

---

## 16. Summary
- Pendekatan keamanan perimeter berbasis jaringan (Network-Centric) sudah usang dan terbukti gagal membendung pergerakan lateral penyerang modern. **Zero Trust Identity** menempatkan identitas kriptografis berumur pendek (*ephemeral*) sebagai batas perimeter baru (*Identity is the new Perimeter*).
- **CSPM dan CIEM** modern berevolusi dari scanner statis periodik menjadi sistem berbasis **Event-Driven Graph Analytics**. Pelanggaran konfigurasi (drift) dan *toxic entitlement combinations* harus dideteksi dalam hitungan detik dan diremediasi secara deterministik via Policy-as-Code (OPA Rego) dan worker otomatis.
- Implementasi standar terbuka seperti **OIDC Workload Identity Federation** dan **SPIFFE/SPIRE** memberikan landasan arsitektur bebas kredensial statis (*zero-secret footprint*) di seluruh pipeline CI/CD dan runtime microservices, secara masif menurunkan *blast radius* dan biaya operasional kepatuhan regulasi enterprise.