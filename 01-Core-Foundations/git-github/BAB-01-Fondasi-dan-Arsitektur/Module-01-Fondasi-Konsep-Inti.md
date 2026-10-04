# Bab 01 Module 01: Arsitektur Fundamental Git, Model Data Internal, dan Content-Addressable Storage

---

## 1. Title & Metadata
* **Modul:** `GIT-01-01`
* **Topik:** Sistem Kontrol Versi Terdistribusi, Model Data Graph, dan Mekanika Object Store Git
* **Tingkat Kesulitan:** Fundamental menuju Advanced Internals
* **Prasyarat:** Pemahaman navigasi command-line interface (CLI) Linux/Unix dasar, konsep sistem berkas (inodes, permissions), dan representasi data biner/hashing kriptografi.
* **Target Waktu:** 90–120 Menit

---

## 2. Concept Definition
Secara formal, **Git** bukanlah sekadar sistem pelacak perubahan berkas berbasis *delta* (perbedaan baris per baris), melainkan sebuah **Content-Addressable Key-Value Object Store** yang di atasnya diimplementasikan struktur data **Directed Acyclic Graph (DAG)** untuk merekam snapshot pohon direktori (*filesystem tree snapshots*) secara *immutable* (kekal).

Setiap node di dalam DAG merepresentasikan status keseluruhan proyek pada satu titik waktu tertentu. Identitas dari setiap objek (file, struktur folder, riwayat, dan metadata) divalidasi dan diakses secara deterministik melalui *cryptographic hash* (SHA-1 atau SHA-256) dari muatannya ditambah header internal Git.

---

## 3. Conceptual Hierarchy & Prerequisites
```
Sistem Kontrol Versi (VCS)
│
├── Generasi 1: Local Only (RCS, SCCS)
├── Generasi 2: Centralized VCS / CVCS (CVS, Subversion, Perforce)
└── Generasi 3: Distributed VCS / DVCS (Git, Mercurial, Darcs)
    │
    └── Model Data Git (Modul Ini)
        ├── Content-Addressable Storage (.git/objects)
        │   ├── Object Types (blob, tree, commit, annotated tag)
        │   └── Hashing Mechanism (Header + Content -> SHA)
        ├── The Three Trees / States
        │   ├── Working Directory (Untracked/Modified)
        │   ├── Index / Staging Area (.git/index)
        │   └── Git Repository / Object Database (HEAD)
        └── Directed Acyclic Graph (DAG) Traversal
```
*Prasyarat Pengetahuan:*
* Konsep Hashing (Algoritma Hashing satu arah: SHA-1, SHA-256).
* Konsep Pointer dan Referensi Memori/Disk.
* I/O Sistem Berkas dan Struktur Direktori Tree.

---

## 4. Business & Technical "Why"

### Masalah pada Sistem Sentralistik (CVCS / Subversion)
Pada CVCS seperti SVN atau Perforce, repositori terpusat memegang seluruh basis data versi. Operasi sehari-hari menghadapi limitasi struktural:
1. **Single Point of Failure (SPOF):** Jika server pusat mengalami *disk corruption* atau koneksi jaringan terputus, seluruh tim kehilangan kemampuan untuk melakukan *commit*, melihat riwayat, atau membuat *branch*.
2. **Latensi Operasional Tinggi:** Setiap operasi diffing, commit, dan branching membutuhkan round-trip jaringan ke server pusat.
3. **Kerapuhan Kolaborasi Lintas Zona:** Pengembang yang bekerja di lingkungan *offline* (pesawat, fasilitas remote tanpa koneksi internet) terisolasi sepenuhnya dari kontrol versi.

### Solusi Teknis DVCS (Git)
Git mengatasi batasan ini dengan mendistribusikan salinan penuh repositori—termasuk seluruh riwayat DAG dan object database—ke setiap mesin pengembang (*local clone*).
* **Eksekusi Lokal Instan:** Operasi diff, commit, log, dan branch traversal terjadi secara lokal pada kecepatan disk/SSD I/O lokal.
* **Integritas Kriptografis (Cryptographic Integrity):** Karakteristik *content-addressable* menjamin bahwa tidak ada manipulasi data, perubahan bit di disk, maupun kompromi jaringan yang dapat terjadi tanpa mengubah hash referensi, sehingga *silent corruption* dapat langsung dideteksi oleh Git.
* **Redundansi Alami:** Setiap developer clone berfungsi sebagai backup komplit dari sistem repositori utama.

---

## 5. The "What"
Sistem Git terdiri dari tiga entitas logis utama dan empat tipe objek fundamental.

### Tiga State / Tiga Area Komputasi Git
1. **Working Directory:** Direktori fisik pada OS tempat berkas didekompresi dan disunting langsung oleh pengembang.
2. **Index (Staging Area):** Berkas biner tunggal (terletak di `.git/index`) yang bertindak sebagai *staging manifest*. Area ini mempersiapkan snapshot logis berikutnya yang akan dikomit.
3. **Repository (`.git` directory):** Basis data objek Git yang menyimpan metadata DAG, referensi (*heads, tags*), log konfigurasi, dan semua objek terkompresi.

### Empat Objek Fundamental Git
Semua objek disimpan di direktori `.git/objects` dalam format terkompresi zlib:
* **Blob (*Binary Large Object*):** Menyimpan murni konten mentah suatu berkas. *Tidak* menyimpan nama berkas, timestamp, maupun atribut permission.
* **Tree:** Merepresentasikan sebuah direktori. Berisi daftar pointer yang memetakan nama berkas/direktori, mode permission UNIX (misal: `100644`, `100755`), ke SHA hash dari blob atau tree turunan.
* **Commit:** Metadata snapshot yang memuat pointer ke satu root `tree`, referensi pointer ke zero atau lebih *parent commit* (membentuk DAG), data *author*, *committer*, timestamp, dan *commit message*.
* **Annotated Tag:** Pointer permanen ke objek commit tertentu, dilengkapi dengan metadata pembuat tag, tanggal, dan pesan verifikasi kriptografi opsional (GPG).

---

## 6. System Architecture & Component Interaction

Diagram alur perubahan status data dari Working Directory menuju Object Store:

```
+----------------------------------------------------------------------------------------------------+
|                                         SISTEM FILE LOKAL                                          |
+----------------------------------------------------------------------------------------------------+
| [ 1. Working Directory ]        [ 2. Staging Area (Index) ]        [ 3. Object Store (.git/objects) ]
|                                                                                                    |
|  main.go (Modified)                                                                                |
|     |                                                                                              |
|     |  git add main.go                                                                             |
|     +--------------------------> Update .git/index                                                 |
|                                       |                                                            |
|                                       |--------> Hash & Compress Content                           |
|                                       |          (zlib deflate)                                    |
|                                       |          Simpan sebagai Object                             |
|                                       |          +----------------------------------------------+  |
|                                       |--------->| Type: blob                                   |  |
|                                                  | SHA: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391|  |
|                                                  +----------------------------------------------+  |
|                                                                                                    |
|  git commit -m "feat: init"                                                                        |
|     |                                                                                              |
|     +--------------------------------------------------> Generate Root Tree                        |
|                                                          +--------------------------------------+  |
|                                                          | Type: tree                           |  |
|                                                          | Cont: 100644 blob e69de29... main.go |  |
|                                                          +--------------------------------------+  |
|                                                                     ^                              |
|                                                                     | references                   |
|                                                          +--------------------------------------+  |
|                                                          | Type: commit                         |  |
|                                                          | tree: [SHA Tree di atas]             |  |
|                                                          | parent: [SHA Parent jika ada]        |  |
|                                                          | author: Jane Doe <jane@corp.internal>|  |
|                                                          +--------------------------------------+  |
|                                                                     ^                              |
|                                                                     | updates                      |
|                                                          [ .git/refs/heads/main ]                  |
|                                                                     ^                              |
|                                                                     | points to                    |
|                                                          [ .git/HEAD ]                             |
+----------------------------------------------------------------------------------------------------+
```

---

## 7. Mechanics & Internal Working

### Kalkulasi SHA Hash
Sebelum Git menulis objek ke disk, ia menyusun *header* standar:
$$\text{Header} = \text{type} + \text{" "} + \text{size in bytes} + \text{"\0" (null byte)}$$
Payload akhir yang di-hash adalah:
$$\text{Payload} = \text{Header} + \text{Content}$$
$$\text{Object ID (OID)} = \text{SHA-1}(\text{Payload})$$

Contoh kalkulasi manual melalui command line shell:
```bash
$ printf "commit 0\0" | sha1sum
# Output membuktikan format deterministik dari Git
```

### Penyimpanan Objek di Disk
Git menghemat operasi file system OS dengan membagi 40-karakter heksadesimal OID ke dalam path:
* **2 karakter pertama:** Digunakan sebagai nama subdirektori di dalam `.git/objects/`.
* **38 karakter sisanya:** Digunakan sebagai nama berkas di dalam subdirektori tersebut.
* Konten berkas adalah hasil kompresi algoritma **zlib** dari keseluruhan $\text{Payload}$.

### Directed Acyclic Graph (DAG) Mechanics
Commit tidak pernah menyimpan status "diff". Komit mereferensikan snapshot direktori lengkap. Apabila file $A$ tidak berubah antara Commit 1 dan Commit 2, maka node `tree` pada Commit 2 akan menunjuk ke SHA hash `blob` file $A$ yang sama persis dengan Commit 1. Tidak ada duplikasi payload pada storage level.

```
Commit C1 (Initial)  <--- Parent Pointer ---  Commit C2 (Feature Update)
[ Tree: 4a2b9... ]                           [ Tree: 9f8e1... ]
  |-- blob: a1111... (file1.txt)               |-- blob: a1111... (Reuse! Tidak berubah)
  `-- blob: b2222... (file2.txt)               `-- blob: c3333... (Konten baru file2.txt)
```

---

## 8. Step-by-Step Implementation Guide: Bedah Plumbing Git
Di bawah ini adalah langkah rekonstruksi commit Git **tanpa menggunakan perintah porcelain tingkat tinggi** (`git add` atau `git commit`). Kita akan menggunakan *low-level plumbing commands* untuk memahami mekanika internalnya secara langsung.

### Langkah 1: Inisialisasi Repositori Kosong
```bash
mkdir git-internals-lab
cd git-internals-lab
git init
```

Periksa struktur internal awal:
```bash
ls -la .git/
# Perhatikan direktori: objects, refs, file: HEAD, config
```

### Langkah 2: Buat Blob Manual Menggunakan `hash-object`
Tulis berkas secara langsung ke Object Database:
```bash
# Menulis konten ke objek Git secara langsung dan mencetak SHA-1 hash-nya
BLOB_SHA=$(printf "package main\n\nfunc main() {}\n" | git hash-object -w --stdin)
echo "Blob OID: ${BLOB_SHA}"
```

Verifikasi keberadaan objek pada disk:
```bash
# Dua karakter pertama folder, 38 karakter nama file
DIR_NAME=$(echo $BLOB_SHA | cut -c1-2)
FILE_NAME=$(echo $BLOB_SHA | cut -c3-40)
ls -l .git/objects/${DIR_NAME}/${FILE_NAME}
```

Periksa tipe dan isi objek menggunakan `git cat-file`:
```bash
git cat-file -t ${BLOB_SHA}
# Output: blob
git cat-file -p ${BLOB_SHA}
# Output: package main ...
```

### Langkah 3: Masukkan Blob ke dalam Index Manual
```bash
# Daftarkan blob ke staging area dengan permission executable normal (100644) dan path 'main.go'
git update-index --add --cacheinfo 100644 ${BLOB_SHA} main.go

# Verifikasi status staging area
git status
# Output akan menampilkan: Changes to be committed: new file: main.go
# Namun file fisik main.go BELUM ADA di working directory!
```

Sinkronisasikan index ke working directory agar berkas fisik muncul:
```bash
git checkout-index -a -f
ls -l main.go
```

### Langkah 4: Tulis Snapshot Index ke Tree Object
```bash
TREE_SHA=$(git write-tree)
echo "Tree OID: ${TREE_SHA}"
git cat-file -p ${TREE_SHA}
# Output memetakan: 100644 blob <BLOB_SHA> main.go
```

### Langkah 5: Buat Objek Commit
```bash
COMMIT_SHA=$(echo "feat: bootstrap core binary architecture" | git commit-tree ${TREE_SHA})
echo "Commit OID: ${COMMIT_SHA}"
git cat-file -p ${COMMIT_SHA}
# Output menampilkan: tree <TREE_SHA>, author, committer, timestamp, dan message.
```

### Langkah 6: Update Pointer Branch (HEAD)
Saat ini HEAD belum menunjuk ke commit baru. Perbarui referensi branch `main`:
```bash
git update-ref refs/heads/main ${COMMIT_SHA}
```

Jalankan log porcelain standar:
```bash
git log -p
# Riwayat commit muncul dengan integritas sempurna seolah-olah dieksekusi via `git commit`
```

---

## 9. Practical Production Example: Standard Enterprise Repository Initialization
Berikut adalah skrip shell otomatis untuk standardisasi repositori korporat dengan konfigurasi penanganan format baris (*end-of-line*), limit file biner, dan proteksi branch lokal:

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="microservice-payment-gateway"
mkdir -p "${REPO_DIR}"
cd "${REPO_DIR}"

# 1. Inisialisasi repositori dengan nama branch standar enterprise
git init --initial-branch=main

# 2. Enforcement konfigurasi lokal untuk mencegah inkonsistensi developer
git config --local core.autocrlf input       # Memaksa standardisasi LF pada Linux/macOS
git config --local core.fileMode true        # Melacak perubahan bit permission UNIX (+x)
git config --local core.precomposeUnicode true # Penanganan nama berkas UTF-8 di macOS
git config --local commit.gpgSign false      # Set true jika signing key tersedia

# 3. Buat .gitattributes untuk mitigasi line-ending churn & file biner
cat << 'EOF' > .gitattributes
# Auto-detect text files and normalize line endings to LF on commit
* text=auto eol=lf

# Force specific language extensions
*.go text diff=golang
*.json text
*.yaml text
*.yml text
*.md text

# Mark binary files explicitly to disable delta parsing and merge conflicts
*.png binary
*.jpg binary
*.tar.gz binary
*.iso binary
EOF

# 4. Standard Enterprise .gitignore
cat << 'EOF' > .gitignore
# System & Tooling artifacts
.DS_Store
Thumbs.db
*.swp
*~
.idea/
.vscode/

# Build outputs
/bin/
/dist/
*.out
*.exe

# Secrets & Environment configuration - NEVER COMMIT
*.env
*.pem
*.key
credentials.json
EOF

# 5. First Structural Commit
git add .gitattributes .gitignore
git commit -m "chore(infra): initialize repository structure with enterprise standards"

echo "[SUCCESS] Repositori ${REPO_DIR} siap digunakan sesuai tata kelola produksi."
```

---

## 10. Anti-Patterns & Common Misconceptions

| Pola Salah (*Anti-Pattern*) | Realitas Arsitektur Git | Konsekuensi Produksi | Remediasi yang Benar |
| :--- | :--- | :--- | :--- |
| **Asumsi Model Delta:** Menganggap Git menyimpan perbedaan teks (*diff lines*) untuk tiap commit. | Git menyimpan snapshot utuh dari keseluruhan sistem file dalam bentuk hash tree. Kompresi delta hanya dilakukan nanti saat *packing* (`.pack`). | Pengembang ragu melakukan perubahan refaktor besar-besaran karena takut ukuran repo membengkak. | Sadari bahwa duplikasi berkas yang identik tidak memakan ruang ekstra karena hashing OID yang sama. |
| **Menyimpan Secret di Commit, Lalu Dihapus di Commit Baru:** Menjalankan `git rm secret.env` setelah sebelumnya terlanjur dikomit. | Objek blob yang memuat secret tetap berada permanen di DAG dan Object Store `.git/objects`. | Kebocoran kredensial produksi saat repo di-*push* ke remote (GitHub/GitLab). | Hapus objek secara radikal dari seluruh riwayat menggunakan `git filter-repo` atau BFG Repo-Cleaner, lalu rotasi kredensial. |
| **Menggunakan Staging Area Tanpa Kontrol:** Menjalankan `git add .` secara membabi-buta sebelum commit. | Menghancurkan isolasi fungsional commit. Berkas temporer, log, dan artefak ter-stage secara tidak sengaja. | Polusi riwayat commit (*commit pollution*), audit perubahan sulit dilakukan. | Gunakan `git add -p` (*patch staging*) untuk meninjau hunk demi hunk perubahan yang relevan saja. |

---

## 11. Edge Cases & Debugging

### Masalah 1: Detached HEAD State
Kondisi ini terjadi ketika `HEAD` merujuk langsung ke sebuah commit SHA, bukan ke sebuah referensi branch bernama (misal: `refs/heads/main`).
```bash
# Cara mendeteksi:
git status
# Output: HEAD detached at a1b2c3d

# Verifikasi pointer HEAD:
cat .git/HEAD
# Jika detached: a1b2c3d4e5... (berupa OID hash murni)
# Jika normal: ref: refs/heads/main
```
*Bahaya:* Segala commit baru yang dibuat dalam status ini tidak memiliki namespace branch. Saat Anda checkout ke branch lain, commit-commit tersebut menjadi objek yatim (*dangling objects*) yang rentan terhapus oleh Garbage Collector (`git gc`).

*Solusi Perbaikan:*
```bash
# Bungkus commit eksperimen yang terisolasi ke dalam branch baru:
git branch recovery-branch
# Kembalikan HEAD ke branch utama:
git checkout main
# Gabungkan jika diperlukan:
git merge recovery-branch
```

### Masalah 2: CRLF Injection pada Git Lintas Platform
Pengembang Windows menambahkan file dengan CRLF (`\r\n`), pengembang Linux melakukan checkout.
```bash
# Debug: Deteksi whitespace dan line ending di index
git ls-files --stage
git check-attr -a path/to/file.go
```
*Solusi:* Terapkan konfigurasi `.gitattributes` wajib pada root repositori dengan parameter `* text=auto eol=lf`.

---

## 12. Failure Modes & Recovery Strategies

### Skenario Kerusakan: Accidental `git reset --hard` (Kehilangan Data Lokal)
Pengembang secara tidak sengaja menjalankan `git reset --hard HEAD~1` sebelum perubahan di-push ke remote, dan commit penting hilang dari riwayat log biasa.

#### Mekanisme Pemulihan Menggunakan DAG Invariant:
Git tidak pernah menghapus objek commit secara instan selama operasi reset. Objek hanya kehilangan referensi branch resminya.

```bash
# Langkah 1: Telusuri jejak mutasi pointer HEAD via Reference Log (Reflog)
git reflog

# Contoh Output:
# 4f82d11 HEAD@{0}: reset: moving to HEAD~1
# 9a7b3c2 HEAD@{1}: commit: feat: implement robust jwt verification logic

# Langkah 2: Periksa apakah commit yang hilang masih utuh di Object Database
git cat-file -t 9a7b3c2
# Output: commit

# Langkah 3: Kembalikan kondisi branch ke commit tersebut
git reset --hard 9a7b3c2
```

Jika perubahan bahkan belum sempat dikomit, namun **sempat dilakukan `git add`** (berada di Index), file tersebut telah berubah menjadi blob di `.git/objects`.

```bash
# Cari dangling/unreachable blobs:
git fsck --lost-found

# Output akan memberikan list SHA:
# dangling blob 8c34f2a1b9204...

# Periksa konten blob tersebut:
git cat-file -p 8c34f2a1b9204 > recovered-file.go
```

---

## 13. Tooling Ecosystem & Integration

| Tool/Subsistem | Lapisan Integrasi | Fungsi Operasional Produksi |
| :--- | :--- | :--- |
| **Git Plumbing Engine** | Core Internal (`git hash-object`, `cat-file`) | Menjalankan pemrosesan I/O biner, pembentukan DAG, dan kompresi zlib di level OS. |
| **Git Porcelain Engine** | Abstraksi Pengembang (`git commit`, `checkout`) | Membungkus plumbing menjadi interface CLI yang ergonomis untuk alur kerja harian. |
| **Git Hooks (`.git/hooks/`)**| Event Interceptor Lifecycle | Skrip lokal bash/python (`pre-commit`, `commit-msg`) untuk validasi linter, linting pesan commit, dan scan security secrets. |
| **Git Credential Manager**| Secure Enclave / Secret Store | Mengamankan token autentikasi HTTPS (OAuth) ke dalam keychain OS tanpa plain-text exposure. |

---

## 14. Security, Isolation, & Access Considerations

1. **Integritas Berkas Melalui SHA Identifiers:**
   Struktur content-addressable menjamin proteksi data transfer: jika satu bit payload disisipkan kode berbahaya selama transmisi jaringan via insecure protocol, kalkulasi SHA di sisi penerima akan gagal sinkron dengan Tree pointer, dan Git memutus transfer dengan error `fatal: object corrupted`.
2. **File Permission Blindness:**
   Git **hanya** menyimpan mode bit permission UNIX yang terbatas:
   * `100644`: Regular non-executable file.
   * `100755`: Executable file.
   * `120000`: Symbolic link.
   Git tidak menyimpan *ownership* (UID/GID), ACL, atau extended attributes. Konfigurasi deployment server yang bergantung pada user ownership tidak boleh mengandalkan repositori Git secara telanjang.
3. **Immutability vs Git Secret Exposure:**
   Menghapus berkas yang memuat kredensial menggunakan commit lanjutan tidak menghapus blob dari `.git/objects`. Siapa pun yang memiliki izin read terhadap repositori dapat mengekstrak berkas tersebut via `git checkout <commit-lama>`.

---

## 15. Scalability, Performance, & Resource Cost

### Mekanisme Loose Objects vs Packfiles
* **Loose Objects:** Saat developer mengedit dan melakukan `git add`, Git membuat satu file per objek di `.git/objects/XX/`. Pada repositori berskala ribuan file, OS akan kehabisan *inode* sistem berkas dan performa I/O memburuk drastis.
* **Packfiles (`.pack` dan `.idx`):** Git mengonsolidasikan objek-objek individual ini melalui proses repacking (`git gc`).
  Di dalam packfile, Git menjalankan kompresi berbasis delta sliding window: Git mencari file-file yang mirip, menyimpan file versi terbaru secara utuh, dan menyusun versi lama murni sebagai *diff backward*.

```bash
# Memaksa optimasi ruang disk & repackaging loose objects
git gc --prune=now --aggressive
```

### Metrics Karakteristik Beban Kerja:
* **Memory footprint:** Konsumsi RAM Git melonjak drastis saat memproses commit yang melibatkan berkas biner tunggal berukuran ratusan megabyte karena algoritma delta compression mencoba membandingkan biner ke dalam memory buffer.
* **Disk I/O:** Skalabilitas Git ditentukan oleh *I/O latency*, bukan CPU core count. Operasi traversal commit log melakukan ribuan random seeks di direktori `.git/objects`.

---

## 16. Trade-Off Analysis

### Distributed (Git) vs Centralized Lock-Based (Perforce / Helix Core)

| Dimensi Arsitektural | Git (DVCS) | Perforce (CVCS) |
| :--- | :--- | :--- |
| **Model Data** | Snapshot DAG, Immutable Objects. | File Delta + Central Server Metadata Database. |
| **Model Kolaborasi** | Merge/Rebase terdistribusi secara paralel. | File-level exclusive locking (Pessimistic Locking). |
| **Penanganan Aset Raksasa (Game Dev/Binaries)** | Buruk tanpa Git LFS. Repositori membengkak secara eksponensial. | Sangat optimal. Klien hanya menarik file spesifik tanpa menduplikasi riwayat aset biner. |
| **Audit Akses Direktori** | All-or-Nothing. Pengembang memiliki riwayat penuh seluruh tree. | Granular Path-level authorization (Bisa membatasi akses subfolder tertentu). |
| **Ketahanan Jaringan** | Sangat Tinggi. Bekerja 100% luring (offline-first). | Sangat Rendah. Ketergantungan total pada uptime server sentral. |

---

## 17. Production Readiness Checklist

- [ ] **Initial Branch Name Uniformity:** Menggunakan `main` sebagai default branch standar (bukan `master` yang *deprecated*).
- [ ] **Line-Ending Normalization:** Berkas `.gitattributes` terkonfigurasi di root direktori dengan `* text=auto eol=lf`.
- [ ] **Baseline `.gitignore` Ingress:** File `.gitignore` terdefinisi dan melarang file sensitif (`.env*`, `*.pem`, `node_modules`, `vendor/`) masuk ke Index.
- [ ] **Git Configuration Check:**
  - `core.fileMode = true` diaktifkan untuk environment berbasis Linux/UNIX.
  - `core.autocrlf` di-set ke `input` (Linux/macOS) atau `true` (Windows).
- [ ] **Hooks Validation:** Hook validasi lokal (`pre-commit`) terpasang untuk scan kebocoran secret (contoh: memanfaatkan tools seperti `trufflehog` atau `gitleaks`).
- [ ] **Cryptographic Verification:** Setiap developer dipersenjatai dengan GPG key atau SSH key terkonfigurasi untuk *Signed Commits* (`git config --global commit.gpgsign true`).

---

## 18. Real-World Scenario: Forensic Remediation Insiden Data Corrupt

### Masalah Lapangan
Sebuah skrip deployment CI/CD di lingkungan produksi mengalami kegagalan saat menjalankan `git fetch origin`. Git melemparkan error fatal:
```text
error: object file .git/objects/4b/825dc642cb6eb9a060e54bf8d69288fbee4904 is empty
error: object file .git/objects/4b/825dc642cb6eb9a060e54bf8d69288fbee4904 is corrupt
fatal: loose object 4b825dc642cb6eb9a060e54bf8d69288fbee4904 (stored in .git/objects/4b/825dc642cb6eb9a060e54bf8d69288fbee4904) is corrupt
```
Kondisi ini terjadi akibat mesin CI mati mendadak (*power outage/hard reset*) saat proses I/O commit berlangsung, meninggalkan file 0-byte pada objek tree.

### Analisis Akar Masalah (RCA) & Mitigasi
1. **Identifikasi Status Kerusakan Objek:**
   ```bash
   find .git/objects/ -type f -empty
   # Ditemukan: .git/objects/4b/825dc642cb6eb9a060e54bf8d69288fbee4904 (Ukuran: 0 bytes)
   ```
2. **Isolasi Objek yang Rusak:**
   ```bash
   # Hapus objek 0-byte tersebut agar tidak memblokir engine fsck
   rm -f .git/objects/4b/825dc642cb6eb9a060e54bf8d69288fbee4904
   ```
3. **Integritas Pemeriksaan Graf:**
   ```bash
   git fsck --full
   # Output menampilkan pointer parent yang kehilangan child tree:
   # broken link from commit 7a3c2... to tree 4b825dc642cb6eb9a060e54bf8d69288fbee4904
   ```
4. **Eksekusi Pemulihan (Restoration):**
   Karena Git adalah sistem terdistribusi, objek yang rusak ini dapat ditarik kembali secara instan dari repositori upstream (*central bare remote*):
   ```bash
   # Ambil objek dari upstream tanpa mengubah status HEAD lokal:
   git fetch origin --refetch
   # Atau ganti objek secara spesifik jika remote mirror tersedia:
   # scp developer-host:/path/.git/objects/4b/825dc6... .git/objects/4b/
   
   # Validasi ulang integritas graph:
   git fsck --full
   # Status exit code: 0 (Database pulih total tanpa kehilangan commit).
   ```

---

## 19. Exercises & Verifiable Challenges

### Challenge 1: Constructing a Detached Tree Commit manually (Hands-On Lab)
**Instruksi:**
1. Masuk ke direktori kosong. Inisialisasi Git.
2. Buat berkas bernama `security.txt` dengan isi teks `contact: security@corp.internal`.
3. Buat file blob dari `security.txt` menggunakan `git hash-object -w`.
4. Tulis file index secara programatik menggunakan `git update-index`.
5. Generate SHA Tree menggunakan `git write-tree`.
6. Eksekusi `git commit-tree` dengan pesan `"sec: initial security manifest"`.
7. Pasang referensi commit ke branch `release-v1.0`.

*Tolok Ukur Verifikasi:*
Jalankan perintah:
```bash
git log release-v1.0 -n 1 --stat
```
Output harus menampilkan metadata author Anda, branch name `release-v1.0`, commit message `"sec: initial security manifest"`, dan statistik berkas `1 file changed, 1 insertion(+) security.txt`.

### Challenge 2: Tracing SHA-1 Collision and Commit Structure
**Instruksi:**
1. Bedah commit terakhir Anda di repo pengujian dengan menjalankan:
   ```bash
   git cat-file -p HEAD
   ```
2. Catat SHA dari atribut `tree`.
3. Eksekusi `git cat-file -p <TREE_SHA>`.
4. Catat SHA dari berkas blob yang terdaftar di dalam tree tersebut.
5. Hitung secara manual panjang byte dari isi blob tersebut menggunakan command `wc -c`.
6. Buktikan secara matematis bahwa Git menyimpan format:
   `blob <size>\0<content>`
   menggunakan kalkulasi hashing Unix CLI:
   ```bash
   (printf "blob <SIZE>\0"; cat <NAMA_FILE>) | sha1sum
   ```
*Tolok Ukur Verifikasi:* Hash output yang dihasilkan oleh kalkulasi manual terminal Anda harus cocok 100% tanpa selisih karakter dengan OID yang tercatat di dalam objek `tree`.

---

## 20. Summary & Mental Model

### Model Mental Utama:
> **"Git adalah basis data file biner Key-Value sederhana yang menggunakan SHA sebagai Primary Key, di atasnya ditumpangkan sebuah directed tree graph untuk membentuk snapshot sistem berkas, dan pointer transparan untuk membentuk riwayat versi."**

```
           +---------------------------------------+
           |       GIT IS NOT A DELTA ENGINE       |
           +---------------------------------------+
                               |
         Setiap Commit Adalah Snapshot Independen
                               |
           +---------------------------------------+
           | Content-Addressable Storage (CAS)     |
           | Key   = SHA-1/SHA-256 Hash of Content |
           | Value = Zlib Compressed Byte Stream   |
           +---------------------------------------+
            /                  |                  \
           v                   v                   v
     [ Blobs ]             [ Trees ]          [ Commits ]
   Raw file bytes        Directory maps      Graph nodes
   No file names         Maps names to SHAs  Points to 1 Tree
   No permissions        Unix filemodes      Points to Parents
```

* Perubahan sekecil satu karakter pada file paling dalam akan mengubah SHA berkas tersebut (`blob`).
* Perubahan SHA `blob` akan memaksa perubahan SHA pada direktori yang menaunginya (`tree`).
* Perubahan SHA `tree` merambat naik ke root folder hingga menghasilkan SHA `commit` baru yang unik.
* Rantai referensi hash ini membuat riwayat Git **bersifat tamper-evident** (mustahil dimanipulasi secara diam-diam tanpa merusak integritas seluruh rantai hash setelahnya).