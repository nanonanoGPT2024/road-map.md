# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Membedah** struktur internal Git (*Content-Addressable Storage*, *Directed Acyclic Graph/DAG*, *Loose vs. Packed Objects*, dan *Index File Format*).
- **Mengimplementasikan** optimasi repositori skala enterprise (*Sparse-Checkout*, *Partial Clones*, *Commit-Graph*, dan *Git LFS*) untuk menangani repositori multi-gigabyte dengan latensi clone minimal.
- **Membangun dan Mengotomasi** pipeline keamanan berbasis kriptografi (*Cryptographic Commit Signing* via GPG/SSH/Sigstore dan *Client/Server-Side Hooks Architecture*).
- **Mengeksekusi** strategi *Disaster Recovery* tingkat lanjut (*Reflog Forensics*, restorasi *dangling/unreachable commits*, dan rewriting history skala besar menggunakan `git-filter-repo`).
- **Merancang Arsitektur** CI/CD dan runner terdistribusi (*Self-Hosted Ephemeral Runners* dengan Kubernetes ARC pada GitHub Enterprise).

---

## 2. Prerequisites

Sebelum mempelajari modul ini, peserta wajib menguasai:
- Konsep dasar Git Porcelain (*branching*, *merging*, *rebasing*, *cherry-picking*, *stash*).
- Pemahaman sistem operasi Linux/POSIX (Bash scripting, manipulasi environment variable, POSIX signals, file descriptor).
- Dasar kriptografi asimetris (Public/Private Key pair, hashing algorithm SHA-1/SHA-256).
- Dasar arsitektur CI/CD dan containerization (Docker, Kubernetes basics).

---

## 3. Concept & Internal Architecture

Git pada dasarnya bukanlah sekadar Version Control System (VCS), melainkan sebuah **Content-Addressable Object Store** berbasis sistem berkas dengan *User Interface* VCS yang dibangun di atasnya (Porcelain).

```
                      +-----------------------------------+
                      |         PORCELAIN LAYER           |
                      | (git commit, git branch, git log) |
                      +-----------------+-----------------+
                                        |
                                        v
                      +-----------------+-----------------+
                      |          PLUMBING LAYER           |
                      |  (hash-object, cat-file, mktree)  |
                      +-----------------+-----------------+
                                        |
                                        v
+-----------------------------------------------------------------------------------+
|                            GIT INTERNAL STORAGE (.git/)                           |
|                                                                                   |
|  .git/objects/XX/YYYY...                                                          |
|  +--------------------+  +--------------------+  +-----------------------------+  |
|  |       BLOB         |  |        TREE        |  |           COMMIT            |  |
|  | - Raw File Content |  | - File Permissions |  | - Tree Object Pointer       |  |
|  | - No Metadata      |  | - Object SHA-1/256 |  | - Parent Commit Hash(es)   |  |
|  | - Compressed zlib  |  | - Filename         |  | - Author, Committer, Msg    |  |
|  +--------------------+  +--------------------+  +-----------------------------+  |
|                                                                                   |
|  .git/refs/                                      .git/index (Staging Area)        |
|  - refs/heads/* (Local Branches)                 - Binary cache of paths, modes,  |
|  - refs/tags/* (Lightweight/Annotated)             timestamps & SHA pointers      |
|  - refs/remotes/* (Remote Tracking)                                               |
+-----------------------------------------------------------------------------------+
```

### 3.1. Struktur Dasar `.git` Directory

Di balik setiap repositori, terdapat direktori `.git` yang mengendalikan seluruh status:
- `HEAD`: File teks yang mereferensikan branch aktif saat ini (`ref: refs/heads/main`) atau hash commit langsung (*detached HEAD*).
- `objects/`: Database objek. File disimpan menggunakan 2 karakter pertama dari hash sebagai direktori dan 38 karakter sisanya sebagai nama berkas (`.git/objects/4b/825dc642cb6eb9a060e54bf8d69288fbee4904`).
- `refs/`: Penunjuk pointer bernama menuju hash commit tertentu.
- `index`: Berkas biner yang bertindak sebagai *staging area*, memetakan pohon kerja (*working directory*) dengan objek di storage.
- `packed-refs` & `objects/pack/`: Kompresi objek massal untuk menghemat I/O dan storage disk.

### 3.2. Git Object Model

Ada empat objek fundamental di Git:
1. **Blob (*Binary Large Object*)**: Hanya menyimpan konten mentah file. Metadata (nama file, permission, timestamp) **tidak** disimpan di dalam blob.
2. **Tree**: Mewakili direktori. Menyimpan array dari pointer yang berisi: mode/permission file, tipe (blob atau tree subdirektori), SHA hash, dan nama file/direktori.
3. **Commit**: Menyimpan pointer ke satu Root Tree, parent commit (nol untuk root commit, satu untuk commit biasa, dua atau lebih untuk merge commit), metadata author, committer, timestamp, dan commit message.
4. **Annotated Tag**: Objek independen yang mirip commit, menunjuk ke commit tertentu, lengkap dengan signature, tagger metadata, dan pesan.

### 3.3. Loose Objects vs. Packfiles

Saat objek pertama kali dibuat, Git menyimpannya sebagai **Loose Object**:
- Di-hash dengan format: `header = "<type> <bytes>\0"`, lalu dihitung SHA-1/SHA-256 dari `header + content`.
- Dikompresi menggunakan library `zlib` (tingkat kompresi defaut: 6).
- Masalah: Menyimpan jutaan berkas kecil menyebabkan kehabisan *inode* OS dan inefisiensi block storage.

Untuk mengatasi inefisiensi tersebut, Git menggunakan **Packfile Engine**:
- **Packfile (`.pack`)**: Menggabungkan ribuan loose objects menjadi satu file biner tunggal menggunakan teknik **Delta Compression** (hanya menyimpan perbedaan/diff antara versi file yang mirip).
- **Index File (`.idx`)**: Berkas indeks biner terpisah yang menyediakan pemetaan offset biner secara langsung agar Git dapat melakukan pencarian objek dalam `.pack` dengan kompleksitas waktu $O(1)$ atau $O(\log N)$ via binary search.

---

## 4. Why & What

| Pertanyaan | Deskripsi Teknis |
| :--- | :--- |
| **Why Deep Dive Internals?** | Pemecahan masalah kritis di level enterprise (seperti *repository corruption*, *merge conflict resolution loop*, *bloated repo*, dan kebocoran kredensial historis) mustahil dilakukan hanya dengan command porcelain (`git pull`, `git push`). Tim platform engineering memerlukan akses ke plumbing command dan pemahaman struktur byte internal. |
| **Why Enterprise Arch Optimization?** | Monorepo modern berskala puluhan Gigabyte dengan ribuan developer melumpuhkan operasi clone biasa. Tanpa *Partial Clones* (Blobless/Treeless), *Commit-Graph*, dan *LFS*, waktu eksekusi CI/CD pipeline membengkak secara eksponensial, menghabiskan network bandwidth dan storage. |
| **What is Commit Signing?** | Mekanisme validasi cryptographic non-repudiation. Secara default, atribut `git config user.name` dan `user.email` dapat dipalsukan secara trivial oleh siapa saja. Commit signing memastikan integritas identitas developer menggunakan enkripsi asimetris. |

---

## 5. How (Workflow Detail)

### Workflow 1: Low-Level Plumbing Execution (Manual Object Creation)
Untuk memahami siklus pembentukan commit murni tanpa perantara porcelain:

```
[Write Content] -> hash-object -w -> [Blob Stored]
                                         |
[Update Index]  -> update-index     -> [Index Staged]
                                         |
[Write Tree]    -> write-tree       -> [Tree Created]
                                         |
[Create Commit] -> commit-tree      -> [Commit Created]
                                         |
[Update Ref]    -> update-ref       -> [Branch Pointed]
```

### Workflow 2: Enterprise Monorepo Optimization (Blobless Clone + Sparse-Checkout)
Saat bekerja pada repositori skala puluhan gigabyte:

```
Step 1: git clone --filter=blob:none --no-checkout <repo_url>
Step 2: git sparse-checkout init --cone
Step 3: git sparse-checkout set services/payment-gateway libs/common
Step 4: git checkout main
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Git sebagai Sistem File Log-Structured & Hash Table

Bayangkan Git seperti sistem perbankan berbasis buku besar (*ledger*) yang tidak bisa diubah (*immutable*):
- **Blob**: Kertas berisi teks dokumen murni tanpa judul.
- **Tree**: Folder transparan berlabel yang mencatat daftar dokumen kertas (blob) beserta nama berkas aslinya.
- **Commit**: Tanda terima resmi yang mencantumkan ringkasan isi folder pada detik tersebut, stempel waktu, tanda tangan pejabat pembuat, dan nomor seri tanda terima sebelumnya (parent hash).

### Diagram: Object Directed Acyclic Graph (DAG)

```
        +-------------------------------------------------------+
        |                    COMMIT OBJECT                      |
        | SHA: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca|
        | - tree: a1b2c3d...                                    |
        | - parent: 9f8e7d6...                                  |
        | - author: Lead Architect <eng@enterprise.com>         |
        +---------------------------+---------------------------+
                                    |
                                    v
        +-------------------------------------------------------+
        |                     TREE OBJECT                       |
        | SHA: a1b2c3d4e5f6... (Root Directory)                 |
        | - 100644 blob d670460b4b...    README.md              |
        | - 040000 tree c4a5b6d7e8...    src/                   |
        +---------------------------+---------------------------+
                                    |
           +------------------------+------------------------+
           |                                                 |
           v                                                 v
+-----------------------+                         +-----------------------+
|      BLOB OBJECT      |                         |      TREE OBJECT      |
| SHA: d670460b4b...    |                         | SHA: c4a5b6d7e8...    |
| Content:              |                         | (src/ Directory)      |
| "# Core System Engine"|                         | - 100644 blob 88fba.. |
+-----------------------+                         |   main.go             |
                                                  +-----------+-----------+
                                                              |
                                                              v
                                                  +-----------------------+
                                                  |      BLOB OBJECT      |
                                                  | SHA: 88fbae128d...    |
                                                  | Content:              |
                                                  | "package main..."     |
                                                  +-----------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Inspecting Git Internals via Plumbing Tools

Melihat representasi biner Git secara telanjang:

```bash
# 1. Inisialisasi repositori murni tanpa porcelain overhead
mkdir /tmp/git-internals-demo && cd /tmp/git-internals-demo
git init

# 2. Buat file baru dan simpan ke database objek via hash-object (Plumbing)
echo "Enterprise Architecture v1.0" | git hash-object -w --stdin
# Output: f8b64b1d6cb6008fd385fd9df848d5d4da4bd8b7

# 3. Verifikasi tipe dan konten objek langsung dari hash
git cat-file -t f8b64b1d6cb6008fd385fd9df848d5d4da4bd8b7
# Output: blob

git cat-file -p f8b64b1d6cb6008fd385fd9df848d5d4da4bd8b7
# Output: Enterprise Architecture v1.0

# 4. Periksa struktur fisik pada filesystem
ls -la .git/objects/f8/
# Output: b64b1d6cb6008fd385fd9df848d5d4da4bd8b7
```

### 7.2. Practical Example: Enterprise Production-Ready Pre-Receive Hook

Berikut adalah script `hooks/pre-receive` yang wajib dijalankan di level server/GitHub Enterprise Appliance untuk memblokir:
1. Push yang tidak memiliki cryptographic signature.
2. Commit dengan ukuran file di atas batas maksimum (>10MB).
3. Plaintext secret (AWS Access Key, Private Key).

```bash
#!/usr/bin/env bash
# ==============================================================================
# Enterprise Git Pre-Receive Hook: Cryptographic & Secret Enforcement
# Location: .git/hooks/pre-receive (Server-Side)
# ==============================================================================
set -euo pipefail

MAX_FILE_SIZE_BYTES=10485760 # 10MB
ZERO_COMMIT="0000000000000000000000000000000000000000"

while read -r oldrev newrev refname; do
    # Abaikan proses delete branch
    if [[ "$newrev" == "$ZERO_COMMIT" ]]; then
        continue
    fi

    # Rentang commit yang akan divalidasi
    if [[ "$oldrev" == "$ZERO_COMMIT" ]]; then
        # Branch baru: validasi seluruh commit baru yang tidak ada di branch lain
        commit_range="$newrev" --not --branches --tags
    else
        commit_range="$oldrev..$newrev"
    fi

    # Dapatkan daftar commit hash
    commits=$(git rev-list "$commit_range")

    for commit in $commits; do
        # 1. Enforcement: Validasi GPG/SSH Signature
        # Format %G? mengembalikan 'G' (Good/Valid), 'U' (Good untrusted), 'B' (Bad)
        sig_status=$(git log -1 --pretty=format:'%G?' "$commit")
        if [[ "$sig_status" != "G" && "$sig_status" != "U" ]]; then
            echo "REJECTED: Commit $commit must be cryptographically signed (GPG/SSH)." >&2
            echo "Signing Status Code: $sig_status" >&2
            exit 1
        fi

        # 2. Enforcement: Deteksi Kebocoran Plaintext AWS Access Key (Regex Scan)
        commit_diff=$(git diff-tree -p "$commit")
        if echo "$commit_diff" | grep -E -q 'AKIA[0-9A-Z]{16}'; then
            echo "SECURITY REJECTION: AWS Access Key detected in commit $commit." >&2
            exit 1
        fi

        # 3. Enforcement: Cek ukuran berkas dalam commit
        # Membaca daftar objek blob pada commit terkait
        git ls-tree -r -l "$commit" | while read -r mode type sha size name; do
            if [[ "$type" == "blob" && "$size" -gt "$MAX_FILE_SIZE_BYTES" ]]; then
                echo "POLICY REJECTION: File $name ($size bytes) in commit $commit exceeds limit ($MAX_FILE_SIZE_BYTES bytes)." >&2
                echo "Gunakan Git LFS (Large File Storage) untuk artefak biner besar." >&2
                exit 1
            fi
        done
    done
done

exit 0
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Monorepo Latency Breakdown & Out-Of-Memory di SuperApp Payment Gateway

**Kondisi Awal:**
- **Repository Size**: 68 Gigabyte (5 tahun commit history, ribuan asset image, SDK binaries, build output).
- **Populasi Developer**: 3.200 Engineers.
- **Problem**: 
  - CI/CD build runner kehabisan memori (*OOMKilled*) saat menjalankan checkout step.
  - Waktu `git clone` rata-rata mencapai **42 menit** via koneksi corporate VPN.
  - Server disk usage pada central VCS appliance (GitHub Enterprise Server) mengalami bottleneck I/O tinggi karena kompresi objek real-time saat packfile di-generate.

**Solusi Arsitektural Multi-Fase:**

```
                  ENTERPRISE OPTIMIZATION ARCHITECTURE
                  
[ 68 GB Giant Repo ] 
         |
         +--> 1. History Purge (git-filter-repo) 
         |       - Evict all *.so, *.aar, *.zip (>50MB) -> Export to S3 / OCI Registry
         |       - Result: Base repo shrank to 4.2 GB
         |
         +--> 2. Commit Graph & Bitmap Indices Activation
         |       - git config core.commitGraph true
         |       - git config pack.writeBitmapHashCache true
         |       - Result: DAG traversal time dropped by 91%
         |
         +--> 3. Partial Clone Pattern for CI Runners
                 - git clone --filter=tree:0 --no-checkout <repo>
                 - Result: CI checkout dropped from 42 mins to 14 seconds
```

**Langkah Implementasi:**
1. **Pembersihan Riwayat Masa Lalu**: Menggunakan tool bare-metal engine `git-filter-repo` (menggantikan `git filter-branch` yang *deprecated* dan rawan korupsi data) untuk mengekstrak dan menghapus ekstensi biner raksasa:
   ```bash
   git-filter-repo --strip-blobs-bigger-than 50M
   ```
2. **Implementasi Git LFS**: Semua binary asset yang tersisa dialihkan pointer-nya ke Object Storage (S3-compatible) dengan *pre-push smudge/clean filters*.
3. **Penerapan Treeless Clone pada CI Workers**: Runner Kubernetes dialihkan untuk menarik metadata commit saja secara instan:
   ```bash
   git clone --filter=tree:0 --depth=1 --no-checkout https://github.com/corp/engine-monorepo.git
   git sparse-checkout set --cone services/auth-service
   git checkout
   ```

**Hasil Metrik:**
- Rata-rata cloning time: Turun dari **42 menit** menjadi **14 detik**.
- Bandwidth data transfer per checkout: Menurun **98.2%**.
- Zero OOMKilled errors pada 250.000 job pipeline bulanan.

---

## 9. Trade-offs

| Pendekatan / Strategi | Keuntungan (Pros) | Biaya & Konsekuensi (Cons) | Latency Impact | Rekomendasi Skenario |
| :--- | :--- | :--- | :--- | :--- |
| **Full Clones** | Akses offline absolut; navigasi history instan; tidak memerlukan dependensi server tambahan setelah clone. | Boros bandwidth; clone time sangat lambat pada repo >5GB; membebani storage lokal workstation. | Tinggi saat initial sync; Zero saat local operation. | Repositori standar (<1GB), aplikasi microservices terisolasi. |
| **Partial Clones (`--filter=blob:none`)** | Clone super cepat; pohon direktori lengkap tetap terlihat; blob diunduh secara on-demand saat dibuka. | Terjadi network latency (*roundtrip pause*) saat pertama kali membuka atau mengedit file yang belum di-cache secara lokal. | Sangat rendah saat clone; spike latency minor saat checkout file baru. | Repositori monorepo besar (>5GB) dengan ribuan direktori aktif. |
| **Git Submodules** | Memisahkan kontrol akses repo; versioning antar modul sangat eksplisit berdasarkan pointer SHA commit. | Developer UX buruk (*detached HEAD traps*); command update rekursif sering terlewat; rawan *merge conflict hell* pada pointer file. | Sedang (clone paralel diperlukan). | Dependensi library cross-org dengan update cycle yang jarang. |
| **Monorepo (Single Unified Tree)** | Atomic commit lintas multi-service; zero cross-repo version mismatch; refactoring universal yang mudah ditinjau. | Mengharuskan tooling tambahan (Sparse checkout, Bazel/Turborepo); manajemen hook yang sangat kompleks. | Tinggi pada Git engine tanpa tuning performa internal. | Perusahaan dengan budaya engineering terintegrasi dan standarisasi tooling tinggi. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Kesalahan Fatal: Menggunakan `git filter-branch` untuk Rewriting Skala Besar
- **Gejala**: Proses rewrite history memakan waktu berjam-jam, memori bocor (*leak*), dan sering meninggalkan dangling tag/reference yang tidak konsisten.
- **Penyebab**: `git filter-branch` meluncurkan subshell OS baru untuk setiap commit tunggal di seluruh histori.
- **Solusi**: Gunakan `git-filter-repo` berbasis Python yang beroperasi langsung pada fast-export/fast-import stream.

### 10.2. Disaster Recovery: Restorasi Branch Terhapus Menggunakan Reflog
Jika seorang engineer tidak sengaja mengeksekusi `git branch -D production-release` dan me-reset hard working tree:

```bash
# 1. Cari SHA commit terakhir dari branch yang terhapus via reflog
git reflog show --date=iso

# Output sample:
# e7a401b HEAD@{2024-03-30 10:15:22 +0700}: commit: hotfix: patch memory leak
# 2c19a03 HEAD@{2024-03-30 10:12:00 +0700}: checkout: moving from production-release to main

# 2. Rekonstruksi branch secara instan dari commit hash target
git branch production-release e7a401b

# 3. Verifikasi integritas DAG
git fsck --full
```

### 10.3. Penanganan Objek Rusak (*Corrupt Loose Object*)
- **Gejala**: `error: object file .git/objects/4b/825dc... is empty`, `fatal: loose object ... is corrupt`.
- **Troubleshooting Sequence**:
  ```bash
  # 1. Cari tahu file apa yang ditunjuk oleh hash yang korup
  find .git/objects/ -type f -empty
  
  # 2. Jalankan integrity check untuk mendeteksi missing objects
  git fsck --full
  
  # 3. Ambil object cadangan dari remote mirror tanpa menimpa working directory
  git fetch origin
  
  # 4. Ekstrak objek spesifik langsung dari packfile remote
  git cat-file -t 4b825dc... || git unpack-objects < .git/objects/pack/pack-*.pack
  ```

---

## 11. Best Practices (Production Checklist)

- [ ] **Enforce Signed Commits**: Pasang proteksi branch rule yang menolak unverified commits (`require_signed_commits: true`).
- [ ] **Activate Commit-Graph & Multi-Pack-Index (MIDX)**:
  ```bash
  git config --global core.commitGraph true
  git config --global gc.writeCommitGraph true
  git config --global core.multiPackIndex true
  ```
- [ ] **Large Binary Governance**: Terapkan Git LFS dengan locking API aktif untuk file biner desain (`.psd`, `.blend`) atau model AI/ML (`.onnx`, `.bin`).
- [ ] **Standardized Ignore List**: Blokir kebocoran file OS dan credential di `.gitignore` global (`.DS_Store`, `Thumbs.db`, `.env*`, `*.pem`, `id_rsa`).
- [ ] **Prevent Dangling History on CI**: Selalu jalankan `git fetch --prune --prune-tags` di CI agent untuk mencegah reference pollution.
- [ ] **Automated Repo Maintenance Daemon**: Aktifkan background maintenance bawaan Git:
  ```bash
  git maintenance start
  ```

---

## 12. Hands-on Practice

Buat direktori latihan lokal di path `hands-on/m02/` dan jalankan skenario simulasi low-level berikut.

```
hands-on/m02/
├── 01_internals_lab/
├── 02_signing_verification/
└── 03_monorepo_sparse/
```

### Langkah Praktikum:

```bash
# Inisialisasi Workspace
mkdir -p hands-on/m02 && cd hands-on/m02

# ==============================================================================
# LAB 1: Membangun Commit Murni dari Nol Menggunakan Plumbing Engine
# ==============================================================================
mkdir 01_internals_lab && cd 01_internals_lab
git init

# 1. Tulis konten ke dalam Object Database (Membuat BLOB)
BLOB_SHA=$(echo "Engine Architecture Native Code" | git hash-object -w --stdin)
echo "Blob Created: $BLOB_SHA"

# 2. Masukkan Blob ke dalam Virtual Index Staging (Staging manual)
git update-index --add --cacheinfo 100644 "$BLOB_SHA" bootstrap.go

# 3. Tulis index ke dalam Object Tree (Membuat TREE)
TREE_SHA=$(git write-tree)
echo "Tree Created: $TREE_SHA"

# 4. Buat Commit yang menunjuk Tree tersebut (Membuat COMMIT)
COMMIT_SHA=$(echo "feat: core architecture initial manual commit" | git commit-tree "$TREE_SHA")
echo "Commit Created: $COMMIT_SHA"

# 5. Arahkan pointer branch main ke commit baru tersebut (Membuat REF)
git update-ref refs/heads/main "$COMMIT_SHA"

# Verifikasi via Porcelain standar
git log -p
cd ..

# ==============================================================================
# LAB 2: Setup Cryptographic Signing via SSH Keys
# ==============================================================================
mkdir 02_signing_verification && cd 02_signing_verification
git init

# 1. Generate SSH Key khusus signing
ssh-keygen -t ed25519 -C "deploy-sign@enterprise.local" -f ./id_ed25519_sign -N ""

# 2. Konfigurasi Git untuk menggunakan SSH Signing
git config user.name "Principal Engineer"
git config user.email "principal@enterprise.local"
git config gpg.format ssh
git config user.signingkey "./id_ed25519_sign.pub"
git config commit.gpgsign true

# 3. Buat file & commit tertanda tangan (Signed Commit)
echo "Secure Payload Data" > secure.txt
git add secure.txt
git commit -m "feat(security): implement cryptographically signed transaction payload"

# 4. Validasi verifikasi signature
git log --show-signature -1
cd ..

# ==============================================================================
# LAB 3: Sparse-Checkout Cone Mode pada Repositori Besar
# ==============================================================================
mkdir 03_monorepo_sparse && cd 03_monorepo_sparse
git init

# Simulasi struktur folder monorepo skala besar
mkdir -p apps/web apps/mobile services/payment services/notification libs/shared
touch apps/web/index.ts apps/mobile/App.tsx services/payment/server.go services/notification/main.py libs/shared/util.go
git add .
git commit -m "feat(repo): initialize massive monorepo layout"

# Aktifkan Sparse-Checkout hanya untuk services/payment dan libs/shared
git sparse-checkout init --cone
git sparse-checkout set services/payment libs/shared

# Buktikan bahwa apps/web dan apps/mobile telah di-unmount dari working tree fisik
ls -la
ls -la services/
cd ../..
```

---

## 13. Exercise

### Level Easy: Manual Inspection
1. Pada sebuah repositori kosong, buat file `config.yaml` dan stage file tersebut (`git add config.yaml`).
2. Jangan lakukan commit. Temukan SHA hash dari objek yang terbentuk di dalam staging area menggunakan command `git ls-files --stage`.
3. Tampilkan isi objek tersebut langsung dari database `.git/objects/` menggunakan plumbing tool `git cat-file`.

### Level Medium: Hook Automation
1. Tulis sebuah script `.git/hooks/pre-commit` lokal yang memvalidasi format branch name.
2. Aturan: Nama branch aktif saat commit dilakukan harus mematuhi regex standard enterprise: `^(feature|bugfix|hotfix)\/[A-Z]+-[0-9]+-[a-z0-9-]+$`.
3. Jika developer mencoba melakukan commit di branch yang melanggar (misalnya: `my-test-branch`), commit harus dibatalkan dengan *exit code non-zero* dan pesan error informatif.

### Level Hard: Large-Scale Binary Purge without Third-Party Tools
1. Buat sebuah test repositori dan simulasikan commit histori sebanyak 5 commit berturut-turut.
2. Di commit ke-2, tambahkan file dummy biner raksasa sebesar 20MB (`head -c 20M /dev/urandom > leak.bin`) dan commit file tersebut.
3. Di commit ke-3, hapus file tersebut menggunakan porcelain `git rm leak.bin` lalu commit lagi.
4. Perhatikan bahwa size file `.git` tetap membengkak karena history retains the blob.
5. Tanpa menggunakan tool eksternal `git-filter-repo` atau Python, gunakan command native `git filter-branch` atau low-level packfile manipulation (`git rev-list`, `git pack-redundant`, `git prune`, `git reflog expire`) hingga file `.git` kembali ramping dan SHA hash leak.bin terhapus absolut dari riwayat DAG.

---

## 14. Challenge

### Studi Kasus: "The Zero-Downtime Infrastructure Refactor Disaster"
Sebuah perusahaan e-commerce unicorn mengalami insiden keamanan: Sebuah branch deployment produksi bernama `release-2024-q1` tanpa sengaja di-force-push (`git push --force`) oleh akun service CI yang mengalami *race-condition*. 

**Kondisi Lingkungan:**
- Force-push tersebut menimpa 140 commit produksi baru dengan snapshot lama dari master branch 3 bulan lalu.
- Developer remote dilarang melakukan push manual untuk sementara waktu.
- Git server appliance tidak mengaktifkan branch protection rule saat insiden berlangsung.
- Repositori server hosting memiliki ukuran packfile 120GB dan ratusan pipeline worker yang saling berebut fetching.

**Tugas Anda:**
1. Rancang arsitektur investigasi forensik berbasis command-line untuk memulihkan reference commit state yang hilang di server, dengan asumsi administrator hanya memiliki akses shell read-only ke server remote `.git` bare repository dan akses penuh ke local clone engineer yang sempat melakukan fetch terakhir 1 jam sebelum insiden.
2. Susun strategi *Disaster Recovery Plan (DRP)* teknis step-by-step mencakup:
   - Identifikasi dangling DAG node menggunakan `git fsck`.
   - Isolasi objek dan rekonstruksi state refs tanpa membuat dirty read bagi deployment lain.
   - Perancangan arsitektur keamanan absolut agar insiden serupa secara teknis tidak dapat diulang oleh service account/automation token di masa depan (Branch rules, OIDC token scoping, bypass prevention).

---

## 15. Quiz Evaluasi Pemahaman

### 15.1. Pertanyaan Basic (5 Soal)
1. Apa perbedaan mendasar antara objek **Blob** dan objek **Tree** di level internal Git?
2. Bagaimana Git menghitung penamaan file hash SHA dari sebuah objek loose?
3. Apa fungsi utama berkas biner `.git/index`?
4. Mengapa menjalankan `rm -rf file` lalu `git rm file` berbeda secara operasional dengan `git checkout -- file`?
5. Di mana letak penyimpanan pointer commit untuk branch lokal bernama `staging` di direktori `.git`?

### 15.2. Pertanyaan Intermediate (5 Soal)
1. Apa perbedaan fundamental antara **Lightweight Tag** dan **Annotated Tag** dalam konteks Git DAG?
2. Mengapa Git Packfile memerlukan file pendamping biner berformat `.idx`? Jelaskan algoritma pencariannya!
3. Bagaimana cara kerja parameter `--filter=tree:0` (Treeless clone) dan apa bedanya dengan `--filter=blob:none` (Blobless clone)?
4. Apa yang terjadi secara internal pada pointer `HEAD` dan file `.git/refs/heads/` saat terjadi kondisi *Detached HEAD*?
5. Mengapa teknik kompresi Git LFS menyimpan pointer metadata file di dalam repositori, alih-alih file aslinya? Format data apa yang digunakan pointer tersebut?

### 15.3. Skenario Kasus Produksi (3 Soal)

**Skenario 1**:
Sebuah pipeline GitOps (misalnya ArgoCD) mendadak gagal melakukan sinkronisasi dengan error `fatal: bad object refs/heads/main`. Tim operasional menemukan bahwa disk host Git server sempat mengalami *Full Disk (100% capacity)* saat proses `git gc` berlangsung beberapa jam sebelumnya. Sebagai Senior Platform Engineer, apa diagnosa awal Anda dan bagaimana tahapan isolasi data yang harus dieksekusi?

**Skenario 2**:
Tim Security mendeteksi bahwa developer `A` mempublikasikan commit yang ditandatangani (signed) menggunakan GPG key milik developer `B`. Bagaimana arsitektur verifikasi cryptographic Git dapat dieksploitasi hingga kondisi pemalsuan identitas ini terjadi, dan bagaimana konfigurasi client/server yang benar untuk memitigasinya?

**Skenario 3**:
Sebuah repositori monorepo dengan 10 juta commit mengalami penurunan performa drastis saat menjalankan command branch listing (`git branch -a`) dan merge base traversal (`git merge-base`). Metrik I/O menunjukkan pembacaan disk mencapai ratusan megabyte setiap pemanggilan log. Optimasi file internal apa di direktori `.git/` yang wajib dibuat untuk menghilangkan disk-seek penalty tersebut?

---

## 16. Summary

1. **Content-Addressable Engine**: Git bukan sekadar snapshot diff, melainkan sistem file terdistribusi berbasis *hash key-value storage* di mana integritas data dijamin oleh SHA DAG.
2. **Object Taxonomy**: Seluruh histori Git hanya tersusun atas 4 objek: **Blob** (isi data), **Tree** (direktori & metadata), **Commit** (snapshot log & referensi parent), serta **Tag** (penanda titik rilis).
3. **Plumbing vs. Porcelain**: Perintah porcelain harian (`add`, `commit`, `pull`) hanyalah wrapper di atas plumbing API (`hash-object`, `update-index`, `write-tree`, `commit-tree`).
4. **Optimasi Enterprise**: Skalabilitas repositori ultra-besar bertumpu pada arsitektur modern Git: **Sparse-Checkout Cone Mode**, **Partial Clones**, **Commit-Graph indexing**, dan **Git LFS offloading**.
5. **Integritas Produksi**: Produksi enterprise modern mewajibkan validasi kriptografis penuh (*SSH/GPG commit signing*) serta perlindungan arsitektur commit pipeline melalui *custom server hooks* dan automated hygiene maintenance.