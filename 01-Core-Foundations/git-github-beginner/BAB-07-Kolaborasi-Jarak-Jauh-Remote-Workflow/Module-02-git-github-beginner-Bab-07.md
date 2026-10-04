# MODUL 02 - BAB 07: DEEP DIVE, IMPLEMENTASI LANJUTAN & ARSITEKTUR PRODUKSI

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- **Menganalisis dan Membongkar** arsitektur internal Git: *Directed Acyclic Graph* (DAG), *Content-Addressable Storage*, serta objek primitif (*blob*, *tree*, *commit*, *annotated tag*).
- **Menerapkan Manipulasi Git Tingkat Rendah (*Plumbing Commands*)** untuk mengotomasi alur kerja, merekonstruksi metadata repositori, dan membedah struktur internal `.git`.
- **Mengarsitekturi Workflow Produksi Skala Enterprise**: Mengelola *Monorepo* vs *Multi-repo* menggunakan *Git Worktrees*, *Sparse-Checkout*, *Partial Clones*, dan *Subtrees*.
- **Mengeksekusi Strategi Disaster Recovery Tingkat Lanjut**: Melacak dan memulihkan *dangling commits*, *corrupted refs*, dan melakukan *scrubbing* kredensial sensitif pada histori commit menggunakan `git-filter-repo` tanpa merusak integritas kriptografis repositori.
- **Mengoptimalkan Performa Operasional Repositori**: Melakukan *garbage collection tuning*, *packfile optimization*, dan mitigasi bottleneck transfer data pada skala gigabyte.

---

## 2. Prerequisite

Peserta wajib menguasai:
1. Pemahaman solid terhadap *Porcelain commands* dasar Git (`git init`, `add`, `commit`, `branch`, `checkout`, `merge`, `rebase`, `pull`, `push`).
2. Konsep dasar sistem operasi POSIX: manipulasi filesystem, symbolic links, file descriptor, standard I/O redirection, dan *hash hashing algorithm* (SHA-1, SHA-256).
3. Pengalaman dasar dalam terminal shell scripting (Bash/Zsh) untuk otomasi pipeline.

---

## 3. Concept & Internal Architecture (Mendalam)

Git bukanlah sistem pelacak perbedaan file tradisional (*delta-based version control system*) seperti VCS generasi awal. Git secara arsitektural adalah **Sistem Berkas Terarah Berbasis Konten (*Content-Addressable File System*)** yang membungkus lapisan *Directed Acyclic Graph* (DAG) sebagai basis riwayat revisinya.

```
       .git/ Directory Structure
       +---------------------------------------------+
       | HEAD -> refs/heads/main                     |
       | config                                      |
       | index  (Binary Stat-Cache / Staging Area)   |
       | objects/                                    |
       |   ├── [0-9a-f]{2}/ (Loose Objects)          |
       |   ├── pack/        (Packfiles & Indices)    |
       |   └── info/                                 |
       | refs/                                       |
       |   ├── heads/       (Local Branch Pointers)  |
       |   ├── tags/        (Tag Pointers)           |
       |   └── remotes/     (Remote Tracking Refs)   |
       +---------------------------------------------+
```

### 3.1. Empat Objek Primitif Git

Setiap data yang dimasukkan ke dalam basis data Git (`.git/objects`) dikompresi menggunakan zlib (RFC 1950) dan diberi pengenal berupa *checksum* kriptografis berukuran 160-bit (40 karakter heksadesimal) untuk SHA-1, atau 256-bit (64 karakter) pada ekstensi SHA-256. Objek-objek ini bersifat **immutable**.

1. **Blob (*Binary Large Object*)**: Hanya menyimpan representasi byte data mentah dari sebuah berkas. Blob *tidak* menyimpan nama berkas, path, permission bit, maupun timestamp.
2. **Tree**: Berfungsi ekuivalen dengan direktori pada sistem berkas POSIX. Tree memetakan daftar nama berkas, atribut izin (misal: `100644` untuk regular file, `100755` untuk executable, `040000` untuk sub-tree), serta referensi hash SHA ke objek *Blob* atau *Tree* anak.
3. **Commit**: Menyimpan snapshot *root tree* dari proyek pada titik waktu tertentu, array parent commit hash (0 untuk root commit, 1 untuk direct commit, $\ge 2$ untuk merge commit), metadata author, committer, timestamp, dan commit message.
4. **Annotated Tag**: Objek independen yang menunjuk langsung ke commit hash tertentu dengan menyertakan tanda tangan PGP (opsional), pesan tagging, dan metadata tagger.

### 3.2. Lifecycle Objek: Loose Objects vs. Packfiles

Saat file ditambahkan (`git add`), Git membuat **Loose Object**. File disimpan di direktori `.git/objects/xx/yyy...` (di mana `xx` adalah 2 karakter pertama hash, dan sisanya 38 karakter menjadi nama file).

```
Hash: d670460b4b4aece5915caf5c68d12f560a9fe3e4
Path: .git/objects/d6/70460b4b4aece5915caf5c68d12f560a9fe3e4
```

Jika repositori memiliki ribuan loose objects, filesystem I/O akan mengalami degradasi performa drastis. Git menyelesaikan ini melalui **Packfiles** (`.pack`) yang didampingi file index (`.idx`). 
- **Packfile**: Mengonsolidasikan ratusan hingga jutaan objek terpisah ke dalam satu file biner tunggal menggunakan kompresi *sliding-window delta compression*. Objek yang mirip (misal beberapa revisi dari file yang sama) dihitung selisih deltanya terhadap versi terbaru (*reverse delta mechanism*).
- **Index File (`.idx`)**: Memetakan *byte-offset* langsung setiap SHA-1 di dalam packfile terkait, memfasilitasi pencarian objek berkecepatan $O(\log N)$ via binary search.

### 3.3. Arsitektur Index (Staging Area)

File `.git/index` adalah struktur data biner terurut berdasarkan path. Index bertindak sebagai cache statis antara working tree dan object database Git. Index menyimpan:
- Timestamp modifikasi file (`mtime`, `ctime`).
- Metadata ukuran file, dev, inode, UID, GID.
- Flags (misal: merge conflict stages 1, 2, dan 3).
- Pemetaan path relatif terhadap root kerja dengan SHA-1 dari blob yang telah distage.

Saat Anda menjalankan `git status`, Git tidak membaca ulang isi seluruh file; Git hanya membandingkan metadata stat POSIX file sistem kerja terhadap data biner yang tersimpan di dalam `.git/index`. Jika stat identik, Git menjamin berkas tidak dimodifikasi secara instan tanpa scanning I/O berlebih.

---

## 4. Why & What

### Mengapa Perlu Memahami Git Hingga Lapisan Arsitektur dan Plumbing?
Pada skala proyek individual, *porcelain commands* (`git add`, `git commit`) sudah cukup memadai. Namun, pada level enterprise:
1. **Repository Performance Optimization**: Repositori berukuran puluhan gigabyte dengan puluhan juta commit graph akan mengalami bottleneck saat `git status` atau `git fetch` jika packfile dan pruning tidak dikonfigurasi secara manual.
2. **Deterministic Disaster Recovery**: Ketika branch terhapus secara tidak sengaja melalui `git push --force`, porcelain commands standar sering kali gagal merekonstruksi commit history. Pemahaman mengenai DAG and Reflog memungkinkan engineer mengembalikan state produksi dalam hitungan detik.
3. **Advanced Build Pipeline Engineering**: Implementasi monorepo dengan CI/CD runner membutuhkan manipulasi sparse checkout dan partial clone untuk memangkas waktu checkout dari 45 menit menjadi 8 detik.

### Apa Perbedaan Porcelain vs. Plumbing?
- **Porcelain Commands**: Antarmuka tingkat tinggi (*high-level user-facing tools*) yang didesain untuk kenyamanan interaksi pengguna manusia (`git commit`, `git checkout`, `git branch`).
- **Plumbing Commands**: Antarmuka tingkat rendah (*low-level engine tools*) yang bersifat deterministik, stabil antar versi Git, dirancang untuk scripting, otomasi internal, dan manipulasi data langsung pada `.git` (`git hash-object`, `git cat-file`, `git mktree`, `git write-tree`, `git commit-tree`, `git update-ref`).

---

## 5. How (Workflow Detail)

### 5.1. Rekonstruksi Siklus Commit Tanpa Perintah Porcelain

Berikut adalah workflow langkah demi langkah pembuatan commit secara langsung melalui *Plumbing API*:

```
[Raw Files] ──(hash-object -w)──> [Blob Objects]
                                         │
                                   (mktree / write-tree)
                                         │
                                         ▼
                                   [Tree Object] <─── [Existing Parent Tree]
                                         │
                                   (commit-tree)
                                         │
                                         ▼
                                  [Commit Object]
                                         │
                                   (update-ref)
                                         │
                                         ▼
                               [Branch Reference: HEAD]
```

1. **Injeksi Berkas ke Object DB**:
   File di-*hash* dan dikompresi menjadi objek blob. Hash kembalian dicatat.
2. **Penyusunan Struktur Direktori (*Tree Assembly*)**:
   Index diperbarui atau manifest direktori dikonversi langsung menjadi Tree Object yang mereferensikan blob-blob terkait.
3. **Generasi Objek Commit**:
   Tree Object dipasangkan dengan parent commit ID, committer payload, dan pesan commit untuk mencetak Commit Object SHA baru.
4. **Pembaruan Namespace Pointer (*Ref Updating*)**:
   Branch pointer (misal: `refs/heads/main`) dialihkan secara atomik ke commit hash yang baru dibuat.

### 5.2. Workflow Git Worktree untuk Pengembangan Multi-Branch Simultan

Saat menangani hotfix kritikal di branch `main` sementara branch fitur `feature/large-refactor` belum siap di-commit, developer sering menggunakan `git stash` yang rentan terhadap merge collision. Arsitektur produksi modern menggunakan **Git Worktree**.

```
                           +------------------------+
                           |  Central .git/ DB     |
                           |  (All DAG Objects)     |
                           +-----------+------------+
                                       |
                   +-------------------+-------------------+
                   |                                       |
                   v                                       v
    +-----------------------------+         +-----------------------------+
    | Main Worktree               |         | Linked Worktree             |
    | Path: /srv/project/main     |         | Path: /srv/project/hotfix   |
    | Branch: refs/heads/main     |         | Branch: refs/heads/hotfix   |
    | Isolated Working Directory  |         | Isolated Working Directory  |
    +-----------------------------+         +-----------------------------+
```

1. Objek repositori tetap tunggal (menghemat disk storage).
2. Dua atau lebih branch aktif secara serentak di direktori independen.
3. Build caching (misal: node_modules, target/) tidak terinterupsi oleh perpindahan branch.

---

## 6. Analogy & Diagram ASCII

### Analogi Arsitektur Git
Bayangkan Git sebagai **Sistem Arsip Dokumen Notaris Kriptografis**:
- **Blob**: Halaman fotokopi dokumen tanpa judul. Notaris tidak peduli apa nama dokumennya; ia hanya membaca isinya, menstempel halaman tersebut dengan cap segel sidik jari matematis (Hash SHA), dan memasukkannya ke laci raksasa.
- **Tree**: Daftar isi folder map arsip. Daftar ini menuliskan: "Dokumen dengan nama kontrak.docx adalah dokumen dengan cap segel `a1b2c3d...`".
- **Commit**: Berita acara yang ditandatangani notaris: "Pada tanggal 20 Oktober, arsip folder dengan daftar isi tree `x9y8z7...` resmi dibukukan. Arsip ini adalah kelanjutan sah dari berita acara kemarin bertanda tangan `m4n5o6...`".
- **Branch**: Secarik kertas sticky note bertuliskan `MAIN` yang ditempelkan di atas map berita acara terakhir. Ketika ada berita acara baru, sticky note tersebut tinggal dicabut dan ditempelkan pada berkas yang baru.

### Diagram Representasi DAG Objek Git

```
  TAG: v1.0.0
       │
       ▼
 [ Commit: 8f2a1b ] ──parent──> [ Commit: 1a9c3d ]
   Tree: e3b0c4                  Tree: 4b825d
   Author: Alice                 Author: Bob
       │                             │
       ▼                             ▼
  [ Tree: e3b0c4 ]              [ Tree: 4b825d ]
  ├── 100644 blob 3b18e5 (app.py) └── 100644 blob a842bc (README.md)
  └── 040000 tree d41d8c (src/)
               │
               ▼
         [ Tree: d41d8c ]
         └── 100755 blob f4c291 (build.sh)
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Membuat Commit Murni Menggunakan Plumbing Command

Berikut adalah simulasi rekonstruksi commit langkah demi langkah tanpa menggunakan perintah `git add` maupun `git commit`.

```bash
# 1. Inisialisasi sandbox
mkdir git-plumbing-sandbox && cd git-plumbing-sandbox
git init

# 2. Buat file mentah
echo "console.log('Enterprise Architecture');" > core.js

# 3. Tulis file langsung ke dalam Object Database Git (Membuat BLOB)
BLOB_SHA=$(git hash-object -w core.js)
echo "Blob SHA: $BLOB_SHA"
# Verifikasi isi dan tipe objek di database
git cat-file -p $BLOB_SHA
git cat-file -t $BLOB_SHA

# 4. Baca blob ke dalam index staging area secara manual
# Format mode: 100644 (regular), 100755 (executable)
git update-index --add --cacheinfo 100644 $BLOB_SHA core.js

# 5. Tulis index menjadi Tree Object (Membuat TREE)
TREE_SHA=$(git write-tree)
echo "Tree SHA: $TREE_SHA"
git cat-file -p $TREE_SHA

# 6. Buat commit yang menunjuk ke Tree Object tersebut (Membuat COMMIT)
COMMIT_SHA=$(echo "feat(core): initial direct plumbing commit" | git commit-tree $TREE_SHA)
echo "Commit SHA: $COMMIT_SHA"

# 7. Arahkan branch refs/heads/main ke Commit SHA baru
git update-ref refs/heads/main $COMMIT_SHA

# 8. Verifikasi melalui log porcelain standar
git log -p -1
```

### 7.2. Practical Example: Monorepo Optimization dengan Sparse-Checkout & Worktree

Implementasi enterprise untuk arsitektur monorepo masif (backend dan frontend terisolasi tanpa perlu clone ganda).

```bash
#!/usr/bin/env bash
set -euo pipefail

# Inisialisasi clone bare/mirror atau blobless clone untuk menghemat I/O
REPO_URL="https://github.com/example-org/massive-monorepo.git"

# Skenario: Clone repositori besar tanpa mengambil blob historis sekaligus
git clone --filter=blob:none --no-checkout $REPO_URL repo-production
cd repo-production

# Aktifkan Sparse-Checkout dengan mode cone (arsitektur deterministik berbasis folder)
git sparse-checkout init --cone

# Set direktori spesifik yang relevan untuk target domain engineer (Domain: Payment Service)
git sparse-checkout set services/payment-gateway libraries/common-auth

# Bangun worktree terisolasi untuk menangani patch kritis branch 'hotfix-null-pointer'
git worktree add -b hotfix-null-pointer ../payment-hotfix-workspace main

# Beralih ke workspace baru yang sepenuhnya terisolasi
cd ../payment-hotfix-workspace

# Verifikasi kondisi working tree yang hanya memuat direktori terpilih
ls -la
git status
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Disaster Recovery & Credential Leak Scrubbing pada Financial Core System

**Latar Belakang Kasus**:  
Sebuah bank digital memproses pembayaran melalui repositori monorepo terpadu. Seorang developer junior secara tidak sengaja meng-commit konfigurasi berisi private key TLS produksi (`certs/prod_payment.key`) bersama ratusan file commit migrasi schema. Commit tersebut telah dipush ke branch `develop` dan di-pull oleh 70 developer aktif serta 12 CI/CD automation runner.

**Masalah**:
1. Menghapus file pada commit baru (`git rm certs/prod_payment.key && git commit`) tidak menyelesaikan kebocoran: file private key tetap tersimpan permanen di histori commit DAG `.git/objects`.
2. Repositori memiliki total ukuran 45 GB dengan total 400.000 commit. Perintah konvensional `git filter-branch` membutuhkan estimasi durasi eksekusi lebih dari 14 jam (berisiko corrupt pada branch concurrent).

**Solusi Arsitektur**:  
Tim platform architecture mengambil tindakan intervensi menggunakan `git-filter-repo` (perangkat modern pengganti filter-branch berbasis Python binding C):

```bash
# 1. Karantina repositori pada sisi remote (GitHub/GitLab API freeze: Block Push)
# Token and key revocation dipicu secara otomatis oleh secret scanner.

# 2. Buat backup bare clone repositori
git clone --mirror git@github.com:bank-digital/core-platform.git core-platform-backup.git
cd core-platform-backup.git

# 3. Eksekusi selective object purging menggunakan git-filter-repo
# Menghapus file spesifik dari seluruh commit DAG, tags, dan dereferenced refs
git filter-repo --path certs/prod_payment.key --invert-paths --force

# 4. Verifikasi kriptografis: pastikan tidak ada blob hash yang tersisa dari secret
git log --all --full-history -- "certs/prod_payment.key"
# Output harus nihil

# 5. Lakukan agresif Garbage Collection untuk memusnahkan loose objects yang melayang (unreachable)
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# 6. Override commit graph ke remote repository dengan koordinasi terstruktur
git push origin --force --all
git push origin --force --tags
```

**Hasil & Metrik**:
- Kredensial private key berhasil dihapus dari 100% commit graph history.
- Waktu eksekusi scrubbing turun drastis dari estimasi 14 jam menjadi 3 menit 42 detik.
- Integritas SHA commit berubah secara terprediksi, dan automated script disebarkan ke workstation developer lokal untuk melakukan resinkronisasi berbasis `git rebase` tanpa meng-clone ulang 45 GB data.

---

## 9. Trade-offs

| Pendekatan / Fitur | Keuntungan | Kerugian / Risiko | Biaya Operasional / Rekomendasi |
| :--- | :--- | :--- | :--- |
| **Git Submodules** | Memisahkan repositori independen secara eksplisit; mengunci referensi commit SHA spesifik. | *Detached HEAD syndrome*; update rekursif sering terlewat (`git submodule update`); CI/CD rawan gagal checkout. | Gunakan hanya jika repositori anak dikelola oleh vendor eksternal yang terpisah hak aksesnya. |
| **Git Subtree** | Menyimpan seluruh histori dependency di dalam repositori utama; developer tidak butuh konfigurasi submodule tambahan. | Menggelembungkan ukuran total repositori; manipulasi push balik ke upstream repo rumit dan rawan salah merge. | Lebih disukai untuk library internal statis jika monorepo native tidak dimungkinkan. |
| **Git Worktrees** | Bekerja pada multiple branch serentak tanpa switching context dan rebuild workspace. | Membutuhkan disk space tambahan untuk working directory; tool linter/IDE lama kadang bingung mendeteksi `.git` file pointer. | **Wajib di workstation developer** untuk multitasking context switching tanpa rebuild. |
| **Merge Commits** | Mempertahankan context histori asli secara verbatim; mudah melakukan revert atomic merge unit. | Commit graph berantakan (*spider-web DAG*); navigasi `git bisect` membutuhkan pemahaman branch topology. | Standar terbaik untuk trunk-based release cabang utama (`main`). |
| **Rebase & Squash** | Histori linier, bersih, mudah dibaca, traversal bisect menjadi deterministik. | Menghancurkan author timestamp asli; *destructive* jika dilakukan pada branch publik yang dipakai bersama. | Wajib diterapkan pada level Feature Branch sebelum merge ke release branch. |
| **Partial Clone (`--filter`)** | Mengunduh metadata saja; memangkas initial clone monorepo dari gigabytes ke megabytes. | Bergantung pada koneksi internet stabil; setiap pembacaan blob baru memicu transmisi on-demand network call. | Standar arsitektur CI/CD ephemeral runners modern. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Kesalahan Fatal: Force Push Destruktif Menghapus Histori Tim
- **Problem**: Seorang developer mengeksekusi `git push origin feature-branch --force` setelah melakukan rebase lokal yang salah arah, menimpa pekerjaan rekannya yang sudah dipush.
- **Root Cause**: Penggunaan `--force` mengabaikan pemeriksaan apakah remote reference telah bergeser sejak terakhir kali diambil (*atomic race condition*).
- **Solusi Produksi**: Selalu gunakan `--force-with-lease`.
  ```bash
  git push origin feature-branch --force-with-lease
  ```
  Ini menolak proses push jika pointer remote cabang telah dimodifikasi oleh engineer lain.

### 10.2. Memulihkan Branch yang Terhapus Permanen Melalui Reflog
- **Problem**: Cabang produksi lokal terhapus menggunakan perintah `git branch -D staging-release`.
- **Mitigasi**:
  ```bash
  # 1. Periksa histori pergerakan pointer HEAD
  git reflog show HEAD

  # Output sampel:
  # 7f3a8b1 HEAD@{0}: checkout: moving from staging-release to main
  # 9e2c1a4 HEAD@{1}: commit: fix(auth): resolve session timeout bug

  # 2. Identifikasi SHA commit terakhir sebelum branch dihapus (9e2c1a4)
  # 3. Rekonstruksi branch secara instan
  git branch staging-release 9e2c1a4
  ```

### 10.3. Mengatasi Error `.git/index.lock`: File exists
- **Problem**: Perintah Git gagal dengan fatal error: `Unable to create '.git/index.lock': File exists.`
- **Root Cause**: Proses Git sebelumnya (seperti auto-fetch IDE atau command sebelumnya) crash secara tidak normal saat sedang menulis perubahan atomik pada index file, meninggalkan lock file orphan.
- **Solusi**:
  ```bash
  # 1. Pastikan tidak ada proses Git aktif di background
  ps aux | grep git

  # 2. Hapus file lock secara aman jika proses Git terbukti mati
  rm -f .git/index.lock
  ```

---

## 11. Best Practices (Production Checklist)

### A. Repositori & DAG Hygiene
- [ ] Terapkan Linear History Strategy pada branch staging dan production melalui pull request policy (*Squash and Merge* atau *Rebase and Merge*).
- [ ] Terapkan proteksi branch (`Branch Protection Rules`): Blokir direct push, wajibkan status checks CI, dan minimal 2 approve peer-review.
- [ ] Bersihkan branch yang sudah dimerge secara terjadwal (`git fetch --prune`).

### B. Security & Integrity Checks
- [ ] Wajibkan Cryptographic Commit Signing menggunakan GPG, SSH, atau S/MIME keys.
- [ ] Konfigurasi Secret Scanner pre-commit (menggunakan tools seperti `gitleaks` atau `trufflehog`) untuk mencegah data sensitif masuk ke index staging.
- [ ] Gunakan Git config level enterprise:
  ```bash
  git config --global transfer.fsckObjects true
  git config --global fetch.fsckObjects true
  git config --global receive.fsckObjects true
  ```

### C. Engine Performance Tuning
- [ ] Aktifkan multithread index preload untuk mempercepat kalkulasi status:
  ```bash
  git config --global core.preloadindex true
  ```
- [ ] Optimalkan penanganan filesystem metadata monitoring pada filesystem besar (macOS/Windows):
  ```bash
  git config --global core.fsmonitor true
  ```

---

## 12. Hands-on Practice

Buat dan simpan script automasi berikut di dalam direktori: `hands-on/m02/production_git_deepdive.sh`.

```bash
#!/usr/bin/env bash
# ==============================================================================
# Hands-On Practice: Deep Dive Git Architecture & Disaster Recovery Simulation
# Target File: hands-on/m02/production_git_deepdive.sh
# ==============================================================================
set -euo pipefail

BASE_DIR="hands-on/m02"
mkdir -p "$BASE_DIR"
cd "$BASE_DIR"

echo "=== [1] Inisialisasi Environment Lab ==="
rm -rf git-enterprise-lab
mkdir git-enterprise-lab
cd git-enterprise-lab
git init

echo "=== [2] Pembuktian Objek Kriptografis Murni ==="
DATA_PAYLOAD="Microservice Architecture In Depth"
# Generate Blob secara langsung
BLOB_HASH=$(printf "%s" "$DATA_PAYLOAD" | git hash-object -w --stdin)
echo "Generated Blob Hash: $BLOB_HASH"

# Verifikasi format internal loose object
OBJECT_SUBDIR=$(echo "$BLOB_HASH" | cut -c 1-2)
OBJECT_FILE=$(echo "$BLOB_HASH" | cut -c 3-40)
echo "Checking disk path: .git/objects/$OBJECT_SUBDIR/$OBJECT_FILE"
test -f ".git/objects/$OBJECT_SUBDIR/$OBJECT_FILE" && echo "Object file verified on disk."

echo "=== [3] Staging Data Tanpa Perintah Porcelain 'git add' ==="
git update-index --add --cacheinfo 100644 "$BLOB_HASH" architecture.txt
TREE_HASH=$(git write-tree)
echo "Generated Tree Hash: $TREE_HASH"

echo "=== [4] Kompilasi Commit Graph Pertama ==="
COMMIT_HASH=$(echo "feat: initialize enterprise core" | git commit-tree "$TREE_HASH")
echo "Generated Commit Hash: $COMMIT_HASH"
git update-ref refs/heads/main "$COMMIT_HASH"

# Reset working tree agar sinkron dengan index dan commit baru
git read-tree --reset -u HEAD

echo "=== [5] Simulasi Worktree Lanjutan ==="
git branch feature/payment
git worktree add ../payment-service-worktree feature/payment

echo "Memverifikasi linked worktrees:"
git worktree list

echo "=== [6] Simulasi Bencana: Accidental Hard Reset & Pemulihan Reflog ==="
# Buat commit kedua
echo "Second change" >> architecture.txt
git commit -am "feat: add second change"
DISASTER_COMMIT_HASH=$(git rev-parse HEAD)

# Hancurkan working tree dan branch pointer ke commit pertama secara paksa
git reset --hard HEAD~1
echo "Kondisi setelah reset tak sengaja (Harusnya commit 1):"
git log --oneline

echo "Mengeksekusi Disaster Recovery via Reflog Analysis..."
RECOVERED_HASH=$(git reflog show HEAD | grep "add second change" | awk '{print $1}' | head -n 1)
echo "Target Commit Ditemukan di Reflog: $RECOVERED_HASH"

# Kembalikan pointer
git merge --ff-only "$RECOVERED_HASH"
echo "Kondisi setelah recovered via Reflog:"
git log --oneline

echo "=== LAB COMPLETED DENGAN SUKSES ==="
```

---

## 13. Exercise

### Level Easy
1. Gunakan perintah `git cat-file -p HEAD` untuk menginspeksi commit root. Identifikasi SHA tree yang ditunjuk, kemudian gunakan perintah yang sama untuk membaca data dari tree tersebut hingga Anda menemukan hash blob spesifik dari sebuah berkas.
2. Jelaskan mengapa SHA-1 dari file kosong (`touch empty.txt && git hash-object empty.txt`) selalu bernilai `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391`.

### Level Medium
1. Simulasikan skenario di mana branch lokal terhapus via `git branch -D`. Buat script Bash satu baris (*one-liner*) menggunakan kombinasi `git fsck --lost-found`, `awk`, dan `git show` untuk mengekstrak dan memfilter seluruh *dangling commit* yang tidak terindeks oleh reflog.
2. Konfigurasikan Git Sparse-Checkout pada repository publik berukuran besar (misal: repositori Kubernetes atau Linux Kernel) agar hanya mengambil folder dokumentasi saja tanpa mengunduh source code kernel C. Ukur perbedaan ukuran disk yang digunakan dibandingkan clone standar.

### Level Hard
1. Buat custom hook `pre-commit` tingkat enterprise menggunakan Bash shell script yang memverifikasi dua kondisi kaku sebelum mengizinkan proses commit berlanjut:
   - Tidak ada baris staging yang memuat pola regex private key AWS/Stripe (`AKIA[0-9A-Z]{16}`, `sk_live_[0-9a-zA-Z]{24}`).
   - File berukuran lebih besar dari 5 MB ditolak secara mutlak dan diarahkan untuk menggunakan Git LFS. Pengecekan ukuran harus dihitung langsung dari staging index blob, bukan dari status file working directory.

---

## 14. Challenge

**Skenario Kasus Kompleks**:  
Sebuah konglomerasi teknologi baru saja mengakuisisi tiga perusahaan startup. Setiap startup memiliki repositori Git independen dengan arsitektur polyrepo:
- Repositori A: `auth-service` (15.000 commits)
- Repositori B: `billing-engine` (22.000 commits)
- Repositori C: `notification-hub` (8.000 commits)

Dewan arsitektur memerintahkan penyatuan ketiga repositori ini ke dalam satu **Unified Monorepo**, dengan kriteria kaku non-negosiasi (*strict constraints*):
1. Seluruh commit history dari ketiga repositori harus dipertahankan secara utuh tanpa ada commit yang hilang, termasuk author name, email, author date, committer date, dan PGP signatures jika memungkinkan.
2. Setiap repositori sumber harus masuk ke dalam sub-direktori masing-masing di repositori monorepo baru (`packages/auth/`, `packages/billing/`, `packages/notification/`). File history dari Repositori A tidak boleh tercampur di root directory Monorepo baru saat diinspeksi menggunakan `git log --follow`.
3. Histori commit yang di-merge harus terurut secara kronologis atau direpresentasikan dalam multi-parent synthetic merges yang bersih.
4. **Tantangan Tambahan**: Selesaikan migrasi ini tanpa menggunakan third-party tool berbayar; hanya perbolehkan penggunaan native command: `git subtree`, `git filter-repo` / `git read-tree`, dan shell scripting native. Rancang arsitektur script transisi tersebut secara presisi.

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic
1. **Bagaimana Git menghitung SHA-1 dari sebuah berkas teks?**
   - A. Menghitung hash mentah dari isi byte teks tanpa modifikasi.
   - B. Menghitung hash dari string: `"blob " + filesize + "\0" + isi berkas mentah`.
   - C. Menggabungkan nama berkas, tanggal pembuatan sistem, dan isi file, lalu di-hash.
   - D. Menghitung hash dari representasi kompresi zip dari file tersebut.

2. **Perintah plumbing manakah yang digunakan untuk mencetak tipe objek Git berdasarkan hash SHA-nya?**
   - A. `git show --type <hash>`
   - B. `git cat-file -t <hash>`
   - C. `git check-ref-format <hash>`
   - D. `git ls-tree <hash>`

3. **Di mana Git menyimpan pointer HEAD lokal yang menunjuk ke branch aktif saat ini?**
   - A. `.git/refs/heads/HEAD`
   - B. `.git/config`
   - C. `.git/index`
   - D. `.git/HEAD`

4. **Apa karakteristik utama dari sebuah Loose Object dalam database `.git/objects`?**
   - A. Dikompresi menggunakan format tarball dan disimpan di direktori root project.
   - B. Satu objek tunggal dikompresi dengan zlib, disimpan di direktori 2-karakter awal SHA-nya.
   - C. Objek gabungan yang menyimpan selisih delta antara file lama dan file baru.
   - D. Objek yang tidak memiliki referensi parent commit di dalam reflog.

5. **Apa fungsi utama dari utilitas `git worktree`?**
   - A. Menjalankan garbage collection otomatis di background.
   - B. Membuat virtual branch yang tersimpan di cloud storage.
   - C. Membuka beberapa branch kerja berbeda secara bersamaan di direktori terpisah menggunakan satu repository database `.git` yang sama.
   - D. Menghubungkan Git dengan IDE visual tree.

---

### 5 Pertanyaan Intermediate
6. **Jika Anda menjalankan `git rebase -i` dan secara tidak sengaja menghapus semua commit pada editor interaktif, apa status objek-objek commit lama tersebut di dalam disk storage?**
   - A. Dihapus seketika dari hard drive untuk menghemat ruang disk.
   - B. Berubah menjadi *dangling commits* yang tetap tersimpan di dalam packfile/loose object sampai masa retensi garbage collection (`gc.pruneExpire`) habis.
   - C. Dikompresi otomatis menjadi berkas stash tersembunyi.
   - D. Dikirimkan kembali ke server remote repository sebagai backup state.

7. **Apa perbedaan struktural mendasar antara objek Tree dan objek Blob?**
   - A. Tree menyimpan data konten; Blob menyimpan metadata nama file.
   - B. Tree menyimpan array entri permissions, nama file/direktori, dan pointer SHA; Blob hanya menyimpan payload data byte mentah.
   - C. Tree hanya mereferensikan Commit lain; Blob mereferensikan Tags.
   - D. Tree tidak di-hash menggunakan SHA-1; Blob di-hash menggunakan SHA-1.

8. **Mengapa `git push --force-with-lease` dianggap jauh lebih aman dibandingkan `git push --force` pada pipeline enterprise?**
   - A. Karena `--force-with-lease` meminta input password dua faktor (2FA) sebelum menimpa branch remote.
   - B. Karena `--force-with-lease` membatalkan force-push jika pointer commit pada remote repository telah berubah dari apa yang diketahui oleh remote-tracking branch lokal.
   - C. Karena `--force-with-lease` secara otomatis membuat clone backup di remote server sebelum eksekusi.
   - D. Karena `--force-with-lease` hanya memperbarui file index tanpa mengubah remote DAG.

9. **Apa yang dilakukan oleh perintah `git sparse-checkout set --cone`?**
   - A. Membatasi checkout hanya pada pola file biner.
   - B. Menerapkan pola seleksi checkout yang dioptimasi secara struktural pada tingkat direktori penuh (hierarkis) untuk performa matching yang jauh lebih cepat daripada pola regex bebas.
   - C. Mengonversi monorepo menjadi sekumpulan submodules secara otomatis.
   - D. Mengunci index file agar tidak dapat dimodifikasi oleh proses lain.

10. **Bagaimana cara kerja mekanisme Packfile reverse delta compression?**
    - A. Versi lama file disimpan utuh (*base*), dan versi baru file hanya disimpan selisih perubahannya (*deltas*).
    - B. Versi paling baru dari file disimpan secara utuh (*base*), sedangkan versi-versi lama disimpan dalam bentuk perbedaan (*deltas*) terhadap versi baru tersebut.
    - C. Semua versi file dikompresi independen tanpa menghitung kesamaan antar file.
    - D. Seluruh file biner di-convert menjadi data base64 sebelum digabungkan ke packfile.

---

### 3 Skenario Kasus Produksi
11. **Skenario Disaster CI/CD Pipeline:**  
    Sebuah automated release deployment script mengalami panic saat menjalankan auto-tagging. Script tersebut secara keliru menjalankan perintah manipulasi ref langsung dan menghapus pointer `refs/tags/v2.1.0` yang merupakan release target produksi. Tim deployment tidak memiliki cadangan database tag terpisah. Namun, repositori tidak pernah di-prune (`git gc`) dalam 7 hari terakhir. Langkah apa yang paling cepat dan deterministik untuk memulihkan kembali Annotated Tag object tersebut?
    - A. Tag tidak dapat dipulihkan secara identik karena cryptographical hash-nya musnah saat pointer refs dihapus.
    - B. Jalankan `git fsck --unreachable` untuk mencari unreachable tag objects, gunakan `git cat-file -p` pada candidate hash untuk memvalidasi tagger dan isi metadata v2.1.0, lalu jalankan `git update-ref refs/tags/v2.1.0 <TAG_OBJECT_HASH>`.
    - C. Buat tag baru menggunakan `git tag v2.1.0` pada commit HEAD saat ini.
    - D. Lakukan checkout ke commit terakhir dan lakukan `git push origin --tags --force`.

12. **Skenario Monorepo Scalability:**  
    Repositori Monorepo enterprise berukuran 120 GB mengalami perlambatan ekstrem saat eksekusi `git status` (membutuhkan waktu 45 detik pada mesin developer). Profiling filesystem mengonfirmasi disk I/O menjadi bottleneck utama karena repositori memiliki lebih dari 800.000 file source code. Arsitektur konfigurasi kombinasi apa yang paling efektif memangkas waktu eksekusi `git status` menjadi sub-detik tanpa memecah repositori menjadi polyrepo?
    - A. Menjalankan `git clean -fdx` diikuti dengan `git repack -ad`.
    - B. Mengaktifkan konfigurasi `core.fsmonitor`, `core.untrackedCache`, dan membatasi working directory menggunakan `git sparse-checkout` cone mode.
    - C. Mengonversi seluruh repositori menjadi bare clone dan mengedit file via SSH.
    - D. Memindahkan direktori `.git` ke dalam RAM disk (tmpfs).

13. **Skenario Git History Secret Contamination:**  
    Sebuah repositori publik yang di-*mirror* ke GitHub kedapatan memuat secret production di dalam commit yang dibuat 3 bulan lalu (posisi commit: berada di kedalaman 500 commit di bawah HEAD saat ini pada branch `main`). Jika Anda melakukan `git rebase -i` untuk mendrop commit tersebut, branch yang bercabang dari commit tersebut akan mengalami divergen masif dan seluruh hash commit sesudahnya akan berubah. Apa tindakan operasional standar industri yang paling tepat?
    - A. Jangan ubah histori Git. Cukup rotate/revoke kredensial yang bocor pada level infrastruktur penyedia cloud, anggap commit history tersebut aman karena sudah lama tertimbun.
    - B. Jalankan `git reset --hard` ke commit sebelum commit yang bocor, lalu paksa developer menulis ulang code 3 bulan terakhir.
    - C. Rotate/revoke kredensial seketika sebagai prioritas tertinggi; gunakan `git-filter-repo` untuk menghapus string secret dari seluruh histori; force-push branch terproteksi dengan koordinasi rilis tim; edukasi tim untuk re-base tracking branch via `git pull --rebase`.
    - D. Hapus repositori di GitHub dan buat repositori baru dari source code lokal saat ini tanpa menyertakan folder `.git`.

---

### Kunci Jawaban & Rasionalisasi Evaluasi

1. **B** — Git menyusun struktur loose object dengan menambahkan header ASCII yang berisi jenis tipe objek (`blob`), spasi, ukuran payload berkas dalam bytes, diikuti oleh null-byte (`\0`), baru kemudian data byte mentah. Gabungan string ini kemudian di-hash menggunakan SHA-1.
2. **B** — Flag `-t` pada plumbing command `git cat-file` secara spesifik mengembalikan tipe dari objek (`blob`, `tree`, `commit`, atau `tag`).
3. **D** — File `.git/HEAD` adalah symbolic reference (biasanya berisi teks `ref: refs/heads/<branch_name>`) yang menunjuk ke branch yang sedang aktif di checkout.
4. **B** — Loose objects adalah objek primitif individual yang dikompresi dengan zlib dan disimpan langsung di sistem berkas berbasis dua karakter heksadesimal pertama dari checksum SHA.
5. **C** — Git worktree memungkinkan sistem berkas lokal memiliki lebih dari satu folder kerja aktif yang terhubung ke satu object store repositori `.git` yang sama, memfasilitasi multitasking tanpa manipulasi context switching via stash.
6. **B** — Git dirancang dengan prinsip *append-only*. Commit yang terlepas dari graf tidak langsung dihapus seketika; ia tetap tersimpan di filesystem sebagai *unreachable object* sampai git pruning membersihkannya (secara default masa retensi 14–30 hari).
7. **B** — Blob bersifat agnostik terhadap sistem berkas (hanya raw content byte). Tree bertindak sebagai direktori, menyimpan nama file, mode izin POSIX, dan tipe hash objek anak.
8. **B** — `--force-with-lease` menolak overwrite jika hash commit di remote tracking ref lokal tidak sama dengan hash commit faktual di server remote, mencegah tertimpanya pekerjaan rekan tim lain yang baru masuk.
9. **B** — Mode cone membatasi aturan sparse checkout hanya pada level pencocokan nama folder secara deterministik, menghindari kompleksitas komputasi parsing pola ekspresi reguler (*full pattern matching*).
10. **B** — Git berasumsi versi file terbaru adalah versi yang paling sering diakses dan dimodifikasi. Oleh karena itu, packfile menyimpan revisi terbaru secara penuh (*canonical base*), sedangkan revisi-revisi historis sebelumnya disimpan dalam selisih perbedaan terbalik (*reverse delta*).
11. **B** — Objek annotated tag adalah objek mandiri di dalam object database. Walaupun ref pointernya di `refs/tags/` dihapus, tag object itu sendiri tetap ada sebagai unreachable object di `.git/objects` sampai di-prune. `git fsck` dapat menemukannya, dan `git update-ref` dapat memulihkan pointernya seketika secara non-destruktif.
12. **B** — Kombinasi `core.fsmonitor` (mengaitkan Git dengan hook daemon event file system OS), `core.untrackedCache` (mengurangi stat scanning file yang belum dilacak), dan `sparse-checkout` (memangkas jumlah working files) adalah arsitektur resmi yang digunakan perusahaan skala besar (seperti Microsoft & GitHub) untuk monorepo masif.
13. **C** — Mengubah commit history saja tidak berguna jika secret tidak di-revoke terlebih dahulu (asumsi secret telah dikompromikan). Menggunakan `git-filter-repo` membersihkan jejak secara menyeluruh di level DAG, diikuti rotasi dan re-sinkronisasi berbasis git rebase workflow.

---

## 16. Summary

1. **Git adalah Content-Addressable Storage Engine**: Segala manipulasi tingkat tinggi (porcelain) berakar pada manipulasi empat tipe objek biner (*blob*, *tree*, *commit*, *annotated tag*) yang disimpan immutable di dalam `.git/objects` dan diidentifikasi secara unik oleh cryptographic hash.
2. **Plumbing Memberikan Kontrol Mutlak**: Memahami perintah dasar seperti `hash-object`, `write-tree`, `commit-tree`, dan `update-ref` adalah kunci dalam merancang otomatisasi internal, CI/CD pipeline generasi baru, serta investigasi corruption.
3. **Integritas Melalui DAG**: Hubungan antar commit adalah Directed Acyclic Graph. Git tidak pernah memperbarui commit di tempat; setiap perubahan metadata maupun konten akan selalu mencetak cabang graph baru. Reflog bertindak sebagai jaring pengaman utama (*safety net*) untuk melacak state pointer HEAD yang hilang.
4. **Skalabilitas Enterprise**: Monorepo berskala gigabyte membutuhkan pemanfaatan arsitektur tingkat lanjut: **Sparse-Checkout** untuk isolasi direktori kerja, **Git Worktrees** untuk parallel execution tanpa re-cloning, **Partial Clones** untuk mereduksi footprint transfer data, serta **Git LFS** untuk aset non-teks.
5. **Operational Hygiene**: Penggunaan `--force-with-lease` harus menggantikan `--force` secara universal di lingkungan produksi. Pemulihan bencana dan pembersihan data sensitif wajib mengandalkan `git-filter-repo` terpadu dengan rotasi kredensial langsung pada tingkat infrastruktur.