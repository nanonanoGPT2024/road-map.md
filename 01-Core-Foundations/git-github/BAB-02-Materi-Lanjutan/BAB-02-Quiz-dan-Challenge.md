# BAB 02: Quiz, Challenge, & Knowledge Check
**Local Workflow & State Traversal**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Trinitas State Git dan Struktur `.git/index`
Jelaskan secara arsitektural interaksi antara *Working Directory*, *Staging Area* (Index), dan *Commit History* (Object Database). Mengapa *Staging Area* tidak diimplementasikan sekadar sebagai daftar referensi pointer sederhana, melainkan sebagai file biner terstruktur (`.git/index`) yang menyimpan *stat cache* lengkap beserta SHA-1/SHA-256 dari blob objek?

### Soal 1.2: Anatomi Mutasi Pointer pada Detached HEAD
Ketika seorang engineer mengeksekusi `git checkout <commit-hash>` atau `git switch --detach <commit-hash>`, sistem memasuki kondisi *Detached HEAD*. 
1. Bedah mutasi internal yang terjadi pada file `.git/HEAD` dibandingkan dengan saat berada pada branch aktif.
2. Apa konsekuensi siklus hidup (*lifecycle*) objek commit baru yang dibuat dalam kondisi *Detached HEAD* jika engineer beralih kembali ke branch `main` tanpa membuat pointer referensi baru? Hubungkan penjelasan Anda dengan mekanisme *Garbage Collection* (`git gc`) dan *pruning*.

### Soal 1.3: Topologi Komparasi Delta: `git diff` Matrix
Jelaskan secara presisi pohon/state mana yang dibandingkan oleh Git ketika mengeksekusi tiga variasi perintah berikut:
1. `git diff` (tanpa argumen tambahan)
2. `git diff --cached` (atau `git diff --staged`)
3. `git diff HEAD`

Gambarkan matriks transisi state yang merefleksikan file yang dimodifikasi di *Working Directory* dan file yang telah dimasukkan ke *Staging Area*.

### Soal 1.4: Imutabilitas Objek dan `git commit --amend`
Secara visual dan konseptual, `git commit --amend` terlihat seperti memodifikasi commit terakhir secara *in-place*. 
1. Buktikan secara teknis mengapa pernyataan "memodifikasi commit secara *in-place*" tersebut keliru berdasarkan prinsip *content-addressable storage*.
2. Jelaskan urutan pembentukan tree object baru, parent assignment, dan rekalkulasi cryptographic hash yang terjadi di balik layar saat flag `--amend` dieksekusi.

### Soal 1.5: Dekonstruksi Penghapusan: `git rm` vs `git rm --cached` vs `rm`
Analisis dampak dari ketiga perintah berikut terhadap tiga area (*Working Tree*, *Index*, dan *Object Database*):
1. Menghapus file menggunakan perintah OS: `rm app.log`
2. Menghapus file menggunakan Git: `git rm app.log`
3. Menghapus file menggunakan Git: `git rm --cached app.log`

Kapan seorang engineer wajib menggunakan variasi `--cached` dalam skenario pengelolaan konfigurasi lingkungan produksi?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Triase Mekanisme Internal `git reset`
Perintah `git reset` memanipulasi riwayat dengan memindahkan pointer referensi branch. Analisis perubahan internal pada (a) `HEAD ref`, (b) `.git/index`, dan (c) *Working Directory* untuk masing-masing flag berikut:
1. `git reset --soft <target-commit>`
2. `git reset --mixed <target-commit>` (default)
3. `git reset --hard <target-commit>`

Jelaskan skenario penggunaan spesifik di mana `--soft` merupakan pilihan mutlak dibandingkan `--mixed` untuk mempertahankan integritas penyusunan commit baru.

### Soal 2.2: Resolusi Ambiguitas: `git checkout` vs `git switch` & `git restore`
Pada rilis Git v2.23, antarmuka pengguna dipecah dengan memperkenalkan `git switch` dan `git restore` guna mengeliminasi ambiguitas fungsional `git checkout`. 
1. Identifikasi risiko operasional yang timbul dari overloaded responsibilities pada `git checkout` (khususnya percampuran antara operasi pointer commit dan manipulasi blob pada working tree).
2. Bagaimana `git restore --source=HEAD~1 --staged --worktree <file>` bekerja secara atomik melintasi boundary Index dan Working Directory?

### Soal 2.3: Mekanisme Stat Cache dan Dirty Checking Engine
Untuk repositori enterprise berskala besar (monorepo dengan ratusan ribu file), mengeksekusi hashing SHA ulang terhadap seluruh file setiap kali `git status` dipanggil akan melumpuhkan performa I/O disk. 
Jelaskan bagaimana Git mengoptimalkan proses *dirty checking* menggunakan metadata sistem operasi (`lstat()`: `mtime`, `ctime`, `file size`, `inode`, `device ID`) yang tersimpan di dalam struktur file biner `.git/index` sebelum memutuskan untuk membaca konten file dan merehash blob baru.

### Soal 2.4: Dekonstruksi Arsitektur Multiroot pada `git stash`
Ketika Anda menjalankan perintah `git stash push -m "WIP"`, Git tidak sekadar memindahkan diff ke direktori temporer, melainkan membuat *commit object* reguler di dalam Object Database.
1. Sebutkan dan jelaskan peran dari commit-commit yang dibentuk oleh Git saat melakukan stash (analisis struktur commit 2-parent vs 3-parent jika menyertakan flag `--include-untracked`).
2. Di mana referensi pointer commit stash disimpan, dan bagaimana Git mengelola riwayat multi-stash secara internal?

### Soal 2.5: Syntax Traversal Graph: Disparitas `~` (Tilde) dan `^` (Caret)
Diberikan sebuah DAG (*Directed Acyclic Graph*) kompleks dengan serangkaian merge commit:
```text
      G---H---I (feature-2)
     /
D---E---F (feature-1)
 \ /
  B---C---J (main)
   \     /
    K---L
```
1. Jelaskan perbedaan matematis murni antara operator `~n` (*first-parent ancestral line*) dan `^n` (*n-th parent selection* pada merge point).
2. Tuliskan ekspresi navigasi relatif traversal yang valid dari commit `J` untuk menunjuk commit `D` tanpa menggunakan hash commit!

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Production Hotfix Loss Akibat `git reset --hard` yang Ceroboh
* **Konteks:** Seorang Technical Lead secara lokal menggabungkan hotfix kritis untuk menangani insiden data breach pada branch `release/v2.1.0`. Karena terjadi anomali lokal, ia bermaksud membatalkan 1 commit eksperimental terakhir dengan mengeksekusi `git reset --hard HEAD~1`. Namun, ia tidak menyadari bahwa ia berada di posisi HEAD yang salah, sehingga perintah tersebut mengeksekusi reset melompati 4 commit hotfix kritis yang belum di-push ke remote origin. Status working directory kini benar-benar bersih (*clean*), dan branch pointer kembali ke posisi lama.
* **Pertanyaan Diagnostik:**
  1. Bagaimana Anda membuktikan bahwa objek commit hotfix tersebut belum benar-benar hilang dari filesystem server/lokal secara permanen?
  2. Rancang prosedur deterministik langkah demi langkah (menggunakan plumbing/porcelain commands seperti `git reflog`, `git fsck`, atau inspecting `.git/logs/`) untuk merekonstruksi branch `release/v2.1.0` tepat pada commit terakhir sebelum insiden terjadi tanpa menyebabkan *dirty working tree*!

### Skenario B: Partial Staging Saturation dan Collision Pasca Interrupted Rebase
* **Konteks:** Seorang engineer senior sedang memecah commit besar (*atomic commit crafting*) menggunakan `git add -p` (patch mode) pada file arsitektur inti `DatabaseEngine.kt` yang berukuran 5.000 baris kode. Setelah menyeleksi 12 hunks ke dalam Staging Area dan menyisakan 8 hunks di Working Directory, sebuah interupsi mendadak memaksanya beralih branch untuk investigasi P1. Engineer tersebut mengeksekusi `git stash push --keep-index`, lalu beralih branch. Sekembalinya dari investigasi, ia mengeksekusi `git stash pop`, yang menghasilkan *merge conflict* parah secara lokal antara Index yang di-retain dan stash state, menyebabkan Staging Area berstatus kotor (*dirty*) dan unmerged.
* **Pertanyaan Diagnostik:**
  1. Mengapa kombinasi `--keep-index` dan `git stash pop` memicu *conflict collision* pada file yang sama? Jelaskan apa yang terjadi pada Index state saat popping dilakukan.
  2. Bagaimana metodologi terbaik untuk mengembalikan state kerja ke kondisi persis sebelum `git stash push --keep-index` dijalankan (12 hunks di stage, 8 hunks uncommitted di working tree) tanpa kehilangan perubahan manual pada hunks yang belum ter-stage?

### Skenario C: Index Bloat dan Memory Overhead Ekstrem Akibat File Biner Masif
* **Konteks:** Seorang developer junior secara tidak sengaja mengeksekusi `git add .` di root proyek monorepo. Perintah ini mengabaikan file `.gitignore` yang salah konfigurasi, menyebabkan tumpukan artefak build lokal (direktori `build/`, file `.tar.gz`, memory dump, dan dataset pengujian) berukuran total 45GB dengan 300.000 file baru masuk ke Staging Area (`.git/index`). Developer tersebut belum menjalankan `git commit`. Namun, ketika mencoba membatalkan staging via `git restore --staged .` atau `git reset`, terminal mengalami *hanging* (OOM Killer mematikan proses Git karena memory exhaustion).
* **Pertanyaan Diagnostik:**
  1. Secara arsitektur, apa yang terjadi pada direktori `.git/objects/` dan file `.git/index` saat `git add .` dieksekusi pada 300.000 file tersebut?
  2. Rancang strategi pemulihan berisiko rendah (*low-risk recovery*) untuk mengosongkan/mengembalikan Staging Area ke state `HEAD` secara instan tanpa membebani memori sistem, dan jelaskan cara membersihkan dangling unreferenced loose blob objects yang terlanjur ter-generate di `.git/objects/` guna memulihkan kapasitas disk server.

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekonstruksi Forensik DAG dan Bedah State Index Manual
* **Problem Statement:**
Sebuah pipeline otomatisasi CI/CD lokal mengalami malfungsi di tengah proses eksekusi script bash. Malfungsi ini memicu eksekusi serangkaian perintah destruktif yang menghapus branch referensi lokal, membatalkan staging, dan meninggalkan repositori dalam kondisi *untracked detached HEAD* dengan sebagian objek tercecer di dalam Object Database. Anda ditugaskan sebagai Principal Engineer untuk melakukan *forensic recovery* dan rekonstruksi DAG tanpa bergantung pada GUI tools.

* **Requirements:**
1. Inisialisasi repositori simulasi dan reproduksi kerusakan:
   - Buat repositori baru, lakukan 3 commit linier berturut-turut pada file `kernel.c`.
   - Buat branch baru `feature/allocator`, tambahkan 2 commit yang memodifikasi `kernel.c` dan menambahkan `allocator.h`.
   - Lakukan modifikasi baru pada `allocator.h`, tambahkan ke staging (`git add`), lalu tambahkan modifikasi lain yang belum di-stage (*partially staged*).
   - Simulasikan bencana: Eksekusi `git reset --hard HEAD~2` saat berada di branch `feature/allocator`, lalu hapus referensi branch tersebut: `git update-ref -d refs/heads/feature/allocator`.
   - Bersihkan log reflog branch dengan menghapus file `.git/logs/refs/heads/feature/allocator` secara manual untuk mensimulasikan ketiadaan branch reflog langsung.
2. Lakukan audit forensik:
   - Gunakan `git fsck --lost-found` atau traversal parsing pada `.git/logs/HEAD` untuk melacak SHA-1 commit target yang terisolasi (*dangling commit*).
   - Identifikasi commit ID yang tepat dari `feature/allocator` sebelum terjadinya hard reset.
3. Rekonstruksi State:
   - Pulihkan pointer branch `feature/allocator` tepat pada dangling commit tersebut.
   - Buat commit baru menggunakan teknik *patch staging* (`git add -p`) untuk membedah perubahan spesifik per-hunk secara granular.
   - Ekstrak riwayat commit dalam format raw tree menggunakan perintah plumbing `git cat-file -p` untuk membuktikan bahwa tree pointer merefleksikan hierarki direktori yang valid.

* **Constraints:**
- Dilarang menggunakan Git GUI client atau ekstensi IDE pihak ketiga (VSCode, GitKraken, dll).
- Dilarang menduplikasi working directory atau melakukan clone ulang dari remote (seluruh operasi pemulihan wajib terjadi secara lokal di level filesystem repository internal).
- Gunakan plumbing commands (`git cat-file`, `git ls-tree`, `git update-ref`) minimal pada satu tahap pembuktian integritas objek.

* **Expected Output:**
- Log terminal yang mendokumentasikan eksekusi perintah pembuktian `git fsck` / `git reflog`.
- Log `git log --graph --oneline --all` yang menampilkan branch `feature/allocator` telah kembali seimbang dan terintegrasi pada riwayat DAG yang benar.
- Output `git cat-file -p <tree-hash>` yang memvalidasi bahwa snapshot tree mengarah ke blob `kernel.c` dan `allocator.h` yang sesuai.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur dan perbedaan fundamental antara Working Directory, Index/Staging Area (`.git/index`), dan Object Database (`.git/objects`).
- [ ] Siklus hidup blob, tree, commit, dan tag objects di dalam Content-Addressable Storage Git.
- [ ] Perilaku spesifik dan implikasi struktural dari `git reset --soft`, `--mixed`, dan `--hard`.
- [ ] Mengapa Git commit bersifat immutable dan implikasi pembuatan hash baru saat menjalankan `git commit --amend`.
- [ ] Kondisi *Detached HEAD* di level filesystem (apa yang tertulis di `.git/HEAD`) dan risiko garbage collection.
- [ ] Perbedaan traversal tree antara `git diff`, `git diff --staged`, dan `git diff HEAD`.
- [ ] Mekanisme internal `git stash` sebagai compound commit yang merangkai state index dan working tree.
- [ ] Logika traversal graf riwayat menggunakan notasi relative commit: operator Tilde (`~`) vs Caret (`^`).

### Saya tidak perlu menghafal:
- [ ] Format biner internal byte-per-byte header file `.git/index` (kecuali memahami bahwa ia menyimpan cache metadata file sistem seperti `mtime`, `ctime`, dan file mode).
- [ ] Struktur bitwise flags internal dari SHA hashing header string Git (`blob <size>\0`).
- [ ] Seluruh sub-flags dan variasi argumen edge-case dari command `git restore` atau `git checkout`.
- [ ] Format serialisasi internal storage format dari packfiles (`.pack`) dan index pack (`.idx`) secara detail pada level ini.

### Saya harus bisa melakukan:
- [ ] Memeriksa dan membedah isi objek Git di low-level menggunakan plumbing command: `git cat-file -t <hash>` dan `git cat-file -p <hash>`.
- [ ] Melakukan *atomic commit crafting* dengan menyeleksi hunks secara parsial menggunakan `git add -p` atau `git restore -p`.
- [ ] Menggunakan `git reflog` untuk melacak dan memulihkan commit yang terputus (*orphaned*) akibat kesalahan eksekusi pointer reset atau branch deletion.
- [ ] Menavigasi DAG Git secara presisi menggunakan sintaks traversal (`HEAD~2`, `HEAD^`, `HEAD^^2`).
- [ ] Mengoreksi kesalahan staging tanpa memengaruhi modifikasi pada working directory menggunakan `git restore --staged <file>` atau `git reset HEAD <file>`.
- [ ] Menemukan dangling objects yang tidak lagi terikat pada ref apapun menggunakan `git fsck --lost-found`.