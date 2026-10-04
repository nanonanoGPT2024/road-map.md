# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (Git Internals & Enterprise Mechanics)

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik pada level Technical Lead / Staff Engineer diharapkan mampu:
1. **Mendekonstruksi Git Plumbing & Database Engine**: Membedah struktur penyimpanan *content-addressable storage* (`.git/objects`), memahami kalkulasi hash SHA-1/SHA-256, serta memanipulasi low-level primitive objects (`blob`, `tree`, `commit`, `annotated tag`).
2. **Menguasai Mekanika Index & DAG Traversal**: Menganalisis binary format file `.git/index` (staging area) dan navigasi algoritma Directed Acyclic Graph (DAG) secara manual menggunakan plumbing commands.
3. **Mengoptimalkan Repository Skala Enterprise**: Mendiagnosis degradasi performa I/O repository besar (Monorepo), mengonfigurasi Sparse Checkout, Shallow Clone, Partial Clone (`treeless`/`blobless`), serta mengelola siklus hidup Packfiles dan Garbage Collection (`git gc`, `git prune`, `git repack`).
4. **Menerapkan Disaster Recovery Tingkat Lanjut**: Merekonstruksi commit graph yang terputus, memulihkan branch yang terhapus permanen melalui `git reflog` parsing, serta membedah dan memperbaiki corrupted object headers.

---

## 2. Prerequisite
Sebelum mendalami modul ini, peserta wajib menguasai:
- Pengetahuan fundamental Git CLI (`git add`, `git commit`, `git push`, `git pull`, `git branch`).
- Pemahaman struktur data dasar: Graf (DAG - Directed Acyclic Graph), Pohon Merkle (Merkle Tree), Hash Table, dan Kompresi zlib/DEFLATE.
- Familiaritas dengan terminal UNIX/Linux, manipulasi file binary via command line (`xxd`, `hexdump`, `shasum`/`sha1sum`), serta pipeline POSIX.

---

## 3. Concept & Internal Architecture (Mendalam)

Git pada intinya bukanlah Version Control System konvensional berbasis delta changes (seperti CVS atau SVN), melainkan sebuah **Content-Addressable Storage Engine berbasis Key-Value** dengan lapisan tracking sistem file (Merkle DAG) di atasnya.

```
       +-----------------------------------------------------------+
       |                  Directed Acyclic Graph                   |
       |                                                           |
       |  [Commit Node: C2] -------- parent -------> [Commit Node: C1]
       |         |                                          |      |
       |     tree sha                                   tree sha   |
       |         v                                          v      |
       |    [Tree: Root]                               [Tree: Root]|
       |     /        \                                 /        \ |
       | [Blob: app] [Tree: src]             [Blob: app] [Tree: src]
       +-----------------------------------------------------------+
                                     |
                                     v
       +-----------------------------------------------------------+
       |        Object Database (.git/objects/xx/yyyy...)          |
       |                                                           |
       |   Header: "<type> <content-length>\0"                     |
       |   Payload: Raw content                                    |
       |   Storage: zlib-deflate compressed binary                 |
       |   Key: SHA-1 / SHA-256 of (Header + Payload)              |
       +-----------------------------------------------------------+
```

### 3.1 Content-Addressable Storage & The 4 Fundamental Objects
Semua entitas data dalam Git disimpan di dalam direktori `.git/objects/`. Key dari setiap object adalah representasi 40 karakter heksadesimal (SHA-1) atau 64 karakter heksadesimal (SHA-256). Git memecah 2 karakter pertama sebagai nama subdirektori dan 38 karakter sisanya sebagai nama file binary untuk menghindari limitasi file-per-directory pada sistem file OS tertentu (seperti ext3/FAT32).

Format penyimpanan binary object sebelum dikompresi zlib:
$$\text{Object Data} = \text{type} + \text{"\textvisiblespace"} + \text{size} + \text{"\textbackslash 0"} + \text{content}$$

Contoh payload:
`blob 14\0Hello, World!\n`

Empat tipe object primitif:
1. **Blob (`type: blob`)**: Menyimpan raw bytes dari sebuah file. Blob tidak menyimpan metadata file (nama file, permission, modification time). Dua file dengan nama berbeda namun ber-content identik akan mereferensikan blob hash yang sama.
2. **Tree (`type: tree`)**: Merepresentasikan struktur direktori. Berisi list terurut dari entry yang terdiri atas: file mode (`100644` untuk standard file, `100755` executable, `040000` subdirectory, `120000` symlink, `160000` gitlink), tipe object, hash SHA target, dan nama file/direktori.
3. **Commit (`type: commit`)**: Node snapshot dalam Merkle DAG. Menyimpan metadata: hash root tree snapshot, nol atau lebih hash commit parent, author (identitas & timestamp penulisan), committer (identitas & timestamp pembuatan commit node), GPG signature (opsional), dan commit message.
4. **Annotated Tag (`type: tag`)**: Pointer permanen yang mengarah ke object spesifik (biasanya commit). Menyimpan tagger metadata, timestamp, tag name, dan cryptographic signature (jika disign). Berbeda dari lightweight tag yang hanya sekadar flat-file reference di `.git/refs/tags/`.

### 3.2 Binary Index Architecture (`.git/index`)
File `.git/index` adalah struktur data binary non-plain-text berkinerja tinggi yang menjembatani **Working Tree** dan **Git Object Database**. Struktur binary ini terdiri dari:
- **12-byte Header**:
  - 4-byte signature: `DIRC` (*Directory Cache*).
  - 4-byte version number: Biasanya versi 2, 3, atau 4.
  - 32-bit integer: Jumlah index entries.
- **Index Entries**: Terurut secara leksikografis berdasarkan path file. Setiap entry mencakup metadata sistem file POSIX (`ctime`, `mtime`, `dev`, `ino`, `mode`, `uid`, `gid`, `file_size`), hash SHA target dari blob, 16-bit flags (stage marker `0` normal, `1` merge base, `2` target branch, `3` incoming branch), dan path string null-terminated.
- **Extensions**: Opsional, seperti Cached Tree Extension (mempercepat kalkulasi `write-tree`), Untracked Cache, dan File System Monitor (FSMonitor).
- **20-byte SHA-1 Checksum**: Hash integritas seluruh content file index sebelum trailer.

### 3.3 Packfile Engine & Delta Compression (`.pack` dan `.idx`)
Menyimpan setiap file versi secara utuh (loose objects) akan menyebabkan fragmentasi disk space dan pemborosan inodes. Git memitigasi ini menggunakan format arsip **Packfile**:
- **Loose Objects**: Object tersimpan individual, dikompresi zlib DEFLATE.
- **Packfile (`.pack`)**: Single multi-megabyte/gigabyte binary stream berisi akumulasi object yang dikompresi dengan delta compression berantai (Directed Delta Chain). Objek versi terbaru disimpan penuh (*whole object*), sedangkan versi terdahulu disimpan sebagai byte-level delta untuk memprioritaskan latensi operasi `checkout` commit mutakhir.
- **Pack Index (`.idx`)**: Binary fan-out table yang memetakan SHA object ke byte-offset presisi di dalam file `.pack`, memungkinkan pembacaan object dengan kompleksitas $O(\log N)$ tanpa membaca seluruh packfile.

### 3.4 Git Reference & Symbolic Refs
- **Direct Ref**: File teks di `.git/refs/heads/<branch-name>` atau `.git/refs/tags/<tag-name>` yang berisi string 40/64 karakter hash object target.
- **Symbolic Ref**: Pointer yang menunjuk ke ref lain, bukan langsung ke hash object. File `.git/HEAD` adalah canonical symbolic ref, berisi misalnya: `ref: refs/heads/main`.
- **Packed Refs**: Untuk menghindari ribuan file kecil di folder `.git/refs/`, Git mengonsolidasikan ref lama ke dalam file `.git/packed-refs`.

---

## 4. Why & What

| Dimensi Analisis | VCS Konvensional (Delta-based / SVN / Perforce) | Git Content-Addressable (Snapshot / Merkle DAG) |
| :--- | :--- | :--- |
| **Model Data** | File diffs terpusat ($V_1 \rightarrow \Delta_1 \rightarrow \Delta_2 \rightarrow V_3$) | Imutable Snapshot Merkle DAG Hash-addressed |
| **Integritas Data** | Berdasarkan trust protokol transport dan database lock | Kriptografis intrinsik (konten termutasi mengubah SHA hash) |
| **Operasi Branching** | Membuat direktori salinan penuh (berat, $O(N)$ filesystem disk) | Menulis 41 byte plain-text file (instan, $O(1)$) |
| **Dependensi Network** | Mayoritas operasi (`log`, `diff`, `commit`) butuh network connection | $100\%$ terdesentralisasi lokal; jaringan hanya untuk rekonsiliasi remote |
| **Delta Resolution** | Delta dihitung maju (forward-delta) saat checkout branch lama | Backward-delta (reverse-packfile) memprioritaskan performa HEAD |

### Nilai Strategis Rekayasa Enterprise:
1. **Auditing Mutlak (Immutability)**: Sejarah commit tidak dapat dimanipulasi tanpa merusak signature root DAG commit berikutnya.
2. **Kinerja Divergensi Cepat**: Pengujian fitur paralel melalui ribuan branch microservices tanpa degradasi resource lokal mesin developer.
3. **Efisiensi Deduplikasi**: Dua file seribu baris identik di direktori berbeda hanya memakan kuota 1 instance blob pada database Git.

---

## 5. How (Workflow Plumbing Detail)

Siklus pembuatan commit tanpa menggunakan porcelain command (`git add`, `git commit`):

```
+-----------------------------------------------------------------------------------+
|                        ALUR LOW-LEVEL PLUMBING GIT                                 |
+-----------------------------------------------------------------------------------+
 1. Raw Files in Workspace
        |
        v  [git hash-object -w <file>]
 2. Write Blob to .git/objects/xx/yyyy...
        |
        v  [git update-index --add --cacheinfo <mode> <sha> <path>]
 3. Mutate Binary In-Memory/Disk Index (.git/index)
        |
        v  [git write-tree]
 4. Traverse Index & Persist Tree Object(s) to .git/objects/
        |
        v  [git commit-tree <tree-sha> -p <parent-sha> -m "message"]
 5. Create Commit Object Node (Pointing to Root Tree & Parent)
        |
        v  [git update-ref refs/heads/main <commit-sha>]
 6. Atomically Advance Symbolic/Direct Branch Reference
+-----------------------------------------------------------------------------------+
```

1. **Persistensi Content**:
   Content file dibaca dari workspace, header diinjeksi, dihitung hash-nya, dikompresi zlib, dan ditulis ke disk loose object path.
2. **Registrasi Index Stage**:
   Metrik OS path dan hash blob didaftarkan ke `.git/index`. Cache tree lama diinvalidasi.
3. **Rekonsiliasi Tree**:
   Index di-parse; tree objects di-generate secara rekursif dari daun (leaf/subdirektori terdalam) hingga akar (root tree).
4. **Penerbitan Commit Node**:
   Commit object dibentuk dengan payload referensi root tree hash, parent commit hash saat ini, signature author, dan commit message.
5. **Transisi Pointer (Ref Update)**:
   File pointer branch pada `refs/heads/<target>` diperbarui ke commit hash baru secara atomik memanfaatkan lockfile pattern (`.git/refs/heads/<target>.lock`).

---

## 6. Analogy & Diagram ASCII

### Analogi: Sistem Logistik Vault Kriptografis
- **Blob** = Dokumen cetak polos tanpa judul atau nomor halaman yang dimasukkan ke dalam brankas kedap udara berlabel hash fingerprint dokumen tersebut.
- **Tree** = Kotak binder transparan yang memiliki daftar isi berlabel: nama folder, permission lemari, dan kartu indeks yang merujuk pada nomor fingerprint dokumen (Blob) atau nomor binder lain (Sub-tree).
- **Commit** = Surat serah terima resmi bersegel lilin berisikan stempel tanggal, nama kurir (Author/Committer), pesan logistik, dan tali fisik yang mengikat kuat ke surat serah terima tugas sebelumnya (Parent Commit).
- **Index** = Meja perakitan sementara. Anda menata binder dan dokumen di meja ini sebelum dipotret dan disegel ke dalam brankas besar.

```
MERKLE DAG ARCHITECTURE:

             [COMMIT: 8a4b3d] (HEAD -> main)
             |-- Tree: e3c1a2 -------------------------+
             |-- Parent: 1f09c2                        |
             |-- Author: Lead Eng <lead@corp.internal> |
             |-- Message: "feat: core auth module"     |
                                                       |
                        +------------------------------+
                        |
                        v
                 [TREE: e3c1a2] (root)
                 |-- 100644 blob 4b825d (README.md)
                 |-- 040000 tree 9d2f1a (src/)
                               |
                               +-----------------------+
                                                       |
                                                       v
                                                [TREE: 9d2f1a] (src)
                                                |-- 100755 blob a1c3e4 (main.py)
                                                |-- 100644 blob f7e8d9 (config.json)
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Membangun Commit Secara Manual Melalui Plumbing Commands
Contoh ini mendemonstrasikan pembentukan commit dari nol murni menggunakan engine plumbing commands tanpa `git add` atau `git commit`.

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Inisialisasi repo kosongan murni
rm -rf test-plumbing && mkdir test-plumbing && cd test-plumbing
git init

# 2. Buat file secara manual
echo "console.log('enterprise-runtime-v1');" > app.js

# 3. Masukkan payload ke object database (menghasilkan SHA-1 blob)
BLOB_SHA=$(git hash-object -w app.js)
echo "Blob Generated: ${BLOB_SHA}"

# 4. Daftarkan blob secara manual ke dalam file .git/index
git update-index --add --cacheinfo 100644 "${BLOB_SHA}" app.js

# 5. Tulis representasi tree dari stage index saat ini
TREE_SHA=$(git write-tree)
echo "Root Tree Generated: ${TREE_SHA}"

# 6. Bentuk commit object node yang menunjuk ke tree tersebut
COMMIT_SHA=$(echo "chore: initial plumbing baseline" | git commit-tree "${TREE_SHA}")
echo "Commit Generated: ${COMMIT_SHA}"

# 7. Arahkan reference master/main ke commit baru
git update-ref refs/heads/main "${COMMIT_SHA}"

# 8. Set HEAD agar menunjuk ke branch main
git symbolic-ref HEAD refs/heads/main

# Verifikasi integritas log dan workspace
git log -p -1
git status
```

### 7.2 Practical Example: Custom Merkle Object Decoder dalam Shell Script
Skrip produksi untuk menginspeksi struktur binary internal, dekompresi object zlib, dan validasi rekursif Merkle Tree.

```bash
#!/usr/bin/env bash
# File: inspect_git_internals.sh
# Deskripsi: Membaca raw zlib object dan mendekonstruksi binary header Git.
set -euo pipefail

inspect_object() {
    local target_sha="$1"
    local prefix="${target_sha:0:2}"
    local suffix="${target_sha:2}"
    local obj_path=".git/objects/${prefix}/${suffix}"

    if [[ ! -f "${obj_path}" ]]; then
        echo "Error: Objek ${target_sha} tidak berada di path ${obj_path} (Loose Object)." >&2
        echo "Objek kemungkinan terkompresi di dalam Packfile (.pack)." >&2
        return 1
    fi

    echo "=== MEMERIKSA OBJECT: ${target_sha} ==="
    echo "Path Lokasi File: ${obj_path}"
    
    # 1. Ekstrak Header dan Payload mentah menggunakan zlib decompressor
    echo "--- Raw Zlib Uncompressed Stream (Tampilkan Hex & ASCII) ---"
    python3 -c '
import zlib, sys
with open(sys.argv[1], "rb") as f:
    decompressed = zlib.decompress(f.read())
    header, _, content = decompressed.partition(b"\x00")
    print(f"HEADER DITEMUKAN: {header.decode(\"latin1\")}")
    print(f"PANJANG PAYLOAD: {len(content)} bytes")
' "${obj_path}"

    echo "--- Evaluasi Tipe Lewat Plumbing git cat-file ---"
    local obj_type
    obj_type=$(git cat-file -t "${target_sha}")
    local obj_size
    obj_size=$(git cat-file -s "${target_sha}")
    echo "Tipe Objek : ${obj_type}"
    echo "Ukuran Asli : ${obj_size} bytes"

    echo "--- Representasi Konten Internal ---"
    git cat-file -p "${target_sha}"
    echo -e "========================================================\n"
}

# Contoh Eksekusi Validasi
if [[ ! -d ".git" ]]; then
    echo "Skrip ini wajib dijalankan di dalam root Git repository." >&2
    exit 1
fi

HEAD_COMMIT=$(git rev-parse HEAD)
inspect_object "${HEAD_COMMIT}"

ROOT_TREE=$(git rev-parse HEAD^{tree})
inspect_object "${ROOT_TREE}"
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Krisis Performa Git pada Monorepo FinTech (120 GB, 45 Juta Objek)
*Konteks Organisasi*: Perusahaan payment gateway global menjalankan 250 microservices di dalam satu monorepo Git sentral. Terdapat 2.200 insinyur software aktif dan 40.000 automated CI runs per hari.

```
                ARSITEKTUR MONOREPO FILTER STREAMING PIPELINE:
                
+-----------------------+               +--------------------------------------+
|  Remote Server Central|               |       Local Developer Machine        |
|   (GitHub Enterprise) |               |                                      |
|                       |               | 1. Blobless Clone:                   |
| 120 GB Full Repo DB   |               |    git clone --filter=blob:none      |
| (Trees, Commits,      |=== (Network) =|    -> Download: Tree & Commits ONLY  |
|  All Historical Blobs)|  Fast Meta    |    -> Size: ~2.1 GB (Bukan 120 GB)   |
|                       |               |                                      |
|                       |<== On-Demand =| 2. Sparse Checkout:                  |
|                       |   Lazy Blob   |    git sparse-checkout set /svc/core |
|                       |     Fetch     |    -> Render Filesystem: 1 service   |
+-----------------------+               +--------------------------------------+
```

### Masalah Akut
1. **CI Pipeline Latency**: Operasi `git clone` memakan waktu rata-rata 38 menit per build agent, mengakibatkan antrean CI macet dan konsumsi bandwidth terabyte per jam.
2. **Developer Workstation Thrashing**: Operasi `git status` lokal memakan waktu 45 detik karena kernel OS harus memindai (*stat*) 1,2 juta file fisik pada disk.
3. **Packfile Explosion**: File `.git/objects/pack/` rusak berkala akibat batasan file deskriptor 32-bit offset dan kegagalan memory allocation (OOM) saat remote server menjalankan garbage collection otomatis.

### Solusi Arsitektur
Arsitektur engineering dialihkan dari representasi monolithic-full-copy menjadi **Selective Projection & Virtualized Fetch Pipeline**:

#### 1. Implementasi Blobless Clone pada CI/CD Runners
Runner CI tidak memerlukan riwayat komit lampau beserta payload blobless-nya. Penerapan teknik *Partial Clone*:
```bash
# Tarik hanya komit dan tree, abaikan SEMUA historical blob sampai file tersebut diakses
git clone --filter=blob:none --no-checkout --depth=1 https://git.internal.corp/monorepo.git
cd monorepo
git checkout main
```
*Hasil*: Waktu clone CI turun drastis dari **38 menit menjadi 14 detik**. Bandwidth per build turun sebesar 97.4%.

#### 2. Implementasi Sparse-Checkout Cone Mode & FSMonitor pada Workstation Developer
Untuk tim yang hanya mengerjakan `services/payment-routing`:
```bash
git clone --filter=blob:none --sparse https://git.internal.corp/monorepo.git
cd monorepo
git sparse-checkout init --cone
git sparse-checkout set services/payment-routing libs/shared-kernel

# Aktifkan Built-in File System Monitor (memanfaatkan epoll/kqueue daemon)
git config core.fsmonitor true
git config core.untrackedCache true
```
*Hasil*: `git status` latency turun drastis dari **45 detik menjadi 82 milidetik**, karena Git tidak lagi melakukan readdir/stat ke jutaan path yang tidak relevan.

#### 3. Rekonfigurasi Repacking Engine Server
Pengoptimalan packfile limits dan multi-pack indexes pada host Git enterprise:
```bash
# Aktifkan multi-pack index (MIDX) untuk indexing silang beberapa packfile raksasa
git config core.multiPackIndex true

# Set memory limits untuk dynamic delta matching engine
git config pack.windowMemory "256m"
git config pack.packSizeLimit "2g"
git config pack.threads "16"

# Jalankan repack non-blocking terjadwal
git repack -a -d -F --max-pack-size=2g
git multi-pack-index write
```

---

## 9. Trade-offs

| Parameter | Shallow Clone (`--depth=N`) | Blobless Clone (`--filter=blob:none`) | Treeless Clone (`--filter=tree:0`) | Full Mirror Clone |
| :--- | :--- | :--- | :--- | :--- |
| **Download Size** | Paling Minimum (Kecil) | Sangat Ringan | Ekstrem Kecil | Sangat Besar (Utuh) |
| **Network Latency Initial** | Sangat Rendah | Rendah | Paling Rendah | Tinggi |
| **Network Latency Runtime** | Menolak operasi di luar batas depth | Menarik blob saat `diff`/`checkout` | Menarik tree & blob saat `checkout` | **Zero Latency** (Lokal 100%) |
| **Kelayakan Merge / Rebase** | Buruk (Sering gagal resolusi Merge Base) | **Sempurna** (Merkle graph komit lengkap) | Lambat (Harus fetch tree secara berkala) | Sempurna |
| **Beban Server Target** | Kalkulasi pack cut-off dinamis (CPU berat) | Cepat (Server bypass blob streaming) | Cepat | Rendah (Menyajikan pre-computed packfile) |
| **Use-Case Optimal** | Ephemeral Linting / Simple build | Standard Developer Workspace | Extreme micro-containers | Deep offline analysis / Disaster Backup |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Keadaan Detached HEAD (Analisis Akar Masalah & Mitigasi)
*Masalah*: Developer mengeksekusi `git checkout <commit-sha>`. Pointer `.git/HEAD` tidak lagi menunjuk ke symbolic reference branch (`refs/heads/...`), melainkan langsung menunjuk ke commit hash. Setiap commit baru yang dibuat pada status ini akan menjadi yatim piatu (*orphaned/dangling*) saat developer beralih ke branch lain.

```bash
# Deteksi status
git status
# "HEAD detached at a1b2c3d"

# Pemeriksaan internal
cat .git/HEAD
# Berisi hash langsung: "a1b2c3d4e5f..." bukan "ref: refs/heads/..."

# Solusi Pemulihan Tanpa Kehilangan Commit Baru:
# Buat dan alihkan branch langsung dari posisi detached saat ini
git branch emergency-salvage-branch
git checkout emergency-salvage-branch
# Sekarang HEAD terikat secara aman pada symbolic reference branch baru
```

### 10.2 Merestorasi Hard Rebase/Reset Bencana via `.git/reflog`
*Masalah*: Perintah `git reset --hard HEAD~5` dijalankan secara keliru pada branch production-ready; 5 commit krusial hilang seketika dari `git log`.

*Mitigasi & Restorasi*:
```bash
# 1. Buka audit trail internal mutasi ref
git reflog show HEAD

# Output contoh:
# 3a1b2c4 (HEAD -> main) HEAD@{0}: reset: moving to HEAD~5
# 9f8e7d6 HEAD@{1}: commit: feat(security): mTLS mutual authentication
# ...

# 2. Periksa status objek yang tertinggal
git show 9f8e7d6

# 3. Kembalikan state pointer secara instan
git reset --hard HEAD@{1}

# Atau amankan ke branch lain:
git branch recovered-state 9f8e7d6
```

### 10.3 Fatal Error: `index.lock` File Exists
*Masalah*: Error `fatal: Unable to create '.git/index.lock': File exists.`
*Mekanisme Pertahanan Git*: Setiap kali file index dimodifikasi, Git menciptakan lockfile atomik `.git/index.lock`. Jika proses Git crash atau di-kill via `SIGKILL` di tengah jalan, lockfile ini tertinggal.

*Troubleshooting*:
```bash
# Verifikasi apakah benar ada proses Git zombie yang masih berjalan
ps aux | grep git

# Jika tidak ada proses aktif yang memegang file tersebut:
rm -f .git/index.lock
```

### 10.4 Mengidentifikasi dan Memperbaiki Corrupted Objects
*Masalah*: `error: object file .git/objects/4b/825dc... is empty` atau `fatal: loose object ... is corrupt`.

*Diagnosa*:
```bash
# Jalankan audit integritas basis data Merkle DAG
git fsck --full

# Output mendeteksi:
# broken link from tree 112233... to blob 4b825d...
# error: sha1 file .git/objects/4b/825dc... is empty
```

*Prosedur Emergency Fix*:
```bash
# 1. Cari file di workspace yang memiliki kemungkinan hash tersebut
# Menggunakan plumbing hash-object
find . -type f -not -path '*/.*' -exec git hash-object {} + | grep "4b825d"

# 2. Jika file ditemukan di working tree, tulis ulang objek ke database:
git hash-object -w path/to/matching/file.ts

# 3. Jalankan kembali pemeriksaan
git fsck --full
```

---

## 11. Best Practices (Production Checklist)

### Security & Sanitasi Repository
- [ ] **Cryptographic Signing**: Terapkan signed commits menggunakan SSH keys atau GPG keys (`git config --global commit.gpgsign true`).
- [ ] **Pre-commit Secrets Interception**: Gunakan scanning engine deterministik (seperti `gitleaks` atau `trufflehog`) pada client-side dan server-side commit hook.
- [ ] **Sanitasi Objek Sensitif**: Jika credential ter-commit ke dalam DAG, jangan gunakan porcelain revert! Lakukan purging permanen dari seluruh packfile dan reflog menggunakan tool performan tinggi `git-filter-repo` (bukan `git filter-branch` yang deprecated dan rawan korupsi data).

### Kinerja & Pemeliharaan Storage
- [ ] **Konfigurasi Git GC Otomatis**: Set parameter window memory agar tidak memicu Out-of-Memory pada server CI/CD.
  ```bash
  git config --global gc.auto 6700
  git config --global gc.pruneExpire "14.days.ago"
  git config --global gc.reflogExpire "30.days.ago"
  ```
- [ ] **Commit Graph Acceleration**: Aktifkan commit-graph file binary untuk mempercepat traversal log jutaan commit.
  ```bash
  git config --global core.commitGraph true
  git commit-graph write --reachable
  ```
- [ ] **Multi-Pack Indexing**: Konsolidasikan akses packfile monorepo.
  ```bash
  git multi-pack-index write
  ```

---

## 12. Hands-on Practice

Buat direktori latihan terisolasi untuk modul ini pada path: `hands-on/m02/`. Ikuti instruksi langkah demi langkah di bawah ini.

```bash
#!/usr/bin/env bash
# Hands-on M02: Bedah Total Internal Git
set -euo pipefail

mkdir -p hands-on/m02/internals-lab
cd hands-on/m02/internals-lab

# Langkah 1: Inisialisasi Environment Lab
git init
echo "# Core Engine Documentation" > README.md
mkdir src
echo "export const API_VERSION = 'v2.1.0';" > src/version.ts

# Langkah 2: Inspeksi Database SEBELUM Staging
echo ">> Memeriksa isi .git/objects awal:"
find .git/objects -type f

# Langkah 3: Eksekusi Staging dan Analisis Pembuatan Loose Objects
git add README.md src/version.ts

echo ">> Memeriksa isi .git/objects setelah 'git add':"
find .git/objects -type f

# Langkah 4: Baca Binary Index Header
echo ">> Membaca signature DIRC dari .git/index:"
xxd -l 12 .git/index

# Langkah 5: Commit Snapshot
git commit -m "feat: infrastructure release initialization"

# Langkah 6: Menguraikan Hash Komit Menjadi Merkle Chain
COMMIT_HASH=$(git rev-parse HEAD)
echo ">> Commit Hash Aktif: ${COMMIT_HASH}"

echo ">> Mendekode Objek Commit:"
git cat-file -p "${COMMIT_HASH}"

ROOT_TREE_HASH=$(git cat-file -p "${COMMIT_HASH}" | grep "tree" | awk '{print $2}')
echo ">> Root Tree Hash: ${ROOT_TREE_HASH}"

echo ">> Mendekode Objek Root Tree:"
git cat-file -p "${ROOT_TREE_HASH}"

SRC_TREE_HASH=$(git cat-file -p "${ROOT_TREE_HASH}" | grep "src" | awk '{print $3}')
echo ">> Subtree src/ Hash: ${SRC_TREE_HASH}"

echo ">> Mendekode Objek Subtree src/:"
git cat-file -p "${SRC_TREE_HASH}"

VERSION_BLOB_HASH=$(git cat-file -p "${SRC_TREE_HASH}" | grep "version.ts" | awk '{print $3}')
echo ">> Blob version.ts Hash: ${VERSION_BLOB_HASH}"

echo ">> Mengambil raw payload dari Blob version.ts:"
git cat-file -p "${VERSION_BLOB_HASH}"

# Langkah 7: Eksperimen Repacking & Kompresi Multi-Object
echo ">> Memicu pemaketan objek menjadi Packfile tunggal:"
git repack -a -d

echo ">> Memeriksa isi direktori .git/objects pasca-repack:"
find .git/objects -type f

echo ">> Membedah index Packfile (.idx):"
IDX_FILE=$(find .git/objects/pack/ -name "*.idx")
git show-index < "${IDX_FILE}"

echo "=== HANDS-ON SELESAI SECARA SEMPURNA ==="
```

---

## 13. Exercise

### Level Easy
1. Gunakan perintah `git hash-object` untuk menghitung SHA-1 dari string `"enterprise-architecture\n"` tanpa menyimpannya ke disk database.
2. Temukan symbolic reference dari file `.git/HEAD` secara manual menggunakan shell POSIX standar (tanpa perintah Git) dan deskripsikan hasilnya.

### Level Medium
1. Buat branch bernama `hotfix-zero` murni menggunakan perintah `git update-ref` langsung menunjuk ke commit hash terakhir pada branch `main`. Pastikan branch baru tersebut terdaftar valid pada `git branch -v`.
2. Hapus branch `main` secara tidak sengaja menggunakan `git branch -D main`. Pulihkan branch tersebut ke posisi persis sebelum dihapus dengan memvalidasi pointer logik dari `.git/logs/refs/heads/`.

### Level Hard
1. Buat sebuah shell script mandiri yang mengonstruksi sebuah hierarki Git repo valid berisi struktur:
   ```
   infra/
     terraform/
       main.tf
   ```
   Ketentuan:
   - **DILARANG KERAS** menggunakan porcelain commands (`git add`, `git commit`, `git checkout`).
   - Wajib menggunakan secara eksklusif kombinasi: `git hash-object -w`, `git update-index --add --cacheinfo`, `git write-tree`, `git commit-tree`, dan `git update-ref`.
   - Validasi hasil akhir dengan menjalankan `git log --stat` dan `git status`, di mana output working tree harus berstatus clean (*nothing to commit, working tree clean*).

---

## 14. Challenge

### Studi Kasus: Rekonstruksi Database Git yang Rusak Akibat Hardware Crash

**Skenario**:
Sebuah disk volume server produksi mengalami pemadaman daya mendadak (*ungraceful power-cut*) tepat saat sebuah tim mengintegrasikan rilis core banking. Terjadi insiden fatal:
1. File `.git/HEAD` terisi nilai kosong (0 bytes/corrupted).
2. Direktori `.git/refs/heads/` kosong seluruhnya karena filesystem metadata flush tertunda.
3. Namun, direktori `.git/objects/` tetap utuh dan berisi ratusan loose objects serta packfiles.
4. Tim tidak memiliki backup lokal terbaru selain repositori server yang rusak tersebut.

**Tugas Anda (Senior Staff Architect)**:
Rancang dan eksekusi strategi penyelamatan sistem secara terstruktur:
- Temukan kembali root commit terakhir yang paling mutakhir secara deterministik menggunakan algoritma traversal graf dari loose objects yang ada.
- Identifikasi objek-objek commit yang berstatus *dangling/unreferenced*.
- Rekonstruksi file `HEAD` dan kembalikan branch `main` ke state snapshot paling akhir sebelum pemadaman.
- Validasi integritas pohon Merkle secara komprehensif hingga `git fsck --full` mengembalikan status exit code 0 tanpa error fatal.

*(Peringatan: Tidak ada jawaban instan otomatis; Anda harus memanfaatkan karakteristik commit header dan algoritma directed acyclic graph traversal).*

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda / Konseptual Singkat)
1. Apa header standar yang diinjeksi Git ke konten file sebelum menghitung checksum SHA-1 pada object `blob`?
2. Mengapa Git membagi nama direktori objek pada 2 karakter pertama di `.git/objects/xx/`?
3. Sebutkan perbedaan mendasar antara representasi file `blob` dan node `tree` di Git!
4. Di manakah Git menyimpan nama file dan file permission (`chmod`) dari suatu file dalam repository?
5. Apa isi internal dari sebuah direct reference branch seperti file `.git/refs/heads/feature-auth`?

### Bagian 2: Intermediate (Analisis Kritis)
1. Mengapa forward-delta compression (seperti yang digunakan RCS/SVN) dinilai tidak optimal untuk alur kerja Git modern dibandingkan dengan backward-delta compression pada Packfile?
2. Apa yang sebenarnya terjadi pada binary format `.git/index` ketika sebuah file di dalam working directory mengalami modifikasi namun belum dieksekusi `git add`?
3. Analisis skenario berikut: Mengapa dua developer berbeda yang menulis file identik di subdirektori berbeda akan menghasilkan hash SHA blob yang identik, tetapi hash SHA tree direktori mereka berbeda?
4. Jelaskan bagaimana *Merkle Tree Property* pada Git menjamin bahwa pemalsuan historical commit 5 tahun lalu akan membatalkan validitas seluruh commit anak hingga `HEAD`!
5. Apa perbedaan arsitektural operasional antara perintah `git fetch --depth=1` (Shallow Clone) dan `git fetch --filter=blob:none` (Partial Blobless Clone)?

### Bagian 3: Skenario Kasus Produksi
1. **Skenario CI/CD Timeout**:
   Pipeline enterprise Anda memakan waktu 40 menit hanya untuk fase checkout repositori 80 GB. Jika runner Anda hanya membutuhkan riwayat commit paling mutakhir untuk memvalidasi linting dan unit test pada commit tersebut, rekomendasikan konfigurasi Git network checkout yang paling hemat waktu dan resource, serta jelaskan alasannya!
2. **Skenario Corrupted Loose Object**:
   Setelah sebuah node CI mati mendadak, pipeline melempar error: `fatal: loose object a3f1c2d... is corrupt`. Langkah terstruktur apa yang harus Anda lakukan untuk mendeteksi file mana yang diasosiasikan dengan object tersebut dan bagaimana cara memulihkannya jika salinan aslinya masih ada di remote mirror?
3. **Skenario Pembersihan Kredensial**:
   Sebuah API Private Key AWS ter-commit dan ter-push ke repository 6 bulan lalu. Seorang engineer melakukan `git revert <commit-sha>`. Jelaskan secara teknis arsitektur mengapa langkah tersebut **sama sekali tidak menyelesaikan masalah keamanan**, dan bagaimana solusi permanen standar industri untuk menuntaskannya!

---

## 16. Summary

1. **Git adalah Content-Addressable Engine**: Git mengabstraksikan file system sebagai key-value database immutable terdistribusi yang diindeks oleh hash kriptografis kontennya (SHA-1/SHA-256).
2. **4 Primitive Engine Objects**: Seluruh snapshot riwayat Git didekonstruksi secara murni dari 4 entitas object fundamental: `blob` (data mentah), `tree` (struktur direktori & permissions), `commit` (node metadata graph & log riwayat), serta `tag` (annotated bookmark permanen).
3. **Merkle DAG Core**: Integritas data Git dijamin oleh sifat kriptografis Merkle DAG. Setiap mutasi pada daun (leaf/blob) akan berpropagasi ke atas, mengubah seluruh tree hash hingga commit hash root-nya.
4. **Optimasi Monorepo Enterprise**: Mengelola repository raksasa memerlukan pergeseran dari paradigma salinan penuh (*full-copy*) menuju *Selective On-Demand Traversal* menggunakan **Blobless Partial Clones**, **Sparse Checkout Cone Mode**, dan **Multi-Pack Indexing (MIDX)**.
5. **Kekuatan Git Plumbing**: Penguasaan low-level plumbing commands memberikan kontrol penuh dalam pemulihan bencana (*disaster recovery*), otomatisasi infrastruktur scale-out, dan debugging performa sistem Git pada skala enterprise.