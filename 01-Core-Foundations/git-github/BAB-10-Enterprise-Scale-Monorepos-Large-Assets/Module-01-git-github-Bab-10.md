## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: GIT-01-10-01
* **Jalur Pembelajaran**: Core Foundations
* **Kategori**: 01-Core-Foundations
* **Bab**: 10 — Enterprise Scale, Monorepos, & Large Asset Management
* **Modul**: 01 — Mengelola Repositori Skala Masif: Git LFS, Partial Clone, Sparse Checkout, dan Scalar
* **Tingkat Kemahiran**: Advanced / Senior Engineer
* **Prasyarat**: 
  * Pemahaman mendalam tentang Git Internals (Object Database, Blobs, Trees, Commits, Tags, DAG).
  * Penguasaan manipulasi commit history (`git filter-repo`, `git rebase`).
  * Kemahiran eksekusi Git CLI tingkat lanjut dan administrasi shell Unix.
* **Estimasi Waktu Penyelesaian**: 180 Menit

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis Bottleneck Arsitektur Git**: Mendiagnosis penyebab degradasi performa pada repositori skala enterprise (monorepo atau repositori dengan aset masif) yang melibatkan *commit graph*, ukuran *working tree*, dan transfer objek jaringan.
2. **Mengimplementasikan Git Large File Storage (LFS)**: Mengonfigurasi, melacak, memigrasi aset biner historis, dan mengisolasi penyimpanan blob berukuran besar menggunakan pointer files dan storage backend terpisah.
3. **Mengeksekusi Strategi Klon Parsial (Partial Clone) dan Dangkal (Shallow Clone)**: Menggabungkan filter blob/tree (`--filter=blob:none`, `--filter=tree:0`) dan batasan kedalaman (`--depth`) untuk meminimalkan durasi transfer data pada *pipeline* CI/CD dan workstation pengembang.
4. **Mengonfigurasi Sparse Checkout Berbasis Cone Mode**: Menyusun pola working-tree selektif pada monorepo untuk mengisolasi subdirektori proyek tertentu tanpa membebani disk I/O dan sistem berkas lokal.
5. **Menerapkan Git Scalar dan Git Maintenance Engine**: Mengotomatisasi optimasi repositori skala besar melalui `scalar register`, `git maintenance`, `core.fsmonitor`, dan `commit-graph` multi-pack.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                            [ENTERPRISE SCALE GIT]
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         │                            │                            │
   [STORAGE ENGINE]             [NETWORK LAYER]             [WORKTREE LAYER]
         │                            │                            │
  ┌──────┴──────┐              ┌──────┴──────┐              ┌──────┴──────┐
  │   Git LFS   │              │Partial Clone│              │Sparse-Check-│
  │ (Pointers & │              │(--filter=   │              │    out      │
  │ Object Store│              │  blob:none) │              │ (Cone Mode) │
  └─────────────┘              └──────┬──────┘              └──────┬──────┘
         │                            │                            │
         └────────────────────────────┼────────────────────────────┘
                                      │
                         [ORCHESTRATION & OPTIMIZATION]
                                      │
                        ┌─────────────┴─────────────┐
                        │   Git Scalar / Maintenance│
                        │ (FSMonitor, Commit-Graph, │
                        │      Multi-Pack Index)    │
                        └───────────────────────────┘
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Model data Git dirancang terdistribusi secara penuh: setiap *clone* secara default menyalin seluruh *history*, seluruh *commit graph*, dan seluruh representasi file (blobs) dari hari pertama repositori diinisialisasi. Model ini ideal untuk repositori skala kecil hingga menengah (misalnya Linux Kernel yang, meskipun besar dari segi commit graph, didominasi oleh berkas teks murni).

Namun, model ini runtuh pada skala *enterprise*:
1. **Monorepo Skala Masif**: Repositori yang menampung ribuan engineer, ratusan proyek lintas divisi, jutaan commit, dan puluhan juta entri tree. Memeriksa status berkas (`git status`) saja dapat memakan waktu beberapa menit akibat bottleneck disk I/O dalam membaca seluruh metadata berkas.
2. **Pencemaran Objek Biner (Binary Blobs)**: Setiap modifikasi berkas biner (CAD files, model Machine Learning, video 4K, instalasi binary SDK) menghasilkan blob utuh baru pada object store Git. Berbeda dengan teks, delta compression Git (`packfiles`) tidak efektif memadatkan data biner terkompresi. Repositori membengkak puluhan hingga ratusan gigabyte, membuat proses `git clone` gagal atau menghabiskan bandwidth jaringan.
3. **Overhead Pipeline CI/CD**: Runner otomatis yang mengkloning repositori 50 GB ratusan kali sehari akan membebani jaringan internal, menghabiskan kuota cloud, dan menurunkan *throughput* rilis.

Penguasaan teknik mitigasi enterprise-scale bukan sekadar optimasi performa marjinal, melainkan prasyarat operasional agar monorepo enterprise tidak kolaps akibat beban strukturalnya sendiri.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Git Large File Storage (LFS)
Git LFS adalah ekstensi resmi Git yang menggantikan berkas biner berukuran besar di repositori Git dengan berkas pointer teks kecil (sekitar 130 byte). Konten biner aktual dikirimkan ke server penyimpanan terpisah (seperti AWS S3 atau server LFS khusus) melalui protokol HTTP(S). Repositori Git hanya menyimpan hash pointer-nya saja.

### 2. Shallow Clone (`--depth`)
Shallow Clone membatasi histori commit yang diunduh ke workstation hanya sejumlah `N` commit terakhir dari ujung branch target. Objek-objek pendahulu yang berada di luar batas kedalaman (`depth`) tidak akan ditransfer ke disk lokal.

### 3. Partial Clone (`--filter`)
Fitur inti Git (sejak v2.20+) yang memungkinkan pengguna menginisialisasi repositori tanpa mengunduh seluruh objek database secara instan. Objek dapat difilter berdasarkan kriteria:
* **Blobless Clone (`--filter=blob:none`)**: Mengunduh seluruh commit dan tree (seluruh direktori dan struktur history), tetapi sama sekali tidak mengunduh isi file (blob) hingga file tersebut di-checkout atau dibaca secara lokal.
* **Treeless Clone (`--filter=tree:0`)**: Hanya mengunduh commit graph. Tree dan blob diunduh secara *on-demand*.

### 4. Sparse Checkout (Cone Mode)
Sparse Checkout menginstruksikan working tree untuk hanya memuat sekumpulan berkas atau folder yang didefinisikan secara spesifik oleh developer, mengabaikan ribuan subproyek lain dalam monorepo tanpa mengubah integritas commit graph. **Cone mode** membatasi pola pencocokan ke tingkat direktori (bukan arbitrary glob), mengoptimalkan parsing algoritma berbasis prefix matching hash-table.

### 5. Git Scalar & Background Maintenance
Scalar adalah lapisan abstraksi dan toolset orkestrasi yang awalnya dikembangkan oleh Microsoft (untuk monorepo Windows OS yang mencapai ukuran ratusan gigabyte) dan kini telah diserap sepenuhnya ke dalam Git inti sejak versi 2.38. Scalar secara otomatis menyetel konfigurasi Git performa tinggi: mengaktifkan `fsmonitor`, mengonfigurasi Sparse Checkout Cone Mode, Partial Clone, multi-pack-index (MIDX), commit-graph generations, dan background fetch/maintenance berkala.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### Git LFS Architecture: Pointer & Smudge/Clean Filter
Git LFS menggunakan hook bawaan Git: **Clean Filter** dan **Smudge Filter** yang didefinisikan dalam `.gitattributes`.

```
Working Directory               Staging Area (Index)              Git ODB (.git/objects)
┌─────────────────┐             ┌─────────────────────┐          ┌───────────────────────┐
│ LargeBinary.bin │ ──clean───> │ Pointer File (.ptr) │ ───────> │ Commit with Pointer   │
│   (100 MB)      │             │ SHA-256 Checksum    │          └───────────────────────┘
└─────────────────┘             └─────────────────────┘                      │
        │                                                                    │
        ▼ (Upload to)                                                        │ (Push)
┌─────────────────────────────────┐                                          ▼
│ Git LFS Object Store (HTTP/S3)  │                               ┌───────────────────────┐
│ Stores actual 100 MB payload    │                               │ Remote Git Repository │
└─────────────────────────────────┘                               └───────────────────────┘
```

1. **Clean Filter (Commit time)**: Ketika file biner di-staging (`git add`), clean filter memotong file tersebut, menghitung SHA-256 hash, memindahkan konten asli ke cache lokal Git LFS (`.git/lfs/objects`), dan menuliskan pointer kecil ke index Git.
2. **Smudge Filter (Checkout time)**: Saat operasi `git checkout` dilakukan, smudge filter membaca pointer dari tree. Jika berkas biner sudah ada di cache lokal, LFS menyalinnya ke working tree. Jika belum, LFS mengeksekusi panggilan HTTPS API ke server LFS untuk mengambil berkas biner tersebut secara paralel.

Format Berkas Pointer Git LFS:
```text
version https://git-lfs.github.com/spec/v1
oid sha256:4b4231b467e2343a44b082e6f4f56fb35e1536e864f1417e3771a26060f5ecf4
size 104857600
```

---

### Partial Clone: Missing Object Protocol (Promisor Remotes)
Ketika repositori dikloning menggunakan:
```bash
git clone --filter=blob:none <url>
```

1. Klien memberi tahu server Git bahwa ia tidak menginginkan blob apa pun di awal.
2. Server mengirimkan packfile yang secara eksklusif hanya memuat commit dan tree object.
3. Klien menandai remote server sebagai **Promisor Remote** di dalam file konfigurasi lokal (`remote.<name>.promisor = true` dan `remote.<name>.partialclonefilter = blob:none`).
4. Ketika pengguna mengeksekusi checkout ke branch tertentu, working tree memerlukan blob untuk mengisi berkas fisik.
5. Git mendeteksi ketiadaan blob di database objek lokal (`.git/objects`), menghentikan operasi sesaat, lalu otomatis membuat request RPC batch baru ke Promisor Remote untuk mengambil blob yang hanya dibutuhkan saat itu.

---

### Sparse Checkout: Cone Mode vs Full Pattern
Sebelum Git 2.25, sparse checkout menggunakan arbitrary `.gitignore`-style globs (Non-cone mode). Hal ini mengharuskan Git mengevaluasi ekspresi regular terhadap setiap berkas di dalam tree, yang membutuhkan kompleksitas $O(N)$ di mana $N$ adalah jumlah file dalam monorepo (misal: 2.000.000 file).

**Cone Mode** (`git sparse-checkout set --cone <dir>`) mengubah aturan parsing:
1. Direktori yang dipilih harus berupa jalur direktori eksplisit (misal: `services/billing`).
2. Git hanya mengizinkan:
   * Seluruh berkas yang berada di *root directory*.
   * Seluruh berkas di subdirektori induk langsung (`services/`).
   * Seluruh pohon berkas secara rekursif di dalam direktori target (`services/billing/**`).
3. Algoritma pencocokan berubah dari regex matching bertingkat menjadi *hash-table prefix lookup* dengan kompleksitas amortisasi $O(1)$ untuk setiap entri tree.

---

### Git Scalar Internal Tuning
Ketika `scalar register` atau `scalar clone` dipanggil, Scalar mengaplikasikan manipulasi konfigurasi tingkat lanjut secara atomik pada `.git/config`:

```ini
[core]
    repositoryformatversion = 1
    untrackedCache = true
    fsmonitor = true
    multiPackIndex = true
[fetch]
    writeCommitGraph = true
[index]
    version = 4
[maintenance]
    auto = false
    strategy = incremental
```

* **Index Version 4**: Menggunakan prefix-compression pada file `.git/index`, mereduksi ukuran memory footprint index hingga 70%.
* **core.fsmonitor**: Mengintegrasikan daemon sistem operasi (FSEvents di macOS, ReadDirectoryChangesW di Windows, inotify di Linux) untuk mendeteksi berkas yang berubah tanpa membaca seluruh direktori via syscall `lstat()`.
* **Multi-Pack-Index (MIDX)**: Menyediakan indeks tunggal untuk membaca objek yang tersebar di puluhan packfile tanpa harus memuat file `.idx` masing-masing packfile.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Komparasi Alur Unduhan: Full vs Blobless vs Treeless Clone

```
========================================================================================
FULL CLONE: git clone <url>
========================================================================================
Server ODB ───────[ALL Commits + ALL Trees + ALL Blobs of ALL History]───────> Local ODB
                                                                                  │
Transfer Size: 100%                                                               ▼
Network Time: Maksimal                                                       Working Tree
Disk Usage  : Maksimal                                                      (Fully Populated)

========================================================================================
BLOBLESS PARTIAL CLONE: git clone --filter=blob:none <url>
========================================================================================
Server ODB ───────[ALL Commits + ALL Trees] (No Blobs)───────────────────────> Local ODB
                                                                                  │
Transfer Size: ~5 - 10%                                                           │
Network Time: Sangat Cepat                                                        ▼
                                                                             git checkout
                                                                                  │
Server ODB <──────[On-Demand Request: Only Blobs for HEAD Commit]─────────────────┘
           ───────[Stream Blobs]─────────────────────────────────────────────> Working Tree

========================================================================================
TREELESS PARTIAL CLONE: git clone --filter=tree:0 <url>
========================================================================================
Server ODB ───────[ALL Commits Only] (No Trees, No Blobs)────────────────────> Local ODB
                                                                                  │
Transfer Size: ~1 - 2% (Extreme minimal)                                          │
Network Time: Ultra Cepat                                                         ▼
                                                                             git checkout
                                                                                  │
Server ODB <──────[On-Demand Request: Trees & Blobs for HEAD Commit Only]─────────┘
           ───────[Stream Trees & Blobs]─────────────────────────────────────> Working Tree
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah demonstrasi inisialisasi Git LFS, pelacakan file biner, dan verifikasi struktur pointer file.

### 1. Inisialisasi Git LFS pada Repositori
```bash
# Pastikan git-lfs terpasang di sistem operasi
git lfs install

# Inisialisasi repositori simulasi
mkdir enterprise-lfs-demo
cd enterprise-lfs-demo
git init
```

### 2. Konfigurasi Tracking Ekstensi File Biner
```bash
# Lacak semua file model AI biner (.bin) dan arsip (.zip)
git lfs track "*.bin"
git lfs track "*.zip"

# Git LFS secara otomatis membuat atau memodifikasi .gitattributes
cat .gitattributes
```
Output terminal:
```text
*.bin filter=lfs diff=lfs merge=lfs -text
*.zip filter=lfs diff=lfs merge=lfs -text
```

### 3. Tambahkan File Biner dan File Tracking ke Staging
```bash
# Buat mock data biner sebesar 10MB
dd if=/dev/urandom of=model_weights.bin bs=1M count=10

# Staging .gitattributes terlebih dahulu, kemudian file biner
git add .gitattributes
git add model_weights.bin
git commit -m "feat: tambahkan model weights v1.0 via LFS"
```

### 4. Inspeksi Format Pointer (Verifikasi Isolasi Data)
```bash
# Tampilkan konten objek yang tersimpan langsung pada index Git (bukan data 10MB, melainkan pointer)
git show HEAD:model_weights.bin
```
Output:
```text
version https://git-lfs.github.com/spec/v1
oid sha256:d8e8fca2dc0f896fd7cb4cb0031ba249...
size 10485760
```

### 5. Memeriksa Status File LFS
```bash
git lfs ls-files
```
Output:
```text
d8e8fca2dc * model_weights.bin
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Skenario nyata monorepo enterprise: Anda adalah Lead Platform Engineer yang menangani monorepo sistem berskala 120 GB dengan 400 microservices di direktori `services/`. Tim Anda hanya bertanggung jawab atas service `services/payment-gateway` dan library bersama `packages/core-crypto`. 

Berikut skrip end-to-end automasi workstation untuk mengkloning monorepo dengan footprint minimum:

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/enterprise-org/mega-monorepo.git"
TARGET_DIR="mega-monorepo"

echo "=== LANGKAH 1: Blobless Clone dengan Konfigurasi Sparse Disabled Awal ==="
# Jangan checkout working directory terlebih dahulu (--no-checkout)
# Hindari fetch blob sama sekali (--filter=blob:none)
git clone --filter=blob:none --no-checkout "$REPO_URL" "$TARGET_DIR"
cd "$TARGET_DIR"

echo "=== LANGKAH 2: Mengaktifkan Sparse-Checkout Menggunakan Cone Mode ==="
git sparse-checkout init --cone

echo "=== LANGKAH 3: Menentukan Set Batasan Direktori Kerja ==="
# Menetapkan hanya direktori yang menjadi dependensi tim
git sparse-checkout set services/payment-gateway packages/core-crypto

echo "=== LANGKAH 4: Eksekusi Checkout Selektif ==="
# Hanya blob untuk direktori yang didefinisikan yang akan diminta dari remote
git checkout main

echo "=== LANGKAH 5: Verifikasi Status Working Tree ==="
# Periksa ukuran direktori kerja di disk
du -sh .
git status -s

echo "=== LANGKAH 6: Mendaftarkan Repositori ke Scalar Engine ==="
# Mengaktifkan background maintenance otomatis, fsmonitor, dan multi-pack-index
scalar register

echo "=== Konfigurasi Selesai: Monorepo Siap Digunakan Secara Cepat ==="
```

Verifikasi pola direktori yang sedang aktif:
```bash
git sparse-checkout list
```
Output:
```text
packages/core-crypto
services/payment-gateway
```

Ketika developer masuk ke folder `services/payment-gateway` dan mengubah file, eksekusi `git status`, `git add`, dan `git commit` berjalan dalam hitungan milidetik karena Git tidak perlu memindai 399 microservices lainnya.

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Pendekatan | Keuntungan Utama | Kerugian / Trade-off | Kapan Harus Digunakan | Kapan Harus Dihindari |
| :--- | :--- | :--- | :--- | :--- |
| **Git LFS** | Memisahkan binary payload dari Git history. Sangat matang, didukung luas oleh GitHub/GitLab/Bitbucket. | Membutuhkan dependensi client khusus. Manajemen permission server LFS terpisah. Migrasi commit lama butuh rewrite history. | Aset biner masif (>50MB), file multimedia, asset game 3D, dataset ML yang sering ter-update. | Repositori murni source code teks, monorepo dengan banyak project teks kecil. |
| **Shallow Clone (`--depth`)** | Ukuran download minimal untuk repositori dengan riwayat commit yang sangat panjang. | Memotong riwayat commit. Operasi `git merge`, `git rebase`, atau `git log` sering error karena kehilangan *merge-base*. | Pipeline CI/CD murni *stateless* (linting, static binary build) yang tidak memerlukan histori commit. | Workstation developer aktif yang melakukan percabangan, merging, dan tracing bugs. |
| **Blobless Clone (`--filter=blob:none`)** | Mempertahankan commit graph utuh. Operasi `git log`, `git checkout <commit>`, `git branch` bekerja offline tanpa latensi jaringan. | Memerlukan koneksi internet saat checkout file/branch baru pertama kali (on-demand download). | Konfigurasi default standar untuk developer workstation pada monorepo skala besar. | Lingkungan air-gapped / offline murni setelah proses clone selesai. |
| **Treeless Clone (`--filter=tree:0`)** | Ukuran clone awal paling kecil dan tercepat di antara semua strategi. | Setiap operasi navigasi direktori historis (`git checkout` commit lain, `git log -p`) memicu download tree via network. | Lingkungan CI yang hanya menjalankan unit test pada satu commit spesifik tanpa switch commit. | Workstation developer (akan sangat lambat akibat spamming network request saat browsing code). |
| **Sparse Checkout (Cone Mode)** | Mengurangi jumlah berkas di filesystem lokal secara drastis. Disk I/O, IDE indexing, dan `git status` instan. | Developer tidak dapat melihat file di luar "cone" kecuali dikonfigurasi ulang secara manual. Build tooling harus paham boundary. | Monorepo enterprise dengan ratusan project terisolasi. | Repositori kecil di mana dependensi antar folder saling bertaut erat dan acak. |

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan Blobless Clone sebagai Standar Workstation**:
   Hindari Full Clone dan Treeless Clone untuk mesin developer. Gunakan:
   ```bash
   git clone --filter=blob:none <repo-url>
   ```
   Pendekatan ini memberikan keseimbangan optimal: commit graph lengkap untuk analisis Git tanpa membuang bandwidth untuk mengunduh konten historis yang tidak disentuh.

2. **Gunakan Cone Mode Wajib pada Sparse Checkout**:
   Jangan pernah menggunakan *non-cone mode* pada monorepo besar. Konfigurasi non-cone mode menonaktifkan optimasi internal Git dan memaksa regex scanning pada jutaan path tree. Selalu panggil:
   ```bash
   git sparse-checkout set --cone <paths...>
   ```

3. **Aktifkan Git Maintenance Service**:
   Alih-alih menunggu `git gc` berjalan secara agresif dan memblokir terminal Anda di tengah jam kerja, aktifkan task otomatis:
   ```bash
   git maintenance start
   ```
   Perintah ini mendaftarkan cron job (Linux/macOS) atau Task Scheduler (Windows) untuk mengoptimalkan `commit-graph`, `pack-files`, dan `loose-objects` di latar belakang secara inkremental.

4. **Karantina Ekstensi File Biner Sebelum Push**:
   Terapkan pre-commit hook atau CI blocking rule yang melarang binary file di atas ambang batas (misal: > 5MB) masuk langsung ke Git tree tanpa melalui Git LFS:
   ```bash
   # Contoh pengecekan pre-push hook sederhana
   git diff --cached --name-only | while read file; do
       if [ $(wc -c < "$file") -gt 5242880 ] && ! git check-attr filter "$file" | grep -q 'filter: lfs'; then
           echo "ERROR: File $file lebih besar dari 5MB dan tidak dilacak oleh Git LFS!"
           exit 1
       fi
   done
   ```

5. **Gunakan Feature Flag FSMonitor**:
   Pada repositori dengan lebih dari 100.000 file, pasang watchman atau integrasikan `core.fsmonitor`:
   ```bash
   git config core.fsmonitor true
   ```

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Menambahkan Berkas Biner Sebelum `git lfs track`
* **Kasus**: Developer membuat file `database.dump` (500MB), lalu mengeksekusi `git add .`, baru menyadari file tersebut besar, lalu mengeksekusi `git lfs track "*.dump"`.
* **Dampak**: Berkas 500MB sudah terlanjur tersimpan di object database lokal Git sebagai raw blob. Menambahkan rule LFS setelahnya tidak menghapus blob tersebut dari commit history.
* **Remediasi**: Hapus berkas dari index Git, commit ulang, dan lakukan migrasi LFS:
  ```bash
  git rm --cached database.dump
  git lfs track "*.dump"
  git add .gitattributes database.dump
  git commit -m "fix: alihkan binary ke lfs"
  ```

### 2. Menggunakan Shallow Clone (`--depth 1`) pada Pipeline yang Melakukan Tagging atau Merging
* **Kasus**: CI/CD dikonfigurasi dengan clone depth 1 untuk efisiensi, kemudian pipeline mencoba mengeksekusi script auto-release (`git describe --tags`) atau merge branch feature ke main.
* **Dampak**: Pipeline gagal fatal dengan error `fatal: No names found, cannot describe anything` atau `fatal: refusing to merge unrelated histories`.
* **Solusi**: Jika butuh tag atau merge, lakukan unshallow secara terkontrol atau gunakan blobless clone daripada shallow clone:
  ```bash
  git fetch --unshallow || true
  # Atau preferensikan blobless:
  git clone --filter=blob:none --no-checkout <url>
  ```

### 3. Menggunakan Arbitrary Wildcard pada Sparse Checkout Non-Cone
* **Kasus**: Developer mengaktifkan sparse-checkout dan memasukkan pola regex file seperti:
  ```bash
  git sparse-checkout set "/*" "!/services/**/*.js"
  ```
* **Dampak**: Git terpaksa beralih dari hash comparison ke full linear scan. Performa checkout dan status anjlok drastis (hingga 10-50x lebih lambat pada monorepo jutaan file).
* **Solusi**: Susun ulang struktur direktori secara modular dan selalu gunakan *cone mode* berbasis direktori.

### 4. Menghapus Cache Git LFS Secara Manual dari `.git/lfs/objects`
* **Kasus**: Developer melihat folder `.git` membesar, lalu menghapus isi `.git/lfs/objects` secara manual menggunakan perintah `rm -rf`.
* **Dampak**: Metadata index lokal rusak. Saat melakukan commit atau status, LFS mendeteksi referensi objek hilang dan gagal melakukan verifikasi checksum (*LFS pointer missing object*).
* **Solusi**: Gunakan manajemen garbage collection bawaan LFS:
  ```bash
  git lfs prune --dry-run
  git lfs prune
  ```

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Migrasi Repositori Riwayat Biner ke Git LFS
* **Konteks**: Repositori lama memiliki file `.psd` dan `.zip` yang sudah terlanjur masuk ke commit history masa lalu, menyebabkan ukuran kloning mencapai ratusan megabyte.
* **Tugas**:
  1. Buat direktori pengujian dan inisialisasi repositori Git.
  2. Buat commit historis tiruan yang memuat file biner langsung ke Git biasa tanpa LFS.
  3. Gunakan perintah bawaan Git LFS (`git lfs migrate`) untuk mengubah histori commit lama secara retroaktif agar file tersebut diubah menjadi LFS pointer.
  4. Verifikasi bahwa ukuran packfile/ODB menyusut dan file biner berpindah ke storage LFS.

```bash
# Setup Skenario
mkdir repo-migration-lab && cd repo-migration-lab
git init
git config user.name "Test Engineer"
git config user.email "test@lab.internal"

# Buat commit historis berkas biner mentah
dd if=/dev/urandom of=archive-v1.zip bs=1M count=15
git add archive-v1.zip
git commit -m "feat: tambahkan archive v1"

dd if=/dev/urandom of=archive-v2.zip bs=1M count=15
git add archive-v2.zip
git commit -m "feat: tambahkan archive v2"

# Analisis ukuran riwayat sebelum migrasi
git count-objects -vH

# EKSEKUSI TUGAS:
# Jalankan git lfs migrate import untuk rewrite history file *.zip
git lfs migrate import --everything --include="*.zip"

# Verifikasi: Periksa commit history terbaru untuk archive-v2.zip
git show HEAD:archive-v2.zip
```

---

### Latihan 2: Membangun Workstation Monorepo Ultra-Ringan
* **Konteks**: Anda diminta mendesain template clone untuk developer frontend yang bekerja pada repositori multi-tier raksasa. Developer hanya boleh mengunduh file frontend UI dan file package configuration di root.
* **Tugas**:
  1. Inisialisasi struktur monorepo dummy di lokal:
     * `apps/frontend-ui/`
     * `apps/backend-api/`
     * `infra/kubernetes/`
     * `package.json`
  2. Buat remote bare repo lokal untuk mensimulasikan server remote.
  3. Dari folder terpisah, lakukan kloning parsial blobless terhadap remote tersebut.
  4. Terapkan sparse-checkout cone mode hanya untuk `apps/frontend-ui`.
  5. Buktikan bahwa folder `apps/backend-api/` dan `infra/kubernetes/` tidak ada pada filesystem fisik lokal, namun integritas Git commit tetap lengkap.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Apa perbedaan teknis mendasar antara `--filter=blob:none` dan `--filter=tree:0` pada Partial Clone?**
   * A. `--filter=blob:none` hanya mengunduh commit terakhir, sedangkan `--filter=tree:0` mengunduh semua commit.
   * B. `--filter=blob:none` mengunduh semua commit dan semua tree tetapi mengabaikan blob, sedangkan `--filter=tree:0` hanya mengunduh commit dan mengabaikan tree serta blob.
   * C. `--filter=blob:none` hanya berlaku untuk Git LFS, sedangkan `--filter=tree:0` berlaku untuk Git standar.
   * D. `--filter=blob:none` menghapus seluruh commit graph dari history lokal.

2. **Mengapa *Cone Mode* pada Sparse-Checkout jauh lebih cepat daripada Sparse-Checkout tradisional (*Non-Cone Mode*)?**
   * A. Cone mode mengompres berkas index menggunakan algoritma gzip.
   * B. Cone mode membatasi kecocokan hanya pada tingkat path prefix/direktori, sehingga Git dapat menggunakan pencarian hash-table $O(1)$ alih-alih mengevaluasi pola regex glob yang membutuhkan $O(N)$ scanning.
   * C. Cone mode secara otomatis mengonversi berkas teks menjadi LFS pointer.
   * D. Cone mode menghapus folder yang tidak digunakan dari remote server Git secara otomatis.

3. **Jika Anda menjalankan perintah `git log -p` pada repositori yang dikloning menggunakan `--filter=blob:none`, apa yang terjadi secara internal?**
   * A. Perintah gagal secara instan dengan pesan error `fatal: blob missing`.
   * B. Git menampilkan commit log, namun diff file teks akan dikosongkan.
   * C. Git membaca commit graph secara lokal, dan setiap kali diff memerlukan isi blob yang belum diunduh, Git secara dinamis melakukan request batch jaringan ke Promisor Remote untuk mengambil blob tersebut.
   * D. Git secara otomatis mengubah repositori lokal menjadi Full Clone secara permanen.

4. **Apa fungsi utama dari komponen `core.fsmonitor` yang dikonfigurasi oleh Git Scalar?**
   * A. Memeriksa integritas SHA-256 seluruh objek packfile setiap menit.
   * B. Menghubungkan Git ke event sistem operasi lokal untuk mengetahui file mana saja yang berubah, sehingga operasi `git status` tidak perlu memindai (lstat) seluruh berkas di disk secara manual.
   * C. Memantau kecepatan jaringan saat melakukan transfer data blob.
   * D. Mengirim metrik performa developer ke dashboard enterprise secara realtime.

---

### Kunci Jawaban & Evaluasi

* **1. Jawaban B**: `--filter=blob:none` (Blobless) menarik seluruh commit dan tree structure, mempertahankan visibilitas direktori lengkap pada history tanpa file content. `--filter=tree:0` (Treeless) hanya menarik commit object murni; tree dan blob diunduh on-demand saat checkout.
* **2. Jawaban B**: Cone mode menerapkan restriksi penamaan berbasis struktur direktori eksplisit. Ini memungkinkan Git melewati komparasi regular expression linier pada setiap berkas, memanfaatkan evaluasi hash-table directory prefix tree.
* **3. Jawaban C**: Promisor Remote menangani request missing object secara transparan. Karena flag `-p` menuntut diff konten, Git menghubungi remote untuk memuat blob yang relevan dengan diff tersebut.
* **4. Jawaban B**: `core.fsmonitor` memanfaatkan native OS filesystem notification hooks (seperti inotify atau FSEvents) untuk merekam modifikasi file, memotong runtime `git status` dari puluhan detik menjadi milidetik pada repository raksasa.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Dokumentasi Resmi Git**:
  * [Git Partial Clone Documentation](https://git-scm.com/docs/git-clone#Documentation/git-clone.txt---filterltfilter-specgt)
  * [Git Sparse Checkout & Cone Mode Specification](https://git-scm.com/docs/git-sparse-checkout)
  * [Git Scalar Architecture & Tooling](https://git-scm.com/docs/scalar)
* **Spesifikasi Git LFS**:
  * [Git Large File Storage Specification v1](https://github.com/git-lfs/git-lfs/blob/main/docs/spec.md)
* **Teknikal Whitepaper & Engineering Blog**:
  * Microsoft Engineering: *Scaling Git at Microsoft with VFS for Git / Scalar*.
  * GitHub Engineering: *Scaling Git’s merge analysis and commit graph operations*.
* **Buku Referensi**:
  * Chacon, S., & Straub, B. (2014). *Pro Git* (2nd ed.). Apress. (Bab Enterprise & Internals).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. Default full clone Git tidak skalabel untuk repositori berukuran gigabyte atau monorepo jutaan file karena mentransfer seluruh snapshot history dan data biner secara exhaustive.
2. **Git LFS** memecahkan masalah aset biner besar dengan mengganti file asli di Git DAG menggunakan berkas pointer berbasis SHA-256, memisahkan transfer binary payload ke storage HTTP/S3 terpisah via clean/smudge filter.
3. **Partial Clone (`--filter=blob:none`)** adalah standar emas workstation monorepo: menjaga integritas visualisasi history commit dan struktur tree, sementara blob data hanya diambil saat dibutuhkan secara on-demand dari Promisor Remote.
4. **Sparse Checkout (Cone Mode)** mengeliminasi overhead working tree lokal. Menggunakan pencocokan prefix direktori alih-alih arbitrary regex globbing, menghasilkan performa I/O yang deterministik dan instan.
5. **Git Scalar** mengintegrasikan seluruh parameter konfigurasi performa tinggi (`fsmonitor`, `untrackedCache`, `maintenance`, commit-graph indexing) menjadi satu solusi terorkestrasi untuk repositori tingkat enterprise.

---

## SEKSI 17 — GLOSARIUM

* **Blob (Binary Large Object)**: Tipe objek Git internal yang digunakan untuk menyimpan konten data berkas tanpa metadata seperti nama file atau permission bits.
* **Clean Filter**: Skrip/proses konversi yang dijalankan Git saat berkas dari working tree dipindahkan ke staging area (index).
* **Smudge Filter**: Skrip/proses konversi yang dijalankan Git saat berkas dari index atau commit object diekstraksi ke working tree fisik.
* **Promisor Remote**: Server remote Git yang disepakati bertindak sebagai penjamin ketersediaan objek ketika klien melakukan kloning parsial dan kekurangan objek tertentu secara lokal.
* **Cone Mode**: Pembatasan pola operasi sparse checkout yang membatasi aturan include/exclude murni pada tingkat hirarki path direktori.
* **Commit-Graph**: Berkas indeks binary internal (`.git/objects/info/commit-graph`) yang memetakan relasi DAG commit untuk mempercepat traversal commit history secara drastis.
* **Multi-Pack-Index (MIDX)**: Indeks biner terpadu yang memetakan letak seluruh objek yang tersebar di beberapa packfile `.pack`, meniadakan kebutuhan membuka banyak file indeks `.idx`.
* **FSMonitor**: Layanan integrasi daemon sistem operasi untuk memantau perubahan disk berkas secara asinkron tanpa full recursive directory scan.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Persiapan Lingkungan Lab**:
  * Pastikan versi Git yang terpasang pada mesin peserta minimal adalah **Git v2.38+** agar fitur `scalar` dan `sparse-checkout cone mode` tersedia secara native tanpa dependensi pihak ketiga.
  * Git LFS client harus terpasang (`git-lfs --version`). Jika menggunakan platform Linux, instruksikan peserta memasang paket dari package manager (`apt install git-lfs` atau `dnf install git-lfs`).
* **Titik Kritis Pemahaman Peserta**:
  * Tekankan bahwa **Partial Clone bukan Shallow Clone**. Banyak engineer mengira `--filter=blob:none` merusak merge-base seperti `--depth 1`. Jelaskan bahwa partial clone mempertahankan commit graph 100% lengkap dan aman untuk branching/merging jangka panjang.
  * Tunjukkan demonstrasi langsung perbedaan waktu eksekusi `git status` pada working tree raksasa sebelum dan sesudah menggunakan `core.fsmonitor` dan `sparse-checkout`.
* **Skenario Masalah Umum**:
  * Saat mendemokan *on-demand fetching* pada blobless clone, jika peserta memutus koneksi internet lalu berpindah commit via `git checkout`, Git akan melempar fatal network error. Manfaatkan momen ini untuk mendiskusikan *trade-off availability* antara model terdistribusi murni vs on-demand hybrid.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0 (Oktober 2023)**:
  * Rilis modul awal berstandar Enterprise Scale.
  * Cakupan mendalam Git LFS, Blobless/Treeless Partial Clone, Sparse Checkout Cone Mode, dan Git Scalar engine.
  * Standardisasi format silabus enterprise architecture.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `GIT-01-09-02: Advanced History Rewriting, Filter-Repo, and Repository Sanitization`
* **Modul Berikutnya**: `GIT-01-10-02: Distributed Workflow Topologies & Submodules vs Subtrees Architecture`
* **Indeks Jalur Pembelajaran**: `01-Core-Foundations -> Bab 10: Enterprise Scale, Monorepos, & Large Asset Management`