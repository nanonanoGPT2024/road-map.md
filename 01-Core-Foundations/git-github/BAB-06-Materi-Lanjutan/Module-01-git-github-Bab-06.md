# Bab 06 Module 01: GitHub Platform Engineering & Governance

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `GIT-ENG-06-01`
* **Nama Modul**: GitHub Platform Engineering: Enterprise Architecture, Governance, & Rulesets
* **Kategori**: `01-Core-Foundations`
* **Tingkat Kesulitan**: *Advanced / Enterprise-Grade*
* **Prasyarat**:
  * Pemahaman mendalam tentang Git Internals, DAG (*Directed Acyclic Graph*), dan referensi objek (`refs/heads/*`, `refs/tags/*`).
  * Pemahaman arsitektur branch workflow (Trunk-Based Development, GitFlow).
  * Pengalaman dasar dengan GitHub Organization, Pull Request life-cycle, dan Continuous Integration (CI).
  * Kemampuan membaca format deklaratif Infrastructure as Code (Terraform/OpenTofu) dan manipulasi API via GitHub CLI (`gh`) atau cURL.
* **Estimasi Waktu Belajar**: 180 Menit (Teori: 60 Menit, Praktik Hands-On: 120 Menit)
* **Author / Maintainer**: Technical Curriculum Architect & Principal Platform Engineer
* **Target Audiens**: Enterprise Platform Engineers, DevSecOps Engineers, Cloud/Infrastructure Architects, Engineering Managers.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Merancang (C4, C6)** topologi Enterprise Account, Organizations, dan Nested Teams pada GitHub Enterprise Cloud/Server sesuai struktur organisasi skala besar.
2. **Mengonfigurasi dan Mengimplementasikan (C3)** *Role-Based Access Control* (RBAC) tingkat lanjut menggunakan *Enterprise Managed Users* (EMU), *Custom Repository Roles*, dan integrasi identity provider berbasis SAML 2.0 serta SCIM.
3. **Mengevaluasi dan Menerapkan (C5, C3)** *Repository Rulesets* lintas repositori dan organisasi untuk menegakkan integritas rantai pasok perangkat lunak (*software supply chain integrity*), termasuk penegakan *commit signature*, konvensi metadata cabang, proteksi linear history, dan pembatasan push bypass.
4. **Mengotomatisasi (C3, C6)** manajemen *Governance-as-Code* memanfaatkan GitHub REST/GraphQL API dan Terraform GitHub Provider.
5. **Menyelidiki dan Mengaudit (C4, C5)** anomali akses dan pelanggaran kebijakan keamanan menggunakan *GitHub Audit Log*, *Audit Log Streaming* ke SIEM, serta *Secret Scanning/Push Protection*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                    [GitHub Enterprise Account]
                                |
       +------------------------+------------------------+
       |                                                 |
[Global Policies]                              [Identity & Access]
       |                                                 |
       +---> Repository Creation Policies                +---> SAML 2.0 / OIDC (IdP)
       +---> Forking & Visibility Rules                  +---> SCIM Provisioning
       +---> Two-Factor Authentication (2FA)             +---> Enterprise Managed Users (EMU)
       |                                                 |
       v                                                 v
[GitHub Organizations] <----------------------+ [IdP-Linked Teams]
       |                                      |   (Nested Teams)
       +---> Base Permissions                 |          |
       +---> Custom Repository Roles          +----------+
       |                                                 |
       +=================================================+
                                |
                                v
               [Repository Governance Engine]
                                |
      +-------------------------+-------------------------+
      |                                                   |
[Legacy Branch Protections]                      [Repository Rulesets]
 (Deprecated at Scale)                          (Targeted / Layered / Scalable)
                                                          |
                                      +-------------------+-------------------+
                                      |                   |                   |
                               [Branch Rules]      [Tag Rules]         [Push Rules]
                                      |                   |                   |
                               - Signed Commits    - Immutable Tags    - File Path Restr.
                               - Linear History    - SemVer Pattern    - File Size Limits
                               - Required Reviews                      - Secret Scanning
                               - Status Checks
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Ketika skala rekayasa perangkat lunak bertumbuh dari belasan engineer menjadi ratusan atau ribuan engineer di berbagai zona waktu, pendekatan manajemen Git yang bersifat *ad-hoc* atau manual akan memicu kegagalan sistemik:

1. **Pencegahan Repo Sprawl dan Drift Konfigurasi**: Tanpa tata kelola terpusat, setiap tim akan membuat repositori dengan standar keamanan yang berbeda-beda. Sebagian mengizinkan *force-push* ke `main`, sebagian mengabaikan *code review*, dan sebagian membiarkan repositori internal terekspos menjadi publik secara tidak sengaja.
2. **Kepatuhan Regulasi dan Audit Industri**: Kerangka kerja seperti SOC 2 Type II, ISO/IEC 27001, PCI-DSS v4.0, dan HIPAA mewajibkan adanya segregasi tugas (*segregation of duties*), proteksi kode produksi dari modifikasi sepihak, verifikasi identitas mutlak (*commit signing*), serta jejak audit (*audit trail*) yang tidak dapat diubah (*tamper-proof*).
3. **Keamanan Rantai Pasok Perangkat Lunak (*Software Supply Chain Security*)**: Serangan modern menyusup melalui dependensi atau kompromi akun developer. Menerapkan verifikasi kriptografis via SSH/GPG signing, status check CI/CD yang terisolasi, dan push protection adalah garis pertahanan pertama platform engineering.
4. **Efisiensi Operasional Platform Engineer**: Mengelola proteksi branch di 2.000 repositori secara manual adalah resep bencana operasional. *Governance-as-Code* memungkinkan satu kebijakan repositori dideklarasikan sekali dan diberlakukan secara otomatis (*enforced*) ke seluruh repositori yang ada saat ini maupun yang akan dibuat di masa depan.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Hierarki Enterprise GitHub
Struktur organisasi tingkat tinggi GitHub terdiri dari:
* **Enterprise Account**: Entitas tata kelola tertinggi yang membawahi banyak organisasi. Digunakan untuk konsolidasi penagihan, kebijakan global (misal: mematikan forking publik di semua organisasi), dan integrasi Single Sign-On (SSO) terpusat.
* **Organization**: Ruang kerja kolaboratif bersama untuk proyek-proyek yang saling terkait. Menjadi batas isolasi (*isolation boundary*) untuk tim, repositori, paket, dan billing runner.
* **Teams & Nested Teams**: Pengelompokan akun pengguna yang mencerminkan struktur organisasi nyata perusahaan. Mendukung pewarisan izin (*permission inheritance*) bertingkat.

### 2. Enterprise Managed Users (EMU)
Arsitektur identitas di mana akun GitHub sepenuhnya dimiliki dan dikendalikan oleh Identity Provider (IdP) perusahaan (seperti Okta, Microsoft Entra ID, atau PingFederate). Pengguna masuk via SSO, akun dibuat via SCIM, dan pengguna tidak dapat mengubah username, email, atau membuat repositori di luar domain perusahaan.

### 3. Custom Repository Roles
Mekanisme pemberian hak akses berprinsip *Least Privilege*. Alih-alih hanya mengandalkan peran statis bawaan (*Read, Triage, Write, Maintain, Admin*), Platform Engineer dapat meracik izin granular (contoh: peran "Release Engineer" yang hanya memiliki hak membuat *release tag* dan menjalankan GitHub Actions, tetapi tidak memiliki hak administratif untuk menghapus repositori).

### 4. Repository Rulesets
Evolusi modern dari *Classic Branch Protection*. Rulesets menyediakan:
* **Pemberlakuan Multi-Level**: Dapat diterapkan di level Organisasi (berlaku lintas ratusan repositori) atau level Repositori individual.
* **Layering & Composition**: Beberapa ruleset dapat aktif bersamaan pada target cabang yang sama; aturan yang paling ketat akan selalu dimenangkan (*most restrictive takes precedence*).
* **Bypass List Eksplisit**: Hak untuk melewati aturan dapat dialokasikan secara presisi ke peran tertentu (misalnya *Organization Admin* atau *Deploy Key/GitHub App*) dengan mekanisme audit bypass.
* **Penerapan Berdasarkan Kriteria Dinamis**: Aturan dapat menargetkan repositori berdasarkan pola nama (`*-service`), topik repositori (`compliance:pci`), atau tipe kepemilikan.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Siklus Evaluasi Ruleset pada Git Push & Pull Request

Setiap kali developer menjalankan operasi `git push` atau mencoba me-merge Pull Request, GitHub memproses permintaan melalui *Policy Evaluation Engine*:

```
[Developer: git push]
        |
        v
[1. Authn & Authz Check] ---> Gagal? ---> [HTTP 401/403: Abort]
        |
        + (Sukses: Identitas terverifikasi via SSH/PAT & SAML)
        v
[2. Enterprise Global Policies] ---> Pelanggaran? ---> [Push Ditolak]
        |
        v
[3. Target Ref Resolution] (misal: refs/heads/main, refs/tags/v1.0.0)
        |
        v
[4. Ruleset Evaluation Engine]
        |
        +---> Evaluasi Ruleset Level Organisasi
        +---> Evaluasi Ruleset Level Repositori
        +---> Menggabungkan Seluruh Aturan Aktif (AND Logic)
        |
        +---> [Pengecekan: Apakah Actor ada di Bypass List?]
        |       |-- Ya -> Lanjut dengan status 'Bypassed' (Dicatat di Audit Log)
        |       \-- Tidak -> Jalankan Enforcements:
        |                     * Commit Signature valid? (GPG/SSH/X.509)
        |                     * Branch name / commit message metadata cocok regex?
        |                     * Secret scanning mendeteksi credential bocor?
        |                     * Linear history terjaga (tanpa merge commit non-fast-forward)?
        v
[5. GitHub Actions / Status Checks Gate] (Khusus PR Merge)
        |
        +---> Status checks (Linter, Unit Test, SAST) = SUCCESS?
        +---> Code Owner review approvals >= threshold minimum?
        +---> Tidak ada unresolved conversation?
        v
[6. Ref Updated / Git Object Written to Disk]
```

### 2. Integrasi Identitas: SAML 2.0 + SCIM Flow

1. **Autentikasi (SAML 2.0)**: Mengontrol *apakah* pengguna diizinkan masuk ke ekosistem GitHub Enterprise. Autentikasi diarahkan ke IdP perusahaan.
2. **Sinkronisasi (SCIM - System for Cross-domain Identity Management)**: Mengontrol *siklus hidup* akun. Ketika karyawan masuk (onboarding) di IdP dan dimasukkan ke grup "Security-Team", SCIM API secara asinkron membuat akun di GitHub dan memasukkannya ke Team GitHub yang berkorespondensi. Saat karyawan resign (offboarding), penonaktifan di IdP secara instan mencabut akses token, SSH key, dan sesi aktif di GitHub.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Topologi Hubungan Multi-Org Governance & Ruleset Enforcement

```
+---------------------------------------------------------------------------------------------------+
| GITHUB ENTERPRISE ACCOUNT: ACME-CORP                                                               |
| [Policy]: Enforce 2FA | Strict Member Privileges | Centralized Audit Streaming to Datadog/Splunk  |
+---------------------------------------------------------------------------------------------------+
       |                                                               |
       v                                                               v
+--------------------------------------------------+  +---------------------------------------------+
| ORGANIZATION: acme-core-infrastructure           |  | ORGANIZATION: acme-digital-banking (PCI-DSS)|
| Base Perm: Read                                  |  | Base Perm: None                             |
+--------------------------------------------------+  +---------------------------------------------+
       |                                                               |
       +--- [Enterprise Ruleset: org-wide-security]                    +--- [Enterprise Ruleset: pci-high-security]
       |    - Target: refs/heads/main, refs/heads/release/*            |    - Target: default branches
       |    - Require Signed Commits: TRUE                             |    - Require Signed Commits: TRUE
       |    - Block Force Pushes: TRUE                                 |    - Require Linear History: TRUE
       |    - Status Checks: [ci/security-scan]                        |    - Status Checks: [sast, pci-gate]
       |    - Bypass Actor: "acme-release-bot" (App Only)              |    - Bypass Actor: NONE (Strict)
       |                                                               |    - Code Reviews: >= 2 Reviewers
       |                                                               |    - Dismiss stale reviews on push
       v                                                               v
+--------------------------------------------------+  +---------------------------------------------+
| REPOSITORIES:                                    |  | REPOSITORIES:                               |
|                                                  |  |                                             |
|  [repo: terraform-aws-network]                   |  |  [repo: ledger-service]                     |
|  Rulesets Aktif:                                 |  |  Rulesets Aktif:                            |
|  1. Org-wide-security (Inherited)                |  |  1. Pci-high-security (Inherited)           |
|  2. Repo-specific: Lock-production-tags          |  |  2. Branch protection: strict CODEOWNERS    |
+--------------------------------------------------+  +---------------------------------------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah automasi inspeksi dan pengujian status tata kelola repositori menggunakan GitHub CLI (`gh`).

### Skrip Pemeriksaan Kepatuhan Branch Protection / Ruleset

Simpan skrip berikut dengan nama `audit-branch-governance.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ORG="acme-corp"
REPO="payment-gateway"
BRANCH="main"

echo "=== Memeriksa Konfigurasi Tata Kelola untuk ${ORG}/${REPO}:${BRANCH} ==="

# 1. Periksa apakah branch 'main' dilindungi oleh Rulesets aktif
echo "[+] Mengevaluasi active rulesets via GitHub API..."
RULES_APPLIED=$(gh api \
  -H "Accept: application/vnd.github+json" \
  "/repos/${ORG}/${REPO}/rules/branches/${BRANCH}" \
  --jq '.[].type' 2>/dev/null || true)

if [ -z "$RULES_APPLIED" ]; then
    echo "[-] PERINGATAN KRITIKAL: Cabang ${BRANCH} tidak memiliki Ruleset aktif!"
    exit 1
fi

echo "[✓] Ruleset terdeteksi aktif:"
echo "$RULES_APPLIED" | sed 's/^/    - /'

# 2. Pastikan aturan 'required_signatures' aktif
if echo "$RULES_APPLIED" | grep -q "required_signatures"; then
    echo "[✓] Compliance PASS: Signed Commits diwajibkan."
else
    echo "[!] Compliance FAIL: Signed Commits TIDAK aktif pada branch ${BRANCH}."
    exit 2
fi

# 3. Pastikan force push diblokir
if echo "$RULES_APPLIED" | grep -q "non_fast_forward"; then
    echo "[✓] Compliance PASS: Force Push diblokir secara eksplisit."
fi

echo "=== Audit selesai: Repositori mematuhi baseline minimum. ==="
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut adalah implementasi nyata *Governance-as-Code* menggunakan HashiCorp Terraform / OpenTofu dengan `integrations/github` provider. Pola ini merefleksikan standar arsitektur platform engineering produksi.

### Struktur File

```
governance-platform/
├── main.tf
├── versions.tf
├── teams.tf
└── rulesets.tf
```

### `versions.tf`

```hcl
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }
}

provider "github" {
  owner = "acme-corp" # Target GitHub Organization
}
```

### `teams.tf`

```hcl
# Mendefinisikan Root Engineering Team
resource "github_team" "engineering" {
  name        = "engineering"
  description = "Seluruh staf divisi Engineering"
  privacy     = "closed"
}

# Nested Team untuk Platform Engineering (Inherit dari Engineering)
resource "github_team" "platform_engineering" {
  name           = "platform-engineering"
  description    = "Core Platform & Infrastructure Engineers"
  privacy        = "closed"
  parent_team_id = github_team.engineering.id
}

# Peran Repositori Kustom: "Security Reviewer"
# Memberikan izin audit & security review tanpa izin write langsung ke branch
resource "github_custom_role" "security_reviewer" {
  name        = "Security Auditor"
  description = "Akses read-only plus kemampuan manajemen security advisories"
  base_role   = "read"
  permissions = [
    "view_secret_scanning_alerts",
    "view_dependabot_alerts",
    "view_code_scanning_alerts"
  ]
}
```

### `rulesets.tf`

Implementasi Repository Ruleset di tingkat Organisasi yang secara otomatis mengunci seluruh cabang default di semua repositori produksi (`target = "all"` atau berbasis dynamic criteria).

```hcl
resource "github_organization_ruleset" "production_safety_gate" {
  name        = "enterprise-production-guardrails"
  target      = "branch"
  enforcement = "active"

  # Terapkan hanya pada repositori dengan topik 'production'
  conditions {
    repository_name {
      include = ["~ALL"]
      exclude = []
      protected = true
    }
  }

  rules {
    # 1. Mengharuskan setiap commit memiliki cryptographic signature (GPG / SSH / S/MIME)
    commit_signature = true

    # 2. Blokir penghapusan cabang target
    deletion = true

    # 3. Blokir force push (non-fast-forward updates)
    non_fast_forward = true

    # 4. Enforce format linear history (larang explicit merge commit)
    required_linear_history = true

    # 5. Konfigurasi Pull Request Requirements
    pull_request {
      required_approving_review_count = 2
      dismiss_stale_reviews_on_push     = true
      require_code_owner_review         = true
      require_last_push_approval       = true
    }

    # 6. Status Checks yang WAJIB lolos sebelum merge
    required_status_checks {
      strict_required_status_checks_policy = true

      required_check {
        context = "security/static-analysis"
      }
      required_check {
        context = "ci/unit-integration-tests"
      }
    }
  }

  # Konfigurasi Bypass List secara selektif (Principle of Least Privilege)
  bypass_actors {
    # Hanya GitHub App terverifikasi (Automation Bot) yang boleh melakukan bypass darurat
    actor_id    = 123456 # ID Aplikasi Automation / Emergency Breakglass
    actor_type  = "Integration"
    bypass_mode = "always"
  }
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi | Pendekatan A: Restriktif Maksimal (Strict Governance) | Pendekatan B: Fleksibel / Otonom (Developer-First) | Rekomendasi Arsitektural Platform |
| :--- | :--- | :--- | :--- |
| **Kecepatan Rilis (*Velocity*)** | Menurun. Setiap push minor butuh 2 approval, signed commit, dan full CI pipeline. | Sangat tinggi. Developer dapat melakukan hotfix langsung ke `main` secara instan. | Gunakan Rulesets adaptif: Branch `develop` lebih longgar, `main` dilindungi ketat. Sediakan jalur automated pipeline. |
| **Manajemen Akses (RBAC)** | EMU + IdP Only. Pengguna lokal diblokir mutlak. Karyawan kontraktor sulit masuk. | Akses repositori ditambahkan manual via GitHub Username individu (*direct collaborators*). | **Wajib EMU** untuk Enterprise. Rekanan luar/kontraktor dimasukkan via akun guest di IdP dengan boundary jelas. |
| **Branch Protections vs Rulesets** | **Rulesets**: Skalabel lintas organisasi, support target pattern, mudah di-template via IaC. | **Classic Branch Protection**: Konfigurasi per-repo manual via Web UI, rentan konfigurasi drift. | **Standardisasi ke Rulesets**. Classic branch protection sudah berada di status pemeliharaan usang (*soft deprecated*). |
| **Bypass Capabilities** | Bypass mode dimatikan secara absolut (`bypass_actors = []`). | Organisasi Admin diberikan izin bypass tanpa syarat. | Izinkan bypass HANYA untuk *GitHub App Service Account* dengan audit logging, jangan pernah berikan bypass permanen ke manusia (*human users*). |

---

## SEKSI 11 — BEST PRACTICES

1. **Jadikan IdP sebagai Single Source of Truth (SSOT)**:
   * Sinkronisasikan grup IdP ke GitHub Teams secara terotomatisasi via SCIM. Jangan pernah menambahkan anggota repositori secara individual (*direct repository collaborator*).
2. **Standardisasi Policy-as-Code via Terraform**:
   * Seluruh modifikasi repositori, roles, permissions, dan ruleset wajib melalui pull request pada repositori meta-governance. Tidak boleh ada platform engineer yang mengubah konfigurasi ruleset langsung melalui GUI GitHub.
3. **Wajibkan Signed Commits Tanpa Pengecualian**:
   * Pasang aturan `commit_signature = true`. Hal ini melindungi organisasi dari penipuan identitas komit (*commit spoofing*), di mana aktor jahat memalsukan header `Author: engineer@acme.com`.
4. **Aktifkan Push Protection untuk Secret Scanning**:
   * Terapkan push protection di level Enterprise. Saring token AWS, private key, dan API keys sebelum blok git commit berhasil keluar dari workstation lokal engineer.
5. **Streaming Audit Log Real-Time**:
   * Jangan biarkan Audit Log hanya tersimpan di GitHub. Lakukan stream log menggunakan protokol Syslog/HTTPS ke SIEM (seperti Datadog, Splunk, atau AWS S3 via Kinesis Firehose) untuk kepatuhan WORM (*Write Once Read Many*) dan deteksi intrusi real-time.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Menggunakan Personal Access Tokens (PAT) Classic untuk Service Automation**:
   * *Anti-pattern*: CI/CD pipeline menggunakan PAT milik akun personal Lead Engineer. Saat engineer resign, pipeline runtuh seketika.
   * *Solusi*: Gunakan **GitHub Apps** terkelola atau **Fine-grained Personal Access Tokens** dengan batasan waktu kedaluwarsa serta hak akses spesifik ke repositori tertentu.
2. **Pola "All-Admin" Organization Members**:
   * Memberikan peran *Owner* pada level Organisasi kepada banyak orang untuk mempermudah konfigurasi. Satu akun terkompromi akan meruntuhkan seluruh arsitektur repositori organisasi. Batasi Organization Owner maksimal 3–5 akun darurat (*breakglass accounts*).
3. **Mengabaikan "Dismiss Stale Pull Request Approvals"**:
   * Developer A meng-approve PR milik Developer B. Developer B kemudian menambahkan commit berbahaya baru sebelum melakukan merge. Jika opsi `dismiss_stale_reviews_on_push` dinonaktifkan, PR dapat di-merge tanpa review ulang atas commit terbaru tersebut.
4. **Salah Mengonfigurasi Scope Regex pada Target Ruleset**:
   * Membuat rule untuk `refs/heads/release*` yang berniat mengunci branch `release/v1.0`, tetapi tidak sengaja mencakup branch testing developer `release-test-feature-x`, mengunci alur kerja yang tidak semestinya.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario
Anda diangkat sebagai Lead Platform Engineer di perusahaan fintech. Anda ditugaskan membangun arsitektur tata kelola baru untuk repositori microservice inti.

### Tugas 1: Guided Exercise
1. Buat branch baru bernama `governance-test` pada repositori latihan Anda.
2. Melalui GitHub CLI (`gh`), buat branch ruleset berbasis JSON payload yang memberlakukan `required_signatures` dan mencegah `non_fast_forward` push pada branch tersebut.
3. Gunakan perintah cURL/gh berikut:

```bash
gh api \
  --method POST \
  -H "Accept: application/vnd.github+json" \
  "/repos/{owner}/{repo}/rulesets" \
  -f name="strict-signature-guard" \
  -f target="branch" \
  -f enforcement="active" \
  -F "conditions[ref_name][include][]=refs/heads/governance-test" \
  -F "conditions[ref_name][exclude]=[]" \
  -F "rules[][type]=required_signatures" \
  -F "rules[][type]=non_fast_forward"
```

### Tugas 2: Semi-Guided Challenge
1. Cobalah membuat commit lokal tanpa cryptographic signature (`git commit -m "unverified commit"` tanpa flag `-S`).
2. Lakukan `git push origin governance-test`.
3. Analisis dan catat pesan error penolakan dari Git hook server GitHub.
4. Konfigurasikan GPG atau SSH signing key di workstation Anda, buat commit yang tertandatangani secara valid (`git commit -S -m "verified commit"`), lalu lakukan push ulang. Buktikan bahwa push berhasil.

### Tugas 3: Autonomous Platform Challenge
Tuliskan konfigurasi Terraform HCL modular yang dapat:
* Menerima variabel `environment` (`production` atau `staging`).
* Jika `production`, deploy Organization Ruleset yang mengunci branch `main` dengan syarat minimal 2 PR reviews, require CODEOWNERS, wajib linear history, dan status check CI `lint` serta `security-gate`.
* Jika `staging`, terapkan aturan lebih longgar: 1 PR review, tanpa kewajiban linear history.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan-pertanyaan berikut untuk menguji pemahaman konseptual dan operasional Anda.

### Pertanyaan 1
Mengapa *Repository Rulesets* lebih disarankan dibandingkan *Classic Branch Protection* untuk lingkungan Enterprise berskala besar?
* A. Classic Branch Protection tidak mendukung verifikasi pull request.
* B. Rulesets memungkinkan penerapan kebijakan berlapis (*layered enforcement*) lintas ratusan repositori sekaligus menggunakan kriteria target dinamis dan mendukung integrasi IaC yang lebih terstruktur.
* C. Classic Branch Protection hanya dapat dikonfigurasi melalui GitHub Enterprise Server versi On-Premise.
* D. Rulesets menghapus kebutuhan status checks pada CI pipeline.

### Pertanyaan 2
Seorang developer mencoba melakukan merge PR yang telah di-approve oleh 2 rekan tim. Namun tombol merge tetap terblokir dengan pesan: *"Merging can only be performed via linear history"*. Apa akar penyebab masalah ini dan bagaimana cara developer memperbaikinya?
* A. Developer belum menandatangani (signed) commit terakhir. Solusi: Gunakan `git commit --amend -S`.
* B. Branch target telah dihapus. Solusi: Buat ulang branch target.
* C. Terdapat merge commit non-fast-forward dalam riwayat branch fitur tersebut. Solusi: Jalankan `git rebase origin/main` untuk meratakan riwayat commit sebelum me-merge.
* D. Aktor tidak memiliki izin bypass. Solusi: Hubungi Enterprise Owner untuk meminta status Admin.

### Pertanyaan 3
Fitur keamanan apa yang secara langsung mencegah insiden kebocoran kredensial (seperti token AWS atau Stripe API Key) *sebelum* commit tersimpan ke riwayat remote repository GitHub?
* A. Dependabot Alerts.
* B. Secret Scanning with Push Protection.
* C. CodeQL SAST Analysis.
* D. Mutual TLS Authentication.

### Pertanyaan 4
Jika sebuah repositori terikat oleh dua Ruleset:
1. **Ruleset Tingkat Organisasi**: Mewajibkan minimal 2 approvals dan signed commits.
2. **Ruleset Tingkat Repositori**: Mewajibkan minimal 1 approval dan status check `ci/test`.

Bagaimana GitHub Ruleset Engine mengevaluasi kondisi ini saat terjadi Pull Request?
* A. Ruleset tingkat Repositori menimpa (override) Ruleset Organisasi. Hanya 1 approval yang dibutuhkan.
* B. Terjadi error collision dan PR otomatis ditutup oleh sistem.
* C. GitHub menerapkan logika gabungan paling restriktif (*most restrictive*): Dibutuhkan minimal 2 approvals, signed commits, DAN status check `ci/test`.
* D. Hanya Ruleset yang dibuat paling awal yang akan dieksekusi.

### Pertanyaan 5
Apa risiko kepatuhan terbesar jika tim Platform Engineering memberikan hak akses langsung (*direct collaborator access*) kepada developer individu alih-alih menggunakan IdP-driven SCIM synced teams?
* A. Waktu proses `git clone` menjadi jauh lebih lambat karena beban autentikasi.
* B. Pengguna yang telah dinonaktifkan dari Identity Provider perusahaan saat offboarding masih tetap memiliki akses aktif ke repositori kode sumber jika akun personal GitHub-nya tidak dicabut manual.
* C. Fitur push protection otomatis nonaktif untuk kolaborator langsung.
* D. Pull Request tidak dapat diaudit melalui REST API.

---

### Kunci Jawaban & Rubrik Penilaian

* **Kunci Jawaban**:
  1. **B** — Rulesets dirancang khusus untuk skalabilitas enterprise (cross-repo enforcement, dynamic evaluation, granular bypass).
  2. **C** — Linear history melarang keberadaan *diamond merge commit*. Rebase diperlukan untuk memastikan semua commit tersusun linear di atas `HEAD` target branch.
  3. **B** — Push Protection bertindak sebagai interceptor hook pada fase `pre-receive` di sisi server GitHub, menolak push jika terdeteksi secret berformat cocok.
  4. **C** — Layered ruleset enforcement bersifat aditif dan memenangkan aturan yang paling restriktif (*most restrictive constraint wins*).
  5. **B** — Kurangnya de-provisioning otomatis via SCIM adalah celah audit fatal (SOC2/ISO27001 violation) karena mantan karyawan masih dapat mengakses IP internal.

* **Rubrik Skor**:
  * **5/5**: Mahir. Siap memegang tanggung jawab Enterprise Platform Governance.
  * **3–4/5**: Kompeten. Pahami kembali mekanisme inheritance dan layered enforcement rulesets.
  * **< 3/5**: Perlu remedial. Ulas kembali Seksi 05 dan 06 secara mendalam.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Dokumentasi Resmi GitHub**:
  * *About Rulesets*: `https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets`
  * *GitHub Enterprise Cloud EMU Architecture*: `https://docs.github.com/en/enterprise-cloud@latest/admin/identity-and-access-management/understanding-enterprise-managed-users`
  * *REST API for Repository Rulesets*: `https://docs.github.com/en/rest/repos/rules`
* **Infrastructure as Code**:
  * *Official Terraform GitHub Provider Documentation*: `https://registry.terraform.io/providers/integrations/github/latest/docs`
* **Keamanan Rantai Pasok & Standar Industri**:
  * *CIS GitHub Benchmark (Center for Internet Security)*: Standar konfigurasi keamanan hardening level 1 & 2 untuk GitHub Organizations.
  * *OpenSSF (Open Source Security Foundation) Scorecard*: Metrik evaluasi tata kelola otomatis untuk repositori terbuka/tertutup.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **Struktur Enterprise Modern**: Tata kelola GitHub skala enterprise mengandalkan pembagian berbasis **Enterprise Account -> Organizations -> Teams**, di mana identitas terikat mutlak pada **Identity Provider (IdP)** melalui **SAML 2.0** dan **SCIM**.
2. **Evolusi Aturan Repositori**: **Repository Rulesets** menggantikan legacy branch protection dengan kapabilitas penegakan lintas repositori, evaluasi dinamis, pewarisan bertingkat (*layered enforcement*), dan manajemen bypass yang dapat diaudit secara ketat.
3. **Integritas Rantai Pasok**: Penggunaan **Signed Commits**, **Linear History**, **Strict Required Status Checks**, dan **Push Protection** bukan sekadar fitur pelengkap, melainkan fondasi pertahanan platform software modern terhadap ancaman injeksi kode berbahaya.
4. **Governance-as-Code**: Konfigurasi keamanan dan hak akses tidak boleh dimodifikasi secara ad-hoc melalui antarmuka visual. Seluruh struktur tata kelola harus dideklarasikan, di-version-control, dan di-deploy menggunakan **Terraform** atau pipeline automasi API.

---

## SEKSI 17 — GLOSARIUM

* **EMU (Enterprise Managed Users)**: Tipe deployment GitHub Enterprise di mana akun pengguna dibuat, dikelola, dan dihapus secara eksklusif oleh sistem Single Sign-On perusahaan.
* **SCIM (System for Cross-domain Identity Management)**: Standar protokol berbasis HTTP terbuka untuk mengotomatiskan pertukaran informasi identitas pengguna antar-domain keamanan.
* **Repository Ruleset**: Sekumpulan aturan yang dapat dikonfigurasi untuk mengontrol bagaimana pengguna berinteraksi dengan cabang dan tag tertentu pada satu atau banyak repositori dalam organisasi.
* **Linear History**: Bentuk riwayat commit Git yang membentuk garis lurus tunggal tanpa commit penggabungan (*merge commit*) eksplisit non-fast-forward.
* **Signed Commit**: Commit Git yang memiliki signature kriptografis (GPG/SSH) yang dapat diverifikasi oleh server Git untuk menjamin integritas penulis (*author authenticity*).
* **Push Protection**: Mekanisme pencegahan di sisi server yang secara langsung memblokir `git push` apabila payload komit mengandung rahasia (*secret key*, token, password) yang teridentifikasi oleh scanner.
* **CODEOWNERS**: File konfigurasi khusus dalam repositori yang mendefinisikan individu atau tim yang secara otomatis diwajibkan memberikan approval review ketika file dalam jalur (*path*) tertentu diubah.
* **Audit Log Streaming**: Fitur enterprise untuk mentransmisikan rekaman event keamanan dan aktivitas administratif GitHub secara instan dan kontinu ke endpoint pengumpul log pihak ketiga.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Titik Kesulitan Siswa (Pain Points)**:
  * Siswa sering kali bingung membedakan antara *Organization Base Permissions* dengan *Custom Repository Roles*. Tekankan bahwa Base Permissions adalah batas bawah (baseline), sedangkan Custom Roles memberikan fleksibilitas tambahan tanpa perlu menaikkan user ke tier 'Admin'.
  * Kerancuan logika penegakan Ruleset berlapis (*layering*). Buat demonstrasi langsung di mana Ruleset Org mewajibkan 2 reviewer dan Ruleset Repo mewajibkan 1 reviewer: buktikan bahwa sistem menuntut 2 reviewer (selalu aturan terketat).
* **Setup Lab yang Dibutuhkan**:
  * Untuk menjalankan simulasi penuh, idealnya instans instruktur memiliki akses ke GitHub Enterprise Cloud (versi trial atau enterprise sandbox).
  * Jika hanya tersedia akun free/team, instruktur harus menjelaskan batasan fitur (misal: Rulesets di level Repo tetap bisa dicoba, namun Enterprise/Org-wide Ruleset membutuhkan lisensi Enterprise).
* **Fokus Diskusi Sesi Interaktif**:
  * Tanyakan: *"Kapan engineer diizinkan melakukan bypass terhadap ruleset?"* Arahkan diskusi ke pola *Emergency Breakglass Procedure* menggunakan GitHub Apps terisolasi alih-alih memberikan wewenang bypass ke akun pribadi.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi**: `1.0.0`
* **Tanggal Rilis**: 2025-02-15
* **Perubahan**:
  * Inisialisasi materi Bab 06 Module 01 standar arsitektur Enterprise Governance.
  * Transisi penuh materi dari *Legacy Branch Protection* ke *GitHub Repository Rulesets*.
  * Penambahan skrip Terraform HCL untuk declaratif ruleset & team mapping.
  * Penambahan diagram alir evaluasi aturan pada push event.
* **Status**: *Stable / Production-Ready*

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `GIT-PRO-05-03` — Advanced Merge Strategies, Conflict Resolution, & Rerere
* **Modul Saat Ini**: `GIT-ENG-06-01` — GitHub Platform Engineering: Enterprise Architecture, Governance, & Rulesets
* **Modul Berikutnya**: `GIT-ENG-06-02` — Secure CI/CD Automation: GitHub Actions Security, OIDC, & Supply Chain Defense (SLSA)