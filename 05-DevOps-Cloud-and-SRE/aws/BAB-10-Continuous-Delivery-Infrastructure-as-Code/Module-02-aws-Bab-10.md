# BAB 10: Continuous Delivery & Infrastructure as Code (IaC)
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang dan mengimplementasikan** arsitektur CI/CD untuk Infrastructure as Code (IaC) multi-akun enterprise menggunakan pola *least-privilege* berbasis OpenID Connect (OIDC) tanpa *long-lived credentials*.
- **Menganalisis internal state engine** (Terraform/OpenTofu dan AWS CloudFormation/CDK) mencakup Directed Acyclic Graph (DAG), mekanisme locking terdistribusi, serta resolusi siklus dependensi kompleks.
- **Membangun sistem Policy-as-Code** berlapis (*defense-in-depth*) menggunakan Open Policy Agent (OPA/Rego) dan AWS CloudFormation Guard guna mencegah miskonfigurasi keamanan sebelum fase provisioning.
- **Mengembangkan strategi deployment nol-downtime** untuk infrastruktur stateful dan stateless melalui teknik *Blue/Green*, *Canary*, dan *Dynamic Ephemeral Environments*.
- **Mengotomatisasi deteksi dan rekonsiliasi state drift** pada skala ratusan akun AWS menggunakan Event-Driven Architecture.

---

### 2. Prerequisite
Sebelum mendalami modul ini, peserta wajib menguasai:
- **AWS Fundamental & Security**: Pemahaman mendalam tentang AWS IAM (Trust Policies, Permission Boundaries, STS AssumeRole), AWS Organizations, dan Service Control Policies (SCP).
- **Core IaC Knowledge**: Sintaksis dasar HashiCorp Configuration Language (HCL) atau AWS Cloud Development Kit (CDK v2 - TypeScript/Python), struktur direktori modular, serta lifecycle state (`init`, `plan`, `apply`, `destroy`).
- **DevOps Mechanics**: Pemahaman mendalam terkait Git branching model (Trunk-Based Development), containerization (Docker), dan eksekusi CI/CD pipeline (GitHub Actions, GitLab CI, atau AWS CodePipeline).
- **Networking**: VPC, Subnetting, Transit Gateway, Route Tables, Security Groups, dan Endpoint Services (PrivateLink).

---

### 3. Concept & Internal Architecture

#### 3.1 Lifecycle & State Engine Mechanics
Sistem IaC modern berbasis state deklaratif (seperti Terraform/OpenTofu) beroperasi dengan membandingkan tiga representasi status sistem:
1. **Desired State**: Kode konfigurasi yang ditulis oleh perekayasa (HCL/CDK code).
2. **Current State (Recorded)**: Snapshot metadata terakhir yang tersimpan di remote backend (`terraform.tfstate`).
3. **Actual State**: Infrastruktur nyata yang berjalan di API AWS.

```
       [ Desired State (HCL/CDK) ]
                   │
                   ▼ (Synthesize/Parse)
       [ Directed Acyclic Graph (DAG) ]
                   │
                   ▼ (Refresh & Diff)
  ┌─────────────────────────────────┐
  │  Current State vs Actual State  │◄───── AWS Cloud APIs
  └─────────────────────────────────┘
                   │
                   ▼ (Generate Execution Plan)
       [ Evaluation / Policy-as-Code ]
                   │
                   ▼ (Acquire Lock & Apply)
       [ AWS Provider Engine ] ───────► Target Resources
```

Saat perintah `plan` atau `apply` dieksekusi:
- **Graph Construction**: Parser memindai seluruh file konfigurasi dan membentuk *Directed Acyclic Graph* (DAG). Setiap node merepresentasikan resource, data source, atau provider configuration, sedangkan edge merepresentasikan dependensi implisit (interpolasi atribut) atau eksplisit (`depends_on`).
- **State Refresh**: Engine melakukan komparasi konkurensi paralel (diatur oleh `-parallelism=n`) ke endpoint AWS API untuk menyinkronkan *Current State* dengan *Actual State*.
- **Plan Generation**: Kalkulasi delta matematika: 
  $$\Delta = \text{Desired State} \setminus \text{Actual State}$$
  Menghasilkan status: `Create`, `Update-in-Place`, `Destroy-and-Recreate` (jika atribut bersifat immutable, seperti `vpc_id` pada subnet).
- **State Locking Mechanism**: Mencegah race condition ketika dua pipeline mengeksekusi state yang sama secara simultan. Pada Amazon S3 backend, lock diakuisisi melalui Amazon DynamoDB table (menggunakan atribut `LockID` bertipe string dengan mekanisme conditional writes `attribute_not_exists(LockID)`). S3 Native Locking kini juga didukung menggunakan fitur conditional writes S3 API.

#### 3.2 Dynamic Cross-Account Deployment via AWS OIDC & IAM Federation
Penggunaan IAM User access keys statis (`AKIA...`) dalam enterprise pipeline menghadirkan risiko keamanan kritikal (*credential exfiltration*). Arsitektur produksi modern mewajibkan federasi identitas berbasis OpenID Connect (OIDC).

```
┌──────────────────────┐                     ┌─────────────────────┐
│ GitHub Actions /     │                     │   AWS Security      │
│ GitLab CI Runner     │                     │   Token Service     │
└──────────┬───────────┘                     └──────────┬──────────┘
           │ 1. Request JWT Identity Token              │
           │    (Claims: sub, aud, iss, repo)           │
           │                                            │
           │ 2. AssumeRoleWithWebIdentity(JWT, RoleARN) │
           ├───────────────────────────────────────────►│
           │                                            │ 3. Validate JWT
           │                                            │    against OIDC Provider
           │                                            │    & Match Trust Policy
           │ 4. Issue Short-Lived STS Credentials       │
           │◄───────────────────────────────────────────┤
           │    (AccessKey, SecretKey, SessionToken)    │
           │                                            │
┌──────────▼───────────┐                     ┌──────────▼──────────┐
│ Central CI/CD        ├────────────────────►│ Production Account  │
│ Automation Account   │ 5. Assume Deployment│ (Target Workload)   │
└──────────────────────┘    Role in Target   └─────────────────────┘
                            Account via STS
```

- **Identity Validation**: Identity Provider (IdP) memverifikasi penandatanganan kriptografis JWT payload.
- **Trust Scoping**: Kebijakan kepercayaan IAM (*Trust Policy*) secara presisi mengevaluasi klaim `sub` (*subject*), misalnya: `repo:enterprise-org/core-infra:ref:refs/heads/main`, memastikan branch yang tidak terotorisasi tidak dapat mengasumsikan peran deployment.

---

### 4. Why & What

| Dimensi | Pendekatan Monolitik / Tradisional | Pendekatan Enterprise IaC Continuous Delivery |
| :--- | :--- | :--- |
| **Blast Radius** | Satu state file besar untuk seluruh infrastruktur organisasi (risiko *catastrophic failure* tinggi). | Terisolasi per akun, domain fungsional (Network, Data, App), dan environment melalui *layered state design*. |
| **Autentikasi Pipeline** | Hardcoded IAM User Access Keys dengan rotasi manual berkala (rentan bocor). | OIDC Short-lived STS session tokens berbasis claim validation dinamis. |
| **Governance** | Manual security review saat PR (*ad-hoc*, rawan *human error*). | Automated Policy-as-Code (OPA/Guard/Checkov) terintegrasi pada status checks PR blocking. |
| **State Drift** | Terdeteksi hanya ketika deployment manual gagal atau saat insiden breakdown. | Automated continuous drift detection berbasis scheduled pipeline dan alarm event-driven. |
| **Eksekusi Apply** | Manual apply dari terminal lokal laptop engineer via privileged profile. | Fully automated, hands-off infrastructure deployment via GitOps engine / CI/CD orchestration. |

---

### 5. How (Workflow Detail)

Arsitektur siklus hidup eksekusi IaC Enterprise dirancang tanpa intervensi lokal (*Zero Console/Local Apply Access*):

```
Developer Workstation
      │  git push (feature/core-db-v2)
      ▼
GitHub Enterprise / GitLab
      │  Pull Request Created
      ├──► Step 1: Pre-commit & Static Linting (TFLint, Trivy, Checkov)
      ├──► Step 2: Policy-as-Code Evaluation (OPA Conftest / CFN Guard)
      ├──► Step 3: STS OIDC Authentication (Assume Scoped Plan Role)
      ├──► Step 4: Speculative Plan (`terraform plan -lock=false`)
      └──► Step 5: Post Plan Summary to PR Comments
      │
Engineering Leads Review & Merge to `main`
      ▼
Deployment Workflow Triggered
      ├──► Step 1: STS OIDC Authentication (Assume Privileged Apply Role)
      ├──► Step 2: Acquire Distributed Lock (DynamoDB / S3 Mutex)
      ├──► Step 3: Terraform Apply Execution with Cryptographic Logging
      ├──► Step 4: Post-deployment Smoke Tests (E2E Validation)
      └──► Step 5: Release Lock & Invalidate Ephemeral STS Tokens
```

#### Tahapan Delivery Pipeline:
1. **Validation & Static Analysis**:
   - Memeriksa integritas sintaks (`terraform fmt -check`, `terraform validate`).
   - Menganalisis *security vulnerabilities* berbasis abstraksi AST menggunakan Trivy dan Checkov.
2. **Policy Verification (Deterministic Gate)**:
   - Output rencana eksekusi dikonversi ke format machine-readable JSON: `terraform show -json tfplan.binary > tfplan.json`.
   - Engine OPA mengevaluasi aturan bisnis (misal: "Instans RDS dilarang memiliki atribut `publicly_accessible = true`" dan "Semua resource wajib memiliki Tag `CostCenter`").
3. **Execution Isolation**:
   - Fase `plan` hanya membaca state (`ReadOnly` + KMS Decrypt).
   - Fase `apply` mewajibkan *Branch Protection Rule* dengan *status checks* lolos, approval minimal 2 Principal/Staff Engineer, dan eksekusi pada environment target via role assumption terisolasi.

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
Bayangkan membangun gedung bertingkat tinggi dengan sistem prefabrikasi modern:
- **HCL / Desired State**: Cetak biru teknik arsitektur sipil bersertifikasi.
- **Dynamic Graph (DAG)**: Urutan kritis konstruksi. Anda tidak bisa mencor lantai 5 sebelum tiang pancang dan balok baja lantai 4 terpasang secara stabil.
- **Terraform State File**: Buku inventaris fisik material yang mencatat spesifikasi mikrometer dari setiap mur, baut, dan panel yang terpasang di lapangan.
- **DynamoDB State Lock**: Palang pengaman fisik di pintu gerbang konstruksi. Hanya satu mandor yang boleh membawa surat izin modifikasi area pada satu waktu agar tidak terjadi tabrakan instruksi antar tim.
- **Policy-as-Code (OPA)**: Inspektur keselamatan independen yang langsung menyetop truk semen di gerbang jika mutu beton tidak sesuai klausul SNI/ISO yang dipersyaratkan.

#### Topologi Multi-Account Enterprise

```
                               ┌────────────────────────┐
                               │  AWS Organizations     │
                               │  Root / Management     │
                               └───────────┬────────────┘
                                           │
         ┌─────────────────────────────────┴─────────────────────────────────┐
         │                                                                   │
         ▼                                                                   ▼
┌─────────────────────────────┐                               ┌─────────────────────────────┐
│ Core Services OU            │                               │ Workloads OU                │
│                             │                               │                             │
│ ┌─────────────────────────┐ │   OIDC Token AssumeRole       │ ┌─────────────────────────┐ │
│ │ CI/CD Tooling Account   │ ├──────────────────────────────┼─►│ Non-Production Account  │ │
│ │ - GitHub Actions Runner │ │   (Least Privilege Execution) │ │ - Dev / QA Workloads    │ │
│ │ - Artifact Registry     │ │                               │ └─────────────────────────┘ │
│ │ - Audit Log Storage     │ │                               │                             │
│ └─────────────────────────┘ │                               │ ┌─────────────────────────┐ │
│                             │                               │ │ Production Account      │ │
│ ┌─────────────────────────┐ │                               │ │ - Prod Workloads        │ │
│ │ Shared Network Account  │ │                               │ │ - Strict Guardrails     │ │
│ │ - Transit Gateway       │ │                               │ └─────────────────────────┘ │
│ └─────────────────────────┘ │                               │                             │
└─────────────────────────────┘                               └─────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Dynamic Remote Backend dengan AssumeRole
Konfigurasi root module yang memisahkan eksekusi pipeline dari akun backend penyimpanan state:

```hcl
# versions.tf
terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40.0"
    }
  }

  backend "s3" {
    bucket         = "corp-tfstate-ap-southeast-3-production"
    key            = "foundation/networking/terraform.tfstate"
    region         = "ap-southeast-3"
    dynamodb_table = "corp-tflocks-ap-southeast-3"
    encrypt        = true
  }
}

provider "aws" {
  region = "ap-southeast-3"

  # Mengasumsikan peran deployment secara dinamis
  assume_role {
    role_arn     = var.target_deployment_role_arn
    session_name = "TerraformCDExecutionSession"
  }

  default_tags {
    tags = {
      ManagedBy   = "Terraform"
      Environment = var.environment
      Repository  = "enterprise-org/terraform-aws-network"
    }
  }
}
```

#### 7.2 Practical Example: Enterprise Production-Ready Infrastructure with OPA Enforcement

Berikut adalah implementasi modular arsitektur deployment VPC & EKS baseline, diproteksi oleh skrip Policy-as-Code Open Policy Agent (OPA) dan workflow deployment otomatis GitHub Actions berbasis OIDC federation.

##### File: `modules/secure_network/main.tf`
```hcl
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.environment}-core-vpc"
  }
}

resource "aws_flow_log" "vpc_flow_logs" {
  iam_role_arn    = var.flow_log_role_arn
  log_destination = var.log_bucket_arn
  traffic_type    = "ALL"
  vpc_id          = aws_vpc.main.id
}

resource "aws_subnet" "private" {
  count             = length(var.private_subnet_cidrs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  map_public_ip_on_launch = false

  tags = {
    Name                                      = "${var.environment}-private-subnet-${count.index + 1}"
    "kubernetes.io/role/internal-elb"         = "1"
    "kubernetes.io/cluster/${var.cluster_id}" = "shared"
  }
}

output "vpc_id" {
  description = "ID dari VPC yang berhasil dibuat"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "Daftar Subnet Private"
  value       = aws_subnet.private[*].id
}
```

##### File: `policies/opa/networking_rules.rego`
Policy OPA untuk memastikan tidak ada alokasi Public IP secara implisit dan Flow Log wajib aktif:

```rego
package terraform.validation

import future.keywords.in

default allow = false

# Lolos jika tidak ada violation
allow {
    count(violations) == 0
}

# Rule 1: Mencegah map_public_ip_on_launch bernilai true pada resource subnet
violations[msg] {
    some resource in input.resource_changes
    resource.type == "aws_subnet"
    resource.change.after.map_public_ip_on_launch == true
    msg := sprintf("Pelanggaran Keamanan: Subnet %v mengaktifkan map_public_ip_on_launch. Publik IP langsung dilarang di tier subnet ini!", [resource.address])
}

# Rule 2: Wajib menyertakan Flow Logs pada VPC baru
violations[msg] {
    some resource in input.resource_changes
    resource.type == "aws_vpc"
    resource.change.actions[_] == "create"
    not flow_log_configured(resource.address)
    msg := sprintf("Kepatuhan Audit: VPC %v didaftarkan tanpa asosiasi aws_flow_log yang valid.", [resource.address])
}

flow_log_configured(vpc_address) {
    some flow_log in input.resource_changes
    flow_log.type == "aws_flow_log"
    flow_log.change.after.vpc_id == sprintf("${%v.id}", [vpc_address])
}
```

##### File: `.github/workflows/iac-continuous-delivery.yml`
```yaml
name: Enterprise IaC Continuous Delivery

on:
  pull_request:
    branches: [ "main" ]
  push:
    branches: [ "main" ]

permissions:
  id-token: write   # Wajib untuk autentikasi OIDC AWS
  contents: read    # Membaca repositori git
  pull-requests: write

jobs:
  validate-and-plan:
    name: Terraform Plan & Security Gate
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Setup Terraform Engine
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.7.5

      - name: Setup Open Policy Agent (OPA)
        uses: open-policy-agent/setup-opa@v2
        with:
          version: 0.62.0

      - name: Authenticate to AWS via OIDC
        uses: aws-actions/configure-aws-credentials@v4
        with:
          audience: sts.amazonaws.com
          aws-region: ap-southeast-3
          role-to-assume: arn:aws:iam::112233445566:role/github-actions-iac-plan-role
          role-session-name: GitHubActionsTerraformPlan

      - name: Terraform Init
        run: terraform init

      - name: Terraform Plan
        id: plan
        run: |
          terraform plan -no-color -out=tfplan.binary
          terraform show -json tfplan.binary > tfplan.json

      - name: Policy Evaluation (OPA Conftest)
        run: |
          opa eval --data policies/opa/networking_rules.rego \
                   --input tfplan.json \
                   "data.terraform.validation.violations" \
                   --format pretty > violations.txt
          
          if [ -s violations.txt ] && ! grep -q "\[\]" violations.txt; then
            echo "::error::Policy-as-Code violations ditemukan:"
            cat violations.txt
            exit 1
          fi

      - name: Comment Plan Output on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const output = `### Pipeline Validations Passed! ✅
            #### OPA Security Check: SUCCESS
            *Target Plan Binary generated successfully for staging verification.*`;
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: output
            })

  apply:
    name: Terraform Apply (Production Execution)
    needs: [validate-and-plan]
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Setup Terraform Engine
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.7.5

      - name: Authenticate to Production AWS via OIDC
        uses: aws-actions/configure-aws-credentials@v4
        with:
          audience: sts.amazonaws.com
          aws-region: ap-southeast-3
          role-to-assume: arn:aws:iam::998877665544:role/github-actions-iac-prod-apply-role
          role-session-name: GitHubActionsTerraformApply

      - name: Terraform Init
        run: terraform init

      - name: Terraform Apply
        run: terraform apply -auto-approve
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Klien
Sebuah Bank Digital Nasional (fintech unicorn) memigrasikan infrastruktur monolitik on-premise ke AWS. Arsitektur mencakup **250+ akun AWS** (terisolasi per bounded context: Payment, Core Banking, KYC, Lending), melayani 40.000 TPS (*transactions per second*) pada peak period, dan wajib patuh terhadap regulasi PCI-DSS Level 1 dan OJK POJK No. 38.

#### Permasalahan Skala Produksi
1. **State Locking Bottleneck & Blast Radius Bencana**: Seluruh infrastruktur dikelola dalam satu repository monolitik dengan satu file state S3 sebesar 85MB. Eksekusi `terraform plan` memakan waktu **48 menit** akibat *API rate-limiting* (AWS STS and CloudControl limits) dan throttling DynamoDB. Jika satu engineer melakukan provisioning, seluruh engineer lain terblokir oleh remote lock.
2. **Kredensial Liar**: Ditemukan lebih dari 80 IAM user aktif yang memiliki access key jangka panjang tersimpan di laptop developer dan CI system lama tanpa logging rotasi.
3. **Konfigurasi Tanpa Izin (Console Drift)**: Sering kali teknisi operasi melakukan perubahan konfigurasi langsung di AWS Console saat *on-call incident triage*, tanpa mencerminkannya kembali ke repository Git. Ketika pipeline merge berjalan, perubahan krusial di-override secara mendadak, memicu downtime parsial berulang kali.

#### Solusi Rekayasa Infrastruktur
1. **De-komposisi State Terdistribusi (State Layering Architecture)**:
   - Membagi repository monolitik menjadi pola arsitektur layer berbasis domain: *Foundation Layer* (VPC, TGW), *Platform Layer* (EKS Clusters, RDS Global), dan *Application Services Layer* (S3, IAM, SQS).
   - Setiap layer memiliki AWS S3 remote backend terisolasi dengan siklus rotasi independen. Waktu kalkulasi `terraform plan` dipangkas dari **48 menit menjadi 2.5 menit**.
2. **Eliminasi IAM Access Keys dengan Centralized IAM OIDC Proxy Hub**:
   - Membangun akun dedicated *CI/CD Tooling Account*. GitHub Actions Runner self-hosted mengautentikasi ke akun ini via STS OIDC, kemudian melakukan chained assume-role ke *Target Workload Accounts* menggunakan IAM trust policy berbasis kondisi cryptographically validated.
3. **Automated Event-Driven Drift Detection & Auto-Remediation Engine**:
   - Menerapkan integrasi AWS CloudTrail + Amazon EventBridge. Setiap mutasi mutating API call (misalnya `AuthorizeSecurityGroupIngress`) dari konsol AWS mentrigger AWS Step Functions yang mengecek apakah mutasi tersebut dipicu oleh IAM Role deployment resmi.
   - Jika mutasi berasal dari sesi console liar, Lambda function langsung menginvalidasi mutasi tersebut (*revert action*) dan mengirimkan alert via Webhook Slack SOC (*Security Operations Center*).

```
[ Engineer Manual Console Edit ]
               │
               ▼
   [ AWS CloudTrail Logging ]
               │
               ▼
     [ Amazon EventBridge ]
               │ (Filter non-IaC IAM Role API Call)
               ▼
    [ AWS Step Functions ]
        ├──► Trigger AWS Lambda (Invoke Auto-Revert API Call)
        └──► Send Alert to Slack SOC / Opsgenie Incident
```

#### Hasil Metrik Bisnis & Operasional
- **Deployment Frequency**: Meningkat dari 2 kali per bulan menjadi 14 kali per hari.
- **Lead Time for Changes**: Menurun dari 3 hari menjadi 15 menit.
- **Audit Findings**: Temuan audit eksternal PCI-DSS terkait akses manual privileged turun drastis ke angka **0 (Zero-Finding)** dalam siklus audit tahunan berikutnya.

---

### 9. Trade-offs

Setiap keputusan arsitektur IaC dan Continuous Delivery membawa trade-off nyata yang harus dievaluasi berdasarkan skala organisasi:

```
                  IaC Tooling & Architecture Trade-off Spectrum

 [ HCL (Terraform/OpenTofu) ]                   [ Imperative / CDK (TS/Python) ]
  Static, Declarative, Rigid                     Turing-Complete, Dynamic, Leaky Abstraction
  ◄─────────────────────────────────────────────────────────────────────────────►
  + Prediktif dan deterministik                  + Pengurangan duplikasi kode (OOP)
  + Kompilasi cepat                              + Abstraksi high-level (L2/L3 constructs)
  - Abstraksi logika kompleks rumit              - Rentan terhadap runtime logic bug
  - DRY enforcement terbatas                     - Analisis statis keamanan lebih berat

 [ Monorepo IaC Architecture ]                  [ Multi-repo / Micro-IaC ]
  ◄─────────────────────────────────────────────────────────────────────────────►
  + Single source of truth                       + Blast radius terisolasi sempurna
  + Visibilitas cross-dependency tinggi          + Waktu eksekusi CI/CD sangat cepat
  - CI trigger overhead tinggi                   - Orkestrasi cross-state kompleks
  - Potensi state contention/race condition      - Duplikasi pipeline config
```

#### Matriks Evaluasi Alternatif Pendekatan

| Kriteria Keputusan | Centralized IaC Delivery Pipeline | Distributed / Cross-Account Decentralized |
| :--- | :--- | :--- |
| **Performance & Latency** | Terhambat oleh *queue lock contention* saat skala pipeline mencapai ratusan eksekusi paralel harian. | Optimal. State lock terdistribusi di setiap akun target secara mandiri. |
| **Scalability Matrix** | Sulit diskalakan melampaui 100 node akun tanpa mengalami degradasi STS rate limits. | Skalabilitas horizontal tinggi mengikuti struktur unit bisnis (*bounded contexts*). |
| **Blast Radius** | **Kritis**: Kompromi pada shared account runner membocorkan akses ke seluruh cluster akun AWS. | **Rendah**: Kegagalan kredensial terisolasi murni pada target workload account terkait. |
| **Cost Implication** | Biaya compute CI/CD runner terpusat lebih murah; utilisasi resource tinggi. | Sedikit lebih tinggi akibat duplikasi state store S3/DynamoDB bucket logs di tiap akun. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Silent State Drift Akibat Ignored Attributes
- **Gejala**: Drift terus muncul di plan padahal konfigurasi Terraform lokal tidak pernah diubah.
- **Penyebab**: AWS autoscaling atau controller eksternal (misal: AWS Load Balancer Controller di EKS) memodifikasi resource (seperti `aws_autoscaling_group.desired_capacity` atau tag pada subnets) secara dinamis.
- **Solusi**: Gunakan blok `lifecycle` dengan `ignore_changes` secara presisi:
  ```hcl
  resource "aws_autoscaling_group" "eks_nodes" {
    # ... konfigurasi lainnya ...
    lifecycle {
      ignore_changes = [
        desired_capacity,
        tag,
        load_balancers
      ]
    }
  }
  ```

#### 10.2 State Lock Macet (*Stale State Lock Deadlock*)
- **Gejala**: Pipeline gagal dengan error: `Error: Error acquiring the state lock: ConditionalCheckFailedException`.
- **Penyebab**: Runner CI/CD di-kill secara paksa (*OOMKilled* atau timeout runner) saat `terraform apply` sedang berjalan, meninggalkan item lock di DynamoDB.
- **Langkah Troubleshooting**:
  1. Verifikasi apakah ada pipeline lain yang benar-benar sedang berjalan untuk commit tersebut.
  2. Dapatkan `Lock Info` dari pesan error:
     ```
     Lock Info:
       ID:        3b469b82-990a-1a84-969c-fefef9392e21
       Path:      corp-tfstate-ap-southeast-3-production/foundation/networking/terraform.tfstate
       Who:       runner@actions-runner-node-04
     ```
  3. Lepaskan lock menggunakan identity yang memiliki hak akses IAM:
     ```bash
     terraform force-unlock -force 3b469b82-990a-1a84-969c-fefef9392e21
     ```

#### 10.3 Dependency Cycle (*Graph Loops*)
- **Gejala**: Terraform melempar error: `Error: Cycle: aws_security_group_rule.sg_a_to_b, aws_security_group.sg_b, aws_security_group.sg_a`.
- **Penyebab**: Security group A mereferensikan Security group B, dan Security Group B secara sirkular mereferensikan Security Group A di dalam deklarasi inline.
- **Solusi**: Pecah aturan security group menjadi resource mandiri (`aws_security_group_rule`) terpisah dari deklarasi utama kontainer security group (`aws_security_group`).

---

### 11. Best Practices (Production Checklist)

#### Pre-commit & Static Code Quality
- [ ] TFLint dikonfigurasi dengan rule module AWS aktif (`tflint --init`).
- [ ] Git pre-commit hook memvalidasi formatting via `terraform fmt -check -recursive`.
- [ ] Scan hardcoded secret menggunakan Gitleaks dan Trivy sebelum commit masuk staging.

#### State Storage & Security Hardening
- [ ] S3 Bucket State mengaktifkan **Bucket Versioning** (wajib untuk disaster recovery rollback).
- [ ] Bucket State mewajibkan enkripsi at-rest berbasis KMS Customer Managed Key (CMK) dengan key rotation aktif.
- [ ] Bucket Policy menerapkan kondisi `aws:SecureTransport: "true"` (enforce HTTPS only).
- [ ] State bucket memblokir seluruh akses publik (`aws_s3_account_public_access_block`).
- [ ] Lifecycle policy dikonfigurasi untuk memindahkan versi noncurrent state ke S3 Glacier Flexible Retrieval setelah 90 hari.

#### Identity & Deployment Governance
- [ ] Pipeline CI/CD 100% menggunakan short-lived AWS STS credentials via Web Identity Federation (OIDC).
- [ ] IAM Role memiliki batas akses (*Permissions Boundary*) yang mencegah eskalasi privilege di luar domain IaC.
- [ ] Mengaktifkan *Speculative Plans* pada Pull Requests untuk mencegah modifikasi state yang belum diotorisasi.
- [ ] Penerapan Policy-as-Code (OPA/Guard) sebagai status check mandatory (*Required Check*) sebelum merge ke protected branch.
- [ ] Drift detection dijadwalkan berjalan harian (misal: cronjob jam 02:00 UTC) untuk mencatat deviasi infrastruktur nyata.

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun struktur remote state governance yang aman dengan pipeline validasi OIDC dan policy check.

#### Struktur Direktori Lab: `hands-on/m02/`
```
hands-on/m02/
├── backend-bootstrap/
│   ├── main.tf
│   └── outputs.tf
├── live/
│   └── production/
│       ├── main.tf
│       ├── terraform.tf
│       └── variables.tf
├── policies/
│   └── check_tags.rego
└── scripts/
    ├── run_plan_securely.sh
    └── verify_backend.sh
```

#### Langkah 1: Bootstrap Secure Remote Backend & Locking
Buat file `hands-on/m02/backend-bootstrap/main.tf`:

```hcl
provider "aws" {
  region = "ap-southeast-3"
}

resource "aws_kms_key" "state_key" {
  description             = "KMS Key for Terraform State Storage"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Environment = "Bootstrap"
  }
}

resource "aws_s3_bucket" "tf_state" {
  bucket        = "iac-adv-prod-tfstate-${random_id.suffix.hex}"
  force_destroy = false
}

resource "random_id" "suffix" {
  byte_length = 4
}

resource "aws_s3_bucket_versioning" "versioning" {
  bucket = aws_s3_bucket.tf_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "encrypt" {
  bucket = aws_s3_bucket.tf_state.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.state_key.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "block_public" {
  bucket                  = aws_s3_bucket.tf_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_dynamodb_table" "tf_locks" {
  name         = "iac-adv-prod-tflocks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }
}

output "state_bucket_name" {
  value = aws_s3_bucket.tf_state.bucket
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.tf_locks.name
}

output "kms_key_arn" {
  value = aws_kms_key.state_key.arn
}
```

Eksekusi bootstrap:
```bash
cd hands-on/m02/backend-bootstrap/
terraform init
terraform apply -auto-approve
```

Catat output `state_bucket_name` dan `dynamodb_table_name`.

#### Langkah 2: Menulis Konfigurasi Infrastruktur & Policy
Buat file policy di `hands-on/m02/policies/check_tags.rego`:

```rego
package terraform.tags

import future.keywords.in

default allow = false

allow {
    count(missing_tags) == 0
}

missing_tags[res.address] {
    some res in input.resource_changes
    res.mode == "managed"
    res.change.actions[_] in ["create", "update"]
    required_tags := {"Environment", "Owner", "CostCenter"}
    provided_tags := {tag | some tag, _ in res.change.after.tags}
    diff := required_tags - provided_tags
    count(diff) > 0
}
```

Buat file `hands-on/m02/live/production/main.tf`:

```hcl
resource "aws_s3_bucket" "workload_bucket" {
  bucket = "corp-data-processing-payload-${random_id.payload_suffix.hex}"

  tags = {
    Environment = "Production"
    Owner       = "DataEngineering"
    CostCenter  = "CC-DEPT-889"
  }
}

resource "random_id" "payload_suffix" {
  byte_length = 4
}
```

Buat file `hands-on/m02/live/production/terraform.tf` (gunakan bucket dari langkah 1):

```hcl
terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40.0"
    }
  }

  backend "s3" {
    # Ganti dengan output aktual dari Step 1
    bucket         = "<STATE_BUCKET_NAME>"
    key            = "live/production/storage.tfstate"
    region         = "ap-southeast-3"
    dynamodb_table = "iac-adv-prod-tflocks"
    encrypt        = true
  }
}

provider "aws" {
  region = "ap-southeast-3"
}
```

#### Langkah 3: Eksekusi Validasi Policy-as-Code & Deployment
Buat file runner bash di `hands-on/m02/scripts/run_plan_securely.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../live/production"

echo "==> 1. Initializing Terraform..."
terraform init

echo "==> 2. Generating Speculative Binary Plan..."
terraform plan -out=tfplan.bin

echo "==> 3. Transforming Plan to JSON..."
terraform show -json tfplan.bin > tfplan.json

echo "==> 4. Evaluating Open Policy Agent (OPA) Guardrails..."
VIOLATIONS=$(opa eval --data ../../policies/check_tags.rego \
                      --input tfplan.json \
                      "data.terraform.tags.missing_tags" \
                      --format raw)

if [ "$VIOLATIONS" != "[]" ]; then
    echo "❌ SECURITY CHECK FAILED: Ditemukan resource tanpa standard tags mandatory:"
    echo "$VIOLATIONS"
    exit 1
fi

echo "✅ All Policy-as-Code Validations Passed!"
echo "==> 5. Executing Production Apply..."
terraform apply tfplan.bin
```

Berikan execution privilege dan jalankan:
```bash
chmod +x hands-on/m02/scripts/run_plan_securely.sh
./hands-on/m02/scripts/run_plan_securely.sh
```

#### Langkah 4: Teardown Cleanup
```bash
# 1. Hancurkan resource workload production
cd hands-on/m02/live/production
terraform destroy -auto-approve

# 2. Hancurkan bootstrap state store
cd ../../backend-bootstrap
# Hapus s3 bucket objects versi lama terlebih dahulu bila diperlukan
aws s3 rm s3://$(terraform output -raw state_bucket_name) --recursive
terraform destroy -auto-approve
```

---

### 13. Exercise

#### Level: Easy
- **Tugas**: Tambahkan validasi pada modul `secure_network` untuk memastikan bahwa tag `CostCenter` harus diawali dengan prefix `CC-` menggunakan HCL variable validation condition.
- **Batasan**: Validasi harus memutus proses `terraform plan` secara dini pada sisi klien tanpa perlu memanggil API AWS.

#### Level: Medium
- **Tugas**: Tulis aturan OPA Rego baru (`policies/enforce_encryption.rego`) yang memvalidasi bahwa seluruh resource `aws_ebs_volume`, `aws_s3_bucket`, dan `aws_rds_cluster` memiliki konfigurasi enkripsi storage aktif (`encrypted == true`).
- **Batasan**: Aturan harus memberikan pesan kesalahan deskriptif yang mencantumkan nama address resource spesifik yang melanggar.

#### Level: Hard
- **Tugas**: Rancang pipeline deteksi drift otomatis menggunakan scheduled GitHub Actions yang mengeksekusi `terraform plan -detailed-exitcode`. Jika exit code bernilai `2` (terdapat drift), pipeline harus secara otomatis membuat GitHub Issue berlabel `incident:state-drift` lengkap dengan komparasi diff actual vs desired, serta memicu notifikasi JSON webhook ke endpoint SIEM.

---

### 14. Challenge

#### Skenario: Active-Active Zero-Trust Multi-Region Infrastructure Delivery Platform
Sebagai Lead Infrastructure Architect di entitas perbankan global, Anda ditugaskan membangun pipeline Continuous Delivery yang mengotomatisasi penyebaran topologi **Active-Active Cross-Region Infrastructure** (Region Primary: `ap-southeast-3` Jakarta, Region Disaster Recovery: `ap-southeast-1` Singapura).

#### Persyaratan Arsitektural:
1. **Dynamic Ephemeral Canary Environments**:
   Setiap kali Pull Request dibuat pada repositori arsitektur inti, pipeline harus mampu mendirikan *ephemeral VPC & microservices sandbox* dengan routing DNS route53 private terisolasi, menjalankan integrasi latency test, dan menghancurkannya secara otomatis setelah status check tuntas (*auto-teardown*).
2. **Policy Gates**:
   Pipeline wajib mengintegrasikan **AWS CloudFormation Guard** atau **OPA** yang memblokir secara deterministik:
   - Penggunaan Security Group dengan `cidr_blocks = ["0.0.0.0/0"]` pada port ingress sensitif (misal: 22, 3389, 5432, 1433).
   - Penyebaran resource tanpa alokasi customer-managed KMS key.
3. **Disaster Recovery Resiliency Test on State**:
   Rancang arsitektur penyimpanan remote backend yang mampu bertahan jika satu region AWS mengalami pemadaman total (*regional total outage*), memastikan proses delivery infrastruktur ke region survivable tetap dapat mengunci state dan membaca histori state secara konsisten tanpa kehilangan dependensi metadata.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Mengapa penggunaan atribut `LockID` bertipe String diwajibkan dalam skema tabel DynamoDB untuk Terraform backend?**
   - A. Sebagai index pencarian riwayat commit Git runner.
   - B. Sebagai partition key penjamin mutual exclusion operasi konkurensi apply.
   - C. Untuk menyimpan payload enkripsi KMS state file.
   - D. Sebagai penanda masa kedaluwarsa IAM short-lived session.

2. **Apa yang terjadi secara internal ketika parameter `-detailed-exitcode` diberikan pada eksekusi `terraform plan`?**
   - A. Menghasilkan dump file format protobuff.
   - B. Mengembalikan exit code 0 (tanpa perubahan), 1 (error fatal), atau 2 (ditemukan perbedaan delta state/drift).
   - C. Memaksa proses apply dieksekusi secara otomatis jika tidak ada error kompilasi graph.
   - D. Mengabaikan validasi dynamic block parsing.

3. **Klaim OIDC token mana yang digunakan oleh IAM Trust Policy untuk membatasi asumsi peran hanya pada branch `main` repositori tertentu?**
   - A. `aud`
   - B. `iss`
   - C. `sub`
   - D. `jti`

4. **Kapan kondisi destruktif *destroy-and-recreate* dipicu oleh engine Terraform saat proses apply?**
   - A. Saat terjadi modifikasi metadata tag resource.
   - B. Saat nilai atribut yang bersifat immutable pada resource AWS diubah pada configuration code.
   - C. Saat DynamoDB table mengalami read latency throttling.
   - D. Saat nilai variable timeout network dinaikkan.

5. **Apa fungsi utama dari pembuatan Directed Acyclic Graph (DAG) pada eksekusi IaC?**
   - A. Menghapus state file lokal yang usang.
   - B. Memetakan urutan operasi dependensi resource dan memfasilitasi eksekusi provisioning paralel non-blocking.
   - C. Melakukan kompresi payload JSON sebelum disimpan di S3.
   - D. Menghasilkan template CloudFormation secara translasi silang.

---

#### Bagian 2: Intermediate (5 Pertanyaan)
1. **Bagaimana cara menangani resource state yang tidak sengaja terhapus di AWS console (*actual drift*) tanpa menghancurkan resource lain yang bergantung padanya di dalam dependency graph?**
   - A. Menghapus seluruh direktori `.terraform` lalu menjalankan `init`.
   - B. Mengedit binary state file S3 secara manual menggunakan utility hex editor.
   - C. Menjalankan `terraform apply -refresh-only` untuk memperbarui state terhadap realita actual, kemudian menuliskan ulang resource block atau menghapusnya secara terkontrol.
   - D. Mengeksekusi `terraform state rm` pada seluruh resource root module.

2. **Dua engineer mengeksekusi pipeline secara bersamaan. Engineer A menjalankan `plan` dan Engineer B menjalankan `apply`. Mengapa Engineer A tidak terblokir oleh DynamoDB lock, sedangkan Engineer C yang mencoba `apply` terblokir?**
   - A. Parameter default `terraform plan` tidak mengakuisisi lock eksklusif write (hanya acquire temporary read lock jika dikonfigurasi).
   - B. DynamoDB backend mengizinkan concurrent multi-write secara default.
   - C. IAM permission Engineer A tidak memiliki akses ke DynamoDB.
   - D. S3 object lock secara otomatis menduplikasi path state ke versi branch baru.

3. **Perhatikan skenario konfigurasi: Modul A mengekspor `vpc_id` ke output. Modul B membaca `vpc_id` via `terraform_remote_state` data source. Apa kerugian utama pendekatan ini dibandingkan Terraform Data Source murni (`aws_vpc`)?**
   - A. Memperlambat throughput bandwidth upload S3.
   - B. Menghasilkan *tight coupling* level state file antar workspace dan potensi kebocoran akses jika tim Modul B memerlukan permission membaca seluruh isi state Modul A.
   - C. Menyebabkan IAM STS token langsung kedaluwarsa.
   - D. Tidak mendukung enkripsi KMS cross-account.

4. **Di dalam framework OPA (Open Policy Agent), apa format representasi artifact yang di-evaluasi untuk mencegah provisioning compute instance dengan tipe instance yang dilarang?**
   - A. Berkas mentah `.tf` sebelum parsing.
   - B. Berkas `.tfstate` histori versi sebelumnya.
   - C. Snapshot JSON representasi dari `terraform plan` output (`terraform show -json`).
   - D. Ekspor audit log CloudTrail runtime.

5. **Manakah konfigurasi Lifecycle Block yang paling aman untuk mencegah *database downtime* ketika parameter security group yang terikat pada instance AWS RDS diubah dan mengharuskan penggantian resource?**
   - A. `prevent_destroy = true`
   - B. `create_before_destroy = true`
   - C. `ignore_changes = [all]`
   - D. `replace_triggered_by = [aws_security_group.main.id]`

---

#### Bagian 3: Skenario Kasus Produksi (3 Kasus Kompleks)

##### Kasus 1: Insiden State Lock Deadlock Massal Pasca-Network Outage
- **Konteks**: Saat running apply untuk rollout 50 cluster EKS production, terjadi putus koneksi global antara GitHub Actions self-hosted runner pool dan AWS PrivateLink endpoint. Seluruh pipeline mati serentak (*abrupt SIGKILL*).
- **Insiden**: Pasca network normal, seluruh pipeline release hotfix terblokir dengan error `ConditionalCheckFailedException` pada DynamoDB lock table. Seorang junior engineer menyarankan untuk menghapus seluruh tabel DynamoDB backend tersebut secara langsung via AWS Console.
- **Pertanyaan**: Jelaskan mengapa usulan junior engineer tersebut merupakan pelanggaran prosedur operasi standar (SOP) tingkat kritikal, dan bagaimana runbook resmi penyelesaian masalah ini secara sistematis dan aman tanpa memicu risiko inkonsistensi state!

##### Kasus 2: Kebocoran Data Sensitif pada Pipeline Execution Output
- **Konteks**: Modul database men-generate password administrator acak menggunakan resource `random_password`. Output password tersebut diteruskan ke resource `aws_db_instance`.
- **Insiden**: Saat eksekusi pull request, output `terraform plan` tercetak pada console build log GitHub Actions dan diposting sebagai komentar publik PR oleh pipeline bot, mengakibatkan kredensial database terekspos ke seluruh organisasi.
- **Pertanyaan**: Mekanisme apa yang gagal diimplementasikan pada konfigurasi HCL tersebut? Sebutkan modifikasi sintaksis konkret yang harus diterapkan untuk membendung kebocoran kredensial ini, baik di level HCL module maupun pipeline stdout masking!

##### Kasus 3: OIDC Trust Policy Misconfiguration Vulnerability
- **Konteks**: Perusahaan menerapkan OIDC untuk autentikasi pipeline GitHub Actions ke AWS.
- **Insiden**: Tim Security menemukan bahwa developer dari repositori personal eksternal (`attacker-org/malicious-repo`) berhasil melakukan asumsi peran ke IAM Role deployment production AWS perusahaan dan berhasil menduplikasi isi S3 bucket rahasia.
- **Pertanyaan**: Teliti letak kerentanan pada IAM Trust Policy JSON berikut dan tuliskan versi perbaikan yang menutup celah eksploitasi tersebut secara definitif:
  ```json
  {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {
          "Federated": "arn:aws:iam::112233445566:oidc-provider/token.actions.githubusercontent.com"
        },
        "Action": "sts:AssumeRoleWithWebIdentity",
        "Condition": {
          "StringEquals": {
            "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
          }
        }
      }
    ]
  }
  ```

---

#### Kunci Jawaban & Panduan Solusi Evaluasi

##### Kunci Bagian 1: Basic
1. **B** - DynamoDB mengandalkan atomisitas Conditional Writes pada `LockID` untuk mencegah lebih dari satu proses modifikasi state dalam satu rentang waktu.
2. **B** - Exit code `2` menandakan plan berhasil dieksekusi dan terdapat diff infrastruktur, fundamental untuk automasi pipeline deteksi drift.
3. **C** - Klaim `sub` (*Subject*) membawa identitas lengkap repositori dan branch asal (`repo:<org>/<repo>:ref:<branch>`).
4. **B** - Modifikasi pada atribut yang didefinisikan AWS API sebagai non-updatable in-place mengharuskan engine membuat resource baru sebelum/setelah menghancurkan yang lama.
5. **B** - DAG memastikan Terraform mengetahui simpul independen yang aman dieksekusi secara konkuren sesuai thread pool parallelism.

##### Kunci Bagian 2: Intermediate
1. **C** - Operasi `-refresh-only` menyinkronkan state terhadap kondisi aktual tanpa mengeksekusi destructive actions terhadap resource lainnya.
2. **A** - Perintah `plan` secara default bersifat spekulatif dan tidak mengunci state DynamoDB secara eksklusif berdurasi panjang, sehingga tidak memblokir sesama reader.
3. **B** - `terraform_remote_state` mengekspos seluruh data state upstream (termasuk potensi data sensitif yang ada di modul lain) dan menciptakan kopling ketat antar workspace.
4. **C** - OPA mengevaluasi representasi JSON struktural yang dihasilkan melalui serialisasi `terraform show -json <plan_file>`.
5. **B** - `create_before_destroy = true` menjamin instance pengganti sudah berdiri dan sehat sebelum resource lama dihancurkan, meminimalkan jendela downtime.

##### Panduan Solusi Bagian 3: Skenario Kasus Produksi

- **Kasus 1**:
  - *Bahaya Menghapus Tabel DynamoDB*: Menghapus tabel DynamoDB menghilangkan sistem locking untuk *seluruh* project lain yang membagikan lock table tersebut. Selain itu, jika tabel dihapus saat ada apply lokal yang masih menggantung di background, state write collision dapat terjadi, yang berpotensi merusak (*corrupting*) format file JSON `.tfstate` di S3 secara permanen.
  - *Runbook Resmi*:
    1. Lakukan audit pada process monitoring pool runner untuk memastikan tidak ada PID Terraform yang masih hidup (*orphaned processes*).
    2. Identifikasi LockID spesifik dari failure log.
    3. Jalankan `terraform force-unlock <LOCK-ID>` menggunakan akun yang berhak.
    4. Jalankan `terraform plan -refresh-only` guna mengonfirmasi integritas state file terhadap API AWS sebelum membuka antrean deployment berikutnya.

- **Kasus 2**:
  - *Kegagalan Implementasi*: Atribut output tidak ditandai sebagai data sensitif, sehingga formatter CLI mengekspos nilainya secara plaintext ke stdout.
  - *Solusi HCL*: Tambahkan atribut `sensitive = true` pada output block terkait:
    ```hcl
    output "db_password" {
      value     = aws_db_instance.main.password
      sensitive = true
    }
    ```
  - *Solusi Pipeline*: Gunakan fitur secret masking runner (misal: GitHub Actions `echo "::add-mask::$DB_PASS"`), serta hindari mencetak berkas plan JSON mentah ke console logs PR tanpa filter sanitasi regex.

- **Kasus 3**:
  - *Letak Kerentanan*: Policy hanya memvalidasi klaim `aud` (Audience), yang berarti **semua repositori publik di seluruh GitHub** yang meminta token JWT untuk audience AWS STS valid akan diizinkan mengasumsikan role tersebut (*arbitrary GitHub repo takeover*).
  - *Versi Perbaikan Definitif*: Tambahkan validasi klaim `sub` atau `job_workflow_ref` yang secara eksplisit membatasi organisasi, nama repositori, dan environment/branch:
    ```json
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Principal": {
            "Federated": "arn:aws:iam::112233445566:oidc-provider/token.actions.githubusercontent.com"
          },
          "Action": "sts:AssumeRoleWithWebIdentity",
          "Condition": {
            "StringEquals": {
              "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
            },
            "StringLike": {
              "token.actions.githubusercontent.com:sub": "repo:enterprise-org/core-banking-infra:ref:refs/heads/main"
            }
          }
        }
      ]
    }
    ```

---

### 16. Summary
Modul ini telah mengupas tuntas arsitektur produksi dan implementasi lanjutan dari Continuous Delivery untuk Infrastructure as Code di ekosistem AWS:

1. **State Engine Internals**: Operasi deklaratif bertumpu pada resolusi graf berarah (DAG) dan locking terdistribusi untuk menjamin integritas state storage di S3 dan DynamoDB.
2. **Zero-Trust Identity**: Penggunaan IAM User Access Keys statis dieliminasi secara total, digantikan oleh federasi identitas OIDC berbasis STS AssumeRole scoped JWT validation.
3. **Guardrails & Governance**: Policy-as-Code (OPA/Guard) bertindak sebagai gerbang deterministik yang mengevaluasi kepatuhan arsitektur sebelum fase mutasi actual state berjalan.
4. **Resilience & Drift**: Menghadapi tantangan skala enterprise memerlukan pemecahan boundary state (*micro-state architecture*) serta sistem pendeteksi drift otomatis berbasis event.

Implementasi standar ini memastikan infrastruktur enterprise dapat dideploy secara cepat, aman, terprediksi, dan patuh terhadap regulasi industri tanpa intervensi manual pada AWS Console.