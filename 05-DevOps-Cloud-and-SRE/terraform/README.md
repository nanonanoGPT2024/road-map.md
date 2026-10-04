# Enterprise Infrastructure as Code: Kurikulum Komprehensif Terraform & OpenTofu

Selamat datang di repositori resmi kurikulum **Enterprise Infrastructure as Code (IaC) dengan Terraform**. Silabus ini dirancang oleh *Senior Technical Curriculum Architect* untuk mentransformasi DevOps Engineer, SRE (*Site Reliability Engineer*), dan Cloud Architect menjadi pakar otomasi infrastruktur tingkat lanjut.

Materi mengacu secara ketat pada kurikulum resmi [roadmap.sh/terraform](https://roadmap.sh/terraform) serta praktik terbaik industri (*battle-tested best practices*) skala Enterprise.

---

## 1. Course Overview & Mindset

### Filosofi Infrastruktur Modern
Infrastruktur modern bukan lagi tentang mengklik konsol grafis (GUI) atau mengeksekusi skrip imperatif ad-hoc. Infrastruktur modern adalah kode: versi yang dapat di-audit, diuji secara terprogram, direplikasi dalam hitungan menit, dan dikelola secara deklaratif.

### Core Engineering Mindsets
1. **Declarative vs Imperative**: Definisikan *end-state* (apa yang Anda inginkan), bukan langkah-langkah implementasinya (bagaimana cara membuatnya). Terraform Engine bertugas mengkalkulasi selisih (*diff*) dan merencanakan grafik eksekusi (*DAG - Directed Acyclic Graph*).
2. **State as the Absolute Source of Truth**: State file bukan sekadar cache metadata, melainkan jembatan representasi antara dunia logis (kode HCL) dan dunia fisik (real-world cloud resources). Menguasai konkurensi state, locking, dan deserialisasi objek state adalah pembeda antara pemula dan arsitek senior.
3. **Zero-Drift Engineering**: Segala modifikasi di luar alur kerja GitOps dianggap cacat operasional. Infrastruktur harus memiliki deteksi deviasi otomatis (*drift detection*) dan kemampuan swa-pulih (*self-healing/reconciliation*).
4. **Shift-Left Security & Immutability**: Validasi keamanan, estimasi biaya (*FinOps*), dan analisis kepatuhan kebijakan (*Policy-as-Code*) dijalankan pada tahap pre-commit dan pull request, sebelum `terraform apply` menyentuh production environment.

---

## 2. Learning Roadmap

```text
========================================================================================
                       TERRAFORM ENTERPRISE CURRICULUM ROADMAP
========================================================================================
[BAB 01: Fondasi IaC & Arsitektur Core]
  │── 01.1 Paradigma Deklaratif & Komponen Internal Terraform
  │── 01.2 HCL2 Syntax Fundamentals & Provider Architecture
  └── 01.3 Eksekusi Siklus Hidup: Init, Plan, Apply, Destroy
        │
[BAB 02: HCL2 Deep Dive & Ekspresi Dinamis]
  │── 02.1 Sistem Tipe Data Kompleks & Validasi Struktural
  │── 02.2 Dynamic Expressions, Built-in Functions & Loops
  └── 02.3 Dynamic Blocks & Splat Expressions
        │
[BAB 03: State Architecture & Concurrency Control]
  │── 03.1 Anatomi Internal State JSON & Schema Versioning
  │── 03.2 Remote State Backends & Distributed State Locking
  └── 03.3 Advanced State Operations & Disaster Recovery
        │
[BAB 04: Resource Lifecycle & Dependency Graph Execution]
  │── 04.1 Directed Acyclic Graph (DAG) & Dependency Ordering
  │── 04.2 Meta-Arguments: count, for_each, dan depends_on
  └── 04.3 Lifecycle Management Rules & Targeted Resource Actions
        │
[BAB 05: Enterprise Module Architecture & Reusability]
  │── 05.1 Desain Modular: Standar Interface, Input & Output Contract
  │── 05.2 Module Composition, Nested Modules, dan Versioning Strategy
  └── 05.3 Private Registry Distribution & Module Testing
        │
[BAB 06: Data Sources, External State & Multi-Provider Architecture]
  │── 06.1 Remote Data Lookups & terraform_remote_state Decoupling
  │── 06.2 Multi-Provider Aliasing, Multi-Region & Multi-Cloud Setup
  └── 06.3 Integrasi Dynamic Secret Stores (HashiCorp Vault Provider)
        │
[BAB 07: Policy-as-Code, Security Scanning & Native Testing]
  │── 07.1 Static Code Analysis: TFLint, Trivy, & Checkov
  │── 07.2 Policy-as-Code (PaC) dengan Open Policy Agent (OPA) / Rego
  └── 07.3 Native Integration Testing dengan HCL `terraform test` Framework
        │
[BAB 08: Production GitOps & Enterprise CI/CD Automation]
  │── 08.1 Automasi Pipeline CI/CD: Speculative Plans & Run Tasks
  │── 08.2 GitOps Pull-Request Automation Menggunakan Atlantis
  └── 08.3 Scheduled Drift Detection & Auto-Reconciliation Workflows
        │
[BAB 09: Skalabilitas Skala Besar: Terragrunt & Monorepo Patterns]
  │── 09.1 Reduksi Duplikasi Kode (DRY) Menggunakan Terragrunt
  │── 09.2 Monorepo vs Polyrepo Architecture & Workspace Isolation
  └── 09.3 FinOps: Analisis Biaya Infrastruktur Prediktif (Infracost)
        │
[BAB 10: State Refactoring, Brownfield Migration & Custom Provider]
  │── 10.1 Refaktor Arsitektur State Menggunakan Declarative `moved` Blocks
  │── 10.2 Brownfield Ingestion: Declarative `import` Blocks & Generative IaC
  └── 10.3 Ekstensibilitas: Rancang Bangun Custom Provider Menggunakan Go
        │
========================================================================================
                     [CAPSTONE PROJECT: ENTERPRISE HYBRID CLOUD]
========================================================================================
```

---

## 3. Navigasi Detail Kurikulum

### [Bab 01: Fondasi IaC & Arsitektur Terraform Core](bab-01-fondasi-iac-arsitektur-core/README.md)
Membangun pemahaman mendalam tentang arsitektur internal Terraform, mekanisme RPC plugin, dan siklus hidup dasar eksekusi infrastruktur.
* [Modul 01.1 - Paradigma Deklaratif & Komponen Internal Terraform Core](bab-01-fondasi-iac-arsitektur-core/01-1-paradigma-deklaratif-arsitektur-internal.md): Analisis pemisahan biner antara Terraform Core dan Provider Plugins melalui protokol gRPC.
* [Modul 01.2 - HCL2 Syntax Fundamentals & Provider Architecture](bab-01-fondasi-iac-arsitektur-core/01-2-hcl2-syntax-provider-architecture.md): Struktur sintaksis HCL2, konfigurasi provider, provider version constraints, dan caching biner provider lokal.
* [Modul 01.3 - Eksekusi Siklus Hidup: Init, Plan, Apply, Destroy](bab-01-fondasi-iac-arsitektur-core/01-3-siklus-hidup-cli-execution.md): Fase inisialisasi backend, pembuatan execution plan berbasis refresh state, dan transactional apply guarantees.

### [Bab 02: HCL2 Deep Dive & Ekspresi Dinamis](bab-02-hcl2-deep-dive-ekspresi-dinamis/README.md)
Menguasai HCL2 untuk menulis kode infrastruktur yang dinamis, tahan uji, serta memiliki validasi input yang ketat.
* [Modul 02.1 - Sistem Tipe Data Kompleks & Validasi Struktural](bab-02-hcl2-deep-dive-ekspresi-dinamis/02-1-tipe-data-validasi-struktural.md): Primitive types, collection types (`list`, `map`, `set`), structural types (`object`, `tuple`), serta *custom validation rules* dengan kondisi kustom.
* [Modul 02.2 - Dynamic Expressions, Built-in Functions & Loops](bab-02-hcl2-deep-dive-ekspresi-dinamis/02-2-dynamic-expressions-functions-loops.md): Manipulasi data menggunakan string, collection, encoding functions, dan list/map comprehensions (`for` expressions).
* [Modul 02.3 - Dynamic Blocks & Splat Expressions](bab-02-hcl2-deep-dive-ekspresi-dinamis/02-3-dynamic-blocks-splat-expressions.md): Konstruksi nested block secara dinamis menggunakan `dynamic` blocks dan ekstraksi data via splat operators (`*`).

### [Bab 03: State Architecture & Concurrency Control](bab-03-state-architecture-concurrency-control/README.md)
Dekomposisi struktur state file, strategi backend jarak jauh, penguncian konkurensi terdistribusi, serta teknik pemulihan bencana state.
* [Modul 03.1 - Anatomi Internal State JSON & Schema Versioning](bab-03-state-architecture-concurrency-control/03-1-anatomi-state-schema-versioning.md): Membedah file `terraform.tfstate`, serialisasi `serial`, lineage, resource addressing, dan metadata dependencies.
* [Modul 03.2 - Remote State Backends & Distributed State Locking](bab-03-state-architecture-concurrency-control/03-2-remote-backends-state-locking.md): Arsitektur backend enterprise (AWS S3 + DynamoDB, HashiCorp Consul, GCS) dengan zero-plain-text security dan lock lease handling.
* [Modul 03.3 - Advanced State Operations & Disaster Recovery](bab-03-state-architecture-concurrency-control/03-3-state-operations-disaster-recovery.md): Eksekusi manipulasi state tingkat lanjut: `state rm`, `state mv`, `state pull`, force-unlocking, dan mitigasi korupsi state tanpa downtime.

### [Bab 04: Resource Lifecycle & Dependency Graph Execution](bab-04-resource-lifecycle-dependency-graph/README.md)
Memahami bagaimana Terraform merajut DAG, menyelesaikan relasi dependensi, dan mengontrol siklus mutasi resource secara deterministik.
* [Modul 04.1 - Directed Acyclic Graph (DAG) & Dependency Ordering](bab-04-resource-lifecycle-dependency-graph/04-1-dag-graph-dependency-ordering.md): Teori graph di balik pembuatan resource, implicit vs explicit dependencies via `depends_on`, dan visualisasi graph.
* [Modul 04.2 - Meta-Arguments: count vs for_each](bab-04-resource-lifecycle-dependency-graph/04-2-meta-arguments-count-for-each.md): Analisis perbandingan refaktor skala besar, perangkap index shift pada `count`, dan pemanfaatan `for_each` pada map/set.
* [Modul 04.3 - Lifecycle Management Rules & Targeted Actions](bab-04-resource-lifecycle-dependency-graph/04-3-lifecycle-rules-targeted-actions.md): Implementasi `create_before_destroy`, `prevent_destroy`, `ignore_changes`, dan pola targeted deployment (`-target`).

### [Bab 05: Enterprise Module Architecture & Reusability](bab-05-enterprise-module-architecture/README.md)
Membangun modul yang dapat digunakan ulang, modular, terisolasi, dan mematuhi kaidah *Semantic Versioning*.
* [Modul 05.1 - Desain Modular: Standar Interface, Input & Output Contract](bab-05-enterprise-module-architecture/05-1-desain-modular-interface-contracts.md): Standar industri perancangan modul: encapsulation, abstraction boundaries, minimal viable inputs, dan deterministic outputs.
* [Modul 05.2 - Module Composition, Nested Modules, & Versioning Strategy](bab-05-enterprise-module-architecture/05-2-module-composition-versioning.md): Anti-pattern god-module vs pattern composable building blocks, semver tagging, dan pinning source control.
* [Modul 05.3 - Private Registry Distribution & Module Testing](bab-05-enterprise-module-architecture/05-3-private-registry-module-testing.md): Hosting modul pada private registry (GitLab, GitHub Packages, Terraform Cloud) dan pipeline validasi modul otomatis.

### [Bab 06: Data Sources, External State & Multi-Provider Architecture](bab-06-datasources-external-state-multi-provider/README.md)
Mendistribusikan dependensi lintas konfigurasi, mengelola arsitektur multi-region/multi-cloud, dan menghapus hardcoded credentials.
* [Modul 06.1 - Remote Data Lookups & terraform_remote_state Decoupling](bab-06-datasources-external-state-multi-provider/06-1-remote-lookups-remote-state-decoupling.md): Strategi interkoneksi antar stack menggunakan data source dinamis vs `terraform_remote_state` read-only access.
* [Modul 06.2 - Multi-Provider Aliasing, Multi-Region & Multi-Cloud Setup](bab-06-datasources-external-state-multi-provider/06-2-multi-provider-aliasing-multi-cloud.md): Konfigurasi aliasing untuk deployment cross-region (contoh: AWS transit gateway peering) dan abstraksi multi-cloud terintegrasi.
* [Modul 06.3 - Integrasi Dynamic Secret Stores (HashiCorp Vault Provider)](bab-06-datasources-external-state-multi-provider/06-3-vault-integration-zero-secrets.md): Pola arsitektur Zero Hardcoded Secrets memanfaatkan integrasi runtime ephemeral credentials dari HashiCorp Vault.

### [Bab 07: Policy-as-Code, Security Scanning & Native Testing](bab-07-policy-as-code-security-testing/README.md)
Menjalankan validasi statis, menegakkan batas-batas kepatuhan keamanan (*governance*), dan menguji infrastruktur dengan framework testing bawaan.
* [Modul 07.1 - Static Code Analysis: TFLint, Trivy, & Checkov](bab-07-policy-as-code-security-testing/07-1-static-code-analysis-linters.md): Implementasi aturan linter terpusat, security guardrails, scanning CVE, dan deteksi miskonfigurasi IAM/S3.
* [Modul 07.2 - Policy-as-Code (PaC) dengan Open Policy Agent (OPA) / Rego](bab-07-policy-as-code-security-testing/07-2-policy-as-code-opa-rego.md): Enforcement kepatuhan enterprise (misal: mandatori tag, pembatasan instance type, pemblokiran ingress public) via OPA plan validation.
* [Modul 07.3 - Native Integration Testing dengan HCL `terraform test` Framework](bab-07-policy-as-code-security-testing/07-3-native-testing-framework.md): Penulisan skenario uji unit dan integrasi native HCL (`run` blocks, assertions, mock providers) tanpa pihak ketiga.

### [Bab 08: Production GitOps & Enterprise CI/CD Automation](bab-08-gitops-enterprise-cicd-automation/README.md)
Mengotomatiskan siklus rilis infrastruktur secara aman melalui pull-request workflow, orkestrasi GitOps, dan auditabilitas penuh.
* [Modul 08.1 - Pipeline CI/CD: Speculative Plans & Cryptographic Signatures](bab-08-gitops-enterprise-cicd-automation/08-1-cicd-pipelines-speculative-plans.md): Perancangan pipeline GitHub Actions/GitLab CI: lint, validate, speculative plan generation, dan secure artifact passing.
* [Modul 08.2 - GitOps Pull-Request Automation Menggunakan Atlantis](bab-08-gitops-enterprise-cicd-automation/08-2-gitops-automation-atlantis.md): Arsitektur Atlantis terisolasi: server-side execution, PR comment triggers, lock repository branch, dan approval gating.
* [Modul 08.3 - Scheduled Drift Detection & Auto-Reconciliation Workflows](bab-08-gitops-enterprise-cicd-automation/08-3-drift-detection-reconciliation.md): Automasi cron job audit berkala untuk mendeteksi perbedaan konfigurasi produksi vs Git repository serta alert routing (Slack/PagerDuty).

### [Bab 09: Skalabilitas Skala Besar: Terragrunt & Monorepo Patterns](bab-09-skalabilitas-terragrunt-monorepo-finops/README.md)
Mengelola ratusan resource lintas akun dan environment dengan konfigurasi yang *Don't Repeat Yourself* (DRY) dan terukur.
* [Modul 09.1 - Reduksi Duplikasi Kode (DRY) Menggunakan Terragrunt](bab-09-skalabilitas-terragrunt-monorepo-finops/09-1-terragrunt-dry-architecture.md): Abstraksi remote state otomatis, hierarki variabel inheritance (`include`, `find_in_parent_folders`), dan dependency graph antar stack.
* [Modul 09.2 - Monorepo vs Polyrepo Architecture & Workspace Isolation](bab-09-skalabilitas-terragrunt-monorepo-finops/09-2-monorepo-polyrepo-workspaces.md): Trade-off isolasi workspace CLI vs isolasi berbasis path direktori untuk multi-tenancy dan blasting radius reduction.
* [Modul 09.3 - FinOps: Analisis Biaya Infrastruktur Prediktif (Infracost)](bab-09-skalabilitas-terragrunt-monorepo-finops/09-3-finops-infracost-analysis.md): Integrasi kalkulasi biaya real-time pada tahap Pull Request untuk mencegah pembengkakan anggaran cloud sebelum apply.

### [Bab 10: State Refactoring, Brownfield Migration & Custom Provider](bab-10-refactoring-migration-custom-provider/README.md)
Menguasai skenario dunia nyata paling kompleks: refaktor arsitektur eksisting tanpa re-creation, adopsi infrastruktur brownfield, dan menulis provider Go kustom.
* [Modul 10.1 - Refaktor Arsitektur State Menggunakan Declarative `moved` Blocks](bab-10-refactoring-migration-custom-provider/10-1-refactoring-state-moved-blocks.md): Restrukturisasi modul enterprise tanpa merusak data produksi menggunakan native block HCL `moved`.
* [Modul 10.2 - Brownfield Ingestion: Declarative `import` Blocks & Generative IaC](bab-10-refactoring-migration-custom-provider/10-2-brownfield-import-generative-iac.md): Adopsi resource cloud warisan (*legacy*) ke dalam Terraform menggunakan sintaks HCL `import` terbaru secara masif.
* [Modul 10.3 - Ekstensibilitas: Rancang Bangun Custom Provider Menggunakan Go](bab-10-refactoring-migration-custom-provider/10-3-custom-provider-development-go.md): Membangun plugin provider dari nol dengan Go dan *Terraform Plugin Framework* (Schema, CRUD lifecycles, state handling).

---

## 4. Spesifikasi Capstone Project Enterprise

Sebagai tugas akhir kurikulum, peserta wajib menyelesaikan rancang bangun infrastruktur berskala produksi enterprise (*Enterprise-Grade Multi-Cloud Transit Network & Kubernetes Platform*).

```text
========================================================================================
                          ENTERPRISE CAPSTONE ARCHITECTURE
========================================================================================

    [ GIT REPOSITORY ]
           │ (PR Trigger)
           ▼
    [ ATLANTIS GITOPS SERVER ] ──> Checks: [TFLint + Trivy + Infracost + OPA Policy]
           │ (Approved & Merged)
           ▼
    [ DISTRIBUTED RUNNER ]
      State Locking: S3 + DynamoDB (KMS Encrypted)
      Secrets Management: HashiCorp Vault Integration
           │
           ├───> [ AWS Region 1 (Primary: ap-southeast-1) ]
           │       ├── Transit Gateway (TGW) Hub
           │       ├── Multi-AZ EKS Cluster (v1.29+)
           │       │     └── Karpenter Node Autoscaling (Spot/On-Demand)
           │       └── Multi-AZ Encrypted RDS Aurora PostgreSQL
           │
           ├───> [ AWS Region 2 (DR: ap-southeast-2) ]
           │       ├── Warm Standby VPC & Read Replica Aurora
           │       └── TGW Inter-Region Peering (Encrypted Transit)
           │
           └───> [ External Cloud/Monitoring Hub ]
                   └── Datadog / Grafana Cloud Integration (Metrics & Log Pipelines)
========================================================================================
```

### Kebutuhan & Spesifikasi Teknis Capstone:

1. **Struktur Modul & Manajemen Repositori**:
   * Implementasi pola **Terragrunt** atau pola **Hierarchical Monorepo** murni untuk membedakan environment `staging` dan `production` tanpa copy-paste kode.
   * Minimal 3 modul kustom buatan sendiri (*VPC Network Fabric*, *Secure EKS*, *Database Layer*) yang dipublikasikan dengan rilis berbasis Semantic Versioning (`v1.0.0`).

2. **Zero-Drift & State Security Guardrails**:
   * Remote backend dengan enkripsi server-side KMS kustom (CMK), log audit bucket aktif, dan proteksi DynamoDB state locking.
   * Tidak boleh ada hardcoded credential di kode HCL. Seluruh database passwords dan sensitive tokens harus dihasilkan dynamically via HashiCorp Vault Provider.

3. **Policy-as-Code & Quality Gates (CI/CD)**:
   * Seluruh PR harus lolos validasi **Open Policy Agent (OPA)**:
     - Larangan membuat security group dengan inbound `0.0.0.0/0` pada port database/SSH.
     - Mandatori pemberian 5 corporate tags baku: `Environment`, `Owner`, `CostCenter`, `ManagedBy=Terraform`, `Project`.
   * Analisis estimasi biaya via **Infracost** yang secara otomatis mencetak rincian perubahan biaya ke komentar PR.

4. **Day-2 Operations & Brownfield Migration**:
   * Demonstrasi skenario refaktor modul menggunakan declarative `moved` blocks tanpa menghasilkan rencana penghancuran (`0 to destroy`).
   * Mengimpor minimal 1 resource legacy (misal: AWS IAM Role atau CloudWatch Log Group) menggunakan declarative `import` block HCL 2.5+.

5. **Deliverables Akhir**:
   * Kode sumber modular lengkap di repositori Git.
   * `runbook.md` instruksi operasional disaster recovery (penanganan korupsi state dan prosedur force-unlocking).
   * Laporan audit conformance dari Checkov & Trivy (Zero High/Critical Vulnerabilities).

---

## 5. Prasyarat & Lingkungan Pengembangan

Sebelum memulai modul pada Bab 01, pastikan lingkungan kerja lokal Anda telah terpasang perangkat lunak berikut:

* **Terraform CLI**: `v1.8.0` atau lebih tinggi (atau **OpenTofu** `v1.7.0+`)
* **Go**: `v1.22+` (khusus Bab 10 Modul 10.3)
* **AWS CLI**: `v2.x` terkonfigurasi dengan role/kredensial yang sesuai
* **Tools Ekosistem**: `tflint`, `trivy`, `infracost`, `atlantis`, `conftest` (OPA)
* **Editor**: Visual Studio Code dengan ekstensi *HashiCorp Terraform* (Language Server protocol enabled)

Mulai pembelajaran Anda dari **[Bab 01: Fondasi IaC & Arsitektur Terraform Core](bab-01-fondasi-iac-arsitektur-core/README.md)**. Bangun infrastruktur Anda dengan determinisme matematis dan standar arsitektur kelas enterprise!