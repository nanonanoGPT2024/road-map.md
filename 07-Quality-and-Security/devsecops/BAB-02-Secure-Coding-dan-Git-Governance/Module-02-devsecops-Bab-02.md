# BAB 02: Secure Coding & Git Governance
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengoperasikan arsitektur Git Governance berbasis *Zero Trust* di lingkungan multi-repo dan monorepo skala enterprise.
- Membedah struktur internal Git object database (`commit`, `tree`, `blob`, `tag`) serta mekanisme verifikasi kriptografis commit menggunakan GPG, SSH, dan Sigstore/Gitsign.
- Membangun pipeline deteksi rahasia (*secret scanning*) berlapis (*pre-commit*, *pre-receive*, dan *asynchronous CI scanning*) menggunakan engine berbasis regex deterministik dan kalkulasi *Shannon Entropy*.
- Mengonfigurasi dan mengotomatisasi *Branch Protection Rules*, *CODEOWNERS*, dan evaluasi *Static Application Security Testing* (SAST) menggunakan Semgrep kustom dengan format pelaporan SARIF standar OASIS.
- Mengimplementasikan federasi identitas CI/CD berbasis OpenID Connect (OIDC) untuk mengeliminasi *long-lived static credentials* pada Git pipeline.

---

### 2. Prerequisite
Peserta wajib memiliki pemahaman mendalam dan pengalaman praktis pada:
- **Git Internals**: Pemahaman tentang Directed Acyclic Graph (DAG), SHA-1/SHA-256 object hashing, dan CLI plumbing commands (`git cat-file`, `git hash-object`).
- **Kriptografi Asimetris**: Public/Private Key Infrastructure (PKI), algoritma Ed25519, RSA, GPG keyring management, serta x509 digital certificates.
- **CI/CD Platform Architecture**: Engine workflow (GitHub Actions, GitLab CI, atau Tekton Pipelines) beserta konsep *ephemeral runners*.
- **Dasar SAST & AppSec**: OWASP Top 10 API/Web, Abstract Syntax Tree (AST), dan CWE (Common Weakness Enumeration).

---

### 3. Concept & Internal Architecture

#### 3.1 Anatomi Git Object Database & Cryptographic Signing
Git bukan sekadar sistem kontrol versi; Git adalah *content-addressable filesystem* berbasis DAG. Setiap state disimpan dalam direktori `.git/objects` sebagai object terkompresi zlib:
1. **Blob**: Menyimpan payload data file mentah tanpa metadata (nama file atau permission).
2. **Tree**: Berfungsi sebagai representasi direktori, memetakan hash blob ke nama file dan permission mode (misal `100644` atau `100755`).
3. **Commit**: Mengikat root tree hash, parent commit hash(es), metadata committer/author (timestamp, nama, email), serta pesan commit.

Ketika sebuah commit ditandatangani secara kriptografis (`git commit -S` via GPG atau SSH signing key):
- Git mengambil *un-signed commit buffer* (seluruh isi commit object dari baris `tree` hingga baris pesan commit).
- Kunci privat menandatangani buffer tersebut.
- Signature yang dihasilkan diinjeksikan langsung ke dalam commit object header di bawah field `gpgsig`.
- Modifikasi 1 bit saja pada kode sumber, timestamp, nama author, atau parent commit akan mengubah hash SHA-1/SHA-256 dari commit tersebut, membatalkan validitas signature matematisnya.

```
+------------------------------------------------------------------------+
| Git Commit Object (Raw Byte Payload)                                   |
|------------------------------------------------------------------------|
| tree 4b825dc642cb6eb9a060e54bf8d69288fbee4904                         |
| parent a1b2c3d4e5f60718293a4b5c6d7e8f9012345678                       |
| author Alice <alice@enterprise.internal> 1700000000 +0700             |
| committer Alice <alice@enterprise.internal> 1700000000 +0700          |
| gpgsig -----BEGIN PGP SIGNATURE-----                                   |
|        iQIzBAABCAAdFiEE... (Base64 ASCII Armor Signature Payload)      |
|        -----END PGP SIGNATURE-----                                     |
|                                                                        |
| feat(core): implement zero-trust payload verification                  |
+------------------------------------------------------------------------+
```

#### 3.2 Shannon Entropy untuk Deteksi Rahasia
Pencarian berbasis Regular Expression (Regex) murni rentan terhadap *false negative* (token baru dengan format tak terduga) dan *false positive* (UUID, hash commit). Pipeline enterprise menggabungkan Regex terarah dengan **Shannon Entropy** untuk mendeteksi string acak dengan kepadatan informasi tinggi (khas API keys, private keys, password terenkripsi).

Formula Shannon Entropy $H(X)$:
$$H(X) = -\sum_{i=1}^{n} P(x_i) \log_2 P(x_i)$$

Di mana:
- $n$: Jumlah karakter unik dalam alfabet string yang dianalisis.
- $P(x_i)$: Probabilitas kemunculan karakter $x_i$ dalam string.

Karakteristik nilai Entropy:
- Teks bahasa Inggris standar / kode program biasa: $\approx 2.5 - 3.5$
- Base64 High-Entropy Secret (misal AWS Secret Access Key, JWT): $\ge 4.5$
- Hex-encoded raw binary key (128/256-bit entropy): $\ge 3.0$ (karena ukuran charset dasar hanya 16 karakter).

#### 3.3 Dynamic Branch Gating & OIDC Federation Architecture
Arsitektur Git Enterprise modern membuang *personal access tokens* (PAT) dan *service account long-lived SSH keys*. Sebagai gantinya, runner CI/CD menggunakan token JWT ephemeral berbasis OpenID Connect (OIDC) yang ditukarkan langsung ke Identity Provider (AWS IAM, GCP Workload Identity, atau HashiCorp Vault) berdasarkan metadata branch, commit ref, dan environment.

---

### 4. Why & What

| Dimensi | Legacy Git Operations | Modern DevSecOps Git Governance |
| :--- | :--- | :--- |
| **Commit Identity** | Plain Git config (`user.name`, `user.email`) yang mudah dipalsukan (*spoofed*). | Cryptographically Signed Commits (GPG/SSH/X.509 via Sigstore). Validasi cryptographically enforced. |
| **Secret Remediation** | Audit manual pasca insiden, rewrite history via `git filter-branch` (destruktif). | Zero-Tolerance Shift-Left: Pre-commit, blocking pre-receive hook, auto-revocation bot via webhook. |
| **SAST Integration** | Dijalankan manual atau batch periodik per malam; hasil terkubur dalam PDF ribuan halaman. | PR-level AST analysis (Semgrep/CodeQL), gated via status checks, output SARIF inline PR comments. |
| **CI/CD Authentication**| Static secret keys (AWS_SECRET_ACCESS_KEY, SSH keys) tersimpan di repositori settings. | Ephemeral OIDC Identity Token Exchange; scope dibatasi hingga spesifik branch / environment. |
| **Merge Authorizations**| Approval informal via Slack/komentar; hak push master/main tidak dibatasi ketat. | Proteksi cabang otomatis, integrasi CODEOWNERS ketat, pemisahan tugas (Separation of Duties). |

---

### 5. How (Workflow Detail)

Arsitektur pertahanan berlapis (*Defense-in-Depth*) untuk Git Governance diimplementasikan melalui tahapan berikut:

```
[Developer Machine]
       │
       ▼ (1) Developer writes code
[Pre-commit Hook (Framework)] ──(Blocks high-entropy secrets, validates GPG signing)
       │
       ▼ (2) git push origin main
[Git Server / Remote (Pre-Receive Hook)] ──(Rejects unsigned commits, enforces format)
       │
       ▼ (3) Pull Request Created
[CI Pipeline Engine (GitHub/GitLab)]
  ├── Step A: OIDC Federated Auth (Get short-lived cloud credentials)
  ├── Step B: Deep Secret Scanning (Gitleaks Full Repo Graph)
  ├── Step C: Contextual AST SAST (Semgrep Rule Scanning -> SARIF)
  └── Step D: Policy as Code Verification (Open Policy Agent / Conftest)
       │
       ▼ (4) Checks Pass & CODEOWNERS Approval
[Merge to Protected Branch] ──(Generates SLSA Provenance Attestation)
```

1. **Local Phase (Shift-Left)**:
   - Developer menginisialisasi commit. `pre-commit` hook mengeksekusi linter, gitleaks (staged diff), dan memvalidasi branch naming standard.
   - Commit ditandatangani menggunakan SSH signing key atau GPG key yang terikat dengan identitas korporat (hardware-backed YubiKey atau local agent).

2. **Ingress Phase (Server Enforcement)**:
   - Server remote (GitLab Enterprise Server / GitHub Enterprise / On-Premise Git Server) mengevaluasi push via `pre-receive` hook.
   - Server menolak transaksi push (`exit 1`) jika commit tidak ditandatangani oleh public key yang terdaftar di database organisasi.

3. **Pull Request Analysis Phase**:
   - Webhook memicu ephemeral CI runner.
   - Runner mengambil ID Token (OIDC) dari platform Git untuk berkomunikasi dengan eksternal vault/cloud secara aman tanpa password.
   - Analisis statis diferensial (`--baseline-commit`) dieksekusi menggunakan Semgrep untuk menemukan kerentanan pada sintaksis AST yang baru.
   - Report SARIF dipublikasikan ke tab *Code Scanning Alerts*.

4. **Policy Enforcement & Merge**:
   - Aturan Branch Protection memverifikasi status:
     - Semua status checks (CI, SAST, Secret Scan) berstatus `SUCCESS`.
     - Review wajib dari user/team yang tercantum di file `CODEOWNERS` untuk direktori sensitif.
     - Linear history enforced (rebase and merge atau squash and merge).

---

### 6. Analogy & Diagram ASCII

Bayangkan sistem Git Governance seperti **Sistem Imigrasi Bandara Internasional Tingkat Tinggi**:
- **Signed Commit** adalah **Paspor Biometrik**: Memastikan bahwa pemegang dokumen benar-benar orang yang tertera, bukan seseorang yang memakai topeng (spoofed author email).
- **Pre-commit Hook** adalah **Pemeriksaan Keamanan Mandiri (Self-Screening)**: Mengingatkan pelancong jika membawa barang terlarang sebelum meninggalkan rumah.
- **Pre-Receive Hook** adalah **Pintu X-Ray Bandara**: Jika Anda membawa senjata (hardcoded secret), Anda dicegat langsung di perimeter terluar dan dilarang masuk ke terminal.
- **Branch Protection & CODEOWNERS** adalah **Protokol Dual-Key Ruang Brankas**: Pintu lemari besi hanya terbuka jika dua staf berwenang memutar kunci otorisasi mereka secara bersamaan.

```
                SECURE PIPELINE BOUNDARY
+-------------------------------------------------------------+
|                                                             |
|   +--------------+      git push      +-----------------+   |
|   | Local Dev    | -----------------> | Git Enterprise  |   |
|   | Signature:OK |                    | Hook: Rejected! |   |
|   +--------------+                    +-----------------+   |
|          |                                     |            |
|          | (Unsigned / Has Secret)             |            |
|          X ------------------------------------+            |
|                                                             |
|   +--------------+      git push      +-----------------+   |
|   | Verified Dev | -----------------> | Protected Repo  |   |
|   | YubiKey Sig  |                    | Branch: main    |   |
|   +--------------+                    +-----------------+   |
|                                                |            |
|                                       Trigger Webhook       |
|                                                v            |
|                                       +-----------------+   |
|                                       | CI Runner (OIDC)|   |
|                                       |  - Semgrep SAST |   |
|                                       |  - Gitleaks     |   |
|                                       |  - SARIF Export |   |
|                                       +-----------------+   |
+-------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: SSH-based Commit Signing
Mengonfigurasi Git lokal agar menandatangani commit menggunakan kunci SSH native (tersedia sejak Git v2.34+):

```bash
# 1. Generate standard secure SSH Ed25519 keypair
ssh-keygen -t ed25519 -C "alice@enterprise.internal" -f ~/.ssh/id_git_signing

# 2. Konfigurasi Git untuk menggunakan SSH signing
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_git_signing.pub
git config --global commit.gpgsign true
git config --global tag.gpgSign true

# 3. Verifikasi commit signature via log plumbing
git commit -m "feat(auth): add zero-trust policy engine"
git log --show-signature -n 1
```

#### 7.2 Practical Example: Enterprise Multi-Tier Implementation

Berikut adalah manifest konfigurasi terintegrasi standar produksi.

##### Step A: `.pre-commit-config.yaml`
Menjalankan validasi secret dan linting lokal deterministik.

```yaml
default_install_hook_types: [pre-commit, pre-push]
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.2
    hooks:
      - id: gitleaks
        name: Detect Hardcoded Secrets (Gitleaks Engine)
        entry: gitleaks protect --verbose --redact --staged
        language: golang
        pass_filenames: false

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: check-added-large-files
        args: ['--maxkb=1024']
      - id: check-merge-conflict
      - id: detect-private-key
      - id: end-of-file-fixer
      - id: trailing-whitespace
```

##### Step B: `.github/workflows/devsecops-pipeline.yml`
Pipeline GitHub Actions dengan autentikasi AWS OIDC (Tokenless), integrasi Gitleaks, dan analisis Semgrep SAST yang mempublikasikan hasil ke GitHub Security SARIF dashboard.

```yaml
name: Enterprise DevSecOps CI Gate

on:
  pull_request:
    branches: [ main, release/* ]
  push:
    branches: [ main ]

permissions:
  id-token: write      # Wajib untuk autentikasi OIDC
  contents: read       # Membaca source code repositori
  security-events: write # Menulis file SARIF ke Security tab
  pull-requests: write # Memberikan feedback komentar pada PR

jobs:
  secret-audit:
    name: Secret Scanning
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code Base
        uses: actions/checkout@v4
        with:
          fetch-depth: 0 # Full history untuk deep scanning

      - name: Run Gitleaks Scan
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITLEAKS_LICENSE: "free-mode"

  sast-analysis:
    name: SAST Engine Execution
    runs-on: ubuntu-latest
    needs: secret-audit
    container:
      image: returntocorp/semgrep:1.60.0
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Run Semgrep AST Rules
        run: |
          semgrep scan \
            --config "p/security-audit" \
            --config "p/owasp-top-ten" \
            --config ".semgrep/custom-rules.yml" \
            --sarif \
            --output semgrep-results.sarif \
            --error

      - name: Upload SARIF to Security Tab
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: semgrep-results.sarif

  cloud-deploy-dryrun:
    name: OIDC Cloud Authentication Test
    runs-on: ubuntu-latest
    needs: sast-analysis
    steps:
      - name: Authenticate with AWS via OIDC
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/GitHubActionsEnterprisePipelineRole
          aws-region: ap-southeast-1
          audience: sts.amazonaws.com

      - name: Verify STS Caller Identity
        run: |
          aws sts get-caller-identity
```

##### Step C: `.semgrep/custom-rules.yml`
Aturan semantik kustom untuk mendeteksi eksekusi query raw database (SQL Injection) yang lolos dari pattern linter standar:

```yaml
rules:
  - id: enterprise-raw-sql-injection-risk
    languages: [python]
    severity: ERROR
    message: >-
      Deteksi penggunaan interpolasi string pada query raw database! 
      Gunakan parameter binding bawaan ORM/Database Engine untuk menghindari SQL Injection.
    metadata:
      cwe: "CWE-89: Improper Neutralization of Special Elements used in an SQL Command"
      owasp: "A03:2021 - Injection"
    patterns:
      - pattern-either:
          - pattern: $DB.execute(f"... {$VAR} ...")
          - pattern: $DB.execute("..." % $VAR)
          - pattern: $DB.execute("...".format($VAR))
      - pattern-not: $DB.execute("...", [...])
      - pattern-not: $DB.execute("...", {...})
```

##### Step D: `.github/CODEOWNERS`
Pemisahan otoritas persetujuan code review:

```plaintext
# Root: default maintainers
* @enterprise-org/core-infra

# Security Sensitive Files
/.github/workflows/          @enterprise-org/appsec-team @enterprise-org/platform-engineers
/.semgrep/                  @enterprise-org/appsec-team
/internal/crypto/           @enterprise-org/appsec-team
/deploy/terraform/          @enterprise-org/cloud-platform

# Core Application Logic
/services/payment/          @enterprise-org/fintech-leads @enterprise-org/appsec-team
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks & Skenario Insiden
Sebuah perusahaan Unicorn Fintech di Asia Tenggara ("FinCorp") mengalami insiden keamanan: salah satu akun personal GitHub milik insinyur eksternal (*third-party contractor*) diretas melalui session hijacking. Peretas membuat commit pada branch `release/v4.2.0` yang disamarkan (*commit spoofing*) dengan nama dan email Principal Architect FinCorp (`architect@fincorp.internal`).

Kode berbahaya tersebut adalah *backdoor HTTP reverse shell* yang disisipkan ke dalam helper class enkripsi pembayaran. Karena repositori tidak menerapkan verifikasi tanda tangan kriptografis commit dan tidak memvalidasi aturan wajib *status check branch*, kode tersebut di-merge dan lolos ke production, mengekspos ribuan token pembayaran transaksi kartu kredit.

#### Investigasi Post-Mortem & Akar Masalah (Root Causes)
1. **Author Spoofing**: Git mengizinkan siapa pun menuliskan `git config user.email` sembarang tanpa verifikasi keaslian.
2. **Branch Governance Void**: Branch `release/*` tidak memiliki status *Branch Protection* aktif; bypass merge diizinkan tanpa review tim AppSec.
3. **Static Scanner Blindspot**: Scanner regex legacy gagal membaca pola obfuscated reverse shell.

#### Solusi Arsitektur DevSecOps yang Diterapkan
1. **Cryptographic Identity Enforcement**:
   - Diaktifkan flag **Require signed commits** di tingkat organisasi.
   - Pendaftaran public key dilakukan via portal SSO korporat; kunci yang tidak terikat ID karyawan langsung diblokir di level reverse-proxy GitHub Enterprise.
2. **Deterministic Pre-receive Guard**:
   - Menerapkan hook pada server Git yang mengevaluasi seluruh revision range:
     `git rev-list --objects $OLDREV..$NEWREV` untuk memastikan tidak ada email committer yang berbeda dari subjek identitas sertifikat penandatangan.
3. **AST Scanning Implementation**:
   - Integrasi Semgrep engine untuk menganalisis semantic data-flow (taint analysis) pada seluruh PR sebelum merge diizinkan.
4. **Hasil Pasca-Implementasi (6 Bulan Metrik)**:
   - Zero incidents author spoofing.
   - Penurunan 89% temuan kerentanan injeksi kode pada tahap Staging.
   - Eliminasi 100% credential static pada seluruh pipeline deployment cloud (beralih ke OIDC federation).

---

### 9. Trade-offs

Mengimplementasikan Git Governance skala enterprise membawa implikasi teknis dan operasional yang signifikan:

```
               [ KEAMANAN (Maximum Security) ]
                         /\
                        /  \
                       /    \
                      /      \
  [ LATENSI PIPELINE ] -------- [ DEVELOPER VELOCITY ]
```

| Parameter | Pendekatan Ringan (Permissive) | Pendekatan Enterprise Hardened (Zero Trust) | Trade-off Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **Pipeline Latency** | Scan cepat (< 1 menit). Regex dasar, tidak ada deep AST. | Latensi tinggi (5-15 menit). Deep commit graph parsing, entropy scanning, full AST taint analysis. | Gunakan `--baseline-commit` / `--diff-depth` agar engine hanya memindai patch set (delta), bukan full repository scanning setiap trigger. |
| **Developer Velocity** | Developer commit langsung tanpa halangan lokal hook. | Komplain developer: commit gagal karena false positive pre-commit hook atau key mismatch. | Buat sistem inline bypass flag dengan justifikasi audit logging ketat, serta sediakan image devcontainer yang telah terkonfigurasi otomatis. |
| **Infrastructure Cost** | Runner CI kecil, beban komputasi rendah. | Runner CI besar (high memory/CPU) untuk menjalankan container AST engine dan secret scan paralel. | Implementasi caching state AST Semgrep dan cache dependency tools pada layer storage S3/GCS runner. |
| **Operational Overhead** | Pengaturan minimal, tidak ada manajemen certificate/key. | Overhead tinggi: rotasi SSH/GPG key tahunan, audit policy drift, pemeliharaan exception file. | Implementasikan Sigstore Cosign/Gitsign yang berbasis *ephemeral short-lived certificates* via OIDC (keyless signing). |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Commit Divergence dan Broken Signatures saat Rebase
- **Gejala**: Developer melakukan interactive rebase (`git rebase -i`), lalu seluruh commit yang sebelumnya bertanda "Verified" berubah menjadi "Unverified" di GitHub/GitLab UI.
- **Root Cause**: Rebase membuat commit object baru dengan timestamp dan hash baru. Jika flag penandatanganan tidak diikutsertakan selama operasi rebase, Git tidak menandatangani ulang commit hasil kalkulasi baru tersebut.
- **Solusi Troubleshooting**:
  Konfigurasikan Git untuk otomatis menandatangani commit saat melakukan rebase:
  ```bash
  git config --global rebase.autoSquash true
  git config --global rebase.autoStash true
  # Jalankan rebase dengan menyertakan instruksi penandatanganan eksplisit
  git rebase --exec 'git commit --amend --no-edit -S' -i HEAD~5
  ```

#### 10.2 False Positive Shannon Entropy pada Resource String
- **Gejala**: Pipeline gagal (`exit 1`) karena Gitleaks menandai hash commit SHA-256 yang tercantum di file dokumentasi atau UUID mock di unit test sebagai secret berkepadatan tinggi (*entropy leak*).
- **Solusi**: Terapkan konfigurasi `.gitleaks.toml` yang granular dengan mekanisme *allowlist* spesifik, hindari mematikan scanning secara global.

```toml
[allowlist]
description = "Global allowlist for benign high-entropy patterns"
paths = [
  '''tests/fixtures/.*''',
  '''go\.sum$''',
  '''package-lock\.json$'''
]
regexes = [
  '''[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}''', # UUIDv4
]
stopwords = [
  "dummy_token",
  "mock_secret_key"
]
```

#### 10.3 OIDC Federated Token Rejected by AWS STS
- **Gejala**: Runner CI memunculkan pesan error `An error occurred (InvalidIdentityToken) when calling the AssumeRoleWithWebIdentity operation: OpenIDConnect provider not found`.
- **Root Cause**: Terjadi ketidakcocokan nilai *Thumbprint/Audience* atau klaim `sub` (*Subject*) pada IAM Trust Policy cloud provider.
- **Solusi Debugging**:
  1. Ekstrak raw JWT token yang dibuat oleh GitHub Runner ke console log (secara aman tanpa mengekspos isi sensitif).
  2. Periksa IAM Role Trust Relationship. Klaim `sub` harus merefleksikan repositori, branch, dan context dengan presisi:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:enterprise-org/core-banking:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini untuk audit kesiapan Git Governance enterprise:

- [ ] **Cryptographic Signing Enforced**: Setiap push ke protected branch wajib memiliki signature kriptografis yang tervalidasi.
- [ ] **Short-Lived OIDC Authentication**: Seluruh pipeline deployer mengeliminasi static access key (AWS, GCP, Azure, Vault).
- [ ] **Dual-Reviewer CODEOWNERS**: File konfigurasi infrastruktur, security, dan credential gateway memerlukan minimal 2 approver dari tim AppSec/Core-Platform.
- [ ] **Linear History**: Aturan branch protection menolak fast-forward merge kotor (*no merge commits*), mempermudah bisecting dan analisis forensik audit.
- [ ] **AST SAST Engine on PR**: Menjalankan Semgrep / CodeQL dengan threshold `critical` dan `high` yang menghentikan pipeline (*breaking build*).
- [ ] **Tiered Secret Detection**:
  - Layer 1: Developer local pre-commit hooks (`gitleaks protect`).
  - Layer 2: Server-side pre-receive hooks (bila mengoperasikan on-premise git).
  - Layer 3: Ephemeral CI runner scan dengan baseline differential.
- [ ] **Ephemeral Clean Environments**: Tooling keamanan berjalan dalam isolated, immutable container image yang sudah di-sign digest SHA256-nya, bukan menggunakan image ber-tag `:latest`.
- [ ] **SARIF Reporting Hub**: Seluruh scanner mengekspor data dalam format SARIF v2.1.0 agar tersinkronisasi ke single pane of glass keamanan enterprise.

---

### 12. Hands-on Practice

Simpan seluruh hasil latihan ini pada repositori lokal di direktori: `hands-on/m02/`

#### Tugas: Membangun Local Git Governance Harness dengan Blokade Kriptografis dan Deteksi Entropi

#### Langkah 1: Persiapan Workspace & Git Init
```bash
mkdir -p hands-on/m02/secure-repo
cd hands-on/m02/secure-repo
git init

# Buat kunci penandatangan SSH khusus simulasi
ssh-keygen -t ed25519 -C "auditor@security.internal" -f ./id_audit_signing -N ""
git config user.name "Security Auditor"
git config user.email "auditor@security.internal"
git config gpg.format ssh
git config user.signingkey "./id_audit_signing.pub"
git config commit.gpgsign true
```

#### Langkah 2: Setup Pre-Commit Hardening Framework
Buat file `hands-on/m02/secure-repo/.pre-commit-config.yaml`:
```yaml
repos:
  - repo: local
    hooks:
      - id: block-raw-private-keys
        name: Block Private Key Files
        entry: 'BEGIN (RSA|EC|OPENSSH|PGP) PRIVATE KEY'
        language: pygrep
        types: [text]

      - id: prevent-eval-injection
        name: Prevent Python Eval Usage
        entry: '\beval\s*\('
        language: pygrep
        types: [python]
```

Inisialisasi pre-commit:
```bash
# Pastikan framework pre-commit sudah terinstall secara global (pip install pre-commit)
pre-commit install
```

#### Langkah 3: Menguji Proteksi Terhadap Payload Berbahaya
Buat file target kerentanan `hands-on/m02/secure-repo/calculator.py`:
```python
import sys

def execute_user_input(payload):
    # Remote Code Execution vulnerability
    return eval(payload)

if __name__ == "__main__":
    result = execute_user_input(sys.argv[1])
    print(result)
```

Coba commit perubahan ini ke Git:
```bash
git add calculator.py
git commit -m "feat: implement calculator evaluation"
```
*Hasil yang diharapkan: Hook `prevent-eval-injection` membatalkan proses commit secara otomatis.*

#### Langkah 4: Remediasi Kode & Verifikasi Cryptographic Signature
Modifikasi `calculator.py` agar aman:
```python
import ast
import sys

def execute_user_input(payload):
    # Parsing aman via Abstract Syntax Tree literal
    return ast.literal_eval(payload)

if __name__ == "__main__":
    result = execute_user_input(sys.argv[1])
    print(result)
```

Jalankan commit ulang dan amati verifikasi tandatangan:
```bash
git add calculator.py
git commit -m "feat(security): implement safe ast literal evaluation"
git log --show-signature -n 1
```
*Output wajib menunjukkan signature status `Good "git" signature for auditor@security.internal with ED25519 key...`*

---

### 13. Exercise

#### Level 1: Easy
Konfigurasikan filter regex `allowlist` pada Gitleaks lokal untuk mengizinkan string `API_KEY_STAGING_MOCK_12345` tetap lolos scan hanya jika berada di dalam folder `src/__mocks__/`, tetapi memblokir string tersebut jika diletakkan di dalam folder `src/config/`.

#### Level 2: Medium
Tuliskan custom script Python `check_entropy.py` yang menerima argumen file, memecah isi file menjadi string token berbasis spasi/variabel, menghitung Shannon Entropy dari tiap token, dan mengembalikan `exit 1` bila ditemukan string berkarakter minimal 20 karakter dengan entropy $> 4.7$. Pasang script ini sebagai *local pre-push hook* Git native (`.git/hooks/pre-push`).

#### Level 3: Hard
Bangun Terraform code (`main.tf`) untuk mengonfigurasi GitHub Repository Branch Protection secara otomatis dengan spesifikasi:
- Target branch: `main`.
- Wajib signed commit (`require_signed_commits = true`).
- Dismiss stale pull request approvals ketika commit baru didorong.
- Wajib lolos review minimal 2 approver dari `CODEOWNERS`.
- Memerlukan status check dari 2 konteks CI: `Secret Scanning` dan `SAST Analysis`.
- Enforce status checks pada administrator (`enforce_admins = true`).

---

### 14. Challenge

**Skenario**: Perusahaan Anda adalah institusi perbankan dengan regulasi ketat. Anda memiliki sebuah *Monorepo* besar yang menampung 40 microservices backend yang dikelola oleh 150 insinyur software. 

**Objektif Arsitektur**:
Rancang strategi Git Governance & CI Gate yang komprehensif untuk memecahkan dilema berikut:
1. **Divergent Domain Ownership**: Service `transfer-service` hanya boleh dimodifikasi oleh tim Payments, sementara `loan-service` oleh tim Lending. Akses push tidak boleh bocor lintas domain.
2. **Blast Radius SAST Performance**: Full codebase scan memakan waktu 45 menit. Anda harus merancang arsitektur pipeline diferensial yang mampu mendeteksi dependensi subfolder yang terdampak (misalnya: perubahan pada shared core lib harus memicu scan pada dependent services, namun perubahan pada isolated service logic hanya menjalankan scan pada folder service itu sendiri) dengan batasan total wall-time pipeline maksimal **5 menit**.
3. **Supply Chain Attestation (SLSA Level 3)**: Seluruh commit harus dijamin ketertelusurannya sejak ditulis oleh engineer terautentikasi SSO hingga terbentuk Docker container artifact, tanpa menggunakan private key statis yang disimpan di CI runner platform.

Tuliskan dokumen desain arsitektur teknis lengkap (mencakup ASCII architecture flow, strategi splitting CODEOWNERS, dynamic matrix generation CI workflow script, dan mekanisme keyless signing artifact menggunakan Sigstore/Cosign).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Konsep Dasar (Basic)
1. Apa komponen hash yang berubah di dalam commit object jika seorang committer mengubah timestamp komputernya sebesar 1 detik tanpa mengubah isi kode sumber?
2. Mengapa algoritma deteksi secret berbasis Shannon Entropy tidak cocok diterapkan pada file biner kompilasi (misal executable ELF atau gambar PNG)?
3. Di mana letak signature kriptografis disimpan ketika kita membuat signed commit via `git commit -S`?
4. Apa perbedaan mendasar antara implementasi `pre-commit` hook dengan `pre-receive` hook dalam konteks perannya sebagai security gate?
5. Mengapa format pelaporan SARIF (Static Analysis Results Interchange Format) menjadi standar interoperabilitas de-facto pada pipeline AppSec modern?

#### Bagian B: Analisis & Arsitektur (Intermediate)
6. Sebuah pipeline CI/CD GitHub Actions menggunakan `actions/checkout@v4` dengan parameter default `fetch-depth: 1`. Mengapa pengaturan ini membuat scanner Gitleaks gagal mendeteksi credential leak yang terjadi pada 2 commit sebelumnya di branch PR yang sama?
7. Bagaimana penyerang dapat memalsukan identitas author (`Author: security-lead <lead@bank.com>`) pada sebuah commit, dan mengapa mekanisme Branch Protection "Require Signed Commits" berhasil menggagalkan serangan ini secara matematis?
8. Analisis kelemahan keamanan dari implementasi Git pre-commit hook lokal murni tanpa didampingi server-side branch protection gate!
9. Jelaskan alur interaksi pertukaran token OIDC antara GitHub Actions runner dengan AWS STS menggunakan diagram alur relasional!
10. Pada Semgrep rule, apa perbedaan signifikan antara penggunaan pattern syntax matching murni (`pattern: $X.execute(...)`) dibandingkan dengan semantic taint mode (`mode: taint`)?

#### Bagian C: Skenario Kasus Produksi
11. **Skenario Incident Response**: Sebuah secret produksi AWS Access Key tertulis di commit history 3 bulan lalu pada branch `main` sebuah repositori internal. Tim Anda memutuskan untuk merotasi secret dan membersihkan history Git menggunakan `git-filter-repo`. Namun, 15 tim lain yang menggunakan repositori tersebut mengalami error *divergent branches* saat melakukan `git pull`. Rancang langkah mitigasi teknis dan prosedur komunikasi devops untuk memulihkan alur kerja para engineer tanpa mengorbankan keamanan history baru yang sudah bersih!
12. **Skenario Bypass CODEOWNERS**: Seorang insinyur senior yang memiliki hak merge administrator ingin merilis hotfix darurat. Insinyur tersebut mengedit file `/internal/crypto/aes.go` yang berada di bawah kepemilikan tim Security. Karena tim Security sedang offline (di luar jam kerja), ia menggunakan akses admin untuk membypass approval requirement. Rancang mekanisme arsitektur automated rollback atau break-glass pattern berbasis audit log yang dapat mencegah atau memantau tindakan ini secara real-time!
13. **Skenario Performance vs Security**: Eksekusi SAST AST Semgrep pada monorepo memicu *timeout* runner CI karena kehabisan alokasi RAM (Out Of Memory / OOMKilled) ketika memindai direktori `node_modules` dan build artifact target Java. Tuliskan file konfigurasi ignore list dan instruksi CLI scanning optimal yang membatasi analisis hanya pada source file murni, namun tetap mempertahankan akurasi cross-file semantic context!

---

### 16. Summary

Implementasi **Secure Coding dan Git Governance** modern mentransformasikan sistem Git dari sekadar version tracking pasif menjadi **Cryptographically Enforced Verification Boundary**. 

Pondasi utama governance ini bersandar pada empat pilar:
1. **Identitas Kriptografis Tak Terbantahkan (*Non-repudiation*)**: Menjamin bahwa seluruh perubahan kode diverifikasi oleh public-key infrastructure melalui Signed Commits (SSH/GPG/Sigstore), menutup celah commit spoofing secara permanen.
2. **Shift-Left Detection Multi-Tier**: Memadukan Regex terarah dan Shannon Entropy calculation pada local developer hook (`pre-commit`), server ingress guard (`pre-receive`), dan CI delta validation (`gitleaks`).
3. **AST-Driven Static Analysis**: Melampaui limitasi linter tekstual konvensional dengan menganalisis code flow, taint vulnerabilities, dan semantic integrity menggunakan Semgrep dengan output SARIF standar OASIS.
4. **Tokenless Zero-Trust Infrastructure**: Mengeliminasi long-lived static credentials pada CI runner melalui federasi identitas OIDC, memastikan bahwa akses ke resource produksi terisolasi secara ketat berdasarkan state context commit dan branch rules yang sah.

Penerapan disiplin ini menjamin bahwa rantai pasok perangkat lunak (*software supply chain*) aman sejak baris kode pertama diketik di workstation engineer hingga terkompilasi menjadi artefak produksi yang tersertifikasi.