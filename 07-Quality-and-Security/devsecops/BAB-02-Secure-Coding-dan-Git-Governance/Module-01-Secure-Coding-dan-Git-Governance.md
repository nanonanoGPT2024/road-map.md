# Bab 02 Module 01: Secure Coding & Tata Kelola Repositori Git

---

## 1. Identitas Modul

* **Track**: DevSecOps Engineering & Software Supply Chain Security
* **Kategori**: `07-Quality-and-Security`
* **Bab**: 02 – Source Code Management Hardening & Pre-Flight Controls
* **Modul**: 01 – Secure Coding & Tata Kelola Repositori Git
* **Tingkat Kesulitan**: Advanced / Enterprise
* **Prasyarat**:
  * Pemahaman arsitektur Git internal (DAG, commit objects, trees, blobs, references).
  * Pengalaman operasional CI/CD Pipeline (GitHub Actions, GitLab CI, atau Jenkins).
  * Pemahaman konsep kriptografi asimetris (RSA, ECDSA, Ed25519) dan federasi identitas (OAuth 2.0 / OIDC).
  * Pengalaman dasar implementasi Public Cloud IAM (AWS IAM, GCP Cloud IAM, atau Azure AD/Entra ID).
* **Estimasi Waktu**: 8 – 10 Jam (Materi Teoretis + Implementasi Hands-on Lab)

---

## 2. Learning Objectives (LO)

Setelah menyelesaikan modul ini, peserta didik ditargetkan mampu:

* **LO-01 (Analisis)**: Mendiagnosis topologi dan attack surface pada sistem SCM (*Source Code Management*) enterprise, khususnya vektor eksfiltrasi kredensial statis dan manipulasi riwayat Git.
* **LO-02 (Evaluasi)**: Membandingkan efisiensi algoritma deteksi secret scanning berbasis Shannon Entropy vs. Regular Expression/Detector-based scanning pada artefak Git packfile dan riwayat commit.
* **LO-03 (Implementasi)**: Mengonfigurasi *Pre-commit Framework* lokal yang terintegrasi secara modular dengan Gitleaks dan linter keamanan untuk menghentikan commit secret sebelum mencapai *remote staging*.
* **LO-04 (Penerapan)**: Mengimplementasikan arsitektur *Commit Integrity* berbasis kriptografi menggunakan GPG (GNU Privacy Guard) dan SSH Signature (Ed25519) untuk mencegah *identity impersonation* di level Git object.
* **LO-05 (Desain)**: Merancang aturan *Branch Protection* bertingkat dan matriks persetujuan `CODEOWNERS` granular berbasis prinsip *Least Privilege* dan *Separation of Duties*.
* **LO-06 (Implementasi)**: Mengonfigurasi federasi identitas berbasis OpenID Connect (OIDC) antara SCM Runner dan Cloud Identity Provider guna mengeliminasi total penggunaan *Long-lived Cloud Credentials* di pipeline CI/CD.
* **LO-07 (Remediasi)**: Menjalankan protokol insiden respons forensik ketika kredensial bocor ke riwayat Git, meliputi teknik rewrite history menggunakan `git-filter-repo`, invalidasi cache, dan revokasi/rotasi kunci kriptografis.
* **LO-08 (Validasi)**: Mengaudit kepatuhan konfigurasi repositori enterprise terhadap kerangka kerja kepatuhan SLSA (*Supply-chain Levels for Software Artifacts*), CIS Software Supply Chain, dan NIST SP 800-204D.

---

## 3. Concept Map & Architecture Diagram

```
+---------------------------------------------------------------------------------------------------+
|                                  ENTERPRISE GIT SECURITY TOPOLOGY                                 |
+---------------------------------------------------------------------------------------------------+

[ LOCAL WORKSTATION ]
  |
  +--> 1. Developer Writes Code (includes credentials, sensitive patterns)
  |      |
  |      v
  +--> 2. [ Git Hook Lifecycle: pre-commit ]
  |      |-- Framework: pre-commit run
  |      |-- Scanner: Gitleaks (Entropy + Regex heuristics)
  |      +-- Failure? -> [ ABORT COMMIT ]
  |
  +--> 3. [ Git Hook Lifecycle: commit-msg ]
  |      +-- Verification: Enforce Commit Signing (SSH / Ed25519 or GPG)
  |
  +--> 4. git push origin main
         |
         v
+---------------------------------------------------------------------------------------------------+
| REMOTE SCM GATEWAY (GitHub Enterprise / GitLab Self-Hosted)                                       |
+---------------------------------------------------------------------------------------------------+
         |
         +--> 5. [ Pre-Receive / Push Protection Hook ]
         |      |-- Native Secret Scanning (Push Protection API)
         |      +-- Rejection if unencrypted high-entropy token detected
         |
         +--> 6. [ SCM Access Control & Governance Engine ]
         |      |-- Branch Protection Rules: Require Linear History, Require PR
         |      |-- Cryptographic Validation: Check commit signature against uploaded public key
         |      +-- CODEOWNERS Engine: Require >= 2 approvals from designated security owners
         |
         +--> 7. [ CI/CD Pipeline Ingestion (Pull Request Context) ]
                |-- Scan Layer 1: Gitleaks SARIF scan (PR diff base..head)
                |-- Scan Layer 2: TruffleHog (Detector verification against live APIs)
                +-- OIDC Token Minting:
                    SCM STS issues ephemeral JSON Web Token (JWT) signed by SCM Private Key
                         |
                         | OIDC Exchange (JWT: aud, sub, repository, ref)
                         v
+---------------------------------------------------------------------------------------------------+
| PUBLIC CLOUD ENVIRONMENT (AWS / GCP / Azure)                                                     |
+---------------------------------------------------------------------------------------------------+
                         |
                         +--> 8. Cloud STS / Workload Identity Federation
                                |-- Validates SCM OIDC Thumbprint & Claims
                                |-- Matches Trust Policy (Condition: StringEquals sub)
                                \-- Generates Ephemeral STS Token (15m - 1h TTL)
                                     |
                                     v
                             [ Target Infrastructure ]
```

---

## 4. Mengapa Ini Penting (Why & Business / Security Impact)

Repositori Git modern bukan sekadar tempat penyimpanan kode sumber (*source code repository*), melainkan basis orkestrasi dari rantai pasok perangkat lunak (*software supply chain*). Kerentanan pada repositori Git menimbulkan ancaman langsung terhadap postur keamanan sistem enterprise:

1. **Eksfiltrasi Rahasia Tanpa Batas (*Unbounded Credential Leakage*)**: Sekali secret (seperti AWS IAM Secret Keys, database connection strings, SSH private keys, SaaS API tokens) masuk ke dalam riwayat commit Git, secret tersebut secara otomatis terduplikasi ke seluruh clone repositori lokal milik seluruh kontributor, backup server, dan staging pipeline. Walaupun file dihapus pada commit berikutnya, Git Directed Acyclic Graph (DAG) mempertahankan blob tersebut secara permanen di riwayat commit (`.git/objects/`).
2. **Ketiadaan Repudiasi dan Pemalsuan Identitas (*Commit Impersonation*)**: Protokol Git secara default mempercayai string `user.name` dan `user.email` yang didefinisikan pada konfigurasi klien lokal (`git config`). Siapa pun dapat melakukan commit dengan menggunakan identitas nama dan email CEO, CISO, atau Lead Engineer. Tanpa validasi tanda tangan kriptografi (GPG/SSH signature), integritas kode yang diaudit menjadi tidak valid, menggagalkan audit kepatuhan SOC 2 Type II, ISO/IEC 27001, dan PCI-DSS 4.0.
3. **Bypass Tata Kelola Rilis (*Governance Bypass*)**: Tanpa *Branch Protection Rules* dan pemetaan `CODEOWNERS` yang ketat, celah eskalasi hak akses internal memungkinkan pengembang merilis kode rentan, backdoor, atau dependensi berbahaya langsung ke branch produksi tanpa peer review independen.
4. **Risiko Kredensial CI/CD Statis**: Praktik usang yang menyimpan token cloud berumur panjang (*long-lived credentials*) di dalam variabel rahasia CI/CD (`CI/CD Secrets`) menghadirkan risiko eskalasi hak akses. Apabila runner CI/CD dieksploitasi melalui injeksi perintah (*command injection*) pada pipeline spec, penyerang dapat mengekstrak kredensial tersebut dengan dampak lateral movement ke seluruh infrastruktur cloud. Federasi identitas berbasis OIDC mentransformasi model keamanan ini menjadi *zero-static-secrets*.

---

## 5. Apa Itu Konsep (What & Definisi Formal Mendalam)

### Secret Scanning
Secret scanning adalah proses inspeksi statis maupun dinamis terhadap konten repositori (teks biasa, riwayat commit, branch, tag, packfiles) untuk mendeteksi keberadaan data sensitif yang tidak terenkripsi (*cleartext credentials*). Secret scanning mengombinasikan dua metode utama:
* **Analisis Entropi Shannon**: Pengukuran tingkat keacakan (*information density*) dari suatu string karakter. String berkekuatan kriptografi tinggi (misalnya *API secret keys*, *hex-encoded private keys*) memiliki nilai entropi mendekati batas teoritis $H(X)$:
  $$H(X) = -\sum_{i=1}^{n} P(x_i) \log_2 P(x_i)$$
  Jika suatu string memiliki panjang $\ge 20$ karakter dengan nilai $H(X) > 4.5$, scanner menandainya sebagai potensi secret.
* **Pattern / Heuristic Detector**: Pengecekan berbasis ekspresi reguler (*Regular Expressions*) yang dirancang khusus untuk mencocokkan struktur prefiks unik yang diterbitkan penyedia layanan (misalnya prefiks AWS `AKIA[0-9A-Z]{16}`, Slack `xox[baprs]-[0-9]{10,13}`, GitHub Personal Access Token `ghp_[a-zA-Z0-9]{36}`).

### Pre-commit Framework
Kerangka kerja eksekusi terisolasi yang mengelola siklus hidup *client-side Git hooks*. Terletak di `.git/hooks/pre-commit`, framework ini mencegat eksekusi perintah `git commit` untuk menjalankan serangkaian static analyzer, formatter, dan credential scanner sebelum objek commit dibuat secara permanen di basis data lokal Git.

### Commit Signing (GPG & SSH)
Mekanisme penjaminan integritas dan non-repudiasi di mana pengembang menandatangani hash SHA dari objek Git commit menggunakan kunci privat asimetris (*asymmetric private key*). 
* **GPG (OpenPGP Standard / RFC 4880)**: Menggunakan Web of Trust atau public key infrastructure untuk menandatangani payload commit.
* **SSH Signing (dimulai sejak Git 2.34)**: Menggunakan kunci SSH yang ada (biasanya kurva eliptik `ed25519`) untuk menandatangani objek Git via format RFC 4251, mengurangi kompleksitas manajemen keyring PGP yang rentan terhadap overhead operasional.

### Branch Protection & CODEOWNERS
* **Branch Protection**: Kebijakan deklaratif di level SCM yang membatasi hak akses penulisan ke branch yang dilindungi (`main`, `release/*`). Aturan ini mewajibkan pemenuhan gerbang kontrol seperti linear history, penolakan force push, persyaratan status checks hijau, dan tanda tangan commit.
* **CODEOWNERS**: File konfigurasi standar (ditempatkan di root, `.github/`, atau `docs/`) yang secara deterministik memetakan jalur direktori/file (*path-based authorization*) ke pengguna atau tim teknis yang berhak memberikan persetujuan (*mandatory reviewers*).

### OIDC (OpenID Connect) Federation
Standar identitas terbuka yang dibangun di atas protokol OAuth 2.0. Di lingkungan SCM CI/CD, runner SCM bertindak sebagai Identity Provider (IdP) yang menerbitkan *cryptographically signed JSON Web Token* (OIDC Token) yang berisi klaim kontekstual eksekusi (seperti `repository`, `actor`, `ref`, `environment`). Cloud Provider STS (*Security Token Service*) memvalidasi tanda tangan JWT tersebut terhadap endpoint OIDC publik milik SCM (`jwks_uri`), lalu menukarkannya secara temporal menjadi kredensial infrastruktur cloud jangka pendek (*short-lived ephemeral tokens*).

---

## 6. Bagaimana Cara Kerjanya (How & Mekanika Internal Arsitektur)

### Mekanika Secret Scanning Engine (TruffleHog vs Gitleaks)
1. **Gitleaks**: Beroperasi sebagai binary statis cepat berbasis Go. Gitleaks mengekstrak objek `commit` dari commit graph, membaca unified diff (`patch`), dan memecah konten baris per baris. Ia mengevaluasi setiap baris terhadap rule engine terdefinisi (berisi regex pattern, batas entropi, dan allowlist). Gitleaks bekerja efisien untuk commit berskala besar, tetapi dapat menghasilkan false positive jika pola regex cocok dengan string acak non-kredensial (seperti UUID, hash kompilasi).
2. **TruffleHog (v3)**: Beroperasi dengan pendekatan verifikasi dinamis (*live credential validation*). TruffleHog membaca commit graph, membongkar packfile, mengekstraksi kandidat token menggunakan detektor native, kemudian secara asinkronus mengirimkan payload verifikasi ke endpoint API publik penyedia layanan (misalnya memanggil endpoint AWS `sts:GetCallerIdentity` atau API Slack `auth.test`). Jika API mengembalikan kode status HTTP 200 OK, TruffleHog menandai secret tersebut sebagai *Verified Leak* (kredensial aktif).

### Lifecycle Git Hooks & Pre-commit
Git hook adalah file eksekusi yang dipicu pada fase-fase kritis siklus kerja Git:

```
[ Developer Terminal ]
      |
   `git commit -m "feat: updates"`
      |
      v
1. .git/hooks/pre-commit
   - Menjalankan pre-commit framework.
   - Mengambil file yang berada di staging area (`git diff --cached`).
   - Eksekusi linter, Gitleaks, pemformat kode.
   - Status exit code:
       * 0: Lolos; lanjut ke tahap berikutnya.
       * != 0: Batalkan pembuatan commit object; kembalikan kontrol ke developer.
      |
      v
2. .git/hooks/prepare-commit-msg
   - Mengedit draf pesan commit sebelum editor teks ditampilkan.
      |
      v
3. .git/hooks/commit-msg
   - Memvalidasi format pesan commit (e.g., Conventional Commits).
      |
      v
4. .git/hooks/post-commit
   - Notifikasi lokal pasca commit dibuat.
      |
      v
   `git push origin <branch>`
      |
      v
5. .git/hooks/pre-push
   - Pengecekan sebelum data dikirim ke remote.
```

### Mekanika OIDC Federation Flow
Alur autentikasi tanpa kredensial statis berjalan melalui tahapan kriptografis berikut:

```
+-----------+            +--------------------+            +-------------------+            +---------------+
| CI Runner |            | SCM OIDC Provider  |            | Cloud Provider    |            | Cloud API /   |
| (Pipeline)|            | (GitHub / GitLab)  |            | STS (AWS / GCP)   |            | Resources     |
+-----------+            +--------------------+            +-------------------+            +---------------+
      |                            |                                 |                              |
      | 1. Request JWT Token       |                                 |                              |
      |    (Audience: sts.cloud)   |                                 |                              |
      |--------------------------->|                                 |                              |
      |                            |                                 |                              |
      | 2. Mint & Sign OIDC Token  |                                 |                              |
      |    (RS256 JWT, claims: sub)|                                 |                              |
      |<---------------------------|                                 |                              |
      |                                                              |                              |
      | 3. AssumeRoleWithWebIdentity(Token, RoleARN)                 |                              |
      |------------------------------------------------------------->|                              |
      |                                                              |                              |
      |                            | 4. Fetch Public Keys (JWKS)     |                              |
      |                            |    to verify JWT signature      |                              |
      |                            |<--------------------------------|                              |
      |                            |-------------------------------->|                              |
      |                                                              |                              |
      |                                                              | 5. Validate Claims:          |
      |                                                              |    - aud == sts.cloud        |
      |                                                              |    - iss == https://scm.com  |
      |                                                              |    - sub == repo:org/app:*   |
      |                                                              |                              |
      | 6. Return Short-Lived Credentials (AccessKey, Secret, Token) |                              |
      |<-------------------------------------------------------------|                              |
      |                                                                                             |
      | 7. Execute Authorized API Calls                                                             |
      |-------------------------------------------------------------------------------------------->|
```

---

## 7. Perbandingan Paradigma / Taksonomi Matriks

### Tabel 1: Secret Scanning Mechanism

| Fitur / Dimensi | Gitleaks | TruffleHog (v3) | SCM Native (GitHub Advanced Security) |
| :--- | :--- | :--- | :--- |
| **Mekanisme Deteksi** | Regex deterministik + Analisis Entropi Shannon. | Regex detektor + Active API Verification. | Signature regex berpemilik + Machine Learning model. |
| **Kecepatan Scanning** | Ekstrem cepat (~100k commits dalam detik). | Sedang (dibatasi oleh latensi outbound API validation). | Asinkronus (terintegrasi pada SCM backend). |
| **False Positive Rate** | Menengah hingga Tinggi (perlu tuning rules). | Sangat Rendah (karena validasi API langsung). | Rendah (model divalidasi oleh partner resmi). |
| **Offline Capability** | Penuh (100% lokal, cocok untuk pre-commit). | Terbatas (fitur verifikasi membutuhkan akses internet). | Ketergantungan penuh pada platform cloud. |
| **Deteksi Packfile Dangling** | Memerlukan argumen `--log-opts="--all"`. | Secara default memindai seluruh DAG dan git packfile. | Hanya branch aktif dan PR diff. |

### Tabel 2: Autentikasi CI/CD Runner ke Cloud

| Parameter | Long-Lived IAM User Keys | OIDC Workload Identity Federation |
| :--- | :--- | :--- |
| **Masa Berlaku Kredensial** | Statis, tidak terbatas (hingga dirotasi manual). | Dinamis, sementara (TTL 15 menit hingga 1 jam). |
| **Vektor Serangan Penyimpanan** | Rentan terekspos jika dump environment variable bocor. | Token kedaluwarsa seketika; replay attack tidak efektif. |
| **Audit Trail (CloudTrail/Log)** | Terikat pada IAM User umum (*shared identity*). | Terikat pada konteks spesifik: commit SHA, PR number, repo, actor. |
| **Kebutuhan Rotasi Kunci** | Wajib periodik (penerapan sering kali gagal/terabaikan). | Tanpa rotasi kunci manual (*keyless architecture*). |
| **Kompleksitas Implementasi** | Rendah (hanya menyalin string secret). | Menengah (memerlukan konfigurasi OIDC Trust Relationship). |

### Tabel 3: Commit Verification Technology

| Indikator | GPG (OpenPGP) | SSH Signature (`git config gpg.format ssh`) |
| :--- | :--- | :--- |
| **Algoritma Utama** | RSA 4096-bit, Ed25519 (via gnupg2). | Ed25519, ECDSA, RSA. |
| **Kompleksitas Manajemen Kunci**| Tinggi (key server sync, expiration date, gpg-agent). | Sangat Rendah (menggunakan kunci SSH yang sudah ada). |
| **Penyimpanan Kunci Publik** | Key server eksternal atau diimpor ke profil SCM. | Diunggah langsung ke akun SCM sebagai Signing Key. |
| **Kesesuaian Developer OS** | Sering bermasalah pada Windows/WSL2 boundary. | Universal di seluruh environment Unix dan Windows modern. |

---

## 8. Analisis Mendalam Attack Surface & Vector Matrix

Sistem kontrol versi Git rentan terhadap serangkaian vektor serangan rantai pasok jika tidak dikonfigurasi secara ketat:

```
+---------------------------------------------------------------------------------------------------+
| Vektor Serangan              | Mekanisme Eksploitasi                        | Dampak / Tingkat Kritis |
+------------------------------+----------------------------------------------+-------------------------+
| Dangling Commit Extraction   | Mengakses commit yang telah di-"rebase" atau | Information Disclosure  |
|                              | di-reset via hash object langsung di web API | [ HIGH ]                |
+------------------------------+----------------------------------------------+-------------------------+
| Identity Impersonation       | Menyetel `git config user.name/email` palsu  | Audit Trail Forgery     |
|                              | tanpa proteksi penandatanganan commit.       | [ MEDIUM-HIGH ]         |
+------------------------------+----------------------------------------------+-------------------------+
| Branch Protection Hijack     | Menembus approval rule via race condition    | Remote Code Execution   |
|                              | merge PR atau broad CODEOWNERS wildcard.     | [ CRITICAL ]            |
+------------------------------+----------------------------------------------+-------------------------+
| Runner Context Exfiltration  | Menginjeksi command payload di build script  | IAM Takeover            |
|                              | untuk membaca secret environment variables.  | [ HIGH ]                |
+------------------------------+----------------------------------------------+-------------------------+
| Force Push Malicious Rewrite | Melakukan `git push --force` untuk menimpa   | History Integrity Loss  |
|                              | audit history dan menyisipkan backdoor.      | [ CRITICAL ]            |
+------------------------------+----------------------------------------------+-------------------------+
```

### Forensic Walkthrough: Dangling Commit Extraction
Saat seorang pengembang melakukan commit berisi secret, lalu menyadari kesalahannya dan mengeksekusi perintah:
```bash
git reset --hard HEAD~1
git push origin main --force
```
Di sisi remote server, commit yang di-reset kehilangan pointer ref-nya (*unreferenced/dangling commit*), namun objek Git di level filesystem (`.git/objects/`) belum terhapus hingga siklus `git gc` (garbage collection) dijalankan secara manual oleh admin server. Penyerang yang mengetahui atau menebak commit hash dapat mengakses commit tersebut melalui API SCM:
```http
GET /repos/:owner/:repo/commits/:dangling_commit_sha HTTP/1.1
Host: api.github.com
Authorization: Bearer <unprivileged_read_token>
```
SCM akan tetap merender objek commit tersebut secara utuh, mengekspos secret yang dianggap telah "dihapus".

---

## 9. Code Example Sederhana (Minimal & Clear)

### Implementasi Pre-commit Hook Dasar
File `.pre-commit-config.yaml` diletakkan di root repositori untuk memfilter secret dan file sensitif sebelum masuk ke commit buffer:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: check-added-large-files
        args: ['--maxkb=500']
      - id: check-merge-conflict
      - id: detect-private-key

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.2
    hooks:
      - id: gitleaks
```

Instalasi dan aktivasi hook lokal:
```bash
# 1. Install framework pre-commit via package manager
pip install pre-commit

# 2. Registrasikan hook ke direktori internal .git/hooks/
pre-commit install

# 3. Validasi eksekusi hook terhadap seluruh file yang ada
pre-commit run --all-files
```

---

## 10. Code Example Lanjutan (Production-Ready)

### A. Enterprise Hardened Pre-Commit Configuration
File konfigurasi pre-commit terdistribusi dengan penyesuaian aturan Gitleaks kustom dan pengecekan integritas commit message:

```yaml
# .pre-commit-config.yaml (Enterprise Standard)
default_install_hook_types: [pre-commit, commit-msg]
default_stages: [commit]
fail_fast: true

repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
        args: ['--allow-multiple-documents']
      - id: check-json
      - id: check-case-conflict
      - id: detect-private-key

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.2
    hooks:
      - id: gitleaks
        args: ["--config=.gitleaks.toml", "--verbose", "--redact"]

  - repo: https://github.com/compilerla/conventional-pre-commit
    rev: v3.1.0
    hooks:
      - id: conventional-pre-commit
        stages: [commit-msg]
        args: ["feat", "fix", "chore", "refactor", "docs", "style", "test", "security"]
```

Konfigurasi kustom Gitleaks (`.gitleaks.toml`):
```toml
# .gitleaks.toml
title = "Enterprise Credential Boundary Rules"

[extend]
useDefault = true

[[rules]]
id = "enterprise-api-token"
description = "Detected Enterprise Internal API Gateway Token"
regex = '''(?i)(ent_api_[a-z0-9]{32})'''
entropy = 3.8
secretGroup = 1

[rules.allowlist]
description = "Allowlist for unit test mocks"
paths = [
  '''tests/mocks/.*''',
  '''fixtures/.*'''
]
regexes = [
  '''ent_api_mock_[0]{24}'''
]
```

### B. CI/CD Hardened Pipeline: Secret Scanning & AWS OIDC Token Exchange
Pipeline GitHub Actions (`.github/workflows/security-gate.yml`) yang aman secara kriptografi, tanpa kredensial statis, menggunakan permission *least privilege*:

```yaml
name: "Security Assurance Gate"

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

permissions:
  id-token: write   # Wajib untuk autentikasi OIDC Web Identity
  contents: read    # Membaca repositori
  security-events: write # Mengunggah laporan SARIF ke GitHub Advanced Security

jobs:
  secret-audit:
    name: "Deterministic Secret Scanning"
    runs-on: ubuntu-latest
    steps:
      - name: "Checkout Entire Git Tree"
        uses: actions/checkout@v4
        with:
          fetch-depth: 0 # Wajib fetch-depth 0 untuk membaca seluruh DAG commit

      - name: "Run Gitleaks with SARIF Output"
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITLEAKS_ENABLE_SARIF: "true"
          GITLEAKS_ENABLE_SUMMARY: "true"

      - name: "Upload Scan Results to GitHub Security Tab"
        if: failure() || success()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: results.sarif

      - name: "Execute Deep TruffleHog Verification"
        uses: trufflesecurity/trufflehog@v3.63.7
        with:
          path: ./
          base: ${{ github.event.repository.default_branch }}
          head: HEAD
          extra_args: --debug --only-verified

  cloud-deployment:
    name: "Assume Cloud Role via OIDC"
    needs: [secret-audit]
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - name: "Checkout Application"
        uses: actions/checkout@v4

      - name: "Authenticate to AWS STS via OIDC (No Static Credentials)"
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: "arn:aws:iam::123456789012:role/GitHubActionsProductionDeployer"
          aws-region: "ap-southeast-1"
          audience: "sts.amazonaws.com"
          role-session-name: "gha-deploy-${{ github.run_id }}"

      - name: "Verify Cloud Identity Context"
        run: |
          aws sts get-caller-identity
```

### C. Terraform Hardening: AWS IAM OIDC Trust Policy & GitHub Branch Protection
Konfigurasi Infrastructure-as-Code (Terraform) untuk menerapkan trust relationship OIDC yang ketat dan mengunci konfigurasi Branch Protection:

```hcl
# main.tf

# 1. GitHub OIDC Provider Definition
resource "aws_iam_openid_connect_provider" "github_actions" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  # Thumbprint resmi server CA GitHub Actions OIDC (DigiCert)
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

# 2. Strict AWS IAM Role with Claims Validation
resource "aws_iam_role" "cicd_deployer" {
  name = "GitHubActionsProductionDeployer"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github_actions.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            # Mengunci eksekusi hanya untuk repositori spesifik pada branch main
            "token.actions.githubusercontent.com:sub" = "repo:enterprise-org/core-banking-service:ref:refs/heads/main"
          }
        }
      }
    ]
  })
}

# 3. GitHub Branch Protection Enforcement
resource "github_branch_protection" "main_protection" {
  repository_id = "core-banking-service"
  pattern       = "main"

  enforce_admins                  = true
  require_signed_commits          = true
  required_linear_history         = true
  allows_force_pushes             = false
  allows_deletions                = false

  required_status_checks {
    strict   = true
    contexts = ["Deterministic Secret Scanning", "Security Assurance Gate"]
  }

  required_pull_request_reviews {
    dismiss_stale_reviews           = true
    require_code_owner_reviews      = true
    required_approving_review_count = 2
    require_last_push_approval      = true
  }
}
```

### D. Production Enterprise CODEOWNERS Architecture
File `.github/CODEOWNERS` dengan pemisahan domain risiko secara eksplisit:

```text
# Global Fallback: Seluruh perubahan wajib diulas oleh tim arsitek inti
* @enterprise-org/core-architects

# Infrastructure-as-Code & Pipeline Security: Wajib disetujui tim DevSecOps
/infra/                   @enterprise-org/cloud-platform-engineers @enterprise-org/devsecops-leads
.github/                  @enterprise-org/devsecops-leads
Dockerfile                @enterprise-org/devsecops-leads
*.tf                      @enterprise-org/cloud-platform-engineers

# Security Critical Configurations: Wajib disetujui tim AppSec
/security/                @enterprise-org/application-security
.gitleaks.toml            @enterprise-org/application-security
CODEOWNERS                @enterprise-org/application-security @enterprise-org/compliance-officers

# Database Migrations: Wajib persetujuan Database Administrator (DBA)
/src/main/resources/db/   @enterprise-org/dba-team
```

---

## 11. Diagram Alur Serangan & Mitigasi (ASCII Art)

Berikut visualisasi serangan *Compromised CI Secret via Replay Attack* dibandingkan mitigasi *Ephemeral OIDC*:

### Alur Eksploitasi: Kredensial Statis Bocor

```
[ DEVELOPER REPO ]             [ ATTACKER ]               [ CLOUD RUNNER ]           [ CLOUD ACCOUNT ]
       |                             |                           |                          |
       | 1. Komit file .env          |                           |                          |
       |    (AWS_SECRET_KEY)         |                           |                          |
       |-------------------------------------------------------->|                          |
       |                             |                           |                          |
       |                             | 2. Public API Scrape      |                          |
       |                             |    (Extract Long-Lived    |                          |
       |                             |     Keys)                 |                          |
       |                             |<--------------------------|                          |
       |                             |                                                      |
       |                             | 3. Invoke Cloud STS: sts:GetCallerIdentity           |
       |                             |    menggunakan Kunci Statis curian                   |
       |                             |----------------------------------------------------->|
       |                             |                                                      |
       |                             | 4. IAM Access Granted (Permanen, no expiration)      |
       |                             |<-----------------------------------------------------|
       |                             |                                                      |
       |                             | 5. PrivEsc & Data Exfiltration                       |
       |                             |----------------------------------------------------->|
```

### Alur Mitigasi Terkunci: OIDC + Commit Signing + Pre-Commit

```
[ DEV WORKSTATION ]            [ LOCAL PRE-COMMIT ]       [ SCM GATEWAY ]            [ CLOUD STS (OIDC) ]
       |                                |                        |                          |
       | 1. Developer saves secret      |                        |                          |
       |    git commit -S -m "feat..."  |                        |                          |
       |------------------------------->|                        |                          |
       |                                |                        |                          |
       |                                | 2. Gitleaks Check:     |                          |
       |                                |    Entropy > 4.5       |                          |
       |                                |    FAIL [Exit Code 1]  |                          |
       |                                |                        |                          |
       | 3. COMMIT BLOCKED LOKAL        |                        |                          |
       |<-------------------------------|                        |                          |
       | (Developer merotasi &          |                        |                          |
       |  menghapus secret)             |                        |                          |
       |                                |                        |                          |
       | 4. git commit -S (Signed)      |                        |                          |
       |------------------------------->| (Passes Checks)        |                          |
       |                                |                        |                          |
       | 5. git push origin main        |                        |                          |
       |-------------------------------------------------------->|                          |
       |                                                         |                          |
       |                                                         | 6. Verifikasi SSH Sig    |
       |                                                         |    & Policy CODEOWNERS   |
       |                                                         |    [SUCCESS]             |
       |                                                         |                          |
       |                                                         | 7. Mint Short-lived JWT  |
       |                                                         |    sub: repo:org/app:main|
       |                                                         |------------------------->|
       |                                                         |                          |
       |                                                         | 8. AssumeRole Granted    |
       |                                                         |    (Expired in 900s)     |
       |                                                         |<-------------------------|
```

---

## 12. Trade-offs & Security vs Usability / Performance

1. **Local Pre-commit vs Deployment Velocity**:
   * *Trade-off*: Menjalankan secret scanning dan unit tests lengkap pada hook `pre-commit` lokal memastikan kode bersih sebelum masuk remote, namun menambah latensi komit sebesar 5–30 detik per operasi. Pengembang yang frustrasi kerap melewati kontrol ini menggunakan argumen `--no-verify`.
   * *Solusi Arsitektural*: Batasi scope pre-commit hook lokal hanya untuk pengecekan berbasis fast-regex (seperti `gitleaks protect --staged`) dan simpan scanning deep-graph/live-verification (seperti TruffleHog) pada level pull request di pipeline CI.
2. **Strict Cryptographic Commit Signing vs Onboarding Friction**:
   * *Trade-off*: Mewajibkan penandatanganan commit (GPG/SSH) mencegah identity impersonation, namun pengelolaan OpenPGP key pair sering menimbulkan kendala teknis pada workstation pengembang junior.
   * *Solusi Arsitektural*: Standarisasi SSH-based commit signing (`git config gpg.format ssh`). Kunci SSH yang sudah terbiasa digunakan untuk push/pull dapat difungsikan langsung sebagai signing key tanpa ketergantungan paket perangkat lunak eksternal seperti GnuPG suite.
3. **CODEOWNERS Granularity vs Organizational Bottlenecks**:
   * *Trade-off*: Menetapkan approval tim keamanan untuk setiap perubahan file meningkatkan kontrol kepatuhan, namun dapat memicu PR bottleneck dan menghambat alur kerja tim engineering.
   * *Solusi Arsitektural*: Gunakan path wildcard spesifik. Tim keamanan hanya dijadikan reviewer wajib untuk direktori kritikal (`.github/`, `/security/`, `/infra/`, `pom.xml`, `package.json`), sementara perubahan logika aplikasi didelegasikan ke engineering lead masing-masing squad.

---

## 13. Edge Cases & Complex Failure Modes

1. **Rebase Rewriting Commit Signatures**:
   * *Gejala*: Pengembang menandatangani commit miliknya secara valid. Namun, ketika branch di-rebase atau di-*squash* via interface web GitHub oleh maintainer yang tidak menandatangani ulang perubahannya, atribut commit signature dapat hilang atau ditandatangani ulang oleh bot key GitHub (`web-flow`), menggagalkan verifikasi identitas penulis aslinya.
   * *Mitigasi*: Aktifkan aturan *Require Linear History* dan nonaktifkan opsi *Squash Merge* di level repositori, atau gunakan model *Rebase and Merge* yang mempertahankan signature commit individu pengembang.
2. **Git Packfile Obfuscation & Base64 Splitting**:
   * *Gejala*: Secret disamarkan atau dipecah ke dalam beberapa variabel:
     ```python
     part1 = "AKIA"
     part2 = "Z7SAMPLEKEYXYZ"
     aws_key = part1 + part2
     ```
   * *Analisis Kerentanan*: Scanner berbasis Regex murni gagal mendeteksi fragmen string ini karena keduanya tidak memenuhi pola panjang minimum token. Scanner Shannon Entropy juga gagal karena tingkat keacakan substring berada di bawah threshold.
   * *Mitigasi*: Integrasikan Semgrep / SAST engine pada fase linting untuk melacak *taint analysis* dan propagasi konstanta variabel string.
3. **OIDC Clock Skew & Audience Mismatch Failure**:
   * *Gejala*: Runner CI gagal mengambil kredensial STS dengan error `InvalidIdentityToken: OpenIDConnect provider's HTTPS certificate doesn't match configured thumbprint` atau `Token has expired`.
   * *Akar Masalah*: Ketidaksesuaian drift waktu NTP sistem runner virtualized dengan NTP AWS/GCP, atau rotasi SSL Root CA pada SCM provider tanpa pembaruan hash `thumbprint_list` di modul Terraform IAM OIDC.

---

## 14. Anti-Patterns & Common Vulnerabilities

### Anti-Pattern 1: Menggunakan `.gitignore` untuk Menghapus Secret yang Terlanjur Terkomit
* *Praktek Buruk*: Mengunggah file konfigurasi berisi secret, lalu baru mendaftarkan file tersebut ke `.gitignore` pada commit selanjutnya.
* *Analisis Teknis*: `.gitignore` hanya mencegah file *untracked* baru agar tidak masuk ke staging area. File yang sudah pernah terkomit tetap tersimpan di dalam commit tree Git DAG dan packfile `.git/objects/`.
* *Eksploitasi*: Penyerang menjalankan:
  ```bash
  git log -p -- .env
  ```
  Isi file yang terhapus akan langsung terlihat pada unified diff commit lama.

### Anti-Pattern 2: Menggunakan Flag Bypass `--no-verify`
* *Praktek Buruk*: Mengabaikan pre-commit hook lokal yang gagal dengan perintah:
  ```bash
  git commit -m "bypass checks" --no-verify
  ```
* *Analisis Teknis*: Kontrol sisi klien (*client-side hooks*) berada di bawah kendali penuh workstation developer dan tidak dapat dipaksakan sebagai kontrol keamanan tunggal.
* *Solusi Remediasi*: Client-side hook hanya berfungsi sebagai *fail-fast feedback loop*. Kontrol keamanan wajib ditegakkan kembali secara mutlak di sisi server melalui *Server-Side Push Protection* dan *CI/CD Pull Request Status Checks*.

### Anti-Pattern 3: Wildcard OIDC Subject Claim Trust Policy
* *Praktek Buruk*: Mengonfigurasi IAM trust policy AWS dengan klaim sub berbasis wildcard tak terbatas:
  ```json
  "Condition": {
    "StringLike": {
      "token.actions.githubusercontent.com:sub": "repo:enterprise-org/*:*"
    }
  }
  ```
* *Analisis Teknis*: Konfigurasi di atas mengizinkan **seluruh repositori** dalam organisasi—termasuk repositori publik eksperimental atau fork repositori oleh intern—untuk melakukan assume role ke akun produksi yang sama.
* *Solusi Remediasi*: Kunci klaim sub secara spesifik ke repositori target dan branch produksi:
  `repo:enterprise-org/production-app:ref:refs/heads/main`.

---

## 15. Best Practices & Enterprise Remediation Guide

### Remediation Playbook: Penanganan Insiden Kebocoran Secret
Jika terdeteksi kebocoran kredensial ke repositori publik atau internal, eksekusi protokol berikut:

```
[ IDENTIFIKASI ]
      |
      v
[ LANGKAH 1: REVOKASI & ROTASI SEGERA ]
      |-- JANGAN HANYA MENGHAPUS FILE DI GIT!
      |-- Kredensial telah terkompromi sejak detik pertama terdorong ke remote.
      |-- Akses Cloud IAM Console / API -> Hapus (Revoke) access key terkait.
      \-- Terbitkan access key baru untuk sistem produksi.
      |
      v
[ LANGKAH 2: AUDIT LOG INVESTIGASI ]
      |-- Periksa CloudTrail / Audit Logs penyedia API:
      |     EventSource: sts.amazonaws.com | Action: GetCallerIdentity
      \-- Cari event anomali dari IP address tidak dikenal pada rentang waktu komit.
      |
      v
[ LANGKAH 3: PEMBERSIHAN RIWAYAT GIT (HISTORY REWRITE) ]
      |-- Gunakan 'git-filter-repo' (resmi direkomendasikan, hindari BFG / filter-branch)
      |   $ pip install git-filter-repo
      |   $ git filter-repo --invert-paths --path path/to/leaked_file.env --force
      |-- Packfile purging:
      |   $ rm -rf .git/refs/original/
      |   $ git reflog expire --expire=now --all
      |   $ git gc --prune=now --aggressive
      \-- Force-push seluruh ref:
          $ git push origin --force --all
          $ git push origin --force --tags
      |
      v
[ LANGKAH 4: INVALIDASI CACHE SCM PLATFORM ]
      \-- Hubungi GitHub Enterprise / GitLab Support untuk menjalankan internal GC
          guna menghapus dangling commits dari API cache backend.
```

---

## 16. Hands-on Lab Step-by-Step

### Lab Objective:
Membangun alur commit integrity dari workstation lokal, mencegah commit file kredensial via Gitleaks, dan mengonfigurasi penandatanganan commit berbasis SSH.

#### Langkah 1: Generate Kunci SSH untuk Signing
```bash
# Buat keypair Ed25519 khusus untuk penandatanganan commit Git
ssh-keygen -t ed25519 -C "secops-developer@enterprise.internal" -f ~/.ssh/id_ed25519_signing -N ""
```

#### Langkah 2: Konfigurasi Git Global untuk SSH Signing
```bash
# Aktifkan format signing SSH
git config --global gpg.format ssh

# Konfigurasi path public key penandatangan
git config --global user.signingkey ~/.ssh/id_ed25519_signing.pub

# Wajibkan signing untuk setiap commit lokal secara default
git config --global commit.gpgsign true

# Set identitas pengembang
git config --global user.name "SecOps Engineer"
git config --global user.email "secops-developer@enterprise.internal"
```

#### Langkah 3: Setup Repositori dan Inisialisasi Pre-commit Hook
```bash
# Buat repositori lokal baru
mkdir git-security-lab && cd git-security-lab
git init

# Buat file implementasi aplikasi sederhana
cat << 'EOF' > app.py
def run():
    print("Application Initialized Safely.")
if __name__ == "__main__":
    run()
EOF

# Inisialisasi environment pre-commit
cat << 'EOF' > .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.2
    hooks:
      - id: gitleaks
EOF

# Install virtualenv dan pasang pre-commit
python3 -m venv venv
source venv/bin/activate
pip install pre-commit
pre-commit install
```

#### Langkah 4: Uji Coba Eksploitasi Kebocoran Kredensial
Simulasikan insiden developer yang tidak sengaja menulis mock API token AWS ke dalam file kode:

```bash
cat << 'EOF' > credentials.py
# Hardcoded credentials simulation
AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
EOF

# Lakukan staging file berbahaya tersebut
git add credentials.py
```

Jalankan perintah commit untuk memicu eksekusi hook:
```bash
git commit -m "feat: added external cloud interface"
```

**Ekspektasi Output Terminal (Commit Digagalkan):**
```text
[INFO] Initializing environment for https://github.com/gitleaks/gitleaks.
[INFO] Installing environment for https://github.com/gitleaks/gitleaks.
[INFO] Once installed this environment will be reused.
[INFO] Running run...
gitleaks.................................................................Failed
- hook id: gitleaks
- exit code: 1

    ○
    │╲
    │ ○
    ○  universal-path-provider
    │
    Discovering secrets in staged files...

Finding:     AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
Secret:      wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
RuleID:      aws-secret-access-key
Entropy:     4.782411
File:        credentials.py
Line:        3

ERR secrets discovered! 1 leaks detected.
```

#### Langkah 5: Remediasi dan Commit Bersih Tertanda Tangan
```bash
# Hapus file kredensial dari staging
git rm -f credentials.py

# Commit file yang aman
git add app.py .pre-commit-config.yaml
git commit -m "feat: initial commit with hardened pre-commit gate"
```

#### Langkah 6: Validasi Integritas Tanda Tangan Kriptografi
Periksa detail commit object Git untuk memverifikasi penandatanganan SSH:

```bash
git log --show-signature -n 1
```

**Ekspektasi Output Terminal:**
```text
commit 3a4f6d8b9e1c2a3d4e5f6a7b8c9d0e1f2a3b4c5d (HEAD -> main)
Good "ssh" signature for secops-developer@enterprise.internal with ED25519 key SHA256:u1A7vX...
Author: SecOps Engineer <secops-developer@enterprise.internal>
Date:   Mon May 20 10:00:00 2024 +0700

    feat: initial commit with hardened pre-commit gate
```

---

## 17. Real-World Case Study & Incident Analysis Enterprise

### Insiden Uber (Oktober 2022)
* **Konteks**: Penyerang berhasil menembus infrastruktur internal Uber setelah mengompromi kredensial VPN seorang kontraktor melalui serangan MFA Fatigue. 
* **Vektor Ekskalasi SCM**: Begitu berada di jaringan internal, penyerang memindai jaringan lokal dan menemukan network share yang berisi skrip PowerShell otomatis (`PowerShell script`). 
* **Temuan Kritikal**: Skrip tersebut memuat kredensial administratif statis (username dan password tingkat tinggi) untuk platform manajemen akses berbasis pam/privilege (Thycotic PAM).
* **Dampak Eskalasi**: Dengan kredensial PAM yang bocor di repositori/skrip internal tersebut, penyerang mengekstrak seluruh secret utama organisasi, termasuk konsol AWS admin, GCP admin, Google Workspace, dan sistem pelaporan kerentanan HackerOne milik Uber.
* **Analisis Pasca Insiden & DevSecOps Fix**:
  * Penerapan scanning secret berbasis entropi di internal git hosting (bukan hanya public repos).
  * Menghapus seluruh hardcoded credentials pada skrip deployment.
  * Transisi penuh otentikasi CI/CD dan sistem otomasi server dari kredensial hardcoded ke OIDC identity tokens dan ephemeral short-lived IAM roles.

---

## 18. Quiz Pemahaman & Challenge

### Soal Evaluasi Pemahaman

1. **Bagaimana algoritma deteksi secret scanning berbasis Shannon Entropy mengklasifikasikan bahwa suatu string acak merupakan token kriptografis, dan apa kelemahannya?**
   * A. Menghitung frekuensi karakter khusus; kelemahannya adalah tidak mendeteksi string hex.
   * B. Mengukur kepadatan informasi ketidakpastian matematis dari set karakter; kelemahannya adalah tingginya false positive pada hash sha256 atau UUID non-sensitif.
   * C. Mengirimkan string ke server cloud eksternal untuk didekripsi; kelemahannya membutuhkan kuota internet.
   * D. Menghitung checksum CRC32; kelemahannya rentan collision.

2. **Mengapa penghapusan commit yang memuat kredensial via `git push --force` setelah melakukan `git reset --hard HEAD~1` belum memitigasi risiko keamanan sepenuhnya?**
   * A. Karena file `.gitconfig` di remote server memblokir reset commit.
   * B. Karena data masih tersimpan di staging index klien.
   * C. Karena Git DAG remote server mempertahankan dangling objects yang tetap dapat dibaca melalui Commit SHA API langsung sebelum garbage collection (GC) dijalankan.
   * D. Karena SCM secara otomatis membuat pull request baru untuk commit yang dihapus.

3. **Klaim standar mana di dalam OIDC JSON Web Token (JWT) yang wajib diverifikasi secara ketat pada IAM Trust Policy untuk membatasi eksekusi deployment role hanya dari branch `main` repositori tertentu?**
   * A. `aud` (Audience)
   * B. `iss` (Issuer)
   * C. `sub` (Subject)
   * D. `exp` (Expiration Time)

4. **Apa fungsi utama dari parameter `require_last_push_approval` pada aturan GitHub Branch Protection?**
   * A. Memaksa pengembang menandatangani commit dengan kunci hardware (YubiKey).
   * B. Menolak PR secara permanen jika conflict terjadi dengan branch upstream.
   * C. Membatalkan status *Approved* sebelumnya jika ada commit baru yang didorong ke branch PR, mencegah penyusupan kode malicious di detik-detik terakhir sebelum merge.
   * D. Membatasi approval hanya boleh dilakukan oleh akun dengan role Organization Owner.

5. **Apa perbedaan mendasar antara implementasi penandatanganan commit menggunakan SSH Signature dibanding GPG?**
   * A. SSH Signature tidak mendukung kurva Ed25519.
   * B. GPG memvalidasi integritas file, sedangkan SSH hanya mengenkripsi koneksi jaringan.
   * C. SSH Signature menggunakan format `ssh-keygen` yang memvalidasi hash objek commit dengan kunci SSH publik pengembang tanpa memerlukan manajemen GnuPG keyring yang terpisah.
   * D. SCM modern tidak lagi mendukung GPG Signature.

### Kunci Jawaban
1. **B** – Shannon Entropy murni mengevaluasi sebaran variasi karakter matematis, sehingga string acak seperti commit hash atau file GUID dapat teridentifikasi sebagai secret jika threshold disetel terlalu sensitif.
2. **C** – Commit object yang kehilangan referensi ref pointer (*dangling object*) tetap berada di dalam packfile internal Git server sampai platform membersihkannya melalui aggressive pruning.
3. **C** – Klaim `sub` (*Subject*) memetakan metadata runtime pipeline: `repo:<org>/<repo>:ref:refs/heads/<branch>`.
4. **C** – Mencegah taktik manipulasi review di mana pengembang meminta approval untuk kode yang bersih, lalu menyuntikkan payload berbahaya sesaat sebelum tombol merge ditekan.
5. **C** – SSH signing menggunakan infrastruktur kunci SSH yang sudah ada pada workstation pengembang, menyederhanakan konfigurasi tanpa perlu utilitas `gpg` dan `gpg-agent`.

### Practical Challenge
**Skenario**: Anda ditugaskan mengaudit repositori monorepo enterprise `fintech-core`. Konfigurasi `.github/CODEOWNERS` saat ini hanya berisi:
```text
* @fintech-core-admins
```
Pipeline deployment saat ini menggunakan kredensial statis AWS Access Key yang disuntikkan via Secrets Manager `AWS_ACCESS_KEY_ID` dan `AWS_SECRET_ACCESS_KEY`.

**Tugas Praktik**:
1. Rancang ulang file `.github/CODEOWNERS` agar memisahkan review hak akses antara folder `/infra/terraform/` (wajib disetujui `@infra-leads`), `/services/payment/` (wajib disetujui `@payment-leads` dan `@appsec-team`), serta fallback review ke `@general-devs`.
2. Tuliskan blok IAM Assume Role Policy (JSON) menggunakan AWS IAM OIDC Trust Policy yang hanya memperbolehkan workflow pada path repositori `fintech-corp/fintech-core` dengan tag environment `production` untuk melakukan assume role.

---

## 19. Summary & Key Takeaways

* **Pertahanan Berlapis (*Defense-in-Depth*) Git**: Keamanan repositori tidak dapat hanya bertumpu pada kontrol sisi klien (pre-commit) atau sisi server (push protection) secara terpisah. Implementasikan gerbang validasi ganda di workstation pengembang, push-level filtering di SCM gateway, serta deep historical scanning di pipeline CI.
* **Eliminasi Kredensial Statis**: Penggunaan AWS Access Keys atau API token statis berumur panjang pada lingkungan CI/CD merupakan anti-pattern berisiko tinggi. Transisikan arsitektur CI/CD menuju federasi identitas temporer berbasis **OpenID Connect (OIDC)**.
* **Jaminan Integritas Kode Asli**: Terapkan penandatanganan commit berbasis **SSH Signing (Ed25519)** atau **GPG** sebagai aturan mutlak di level branch protection untuk menjamin integritas kode dan akuntabilitas audit compliance.
* **Granularitas Tata Kelola SCM**: Terapkan file **`CODEOWNERS`** berbasis domain arsitektur, aktifkan aturan dismiss stale reviews saat terjadi push baru, dan wajibkan linear commit history untuk mengeliminasi manipulasi merge/squash commit.
* **Respon Insiden Aktif**: Jika secret bocor ke Git DAG, lakukan **revokasi segera pada sistem penyedia kredensial**. Menghapus file dan me-rewrite riwayat commit menggunakan `git-filter-repo` adalah langkah sanitasi repositori, bukan pengganti rotasi kunci.

---

## 20. Referensi Resmi & Standar Keamanan

1. **OWASP Top 10 CI/CD Security Risks**:
   * *CICD-SEC-01*: Insufficient Flow Control Mechanisms (Mitigasi: Branch Protection & CODEOWNERS).
   * *CICD-SEC-06*: Insufficient Credential Hygiene (Mitigasi: Gitleaks & TruffleHog).
   * *CICD-SEC-07*: Impersistent Identity Authorization (Mitigasi: OIDC Workload Identity).
2. **NIST Special Publication 800-204D**:
   * *Strategies for Framework-based Software Supply Chain Security in Development and Deployment Pipelines* – Bagian Kontrol Integritas Source Control Management.
3. **CIS Software Supply Chain Security Guide**:
   * *Section 1.1*: Source Code - Repository Integrity and Access Permissions.
   * *Section 1.2*: Commit Signature Enforcement and Non-Repudiation Controls.
4. **MITRE ATT&CK for Enterprise**:
   * *T1552.001*: Unsecured Credentials: Credentials in Files (Deteksi Git Repositories).
   * *T1195.001*: Supply Chain Compromise: Compromise Software Dependencies and Pipeline Infrastructure.
5. **OpenSSF Scorecards Documentation**:
   * *Metric: Branch-Protection & Token-Permissions* – Implementasi least-privilege token pada SCM Actions runner.