# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. Membedah arsitektur internal Git (*Content-Addressable Storage*, *Directed Acyclic Graph* (DAG), dan struktur direktori `.git/`) menggunakan *plumbing commands*.
2. Mengimplementasikan alur kerja kolaboratif tingkat lanjut (*interactive rebasing*, *cherry-picking*, *Git worktrees*, dan *three-way merge conflict resolution*).
3. Mengonfigurasi dan mengotomatisasi *governance* repositori melalui *client-side/server-side Git Hooks*, *cryptographic signing* (GPG/SSH), dan *Branch Protection Rules*.
4. Mendiagnosis dan merehabilitasi anomali repositori tingkat produksi (kondisi *detached HEAD*, komit hilang, dan kebocoran kredensial) menggunakan `git reflog` serta utilitas *history rewriting*.
5. Merancang arsitektur percabangan terukur (*Scalable Trunk-Based Development* vs *Gitflow*) dengan mitigasi *trade-off* performa skala *enterprise*.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- Perintah dasar Git *porcelain*: `git init`, `add`, `commit`, `push`, `pull`, `branch`, `checkout`/`switch`.
- Konsep dasar protokol jaringan (SSH *keypair generation*, HTTPS token-based authentication).
- Pengoperasian antarmuka baris perintah (CLI) POSIX/Bash (manipulasi berkas, standard I/O redirection, environment variables).
- Dasar arsitektur kontrol versi terdistribusi (*Distributed Version Control Systems* / DVCS).

---

## 3. Concept & Internal Architecture

Git pada level fundamental bukanlah sistem kontrol versi berbasis *delta-based diff* konvensional (seperti SVN atau CVS), melainkan sebuah **Content-Addressable Key-Value Store** yang dilapisi oleh struktur data graf asiklik terarah (**Directed Acyclic Graph - DAG**).

```
                        +----------------------+
                        |   Working Directory  |
                        +----------------------+
                                   |
                             git add <file>
                                   v
                        +----------------------+
                        |   Index / Staging    |  <-- Binary file: .git/index
                        +----------------------+
                                   |
                            git commit -m
                                   v
+-----------------------------------------------------------------------+
|  Git Object Store (.git/objects/) & Directed Acyclic Graph (DAG)      |
|                                                                       |
|   +-------------------+                                               |
|   |   Commit Object   |                                               |
|   |  - tree: 4b825dc  |                                               |
|   |  - parent: 1a2b3c |                                               |
|   |  - author/committer|                                              |
|   +-------------------+                                               |
|             |                                                         |
|             v                                                         |
|   +-------------------+                                               |
|   |    Tree Object    |                                               |
|   |  - mode 100644    |                                               |
|   |    blob a1b2c3d   |                                               |
|   +-------------------+                                               |
|             |                                                         |
|             v                                                         |
|   +-------------------+                                               |
|   |    Blob Object    | (Plain file content, uncompressed via zlib)   |
|   |  "console.log()"  |                                               |
|   +-------------------+                                               |
+-----------------------------------------------------------------------+
```

### 3.1. Anatomi `.git/` Directory
Ketika perintah `git init` dieksekusi, Git menginisialisasi sub-sistem metadata:
- `HEAD`: File teks referensial yang menunjuk ke branch aktif saat ini (contoh: `ref: refs/heads/main`).
- `config`: Konfigurasi lokal repositori (menimpa level *global* `~/.gitconfig` dan *system* `/etc/gitconfig`).
- `index`: File biner yang merepresentasikan *staging area*, memetakan lintasan file ke *hash object*.
- `objects/`: Database objek internal. Memuat format *loose objects* (sub-direktori 2 digit heksadesimal pertama dari SHA) dan format *packfiles* (`.pack` dan `.idx`).
- `refs/`: Menyimpan pointer referensi lokal (`refs/heads/*`), remote-tracking (`refs/remotes/*`), dan tags (`refs/tags/*`).

### 3.2. Empat Tipe Git Objects (Primitif)
Setiap objek Git dienkapsulasi dengan *header* seragam: `type <size>\0<content>`, kemudian dikompresi menggunakan format `zlib` deflated dan di-hash menggunakan algoritma SHA-1 (160-bit, 40 karakter heksadesimal) atau SHA-256 (pada Git versi modern).

1. **Blob (*Binary Large Object*)**: Hanya menyimpan *payload* konten file mentah. Metadata seperti nama file, izin eksekusi (`mode`), dan timestamp **tidak** disimpan di dalam blob.
2. **Tree**: Merepresentasikan direktori sistem berkas. Berisi entri daftar berkas yang memetakan izin akses (misal: `100644` untuk regular non-executable file, `100755` untuk executable, `040000` untuk direktori pohon), tipe objek (*blob* atau *tree* bersarang), nama berkas, dan *hash SHA* referensinya.
3. **Commit**: Mengikat *Tree* root pada titik waktu tertentu dengan metadata historis: *parent commit hash(es)*, data pengarang (*author*), pencatat (*committer*), timestamp waktu epoch UNIX beserta offset zona waktu, serta pesan komit (*commit message*).
4. **Annotated Tag**: Objek independen yang menunjuk langsung ke commit hash tertentu dengan *tagger metadata*, timestamp, pesan tag khusus, dan opsional tanda tangan kriptografis PGP/GPG.

### 3.3. Plumbing vs. Porcelain
Git memisahkan antarmuka operasinya menjadi dua lapisan arsitektur:
- **Porcelain Commands**: Antarmuka tingkat tinggi (*high-level user interface*) yang ergonomis untuk kebutuhan harian, seperti `git add`, `git commit`, `git merge`, `git checkout`.
- **Plumbing Commands**: Antarmuka tingkat rendah (*low-level engine interface*) yang deterministik, presisi, dan cocok untuk automasi skrip internal: `git hash-object`, `git cat-file`, `git update-index`, `git write-tree`, `git commit-tree`, `git rev-parse`.

---

## 4. Why & What

| Dimensi | Antarmuka Standar (Porcelain/Manual) | Arsitektur Enterprise (Plumbing/Automated) |
| :--- | :--- | :--- |
| **Transparansi Histori** | Linier semu / tidak terkontrol via auto-merge | Terverifikasi deterministik via strict DAG rebase & sign |
| **Keamanan Kode** | Komit anonim, rawan impersonasi identitas | Cryptographically signed (GPG/SSH), Signed Commits |
| **Governance Mutu** | Validasi manual pasca push (terlambat) | Fail-fast via local/server Git Hooks & CI Pipeline Blockers |
| **Resolusi Anomali** | `git clone` ulang saat terjadi state corrupt | Bedah `git reflog`, cherry-pick, reset index tree level |
| **Workspace Scalability**| Satu folder per cabang (konteks switching mahal) | Git Worktrees (multi-konkurensi direktori satu storage) |

### Mengapa Pemahaman Plumbing Wajib di Skala Enterprise?
1. **Disaster Recovery**: Pemahaman atas *dangling objects* dan `reflog` mencegah kehilangan jam kerja akibat perintah destruktif seperti `git reset --hard` atau *force push* yang tidak disengaja.
2. **Deterministic CI/CD Tooling**: Pembuatan alat bantu internal, audit jejak langkah komit otomatis, dan verifikasi integritas dependensi memerlukan eksekusi *plumbing commands* untuk parsing performa tinggi tanpa dependensi UI visual.
3. **Integritas Rantai Pasok (*Supply Chain Security*)**: Penerapan validasi identitas kriptografis memastikan setiap baris kode yang masuk ke *production release branch* benar-benar berasal dari insinyur yang memiliki izin akses resmi.

---

## 5. How (Workflow Detail)

### 5.1. Alur Kerja Interactive Rebasing & Histori Linier
Interactive Rebasing (`git rebase -i`) merekonstruksi urutan komit dengan memainkan ulang (*replaying*) patch komit di atas basis commit baru:

```
State Awal DAG:
      (base)
o---o---A---B---C (feature)
         \
          D---E (main)

Tahapan Rebase Feature ke Main:
1. Git menandai ancestor bersama (A).
2. Menyimpan patch commit B dan C ke file temporary (.git/rebase-merge/).
3. Mereset pointer branch 'feature' ke target 'main' (E).
4. Mengaplikasikan patch B -> B', menangani konflik bila ada.
5. Mengaplikasikan patch C -> C'.

State Akhir DAG:
o---o---A---D---E (main)
                 \
                  B'---C' (feature)
```

Tindakan (*commands*) yang tersedia dalam interactive rebasing:
- `pick`: Mempertahankan commit apa adanya.
- `reword`: Mengubah pesan commit tanpa mengubah payload kode.
- `edit`: Berhenti pada commit tersebut untuk mengizinkan amandemen file atau pemecahan commit menjadi lebih kecil.
- `squash`: Menggabungkan commit dengan commit sebelumnya dan menggabungkan kedua log pesan.
- `fixup`: Menggabungkan perubahan ke commit sebelumnya, membuang log pesan commit ini (hanya menggunakan pesan commit induk).
- `drop`: Menghapus commit dari histori DAG.

### 5.2. Alur Kerja Resolusi Tiga Arah (Three-Way Merge Engine)
Ketika terjadi divergensi file antara `HEAD` lokal dan branch target, Git memanggil *recursive 3-way merge* (atau *ort* merge engine):
- **Base (Ancestor)**: Kondisi file pada titik percabangan terakhir.
- **Ours (`HEAD`)**: Kondisi file pada branch lokal yang sedang aktif.
- **Theirs**: Kondisi file pada branch eksternal yang sedang digabungkan.

Git hanya menaikkan status *Conflict Marker* (`<<<<<<<`, `=======`, `>>>>>>>`) jika baris yang sama dimodifikasi dengan cara berbeda dari titik Ancestor oleh kedua belah pihak secara bersamaan.

### 5.3. Konfigurasi Git Worktrees
Untuk menangani *hotfix* mendadak tanpa mengganggu state kompilasi/stashing di branch aktif, gunakan Git Worktree:
```bash
# Membuat worktree baru di direktori terpisah dengan branch hotfix independen
git worktree add ../hotfix-gateway-timeout -b hotfix/gateway-504
```
Fitur ini menggunakan basis `.git` yang sama (menghemat disk space dan transfer waktu cloning), tetapi memisahkan *working directory* dan *index*.

---

## 6. Analogy & Diagram ASCII

### Analogi: Content-Addressable Storage vs. Sistem Arsip Konvensional
- **Sistem Konvensional (SVN/CVS)**: Seperti buku kas akuntansi fisik. Saat halaman 4 berubah, dicatat: *"Pada hari X, kata 'A' diganti 'B' di halaman 4"*. Jika Anda merobek catatan perubahan, kondisi akhir berkas tidak dapat dihitung secara independen.
- **Git Storage Architecture**: Seperti brankas berdaya tampung tak terbatas yang dikunci dengan sidik jari digital (SHA Hash). Saat Anda memasukkan dokumen, mesin meng-hash isinya. Jika isinya adalah `Halo Dunia`, kuncinya adalah `d91e...`. Berkas yang sama persis tidak akan pernah disimpan dua kali (*deduplication*). Jika satu titik koma diubah, brankas menghasilkan sidik jari baru, mengunci dokumen baru, dan menyusun peta pohon baru (*tree object*) yang menunjuk ke dokumen baru tersebut.

### Diagram: Anatomi Objek Git Lengkap
```
+--------------------------------------------------------------------------+
| COMMIT OBJECT (Hash: 9e32a...)                                           |
|--------------------------------------------------------------------------|
| tree 72a81f335b2e9e...                                                   |
| parent 18c39e0839ab...                                                   |
| author Senior SRE <sre@enterprise.internal> 1709280000 +0700             |
| committer Release Bot <ci@enterprise.internal> 1709280000 +0700          |
| gpgsig -----BEGIN PGP SIGNATURE----- ...                                 |
|                                                                          |
| feat(auth): migrate token payload to asymmetric ed25519                  |
+--------------------------------------------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
| TREE OBJECT (Hash: 72a81...)                                             |
|--------------------------------------------------------------------------|
| 100644 blob a09fd8...    package.json                                    |
| 040000 tree 8831ef...    src/                                            |
+--------------------------------------------------------------------------+
                                     |
          +--------------------------+-------------------------+
          v                                                    v
+-----------------------------------+   +----------------------------------+
| BLOB OBJECT (Hash: a09fd...)      |   | TREE OBJECT (Hash: 8831e...)     |
|-----------------------------------|   |----------------------------------|
| {                                 |   | 100644 blob 331ae...    auth.ts  |
|   "name": "core-gateway",         |   +----------------------------------+
|   "version": "2.4.0"              |                     |
| }                                 |                     v
+-----------------------------------+   +----------------------------------+
                                        | BLOB OBJECT (Hash: 331ae...)     |
                                        |----------------------------------|
                                        | export class TokenService { ...} |
                                        +----------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Eksplorasi Plumbing Command
Membangun objek Git dari awal tanpa perintah `git add` atau `git commit`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Inisialisasi repositori eksperimental
mkdir -p /tmp/git-plumbing-demo && cd /tmp/git-plumbing-demo
git init

# 2. Tulis data mentah ke Object Store (Membuat Blob)
BLOB_HASH=$(echo "Enterprise Security Payload" | git hash-object -w --stdin)
echo "Blob Generated: ${BLOB_HASH}"

# 3. Verifikasi tipe dan isi blob
git cat-file -t "${BLOB_HASH}"
git cat-file -p "${BLOB_HASH}"

# 4. Tambahkan Blob ke Staging Area (Index) secara manual dengan mode 100644
git update-index --add --cacheinfo 100644 "${BLOB_HASH}" security-config.txt

# 5. Tulis Index ke dalam Tree Object
TREE_HASH=$(git write-tree)
echo "Tree Generated: ${TREE_HASH}"
git cat-file -p "${TREE_HASH}"

# 6. Buat Commit Object yang mereferensikan Tree Object
COMMIT_HASH=$(echo "feat(core): initial programmatic plumbing commit" | git commit-tree "${TREE_HASH}")
echo "Commit Generated: ${COMMIT_HASH}"

# 7. Update referensi HEAD lokal secara atomic
git update-ref refs/heads/main "${COMMIT_HASH}"

# 8. Verifikasi via porcelain log
git log -1 --stat
```

### 7.2. Practical Example: Implementasi Pre-Commit Hook Produksi
Automasi verifikasi integritas kode lokal sebelum di-commit (mencegah *leaked secrets*, validasi format commit):

Simpan berkas pada `.git/hooks/pre-commit`:
```bash
#!/usr/bin/env bash
# ==============================================================================
# Enterprise Pre-Commit Verification Hook
# Validasi Secret Hunting & File Hygiene
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo "==> [HOOK] Menjalankan validasi pre-commit..."

# 1. Deteksi file terlarang (.env, sertifikat privat, kredensial biner)
FORBIDDEN_PATTERNS='(\.env$|\.pem$|\.key$|id_rsa|_rsa$)'
STAGED_FILES=$(git diff --cached --name-only)

for FILE in ${STAGED_FILES}; do
    if echo "${FILE}" | grep -E -q "${FORBIDDEN_PATTERNS}"; then
        echo -e "${RED}[ERROR] Pelanggaran Keamanan! Berkas terlarang terdeteksi: ${FILE}${NC}"
        echo "Jangan pernah melakukan commit file konfigurasi rahasia ke VCS."
        exit 1
    fi
done

# 2. Deteksi string rahasia sensitif (AWS Keys, Private Keys, generic secrets)
if git diff --cached -U0 | grep -E -i -q '(aws_secret_access_key|bearer\s+[a-z0-9\._\-]{30,}|BEGIN PRIVATE KEY)'; then
    echo -e "${RED}[ERROR] Staged diff memuat deteksi secret / API credentials.${NC}"
    echo "Batalkan staging dan gunakan Vault / Environment Variable runtime."
    exit 1
fi

echo -e "${GREEN}[SUCCESS] Validasi pre-commit lolos standard compliance.${NC}"
exit 0
```
Beri izin eksekusi:
```bash
chmod +x .git/hooks/pre-commit
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario Insiden: Kebocoran Master API Key FinTech pada Repositori Publik
- **Platform**: Layanan Pembayaran Perbankan Terdistribusi (*High Volume Microservices*).
- **Insiden**: Seorang *junior developer* secara tidak sengaja men-stage file `.env.production` yang memuat kredensial *AWS Secret Key* dan *Database Encryption Master Key*, lalu melakukan `push` ke remote branch `feat/payment-gateway-rework`.
- **Dampak Potensial**: Kompromi infrastruktur PCI-DSS, denda regulasi finansial, pencabutan lisensi payment gateway.

### Strategi Mitigasi & Resolusi Arsitektural

#### Fase 1: Revokasi & Isolasi Kredensial (Zero-Minute Action)
Jangan berasumsi histori aman sebelum kunci diubah. Tim SRE harus segera mematikan/me-rotate *access key* yang terekspos di level cloud provider sebelum mengeksekusi mitigasi histori Git.

#### Fase 2: Purging Menggunakan `git-filter-repo` (Bukan Menggunakan `git rm`)
Melakukan `git rm .env.production && git commit` tidak menyelesaikan masalah karena objek *blob* kredensial tetap hidup abadi di komit sebelumnya dalam DAG.

```bash
# Instalasi modern filter utilitas (ekivalen performa tinggi BFG / pengganti git filter-branch yang deprecated)
pip3 install git-filter-repo

# Eksekusi pembersihan total path berkas dari seluruh riwayat komit cabang dan tag
git filter-repo --invert-paths --path .env.production --force

# Validasi bahwa hash blob telah musnah dari cache lokal
git log --all --full-history -- "**.env.production"
```

#### Fase 3: Garbage Collection & Dereferencing Forceful
Paksa Git membersihkan referensi sisa (`reflog`) dan mengeksekusi *garbage collection* agresif:
```bash
# Expire reflog sekarang juga
git reflog expire --expire=now --all

# Prune loose & unreachable objects secara destruktif
git gc --prune=now --aggressive
```

#### Fase 4: Force Push Terkoordinasi & Protected Branch Bypass Protocol
```bash
# Mengganti history secara aman dengan lease check untuk memastikan tidak menimpa komit orang lain
git push origin --force-with-lease --all
git push origin --force-with-lease --tags
```

---

## 9. Trade-offs

| Pendekatan | Keuntungan Utama | Kerugian / Risiko | Skenario Pemakaian Ideal |
| :--- | :--- | :--- | :--- |
| **Merge Commits (`--no-ff`)** | Mempertahankan konteks historis riil cabang fitur secara utuh. | Riwayat DAG menjadi rumit (*train track graph*), visualisasi log sulit dibaca. | Tim besar yang memerlukan audit historis penggabungan cabang secara eksplisit. |
| **Squash and Merge** | Riwayat `main` sangat bersih, 1 PR = 1 komit linier atomik. | Seluruh histori mikro (*individual sub-commits*) musnah, menyulitkan `git bisect`. | *Trunk-Based Development* dengan *pull request* cakupan kecil hingga sedang. |
| **Rebase and Merge** | Histori 100% linier, navigasi `git bisect` presisi tinggi. | Hash commit berubah (*rewriting history*); risiko konflik repetitif pada tiap commit. | Repositori tim dengan regulasi kepatuhan riwayat komit yang ketat. |
| **Git Submodules** | Memecah repositori masif; dependensi isolasi kode strictly pinned. | State "Detached HEAD" berulang; sinkronisasi commit lintas repo rawan *desync*. | Integrasi modul vendor pihak ketiga atau protokol bersama lintas bahasa. |
| **Monorepo (Single Repo)** | Atomics cross-project refactoring; single source of truth. | Skala ukuran `.git` membengkak; cloning lambat tanpa sparse-checkout/VFS. | Ekosistem mikroservis internal saling bergantung (*tightly coupled interfaces*). |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Kondisi Detached HEAD
- **Penyebab**: Pengguna mengeksekusi `git checkout <commit-hash>` secara langsung alih-alih me-reference branch. Komit baru yang dibuat dalam kondisi ini tidak memiliki pointer branch yang menampungnya, sehingga akan dihanguskan saat *garbage collection*.
- **Deteksi**:
  ```bash
  git status
  # Output: HEAD detached at 8f12a3d
  ```
- **Solusi**:
  ```bash
  # Segera buat pointer branch baru pada commit aktif saat ini
  git switch -c recovery-branch-name
  ```

### 10.2. Salah Eksekusi `git reset --hard` (Kehilangan Staged/Unstaged Work)
- **Penyebab**: Menjalankan reset hard tanpa mencadangkan perubahan lokal, membatalkan komit yang belum terdorong ke remote.
- **Deteksi & Pemulihan via `git reflog`**:
  ```bash
  # 1. Periksa histori pointer HEAD lokal
  git reflog show HEAD

  # Output:
  # 1a2b3c4 HEAD@{0}: reset: moving to HEAD~1
  # 9e8d7c6 HEAD@{1}: commit: feat(billing): add stripe webhook handler

  # 2. Kembalikan state pointer branch ke hash sebelum reset dilakukan
  git reset --hard HEAD@{1}
  ```

### 10.3. Merge Conflict Marker Terlanjur Ter-Commit
- **Penyebab**: Developer tidak teliti menandai komit tanpa menyelesaikan marker `<<<<<<< HEAD`, `=======`, `>>>>>>>`.
- **Deteksi**:
  ```bash
  git grep -E '^(<<<<<<<|=======|>>>>>>>)'
  ```
- **Solusi**:
  Perbaiki sintaks file sumber, lalu eksekusi:
  ```bash
  git commit --amend --no-edit
  ```

---

## 11. Best Practices (Production Checklist)

### Checklist Pra-Push & Produksi
- [ ] **Linearity**: Branch fitur telah di-rebase di atas commit terbaru `origin/main` sebelum membuat Pull Request.
- [ ] **Commit Message Standard**: Mematuhi format *Conventional Commits*:
  `<type>(<scope>): <short summary>` (Contoh: `fix(auth): prevent timing attack in hash validation`).
- [ ] **Cryptographic Verification**: Komit ditandatangani menggunakan GPG atau SSH signature key (`git commit -S -m "..."`).
- [ ] **Secret Hygiene**: Repositori memuat `.gitignore` global & lokal yang komprehensif. Tidak ada token, private key, atau `.env` yang ter-stage (`git status` bersih).
- [ ] **Branch Protection Policies**:
  - `main` / `master` dikunci (*read-only* langsung).
  - Wajib *Pull Request review* minimal oleh 2 *peer reviewer* berstatus CODEOWNERS.
  - Status check CI (linter, unit testing, SAST security scan) wajib bernilai `PASS`.
  - Mengaktifkan enforce "Require signed commits".
  - Mengaktifkan opsi "Require linear history" atau "Automatically delete head branches".

---

## 12. Hands-on Practice

Praktikum terpandu ini mensimulasikan perbaikan cabang dan repositori yang terdesinkronisasi. Siapkan direktori kerja pada `hands-on/m02/`.

### Tahap 1: Setup Workspace Hands-on
```bash
mkdir -p hands-on/m02/production-sim && cd hands-on/m02/production-sim
git init
git config user.name "Enterprise Architect"
git config user.email "architect@enterprise.internal"

# Inisialisasi basis aplikasi
cat << 'EOF' > app.js
function main() {
    console.log("Core Banking Engine v1.0.0");
}
main();
EOF

git add app.js
git commit -m "feat(core): initial production release"
git branch -M main
```

### Tahap 2: Menghasilkan Divergensi & Merge Conflict Buatan
```bash
# Buat branch feature A
git checkout -b feat/payment-v1
cat << 'EOF' > app.js
function main() {
    console.log("Core Banking Engine v1.1.0-alpha");
    console.log("Provider: Native Payment Gateway");
}
main();
EOF
git commit -am "feat(payment): integrate native payment gateway"

# Buat branch feature B dari main
git checkout main
git checkout -b feat/payment-v2
cat << 'EOF' > app.js
function main() {
    console.log("Core Banking Engine v1.1.0-beta");
    console.log("Provider: Cloud Payment Gateway");
}
main();
EOF
git commit -am "feat(payment): integrate cloud payment gateway"
```

### Tahap 3: Penyelesaian Konflik Tingkat Lanjut Menggunakan Diff3
```bash
# Konfigurasi Git untuk menampilkan common ancestor pada conflict marker
git config merge.conflictStyle diff3

# Pindah ke main dan gabungkan feat/payment-v1
git checkout main
git merge feat/payment-v1 --no-ff -m "merge: feat/payment-v1 into main"

# Coba rebase feat/payment-v2 di atas main terbaru
git checkout feat/payment-v2
git rebase main || true

# Periksa status
git status
```

Buka `app.js`. Anda akan melihat 3 blok:
1. `<<<<<<< HEAD` (Kondisi di branch `main`)
2. `||||||| merged common ancestor` (Kondisi saat percabangan awal)
3. `>>>>>>> feat(payment)...` (Kondisi di branch `feat/payment-v2`)

Selesaikan isi `app.js` menjadi implementasi terpadu:
```javascript
function main() {
    console.log("Core Banking Engine v1.1.0-prod");
    console.log("Provider: Hybrid Payment Gateway (Native & Cloud)");
}
main();
```

Selesaikan rebase:
```bash
git add app.js
git rebase --continue
```

### Tahap 4: Verifikasi DAG Linier
```bash
git log --graph --oneline --decorate --all
```

---

## 13. Exercise

### Level Easy
1. Gunakan perintah `git hash-object` untuk menghitung nilai SHA-1 hash dari string `"Sistem Terdistribusi"` tanpa menuliskan objek ke dalam database `.git/objects`.
2. Tampilkan tipe dan ukuran file dari objek hash hasil tugas nomor 1 menggunakan utilitas `git cat-file`.

### Level Medium
1. Buat branch baru `experiment-squash`. Lakukan 4 kali commit berturut-turut yang masing-masing hanya menambahkan satu baris teks ke dalam file `changelog.md`.
2. Lakukan interactive rebasing (`git rebase -i`) untuk menggabungkan (*squash*) 4 commit tersebut menjadi tepat 1 commit tunggal dengan format pesan: `docs(changelog): consolidate v1.0.1 - v1.0.4 update logs`.
3. Tunjukkan log historis (`git log -1`) untuk membuktikan hasil penggabungan.

### Level Hard
1. Buat skrip Bash otomatis yang mengekstraksi seluruh commit berstatus *dangling* / *orphaned* di dalam sebuah repositori dan menyimpannya ke dalam branch penyelamatan bernama `archive/salvaged-nodes`.
2. Skrip harus mampu memilah secara terprogram hanya objek komit yang dibuat dalam kurun waktu 48 jam terakhir tanpa memicu *error* jika tidak ada commit yatim yang ditemukan.

---

## 14. Challenge

### Studi Kasus: "The Split-Brain Disaster"
**Deskripsi Skenario:**
Sebuah pipeline CI/CD otomatis salah mengonfigurasi perintah `git filter-branch` di server *staging* yang menimpa histori cabang `release/v3.0.0` dan mem-force push hasil commit baru (dengan SHA yang berubah total) ke origin. Sementara itu, 5 tim pengembang telah melakukan percabangan (*branched-out*) dari branch `release/v3.0.0` versi lama dan terus membuat komit baru di atasnya.

**Tugas Anda:**
1. Rancang arsitektur strategi penyelamatan tanpa kehilangan histori pekerjaan yang sedang berjalan dari ke-5 tim tersebut.
2. Tuliskan urutan runbook langkah mitigasi Git (perintah spesifik CLI beserta argumen) yang wajib dijalankan oleh masing-masing insinyur pada repositori lokal mereka untuk memulihkan dependensi ke *canonical history* yang benar tanpa menduplikasi commit lama (mencegah *re-merge duplication storms*).
3. Definisikan langkah proteksi GitHub/GitLab API untuk mengunci branch agar insiden *force-push* serupa tidak dapat dieksekusi oleh service-account bot di kemudian hari.

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic

#### Q1: Objek Git apa yang bertanggung jawab menyimpan mapping antara nama berkas, mode file, dan referensi hash konten?
- A. Commit Object
- B. Blob Object
- C. Tree Object
- D. Tag Object

#### Q2: Apa fungsi utama dari file `.git/index`?
- A. Menyimpan konfigurasi global pengguna Git.
- B. Bertindak sebagai *staging area* biner yang memetakan file kerja ke objek pohon berikutnya.
- C. Menyimpan catatan log seluruh navigasi HEAD pengguna.
- D. Menyimpan riwayat unduhan paket dependensi.

#### Q3: Perintah plumbing manakah yang digunakan untuk membedah tipe dari sebuah hash objek tertentu?
- A. `git cat-file -t <hash>`
- B. `git show-type <hash>`
- C. `git verify-pack <hash>`
- D. `git rev-parse --type <hash>`

#### Q4: Manakah pernyataan yang BENAR mengenai Blob Object pada Git?
- A. Blob menyimpan tanggal modifikasi dan nama pengarang berkas.
- B. Jika dua file berbeda memiliki nama yang beda namun isi 100% identik, Git membuat dua blob berbeda.
- C. Blob hanya menyimpan isi payload berkas mentah terkompresi tanpa nama file aslinya.
- D. Blob selalu berukuran minimal 4KB terlepas dari isi berkas.

#### Q5: Di manakah Git menyimpan pointer cabang lokal yang aktif saat ini?
- A. `.git/refs/heads/`
- B. `.git/HEAD`
- C. `.git/config`
- D. `.git/logs/HEAD`

---

### 5 Pertanyaan Intermediate

#### Q6: Apa perbedaan mendasar antara `git rebase` dan `git merge` dalam struktur DAG?
- A. `merge` selalu gagal jika ada file yang dihapus, sedangkan `rebase` mengabaikannya.
- B. `rebase` membuat commit baru dengan memutar ulang patch di atas target dan mengubah hash, sedangkan `merge` menyatukan dua histori melalui sebuah merge commit tanpa mengubah riwayat sebelumnya.
- C. `rebase` hanya dapat dilakukan pada server remote.
- D. `merge` memformat ulang pesan commit sesuai standar conventional commit secara otomatis.

#### Q7: Jika Anda menjalankan `git reset --hard HEAD~1`, apa yang sebenarnya terjadi pada commit yang dibatalkan tersebut?
- A. File commit langsung dihapus permanen seketika dari hard drive.
- B. Objek commit tetap berada di `.git/objects/` sebagai *dangling object* hingga masa retensi `reflog` kedaluwarsa dan di-*prune* oleh garbage collection.
- C. Komit dipindahkan secara otomatis ke branch `refs/heads/stash`.
- D. Hanya staging area yang dibersihkan, working directory tidak tersentuh.

#### Q8: Apa manfaat utama mengaktifkan `git config merge.conflictStyle diff3`?
- A. Mempercepat proses kompilasi kode saat merge otomatis.
- B. Menampilkan titik dasar leluhur (*common ancestor*) di dalam marker konflik di samping versi lokal dan remote.
- C. Menghilangkan sepenuhnya kebutuhan resolusi manual.
- D. Mencegah Git melakukan merge secara fast-forward.

#### Q9: Kapan perintah `git push --force-with-lease` lebih disarankan dibanding `git push --force`?
- A. Ketika Anda ingin memaksa upload tanpa koneksi internet.
- B. Saat Anda ingin memastikan tidak menimpa komit rekan kerja yang telah didorong ke remote tanpa sepengetahuan Anda.
- C. Saat branch tujuan dilindungi oleh kunci PGP.
- D. Saat repositori lokal memiliki ukuran berkas di atas 2 GB.

#### Q10: Apa kegunaan utama utilitas `git worktree` dibanding membuat salinan direktori baru via `git clone`?
- A. Mengizinkan penggunaan banyak branch secara konkuren pada working directory terpisah dengan menggunakan basis database `.git` lokal yang sama.
- B. Menghilangkan kebutuhan untuk melakukan commit terhadap perubahan berkas.
- C. Menyimpan rahasia sistem di luar direktori repositori utama.
- D. Mengubah protokol repositori secara instan dari HTTPS ke SSH.

---

### 3 Skenario Kasus Produksi

#### Skenario 1
Sebuah automated cron job di server build mengeksekusi script yang memanggil `git gc --prune=now --aggressive` setiap 10 menit pada sebuah central bare repository. Di saat yang sama, tim developer melaporkan bahwa push berukuran sedang sering mengalami error `fatal: pack-objects died of signal 9` atau `fatal: unable to read sha1 file`.
**Pertanyaan:** Analisis akar permasalahan arsitektural ini dan apa solusi yang harus diterapkan?

#### Skenario 2
Seorang engineer secara tidak sengaja melakukan squash pada branch `main` lokal miliknya mundur sebanyak 50 commit ke belakang, lalu melakukan `git push --force` ke remote server branch `main`. Seluruh branch protection saat itu sedang dimatikan untuk keperluan maintenance migrasi infra.
**Pertanyaan:** Bagaimana langkah-langkah recovery tercepat dari sisi server atau engineer lain untuk mengembalikan commit history `main` ke state 1 detik sebelum force-push terjadi?

#### Skenario 3
Organisasi Anda memiliki monorepo berukuran 45 GB akibat banyaknya asset biner masa lalu. Developer mengeluhkan durasi cloning awal yang mencapai lebih dari 45 menit. Manajemen melarang pemisahan monorepo menjadi multi-repo karena tingginya dependensi dependensi internal.
**Pertanyaan:** Arsitektur dan konfigurasi Git modern apa yang harus diterapkan pada client dan CI environment untuk mereduksi durasi cloning ke hitungan detik tanpa memecah monorepo?

---

### Kunci Jawaban & Evaluasi

#### Kunci Jawaban Basic
1. **C. Tree Object** — Tree memetakan nama file, izin POSIX, dan referensi Blob/Sub-tree.
2. **B. Bertindak sebagai staging area biner yang memetakan file kerja ke objek pohon berikutnya** — File `.git/index` adalah struktur biner perantara working tree dan object store.
3. **A. `git cat-file -t <hash>`** — Opsi `-t` mengembalikan tipe objek (*blob, tree, commit, tag*).
4. **C. Blob hanya menyimpan isi payload berkas mentah terkompresi tanpa nama file aslinya** — Nama file berada pada level Tree.
5. **B. `.git/HEAD`** — File ini memuat symref ke branch aktif (`ref: refs/heads/...`).

#### Kunci Jawaban Intermediate
6. **B. `rebase` membuat commit baru...** — Rebase memodifikasi history dengan membuat node DAG baru; Merge mempertahankan histori dan menyatukan via merge node.
7. **B. Objek commit tetap berada di `.git/objects/`...** — Objek tidak langsung dihapus seketika; reflog melacak referensinya selama masa retensi (default 30-90 hari).
8. **B. Menampilkan titik dasar leluhur (*common ancestor*)...** — Memudahkan analisis logika kenapa kode diubah dari versi aslinya.
9. **B. Saat Anda ingin memastikan tidak menimpa komit rekan kerja...** — `--force-with-lease` memvalidasi apakah remote-tracking ref lokal cocok dengan kondisi remote branch sebelum menimpa.
10. **A. Mengizinkan penggunaan banyak branch secara konkuren...** — Berbagi satu database `.git/objects` sehingga hemat storage dan efisien secara I/O.

#### Kunci Jawaban Skenario Kasus Produksi

##### Solusi Skenario 1:
- **Akar Masalah**:
  1. `git gc --aggressive` membutuhkan konsumsi memori (RAM) dan CPU yang luar biasa intensif saat menyusun packfile deltas. Error signal 9 menandakan proses dibunuh oleh Linux Kernel *OOM (Out Of Memory) Killer*.
  2. Menjalankan garbage collection agresif setiap 10 menit saat transaksi baca/tulis konkuren aktif menyebabkan race-condition: objek sementara yang baru diunggah developer dianggap "unreachable" lalu dihapus oleh `--prune=now` sebelum commit tree selesai direkatkan.
- **Rekomendasi Arsitektural**:
  Matikan cron manual tersebut. Aktifkan fitur *Git Maintenance* bawaan (`git maintenance start`) yang menjalankan tugas pemeliharaan berkala secara aman di latar belakang, atur batas memori delta (`pack.windowMemory`), dan jadwalkan prune hanya pada periode non-aktif dengan grace period retensi (misal: `--expire=14.days`).

##### Solusi Skenario 2:
- **Langkah Pemulihan**:
  1. Cari engineer yang belum melakukan `git pull` setelah insiden force-push terjadi.
  2. Pada mesin engineer tersebut, remote tracking branch `origin/main` masih menunjuk pada commit hash SHA sebelum kejadian destruktif terjadi.
  3. Lakukan pengembalian paksa dari mesin engineer tersebut menggunakan hash yang valid:
     ```bash
     # Cari commit hash sebelum force push terjadi
     git reflog show origin/main
     # Atau periksa git log origin/main -1

     # Pulihkan main lokal ke hash tersebut
     git checkout main
     git reset --hard origin/main@{1} # atau masukkan commit hash langsung

     # Force-push kembali state yang benar
     git push origin main --force-with-lease
     ```
  4. Nyalakan kembali *Branch Protection Rules* secara permanen dengan membatasi izin *bypass force-push* bahkan untuk level Administrator.

##### Solusi Skenario 3:
- **Rekomendasi Arsitektur Git Skala Besar**:
  1. **Blobless / Treeless Clones**: Terapkan *partial clone* pada developer workstation dan CI runner:
     ```bash
     # Mengunduh histori commit & tree, blob diunduh secara on-demand saat checkout
     git clone --filter=blob:none <repo-url>
     ```
  2. **Sparse Checkout**: Isolasi workspace developer agar hanya me-render sub-direktori mikroservis yang sedang dikerjakan secara aktif:
     ```bash
     git sparse-checkout init --cone
     git sparse-checkout set services/core-banking libs/common
     ```
  3. **Git LFS (Large File Storage)**: Pindahkan asset biner non-text historis (gambar, video, bundle jar, dataset) ke Git LFS storage terpisah di luar DAG utama.
  4. **FSMonitor**: Aktifkan filesystem monitor (`git config core.fsmonitor true`) guna memangkas overhead pemindaian puluhan ribu file pada sistem berkas OS lokal.

---

## 16. Summary

1. **Git adalah Engine Berbasis CAS & DAG**: Setiap entitas di Git disimpan dalam bentuk *Blob*, *Tree*, *Commit*, atau *Tag* yang diindeks secara kriptografis menggunakan algoritma hashing melalui penyimpanan berbasis konten.
2. **Porcelain Dibangun di Atas Plumbing**: Seluruh operasi tingkat tinggi (`add`, `commit`, `checkout`) merupakan kumpulan operasi atomik dari *plumbing primitives* (`hash-object`, `update-index`, `write-tree`, `commit-tree`).
3. **Histori Bersih adalah Aset Enjiniring**: Penggunaan *interactive rebasing*, *squash merges*, dan *conventional commits* memfasilitasi audit forensik, automasi CI/CD terprediksi, serta memudahkan identifikasi anomali via `git bisect`.
4. **Keamanan adalah Prioritas Utama**: Kebocoran kredensial memerlukan pembersihan riwayat DAG secara tuntas (`git-filter-repo` + `reflog expire`) di samping rotasi kunci. Integritas rantai pasok diamankan dengan validasi komit bertanda tangan kriptografis (*Signed Commits*).
5. **Skalabilitas Memerlukan Strategi Terarah**: Pada skala repositori enterprise, utilisasi *Git Worktrees*, *Partial Clones*, *Sparse Checkout*, dan manajemen *Branch Protection* yang ketat menjadi fondasi esensial untuk menjaga throughput pengiriman perangkat lunak tetap tinggi dan stabil.