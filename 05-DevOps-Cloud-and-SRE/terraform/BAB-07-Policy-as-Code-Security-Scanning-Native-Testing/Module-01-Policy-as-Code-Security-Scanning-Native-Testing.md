# Module 01: Policy-as-Code, Security Scanning & Native Testing

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang, mengonfigurasi, dan mengotomatisasi mekanisme *Policy-as-Code* (PaC) pada pipeline CI/CD Terraform menggunakan Open Policy Agent (OPA) dan Rego.
- Menganalisis file rencana eksekusi (*Terraform JSON execution plan*) untuk mendeteksi pelanggaran keamanan arsitektur sebelum fase *provisioning*.
- Mengimplementasikan pemindaian keamanan statis (*Static Application Security Testing* untuk IaC) memanfaatkan Trivy/tfsec dan Checkov dengan *custom policies* serta *suppression management*.
- Membangun pengujian otomatis tingkat unit dan integrasi menggunakan Terraform Native Testing Framework (`terraform test` dan file `.tftest.hcl`) yang diperkenalkan pada Terraform v1.6+.
- Mengisolasi dependensi penyedia cloud eksternal melalui teknik *provider mocking* dan *override* variabel dalam lingkungan pengujian IaC.

---

## 2. Prerequisite
Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- Sintaksis dasar dan lanjutan HashiCorp Configuration Language (HCL2): ekspresi, fungsi bawaan, blok modul, variabel, dan *outputs*.
- Siklus hidup eksekusi Terraform: `terraform init`, `validate`, `plan`, `apply`, dan manajemen *state file*.
- Konsep dasar CI/CD Pipeline (GitLab CI, GitHub Actions, atau Jenkins) dan manipulasi data format JSON (`jq`).
- Terpasangnya kakas berikut pada mesin kerja lokal:
  - Terraform CLI (versi $\ge$ 1.6.0)
  - Open Policy Agent (OPA) CLI (versi $\ge$ 0.55.0)
  - Trivy CLI (versi $\ge$ 0.45.0) atau Checkov CLI (versi $\ge$ 3.0.0)
  - Python 3.10+ (untuk skrip automasi pengujian)

---

## 3. Concept
Infrastruktur modern menuntut kecepatan provisi tinggi tanpa mengorbankan postur keamanan (*security posture*) dan kepatuhan (*compliance*). Pendekatan tradisional yang mengandalkan audit manual pasca-deployment (*post-provisioning gatekeeping*) terbukti lambat, rawan kelalaian manusiawi, dan mahal dalam remediasi insiden.

*Policy-as-Code* (PaC) mentransformasikan aturan tata kelola, batasan anggaran, dan standar keamanan organisasi menjadi kode program yang dapat diuji, dikontrol versinya (*version-controlled*), dan dieksekusi secara otomatis di dalam pipeline integrasi berkelanjutan (*shift-left paradigm*). 

Dalam ekosistem Terraform, validasi keamanan dan fungsionalitas dibagi menjadi tiga lapisan (*defense-in-depth testing*):
1. **Static Analysis & SAST (Trivy/tfsec, Checkov):** Menganalisis sintaks HCL mentah untuk mendeteksi *misconfiguration* umum (misal: S3 bucket publik, port SSH 22 terbuka ke `0.0.0.0/0`, atau enkripsi KMS nonaktif).
2. **Policy-as-Code Enforcement (OPA/Rego):** Mengevaluasi representasi JSON dari `terraform plan` terhadap aturan organisasi yang kompleks dan spesifik konteks (misal: pembatasan ukuran instance EC2 hanya seri `t4g.*` pada environment `staging`, atau kuota maksimal total IP publik).
3. **Native Testing Framework (`terraform test`):** Memverifikasi logika internal modul Terraform—seperti kebenaran kalkulasi CIDR, kondisi kondisional (`count`/`for_each`), dan dependensi *output*—menggunakan pengujian unit (*mocked plan*) maupun pengujian integrasi (*actual apply & destroy*).

---

## 4. Why
Mengapa paradigma pengujian berlapis ini esensial bagi arsitektur komputasi awan?
- **Pencegahan Dini (*Shift-Left Remediation*):** Biaya memperbaiki celah keamanan pada tahap *pull request* jauh lebih murah dibanding remediasi server produksi yang telah tereksploitasi.
- **Standarisasi Non-Negosiasi (*Automated Guardrails*):** Menghilangkan friksi subjektif antara tim Platform/SRE dan tim Security/Auditor. Aturan kepatuhan didefinisikan secara eksplisit dan deterministik.
- **Mencegah Kerusakan State (*Blast Radius Reduction*):** Native testing memastikan bahwa perubahan konfigurasi pada modul inti tidak merusak modul turunan (*downstream consumers*) sebelum kode di-merge ke branch utama.
- **Auditability & Traceability:** Kebijakan keamanan disimpan dalam repository Git, memiliki riwayat commit, melalui proses *code review*, dan tunduk pada pengujian regresi internal.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Siklus Evaluasi Keamanan Terraform
Alur validasi IaC modern terdiri dari tahapan terstruktur:
1. **Linting & Validasi Sintaks:** `terraform fmt -check`, `terraform validate`.
2. **Static Security Scanning (HCL parsing):** Memeriksa file `.tf` secara AST (*Abstract Syntax Tree*) menggunakan Checkov / Trivy.
3. **Plan Generation & Export:** Menghasilkan biner plan dan mengekspornya ke JSON terstruktur:
   ```bash
   terraform plan -out=tfplan.binary
   terraform show -json tfplan.binary > tfplan.json
   ```
4. **Policy Enforcement (JSON parsing):** OPA mengurai `tfplan.json` (khususnya blok `resource_changes`) menggunakan aturan Rego. Jika terdeteksi *deny rule*, CI pipeline menghasilkan exit code non-zero.
5. **Native Functional Testing:** Menjalankan file `.tftest.hcl` untuk memvalidasi *assertions* pada modul.

### 5.2 Anatomi `tfplan.json` untuk OPA
Objek terpenting di dalam `tfplan.json` adalah `resource_changes`, yang memuat array tindakan (*actions*) terhadap sumber daya:
- `change.actions`: Berisi array string, misalnya `["create"]`, `["update"]`, `["delete"]`, atau `["no-op"]`.
- `change.before`: Atribut resource sebelum dieksekusi (bernilai null pada pembuatan baru).
- `change.after`: Atribut resource yang diajukan untuk dibuat/diperbarui.
- `change.after_unknown`: Atribut bernilai dinamis yang hanya diketahui setelah provider cloud selesai mengeksekusi API (misal: ID instans, ARN tergenerasi).

### 5.3 Static Analyzers: Checkov vs Trivy
- **Checkov:** Berbasis Python, menganalisis HCL, Kubernetes, Dockerfile, dan CloudFormation. Checkov memiliki pemahaman mendalam tentang *graph relationship* antar resource Terraform (misal: memeriksa apakah `aws_security_group_rule` terhubung ke `aws_security_group` tertentu).
- **Trivy (sebelumnya tfsec):** Ditulis dalam Go, berfokus pada kecepatan eksekusi tinggi dan konsumsi memori rendah. Mengintegrasikan pemindaian IaC, container image, dan dependency vulnerabilities dalam satu binary.

### 5.4 Terraform Native Testing Framework (v1.6+)
Sebelum v1.6, pengujian fungsional modul membutuhkan kakas eksternal seperti Terratest (berbasis Go) atau Kitchen-Terraform (berbasis Ruby). Terraform v1.6+ menyediakan framework native dengan spesifikasi:
- File pengujian dinamai dengan ekstensi `.tftest.hcl` di dalam direktori `tests/` atau selevel modul.
- Terdiri dari satu atau lebih blok `run`.
- Setiap blok `run` dapat mengeksekusi mode `command = plan` (unit test tanpa membuat resource sungguhan) atau `command = apply` (integration test yang memanggil API provider nyata).
- Blok `assert` mengevaluasi ekspresi boolean; jika bernilai `false`, pengujian gagal dan mengeluarkan pesan `error_message`.
- Fitur Provider Mocking (`mock_provider`) memungkinkan pengujian modul tanpa autentikasi kredensial cloud asli.

---

## 6. How
Prosedur end-to-end implementasi pengujian dan audit keamanan:

1. **Konfigurasi Modul Terraform:** Tulis file konfigurasi `.tf`.
2. **Pemindaian Statis:** Jalankan Checkov dan Trivy untuk mendeteksi *insecure defaults*.
3. **Eksekusi Native Unit Test:** Jalankan `terraform test` dengan mocking untuk menguji validitas variabel, kalkulasi lokal, dan assertions logika.
4. **Generasi Execution Plan:** Inisialisasi dan buat plan terkompilasi, lalu konversi ke JSON.
5. **Evaluasi Kebijakan OPA:** Eksekusi binary OPA terhadap `tfplan.json` menggunakan file policy `.rego`.
6. **Integrasi Pipeline:** Kemas seluruh alur kerja ini ke dalam tahapan CI/CD Pipeline dengan batasan gerbang (*exit code gatekeeper*).

---

## 7. Analogy
Bayangkan proses pembangunan gedung apartemen bertingkat:
- **Linting (`terraform validate`):** Memeriksa apakah cetak biru (*blueprint*) digambar dengan standar notasi arsitektur yang benar, tanpa ada simbol yang cacat.
- **Static Security Scan (Trivy/Checkov):** Inspektur bahan bangunan membaca cetak biru dan langsung menandai: *"Material dinding ini tidak tahan api"* atau *"Pintu darurat dipasangi kunci manual dari dalam"*.
- **Native Testing (`terraform test`):** Insinyur struktur membuat model simulasi komputer atau miniatur skala kecil (*mocking*) untuk menguji apakah balok penopang mampu menahan beban angin topan sesuai perhitungan matematis rumus sipil.
- **Policy-as-Code (OPA):** Badan Perizinan Tata Kota (BPN/Dinas Tata Ruang) memeriksa cetak biru akhir terhadap regulasi daerah: *"Tinggi gedung di zona ini tidak boleh melebihi 10 lantai"* dan *"Rasio ruang terbuka hijau harus minimal 30%"*. Jika melanggar, izin mendirikan bangunan (IMB) ditolak sebelum semen pertama dituangkan.

---

## 8. Diagram (ASCII)

```
[ Developer Commit ]
        │
        ▼
[ 1. Syntax & Linting ] ──────► terraform fmt -check && terraform validate
        │ (PASS)
        ▼
[ 2. Static IaC Scanning ] ───► Trivy / Checkov
        │                         │
        │ (PASS)                  ├─ (FAIL: High/Crit) ──► [ REJECT PIPELINE ]
        ▼                         │
[ 3. Native Unit Testing ] ───► terraform test (command = plan, mock_provider)
        │                         │
        │ (PASS)                  └─ (FAIL: Assert Error) ► [ REJECT PIPELINE ]
        ▼
[ 4. Plan & Export ] ─────────► terraform plan -out=plan.bin
                                terraform show -json plan.bin > plan.json
        │
        ▼
[ 5. Policy Enforcement ] ────► opa eval --data policies/ --input plan.json
        │
        ├── Violations Found? ──► YES ───────────────────► [ REJECT PIPELINE ]
        │
        ▼ NO
[ 6. Deploy / Provision ] ────► terraform apply plan.bin
```

---

## 9. Simple Example

### 9.1 Skenario
Mencegah pembuatan bucket AWS S3 yang tidak memiliki tag `Environment` menggunakan OPA Rego.

### 9.2 OPA Rego Policy (`rules/tags.rego`)
```rego
package terraform.security

import future.keywords.in

default allow = false

# Dapatkan semua resource S3 yang sedang dibuat atau diupdate
s3_creations[resource] {
    some resource in input.resource_changes
    resource.type == "aws_s3_bucket"
    resource.change.actions[_] in ["create", "update"]
}

# Pelanggaran jika tag 'Environment' tidak ditemukan atau kosong
deny[msg] {
    some bucket in s3_creations
    not bucket.change.after.tags.Environment
    msg := sprintf("Resource '%v' dilarang: Tag 'Environment' wajib disertakan.", [bucket.address])
}

deny[msg] {
    some bucket in s3_creations
    bucket.change.after.tags.Environment == ""
    msg := sprintf("Resource '%v' dilarang: Tag 'Environment' tidak boleh bernilai kosong.", [bucket.address])
}

# Izinkan apply jika tidak ada pesan deny
allow {
    count(deny) == 0
}
```

---

## 10. Practical Example (Konfigurasi Hands-on Lengkap)

Mari kita bangun arsitektur nyata: Modul Terraform untuk membuat S3 Bucket dan Security Group, divalidasi dengan Checkov, diuji dengan `terraform test`, dan dievaluasi via OPA.

### 10.1 Struktur File Direktori
```
project-pac-testing/
├── main.tf
├── variables.tf
├── outputs.tf
├── tests/
│   └── unit_tests.tftest.hcl
├── policies/
│   └── networking_guardrails.rego
└── checkov-config.yml
```

### 10.2 Kode Terraform (`variables.tf`)
```hcl
variable "aws_region" {
  type        = string
  default     = "ap-southeast-1"
  description = "Region AWS target"
}

variable "environment" {
  type        = string
  description = "Deployment target environment (dev/staging/prod)"
  
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Variabel environment harus bernilai: dev, staging, atau prod."
  }
}

variable "ingress_ports" {
  type        = list(number)
  description = "Daftar port ingress yang dibuka"
  default     = [443]
}
```

### 10.3 Kode Terraform (`main.tf`)
```hcl
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# S3 Bucket dengan Enkripsi Default (KMS SSE)
resource "aws_s3_bucket" "app_storage" {
  bucket_prefix = "corp-data-${var.environment}-"
  
  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "app_storage_crypto" {
  bucket = aws_s3_bucket.app_storage.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "app_storage_block" {
  bucket = aws_s3_bucket.app_storage.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Security Group
resource "aws_security_group" "web_access" {
  name_prefix = "app-sg-${var.environment}-"
  description = "Aturan firewall aplikasi web"

  dynamic "ingress" {
    for_each = var.ingress_ports
    content {
      description = "Izinkan trafik inbound port ${ingress.value}"
      from_port   = ingress.value
      to_port     = ingress.value
      protocol    = "tcp"
      cidr_blocks = ingress.value == 443 ? ["0.0.0.0/0"] : ["10.0.0.0/8"]
    }
  }

  egress {
    description = "Izinkan seluruh trafik outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Environment = var.environment
  }
}
```

### 10.4 Native Test (`tests/unit_tests.tftest.hcl`)
Pengujian unit menggunakan fitur `mock_provider` dari Terraform 1.6+:

```hcl
mock_provider "aws" {}

variables {
  aws_region  = "ap-southeast-1"
  environment = "prod"
}

run "verify_security_group_safety" {
  command = plan

  variables {
    ingress_ports = [443]
  }

  assert {
    condition     = aws_security_group.web_access.ingress[0].to_port == 443
    error_message = "Port ingress utama harus port HTTPS 443."
  }

  assert {
    condition     = contains(aws_security_group.web_access.ingress[0].cidr_blocks, "0.0.0.0/0")
    error_message = "Port 443 harus terbuka untuk publik."
  }
}

run "reject_insecure_port_broadcasting" {
  command = plan

  variables {
    ingress_ports = [22]
  }

  # Validasi bahwa port non-443 tidak dibuka ke 0.0.0.0/0
  assert {
    condition     = !contains(aws_security_group.web_access.ingress[0].cidr_blocks, "0.0.0.0/0")
    error_message = "Port administratif (seperti 22) DILARANG keras memiliki CIDR 0.0.0.0/0."
  }

  assert {
    condition     = contains(aws_security_group.web_access.ingress[0].cidr_blocks, "10.0.0.0/8")
    error_message = "Port non-HTTPS harus diarahkan ke CIDR internal privat."
  }
}

run "verify_s3_public_access_block" {
  command = plan

  assert {
    condition     = aws_s3_bucket_public_access_block.app_storage_block.block_public_acls == true
    error_message = "S3 Block Public ACLs wajib diaktifkan (true)."
  }

  assert {
    condition     = aws_s3_bucket_public_access_block.app_storage_block.restrict_public_buckets == true
    error_message = "S3 Restrict Public Buckets wajib diaktifkan (true)."
  }
}
```

### 10.5 OPA Rego Policy (`policies/networking_guardrails.rego`)
Aturan keamanan perusahaan: Dilarang membuat Security Group yang membuka port SSH (22) atau RDP (3389) ke internet publik (`0.0.0.0/0`), terlepas dari nilai konfigurasi variable apapun.

```rego
package terraform.compliance

import future.keywords.in

default allow = false

# Definisi port berisiko tinggi
dangerous_ports := [22, 3389, 21, 23]

# Tangkap semua resource Security Group yang sedang dibuat/dimodifikasi
sg_changes[res] {
    some res in input.resource_changes
    res.type == "aws_security_group"
    res.change.actions[_] in ["create", "update"]
}

# Aturan Deny: Periksa aturan ingress inline
deny[msg] {
    some sg in sg_changes
    some ingress in sg.change.after.ingress
    some port in dangerous_ports
    
    port >= ingress.from_port
    port <= ingress.to_port
    "0.0.0.0/0" in ingress.cidr_blocks
    
    msg := sprintf(
        "CRITICAL POLICY VIOLATION: Resource '%v' membuka port berisiko tinggi (%v) ke publik (0.0.0.0/0)!",
        [sg.address, port]
    )
}

# Aturan Deny: Wajib memiliki tag Environment bernilai dev, staging, atau prod
deny[msg] {
    some sg in sg_changes
    env := sg.change.after.tags.Environment
    not env in ["dev", "staging", "prod"]
    msg := sprintf("TAGGING VIOLATION: Resource '%v' memiliki nilai tag Environment tidak valid: '%v'.", [sg.address, env])
}

# Aturan Allow
allow {
    count(deny) == 0
}
```

### 10.6 Konfigurasi Checkov CLI (`checkov-config.yml`)
```yaml
directory:
  - .
framework:
  - terraform
output: cli
soft-fail: false
download-external-modules: false
compact: true
quiet: true
skip-check:
  - CKV_AWS_144 # Skip: S3 Cross-Region Replication (tidak relevan untuk unit test ini)
```

### 10.7 Instruksi Eksekusi CLI
```bash
# 1. Inisialisasi konfigurasi
terraform init

# 2. Jalankan Native Tests
terraform test

# 3. Jalankan Checkov Security Scanner
checkov --config-file checkov-config.yml

# 4. Bangun Plan JSON
terraform plan -var="environment=dev" -out=tfplan.binary
terraform show -json tfplan.binary > tfplan.json

# 5. Jalankan Evaluasi OPA
opa eval --data policies/ --input tfplan.json "data.terraform.compliance.deny"
```

---

## 11. Real World Example
Pada bank multinasional, tim arsitektur menerapkan sistem gerbang otomatis pada GitLab CI runner. Setiap kali developer membuat *Merge Request* (MR), pipeline menjalankan:
1. `trivy config . --severity HIGH,CRITICAL --exit-code 1`
2. `terraform test`
3. Pipeline menghasilkan `tfplan.json` terhadap infrastruktur *ephemeral*.
4. OPA mengevaluasi aturan FinOps dan Security:
   - Tidak boleh membuat instans database multi-AZ pada environment `dev`.
   - Tidak boleh menggunakan volume EBS tipe `gp2` (harus `gp3`).
   - Tidak boleh mengalokasikan AWS Elastic IP (EIP) lebih dari 2 buah per VPC.
Jika ada violation, MR otomatis ditandai *blocked* dan bot memberikan komentar langsung pada baris kode terkait detail pelanggaran kebijakan CIS Benchmark / FinOps.

---

## 12. Trade-offs
Mengadopsi ekosistem pengujian dan PaC membawa implikasi teknis:
- **Durasi Eksekusi CI/CD (Pipeline Latency):** Pemindaian menyeluruh, kompilasi JSON plan, dan pengujian integrasi (`command = apply`) menambah waktu eksekusi pipeline dari hitungan detik menjadi 5–15 menit.
- **Beban Pemeliharaan Bahasa Baru (Mental Overhead):** Tim platform harus mempelajari dan memelihara kode Rego (berbasis Datalog) di samping HCL. Rego memiliki kurva pembelajaran yang cukup curam dibanding sintaks prosedural.
- **Dilema Unit Test vs Integration Test:**
  - `command = plan` (Unit test) sangat cepat dan gratis, tetapi tidak dapat memverifikasi nilai terhitung (*unknown attributes*) yang hanya dihasilkan API AWS (seperti ID subnet otomatis).
  - `command = apply` (Integration test) memvalidasi status riil, tetapi memakan biaya komputasi cloud riil dan membutuhkan mekanisme *cleanup/destroy* yang rawan menyisakan sumber daya bocor (*zombie resources*).

---

## 13. When To Use
- Modul inti digunakan secara luas oleh banyak tim pengembang di organisasi (*shared platform modules*).
- Lingkungan produksi mengelola data sensitif (PII, PCI-DSS, HIPAA) yang tunduk pada audit kepatuhan regulasi ketat.
- Organisasi berskala besar di mana tim keamanan terpisah dari tim operasional dan membutuhkan *hard guardrails* otomatis tanpa intervensi manual.
- Menggantikan *approval gate* berbasis rapat CAB (*Change Advisory Board*) yang manual dengan gerbang kode otomatis.

---

## 14. When NOT To Use
- Eksplorasi awal atau pembuatan prototipe konsep (*Proof-of-Concept / PoC*) yang bersifat *disposable* (akan dihapus dalam hitungan jam).
- Lingkungan pengujian personal tunggal (*sandbox developer*) di mana kecepatan iterasi desain arsitektur lebih krusial daripada kepatuhan keamanan.
- Arsitektur statis sederhana yang jarang sekali mengalami perubahan frekuensi deployment.

---

## 15. Common Mistakes
1. **Mengabaikan `after_unknown` pada Evaluasi OPA:**
   Menulis aturan OPA yang mengasumsikan seluruh atribut bernilai pasti pada `tfplan.json`. Untuk resource yang dibuat baru, atribut seperti `id`, `arn`, atau `ipv4_address` seringkali bernilai null atau berada dalam blok `after_unknown`, sehingga memicu *runtime exception* atau *false negative* pada evaluasi Rego.
2. **Hardcoding Kredensial Cloud pada Native Integration Test:**
   Menyimpan akses AWS/GCP langsung di file konfigurasi pengujian alih-alih memanfaatkan OIDC provider, IAM Roles, atau Environment Variables sementara.
3. **Penyalahgunaan Checkov Suppression (`#checkov:skip`):**
   Developer membungkam peringatan keamanan (*security alerts*) menggunakan komentar `#checkov:skip=CKV_...` tanpa mencantumkan justifikasi arsitektur yang valid dan tanpa persetujuan tim SecOps.
4. **Menjalankan `terraform test` Tanpa Isolasi State:**
   Mengeksekusi native integration test pada workspace atau state yang sama dengan infrastruktur aktual, yang berpotensi menimpa atau menghapus resource aktif saat siklus *teardown* pengujian dijalankan.

---

## 16. Best Practices
- **Fail-Fast Hierarchy:** Jalankan pengujian teringan terlebih dahulu: `terraform fmt` $\rightarrow$ `tfsec/trivy` $\rightarrow$ `terraform test (plan)` $\rightarrow$ `OPA eval (tfplan)` $\rightarrow$ `terraform test (apply)`.
- **Gunakan Format Standar JSON OPA:** Simpan aturan Rego dalam modul-modul modular (misalnya: `policies/tags/`, `policies/security_groups/`, `policies/storage/`) dengan struktur data input yang konsisten.
- **Validasi Nilai Default Menggunakan Variable Validations:** Tangani validasi parameter sederhana langsung di HCL menggunakan blok `validation {}` pada `variables.tf`, simpan OPA untuk aturan lintas-sumberdaya (*cross-resource governance*).
- **Audit Suppression:** Konfigurasi pemindai keamanan agar menolak *inline skip* kecuali menyertakan tiket referensi (contoh: `#checkov:skip=CKV_AWS_20:JIRA-4021 approved exception`).
- **Gunakan Provider Mocking:** Manfaatkan `mock_provider` di Terraform 1.6+ untuk 90% skenario pengujian guna meniadakan latensi jaringan dan konsumsi biaya cloud.

---

## 17. Troubleshooting

| Gejala Masalah | Penyebab Utama | Solusi Perbaikan |
|---|---|---|
| `terraform test` gagal: *Provider configuration not found* | Modul turunan atau blok test tidak memiliki konfigurasi provider eksplisit atau mocking | Tambahkan blok `mock_provider "<provider_name>" {}` di bagian atas file `.tftest.hcl` untuk unit test. |
| OPA mengembalikan output kosong `undefined` | Jalur paket (*package path*) atau variabel kueri tidak sesuai dengan payload input JSON | Verifikasi path query: `opa eval --data policies/ --input tfplan.json "data.<nama_package>.<nama_rule>"`. |
| Checkov gagal mem-parsing Terraform module | Checkov tidak dapat menyelesaikan modul privat eksternal tanpa otentikasi Git | Tambahkan argumen `--download-external-modules false` jika hanya menguji resource internal, atau sediakan SSH key di runner. |
| OPA evaluasi lolos padahal ada pelanggaran (*false negative*) | Rule Rego memeriksa blok `change.after` padahal resource mengalami operasi `delete` | Tambahkan validasi eksplisit aksi: `res.change.actions[_] in ["create", "update"]` agar kondisi sesuai siklus resource. |

---

## 18. Exercise
1. Buat sebuah modul Terraform sederhana yang mendeklarasikan resource `aws_kms_key` dengan `deletion_window_in_days = 7`.
2. Tulis file `tests/kms.tftest.hcl` yang memverifikasi bahwa jika variabel input `environment` disetel ke `prod`, maka nilai `deletion_window_in_days` harus sama dengan atau lebih besar dari 30 hari. Gunakan `command = plan` dan `mock_provider`.
3. Tulis aturan OPA Rego yang menolak plan jika resource `aws_kms_key` memiliki parameter `enable_key_rotation` bernilai `false`.
4. Uji aturan OPA tersebut terhadap hasil export `terraform show -json`.

---

## 19. Challenge
Rancang arsitektur PaC menyeluruh untuk lingkungan multi-tier (Database, API, Web). Implementasikan:
1. Native Test (`.tftest.hcl`) yang menguji kalkulasi CIDR subnet VPC: Subnet Database dilarang memiliki route langsung menuju Internet Gateway (`aws_internet_gateway`).
2. OPA Policy yang melarang penggunaan instance tipe apapun selain keluarga Graviton (`*.graviton` atau seri `t4g.*`, `m6g.*`, `c6g.*`) di AWS pada seluruh instans `aws_instance` dan `aws_db_instance`.
3. CI script mandiri (Bash/Python) yang mengintegrasikan Trivy, Terraform Test, dan OPA. Pipeline harus menghasilkan satu file rekap JSON komprehensif berisi seluruh temuan celah keamanan beserta *compliance score* (0-100%).

---

## 20. Summary
- **Shift-Left Security:** Pendekatan modern mendorong pengujian kepatuhan dan keamanan dilakukan sedini mungkin di workstation developer dan pipeline PR sebelum sumber daya benar-benar diprovisi.
- **Lapisan Alat Pelengkap:**
  - *Trivy/Checkov:* Menganalisis file konfigurasi statis untuk celah keamanan umum berbasis CVE dan best practice CIS.
  - *Terraform Test:* Memvalidasi kebenaran logika fungsional internal modul HCL secara native tanpa perkakas eksternal pihak ketiga.
  - *Open Policy Agent (OPA):* Melakukan audit arsitektural dan tata kelola tingkat lanjut terhadap artefak rencana eksekusi (`tfplan.json`).
- Penguasaan ketiga pilar ini membedakan seorang praktisi Cloud/DevOps biasa dari seorang *Principal Platform Architect* yang mampu menjamin stabilitas, efisiensi biaya, dan integritas kepatuhan infrastruktur skala besar.