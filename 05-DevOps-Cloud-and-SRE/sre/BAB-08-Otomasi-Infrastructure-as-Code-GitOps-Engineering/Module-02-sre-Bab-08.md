# BAB 08: Otomasi Infrastructure-as-Code & GitOps Engineering
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Mengimplementasikan Arsitektur IaC Skala Enterprise**: Mampu merancang sistem modularisasi Terraform/OpenTofu tingkat lanjut menggunakan *dynamic remote backends*, *isolated state files*, *distributed locking*, serta *cross-account IAM assume-role execution pattern*.
2. **Menguasai Mekanisme Internal GitOps Controller**: Membedah dan mengonfigurasi algoritma rekonsiliasi (*Level-Triggered 3-Way Merge Patch*) pada ArgoCD/Flux untuk mencegah *configuration drift* dan *out-of-sync loops*.
3. **Membangun Pipeline Policy-as-Code (PaC) Berbasis Zero-Trust**: Mengintegrasikan Open Policy Agent (OPA), Conftest, dan Kyverno ke dalam alur PR (*Pull Request*) dan *admission control* untuk menegakkan *guardrail* keamanan dan kepatuhan secara deterministik.
4. **Menangani State Desynchronization dan Disaster Recovery**: Mendiagnosis serta mereparasi *corrupted state*, *dependency cycle deadlocks*, dan *drift remediation* pada sistem multi-region tanpa downtime.
5. **Mengorkestrasi Automasi Produksi End-to-End**: Mengimplementasikan *ephemeral environments*, integrasi External Secrets Operator (ESO) dengan HashiCorp Vault, serta automated pull-request validation berbasis Atlantis/GitHub Actions Self-Hosted Runners.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
*   **Kubernetes Internals**: Kontroler, API Server, *Custom Resource Definitions* (CRD), dan siklus hidup Pod.
*   **Distributed Systems Fundamentals**: *Consensus mechanisms* (Raft/Paxos), *eventual consistency*, dan teorema CAP.
*   **Dasar IaC & Git**: Sintaks HCL dasar Terraform, manipulasi Git tingkat lanjut (*rebase, cherry-pick, signed commits*), serta *cloud networking* dasar (VPC, Peering, Transit Gateway, Subnetting).
*   **SRE Core Principles**: Error Budget, Service Level Objectives (SLO), MTTR/MTTD, serta prinsip *Blameless Post-Mortem*.

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi IaC dan GitOps pada skala enterprise membutuhkan pemahaman mendalam tentang bagaimana *state*, *graph resolution*, dan *reconciliation loop* beroperasi di tingkat kernel dan protokol.

#### 3.1 Directed Acyclic Graph (DAG) Engine pada Terraform/OpenTofu
Terraform mengonversi seluruh deklarasi blok HCL menjadi representasi graf struktural berarah tanpa siklus (*Directed Acyclic Graph* atau DAG).
1. **Tokenisasi & Parsing**: Kode HCL diurai menjadi *Abstract Syntax Tree* (AST) oleh parser HCL2.
2. **Node Creation & Interpolation**: Setiap *resource*, *provider*, dan *variable* dimetakan menjadi simpul (*node*). Edge antar-simpul ditentukan oleh referensi implisit (misalnya `aws_subnet.main.id` di dalam `aws_instance`) atau eksplisit (`depends_on`).
3. **Topological Sorting**: Algoritma Kahn atau DFS digunakan untuk mengurutkan dependensi eksekusi. Operasi yang berada pada sub-graf independen dieksekusi secara konkuren sesuai batas `--parallelism` (default: 10 worker pools).
4. **State Refresh & Delta Generation**: State lokal/remote dibaca, dikorelasikan dengan ID sumber daya di cloud API, menghasilkan *execution plan* yang merepresentasikan operasi aljabar himpunan:
   
$$\Delta = \text{Desired State} \setminus \text{Current Real State}$$

```
                +----------------------------+
                |    HCL Resource Blocks     |
                +----------------------------+
                              |
                              v
                +----------------------------+
                |  HCL2 Parser (AST Build)   |
                +----------------------------+
                              |
                              v
                +----------------------------+
                | Dynamic DAG Initialization |
                +----------------------------+
                   /          |           \
                  v           v            v
            [Node: VPC] [Node: IAM] [Node: KMS]
                  \           |            /
                   v          v           v
                +----------------------------+
                | Dependency Resolution &    |
                | Topological Walk (Parallel)|
                +----------------------------+
                              |
                              v
                +----------------------------+
                | Cloud API CRUD Execution   |
                +----------------------------+
```

#### 3.2 Dynamic Remote State & Distributed Lock Primitives
*State* pada IaC merupakan *single point of truth* pemetaan logika HCL ke ID infrastruktur riil.
*   **State Race Condition Protection**: Distributed locking mencegah dua proses eksekusi modifikasi state secara bersamaan. Contoh: DynamoDB menggunakan atribut `LockID` yang divalidasi dengan operasi `PutItem` berkondisi `attribute_not_exists(LockID)`.
*   **Kriptografi & Zero-Trust State Storage**: State file menyimpan *plain text secrets* jika modul mengekspos atribut sensitif. Arsitektur produksi wajib menerapkan KMS envelope encryption (AES-GCM-256) pada S3/GCS bucket dengan *strict IAM bucket policies* dan memblokir seluruh akses publik via VPC Endpoint.

#### 3.3 GitOps Control Loop: 3-Way Merge Patch Algorithm
GitOps beroperasi pada model *Level-Triggered Control Loop* yang diadopsi dari arsitektur internal Kubernetes. Controller (ArgoCD/Flux) tidak sekadar membandingkan Git dengan Cluster, melainkan melakukan kalkulasi *3-way merge patch*:

```
    +-------------------+       +--------------------+
    | Desired (Git)     |       | Live (Cluster API) |
    +-------------------+       +--------------------+
             \                         /
              \                       /
               v                     v
            +---------------------------+
            | 3-Way Merge Engine        |
            |                           |
            | Base: Last-Applied-Config |
            +---------------------------+
                         |
                         v
            +---------------------------+
            | Calculated Mutation Delta |
            +---------------------------+
                         |
                         v
            +---------------------------+
            | API Server Patch Exec     |
            +---------------------------+
```

*   **Tiga State yang Dilibatkan**:
    1.  **Desired State**: Manifest yang didefinisikan pada commit Git terbaru.
    2.  **Live State**: Konfigurasi aktual yang sedang berjalan di etcd kluster.
    3.  **Last-Applied-Configuration**: Anotasi metadata (`kubectl.kubernetes.io/last-applied-configuration`) yang merekam state manifest saat sinkronisasi terakhir berhasil.
*   **Algoritma Resolusi Drift**:
    *   Jika sebuah field diubah di *Live State* tetapi tidak ada di *Desired* maupun *Last-Applied*, controller menganggapnya sebagai injeksi eksternal (misal: mutating webhook inject sidecar) dan tidak meng-overwrite field tersebut (mencegah *infinite reconciliation loops*).
    *   Jika sebuah field dihapus dari *Desired State* tetapi ada di *Last-Applied-Configuration*, field tersebut akan dihapus secara paksa dari *Live State*.

---

### 4. Why & What

| Dimensi | Pendekatan Tradisional (ClickOps / Ad-Hoc Scripts) | Enterprise IaC + GitOps Engineering |
| :--- | :--- | :--- |
| **Auditabilitas** | Log audit terfragmentasi di CloudTrail/AuditLogs tanpa konteks intensi bisnis. | Git commit hash bertanda tangan GPG; setiap perubahan tercatat dengan *author*, *approver*, dan *ticket issue context*. |
| **Configuration Drift** | Tak terhindarkan. Patch darurat di server live menyebabkan degradasi baseline sistem. | Deteksi drift otomatis (interval polling/webhook); pemulihan instan (*self-healing/auto-remediation*). |
| **Blast Radius Isolation** | Shared monolith scripts; kegagalan syntax dapat merusak seluruh core routing jaringan. | Multi-tier state isolation via Workspace/Directories terisolasi berdasarkan lifecycle dependensi (Core -> Platform -> App). |
| **Security Gates** | Validasi manual pasca-deployment saat inspeksi berkala. | Policy-as-Code preventif di PR (*shift-left*) dan *admission-time validation* di kluster (Zero-Trust). |
| **MTTR (Recovery)** | Hitungan jam/hari (reka ulang manual konfigurasi dari backup parsial). | Hitungan menit: `git revert <commit-id>` memicu rollback deterministik di seluruh target cluster. |

---

### 5. How (Workflow Detail)

Alur kerja promosi perubahan infrastruktur skala enterprise menggunakan pola **Branch-Driven Infrastructure Promotion with Automated Guardrails**:

```
[Developer]
    |
    v
1. Buat Feature Branch -> Modifikasi HCL/Manifest
    |
    v
2. Push ke Remote Repository -> Trigger CI Pipeline
    |
    +---> Run Pre-commit Hook (tflint, tfsec, checkov)
    +---> Run Conftest (OPA static validation against organizational baseline)
    |
    v
3. Buka Pull Request (PR) ke branch `main`
    |
    v
4. Atlantis / Orchestrator Worker Hook:
    +---> Inisialisasi isolated workspace
    +---> `tofu init` & `tofu plan`
    +---> Post formatted plan output sebagai komentar PR
    |
    v
5. Review & Policy Gate:
    +---> Peer Review minimal 2 Principal SRE
    +---> Otomatisasi evaluasi biaya via Infracost
    |
    v
6. PR Approval & Merge Command (`atlantis apply` atau merge commit)
    |
    v
7. Cloud Infrastructure Provisioned:
    +---> Assume deployment role via AWS STS / GCP Workload Identity
    +---> State ter-update dan ter-lock di Remote Storage
    |
    v
8. GitOps Repo Sync (ArgoCD):
    +---> Webhook mentrigger ArgoCD Application Controller
    +---> Repo-server merender Kustomize/Helm templates
    +---> 3-Way diff calculated vs Live Cluster
    +---> Sync applied (Prune, Validate, Auto-Heal active)
    |
    v
9. Observability Verification:
    +---> Prometheus memonitor error rates & drift metrics
    +---> Notifikasi status ke SRE incident channels
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem
Bayangkan **Terraform** sebagai tim arsitek dan kontraktor sipil yang membangun gedung bertingkat dari cetak biru fisik. Mereka menuangkan beton, memasang pipa saluran air, dan membangun struktur baja (komponen statis, mahal, dan jarang dibongkar).
Sedangkan **GitOps (ArgoCD)** adalah sistem manajemen otomatis gedung cerdas (*Building Management System*). Ia terus-menerus memantau ruangan: jika termostat berubah dari 22°C (karena ada orang iseng memutar kenop manual di dinding), kontroler sistem secara otomatis menolak perubahan tersebut dan menyetelnya kembali ke 22°C sesuai cetak biru operasional di pusat kontrol.

#### Diagram Arsitektur Enterprise Multi-Account GitOps

```
                     DEVELOPER ZONE
                           |
             (Git Push / Signed Commits)
                           |
                           v
           +-------------------------------+
           |    Enterprise Git Host        |
           |  - infra-core-repo (IaC)      |
           |  - gitops-manifest-repo (K8s) |
           +---------------+---------------+
                           |
                 (Webhook Notifications)
                           |
                           v
        +-------------------------------------+
        |     CI / Automation Control Plane   |
        |  +-------------------------------+  |
        |  | Atlantis / GitHub Action Runr |  |
        |  | - Pre-flight OPA / Conftest   |  |
        |  | - Ephemeral Plan & Locks      |  |
        |  +---------------+---------------+  |
        +------------------|------------------+
                           |
               (STS AssumeRole via OIDC)
                           |
       +-------------------+-------------------+
       |                                       |
       v                                       v
+-----------------------------+ +-----------------------------+
| AWS Account: Network & Core | | AWS Account: EKS Cluster    |
| - Transit Gateways          | | - IAM Roles for Service Acct|
| - VPCs & Direct Connects    | | - Auto-Scaling Node Groups  |
| - S3 State Store + DynamoDB | | - KMS Master Encryption Keys|
+-----------------------------+ +--------------+--------------+
                                               |
                                               v
                                +-----------------------------+
                                | ArgoCD Control Plane Pods   |
                                | - Application Controller    |
                                | - Repo Server Engine        |
                                +--------------+--------------+
                                               |
                                     (3-Way Reconciliation)
                                               |
                      +------------------------+------------------------+
                      |                                                 |
                      v                                                 v
        +---------------------------+                     +---------------------------+
        |  K8s Namespace: Staging   |                     |  K8s Namespace: Prod      |
        | - External Secrets (Vault)|                     | - External Secrets (Vault)|
        | - Microservices Workloads |                     | - Strict Kyverno Policies |
        +---------------------------+                     +---------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Policy-as-Code Enforcer Menggunakan Open Policy Agent (Rego)
File ini memblokir pembuatan bucket AWS S3 yang tidak mengaktifkan enkripsi default atau mengizinkan akses publik.

```rego
# policy/s3_guardrails.rego
package terraform.security

default allow = false

# Ambil seluruh resource aws_s3_bucket dari tfplan JSON
deny[msg] {
    resource := input.resource_changes[_]
    resource.type == "aws_s3_bucket"
    
    # Validasi apakah enkripsi SSE terdefinisi
    not resource.change.after.server_side_encryption_configuration
    
    msg := sprintf("Pelanggaran Keamanan: Resource S3 '%v' wajib mendefinisikan server_side_encryption_configuration.", [resource.address])
}

deny[msg] {
    resource := input.resource_changes[_]
    resource.type == "aws_s3_bucket_public_access_block"
    
    # Pastikan block_public_acls bernilai true
    resource.change.after.block_public_acls != true
    
    msg := sprintf("Pelanggaran Kepatuhan: S3 bucket access block '%v' harus mengaktifkan block_public_acls.", [resource.address])
}

allow {
    count(deny) == 0
}
```

#### 7.2 Practical Example: Enterprise Modular Terraform Engine dengan Assume-Role & Dynamic State

Struktur file implementasi produksi tingkat lanjut:

##### File: `versions.tf`
```hcl
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.35.0"
    }
  }

  backend "s3" {
    bucket         = "corp-sre-production-tfstate"
    key            = "platform/networking/production.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "corp-sre-production-tflocks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  # Assume-role pattern: CI/CD runner tidak memegang IAM credential permanen
  assume_role {
    role_arn     = "arn:aws:iam::${var.target_account_id}:role/EnterpriseIaCExecutionRole"
    session_name = "IaCPlatformAutomationSession"
    external_id  = var.deployment_external_id
  }

  default_tags {
    tags = {
      Owner       = "Core-SRE-Team"
      ManagedBy   = "Terraform"
      Environment = var.environment
      SLODriven   = "Tier-1"
    }
  }
}
```

##### File: `variables.tf`
```hcl
variable "aws_region" {
  type        = string
  default     = "ap-southeast-1"
  description = "Region AWS target deployment"
}

variable "target_account_id" {
  type        = string
  description = "AWS Target Account ID untuk deployment (Cross-Account Setup)"
  
  validation {
    condition     = can(regex("^[0-9]{12}$", var.target_account_id))
    error_message = "target_account_id harus berupa 12 digit numerik."
  }
}

variable "deployment_external_id" {
  type        = string
  sensitive   = true
  description = "Shared External ID untuk mitigasi Confused Deputy Problem"
}

variable "environment" {
  type        = string
  default     = "production"
  validation {
    condition     = contains(["staging", "production", "dr"], var.environment)
    error_message = "Environment harus staging, production, atau dr."
  }
}

variable "vpc_cidr" {
  type        = string
  default     = "10.100.0.0/16"
}
```

##### File: `main.tf`
```hcl
# Subnet kalkulasi otomatis menggunakan cidrsubnet() function
locals {
  az_count        = 3
  azs             = ["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"]
  transit_gateway = "tgw-0987654321fedcba0"
}

resource "aws_vpc" "core_vpc" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "vpc-${var.environment}-core"
  }
}

resource "aws_subnet" "private" {
  count             = local.az_count
  vpc_id            = aws_vpc.core_vpc.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index)
  availability_zone = local.azs[count.index]

  tags = {
    Name                              = "snet-${var.environment}-private-${local.azs[count.index]}"
    "kubernetes.io/role/internal-elb" = "1"
  }
}

resource "aws_route_table" "private" {
  count  = local.az_count
  vpc_id = aws_vpc.core_vpc.id

  route {
    cidr_block         = "10.0.0.0/8"
    transit_gateway_id = local.transit_gateway
  }

  tags = {
    Name = "rtb-${var.environment}-private-az${count.index + 1}"
  }
}

resource "aws_route_table_association" "private" {
  count          = local.az_count
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}
```

#### 7.3 Practical Example: ArgoCD ApplicationSet dengan Zero-Trust External Secrets

File ini mendefinisikan automasi deployment multi-kluster berbasis GitOps menggunakan pola ApplicationSet dan sinkronisasi rahasia via HashiCorp Vault.

##### File: `argo-appset-payments.yaml`
```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: payment-processing-workloads
  namespace: argocd
spec:
  generators:
    - clusters:
        selector:
          matchLabels:
            tier: payment-critical
            environment: production
  template:
    metadata:
      name: '{{name}}-payment-gateway'
    spec:
      project: default
      source:
        repoURL: 'git@github.com:enterprise-corp/fintech-manifests.git'
        targetRevision: HEAD
        path: apps/payment-gateway/overlays/{{metadata.labels.region}}
      destination:
        server: '{{server}}'
        namespace: payment-system
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
        syncOptions:
          - CreateNamespace=true
          - ApplyOutOfSyncOnly=true
          - PrunePropagationPolicy=foreground
          - RespectIgnoreDifferences=true
        retry:
          limit: 5
          backoff:
            duration: 10s
            factor: 2
            maxDuration: 3m
      ignoreDifferences:
        - group: apps
          kind: Deployment
          jsonPointers:
            - /spec/replicas # Membiarkan HPA mengendalikan replica count dinamis
```

##### File: `externalsecret-integration.yaml`
```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: vault-backend
  namespace: payment-system
spec:
  provider:
    vault:
      server: "https://vault.internal.corp:8200"
      path: "secret"
      version: "v2"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "payment-gateway-production"
---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: payment-core-secrets
  namespace: payment-system
spec:
  refreshInterval: "1h"
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: app-runtime-secret
    creationPolicy: Owner
  data:
    - secretKey: DB_PASSWORD
      remoteRef:
        key: production/database/credentials
        property: password
    - secretKey: STRIPE_PRIVATE_KEY
      remoteRef:
        key: production/thirdparty/stripe
        property: api_key
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Insiden: "The 3-Way Merge Storm & State Lockout"
*   **Perusahaan**: Bank Digital Tier-1 (10 Juta Active Daily Users)
*   **Konteks**: Infrastruktur pemrosesan transaksi microservices berjalan di 3 Region AWS (Active-Active-Active) dengan 4 kluster EKS per region, diorkestrasi via ArgoCD dan Terraform.

#### Kronologi Kegagalan (Failure Cascade):
1. **Pemicu**: Tim Core Infra melakukan update definisi label Kubernetes secara global menggunakan Terraform module, menambahkan label `compliance.audit/checksum: <hash>` ke semua Deployment.
2. **Desinkronisasi State Lock**: Saat apply paralel berjalan di 3 region via GitHub Actions, pipeline region `ap-southeast-1` mengalami *network blip* dengan AWS DynamoDB. Lock state tidak terbebas (*stale lock*), menghentikan pipeline berikutnya.
3. **Collision dengan HPA & GitOps Controller**: Di sisi lain, tim payments mendeploy update manifest microservice via GitOps ArgoCD. ArgoCD mendeteksi perbedaan (*drift*) karena label baru dari Terraform tidak ada di repository Git aplikasi.
4. **Reconciliation Loop Storm**:
   *   ArgoCD dengan parameter `selfHeal: true` secara terus-menerus menghapus label `compliance.audit/checksum`.
   *   Engine Terraform pipeline lain yang baru saja recover dari stale lock mendeteksi *drift* dan menambahkan kembali label tersebut secara berkala.
   *   Kubernetes API Server di 12 kluster mengalami lonjakan load CPU hingga 98% karena *admission mutation webhooks* terpicu lebih dari 400 kali per detik.
5. **Dampak Bisnis**: Kluster API server mulai *throttling* request. HPA (*Horizontal Pod Autoscaler*) gagal melakukan scale-out saat beban transaksi pembayaran jam sibuk melonjak. Terjadi *dropped transactions* sebesar 14.5% selama 42 menit, melanggar batas error budget bulanan.

#### Root Cause Analysis (RCA):
*   Pelanggaran prinsip *Separation of Concerns*: Terraform dan ArgoCD sama-sama mengelola manifest object Kubernetes Deployment yang sama.
*   Terraform tidak dikonfigurasi untuk mengabaikan field yang dikelola oleh controller GitOps atau sebaliknya (`ignoreDifferences` tidak disetel di ArgoCD).
*   DynamoDB distributed lock tidak memiliki mekanisme TTL (*Time to Live*) otomatis untuk membersihkan lock yang tertinggal akibat pipeline runner mati (*hung state*).

#### Solusi Arsitektural & Mitigasi Permanen:
1. **Pemisahan Domain Mutlak**:
   *   Terraform HANYA mengelola infrastruktur *substrate* (VPC, EKS Cluster Control Plane, Node Groups, IAM Roles, S3).
   *   Kubernetes manifest, workloads, configmaps, dan secrets HANYA diorkestrasi oleh GitOps Controller (ArgoCD). Terraform TIDAK BOLEH memanggil `kubernetes_*` resources untuk aplikasi layer-7.
2. **Koreksi ArgoCD Configuration**:
   Menetapkan `ignoreDifferences` secara global pada k8s metadata yang dimutasi oleh sistem eksternal:
   ```yaml
   apiVersion: v1
   kind: ConfigMap
   metadata:
     name: argocd-cm
     namespace: argocd
   data:
     resource.customizations.ignoreDifferences.all: |
       jsonPointers:
         - /metadata/resourceVersion
         - /metadata/generation
         - /metadata/managedFields
   ```
3. **Automated State Lock Breaker & Telemetry**:
   Membuat Lambda function monitoring DynamoDB Locks yang mengirimkan alert jika lock ditahan lebih dari 30 menit tanpa ada active PID runner, serta mewajibkan implementasi `--lock-timeout=15m` pada script inisialisasi wrapper IaC.

---

### 9. Trade-offs

Setiap keputusan arsitektur automasi memiliki konsekuensi teknis yang harus diukur berdasarkan SLO:

| Pendekatan / Teknologi | Keuntungan (Pros) | Biaya & Risiko (Cons / Trade-offs) | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **Pull-Based GitOps (e.g., ArgoCD Agent)** | • Zero incoming firewall ports ke kluster.<br>• Rekonsiliasi aktif dan self-healing langsung dari dalam kluster. | • Konsumsi resource CPU/Memory meningkat di dalam kluster.<br>• Potensi *noisy neighbor* jika kluster kelebihan ratusan `Application` resources. | Arsitektur multi-cluster enterprise dengan standar isolasi Zero-Trust Network. |
| **Push-Based IaC (e.g., Pipeline CI/CD Langsung)** | • Kontrol pipeline tersentralisasi.<br>• Mudah diintegrasikan dengan end-to-end testing bertahap. | • Runner memerlukan akses network langsung dan IAM credential berprivilese tinggi ke kluster API.<br>• Tidak ada deteksi drift otomatis jika ada perubahan lokal. | Provisioning fondasi infrastruktur (Cloud Hardware, Networking, IAM, RDS Database). |
| **Monorepo Manifests** | • *Single source of truth* memudahkan visibilitas cross-dependency.<br>• Commit atomik mencakup perubahan pada beberapa service sekaligus. | • Skalabilitas Git menurun pada tim ribuan orang (*merge conflict hell*).<br>• Git polling webhook memicu load server berat pada Git server. | Tim skala kecil hingga menengah (< 50 engineer) atau platform engineering tersentralisasi. |
| **Polyrepo per Service** | • Blast radius isolasi akses git ketat.<br>• CI/CD pipeline independen dan cepat. | • Sulit melacak dependensi antar-layanan.<br>• Mengubah shared library konfigurasi memerlukan manipulasi massal ratusan PR repo. | Organisasi besar dengan tim otonom microservices (*domain-driven design*). |
| **Auto-Sync + Auto-Heal di Production** | • Eliminasi total *configuration drift* secara real-time.<br>• Drift manual langsung di-overwrite deterministik. | • Jika manifest di Git salah, kegagalan langsung menyebar ke produksi secara instan (*fast-blast failure*). | Service stateless non-kritikal; atau pipeline dengan validasi automated canary yang sangat matang. |

---

### 10. Common Mistakes & Troubleshooting

#### Skenario Kasus 1: "State Lock Deadlock (Terraform/OpenTofu)"
*   **Gejala**: Error `Error acquiring the state lock: ConditionalCheckFailedException: The conditional request failed`.
*   **Akar Masalah**: CI runner crash mendadak (misalnya: OOMKilled atau spot-instance termination) di tengah-tengah operasi apply sebelum ia sempat melepaskan hash lock di DynamoDB.
*   **Cara Diagnosa**:
    Periksa Lock ID dari pesan error:
    ```bash
    # Dapatkan info lock
    aws dynamodb get-item \
      --table-name corp-sre-production-tflocks \
      --key '{"LockID": {"S": "corp-sre-production-tfstate/platform/networking/production.tfstate-md5"}}'
    ```
*   **Solusi**:
    1. Pastikan tidak ada pipeline proses aktif yang sedang berjalan menggunakan log CI/CD.
    2. Eksekusi unlock secara hati-hati menggunakan ID yang tertera:
       ```bash
       tofu force-unlock <LOCK-ID>
       ```

#### Skenario Kasus 2: "Infinite Reconciliation Loop di GitOps (ArgoCD)"
*   **Gejala**: ArgoCD menampilkan status `OutOfSync` dan `Synced` bergantian setiap beberapa detik, CPU repo-server melonjak tinggi.
*   **Akar Masalah**: Konflik antara *defaulting webhook* di kluster dengan manifest di Git. Contoh: Manifest mendefinisikan field kosong atau string integer, tetapi Admission Controller Kubernetes secara otomatis mengubah formatnya (misalnya menambahkan field `protocol: TCP` pada service ports).
*   **Cara Diagnosa**:
    Jalankan *diff* manual via terminal ArgoCD CLI:
    ```bash
    argocd app diff <app-name> --hard-refresh
    ```
    Amati field mana yang terus-menerus berbeda antara *Live* dan *Target*.
*   **Solusi**:
    Gunakan konfigurasi `respectIgnoreDifferences` atau sesuaikan manifest Git agar sama persis dengan mutasi yang dihasilkan oleh API admission webhook Kubernetes.

#### Skenario Kasus 3: "Dependency Cycle Deadlock pada Terraform DAG"
*   **Gejala**: Error: `Error: Cycle: aws_security_group.db, aws_security_group.app`.
*   **Akar Masalah**: Security group App mereferensikan SG DB pada *ingress rule*, dan Security Group DB mereferensikan SG App pada *egress rule* di dalam blok resource yang sama.
*   **Solusi**:
    Pisahkan aturan ingress/egress dari blok resource `aws_security_group` menjadi resource independen: `aws_security_group_rule`. Ini memecah circular dependency pada graf topological sort:
    ```hcl
    # Hindari inline rules:
    resource "aws_security_group" "app" { name = "app-sg" }
    resource "aws_security_group" "db"  { name = "db-sg" }

    # Solusi: Gunakan resource independen
    resource "aws_security_group_rule" "app_to_db" {
      type                     = "egress"
      from_port                = 5432
      to_port                  = 5432
      protocol                 = "tcp"
      security_group_id        = aws_security_group.app.id
      source_security_group_id = aws_security_group.db.id
    }
    ```

---

### 11. Best Practices (Production Checklist)

Gunakan tabel checklist evaluasi kesiapan produksi ini sebelum meluncurkan sistem automasi baru:

| Kategori | Item Pemeriksaan (Verification Item) | Criticality | Status Validasi |
| :--- | :--- | :--- | :--- |
| **State Security** | State file S3/GCS dienkripsi menggunakan KMS Customer-Managed Key (CMK) dan public access diblokir penuh. | P0 - Blocker | [ ] |
| **State Security** | Versioning diaktifkan pada state bucket untuk proteksi pemulihan terhadap *accidental state corruption*. | P0 - Blocker | [ ] |
| **Identity & IAM** | CI/CD runner menggunakan OIDC/STS AssumeRole; tidak ada long-lived credentials (IAM User API Key) disimpan di Git. | P0 - Blocker | [ ] |
| **GitOps Safety** | Flag `prune: true` dan `selfHeal: true` aktif secara deterministik di production dengan `ignoreDifferences` tervalidasi. | P1 - High | [ ] |
| **Secrets Engine** | Tidak ada credential/password/token dalam bentuk raw string di Git; wajib menggunakan SealedSecrets atau ExternalSecrets (Vault). | P0 - Blocker | [ ] |
| **Guardrails** | Conftest/OPA diintegrasikan pada alur CI PR; memblokir modifikasi CIDR subnet atau penghapusan storage tanpa izin. | P1 - High | [ ] |
| **Operations** | Menggunakan Terraform wrapper atau workspace terisolasi per environment; membatasi `--parallelism` untuk mencegah API Throttling. | P2 - Medium | [ ] |
| **Disaster Recovery**| Snapshot backup terjadwal untuk S3 state bucket dan etcd data store GitOps minimal per 6 jam. | P1 - High | [ ] |

---

### 12. Hands-on Practice

Dalam praktikum ini, Anda akan membangun pipeline automasi terisolasi: membuat modul IaC dengan guardrail OPA, mengonfigurasi local cluster berbasis Kind, dan mendeploy ArgoCD untuk mengelola rekonsiliasi.

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

```
hands-on/m02/
├── policy/
│   └── enforce_tags.rego
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── gitops/
│   └── app-deployment.yaml
└── run-validation.sh
```

#### Langkah 1: Siapkan Policy Guardrail (OPA Rego)
Buat file `hands-on/m02/policy/enforce_tags.rego`:
```rego
package terraform.validation

default allow = false

# Resource yang wajib memiliki tag Environment dan CostCenter
mandatory_tags = ["Environment", "CostCenter"]

deny[msg] {
    resource := input.resource_changes[_]
    resource.type == "aws_subnet"
    
    tags := resource.change.after.tags
    missing := [tag | tag := mandatory_tags[_]; not tags[tag]]
    count(missing) > 0
    
    msg := sprintf("Resource '%v' kehilangan mandatory tags: %v", [resource.address, missing])
}

allow {
    count(deny) == 0
}
```

#### Langkah 2: Buat Skrip Terraform
Buat file `hands-on/m02/terraform/variables.tf`:
```hcl
variable "region" {
  type    = string
  default = "ap-southeast-1"
}

variable "environment" {
  type    = string
  default = "production"
}
```

Buat file `hands-on/m02/terraform/main.tf`:
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
  region                      = var.region
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  access_key                  = "mock_access_key"
  secret_key                  = "mock_secret_key"
}

resource "aws_vpc" "app_vpc" {
  cidr_block = "10.20.0.0/16"

  tags = {
    Name        = "vpc-m02-practice"
    Environment = var.environment
    CostCenter  = "CC-1029"
  }
}

resource "aws_subnet" "invalid_subnet" {
  vpc_id            = aws_vpc.app_vpc.id
  cidr_block        = "10.20.1.0/24"
  availability_zone = "ap-southeast-1a"

  # Sengaja tidak menyertakan tags untuk menguji Policy-as-Code gate
  tags = {
    Name = "snet-unprotected"
  }
}
```

Buat file `hands-on/m02/terraform/outputs.tf`:
```hcl
output "vpc_id" {
  value = aws_vpc.app_vpc.id
}
```

#### Langkah 3: Manifest GitOps
Buat file `hands-on/m02/gitops/app-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sre-telemetry-collector
  namespace: default
  labels:
    app.kubernetes.io/name: telemetry-collector
spec:
  replicas: 2
  selector:
    matchLabels:
      app: telemetry-collector
  template:
    metadata:
      labels:
        app: telemetry-collector
    spec:
      containers:
        - name: collector
          image: nginx:1.25.3-alpine
          ports:
            - containerPort: 80
          resources:
            limits:
              cpu: "250m"
              memory: "256Mi"
            requests:
              cpu: "100m"
              memory: "128Mi"
```

#### Langkah 4: Skrip Eksekusi dan Pengujian
Buat file `hands-on/m02/run-validation.sh`:
```bash
#!/usr/bin/env bash
set -eo pipefail

echo "=== MEMULAI PRAKTIKUM HANDS-ON MODUL 02 ==="
cd "$(dirname "$0")"

# 1. Inisialisasi dan Generate Plan JSON
echo "[1/4] Menjalankan Terraform Init & Plan..."
cd terraform
tofu init -reconfigure || terraform init -reconfigure
tofu plan -out=tfplan.binary || terraform plan -out=tfplan.binary
tofu show -json tfplan.binary > tfplan.json || terraform show -json tfplan.binary > tfplan.json

# 2. Validasi Policy Menggunakan OPA/Conftest
echo "[2/4] Mengevaluasi Terraform Plan terhadap OPA Policy..."
cd ..
if command -v opa &> /dev/null; then
    opa eval --input terraform/tfplan.json --data policy/enforce_tags.rego "data.terraform.validation.deny" --format pretty || true
else
    echo "Peringatan: OPA binary tidak ditemukan di PATH. Lewati eksekusi lokal OPA."
fi

# 3. Setup Kluster Mini & ArgoCD
echo "[3/4] Setup Kluster Kubernetes Lokal (Kind)..."
if command -v kind &> /dev/null && command -v kubectl &> /dev/null; then
    kind get clusters | grep "sre-m02-cluster" || kind create cluster --name sre-m02-cluster
    
    echo "Menerapkan manifest GitOps..."
    kubectl apply -f gitops/app-deployment.yaml
    kubectl rollout status deployment/sre-telemetry-collector --timeout=60s

    # 4. Mensimulasikan Configuration Drift & Self-Healing
    echo "[4/4] Simulasi Drift: Memodifikasi replica secara manual di luar konfigurasi deklaratif..."
    kubectl scale deployment sre-telemetry-collector --replicas=5
    echo "Jumlah replica saat ini setelah dirusak manual:"
    kubectl get deployment sre-telemetry-collector -o jsonpath='{.spec.replicas}' && echo ""

    echo "Mensimulasikan rekonsiliasi manual (seperti loop controller GitOps)..."
    kubectl apply -f gitops/app-deployment.yaml
    echo "Jumlah replica setelah rekonsiliasi GitOps:"
    kubectl get deployment sre-telemetry-collector -o jsonpath='{.spec.replicas}' && echo ""
else
    echo "Kind atau Kubectl tidak terpasang. Lewati pengujian kluster lokal."
fi

echo "=== PRAKTIKUM SELESAI DENGAN SUKSES ==="
```

Jalankan skrip praktikum:
```bash
chmod +x hands-on/m02/run-validation.sh
./hands-on/m02/run-validation.sh
```

---

### 13. Exercise

Kerjakan instruksi di bawah ini secara mandiri:

1. **Level: Easy**
   *   Tulis sebuah modul Terraform lokal yang mendefinisikan Security Group untuk Postgres Database (Port 5432).
   *   Kriteria Keberhasilan: Modul menerima variabel `ingress_cidr_blocks` (list of string). Jika ada elemen CIDR `0.0.0.0/0`, Terraform execution wajib *fail* pada saat validasi variabel menggunakan blok `validation {}`.

2. **Level: Medium**
   *   Buat file OPA Rego baru (`policy/prevent_route_broadcasting.rego`) yang mengevaluasi Terraform Plan JSON.
   *   Kriteria Keberhasilan: Memblokir resource `aws_route` jika field `destination_cidr_block` bernilai `0.0.0.0/0` dan diarahkan langsung ke `gateway_id` yang bukan transit gateway (`tgw-*`).

3. **Level: Hard**
   *   Rancang spesifikasi YAML untuk ArgoCD Application yang mengaktifkan sinkronisasi bertahap (*Sync Waves*) dan *Resource Hooks*.
   *   Kriteria Keberhasilan:
       1. Database migration dijalankan sebagai Kubernetes Job pada `Wave 0`.
       2. Deployment Microservice dijalankan pada `Wave 1`.
       3. Notifikasi webhook HTTP dikirimkan via post-sync job pada `Wave 2` hanya jika Wave 0 dan 1 sukses.
       4. Jika migration job gagal, seluruh proses sync otomatis berhenti dan tidak memicu deployment workload.

---

### 14. Challenge

#### Skenario Studi Kasus Kompleks (Production Resiliency)

Sebuah platform perbankan global sedang mengoperasikan arsitektur multi-region Active-Active di AWS menggunakan GitOps (ArgoCD) dan OpenTofu. Anda ditantang untuk merancang arsitektur automasi yang tahan terhadap insiden berikut tanpa campur tangan manusia (zero manual intervention):

*   **Kondisi Awal**: Terjadi *split-brain* jaringan transatlantik antara Region Utama (`us-east-1`) dan Region Sekunder (`eu-central-1`).
*   **Chaos Event**: 
    1. Pipeline GitOps mendeteksi commit baru pada manifest release aplikasi.
    2. Saat controller ArgoCD di `eu-central-1` mencoba membaca upstream Git repo, koneksi timeout terjadi secara intermiten (packet drop 40%).
    3. Di saat bersamaan, developer secara manual menaikkan CPU limit di kluster `eu-central-1` via `kubectl edit` untuk mengatasi lonjakan beban darurat.
    4. State backend Terraform terkunci oleh proses pipeline yang *hung* akibat *dropped connection* ke DynamoDB table di `us-east-1`.

#### Tugas Anda:
1. Buat cetak biru (*Design Document*) yang mencakup:
   * Mekanisme *Decoupled State Backend* agar kegagalan region primer tidak melumpuhkan kemampuan rilis infrastruktur di region sekunder.
   * Strategi mitigasi GitOps controller agar tidak mengalami *thrashing* atau menghapus perubahan manual darurat sebelum insiden selesai dievaluasi (*maintenance window locking pattern*).
   * Implementasi OIDC Token validation architecture yang tetap aman saat Identity Provider (IdP) eksternal mengalami degradasi performa (High Latency).
2. Tuliskan file konfigurasi ArgoCD `ResourceHealth` dan `SyncPolicy` yang mampu membedakan antara *unhealthy workload* karena kegagalan downstream dependency vs *infrastructure failure*.

*(Selesaikan tantangan ini tanpa menggunakan solusi *clickops* atau akses SSH langsung ke server produksi).*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Apa fungsi utama dari atribut `LockID` pada DynamoDB saat digunakan sebagai backend remote Terraform?**
   * A. Menyimpan plain-text password untuk IAM role.
   * B. Mengidentifikasi unik file state yang sedang dimodifikasi untuk mencegah eksekusi konkuren yang merusak state.
   * C. Menghitung biaya pengeluaran infrastruktur per apply.
   * D. Menjadi primary key untuk memulihkan versi Terraform lama.

2. **Pada arsitektur GitOps murni (Pull-Based), di manakah agen kontroler sinkronisasi diinstal?**
   * A. Di laptop developer masing-masing.
   * B. Di dalam CI/CD shared server eksternal seperti Jenkins VM.
   * C. Di dalam kluster Kubernetes target.
   * D. Di dalam SaaS repository hosting Git.

3. **Operasi aljabar apa yang dilakukan Terraform Plan saat membandingkan State aktual dengan Desired Configuration?**
   * A. Transformasi Fourier.
   * B. Hashing simetris SHA-256.
   * C. Topological Graph Walk dan penghitungan delta himpunan ($Desired \setminus Current$).
   * D. Binary search tree lookup pada memori RAM.

4. **Apa risiko terbesar menyimpan file state Terraform di Git repository publik maupun privat?**
   * A. Waktu eksekusi `tofu init` menjadi lebih lambat.
   * B. File state berisi nilai atribut sumber daya dalam plain-text, termasuk potensi rahasia (passwords, private keys, tokens).
   * C. Git akan otomatis me-reject file berformat `.tfstate`.
   * D. File state akan memicu memory leak pada kernel Linux.

5. **Apa yang dimaksud dengan "Configuration Drift"?**
   * A. Perubahan struktur organisasi tim SRE secara berkala.
   * B. Kondisi di mana konfigurasi infrastruktur riil di cloud melenceng dari apa yang didefinisikan pada deklarasi kode IaC/Git.
   * C. Proses migrasi dari AWS ke Google Cloud Platform.
   * D. Penurunan latensi jaringan pada kluster Kubernetes.

#### Bagian 2: Intermediate (5 Pertanyaan)
6. **Dalam kalkulasi 3-Way Merge Patch di Kubernetes/GitOps, mengapa *Last-Applied-Configuration* mutlak diperlukan selain Desired dan Live State?**
   * A. Untuk mengalokasikan IP address pod secara statik.
   * B. Untuk membedakan apakah sebuah field yang hilang pada Desired State sengaja dihapus oleh engineer, atau merupakan field default yang ditambahkan secara otomatis oleh API Server/Mutating Webhook.
   * C. Untuk mempercepat enkripsi KMS pada database etcd.
   * D. Untuk mencegah developer membuka Pull Request baru.

7. **Kapan implementasi argumen `lifecycle { ignore_changes = [...] }` pada Terraform menjadi sebuah anti-pattern yang berbahaya?**
   * A. Ketika digunakan pada resource sementara (*ephemeral*).
   * B. Ketika digunakan untuk mengabaikan tag yang dikelola oleh software pihak ketiga.
   * C. Ketika digunakan secara berlebihan untuk menutupi kesalahan arsitektur (seperti cyclic modification) sehingga infrastruktur riil tidak lagi terlacak oleh kode sumber.
   * D. Ketika digunakan pada resource storage seperti EBS volume.

8. **Mengapa *AssumeRole pattern* berbasis OIDC lebih direkomendasikan untuk CI/CD pipeline dibandingkan menggunakan *Static IAM Access Keys*?**
   * A. Karena Static IAM Keys membutuhkan biaya langganan tambahan di AWS.
   * B. Karena OIDC menghasilkan short-lived credentials yang otomatis kedaluwarsa, mengeliminasi risiko kebocoran credential permanen pada runner logs atau environment variables.
   * C. Karena AssumeRole meningkatkan throughput jaringan hingga 10 Gbps.
   * D. Karena Static IAM Keys tidak mendukung deployment ke kluster Kubernetes.

9. **Apa implikasi dari mengaktifkan `ApplyOutOfSyncOnly=true` pada ArgoCD Sync Options?**
   * A. ArgoCD hanya akan merestart pods yang mengalami OOMKilled.
   * B. ArgoCD hanya mengirimkan payload patch ke API Server untuk resource yang berstatus *OutOfSync*, memangkas pemanggilan API yang tidak perlu pada deployment berskala ribuan manifest.
   * C. Mengizinkan sinkronisasi dilakukan tanpa melalui proses review Git.
   * D. Mematikan fitur self-healing secara permanen pada target cluster.

10. **Bagaimana cara Open Policy Agent (OPA) / Conftest mengevaluasi kepatuhan infrastruktur Terraform sebelum resource dibuat?**
    * A. Menjalankan reverse engineering dari file biner provider cloud.
    * B. Mengonversi `terraform plan` binary menjadi representasi JSON (`tofu show -json`), lalu mengevaluasi struktur data JSON tersebut terhadap kumpulan aturan logika deklaratif Rego.
    * C. Melakukan ping port HTTP secara periodik ke AWS endpoint.
    * D. Menguji unit test menggunakan framework Go secara dinamis.

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan Kompleks)
11. **Skenario Kasus A**:
    Platform Anda menggunakan Terraform untuk provisioning AWS RDS Aurora Cluster dan ArgoCD untuk mendeploy aplikasi backend. Seorang engineer menambahkan flag `deletion_protection = false` pada modul RDS di Git, melakukan plan, dan apply. Di saat yang sama, tim lain menghapus microservice di ArgoCD yang ternyata memicu cascading delete pada namespace yang memiliki custom finalizer. State locking Terraform tiba-tiba freeze, dan cluster database ikut terhapus.
    *Pertanyaan*: Apa perbaikan arsitektur mitigasi paling fundamental yang harus diterapkan untuk menjamin database produksi tidak bisa terhapus oleh pipeline automasi apa pun?
    * A. Menghapus akun AWS dan membuatnya kembali dari awal.
    * B. Mengimplementasikan IAM Permission Boundary dan AWS Service Control Policy (SCP) pada level AWS Organization yang menolak aksi `rds:DeleteDBCluster` terhadap resource ber-tag `Environment=production`, terlepas dari apapun yang dideklarasikan oleh Terraform.
    * C. Menambahkan `sleep 300` pada seluruh script bash CI runner sebelum perintah apply.
    * D. Mengganti database Aurora dengan deployment SQLite di dalam Pod Kubernetes.

12. **Skenario Kasus B**:
    Anda mengelola 50 kluster Kubernetes di seluruh dunia menggunakan ArgoCD ApplicationSet dengan generator Git Directory. Suatu hari, sistem Git internal mengalami lonjakan latensi tinggi (HTTP 504 Gateway Timeout). Controller ArgoCD di semua kluster mendadak menandai seluruh microservices sebagai `OutOfSync` dan mulai menghentikan (*pruning*) puluhan workload aplikasi di production.
    *Pertanyaan*: Mengapa controller bertindak destruktif seperti itu, dan parameter spec apa yang dapat mencegah bencana tersebut?
    * A. Timeout menyebabkan repo-server merender manifest kosong (*empty tree*). Karena `prune: true` aktif, ArgoCD mengasumsikan seluruh workload telah dihapus dari Git dan menghapusnya dari cluster. Pencegahannya adalah mengatur sync options `PruneLast=true` serta mengonfigurasi `retry` backoff policy dan guardrail validasi non-empty manifest sebelum sync dieksekusi.
    * B. Kubernetes API server secara default menghapus pod jika tidak ada koneksi internet ke Git.
    * C. Hal tersebut merupakan bug etcd dan solusinya adalah merestart master node.
    * D. ArgoCD kehabisan memori sehingga mengirimkan sinyal SIGKILL ke seluruh container.

13. **Skenario Kasus C**:
    Dua tim SRE berbagi satu remote state file Terraform untuk mengelola VPC dan Subnet. Tim A menambahkan subnet baru dengan CIDR `10.0.5.0/24`. Tim B, tanpa koordinasi, menjalankan modul yang menggunakan fungsi `cidrsubnet(var.vpc_cidr, 8, count.index)`. Saat Tim B melakukan apply, rute subnet milik Tim A terhapus dari state dan AWS Console karena kalkulasi overlapping index.
    *Pertanyaan*: Bagaimana merancang struktur state dan modul Terraform untuk menghindari bencana dependensi indeks ini pada skala enterprise?
    * A. Menggabungkan seluruh infrastruktur ke dalam satu file `main.tf` raksasa dengan 50.000 baris kode.
    * B. Memecah state monolith menjadi state-state mikro yang terisolasi (*State Slicing*), menghentikan penggunaan alokasi subnet berbasis *dynamic sequential index* (`count.index`), dan beralih ke struktur eksplisit `for_each` dengan *keyed map* unik yang persisten.
    * C. Menjalankan perintah `tofu apply` bergantian menggunakan jadwal spreadsheet manual.
    * D. Mengubah cloud provider setiap kali ada subnet baru yang dibuat.

---

#### Kunci Jawaban & Evaluasi Quiz

##### Bagian 1: Basic
1. **B**: LockID pada DynamoDB mencegah race-condition eksekusi `apply` bersamaan yang berpotensi merusak integritas file state.
2. **C**: Arsitektur Pull-Based GitOps menempatkan controller (seperti ArgoCD/Flux) langsung di dalam target kluster untuk mengeliminasi kebutuhan membuka port ingress kluster ke publik.
3. **C**: Terraform memodelkan dependensi sebagai Directed Acyclic Graph (DAG) dan menghitung selisih aljabar antara kondisi riil API cloud dan deklarasi file konfigurasi.
4. **B**: State file secara historis dan fundamental menyimpan representasi output infrastruktur apa adanya dalam format teks biasa (plain text), termasuk data rahasia seperti generated passwords.
5. **B**: Configuration drift adalah deviasi antara kondisi aktual komponen infrastruktur yang sedang berjalan dengan blueprint yang tersimpan di repositori Git.

##### Bagian 2: Intermediate
6. **B**: *Last-Applied-Configuration* berfungsi sebagai baseline ketiga untuk membedakan modifikasi yang disengaja di Git vs injeksi default oleh sistem admission control internal kluster (menghindari infinite loops).
7. **C**: Mengabaikan perubahan field secara permanen via `ignore_changes` tanpa alasan yang terdokumentasi dengan baik merusak sifat deklaratif IaC dan menyembunyikan drift berbahaya di lingkungan produksi.
8. **B**: OIDC mengeliminasi *long-lived static secret keys* di CI/CD tools. Runner mengasumsikan role sementara via token JWT pendek yang dienkripsi, mengurangi risiko credential leak secara drastis.
9. **B**: Opsi ini mengoptimalkan kinerja kluster secara signifikan dengan hanya merekonsiliasi delta resource yang memang mengalami modifikasi atau out-of-sync, menurunkan load API server.
10. **B**: OPA/Conftest mengevaluasi file plan Terraform yang diekspor menjadi format JSON terhadap file kebijakan Rego yang mendefinisikan aturan kepatuhan (*governance*).

##### Bagian 3: Skenario Kasus Produksi
11. **B**: Solusi enterprise SRE sejati tidak mengandalkan proteksi level-aplikasi semata, melainkan menerapkan pertahanan berlapis (*Defense-in-Depth*). AWS SCP berada di atas seluruh kredensial IAM akun, memastikan perintah delete DB ditolak di tingkat otorisasi root cloud policy.
12. **A**: Ketika manifest parser menghasilkan response kosong akibat transient failure, controller yang ceroboh akan menganggap seluruh resource telah sengaja dihapus dari git. Menerapkan safe-guards, retry policies, dan membatasi destructive operations adalah mitigasi mutlak di level enterprise.
13. **B**: Penggunaan `count.index` untuk sumber daya jaringan adalah anti-pattern umum karena penghapusan atau penambahan elemen di tengah array akan menggeser seluruh index di bawahnya, memicu rekreasi atau penghapusan destruktif. Membagi state file dan beralih ke `for_each` map mengatasi masalah ini secara deterministik.

---

### 16. Summary

*   **Pondasi Immutability**: Infrastruktur modern harus diperlakukan sebagai entitas deklaratif, di mana kode di repositori Git adalah representasi absolut dari realitas sistem di cloud (*Single Source of Truth*).
*   **Graf dan Konsistensi**: Mesin Terraform/OpenTofu mengeksekusi DAG melalui *topological walk*, sedangkan GitOps controller (ArgoCD) memanfaatkan algoritma *3-Way Merge Patch* untuk memastikan *state convergence* tanpa merusak mutasi sah dari admission webhooks kluster.
*   **Zero-Trust Security**: Jangan pernah mempercayai validasi manual. Penerapan **Policy-as-Code (OPA/Rego)** di alur PR, isolasi credential via **OIDC Assume-Role**, serta manajemen rahasia terintegrasi via **External Secrets Operator** merupakan standar wajib produksi enterprise.
*   **Resiliensi Arsitektur**: Pemisahan tegas (*separation of concerns*) antara lapisan *substrate* (Cloud IaC) dan lapisan *workload* (GitOps Manifests) adalah kunci untuk mencegah siklus rekonsiliasi yang saling bertabrakan (*reconciliation storms*) dan kegagalan kaskade multi-region.