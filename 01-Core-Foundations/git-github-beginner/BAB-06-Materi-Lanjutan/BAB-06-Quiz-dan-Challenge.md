# BAB 06: Quiz, Challenge, & Knowledge Check
**Resolusi Konflik (Merge Conflict Resolution & State Recovery)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Anatomi Algoritma Three-Way Merge:**  
   Jelaskan bagaimana Git mendeteksi adanya *merge conflict* menggunakan prinsip *three-way merge*. Mengapa Git memerlukan referensi *common ancestor* (merge base), dan kondisi matematis/logis apa pada baris kode yang memicu Git berhenti serta menyerahkan resolusi kepada pengguna?

2. **Dekomposisi Penanda Konflik (*Conflict Markers*):**  
   Uraikan struktur teks default yang diinjeksikan Git ke dalam file saat terjadi konflik (`<<<<<<< HEAD`, `=======`, `>>>>>>> <branch_name>`). Apa representasi data di atas tanda pembatas `=======` dibandingkan dengan data di bawahnya pada konteks operasi `git merge` versus operasi `git rebase`?

3. **Status Index dan Siklus Hidup Resolusi:**  
   Saat konflik terjadi, file berada dalam status *unmerged*. Jelaskan secara teknis apa yang dilakukan perintah `git add <file>` terhadap file berkonflik tersebut di dalam *Staging Area* (Index), dan mengapa eksekusi `git commit` tanpa argumen `-m` secara otomatis memicu pesan commit bawaan Git (*merge commit message template*)?

4. **Konflik Konten vs. Konflik Struktural (Tree Conflicts):**  
   Bandingkan perbedaan fundamental antara *content conflict* (modifikasi baris yang sama secara konkuren) dan *structural/tree conflict* (misalnya: *modify/delete conflict* atau *rename/rename conflict*). Bagaimana mekanisme Git mencatat status *structural conflict* pada working tree?

5. **Aborsi State vs. Rollback:**  
   Jelaskan perbedaan mendasar antara membatalkan proses penggabungan yang sedang berlangsung menggunakan `git merge --abort` dengan membatalkan penggabungan yang telah selesai di-commit menggunakan `git reset --hard HEAD~1`. Apa implikasi masing-masing perintah terhadap *working tree* dan perubahan lokal yang belum di-commit sebelum operasi merge dimulai?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Inspeksi Git Index Stage (:1:, :2:, :3:):**  
   Ketika file mengalami konflik, Git menyimpan tiga versi objek *blob* file tersebut di dalam index. Jelaskan peran dari Stage 1, Stage 2, dan Stage 3. Bagaimana Anda menggunakan utilitas tingkat rendah (*plumbing command*) seperti `git ls-files -u` dan `git cat-file -p` atau `git show :<stage>:<path>` untuk menginspeksi masing-masing versi secara independen?

2. **Strategi Checkout Ekstrem (`--ours` vs `--theirs`):**  
   Pada saat terjadi konflik massal (misalnya pada 50 file konfigurasi atau asset biner), Anda memutuskan untuk memenangkan branch lokal sepenuhnya atau branch target sepenuhnya. Jelaskan mekanisme kerja `git checkout --ours -- <path>` dan `git checkout --theirs -- <path>`. Mengapa semantik `--ours` dan `--theirs` bertukar arti (*swapped context*) ketika diaplikasikan dalam konteks `git rebase` dibandingkan dengan `git merge`?

3. **Otomasi Resolusi Berulang dengan `git rerere`:**  
   Bagaimana cara kerja sub-sistem internal `git rerere` (*Reuse Recorded Resolution*)? Jelaskan bagaimana *pre-image* dan *post-image* dari suatu konflik dicatat di dalam direktori internal `.git/rr-cache`, serta risiko apa yang muncul jika resolusi yang salah (*faulty resolution*) tidak sengaja terekam oleh cache ini?

4. **Post-Merge Disaster Recovery via `git reflog`:**  
   Seorang *engineer* menyelesaikan *merge conflict* yang sangat kompleks, melakukan commit, namun kemudian menyadari bahwa ia secara tidak sengaja menghapus ratusan baris kode krusial dari branch target (terjadi regresi logika). Bagaimana tahapan forensik dan langkah pemulihan (*state recovery*) sistematis menggunakan kombinasi `git reflog`, inspeksi commit SHA, dan `git reset` untuk mengembalikan repository ke kondisi tepat sebelum merge dieksekusi tanpa kehilangan histori kerja?

5. **Diff Analysis Lanjutan untuk Resolusi Konflik:**  
   Git menyediakan konfigurasi `merge.conflictStyle` dengan opsi `diff3` dan `zdiff3`. Jelaskan apa perbedaan visual dan struktural penanda konflik standar dengan format `diff3`/`zdiff3`. Mengapa format ini sangat direkomendasikan untuk mencegah *human-error* saat menyelesaikan konflik multi-baris yang ambigu?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Merge Rusak pada Release Window Kritis
Sebuah rilis darurat (*hotfix*) dari branch `hotfix/security-patch` harus digabungkan ke branch `main`. Saat proses `git merge`, terjadi konflik pada 12 file inti, salah satunya file konfigurasi routing produksi. Seorang *engineer* junior mencoba menyelesaikan konflik tersebut, menjalankan `git add .` dan `git commit`, lalu mendorongnya (*push*) ke remote repository. 

Dua menit kemudian, pipeline CI/CD produksi gagal total karena sintaks routing rusak dan sebagian kode fitur yang belum siap rilis dari branch eksperimental yang lama ikut terbawa ke dalam `main`. Tim tidak diizinkan melakukan *force push* (`--force`) ke branch `main` karena aturan proteksi branch (*branch protection rules*) di GitHub/GitLab.

* **Pertanyaan Diagnostik & Solusi:**
  1. Bagaimana langkah sistematis untuk membalikkan (*revert*) *merge commit* tersebut pada branch `main` tanpa melanggar aturan proteksi branch (tanpa *force push*)?
  2. Apa sintaks spesifik perintah `git revert` yang wajib menyertakan flag `-m` (*parent number*), dan bagaimana cara Anda menentukan apakah harus memilih parent `1` atau parent `2`?
  3. Jika di masa depan branch `hotfix/security-patch` tersebut ingin digabungkan kembali ke `main` setelah diperbaiki, masalah apa yang akan dihadapi terkait histori commit yang telah di-*revert*, dan bagaimana cara mengatasinya?

---

### Skenario B: *Semantic Conflict* (Konflik Semantik Lolos Tanpa Marker)
Tim Backend mengintegrasikan dua branch: `feature/auth-v2` dan `feature/payment-gateway`. Git melaporkan bahwa merge berhasil secara otomatis (*Auto-merging clean, 0 conflicts detected*) dan merge commit berhasil terbentuk. Namun, saat unit test dijalankan di pipeline CI, aplikasi mengalami *crash* dengan error `TypeError: processPayment() missing 1 required positional argument: 'auth_token'`.

Investigasi menunjukkan bahwa branch Auth mengubah definisi fungsi `processPayment(amount)` menjadi `processPayment(amount, auth_token)` di file `billing.py`, sedangkan branch Payment menambahkan pemanggilan baru `processPayment(100)` di baris yang berbeda di file yang sama atau file lain. Karena baris yang dimodifikasi tidak bersinggungan secara fisik, Git menganggap penggabungan bersih secara sintaksis teks (*clean merge*).

* **Pertanyaan Diagnostik & Solusi:**
  1. Mengapa algoritma pendeteksi konflik standar Git berbasis teks (*line-based*) tidak mampu mendeteksi *semantic/logical conflict* semacam ini?
  2. Bagaimana arsitektur verifikasi lokal yang ideal yang harus dijalankan seorang *engineer* sebelum melakukan push *merge commit* ke remote untuk mendeteksi silent-failure seperti ini?
  3. Tuliskan skrip bash singkat atau rantai perintah Git yang mengotomasi verifikasi pasca-merge (misalnya: eksekusi penggabungan sementara, eksekusi test runner, dan aborsi otomatis jika test gagal).

---

### Skenario C: Konflik Penggantian Nama Direktori Skala Masif vs Refactoring
Branch `refactor/core-engine` merestrukturisasi repository dengan memindahkan direktori `/src/legacy_controllers/` ke `/src/modules/controllers/` dan mengubah ekstensi file dari `.js` ke `.ts`. Di saat yang sama, tim lain mengerjakan branch `feature/tax-calculator` selama dua minggu dan memodifikasi ribuan baris di dalam file `/src/legacy_controllers/tax.js`.

Ketika `feature/tax-calculator` digabungkan ke branch yang sudah memiliki perubahan refaktor tersebut, Git memunculkan status konflik struktural: *CONFLICT (modify/delete): /src/legacy_controllers/tax.js deleted in HEAD and modified in feature/tax-calculator*. Git gagal mendeteksi perpindahan (*rename detection threshold failure*).

* **Pertanyaan Diagnostik & Solusi:**
  1. Faktor internal apa yang menyebabkan algoritma *rename detection* Git gagal mengenali bahwa file tersebut hanya berpindah lokasi dan berganti ekstensi, bukan dihapus?
  2. Bagaimana cara mengonfigurasi atau memanggil merge command menggunakan opsi `-X rename-threshold=<n>` untuk memaksa Git mendeteksi kemiripan konten file tersebut?
  3. Jika deteksi otomatis tetap gagal karena persentase perubahan kode terlalu besar, apa langkah-langkah presisi untuk memindahkan perubahan dari file lama ke path file baru secara manual menggunakan git plumbing/patch utilities (`git diff`, `git apply`, atau `git checkout`) tanpa mengetik ulang kode?

---

## 4. Chapter Challenge

### Tantangan Praktis: Simulasi Pemulihan Insiden Merge Rusak & Resolusi State Tingkat Lanjut

#### Problem Statement
Anda berperan sebagai *Tech Lead* yang mewarisi sebuah repository lokal yang berada dalam kondisi *broken state*. Seorang developer sedang berada di tengah-tengah proses merge yang gagal dan berkonflik, mencoba melakukan reset secara serampangan, meninggalkan unmerged files, dan secara tidak sengaja menghapus file database migration yang krusial dari staging area. 

Anda ditugaskan untuk mengurai kekacauan ini: merekonstruksi kembali kondisi konflik secara terkontrol, menyelesaikan konflik baris per baris dengan integritas fungsional 100%, dan mendokumentasikan jejak pemulihan (*recovery trail*).

#### Requirements
1. **Setup Simulasi:**
   * Inisialisasi Git repository baru di direktori lokal.
   * Buat branch `main` dengan file `service.py` yang berisi implementasi server web sederhana (minimal 15 baris kode).
   * Buat branch `feature/rate-limiter` dari commit awal `main`.
   * Pada `main`, tambahkan mekanisme *logging* pada fungsi inti `service.py` dan buat commit "feat: add structured logging".
   * Pada `feature/rate-limiter`, ubah fungsi yang sama persis untuk menyuntikkan logika *rate limiting* dan buat commit "feat: add token bucket rate limiter".
2. **Eksekusi Konflik:**
   * Lakukan merge `feature/rate-limiter` ke dalam `main` sehingga Git memicu *Merge Conflict* pada `service.py`.
3. **Analisis Plumbing:**
   * Ekstrak konten Stage 1 (Base), Stage 2 (Ours), dan Stage 3 (Theirs) dari file `service.py` ke tiga file terpisah di luar tracking (`base.py`, `ours.py`, `theirs.py`) menggunakan `git show :<stage>:service.py`.
4. **Resolusi Semantik:**
   * Selesaikan konflik pada `service.py` secara manual: kode hasil akhir **harus mempertahankan kedua fitur** (baik *structured logging* dari `main` maupun *rate limiter* dari `feature/rate-limiter` harus berjalan harmonis secara sintaksis).
   * Hapus seluruh penanda konflik (*conflict markers*).
5. **Finalisasi & Pembuktian Recovery:**
   * Selesaikan merge commit dengan pesan format: `merge: reconcile structured logging with rate limiter`.
   * Simulasikan skenario kecelakaan: Jalankan `git reset --hard HEAD~1` (secara sengaja menghapus merge commit yang baru saja dibuat).
   * Pulihkan kembali merge commit yang hilang tersebut murni menggunakan `git reflog` dan `git reset`.

#### Constraints
* Dilarang menggunakan GUI tool atau Git extension bawaan editor (seperti VS Code Merge Editor). Seluruh operasi analisis, ekstraksi stage, dan resolusi harus diverifikasi via Git CLI dan teks editor berbasis terminal (Vim/Nano) atau command-line redirection.
* Repository harus memiliki commit tree yang bersih tanpa meninggalkan file temporer untracked.

#### Expected Output
1. Log `git log --graph --oneline -n 5` yang menunjukkan percabangan telah menyatu kembali (*merge commit* berhasil dipulihkan).
2. Hasil eksekusi `python service.py` (atau `cat service.py`) yang membuktikan bahwa blok kode *logging* dan *rate limiting* berada pada tempatnya tanpa syntax error.
3. Catatan baris perintah (*command history*) dari `git reflog` yang menunjukkan entri recovery merge commit tersebut.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Logika algoritma *Three-Way Merge* dan mengapa *common ancestor* menentukan titik divergensi perubahan.
- [ ] Struktur penanda konflik standar (`<<<<<<<`, `=======`, `>>>>>>>`) dan format lanjutan `diff3` / `zdiff3` yang menyertakan base ancestor.
- [ ] Konsep Git Index Stages: Stage 0 (normal), Stage 1 (merge-base), Stage 2 (target/HEAD), Stage 3 (incoming/MERGE_HEAD).
- [ ] Perbedaan fungsional serta risiko antara `git merge --abort`, `git reset --merge`, dan `git reset --hard`.
- [ ] Mengapa *clean merge* secara tekstual belum tentu menjamin *clean merge* secara semantik/fungsional (*semantic conflicts*).
- [ ] Cara kerja internal `git rerere` dalam mengotomasi resolusi konflik berulang pada cabang berumur panjang (*long-lived branches*).
- [ ] Implikasi membatalkan *merge commit* menggunakan `git revert -m 1` terhadap integrasi branch di masa mendatang.

### Saya tidak perlu menghafal:
- [ ] Format biner internal dari objek blob tree di dalam direktori `.git/objects/`.
- [ ] Seluruh algoritma rekursif internal (`ort`, `recursive`, `octopus`, `resolve`) hingga ke tingkat baris implementasi C pada source code Git engine.
- [ ] Nilai hash SHA-1/SHA-256 spesifik dari commit; cukup memahami cara mengekstrak dan memetakannya via `git rev-parse` atau `git log`.

### Saya harus bisa melakukan:
- [ ] Membaca, menganalisis, dan menyelesaikan *conflict markers* kompleks multi-blok secara manual tanpa merusak logika aplikasi.
- [ ] Menggunakan `git ls-files -u` untuk memeriksa status file yang berkonflik di staging area.
- [ ] Mengisolasi versi file dari Stage 1, 2, dan 3 menggunakan sintaks `git show :<stage>:<path>`.
- [ ] Melakukan resolusi cepat satu sisi menggunakan `git checkout --ours -- <path>` atau `git checkout --theirs -- <path>` jika diperlukan.
- [ ] Membatalkan proses penggabungan yang sedang berjalan secara aman tanpa merusak perubahan working tree yang belum ter-stage (`git merge --abort`).
- [ ] Memulihkan commit penggabungan yang terhapus atau salah reset menggunakan `git reflog` dan `git reset --hard <SHA>`.
- [ ] Melakukan `git revert` pada sebuah merge commit dengan mendefinisikan flag parent `-m` yang tepat berdasarkan audit branch tree.