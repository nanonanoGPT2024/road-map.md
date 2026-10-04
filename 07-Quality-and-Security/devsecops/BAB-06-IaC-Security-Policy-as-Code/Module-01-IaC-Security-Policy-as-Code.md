# Bab 06 Module 01: Infrastructure as Code (IaC) Security & Policy-as-Code

---

### 1. Identitas Modul
* **Track**: DevSecOps
* **Kategori**: 07-Quality-and-Security
* **Kode Modul**: DSO-07-06-01
* **Tingkat Kesulitan**: Advanced
* **Prasyarat**: 
  * Pemahaman mendalam mengenai deklarasi infrastruktur menggunakan HashiCorp Configuration Language (HCL/Terraform) dan Kubernetes Helm Charts.
  * Kemahiran operasional pipeline CI/CD (GitHub Actions, GitLab CI, atau Jenkins).
  * Pemahaman dasar arsitektur Cloud IAM, Networking (Security Groups, VPC), dan Public Cloud Storage (AWS S3, GCP Cloud Storage, Azure Blob).
* **Estimasi Waktu Penyelesaian**: 180 Menit

---

### 2. Learning Objectives
Setelah menyelesaikan modul ini, peserta didik mampu:
* **LO-01**: Mengidentifikasi celah keamanan sintaksis dan semantik pada template Terraform dan Helm charts menggunakan analisis statis berbasis Abstract Syntax Tree (AST).
* **LO-02**: Membedakan arsitektur dan mekanisme evaluasi antara Checkov, TFSec (Trivy IaC), dan KICS dalam pipeline deteksi kerentanan.
* **LO-03**: Merancang dan mengimplementasikan kebijakan Policy-as-Code deklaratif menggunakan Open Policy Agent (OPA) dan bahasa Rego.
* **LO-04**: Mengotomatisasi validasi kepatuhan infrastruktur terhadap standar CIS (Center for Internet Security) Benchmarks sebelum provisi runtime.
* **LO-05**: Mengintegrasikan gerbang keamanan IaC (Quality Gates) ke dalam pull-request workflow untuk memblokir infrastruktur berisiko tinggi.
* **LO-06**: Menganalisis batasan evaluasi statis pada konfigurasi dinamis (misalnya `locals`, fungsi bawaan Terraform, dan variabel tak terdefinisi).
* **LO-07**: Mengonfigurasi reporting berbasis OASIS Static Analysis Results Interchange Format (SARIF) untuk agregasi temuan keamanan di tingkat enterprise.
* **LO-08**: Mengaudit dan mengevaluasi konfigurasi infrastruktur multi-lingkungan guna mengeliminasi security drift dan konfigurasi izin berlebih (*over-privileged roles*).

---

### 3. Concept Map & Architecture Diagram

```
+-----------------------------------------------------------------------------------+
|                           DEVELOPER / LOCAL WORKSTATION                           |
|  +--------------------+       Pre-commit Hook        +-------------------------+  |
|  | Terraform / Helm   | ---------------------------> | Local Linters & Scanners|  |
|  | Source Code        |                              | (TFLint, TFSec, Checkov)|  |
|  +--------------------+                              +-------------------------+  |
+-----------------------------------------------------------------------------------+
                                    | (git push)
                                    v
+-----------------------------------------------------------------------------------+
|                              CI/CD PIPELINE GATEWAY                               |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | STEP 1: AST Extraction & Parsing Engine (HCL/YAML -> Unified JSON AST)      |  |
|  +-----------------------------------------------------------------------------+  |
|                                         |                                         |
|                                         v                                         |
|  +-----------------------------------------------------------------------------+  |
|  | STEP 2: Multi-Engine Static IaC Security Analysis                           |  |
|  |   - Checkov: Graph-based policy analysis & framework checks                 |  |
|  |   - Trivy/TFSec: Fast structural scanning & CVE correlation                 |  |
|  |   - KICS: AST cross-representation against CIS Benchmarks                   |  |
|  +-----------------------------------------------------------------------------+  |
|                                         |                                         |
|                                         v                                         |
|  +-----------------------------------------------------------------------------+  |
|  | STEP 3: Decoupled Policy-as-Code Evaluation                                 |  |
|  |   - Open Policy Agent (OPA) Engine                                          |  |
|  |   - Input: terraform.json / helm-manifest.json                              |  |
|  |   - Rules: Organization-defined Rego Policies                               |  |
|  +-----------------------------------------------------------------------------+  |
|                                         |                                         |
|                 +-----------------------+-----------------------+                 |
|                 | Fail (Critical Flaw)                          | Pass            |
|                 v                                               v                 |
|  +-----------------------------+               +-------------------------------+  |
|  | SARIF Generation & Upload   |               | Terraform Plan / Helm Dry-Run |  |
|  | PR Annotation & CI Exit 1   |               | Approval Gate -> Provision    |  |
|  +-----------------------------+               +-------------------------------+  |
+-----------------------------------------------------------------------------------+
                                                                  |
                                                                  v
+-----------------------------------------------------------------------------------+
|                        CLOUD RUNTIME / KUBERNETES CLUSTER                         |
|  +-----------------------------------------------------------------------------+  |
|  | Pre-flight Admission Control: OPA Gatekeeper / Kyverno (Fail-safe final check)|
|  +-----------------------------------------------------------------------------+  |
|  | Validated Infrastructure Deployed (Zero Critical Drift / Fully Encrypted)  |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

### 4. Mengapa Ini Penting (Why & Business / Security Impact)
Infrastruktur modern yang dikelola melalui IaC memindahkan seluruh topologi jaringan, boundary perimeter, kebijakan akses identitas (IAM), dan enkripsi data dari konfigurasi konsol manual ke dalam repositori kode sumber. Karakteristik ini membawa implikasi keamanan:
* **Amplifikasi Kesalahan Konfigurasi**: Satu baris kesalahan pada modul Terraform dasar (seperti `0.0.0.0/0` pada ingress security group basis data atau atribut `public_read` pada S3 bucket) secara otomatis tereplikasi ke ratusan resource di seluruh staging dan production environment.
* **Finansial dan Regulasi**: Pelanggaran terhadap standar kepatuhan industri (PCI-DSS 4.0, HIPAA, SOC 2 Type II, ISO/IEC 27001) yang berakar dari kesalahan konfigurasi cloud publik dapat mengakibatkan denda regulasi jutaan dolar, penangguhan lisensi transaksi, dan kebocoran data terstruktur.
* **Efisiensi Shift-Left**: Biaya remediasi kerentanan pada fase runtime (post-provisioning) mencapai 30 hingga 60 kali lebih tinggi dibandingkan mendeteksinya pada fase *pull request*. Shift-Left IaC Validation memastikan infrastruktur yang cacat digugurkan pada tahap CI sebelum API provider cloud mengalokasikan resource tersebut.

---

### 5. Apa Itu Konsep (What & Definisi Formal Mendalam)
* **Static Analysis for IaC**: Metode evaluasi non-eksekusi terhadap file deklarasi infrastruktur (seperti Terraform HCL, Kubernetes Manifests, Helm Charts, CloudFormation) untuk mendeteksi deviasi arsitektur, anti-patterns, dan celah keamanan menggunakan pemetaan Abstract Syntax Tree (AST).
* **Policy-as-Code (PaC)**: Paradigma penulisan, pengelolaan, dan penegakan aturan kepatuhan keamanan menggunakan bahasa deklaratif yang dapat dikontrol versinya (*version-controlled*). Logika kebijakan terpisah secara independen dari logika implementasi infrastruktur.
* **Open Policy Agent (OPA) & Rego**: OPA adalah *general-purpose policy engine* open-source berkinerja tinggi. OPA menggunakan bahasa deklaratif bernama **Rego** untuk mengevaluasi data masukan berbasis JSON terhadap sekumpulan aturan bisnis dan keamanan, menghasilkan keputusan deterministik (misalnya `allow` vs `deny`).
* **CIS Benchmarks Automation**: Mekanisme penegakan otomatis dari panduan konsensus global yang diterbitkan oleh Center for Internet Security untuk mengonfigurasi komponen sistem, sistem operasi, container, dan platform cloud secara aman.

---

### 6. Bagaimana Cara Kerja (How & Mekanika Internal Arsitektur)

#### 6.1 Fase Parsing dan Pembentukan AST
Pemindai statis (seperti Checkov, TFSec, atau KICS) tidak mengevaluasi berkas sebagai teks mentah (*raw string matching*). Mekanisme internalnya meliputi:
1. **Lexical Analysis (Scanning/Tokenizing)**: Membaca berkas `.tf` atau `.yaml` dan memecahnya menjadi token leksikal (keywords, identifiers, operators, literals).
2. **Grammar Parsing**: Menyusun urutan token menjadi Abstract Syntax Tree (AST). Pada Terraform, pustaka parser HCL2 mengonversi blok `resource`, `variable`, dan `locals` menjadi struktur pohon hierarkis.
3. **Graph Construction**: Scanner mutakhir (khususnya Checkov) membangun *Directed Acyclic Graph* (DAG) dari dependensi resource untuk menyelesaikan referensi silang atribut (misalnya, mereferensikan subnet ID dari resource VPC ke resource Network Interface).

#### 6.2 Evaluasi Kebijakan OPA/Rego
1. Perintah `terraform show -json tfplan.binary > tfplan.json` mengekspor konfigurasi state yang diusulkan ke payload JSON terstandardisasi.
2. OPA memuat file kebijakan (`.rego`) yang mendefinisikan batasan invariant.
3. File `tfplan.json` dipasok sebagai dokumen `input` ke OPA runtime.
4. OPA mengevaluasi aturan komparasi secara deklaratif tanpa efek samping (*side-effect free*). Jika terjadi evaluasi yang memenuhi predikat pelanggaran (*violation condition*), OPA menghasilkan output array dokumen berupa daftar pelanggaran beserta pesan remediasinya.
5. CI/CD engine memeriksa nilai kembalian OPA; jika array pelanggaran tidak kosong, pipeline dihentikan dengan *non-zero exit code* (`exit 1`).

---

### 7. Perbandingan Paradigma / Taksonomi Matriks

| Parameter Evaluasi | Checkov (Bridgecrew/Palo Alto) | TFSec / Trivy (Aqua Security) | KICS (Checkmarx) | OPA / Conftest |
| :--- | :--- | :--- | :--- | :--- |
| **Bahasa Engine Inti** | Python | Go | Go | Go (Rego Language) |
| **Model Analisis** | Graph-based AST, Deep Context Tracking | AST Parsing & Pattern Match | Multi-representation AST | Declarative Logic Query Engine |
| **Kecepatan Eksekusi** | Sedang (Tinggi pada repo skala besar) | Sangat Cepat | Cepat | Cepat |
| **Definisi Custom Rule** | Python atau YAML | Custom Go Plugins atau YAML | SQL-like query (JSONPath/Rego) | Rego Native Policy Query |
| **Cakupan Kerangka Kerja** | Terraform, Helm, K8s, ARM, CloudFormation, Serverless | Terraform, Helm, Dockerfile, K8s (via Trivy) | Terraform, Helm, K8s, Ansible, Docker, OpenAPI | Format data arbitrer apa pun (JSON/YAML) |
| **Integrasi Ekosistem** | CLI, SARIF, Bridgecrew Cloud Platform | CLI, SARIF, Trivy Ecosystem | CLI, SARIF, DefectDojo | CLI, Gatekeeper, Envoy Proxy |

---

### 8. Analisis Mendalam Attack Surface & Vector Matrix

| Target Vektor | Mekanisme Kerentanan IaC | Dampak Eksploitasi Lapangan | Kontrol Deteksi Statis | Mitigasi Policy-as-Code |
| :--- | :--- | :--- | :--- | :--- |
| **Object Storage (S3 / GCS)** | Variabel `acl = "public-read"` atau penonaktifan blok `public_access_block`. | Data Exfiltration skala masif, *ransomware*, kebocoran kredensial rahasia. | Checkov CKV_AWS_20, TFSec AWS002, KICS Storage Bucket Public Read. | Rego invariant: Block if `aws_s3_bucket_public_access_block` != true. |
| **IAM Privileges** | Konfigurasi aksi wildcard: `Action = ["*"]` dan `Resource = ["*"]`. | *Privilege escalation*, kompromi lateral, pengambilalihan akun cloud (*tenant takeover*). | Checkov CKV_AWS_1, TFSec AWS099, KICS IAM Action Wildcard. | Rego filter: Parse `statement.Action`, tolak jika terdapat nilai string wildcard `*`. |
| **Database Encryption** | Variabel `storage_encrypted = false` atau ketiadaan kunci KMS kustom. | Kebocoran data at-rest jika physical storage disusupi atau replikasi snapshot tidak sah. | Checkov CKV_AWS_16, TFSec AWS089. | Evaluasi atribut `storage_encrypted == true` dan `kms_key_id` bukan bawaan provider. |
| **Perimeter Network (SG)** | Ingress rule: `cidr_blocks = ["0.0.0.0/0"]` pada port administratif (SSH: 22, RDP: 3389). | Serangan *brute-force* langsung, eksploitasi zero-day RCE terhadap host internal. | Checkov CKV_AWS_24, TFSec AWS008. | Evaluasi CIDR: Tolak `0.0.0.0/0` jika port tujuan terdaftar pada *sensitive port array*. |

---

### 9. Code Example Sederhana (Minimal & Clear)

#### 9.1 Skenario Rentan: Konfigurasi AWS S3 Bucket Insecure (`main.tf`)
```hcl
# rentan: Tidak ada proteksi public access dan tidak ada enkripsi sisi server (SSE)
resource "aws_s3_bucket" "financial_data" {
  bucket = "corp-financial-records-prod"
}

resource "aws_s3_bucket_acl" "financial_data_acl" {
  bucket = aws_s3_bucket.financial_data.id
  acl    = "public-read" # Pelanggaran keamanan kritis
}
```

#### 9.2 Eksekusi Pemindaian Checkov CLI
```bash
# Menjalankan scanning IaC lokal hanya pada resource S3
checkov -f main.tf --framework terraform --check CKV_AWS_20,CKV_AWS_19
```

#### 9.3 Output Evaluasi (Kegagalan Dideteksi)
```
Check: CKV_AWS_20: "S3 Bucket has an ACL defined which allows public READ access."
	FAILED for resource: aws_s3_bucket_acl.financial_data_acl
	File: /main.tf:6-9
	Guide: https://docs.bridgecrew.io/docs/s3_1-acl-read-permissions-everyone

		6 | resource "aws_s3_bucket_acl" "financial_data_acl" {
		7 |   bucket = aws_s3_bucket.financial_data.id
		8 |   acl    = "public-read"
		9 | }
```

---

### 10. Code Example Lanjutan (Production-Ready)

#### 10.1 Konfigurasi Terraform yang Telah Dikeraskan (`s3_hardened.tf`)
```hcl
resource "aws_kms_key" "s3_encryption_key" {
  description             = "Dedicated KMS Key for Financial Records Storage"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_s3_bucket" "financial_data" {
  bucket        = "corp-financial-records-prod"
  force_destroy = false

  tags = {
    Environment        = "Production"
    DataClassification = "Restricted"
    ManagedBy          = "Terraform"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "financial_data_crypto" {
  bucket = aws_s3_bucket.financial_data.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.s3_encryption_key.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "financial_data_isolation" {
  bucket = aws_s3_bucket.financial_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "financial_data_versioning" {
  bucket = aws_s3_bucket.financial_data.id
  versioning_configuration {
    status = "Enabled"
  }
}
```

#### 10.2 Custom OPA Rego Policy: Penegakan Standardisasi S3 & Enkripsi KMS (`s3_enforcement.rego`)
```rego
package enterprise.cloud.storage

import future.keywords.in

default allow = false

# Ambil seluruh alokasi resource dari plan Terraform
resource_changes := input.resource_changes

# Kumpulan aturan deny yang mengumpulkan seluruh temuan kegagalan
deny[msg] {
    some resource in resource_changes
    resource.type == "aws_s3_bucket"
    resource.change.actions[_] in ["create", "update"]
    
    # Validasi penegakan tagging wajib
    required_tags := {"Environment", "DataClassification", "ManagedBy"}
    provided_tags := {tag | resource.change.after.tags[tag]}
    missing_tags := required_tags - provided_tags
    count(missing_tags) > 0
    
    msg := sprintf("Resource '%v' gagal validasi: Label wajib berikut tidak ditemukan: %v", [resource.address, missing_tags])
}

deny[msg] {
    some resource in resource_changes
    resource.type == "aws_s3_bucket_public_access_block"
    resource.change.actions[_] in ["create", "update"]
    
    config := resource.change.after
    not (config.block_public_acls == true and
         config.block_public_policy == true and
         config.ignore_public_acls == true and
         config.restrict_public_buckets == true)
         
    msg := sprintf("Resource '%v' melanggar kebijakan CIS AWS Benchmark. Seluruh public access block flags harus bernilai true.", [resource.address])
}

# Pipeline hanya lolos (allow) jika tidak ada satu pun evaluasi deny yang terpicu
allow {
    count(deny) == 0
}
```

#### 10.3 Pipeline Integrasi GitHub Actions Berbasis SARIF dan Conftest (`.github/workflows/iac-sec.yml`)
```yaml
name: "IaC Security & Policy Validation"

on:
  pull_request:
    branches: [ "main" ]

jobs:
  iac-validation:
    name: "Perform Static Analysis and PaC Gate"
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
      pull-requests: write

    steps:
      - name: "Checkout Source Code"
        uses: actions/checkout@v4

      - name: "Setup Terraform Engine"
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.7.5"

      - name: "Install Conftest"
        run: |
          CONFTEST_VERSION=0.49.1
          curl -LO "https://github.com/open-policy-agent/conftest/releases/download/v${CONFTEST_VERSION}/conftest_${CONFTEST_VERSION}_Linux_x86_64.tar.gz"
          tar xzf conftest_${CONFTEST_VERSION}_Linux_x86_64.tar.gz
          sudo mv conftest /usr/local/bin/

      - name: "Generate Terraform Plan Output"
        run: |
          terraform init -backend=false
          terraform plan -out=tfplan.binary
          terraform show -json tfplan.binary > tfplan.json

      - name: "Execute Checkov Static Analysis (SARIF Export)"
        uses: bridgecrewio/checkov-action@master
        with:
          framework: terraform
          output_format: sarif
          output_file_path: results.sarif
          soft_fail: false # Hard gate: batalkan build jika pelanggaran kritis ditemukan

      - name: "Publish SARIF to GitHub Security Center"
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: results.sarif

      - name: "Execute Custom Policy-as-Code via Conftest (OPA)"
        run: |
          conftest test tfplan.json \
            --policy ./policies \
            --namespace enterprise.cloud.storage \
            --fail-on-warn
```

---

### 11. Diagram Alur Serangan & Mitigasi

```
+----------------------------------------------------------------------------------------+
|                                ALUR SERANGAN (UNPROTECTED)                             |
|                                                                                        |
| Dev Commit:          PR Disetujui:          Runtime Provisi:        Eksploitasi:       |
| Ingress 0.0.0.0/0    Tanpa scanning statis, Permintaan ke Cloud     Penyerang memindai |
| Port 22 (SSH) pada   langsung di-merge ke   API membuat SG terbuka  port 22, brute     |
| Security Group       trunk branch.          ke Internet.            force SSH, RCE.    |
|        |                   |                       |                       |           |
|        v                   v                       v                       v           |
|  [HCL: 0.0.0.0/0] ===> [Git Merge] ==========> [AWS EC2 Instance] ===> [DATA BREACH]  |
+----------------------------------------------------------------------------------------+
                                            VS
+----------------------------------------------------------------------------------------+
|                               ALUR MITIGASI (DEVSECOPS GATE)                           |
|                                                                                        |
| Dev Commit:          Pipeline CI:           Pipeline Evaluasi OPA:  Hasil Remediasi:   |
| Ingress 0.0.0.0/0    Checkov / TFSec parsing Rego mendeteksi        PR Diblokir;       |
| Port 22 (SSH) pada   HCL ke AST; pola       pelanggaran invariant.  Developer dipaksa  |
| Security Group       insecure tertangkap.   Exit Code 1.            memakai Bastion/SSM|
|        |                   |                       |                       |           |
|        v                   v                       v                       v           |
|  [HCL: 0.0.0.0/0] ===> [AST Parsing] ========> [OPA Invariant Reject]==> [BUILD HALTED]|
|                                                                    (Cloud Tetap Aman)  |
+----------------------------------------------------------------------------------------+
```

---

### 12. Trade-offs & Security vs Usability / Performance

* **Kecepatan Pipeline vs Kedalaman Analisis Graf**:
  * *AST Parsing Murni (Trivy/TFSec)*: Berjalan dalam hitungan detik karena tidak membangun dependensi antar-berkas yang kompleks. Namun, berisiko mengalami *false negatives* saat variabel dievaluasi silang antar modul.
  * *Deep-Graph Context Engines (Checkov/KICS)*: Mengonsumsi CPU dan memori signifikan untuk memetakan referensi dependensi kompleks. Memperlambat durasi build PR secara proporsional dengan besarnya basis kode, tetapi memberikan analisis semantik akurat.
* **Strict Enforcement (Hard Gate) vs Developer Velocity**:
  * Penerapan `soft_fail: false` memblokir penggabungan kode secara absolut saat aturan terlanggar. Hal ini menjamin keamanan (*zero tolerance*), tetapi dapat memicu gesekan operasional (*engineering fatigue*) jika aturan internal menghasilkan *false positive*.
  * Solusi seimbang: Implementasikan mekanisme *grace period* dengan menandai *warning* pada temuan berlevel *Medium/Low*, dan menerapkan *hard-fail block* hanya pada temuan berlevel *High* dan *Critical* (misalnya pembukaan port publik dan bucket tanpa enkripsi).

---

### 13. Edge Cases & Complex Failure Modes

1. **Resolusi Dynamic Values & Functions**:
   Evaluasi statis tidak mengeksekusi fungsi runtime provider cloud (seperti data source `data.aws_iam_policy_document` yang bergantung pada akun remote atau eksekusi fungsi bawaan HCL `templatefile()`, `cidrsubnet()`). Jika nilai konfigurasi dipasok secara eksternal melalui variabel environment (`TF_VAR_`), pemindai statis dapat melewatkan celah keamanan (*undetected vulnerability*).
2. **Helm Template Rendering Discrepancies**:
   Memindai *raw Helm charts* langsung sering kali menghasilkan temuan bias atau terlewat. Analisis harus dilakukan terhadap manifest akhir yang telah dirender menggunakan `helm template . -f values.yaml`, bukan hanya pada berkas `templates/*.yaml` mentah yang masih mengandung kontrol kondisional Go template (`{{- if .Values.enabled }}`).
3. **Multi-layer Inline Suppression Hijacking**:
   Pengembang dapat mencoba melewati validasi menggunakan komentar supresi inline, seperti `#checkov:skip=CKV_AWS_20:Temporary exception`. Tanpa audit ketat terhadap supresi ini di level PaC, developer dapat secara diam-diam memasukkan konfigurasi yang rentan.

---

### 14. Anti-Patterns & Common Vulnerabilities

* **Anti-Pattern 1: "Global Soft-Fail"**
  * *Problem*: Mengaktifkan bendera `--soft-fail` pada Checkov/KICS di pipeline produksi agar pipeline "selalu hijau" (status exit code selalu 0).
  * *Koreksi*: Pisahkan profil kepatuhan; jalankan *fail-on-critical* untuk pipeline utama, alokasikan *soft-fail* hanya pada *experimental sandbox modules*.
* **Anti-Pattern 2: Evaluasi HCL Mentah Tanpa Terraform Plan Analysis**
  * *Problem*: Hanya memindai berkas `.tf` statis tanpa menghasilkan output `terraform plan` berformat JSON. Konfigurasi warisan (*inheritance*), modul pihak ketiga (`registry.terraform.io`), dan *overridden variables* tidak terekspos secara nyata.
  * *Koreksi*: Pasok file rencana biner yang dikonversi (`terraform show -json`) ke dalam OPA atau pemindai statis untuk mengevaluasi *post-expansion state*.
* **Anti-Pattern 3: Hardcoded Inline Secrets pada File Template**
  * *Problem*: Mengabaikan penanganan secret dengan mendeklarasikannya di blok resource default (misalnya `password = "Admin123!"`).
  * *Koreksi*: Gunakan Secret Stores (AWS Secrets Manager, HashiCorp Vault) dan enforce deteksi entropy rahasia via scanner IaC sebelum commit terjadi.

---

### 15. Best Practices & Enterprise Remediation Guide

1. **Implementasi Pre-commit Hooks Terpusat**:
   Gunakan framework `pre-commit` di workstation lokal developer untuk mengeksekusi pemeriksaan ringan (seperti `tflint`, `tfsec`) guna mendeteksi cacat sintaksis sebelum kode di-push ke remote origin.
2. **Strukturisasi Kebijakan Modular (Separation of Concerns)**:
   Pisahkan repositori kebijakan keamanan OPA/Rego dari repositori infrastruktur. Kelola kebijakan sebagai artefak versi terpusat yang diunduh saat eksekusi pipeline CI.
3. **Standarisasi Baseline CIS Benchmark**:
   Gunakan aturan berbasis ID resmi CIS (misalnya CIS AWS Foundations Benchmark v3.0.0). Setiap penolakan oleh pipeline harus menyertakan link dokumentasi internal mengenai cara remediasi yang sah.
4. **Audit Terhadap Komentar Supresi (Suppression Governance)**:
   Terapkan aturan meta-kebijakan yang menolak setiap Pull Request yang menyertakan komentar supresi keamanan, kecuali jika PR tersebut menyertakan link tiket persetujuan resmi dari Security Architect.

---

### 16. Hands-on Lab Step-by-Step

#### Skenario Lab
Anda ditugaskan mengamankan modul provisi Azure Virtual Machine dan Network Security Group (NSG) yang secara keliru mengizinkan port RDP (3389) terbuka ke seluruh internet. Anda akan memasang alat scanner, memicu kegagalan, dan menyusun rule Rego untuk memblokirnya.

#### Langkah 1: Inisialisasi Workspace dan Berkas Rentan
Buat direktori baru dan buat berkas `network.tf`:
```bash
mkdir -p ~/iac-security-lab/policies && cd ~/iac-security-lab

cat << 'EOF' > network.tf
provider "azurerm" {
  features {}
}

resource "azurerm_network_security_group" "bad_nsg" {
  name                = "nsg-production-app"
  location            = "eastus"
  resource_group_name = "rg-production"

  security_rule {
    name                       = "Insecure_RDP_Rule"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "3389"
    source_address_prefix      = "0.0.0.0/0"
    destination_address_prefix = "*"
  }
}
EOF
```

#### Langkah 2: Pindai dengan Trivy / TFSec
Jalankan scanning statis menggunakan container runtime Docker:
```bash
docker run --rm -v $(pwd):/workspace -w /workspace aquasec/trivy:latest config .
```
*Ekspektasi Output*: Trivy mendeteksi kerentanan kritis: Rule `Insecure_RDP_Rule` mengizinkan akses RDP publik (`source_address_prefix: 0.0.0.0/0`), memicu referensi ID `AVD-AZU-0047`.

#### Langkah 3: Susun Aturan Custom Policy-as-Code (Rego)
Buat file `policies/azure_nsg_defense.rego`:
```rego
package enterprise.azure.network

import future.keywords.in

default allow = false

# Identifikasi rule NSG inbound yang mengizinkan port sensitif
sensitive_ports := ["3389", "22", "445"]

deny[msg] {
    resource := input.azurerm_network_security_group[_]
    rule := resource.security_rule[_]
    
    rule.direction == "Inbound"
    rule.access == "Allow"
    rule.source_address_prefix == "0.0.0.0/0"
    rule.destination_port_range in sensitive_ports
    
    msg := sprintf("PELANGGARAN KRITIS: Rule '%v' pada NSG '%v' mengizinkan port sensitif %v terbuka ke 0.0.0.0/0", 
                   [rule.name, resource._hcl_meta.module_offset, rule.destination_port_range])
}

allow {
    count(deny) == 0
}
```

#### Langkah 4: Evaluasi Kebijakan Menggunakan Conftest
Instal Conftest atau jalankan via Docker untuk mengevaluasi konfigurasi:
```bash
docker run --rm -v $(pwd):/workspace -w /workspace openpolicyagent/conftest:latest test network.tf \
  -p policies/ \
  --namespace enterprise.azure.network
```

*Ekspektasi Output*:
```
FAIL - network.tf - enterprise.azure.network - PELANGGARAN KRITIS: Rule 'Insecure_RDP_Rule' pada NSG '0' mengizinkan port sensitif 3389 terbuka ke 0.0.0.0/0

1 test, 0 passed, 0 warnings, 1 failure, 0 exceptions
```

#### Langkah 5: Remediasi Konfigurasi HCL
Ubah nilai `source_address_prefix` pada file `network.tf` dari `0.0.0.0/0` menjadi IP korporat tepercaya (misalnya `10.200.0.0/24`):
```bash
sed -i 's/"0.0.0.0\/0"/"10.200.0.0\/24"/g' network.tf
```

#### Langkah 6: Verifikasi Hasil Ulang
Jalankan kembali evaluasi Conftest:
```bash
docker run --rm -v $(pwd):/workspace -w /workspace openpolicyagent/conftest:latest test network.tf \
  -p policies/ \
  --namespace enterprise.azure.network
```
*Ekspektasi Output*:
```
1 test, 1 passed, 0 warnings, 0 failures, 0 exceptions
```

---

### 17. Real-world Case Study & Incident Analysis Enterprise

#### 17.1 Deskripsi Insiden
Sebuah institusi perbankan regional memprovisikan kluster Elasticsearch publik yang dikelola modul Terraform bersama (*shared Terraform module*). Modul tersebut secara default mendeklarasikan ingress Security Group dengan izin `0.0.0.0/0` pada port TCP 9200 untuk mempermudah validasi staging. 

Ketika modul ini digunakan kembali oleh tim produk baru pada lingkungan produksi tanpa menimpa (*override*) variabel port security group, sistem monitoring internal gagal mendeteksinya karena pipeline CI/CD hanya memeriksa apakah konfigurasi Terraform memiliki format sintaks yang valid (`terraform validate`).

#### 17.2 Analisis Akar Masalah (Root Cause Analysis)
1. **Kegagalan Validasi Semantik**: `terraform validate` hanya memvalidasi konsistensi internal tipe data sintaks HCL, bukan semantik keamanan atribut.
2. **Ketiadaan Engine Policy-as-Code**: Tidak terdapat quality-gate yang melarang *unrestricted ingress* ke port database operasional non-publik.
3. **Konfigurasi Default Tidak Aman (Insecure Default)**: Modul mendefinisikan fallback nilai default variabel yang memperbolehkan eksposur publik jika tidak didefinisikan secara eksplisit oleh konsumen modul.

#### 17.3 Tindakan Pencegahan dan Remediasi
* Modul publik dirombak untuk menghapus seluruh nilai default permisif; variabel `allowed_ingress_cidrs` dibuat berstatus *mandatory* (`nullable = false`).
* Checkov diintegrasikan ke dalam seluruh template GitHub Actions repositori organisasi dengan kebijakan penolakan otomatis (fail pipeline) untuk rule `CKV_AWS_24` (Open ingress port 9200/Elasticsearch).
* Seluruh state produksi diinspeksi secara dinamis untuk mendeteksi *drift* menggunakan KICS.

---

### 18. Quiz Pemahaman & Challenge

#### Evaluasi Konseptual
1. Mengapa eksekusi `terraform validate` saja tidak mencukupi untuk menjamin keamanan template infrastruktur?
   * *Jawaban*: `terraform validate` hanya melakukan verifikasi sintaksis HCL dan integritas tipe data (misal: memeriksa apakah string diberikan ke atribut yang meminta string). Perintah tersebut tidak mengevaluasi postur keamanan semantik objek (seperti keterbukaan port, ketiadaan enkripsi disk, atau cakupan hak akses IAM).
2. Apa keuntungan mendasar menggunakan representasi Directed Acyclic Graph (DAG) pada Checkov dibandingkan pembacaan pola regex/AST sederhana?
   * *Jawaban*: AST murni hanya merepresentasikan satu node blok resource secara terisolasi. Pendekatan DAG mampu menelusuri hubungan referensial silang kompleks, seperti resource `aws_security_group_rule` yang dibuat terpisah dari resource induk `aws_security_group`, sehingga mendeteksi pelanggaran yang terpecah di berbagai berkas atau modul.
3. Bagaimana Open Policy Agent (OPA) memperlakukan variabel yang tidak terdefinisi (*undefined*) selama proses kueri Rego berjalan?
   * *Jawaban*: Dalam Rego, jika sebuah ekspresi merujuk pada dokumen atau variabel yang tidak ada/tidak terdefinisi, ekspresi tersebut dievaluasi sebagai *undefined*, bukan melempar exception fatal (*null-pointer*). Kondisi yang mengevaluasi ekspresi *undefined* tersebut otomatis dianggap salah (*false*), yang merupakan bagian dari mekanisme safety deklaratif Rego.
4. Mengapa lebih disarankan menjalankan validasi Policy-as-Code terhadap file JSON output `terraform plan` dibandingkan terhadap file `.tf` mentah?
   * *Jawaban*: Output `terraform plan` JSON telah merefleksikan resolusi variabel, penggabungan modul dependensi eksternal, perhitungan ekspresi kondisional (operator ternary), dan pemetaan state yang sesungguhnya akan diterapkan ke runtime cloud provider.
5. Sebutkan format interchange standar internasional berbasis JSON yang digunakan pemindai IaC modern agar temuan dapat dibaca terpusat di dashboard SIEM atau GitHub Advanced Security!
   * *Jawaban*: SARIF (Static Analysis Results Interchange Format), sebuah standar OASIS untuk mendefinisikan format output alat analisis statis.

#### Practical Challenge
**Misi**: Susun sebuah policy Rego (`policies/helm_security.rego`) yang mengevaluasi manifest hasil render Helm Chart Kubernetes (`manifest.json`). Kebijakan Anda harus:
1. Memeriksa semua resource yang memiliki `kind == "Deployment"`.
2. Menghasilkan pesan `deny` jika terdapat container di dalam `spec.template.spec.containers` yang:
   * Menetapkan `securityContext.privileged` bernilai `true`.
   * Membuka atribut `securityContext.runAsRoot` bernilai `true`.
   * Tidak mendefinisikan blok batas sumber daya memori (`resources.limits.memory`).
3. Kebijakan harus mengembalikan daftar pelanggaran secara spesifik mencantumkan nama container dan nama deployment terkait.

---

### 19. Summary & Key Takeaways
* Static IaC Analysis memindahkan deteksi risiko infrastruktur dari runtime cloud ke tahap pre-deployment, memutus rantai serangan pada fase *pull request*.
* Pemindai seperti Checkov, TFSec/Trivy, dan KICS bekerja dengan mengonversi berkas HCL atau YAML ke dalam representasi Abstract Syntax Tree (AST) dan semantic graph untuk menganalisis relasi antar-resource.
* Policy-as-Code (PaC) memisahkan aturan kepatuhan (*compliance*) dari logika kode infrastruktur. Menggunakan Open Policy Agent (OPA) dan Rego, tim keamanan dapat menegakkan batas keamanan organisasi secara seragam di seluruh pipeline.
* Standardisasi baseline CIS Benchmarks dapat diotomatisasi sepenuhnya melalui ruleset terstandarisasi yang mengevaluasi parameter kritis seperti enkripsi data at-rest, isolasi jaringan privat, dan *least-privilege IAM*.
* Format output standar seperti SARIF menjadi jembatan integrasi antara alat analisis statis independen dengan sistem orkestrasi peringatan terpusat di level enterprise.

---

### 20. Referensi Resmi & Standar Keamanan
* **CIS Benchmarks Documentation**: [Center for Internet Security (CIS) Cloud & Kubernetes Benchmarks](https://www.cisecurity.org/cis-benchmarks/)
* **Open Policy Agent (OPA) Documentation**: [OPA Rego Language Reference & Engine Specifications](https://www.openpolicyagent.org/docs/latest/)
* **Checkov Policy Reference**: [Bridgecrew / Palo Alto Networks IaC Security Rules](https://www.checkov.io/docs/)
* **NIST Special Publication 800-53 (Rev 5)**: *Security and Privacy Controls for Information Systems and Organizations* (Khususnya kontrol AC-3 Access Enforcement, SC-7 Boundary Protection, dan SC-28 Protection of Information at Rest).
* **OASIS Standard**: [Static Analysis Results Interchange Format (SARIF) Version 2.1.0](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html)