# MODUL 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 01-Core-Foundations | **Topik:** Git & GitHub | **Bab:** 03-Materi-Lanjutan

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengurai dan merekayasa ulang arsitektur internal Git (Object Database, Directed Acyclic Graph/DAG, Packfiles, dan Index).
- Mengoperasikan *plumbing commands* untuk memanipulasi, memulihkan, dan mengaudit *state* repositori pada tingkat byte/hash.
- Mengimplementasikan teknik manipulasi histori tingkat lanjut (*advanced interactive rebase*, *three-way merge engine internals*, dan *history rewriting* skala besar).
- Menerapkan arsitektur repositori modern untuk skala *Enterprise* (Monorepo, *Sparse-Checkout*, *Partial Clone*, dan *Scalar/VFS*).
- Merancang alur verifikasi kriptografis (*commit signing* dengan SSH/GPG) dan sistem *governance* kepatuhan (GitHub Rulesets & CI-driven validation).
- Menangani insiden repositori kritis (*catastrophic history corruption*, *credential leakage purge*, dan *dangling commits recovery* via Reflog).

---

## 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib menguasai:
- Konsep dasar Git: Branching, Merging, Fetching, Pushing, Stashing.
- Pemahaman sistem file POSIX dan manipulasi command line (Bash/Zsh).
- Pengetahuan fundamental kriptografi asimetris (Public/Private Keys, SHA-1/SHA-256 Hashing).
- Konsep dasar arsitektur pipeline CI/CD modern.

---

## 3. Concept & Internal Architecture (Mendalam)

Git bukanlah sekadar sistem kontrol versi berbasis *delta/diff* tradisional seperti SVN atau CVS; Git pada dasarnya adalah sebuah **Content-Addressable Key-Value Store** yang dilapisi oleh struktur data pohon (*Merkle Tree*) yang membentuk sebuah **Directed Acyclic Graph (DAG)**.

```
                         ┌───────────────────────────┐
                         │      Commit Object        │
                         │ Hash: a1b2c3d...          │
                         │ - Tree: e5f6g7h...        │
                         │ - Parent: 9z8y7x6...      │
                         │ - Author / Committer      │
                         │ - Message                 │
                         └─────────────┬─────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │        Tree Object        │
                         │ Hash: e5f6g7h...          │
                         │ - 100644 blob 3k4l5m...   │──> src/index.ts
                         │ - 040000 tree 8p9q0r...   │──> src/utils/
                         └─────────────┬─────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
      ┌───────────────────────────┐         ┌───────────────────────────┐
      │        Blob Object        │         │        Tree Object        │
      │ Hash: 3k4l5m...           │         │ Hash: 8p9q0r...           │
      │ Content: Raw data only    │         │ - 100644 blob 2a3b4c...   │──> math.ts
      │ (No filename, no metadata)│         └───────────────────────────┘
      └───────────────────────────┘
```

### 3.1. Struktur Objek Git (`.git/objects`)
Setiap objek Git diidentifikasi secara unik menggunakan hash kriptografis (default: SHA-1 160-bit; modern: SHA-256). Format penyimpanan pada disk dikompresi menggunakan format `zlib deflated`, diawali dengan *header*: `[tipe_objek] [ukuran_dalam_byte]\0[konten]`.

Terdapat empat tipe objek fundamental dalam Git:
1. **Blob (*Binary Large Object*)**: Hanya menyimpan data mentah file. Blob tidak menyimpan nama file, *timestamp*, maupun *permission* (atribut ini disimpan di dalam *Tree*).
2. **Tree**: Merepresentasikan direktori. Berisi daftar referensi mode file (misal `100644` untuk standar, `100755` untuk *executable*, `040000` untuk subdirektori), tipe objek, hash SHA, dan nama file/direktori.
3. **Commit**: Mengikat *Tree* akar (*root directory snapshot*), satu atau lebih pointer hash *Parent*, metadata pembuat (*author* & *committer* dengan *timezone offset*), serta pesan *commit*.
4. **Annotated Tag**: Objek independen yang menunjuk langsung ke sebuah *commit*, menyimpan metadata penanda (*tagger*), waktu, pesan rilis, dan tanda tangan kriptografis opsional (GPG/SSH).

### 3.2. Index (`.git/index` atau Staging Area)
Index adalah file biner terurut yang bertindak sebagai *cache* konsolidasi antara direktori kerja (*Working Directory*) dan riwayat penyimpanan (*Object Database*). Index mencatat path file, stempel waktu `stat` sistem operasi (mtime, ctime, inode, file size), serta hash SHA-1 objek *blob* target. Mekanisme ini memungkinkan Git mendeteksi perubahan file secara instan menggunakan komparasi `stat` tanpa perlu membaca keseluruhan isi file dari disk.

### 3.3. Packfiles dan Delta Compression (`.git/objects/pack`)
Menyimpan setiap versi file sebagai satu objek individual yang utuh akan menghabiskan ruang disk secara cepat. Untuk efisiensi, Git mengonsolidasikan objek-objek longgar (*loose objects*) ke dalam **Packfile** (`.pack`) disertai file indeks (`.idx`). 
- Git menggunakan algoritma kompresi delta berbasis *sliding window*. 
- Secara cerdas, Git menyimpan versi file *terbaru* secara utuh (*canonical/full object*) dan versi-versi *sebelumnya* sebagai *delta* (perubahan terbalik). Hal ini memastikan operasi pada cabang modern (*tip of branch*) selalu memiliki performa pembacaan maksimal tanpa perlu merekonstruksi *diff chain*.

### 3.4. The Merge Engine: Recursive vs. ORT
Secara historis, Git menggunakan strategi *recursive 3-way merge*. Jika terdapat lebih dari satu *Common Ancestor* (misal pada pola *criss-cross merge*), Git membuat sebuah *virtual common ancestor* dengan menggabungkan para leluhur tersebut terlebih dahulu. 
Mulai Git versi 2.33+, engine default digantikan oleh **ORT** (*Ostensibly Recursive's Twin*). ORT ditulis ulang sepenuhnya untuk mengatasi inefisiensi arsitektur lama:
- Mengeliminasi kalkulasi I/O disk yang redundan dengan mengalihkan *conflict resolution* ke *in-memory operation*.
- Optimalisasi deteksi *rename* secara eksponensial (menurunkan kompleksitas komputasi dari $O(N \cdot M)$ menjadi mendekati instan melalui *directory rename detection*).

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional (Primitif) | Pendekatan Enterprise (Advanced Engineering) |
| :--- | :--- | :--- |
| **History Hygiene** | Menggunakan merge commit secara acak, commit fix-up tercecer di *main*, pesan commit non-standar. | Menggunakan strategi rebase topologis, *squash-merging* terkontrol, mematuhi *Conventional Commits*, linear/semi-linear tree. |
| **Repository Scale** | Full Clone untuk seluruh riwayat dan aset biner; menyebabkan bottleneck jaringan dan memori. | Implementasi *Partial Clones* (`--filter=blob:none`), *Sparse-Checkout*, dan optimasi `commit-graph`. |
| **Security & Trust** | Identitas berbasis email lokal pada konfigurasi `.gitconfig` yang rentan terhadap pemalsuan (*spoofing*). | Verifikasi identitas kriptografis wajib (*Signed Commits* SSH/GPG), aturan GitHub Rulesets tanpa *bypass*. |
| **Data Recovery** | Melakukan re-clone saat branch rusak atau file terhapus; panik terhadap status *Detached HEAD*. | Rekonstruksi state melalui `git reflog`, manual DAG traversal, dan plumbing *commit rescue*. |

---

## 5. How (Workflow Detail)

### 5.1. Workflow: Rebase Topologis Tingkat Lanjut dengan Dependency Chaining
Saat mengelola cabang fitur yang bergantung pada cabang fitur lain sebelum digabungkan ke `main`, rebase standar sering kali menduplikasi commit. Diperlukan perintah `git rebase --onto`:

```
Histori Awal:
main:      A---B
feature-1:      \---C---D
feature-2:               \---E---F (dibuat dari feature-1)

Tujuan: Pindahkan feature-2 langsung ke main tanpa membawa C dan D.
Sintaks: git rebase --onto <new-base> <old-base> <branch-to-move>
Eksekusi: git rebase --onto main feature-1 feature-2

Hasil:
main:      A---B---E'---F' (feature-2)
                \
                 \---C---D (feature-1)
```

### 5.2. Workflow: Enterprise Monorepo Sparse-Checkout Pipeline
Untuk merekayasa akses pada repositori monorepo multi-gigabyte agar developer hanya mengunduh subdirektori yang relevan:

```bash
# 1. Clone metadata saja tanpa mengunduh blob konten
git clone --filter=blob:none --no-checkout <repo-url> enterprise-monorepo
cd enterprise-monorepo

# 2. Inisialisasi mode sparse-checkout berbasis kerucut (cone mode)
git sparse-checkout init --cone

# 3. Definisikan domain kerja terbatas (hanya microservice pembayaran dan shared library)
git sparse-checkout set services/payment-gateway libs/common-auth

# 4. Checkout branch kerja
git checkout main
```

---

## 6. Analogy & Diagram ASCII

### 6.1. Analogi DAG Git vs. Rekening Bank
Sistem file konvensional menyimpan status saat ini secara destruktif (*overwriting files*), mirip seperti mengecat ulang dinding. Git bekerja seperti **buku kas akuntansi terdistribusi (ledger/blockchain)**. Anda tidak pernah menghapus riwayat; Anda hanya menambahkan (*append-only*) mutasi baru. Sebuah *Commit* adalah segel buku kas yang mereferensikan hash segel sebelumnya. Jika satu huruf dalam sejarah berubah, seluruh hash berikutnya runtuh (*Merkle Tree validation*).

### 6.2. Diagram: Three-Way Merge Algorithm (ORT Engine)
```
        [Common Ancestor: Base]
                 O (file.txt: "foo")
                / \
               /   \
              /     \
  [Ours: Commit A]   [Theirs: Commit B]
   (file.txt: "foo")  (file.txt: "bar")
              \     /
               \   /
                \ /
          [Merge Result]
        (file.txt: "bar")
  
  Mekanisme Keputusan 3-Way Merge:
  - Base vs. Ours   : Tidak ada perubahan ("foo" == "foo")
  - Base vs. Theirs  : Ada perubahan ("foo" -> "bar")
  - Resolusi Otomatis: Ambil "Theirs" tanpa konflik. Konflik hanya timbul jika 
    Ours != Base DAN Theirs != Base, serta Ours != Theirs.
```

---

## 7. Code Examples

### 7.1. Simple/Low-Level Example: Rekonstruksi Commit Secara Manual Menggunakan Git Plumbing
Membuat file, memasukkannya ke database objek, menyusun struktur pohon, dan membuat commit tanpa menggunakan `git add` atau `git commit`.

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Inisialisasi repositori kosong
mkdir plumbing-lab && cd plumbing-lab
git init

# 2. Buat file fisik dan hitung hash-nya ke dalam object database (menghasilkan Blob)
echo "console.log('Core Engine v1');" > app.js
BLOB_HASH=$(git hash-object -w app.js)
echo "Blob Hash: ${BLOB_HASH}"

# 3. Daftarkan blob ke staging index secara manual dengan mode 100644 (standard file)
git update-index --add --cacheinfo 100644 "${BLOB_HASH}" app.js

# 4. Tulis staging index ke dalam bentuk Tree Object
TREE_HASH=$(git write-tree)
echo "Tree Hash: ${TREE_HASH}"

# 5. Buat Commit Object yang menunjuk ke Tree tersebut (tanpa Parent)
COMMIT_HASH=$(echo "feat(core): initial plumbing commit" | git commit-tree "${TREE_HASH}")
echo "Commit Hash: ${COMMIT_HASH}"

# 6. Arahkan pointer branch main ke commit yang baru dibuat
git update-ref refs/heads/main "${COMMIT_HASH}"

# 7. Verifikasi integritas DAG melalui Porcelain command
git log --stat
```

### 7.2. Practical Example: Enterprise Pre-Push Verification Hook
Skrip hook Bash produksi (`.git/hooks/pre-push`) untuk memblokir secret ter-commit, mendeteksi pelanggaran branch naming convention, dan memverifikasi tanda tangan GPG lokal sebelum paket data keluar dari mesin insinyur.

```bash
#!/usr/bin/env bash
# .git/hooks/pre-push
set -eo pipefail

PROTECTED_BRANCH="main"
CURRENT_BRANCH=$(git symbolic-ref --short HEAD)

echo "==> [HOOK] Memulai audit pra-pengiriman untuk branch: ${CURRENT_BRANCH}"

# 1. Larang push langsung ke protected branch
if [ "$CURRENT_BRANCH" = "$PROTECTED_BRANCH" ]; then
    echo "ERROR: Push langsung ke branch '${PROTECTED_BRANCH}' dilarang oleh arsitektur tata kelola!"
    echo "Gunakan alur kerja Pull Request."
    exit 1
fi

# 2. Deteksi kebocoran kredensial atau private keys secara statis
echo "==> [HOOK] Memeriksa pola kebocoran kredensial..."
FORBIDDEN_PATTERNS="(BEGIN RSA PRIVATE KEY|BEGIN OPENSSH PRIVATE KEY|AKIA[0-9A-Z]{16}|ghp_[a-zA-Z0-9]{36})"
COMMITS_TO_SCAN=$(git rev-list "origin/${PROTECTED_BRANCH}..HEAD")

for COMMIT in $COMMITS_TO_SCAN; do
    if git diff-tree -p "$COMMIT" | grep -E "$FORBIDDEN_PATTERNS" > /dev/null; then
        echo "SECURITY ALERT: Ditemukan artefak rahasia pada commit ${COMMIT}!"
        echo "Push dibatalkan segera. Bersihkan histori Anda menggunakan git-filter-repo."
        exit 1
    fi
done

# 3. Validasi penandatanganan commit (GPG/SSH Signature Validation)
echo "==> [HOOK] Memverifikasi integritas kriptografi commit..."
for COMMIT in $COMMITS_TO_SCAN; do
    # %G? mengevaluasi status: G = Good (Valid), B = Bad, U = Untrusted, N = No signature
    SIGNATURE_STATUS=$(git log -1 --format="%G?" "$COMMIT")
    if [ "$SIGNATURE_STATUS" = "N" ] || [ "$SIGNATURE_STATUS" = "B" ]; then
        echo "COMPLIANCE ERROR: Commit ${COMMIT} tidak ditandatangani atau tanda tangan korup (Status: ${SIGNATURE_STATUS})!"
        echo "Seluruh commit korporat wajib ditandatangani dengan GPG/SSH keys."
        exit 1
    fi
done

echo "==> [HOOK] Seluruh validasi berhasil dilewati. Mengizinkan transfer payload."
exit 0
```

---

## 8. Real-World Case Study (Enterprise Scale)

### Kasus: Insiden Penurunan Performa Repositori FinTech & Kebocoran Kredensial Multi-Branch
* **Profil Entitas**: Platform Pembayaran Skala Global.
* **Skala Repositori**: 1 Monorepo, 850+ Rekayasa Perangkat Lunak, 180.000+ commit, ukuran disk `.git` mencapai 14.2 GB.

### Masalah Utama:
1. Waktu eksekusi CI/CD pipeline membengkak drastis: Perintah `git clone` rata-rata membutuhkan waktu 18 menit pada agent pipeline ephemeral.
2. Seorang insinyur secara tidak sengaja meng-commit file `vault-production-token.json` ke dalam sebuah branch eksperimental yang kemudian dimerge ke `main`. Upaya perbaikan primitif (`git rm` pada commit berikutnya) tetap membiarkan token tersebut dapat diakses oleh siapa pun di seluruh clone masa depan melalui DAG.

### Strategi Remediasi & Rekayasa Arsitektur:

#### Fase 1: Purging Secret Global Menggunakan Engine Terakselerasi
Penggunaan `git filter-branch` sudah ditinggalkan (*deprecated*) karena performa I/O yang sangat lambat dan resiko kegagalan penulisan ref. Tim menggunakan `git-filter-repo` (berbasis Python engine):

```bash
# Isolasi repositori ke status fresh mirror
git clone --mirror git@github.com:enterprise/monorepo.git monorepo-sanitization
cd monorepo-sanitization

# Analisis ukuran dan hapus file rahasia di seluruh DAG, tag, dan refs
git filter-repo --invert-paths --path "vault-production-token.json" --force

# Revoke kredensial pada server produksi secara paralel (Prinsip Zero-Trust)
# Push pembaruan histori secara atomik ke origin (membutuhkan bypass administrasi)
git push origin --force --all
git push origin --force --tags
```

#### Fase 2: Reduksi Latensi CI/CD melalui Treeless Clones
Pipeline CI diubah dari model *shallow clone* (`--depth=1` yang memecah kalkulasi merge-base dan penelusuran commit) menjadi *Treeless Clone*:

```yaml
# GitHub Actions Optimized Step
- name: Accelerated Repository Checkout
  run: |
    git clone --filter=tree:0 --no-checkout https://github.com/enterprise/monorepo.git .
    git checkout ${{ github.sha }}
```
* **Hasil**: Durasi transfer metadata jaringan terpangkas dari 18 menit menjadi **24 detik**, menghemat bandwidth transfer cloud sebesar 88%.

---

## 9. Trade-offs & Architecture Considerations

| Parameter Arsitektur | Opsi A: Merge Commit (Non-Fast-Forward) | Opsi B: Rebase Linear History | Opsi C: Squash and Merge |
| :--- | :--- | :--- | :--- |
| **History Traceability** | Maksimal: Mempertahankan struktur waktu asli dan asosiasi cabang. | Menengah: Garis waktu linier bersih, tetapi konteks pengelompokan cabang hilang. | Terisolasi: Riwayat mikro hilang, hanya ada 1 representasi commit per PR. |
| **Bisect Operability** | Rawan: Sering kali `git bisect` mendarat pada broken intermediate commits. | Baik: Setiap commit dapat diisolasi dan diuji mandiri jika rebase dilakukan rapi. | Sempurna: Setiap commit pada `main` selalu merepresentasikan unit kerja yang valid/hijau. |
| **Audit Compliance** | Tinggi: Menampilkan data audit asli tanpa memanipulasi waktu pembuatan. | Rendah/Menengah: Mengubah hash dan stempel waktu committer. | Tergantung: Metadata asli berpindah ke deskripsi pull request. |
| **Kompleksitas Konflik** | Konflik diselesaikan sekali saja pada *merge commit*. | Konflik diselesaikan commit-demi-commit (dapat melelahkan jika banyak commit). | Konflik diselesaikan satu kali saat evaluasi final branch. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Kesalahan Fatal: Menggunakan `git push --force` Alih-alih `--force-with-lease`
* **Gejala**: Perubahan rekan kerja di remote branch terhapus secara permanen karena tertimpa oleh local commit yang kedaluwarsa.
* **Penyebab**: Flag `--force` memerintahkan remote server menonaktifkan pengecekan integritas pointer, memaksakan hash lokal tanpa peduli ada update baru di remote.
* **Solusi Perbaikan**: Gunakan selalu:
  ```bash
  git push --force-with-lease
  ```
  Opsi ini memastikan transaksi atomic: remote hanya akan diperbarui jika hash referensi remote sama persis dengan snapshot pelacak lokal (`refs/remotes/origin/...`).

### 10.2. Disaster Recovery: Memulihkan Commit yang Hilang Akibat `git reset --hard`
* **Kasus**: Developer menjalankan `git reset --hard HEAD~5` secara tidak sengaja dan kehilangan 5 commit penting.
* **Diagnosis & Solusi**:

```bash
# 1. Telusuri Reflog (pencatat seluruh pergerakan HEAD secara lokal)
git reflog

# Output:
# 4f8b9e1 HEAD@{0}: reset: moving to HEAD~5
# 7c3d2e5 HEAD@{1}: commit: feat(auth): add OAuth2 provider   <-- COMMIT INI HILANG
# a9b8c7d HEAD@{2}: commit: feat(auth): add token validation

# 2. Pulihkan pointer branch saat ini langsung ke hash sebelum eksekusi reset
git reset --hard 7c3d2e5

# Atau amankan ke branch penyelamat khusus:
git branch recovery-branch 7c3d2e5
```

### 10.3. Penanganan Objek Terkorupsi: Pembersihan Lock File Stale
* **Masalah**: Muncul pesan error fatal: `fatal: Unable to create '.git/index.lock': File exists.`
* **Penyebab**: Proses Git terputus mendadak (*SIGKILL*, crash sistem operasi, atau OOM Killer) saat sedang memodifikasi index.
* **Troubleshooting**: Pastikan tidak ada proses Git aktif di background sebelum menghapus file lock:
  ```bash
  ps aux | grep git
  # Jika aman dan tidak ada proses berjalan:
  rm -f .git/index.lock
  ```

---

## 11. Best Practices (Production Checklist)

- [ ] **Linear/Clean Topology**: Standarisasi PR merging menggunakan strategi *Squash-Merge* atau *Rebase & Merge* guna mencegah *spaghetti DAG*.
- [ ] **Cryptographic Attestation**: Wajibkan penandatanganan commit menggunakan kunci SSH lokal atau GPG key yang terotentikasi.
- [ ] **Branch Protection Rulesets**:
  - Matikan opsi `Force Pushes` dan `Deletions` pada branch target rilis (`main`, `production`).
  - Wajibkan *linear commit history*.
  - Wajibkan verifikasi *Status Checks* (Green CI) sebelum penggabungan kode.
- [ ] **Repository Optimization Maintenance**:
  - Jalankan `git maintenance start` pada mesin developer untuk menjalankan `gc`, `pack-refs`, dan komputasi `commit-graph` di background.
- [ ] **Sanitized Commits**: Terapkan *Conventional Commits* (`feat:`, `fix:`, `refactor:`, `chore:`) untuk mengotomatisasi Semantic Versioning dan changelog generator.
- [ ] **Monorepo Hygiene**: Tempatkan file `.gitattributes` di root repositori untuk mendeklarasikan normalisasi line-ending (`* text=auto eol=lf`) dan penanganan Git LFS (*Large File Storage*).

---

## 12. Hands-on Practice

Simpan seluruh hasil latihan pada folder: `hands-on/m02/`

### Skenario: Merancang Objek Tingkat Rendah, Manipulasi Histori Kompleks, dan Diagnostik Reflog

#### Langkah 1: Eksplorasi Database Objek Manual
```bash
mkdir -p hands-on/m02/lab-internals && cd hands-on/m02/lab-internals
git init

# Buat file dan periksa lokasi fisik objeknya
echo "Arquitetura de Software" > manifesto.txt
HASH=$(git hash-object -w manifesto.txt)
echo "Hash: ${HASH}"

# Lihat 2 karakter pertama (nama subdirektori) dan 38 karakter sisanya
DIR_NAME=$(echo "$HASH" | cut -c1-2)
FILE_NAME=$(echo "$HASH" | cut -c3-40)
ls -la ".git/objects/${DIR_NAME}/${FILE_NAME}"

# Dekompresi dan baca konten objek mentah secara langsung
git cat-file -p "${HASH}"
git cat-file -t "${HASH}" # Output: blob
```

#### Langkah 2: Rekayasa Manipulasi Histori Tanpa Kehilangan Root Identitas
```bash
# Tambahkan beberapa commit
git add manifesto.txt
git commit -m "docs: initial manifest"

echo "Metric 1: MTTR" >> metrics.txt
git add metrics.txt
git commit -m "feat: add MTTR metric"

echo "Metric 2: Lead Time" >> metrics.txt
git add metrics.txt
git commit -m "feat: add Lead Time metric"

# Ubah urutan commit dan modifikasi isi commit pertama menggunakan interactive rebase
GIT_SEQUENCE_EDITOR="sed -i.bak 's/pick/edit/g'" git rebase -i --root

# Periksa status rebase yang sedang pause
git status

# Ubah author data untuk simulasi compliance remediation
git commit --amend --author="SecOps Admin <secops@enterprise.internal>" --no-edit
git rebase --continue
```

#### Langkah 3: Simulasi Bencana dan Penyelamatan Reflog
```bash
# Hapus commit terakhir secara destruktif
git reset --hard HEAD~1

# Verifikasi bahwa commit "Lead Time" seolah-olah hilang
git log --oneline

# Selamatkan commit menggunakan dangling reflog hash
TARGET_LOST_HASH=$(git reflog | grep "feat: add Lead Time metric" | head -n1 | awk '{print $1}')
echo "Recovering hash: ${TARGET_LOST_HASH}"

git branch rescued-feature "${TARGET_LOST_HASH}"
git log --graph --oneline rescued-feature
```

---

## 13. Exercises

### Level 1 (Easy):
Gunakan plumbing command Git untuk:
1. Membaca isi dari sebuah *Tree Object* dari commit terkini tanpa melakukan checkout branch.
2. Temukan sha hash dari root tree object dari HEAD saat ini.

<details>
<summary>Solusi Petunjuk</summary>

```bash
ROOT_TREE=$(git rev-parse HEAD^{tree})
echo "Root Tree: $ROOT_TREE"
git ls-tree $ROOT_TREE
```
</details>

### Level 2 (Medium):
Lakukan operasi *squash* manual menggunakan interaksi rebase non-interaktif atau perakitan commit-tree terhadap 3 commit terakhir, ubah author timestamp menjadi waktu Unix epoch `1609459200` tanpa mengubah committer timestamp saat ini.

<details>
<summary>Solusi Petunjuk</summary>

```bash
# Alternatif via Git Environment Variable overrides saat amend/rebase
GIT_COMMITTER_DATE=$(date) GIT_AUTHOR_DATE="1609459200" git commit --amend --no-edit
```
</details>

### Level 3 (Hard):
Tulis sebuah script Bash mandiri yang melakukan iterasi rekursif terhadap seluruh objek pada `.git/objects/pack/*.idx` untuk menemukan objek *blob* terbesar (secara uncompressed data footprint) di seluruh riwayat repositori untuk menemukan anomali biner.

<details>
<summary>Solusi Petunjuk</summary>

```bash
git verify-pack -v .git/objects/pack/*.idx \
  | grep -v chain \
  | sort -k3nr \
  | head -n 5 \
  | while read -r hash type size rest; do
      echo "Size: $((size/1024)) KB | Hash: $hash | Name: $(git rev-list --objects --all | grep "$hash" | cut -d' ' -f2-)"
    done
```
</details>

---

## 14. Real-World Architectural Challenge

### Konteks Skenario:
Sebuah bank digital mengalami kegagalan proses deployment di lingkungan staging:
1. Repositori monorepo mereka memiliki aturan: **Linear History Only (Strict Semi-Linear)**.
2. Developer A dan Developer B secara independen mengerjakan branch fitur yang memodifikasi skema *database migration*.
3. Branch Developer A telah disetujui, diuji, dan digabungkan ke `main` via rebase otomatis CI.
4. Branch Developer B lolos pengujian secara lokal pada basis commit lama, namun saat direbase di atas `main` yang baru, menimbulkan tabrakan logika (*semantic conflict*), bukan tabrakan teks (*merge conflict*). Akibatnya, build pipeline rusak saat digabungkan, dan staging database bermutasi ke status korup.

### Parameter Tantangan:
Rancang arsitektur pipeline branching dan verifikasi Git Enterprise berbasis automasi:
1. Formulasikan arsitektur **Merge Queue / Train Engine** menggunakan arsitektur event-driven Git webhook untuk mencegah terjadinya tabrakan semantik antar cabang sebelum commit mencapai `main`.
2. Gambarkan diagram alur DAG yang mendemonstrasikan bagaimana *Speculative Merging* memvalidasi commit A dan B secara simultan tanpa menghentikan jalur throughput developer lainnya.
3. Definisikan konfigurasi spesifik GitHub Branch Protection / Rulesets untuk memastikan zero-regression guarantees pada sistem trunk-based ini.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic (Pilihan Ganda)

1. Objek Git apa yang bertanggung jawab memetakan nama file, direktori, dan mode permission ke representasi hash datanya?
   - A. Blob
   - B. Tree
   - C. Commit
   - D. Reference

2. Di manakah Git menyimpan riwayat perpindahan pointer `HEAD` lokal secara historis?
   - A. `.git/HEAD`
   - B. `.git/logs/HEAD` (Reflog)
   - C. `.git/config`
   - D. `.git/info/exclude`

3. Format kompresi bawaan apa yang digunakan objek-objek Git saat disimpan sebagai *loose objects*?
   - A. Gzip
   - B. Zstandard (zstd)
   - C. Zlib (Deflate)
   - D. Bzip2

4. Manakah flag yang benar dan aman digunakan saat melakukan modifikasi riwayat lokal yang harus dipublikasikan ke branch remote?
   - A. `--force`
   - B. `--force-with-lease`
   - C. `--hard`
   - D. `--ignore-remote`

5. Apa efek dari konfigurasi clone `--filter=blob:none`?
   - A. Repositori hanya mengunduh commit terakhir (kedalaman shallow = 1).
   - B. Repositori tidak mengunduh tag sama sekali.
   - C. Repositori mengunduh commit dan tree secara utuh, namun blob data file hanya ditarik secara on-demand saat dibuka/dicheckout.
   - D. Repositori mengabaikan seluruh file yang didefinisikan dalam `.gitignore`.

---

### Bagian B: Intermediate (Esai Analitis)

6. Jelaskan secara mendalam mengapa Git memilih arsitektur *Merkle Tree/DAG* daripada arsitektur *Linear Delta Recording* (seperti RCS/CVS)! Apa implikasinya terhadap verifikasi integritas data?
7. Analisis apa perbedaan internal mendasar antara pointer **Branch** (`refs/heads/*`) dan pointer **Lightweight Tag** (`refs/tags/*`) di dalam direktori `.git/`!
8. Apa yang terjadi secara struktural pada file index dan working tree ketika seorang insinyur mengeksekusi `git reset --soft HEAD~1` dibandingkan dengan `git reset --mixed HEAD~1`?
9. Jelaskan bagaimana mesin penggabungan modern **ORT** mampu menyelesaikan masalah deteksi pemindahan file/direktori (*rename detection*) jauh lebih cepat dibanding engine tradisional *Recursive*!
10. Mengapa melakukan `git filter-branch` dianggap tidak aman dan sudah *deprecated* oleh Git core team untuk membersihkan artefak sensitif pada repositori modern berskala besar?

---

### Bagian C: Kasus Solutif Tingkat Lanjut (Production Troubleshooting Scenarios)

11. **Kasus 1: Dangling Object Purge & Storage Reclamation**
    Sebuah repositori enterprise telah dibersihkan dari artefak biner besar (file `.tar.gz` 4GB) menggunakan `git-filter-repo`. Namun, saat administrator menjalankan `du -sh .git`, ukuran repositori pada disk masih tetap 4GB lebih. Identifikasi penyebab internal Git terkait referensi lingering dan packfiles, lalu tuliskan langkah mitigasi absolut untuk membebaskan ruang disk fisik tersebut!

12. **Kasus 2: Resolusi Criss-Cross Merge Deadlock**
    Dua branch jangka panjang mengalami situasi di mana Branch X menggabungkan Branch Y, dan Branch Y secara simultan menggabungkan Branch X pada waktu yang berbeda, menghasilkan dua *Common Ancestors* independen (criss-cross DAG). Ketika keduanya digabungkan ke `main`, developer terjebak dalam loop konflik berulang. Bagaimana arsitektur Git menyelesaikan skenario multiple merge base ini, dan bagaimana strategi insinyur untuk menormalisasi cabang tersebut?

13. **Kasus 3: Audit Forensik Pemalsuan Identitas Commit**
    Di dalam repositori perbankan, ditemukan sebuah commit berbahaya yang tercatat menggunakan nama dan email Chief Architect (`architect@bank.com`), namun Arsitek tersebut membantah pernah menulis kode tersebut. Sebagai Lead AppSec Engineer, langkah validasi forensik Git apa yang akan Anda jalankan untuk membuktikan apakah commit tersebut palsu (*spoofed*), dan arsitektur kontrol GitHub apa yang harus ditegakkan untuk mencegah hal tersebut terulang kembali?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Jawaban Bagian A:
1. **B (Tree)**. Blob hanya berisi data biner mentah. Tree memetakan permission, nama file, dan menghubungkannya ke hash Blob/sub-Tree.
2. **B (`.git/logs/HEAD`)**. Git reflog disimpan di bawah direktori logs.
3. **C (Zlib)**. Git menggunakan modul kompresi Zlib deflated.
4. **B (`--force-with-lease`)**. Flag ini memvalidasi kecocokan nilai referensi remote sebelum melakukan override historis.
5. **C**. Opsi ini menciptakan *Blobless Partial Clone*, salah satu pilar penanganan monorepo skala masif.

#### Panduan Jawaban Bagian B:
6. **Merkle Tree & Integrity**: Merkle Tree memungkinkan Git memvalidasi seluruh snapshot proyek melalui satu *root commit hash*. Perubahan satu byte pada file terdalam di masa lalu akan mengubah hash blob, mengubah hash tree direktori induknya, hingga mengubah seluruh hash commit turunannya. Ini menjamin sifat *tamper-evident* (anti-pemalsuan mutlak). Sebaliknya, *Delta Recording* linear mengharuskan pembacaan bertingkat di mana korupsi data di tengah riwayat sulit dideteksi tanpa memproses ulang seluruh rangkaian diferensial.
7. **Branch vs Lightweight Tag**: Secara internal, keduanya adalah pointer teks sederhana di `.git/refs/` yang menyimpan SHA-1 commit (berukuran 41 byte). Perbedaan mendasar: Pointer **Branch** bersifat dinamis; Git akan memperbarui hash di dalamnya secara otomatis setiap kali commit baru ditambahkan saat branch tersebut aktif. Pointer **Tag** bersifat statis (*immutable*); nilainya tidak pernah bergeser dan ditujukan untuk mengunci satu titik waktu rilis secara permanen.
8. **Soft vs Mixed Reset**: 
   - `git reset --soft HEAD~1`: Hanya memindahkan pointer ref HEAD ke commit sebelumnya. Staging Index dan Working Tree tidak disentuh sama sekali (perubahan dari commit yang dibatalkan langsung berada dalam status *staged*).
   - `git reset --mixed HEAD~1` (default): Memindahkan pointer ref HEAD dan memperbarui Staging Index agar identik dengan `HEAD~1`. Working Tree tetap utuh (perubahan menjadi *unstaged*).
9. **ORT Engine Rename Optimization**: Engine Recursive memproses deteksi rename dengan membandingkan pasangan file di seluruh disk kerja secara fisik. Engine ORT mengeksekusi kalkulasi ini sepenuhnya di *memory layer*. ORT mengamati bahwa jika direktori induk berpindah, seluruh file di dalamnya tidak perlu dicek kesamaan isinya satu per satu; Git ORT langsung menerapkan *Directory-Level Rename Resolution*, memangkas jutaan komparasi string yang tidak diperlukan.
10. **Deprecasi `git filter-branch`**: Shell-script based processing yang mengeksekusi sub-shell dan I/O disk untuk setiap single commit. Sangat lambat pada repositori besar, tidak menangani anotasi tag bertingkat dengan benar, sering kali meninggalkan backup refs rahasia di `.git/refs/original/`, dan sangat rentan merusak tanda tangan digital (*GPG signatures*) tanpa peringatan yang komprehensif.

#### Panduan Jawaban Bagian C (Kasus Solutif):
11. **Penyelamatan Disk Pascafilter**:
    - *Penyebab*: Objek 4GB tersebut masih direferensikan oleh **Reflog**, pointer stashes, atau file pack metadata internal, sehingga mekanisme *Garbage Collector* (`git gc`) menganggap objek tersebut belum benar-benar yatim (*reachable*).
    - *Solusi Mitigasi*:
      ```bash
      # 1. Hapus seluruh riwayat reflog yang menahan referensi lama
      git reflog expire --expire=now --all
      # 2. Jalankan pembersihan agresif dan hapus loose & pack objects tak terpakai
      git gc --prune=now --aggressive
      ```
12. **Criss-Cross Merge Resolution**:
    - Git menangani criss-cross merge secara default dengan membuat *Virtual Common Ancestor* (melakukan merge internal di memori antara kedua ancestor). Namun, jika timbul ambiguitas logika berkepanjangan:
    - *Solusi*: Lakukan normalisasi topologi. Alih-alih melakukan *bi-directional merges*, isolasi perubahan Branch Y, lakukan `git rebase` terhadap Branch X untuk menyatukan basis riwayat secara linear, lalu gabungkan kembali ke `main`. Terapkan larangan branching silang (*cross-merging*) antar feature branch pada panduan tim.
13. **Forensik Identitas & Preventif**:
    - *Forensik*: Jalankan audit format mendalam: `git log -1 --format="raw" <commit-hash>`. Bandingkan blok `author` vs `committer`. Yang terpenting, periksa parameter status penandatanganan: `git verify-commit <commit-hash>` atau `git log -1 --format="%G? %GS %GK" <commit-hash>`. Jika commit palsu, output akan menunjukkan status `N` (No signature) atau `B` (Bad signature).
    - *Pencegahan Enterprise*: Aktifkan fitur **Vigilant Mode** pada GitHub Enterprise. Terapkan aturan GitHub Ruleset: **"Require signed commits"**. Dengan aturan ini, server GitHub akan menolak mutasi push commit apa pun yang tidak memiliki validasi kunci kriptografi asimetris yang cocok dengan public key yang terdaftar pada akun insinyur yang bersangkutan.

---

## 16. Summary

1. **Git adalah Content-Addressable Storage**: Arsitektur Git beroperasi atas empat objek utama (*blob, tree, commit, tag*) yang disimpan menggunakan hashing kriptografis pada Merkle Tree terkompresi. Memahami mekanisme internal ini adalah kunci penanganan insiden skala enterprise.
2. **Efisiensi Skala Besar**: Operasi monorepo masif menuntut pergeseran dari paradigma lama. Implementasi *Partial Clones* (`--filter=blob:none`), *Sparse-Checkout Cone Mode*, serta engine komparasi modern (**ORT**) adalah fondasi performa tinggi pada ekosistem rekayasa modern.
3. **Integritas dan Determinisme**: Manipulasi histori via *rebase* topologis menyediakan kejelasan audit log, namun harus diimbangi dengan protokol keamanan tingkat tinggi: penggunaan `--force-with-lease` mutlak, verifikasi Reflog berkala, serta penandatanganan kriptografis (*Signed Commits*) untuk menjamin *Zero-Trust Delivery Pipeline*.