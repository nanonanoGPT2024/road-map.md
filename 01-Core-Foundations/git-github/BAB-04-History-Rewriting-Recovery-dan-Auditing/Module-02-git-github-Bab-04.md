# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (Git & GitHub)

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menguasai anatomi penyimpanan objek Git di disk (`loose objects`, `packfiles`, `bitmap indexes`, dan `commit-graphs`).
- Mengimplementasikan manipulasi riwayat tingkat lanjut secara deterministik menggunakan *interactive rebase*, *range selection*, dan `git-filter-repo`.
- Menavigasi, merekonstruksi, dan merecover metadata referensi Git yang hilang via `reflog`, *detached HEAD*, dan `git fsck`.
- Mendesain serta menerapkan arsitektur *monorepo* berskala enterprise menggunakan `sparse-checkout`, `scalar`, dan Git LFS.
- Membangun otomatisasi validasi *pre-commit* hingga *pre-receive* hooks yang terintegrasi dengan GitHub Enterprise Server/Cloud.

---

## 2. Prerequisite

- Pemahaman solid tentang siklus hidup Git dasar: `working tree`, `staging area (index)`, dan `commit history`.
- Menguasai dasar-dasar CLI Linux/Unix (POSIX-compliant shell, manipulasi I/O, `sed`, `awk`, `zlib`).
- Pemahaman dasar mengenai struktur data Graf Berarah Tak Berdaur (*Directed Acyclic Graph* / DAG) dan fungsi hash kriptografi (SHA-1 / SHA-256).
- Akses ke terminal dengan Git versi $\ge 2.40$ terinstal.

---

## 3. Concept & Internal Architecture

Git pada dasarnya adalah sebuah **Content-Addressable Storage (CAS)** yang dipasangkan dengan antarmuka penelusuran *VCS (Version Control System)* berbasis Directed Acyclic Graph (DAG).

```
                      +-------------------+
                      |   Git Object DB   |
                      |  (.git/objects/)  |
                      +---------+---------+
                                |
        +---------------+-------+-------+---------------+
        |               |               |               |
        v               v               v               v
  +-----------+   +-----------+   +-----------+   +-----------+
  |   BLOB    |   |   TREE    |   |  COMMIT   |   | TAG (Ann) |
  | Raw Data  |   | Directory |   | Metadata  |   | Explicit  |
  |  Payload  |   | Structure |   | + Pointer |   | Pointer   |
  +-----------+   +-----------+   +-----------+   +-----------+
```

### 3.1 Format Objek Dasar Git

Setiap objek di dalam direktori `.git/objects/` disimpan dengan format:
$$\text{store\_format} = zlib(\text{type} + \text{" "} + \text{size\_in\_bytes} + \text{"\textbackslash 0"} + \text{content})$$

1. **Blob**: Hanya menyimpan payload biner/teks dari sebuah file. Izin akses file (*file mode*), nama file, dan timestamp **tidak** disimpan di dalam blob.
2. **Tree**: Merepresentasikan direktori. Berisi daftar baris yang memetakan file mode, tipe objek (blob/tree), hash SHA, dan nama file/direktori.
3. **Commit**: Berisi referensi ke sebuah *root tree*, nol atau lebih hash parent commit, metadata pembuat/pengunggah (*author/committer* beserta stempel waktu), dan pesan log commit.
4. **Annotated Tag**: Berisi referensi ke objek tertentu (biasanya commit), metadata penandatangan (*tagger*), signature GPG opsional, dan pesan anotasi.

### 3.2 Packfiles, Indexes, dan Multipack Indexes (MIDX)

Seiring bertambahnya commit, menyimpan satu file per objek (*loose object*) akan menghabiskan *inode* sistem berkas dan menurunkan performa I/O. Git mengatasi masalah ini menggunakan format kompresi gabungan:

- **Packfile (`.pack`)**: Kumpulan gabungan banyak objek yang dikompresi menggunakan delta compression (objek disimpan sebagai perbedaan/delta terhadap objek lain yang serupa).
- **Index Pack (`.idx`)**: Berisi tabel *fan-out* dan hash terurut yang memetakan SHA ke *byte offset* di dalam file `.pack` agar pencarian objek dapat berjalan pada kompleksitas $O(\log N)$ atau $O(1)$.
- **Reachability Bitmaps (`.bitmap`)**: Bitmap terindeks per-commit yang memungkinkan Git menghitung relasi *reachability* antar branch (misalnya saat `git push` atau `git fetch`) dengan operasi logika biner (`AND`, `OR`) cepat tanpa perlu menjelajahi DAG secara manual.

---

## 4. Why & What

| Pendekatan / Fitur | What (Apa itu?) | Why (Mengapa diperlukan pada Skala Enterprise?) |
| :--- | :--- | :--- |
| **Interactive Rebase** | Penulisan ulang riwayat lokal secara linear dan deklaratif. | Menjaga riwayat trunk tetap bersih (*bisectable*), mempermudah audit perubahan, dan menghapus kesalahan sebelum dilempar ke remote. |
| **Git Reflog** | Jurnal pencatatan mutasi lokal pointer `HEAD` dan referensi branch. | *Safety net* mutlak untuk mengembalikan commit yang terhapus atau tersesat akibat `reset --hard` atau *rebase conflict* yang salah diselesaikan. |
| **Sparse-Checkout & Scalar** | Pembatasan virtualisasi checkout direktori tertentu di working tree. | Mengatasi limitasi performa pada monorepo multi-gigabyte sehingga developer hanya mengunduh dan memuat sub-tree yang relevan. |
| **Git LFS** | Penyimpanan aset biner besar di luar basis data Git dengan penunjuk teks (pointer). | Mencegah pembengkakan ukuran `.git` yang eksponensial akibat file binary (jar, zip, mp4, weights AI) yang tidak dapat dikompresi secara delta. |

---

## 5. How (Workflow Detail)

### 5.1 Siklus Rekonstruksi Riwayat Tingkat Lanjut (*Interactive Rebase*)
1. Git memisahkan pointer branch target dan membuat lingkungan *detached HEAD* pada basis commit yang dipilih.
2. Script instruksi TODO disusun di `.git/rebase-merge/git-rebase-todo`.
3. Engine mengeksekusi instruksi per baris: `pick`, `reword`, `edit`, `squash`, `fixup`, `drop`, atau `exec`.
4. Jika terjadi konflik, eksekusi dijeda. Git memperbarui file *index* dan menyajikan *working tree* untuk resolusi manual.
5. Resolusi diverifikasi, index diperbarui via `git add`, dan eksekusi dilanjutkan via `git rebase --continue`.
6. Referensi branch target dipindahkan secara atomik (*ref update*) ke commit teratas yang baru dibuat.

```
(main)       A---B---C
                  \
(feature)          D---E---F  --> git rebase -i main
                            \
                             D'--E'--F' (linear di atas C)
```

---

## 6. Analogy & Diagram ASCII

Bayangkan Git sebagai sistem **Buku Ekspedisi Logistik Kargo Kontainer**:

- **Loose Objects**: Tiap paket barang diletakkan terpisah di lantai gudang terbuka. Sangat mudah diambil jika jumlahnya sedikit, namun memenuhi ruang penyimpanan dengan cepat.
- **Packfile**: Paket-paket tersebut disusun rapi, dipres hampa udara, lalu dimasukkan ke dalam kontainer baja berukuran seragam.
- **Reflog**: Rekaman CCTV sekuriti gudang yang mencatat setiap pergerakan kontainer. Sekalipun seorang pekerja salah menaruh atau membuang kontainer keluar dari catatan utama, rekaman CCTV dapat diputar mundur untuk menemukan koordinat kargo tersebut secara akurat.

```
       INDEX/WORKING DIRECTORY                    GIT OBJECT STORE (DAG)
      +------------------------+             +-------------------------------+
      | File: src/main.rs      |             | Blob: a1b2c3...               |
      | Hash: sha1(content)    +------------>| (Raw File Payload)            |
      +------------------------+             +---------------+---------------+
                                                             ^
                                                             |
      +------------------------+             +---------------+---------------+
      | Dir:  src/             |             | Tree: f9e8d7...               |
      | Entry: [blob] main.rs  +------------>| (Directory Node Manifest)     |
      +------------------------+             +---------------+---------------+
                                                             ^
                                                             |
      +------------------------+             +---------------+---------------+
      | Commit: "feat: core"   |             | Commit: 4a5b6c...             |
      | Metadata: Tree, Author +------------>| (Root Pointer, Tree, Parent)  |
      +------------------------+             +-------------------------------+
                                                             ^
                                                             |
      +------------------------+             +---------------+---------------+
      | Branch: refs/heads/main+------------>| Points to: Commit 4a5b6c      |
      +------------------------+             +-------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Menyelidiki Struktur Internal Objek Git

Mari membuat objek Git murni secara manual tanpa menggunakan perintah tingkat tinggi (`porcelain`):

```bash
# Inisialisasi repo kosong
mkdir git-internals-lab && cd git-internals-lab
git init

# 1. Tulis string langsung ke CAS sebagai BLOB
BLOB_HASH=$(printf "console.log('enterprise-runtime');" | git hash-object -w --stdin)
echo "Blob Hash: $BLOB_HASH"

# 2. Periksa tipe dan ukuran objek
git cat-file -t $BLOB_HASH
git cat-file -p $BLOB_HASH

# 3. Buat file index sintetis dan masukkan blob ke dalamnya
git update-index --add --cacheinfo 100644 $BLOB_HASH index.js

# 4. Tulis index menjadi Tree Object
TREE_HASH=$(git write-tree)
echo "Tree Hash: $TREE_HASH"
git cat-file -p $TREE_HASH

# 5. Buat Commit Object yang menunjuk ke Tree tersebut
COMMIT_HASH=$(echo "feat: initial low-level commit" | git commit-tree $TREE_HASH)
echo "Commit Hash: $COMMIT_HASH"

# 6. Ikat HEAD lokal ke commit baru tersebut
git update-ref refs/heads/main $COMMIT_HASH
git symbolic-ref HEAD refs/heads/main

# Verifikasi riwayat log normal
git log -p
```

### 7.2 Practical Example: Enterprise Advanced Interactive Rebase & Scripted Fixup

Skenario: Memperbaiki commit historis di tengah branch fitur tanpa merusak commit setelahnya secara manual:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Buat branch demo
git checkout -b feature/auth-provider
echo "export const auth = () => false;" > auth.ts
git add auth.ts && git commit -m "feat(auth): add base provider"

echo "export const config = { port: 8080 };" > config.ts
git add config.ts && git commit -m "chore(config): add server port"

echo "export const parseToken = () => null;" >> auth.ts
git add auth.ts && git commit -m "feat(auth): implement token parser"

# KASUS: Ingin memperbaiki `base provider` tanpa interaksi manual GUI
# Buat perbaikan untuk commit pertama (hash: HEAD~2)
sed -i 's/false/true/' auth.ts
git add auth.ts

# Gunakan fixup commit yang otomatis menargetkan hash terkait
TARGET_COMMIT=$(git rev-parse HEAD~2)
git commit --fixup="$TARGET_COMMIT"

# Eksekusi autosquash non-interaktif
GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash HEAD~4

# Validasi bahwa riwayat telah bersih dan linear
git log --oneline -n 3
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Insiden Kebocoran Kredensial AWS IAM & *Monorepo Degradation* pada FinTech Bank "X"

#### Latar Belakang
Sebuah monorepo dengan ukuran direktori `.git` sebesar 45 GB (berisi 12 tahun riwayat commit) mengalami insiden:
1. Kunci privat root AWS (`AKIA...`) ter-commit ke dalam riwayat 6 bulan yang lalu di direktori legacy.
2. Waktu *clone* CI/CD pipeline melonjak hingga 42 menit per runner.

#### Solusi Rekayasa
Tim Platform Engineer menerapkan solusi dua arah: membersihkan seluruh riwayat Git secara deterministik dan merestrukturisasi monorepo.

```
[45 GB Repo: Blobs + Secret]
            |
            v
   [git-filter-repo] --------> Hapus Secret AWS & Pangkas Biner > 50MB
            |
            v
  [Sparse-Checkout + LFS] ---> Pisahkan Aset Statis ke Storage Bucket
            |
            v
[2.1 GB Repo + Sub-5 min Clone Time]
```

Langkah eksekusi menggunakan `git-filter-repo`:

```bash
# 1. Isolasi clone mirror repo untuk sanitasi menyeluruh
git clone --mirror git@github.com:bank-x/core-monorepo.git core-monorepo-sanitization.git
cd core-monorepo-sanitization.git

# 2. Analisis ukuran dan identifikasi blob terbesar
git-filter-repo --analyze

# 3. Hapus credential yang bocor secara mutlak dari SELURUH cabang dan tag
cat << 'EOF' > expressions.txt
AKIA[0-9A-Z]{16}==>REDACTED_AWS_KEY
EOF
git-filter-repo --replace-text expressions.txt

# 4. Hapus direktori biner legacy yang salah commit
git-filter-repo --path legacy-blobs/ --invert-paths

# 5. Optimasi packfile, rebuild commit-graph, dan expire reflog seketika
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# 6. Force-push mirror termutakhir ke upstream baru
git remote set-url origin git@github.com:bank-x/core-monorepo-sanitized.git
git push --mirror origin
```

#### Hasil Terukur
- Ukuran direktori `.git` terpangkas dari **45 GB menjadi 2.1 GB** (penurunan ~95%).
- Durasi fresh checkout di *ephemeral CI runners* turun dari **42 menit ke 2 menit 15 detik**.
- Kredensial lama dinonaktifkan di AWS IAM; signature commit baru diverifikasi via branch protection rules.

---

## 9. Trade-offs

```
                       TRADE-OFF PARADIGM
    Performance/Speed                   Traceability/Historical Context
          ▲                                         ▲
          │                                         │
    [Squash Merge]                           [Full Merge Commit]
    (Fast, Compact, Lossy)                  (Traceable, Bulky DAG)
          │                                         │
          +-------------------+---------------------+
                              │
                      [Rebase Linear]
                  (Clean, Re-writes Hashes)
```

| Strategi / Fitur | Pros | Cons | Dampak Latensi / Resource |
| :--- | :--- | :--- | :--- |
| **Squash-Merging** | Riwayat trunk (`main`) menjadi murni linear; ukuran `.git` tumbuh sangat lambat. | Menghilangkan granularitas riwayat konteks individual sub-fitur; metadata original author commit lebur. | I/O Git log sangat cepat; waktu eksekusi CI minimal. |
| **Merge Commits (`--no-ff`)** | Mempertahankan topologi percabangan yang akurat; mudah untuk me-*revert* satu set fitur secara utuh. | DAG menjadi rumit (*train track graph*); operasi penelusuran commit manual menjadi bising. | Penjelajahan DAG membutuhkan traversal CPU lebih tinggi; penambahan ukuran index. |
| **Git LFS** | Mengurangi beban transfer data blob biner pada `.git`; clone awal repo menjadi sangat ringan. | Ketergantungan infrastruktur storage LFS eksternal; latensi checkout bertambah jika terjadi *cache miss* file lokal. | Menghemat bandwidth clone secara masif; menambah dependensi network egress saat checkout pointer. |
| **Aggressive GC (`git gc`)** | Meminimalkan penggunaan ruang disk; mempercepat pembacaan packfile melalui delta loops. | Memerlukan utilisasi resource CPU (multi-core saturation) dan memori RAM yang sangat tinggi selama proses pengemasan (*re-packing*). | Eksekusi lokal memakan waktu menit hingga jam pada repo skala enterprise. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Salah Melakukan `git reset --hard` dan Kehilangan Commit Penting
- **Gejala**: Kode fitur lokal yang belum sempat di-push hilang dari working directory dan log branch.
- **Penyebab**: Pointer branch dipindahkan secara paksa ke commit lama, sementara commit baru belum digabungkan ke tree aktif manapun.
- **Solusi**:
```bash
# Telusuri log jejak mutasi pointer HEAD lokal
git reflog

# Output contoh:
# 3b4f12a HEAD@{0}: reset: moving to HEAD~2
# a8e90c1 HEAD@{1}: commit: feat(billing): add stripe webhook handler

# Pulihkan kondisi state ke commit yang dituju
git reset --hard HEAD@{1}
# ATAU buat branch penyelamat dari hash commit tersebut
git branch recovery-branch a8e90c1
```

### 10.2 Conflict Resolution yang Terjebak Saat Interactive Rebase
- **Gejala**: Shell menampilkan `(rebase-apply) | (rebase-merge)`, status branch ambigu, developer panik dan menghapus folder `.git`.
- **Penyebab**: Konflik kode terjadi di commit tengah dan resolusi tidak didaftarkan secara benar ke index.
- **Solusi**:
```bash
# JANGAN PERNAH menghapus direktori .git

# 1. Cek file yang berkonflik
git status

# 2. Selesaikan konflik secara manual pada file, lalu tandai selesai:
git add <conflicted-file>

# 3. Lanjutkan rebase (JANGAN jalankan 'git commit' secara langsung)
git rebase --continue

# Alternatif: Jika ingin membatalkan rebase secara aman dan kembali ke status awal:
git rebase --abort
```

---

## 11. Best Practices (Production Checklist)

### Arsitektur Git & Monorepo Checklist
- [ ] **Commit Graph Acceleration**: Aktifkan fitur `core.commitGraph` untuk mempercepat traversal log pada repo besar:
  ```bash
  git config --global core.commitGraph true
  git config --global gc.writeCommitGraph true
  ```
- [ ] **Deterministic Cleanliness**: Pastikan seluruh local feature branch telah di-rebase secara linear di atas `origin/main` sebelum membuat Pull Request.
- [ ] **Pre-Push Validation**: Pasang hook client-side untuk memblokir file berukuran $> 10\text{ MB}$ masuk ke CAS tanpa Git LFS.
- [ ] **Sparse Index & Checkout**: Gunakan konfigurasi sparse cone pada monorepo:
  ```bash
  git config core.sparseCheckout true
  git config core.sparseCheckoutCone true
  ```
- [ ] **Signing Commits**: Wajibkan verifikasi kriptografis (GPG/SSH signature) pada commit level enterprise untuk mencegah modifikasi identitas pengunggah (*author spoofing*):
  ```bash
  git config --global user.signingkey "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5..."
  git config --global gpg.format ssh
  git config --global commit.gpgsign true
  ```

---

## 12. Hands-on Practice

Simpan seluruh hasil latihan skrip dan manipulasi ini di direktori: `hands-on/m02/`.

### Langkah 1: Eksperimen Detached HEAD & Pemulihan Reflog
```bash
mkdir -p hands-on/m02/deep-dive-lab
cd hands-on/m02/deep-dive-lab
git init

# Buat commit baseline
for i in {1..5}; do
  echo "v$i content" > version.txt
  git add version.txt
  git commit -m "chore: bump to version $i"
done

# Masuk ke mode Detached HEAD pada commit ke-3 (HEAD~2)
git checkout HEAD~2

# Buat branch eksperimental tanpa nama cabang
echo "experimental hotfix" >> hotfix.txt
git add hotfix.txt
git commit -m "fix(hotfix): critical unreferenced patch"

# Beralih kembali ke main (meninggalkan commit perbaikan tanpa referensi)
git checkout main

# Periksa status: Commit eksperimental terlihat hilang dari git log
git log --oneline

# TEMUKAN DAN PULIHKAN:
LOST_HASH=$(git reflog -n 5 | grep "critical unreferenced patch" | awk '{print $1}')
echo "Recovered commit hash: $LOST_HASH"

# Rekonstruksi menjadi branch resmi
git branch recovered-hotfix $LOST_HASH
git log --oneline recovered-hotfix
```

### Langkah 2: Simulasi dan Resolusi Konflik Rebase Multi-Level
```bash
# Dari repo yang sama, buat dua feature branch terpisah
git checkout main
git checkout -b feature/database
echo "database: postgresql" >> services.yaml
git add services.yaml && git commit -m "feat(db): configure postgres"

git checkout main
git checkout -b feature/cache
echo "cache: redis" >> services.yaml
git add services.yaml && git commit -m "feat(cache): configure redis"

# Rebase feature/cache di atas feature/database (akan timbul konflik content)
git checkout feature/cache
set +e
git rebase feature/database
set -e

# Selesaikan konflik menggunakan strategi enterprise:
cat << 'EOF' > services.yaml
database: postgresql
cache: redis
EOF

git add services.yaml
git rebase --continue
```

---

## 13. Exercise

### Level Easy
Ambil sebuah commit pesan yang baru dibuat (`HEAD`), lalu ubah pesannya tanpa membuka editor interaktif menggunakan flag bawaan Git.
- *Petunjuk Target*: `git commit --amend -m "..."`.

### Level Medium
Diberikan 3 buah commit di lokal:
```text
c3 - fix: typo in variable
c2 - fix: wrong calculation logic
c1 - feat: implement scoring algorithm
```
Tuliskan rangkaian perintah Git CLI untuk menggabungkan `c3` dan `c2` langsung ke dalam `c1` sehingga riwayat commit hanya tersisa satu commit: `feat: implement scoring algorithm`.

### Level Hard
Buat sebuah bash script bernama `purge-large-binaries.sh` yang:
1. Memindai seluruh tree repository dan mencari semua objek dalam `.git` yang memiliki ukuran lebih besar dari 5 MB.
2. Mencetak hash SHA, nama file asli, dan ukurannya secara urut dari yang terbesar.
3. Menjalankan perintah non-interaktif untuk mengekstrak objek tersebut dari *index* tanpa menghapus file di working tree.

---

## 14. Challenge

### Skenario Insiden: "The Phantom Merge & Broken Submodule Divergence"
Sebuah tim release merilis patch darurat langsung ke branch `production`. Di saat bersamaan, developer lain melakukan rebase divergen pada branch `develop`, lalu tim CI/CD menggabungkan keduanya menggunakan *octopus merge* yang gagal di level submodule pointer. 

**Kondisi Lingkungan**:
- Repository memiliki submodule terikat yang merujuk pada commit SHA submodule yang belum di-push ke server remote.
- Terjadi siklus *detached HEAD* melingkar di mana `.git/index.lock` terkunci secara permanen akibat kill process mendadak dari container Docker.

**Tugas Anda**:
Rancang dokumen rancang-bangun *Disaster Recovery Plan* dan susun skrip Bash otomatis (`orchestrate-recovery.sh`) yang:
1. Mengamankan lock file tanpa merusak transaksi staging area.
2. Mengidentifikasi submodule dangling commit.
3. Menyusun ulang commit graph antara `production` dan `develop` tanpa menghasilkan duplicate SHA dan tanpa merusak tag audit historis.

*(Implementasikan script ini murni via Git raw tooling tanpa bantuan tool web/GUI).*

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. Apa perbedaan mendasar antara direktori `.git/refs/heads/` dan file `.git/HEAD`?
2. Mengapa Git mengkategorikan file blob hanya berdasarkan hash isinya, bukan berdasarkan nama filenya?
3. Apa perbedaan perintah `git rebase` versus `git merge` ditinjau dari integritas *commit hash*?
4. Apa fungsi dari perintah `git fsck`?
5. Di manakah Git menyimpan catatan operasional lokal yang dibuat oleh developer ketika pointer branch melompat?

### Bagian 2: Intermediate (5 Pertanyaan)
1. Jelaskan bagaimana mekanisme *delta compression* pada Git packfile bekerja saat membandingkan dua versi kode yang berbeda!
2. Apa yang terjadi secara internal di direktori `.git` ketika Anda mengeksekusi `git checkout --detach`?
3. Mengapa `git push --force` dilarang keras di main trunk repository enterprise, dan mengapa `git push --force-with-lease` dianggap sebagai alternatif yang lebih aman?
4. Bagaimana sparse-checkout mode "cone" mengoptimalkan pencocokan path jika dibandingkan dengan mode "full pattern matching" standar?
5. Jelaskan peran file `.gitattributes` dalam integrasi Git LFS!

### Bagian 3: Skenario Kasus Produksi (3 Skenario)
1. **Skenario 1**: Seorang junior engineer mengeksekusi `git reset --hard origin/main` saat berada di cabang fitur yang sedang digarap, menghapus 4 hari kerja lokal yang belum ter-push. Jelaskan langkah audit dan restorasi step-by-step menggunakan Git low-level tools!
2. **Skenario 2**: Pipeline deployment Kubernetes membaca commit graph Git dan mendeteksi bahwa branch rilis memiliki urutan waktu commit (`committer date`) yang melompat mundur secara anomali akibat rebase lokal dari zona waktu yang berbeda. Bagaimana Anda menstandardisasi commit timestamp secara otomatis di tahap staging?
3. **Skenario 3**: Sebuah monorepo mengalami degradasi performa I/O ekstrim di mana perintah `git status` memakan waktu 45 detik. Jelaskan arsitektur investigasi performa dan parameter Git filesystem daemon (`fsmonitor`, `untrackedCache`) yang harus dikonfigurasi untuk mereduksinya ke sub-detik!

---

## 16. Summary

- **Struktur Internal CAS**: Git adalah Directed Acyclic Graph (DAG) di atas Content-Addressable Storage berformat zlib. Empat objek intinya adalah **Blob**, **Tree**, **Commit**, dan **Annotated Tag**.
- **Manipulasi Riwayat**: `git rebase -i` memungkinkan rekonstruksi grafis riwayat secara deterministik. Penggunaan flag seperti `--fixup` dan `--autosquash` memungkinkan otomatisasi refaktorisasi commit tanpa intervensi editor manual.
- **Resiliensi dan Recovery**: Selama objek telah dicatat ke CAS (meskipun hanya berupa dangling blob/commit), **Reflog** dan **Low-Level Plumbing Tools** (`hash-object`, `cat-file`, `write-tree`, `update-ref`) dapat merekonstruksi branch yang terhapus secara utuh.
- **Skalabilitas Monorepo**: Operasi Git berskala enterprise bergantung pada efisiensi packfiles, commit-graph bitmaps, `git-filter-repo` untuk sanitasi ukuran, serta implementasi `sparse-checkout` dan Git LFS untuk mengisolasi beban kerja file besar.