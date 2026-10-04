# Bab 03 Module 01: Inspeksi Riwayat Proyek dan Analisis Perubahan Kode (`git log`, `git diff`, `git show`)

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta mampu:
*   Menganalisis riwayat perubahan kode sumber secara mendalam menggunakan variasi format flag pada `git log`.
*   Mengevaluasi perbedaan delta baris (*line-by-line diff*) antara *working directory*, *staging area* (index), dan *commit history* menggunakan `git diff`.
*   Mengisolasi dan mengaudit metadata serta payload konten dari commit spesifik menggunakan `git show`.
*   Melakukan penelusuran regresi (*regression tracing*) secara sistematis untuk kebutuhan *root-cause analysis* (RCA) di lingkungan produksi.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, Anda harus memahami:
*   Arsitektur tiga area Git: *Working Directory*, *Staging Area* (*Index*), dan *Repository* (*Commit History*).
*   Operasi fundamental: `git init`, `git add`, `git commit`, dan `git status`.
*   Struktur *Object Database* Git dasar (Blob, Tree, dan Commit object berformat SHA-1/SHA-256).
*   Navigasi antarmuka baris perintah (*terminal CLI*) dan pengoperasian dasar pager `less`.

---

### 3. Concept
Secara arsitektural, Git menyimpan riwayat proyek bukan sebagai serangkaian berkas delta mentah (*delta storage* linier), melainkan sebagai graf asiklik terarah (*Directed Acyclic Graph* atau DAG) yang terdiri dari serangkaian *commit snapshot*. 

```
               [Commit: C3] (HEAD -> main)
                    |
              parent pointer
                    v
               [Commit: C2]
                    |
              parent pointer
                    v
               [Commit: C1] (Root)
```

Setiap objek *commit* memiliki metadata permanen:
*   **Tree Hash**: Pointer ke *tree object* yang merepresentasikan kondisi pohon direktori pada detik commit dibuat.
*   **Parent Pointer(s)**: Hash dari satu atau lebih commit pendahulu.
*   **Author & Committer**: Identitas pengembang beserta *timestamp* zona waktu presisi.
*   **Commit Message**: Dokumentasi kontekstual perubahan.

Ketika mengeksekusi inspeksi:
*   `git log` bertindak sebagai traversal engine pada DAG. Ia menelusuri rantai *parent pointer* dimulai dari titik referensi saat ini (`HEAD`) mundur ke arah commit awal (*root*), merender jejak metadata yang ditemui.
*   `git diff` menjalankan algoritma komparasi teks (secara *default* variasi dari algoritma Myers) yang membandingkan dua *tree object*, atau *tree* terhadap *index*, atau *index* terhadap *working directory*. Mesin ini mengidentifikasi operasi penambahan (*addition*), penghapusan (*deletion*), atau modifikasi blok byte.
*   `git show` mengekstrak objek Git tunggal berdasarkan referensi hash, menguraikan metadata header commit, dan secara otomatis mengeksekusi komparasi *diff* terhadap *immediate parent*-nya.

---

### 4. Why
Dalam rekayasa perangkat lunak skala produksi, waktu membaca dan menginvestigasi kode melampaui waktu penulisan kode baru dengan rasio sekitar 10:1. Memahami riwayat modifikasi secara presisi adalah instrumen mitigasi risiko kritis:
*   **Incident Response & RCA**: Ketika layanan *down* pasca-deployment, tim SRE/DevOps harus mengidentifikasi commit pemicu kegagalan (*faulty commit*) dalam hitungan detik.
*   **Code Review Verification**: Memastikan perubahan yang dinaikkan ke lingkungan pengujian murni hanya mencakup cakupan tugas tiket tanpa ada berkas konfigurasi lokal atau rahasia (*credentials*) yang bocor.
*   **Audit Trail Compliance**: Industri teregulasi (fintech, kesehatan) menuntut visibilitas penuh: siapa mengubah baris kode apa, kapan, dan atas dasar konteks fungsional apa.

---

### 5. What
Komponen kunci dalam ekosistem inspeksi Git mencakup:

*   **`git log`**: Utilitas penelusuran riwayat commit.
    *   `--oneline`: Merangkum output menjadi 7 karakter hash awal dan subjek commit per baris.
    *   `--stat`: Menampilkan metrik kuantitatif perubahan (jumlah berkas, baris ditambah/dihapus).
    *   `-p` atau `--patch`: Menampilkan representasi diff patch lengkap bersama riwayat log.
    *   `--graph`: Memvisualisasikan percabangan dan penggabungan topologi DAG menggunakan karakter ASCII.
*   **`git diff`**: Utilitas perbandingan delta.
    *   `git diff`: Menampilkan perbedaan antara *Working Directory* dan *Staging Area* (perubahan yang belum di-`add`).
    *   `git diff --staged` (atau `--cached`): Menampilkan perbedaan antara *Staging Area* dan commit terakhir (`HEAD`).
    *   `git diff <commit_A> <commit_B>`: Menampilkan delta absolut antara dua status riwayat yang berbeda.
*   **`git show`**: Utilitas inspeksi atomik.
    *   `git show <commit_id>`: Menginspeksi payload lengkap dari sebuah commit tunggal.
    *   `git show <commit_id>:<file_path>`: Mengambil snapshot isi berkas pada commit tertentu tanpa *checkout*.

---

### 6. How
Alur kerja sistematis audit dan inspeksi kode lokal:

```
[Working Directory] 
       │
   (Modifikasi)
       │
       ├──> $ git diff                 (Periksa apa yang belum di-stage)
       │
       v
[Staging Area / Index]
       │
       ├──> $ git diff --staged        (Verifikasi apa yang akan masuk commit)
       │
       v
[Commit History / HEAD]
       │
       ├──> $ git log --oneline -n 5   (Lihat ringkasan 5 commit terakhir)
       ├──> $ git show <hash>          (Bedah satu commit mencurigakan)
       └──> $ git log -S "query"       (Lacak kapan string spesifik dimodifikasi)
```

1.  **Langkah 1: Deteksi Modifikasi Belum Tersimpan**
    Jalankan `git diff` untuk meninjau perubahan yang berada di *Working Directory* sebelum memasukkannya ke *Index*.
2.  **Langkah 2: Validasi Pre-commit**
    Setelah menjalankan `git add`, jalankan `git diff --staged`. Ini adalah *quality gate* terakhir sebelum mutasi commit dicatat ke dalam database objek.
3.  **Langkah 3: Traversal Riwayat**
    Gunakan `git log --graph --oneline --decorate --all` untuk memahami posisi `HEAD` terhadap cabang lain di topologi Git.
4.  **Langkah 4: Analisis Spesifik Target**
    Identifikasi hash target dari `git log`, lalu eksekusi `git show <hash>` untuk meninjau payload patch dan metadata author.

---

### 7. Analogy
Bayangkan sebuah repositori Git sebagai sistem audit gedung bertingkat dengan keamanan tinggi:
*   *Commit* adalah berkas foto snapshot 360 derajat dari setiap ruangan di gedung pada waktu tertentu, lengkap dengan stempel waktu dan tanda tangan petugas.
*   **`git log`** adalah buku jurnal satpam di pintu depan. Anda membolak-balik halaman buku untuk membaca: "Pukul 10:00 Alice menutup jendela", "Pukul 11:00 Bob memasang alarm".
*   **`git diff`** adalah teknologi pemindai pembanding dua foto (*photo comparison software*). Anda memasukkan foto kondisi ruangan pukul 10:00 dan foto pukul 11:00, lalu layar menyorot kursi mana yang bergeser 5 cm dengan garis merah (lama) dan hijau (baru).
*   **`git show`** adalah perintah untuk membuka satu amplop laporan audit tertentu: Anda menarik map laporan investigasi pukul 11:00, melihat siapa petugasnya, catatannya, beserta foto perbandingan sebelum dan sesudah kejadian tersebut.

---

### 8. Diagram
Diagram alur perbandingan delta pada area kerja Git:

```
+-------------------------------------------------------------------------+
|                              WORKING DIRECTORY                          |
|                       (Modifikasi berkas fisik aktif)                   |
+-------------------------------------------------------------------------+
       │                                                   ▲
       │                                                   │
       │                   git diff                        │
       │     (Bandingkan perubahan belum di-stage)         │
       ▼                                                   │
+-------------------------------------------------------------------------+
|                            STAGING AREA (INDEX)                         |
|                    (Snapshot persiapan commit berikutnya)                |
+-------------------------------------------------------------------------+
       │                                                   ▲
       │                                                   │
       │               git diff --staged                   │
       │     (Bandingkan staged vs commit terakhir)        │
       ▼                                                   │
+-------------------------------------------------------------------------+
|                           LOCAL REPOSITORY (HEAD)                       |
|                      (Database Commit DAG tersimpan)                     |
+-------------------------------------------------------------------------+
       │
       ├──────────────────────────────┬─────────────────────────────┐
       ▼                              ▼                             ▼
  $ git log                    $ git show <hash>             $ git diff H1 H2
(Traversal DAG)             (Bedah satu commit)           (Bandingkan dua snapshot)
```

---

### 9. Simple Example
Skenario: Membuat repositori, memodifikasi berkas, dan menginspeksi perbedaan status.

```bash
# Inisialisasi repositori
mkdir git-inspection-demo && cd git-inspection-demo
git init

# Buat berkas awal
echo "console.log('App Initialized');" > app.js
git add app.js
git commit -m "feat: initialize application"

# Tambahkan perubahan di working directory
echo "console.log('Database Connected');" >> app.js

# Inspeksi perubahan yang belum di-stage
git diff
```

Output terminal dari `git diff`:
```diff
diff --git a/app.js b/app.js
index f30f617..a2f9b81 100644
--- a/app.js
+++ b/app.js
@@ -1 +1,2 @@
 console.log('App Initialized');
+console.log('Database Connected');
```

Stage perubahan tersebut, lalu jalankan verifikasi stage:
```bash
git add app.js
git diff            # Output kosong, karena tidak ada perbedaan Working Tree vs Index
git diff --staged   # Output menampilkan delta Index vs HEAD
```

---

### 10. Practical Example
Skenario: Konfigurasi microservice pembayaran yang mengalami bug fungsional. Anda perlu mengaudit histori menggunakan format log tingkat lanjut dan menganalisis patch commit.

```bash
# 1. Menampilkan log ringkas dengan relasi graf dan penanda referensi
git log --graph --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --abbrev-commit

# 2. Mencari commit mana yang mengubah baris yang memuat variabel 'PAYMENT_GATEWAY_TIMEOUT'
git log -S "PAYMENT_GATEWAY_TIMEOUT" -p

# 3. Menampilkan rangkuman statistik commit dalam rentang 3 commit terakhir
git log -n 3 --stat

# 4. Melakukan komparasi langsung antara dua commit spesifik
# (Asumsikan hash commit: a1b2c3d dan e5f6g7h)
git diff a1b2c3d..e5f6g7h -- src/config/payment.ts

# 5. Menginspeksi metadata dan payload penuh dari satu commit target
git show e5f6g7h
```

Output nyata pada terminal untuk `git show e5f6g7h`:
```text
commit e5f6g7h890abcdef1234567890abcdef12345678
Author: Jane Doe <jane.doe@enterprise.com>
Date:   Mon May 20 14:32:01 2024 +0700

    fix(payment): increase gateway timeout threshold

    Production metrics indicated false-positive timeouts under heavy network load.

diff --git a/src/config/payment.ts b/src/config/payment.ts
index d8a11bc..44b209e 100644
--- a/src/config/payment.ts
+++ b/src/config/payment.ts
@@ -10,3 +10,3 @@ export const paymentConfig = {
   retryCount: 3,
-  PAYMENT_GATEWAY_TIMEOUT: 2000,
+  PAYMENT_GATEWAY_TIMEOUT: 5000,
 };
```

---

### 11. Real World Example
**Kasus**: *Outage* di Platform E-Commerce Global (Investigasi Regresi).

**Konteks**: Layanan *Checkout Service* tiba-tiba melempar error `500 Internal Server Error` untuk semua transaksi dengan mata uang asing sesaat setelah deployment rilis `v2.14.0`.

**Investigasi Berbasis Git**:
1. Tim insinyur membandingkan rilis stabil sebelumnya (`v2.13.9`) dengan tag bermasalah (`v2.14.0`) secara terarah ke folder mata uang:
   ```bash
   git diff v2.13.9..v2.14.0 -- services/currency/
   ```
2. Dari hasil *diff*, ditemukan ada 12 commit yang menyentuh direktori tersebut. Untuk melacak baris logika spesifik yang memanipulasi konversi mata uang, teknisi menjalankan teknik *pickaxe search*:
   ```bash
   git log -S "convertRate" --since="2 days ago" -p services/currency/converter.go
   ```
3. Git mengisolasi commit `7c9a12b`. Menggunakan `git show 7c9a12b`, tim menemukan adanya refaktorisasi operasi pembagian desimal yang secara tidak sengaja memicu *division by zero* ketika kurs mata uang belum ter-cache.
4. **Hasil**: Akar masalah diidentifikasi dalam 4 menit tanpa perlu melakukan *reverse-engineering* pada *binary artifact* kontainer, memungkinkan proses `git revert` instan untuk mitigasi.

---

### 12. Trade-offs

| Parameter | Evaluasi Analisis |
| :--- | :--- |
| **Advantages** | Kemampuan offline total (seluruh riwayat tersimpan lokal di `.git`), audit kecepatan tinggi langsung di CLI, akurasi pelacakan per karakter via delta formatting. |
| **Disadvantages** | Tidak intuitif untuk diff berkas biner (gambar, berkas compiled `.jar`/`.exe`), memerlukan pemahaman sintaks flag yang padat, output bisa sangat panjang (*overwhelming*) pada commit skala besar. |
| **Complexity** | Rendah untuk inspeksi satu baris (`--oneline`), namun meningkat secara eksponensial saat melibatkan *merge commits* dengan banyak *parent* (*octopus merges*). |
| **Performance** | Sangat cepat untuk operasi log standar. Namun, operasi `git log -S` atau `git diff` pada repositori raksasa (*monorepo*) tanpa pembatasan path (*pathspec*) dapat memakan I/O disk dan komputasi CPU intensif. |
| **Cost** | Memerlukan ruang penyimpanan lokal untuk repositori penuh (metadata objek) dibandingkan hanya mengunduh shallow clone (`depth=1`). |

---

### 13. When To Use
*   Sebelum menjalankan `git commit`, gunakan `git diff --staged` untuk memastikan tidak ada artefak build, token rahasia, atau log debug yang tidak sengaja terikut.
*   Saat melakukan *peer review* lokal sebelum melakukan *push* ke remote repository.
*   Saat melakukan investigasi insiden produksi untuk merekonstruksi urutan kejadian modifikasi kode sumber.
*   Ketika merilis versi baru, gunakan `git log <tag_lama>..<tag_baru> --oneline` untuk mengompilasi draf *Changelog* atau *Release Notes*.

---

### 14. When NOT To Use
*   **Audit Berkas Biner Besar**: Jangan gunakan `git diff` teks biasa pada berkas gambar, audio, atau PDF terkompilasi karena hanya akan menghasilkan teks sampah (*binary files differ*). Gunakan *LFS extension diff tools*.
*   **Audit Riwayat Panjang di Proyek Berskala Terabita (Monorepo Raksasa)**: Hindari menjalankan `git log` tanpa argumen pembatas (seperti `-n`, `--since`, atau *pathspec*), karena dapat menyebabkan *memory spike* pada mesin lokal.
*   **Pencarian Kode Statis Saat Ini**: Jangan gunakan `git log` untuk mencari kode yang sedang aktif saat ini; gunakan `git grep` atau ripgrep yang jauh lebih cepat karena tidak perlu memindai seluruh DAG.

---

### 15. Common Mistakes
*   **Tertukar antara `git diff` dan `git diff --staged`**: Mengira seluruh perubahan telah siap di-commit saat melihat output `git diff` kosong, padahal perubahan sudah dimasukkan ke index melalui `git add` dan belum diperiksa menggunakan `--staged`.
*   **Terjebak di UI Pager (`less`)**: Panik saat terminal "membeku" setelah menjalankan `git log`. (Solusi: Tekan `q` untuk keluar dari pager, `f` atau `Space` untuk maju satu halaman, `/` untuk mencari kata).
*   **Mengabaikan Konteks Spasi (*Whitespace Noise*)**: Meninjau diff yang tercemar oleh perubahan *indentation* (spasi vs tab). Solusi: Gunakan flag `-w` atau `--ignore-all-space` agar Git fokus murni pada modifikasi logika.
*   **Membandingkan Arah Diff Terbalik**: Mengeksekusi `git diff commitA..commitB` secara terbalik, sehingga penghapusan kode tampak sebagai penambahan kode, dan sebaliknya. Ingat: parameter pertama adalah titik mula (*source*), parameter kedua adalah tujuan (*target*).

---

### 16. Best Practices (Production Checklist)
- [ ] Konfigurasikan alias Git global untuk log visual (`git config --global alias.lg "log --graph --oneline --decorate --all"`).
- [ ] Terapkan kebiasaan menjalankan `git diff --staged` tepat sebelum memanggil editor `git commit`.
- [ ] Batasi pencarian log menggunakan *pathspec* spesifik jika bekerja di repositori besar: `git log -- path/to/module/`.
- [ ] Selalu sertakan flag `--stat` saat meninjau commit orang lain untuk mendapatkan gambaran umum volume perubahan sebelum membedah detail logika baris per baris.
- [ ] Gunakan flag `--word-diff` saat membedah modifikasi baris kode yang panjang guna menyorot mutasi kata spesifik alih-alih seluruh baris penuh.

---

### 17. Troubleshooting

#### Masalah 1: Output `git diff` Menampilkan Seluruh Isi Berkas Berubah Karena Masalah Akhir Baris (CRLF vs LF)
*Gejala*: Seluruh baris di berkas ditandai merah (terhapus) dan digantikan hijau (ditambahkan), padahal logika kode sama.
*Penyebab*: Inkonsistensi karakter akhir baris Windows (`\r\n`) dan POSIX/Linux (`\n`).
*Solusi*: Abaikan perubahan carriage return saat membandingkan:
```bash
git diff --ignore-space-at-eol
```
Konfigurasikan normalisasi secara permanen pada repositori melalui `.gitattributes`:
```text
* text=auto
```

#### Masalah 2: Log Mengisi Seluruh Layar dan Terminal Menolak Input Perintah Baru
*Gejala*: Muncul penanda `(END)` atau `:` di pojok kiri bawah layar; perintah terminal standar tidak bisa diketikkan.
*Penyebab*: Output `git log` diteruskan ke pager internal sistem (`less`).
*Solusi*: Tekan tombol `q` pada keyboard untuk memutus aliran pager dan mengembalikan kendali ke shell.

---

### 18. Exercise
Jalankan skenario latihan berikut di terminal lokal Anda:

1.  Buat direktori baru bernama `git-lab-history` dan inisialisasi repositori Git.
2.  Buat berkas `calc.py` dengan isi:
    ```python
    def add(a, b):
        return a + b
```
3.  Commit berkas tersebut dengan pesan `"feat: add addition function"`.
4.  Modifikasi `calc.py` menjadi:
    ```python
    def add(a, b):
        # Addition logic
        return a + b

    def sub(a, b):
        return a - b
```
5.  Gunakan `git diff` untuk melihat modifikasi di *working directory*.
6.  Pindahkan *hanya* fungsi `sub` ke status staged menggunakan *interactive staging* `git add -p` (pilih `s` untuk split hunk, lalu `y` untuk potongan fungsi `sub` dan `n` untuk komentar pada fungsi `add`).
7.  Verifikasi bahwa `git diff` menampilkan penambahan komentar, sedangkan `git diff --staged` menampilkan implementasi fungsi `sub`.
8.  Commit perubahan staging tersebut dengan pesan `"feat: add subtraction function"`.
9.  Gunakan `git log --oneline -n 2` untuk memverifikasi dua commit yang ada di repositori.

---

### 19. Challenge
Analisis Forensik Repositori Terkompromi:

Telah terjadi kebocoran kredensial API Key pada sebuah proyek dummy. Anda diminta mensimulasikan dan membongkar jejak kebocoran tersebut:

1.  Buat 3 commit berturut-turut pada berkas `server.js`.
    *   Commit 1: Inisialisasi server dasar.
    *   Commit 2: Memasukkan baris `const STRIPE_SECRET = "sk_live_98374982347293847";` di tengah berkas.
    *   Commit 3: Mengubah baris tersebut menjadi `const STRIPE_SECRET = process.env.STRIPE_SECRET;` (mencoba menghapus jejak).
2.  **Misi Tantangan**: 
    Tanpa membuka berkas `server.js` di teks editor, temukan hash commit persis yang memasukkan string `"sk_live_98374982347293847"` menggunakan satu perintah terpadu Git.
3.  Ekstrak tanggal, nama penulis, dan pesan commit dari commit pelanggar tersebut menggunakan `git show` yang difilter hanya menampilkan metadatanya saja tanpa baris diff.

*Kunci Jawaban Tantangan*:
```bash
# Identifikasi commit menggunakan pickaxe search:
git log -S "sk_live_98374982347293847" --oneline

# Ekstraksi metadata tanpa diff:
git show -s --format="Author: %an%nDate: %ad%nMessage: %s" <COMMIT_HASH_DITEMUKAN>
```

---

### 20. Summary
*   **`git log`** menavigasi topologi DAG Git ke arah belakang (*backward traversal* dari commit referensi) untuk merekonstruksi riwayat pengembangan.
*   **`git diff`** menghitung perbedaan delta antar area status sistem (*Working Tree*, *Index*, *Commits*) dengan memanfaatkan algoritma perbandingan baris.
*   **`git diff` default** membandingkan *Working Directory* vs *Index*; sedangkan **`git diff --staged`** membandingkan *Index* vs *HEAD*.
*   **`git show`** menggabungkan ekstraksi metadata commit dan eksekusi komparasi patch terhadap *immediate parent*-nya untuk analisis terisolasi yang mendalam.
*   Kombinasi flag seperti `-S` (*pickaxe search*), `--stat`, dan visualisasi topologi graf `--graph` merupakan fondasi mutlak bagi *software engineer* dalam melakukan audit kode dan resolusi insiden secara terukur di skala produksi.