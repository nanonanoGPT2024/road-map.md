## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: GIT-CORE-04-01
* **Nama Modul**: History Rewriting, Recovery, and Auditing
* **Kategori**: 01-Core-Foundations
* **Tingkat Kesulitan**: Intermediate to Advanced
* **Prasyarat**:
  * Pemahaman mendalam mengenai Git Object Model (Blobs, Trees, Commits, Tags).
  * Kemahiran dalam branching dasar, three-way merge, dan resolusi merge conflict.
  * Pemahaman konsep Directed Acyclic Graph (DAG) pada Git.
* **Estimasi Waktu Belajar**: 180 Menit (Teori: 60 Menit, Praktik Hands-On: 120 Menit)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis** struktur DAG ketika terjadi modifikasi riwayat commit, memahami implikasi matematis dari perubahan SHA-1/SHA-256 pada node turunan.
2. **Mengoperasikan** `git rebase -i` (interactive rebase) secara presisi untuk manipulasi riwayat (squashing, rewording, dropping, reordering, dan splitting commits) sebelum integrasi ke branch utama.
3. **Mendiagnosis dan Menyelamatkan** commit, branch, atau state direktori kerja yang hilang menggunakan `git reflog`, `git fsck`, dan manipulasi dereferensi object.
4. **Mengisolasi dan Mengidentifikasi** regresi bug dalam basis kode secara otomatis menggunakan algoritma pencarian biner pada `git bisect`.
5. **Melakukan Audit Forensik** pada repositori menggunakan kombinasi filter tingkat lanjut dari `git log` dan sintaks mendalam dari `git blame`.
6. **Menerapkan** protokol kolaborasi yang aman (safe force-pushing) menggunakan `--force-with-lease` guna mencegah penimpaan destruktif pada remote repository.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       GIT REWRITING, RECOVERY & AUDITING
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        ▼                              ▼                              ▼
HISTORY REWRITING              DISASTER RECOVERY               FORENSIC AUDITING
  (Graph Mutation)               (Object Retrieval)             (State Inspection)
        │                              │                              │
  ├── git commit --amend        ├── git reflog                 ├── git log (Graph/Filters)
  ├── git rebase -i             ├── git fsck --lost-found      ├── git blame (-L, -C, -M)
  │    ├─ pick / reword         └── Dangling Commits/Trees     └── git bisect
  │    ├─ squash / fixup                                            ├─ start / bad / good
  │    ├─ drop / edit                                               └─ run <script>
  │    └─ exec
  └── git push --force-with-lease
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Git sering kali dipromosikan sebagai sistem yang *immutable* (kekal), di mana setiap aksi dicatat dan tidak dapat diubah. Namun, kenyataan rekayasa perangkat lunak modern menuntut fleksibilitas:
* Developer melakukan eksperimen lokal yang menghasilkan commit kotor ("wip", "fix typo", "test").
* Bug regresif yang tidak terdeteksi selama berminggu-minggu masuk ke branch produksi dan membutuhkan penelusuran jutaan baris kode secara efisien.
* Perubahan destruktif yang tidak disengaja (`git reset --hard`, salah hapus branch) dapat melumpuhkan produktivitas tim jika developer tidak memahami arsitektur internal Git untuk memulihkan data.

Tanpa pemahaman *History Rewriting*, repositori enterprise akan berubah menjadi tumpukan commit sampah yang menyulitkan peninjauan kode (*code review*), menghancurkan kejelasan *semantic versioning*, dan membuat *continuous delivery* rapuh. Tanpa *Recovery* dan *Auditing*, developer bekerja dalam ketakutan akan kehilangan data, dan tim investigasi insiden kehilangan kemampuan melacak sumber anomali secara deterministik.

---

## SEKSI 05 — APA ITU (WHAT)

Modul ini membedah tiga pilar utama manipulasi riwayat tingkat lanjut dalam Git:

1. **History Rewriting (Mutasi Riwayat)**: Proses pembuatan commit baru secara sengaja untuk menggantikan commit lama pada DAG. Git tidak pernah benar-benar "mengubah" commit yang ada; Git membuat objek commit baru dengan metadata yang disesuaikan, lalu memindahkan referensi penunjuk branch ke node baru tersebut.
2. **Disaster Recovery (Pemulihan Bencana)**: Mekanisme pelacakan internal berbasis log referensi lokal (`reflog`) dan deteksi orphan/dangling object di dalam database Git (`.git/objects`) untuk mengembalikan commit yang terputus dari tip branch.
3. **Forensic Auditing (Audit Forensik)**: Penggunaan perkakas analisis repositori untuk menginspeksi asal-usul setiap baris kode (`blame`), melacak evolusi struktural file (`log`), dan mengeksekusi algoritma *divide-and-conquer* biner (`bisect`) untuk mendeteksi anomali fungsional dalam hitungan detik.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Mekanisme Imutabilitas dan Regenerasi Hashing
Objek Commit Git terdiri dari:
* SHA dari root `tree` (representasi direktori kerja).
* SHA dari satu atau lebih `parent commit`.
* Metadata: Author, Committer, Timestamps.
* Pesan commit (*commit message*).

Kriptografi Git memastikan bahwa jika Anda mengubah satu bit saja dari data tersebut (misalnya pesan commit atau parent commit), SHA identifier dari commit tersebut berubah total. Konsekuensinya: **Mengubah commit di masa lalu secara matematis memaksa semua commit turunannya (*child commits*) untuk ditulis ulang dengan SHA baru.**

### 2. Anatomi Interactive Rebase (`git rebase -i <base>`)
Ketika Anda menjalankan perintah `git rebase -i HEAD~N`:
1. Git membuat daftar TODO berisi rentang commit dari `<base>` hingga commit saat ini (`HEAD`).
2. Git melepaskan `HEAD` (*detached HEAD*) dan menempatkannya pada `<base>`.
3. Git membaca instruksi dari skrip TODO baris demi baris:
   * **pick**: Mengaplikasikan patch commit tersebut menggunakan algoritma `cherry-pick`.
   * **reword**: Mengaplikasikan patch, membuka editor untuk mengubah pesan.
   * **edit**: Menghentikan proses eksekusi dan menyerahkan kontrol shell kepada pengguna untuk memodifikasi working tree atau index.
   * **squash / fixup**: Menggabungkan perubahan commit tersebut ke dalam commit sebelumnya (perbedaannya: `squash` mempertahankan dan menggabungkan pesan; `fixup` membuang pesan commit saat ini).
   * **drop**: Menghilangkan commit secara permanen dari linearitas branch baru.
   * **exec**: Mengeksekusi perintah shell pada titik commit tersebut (berguna untuk otomatisasi pengujian).
4. Penunjuk branch dimajukan (*fast-forwarded*) ke commit teratas yang baru dibuat.

### 3. Arsitektur Git Reflog
`reflog` (*Reference Logs*) adalah mekanisme keamanan lokal Git yang mencatat riwayat pembaruan penunjuk referensi (`HEAD` dan nama-nama branch). 
* Terletak di direktori `.git/logs/HEAD` dan `.git/logs/refs/heads/<branch>`.
* Tidak pernah di-*push* ke remote server; bersifat sepenuhnya privat di mesin lokal Anda.
* Setiap kali `HEAD` bergerak (karena `checkout`, `commit`, `rebase`, `reset`, `merge`), entri baru ditambahkan ke log dengan penunjuk indeks berbasis array (contoh: `HEAD@{0}`, `HEAD@{1}`).
* Objek yang ditinggalkan oleh `git reset --hard` tidak langsung dihapus, melainkan menjadi *dangling objects*. Objek ini dipertahankan secara default selama 30 hari (atau 90 hari untuk objek yang masih direferensikan) sebelum dibersihkan oleh Garbage Collector (`git gc`).

### 4. Algoritma Git Bisect
`git bisect` mengimplementasikan algoritma **Pencarian Biner (Binary Search)** langsung pada DAG repositori:
1. Memerlukan penanda titik buruk/rusak (`bad commit`) di mana bug terdeteksi, dan titik baik (`good commit`) di masa lalu di mana bug belum ada.
2. Git menghitung jumlah commit di antara kedua titik tersebut dan melakukan *checkout* otomatis tepat di commit median (tengah).
3. Penguji menandai status commit median tersebut:
   * Jika median **rusak**: Git mengeliminasi paruh kedua riwayat dan mempersempit rentang ke paruh pertama.
   * Jika median **baik**: Git mengeliminasi paruh pertama riwayat dan mempersempit rentang ke paruh kedua.
4. Kompleksitas pencarian adalah $\mathcal{O}(\log n)$, di mana $n$ adalah jumlah commit. Sebuah regresi di antara 1.024 commit dapat diidentifikasi secara presisi hanya dalam maksimal 10 langkah evaluasi.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Diagram 1: Transformasi DAG pada Interactive Rebase (Squash & Reorder)

```
KONDISI AWAL:
               (HEAD -> feature)
                 │
[C1] ───> [C2] ───> [C3] ───> [C4]
  │        │        │        │
  │        │        │        └─ Feature B (WIP/Fix typo)
  │        │        └────────── Feature A (Core implementation)
  │        └─────────────────── Initial feature scaffold
  └──────────────────────────── (Base Commit)

OPERASI: Reorder C3 ke depan, lalu Squash C4 ke dalam C2

HASIL DAG:
                 (HEAD -> feature)
                 │
                 [C4'] (Menggabungkan diff C2 + C4)
                ╱
[C1] ───> [C3'] 
  │
  └─ [C3] kini menjadi parent dari [C4'], SHA C3' dan C4' berubah total!

DANGLING STATE (Akan dibersihkan Garbage Collection):
  [C2] ───> [C3] ───> [C4] (Yatim / Tanpa Referensi Branch Aktif)
    ▲
    └─ Tersimpan dan terlacak di `git reflog`
```

### Diagram 2: Pelacakan Reflog Setelah Operasi Destruktif (`git reset --hard`)

```
Kejadian: Developer menjalankan `git reset --hard HEAD~2` secara tidak sengaja.

STATE SEBELUM RESET:
[A] ───> [B] ───> [C] (HEAD -> main)

STATE SETELAH RESET:
[A] (HEAD -> main)
 │
 └───> [B] ───> [C] (Dangling/Unreachable Commits)

REFLOG TRACKING TABLE (.git/logs/HEAD):
┌──────────┬──────────────┬─────────────────────────────────────────────────┐
│ Pointer  │ Target Hash  │ Action Description                              │
├──────────┼──────────────┼─────────────────────────────────────────────────┤
│ HEAD@{0} │ hash(A)      │ reset: moving to HEAD~2                         │
│ HEAD@{1} │ hash(C)      │ commit: Add feature C                           │
│ HEAD@{2} │ hash(B)      │ commit: Add feature B                           │
│ HEAD@{3} │ hash(A)      │ commit: Add feature A                           │
└──────────┴──────────────┴─────────────────────────────────────────────────┘

RECOVERY:
Menjalankan `git reset --hard HEAD@{1}` atau `git branch recovery-branch HEAD@{1}`
mengembalikan branch pointer kembali ke node [C] secara instan.
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

### Kasus: Memodifikasi Commit Terakhir (`git commit --amend`) dan Memulihkannya via Reflog

#### Langkah 1: Buat commit awal yang salah
```bash
# Inisialisasi sandbox
mkdir git-recovery-demo && cd git-recovery-demo
git init

# Buat file konfigurasi
echo "DATABASE_PORT=3306" > config.env
git add config.env
git commit -m "feat: config database"
```

#### Langkah 2: Mengubah commit menggunakan `--amend`
```bash
# Tambahkan data baru yang tertinggal
echo "DATABASE_HOST=localhost" >> config.env
git add config.env

# Modifikasi commit terakhir (baik file maupun pesannya)
git commit --amend -m "feat: configure database connection parameters"
```

#### Langkah 3: Menyelidiki apa yang terjadi secara internal
```bash
# Periksa log standar
git log --oneline
# Output hanya menampilkan 1 commit baru

# Periksa reflog untuk melihat commit lama
git reflog
```
*Output Representatif:*
```
a1b2c3d HEAD@{0}: commit (amend): feat: configure database connection parameters
e4f5g6h HEAD@{1}: commit (initial): feat: config database
```
Commit `e4f5g6h` masih ada di dalam disk. Jika amend tersebut salah, Anda cukup menjalankan:
```bash
git reset --hard HEAD@{1}
```
Dan repositori Anda kembali ke kondisi sebelum amend dilakukan.

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

### Kasus Nyata: Investigasi Bug Produksi dengan `git bisect` Terotomatisasi dan Reorganisasi Riwayat

#### Skenario:
Sebuah fungsi komputasi matematika regresi diperkenalkan di antara puluhan commit. Tim QA menemukan bahwa fungsi `calculateTax(100)` menghasilkan nilai negatif di branch `main`, padahal sebelumnya menghasilkan output `110`.

#### 1. Setup Simulasi Lingkungan Kasus
```bash
mkdir enterprise-bisect-lab && cd enterprise-bisect-lab
git init

# Buat baseline yang valid
cat << 'EOF' > calculator.py
def calculate_tax(base):
    return base * 1.10

if __name__ == "__main__":
    assert calculate_tax(100) == 110.0, "Regression detected!"
    print("Test Passed")
EOF

git add calculator.py
git commit -m "feat: initial working tax calculator"
GOOD_COMMIT=$(git rev-parse HEAD)

# Tambahkan 10 dummy commits
for i in {1..5}; do
    echo "# optimization step $i" >> calculator.py
    git commit -am "chore: code optimization step $i"
done

# Injeksi Bug di commit ke-6
cat << 'EOF' > calculator.py
def calculate_tax(base):
    return base * -1.10  # BUG INTRODUCED

if __name__ == "__main__":
    assert calculate_tax(100) == 110.0, "Regression detected!"
    print("Test Passed")
EOF
git commit -am "refactor: optimize tax arithmetic matrix"

# Tambahkan beberapa commit lanjutan
for i in {6..10}; do
    echo "# documentation update $i" >> README.md
    git add README.md
    git commit -m "docs: update section $i"
done
BAD_COMMIT=$(git rev-parse HEAD)
```

#### 2. Menjalankan Git Bisect Secara Otomatis
Alih-alih melakukan tes manual pada puluhan commit, kita gunakan skrip Python bawaan sebagai predikat kelulusan (*test runner*).

```bash
# Mulai sesi bisect
git bisect start

# Tentukan batas boundary
git bisect bad $BAD_COMMIT
git bisect good $GOOD_COMMIT

# Jalankan otomasi pencarian
git bisect run python3 calculator.py
```

*Output Terminal:*
```
Bisecting: 5 revisions left to test after this (roughly 3 steps)
[commit hash...] chore: code optimization step 3
running python3 calculator.py
Test Passed
Bisecting: 2 revisions left to test after this (roughly 1 step)
[commit hash...] refactor: optimize tax arithmetic matrix
running python3 calculator.py
Traceback (most recent call last):
  File "calculator.py", line 5, in <module>
    assert calculate_tax(100) == 110.0, "Regression detected!"
AssertionError: Regression detected!
...
<hash> is the first bad commit
commit <hash>
Author: Lead Engineer <lead@enterprise.com>
Date:   ...
    refactor: optimize tax arithmetic matrix
```

#### 3. Mengakhiri Sesi Bisect
```bash
# Mengembalikan repository ke HEAD asli
git bisect reset
```

#### 4. Audit Siapa yang Mengubah Baris Spesifik dengan `git blame`
```bash
# Menelusuri baris 1 sampai 3 file calculator.py beserta timestamp dan commit hash
git blame -L 1,3 calculator.py
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Pendekatan / Keputusan | Keuntungan | Kerugian / Risiko | Mitigasi |
| :--- | :--- | :--- | :--- |
| **Interactive Rebase** sebelum PR merge | Riwayat commit bersih, atomik, mudah dibaca, mempermudah `git revert` terisolasi. | Menghancurkan riwayat kronologis asli; mengubah hash seluruh child commit. | Gunakan **hanya** pada *feature branch* lokal yang belum di-share ke developer lain. |
| **Push Force (`--force`)** | Memaksa remote branch sinkron dengan local branch yang telah di-rewrite. | Menghancurkan pekerjaan rekan kerja jika mereka telah meletakkan commit baru di branch tersebut. | **DILARANG KERAS**. Gunakan `--force-with-lease` sebagai standar wajib mutlak. |
| **Squash Everything on Merge** | Main branch selalu memiliki commit tunggal per fitur (1 PR = 1 Commit). | Menghilangkan konteks granular mikro-evolusi kode selama development. | Tulis PR summary yang sangat mendalam dan terstruktur pada final squashed commit. |
| **Preserving Merge Commits (`--no-ff`)** | Mempertahankan topologi asli riwayat pengembangan tanpa rekayasa. | Riwayat menjadi sangat berantakan ("spaghetti graph"), sulit dianalisis via `git bisect`. | Terapkan standarisasi trunk-based development dengan branch yang berusia pendek. |

---

## SEKSI 11 — BEST PRACTICES

1. **Aturan Emas Rebase (The Golden Rule of Rebasing)**: 
   * *Jangan pernah melakukan rebase pada commit yang sudah berada di luar kontrol lokal Anda (public/shared branch seperti `main`, `master`, `staging`, `develop`).* Rebase pada public branch akan memaksa rekan setim melakukan re-merge berulang-ulang yang merusak integritas repositori.
2. **Gunakan Proteksi Push Secara Ketat**:
   * Jadikan alias berikut sebagai standar di shell lingkungan kerja:
     ```bash
     git config --global alias.pf "push --force-with-lease --force-if-includes"
     ```
   * Flag `--force-with-lease` memeriksa apakah remote reference sama dengan apa yang ada di local remote-tracking branch Anda. Jika ada developer lain yang baru saja melakukan push, Git akan menolak operasi tersebut.
3. **Commit Atomik dan Semantik**:
   * Sebelum mengajukan Pull Request, rapikan riwayat Anda: gunakan `fixup` untuk menggabungkan commit-commit penambal kesalahan sintaksis, dan `reword` untuk memastikan judul commit mengikuti konvensi standard (*Conventional Commits*).
4. **Audit Mengabaikan Whitespace pada Blame**:
   * Jangan biarkan formater otomatis mengaburkan sejarah kepemilikan kode:
     ```bash
     git blame -w -M -C <file>
     ```
     * `-w`: Mengabaikan modifikasi whitespace.
     * `-M`: Mendeteksi pemindahan baris dalam file yang sama.
     * `-C`: Mendeteksi baris kode yang disalin atau dipindahkan dari file lain dalam commit yang sama.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Menghancurkan Branch Rekan Kerja dengan `git push --force`
* **Gejala**: Developer melakukan rebase lokal, lalu menjalankan `git push origin feature-branch --force`. Pekerjaan rekan kerja yang di-push beberapa menit sebelumnya tertimpa dan hilang dari log remote.
* **Solusi Perbaikan**: Gunakan remote audit log (GitHub/GitLab audit trail) atau periksa `git reflog` pada mesin rekan kerja untuk mendapatkan commit SHA yang tertimpa, lalu buat branch pemulihan.

### 2. Panik Setelah `git reset --hard` yang Salah Sasaran
* **Gejala**: Developer berniat membatalkan staged file, namun mengeksekusi `git reset --hard HEAD~1` dan mengira kode mereka musnah selamanya.
* **Solusi Perbaikan**: Segera periksa `git reflog`, cari commit hash sebelum eksekusi reset (sering kali ditandai dengan aksi terakhir), lalu checkout commit tersebut:
  ```bash
  git branch recovery-point HEAD@{1}
  ```

### 3. Berada dalam Kondisi Detached HEAD Tanpa Sadar
* **Gejala**: Menjalankan `git checkout <commit-hash>` untuk memeriksa kode lama, lalu membuat beberapa commit baru di sana. Begitu pindah branch (`git checkout main`), semua commit baru seolah-olah lenyap.
* **Solusi Perbaikan**: Objek commit masih ada di object store. Buka `git reflog`, temukan commit terakhir yang dibuat pada state detached tersebut, lalu buat branch resmi:
  ```bash
  git branch new-branch-name <commit-hash>
  ```

### 4. Menjalankan Bisect pada Direktori Kerja yang "Kotor" (*Dirty Working Directory*)
* **Gejala**: Eksekusi `git bisect` gagal berpindah commit atau terjadi conflict file lokal yang belum di-commit.
* **Solusi Perbaikan**: Selalu bersihkan atau amankan state sebelum audit:
  ```bash
  git stash save "Stashed state before bisecting"
  ```

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario 1: Interactive Rebase dan Code Sanitization
* **Tujuan**: Menggabungkan 4 commit eksperimental lokal menjadi 2 commit bersih dengan standar Conventional Commits.
* **Tugas**:
  1. Buat folder `hands-on-rebase` dan inisialisasi Git.
  2. Buat file `service.py`. Commit 1: `feat: skeleton service`.
  3. Edit file, commit 2: `fix: typo in function name`.
  4. Edit file, commit 3: `wip: logic implementation`.
  5. Edit file, commit 4: `cleanup: remove debug logs`.
  6. Gunakan `git rebase -i HEAD~4` untuk:
     * Menggabungkan Commit 2 ke dalam Commit 1 (gunakan `fixup`).
     * Menggabungkan Commit 4 ke dalam Commit 3 (gunakan `squash`), dan ubah pesannya menjadi `feat: implement business domain logic`.
* **Kriteria Keberhasilan**: Output `git log --oneline` hanya memuat 2 commit dengan pesan yang bersih dan benar.

### Skenario 2: Emergency Recovery Menggunakan `git reflog`
* **Tujuan**: Memulihkan branch penting yang terhapus secara permanen via hard deletion.
* **Tugas**:
  1. Buat branch baru bernama `critical-payment-gateway`.
  2. Buat file `payment.py`, tambahkan fungsi pembayaran, dan commit dengan pesan `feat: integrate stripe gateway`.
  3. Pindah kembali ke branch `main`.
  4. Hapus branch tersebut secara paksa: `git branch -D critical-payment-gateway`.
  5. Buktikan bahwa branch sudah tidak ada via `git branch`.
  6. Gunakan `git reflog` untuk mengidentifikasi SHA dari commit commit pembayaran tersebut.
  7. Pulihkan branch secara sempurna beserta seluruh commit-nya.
* **Kriteria Keberhasilan**: Branch `critical-payment-gateway` kembali aktif dan file `payment.py` berada di workspace utuh tanpa kehilangan data.

### Skenario 3: Investigasi Anomali dengan Git Bisect Run Script
* **Tujuan**: Mengotomatisasi penemuan commit yang memperkenalkan kegagalan unit-test.
* **Tugas**:
  1. Buat repositori dengan file `app.sh`.
  2. Konfigurasikan skrip agar mengembalikan exit status `0` pada commit pertama.
  3. Buat 8 commit berturut-turut. Pada commit ke-5, buat skrip mengembalikan exit status `1` (kegagalan).
  4. Tulis skrip testing otomatis bernama `test-runner.sh` yang mengeksekusi `bash app.sh`.
  5. Inisiasi `git bisect` dan biarkan perintah `git bisect run bash test-runner.sh` menemukan commit ke-5 secara otomatis tanpa intervensi manual.
* **Kriteria Keberhasilan**: Terminal mencetak commit hash ke-5 sebagai "first bad commit" secara deterministik.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

### Pertanyaan Pilihan Ganda

#### 1. Jika Anda melakukan `git commit --amend` pada commit yang memiliki 3 commit turunan di depannya, apa yang terjadi pada DAG repositori Anda?
A. Hanya commit yang di-amend yang berubah, commit turunan tetap mempertahankan hash lamanya.  
B. Commit yang di-amend mendapatkan hash baru, dan 3 commit turunan otomatis terhapus dari disk.  
C. Commit yang di-amend mendapatkan hash baru, dan 3 commit turunan akan ikut ditulis ulang dengan hash baru jika di-rebase, atau menjadi *dangling* jika proses terputus.  
D. Git menolak proses amend jika commit tersebut memiliki turunan.

#### 2. Apa perbedaan fungsional paling fundamental antara perintah `squash` dan `fixup` pada interactive rebase?
A. `squash` menggabungkan perubahan ke commit sebelumnya dan menggabungkan kedua pesan commit; `fixup` membuang pesan commit saat ini dan hanya mempertahankan pesan commit sebelumnya.  
B. `fixup` menggabungkan perubahan ke commit sesudahnya; `squash` ke commit sebelumnya.  
C. `squash` bekerja pada level file; `fixup` bekerja pada level hunk.  
D. `fixup` secara otomatis membatalkan eksekusi jika terjadi merge conflict; `squash` melanjutkan secara paksa.

#### 3. Mengapa parameter `--force-with-lease` dinilai jauh lebih aman dibandingkan `--force` reguler?
A. Karena `--force-with-lease` secara otomatis membuat backup branch di remote server sebelum menimpa.  
B. Karena `--force-with-lease` menolak penulisan paksa jika remote branch telah diperbarui oleh orang lain sejak terakhir kali Anda mengambil (*fetch*) data tersebut.  
C. Karena `--force-with-lease` hanya dapat digunakan oleh pengguna dengan hak akses repository administrator.  
D. Karena `--force-with-lease` membatasi force-push hanya untuk 1 commit terakhir saja.

#### 4. Kapan sebuah commit yang tidak lagi memiliki referensi penunjuk (dangling commit) akan dihapus secara fisik dan permanen dari direktori `.git/objects`?
A. Seketika saat branch dihapus.  
B. Tepat 24 jam setelah perintah `git reset` dijalankan.  
C. Ketika `git gc` (Garbage Collector) berjalan dan commit tersebut telah melampaui masa kedaluwarsa grace period reflog (standarnya 30–90 hari).  
D. Dangling commit tidak akan pernah dihapus dari Git selamanya.

---

### Kunci Jawaban & Rasionalisasi

1. **Jawaban: C**. Karena hash commit Git bersifat kriptografis rekursif (mencakup parent hash), memodifikasi sebuah node nenek moyang secara otomatis memutus rantai integritas seluruh node keturunannya, memaksa kalkulasi ulang seluruh SHA node turunannya.
2. **Jawaban: A**. Keduanya mengkonsolidasikan diff perubahan struktural ke commit di atasnya, namun `fixup` secara instan membersihkan log pesan tanpa membuka dialog editor teks untuk pesan commit tersebut.
3. **Jawaban: B**. `--force-with-lease` bertindak sebagai *optimistic locking*. Ia mengecek apakah remote ref matching dengan remote-tracking branch lokal kita. Jika ada commit baru dari kolaborator lain yang belum kita ketahui, operasi dibatalkan.
4. **Jawaban: C**. Git mempertahankan object database dalam bentuk loose/packed objects. Pembersihan permanen murni dikelola oleh routine `git gc` dengan parameter waktu kedaluwarsa konfigurasi `gc.pruneExpire` dan `gc.reflogExpire`.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Dokumentasi Resmi Git**:
  * [git-rebase(1) Manual Page](https://git-scm.com/docs/git-rebase)
  * [git-reflog(1) Manual Page](https://git-scm.com/docs/git-reflog)
  * [git-bisect(1) Manual Page](https://git-scm.com/docs/git-bisect)
* **Buku Standar Industri**:
  * *Pro Git* (2nd Edition) oleh Scott Chacon & Ben Straub — Chapter 7: Git Tools (Rewriting History & Debugging).
* **Alat Bantu Pemulihan Tingkat Lanjut**:
  * [git-filter-repo](https://github.com/newren/git-filter-repo) (Pengganti modern resmi dari `git filter-branch` yang telah didepresiasi untuk sanitasi basis kode/penghapusan secret secara masif).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            HISTORY AUDIT CHEAT SHEET                         │
├──────────────────────────┬───────────────────────────────────────────────────┤
│ Operasi                  │ Perintah Utama                                    │
├──────────────────────────┼───────────────────────────────────────────────────┤
│ Edit N Commit Terakhir   │ git rebase -i HEAD~N                              │
│ Safe Remote Overwrite    │ git push --force-with-lease origin <branch>       │
│ Audit Riwayat Pointer    │ git reflog show --date=relative                   │
│ Pulihkan Commit Yatim    │ git checkout -b <nama-branch> <SHA-dari-reflog>   │
│ Binary Search Regresi    │ git bisect start -> bad -> good -> run <test>     │
│ Deep Blame (Clean Audit) │ git blame -w -C -C -L <start>,<end> <file>        │
│ Cek Objek Terputus       │ git fsck --lost-found                             │
└──────────────────────────┴───────────────────────────────────────────────────┘
```

Manipulasi riwayat adalah pedang bermata dua: memberikan keleluasaan merapikan riwayat pengembangan lokal hingga mencapai standar industri, namun memiliki risiko perusakan jika dieksekusi secara serampangan di shared environment. Menguasai `reflog` dan `bisect` mengubah developer dari sekadar pengguna biasa menjadi teknisi yang mampu mengendalikan dan memulihkan state sistem secara deterministik.

---

## SEKSI 17 — GLOSARIUM

* **Dangling Commit**: Objek commit di dalam database Git yang tidak dapat diakses lagi melalui referensi langsung maupun melalui penelusuran balik dari tip branch atau tag mana pun.
* **Detached HEAD**: Kondisi di mana penunjuk `HEAD` merujuk langsung ke hash sebuah commit tertentu, alih-alih merujuk ke nama sebuah branch lokal.
* **Fast-Forward**: Pemindahan penunjuk branch ke commit turunan langsung tanpa perlu membuat merge commit baru, karena tidak ada divergensi historis pada jalur percabangan.
* **Garbage Collection (`git gc`)**: Proses pembersihan internal repositori Git yang bertugas mengompresi commit objects (packing) dan membuang (*pruning*) dangling objects yang telah melewati masa retensi aman.
* **Reflog (Reference Log)**: Mekanisme logging lokal yang mencatat setiap mutasi pemindahan penunjuk referensi branch dan HEAD di dalam repositori lokal.
* **Semantic History**: Penyusunan riwayat commit yang merefleksikan perubahan fitur fungsional secara logis dan terstruktur, alih-alih catatan kronologis acak selama penulisan kode.

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Poin Kritis Pengajaran:
1. **Tekankan Batasan Mental Immutability**: Peserta sering berasumsi bahwa Git benar-benar mengedit file metadata saat di-rebase. Tekankan bahwa Git **selalu** membuat objek baru. Gambarkan diagram DAG berulang kali di papan tulis hingga konsep pergantian pointer benar-benar dipahami.
2. **Karantina Latihan Rebase**: Saat latihan interactive rebase, pastikan peserta menggunakan direktori lokal dummy yang terisolasi. Jangan izinkan mereka bereksperimen langsung di repositori proyek utama mereka sebelum lulus skenario hands-on.
3. **Praktik Nyata Bisect Run**: Demonstrasikan bagaimana `git bisect run` dapat dihubungkan ke test framework modern (seperti `pytest`, `jest`, atau skrip shell sederhana). Ini adalah salah satu fitur paling impresif yang jarang dipahami oleh developer tingkat menengah.
4. **Instalasi Git Versi Terbaru**: Pastikan peserta menggunakan Git versi $\ge 2.30$ untuk mendukung opsi mitigasi keamanan rebase dan proteksi leases secara optimal.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi**: 1.0.0
* **Tanggal Rilis**: 2026-03-31
* **Catatan Perubahan**:
  * Inisialisasi materi History Rewriting, Recovery, and Auditing.
  * Standardisasi format silabus teknis berbasis 20 Seksi GEMINI.md.
  * Penambahan skrip simulasi deterministik otomatisasi `git bisect run`.
  * Integrasi best practice keamanan push berbasis `--force-with-lease`.
* **Author / Reviewer**: Senior Technical Curriculum Architect (Core Foundations Track).

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: 
  * `[GIT-CORE-03-02]`: Advanced Branching Strategies and Conflict Resolution Architecture
* **Modul Saat Ini**: 
  * `[GIT-CORE-04-01]`: History Rewriting, Recovery, and Auditing
* **Modul Selanjutnya**: 
  * `[GIT-CORE-04-02]`: Submodules, Subtrees, and Monorepo Scalability Patterns (atau modul integrasi workflows berikutnya sesuai silabus kurikulum).