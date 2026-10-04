# BAB 04: Quiz, Challenge, & Knowledge Check
**Percabangan Terisolasi (Branching Strategies & Mechanics)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi Fisik Branch di Level Storage
Secara teknis di dalam direktori `.git/`, apakah sebuah *branch* merupakan salinan (*snapshot copy*) dari seluruh direktori proyek seperti pada VCS terpusat generasi lama (misal: SVN copy), atau entitas lain? Jelaskan representasi data branch pada file `.git/refs/heads/<branch-name>` beserta ukuran payload penyimpanannya!

### Soal 1.2: Perilaku Pointer `HEAD` dan Resolusi Simbolik
Jelaskan perbedaan mendasar antara kondisi `HEAD` yang menunjuk ke sebuah *branch reference* (simbolik) versus kondisi *Detached HEAD*. Apa implikasi struktural terhadap commit baru yang dibuat saat sistem berada dalam status *Detached HEAD*?

### Soal 1.3: Mekanisme Transisi `git branch` vs `git switch`
Mengapa Git memperkenalkan perintah `git switch` dan `git restore` pada Git versi 2.23 untuk menggantikan dominasi `git checkout`? Dari perspektif desain antarmuka CLI (*separation of concerns*), sebutkan ambiguitas operasional apa yang dieliminasi dari `git checkout`!

### Soal 1.4: Proteksi Integritas: Flag `-d` vs `-D`
Ketika mengeksekusi `git branch -d <feature-branch>`, Git terkadang menolak operasi tersebut dengan pesan galat: `error: The branch '<feature-branch>' is not fully merged`. Secara matematis pada struktur *Directed Acyclic Graph* (DAG), bagaimana Git memvalidasi apakah sebuah cabang "sudah di-merge" atau belum sebelum mengizinkan penghapusan aman? Mengapa flag `-D` dapat melewati proteksi ini?

### Soal 1.5: Prasyarat Matematis Fast-Forward Merge
Apa kondisi topologi DAG yang mutlak dipenuhi agar sebuah operasi penggabungan (*merge*) dapat dieksekusi sebagai *Fast-Forward*? Mengapa operasi *Fast-Forward* tidak menghasilkan commit merge baru (*non-merge commit*)?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Atomisitas Update Ref via `git update-ref`
Saat Anda melakukan commit baru pada branch `feature/auth`, Git memperbarui pointer branch tersebut secara atomik. Bagaimana Git memanipulasi file ref di `.git/refs/heads/feature/auth` secara aman dari *race condition* (misalnya menggunakan mekanisme lock file `.git/refs/heads/feature/auth.lock`)?

### Soal 2.2: Isolasi State Direktori Kerja saat Branch Switching
Anda berada di branch `feature-A` dengan modifikasi file yang belum di-commit (*dirty working tree*). Anda mengeksekusi `git switch feature-B`. Dalam kondisi apa Git akan **mengizinkan** perpindahan tersebut tanpa kehilangan data, dan dalam kondisi apa Git akan **memblokir** operasi tersebut dengan galat `error: Your local changes to the following files would be overwritten by checkout`?

### Soal 2.3: Tracking Ref Spec dan Pemetaan Upstream
Jelaskan konfigurasi yang diinjeksikan Git ke dalam file `.git/config` saat Anda menjalankan perintah:
```bash
git push -u origin feature/payment
```
Uraikan korelasi antara entri konfigurasi `branch.feature/payment.remote` dan `branch.feature/payment.merge` terhadap pemetaan ref lokal `refs/remotes/origin/feature/payment`!

### Soal 2.4: Diagnostik Ref 'Stale' dan Garbage Collection
Sebuah branch fitur telah dihapus dari *remote repository* (GitHub) via Pull Request merge. Namun, saat engineer menjalankan `git branch -a` di mesin lokal, branch `remotes/origin/feature/payroll` masih muncul. Mengapa Git lokal mempertahankan ref tersebut, dan apa perbedaan mekanistik antara menjalankan `git fetch --prune` vs `git remote prune origin`?

### Soal 2.5: Mitigasi Bencana: Resurrecting Orphaned Commits
Seorang developer secara tidak sengaja mengeksekusi `git branch -D feature/core-engine` yang berisi 15 commit baru dan belum pernah di-push ke remote. Jelaskan langkah forensik menggunakan `git reflog` dan plumbing command `git branch <new-branch> <target-hash>` untuk memulihkan seluruh riwayat commit tersebut secara utuh sebelum siklus *garbage collection* (`git gc`) dijalankan!

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Krisis Hotfix pada Produksi (Release Branch Isolation)
* **Kasus:** Sistem produksi berjalan pada rilis `v1.12.0` (commit `hash-A`). Branch `main` saat ini telah tercemar oleh 40 commit baru untuk rilis `v1.13.0` yang belum stabil dan belum melalui tahap regresi QA. Ditemukan celah keamanan *zero-day* di produksi yang menuntut patch darurat dalam waktu 45 menit.
* **Pertanyaan Diagnostik & Solusi:**
  1. Rancang urutan perintah Git presisi tinggi untuk membuat branch perbaikan yang diisolasi *langsung* dari commit penanda rilis `v1.12.0` tanpa membawa polusi commit `v1.13.0`!
  2. Bagaimana strategi Anda merilis hotfix tersebut (misal menjadi `v1.12.1`) sekaligus memastikan *patch* keamanan tersebut diintegrasikan kembali (*backported*) ke branch `main` tanpa menyebabkan konflik regresif pada fitur `v1.13.0`?

### Skenario B: Divergensi Massal Akibat Destructive Push pada Shared Branch
* **Kasus:** Dua software engineer (Dev A dan Dev B) berkolaborasi pada remote branch `feature/data-pipeline`. Dev A melakukan `rebase` lokal terhadap branch `main`, lalu mengeksekusi `git push --force` ke remote repository. Ketika Dev B (yang memiliki commit baru di atas histori lama sebelum rebase) menjalankan `git pull`, terminal Dev B dipenuhi oleh konflik penggabungan puluhan commit identik dengan hash berbeda (*duplicated commit divergence*).
* **Pertanyaan Diagnostik & Solusi:**
  1. Mengapa destruksi histori ini bisa terjadi pada mesin Dev B? Jelaskan apa yang terjadi pada DAG lokal Dev B!
  2. Instruksi teknis apa yang harus dieksekusi Dev B untuk menyelaraskan histori lokalnya dengan remote branch hasil rebase Dev A tanpa kehilangan pekerjaan lokal Dev B yang belum ter-push?

### Skenario C: Evaluasi Arsitektur Percabangan Enterprise (Trunk-Based vs GitFlow)
* **Kasus:** Sebuah organisasi rekayasa perangkat lunak berskala 120 engineer menghadapi bottleneck delivery: siklus rilis memakan waktu 2 minggu akibat proses integrasi yang rumit antar-branch (*merge hell* pada release branch GitFlow). Manajemen menuntut percepatan deploy ke staging/produksi hingga beberapa kali sehari menggunakan CI/CD pipeline modern.
* **Pertanyaan Diagnostik & Solusi:**
  1. Analisis akar kelemahan model branching GitFlow tradisional dalam skenario *high-velocity continuous delivery*!
  2. Berikan justifikasi teknis migrasi menuju *Short-Lived Feature Branches / Trunk-Based Development* (TBD)! Risiko operasional apa yang muncul pada sistem produksi (misal: kode fitur setengah jadi ter-deploy), dan mekanisme software architecture apa (misal: *feature flags/toggles*) yang wajib disiapkan untuk memitigasi risiko tersebut?

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekonstruksi Forensik DAG dan Isolasi Rilis Produksi

#### Deskripsi Masalah
Sebuah insiden deployment terjadi di mana branch `main` secara tidak sengaja terhapus di repositori lokal seorang developer junior setelah proses *detached HEAD checkout*. Selain itu, branch `feature/identity` yang krusial telah dihapus secara paksa (`-D`), menyisakan commit-commit yatim piatu (*orphaned commits*) di object database lokal. Anda ditugaskan sebagai Lead Engineer untuk merekonstruksi topologi Git kembali ke kondisi stabil, membuat branch hotfix terisolasi, dan memastikan integritas DAG terjaga.

#### Requirements
1. Inisialisasi repositori Git lokal baru bernama `enterprise-recovery`.
2. Buat simulasi minimal 3 commit di branch awal (`main`), beri tag `v1.0.0` pada commit kedua.
3. Buat branch baru bernama `feature/identity`, tambahkan 2 commit di dalamnya.
4. Simulasikan insiden:
   - Pindah ke commit `v1.0.0` sehingga terjadi kondisi *Detached HEAD*.
   - Hapus paksa branch `feature/identity` (`git branch -D feature/identity`).
   - Buat 1 commit perbaikan darurat langsung di status *Detached HEAD*.
5. Eksekusi proses penyelamatan forensik:
   - Temukan kembali hash commit ujung dari `feature/identity` yang terhapus menggunakan reflog inspect.
   - Pulihkan branch `feature/identity` ke commit aslinya.
   - Ambil commit perbaikan darurat yang dibuat di status detached HEAD dan resmikan menjadi branch `hotfix/v1.0.1`.
   - Lakukan merge `hotfix/v1.0.1` ke branch rilis baru bernama `release/prod` tanpa menggunakan *Fast-Forward* merge (`--no-ff`) untuk mempertahankan jejak audit histori.

#### Constraints
- Dilarang menggunakan tool GUI (hanya boleh menggunakan Git CLI murni).
- Semua manipulasi identifikasi objek wajib dibuktikan dengan SHA-1 hash (atau *short-hash*) menggunakan perintah plumbing atau log grafikal tingkat lanjut.
- Tidak boleh ada data commit yang hilang (*zero unreferenced commits* di akhir operasi).

#### Expected Output
Laporan terminal yang menunjukkan:
1. Output eksekusi perintah `git reflog` yang memperlihatkan titik pemulihan.
2. Visualisasi DAG final menggunakan perintah:
   ```bash
   git log --graph --oneline --all --decorate
   ```
   Visualisasi wajib menampilkan percabangan yang jelas antara `hotfix/v1.0.1`, `feature/identity`, dan basis tag `v1.0.0`.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Bahwa branch di Git secara fisik hanyalah sebuah pointer (file teks 41-byte) yang berisi hash SHA-1 commit terakhir, bukan direktori fisik yang menyalin file proyek.
- [ ] Definisi dan peran pointer `HEAD` sebagai referensi simbolik aktif untuk commit berikutnya.
- [ ] Kondisi *Detached HEAD*, implikasi siklus hidup objeknya, dan risiko *garbage collection* terhadap commit tanpa referensi.
- [ ] Perbedaan fungsional antara Fast-Forward merge (hanya menggeser pointer) vs 3-Way Merge (memerlukan merge commit & common ancestor).
- [ ] Peran dan struktur file `.git/refs/heads/` serta `.git/refs/remotes/` dalam topologi sinkronisasi lokal-remote.
- [ ] Keterbatasan struktural GitFlow pada ekosistem Continuous Integration / Continuous Deployment (CI/CD).

### Saya tidak perlu menghafal:
- [ ] Seluruh parameter/flags obscure dari legacy command `git checkout` (prioritaskan pemahaman tajam pada `git switch` dan `git restore`).
- [ ] Format biner internal dari *packfiles* (`.pack` dan `.idx`) tempat Git memadatkan commit lama saat garbage collection.
- [ ] Nilai 40-karakter SHA-1 hash secara manual (cukup pahami bahwa 7-8 karakter awal sudah cukup unik untuk me-resolve objek).

### Saya harus bisa melakukan:
- [ ] Menggunakan `git switch -c <name>` dan `git switch <name>` dengan tepat untuk navigasi branch.
- [ ] Mendiagnosis dan menyelesaikan kegagalan branch switching akibat *dirty working directory* menggunakan teknik pembatalan atau isolasi state.
- [ ] Menemukan commit yang hilang akibat branch deletion yang tidak disengaja menggunakan `git reflog`.
- [ ] Memulihkan branch yang terhapus langsung dari *orphaned commit hash*.
- [ ] Melakukan isolasi hotfix dari tag spesifik di masa lalu tanpa mencemari branch development aktif.
- [ ] Mengonfigurasi dan membersihkan remote tracking reference yang usang menggunakan `git fetch --prune`.
- [ ] Memvisualisasikan topologi Directed Acyclic Graph (DAG) secara mandiri di command line menggunakan opsi pemformatan `git log --graph --oneline --all`.