# Bab 01: Dasar-Dasar Version Control & Arsitektur Git
## Module 01: Pengenalan Version Control System (VCS) dan Fundamental Git

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
*   **Menganalisis** perbedaan fundamental antara sistem manajemen berkas konvensional (arsip manual), Centralized Version Control Systems (CVCS), dan Distributed Version Control Systems (DVCS).
*   **Mengonfigurasi** identitas dasar dan lingkungan kerja Git pada level global maupun lokal dengan tepat.
*   **Membedakan** tiga status utama berkas (*Working Directory*, *Staging Area/Index*, dan *Git Directory/Repository*).
*   **Mengeksekusi** inisialisasi repositori lokal baru serta merekam jejak perubahan (*commit*) pertama secara deterministik.
*   **Mengidentifikasi** integritas data Git berbasis SHA-1/SHA-256 hash serta mekanisme *snapshot* vs *delta-based storage*.

---

### 2. Conceptual Overview
**Version Control System (VCS)** adalah sistem perangkat lunak yang merekam riwayat perubahan sekumpulan berkas dari waktu ke waktu sehingga pengguna dapat menginspeksi, membandingkan, atau memulihkan versi terdahulu secara akurat.

Git adalah sistem kontrol versi terdistribusi (*Distributed VCS/DVCS*) yang dirancang oleh Linus Torvalds pada tahun 2005. Berbeda dengan model sentralistis (seperti SVN atau CVS) di mana klien hanya mengambil *snapshot* berkas tertentu dari server pusat, setiap salinan (*clone*) dari repositori Git merupakan repositori yang lengkap dengan riwayat penuh (*full redundancy*).

Pendekatan fundamental Git terletak pada bagaimana ia memperlakukan data:
*   Sistem lawas memperlakukan data sebagai sekumpulan berkas dasar ditambah akumulasi perbedaan perubahan format teks (*delta-based version control*).
*   Git memperlakukan data sebagai serangkaian **foto instan (*snapshots*)** dari sistem berkas mini. Setiap kali Anda melakukan perubahan dan merekamnya (*commit*), Git mengambil foto dari seluruh berkas yang ada pada saat itu dan menyimpan referensi ke *snapshot* tersebut. Jika suatu berkas tidak berubah, Git tidak menduplikasi berkas tersebut, melainkan menunjuk langsung ke berkas identik yang sudah disimpan sebelumnya.

---

### 3. Why It Matters
Manajemen proyek perangkat lunak tanpa VCS menyebabkan berbagai kegagalan operasional:
1.  **Anti-Pattern "Folder Versi Manual":** Penamaan direktori seperti `project_final`, `project_final_v2`, `project_final_fix_beneran.zip` bersifat rawan eror (*error-prone*), tidak memiliki jejak audit log, dan memboroskan ruang penyimpanan.
2.  **Kurangnya *Traceability*:** Tanpa VCS, tidak mungkin mengetahui secara pasti siapa yang mengubah sebaris kode tertentu, kapan perubahan dibuat, dan mengapa perubahan tersebut dilakukan (*blame/annotation failure*).
3.  **Hambatan Kolaborasi (*Merge Conflicts* Tanpa Panduan):** Ketika dua *engineer* mengedit berkas yang sama secara simultan, mekanisme penggabungan manual berisiko tinggi menimpa pekerjaan pihak lain secara tidak sengaja (*silent overwrite*).
4.  **Ketiadaan *Rollback Strategy*:** Ketika kode cacat masuk ke lingkungan produksi (*production*), waktu pemulihan (*Mean Time to Recovery / MTTR*) menjadi sangat lama karena hilangnya titik referensi stabil terdahulu.

---

### 4. What It Is
Komponen dasar arsitektur Git terdiri dari tiga status berkas (*The Three States*) dan satu area penyimpanan jarak jauh opsional:

*   **Working Directory (Working Tree):** Salinan lokal satu versi tertentu dari proyek yang diekstraksi dari basis data Git ke disk lokal untuk dilihat dan diedit.
*   **Staging Area (Index):** Berkas biner sederhana (biasanya tersimpan di `.git/index`) yang bertindak sebagai area persiapan. Tempat ini mencatat berkas mana saja yang perubahannya akan dimasukkan ke dalam rekaman snapshot berikutnya.
*   **Git Directory (Repository):** Tempat penyimpanan permanen metadata dan basis data objek (*Object Database*) untuk proyek Anda. Direktori tersembunyi `.git/` ini adalah inti Git yang disalin saat melakukan operasi `clone`.
*   **HEAD:** Pointer penunjuk yang merujuk pada cabang (*branch*) lokal atau *commit* aktif yang sedang dikerjakan di *Working Directory*.
*   **Blob, Tree, Commit (Git Objects):** Struktur data internal Git. *Blob* menyimpan konten berkas, *Tree* menyimpan struktur direktori dan nama berkas, serta *Commit* menyimpan metadata (penulis, pesan, stempel waktu, dan pointer ke *Tree*).

---

### 5. How It Works
Alur kerja standar Git mengikuti siklus deterministik:

1.  **Modifikasi Berkas:** Berkas diedit di dalam *Working Directory*. Berkas ini kini berstatus *Modified*.
2.  **Pementasan (*Staging*):** Anda menjalankan perintah untuk menandai berkas yang akan disimpan ke *snapshot* berikutnya. Git menghitung *hash* konten berkas, menulis berkas ke basis data objek sebagai *blob*, lalu mencatat metadata ke berkas `.git/index`. Berkas kini berstatus *Staged*.
3.  **Komit (*Commit*):** Git membaca isi *Staging Area*, membuat objek *Tree* permanen, membuat objek *Commit* yang merujuk pada objek *Tree* tersebut beserta *hash* *commit* induk (*parent commit*), dan memperbarui pointer `HEAD`. Berkas kini berstatus *Committed*.

Integritas data dijamin melalui kriptografi hashing. Setiap objek diberi label menggunakan Secure Hash Algorithm (standar default SHA-1 menghasilkan string heksadesimal 40 karakter; versi terbaru mendukung SHA-256). Setiap perubahan mikroskopis pada berkas akan menghasilkan nilai *hash* yang sepenuhnya berbeda, mencegah korupsi data tanpa terdeteksi.

---

### 6. Architecture Diagram

Berikut visualisasi aliran data antar tiga area internal Git beserta repositori remote:

```text
+-------------------------------------------------------------------------------+
|                                  LOCAL MACHINE                                |
|                                                                               |
|  +-------------------+      +-------------------+      +-------------------+  |
|  |                   |      |                   |      |                   |  |
|  | Working Directory |      |   Staging Area    |      |   Git Directory   |  |
|  |  (Working Tree)   |      |      (Index)      |      |   (Repository)    |  |
|  |                   |      |                   |      |      [.git/]      |  |
|  +---------+---------+      +---------+---------+      +---------+---------+  |
|            |                          |                          |            |
|            |        git add           |                          |            |
|            +------------------------->+                          |            |
|            |                          |       git commit         |            |
|            |                          +------------------------->+            |
|            |                                                     |            |
|            |                    git checkout / restore           |            |
|            |<----------------------------------------------------+            |
|            |                                                     |            |
+------------+-----------------------------------------------------+------------+
                                                                   |
                                          git push                 |  git fetch /
                                       +---------------------------+  git pull
                                       |                           |
                                       v                           |
                      +---------------------------------+          |
                      |                                 |          |
                      |      Remote Repository          +----------+
                      |      (GitHub / GitLab)          |
                      |                                 |
                      +---------------------------------+
```

---

### 7. Simple Example
Inisialisasi dasar dan konfigurasi identitas melalui Terminal:

```bash
# 1. Konfigurasi identitas global pengembang
git config --global user.name "John Doe"
git config --global user.email "johndoe@example.com"

# 2. Konfigurasi branch default global menjadi 'main'
git config --global init.defaultBranch main

# 3. Validasi konfigurasi
git config --list --show-origin
```

---

### 8. Practical Real-World Example
Berikut skenario nyata: Membangun repositori baru untuk proyek microservice berbasis Node.js bernama `service-payment`.

```bash
# Membuat direktori dan masuk ke dalamnya
mkdir service-payment && cd service-payment

# Menginisialisasi repositori Git lokal
git init

# Output:
# Initialized empty Git repository in /home/user/service-payment/.git/

# Membuat berkas entry point awal
echo "console.log('Payment Engine v1.0.0 Initiated');" > index.js

# Mengecek status working directory saat ini
git status

# Menambahkan file ke Staging Area (Index)
git add index.js

# Melakukan commit dengan pesan terstruktur
git commit -m "feat: initialize payment engine core entrypoint"

# Melihat log riwayat transaksi Git
git log --oneline
```

---

### 9. Step-by-Step Implementation Guide
Langkah mendalam menjalankan alur siklus hidup berkas:

1.  **Periksa Status Awal:**
    ```bash
    git status
    ```
    *Output:* Menunjukkan branch aktif dan mengonfirmasi "nothing to commit, working tree clean".

2.  **Buat Berkas Konfigurasi Lingkungan:**
    ```bash
    cat <<EOF > config.json
    {
      "env": "development",
      "port": 8080
    }
    EOF
    ```

3.  **Analisis Status Untracked:**
    Jalankan kembali `git status`. Berkas `config.json` akan berwarna merah dan berada di bawah bagian `Untracked files`. Artinya berkas ada di *Working Directory*, namun Git belum melacaknya di *Index*.

4.  **Pindahkan Berkas ke Staging Area:**
    ```bash
    git add config.json
    ```

5.  **Verifikasi Penambahan Staging Area:**
    Jalankan `git status`. Berkas `config.json` sekarang berada di bawah `Changes to be committed` (berwarna hijau).

6.  **Eksekusi Snapshot (Commit):**
    ```bash
    git commit -m "chore: add default development configuration schema"
    ```

7.  **Inspeksi Struktur Log Detail:**
    ```bash
    git log --format=fuller
    ```
    Perhatikan atribut `Author`, `Commit`, `CommitDate`, dan string `commit hash` unik.

---

### 10. Edge Cases & Boundary Conditions
1.  **Nested `.git` Directories:** Jika Anda menjalankan `git init` di dalam sub-folder dari repositori yang sudah ada tanpa konfigurasi *Submodule*, Git akan mengabaikan direktori tersebut atau menghasilkan *submodule warning* terputus. Hindari membuat repositori di dalam repositori kecuali secara sadar mendesain Git Submodules/Subtrees.
2.  **CRLF vs LF (Line Endings Cross-Platform):** Pengembang Windows menggunakan Carriage Return + Line Feed (`\r\n`), sedangkan Linux/macOS hanya menggunakan Line Feed (`\n`). Jika tidak dikonfigurasi, Git akan menganggap seluruh baris pada berkas berubah saat dipindahkan antar-sistem operasi.
    *   *Solusi Windows:* `git config --global core.autocrlf true`
    *   *Solusi Mac/Linux:* `git config --global core.autocrlf input`
3.  **Case Sensitivity pada File Path:** Sistem operasi Windows dan macOS secara default bersifat *case-insensitive* namun *case-preserving*, sedangkan Linux *case-sensitive*. Mengubah nama `Model.js` menjadi `model.js` dapat berakibat fatal jika konfigurasi `core.ignorecase` Git tidak diatur dengan teliti.

---

### 11. Common Pitfalls & Mistakes
*   **Kesalahan 1: Lupa Mengonfigurasi Identitas.** Menggunakan Git sebelum `user.name` atau `user.email` diatur menghasilkan komit beridentitas rusak (misal: `root@localhost`), yang menyulitkan atribusi audit kode.
*   **Kesalahan 2: Memperlakukan Staging Area Seperti Komit Sementara.** Mengira bahwa melakukan `git add` sudah menyimpan kode secara aman. Jika berkas di *Working Directory* tertimpa tanpa sengaja atau repo di-*hard reset*, pemulihan berkas yang hanya di-*stage* membutuhkan inspeksi manual *dangling blob* lewat `git fsck`.
*   **Kesalahan 3: Menyimpan Kredensial Sensitif.** Memasukkan `.env`, SSH keys, atau sertifikat API langsung pada commit awal. Sekali berkas terkomit, menghapus berkas di commit berikutnya **tidak** menghapusnya dari riwayat repositori `.git/`. Berkas tetap ada di riwayat lampau.

---

### 12. Performance & Resource Considerations
*   **Penyimpanan Biner vs Teks:** Git sangat efisien untuk berkas teks berbasis baris karena kompresi objek *zlib* dan algoritma *packfile* (delta-compression antar-versi). Namun, untuk berkas biner besar (misal: database dump `.sql`, video `.mp4`, model AI `.bin`), Git tidak dapat membuat delta yang efisien. Setiap revisi biner akan menduplikasi ukuran file secara penuh di dalam folder `.git/`, menyebabkan pembengkakan repositori (*repository bloat*). Gunakan *Git LFS (Large File Storage)* untuk kasus tersebut.
*   **Lokalitas Eksekusi:** Berbeda dari CVCS yang butuh komunikasi TCP/IP ke server pusat untuk melihat log atau diff, 95% operasi Git dieksekusi secara instan (*sub-second*) langsung ke disk penyimpanan lokal.

---

### 13. Security Considerations
*   **Verifikasi Identitas vs Otentikasi:** Konfigurasi `user.name` dan `user.email` pada Git bukan mekanisme keamanan; data ini bisa dipalsukan oleh siapa saja (*identity spoofing*). Otentikasi asli dilakukan pada protokol transfer (SSH/HTTPS) atau melalui penandatanganan kriptografis (*GPG/SSH Commit Signing*).
*   **Pembersihan Berkas Rahasia:** Sekali secret terdorong (*committed*), lakukan rotasi secret secara langsung (anggap kredensial telah bocor), bukan sekadar melakukan komit penghapusan berkas. Gunakan tool seperti `trufflehog` atau `gitleaks` dalam pipeline CI/CD untuk mencegah kebocoran secret.

---

### 14. Comparison & Trade-offs

| Kategori Analisis | Manual Zip / Backup | Centralized VCS (SVN) | Distributed VCS (Git) |
| :--- | :--- | :--- | :--- |
| **Penyimpanan Riwayat** | Ad-hoc / Terfragmentasi | Terpusat di Server Utama | Penuh di Setiap Mesin Lokal |
| **Kinerja Offline** | Tidak Terstruktur | Tidak Bisa (Butuh Jaringan) | Penuh (Kecuali Push/Pull) |
| **Operasi Branching** | Gandakan Salinan Folder | Berat (Duplikasi Path) | Sangat Ringan (Pointer 41-byte) |
| **Integritas Data** | Tidak Terjamin | Bergantung File System Server | Kriptografis Keras (SHA Tree) |
| **Kurva Belajar** | Sangat Rendah | Sedang | Curam / Kompleks |

---

### 15. Best Practices & Design Patterns
*   **Struktur Commit Atomik (*Atomic Commits*):** Sebuah komit harus merepresentasikan satu unit perubahan logis yang tidak dapat dibagi lagi. Jangan gabungkan implementasi fitur baru dengan perbaikan *bug* yang tidak relevan di dalam satu komit yang sama.
*   **Penerapan Konvensi Pesan Commit (Conventional Commits):** Format commit terstandarisasi memudahkan pembacaan changelog otomatis:
    ```text
    <type>(<scope opsional>): <deskripsi imperatif singkat>

    [body penjelasan opsional]

    [footer tiket / referensi issue opsional]
    ```
    *Contoh:* `fix(auth): resolve JWT expiration validation edge-case`
*   **Inisialisasi `.gitignore` Lebih Awal:** Selalu definisikan berkas apa saja yang harus diabaikan (misal: node_modules/, .env, *.log, dist/) tepat setelah `git init`, sebelum melakukan komit pertama.

---

### 16. Verification & Testing
Untuk memvalidasi keberhasilan konfigurasi dan pemahaman status Git:

1.  **Periksa Integritas Konfigurasi:**
    ```bash
    git config --show-scope --list
    ```
    *Ekspektasi Output:* Terdapat level `global` atau `local` yang menunjukkan `user.name` dan `user.email`.
2.  **Verifikasi Keberadaan Internal Database:**
    ```bash
    ls -la .git
    ```
    *Ekspektasi Output:* Muncul berkas `HEAD`, direktori `objects/`, `refs/`, dan berkas `config`.
3.  **Inspeksi Objek Git Secara Rendah (*Plumbing Command*):**
    ```bash
    # Mengambil hash commit terakhir
    LAST_COMMIT=$(git rev-parse HEAD)
    # Memeriksa tipe dari objek tersebut
    git cat-file -t $LAST_COMMIT
    # Memeriksa konten mentah dari objek commit
    git cat-file -p $LAST_COMMIT
    ```
    *Ekspektasi Output:* Tipe adalah `commit`, dan isinya memuat struktur pohon (*tree*), author, committer, serta pesan komit.

---

### 17. Troubleshooting Guide

#### Masalah A: Error "Author identity unknown"
*   **Gejala:** Saat `git commit`, muncul peringatan:
    `fatal: unable to auto-detect email address (got 'user@machine.(none)')`
*   **Akar Masalah:** Git belum membaca variabel `user.email` dan `user.name` pada konfigurasi lokal maupun global.
*   **Resolusi:**
    ```bash
    git config --global user.name "Nama Lengkap"
    git config --global user.email "email@domain.com"
    ```

#### Masalah B: Mengurungkan Berkas yang Salah Masuk Staging
*   **Gejala:** Berkas sensitif `credentials.json` tidak sengaja dijalankan via `git add credentials.json` dan berstatus *staged*.
*   **Akar Masalah:** Berkas masuk ke `.git/index` namun belum di-commit secara permanen.
*   **Resolusi:**
    ```bash
    # Lepaskan file dari staging tanpa menghapus data di working directory
    git restore --staged credentials.json
    ```

---

### 18. Mini Project / Lab Exercise

#### Skenario Lab:
Membangun fondasi repositori backend sistem inventaris, menangani tracking awal, dan mengonfigurasi filter pengabaian berkas secara presisi.

#### Instruksi Tugas:
1.  Buat direktori baru bernama `lab-inventory-core` dan inisialisasi sebagai repositori Git dengan branch utama bernama `main`.
2.  Konfigurasikan repositori lokal ini agar memiliki identitas penulis: `Lab Worker <lab@local.internal>`.
3.  Buat berkas `.gitignore` yang memblokir semua berkas dengan ekstensi `.log` dan semua folder bernama `cache/`.
4.  Buat struktur berkas awal:
    *   `README.md` (isi: `# Inventory Core Module`)
    *   `app.log` (isi: `test error output`)
    *   `src/index.js` (isi: `// Init Core`)
5.  Gunakan `git status` untuk memverifikasi bahwa `app.log` berhasil terabaikan secara otomatis oleh Git.
6.  Lakukan *staging* pada semua berkas yang sah dan buat komit pertama dengan pesan: `feat: scaffold initial repository structure and ignore policies`.
7.  Tampilkan satu baris ringkasan commit menggunakan perintah `git log`.

---

### 19. Review Questions & Knowledge Check
1.  **Analisis:** Mengapa Git disebut sebagai *Distributed Version Control System* jika dibandingkan dengan Apache Subversion (SVN)? Konsekuensi apa yang terjadi jika koneksi internet terputus saat developer ingin melihat riwayat perubahan kode?
2.  **Mekanisme:** Jelaskan apa yang terjadi di balik layar pada folder `.git` saat Anda menjalankan perintah `git add main.py`! Objek Git apa yang seketika terbentuk di dalam `.git/objects`?
3.  **Diagnostik:** Jika Anda membuat direktori kosong bernama `assets/images/` lalu menjalankan `git status`, mengapa Git menolak mendeteksi direktori tersebut? Bagaimana cara mengakali karakteristik Git terhadap folder kosong?
4.  **Konseptual:** Apa perbedaan peran antara atribut `Author` dan `Committer` di dalam metadata sebuah commit Git? Pada skenario apa kedua data ini menjadi tidak identik?
5.  **Performa:** Jelaskan perbedaan fundamental antara metode penyimpanan *Delta Storage* yang digunakan SVN dengan sistem *Snapshot* yang diadopsi oleh Git! Mengapa pendekatan *Snapshot* membuat operasi `checkout` cabang pada Git menjadi sangat cepat?

---

### 20. Next Steps & Further Reading
*   Mempelajari modul selanjutnya: **Module 02 - Inspeksi, Diffing, dan Penanganan Siklus Hidup Revisi (Staging Area In-Depth & Git Diff)**.
*   Membaca dokumentasi resmi Pro Git Book: *Chapter 1: Getting Started* dan *Chapter 2: Git Basics*.
*   Eksplorasi dokumentasi manual: Jalankan `git help config` dan `git help status` langsung dari Terminal Anda untuk mempelajari flag operasional lanjutan.