# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (Git & GitHub Enterprise)

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis & Mengimplementasikan Strategi Integrasi Branching Tingkat Lanjut**: Mampu mengevaluasi dan memilih secara presisi antara *Trunk-Based Development (TBD)*, *Gitflow*, dan *Environment-Branching* berdasarkan metrik DORA (*Deployment Frequency*, *Lead Time for Changes*, *MTTR*, *Change Failure Rate*).
- **Menguasai Mekanika Internal Merge Engine & Rebase DAG Topology**: Membedakan algoritma `ort` (*Ostrogoth Re-implementation of Trivially-recursive merge*) vs recursive 3-way merge, mengoperasikan *interactive rebase* dengan strategi preservasi topologi, dan menavigasi dynamic tree conflict.
- **Mengotomatisasi Forensik Repositori & Pemulihan Disaster Recovery**: Mengisolasi regresi kode menggunakan `git bisect run` berbasis script otomatis, serta merekonstruksi riwayat commit yang hilang menggunakan `git reflog`, `git fsck --lost-found`, dan manipulasi direct plumbing object.
- **Mendesain Arsitektur Repositori Skala Enterprise**: Mengelola modularitas kode melalui Git Submodules (gitlink mode `160000`), Git Subtrees, Git LFS (*Large File Storage*) dengan custom smudge/clean filter drivers, dan optimasi monorepo (`scalar`, `sparse-checkout`, `commit-graph`).
- **Membangun Enforce Security & Governance Gates**: Mengembangkan client-side dan server-side Git Hooks (`pre-commit`, `commit-msg`, `pre-receive`), mengonfigurasi GPG/SSH commit signature verification, serta menerapkan enterprise branch protection rulesets dan Merge Queues pada GitHub Enterprise Server/Cloud.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, pastikan workstation dan wawasan teknis Anda telah memenuhi kriteria berikut:

### Kebutuhan Pengetahuan
- Memahami struktur fundamental direktori `.git` (Blob, Tree, Commit, Annotated Tag) dari Module 01.
- Mahir dalam eksekusi perintah dasar Porcelain (`git status`, `git add`, `git commit`, `git checkout`, `git branch`).
- Memahami konsep dasar kriptografi kunci asimetris (Public/Private Key) untuk SSH dan GPG.

### Kebutuhan Tooling & Environment
- **Git Engine**: Git versi 2.40.0 atau lebih tinggi (disarankan versi terbaru untuk memanfaatkan algoritma merge `ort` dan fitur `scalar`).
  ```bash
  git --version
  ```
- **Shell**: Bash atau Zsh pada lingkungan UNIX-like (Linux, macOS, atau WSL2 di Windows).
- **GPG Suite**: `gnupg` terinstal untuk menandatangani commit secara kriptografis.
  ```bash
  gpg --version
  ```
- **Git LFS Extension**: Terpasang dan terinisialisasi.
  ```bash
  git lfs version
  ```
- **Editor**: Editor berbasis terminal (`vim`, `nano`) atau visual (`code` / VSCode) yang terkonfigurasi sebagai git editor:
  ```bash
  git config --global core.editor "code --wait"
  ```

---

## 3. Concept & Internal Architecture

### 3.1 Anatomi 3-Way Merge & Algoritma `ort`
Ketika dua branch divergen disatukan melalui *merge*, Git tidak membandingkan state akhir kedua branch secara langsung (2-way diff). Git menggunakan **3-Way Merge Algorithm**.

```
    B---C  (feature)
   /
  A        (LCA - Lowest Common Ancestor)
   \
    D---E  (main)
```

1. **Lowest Common Ancestor (LCA)**: Git menelusuri DAG (*Directed Acyclic Graph*) ke belakang untuk menemukan commit bersama terakhir sebelum divergensi ($A$).
2. **Diff Generation**:
   - $\Delta_1 = Diff(A, C)$ (perubahan pada `feature`)
   - $\Delta_2 = Diff(A, E)$ (perubahan pada `main`)
3. **Merge Application**: Git mengaplikasikan $\Delta_1$ dan $\Delta_2$ secara simultan ke snapshot $A$.
   - Jika $\Delta_1$ mengubah baris $X$ dan $\Delta_2$ tidak menyentuh baris $X$, perubahan $\Delta_1$ diterima otomatis.
   - Jika $\Delta_1$ dan $\Delta_2$ memodifikasi baris $X$ dengan isi berbeda, terjadi **Merge Conflict**.

Mesin default Git modern adalah **`ort` (Ostrogoth Re-implementation of Trivially-recursive)**, menggantikan mesin `recursive` warisan. `ort` dirancang ulang dari nol untuk:
- Mengurangi re-indexing berkali-kali pada kasus LCA multipel (saat terjadi criss-cross merges).
- Mengoptimalkan dynamic rename detection secara eksponensial lebih cepat dengan melakukan deteksi hanya pada direktori terdampak, bukan memindai keseluruhan repositori.
- Menyimpan resolusi konflik di memori sebelum menulis blob baru ke dalam *Object Database*, mengurangi I/O disk secara masif pada monorepo skala enterprise.

### 3.2 Rebase: Linearizing the Graph Topology
Rebase secara fundamental adalah proses **cherry-pick serial otomatis**. 

```
Initial State:
A---B---C (main)
     \
      D---E (topic)

Langkah git rebase main (dijalankan di branch topic):
1. Git mencari LCA: B
2. Git menyimpan delta commit D (ΔD = Diff(B, D)) dan E (ΔE = Diff(D, E)) ke temporary patch files di .git/rebase-apply/ atau .git/rebase-merge/.
3. Git me-reset HEAD topic ke target ref (commit C): HEAD dipaksa menunjuk ke C.
4. Git mengaplikasikan ΔD di atas C, menghasilkan commit baru D' (SHA-1/SHA-256 berubah total).
5. Git mengaplikasikan ΔE di atas D', menghasilkan commit baru E'.

Final State:
A---B---C (main)
         \
          D'---E' (topic)
```
Setiap commit hasil rebase ($D'$, $E'$) memiliki:
- Tree object baru (jika ada adaptasi kode terhadap C).
- Parent pointer yang baru ($D'$ menunjuk ke $C$, bukan $B$).
- Author Date tetap sama, tetapi **Committer Date** dan **Committer Identity** diperbarui ke waktu eksekusi rebase.
- Hash SHA yang sepenuhnya berbeda.

### 3.3 Lifecycle Git Hooks Engine
Hooks adalah executable script yang dipicu oleh Git lifecycle events. Terletak di direktori `.git/hooks/` (atau direktori yang ditentukan via `core.hooksPath`).

```
CLIENT-SIDE WORKFLOW:
[Working Directory Changes]
        │
        ▼
   `git commit`
        │
        ├─► [hook: pre-commit] (Linting, Static Analysis, Secret Scanning)
        │     └─► Exit != 0 ? ABORT COMMIT : Continue
        │
        ├─► [hook: prepare-commit-msg] (Injeksi template/issue key otomatis)
        │
        ├─► [hook: commit-msg] (Validasi format: Conventional Commits via Regex)
        │     └─► Exit != 0 ? ABORT COMMIT : Continue
        │
        └─► [hook: post-commit] (Notifikasi, metrics tracking)
        │
        ▼
[Commit Recorded in DAG]
        │
        ▼
    `git push`
        │
        └─► [hook: pre-push] (Validasi branch, LFS sanity check)
              └─► Exit != 0 ? ABORT PUSH : Send Packfile to Remote
```

```
SERVER-SIDE WORKFLOW (GitHub Enterprise / Bare Repo):
[Receive Packfile via SSH/HTTPS]
        │
        ▼
   `git-receive-pack`
        │
        ├─► [hook: pre-receive] (Central Policy: reject unsigned commits, 
        │                        large files, invalid branch names)
        │     └─► Exit != 0 ? REJECT ENTIRE PUSH : Continue
        │
        ├─► [hook: update] (Dieksekusi per-ref update)
        │     └─► Exit != 0 ? REJECT REF : Continue
        │
        ▼
[Update References (refs/heads/*)]
        │
        └─► [hook: post-receive] (Trigger CI/CD Webhook, Jira sync)
```

### 3.4 Git LFS (Large File Storage) Architecture
Git didesain untuk melacak delta teks, bukan binary delta. Menyimpan aset biner besar (misal: model ML `.onnx`, file video `.mp4`, artifact kompilasi `.zip`) langsung ke Git akan menyebabkan repositori membengkak secara eksponensial (*bloat*) karena Git menyimpan kompresi zlib dari seluruh file baru untuk setiap modifikasi, bukan delta baris.

Git LFS memodifikasi perilaku ini dengan mengintegrasikan **Smudge & Clean Filters** pada Git Attributes:

```
+-----------------------------------------------------------------------------------+
| WORKING DIRECTORY                       GIT OBJECT STORE (.git/objects)           |
|                                                                                   |
|  [ large_model.bin ]                      [ Pointer File (Blob) ]                  |
|      (Size: 2GB)                             version https://git-lfs.github.com/v1|
|           │                                  oid sha256:e3b0c44298fc1c149af...    |
|           │ `git add`                        size 2147483648                      |
|           │ (CLEAN FILTER)                           ▲                            |
|           ├──────────────────────────────────────────┘                            |
|           │                                                                       |
|           ▼ Transfer binary via HTTP/S3                                           |
|   +──────────────────+                                                            |
|   | Git LFS Server / |                                                            |
|   | S3 Object Storage|                                                            |
|   +──────────────────+                                                            |
|           ▲                                                                       |
|           │ `git checkout`                                                        |
|           │ (SMUDGE FILTER)                                                       |
|           └──────────────────────────────────────────┐                            |
|                                                      ▼                            |
|                                           [ large_model.bin ]                     |
|                                               (Restored 2GB)                      |
+-----------------------------------------------------------------------------------+
```
1. **Clean Filter (`git add`)**: Binary di-intersep. Git LFS menghitung checksum SHA-256 binary tersebut, mengunggah payload asli ke LFS Store (misal: AWS S3), dan menggantinya di staging area dengan file teks kecil berupa **LFS Pointer** (~130 bytes).
2. **Smudge Filter (`git checkout`)**: Ketika Git membaca tree object dan menemukan pointer LFS, Smudge filter mengunduh binary yang sesuai dari LFS Server berdasarkan OID (Object Identifier) SHA-256 dan merestorasi file asli ke working tree.

---

## 4. Why & What

| Dimensi | Pendekatan Monolitik / Naif | Arsitektur Enterprise Lanjutan | Dampak Bisnis / Rekayasa |
| :--- | :--- | :--- | :--- |
| **Branching Strategy** | Gitflow Tradisional (Banyak long-lived branch: `develop`, `release`, `feature`, `hotfix`). | Trunk-Based Development (TBD) dengan Short-lived Feature Branches (< 24 jam) + Feature Flags. | Memangkas *Lead Time for Changes* dari hitungan minggu ke jam. Menghilangkan fenomena *Merge Hell* di akhir sprint. |
| **Integrasi Riwayat (Merge Policy)** | Ad-hoc (Bebas memilih merge commit, fast-forward, atau rebase secara inkonsisten). | Enforced Squash-Merge pada PR, Linear History di branch `main`. | Audit visual DAG menjadi linear, bersih, dan mempermudah rollback atomic (`git revert <squash-commit-hash>`). |
| **Integrasi Eksternal** | Copy-paste code dependency langsung ke repo. | Git Submodules (fixed gitlink SHA) atau Git Subtrees (embedded history merge). | Isolasi dependensi terjamin, trace audibilitas dependensi akurat, compliance lisensi terjaga. |
| **Asset Management** | Binary besar di-commit langsung ke Git packfile. | Git LFS + `.gitattributes` strict pattern matching. | Mencegah clone time membengkak dari puluhan gigabyte menjadi megabyte. Operasi remote menjadi jauh lebih cepat. |
| **Governance & Quality** | Review manual tanpa automated gates; developer push langsung ke branch utama. | Signed Commits (GPG/SSH) + CI Merge Queues + CODEOWNERS + Server-side Branch Rulesets. | Mencegah impersonation attack, zero-defect release ke production, proteksi audit SOC2 & ISO 27001. |

---

## 5. How: Workflow Detail

### 5.1 Implementasi Trunk-Based Development & Linear History Enforcement
Dalam arsitektur enterprise, branch `main` harus selalu berada dalam kondisi deployable (*always releasable*).

```
1. Sync master local
   git checkout main && git pull --rebase origin main

2. Buat short-lived branch (maksimal masa hidup: 1-2 hari)
   git checkout -b feat/checkout-idempotency

3. Lakukan commits dengan atomic standards (Conventional Commits)
   git commit -m "feat(checkout): implement idempotency key cache via redis"

4. Sync berkala dengan upstream main (hindari divergence masif)
   git fetch origin
   git rebase origin/main

5. Squash & Rebase secara lokal jika commit history internal masih berantakan
   git rebase -i HEAD~3

6. Push branch & buka Pull Request
   git push origin feat/checkout-idempotency

7. Integrasi via Merge Queue di GitHub (Squash and Merge) -> DAG master tetap linear.
```

### 5.2 Forensic Diagnosis Menggunakan Automated `git bisect`
Ketika bug lolos ke production dan commit pool berjumlah ratusan, pelacakan manual tidak efektif. Gunakan algoritma *Binary Search* otomatis milik Git.

```
       B1  B2  B3  B4  B5  B6  B7  B8 (HEAD - Bad)
       |---|---|---|---|---|---|---|
Good (v1.0)                     Bad (v1.1)

Langkah Algoritmik Bisect:
1. Git menandai v1.0 = GOOD, HEAD = BAD. Range = 8 commits.
2. Git mengkalkulasi titik tengah (B4) dan melakukan checkout otomatis.
3. Automated test script dijalankan via `git bisect run <script>`.
4. Jika script exit 0 (PASS) -> range berpindah ke B5..B8 (B4 ditandai GOOD).
5. Jika script exit != 0 (FAIL) -> range berpindah ke B1..B3 (B4 ditandai BAD).
6. Proses diulang secara logaritmik: O(log N). Dari 1.000 commit, akar masalah ditemukan dalam maksimal 10 iterasi.
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Jalur Rel Kereta Api dan Merge Strategies
Bayangkan commit adalah gerbong kereta api dan branch adalah jalur rel kereta.

- **3-Way Merge (`--no-ff`)**: Membangun jalur rel baru (`feature`) yang bercabang dari rel utama (`main`). Saat penggabungan, dibangun stasiun persimpangan baru (*Merge Commit*) yang menyambungkan kedua rel. Jalur lama tetap bercabang secara permanen.
- **Fast-Forward Merge (`--ff`)**: Rel baru dibangun lurus menyambung ujung rel lama tanpa ada percabangan baru sama sekali. Jarum rel hanya digeser maju (*pointer advance*).
- **Interactive Rebase**: Memotong rel `feature` dari titik percabangan lama, mengangkat seluruh gerbongnya satu per satu, lalu mengelasnya langsung di ujung gerbong terdepan rel `main`.
- **Squash Merge**: Mengambil seluruh muatan kargo dari 10 gerbong di rel `feature`, memadatkannya ke dalam satu kontainer raksasa, lalu menaruhnya sebagai satu gerbong tunggal di ujung rel `main`. Riwayat internal 10 gerbong tersebut dibuang dari rel utama.

```
--- MERGE COMMIT (3-Way Merge) ---
main:    A---B-------C-------M (Merge Commit memiliki 2 parent: C & F)
              \             /
feature:       D---E-------F

--- REBASE (Linearized History) ---
Sebelum Rebase:
main:    A---B---C
              \
feature:       D---E

Setelah `git rebase main` pada branch feature:
main:    A---B---C
                  \
feature:           D'---E' (SHA berubah total, parent D' adalah C)

--- SQUASH AND MERGE ---
main:    A---B---C-----------S (Commit S berisi akumulasi perubahan D+E+F)
              \             /
feature:       D---E---F---┘ (Branch feature dihapus setelah merge)
```

---

## 7. Simple & Practical Examples

### 7.1 Automated Git Bisect dengan Exit Codes
Skenario: Terjadi penurunan performa pada fungsi `calculate_tax()`. Kita membuat script tes reproduksi untuk dioperasikan oleh `git bisect`.

**Test Script: `test_regression.sh`**
```bash
#!/usr/bin/env bash
# Exit 0 jika test PASS (Good commit)
# Exit 1 jika test FAIL (Bad commit)
# Exit 125 jika commit tidak bisa di-test (misal build broken di luar konteks)

set -e

# Setup environment / compile jika diperlukan
# npm install / make / cargo check

# Eksekusi unit test spesifik
python3 -m unittest tests/test_tax.py > /dev/null 2>&1

STATUS=$?

if [ $STATUS -eq 0 ]; then
    exit 0
else
    exit 1
fi
```

**Eksekusi Bisect Otomatis**:
```bash
# 1. Mulai bisect engine
git bisect start

# 2. Tandai commit saat ini (misal commit rusak) sebagai bad
git bisect bad HEAD

# 3. Tandai release terakhir yang stabil sebagai good
git bisect good v2.4.0

# 4. Berikan kontrol sepenuhnya ke script automasi
git bisect run ./test_regression.sh

# Output Terminal Otomatis:
# Bisecting: 12 revisions left to test after this (roughly 4 steps)
# ... running ./test_regression.sh
# ...
# d3b07384d113edec49eaa6238ad5ff001920ef83 is the first bad commit
# commit d3b07384d113edec49eaa6238ad5ff001920ef83
# Author: Developer <dev@enterprise.com>
# Date:   Mon Oct 23 14:02:11 2023 +0700
#
#     perf(tax): refactor rounding math algorithm

# 5. Reset HEAD kembali ke state awal
git bisect reset
```

### 7.2 Implementasi Production Pre-Commit Hook (Validasi Linting & Secret Leaks)
Simpan file ini di `.githooks/pre-commit` (gunakan `git config core.hooksPath .githooks` agar dapat di-version control):

```bash
#!/usr/bin/env bash
# ==============================================================================
# Enterprise Pre-Commit Hook: Linting & Secret Detection
# ==============================================================================

set -eo pipefail

echo "==> [HOOK] Menjalankan validasi pre-commit..."

# 1. Deteksi file terlarang atau secret key tidak sengaja masuk staging
FORBIDDEN_PATTERNS=(
    "BEGIN RSA PRIVATE KEY"
    "BEGIN OPENSSH PRIVATE KEY"
    "ghp_[a-zA-Z0-9]{36}"          # GitHub Personal Access Token
    "AKIA[0-9A-Z]{16}"             # AWS Access Key ID
    "eyJhbGciOi"                   # JWT Token header
)

STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM)

if [ -z "$STAGED_FILES" ]; then
    exit 0
fi

echo "--> Memeriksa kebocoran credentials/secrets..."
for PATTERN in "${FORBIDDEN_PATTERNS[@]}"; do
    if git diff --cached -S"$PATTERN" --pickaxe-regex --quiet; then
        : # Pattern tidak ditemukan, aman
    else
        echo "❌ [SECURITY VIOLATION] Terdeteksi pola credentials sensitif: '$PATTERN'"
        echo "   Commit dibatalkan. Bersihkan secret sebelum melakukan commit!"
        exit 1
    fi
done

# 2. Enforce Linting / Format Checker pada file staged
echo "--> Menjalankan static check pada staged files..."
for FILE in $STAGED_FILES; do
    if [[ "$FILE" =~ \.py$ ]]; then
        if command -v flake8 >/dev/null 2>&1; then
            flake8 "$FILE" || { echo "❌ Flake8 violation pada $FILE"; exit 1; }
        fi
    elif [[ "$FILE" =~ \.(js|ts)$ ]]; then
        if command -v eslint >/dev/null 2>&1; then
            npx eslint "$FILE" || { echo "❌ ESLint violation pada $FILE"; exit 1; }
        fi
    fi
done

echo "✅ [HOOK] Seluruh validasi pre-commit lolos."
exit 0
```

### 7.3 Commit-Msg Hook: Enforcing Conventional Commits Specification
Simpan file ini di `.githooks/commit-msg`:

```bash
#!/usr/bin/env bash
# ==============================================================================
# Enterprise Commit-Msg Hook: Conventional Commits Compliance
# Pattern: <type>(<scope>): <subject> (max 72 chars)
# ==============================================================================

COMMIT_MSG_FILE=$1
COMMIT_MSG=$(head -n 1 "$COMMIT_MSG_FILE")

# Regular Expression untuk Conventional Commits
REGEX="^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-z0-9_-]+\))?: .{1,72}$"

if ! [[ "$COMMIT_MSG" =~ $REGEX ]]; then
    echo "❌ [INVALID COMMIT MESSAGE]"
    echo "Pesan commit tidak memenuhi format Conventional Commits!"
    echo "Format yang diharapkan:"
    echo "  <type>(<scope>): <deskripsi>"
    echo "Contoh:"
    echo "  feat(auth): implement oauth2 token rotation"
    echo "  fix(db): handle connection pool timeout gracefully"
    echo ""
    echo "Pesan Anda saat ini:"
    echo "  \"$COMMIT_MSG\""
    exit 1
fi

echo "✅ [HOOK] Commit message valid."
exit 0
```

---

## 8. Real-World Case Study (Enterprise Scale)

### Kasus: High-Throughput Monorepo Scale-Out pada Bank Digital Global

#### Konteks & Masalah
Sebuah bank digital memiliki monorepo backend yang diakses oleh 450+ software engineer. Terjadi masalah skalabilitas kritis:
1. **Merge Contention & Flaky Master**: Sekitar 120 PR di-merge setiap hari secara manual menggunakan 3-Way Merge (`--no-ff`). Cabang `main` sering mengalami *broken build* karena *semantic merge conflict* (secara git merge tidak ada syntax conflict, tetapi interface kode yang diubah di branch A mematahkan logika branch B yang di-merge hampir bersamaan).
2. **Packfile Explosion**: Developer sering secara tidak sengaja meng-commit mock dataset JSON berukuran ratusan MB dan binari `.jar` lokal. Ukuran clone repositori `.git` mencapai **48 GB**, menyebabkan waktu setup CI runner memakan waktu 35 menit per build.
3. **Audit Compliance (SOC2 / OJK)**: Tim auditor menemukan sejumlah commit anonim atau commit dengan email fiktif tanpa tanda tangan kriptografis, melanggar asas *non-repudiation*.

#### Solusi Arsitektural
Engineering Directorate mengeksekusi transformasi arsitektur Git repositori dalam tiga fase:

```
+---------------------------------------------------------------------------------------------------+
| PIPELINE MERGE QUEUE & SECURITY ARCHITECTURE                                                      |
|                                                                                                   |
|  Developer Workstation           GitHub Enterprise                  CI Integration Engine         |
|  ┌──────────────────┐           ┌────────────────────────┐         ┌─────────────────────────┐    |
|  │ Signed Commits   │           │ Branch Rulesets Enforced:│        │ Ephemeral Test Run      │    |
|  │ GPG / SSH Key    │──Push────►│ - Require GPG Signature │         │ (Parallel Pods)         │    |
|  └──────────────────┘           │ - CODEOWNERS Approval  │         └────────────┬────────────┘    |
|                                 │ - Linear History Only  │                      ▲                 |
|                                 └───────────┬────────────┘                      │                 |
|                                             │ PR Approved                       │ Validasi        |
|                                             ▼                                   │ Status          |
|                                 ┌────────────────────────┐                      │                 |
|                                 │ GitHub Merge Queue     │──────────────────────┘                 |
|                                 │ (Speculative Rebase:   │                                        |
|                                 │  main + PR1 + PR2)     │──Passed Tests──► Fast-Forward          |
|                                 └────────────────────────┘                  Commit ke Branch Main |
+---------------------------------------------------------------------------------------------------+
```

1. **Purging History & Implementasi Git LFS**:
   - Menggunakan `git-filter-repo` untuk membersihkan binary historis dari DAG monorepo, mereduksi ukuran repositori dari 48 GB menjadi **1.2 GB**.
   - Menerapkan `.gitattributes` strict dengan ekstensi LFS wajib:
     ```gitattributes
     *.zip filter=lfs diff=lfs merge=lfs -text
     *.tar.gz filter=lfs diff=lfs merge=lfs -text
     *.onnx filter=lfs diff=lfs merge=lfs -text
     *.parquet filter=lfs diff=lfs merge=lfs -text
     ```
2. **GitHub Merge Queue Execution**:
   - Meniadakan tombol direct "Merge Pull Request". Mengaktifkan **Merge Queue**.
   - Merge Queue menguji Pull Request secara spekulatif dalam tumpukan antrean (*speculative rebase batches*). Jika 5 PR masuk antrean, runner CI menguji kombinasi inkremental:
     - Target 1: `main + PR1`
     - Target 2: `main + PR1 + PR2`
   - Jika PR1 lolos dan PR2 gagal, PR2 secara otomatis di-eject dari antrean tanpa merusak branch `main`, dan PR1 langsung di-merge via Fast-Forward. Zero broken builds di `main`.
3. **Enforced Cryptographic Signing & Identity Verification**:
   - Menolak seluruh commit yang tidak ditandatangani via GitHub Ruleset: `Require signed commits = true`.
   - Mengonfigurasi CI untuk memvalidasi bahwa email committer wajib identik dengan identitas GPG/SSH key yang terdaftar di database SSO perusahaan.

#### Hasil Terukur
- Waktu clone repository di CI runner turun dari **35 menit menjadi 42 detik** (menggunakan cache dan sparse-checkout).
- Build failure di branch `main` turun hingga **0%** (*zero regressions in main branch*).
- Status audit SOC2 untuk kontrol integritas repositori meraih status komparatif **100% compliant**.

---

## 9. Trade-offs & Engineering Decisions

Dalam mendesain alur kerja Git enterprise, arsitek sistem harus memilih kompromi yang tepat:

```
                      STRATEGI INTEGRASI CABANG
                                  ▲
                                 / \
                                /   \
          Linear History       /     \  Full Traceability
          (Rebase & Squash)   /       \ (3-Way Merge Commits)
                             /_________\
                            Kognitif Tim
                          (Simplicity vs Audit)
```

| Parameter | 3-Way Merge (`--no-ff`) | Squash & Merge | Rebase & Fast-Forward |
| :--- | :--- | :--- | :--- |
| **Bentuk DAG** | Non-linear, banyak loop branching paralel. | Linear mutlak (1 PR = 1 Commit di main). | Linear murni (Semua commit PR dipindahkan ke main). |
| **Preservasi Konteks** | **Tinggi**: Seluruh sejarah commit eksperimen/WIP tersimpan. | **Rendah**: Menghapus seluruh micro-commits; hanya menyisakan deskripsi PR. | **Tinggi**: Setiap commit individual dipertahankan secara diskrit. |
| **Operasi `git revert`** | Sulit: Memerlukan penentuan flag `-m parent-number` (rentan salah revert). | **Sangat Mudah**: Mengembalikan commit tunggal mengembalikan seluruh fitur. | Menengah: Harus me-revert sejumlah commit penyusun fitur secara urut. |
| **Risiko Merge Conflict** | Ditangani saat penggabungan PR. | Ditangani saat penyatuan PR. | Bisa memicu conflict berulang pada setiap commit yang di-apply ulang. |
| **GPG Signing Impact** | Signature asli developer di setiap commit tetap utuh. | Signature dibuat baru oleh committer yang melakukan squash (sering kali GitHub web/bot). | Signature commit lokal invalidated jika rebase dijalankan tanpa setup autore-sign (`-S`). |

### Modularitas: Git Submodules vs Git Subtrees vs Monorepo Single Tree

| Kategori | Git Submodule | Git Subtree | Native Monorepo |
| :--- | :--- | :--- | :--- |
| **Mekanisme** | Menyimpan pointer SHA-1 (mode `160000`) ke repo eksternal. | Menggabungkan commit tree repo luar langsung ke subdirectory repo lokal. | Seluruh service/kode berada dalam satu Git Tree yang sama. |
| **Developer Overhead** | **Sangat Tinggi**: Wajib memahami `submodule update --init --recursive`, commit detached HEAD. | **Rendah**: Developer biasa memperlakukan kode seperti subdirektori normal. | **Nol**: Tidak membutuhkan manipulasi tooling Git modular terpisah. |
| **Cloning Speed** | Fleksibel: Bisa memilih tidak meng-clone submodule jika tidak butuh. | Lambat: Repositori utama membawa salinan riwayat commit direktori tersebut. | Butuh optimasi: Memerlukan `sparse-checkout` dan `cone-mode` jika repo > 10GB. |
| **Atomic Updates** | **Mustahil**: Commit di repo induk dan repo anak adalah dua transaksi terpisah. | **Mungkin**: Bisa melakukan commit perubahan modul bersamaan dengan consumer-nya. | **Native**: Satu commit bisa menyentuh shared-library dan service consumer sekaligus. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Bencana Detached HEAD dan Penghapusan Objek Tak Sengaja
**Masalah**: Developer melakukan checkout ke SHA tertentu (`git checkout <commit-sha>`), membuat commit baru di posisi tersebut, lalu berpindah ke branch lain (`git checkout main`). Commit-commit baru tersebut tidak terikat pada branch ref mana pun, melayang sebagai *dangling/orphan commits*, dan terancam terhapus permanen oleh *Garbage Collector* (`git gc`).

**Solusi Pemulihan (Forensic Discovery)**:
```bash
# 1. Telusuri riwayat pergerakan HEAD
git reflog

# Output Reflog:
# 2b1c4e0 HEAD@{0}: checkout: moving from 8f12a3d to main
# 8f12a3d HEAD@{1}: commit: feat(crypto): add hmac signature verification
# a1b2c3d HEAD@{2}: commit: fix(token): resolve buffer overflow
# e4f5a6b HEAD@{3}: checkout: moving from feat-x to e4f5a6b

# 2. Temukan SHA commit terakhir sebelum berpindah (8f12a3d)
# 3. Buat branch baru dari titik tersebut untuk menyelamatkan objek
git branch recovery-branch 8f12a3d

# 4. Verifikasi bahwa DAG telah terikat kembali ke named reference
git log --oneline -n 3 recovery-branch
```

### 10.2 Bencana Force-Push Menimpa Public Branch
**Masalah**: Developer menjalankan `git push --force origin main` yang menimpa commit milik rekan tim lain dengan state lokalnya yang tertinggal.

**Solusi & Proteksi**:
```bash
# RECOVERY (Jika server remote belum di-garbage collect):
# 1. Buka repo server via terminal/GitHub Console, temukan old ref melalui reflog remote.
# 2. Jika dilakukan di local, periksa reflog remote tracking branch:
git reflog show origin/main

# 3. Kembalikan state pointer origin/main ke commit sebelum force push terjadi
git push --force-with-lease origin <commit-id-sebelum-hancur>:main

# PREVENSI JANGKA PANJANG:
# Hentikan penggunaan '--force' murni. Wajib gunakan flag '--force-with-lease'.
# Flag ini membatalkan push jika reference remote telah bergerak tanpa sepengetahuan developer.
git push --force-with-lease origin my-branch
```

### 10.3 Resolusi Terjebak Dynamic Submodule De-sync
**Masalah**: Menjalankan `git checkout` atau `git pull` menghasilkan error fatal submodule dirty atau direktori submodule menunjuk ke status *untracked changes* / *modified content* tanpa alasan jelas.

**Solusi Rekonstruksi Submodule**:
```bash
# 1. Bersihkan status registri submodule yang de-sync
git submodule sync --recursive

# 2. Paksa sinkronisasi commit pointer yang dicatat superproject
git submodule update --init --recursive --force

# 3. Jika submodule tetap kotor karena untracked binary/cache
git submodule foreach --recursive 'git reset --hard HEAD && git clean -fdx'
```

---

## 11. Best Practices (Production Checklist)

Mekanisme governance repositori enterprise wajib memenuhi checklist berikut sebelum masuk ke production environment:

- [ ] **Linear History Policy**: Menolak merge commit biasa pada branch `main`/`production`. Gunakan kebijakan Squash atau Rebase-Fast-Forward.
- [ ] **Commit Signing Enforced**: Seluruh kontributor wajib menandatangani commit menggunakan kunci GPG atau SSH terverifikasi.
- [ ] **Granular CODEOWNERS Specification**: Mendefinisikan file `.github/CODEOWNERS` untuk memastikan file kritis (misal: arsitektur database, konfigurasi security/auth, pipeline CI) memerlukan persetujuan eksplisit dari tim spesialis terkait.
- [ ] **Merge Queue Integration**: Mengaktifkan Merge Queue untuk branch release utama guna mengeliminasi regresi integrasi konkuren.
- [ ] **Automated Secret Scanning**: Menerapkan pre-commit hook (Client-side) dan Secret Scanning Push Protection (Server-side) untuk mencegah kebocoran credentials API, token, dan private key.
- [ ] **Conventional Commits Standard**: Mengaktifkan hook `commit-msg` untuk validasi parsing automated semantic versioning dan generation changelog otomatis.
- [ ] **Git Attributes LFS Rules**: Mendaftarkan ekstensi biner pada `.gitattributes` sebelum file biner di-track oleh Git.
- [ ] **Ephemeral Clones Optimization**: Pada pipeline CI/CD, clone repositori wajib menggunakan kedalaman minimal dan single-branch:
  ```bash
  git clone --depth=1 --single-branch --branch main <repo-url>
  ```
- [ ] **Git Native Maintenance Tuning**: Menjalankan optimasi database periodik pada developer machine atau host server untuk repositori masif:
  ```bash
  git maintenance start
  git commit-graph write --reachable
  ```

---

## 12. Hands-on Practice

Buatlah lab simulasi lokal end-to-end ini di direktori `hands-on/m02/` untuk mempraktikkan skenario arsitektur produksi: GPG signing, custom hooks, conflict engineering, LFS, dan disaster recovery forensics.

```
hands-on/m02/
├── .githooks/
│   ├── commit-msg
│   └── pre-commit
├── src/
│   └── app.py
├── tests/
│   └── test_app.py
└── .gitattributes
```

### Langkah Praktikum Langkah-demi-Langkah

#### Step 1: Inisialisasi Repositori dan Konfigurasi Hooks Path
```bash
mkdir -p hands-on/m02
cd hands-on/m02
git init
mkdir -p .githooks src tests

# Arahkan Git Hooks path ke direktori yang di-track VCS
git config core.hooksPath .githooks
```

#### Step 2: Implementasi Hook Commit Enforcement
Buat file `.githooks/commit-msg`:
```bash
cat << 'EOF' > .githooks/commit-msg
#!/usr/bin/env bash
MSG=$(head -n 1 "$1")
PATTERN="^(feat|fix|chore|docs|refactor)\([a-z-]+\): [a-z0-9 ]+$"
if ! [[ "$MSG" =~ $PATTERN ]]; then
    echo "❌ Error: Format commit wajib '<type>(<scope>): <pesan lowercase>'!"
    echo "   Contoh: feat(core): implement database pooling"
    exit 1
fi
EOF
chmod +x .githooks/commit-msg
```

#### Step 3: Setup Git LFS untuk Asset Simulasi
```bash
git lfs install
cat << 'EOF' > .gitattributes
*.bin filter=lfs diff=lfs merge=lfs -text
*.dat filter=lfs diff=lfs merge=lfs -text
EOF

git add .gitattributes .githooks
git commit -m "chore(repo): initialize lfs and commit-msg policy"
```

#### Step 4: Simulasi Base Code & Regresi untuk Git Bisect
Buat file `src/app.py`:
```python
def process_data(items):
    # Algoritma Versi 1.0 (Stabil)
    return [x * 2 for x in items]

if __name__ == "__main__":
    print(process_data([1, 2, 3]))
```

Buat file test `tests/test_app.py`:
```python
import unittest
from src.app import process_data

class TestApp(unittest.TestCase):
    def test_logic(self):
        self.assertEqual(process_data([1, 2, 3]), [2, 4, 6])

if __name__ == "__main__":
    unittest.main()
```

Lakukan commit base version:
```bash
git add src/ tests/
git commit -m "feat(core): implement core process data method"
git tag v1.0.0
```

#### Step 5: Membuat Serangkaian Commits & Menyisipkan Bug Tersembunyi
```bash
# Commit 1 (Aman)
echo "# documentation" >> README.md
git add README.md
git commit -m "docs(readme): add project documentation overview"

# Commit 2 (PENYUSUP BUG: Mengubah logika proses yang merusak array mutation)
cat << 'EOF' > src/app.py
def process_data(items):
    # Logika bermasalah: Mengganti output indeks secara salah
    return [x * 3 for x in items] # Harusnya * 2

if __name__ == "__main__":
    print(process_data([1, 2, 3]))
EOF
git add src/app.py
git commit -m "refactor(core): optimize vector processing engine"

# Commit 3 (Aman tapi dilakukan setelah bug ada)
echo "LOG_LEVEL=DEBUG" > .env.example
git add .env.example
git commit -m "chore(env): add default logging variables template"
```

#### Step 6: Eksekusi Disaster Discovery Menggunakan Automated Bisect
Verifikasi bahwa branch saat ini gagal dalam unit testing:
```bash
python3 tests/test_app.py || echo "PENGUJIAN GAGAL PADA CURRENT HEAD"
```

Jalankan automated bisect hunting:
```bash
git bisect start
git bisect bad HEAD
git bisect good v1.0.0
git bisect run python3 tests/test_app.py
```
*Amati terminal secara real-time bagaimana Git melompat melewati DAG dan menemukan commit `refactor(core): optimize vector processing engine` sebagai sumber anomali secara presisi.*

Kembalikan pointer:
```bash
git bisect reset
```

#### Step 7: Eksperimen Detached HEAD Forensics & Reflog Recovery
```bash
# Buat simulasi kecelakaan fatal
git checkout HEAD~1
echo "KODE_SANGAT_RAHASIA=TRUE" > secret.txt
git add secret.txt
# Bypass commit hook dengan flag -n jika commit message tidak standar untuk demo
git commit -m "feat(secret): experimental cryptographic implementation"

# Dapatkan SHA commit ini untuk referensi
DANGLING_SHA=$(git rev-parse HEAD)
echo "Commit rahasia dibuat di: $DANGLING_SHA"

# Pindah ke branch main tanpa mengikat commit tadi ke branch mana pun
git checkout -f master 2>/dev/null || git checkout -f main

# Commit rahasia sekarang 'hilang' dari graf git log reguler
git log --oneline -n 3
# Buktikan bahwa SHA tadi tidak muncul di log aktif!

# OPERASI FORENSIK PEMULIHAN:
git reflog | grep "experimental cryptographic"
# Pulihkan commit yang terisolasi ke named branch baru
git checkout -b recovered-secret-branch $DANGLING_SHA
git log -1
# Berhasil: Node yang terputus dari DAG telah diamankan kembali!
```

---

## 13. Exercises

### Level: Easy
1. Dari repositori lab di atas, ubah commit message terakhir pada `recovered-secret-branch` menjadi `feat(security): implement advanced secret payload handling` tanpa membuat commit node baru (gunakan amend).
2. Konfigurasikan Git config lokal repositori tersebut agar seluruh proses `git pull` secara default selalu menggunakan strategi `--rebase` tanpa fast-forwarding merge commits liar.
   - *Target output*: Inspect `.git/config` untuk memverifikasi entri konfigurasi baru.

### Level: Medium
1. Simulasikan skenario *Criss-Cross Merge conflict*:
   - Buat branch `feature-alpha` dan `feature-beta` dari `main`.
   - Modifikasi baris yang sama pada file `src/app.py` di kedua branch dengan nilai berbeda.
   - Gabungkan `feature-alpha` ke `feature-beta` (resolve conflict).
   - Lakukan modifikasi tambahan di `main`, lalu gabungkan `feature-beta` ke `main`.
   - Analisis melalui diagram DAG visual (`git log --graph --oneline --all`) bagaimana Git menentukan LCA menggunakan merge engine `ort`.

### Level: Hard
1. **Writing a Robust Server-Side Pre-Receive Hook**:
   - Buat bare repository lokal yang berperan sebagai remote server:
     ```bash
     git init --bare server-repo.git
     ```
   - Tulis executable hook di `server-repo.git/hooks/pre-receive` yang mengimplementasikan aturan berikut:
     1. Menolak push apa pun ke branch `main` jika commit di dalamnya tidak memiliki commit signature yang valid (Signed Commit Enforcement).
     2. Menolak push jika ada commit baru yang menyertakan file biner berukuran > 5 MB yang tidak dilacak melalui Git LFS (inspeksi metadata Git Object size secara langsung melalui plumbing command `git cat-file --batch-check`).

---

## 14. Challenge: Production Incident Simulation

### Skenario: "The Poisoned Merge Queue Deadlock"
Anda adalah Principal Site Reliability & Platform Engineer di unicorn fintech. 

Pada jam 15:00 WIB, sebuah pull request besar yang menggabungkan 40 commit di-merge ke branch `main` via Squash-Merge. Seketika itu juga, automated release pipeline mempromosikan commit tersebut ke staging cluster, dan seluruh transaksi payment gateway terhenti (500 Internal Server Error masif). 

Setelah diinvestigasi cepat:
1. Revert commit melalui UI GitHub gagal secara total karena PR-PR lain telah di-merge di atasnya dalam rentang 10 menit, memicu merge collision pada file konfigurasi payment orchestration `config/payment.yaml`.
2. Developer pembuat PR awal sedang cuti tanpa akses laptop.
3. Tim audit OJK menuntut tidak boleh ada *history force-push* pada branch `main` untuk menjaga compliance immutable log audit.
4. Repositori memiliki Git submodule internal `lib-crypto` yang ikut terkunci versinya pada commit yang rusak tersebut.

### Tugas Tantangan:
Rancang dan eksekusi serangkaian instruksi terminal Git tingkat lanjut untuk:
1. Mengembalikan status operasional branch `main` ke titik fungsional tepat sebelum commit fatal tersebut terjadi, tanpa menggunakan opsi `git push --force` atau merusak linieritas commit history rekan tim lain yang sudah berada di `main`.
2. Menyelaraskan submodule `lib-crypto` kembali ke versi rilis stabil sebelumnya tanpa menyebabkan status `Submodule dirty` di local clone 300 engineer lain saat mereka menjalankan `git pull`.
3. Menulis *post-mortem RCA (Root Cause Analysis)* singkat dari sisi version control architecture: Mengapa automated merge queue membiarkan bug ini lolos, dan ruleset/hook GitHub Enterprise apa yang harus dipasang agar insiden serupa terblokir secara permanen di tingkat kernel push Git.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Konseptual Fundamental (5 Soal)
1. **Bagaimana Git LFS memanipulasi Git staging area untuk mencegah binary masuk ke DAG object database?**
   - A. Mengompresi binary menggunakan algoritma Brotli sebelum masuk ke packfile.
   - B. Menggunakan Clean filter untuk menukar payload binary asli dengan file pointer SHA-256 teks kecil, dan Smudge filter untuk merestorasinya saat checkout.
   - C. Mengubah metadata bit permission file biner menjadi mode `160000` (gitlink).
   - D. Menghapus objek binary dari commit history sesaat setelah push remote berhasil.

2. **Perbedaan fundamental antara algoritma merge `recursive` warisan dengan algoritma baru `ort` adalah:**
   - A. `ort` tidak lagi mendukung penggabungan 3-Way Merge, melainkan beralih ke 2-Way Diffing.
   - B. `ort` mendeteksi file rename secara dinamis di memori dan menyederhanakan perhitungan LCA multipel secara eksponensial lebih cepat tanpa I/O disk konstan.
   - C. Algoritma `ort` hanya berfungsi pada repositori berbasis platform Git monorepo berbayar.
   - D. `recursive` membuang parent pointer kedua saat menyelesaikan conflict, sedangkan `ort` mempertahankannya.

3. **Mengapa eksekusi `git rebase` pada branch publik yang digunakan bersama oleh banyak developer dikategorikan sebagai *Anti-Pattern* berbahaya?**
   - A. Rebase membatalkan seluruh commit signature (GPG) secara permanen tanpa opsi recovery.
   - B. Rebase menciptakan object commit baru dengan SHA berbeda untuk commit yang logikanya sama, menyebabkan duplikasi commit massal dan konflik rumit bagi developer lain saat mereka melakukan sinkronisasi pull.
   - C. Rebase mengunci working tree developer lain melalui file `.git/index.lock`.
   - D. Git server akan menolak eksekusi rebase secara native melalui proteksi POSIX file locking.

4. **Apa makna teknis dari representasi Git tree mode `160000` pada entri subdirektori repositori?**
   - A. File tersebut adalah symlink absolut ke root filesystem workstation.
   - B. File tersebut adalah executable binary yang diproteksi dari eksekusi user non-root.
   - C. Entri tersebut adalah sebuah Git Submodule (gitlink) yang merujuk pada specific commit SHA-1 di repositori terpisah, bukan merepresentasikan tree directory biasa.
   - D. Direktori tersebut dikecualikan dari scanning packfile optimasi garbage collection.

5. **Apa fungsi utama dari command `git bisect log` saat proses debugging regresi kode sedang berlangsung?**
   - A. Menampilkan log aktivitas push developer lain ke branch yang sedang di-bisect.
   - B. Menyimpan dan menampilkan urutan pengujian commit yang sudah ditandai `good` atau `bad` sehingga sesi bisect dapat di-playback atau dibagikan ke engineer lain.
   - C. Menghitung kompleksitas waktu Big-O dari proses pencarian biner lokal.
   - D. Membatalkan seluruh perubahan uncommitted file secara rekursif di working tree.

### Bagian B: Analisis & Skenario Menengah (5 Soal)
6. **Perhatikan skenario reflog berikut:**
   ```
   d4c3b2a HEAD@{0}: reset: moving to HEAD~2
   f1e2d3c HEAD@{1}: commit: feat(billing): integrate stripe payment gateway
   b8a7c6d HEAD@{2}: commit: fix(auth): fix race condition on refresh token
   ```
   **Jika developer secara tidak sengaja menjalankan `git reset --hard HEAD~2`, perintah apa yang paling cepat dan aman untuk memulihkan repositori kembali ke status commit `f1e2d3c`?**
   - A. `git checkout -b fix-branch && git merge HEAD@{2}`
   - B. `git reset --hard HEAD@{1}`
   - C. `git revert HEAD~2..HEAD`
   - D. `git push --force origin main`

7. **Seorang engineer ingin mengabaikan file log yang sudah terlanjur ter-commit di masa lalu (`server.log`). Ia menambahkan baris `*.log` ke file `.gitignore`, namun saat memodifikasi `server.log`, Git tetap mendeteksi perubahannya pada `git status`. Mengapa ini terjadi dan apa solusinya?**
   - A. `.gitignore` rusak; solusi: install ulang binary Git engine.
   - B. File tersebut sudah masuk ke dalam Git tracking cache (staging area); solusi: jalankan `git rm --cached server.log` lalu commit perubahan tracking tersebut.
   - C. File binary tidak dapat di-filter via `.gitignore`; solusi: definisikan filter di `.gitattributes`.
   - D. Ekstensi file log bertabrakan dengan internal git packfile; solusi: hapus `.git/index`.

8. **Manakah konfigurasi perintah berikut yang secara otomatis mengonfigurasi Git agar selalu merekonstruksi topologi linear saat melakukan integrasi branch remote pada `git pull`?**
   - A. `git config --global merge.ff only`
   - B. `git config --global pull.rebase true`
   - C. `git config --global pull.ff false`
   - D. `git config --global rebase.autoSquash true`

9. **Ketika terjadi merge conflict, Git menandai baris konflik dengan format diff3 (jika diaktifkan). Apa keuntungan mengaktifkan `git config merge.conflictStyle diff3` dibandingkan format conflict default?**
   - A. Otomatis menyelesaikan konflik tanpa intervensi manusia berdasarkan timestamp file.
   - B. Menampilkan snapshot kode asli dari Lowest Common Ancestor (LCA) di antara snapshot cabang lokal dan cabang remote, memberikan konteks riil atas apa yang sebenarnya diubah kedua belah pihak.
   - C. Mengizinkan developer mengabaikan syntax error secara langsung di dalam IDE.
   - D. Membagi file konflik menjadi tiga file terpisah pada filesystem OS.

10. **Sebuah pipeline CI/CD GitHub Actions mengalami kegagalan pada stage deploy karena committer identity verification gagal. Output terminal menunjukkan: "Commit invalid: gpg signature could not be verified: no public key". Apa akar masalah operasional ini?**
    - A. Developer menandatangani commit menggunakan kunci GPG lokal, namun Public Key dari GPG tersebut belum diunggah dan diverifikasi pada profil akun GitHub Enterprise miliknya.
    - B. File `.gitattributes` memblokir pembacaan format kunci kriptografis OpenPGP.
    - C. GitHub Enterprise Server hanya mendukung SSH commit signing dan tidak mendukung standar RFC 4880 OpenPGP.
    - D. Runner CI/CD dijalankan tanpa privilege user `sudo`.

### Bagian C: Pemecahan Masalah Kasus Produksi Riil (3 Soal)
11. **Skenario 1: The Multi-Gigabyte Git Leak Disaster**
    Seorang engineer secara tidak sengaja menambahkan file binary model machine learning berukuran 12 GB ke commit 5 hari yang lalu, dan telah melakukan 15 commit baru di atasnya. File tersebut sudah di-push ke branch development utama yang telah di-pull oleh 20 engineer lainnya. Tim platform memutuskan binary 12 GB tersebut harus dimusnahkan secara permanen dari seluruh commit history repositori tanpa merusak relasi parent-child commit lainnya.
    
    *Pertanyaan Arsitektur*: Mengapa perintah Porcelain standar seperti `git rm` dan `git commit --amend` tidak akan menyelesaikan masalah ukuran packfile repositori, dan utility apa yang secara resmi direkomendasikan industri untuk membedah serta merekayasa ulang seluruh DAG Git dalam kasus ini?
    - A. `git rm` hanya membuat commit baru yang menghapus file dari working directory terkini; blob 12 GB tetap kekal tersimpan di dalam `.git/objects/pack/` historis. Solusinya adalah menggunakan `git-filter-repo` (atau `BFG Repo-Cleaner`) untuk menulis ulang seluruh tree object dan merefresh packfiles melalui `git gc --prune=now`.
    - B. `git rm` memicu lockup database biner. Solusinya adalah menghapus direktori `.git` di workstation lokal developer lalu melakukan `git init` ulang secara force ke remote server.
    - C. `git commit --amend` secara otomatis merekonstruksi SHA seluruh branch remote secara asinkron tanpa mengubah hash induk.
    - D. Objek binary 12 GB akan terhapus otomatis oleh server GitHub setelah 24 jam jika tidak ada referensi tag.

12. **Skenario 2: GitHub Merge Queue Deadlock on Dependent Releases**
    Sebuah tim menerapkan GitHub Merge Queue. Dua branch diajukan secara paralel:
    - **PR-A**: Mengubah nama metode database dari `UserRepository.get_user()` menjadi `UserRepository.find_by_id()`.
    - **PR-B**: Menambahkan endpoint HTTP baru yang memanggil `UserRepository.get_user()`.
    Kedua PR dibuat dari commit baseline `main` yang sama dan masing-masing lulus uji testing lokal di branch masing-masing tanpa ada git conflict pada file yang disentuh (PR-A menyentuh repository module, PR-B menyentuh controller module).
    
    *Pertanyaan Arsitektur*: Apa yang terjadi ketika kedua PR tersebut dimasukkan ke dalam antrean GitHub Merge Queue secara bersamaan (PR-A berada di posisi antrean #1, dan PR-B di posisi #2)?
    - A. Merge Queue akan langsung me-merge kedua PR tersebut ke `main` secara simultan karena tidak ada line text conflict (Git 3-Way merge lolos otomatis). Akibatnya branch `main` langsung rusak di production.
    - B. Merge Queue secara spekulatif menguji PR-B di atas branch tiruan hasil penggabungan `main + PR-A`. Suite testing pada runner spekulatif PR-B akan mendeteksi `AttributeError: get_user() not found`, menggagalkan CI PR-B, mengeluarkannya secara otomatis dari antrean, dan hanya mengizinkan PR-A terintegrasi ke `main`.
    - C. Git engine secara otomatis mendeteksi perubahan nama fungsi dan melakukan refactor otomatis pada kode PR-B menggunakan AST parsing.
    - D. GitHub Enterprise menahan PR-A dan PR-B secara permanen hingga administrator me-restart server.

13. **Skenario 3: Forensic Reflog Recovery pada Bare Server Repository**
    Sebuah skrip deployment otomatis mengalami error logika dan mengeksekusi penghapusan branch release produksi di Bare Repository remote (`git push origin --delete release/v2.0`). Bare repository tidak memiliki working directory dan secara default tidak mengaktifkan reflog per-user (`core.logAllRefUpdates` sering kali berbeda konfigurasinya dengan non-bare).
    
    *Pertanyaan Arsitektur*: Jika reflog branch tersebut tidak tersedia di sisi Bare Server, metode internal plumbing Git tingkat lanjut apa yang dapat dieksekusi oleh DevOps Administrator langsung di host server bare untuk melacak dan merestorasi commit tip dari branch `release/v2.0` yang dihapus tersebut?
    - A. Tidak ada cara; jika branch dihapus dari bare repo, seluruh objek commit langsung terhapus secara fisik saat itu juga dari filesystem POSIX.
    - B. Menggunakan utility `git fsck --lost-found` untuk memindai seluruh *dangling commit objects* di `.git/objects/`, memeriksa metadata commit menggunakan `git show <dangling-commit-sha>`, menemukan hash commit terakhir yang sesuai, dan mengaitkan kembali referensi branch melalui `git update-ref refs/heads/release/v2.0 <found-sha>`.
    - C. Mengunduh data dari backup tape karena Git tidak menyimpan commit yang referensinya sudah hilang.
    - D. Menjalankan perintah `git log --all` langsung di root sistem operasi bare repository.

---

### Kunci Jawaban Evaluasi

#### Bagian A: Konseptual Fundamental
1. **B** - Git LFS mengintersep file besar menggunakan Git clean filter saat penambahan ke staging (menggantikannya dengan metadata pointer ~130 bytes ke Object Database Git) dan mengunggah konten biner asli ke LFS storage, lalu memanggil smudge filter saat checkout.
2. **B** - Algoritma `ort` didesain ulang untuk memecahkan bottleneck performa: rename detection dioptimasi secara masif, dan status penggabungan/konflik diarsiteksikan di memori secara efisien sebelum penulisan blob dilakukan.
3. **B** - Rebase menulis ulang sejarah commit (mengubah SHA-1/SHA-256 parent node). Jika branch yang sudah di-rebase di-push ke public branch bersama, engineer lain akan mendapati history divergen parah dan penggabungan ulang akan menduplikasi commit.
4. **C** - Mode `160000` adalah penanda struktur internal Git (Tree mode) untuk sebuah gitlink, yang menandakan keberadaan Git Submodule yang menunjuk pada commit hash spesifik di repositori lain.
5. **B** - `git bisect log` menyimpan riwayat penandaan commit (`good`/`bad`) dari sesi pencarian saat ini, yang berguna untuk replikasi otomasi atau auditing tracking bug.

#### Bagian B: Analisis & Skenario Menengah
6. **B** - Pada reflog yang disajikan, `HEAD@{1}` adalah posisi commit fungsional `f1e2d3c` sebelum eksekusi `git reset` dijalankan. Perintah `git reset --hard HEAD@{1}` akan mengembalikan pointer branch aktif kembali ke state tersebut seketika.
7. **B** - Aturan `.gitignore` hanya berlaku untuk file yang berstatus *untracked*. Jika file sudah pernah di-commit ke Git index, perubahannya akan terus dilacak sampai referensinya dihapus dari index staging via `git rm --cached`.
8. **B** - `git config --global pull.rebase true` memaksa setiap operasi `git pull` mengeksekusi rebase lokal di atas branch upstream, mencegah munculnya merge commit non-linear ad-hoc.
9. **B** - Mode `diff3` menyertakan blok pembanding ketiga di antara `<<<<<<<` dan `>>>>>>>`, yaitu `||||||| merged common ancestors`, yang memperlihatkan kondisi baris kode sebelum kedua branch melakukan modifikasi masing-masing.
10. **A** - Keberhasilan verifikasi signed commit pada GitHub/GitLab Enterprise mewajibkan Public Key asimetris yang berpasangan dengan Private Key penandatangan lokal developer terdaftar secara eksplisit di profile platform.

#### Bagian C: Pemecahan Masalah Kasus Produksi Riil
11. **A** - Perintah Porcelain biasa tidak pernah menghapus riwayat object dari packfiles masa lalu. `git-filter-repo` menulis ulang seluruh riwayat DAG, dan `git gc --prune=now` membersihkan loose/packed object yang tidak lagi memiliki jalur referensi.
12. **B** - Ini adalah keunggulan utama GitHub Merge Queue. Antrean tidak hanya melihat git diff secara statis, tetapi membangun temporary test branch yang menggabungkan state akumulatif (`main + PR-A + PR-B`). Kegagalan build integration PR-B dideteksi sebelum menyentuh `main`.
13. **B** - Git tidak menghapus commit seketika. Objek-objek tersebut tetap ada di object database sebagai loose/packed objects tanpa referensi (*dangling*). Tool plumbing `git fsck --lost-found` memunculkan kembali pointer SHA-SHA yatim tersebut, yang kemudian dapat direkonstruksi ulang menjadi named branch melalui plumbing command `git update-ref`.

---

## 16. Summary

```
+───────────────────────────────────────────────────────────────────────────────────────────+
|                         ENTERPRISE GIT ARCHITECTURE AT A GLANCE                           |
+───────────────────────────────────────────────────────────────────────────────────────────+
|                                                                                           |
|    GRAPH ENGINE               INTEGRATION GATEWAY               STORAGE ARCHITECTURE      |
|  ┌──────────────────────┐    ┌───────────────────────────┐    ┌─────────────────────────┐ |
|  │  Directed Acyclic    │    │  Trunk-Based Development  │    │  Git LFS Storage        │ |
|  │  Graph (DAG)         │    │  Linear History (Rebase)  │    │  Smudge/Clean Intercept │ |
|  │  ort Merge Algorithm │    │  GitHub Merge Queues      │    │  Pointer SHA256 Engine  │ |
|  └──────────────────────┘    └───────────────────────────┘    └─────────────────────────┘ |
|             ▲                              ▲                               ▲              |
|             │                              │                               │              |
|             └──────────────────────────────┼───────────────────────────────┘              |
|                                            │                                              |
|                                 SECURITY & COMPLIANCE                                     |
|                              ┌───────────────────────────┐                                |
|                              │  Cryptographic Signatures │                                |
|                              │  GPG / SSH Strict Policy  │                                |
|                              │  Pre-Receive Audit Hooks  │                                |
|                              └───────────────────────────┘                                |
+───────────────────────────────────────────────────────────────────────────────────────────+
```

1. **Integritas Graf Mutlak (DAG Mechanics)**: Segala perubahan di Git bermuara pada manipulasi simpul pohon DAG. Rebase memindahkan basis cabang untuk menyajikan topologi linear, sementara 3-Way Merge mempertahankan titik percabangan historis melalui Lowest Common Ancestor (LCA).
2. **Skalabilitas Monorepo Modern**: Penanganan repositori skala masif memerlukan pemisahan aset biner via Git LFS (Clean/Smudge filters) serta pembatasan checkout melalui fitur modern seperti `sparse-checkout`, `scalar`, dan algoritma merge generasi baru `ort`.
3. **Kualitas & Keamanan Berbasis Sistem**: Keandalan kode di enterprise tidak bersandar pada kedisiplinan manusiawi semata, melainkan pada otomasi gerbang pengaman: automated pre-commit scanning, commit message normalization, cryptographic signature verification, dan speculative integration melalui CI Merge Queues.