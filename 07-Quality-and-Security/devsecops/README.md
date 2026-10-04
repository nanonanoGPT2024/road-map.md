# Kurikulum DevSecOps Engineering: Dari Shift-Left Hingga Runtime Defense

Selamat datang di repositori kurikulum resmi **DevSecOps Engineering**. Kurikulum ini dirancang untuk menjembatani kesenjangan antara tim Development, Security, dan Operations melalui otomatisasi keamanan berlapis, tata kelola *supply chain*, penegakan *Policy-as-Code*, serta perlindungan runtime cloud-native modern.

---

## 1. Course Overview & Mindset

### Pergeseran Industri Menuju DevSecOps
Model pengujian keamanan tradisional berbasis *gatekeeping* di akhir siklus rilis (*penetration testing* tahunan atau *staging review*) tidak lagi relevan dalam ekosistem modern yang menuntut puluhan hingga ratusan *deployment* per hari. DevSecOps mentransformasikan fungsi keamanan dari penghambat (*blocker*) menjadi pendorong bisnis (*accelerator*) melalui otomatisasi protektif, pengujian berkelanjutan (*Continuous Verification*), dan arsitektur *Zero Trust*.

### Filosofi Inti
1. **Shift-Left Security:** Mendeteksi kerentanan pada titik interaksi paling awal (IDE pengembang, *git commit hooks*, dan *pull request*) guna menekan biaya remediabilitas dan risiko regresi kode.
2. **Security as Code (SaC):** Seluruh konfigurasi keamanan, kebijakan jaringan, manajemen identitas, dan kontrol kepatuhan dikelola secara deklaratif, terversi di dalam Git, dan divalidasi via *automated pipelines*.
3. **Continuous Feedback Loops:** Membuka transparansi telemetry keamanan bagi tim pengembang tanpa membanjiri mereka dengan *false positives*; integrasi *DefectDojo* atau platform agregasi kerentanan dengan alur kerja issue tracker (misal: Jira/GitLab Issues).
4. **Supply Chain Integrity:** Tidak ada artefak yang dipercaya tanpa validasi integritas kriptografis, verifikasi asal (*provenance*), *Software Bill of Materials* (SBOM), dan pembatasan izin dependensi pihak ketiga.
5. **Defense-in-Depth & Zero Trust Runtime:** Asumsi bahwa batas perimeter jaringan luar telah jebol (*assume breach*); setiap panggilan sistem (*syscall*), paket data jaringan *east-west*, dan identitas layanan wajib dienkripsi, diautentikasi, serta dipantau secara deterministik via eBPF dan *admission controllers*.

### Prasyarat Teknis (Prerequisites)
* Pemahaman solid mengenai Administrasi Sistem Linux (POSIX, Namespace, Cgroups, Systemd, Iptables).
* Penguasaan Git (Workflow berbasis cabang, rebase, signing commits).
* Pemahaman fundamental kontainerisasi (Docker/OCI Runtime) dan orkestrasi (Kubernetes dasar).
* Pengalaman mengonfigurasi salah satu engine CI/CD (GitHub Actions, GitLab CI, atau Jenkins).
* Penguasaan dasar bahasa pemrograman scripting atau backend (Python, Go, Node.js, atau Bash).
* Pemahaman dasar arsitektur Cloud Provider (AWS, GCP, atau Azure) dan jaringan IP.

---

## 2. Learning Roadmap

```plaintext
DevSecOps Engineering Roadmap
│
├── [01] Fondasi DevSecOps & Pemodelan Ancaman (Threat Modeling)
│    ├── Shift-Left Security & Cultural Transformation
│    ├── STRIDE, DREAD, & PASTA Frameworks
│    └── Threat Modeling as Code (PyTM, Threat Dragon)
│
├── [02] Secure Coding & Tata Kelola Repositori Git
│    ├── Secret Scanning & Pre-commit Enforcement
│    ├── Branch Protection Rules, CODEOWNERS, & Signed Commits
│    └── Hardening Git SCM Platform (Audit Log & OIDC Federation)
│
├── [03] Static Application Security Testing (SAST) & Linter Keamanan
│    ├── Analisis Statis Berbasis Pola vs AST (Abstract Syntax Tree)
│    ├── Integrasi Semgrep & SonarQube ke dalam CI/CD
│    └── Manajemen False Positive & Automated Security Quality Gates
│
├── [04] Software Supply Chain Security & Analisis Dependensi (SCA)
│    ├── Software Bill of Materials (SBOM) Generation (Syft, CycloneDX)
│    ├── Dependency Vulnerability Scanning (Trivy, Grype, OSV)
│    └── Supply Chain Integrity: Cosign, In-Toto, & Framework SLSA
│
├── [05] Dynamic Application Security Testing (DAST) & Keamanan API
│    ├── Integrasi DAST Otomatis (OWASP ZAP, Nikto) dalam Pipeline
│    ├── Pengujian Keamanan REST, GraphQL, & gRPC APIs
│    └── Fuzz Testing & Runtime Behavioral Analysis
│
├── [06] Infrastructure as Code (IaC) Security & Policy-as-Code
│    ├── Static Analysis untuk Terraform & Helm (Checkov, TFSec, KICS)
│    ├── Policy-as-Code Menggunakan Open Policy Agent (OPA) & Rego
│    └── Validasi Kepatuhan CIS Benchmarks Otomatis
│
├── [07] Container Hardening & Image Security
│    ├── Reduksi Attack Surface: Multi-stage, Distroless, Non-Root UID
│    ├── Scanning Image Registri & Vulnerability Remediation
│    └── Linux Kernel Sandboxing: AppArmor, Seccomp, & Capabilities
│
├── [08] Kubernetes Runtime Security & Admission Control
│    ├── Kubernetes Admission Controllers (OPA Gatekeeper & Kyverno)
│    ├── Runtime Threat Detection Berbasis eBPF (Falco, Tetragon)
│    └── Isolasi Pod, NetworkPolicies, & Mutasi Konteks Keamanan
│
├── [09] Cloud Security Posture Management (CSPM) & Zero Trust Identity
│    ├── Cloud Infrastructure Entitlement Management (CIEM) & IAM Least Privilege
│    ├── Audit Kepatuhan Multi-Cloud Otomatis (Prowler, ScoutSuite)
│    └── Workload Identity Federation (GCP Workload Identity, AWS IRSA)
│
└── [10] Observabilitas Keamanan, SIEM, & Incident Response Otomatis
     ├── Agregasi Log Audit & Vulnerability Management (DefectDojo)
     ├── SIEM Cloud-Native & eBPF Telemetry (Elastic, Wazuh)
     └── Automated Incident Response, SOAR, & Chaos Security Engineering
```

---

## 3. Navigasi Detail Modul

### [Bab 01: Fondasi DevSecOps & Pemodelan Ancaman (Threat Modeling)](./01-foundations-threat-modeling/)
*   **[Modul 01.1: Paradigma Shift-Left dan Arsitektur DevSecOps](./01-foundations-threat-modeling/01-shift-left-and-culture.md)**
    *   Diferensiasi DevOps vs DevSecOps; analisis biaya remediabilitas bug/kerentanan (NIST metrics).
    *   Penerapan Security Champions Program dan integrasi metrik performa keamanan (MTTD, MTTR, Vulnerability Density).
*   **[Modul 01.2: Metodologi Threat Modeling Komprehensif](./01-foundations-threat-modeling/02-threat-modeling-methodologies.md)**
    *   Dekomposisi sistem aplikasi: Data Flow Diagrams (DFD), Trust Boundaries, dan Entry Points.
    *   Aplikasi taktis framework STRIDE (*Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege*) dan kalkulasi risiko DREAD.
*   **[Modul 01.3: Threat Modeling as Code](./01-foundations-threat-modeling/03-threat-modeling-as-code.md)**
    *   Penyusunan model ancaman programatik menggunakan `pytm` (Python Threat Modeling).
    *   Ekspor arsitektur DFD otomatis ke format SVG/JSON dan integrasi hasil analisis ke dalam *Pull Request*.

### [Bab 02: Secure Coding & Tata Kelola Repositori Git](./02-secure-coding-git-governance/)
*   **[Modul 02.1: Secret Detection & Pre-commit Hooks](./02-secure-coding-git-governance/01-secret-scanning.md)**
    *   Deteksi kredensial sensitif secara lokal menggunakan `gitleaks` dan `trufflehog`.
    *   Penerapan *deterministic pre-commit framework* untuk memblokir token, API keys, dan private keys sebelum tersimpan di Git Tree.
*   **[Modul 02.2: Integritas Git, CODEOWNERS, & Signed Commits](./02-secure-coding-git-governance/02-branch-protection-and-signing.md)**
    *   Penandatanganan commit berbasis GPG dan SSH keys; verifikasi integritas commit pada server upstream.
    *   Konfigurasi Branch Protection Rules, Mandatory PR Reviews, CODEOWNERS file, dan integrasi Continuous Integration gating.
*   **[Modul 02.3: Hardening SCM Platform & Autentikasi Tanpa Password](./02-secure-coding-git-governance/03-scm-hardening-oidc.md)**
    *   Audit log SCM (GitHub/GitLab), granular token permissions (*Fine-Grained Personal Access Tokens*).
    *   Eliminasi credential jangka panjang pada CI/CD runners melalui implementasi OpenID Connect (OIDC) Federation ke Cloud Provider.

### [Bab 03: Static Application Security Testing (SAST) & Linter Keamanan](./03-sast-and-linters/)
*   **[Modul 03.1: Mekanisme SAST: Pola Regex vs Abstract Syntax Tree (AST)](./03-sast-and-linters/01-sast-mechanisms.md)**
    *   Prinsip kerja parser kode statis, analisis leksikal, Semantic Analysis, Control Flow Graph (CFG), dan Data Flow Tracking (Taint Analysis).
    *   Kelebihan dan keterbatasan SAST dalam mendeteksi OWASP Top 10 vulnerabilities (Injections, Deserialization, SSRF).
*   **[Modul 03.2: Implementasi Ruleset Semgrep Kustom & SonarQube](./03-sast-and-linters/02-semgrep-sonarqube-pipeline.md)**
    *   Penulisan Custom Security Rules pada Semgrep berbasis sintaks target (Python/Go/Java) untuk mendeteksi *insecure patterns* internal.
    *   Integrasi SonarQube / SonarCloud dalam pipeline CI/CD untuk analisis *clean code* dan kerentanan bersamaan.
*   **[Modul 03.3: False Positive Triage & Quality Gate Automation](./03-sast-and-linters/03-triage-and-quality-gates.md)**
    *   Strategi manajemen *baseline scanning* untuk legacy repositories.
    *   Konfigurasi ambang batas (*Quality Gates*) yang membatalkan build secara otomatis jika ditemukan *Critical/High* security severity.

### [Bab 04: Software Supply Chain Security & Analisis Dependensi (SCA)](./04-sca-supply-chain/)
*   **[Modul 04.1: Software Bill of Materials (SBOM) Generation & Parsing](./04-sca-supply-chain/01-sbom-standards.md)**
    *   Standarisasi format SBOM: SPDX vs CycloneDX.
    *   Automasi pembuatan SBOM dari kode sumber, binary, dan image kontainer menggunakan `Syft` dan `CycloneDX CLI`.
*   **[Modul 04.2: Dependency Vulnerability Scanning & License Compliance](./04-sca-supply-chain/02-dependency-scanning.md)**
    *   Audit dependensi pihak ketiga menggunakan Trivy, Grype, dan OWASP Dependency-Check.
    *   Deteksi risiko lisensi (GPL violation) dan integrasi automasi *patching* dependensi (Dependabot / Renovate).
*   **[Modul 04.3: Integritas Rantai Pasok: Cosign, In-Toto, & SLSA Framework](./04-sca-supply-chain/03-slsa-and-cosign.md)**
    *   Framework Supply-chain Levels for Software Artifacts (SLSA level 1-4).
    *   Implementasi *keyless signing* dan verifikasi artefak kontainer menggunakan Cosign, Fulcio, dan Rekor (Sigstore ecosystem).

### [Bab 05: Dynamic Application Security Testing (DAST) & Keamanan API](./05-dast-and-api-security/)
*   **[Modul 05.1: Pipeline DAST Otomatis Menggunakan OWASP ZAP](./05-dast-and-api-security/01-owasp-zap-pipeline.md)**
    *   Diferensiasi pendekatan Black-box, Grey-box, dan White-box.
    *   Konfigurasi OWASP ZAP baseline scan, spider scanning, dan active scan headless di dalam kontainer CI/CD runner.
*   **[Modul 05.2: Pengujian Keamanan API (REST, GraphQL, & gRPC)](./05-dast-and-api-security/02-api-security-testing.md)**
    *   Eksplorasi OWASP API Security Top 10 (BOLA/IDOR, Broken Authentication, Mass Assignment).
    *   Otomatisasi pengujian API berbasis OpenAPI / Swagger specifications menggunakan ZAP API Scan dan Postman/Newman Security Tests.
*   **[Modul 05.3: Web Application Fuzzing & Profiling](./05-dast-and-api-security/03-fuzzing-runtime-behavior.md)**
    *   Fuzzing endpoint web dan API menggunakan toolkit modern (`ffuf`, `wfuzz`) untuk identifikasi error tak terdokumentasi dan *input validation bypass*.
    *   Kombinasi telemetri runtime IAST (Interactive Application Security Testing) untuk validasi kerentanan aktif.

### [Bab 06: Infrastructure as Code (IaC) Security & Policy-as-Code](./06-iac-policy-as-code/)
*   **[Modul 06.1: Static Scanning untuk Terraform, Helm, & CloudFormation](./06-iac-policy-as-code/01-iac-scanning.md)**
    *   Deteksi miskonfigurasi keamanan infrastruktur (unencrypted storage, public S3 buckets, overly permissive ingress rules) menggunakan `Checkov`, `TFSec`, dan `KICS`.
    *   Pemeriksaan drift konfigurasi (*configuration drift*) dan dampaknya terhadap *security posture*.
*   **[Modul 06.2: Open Policy Agent (OPA) & Bahasa Deklaratif Rego](./06-iac-policy-as-code/02-opa-rego-fundamentals.md)**
    *   Arsitektur decouple policy engine: Input JSON/YAML -> OPA Core -> Query Decision.
    *   Penulisan unit tests dan rules Rego kustom untuk memvalidasi rencana eksekusi (`terraform show -json`).
*   **[Modul 06.3: Automasi Kepatuhan Berbasis Standar Industri](./06-iac-policy-as-code/03-cis-benchmarks-automation.md)**
    *   Pemetaan aturan IaC ke standar CIS Benchmarks, NIST SP 800-53, dan PCI-DSS.
    *   Pembuatan gerbang penolakan otomatis (*strict rejection policy*) pada level merge request ketika terjadi deviasi konfigurasi.

### [Bab 07: Container Hardening & Image Security](./07-container-hardening/)
*   **[Modul 07.1: Konstruksi Image OCI yang Minimalis & Aman](./07-container-hardening/01-secure-dockerfiles.md)**
    *   Prinsip *Least Surface*: Multi-stage builds, Chainguard images, Google Distroless, dan Alpine Linux.
    *   Eliminasi shell, package managers, root privilege (`USER nonroot:nonroot`), dan manajemen OCI annotations.
*   **[Modul 07.2: Vulnerability Management pada Image Registry](./07-container-hardening/02-registry-scanning.md)**
    *   Mekanisme continuous scanning pada registri (Harbor, AWS ECR, GCP Artifact Registry).
    *   Penerapan kebijakan blokir (*quarantine policy*) terhadap image dengan CVE berkategori *Critical* dan patch *available*.
*   **[Modul 07.3: Isolasi Kernel: Seccomp, AppArmor, & Linux Capabilities](./07-container-hardening/03-kernel-isolation.md)**
    *   Restriksi *system calls* berbahaya menggunakan profil Seccomp default dan kustom.
    *   Penerapan AppArmor profiles dan eliminasi privilege Linux Capabilities (`cap-drop=ALL`, add spesifik yang dibutuhkan saja).

### [Bab 08: Kubernetes Runtime Security & Admission Control](./08-kubernetes-runtime-security/)
*   **[Modul 08.1: Validating & Mutating Admission Controllers](./08-kubernetes-runtime-security/01-admission-controllers.md)**
    *   Arsitektur Kubernetes API Request Lifecycle.
    *   Penegakan kepatuhan cluster menggunakan Kyverno dan OPA Gatekeeper (Memblokir `privileged: true`, mewajibkan `readOnlyRootFilesystem`, CPU/Memory limits, dan label kepatuhan).
*   **[Modul 08.2: Runtime Intrusion Detection Menggunakan Falco](./08-kubernetes-runtime-security/02-falco-runtime-detection.md)**
    *   Monitoring system calls via kernel module dan eBPF probe.
    *   Penulisan Falco custom rules untuk mendeteksi: eksekusi shell di dalam pod, pembacaan file sensitif (`/etc/shadow`), perubahan konfigurasi cron, dan koneksi ke IP mencurigakan.
*   **[Modul 08.3: Isolasi Jaringan Pod & eBPF Telemetry](./08-kubernetes-runtime-security/03-cilium-tetragon-defense.md)**
    *   Penerapan Zero Trust Network Policies (K8s NetworkPolicy dan Cilium CNI L3/L4/L7 policies).
    *   Observabilitas proses runtime mendalam dan *process kill enforcement* real-time menggunakan Cilium Tetragon.

### [Bab 09: Cloud Security Posture Management (CSPM) & Zero Trust Identity](./09-cspm-cloud-security/)
*   **[Modul 09.1: Cloud Infrastructure Entitlement Management (CIEM)](./09-cspm-cloud-security/01-cloud-iam-least-privilege.md)**
    *   Analisis hak akses berlebih (*over-privileged roles*) pada AWS IAM, GCP IAM, dan Azure Entra ID.
    *   Otomatisasi pemangkasan izin berbasis access review logs dan permission boundary.
*   **[Modul 09.2: CSPM Scanners & Continuous Audit](./09-cspm-cloud-security/02-cspm-scanning-prowler.md)**
    *   Eksekusi automated audit scanning multi-cloud menggunakan `Prowler`, `ScoutSuite`, atau `Trivy Cloud`.
    *   Kalkulasi Cloud Security Score dan pelaporan deviasi postur cloud terhadap SOC2 Type II dan ISO 27001.
*   **[Modul 09.3: Workload Identity Federation Tanpa Long-lived Secrets](./09-cspm-cloud-security/03-workload-identity-federation.md)**
    *   Integrasi Pod Kubernetes dengan peran Cloud IAM menggunakan AWS IRSA (IAM Roles for Service Accounts) dan GCP Workload Identity.
    *   Mitigasi risiko eksfiltrasi static credentials dari environment kontainer.

### [Bab 10: Observabilitas Keamanan, SIEM, & Incident Response Otomatis](./10-observability-incident-response/)
*   **[Modul 10.1: Vulnerability Aggregation & Management dengan DefectDojo](./10-observability-incident-response/01-defectdojo-orchestration.md)**
    *   Konsolidasi hasil scanning dari SAST, SCA, DAST, dan IaC ke dalam satu dashboard terpusat.
    *   Deduping kerentanan, pelacakan metrik SLA remediabilitas tim, dan integrasi penugasan tiket otomatis (Jira API).
*   **[Modul 10.2: SIEM Integration & Log Auditing Multi-Sumber](./10-observability-incident-response/02-siem-audit-logging.md)**
    *   Pengumpulan dan agregasi Kubernetes Audit Logs, CloudTrail, dan Falco events menggunakan Fluent Bit / Logstash ke Elasticsearch / Wazuh SIEM.
    *   Penyusunan security alerting berbasis threshold dan korelasi log anomali.
*   **[Modul 10.3: Automated Remediation, SOAR, & Chaos Security Engineering](./10-observability-incident-response/03-soar-chaos-security.md)**
    *   Implementasi webhook-based remediation (misal: otomatis mengisolasi node/pod yang terinfeksi ketika Falco mendeteksi anomali).
    *   Pengujian ketahanan pertahanan menggunakan Chaos Security Engineering: simulasi injeksi kegagalan konfigurasi dan serangan red-team sintetis.

---

## 4. Spesifikasi Capstone Project Enterprise

### Gambaran Kasus
Peserta wajib membangun arsitektur **Enterprise Polyglot DevSecOps Pipeline & Runtime Defense Platform** untuk platform aplikasi *Core Financial Banking* (terdiri dari backend berbasis Go/gRPC, frontend Next.js, dan database PostgreSQL) yang di-deploy ke cluster Kubernetes target (k3s / EKS / GKE).

```plaintext
[ Developer Git Push ]
        │
        ▼ (Gitleaks, Commit Signing Check)
[ CI Engine: GitHub Actions / GitLab CI ]
        │
        ├── Step 1: SAST (Semgrep) ──► Fail on High/Critical
        ├── Step 2: SCA (Trivy + Syft SBOM) ──► Generate CycloneDX
        ├── Step 3: IaC Audit (Checkov + OPA Rego) ──► Block Misconfig
        ├── Step 4: Container Build (Distroless, Non-Root)
        └── Step 5: Provenance & Signing (Cosign Sigstore)
        │
        ▼
[ OCI Registry: Harbor / ECR / GHCR ] (Signed Image + SBOM Attached)
        │
        ▼
[ CD Deployment: ArgoCD ]
        │
        ▼
[ Kubernetes Target Cluster ]
        ├── Admission Control: Kyverno / OPA Gatekeeper (Verifikasi Cosign Signature)
        ├── Network Segmentation: Cilium L3-L7 Zero Trust Policies
        ├── Runtime Defense: Falco + Cilium Tetragon (eBPF)
        └── Auditing & Visibility: DefectDojo + SIEM (Wazuh / Elastic)
```

### Rincian Komponen Arsitektur & Kriteria Wajib

1. **Shift-Left Security Verification:**
   * Repositori dikonfigurasi dengan *pre-commit hooks* (`gitleaks`, `shellcheck`, linter kode).
   * Pull Request hanya dapat di-*merge* jika lolos verifikasi branch protection: minimal 1 review, status checks hijau, dan commit berstatus *Verified*.

2. **Automated Pipeline Security (CI):**
   * **Secret Scanning:** `Trufflehog` atau `Gitleaks` memindai seluruh *commit history*.
   * **SAST:** `Semgrep` menjalankan rule standar dan minimal 3 *custom organization-specific rules*. Menolak eksekusi build bila ditemukan *CWE-89 (SQL Injection)* atau *CWE-798 (Hardcoded Credentials)*.
   * **SCA & SBOM:** Pembuatan file SBOM format CycloneDX via `Syft` yang diarsipkan sebagai *pipeline artifact*. Pemindaian kerentanan pustaka via `Grype` atau `Trivy`.
   * **IaC Scanning:** File Terraform / Kubernetes Manifests / Helm charts dipindai via `Checkov` dengan compliance policy OPA/Rego custom.
   * **Image Signing & Provenance:** Menggunakan `Cosign` untuk menandatangani image digest dan mengunggah *attestation* ke OCI registry.

3. **Kubernetes Runtime Defense & Admission Control (CD & Runtime):**
   * **Admission Enforcement:** `Kyverno` atau `OPA Gatekeeper` memvalidasi bahwa hanya image yang memiliki tanda tangan kriptografis dari keyless Cosign yang diizinkan untuk berjalan di cluster.
   * **Pod Hardening:** Pod dilarang berjalan sebagai root, root filesystem harus *read-only*, dan seluruh Linux Capabilities harus di-*drop*.
   * **Runtime Threat Detection:** `Falco` dikonfigurasi aktif dengan notifikasi real-time ke channel alert (Slack / Webhook) apabila terjadi percobaan spawn shell di dalam container atau akses ke direktori `/root`.
   * **Network Policies:** Implementasi *default-deny all ingress and egress*, hanya membuka akses komunikasi antar pod yang diizinkan secara eksplisit.

4. **Security Telemetry & Aggregation:**
   * Seluruh log temuan kerentanan pipeline CI/CD (SAST, SCA, IaC) diekspor secara terprogram via API ke instance `DefectDojo`.
   * Log aktivitas runtime Kubernetes dan event Falco diagregasikan ke dalam SIEM (*Wazuh* atau *Elasticsearch*).

### Deliverables Proyek
1. **Source Code Repository:**
   * File `.pre-commit-config.yaml` yang fungsional.
   * Definisi CI/CD pipeline (`.github/workflows/*.yml` atau `.gitlab-ci.yml`).
   * Custom Rules: Semgrep (`.semgrep/rules.yaml`), OPA Rego (`policy/*.rego`), Falco (`falco_rules.local.yaml`).
2. **Infrastructure as Code Manifests:**
   * Script Terraform/OpenTofu dan Kubernetes Manifests lengkap dengan profil keamanan (Seccomp, Capabilities, SecurityContext).
3. **Enterprise Security Audit Report (PDF/Markdown):**
   * Bukti mitigasi risiko (Screenshot log pipeline yang menolak commit rentan).
   * Laporan ringkasan SBOM dan mitigasi CVE dari DefectDojo.
   * Dokumentasi investigasi insiden simulasi serangan runtime (Falco breach detection demo).

---

## 5. Standar Kontribusi & Lisensi

Proyek silabus ini dikembangkan untuk komunitas engineer profesional. Silakan ajukan *Pull Request* atau *Issue* sesuai dengan panduan kontribusi resmi di repositori ini.

Lisensi di bawah [MIT License](LICENSE). Hak Cipta (c) 2024 Tim DevSecOps Curriculum Architect.