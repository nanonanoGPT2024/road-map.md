# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis Anatomi Internal Git**: Membedah struktur direktori `.git`, mekanisme Directed Acyclic Graph (DAG), serta siklus hidup *content-addressable object store* (blob, tree, commit, annotated tag).
2. **Mengoperasikan Rekayasa Riwayat Lanjutan**: Melakukan manipulasi riwayat Git (*history rewriting*) secara presisi menggunakan *interactive rebase*, *squash*, *fixup*, *autosquash*, dan *cherry-pick* tanpa merusak integritas repositori tim.
3. **Menerapkan Disaster Recovery Tingkat Lanjut**: Mengisolasi dan memulihkan commit yang hilang (*dangling/orphaned commits*) melalui `git reflog`, `git fsck`, dan manipulasi referensi internal.
4. **Mengotomatisasi Pelacakan Regresi Produksi**: Mengoperasikan `git bisect` berbasis skrip otomasi (`bisect run`) untuk mendeteksi *faulty commit* pada repositori berskala ribuan commit dalam hitungan menit.
5. **Merancang Arsitektur Percabangan Enterprise**: Mengonfigurasi strategi percabangan (*Trunk-Based Development* vs *GitFlow*), *Branch Protection Rules*, *Commit Signing* (GPG/SSH), serta mitigasi repositori raksasa (Git LFS dan *sparse-checkout*).

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda harus memahami:
* Operasi dasar Git: `add`, `commit`, `status`, `push`, `pull`, `fetch`, dan `branch`.
* Konsep dasar *three-tree architecture*: Working Directory, Staging Area (Index), dan Commit History (HEAD).
* Familiaritas dengan terminal/CLI Linux/macOS/WSL dan teks editor berbasis terminal (Vim/Nano).
* Pemahaman fundamental mengenai algoritma hashing kriptografis (SHA-1/SHA-256).

---

## 3. Concept & Internal Architecture

Git pada dasarnya bukanlah sekadar *Version Control System* (VCS) berbasis delta perubahan file, melainkan sebuah **Content-Addressable Key-Value Store** yang dibungkus oleh antarmuka *VCS porcelain*.

### 3.1 Struktur Direktori `.git`
Ketika `git init` dieksekusi, direktori tersembunyi `.git/` diinisialisasi dengan struktur inti berikut:

```text
.git/
├── HEAD            # Pointer ke cabang aktif saat ini (contoh: ref: refs/heads/main)
├── config          # Konfigurasi spesifik repositori lokal
├── description     # Digunakan oleh GitWeb (jarang digunakan modern)
├── hooks/          # Skrip otomatisasi sisi klien/server (pre-commit, commit-msg, dll.)
├── info/           # Metadata repositori (contoh: info/exclude untuk local ignore)
├── index           # Binary file: staging area (cache dari working tree)
├── objects/        # Database objek: content-addressable storage
│   ├── [0-9a-f]{2}/# Subdirektori 2 karakter pertama SHA-1
│   ├── info/       # Metadata packfile
│   └── pack/       # Packfiles (.pack) dan Index packfile (.idx) untuk kompresi
└── refs/           # Pointer ke commit objects
    ├── heads/      # Referensi cabang lokal (main, staging, feature)
    ├── tags/       # Referensi tag
    └── remotes/    # Referensi cabang remote tracking
```

### 3.2 Tipe Objek Git (The Core 4)
Semua entitas data dalam Git disimpan di dalam direktori `.git/objects/`. Setiap objek diidentifikasi oleh hash SHA-1 berukuran 40 karakter (atau SHA-256 pada sistem modern), di mana 2 karakter pertama menjadi nama subdirektori dan 38 karakter berikutnya menjadi nama file. Objek dikompresi menggunakan zlib (RFC 1950).

Format penyimpanan payload:
$$\text{header} = \text{tipe} + \text{" "} + \text{ukuran\_byte} + \text{\textbackslash 0}$$
$$\text{payload} = \text{header} + \text{konten}$$
$$\text{Object ID (OID)} = \text{SHA-1}(\text{payload})$$

```
+-----------------------------------------------------------------------------+
|                                OBJECT TYPES                                 |
+-----------------------------------------------------------------------------+
|  1. BLOB (Binary Large Object)                                              |
|     - Hanya menyimpan konten mentah file (raw data).                        |
|     - Tidak menyimpan nama file, path direktori, timestamp, atau permission.|
|                                                                             |
|  2. TREE                                                                    |
|     - Merepresentasikan struktur direktori/folder.                          |
|     - Memetakan nama file, file mode (permissions), dan OID blob/sub-tree.  |
|                                                                             |
|  3. COMMIT                                                                  |
|     - Metadata snapshot proyek: root Tree OID, parent Commit OID,           |
|       author (timestamp & identitas), committer, dan commit message.        |
|                                                                             |
|  4. ANNOTATED TAG                                                           |
|     - Pointer permanen ke commit tertentu: commit OID, nama tagger,         |
|       timestamp, pesan tag, dan opsional GPG signature.                     |
+-----------------------------------------------------------------------------+
```

### 3.3 Anatomi Directed Acyclic Graph (DAG)
Setiap commit menyimpan pointer yang merujuk balik ke commit pendahulunya (*parent commit*). Struktur ini membentuk graf berarah tanpa siklus (DAG):
* Root commit: Tidak memiliki parent.
* Standard commit: Memiliki 1 parent.
* Merge commit: Memiliki 2 atau lebih parent.

```
       C1 <-------- C2 <-------- C4 (feature)
        ^            ^            ^
        |            |            |
       Root         Parent       Tip of branch
        |            |
        +---------- C3 <-------- C5 (main)
```
*Arah panah mengindikasikan referensi parent.*

### 3.4 Mekanisme Loose Objects vs. Packfiles
* **Loose Objects**: Format default saat file dimodifikasi dan di-stage (`git add`). Setiap file/perubahan menghasilkan satu file terkompresi individual. Hal ini menghasilkan inefisiensi I/O disk jika terdapat ribuan objek.
* **Packfiles (`git gc`)**: Git mengonsolidasi loose objects menjadi satu file biner arsip (`.pack`) disertai file indeks pencarian biner (`.idx`). Packfile mengimplementasikan *delta compression*: jika sebuah file 10MB hanya diubah 1 baris, Git hanya menyimpan 1 versi penuh (basis) dan delta perubahan biner untuk versi lainnya, memangkas ukuran disk hingga >90%.

---

## 4. Why & What

| Dimensi | Konsep Dasar (Porcelain) | Tingkat Enterprise (Plumbing & Production) |
| :--- | :--- | :--- |
| **Pola Pikir** | Git sebagai alat penyimpan backup riwayat file linear. | Git sebagai database immutable berbasis graph terdistribusi dengan audit-trail kriptografis. |
| **Manajemen Konflik** | Menyelesaikan manual saat `git merge` lalu commit acak. | Rebase interaktif terstruktur, preservasi riwayat linear atau semi-linear yang atomik dan bisect-able. |
| **Kualitas Audit** | Commit bercampur aduk: "fix typo", "wip", "debug". | Semantic Commits, terverifikasi tanda tangan kriptografis GPG/SSH, lolos linting otomatis. |
| **Resolusi Insiden** | Mencari bug secara manual baris demi baris pada puluhan PR. | Automasi binary search via `git bisect` berbasis integrasi tes otomatis CI/CD. |
| **Skalabilitas Repositori** | Semua aset biner (gambar, dataset, build) masuk repo. | Pemisahan aset via Git LFS (*Large File Storage*), selective checkout via *Sparse-Checkout*. |

---

## 5. How (Workflow Detail)

### 5.1 Siklus Interactive Rebase & Autosquash
Tujuan: Menjaga riwayat cabang fitur tetap rapi, atomik, dan mudah di-review sebelum digabungkan ke cabang utama.

```
Working -> Stage -> Commit WIP -> Fixup commit -> Interactive Rebase (Autosquash) -> Clean Branch
```

1. Jalankan rebase interaktif terhadap cabang target:
   ```bash
   git rebase -i HEAD~4
   # atau rebase terhadap upstream:
   git rebase -i origin/main
   ```
2. Git akan membuka editor konfigurasi rebase dengan perintah-perintah:
   * `pick`: Menggunakan commit tersebut apa adanya.
   * `reword`: Menggunakan commit, namun mengubah pesan commit.
   * `edit`: Berhenti pada commit tersebut untuk mengizinkan perubahan file/split commit.
   * `squash`: Menggabungkan commit ke commit sebelumnya, menggabungkan pesan commit.
   * `fixup`: Menggabungkan commit ke commit sebelumnya, membuang pesan commit ini.
   * `drop`: Menghapus commit dari DAG.

### 5.2 Siklus Disaster Recovery (Reflog Archeology)
Jika cabang terhapus secara tidak sengaja via `git branch -D` atau eksekusi `git reset --hard` yang keliru:

```
Insiden Terjadi -> git reflog show -> Identifikasi OID Terakhir -> git checkout -b recovery-branch <OID>
```

1. Git mencatat mutasi pointer `HEAD` dalam log referensi lokal:
   ```bash
   git reflog show HEAD
   ```
2. Temukan indeks titik waktu sebelum insiden (contoh: `HEAD@{1}`).
3. Bentuk cabang baru tepat pada snapshot tersebut:
   ```bash
   git branch recovery-branch HEAD@{1}
   ```

### 5.3 Siklus Deteksi Bug Otomatis (Git Bisect)
Git Bisect menggunakan algoritma Binary Search $O(\log N)$ untuk menemukan commit yang memperkenalkan regresi:

```
Inisiasi (git bisect start)
   |
Tentukan Bad State (git bisect bad)
   |
Tentukan Good State (git bisect good <commit-lama>)
   |
Git Check out titik tengah (Midpoint)
   |
Jalankan Pengujian (Manual atau Skrip Otomatis)
   |
+--- Sukses? ---> `git bisect good` --+
|                                     |
+--- Gagal?  ---> `git bisect bad`  --+
                                      |
Ulangi hingga First Bad Commit Terisolasi
                                      |
Selesai & Reset (git bisect reset)
```

---

## 6. Analogy & Diagram ASCII

### 6.1 Analogi: Git Plumbing vs Porcelain
Bayangkan sebuah mobil modern:
* **Porcelain Commands** (`git add`, `git commit`, `git checkout`): Roda kemudi, pedal gas, tuas persneling, dan speedometer. Dibuat untuk kenyamanan manusia.
* **Plumbing Commands** (`git hash-object`, `git cat-file`, `git write-tree`): Sistem injeksi bahan bakar elektronik, sensor poros engkol, dan bus data CAN. Bekerja di balik layar untuk memproses data mentah.

### 6.2 Diagram Struktur Internal Objek Git (Low-Level DAG)

```
        COMMIT OBJECT (OID: a1b2c3d...)
        +---------------------------------------------------+
        | tree: 98f4e21...                                  |
        | parent: e7a10bc...                                |
        | author: Eng Lead <lead@corp.com> 1700000000 +0700 |
        | committer: Eng Lead <lead@corp.com> 1700000000    |
        |                                                   |
        | feat(payment): implement QRIS payment gateway     |
        +---------------------------------------------------+
                                  |
                                  v
                        TREE OBJECT (OID: 98f4e21...)
                        +-----------------------------------+
                        | 100644 blob 4d5e6f...  README.md  |
                        | 040000 tree c1a2b3...  src        |
                        +-----------------------------------+
                                                   |
                         +-------------------------+
                         v
               TREE OBJECT (OID: c1a2b3...)
               +--------------------------------------------+
               | 100644 blob a9b8c7...  index.ts            |
               | 100644 blob de34f2...  payment.ts          |
               +--------------------------------------------+
                                              |
                                              v
                                    BLOB OBJECT (OID: de34f2...)
                                    +-----------------------+
                                    | export class QRIS {   |
                                    |   process() { ... }   |
                                    | }                     |
                                    +-----------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Membangun Commit Menggunakan Plumbing Commands
Kita akan membuat sebuah commit yang sah secara kriptografis tanpa mengeksekusi `git add` atau `git commit`.

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Inisialisasi sandbox
mkdir /tmp/git-plumbing-demo && cd /tmp/git-plumbing-demo
git init

# 2. Tulis konten file dan simpan sebagai BLOB ke database .git/objects/
echo "console.log('Production System Active');" > app.js
BLOB_HASH=$(git hash-object -w app.js)
echo "Blob Hash: ${BLOB_HASH}"

# 3. Daftarkan BLOB ke dalam Staging Area (Index)
git update-index --add --cacheinfo 100644 "${BLOB_HASH}" app.js

# 4. Tulis Index menjadi TREE Object
TREE_HASH=$(git write-tree)
echo "Tree Hash: ${TREE_HASH}"

# 5. Buat COMMIT Object berbasis Tree tersebut
COMMIT_HASH=$(echo "chore: initial low-level commit" | git commit-tree "${TREE_HASH}")
echo "Commit Hash: ${COMMIT_HASH}"

# 6. Arahkan pointer referensi HEAD cabang main ke Commit baru
git update-ref refs/heads/main "${COMMIT_HASH}"
git symbolic-ref HEAD refs/heads/main

# 7. Verifikasi integritas menggunakan porcelain
git status
git log -1 --stat
```

### 7.2 Practical Example: Interactive Rebase dengan Fixup & Autosquash

Skenario: Anda sedang mengembangkan fitur baru. Anda memiliki commit utama dan beberapa commit perbaikan bug kecil yang seharusnya disatukan ke commit fitur secara rapi sebelum pull request diajukan.

```bash
#!/usr/bin/env bash
set -euo pipefail

# Konfigurasi repositori lokal
git config rebase.autoSquash true

# Buat initial commit
echo "module.exports = { port: 8080 };" > config.js
git add config.js && git commit -m "feat(core): initial application bootstrap"

# Buat feature commit
echo "function auth() { return true; }" >> auth.js
git add auth.js && git commit -m "feat(auth): add base authentication logic"

# Ambil SHA commit auth untuk target autosquash
AUTH_COMMIT_SHA=$(git rev-parse HEAD)

# Buat perbaikan untuk auth (typo atau linting)
echo "function auth() { return Boolean('valid_session'); }" > auth.js
git add auth.js

# Gunakan flag --fixup ke commit target
git commit --fixup="${AUTH_COMMIT_SHA}"

# Buat fitur lain di atasnya
echo "function profile() { return { user: 'admin' }; }" > profile.js
git add profile.js && git commit -m "feat(user): add user profile endpoint"

# Jalankan autosquash rebase secara non-interaktif untuk lingkungan scripting
# (Dalam dunia nyata, developer menjalankan 'git rebase -i --autosquash HEAD~3')
GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash HEAD~3

# Hasil log: Commit fixup otomatis disatukan ke target tanpa intervensi manual editor
git log --oneline
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Insiden Payment Outage di Skala Enterprise (Fintech)
* **Konteks**: Platform perbankan digital merilis versi `v4.12.0` yang terdiri dari 420 commit gabungan dari 15 tim. 10 menit setelah rilis canary, tingkat kegagalan transaksi meningkat dari 0.01% menjadi 14.8%.
* **Masalah**: Tidak ada error exception fatal pada observability dashboard; transaksi silently failing (terjadi race condition database lock). Log menunjukkan error muncul sporadis. Pengembang tidak mengetahui commit mana dari 420 commit yang memicu anomali ini.
* **Tindakan**: Tim Platform Engineering menggunakan skrip pengujian berbasis performa, dieksekusi melalui `git bisect run`.

#### Skrip Otomasi Investigasi (`bisect_validator.sh`)
```bash
#!/usr/bin/env bash
# Skrip validasi untuk git bisect run
# Return 0: Good, Return 1: Bad, Return 125: Untestable/Skip

set -e

# Bersihkan artifact build sebelumnya
rm -rf dist/ node_modules/

# Install depedensi terkunci
npm ci --silent > /dev/null 2>&1

# Build source
npm run build --silent > /dev/null 2>&1

# Eksekusi integrasi simulasi beban transaksi konkurensi tinggi
# Jika exit code 0 maka commit GOOD, jika non-zero maka BAD
npm run test:concurrency-load -- --silent
```

#### Eksekusi Orkestrasi Pemulihan
```bash
# 1. Mulai bisect
git bisect start

# 2. Tandai commit produksi saat ini sebagai BAD
git bisect bad v4.12.0

# 3. Tandai rilis stabil sebelumnya sebagai GOOD
git bisect good v4.11.0
# Output: Bisecting: 209 revisions left to test after this (roughly 8 steps)

# 4. Berikan kontrol penuh pada runner skrip
git bisect run ./bisect_validator.sh

# Git secara otomatis melakukan binary search check out ke tiap titik tengah,
# menjalankan ./bisect_validator.sh, dan memvalidasi log.

# Hasil akhir setelah 8 iterasi otomatis (~3 menit):
# 89ab32c114f5e8d901a1b2c3d4e5f6a7b8c9d0e1 is the first bad commit
# Author: Core-DB Team <db-core@fintech.corp>
# Commit Message: perf(db): optimize connection pool acquisition timeout

# 5. Reset kondisi kerja
git bisect reset

# 6. Buat Hotfix Revert Commit secara instan pada branch release
git checkout -b hotfix/revert-db-timeout v4.12.0
git revert --no-edit 89ab32c114f5e8d901a1b2c3d4e5f6a7b8c9d0e1 -S
git push origin hotfix/revert-db-timeout
```

---

## 9. Trade-offs

Mengelola Git pada skala enterprise menuntut pertimbangan arsitektur dan trade-off operasional:

```
+---------------------------------------------------------------------------------------------------+
| STRATEGI PENGGABUNGAN: REBASE (LINEAR) VS MERGE COMMITS (NON-LINEAR)                              |
+------------------------------------+--------------------------------------------------------------+
| Pendekatan                         | Keuntungan / Kerugian                                        |
+------------------------------------+--------------------------------------------------------------+
| Linear History (Rebase + FF-only)  | (+) Riwayat sangat bersih, bisect sangat cepat & akurat.      |
|                                    | (-) Menulis ulang commit hashes (re-writing history).        |
|                                    | (-) Konteks pengelompokan branch fitur menjadi hilang.       |
|                                    | (-) Berbahaya jika rebase dilakukan pada shared branch.       |
+------------------------------------+--------------------------------------------------------------+
| Non-Linear History (True Merge)    | (+) 100% mempertahankan riwayat kronologis autentik.        |
|                                    | (+) Mudah melacak kapan fitur tertentu digabungkan.          |
|                                    | (-) Graph menjadi "jalur kereta api" ruwet (spaghetti DAG).  |
|                                    | (-) Bisect lebih kompleks karena menelusuri banyak cabang.    |
+------------------------------------+--------------------------------------------------------------+
| Semi-Linear (Rebase + Merge --no-ff)| Pilihan Ideal Enterprise: Fitur di-rebase terlebih dahulu,   |
|                                    | lalu digabung via explicit merge commit dengan CI verification.|
+------------------------------------+--------------------------------------------------------------+
```

```
+---------------------------------------------------------------------------------------------------+
| PENYIMPANAN DATA: GIT NATIVE BLOB VS GIT LFS (LARGE FILE STORAGE)                                 |
+------------------------------------+--------------------------------------------------------------+
| Model                              | Analisis Karakteristik                                       |
+------------------------------------+--------------------------------------------------------------+
| Git Native Storage                 | Karakter: Seluruh riwayat file didistribusikan ke semua klon. |
|                                    | Trade-off: Repositori membengkak drastis jika ada binary,    |
|                                    | clone time eksponensial, network transfer membebani server.   |
+------------------------------------+--------------------------------------------------------------+
| Git LFS                            | Karakter: File biner diganti pointer metadata text kecil.    |
|                                    | Trade-off: Ukuran clone sangat minimal. Memerlukan server    |
|                                    | storage khusus (S3 compatible), biaya storage LFS, dependensi|
|                                    | tools tambahan pada pipeline CI/CD.                          |
+------------------------------------+--------------------------------------------------------------+
```

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Force Push Mengakibatkan Data Rekan Kerja Terhapus
* **Kesalahan**: Menggunakan flag agresif `git push --force` setelah melakukan rebase lokal, yang secara paksa menimpa commit yang telah di-push oleh anggota tim lain di cabang yang sama.
* **Solusi**: Wajib mengganti `--force` dengan parameter protektif `--force-with-lease`.
  ```bash
  # Mencegah overwrite jika referensi remote telah berubah oleh orang lain
  git push --force-with-lease origin feature/payment-revamp
  ```

### 10.2 Jebakan Kondisi Detached HEAD
* **Masalah**: Melakukan checkout langsung ke Hash Commit atau Tag (`git checkout <commit-hash>`), kemudian membuat commit-commit baru. Saat beralih ke `main`, seluruh commit baru seolah "lenyap".
* **Akar Masalah**: Commit baru tidak diikat oleh nama cabang (*no ref pointer*). Garbage collector Git nantinya akan membersihkannya sebagai dangling object.
* **Resolusi Cepat**:
  ```bash
  # Identifikasi commit hash terakhir pada status detached
  git log -1 --format="%H"
  # Buat cabang formal dari commit tersebut sebelum beralih
  git branch feature/rescued-work
  git checkout feature/rescued-work
  ```

### 10.3 Kebocoran Data Sensitif (Kredensial/API Key/Private Key)
* **Masalah**: Menghapus file rahasia dengan `git rm secret.env && git commit` tidak menghapus file dari riwayat Git. Data tetap ada di dalam database objek pada commit sebelumnya.
* **Resolusi Industri**: Jangan gunakan `git-filter-branch` (usang dan lambat). Gunakan tool standar performa tinggi: **`git-filter-repo`**.
  ```bash
  # Instalasi: pip install git-filter-repo
  # Bersihkan file dari seluruh cabang dan seluruh riwayat snapshot
  git filter-repo --invert-paths --path secret.env --force

  # Hapus dan sinkronkan referensi remote
  git remote add origin <url-repo>
  git push origin --force --all
  git push origin --force --tags
  ```

---

## 11. Best Practices (Production Checklist)

Berikut standar minimum repository readiness pada level enterprise:

- [ ] **Linear/Clean Branch Strategy**: Konfigurasi rebase secara default untuk integrasi upstream: `git config --global pull.rebase true`.
- [ ] **Autosquash Hygiene**: Memecah commit ke level atomik dan menyusunnya via `git commit --fixup` sebelum membuka Pull Request.
- [ ] **Kriptografi Terverifikasi**: Menandatangani (*sign*) commit menggunakan kunci SSH atau GPG untuk menjamin integritas author.
  ```bash
  git config --global commit.gpgsign true
  git config --global gpg.format ssh
  git config --global user.signingkey ~/.ssh/id_ed25519.pub
  ```
- [ ] **Enterprise Git Hooks (Husky / Core Hooks)**: Mencegah kegagalan sejak lingkungan lokal:
  * `pre-commit`: Validasi formatting code, static analysis (linting), dan deteksi *hardcoded secrets* (TruffleHog/Gitleaks).
  * `commit-msg`: Validasi format pesan commit berbasis *Conventional Commits* via commitlint.
  * `pre-push`: Menjalankan suite unit test cepat.
- [ ] **Branch Protection Rules (GitHub Enterprise)**:
  * Strict: Require branches to be up to date before merging.
  * Require signed commits: Aktif.
  * Require status checks to pass before merging (CI Gates).
  * Do not allow bypass of the above settings for administrators.

---

## 12. Hands-on Practice

Simpan seluruh hasil latihan praktikum ini pada direktori repositori: `hands-on/m02/`.

### Tahap 1: Inisialisasi Lingkungan & Eksplorasi Database Internal
```bash
mkdir -p hands-on/m02/internal-deep-dive
cd hands-on/m02/internal-deep-dive
git init

# Buat file awal
echo "Architecture Blueprint v1.0" > blueprint.txt
git add blueprint.txt
git commit -m "docs: create architecture blueprint"

# Tinjau isi direktori objects
echo "=== Isi Direktori Objects ==="
find .git/objects -type f

# Ekstraksi tipe dan isi objek commit terakhir menggunakan plumbing cat-file
LATEST_COMMIT=$(git rev-parse HEAD)
echo "Commit Hash: $LATEST_COMMIT"
git cat-file -t "$LATEST_COMMIT"
git cat-file -p "$LATEST_COMMIT"
```

### Tahap 2: Reconstruct History Menggunakan Git Reflog Pasca Bencana
```bash
# Simulasikan kerja harian
echo "Critical Core Engine Logic" > engine.py
git add engine.py
git commit -m "feat(engine): add core processing cycle"

echo "Experimental Code" >> engine.py
git commit -am "feat(engine): introduce experimental async loop"

# BENCANA: Developer sengaja/tidak sengaja melakukan hard reset ke commit awal
git reset --hard HEAD~2

# Verifikasi kondisi: File engine.py lenyap dari working directory
ls -la engine.py || echo "File hilang dari working directory!"

# RECOVERY: Cari pointer commit yang hilang di reflog
git reflog show HEAD

# Ambil commit ID sebelum reset dilakukan (HEAD@{1})
LOST_COMMIT=$(git rev-parse 'HEAD@{1}')
echo "Recovering to commit: $LOST_COMMIT"

# Pulihkan kondisi
git merge "$LOST_COMMIT" --ff-only
ls -la engine.py
echo "File engine.py berhasil dipulihkan tanpa kehilangan data!"
```

### Tahap 3: Implementasi Git Bisect Otomatis Menggunakan Assertion Script
```bash
mkdir -p hands-on/m02/bisect-lab
cd hands-on/m02/bisect-lab
git init

# Buat generator commit untuk simulasi
cat << 'EOF' > test_app.sh
#!/usr/bin/env bash
python3 -c "import sys; data = open('data.txt').read(); sys.exit(0 if 'STABLE' in data else 1)"
EOF
chmod +x test_app.sh

# Commit 1 (Good)
echo "System State: STABLE" > data.txt
git add data.txt test_app.sh
git commit -m "chore: initial release v1.0"
git tag v1.0

# Generate serangkaian commit normal
for i in {1..5}; do
  echo "Log: process iteration $i" >> audit.log
  git add audit.log
  git commit -m "chore(audit): update operation trace $i"
done

# Injeksi Defect / Bug (Bad Commit)
echo "System State: DEGRADED_FAIL" > data.txt
git add data.txt
git commit -m "feat(data): modify system status state"

# Generate commit tambahan setelah bug
for i in {6..10}; do
  echo "Log: process iteration $i" >> audit.log
  git add audit.log
  git commit -m "chore(audit): update operation trace $i"
done

# Jalankan Bisect Runner
git bisect start
git bisect bad HEAD
git bisect good v1.0
git bisect run ./test_app.sh

# Catat commit hasil bisect dan selesaikan
git bisect reset
```

---

## 13. Exercise

### Level: Easy
1. Gunakan plumbing command `git hash-object` untuk menghitung SHA-1 dari string `"Hello Enterprise Git"`. Bandingkan hasilnya dengan hash yang dihasilkan oleh shell command: `printf "blob 20\0Hello Enterprise Git" | sha1sum`. Jelaskan mengapa hasilnya identik.
2. Konfigurasi alias git lokal untuk menampilkan log grafis yang ringkas dan memuat DAG secara jelas dengan format:
   `git log --graph --oneline --decorate --all`. Simpan sebagai alias `git lg`.

### Level: Medium
1. Simulasikan skenario di mana Anda membuat 3 commit terpisah pada branch fitur:
   * Commit A: `feat: add payment controller`
   * Commit B: `fix: resolve typo in variable name`
   * Commit C: `fix: add missing validation logic`
   Gunakan `git rebase -i` untuk menyatukan (*squash/fixup*) Commit B dan C langsung ke Commit A, sehingga menyisakan 1 commit yang bersih tanpa merusak timestamp orisinal dari Commit A secara signifikan.
2. Buat git pre-commit hook lokal sederhana (`.git/hooks/pre-commit`) menggunakan shell script murni yang menolak commit secara otomatis jika terdeteksi string `TODO: DO NOT COMMIT` atau `API_SECRET_KEY` pada file-file yang di-stage (`git diff --cached`).

### Level: Hard
1. Tulis sebuah shell script yang mengurai file commit graph mentah:
   Ambil hash commit terbaru (`HEAD`), parse payload commit menggunakan `git cat-file -p`, temukan tree hash-nya, lakukan rekursi traversal ke seluruh sub-tree dan blob yang ada di dalamnya, lalu cetak peta pohon direktori beserta ukuran byte dari setiap blob tanpa menggunakan perintah `git ls-tree`.

---

## 14. Challenge

### Studi Kasus: Restrukturisasi Monorepo Skala Enterprise
Perusahaan Anda memiliki monorepo berukuran 40GB yang menggabungkan 15 backend services. Manajemen memutuskan untuk memisahkan service bernama `auth-service` ke repositori mandiri tersendiri demi kepatuhan regulasi (PCI-DSS & ISO 27001).

**Ketentuan Tantangan:**
1. Anda harus mengekstrak direktori `services/auth-service/` menjadi repositori baru yang terisolasi.
2. Riwayat commit (*commit history*) yang berkaitan eksklusif dengan `services/auth-service/` **harus dipertahankan secara utuh** sejak commit pertama dibuat hingga sekarang.
3. Seluruh commit history dari 14 service lainnya **harus dimusnahkan secara permanen** dari repositori baru tersebut untuk mencegah kebocoran kode rahasia service lain saat diaudit oleh auditor eksternal.
4. Di repositori baru, isi direktori `services/auth-service/` harus dipromosikan ke root direktori repositori (`/`).
5. Ukuran repositori baru pasca pemisahan tidak boleh menyisakan loose objects atau packfile yang menyimpan referensi ke service lain (Database commit harus diverifikasi bersih menggunakan `git verify-pack`).

*Petunjuk Teknis: Analisis kemampuan alat modern `git-filter-repo` dengan parameter `--subdirectory-filter` dan pembersihan agresif object database via `git gc --prune=now`.*

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic (Pilihan Ganda)
1. Apa fungsi utama dari header objek Git yang berisi `<tipe> <panjang_byte>\0` sebelum konten di-hash?
   * A. Sebagai enkripsi password objek Git.
   * B. Memastikan identitas deterministik unik terhadap tipe data dan ukurannya pada payload SHA-1.
   * C. Memberikan informasi ekstensi file yang disimpan.
   * D. Menentukan hak akses pengguna Linux (CHMOD).

2. Direktori `.git/refs/heads/main` menyimpan informasi berupa:
   * A. Seluruh riwayat zip dari file proyek.
   * B. File teks biasa berisikan 40 karakter SHA-1 commit object yang berada di pucuk cabang main.
   * C. Daftar merge commit yang pernah terjadi.
   * D. Konfigurasi CI/CD cabang main.

3. Kapan Git memindahkan file dari status loose object ke packed object?
   * A. Setiap kali pengembang mengetik `git commit`.
   * B. Ketika perintah `git push` gagal dilakukan.
   * C. Saat proses garbage collection otomatis dipicu (`git gc`) atau manual packfile threshold terlampaui.
   * D. Git tidak pernah memindahkan file yang sudah ditulis.

4. Flag apa yang harus dipasangkan pada perintah `git push --force` untuk memvalidasi bahwa remote pointer belum dimodifikasi oleh orang lain sebelum di-overwrite?
   * A. `--safe`
   * B. `--validate`
   * C. `--strict`
   * D. `--force-with-lease`

5. Algoritma pencarian apa yang mendasari mekanisme pelacakan commit pada `git bisect`?
   * A. Breadth-First Search (BFS)
   * B. Binary Search
   * C. Linear Scan
   * D. Depth-First Search (DFS)

---

### 15.2 Pertanyaan Intermediate (Pilihan Ganda)
6. Manakah dari pernyataan berikut yang paling tepat menggambarkan perbedaan objek `tree` dan objek `blob`?
   * A. Objek `blob` menyimpan metadata nama file dan permission; objek `tree` menyimpan konten file mentah.
   * B. Objek `tree` memetakan nama file, file mode permissions, dan hash blob terkait; objek `blob` murni hanya menyimpan konten data file.
   * C. Objek `tree` menyimpan snapshot commit; objek `blob` menyimpan cabang.
   * D. Objek `blob` berukuran tetap; objek `tree` berukuran dinamis.

7. Mengapa menjalankan `git rebase` pada cabang yang digunakan bersama oleh publik (shared public branch) sangat dilarang?
   * A. Karena Git akan menghapus remote repositori secara otomatis.
   * B. Karena rebase membuat commit baru dengan SHA-1 berbeda untuk perubahan yang sama, merusak DAG rekan satu tim dan memaksa recursive merge yang berantakan.
   * C. Karena rebase memakan memori server Git hingga 100%.
   * D. Karena kompresi packfile server menjadi korup.

8. Jika sebuah commit hilang akibat eksekusi `git reset --hard HEAD~5`, bagaimana status commit tersebut di dalam database internal Git sebelum dibersihkan oleh garbage collector?
   * A. Corrupted Object
   * B. Symbolic Link
   * C. Dangling Commit
   * D. Staged Entity

9. Pada rebase interaktif, apa perbedaan mendasar antara instruksi `squash` dan `fixup`?
   * A. `squash` membuang commit; `fixup` menahan commit.
   * B. `squash` mempertahankan dan menggabungkan deskripsi commit message; `fixup` menggabungkan perubahan kode namun membuang deskripsi commit terkait.
   * C. `squash` bekerja pada branch terpisah; `fixup` bekerja pada commit lokal.
   * D. Tidak ada perbedaan fungsional.

10. Jika file biner 2GB dimasukkan secara tidak sengaja ke Git, lalu di-commit dan di-push, kemudian dihapus pada commit berikutnya menggunakan `git rm`, apa yang terjadi pada ukuran repositori `.git` lokal rekan kerja yang melakukan clone baru?
    * A. Ukuran clone langsung kecil karena file sudah dihapus pada commit terbaru.
    * B. Repositori tetap mengunduh file biner 2GB tersebut karena seluruh riwayat DAG diunduh pada deep clone.
    * C. Kloning akan memunculkan error fatal out-of-memory.
    * D. Git LFS secara otomatis mengisolasi file tersebut.

---

### 15.3 Skenario Kasus Produksi (Analisis Kasus)

11. **Skenario Kasus 1**:
    Seorang engineer secara tidak sengaja mengeksekusi perintah:
    ```bash
    git branch -D payment-v2
    ```
    Cabang tersebut berisikan 12 commit fitur penting yang belum di-push ke remote GitHub. Engineer tersebut panik karena mengira kodenya hilang selamanya.
    Sebagai Lead Architect, jelaskan:
    1. Apakah data tersebut benar-benar musnah seketika? Mengapa?
    2. Tuliskan 2 baris perintah shell Git untuk mengembalikan cabang tersebut secara utuh ke kondisi sebelum terhapus!

12. **Skenario Kasus 2**:
    Pada sebuah pipeline deployment CI/CD, merge queue menerapkan metode "Trunk-Based Development" murni dengan ratusan PR setiap harinya. Seringkali muncul bug tersembunyi yang lolos ke trunk karena developer melakukan testing pada commit lokal yang tertinggal (*out-of-date*) dari HEAD trunk saat ini. 
    Arsitektur proteksi branch apa yang harus diterapkan pada GitHub Enterprise Repository Settings untuk menjamin secara absolut bahwa PR yang di-merge sudah diuji terhadap kode trunk yang paling baru?

13. **Skenario Kasus 3**:
    Sebuah repositori backend monolith mengalami penurunan performa operasi `git fetch` dan `git checkout` secara signifikan (memakan waktu lebih dari 15 menit). Saat diaudit, ditemukan bahwa direktori `.git/objects/pack` berukuran 120GB dan terdapat 500.000 loose objects. 
    Langkah arsitektural teknis apa saja (minimal 3 langkah berurutan) yang harus dilakukan oleh tim Platform Engineering untuk meremajakan performa internal repositori tersebut?

---

### Kunci Jawaban & Pembahasan Evaluasi

#### Jawaban Soal Basic:
1. **B** — Git mendesain penyimpanan berbasis content-addressable storage. Header `<type> <size>\0` disatukan dengan payload sebelum kalkulasi SHA-1 dilakukan guna memastikan tipe data dan integritas ukuran file terikat secara deterministik dalam hash.
2. **B** — Referensi branch di bawah `.git/refs/heads/` hanyalah sebuah file teks biasa yang berisi 40-karakter string SHA-1 dari commit terakhir di cabang tersebut.
3. **C** — Git mengemas loose objects menjadi packfiles saat dipicu oleh command `git gc` (garbage collection) atau ketika Git mendeteksi jumlah loose objects melebihi ambang batas threshold konfigurasi (`gc.auto`).
4. **D** — Flag `--force-with-lease` mengecek kondisi referensi lokal remote tracker (`refs/remotes/...`) dengan kondisi aktual branch pada remote server. Jika ada commit baru dari orang lain, push ditolak.
5. **B** — `git bisect` mengimplementasikan Binary Search $O(\log N)$ untuk mempercepat pelacakan commit rusak di antara ribuan commit history.

#### Jawaban Soal Intermediate:
6. **B** — Blob murni menyimpan isi konten data. Struktur penamaan file, direktori bertingkat, dan atribut permission (mode) diatur dan disimpan oleh objek terpisah bertipe `tree`.
7. **B** — Rebase menulis ulang riwayat commit dengan cara mengalkulasi SHA hash commit baru. Melakukan ini pada commit yang sudah ditarik oleh orang lain akan menyebabkan divergensi commit DAG yang parah.
8. **C** — Commit yang tidak lagi memiliki pointer/referensi (baik dari branch, tag, maupun HEAD) disebut *dangling commit*. Objeknya masih ada di disk sebelum garbage collection dijalankan.
9. **B** — `squash` memadukan perubahan file sekaligus membuka editor teks untuk menggabungkan commit message. `fixup` menyatukan perubahan file secara instan dan mengabaikan/membuang pesan commit tersebut.
10. **B** — Git mendistribusikan seluruh riwayat DAG secara komprehensif saat clone default. Meskipun file sudah dihapus pada commit terbaru, blob 2GB tersebut tetap berada pada commit lama dalam riwayat proyek.

#### Pembahasan Skenario Kasus Produksi:
11. **Analisis Skenario 1**:
    * **Status Data**: Data belum musnah. Git menerapkan prinsip *append-only storage*. Objek commit dan blob masih berada utuh di dalam `.git/objects/`. Hanya pointer referensi cabang di `.git/refs/heads/payment-v2` yang dihapus. Data akan bertahan hingga masa retention default git reflog / prune terlampaui (biasanya 30-90 hari).
    * **Langkah Pemulihan**:
      ```bash
      # 1. Cari hash commit terakhir dari branch yang dihapus via reflog
      LAST_COMMIT=$(git reflog show | grep -i "payment-v2" | head -n 1 | awk '{print $1}')
      # 2. Bangkitkan kembali branch dari commit hash tersebut
      git branch payment-v2 $LAST_COMMIT
      ```

12. **Analisis Skenario 2**:
    Platform Engineering harus menerapkan konfigurasi GitHub Branch Protection / Rulesets:
    1. Aktifkan **"Require branches to be up to date before merging"** (Strict status checks). Ini memaksa cabang PR untuk di-rebase atau di-merge terhadap HEAD trunk terkini sebelum tombol merge bisa aktif.
    2. Terapkan fitur **"GitHub Merge Queue"**. Merge Queue secara otomatis membuat temporary branch yang menggabungkan PR dengan HEAD trunk terbaru, mengeksekusi test pipeline, dan jika lolos, langsung menggabungkannya ke trunk secara serial tanpa campur tangan manual.

13. **Analisis Skenario 3**:
    Langkah mitigasi arsitektur peremajaan repositori:
    1. **Pembersihan dan Repacking Objek Repositori**:
       Jalankan pembersihan agresif loose objects dan optimasi packfile:
       ```bash
       git prune --expire=now
       git repack -a -d -f --depth=250 --window=250
       git gc --prune=now --aggressive
       ```
    2. **Migrasi Binary Blobs ke Git LFS / Purge History**:
       Gunakan `git-filter-repo` untuk membedah riwayat dan memindahkan seluruh file binary di atas threshold tertentu (contoh: >10MB) keluar dari Git DAG menuju Git Large File Storage (LFS).
    3. **Terapkan Sparse-Checkout & Partial Clone**:
       Ubah alur kerja developer monolith menggunakan strategi partial checkout:
       ```bash
       git clone --filter=blob:none <repo-url>
       git sparse-checkout set <service-yang-dikerjakan>
       ```
       Hal ini membuat developer hanya mengunduh metadata dan source code yang relevan secara on-demand, mereduksi waktu clone dari 15 menit menjadi di bawah 30 detik.

---

## 16. Summary

1. **Sifat Hakiki Git**: Git adalah *Content-Addressable Key-Value Database* berbasis snapshot terenkapsulasi kompresi zlib, bukan database file differential/delta. Seluruh arsitektur dibangun di atas 4 objek fundamental: `blob`, `tree`, `commit`, dan `annotated tag`.
2. **Kekuatan Riwayat DAG**: Riwayat Git berbentuk *Directed Acyclic Graph*. Operasi branch dan tag hanyalah manipulasi teks pointer 40-karakter ke commit object; mereka tidak mereplikasi codebase secara fisik.
3. **Disaster Recovery**: Kehilangan kode di Git lokal hampir mustahil terjadi selama perubahan sudah pernah di-stage atau di-commit. `git reflog` bertindak sebagai audit log absolut dari mutasi referensi HEAD lokal yang memungkinkan rekonstruksi kondisi sebelum insiden terjadi.
4. **Otomatisasi Kualitas Enterprise**: Pemanfaatan `git bisect` berbasis skrip otomasi memangkas waktu investigasi regresi perangkat lunak secara eksponensial ($O(\log N)$).
5. **Skalabilitas Produksi**: Skalabilitas repositori enterprise memerlukan kompromi sadar antara model riwayat linear (*rebase/squash*) dengan non-linear, penerapan proteksi commit signing (SSH/GPG), isolasi artefak biner melalui Git LFS, serta optimalisasi packfile database secara teratur.