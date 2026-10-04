# Kurikulum Rekayasa Perangkat Lunak Enterprise: Git & GitHub
**Kategori:** 01-Core-Foundations  
**Bab 09:** Materi Lanjutan  
**Modul 02:** Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik pada level Staff/Principal Engineer diharapkan mampu:
- Mengonstruksi dan merekonstruksi struktur basis data *Content-Addressable Storage* Git secara manual menggunakan perintah *plumbing* (`hash-object`, `mktree`, `commit-tree`, `update-ref`).
- Mendiagnosis serta mereparasi kerusakan integritas Directed Acyclic Graph (DAG) dan *object database* menggunakan `git fsck`, `git reflog`, dan manipulasi berkas `.git/objects`.
- Merancang dan mengeksekusi strategi pengelolaan monorepo skala petabyte/multi-gigabyte menggunakan kombinasi *Git Partial Clones* (Blobless/Treeless Clones), *Sparse-Checkout* (Cone Mode), dan arsitektur *Scalar*.
- Mengimplementasikan tata kelola keamanan enterprise melalui *cryptographic commit signing* (GPG/SSH/X.509), Branch Protection Rulesets tingkat lanjut, serta audit jejak riwayat menggunakan `git-filter-repo` untuk membersihkan artefak sensitif/rahasia tanpa merusak hash relasional yang valid.
- Merumuskan arsitektur pipeline GitOps berbasis *trunk-based development* dengan implementasi GitHub Actions Merge Queue untuk mengeliminasi *semantic merge conflicts* pada frekuensi merge tinggi.

---

## 2. Prerequisite
Untuk menyerap materi ini secara optimal, peserta wajib menguasai:
- **Git Fundamentals**: Model 3-Trees (Working Directory, Staging Area/Index, HEAD), percabangan dasar, manipulasi remote, serta resolusi konflik manual.
- **Sistem Operasi & Shell**: Kemampuan navigasi Linux/Unix shell lanjutan, pemahaman *file descriptors*, kompresi (Zlib/DEFLATE), kalkulasi hash cryptographic (SHA-1, SHA-256), serta penanganan permission file (POSIX filesystem permissions: 100644, 100755, 040000).
- **Struktur Data Dasar**: Pemahaman mendalam mengenai Graf Asiklik Terarah (*Directed Acyclic Graph* / DAG), Hash Tree (*Merkle Tree*), dan Directed Trees.

---

## 3. Concept & Internal Architecture

Git pada hakikatnya bukanlah sebuah VCS (*Version Control System*) monolitik tradisional berorientasi delta (seperti SVN atau CVS), melainkan sebuah **Content-Addressable Object Store** yang dibungkus oleh antarmuka *VCS Porcelain*.

```
+-----------------------------------------------------------------------+
|                    PORCELAIN LAYER (User Facing)                      |
|  git add | git commit | git checkout | git branch | git merge | ...   |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
|                   PLUMBING LAYER (Engine Internals)                   |
| hash-object | cat-file | mktree | commit-tree | update-ref | rev-list |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
|                 OBJECT DATABASE (Content-Addressable)                 |
|  .git/objects/  -->  Loose Objects (zlib deflated) & Packfiles (.pack)|
|                                                                       |
|   +----------+        +----------+        +----------+    +-------+   |
|   |   BLOB   |  <---  |   TREE   |  <---  |  COMMIT  | <--|  TAG  |   |
|   | Payload  |        | Metadata |        | Merkle   |    | Crypto|   |
|   | Contents |        | & Modes  |        | Parent   |    | Meta  |   |
|   +----------+        +----------+        +----------+    +-------+   |
+-----------------------------------------------------------------------+
```

### 3.1 Struktur Objek Fundamental Git
Setiap entitas dalam Git disimpan di dalam folder `.git/objects/` sebagai objek yang diidentifikasi oleh checksum (standar: 160-bit SHA-1, modern: 256-bit SHA-256).

Format penyimpanan objek mentah (*uncompressed*) selalu mematuhi struktur:
$$\text{Header} = \langle \text{tipe\_objek} \rangle + \text{" "} + \langle \text{ukuran\_dalam\_bytes} \rangle + \text{"\textbackslash 0"}$$
$$\text{Payload} = \langle \text{isi\_konten} \rangle$$
$$\text{Total Object} = \text{zlib\_compress}(\text{Header} + \text{Payload})$$

Terdapat 4 jenis objek primitif:
1. **Blob**: Menyimpan data mentah file murni. Blob **tidak** menyimpan nama file, atribut permission, ataupun timestamp.
2. **Tree**: Menyimpan representasi direktori (daftar entri yang memetakan file modes, nama file/direktori, dan pointer SHA-1 ke blob atau tree anak).
3. **Commit**: Menyimpan pointer ke Tree *root* dari proyek pada titik waktu tersebut, pointer ke satu atau lebih *parent commit* (nol untuk root commit, satu untuk normal, dua atau lebih untuk merge commit), metadata komiter & author (nama, email, epoch timestamp, timezone offset), serta pesan komit.
4. **Annotated Tag**: Objek mirip komit yang menunjuk secara permanen ke objek komit tertentu, disertai metadata pembuat tag, timestamp, pesan, dan opsional tanda tangan kriptografis (GPG/SSH).

### 3.2 Indeks Git (`.git/index`)
File `.git/index` adalah berkas biner terurut yang bertindak sebagai *cache layer* antara repositori lokal (direktori objek) dan *working tree*. Setiap entri indeks memuat atribut *stat* file Linux (mtime, ctime, inode, file size, UID, GID) bersama dengan hash SHA objek blob yang relevan dan status stage (0 untuk kondisi bersih, 1/2/3 saat terjadi merge conflict). Berkat file indeks, Git dapat mengetahui instan file mana yang mengalami modifikasi tanpa perlu mengurai ulang seluruh pohon direktori.

### 3.3 Loose Objects vs. Packfiles
- **Loose Objects**: Format default saat objek baru diciptakan. Objek dikompresi individual menggunakan zlib dan disimpan di subdirektori berdasar 2 karakter pertama SHA, diikuti 38 karakter sisa nama file (contoh: `.git/objects/4b/825dc642cb6eb9a060e54bf8d69288fbee4904`).
- **Packfiles (`.pack`) & Indexes (`.idx`)**: Ketika jumlah loose objects melewati batas ambang (*threshold*) atau saat `git gc` / `git push` dijalankan, Git mengemas ribuan loose objects menjadi satu file pack biner raksasa. Git memanfaatkan kompresi delta yang sangat efisien (*sliding-window compression*), di mana versi-versi file yang berdekatan hanya disimpan perbedaan perubahannya (*deltas*), dan `.idx` mengizinkan akses acak (*random access*) secara $O(\log N)$ via Binary Search.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional (Porcelain Only) | Pendekatan Enterprise Core (Plumbing & Internal Mastery) |
| :--- | :--- | :--- |
| **Penyelesaian Masalah** | Bergantung pada `git reset --hard` atau kloning ulang repositori ketika terjadi corrupt/konflik berat. | Diagnostik manual via `git cat-file`, `git fsck`, pemulihan tree dangling, dan bedah state index. |
| **Skalabilitas Repositori** | Repositori raksasa (Monorepo > 50 GB) menyebabkan `git status` dan `git fetch` freeze / memakan OOM (*Out of Memory*). | Implementasi *Blobless Clone* (`--filter=blob:none`), *Sparse-Checkout cone mode*, dan optimasi I/O via *Scalar*. |
| **Integritas Rantai Pasok (Supply Chain)** | Mengasumsikan identitas author dari header teks `user.name` & `user.email` yang rentan spoofing. | Enforcement penandatanganan kriptografis *commit-level* berbasis SSH/GPG dengan integrasi *Branch Rulesets* GitHub. |
| **Audit Jejak Rahasia** | Menghapus rahasia/secret melalui komit perbaikan (komit baru), membiarkan secret abadi di DAG history. | Rewrite riwayat level rendah (*content rewriting*) menggunakan `git-filter-repo` dan sanitasi garbage collection instan. |

---

## 5. How (Workflow Detail)

### 5.1 Manual Reconstruction of Commit Object via Plumbing APIs
Alur berikut menunjukkan bagaimana porcelain `git add` dan `git commit` diurai ke dalam primitive pipeline:

```
[Plain Text / File Content]
       |
       v  1. git hash-object -w <file>
[Blob Object Created in .git/objects/]
       |
       v  2. git update-index --add --cacheinfo <mode> <sha> <filename>
[.git/index (Staging Binary Updated)]
       |
       v  3. git write-tree
[Tree Object Created with Hierarchy]
       |
       v  4. git commit-tree <tree-sha> -p <parent-sha> -m "Commit Message"
[Commit Object Linked in DAG]
       |
       v  5. git update-ref refs/heads/<branch> <commit-sha>
[Branch Reference Pointers Advanced]
```

### 5.2 Deep-Branch Surgery: Interactive Rebase with Topology Preservation
Dalam enterprise development, penggabungan fitur jangka panjang sering kali memerlukan rekonsiliasi riwayat tanpa mengubah topologi merge commits. Eksekusi ini menggunakan parameter `--rebase-merges` (`-r`):

```bash
# Melakukan rebase interaktif dengan menjaga bentuk percabangan merge
git rebase -i -r --onto target-branch upstream-branch feature-branch
```

---

## 6. Analogy & Diagram ASCII

### 6.1 Analogi: Git Object Store sebagai Sistem Penyimpanan Arsip Kriptografis
Bayangkan sistem arsip dokumen fisik kedap udara:
- **Blob**: Fotokopi selembar kertas bertuliskan naskah, tanpa judul, tanpa map. Diberi stiker sidik jari digital (SHA) di luarnya.
- **Tree**: Sebuah map berlabel yang di dalamnya berisi daftar inventaris stiker sidik jari lembaran fotokopi (Blob) dan map-map subdirektori lain (Tree anak).
- **Commit**: Berita Acara tertanggal yang ditandatangani kurator, menyatakan: *"Pada timestamp $T$, map proyek identik dengan Sidik Jari Tree $X$, yang merupakan kelanjutan langsung dari Berita Acara Sidik Jari $Y$"*.
- **Branch Reference**: Sebuah sticky note kuning bertuliskan `main` yang menempel di sampul luar salah satu Berita Acara (Commit). Saat ada Berita Acara baru, kita cukup mencabut sticky note tersebut dan menempelkannya ke Berita Acara yang paling baru.

### 6.2 Visualisasi DAG dan Merkle Tree State
```
.git/refs/heads/main
       |
       v
+-------------------------------------------------------+
| Commit: e8f3a9...                                     |
| Author: Staff Engineer <staff@enterprise.internal>   |
| Parent: c2d4e1...                                     |
| Tree:   a1b2c3... ----------------------------------+ |
+---------------------------------------------------|---+
                                                    |
                                                    v
                   +---------------------------------------------------+
                   | Tree: a1b2c3... (Root Directory)                  |
                   | 100644 blob 3e4f5a...    README.md                |
                   | 100755 blob 9a8b7c...    deploy.sh                |
                   | 040000 tree 8f1e2d...    src/                     |
                   +--------------------------------+------------------+
                                                    |
                                                    v
                   +---------------------------------------------------+
                   | Tree: 8f1e2d... (src Directory)                   |
                   | 100644 blob 5c4d3b...    kernel.go                |
                   +--------------------------------+------------------+
                                                    |
                                                    v
                   +---------------------------------------------------+
                   | Blob: 5c4d3b...                                   |
                   | package main\nfunc Init() { ... }                 |
                   +---------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Membangun Komit Murni Menggunakan Plumbing
Langkah-langkah berikut membuat file dan commit tanpa menyentuh perintah `git add` maupun `git commit`:

```bash
# Inisialisasi repositori kosong
mkdir plumbing-demo && cd plumbing-demo
git init

# 1. Simpan konten mentah ke Object Store (Menghasilkan BLOB)
PAYLOAD="fmt.Println(\"Internal Plumbing Execution\")"
BLOB_SHA=$(printf "%s" "$PAYLOAD" | git hash-object -w --stdin)
echo "Blob Hash: $BLOB_SHA"

# 2. Catat BLOB ke dalam Index (Staging Area)
git update-index --add --cacheinfo 100644 "$BLOB_SHA" "main.go"

# 3. Bentuk TREE dari Index
TREE_SHA=$(git write-tree)
echo "Tree Hash: $TREE_SHA"

# 4. Buat COMMIT objek yang menunjuk ke Tree tersebut
COMMIT_SHA=$(echo "feat: core architecture plumbing init" | git commit-tree "$TREE_SHA")
echo "Commit Hash: $COMMIT_SHA"

# 5. Arahkan pointer HEAD branch main ke commit baru
git update-ref refs/heads/main "$COMMIT_SHA"
git symbolic-ref HEAD refs/heads/main

# Verifikasi status pohon
git log -p
```

### 7.2 Practical Example: Enterprise Monorepo Sparse Optimization Script
Skrip otomatisasi untuk konfigurasi kloning repositori berskala enterprise (>20 GB) dengan konsumsi bandwidth dan disk minimal:

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_URL="git@github.com:enterprise-corp/monorepo.git"
TARGET_DIR="monorepo-core"

echo "=== Memulai Enterprise Optimized Sparse Clone ==="

# 1. Clone dengan filter blobless (metadata & tree diunduh, blob ditarik on-demand)
git clone --filter=blob:none --no-checkout "$REPO_URL" "$TARGET_DIR"
cd "$TARGET_DIR"

# 2. Aktifkan sparse-checkout dengan mode Cone (Algoritma pencocokan prefix sangat cepat)
git sparse-checkout init --cone

# 3. Definisikan batas direktori lingkup domain microservice kita saja
git sparse-checkout set services/payment-gateway libs/common-auth

# 4. Konfigurasi internal Git engine untuk performa ekstrem pada repositori besar
git config core.fsmonitor true
git config core.untrackedCache true
git config maintenance.auto false
git config feature.manyFiles true

# 5. Check out cabang target
git checkout main

echo "=== Repositori siap digunakan dengan I/O optimal ==="
du -sh .git
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Kebocoran Master Key Kriptografi dan Degradasi Performa pada FinTech Monorepo (50 GB)
* **Konteks**: Sebuah institusi finansial global mengoperasikan monorepo sebesar 50 GB yang diakses 1.500 engineer.
* **Insiden**:
  1. Seorang engineer secara tidak sengaja mengompilasi dan meng-commit *file private-key produksi* (`master-signer.key`, 2 KB) ke dalam branch `main`. File tersebut telah berada di dalam riwayat commit selama 4 bulan dan telah ditumpuk oleh 12.000 komit baru.
  2. Beban cloning CI runner melonjak: rata-rata fresh clone memakan waktu 48 menit, menghabiskan 85% bandwidth internal network infrastructure.
* **Strategi Mitigasi Arsitektur**:
  1. **Purging Rahasia**: Menggunakan `git-filter-repo` (Python-based engine, bukan `git filter-branch` lama yang lambat dan merusak metadata).
     ```bash
     # Install engine
     pip install git-filter-repo

     # Backup total repositori sebelum operasi destruktif
     git clone --mirror git@github.com:fintech/monorepo.git monorepo-backup.git

     # Hapus seluruh eksistensi private key dari setiap commit dan tag di dalam riwayat
     git filter-repo --invert-paths --paths-segment master-signer.key --force

     # Force-push mirror baru ke GitHub Enterprise Server
     git push origin --force --all
     git push origin --force --tags
     ```
  2. **Eliminasi Bloat Binary**: Ditemukan pula adanya binary artifact `build/` (.jar/.so) historis sebesar 32 GB. Dikonversi menggunakan `git-filter-repo --strip-blobs-bigger-than 10M`.
  3. **Arsitektur CI/CD Blobless**:
     CI diubah dari `git clone` penuh menjadi:
     ```yaml
     - name: Checkout Code
       uses: actions/checkout@v4
       with:
         fetch-depth: 1
         filter: 'blob:none'
     ```
* **Hasil**:
  - Ukuran base `.git/objects` susut dari 50 GB ke 1.8 GB.
  - Clone time pada pipeline CI/CD turun dari 48 menit menjadi 32 detik.
  - Audit kepatuhan PCI-DSS menyatakan file kunci telah tereliminasi sepenuhnya dari seluruh cabang dan reflog internal.

---

## 9. Trade-offs

| Pendekatan / Fitur | Trade-off Positif (Keuntungan) | Trade-off Negatif (Konsekuensi & Biaya) | Skenario Rekomendasi |
| :--- | :--- | :--- | :--- |
| **Monorepo (Single Repo Scale)** | Single source of truth, kemudahan cross-project refactoring, dependensi atomic. | Memerlukan tooling khusus (*Scalar, Sparse-checkout*), risiko merge congestion tinggi, beban clone berat. | Organisasi besar dengan koordinasi dependensi internal yang ketat (e.g., Google, Meta). |
| **Polyrepo (Multi-Repo Scale)** | Isolasi failure domain, boundary akses granular, tooling bawaan Git beroperasi optimal ($O(1)$). | *Dependency hell*, perubahan API multi-repo memerlukan orkestrasi PR terkoordinasi yang rawan *drift*. | Organisasi dengan arsitektur microservices yang terdistribusi secara otonom. |
| **Merge Commits (True Merge)** | Mempertahankan keaslian topologi historis, tidak merusak cryptographic signature asli komit. | Riwayat commit menjadi nonlinear (*diamond problem*), mempersulit visualisasi dan teknik `git bisect`. | Branch integrasi utama (misal: staging -> production, release branches). |
| **Interactive Rebase (Fast-Forward)** | Histori linear yang rapi, mempermudah pelacakan regresi dengan `git bisect` dan rollback instan. | Mengubah Commit SHA (hash rewrite), merusak signatur kriptografi lama, berbahaya jika dieksekusi di public branch. | Branch lokal privat sebelum membuka Pull Request ke trunk. |
| **Git LFS (Large File Storage)** | Mencegah ukuran repositori membengkak dengan memindahkan binary besar ke object storage terpisah (S3). | Kompleksitas ketergantungan server LFS, biaya storage ganda, rentan *dangling pointers* jika LFS server down. | Proyek dengan aset tak-terkompresi (model AI/ML `.onnx`, aset grafis game `.psd`, dsb.). |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Broken Detached HEAD State Setelah Operasi Rebase Abort
* **Gejala**: Engineer berada di `(HEAD detached at d82b1c)`, perubahan lokal tampak hilang saat mencoba checkout ke branch asal.
* **Root Cause**: Rebase gagal diselesaikan secara normal, pengguna menjalankan checkout tanpa mengintegrasikan commit yang dibuat di anonymous state.
* **Resolusi**:
  ```bash
  # 1. Lacak Commit SHA terakhir yang valid menggunakan reflog
  git reflog

  # Output identifikasi:
  # d82b1c1 HEAD@{0}: commit: fix: critical logic
  # 9a7b6c5 HEAD@{1}: rebase (start): checkout origin/main

  # 2. Amankan commit terapung tersebut ke dalam branch pemulihan
  git branch recovery-branch d82b1c1

  # 3. Pindah kembali ke branch fitur dan lakukan merge terkontrol
  git checkout feature-branch
  git merge recovery-branch
  ```

### 10.2 Corrupt Loose Object Detection (`error: object file ... is empty`)
* **Gejala**: Operasi Git gagal dengan `fatal: loose object 4b825dc... is corrupt`.
* **Root Cause**: Server/komputer mati tiba-tiba (*kernel panic/power loss*) saat penulisan ke disk sebelum metadata disinkronisasi ke persistent storage, menghasilkan file 0-byte di `.git/objects/`.
* **Resolusi**:
  ```bash
  # 1. Cari file corrupt
  find .git/objects/ -type f -empty

  # 2. Hapus objek 0-byte tersebut
  find .git/objects/ -type f -empty -delete

  # 3. Jalankan fsck untuk melihat objek dangling atau hilang
  git fsck --full

  # 4. Tarik objek yang hilang langsung dari remote repository
  git fetch origin $(git rev-parse --abbrev-ref HEAD) --refetch
  ```

---

## 11. Best Practices (Production Checklist)

### Checklist Konfigurasi Repositori Enterprise

- [ ] **Commit Signing Verification**: Seluruh commit wajib ditandatangani menggunakan SSH/GPG key yang terverifikasi.
  ```bash
  git config --global user.signingkey "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5..."
  git config --global gpg.format ssh
  git config --global commit.gpgsign true
  ```
- [ ] **GitHub Ruleset Enforcement**:
  - Aktifkan *"Require a pull request before merging"* dengan minimal 2 approved reviews dari Code Owners.
  - Aktifkan *"Require status checks to pass"* dengan mode Strict (branch harus up-to-date terhadap branch target sebelum di-merge).
  - Aktifkan *"Require signed commits"*.
  - Aktifkan *"Require linear history"* jika organisasi menganut Rebase/Squash paradigm.
- [ ] **Garbage Collection Policy**:
  - Konfigurasi pembersihan otomatis loose objects:
    ```bash
    git config --global gc.auto 6700
    git config --global gc.pruneExpire "14.days.ago"
    ```
- [ ] **Modern Git Transport & Diff Engine**:
  - Gunakan algoritma diff Histogram untuk resolusi perubahan kode struktural yang jauh lebih cerdas dibanding Myers standard:
    ```bash
    git config --global diff.algorithm histogram
    ```

---

## 12. Hands-on Practice

Buat seluruh file praktikum di dalam path: `hands-on/m02/`

### Skenario: Investigasi Korupsi DAG & Konstruksi Commit Tingkat Rendah

#### Langkah 1: Persiapan Workspace
```bash
mkdir -p hands-on/m02/internals-lab
cd hands-on/m02/internals-lab
git init
```

#### Langkah 2: Eksplorasi Struktur Objek Manual
```bash
# Buat file teks
echo "Enterprise Architecture Payload System" > data.txt

# Buat blob objek dan tangkap hash
HASH=$(git hash-object -w data.txt)
echo "Generated SHA: $HASH"

# Verifikasi keberadaan file di sistem berkas internal
DIR_PREFIX=${HASH:0:2}
FILE_SUFFIX=${HASH:2}
ls -la .git/objects/$DIR_PREFIX/$FILE_SUFFIX

# Dekode isi objek secara langsung menggunakan zlib decompressor
# (Verifikasi bahwa format raw berisi header dan payload)
python3 -c "import zlib; print(zlib.decompress(open('.git/objects/$DIR_PREFIX/$FILE_SUFFIX', 'rb').read()))"
```

#### Langkah 3: Rekayasa Manipulasi Reflog
```bash
# Tambah commit normal
git add data.txt
git commit -m "feat: initial commit"

# Ubah isi data dan commit lagi
echo "Second Iteration" >> data.txt
git commit -am "feat: second iteration"

# Sengaja lakukan hard reset ke state awal
git reset --hard HEAD~1

# Buktikan bahwa commit "Second Iteration" masih tersimpan di Object Database
git fsck --lost-found
git reflog
```

---

## 13. Exercise

### Level Easy: Manual SHA Validation
Ambil sebuah file teks bebas. Hitung SHA-1 hash menggunakan utility Linux standar (`sha1sum`) secara manual dengan menyertakan null-byte header Git (`blob <size>\0<content>`). Pastikan output hash identik 100% dengan luaran `git hash-object <file>`.

### Level Medium: Forensic Tree Recovery
Sebuah branch telah terhapus secara permanen via `git branch -D production-release`. Reflog untuk branch tersebut telah kedaluwarsa/terhapus (`git reflog expire --expire=now --all`). Buatlah skrip shell yang mengurai seluruh dangling tree dan dangling commit dari direktori `.git/objects` menggunakan kombinasi `git fsck --lost-found`, lalu otomatis mengidentifikasi dangling commit mana yang memiliki commit message berawalan `"prod:"` untuk kemudian di-restore ke branch baru.

### Level Hard: Merge-Conflict Arbiter via Lower Plumbing
Simulasikan skenario *three-way merge conflict* tanpa menggunakan perintah `git merge`. 
1. Siapkan satu ancestor commit ($O$), lalu buat dua percabangan yang memodifikasi baris file yang sama ($A$ dan $B$).
2. Baca file indeks yang sedang konflik secara programmatic.
3. Ekstraksi ketiga stage konflik (Stage 1: Ancestor, Stage 2: Target, Stage 3: Source) menggunakan `git checkout-index --stage=all`.
4. Rekonsiliasi file menggunakan utilitas tingkat sistem operasi `merge` atau `diff3`, perbarui index menggunakan `git update-index`, dan selesaikan commit secara manual menggunakan `git write-tree` dan `git commit-tree`.

---

## 14. Challenge

### Studi Kasus: "The Phantom Detonation & Ghost Pipeline"
**Skenario**:
Anda dipekerjakan sebagai Principal Site Reliability & Core Infrastructure Engineer di sebuah unicorn FinTech. Tim rilis melaporkan kepanikan: 
1. Repositori monorepo backend mereka mengalami error kritis saat checkout di server CI: `fatal: bad tree object <SHA>`. Pipeline deployment terhenti total di seluruh global region.
2. Diduga kuat ada salah satu engineer senior yang mematikan paksa laptopnya saat sedang melakukan git rewrite (`git rebase` / manual pack) yang terhubung ke server remote via sync script tidak standar, mengakibatkan salah satu objek Tree di remote GitHub Enterprise rusak (terbaca sebagai corrupted zero-byte object).
3. Repositori remote melarang force-push ke branch utama (`main`), namun GitHub Enterprise Administrator memberikan Anda akses SSH tingkat tinggi ke repositori *bare* fisik di instance server (`/data/git/repositories/enterprise/monorepo.git`).

**Instruksi Misi**:
- Identifikasi commit dan path direktori persis yang ditunjuk oleh `bad tree object` tersebut tanpa bergantung pada `git pull` (karena clone/fetch gagal).
- Rekonstruksi struktur tree yang hilang dari salinan lokal developer lain yang masih memiliki state direktori tersebut.
- Modifikasi objek biner tree pengganti secara manual di bare repository, validasi konsistensi kriptografis Merkle root DAG, dan pulihkan kondisi repositori ke status clean tanpa ada riwayat komit yang hilang (*zero loss of business logic history*).
- Buat *Post-Mortem Root-Cause Analysis* (RCA) teknis formal beserta rekomendasi preventif arsitektur.

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic
1. Apa struktur header biner pasti yang disematkan Git sebelum melakukan kalkulasi hash SHA-1 pada sebuah Blob objek?
2. Bagaimana cara kerja Git membedakan sebuah file biasa dengan permission `644` dan file executable dengan permission `755` jika kedua file memiliki isi string teks yang sama persis?
3. Sebutkan perbedaan fundamental antara pointer *Reference* (`refs/heads/foo`) dan *Symbolic Reference* (`HEAD`)!
4. Apa yang membedakan format penyimpanan data antara *Loose Object* dan *Packfile*?
5. Mengapa perintah `git checkout -b new-branch` berjalan instan ($O(1)$) tanpa peduli seberapa besar ukuran source code di working tree?

### 5 Pertanyaan Intermediate
6. Jelaskan skenario di mana dua commit berbeda menghasilkan nilai Hash SHA-1 *Tree root* yang identik!
7. Pada operasi `git rebase -i`, bagaimana Git memanfaatkan file instruksi *git-rebase-todo* dan state `.git/rebase-merge/` secara internal?
8. Mengapa Git secara default menolak operasi `git push` yang bukan berstatus *fast-forward*, dan kalkulasi graf apa yang dijalankan remote engine untuk memvalidasi hal tersebut?
9. Jelaskan perbedaan mendasar mekanisme kerja antara *Partial Clone blobless* (`--filter=blob:none`) dan *Partial Clone treeless* (`--filter=tree:0`) dari sisi konsumsi bandwidth jaringan dan latensi operasi `git checkout`!
10. Bagaimana `git-filter-repo` dapat memproses pembersihan histori ribuan kali lebih cepat dibanding `git filter-branch` bawaan legacy Git?

### 3 Skenario Kasus Produksi
11. **Skenario Kasus A**: Pengembang A melakukan merge dari `feature-A` ke `develop`. Bersamaan dengan itu, Pengembang B melakukan merge dari `feature-B` ke `develop`. CI/CD di kedua PR hijau sempurna. Namun, setelah keduanya masuk ke `develop`, build branch utama langsung patah (*compile error*). Peristiwa apa yang terjadi di sini dari perspektif DAG, dan bagaimana implementasi GitHub Merge Queue mencegah bencana ini?
12. **Skenario Kasus B**: Server audit keamanan mendeteksi bahwa SSH Private Key milik deployment engineer bocor. Namun kunci tersebut telah digunakan untuk menandatangani ratusan commit pada branch rilis LTS yang sudah berjalan 6 bulan. Rancang mitigasi: Bagaimana prosedur rotasi kunci tanpa menyebabkan invalidasi (*cryptographic signature breach*) pada riwayat commit lama di antarmuka GitHub Enterprise?
13. **Skenario Kasus C**: Pada repositori monorepo dengan 200.000 file, eksekusi `git status` memakan waktu 45 detik di perangkat workstation macOS engineer. Jelaskan secara teknis penyebab bottleneck I/O tersebut pada layer sistem operasi, dan susun konfigurasi Git spesifik yang dapat memangkas waktu eksekusi kembali di bawah 1 detik!

---

## 16. Summary
- Git adalah **Content-Addressable Storage** terdesentralisasi yang mengimplementasikan **Merkle DAG** untuk melacak status snapshot, bukan perbedaan mutasi diferensial.
- Hirarki objek Git dibangun dari 4 tipe dasar: **Blob** (konten mentah), **Tree** (direktori & metadata permissions), **Commit** (snapshot Merkle root + authoring data + parent pointers), dan **Tag** (pointer permanen teranotasi).
- Perintah *Porcelain* (`add`, `commit`, `checkout`) hanyalah pembungkus ergonomis dari rangkaian perintah *Plumbing* (`hash-object`, `update-index`, `write-tree`, `commit-tree`, `update-ref`).
- Skalabilitas skala enterprise pada ukuran repo puluhan gigabyte mengandalkan teknologi modern: **Sparse-Checkout Cone Mode**, **Blobless Partial Clones**, **Scalar**, serta algoritma diff mutakhir (**Histogram**).
- Integritas data repositori tingkat enterprise wajib ditegakkan menggunakan **Cryptographic Commit Signing** serta proteksi restriktif pada **Branch Rulesets** guna menjamin ketahanan *software supply chain security*.