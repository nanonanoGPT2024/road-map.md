# BAB 06: Materi Lanjutan
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan memiliki kompetensi tingkat lanjut untuk:
1. **Menganalisis dan Membedah Arsitektur Internal Git**: Memahami struktur *Content-Addressable Storage*, Directed Acyclic Graph (DAG), serta format serialisasi 4 objek fundamental Git (`blob`, `tree`, `commit`, `tag`).
2. **Menguasai Plumbing vs. Porcelain Commands**: Memanipulasi *staging area* (index) dan *ref database* langsung melalui level *plumbing* untuk merekonstruksi status repositori saat terjadi kegagalan sistem.
3. **Mengeksekusi Git History Rewriting Secara Aman**: Melakukan `rebase -i` (squash, fixup, reword, drop), `cherry-pick`, dan pembersihan riwayat sensitif dengan aman tanpa merusak integritas *ancestor tree*.
4. **Menerapkan Advanced Debugging & Remediasi**: Mengisolasi regresi kode secara matematis menggunakan `git bisect` terotomatisasi serta memulihkan branch yang hilang via `git reflog` dan commit *dangling*.
5. **Merancang Strategi Percabangan Skala Enterprise**: Mengevaluasi *trade-offs* antara *Trunk-Based Development* dan *GitFlow*, mengonfigurasi merge strategy (`recursive/ort`, *fast-forward only*, *squash-and-merge*), serta mengamankan supply chain kode melalui signed commits (GPG/SSH).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
* Operasi dasar Git: `init`, `clone`, `add`, `commit`, `push`, `pull`, `fetch`.
* Mekanisme branching dasar dan *two-way merge resolution*.
* Konsep dasar Unix CLI: pipe (`|`), redirection (`>`, `>>`), hash algorithms (SHA-1, SHA-256), dan variabel lingkungan (environment variables).
* Familiaritas dengan sistem direktori tersembunyi (`.git/`).

---

### 3. Concept & Internal Architecture (Mendalam)

Git bukanlah sekadar sistem *Version Control System* (VCS) berbasis *delta compression*; Git pada intinya adalah **Content-Addressable Storage** berbasis key-value yang diakses melalui graf asiklik terarah (**Directed Acyclic Graph / DAG**).

```
                      +-------------------+
                      |      HEAD         |
                      +---------+---------+
                                |
                                v
                      +-------------------+
                      | refs/heads/main   | (Reference / Pointer)
                      +---------+---------+
                                |
                                v
+---------------------------------------------------------------+
|                      Object Store (.git/objects)              |
|                                                               |
|    +-------------------------+                                |
|    |  Commit Object: c14a    |                                |
|    |  - tree: 48b2...        |                                |
|    |  - parent: 9f12...      |                                |
|    |  - author / committer   |                                |
|    +------------+------------+                                |
|                 |                                             |
|                 v                                             |
|    +-------------------------+                                |
|    |  Tree Object: 48b2      |                                |
|    |  - 100644 blob e69d src |                                |
|    +------------+------------+                                |
|                 |                                             |
|                 v                                             |
|    +-------------------------+                                |
|    |  Blob Object: e69d      | (Raw payload data, zlib)       |
|    +-------------------------+                                |
+---------------------------------------------------------------+
```

#### 3.1. Struktur Internal Direktori `.git/`

Ketika `git init` dijalankan, Git menginisialisasi sistem basis data file:
* **`HEAD`**: Simbolik pointer yang merujuk ke branch yang aktif saat ini (`ref: refs/heads/main`).
* **`config`**: Konfigurasi spesifik repositori.
* **`objects/`**: Object database (content store). Menyimpan semua data terkompresi. Dua digit pertama hash SHA-1 menjadi nama subdirektori, dan 38 digit berikutnya menjadi nama file.
* **`refs/`**: Pointer ke commit. Terbagi menjadi `heads/` (local branches), `tags/` (tags), dan `remotes/` (remote tracking branches).
* **`index`**: File biner yang merepresentasikan *staging area*. Bertindak sebagai jembatan antara *working directory* dan object database.

#### 3.2. 4 Tipe Objek Git (Object Store Architecture)

Semua entitas dalam Git di-hash menggunakan formula:
$$\text{SHA-1}(\text{type} + \text{" "} + \text{size} + \text{"\0"} + \text{content})$$

1. **Blob (Binary Large Object)**: Menyimpan raw bytes konten file. Blob tidak menyimpan metadata seperti nama file, ekstensi, timestamp, atau permissions.
2. **Tree**: Merepresentasikan struktur direktori. Berisi entri yang mengikat nama file dan permission bits (misal: `100644` untuk file biasa, `100755` untuk file executable, `040000` untuk subdirektori) ke SHA-1 hash dari blob atau tree lain.
3. **Commit**: Objek yang merepresentasikan snapshot waktu. Mengandung pointer ke top-level tree, satu atau lebih pointer ke parent commit SHA-1 (0 parent untuk initial commit, 2 parent untuk merge commit), metadata author, committer, timestamp, serta commit message.
4. **Annotated Tag**: Objek independen yang menunjuk ke commit spesifik, memuat tagger metadata, timestamp, PGP signature, dan pesan tag.

#### 3.3. Directed Acyclic Graph (DAG) & Index State

* Branch pada Git bukanlah representasi kontainer fisik, melainkan **mutable pointer** (file teks 41-byte di `.git/refs/heads/`) yang menunjuk ke commit SHA-1.
* Operasi commit baru hanya menambahkan sebuah commit object ke `.git/objects/` dan menggeser pointer branch yang ditunjuk oleh `HEAD` ke commit SHA-1 yang baru. Ancestor node bersifat *immutable*. Jika sebuah node diubah secara historis, seluruh hash commit anak hingga daun graf akan berubah secara berantai (*cryptographic hash chain*).

---

### 4. Why & What

| Fitur / Konsep | What (Apa itu?) | Why (Mengapa krusial dalam skala Enterprise?) |
| :--- | :--- | :--- |
| **Interactive Rebase** | Mekanisme menulis ulang (*rewriting*) urutan, pesan, dan integrasi commit sebelum digabungkan ke branch utama. | Menjaga histori Git tetap linear, bersih, dan mudah diaudit (*bisect-friendly*). Mencegah polusi mikro-commit seperti "fix typo" atau "test ci". |
| **Git Reflog** | Mekanisme logging internal yang mencatat pergerakan *HEAD* dan reference lokal. | Bertindak sebagai jaring penyelamat (*fail-safe*) produksi. Commit yang hilang akibat `git reset --hard` atau bad rebase dapat dipulihkan 100%. |
| **Git Bisect** | Algoritma pencarian biner (*binary search*) melintasi DAG commit history. | Mengurangi waktu pelacakan bug regresi secara eksponensial ($O(\log N)$). Mampu menemukan commit penyebab error di antara ribuan commit otomatis via shell script. |
| **Plumbing vs Porcelain** | *Porcelain* adalah user interface level tinggi (`checkout`, `commit`); *Plumbing* adalah core tool level rendah (`hash-object`, `cat-file`, `commit-tree`). | Krusial untuk otomatisasi CI/CD tingkat lanjut, custom tooling, audit keamanan, dan analisis kerusakan data (.git corruption). |

---

### 5. How (Workflow Detail)

#### 5.1. Alur Kerja Interactive Rebase (`git rebase -i`)

Operasi rebase bekerja dengan melepaskan (*unapplying*) commit lokal satu per satu dan menerapkannya kembali di atas commit target (`upstream`):

```
State Awal:
A --- B --- C (main)
       \
        D --- E --- F (feature)

Proses Rebase (git checkout feature; git rebase main):
1. Git menemukan common ancestor (B).
2. Commit D, E, F disimpan sementara sebagai patch biner di .git/rebase-merge/.
3. Branch pointer 'feature' dipindahkan ke C.
4. Patch D', E', F' diterapkan secara berurutan di atas C.

State Akhir:
A --- B --- C (main)
             \
              D' --- E' --- F' (feature)
```

#### 5.2. Alur Diagnostik Git Bisect Automatis

Pencarian regresi berjalan menggunakan interval biner:

```
[Good] C01 --- C02 --- C03 --- C04 --- C05 --- C06 --- C07 --- C08 [Bad]
                          ^
                    Midpoint Test: C04
              (Jika C04 Good, cari di C05-C08)
              (Jika C04 Bad, cari di C02-C03)
```

Jika diotomasi via script return code:
* Exit code `0`: Commit dinilai bersih (Good).
* Exit code `1` - `127` (kecuali 125): Commit dinilai rusak/regresi (Bad).
* Exit code `125`: Commit dilewati/skip (Untestable / broken build dependency).

---

### 6. Analogy & Diagram ASCII

#### 6.1. Analogi: Git Object Database sebagai Sistem Inventaris Logistik

* **Blob**: Barang mentah tanpa label identitas nama. Disimpan murni berdasarkan berat dan bentuk fisiknya (konten payload).
* **Tree**: Kotak berlabel manifes. Menjelaskan tata letak: "Di dalam kotak ini terdapat barang A dengan izin akses X, dan sub-kotak B".
* **Commit**: Surat jalan bertanggal dan bertanda tangan. Menyatakan: "Kondisi gudang saat ini direpresentasikan oleh Manifes Pohon X, melanjutkan surat jalan sebelumnya Y".
* **Branch**: Sticky note bertuliskan nama yang ditempelkan di atas surat jalan. Memindahkan branch cukup dengan mencabut sticky note dan menempelkannya ke surat jalan lain.

#### 6.2. Diagram ASCII: Struktur Penyimpanan Objek Git

```
             .git/objects/
             |
             +-- 4b/
             |   +-- 825dc642cb6eb9a060e54bf8d69288fbee4904 (Tree)
             |
             +-- e6/
             |   +-- 9de29bb2d1d6434b8b29ae775ad8c2e48c5391 (Blob)
             |
             +-- d8/
                 +-- 329f1234a... (Commit)

+--------------------------------------------------------------------+
|                         COMMIT OBJECT                              |
| Hash: d8329f...                                                    |
| Payload:                                                           |
|   tree 4b825dc642cb6eb9a060e54bf8d69288fbee4904                   |
|   parent a1b2c3...                                                 |
|   author Senior SRE <sre@enterprise.internal> 1708819200 +0700     |
|   committer Senior SRE <sre@enterprise.internal> 1708819200 +0700  |
|                                                                    |
|   feat(core): implement secure TLS handshake                       |
+--------------------------------------------------------------------+
                 |
                 v points to
+--------------------------------------------------------------------+
|                          TREE OBJECT                               |
| Hash: 4b825d...                                                    |
| Payload:                                                           |
|   100644 blob e69de29bb2d1d6434b8b29ae775ad8c2e48c5391    main.go   |
|   040000 tree 8f3c1a2d3b4c5e6f7a8b9c0d1e2f3a4b5c6d7e8f    pkg     |
+--------------------------------------------------------------------+
                 |
                 v points to
+--------------------------------------------------------------------+
|                          BLOB OBJECT                               |
| Hash: e69de2...                                                    |
| Payload:                                                           |
|   package main\n\nfunc main() {\n  println("Production Ready")\n}  |
+--------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Merekonstruksi Git Internal Menggunakan Plumbing Commands

Demonstrasi bagaimana membuat commit tanpa pernah menjalankan `git add` atau `git commit`:

```bash
# 1. Inisialisasi repositori bersih
mkdir git-internals-lab && cd git-internals-lab
git init

# 2. Buat Blob secara langsung dari STDIN
BLOB_HASH=$(echo "println('Hello Enterprise Architecture')" | git hash-object -w --stdin)
echo "Blob Hash: $BLOB_HASH"
# Output Blob Hash: 40 digit SHA-1

# 3. Verifikasi tipe dan isi blob
git cat-file -t $BLOB_HASH
# Output: blob
git cat-file -p $BLOB_HASH
# Output: println('Hello Enterprise Architecture')

# 4. Buat Index/Staging manual tanpa menyentuh Working Directory
git update-index --add --cacheinfo 100644 $BLOB_HASH app.py

# 5. Tulis Index ke dalam format Tree Object
TREE_HASH=$(git write-tree)
echo "Tree Hash: $TREE_HASH"
git cat-file -p $TREE_HASH
# Output: 100644 blob <BLOB_HASH>    app.py

# 6. Tulis Commit Object yang menunjuk ke Tree Hash
COMMIT_HASH=$(echo "feat: core manual plumbing commit" | git commit-tree $TREE_HASH)
echo "Commit Hash: $COMMIT_HASH"

# 7. Arahkan pointer branch refs/heads/main ke Commit Hash
git update-ref refs/heads/main $COMMIT_HASH

# 8. Verifikasi histori log
git log -1 --stat
```

#### 7.2. Practical Example: Advanced Interactive Rebase & Scripted Bisect

##### Script Pembantu Pengujian Bisect Otomatis (`test-runner.sh`):
```bash
#!/usr/bin/env bash
set -e

# Return code convention:
# 0 = Good / Pass
# 1 = Bad / Regressed
# 125 = Broken environment (skip)

CONFIG_FILE="config/app.json"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Config file not found, skipping commit"
    exit 125
fi

# Validasi apakah rate_limit bernilai valid dan bukan 0 (regresi)
RATE_LIMIT=$(jq '.rate_limit' "$CONFIG_FILE" 2>/dev/null || echo "null")

if [ "$RATE_LIMIT" = "null" ]; then
    exit 125
fi

if [ "$RATE_LIMIT" -le 0 ]; then
    echo "REGRESSION DETECTED: rate_limit is $RATE_LIMIT"
    exit 1
fi

echo "COMMIT CLEAN: rate_limit is $RATE_LIMIT"
exit 0
```

##### Eksekusi Git Bisect Menggunakan Script:
```bash
git bisect start
git bisect bad HEAD
git bisect good v1.0.0
git bisect run ./test-runner.sh
# Git akan mengeksekusi binary search secara otonom dan mengeluarkan commit pertama yang fail.
git bisect reset
```

---

### 8. Real World Case Study (Enterprise Scale)

#### 8.1. Konteks Insiden
* **Organisasi**: Platform Fintech Transaksi Pembayaran Skala Global.
* **Problem Statement**: Seorang engineer secara tidak sengaja mem-push branch yang memuat kredensial private key AWS (`AKIA...`) dan database password ke repositori monorepo terpusat. Sebelum alarm security berbunyi, 15 commit lain telah di-merge di atasnya oleh tim pengembang lain melalui operasi merge commits. Kredensial telah masuk ke dalam history commit permanen.
* **Dampak**: Resiko kompromi sistem dan sanksi audit PCI-DSS level 1. Repo tidak boleh dihapus karena memuat ribuan reference aktif dari puluhan tim.

#### 8.2. Rencana Pemulihan (Incident Response & Historical Scrubbing)

```
[Audit Stage] -> [Freeze Branch] -> [Scrub with git-filter-repo] -> [Re-sign/Inject] -> [Force Align]
```

##### Langkah Eksekusi Teknis:

1. **Lock Repositori & Freeze Branch**:
   Admin mengunci *push access* pada GitHub Enterprise / GitLab untuk mencegah dereferencing dinamis.

2. **Scrubbing Menggunakan `git-filter-repo` (Bukan `filter-branch` yang deprecated dan lambat)**:
   ```bash
   # Buat clone mirror segar
   git clone --mirror git@github.com:fintech-corp/core-ledger.git ledger-scrub
   cd ledger-scrub

   # Buat rules file untuk membuang file sensitif dan string replace
   cat << 'EOF' > expressions.txt
   regex:AKIA[0-9A-Z]{16}==>REDACTED_AWS_KEY
   regex:password=[^\s]+==>password=REDACTED
   EOF

   # Jalankan pembersihan objek secara global
   git filter-repo --invert-paths --paths-glob '**/secrets.env' --replace-text expressions.txt --force

   # Bersihkan sisa packfiles dangling dan unreferenced objects
   git reflog expire --expire=now --all
   git gc --prune=now --aggressive
   ```

3. **Verifikasi Hash Integrity**:
   ```bash
   # Pastikan tidak ada string kredensial yang tersisa di seluruh commit tree
   git log -S "AKIA" --all
   # Harapannya: Output kosong
   ```

4. **Mirror Push & Sinkronisasi Client Local State**:
   ```bash
   git remote set-url origin git@github.com:fintech-corp/core-ledger.git
   git push origin --force --all
   git push origin --force --tags
   ```

5. **Mitigasi Client-Side Divergence**:
   Seluruh developer wajib menjalankan:
   ```bash
   git fetch origin
   git reset --hard origin/main
   ```

---

### 9. Trade-offs

| Parameter | Merge Commit (`--no-ff`) | Squash and Merge | Rebase & Fast-Forward |
| :--- | :--- | :--- | :--- |
| **History Topology** | Non-linear. Mempertahankan visualisasi cabang historis secara utuh. | Strictly Linear. Semua perubahan PR dirangkum ke 1 commit tunggal. | Strictly Linear. Histori commit individu dipindahkan ke pucuk HEAD. |
| **Auditability** | Sangat tinggi untuk pelacakan konteks PR. Commit asli developer tetap ada. | Rendah untuk mikro-perubahan. Riwayat eksperimental individual hilang. | Sangat tinggi per commit atomik, namun commit timestamp asli berubah. |
| **Bisect Debugging** | Sedikit lebih lambat karena harus menelusuri multiple parent branches. | Sangat cepat dan deterministik (1 PR = 1 checkpoint biner). | Efisien, tetapi dapat gagal di commit perantara jika commit tersebut broken. |
| **Conflict Resolution** | Resolusi dilakukan 1 kali pada commit merge. | Resolusi dilakukan 1 kali saat persiapan penggabungan branch. | Resolusi dapat terjadi berulang kali pada tiap-tiap commit yang di-*re-apply*. |
| **Rekomendasi Enterprise**| Repositori rilis berkecepatan rendah, compliance ketat. | Monorepo enterprise berskala besar (Google/Meta style Trunk-Based). | Feature branch berumur pendek (short-lived feature branches). |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Kesalahan Fatal: Detached HEAD State
* **Kondisi**: Developer melakukan `git checkout <commit-sha>` lalu membuat 10 commit baru. Saat berpindah branch (`git checkout main`), commit-commit tersebut tampak hilang total.
* **Akar Masalah**: Commit baru tidak diikat oleh reference pointer branch manapun. Begitu `HEAD` bergeser, commit menjadi *unreachable / dangling*.
* **Troubleshooting Step**:
  ```bash
  # 1. Cari commit SHA terakhir yang dibuat saat detached HEAD
  git reflog

  # Output:
  # 7b2a1c9 HEAD@{0}: checkout: moving from 8f1e2d to main
  # 8f1e2d3 HEAD@{1}: commit: feat: critical local logic
  # 9a0b1c2 HEAD@{2}: commit: feat: first detached work

  # 2. Pasang branch baru tepat pada commit terakhir sebelum checkout
  git branch recovery-branch 8f1e2d3

  # 3. Verifikasi data telah aman
  git checkout recovery-branch
  ```

#### 10.2. Kesalahan Fatal: Forced Push yang Menimpa Perubahan Rekan Tim
* **Kondisi**: Developer mengeksekusi `git push origin feature-branch --force` setelah melakukan rebase lokal, menimpa 5 commit yang telah di-push oleh engineer lain.
* **Mitigasi Preventif**:
  Selalu gunakan opsi `--force-with-lease`. Opsi ini menolak pengiriman perubahan jika remote tracking reference (`origin/feature-branch`) tidak cocok dengan state remote aktual.
  ```bash
  git push origin feature-branch --force-with-lease
  ```

#### 10.3. Resolusi Git Rebase Melenceng (Bad Rebase Abort)
* **Kondisi**: Konflik merge bertubi-tubi menyebabkan file rusak total saat rebase.
* **Penyelesaian**:
  ```bash
  # Batalkan proses rebase dan kembalikan state repositori persis sebelum rebase dimulai
  git rebase --abort
  ```

---

### 11. Best Practices (Production Checklist)

#### 11.1. Production Architecture Checklist
- [ ] **GPG/SSH Signature Verification**: Semua commit dan tags wajib ditandatangani secara kriptografis (`git config --global commit.gpgsign true`).
- [ ] **Linear/Semi-Linear History Policy**: Terapkan pull request rules: *Squash or Rebase* untuk membuang merge commit yang redundan.
- [ ] **Branch Protection Rules**:
  - `main` dan `release/*` dikunci dari direct push (`push --force` dinonaktifkan permanen).
  - Wajib lulus status check (CI pipeline, SAST security scan).
  - Minimal 2 code reviewers (*Peer review mandatory*).
- [ ] **Repository Hygiene (`.gitignore` & `.gitattributes`)**:
  - Standarisasi penanganan line endings lintas OS (`* text=auto eol=lf`).
  - Cegah artefak biner dan secret env file masuk ke cache index.

#### 11.2. Git Hook Keamanan Lokal (Pre-commit)
Simpan di `.git/hooks/pre-commit` dan berikan permission executable (`chmod +x`):
```bash
#!/usr/bin/env bash
# Proteksi kebocoran kredensial sederhana pada level client-side

FORBIDDEN_PATTERNS="(AKIA[0-9A-Z]{16}|PRIVATE KEY|ghp_[0-9a-zA-Z]{36})"

if git diff --cached | grep -E "$FORBIDDEN_PATTERNS" > /dev/null; then
    echo "CRITICAL ERROR: Ditemukan indikasi secret/credential pada staging area!"
    echo "Aborting commit. Silakan bersihkan data sensitif terlebih dahulu."
    exit 1
fi
```

---

### 12. Hands-on Practice

Buat seluruh file praktikum di direktori: `hands-on/m02/`

```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

#### Langkah 1: Membedah Anatomi Objek di `.git/`
1. Inisialisasi lab baru:
   ```bash
   git init lab-internals
   cd lab-internals
   ```
2. Buat file baru dan amati perubahan sistem direktori `.git/`:
   ```bash
   echo "High Performance Architecture" > arch.txt
   find .git/objects -type f
   # Output kosong (belum ada objek)
   ```
3. Stage file dan pantau object store:
   ```bash
   git add arch.txt
   find .git/objects -type f
   # Perhatikan muncul file object baru di .git/objects/xx/yyyy...
   ```
4. Baca konten dan tipe objek:
   ```bash
   OBJ_PATH=$(find .git/objects -type f | head -n 1)
   OBJ_HASH=$(echo $OBJ_PATH | sed 's/\.git\/objects\///' | tr -d '/')
   git cat-file -t $OBJ_HASH
   git cat-file -p $OBJ_HASH
   ```

#### Langkah 2: Simulasi Simulasi Bencana & Pemulihan dengan Git Reflog
1. Buat branch dan lakukan commit:
   ```bash
   git commit -m "feat: commit 1"
   echo "Update 1" >> arch.txt && git commit -am "feat: commit 2"
   echo "Update 2" >> arch.txt && git commit -am "feat: commit 3"
   ```
2. Catat commit hash terakhir, lalu hancurkan histori secara sengaja:
   ```bash
   git reset --hard HEAD~2
   # Sekarang status repo kembali ke commit 1. Commit 2 dan 3 hilang dari git log.
   git log --oneline
   ```
3. Pulihkan status repositori menggunakan Reflog:
   ```bash
   git reflog
   # Identifikasi commit hash dari "feat: commit 3" (misal: HEAD@{1})
   git reset --hard HEAD@{1}
   git log --oneline
   # Seluruh commit telah kembali utuh
   ```

#### Langkah 3: Setup Automated Regression Finder via Git Bisect
1. Buat sequence build:
   ```bash
   for i in {1..10}; do
     echo "build_version=$i" > build.env
     if [ $i -eq 6 ]; then
       echo "DB_TIMEOUT=0" >> build.env # Injeksi bug regresi di commit 6
     else
       echo "DB_TIMEOUT=30" >> build.env
     fi
     git commit -am "chore(release): step $i"
   done
   ```
2. Buat file validator `validate.sh`:
   ```bash
   cat << 'EOF' > validate.sh
   #!/usr/bin/env bash
   grep -q "DB_TIMEOUT=0" build.env && exit 1
   exit 0
   EOF
   chmod +x validate.sh
   ```
3. Eksekusi pencarian otomatis:
   ```bash
   git bisect start
   git bisect bad HEAD
   git bisect good HEAD~9
   git bisect run ./validate.sh
   git bisect reset
   ```

---

### 13. Exercise

#### Level: Easy
Buat script Bash yang membaca commit hash tertentu dan mencetak output yang menunjukkan:
1. Hash SHA-1 dari Tree yang ditunjuk oleh commit tersebut.
2. Seluruh file beserta hash Blob yang ada di dalam Tree tersebut tanpa menggunakan perintah `git checkout`.
*Verifikasi*: Script harus berhasil mengekstraksi data pada repositori `lab-internals`.

#### Level: Medium
Terdapat 4 commit mikro lokal di branch `feature-auth`:
- `fix: typo variable`
- `feat: add jwt auth logic`
- `fix: correct token expiration logic`
- `refactor: format auth controller`

Lakukan interactive rebase (`git rebase -i`) untuk menggabungkan seluruh perubahan di atas menjadi 1 commit atomik standar conventional commit:
`feat(auth): implement complete JWT authentication with token validation`

#### Level: Hard
Sebuah repositori mengalami crash filesystem yang menyebabkan branch pointer `refs/heads/production` terhapus (`rm .git/refs/heads/production`), sementara reflog untuk branch tersebut korup/kosong. 
*Tugas*: Rekonstruksi branch `production` dari object database (`.git/objects/`) menggunakan `git fsck --lost-found`, identifikasi commit dangling yang relevan, dan kaitkan kembali pointer branch ke titik yang tepat.

---

### 14. Challenge

#### Skenario Insiden: "The Cross-Branch Secret Leak & Diverged Linear State"

Sebuah tim engineering berskala 50 orang sedang mempersiapkan rilis major ke production. Terjadi rentetan insiden berikut secara bersamaan:

1. Developer A melakukan merge `feature/payment` ke branch `staging` menggunakan merge commit standard.
2. Di dalam branch `feature/payment`, terdapat file `certs/private.key` yang berisi kunci enkripsi bank asli.
3. Developer B, C, dan D telah menarik (`git pull`) branch `staging` tersebut, membuat branch baru masing-masing dari `staging`, dan mem-push 12 commit baru di branch masing-masing yang bergantung pada logika baru payment.
4. Tim Security memerintahkan:
   - File `certs/private.key` **wajib terhapus dari seluruh commit history** di repositori remote maupun local.
   - Histori commit fungsional lainnya tidak boleh hilang.
   - Struktur histori di `staging` harus diubah menjadi strictly linear (mengeliminasi merge commit yang salah).
   - Seluruh developer (B, C, D) harus dapat mengintegrasikan branch pekerjaan mereka kembali di atas `staging` yang baru tanpa memunculkan kembali commit lama yang memuat private key tersebut.

**Instruksi Tantangan**:
Rancang runbook disaster recovery teknis langkah-demi-langkah (disertai blok perintah Git presisi, argumen flags, dan prosedur verifikasi audit) untuk mengeksekusi operasi sanitasi ini tanpa kehilangan integritas logika aplikasi tim.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)

1. **Bagaimana Git menentukan bahwa isi dari sebuah file identik dengan file lain di dalam repositori meskipun namanya berbeda?**
   * A. Berdasarkan metadata ekstensi file dan ukuran byte.
   * B. Melalui pencocokan hash SHA-1 dari konten file yang disimpan dalam Blob object terpisah.
   * C. Melalui pencatatan path direktori di file `.git/index`.
   * D. Menggunakan perbandingan timestamp modifikasi file di level sistem operasi.
   * *Jawaban*: B.
   * *Penjelasan*: Git adalah content-addressable storage. Blob hanya menyimpan isi konten. Jika dua file berbeda nama memiliki konten byte yang identik, keduanya menunjuk ke satu Blob object SHA-1 yang sama.

2. **Perintah plumbing apa yang digunakan untuk memeriksa tipe dari suatu objek Git secara spesifik?**
   * A. `git show --type <hash>`
   * B. `git cat-file -t <hash>`
   * C. `git check-ref-format <hash>`
   * D. `git ls-tree <hash>`
   * *Jawaban*: B.
   * *Penjelasan*: `git cat-file -t <hash>` akan mengembalikan jenis objek (`blob`, `tree`, `commit`, atau `tag`).

3. **Apa isi fisik dari sebuah file branch pointer di `.git/refs/heads/<nama-branch>`?**
   * A. Kumpulan diff patch dari base commit.
   * B. 40-karakter hexadecimal SHA-1 string dan newline char yang menunjuk ke commit terakhir.
   * C. File biner zlib terkompresi dari seluruh tree.
   * D. Log riwayat commit yang pernah dijalankan di branch tersebut.
   * *Jawaban*: B.
   * *Penjelasan*: Branch di Git hanyalah sebuah lightweight pointer; file teks sederhana berukuran 41 byte yang memuat hash commit terbaru.

4. **Kapan kondisi `detached HEAD` terjadi?**
   * A. Ketika file `.git/HEAD` terhapus secara fisik.
   * B. Saat Git menolak merge request akibat merge conflict.
   * C. Ketika HEAD menunjuk langsung ke commit hash tertentu, bukan ke sebuah branch reference.
   * D. Ketika branch lokal gagal disinkronkan dengan remote server.
   * *Jawaban*: C.
   * *Penjelasan*: HEAD normalnya menunjuk ke symbolic ref (seperti `refs/heads/main`). Jika checkout diarahkan langsung ke commit hash atau tag, HEAD berstatus detached.

5. **Apa fungsi dari argumen `--force-with-lease` dibandingkan `--force` biasa?**
   * A. Tidak mengizinkan overwrite branch jika ada branch protection di remote server.
   * B. Menolak force push jika upstream branch telah diperbarui oleh orang lain sejak fetch lokal terakhir.
   * C. Mengenkripsi push payload menggunakan secure SSH lease tokens.
   * D. Membuat commit backup secara otomatis di server sebelum histori ditimpa.
   * *Jawaban*: B.
   * *Penjelasan*: `--force-with-lease` membandingkan ekspektasi state remote ref kita dengan aktual di remote; jika ada update yang belum ditarik secara lokal, push dibatalkan untuk menghindari hilangnya commit rekan tim.

---

#### Bagian 2: Intermediate (5 Soal)

6. **Pada interactive rebase, apa perbedaan mendasar antara aksi `squash` dan `fixup`?**
   * A. `squash` menghapus perubahan kode, `fixup` mempertahankan perubahan kode.
   * B. Keduanya menggabungkan commit ke commit sebelumnya, namun `squash` membuka prompt editor untuk menggabungkan commit message, sedangkan `fixup` membuang commit message dari commit yang digabung.
   * C. `fixup` dapat diterapkan pada merge commit, sedangkan `squash` dilarang.
   * D. `squash` membuat tree baru, sedangkan `fixup` memodifikasi index file secara direct.
   * *Jawaban*: B.
   * *Penjelasan*: Keduanya menyatukan delta kode ke commit parent terdekat di atasnya. `squash` mengizinkan pengeditan pesan gabungan, `fixup` langsung menggunakan pesan commit parent tanpa konfirmasi.

7. **Jika eksekusi script pada `git bisect run <script>` mengembalikan return code `125`, tindakan apa yang diambil oleh engine Bisect Git?**
   * A. Menghentikan pencarian dan menetapkan commit saat ini sebagai titik regresi.
   * B. Melewati (skip) commit saat ini dan mencari commit di sekitarnya karena status commit ini tidak dapat diuji (untestable/broken dependency).
   * C. Membatalkan (abort) seluruh proses bisect dan mengembalikan state ke branch asal.
   * D. Membalik urutan pencarian binary search.
   * *Jawaban*: B.
   * *Penjelasan*: Kode keluar 125 direservasi oleh Git bisect untuk menandakan bahwa commit saat ini berada dalam kondisi tidak dapat diuji (misal kompilasi gagal akibat bug luar lingkup pengujian), sehingga Git akan memanggil `git bisect skip`.

8. **Bagaimana Git membedakan snapshot sebuah file yang memiliki permission executable script (`755`) dengan file biasa (`644`)?**
   * A. Informasi permission disimpan di dalam header chunk payload Blob object itu sendiri.
   * B. Informasi mode file disimpan di dalam entri direktori pada Tree object induknya.
   * C. Disimpan secara eksklusif di dalam file `.git/config`.
   * D. Git tidak peduli terhadap permission file sistem operasi Unix.
   * *Jawaban*: B.
   * *Penjelasan*: Blob murni data konten. Mode akses file (`100644`, `100755`) dicatat di baris entri file yang bersangkutan di dalam Tree object.

9. **Apa konsekuensi teknis dari menjalankan `git rebase` pada branch publik yang dipakai bersama oleh banyak engineer?**
   * A. Terjadinya korupsi data internal pada server remote GitHub/GitLab.
   * B. Riwayat commit cabang publik berubah hash-nya, menyebabkan duplikasi commit dan "merge conflicts hell" saat engineer lain melakukan fetch dan merge.
   * C. Branch publik terkunci dan beralih status menjadi read-only secara otomatis.
   * D. Git server akan menolak semua push di masa depan dari branch manapun.
   * *Jawaban*: B.
   * *Penjelasan*: Rebase menulis ulang commit SHA-1. Jika branch tersebut telah diclone orang lain, base ancestor mereka menjadi tidak cocok lagi, sehingga `git pull` berikutnya akan mencoba melakukan 3-way merge yang memunculkan commit duplikat dan konflik masif.

10. **Bagaimana mekanisme Garbage Collection (`git gc`) menentukan objek mana yang harus dibuang dari `.git/objects/`?**
    * A. Menghapus semua file yang memiliki ukuran lebih dari 100MB.
    * B. Melacak keterjangkauan (*reachability*) dari semua references (branches, tags, reflogs, HEAD); objek yang *unreachable* dan melewati batas kedaluwarsa waktu (*prune threshold*) akan dihapus.
    * C. Menghapus commit yang tidak memiliki author email berdomain valid.
    * D. Menghapus seluruh blob yang tidak memiliki nama file berevolusi.
    * *Jawaban*: B.
    * *Penjelasan*: Objek yang tidak memiliki path traverse dari ref manapun berstatus *dangling*. Objek ini dibuang jika usianya melampaui retention period (default: 30 hari untuk reflog unreachable, 14 hari untuk loose unreachable objects).

---

#### Bagian 3: Skenario Kasus Produksi (3 Soal)

11. **Skenario Insiden Release Pipeline**:
    Sebuah aplikasi monorepo mengalami crash looping di cluster Kubernetes production tepat setelah hotfix commit `a7b3c2` di-push. Pipeline CI/CD berjalan otomatis dan tidak ada developer yang memiliki akses terminal manual ke server. Tim hanya memiliki akses read-write ke repositori Git.
    Hotfix tersebut terdiri dari 4 commit:
    - `c1`: Minor CSS patch
    - `c2`: Skrip migrasi database breaking change
    - `c3`: Update endpoint URL
    - `c4`: Typo fix di doc
    
    Akar masalah teridentifikasi ada di commit `c2`. Tim tidak boleh menggunakan `git push --force` karena melanggar branch protection rule perusahaan.
    
    **Pertanyaan**: Apa langkah paling aman, cepat, dan sesuai standar audit yang harus dilakukan tim untuk membatalkan perubahan `c2` tanpa merusak riwayat commit lainnya?
    * A. Melakukan `git reset --hard HEAD~3` kemudian push dengan flag `--no-verify`.
    * B. Menggunakan `git revert c2`, menyelesaikan potensi konflik bila ada, dan mem-push commit revert baru ke remote branch.
    * C. Mengedit commit via `git rebase -i` lokal lalu meminta admin mematikan sementara branch protection rule.
    * D. Melakukan checkout commit `c1` ke branch baru lalu mengubah default branch di repositori.
    * *Jawaban*: B.
    * *Penjelasan*: `git revert <commit-sha>` adalah operasi murni aditif. Perintah ini membuat commit baru yang isinya menginversi perubahan dari commit target. Ini menjaga histori linear tetap utuh, tidak memerlukan force-push, dan mematuhi branch protection rules.

12. **Skenario Divergent History Pasca-Outage**:
    Developer A sedang bekerja di branch `feature-realtime`. Koneksi internet putus di tengah operasi `git rebase main`. Setelah koneksi kembali, developer panik dan mengeksekusi serangkaian perintah acak: `git checkout -b feature-realtime-backup`, `git reset --hard origin/main`, dan `git pull`. Akibatnya, seluruh pekerjaan lokal selama 3 hari yang belum sempat di-push hilang dari working directory dan branch tree.
    
    **Pertanyaan**: Bagaimana arsitek Git memandu proses pemulihan state kode lokal developer A tersebut?
    * A. Data hilang total dan tidak dapat dipulihkan karena belum pernah dikirim ke remote origin server.
    * B. Periksa direktori `.git/refs/original/` dan salin file packfile lama ke staging area.
    * C. Jalankan `git reflog`, cari entri operasi sebelum rebase pertama atau status commit lokal terakhir yang dibuat (sebelum checkout/reset), lalu jalankan `git branch restored-work <commit-sha-dari-reflog>`.
    * D. Jalankan `git clean -fdx` untuk membersihkan working directory lalu jalankan `git undo`.
    * *Jawaban*: C.
    * *Penjelasan*: Selama commit pernah dibuat secara lokal, Git menyimpan SHA-1 commit tersebut di reflog database lokal (`.git/logs/HEAD`). Mengidentifikasi commit state sebelum insiden melalui `git reflog` memungkinkan pemulihan branch 100% menggunakan `git branch <nama> <sha>`.

13. **Skenario Kerusakan Merge Strategy (Merge Ort Divergence)**:
    Dua branch parallel (`feat-crypto` dan `feat-fiat`) mengubah file arsitektur inti `engine.go` di baris yang sama. Saat branch `feat-crypto` di-merge ke `main`, conflict telah di-resolve dengan logika baru. Namun saat `feat-fiat` di-rebase di atas `main`, Git berulang kali berhenti dan meminta resolusi manual pada 8 commit berbeda untuk file yang sama persis, memicu risiko kesalahan manusia (human error).
    
    **Pertanyaan**: Mekanisme Git lanjutan apa yang seharusnya diaktifkan oleh developer sejak awal untuk membuat Git merekam dan otomatis menerapkan kembali resolusi konflik yang sama di masa mendatang?
    * A. Git Subtree Merging Logic (`git config --global merge.strategy subtree`).
    * B. Git Reuse Recorded Resolution (`git config --global rerere.enabled true`).
    * C. Git Safe Interactive Fast-Forward (`git config --global rebase.autoSquash true`).
    * D. Git LFS Content Tracking Extension (`git config --global lfs.fetchexclude`).
    * *Jawaban*: B.
    * *Penjelasan*: `git rerere` (*Reuse Recorded Resolution*) adalah fitur internal yang merekam bagaimana merge conflict diselesaikan. Jika konflik yang sama muncul lagi di kemudian hari (misalnya di tengah proses iterative rebase berseri), Git akan menerapkan resolusi yang sama secara otomatis tanpa intervensi developer.

---

### 16. Summary

1. **Fundamental Storage Engine**: Git adalah *Content-Addressable Storage* yang diakses melalui graf DAG. Perubahan nama atau permission file tidak memodifikasi data blob, melainkan hanya struktur representasi di dalam Tree object.
2. **Immutability of History**: Setiap commit terikat pada hash cryptographic parent-nya. Mengubah 1 byte di masa lalu akan mengubah seluruh hash anak secara berantai. Operasi `rebase` pada dasarnya adalah membuat commit *baru* yang identik kontennya namun memiliki parent yang berbeda.
3. **Plumbing Authority**: Memahami interface plumbing (`hash-object`, `cat-file`, `write-tree`, `commit-tree`, `update-ref`) membekali insinyur perangkat lunak kemampuan membedah dan merekonstruksi repositori yang rusak akibat system crash atau insiden human-error.
4. **Resilience via Reflog**: Kehilangan pointer branch bukan berarti kehilangan data. Selama objek belum dibuang oleh Garbage Collector (`git gc`), pointer commit selalu dapat dilacak dan dipulihkan sepenuhnya via `git reflog`.
5. **Enterprise Production Standard**: Repositori modern berskala enterprise menuntut implementasi Trunk-Based Development, signed commits terverifikasi, otomatisasi debugging menggunakan `git bisect`, serta mitigasi leak creds menggunakan modern scrubbing tools (`git-filter-repo`).