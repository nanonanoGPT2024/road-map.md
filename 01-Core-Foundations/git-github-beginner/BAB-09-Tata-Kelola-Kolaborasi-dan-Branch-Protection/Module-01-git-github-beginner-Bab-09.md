## SEKSI 01 — IDENTITAS MODUL

* **Jalur Pembelajaran**: Git & GitHub Fundamentals
* **Kategori**: `01-Core-Foundations`
* **Bab 09**: Tata Kelola Kolaborasi & Keamanan Repositori
* **Modul**: `01`
* **Slug Modul**: `09-01-tata-kelola-kolaborasi-keamanan-repositori`
* **Tingkat Kesulitan**: Beginner to Intermediate
* **Estimasi Waktu Penyelesaian**: 90 Menit
* **Prasyarat**: 
  * Memahami konsep percabangan (*branching*) dan penggabungan (*merging*) Git.
  * Terbiasa membuat *Pull Request* (PR) di GitHub.
  * Mengetahui dasar-dasar CLI Git (`git commit`, `git push`, `git rebase`, `git log`).
  * Memiliki akun GitHub aktif dan Git terpasang di sistem operasi lokal.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Mengimplementasikan GitHub Branch Protection Rules / Repository Rulesets** untuk mencegah manipulasi langsung pada cabang produksi (`main`/`master`) dan memaksakan siklus hidup validasi kode yang ketat.
2. **Menulis dan Mengonfigurasi Berkas `CODEOWNERS`** secara granular berdasarkan direktori, format file, dan sub-sistem guna memastikan tinjauan kode (*code review*) otomatis diarahkan kepada pemangku kepentingan yang tepat.
3. **Mengonfigurasi dan Mengotomasi Penandatanganan Komit (*Commit Signing*) Menggunakan GPG/SSH** untuk memvalidasi integritas kriptografis serta autentisitas identitas pengembang (*verified badge*).
4. **Mendeteksi, Mencegah, dan Memitigasi Kebocoran Kredensial (*Secret Leakage*)** menggunakan pola `.gitignore`, *pre-commit hooks*, serta strategi sanitasi riwayat Git mendalam menggunakan perangkat modern seperti `git-filter-repo`.
5. **Menerapkan Prinsip Hak Akses Terkecil (*Principle of Least Privilege - PoLP*)** pada level kolaborator repositori dan tim organisasi GitHub.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
                  TATA KELOLA & KEAMANAN REPOSITORI
                                  │
         ┌────────────────────────┼────────────────────────┐
         │                        │                        │
         ▼                        ▼                        ▼
 1. INTEGRITAS CABANG     2. TANGGUNG JAWAB KODE   3. KEAMANAN & IDENTITAS
 (Branch Governance)         (Code Ownership)        (Identity & Secrets)
         │                        │                        │
 ┌───────┴───────┐        ┌───────┴───────┐        ┌───────┴───────┐
 │               │        │               │        │               │
 ▼               ▼        ▼               ▼        ▼               ▼
Branch        Rulesets  CODEOWNERS   Reviewer    Commit         Secret
Protection    (Modern)  Syntax       Routing     Signing        Sanitization
(PR Gates)    (Bypass)                           (GPG/SSH)      (Pre-commit)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

1. **Mitigasi Serangan *Supply Chain* & *Blast Radius***: Akses tak terbatas ke cabang utama membuka pintu masuk bagi kode berbahaya, regresi fatal, atau injeksi dependensi berbahaya langsung ke *pipeline* deployment.
2. **Kepatuhan Audit & Regulasi Industri**: Kerangka kerja keamanan global seperti SOC 2 Type II, ISO/IEC 27001, dan PCI-DSS mewajibkan pemisahan tugas (*segregation of duties*). Kode tidak boleh masuk ke produksi tanpa ada tinjauan independen minimal dari satu pihak yang berkualifikasi.
3. **Pemberantasan *Impersonation***: Alamat email dalam metadata Git dapat dimanipulasi dengan mudah via `git config user.email`. Tanpa penandatanganan kriptografis (GPG/SSH), penyerang dapat memalsukan komit seolah-olah ditulis oleh *maintainer* atau CTO Anda.
4. **Pencegahan Kebocoran Kredensial Finansial & Infrastruktur**: *Token*, API *keys*, dan *private keys* yang terdorong (*pushed*) ke repositori publik dapat disusupi bot dalam hitungan detik, mengakibatkan insiden keamanan bernilai jutaan dolar.

---

## SEKSI 05 — APA ITU (WHAT)

Tata kelola kolaborasi dan keamanan repositori adalah sekumpulan kebijakan teknis, mekanisme proteksi kriptografis, dan konfigurasi deklaratif yang dirancang untuk menjaga ketersediaan, integritas, dan kerahasiaan basis kode (*codebase*). Komponen utamanya mencakup:

* **Branch Protection Rules / GitHub Rulesets**: Mekanisme pembatasan di tingkat server yang mencegah tindakan destruktif seperti *force-push* (`git push --force`), penghapusan cabang target, penggabungan cabang tanpa peninjauan lulus (*approved review*), atau penggabungan sebelum status CI (*Continuous Integration*) bernilai hijau (*passing*).
* **GitHub Rulesets (Generasi Baru)**: Evolusi dari *branch protection rules* yang memungkinkan aturan diterapkan lintas repositori secara terpusat, mendukung evaluasi bersyarat, dan memiliki fitur *evaluation mode* untuk menguji dampak aturan tanpa memblokir alur kerja.
* **CODEOWNERS**: Berkas deklaratif yang ditempatkan di root repositori, `.github/`, atau `docs/`, yang secara otomatis memetakan jalur direktori atau ekstensi file ke tim atau individu spesifik sebagai peninjau wajib saat *Pull Request* dibuat.
* **Commit Signature Verification (GPG/SSH)**: Pemanfaatan kriptografi asimetris untuk menandatangani *commit object* Git secara lokal. GitHub memverifikasi tanda tangan tersebut dengan *public key* yang terdaftar, memberikan badge hijau **Verified**.
* **Secret Hygiene**: Protokol untuk mencegah masuknya teks sensitif (sandi, API token, sertifikat) ke dalam basis data objek Git menggunakan proteksi *pre-commit* dan pembersihan riwayat (*history rewrites*).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Siklus Validasi Branch Protection / Rulesets
Saat seorang pengembang menjalankan perintah `git push origin main`, alur validasi berikut dieksekusi di server GitHub sebelum referensi cabang diperbarui:

1. **Evaluasi Hak Akses**: Apakah pengguna memiliki izin *bypass*? Jika tidak, lanjutkan evaluasi aturan.
2. **Pengecekan Tipe Push**: Apakah push berupa *direct commit*? Jika *Require Pull Request* aktif, push ditolak secara instan dengan kode error HTTP 403 atau pesan penolakan Git *pre-receive hook*.
3. **Pengecekan Status Checks**: Jika melalui PR, apakah status CI (misalnya GitHub Actions atau SonarQube) telah lulus?
4. **Pengecekan Tinjauan Kode**: Apakah jumlah *approvals* memenuhi ambang batas minimum dan mencakup persetujuan dari anggota `CODEOWNERS`?

### 2. Evaluasi Aturan `CODEOWNERS`
Algoritma parsing GitHub untuk berkas `CODEOWNERS` mengikuti aturan presedensi mirip dengan `.gitignore`:
* Berkas dibaca dari baris pertama ke baris terakhir.
* Aturan yang terletak **paling bawah** memiliki prioritas tertinggi (*last matching pattern wins*).
* Sintaks mendukung *wildcard* (`*`), *double asterisk* (`**`) untuk pencocokan direktori rekursif, dan pemetaan ke akun `@username` atau tim `@org/team-name`.

### 3. Arsitektur Kriptografi Penandatanganan Komit
* **Kunci Privat (Private Key)**: Disimpan aman di mesin lokal pengembang (dijaga oleh *passphrase*).
* **Proses Komit**: Saat membuat komit dengan flag `-S`, Git mengambil *hash* dari metadata komit (pohon komit, komit induk, pembuat, stempel waktu, dan pesan), membuat intisari (*digest*), menandatanganinya dengan kunci privat, lalu menyematkan blok signature ASCII-armored ke dalam header komit.
* **Verifikasi Server**: GitHub membaca tanda tangan dari header objek komit, mencocokkannya dengan *Public Key* pengembang yang tersimpan di profil pengguna GitHub, memverifikasi tanda tangan matematis, dan menandai komit sebagai **Verified**.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Diagram 1: Gerbang Peninjauan dan Proteksi Cabang (PR Enforcement Pipeline)

```text
Pengembang (Lokal)       GitHub Server (Remote)             Reviewer / CI
     │                              │                             │
     │ 1. git push origin feature   │                             │
     ├─────────────────────────────>│                             │
     │                              │                             │
     │ 2. Buat Pull Request         │                             │
     ├─────────────────────────────>│ 3. Evaluasi CODEOWNERS      │
     │                              ├────────────────────────────>│
     │                              │    (Notifikasi Peninjau)    │
     │                              │                             │
     │                              │ 4. Jalankan Status Checks   │
     │                              ├────────────────────────────>│ (CI Pipeline)
     │                              │<────────────────────────────┤
     │                              │    (Status: PASSED)         │
     │                              │                             │
     │                              │ 5. Tinjau & Approve         │
     │                              │<────────────────────────────┤
     │                              │                             │
     │ 6. Klik 'Merge' (PR)         │                             │
     ├─────────────────────────────>│ 7. Evaluasi Ruleset:        │
     │                              │    - Approvals Valid? [YES] │
     │                              │    - CI Passed?       [YES] │
     │                              │    - Up-to-date?      [YES] │
     │                              │    - Commits Signed?  [YES] │
     │                              │                             │
     │                              │ 8. Merge ke Cabang 'main'   │
     │<─────────────────────────────┤                             │
     │       (PR Closed/Merged)     │                             │
```

### Diagram 2: Skema Verifikasi Tanda Tangan Kriptografis Komit

```text
[ Komputasi Pengembang Lokal ]                     [ GitHub Server ]
┌───────────────────────────────┐                  ┌───────────────────────────────┐
│ Metadata Komit:               │                  │ 1. Terima Objek Komit         │
│ - Tree SHA                    │                  │    - Ekstrak Signature        │
│ - Parent SHA                  │                  │    - Ambil Public Key Akun    │
│ - Author, Committer, Message  │                  │                               │
└───────────────┬───────────────┘                  └───────────────┬───────────────┘
                │                                                  │
                ▼                                                  ▼
     ┌─────────────────────┐                            ┌─────────────────────┐
     │ SHA-256 Hash Digest │                            │ Eksekusi Verifikasi │
     └──────────┬──────────┘                            │ Kriptografis        │
                │                                       └──────────┬──────────┘
                ▼ (Enkripsi dengan Private Key)                    │
     ┌─────────────────────┐                            ┌──────────┴──────────┐
     │ GPG / SSH Signature │                            │ Cocok?              │
     └──────────┬──────────┘                            ├──────────┬──────────┤
                │                                       ▼ [YA]     ▼ [TIDAK]
                ▼                                   [VERIFIED]  [UNVERIFIED]
     ┌─────────────────────┐
     │ Disematkan ke Header│
     │ Objek Komit Git     │
     └─────────────────────┘
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah implementasi dasar pembatasan proteksi, berkas kepemilikan kode, dan penandatanganan komit.

### 1. Berkas `.github/CODEOWNERS` Sederhana

```ini
# Aturan default: Setiap perubahan yang tidak spesifik membutuhkan persetujuan tim lead
* @octocat-team-lead

# Perubahan pada dokumentasi hanya membutuhkan persetujuan tim technical writer
/docs/ @octocat-tech-writers

# Perubahan konfigurasi CI/CD sensitif harus disetujui Security Engineer
.github/workflows/ @octocat-secops
```

### 2. Konfigurasi Git Commit Signing dengan SSH (Alternatif Modern Pengganti GPG)

```bash
# 1. Generate SSH key khusus penandatanganan (jika belum ada)
ssh-keygen -t ed25519 -C "developer@perusahaan.com" -f ~/.ssh/id_ed25519_signing -N ""

# 2. Konfigurasi Git untuk menggunakan SSH sebagai format penandatanganan
git config --global gpg.format ssh

# 3. Arahkan Git ke public key yang digunakan untuk tanda tangan
git config --global user.signingkey ~/.ssh/id_ed25519_signing.pub

# 4. Aktifkan penandatanganan otomatis untuk semua komit
git config --global commit.gpgsign true

# 5. Salin public key untuk didaftarkan ke GitHub (Profile -> SSH Keys -> New SSH Key -> Key type: Signing Key)
cat ~/.ssh/id_ed25519_signing.pub
```

### 3. Membuat Komit dan Memeriksa Status Tanda Tangan

```bash
# Buat berkas baru dan lakukan komit
echo "print('Production Safe')" > app.py
git add app.py
git commit -m "feat: inisialisasi aplikasi aman"

# Verifikasi tanda tangan lokal
git log --show-signature -n 1
```

*Output yang Diharapkan:*
```text
commit 4b82c1a8d14db0b82f0c72e2d93e2b34a66a7ecf (HEAD -> main)
Good "ssh" signature for developer@perusahaan.com with ED25519 key SHA256:7bXN...
Author: John Doe <developer@perusahaan.com>
Date:   Mon May 20 10:00:00 2024 +0700

    feat: inisialisasi aplikasi aman
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus: Arsitektur monorepo skala berkembang yang memiliki modul `core-banking`, infrastruktur `terraform/`, dan antarmuka `frontend/`. Repositori membutuhkan tata kelola ketat sesuai regulasi perbankan.

### 1. Struktur Direktori Repositori

```text
enterprise-repo/
├── .github/
│   ├── CODEOWNERS
│   └── workflows/
│       └── audit-check.yml
├── core-banking/
│   └── ledger.go
├── infrastructure/
│   └── main.tf
├── frontend/
│   └── package.json
└── .gitignore
```

### 2. Definisi Tingkat Lanjut `.github/CODEOWNERS`

```ini
###############################################################################
# METADATA TATA KELOLA KEPEMILIKAN KODE MONOREPO
# Aturan: Baris terbawah memiliki prioritas tertinggi.
###############################################################################

# 1. Fallback Global: Seluruh file secara bawaan dimiliki Tim Arsitek
* @enterprise-org/system-architects

# 2. Modul Frontend: Akses delegasi ke Tim Web Engineers
/frontend/ @enterprise-org/frontend-leads

# 3. Infrastruktur & Cloud: Wajib ditinjau oleh tim DevOps dan SRE
/infrastructure/ @enterprise-org/devops-team @enterprise-org/sre-team

# 4. Modul Finansial Kritis: Wajib ditinjau oleh Core Banking Guild & Lead Auditor
/core-banking/ @enterprise-org/core-banking-guild @compliance-auditor

# 5. Pipeline CI/CD dan Berkas Keamanan: Hak istimewa tim SecOps
/.github/workflows/ @enterprise-org/security-operations
/.github/CODEOWNERS @enterprise-org/security-operations
```

### 3. Otomasi GitHub Ruleset via GitHub CLI (`gh`)

Alih-alih mengklik GUI web yang rawan inkonsistensi manusia, buat aturan *Ruleset* deklaratif menggunakan format JSON:

Simpan file sebagai `ruleset-production.json`:
```json
{
  "name": "Production Strict Protection",
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
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [
          { "context": "security-static-analysis" },
          { "context": "integration-tests" }
        ]
      }
    }
  ],
  "bypass_actors": []
}
```

Terapkan aturan menggunakan GitHub CLI:
```bash
gh api --method POST \
  -H "Accept: application/vnd.github+json" \
  /repos/enterprise-org/enterprise-repo/rulesets \
  --input ruleset-production.json
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Aspek | Kebijakan Agresif / Sangat Ketat | Kebijakan Longgar / Permisif | Pendekatan Berimbang (Direkomendasikan) |
| :--- | :--- | :--- | :--- |
| **Approval Threshold** | Minimal 3 *Approvals* termasuk CODEOWNERS & Admin | Tanpa *Approval* (Boleh langsung push ke `main`) | 1–2 *Approvals*, wajib persetujuan CODEOWNERS |
| **Commit Signing** | Menolak semua komit tanpa GPG/SSH Signature | Mengizinkan komit unsigned | Wajibkan tanda tangan untuk cabang rilis (`main`, `release/*`) |
| **Linear History** | Wajib *Squash* atau *Rebase* murni, tanpa *Merge Commit* | Mengizinkan sembarang tipe penggabungan (*merge commit*, fast-forward) | Wajibkan *Squash Merge* atau *Rebase Merge* agar riwayat linear mudah diaudit |
| **Dismiss Stale Reviews** | Aktif: Push komit baru otomatis membatalkan *Approval* | Nonaktif: *Approval* tetap sah meski ada perubahan baru | Aktif untuk file produksi, memitigasi penyelundupan kode setelah peninjauan |
| **Dampak Kecepatan Tim** | *Throughput* PR melambat; potensi kemacetan (*review bottleneck*) | Kecepatan rilis instan, namun risiko *downtime* produksi masif | Menggunakan CODEOWNERS berbasis tim (bukan perorangan) untuk redundansi peninjau |

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan GitHub Teams pada CODEOWNERS**: Jangan pernah memetakan individual username (`@johndoe`) pada `CODEOWNERS`. Jika individu tersebut cuti atau keluar dari perusahaan, PR akan terkunci. Gunakan struktur tim organisasi GitHub (`@org/backend-team`).
2. **Aktifkan "Dismiss stale pull request approvals when new commits are pushed"**: Fitur ini memastikan bahwa setiap baris kode baru yang ditambahkan setelah peninjauan wajib dievaluasi ulang oleh reviewer.
3. **Konfigurasi Proteksi Rahasia (*Secret Scanning*) dan *Push Protection***: Aktifkan fitur bawaan GitHub *Push Protection* pada repositori organisasi. Fitur ini secara langsung menganalisis dan menolak eksekusi `git push` yang terdeteksi membawa string API Token terdaftar (misalnya AWS Keys, Stripe Secret Keys).
4. **Isolasi Berkas Sensitif dengan Pre-Commit Hooks**: Terapkan alat otomasi linting keamanan lokal seperti `gitleaks` atau `trufflehog` menggunakan kerangka kerja `pre-commit`:
   ```yaml
   # .pre-commit-config.yaml
   repos:
     - repo: https://github.com/gitleaks/gitleaks
       rev: v8.18.2
       hooks:
         - id: gitleaks
   ```
5. **Terapkan Prinsip Hak Akses Terkecil (PoLP)**: Kolaborator eksternal hanya boleh diberi peran `Triage` atau `Read`. Hak `Write` dibatasi untuk anggota tim aktif, sementara hak `Admin` hanya dipegang oleh *Repository Administrators* atau tim *SecOps*.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Menambahkan Rahasia ke `.gitignore` SETELAH Komit Terjadi
*Kesalahan*: Mengira bahwa menambahkan file `.env` ke `.gitignore` akan menghapus kredensial yang sebelumnya sudah terlanjur di-komit.
*Dampak*: Objek Git masa lalu tetap merekam file tersebut dalam database commit tree; siapa pun dapat mengaksesnya via `git checkout` atau melihat riwayat komit lama.
*Solusi*: Gunakan alat sanitasi historis mendalam seperti `git-filter-repo` (bukan sekadar `git rm`):
```bash
# Jalankan sanitasi riwayat secara permanen
pip install git-filter-repo
git filter-repo --path .env --invert-paths --force
```

### 2. Syntax Conflict pada Urutan `CODEOWNERS`
*Kesalahan*: Menempatkan aturan global di bagian paling bawah.
```ini
/security/ @secops-team
* @everyone  # <--- INI AKAN MENIMPA SEMUA ATURAN DI ATASNYA!
```
*Solusi*: Selalu letakkan aturan umum di atas dan aturan spesifik di bawah:
```ini
* @everyone
/security/ @secops-team # Benar: Aturan ini memenangkan presedensi
```

### 3. Melakukan Bypass Ruleset Tanpa Justifikasi
*Kesalahan*: Memberikan izin *bypass* Branch Protection kepada semua akun bertipe *Organization Admin* demi alasan kenyamanan harian.
*Dampak*: Admin yang tidak sengaja menjalankan `git push origin main --force` dari terminal lokal dapat menimpa basis data cabang utama dan menghilangkan riwayat kerja tim.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Latihan: Mengamankan Repositori Kolaboratif

Lakukan skenario pengamanan repositori lokal dan GitHub dari awal hingga akhir menggunakan perintah terminal:

```bash
# =============================================================================
# TUGAS 1: Buat Repositori Lokal & Simulasi Kebocoran Kredensial
# =============================================================================

# 1. Inisialisasi direktori repositori pengujian
mkdir repo-keamanan-praktis && cd repo-keamanan-praktis
git init -b main

# 2. Konfigurasi identitas lokal Anda
git config user.name "Security Learner"
git config user.email "learner@cybersec.local"

# 3. Buat file sensitif secara tidak sengaja
echo "DATABASE_PASSWORD=SuperSecretPassword123!" > config.env
git add config.env
git commit -m "feat: tambahkan konfigurasi database lokal"

# =============================================================================
# TUGAS 2: Hapus Riwayat Rahasia Menggunakan git-filter-repo
# =============================================================================

# 1. Pastikan git-filter-repo telah terpasang di sistem operasi Anda
# (Contoh instalasi via pip: pip install git-filter-repo)

# 2. Jalankan pembersihan riwayat Git terhadap file config.env
git filter-repo --path config.env --invert-paths

# 3. Verifikasi bahwa riwayat komit telah dibersihkan secara mutlak
git log --oneline
# (Perhatikan bahwa commit SHA telah berubah dan riwayat config.env lenyap)

# =============================================================================
# TUGAS 3: Buat Berkas Tata Kelola CODEOWNERS
# =============================================================================

mkdir -p .github
cat << 'EOF' > .github/CODEOWNERS
# Aturan Kepemilikan Kode Default
* @security-learner

# Modul Inti
/src/ @security-learner
EOF

# Tambahkan aturan .gitignore untuk mencegah kebocoran berulang
cat << 'EOF' > .gitignore
*.env
.DS_Store
node_modules/
vendor/
EOF

git add .github/ .gitignore
git commit -m "chore: tetapkan konfigurasi tata kelola CODEOWNERS dan gitignore"

# =============================================================================
# TUGAS 4: Setup Penandatanganan Komit Berbasis Kunci SSH
# =============================================================================

# 1. Buat pasangan kunci penandatanganan SSH baru
ssh-keygen -t ed25519 -C "learner@cybersec.local" -f ~/.ssh/git_test_signing -N ""

# 2. Daftarkan kunci SSH ke konfigurasi repositori lokal
git config gpg.format ssh
git config user.signingkey ~/.ssh/git_test_signing.pub
git config commit.gpgsign true

# 3. Lakukan pengujian komit bertanda tangan
echo "console.log('Secure Application Running');" > src_app.js
git add src_app.js
git commit -m "feat: inisialisasi aplikasi dengan komit terverifikasi"

# 4. Validasi keabsahan tanda tangan kriptografis komit terakhir
git log --show-signature -n 1
```

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan-pertanyaan berikut untuk mengevaluasi pemahaman teknis Anda:

1. **Bagaimana algoritma GitHub membaca berkas `.github/CODEOWNERS` ketika ada dua aturan yang cocok (*matching patterns*) untuk sebuah berkas?**
   * A. Aturan yang paling atas yang diprioritaskan.
   * B. GitHub akan melempar peringatan sintaks dan mengabaikan kedua aturan.
   * C. Aturan yang posisinya paling bawah (*last-matching rule*) yang diprioritaskan.
   * D. Aturan yang memiliki jumlah reviewer paling banyak yang dieksekusi.

2. **Seorang pengembang secara tidak sengaja melakukan `git push` file kredensial AWS ke repositori publik. Langkah mitigasi pertama dan terpenting yang wajib segera dilakukan adalah:**
   * A. Menambahkan file tersebut ke dalam `.gitignore` lalu push ulang.
   * B. Mengubah commit message lama menggunakan `git commit --amend`.
   * C. Segera melakukan rotasi (*revoke/rotate*) terhadap API Key AWS tersebut di dashboard AWS IAM.
   * D. Menghapus repositori GitHub dan membuatnya kembali dari awal.

3. **Manakah alasan teknis yang paling tepat mengapa penandatanganan komit (Commit Signing) menggunakan GPG atau SSH diperlukan dalam tata kelola keamanan modern?**
   * A. Komit yang ditandatangani akan mengenkripsi kode sumber sehingga tidak bisa dibaca oleh pihak luar tanpa izin.
   * B. Mencegah pemalsuan identitas (*identity spoofing*) karena Git secara bawaan memperbolehkan siapa pun menulis nama dan email siapa pun di metadata komit.
   * C. Mempercepat proses kompilasi kode pada pipeline Continuous Integration.
   * D. Menjamin bahwa komit tersebut bebas dari kerentanan keamanan atau celah *zero-day*.

4. **Apa implikasi dari mengaktifkan opsi *"Require linear history"* pada GitHub Branch Protection?**
   * A. Tidak ada cabang baru yang boleh dibuat di repositori selain cabang `main`.
   * B. Riwayat cabang tidak boleh mengandung *merge commits*; penggabungan harus dilakukan melalui metode *Squash and Merge* atau *Rebase and Merge*.
   * C. Pengembang dilarang menggunakan perintah `git rebase` pada cabang lokal mereka.
   * D. Setiap komit wajib memiliki tanda tangan SSH/GPG.

5. **Di mana saja lokasi yang valid secara standar di dalam repositori untuk meletakkan berkas `CODEOWNERS` agar dapat dideteksi secara otomatis oleh GitHub?**
   * A. Hanya di direktori `.github/`.
   * B. Direktori *root* repositori, direktori `.github/`, atau direktori `docs/`.
   * C. Direktori `.git/hooks/` atau `.github/policies/`.
   * D. Direktori root repositori atau di dalam folder `src/`.

---

### Kunci Jawaban & Rasional Penilaian:
* **1: C** — Berkas `CODEOWNERS` menggunakan mekanisme presedensi berurutan dari atas ke bawah (*bottom-up wins*), identik dengan mekanisme parsing berkas `.gitignore`.
* **2: C** — Setelah rahasia terekspos ke internet publik, rahasia tersebut harus dianggap sudah disusupi (*compromised*). Menghapus riwayat Git adalah langkah sekunder; langkah primer mutlak adalah menonaktifkan kredensial di sisi penyedia layanan.
* **3: B** — Git tidak memvalidasi kepemilikan string `user.email`. Penandatanganan komit asimetris membuktikan bahwa pemegang *private key* yang sah adalah entitas sebenarnya yang menghasilkan objek komit tersebut.
* **4: B** — Opsi *linear history* mencegah masuknya *merge commits* yang membuat visualisasi pohon Git menjadi bercabang-cabang dan menyulitkan pelacakan titik balik audit (*bisecting*).
* **5: B** — Dokumentasi resmi GitHub menetapkan tiga lokasi prioritas: root repositori (`./CODEOWNERS`), direktori GitHub (`.github/CODEOWNERS`), dan direktori dokumentasi (`docs/CODEOWNERS`).

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1. **GitHub Official Documentation**:
   * *Managing a branch protection rule*: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule
   * *About code owners*: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners
   * *Managing rulesets for a repository*: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets
2. **Git Documentation & Tooling**:
   * *Pro Git Book by Scott Chacon and Ben Straub - Chapter 7.4: Git Tools - Signing Your Work*: https://git-scm.com/book/en/v2/Git-Tools-Signing-Your-Work
   * *git-filter-repo repository & documentation*: https://github.com/newren/git-filter-repo
3. **Standar Keamanan Industri**:
   * *OWASP Source Code Analysis Guidelines*: https://owasp.org/www-community/Source_Code_Analysis_Tools
   * *NIST Special Publication 800-218: Secure Software Development Framework (SSDF)*.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **Branch Protection & Rulesets** bertindak sebagai perisai server repositori yang memblokir penulisan langsung ke cabang stabil, mewajibkan peninjauan kode (*peer review*), serta mensyaratkan kelulusan pengujian CI otomatis sebelum penggabungan dapat diproses.
2. **Berkas `CODEOWNERS`** mendesentralisasikan akuntabilitas kode ke tim teknis spesifik secara deklaratif berdasarkan path atau ekstensi file, menjamin kode tidak masuk ke produksi tanpa sepengetahuan pemilik domain teknisnya.
3. **Commit Signing (GPG/SSH)** memecahkan kelemahan mendasar Git terkait pemalsuan identitas (*author spoofing*), membubuhkan segel digital kriptografis yang diverifikasi langsung oleh platform remote.
4. **Higienitas Kredensial (Secret Hygiene)** membutuhkan pertahanan berlapis: `.gitignore` untuk pencegahan awal, *pre-commit hooks* untuk penapisan lokal, *Push Protection* di level remote, serta `git-filter-repo` jika perlu menghapus riwayat bocor secara menyeluruh.
5. Menjaga keseimbangan antara **keamanan ketat** dan **kecepatan tim** (*developer velocity*) adalah seni tata kelola: gunakan tim dinamis alih-alih individu, otomatisasi gerbang validasi, dan terapkan *least privilege access*.

---

## SEKSI 17 — GLOSARIUM

* **RBAC (Role-Based Access Control)**: Mekanisme kontrol akses yang membatasi hak operasi sistem (baca, tulis, kelola) berdasarkan peran kerja pengguna dalam organisasi (misalnya: *Read, Triage, Write, Maintain, Admin*).
* **Branch Ruleset**: Generasi modern dari kontrol integritas cabang di GitHub yang memungkinkan penegakan aturan secara multi-target, evaluasi status dinamis, dan kontrol bypass granular.
* **CODEOWNERS**: Berkas konfigurasi pemetaan repositori yang mendefinisikan tim atau individu yang bertanggung jawab atas komponen kode tertentu.
* **Commit Signing**: Proses menghasilkan tanda tangan digital pada objek komit Git menggunakan pasangan kunci kriptografi privat-publik (GPG atau SSH) untuk membuktikan integritas dan asal-usul komit.
* **Pre-Receive Hook**: Skrip validasi di sisi server Git yang dieksekusi saat menerima push, digunakan untuk menolak data jika tidak memenuhi kriteria integritas yang ditetapkan.
* **Blast Radius**: Besarnya cakupan atau tingkat kerusakan infrastruktur dan bisnis yang ditimbulkan apabila terjadi satu insiden kegagalan sistem atau kebocoran akses.
* **git-filter-repo**: Utilitas baris perintah resmi yang direkomendasikan komunitas Git untuk menulis ulang riwayat basis data Git secara mendalam dan cepat, menggantikan utilitas lama `git filter-branch`.

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Peringatan & Kendala Umum Pengajaran
* **Kesalahpahaman Mekanisme Git Signed Commits**: Banyak peserta pemula berpikir bahwa penandatanganan komit mengenkripsi kode mereka. Tegaskan secara eksplisit kepada peserta bahwa *commit signing* hanyalah proses **autentikasi dan integritas data**, bukan enkripsi kerahasiaan (*confidentiality*). Objek kode tetap terbuka untuk dibaca oleh pihak yang memiliki hak akses repositori.
* **Masalah Kunci SSH vs. GPG**: Untuk peserta modern, sangat disarankan mengajarkan penandatanganan berbasis **SSH Key** (tersedia sejak Git versi 2.34+). Konfigurasi GPG klasik kerap menimbulkan kendala pada pengaturan antarmuka *pinentry-curses*, *GPG agent*, dan *passphrase prompt* di terminal yang membingungkan bagi pemula.
* **Koreksi Penggunaan `git-filter-repo`**: Berikan peringatan keras bahwa memodifikasi riwayat Git dengan `git-filter-repo` atau perintah pengubah riwayat lainnya akan mengubah seluruh commit SHA secara global. Perintah ini **bersifat destruktif** dan membutuhkan koordinasi penuh (force push) apabila dilakukan pada repositori kolaboratif tim.

### Desain Lingkungan Praktikum (Lab Sandbox)
Sediakan organisasi pengujian (*dummy organization*) di GitHub Enterprise Cloud atau GitHub Free bagi peserta untuk mempraktikkan konfigurasi `CODEOWNERS` dan pengaturan hak akses tim tanpa risiko merusak repositori kerja riil.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0** (Tanggal Rilis: Mei 2024)
  * Rilis awal modul *Tata Kelola Kolaborasi & Keamanan Repositori*.
  * Integrasi kurikulum penuh berbasis 20 seksi standar GEMINI.md.
  * Penambahan implementasi penandatanganan SSH signing key modern sebagai opsi mutakhir selain GPG.
  * Penyusunan contoh deklaratif konfigurasi GitHub Ruleset berbasis API payload JSON.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `08-02-resolving-complex-merge-conflicts` — Mengurai Konflik Penggabungan Kompleks dan Strategi Rebase
* **Modul Saat Ini**: `09-01-tata-kelola-kolaborasi-keamanan-repositori` — Tata Kelola Kolaborasi & Keamanan Repositori
* **Modul Berikutnya**: `09-02-continuous-integration-code-quality-gates` — Otomasi Pipeline CI dan Gerbang Kualitas Kode Repositori (*Code Quality Gates*)