# BAB-06: IaC Security & Policy-as-Code
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengoperasikan arsitektur *Policy-as-Code* (PaC) bertingkat (*multi-layered defense*) dari siklus IDE, CI/CD pipeline, hingga runtime admission controller.
- Mengembangkan aturan evaluasi deklaratif tingkat lanjut menggunakan Open Policy Agent (OPA) / Rego pada representasi AST (*Abstract Syntax Tree*) dari artefak `terraform plan` JSON.
- Mengintegrasikan analisis komposisi graf dependensi infrastruktur untuk mendeteksi *blast radius* destruktif, *drift* konfigurasi, dan kebocoran rahasia (*secret leakage*) dalam *Terraform state file*.
- Memetakan dan mengotomatiskan kontrol kepatuhan regulasi finansial (PCI-DSS 4.0, SOC 2 Type II, CIS Benchmark) ke dalam *custom dynamic security guardrails*.
- Mengatasi tantangan skalabilitas evaluasi kebijakan skala *enterprise* (ribuan repositori mikro-IaC) menggunakan *centralized policy registry* dan strategi *decoupled distribution*.

---

### 2. Prerequisite
Sebelum mendalami modul ini, peserta wajib menguasai:
- **Terraform Core**: Pemahaman mendalam mengenai siklus hidup Terraform (`init`, `plan`, `apply`), dependensi graf, konfigurasi *provider*, modul, dan struktur internal *state* (`terraform.tfstate`) serta *plan binary-to-JSON serialisation*.
- **Dasar Policy Engine**: Sintaks dasar Open Policy Agent (OPA) Rego atau HashiCorp Sentinel, konsep dasar *rule*, *head*, *body*, dan evaluasi *boolean set*.
- **CI/CD Orchestration**: Konfigurasi *pipeline* berbasis GitHub Actions, GitLab CI, atau Argo Workflows termasuk injeksi *environment variable*, *artifact passing*, dan *exit code handling*.
- **Container & Kubernetes Prerequisite**: Konsep *Admission Control* (Validating/Mutating Webhooks) dan format manifes Kubernetes.

---

### 3. Concept & Internal Architecture

Implementasi enterprise dari IaC Security dan Policy-as-Code tidak bertumpu pada satu pemindai statis, melainkan arsitektur berlapis yang mengabstraksi evaluasi kebijakan dari *execution engine* infrastruktur.

```
       +-----------------------------------------------------------+
       |                  Enterprise IaC Codebase                  |
       +-----------------------------------------------------------+
                                     |
                                     v
                 +---------------------------------------+
                 | Phase 1: Pre-Synthesized Static Lint  |
                 | (Checkov / Trivy AST on Raw .tf Files)|
                 +---------------------------------------+
                                     |
                                     v
                       +---------------------------+
                       |   Terraform Engine Execution
                       |   `terraform plan -out=plan`
                       |   `terraform show -json`  |
                       +---------------------------+
                                     |
                                     v
                    +----------------------------------+
                    | Normalized Plan JSON (Normalized)|
                    +----------------------------------+
                                     |
      +------------------------------+------------------------------+
      |                                                             |
      v                                                             v
+-------------------------------+                     +-------------------------------+
|  Custom Policy Engine (OPA)   |                     | Blast Radius & Blast Budget   |
|  Evaluasi Rego terhadap:      |                     | Engine:                       |
|  - Resource Mutation Types    |                     | - Count(destroy) > Threshold  |
|  - Ingress/Egress CIDR rules  |                     | - Cost impact analysis        |
|  - Enkripsi KMS CMK Customer  |                     | - Critical data store drop    |
+-------------------------------+                     +-------------------------------+
      |                                                             |
      +------------------------------+------------------------------+
                                     |
                                     v
                     +-------------------------------+
                     |  Evaluation Aggregator Engine |
                     |  (Soft-Mandatory vs Hard-Fail)|
                     +-------------------------------+
                                     |
                     +---------------+---------------+
                     |                               |
          [Violations Detected]              [Zero Violation]
                     |                               |
                     v                               v
         +-----------------------+       +-----------------------+
         | CI/CD Pipeline Block  |       | Approval Gate Granted |
         | Post PR Comment via   |       | State Applied to      |
         | GitHub/GitLab API     |       | Production Provider   |
         +-----------------------+       +-----------------------+
```

#### Komponen Arsitektur Inti:
1. **Normalized Abstract Syntax Tree (Plan Serialization)**:
   Terraform mengekspresikan infrastruktur yang akan dibuat/diubah/dihapus dalam representasi JSON terstruktur via `terraform show -json <plan_file>`. Format ini memuat:
   - `resource_changes`: Array yang memuat operasi CRUD (`actions`: `["create"]`, `["update"]`, `["delete"]`).
   - `configuration`: Blok referensi konfigurasi asli HCL.
   - `prior_state` vs `after_state`: Menampilkan delta persis nilai atribut sebelum dan sesudah diaplikasikan.
2. **Decoupled Policy Distribution**:
   Aturan (*policies*) tidak disimpan di repositori aplikasi/infrastruktur tim produk, melainkan pada *Centralized Policy Repository* yang di-versi secara ketat (*semantic versioning*). CI/CD pipeline menarik (*pull*) versi *bundle* kebijakan terverifikasi menggunakan *secure digest* (SHA256).
3. **Decisional Tiers**:
   - **Advisory (Soft Guardrail)**: Memberikan peringatan pada log dan *pull request* tanpa memutus *build* (biasanya digunakan untuk *deprecation warning* atau *cost optimization*).
   - **Hard Mandatory (Hard Guardrail)**: Langsung melempar `exit code != 0`, membatalkan seluruh *pipeline execution* seketika jika terdapat pelanggaran keamanan kritis (misal: S3 bucket publik, pembukaan port `0.0.0.0/0` pada port 22/3389, non-CMK disk encryption).

---

### 4. Why & What

| Dimensi | Pendekatan Reaktif (Legacy) | Policy-as-Code Enterprise |
| :--- | :--- | :--- |
| **Mekanisme Audit** | Audit manual via Cloud Security Posture Management (CSPM) setelah deployment. | Analisis komputasional deterministik *sebelum* infrastruktur dialokasikan (*pre-flight*). |
| **Feedback Loop** | Mingguan / Bulanan melalui laporan tim Information Security. | Detik / Menit langsung pada *developer feedback loop* (Terminal/Pull Request). |
| **Konsistensi** | Subjektif bergantung pada auditor manusia; sering terjadi *human-error*. | Deterministik murni berbasis kode; *zero tolerance deviation*. |
| **Blast Radius** | Terdeteksi saat insiden pemadaman atau kebocoran data di produksi. | Terdeteksi di CI; eksekusi diblokir otomatis jika operasi *delete* melebihi batas toleransi. |
| **Audit Trails** | Log AWS CloudTrail / GCP Audit Logs yang terfragmentasi. | Log versi *git commit* aturan Rego yang dapat diverifikasi secara kriptografis (*git provenance*). |

---

### 5. How (Workflow Detail)

Alur kerja implementasi *end-to-end* IaC security pada pipeline produksi:

1. **Local Developer Hook (Shift-Left Tier 1)**:
   - *Developer* mengeksekusi `git commit`.
   - Tooling pre-commit lokal mengeksekusi *lightweight static analysis* (misal: Checkov/Trivy) untuk mendeteksi *hardcoded secrets* dan kesalahan sintaksis HCL dasar.
2. **PR Synthesis & Plan Generation (Shift-Left Tier 2)**:
   - *Developer* membuka Pull Request ke *branch* `main`.
   - Pipeline CI menginisialisasi Terraform dan mengeksekusi:
     ```bash
     terraform init -backend=false
     terraform plan -out=tfplan.binary
     terraform show -json tfplan.binary > tfplan.json
     ```
3. **Policy Enforcement Phase**:
   - OPA Engine memuat *bundle* kebijakan Rego yang ditarik dari *registry* tersentralisasi.
   - Evaluasi dijalankan terhadap file `tfplan.json`.
   - Engine mengevaluasi *threshold* destruksi (*blast radius calculation*).
4. **Attestation & Execution**:
   - Jika evaluasi menghasilkan `allow == true` dan `count(violations) == 0`:
     - Pipeline menandatangani (*cryptographic attestation*) manifes plan yang lolos validasi.
     - *Gate* approval untuk deployment otomatis terbuka.
   - Jika `violations > 0`:
     - Pipeline memicu webhook untuk mem-posting detail pelanggaran secara spesifik ke antarmuka PR (menyebutkan file, blok resource, dan ID standar kepatuhan yang dilanggar).
     - Pipeline memutus eksekusi dengan `exit 1`.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Cetak Biru dan Pengawas Bangunan Digital
Bayangkan membangun gedung pencakar langit. 
- **Kode HCL** adalah sketsa awal dari arsitek.
- **`terraform plan` JSON** adalah cetak biru teknis detail yang menghitung presisi struktur fondasi, sistem kelistrikan, dan bahan kimia semen yang akan dituangkan.
- **Policy-as-Code (Rego/OPA)** adalah **Badan Regulasi Keselamatan Bangunan**. Sebelum satu truk semen pun tiba di lokasi konstruksi nyata (AWS/GCP/Azure), inspektur membaca cetak biru tersebut menggunakan mesin pemindai otomatis.
- Jika cetak biru memperlihatkan pintu darurat terkunci atau tangga kebakaran ditiadakan, pembangunan **dibatalkan secara hukum seketika di atas kertas**, bukan setelah gedung selesai dibangun dan terbakar.

```
       [Developer]
            │
      Writes HCL Code
            │
            ▼
    [terraform plan]
            │
   Generates Normalized
       AST Blueprint
            │
            ▼
     ┌─────────────┐
     │ tfplan.json │
     └──────┬──────┘
            │
            ├───────────────────────────────────────────────────────┐
            ▼                                                       ▼
  ┌──────────────────┐                                    ┌──────────────────┐
  │ OPA Engine (Rego)│                                    │  Blast Engine    │
  └─────────┬────────┘                                    └────────┬─────────┘
            │                                                      │
    Evaluates Security                                      Evaluates Impact
   - Public Ingress?                                       - Deleting Prod DB?
   - Unencrypted EBS?                                      - Changes > 50 res?
            │                                                      │
            └───────────────────────┬──────────────────────────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │  Decision Evaluator │
                         └──────────┬──────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
             [DENIED]                            [ALLOWED]
                  │                                   │
      - Exit Code 1                       - Exit Code 0
      - Drop Pipeline                     - terraform apply
      - Notify Security Dashboard         - Cloud State Mutated
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example (Pemula): Validasi Tag Sederhana via OPA
Skenario: Memastikan setiap resource AWS memiliki tag `Environment` yang valid.

File: `policy_simple.rego`
```rego
package terraform.simple

import future.keywords.in

default allow = false

valid_environments := ["production", "staging", "development"]

# Kumpulkan semua pelanggaran tag
deny[msg] {
    resource := input.resource_changes[_]
    resource.mode == "managed"
    
    # Periksa ketiadaan tag Environment atau nilai yang tidak valid
    tags := resource.change.after.tags
    not tags.Environment
    
    msg := sprintf("Resource '%v' tidak memiliki tag mandatory 'Environment'.", [resource.address])
}

deny[msg] {
    resource := input.resource_changes[_]
    resource.mode == "managed"
    env := resource.change.after.tags.Environment
    not env in valid_environments
    
    msg := sprintf("Resource '%v' memiliki Environment '%v' yang tidak valid. Opsi valid: %v", [resource.address, env, valid_environments])
}

allow {
    count(deny) == 0
}
```

---

#### 7.2 Practical Example (Enterprise Production): OPA Plan Analyzer & Blast Radius Guard
Skenario Lanjutan:
1. Memastikan tidak ada Security Group yang membuka port 22 (SSH) ke `0.0.0.0/0`.
2. Memastikan seluruh S3 Bucket mengaktifkan enkripsi SSE dengan KMS CMK (bukan SSE-S3 standar).
3. **Blast Radius Protection**: Menolak plan secara otomatis jika terdapat operasi *destruction* pada resource berstatus `production` melebihi toleransi yang ditentukan (Threshold: Maksimal 0 resource `aws_rds_cluster` atau `aws_dynamodb_table` boleh di-destroy).

File: `policies/enterprise_guardrails.rego`
```rego
package enterprise.terraform.security

import future.keywords.every
import future.keywords.if
import future.keywords.in

# Default deny-all posture untuk validasi final
default allow = false

# Definisi konstanta kepatuhan
CRITICAL_RESOURCE_TYPES := [
    "aws_rds_cluster",
    "aws_rds_cluster_instance",
    "aws_dynamodb_table",
    "aws_elasticsearch_domain"
]

###############################################################################
# RULE 1: Deteksi Pelanggaran CIDR Terbuka pada Security Group (Ingress 22)
###############################################################################
deny[reason] {
    resource := input.resource_changes[_]
    resource.type == "aws_security_group_rule"
    resource.change.actions[_] in ["create", "update"]
    
    # Ambil konfigurasi target
    type := resource.change.after.type
    type == "ingress"
    
    from_port := resource.change.after.from_port
    to_port := resource.change.after.to_port
    cidr_blocks := resource.change.after.cidr_blocks[_]
    
    # Evaluasi port SSH
    is_ssh_exposed(from_port, to_port)
    cidr_blocks == "0.0.0.0/0"
    
    reason := {
        "rule_id": "SEC-NET-001",
        "severity": "CRITICAL",
        "resource": resource.address,
        "message": "Ingress Security Group membuka akses SSH (port 22) langsung ke publik (0.0.0.0/0)."
    }
}

is_ssh_exposed(from_p, to_p) if {
    from_p <= 22
    to_p >= 22
}

###############################################################################
# RULE 2: Enkripsi Ketat S3 dengan AWS KMS Customer Managed Keys (CMK)
###############################################################################
deny[reason] {
    resource := input.resource_changes[_]
    resource.type == "aws_s3_bucket_server_side_encryption_configuration"
    resource.change.actions[_] in ["create", "update"]
    
    rules := resource.change.after.rule[_]
    apply_sse := rules.apply_server_side_encryption_by_default[_]
    
    # Validasi apakah algoritma menggunakan aws:kms dan memasukkan kms_master_key_id
    not is_kms_compliant(apply_sse)
    
    reason := {
        "rule_id": "SEC-S3-002",
        "severity": "HIGH",
        "resource": resource.address,
        "message": "S3 SSE configuration wajib menggunakan KMS dengan KMS Master Key spesifik (Customer Managed Key)."
    }
}

is_kms_compliant(sse) if {
    sse.sse_algorithm == "aws:kms"
    sse.kms_master_key_id != null
    count(sse.kms_master_key_id) > 0
}

###############################################################################
# RULE 3: Blast Radius Guardrail (Mencegah Kehancuran Data Kritis)
###############################################################################
deny[reason] {
    destroyed_critical_resources := [res |
        res := input.resource_changes[_]
        res.type in CRITICAL_RESOURCE_TYPES
        res.change.actions[_] == "delete"
    ]
    
    count(destroyed_critical_resources) > 0
    
    offending_addresses := [r.address | r := destroyed_critical_resources[_]]
    
    reason := {
        "rule_id": "RES-BLAST-003",
        "severity": "FATAL",
        "resource": "pipeline_execution",
        "message": sprintf("Blast Radius Guardrail terpicu: Terdeteksi penghapusan data store kritis: %v", [offending_addresses])
    }
}

###############################################################################
# DECISION AGGREGATOR
###############################################################################
violations := [v | v := deny[_]]

# Allow HANYA jika array violations kosong mutlak
allow if {
    count(violations) == 0
}
```

File: Skrip Validasi CI Execution (`ci_policy_checker.py`)
```python
#!/usr/bin/env python3
"""
Enterprise Policy Validation Gatekeeper Script
Mengevaluasi output JSON Terraform Plan terhadap Rego Policy menggunakan OPA binary
"""
import subprocess
import json
import sys

def run_opa_eval(policy_path: str, plan_json_path: str) -> dict:
    cmd = [
        "opa", "eval",
        "--data", policy_path,
        "--input", plan_json_path,
        "data.enterprise.terraform.security"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[FATAL] Gagal mengeksekusi OPA engine:\n{result.stderr}", file=sys.stderr)
        sys.exit(2)
        
    return json.loads(result.stdout)

def main():
    if len(sys.argv) < 3:
        print("Penggunaan: ./ci_policy_checker.py <path_to_policy.rego> <path_to_tfplan.json>")
        sys.exit(1)

    policy_file = sys.argv[1]
    plan_file = sys.argv[2]

    raw_output = run_opa_eval(policy_file, plan_file)
    
    # Parsing output OPA
    try:
        data = raw_output["result"][0]["expressions"][0]["value"]
        is_allowed = data.get("allow", False)
        violations = data.get("violations", [])
    except (KeyError, IndexError) as err:
        print(f"[ERROR] Format output evaluasi OPA tidak valid: {err}", file=sys.stderr)
        sys.exit(2)

    print("=========================================================")
    print("           ENTERPRISE IAC SECURITY SCAN RESULTS          ")
    print("=========================================================")

    if is_allowed:
        print("[SUCCESS] Status: ALLOWED. Tidak ditemukan pelanggaran kebijakan.")
        sys.exit(0)
    else:
        print(f"[DENIED] Status: BLOCKED. Terdeteksi {len(violations)} pelanggaran kebijakan:\n")
        fatal_count = 0
        for idx, v in enumerate(violations, start=1):
            severity = v.get("severity", "UNKNOWN")
            if severity in ["CRITICAL", "FATAL"]:
                fatal_count += 1
            print(f"[{idx}] Rule ID : {v.get('rule_id')}")
            print(f"    Severity: {severity}")
            print(f"    Target  : {v.get('resource')}")
            print(f"    Message : {v.get('message')}\n")
            
        print("=========================================================")
        print(f"Deployment digagalkan secara otomatis oleh Security Guardrail. (Total Pelanggaran Kritis: {fatal_count})")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Insiden FinTech MegaPay Global (Insiden Pembongkaran Database Transaksi)
* **Konteks**: FinTech dengan volume 12.000 transaksi/detik mengelola lebih dari 400 repositori microservices di AWS via Terraform.
* **Insiden**: Seorang *DevOps Engineer* melakukan perbaikan penamaan subnet pada modul jaringan shared VPC. Terraform mendeteksi dependensi siklik dan menyimpulkan bahwa cluster multi-AZ AWS Aurora PostgreSQL Production yang menampung saldo dompet nasabah harus di-*destroy* dan di-*recreate*. Engineer tersebut menjalankan `terraform apply` di pipeline CI yang tidak memiliki perlindungan *plan mutation parsing*.
* **Dampak**: 
  - Database utama terhapus seketika.
  - Waktu *downtime* layanan: 4 jam 45 menit (proses *restore* PITR dari snapshot snapshot S3/KMS).
  - Kerugian finansial: Biaya kompensasi SLA senilai $1.200.000 USD dan audit regulasi perbankan.

#### Implementasi Resolusi DevSecOps:
1. **Penerapan Multi-Phase Blast Engine**:
   - Diimplementasikan kebijakan OPA wajib: Eksekusi `terraform plan` yang mendeteksi tindakan `["delete"]` pada resource yang diberi metadata `lifecycle_tier: stateful-data` secara eksplisit ditolak (*un-overridable fatal block*).
2. **Terraform State State-Lock Guarding**:
   - Menambahkan aturan Rego yang mewajibkan seluruh database production mengaktifkan parameter `deletion_protection = true` pada atribut HCL.
   - Pengecualian penghapusan (*break-glass*) mewajibkan *cryptographic sign-off* via Pull Request yang disetujui serentak oleh *Principal SRE* dan *Head of Security* menggunakan GPG keys yang valid.
3. **Hasil**:
   - Menangkap 14 potensi *accidental destruction* database dan bucket data analytics dalam kurun waktu 12 bulan berikutnya tanpa ada insiden *unplanned data loss* berulang.

---

### 9. Trade-offs

Mengoperasikan dynamic policy enforcement dalam skala enterprise menuntut kompromi arsitektural:

```
                  [AGILITY]
                     ▲
                    / \
                   /   \
                  /     \
                 /  Trade \
                /   Space  \
               /            \
  [SECURITY]  ◄──────────────►  [COMPUTATION COST/LATENCY]
```

1. **Security vs Agility (Developer Friction)**:
   - *Strict Guardrails*: Menerapkan kegagalan instan (*hard blocking*) pada setiap pelanggaran kecil memicu *alert fatigue* dan memperlambat laju rilis fitur tim produk.
   - *Mitigasi*: Pisahkan kebijakan ke dalam tingkat *warning* (soft policy di PR comment) dan *hard-gate* (hanya untuk ancaman kritis seperti isolasi jaringan dan enkripsi data).

2. **Parsing Raw HCL vs Plan JSON Output**:
   - *Raw HCL Parsing (misal: TF12 raw AST)*:
     - *Kelebihan*: Sangat cepat, dapat dieksekusi sebelum `terraform init` (tanpa butuh akses API Cloud).
     - *Kekurangan*: Buta terhadap referensi variabel dinamis, modul eksternal, *computed values*, dan logika *interpolation*.
   - *Plan JSON Analysis*:
     - *Kelebihan*: Akurasi 100% mutlak; memperlihatkan konfigurasi final yang akan diaplikasikan cloud engine.
     - *Kekurangan*: Latensi tinggi; pipeline harus menjalankan autentikasi cloud dan eksekusi `terraform plan` lengkap (membutuhkan waktu beberapa menit).

3. **Performance & Latency Evaluation**:
   - Repositori IaC monolitik dengan 2.000 resource menghasilkan file `tfplan.json` berukuran puluhan megabyte (>50MB). Evaluasi AST Rego dengan iterasi bersarang (*nested loops*) yang tidak dioptimalkan dapat memakan waktu evaluasi >10 menit dan memicu *OOM (Out-of-Memory)* pada runner CI.
   - *Mitigasi*: Menulis aturan Rego berbasis set (*lookup table/indexing*), hindari penggunaan loop rekursif ganda `input.resource_changes[_]`.

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum:
1. **Mengabaikan Blok `planned_values` vs `resource_changes`**:
   Banyak *policy engineer* salah mengevaluasi `input.planned_values`. Blok ini tidak memuat operasi tindakan (`actions: ["create", "delete"]`). Pemeriksaan wajib dilakukan pada `input.resource_changes` untuk memverifikasi apakah sebuah resource sedang diubah, dibuat, atau dihancurkan.
2. **Loop Iterasi Rego Tanpa Filtering Mode**:
   Lupa memfilter `resource.mode == "managed"`. Terraform plan juga mencakup data blocks (`resource.mode == "data"`). Menjalankan rule mutasi konfigurasi pada *data source* akan menghasilkan *false positives*.
3. **Mengabaikan Evaluasi Kasus `null` / `missing attribute`**:
   Di Rego, jika sebuah atribut tidak didefinisikan dalam Terraform code, merujuk langsung ke `resource.change.after.some_attribute` akan menghasilkan *undefined evaluation* (bukan `false`), yang menyebabkan rule terabaikan secara diam-diam (*silent pass*).

#### Troubleshooting Playbook:
* **Issue**: OPA menghasilkan evaluasi `allow: false`, tetapi tidak ada pesan *error* pada array `violations`.
  - *Akar Masalah*: Sintaksis aturan Rego memicu *undefined failure* di dalam tubuh *rule aggregator*, sehingga default fallback terpicu tanpa mengisi set *deny*.
  - *Solusi*: Jalankan debugging lokal via OPA CLI:
    ```bash
    opa eval --data policy.rego --input tfplan.json "data" --format pretty
    ```
* **Issue**: CI Runner mengalami *Out of Memory* saat mengeksekusi `ci_policy_checker.py`.
  - *Solusi*: Filter file `tfplan.json` menggunakan `jq` sebelum evaluasi untuk membuang artefak konfigurasi yang tidak relevan (misal metadata `provider_config` dan state lampau yang besar):
    ```bash
    jq '{resource_changes: .resource_changes}' tfplan.json > tfplan_compact.json
    ```

---

### 11. Best Practices (Production Checklist)

#### Pre-Commit & Code Hygiene
- [ ] Developer dilarang keras menyimpan kredensial/rahasia dalam HCL; aktifkan validasi lokal Git Guardian / TruffleHog.
- [ ] Seluruh resource IaC wajib menurunkan *baseline module* perusahaan yang sudah diaudit oleh Cloud Platform Team.

#### CI/CD Pipeline Enforcement
- [ ] Pisahkan permission: Runner CI untuk *Policy Testing* beroperasi dalam mode *Read-Only* terhadap Cloud Provider.
- [ ] Simpan binary OPA dan dependencies scanner dalam *hardened internal container base image*.
- [ ] Aturan OPA tidak ditarik via `curl` bebas dari internet; verifikasi integritas menggunakan digest SHA256 atau image OCI tersertifikasi.
- [ ] Terapkan pelaporan hasil evaluasi policy langsung ke PR comments dengan integrasi context line file HCL yang melanggar.

#### Policy Governance
- [ ] Gunakan arsitektur *Policy-as-Code Repository* tersentralisasi yang memiliki skema rilis SemVer (misal: `v1.2.0`).
- [ ] Setiap *Rule Rego* wajib memiliki metadata formal: `rule_id`, `severity` (`INFO`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), dan tautan dokumentasi solusi perbaikan.
- [ ] Blast Radius Guard aktif secara *un-bypassable* pada seluruh *stateful resources*.

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan mensimulasikan kegagalan pipeline CI/CD produksi karena pelanggaran aturan keamanan IaC dan blast radius secara hands-on.

#### Langkah 1: Persiapan Struktur Direktori
Buat direktori kerja lokal:
```bash
mkdir -p hands-on/m02/policies hands-on/m02/terraform
cd hands-on/m02
```

#### Langkah 2: Buat Kode Infrastruktur Rentan (Vulnerable Terraform)
Simpan file berikut di `terraform/main.tf`:
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
  region                      = "ap-southeast-1"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  access_key                  = "mock_key"
  secret_key                  = "mock_secret"
}

# PELANGGARAN 1: Security Group membuka akses SSH 0.0.0.0/0
resource "aws_security_group_rule" "insecure_ssh" {
  type              = "ingress"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = "sg-12345678"
}

# PELANGGARAN 2: S3 SSE tidak menggunakan KMS CMK (hanya SSE standar)
resource "aws_s3_bucket" "data_lake" {
  bucket = "megapay-customer-pii-data-prod"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "insecure_crypto" {
  bucket = aws_s3_bucket.data_lake.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
      # kms_master_key_id tidak disetel
    }
  }
}
```

#### Langkah 3: Sintesis Terraform Plan ke JSON
Jalankan kompilasi plan secara lokal:
```bash
cd terraform
terraform init
terraform plan -out=tfplan.binary
terraform show -json tfplan.binary > ../tfplan.json
cd ..
```

#### Langkah 4: Terapkan Rego Security Guardrail
Simpan file kebijakan berikut di `policies/guardrails.rego`:
```rego
package enterprise.terraform.security

import future.keywords.if
import future.keywords.in

default allow = false

# Rule 1: Larangan SSH Terbuka
deny[reason] {
    resource := input.resource_changes[_]
    resource.type == "aws_security_group_rule"
    resource.change.actions[_] in ["create", "update"]
    
    resource.change.after.type == "ingress"
    resource.change.after.from_port <= 22
    resource.change.after.to_port >= 22
    resource.change.after.cidr_blocks[_] == "0.0.0.0/0"
    
    reason := {
        "rule_id": "SEC-NET-001",
        "severity": "CRITICAL",
        "resource": resource.address,
        "message": "Security Group Rule membuka SSH (port 22) ke publik (0.0.0.0/0)."
    }
}

# Rule 2: Wajib KMS CMK untuk Enkripsi S3
deny[reason] {
    resource := input.resource_changes[_]
    resource.type == "aws_s3_bucket_server_side_encryption_configuration"
    resource.change.actions[_] in ["create", "update"]
    
    rule := resource.change.after.rule[_]
    encryption := rule.apply_server_side_encryption_by_default[_]
    
    not is_valid_kms(encryption)
    
    reason := {
        "rule_id": "SEC-S3-002",
        "severity": "HIGH",
        "resource": resource.address,
        "message": "Enkripsi S3 wajib menggunakan aws:kms dengan Customer Managed Key (kms_master_key_id)."
    }
}

is_valid_kms(encryption) if {
    encryption.sse_algorithm == "aws:kms"
    encryption.kms_master_key_id != null
    count(encryption.kms_master_key_id) > 0
}

violations := [v | v := deny[_]]

allow if {
    count(violations) == 0
}
```

#### Langkah 5: Eksekusi Evaluasi Kebijakan
Jalankan evaluasi menggunakan OPA CLI:
```bash
opa eval --data policies/guardrails.rego --input tfplan.json "data.enterprise.terraform.security" --format pretty
```

*Expected Output*: OPA akan merespons dengan `allow: false` dan menampilkan array `violations` yang berisi detail deteksi pada `aws_security_group_rule.insecure_ssh` dan `aws_s3_bucket_server_side_encryption_configuration.insecure_crypto`.

---

### 13. Exercise

#### Level: Easy
1. Modifikasi file `policies/guardrails.rego` untuk menambahkan aturan baru:
   - Resource `aws_s3_bucket` harus memiliki atribut penamaan bucket yang diawali dengan prefix `megapay-`.
2. Lakukan pengujian terhadap file `tfplan.json` yang ada untuk memastikan aturan tersebut berfungsi.

#### Level: Medium
Buat policy Rego baru yang mengevaluasi resource `aws_db_instance`:
1. Blokir perubahan jika parameter `storage_encrypted` bernilai `false`.
2. Blokir pembuatan instans database jika `publicly_accessible` bernilai `true`.
3. Buat file `terraform/rds.tf` mock yang melanggar aturan ini, generate file JSON plan-nya, dan validasi keberhasilan deteksi policy engine Anda.

#### Level: Hard
Kembangkan mekanisme validasi dependensi relasional:
1. Sebuah resource `aws_ebs_volume` wajib diasosiasikan dengan `aws_kms_key` khusus perusahaan yang memiliki tag `KeyType: DataVolume`.
2. Telusuri graf plan JSON Terraform (`input.configuration` dan `input.resource_changes`) untuk membuktikan bahwa ID KMS Key yang di-passing ke volume EBS benar-benar dideklarasikan di dalam state dan memiliki tag yang sesuai, bukan sekadar hardcoded string ARN.

---

### 14. Challenge

**Skenario**:
Perusahaan perbankan Anda sedang melakukan migrasi dari *legacy on-premise* ke AWS multi-region. CISO menerbitkan mandat darurat menyusul ancaman *ransomware*:
> *"Dilarang keras melakukan operasi deployment apa pun jika infrastruktur tersebut menghapus backup snapshot, mengizinkan ingress dari subnet yang tidak terdaftar dalam Enterprise CIDR IPAM (10.0.0.0/8), atau memicu downscale ukuran instans database transaksi pada jam operasional."*

**Tantangan Arsitektur**:
1. Buat arsitektur pipeline terpadu (*mock pipeline script*) yang mengevaluasi input dinamis:
   - File `tfplan.json`.
   - File eksternal `ipam_approved_cidrs.json` yang diambil dari API dinamis saat evaluasi berlangsung.
   - Variabel waktu pipeline (`deployment_timestamp`).
2. Rancang aturan Rego yang:
   - Menganalisis perubahan instance class RDS (`instance_class`) dari tipe besar (misal: `db.r6g.2xlarge`) ke tipe yang lebih rendah (misal: `db.t3.medium`). Jika pipeline dieksekusi di antara pukul 08:00 - 18:00 UTC, rencana deployment harus di-block secara otomatis.
   - Memastikan tidak ada rule Ingress yang melenceng dari daftar subnet CIDR IPAM internal enterprise.
3. Seluruh evaluasi harus dijalankan secara modular menggunakan OPA unit tests (`*_test.rego`) dengan cakupan kode 100%. Tidak disediakan template dasar; Anda harus mendesain arsitektur schema input dan evaluasi Rego secara mandiri.

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Mengapa memvalidasi keamanan infrastruktur pada file `terraform plan` JSON lebih akurat dibandingkan hanya melakukan static linting pada file mentah `.tf`?
2. Pada file `tfplan.json`, apa perbedaan mendasar antara representasi array `resource_changes` dan objek `planned_values`?
3. Di dalam sintaksis OPA/Rego, apa akibat fatal jika sebuah query mengakses field JSON yang tidak dideklarasikan pada resource tanpa menggunakan konstruksi *safe traversal* atau helper function?
4. Apa fungsi dari flag `resource.mode == "managed"` pada saat kita menulis aturan Rego untuk Terraform?
5. Mengapa penyimpanan Policy-as-Code harus dipisahkan repositorinya dari repositori kode IaC tim aplikasi?

#### 5 Pertanyaan Intermediate
6. Bagaimana cara membedakan operasi *in-place update* dengan operasi *recreation (destroy-and-create)* saat menganalisis array tindakan `actions` di dalam `resource_changes`?
7. Sebutkan kelemahan utama dari pendekatan analisis keamanan IaC yang hanya berbasis pre-commit hook lokal, dan bagaimana cara memitigasinya di pipeline produksi.
8. Jelaskan skenario di mana aturan Policy-as-Code gagal mendeteksi kebocoran kredensial rahasia yang disimpan dalam file `terraform.tfstate` lokal.
9. Bagaimana strategi penanganan OPA evaluation timeouts ketika file `tfplan.json` berukuran sangat besar (>100 MB) akibat banyaknya resource dalam satu state monolitik?
10. Bagaimana Anda mengimplementasikan mekanisme *Exception/Bypass List* (misal: port 22 boleh dibuka khusus untuk Bastion Host tertentu) secara aman dan teraudit tanpa merusak integritas policy global?

#### 3 Skenario Kasus Produksi
11. **Skenario Kasus A**:
    Pipeline CI/CD Anda memproses pull request yang menghapus 20 resource non-kritis dan 1 resource tabel DynamoDB audit. Tim security mengaktifkan aturan *blast radius limit*: `count(destroy) < 5`. Jika Anda hanya menghitung total penghapusan numerik, deployment diblokir. Namun jika DynamoDB dihapus, sistem audit kolaps permanen. Bagaimana cara menstrukturkan aturan Rego yang memisahkan kuota penghapusan sumber daya *stateless* (EC2, CloudWatch Alarm) dengan perlindungan mutlak sumber daya *stateful*?
12. **Skenario Kasus B**:
    Sebuah tim rekayasa platform mengeluhkan bahwa aturan OPA mereka sering mengalami kegagalan *false positive* saat Terraform mengeksekusi modul *Third-Party* dari Terraform Registry yang menggunakan pola `count = 0` untuk conditional creation. Bagaimana representasi objek kondisional tersebut di dalam `tfplan.json` dan bagaimana cara memfilternya di Rego?
13. **Skenario Kasus C**:
    Di lingkungan produksi multi-cloud (AWS dan GCP), bagaimana merancang satu arsitektur OPA engine yang seragam agar tim keamanan tidak perlu menulis ulang aturan yang sama (seperti pelarangan CIDR `0.0.0.0/0` pada port database) untuk `aws_security_group_rule` dan `google_compute_firewall`?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Jawaban Basic:
1. File mentah `.tf` belum mengolah resolusi variabel lingkungan, modul eksternal, fungsi logika (`can`, `try`), serta evaluasi *state* saat ini. Sebaliknya, `terraform plan` JSON merupakan representasi konkret hasil kalkulasi Terraform engine terhadap perubahan yang *pasti* akan dikirimkan ke Cloud API.
2. `resource_changes` berisi delta status komparasi (operasi CRUD apa yang akan dilakukan: `create`, `update`, `delete`), sedangkan `planned_values` hanya merefleksikan proyeksi keadaan akhir infrastruktur setelah dieksekusi tanpa informasi riwayat apakah resource tersebut mengalami *recreation* atau modifikasi minor.
3. Query akan mengalami status evaluasi *undefined*. Pada Rego, *rule* yang bernilai *undefined* di dalam klausa `deny` akan dianggap tidak menghasilkan nilai, yang berujung pada lolosnya evaluasi secara keliru (*false negative / silent pass*).
4. Untuk menyaring data blocks (`data.aws_...`) dari managed resources (`aws_...`). Data blocks hanya membaca infrastruktur yang sudah ada dan tidak memutasi cloud state, sehingga biasanya tidak perlu dikenakan aturan validasi provisioning.
5. Pemisahan repositori mencegah terjadinya *conflict of interest* (di mana pengembang aplikasi dapat mengubah atau mematikan aturan keamanan sendiri) dan memungkinkan tim kepatuhan/keamanan mendistribusikan satu versi kebijakan standar ke seluruh repositori perusahaan secara tersentralisasi.

#### Jawaban Intermediate:
6. Tindakan *in-place update* direpresentasikan dengan array `["update"]`. Tindakan *recreation* (penghapusan lalu pembuatan ulang) diekspresikan dengan urutan `["delete", "create"]` atau `["create", "delete"]` pada array `actions`.
7. Pre-commit hook beroperasi di sisi klien dan dapat dilewati dengan mudah oleh developer menggunakan perintah `git commit --no-verify`. Mitigasinya adalah menerapkan *mandatory gated check* di CI server tersentralisasi yang dilindungi branch protection rule (wajib lolos sebelum PR dapat di-merge).
8. Kebocoran kredensial dalam `.tfstate` terjadi saat nilai rahasia di-generate atau dipassing sebagai *plain text input variables*. Policy engine plan validator hanya melihat rencana perubahan; jika secret sudah masuk ke dalam state backend, file state tersebut tetap terbuka untuk dibaca jika IAM backend (S3/GCS bucket) tidak diisolasi atau dienkripsi.
9. Gunakan optimasi data: Lakukan pra-pemrosesan via streaming parsing (`jq`) untuk membuang blok state masa lalu yang tidak berubah (`prior_state`), indeks aturan Rego menggunakan lookup hash-map alih-alih nested array comprehension, dan pecah Terraform monolitik menjadi micro-state IaC yang lebih terisolasi.
10. Menggunakan pola *Policy-as-Code Exception Matrix* terenkripsi (misal file `exceptions.json` yang ditandatangani KMS). File pengecualian mencantumkan `rule_id`, `resource_address`, `justification`, `expiration_date`, dan `approver`. Policy Rego memvalidasi apakah resource yang melanggar memiliki izin aktif yang belum kedaluwarsa di dalam matriks tersebut.

#### Panduan Solusi Kasus Produksi:
11. **Solusi Kasus A**:
    Pisahkan penghitungan blast radius menjadi dua matriks:
    ```rego
    stateful_types := ["aws_dynamodb_table", "aws_rds_cluster"]
    
    # Absolute veto: 0 toleransi untuk stateful
    deny[msg] {
        r := input.resource_changes[_]
        r.type in stateful_types
        r.change.actions[_] == "delete"
        msg := sprintf("Pelanggaran Kritis: Penghapusan resource stateful dilarang: %v", [r.address])
    }
    
    # Quota threshold untuk stateless
    deny[msg] {
        stateless_destroys := [r | 
            r := input.resource_changes[_]
            not r.type in stateful_types
            r.change.actions[_] == "delete"
        ]
        count(stateless_destroys) >= 5
        msg := sprintf("Blast radius stateless terlampaui: %v (Batas: 5)", [count(stateless_destroys)])
    }
    ```
12. **Solusi Kasus B**:
    Ketika resource dideklarasikan dengan `count = 0`, Terraform merepresentasikannya di `resource_changes` dengan tindakan `["no-op"]` atau menghapusnya sama sekali dari array target modifikasi runtime. Solusinya, filter eksplisit tindakan:
    ```rego
    valid_actions := ["create", "update", "delete"]
    is_active_change(resource) {
        resource.change.actions[_] in valid_actions
        not "no-op" in resource.change.actions
    }
    ```
13. **Solusi Kasus C**:
    Bangun *Normalisation Layer* (Data Adapter Pattern) di Rego. Buat modul parser perantara yang mengubah skema spesifik cloud provider menjadi struktur generik terpadu:
    ```rego
    # Normalizer AWS
    normalized_ingress[{"cidr": cidr, "port": p, "resource": r.address}] {
        r := input.resource_changes[_]
        r.type == "aws_security_group_rule"
        r.change.after.type == "ingress"
        cidr := r.change.after.cidr_blocks[_]
        p := r.change.after.from_port
    }
    # Normalizer GCP
    normalized_ingress[{"cidr": cidr, "port": p, "resource": r.address}] {
        r := input.resource_changes[_]
        r.type == "google_compute_firewall"
        r.change.after.direction == "INGRESS"
        cidr := r.change.after.source_ranges[_]
        p := r.change.after.allow[_].ports[_]
    }
    # Rule Keamanan Inti (Cloud-Agnostic)
    deny[msg] {
        rule := normalized_ingress[_]
        rule.cidr == "0.0.0.0/0"
        rule.port in [22, 3389, 5432]
        msg := sprintf("Akses port sensitif terbuka ke publik pada: %v", [rule.resource])
    }
    ```

---

### 16. Summary

Implementasi tingkat lanjut dari *IaC Security & Policy-as-Code* mengubah paradigma pengamanan infrastruktur dari pendekatan audit post-deployment yang lambat menjadi sistem gerbang komputasi (*automated computational guardrails*) yang deterministik. 

Kunci arsitektur enterprise yang sukses terletak pada pemanfaatan representasi terstruktur *Terraform Plan JSON*, penerapan engine kebijakan deklaratif berbasis *Open Policy Agent (OPA)*, pemisahan dependensi aturan dari kode aplikasi melalui *Centralized Policy Distribution*, serta penerapan *Blast Radius Limiter* untuk mencegah pemadaman sistem akibat *accidental destruction*.

Dengan mengintegrasikan pipeline pengujian kebijakan deklaratif di setiap fase siklus hidup pengembangan perangkat lunak, enterprise mampu mengeliminasi konfigurasi keliru (*misconfiguration*) langsung pada akarnya, mematuhi standar kepatuhan internasional secara otomatis, dan memberikan ruang bagi tim rekayasa untuk berinovasi tanpa mengorbankan postur keamanan sistem secara keseluruhan.