# MODUL 02: Deep Dive Git Internals, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengurai dan memanipulasi struktur penyimpanan Git internal (`object store`, `DAG`, `index`, `refs`) menggunakan *plumbing commands*.
- Merancang dan mengoptimalkan performa repositori berskala *enterprise/monorepo* menggunakan fitur *Partial Clone*, *Sparse-Checkout*, dan *Commit-Graph*.
- Mengimplementasikan mekanisme kontrol kualitas kode dan *compliance* berbasis *server-side hooks* dan *custom policy enforcement engine*.
- Menganalisis serta memulihkan korupsi objek Git, kebocoran kredensial historis secara permanen (*purging*), dan konflik rebase multidimensi.
- Mengevaluasi perbandingan arsitektural antara *Monorepo*, *Multi-repo*, *Git Submodules*, dan *Git Subtree* untuk sistem terdistribusi skala besar.

---

## 2. Prerequisite

- Pemahaman mendalam mengenai *Three-Tree Architecture* Git (`Working Directory`, `Staging Area/Index`, `Repository/HEAD`).
- Kemahiran eksekusi Git CLI lanjutan: `interactive rebase`, `merge strategies` (ort, recursive, octopus), `cherry-pick`, `bisect`.
- Pemahaman fundamental tentang algoritma kriptografi *hashing* (SHA-1, SHA-256) dan struktur data *Directed Acyclic Graph* (DAG).
- Pengalaman dasar administrasi Linux shell (Bash/POSIX) dan manipulasi sistem berkas (POSIX filesystem).

---

## 3. Concept & Internal Architecture

### 3.1 Struktur Fisik Direktori `.git`

Git bukan sekadar *version control engine*; Git adalah sistem berkas beralamat konten (*content-addressable filesystem*) dengan antarmuka VCS di atasnya.

```
.git/
├── HEAD                     # Pointer ke branch aktif saat ini (contoh: ref: refs/heads/main)
├── config                   # Konfigurasi repositori spesifik
├── description              # Digunakan oleh Gitweb daemon
├── hooks/                   # Direktori client-side & server-side hook scripts
├── info/                    # Metadata global (contoh: info/exclude)
├── index                    # Biner staging area (cache dari tree status selanjutnya)
├── objects/                 # Database objek berbasis konten (Immutable Object Store)
│   ├── [0-9a-f]{2}/         # 2 karakter hex pertama dari hash objek
│   ├── info/                # Informasi commit-graph dan packfile alternatif
│   └── pack/                # Packfiles biner terkompresi (.pack) dan indeks (.idx)
└── refs/                    # Pointer ke commit objects
    ├── heads/               # Local branches
    ├── remotes/             # Remote-tracking branches
    └── tags/                # Tags (lightweight dan annotated)
```

### 3.2 Git Object Types (The Big Four)

Semua konten dalam Git disimpan di direktori `.git/objects/` sebagai *blob zlib-compressed*. Header objek diformat sebagai:  
`"<type> <size>\0<content>"` lalu di-*hash* menggunakan SHA-1 (atau SHA-256 pada repositori modern).

1. **Blob**: Menyimpan data mentah berkas. Blob tidak menyimpan metadata berkas (nama berkas, permission mode, timestamp).
2. **Tree**: Merepresentasikan direktori. Berisi daftar referensi pointer ke blob (berkas) atau tree lain (subdirektori), lengkap dengan mode file (misal: `100644` untuk normal, `100755` untuk executable) dan nama berkas.
3. **Commit**: Berisi pointer ke root Tree, pointer ke *parent commit* (nol untuk root commit, satu untuk normal commit, dua atau lebih untuk merge commit), metadata author, committer, timestamp, dan commit message.
4. **Annotated Tag**: Objek independen yang menunjuk langsung ke commit (atau blob/tree), berisi author tag, timestamp, PGP signature, dan pesan tag.

### 3.3 Packfiles, Delta Compression, dan MIDX

Seiring pertumbuhan repositori, penyimpanan objek individual (*loose objects*) mengakibatkan inefisiensi I/O dan konsumsi ruang disk yang masif. Git mengatasi hal ini melalui mekanisme **Packing Engine**:
- **Packfile (`.pack`)**: Gabungan ratusan ribu loose objects yang dikompresi menggunakan *Sliding Window Delta Compression*. Objek baru yang merupakan modifikasi berkas lama disimpan hanya sebagai *delta byte-difference*.
- **Pack Index (`.idx`)**: Struktur data pencarian biner (fan-out table + O(log N) binary search) yang memetakan SHA commit/blob ke byte offset presisi di dalam file `.pack`.
- **Multi-Pack-Index (MIDX)**: Indeks lapisan kedua yang menggabungkan beberapa file `.pack` menjadi satu struktur pencarian virtual tunggal untuk mencegah regresi performa lookup saat repositori memiliki ratusan packfiles.

---

## 4. Why & What

| Dimensi | *Porcelain Commands* (Tingkat Tinggi) | *Plumbing Commands* (Tingkat Rendah) |
| :--- | :--- | :--- |
| **Definisi** | Perintah *user-facing* Git (`commit`, `checkout`, `merge`, `rebase`). | Perintah mesin Git yang memanipulasi DAG dan object store secara langsung (`hash-object`, `cat-file`, `write-tree`, `commit-tree`). |
| **Deterministik** | Sering kali bergantung pada status interaktif, konfigurasi global, dan *worktree context*. | 100% deterministik, *scriptable*, berorientasi pipeline Unix (stdout/stdin). |
| **Use Case Enterprise** | Alur kerja harian *developer* di terminal. | Automasi CI/CD tingkat lanjut, audit keamanan, *custom backup tooling*, monorepo indexing. |

### Mengapa Memahami Internals Sangat Krusial?
1. **Pencegahan Data Loss**: Memahami *reflog*, *loose objects*, dan *dangling commits* memungkinkan pemulihan data pada skenario *disaster* (misal: `git reset --hard` salah branch di remote, `rebase` tertimpa).
2. **Skalabilitas Monorepo**: Repositori berukuran puluhan gigabyte akan mengalami degradasi total pada I/O jika engineer tidak mengonfigurasi *sparse-checkout*, *scalar*, dan *pack-redundancy*.
3. **Enterprise Compliance**: Proteksi cabang melalui web UI GitHub/GitLab dapat di-bypass jika transport layer atau webhook internal tidak diverifikasi di level *server-side hooks* (`pre-receive`).

---

## 5. How (Workflow Detail)

### Rekonstruksi Commit Secara Manual Menggunakan Plumbing Engine

Diagram status saat memproduksi commit baru secara manual tanpa menyentuh *porcelain command* (`git add` atau `git commit`):

```
+------------------+      git hash-object -w
| File: app.py     | ---------------------------> [ Blob Object: a1b2c3... ]
+------------------+                                      ^
                                                          |
+------------------+      git update-index --add          |
| Staging Index    | -------------------------------------+
+------------------+
        |
        | git write-tree
        v
+-----------------------------+
| Tree Object: d4e5f6...      | <--- Berisi mode 100644, app.py, sha a1b2c3...
+-----------------------------+
        |
        | git commit-tree -p <parent_sha>
        v
+-----------------------------+
| Commit Object: 9f8e7d...    | <--- Berisi pointer Tree d4e5f6..., Parent, Author
+-----------------------------+
        |
        | git update-ref refs/heads/main
        v
+-----------------------------+
| Branch: refs/heads/main     | <--- Mengarah ke commit 9f8e7d...
+-----------------------------+
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Sistem Pengarsipan Dokumen Legal Notaris
- **Blob**: Kertas isi perjanjian tanpa judul, tanpa map. Hanya teks murni.
- **Tree**: Map folder berlabel yang mencatat daftar dokumen yang dimasukkan (beserta judul map sub-bagian).
- **Commit**: Berita Acara yang disegel notaris, mencatat: *"Pada hari ini, map Tree X telah disahkan oleh Auditor Y, sebagai kelanjutan Berita Acara sebelumnya (Parent Commit Z)"*.
- **Refs (Branch/Tag)**: Stiker *Post-it* yang ditempel di luar lemari arsip. Stiker bertuliskan "PRODUKSI TERAKHIR" (Branch) dapat dipindah-pindah ke Berita Acara manapun seketika.

### Directed Acyclic Graph (DAG) Internal

```
    [Commit C1] <------- [Commit C2] <------- [Commit C3]  (HEAD -> main)
         |                    |                    |
         v                    v                    v
     (Tree T1)            (Tree T2)            (Tree T3)
       /    \               /    \               /    \
 [Blob B1] [Blob B2]   [Blob B1] [Blob B3]   [Blob B4] [Blob B3]
 (app.py)  (utils.py)  (app.py)  (utils.py)  (app.py)  (utils.py)
                       (Unchanged) (Modified) (Modified)(Unchanged)
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Membedah Objek Git Menggunakan Bash

```bash
# Inisialisasi sandbox
mkdir /tmp/git-internals && cd /tmp/git-internals
git init

# 1. Buat file
echo "print('Enterprise Architecture')" > service.py

# 2. Injeksi langsung ke object store via plumbing command
BLOB_HASH=$(git hash-object -w service.py)
echo "Blob Hash: $BLOB_HASH"

# Verifikasi tipe dan konten via plumbing cat-file
git cat-file -t $BLOB_HASH
# Output: blob
git cat-file -p $BLOB_HASH
# Output: print('Enterprise Architecture')

# 3. Masukkan ke index
git update-index --add --cacheinfo 100644 $BLOB_HASH service.py

# 4. Tulis staging index menjadi Tree object
TREE_HASH=$(git write-tree)
echo "Tree Hash: $TREE_HASH"
git cat-file -p $TREE_HASH
# Output: 100644 blob <BLOB_HASH>    service.py

# 5. Buat Commit Object dari Tree
COMMIT_HASH=$(echo "feat: core architecture initialisation" | git commit-tree $TREE_HASH)
echo "Commit Hash: $COMMIT_HASH"
git cat-file -p $COMMIT_HASH

# 6. Arahkan pointer branch main ke commit tersebut
git update-ref refs/heads/main $COMMIT_HASH
git log -1
```

### 7.2 Practical Example: Enterprise Git Pre-Receive Hook (Policy Enforcement)

Skrip hook berikut berjalan di sisi Git Server (contoh: GitHub Enterprise Server, GitLab Self-Managed, Bare Server) untuk memvalidasi:
1. Format commit message harus mematuhi spesifikasi *Conventional Commits* dan mencantumkan Ticket ID (misal: `JIRA-1234`).
2. Mencegah berkas terlarang masuk (kredensial `.pem`, `.key`, `.env`).
3. Mencegah eksekusi *force push* pada branch terproteksi (`main`, `production`).

```bash
#!/usr/bin/env bash
# File: hooks/pre-receive
# Server-side hook. STDIN menerima: <old-value> <new-value> <ref-name>

set -e

ZERO_OID="0000000000000000000000000000000000000000"
FORBIDDEN_FILES_REGEX='\.(pem|key|env|pfx|pkcs12)$'
COMMIT_MSG_REGEX='^(feat|fix|chore|docs|refactor|perf|test)(\([a-zA-Z0-9_-]+\))?: [A-Z]+-[0-9]+ .+'

validate_commit() {
    local rev=$1
    local msg
    msg=$(git log -1 --format=%B "$rev")
    
    # 1. Validasi Commit Message Format
    if ! echo "$msg" | grep -Eq "$COMMIT_MSG_REGEX"; then
        echo "[POLICY VIOLATION] Commit $rev ditolak!"
        echo "Format commit message tidak valid: '$msg'"
        echo "Contoh yang benar: 'feat(billing): PROJ-402 Add Stripe webhook idempotency'"
        return 1
    fi

    # 2. Validasi Forbidden Files/Secrets
    local files
    files=$(git diff-tree --no-commit-id --name-only -r "$rev")
    for file in $files; do
        if echo "$file" | grep -Eq "$FORBIDDEN_FILES_REGEX"; then
            echo "[SECURITY VIOLATION] Commit $rev membawa secret file: $file"
            return 1
        fi
    done
    return 0
}

# Baca dari standard input (piped oleh Git binary)
while read -r old_rev new_rev ref_name; do
    # Proteksi delete branch produksi
    if [ "$new_rev" = "$ZERO_OID" ]; then
        if [[ "$ref_name" =~ refs/heads/(main|production|release-.*) ]]; then
            echo "[CRITICAL VIOLATION] Branch $ref_name dilindungi dan tidak boleh dihapus!"
            exit 1
        fi
        continue
    fi

    # Proteksi non-fast-forward push (force push)
    if [ "$old_rev" != "$ZERO_OID" ]; then
        if git merge-base --is-ancestor "$old_rev" "$new_rev" 2>/dev/null; then
            : # Fast-forward, aman
        else
            if [[ "$ref_name" =~ refs/heads/(main|production) ]]; then
                echo "[SECURITY VIOLATION] Force-push pada $ref_name dilarang keras!"
                exit 1
            fi
        fi
    fi

    # Dapatkan daftar commit baru yang di-push
    if [ "$old_rev" = "$ZERO_OID" ]; then
        # Branch baru
        commits=$(git rev-list "$new_rev" --not --branches)
    else
        # Range commit baru
        commits=$(git rev-list "$old_rev..$new_rev")
    fi

    for commit in $commits; do
        if ! validate_commit "$commit"; then
            exit 1
        fi
    done
done

exit 0
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario Kasus: Monorepo Financial Enterprise (50GB+ Repository, 800+ Engineers)

#### Masalah Utama
Perusahaan fintech global memiliki monorepo berumur 7 tahun. Total ukuran direktori `.git` mencapai 68 GB. 
Gejala kegagalan sistem:
- Eksekusi `git clone` memakan waktu 45 menit, kerap terputus karena TCP timeout.
- Perintah harian seperti `git status` membutuhkan waktu 18 detik di workstation developer.
- Resource disk pada runner CI/CD habis (*out of disk space*), menyebabkan *deployment pipeline bottleneck*.

#### Analisis Root-Cause
1. Repositori menimbun ribuan asset biner historis (mock data JSON ukuran raksasa, build artifacts `.tar.gz`, fixture binary).
2. Algoritma traversi Git memindai seluruh *file tree* (1,2 juta berkas) setiap kali `git status` dipanggil.
3. Objek packfile terfragmentasi tanpa adanya konsolidasi *multi-pack index*.

#### Solusi Arsitektur Produksi

```
[ Developer Terminal ]
       |
       | 1. Blobless Clone: git clone --filter=blob:none --no-checkout <repo_url>
       v
[ Local .git Metadata Only (Ukuran: ~900 MB, Durasi: 40s) ]
       |
       | 2. Sparse-Checkout Konfigurasi (Hanya sub-tree yang relevan)
       |    git sparse-checkout set services/core-banking apps/shared-libs
       v
[ Working Directory: Hanya 15.000 file aktif ]
       |
       | 3. Optimasi Indexing Engine
       |    git config core.untrackedCache true
       |    git config core.fsmonitor true
       |    git config core.commitGraph true
       v
Hasil: `git status` latency turun dari 18s -> 120ms
```

1. **Blob-less Partial Clone**: Hanya mengunduh *commits* dan *trees*. Data *blob* (isi file) diunduh secara *on-demand* (lazy loading) saat checkout terjadi.
2. **Sparse-Checkout Core Cone Mode**: Membatasi populasi sistem berkas lokal hanya ke subdirektori fungsional divisi developer terkait.
3. **FSMonitor Daemon**: Mengintegrasikan `fsmonitor` dengan subsistem OS (Watchman/FSEvents) sehingga Git tidak perlu melakukan `stat()` pada seluruh berkas untuk mendeteksi perubahan.
4. **Git Maintenance & Commit-Graph Optimization**: Mengaktifkan background scheduler untuk kompilasi berkas `commit-graph` dan `midx` berkala.

---

## 9. Trade-offs

| Pendekatan / Fitur | Keuntungan | Konsekuensi & Trade-off |
| :--- | :--- | :--- |
| **Blobless Clone (`--filter=blob:none`)** | Menghemat storage hingga 90%, transfer git clone menjadi instan. | Operasi seperti `git log -p` (melihat diff riwayat lama) atau `git checkout` branch yang jauh akan memicu dependensi *network request* mendadak. |
| **Monorepo (Single Large Repo)** | Integrasi dependensi atomik, *single source of truth*, memudahkan refactoring cross-team. | Membutuhkan *advanced tooling* (Bazel/Turborepo, Scalar, Sparse-checkout). Beban server VCS sangat tinggi. |
| **Multi-Repo (Polyrepo)** | Akses kontrol granular, repositori kecil dan cepat, lifecycle CI/CD independen. | *Dependency hell* antar *versioned packages*, sulit melakukan audit atomik dan koordinasi rilis lintas tim. |
| **Git Submodules** | Memisahkan komponen kode di level pointer commit; menjaga batas repositori tetap ketat. | *UX friction* tinggi bagi developer pemula (risiko *detached HEAD*, state submodule out-of-sync jika lupa `--recurse-submodules`). |
| **Git Subtree** | Riwayat eksternal digabung ke repositori utama tanpa sub-repo tracking rumit bagi kontributor. | Memperbesar ukuran repositori utama, proses pushing *upstream* balik ke repo asal membutuhkan sintaks rumit. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Kesalahan Fatal: Hard Reset yang Tidak Disengaja (`git reset --hard`)
**Penyebab**: Developer mengeksekusi `git reset --hard HEAD~5` untuk membuang perubahan lokal, namun menyadari ada 3 commit krusial yang belum di-push dan ikut terhapus dari log standar.

**Troubleshooting Menggunakan Reflog & Lost-Found**:
```bash
# 1. Periksa histori pointer HEAD lokal
git reflog

# 2. Cari hash commit sebelum reset dilakukan (misal: HEAD@{1})
# Output: 8b3c9a1 HEAD@{1}: commit: feat(auth): add OAuth2 provider

# 3. Pulihkan status branch ke commit tersebut
git reset --hard 8b3c9a1

# Alternatif jika commit tidak ada di reflog (sudah ter-expire):
git fsck --lost-found --unreachable
# Analisis dangling commit:
git cat-file -p <DANGLING_COMMIT_SHA>
# Sambungkan kembali:
git merge <DANGLING_COMMIT_SHA>
```

### 10.2 Masalah: Kredensial AWS Bocor di Commit Historis
**Penyebab**: File `.env` ter-commit 20 commit yang lalu dan sudah di-*push* ke remote origin. Menghapus file di commit terbaru tidak menghapus credential dari history!

**Solusi Produksi (Purging Object Database via `git-filter-repo`)**:
*Catatan: Jangan gunakan `git filter-branch` lama karena lambat dan tidak aman.*

```bash
# 1. Install git-filter-repo (Python based)
pip install git-filter-repo

# 2. Jalankan pembersihan menyeluruh pada seluruh branch dan tag
git filter-repo --invert-paths --path-match .env --force

# 3. Hapus cache reflog lama untuk membebaskan referensi objek
git reflog expire --expire=now --all

# 4. Paksa garbage collector Git membersihkan loose/unreachable objects
git gc --prune=now --aggressive

# 5. Force push yang terkontrol ke remote (membutuhkan koordinasi tim)
git push origin --force --all --tags
```

---

## 11. Best Practices (Production Checklist)

- [ ] **GPG / SSH Commit Signing Enforced**: Pastikan setiap developer menandatangani commit (`git commit -S`) untuk mencegah *identity spoofing*.
- [ ] **Automated Garbage Collection Scheduling**: Jalankan `git maintenance start` pada mesin CI dan workstation monorepo untuk optimasi commit-graph dan packfile otomatis di background.
- [ ] **Gitignore Strict Whitelist**: Terapkan pendekatan whitelist di `.gitignore` untuk sistem kritis:
  ```gitignore
  # Abaikan semua secara default
  /*
  # Izinkan folder dan berkas spesifik
  !/src/
  !/docs/
  !/package.json
  ```
- [ ] **Branch Protection Rule via Matrix Approval**: Minimal 2 approving review, status check CI lolos, dan require linear history (rebase/squash only).
- [ ] **Large Binary Assets Externalization**: Gunakan **Git LFS** (Large File Storage) atau bucket object storage eksternal (S3) untuk file di atas 50MB. Cegah binary masuk ke standard DAG.

---

## 12. Hands-on Practice

Simpan seluruh hasil latihan ini pada direktori: `hands-on/m02/`

### Skenario Praktikum: Simulasi Recovery Disaster & Rekonstruksi Plumbing DAG

#### Langkah 1: Eksplorasi Object Store Mentah
```bash
mkdir -p hands-on/m02/internals-lab && cd hands-on/m02/internals-lab
git init

# Buat berkas
echo "Architectural Blueprint Alpha" > architecture.txt

# Simpan manual ke database Git
SHA=$(git hash-object -w architecture.txt)
echo "Generated SHA: $SHA"

# Telusuri berkas di dalam .git/objects/
FIRST_TWO=${SHA:0:2}
REST_HASH=${SHA:2}
ls -la .git/objects/$FIRST_TWO/$REST_HASH
```

#### Langkah 2: Inspeksi Zlib Compression
Gunakan utilitas terminal untuk melihat bahwa Git mengompresi payload secara biner menggunakan zlib:
```bash
python3 -c "import zlib; print(zlib.decompress(open('.git/objects/$FIRST_TWO/$REST_HASH', 'rb').read()).decode('utf-8', errors='ignore'))"
```

#### Langkah 3: Rekonstruksi Pohon Komit Tanpa Porcelain
```bash
# Tambahkan ke index
git update-index --add --cacheinfo 100644 $SHA architecture.txt

# Generate Tree Object
TREE=$(git write-tree)

# Generate Commit Object
COMMIT=$(echo "chore: manual raw injection" | git commit-tree $TREE)

# Set branch pointer manual
git update-ref refs/heads/master $COMMIT

# Verifikasi log
git log -v -1
```

#### Langkah 4: Simulasi "Accidental Destruction" & Pemulihan Mutlak
```bash
# Buat commit kedua
echo "Secondary Layer" >> architecture.txt
git commit -am "feat: add secondary layer"

# Catat SHA commit terbaru
CORRECT_HEAD=$(git rev-parse HEAD)

# Hancurkan worktree dan cabang secara ekstrem
git branch -D master
git checkout --orphan temp_broken
git reset --hard

# BUKTIKAN: File hilang dari working tree, branch master musnah!
# EKSEKUSI PEMULIHAN:
git reflog
# Jika reflog bersih, gunakan fsck:
git fsck --lost-found

# Pulihkan referensi master ke commit valid terakhir
git branch master $CORRECT_HEAD
git checkout master
cat architecture.txt
```

---

## 13. Exercise

### Level Easy
1. Gunakan perintah `git cat-file` untuk mencari tipe dan ukuran persis (dalam bytes) dari commit terakhir di repositori lokal Anda tanpa melihat log commit.
2. Jelaskan mengapa Git tidak langsung menyimpan nama file di dalam objek `blob`, melainkan menyimpannya di objek `tree`.

### Level Medium
1. Repositori Anda memiliki commit history bercabang (*diamond dependency merge*). Tuliskan satu baris perintah CLI menggunakan `git rev-list` dan `git log` untuk memvalidasi apakah commit `A` adalah *ancestor* langsung dari commit `B`.
2. Sebuah file konfigurasi produksi `config.json` diedit secara tidak sengaja di 5 commit terpisah. Bagaimana cara Anda menggunakan `git log` dan `git diff` untuk mengekstraksi riwayat perubahan spesifik pada rentang baris ke-40 hingga baris ke-65 pada file tersebut?

### Level Hard
1. Buat skrip Bash otomatis (`audit-pack.sh`) yang membedah file `.git/objects/pack/*.idx`. Skrip harus mengidentifikasi 10 objek terbesar di dalam packfile tanpa mengekstrak keseluruhan packfile ke disk, mencetak ukuran aslinya (*uncompressed size*), hash SHA-nya, dan path file yang memilikinya.

---

## 14. Challenge (Studi Kasus Kompleks)

### Deskripsi Masalah:
Tim platform infrastructure Anda bertugas mengonsolidasikan 3 repositori terpisah menjadi satu Monorepo terpadu:
1. `repo-auth` (Microservice Identity - Go)
2. `repo-payment` (Transaction Engine - Java)
3. `repo-frontend` (Admin Dashboard - TypeScript)

### Batasan & Persyaratan Produksi:
- Seluruh riwayat commit (*commit history*), commit hash asli (jika memungkinkan), author, timestamp, dan tag dari ketiga repositori **wajib dipertahankan secara utuh**.
- Struktur direktori akhir di dalam monorepo harus menjadi:
  - `/services/auth/` (berisi seluruh riwayat dari `repo-auth`)
  - `/services/payment/` (berisi seluruh riwayat dari `repo-payment`)
  - `/apps/frontend/` (berisi seluruh riwayat dari `repo-frontend`)
- Tidak boleh ada file merge conflict artifisial yang merusak *bisectability* (`git bisect`) di masa depan.
- Repositori akhir harus memiliki ukuran disk serendah mungkin dengan dependensi packfile yang teroptimasi.

### Tugas Anda:
Rancang spesifikasi arsitektur langkah-demi-langkah (Runbook teknis) yang memanfaatkan `git-filter-repo`, manipulasi *remote grafts*, dan *octopus merge strategy* untuk mewujudkan integrasi monorepo ini tanpa kehilangan 1 bit riwayat pun.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Basic (Pilihan Ganda)

#### Soal 1
Struktur data apa yang digunakan Git untuk menyimpan relasi riwayat commit?
- A) Singly Linked List
- B) B-Tree
- C) Directed Acyclic Graph (DAG)
- D) Hash Table Flat

#### Soal 2
Perintah plumbing manakah yang digunakan untuk menghitung SHA hash dari suatu berkas dan secara opsional menyimpannya ke dalam database `.git/objects/`?
- A) `git cat-file`
- B) `git hash-object`
- C) `git write-tree`
- D) `git mktag`

#### Soal 3
Apa peran utama berkas `.git/index`?
- A) Menyimpan riwayat stash developer.
- B) Bertindak sebagai cache biner yang memetakan working tree ke tree object berikutnya (Staging Area).
- C) Mencatat log perubahan server remote.
- D) Menyimpan daftar kredensial otentikasi SSH.

#### Soal 4
Informasi apa yang **TIDAK** disimpan di dalam sebuah objek Blob Git?
- A) Isi mentah teks berkas.
- B) Metadata byte berkas biner.
- C) Nama berkas (*filename*) dan izin akses POSIX (*file permissions*).
- D) Karakter baris baru (*line endings*).

#### Soal 5
Apa fungsi dari file `HEAD` pada sistem Git?
- A) Menunjuk secara konstan ke commit pertama (root).
- B) Pointer referensi simbolik ke branch yang sedang aktif di-checkout.
- C) Menampung backup merge conflict.
- D) Cache commit log tercepat.

---

### 15.2 Intermediate (Pilihan Ganda)

#### Soal 6
Dalam skenario optimasi monorepo, teknik manakah yang menginstruksikan Git untuk hanya mengunduh metadata commit/tree saat kloning dan menunda pengunduhan isi file mentah (blob) hingga dibutuhkan?
- A) `git clone --depth 1`
- B) `git clone --bare`
- C) `git clone --filter=blob:none`
- D) `git sparse-checkout disable`

#### Soal 7
Apa perbedaan mendasar antara *Annotated Tag* dan *Lightweight Tag* di level Git internals?
- A) Annotated tag disimpan di `.git/refs/tags/` sedangkan lightweight disimpan di remote.
- B) Annotated tag adalah objek mandiri di dalam `.git/objects` lengkap dengan metadata dan checksum, sedangkan lightweight tag hanyalah file referensi murni yang menunjuk langsung ke commit SHA.
- C) Lightweight tag memerlukan signature GPG, annotated tag tidak.
- D) Annotated tag hanya berlaku untuk merge commit.

#### Soal 8
Jika Anda menjalankan perintah `git gc --prune=now`, apa yang terjadi pada objek commit yang tidak memiliki referensi (unreachable) dan tidak ada di reflog?
- A) Objek dipindahkan ke folder `.git/lost-found` sebagai backup zip.
- B) Objek diubah tipenya menjadi blob.
- C) Objek dihapus secara permanen dari sistem berkas disk.
- D) Objek dikompresi menjadi annotated tag otomatis.

#### Soal 9
Manakah server-side hook yang paling tepat digunakan untuk menegakkan aturan tata kelola organisasi (seperti memblokir commit yang tidak mencantumkan ID JIRA atau mendeteksi file secret) sebelum referensi branch diperbarui di server Git?
- A) `post-receive`
- B) `pre-commit`
- C) `pre-receive`
- D) `post-update`

#### Soal 10
Mengapa teknik *Sparse-Checkout Cone Mode* (`git sparse-checkout set --cone`) jauh lebih direkomendasikan untuk repositori skala enterprise dibanding non-cone mode?
- A) Mengizinkan download file via HTTP/2 tanpa enkripsi.
- B) Mengabaikan pengecekan merge conflict.
- C) Membatasi pola pencocokan direktori secara linear/rekursif berbasis prefix, menghilangkan kompleksitas parsing Regex O(N) yang lambat.
- D) Mengubah seluruh blob menjadi symlink otomatis.

---

### 15.3 Skenario Kasus Produksi

#### Kasus A
CI runner pipeline Anda mengalami kegagalan build intermiten dengan log error: `fatal: packfile './.git/objects/pack/pack-...pack' is corrupted (bad tree object)`.  
Bagaimana langkah isolasi forensik Anda untuk mengidentifikasi commit/tree yang rusak tersebut, dan bagaimana cara memulihkannya jika salinan sehat tersedia di mesin developer lokal?

#### Kasus B
Sebuah enterprise fintech mengharuskan bahwa tidak boleh ada *merge commit* pada branch `main` (harus linear history) dan semua commit harus ditandatangani menggunakan GPG. Developer sering lupa dan melakukan standard `git merge` lokal lalu mencoba me-push ke server.  
Rancang arsitektur server-side validation script (`pre-receive`) ringkas untuk memvalidasi:
1. Setiap commit baru tidak boleh memiliki parent lebih dari satu (no merge commits).
2. Status PGP/GPG signature commit valid.

#### Kasus C
Sebuah tim data engineering secara tidak sengaja menambahkan file model AI berukuran 12 GB ke git history 3 bulan lalu. Meskipun file tersebut sudah di-`rm` pada commit berikutnya, developer baru yang melakukan clone tetap mengunduh riwayat 12 GB tersebut.  
Jelaskan urutan tindakan devops engineer untuk membuang blob 12 GB tersebut secara permanen dari seluruh ref remote, merekayasa ulang DAG tanpa merusak tanggal author asli, dan langkah-langkah yang harus diambil oleh ratusan developer lain di tim tersebut untuk menyinkronkan repositori lokal mereka!

---

### Kunci Jawaban & Analisis Evaluasi

#### Kunci Jawaban Basic
1. **C** — Git mengimplementasikan struktur DAG (*Directed Acyclic Graph*), di mana commit adalah node yang menunjuk ke parent-nya secara terarah dan tidak pernah melingkar (*acyclic*).
2. **B** — `git hash-object` adalah plumbing command yang menghitung SHA hash dan opsi `-w` menulis objek tersebut ke database `.git/objects/`.
3. **B** — File `.git/index` adalah staging area biner yang merekam pohon file yang disiapkan untuk commit berikutnya.
4. **C** — Blob murni hanya berisi konten data berkas. Nama berkas dan mode perizinan disimpan pada Tree object.
5. **B** — Berkas `HEAD` adalah file teks referensi simbolik yang mengindikasikan cabang yang sedang aktif (contoh: `ref: refs/heads/main`).

#### Kunci Jawaban Intermediate
6. **C** — Argumen `--filter=blob:none` menginstruksikan git server untuk mengecualikan blob dari proses initial fetch/clone (blobless clone).
7. **B** — Annotated tag adalah first-class Git object dengan author, message, timestamp, dan hash SHA tersendiri. Lightweight tag hanya sebuah pointer text file sederhana di dalam directori `refs/tags/`.
8. **C** — Parameter `--prune=now` memaksa garbage collector untuk memotong masa retensi grace-period standar (14 hari) dan langsung menghapus loose unreachable objects secara permanen.
9. **C** — `pre-receive` adalah script pertama yang dieksekusi di server saat menerima push, sebelum ada referensi yang dimutasi, menjadikannya gerbang validasi terbaik.
10. **C** — Cone mode membatasi sparse matching hanya pada level folder (berbasis direktori rekursif), menghindari algoritma Regex globbing kompleks pada jutaan file yang dapat memicu degradasi performa I/O masif.

#### Analisis Solusi Skenario Produksi

##### Solusi Kasus A
1. **Forensik**: Jalankan `git fsck --full --strict` pada server/runner untuk melokalisasi SHA spesifik objek packfile yang mengalami *bad sha/corrupt zlib header*.
2. **Pencarian Objek Sehat**: Cari hash SHA tersebut di repositori lokal developer yang masih sehat menggunakan `git cat-file -e <SHA>`.
3. **Ekstraksi & Injeksi**: Ekstrak objek sehat dari mesin developer menggunakan `git cat-file -p <SHA>` atau salin file loose object dari direktori `.git/objects/XX/XXX...` lokal developer langsung ke path yang sama di CI runner/server.
4. **Verifikasi**: Jalankan kembali `git fsck` untuk memastikan integritas packfile dan database DAG telah pulih sepenuhnya.

##### Solusi Kasus B
Skrip `pre-receive` shell logic:
```bash
#!/usr/bin/env bash
while read oldrev newrev refname; do
    if [ "$refname" = "refs/heads/main" ]; then
        # Ambil daftar commit baru
        for commit in $(git rev-list $oldrev..$newrev); do
            # 1. Cek jumlah parent
            parents=$(git rev-list --parents -n 1 $commit | awk '{print NF-1}')
            if [ "$parents" -gt 1 ]; then
                echo "ERROR: Merge commit terdeteksi pada $commit. Hanya linear history (rebase/squash) yang diizinkan."
                exit 1
            fi
            # 2. Cek GPG Signature
            if ! git verify-commit "$commit" >/dev/null 2>&1; then
                echo "ERROR: Commit $commit tidak memiliki GPG signature yang valid!"
                exit 1
            fi
        done
    fi
done
exit 0
```

##### Solusi Kasus C
1. **Purging Objek**: Gunakan `git-filter-repo --strip-blobs-bigger-than 100M` atau `git-filter-repo --invert-paths --path <path_ke_file_model>` pada mirror clone repositori.
2. **Prune**: Bersihkan database git server menggunakan:
   ```bash
   git reflog expire --expire=now --all
   git gc --prune=now --aggressive
   ```
3. **Force Update Remote**: Push rewrite history ke origin via `git push origin --force --all --tags`.
4. **Mitigasi Tim Developer**: Developer dilarang melakukan `git pull` standar karena akan menggabungkan kembali commit 12GB lama (*re-introducing the ghost objects*). Seluruh developer wajib mengeksekusi:
   ```bash
   git fetch origin
   git reset --hard origin/main
   # Atau melakukan fresh re-clone dari origin yang sudah bersih
   ```

---

## 16. Summary

Git adalah sistem penyimpanan objek berbasis konten kriptografis yang efisien dan elegan. Inti dari keandalan Git terletak pada pemisahan yang bersih antara data mentah (*Blobs*), struktur hierarki berkas (*Trees*), catatan snapshot historis (*Commits*), dan pointer dinamis (*Refs*).

Untuk repositori berskala enterprise dan arsitektur monorepo masif, pemahaman tingkat tinggi saja tidak cukup. Para *Lead Engineer* dan *Architect* harus menguasai:
- Mekanisme **Partial Clones** dan **Sparse-Checkout** untuk mengatasi batasan I/O sistem berkas.
- Tata kelola keamanan mutlak menggunakan **GPG Commit Signing** dan **Server-Side Policy Enforcement** (`pre-receive hooks`).
- Kesiapan mitigasi bencana (*Disaster Recovery*) memanfaatkan pembedahan internal (`git reflog`, `git fsck`, `git-filter-repo`, dan *plumbing commands*).

Penguasaan terhadap internal Git menjamin stabilitas repositori kode sebagai aset intelektual terpenting perusahaan, menjaga siklus pengembangan perangkat lunak tetap cepat, aman, dan dapat diskalakan ke ribuan kontributor.