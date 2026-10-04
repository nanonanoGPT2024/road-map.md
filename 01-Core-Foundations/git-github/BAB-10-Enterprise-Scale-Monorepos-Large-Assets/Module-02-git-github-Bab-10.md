# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengurai struktur penyimpanan internal Git (Plumbing Architecture): *Directed Acyclic Graph* (DAG), *Loose Objects*, *Packfiles*, *Delta Compression*, dan mekanisme *Git Reference Transaction*.
- Mengimplementasikan topologi performa tinggi untuk repositori skala *Enterprise* (*Monorepo* puluhan *gigabyte*) menggunakan `sparse-checkout`, `git worktree`, `Scalar`, dan `partial clone` (`blobless`/`treeless`).
- Merancang dan mengeksekusi pipeline optimasi database Git melalui *garbage collection* tingkat lanjut (`git gc`, `git prune`, `repack`, `multi-pack-index` / MIDX, dan `commit-graph`).
- Mengotomatisasi validasi integritas repositori dan *security governance* menggunakan Custom Hooks (Client & Server-side hooks) yang terintegrasi dengan runtime enterprise.
- Melakukan remedi skala masif terhadap polusi riwayat (*history pollution*) dan insiden kebocoran kredensial menggunakan engine performa tinggi `git-filter-repo`.

---

## 2. Prerequisites
Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Git Fundamentals**: Branching, merging, rebasing, resolving conflicts, serta siklus hidup *three-tree architecture* (Working Directory, Index/Staging, HEAD).
- **Sistem Berkas & CLI Linux/POSIX**: Operasi Bash/Zsh tingkat menengah, POSIX streams (`stdin`, `stdout`, `stderr`), file permissions (`chmod`, file execution contexts), dan environment variables.
- **Kriptografi Dasar**: Hash collision resistance, SHA-1 vs SHA-256, dan mekanisme tanda tangan digital asimetris (GPG/SSH commit signing).

---

## 3. Concept & Internal Architecture (Mendalam)

### A. The Object Database (ODB) & Directed Acyclic Graph (DAG)
Git secara fundamental adalah sebuah **Content-Addressable Storage Engine** yang dilapisi oleh antarmuka sistem kendali versi (*version control interface*). Semua data disimpan di dalam folder `.git/objects/`.

Git mendefinisikan 4 tipe objek dasar yang bersifat *immutable*:
1. **Blob**: Menyimpan representasi *payload* data murni (isi berkas) tanpa metadata sistem berkas (nama berkas, mode perizinan dieksklusikan).
2. **Tree**: Menyimpan array referensi yang merepresentasikan direktori, berisi mode perizinan POSIX, tipe objek (blob atau sub-tree), hash SHA target, dan nama berkas/direktori.
3. **Commit**: Mengikat *root tree*, mereferensikan nol atau lebih *parent commit hashes*, metadata penulis (*author*), penyimpan (*committer*), timestamp, serta *commit message*.
4. **Annotated Tag**: Objek independen yang menunjuk langsung ke commit hash tertentu, menyimpan metadata penandatangan, pesan, dan signature opsional.

Format serialisasi objek di disk:
```text
[tipe_objek] [ukuran_payload_dalam_bytes]\0[isi_payload_biner]
```
Data di atas dikompresi menggunakan pustaka **zlib (deflate)** dan disimpan pada path yang ditentukan dari 2 karakter pertama hash sebagai direktori dan 38 karakter berikutnya sebagai nama berkas (contoh: `.git/objects/4b/825dc642cb6eb9a060e54bf8d69288fbee4904`).

```
                +-------------------+
                |   Commit Object   |
                | (Metadata+Author) |
                +---------+---------+
                          |
                          v
                +-------------------+
                |    Tree Object    |
                |    (Directory)    |
                +----+---------+----+
                     |         |
           +---------+         +---------+
           v                             v
+-------------------+           +-------------------+
|    Tree Object    |           |    Blob Object    |
|  (Sub-directory)  |           |      (File)       |
+---------+---------+           +-------------------+
          |
          v
+-------------------+
|    Blob Object    |
|      (File)       |
+-------------------+
```

### B. Packfiles, Thin Packs, Multi-Pack-Index (MIDX), & Commit-Graph
Menyimpan setiap versi berkas sebagai *loose object* individual akan menghabiskan *inode* pada sistem berkas dan memperlambat I/O. Git mengatasi ini melalui arsitektur kompresi sekunder:

- **Packfile (`.pack`) & Index (`.idx`)**: Git mengelompokkan ribuan *loose objects* ke dalam satu berkas biner `.pack`. Berkas pasangan `.idx` menggunakan struktur *fan-out table* 256-entri dan *binary search table* terurut untuk memetakan SHA-1/SHA-256 ke offset biner presisi di dalam berkas `.pack`.
- **Directed Delta Compression**: Di dalam packfile, Git tidak menyimpan *full-snapshot* untuk setiap revisi berkas yang mirip. Git menggunakan algoritma pencarian jendela geser (*sliding window*) untuk mendeteksi kesamaan data, lalu menyimpan satu versi sebagai *base object* dan versi-versi lainnya sebagai rangkaian byte diferensial (*delta compression*).
- **Commit-Graph Engine**: Format biner `.git/objects/info/commit-graph` menyimpan struktur DAG commit secara linear untuk mengeliminasi kebutuhan parsing berkas commit zlib individual saat melakukan kalkulasi traversi graf (seperti `git log --graph`, merge-base resolution, dan commit reachability).
- **Multi-Pack-Index (MIDX)**: Ketika repositori memiliki puluhan file `.pack`, MIDX menyediakan lapisan indeks terpadu tunggal (`.git/objects/pack/multi-pack-index`) untuk mencegah pencarian linear di seluruh `.idx` yang terfragmentasi.

### C. Git Protocol v2 & Reference Advertising
Pada Protocol v1, server mengirimkan seluruh daftar referensi (*refs advertisement*) ke klien saat negosiasi dimulai. Jika repositori memiliki 500.000 tags dan branches, klien harus mengunduh megabyte metadata sebelum pertukaran commit dimulai.
**Git Protocol v2** mengubah interaksi menjadi *multiplexed command-response*:
- Menyediakan kapabilitas *filtering* langsung di level server. Klien hanya meminta refspec tertentu (`command=ls-refs` dengan filter).
- Memungkinkan *Partial Clone* natively (`fetch` payload dengan parameter `filter=blob:none` atau `filter=tree:0`).

---

## 4. Why & What

| Fitur / Konsep | Masalah yang Diselesaikan (Why) | Solusi Arsitektural (What) |
| :--- | :--- | :--- |
| **Git Worktree** | *Stashing* atau commit parsial saat berganti konteks fitur darurat mengganggu proses kompilasi lokal dan merusak cache build. | Membuka cabang berbeda secara simultan di direktori independen, namun tetap berbagi satu database `.git` yang sama. |
| **Sparse Checkout** | Repositori monorepo raksasa (>20GB) membebani kapasitas disk workstation lokal dan melumpuhkan kecepatan sistem berkas OS. | Menginstruksikan Git untuk hanya memproyeksikan sub-set path direktori tertentu ke working directory lokal. |
| **Partial Clone** | Durasi clone monorepo sangat lama akibat transfer ribuan commit riwayat berkas biner lama. | Klien hanya mengunduh tree & commit history (`blobless`), memicu fetch *on-demand* hanya ketika blob spesifik diakses. |
| **Commit-Graph & MIDX** | Operasi CI/CD checkout dan traversi cabang melambat secara eksponensial seiring bertambahnya commit. | Struktur data biner terindeks yang mengoptimalkan komputasi traversi DAG dari $O(N)$ menjadi mendekati $O(1)$. |
| **git-filter-repo** | `git filter-branch` berbasis shell loop lambat (berhari-hari pada repositori besar) dan sering merusak metadata commit. | Engine manipulasi DAG performa tinggi berbasis Python/C yang menulis ulang byte-stream fast-import secara paralel. |

---

## 5. How (Workflow Detail)

### A. Lifecycle Traversing: Plumbing Layer vs Porcelain Layer
Git memisahkan arsitektur perintah menjadi dua tingkatan:
1. **Porcelain**: Perintah level tinggi ramah pengguna (`git add`, `git commit`, `git checkout`).
2. **Plumbing**: Perintah primitif level rendah berkinerja tinggi yang berinteraksi langsung dengan object storage engine (`git hash-object`, `git mktree`, `git commit-tree`, `git update-ref`).

Alur eksekusi internal saat sebuah commit dibuat secara atomik:
```
[Unstaged Files] 
       │
       ▼ (git hash-object -w <file>)
[Write Loose Objects: Blobs]
       │
       ▼ (git update-index --add --cacheinfo <mode>,<hash>,<path>)
[Update .git/index (Binary Cache)]
       │
       ▼ (git write-tree)
[Write Loose Objects: Tree/Sub-trees]
       │
       ▼ (git commit-tree <tree-hash> -p <parent-hash> -m "feat: msg")
[Write Loose Objects: Commit]
       │
       ▼ (git update-ref refs/heads/main <commit-hash>)
[Atomic Ref Pointer Transaction]
```

### B. Monorepo Optimization Lifecycle
1. **Konfigurasi Git Engine v2 Global**:
   ```bash
   git config --global protocol.version 2
   ```
2. **Inisialisasi Blobless Clone**:
   Klien mengabaikan transfer blob historis, hanya mengambil commit & trees.
   ```bash
   git clone --filter=blob:none --no-checkout <repository-url>
   ```
3. **Penerapan Concurrency Sparse Checkout**:
   Batasi direktori yang diproyeksikan hanya pada domain service yang dikembangkan.
   ```bash
   git sparse-checkout init --cone
   git sparse-checkout set services/payment-gateway libs/common-auth
   git checkout main
   ```
4. **Paralelisasi Workspace dengan Git Worktree**:
   Buat sandbox instan untuk *hotfix* tanpa mengotori ruang kerja saat ini.
   ```bash
   git worktree add ../hotfix-payment-patch -b hotfix/PAY-2024
   ```

---

## 6. Analogy & Diagram ASCII

### Analogi: Sistem Pengarsipan Perusahaan
Bayangkan Git sebagai sistem brankas dokumen rahasia terpusat:
- **Blob**: Lembaran fotokopi dokumen tanpa judul dan tanpa tanggal. Diidentifikasi murni berdasarkan sidik jari unik tinta dokumen tersebut (Content Hash).
- **Tree**: Daftar isi folder map fisik. Menyebutkan: "Di dalam map ini ada dokumen bertanda sidik jari X dengan label 'neraca.xlsx', dan ada map cabang Y".
- **Commit**: Berkas memo bersegel resmi bertanggal yang menyatakan: "Pada hari ini, struktur map yang sah adalah folder Tree Z, melanjutkan pekerjaan dari memo sebelumnya".
- **Worktree**: Meja kerja terpisah di ruangan lain. Anda tidak perlu menyalin brankas dokumen; Anda cukup menarik dokumen dari brankas yang sama ke meja baru.

### Diagram: Multi-Worktree Architecture Shared Database

```text
    Local Workstation Filesystem
    ========================================================================================

    Directory: /work/main-dev/                    Directory: /work/hotfix-patch/
    (Active Branch: feature/core)                 (Active Branch: hotfix/vuln-101)
    +------------------------------------+        +------------------------------------+
    | Working Directory:                 |        | Working Directory:                 |
    | - src/core/main.go                 |        | - src/core/main.go                 |
    | - src/core/engine.go               |        | - src/core/engine.go               |
    |                                    |        |                                    |
    | .git (Pointer File)                |        | .git (Pointer File)                |
    | "gitdir: /work/main-dev/.git/..."  |        | "gitdir: /work/main-dev/.git/..."  |
    +-----------------+------------------+        +-----------------+------------------+
                      |                                             |
                      +----------------------+----------------------+
                                             |
                                             v
                      +---------------------------------------------+
                      | Canonical Shared .git Directory:            |
                      | /work/main-dev/.git/                        |
                      |                                             |
                      | ├── objects/  <-- SHARED CONTENT STORE      |
                      | │   ├── pack/    (Semua blob/tree/commit)   |
                      | │   └── [0-9a-f][0-9a-f]/                   |
                      | ├── refs/     <-- SHARED POINTER BRANCHES   |
                      | └── worktrees/                              |
                      |     └── hotfix-patch/                       |
                      |         ├── HEAD (Point to vuln-101)        |
                      |         ├── index (Local stage buffer)      |
                      |         └── logs/                           |
                      +---------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### A. Simple Example: Merekonstruksi Commit Murni Melalui Plumbing Commands
Langkah berikut membuat object Git valid dan mencatat commit ke cabang tanpa menyentuh perintah `git add` atau `git commit`.

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Buat direktori pengujian dan inisialisasi git murni
rm -rf test-plumbing && mkdir test-plumbing && cd test-plumbing
git init

# 2. Tulis berkas langsung ke Object Database sebagai Blob
BLOB_HASH=$(echo "Enterprise Application Configuration v1.0" | git hash-object -w --stdin)
echo "Blob Generated: ${BLOB_HASH}"

# 3. Masukkan Blob ke Staging Index secara terprogram
# Mode 100644 menandakan regular non-executable file
git update-index --add --cacheinfo 100644 "${BLOB_HASH}" "config/runtime.cfg"

# 4. Tulis pohon struktur direktori (Tree Object) dari staging index
TREE_HASH=$(git write-tree)
echo "Root Tree Generated: ${TREE_HASH}"

# 5. Buat Commit Object yang mereferensikan Root Tree tersebut
COMMIT_HASH=$(echo "feat(arch): inject runtime configuration via plumbing" | git commit-tree "${TREE_HASH}")
echo "Commit Generated: ${COMMIT_HASH}"

# 6. Arahkan pointer cabang main ke commit yang baru dibuat secara atomik
git update-ref refs/heads/main "${COMMIT_HASH}"

# 7. Verifikasi integritas status via porcelain command
git log -p -1
```

### B. Practical Example: Enterprise Pre-Receive Hook (Policy Enforcement)
Simpan berkas berikut pada server Git remote host (GitHub Enterprise Server / GitLab Omnibus / Bare Repo) di path `.git/hooks/pre-receive`. Skrip memvalidasi:
1. Format commit message harus mematuhi Conventional Commits.
2. Ukuran file yang di-push tidak boleh melebihi batas (5MB) untuk mencegah polusi disk.
3. Larangan commit kredensial file sensitif (`.pem`, `.env`, `id_rsa`).

```python
#!/usr/bin/env python3
import sys
import subprocess
import re

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
CONVENTIONAL_COMMIT_REGEX = r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-z0-9-_.]+\))?: .{1,100}$"
FORBIDDEN_FILE_PATTERNS = [r"\.pem$", r"\.env$", r"^id_rsa$", r"\.key$"]

def run_cmd(cmd):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    return result.stdout.strip()

def validate_commit_message(commit_hash):
    msg = run_cmd(["git", "log", "-1", "--format=%s", commit_hash])
    if not re.match(CONVENTIONAL_COMMIT_REGEX, msg):
        print(f"[REJECTED] Commit {commit_hash[:8]} message violates Conventional Commits standard.")
        print(f"Format: <type>(<scope>): <subject>. Current: '{msg}'")
        return False
    return True

def validate_tree_objects(old_rev, new_rev):
    # Dapatkan daftar objek yang berubah di antara dua revision
    null_rev = "0000000000000000000000000000000000000000"
    rev_range = f"{new_rev}" if old_rev == null_rev else f"{old_rev}..{new_rev}"
    
    diff_tree = run_cmd(["git", "diff-tree", "-r", "--no-commit-id", "--name-only", "--diff-filter=AM", rev_range])
    if not diff_tree:
        return True

    files = diff_tree.split("\n")
    for file_path in files:
        if not file_path:
            continue
        # Cek blacklist ekstensi sensitif
        for pattern in FORBIDDEN_FILE_PATTERNS:
            if re.search(pattern, file_path, re.IGNORECASE):
                print(f"[REJECTED] Policy violation: File sensitif terdeteksi '{file_path}'.")
                return False
        
        # Validasi ukuran blob menggunakan ls-tree
        try:
            blob_info = run_cmd(["git", "ls-tree", "-r", "--long", new_rev, file_path])
            if blob_info:
                # Kolom 4 berisi ukuran file (size in bytes)
                size_str = blob_info.split()[3]
                if size_str != "-" and int(size_str) > MAX_FILE_SIZE_BYTES:
                    print(f"[REJECTED] File '{file_path}' terlalu besar ({int(size_str)/(1024*1024):.2f}MB). Batas: 5MB.")
                    return False
        except subprocess.CalledProcessError:
            pass

    return True

def main():
    has_errors = False
    # Pre-receive hook membaca dari stdin: <old-value> <new-value> <ref-name>
    for line in sys.stdin:
        old_rev, new_rev, ref_name = line.strip().split()
        
        # Abaikan branch deletion
        if new_rev == "0000000000000000000000000000000000000000":
            continue

        null_rev = "0000000000000000000000000000000000000000"
        rev_range = f"{new_rev}" if old_rev == null_rev else f"{old_rev}..{new_rev}"
        
        commits = run_cmd(["git", "rev-list", rev_range]).split()
        for commit in commits:
            if not validate_commit_message(commit):
                has_errors = True
                break

        if not validate_tree_objects(old_rev, new_rev):
            has_errors = True

    if has_errors:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Monorepo "OmniFin" Melambat Akibat Pertumbuhan Cepat
- **Kondisi Perusahaan**: PT Omni Finansial Indonesia memiliki arsitektur Monorepo dengan ukuran 48 GB, memiliki 1.200 microservices, 2.500 developer aktif, dan riwayat commit sebanyak 850.000 entri.
- **Masalah**:
  1. Waktu eksekusi `git clone` memakan waktu 45 menit pada koneksi kantor dan 120 menit pada runner CI/CD.
  2. Operasi harian `git status` membutuhkan latensi 12-18 detik di workstation macOS/Linux developer lokal.
  3. Insiden: Seorang engineer junior tidak sengaja melakukan commit file dump database `.sql` sebesar 1.8 GB ke cabang rilis 6 bulan yang lalu, melipatgandakan ukuran Packfile dan memperlambat sinkronisasi mirror remote.

### Solusi Arsitektur
Engineering Team mengeksekusi 3 fase perbaikan:

#### 1. Pembersihan Objek Masif Historis (`git-filter-repo`)
Menghapus seluruh file dump SQL secara global dari seluruh riwayat DAG tanpa merusak relasi signed-tag yang esensial.
```bash
# Menghapus berkas dari seluruh commit history secara deterministik
git-filter-repo --invert-paths --path-match "production_dump.sql" --force

# Menghapus reflog lokal dan mengeksekusi aggressive garbage collection
git reflog expire --expire=now --all
git -c gc.reflogExpire=0 -c gc.reflogExpireUnreachable=0 \
  -c gc.rerereresolved=0 -c gc.rerereunresolved=0 \
  -c gc.pruneExpire=now gc --prune=now --aggressive
```

#### 2. Implementasi Blobless Clone & Sparse Cone di Pipeline CI/CD
Semua pipeline Jenkins & GitHub Actions diubah konfigurasinya:
```bash
# Clone hanya pohon git tanpa blob payload historis (menghemat 90% waktu download)
git clone --filter=blob:none --no-checkout https://git.internal.omnifin.id/core/monorepo.git app
cd app
git sparse-checkout set --cone services/settlement-service libs/shared-kernel
git checkout $CI_COMMIT_SHA
```

#### 3. Optimasi Workstation Developer via File System Monitor (FSMonitor) & MIDX
Mengonfigurasi FSMonitor menggunakan engine IPC native OS (FSEvents di macOS / inotify di Linux) dan mengaktifkan kompilasi commit-graph otomatis:
```bash
git config --global core.fsmonitor true
git config --global core.untrackedcache true
git config --global fetch.writeCommitGraph true
git config --global pack.useBitmapBoundaryTraversal true
```

### Hasil Metrik
- Waktu provisioning runner CI/CD turun dari **45 menit** menjadi **18 detik** (reduksi 99.3%).
- Eksekusi `git status` lokal turun dari **14 detik** menjadi **85 milidetik**.
- Ukuran disk repositori di server berkurang dari **48 GB** menjadi **8.2 GB**.

---

## 9. Trade-offs & Analysis

```
                              Optimization Spectrum
          ┌─────────────────────────────────────────────────────────────┐
          │                                                             │
Full Clone Baseline                                             Treeless Clone
(Highest Reliability,                                           (Lowest Network Footprint,
 Zero Network Overhead)                                         Extreme Server Request Churn)
                  ▲                             ▲
                  │                             │
                  └───────────────┬─────────────┘
                                  │
                          Blobless Clone
                    (SWEET SPOT UNTUK ENTERPRISE)
```

| Pendekatan / Fitur | Pros | Cons | Biaya & Pertimbangan Skalabilitas |
| :--- | :--- | :--- | :--- |
| **Full Clone (Standar)** | - Akses offline lengkap.<br>- Operasi internal (blame/bisect) 100% lokal tanpa roundtrip jaringan. | - Waktu clone tinggi.<br>- Boros storage.<br>- Tekanan I/O tinggi pada workstation lokal. | Tidak dapat bertahan (*unsustainable*) pada ukuran monorepo > 15 GB. |
| **Blobless Clone (`--filter=blob:none`)** | - Download awal sangat cepat.<br>- Pohon direktori riwayat commit tetap utuh.<br>- Single-file checkout instan. | - Traversi `git log -p` atau `git blame` lama akan memicu lazy-fetch HTTP blob dari remote server. | **Rekomendasi Utama Enterprise**. Menurunkan network transfer saat clone hingga ~90% dengan overhead server marginal. |
| **Treeless Clone (`--filter=tree:0`)** | - Ukuran data awal paling minimal (hanya commit array). | - Setiap operasi checkout commit baru memicu RPC request untuk fetch tree & blob. | Biaya komputasi remote server melonjak drastis jika banyak developer berpindah-pindah cabang secara simultan. |
| **Git Submodules** | - Isolasi repositori ketat.<br>- Hak akses (RBAC) granular per komponen repositori terpisah. | - Sering menyebabkan *detached HEAD*.<br>- Kompleksitas update pointer commit SHA.<br>- Rentan merge error saat rekonsiliasi state. | Biaya kognitif tim tinggi; risiko kegagalan build tinggi jika pipeline tidak dirancang defensif. |
| **Aggressive Repack (`git gc --aggressive`)** | - Kompresi delta maksimal.<br>- Ukuran repositori di storage remote turun signifikan. | - Sangat membebani CPU server saat runtime kompresi.<br>- Waktu pemrosesan membutuhkan berjam-jam pada repo besar. | Jalankan hanya secara berkala (*scheduled off-peak cron*) di server hosting Git, bukan di workstation harian. |

---

## 10. Common Mistakes & Troubleshooting

### A. Insiden 1: Menghapus Cabang Produksi yang Belum Ter-merge (Dangling Commit)
*Gejala*: Developer mengeksekusi `git branch -D release/2.4.0` tanpa sengaja dan mengira commit hilang permanen dari database.
*Solusi*: Traversi reflog atau dangling commits via plumbing tools:
```bash
# 1. Cari commit terakhir yang hilang di database lokal
git reflog show release/2.4.0
# Jika reflog cabang telah terhapus, gunakan plumbing fsck:
git fsck --lost-found | grep commit

# 2. Periksa detail isi hash target yang dicurigai
git show <FOUND_HASH>

# 3. Pulihkan cabang secara instan
git branch release/2.4.0 <FOUND_HASH>
```

### B. Insiden 2: Repository Bloating Akibat Objek Biner yang Terlanjur Terhapus di HEAD
*Gejala*: Berkas besar `build/app.bin` (500MB) telah dihapus dengan `git rm`, namun ukuran folder `.git/` tidak berkurang sama sekali saat di-push/fetch.
*Akar Masalah*: Berkas masih tersimpan sebagai immutable blob di riwayat commit masa lalu.
*Solusi*: Bersihkan referensi, pack ulang secara agresif:
```bash
# 1. Gunakan git-filter-repo untuk membersihkan commit history
git-filter-repo --invert-paths --path "build/app.bin" --force

# 2. Paksa pembersihan reference log
git reflog expire --expire=now --all
git prune --expire=now

# 3. Tulis ulang packfiles dengan membuang objek unreferenced
git repack -a -d -f --depth=250 --window=250
```

### C. Insiden 3: Stale Worktree Lock & Metadata Inconsistency
*Gejala*: Terjadi error `fatal: 'worktree' already exists` saat mencoba membuat worktree pada path yang sebelumnya dihapus paksa via perintah `rm -rf`.
*Akar Masalah*: Metadata internal di `.git/worktrees/<name>` masih tertinggal karena direktori kerja tidak dihapus menggunakan antarmuka resmi porcelain `git worktree remove`.
*Solusi*: Bersihkan referensi administratif worktree yang rusak:
```bash
# Identifikasi worktree yang berstatus prunable
git worktree list

# Bersihkan metadata administratif
git worktree prune -v
```

---

## 11. Best Practices & Production Checklist

### Infrastructure & Server-Side Tuning
- [ ] Aktifkan `protocol.version = 2` pada seluruh level server dan proxy edge.
- [ ] Atur scheduled cron job untuk eksekusi berkala:
  - `git multi-pack-index write`
  - `git commit-graph write --reachable --changed-paths`
  - `git pack-refs --all --prune`
- [ ] Pastikan kapasitas core CPU dan RAM server dialokasikan minimal 2x dari ukuran repositori tunggal terbesar saat proses `git repack` berlangsung.

### Developer Environment Setup (Workstation Tuning)
- [ ] Konfigurasikan File System Monitor native untuk menghentikan stat crawling:
  ```bash
  git config --global core.fsmonitor true
  git config --global core.untrackedcache true
  ```
- [ ] Gunakan fitur `git worktree` alih-alih melakukan clone sekunder secara terpisah untuk pengujian multi-cabang:
  ```bash
  git config --global worktree.guessRemote true
  ```
- [ ] Kunci konfigurasi push agar selalu defensif:
  ```bash
  git config --global push.default simple
  git config --global push.followTags false
  ```

### Large Repositories & CI/CD Pipelines
- [ ] Terapkan konfigurasi clone minimalis di CI:
  ```bash
  git clone --filter=blob:none --no-tags --depth=1 --single-branch -b <branch> <url>
  ```
- [ ] Larang keras file biner (dokumen binary, installer, bundle node_modules, database snapshot) masuk ke repositori Git. Gunakan storage LFS terisolasi atau Artifact Registry (Artifactory, Nexus, S3).
- [ ] Pasang server-side hook (`pre-receive`) untuk menolak commit yang mengandung kredensial sensitif atau file yang melebihi batas ukuran (maks. 5MB-10MB).

---

## 12. Hands-on Practice

Eksekusi seluruh urutan instruksi teknis ini di terminal workstation Anda. Simpan dan jalankan script ini di dalam direktori `hands-on/m02/`.

### Tahap 1: Setup Workspace & Low-Level Object Dissection
```bash
# Navigasi ke target direktori hands-on
mkdir -p hands-on/m02 && cd hands-on/m02

# Buat repositori isolasi
rm -rf enterprise-deepdive && mkdir enterprise-deepdive && cd enterprise-deepdive
git init

# Buat sebuah blob secara manual dan bedah isinya
echo "System Core Architecture Layer" > file.txt
BLOB_HASH=$(git hash-object -w file.txt)
echo "Generated Blob SHA: ${BLOB_HASH}"

# Periksa tipe dan ukuran objek langsung dari database Git (.git/objects/)
git cat-file -t "${BLOB_HASH}"
git cat-file -s "${BLOB_HASH}"
git cat-file -p "${BLOB_HASH}"

# Lihat bagaimana Git menyimpan payload di filesystem (zlib decompress)
OBJECT_SUBDIR=$(echo "${BLOB_HASH}" | cut -c 1-2)
OBJECT_FILE=$(echo "${BLOB_HASH}" | cut -c 3-40)
python3 -c "import zlib; print(zlib.decompress(open('.git/objects/${OBJECT_SUBDIR}/${OBJECT_FILE}', 'rb').read()).decode('latin1'))"
```

### Tahap 2: Implementasi Git Worktrees Terisolasi
```bash
# Commit berkas awal ke main branch
git add file.txt
git commit -m "feat(kernel): initial architecture baseline"

# Skenario: Bug kritikal muncul di production saat Anda sedang bersiap kerja.
# Buat branch hotfix menggunakan Worktree independen di luar direktori kerja saat ini
git worktree add ../hotfix-isolation -b hotfix/CRIT-9901

# Verifikasi struktur direktori worktree
git worktree list
ls -la ../hotfix-isolation

# Kerjakan perbaikan di worktree baru tersebut
cd ../hotfix-isolation
echo "Hotfix Patch Security Injected" >> file.txt
git commit -am "fix(security): resolve vulnerability zero-day"

# Kembali ke repositori utama, verifikasi status commit
cd ../enterprise-deepdive
git log --oneline --graph --all

# Bersihkan worktree setelah branch selesai
git worktree remove ../hotfix-isolation
git branch -D hotfix/CRIT-9901
```

### Tahap 3: Simulasi Sparse Checkout Cone-Mode
```bash
# Buat struktur monorepo tiruan di repo utama
mkdir -p apps/web apps/mobile libs/payments libs/auth
echo "package web" > apps/web/main.go
echo "package mobile" > apps/mobile/main.go
echo "package payments" > libs/payments/pay.go
echo "package auth" > libs/auth/auth.go

git add apps libs
git commit -m "feat(repo): build enterprise monorepo directory layout"

# Aktifkan sparse checkout cone mode
git sparse-checkout init --cone

# Set proyeksi direktori kerja HANYA untuk apps/web dan libs/payments
git sparse-checkout set apps/web libs/payments

# Verifikasi struktur direktori yang tersisa di filesystem Anda
ls -R
# Buktikan bahwa apps/mobile dan libs/auth hilang dari disk lokal,
# tetapi tetap eksis di dalam ODB (Object DataBase)!
git ls-tree HEAD apps/
```

### Tahap 4: Optimasi Repack, Commit-Graph, & MIDX
```bash
# Hasilkan ratusan commit dummy secara terprogram untuk menguji kompilasi commit-graph
for i in {1..50}; do
  echo "metric update $i" >> apps/web/main.go
  git commit -am "chore(profiler): iteration $i" > /dev/null
done

# Pack loose objects dan generate Multi-Pack-Index (MIDX)
git repack -d
git multi-pack-index write

# Kompilasi commit-graph DAG biner
git commit-graph write --reachable --changed-paths

# Verifikasi keberadaan file commit-graph dan MIDX biner
ls -la .git/objects/info/commit-graph
ls -la .git/objects/pack/multi-pack-index
```

---

## 13. Exercises

### Level Easy
1. Dari direktori repositori pengujian, gunakan kombinasi plumbing commands `git rev-parse`, `git cat-file`, dan `git ls-tree` untuk menampilkan seluruh hash tree dan blob dari commit HEAD tanpa mengeksekusi `git show` atau `git log`.
   - *Expected Output*: Terlihat daftar tipe objek, hash biner, dan path yang sesuai secara hierarkis.

### Level Medium
1. Simulasikan insiden rusaknya pointer cabang lokal (`refs/heads/main` terhapus atau bernilai byte acak). Kembalikan pointer cabang `main` ke posisi commit terakhir secara presisi hanya menggunakan data dari `.git/logs/refs/heads/main` dan utilitas `git update-ref`.
   - *Expected Output*: Cabang `main` kembali berfungsi normal pada posisi SHA yang tepat dan diverifikasi melalui `git status`.

### Level Hard
1. Buat skrip Bash otomatis (`audit-pack.sh`) yang:
   - Memindai seluruh packfile yang ada di `.git/objects/pack/`.
   - Menggunakan command `git verify-pack -v` untuk mengekstraksi 5 blob berukuran terbesar (terkompresi dan uncompressed) di seluruh riwayat repositori.
   - Mengonversi hash blob tersebut kembali ke nama path file aslinya di commit tree terkait.
   - *Expected Output*: Tabel output di terminal yang menampilkan: `BLOB SHA | SIZE IN BYTES | COMMIT PATH`.

---

## 14. Challenge: Production Disaster Recovery & Monorepo Restructuring

### Skenario Lapangan:
Anda diangkat sebagai Principal Systems Engineer di sebuah unicorn FinTech. Terjadi krisis arsitektural ganda:
1. **Insiden Keamanan**: Seorang mantan engineer mengunggah private key produksi AWS dan TLS certificate (`.pfx`) ke branch fitur 2 tahun lalu yang telah di-merge ke branch `main`. File tersebut berada di dalam path `deploy/credentials/prod_master.pfx` dan berukuran 120MB (binary). Repositori ini telah memiliki lebih dari 20.000 commit turunan di atasnya.
2. **Krisis CI**: Waktu tunggu CI/CD melonjak menjadi 1 jam per pull request karena runner mengunduh total 15GB data git packfile.
3. **Persyaratan**:
   - Berkas `prod_master.pfx` dan seluruh variasi binary dump di folder `deploy/credentials/` harus dibersihkan secara total dan permanen dari seluruh DAG, seluruh commit, seluruh tags, dan seluruh branches.
   - Semua *GPG Signed Commits* yang tidak tersentuh perubahan berkas tersebut sedapat mungkin dipertahankan relasi pohon silsilahnya (*ancestry graph* tidak boleh terpecah).
   - Seluruh developer remote tidak boleh melakukan clone ulang secara penuh; Anda harus mempublikasikan instruksi *force rebase/synchronization* yang aman untuk upstream branch.
   - Ukuran packfile repositori di remote origin setelah proses pembersihan harus turun minimal 80%.

### Tugas Anda:
Rancang dan uji coba seluruh script automasi pembersihan history, regenerasi commit-graph, rebuilding packfile, dan tata cara mitigasi workstation developer tanpa menyebabkan data corruption.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)
1. Manakah tipe objek Git yang bertugas memetakan relasi direktori, atribut hak akses berkas POSIX, dan mengelompokkan hash antar berkas?
   - A. Commit Object
   - B. Blob Object
   - C. Tree Object
   - D. Tag Object

2. Perintah Git plumbing manakah yang digunakan untuk mengalkulasi hash SHA dan secara opsional menuliskan konten berkas mentah langsung ke database `.git/objects/`?
   - A. `git write-tree`
   - B. `git hash-object`
   - C. `git update-ref`
   - D. `git cat-file`

3. Direktori internal manakah di dalam `.git` yang menyimpan log historis rotasi pointer cabang lokal dan HEAD, yang sangat esensial untuk menyelamatkan commit yang terhapus?
   - A. `.git/refs/`
   - B. `.git/info/`
   - C. `.git/objects/`
   - D. `.git/logs/`

4. Konsep kompresi apakah yang digunakan oleh Packfile Git untuk menyimpan perubahan antar versi berkas serupa tanpa menyimpan berkas penuh secara berulang-ulang?
   - A. Delta Compression
   - B. Lempel-Ziv-Oberhumer (LZO)
   - C. Huffman-only Encoding
   - D. Gzip Multi-stream

5. Parameter apakah yang wajib ditambahkan pada perintah `git clone` untuk mengeksekusi mekanisme "Blobless Clone"?
   - A. `--depth=1`
   - B. `--filter=blob:none`
   - C. `--sparse`
   - D. `--no-checkout`

---

### Bagian 2: Intermediate (Pilihan Ganda)
6. Mengapa mekanisme `commit-graph` (`.git/objects/info/commit-graph`) meningkatkan performa traversi riwayat Git secara radikal pada repositori berskala besar?
   - A. Karena mengubah format penyimpanan zlib commit menjadi struktur biner tabular linear yang memuat offset generasi dan representasi relasi parent langsung.
   - B. Karena menghapus seluruh commit riwayat lama dan hanya menyisakan commit terbaru.
   - C. Karena mengenkripsi hash commit menggunakan algoritma hashing yang lebih pendek.
   - D. Karena menyimpan commit langsung di RAM kernel space.

7. Perbedaan mendasar antara fitur `git worktree` dan membuka branch lain di folder terpisah melalui `git clone` baru adalah:
   - A. `git worktree` membuat duplikasi penuh folder `.git/` sehingga memakan storage dua kali lipat.
   - B. `git worktree` berbagi *Object Database (ODB)* dan referensi konfigurasi yang sama dari repositori utama tanpa duplikasi berkas internal `.git`.
   - C. `git worktree` tidak mengizinkan kompilasi kode secara paralel.
   - D. `git worktree` hanya dapat berjalan pada sistem operasi Windows.

8. Apa implikasi struktural jika Anda mengaktifkan Sparse Checkout dengan mode non-cone (`--no-cone`) dibandingkan dengan mode cone (`--cone`)?
   - A. Mode non-cone membaca pattern berbasis regex penuh untuk setiap berkas, menyebabkan degradasi performa $O(N)$ terhadap total berkas repositori.
   - B. Mode non-cone jauh lebih cepat daripada mode cone.
   - C. Mode cone melarang penggunaan sub-direktori.
   - D. Tidak ada perbedaan performa antara kedua mode.

9. Mengapa tool modern seperti `git-filter-repo` sangat direkomendasikan untuk rewriting riwayat repositori daripada perintah warisan `git filter-branch`?
   - A. Karena `git filter-branch` mengeksekusi subshell Unix individual untuk setiap commit, menyebabkan I/O overhead masif dan sering menghasilkan korupsi author time.
   - B. Karena `git filter-branch` hanya bisa memproses branch `main`.
   - C. Karena `git-filter-repo` ditulis menggunakan shell script murni.
   - D. Karena `git filter-branch` mengharuskan koneksi internet aktif.

10. Apa fungsi dari berkas index biner `.idx` yang selalu mendampingi berkas `.pack` di direktori `.git/objects/pack/`?
    - A. Menyimpan pesan commit log.
    - B. Menyediakan tabel pemetaan hash SHA ke binary offset lokasi objek di dalam berkas `.pack` agar pencarian berjalan secara binary search.
    - C. Berisi data kompresi cadangan jika packfile rusak.
    - D. Mengontrol hak akses developer terhadap objek packfile.

---

### Bagian 3: Skenario Kasus Produksi
11. Sebuah pipeline CI/CD pada repositori monorepo 30GB mengalami error `fatal: early EOF` dan `The remote end hung up unexpectedly` saat proses `git fetch` awal. Parameter performa Git client/server manakah yang harus Anda sesuaikan untuk mengatasi limitasi streaming buffer packfile tersebut?
12. Anda menemukan bahwa developer lokal secara berkala mengalami kelambatan eksekusi `git status` (memakan waktu lebih dari 30 detik) pada filesystem SSD NVMe mereka. Repositori memiliki 1.500.000 files. Analisis apa yang menjadi bottleneck dan bagaimana konfigurasi sistem berkas Git tingkat lanjut menyelesaikannya secara permanen?
13. Dalam server Git bare terpusat berbasis Linux, sebuah script `pre-receive` hook menolak proses push karena memvalidasi commit message. Namun, developer mengklaim bahwa commit message yang salah telah diperbaiki melalui `git commit --amend` sebelum di-push. Mengapa server hook masih mendeteksi pesan yang salah tersebut dan bagaimana arsitektur Git menjelaskan status transaksi refs push tersebut?

---

### Kunci Jawaban & Evaluasi

#### Kunci Jawaban Basic:
1. **C** (Tree Object memetakan entri struktur direktori dan mode hak akses).
2. **B** (`git hash-object` membaca stream data dan menghitung hash SHA serta dapat menulis blob dengan flag `-w`).
3. **D** (`.git/logs/` menyimpan catatan pergerakan state referensi melalui reflog).
4. **A** (Delta compression menyimpan selisih data antar revisi yang berdekatan dalam sliding window).
5. **B** (`--filter=blob:none` mengabaikan payload isi berkas dan hanya mengunduh commit serta tree).

#### Kunci Jawaban Intermediate:
6. **A** (Commit-graph memformat data commit ke representasi integer array biner tetap, mengeliminasi dekompresi zlib berulang pada traversi graf).
7. **B** (Worktree berbagi direktori `.git/objects` yang sama, menghemat disk space dan eliminasi network transfer).
8. **A** (Mode non-cone mengevaluasi regex penuh untuk setiap path berkas, membuatnya lambat pada repositori dengan ratusan ribu berkas, sedangkan mode cone mengevaluasi prefix direktori secara instan).
9. **A** (`git filter-branch` sangat lambat karena menjalankan fork process shell pada setiap siklus commit).
10. **B** (Index `.idx` adalah sparse/fan-out index yang memetakan hash ke offset byte packfile).

#### Kunci Jawaban Skenario Kasus Produksi:
11. **Analisis Skenario 1**:
    Kegagalan ini diakibatkan oleh terputusnya koneksi TCP saat server melakukan streaming delta packfile besar atau kehabisan alokasi buffer memory di sisi HTTP/SSH buffer. Solusinya:
    - Naikkan nilai HTTP post buffer: `git config --global http.postBuffer 1048576000` (1GB).
    - Batasi window memory packfile agar tidak memicu Out-Of-Memory (OOM) killer di server: `git config --global pack.windowMemory "256m"`.
    - Di sisi CI/CD, ubah strategi pengambilan data dari full clone menjadi blobless clone (`--filter=blob:none`) dengan kedalaman dangkal (`--depth=1`).

12. **Analisis Skenario 2**:
    Bottleneck terjadi pada syscall sistem berkas `lstat()` yang harus dijalankan pada 1.500.000 berkas oleh proses single-threaded untuk membandingkan timestamp working directory vs staging index. Solusi permanen:
    - Aktifkan Git Built-in File System Monitor daemon: `git config core.fsmonitor true`. Ini membuat Git mendengarkan event perubahan berkas OS (inotify/FSEvents) alih-alih memindai seluruh filesystem.
    - Aktifkan untracked cache: `git config core.untrackedcache true`.
    - Terapkan sparse-checkout cone-mode untuk mengurangi jumlah file fisik di disk yang perlu dipindai.

13. **Analisis Skenario 3**:
    Meskipun developer melakukan amend pada HEAD lokal, jika branch lokal tersebut memiliki cabang parent yang belum sinkron atau push menyertakan range commit ganda (misal akibat merge sebelumnya), `git rev-list <old-rev>..<new-rev>` yang dibaca oleh `pre-receive` hook akan tetap memeriksa *seluruh* commit baru yang belum ada di server. Jika salah satu commit masa lalu yang terbawa masih mengandung pesan yang salah, hook akan menolak seluruh batch push tersebut secara atomik. Developer harus melakukan interactive rebase (`git rebase -i`) untuk memperbaiki commit historis yang salah di sepanjang rantai revision range tersebut.

---

## 16. Summary
- Git adalah Content-Addressable Storage Engine berbasis DAG yang dibangun di atas 4 objek dasar *immutable*: Blob, Tree, Commit, dan Annotated Tag.
- Pustaka internal Git mengandalkan kompresi bertingkat: Zlib untuk *Loose Objects* dan Sliding Window Delta Compression untuk format *Packfiles* (`.pack`/`.idx`).
- Untuk menangani Monorepo skala masif, kombinasi arsitektur **Git Protocol v2**, **Blobless Clone (`--filter=blob:none`)**, **Sparse-Checkout Cone Mode**, dan **Git Worktrees** adalah standar industri enterprise modern untuk memangkas konsumsi storage dan bandwidth jaringan secara signifikan.
- Skalabilitas traversi riwayat repositori bergantung langsung pada optimasi database internal Git melalui pemanfaatan biner **Commit-Graph** dan **Multi-Pack-Index (MIDX)**.
- Remediasi polusi riwayat atau kebocoran kredensial sensitif pada repositori skala besar wajib menggunakan engine performa tinggi berbasis stream parsing seperti **git-filter-repo**, dikombinasikan dengan *aggressive pruning/repacking*, guna menjamin integritas referensi dan kebersihan objek di disk.