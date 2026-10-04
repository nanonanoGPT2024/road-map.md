## SEKSI 01 — IDENTITAS MODUL

* **Kurikulum:** `git-github`
* **Kategori:** `01-Core-Foundations`
* **Bab:** `09` — Repository Security, Compliance, & Secrets Management
* **Modul:** `01` — Repository Security, Compliance, & Secrets Management
* **Tingkat Kesulitan:** Advanced / Enterprise-Grade
* **Prasyarat:** Pemahaman mendalam tentang Git DAG (Directed Acyclic Graph), Git Plumbing/Porcelain commands, GitHub Branching Strategy, CI/CD Pipeline Fundamentals.
* **Alokasi Waktu:** 120 Menit (Teori & Praktik Terintegrasi)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta mampu:

1. **Menganalisis & Mengurangi Risiko Kriptografis:** Memahami integritas objek Git, transisi dari SHA-1 ke SHA-256, serta menerapkan penandatanganan commit (*cryptographic commit signing*) menggunakan GPG dan SSH keys.
2. **Mengimplementasikan Secrets Management Lifecycle:** Mencegah kebocoran kredensial secara lokal menggunakan *pre-commit hooks* (Gitleaks) dan remediate kebocoran historis menggunakan `git-filter-repo`.
3. **Menerapkan GitHub Governance & Compliance:** Mengonfigurasi *Repository Rulesets*, *Push Protection*, *Secret Scanning*, dan *CODEOWNERS* untuk memenuhi standar audit kepatuhan industri (SOC 2, ISO/IEC 27001, NIST SSDF).
4. **Mengeksekusi Incident Response Terstruktur:** Menjalankan protokol insiden kebocoran rahasia yang mencakup rotasi kredensial, perbaikan riwayat (*DAG rewrite*), dan koordinasi *force-push* mitigasi secara aman (`--force-with-lease`).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
[ SDLC / Dev Machine ]
       │
       ├── (1) Identity & Attestation ────► Commit Signing (GPG / SSH)
       │
       ├── (2) Local Guardrails ──────────► Pre-commit Hook (Gitleaks / TruffleHog)
       │
       ▼ [ git push ]
[ GitHub Edge Security ]
       │
       ├── (3) Push Gateways ─────────────► Push Protection (Secret Blockade)
       │
       ▼ [ Upstream Repository ]
[ Governance & Compliance ]
       │
       ├── (4) Access Control ────────────► Repository Rulesets & CODEOWNERS
       ├── (5) Continuous Audit ──────────► Secret Scanning & Dependabot
       └── (6) Disaster Remediation ─────► DAG Rewriting (git-filter-repo) + Rotation
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Dalam model keamanan rantai pasok perangkat lunak (*Software Supply Chain Security*), repositori Git bukan sekadar penyimpanan kode; ia adalah perimeter utama. Git menyimpan seluruh rekaman histori perubahan secara kekal (*immutable history*). Ketika variabel sensitif (seperti API tokens, private keys, database credentials) ter-commit, data tersebut akan tetap berada di dalam *object database* selamanya—meskipun telah dihapus pada commit berikutnya.

Serangan rantai pasok modern memanfaatkan metadata dan histori Git:
* **Eksfiltrasi Otomatis:** Bot penyerang memantau GitHub Public Event Stream secara *real-time*; token yang terdorong ke repositori publik rata-rata dieksploitasi dalam hitungan detik.
* **Spoofing Identitas:** Git mengizinkan pengguna memalsukan *author name* dan *email* secara trivial melalui `git config`. Tanpa tanda tangan kriptografis, atribusi commit tidak memiliki kekuatan hukum ataupun validitas audit.
* **Pelanggaran Kepatuhan Regulasi:** Kerangka kerja seperti SOC 2 Type II, ISO 27001, dan PCI-DSS mensyaratkan integritas kode (*tamper-proofing*), pemisahan tugas (*separation of duties*), dan larangan tegas atas penyimpanan *hardcoded secrets*.

---

## SEKSI 05 — APA ITU (WHAT)

**Repository Security & Secrets Management** adalah kombinasi kebijakan teknis, instrumentasi kriptografis, dan tata kelola repositori untuk menjamin:
1. **Confidentiality:** Pencegahan dan deteksi material sensitif di seluruh siklus hidup repositori.
2. **Integrity & Authenticity:** Verifikasi bahwa kode benar-benar berasal dari kontributor yang sah tanpa modifikasi pihak ketiga (*provenance & non-repudiation*).
3. **Governance & Compliance:** Penegakan aturan baku organisasi terhadap branching, *pull request approvals*, dan pembatasan akses mutasi riwayat.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Integritas Objek Git & Commit Signing
Git menggunakan *hash* SHA-1 (dan bertahap mengadopsi SHA-256) untuk mengidentifikasi objek: *blobs*, *trees*, *commits*, dan *tags*. Commit object berisi metadata: pointer ke tree root, commit induk (*parent*), committer, author, dan commit message.

```text
commit 178b... (header)
tree 4b825dc...
parent d670460...
author John Doe <john@example.com> 1700000000 +0000
committer John Doe <john@example.com> 1700000000 +0000
gpgsig -----BEGIN PGP SIGNATURE-----
 ... [Payload Kriptografis] ...
 -----END PGP SIGNATURE-----

Pesan Commit
```
Ketika commit ditandatangani (`git commit -S`), Git mengenkripsi digest commit menggunakan *private key* (GPG atau SSH). Pihak luar/GitHub memvalidasi digest tersebut dengan *public key* yang telah didaftarkan. Status **Verified** membuktikan bahwa metadata tidak dimanipulasi setelah penandatanganan.

### 2. Mekanisme Deteksi Rahasia (Static Analysis & Heuristics)
Alat seperti **Gitleaks** menggunakan kombinasi:
* **Regular Expressions (Regex):** Mencocokkan pola spesifik penyedia layanan (misal: AWS Access Key ID diawali `AKIA[0-9A-Z]{16}`).
* **Shannon Entropy:** Mengukur keacakan string. Nilai entropi tinggi di dalam string alfanumerik mengindikasikan *secret token* atau *private key*.
* **Path Exclusions:** Memfilter file non-kritis (e.g., lockfiles, test fixtures).

### 3. Anatomis Remediasi: DAG Rewriting
Jika sebuah secret masuk ke riwayat:
```text
C1 ──► C2 (Leaked Secret) ──► C3 ──► C4 (HEAD)
```
Menghapus file di `C5` **TIDAK** menghapus secret dari `C2`. Objek blob tetap ada di disk repositori dan riwayat Git. Remediasi memerlukan penulisan ulang seluruh commit child dari titik kebocoran menggunakan manipulasi Directed Acyclic Graph (DAG):
```text
C1 ──► C2' (Cleaned) ──► C3' ──► C4' (New HEAD)
```
Karena SHA commit bergantung pada konten tree dan SHA parent-nya, modifikasi `C2` mengubah seluruh hash sesudahnya.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Siklus Pertahanan Multi-Lapis (Defense-in-Depth Pipeline)

```text
+---------------------------------------------------------------------------------------+
| FASE 1: LOCAL DEVELOPER ENVIRONMENT                                                   |
|                                                                                       |
|   [Edit Code] ──► [git add] ──► [git commit]                                          |
|                                     │                                                 |
|                                     ▼                                                 |
|                     ┌───────────────────────────────┐                                 |
|                     │   Local Hook: .pre-commit     │                                 |
|                     │   - Gitleaks Static Scanning  │                                 |
|                     └───────────────┬───────────────┘                                 |
|                                     │                                                 |
|               [Secret Detected?] ───┴───► [Lolos / Bersih?]                           |
|                      │                               │                                |
|                      ▼ (Blokir Commit)               ▼                                |
|                 Abort Process                Sign Commit (SSH/GPG)                    |
+──────────────────────────────────────────────────────┬────────────────────────────────+
                                                       │
                                                       ▼ [git push origin main]
+---------------------------------------------------------------------------------------+
| FASE 2: GITHUB EDGE / PRE-RECEIVE LAYER                                               |
|                                                                                       |
|                     ┌───────────────────────────────┐                                 |
|                     │     Push Protection Engine    │                                 |
|                     │  - Enterprise Token Scanners  │                                 |
|                     └───────────────┬───────────────┘                                 |
|                                     │                                                 |
|               [Payload Valid?] ─────┴───► [Violations Detected?]                      |
|                      │                               │                                |
|                      │                               ▼ (Reject Push)                  |
|                      │                         HTTP 403 Forbidden                     |
|                      ▼                                                                |
+───────────────────────────────────────────────────────────────────────────────────────+
| FASE 3: TARGET REPOSITORY GOVERNANCE                                                  |
|                                                                                       |
|   ┌───────────────────────────────────────────────────────────────────────────────┐   |
|   │ GitHub Rulesets Engine                                                        │   |
|   │ ├── Enforce Linear History (No merge commits)                                 │   |
|   │ ├── Restrict Force Pushes                                                     │   |
|   │ ├── Mandatory CODEOWNERS Approvals                                            │   |
|   │ └── Require Signed Commits Verification                                       │   |
|   └───────────────────────────────────────────────────────────────────────────────┘   |
|                                      │                                                |
|                                      ▼                                                |
|                          Merge to Protected Branch                                    |
+---------------------------------------------------------------------------------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Konfigurasi penandatanganan commit berbasis SSH key (lebih modern, ringan, dan meniadakan dependensi runtime GPG).

### Langkah 1: Buat SSH Signing Key
```bash
ssh-keygen -t ed25519 -C "security-attested@company.com" -f ~/.ssh/id_git_signing
```

### Langkah 2: Konfigurasi Git Global
```bash
# Tentukan format penandatanganan SSH
git config --global gpg.format ssh

# Arahkan ke file public key
git config --global user.signingkey ~/.ssh/id_git_signing.pub

# Wajibkan tanda tangan di seluruh commit secara otomatis
git config --global commit.gpgsign true

# Konfigurasi program penandatanganan jika di macOS/Linux
git config --global gpg.ssh.program "ssh-keygen"
```

### Langkah 3: Eksekusi dan Verifikasi
```bash
git commit -m "feat: implement cryptographic attestation"
git log --show-signature -n 1
```

*Output yang diharapkan:*
```text
commit 8a3f9e... (HEAD -> main)
Good "ssh-ed25519" signature for security-attested@company.com with ED25519 key SHA256:abc...
Author: Security Engineer <security-attested@company.com>
Date:   Mon May 20 10:00:00 2024 +0700

    feat: implement cryptographic attestation
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Skenario Enterprise: Penerapan pipeline proteksi lokal, simulasi insiden kebocoran kredensial, scrubbing riwayat menggunakan tooling modern (`git-filter-repo`), dan penguncian branch via declarative ruleset.

### Tahap 1: Setup Shift-Left Secret Prevention (Gitleaks Engine)

Buat file `.pre-commit-config.yaml` di root repositori:

```yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.2
    hooks:
      - id: gitleaks
        stages: [commit]
```

Inisialisasi pre-commit:
```bash
pip install pre-commit
pre-commit install
```

### Tahap 2: Simulasi Insiden & Forensik Kebocoran

Secara tidak sengaja, file konfigurasi berisi production secret masuk ke dalam histori git:

```bash
# Developer memasukkan file rahasia
echo "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" > prod.env
git add prod.env
git commit --no-verify -m "chore: add configuration file" # Sengaja mem-bypass hook
```

Secret terlanjur terdorong ke remote repositori internal.

### Tahap 3: Emergency Protocol — History Scrubbing (`git-filter-repo`)

> **PERINGATAN KRITIS:** Sebelum membersihkan git history, **LAKUKAN ROTASI / REVOKASI KREDENSIAL DI AWS IAM SECARA INSTAN**. Asumsikan kredensial telah terkompromi!

Alat bawaan `git filter-branch` sudah berstatus *deprecated* oleh pengembang Git inti karena lambat dan tidak aman terhadap metadata korupsi. Gunakan **`git-filter-repo`** (berbasis Python).

1. Install `git-filter-repo`:
   ```bash
   pip install git-filter-repo
   ```

2. Buat fresh clone repositori sebagai workspace isolasi (*mirror*):
   ```bash
   git clone --no-local . ../repo-scrub-workspace
   cd ../repo-scrub-workspace
   ```

3. Jalankan pembersihan file `prod.env` dari seluruh histori Git:
   ```bash
   git filter-repo --invert-paths --path prod.env --force
   ```

4. Periksa apakah secret string masih ada di seluruh DAG:
   ```bash
   git log -S "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
   # Output harus KOSONG (menandakan commit pembawa nilai tersebut telah tereliminasi)
   ```

5. Hubungkan kembali remote dan lakukan sinkronisasi paksa secara aman:
   ```bash
   git remote add origin git@github.com:organization/secure-repo.git
   git push origin --force-with-lease --all
   git push origin --force-with-lease --tags
   ```

### Tahap 4: Mengonfigurasi GitHub Ruleset (Automated Compliance)

Gunakan GitHub API untuk mendefinisikan Repository Ruleset via skrip deklaratif `ruleset.json`:

```json
{
  "name": "Production Grade Guardrails",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/main"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "deletion"
    },
    {
      "type": "non_fast_forward"
    },
    {
      "type": "required_signatures"
    },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 2,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": true,
        "require_last_push_approval": true
      }
    }
  ]
}
```

Terapkan menggunakan GitHub CLI:
```bash
gh api \
  --method POST \
  -H "Accept: application/vnd.github+json" \
  /repos/organization/secure-repo/rulesets \
  --input ruleset.json
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Aspek / Pilihan | Keuntungan | Kerugian / Risiko | Kapan Harus Digunakan |
|---|---|---|---|
| **Commit Signing: SSH vs GPG** | SSH key mudah dibuat, didukung native oleh Git >= 2.34, menggunakan keypair yang sudah ada. | SSH keys tidak memiliki Web of Trust atau server keyserver terdesentralisasi seperti GPG. | Standar default internal enterprise modern. Gunakan GPG hanya bila regulasi lama memaksakannya. |
| **History Rewrite vs Git Revert** | Memotong jejak file secara permanen dari GitHub dan git log; menghapus liability audit. | Mengubah seluruh SHA hash turunan; mematahkan local tracking branch rekan tim; berisiko tinggi. | Wajib dieksekusi HANYA jika raw secret bernilai tinggi bocor ke repositori publik/akses luas. |
| **Pre-commit Hooks vs Push Protection** | Memberikan feedback instan langsung di mesin pengembang sebelum I/O jaringan. | Hook lokal dapat dibypass dengan `--no-verify`; bergantung pada disiplin lingkungan dev. | Terapkan pre-commit hook sebagai filter pertama, tetapi posisikan push protection sebagai gatekeeper mutlak. |
| **GitHub Rulesets vs Classic Branch Protection** | Mendukung inheritance di level organisasi, multiple rulesets per target, bypass list berbasis role/app. | Model konfigurasi lebih kompleks dengan parameter berlapis. | Seluruh repositori baru atau migrasi arsitektur enterprise skala besar. |

---

## SEKSI 11 — BEST PRACTICES

1. **Prinsip "Assume Breach":** Selalu asumsikan secret yang masuk ke commit—meskipun belum di-push—berpotensi terekspos. Prioritas pertama selalu **rotasi**, bukan scrubbing.
2. **Deklarasi CODEOWNERS Eksplisit:** Definisikan ownership atas path file sensitif (misal: CI/CD workflows, Terraform specs, file enkripsi) di `.github/CODEOWNERS`:
   ```text
   .github/workflows/ @organization/secops-team
   terraform/         @organization/cloud-infra-leads
   ```
3. **Audit Token Permissions:** Hindari penggunaan Classic Personal Access Tokens (PATs). Terapkan secara ketat **Fine-Grained Personal Access Tokens** dengan pembatasan hak akses repositori individual dan masa berlaku maksimal 90 hari.
4. **Isolasi CI Secrets:** Jangan pernah mengekspos environment variable yang memuat secrets ke job CI/CD yang dieksekusi dari untrusted Pull Request forks (*PwnRequest protection*).
5. **Gunakan Push Protection GitHub:** Aktifkan *Secret Scanning Push Protection* di level organisasi agar remote engine menolak commit secara otomatis jika mendeteksi format secret token standar (AWS, Stripe, Slack, dsb).

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Menghapus Secret Menggunakan Commit Baru
*Anti-pattern:*
```bash
git rm .env
git commit -m "fix: remove sensitive env file"
git push origin main
```
*Dampak Fatal:* File `.env` tetap tersimpan utuh di commit sebelumnya. Siapapun dapat mengambilnya via `git checkout HEAD~1 -- .env` atau via GitHub Commit View API.

### 2. Melakukan Remediasi Tanpa Rotasi Kredensial
Scrubbing riwayat Git menggunakan `git-filter-repo` memerlukan waktu beberapa menit hingga jam. Banyak pengembang menganggap masalah selesai setelah commit bersih, padahal crawler penyerang telah mengindeks API key tersebut dalam 5 detik pertama sejak push. Kredensial lama **wajib** dicabut (*revoked*) di dashboard provider.

### 3. Merusak Kolaborasi Tim Melalui Blind `git push --force`
Menimpa riwayat cabang utama menggunakan `--force` mentah dapat menimpa pekerjaan developer lain yang baru saja di-push.
*Solusi:* Selalu gunakan parameter pelindung konkurensi:
```bash
git push --force-with-lease origin <branch-name>
```

### 4. Menyimpan File Sensitif yang Dikecualikan di `.gitignore` Terlambat
`.gitignore` **hanya** berfungsi untuk file yang berstatus *untracked*. Jika file telah masuk ke Git index (*staged* atau *committed*), penambahan path ke `.gitignore` tidak akan menghapus tracking file tersebut.
*Solusi:*
```bash
git rm --cached <file-path>
```

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Deteksi Rahasia Lokal dengan Gitleaks
1. Inisialisasi repositori Git baru.
2. Pasang binari `gitleaks` di sistem Anda.
3. Buat file dummy `config.py` yang memuat teks tiruan: `AWS_KEY = "AKIAIOSFODNN7EXAMPLEB"`
4. Jalankan deteksi gitleaks secara ad-hoc:
   ```bash
   gitleaks detect --source . --verbose
   ```
5. Evaluasi laporan yang dihasilkan: identifikasi jenis secret, rule ID, commit hash, dan nomor baris pelanggaran.

### Latihan 2: Rekayasa Ulang DAG Historis
1. Buat 3 commit berturut-turut di repositori uji coba:
   * Commit 1: `setup project`
   * Commit 2: `leak password` (buat file `db_pass.txt` berisi plaintext password)
   * Commit 3: `feature implementation`
2. Gunakan `git-filter-repo` untuk memotong file `db_pass.txt` dari seluruh DAG.
3. Gunakan `git log --graph --oneline` dan `git log -p` untuk memastikan commit 2 terkonversi secara mulus tanpa jejak commit `db_pass.txt`, sementara Commit 1 dan Commit 3 tetap utuh (perhatikan perubahan hash Commit 3).

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Apa yang terjadi secara internal pada Git commit tree ketika Anda melakukan scrubbing satu file rahasia dari histori 10 commit yang lalu?**
   * A. Hanya commit yang berisi file tersebut yang berubah hash-nya; commit sesudahnya tetap sama.
   * B. Seluruh commit yang berada setelah commit yang di-scrub akan memiliki SHA-1/SHA-256 hash baru, karena hash commit mereferensikan hash parent secara berantai.
   * C. Git hanya menyembunyikan file tersebut menggunakan atribut `.git/info/exclude`.
   * D. Riwayat Git tidak dapat diubah; yang berubah hanyalah branch pointer.

2. **Mengapa `git push --force-with-lease` jauh lebih direkomendasikan daripada `git push --force` setelah melakukan operasi scrubbing riwayat?**
   * A. `--force-with-lease` secara otomatis merotasi token yang bocor di GitHub.
   * B. `--force-with-lease` mencegah penimpaan ref jika ada pembaruan commit dari anggota tim lain yang belum di-fetch ke lokal developer.
   * C. `--force-with-lease` tidak memerlukan hak akses write di branch protection rules.
   * D. Parameter tersebut secara otomatis menghapus cache GitHub Pull Request.

3. **Seorang developer memalsukan commit dengan menjalankan `git config user.name "CEO"` dan `git config user.email "ceo@company.com"`. Mekanisme apa yang mutlak menggagalkan penipuan ini pada level kepatuhan?**
   * A. Memeriksa file `.gitignore`.
   * B. Penegakan aturan *Signed Commits* (GPG/SSH) yang diverifikasi oleh GitHub Rulesets.
   * C. Mengaktifkan Dependabot alerts.
   * D. Menjalankan `git fsck`.

4. **Kapan waktu yang paling tepat untuk melakukan rotasi kredensial (API Key / Password) yang terlanjur ter-push ke GitHub?**
   * A. Setelah seluruh developer di tim menyetujui pembersihan histori.
   * B. Tepat sebelum melakukan `git push --force-with-lease`.
   * C. Detik pertama insiden disadari, mendahului seluruh proses pembersihan kode lokal atau histori Git.
   * D. Saat audit triwulanan SOC 2 tiba.

5. **Apa fungsi utama dari integrasi file `.github/CODEOWNERS` dalam kerangka kerja keamanan repositori?**
   * A. Memberikan hak akses administratif kepada developer tertentu ke server hosting.
   * B. Memaksa review dan approval wajib dari tim/individu yang bertanggung jawab atas komponen kode tertentu sebelum Pull Request dapat di-merge.
   * C. Mencegah user mengunduh kode program via zip file.
   * D. Mengotomatisasi penandatanganan commit.

### Kunci Jawaban:
1. **B** — Karakteristik kriptografis DAG Git mengikat hash parent pada setiap node anak. Modifikasi node lama otomatis memicu efek domino rekalkulasi hash hingga tip `HEAD`.
2. **B** — `--force-with-lease` memvalidasi bahwa referensi remote yang diketahui lokal sama dengan kondisi remote saat ini, menghindari insiden tertimpanya commit orang lain tanpa sengaja.
3. **B** — Git metadata *author* dapat diubah bebas, namun signature kriptografis hanya dapat dibuat oleh pemegang *private key* yang sah dan terdaftar pada identitas akun GitHub.
4. **C** — Rotasi langsung membatalkan nilai eksploitasi rahasia tersebut di cloud/infrastruktur target. Menunda rotasi demi membersihkan git history memberikan *window of vulnerability* bagi penyerang.
5. **B** — CODEOWNERS bertindak sebagai gerbang otorisasi review kode berbasis jalur direktori (*path-based authorization guard*).

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Git Core Documentation:** *Git Tools - Rewriting History & Signing Work* (https://git-scm.com/book/en/v2/)
* **GitHub Documentation:** *About repository security configurations and rulesets* (https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets)
* **OpenSSF (Open Source Security Foundation):** *Best Practices for Secure Software Development & Source Code Management*
* **git-filter-repo Documentation:** *The official recommended replacement for git-filter-branch* (https://github.com/newren/git-filter-repo)
* **Gitleaks Enterprise Repository:** *Auditing git repos for secrets and keys* (https://github.com/gitleaks/gitleaks)
* **NIST SP 800-218:** *Secure Software Development Framework (SSDF) - Task PW.1 & PW.2 (Protect Code Integrity)*

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. Repositori Git bersifat *append-only* secara historis; penghapusan file lewat commit standar tidak mengamankan data yang pernah bocor.
2. Identitas pengembang pada commit dapat dipalsukan secara sepihak; penandatanganan kriptografis (GPG/SSH) adalah satu-satunya mekanisme verifikasi integritas otentik (*non-repudiation*).
3. Secrets lifecycle remediation mengutamakan **Rotasi Kredensial Eksternal** secara instan di atas perbaikan histori internal.
4. Remediasi DAG historis wajib menggunakan tools berstandar modern seperti `git-filter-repo`, ditinggalkan sepenuhnya metode usang `git filter-branch`.
5. Tata kelola modern GitHub berbasis **Rulesets** memungkinkan penegakan kepatuhan berskala multi-repositori (misal: *Mandatory Signed Commits*, *PR Reviews*, dan *Secret Scanning Push Protection*).

---

## SEKSI 17 — GLOSARIUM

* **Attestation:** Bukti komputasional/kriptografis bahwa sebuah artefak atau commit dibuat oleh entitas tertentu yang terverifikasi.
* **Commit Signing:** Proses enkripsi digest commit metadata menggunakan kunci asimetris (*private key*) milik kontributor.
* **DAG (Directed Acyclic Graph):** Struktur data matematika dasar Git di mana commit direpresentasikan sebagai node yang menunjuk ke commit sebelumnya (*ancestor*) secara searah tanpa siklus.
* **Fine-Grained PAT:** Personal Access Token GitHub yang menerapkan prinsip *least-privilege*, dengan restriksi scope per level repositori dan waktu kedaluwarsa ketat.
* **Gitleaks:** Tool static code analysis open-source yang dirancang spesifik untuk mendeteksi rahasia dan kunci API yang belum atau sudah ter-commit di repositori Git.
* **Non-repudiation:** Jaminan bahwa pembuat aksi (misal: commit code) tidak dapat menyangkal keaslian pembuatannya karena terikat oleh private key kriptografis miliknya.
* **Push Protection:** Fitur keamanan Git hosting yang secara proaktif menganalisis commit saat proses *pre-receive* dan menolak push jika terdeteksi secrets terdefinisi.
* **Repository Rulesets:** Fitur tata kelola GitHub tingkat lanjut pengganti branch protection rules konvensional yang memungkinkan konfigurasi aturan kontrol cabang secara modular, deklaratif, dan hierarkis.
* **Shannon Entropy:** Formula matematika probabilitas yang digunakan untuk mendeteksi tingkat keacakan string data; digunakan algoritma sekuriti untuk menemukan token rahasia yang acak.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Setup Sandbox:** Pastikan mahasiswa tidak mengeksekusi latihan remedi (`git-filter-repo`) di repositori production organisasi. Berikan repositori tiruan (*dummy mock repo*) khusus untuk latihan destruktif.
* **Penekanan Mental Model:** Siswa kerap berasumsi bahwa menjalankan `git filter-repo` otomatis memperbaiki repositori teman timnya. Tekankan bahwa histori rewrite menghasilkan *divergent DAG*, sehingga seluruh collaborator harus melakukan re-clone atau re-base dari commit yang telah dibersihkan.
* **Kendala Kompatibilitas:** Windows environment sering mengalami masalah execution policy dengan file script hooks. Pastikan mahasiswa menggunakan Git Bash atau WSL2 saat melakukan pengujian tools CLI berbasis Python dan shell scripts.

---

## SEKSI 19 — CHANGELOG & VERSI

* **v1.0.0 (Mei 2024):**
  * Rilis inisial kurikulum arsitektur enterprise.
  * Standarisasi migrasi dari Branch Protection ke GitHub Rulesets API.
  * Transisi kurikulum commit signing dari sistem GPG murni ke SSH-based signing.
  * Penggantian rekomendasi BFG/`git-filter-branch` dengan `git-filter-repo`.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** Bab 08 Modul 02 — *Advanced Merge Conflict Resolution Strategies & Rebase Workflows*
* **Modul Saat Ini:** Bab 09 Modul 01 — *Repository Security, Compliance, & Secrets Management*
* **Modul Berikutnya:** Bab 09 Modul 02 — *Enterprise Access Controls, SAML SSO, & Fine-Grained Permissions*