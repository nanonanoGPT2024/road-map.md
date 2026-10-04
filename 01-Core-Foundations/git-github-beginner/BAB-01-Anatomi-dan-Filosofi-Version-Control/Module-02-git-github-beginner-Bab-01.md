# BAB 01: Fondasi & Arsitektur
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis Arsitektur Internal Git:** Membedah struktur direktori `.git/`, memverifikasi integritas *Content-Addressable Storage*, serta merekonstruksi relasi antar objek *Directed Acyclic Graph* (DAG) pada tingkat *byte-level*.
2. **Mengoperasikan Plumbing Commands:** Mengonstruksi komit produksi secara manual menggunakan perintah *plumbing* (`hash-object`, `update-index`, `write-tree`, `commit-tree`, `update-ref`) tanpa bantuan *porcelain commands*.
3. **Mendiagnosis dan Memitigasi Kerusakan Repository:** Mengisolasi *dangling commits*, memulihkan *detached HEAD state*, serta merekonstruksi indeks yang korup menggunakan `git fsck` dan `git reflog`.
4. **Merancang Topologi Repository Skala Enterprise:** Menentukan strategi *branching*, konfigurasi `.gitattributes`, optimasi Git Monorepo (*sparse-checkout*, *scalar*, *commit-graph*), serta integrasi penandatanganan kriptografis (GPG/SSH).

---

### 2. Prerequisite

Peserta wajib menguasai:
* Operasional dasar terminal UNIX/Linux (manajemen file, *piping*, manipulasi *standard stream*, hexdump/xxd, zlib utilities).
* Pemahaman fundamental siklus hidup file Git: *Untracked*, *Modified*, *Staged*, *Committed*.
* Penggunaan dasar Porcelain Git: `git init`, `git add`, `git commit`, `git status`, `git branch`.
* Konsep kriptografi dasar: Fungsi *hash* kriptografis (SHA-1, SHA-256) dan pasangan kunci asimetris (*public-private key*).

---

### 3. Concept & Internal Architecture (Mendalam)

Git pada intinya bukanlah sistem pelacak revisi berbasis delta berkas (*delta-based version control system*), melainkan sebuah **Content-Addressable Key-Value Data Store** yang dipadukan dengan mesin pengelola struktur pohon direktori (*Merkle Tree*) di atas sistem berkas lokal.

#### 3.1 Anatomi Internal Direktori `.git/`

Saat `git init` dieksekusi, Git mengalokasikan struktur database internal di bawah direktori `.git/`:

```
.git/
├── HEAD               # Pointer simbolik ke branch aktif saat ini (contoh: ref: refs/heads/main)
├── config             # File konfigurasi spesifik repositori (prioritas lokal)
├── description        # Deskripsi proyek (digunakan oleh GitWeb)
├── hooks/             # Skrip automasi sisi klien & server (pre-commit, post-merge, dll)
├── info/
│   └── exclude        # Aturan ignore lokal tanpa harus komit ke .gitignore
├── index              # Biner cache: staging area yang memetakan working tree ke object store
├── objects/           # Object database (Content-Addressable Store)
│   ├── [0-9a-f]{2}/   # Fan-out direktori (2 karakter pertama dari hash SHA-1/256)
│   ├── info/          # Metadata packfile
│   └── pack/          # Objek terkompresi delta dalam file .pack dan indeks .idx
└── refs/              # Namespace pointer referensi
    ├── heads/         # Pointers commit lokal (Branches)
    ├── tags/          # Pointers tag release (Lightweight vs Annotated)
    └── remotes/       # Pointers tracking repositori upstream
```

#### 3.2 Model Data: Empat Objek Inti Git

Setiap entitas dalam database Git dimampatkan menggunakan algoritma `zlib Deflate` dan diberi identitas berupa *hash* SHA-1 (160-bit / 40 digit heksadesimal) atau SHA-256 (256-bit / 64 digit heksadesimal). Format raw data sebelum di-hash selalu mengikuti standar:

$$\text{Format Payload} = \langle\text{type}\rangle\ \langle\text{size-in-bytes}\rangle\backslash 0\langle\text{content}\rangle$$

1. **Blob (`blob`):** Menyimpan data mentah file pengguna. Objek blob **tidak** menyimpan nama file, atribut izin file (*file permissions*), maupun stempel waktu (*timestamp*). Dua file berbeda nama dengan isi byte yang identik akan merujuk ke satu blob yang sama.
2. **Tree (`tree`):** Berfungsi sebagai representasi direktori sistem berkas. Sebuah *tree* berisi daftar *entry*, di mana setiap *entry* mencakup: mode izin file (misal: `100644` untuk standard file, `100755` untuk executable, `040000` untuk direktori/sub-tree), tipe objek, hash SHA objek target, dan nama file/direktori.
3. **Commit (`commit`):** Titik simpul (node) permanen dalam grafik Git. Objek commit membungkus metadata: hash dari *root tree*, hash commit induk (*parent commits* — nol untuk root commit, satu untuk commit standar, dua atau lebih untuk merge commit), data identitas *author* dan *committer* (nama, email, epoch timestamp, timezone offset), serta pesan komit (*commit message*).
4. **Annotated Tag (`tag`):** Mirip dengan objek komit, tetapi menunjuk langsung ke commit target dengan menyertakan tanda tangan digital (opsional), pesan tag, data penandatangan (*tagger*), dan metadata waktu.

```
       +-------------------------------------------------------+
       |                  COMMIT OBJECT                        |
       |  tree: e9b56f...                                      |
       |  parent: 7c12a4...                                    |
       |  author: Principal Eng <arch@corp.com> 1708819200 +0700|
       |  committer: Principal Eng ...                         |
       |  [Commit Message: chore: migrate auth engine]         |
       +---------------------------+---------------------------+
                                   |
                                   v
       +-------------------------------------------------------+
       |                   ROOT TREE OBJECT                    |
       |  100644 blob a381b9...    README.md                   |
       |  040000 tree d42f11...    src                         |
       +---------------------------+---------------------------+
                                   |
                                   v
       +-------------------------------------------------------+
       |                   SUB-TREE OBJECT                     |
       |  100644 blob c89f2a...    main.go                     |
       +---------------------------+---------------------------+
                                   |
                                   v
       +-------------------------------------------------------+
       |                     BLOB OBJECT                       |
       |  package main; func Main() { ... }                    |
       +-------------------------------------------------------+
```

#### 3.3 Struktur Biner File `index` (Staging Area)

File `.git/index` adalah file biner terurut berdasarkan nama path file. Header file index berukuran 12 byte:
* 4 byte: Tanda tangan (*magic number*) `DIRC` (*Directory Cache*).
* 4 byte: Versi format indeks (umumnya versi 2, 3, atau 4).
* 4 byte: Jumlah total entri file dalam indeks.

Setiap entri file mencatat metadata POSIX `stat`: waktu `ctime` dan `mtime`, dev/ino, mode file, UID/GID, ukuran file, SHA-1/256 objek blob yang valid, dan flags (termasuk status bit merge-conflict *stage 0 s.d. 3*).

---

### 4. Why & What

| Paradigma | Git (Snapshot Directed Acyclic Graph) | VCS Tradisional (Delta-Based/RCS/SVN) |
| :--- | :--- | :--- |
| **Model Penyimpanan Data** | Snapshot lengkap dari seluruh repositori di setiap titik komit, diduplikasi secara efisien melalui hashing & pointer. | Rangkaian berkas basis (*base files*) yang disusul oleh deretan perbedaan diferensial (*diff deltas*). |
| **Pemeriksaan Integritas** | Validasi integritas kriptografis total menggunakan Merkle Tree. Integritas data diverifikasi secara implisit via SHA. | Tidak ada penjaminan kriptografis terhadap integritas isi berkas dari bit-rot atau manipulasi lokal. |
| **Kompleksitas Percabangan** | Pembuatan cabang bersifat instant $\mathcal{O}(1)$. Branch hanyalah berkas 41-byte berisi string hash commit. | Cabang adalah duplikasi folder virtual pada server remote, memakan ruang linier $\mathcal{O}(N)$ dan latensi tinggi. |
| **Dependensi Jaringan** | Terdesentralisasi penuh (*fully distributed*). Semua operasi (kecuali transfer data jaringan) berjalan lokal $\mathcal{O}(1)$. | Bergantung penuh pada latensi server pusat (*centralized lock/checkout*). Operasi offline sangat terbatas. |

---

### 5. How (Workflow Detail)

#### 5.1 Siklus Hidup Objek via Pure Plumbing Execution

Secara mekanik, Git mengeksekusi konversi dari teks kode sumber menuju node commit melalui lima layer isolasi perintah plumbing:

```
[File Kerja di Disk]
        │
        ▼ (git hash-object -w)
[Objek Blob di .git/objects/]
        │
        ▼ (git update-index --add)
[Registrasi ke Staging Index .git/index]
        │
        ▼ (git write-tree)
[Objek Tree di .git/objects/]
        │
        ▼ (git commit-tree)
[Objek Commit di .git/objects/]
        │
        ▼ (git update-ref)
[Pembaruan Referensi Cabang di .git/refs/heads/]
```

#### 5.2 Algoritma Resolusi 3-Way Merge

Saat menggabungkan dua cabang (misal branch target `HEAD` dan branch sumber `FEATURE`), Git mencari **Lowest Common Ancestor (LCA)** sebagai basis (*Base Commit*).

Git membedah komparasi multi-jalur:
1. $B$ = Base Commit (LCA)
2. $O$ = Ours Commit (`HEAD`)
3. $T$ = Theirs Commit (`FEATURE`)

Jika perubahan pada file $F$ memenuhi kondisi:
* $O(F) \neq B(F)$ dan $T(F) == B(F)$, maka hasil akhir mengambil $O(F)$ otomatis.
* $T(F) \neq B(F)$ dan $O(F) == B(F)$, maka hasil akhir mengambil $T(F)$ otomatis.
* $O(F) \neq B(F)$ dan $T(F) \neq B(F)$ dengan modifikasi pada chunk baris yang berbeda, maka Git menyatukan (*clean merge*).
* $O(F) \neq B(F)$ dan $T(F) \neq B(F)$ pada chunk baris yang tumpang tindih (*overlapping*), Git menghentikan otomasi, menetapkan status stage ke indeks:
  * Stage 1: Versi $B$ (LCA)
  * Stage 2: Versi $O$ (Ours)
  * Stage 3: Versi $T$ (Theirs)
  File kerja ditandai dengan konflik teks standar (`<<<<<<<`, `=======`, `>>>>>>>`).

---

### 6. Analogy & Diagram ASCII

#### 6.1 Analogi Sistem Git

Git bekerja persis seperti sebuah **Brankas Dokumen Kriptografis Abadi**:
* **Blob** adalah lembaran dokumen terisolasi tanpa judul. Dokumen ini diberi stempel sidik jari unik (*hash*). Jika ada dokumen dengan isi huruf yang sama persis, brankas tidak mencetak ulang; brankas hanya menggunakan kembali salinan yang sudah ada.
* **Tree** adalah amplop transparan berlabel yang berisi daftar nomor sidik jari lembaran dokumen beserta nama map-nya.
* **Commit** adalah berita acara resmi bersegel lilin yang menyatakan: *"Amplop utama saat ini berada pada kondisi tree X, ditandatangani oleh Engineer Y pada jam Z, dan disusun persis di atas berita acara sebelumnya (Parent Commit)."*
* **Branch** hanyalah sebuah sticky note kecil bertuliskan nama yang ditempelkan di atas salah satu segel berita acara. Memindahkan branch cukup dengan melepas sticky note dan menempelkannya ke berita acara yang lain.

#### 6.2 Visualisasi Siklus Internal Plumbing Engine

```
+-----------------------------------------------------------------------------+
|                                WORKING TREE                                 |
| File: core.go ("package engine\nfunc Run(){}")                             |
+-----------------------------------------------------------------------------+
       │
       │ 1. git hash-object -w core.go
       ▼
+-----------------------------------------------------------------------------+
|                          .git/objects/ STORAGE                              |
| SHA: 8a4c1f9d45e0c6...                                                      |
| Header: blob 32\0                                                           |
| Body:   package engine\nfunc Run(){}                                        |
+-----------------------------------------------------------------------------+
       │
       │ 2. git update-index --add --cacheinfo 100644 8a4c1f... core.go
       ▼
+-----------------------------------------------------------------------------+
|                            .git/index (BINARY)                              |
| Entries:                                                                    |
| [mode: 100644, sha: 8a4c1f..., path: core.go, stage: 0, stat_cached: ...] |
+-----------------------------------------------------------------------------+
       │
       │ 3. git write-tree
       ▼
+-----------------------------------------------------------------------------+
|                          .git/objects/ STORAGE                              |
| SHA: c2e811bc009a...                                                        |
| Type: TREE                                                                  |
| Content: 100644 blob 8a4c1f...    core.go                                   |
+-----------------------------------------------------------------------------+
       │
       │ 4. git commit-tree c2e811... -m "feat: init engine"
       ▼
+-----------------------------------------------------------------------------+
|                          .git/objects/ STORAGE                              |
| SHA: f5d398ca71b2...                                                        |
| Type: COMMIT                                                                |
| Content:                                                                    |
|   tree c2e811...                                                            |
|   author Dev Lead <lead@corp.com> 1708819200 +0000                          |
|   committer Dev Lead <lead@corp.com> 1708819200 +0000                       |
|                                                                             |
|   feat: init engine                                                         |
+-----------------------------------------------------------------------------+
       │
       │ 5. git update-ref refs/heads/main f5d398...
       ▼
+-----------------------------------------------------------------------------+
|                         .git/refs/heads/main                                |
| Plain text file: f5d398ca71b2...                                            |
+-----------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Rekonstruksi Commit via Pure Low-Level Plumbing

Kita membuat repositori dan mengeksekusi *commit* tanpa perintah `git add` atau `git commit`.

```bash
# 1. Inisialisasi workspace terisolasi
mkdir -p /tmp/git-plumbing-sandbox && cd /tmp/git-plumbing-sandbox
git init

# 2. Buat file fisik di working tree
echo "package main" > main.go

# 3. Buat objek blob langsung ke object store, tangkap hash-nya
BLOB_SHA=$(git hash-object -w main.go)
echo "Blob Generated: ${BLOB_SHA}"

# 4. Registrasikan blob ke file index staging area
git update-index --add --cacheinfo 100644 "${BLOB_SHA}" main.go

# 5. Konversi index menjadi objek tree biner
TREE_SHA=$(git write-tree)
echo "Tree Generated: ${TREE_SHA}"

# 6. Buat objek commit dari tree yang telah terdaftar
COMMIT_SHA=$(git commit-tree "${TREE_SHA}" -m "feat(core): initialize bootstrap via low-level engine")
echo "Commit Generated: ${COMMIT_SHA}"

# 7. Arahkan pointer branch main ke commit yang baru dibuat
git update-ref refs/heads/main "${COMMIT_SHA}"

# 8. Set simbolik HEAD ke branch main
git symbolic-ref HEAD refs/heads/main

# 9. Verifikasi integritas status via porcelain command standar
git log -1 --stat
git status
```

#### 7.2 Practical Example: Dekompilasi Objek Biner Menggunakan Scripting Bash

Memverifikasi isi objek mentah langsung dari penyimpanan disk `.git/objects/` menggunakan dekompresi zlib internal:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Ambil commit SHA terakhir dari repository aktif
TARGET_COMMIT=$(git rev-parse HEAD)
DIR_PREFIX="${TARGET_COMMIT:0:2}"
OBJECT_FILE="${TARGET_COMMIT:2}"
PATH_TO_OBJECT=".git/objects/${DIR_PREFIX}/${OBJECT_FILE}"

echo "Locating object: ${PATH_TO_OBJECT}"

# Objek Git di-compress dengan zlib. Kita dekompresi menggunakan script Python one-liner
RAW_CONTENT=$(python3 -c "import zlib; print(open('${PATH_TO_OBJECT}', 'rb').read())" | python3 -c "import sys, zlib; sys.stdout.buffer.write(zlib.decompress(sys.stdin.buffer.read()))")

echo "=== RAW DECOMPRESSED OBJECT STREAM ==="
echo "${RAW_CONTENT}"
echo "======================================"

# Validasi terhadap Git Porcelain
echo "=== GIT CAT-FILE VERIFICATION ==="
git cat-file -p "${TARGET_COMMIT}"
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Degradasi Performa Monorepo 300GB & Latensi I/O pada FinTech Skala Besar

* **Konteks:** Perusahaan institusi finansial dengan tim rekayasa perangkat lunak berisi 1.200 engineer mengelola repositori monorepo terpadu berukuran 300GB dengan 4,5 juta objek Git.
* **Gejala Masalah:**
  1. Operasi harian `git status` membutuhkan waktu $42\text{ detik}$.
  2. Perintah `git checkout` memicu I/O thrashing sistem berkas lokal selama $\pm 3\text{ menit}$.
  3. Proses clone baru pada infrastruktur CI/CD *runner* membutuhkan waktu $1,5\text{ jam}$, memboroskan alokasi bandwidth jaringan hingga 60TB/bulan.
* **Akar Masalah (Root Cause Analysis):**
  1. File `.git/index` membengkak hingga $850\text{ MB}$, memaksa operasi `lstat()` sistem berkas dilakukan secara masif terhadap ratusan ribu file setiap kali `git status` dipanggil.
  2. Graph traversal Git mengalami perlambatan non-linear karena file objek pack (`.pack`) terfragmentasi ke dalam 2.000 file terpisah tanpa metadata ringkas.
* **Solusi Arsitektural Multi-Layer:**

```bash
# 1. Aktifkan Scalar Engine & Sparse-Checkout untuk membatasi working tree pada domain kerja tim
scalar register
git sparse-checkout set --cone services/order-processor services/payment-gateway

# 2. Aktifkan Git Filesystem Monitor (FSMonitor) berbasis daemon native OS
git config core.fsmonitor true
git config core.untrackedCache true

# 3. Konsolidasi packfiles & generasikan Commit-Graph file untuk optimasi DAG traversal
git repack -A -d --geometric=2
git multi-pack-index write --bitmap
git commit-graph write --reachable --changed-paths

# 4. Pipeline CI/CD dikonfigurasi menggunakan shallow & blobless clone
git clone --filter=blob:none --no-checkout --depth=1 https://internal-vcs.corp/monorepo.git .
```

* **Dampak Metrik Pasca Optimasi:**
  * Waktu eksekusi `git status` anjlok dari **42 detik** menjadi **0,18 detik** (peningkatan $\approx 230\times$).
  * Waktu inisialisasi lingkungan kerja local checkout berkurang dari **3 menit** menjadi **4 detik**.
  * Waktu build pipeline CI berkurang dari **1,5 jam** menjadi **11 detik** per node eksekusi.

---

### 9. Trade-offs

| Pendekatan Rekayasa | Keuntungan | Kompensasi / Kerugian (Trade-offs) | Skenario Rekomendasi |
| :--- | :--- | :--- | :--- |
| **Merge Commits (`--no-ff`)** | Mempertahankan topologi cabang secara utuh. Merefleksikan sejarah kronologis integrasi fitur secara eksak. | Memperumit pembacaan grafik history Git. Mempersulit operasi `git bisect` bila terdapat merge commit multi-cabang yang kusut. | Enterprise dengan audit compliance ketat yang membutuhkan riwayat branch merge formal. |
| **Linear History (Rebase & Fast-Forward)** | Histori commit bersih dan lurus searah linier. Mempermudah navigasi `git log` dan otomatisasi CI/CD rollback. | Mengubah identitas hash SHA secara permanen (*history rewriting*). Berisiko tinggi bila dieksekusi pada branch kolaboratif publik. | Trunk-based development dengan pull-request bersiklus pendek (*short-lived feature branches*). |
| **Squash and Merge** | Mengabstraksi noise commit lokal (*"wip"*, *"fix lint"*) menjadi 1 commit terpadu pada branch integrasi. | Menghilangkan perincian granular historis perkembangan kode secara mikro dari penulis aslinya. | Sistem integrasi microservices di mana setiap Pull Request merepresentasikan satu unit deployment atomik. |
| **Full Clone vs Blobless Clone (`--filter=blob:none`)** | Full Clone menyediakan salinan offline 100% independen dari remote server. | Blobless Clone menghemat storage hingga 90% pada repositori masif, tetapi membutuhkan koneksi remote setiap kali mengakses commit lawas. | Gunakan Full Clone untuk repositori standar ($<2\text{GB}$). Wajibkan Blobless Clone untuk Monorepo masif dan CI/CD worker. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Kehilangan Pekerjaan Akibat *Detached HEAD State*

* **Kondisi:** Developer mengeksekusi `git checkout <commit-sha>`, membuat beberapa commit penting, lalu kembali ke branch utama dengan `git checkout main`. Semua commit yang dibuat sebelumnya tampak hilang.
* **Penyebab:** Objek commit baru dibuat dengan `HEAD` menunjuk langsung ke commit SHA, bukan ke pointer referensi cabang (`refs/heads/*`). Saat pindah branch, commit-commit tersebut menjadi *orphan / dangling commits*.
* **Penanganan & Pemulihan:**

```bash
# 1. Lacak jejak perpindahan HEAD menggunakan reflog
git reflog show HEAD

# Output contoh:
# e1a2b3c HEAD@{0}: checkout: moving from e1a2b3c to main
# e1a2b3c HEAD@{1}: commit: feat(security): critical patch on crypto engine
# 9f8e7d6 HEAD@{2}: checkout: moving from main to 9f8e7d6

# 2. Selamatkan commit yang mengambang ke branch permanen baru
git branch recovery-crypto-patch e1a2b3c

# 3. Hubungkan branch baru tersebut kembali ke workflow produksi
git checkout recovery-crypto-patch
```

#### 10.2 Penanganan *Index Lock Collision*

* **Kondisi:** Muncul pesan fatal: `fatal: Unable to create '.git/index.lock': File exists.`
* **Penyebab:** Proses Git sebelumnya (seperti IDE linter background check atau CLI) terminated secara abnormal (SIGKILL) saat sedang memodifikasi staging index, meninggalkan lockfile aktif.
* **Penanganan Aman Tanpa Data Loss:**

```bash
# 1. Verifikasi apakah ada proses git yang masih aktif berjalan
ps aux | grep git

# 2. HENTIKAN proses orphan bila ada (misal PID: 49302)
kill -9 49302 2>/dev/null || true

# 3. Hapus index lock secara manual setelah dipastikan tidak ada proses yang menulis
rm -f .git/index.lock

# 4. Validasi integritas indeks repositori
git status
```

---

### 11. Best Practices (Production Checklist)

* [ ] **Konfigurasi Identitas Baku:** Tetapkan identitas committer global yang tervalidasi dengan email SSO perusahaan:
  ```bash
  git config --global user.name "Firstname Lastname"
  git config --global user.email "account@enterprise.corp"
  ```
* [ ] **Penandatanganan Kriptografis Wajib (GPG/SSH Signing):**
  ```bash
  git config --global commit.gpgsign true
  git config --global gpg.format ssh
  git config --global user.signingkey ~/.ssh/id_ed25519_signing.pub
  ```
* [ ] **Normalisasi End-of-Line (EOL):** Konfigurasikan `.gitattributes` di root repositori untuk mencegah kerusakan checksum file antar sistem operasi:
  ```gitattributes
  * text=auto eol=lf
  *.bat text eol=crlf
  *.png binary
  *.jpg binary
  *.jar binary
  ```
* [ ] **Konfigurasi Git Safe Directories:** Mencegah eksploitasi eskalasi privilese direktori lokal:
  ```bash
  git config --global --add safe.directory /workspace
  ```
* [ ] **Automasi Garbage Collection & Maintenance:** Pastikan background maintenance aktif untuk repositori aktif berukuran besar:
  ```bash
  git maintenance start
  ```

---

### 12. Hands-on Practice

Target path: Jalankan seluruh runtutan instruksi ini pada workspace lokal Anda: `hands-on/m02/`.

```bash
#!/usr/bin/env bash
# Hands-on M02: Simulasi Bedah Arsitektur & Manipulasi Index

# Langkah 1: Persiapan Workspace Hands-on
mkdir -p hands-on/m02/architecture-lab
cd hands-on/m02/architecture-lab
git init

# Langkah 2: Eksplorasi Struktur Internal Awal
echo "Verifikasi direktori internals awal:"
ls -la .git/

# Langkah 3: Membuat Objek Menggunakan Hashing Kriptografis
echo "console.log('Production Kernel Initialized');" > kernel.js
BLOB_HASH=$(git hash-object -w kernel.js)
echo "Blob Generated dengan Hash: ${BLOB_HASH}"

# Langkah 4: Verifikasi Tipe & Isi Objek Menggunakan cat-file
echo -n "Tipe objek: "
git cat-file -t "${BLOB_HASH}"
echo -n "Ukuran objek: "
git cat-file -s "${BLOB_HASH}"
echo "Isi objek:"
git cat-file -p "${BLOB_HASH}"

# Langkah 5: Registrasi File ke Stage 0 secara Manual
git update-index --add --cacheinfo 100644 "${BLOB_HASH}" src/kernel.js

# Langkah 6: Tulis Struktur Directory Tree ke Object Database
ROOT_TREE=$(git write-tree)
echo "Root Tree Generated: ${ROOT_TREE}"
git cat-file -p "${ROOT_TREE}"

# Langkah 7: Pembuatan Node Commit Pertama
FIRST_COMMIT=$(git commit-tree "${ROOT_TREE}" -m "feat(kernel): bootstrap system core")
echo "Commit Root Node: ${FIRST_COMMIT}"

# Langkah 8: Mengaitkan Referensi Branch Produksi
git update-ref refs/heads/main "${FIRST_COMMIT}"
git symbolic-ref HEAD refs/heads/main

# Langkah 9: Verifikasi Status Kerja (Working Tree harus sinkron penuh)
git status
git log --graph --oneline

# Langkah 10: Simulasi dan Bedah Merge Conflict Tiga-Arah pada Level Index
git checkout -b feature-a
echo "console.log('Production Kernel: Variant A');" > src/kernel.js
git commit -am "feat: update variant a"

git checkout main
git checkout -b feature-b
echo "console.log('Production Kernel: Variant B');" > src/kernel.js
git commit -am "feat: update variant b"

git checkout main
git merge feature-a --no-ff -m "merge: integration branch a"

echo "Memicu konflik merge buatan:"
git merge feature-b || true

echo "Daftar entri stage pada Index File pasca konflik (Stage 1, 2, 3):"
git ls-files --stage

echo "Inspeksi isi tiap stage konflik:"
echo "--- BASE (Stage 1) ---"
git cat-file -p $(git ls-files --stage src/kernel.js | grep " 1\t" | awk '{print $2}')
echo "--- OURS (Stage 2) ---"
git cat-file -p $(git ls-files --stage src/kernel.js | grep " 2\t" | awk '{print $2}')
echo "--- THEIRS (Stage 3) ---"
git cat-file -p $(git ls-files --stage src/kernel.js | grep " 3\t" | awk '{print $2}')

# Langkah 11: Resolusi Konflik Manual Berbasis Stage Checkout
git checkout --ours src/kernel.js
git add src/kernel.js
git commit -m "fix(merge): resolve conflict prioritizing main variant"

echo "Praktikum selesai dengan sukses. Pohon DAG terverifikasi."
git log --graph --oneline -n 5
```

---

### 13. Exercise

#### Level Easy
Ekstrak isi dari commit root tertua pada sebuah repositori aktif lokal Anda menggunakan kombinasi `git rev-list --max-parents=0 HEAD` dan `git cat-file -p`. Dilarang menggunakan perintah `git show` atau `git log`.

#### Level Medium
Sebuah commit telah dibuat secara tidak sengaja langsung di branch `main`. Buat skrip bash untuk memindahkan commit tersebut ke branch baru bernama `hotfix/security-patch`, kemudian kembalikan pointer `main` ke commit sebelumnya **tanpa** menyentuh working tree dan **tanpa** menggunakan perintah `git reset --hard`.

#### Level Hard
Simulasikan insiden di mana file `.git/refs/heads/main` terhapus secara permanen via perintah `rm .git/refs/heads/main` dan `git reflog expire --expire=now --all` telah dijalankan. Rekonstruksi kembali pointer branch `main` tersebut ke status state commit terakhir menggunakan utilitas `git fsck` dan analisis objek type commit.

---

### 14. Challenge

**Studi Kasus:** Sebuah platform transaksi pembayaran enterprise mengalami insiden push data kredensial AWS secret (`AKIA...` dan secret key mentah) ke repository publik GitHub 3 jam yang lalu. Sejak kejadian tersebut, telah masuk 15 commit baru dari 4 engineer berbeda pada beberapa cabang fitur yang terintegrasi secara aktif.

**Tugas Anda:**
1. Rancang arsitektur strategi sanitasi permanen untuk menghapus blob file kredensial tersebut dari seluruh histori commit repositori (seluruh rantai DAG).
2. Prosedur tidak boleh merusak metadata commit lainnya (identitas author asli, timestamp, commit messages dari commit yang sah tidak boleh terdampak kecuali parent-child relationship yang ter-rehash).
3. Buat rancangan mitigasi teknis agar proses rewriting history tersebut tidak memicu split-brain conflict yang meluas di workstation 1.200 engineer lain yang memegang salinan clone repositori lama.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Pertanyaan Basic (5 Soal)
1. Di mana Git menyimpan data nama file dari suatu script yang Anda buat?
   * *Jawaban:* Di dalam objek **Tree**, bukan di dalam objek **Blob**.
2. Apa yang tersimpan secara fisik di dalam berkas teks `.git/refs/heads/main`?
   * *Jawaban:* Tepat 40 karakter heksadesimal (SHA-1) atau 64 karakter (SHA-256) yang merujuk pada hash unik dari commit paling ujung pada cabang tersebut, diikuti oleh karakter *newline*.
3. Apa perbedaan esensial antara *Lightweight Tag* dan *Annotated Tag* pada level arsitektur objek Git?
   * *Jawaban:* Lightweight tag hanyalah pointer referensi teks mentah di bawah `.git/refs/tags/` yang menunjuk langsung ke sebuah commit SHA. Annotated tag adalah objek independen di dalam `.git/objects/` yang memiliki hash tersendiri, membawa metadata tagger, tanggal, pesan deskripsi, dan dapat ditandatangani via GPG.
4. Apa fungsi dari angka `100644` yang muncul di samping metadata entri objek tree?
   * *Jawaban:* Itu adalah representasi mode izin file format POSIX standar yang menandakan *regular non-executable user-space file*.
5. Kapan Git secara internal memicu pembentukan file `.pack` dari sekumpulan loose objects di `.git/objects/`?
   * *Jawaban:* Saat ambang batas jumlah loose objects terlampaui (otomatisasi via auto `git gc`), atau saat transfer jaringan dieksekusi (`git push`, `git fetch`), atau saat dipicu manual via `git repack`.

#### Bagian B: Pertanyaan Intermediate (5 Soal)
6. Apa representasi status dari file yang berada pada Stage 1, Stage 2, dan Stage 3 saat terjadi merge conflict di staging index?
   * *Jawaban:* Stage 1 adalah snapshot file dari Lowest Common Ancestor (Base). Stage 2 adalah snapshot file dari branch target saat ini (Ours/HEAD). Stage 3 adalah snapshot file dari branch eksternal yang sedang digabungkan (Theirs).
7. Mengapa penambahan baris spasi kosong pada sebuah file menghasilkan Blob SHA yang sama sekali berbeda, sedangkan mengubah nama file tanpa mengubah isinya menghasilkan Blob SHA yang persis sama?
   * *Jawaban:* Karena Git adalah *Content-Addressable Storage*. Hash dihitung secara matematis semata-mata dari muatan header dan isi byte berkas (`blob <size>\0<content>`). Nama file disimpan di luar berkas (di dalam Tree), sehingga perubahan nama tidak menyentuh konten blob.
8. Apa peran biner *Commit-Graph* (`.git/objects/info/commit-graph`) dalam mengoptimasi performa enterprise monorepo?
   * *Jawaban:* Commit-graph memetakan relasi generasi DAG secara terindeks dalam struktur biner kontinu, meniadakan overhead parsing berulang pada berkas commit objek secara individual saat menghitung jangkauan grafik (*reachability queries*), operasi log, dan *merge-base calculation*.
9. Jelaskan bahaya mengeksekusi `git push --force` dibandingkan menggunakan `git push --force-with-lease` pada lingkungan tim produksi!
   * *Jawaban:* `git push --force` akan menimpa branch remote secara buta tanpa memeriksa apakah ada commit baru yang telah di-push oleh rekan tim lain. `--force-with-lease` menolak eksekusi jika referensi remote tracking lokal kita tidak sinkron dengan referensi aktual di server upstream, mencegah tertimpanya pekerjaan orang lain tanpa sengaja.
10. Bagaimana mekanisme pembersihan objek sampah (*Garbage Collection*) Git membedakan antara commit yang masih valid dengan commit yang harus dihapus?
    * *Jawaban:* Git menelusuri grafik DAG dimulai dari entitas jangkar (*root references*: semua pointer di `refs/`, file `HEAD`, dan indeks). Objek yang tidak memiliki jalur keterjangkauan (*unreachable*) dari jangkar tersebut dan telah melewati ambang waktu grace period (default 14 hari via `gc.pruneExpire`) akan dieleminasi secara permanen dari disk.

#### Bagian C: Skenario Kasus Produksi (3 Soal)
11. **Skenario 1:** Sebuah script deployment CI/CD mengeksekusi `git checkout $COMMIT_SHA`. Mengapa menjalankan `git commit` di dalam runner CI pada tahapan ini akan menghasilkan komit yang berisiko hilang, dan bagaimana mitigasi standarnya pada level script bash?
    * *Jawaban:* Karena runner berada dalam kondisi *Detached HEAD*. Commit baru tidak memiliki pointer cabang referensi (`refs/heads/*`). Jika pipeline mengeksekusi checkout lanjutan, commit tersebut menjadi orphan dan akan di-prune oleh GC. Mitigasi: Selalu sertakan perintah `git checkout -b <temporary-release-branch>` sebelum mengeksekusi manipulasi data pada CI runner.
12. **Skenario 2:** Repositori production Anda mengalami degradasi di mana ukuran direktori `.git/` mencapai $45\text{ GB}$, padahal total ukuran file kerja (*working tree checkout*) hanya $300\text{ MB}$. Hasil audit menunjukkan ada engineer yang pernah melakukan komit dump database `.sql` berukuran $5\text{ GB}$ beberapa bulan lalu dan telah menghapusnya di commit berikutnya. Mengapa storage repositori tidak berkurang saat file dihapus, dan perintah apa yang harus dieksekusi?
    * *Jawaban:* Menghapus file di working tree hanya membuat node commit baru yang tidak lagi mencantumkan file tersebut di objek Tree barunya; namun, blob file $5\text{ GB}$ tersebut masih tersimpan permanen di histori commit lama dalam `.git/objects/pack/`. Solusi: Gunakan utilitas modern seperti `git-filter-repo` (menggantikan `filter-branch` yang deprecated) untuk membuang blob secara permanen dari seluruh snapshot histori: `git-filter-repo --path database.sql --invert-paths`, dilanjutkan dengan dereferensi reflog dan pemanggilan pembersihan total: `git reflog expire --expire=now --all && git gc --prune=now --aggressive`.
13. **Skenario 3:** Tim Anda menggunakan strategi merge trunk-based. Dua engineer menyelesaikan branch fitur terpisah yang memodifikasi baris file yang sama. Developer A me-rebase branchnya ke `main` dan sukses push. Developer B melakukan `git pull --rebase origin main` tetapi mendapati konflik kompleks. Karena frustrasi, Developer B melakukan `git rebase --skip`. Apa konsekuensi destruktif dari instruksi `--skip` tersebut pada konteks integritas codebase?
    * *Jawaban:* Instruksi `git rebase --skip` menginstruksikan Git untuk **membuang seluruh perubahan** yang terdapat pada commit lokal yang sedang mengalami konflik tersebut, dan melanjutkan rebase seolah-olah commit tersebut tidak pernah ada. Akibatnya, logika bisnis atau perbaikan bug yang telah dibuat Developer B pada commit tersebut hilang permanen dari histori rantai cabang tanpa adanya jejak penolakan formal, memicu silent bug di branch utama.

---

### 16. Summary

1. **Git adalah Content-Addressable Storage:** File diidentifikasi melalui nilai hash kriptografis isinya, menjamin integritas data mutlak dan efisiensi deduplikasi tingkat byte.
2. **Abstraksi Sistem Berkas melalui Merkle DAG:** Pemetaan direktori dan histori perubahan kode sumber direpresentasikan melalui kombinasi modular empat objek utama: `blob` (konten berkas mentah), `tree` (manifest direktori & perizinan berkas), `commit` (node titik waktu & relasi parent-child), serta `tag` (penandaan rilis permanen).
3. **Plumbing vs Porcelain:** Antarmuka Porcelain yang kita gunakan sehari-hari (`add`, `commit`, `checkout`) hanyalah pembungkus tingkat tinggi di atas mesin mekanik fundamental sistem berkas Git (`hash-object`, `update-index`, `write-tree`, `commit-tree`, `update-ref`). Memahami cara kerja komponen dasar ini membuka kapabilitas rekonstruksi, perbaikan data rusak, dan automasi tingkat lanjut.
4. **Skalabilitas Enterprise Menuntut Arsitektur Sadar Performa:** Mengelola repositori skala raksasa mengharuskan rekayasawan perangkat lunak memahami mekanisme `Commit-Graph`, implementasi `FSMonitor`, reduksi transfer data dengan *Blobless/Tree-less Clones*, serta disiplin mutlak terhadap integritas rantai komit linier dan penandatanganan kriptografis.