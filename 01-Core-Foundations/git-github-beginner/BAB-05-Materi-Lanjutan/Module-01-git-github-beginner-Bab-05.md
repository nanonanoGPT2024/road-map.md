# Kurikulum Git & GitHub: 01-Core-Foundations

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** GIT-FOUND-05-01
* **Judul Modul:** Integrasi Kode: Fast-Forward, 3-Way Merge, dan Rebase Dasar
* **Kategori:** 01-Core-Foundations
* **Level Kemahiran:** Beginner to Intermediate
* **Prasyarat:** 
  * Memahami konsep DAG (*Directed Acyclic Graph*) dan struktur *commit* Git.
  * Menguasai navigasi branch dasar (`git branch`, `git switch`, `git checkout`).
  * Memahami *working directory*, *staging area*, dan *repository history*.
* **Estimasi Waktu Belajar:** 120 Menit (60 Menit Teori & Analisis, 60 Menit Praktik Mandiri)
* **Target Environment:** Terminal POSIX / PowerShell dengan Git versi $\ge$ 2.34 (menggunakan strategi default engine ORT).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis Topologi Commit (C4 - Analysis):** Mengidentifikasi kondisi topologi branch yang memungkinkan terjadinya integrasi *Fast-Forward* versus yang membutuhkan *3-Way Merge*.
2. **Mengeksekusi Integrasi Kode (C3 - Application):** Melakukan integrasi branch menggunakan pendekatan *Fast-Forward*, *3-Way Merge* (dengan merge commit), dan *Rebase* dasar secara presisi melalui Git CLI.
3. **Mendemonstrasikan Rebase Workflow (C3 - Application):** Memindahkan basis komit dari satu branch ke branch lain tanpa merusak linearitas riwayat, serta mematuhi kaidah keamanan riwayat publik.
4. **Mengevaluasi Konsekuensi Teknis (C5 - Evaluation):** Membandingkan dampak auditabilitas, integritas referensi SHA-1, dan kemudahan pelacakan regresi (misalnya menggunakan `git bisect`) antara pendekatan *Merge* dan *Rebase*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                           +--------------------------------------+
                           |  INTEGRASI KODE PADA CABANG (BRANCH) |
                           +--------------------------------------+
                                              |
                +-----------------------------+-----------------------------+
                |                                                           |
                v                                                           v
     [STRATEGI PENGGABUNGAN (MERGE)]                               [STRATEGI PERUBAHAN BASIS]
                |                                                           |
        +-------+-------+                                                   v
        |               |                                            [GIT REBASE]
        v               v                                                   |
  [FAST-FORWARD]  [3-WAY MERGE]                                      - Replay Commits
  - Linear        - Non-Linear (Divergent)                           - Linear History
  - Tanpa Commit  - Membuat Merge Commit                             - SHA-1 Berubah
    Baru          - 2 Parent Commits                                 - Bahaya pada Public Branch
  - Pointer Move  - Menggunakan Base Ancestor
```

Struktur relasi:
* **Fast-Forward:** Hanya dapat dieksekusi jika *head commit* dari target branch merupakan direct ancestor dari source branch.
* **3-Way Merge:** Wajib digunakan ketika kedua branch telah divergen (*diverged*), membutuhkan titik temu (*common ancestor* / *merge base*), commit source, dan commit target.
* **Rebase:** Mengambil *diff patch* dari branch fitur, kemudian menerapkannya kembali (*replaying*) di ujung (*tip*) branch target untuk menghasilkan riwayat commit yang linier.

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Dalam proyek perangkat lunak modern, pengembangan fitur, perbaikan bug (*hotfix*), dan eksperimen kode dilakukan secara paralel pada branch terisolasi. Namun, kode yang terisolasi tidak bernilai produksi sebelum diintegrasikan ke branch utama (seperti `main` atau `develop`).

Pemahaman mendalam tentang teknik integrasi kode bukan sekadar perihal menjalankan perintah integrasi, melainkan tentang:
1. **Integritas Riwayat Proyek (*History Hygiene*):** Riwayat commit adalah dokumentasi teknis evolusi perangkat lunak. Pemilihan strategi integrasi yang salah dapat menyebabkan "Merge Hell", graph riwayat yang kusut seperti benang kusut (*railroad tracks pattern*), dan hilangnya konteks perubahan.
2. **Efisiensi Debugging dan Audit:** Ketika sebuah *bug* masuk ke branch produksi, investigasi menggunakan `git bisect` akan jauh lebih efisien pada riwayat yang terstruktur rapi. Jika merge commit dibuat secara ceroboh, pelacakan akar penyebab (*root-cause analysis*) menjadi sangat kompleks.
3. **Kolaborasi Tim yang Aman:** Salah paham terhadap mekanisme *rebase* pada branch publik dapat menimpa riwayat pekerjaan rekan satu tim, memicu hilangnya commit, dan menimbulkan desinkronisasi fatal antar repositori lokal.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Fast-Forward Merge
Fast-Forward adalah mekanisme integrasi termudah di mana Git tidak membuat commit baru. Peristiwa ini terjadi ketika branch tujuan (`main`) tidak memiliki commit baru sejak branch fitur (`feature`) dibuat darinya. Git cukup menggeser pointer referensi branch tujuan maju ke commit terakhir dari branch fitur.

* Karakteristik: Tidak ada commit baru, riwayat tetap linier 100%, metadata merge tidak dicatat.

### 2. 3-Way Merge (True Merge)
3-Way Merge terjadi ketika branch tujuan dan branch fitur telah saling divergen (keduanya memiliki commit baru yang independen). Git tidak dapat sekadar memindahkan pointer, melainkan harus:
1. Mengidentifikasi **Common Ancestor** (Commit B - titik awal percabangan).
2. Membaca **Our Commit** (Commit C - kondisi terkini branch tujuan).
3. Membaca **Their Commit** (Commit D - kondisi terkini branch fitur).
4. Melakukan kalkulasi penggabungan dan menghasilkan sebuah **Merge Commit** baru yang secara struktural memiliki **dua orang tua (two parents)**.

### 3. Rebase Dasar
Rebase adalah proses memindahkan atau meregenerasi urutan commit dari satu branch ke ujung commit branch lain. Alih-alih membuat *merge commit* untuk mempertemukan dua cabang divergen, Rebase mencabut commit-commit unik dari branch saat ini secara temporer, memajukan pointer branch ke target base, lalu menembakkan (*re-applying*) commit-commit tadi satu per satu sebagai commit baru (dengan nilai SHA-1 yang sepenuhnya berbeda).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### Algoritma Internal Git

#### Mekanisme Penentuan Merge Base
Git mencari *Lowest Common Ancestor* (LCA) di dalam struktur DAG dengan menelusuri rantai pointer parent ke belakang dari kedua branch head.

```
       B --- C (main)
      /
  A -+
      \
       D --- E (feature)
```
* Ancestor bersama: `A`
* Git membandingkan delta:
  * $\Delta_1 = \text{Diff}(A \to C)$
  * $\Delta_2 = \text{Diff}(A \to E)$
* Engine penggabungan Git (sejak v2.34: default engine `merge-ort`, singkatan dari *Ostensibly Recursive's Twin*) mencoba menyatukan kedua perubahan tanpa intervensi pengguna jika kedua delta menyentuh berkas atau baris yang berbeda.

#### Mekanisme Rebase Step-by-Step
Ketika Anda berada di branch `feature` dan mengeksekusi `git rebase main`:
1. Git menandai commit unik pada `feature` yang tidak ada di `main` (misal: `D` dan `E`).
2. Commit `D` dan `E` disimpan ke area temporer dalam format patch (terletak di direktori `.git/rebase-apply` atau `.git/rebase-merge`).
3. Pointer branch `feature` direset secara paksa (*hard reset*) ke posisi branch `main` (`C`).
4. Git mengaplikasikan patch `D` ke atas `C`, menghasilkan commit baru `D'` dengan parent `C`.
5. Git mengaplikasikan patch `E` ke atas `D'`, menghasilkan commit baru `E'` dengan parent `D'`.
6. Pointer `HEAD` dan branch `feature` dipindahkan ke `E'`. Commit lama `D` dan `E` ditinggalkan tanpa referensi branch dan nantinya akan dibersihkan oleh Garbage Collector (`git gc`).

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Skenario 1: Fast-Forward Merge

#### Kondisi Awal:
```
(main)
  A --- B
         \
          C --- D  (feature, HEAD)
```
*Catatan:* `main` belum bergerak sejak commit `B`.

#### Setelah `git switch main` lalu `git merge feature`:
```
(main, feature, HEAD)
  A --- B --- C --- D
```
*Hasil:* Pointer `main` melompat langsung ke commit `D`. Tidak ada *merge commit* tambahan.

---

### Skenario 2: 3-Way Merge (True Merge)

#### Kondisi Awal (Divergen):
```
          C --- D  (main, HEAD)
         /
  A --- B (Merge Base)
         \
          E --- F  (feature)
```
*Catatan:* Terdapat commit baru di `main` (`C`, `D`) dan di `feature` (`E`, `F`).

#### Setelah `git merge feature`:
```
          C ------- D --------- M  (main, HEAD)
         /                     /
  A --- B                     /
         \                   /
          E --------------- F  (feature)
```
*Hasil:* Terbentuk commit `M` (Merge Commit). Commit `M` memiliki dua parent: `D` (Parent 1) dan `F` (Parent 2).

---

### Skenario 3: Rebase Dasar

#### Kondisi Awal (Divergen):
```
          C --- D  (main)
         /
  A --- B (Merge Base)
         \
          E --- F  (feature, HEAD)
```

#### Selama Eksekusi `git rebase main`:
```
  Langkah 1: Simpan E dan F ke memori sementara.
  Langkah 2: Set HEAD feature ke D.
  Langkah 3: Re-apply E -> menghasilkan E' (SHA-1 berubah!).
  Langkah 4: Re-apply F -> menghasilkan F' (SHA-1 berubah!).
```

#### Kondisi Akhir:
```
                  (main)
                    |
  A --- B --- C --- D --- E' --- F'  (feature, HEAD)
```
*Hasil:* Riwayat menjadi sepenuhnya linier. Jika branch `main` kemudian melakukan `git merge feature`, prosesnya akan menjadi **Fast-Forward**.

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah simulasi skenario *Fast-Forward* menggunakan shell session:

```bash
# 1. Inisialisasi repositori baru
mkdir git-integration-demo && cd git-integration-demo
git init -b main

# 2. Buat commit awal di branch main
echo "# Core Library" > README.md
git add README.md
git commit -m "docs: inisialisasi berkas README"

# 3. Buat branch baru dan beralih ke dalamnya
git switch -c feature/logger

# 4. Buat commit baru di branch feature
echo "function log(msg) { console.log(msg); }" > logger.js
git add logger.js
git commit -m "feat: tambahkan fungsi dasar logger"

# 5. Kembali ke main dan lakukan integrasi Fast-Forward
git switch main
git merge feature/logger
```

**Output Terminal:**
```text
Updating a1b2c3d..e4f5g6h
Fast-forward
 logger.js | 1 +
 1 file changed, 1 insertion(+)
 create mode 100644 logger.js
```

Perhatikan baris `Fast-forward`. Git hanya memajukan pointer tanpa memicu editor teks untuk menulis pesan merge.

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Simulasi riil: Tim backend sedang memelihara branch `main`, sementara seorang engineer mengerjakan branch `feature/auth`. Di tengah jalan, sebuah patch keamanan masuk ke `main`. Kita akan menyelesaikan integrasi dengan dua pendekatan: **3-Way Merge** dan **Rebase**.

### Persiapan Repositori:
```bash
# Setup sandbox
mkdir app-auth-workflow && cd app-auth-workflow
git init -b main

# Commit awal
echo "console.log('App init');" > app.js
git add app.js && git commit -m "chore: setup app bootstrap"

# Buka branch fitur
git switch -c feature/auth
echo "const login = () => true;" >> auth.js
git add auth.js && git commit -m "feat(auth): implementasi dummy login"

# Simulasi commit masuk di main saat feature/auth masih dikembangkan
git switch main
echo "console.log('Security patch applied');" >> security.js
git add security.js && git commit -m "fix(security): patch kerentanan env"
```

### Opsi A: Menyelesaikan Menggunakan 3-Way Merge
```bash
# Integrasikan feature/auth langsung ke main
git switch main
git merge feature/auth -m "merge: integrasikan feature/auth ke main"

# Verifikasi riwayat commit
git log --oneline --graph
```
**Hasil Graph:**
```text
*   7c9b1a2 (HEAD -> main) merge: integrasikan feature/auth ke main
|\  
| * e3a4f12 (feature/auth) feat(auth): implementasi dummy login
* | 8a1b2c3 fix(security): patch kerentanan env
|/  
* 0f12d4a chore: setup app bootstrap
```

### Opsi B: Menyelesaikan Menggunakan Rebase Workflow
Jika standar tim mewajibkan riwayat linier sebelum *Pull Request* digabungkan:
```bash
# Beralih ke branch fitur
git switch feature/auth

# Rebase feature/auth ke atas main yang telah ter-update
git rebase main

# Verifikasi riwayat pada branch fitur
git log --oneline --graph
```
**Hasil Graph:**
```text
* d5c6b7a (HEAD -> feature/auth) feat(auth): implementasi dummy login
* 8a1b2c3 (main) fix(security): patch kerentanan env
* 0f12d4a chore: setup app bootstrap
```
*Sekarang, commit dummy login berada tepat di ujung patch keamanan. Jika `main` digabungkan dengan `feature/auth`, integrasi berjalan secara Fast-Forward.*

```bash
git switch main
git merge feature/auth
```
**Hasil Akhir Linier di `main`:**
```text
* d5c6b7a (HEAD -> main, feature/auth) feat(auth): implementasi dummy login
* 8a1b2c3 fix(security): patch kerentanan env
* 0f12d4a chore: setup app bootstrap
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Aspek | Fast-Forward | 3-Way Merge (`--no-ff`) | Rebase Dasar |
| :--- | :--- | :--- | :--- |
| **Bentuk Riwayat** | Linier murni | Non-linier (Grafik divergen / web-like) | Linier murni |
| **Merge Commit** | Tidak ada | Ada (kecuali resolved manual) | Tidak ada |
| **Auditabilitas Konteks** | Konteks cabang hilang | Sangat baik (menandai penggabungan fitur) | Mempertahankan atomisitas commit |
| **Modifikasi Riwayat** | Aman (Pointer geser saja) | Aman (Menambah commit baru) | **Berbahaya** (Mengubah SHA-1 commit) |
| **Debugging (`git bisect`)** | Mudah | Rentan ambigu di commit merge | Sangat mudah dan prediktif |
| **Tingkat Kompleksitas** | Nol | Rendah - Menengah | Menengah - Tinggi |

### Kapan Memilih 3-Way Merge:
* Saat mempertahankan bukti historis bahwa sebuah fitur dikembangkan secara paralel adalah syarat regulasi/audit.
* Mengintegrasikan *Release Branch* atau *Long-Running Branch* ke `main`.

### Kapan Memilih Rebase:
* Membersihkan riwayat branch lokal personal sebelum mempublikasikan kode (*push*) ke remote.
* Memperbarui branch fitur dengan perubahan terbaru dari `main` tanpa mengotori commit log dengan pesan "Merge branch 'main' into feature".

---

## SEKSI 11 — BEST PRACTICES

1. **Patuhi "The Golden Rule of Rebase":**
   > *Jangan pernah merebase commit yang sudah di-push ke repositori publik/shared branch.*
   Jika Anda mengubah commit yang telah di-*pull* oleh anggota tim lain, Anda memecah riwayat referensi mereka dan memicu duplicate commits saat sinkronisasi ulang.
2. **Gunakan `git merge --no-ff` untuk Rekaman Fitur Utama:**
   Bahkan jika branch Anda memungkinkan *Fast-Forward*, gunakan instruksi eksplisit:
   ```bash
   git merge --no-ff feature/nama-fitur
   ```
   Langkah ini memaksa Git membuat merge commit, menjaga keutuhan informasi bahwa kelompok commit tersebut merupakan satu kesatuan sub-proyek.
3. **Selalu Tarik Perubahan Remote Menggunakan Rebase:**
   Konfigurasikan Git lokal untuk menyelaraskan branch pelacak lokal dengan branch remote secara linier:
   ```bash
   git config --global pull.rebase true
   ```
   Ini mencegah terciptanya *merge commit* redundant setiap kali Anda menjalankan `git pull`.
4. **Verifikasi Status Branch Sebelum dan Sesudah Integrasi:**
   Jalankan `git status` dan `git log --graph --oneline -n 5` untuk mengonfirmasi posisi `HEAD` sebelum mengeksekusi integrasi berbahaya.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Merusak Repositori Tim Akibat Force Push Tanpa Lease
* **Penyebab:** Melakukan rebase pada branch publik, kemudian memaksa pembaharuan ke server menggunakan `git push --force`.
* **Dampak:** Commit rekan tim yang telah masuk ke branch yang sama tertimpa dan terhapus secara efektif dari tracking index.
* **Solusi/Pencegahan:** Selalu gunakan proteksi lease jika terpaksa memperbarui riwayat branch:
  ```bash
  git push --force-with-lease
  ```

### 2. Terjebak dalam Infinite Loop Merge Commits
* **Penyebab:** Melakukan `git merge main` ke branch fitur secara berkala setiap kali ada perubahan di `main`, lalu melakukan `git merge feature` kembali ke `main`.
* **Dampak:** Log Git dipenuhi puluhan merge commit artifisial ("Merge branch 'main' into feature-xyz") yang mengaburkan substansi perubahan kode yang sesungguhnya.
* **Solusi:** Gunakan `git rebase main` saat berada di branch fitur untuk memperbarui basis kode.

### 3. Panik Saat Rebase Terhenti Akibat Konflik
* **Penyebab:** Patch rebase mengalami benturan perubahan kode dan developer tidak tahu cara membatalkannya.
* **Solusi:** 
  * Jangan langsung menghapus direktori proyek!
  * Jika ingin membatalkan rebase dan kembali ke status awal:
    ```bash
    git rebase --abort
    ```
  * Jika sudah menyelesaikan konflik pada berkas:
    ```bash
    git add <file-konflik>
    git rebase --continue
    # JANGAN PERNAH menjalankan git commit saat menyelesaikan konflik rebase!
    ```

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Lab 1: Memaksa Non-Fast-Forward Merge (Tingkat: Terbimbing)
1. Buat folder `lab-git-merge`, inisialisasi Git repository.
2. Tambahkan berkas `index.html`, commit dengan pesan `feat: inisialisasi HTML`.
3. Buka branch baru `styling`.
4. Tambahkan berkas `style.css`, commit dengan pesan `feat: tambahkan styles dasar`.
5. Kembali ke `main`. Karena tidak ada commit baru di `main`, branch ini valid untuk *Fast-Forward*.
6. Integrasikan branch `styling` dengan **mematikan** fitur fast-forward:
   ```bash
   git merge --no-ff styling -m "merge: integrasikan styling ke main"
   ```
7. Amati output grafis riwayat:
   ```bash
   git log --graph --oneline
   ```
   *Ekspektasi:* Terdapat node merge commit meskipun sebenarnya bisa dilakukan fast-forward.

---

### Lab 2: Pembersihan Riwayat Divergen Melalui Rebase (Tingkat: Mandiri)
1. Buat branch baru dari `main` bernama `feature/calculator`.
2. Tulis implementasi fungsi kalkulator pada `calc.js` dan lakukan commit: `feat: add add() function`.
3. Pindah ke branch `main`. Lakukan perubahan independen pada `README.md`, lalu commit: `docs: update deskripsi repository`.
4. Kembali ke `feature/calculator`.
5. Jalankan proses rebase terhadap `main`.
6. Pastikan seluruh commit fitur Anda berada di atas commit dokumentasi dari `main`.
7. Gabungkan branch fitur ke `main` secara Fast-Forward.

---

### Lab 3: Penyelamatan Riwayat (Disaster Recovery Challenge)
1. Pada repositori latihan, eksekusi rebase yang tidak disengaja.
2. Amati bahwa commit ID lama branch fitur Anda telah hilang dari log standar.
3. Gunakan perkakas audit internal Git untuk menemukan kembali commit SHA lama:
   ```bash
   git reflog
   ```
4. Reset pointer branch Anda ke commit lama sebelum rebase dieksekusi:
   ```bash
   git reset --hard HEAD@{n}
   ```
5. Pulihkan state branch ke kondisi stabil.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan berikut untuk menguji pemahaman Anda:

1. **Kondisi topologi manakah yang menjadi syarat mutlak terjadinya penggabungan Fast-Forward?**
   * A. Target branch memiliki jumlah commit lebih banyak dari source branch.
   * B. Head commit target branch merupakan leluhur langsung (*direct ancestor*) dari source branch.
   * C. Kedua branch sama-sama memiliki commit baru yang divergen.
   * D. Repository memiliki engine ORT yang aktif secara global.

2. **Berapa jumlah parent commit yang dimiliki oleh sebuah commit hasil dari 3-Way Merge (`git merge --no-ff`)?**
   * A. 1
   * B. 2
   * C. 3
   * D. Bergantung pada jumlah file yang berkonflik.

3. **Apa dampak utama terhadap commit object ketika operasi `git rebase` berhasil dijalankan?**
   * A. Nilai hash SHA-1 dari commit yang dipindahkan tetap persis sama.
   * B. Commit-commit yang dipindahkan dilebur (*squashed*) secara otomatis menjadi satu commit root.
   * C. Git mencetak commit baru dengan hash SHA-1 baru karena parent-nya telah berganti.
   * D. Git menghapus working directory dan memulihkan stash secara rekursif.

4. **Kapan implementasi perintah `git rebase` DILARANG keras untuk dilakukan?**
   * A. Ketika branch fitur Anda baru saja dibuat dari branch `main` lokal.
   * B. Ketika Anda belum melakukan `git add` pada unstaged changes.
   * C. Ketika commit yang akan direbase telah dipublikasikan ke branch bersama (*shared/public branch*).
   * D. Ketika file yang dimodifikasi bertipe binary (*executable*).

5. **Setelah menyelesaikan konflik di tengah-tengah proses rebase, perintah CLI apa yang harus dieksekusi selanjutnya?**
   * A. `git commit -m "resolve conflict"`
   * B. `git rebase --continue`
   * C. `git push --force`
   * D. `git merge --continue`

---

### Kunci Jawaban & Rasionalisasi

1. **Jawaban: B.** Fast-Forward hanya dapat terjadi jika target branch tidak memiliki commit baru yang bercabang dari merge base; pointer cukup berjalan maju (*fast-forward*) menyusuri garis lurus leluhur.
2. **Jawaban: B.** Merge commit standar adalah konvergensi dari dua alur cabang yang berbeda, sehingga metadata commit tersebut mencatat tepat dua pointer parent (Parent 1: branch tujuan, Parent 2: branch yang digabungkan).
3. **Jawaban: C.** Kriptografi Git (SHA-1) menghitung isi tree, pesan commit, author, commit date, dan *Parent SHA*. Karena parent dari commit tersebut berubah saat ditempatkan di atas base baru, hash SHA-1 secara matematis pasti berubah.
4. **Jawaban: C.** Sesuai *Golden Rule of Rebase*, merebase commit yang sudah dipublikasikan ke remote publik akan merusak basis commit rekan kerja Anda dan memicu konflik desinkronisasi massal.
5. **Jawaban: B.** Selama rebase, Git menerapkan patch satu per satu. Setelah konflik diselesaikan dan dimasukkan ke staging area (`git add`), instruksi yang valid adalah `git rebase --continue` untuk melanjutkan applying patch berikutnya. Menjalankan `git commit` secara manual akan merusak kontrol alur rebase Git.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Dokumentasi Resmi Git:**
  * [git-merge Documentation](https://git-scm.com/docs/git-merge)
  * [git-rebase Documentation](https://git-scm.com/docs/git-rebase)
* **Buku Standar Industri:**
  * *Pro Git* oleh Scott Chacon and Ben Straub — Chapter 3: *Git Branching - Basic Branching and Merging & Rebasing*.
* **Spesifikasi Internal Engine:**
  * Git Core Team: *Merge-ORT: A New Merge Engine for Git* (Landed in Git 2.33/2.34 release series).
* **Simulator Visual Interaktif:**
  * [Visualizing Git Concepts and DAG](https://git-school.github.io/visualizing-git/)
  * [Learn Git Branching Interactive Sandbox](https://learngitbranching.js.org/)

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

* **Fast-Forward Merge** tidak menghasilkan commit baru; ia hanya memajukan pointer branch ke depan ketika tidak ada percabangan riwayat (*linear*).
* **3-Way Merge** digunakan saat branch mengalami divergensi. Git membaca tiga titik (*Ancestor*, *Our tip*, *Their tip*) untuk menyatukan perubahan dalam sebuah *merge commit* khusus yang memiliki dua parent.
* **Rebase** memodifikasi riwayat dengan menulis ulang (*rewriting*) urutan commit dari satu base ke base commit lain. Ini menghasilkan riwayat yang linier, bersih, dan mempermudah penelusuran regresi.
* **Integritas Riwayat vs. Kebersihan Visual:** Merge commit menjaga akurasi konteks sejarah secara objektif, sementara Rebase menyederhanakan riwayat linier demi estetika dan efisiensi audit.
* **The Golden Rule:** Jaga branch publik Anda dari mutasi riwayat; gunakan rebase secara ketat hanya pada branch lokal/fitur privat sebelum dipublikasikan.

---

## SEKSI 17 — GLOSARIUM

* **DAG (Directed Acyclic Graph):** Struktur data matematika simpul (*nodes*) dan sisi berarah (*edges*) tanpa siklus tertutup, yang digunakan Git untuk memodelkan seluruh riwayat commit.
* **Merge Base:** Nenek moyang terdekat (*lowest common ancestor*) yang dimiliki secara bersamaan oleh dua branch yang divergen.
* **Parent Commit:** Objek commit referensi yang mendahului sebuah commit tertentu.
* **Patch:** Berkas teks representasi perbedaan baris kode (*diff*) yang dapat diterapkan pada file sumber.
* **Reflog (Reference Logs):** Mekanisme audit Git yang mencatat histori pergerakan pointer `HEAD` dan branch lokal, memungkinkan pemulihan commit yang terhapus secara logis.
* **ORT Engine:** Algoritma penggabungan berkas default Git modern (*Ostensibly Recursive's Twin*) yang dirancang untuk performa tinggi dan resolusi konflik otomatis yang lebih akurat.

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Poin Penekanan Materi:
* Pemula sering menganggap *Rebase* sebagai pengganti mutlak *Merge*. Tegaskan bahwa Rebase dan Merge adalah perkakas komplementer, bukan rivalitas fungsional.
* Hindari mengajarkan `rebase -i` (interaktif) pada sesi ini. Fokuskan peserta pada model mental bagaimana pointer bergerak dan mengapa nilai hash SHA-1 berubah saat dieksekusi.

### Panduan Visualisasi Kelas:
* Gambarkan struktur pohon di papan tulis/canvas. Gunakan magnet atau penanda warna untuk mendemonstrasikan pointer branch (`main`, `HEAD`, `feature`). Tunjukkan secara fisik bahwa saat rebase terjadi, magnet commit dicabut dan ditempelkan kembali di tempat baru dengan warna (SHA) yang berbeda.

### Antisipasi Masalah Teknis Peserta:
* Sering kali peserta lupa melakukan `git switch` ke branch target sebelum mengetik `git merge`. Latih peserta untuk selalu membaca output status: *"Merge dilakukan dari branch tujuan dengan memanggil branch sumber."*

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.1.0 (2024-10-24):**
  * Penambahan rincian Git merge engine ORT pada Seksi 06.
  * Standarisasi sintaks CLI menggunakan `git switch` modern menggantikan `git checkout`.
  * Integrasi latihan pemulihan disaster recovery menggunakan `git reflog`.
* **Versi 1.0.0 (2023-05-15):**
  * Rilis modul perdana kurikulum core-foundations untuk materi integrasi Fast-Forward, True Merge, dan Rebase.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `GIT-FOUND-04-02: Isolasi Fitur dan Strategi Percabangan Dasar`
* **Modul Saat Ini:** `GIT-FOUND-05-01: Integrasi Kode: Fast-Forward, 3-Way Merge, dan Rebase Dasar`
* **Modul Berikutnya:** `GIT-FOUND-05-02: Resolusi Konflik: Teori, Strategi, dan Eksekusi Praktis`