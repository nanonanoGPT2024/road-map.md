# MODUL 01 (BAB 02): INISIALISASI, KONFIGURASI, & SIKLUS HIDUP OBJEK GIT

---

## SEKSI 01 — IDENTITAS MODUL

| Parameter | Spesifikasi |
| :--- | :--- |
| **Kode Modul** | `GIT-CORE-0201` |
| **Kategori Kurikulum** | `01-Core-Foundations` |
| **Tingkat Kesulitan** | *Beginner to Intermediate* |
| **Estimasi Waktu Belajar** | 90 Menit |
| **Prasyarat Pengetahuan** | Pemahaman dasar Command Line Interface (CLI/Terminal), navigasi filesystem (`cd`, `mkdir`, `ls`, `cat`), dan manipulasi teks dasar. |
| **Lingkungan Praktik** | Git versi $\ge 2.38$, Bash / Zsh shell di Linux, macOS, atau Windows Subsystem for Linux (WSL2). |
| **Keluaran Akhir (Artifact)** | Repositori Git yang dikonfigurasi secara deterministik, pemahaman dekonstruksi direktori `.git/`, dan kemampuan membedah *content-addressable database*. |

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta mampu:
1. **Mengonfigurasi** hierarki konfigurasi Git (*System*, *Global*, *Local*, *Worktree*) secara deterministik untuk mencegah kebocoran kredensial atau atribusi metadata *commit* yang keliru.
2. **Menginisialisasi** repositori lokal menggunakan parameter eksplisit dan menganalisis struktur internal direktori `.git/` secara mendalam.
3. **Mendekonstruksi** *content-addressable storage* Git dengan menghitung SHA-1/SHA-256 hash secara manual dari payload data dan header objek.
4. **Menelusuri** siklus hidup empat objek fundamental Git (*blob*, *tree*, *commit*, *annotated tag*) langsung dari sistem berkas menggunakan perintah *plumbing*.
5. **Mengisolasi dan memperbaiki** anomali pada siklus pelacakan status berkas (*untracked*, *staged*, *committed*, *modified*).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                     +---------------------------------------+
                     |        git config (Hierarki)          |
                     |  [System -> Global -> Local -> Work]  |
                     +-------------------+-------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |         Inisialisasi (git init)       |
                     +-------------------+-------------------+
                                         |
                       +-----------------+-----------------+
                       |                                   |
                       v                                   v
             [Working Directory]                    [.git/ Directory]
             (Berkas Nyata)                         |-- HEAD
                       |                            |-- config
                       | (git add)                  |-- index (Staging Area)
                       v                            |-- refs/
                 [Index/Staging]                    +-- objects/ (Object Store)
                       |                                   |
                       | (git commit)                      |
                       v                                   v
             [Immutable Object Store] <--------------------+
             |-- Blob   : Payload data mentah
             |-- Tree   : Struktur direktori & mode berkas
             |-- Commit : Pointer ke Tree, Author, & Parent
             +-- Tag    : Pointer permanen bertanda tangan
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Mayoritas pengguna memperlakukan Git sebagai serangkaian perintah magis (*magic incantations*): `git add`, `git commit`, `git push`. Ketika terjadi *merge conflict*, repositori *detached HEAD*, atau korupsi *index*, mereka mengalami kebingungan karena kehilangan representasi mental tentang apa yang sebenarnya terjadi di bawah permukaan.

Git pada dasarnya bukanlah sekadar Version Control System (VCS); **Git adalah sebuah Content-Addressable Object Database dengan antarmuka VCS di atasnya**. Memahami struktur direktori `.git/` dan siklus hidup objeknya akan:
* Menghilangkan ketakutan saat berhadapan dengan kegagalan operasi Git.
* Memungkinkan Anda merekonstruksi repositori yang rusak tanpa kehilangan data.
* Menjamin atribusi kode (identitas *committer* dan *author*) valid secara hukum dan teknis di lingkungan kolaborasi *enterprise*.
* Mengubah Git dari alat yang membingungkan menjadi instrumen rekayasa perangkat lunak yang presisi.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Hierarki `git config`
Git membaca konfigurasinya secara kaskade (*cascading*). Nilai konfigurasi yang lebih spesifik akan menimpa (*override*) konfigurasi yang lebih umum:
* **System (`--system`)**: Berlaku untuk semua pengguna di sistem operasi. Berada di `/etc/gitconfig` (Linux/macOS) atau `C:\ProgramData\Git\config` (Windows).
* **Global (`--global`)**: Berlaku untuk seluruh repositori milik pengguna yang sedang aktif. Berada di `~/.gitconfig` atau `~/.config/git/config`.
* **Local (`--local`)**: Standar (*default*). Hanya berlaku pada repositori spesifik saat ini. Berada di `.git/config`.
* **Worktree (`--worktree`)**: Berlaku untuk *linked working tree* tertentu dalam repositori berskala besar.

### 2. Anatomi Direktori `.git/`
Ketika `git init` dieksekusi, Git membuat direktori tersembunyi bernama `.git/` dengan komponen utama:
* `HEAD`: Berkas teks penunjuk cabang aktif atau referensi objek commit saat ini (`ref: refs/heads/main`).
* `config`: Konfigurasi lokal yang spesifik untuk repositori ini.
* `description`: Digunakan oleh GitWeb; jarang dipakai di Git modern.
* `hooks/`: Skrip otomasi sisi klien atau peladen yang dipicu oleh siklus tertentu (misal: `pre-commit`).
* `info/exclude`: Berkas pengecualian pelacakan khusus lokal yang tidak di-*commit* (berbeda dari `.gitignore`).
* `objects/`: *Database* objek konten-teralamatkan (*blob*, *tree*, *commit*, *annotated tag*).
* `refs/`: Penunjuk bernama (*pointers*) yang merujuk ke *hash* commit (cabang dan tag).
* `index`: Direktori biner yang merepresentasikan *Staging Area* (dibuat saat `git add` pertama kali dijalankan).

### 3. Empat Tipe Objek Git Fundamental
Semua objek di dalam Git disimpan di direktori `.git/objects/` dan bersifat *immutable* (tidak dapat diubah setelah ditulis):
1. **Blob (*Binary Large Object*)**: Menyimpan konten murni dari sebuah berkas. Blob **tidak** menyimpan nama berkas, waktu modifikasi, atau izin berkas.
2. **Tree**: Merepresentasikan direktori. Berisi daftar asosiasi antara mode berkas (*permissions*), tipe objek (*blob* atau *tree* lain), *hash*, dan nama berkas.
3. **Commit**: Mengikat *Tree* akar dari *snapshot*, menunjuk ke satu atau lebih *parent commit*, serta menyimpan metadata pembuat (*author*), penyimpan (*committer*), waktu, dan pesan *commit*.
4. **Annotated Tag**: Objek mirip commit yang menunjuk secara permanen ke suatu objek (umumnya commit), dilengkapi metadata penanda tangan dan pesan rilis.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Algoritma Content-Addressable Storage
Git tidak menggunakan nama berkas untuk melacak objek di dalam basis datanya, melainkan *cryptographic hash* (SHA-1 berupa 40 digit heksadesimal, atau SHA-256 berupa 64 digit heksadesimal). 

Format internal pembuatan sebuah objek Git:
$$\text{Payload} = \text{type} + \text{" "} + \text{size} + \text{"\0"} + \text{content}$$

Contoh pembuatan Hash:
1. Git menerima konten string `"halo dunia\n"`.
2. Git menghitung panjang string tersebut (11 byte).
3. Git menyusun *header*: `blob 11\0`.
4. Git menggabungkan *header* dan *content*.
5. Git menghitung SHA-1 dari kombinasi tersebut:
   $$\text{SHA-1}(\text{"blob 11\0halo dunia\n"}) = \text{d5e18237e2...}$$
6. Objek dikompresi menggunakan format `zlib`.
7. Berkas disimpan pada jalur: `.git/objects/d5/e18237e2...` (2 karakter pertama menjadi nama subdirektori, 38 karakter sisanya menjadi nama berkas).

### 2. Alur Transisi State Siklus Hidup Git
```
                    [ File System ]
                           |
                           v (Buat berkas)
                    [ UNTRACKED ]
                           |
                           | git add <file>
                           v
                     [ STAGED ] <------------+
                     (Blob ditulis           |
                      ke .git/objects)       |
                           |                 |
                           | git commit      | git add <file>
                           v                 |
                    [ UNMODIFIED ]           |
                           |                 |
                           v (Edit berkas)   |
                     [ MODIFIED ] -----------+
```

1. **Untracked**: Berkas berada di direktori kerja, tetapi tidak terdaftar di dalam berkas *index* Git.
2. **Staged**: Berkas telah dipindai, objek *blob* telah dibuat dan dikompresi ke direktori `.git/objects/`, dan jalurnya dicatat ke berkas biner `.git/index`.
3. **Committed**: Git menyusun struktur *Tree* berdasarkan berkas *index*, membungkusnya dalam objek *Commit*, lalu memperbarui referensi cabang saat ini ke *Commit* baru tersebut.
4. **Modified**: Konten berkas di direktori kerja telah berubah dan *checksum*-nya tidak lagi sama dengan *hash* yang tertera pada *index*.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Relasi Objek Git Internal
Diagram berikut mendemonstrasikan bagaimana Git menyimpan riwayat proyek secara modular dan efisien:

```
+-------------------------------------------------------------------------+
|                              OBJECT STORE                               |
+-------------------------------------------------------------------------+

 [COMMIT OBJECT]
 +-------------------------------------------------------+
 | commit 218                                            |
 | tree 8a5d3f...                                        |
 | parent a4f2c1...                                      |
 | author Linus Torvalds <torvalds@kernel.org> 170000000 |
 | committer Linus Torvalds <torvalds@kernel.org> 170000 |
 |                                                       |
 | feat: implementasi modul parser                       |
 +---------------------------+---------------------------+
                             |
                             v
 [ROOT TREE OBJECT]
 +-------------------------------------------------------+
 | tree 102                                              |
 | 100644 blob 4b825d...    README.md                    |
 | 040000 tree 7c1e9a...    src                          |
 +-----------------------------+-------------------------+
        |                      |
        |                      v
        |        [SUB-TREE OBJECT (src/)]
        |        +---------------------------------------+
        |        | tree 68                               |
        |        | 100644 blob d5e182...    main.py      |
        |        +-------------------+-------------------+
        v                            v
 [BLOB OBJECT]                [BLOB OBJECT]
 +-------------------+        +--------------------------+
 | blob 14           |        | blob 11                  |
 | # Dokumentasi     |        | print("OK")              |
 +-------------------+        +--------------------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah pembuktian langsung mekanisme *content hashing* Git menggunakan *standard shell tools*.

### 1. Inisialisasi Repositori
```bash
$ mkdir demo-internal && cd demo-internal
$ git init
Initialized empty Git repository in /path/to/demo-internal/.git/
```

### 2. Manual Hashing Menggunakan `git hash-object`
Ketikkan teks ke Git dan minta Git menghitung *hash*-nya tanpa membuat commit:
```bash
$ echo "arsitektur git" | git hash-object --stdin
22b0fdfbb21ba09990526e033e08f0a2d54cb50c
```

### 3. Memverifikasi dengan Pipeline SHA-1 Standar
Mari verifikasi bahwa kalkulasi Git murni mengikuti formula `type + " " + size + "\0" + content`:
```bash
$ payload="arsitektur git\n"
$ length=$(printf "$payload" | wc -c)
$ printf "blob %s\0%s" "$length" "$payload" | sha1sum
22b0fdfbb21ba09990526e033e08f0a2d54cb50c  -
```
*Hasil perhitungan matematis Linux shell identik dengan keluaran perintah bawaan Git.*

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kita akan melakukan eksperimen *plumbing*: membuat commit lengkap secara manual lapis demi lapis tanpa pernah menjalankan `git add` maupun `git commit`.

```bash
# 1. Bersihkan lingkungan & inisialisasi
rm -rf plumbing-lab && mkdir plumbing-lab && cd plumbing-lab
git init

# 2. Konfigurasi identitas repositori lokal
git config user.name "Sistem Insinyur"
git config user.email "engineer@enterprise.internal"

# 3. Buat berkas dan simpan langsung ke Object Database (Plumbing)
echo "console.log('Kernel Engine v1');" > app.js
BLOB_HASH=$(git hash-object -w app.js)
echo "Blob Hash: $BLOB_HASH"

# 4. Verifikasi bahwa objek fisik telah tertulis di direktori .git/objects
ls -la .git/objects/${BLOB_HASH:0:2}

# 5. Daftarkan berkas ke Index (Staging Area secara manual)
# Mode 100644 adalah berkas normal non-executable
git update-index --add --cacheinfo 100644 "$BLOB_HASH" app.js
git status
# Perhatikan: Git sekarang mendeteksi "Changes to be committed"

# 6. Tulis struktur pohon direktori (Tree Object) dari Index
TREE_HASH=$(git write-tree)
echo "Tree Hash: $TREE_HASH"

# 7. Bedah isi dari Tree Object tersebut
git cat-file -p "$TREE_HASH"
# Output akan menampilkan relasi mode berkas, nama berkas, dan Blob Hash

# 8. Buat objek Commit yang merujuk ke Tree Hash di atas
COMMIT_HASH=$(echo "chore: inisialisasi basis data sistem" | git commit-tree "$TREE_HASH")
echo "Commit Hash: $COMMIT_HASH"

# 9. Hubungkan cabang aktif (refs/heads/main) ke Commit Hash yang baru kita buat
git update-ref refs/heads/main "$COMMIT_HASH"
git checkout main

# 10. Periksa hasil akhir melalui perintah tingkat tinggi (Porcelain)
git log -p
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Pendekatan / Keputusan | Kelebihan | Kekurangan / Risiko |
| :--- | :--- | :--- |
| **SHA-1 vs SHA-256** | SHA-1 kompatibel secara universal di semua *server hosting* (GitHub, GitLab). Cepat diproses. | SHA-1 rentan terhadap serangan kolisi teoretis (*SHAttered*). Transisi ke SHA-256 membutuhkan flag khusus (`git init --object-format=sha256`) dan belum didukung luas oleh ekosistem CI/CD lama. |
| **Penyimpanan Objek Loose vs Packed (Packfiles)** | *Loose Objects* (1 berkas per 1 objek) membuat penulisan operasi baca/tulis cepat secara konkurensi. | Memboroskan inode pada sistem berkas (*filesystem exhaustion*). Perlu kompresi periodik (`git gc`) untuk menyatukannya ke berkas `.pack`. |
| **`git config --global` vs `--local`** | *Global* praktis; pengembang tidak perlu mengisi ulang nama/email setiap kali membuat repositori baru. | Berisiko membocorkan alamat email pribadi ke repositori korporat jika lupa menimpa konfigurasinya dengan *flag* `--local`. |
| **Git Plumbing vs Porcelain** | *Plumbing* memberi kontrol granular 100% untuk otomasi skrip internal dan integritas *tooling*. | Kurva pembelajaran tinggi; perintah berbahaya jika tidak memahami format metadata secara presisi. |

---

## SEKSI 11 — BEST PRACTICES

1. **Konfigurasi Nama Cabang Default Secara Eksplisit**:
   Mulai Git 2.28+, tetapkan nama cabang utama yang konsisten secara global:
   ```bash
   git config --global init.defaultBranch main
   ```
2. **Pisahkan Identitas Profil Berbasis Direktori**:
   Gunakan fitur `includeIf` di berkas `~/.gitconfig` untuk memisahkan konfigurasi kerja dan personal secara otomatis:
   ```ini
   # ~/.gitconfig
   [user]
       name = Budi Developer
       email = personal@domain.id

   [includeIf "gitdir:~/work/"]
       path = ~/.gitconfig-work
   ```
3. **Audit Status File Menggunakan Flag Singkat**:
   Gunakan format ringkas untuk memahami kondisi matriks *Index* vs *Working Directory*:
   ```bash
   git status -s
   # Menghasilkan kode dua kolom: Kolom 1 = Staging Area, Kolom 2 = Working Directory
   ```
4. **Verifikasi Integritas Objek**:
   Jalankan audit berkala pada repositori berukuran besar untuk memeriksa kemungkinan korupsi data internal:
   ```bash
   git fsck --full
   ```

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Inisialisasi Repositori Bersarang (*Nested Git Init*)
* **Masalah**: Menjalankan `git init` di dalam subdirektori dari sebuah repositori yang sudah aktif.
* **Dampak**: Repositori luar mendeteksi subdirektori sebagai *subproject/submodule* tanpa konfigurasi yang benar, menyebabkan berkas di dalamnya tidak terlacak.
* **Deteksi & Solusi**:
  ```bash
  find . -name ".git" -type d
  # Jika ada lebih dari satu, hapus direktori .git yang salah (di subfolder):
  rm -rf subfolder/.git
  ```

### 2. Kesalahan Atribusi Komit Akibat Variabel Lingkungan
* **Masalah**: Mengira `git config user.email` sudah benar, padahal terdapat variabel lingkungan `GIT_AUTHOR_EMAIL` atau `GIT_COMMITTER_EMAIL` yang aktif di terminal.
* **Dampak**: Commit tercatat dengan nama yang keliru. Git memprioritaskan *Environment Variables* di atas `git config`.
* **Solusi**:
  ```bash
  unset GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL
  ```

### 3. Mengedit Berkas `.git/objects/` Secara Manual
* **Masalah**: Mencoba menyunting berkas objek di direktori `.git/objects/` menggunakan *text editor* biasa.
* **Dampak**: Berkas rusak (*corrupt object*) karena berkas dikompresi dengan `zlib` dan *hash*-nya tidak lagi cocok dengan nama direktori/berkasnya.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Ekstraksi Dekompresi Objek Loose (Level: Pemula)
1. Buat folder baru, inisialisasi repositori Git.
2. Buat berkas `secret.txt` dengan isi `"KODE_RAHASIA_123"`.
3. Jalankan `git add secret.txt`.
4. Temukan *hash* objek di direktori `.git/objects/`.
5. Gunakan utilitas baris perintah sistem (seperti modul Python `zlib` atau alat bantu sistem) untuk mendekonstruksi berkas biner tersebut tanpa memanggil perintah `git cat-file`:
   ```bash
   python3 -c "import zlib; print(zlib.decompress(open('.git/objects/XX/YYYY...', 'rb').read()).decode('latin1'))"
   ```
6. **Validasi**: Pastikan teks `blob 16\0KODE_RAHASIA_123` muncul di layar terminal.

### Latihan 2: Rekonstruksi Pohon Komit Rusak (Level: Menengah)
1. Eksekusi skrip berikut untuk membuat repositori:
   ```bash
   mkdir broken-lab && cd broken-lab && git init
   echo "versi 1" > file.txt && git add file.txt && git commit -m "Commit 1"
   echo "versi 2" > file.txt && git add file.txt && git commit -m "Commit 2"
   ```
2. Hapus referensi cabang aktif secara paksa:
   ```bash
   rm .git/refs/heads/main
   ```
3. Uji dengan menjalankan `git log`. Hasilnya akan *error*: `fatal: your current branch 'main' does not have any commits yet`.
4. **Misi**: Cari *Commit Hash* terakhir menggunakan perintah `git fsck --lost-found`.
5. Pulihkan cabang `main` ke commit tersebut menggunakan `git update-ref refs/heads/main <HASH>`.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Di manakah Git menyimpan nama dari sebuah berkas dalam Object Database?**
   * A. Di dalam objek Blob bersama konten data.
   * B. Di dalam objek Tree yang membungkus Blob tersebut.
   * C. Di dalam berkas `.git/description`.
   * D. Di dalam *commit message*.
   * *Jawaban yang Benar:* **B**  
   * *Alasan:* Objek Blob murni hanya menyimpan konten byte data. Nama berkas dan hak akses (*file permission mode*) disimpan di dalam objek Tree.

2. **Jika terdapat dua berkas bernama `dokumen_lama.txt` dan `arsip_baru.txt` dengan isi konten byte yang 100% identik di-*staging*, berapa banyak objek Blob yang terbentuk di direktori `.git/objects/`?**
   * A. 2 Blob
   * B. 0 Blob (karena belum di-commit)
   * C. 1 Blob
   * D. 3 Blob
   * *Jawaban yang Benar:* **C**  
   * *Alasan:* Git bersifat *content-addressable*. Karena konten kedua berkas identik, keduanya menghasilkan SHA-1 *checksum* yang sama. Git tidak akan menduplikasi objek penyimpanan, melainkan menggunakan referensi *hash* tunggal yang sama di dalam Tree.

3. **Urutan hierarki prioritas konfigurasi Git dari prioritas tertinggi ke terendah adalah:**
   * A. System $\rightarrow$ Global $\rightarrow$ Local
   * B. Local $\rightarrow$ Global $\rightarrow$ System
   * C. Global $\rightarrow$ Local $\rightarrow$ Worktree
   * D. Local $\rightarrow$ System $\rightarrow$ Global
   * *Jawaban yang Benar:* **B**  
   * *Alasan:* Git mengevaluasi konfigurasi dari level terdekat (paling spesifik). Nilai pada `.git/config` (*Local*) akan menimpa `~/.gitconfig` (*Global*), dan *Global* akan menimpa konfigurasi `/etc/gitconfig` (*System*).

4. **Kapan sebuah objek Blob dituliskan secara fisik ke `.git/objects/`?**
   * A. Saat berkas disimpan di editor teks.
   * B. Saat perintah `git add` dieksekusi.
   * C. Saat perintah `git commit` dieksekusi.
   * D. Saat perintah `git push` dieksekusi.
   * *Jawaban yang Benar:* **B**  
   * *Alasan:* Perintah `git add` memproses konten berkas, menghitung *hash*, mengompresi payload via `zlib`, dan langsung menuliskan objek Blob ke *database*, seraya mencatat relasinya di berkas `.git/index`.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Dokumentasi Resmi Git**:
  * [Git Internals - Plumbing and Porcelain](https://git-scm.com/book/en/v2/Git-Internals-Plumbing-and-Porcelain)
  * [Git Internals - Git Objects](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects)
* **Buku Rekomendasi**:
  * Chacon, S., & Straub, B. (2014). *Pro Git* (2nd ed.). Apress. (Khususnya Bab 10: *Git Internals*).
* **Makalah / Spesifikasi Teknis**:
  * Torvalds, L. (2005). *Git Architecture and Design Principles*.
  * RFC 1950: *ZLIB Compressed Data Format Specification*.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

* Direktori `.git/` adalah keseluruhan repositori Git; direktori kerja (*working directory*) di luarnya hanyalah kanvas ekstraksi sementara.
* Git mengimplementasikan basis data kunci-nilai (*key-value store*), di mana kuncinya adalah *cryptographic hash* dan nilainya adalah konten yang dikompresi dengan `zlib`.
* Empat objek Git fundamental meliputi:
  * **Blob**: Isi berkas mentah.
  * **Tree**: Representasi struktur direktori dan metadata nama berkas.
  * **Commit**: Rekaman status berkas lengkap dengan riwayat hierarki (*parent*) dan metadata penulis.
  * **Annotated Tag**: Penanda permanen yang mengarah ke objek lain.
* Perubahan status berkas bergerak secara deterministik:
  $$\text{Working Directory} \xrightarrow{\text{git add}} \text{Index (Blob terbuat)} \xrightarrow{\text{git commit}} \text{Repository (Tree \& Commit terbuat)}$$
* Konfigurasi Git bekerja secara bertingkat: *System* $\rightarrow$ *Global* $\rightarrow$ *Local*, di mana konfigurasi *Local* selalu memiliki prioritas tertinggi.

---

## SEKSI 17 — GLOSARIUM

* **Content-Addressable Storage**: Mekanisme penyimpanan di mana data diakses berdasarkan konten datanya (melalui nilai *hash*), bukan berdasarkan lokasi penyimpanan fisik atau nama berkasnya.
* **Plumbing Commands**: Perintah Git level rendah (*low-level*) yang dirancang untuk bekerja langsung dengan objek dan arsitektur internal Git (misal: `git hash-object`, `git cat-file`).
* **Porcelain Commands**: Perintah Git level tinggi (*user-facing*) yang ramah pengguna (misal: `git add`, `git commit`, `git checkout`).
* **Zlib**: Pustaka kompresi data perangkat lunak yang digunakan Git untuk mengompresi setiap objek sebelum disimpan di disk.
* **Loose Object**: Objek Git yang disimpan secara individual sebagai satu berkas terkompresi tunggal dalam direktori `.git/objects/`.
* **Index / Staging Area**: Berkas biner di `.git/index` yang bertindak sebagai gerbang penyaring antara direktori kerja dan riwayat commit.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Poin Penekanan Materi**:
  * Jangan biarkan peserta melanjutkan ke konsep *branching* sebelum mereka benar-benar memahami bahwa sebuah *branch* hanyalah berkas teks sederhana berisi 40 karakter *hash* komit di `.git/refs/heads/`.
  * Demonstrasikan pembongkaran objek menggunakan `git cat-file -t <hash>` (untuk melihat tipe) dan `git cat-file -p <hash>` (untuk mencetak konten). Ini adalah alat bantu visual terbaik bagi peserta.
* **Titik Kebingungan Umum Peserta**:
  * Peserta sering bingung mengapa mengganti nama berkas tanpa mengubah isinya akan menghasilkan *hash* Blob yang persis sama. Tekankan kembali bahwa Blob **tidak** menyimpan nama berkas; perubahan nama berkas hanya memodifikasi objek *Tree*.
* **Setup Lab**:
  * Pastikan peserta tidak menjalankan perintah lab di folder yang disinkronkan dengan layanan awan otomatis (seperti OneDrive, iCloud, atau Dropbox), karena sistem sinkronisasi berkas eksternal dapat mengunci berkas sementara Git di dalam direktori `.git/` sehingga menimbulkan kesalahan I/O.

---

## SEKSI 19 — CHANGELOG & VERSI

| Versi | Tanggal Rilis | Penulis / Reviewer | Deskripsi Perubahan |
| :--- | :--- | :--- | :--- |
| `1.0.0` | 2024-03-30 | Senior Technical Curriculum Architect | Rilis awal kurikulum: Inisialisasi, Konfigurasi, dan Siklus Hidup Objek Git. |
| `1.1.0` | 2024-10-15 | Tim Asesmen Kurikulum | Penambahan sub-bab komparasi SHA-1 vs SHA-256 dan latihan *plumbing reconstruction*. |

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `GIT-CORE-0101` — Pengenalan Sistem Kontrol Versi Terdistribusi dan Filosofi Git.
* **Modul Saat Ini**: `GIT-CORE-0201` — Inisialisasi, Konfigurasi, & Siklus Hidup Objek Git.
* **Modul Berikutnya**: `GIT-CORE-0202` — Mekanika Percabangan (Branching Mechanics), Pointer HEAD, dan Algoritma Penggabungan (Merge).