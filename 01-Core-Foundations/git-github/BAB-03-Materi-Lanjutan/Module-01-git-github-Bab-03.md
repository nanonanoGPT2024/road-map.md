# Kurikulum: Git & GitHub Core Engineering
## Kategori: 01-Core-Foundations
## Bab 03: Arsitektur Transisi Status & Manajemen State
### Module 01: Arsitektur Tiga Pohon (Three Trees Architecture) dan Siklus Hidup Berkas (File Lifecycle Engine)

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan memiliki kemampuan terukur untuk:
*   Menganalisis dan membedah representasi biner berkas di dalam tiga area transisi Git (*Working Directory*, *Staging Area/Index*, dan *Commit History/HEAD*) secara deterministik.
*   Mengoperasikan manipulasi status berkas (*Untracked*, *Unmodified*, *Modified*, *Staged*) menggunakan perintah *plumbing* (`git ls-files`, `git update-index`, `git write-tree`) di samping perintah *porcelain* standar.
*   Mendiagnosis dan menyelesaikan inkonsistensi *cache index* berkas akibat anomali *filesystem metadata* (*inode*, *mtime*, *ctime*) pada lingkungan sistem operasi heterogen.
*   Menyusun strategi komit granular berstandar produksi memanfaatkan isolasi *Index* tanpa mengotori *Working Directory*.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta didik wajib menguasai:
*   **Bab 02: Git Object Model**: Pemahaman mendalam tentang *Blob*, *Tree*, *Commit*, dan kalkulasi *Object Hash* (SHA-1/SHA-256).
*   **Struktur Direktori `.git/`**: Pemahaman mengenai fungsi direktori `objects/`, `refs/`, dan berkas `HEAD`.
*   **Dasar Operasi POSIX I/O**: Pemahaman tentang sistem berkas, struktur data *stat* (st_size, st_mtime), serta manipulasi I/O terminal berbasis Linux/macOS/POSIX-compliant.

---

### 3. Concept
Secara fundamental, Git bukanlah sistem pelacak perbedaan berbasis baris (*delta-based version control*), melainkan sebuah *content-addressable filesystem* yang memanipulasi *snapshot* dari tiga pohon representasi data yang independen:

1.  **The Working Tree (Working Directory)**:
    Representasi sistem berkas lokal pada sistem operasi Anda. Ini adalah satu-satunya pohon yang memuat berkas riil yang dapat dieksekusi, didekompilasi, atau diubah oleh editor teks Anda. Status pohon ini bersifat *transient* (sementara) dan berada di luar kontrol *cryptographic integrity* Git sebelum dicatat.
2.  **The Index (Staging Area / Cache)**:
    Jantung performa Git yang disimpan secara fisik dalam format biner pada `.git/index`. *Index* adalah representasi logis dari pohon direktori berikutnya yang akan dijadikan *commit*. *Index* menyimpan daftar berurut dari *path* berkas, atribut perizinan (seperti `100644` untuk berkas biasa atau `100755` untuk eksekusi), *Object ID* (SHA) yang menunjuk ke objek *blob* di dalam `.git/objects`, serta *stat cache* sistem operasi untuk mendeteksi perubahan berkas secara instan tanpa perlu membaca ulang seluruh konten berkas dari *disk*.
3.  **The HEAD (Repository / Commit Tree)**:
    Penunjuk (*pointer*) ke *commit* terakhir yang sedang aktif pada cabang (*branch*) yang sedang diperiksa. *HEAD* merepresentasikan *snapshot* permanen, *immutable* (tidak dapat diubah), dan terenkapsulasi di dalam database objek Git.

```
+--------------------------------------------------------------------------------+
|                             TIGA POHON ARSITEKTUR                              |
|                                                                                |
|  [ Working Directory ]  ====== git add =====>  [      Index      ]             |
|  (Filesystem Nyata)     <==== checkout/ ====== (Cache Biner:     )             |
|                                restore          (.git/index      )             |
|                                                      ||                        |
|                                                 git commit                     |
|                                                      ||                        |
|                                                      \/                        |
|                                                [  HEAD/Repo   ]                |
|                                                (Commit Graph  )                |
+--------------------------------------------------------------------------------+
```

Perubahan berkas bergerak melintasi siklus hidup:
*   **Untracked**: Berkas hadir di *Working Directory*, namun tidak ada referensinya di dalam *Index*.
*   **Staged**: Representasi *blob* dari konten berkas telah ditulis ke database objek, dan *Index* telah diperbarui untuk menunjuk ke hash *blob* tersebut.
*   **Unmodified**: Konten berkas di *Working Directory*, *Index*, dan *HEAD* identik secara *cryptographic hash* dan *metadata stat*.
*   **Modified**: Konten berkas di *Working Directory* berbeda dari entri yang dicatat di dalam *Index*.

---

### 4. Why
Memahami pemisahan antara *Working Directory*, *Index*, dan *HEAD* bukan sekadar teori akademis, melainkan esensial dalam rekayasa perangkat lunak skala produksi:

*   **Atomic Commits**: *Index* memungkinkan insinyur membedah perubahan masif menjadi komit-komit logis yang independen, atomik, dan mudah di-*revert* jika terjadi insiden produksi. Anda dapat memodifikasi 10 berkas, namun hanya memilih 2 berkas (atau bahkan beberapa baris dalam 1 berkas) untuk di-*deploy*.
*   **Efisiensi Stat Cache (I/O Performance)**: Pada repositori berukuran gigabita dengan jutaan berkas, menjalankan `diff` antara seluruh isi berkas di sistem berkas dan database objek setiap kali menjalankan `git status` akan melumpuhkan I/O sistem operasi. *Index* menyimpan struktur `stat` POSIX (*mtime*, ukuran berkas, *inode*). Jika metadata berkas tidak berubah, Git melompati pembacaan berkas secara instan.
*   **Resolusi Konflik Multi-Stage**: Saat terjadi konflik *merge*, *Index* secara internal menggunakan tiga *slot* terpisah (*Stage 1: Common Ancestor*, *Stage 2: Target Branch/Ours*, *Stage 3: Incoming Branch/Theirs*) untuk memungkinkan rekonsiliasi state yang aman.

---

### 5. What
Komponen-komponen kritis dalam siklus ini mencakup:

*   **Berkas `.git/index`**: Berkas biner dengan format header tetap (DIRC - "Directory Cache"), nomor versi, jumlah entri berkas, diikuti oleh daftar terurut dari entri direktori terkompresi.
*   **Metadata Stat Cache**: Menyimpan nilai `ctime`, `mtime`, `device`, `inode`, `uid`, `gid`, dan `file size` untuk mendeteksi *dirty state* tanpa memvalidasi ulang SHA berkas.
*   **SHA-1 / SHA-256 Object References**: Alamat referensi konten terkompresi (zlib) di dalam pohon objek.
*   **File Status Lifecycle Engine**:
    *   *Untracked State*: Berkas yang belum pernah diregistrasi ke `.git/index`.
    *   *Staged State*: Objek *blob* sudah dibuat di `.git/objects/`, referensi SHA dimasukkan ke `.git/index`.
    *   *Committed State*: Pohon struktur direktori (*Tree object*) dibuat dari *Index*, dibungkus dalam *Commit object*, dan direferensikan oleh *HEAD*.
    *   *Modified State*: *Inode/mtime* sistem berkas berubah, memicu Git untuk membaca dan memverifikasi *content hash*.

---

### 6. How
Alur kerja mekanikal internal pergerakan data:

```
[Working Directory]               [Index]                     [.git/objects]
        |                            |                              |
        |--- Berkas dimodifikasi --->|                              |
        |    (Dirty Working Tree)    |                              |
        |                            |                              |
        |--- git add <file> -------->|                              |
        |                            |--- Buat Blob zlib ---------->|
        |                            |    (Simpan hash di objek)    |
        |                            |                              |
        |                            |<-- Tulis SHA & Stat Info ----|
        |                            |    (Update binary cache)     |
        |                            |                              |
        |                            |--- git commit -------------->|
        |                            |    (Generate Tree Object)    |
        |                            |    (Generate Commit Object)  |
        |                            |    (Update HEAD Reference)   |
```

1.  **Deteksi Modifikasi**: Pengguna mengubah berkas `app.py`. Sistem operasi memperbarui `mtime` berkas pada sistem berkas lokal.
2.  **Status Scanning**: Git membandingkan `mtime` sistem berkas dengan `mtime` yang tersimpan di berkas `.git/index`. Perbedaan memicu Git menghitung hash konten baru. Jika berbeda, berkas ditandai sebagai *Modified*.
3.  **Staging (`git add`)**: 
    * Git membaca berkas, mengompresinya menggunakan *deflate* (zlib), menghitung hash SHA-nya, dan menuliskannya langsung ke `.git/objects/xx/yyyy...` sebagai objek *blob*.
    * Git memperbarui `.git/index` dengan mencatat *path*, *file mode*, SHA *blob* baru, dan nilai `stat` terkini.
4.  **Committing (`git commit`)**:
    * Git membaca entri di `.git/index` untuk merakit objek *Tree* (representasi pohon direktori).
    * Git membuat objek *Commit* baru yang merujuk pada *Tree* tersebut dan menautkannya ke *parent commit* sebelumnya.
    * Ref cabang saat ini (misal `refs/heads/main`) diperbarui untuk menunjuk ke hash *commit* baru. *HEAD* secara otomatis merefleksikan perubahan ini.

---

### 7. Analogy
Bayangkan proses pengiriman logistik internasional:

*   **Working Directory** adalah **Gudang Produksi**. Anda merakit, memotong, membongkar, dan merekayasa barang di sini. Kondisinya bisa sangat berantakan (*dirty state*), dengan komponen setengah jadi yang berserakan.
*   **The Index (Staging Area)** adalah **Kontainer Pengiriman (Pallet)**. Anda tidak mengirim seluruh gudang Anda. Anda memilih secara spesifik kotak mana saja yang sudah selesai, menempelkan manifes resmi (*SHA checksum*), dan menaruhnya di atas palet. Anda bisa menambah barang ke palet atau menurunkannya kembali jika salah ambil, tanpa merusak barang di gudang.
*   **The HEAD (Repository)** adalah **Kapal Kargo yang Berlayar dengan Segel Permanen**. Sekali kontainer dimuat dan kapal diberangkatkan (*commit*), muatan disegel dengan stempel waktu dan identitas kapal. Segel tidak dapat dirusak tanpa membatalkan seluruh rekaman manifes pelayaran sebelumnya.

---

### 8. Diagram
Struktur perpindahan status dan representasi biner tiga pohon:

```
+-----------------------------------------------------------------------------------------------+
| FILE LIFECYCLE & THREE TREES ARCHITECTURE                                                     |
+-----------------------------------------------------------------------------------------------+

  [ WORKING DIRECTORY ]           [ THE INDEX (.git/index) ]           [ THE HEAD (Commit Graph) ]
  (Raw File System)               (Binary Staging Table)               (Immutable Objects)

  +-------------------+           +-----------------------+            +-----------------------+
  |                   |           | Mode  | SHA   | Path  |            | Commit: a1b2c         |
  |  main.py (v2)     |           | 100644| e98a1 |main.py|            | Tree:   f3e2d         |
  |  api.py  (v1)     |           | 100644| c4b3a |api.py |            +-----------+-----------+
  |  test.py (untrack)|           +-----------------------+                        |
  +-------------------+                                                            v
           |                                                            +-----------------------+
           |                                                            | Tree Object: f3e2d    |
           |                                                            | 100644 blob d87a2 main|
           |                                                            | 100644 blob c4b3a api |
           |                                                            +-----------------------+
           |
           | 1. Perubahan terjadi (main.py diubah ke v2)
           |    Working Directory != Index (File: "Modified")
           |
           +====== 2. git add main.py ====================>
                    - Tulis Blob e98a1 ke .git/objects
                    - Perbarui record main.py di Index
                    - Working Directory == Index != HEAD (File: "Staged")
                                    |
                                    +====== 3. git commit ====================>
                                             - Tulis Tree baru dari Index
                                             - Tulis Commit baru
                                             - Arahkan HEAD ke Commit baru
                                             - Working Tree == Index == HEAD ("Clean")
```

---

### 9. Simple Example
Demonstrasi transisi siklus hidup berkas menggunakan terminal:

```bash
# 1. Inisialisasi repositori baru
$ mkdir git-lifecycle-demo && cd git-lifecycle-demo
$ git init

# 2. Membuat berkas baru di Working Directory
$ echo "print('version 1')" > app.py

# Berkas berstatus UNTRACKED (ada di disk, belum terdaftar di index)
$ git status -s
?? app.py

# 3. Memindahkan berkas ke STAGING AREA (Index)
$ git add app.py

# Berkas berstatus STAGED (Blob telah ditulis, Index telah diperbarui)
$ git status -s
A  app.py

# 4. Melakukan commit ke HEAD
$ git commit -m "feat: initial commit version 1"
[main (root-commit) 5a1b32f] feat: initial commit version 1
 1 file changed, 1 insertion(+)
 create mode 100644 app.py

# Repository CLEAN (Working Directory == Index == HEAD)
$ git status -s
# (Output kosong)

# 5. Memodifikasi berkas di Working Directory
$ echo "print('version 2')" > app.py

# Berkas berstatus MODIFIED (Working Directory != Index)
$ git status -s
 M app.py
```

---

### 10. Practical Example
Investigasi mendalam menggunakan perintah *Plumbing* untuk memvalidasi isi internal `.git/index` dan manipulasi *Stage* tanpa antarmuka *Porcelain*:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Setup repositori eksperimen
rm -rf deep-dive-repo
mkdir deep-dive-repo && cd deep-dive-repo
git init

# Buat file awal
echo "alpha-content" > alpha.txt
echo "beta-content" > beta.txt

# Inspect Index sebelum staging (Index kosong)
echo "=== 1. Index Sebelum Staging ==="
git ls-files --stage

# Pindahkan file secara plumbing ke staging area
# git hash-object -w menghitung hash dan menulis blob ke database
ALPHA_HASH=$(git hash-object -w alpha.txt)
BETA_HASH=$(git hash-object -w beta.txt)

echo "Alpha Blob Hash: ${ALPHA_HASH}"
echo "Beta Blob Hash:  ${BETA_HASH}"

# Update index secara langsung tanpa 'git add'
git update-index --add --cacheinfo 100644 "${ALPHA_HASH}" alpha.txt
git update-index --add --cacheinfo 100644 "${BETA_HASH}" beta.txt

echo -e "\n=== 2. Isi Index Pasca Plumbing Update ==="
# Format output: <mode> <object-hash> <stage-number> <path>
git ls-files --stage

echo -e "\n=== 3. Status Melalui Git Porcelain ==="
git status

# Memodifikasi Working Directory tanpa menyentuh Index
echo "alpha-corrupted" > alpha.txt

echo -e "\n=== 4. Status Menunjukkan Parsial Staged & Modified ==="
# Menunjukkan alpha.txt ada di Staging Area (versi lama) dan Modified di Working Directory
git status -s

# Memeriksa perbedaan antara Index dan Working Tree
echo -e "\n=== 5. Diff Index vs Working Tree ==="
git diff

# Memeriksa perbedaan antara HEAD dan Index
echo -e "\n=== 6. Diff HEAD vs Index ==="
git diff --cached
```

---

### 11. Real World Example
**Insiden: Anomali Cache Inode pada Build Pipeline Monorepo Skala Besar**

*   **Konteks**: Sebuah perusahaan skala *hyper-growth* memelihara monorepo sebesar 45 GB dengan lebih dari 250.000 berkas. Mesin CI (*Continuous Integration*) menggunakan mekanisme *worker caching* yang memulihkan (`rsync`/`tar`) folder `.git/` dan *working directory* antar eksekusi untuk menghemat waktu kloning.
*   **Masalah**: Pipeline build mendadak mengalami *cache invalidation failure*. Berkas-berkas sumber tidak berubah secara konten, namun perintah `git status` dan linter internal membutuhkan waktu lebih dari 12 menit hanya untuk memindai berkas, yang biasanya memakan waktu 4 detik. Pada beberapa *worker node*, komit kosong dibuat secara otomatis oleh skrip rilis karena Git menandai puluhan ribu berkas sebagai "Modified".
*   **Root Cause**: Utilitas ekstraksi *tar* pada *worker node* memulihkan berkas dengan nilai *timestamp* nanodetik dan nomor *inode* yang berbeda dari metadata stat yang dicatat di `.git/index`. Git mengasumsikan seluruh sistem berkas berada dalam kondisi *dirty*. Git terpaksa membaca ulang ratusan ribu berkas dari *disk*, melakukan *hash recalculation*, dan memenuhi antrean I/O (I/O Bottleneck).
*   **Solusi Rekayasa**:
    1. Tim DevOps menerapkan perintah koreksi stat cache langsung setelah restorasi artefak:
       ```bash
       git update-index --refresh
       ```
    2. Perintah ini memaksa Git memeriksa metadata sistem operasi saat itu dan memperbarui entri stat biner di `.git/index` tanpa menulis ulang *blob* yang sudah ada.
    3. Konfigurasi `core.checkStat = minimal` diaktifkan di tingkat global *runner*, sehingga Git hanya memvalidasi modifikasi berdasarkan ukuran berkas dan waktu modifikasi standar (*mtime* detik), mengabaikan perubahan *ctime* atau *inode* akibat proses un-tar CI. Waktu eksekusi build kembali turun ke 5 detik.

---

### 12. Trade-offs

| Aspek | Staging Terpisah (*Three-Tree Architecture*) | Snapshot Langsung (*Two-Tree Architecture, misal Subversion/Perforce*) |
| :--- | :--- | :--- |
| **Kontrol Granularitas** | **Tinggi**: Memungkinkan pemilihan parsial (`git add -p`), perbaikan komit modular tanpa memengaruhi file kerja. | **Rendah**: Apa yang ada di disk adalah apa yang akan terkirim ke server repositori. |
| **Kompleksitas Mental** | **Tinggi**: Pengembang harus memahami perbedaan *unstaged changes* vs *staged changes* vs *committed history*. | **Rendah**: Konsep biner sederhana: berkas lokal vs repositori remote. |
| **Overhead Penyimpanan Lokal**| **Moderat**: Penulisan instan ke `.git/objects` saat operasi `git add` dapat meninggalkan *dangling/unreferenced blobs* jika dibatalkan. | **Minimal**: Objek baru hanya ditulis pada saat instruksi `commit` dieksekusi secara global. |
| **Performa I/O** | **Tinggi**: Berkas biner `.git/index` menyimpan *stat cache* lokal, meminimalkan *system disk reads* saat operasi status. | **Tergantung Jaringan/Disk**: Sering kali membutuhkan verifikasi server atau pemindaian seluruh disk lokal. |

---

### 13. When To Use
*   Ketika menyusun komit atomik (*atomic commits*) yang mengikuti konvensi seperti *Conventional Commits*.
*   Saat Anda melakukan *debugging* lokal menggunakan log ekstensif atau instrumentasi kode, namun tidak ingin perubahan diagnostik tersebut masuk ke dalam riwayat repositori.
*   Saat menyelesaikan konflik *merge* atau *rebase* yang kompleks, membutuhkan isolasi berkas yang berhasil dituntaskan dari berkas yang masih dalam sengketa.

---

### 14. When NOT To Use
*   Pada *automated pipeline* atau skrip *backup* instan berbasis snapshot penyimpanan blok (misalnya EBS/ZFS snapshots), di mana pemisahan lapisan *Index* adalah redundansi komputasi yang tidak diperlukan.
*   Jika Anda memprogram sistem sinkronisasi berkas real-time (seperti Google Drive/Dropbox sync engine), arsitektur tiga pohon Git menambah *write overhead* dan latensi pelacakan yang tidak efisien.

---

### 15. Common Mistakes
1.  **Mengasumsikan `git add` Hanya Sebuah Penanda**: Banyak pengembang mengira `git add` hanya mencatat nama berkas. Padahal, `git add` langsung membaca konten berkas saat itu juga, mengompresinya, dan menyimpannya sebagai *blob* permanen di database objek. Jika Anda mengubah berkas *setelah* melakukan `git add`, modifikasi terbaru tersebut **tidak** akan masuk ke komit kecuali Anda melakukan `git add` ulang.
2.  **Menghapus Berkas Menggunakan `rm` Manual Tanpa Sinkronisasi Index**: Menggunakan `rm file.txt` menghapus berkas dari *Working Directory*, tetapi meninggalkan referensi yatim di *Index*. Operasi yang benar adalah menggunakan `git rm file.txt` untuk menghapus dari kedua pohon sekaligus.
3.  **Memanipulasi `.git/index` Saat Berkas Terkunci**: Menghapus `.git/index.lock` secara paksa ketika sebuah proses latar belakang Git (misalnya IDE file watcher) sedang menulis data, yang mengakibatkan korupsi biner pada berkas index.

---

### 16. Best Practices (Production Checklist)
*   [ ] **Verifikasi Status Dua Arah**: Selalu gunakan `git diff` (untuk mengecek *Working Tree vs Index*) dan `git diff --cached` (untuk mengecek *Index vs HEAD*) sebelum menjalankan perintah komit.
*   [ ] **Gunakan Interactive Staging**: Terapkan `git add -patch` (`git add -p`) untuk meninjau perubahan baris demi baris, memastikan tidak ada token sensitif (*API keys*), *temporary debug logs*, atau whitespace sampah yang terunggah.
*   [ ] **Pertahankan Kebersihan Status**: Hindari membiarkan status `git status` dipenuhi puluhan berkas *Untracked*. Segera tambahkan berkas yang tidak relevan ke `.gitignore` agar tidak membebani pemindaian index.
*   [ ] **Segarkan Stat Cache**: Jalankan `git update-index --refresh` jika sistem berkas baru saja mengalami perubahan atribut masif dari luar Git (seperti migrasi OS atau eksekusi container volume).

---

### 17. Troubleshooting

#### Masalah 1: Korupsi Berkas Index Biner (`fatal: index file corrupt`)
*   **Gejala**: Perintah git apapun mengembalikan galat `fatal: index file corrupt` atau `error: bad index file sha1 signature`.
*   **Penyebab**: Mesin mati mendadak saat operasi penulisan berkas `.git/index`, atau disk penuh di tengah proses staging.
*   **Solusi Recovery**:
    Karena *Index* hanya berupa *cache*, Anda dapat merekonstruksinya dari *HEAD* tanpa kehilangan data pada *Working Directory*:
    ```bash
    # 1. Hapus berkas biner index yang korup
    rm -f .git/index
    
    # 2. Rekonstruksi ulang index dari commit terakhir (HEAD)
    git reset
    
    # 3. Validasi status kembali normal
    git status
    ```

#### Masalah 2: Konflik Berkas Kunci Index (`fatal: Unable to create '.git/index.lock': File exists`)
*   **Gejala**: Operasi `git add` atau `commit` ditolak dengan pesan kunci terkunci.
*   **Penyebab**: Proses Git lain (seperti background extension pada VS Code, GitLens, atau proses crash sebelumnya) mempertahankan lock file.
*   **Solusi Recovery**:
    ```bash
    # 1. Pastikan tidak ada proses git yang sedang berjalan
    ps aux | grep git
    
    # 2. Jika dipastikan tidak ada proses yang aktif, hapus file lock
    rm -f .git/index.lock
    ```

---

### 18. Exercise
Lakukan skenario diagnostik teknis ini pada terminal lokal Anda:

1.  Inisialisasi direktori kosong sebagai repositori Git.
2.  Buat berkas bernama `secret.txt` dengan isi `database_password_v1`.
3.  Jalankan `git add secret.txt`.
4.  Cari objek hash *blob* dari `secret.txt` menggunakan perintah `git ls-files --stage`.
5.  Ubah isi `secret.txt` di *Working Directory* menjadi `database_password_v2`. Jangan jalankan `git add`.
6.  Ambil kembali konten asli `database_password_v1` dari sistem objek Git langsung ke layar terminal tanpa membatalkan modifikasi yang ada di *Working Directory* (Gunakan `git cat-file`).
7.  Jelaskan mengapa hash pada `git ls-files --stage` tidak berubah meskipun berkas di disk telah dimodifikasi.

---

### 19. Challenge
**Rekonstruksi Komit Penuh Tanpa Menggunakan Perintah Porcelain (`add` atau `commit`)**

Tuliskan sebuah skrip Bash murni yang hanya menggunakan perintah *low-level (plumbing)* Git untuk:
1.  Menginisialisasi repositori Git baru.
2.  Membuat berkas `config/system.json` dengan konten `{"env": "production"}` langsung di *Working Directory*.
3.  Menghasilkan hash *blob* dan menyimpannya ke `.git/objects`.
4.  Mendaftarkan berkas tersebut ke pohon biner `.git/index` menggunakan `git update-index` dengan hak akses mode `100644`.
5.  Menghasilkan objek *Tree* dari `.git/index` menggunakan `git write-tree`.
6.  Membuat objek *Commit* dari hash *Tree* tersebut menggunakan `git commit-tree` dengan pesan `"feat: pure plumbing initialization"`.
7.  Memperbarui referensi `refs/heads/main` dan `HEAD` agar menunjuk ke hash komit baru tersebut menggunakan `git update-ref`.
8.  Buktikan keberhasilannya dengan menjalankan `git log -1` dan `git status` (output `git status` harus menghasilkan `working tree clean`).

---

### 20. Summary
*   Arsitektur Git berdiri di atas interaksi **Tiga Pohon**: *Working Directory* (representasi fisik sistem operasi), *Index* (tabel cache biner staging), dan *HEAD* (graf komit permanen).
*   Operasi staging (`git add`) bukan sekadar pelabelan metadata, melainkan eksekusi kompresi dan penulisan objek *blob* secara fisik ke `.git/objects` disertai pencatatan *stat cache* pada sistem berkas `.git/index`.
*   Siklus hidup berkas melintasi status terisolasi: *Untracked* $\rightarrow$ *Staged* $\rightarrow$ *Unmodified* $\rightarrow$ *Modified*.
*   Pemisahan *Index* dari *Working Directory* memberikan performa I/O instan melalui *metadata checking* serta fleksibilitas tinggi dalam membangun *atomic commits* yang tangguh untuk ekosistem rekayasa perangkat lunak modern.