# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

- **Menganalisis dan Membedah Internal Git**: Memahami struktur penyimpanan *Content-Addressable Storage* (CAS), mekanisme pengalamatan objek kriptografis (SHA-1/SHA-256), serta siklus hidup pemadatan data (*packfiles* dan *delta compression*).
- **Menguasai Operasi *Plumbing***: Mengonstruksi status *tree*, objek *commit*, dan manipulasi *reference pointer* secara deterministik tanpa bergantung pada antarmuka *porcelain*.
- **Merancang Infrastruktur Git Skala Enterprise**: Menerapkan arsitektur monorepo berkinerja tinggi menggunakan *Partial Clones*, *Sparse-Checkout*, dan integrasi *Git Large File Storage* (LFS) berbasis penyimpanan objek eksternal (S3/GCS).
- **Mengimplementasikan Tata Kelola dan *Policy Enforcement***: Membangun *hook pipeline* terdistribusi (klien dan server-side *pre-receive hooks*) untuk validasi kriptografis, pencegahan kebocoran kredensial, dan kepatuhan audit regulasi.
- **Melakukan Rekonstruksi dan Pemulihan Bencana Repositori**: Menjalankan operasi pembersihan riwayat secara bedah (*history rewriting*) menggunakan `git-filter-repo`, menyelesaikan korupsi objek DAG (*Directed Acyclic Graph*), dan mengisolasi dependensi melalui strategi *subtree* atau *submodule*.

---

## 2. Prerequisites

Sebelum memulai modul ini, Anda wajib memiliki pemahaman mendalam tentang:

1. **Pengoperasian Antarmuka *Porcelain* Git**: Penggunaan harian `git rebase -i`, `git merge` (termasuk resolusi konflik tiga arah / *three-way merge*), `git cherry-pick`, dan `git bisect`.
2. **Sistem Operasi POSIX & Arsitektur Berkas**: Penanganan *standard streams* (`stdin`, `stdout`, `stderr`), *file descriptors*, *inode*, *symlink*, dan eksekusi skrip Bash/POSIX.
3. **Prinsip Kriptografi Dasar**: Fungsi *hash* satu arah (SHA-1, SHA-256), penandatanganan asimetris (GPG/SSH *signature verification*), dan enkripsi transit (TLS/SSH *handshake*).
4. **Jaringan Komputer & API**: Pemahaman protokol transfer data (HTTP/2, Smart HTTP, SSH v2) serta integrasi Webhooks dengan layanan backend.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Content-Addressable Storage (CAS) dan Objek Git

Git secara fundamental bukanlah sistem manajemen versi berbasis *delta file*, melainkan sebuah *filesystem* berbasis *content-addressable* dengan antarmuka pelacakan riwayat (VCS) di atasnya. Setiap data yang disimpan ke dalam direktori `.git/objects/` diidentifikasi oleh nilai *hash* kriptografis dari konten tersebut beserta *header*-nya.

Struktur *header* Git objek menggunakan format:
```text
[tipe_objek] [panjang_konten_dalam_bytes]\0[konten_biner]
```

Git mendefinisikan empat tipe objek dasar:

1. **Blob**: Menyimpan data mentah berkas tanpa metadata (nama berkas, izin akses mode POSIX, atau stempel waktu tidak disimpan di sini).
2. **Tree**: Merepresentasikan direktori. Berisi daftar referensi ke hash objek *blob* (untuk berkas) atau *tree* lain (untuk sub-direktori), lengkap dengan mode berkas POSIX (misal: `100644` untuk berkas biasa, `100755` untuk berkas *executable*, `040000` untuk direktori).
3. **Commit**: Mengikat *tree* akar (*root tree*) dengan riwayat logis. Berisi hash *root tree*, hash satu atau lebih *parent commit*, identitas *author* (pembuat kode), identitas *committer* (penerap kode), stempel waktu, serta pesan *commit*.
4. **Annotated Tag**: Penunjuk permanen ke objek *commit* tertentu yang menyimpan metadata penanda, tanggal pembuatan, pesan tag, dan opsional tanda tangan kriptografis GPG.

```
+-------------------------------------------------------------------------+
|                              COMMIT OBJECT                              |
| Hash: e4b2c9...                                                         |
| tree: 7f3a1d... (Root Tree)                                             |
| parent: a1b2c3...                                                       |
| author: Lead Eng <lead@corp.internal> 1708848000 +0700                  |
| committer: Lead Eng <lead@corp.internal> 1708848000 +0700               |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                               TREE OBJECT                               |
| Hash: 7f3a1d...                                                         |
| 100644 blob c82e5a...    README.md                                      |
| 100755 blob a91f3b...    deploy.sh                                      |
| 040000 tree d4e5f6...    src/                                           |
+------------------------------------+------------------------------------+
                                     |
                         +-----------+-----------+
                         |                       |
                         v                       v
      +-----------------------------+ +-----------------------------+
      |         BLOB OBJECT         | |         TREE OBJECT         |
      | Hash: c82e5a...             | | Hash: d4e5f6...             |
      | Content: "# Core API Docs"  | | 100644 blob f1c2b3... main.go|
      +-----------------------------+ +-----------------------------+
```

### 3.2 Penyimpanan Loose Objects vs. Packfiles

Objek yang baru dibuat disimpan sebagai berkas individual (*loose objects*) di direktori `.git/objects/XX/YYYY...`, di mana `XX` adalah 2 karakter pertama hash, dan `YYYY...` adalah 38 karakter sisanya. Objek ini dikompresi menggunakan algoritma Zlib (RFC 1950).

Pada skala enterprise dengan jutaan berkas dan riwayat *commit*, keberadaan miliaran *loose objects* menyebabkan inefisiensi alokasi blok disk (*inode exhaustion*) dan degradasi performa I/O. Git mengatasi hal ini melalui mekanisme *Packing*:

- **Packfile (`.pack`)**: Sebuah arsip biner tunggal yang mengonsolidasikan ribuan/jutaan objek. Git menerapkan algoritma *sliding window delta compression*: objek yang mirip (misalnya versi berbeda dari berkas yang sama) disimpan sebagai selisih (*delta offset*) terhadap versi dasarnya.
- **Index File (`.idx`)**: Berkas indeks biner yang berisi tabel *lookup* terurut dan *offset pointer* 64-bit yang memungkinkan pencarian objek O(log N) secara acak di dalam berkas `.pack` tanpa membaca seluruh berkas dari awal.

### 3.3 Sistem Referensi (Refs) dan HEAD

Referensi Git hanyalah berkas teks sederhana di dalam `.git/refs/` yang menyimpan 40 karakter hash heksadesimal:

- **Direct Reference**: Berkas statis seperti `.git/refs/heads/main` yang berisi hash commit terakhir pada cabang tersebut.
- **Symbolic Reference**: Berkas penunjuk dinamis. Contoh paling fundamental adalah `.git/HEAD`, yang biasanya berisi string seperti `ref: refs/heads/main`. Saat repositori berada pada kondisi *detached HEAD*, berkas ini langsung menyimpan raw commit hash alih-alih jalur referensi.
- **Packed-Refs**: Untuk meminimalkan berkas individual, Git memadatkan referensi yang jarang berubah ke dalam berkas tunggal `.git/packed-refs`.

### 3.4 Arsitektur Git Large File Storage (LFS)

Git tidak dirancang secara native untuk berkas biner besar yang berubah secara berkala karena kompresi delta tidak efektif pada data terkompresi/terenkripsi (misalnya video, model AI, arsip zip). Git LFS menyelesaikan masalah ini melalui arsitektur decoupled:

1. **Smudge Filter**: Dijalankan pada fase *checkout*. Mengganti pointer metadata LFS yang ada di repositori lokal dengan konten biner riil yang diunduh dari server penyimpanan objek LFS.
2. **Clean Filter**: Dijalankan pada fase `git add`. Mengekstraksi konten biner besar ke penyimpanan cache LFS lokal (`.git/lfs/objects/`), menghitung hash SHA-256 dari biner tersebut, lalu menuliskan berkas pointer kecil berukuran ~130 bytes ke staging area Git biasa.

```
Git Working Tree                   Git Staging / Index             Remote LFS Storage
+-------------------+              +-------------------+          +------------------+
|  large_model.bin  | --(clean)--> |  Pointer File:    | -------> |  AWS S3 / GCS    |
|  (Raw 2.5 GB)     |   Filter     |  version: v1      |  Push    |  (Actual Binary  |
+-------------------+              |  oid sha256:...   |          |   Payload Store) |
                                   |  size: 2684354560 |          +------------------+
                                   +-------------------+
```

---

## 4. Why & What

### Mengapa Pendekatan Tradisional Gagal di Skala Enterprise?

- **Bottleneck Throughput Jaringan**: Repositori berukuran puluhan gigabyte memerlukan waktu *clone* yang tidak realistis untuk *pipeline* CI/CD paralel, meningkatkan biaya *bandwidth* cloud secara eksponensial.
- **Degradasi Kinerja Operasi Dasar**: Pada repositori dengan ratusan ribu berkas, perintah sederhana seperti `git status` atau `git checkout` dapat membutuhkan waktu beberapa menit akibat *scanning overhead* pada *Virtual File System* (VFS).
- **Integritas dan Kepatuhan Regulasi**: Tanpa proteksi ketat di tingkat *pre-receive*, repositori dapat terkontaminasi oleh rahasia perusahaan (*API keys*, sertifikat privat), berkas biner raksasa yang tidak sengaja ter-commit, atau riwayat kerja tanpa tanda tangan kriptografis valid yang melanggar audit SOC 2 / ISO 27001.

### Apa yang Diimplementasikan dalam Modul Ini?

Kami mengimplementasikan arsitektur kontrol repositori tingkat rendah:
1. Pemanfaatan antarmuka *plumbing* untuk manipulasi struktur Git secara programatis dan deterministik.
2. Konfigurasi repositori berskala besar (*Monorepo optimization*) menggunakan kombinasi *Blobless/Treeless Clones* dan *Sparse-Checkout Patterns*.
3. Implementasi gerbang validasi server (*Pre-Receive Governance Engine*) yang menolak mutasi tidak valid sebelum referensi Git diubah di remote bare repository.

---

## 5. How (Workflow Detail)

### 5.1 Siklus Hidup Objek Plumbing

Alur konstruksi objek Git secara programatis dimulai dari data mentah hingga menjadi commit di cabang:

```
[Raw File Content]
       |
       v (git hash-object -w)
 [Blob Object]
       |
       v (git update-index --add --cacheinfo)
 [Git Index / Staging]
       |
       v (git write-tree)
 [Tree Object] <----+ (Sub-trees recursively)
       |
       v (git commit-tree -p <parent_hash> -m <msg>)
[Commit Object]
       |
       v (git update-ref refs/heads/<branch>)
[Updated Branch Pointer]
```

### 5.2 Server-Side Verification Lifecycle

Saat pengembang mengeksekusi `git push`, remote Git server menjalankan siklus validasi berikut:

```
Developer (git push)
        |
        v [SSH/HTTPS Authentication & Authorization]
Git Remote Bare Engine
        |
        +---> [Penerimaan Packfile Sementara (.tmp_pack)]
        |
        +---> Eksekusi: hooks/pre-receive
        |           |
        |           +---> Membaca STDIN: <old-value> <new-value> <ref-name>
        |           +---> Menjalankan Security, Signature, & Size Scanners
        |           |
        |           +---> Status Exit 0?
        |                     |
        |                     +-- YES: Lanjutkan transaksi
        |                     +-- NO : Batalkan transaksi, bersihkan packfile sementara,
        |                              kirim error log ke developer
        |
        +---> Mutasi Referensi (refs/heads/*)
        |
        +---> Eksekusi: hooks/update (per-ref)
        |
        +---> Eksekusi: hooks/post-receive (Asynchronous notifications, Webhooks, CI triggers)
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Git sebagai Bank Brankas Terdesentralisasi

- **Blob**: Emas batangan murni. Tidak memiliki label nama kepemilikan di fisiknya. Nilai dan identitasnya dihitung murni dari berat dan kemurniannya (kandungan datanya di-hash).
- **Tree**: Kotak deposit bertingkat yang diberi nomor register. Kotak ini mencantumkan daftar barang apa saja yang ada di dalamnya ("Di sekat A ada emas berkode X, di sekat B ada kotak deposit lain berkode Y").
- **Commit**: Surat berita acara penyerahan brankas. Mencatat siapa yang menyegel brankas, kapan penyegelan dilakukan, brankas induk sebelumnya yang digantikan, serta cap stempel notaris (*digital signature*).
- **Refs (Branches)**: Label stiker kertas yang ditempel di pintu luar brankas. Label ini dapat dipindahkan dengan mudah ke brankas lain tanpa perlu memindahkan isi brankas itu sendiri.

### Diagram Arsitektur Internal Repositori Enterprise

```
+-------------------------------------------------------------------------------+
|                       ENTERPRISE MONOREPO ARCHITECTURE                        |
+-------------------------------------------------------------------------------+
| LOCAL CLIENT ENVIRONMENT                                                      |
|                                                                               |
|  Sparse-Checkout Scope: /services/payment-gateway/*                           |
|                                                                               |
|  +--------------------+      +--------------------+     +-------------------+ |
|  | Virtualized Trees  | <--> | Git Index (Cache)  | <-> | Local Working Tree| |
|  +--------------------+      +--------------------+     +-------------------+ |
|            ^                           ^                                      |
|            | Partial Clone             | Smudge/Clean                         |
|            | (--filter=blob:none)      v                                      |
|            |                 +--------------------+                           |
|            |                 | Git LFS Local Core |                           |
|            |                 +--------------------+                           |
+------------|---------------------------|--------------------------------------+
             |                           |
             | RPC / Smart HTTP          | HTTPS REST Batch API
             v                           v
+----------------------------+  +-----------------------------------------------+
| GitHub Enterprise / GitLab |  | S3-Compatible Object Store (Git LFS Backend) |
| Bare Repository Engine     |  +-----------------------------------------------+
|                            |  | Pointer SHA256-Matched Binaries:              |
|  +----------------------+  |  | - ML Models (*.onnx, *.pt)                    |
|  | hooks/pre-receive    |  |  | - Firmware Binaries (*.bin)                   |
|  | - Policy Engine      |  |  | - High-res Assets (*.tar.gz)                  |
|  | - Secret Blocker     |  |  +-----------------------------------------------+
|  +----------------------+  |
|  | Packfiles & Metadata |  |
|  +----------------------+  |
+----------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Manipulasi Git Menggunakan *Plumbing Commands*

Skrip berikut membuktikan bahwa komitmen Git dapat dibuat secara presisi dari level primitif tanpa menyentuh perintah *porcelain* standar (`git add` atau `git commit`).

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Inisialisasi repositori eksperimental
rm -rf test-plumbing && mkdir test-plumbing && cd test-plumbing
git init

# 2. Tulis raw blob langsung ke object database
BLOB_CONTENT="console.log('Enterprise Core Engine v1.0');"
BLOB_HASH=$(printf "%s" "$BLOB_CONTENT" | git hash-object -w --stdin)
echo "Blob Hash Terbuat: ${BLOB_HASH}"

# Verifikasi keberadaan berkas fisik loose object
OBJECT_SUBDIR=$(echo "$BLOB_HASH" | cut -c1-2)
OBJECT_FILE=$(echo "$BLOB_HASH" | cut -c3-40)
echo "Loose object tersimpan di: .git/objects/${OBJECT_SUBDIR}/${OBJECT_FILE}"

# 3. Masukkan blob ke Staging Area (Index) dengan nama berkas dan mode eksekusi POSIX
git update-index --add --cacheinfo 100644 "$BLOB_HASH" "src/app.js"

# 4. Tulis staging area menjadi Tree Object
TREE_HASH=$(git write-tree)
echo "Root Tree Hash: ${TREE_HASH}"

# Inspeksi isi Tree Object
git ls-tree "$TREE_HASH"

# 5. Buat Commit Object pertama (Root Commit tanpa Parent)
COMMIT_HASH=$(echo "feat(core): initial plumbing architectural commit" | git commit-tree "$TREE_HASH")
echo "Commit Hash Terbuat: ${COMMIT_HASH}"

# 6. Arahkan cabang main ke Commit Hash baru secara manual
git update-ref refs/heads/main "$COMMIT_HASH"

# 7. Sinkronkan working directory dengan index dan HEAD
git reset --hard refs/heads/main

# Verifikasi log akhir
git log -1 --stat
```

---

### 7.2 Practical Example: Enterprise Pre-Receive Hook (Policy & Secret Gating)

Skrip server-side hook berikut dirancang untuk dijalankan di direktori `hooks/pre-receive` pada Git Server terpusat (GitHub Enterprise, GitLab Self-Managed, atau Gitorious/Bare Server). Hook ini memblokir push jika:
1. Mengandung berkas biner > 5MB tanpa menggunakan Git LFS.
2. Mengandung *leaked secrets* (Pola RegEx AWS Access Key / Generic Private Keys).
3. Pesan *commit* tidak mematuhi konvensi *Conventional Commits*.

```bash
#!/usr/bin/env bash
#
# Production Pre-Receive Hook: Enterprise Integrity Enforcement
# Lokasi implementasi: <bare-repo.git>/hooks/pre-receive
# Pastikan perizinan: chmod +x hooks/pre-receive
#

set -euo pipefail

MAX_SIZE_BYTES=5242880 # Batas toleransi 5MB
ZERO_COMMIT="0000000000000000000000000000000000000000"

# Regular Expressions
CONVENTIONAL_COMMIT_REGEX="^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-z0-9_-]+\))?: .{1,100}$"
SECRET_PATTERNS=(
    "AKIA[0-9A-Z]{16}"                           # AWS Access Key ID
    "-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----" # Cryptographic Private Keys
)

reject() {
    echo "=================================================================" >&2
    echo " [SECURITY & POLICY VIOLATION] Gagal memproses pembaruan Git"     >&2
    echo " Detail Kesalahan: $1"                                            >&2
    echo "=================================================================" >&2
    exit 1
}

validate_commit_metadata() {
    local rev="$1"
    local msg
    msg=$(git log -1 --format=%B "$rev")

    if ! echo "$msg" | head -n 1 | grep -Eq "$CONVENTIONAL_COMMIT_REGEX"; then
        reject "Pesan commit pada [$rev] tidak sesuai format Conventional Commits: '$msg'"
    fi
}

validate_blob() {
    local blob_hash="$1"
    local file_path="$2"

    # 1. Periksa batas ukuran objek biner langsung
    local size
    size=$(git cat-file -s "$blob_hash")
    if [ "$size" -gt "$MAX_SIZE_BYTES" ]; then
        reject "Berkas [$file_path] melampaui ukuran maksimum ($((size / 1024 / 1024))MB > 5MB). Gunakan Git LFS!"
    fi

    # 2. Scanning kebocoran secret pada berkas
    local content
    content=$(git cat-file -p "$blob_hash")
    for pattern in "${SECRET_PATTERNS[@]}"; do
        if echo "$content" | grep -Eq "$pattern"; then
            reject "Ditemukan pola rahasia kredensial (Secret Leak) pada berkas [$file_path]!"
        fi
    done
}

# Memproses STDIN line-by-line: <old-value> <new-value> <ref-name>
while read -r OLD_REV NEW_REV REF_NAME; do
    # Jika cabang dihapus (Branch Deletion), lewati validasi
    if [ "$NEW_REV" = "$ZERO_COMMIT" ]; then
        continue
    fi

    # Tentukan rentang commit yang dievaluasi
    if [ "$OLD_REV" = "$ZERO_COMMIT" ]; then
        # Cabang baru: Validasi seluruh commit baru yang tidak ada di refs/heads/* lain
        RANGE="$NEW_REV"
        EXCLUDE_EXISTING="--not --branches"
    else
        # Cabang eksis yang diperbarui: Validasi delta commit saja
        RANGE="${OLD_REV}..${NEW_REV}"
        EXCLUDE_EXISTING=""
    fi

    COMMITS=$(git rev-list "$RANGE" $EXCLUDE_EXISTING || true)

    for COMMIT in $COMMITS; do
        # Evaluasi struktur pesan commit
        validate_commit_metadata "$COMMIT"

        # Evaluasi seluruh berkas yang dimutasi dalam commit ini
        git diff-tree -r -c --no-commit-id "$COMMIT" | while read -r line; do
            if [ -z "$line" ]; then continue; fi
            
            # Format parsing output diff-tree: :mode_old mode_new sha_old sha_new status filename
            NEW_OBJECT_HASH=$(echo "$line" | awk '{print $4}')
            STATUS=$(echo "$line" | awk '{print $5}')
            FILE_PATH=$(echo "$line" | awk '{print $6}')

            # Abaikan berkas yang dihapus (status D)
            if [ "$STATUS" != "D" ] && [ "$NEW_OBJECT_HASH" != "$ZERO_COMMIT" ]; then
                validate_blob "$NEW_OBJECT_HASH" "$FILE_PATH"
            fi
        done
    done
done

echo "Seluruh validasi integritas repositori berhasil dilewati."
exit 0
```

---

## 8. Real World Case Study (Enterprise Scale)

### Konteks Masalah
Sebuah institusi perbankan multinasional mengalami kegagalan operasional pada repositori monorepo arsitektur inti mereka:
- **Ukuran Repositori**: 68 GB pada disk server Git, 4.2 juta commit, 450.000 berkas terdaftar.
- **Gejala**: 
  - Waktu pengerjaan `git clone` rata-rata 54 menit pada jaringan kantor, menyebabkan kegagalan *timeout* pada agen CI/CD Kubernetes.
  - Perintah `git status` memakan waktu 45 detik di mesin lokal developer karena penelusuran jutaan berkas oleh subsistem VFS.
  - Terdapat kebocoran berkas `.env` dan sertifikat `.p12` lama di dalam riwayat commit tahun 2018 yang tersimpan permanen di *packfile*.

### Analisis Akar Masalah (Root Cause Analysis)
1. **Penyimpanan Aset Statis**: Terdapat direktori `sdk-releases/` berisi berkas `.zip` dan file biner *compiled artifact* Java `.jar` berukuran puluhan gigabyte yang di-*commit* selama bertahun-tahun langsung ke DAG Git tanpa delta compression yang efisien.
2. **Ketiadaan Sparse Mechanism**: Setiap developer frontend men-download seluruh kode backend mikroservis, pustaka C++, dan dokumen audit.

### Solusi Rekayasa & Transformasi

#### Fase 1: Bedah Riwayat Ekstrem Menggunakan `git-filter-repo`
Membersihkan seluruh histori repositori dari file biner tak berguna dan secret masa lalu:

```bash
# Instalasi git-filter-repo via pip
pip3 install git-filter-repo

# Kloning mirror lengkap repositori terisolasi
git clone --mirror git@corp-vcs.internal:banking/core-monorepo.git core-monorepo-migration.git
cd core-monorepo-migration.git

# Ekstraksi dan eliminasi berkas biner ilegal serta kredensial di seluruh cabang & tags
cat << 'EOF' > expressions.txt
regex:(password|api_key|client_secret)\s*=\s*['"][A-Za-z0-9_=-]+['"]==>[REDACTED]
EOF

git-filter-repo \
  --strip-blobs-bigger-than 10M \
  --path-glob "sdk-releases/*.zip" --invert-paths \
  --path-glob "sdk-releases/*.jar" --invert-paths \
  --replace-text expressions.txt \
  --force

# Rekonstruksi database dan repacking total
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```
*Hasil Fase 1*: Ukuran repositori dasar terpangkas dari **68 GB menjadi 3.2 GB**.

#### Fase 2: Implementasi Blobless Partial Clone & Sparse-Checkout
Setiap developer lokal dan runner CI/CD diinstruksikan untuk menggunakan konfigurasi sparse:

```bash
# Clone repositori tanpa mengunduh seluruh isi blob (Blobless Clone)
git clone --filter=blob:none --no-checkout git@corp-vcs.internal:banking/core-monorepo.git enterprise-workspace
cd enterprise-workspace

# Konfigurasi Sparse-Checkout menggunakan algoritma cone (O(1) tree match)
git sparse-checkout init --cone

# Fokus hanya pada domain payment gateway
git sparse-checkout set services/payment-core libs/common-auth

# Lakukan checkout materialisasi
git checkout main
```

#### Fase 3: Integrasi Git LFS Terdistribusi
Mengalihkan berkas data mock pengujian transaksi (.parquet, .iso) ke Git LFS yang diarahkan ke MinIO S3 cluster on-premise:

```bash
git lfs install
git lfs track "*.parquet"
git lfs track "*.iso"
git add .gitattributes
git commit -m "chore(infra): configure git-lfs for heavy test payloads"
```

### Metrik Hasil Transformasi

| Metrik Kinerja | Sebelum Implementasi | Setelah Implementasi | Peningkatan |
| :--- | :--- | :--- | :--- |
| **Waktu CI Init (`clone`)** | 54 Menit | 28 Detik | **99.1% reduksi** |
| **Penggunaan Disk Lokal Dev**| 68 GB | 2.1 GB | **96.9% penghematan** |
| **Latensi `git status`** | ~45 Detik | 0.3 Detik | **150x lebih cepat** |
| **Kepatuhan Audit Kriptografis**| Gagal (Kredensial Bocor) | Lolos (Enforced SHA-256 GPG) | **Compliant** |

---

## 9. Trade-offs

| Aspek Arsitektur | Pilihan Desain | Keuntungan (Pros) | Biaya & Kerugian (Cons/Trade-offs) |
| :--- | :--- | :--- | :--- |
| **Struktur Repositori** | *Monorepo* | Pelacakan dependensi atomik; visibilitas kode terpadu; *single source of truth*. | Membutuhkan tooling mutakhir (*sparse-checkout*, blobless clones); risiko skalabilitas I/O. |
| | *Polyrepo* | Isolasi hak akses granular; siklus CI terpisah; footprint kloning kecil. | *Cross-repository dependency hell*; koordinasi rilis lintas layanan sangat kompleks. |
| **Strategi Integrasi Riwayat** | *Squash Merging* | Riwayat linear bersih; penyederhanaan operasi `revert` di tingkat fitur. | Metadata historis atomik per-commit hilang; operasi `git bisect` di dalam fitur menjadi tidak mungkin. |
| | *Merge Commit (No-FF)* | Melestarikan konteks cabang dan kronologi asli pengembangan. | Graph commit menjadi kusut (*railroad tracks*); mempersulit analisis navigasi manual. |
| **Manajemen File Biner** | *In-tree Git Storage* | Repositori bersifat mandiri (*hermetic*); tidak bergantung pada server eksternal. | *Packfile bloat* permanen; waktu kloning membengkak selaras waktu. |
| | *Git LFS* | Repositori Git tetap ramping; transfer biner sesuai kebutuhan (*lazy pull*). | Ketergantungan infrastruktur storage LFS terpisah; kompleksitas autentikasi ganda (Git vs LFS API). |
| **Pemadatan Objek** | `git gc --aggressive` | Rasio kompresi disk maksimal; struktur *packfile delta chain* optimal. | Membutuhkan konsumsi CPU dan memori (RAM) sangat tinggi saat kompresi dilakukan; waktu eksekusi lama. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Rusaknya Riwayat Akibat Shared Branch Rebasing
- **Gejala**: Pengembang menjalankan `git rebase` pada cabang kolaborasi publik (`develop` atau `release/*`), lalu melakukan `git push --force`. Pengembang lain mengalami penolakan *divergent tree* dan duplikasi riwayat commit saat menarik data.
- **Penyebab**: Hash commit bersifat deterministik terhadap commit induknya (*parent hash*). Rebase menciptakan commit baru dengan hash berbeda meskipun isi kodenya identik.
- **Troubleshooting & Mitigasi**:
  1. Hindari penggunaan `--force`. Wajibkan konfigurasi server `--force-with-lease` untuk memverifikasi referensi remote lokal sebelum menimpa.
  2. Gunakan `git reflog` pada mesin yang memicu insiden untuk menemukan commit hash sesaat sebelum rebase terjadi.
  3. Lakukan hard reset dan pemulihan:
     ```bash
     git reset --hard ORIG_HEAD
     # Atau tentukan titik spesifik via reflog
     git reset --hard HEAD@{1}
     git push --force-with-lease origin release/v2.1
     ```

### 10.2 Korupsi Database Objek Git (Corrupt Loose Object)
- **Gejala**: Pesan galat `error: object file .git/objects/4b/825dc... is empty` atau `fatal: loose object ... is corrupt`.
- **Troubleshooting**:
  1. Identifikasi objek yang rusak menggunakan `git fsck --full`.
  2. Jika objek yang rusak adalah berkas blob, cari commit yang merujuknya melalui riwayat branch.
  3. Ambil data dari index cache atau remote clone yang sehat:
     ```bash
     # Verifikasi integritas
     git fsck --full

     # Temukan objek yang rusak dan hapus berkas 0-byte tersebut
     find .git/objects/ -type f -empty -delete

     # Tarik objek yang hilang langsung dari remote origin tanpa merusak working tree
     git fetch origin $(git rev-parse --abbrev-ref HEAD)
     ```

### 10.3 Terjebak dalam "Detached HEAD" saat Transaksi Kritis
- **Gejala**: Pengembang membuat banyak commit penting, namun terminal menampilkan `HEAD detached at <commit-hash>`. Saat berganti cabang, commit tersebut tampak "hilang".
- **Penyebab**: HEAD menunjuk langsung ke hash commit tertentu, bukan ke referensi cabang di `refs/heads/*`.
- **Troubleshooting**:
  ```bash
  # 1. Jangan panik dan jangan lakukan git checkout sebelum membuat pointer
  # 2. Segera buat cabang darurat di posisi detached HEAD saat ini
  git branch recovery-branch-temp

  # 3. Sekarang aman berpindah ke cabang tujuan dan lakukan fast-forward / merge
  git checkout main
  git merge recovery-branch-temp

  # 4. Hapus cabang darurat setelah diverifikasi
  git branch -d recovery-branch-temp
  ```

---

## 11. Best Practices (Production Checklist)

Gunakan tabel checklist berikut sebagai standar audit teknis repositori level enterprise:

| Area Evaluasi | Parameter Konfigurasi / Kebijakan | Status Rekomendasi |
| :--- | :--- | :--- |
| **Keamanan** | GPG/SSH Commit Signing diaktifkan secara wajib (`git config commit.gpgsign true`) | **MANDATORY** |
| **Keamanan** | Server-side Hook memvalidasi zero-plaintext-secrets (AWS, Private Keys, OAuth Tokens) | **MANDATORY** |
| **Keamanan** | `receive.denyNonFastForwards = true` diaktifkan di seluruh cabang rilis pada server bare | **MANDATORY** |
| **Performa** | Mengaktifkan berkas indeks pelacak perubahan: `git config core.untrackedCache true` | **RECOMMENDED** |
| **Performa** | Mengaktifkan *File System Monitor* daemon: `git config core.fsmonitor true` | **RECOMMENDED** |
| **Performa** | Pipeline CI menggunakan `--filter=blob:none --depth=1` untuk efisiensi checkout | **MANDATORY** |
| **Manajemen Aset**| Format berkas biner > 5MB dialokasikan eksklusif melalui Git LFS via `.gitattributes` | **MANDATORY** |
| **Tata Kelola** | Kebijakan proteksi cabang (*Branch Protection Rules*) membatasi direct-push ke `main` | **MANDATORY** |
| **Pemeliharaan** | Rutinitas `git maintenance run --auto` terjadwal via Cron/Systemd di mesin CI/Server | **RECOMMENDED** |

---

## 12. Hands-on Practice

Target eksekusi: Simpan seluruh artefak praktikum ini di direktori `hands-on/m02/`.

### Langkah 1: Mempersiapkan Workspace
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

### Langkah 2: Rekonstruksi Commit Manual Menggunakan Git Plumbing
Tujuan: Memahami secara mendalam representasi internal Git tanpa antarmuka abstrak.

1. Buat direktori dan inisialisasi:
   ```bash
   mkdir plumbing-lab && cd plumbing-lab
   git init
   ```
2. Buat berkas dan simpan ke object database:
   ```bash
   echo "export const DB_PORT = 5432;" > config.js
   BLOB_ID=$(git hash-object -w config.js)
   echo "Blob ID: $BLOB_ID"
   ```
3. Registrasikan berkas ke index secara manual:
   ```bash
   git update-index --add --cacheinfo 100644 "$BLOB_ID" config.js
   ```
4. Materialisasi struktur Tree:
   ```bash
   TREE_ID=$(git write-tree)
   echo "Tree ID: $TREE_ID"
   ```
5. Buat commit beridentitas khusus:
   ```bash
   COMMIT_ID=$(echo "chore(config): set database port" | git commit-tree "$TREE_ID")
   echo "Commit ID: $COMMIT_ID"
   ```
6. Ikat pointer cabang utama:
   ```bash
   git update-ref refs/heads/main "$COMMIT_ID"
   git checkout main
   git log -p
   ```
7. Keluar kembali ke root direktori:
   ```bash
   cd ..
   ```

### Langkah 3: Purging Data Sensitif Riwayat Menggunakan Git-Filter-Repo
Tujuan: Melatih operasi perbaikan darurat saat terjadi kebocoran file kredensial secara permanen di masa lalu.

1. Siapkan repositori simulasi bencana:
   ```bash
   mkdir filter-lab && cd filter-lab
   git init
   git config user.name "Dev Engine"
   git config user.email "dev@corp.internal"

   # Commit pertama: Berkas normal
   echo "console.log('App Started');" > index.js
   git add index.js && git commit -m "feat: initial commit"

   # Commit kedua: Malapetaka (Credential Leak)
   echo "AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE123456" > credentials.env
   git add credentials.env && git commit -m "feat: add local environment config"

   # Commit ketiga: Pekerjaan berlanjut
   echo "console.log('API Service Ready');" >> index.js
   git add index.js && git commit -m "feat: implement service logic"

   # Developer mencoba menghapus berkas (NAMUN MASIH TERSIMPAN DI RIWAYAT!)
   git rm credentials.env
   git commit -m "fix: remove sensitive env file"
   ```
2. Verifikasi bahwa secret masih dapat diakses via history:
   ```bash
   git log --all --full-history -- "credentials.env"
   git checkout HEAD~1 -- credentials.env
   cat credentials.env
   git reset --hard HEAD
   ```
3. Lakukan bedah riwayat permanen menggunakan `git-filter-repo`:
   ```bash
   # Pastikan git-filter-repo terpasang
   git filter-repo --invert-paths --path credentials.env --force
   ```
4. Verifikasi bahwa file dan riwayatnya telah musnah total dari seluruh objek commit:
   ```bash
   git log --all --full-history -- "credentials.env"
   # Output harus KOSONG mutlak!
   ```
5. Keluar kembali ke root direktori:
   ```bash
   cd ..
   ```

### Langkah 4: Implementasi Partial Clone & Sparse-Checkout Simulation
Tujuan: Mengonfigurasi monorepo hemat bandwidth pada mesin lokal.

1. Siapkan repositori server upstream simulasi:
   ```bash
   git init --bare server-monorepo.git

   # Setup struktur monorepo di direktori sementara
   mkdir temp-seed && cd temp-seed
   git init
   mkdir -p services/auth services/billing services/analytics
   echo "Auth Code" > services/auth/main.go
   echo "Billing Code" > services/billing/main.go
   echo "Analytics Code" > services/analytics/main.go
   git add .
   git commit -m "feat(mono): structural foundation"
   git remote add origin ../server-monorepo.git
   git push origin master
   cd .. && rm -rf temp-seed
   ```
2. Eksekusi Blobless Clone dan Sparse-checkout hanya untuk domain `services/billing`:
   ```bash
   git clone --filter=blob:none --no-checkout server-monorepo.git local-billing-dev
   cd local-billing-dev

   # Aktifkan sparse checkout cone mode
   git sparse-checkout init --cone
   git sparse-checkout set services/billing

   # Checkout master
   git checkout master

   # Buktikan bahwa hanya services/billing yang terwujud di direktori
   ls -la
   ls -la services/
   # Hanya direktori services/billing/ yang ada di filesystem lokal!
   ```
3. Selesai. Kembali ke root direktori praktikum.
   ```bash
   cd ..
   ```

---

## 13. Exercise

### Latihan 1 (Level: Easy)
- **Tugas**: Buat skrip Bash yang menggunakan perintah `git cat-file` untuk menginspeksi jenis objek dan isi mentah dari referensi `HEAD` saat ini.
- **Kriteria Keberhasilan**: Skrip mencetak tipe objek commit, ukuran payload, commit author, dan hash root tree secara terpisah dengan mem-parsing output biner langsung.
- **Langkah Verifikasi**: Eksekusi skrip di dalam sembarang repositori Git yang valid dan bandingkan outputnya dengan `git log -1`.

### Latihan 2 (Level: Medium)
- **Tugas**: Konfigurasikan sebuah client-side hook `.git/hooks/commit-msg` yang memblokir pembuatan commit jika pesan tidak mencantumkan nomor tiket JIRA valid pada format: `[PROJECT-[0-9]+] <pesan-commit>`.
- **Kriteria Keberhasilan**: 
  - `git commit -m "fix broken login"` harus ditolak dengan *exit code* 1 dan mencetak instruksi koreksi.
  - `git commit -m "[CORE-8921] fix broken login authentication flow"` harus berhasil dengan *exit code* 0.

### Latihan 3 (Level: Hard)
- **Tugas**: Simulasikan insiden Git di mana referensi cabang utama terhapus secara tidak sengaja (`git branch -D main`). Tanpa menggunakan remote clone cadangan, pulihkan status cabang `main` beserta seluruh commit-nya persis sebelum insiden penghapusan terjadi.
- **Kriteria Keberhasilan**: Cabang `main` kembali muncul di daftar `git branch`, dan `git rev-parse main` menghasilkan hash commit paling mutakhir sebelum terhapus.
- **Langkah Verifikasi**: Manfaatkan `git reflog` atau pemindaian dangling objects via `git fsck --lost-found`.

---

## 14. Challenge

### Studi Kasus: Rekonstruksi Infrastruktur Git Korporat Pasca-Serangan Bencana dan Pelanggaran Lisensi

**Skenario Operasional**:
Anda adalah Principal Site Reliability Engineer pada sebuah perusahaan logistik unicorn. Repositori monorepo utama (`logistics-engine.git`) yang berukuran 80GB mengalami kontaminasi ganda yang kritis:

1. **Pelanggaran Lisensi**: Seorang developer mengimpor repositori pihak ketiga berlisensi GPLv3 murni ke dalam modul komersial internal repositori (`libs/proprietary-route-optimizer/`) 18 bulan yang lalu. Sebanyak 1.400 commit telah dibangun di atas kode tersebut. Lisensi korporat mewajibkan pemusnahan total jejak kode berlisensi GPLv3 dari seluruh riwayat *branch* dan *tag* agar repositori bersih secara hukum.
2. **Korupsi Reflog & Object Registry**: Seorang operator junior yang mencoba menyelesaikan masalah ini secara serampangan menjalankan perintah pembersihan agresif yang terhenti di tengah jalan karena server *out-of-memory*, meninggalkan puluhan referensi cabang dalam kondisi korup atau tidak sinkron dengan *packfiles*.

**Parameter & Batasan Eksekusi**:
- Repositori aktif digunakan oleh 800+ developer aktif. *Downtime maintenance window* yang dialokasikan oleh tim eksekutif hanya **2 jam**.
- Seluruh commit valid yang tidak melanggar lisensi wajib dipertahankan integritas metadata-nya (nama penulis asli, stempel waktu, dan relasi *parent* DAG).
- Seluruh *annotated tags* rilis produksi versi lama (`v1.0.0` sampai `v5.8.2`) harus tetap valid dan menunjuk ke *tree state* yang telah dibersihkan secara konsisten.
- Seluruh berkas di luar jalur modul pelanggaran tidak boleh berubah hash SHA-nya kecuali commit-commit yang terdampak restrukturisasi DAG secara langsung.

**Output yang Dituntut**:
Rancang dokumen rancangan arsitektur dan rangkaian skrip otomatisasi teruji untuk:
1. Mengidentifikasi, mengisolasi, dan memvalidasi batas kontaminasi modul GPLv3.
2. Menjalankan operasi pembersihan bedah non-interaktif berkecepatan tinggi.
3. Memverifikasi integritas DAG baru secara menyeluruh menggunakan audit matematis kriptografis.
4. Mendistribusikan status repositori yang telah direkonstruksi ke sistem upstream bare server baru tanpa menimbulkan tabrakan rekonsiliasi (*reconciliation divergence*) bagi mesin developer lokal.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Konseptual Dasar (5 Soal)

#### Soal 1
Di manakah Git menyimpan nama dari sebuah berkas yang sedang dilacak?
- A. Di dalam header *blob object*.
- B. Di dalam berkas indeks (`.git/index`) dan *tree object*.
- C. Di dalam *commit object*.
- D. Di dalam *loose object header*.

> **Jawaban: B**  
> **Penjelasan**: Objek *blob* Git bersifat agnostik terhadap metadata; *blob* hanya menyimpan deretan *byte* data murni. Nama berkas dan atribut izin eksekusi POSIX disimpan di dalam entri *Tree Object* atau di staging buffer (`.git/index`).

---

#### Soal 2
Apa fungsi utama berkas biner `.git/packed-refs`?
- A. Menyimpan berkas biner besar yang dikelola oleh Git LFS.
- B. Mengonsolidasikan referensi cabang dan tag dari berkas teks lepas di `.git/refs/` guna meminimalkan I/O *filesystem*.
- C. Menyimpan kompresi delta dari commit history.
- D. Mengarsipkan seluruh commit yang telah di-rebase.

> **Jawaban: B**  
> **Penjelasan**: Git mengonsolidasikan referensi cabang dan tag yang jarang bermutasi ke dalam sebuah berkas datar `.git/packed-refs` untuk mencegah pembengkakan jumlah berkas individual dan mengoptimalkan performa pembacaan referensi.

---

#### Soal 3
Bagaimana Git membedakan berkas yang executable (`chmod +x`) dan berkas biasa dalam penyimpanannya?
- A. Menulis tag `[EXEC]` di dalam blob.
- B. Menyimpan bit mask POSIX (`100755` vs `100644`) di dalam *Tree Object*.
- C. Menggunakan konfigurasi `.gitattributes` saja.
- D. Git tidak dapat membedakan atribut perizinan berkas POSIX.

> **Jawaban: B**  
> **Penjelasan**: Struktur internal *Tree Object* Git menyimpan *mode octal* standar POSIX untuk setiap entri, di mana `100755` menandakan berkas executable, `100644` berkas reguler, dan `040000` direktori.

---

#### Soal 4
Perintah plumbing manakah yang digunakan untuk menghitung hash SHA dan secara opsional menulis data mentah ke dalam database objek `.git/objects/`?
- A. `git write-tree`
- B. `git update-index`
- C. `git hash-object`
- D. `git commit-tree`

> **Jawaban: C**  
> **Penjelasan**: `git hash-object` membaca aliran berkas, menghasilkan nilai hash kriptografis SHA-nya, dan bila diberikan flag `-w`, akan menulis payload objek tersebut secara permanen ke direktori objek.

---

#### Soal 5
Pada Git LFS, apa isi data sesungguhnya dari berkas biner yang tersimpan di dalam Git Object DAG lokal?
- A. Data biner yang dikompresi dengan algoritma Zlib tingkat tinggi.
- B. Berkas pointer berbasis teks yang berisi hash SHA-256 dan metadata ukuran berkas biner asli.
- C. Berkas kosong 0-byte.
- D. Encrypted base64 string.

> **Jawaban: B**  
> **Penjelasan**: Git LFS mengganti file asli di pohon Git dengan berkas penunjuk teks kecil (*pointer file*) berukuran sekitar 130 byte yang menyimpan SHA-256 hash dari berkas biner yang disimpan secara terpisah di storage LFS backend.

---

### 15.2 Pertanyaan Tingkat Menengah (5 Soal)

#### Soal 6
Apa perbedaan mendasar antara opsi *Partial Clone* `--filter=blob:none` dan `--filter=tree:0`?
- A. `--filter=blob:none` hanya mengunduh commit tanpa tag; `--filter=tree:0` mengunduh seluruh data.
- B. `--filter=blob:none` (Blobless) mengunduh semua commit dan tree tetapi mengabaikan blob; `--filter=tree:0` (Treeless) hanya mengunduh commit saja dan mengunduh tree serta blob secara on-demand saat checkout.
- C. Keduanya identik, hanya alias sintaksis.
- D. `--filter=blob:none` menghapus riwayat masa lalu; `--filter=tree:0` mempertahankan riwayat 1 tahun terakhir.

> **Jawaban: B**  
> **Penjelasan**: Blobless clone (`blob:none`) mempertahankan seluruh commit dan pohon struktur direktori lokal sehingga operasi `git log` dan navigasi direktori instan, sedangkan Treeless clone (`tree:0`) membatasi unduhan hanya pada commit node, memaksa penarikan network I/O setiap kali berpindah struktur direktori pohon yang belum di-cache.

---

#### Soal 7
Mengapa eksekusi `git gc --aggressive` yang dijalankan di repositori monorepo besar dapat menyebabkan penurunan performa sementara selama proses berlangsung?
- A. Karena proses ini mengunci repositori secara eksklusif dan merekonstruksi ulang rantai *sliding-window delta compression* secara mendalam yang menghabiskan seluruh alokasi memori RAM dan core CPU.
- B. Karena perintah tersebut otomatis menghapus semua referensi lokal yang belum di-push.
- C. Karena Git mengunduh ulang seluruh packfile dari server remote.
- D. Karena Git membatalkan seluruh commit yang tidak bertanda tangan GPG.

> **Jawaban: A**  
> **Penjelasan**: Parameter `--aggressive` meningkatkan ukuran jendela inspeksi delta (*window depth*), memaksa kompresor Git menganalisis jutaan kemungkinan pasangan delta objek lama, yang menyebabkan beban komputasi CPU dan alokasi memori sangat tinggi secara masif.

---

#### Soal 8
Bagaimana cara kerja mekanisme filter `clean` dan `smudge` pada konfigurasi `.gitattributes`?
- A. `clean` dijalankan saat `git push`, `smudge` saat `git fetch`.
- B. `clean` mengubah konten berkas working tree sebelum disimpan ke staging area/index; `smudge` mengubah konten dari database objek sebelum disajikan ke working tree pengembang.
- C. `clean` membersihkan dangling commit; `smudge` mengompresi packfile.
- D. Keduanya adalah perintah internal perbaikan disk yang tidak dapat dikonfigurasi pengguna.

> **Jawaban: B**  
> **Penjelasan**: Filter driver bekerja di perbatasan antara *working tree* dan *index*. Filter `clean` mentransformasi data dari disk lokal ke index (misalnya menghapus spasi atau mengekstrak pointer LFS), sedangkan `smudge` mentransformasi data dari database objek kembali ke kondisi kerja di filesystem lokal saat proses checkout.

---

#### Soal 9
Dalam implementasi server-side hook `pre-receive`, argumen/masukan apakah yang dikirimkan oleh Git core engine ke skrip melalui *Standard Input* (STDIN)?
- A. Nama repositori dan path absolut direktori server.
- B. Satu atau beberapa baris teks dengan format: `<old-value-hash> <new-value-hash> <ref-name>`.
- C. Seluruh patch diff kompresi dari commit yang di-push.
- D. Payload token JSON JWT dari SSH Session.

> **Jawaban: B**  
> **Penjelasan**: Engine Git server mengeksekusi `pre-receive` dengan mengalirkan daftar mutasi referensi melalui STDIN, di mana setiap baris berisi commit hash lama, commit hash baru, dan nama referensi lengkap (misal: `refs/heads/main`).

---

#### Soal 10
Mengapa penggunaan `git filter-branch` sudah ditinggalkan dan dinyatakan *deprecated*, lalu digantikan oleh `git-filter-repo`?
- A. `git filter-branch` tidak mendukung SHA-256.
- B. `git filter-branch` mengeksekusi subshell Unix terpisah untuk setiap commit dan berkas yang diproses, membuatnya luar biasa lambat dan rawan merusak referensi metadata audit secara destruktif pada repositori non-trivial.
- C. `git filter-branch` adalah aplikasi berbayar proprietary.
- D. `git filter-branch` tidak dapat menghapus berkas yang ukurannya lebih dari 1GB.

> **Jawaban: B**  
> **Penjelasan**: `git filter-branch` mengandalkan pembuatan proses subshell shell POSIX per-commit yang menyebabkan *overhead* I/O parah pada repositori skala menengah-besar, serta memiliki kecacatan desain struktural yang kerap menghasilkan kerusakan *signature* dan *boundary cases* yang berbahaya.

---

### 15.3 Skenario Kasus Produksi (3 Soal)

#### Soal 11: Insiden False-Positive Secret Blocker
Pipeline push developer diblokir oleh skrip server-side `pre-receive` hook dengan pesan error:
`[SECURITY ERROR] Found pattern matching: AKIA[0-9A-Z]{16} in file tests/fixtures/mock_credentials.json`.
Developer berargumen bahwa string tersebut hanyalah data testing palsu untuk unit test *mocking* dan bukan kredensial riil. Sebagai Enterprise Platform Engineer, bagaimana Anda menyelesaikan kebuntuan operasional ini secara permanen tanpa melemahkan postur keamanan repositori?

- A. Memberikan hak kepada developer untuk menggunakan flag bypass `git push --no-verify`.
- B. Mematikan skrip *pre-receive* hook di server secara permanen.
- C. Mengimplementasikan sistem konfigurasi *allowlisting* berbasis hash berkas atau inline entropy verification (misalnya Shannon Entropy scoring + penanda berkas khusus `.sec-ignore`) yang diverifikasi langsung di dalam logika `pre-receive` hook.
- D. Memerintahkan developer menghapus seluruh unit test yang berkaitan dengan keamanan.

> **Jawaban: C**  
> **Penjelasan**: Flag `--no-verify` hanya mengabaikan *client-side hook* dan tidak berpengaruh terhadap *server-side pre-receive hook*. Solusi arsitektural yang benar adalah membangun mekanisme tata kelola pengecualian terkontrol di dalam engine pre-receive hook (misal dengan entropy checking atau berkas referensi pengecualian bertanda tangan digital).

---

#### Soal 12: Broken Remote Monorepo Synchronization
Sebuah tim CI/CD melaporkan bahwa setelah repositori monorepo dimigrasikan sebagian ke Git LFS, runner Kubernetes mereka mengalami kegagalan *intermittent* dengan pesan:
`Error downloading object: smudgeblob <hash>: LFS: [401] Unauthorized`.
Akan tetapi, operasi `git clone` reguler menggunakan kredensial yang sama berhasil mengunduh kode teks biasa. Di manakah letak kegagalan konfigurasi infrastruktur ini?

- A. Runner CI kehabisan ruang disk lokal.
- B. Token autentikasi SSH/HTTPS runner hanya memiliki izin baca ke repositori Git inti, tetapi tidak memiliki izin atau *header routing* ke layanan *Storage API Endpoint* Git LFS backend (misal: S3 Presigned URL generator atau LFS Auth Token endpoint).
- C. Format commit developer rusak.
- D. Git LFS tidak mendukung sistem operasi Linux pada Kubernetes container.

> **Jawaban: B**  
> **Penjelasan**: Git LFS menggunakan protokol API batch terpisah dari protokol transfer Git inti (Smart HTTP / SSH). Galat HTTP 401 membuktikan bahwa negosiasi transfer Git berhasil mengunduh pointer berkas teks, namun saat perintah *smudge filter* mencoba mengunduh payload aktual dari server LFS, kredensial runner ditolak oleh endpoint otorisasi storage backend.

---

#### Soal 13: Divergent Subtree Disaster
Sebuah komponen pustaka bersama (`libs/telemetry`) dikelola menggunakan strategi `git subtree`. Seorang teknisi mengeksekusi:
`git subtree pull --prefix=libs/telemetry git@upstream:libs/telemetry.git main --squash`
dan mengalami konflik besar yang tidak dapat diselesaikan secara otomatis, diikuti rusaknya struktur direktori root karena kode terduplikasi di luar prefix folder. Langkah mitigasi arsitektur terbaik untuk memulihkan dan mencegah insiden ini berulang adalah:

- A. Menghapus direktori `.git` dan mengkloning ulang.
- B. Menghentikan proses rekonsiliasi via `git merge --abort`, memeriksa apakah flag `--prefix` tepat sama persis dengan jalur direktori eksisting, dan mempertimbangkan migrasi ke Git Submodule atau monorepo murni jika dependensi memerlukan isolasi siklus rilis yang independen dan deterministik.
- C. Menjalankan `git push --force` ke remote server.
- D. Mengubah izin berkas direktori `libs/telemetry` menjadi *read-only*.

> **Jawaban: B**  
> **Penjelasan**: Jika parameter `--prefix` pada `git subtree` salah satu karakter saja, Git akan memperlakukan operasi tersebut sebagai penggabungan ke root direktori yang memicu kekacauan pohon berkas. Menghentikan transaksi dengan `git merge --abort` adalah langkah mitigasi langsung yang paling aman untuk mengembalikan pointer ke status konsisten.

---

## 16. Summary

Penguasaan Git pada tataran enterprise membutuhkan pergeseran paradigma: dari sekadar memperlakukan Git sebagai alat bantu pencatat versi (*porcelain-level thinking*) menjadi mengelolanya sebagai sistem penyimpanan data terdistribusi berbasis konten kriptografis (*plumbing & architectural thinking*). 

Pada skala monorepo dengan ratusan insinyur dan jutaan aset, kegagalan tata kelola Git berdampak langsung terhadap reliabilitas infrastruktur, biaya bandwidth cloud, dan kecepatan delivery perangkat lunak. Tiga pilar utama arsitektur repositori modern yang telah kita bedah:
1. **Efisiensi Skala Penyimpanan**: Memisahkan kode logika berukuran kecil dari biner raksasa melalui Git LFS, serta mengombinasikan *Blobless Clones* dengan *Sparse-Checkout Cone Mode* guna memangkas latensi transfer data dan I/O filesystem.
2. **Keamanan & Tata Kelola Deterministik**: Mencegah insiden keamanan dan pelanggaran konvensi secara absolut pada level remote bare server melalui *Pre-Receive Governance Engine*, alih-alih mengandalkan kepatuhan klien yang rapuh.
3. **Resiliensi & Pemulihan Mutlak**: Kemampuan mengaudit, membedah, dan merekonstruksi Directed Acyclic Graph (DAG) menggunakan antarmuka *plumbing* dan perkakas modern seperti `git-filter-repo` saat menghadapi korupsi data atau kebocoran informasi berisiko tinggi.