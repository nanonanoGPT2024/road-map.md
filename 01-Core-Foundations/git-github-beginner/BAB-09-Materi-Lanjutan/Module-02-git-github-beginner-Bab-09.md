# MODUL 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

1. **Membongkar dan Memanipulasi *Object Database* Git**: Memahami implementasi *Content-Addressable Storage* (CAS) pada Git dengan membedah 4 tipe objek dasar (*blob*, *tree*, *commit*, *annotated tag*) menggunakan *plumbing commands*.
2. **Mengonstruksi dan Memodifikasi State Git Tanpa Porcelain Commands**: Membuat commit, memodifikasi staging tree, dan memanipulasi referensi pointer secara deterministik langsung pada level *plumbing* (`hash-object`, `mktree`, `commit-tree`, `update-ref`).
3. **Mengoperasikan Worktree Isolation**: Mengelola multi-cabang secara simultan tanpa *branch context-switching* atau *stash overhead* menggunakan `git worktree` untuk skenario *hotfix production* paralel.
4. **Menerapkan Automasi Root-Cause Analysis**: Mengotomasi pelacakan regresi kode pada ribuan commit menggunakan `git bisect run` terintegrasi dengan skrip unit testing/exit code automation.
5. **Mengeksekusi Strategi Histori Tingkat Lanjut**: Melakukan restrukturisasi commit graph secara aman menggunakan Interactive Rebase (`git rebase -i`), *squashing*, *reordering*, dan menyelesaikan skenario divergensi kompleks tanpa merusak integritas SHA-1/SHA-256.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
* Operasi dasar Git (*porcelain commands*): `add`, `commit`, `push`, `pull`, `branch`, `merge`.
* Pemahaman fundamental mengenai sistem file Unix, piping (`|`), standard I/O redirection (`>`, `<`), dan environment variables.
* Algoritma hashing dasar (kriptografis): konsep dasar *checksum* SHA-1 dan SHA-256.
* Struktur data dasar: *Directed Acyclic Graph* (DAG), *Pointers*, dan *Key-Value Store*.

---

## 3. Concept & Internal Architecture (Mendalam)

Git bukan sekadar sistem pengontrol versi (VCS) berbasis delta (*delta-based* seperti SVN), melainkan sebuah **Content-Addressable Key-Value Database** dengan lapisan antarmuka VCS di atasnya.

```
.git/
├── HEAD               # Pointer ke ref cabang aktif saat ini (mis: ref: refs/heads/main)
├── config             # Konfigurasi spesifik repositori
├── index              # Binary file: staging area / cache directory cache
├── objects/           # Object Database (OFS / Loose Objects & Packfiles)
│   ├── [0-9a-f]{2}/   # 2 karakter heksadesimal pertama (sharding direktori)
│   │   └── [0-9a-f]{38} # 38 karakter heksadesimal sisa (nama objek)
│   ├── info/
│   └── pack/          # Packfile (.pack) & Pack Index (.idx) untuk kompresi massal
└── refs/              # References (Pointers ke commit SHA)
    ├── heads/         # Pointers cabang lokal
    ├── tags/          # Pointers tag lokal
    └── remotes/       # Pointers tracking remote branch
```

### 3.1. Empat Tipe Objek Git Primitif

Setiap entitas di dalam `.git/objects/` disimpan menggunakan kompresi `zlib-deflate`. Konten objek memiliki struktur header terstandardisasi:

$$\text{Header} = \text{type} + \text{" "} + \text{size} + \text{"\textbackslash 0"}$$
$$\text{SHA-1 Hash} = \text{SHA1}(\text{Header} + \text{Payload})$$

```
+------------------------------------------------------------------------+
|                          Git Object Structure                          |
|                                                                        |
|  +--------+---+-----------------------+---+--------------------------+  |
|  |  type  |   | size (ASCII decimal)  | \0|         Payload          |  |
|  +--------+---+-----------------------+---+--------------------------+  |
|                                                                        |
|  <------------------- Compressed via zlib deflate ------------------->  |
+------------------------------------------------------------------------+
```

1. **Blob (Binary Large Object)**: Hanya menyimpan data konten mentah suatu berkas. Blob **tidak** menyimpan metadata berkas (nama berkas, permission mode, timestamp).
2. **Tree**: Merepresentasikan struktur direktori. Berisi daftar referensi mode berkas (*POSIX file mode*), tipe objek (*blob* atau *tree* sub-direktori), SHA-1 hash target, dan nama berkas/folder.
3. **Commit**: Merepresentasikan snapshot state proyek pada titik waktu tertentu. Berisi:
   * Pointer ke satu *Root Tree object*.
   * Zero, satu, atau lebih pointer *Parent Commit* (zero untuk initial commit, dua untuk merge commit).
   * Metadata Author (nama, email, epoch timestamp).
   * Metadata Committer (nama, email, epoch timestamp).
   * Pesan commit (*commit message*).
4. **Annotated Tag**: Objek independen yang menunjuk langsung ke commit tertentu, menyimpan tagger metadata, timestamp, PGP signature, dan pesan tag.

### 3.2. Directed Acyclic Graph (DAG) & Index Internals

File `.git/index` adalah binary cache berkecepatan tinggi yang memetakan file tree pada sistem file lokal ke objek *blob* yang sudah di-hash di dalam `.git/objects/`. Saat `git add` dieksekusi:
1. Git membaca berkas target.
2. Git menghitung hash dan menulis objek `blob` ke direktori `.git/objects/`.
3. Entri nama file, mode izin (mis: `100644` untuk standard file, `100755` untuk executable), stat metadata (mtime, ctime, inode, file size), dan SHA-1 dari blob tersebut dicatat ke file `.git/index`.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional (Black-box Git) | Pendekatan Enterprise Low-Level (Arsitektural) |
| :--- | :--- | :--- |
| **Penyelesaian Konflik** | Melakukan merge berulang, menghasilkan "Merge Hell" dan histori *octopus* yang tidak terlacak. | Menggunakan strategi *interactive rebase* dengan pemahaman titik divergensi DAG; menjaga linearitas dan auditabilitas. |
| **Troubleshooting Bug** | Menelusuri commit manual satu per satu via log manual; memakan waktu berjam-jam/berhari-hari. | Otomasi `git bisect` berbasis skrip tes eksternal; memangkas penelusuran menjadi $O(\log n)$ dalam hitungan menit. |
| **Multi-tasking / Hotfix** | `git stash`, pindah branch, kerja, stash pop (rawan *conflict dropping* dan *untracked loss*). | `git worktree`: isolasi direktori terpisah dengan `.git` metadata terpusat; instan, nol risiko stash collision. |
| **CI/CD Build Performance**| Melakukan full clone berkali-kali pada pipeline; membebani bandwidth dan storage agent runner. | Optimasi dengan *Blobless / Tree-less clones* (`--filter=blob:none`) dan manipulasi pointer sparse-checkout. |

---

## 5. How (Workflow Detail)

### 5.1. Rekonstruksi Commit Manual Menggunakan Plumbing Commands
Siklus pembuatan commit tanpa menyentuh perintah *porcelain* (`git add` / `git commit`):

```
[File Content] 
      │ 
      │ (git hash-object -w)
      ▼
[Blob Object in .git/objects]
      │
      │ (git update-index --add --cacheinfo)
      ▼
[.git/index (Staging Area)]
      │
      │ (git write-tree)
      ▼
[Tree Object in .git/objects]
      │
      │ (git commit-tree [tree-hash] -p [parent-hash])
      ▼
[Commit Object in .git/objects]
      │
      │ (git update-ref refs/heads/<branch>)
      ▼
[Branch Pointer Updated]
```

### 5.2. Isolated Concurrent Engineering Menggunakan Git Worktree
Memungkinkan pengerjaan beberapa branch secara bersamaan pada direktori terpisah tanpa kloning ulang:

```
                  Local Repository (.git main db)
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼                                               ▼
Main Working Tree                             Linked Working Tree
(/srv/apps/payment-service)                   (/srv/apps/hotfix-zero-day)
Checked out on: `main`                        Checked out on: `hotfix/CVE-2024`
```

---

## 6. Analogy & Diagram ASCII

Bayangkan Git sebagai sistem pengarsipan hukum modern:
* **Blob**: Lembaran kertas bertuliskan teks tanpa nama berkas, disimpan dalam brankas berlabel nomor sidik jarinya (*hash*).
* **Tree**: Folder map berkas fisik yang berisi daftar isi. Setiap baris menuliskan: *"Kertas nomor hash X dinamakan contract.pdf"*.
* **Commit**: Nota serah terima resmi bertanggal yang mencantumkan: *"Folder map yang berlaku saat ini adalah Map Hash Y, melanjutkan berkas dari Nota Sebelumnya Hash Z"*.
* **Branch**: Sticky note kecil (label nama cabang) yang ditempelkan di atas nota serah terima (Commit). Memindahkan branch hanyalah mencabut sticky note dan menempelkannya ke nota yang lain.

```
       +-----------------------------------------------------------+
       |                       COMMIT OBJECT                       |
       |  tree: d8329fc13b4cb1e866870f6f55979d15b43be7b7          |
       |  parent: 4a2b7c... (SHA Previous Commit)                 |
       |  author: Principal Eng <arch@corp.internal>               |
       |  committer: Principal Eng <arch@corp.internal>            |
       |                                                           |
       |  feat(core): implement zero-allocation buffer             |
       +-----------------------------+-----------------------------+
                                     |
                                     v
       +-----------------------------------------------------------+
       |                        TREE OBJECT                        |
       |  Mode     Type    SHA                               Name  |
       |  100644   blob    557db03de997c86a4a028e1ebd3a1c... README.md
       |  040000   tree    a1b2c3d4e5f6...                   src   |
       +------------------------------------------------------+----+
                                                              |
                                                              v
                                +----------------------------------+
                                |            TREE OBJECT           |
                                |  Mode     Type    SHA      Name  |
                                |  100644   blob    e69de29b main.go
                                +---------------------+------------+
                                                      |
                                                      v
                                +----------------------------------+
                                |            BLOB OBJECT           |
                                |  package main                    |
                                |  func main() { ... }             |
                                +----------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Membuat Commit dari Dasar Murni (Plumbing Level)

Jalankan perintah ini di shell terminal Linux/macOS untuk melihat pembuatan objek secara transparan:

```bash
# Inisialisasi sandbox
mkdir git-internals-sandbox && cd git-internals-sandbox
git init

# 1. Buat Payload Konten dan simpan sebagai BLOB langsung ke object store
echo "fmt.Println('Enterprise Architecture v1')" > app.go
BLOB_HASH=$(git hash-object -w app.go)
echo "Blob Generated: ${BLOB_HASH}"

# Periksa tipe dan isi objek langsung dari database
git cat-file -t ${BLOB_HASH}
git cat-file -p ${BLOB_HASH}

# 2. Masukkan BLOB ke dalam Staging Area (.git/index) secara manual
git update-index --add --cacheinfo 100644 ${BLOB_HASH} src/app.go

# 3. Tulis isi staging area menjadi TREE object
TREE_HASH=$(git write-tree)
echo "Tree Generated: ${TREE_HASH}"
git cat-file -p ${TREE_HASH}

# 4. Buat COMMIT object yang mereferensikan root Tree tersebut
COMMIT_HASH=$(echo "feat(engine): bootstrap architecture using plumbing" | git commit-tree ${TREE_HASH})
echo "Commit Generated: ${COMMIT_HASH}"
git cat-file -p ${COMMIT_HASH}

# 5. Pasang branch pointer (refs/heads/main) ke commit baru tersebut
git update-ref refs/heads/main ${COMMIT_HASH}

# 6. Set HEAD agar menunjuk ke branch main
git symbolic-ref HEAD refs/heads/main

# 7. Validasi menggunakan porcelain command
git log -1 --stat
```

### 7.2. Practical Example: Enterprise Multi-Worktree Orchestrator & Commit Governance

Skenario: Anda sedang mengembangkan fitur besar pada repositori production, namun terjadi insiden kritis (*P1 Zero-Day Vulnerability*) yang mewajibkan hotfix instan ke branch `production`. Tanpa merusak working directory lokal atau melakukan `git stash`:

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT=$(pwd)
HOTFIX_DIR="../payment-engine-hotfix-cve"

echo "[1/4] Mengisolasi Workspace Hotfix via Git Worktree..."
# Membuat folder paralel yang linked ke object database lokal utama
git fetch origin production
git worktree add -b hotfix/cve-remediation "${HOTFIX_DIR}" origin/production

echo "[2/4] Beralih konteks eksekusi ke Worktree Hotfix..."
pushd "${HOTFIX_DIR}" > /dev/null

echo "[3/4] Melakukan Patching..."
cat << 'EOF' > security_patch.go
package main

// SecurityPatch mitigates memory exhaustion via payload limit
const MaxPayloadSize = 1024 * 1024 // 1MB constraint
EOF

git add security_patch.go
git commit -m "fix(security): mitigate memory exhaustion vulnerability CVE-2024"

echo "[4/4] Validasi DAG dan Bersihkan Linked Worktree..."
git log -1 --oneline --graph

popd > /dev/null

# Setelah merge/push selesai dari folder hotfix:
echo "Membersihkan linked worktree..."
git worktree remove "${HOTFIX_DIR}"
git worktree prune

echo "Repositori lokal bersih. Siap melanjutkan fitur utama tanpa resiko state collision."
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Regresi Performa pada Monorepo Pembayaran Skala FinTech
* **Latar Belakang**: Sebuah startup payment gateway memproses ~40.000 TPS. Tim payments melakukan deployment monorepo dengan frekuensi 80 merge/hari.
* **Insiden**: Latensi p99 meningkat dari 12ms ke 480ms setelah deployment release v4.12.0. Rilis tersebut mencakup 1.200 commit gabungan dari 15 tim domain yang berbeda.
* **Tantangan**: Melacak commit mana yang mengintroduksi kebocoran memori/CPU bottleneck secara manual adalah mustahil dalam batas SLA downtime.

### Implementasi Solusi: Automated Git Bisect dengan Regression Harness Script

Tim Core Infrastructure mengimplementasikan skrip validasi micro-benchmark independen (`perf_check.sh`):

```bash
#!/usr/bin/env bash
# perf_check.sh
# Git bisect expects:
# Exit code 0  -> Good/Passed
# Exit code 1-124, 126-255 -> Bad/Failed
# Exit code 125 -> Skip commit (unbuildable state)

set -e

# Compile binary target
go build -o /tmp/engine ./cmd/engine || exit 125

# Eksekusi continuous load test mini (5 detik)
LATENCY=$(/tmp/engine --benchmark --duration=5s | awk '/p99/ {print $2}' | tr -d 'ms')

# Evaluasi threshold: Batas toleransi p99 adalah 20ms
THRESHOLD=20

if (( $(echo "$LATENCY > $THRESHOLD" | bc -l) )); then
    echo "FAILED: Latensi p99 terukur ${LATENCY}ms (melebihi limit ${THRESHOLD}ms)"
    exit 1
else
    echo "PASSED: Latensi p99 terukur ${LATENCY}ms"
    exit 0
fi
```

Eksekusi bisect otomatis di CI/CD:

```bash
# Menentukan baseline commit
git bisect start
git bisect bad v4.12.0               # Titik commit dengan bug latensi
git bisect good v4.11.0              # Titik commit stabil terakhir

# Serahkan pencarian biner sepenuhnya ke Git
git bisect run ./perf_check.sh
```

### Hasil Teknis:
* Pencarian biner memangkas penelusuran **1.200 commit menjadi hanya 11 iterasi** ($\lceil\log_2(1200)\rceil \approx 11$).
* Dalam **4 menit 12 detik**, Git bisect berhasil mengidentifikasi commit spesifik:
  `commit 9b2d87e02... ("perf(metrics): add high-precision thread locking for telemetry")`.
* Tim cukup me-revert commit tersebut menggunakan `git revert 9b2d87e02` tanpa mengganggu 1.199 commit lainnya. Sistem kembali normal dalam 10 menit total.

---

## 9. Trade-offs

| Parameter | Rebase Interaktif / Linear History | Traditional Merge Commits |
| :--- | :--- | :--- |
| **Bentuk DAG** | Sempurna, 1 dimensi, linear string. | Multi-dimensi, graf bergelombang (*diamond patterns*). |
| **Audit Log Analysis** | Mudah dibaca manusia (`git log --oneline`), otomatisasi `git bisect` 100% deterministik. | Sulit ditelusuri secara linier; titik revert ambigu jika terdapat *nested merge commits*. |
| **Integritas Konteks Branch**| Riwayat penggabungan paralel hilang; metadata branch asal terhapus. | Mempertahankan konteks historis kapan dan dari branch mana fitur digabungkan secara presisi. |
| **Tingkat Bahaya Tim** | Tinggi jika dilakukan di public shared branch; mengubah commit SHA secara masif. | Sangat aman untuk shared branch; bersifat *append-only* tanpa modifikasi SHA yang sudah dipublikasikan. |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Blind Force Pushing (`git push --force`)
* **Dampak**: Menimpa commit rekan kerja yang di-push ke remote branch yang sama secara diam-diam (*silent overwrite*).
* **Solusi Perusahaan**: Gunakan proteksi sewa:
  ```bash
  git push --force-with-lease
  ```
  Ini memastikan bahwa remote reference masih berada pada commit yang terakhir kali Anda fetch. Jika orang lain telah melakukan update, push akan di-reject.

### Mistake 2: Staging Area Locking Akibat Kill Process (`.git/index.lock`)
* **Gejala**: Muncul pesan error `fatal: Unable to create '.git/index.lock': File exists.`
* **Akar Masalah**: Proses Git sebelumnya mati tidak normal saat menulis status indeks, meninggalkan lockfile proteksi konkurensi.
* **Troubleshooting**:
  1. Pastikan tidak ada proses Git aktif di background: `pgrep -a git`
  2. Jika proses sudah mati, hapus lockfile tersebut secara manual:
     ```bash
     rm -f .git/index.lock
     ```

### Mistake 3: Kehilangan Commit Penting Akibat Detached HEAD / Rebase Salah
* **Penyelamatan Histori Menggunakan Reflog Forensics**:
  Jika commit hilang pasca `git reset --hard` atau *bad rebase*:
  ```bash
  # 1. Buka history jurnal transaksi reflog
  git reflog show HEAD

  # Output identifikasi SHA sebelum bencana terjadi:
  # 7b21a34 HEAD@{1}: reset: moving to HEAD~5
  # a1c890f HEAD@{2}: commit: feat(billing): critical tax calculation logic

  # 2. Pulihkan state ke branch pemulihan baru
  git branch recovery-branch a1c890f

  # 3. Validasi tree telah kembali
  git log -1 recovery-branch
  ```

---

## 11. Best Practices (Production Checklist)

1. **[ ] Enforce Conventional Commits**: Struktur pesan wajib mematuhi skema format: `<type>(<scope>): <subject>` untuk parsing CI/CD semver otomatis.
2. **[ ] Zero Broken Window via Hooks**: Terapkan client-side verification hook (`pre-commit`) via bash murni untuk memvalidasi syntax, code formatting, dan static analysis.
3. **[ ] Secret Scanning Native**: Tolak commit yang mengandung `.pem`, `.key`, `id_rsa`, atau pattern AWS Key via hook sebelum file sempat masuk ke staging index.
4. **[ ] Sign Every Commit**: Terapkan penandatanganan commit menggunakan kunci kriptografis GPG atau SSH key (`git config --global commit.gpgsign true`).
5. **[ ] Blobless CI Clones**: Gunakan `git clone --filter=blob:none <repo>` pada pipeline runner untuk menghemat bandwidth hingga 85% pada repositori berukuran gigabyte.
6. **[ ] Atomic Single-Purpose Commits**: Hindari commit berukuran ribuan baris dengan fungsi ganda; pisahkan refactoring dan implementasi fitur ke dalam commit berbeda.
7. **[ ] Worktree-Based Hotfixing**: Jangan gunakan `git stash` pada skenario kritis; gunakan `git worktree` untuk menjamin isolasi total.
8. **[ ] Refuse Auto-Merge Polusi**: Matikan opsi fast-forward sembarangan pada pipeline integrasi utama, gunakan rebase branch lokal terlebih dahulu sebelum pull request diintegrasikan.
9. **[ ] Cleanup Dangling References**: Jalankan pembersihan objek usang secara berkala di workspace dev: `git gc --prune=now`.
10. **[ ] Maintain Gitignore Strictness**: Jangan pernah memasukkan file artefak binary, log, file `.env`, atau virtual environment ke dalam version control.
11. **[ ] Branch Protection Rule Base**: Kunci branch `main`/`production` dari opsi push langsung (`push protected`), wajib via Pull Request yang lulus automated test.
12. **[ ] Detached Head Vigilance**: Selalu periksa branch aktif dengan `git status` sebelum memodifikasi kode guna menghindari *dangling object state*.

---

## 12. Hands-on Practice

Buat dan simpan latihan ini pada direktori: `hands-on/m02/`

### Skenario Praktik
Anda bertindak sebagai Platform Engineer yang bertugas membuat script otomatisasi Git Hooks untuk mencegah kebocoran file kredensial (`.env`, private keys) dan memaksakan audit trail berbasis Conventional Commits.

### Langkah 1: Persiapan Environment
```bash
mkdir -p hands-on/m02/enterprise-governance
cd hands-on/m02/enterprise-governance
git init
```

### Langkah 2: Pembuatan Git Hook Script (`.git/hooks/pre-commit`)
Tulis skrip proteksi staging area berikut:

```bash
cat << 'EOF' > .git/hooks/pre-commit
#!/usr/bin/env bash
set -eo pipefail

echo "==> Memulai verifikasi pre-commit security validation..."

# 1. Deteksi Secret Files yang tidak sengaja ter-stage
RESTRICTED_PATTERNS="(\.env|\.pem|\.key|id_rsa|credentials\.json)"
STAGED_FILES=$(git diff --cached --name-only)

for FILE in $STAGED_FILES; do
    if [[ "$FILE" =~ $RESTRICTED_PATTERNS ]]; then
        echo "CRITICAL ERROR: Percobaan commit berkas sensitif diblokir: $FILE"
        echo "Batalkan staging berkas ini menggunakan: git rm --cached $FILE"
        exit 1
    fi
done

# 2. Deteksi Hardcoded Private Key strings di dalam file yang di-stage
if git diff --cached -S"BEGIN PRIVATE KEY" --quiet; then
    : # Bersih, tidak ditemukan
else
    echo "CRITICAL ERROR: Ditemukan teks string 'BEGIN PRIVATE KEY' di dalam staged patch!"
    exit 1
fi

echo "==> Security validation PASSED."
exit 0
EOF

chmod +x .git/hooks/pre-commit
```

### Langkah 3: Pembuatan Git Hook Message Linting (`.git/hooks/commit-msg`)
Pastikan standar penamaan commit dipatuhi:

```bash
cat << 'EOF' > .git/hooks/commit-msg
#!/usr/bin/env bash
set -eo pipefail

COMMIT_MSG_FILE=$1
COMMIT_MSG=$(cat "$COMMIT_MSG_FILE")

# Standard Conventional Commits: type(scope): description
CONVENTIONAL_PATTERN="^(feat|fix|docs|style|refactor|perf|test|chore|ci)(\([a-zA-Z0-9_-]+\))?: .{1,80}$"

if [[ ! "$COMMIT_MSG" =~ $CONVENTIONAL_PATTERN ]]; then
    echo "ERROR: Format pesan commit ditolak!"
    echo "Pesan Anda: $COMMIT_MSG"
    echo "Format wajib: <type>(<optional-scope>): <deskripsi>"
    echo "Contoh: feat(auth): add OAuth2 provider token validation"
    exit 1
fi

echo "==> Commit message PASSED."
exit 0
EOF

chmod +x .git/hooks/commit-msg
```

### Langkah 4: Pengujian Skeptis (Negative & Positive Test)
```bash
# Test 1: Gagal karena file .env
touch .env
git add .env
# Ekspektasi: Gagal di pre-commit
git commit -m "chore(config): add env config" || echo "--> SUKSES DIBLOKIR SECARA TEPAT"
git rm -cached .env && rm .env

# Test 2: Gagal karena format commit salah
touch core.go
git add core.go
# Ekspektasi: Gagal di commit-msg
git commit -m "menambahkan core go" || echo "--> SUKSES DIBLOKIR COMMIT-MSG FORMAT"

# Test 3: Berhasil (Happy Path)
git commit -m "feat(core): implement core engine foundation"
# Ekspektasi: 0 exit code, commit terbuat
```

---

## 13. Exercise

### Level Easy
1. Gunakan perintah `git cat-file -p HEAD` untuk melihat SHA Tree utama. Lalu jalankan `git cat-file -p <tree-sha>` untuk melihat daftar file dan perizinan mode POSIX-nya.
2. Tampilkan isi objek commit terakhir Anda murni dalam bentuk teks raw byte stream menggunakan kombinasi command standard Unix tanpa porcelain `git log`.

### Level Medium
1. Simulasikan skenario *detached HEAD*: checkout langsung ke salah satu commit hash lama.
2. Buat sebuah berkas `untracked.txt`, lakukan commit pada mode detached HEAD tersebut.
3. Kembali ke branch `main`. Tunjukkan bagaimana cara menyelamatkan commit tersebut agar masuk ke dalam branch baru bernama `feature/recovered-state` menggunakan bantuan `git reflog`.

### Level Hard
1. Buat repositori lokal baru dengan 5 commit dummy. 
2. Gunakan `git rebase -i HEAD~4` untuk:
   * Menggabungkan (*squash*) Commit ke-2 dan ke-3 menjadi satu commit utuh.
   * Mengubah isi pesan (*reword*) commit ke-4.
   * Menghapus (*drop*) commit ke-5.
3. Buktikan perubahan integritas DAG dengan membandingkan seluruh SHA sebelum dan sesudah proses rebase dilakukan.

---

## 14. Challenge

### Studi Kasus: Forensic Recovery & Zero-Data-Loss Pipeline

**Skenario**: Seorang junior developer secara tidak sengaja menjalankan urutan perintah berikut di branch integrasi penting (`feature/enterprise-billing`):

```bash
git checkout feature/enterprise-billing
git reset --hard HEAD~10
git clean -fdx
git gc --prune=now
```

Seluruh tim panik karena 10 commit fitur (termasuk implementasi pajak transaksi baru) hilang dari histori log `git log`.

**Tugas Anda Tanpa Bantuan GUI Tool**:
1. Jelaskan secara arsitektural: apakah `git gc --prune=now` benar-benar memusnahkan objek commit yang baru saja di-*dereference* oleh `git reset --hard`?
2. Rekonstruksi skenario tersebut di dalam direktori uji coba lokal.
3. Temukan kembali referensi commit yang melayang (*dangling commit*) menggunakan `git fsck --lost-found`.
4. Pulihkan commit tersebut menjadi branch utuh kembali ke keadaan tepat sebelum perintah `reset --hard` dieksekusi.
5. Buat laporan teknis post-mortem singkat yang menjelaskan mengapa data tersebut masih bisa (atau tidak bisa) diselamatkan berdasarkan arsitektur internal Git.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic Knowledge (Pilihan Ganda & Analisis Pendek)

#### Q1: Di manakah Git menyimpan nama dari sebuah file?
* A. Di dalam payload Blob object
* B. Di dalam file header Blob object
* C. Di dalam entri Tree object
* D. Di dalam Commit object

*Jawaban*: **C**  
*Penjelasan*: Objek Blob hanya berisi stream konten biner/teks murni dari suatu berkas. Informasi nama file, mode perizinan berkas (100644, 100755), dan direktori penyimpanannya dipegang secara eksklusif oleh objek **Tree**.

---

#### Q2: Apa yang terjadi secara internal ketika sebuah branch baru dibuat menggunakan `git branch feature/v1`?
* A. Git menduplikasi seluruh direktori dan file proyek ke direktori baru.
* B. Git membuat file teks baru berukuran 41 byte di `.git/refs/heads/feature/v1` yang berisi SHA-1 dari commit saat ini.
* C. Git membuat objek Tree baru di dalam `.git/objects`.
* D. Git menulis ulang riwayat commit ke dalam index binary file.

*Jawaban*: **B**  
*Penjelasan*: Branch di Git bersifat *lightweight pointer*. Membuat branch baru hanyalah menuliskan file teks kecil (40 karakter heksadesimal hash + 1 karakter newline) yang menunjuk ke commit hash yang sedang aktif.

---

#### Q3: Jika isi dari sebuah file sama persis di 5 direktori yang berbeda dalam satu repositori, berapa banyak objek Blob yang disimpan di dalam `.git/objects/`?
* A. 5 objek Blob terpisah
* B. 1 objek Blob
* C. 1 objek Blob dan 4 symlink
* D. 5 objek Tree

*Jawaban*: **B**  
*Penjelasan*: Git menggunakan *Content-Addressable Storage*. Jika konten file identik, hasil kalkulasi SHA hash-nya pasti sama persis. Git hanya menyimpan satu objek fisik di disk dan mereferensikan SHA yang sama dari entri Tree yang berbeda.

---

#### Q4: Perintah Git manakah yang masuk dalam kategori Plumbing Command?
* A. `git status`
* B. `git commit`
* C. `git write-tree`
* D. `git pull`

*Jawaban*: **C**  
*Penjelasan*: Perintah porcelain dirancang untuk antarmuka pengguna manusia tingkat tinggi (`status`, `commit`, `pull`), sedangkan `write-tree`, `commit-tree`, dan `hash-object` adalah plumbing commands tingkat rendah yang dirancang untuk skrip mesin dan manipulasi internal.

---

#### Q5: Apakah objek commit dapat diubah isinya tanpa merusak nilai Commit SHA Hash-nya?
* A. Bisa, jika author dan committer adalah orang yang sama.
* B. Bisa, asalkan nama filenya tidak berubah.
* C. Tidak bisa, setiap perubahan bit payload akan menghasilkan SHA Hash yang sama sekali berbeda.
* D. Bisa, menggunakan perintah `git commit --amend` tanpa mengubah hash.

*Jawaban*: **C**  
*Penjelasan*: Prinsip *Cryptographic Hash Integrity*. SHA commit dihitung berdasarkan isi Tree, parent SHA, author, committer, timestamp, dan commit message. Mengubah 1 bit karakter pada elemen tersebut akan mengubah total hash hash commit yang dihasilkan (*avalanche effect*).

---

### Bagian B: Intermediate Concepts

#### Q6: Mengapa eksekusi `git rebase` pada commit yang telah dipublikasikan ke remote public branch dianggap sebagai operasi berbahaya?
*Jawaban & Penjelasan Teknis*:
Karena `rebase` bekerja dengan cara **membuat commit baru** (SHA baru) dan mengabaikan commit lama, meskipun diff isinya sama. Jika commit lama sudah di-pull oleh kontributor lain, riwayat commit lokal mereka akan bercabang/divergen dari remote yang telah di-rebase. Ketika mereka melakukan push/pull berikutnya, akan tercipta merge commit duplikat yang berantakan (*duplicate historical graph*), merusak histori pelacakan regresi.

---

#### Q7: Jelaskan perbedaan fundamental antara referensi `HEAD` dan referensi `ORIG_HEAD`!
*Jawaban & Penjelasan Teknis*:
* **`HEAD`**: Simbolik pointer aktif yang melacak commit/cabang yang sedang dibuka di working tree saat ini.
* **`ORIG_HEAD`**: Mekanisme backup otomatis Git yang menyimpan posisi commit `HEAD` sebelum dilakukannya operasi drastis yang berpotensi memindahkan pointer jauh (seperti `git merge`, `git reset`, atau `git rebase`). Ini memungkinkan pembatalan instan via `git reset ORIG_HEAD`.

---

#### Q8: Apa perbedaan mendasar antara `git clean -f` dan `git reset --hard`?
*Jawaban & Penjelasan Teknis*:
* `git reset --hard`: Mengubah dan mengembalikan berkas-berkas yang sudah **terlacak (*tracked files*)** di staging index dan commit database agar cocok dengan titik referensi commit tertentu. Berkas yang tidak terlacak (*untracked*) tidak disentuh sama sekali.
* `git clean -f`: Bekerja secara eksklusif untuk menghapus berkas-berkas baru yang **belum terlacak (*untracked files*)** dari working tree fisik lokal.

---

#### Q9: Kapan kondisi `git worktree` jauh lebih unggul dibandingkan melakukan kloning repositori secara mandiri (`git clone`) ke folder baru?
*Jawaban & Penjelasan Teknis*:
`git worktree` memanfaatkan basis data `.git` yang sama (berbagi objek, packfile, dan refs yang sudah ada). Hal ini menghasilkan:
1. **Zero disk duplication**: Tidak perlu men-download atau menduplikasi gigabytes *object store*.
2. **Instant setup**: Pembuatan direktori kerja baru memakan waktu kurang dari 1 detik.
3. **Synchronized state**: Branch yang di-fetch pada worktree utama langsung tersedia di linked worktree tanpa perlu re-fetching dari remote.

---

#### Q10: Bagaimana arsitektur packfile (`.pack` dan `.idx`) mengatasi inefisiensi ruang pada penyimpanan objek *loose* di Git?
*Jawaban & Penjelasan Teknis*:
Secara default, Git menyimpan file sebagai objek loose (1 file zlib per objek). Ketika file sering dimodifikasi, Git menyimpan snapshot penuh berkas di tiap revisi. Melalui `git gc`, Git menyatukan ribuan objek loose ke dalam satu file binary besar (`.pack`) menggunakan algoritma kompresi delta canggih (menyimpan versi terbaru secara penuh, dan versi lama murni sebagai diff/delta). File indeks (`.idx`) memetakan SHA commit ke byte-offset presisi di dalam file `.pack` untuk pencarian berkecepatan $O(1)$.

---

### Bagian C: Skenario Kasus Produksi

#### Skenario 1: CI/CD Pipeline Monorepo Mengalami Out-Of-Memory (OOM)
* **Kasus**: Pipeline CI/CD Monorepo berukuran 40GB selalu OOM dan memakan waktu 28 menit hanya pada tahap `git clone` di AWS CodeBuild runner.
* **Solusi Arsitektur**:
  1. Ganti strategi clone default dengan **Blobless Clone**:
     ```bash
     git clone --filter=blob:none --no-checkout <repo_url> .
     ```
     Pipeline hanya mengunduh seluruh commit graph dan tree structure tanpa satupun isi berkas (blob).
  2. Lakukan checkout spesifik hanya pada commit/branch yang dieksekusi:
     ```bash
     git checkout $CI_COMMIT_SHA
     ```
     Git hanya akan mengunduh blob yang relevan untuk commit tersebut secara *on-demand*.
  3. Terapkan **Sparse-Checkout** jika pipeline hanya menguji satu microservice tertentu:
     ```bash
     git sparse-checkout set services/payment-gateway
     ```
* **Hasil**: Waktu kloning terpangkas dari 28 menit menjadi di bawah 45 detik, dan penggunaan memori berkurang hingga 90%.

---

#### Skenario 2: Secret Database Terlanjur Masuk ke dalam Histori Commit 3 Bulan Lalu
* **Kasus**: File konfigurasi `staging.env` berisi credential production AWS RDS di-commit 150 commit yang lalu dan telah terdorong ke remote GitHub Enterprise. Melakukan delete file di commit terbaru tidak menghapus password tersebut dari database historis `.git`.
* **Solusi Arsitektur**:
  1. Menggunakan tool native `git-filter-repo` (pengganti modern dari `git filter-branch` yang deprecated):
     ```bash
     git filter-repo --invert-paths --path staging.env --force
     ```
  2. Eksekusi ini secara matematis menulis ulang (*rewrite*) seluruh SHA hash dari commit titik insiden hingga HEAD.
  3. Paksa dereference objek dangling dan hapus reflog:
     ```bash
     git reflog expire --expire=now --all
     git gc --prune=now
     ```
  4. Lakukan koordinasi force-push terproteksi ke upstream dan wajibkan seluruh tim melakukan clone baru (*fresh checkout*).
  5. Rotasi kredensial AWS RDS secara instan di AWS IAM/KMS (asumsikan secret sudah kompromi).

---

#### Skenario 3: Penyelamatan Branch Saat Terjadi Merge Conflict Masif pada Rebase
* **Kasus**: Seorang teknisi menjalankan `git rebase main` pada branch fiturnya yang tertinggal 400 commit. Terjadi konflik rumit pada commit ke-4 dari 400. Teknisi tersebut panik dan mencoba berbagai perintah hingga staging area rusak parah dan command terminal menampilkan status `(rebase 4/400)`.
* **Solusi Arsitektur & Tindakan**:
  1. Hentikan proses rebase seketika dan kembalikan state repositori ke kondisi sebelum perintah rebase dieksekusi menggunakan:
     ```bash
     git rebase --abort
     ```
  2. Jika `--abort` gagal karena indeks rusak manual:
     Gunakan reflog commit branch sebelum rebase dijalankan:
     ```bash
     git reflog show feature-branch
     # Cari titik sebelum 'rebase: checkout main'
     git reset --hard feature-branch@{1}
     ```
  3. Strategi alternatif yang aman: Buat cabang replika untuk pengujian, lalu gunakan teknik squash commit lokal terlebih dahulu agar 400 commit tersebut diringkas menjadi 1-3 commit fitur yang kohesif sebelum direbase ke `main`:
     ```bash
     git checkout -b feature-branch-rebase-prep
     git reset --soft main
     git commit -m "feat(module): aggregate feature implementations"
     git rebase main
     ```

---

## 16. Summary

1. **Git adalah Content-Addressable Storage**: File dan histori disimpan sebagai objek berbasis checksum kriptografis. Perubahan 1 bit data akan mengubah SHA secara cascading.
2. **Porcelain vs Plumbing**: Perintah harian (`add`, `commit`, `status`) adalah lapisan kosmetik (*porcelain*). Mesin sesungguhnya beroperasi melalui perintah *plumbing* (`hash-object`, `write-tree`, `commit-tree`, `update-ref`) yang memanipulasi Directed Acyclic Graph (DAG) secara langsung.
3. **Ekosistem 4 Objek Primitif**: Arsitektur Git tersusun dari kombinasi atomik: **Blob** (data isi), **Tree** (struktur hierarki/nama berkas), **Commit** (relasi riwayat dan metadata), serta **Annotated Tag** (marker rilis statis).
4. **Isolasi Mutlak Melalui Worktree**: Hilangkan context-switching overhead dan resiko data hilang dari `git stash` pada penanganan insiden paralel dengan mendistribusikan pengerjaan ke `git worktree`.
5. **Kekuatan Otomasi Forensik**: Pemanfaatan `git bisect` berbasis skrip tes otomatis mengubah proses isolasi bug dari manual yang melelahkan menjadi pencarian biner deterministik $O(\log n)$ berstandar industri.