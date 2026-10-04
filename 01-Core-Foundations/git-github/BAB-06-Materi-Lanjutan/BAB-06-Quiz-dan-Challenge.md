# BAB 06: Quiz, Challenge, & Knowledge Check
**GitHub Platform Engineering & Governance**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Model Otentikasi dan Otorisasi Terprogram
Bandingkan arsitektur keamanan antara **GitHub Apps**, **OAuth Apps**, dan **Fine-Grained Personal Access Tokens (PATs)**. Analisis dari perspektif *token lifecycle*, model delegasi hak akses (*machine-to-machine* vs *on-behalf-of-user*), batasan *blast radius*, dan mekanisme audit logging di tingkat Enterprise!

### Soal 1.2: Paradigma GitHub Rulesets vs Classic Branch Protection
Jelaskan perbedaan struktural antara implementasi tradisional **Classic Branch Protection** dan **GitHub Repository Rulesets**. Mengapa Enterprise modern mengadopsi Rulesets untuk menegakkan *governance* skala multi-repositori, dan bagaimana mekanisme evaluasi prioritas (evaluasi multi-layer) bekerja saat terjadi benturan aturan antara level Organization dan level Repository?

### Soal 1.3: Manajemen Identitas: SAML SSO, SCIM, dan Enterprise Managed Users (EMU)
Bedah batasan arsitektural antara implementasi **SAML SSO Standar** dengan **Enterprise Managed Users (EMU)** pada GitHub Enterprise Cloud. Apa implikasi struktural EMU terhadap kolaborasi *open-source*, penamaan akun pengguna (*username normalization*), siklus hidup identitas otomatis melalui SCIM, dan isolasi tenant data perusahaan?

### Soal 1.4: Arsitektur Keamanan GitHub Actions Self-Hosted Runners
Mengapa penggunaan *ephemeral self-hosted runners* lebih direkomendasikan daripada *persistent static self-hosted runners* dalam lingkungan CI/CD Enterprise? Jelaskan risiko keamanan terkait *runner persistence*, persistensi file sistem/workspace antar-eksekusi, dan potensi eksfiltrasi token sementara (`GITHUB_TOKEN`) dalam skenario repositori publik maupun internal.

### Soal 1.5: Platform Security Posture: Push Protection dan Secret Scanning
Bagaimana mekanisme internal **Push Protection** bekerja di level transport Git (misalnya pada hook `pre-receive` di sisi server GitHub)? Jelaskan urutan pemrosesan validasi entropy/regex, verifikasi token secara real-time ke penyedia layanan pihak ketiga (partner tokens), serta trade-off performa latensi jaringan saat pengembang melakukan `git push` dengan payload ribuan commit.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Resolusi State Drift pada SCIM Deprovisioning & Orphaned Repositories
Sebuah akun insinyur senior disuspensi di Identity Provider (IdP) Okta melalui SCIM, namun pengguna tersebut masih memiliki commit signature yang valid dan tercatat sebagai *sole administrator* pada beberapa repositori internal private yang krusial. Analisis bagaimana SCIM bridge mengeksekusi *deprovisioning*, dampaknya terhadap kepemilikan aset repositori, dan rancang strategi mitigasi arsitektural untuk mencegah timbulnya *orphaned repositories* dan kebocoran akses via lingering SSH keys atau personal PATs yang dibuat sebelum suspensi.

### Soal 2.2: Debugging Bypass Matrix pada Hierarki Rulesets Multi-Layer
Sebuah repositori `payment-gateway-service` memiliki:
1. Ruleset tingkat Organisasi berstatus *Active* yang membatasi bypass hanya untuk role `Security Team`, mewajibkan 2 reviewer, dan memblokir opsi *Force Push*.
2. Ruleset tingkat Repositori yang dikonfigurasi oleh tim lokal dengan target branch yang sama, menetapkan status *Bypass List* untuk tim `Release Leads`.

Ketika seorang anggota `Release Leads` (bukan anggota `Security Team`) mencoba melakukan `git push --force-with-lease` ke branch `main`, operasi tersebut ditolak. Namun, ketika mereka mencoba me-merge Pull Request tanpa persetujuan `Security Team`, aksi tersebut berhasil dieksekusi. Bongkar logika resolusi konflik ruleset GitHub dan jelaskan mengapa anomali perilaku ini terjadi secara deterministik!

### Soal 2.3: Analisis Audit Log Streaming Latency dan Incident Forensics
Enterprise Anda mengalirkan GitHub Audit Log secara *real-time* ke SIEM (misalnya Splunk/Datadog) via HTTPS Event Collector (HEC). Terjadi insiden di mana repositori inti perusahaan diubah visibilitasnya dari *Private* menjadi *Public* selama 4 menit sebelum diubah kembali. Namun, alert keamanan baru terpicu 22 menit setelah insiden selesai.
Jelaskan potensi titik kegagalan (*bottleneck*) dalam pipeline: dari *GitHub event ingestion queue*, batasan *rate-limiting* API, hingga latensi pengiriman SIEM. Event payload spesifik apa yang harus di-query untuk mengidentifikasi siapa aktor pelaksana, alamat IP sumber, dan metode otentikasi yang digunakan?

### Soal 2.4: Mitigasi Supply Chain Attack via Workflow Poisoning (`pull_request_target`)
Perhatikan cuplikan alur kerja GitHub Actions berikut:

```yaml
on:
  pull_request_target:
    types: [opened, synchronize]

jobs:
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
      - name: Run Integration Tests
        run: |
          npm install
          npm test
        env:
          CLOUD_DEPLOY_KEY: ${{ secrets.PROD_AWS_SECRET }}
```

Jelaskan kerentanan kritis *P1/Critical Remote Code Execution & Secret Exfiltration* yang ada pada kode di atas. Bagaimana penyerang dari *forked repository* dapat mengeksploitasi workflow ini, dan bagaimana perbaikan strukturalnya dengan memisahkan *privilege contexts*?

### Soal 2.5: Handling API Rate Limits & Secondary Throttling pada Skala Enterprise
Sebuah controller kustom yang dibangun dengan Golang mengelola 3.000 repositori di GitHub Enterprise Cloud menggunakan GitHub REST/GraphQL API. Secara berkala, aplikasi menerima HTTP `403 Forbidden` dengan pesan respons `You have triggered an abuse detection mechanism` atau `Secondary Rate Limit Exceeded`, meskipun kuota hourly 5.000 request per jam belum habis.
Analisis algoritma *concurrency control*, *sliding window*, dan pola mutasi burst yang memicu pembatasan sekunder tersebut. Rancang arsitektur client-side wrapper (termasuk *backoff strategies* dan routing token pool) untuk menjamin kelangsungan sinkronisasi tanpa melanggar batas penggunaan wajar (*fair usage limits*).

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Kebocoran Kredensial Produksi dan Insiden Push Protection Bypass
**Latar Belakang:**
Sebuah tim pengembang backend di instansi perbankan sedang terburu-buru merilis hotfix untuk insiden transaksi gagal di production. Seorang insinyur secara tidak sengaja meng-commit file `.env` yang berisi private key AWS IAM dengan hak akses *AdministratorAccess*. Push Protection memblokir perintah `git push` tersebut di terminal pengembang. Karena panik mengejar target SLA pemulihan sistem, pengembang menggunakan opsi *Bypass Push Protection* dari link terminal dengan memilih alasan "False positive / Test secret". Beberapa menit kemudian, honeypot keamanan mendeteksi upaya pembuatan resource EC2 asing di AWS.

**Tugas Diagnostik & Mitigasi Anda:**
1. Rancang arsitektur proteksi preventif terpusat agar pengembang tidak memiliki otoritas bypass sepihak (*unilateral bypass*) untuk kredensial berisiko tinggi.
2. Jelaskan langkah remediasi instan yang harus dieksekusi oleh platform security engineer dalam 10 menit pertama setelah bypass terdeteksi di Audit Log.
3. Rancang mekanisme otomatis berbasis *webhook event* (`secret_scanning_alert`) untuk melakukan *automated secret revocation* langsung ke cloud provider terkait secara real-time.

---

### Skenario B: Host Compromise via Actions Self-Hosted Runner dalam Private VPC
**Latar Belakang:**
Untuk memangkas biaya komputasi cloud, tim Platform Engineering menginstal runner GitHub Actions static langsung pada satu instance EC2 besar yang berada di dalam Private Subnet VPC produksi. Instance ini memiliki IAM Instance Profile yang terasosiasi langsung dengan hak akses database RDS dan S3 bucket data finansial. Repositori tersebut mengaktifkan skrip CI otomatis untuk seluruh kontribusi branch, termasuk Pull Request dari kolaborator internal di departemen lain. Seorang penyerang internal menyisipkan payload destruktif di dalam Makefile build: `curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/` untuk mencuri temporary role credentials via IMDSv2.

**Tugas Diagnostik & Mitigasi Anda:**
1. Bedah secara menyeluruh tiga lapisan kelemahan sistemik (*defense-in-depth failure*) pada arsitektur runner di atas.
2. Rekonstruksi arsitektur runner menggunakan **Actions Runner Controller (ARC)** di Kubernetes. Jelaskan bagaimana konsep pod *ephemeral*, isolasi network policy, IMDS hop-limit, dan *OpenID Connect (OIDC)* menghilangkan total ketergantungan pada IAM credentials statis/instance profile.

---

### Skenario C: Krisis Governance dan Kegagalan Migrasi Policy-as-Code
**Latar Belakang:**
Sebuah organisasi rintisan bertransformasi menjadi korporasi dengan 1.200 pengembang, 800 mikroservis, dan 45 tim engineering. Konfigurasi repositori sebelumnya diatur secara manual oleh masing-masing *tech lead* via GitHub Web UI, mengakibatkan variasi konfigurasi: ada yang mewajibkan linear history, ada yang membebaskan *force push*, dan beberapa repositori tidak memiliki status check sama sekali.
Tim Platform Governance meluncurkan script Terraform (`terraform-provider-github`) untuk menyeragamkan seluruh repositori di bawah satu ruleset ketat: *wajib signed commits, 2 code approvals, linear history, dan merge queue aktif*.
Dampaknya: 60% pipeline deployment microservices macet seketika pada hari peluncuran. Bot otomatis (seperti Renovate dan Semantic-Release) gagal melakukan merge otomatis, commit lama non-GPG ditolak saat rebase, dan developer memprotes keras pemblokiran release darurat.

**Tugas Diagnostik & Mitigasi Anda:**
1. Analisis kesalahan fatal dalam metodologi peluncuran Policy-as-Code tim Platform Governance tersebut.
2. Buat blueprint strategi *Phased Governance Rollout* menggunakan fitur **Ruleset Enforcement Status** (*Disabled*, *Evaluate*, *Active*) dan *Target Criteria*.
3. Rancang integrasi bot automation yang kompatibel dengan aturan signed commit dan branch ruleset tanpa mengorbankan keamanan Enterprise (misalnya konfigurasi dedicated bypass actor, GitHub App bot signing keys, dan OIDC bypass conditions).

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Governance Engine & Ephemeral Runner Orchestration via Policy-as-Code

#### Problem Statement
Sebuah institusi fintech skala multi-nasional membutuhkan standardisasi tata kelola platform GitHub dari status *unmanaged* menuju arsitektur *Zero-Trust Platform Governance*. Anda ditugaskan sebagai Lead Platform Engineer untuk membangun infrastruktur governance otomatis berbasis Policy-as-Code dan mendesain lingkungan runner CI/CD yang terisolasi secara kriptografis dan jaringan.

#### Requirements
1. **Infrastructure as Code (Terraform):**
   - Buat manifest Terraform menggunakan provider `integrations/github` untuk mengonfigurasi struktur Organisasi.
   - Definisikan satu **Organization-Level Ruleset** terpusat yang:
     - Diterapkan pada seluruh repositori produksi (gunakan tagging/naming pattern `service-*`).
     - Mewajibkan branch `main` memiliki minimal 2 approver dari tim berwenang.
     - Mewajibkan seluruh status check CI lulus (minimal: Lint, Unit Test, Secret Scan).
     - Menegakkan *Commit Signature Verification* (hanya signed commits yang diterima).
     - Membatasi aktor bypass HANYA untuk satu GitHub App khusus (`Platform-Emergency-Bypass-App`).
2. **Identity & Secrets Architecture via OIDC:**
   - Hapus seluruh penggunaan long-lived cloud credentials dari GitHub Actions.
   - Buat spesifikasi konfigurasi integrasi AWS/GCP IAM Role Trust Policy menggunakan GitHub Actions OpenID Connect (OIDC) yang dibatasi secara granular berdasarkan repositori, environment (`production`), dan ref (`refs/heads/main`).
3. **Automated Governance Compliance Sentinel:**
   - Tulis sebuah skrip automasi (Go / Python / Node.js) atau GitHub Action composite yang bertindak sebagai policy validator:
     - Memindai konfigurasi repositori secara berkala via GitHub GraphQL API.
     - Mendeteksi repositori yang tidak memenuhi kepatuhan tata kelola (misal: Ruleset tidak aktif, dependabot dinonaktifkan, atau visibilitas tidak terdaftar).
     - Secara otomatis membuat issue bertiket audit keamanan dan mengirim notifikasi JSON alert ke downstream webhook endpoint.

#### Constraints
- **Zero Static Secrets:** Tidak boleh ada static Cloud Credentials (seperti `AWS_ACCESS_KEY_ID` atau GCP Service Account Keys) yang disimpan dalam GitHub Actions Secrets.
- **Strict Least Privilege:** Ruleset tidak boleh mengizinkan bypass individu (user level). Bypass hanya diizinkan via Service Principal / GitHub App.
- **Idempotency:** Kode Terraform dan script automasi governance harus sepenuhnya *idempotent* dan mampu menangani API rate-limit melalui mekanisme *exponential backoff*.

#### Expected Output
1. File HCL Terraform modular (`main.tf`, `rulesets.tf`, `teams.tf`, `variables.tf`).
2. Template AWS/GCP IAM OIDC Trust Policy JSON yang telah dikunci dengan *Subject Claim (`sub`)* yang aman.
3. Kode sumber skrip *Governance Compliance Sentinel* yang lengkap, dapat dieksekusi, dan memiliki penanganan error yang komprehensif.
4. Dokumen arsitektur singkat (Runbook Keamanan) dalam format Markdown yang memetakan matriks eskalasi hak akses saat insiden produksi terjadi.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur identitas GitHub Enterprise: Perbedaan mendasar antara GitHub Standar, SAML SSO-enabled, dan Enterprise Managed Users (EMU).
- [ ] Hierarki otentikasi mesin: Kapan harus menggunakan GitHub App, Machine User PAT, atau OIDC Federated Identity.
- [ ] Mekanisme resolusi konflik GitHub Rulesets saat diterapkan multi-level (Enterprise -> Organization -> Repository).
- [ ] Anatomi eksploitasi pipeline GitHub Actions: Vektor serangan `pull_request_target`, *script injection* via untrusted inputs (`github.head_ref`), dan *pwn requests*.
- [ ] Topologi Actions Runner: Trade-off keamanan antara GitHub-Hosted, Static Self-Hosted, dan Ephemeral Container Runners (ARC).
- [ ] Siklus hidup audit keamanan: Audit log streaming, format event schema, integrasi SIEM, dan triggering Secret Scanning alert events.
- [ ] Algoritma rate-limiting GitHub API (Primary vs Secondary limits) serta teknik optimasi kueri GraphQL untuk meminimalkan konsumsi kuota rate limit.

### Saya tidak perlu menghafal:
- [ ] Seluruh format JSON schema Audit Log untuk setiap event type individual (cukup pahami field inti: `action`, `actor`, `org`, `repo`, `created_at`).
- [ ] Detail sintaksis parameter spesifik dari ribuan atribut Terraform `github_*` provider (gunakan dokumentasi resmi Terraform registry sebagai rujukan).
- [ ] Daftar lengkap alamat IP server outbound GitHub Actions runners (gunakan endpoint API `/meta` untuk kebutuhan dinamis).

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi dan mengelola GitHub Organization & Rulesets secara deklaratif menggunakan Terraform.
- [ ] Membangun pipeline CI/CD yang terotentikasi ke Cloud Provider (AWS/GCP/Azure) menggunakan OpenID Connect (OIDC) tanpa static API keys.
- [ ] Mengonfigurasi Actions Runner Controller (ARC) berbasis Kubernetes dengan scaling otomatis yang bersifat *ephemeral*.
- [ ] Mengaudit, mendeteksi, dan meremediasi kebocoran credential di repositori menggunakan Secret Scanning Push Protection dan webhook otomatisasi.
- [ ] Menulis kueri GitHub GraphQL API tingkat lanjut untuk mengekstrak metrik tata kelola, hak akses tim, dan status kepatuhan branch protection di ratusan repositori sekaligus.