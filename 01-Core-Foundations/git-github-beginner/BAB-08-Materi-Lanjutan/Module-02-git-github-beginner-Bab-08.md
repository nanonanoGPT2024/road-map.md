# Kurikulum Enterprise: Git & GitHub Foundations
## BAB 08: Materi Lanjutan
### Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- **Menganalisis Internal Storage Engine Git (Bloom's Level 4 - Analyze)**: Membedah struktur penyimpanan berkas Git di level *filesystem* (`.git/objects`, *loose objects*, *packfiles*, `.idx`, serta algoritma kompresi zlib).
- **Mengevaluasi Topologi Directed Acyclic Graph (DAG) (Bloom's Level 5 - Evaluate)**: Mendiagnosis state repository, mendeteksi percabangan anomali (*dangling commits*), dan merekonstruksi riwayat riil menggunakan `git reflog` serta `git fsck`.
- **Mengimplementasikan Arsitektur Git Skala Monorepo & Enterprise (Bloom's Level 3 - Apply)**: Mengkonfigurasi *Git Worktrees*, *Sparse-Checkout*, dan *Blobless/Treeless Clones* untuk mengoptimalkan throughput pada repository multi-gigabyte.
- **Mengarsiteki Pipeline Tata Kelola & Proteksi Repository (Bloom's Level 6 - Create)**: Membangun automasi *pre-commit/pre-receive hooks*, enkripsi artefak rahasia, implementasi penandatanganan commit berbasis kriptografi (GPG/SSH), serta mengintegrasikan *Merge Queues* pada lingkungan produksi.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta diwajibkan telah menguasai:
- **Git Basic-to-Intermediate Workflow**: Staging lifecycle (`working directory`, `index`, `HEAD`), branching, merging, dan basic merge conflict resolution.
- **Sistem Operasi & Shell Scripting**: Pemahaman POSIX shell (Bash/Zsh), manipulasi filesystem Linux, symbolic links, file permissions (`chmod`, `umask`), dan pipeline I/O (`stdin`, `stdout`, `stderr`, piping).
- **Dasar Kriptografi Terapan**: Konsep fungsi hash kriptografis (*SHA-1*, *SHA-256*), algoritma enkripsi asimetris (*public/private keys* RSA/Ed25519) untuk otentikasi SSH dan verifikasi GPG.

---

### 3. Concept & Internal Architecture

Git pada dasarnya bukanlah sekadar *Version Control System* (VCS) berbasis delta-per-line tradisional (seperti SVN atau CVS), melainkan sebuah **Content-Addressable Key-Value Data Store** yang dilapisi oleh antarmuka sistem kontrol versi berbasis grafik terarah tanpa siklus (*Directed Acyclic Graph* / DAG).

```
                      +---------------------------------------+
                      |   Git Content-Addressable Storage    |
                      +---------------------------------------+
                                          |
        +------------------+--------------+-------------+------------------+
        |                  |                            |                  |
        v                  v                            v                  v
+---------------+  +---------------+            +---------------+  +---------------+
|     BLOB      |  |     TREE      |            |    COMMIT     |  |  TAG (Annot)  |
+---------------+  +---------------+            +---------------+  +---------------+
| Raw File Data |  | Directory     |            | Tree SHA-1    |  | Object SHA-1  |
| No Metadata   |  | Permissions   |            | Parent SHA-1  |  | Tag Type      |
| No File Name  |  | Filenames     |            | Author/Time   |  | Tag Name      |
| Zlib deflate  |  | Pointers      |            | Committer     |  | Tagger / Msg  |
+---------------+  +---------------+            +---------------+  +---------------+
```

#### 3.1. Struktur Objek Immutable Git
Semua entitas data dalam Git disimpan dalam direktori `.git/objects/` sebagai objek yang di-hash menggunakan SHA-1 (160-bit, 40 karakter heksadesimal) atau SHA-256 pada repository modern. Dua karakter pertama menjadi nama sub-direktori, dan 38 karakter berikutnya menjadi nama file.

Terdapat empat tipe objek fundamental:
1. **Blob (*Binary Large Object*)**: Menyimpan isi konten file murni. Blob **tidak** menyimpan nama file, atribut permission, timestamp, atau relasi direktori. Dua file identik di lokasi berbeda hanya akan menghasilkan satu blob.
2. **Tree**: Merepresentasikan direktori. Berisi daftar pointer berformat biner yang memetakan file modes (`100644` untuk standard file, `100755` untuk executable, `040000` untuk sub-tree), nama file/direktori, dan hash SHA dari blob atau tree turunan.
3. **Commit**: Node immutable dalam DAG yang mengikat satu Tree root level (snapshot state proyek), satu atau lebih Parent Commit SHA (kecuali *root commit*), metadata Author, Committer, timestamp, dan commit message.
4. **Annotated Tag**: Pointer permanen yang menunjuk langsung ke commit tertentu, menyimpan metadata pembuat tag, timestamp, dan signature GPG.

#### 3.2. Lifecycle Format Penyimpanan: Loose Objects vs Packfiles
- **Loose Objects**: Saat developer melakukan modifikasi dan menjalankan `git add`, Git mengompresi payload secara individual menggunakan zlib format deflate dengan header `[tipe objek] [ukuran payload dalam bytes]\0`. Jika terjadi ratusan perubahan file kecil, sistem I/O disk akan terbebani oleh jutaan file individual kecil (*inode exhaustion*).
- **Packfiles (`.pack`) & Indexes (`.idx`)**: Untuk efisiensi ruang dan jaringan, Git mengonsolidasi loose objects ke dalam format biner terpadu via proses *garbage collection* (`git gc`). Packfile menggunakan teknik **Delta Compression**: alih-alih menyimpan full-snapshot untuk setiap revisi file, Git menyimpan satu versi utuh (biasanya versi terbaru untuk kecepatan akses) dan menyimpan selisih diferensial (*reverse-delta chain*) untuk versi-versi pendahulunya. File `.idx` memetakan hash SHA secara direct-offset ke dalam file `.pack` binary dengan kompleksitas pencarian $O(\log N)$.

#### 3.3. Git Plumbing vs Porcelain Architecture
Arsitektur perintah Git dipisahkan secara tegas:
- **Porcelain Commands**: Antarmuka tingkat tinggi yang digunakan oleh end-user (`git checkout`, `git commit`, `git pull`, `git merge`).
- **Plumbing Commands**: Primitif tingkat rendah UNIX-friendly yang berinteraksi langsung dengan database Git (`git hash-object`, `git cat-file`, `git mktree`, `git write-tree`, `git commit-tree`, `git update-ref`). Seluruh operasi Porcelain selalu dikonversi menjadi urutan eksekusi perintah Plumbing di latar belakang.

---

### 4. Why & What

| Dimensi | Pendekatan Naif / Tradisional | Pendekatan Enterprise Git Architecture | Dampak Rekayasa & Bisnis |
| :--- | :--- | :--- | :--- |
| **Penyimpanan Kode** | Menyimpan delta teks baris per baris secara incremental terpusat (SVN/Perforce). | Snapshot berbasis Content-Addressable Cryptographic DAG terdistribusi. | Integritas data matematis terjamin; korupsi bit terdeteksi instan via hash collision checks. |
| **Kinerja Skala Besar** | Full-clone repository monorepo multi-GB membebani disk dan transfer bandwidth. | Blobless/Treeless partial clone dipadukan dengan *Sparse-Checkout* dan *Git Worktrees*. | Reduksi waktu checkout dari >45 menit menjadi <30 detik; penghematan storage lokal hingga 90%. |
| **Pemulihan Bencana** | Panik saat *accidental hard reset*; ketergantungan pada backup server terpusat. | Pemanfaatan *Local Reference Logs* (`reflog`) dan *Packfile Data Excavation*. | *Zero data loss* pada layer workstation pengembang; insiden `reset --hard` teratasi dalam <5 menit. |
| **Kualitas & Kepatuhan** | Pengecekan styling dan keamanan manual pada tahap code review via Pull Request. | Deterministic automated Client/Server-side Hooks, Signed Commits, dan Branch Guardrails. | Shift-left security terwujud; celah kebocoran secret credential di-block sebelum lolos ke staging. |

---

### 5. How (Workflow Detail)

#### 5.1. Alur Parsing Internal Objek Menggunakan Plumbing
Ketika Anda mengeksekusi `git add main.py` lalu `git commit -m "feat: init"`:
1. Git membaca `main.py`, menghitung format header: `blob 24\0` + isi payload.
2. Git menghitung hash SHA-1 dari string tersebut, mengompresnya dengan zlib, dan menuliskannya ke `.git/objects/XX/YYYY...`.
3. Git memperbarui `.git/index` (staging binary index) untuk memetakan path file `main.py` ke SHA-1 blob tersebut beserta metadata inode OS.
4. Saat commit, Git mengeksekusi `git write-tree` untuk membekukan index menjadi objek Tree.
5. Git mengeksekusi `git commit-tree [tree-sha] -m "message"`, menciptakan objek Commit.
6. Git mengarahkan pointer branch aktif saat ini (misal `.git/refs/heads/main`) ke SHA-1 commit baru tersebut.

#### 5.2. Mekanisme Git Worktree untuk Multi-Branch Parallel Context
Alih-alih melakukan `git stash` atau *destructive checkout* saat berada di tengah pengerjaan fitur dan harus menangani *critical hotfix*:
```
Working Dir 1 (/repo/feature-auth)  <-- Terikat ke branch 'feat/auth' (HEAD 1)
Working Dir 2 (/repo/hotfix-payment) <-- Terikat ke branch 'hotfix/pay' (HEAD 2)
                 \                      /
                  v                    v
              Shared Database (.git/objects, refs)
```
Git mengizinkan satu database `.git` tunggal di-share ke beberapa working directories terisolasi, menghilangkan *overhead* cloning berulang atau konteks switching yang mengotori index.

---

### 6. Analogy & Diagram ASCII

#### Analogi File System Git
Bayangkan Git sebagai **Sistem Arsip Notaris Kriptografis**:
- **Blob**: Fotokopi selembar surat tanpa nama dan tanggal, hanya isi teksnya saja. Di pojoknya diberi cap sidik jari unik (*SHA*). Jika ada 10 surat dengan isi 100% identik, notaris hanya menyimpan 1 lembar saja di brankas.
- **Tree**: Sebuah amplop map transparan. Di luar map tertulis: "Surat A ditaruh di slot 1, Surat B ditaruh di slot 2". Map ini juga diberi cap sidik jari tersendiri berdasarkan daftar isinya.
- **Commit**: Berita acara yang ditandatangani. Berisi pesan: "Pada detik ini, map versi X disetujui untuk menggantikan map versi W. Ditandatangani oleh Auditor Y".
- **Branch**: Sticky note kecil warna-warni yang bertuliskan "PRODUCTION" yang ditempelkan di atas salah satu Berita Acara (Commit). Sticky note ini sangat ringan dan bisa dipindah-pindah dalam hitungan milidetik.

#### Diagram Representasi Fisik Objek Git
```
+-------------------------------------------------------------------------+
| .git/refs/heads/main -> Menunjuk ke Hash: 9f8a12                        |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| COMMIT OBJECT (Hash: 9f8a12...)                                         |
| tree d41d8c...                                                          |
| parent a3b811...                                                        |
| author Senior Engineer <eng@corp.internal> 1700000000 +0700             |
| committer Senior Engineer <eng@corp.internal> 1700000000 +0700          |
|                                                                         |
| feat(core): implement secure authorization pipeline                     |
+-------------------------------------------------------------------------+
       |                                           |
       v                                           v (Parent Pointer)
+-------------------------------+       +---------------------------------+
| TREE OBJECT (Hash: d41d8c...) |       | COMMIT OBJECT (Hash: a3b811...) |
+-------------------------------+       +---------------------------------+
| 100644 blob e69de2... README.md       | (Previous commit node in DAG)   |
| 100755 blob a45c21... run.sh          +---------------------------------+
| 040000 tree b28911... src/            |
+-------------------------------+-------+
                             |
                             v
              +-------------------------------+
              | TREE OBJECT (Hash: b28911...) |
              +-------------------------------+
              | 100644 blob f1d2d2... main.py |
              +-------------------------------+
                             |
                             v
              +-------------------------------+
              | BLOB OBJECT (Hash: f1d2d2...) |
              +-------------------------------+
              | print("Enterprise ready")     |
              +-------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Plumbing Commands Forensik Manual
Menghasilkan commit murni tanpa memanggil `git add` atau `git commit`.

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Inisialisasi playground repositori kosong
mkdir git-internals-lab && cd git-internals-lab
git init

# 2. Buat file baru dan simpan langsung ke object store (Object Type: BLOB)
CONTENT="Enterprise Config Payload v1"
BLOB_SHA=$(echo "$CONTENT" | git hash-object -w --stdin)
echo "Generated Blob SHA: ${BLOB_SHA}"

# 3. Verifikasi tipe objek dan isi konten mentah dari .git/objects/
git cat-file -t "${BLOB_SHA}"
git cat-file -p "${BLOB_SHA}"

# 4. Bangun file index secara virtual tanpa working tree
git update-index --add --cacheinfo 100644 "${BLOB_SHA}" "config/app.conf"

# 5. Tulis Index ke dalam Database Objek (Object Type: TREE)
TREE_SHA=$(git write-tree)
echo "Generated Tree SHA: ${TREE_SHA}"
git cat-file -p "${TREE_SHA}"

# 6. Buat node Commit yang menunjuk ke Tree tersebut (Object Type: COMMIT)
COMMIT_SHA=$(echo "feat: initialize root enterprise configuration" | git commit-tree "${TREE_SHA}")
echo "Generated Commit SHA: ${COMMIT_SHA}"

# 7. Arahkan pointer branch main ke Commit tersebut
git update-ref refs/heads/main "${COMMIT_SHA}"

# 8. Reset working tree agar sinkron dengan branch pointer
git checkout -f main
ls -la config/app.conf
git log --oneline
```

#### 7.2. Practical Example: Enterprise Pre-Push Hook Guard
Implementasi security hook Bash di sisi workstation (`.git/hooks/pre-push`) untuk mencegah kebocoran private key, plain credential AWS, dan penolakan commit non-GPG signed ke remote protected branches.

```bash
#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: .git/hooks/pre-push
# DESKRIPSI: Enterprise Protection Hook (Security scanning & GPG Signoff check)
# ==============================================================================
set -euo pipefail

PROTECTED_BRANCH="main"
CURRENT_BRANCH=$(git symbolic-ref --short HEAD)

echo "[-] Menjalankan pre-push validation engine pada branch: ${CURRENT_BRANCH}..."

# 1. Deteksi Secret Terlarang (High-Entropy Strings / Private Keys)
FORBIDDEN_PATTERNS=(
    "-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----"
    "AKIA[0-9A-Z]{16}" # AWS Access Key ID
    "ghp_[a-zA-Z0-9]{36}" # GitHub Personal Access Token
)

for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
    if git diff origin/"${PROTECTED_BRANCH}"..HEAD | grep -E -q "$pattern"; then
        echo "[FATAL] Ditemukan kredensial berisiko tinggi yang melanggar audit ISO27001!"
        echo "Pattern violation: ${pattern}"
        exit 1
    fi
done

# 2. Verifikasi GPG Signature pada Commit yang akan di-push ke protected branch
if [ "${CURRENT_BRANCH}" = "${PROTECTED_BRANCH}" ]; then
    COMMITS_TO_PUSH=$(git rev-list origin/"${PROTECTED_BRANCH}"..HEAD)
    for commit in ${COMMITS_TO_PUSH}; do
        if ! git verify-commit "${commit}" >/dev/null 2>&1; then
            echo "[FATAL] Commit ${commit} TIDAK memiliki GPG signature yang valid!"
            echo "Kebijakan Enterprise mewajibkan signed commits: 'git commit -S -m ...'"
            exit 1
        fi
    done
fi

echo "[SUCCESS] Validasi pre-push berhasil. Melanjutkan pengiriman kode ke remote."
exit 0
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Financial Monorepo Bloat & Corruption Recovery
- **Konteks**: Suatu platform perbankan digital memiliki Monorepo backend (Java/Go) berukuran 120 GB yang dikerjakan oleh 650 engineer. Terjadi insiden: sebuah script deployment keliru melakukan commit database snapshot SQLite dummy berukuran 15 GB langsung ke branch `main`. Akibatnya, `git fetch` dan proses CI/CD runner terhenti (*Out-of-Memory error*), melumpuhkan deployment harian.
- **Kebutuhan**:
  1. Membersihkan artefak biner 15 GB tersebut dari *seluruh* history commit, bukan hanya menghapus file di commit terbaru.
  2. Menjaga integritas hash referensi branch aktif.
  3. Memastikan workstation developer tidak mengalami konflik fatal saat menarik (*pull*) history yang telah di-*rewrite*.
- **Solusi Arsitektural**:
  1. Isolasi repository dan aktifkan read-only lock pada remote GitHub Enterprise Server.
  2. Gunakan `git-filter-repo` (Python-based utility resmi penerus `git filter-branch` yang telah di-deprecate karena performa lambat dan rawan korupsi pointer).
  3. Eksekusi purging berbasis path biner:
     ```bash
     # Analisis histori ukuran objek terbesar
     git-filter-repo --analyze
     
     # Purge file secara destruktif dari seluruh graph tanpa merusak struktur merge commit
     git-filter-repo --path-match "database/dumps/dump_large.sqlite" --invert-paths --force
     
     # Pembersihan agresif dan kompresi packfile secara deterministik
     git reflog expire --expire=now --all
     git gc --prune=now --aggressive
     ```
  4. Repository terpangkas dari 120 GB menjadi 4.2 GB.
  5. GitHub Protected Branch di-update via push mirror paksa (`git push origin --force --all --tags`).
  6. Mengaktifkan **GitHub Push Protection** dan **Git LFS (Large File Storage)** dengan pointer locking policy agar file berukuran >100 MB otomatis ditolak di layer HTTP transport.

---

### 9. Trade-offs

| Aspek Arsitektur | Opsi A: Monolithic Full History | Opsi B: Partial/Blobless Clones (`--filter=blob:none`) |
| :--- | :--- | :--- |
| **Network Throughput & Clone Latency** | **Sangat Lambat**: Mengunduh seluruh commit dan blob sejak inisiasi repositori (bisa memakan hitungan jam). | **Sangat Cepat**: Mengunduh hanya tree dan metadata commit. Blob diunduh on-demand saat file dibuka/diedit. |
| **Disk Storage Footprint** | Menghabiskan puluhan hingga ratusan gigabyte disk space lokal developer. | Mengurangi konsumsi disk lokal secara dramatis hingga 70-90%. |
| **Dependensi Konektivitas Jaringan** | **Offline Friendly**: Developer dapat melihat commit 5 tahun lalu, diffing, dan blame tanpa jaringan sama sekali. | **Semi-Offline**: Eksekusi perintah seperti `git checkout` ke commit lama atau `git log -p` memerlukan koneksi untuk fetch missing blob. |
| **Beban Infrastruktur Git Server** | Terfokus tinggi hanya di awal saat initial full-clone, setelah itu query remote sangat rendah. | Beban I/O server remote konstan dan granular karena banyaknya panggilan on-demand blob fetches kecil. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Insiden: Accidental `git reset --hard` yang Menghapus Kode Belum Di-push
- **Gejala**: Developer tidak sengaja mengeksekusi `git reset --hard HEAD~3`. Tiga commit terakhir yang berisi fitur kritikal hilang dari `git log`.
- **Diagnosis Internal**: Git tidak serta merta menghapus data. Objek commit masih berstatus *loose object* atau berada dalam packfile, hanya pointer branch yang digeser mundur. Objek yang kehilangan referensi menjadi *dangling commit*.
- **Mitigasi Step-by-Step**:
  ```bash
  # 1. Buka audit trail internal reflog lokal
  git reflog
  # Output:
  # 1a2b3c4 HEAD@{0}: reset: moving to HEAD~3
  # 5e6f7d8 HEAD@{1}: commit: feat(auth): complete OAuth2 implementation

  # 2. Temukan SHA commit sebelum insiden (HEAD@{1})
  # 3. Pulihkan commit dengan membuat branch pemulih langsung pada pointer tersebut
  git branch recovery-auth 5e6f7d8

  # 4. Verifikasi isi branch yang dipulihkan
  git checkout recovery-auth
  git log -n 1
  ```

#### 10.2. Insiden: Git Submodule Detached State & Out-of-Sync Pointer
- **Gejala**: Developer memperbarui kode di dalam folder submodule, namun branch utama repository induk tetap mencatat status perubahan tak bertuan, atau tim lain menarik submodule yang rusak (*fatal: reference is not a tree*).
- **Akar Masalah**: Submodule tidak otomatis bergerak bersama branch-nya; ia terkunci secara statis pada SHA tertentu di repository induk. Jika commit submodule lokal belum di-push ke remote-nya sendiri, repository induk akan menunjuk ke SHA privat yang tidak ada di server.
- **SOP Resolusi**:
  ```bash
  # 1. Masuk ke dalam direktori submodule dan dorong commit ke origin submodule
  cd components/shared-core
  git checkout main
  git push origin main

  # 2. Kembali ke repository induk dan perbarui referensi index git
  cd ../..
  git add components/shared-core
  git commit -m "chore(deps): bump shared-core commit reference"
  git push origin main

  # 3. Bagi tim pengembang lain, lakukan update recursive secara deterministik:
  git submodule update --init --recursive
  ```

---

### 11. Best Practices (Production Checklist)

#### 11.1. Konfigurasi Global Tingkat Lanjut (Local Machine)
- [ ] Aktifkan `rerere` (*Reuse Recorded Resolution*) untuk merekam dan otomatis menyelesaikan konflik yang sama secara otomatis:
  ```bash
  git config --global rerere.enabled true
  ```
- [ ] Atur default reconciliation pull menjadi rebase demi sejarah commit linear:
  ```bash
  git config --global pull.rebase true
  ```
- [ ] Gunakan algoritma diffing modern *histogram* yang lebih cerdas memahami perpindahan blok kode dibanding algoritma *myers* klasik:
  ```bash
  git config --global diff.algorithm histogram
  ```

#### 11.2. Git Branching & Protected Trunk Verification Checklist
- [ ] **Strict Branch Protection**: Tidak ada pengembang (termasuk Admin/CTO) yang dapat melakukan direct push ke `main`.
- [ ] **Linear Commit History**: Aktifkan kebijakan `Require linear history` (blok merge commit tradisional jika pipeline mensyaratkan fast-forward atau squash).
- [ ] **Cryptographic Signatures**: Wajibkan verifikasi commit bertanda tangan (`Require signed commits`).
- [ ] **Auto-Deletion**: Konfigurasi otomatisasi penghapusan branch fitur setelah PR di-merge (*Automatically delete head branches*).

---

### 12. Hands-on Practice

Simpan seluruh hasil latihan di: `hands-on/m02/`

```
hands-on/m02/
├── 01_internals_inspect.sh
├── 02_worktree_setup.sh
├── 03_sparse_checkout.sh
└── 04_history_rewrite.sh
```

#### Langkah 1: Eksplorasi Database Objek (`01_internals_inspect.sh`)
Buat script Bash yang membuktikan kompresi zlib dan pemetaan SHA pada file internal:

```bash
#!/usr/bin/env bash
set -euo pipefail

mkdir -p hands-on/m02/internals-playground
cd hands-on/m02/internals-playground
git init

# Buat berkas dengan konten deterministik
echo "Architecture Level Git Data" > data.txt

# Masukkan ke index
git add data.txt

# Ekstraksi SHA dari index
SHA=$(git ls-files --stage | awk '{print $2}')
DIR_PREFIX=${SHA:0:2}
FILE_SUFFIX=${SHA:2}

OBJECT_PATH=".git/objects/${DIR_PREFIX}/${FILE_SUFFIX}"
echo "Mencari berkas fisik di: ${OBJECT_PATH}"

# Baca isi file terkompresi menggunakan zlib via python
python3 -c "import zlib; print(zlib.decompress(open('${OBJECT_PATH}', 'rb').read()).decode('latin-1'))"
```

#### Langkah 2: Setup Isolasi Paralel dengan Git Worktree (`02_worktree_setup.sh`)
```bash
#!/usr/bin/env bash
set -euo pipefail

cd hands-on/m02/internals-playground
git commit -m "feat: initial commit for worktree baseline"

# Tambahkan worktree terpisah di direktori ../hotfix-worktree
git worktree add -b hotfix/critical-patch ../hotfix-worktree

# Verifikasi daftar worktree aktif
git worktree list

# Navigasi ke direktori kerja baru
cd ../hotfix-worktree
echo "HOTFIX APPLIED" >> hotfix.log
git add hotfix.log
git commit -m "fix(security): resolve memory leak vulnerability"

# Kembali ke repositori utama dan verifikasi state DAG
cd ../internals-playground
git log --all --graph --oneline
```

#### Langkah 3: Konfigurasi Git Sparse-Checkout untuk Monorepo (`03_sparse_checkout.sh`)
```bash
#!/usr/bin/env bash
set -euo pipefail

mkdir -p hands-on/m02/monorepo-sim
cd hands-on/m02/monorepo-sim
git init

# Simulasikan arsitektur monorepo berukuran masif
mkdir -p services/auth-service services/payment-service services/analytics-service
echo "Auth Service Code" > services/auth-service/index.js
echo "Payment Service Code" > services/payment-service/index.js
echo "Analytics Service Code" > services/analytics-service/index.js

git add .
git commit -m "chore: setup monorepo structure"

# Aktifkan sparse checkout mode cone (high performance path parsing)
git sparse-checkout init --cone

# Set direktori aktif hanya pada services/auth-service
git sparse-checkout set services/auth-service

# Periksa direktori working space fisik
echo "Menampilkan isi filesystem lokal:"
ls -la services/
```

#### Langkah 4: Interaktif Rebase & History Engineering (`04_history_rewrite.sh`)
```bash
#!/usr/bin/env bash
set -euo pipefail

cd hands-on/m02/internals-playground

# Buat rantai commit kotor (dirty history)
echo "wip 1" >> log.txt && git commit -am "fix typo"
echo "wip 2" >> log.txt && git commit -am "fix typo again"
echo "wip 3" >> log.txt && git commit -am "cleanup forgotten prints"

# Jalankan autosquash non-interaktif terotomasi untuk standardisasi
# Menggabungkan 3 commit terakhir ke dalam commit struktural
GIT_SEQUENCE_EDITOR="sed -i.bak '2,3s/pick/squash/'" git rebase -i HEAD~3
git log -n 2 --oneline
```

---

### 13. Exercises

#### Level Easy
1. Buat direktori Git baru, buat file teks bernama `hello.txt` berisi string `"DevOps"`.
2. Hitung SHA-1 hash dari string tersebut secara manual via piping shell ke `git hash-object`.
3. Verifikasi apakah SHA yang dihasilkan sama persis dengan yang dihasilkan sistem Git saat Anda melakukan `git add hello.txt`.
*Kriteria Keberhasilan*: SHA-1 output dari `printf "blob 7\0DevOps" | sha1sum` identik 100% dengan `git hash-object hello.txt`.

#### Level Medium
1. Simulasikan situasi di mana Anda memiliki 3 commit di branch `feature-analytics`.
2. Commit kedua tidak sengaja menambahkan file berkas `.env` berisi `DATABASE_PASSWORD=secret`.
3. Lakukan rewrite history menggunakan interactive rebase (`git rebase -i`) dengan opsi `edit` pada commit kedua untuk menghapus file `.env` tersebut dari commit history.
4. Tunjukkan bahwa commit ketiga berhasil diaplikasikan kembali tanpa ada jejak `.env` pada graph tree.
*Kriteria Keberhasilan*: `git log -p` pada seluruh history branch tidak lagi mengekspos variabel `DATABASE_PASSWORD`.

#### Level Hard
1. Buat skrip automasi pemulihan repo yang mengalami korupsi pointer (simulasikan dengan menghapus isi dari `.git/refs/heads/main`).
2. Gunakan `git fsck --lost-found` untuk mengidentifikasi *dangling commit*.
3. Parse log payload commit terakhir secara otomatis untuk mengekstrak SHA commit yang tepat.
4. Rekonstruksi branch `main` kembali ke posisi commit terakhir secara akurat tanpa melakukan cloning ulang.
*Kriteria Keberhasilan*: Branch `main` kembali aktif dan menunjuk ke snapshot paling mutakhir dengan exit code 0.

---

### 14. Challenge

#### Skenario Kasus Kompleks: The Post-Incident Git Exorcism
Sebuah pipeline otomatis milik developer magang mengeksekusi script yang men-generate 10.000 file dummy (`dummy_1.bin` s/d `dummy_10000.bin`, masing-masing 512 KB) dan melakukan commit langsung ke branch inti `release-v2.0` yang belum sempat di-push ke server origin. Setelah menyadari kesalahannya, sang developer mencoba memperbaikinya dengan mengeksekusi `rm -f *.bin` lalu membuat commit baru: `"fix: remove binary files"`.

Meskipun pada commit terakhir file-file tersebut sudah hilang dari working directory, ukuran folder `.git` tetap membengkak sebesar ~5 GB karena seluruh snapshot biner masih terikat kuat di dalam objek-objek Tree dan Commit sebelumnya. Sementara itu, 15 engineer lain sudah membuat commit baru di atas commit "fix" tersebut.

#### Tantangan Teknis:
Anda sebagai Principal DevOps/Platform Engineer ditugaskan untuk:
1. Membuang seluruh riwayat keberadaan 10.000 file `.bin` tersebut dari **seluruh rentang DAG** commit branch `release-v2.0` secara total.
2. Mempertahankan 15 commit bisnis sah yang dibuat oleh para engineer lain tanpa merusak authorship, timestamp, dan urutan dependensi logika kodenya.
3. Menjalankan *aggressive housekeeping* hingga ukuran lokal repository kembali ke ukuran normal (< 50 MB).
4. Menghasilkan laporan audit forensik yang membuktikan bahwa tidak ada satupun *dangling blob* atau *unreferenced packfile* yang tersisa di dalam disk storage `.git`.

*Catatan: Eksekusi ini harus diselesaikan murni menggunakan Git core CLI tools atau `git-filter-repo` tanpa merusak branch refs lainnya.*

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. **Objek Git apa yang bertugas menyimpan nama file dan mode izin akses (permissions) file?**
   - A. Blob
   - B. Tree
   - C. Commit
   - D. Index
   *Kunci Jawaban*: **B**. Blob hanya menyimpan data mentah konten file; penamaan file dan hak aksesnya dikelola sepenuhnya oleh objek Tree.

2. **Dua karakter pertama dari hash SHA objek Git digunakan untuk apa pada filesystem `.git/objects/`?**
   - A. Menandai tipe objek (Tree/Blob/Commit).
   - B. Menjadi nama sub-direktori guna mencegah bottleneck batas file maksimum pada filesystem OS.
   - C. Versi dari kompresi zlib.
   - D. Kode hash otentikasi komitter.
   *Kunci Jawaban*: **B**. Sistem operasi file system dapat mengalami degradasi performa I/O jika satu folder menampung puluhan ribu file. Git memecahnya ke dalam 256 sub-direktori (00-ff).

3. **Perintah apa yang digunakan untuk membaca isi mentah sebuah objek Git berdasarkan SHA-nya tanpa memedulikan tipenya?**
   - A. `git cat-file -p <SHA>`
   - B. `git show-object --raw <SHA>`
   - C. `git dump-blob <SHA>`
   - D. `git unpack-file --force <SHA>`
   *Kunci Jawaban*: **A**. Flag `-p` (*pretty-print*) pada `git cat-file` memerintahkan Git mendeteksi tipe objek dan mencetak isinya secara terformat.

4. **Apa status sebuah commit jika ia tidak lagi memiliki cabang (branch) atau tag yang menunjuk kepadanya?**
   - A. Orphan branch
   - B. Dangling commit
   - C. Zombie commit
   - D. Untracked commit
   *Kunci Jawaban*: **B**. Sebuah commit yang lepas dari DAG traversal karena penimpaan pointer disebut *dangling commit*.

5. **Di mana Git mencatat riwayat pergerakan pointer HEAD lokal secara kronologis?**
   - A. `.git/config`
   - B. `.git/HEAD`
   - C. `.git/logs/HEAD` (Reflog)
   - D. `.git/hooks/post-commit`
   *Kunci Jawaban*: **C**. `git reflog` membaca log transaksi dari `.git/logs/HEAD` dan direktori `.git/logs/refs/`.

---

#### Intermediate (5 Pertanyaan)
1. **Apa perbedaan mendasar antara `git merge --squash` dan `git rebase -i` yang di-squash?**
   - A. Keduanya identik secara fungsional.
   - B. `git merge --squash` menyatukan commit langsung ke working tree branch target tanpa mempertahankan riwayat parent terpisah, sedangkan rebase menyusun ulang DAG secara berurutan.
   - C. Rebase squash tidak menghasilkan SHA baru.
   - D. `merge --squash` mempertahankan branch merge commit node ganda.
   *Kunci Jawaban*: **B**. `merge --squash` mengambil seluruh perubahan dan menaruhnya dalam kondisi staged di working directory tujuan tanpa metadata commit parent DAG ganda.

2. **Bagaimana Git LFS (Large File Storage) memperlakukan file biner masif di repository?**
   - A. Mengompresinya dengan algoritma Brotli ke dalam `.git/objects`.
   - B. Mengganti isi berkas asli dalam commit Git dengan file teks pointer kecil yang berisi hash SHA-256 dan ukuran file, lalu mengunggah payload asli ke LFS server terpisah.
   - C. Menyimpannya pada branch tersembunyi bernama `refs/lfs/data`.
   - D. Membagi file menjadi ribuan loose blobs kecil secara otomatis.
   *Kunci Jawaban*: **B**. Git LFS hanya menyimpan berkas pointer teks metadata berukuran sekitar 130 byte pada Git tree, menghindari pembengkakan ukuran packfile lokal.

3. **Apa kegunaan utama fitur `git worktree` dibandingkan membuat klon (`git clone`) baru dari repository yang sama?**
   - A. Mengizinkan bypass branch protection rule.
   - B. Menghemat storage disk dan bandwidth jaringan secara signifikan karena semua worktree berbagi basis objek database (`.git/objects`) yang sama.
   - C. Mengizinkan dua working tree checkout branch yang sama secara simultan.
   - D. Mengubah format packfile menjadi loose objects.
   *Kunci Jawaban*: **B**. Worktree menyediakan direktori kerja terisolasi dengan branch berbeda tanpa perlu menduplikasi object database `.git/`. (Perlu dicatat bahwa Git secara default melarang checkout ke branch yang sama pada dua worktree aktif).

4. **Kapan *packfile* dibuat oleh Git secara internal?**
   - A. Setiap kali developer mengetik `git commit`.
   - B. Hanya saat repository di-clone dari GitHub.
   - C. Saat eksekusi `git gc`, network push/fetch over wire protocol, atau ketika jumlah loose objects melewati ambang batas threshold konfigurasi (`gc.auto`).
   - D. Saat branch di-merge dengan strategi squash.
   *Kunci Jawaban*: **C**. Git menjaga performa dengan mengemas loose objects ke dalam packfiles secara periodik atau saat transfer data jaringan berlangsung.

5. **Apa efek samping destruktif dari mengeksekusi `git filter-branch` atau `git-filter-repo` pada branch produksi bersama?**
   - A. Semua commit yang di-filter akan terhapus permanen dari server lokal developer saja.
   - B. Seluruh commit SHA yang diproses beserta seluruh commit turunannya akan berubah total, merusak DAG dan memicu conflict/duplikasi jika ditarik oleh kontributor lain yang masih memiliki history lama.
   - C. Repository akan beralih ke format non-DAG.
   - D. Kunci SSH developer akan dicabut secara otomatis oleh Git daemon.
   *Kunci Jawaban*: **B**. Mengubah konten atau history commit otomatis mengubah hash SHA commit tersebut dan seluruh anak keturunannya (*cascading hash invalidation*).

---

#### Skenario Kasus Produksi (3 Pertanyaan)

1. **Skenario Deployment Critical Hotfix**:
   Seorang DevOps Engineer mendapati bahwa commit darurat di production branch terhambat karena aturan proteksi GitHub `Linear History Required` aktif. Rekan kerjanya melakukan merge menggunakan tombol "Merge Pull Request" biasa (membuat non-fast-forward merge commit `Merge branch 'feat' into main`). Pipeline deployment ditolak secara otomatis oleh rule engine.
   *Bagaimana tindakan paling presisi untuk memperbaiki branch tanpa kehilangan logika kode?*
   - A. Menghapus branch `main` di GitHub dan mem-push ulang local branch.
   - B. Melakukan `git revert` pada merge commit lalu memaksa push (`--force`).
   - C. Melakukan `git checkout main`, lalu `git rebase -i` untuk mendatarkan struktur commit, me-remove merge commit node, lalu push fast-forward.
   - D. Menonaktifkan branch protection secara permanen.
   *Kunci Jawaban*: **C**. Linear history melarang node DAG yang memiliki 2 parent commit. Rebase mengekstrak commit individual di atas tip branch target, meratakan (*flattening*) riwayat menjadi garis lurus sequential.

2. **Skenario Corrupted Object Error**:
   Sebuah server build CI/CD runner tiba-tiba crash akibat *hard power failure* di tengah proses penulisan objek git. Pada eksekusi build berikutnya, Git melempar pesan fatal: `error: object file .git/objects/4b/825dc... is empty` dan `fatal: loose object 4b825dc... is corrupt`.
   *Langkah penanganan teknis tanpa harus mengklon ulang repository ratusan gigabyte dari awal adalah:*
   - A. Menjalankan `git clean -fdx`.
   - B. Hapus file objek kosong yang korup tersebut (`.git/objects/4b/825dc...`), jalankan `git fsck`, lalu fetch ulang objek spesifik yang hilang dari remote via `git fetch origin --refetch`.
   - C. Mengganti isi file objek yang korup dengan string spasi kosong.
   - D. Mengeksekusi `git init` ulang di atas folder yang sama.
   *Kunci Jawaban*: **B**. Berkas berukuran 0-byte akibat *interrupted I/O write* memblokir engine zlib Git. Menghapus objek kosong tersebut memungkinkan Git memvalidasi ulang DAG-nya dan mengunduh ulang blob/tree yang hilang dari remote mirror via `--refetch`.

3. **Skenario Git Reflog Expiration Policy**:
   Sebuah tim ingin memulihkan kode yang terhapus secara tidak sengaja oleh developer 4 bulan yang lalu. Saat mereka membuka `git reflog`, riwayat commit tersebut sudah tidak ada lagi, meskipun developer bersumpah mereka tidak pernah menjalankan `git gc` secara manual.
   *Mengapa referensi tersebut hilang secara otomatis?*
   - A. Sistem operasi membersihkan direktori `/tmp` secara berkala.
   - B. Git memiliki konfigurasi internal default `gc.reflogExpire` (biasanya 90 hari untuk reachable refs dan 30 hari untuk unreachable/dangling refs) yang otomatis dieksekusi via background maintenance.
   - C. Objek Git terhapus otomatis setiap 1.000 commit.
   - D. GitHub API menghapus riwayat reflog lokal pada setiap otentikasi CLI.
   *Kunci Jawaban*: **B**. Git memiliki siklus hidup pembersihan otomatis (*automatic housekeeping*). Entri reflog yang tidak lagi terikat pada cabang hidup kedaluwarsa secara default dalam 30 hari, setelah itu dipangkas oleh `git prune`.

---

### 16. Summary

1. **Git adalah Mesin Kriptografis Terarah**: Di balik abstraksi branch dan commit-nya, Git adalah *content-addressable storage* immutable. Seluruh data disimpan sebagai Blob, Tree, Commit, atau Tag yang diverifikasi oleh integritas algoritma hash (SHA-1/SHA-256).
2. **Efisiensi Melalui Plumbing & Packfiles**: Git tidak pernah merekam *per-line delta* saat membuat commit; Git mengambil full-tree snapshot yang kemudian dikompresi secara asinkron menjadi packfiles berbasis delta-compression untuk efisiensi penyimpanan dan transfer jaringan.
3. **Immutabilitas Menjamin Keamanan Data**: Commit yang "hilang" akibat operasi destruktif (`reset --hard`, *bad rebase*) hampir selalu dapat dipulihkan melalui `git reflog` dan traversal objek dangling via `git fsck`, selama belum dibersihkan oleh siklus `git prune/gc`.
4. **Skalabilitas Enterprise Menuntut Pola Modern**: Bekerja dalam skala Monorepo multi-tim memerlukan toolset lanjutan: *Git Worktrees* untuk paralelisasi direktori kerja, *Blobless Clones* dan *Sparse-Checkout* untuk efisiensi transfer, serta *Client/Server Hooks* untuk menegakkan tata kelola keamanan dan auditabilitas secara deterministik.