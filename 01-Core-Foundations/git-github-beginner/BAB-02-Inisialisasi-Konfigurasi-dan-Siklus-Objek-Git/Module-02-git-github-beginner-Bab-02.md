# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Membongkar & Menganalisis Arsitektur Internal Git**: Memvalidasi representasi biner objek Git (*blob*, *tree*, *commit*, *annotated tag*) langsung pada sistem berkas `.git/objects` menggunakan Git *plumbing commands*.
2. **Menguasai Manipulasi Riwayat Tingkat Lanjut (*Advanced History Rewriting*)**: Melakukan `git rebase -i` (interaktif), *squashing*, *splitting*, dan *cherry-picking* secara deterministik tanpa merusak integritas pohon commit.
3. **Mengoperasikan Mekanisme Pemulihan Bencana (*Disaster Recovery*)**: Memulihkan status *dangling commits*, *detached HEAD*, dan percabangan yang terhapus menggunakan Git *Reference Logs* (`git reflog`) dan `git fsck`.
4. **Merancang Strategi Branching & Delivery Enterprise**: Mengimplementasikan *Trunk-Based Development* dengan integrasi *Merge Queue*, *Protected Branches*, dan *Branch Protection Rules* berstandar keamanan industri.
5. **Mengotomatisasi Tata Kelola Repositori Tingkat Lanjut**: Mengonfigurasi *client-side* dan *server-side Git Hooks* untuk penegakan *Conventional Commits*, *GPG/SSH signature verification*, serta *Secret Scanning*.

---

## 2. Prerequisite

Peserta wajib telah memahami dan memverifikasi kompetensi berikut sebelum memulai modul ini:
* Memahami konsep dasar VCS: `git init`, `git add`, `git commit`, `git status`, `git log`, `git push`, `git pull`.
* Mahir menggunakan CLI/Terminal berbasis POSIX (Bash/Zsh) termasuk manipulasi berkas dasar (`cat`, `mkdir`, `tree`, `find`, pipes `|`).
* Memiliki akun GitHub Enterprise atau GitHub Free/Team dengan akses konfigurasi repositori administratif.
* Telah menginstal Git versi $\ge 2.40.0$ pada sistem lokal.

Verifikasi kesiapan lingkungan:
```bash
git --version
# Output minimal: git version 2.40.0
```

---

## 3. Concept & Internal Architecture

Git pada dasarnya bukanlah *Version Control System* monolitik konvensional; Git adalah **Content-Addressable Key-Value Store** terdistribusi yang dilapisi oleh antarmuka VCS tingkat tinggi (*porcelain commands*).

```
+-----------------------------------------------------------------------+
|                         Git Porcelain Layer                           |
|       (git add, git commit, git checkout, git branch, git merge)      |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                         Git Plumbing Layer                            |
|    (git hash-object, git cat-file, git mktree, git commit-tree)       |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                 Object Storage Engine (.git/objects)                  |
|  [SHA-1/SHA-256 Hashing] -> [zlib Deflate] -> [Key-Value File Store]  |
+-----------------------------------------------------------------------+
```

### 3.1. Struktur Objek Git (The Core 4)
Semua entitas di dalam Git diidentifikasi oleh hash SHA-1 (40 karakter heksadesimal) atau SHA-256 (64 karakter pada repositori baru). Data dikompresi menggunakan format `zlib`.

1. **Blob (Binary Large Object)**: Menyimpan konten berkas murni tanpa metadata (tidak menyimpan nama berkas, permissions, atau timestamp).
2. **Tree**: Merepresentasikan direktori. Berisi daftar pointer yang mengaitkan hash *blob* dengan nama berkas dan mode izin eksekusi (`100644` untuk standar, `100755` untuk executable), atau mengaitkan hash *tree* lain (sub-direktori).
3. **Commit**: Objek immutable yang mereferensikan root `tree` (keadaan snapshot repositori), pointer ke satu atau lebih *parent commit* (nol untuk root commit, satu untuk commit biasa, $\ge 2$ untuk merge commit), metadata author, committer, timestamp, serta commit message.
4. **Annotated Tag**: Pointer permanen ke commit tertentu yang memuat metadata penandatangan, pesan, dan opsional tanda tangan kriptografis (GPG/SSH).

```
   +---------------------------------------------------+
   |                   COMMIT OBJECT                   |
   | SHA: 7a8f3b...                                    |
   | tree: e4d2a1... (Snapshot root)                   |
   | parent: 1c09f8...                                 |
   | author: SRE Team <sre@enterprise.com> 1700000000  |
   +---------------------------------------------------+
                            |
                            v
   +---------------------------------------------------+
   |                    TREE OBJECT                    |
   | SHA: e4d2a1...                                    |
   | 100644 blob a3c2f1...    README.md                |
   | 040000 tree b9e4d0...    src/                     |
   +---------------------------------------------------+
            |                               |
            v                               v
   +-------------------+          +-------------------+
   |    BLOB OBJECT    |          |    TREE OBJECT    |
   | SHA: a3c2f1...    |          | SHA: b9e4d0...    |
   | "Hello World\n"   |          | 100644 blob ...   |
   +-------------------+          +-------------------+
```

### 3.2. Directed Acyclic Graph (DAG) & Branching Architecture
* Sebuah *branch* di Git bukanlah salinan fisik direktori (*bukan deep copy*), melainkan sebuah **pointer bergerak sederhana (41 byte: 40 byte SHA + 1 newline)** yang disimpan di `.git/refs/heads/<branch-name>`.
* `HEAD` adalah symbolic reference (`symref`) yang menunjuk ke branch yang sedang aktif saat ini (`ref: refs/heads/main`), atau menunjuk langsung ke commit hash tertentu (**Detached HEAD mode**).

### 3.3. Index (Staging Area) Binary Format
File `.git/index` adalah file biner yang memetakan working tree ke objek-objek Git. Index menyimpan:
* File metadata stat (ctime, mtime, dev/ino, uid, gid, file size).
* SHA hash dari blob yang sesuai.
* Stage flags (digunakan untuk *merge conflict tracking*: stage 0 = normal, stage 1 = ancestor base, stage 2 = target branch / `ours`, stage 3 = incoming branch / `theirs`).

---

## 4. Why & What

### Mengapa Memahami Internal Git Penting bagi Enterprise?
1. **Zero Data-Loss Capability**: Engineer yang memahami DAG dan Reflog dapat memulihkan kode yang terhapus akibat *force push* atau *bad rebase* dalam hitungan menit, menghilangkan *downtime* produktivitas.
2. **Determinisme CI/CD Pipeline**: Masalah merge conflict berskala besar di trunk branch (misal: ribuan PR masuk setiap minggu) hanya bisa diselesaikan dengan pemahaman yang benar atas *three-way merge* dan *rebase semantics*.
3. **Auditability & Regulatory Compliance**: Regulasi (seperti PCI-DSS, SOC2, ISO 27001) menuntut chain-of-custody kode yang valid: verifikasi kriptografis signature commit, pencegahan modifikasi riwayat secara tidak sah, dan proteksi branch otomatis.

### Perbandingan: Git Merge vs Git Rebase

| Aspek | Merge (`git merge`) | Rebase (`git rebase`) |
| :--- | :--- | :--- |
| **Mekanisme** | Membuat *merge commit* baru dengan $\ge 2$ parents. | Menulis ulang riwayat dengan memindahkan basis commit ke HEAD target. |
| **Topologi Riwayat** | Non-linear; mencerminkan urutan kronologis kejadian cabang. | Linear; terlihat seolah-olah semua perubahan dieksekusi secara sekuensial. |
| **Integritas Konteks** | Mempertahankan branch lifecycle asli. | Menghancurkan SHA hash commit asli (membuat commit baru dengan SHA berbeda). |
| **Resolusi Konflik** | Diselesaikan satu kali pada merge commit. | Diselesaikan commit demi commit selama proses replaying perubahan. |
| **Rekomendasi Enterprise**| Integrasi feature branch besar ke release branch. | Membersihkan feature branch lokal sebelum membuka Pull Request (Trunk-Based).|

---

## 5. How (Workflow Detail)

### 5.1. Alur Detil Manipulasi Riwayat Interaktif (Interactive Rebase)
Ketika mengeksekusi `git rebase -i HEAD~N`, alur internal Git adalah sebagai berikut:
1. Git membuat daftar TODO commit dari `HEAD~N` hingga `HEAD`.
2. Git me-reset HEAD sementara ke `HEAD~N`.
3. Sesuai instruksi konfigurasi pengguna (`pick`, `squash`, `edit`, `drop`):
   * `pick`: Mengaplikasikan commit asli menggunakan `git cherry-pick`.
   * `squash` / `fixup`: Menggabungkan perubahan ke commit sebelumnya; `squash` meminta edit commit message baru, sedangkan `fixup` membuang pesan commit tersebut.
   * `edit`: Menjeda eksekusi rebase dan mengembalikan kontrol ke terminal pada commit tersebut untuk intervensi manual.
   * `drop`: Melewati (*skip*) commit dari riwayat.
4. Git memindahkan pointer branch aktif ke commit baru yang paling ujung.

### 5.2. Alur Resolusi Three-Way Merge
Saat Git menggabungkan branch `feature` ke `main`:
1. Git mencari **Merge Base** (Lowest Common Ancestor / LCA dalam DAG).
2. Git membandingkan:
   * Diff A: `Merge Base` $\to$ `main` (Perubahan kita / *ours*)
   * Diff B: `Merge Base` $\to$ `feature` (Perubahan mereka / *theirs*)
3. Jika Diff A dan Diff B memodifikasi baris berkas yang berbeda, Git menggabungkannya secara otomatis (*auto-merging*).
4. Jika baris yang sama dimodifikasi secara berlainan: Git menuliskan *conflict markers* (`<<<<<<<`, `=======`, `>>>>>>>`) ke dalam berkas di *working tree* dan mengisi index stage 1, 2, dan 3.

---

## 6. Analogy & Diagram ASCII

### 6.1. Analogi: Git sebagai Sistem Logistik Pengarsipan Dokumen Tersegel
* **Blob**: Isi dokumen mentah yang dicetak tanpa header dan dimasukkan ke dalam amplop kaca transparan.
* **Tree**: Lembar inventaris map folder yang mencatat: "Amplop dengan barcode hash X adalah dokumen bernama `config.json`".
* **Commit**: Berita acara serah terima resmi bermeterai yang menyatakan: "Pada tanggal T, inventaris folder Y telah divalidasi, melanjutkan berita acara serah terima sebelumnya Z".
* **Branch**: Label stiker berperekat bertuliskan "PRODUCTION" yang ditempelkan di atas salah satu berita acara serah terima. Memindahkan cabang hanyalah mencopot stiker dan menempelkannya ke berita acara yang lain.

### 6.2. Diagram DAG: Resolusi Three-Way Merge vs Fast-Forward

```
KASUS 1: FAST-FORWARD MERGE (Tidak ada divergensi pada base)
Sebelum:
main:      A --- B
                  \
feature:           C --- D (HEAD)

Perintah: git checkout main && git merge feature
Sesudah:
main:      A --- B --- C --- D (HEAD)
                             ^
                           (Pointer main hanya dimajukan)

-----------------------------------------------------------------------

KASUS 2: THREE-WAY MERGE (Divergensi terjadi)
Sebelum:
                 C --- D (feature)
                /
main:      A --- B (Merge Base)
                  \
                   E --- F (main, HEAD)

Perintah: git merge feature
Sesudah:
                 C --- D
                /       \
main:      A --- B       M (Merge Commit: Parents F & D)
                  \     /
                   E --- F
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Membuat Commit Murni Melalui Plumbing Commands
Latihan ini membuktikan bahwa commit Git dapat dibuat tanpa pernah menjalankan `git add` atau `git commit`.

```bash
# Inisialisasi sandbox
mkdir git-plumbing-lab && cd git-plumbing-lab
git init

# 1. Buat blob langsung ke dalam .git/objects
BLOB_SHA=$(echo "console.log('Enterprise Core API');" | git hash-object -w --stdin)
echo "Blob created with SHA: ${BLOB_SHA}"

# 2. Masukkan blob ke Staging Area (Index) secara programatis
git update-index --add --cacheinfo 100644 "${BLOB_SHA}" index.js

# 3. Tulis Staging Area menjadi Tree Object
TREE_SHA=$(git write-tree)
echo "Tree created with SHA: ${TREE_SHA}"

# 4. Buat Commit Object yang menunjuk Tree tersebut
COMMIT_SHA=$(echo "feat(core): initial programmatic plumbing commit" | git commit-tree "${TREE_SHA}")
echo "Commit created with SHA: ${COMMIT_SHA}"

# 5. Pasang branch master/main ke Commit tersebut
git update-ref refs/heads/main "${COMMIT_SHA}"
git checkout main

# Verifikasi riwayat normal
git log -p
```

### 7.2. Practical Example: Surgical Interactive Rebase & Splitting
Skenario: Anda memiliki satu commit kotor (*dirty commit*) berisi dua fitur berbeda (`auth` dan `database`), yang harus dipecah menjadi dua atomic commits berstandar *Conventional Commits*.

```bash
# Setup dirty state
git checkout -b feature/auth-and-db
echo "jwt_secret=prod" > auth.env
echo "db_pool=20" > db.env
git add auth.env db.env
git commit -m "feat: setup auth and db together (messy)"

# Mulai interactive rebase pada commit terakhir
# Ubah aksi 'pick' menjadi 'edit' pada editor yang terbuka
GIT_SEQUENCE_EDITOR="sed -i 's/^pick/edit/'" git rebase -i HEAD~1

# Batalkan commit terakhir, kembalikan ke working tree
git reset HEAD~1

# Stage dan commit komponen Database
git add db.env
git commit -m "feat(database): configure production connection pool size"

# Stage dan commit komponen Auth
git add auth.env
git commit -m "feat(auth): configure jwt authorization secrets"

# Lanjutkan rebase hingga selesai
git rebase --continue

# Verifikasi: riwayat sekarang linear dan memiliki 2 commit terpisah yang bersih
git log --oneline -n 2
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Disaster Recovery Insiden Kredensial Bocor pada Repositori Pembayaran Skala FinTech

* **Konteks**: Sebuah repositori mikroservis gateway pembayaran diakses oleh 120 teknisi. Seorang engineer secara tidak sengaja memasukkan private key enkripsi (`production-keystore.p12`) berukuran 12MB dan men-push-nya ke branch `main`. File tersebut memuat sertifikat mTLS bank partner.
* **Tantangan**:
  * Menghapus file secara lokal dan membuat commit baru (`git rm production-keystore.p12 && git commit`) **TIDAK** menghapus file dari riwayat Git. Hash blob biner 12MB tersebut tetap tersimpan di riwayat selamanya, dapat diunduh oleh siapa pun yang memiliki hak akses klon.
  * Branch `main` diproteksi ketat dan memiliki 40+ Pull Request aktif yang basis kodenya sedang bergantung pada commit tersebut.

### Eksekusi Penanggulangan (*Incident Response Workflow*)

```bash
# LANGKAH 1: Freeze Repositori & Cabut Kredensial yang Bocor Segera
# (Tindakan pertama SRE: Revoke sertifikat di Key Management Service/KMS)

# LANGKAH 2: Instalasi alat pembersih biner resmi performa tinggi (git-filter-repo)
pip install git-filter-repo

# LANGKAH 3: Kloning mirror repositori secara fresh (bare clone) untuk inspeksi
git clone --mirror git@github.com:enterprise/payment-gateway.git repo-cleanup
cd repo-cleanup

# LANGKAH 4: Eksekusi penulisan ulang riwayat secara menyeluruh
# Menghapus berkas dari seluruh tree, ref, dan tag di seluruh DAG
git filter-repo --invert-paths --path production-keystore.p12

# LANGKAH 5: Verifikasi integritas repositori pasca-filter
git log --all --full-history -- "**/production-keystore.p12"
# Output HARUS KOSONG (menandakan file telah lenyap dari seluruh sejarah)

# LANGKAH 6: Paksa pembersihan objek yang tak bertuan (dangling/unreferenced objects)
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# LANGKAH 7: Update Remote Mirror Repositori
git push origin --force --all
git push origin --force --tags

# LANGKAH 8: Penanganan Developer Lokal (Mencegah push balik objek lama)
# Semua engineer diinstruksikan melakukan hard sync:
# git fetch origin
# git reset --hard origin/main
```

---

## 9. Trade-offs

| Pendekatan / Fitur | Keuntungan (*Pros*) | Kerugian (*Cons*) | Rekomendasi Kasus Penggunaan |
| :--- | :--- | :--- | :--- |
| **Squash Merging (GitHub PR)** | Menjaga riwayat trunk branch (`main`) tetap ultra-bersih, linear, dan mudah di-*revert* secara utuh per fitur. | Menghilangkan perincian granular langkah kerja engineering selama masa pengembangan fitur. | Standar emas untuk tim high-velocity Trunk-Based Development. |
| **Three-Way Merge (`--no-ff`)**| Mempertahankan konteks asli branch, timestamp commit individual, dan batasan eksplisit branch. | Memunculkan "merge bubbles" non-linear yang membingungkan visualisasi graph riwayat jika volume PR sangat tinggi. | Release branch pemotongan versi LTS, audit trail kaku regulasi militer/medis. |
| **Monorepo Git LFS (Large File Storage)**| Mencegah pembengkakan sistem berkas `.git/objects` akibat aset biner besar (gambar, model AI, compiled binaries). | Menambah kompleksitas CI/CD (perlu `git-lfs pull`), biaya storage remote terpisah, latensi transfer data eksternal. | Repositori dengan aset biner tetap $\ge 50$MB yang sering mengalami perubahan versi. |
| **Monorepo Sparse-Checkout** | Developer hanya mengunduh subset direktori yang mereka kerjakan; menghemat disk I/O dan memori. | Pengelolaan dependensi antar direktori lokal menjadi kompleks; potensi kegagalan resolusi IDE tooling. | Repositori raksasa berskala jutaan baris kode (misal: sistem monorepo Google/Meta/Enterprise scale). |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Kesalahan Fatal: Detached HEAD State
* **Gejala**: Developer melakukan commit kode baru setelah menjalankan `git checkout <commit-sha>`. Saat pindah ke branch lain (`git checkout main`), commit-commit baru tersebut tampak "hilang".
* **Akar Masalah**: Commit dilakukan saat `HEAD` tidak menunjuk pada branch pointer mana pun. Commit baru tidak memiliki referensi yang menambatkannya di DAG.
* **Resolusi**:
```bash
# 1. Identifikasi commit yang terisolasi melalui reflog
git reflog
# Temukan entry: e.g., "7f8b901 HEAD@{1}: commit: implement secure session"

# 2. Selamatkan commit dengan membuat branch resmi tepat di posisi commit tersebut
git branch recovery-branch 7f8b901

# 3. Pindah ke branch baru dan merge dengan aman
git checkout recovery-branch
```

### 10.2. Kesalahan Fatal: Merge Conflict pada Binary Files
* **Gejala**: Terjadi konflik Git pada file biner (misal: `schema.pb` atau `asset.png`) yang menampilkan pesan `Cannot merge binary files automatically`.
* **Akar Masalah**: Algoritma Three-Way Merge Git memproses teks baris demi baris, tidak dapat membedakan chunk pada representasi data biner terkompresi.
* **Resolusi**:
```bash
# Memaksa memilih versi cabang sendiri (current branch)
git checkout --ours path/to/binary-file.png
git add path/to/binary-file.png

# ATAU: Memaksa memilih versi cabang yang di-merge (incoming branch)
git checkout --theirs path/to/binary-file.png
git add path/to/binary-file.png

# Selesaikan merge
git commit -m "fix(assets): resolve binary conflict utilizing incoming version"
```

---

## 11. Best Practices (Production Checklist)

### Security & Integrity Checklist
- [ ] **GPG / SSH Commit Signing Wajib Aktif**: Seluruh engineer wajib menandatangani commit (`git commit -S -m "..."`). Menghilangkan celah *author spoofing*.
- [ ] **Pencegahan Force Push Terkunci**: Branch `main`, `master`, dan `release/*` wajib dilindungi aturan *Branch Protection Rule* dengan toggle `Require a pull request before merging` dan `Do not allow bypassing the above settings`.
- [ ] **Linear History Enforced**: Aktifkan `Require linear history` pada GitHub repository settings untuk memblokir merge commit kotor di branch produksi.
- [ ] **Automated Secret Scanning**: Pasang tool `gitleaks` atau `trufflehog` pada pre-commit hook lokal dan server-side GitHub Actions pipeline.

### Konfigurasi Git Hooks Enterprise (`commit-msg` Validator)
Pasang script berikut pada `.git/hooks/commit-msg` untuk menegakkan format **Conventional Commits**:

```bash
#!/usr/bin/env bash
set -eo pipefail

COMMIT_MSG_FILE=$1
COMMIT_MSG=$(head -n 1 "${COMMIT_MSG_FILE}")

# Format regex: type(scope): description
CONVENTIONAL_REGEX="^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-zA-Z0-9_\-]+\))?: .+"

if ! [[ "${COMMIT_MSG}" =~ ${CONVENTIONAL_REGEX} ]]; then
    echo -e "\e[31m[ERROR] Format commit message tidak valid!\e[0m"
    echo -e "Pesan commit yang Anda masukkan: '${COMMIT_MSG}'"
    echo -e "Format yang diizinkan adalah: \e[32mtype(scope): deskripsi\e[0m"
    echo -e "Contoh: \e[32mfeat(auth): add oauth2 token validation mechanism\e[0m"
    exit 1
fi
```
Jadikan executable:
```bash
chmod +x .git/hooks/commit-msg
```

---

## 12. Hands-on Practice

Simpan seluruh hasil latihan praktikum mandiri ini di dalam direktori `hands-on/m02/`.

### Skenario Praktik: Investigasi Forensik dan Pemulihan Bencana Repositori
Anda bertindak sebagai Incident Lead. Seorang junior developer panik karena tidak sengaja menjalankan `git reset --hard` yang menghapus fitur kritis sebelum sempat di-push ke GitHub.

```bash
# 1. Setup direktori latihan
mkdir -p hands-on/m02/forensic-lab
cd hands-on/m02/forensic-lab
git init

# 2. Buat status basis
echo "v1.0 stable release" > release.txt
git add release.txt
git commit -m "feat(release): init production v1.0"

# 3. Developer menulis fitur baru yang krusial
echo "Super critical encryption logic" >> crypto.go
git add crypto.go
git commit -m "feat(crypto): add enterprise grade AES-256 pipeline"

# 4. KECELAKAAN: Developer menjalankan hard reset ke commit awal
git reset --hard HEAD~1

# 5. PEMBUKTIAN KEHILANGAN:
ls -la
# Berkas crypto.go lenyap dari working tree!

# 6. INVESTIGASI & PEMULIHAN FORENSIK:
# Buka reference logs
git reflog

# Cari hash commit "feat(crypto): add enterprise grade AES-256 pipeline"
# Tampilan akan menyerupai:
# abc1234 HEAD@{1}: commit: feat(crypto): add enterprise grade AES-256 pipeline

# Ekstrak hash commit tersebut (ganti TARGET_HASH dengan hash yang muncul pada terminal Anda)
TARGET_HASH=$(git reflog | grep "feat(crypto)" | awk '{print $1}' | head -n 1)

# Kembalikan repositori ke kondisi commit tersebut tanpa merusak data
git branch recovery-crypto "${TARGET_HASH}"
git checkout recovery-crypto

# 7. VALIDASI HASIL RECOVERY:
cat crypto.go
# Hasil verifikasi: String "Super critical encryption logic" berhasil dipulihkan seutuhnya!
```

---

## 13. Exercise

### Level Easy
1. Dari repositori Git mana pun, carilah SHA-1 hash dari objek `tree` yang direferensikan oleh commit terbaru (`HEAD`).
2. Gunakan `git cat-file -p <TREE-SHA>` untuk menginspeksi isi struktur berkas dari tree tersebut.
3. Gunakan `git cat-file -t <BLOB-SHA>` untuk memverifikasi tipe objek dari salah satu file yang terdaftar di dalam tree.

### Level Medium
1. Buat sebuah branch baru bernama `exercise-rebase`.
2. Lakukan 4 kali commit berturut-turut yang masing-masing menambahkan 1 baris string ke sebuah berkas bernama `changelog.md`.
3. Gunakan `git rebase -i` untuk:
   * Menggabungkan (*squash*) Commit ke-2 dan ke-3 menjadi satu commit utuh.
   * Menghapus (*drop*) Commit ke-4.
   * Mengubah pesan commit pertama agar sesuai standar Conventional Commits (`docs(changelog): start documentation tracking`).
4. Verifikasi bahwa riwayat commit pada branch tersebut kini hanya tersisa 2 commit dengan urutan yang rapi.

### Level Hard
1. Buat dua branch: `release/v2.0` dan `feature/payment-v2`.
2. Simulasikan situasi merge conflict kompleks pada sebuah berkas JSON: `config/services.json` yang berisi konfigurasi multiline nested JSON.
3. Jalankan merge dan hentikan pada kondisi status konflik.
4. Gunakan `git ls-files -u` untuk memeriksa hash dari stage 1 (base), stage 2 (ours), dan stage 3 (theirs).
5. Selesaikan konflik secara manual menggunakan tool `git checkout --ours` atau `git checkout --theirs` per modul, tambahkan perubahan ke index, dan selesaikan merge commit dengan author signature yang valid.

---

## 14. Challenge

### Studi Kasus: "The Ghost Branch & Secret Incident"
**Skenario**:
Sebuah tim integrasi sistem mengalami anomali repositori skala besar:
1. Seseorang secara tidak sengaja mengunggah file credential berukuran 200MB bernama `database-dump.sql` pada branch `legacy-migration` tiga bulan yang lalu.
2. Branch `legacy-migration` telah di-merge ke branch `develop`, lalu branch `develop` di-merge ke branch `main`.
3. Meskipun file `database-dump.sql` telah dihapus menggunakan perintah biasa (`rm`) dua minggu lalu di `main`, ukuran kloning repositori (`.git` directory) membengkak menjadi $\ge 1.5$ GB, menyebabkan runner CI/CD kehabisan alokasi storage (*out of disk space*).
4. Developer lain masih memiliki branch lokal yang mengarah pada commit lama yang mengandung file tersebut.

**Tugas Arsitektur Anda**:
* Rancang panduan teknis langkah-demi-langkah (SOP Kejuruteraan) untuk:
  1. Menghapus objek blob `database-dump.sql` dari seluruh riwayat komit Git di semua branch dan tag secara permanen menggunakan tooling standar enterprise tanpa merusak *commit message* dan asosiasi *author* asli pada commit-commit lainnya.
  2. Mencegah developer lokal yang masih memiliki commit dangling lama mengunggah kembali (*pushing back*) blob 200MB tersebut ke repositori remote (setup policy proteksi di remote / pre-receive hook level).
  3. Mengurangi ukuran fisik repositori remote di disk server secara signifikan (*aggressive garbage collection*).
* **Kriteria Penilaian**: Repositori berhasil direduksi ukurannya di bawah 50MB, hash tree bersih dari file dump, dan seluruh pipeline CI/CD kembali beroperasi normal tanpa *build failure*.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1. Pertanyaan Basic (Pilihan Ganda)

1. Objek Git manakah yang menyimpan relasi antara nama berkas, mode perizinan berkas (permissions), dan hash konten berkas?
   * A. Commit Object
   * B. Blob Object
   * C. Tree Object
   * D. Tag Object

2. Perintah plumbing apa yang digunakan untuk mengekstrak isi mentah serta metadata dari sebuah objek hash Git?
   * A. `git hash-object`
   * B. `git cat-file`
   * C. `git rev-parse`
   * D. `git update-ref`

3. Apa representasi fisik dari sebuah Git branch pada sistem penyimpanan berkas lokal repositori?
   * A. File JSON yang memuat seluruh riwayat commit cabang tersebut.
   * B. Folder terkompresi yang berisi salinan lengkap source code.
   * C. Sebuah berkas teks biasa berukuran 41 byte yang hanya memuat hash SHA dari commit terakhir.
   * D. Entri biner di dalam berkas `.git/config`.

4. Apa dampak eksekusi `git reset --soft HEAD~1` terhadap status repositori?
   * A. Membatalkan commit terakhir dan membuang semua perubahan dari working directory.
   * B. Membatalkan commit terakhir, namun mempertahankan perubahan kode tetap berada di Staging Area (Index).
   * C. Menghapus branch aktif dan memindahkannya ke detached HEAD.
   * D. Menulis ulang riwayat Git langsung ke repositori remote.

5. File internal apakah yang menyimpan referensi commit yang sedang diakses (*checked out*) oleh developer?
   * A. `.git/refs/heads/master`
   * B. `.git/HEAD`
   * C. `.git/index`
   * D. `.git/config`

---

### 15.2. Pertanyaan Intermediate (Pilihan Ganda)

6. Selama proses merge conflict, `stage 2` pada Git Index merepresentasikan apa?
   * A. File yang ada pada ancestor bersama (common ancestor/merge base).
   * B. Versi file dari branch yang sedang aktif dituju (`ours`).
   * C. Versi file dari branch yang sedang digabungkan masuk (`theirs`).
   * D. File hasil auto-merge dari Git engine.

7. Mengapa menjalankan `git rebase` pada branch publik yang digunakan bersama oleh banyak teknisi (seperti branch `develop` atau `main`) sangat dilarang keras (*anti-pattern*)?
   * A. Karena rebase memakan konsumsi CPU server yang sangat besar.
   * B. Karena rebase menciptakan merge bubble yang tidak dapat diaudit.
   * C. Karena rebase mengubah SHA hash commit yang sudah ada, memaksa teknisi lain melakukan merge non-trivial pada riwayat yang divergen secara artifisial.
   * D. Rebase secara otomatis menghapus working directory developer lain.

8. Apa perbedaan struktural utama antara *Lightweight Tag* dan *Annotated Tag*?
   * A. Lightweight tag tidak bisa dipush ke remote repositori.
   * B. Annotated tag adalah objek tersendiri di dalam `.git/objects` lengkap dengan SHA, author, dan pesan, sedangkan Lightweight tag hanyalah pointer langsung ke SHA commit.
   * C. Lightweight tag ditandatangani dengan GPG, sedangkan Annotated tag tidak.
   * D. Annotated tag hanya dapat digunakan pada branch `main`.

9. Jika Anda tidak sengaja menjalankan `git branch -D payment-feature` (menghapus branch yang belum di-merge), bagaimana cara Git merecover commit tersebut sebelum Garbage Collection berjalan?
   * A. Tidak mungkin dikembalikan karena flag `-D` menghapus blob secara permanen dari disk.
   * B. Mengambil hash commit terakhir branch tersebut melalui `git reflog`, lalu menjalankan `git branch payment-feature <COMMIT-SHA>`.
   * C. Menjalankan perintah `git restore --all`.
   * D. Mengunduhnya otomatis kembali dari cache memory terminal.

10. Apa kegunaan utama dari Git hook tipe `pre-receive`?
    * A. Menolak eksekusi git commit di lokal jika format commit message salah.
    * B. Mengecek kredensial login GitHub developer di level browser.
    * C. Script server-side yang dapat membatalkan aksi `git push` jika repositori mendeteksi adanya pelanggaran aturan (misal: commit tanpa GPG signature atau file melebihi limit ukuran).
    * D. Mengompilasi kode program sebelum file dipindahkan ke working tree.

---

### 15.3. Skenario Kasus Produksi (Analisis Praktis)

11. **Skenario A**: 
    Sebuah PR dengan 15 commit ditolak oleh Lead Architect karena riwayat commit-nya tidak rapi (terdapat commit seperti `fix typo`, `wip`, `test broken`). Namun, tim tidak ingin menggunakan fitur *Squash and Merge* di GitHub UI karena ingin memecah 15 commit tersebut secara rapi menjadi 3 bagian commit logis berbasis *features*. Langkah apa yang harus dilakukan oleh pembuat PR di mesin lokalnya sebelum melakukan push ulang? Jelaskan urutan instruksinya.

12. **Skenario B**: 
    Setelah melakukan operasi merge branch yang rumit, seorang engineer menemukan bahwa production build rusak karena file konfigurasi rahasia ter-override secara keliru oleh setting branch staging. Engineer tersebut panik dan berniat membatalkan merge commit yang baru saja dibuat di lokal (belum di-push ke remote). Perintah apa yang paling aman untuk mengembalikan repositori ke kondisi tepat 1 detik sebelum proses merge dieksekusi tanpa meninggalkan artifak apa pun?

13. **Skenario C**: 
    Repositori enterprise Anda memiliki aturan bahwa setiap baris kode yang masuk ke trunk harus melalui automated testing. Namun, ketika dua branch PR yang lolos tes secara independen digabungkan ke `main` secara bersamaan, branch `main` langsung mengalami *broken build* (*semantic conflict*, bukan sintaksis). Konsep arsitektur GitHub apa yang harus diaktifkan pada branch protection settings untuk mencegah masalah konkurensi ini?

---

### Kunci Jawaban & Pembahasan Quiz

#### Jawaban Basic:
1. **C (Tree Object)**. Penjelasan: Blob hanya menyimpan data isi file; relasi nama berkas, mode bit izin eksekusi, dan struktur folder dikelola secara eksklusif oleh objek Tree.
2. **B (`git cat-file`)**. Penjelasan: `git cat-file -p` memformat dan mencetak isi objek, sedangkan flag `-t` mencetak tipenya.
3. **C (Berkas teks biasa berukuran 41 byte...)**. Penjelasan: Git branches hanyalah *movable pointers* berupa teks ASCII yang berisi 40 karakter heksadesimal SHA commit target ditambah sebuah newline byte.
4. **B (Membatalkan commit terakhir, namun mempertahankan perubahan kode tetap berada di Staging Area)**. Penjelasan: `--soft` hanya memundurkan pointer `HEAD` dan branch; file di Index dan Working Tree tidak disentuh sama sekali.
5. **B (`.git/HEAD`)**. Penjelasan: Berkas `.git/HEAD` bertindak sebagai symbolic ref penunjuk branch yang aktif saat ini.

#### Jawaban Intermediate:
6. **B (Versi file dari branch yang sedang aktif dituju / `ours`)**. Penjelasan: Pada Index Git, Stage 1 adalah base ancestor, Stage 2 adalah branch tujuan checkout aktif (`ours`), dan Stage 3 adalah branch yang sedang dimerge ke dalam repositori (`theirs`).
7. **C (Karena rebase mengubah SHA hash commit...)**. Penjelasan: Rebase menulis ulang sejarah dengan membuat objek commit baru ber-SHA beda. Mendorong commit yang di-rebase ke branch publik memaksa rekan tim lain mengalami riwayat yang tidak sinkron, memicu merge commit duplikat yang masif.
8. **B (Annotated tag adalah objek tersendiri di dalam `.git/objects`...)**. Penjelasan: Annotated tag memiliki identitas objek sendiri, checksum mandiri, dan menyimpan informasi siapa penandatangan tag tersebut.
9. **B (Mengambil hash commit terakhir branch tersebut melalui `git reflog`...)**. Penjelasan: Objek commit tidak langsung dihapus seketika; selama masa retensi GC (standar 30-90 hari), pointer reflog masih mencatat hash commit tersebut sehingga dapat dipulihkan kapan saja.
10. **C (Script server-side yang dapat membatalkan aksi `git push`...)**. Penjelasan: `pre-receive` hook dieksekusi di sisi server penampung Git (bare repository) sebelum referensi di-update; exit code selain 0 akan menolak push dari klien secara instan.

#### Pembahasan Skenario Produksi:
11. **Solusi Skenario A**: 
    Developer harus menjalankan `git rebase -i HEAD~15` di lokal. Pada file manifest TODO rebase, gunakan kombinasi `pick`, `squash`, dan `fixup` untuk mengelompokkan 15 commit menjadi 3 cluster commit logis. Ubah pesan commit menggunakan konvensi baku Conventional Commits. Terakhir, lakukan forced push dengan safety guard: `git push --force-with-lease origin <feature-branch>`.
12. **Solusi Skenario B**: 
    Gunakan perintah: `git reset --hard ORIG_HEAD` atau `git reset --hard HEAD@{1}`. Git menyimpan pointer snapshot sebelum operasi berbahaya (seperti merge atau rebase besar) pada simbolis `ORIG_HEAD`. Perintah ini membatalkan merge commit, membersihkan index, dan menyelaraskan working tree seketika ke status sebelum merge terjadi.
13. **Solusi Skenario C**: 
    Aktifkan fitur **Merge Queue** yang dikombinasikan dengan **Require branches to be up to date before merging** (*Strict status checks*). Dengan Merge Queue, GitHub secara dinamis membuat branch gabungan temporer, memvalidasi CI build pada hasil penggabungan simulasi, dan hanya men-commit ke `main` jika hasil kombinasi kedua PR tersebut benar-benar lulus pengujian integrasi.

---

## 16. Summary

* **Arsitektur Internal**: Git adalah mesin penyimpan biner *content-addressable* berbasis DAG yang mengompresi data menjadi 4 tipe objek utama: **Blobs**, **Trees**, **Commits**, dan **Tags**. Seluruh riwayat terikat oleh integritas kriptografis hashing.
* **Manipulasi Riwayat**: `git rebase -i` memberikan kontrol penuh untuk membersihkan riwayat kode sebelum integrasi, namun wajib dihindari pada branch bersama untuk mencegah divergensi riwayat lintas tim.
* **Resiliensi Data**: Di Git, hampir tidak ada data yang hilang seketika berkat proteksi **Reflog** dan penundaan pembersihan oleh engine **Garbage Collection (`git gc`)**. Bencana hard reset atau penghapusan branch dapat dimitigasi dengan identifikasi SHA pada reflog.
* **Standarisasi Enterprise**: Lingkungan produksi modern menuntut pemanfaatan **Trunk-Based Development**, penegakan tanda tangan kriptografis commit (GPG/SSH), validasi sintaks pesan commit via **Git Hooks**, serta penerapan otomatisasi keamanan seperti **Secret Scanning** dan **Merge Queues** guna menjamin stabilitas repositori berkecepatan tinggi.