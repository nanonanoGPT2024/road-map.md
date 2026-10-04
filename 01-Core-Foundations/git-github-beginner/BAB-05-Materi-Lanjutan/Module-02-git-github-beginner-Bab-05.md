# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis Internal Storage Engine Git**: Membedah struktur internal `.git` (*plumbing layer*, *object database*, SHA-1/SHA-256 DAG, *packfiles*, *delta compression*, dan *index staging mechanism*).
- **Merancang Strategi Percabangan Skala Enterprise**: Mengevaluasi dan mengimplementasikan model percabangan tingkat lanjut (*Trunk-Based Development* vs. *Scalable GitFlow* / *GitHub Flow*) yang disesuaikan dengan latensi rilis dan kapabilitas CI/CD.
- **Menguasai Mekanika Penggabungan Tingkat Lanjut (*Merge Strategies & Conflict Resolution*)**: Mengonfigurasi dan mengoperasikan strategi *merge* (`ort`, *octopus*, *subtree*, `ours`, `theirs`), serta mengotomatisasi *conflict resolution* menggunakan `git rerere`.
- **Mengoptimalkan Repository Skala Besar (*Monorepo Scalability*)**: Mengimplementasikan *Sparse-Checkout*, *Shallow Clones*, *Partial Clones* (Blobless/Treeless), dan *Git Large File Storage (LFS)* untuk meminimalkan beban I/O jaringan dan disk storage.
- **Membangun Pipeline Tata Kelola & Keamanan Git Berbasis Hook**: Mengembangkan arsitektur validasi statis lokal dan *remote* menggunakan *Git Hooks* (*client-side* & *server-side*) yang terintegrasi dengan penandatanganan kriptografis commit (GPG/SSH).
- **Melakukan Pemulihan Bencana (*Disaster Recovery*)**: Menyelamatkan commit yang hilang, memperbaiki repository yang terkorupsi, serta merestrukturisasi riwayat commit menggunakan `git reflog`, `git fsck`, `git filter-repo`, dan *plumbing commands*.

---

## 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib memiliki:
- Pemahaman solid mengenai siklus dasar Git (`add`, `commit`, `push`, `pull`, `fetch`, `merge`, `rebase`).
- Pengalaman dasar menggunakan Git CLI dan antarmuka GitHub (Pull Requests, Forking, Branch Protection).
- Penguasaan dasar shell scripting (Bash/Zsh) dan environment variable pada sistem operasi Linux/macOS/WSL.
- Terpasang pada lingkungan kerja:
  - Git versi `>= 2.40.0`
  - GnuPG (GPG) atau OpenSSH `>= 8.0` untuk penandatanganan commit.
  - Python `>= 3.9` (dibutuhkan untuk `git-filter-repo`).

---

## 3. Concept & Internal Architecture

Git pada dasarnya bukanlah sekadar Version Control System (VCS); secara arsitektur, Git adalah **Content-Addressable Key-Value Store** yang di atasnya dibangun sistem berkas tervisi (*versioned file system*) berbasis Directed Acyclic Graph (DAG).

```
                      +---------------------------------------+
                      |       USER-FACING PORCELAIN           |
                      | (git add, commit, checkout, branch)   |
                      +---------------------------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |         LOW-LEVEL PLUMBING            |
                      | (hash-object, cat-file, write-tree)   |
                      +---------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                            GIT REPOSITORY STORAGE (.git/)                         |
|                                                                                   |
|  +---------------------------+   +----------------------+   +------------------+  |
|  |       INDEX (STAGE)       |   |       HEAD / REFS    |   |     REFLOG       |  |
|  | Binary cache (.git/index) |   | .git/refs/heads/*    |   | .git/logs/refs/* |  |
|  +---------------------------+   +----------------------+   +------------------+  |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |                          OBJECT STORE (.git/objects)                        |  |
|  |                                                                             |  |
|  |   [BLOB]             [TREE]                    [COMMIT]         [TAG]       |  |
|  | File contents    Directory manifest      Snapshot metadata  Annotated tag   |  |
|  | (Raw payload)    (Perms, type, SHA, name)(Tree SHA, Parent) (Commit, Sig)   |  |
|  |                                                                             |  |
|  |   +---------------------------------------------------------------------+   |  |
|  |   | PACKED STORAGE (.git/objects/pack/)                                 |   |  |
|  |   | .pack (Delta compressed objects) | .idx (Binary search index)       |   |  |
|  |   +---------------------------------------------------------------------+   |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

### 3.1. Anatomi Directory `.git/`
Repository Git dikontrol oleh direktori tersembunyi `.git/`, dengan struktur esensial sebagai berikut:
- **`HEAD`**: File teks berisi referensi simbolik (*symbolic reference*) ke branch yang sedang aktif (misalnya `ref: refs/heads/main`), atau berisi *direct SHA hash* jika dalam kondisi *Detached HEAD*.
- **`index`**: Berkas biner yang menjadi perantara antara *working directory* dan *object store*. Menyimpan *stat cache* (mtime, ctime, inode, file size) untuk deteksi mutasi berkas secara ultra-cepat tanpa perlu membaca konten secara utuh.
- **`objects/`**: Object database. Menyimpan *loose objects* (format direktori `objects/xx/yyy...` di mana `xx` adalah 2 karakter pertama heksadesimal SHA dan selebihnya adalah nama berkas) dan *packfiles* (`objects/pack/`).
- **`refs/`**: Pointer statis ke commit hash:
  - `refs/heads/`: Branch lokal.
  - `refs/remotes/`: Tracking branch remote.
  - `refs/tags/`: Pointer penanda rilis.
- **`logs/`**: Catatan riwayat pergerakan pointer refs (`git reflog`).

### 3.2. Git Object Model (The Big 4)
Setiap entitas dalam Git dikompresi menggunakan Zlib (RFC 1950) dan disimpan berdasarkan kalkulasi SHA-1 (160-bit / 40 hex char) atau SHA-256 (256-bit / 64 hex char):

$$\text{Object Hash} = \text{SHA}\big(\texttt{"<type> <size>\\0<content>"}\big)$$

1. **Blob (*Binary Large Object*)**: Hanya menyimpan data mentah file. Blob **tidak** menyimpan nama file, atribut izin file (permissions), atau timestamp. Jika 10 file berbeda memiliki konten yang 100% identik, Git hanya menyimpan **1 Blob tunggal**.
2. **Tree**: Merepresentasikan direktori sistem berkas. Berisi daftar baris dengan format: `[file-mode] [object-type] [SHA-hash] [filename/dirname]`. Tree dapat merujuk ke Blob (file) atau Tree lainnya (sub-direktori).
3. **Commit**: Mengikat snapshot Tree root ke dalam riwayat lineage. Memuat:
   - Hash dari root `tree`.
   - Nol, satu, atau lebih parent commit hashes (`parent`).
   - Penulis (`author` + timestamp).
   - Pengesah (`committer` + timestamp).
   - Pesan commit (*commit message*).
   - Penandatanganan kriptografis opsional (GPG/SSH signature block).
4. **Annotated Tag**: Objek persisten yang menunjuk langsung ke commit tertentu, menyimpan tagger metadata, timestamp, pesan rilis, dan verifikasi tanda tangan digital.

### 3.3. Loose Objects vs. Packfiles
- **Loose Objects**: Format default saat berkas baru di-stage atau di-commit. Setiap perubahan menyimpan objek terpisah dalam kompresi zlib. Pendekatan ini cepat untuk penulisan, tetapi tidak efisien untuk disk I/O dan storage saat repository membesar.
- **Packfiles (`.pack` & `.idx`)**: Git secara berkala menjalankan *garbage collection* (`git gc` / `git repack`) untuk memadatkan ratusan *loose objects* menjadi single packfile. Git menggunakan algoritma **Sliding Window Delta Compression**:
  - Git mengurutkan berkas berdasarkan kemiripan nama dan ukuran.
  - Menyimpan satu versi utuh (*base object*) dan versi modifikasinya hanya disimpan sebagai selisih (*delta chunks*).
  - Objek terbaru umumnya disimpan secara utuh (*un-delta'd*), sedangkan versi historis disimpan sebagai delta berantai (*reverse delta*), mengoptimalkan kecepatan checkout versi mutakhir.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional / Pemula | Pendekatan Enterprise Modern |
| :--- | :--- | :--- |
| **Pola Kolaborasi** | GitFlow murni dengan *long-lived feature branches*, *release branches*, dan *hotfix branches*. | **Trunk-Based Development (TBD)** dengan *short-lived branches* (< 24 jam), dilindungi oleh *Feature Flags/Toggles*. |
| **Eksekusi Penggabungan** | *Implicit merge* via Web UI, mengabaikan struktur graph riwayat. Mengakibatkan *merge bubbles* tak teratur. | Standarisasi eksplisit: **Squash and Merge** untuk PR fitur (menjaga main branch linear), atau **Semi-Linear Merge** (`ff-only` setelah rebase) untuk traceability audit. |
| **Integritas & Audit** | Identitas berbasis `user.name` & `user.email` polos yang mudah dipalsukan (*spoofable*). | **Cryptographic Commit Signing** (GPG/SSH) yang diwajibkan secara mutlak di branch utama via kebijakan GitHub Branch Protection. |
| **Repositori Masif** | Meng-clone seluruh riwayat secara mendalam (*full deep clone*). Waktu clone bermenit-menit hingga berjam-jam. | **Blobless Clone** (`--filter=blob:none`), **Sparse-Checkout**, dan **Git LFS** untuk aset biner. |
| **Quality Enforcement** | Review manual dan running test lokal secara opsional. | Otomasi terenkapsulasi via **Git Client Hooks** (Husky/Lefthook) dan proteksi immutable via **GitHub Rulesets/Actions**. |

### Justifikasi Arsitektural Enterprise
Pada skala tim rekayasa ratusan engineer, Git bukan sekadar alat pencatat revisi melainkan **dasar dari Supply Chain Security dan Deployment Automation**. Inkonsistensi riwayat Git menimbulkan friksi merge resolution yang mahal, commit palsu membuka celah *social engineering*, dan repository yang bloated melumpuhkan throughput CI/CD pipeline.

---

## 5. How (Workflow Detail)

Berikut adalah siklus hidup produksi yang ketat (*Strict Production Workflow*) yang menerapkan validasi pre-commit, branching linier, penandatanganan kriptografis, dan integrasi upstream:

```
[Local Workspace]                 [Local Git Hooks]             [Remote: GitHub Engine]
       |                                  |                                |
1. Mutasi Berkas                          |                                |
       |                                  |                                |
2. git add (Update Index Cache)           |                                |
       |                                  |                                |
3. git commit -S -m "..."                |                                |
       +--------------------------------->|                                |
       |                           [pre-commit Hook]                       |
       |                           - Linting (ESLint/GolangCI)             |
       |                           - Secret Scan (TruffleHog)              |
       |                           - Static Analysis                       |
       |                                  |                                |
       |                           [commit-msg Hook]                       |
       |                           - Validate Conventional Commits         |
       |                                  |                                |
       |<---------------------------------+ (Lolos Validasi)               |
       |                                                                   |
4. git fetch origin main                                                   |
       |                                                                   |
5. git rebase origin/main (Menjaga riwayat tetap datar/linear)             |
       |                                                                   |
6. git push origin feature/JIRA-1234                                       |
       +------------------------------------------------------------------>|
                                                                           |
                                                                    [Server Guard]
                                                                    - Verify GPG Sig
                                                                    - Branch Ruleset
                                                                    - Trigger CI/CD
```

### Algoritma Resolusi Penggabungan: `ort` vs `recursive`
Git versi 2.33+ menetapkan **`ort`** (*Ostensibly Recursive's Twin*) sebagai default merge engine menggantikan engine lama `recursive`.
- `recursive` mengeksekusi merge ambigu (3-way merge dengan multiple common ancestors / criss-cross merges) secara rekursif dengan menulis *virtual intermediate trees* ke disk. Operasi ini lambat pada repositori besar.
- `ort` didesain ulang dari nol:
  1. Operasi pemrosesan konflik dan pelacakan rename (*rename detection*) dilakukan sepenuhnya di memory (*in-memory*) tanpa disk writes berkala.
  2. Mengimplementasikan deteksi rename $O(N)$ secara heuristik melalui pemetaan kesamaan tree, mengeliminasi kalkulasi kombinatorial yang memicu perlambatan merge.
  3. Memisahkan tahapan kalkulasi konflik dengan modifikasi index, memastikan status staging tidak rusak jika operasi dibatalkan.

---

## 6. Analogy & Diagram ASCII

### Analogi: Git sebagai Sistem Logistik Peti Kemas Maritim
- **Blob**: Barang mentah tanpa identitas di dalam kontainer. Satu kotak baut dengan spesifikasi persis sama tidak diproduksi ulang; hanya ada satu blueprint baut di gudang Git.
- **Tree**: Manifest kargo manifes pelayaran. Berisi daftar: "Kontainer A berisi Berkas X (Blob ID), Rak B berisi Sub-Folder Y (Tree ID)".
- **Commit**: Surat jalan resmi bersandi segel waktu (*timestamp*) dan tanda tangan nahkoda (*signature*), mencatat manifest kargo mana (*Tree*) yang sah pada jam tersebut, dan merujuk ke surat jalan pelayaran sebelumnya (*Parent Commit*).
- **Branch Pointer**: Label tempel berpindah (*sticky note*) bertuliskan "MAIN DOCK". Ia hanya menempel pada commit terakhir.
- **Reflog**: Kamera pengawas CCTV pelabuhan. Label tempel bisa dipindah atau dibuang, tetapi rekaman CCTV mencatat detik demi detik ke mana saja label tersebut pernah ditempelkan.

### Diagram: Anatomi Internal DAG & Objek Terkait
```
 +-----------------------------------------------------------------------------------+
 | COMMIT OBJECT (SHA: a1b2c3d)                                                      |
 | tree: 98f12a4                                                                     |
 | parent: 4e5d6c7                                                                   |
 | author: Principal Architect <lead@corp.internal> 1709280000 +0700                 |
 | gpgsig: -----BEGIN PSSH SIGNATURE----- ...                                        |
 +-----------------------------------------------------------------------------------+
        |
        v
 +-----------------------------------------------------------------------------------+
 | ROOT TREE OBJECT (SHA: 98f12a4)                                                   |
 | 100644 blob e69de29bb2d1d6434b8b29ae775ad8c2e48c5391    README.md                |
 | 040000 tree b0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9    src/                     |
 +-----------------------------------------------------------------------------------+
                                                                 |
                                                                 v
                                 +---------------------------------------------------+
                                 | SUB-TREE OBJECT: src/ (SHA: b0b1c2d)              |
                                 | 100644 blob a5c2d3e...    main.go                 |
                                 | 100644 blob f1a2b3c...    config.yaml             |
                                 +---------------------------------------------------+
                                        |                   |
                                        v                   v
                               +-----------------+  +-----------------+
                               | BLOB OBJECT     |  | BLOB OBJECT     |
                               | (Raw Go code)   |  | (Raw YAML text) |
                               +-----------------+  +-----------------+
```

---

## 7. Simple Example & Practical Example

### Simple Example: Menggunakan Plumbing Commands untuk Membuat Commit Manual
Membuat commit tanpa menyentuh *porcelain command* (`git add` / `git commit`). Membuktikan bahwa Git adalah database murni.

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Inisialisasi bare minimum repo
mkdir git-internals-lab && cd git-internals-lab
git init

# 2. Tulis konten ke dalam object database sebagai Blob (Simulasi staging berkas)
BLOB_SHA=$(echo "fmt.Println('Enterprise Architecture')" | git hash-object -w --stdin)
echo "Blob Generated: ${BLOB_SHA}"

# 3. Masukkan Blob ke dalam Virtual Index Staging
git update-index --add --cacheinfo 100644 "${BLOB_SHA}" core.go

# 4. Tulis Index ke dalam format Tree Object
TREE_SHA=$(git write-tree)
echo "Tree Generated: ${TREE_SHA}"

# 5. Buat Commit Object yang menunjuk ke Tree Object tersebut
COMMIT_SHA=$(echo "feat(core): initial plumbing commit" | git commit-tree "${TREE_SHA}")
echo "Commit Generated: ${COMMIT_SHA}"

# 6. Perbarui referensi branch lokal 'main' ke commit baru
git update-ref refs/heads/main "${COMMIT_SHA}"
git symbolic-ref HEAD refs/heads/main

# 7. Verifikasi bahwa working tree sinkron
git checkout -f main
git log -p
```

### Practical Example: Konfigurasi Produksi Monorepo & Client-Side Hooks
Implementasi manajemen repositori modern: Blobless Partial Clone, Sparse-Checkout, dan Automasi Hooks menggunakan Husky/Lint-Staged & GPG Verification.

#### 1. Setup Sparse-Checkout (Hanya checkout service yang relevan)
```bash
# Clone repository tanpa mendownload blob riwayat (Treeless/Blobless partial clone)
git clone --filter=blob:none --no-checkout git@github.com:enterprise-corp/monorepo.git
cd monorepo

# Inisialisasi Sparse-Checkout menggunakan mode cone (teroptimasi algoritma C)
git sparse-checkout init --cone

# Set hanya direktori microservice yang dikerjakan oleh tim payments
git sparse-checkout set services/payment-gateway libs/common-auth

# Checkout branch main
git checkout main
```

#### 2. Konfigurasi Git Hook: Secret Scanner & Linter (`.husky/pre-commit`)
```bash
#!/usr/bin/env bash
# File: .husky/pre-commit
set -euo pipefail

echo "==> [Hook: Pre-Commit] Menjalankan Analisis Keamanan & Kualitas..."

# 1. Pastikan tidak ada credential/secret bocor ke index staging
if command -v trufflehog &> /dev/null; then
    echo "--> Memeriksa kebocoran credentials (TruffleHog)..."
    trufflehog git file://. --since-commit HEAD --only-verified --fail
else
    echo "WARNING: TruffleHog tidak terpasang. Menjalankan fallback regex scan..."
    if git diff --cached | grep -E -i '(password|secret|api[_-]?key|private[_-]?key)\s*[:=]\s*["\x27][A-Za-z0-9/\+=]{8,}["\x27]'; then
        echo "ERROR: Terdeteksi potensi hardcoded credential pada staged changes!"
        exit 1
    fi
fi

# 2. Validasi format file dan linter hanya pada file yang di-stage
if command -v lint-staged &> /dev/null; then
    echo "--> Menjalankan lint-staged..."
    npx lint-staged
fi

echo "==> [Hook: Pre-Commit] Lolos verifikasi."
```

#### 3. Konfigurasi Git Hook: Validasi Pesan Standar Semantik (`.husky/commit-msg`)
```bash
#!/usr/bin/env bash
# File: .husky/commit-msg
set -euo pipefail

COMMIT_MSG_FILE=$1
COMMIT_MSG=$(cat "$COMMIT_MSG_FILE")

# Standar Conventional Commits: type(scope)!: description
PATTERN="^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-z0-9_-]+\))?!?: .{1,72}$"

if ! [[ "$COMMIT_MSG" =~ $PATTERN ]]; then
    echo "=================================================================="
    echo "ERROR: Format Commit Message Tidak Memenuhi Standar Enterprise!"
    echo "Format wajib: <type>(<scope>): <subject>"
    echo "Contoh: feat(auth): implement oauth2 refresh token rotation"
    echo "Tipe yang diizinkan: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert"
    echo "=================================================================="
    exit 1
fi
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Krisis Kebocoran Kunci Privat TLS & "Monorepo Hang" pada PT FinTech Mega Nusantara
- **Lingkungan**: Monorepo perbankan (~45 GB disk usage, 800+ microservices, 1.200 engineer).
- **Insiden 1**: Seorang developer meng-commit sertifikat TLS wildcard `wildcard.internal.bank.crt` beserta *private key* tanpa enkripsi `server.key` (2048-bit RSA) ke dalam branch `main`. Commit ini langsung ter-mirror ke remote backup dan desentralisasi repository lokal ratusan engineer.
- **Insiden 2**: Waktu eksekusi `git fetch origin` di lingkungan CI/CD melonjak dari 15 detik menjadi 42 menit karena direktori `.git` membengkak akibat masuknya *training dataset model antifraud* berkas `.parquet` sebesar 18 GB yang ter-commit secara berkala.

### Strategi Remediasi Skala Penuh

#### Langkah 1: Karantina & Purging Total Secret Menggunakan `git-filter-repo`
*Mengapa bukan `git filter-branch`?* Karena `git filter-branch` memproses commit satu per satu melalui eksekusi subshell shell script terisolasi, membutuhkan waktu ~14 jam untuk monorepo ini, dan sering meninggalkan metadata residu di packfiles. `git-filter-repo` berbasis Python/C mengoptimalkan DAG filtering di memory dalam beberapa menit.

```bash
# 1. Karantina repository dan hentikan semua akses tulis via GitHub Management API
# 2. Jalankan kloningan bare utuh khusus remediasi (Mirror Clone)
git clone --mirror git@github.com:fintech-mega/monorepo.git monorepo-remediation.git
cd monorepo-remediation.git

# 3. Jalankan git-filter-repo untuk menghapus berkas private key di seluruh riwayat branch & tag
git filter-repo --invert-paths --path "server.key" --path "wildcard.internal.bank.crt"

# 4. Hapus seluruh data biner model machine learning (.parquet) yang salah tempat
git filter-repo --strip-blobs-bigger-than 50M

# 5. Paksa pembersihan object database lokal dan purge reflog
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# 6. Force-push mirror DAG baru yang telah bersih ke upstream
git push --force --mirror git@github.com:fintech-mega/monorepo.git
```

#### Langkah 2: Migrasi Aset Biner ke Git LFS
Mengalihkan berkas data model masa depan langsung ke storage blob eksternal (AWS S3-backed Git LFS server) agar tidak merusak DAG Git:

```bash
# Di workspace developer
cd monorepo
git lfs install

# Daftarkan pattern file binary ke dalam .gitattributes
git lfs track "*.parquet"
git lfs track "*.tar.gz"

# Pastikan .gitattributes ter-commit ke root repo
git add .gitattributes
git commit -m "chore(infra): enforce git-lfs tracking for heavy binary datasets"
git push origin main
```

#### Hasil Remediasi
- Ukuran total direktori `.git` terpangkas dari **45 GB menjadi 2.1 GB**.
- Waktu `git clone` CI runner turun dari **42 menit menjadi 18 detik** (menggunakan *blobless clone* `--filter=blob:none`).
- Sertifikat private key yang bocor secara resmi di-revoke via CA internal, digantikan dengan pasangan kunci baru yang dirotasi otomatis via HashiCorp Vault.

---

## 9. Trade-offs

Setiap keputusan arsitektur Git membawa konsekuensi performa, biaya, dan kemudahan operasional:

```
        Trunk-Based Development (Linear History)
                     ▲
                    / \
                   /   \
  Operasi CI/CD   /     \  Ketahanan Audit &
  Ultra Cepat    /       \ Kepatuhan Regulasi
                /         \
               ◄───────────►
      Merge Commit DAG     Monorepo Blobless
     (Full Traceability)   (Minimal I/O Storage)
```

| Pendekatan / Fitur | Keuntungan (*Pros*) | Kerugian / Biaya (*Cons / Trade-offs*) | Rekomendasi Kasus Penggunaan |
| :--- | :--- | :--- | :--- |
| **Rebase & Fast-Forward (Linear History)** | - Riwayat commit bersih tanpa *noise merge commit*.<br>- Eksekusi `git bisect` sangat akurat dan cepat.<br>- Analisis akar masalah mudah dibaca secara sekuensial. | - Identitas *timestamp* commit asli dapat berubah.<br>- Membutuhkan kedisiplinan dan keahlian rebase dari developer.<br>- Menghilangkan jejak konteks PR jika commit di-squash berlebihan. | Tim dengan delivery frekuensi tinggi (SaaS, continuous deployment), Trunk-Based Development. |
| **Merge Commit DAG (Non-Fast-Forward)** | - Mempertahankan konteks historis branch secara utuh.<br>- Audit trail mencatat dengan tepat kapan fitur disatukan.<br>- Memudahkan *revert* keseluruhan fitur via 1 commit. | - Graph menjadi sangat rumit (*railway topology* yang kusut).<br>- Melipatgandakan *noise* di audit logs.<br>- Meningkatkan potensi *merge conflicts* berulang saat sync. | Sistem perbankan legacy, software terdistribusi dengan long-term support (LTS), audit regulasi kaku. |
| **Git LFS** | - Repository inti tetap ramping.<br>- Mengurangi waktu clone secara signifikan. | - Bergantung pada server penyimpanan objek tambahan.<br>- Pengelolaan kuota bandwidth mahal.<br>- Operasi checkout offline terganggu jika blob belum ditarik. | Repositori dengan game assets, dataset AI/ML, build tools binaries, PDF templates. |
| **Partial Clones (`--filter=blob:none`)** | - Download awal instan.<br>- Hemat kapasitas penyimpanan lokal. | - Latensi jaringan muncul sewaktu-waktu saat mengeksekusi perintah yang memerlukan akses file historis (`git log -p`, `git diff`). | CI/CD build agents, engineer yang bekerja di repositori berskala Terabyte. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Insiden: Kehilangan Commit Berharga Akibat `git reset --hard` yang Keliru
- **Gejala**: Developer tidak sengaja menjalankan `git reset --hard HEAD~5` atau `git reset --hard origin/main` pada branch lokal sebelum melakukan push, menghapus pekerjaan beberapa hari.
- **Troubleshooting**:

```bash
# 1. Buka catatan riwayat mutasi pointer internal
git reflog

# Output akan menampilkan daftar transaksi:
# 7c4a1b0 HEAD@{0}: reset: moving to origin/main
# e8f92a1 HEAD@{1}: commit: feat(billing): add stripe webhook handler  <-- COMMIT YANG HILANG!

# 2. Buat branch recovery langsung dari pointer SHA commit sebelum insiden reset
git branch recovery-billing-worker e8f92a1

# 3. Verifikasi file sudah kembali sepenuhnya
git checkout recovery-billing-worker
```

### 10.2. Insiden: Detached HEAD State Setelah Eksplorasi Tag/SHA
- **Gejala**: Developer checkout langsung ke tag atau commit SHA (`git checkout v1.2.0`), melakukan perbaikan bug, dan membuat commit. Setelah berpindah kembali ke `main`, seluruh commit perbaikan bug tersebut "hilang".
- **Troubleshooting**: Commit tidak hilang; commit tersebut berada dalam status *Orphaned Object*.

```bash
# 1. Temukan commit hash perbaikan saat berada di detached state
git reflog show HEAD

# 2. Buat branch baru dari titik commit terputus tersebut
git branch fix-bug-v1.2.0-patch <commit-sha-dari-reflog>

# 3. Gabungkan kembali ke aliran kerja utama
git checkout main
git merge fix-bug-v1.2.0-patch
```

### 10.3. Insiden: Perulangan Konflik Merge yang Melelahkan
- **Gejala**: Developer melakukan rebase berkala terhadap upstream branch yang aktif dan harus menyelesaikan merge conflict yang sama secara manual berulang-ulang.
- **Troubleshooting**: Aktifkan mesin **Reuse Recorded Resolution (`rerere`)**:

```bash
# Aktifkan rerere secara global pada mesin developer
git config --global rerere.enabled true

# (Opsional) Izinkan Git secara otomatis melakukan staging pada rekaman resolusi yang cocok
git config --global rerere.autoupdate true
```
*Mekanisme internal*: Git menyimpan hash *pre-image* (kondisi konflik) dan *post-image* (resolusi yang Anda buat) di direktori `.git/rr-cache/`. Ketika pola konflik identik muncul kembali, Git langsung mengaplikasikan solusinya tanpa campur tangan manusia.

---

## 11. Best Practices (Production Checklist)

Berikut adalah kriteria siap-produksi (*Production Checklist*) tingkat enterprise:

- [ ] **Linear Commit Protocol**: Mengonfigurasi repository upstream hanya menerima strategi *Squash and Merge* atau *Rebase and Merge* (Blokir merge commit non-fast-forward liar di `main`).
- [ ] **Cryptographic Signing (GPG/SSH)**: 
  - Seluruh engineer wajib menandatangani commit menggunakan kunci SSH atau GPG (`git config --global commit.gpgsign true`).
  - GitHub Branch Protection wajib mencentang: **Require signed commits**.
- [ ] **Penyaringan Berkas Terintegrasi (`.gitignore`)**:
  - Wajib menolak `.env*`, `*.pem`, `*.key`, binary output, dan folder dependency (`node_modules/`, `vendor/`, `target/`).
- [ ] **GitHub Rulesets Enforcement**:
  - Blokir `git push --force` ke branch terlindungi (`main`, `production`, `release/*`).
  - Wajibkan minimal 2 approver *Code Review* dari anggota tim yang didefinisikan pada file `CODEOWNERS`.
  - Wajib lolos verifikasi status checks CI (Build, Unit Tests, Static Code Analysis, Secret Detection).
- [ ] **Git Configuration Tuning**:
  - Konfigurasi Core Engine:
    ```bash
    git config --global core.compression 9
    git config --global merge.conflictstyle zdiff3
    git config --global pull.rebase true
    git config --global init.defaultBranch main
    ```
  - *Catatan*: `zdiff3` menampilkan *common ancestor block* asli selain blok `OURS` dan `THEIRS`, memudahkan penelusuran akar logika yang berubah secara akurat.

---

## 12. Hands-on Practice

Simpan seluruh hasil latihan ini pada sub-direktori: `hands-on/m02/`

### Skenario Praktikum:
Anda ditugaskan mendirikan repository terproteksi dengan signing commit, menyimulasikan insiden data terkorupsi, dan melakukan pemulihan manual berbasis DAG.

#### Langkah 1: Inisialisasi Lingkungan & Generate SSH Signing Key
```bash
mkdir -p hands-on/m02/production-vault && cd hands-on/m02/production-vault
git init

# Buat pasangan kunci SSH khusus penandatanganan commit
ssh-keygen -t ed25519 -C "architect@corp.local" -f ./id_signing -N ""

# Konfigurasi penandatanganan Git berbasis SSH lokal
git config user.name "Enterprise Architect"
git config user.email "architect@corp.local"
git config gpg.format ssh
git config user.signingkey "./id_signing.pub"
git config commit.gpgsign true
```

#### Langkah 2: Buat Commit Bertanda Tangan dan Validasi
```bash
echo "# Core Security Service" > README.md
git add README.md
git commit -m "feat: initialize enterprise repository"

# Verifikasi tanda tangan kriptografis pada log
git log --show-signature -n 1
```

#### Langkah 3: Simulasi Insiden Kerusakan Manual pada `.git/objects`
```bash
# 1. Buat commit kedua dengan data penting
echo "CRITICAL_SYSTEM_STATE=OPERATIONAL" > system.state
git add system.state
git commit -m "feat(system): record critical state"

# 2. Dapatkan commit SHA terakhir
TARGET_SHA=$(git rev-parse HEAD)
echo "Target Commit: ${TARGET_SHA}"

# 3. Rusak file object secara sengaja di storage backend
OBJ_DIR=".git/objects/${TARGET_SHA:0:2}"
OBJ_FILE="${OBJ_DIR}/${TARGET_SHA:2}"
echo "Corrupting object: ${OBJ_FILE}"
echo "CORRUPTED_ZERO_BYTE_DATA" > "${OBJ_FILE}"

# 4. Jalankan integritas audit menggunakan git fsck
git fsck --full || true
# Git akan melaporkan error: 'error: inflate: data stream error' atau 'sha1 mismatch'
```

#### Langkah 4: Pemulihan Bencana (*Disaster Recovery Operation*)
```bash
# 1. Isolasi commit yang rusak
# Berkas working directory system.state masih ada di disk
# Buat kembali blob object yang benar secara manual
NEW_BLOB=$(git hash-object -w system.state)

# 2. Periksa tree commit induk
PARENT_SHA=$(git rev-parse HEAD~1)
PARENT_TREE=$(git rev-parse ${PARENT_SHA}^{tree})

# 3. Rekonstruksi index manual
git read-tree ${PARENT_TREE}
git update-index --add --cacheinfo 100644 "${NEW_BLOB}" system.state
RECOVERED_TREE=$(git write-tree)

# 4. Buat commit baru menggantikan commit yang rusak dengan metadata asli
RECOVERED_COMMIT=$(echo "feat(system): record critical state (RECOVERED)" | git commit-tree "${RECOVERED_TREE}" -p "${PARENT_SHA}")

# 5. Pasang kembali branch main ke commit hasil pemulihan
git update-ref refs/heads/main "${RECOVERED_COMMIT}"

# 6. Audit ulang kesehatan repositori
git fsck --full
echo "Audit Sukses: Sistem kembali operasional dan konsisten!"
```

---

## 13. Exercises

### Level Easy
1. Ubah konfigurasi Git Anda agar menggunakan tampilan format visualisasi log satu baris yang kaya metadata (decorations, hash, author date, commit message) menggunakan perintah alias `git lg`.
2. Aktifkan konfigurasi `merge.conflictstyle zdiff3` dan jelaskan secara singkat perbedaan output yang dihasilkan dibanding conflict-style default saat terjadi merge conflict.

### Level Medium
1. Simulasikan skenario *Criss-Cross Merge* sederhana:
   - Buat commit awal `C0` pada branch `main`.
   - Buat branch `feature-A` dan `feature-B` dari `C0`.
   - Tambahkan commit `A1` pada `feature-A` dan `B1` pada `feature-B`.
   - Merge `feature-B` ke dalam `feature-A` (Commit `M1`).
   - Merge `feature-A` ke dalam `feature-B` (Commit `M2`).
   - Analisis bagaimana algoritma default `ort` menentukan *virtual common ancestor* saat `feature-A` dan `feature-B` digabungkan kembali. Tuliskan log pembuktiannya.
2. Tulis sebuah script Git Server-Side Hook `pre-receive` yang memvalidasi bahwa setiap commit baru yang di-push ke server **wajib** memiliki tanda tangan GPG/SSH yang valid. Tolak push jika ada satu commit saja yang unsigned.

### Level Hard
1. Tulis skrip otomatisasi pembersihan repository yang mengekstraksi seluruh commit dalam interval 6 bulan terakhir yang memodifikasi berkas dengan ekstensi `.log` atau `.tmp`. Skrip harus:
   - Menggunakan `git-filter-repo` atau custom plumbing loop (`rev-list`, `mktree`, `commit-tree`).
   - Memastikan tidak ada *committer timestamp* atau *author name* yang berubah selain penghapusan blob target.
   - Mengatur ulang struktur DAG secara bersih tanpa meninggalkan loose references pada `.git/refs/original/`.

---

## 14. Challenge

### Studi Kasus Produksi Kompleks (The Silent Corruption & Leak Challenge)

**Latar Belakang Kasus**:
Perusahaan perbankan digital tempat Anda bekerja mengalami insiden keamanan ganda di repositori pembayaran utama (`payment-core`):
1. Sebuah berkas kredensial produksi `service-account.json` tanpa sengaja di-commit 3 bulan yang lalu pada commit `8a4f91e`, dan sejak saat itu telah ada lebih dari **4.500 commit**, **120 merge points**, serta **15 tag rilis semantik** (`v2.1.0` s/d `v2.4.5`) yang bertumpuk di atas riwayat tersebut.
2. Pada saat yang sama, seorang teknisi infrastruktur secara tidak sengaja mematikan mesin virtual CI saat operasi `git gc --aggressive` berjalan di storage server mirror, menyebabkan **2 loose objects tree** terkorupsi dengan status zero-byte. Kondisi ini mengakibatkan kegagalan seluruh proses deployment ke staging (*Fatal: bad tree object*).

**Tantangan Arsitektur**:
Rancang dan eksekusi dokumen arsitektur pemulihan (*Disaster Recovery Protocol*) yang merinci:
1. **Langkah Isolasi**: Bagaimana Anda membekukan operasional tanpa memblokir seluruh 200 engineer agar tidak menambah kerusakan data baru.
2. **Rekonstruksi Objek Terkorupsi**: Mekanisme mendeteksi SHA pasti dari tree object yang rusak dan merekonstruksinya dari cache lokal milik workstation engineer lain tanpa merusak linearitas DAG.
3. **Penyuntingan Riwayat Non-Destruktif**: Bagaimana Anda melenyapkan `service-account.json` dari commit `8a4f91e` hingga commit HEAD terbaru secara mutlak, **sambil mempertahankan penanggalan rilis tag yang sudah ada**, serta mendistribusikan ulang DAG baru ke seluruh mesin engineer tanpa memicu kepanikan conflict-storm saat mereka melakukan `git pull`.

*Kriteria Keberhasilan Tantangan*:
Dokumentasi diserahkan dalam bentuk SOP teknis komprehensif berisi urutan perintah CLI teruji, analisis integritas matematis DAG, mitigasi downtime, serta strategi rotasi credential downstream.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. **Objek Git apa yang bertugas menyimpan nama berkas (*file name*) dan izin eksekusi (*file permissions*)?**
   - A. Blob Object
   - B. Tree Object
   - C. Commit Object
   - D. Tag Object
   *Kunci Jawaban*: **B**. Blob hanya menyimpan payload data mentah. Nama dan mode berkas diikat pada Tree Object.

2. **Karakteristik utama dari penyimpanan Content-Addressable adalah...**
   - A. Berkas diidentifikasi berdasarkan alamat path direktori di hard drive.
   - B. Berkas diidentifikasi berdasarkan nomor urut sekuensial commit (incrementing ID).
   - C. Berkas diidentifikasi secara unik berdasarkan kalkulasi hash kriptografis dari isinya.
   - D. Berkas dienkripsi dengan symmetric cipher menggunakan nama pengguna sebagai kunci.
   *Kunci Jawaban*: **C**. Pengalamatan berbasis konten menghitung checksum (SHA-1/256) langsung dari muatan berkas.

3. **Apa fungsi mendasar dari berkas binary `.git/index`?**
   - A. Menyimpan konfigurasi remote URL.
   - B. Sebagai staging area in-memory/cache yang memetakan status working directory dengan object store.
   - C. Menyimpan arsip rollback jika commit di-revert.
   - D. Mencatat log login developer yang mengakses repositori.
   *Kunci Jawaban*: **B**. Index berfungsi sebagai jembatan *stat-cache* antara working tree dan commit snapshot berikutnya.

4. **Kondisi 'Detached HEAD' pada repositori Git merepresentasikan...**
   - A. Git repository mengalami korupsi fatal pada hard drive.
   - B. HEAD merujuk secara langsung ke commit hash tertentu, bukan ke pointer branch simbolik.
   - C. Branch lokal tidak memiliki upstream branch di remote GitHub.
   - D. Koneksi SSH ke remote GitHub terputus sewaktu push.
   *Kunci Jawaban*: **B**. Detached HEAD berarti `HEAD` berisi commit SHA langsung, bukan `refs/heads/<branch>`.

5. **Perintah Git manakah yang merupakan Plumbing Command (low-level)?**
   - A. `git commit`
   - B. `git status`
   - C. `git hash-object`
   - D. `git checkout`
   *Kunci Jawaban*: **C**. `hash-object` adalah plumbing command yang langsung berinteraksi dengan object database.

---

### Bagian 2: Intermediate (5 Pertanyaan)
6. **Mengapa algoritma merge engine `ort` secara drastis lebih cepat dibandingkan `recursive` pada monorepo skala masif?**
   - A. `ort` mengabaikan pengecekan rename berkas (*rename detection disabled*).
   - B. `ort` melakukan kalkulasi merge dan deteksi rename seluruhnya di memory tanpa menulis intermediate trees ke disk.
   - C. `ort` ditulis menggunakan assembly language khusus instruksi CPU AVX-512.
   - D. `ort` hanya mendukung algoritma fast-forward merge dan menolak three-way merge.
   *Kunci Jawaban*: **B**. Pendekatan in-memory conflict calculation dan heuristik rename detection memangkas disk I/O bottleneck secara masif.

7. **Bagaimana Git LFS (*Large File Storage*) mencegah direktori `.git` membengkak saat menangani berkas berukuran Gigabyte?**
   - A. Memampatkan berkas biner menggunakan kompresi 7-Zip LZMA level 9.
   - B. Mengonversi data biner menjadi base64 text stream di dalam commit blob.
   - C. Mengganti berkas asli di repositori Git dengan pointer text file berukuran ~130 byte yang merujuk ke server LFS eksternal.
   - D. Menghapus otomatis riwayat berkas biner setiap kali branch dimerge.
   *Kunci Jawaban*: **C**. Git hanya menyimpan metadata pointer file kecil; payload raksasa dialihkan ke dedicated LFS store.

8. **Apa perbedaan fungsional utama antara flag `--filter=blob:none` (blobless clone) dan `--filter=tree:0` (treeless clone)?**
   - A. Blobless clone mendownload semua tree tetapi melewatkan blob historis; Treeless clone hanya mendownload commit tanpa tree maupun blob hingga berkas diakses.
   - B. Blobless clone menghapus file gambar; Treeless clone menghapus sub-folder.
   - C. Treeless clone hanya berlaku untuk SVN bridge.
   - D. Blobless clone tidak mengizinkan operasi checkout branch lokal.
   *Kunci Jawaban*: **A**. Blobless clone memungkinkan eksekusi perintah struktural (`git log`, `git checkout`) berjalan cepat secara lokal karena struktur direktori (Tree) lengkap, sedangkan Treeless clone menunda download Tree hingga benar-benar dibutuhkan.

9. **Jika sebuah commit di-amend menggunakan `git commit --amend`, apa yang sebenarnya terjadi pada DAG Git di level storage engine?**
   - A. Git memodifikasi commit object yang lama di sektor disk yang sama.
   - B. Git membuat Commit Object baru dengan hash yang berbeda, sementara Commit Object lama menjadi orphaned/unreferenced.
   - C. Git hanya memperbarui pesan teks di file metadata log tanpa mengubah hash SHA.
   - D. Git membatalkan commit sebelumnya lalu menjalankan git stash secara otomatis.
   *Kunci Jawaban*: **B**. Karakteristik Git objects adalah *immutable* (kekal). Modifikasi data selalu melahirkan objek baru dengan SHA baru; objek lama tetap ada hingga dipangkas oleh `git gc`.

10. **Apa kegunaan utama dari mekanisme `git rerere` dalam flow kolaborasi berbasis Rebase?**
    - A. Mempercepat proses download blob saat cloning.
    - B. Merekam pola penyelesaian konflik manual dan mengaplikasikannya secara otomatis ketika pola konflik identik terdeteksi di masa depan.
    - C. Menolak otomatis PR yang tidak memiliki unit test.
    - D. Mengubah format enkripsi GPG menjadi SSH secara seamless.
    *Kunci Jawaban*: **B**. Rerere singkatan dari *Reuse Recorded Resolution*, mengeliminasi friksi penyelesaian konflik berulang pada cabang yang sering di-rebase.

---

### Bagian 3: Production Scenarios (3 Skenario Kasus)
11. **Skenario A**: Tim QA menemukan bug kritis di production yang diperkenalkan oleh commit 3 minggu lalu. Repository memiliki lebih dari 1.000 commit baru sejak saat itu dengan struktur DAG yang kompleks akibat berbagai merge. Anda diminta mencari commit tunggal mana yang pertama kali menyebabkan bug terjadi. Perintah strategi paling optimal dan deterministik adalah...
    - A. Membaca `git log -p` dari commit terbaru secara manual satu demi satu.
    - B. Menggunakan `git bisect` terotomatisasi dengan menyuplai script testing non-interaktif (`git bisect run ./test-script.sh`).
    - C. Menggunakan `git revert HEAD~100..HEAD` sekaligus.
    - D. Menjalankan `git checkout` secara acak hingga menemukan commit yang hijau.
    *Kunci Jawaban*: **B**. `git bisect run` menerapkan algoritma pencarian biner ($O(\log N)$) yang mengisolasi commit regresi secara otomatis dan objektif tanpa human-error.

12. **Skenario B**: Seorang engineer secara tidak sengaja menjalankan `git push origin feature-branch --force` dan menimpa pekerjaan 3 engineer lain yang belum sempat ditarik ke lokal mereka. Untungnya, Anda memiliki akses administratif ke GitHub Organization. Tindakan awal paling presisi untuk mengembalikan branch remote tersebut ke posisi sebelum force-push adalah...
    - A. Menghapus remote repository dan membuat baru dari backup kemarin malam.
    - B. Memeriksa GitHub Audit Log / Push Events API untuk menemukan SHA commit HEAD sesaat sebelum transaksi force-push terjadi, lalu menjalankan `git push origin <commit-sha>:refs/heads/feature-branch`.
    - C. Meminta seluruh engineer menjalankan `git pull --rebase` secara bersamaan.
    - D. Menjalankan `git filter-repo` untuk membersihkan riwayat branch.
    *Kunci Jawaban*: **B**. Push Events API / Audit Log mencatat pointer hash sebelum status update (`before` SHA). Mengarahkan ref remote kembali ke SHA tersebut mengembalikan status branch secara instan tanpa data loss.

13. **Skenario C**: Pada pipeline CI/CD berbasis Kubernetes, proses build Docker image memakan waktu 20 menit hanya untuk fase `git clone` repositori backend enterprise (ukuran repo `.git`: 35 GB). Tim tidak membutuhkan riwayat komit lampau saat fase build, hanya source code mutakhir dari branch target. Konfigurasi clone paling efisien untuk memangkas waktu build hingga di bawah 10 detik adalah...
    - A. `git clone --bare <url>`
    - B. `git clone --depth=1 --single-branch --branch <target-branch> <url>`
    - C. `git clone --mirror <url>`
    - D. `git clone --filter=tree:0 <url>`
    *Kunci Jawaban*: **B**. Kombinasi `--depth=1` (shallow clone, membuang seluruh riwayat) dan `--single-branch` hanya mengunduh data commit snapshot terakhir pada branch terkait, menghemat transfer data jaringan hingga >95%.

---

## 16. Summary

1. **Git adalah Content-Addressable Database**: Semua objek (Blob, Tree, Commit, Tag) bersifat immutable, terkompresi secara kriptografis melalui identifikasi hash (SHA-1/SHA-256), dan dihubungkan dalam topologi Directed Acyclic Graph (DAG).
2. **Kekuatan Internal Terletak pada Indireksi Pointer**: Branch dan Tag hanyalah berkas teks penunjuk (*reference pointers*) berukuran sangat kecil yang menunjuk ke Commit Object hash. Manipulasi riwayat Git tidak memodifikasi data secara mutasi in-place, melainkan melahirkan objek baru dan memindahkan pointer ref.
3. **Optimasi Skala Enterprise Menuntut Pengendalian I/O**: Repositori berskala masif harus diatur secara ketat dengan mengisolasi aset biner (Git LFS), menerapkan Blobless Clone (`--filter=blob:none`), Sparse-Checkout, serta mengandalkan merge engine modern seperti `ort`.
4. **Keamanan & Tata Kelola Bersifat Berlapis**: Kepatuhan arsitektur produksi wajib ditegakkan di dua sisi: sisi lokal menggunakan *Git Client Hooks* (Husky/Lint-Staged/Secret Scanners) dan sisi hulu (*remote*) menggunakan GitHub Rulesets yang memblokir rewrite riwayat, mewajibkan penandatanganan kriptografis (GPG/SSH), serta menuntut integrasi CI/CD statis yang ketat.
5. **Tidak Ada Data yang Benar-Benar Hilang Sebelum Garbage Collection**: Segala perubahan pointer tersimpan di `git reflog`. Selama sebuah objek belum dipangkas oleh `git gc`, objek tersebut selalu dapat direkonstruksi kembali melalui audit konsistensi `git fsck` dan plumbing commands.