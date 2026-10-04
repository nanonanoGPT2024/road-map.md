# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Kategori: 01-Core-Foundations
### Topik: git-github-beginner
### Bab 10: BAB-10-Materi-Lanjutan
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengonstruksi mental model internal Git berbasis *Content-Addressable Storage* dan *Directed Acyclic Graph* (DAG).
- Merekonstruksi objek Git (*blob*, *tree*, *commit*, *annotated tag*) secara manual menggunakan *plumbing commands*.
- Menerapkan strategi branching tingkat enterprise (*Trunk-Based Development* skala besar dan *Release Train*) dengan mitigasi konflik deterministik.
- Mengoptimalkan performa repository berskala besar (Monorepo) menggunakan *Sparse Checkout*, *Scalar*, dan *Partial Clones*.
- Melakukan investigasi forensik dan pemulihan bencana (*disaster recovery*) pada kerusakan commit, kehilangan ref, dan kebocoran kredensial sensitif dalam *packfile*.
- Mengimplementasikan pipeline pengamanan repository berbasis *cryptographic signature* (SSH/GPG) dan automasi audit *pre-receive/pre-commit hooks*.

---

### 2. Prerequisite
Untuk mencerna materi ini secara optimal, peserta wajib menguasai:
- Operasi dasar Git (*working tree*, *staging area*, *local repository*, *remote*).
- Operasi branching standar: `git checkout`, `git switch`, `git merge`, dan dasar `git rebase`.
- Pemahaman dasar sistem berkas POSIX, perizinan (*file permissions/octal modes*), dan manipulasi terminal Unix/Linux.
- Pemahaman fungsi hashing kriptografis (SHA-1 dan SHA-256) serta struktur data dasar *graph* dan *tree*.

---

### 3. Concept & Internal Architecture (Mendalam)

Git pada dasarnya bukanlah sekadar Version Control System (VCS); secara fundamental, Git adalah sebuah **sistem berkas beralamat konten (*content-addressable filesystem*)** yang memiliki antarmuka VCS berlapis di atasnya (*porcelain layer*).

```
+-------------------------------------------------------------------+
|                        Porcelain Commands                         |
|     (git add, git commit, git checkout, git branch, git merge)     |
+-------------------------------------------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
|                         Plumbing Commands                         |
|   (git hash-object, git cat-file, git mktree, git commit-tree)    |
+-------------------------------------------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
|                    Object Store Database (.git)                   |
|       [Blob]            [Tree]           [Commit]         [Tag]   |
+-------------------------------------------------------------------+
```

#### 3.1. Anatomi `.git` Directory
Struktur internal direktori `.git` menyimpan keseluruhan status, basis data objek, dan riwayat revisi proyek:
- `HEAD`: Pointer simbolik ke branch yang sedang aktif (misalnya `ref: refs/heads/main`) atau commit hash (kondisi *detached HEAD*).
- `config`: Konfigurasi lokal repositori (menimpa level `--global` dan `--system`).
- `description`: Digunakan oleh GitWeb/daemon dasar (jarang dipakai pada sistem modern).
- `hooks/`: Skrip otomasi sisi klien (*client-side*) yang dieksekusi sebelum/sesudah lifecycle Git tertentu.
- `index`: Berkas biner (*staging area*) yang memetakan path berkas di direktori kerja ke SHA-1/SHA-256 objek di database Git beserta metadata POSIX (`stat` cache: mtime, ctime, file size, permissions).
- `objects/`: Basis data objek terkompresi menggunakan algoritma zlib (*deflate*). Terbagi menjadi:
  - *Loose objects*: Disimpan dalam direktori 2 karakter pertama dari hash, dengan nama berkas 38 karakter sisanya (misal: `objects/4b/825dc642cb6eb9a060e54bf8d69288fbee4904`).
  - *Packfiles*: Arsip gabungan biner berkinerja tinggi (`.pack`) beserta indeks pencariannya (`.idx`) hasil kompilasi *Garbage Collection* (`git gc`).
- `refs/`: Penunjuk bernama ke commit hash.
  - `refs/heads/`: Pointer branch lokal.
  - `refs/tags/`: Pointer rilis (*lightweight* atau *annotated*).
  - `refs/remotes/`: Pointer mirror branch pada remote server.

#### 3.2. Empat Objek Inti Git
Semua mutasi di Git disimpan dalam salah satu dari empat jenis objek immutable:
1. **Blob (*Binary Large Object*)**: Hanya menyimpan konten berkas mentah. Metadata seperti nama berkas, jalur direktori, dan mode izin eksekusi (`chmod`) **tidak** disimpan di dalam blob.
2. **Tree**: Merepresentasikan direktori. Berisi daftar referensi yang mengikat SHA hash dari blob (berkas) atau tree lain (sub-direktori), lengkap dengan mode perizinan berkas POSIX (misal: `100644` untuk normal non-executable file, `100755` untuk executable script, `040000` untuk sub-directory/sub-tree).
3. **Commit**: Mengikat tree root proyek pada waktu tertentu, metadata pengarang (*author*), pencatat (*committer*), stempel waktu (*timestamp* zona waktu ISO), pesan log, dan hash satu atau lebih commit induk (*parents*).
4. **Annotated Tag**: Objek independen yang mirip dengan commit, menyimpan penunjuk ke commit tertentu, nama penanda (*tagger*), stempel waktu, pesan penjelasan, dan tanda tangan digital opsional (GPG/SSH).

#### 3.3. Directed Acyclic Graph (DAG) & Immutability
Git menyusun riwayat sebagai sebuah DAG. Setiap commit baru mereferensikan pendahulunya (*parent hash*). Sifat immutability berlaku mutlak: modifikasi 1 bit pada berkas akan mengubah SHA hash blob tersebut. Perubahan hash blob memicu perubahan hash tree direktori induk, yang berlanjut mengubah hash root tree, dan berakhir mengubah hash commit itu sendiri. 

```
  Commit Object (Hash: c1a2)         Commit Object (Hash: f9d4)
+-----------------------------+    +-----------------------------+
| tree: 77a1...               |    | tree: 98e2...               |
| parent: [NONE]              |<---| parent: c1a2...             |
| author: Bob <bob@corp.io>   |    | author: Alice <al@corp.io>  |
+-----------------------------+    +-----------------------------+
               |                                  |
               v                                  v
          Tree (77a1)                        Tree (98e2)
     +--------------------+             +--------------------+
     | 100644 blob 3b18.. |             | 100644 blob a1b4.. | (Modified)
     | (README.md)        |             | (README.md)        |
     | 040000 tree 88cd.. |             | 040000 tree 88cd.. | (Unchanged: points
     +--------------------+             +--------------------+  to same sub-tree)
               |                                  |
               v                                  |
          Tree (88cd) <---------------------------+
     +--------------------+
     | 100644 blob e5c2.. |
     | (src/main.go)      |
     +--------------------+
```

---

### 4. Why & What
Pemahaman Git tingkat permukaan (*porcelain abstractions*) kerap runtuh saat dihadapkan pada insiden produksi tingkat enterprise: merge conflict berskala ratusan berkas, kebocoran secret credential di commit 3 tahun lalu, atau repository berukuran ratusan Gigabyte yang membekukan pipeline CI/CD.

| Dimensi | Pendekatan Pemula (Porcelain Only) | Pendekatan Enterprise (Under-The-Hood Engine) |
| :--- | :--- | :--- |
| **Penyimpanan Data** | Menganggap Git menyimpan *delta/diff* per baris. | Mengetahui Git menyimpan *snapshot* utuh terkompresi dengan deduplikasi hash instan. |
| **Resolusi Masalah** | Panik saat *detached HEAD*, sering clone ulang repositori jika terjadi rebase error. | Memanfaatkan `git reflog`, `git fsck`, dan manipulasi direct object dereferencing. |
| **Keamanan** | Mengandalkan proteksi password/token HTTPS biasa. | Menegakkan commit signing wajib (GPG/SSH key), validasi signature di branch policy, scanning push secret via AST/Entropy parser. |
| **Skalabilitas** | Menarik (*pull*) seluruh riwayat commit dari awal hingga akhir di setiap run CI. | Menggunakan *Blobless Shallow Clones*, *Sparse Checkout Patterns*, dan *Scalar Engine*. |

---

### 5. How (Workflow detail)

Berikut alur deterministik pembuatan riwayat commit tanpa menggunakan `git add` atau `git commit`, melainkan melalui manipulasi database langsung menggunakan *plumbing commands*:

```
[Plain File: app.py] 
        |
        v  (git hash-object -w)
[Blob Object: Hash '3b18...'] in .git/objects/
        |
        v  (git update-index --add --cacheinfo)
[Staging Area / The Index File]
        |
        v  (git write-tree)
[Tree Object: Hash 'd832...'] in .git/objects/
        |
        v  (git commit-tree Hash -m "msg")
[Commit Object: Hash '7fa0...'] in .git/objects/
        |
        v  (git update-ref refs/heads/main)
[Branch Pointer Updated] -> HEAD refers to 'main'
```

#### Langkah-Langkah Operasional Rendah (Plumbing Execution)
1. **Hashing Konten**: Berkas mentah diproses melalui algoritma hash dengan header format:
   $$\text{Header} = \text{"blob "} + \text{size} + \backslash 0$$
   Konten biner dikompresi menggunakan zlib dan ditulis ke `.git/objects/`.
2. **Indeksasi**: *Staging area* (`.git/index`) dimodifikasi untuk memetakan nama file, izin POSIX, dan hash blob baru.
3. **Penyusunan Tree**: Membaca index dan menulis representasi hierarki tree saat ini ke object database.
4. **Penyusunan Commit**: Menggabungkan hash tree root dengan metadata, stempel waktu, dan hash parent commit sebelumnya.
5. **Dereferensi Pointer**: Mengarahkan branch pointer (`refs/heads/<branch>`) ke hash commit yang baru dibuat.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Notaris, Brankas Sidik Jari, dan Kartu Katalog Perpustakaan
- **Blob** adalah selembar kertas bertuliskan isi surat tanpa judul. Kertas ini dimasukkan ke brankas raksasa; brankas tidak peduli judul surat itu apa, ia hanya memberi stempel sidik jari unik (*hash*) berdasarkan isi dokumen.
- **Tree** adalah amplop transparan berlabel yang berisi daftar nomor sidik jari kertas-kertas tersebut, lengkap dengan nama berkas yang disematkan padanya ("app.py", "run.sh").
- **Commit** adalah sertifikat notaris yang menyatakan: "Pada tanggal X, Alice mengesahkan susunan amplop nomor sekian, sebagai kelanjutan resmi dari sertifikat notaris milik Bob kemarin".
- **Branch** adalah selembar *sticky note* yang menempel di luar brankas bertuliskan "PRODUKSI", yang bisa dengan cepat dipindahkan untuk menunjuk sertifikat notaris mana pun.

#### Struktur Packfile vs Loose Object

```
    LOOSE OBJECT STORAGE                    PACKED STORAGE (.pack + .idx)
+---------------------------+           +------------------------------------+
| .git/objects/             |           | .git/objects/pack/                 |
|  ├── 4b/                  |           |  ├── pack-8a3f...idx (Index Map)   |
|  │   └── 825dc6... (zlib) |           |  └── pack-8a3f...pack (Binary Stream)
|  ├── 8a/                  |           +------------------------------------+
|  │   └── 11c9ea... (zlib) |           | Contains deltas between versions:  |
|  └── d4/                  |  git gc   | Base: Commit v2 Full Object        |
|      └── f703bc... (zlib) | --------> |  └── Delta: Commit v1 (-3 / +5)    |
| (High inode consumption,  |           | (Sliding window delta compression, |
|  uncompressed deltas)     |           |  minimal disk & RAM usage)         |
+---------------------------+           +------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Membuat Commit dari Nol via Plumbing Commands
Skrip shell murni tanpa automasi porcelain:

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Inisialisasi bare minimum environment
mkdir git-internals-lab && cd git-internals-lab
git init

# 2. Buat file secara fisik di workspace
echo "print('Production Grade Git Architecture')" > engine.py

# 3. Masukkan file ke object database sebagai Blob (simpan output hash)
BLOB_HASH=$(git hash-object -w engine.py)
echo "Blob Hash Terbentuk: ${BLOB_HASH}"

# 4. Daftarkan blob ke staging area (index) dengan filemode 100644 (standard file)
git update-index --add --cacheinfo 100644 "${BLOB_HASH}" engine.py

# 5. Tulis status staging index menjadi Tree object
TREE_HASH=$(git write-tree)
echo "Root Tree Hash Terbentuk: ${TREE_HASH}"

# 6. Buat Commit object dari Tree tanpa commit parent
COMMIT_HASH=$(echo "feat: core engine architecture bootstrap" | git commit-tree "${TREE_HASH}")
echo "Commit Hash Terbentuk: ${COMMIT_HASH}"

# 7. Update pointer refs heads agar branch main menunjuk commit ini
git update-ref refs/heads/main "${COMMIT_HASH}"

# 8. Reset HEAD pointer secara simbolik ke main
git symbolic-ref HEAD refs/heads/main

# 9. Verifikasi via porcelain command
git log -p -1
```

#### 7.2. Practical Example: Enterprise Pre-Commit Hook Anti-Credential Leak
Skrip validasi otomatis di `.git/hooks/pre-commit` untuk mencegah developer secara tidak sengaja mengunggah Private Key, AWS Credentials, atau format JWT:

```bash
#!/usr/bin/env bash
# File: .git/hooks/pre-commit
set -euo pipefail

echo "==> [Security Audit] Memeriksa Staged Blobs terhadap Kebocoran Rahasia..."

# List pattern regex kritis
BLOCKED_PATTERNS=(
    "-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----"
    "(?i)aws_secret_access_key\s*=\s*['\"][A-Za-z0-9/+=]{40}['\"]"
    "eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*"
    "(?i)ghp_[A-Za-z0-9]{36}" # GitHub Personal Access Token
)

EXIT_CODE=0

# Ambil hash dari index yang akan di-commit (menghindari false positive pada unstaged changes)
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM)

if [ -z "${STAGED_FILES}" ]; then
    exit 0
fi

for FILE in ${STAGED_FILES}; do
    # Skip symlinks atau submodule
    if [ ! -f "${FILE}" ]; then
        continue
    fi

    for PATTERN in "${BLOCKED_PATTERNS[@]}"; do
        # Menguji stage cache menggunakan git show
        if git show ":${FILE}" | grep -Pq "${PATTERN}"; then
            echo -e "\e[31m[CRITICAL REJECT]\e[0m Pola kredensial sensitif terdeteksi di: ${FILE}"
            echo -e "Pattern: ${PATTERN}"
            EXIT_CODE=1
        fi
    done
done

if [ ${EXIT_CODE} -ne 0 ]; then
    echo "================================================================="
    echo "Commit digagalkan secara lokal oleh sistem keamanan."
    echo "Hapus kredensial, gunakan environment injection atau vault."
    echo "================================================================="
    exit 1
fi

echo "==> [Security Audit] Lolos verifikasi keamanan."
exit 0
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Masalah
Sebuah platform perbankan digital multinasional memiliki monorepo berumur 6 tahun dengan metrik:
- Total ukuran direktori `.git`: **142 GB**.
- Jumlah total commit: **1,200,000+**.
- Durasi eksekusi `git status`: **45 detik**.
- Durasi CI/CD clone: **22 menit per job**, mengakibatkan antrean pipeline yang masif dan biaya runner cloud melonjak hingga ribuan USD per bulan.
- Penyebab utama: Developer di masa lalu meng-commit artefak kompilasi biner `.tar.gz`, dump database pengujian `.sql`, dan model machine learning `.onnx` langsung ke Git history.

#### Arsitektur Solusi & Resolusi

```
[Legacy Monorepo: 142 GB]
       |
       v (Tahap 1: Analisis Blob Terbesar via plumbing)
[git rev-list --objects --all] -> Temukan top 50 hash berkas biner > 100MB
       |
       v (Tahap 2: BFG Repo-Cleaner / git-filter-repo)
[Purge History Delta: Exclude Big Blobs & Update Historical Commit Trees]
       |
       v (Tahap 3: Re-archiving Blobs to External Storage)
[Inject Git-LFS (Large File Storage) for tracking future *.onnx, *.bin]
       |
       v (Tahap 4: CI/CD Pipeline Transformation)
[Blobless Shallow Clone Strategy: git clone --filter=blob:none --depth=1]
       |
       v
[Optimized Monorepo: 2.1 GB History Size | Status Run: 0.3s | CI Clone: 8s]
```

1. **Purging Git History Secara Permanen**:
   Menggunakan engine `git-filter-repo` untuk merekonstruksi seluruh DAG pohon commit tanpa menyertakan artefak biner di masa lampau:
   ```bash
   git-filter-repo --strip-blobs-bigger-than 50M
   ```
2. **Aggressive Garbage Collection**:
   Menghapus reflog kadaluarsa, membuang unreachable loose objects, dan memaksa penulisan ulang packfile secara menyeluruh:
   ```bash
   git reflog expire --expire=now --all
   git gc --prune=now --aggressive
   ```
3. **Mengubah Strategi CI/CD Clone**:
   Menghentikan `git clone --mirror` atau full clone tradisional pada runner pipeline. Menggantinya dengan *treeless/blobless shallow clone*:
   ```bash
   git clone --filter=blob:none --no-checkout --depth=1 https://github.com/corp/core-monorepo.git .
   git checkout HEAD
   ```
   **Hasil**: Data yang ditransfer pipeline CI turun drastis dari **142 GB** menjadi **85 MB**, dan waktu run CI terpangkas sebesar **98.2%**.

---

### 9. Trade-offs (Analisis Komparasi Arsitektural)

#### 9.1. Merge Commit vs. Rebase & Fast-Forward vs. Squash Merge

```
A---B---C (main)             A---B---C---M (Merge Commit)
     \                            \     /
      D---E (feature)              D---E

A---B---C (main)             A---B---C---D'---E' (Rebase & FF)
     \
      D---E (feature)

A---B---C (main)             A---B---C---F (Squash Merge, F = D+E)
     \
      D---E (feature)
```

| Tipe Integrasi | Latency & Kecepatan | Performa Riwayat (Graph Topology) | Skalabilitas Tim (Audit Trail) | Cost / Overhead Pemulihan |
| :--- | :--- | :--- | :--- | :--- |
| **Merge Commit (`--no-ff`)** | Rendah: Tidak ada manipulasi hash lama. | Kompleks, bercabang-cabang (*train track topology*), sulit ditelusuri mesin. | **Sangat Tinggi**: Mempertahankan konteks historis cabang, identitas author, dan waktu asli. | Sangat Mudah: Cukup `git revert -m 1 <commit-hash>` untuk membatalkan seluruh fitur. |
| **Interactive Rebase & FF** | Tinggi: CPU harus merekayasa ulang patch commit satu per satu. | **Linear murni**: Bersih, mudah dibaca, mempermudah operasi `git bisect`. | **Rendah**: Menimpa commit timestamps, SHA hash berubah total, identitas committer terdistorsi. | Kompleks: Konflik harus diselesaikan berulang kali pada tiap commit individual saat rebase. |
| **Squash & Merge** | Sangat Rendah: Langsung mengonsolidasi perubahan ke satu commit baru. | **Linear sederhana**: Satu commit per unit fitur PR (*Pull Request*). | **Menengah**: Riwayat pengerjaan granular hilang; hanya menyisakan snapshot final fitur. | Sangat Rendah: Logika fitur terisolasi pada satu commit tunggal; revert deterministik. |

#### 9.2. Git LFS vs Native Packfile Storage
- **Git Native Storage**: Menggunakan *sliding-window delta compression*. Sangat efisien untuk file teks (kode sumber), tetapi sangat boros CPU/RAM dan menyebabkan fragmentasi penyimpanan bila dipakai untuk berkas biner (video, gambar, ZIP, model binary).
- **Git LFS (Large File Storage)**: Mengganti konten biner di repositori lokal dengan *text pointer metadata* kecil (berisi SHA-256 dan ukuran file). Konten biner asli dialihkan via panggilan API HTTP/S3 ke storage server terpisah.
  - *Trade-off*: Mengurangi ukuran repository hingga 90%+, namun menambah latensi dependensi pada ketersediaan storage endpoint sekunder saat checkout branch dilakukan.

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Kesalahan Fatal: Force Push (`git push -f`) Menimpa History Main Branch
*Kondisi*: Seorang developer melakukan interactive rebase yang salah, lalu menjalankan `git push origin main --force`. Perubahan dari puluhan engineer lain di remote terhapus seketika.

*Prosedur Pemulihan (Disaster Recovery)*:
1. Akses server remote atau mesin lokal developer yang belum sempat menjalankan `git pull` terbaru.
2. Identifikasi commit hash terakhir sebelum force push terjadi menggunakan `git reflog`:
   ```bash
   git reflog show origin/main
   # Output contoh:
   # 7e2a1b9 refs/remotes/origin/main@{0}: pull: Fast-forward
   # a810c42 refs/remotes/origin/main@{1}: update-ref: force-update (KOMPUTASI RUSAK)
   # 3d98ef1 refs/remotes/origin/main@{2}: commit: feat: crucial payment gateway
   ```
3. Kembalikan branch ke hash asli yang valid (`3d98ef1`):
   ```bash
   git checkout main
   git reset --hard 3d98ef1
   # Gunakan force-with-lease untuk memastikan keamanan persaingan mutasi branch
   git push origin main --force-with-lease
   ```

#### 10.2. Mitigasi Kegagalan Rebase Berskala Masif
Saat rebase tersangkut di puluhan commit dengan status file conflicted yang masif:
```bash
# Batalkan status rebase sepenuhnya dan kembalikan Working Tree ke kondisi semula
git rebase --abort

# Alternatif: Jika terlanjur git rebase --skip dan ada data hilang, pulihkan lewat ORIG_HEAD
git reset --hard ORIG_HEAD
```

#### 10.3. Membersihkan File Terlanjur Terhapus Tapi Masih Ada di `.git/objects`
File rahasia `.env` yang dihapus dengan `rm .env && git commit -am "delete env"` **masih hidup di Git object database selamanya**.
Verifikasi keberadaannya:
```bash
git rev-list --objects --all | grep "\.env"
```
Solusi: Gunakan `git-filter-repo` (bukan `git filter-branch` yang sudah *deprecated* karena lambat dan tidak aman):
```bash
git filter-repo --path .env --invert-paths --force
```

---

### 11. Best Practices (Production Checklist)

#### Pre-Push & Development Level
- [ ] **GPG / SSH Commit Signing Terpasang**: Konfigurasikan penandatanganan kriptografis untuk memvalidasi otentisitas committer (`git config --global commit.gpgsign true`).
- [ ] **Atomic Commits**: Setiap commit harus fokus pada satu unit kapabilitas fungsional yang dapat dikompilasi secara independen (*does one thing, passes all tests*).
- [ ] **Conventional Commits**: Format commit terstruktur (`feat:`, `fix:`, `perf:`, `chore:`, `refactor:`, `BREAKING CHANGE:`).
- [ ] **Global `.gitignore` Terintegrasi**: Memblokir file sistem operasi (`.DS_Store`, `Thumbs.db`), log lokal, dan cache editor (`.idea/`, `.vscode/`).

#### Architecture & Repository Policy Level
- [ ] **Proteksi Branch Utama (`main`/`master`)**:
  - Aktifkan proteksi branch: Blokir `git push --force` tanpa privilege khusus.
  - Wajibkan validasi via Pull Request minimal 2 persetujuan (*two-man rule*).
  - Wajibkan passing checks pada pipeline CI (build, lint, unit tests, security scans).
  - Wajibkan opsi `--force-with-lease` jika rewrite history terpaksa dilakukan pada feature branch.
- [ ] **Konfigurasi Git System Tuning**:
  ```bash
  # Optimasi performa deteksi perubahan di filesystem besar (POSIX/Windows)
  git config --global core.fsmonitor true
  git config --global core.untrackedCache true
  ```

---

### 12. Hands-on Practice
Langkah-langkah praktikum berikut harus dieksekusi secara berurutan di terminal Anda untuk membuktikan manipulasi level rendah Git. Simpan seluruh artefak percobaan ini di `hands-on/m02/`.

```bash
# Skenario: Hands-on Bedah Forensik Objek Git
mkdir -p hands-on/m02/forensic-lab
cd hands-on/m02/forensic-lab
git init

# 1. Eksplorasi direktori .git internal sebelum operasi apapun
ls -la .git/
ls -la .git/objects/ # Hanya ada info/ dan pack/

# 2. Buat berkas target
echo "Architecture-Deep-Dive" > core.txt

# 3. Tulis langsung ke database Git via plumbing
HASH=$(git hash-object -w core.txt)
echo "Generated Hash: ${HASH}"

# 4. Validasi keberadaan file di dalam .git/objects/
# Ambil 2 karakter pertama untuk folder, 38 karakter sisanya untuk nama berkas
DIR_NAME=${HASH:0:2}
FILE_NAME=${HASH:2}
ls -la ".git/objects/${DIR_NAME}/${FILE_NAME}"

# 5. Baca tipe dan ukuran objek langsung dari database
git cat-file -t "${HASH}" # Menghasilkan 'blob'
git cat-file -s "${HASH}" # Menghasilkan ukuran byte

# 6. Baca konten terdekompresi langsung dari database
git cat-file -p "${HASH}"

# 7. Buktikan idempotensi: Berkas berbeda nama dengan isi sama menghasilkan Hash identik
echo "Architecture-Deep-Dive" > duplicate.txt
DUP_HASH=$(git hash-object duplicate.txt)
echo "Duplicate Hash: ${DUP_HASH}"
[ "${HASH}" == "${DUP_HASH}" ] && echo "Identik: Git mengenali konten, bukan nama berkas!"

# 8. Bedah staging index
git update-index --add --cacheinfo 100644 "${HASH}" custom-name.txt
git ls-files --stage # Periksa metadata yang dicatat di index

# 9. Tulis Tree dari index saat ini
TREE_ID=$(git write-tree)
echo "Tree ID: ${TREE_ID}"
git cat-file -p "${TREE_ID}" # Tampilkan representasi isi tree direktori

# 10. Commit manual
COMMIT_ID=$(echo "manual plumbing commit" | git commit-tree "${TREE_ID}")
echo "Commit ID: ${COMMIT_ID}"
git cat-file -p "${COMMIT_ID}"

# 11. Kaitkan HEAD dengan commit manual
git update-ref refs/heads/main "${COMMIT_ID}"
git symbolic-ref HEAD refs/heads/main

# 12. Audit status akhir via porcelain
git log --stat
git status
```

---

### 13. Exercise

#### Level: Easy
1. Dari repository `hands-on/m02/forensic-lab`, ubah isi `core.txt` menjadi `"Architecture-V2"`.
2. Generate SHA-1 hash barunya menggunakan `git hash-object` tanpa parameter `-w`. 
3. Jelaskan mengapa berkas hash baru tersebut belum muncul di direktori `.git/objects/`.

#### Level: Medium
1. Buat commit baru di atas `COMMIT_ID` sebelumnya **hanya** menggunakan plumbing commands (`git hash-object`, `git update-index`, `git write-tree`, `git commit-tree`, dan `git update-ref`).
2. Pasang commit sebelumnya sebagai `-p` (*parent*) pada commit baru ini.
3. Jalankan `git log --graph --oneline` untuk memverifikasi bahwa garis silsilah kedua commit tersebut tersambung dengan benar.

#### Level: Hard
1. Buat kondisi kerusakan simulasi (*simulated disaster*):
   Hapus branch pointer lokal: `rm .git/refs/heads/main`.
   Jalankan `git status` (Git akan melaporkan repositori tidak memiliki branch atau error).
2. Lakukan recovery tanpa bantuan internet:
   - Gunakan `git reflog` atau pemindaian dangling objects via `git fsck --lost-found`.
   - Temukan commit hash terakhir.
   - Rekonstruksi file `refs/heads/main` hingga repository kembali normal sepenuhnya.

---

### 14. Challenge (Tantangan Studi Kasus Nyata)

**Konteks**: Anda dipekerjakan sebagai Senior Infrastructure & Release Engineer di sebuah unicorn fintech. Seorang developer secara keliru menggabungkan (*merge*) branch fitur yang belum diaudit ke branch `release-v2.4.0` yang sedang dipersiapkan untuk deploy dalam 30 menit ke Kubernetes cluster produksi. 

Branch release tersebut telah memiliki 15 commit baru setelah merge branch yang salah tersebut masuk. Struktur cabang sudah dipush ke remote GitHub enterprise dan tim QA sedang melakukan automated testing di atas commit paling ujung.

```
...---R1---R2---M (Infiltrated Merge Commit)---R3---...---R17 (HEAD / release-v2.4.0)
               /
     F1-------F2 (Unvetted Feature)
```

**Tugas Anda (Tanpa Solusi Instan)**:
1. Rancang urutan perintah Git presisi tinggi untuk mendepak seluruh perubahan kode yang dibawa oleh `F1` dan `F2` dari branch `release-v2.4.0`, **tanpa** menghilangkan histori commit `R3` hingga `R17`.
2. Jelaskan risiko pemakaian `git revert -m 1 M` terhadap kemungkinan digabungkannya kembali branch `F` di rilis berikutnya (`release-v2.5.0`), dan bagaimana Anda memitigasi konsekuensi *revert of revert* tersebut di masa mendatang.
3. Definisikan command pipeline audit yang akan Anda pasang di pipeline CI untuk memblokir pull request yang mengandung divergen hash lebih dari 20 commit dari upstream branch tanpa approval eksplisit.

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Apa perbedaan mendasar antara Loose Object dan Packfile di dalam direktori internal `.git/objects`?
2. Mengapa merename berkas dari `client.go` menjadi `customer.go` tanpa merubah isinya tidak akan membuat Git membuat objek Blob baru?
3. Informasi spesifik apa saja yang disimpan di dalam objek Commit Git?
4. Apa fungsi dari file `.git/index` pada level arsitektur sistem berkas Git?
5. Mengapa perintah `git push --force-with-lease` jauh lebih direkomendasikan di lingkungan produksi dibanding `git push --force` konvensional?

#### 5 Pertanyaan Intermediate
6. Jelaskan mekanisme perhitungan SHA-1/SHA-256 pada sebuah Blob Git! Mengapa hash dari teks `"hello"` di Git berbeda dengan hash dari perintah command-line `echo -n "hello" | sha1sum`?
7. Apa yang secara internal terjadi pada pointer commit saat developer berada dalam status *detached HEAD*? Apa risiko terbesarnya jika developer membuat commit baru dalam status ini?
8. Bagaimana algoritma 3-way merge bekerja saat menyelesaikan percabangan, dan objek Git apa saja yang dibaca untuk menentukan common ancestor?
9. Jelaskan perbedaan struktural antara *Lightweight Tag* dan *Annotated Tag* dalam representasi direktori `.git/refs/tags/` dan object database!
10. Bagaimana `git gc` (*Garbage Collector*) menentukan bahwa sebuah objek di database Git berstatus "unreachable" dan aman untuk dihapus?

#### 3 Skenario Kasus Produksi
11. **Skenario A**: Tim DevOps Anda mendapati pipeline CI/CD memakan waktu 40 menit hanya untuk fase `actions/checkout`. Setelah dicek, developer memasukkan dataset training sebesar 8 GB secara bertahap pada commit 2 minggu lalu yang kemudian mereka hapus di commit berikutnya. Mengapa repository masih berukuran 8 GB saat diclone meskipun file fisiknya sudah dihapus, dan langkah teknis apa yang harus diambil?
12. **Skenario B**: Seorang developer melakukan rebase branch fiturnya terhadap `main`. Tiba-tiba terminal crash karena kehabisan daya listrik laptop saat rebase sedang berjalan di tengah jalan. Direktori lokalnya kini berada dalam status limbo/error (`interactive rebase in progress`). Perintah apa yang harus dieksekusi untuk memulihkan status repo kembali persis sebelum insiden rebase dimulai tanpa kehilangan kode sama sekali?
13. **Skenario C**: Pada audit kepatuhan SOC2 / ISO 27001, ditemukan bahwa commit yang masuk ke branch produksi dapat dipalsukan atribut nama dan email pengarangnya melalui modifikasi `git config user.name` dan `git config user.email`. Rancang arsitektur verifikasi di level GitHub Organization dan Git CLI untuk menjamin validitas pengirim kode (*non-repudiation*)!

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Jawaban Basic
1. *Loose object* adalah berkas individual terkompresi zlib berisi 1 objek Git (blob/tree/commit). *Packfile* adalah kumpulan ratusan/ribuan objek yang dikompilasi menjadi satu arsip biner dengan *delta compression* (hanya menyimpan perbedaan byte antar versi berkas) untuk menghemat ruang disk dan bandwidth jaringan.
2. Karena Git adalah sistem berbasis *content-addressable*. Blob hanya menyimpan isi konten. Nama berkas disimpan pada objek **Tree**. Mengubah nama berkas hanya menghasilkan Tree baru yang tetap menunjuk ke Hash Blob yang sama.
3. Hash Root Tree, Hash parent commit (nol untuk root commit, satu untuk normal, dua atau lebih untuk merge commit), Author (nama, email, stempel waktu ISO), Committer (nama, email, stempel waktu ISO), dan Pesan commit (commit message).
4. Sebagai *cache layer* biner performa tinggi yang memetakan working tree fisik dengan object store internal, mencatat metadata filesystem POSIX (`stat` data: size, mtime, inode) untuk deteksi mutasi berkas secara instan tanpa membaca ulang seluruh isi file.
5. `git push --force` akan menimpa remote branch secara buta tanpa peduli apakah ada rekan kerja lain yang telah mempush commit baru ke remote tersebut. `--force-with-lease` memeriksa apakah referensi remote lokal (`refs/remotes/origin/...`) identik dengan referensi aktual di remote server; jika ada commit baru milik orang lain yang belum ditarik secara lokal, push akan dibatalkan otomatis.

#### Jawaban Intermediate
6. Git menambahkan header sebelum melakukan hashing: `"blob <size>\0<content>"`. Nilai SHA dihitung dari penggabungan header biner ini ditambah konten berkas mentah, bukan semata-mata dari string kontennya saja.
7. Pointer `HEAD` menunjuk langsung ke sebuah hash commit spesifik, bukan ke sebuah branch reference (`refs/heads/*`). Risikonya: Commit baru yang dibuat di status ini tidak memiliki referensi branch yang memayunginya; jika developer beralih branch (`git switch main`), commit-commit baru tersebut akan terisolasi (*unreachable*) dan sewaktu-waktu akan dimusnahkan secara permanen oleh `git gc`.
8. Git mencari *Lowest Common Ancestor* (LCA) di antara dua branch commit menggunakan algoritma penelusuran graf DAG. Git membaca 3 snapshot Tree: Tree Base (LCA), Tree Branch A (Current/Ours), dan Tree Branch B (Incoming/Theirs). Perubahan dievaluasi terhadap Base. Jika satu branch memodifikasi dan branch lain tidak, perubahan diterima secara otomatis; jika kedua branch memodifikasi blok baris yang sama secara berbeda, Git memicu *merge conflict*.
9. *Lightweight tag* hanyalah teks murni berupa file di `.git/refs/tags/<tag_name>` yang langsung berisi hash commit target (mirip pointer branch statis). *Annotated tag* adalah entitas objek mandiri di `.git/objects/` dengan metadata sendiri (author, date, message, gpg signature), dan file di `refs/tags/` menunjuk ke hash objek tag ini.
10. Objek dinyatakan *unreachable* jika objek tersebut tidak dapat diakses melalui penelusuran graf DAG dari referensi manapun yang valid (`heads`, `tags`, `remotes`, atau entri `reflog`). Git memeriksa usia kadaluarsa objek tersebut (default: `gc.pruneExpire = 2.weeks.ago`) sebelum menghapusnya secara permanen dari pack/loose store.

#### Jawaban Kasus Produksi
11. **Analisis**: Objek biner 8 GB tersebut masih terikat secara kekal pada commit historis masa lampau di DAG database, sehingga operasi clone standar tetap menyedot seluruh loose/pack objects tersebut.
    **Solusi**: Gunakan alat pembersih riwayat seperti `git-filter-repo --strip-blobs-bigger-than 100M` untuk merajut ulang sejarah DAG tanpa blob tersebut. Kadaluarsakan reflog lokal (`git reflog expire --expire=now --all`), eksekusi pembersihan agresif (`git gc --prune=now --aggressive`), dan lakukan force push terkoordinasi ke remote. Pada CI, ubah fetch pipeline menggunakan strategi blobless (`--filter=blob:none`).
12. **Solusi**: Terminal crash tidak merusak database commit Git karena sifatnya yang append-only. 
    1. Periksa histori pointer state via `git reflog`.
    2. Identifikasi commit sebelum rebase dieksekusi (biasanya ditandai action `rebase (start): checkout <base>`).
    3. Jalankan `git rebase --abort` untuk membersihkan direktori temporer `.git/rebase-merge` atau `.git/rebase-apply`.
    4. Jika abort gagal, eksekusi pemulihan paksa: `git reset --hard ORIG_HEAD` atau `git reset --hard HEAD@{n}` merujuk pada hash yang valid di reflog.
13. **Arsitektur Solusi**:
    1. Wajibkan seluruh engineer men-generate SSH/GPG Signing Key yang terasosiasi dengan email korporat resmi dan didaftarkan pada akun GitHub masing-masing.
    2. Konfigurasikan CLI: `git config --global commit.gpgsign true` dan `git config --global gpg.format ssh`.
    3. Di level GitHub Organization Repository Settings: Aktifkan aturan **"Require signed commits"** pada *Branch Protection Rules* / *Repository Rulesets* untuk cabang `main` dan cabang rilis.
    4. Setiap commit tanpa signature kriptografis valid yang cocok dengan identitas akun committer akan ditolak secara mutlak pada level *pre-receive validation engine* remote server.

---

### 16. Summary
- Git adalah **Content-Addressable Storage Engine** yang membungkus antarmuka pelacakan revisi berbasis Graph (DAG).
- Konten file diabstraksikan menjadi **Blob**, struktur direktori dikelola oleh **Tree**, riwayat perubahan direkam oleh **Commit**, dan penandaan rilis diikat oleh **Tag**. Seluruhnya bersifat kekal (*immutable*) dan diidentifikasi via kriptografi hashing.
- Skalabilitas Git di level enterprise ditentukan oleh pemahaman internal arsitektur: memilah penggunaan strategi branching, mengendalikan ukuran direktori `.git` lewat filtering objek biner masif, dan mengoptimalkan latensi CI/CD melalui shallow/blobless clones.
- Pemulihan bencana sistem Git dapat dimitigasi secara deterministik selama data masih tercatat di object database melalui kombinasi `git reflog`, dereferensi hash tingkat rendah, dan inspeksi plumbing commands.
- Integritas rantai pasok perangkat lunak (*software supply chain*) modern bertumpu pada validasi integritas commit bertanda tangan digital (GPG/SSH) yang ditegakkan secara ketat pada branch ruleset produksi.