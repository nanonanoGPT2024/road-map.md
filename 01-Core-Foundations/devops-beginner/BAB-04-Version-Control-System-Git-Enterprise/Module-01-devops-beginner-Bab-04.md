## SEKSI 01 — IDENTITAS MODUL

*   **Kode Modul**: `CF-GIT-01`
*   **Nama Modul**: Version Control System Terapan: Git Enterprise
*   **Kategori**: `01-Core-Foundations`
*   **Tingkat Kesulitan**: Beginner to Intermediate
*   **Estimasi Waktu**: 180 Menit
*   **Prasyarat**: Pemahaman dasar Linux CLI, instalasi Git lokal, manipulasi file teks dasar.
*   **Target Peran**: DevOps Engineer, Site Reliability Engineer (SRE), Platform Engineer, Software Engineer.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

1.  **Menganalisis** struktur internal Git (Directed Acyclic Graph / DAG, Object Storage, dan Plumbing Commands) untuk mendiagnosis kerusakan repositori.
2.  **Menerapkan** strategi branching modern (Trunk-Based Development dan GitHub Flow) yang dioptimalkan untuk siklus Continuous Integration / Continuous Delivery (CI/CD).
3.  **Mengimplementasikan** mekanisme integritas dan keamanan enterprise melalui Cryptographic Commit Signing (GPG/SSH) dan Git Hooks berbasis otomasi.
4.  **Mengeksekusi** manipulasi riwayat Git tingkat lanjut menggunakan Interactive Rebase, Cherry-pick, dan Resolusi Konflik berbasis 3-way merge tanpa merusak integritas upstream.
5.  **Merancang** tata kelola repositori skala enterprise, mencakup *Branch Protection Rules*, *CODEOWNERS*, dan standardisasi *Conventional Commits*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
[Enterprise Git Governance]
 ├── Core Mechanics & DAG
 │    ├── Objects: Blob, Tree, Commit, Tag
 │    ├── References: Heads, Remotes, Tags, Symbolic Ref (HEAD)
 │    └── History State: Working Tree, Index (Staging), Commit History
 ├── Branching Architecture
 │    ├── GitFlow (Legacy/Scheduled Release)
 │    ├── Trunk-Based Development (Cloud-Native/CI-CD Optimized)
 │    └── GitHub Flow (PR/Review-Centric)
 ├── Security & Compliance
 │    ├── Cryptographic Signing: GPG vs SSH Keys
 │    ├── Secret Leaks Prevention: Pre-commit Hooks, Gitleaks
 │    └── Repository Governance: Branch Protections & CODEOWNERS
 └── Advanced History Engineering
      ├── Non-destructive: git merge (--no-ff, --ff-only)
      ├── History Rewriting: git rebase -i, squash, amend
      └── Disaster Recovery: git reflog, detached HEAD recovery
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Dalam ekosistem enterprise modern, Git bukan sekadar alat pelacak perubahan kode sumber (source code tracker), melainkan fondasi utama dari paradigma **Everything as Code** (Infrastructure as Code, Policy as Code, dan GitOps). Setiap pipeline otomatisasi CI/CD dipicu oleh *event* Git (push, pull request, tag). 

Jika seorang engineer tidak memahami cara kerja internal Git dan standar enterprise:
1.  **Risiko Integritas Kode**: Terjadi *race condition*, *history pollution*, dan *accidental overwrite* kode produksi akibat ketidakpahaman manipulasi pointer cabang.
2.  **Kebocoran Kredensial**: Repositori menjadi vektor serangan utama ketika kredensial (API keys, private certificates) ter-commit secara permanen ke riwayat Git yang tidak dapat dihapus hanya dengan commit baru.
3.  **Bottleneck Rilis**: Penerapan alur kerja yang salah (misalnya, cabang yang bertahan berminggu-minggu) menyebabkan *merge hell*, menghentikan siklus deployment harian, dan menghambat delivery bisnis.
4.  **Audit & Compliance**: Regulasi kepatuhan seperti SOC2, PCI-DSS, dan ISO 27001 mewajibkan verifikasi non-repudiasi (*unforgeable identity*) atas setiap baris kode yang masuk ke produksi, yang hanya dapat dijamin melalui *signed commits* dan *enforced peer-review workflows*.

---

## SEKSI 05 — APA ITU (WHAT)

**Enterprise Git** adalah penerapan Version Control System Git yang diperluas dengan standardisasi tata kelola (governance), keamanan kriptografis, arsitektur kolaborasi berskala besar, dan integrasi pipeline otomatisasi.

Komponen struktural Enterprise Git meliputi:

*   **Directed Acyclic Graph (DAG)**: Representasi matematis dari commit Git di mana setiap commit menyimpan pointer immutable ke commit induknya (*parent commit*).
*   **Trunk-Based Development (TBD)**: Pola branching di mana semua developer mengintegrasikan perubahan kecil secara berkala langsung ke branch tunggal (`main`), memvalidasinya dengan CI otomatis, dan menghindari *long-lived branches*.
*   **Conventional Commits**: Standar penulisan pesan commit terstruktur (`type(scope): description`) yang memfasilitasi pembuatan changelog otomatis dan penentuan versi otomatis berbasis *Semantic Versioning* (SemVer: `MAJOR.MINOR.PATCH`).
*   **Cryptographic Commit Signing**: Penandatanganan digital commit menggunakan asymmetric cryptography (GPG atau SSH) untuk membuktikan otentisitas dan integritas penulis commit.
*   **Branch Protection & Access Control**: Kebijakan server-side yang mewajibkan status CI berhasil, jumlah *peer-review approvals* minimum, dan linear history sebelum kode dapat digabungkan (*merged*).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Struktur Objek Internal Git
Direktori `.git` menyimpan database *content-addressable storage*. Setiap objek diidentifikasi oleh hash SHA-1 (atau SHA-256 pada Git modern) dari konten beserta header-nya:
*   **Blob**: Menyimpan data biner/teks dari file tanpa metadata (nama file atau permission).
*   **Tree**: Berfungsi seperti direktori; memetakan nama file dan permission ke hash SHA dari Blob atau Tree anak.
*   **Commit**: Menyimpan metadata (author, committer, timestamp, pesan) dan referensi hash Tree root serta hash Parent Commit.
*   **Tag**: Pointer permanen ke commit tertentu, sering kali disertai tanda tangan kriptografis.

### 2. Tiga Area Status Git (Three Tree Architecture)
1.  **Working Tree**: Direktori fisik di filesystem lokal tempat file diedit.
2.  **Index (Staging Area)**: Snapshot biner dalam format file `.git/index` yang merepresentasikan persiapan commit berikutnya.
3.  **Repository (Commit History)**: Basis data objek permanen di dalam `.git/objects`.

### 3. Rebase vs Merge Mechanism
*   **Merge**: Git membuat sebuah *merge commit* baru yang memiliki dua (atau lebih) parent. Ini mempertahankan riwayat kronologis absolut secara non-destruktif, namun menghasilkan riwayat non-linear yang kompleks (topologi spaghetti).
*   **Rebase**: Git mengambil commit-commit dari branch fitur saat ini, mencari *Common Ancestor* dengan branch target, lalu memainkan ulang (*replay*) commit-commit tersebut satu per satu di atas *tip* branch target. Operasi ini **mengubah hash SHA** dari commit karena parent-nya telah berganti, menghasilkan riwayat commit yang sepenuhnya linear.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Git Object Storage Topology
```text
.git/
├── HEAD -> refs/heads/main
├── refs/
│   └── heads/
│       └── main -> 8f3a1b...
└── objects/
    ├── 8f/3a1b... (Commit Object)
    │    ├── Tree: e2c94a...
    │    ├── Parent: 1a4d8c...
    │    ├── Author: DevOps Eng <ops@corp.internal>
    │    └── Message: "feat(auth): add oauth2 validation"
    ├── e2/c94a... (Tree Object)
    │    ├── 100644 blob 4d28e7...  main.go
    │    └── 040000 tree f6b19a...  config/
    └── 4d/28e7... (Blob Object)
         └── Content: "package main\n\nfunc main() {...}"
```

### 2. Perbandingan Topologi: Merge vs Rebase

#### Operasi Git Merge (Non-Fast-Forward / `--no-ff`)
```text
Sebelum:
      A---B---C  [feature]
     /
D---E---F        [main]

Setelah:
      A---B---C  [feature]
     /         \
D---E-----------F---M  [main] (M = Merge Commit dengan Parent C & F)
```

#### Operasi Git Rebase
```text
Sebelum:
      A---B---C  [feature]
     /
D---E---F        [main]

Setelah:
                A'--B'--C' [feature] (Linear replay, hash SHA berubah)
               /
D---E---------F            [main]
```

### 3. Trunk-Based Development Pipeline Integration
```text
[Developer Local]
       │ (Feature Branch: max 1-2 hari kerja)
       ▼
 [Push Branch] ──► [Pull Request Created]
                          │
                          ├─► [Webhook Trigger] ──► [CI Pipeline]
                          │                           ├─ Linting
                          │                           ├─ Unit Test
                          │                           ├─ Secret Scan
                          │                           └─ SAST
                          ├─► [CODEOWNERS Review Required]
                          │
                   [CI: PASS & Approval: OK]
                          │
                          ▼
            [Squash & Merge / Rebase] ──► [Trunk: main]
                                               │
                                               ▼
                                      [CD Pipeline Run]
                                               │
                                               ▼
                                     [Staging / Production]
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah konfigurasi dasar identitas terverifikasi dan pembuatan commit berstandar industri.

### Konfigurasi Identitas dan Signing Key (SSH)
```bash
# 1. Konfigurasi identitas global
git config --global user.name "DevOps Engineer"
git config --global user.email "devops@enterprise.internal"

# 2. Buat SSH Signing Key khusus (ed25519)
ssh-keygen -t ed25519 -C "devops@enterprise.internal" -f ~/.ssh/id_git_signing -N ""

# 3. Konfigurasi Git untuk menandatangani commit menggunakan format SSH
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_git_signing.pub
git config --global commit.gpgsign true
git config --global tag.gpgSign true
```

### Membuat Commit yang Ditandatangani
```bash
# Inisialisasi repo demonstrasi
mkdir git-enterprise-core && cd git-enterprise-core
git init

# Buat file awal
echo "runtime: nodejs20" > runtime.yaml
git add runtime.yaml

# Commit dengan Conventional Commit syntax dan tanda tangan digital otomatis
git commit -m "chore(infra): initialize runtime configuration"

# Verifikasi tanda tangan commit
git log --show-signature -n 1
```

*Output Verifikasi:*
```text
commit 3f5d2b78a9c... (HEAD -> main)
Good "ssh" signature for devops@enterprise.internal with ED25519 key SHA256:...
Author: DevOps Engineer <devops@enterprise.internal>
Date:   Mon May 20 10:00:00 2024 +0700

    chore(infra): initialize runtime configuration
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Skenario nyata di enterprise: Mengembangkan modul otentikasi menggunakan cabang pendek (*short-lived branch*), memadatkan (*squash*) riwayat commit yang berantakan via interactive rebase, menyinkronkan dengan trunk yang terus bergerak maju, lalu menggabungkannya tanpa merusak struktur trunk.

```bash
# 1. Pastikan trunk (main) selalu mutakhir
git checkout main
git pull --rebase origin main

# 2. Buat short-lived branch untuk perbaikan issue AUTH-402
git checkout -b feature/AUTH-402-jwt-validation

# 3. Lakukan beberapa siklus kerja (commit mikro/lokal)
echo "package auth" > auth.go
git add auth.go
git commit -m "wip: start auth logic"

echo "func ValidateToken() bool { return true }" >> auth.go
git add auth.go
git commit -m "fix typo and add validator"

# 4. Asumsikan cabang 'main' di server pusat telah bergerak maju karena engineer lain:
#    Simulasikan perubahan di main
git checkout main
echo "v1.2.0" > version.txt
git add version.txt
git commit -m "chore(release): bump version to 1.2.0"
git checkout feature/AUTH-402-jwt-validation

# 5. Lakukan Interactive Rebase untuk merapikan 2 commit 'wip' menjadi 1 commit standar
#    Targetkan rebase ke base branch (main)
git rebase -i main
```

Saat editor Git interaktif terbuka, ubah baris perintah:
```text
pick 1a2b3c4 wip: start auth logic
squash 5d6e7f8 fix typo and add validator

# Rebase 1a2b3c4..5d6e7f8 onto 9z8y7x6 (main)
```

Simpan dan keluar. Git akan meminta pesan commit gabungan baru. Tulis pesan terstandardisasi:
```text
feat(auth): implement JWT token validation engine

- Add base package for authentication
- Implement ValidateToken parser with signature checking
Refs: AUTH-402
```

Verifikasi struktur graph terminal:
```bash
git log --graph --oneline --decorate -n 5
```

*Output:*
```text
* 7f9a1b2 (HEAD -> feature/AUTH-402-jwt-validation) feat(auth): implement JWT token validation engine
* 9z8y7x6 (main) chore(release): bump version to 1.2.0
...
```

Perubahan kini berada tepat di atas `main`, siap didorong (*push*) ke remote untuk pembuatan Pull Request tanpa memicu konflik divergen:
```bash
git push origin feature/AUTH-402-jwt-validation
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Arsitektural | Opsi A | Opsi B | Trade-off & Implikasi Analitis |
| :--- | :--- | :--- | :--- |
| **Branching Model** | **Trunk-Based Development** | **GitFlow** | **Trunk-Based**: Memerlukan test automation yang sangat matang dan kultur *feature flagging*. Menghilangkan bottleneck integrasi. Sangat cepat.<br>**GitFlow**: Aman untuk rilis berbasis jadwal (software packaged/on-premise), namun lambat, rawan divergensi, dan menghambat feedback loop CI/CD. |
| **Integrasi Branch** | **Linear History (Rebase / Squash-Merge)** | **Preserved Graph (Merge Commit `--no-ff`)** | **Rebase/Squash**: Log audit sangat bersih, mudah dilakukan `git bisect`. Kehilangan detail granular micro-commit.<br>**Merge Commit**: Mempertahankan konteks historis riil, tetapi history menjadi rumit (*train track*) dan menyulitkan otomatisasi pembacaan log. |
| **Repository Strategy** | **Monorepo** | **Polyrepo** | **Monorepo**: Dependensi lintas tim tersentralisasi, refactoring global mudah, namun butuh *tooling* berat (Bazel, Nx) dan optimasi checkout Git (sparse-checkout).<br>**Polyrepo**: Akses terisolasi, repositori ringan, namun membuat *cross-service contract breakages* sulit dilacak. |
| **Signing Method** | **GPG Signing** | **SSH Signing** | **GPG**: Standar lama industri, integrasi enterprise luas, namun manajemen key, expiry, dan web of trust sangat kompleks.<br>**SSH**: Ringan, memanfaatkan key SSH developer yang sudah ada, mudah dikonfigurasi, didukung Git versi >= 2.34. |

---

## SEKSI 11 — BEST PRACTICES

### 1. Repository Governance Configuration
Setiap repositori enterprise wajib memiliki file spesifikasi reviewer `.github/CODEOWNERS` (atau konfigurasi padanan pada GitLab / Bitbucket):
```text
# Global owner untuk semua file
*                   @enterprise/platform-leads

# Modul spesifik
/infra/terraform/   @enterprise/cloud-engineers
/auth/              @enterprise/security-team
```

### 2. Penerapan Local Pre-Commit Framework
Cegah human-error sebelum mencapai upstream dengan `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: check-added-large-files
        args: ['--maxkb=1024']
      - id: check-merge-conflict
      - id: detect-private-key
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.2
    hooks:
      - id: gitleaks
```

Instalasi framework secara lokal:
```bash
pip install pre-commit
pre-commit install
```

### 3. Aturan Operasional Commit
*   **Atomic Commits**: Satu commit harus menyelesaikan satu unit logika bisnis. Jangan mencampur perbaikan bug dengan refactor kode atau pembaruan konfigurasi.
*   **Immutability Policy**: Dilarang menjalankan `git push --force` ke shared branch (`main`, `staging`, `production`). Wajib gunakan `--force-with-lease` hanya pada branch fitur pribadi jika benar-benar dibutuhkan setelah rebase.
*   **No Binary in Git**: Gunakan Git LFS (Large File Storage) atau Artifact Registry (Nexus/Artifactory) untuk file biner berukuran > 5MB.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Menjalankan Force Push Destruktif
*   **Kesalahan**: Mengeksekusi `git push --force origin feature-branch` saat rekan tim lain sedang ikut berkontribusi pada cabang yang sama.
*   **Dampak**: Menghapus pekerjaan anggota tim yang telah di-push sebelumnya tanpa pemberitahuan.
*   **Mitigasi**: Gunakan flag protektif:
    ```bash
    git push --force-with-lease origin feature-branch
    ```
    Perintah ini akan gagal jika ada commit baru di remote yang belum diambil (*fetched*) secara lokal.

### 2. Melakukan Rebase pada Public Branch
*   **Kesalahan**: Menjalankan `git checkout main && git rebase some-feature`.
*   **Dampak**: Golden Rule Git dilanggar: *Never rebase a public branch*. Hash commit pada branch utama berubah total, memaksa semua developer lain melakukan perbaikan manual (*diverged branches*).

### 3. Commit Secret (API Keys/Private Tokens) lalu Dihapus di Commit Berikutnya
*   **Kesalahan**:
    ```bash
    git commit -m "add config with api key"
    git rm credentials.json
    git commit -m "remove secret"
    ```
*   **Dampak**: Secret tetap berada di dalam DAG database `.git/objects` selamanya dan dapat diekstrak oleh siapapun yang memiliki hak akses klon.
*   **Solusi Perbaikan**: Secret harus segera di-revoke (diasumsikan telah bocor). Bersihkan riwayat secara permanen menggunakan `git-filter-repo`:
    ```bash
    git-filter-repo --path credentials.json --invert-paths
    ```

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Lab 1: Interactive Rebase dan History Sanitation
*   **Tujuan**: Mengubah riwayat kerja lokal yang berantakan menjadi riwayat enterprise siap-audit.
*   **Skenario**:
    1. Buat folder baru `lab-git-rebase` dan inisialisasi Git.
    2. Buat file `api.py` dengan konten awal baris komentar. Commit dengan pesan `setup api`.
    3. Tambahkan fungsi `login()`. Commit dengan pesan `wip`.
    4. Tambahkan komentar di dalam fungsi `login()`. Commit dengan pesan `typo`.
    5. Tambahkan fungsi `logout()`. Commit dengan pesan `add logout`.
*   **Tugas**:
    Lakukan interactive rebase untuk menggabungkan commit 2 dan 3 menjadi satu commit utuh: `feat(api): add user login functionality`, dan ubah commit 4 menjadi: `feat(api): add user logout functionality`. Pastikan commit pertama (`setup api`) diubah menggunakan Conventional Commit menjadi: `chore(api): initialize service skeleton`.

### Lab 2: Pemulihan Bencana dengan Git Reflog
*   **Tujuan**: Menyelamatkan branch yang terhapus secara tidak sengaja.
*   **Skenario**:
    1. Buat branch bernama `hotfix/critical-payload`.
    2. Tambahkan file `hotfix.txt`, commit perubahan tersebut.
    3. Pindah kembali ke branch `main`: `git checkout main`.
    4. Hapus branch secara paksa: `git branch -D hotfix/critical-payload`.
*   **Tugas**:
    Gunakan `git reflog` untuk melacak SHA commit terakhir dari branch yang terhapus tersebut, lalu pulihkan branch kembali utuh ke status sebelum dihapus.

### Lab 3: Proteksi Repository dengan Pre-commit Git Hook
*   **Tujuan**: Membangun custom hook lokal untuk mendeteksi *hardcoded secrets* sederhana.
*   **Tugas**:
    1. Masuk ke direktori `.git/hooks/`.
    2. Buat file executable `pre-commit`.
    3. Tulis script bash yang memeriksa apakah ada penambahan string `AWS_SECRET_ACCESS_KEY` atau `BEGIN RSA PRIVATE KEY` pada file yang di-stage (`git diff --cached`).
    4. Jika string ditemukan, hook harus menolak commit (*exit code non-zero*) dan menampilkan pesan kesalahan.
    5. Uji efektivitas script dengan mencoba melakukan commit file dummy yang mengandung token tersebut.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1.  **Jika branch `feature` ditarik dari `main`, kemudian dilakukan `git rebase main` pada branch `feature`, apa yang secara fundamental terjadi pada commit di branch `feature`?**
    *   A. Hash SHA commit tetap sama, hanya pointer branch yang diperbarui.
    *   B. Commit-commit di branch feature dihapus secara permanen dan digantikan oleh merge commit.
    *   C. Commit-commit di branch feature diputar ulang di atas commit terakhir `main` sehingga menghasilkan hash SHA baru.
    *   D. Git menyalin branch `main` ke dalam direktori lokal branch feature.
    *   *Kunci Jawaban*: **C**. Rebase membuat replika commit baru dengan parent yang baru, sehingga mengubah hash SHA unik dari masing-masing commit.

2.  **Manakah strategi branching yang paling direkomendasikan untuk organisasi yang mengimplementasikan Continuous Deployment (deploy ke produksi berkali-kali per hari)?**
    *   A. GitFlow
    *   B. Trunk-Based Development
    *   C. Environment Branching (dev -> test -> uat -> prod)
    *   D. Release-driven Development
    *   *Kunci Jawaban*: **B**. Trunk-Based Development meminimalkan siklus integrasi dan menghilangkan branch jangka panjang, memungkinkan deployment berfrekuensi tinggi dengan risiko minimal.

3.  **Mengapa eksekusi perintah `git rm secret.txt && git commit -m "remove secret"` TIDAK mengamankan rahasia yang tidak sengaja terdorong ke repositori?**
    *   A. File masih tersimpan pada RAM server Git.
    *   B. Objek blob dari file tersebut tetap tersimpan di riwayat commit sebelumnya di dalam `.git/objects`.
    *   C. Perintah tersebut hanya menghapus file dari staging area, bukan dari branch.
    *   D. Git secara otomatis membuat salinan cadangan di branch remote.
    *   *Kunci Jawaban*: **B**. Git bersifat *append-only*. Perintah tersebut hanya mencatat status bahwa file telah dihapus pada commit terbaru, namun commit lama masih mereferensikan blob file yang berisi secret.

4.  **Apa perbedaan teknis fungsional antara `git pull` standar dengan `git pull --rebase`?**
    *   A. `git pull` standar selalu menghapus commit lokal yang tidak ada di remote.
    *   B. `git pull` standar mengeksekusi `git fetch` diikuti oleh `git merge`, yang sering menghasilkan merge commit otomatis tak diinginkan jika repositori divergen. Sementara `git pull --rebase` menyusun kembali commit lokal di atas commit remote terbaru.
    *   C. `git pull --rebase` membatalkan semua perubahan lokal yang belum di-stage.
    *   D. Tidak ada perbedaan teknis selain kecepatan transmisi network.
    *   *Kunci Jawaban*: **B**. `git pull` default menggunakan strategi merge yang dapat mengotori riwayat dengan unnecessary *merge bubbles*, sedangkan `--rebase` mempertahankan linearitas git history.

5.  **Perintah Git mana yang digunakan untuk melacak commit spesifik yang memperkenalkan bug secara otomatis menggunakan algoritma binary search?**
    *   A. `git blame`
    *   B. `git log -S`
    *   C. `git bisect`
    *   D. `git reflog`
    *   *Kunci Jawaban*: **C**. `git bisect` mengisolasi commit penyebab regresi menggunakan pencarian biner dengan menguji status good/bad pada serangkaian commit.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

*   **Buku**:
    *   *Pro Git* (2nd Edition) oleh Scott Chacon dan Ben Straub (Tersedia gratis di: `https://git-scm.com/book/en/v2`).
    *   *Git in Practice* oleh Mike McQuaid.
*   **Dokumentasi Resmi & Standar RFC**:
    *   Git Documentation Internals: `https://git-scm.com/docs/gitrepository-layout`
    *   Conventional Commits v1.0.0 Specification: `https://www.conventionalcommits.org/en/v1.0.0/`
    *   Trunk-Based Development Reference Guide: `https://trunkbaseddevelopment.com/`
*   **Alat Bantu Enterprise**:
    *   Gitleaks: Standalone Secret Scanner for Git Repositories (`https://github.com/gitleaks/gitleaks`).
    *   Pre-commit: Multi-language Pre-commit Hook Framework (`https://pre-commit.com/`).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1.  **Git adalah Database Berbasis Konten**: Seluruh file, direktori, dan commit disimpan dalam bentuk objek terkompresi yang diidentifikasi oleh hash kriptografis yang membentuk Directed Acyclic Graph (DAG).
2.  **Struktur Branching Menentukan Kecepatan Deployment**: Enterprise modern bertransisi dari alur kerja warisan yang kaku (*GitFlow*) ke alur kerja berbasis *Trunk-Based Development* untuk memperpendek masa integrasi dan mencegah *merge conflicts* masif.
3.  **Integritas dan Keamanan adalah Mandatori**: Penandatanganan commit menggunakan SSH/GPG bukan opsi tambahan, melainkan prasyarat untuk memvalidasi identitas penulis dan menjamin pipeline software supply-chain terlindungi dari pemalsuan kode.
4.  **History Git Dapat Direkayasa (Dengan Aman)**: Pemanfaatan *Interactive Rebase* memungkinkan insinyur merapikan riwayat lokal menjadi commit log atomik yang informatif, namun manipulasi riwayat pada branch publik yang dibagi dilarang keras untuk menjaga stabilitas kolaborasi tim.

---

## SEKSI 17 — GLOSARIUM

*   **Atomic Commit**: Praktik menyimpan satu unit perubahan logika fungsional lengkap yang tidak merusak build dan dapat di-revert secara independen.
*   **CODEOWNERS**: File konfigurasi repository yang secara otomatis menetapkan individu atau tim tertentu sebagai reviewer wajib untuk perubahan pada jalur direktori yang ditentukan.
*   **Conventional Commits**: Format standar penulisan commit yang mempermudah otomatisasi pembuatan release notes dan pelabelan versi SemVer secara deterministik.
*   **Directed Acyclic Graph (DAG)**: Struktur data matematika berbasis simpul (commit) dan rusuk terarah tanpa siklus berulang, menjadi basis penyimpanan relasi commit Git.
*   **Fast-Forward Merge**: Penggabungan branch di mana pointer branch target cukup dimajukan ke commit terakhir branch sumber tanpa pembuatan merge commit baru karena tidak ada divergensi histori.
*   **Git Reflog**: Log referensi lokal yang mencatat setiap pergerakan pointer `HEAD`, berfungsi sebagai mekanisme pemulihan data ketika commit atau branch hilang.
*   **Interactive Rebase (`git rebase -i`)**: Utilitas manipulasi urutan, konten, atau pesan pada rangkaian commit lokal sebelum digabungkan ke branch utama.
*   **Semantic Versioning (SemVer)**: Standar format penomoran versi aplikasi: `MAJOR.MINOR.PATCH` (misal: 2.4.1), di mana kenaikan angka merepresentasikan derajat signifikansi perubahan kode.

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Poin Penekanan Materi**:
    *   Pastikan siswa benar-benar memahami perbedaan antara *Working Directory*, *Staging Area (Index)*, dan *Git Directory (`.git`)* sebelum masuk ke materi manipulasi rebase.
    *   Tunjukkan langsung isi direktori `.git/objects` dan demokan utilitas `git cat-file -p <hash>` untuk membongkar miskonsepsi bahwa Git menyimpan perubahan dalam bentuk "delta diff", padahal Git menyimpan *snapshot* utuh.
*   **Potensi Jebakan Mahasiswa (Common Pitfalls)**:
    *   Banyak pemula terjebak dalam *Detached HEAD state*. Berikan penjelasan visual bahwa detached HEAD hanya berarti `HEAD` menunjuk langsung ke sebuah hash commit, bukan ke sebuah branch name.
    *   Ketakutan terhadap Rebase. Bimbing siswa untuk melihat rebase sebagai linearisasi log lokal, bukan tindakan destruktif jika diterapkan pada branch private.
*   **Setup Lingkungan Belajar (Lab Prerequisite)**:
    *   Gunakan Git versi minimum `2.34+` di workstation siswa untuk mendukung native SSH signing.
    *   Siapkan repository Git sandbox lokal agar siswa berani mencoba command berisiko seperti `git reset --hard` dan `git rebase` tanpa rasa khawatir merusak pekerjaan tim.

---

## SEKSI 19 — CHANGELOG & VERSI

| Versi | Tanggal Rilis | Penulis / Maintainer | Ringkasan Perubahan |
| :--- | :--- | :--- | :--- |
| **v1.0.0** | 2024-05-20 | Lead DevOps Curriculum Architect | Rilis kurikulum awal berstandar enterprise (TBD, SSH Signing, Git Hooks). |
| **v1.1.0** | 2024-06-15 | Senior Infrastructure Engineer | Penambahan panduan mitigasi secret leak menggunakan `git-filter-repo`. |

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya**: `CF-LNX-03` — Advanced Linux System Administration & Shell Automation
*   **Modul Saat Ini**: `CF-GIT-01` — Version Control System Terapan: Git Enterprise
*   **Modul Berikutnya**: `CF-NET-01` — Network Fundamentals for Cloud Engineers & DevOps (TCP/IP, DNS, Routing, TLS Termination)