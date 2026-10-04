# Kurikulum DevOps Beginner: Dari Fondasi Kultur Hingga Otomasi Enterprise

Selamat datang di repositori kurikulum resmi **DevOps Beginner**. Program pembelajaran ini dirancang khusus untuk membangun fondasi teknis yang kokoh, terstruktur, dan berstandar industri bagi calon DevOps Engineer, Site Reliability Engineer (SRE), dan Platform Engineer.

---

## 1. Course Overview & Mindset

DevOps bukan sekadar kumpulan alat (*tools*) seperti Docker atau Kubernetes; DevOps adalah integrasi filosofis antara kultur, praktik rekayasa perangkat lunak, dan otomatisasi infrastruktur untuk mempercepat siklus pengiriman perangkat lunak dengan keandalan (*reliability*) tinggi.

### Pola Pikir Utama (Core Mindsets)
* **Systems Thinking (The First Way):** Memahami alur kerja secara holistik dari kode sumber hingga sampai ke tangan pengguna akhir tanpa menimbulkan *bottleneck* lokal.
* **Amplify Feedback Loops (The Second Way):** Memperpendek dan mempercepat umpan balik teknis melalui pengujian terotomatisasi, *code review*, dan pemantauan waktu-nyata (*real-time monitoring*).
* **Culture of Continual Experimentation and Learning (The Third Way):** Mentolerir kegagalan yang terkendali, mengotomatisasi mitigasi, dan mengubah insiden operasional menjadi materi evaluasi tanpa menyalahkan individu (*blameless post-mortem*).
* **Shift-Left Security & Testing:** Mengintegrasikan pengujian kualitas, pemindaian kerentanan kode, dan kepatuhan konfigurasi sedini mungkin dalam siklus hidup pengembangan.
* **Idempotency & Everything as Code:** Mengelola infrastruktur, konfigurasi, kebijakan keamanan, dan *pipeline* pengiriman sepenuhnya melalui kode yang tercatat dalam version control.

---

## 2. Learning Roadmap (10 Bab)

```text
DevOps Beginner Roadmap
│
├── [Bab 01] Fondasi DevOps, Kultur, dan Siklus Hidup Perangkat Lunak
│   ├── Prinsip CALMS & The Three Ways
│   └── Transformasi SDLC: Waterfall ke Agile & DevOps
│
├── [Bab 02] Sistem Operasi Linux & Otomasi Shell Scripting
│   ├── Arsitektur Linux, Filesystem, & User Permission
│   └── Bash Scripting Tingkat Lanjut & Systemd Service
│
├── [Bab 03] Jaringan Komputer & Protokol Inti DevOps
│   ├── TCP/IP, DNS, Subnetting, & CIDR
│   └── HTTP/HTTPS, TLS/SSL, SSH, & Reverse Proxy
│
├── [Bab 04] Version Control System Terapan: Git Enterprise
│   ├── Git Internals, Branching Strategy (Git Flow, Trunk-Based)
│   └── Resolusi Konflik, Rebase, Cherry-Pick, & Semantic Versioning
│
├── [Bab 05] Kontainerisasi Aplikasi Modern Menggunakan Docker
│   ├── Arsitektur Container Engine vs Hypervisor
│   ├── Dockerfile Best Practices & Multi-Stage Builds
│   └── Docker Compose untuk Lingkungan Multi-Kontainer
│
├── [Bab 06] Continuous Integration (CI) Praktis
│   ├── Konsep Pipeline CI & Automated Testing
│   └── GitHub Actions: Workflow, Matrix Builds, Secrets, & Cache
│
├── [Bab 07] Continuous Delivery & Automated Deployment (CD)
│   ├── Manajemen Artefak & Container Registry
│   └── Strategi Rilis: Rolling Update, Blue/Green, & Canary
│
├── [Bab 08] Infrastructure as Code (IaC) Menggunakan Terraform
│   ├── Pendekatan Deklaratif vs Imperatif
│   ├── Sintaks HCL, Provider, Resource, & Variables
│   └── State Management, Lock Mechanism, & Remote Backend
│
├── [Bab 09] Fondasi Observabilitas: Metrics, Logs, & Traces
│   ├── Arsitektur Pengumpulan Metrik dengan Prometheus
│   ├── Visualisasi Dashboard & Alerting via Grafana
│   └── Sentralisasi Log Aplikasi Menggunakan Grafana Loki
│
└── [Bab 10] DevSecOps & Hardening Infrastruktur Pemula
    ├── Pengelolaan Secret Terpusat
    ├── Pemindaian Kerentanan: Static Analysis & Container CVE Scanning
    └── Prinsip Least Privilege & CIS Benchmark Hardening
```

---

## 3. Navigasi Silabus

### [Bab 01: Fondasi DevOps, Kultur, dan Siklus Hidup Perangkat Lunak](./01-fondasi-devops-dan-kultur/)
Memahami esensi kultural dan metodologi modern yang melandasi evolusi paradigma DevOps di industri.
* [01. Prinsip CALMS dan The Three Ways](./01-fondasi-devops-dan-kultur/01-prinsip-calms-dan-three-ways.md)
* [02. Dekonstruksi SDLC: Waterfall, Agile, hingga CI/CD Continuum](./01-fondasi-devops-dan-kultur/02-dekonstruksi-sdlc-dan-cicd.md)
* [03. Mengukur Efektivitas DevOps: Metrik DORA Enterprise](./01-fondasi-devops-dan-kultur/03-metrik-dora-enterprise.md)

### [Bab 02: Sistem Operasi Linux & Otomasi Shell Scripting](./02-linux-dan-shell-scripting/)
Menguasai sistem operasi dasar server produksi, hak akses, administrasi proses, dan otomasi tugas rutin.
* [01. Arsitektur Linux, Linux Filesystem Hierarchy, dan I/O Redirection](./02-linux-dan-shell-scripting/01-arsitektur-linux-dan-filesystem.md)
* [02. Manajemen User, POSIX Permissions, dan Process Signals](./02-linux-dan-shell-scripting/02-user-permissions-dan-process.md)
* [03. Pemrograman Bash Scripting Defensif & Systemd Service Management](./02-linux-dan-shell-scripting/03-bash-scripting-dan-systemd.md)

### [Bab 03: Jaringan Komputer & Protokol Inti DevOps](./03-jaringan-komputer-dan-protokol/)
Mempelajari dasar komunikasi data antar server, resolusi nama domain, keamanan jalur data, dan proxy.
* [01. Layer Jaringan: TCP/IP Stack, Subnetting, Routing, dan CIDR](./03-jaringan-komputer-dan-protokol/01-tcpip-subnetting-cidr.md)
* [02. DNS Resolution, Anatomy of HTTP/HTTPS Request, dan PKI/TLS Handshake](./03-jaringan-komputer-dan-protokol/02-dns-https-tls-handshake.md)
* [03. SSH Key Management, Firewall (UFW/Iptables), dan Nginx Reverse Proxy](./03-jaringan-komputer-dan-protokol/03-ssh-firewall-reverse-proxy.md)

### [Bab 04: Version Control System Terapan: Git Enterprise](./04-git-enterprise-vcs/)
Mengimplementasikan alur kerja kolaborasi berbasis kode yang rapi, aman, dan dapat dilacak (*auditable*).
* [01. Git Internals: Blobs, Trees, Commits, dan Head Pointer](./04-git-enterprise-vcs/01-git-internals-dan-arsitektur.md)
* [02. Pola Percabangan: GitFlow vs Trunk-Based Development](./04-git-enterprise-vcs/02-branching-strategies.md)
* [03. Advanced Git Operations: Interactive Rebase, Bisect, Hooks, dan SemVer](./04-git-enterprise-vcs/03-advanced-git-dan-semver.md)

### [Bab 05: Kontainerisasi Aplikasi Modern Menggunakan Docker](./05-kontainerisasi-docker/)
Mengisolasi *runtime* aplikasi ke dalam kontainer yang portabel, ringan, dan siap didistribusikan.
* [01. Mekanisme Isolasi Kernel Linux: Cgroups, Namespaces, dan Rootfs](./05-kontainerisasi-docker/01-cgroups-namespaces-arsitektur.md)
* [02. Dockerfile Engineering: Layer Caching, Non-Root Users, dan Multi-Stage](./05-kontainerisasi-docker/02-dockerfile-multistage-builds.md)
* [03. Multi-Container Orchestration: Docker Compose, Network, dan Storage Volume](./05-kontainerisasi-docker/03-docker-compose-dan-storage.md)

### [Bab 06: Continuous Integration (CI) Praktis](./06-continuous-integration/)
Membangun otomatisasi kompilasi, verifikasi kualitas kode (*linting*), dan eksekusi rangkaian tes unit/integrasi.
* [01. Anatomi Engine CI: Runner, Triggers, Jobs, Steps, dan Environment](./06-continuous-integration/01-anatomi-engine-ci.md)
* [02. Implementasi GitHub Actions: Matrix Strategy, Cache Optimizing, dan Output](./06-continuous-integration/02-github-actions-implementation.md)
* [03. Quality Gates: Linter, SonarQube Scanner, dan Automated Unit Testing](./06-continuous-integration/03-quality-gates-dan-automated-tests.md)

### [Bab 07: Continuous Delivery & Automated Deployment (CD)](./07-continuous-delivery-deployment/)
Mengotomatisasi rilis aplikasi ke lingkungan produksi secara deterministik tanpa waktu henti (*zero-downtime*).
* [01. Manajemen OCI Artifact: Docker Hub, GHCR, dan Image Signing](./07-continuous-delivery-deployment/01-manajemen-oci-registry.md)
* [02. Pola Penerapan Modern: Rolling Updates, Blue-Green, dan Canary Deployment](./07-continuous-delivery-deployment/02-deployment-strategies.md)
* [03. Continuous Deployment Otomatis via SSH/Agent ke Baremetal/Cloud VPS](./07-continuous-delivery-deployment/03-automated-vps-deployment.md)

### [Bab 08: Infrastructure as Code (IaC) Menggunakan Terraform](./08-infrastructure-as-code-terraform/)
Memetakan dan mengelola infrastruktur komputasi menggunakan kode deklaratif yang dapat diuji dan direproduksi.
* [01. Prinsip Idempotensi, Konfigurasi Deklaratif, dan Arsitektur Terraform Core](./08-infrastructure-as-code-terraform/01-prinsip-idempotensi-terraform-core.md)
* [02. HCL Foundations: Provider, Resource, Data Sources, Variables, dan Outputs](./08-infrastructure-as-code-terraform/02-hcl-syntax-dan-resources.md)
* [03. Mengelola State Files: Remote State S3/GCS, State Locking via DynamoDB](./08-infrastructure-as-code-terraform/03-terraform-state-management.md)

### [Bab 09: Fondasi Observabilitas: Metrics, Logs, & Traces](./09-fondasi-observabilitas/)
Membangun visibilitas penuh terhadap kesehatan aplikasi, performa sistem, dan pelacakan galat produksi.
* [01. Tiga Pilar Observabilitas & Arsitektur Metrik Prometheus](./09-fondasi-observabilitas/01-tiga-pilar-dan-prometheus-engine.md)
* [02. Pembuatan Dashboard Telemetri & Strategi Alerting Rule Grafana](./09-fondasi-observabilitas/02-grafana-dashboards-dan-alerting.md)
* [03. Sentralisasi Log dengan Grafana Loki dan Promtail Collector](./09-fondasi-observabilitas/03-centralized-logging-loki.md)

### [Bab 10: DevSecOps & Hardening Infrastruktur Pemula](./10-devsecops-dan-hardening/)
Menjaga postur keamanan sistem secara proaktif melalui pengujian otomatis dan praktik isolasi hak akses minimal.
* [01. Manajemen Secret Terpusat: Env Injection vs Secret Engine (Vault/GitHub Secrets)](./10-devsecops-dan-hardening/01-secret-management-strategy.md)
* [02. Static Security Analysis (SAST) & Vulnerability Scanning dengan Trivy](./10-devsecops-dan-hardening/02-sast-dan-trivy-container-scanning.md)
* [03. Hardening Server Produksi: SSH Key-Only, Fail2ban, dan CIS Benchmark](./10-devsecops-dan-hardening/03-server-hardening-cis-benchmark.md)

---

## 4. Spesifikasi Capstone Project Enterprise

### Judul Proyek
**"Automated Production Deployment Pipeline for Scalable Micro-Services Ecosystem"**

### Arsitektur Sistem

```text
[Developer] -- (git push) --> [GitHub Repo]
                                   │
                                   ├──> [CI Pipeline: GitHub Actions]
                                   │     ├── 1. Code Linting & Unit Testing
                                   │     ├── 2. SAST Scanning (Semgrep)
                                   │     ├── 3. Docker Multi-Stage Build
                                   │     ├── 4. Image Security Scan (Trivy)
                                   │     └── 5. Push Artifact to Registry (GHCR)
                                   │
                                   └──> [Terraform Engine]
                                         └── Provisioning Virtual Cloud Server (VPS),
                                             Security Group, Network, & Storage
                                                     │
                                                     ▼
                                        [Production Server (Docker Host)]
                                         ├── Nginx (Reverse Proxy + Let's Encrypt SSL)
                                         ├── Web API Service (Go/Node.js)
                                         ├── Database Engine (PostgreSQL - Isolated Net)
                                         └── Observability Stack:
                                              ├── Node Exporter
                                              ├── Promtail
                                              ├── Prometheus
                                              ├── Grafana
                                              └── Loki
```

### Kebutuhan Fungsional (Functional Requirements)
1. **Pipeline Otomatis Terintegrasi:** Setiap kode yang masuk ke branch `main` harus melewati seluruh rangkaian uji (lint, unit test, build, scan) secara otomatis sebelum diizinkan *deploy*.
2. **Zero Plaintext Secrets:** Dilarang keras menempatkan kredensial (kunci privat, kata sandi basis data, token API) di dalam repositori Git. Seluruh *secret* harus disuntikkan secara dinamis menggunakan GitHub Encrypted Secrets dan file *environment* yang aman.
3. **Reproducibility Infrastruktur:** Seluruh infrastruktur (komputasi, *firewall*, volume penyimpanan) didefinisikan menggunakan modul Terraform yang dapat dihancurkan (*destroy*) dan dibuat ulang (*apply*) tanpa konfigurasi manual.
4. **Isolasi Kontainer:** Aplikasi, basis data, dan modul pemantauan berjalan di dalam kontainer Docker terpisah yang terhubung melalui *Docker User-Defined Bridge Network* dengan prinsip isolasi port minimal.

### Kebutuhan Non-Fungsional (Non-Functional Requirements)
1. **Security & Compliance:**
   * Skor *Vulnerability Scanning* Trivy tidak boleh mengandung kategori *CRITICAL* yang belum termitigasi.
   * Server produksi mematikan autentikasi *SSH Password* (hanya menerima otentikasi kunci kriptografi ed25519) dan mengaktifkan proteksi brute-force (Fail2ban).
2. **Reliability & Self-Healing:**
   * Semua layanan Docker dikonfigurasi dengan kebijakan `restart: unless-stopped`.
   * Tersedia health check endpoint (`/healthz`) pada aplikasi yang dipantau berkala oleh reverse proxy dan Prometheus.
3. **Observabilitas Waktu-Nyata:**
   * Dashboard Grafana harus menampilkan metrik CPU, Memory, Disk I/O, Network Throughput, dan HTTP Response Code (2xx, 4xx, 5xx) secara *real-time*.
   * Peringatan (*alerts*) otomatis terkirim (misal: via Discord/Telegram/Slack webhook) apabila penggunaan CPU melampaui 80% selama 5 menit berturut-turut.

### Format Pengumpulan & Kriteria Kelulusan (Acceptance Criteria)
Untuk menyelesaikan kurikulum ini secara penuh, siswa wajib menyerahkan:
* **Repositori Kode Sumber:** Berisi kode aplikasi, `Dockerfile`, konfigurasi `docker-compose.prod.yml`, dan alur kerja `.github/workflows/pipeline.yml`.
* **Repositori/Folder Terraform:** Skrip `.tf` lengkap dan terdokumentasi rapi beserta contoh konfigurasi `terraform.tfvars.example`.
* **Dokumen Runbook Produksi (`RUNBOOK.md`):** Panduan operasional langkah demi langkah untuk melakukan *disaster recovery* jika server mengalami *crash* total.
* **Tangkapan Layar Bukti Pengujian:**
  1. Pipeline CI/CD GitHub Actions berstatus sukses (*green check*).
  2. Hasil pemindaian Trivy yang bersih.
  3. Dashboard Grafana yang menampilkan visualisasi metrik aktif dari aplikasi yang sedang melayani *traffic*.