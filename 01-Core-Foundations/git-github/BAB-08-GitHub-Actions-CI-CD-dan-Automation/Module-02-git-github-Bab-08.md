# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** arsitektur internal Git (*Content-Addressable Storage*, *Directed Acyclic Graph* (DAG), struktur objek, dan format packfile).
- **Mengonstruksi** state commit secara manual menggunakan *plumbing commands* (`hash-object`, `mktree`, `commit-tree`, `update-ref`) tanpa perantara *porcelain commands*.
- **Merancang dan mengimplementasikan** arsitektur Monorepo berskala *enterprise* menggunakan strategi *Partial Clone*, *Sparse-Checkout* (Cone Mode), dan integrasi *Git Scalar*.
- **Mengevaluasi dan memitigasi** degradasi performa repositori akibat akumulasi artefak biner (*binary bloat*) menggunakan `git-filter-repo` dan teknik *packfile repacking*.
- **Menerapkan** sistem integritas kriptografis tingkat produksi melalui verifikasi commit berbasis GPG/SSH yang terintegrasi dengan validasi CI/CD dan Branch Protection Rule.

---

## 2. Prerequisite

Peserta wajib menguasai:
- Konsep dasar *branching*, *merging*, *rebasing*, dan *cherry-picking*.
- Operasi dasar terminal POSIX (Bash/Zsh) dan manipulasi teks (`awk`, `sed`, `xargs`, `hexdump`/`xxd`).
- Kriptografi dasar: Public-Key Infrastructure (PKI), algoritma *hashing* (SHA-1, SHA-256), serta protokol SSH/GPG.
- Pemahaman siklus hidup Continuous Integration/Continuous Deployment (CI/CD).

---

## 3. Concept & Internal Architecture

Git pada level fundamental bukanlah sistem kontrol versi biasa, melainkan sebuah **Content-Addressable File System** berbasis Directed Acyclic Graph (DAG) dengan antarmuka VCS di atasnya.

```
.git/
├── HEAD                     # Penunjuk branch aktif (ref: refs/heads/main)
├── config                   # Konfigurasi lokal repositori
├── description              # Digunakan oleh Gitweb
├── hooks/                   # Skrip automasi lifecycle client/server
├── index                    # Staging area biner (dircache)
├── info/
│   └── exclude              # File ignore lokal privat
├── objects/                 # Database Objek Imutabel
│   ├── [0-9a-f]{2}/         # 2 karakter pertama SHA (Loose Objects)
│   ├── info/                # Metadata packfile & commit-graph
│   └── pack/                # Packfile (.pack) & Index (.idx) terkompresi
└── refs/                    # Pointer yang dapat dimutasi
    ├── heads/               # Local branch pointers
    ├── tags/                # Tag pointers
    └── remotes/             # Remote tracking branches
```

### 3.1 Empat Objek Fundamental Git

Semua data yang disimpan di dalam direktori `.git/objects/` direpresentasikan dalam salah satu dari empat jenis objek imutabel:

1. **Blob (*Binary Large Object*)**: Hanya menyimpan konten mentah file. Metadata seperti nama file, izin eksekusi (`filemode`), dan path tidak disimpan di dalam blob.
2. **Tree**: Merepresentasikan direktori. Berisi daftar pointer yang memetakan nama file, izin eksekusi UNIX (`100644`, `100755`, `040000` untuk sub-tree), serta hash SHA dari blob atau tree anak terkait.
3. **Commit**: Menyimpan snapshot tree root direktori proyek, pointer hash ke commit induk (*parents*), identitas *author* & *committer* (nama, email, stempel waktu POSIX), serta pesan commit.
4. **Annotated Tag**: Objek independen yang menunjuk langsung ke commit, berisi penandatangan tag, stempel waktu, pesan, dan signature kriptografis (GPG/SSH).

```
[Commit Object] ────> Tree (Root: /)
                        ├── Blob (README.md)
                        └── Tree (src/)
                              ├── Blob (main.go)
                              └── Blob (utils.go)
```

### 3.2 Struktur Kompresi dan Hash Algoritma

Objek mentah Git dibungkus dengan header:
$$\text{Header} = \texttt{"<tipe> <ukuran\_byte>\textbackslash 0"}$$

Isi lengkap (`Header + Konten Mentah`) kemudian di-*hash* menggunakan SHA-1 (160-bit, menghasilkan 40 karakter heksadesimal) atau SHA-256 (pada konfigurasi Git modern dengan ekstensi Object Format baru), lalu dikompresi menggunakan pustaka **zlib (Deflate)**.

### 3.3 Packfile dan Mekanisme Delta Compression

Ketika jumlah *loose objects* membesar, efisiensi I/O sistem berkas akan menurun secara drastis. Git mengatasi masalah ini melalui proses *garbage collection* (`git gc`) yang menggabungkan *loose objects* ke dalam **Packfile** (`.pack`) dengan indeks pencarian terbalik (`.idx`).
- **Sliding Window Delta Compression**: Git memindai objek dengan ukuran dan path nama file yang serupa, mengurutkannya, dan menyimpan objek terbaru secara penuh (*full canonical base*), sementara objek-objek versi lama hanya disimpan sebagai catatan perbedaan (*deltas/diff*).
- Pendekatan ini mengoptimalkan pembacaan riwayat terkini karena checkout versi terbaru tidak memerlukan kalkulasi rekonstruksi delta bertingkat.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional (Porcelain Level) | Pendekatan Enterprise Core (Plumbing & Internal Level) |
| :--- | :--- | :--- |
| **Model Eksekusi** | Bergantung pada perintah abstraksi tingkat tinggi (`git add`, `git commit`, `git checkout`). | Memanipulasi *Index* dan *Object Database* secara terprogram via pipeline plumbing untuk automasi CI/CD performa tinggi. |
| **Skalabilitas Repositori** | *Full Clone* (`git clone <url>`) mengunduh seluruh blob riwayat repositori hingga gigabyte/terabyte. | *Blobless/Treeless Partial Clone* dan *Sparse-Checkout* hanya menarik objek yang dibutuhkan secara *on-demand*. |
| **Integritas Riwayat** | Mengandalkan trust implisit branch tanpa validasi kriptografis. | Penegakan *Cryptographic Commit Signing* terikat identitas IdP dengan verifikasi ketat pada gerbang pre-receive/CI. |
| **Mitigasi Insiden** | `git reset --hard` atau `git revert` secara membabi buta saat terjadi korupsi histori. | Rekonstruksi state via DAG traversal, reflog manual recovery, dan isolasi objek yang terputus (*dangling objects*). |

---

## 5. How (Workflow Detail)

### 5.1 Siklus Hidup Objek Plumbing (Low-Level Commit Creation)
Diagram alur pembuatan commit murni melalui antarmuka *plumbing*:

```
[File Mentah]
     │
     ▼ (git hash-object -w)
[Loose Blob Object di .git/objects/]
     │
     ▼ (git update-index --add --cacheinfo)
[Staging Area (.git/index)]
     │
     ▼ (git write-tree)
[Tree Object di .git/objects/]
     │
     ▼ (git commit-tree <tree-sha> -p <parent-sha>)
[Commit Object di .git/objects/]
     │
     ▼ (git update-ref refs/heads/<branch> <commit-sha>)
[Branch Pointer Terekam]
```

### 5.2 Enterprise Monorepo Optimization Workflow
Untuk repositori skala terabyte (ratusan juta baris kode):

1. **Inisialisasi Sparse & Partial Clone**:
   ```bash
   git clone --filter=blob:none --no-checkout <repo_url>
   ```
2. **Aktivasi Cone-Mode Sparse-Checkout**:
   Membatasi pencarian matching pola path hanya pada level direktori demi menjaga performa evaluasi path.
   ```bash
   git sparse-checkout init --cone
   git sparse-checkout set services/order-service services/common
   git checkout main
   ```
3. **Commit-Graph Acceleration**:
   Mengoptimalkan penelusuran commit graph dengan membuat file cache biner:
   ```bash
   git commit-graph write --reachable --changed-paths
   ```

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem
Bayangkan Git sebagai **Sistem Penitipan Kontainer Global**:
- **Blob**: Muatan murni di dalam kotak, disegel tanpa label nama barang.
- **Tree**: Manifest kargo yang mencatat: "Kotak bernomor seri X bernama `app.py`, kotak bernomor seri Y bernama `database.sql`".
- **Commit**: Bukti tanda terima manifes kargo yang mencatat: "Pemberi kargo: Alice, Penanggung jawab: Bob, Waktu serah terima: Pukul 10.00, Tanda terima sebelumnya: Hash Z".
- **Branch (Ref)**: Sticky note di luar rak kontainer bertuliskan `production`. Anda bisa memindahkan sticky note tersebut ke kontainer mana pun secara instan.

### Diagram Objek DAG

```
 refs/heads/main ──> [Commit: 3a1f9e] (Parent: 1b2c3d)
                          │
                          ▼
                    [Tree: a7b8c9] (Root)
                     ├── [Blob: 4d5e6f] (package.json)
                     └── [Tree: f0e1d2] (src/)
                          └── [Blob: 9a8b7c] (index.ts)
                                  ▲
                                  │ (Shared Identical Content)
 refs/heads/feat ──> [Commit: 8e7d6c] (Parent: 3a1f9e)
                          │
                          ▼
                    [Tree: b2c3d4] (Root)
                     ├── [Blob: 4d5e6f] (package.json)  <-- Tidak diduplikasi
                     └── [Tree: c4d5e6] (src/)
                          ├── [Blob: 9a8b7c] (index.ts)  <-- Tidak diduplikasi
                          └── [Blob: 112233] (auth.ts)   <-- File baru
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Membangun Commit Melalui Plumbing Commands

Berikut adalah demonstrasi deterministik pembuatan commit tanpa perintah `git add` maupun `git commit`.

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Inisialisasi bare repo minimal
rm -rf test-plumbing && mkdir test-plumbing && cd test-plumbing
git init

# 2. Tulis konten langsung ke object database sebagai Blob
BLOB_CONTENT="console.log('Production Kernel Initialized');"
BLOB_SHA=$(echo -n "$BLOB_CONTENT" | git hash-object -w --stdin)
echo "Blob created with SHA: $BLOB_SHA"

# 3. Baca loose object untuk verifikasi header & dekompresi
cat << 'EOF' > inspect_obj.py
import zlib, sys
with open(sys.argv[1], 'rb') as f:
    decompressed = zlib.decompress(f.read())
    print(f"Decoded Object Payload:\n{decompressed}")
EOF
python3 inspect_obj.py .git/objects/${BLOB_SHA:0:2}/${BLOB_SHA:2}

# 4. Tambahkan blob ke index staging area secara manual
# Format: git update-index --add --cacheinfo <mode>,<sha>,<path>
git update-index --add --cacheinfo 100644 "$BLOB_SHA" "src/index.js"

# 5. Tulis isi index ke dalam Tree object
TREE_SHA=$(git write-tree)
echo "Tree created with SHA: $TREE_SHA"

# 6. Buat Commit object yang menunjuk ke Tree tersebut
COMMIT_SHA=$(echo "chore: bootstrap repository via low-level plumbing" | git commit-tree "$TREE_SHA")
echo "Commit created with SHA: $COMMIT_SHA"

# 7. Arahkan branch refs/heads/main ke commit baru
git update-ref refs/heads/main "$COMMIT_SHA"

# 8. Verifikasi integrasi log
git log -1 --stat
```

### 7.2 Practical Example: Custom Merge Driver Berskala Enterprise

Contoh konfigurasi `custom merge driver` untuk menyelesaikan konflik perubahan metadata semantik (*seperti increment build number/versioning file JSON*) secara otomatis.

**Langkah 1: Skrip Custom Merge Resolver (`merge-drivers/json-merge.sh`)**
```bash
#!/usr/bin/env bash
# Git merge driver passing arguments:
# %O = Ancestor temporary file
# %A = Current branch temporary file
# %B = Other branch temporary file
# %P = File path

ANCESTOR=$1
CURRENT=$2
OTHER=$3
FILEPATH=$4

echo "Automated resolution executing for: $FILEPATH"

# Gabungkan JSON keys secara deterministik menggunakan jq (current overrides ancestor, other merged)
if jq -s '.[0] * .[1] * .[2]' "$ANCESTOR" "$CURRENT" "$OTHER" > "${CURRENT}.tmp"; then
    mv "${CURRENT}.tmp" "$CURRENT"
    exit 0
else
    echo "Gagal menggabungkan skema JSON secara deterministik. Mengalihkan ke konflik manual."
    exit 1
fi
```

**Langkah 2: Registrasi Driver ke `.gitattributes` dan `.git/config`**
```bash
# Registrasi atribut untuk file konfigurasi rilis
echo "deploy-manifest.json merge=json-merger" >> .gitattributes

# Daftarkan skrip merger ke konfigurasi Git
git config merge.json-merger.name "Automated JSON Semantic Merger"
git config merge.json-merger.driver "./merge-drivers/json-merge.sh %O %A %B %P"
```

---

## 8. Real World Case Study: Arsitektur Skala Besar (Enterprise Fintech)

### Konteks
Sebuah perbankan multinasional mentransisikan 450 pengembang dari arsitektur multi-repo ke Monorepo tunggal sebesar 85GB. Seiring bertambahnya commit dan artefak uji biner yang tidak sengaja terdorong, pengembang mengalami:
- Operasi `git clone` rata-rata memakan waktu 45-60 menit.
- Perintah harian seperti `git status` membutuhkan waktu >18 detik.
- Runner CI/CD kehabisan memori (*OOMKilled*) saat fase penarikan repositori.

### Akar Masalah Teknis
1. Repositori memiliki 14 juta *loose/packed objects*, dengan akumulasi delta chain yang terlalu panjang.
2. Index memuat 650.000 file sekaligus ke memory footprint lokal (`.git/index` > 300MB).
3. Artefak `*.jar`, `*.tar.gz`, dan dataset mock JSON committed directly ke branch historis.

### Solusi Arsitektural

```
                 [Central Git Enterprise Engine]
                                │
          ┌─────────────────────┴─────────────────────┐
          ▼                                           ▼
[Developer Machine]                         [CI/CD Worker Cluster]
  ├── Git Scalar Core Engine                  ├── Blobless Clone (--filter=blob:none)
  ├── Sparse-Checkout (Cone: 1 Service)       ├── Shallow Depth (--depth=1)
  └── FSMonitor Background Daemon             └── Shared Reference Object Cache
```

1. **Pemurnian Objek Historis (Server-side Maintenance Window)**:
   ```bash
   # Ekstraksi dan eliminasi artefak biner di atas 5MB
   git-filter-repo --strip-blobs-bigger-than 5M --analyze
   git-filter-repo --strip-blobs-bigger-than 5M --force

   # Agresif repacking dengan perpanjangan window delta
   git reflog expire --expire=now --all
   git repack -a -d -f --depth=250 --window=250
   git prune --expire=now
   ```

2. **Standardisasi Mesin Klien melalui Git Scalar**:
   ```bash
   # Scalar mengaktifkan sparse-checkout, fsmonitor, dan commit-graph otomatis
   scalar register
   scalar reconfigure --all
   ```

3. **Optimasi Waktu Checkout CI/CD**:
   ```yaml
   # Pipeline Runner Step
   - name: Fetch Pipeline Context
     run: |
       git clone --filter=blob:none --no-checkout --depth 1 https://github.com/fintech/core-monorepo.git .
       git sparse-checkout init --cone
       git sparse-checkout set services/transaction-engine libs/foundation
       git checkout HEAD
   ```

### Hasil Metrik
- Waktu `git clone` CI/CD turun dari **48 menit** menjadi **11 detik**.
- Waktu eksekusi `git status` lokal terpangkas dari **18,4 detik** menjadi **120 milidetik** berkat `fsmonitor` built-in daemon.
- Ukuran total database `.git/objects` pada remote server menyusut dari **85GB** ke **4.2GB**.

---

## 9. Trade-offs

| Parameter | Monorepo Berskala Besar (Partial/Sparse) | Multi-Repo Standar | Submodule Architecture | Subtree Integration |
| :--- | :--- | :--- | :--- | :--- |
| **Throughput CI/CD** | Rendah tanpa optimasi sparse path; Sangat tinggi jika path-filtering matang. | Sangat tinggi per isolated repo. | Menengah (overhead sinkronisasi pointer submodule). | Menengah (overhead merge tree parsing). |
| **Operasional Klien** | Membutuhkan tools tambahan (`scalar`, FSMonitor) & edukasi dev. | Rendah (standar git clone standar). | Kompleksitas tinggi (*detached HEAD*, recursive updates). | Rendah bagi tim hilir; kompleks bagi upstream merger. |
| **Integritas Versi** | Atomic (satu commit atomic mencakup multi-layanan). | Non-atomic (ketergantungan API terpecah di berbagai commit hash). | Tergantung locking ref submodule; rawan drift. | Terintegrasi langsung dalam riwayat commit parent. |
| **Infrastruktur Storage** | Memerlukan performa disk I/O tinggi pada Git server pusat. | Terdistribusi ke berbagai isolated instances. | Minimal pada parent repo; beban terdistribusi. | Riwayat commit tersalin dobel, memperbesar object database. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Fatal Mistake: Menghapus File Besar Menggunakan Regular `git rm`
- **Gejala**: Pengembang menghapus `dataset.bin` (500MB) dengan `git rm dataset.bin && git commit -m "delete file"`. Ukuran repo `.git` tidak berkurang sama sekali.
- **Root Cause**: Git mempertahankan seluruh file historis di DAG agar versi commit sebelumnya dapat di-checkout kapan saja.
- **Solusi Rekayasa**: Gunakan `git-filter-repo` untuk membersihkan pointer objek dari DAG secara permanen:
  ```bash
  # Install pip install git-filter-repo
  git filter-repo --invert-paths --path dataset.bin --force
  ```

### 10.2 Troubleshooting: Submodule Detached HEAD & Pointer Sync Mismatch
- **Gejala**: Pengembang melakukan perubahan di dalam direktori submodule, tetapi rekan tim melihat referensi commit lama yang tidak ditemukan (*fatal: reference is not a tree*).
- **Audit & Investigasi**:
  ```bash
  # Periksa status pointer SHA yang dicatat oleh parent tree
  git ls-tree HEAD path/to/submodule
  # Masuk ke direktori dan periksa status commit lokal
  cd path/to/submodule && git status
  ```
- **Remediasi**:
  ```bash
  cd path/to/submodule
  git checkout main
  git pull origin main
  cd ../
  git add path/to/submodule
  git commit -m "fix(submodule): synchronize tracking pointer to latest upstream main"
  ```

### 10.3 Troubleshooting: Reflog Traversal Recovery (Menyelamatkan Branch Terhapus)
- **Skenario**: Branch rilis `release/2.4.0` terhapus secara tidak sengaja dengan `git branch -D`.
- **Eksekusi Pemulihan**:
  ```bash
  # 1. Telusuri HEAD history melalui reflog
  git reflog show --date=relative | grep "release/2.4.0"

  # Contoh output:
  # 7a2e4b1 HEAD@{10 minutes ago}: checkout: moving from release/2.4.0 to main

  # 2. Rekonstruksi branch dari commit hash target
  git checkout -b release/2.4.0 7a2e4b1

  # 3. Lakukan integritas fsck untuk memastikan tidak ada loose objek yang hilang
  git fsck --lost-found
  ```

---

## 11. Best Practices (Production Checklist)

- [ ] **GPG/SSH Signature Validation**: Terapkan *Required signed commits* pada Protected Branch di remote.
- [ ] **Git Attributes Optimization**: Pastikan file `.gitattributes` terkonfigurasi dengan normalisasi line-ending (`* text=auto eol=lf`) guna menghindari hash churn lintas OS.
- [ ] **Packfile Churn Reduction**: Terapkan jadwal cron pemeliharaan repo secara berkala:
  ```bash
  git maintenance start
  git maintenance run --task=commit-graph --task=loose-objects --task=pack-files
  ```
- [ ] **Large File Policy Enactment**: Larang file biner > 10MB masuk ke VCS melalui GitHub Push Protection atau pre-receive hook berbasis ukuran blob.
- [ ] **Detached HEAD Prevention**: Konfigurasi Submodule checkout default untuk mendeteksi branch:
  ```bash
  git config --global submodule.recurse true
  ```

---

## 12. Hands-on Practice

Simpan seluruh hasil skrip dan konfigurasi latihan ini ke dalam subdirektori: `hands-on/m02/`

### Skenario: Rekonstruksi Riwayat Terdistribusi dan Investigasi Objek
Lakukan langkah demi langkah berikut di terminal lokal Anda:

#### Langkah 1: Eksplorasi Struktur Objek Manual
```bash
mkdir -p hands-on/m02/deep-dive && cd hands-on/m02/deep-dive
git init

# Buat file dan tambahkan metadata
echo "System Kernel v1.0" > core.txt
git add core.txt
git commit -m "feat: initial core module"

# Ekstrak hash commit terakhir
COMMIT_HASH=$(git rev-parse HEAD)
echo "Commit Hash: $COMMIT_HASH"

# Baca metadata commit objek mentah
git cat-file -p "$COMMIT_HASH"

# Dapatkan Tree SHA dari commit tersebut
TREE_HASH=$(git cat-file -p "$COMMIT_HASH" | awk '/tree/ {print $2}')
echo "Tree Hash: $TREE_HASH"

# Baca isi Tree objek
git cat-file -p "$TREE_HASH"
```

#### Langkah 2: Simulasi dan Investigasi Packfile
```bash
# Hasilkan banyak mutasi commit untuk memicu pembuatan packfile
for i in {1..20}; do
  echo "Patch revision $i" >> core.txt
  git commit -am "chore: incremental update $i"
done

# Repack seluruh loose object ke dalam satu packfile terkompresi
git repack -a -d

# Periksa direktori pack
ls -lh .git/objects/pack/

# Analisis isi index packfile (.idx) menggunakan verify-pack
PACK_IDX=$(ls .git/objects/pack/*.idx | head -n 1)
git verify-pack -v "$PACK_IDX" | head -n 15
```

#### Langkah 3: Implementasi Cone-Mode Sparse-Checkout
```bash
cd ..
git init monorepo-sim && cd monorepo-sim

# Buat struktur direktori multi-service
mkdir -p services/auth-service/src
mkdir -p services/payment-service/src
mkdir -p libs/common/src

echo "Auth API" > services/auth-service/src/app.py
echo "Payment Gateway" > services/payment-service/src/app.py
echo "Shared Utils" > libs/common/src/utils.py

git add .
git commit -m "feat: initial monorepo topology"

# Aktifkan Sparse-Checkout hanya untuk auth-service dan libs/common
git sparse-checkout init --cone
git sparse-checkout set services/auth-service libs/common

# Verifikasi struktur working tree (payment-service harus hilang secara virtual)
ls -la services/
```

---

## 13. Exercise

### Level Easy
Tulis skrip bash yang mencari 5 objek *loose* terbesar di dalam `.git/objects/` dan menampilkan: SHA objek, tipe objek (`blob`, `tree`, dll.), serta ukuran ukurannya yang belum terkompresi.

### Level Medium
Simulasikan skenario di mana referensi branch pointer `refs/heads/main` terhapus secara manual lewat perintah manipulasi file:
```bash
rm .git/refs/heads/main
```
Pulihkan repositori agar `git status` dan `git log` kembali normal, **tanpa** menggunakan perintah `git clone` ulang.

### Level Hard
Buat sebuah program atau skrip bash yang mengimplementasikan **Pre-Receive Hook Engine** (simulasi server-side). Skrip ini harus memvalidasi setiap push baru:
1. Menolak commit apa pun yang tidak memiliki valid SSH/GPG Signature.
2. Memindai commit tree baru dan menolak commit yang menyertakan blob berukuran > 2 MB.
3. Mengembalikan exit code non-zero dan pesan deskriptif kepada pengembang.

---

## 14. Challenge

### Studi Kasus Produksi Kompleks: "The Monolith Split-Brain Emergency"

**Kondisi**:
Sebuah perusahaan logistik skala enterprise mengalami insiden Git fatal saat migrasi automated CI/CD:
1. Skrip rebase yang gagal berjalan secara rekursif pada sistem pipeline tak bertuan, menghasilkan 400 *orphaned commits* yang lepas dari cabang mana pun.
2. Sebuah secret key produksi (`credentials.p12`, 45MB) tanpa sengaja masuk ke 30 cabang aktif yang berbeda sejak 2 bulan yang lalu.
3. File database SQLite internal `.git/index.lock` terkunci terus-menerus karena adanya script reporting yang macet.
4. Tim rilis tidak dapat melakukan `git push` karena Git Remote Engine menolak commit akibat batas ukuran objek (object limit rule: 20MB) terlampaui.

**Misi Anda**:
Susun sebuah prosedur baku (*Runbook*) dan skrip otomasi penanggulangan bencana (*Disaster Recovery Automation Script*) yang dapat dieksekusi secara idempotent oleh tim SRE untuk:
- Mengidentifikasi dan mengekstrak seluruh commit berharga dari dangling reflog tanpa merusak referensi yang sah.
- Membersihkan `credentials.p12` dari **seluruh cabang, tag, dan riwayat commit** secara instan tanpa mengubah timestamp dan author asli dari commit-commit yang bersih.
- Menjamin seluruh tim pengembang dapat melakukan sinkronisasi lokal tanpa harus melakukan *clone* ulang yang membebani jaringan internal.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic

1. Mengapa Git mengabaikan nama file dan hak akses UNIX saat menghitung nilai SHA-1 dari sebuah `blob`?
2. Apa perbedaan fungsional utama antara *loose object* dan *packfile* di dalam `.git/objects/`?
3. Apa peran dari file biner `.git/index` dalam arsitektur three-tier architecture Git?
4. Mengapa eksekusi `git checkout <commit-hash>` menyebabkan kondisi yang disebut *Detached HEAD*?
5. Perintah Git plumbing mana yang berfungsi untuk membaca isi mentah dan tipe dari sebuah objek berdasarkan hash-nya?

### 15.2 Pertanyaan Intermediate

1. Pada struktur packfile, jelaskan bagaimana Git mengimplementasikan teknik *sliding window delta compression* dan mengapa objek versi terbaru justru disimpan sebagai *full canonical* (bukan deltas)?
2. Apa perbedaan operasional mendasar antara `git clone --filter=blob:none` (Blobless) dan `git clone --filter=tree:0` (Treeless) dalam konteks Monorepo berskala besar?
3. Bagaimana mekanisme kerja `git sparse-checkout` dalam mode *cone* dibandingkan mode non-cone tradisional dalam hal kompleksitas algoritma pencocokan pola (*pattern matching*)?
4. Jika dua branch terpisah membuat file dengan konten biner yang persis sama tetapi diletakkan pada nama file dan path folder yang berbeda, berapa banyak objek `blob` baru yang akan dibuat di `.git/objects`? Jelaskan arsitekturnya.
5. Mengapa perintah `git rebase` mengubah seluruh commit hash dari titik cabang yang bersangkutan hingga ujung rantai commit, meskipun kode yang ditulis tidak berbenturan (*conflict-free*)?

### 15.3 Skenario Kasus Produksi

1. **Skenario 1**: Tim DevOps Anda mendapati waktu eksekusi job CI/CD melonjak dari 2 menit menjadi 25 menit. Setelah dianalisis, runner CI/CD mengeksekusi `git fetch origin` yang mentransfer 8GB data setiap build karena ada tim QA yang meletakkan rekaman testing `.mp4` ke dalam branch staging. Bagaimana langkah mitigasi terstruktur di level server Git dan pipeline untuk memblokir kejadian serupa di masa depan tanpa merusak riwayat branch yang sudah terlanjur ditarik?
2. **Skenario 2**: Anda sedang melakukan `git rebase -i` skala besar pada branch strategis. Di tengah proses, laptop mengalami *kernel panic* dan mati mendadak. Saat sistem menyala, repositori berada dalam kondisi korup: `.git/HEAD` hilang dan `git status` menampilkan *fatal: not a git repository*. Uraikan langkah forensics dan pemulihan byte-level repositori tersebut menggunakan DAG traversal.
3. **Skenario 3**: Sebuah institusi finansial mewajibkan bahwa semua commit yang masuk ke branch `production` harus ditandatangani secara kriptografis menggunakan SSH/GPG Key yang terikat dengan Active Directory per karyawan. Bagaimana arsitektur verifikasi ini diterapkan di sisi CI pipeline dan branch protection policy jika Git Server yang digunakan adalah platform self-hosted tanpa fitur integrasi GUI bawaan?

---

## 16. Summary

- **Content-Addressable Storage**: Git menyimpan data murni sebagai graph state imutabel di mana nilai hash SHA menentukan lokasi dan identitas objek (`blob`, `tree`, `commit`, `tag`).
- **Pemisahan Logika Plumbing vs Porcelain**: Memahami perintah level rendah (*plumbing*) memampukan rekayasa automasi repositori tingkat lanjut, pemulihan bencana (*disaster recovery*), dan manipulasi state index berkinerja tinggi.
- **Skalabilitas Enterprise**: Monorepo berskala besar tidak dapat dikelola secara optimal menggunakan konfigurasi Git standar. Penerapan fitur modern seperti *Blobless Clone*, *Sparse-Checkout Cone Mode*, *Commit-Graph*, dan *FSMonitor* merupakan pondasi wajib guna menekan beban IO disk dan latensi jaringan.
- **Integritas Historis**: Keamanan repositori enterprise bertumpu pada validasi identitas kriptografis (*Signed Commits*) serta higienitas DAG dari kontaminasi artefak biner melalui tata kelola siklus hidup git yang disiplin.