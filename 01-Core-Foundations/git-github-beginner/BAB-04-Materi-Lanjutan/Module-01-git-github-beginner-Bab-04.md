## SEKSI 01 — IDENTITAS MODUL

*   **ID Modul:** `CORE-GIT-04-01`
*   **Judul Modul:** Percabangan Terisolasi (*Isolated Branching Architecture*)
*   **Kategori:** `01-Core-Foundations`
*   **Tingkat Kesulitan:** Pemula Menengah (*Beginner to Intermediate*)
*   **Prasyarat:** `CORE-GIT-03-01` (Siklus Hidup Commit & Staging Area), pemahaman dasar struktur direktori UNIX/CLI.
*   **Estimasi Waktu Penyelesaian:** 90 Menit
*   **Target Stack/Tools:** Git CLI (versi minimum 2.23+ untuk sintaks `git switch`), Terminal Bash/Zsh.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Mendekonstruksi Model Internal Branch:** Menjelaskan secara presisi representasi fisik *branch* di dalam direktori `.git/refs/heads/` sebagai *pointer* 41-byte (40 karakter hash SHA-1 + *newline*), bukan salinan fisik direktori (*copy-on-write/full snapshot duplication*).
2.  **Memanipulasi dan Melacak Posisi `HEAD`:** Mengidentifikasi relasi antara file `.git/HEAD`, *symbolic reference*, dan *commit-graph* selama operasi manipulasi *branch*.
3.  **Mengoperasikan Perintah Isolasi Modern:** Menggunakan perintah modern `git switch` dan `git branch` secara tepat untuk membuat, berpindah, dan menghapus alur kerja tanpa risiko tercampurnya status *working tree*.
4.  **Mendiagnosis Kondisi Transisi *Working Tree*:** Memprediksi perilaku perpindahan *branch* ketika *working directory* berstatus *dirty* (memiliki modifikasi yang belum di-*commit*) serta mencegah penolakan transisi (*aborted switch*).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
[ Directed Acyclic Graph (DAG) ]
               │
               ▼
     [ Commit Objects ] (Snapshot + Metadata)
        ▲           ▲
        │           │
[ Pointer: main ]  [ Pointer: feature-auth ] ◄── (Refs: .git/refs/heads/*)
                           ▲
                           │
                    [ Pointer: HEAD ] ◄───────── (State: .git/HEAD)
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
[ Attached HEAD State ]        [ Detached HEAD State ]
(HEAD -> Ref -> Commit)         (HEAD -> Commit langsung)
```

Alur logis modul:
1. Dari *commit history* linier menuju percabangan non-linier.
2. Mekanisme *lightweight pointer* vs sistem VCS lama (SVN/CVS).
3. Dinamika *reference pointer* melalui file fisik sistem Git.
4. Isolasi perubahan pada ruang kerja (*working directory*).

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Pada sistem kendali versi terpusat legacy (seperti Subversion/SVN), membuat *branch* berarti menyalin seluruh struktur direktori proyek ke sub-direktori baru (`/branches/my-feature`). Operasi ini memakan ruang disk yang signifikan, membutuhkan koneksi jaringan, dan berjalan lambat secara eksponensial seiring bertambahnya ukuran basis kode.

Git merevolusi paradigma ini dengan memperlakukan *branch* sebagai **pointer referensi yang sangat ringan (lightweight reference pointer)**. Pembuatan sebuah *branch* di Git hanya membutuhkan penulisan 41 byte data ke dalam disk lokal (hampir instan, ~0.001 detik), tanpa memedulikan apakah ukuran repositori Anda sebesar 10 MB atau 50 GB.

Bagi seorang perekayasa perangkat lunak:
*   **Isolasi Konteks yang Bersih:** Memungkinkan eksperimen, perbaikan *bug* mendesak (*hotfix*), atau pengembangan fitur baru tanpa merusak stabilitas kode utama yang siap rilis (*production-ready*).
*   **Manajemen Konteks Kognitif:** Memungkinkan perpindahan cepat antar tugas secara aman, asalkan aturan transisi pohon kerja (*working tree transition*) dipatuhi.
*   **Efisiensi Sumber Daya:** Menghemat kapasitas memori dan *storage* secara drastis melalui pemanfaatan struktur *Directed Acyclic Graph* (DAG).

---

## SEKSI 05 — APA ITU (WHAT)

### Definisi Formal
Sebuah **Git Branch** pada level abstraksi tertinggi adalah alur pengembangan independen. Pada level implementasi internal, *branch* hanyalah sebuah **file teks sederhana berukuran 41 byte** yang berisi hash 40 karakter dari commit terakhir dalam alur tersebut, ditambah satu byte karakter *newline* (`\n`).

### Karakteristik Branch di Git
*   **Penyimpanan Internal:** Terletak pada direktori `.git/refs/heads/<nama-branch>`.
*   **Dinamika:** Setiap kali commit baru dibuat pada branch aktif, Git secara otomatis memperbarui nilai hash di dalam file referensi tersebut ke hash commit yang baru.
*   **HEAD:** File khusus `.git/HEAD` yang mendefinisikan konteks aktif saat ini. Pada kondisi normal (*attached HEAD*), file ini merujuk ke nama branch, bukan langsung ke hash commit:
    ```text
    ref: refs/heads/main
    ```

### Pemisahan Tanggung Jawab: `git switch` vs `git checkout`
Sebelum rilis Git 2.23, perintah `git checkout` memikul dua tanggung jawab ortogonal yang membingungkan:
1. Memanipulasi cabang dan referensi `HEAD` (operasi level cabang).
2. Membatalkan modifikasi file pada *working directory* (operasi level file).

Dalam kurikulum modern ini, kita mengadopsi perintah standar:
*   `git switch`: Dikhususkan secara eksklusif untuk berpindah, membuat, dan mengelola alur cabang.
*   `git restore`: Dikhususkan untuk membatalkan modifikasi file (dibahas di modul terpisah).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Anatomi File `.git` Terkait Branch

Saat repositori Git diinisialisasi dan commit pertama dieksekusi, struktur internal berikut dibentuk:

```bash
$ cat .git/HEAD
ref: refs/heads/main

$ cat .git/refs/heads/main
a1b2c3d4e5f60718293a4b5c6d7e8f9012345678
```

### 2. Siklus Pembuatan Branch Baru
Saat menjalankan perintah:
```bash
git branch feature-auth
```
Git melakukan operasi berikut:
1. Membaca hash commit yang sedang ditunjuk oleh `HEAD` (misal: `a1b2c3d`).
2. Membuat file baru di `.git/refs/heads/feature-auth`.
3. Menulis string `a1b2c3d...` ke dalam file tersebut.
4. **Catatan:** `HEAD` *belum* berpindah. Nilai `.git/HEAD` masih `ref: refs/heads/main`.

### 3. Operasi Transisi Branch (`git switch`)
Saat menjalankan:
```bash
git switch feature-auth
```
Git melakukan serangkaian aksi berurutan:
1. Mengubah isi `.git/HEAD` menjadi `ref: refs/heads/feature-auth`.
2. Menghitung delta (perbedaan) antara pohon commit asal dengan pohon commit target.
3. Memperbarui *staging area* (Index) dan *working tree* lokal agar identik dengan kondisi snapshot yang ditunjuk oleh commit tujuan.
4. Menghapus file lokal yang tidak ada di commit target, memperbarui file yang termodifikasi, dan menulis file baru yang didefinisikan pada commit target.

### 4. Transisi Bersih vs Transisi Kotor (*Clean vs Dirty Tree*)
Sebelum Git mengizinkan pergantian branch, Git memeriksa *working tree*:
*   Jika perubahan lokal pada file tidak bertabrakan (*overlap*) dengan file yang berbeda di antara kedua branch, Git mentoleransi dan membawa perubahan uncommitted tersebut ke branch baru.
*   Jika ada file uncommitted yang isinya berbeda antara branch asal dan branch target, Git membatalkan operasi secara atomik untuk mencegah *data loss* dengan pesan:
    `error: Your local changes to the following files would be overwritten by checkout:`

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Fase 1: Pembuatan Branch (`git branch feature-x`)

```text
 working tree & index: sinkron dengan commit [C2]

             HEAD
              │
              ▼
            main ────────┐
                         ▼
 [C0] ◄─── [C1] ◄─── [C2] (hash: 7a8b9c)
                         ▲
            feature-x ───┘
```
*Kondisi:* `feature-x` telah terbentuk, tetapi pointer `HEAD` masih mereferensikan `main`.

---

### Fase 2: Perpindahan Branch (`git switch feature-x`)

```text
                         HEAD
                          │
                          ▼
            main    feature-x
              │          │
              ▼          ▼
 [C0] ◄─── [C1] ◄─── [C2] (hash: 7a8b9c)
```
*Kondisi:* File `.git/HEAD` kini berisi `ref: refs/heads/feature-x`.

---

### Fase 3: Commit Baru pada Branch Terisolasi (`git commit -m "feat: login"`)

```text
            main
              │
              ▼
 [C0] ◄─── [C1] ◄─── [C2] ◄─── [C3] (hash: 9f8e7d)
                                 ▲
                                 │
                            feature-x
                                 ▲
                                 │
                                HEAD
```
*Kondisi:* Pointer `feature-x` bergerak maju ke `C3`. Pointer `main` tetap tertinggal di `C2`. Alur terisolasi secara sempurna.

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah demonstrasi minimalis pembuatan alur kerja terisolasi dari baris perintah.

```bash
# 1. Pastikan status repositori bersih
$ git status
On branch main
nothing to commit, working tree clean

# 2. Buat branch baru sekaligus berpindah ke dalamnya
$ git switch -c feature-metrics
Switched to a new branch 'feature-metrics'

# 3. Verifikasi file pointer HEAD fisik
$ cat .git/HEAD
ref: refs/heads/feature-metrics

# 4. Tambahkan file baru di dalam branch terisolasi ini
$ echo "METRICS_ENABLED=true" > config.env
$ git add config.env
$ git commit -m "feat: tambahkan konfigurasi metrik"
[feature-metrics b3a1c2f] feat: tambahkan konfigurasi metrik
 1 file changed, 1 insertion(+)
 create mode 100644 config.env

# 5. Kembali ke branch main dan buktikan isolasinya
$ git switch main
Switched to branch 'main'

# 6. Buktikan file config.env tidak ada di main (Terisolasi!)
$ ls config.env
ls: cannot access 'config.env': No such file or directory
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Skenario: Anda sedang mengembangkan modul otentikasi, namun tiba-tiba manajer teknis meminta perbaikan darurat (*hotfix*) terhadap kerentanan keamanan pada kode produksi (`main`).

```bash
# LANGKAH 1: Inisialisasi alur kerja fitur
$ git switch -c feature/oauth2
Switched to a new branch 'feature/oauth2'

$ echo "export function auth() { return 'oauth2'; }" > src/auth.js
$ git add src/auth.js
$ git commit -m "feat(auth): inisialisasi modul oauth2"
[feature/oauth2 4d8e12a] feat(auth): inisialisasi modul oauth2

# LANGKAH 2: Muncul bug darurat di main. Working directory harus bersih!
$ git status
On branch feature/oauth2
nothing to commit, working tree clean

# LANGKAH 3: Pindah kembali ke main untuk membuat branch hotfix
$ git switch main
Switched to branch 'main'

# LANGKAH 4: Cabangkan hotfix langsung dari main
$ git switch -c hotfix/cve-sanitize-input
Switched to a new branch 'hotfix/cve-sanitize-input'

# LANGKAH 5: Eksekusi perbaikan
$ echo "export function sanitize(input) { return input.trim(); }" > src/security.js
$ git add src/security.js
$ git commit -m "fix(security): sanitasi payload mentah"
[hotfix/cve-sanitize-input 8c9f001] fix(security): sanitasi payload mentah

# LANGKAH 6: Observasi daftar pointer lokal
$ git branch -v
  feature/oauth2          4d8e12a feat(auth): inisialisasi modul oauth2
* hotfix/cve-sanitize-input 8c9f001 fix(security): sanitasi payload mentah
  main                    2b1a09e chore: base release

# KESIMPULAN:
# Kode oauth2 dan kode hotfix hidup pada ruang semesta terpisah.
# Keduanya tidak saling mengetahui perubahan masing-masing.
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Aspek | Percabangan Frekuensi Tinggi (Short-Lived Feature Branches) | Monolitik / Trunk-Only (Commit langsung ke Main) |
| :--- | :--- | :--- |
| **Isolasi Risiko** | **Sangat Tinggi.** Bug pada eksperimen tidak akan merusak alur rilis utama sebelum diuji. | **Sangat Rendah.** Potensi merusak lingkungan pengujian/produksi secara langsung jika tes gagal. |
| **Konflik Integrasi (*Merge Conflicts*)** | Berpotensi terjadi saat integrasi jika branch dibiarkan berumur terlalu panjang (*stale branch*). | Hampir nihil karena tidak ada percabangan, namun stabilitas kode rentan. |
| **Beban Kognitif Pengembang** | Memerlukan disiplin penamaan (*naming convention*) dan manajemen referensi. | Sederhana secara alur Git, tetapi menuntut pengujian pra-commit yang sangat ketat. |
| **Performa Git** | Git dapat menangani ribuan branch lokal tanpa penurunan performa I/O secara signifikan. | Efisien, tetapi tidak mengeksploitasi arsitektur Git yang berbasis DAG. |

---

## SEKSI 11 — BEST PRACTICES

1.  **Gunakan Konvensi Penamaan Terstruktur (*Namespace-style*):**
    Gunakan pemisah garis miring (`/`) untuk mengelompokkan kategori kerja:
    *   `feature/nama-fitur`
    *   `bugfix/deskripsi-isu`
    *   `hotfix/id-tiket`
    *   `experiment/ide-baru`
2.  **Jaga Siklus Hidup Branch Tetap Pendek (*Short-Lived*):**
    Branch lokal sebaiknya berusia antara hitungan jam hingga 2-3 hari. Hindari memelihara branch selama berminggu-minggu tanpa sinkronisasi, karena akan menimbulkan *merge conflict* masif.
3.  **Hapus Branch yang Telah Selesai Diintegrasikan:**
    Jangan menumpuk pointer lokal yang sudah usang (*stale*).
    ```bash
    git branch -d feature/oauth2 # Safe delete (mengecek status integrasi)
    ```
4.  **Prioritaskan `git switch` Dibandingkan `git checkout`:**
    Gunakan `git switch` untuk navigasi branch guna mengurangi ambiguitas perilaku CLI.
5.  **Pastikan Working Directory Bersih Sebelum Berpindah:**
    Gunakan `git status` sebelum melakukan *switch*. Jika pekerjaan belum selesai tetapi harus berpindah konteks, lakukan commit sementara (*WIP commit*) atau gunakan *stash* (dibahas di bab mendatang).

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Modifikasi File Tanpa Sadar Tertinggal di Branch Asal (*Carrying Changes*)
*   **Gejala:** Mengedit file di `branch-A`, lupa melakukan commit, lalu menjalankan `git switch branch-B`. Tiba-tiba modifikasi tersebut terbawa ke `branch-B`.
*   **Penyebab Teknis:** Git membiarkan transisi branch jika modifikasi lokal tidak menimbulkan konflik dengan file di branch target.
*   **Pencegahan:** Selalu jalankan `git status` sebelum berpindah. Ambil tindakan: commit perubahan tersebut atau pisahkan alur kerjanya.

### 2. Transisi Branch Ditolak (*Aborted Checkout*)
*   **Gejala:** Git menampilkan pesan galat:
    ```text
    error: Your local changes to the following files would be overwritten by checkout:
        app.config
    Please commit your changes or stash them before you switch branches.
    Aborting
    ```
*   **Penyebab Teknis:** File `app.config` di branch saat ini telah Anda modifikasi tanpa commit, sementara di branch tujuan, file `app.config` memiliki konten snapshot yang berbeda. Git menolak berpindah demi mencegah hilangnya modifikasi lokal Anda.
*   **Solusi:** Lakukan commit terlebih dahulu (`git add . && git commit -m "wip: save state"`) sebelum beralih.

### 3. Salah Penggunaan Force Delete (`-D` vs `-d`)
*   **Kesalahan:** Menggunakan `git branch -D feature-x` secara sembarangan.
*   **Dampak Teknis:** Parameter `-D` adalah alias dari `--delete --force`. Tindakan ini akan menghapus pointer branch meskipun commit-commit di dalamnya belum pernah digabungkan (*merged*) ke branch lain, sehingga commit tersebut terancam menjadi *dangling objects*.
*   **Solusi:** Gunakan `-d` secara konsisten. Git akan menolak penghapusan dan memberikan peringatan jika ada perubahan yang belum terintegrasi.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

Jalankan skenario latihan ini di terminal Anda secara berurutan.

### Tugas
1. Buat direktori baru bernama `lab-branching` dan inisialisasi repositori Git.
2. Buat commit pertama pada branch `main` dengan file bernama `system.txt` berisi tulisan `v1.0.0`.
3. Buat branch bernama `feature/database` tanpa langsung berpindah ke dalamnya.
4. Periksa isi file `.git/refs/heads/feature/database` dan bandingkan dengan hash commit saat ini.
5. Pindah ke branch `feature/database` menggunakan perintah modern `git switch`.
6. Ubah isi `system.txt` menjadi `v2.0.0-db` dan commit perubahan tersebut.
7. Pindah kembali ke branch `main`, lalu buktikan isi file `system.txt` masih berbunyi `v1.0.0`.
8. Tampilkan daftar semua branch beserta hash commit terakhirnya menggunakan satu perintah tunggal.

### Kunci Perintah Terminal (Verifikasi Mandiri)

```bash
# 1 & 2
mkdir lab-branching && cd lab-branching
git init
echo "v1.0.0" > system.txt
git add system.txt
git commit -m "chore: initial commit"

# 3
git branch feature/database

# 4
git rev-parse HEAD
cat .git/refs/heads/feature/database
# (Output kedua perintah di atas harus identik!)

# 5
git switch feature/database

# 6
echo "v2.0.0-db" > system.txt
git commit -am "feat: implement database config"

# 7
git switch main
cat system.txt
# (Output harus menampilkan: v1.0.0)

# 8
git branch -v
```

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan-pertanyaan berikut untuk menguji pemahaman Anda:

1.  **Berapa ukuran fisik file dari sebuah Git branch lokal yang tersimpan di dalam folder `.git/refs/heads/`?**
    *   a) Sesuai dengan ukuran total file dalam proyek.
    *   b) 41 Byte (40 karakter hash SHA-1 + 1 karakter *newline*).
    *   c) Bervariasi tergantung jumlah commit yang dibuat di branch tersebut.
    *   d) Nol byte, karena disimpan di dalam database binary Git.

2.  **Apa yang terjadi pada file `.git/HEAD` ketika Anda berpindah branch menggunakan perintah `git switch staging`?**
    *   a) File tersebut dihapus dan dibuat ulang dengan isi commit hash target.
    *   b) Mengisi snapshot seluruh kode program staging ke dalam direktori cache.
    *   c) Nilai string referensinya diperbarui menjadi `ref: refs/heads/staging`.
    *   d) Git membekukan branch `main` ke server remote.

3.  **Manakah perintah yang BENAR untuk membuat sebuah branch baru bernama `fix/typo` dan langsung berpindah ke dalamnya secara atomik?**
    *   a) `git switch -c fix/typo`
    *   b) `git branch --move fix/typo`
    *   c) `git create fix/typo`
    *   d) `git branch -d fix/typo`

4.  **Kapan Git MENOLAK operasi `git switch` dari `branch-A` ke `branch-B`?**
    *   a) Setiap kali terdapat file yang belum di-commit di *working directory*.
    *   b) Hanya ketika uncommitted changes bertabrakan langsung (*conflicted overlap*) dengan modifikasi file yang ada di `branch-B`.
    *   c) Ketika branch tujuan memiliki jumlah commit yang lebih banyak dari branch asal.
    *   d) Ketika komputer tidak terhubung ke jaringan internet.

5.  **Apa perbedaan mendasar antara opsi `-d` dan `-D` pada perintah `git branch`?**
    *   a) `-d` menghapus branch di remote, `-D` menghapus di lokal.
    *   b) `-d` mengecek apakah branch sudah fully merged sebelum dihapus; `-D` melakukan force-deletion tanpa pengecekan.
    *   c) `-d` hanya menghapus file commit; `-D` menghapus direktori proyek.
    *   d) Keduanya identik, `-D` hanyalah sintaks versi lama.

---

### Kunci Jawaban Quiz
1.  **b** — Branch di Git hanyalah sebuah *pointer reference* teks biasa dengan panjang 40 karakter hash ditambah satu karakter penutup baris baru (*newline*).
2.  **c** — File `.git/HEAD` bertindak sebagai *symbolic reference* yang mencatat branch mana yang saat ini sedang aktif diperiksa.
3.  **a** — Opsi `-c` pada `git switch` merupakan singkatan dari `--create`.
4.  **b** — Git sangat cerdas; ia hanya memblokir *switch* jika operasi tersebut berpotensi menimpa data yang belum disimpan (*uncommitted local changes*) pada file yang bertentangan di target branch.
5.  **b** — Flag `-d` (`--delete`) memiliki sistem pengaman (*safety check*), sedangkan `-D` (`--delete --force`) mematikan pengaman tersebut.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

*   **Dokumentasi Resmi Git:**
    *   [`git-switch` Documentation](https://git-scm.com/docs/git-switch)
    *   [`git-branch` Documentation](https://git-scm.com/docs/git-branch)
*   **Buku:**
    *   *Pro Git* oleh Scott Chacon & Ben Straub — Chapter 3: *Git Branching* (Tersedia bebas di situs resmi git-scm).
*   **Materi Interaktif Lanjutan:**
    *   *Visualizing Git Internals through the `.git` directory* oleh Edward Thomson.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1.  **Hakikat Branch:** Bukan duplikasi direktori, melainkan *lightweight pointer* 41 byte yang bergerak maju secara otomatis saat commit baru dibuat.
2.  **Peran `HEAD`:** Kompas internal Git yang menentukan posisi referensi aktif. Ia mengarahkan modifikasi dan commit baru ke branch yang tepat.
3.  **Perintah Modern:** Pisahkan tanggung jawab operasional; gunakan `git switch` untuk berpindah dan membuat branch (`-c`), hindari kebiasaan memakai `git checkout` untuk mencegah salah eksekusi file.
4.  **Integritas Kode:** Isolasi Git menjamin percobaan di branch sampingan tidak akan mengganggu kestabilan branch utama sebelum tahap integrasi eksplisit (*merge/rebase*).

---

## SEKSI 17 — GLOSARIUM

*   **Branch Pointer:** File referensi teks dalam repositori Git yang menyimpan ID commit paling ujung (*tip of the branch*).
*   **HEAD:** File acuan penunjuk lokasi kerja aktif saat ini di dalam pohon repositori Git.
*   **Working Tree (Working Directory):** Direktori lokal fisik tempat pengguna melihat, menambah, dan mengubah file secara langsung di sistem operasi.
*   **Clean State:** Kondisi di mana tidak ada modifikasi yang belum di-*stage* atau belum di-*commit* di working directory.
*   **Dirty State:** Kondisi di mana terdapat perubahan pada berkas yang belum disimpan ke dalam snapshot database Git.
*   **Atomic Switch:** Sifat peralihan branch di mana Git akan menyelesaikan seluruh operasi tanpa cela, atau membatalkannya secara utuh jika terdeteksi konflik risiko kehilangan data.

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Poin Penekanan Konseptual:** Jangan biarkan siswa berpikir bahwa membuat branch baru berarti menduplikasi file fisik di hard drive mereka. Buka folder `.git/refs/heads/` secara langsung di terminal dan cetak isinya menggunakan perintah `cat` untuk menghancurkan miskonsepsi ini sejak awal.
*   **Peringatan Peralihan Sintaks:** Siswa yang sebelumnya pernah membaca tutorial Git lawas mungkin akan sering menggunakan `git checkout -b <nama>`. Arahkan secara persuasif namun tegas menuju `git switch -c <nama>`, jelaskan bahwa standardisasi Git 2.23+ memecah kompleksitas perintah lama tersebut menjadi lebih aman dan intuitif.
*   **Debugging di Kelas:** Jika siswa terjebak dengan pesan *error: local changes would be overwritten*, gunakan ini sebagai momen pembelajaran untuk menguji status working tree mereka, bukan langsung menyuruh mereka menghapus perubahan secara paksa.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi 1.1.0 (Februari 2025):**
    *   Standardisasi penuh sintaks isolasi menggunakan `git switch`.
    *   Penambahan penjelasan mendalam struktur internal berkas `.git/refs/heads/`.
    *   Penyesuaian format 20 seksi sesuai standar kurikulum GEMINI.md.
*   **Versi 1.0.0 (Januari 2024):**
    *   Rilis modul inisial percabangan terisolasi.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya:** `CORE-GIT-03-01` — Siklus Hidup Commit & Staging Area Mekanistik
*   **Modul Saat Ini:** `CORE-GIT-04-01` — Percabangan Terisolasi (*Isolated Branching Architecture*)
*   **Modul Selanjutnya:** `CORE-GIT-04-02` — Mekanisme Integrasi Alur: Fast-Forward vs Three-Way Merge (*Segera Hadir*)