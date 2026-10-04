## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: GGB-01-07-01
* **Nama Modul**: Kolaborasi Jarak Jauh: Remote Tracking, Sinkronisasi, dan Model Terdistribusi
* **Kategori**: `01-Core-Foundations`
* **Tingkat Kesulitan**: Pemula Menengah (Beginner to Intermediate)
* **Prasyarat**:
  * Penguasaan *Local Version Control* (Commit, Branching, Merging lokal).
  * Pemahaman struktur dasar direktori `.git` (khususnya *object storage* dan *pointers*).
  * Akun aktif pada Git hosting platform (GitHub / GitLab) dan konfigurasi SSH Key / Personal Access Token (PAT).
* **Alokasi Waktu**: 
  * Teori: 45 Menit
  * Praktik Mandiri: 75 Menit
* **Target Pembaca**: Perekayasa Perangkat Lunak tingkat dasar hingga menengah yang ingin memahami mekanisme internal pertukaran data antar repositori terdistribusi pada Git.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Mendefinisikan** arsitektur *Distributed Version Control System* (DVCS) dan menjelaskan secara teknis bagaimana repositori lokal berinteraksi dengan repositori *remote*.
2. **Membedakan** secara presisi antara cabang lokal (*local branch*), cabang pelacak jarak jauh (*remote-tracking branch* seperti `origin/main`), dan cabang riil di remote (*upstream branch*).
3. **Mengonfigurasi** dan mengelola *remote endpoints* menggunakan perintah `git remote` (tambah, verifikasi URL, ubah URL, hapus).
4. **Menganalisis** perbedaan mendasar antara operasi transfer data murni (`git fetch`), integrasi lokal (`git merge`), dan abstraksi gabungan (`git pull`).
5. **Mengeksekusi** proses sinkronisasi kode secara aman menggunakan `git push` beserta flag `--set-upstream` (`-u`), serta mengidentifikasi penyebab terjadinya penolakan push (*non-fast-forward rejection*).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       +---------------------------------------+
                       |   Distributed Version Control Model   |
                       +---------------------------------------+
                                           |
                   +-----------------------+-----------------------+
                   |                                               |
                   v                                               v
    +-----------------------------+                 +-----------------------------+
    |      Local Repository       |                 |      Remote Repository      |
    |      (Mesin Pengembang)     |                 |    (GitHub / Server Pusat)  |
    +-----------------------------+                 +-----------------------------+
      |        ^               |                      ^              |
      |        |               |                      |              |
 (git push) (git merge)   (git fetch)             (Receive)      (Serve)
      |        |               |                      |              |
      v        |               v                      |              |
  +-------------------------------+                   |              |
  |    Remote-Tracking Branch     | <-----------------+--------------+
  |     (refs/remotes/origin/*)   |      Update metadata/refs lokal
  +-------------------------------+
```

* **Remote Endpoint**: Alias pointer yang merepresentasikan URL repositori target (default: `origin`).
* **Remote-Tracking Branch**: Saluran read-only lokal yang mencerminkan status terakhir commit di server remote (misal: `refs/remotes/origin/main`).
* **Upstream Branch**: Cabang remote yang dipetakan langsung ke cabang lokal untuk tracking otomatis.
* **Three-Way Handshake of Sync**:
  1. `Fetch`: Mengunduh objek commit baru dari remote ke remote-tracking branch tanpa menyentuh *working directory*.
  2. `Merge`: Mengintegrasikan perubahan dari remote-tracking branch ke cabang lokal aktif.
  3. `Push`: Mengirimkan objek commit lokal ke remote dan memajukan pointer remote branch jika kondisi valid (*Fast-Forward*).

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Git dirancang sebagai sistem terdistribusi, bukan tersentralisasi seperti Subversion (SVN) atau Perforce. Pemahaman ini sering terdistorsi oleh paradigma sentralistis GitHub. Jika pengembang tidak memahami pemisahan antara referensi lokal, referensi remote-tracking, dan repositori remote yang sebenarnya, kesalahan fatal akan terjadi:

1. **Blind Pull Hazards**: Melakukan `git pull` secara membabi buta dapat menghasilkan merge commit yang tidak diinginkan (*spaghetti history*) atau memicu konflik langsung pada *working directory* saat kode lokal belum siap.
2. **Push Rejection Panic**: Pemula kerap kali merespons error `[rejected - non-fast-forward]` dengan melakukan force-push (`git push -f`), yang berpotensi menghapus riwayat komit rekan setim yang telah terdistribusi secara permanen.
3. **Decoupled Workflow**: Memahami bahwa `fetch` terpisah dari integrasi (`merge`/`rebase`) memungkinkan inspeksi kode (*code audit*) sebelum mengizinkan kode asing mencemari basis kode lokal.

---

## SEKSI 05 — APA ITU (WHAT)

Secara mekanis, interaksi remote pada Git adalah protokol transfer objek komit, *trees*, dan *blobs* antar dua repositori Git independen, diikuti oleh sinkronisasi penunjuk cabang (*references* atau *refs*).

### Komponen Utama:

1. **`git remote`**: Perintah utilitas untuk mengelola daftar bookmark/alias yang memetakan label pendek (seperti `origin` atau `upstream`) ke Universal Resource Identifier (URI) dari repositori eksternal.
2. **Refs Storage**:
   * Lokal branch berada di: `.git/refs/heads/<branch-name>`
   * Remote-tracking branch berada di: `.git/refs/remotes/<remote-name>/<branch-name>`
3. **`git fetch`**: Operasi murni jaringan yang menyalin objek dari sistem file target ke direktori `.git/objects/` lokal, kemudian memperbarui referensi di `.git/refs/remotes/<remote-name>/`.
4. **`git merge`**: Operasi murni lokal yang menggabungkan riwayat commit dari cabang pelacak (misal `origin/main`) ke cabang lokal yang sedang aktif (`main`).
5. **`git pull`**: Perintah komposit tingkat tinggi (*porcelain*) yang mengeksekusi `git fetch` terlebih dahulu, lalu secara otomatis menjalankan `git merge FETCH_HEAD` (atau `git rebase` jika dikonfigurasi).
6. **`git push`**: Operasi upload objek Git lokal ke repositori remote, dilanjutkan dengan permintaan pembaruan ref di remote server.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Anatomi Tracking Branch
Saat Anda mengkloning repositori atau mengatur hubungan tracking:
```bash
git branch --set-upstream-to=origin/main main
```
Git memodifikasi berkas konfigurasi lokal (`.git/config`):
```ini
[branch "main"]
    remote = origin
    merge = refs/heads/main
```
Konfigurasi ini memberitahukan Git: "Ketika saya berada di branch `main` dan menjalankan `git pull`, ambil referensi dari remote `origin` yang mengarah ke `refs/heads/main`."

### 2. Mekanisme `git fetch` vs `git pull`
* **Saat `git fetch origin` dijalankan**:
  1. Git membuka koneksi transport (HTTPS/SSH) ke host `origin`.
  2. Git menegosiasikan referensi objek yang hilang (*packfile negotiation*).
  3. Objek baru diunduh ke `.git/objects/`.
  4. Pointer `.git/refs/remotes/origin/main` digeser ke commit SHA terbaru dari server.
  5. Pointer cabang lokal Anda (`.git/refs/heads/main`) **TIDAK BERUBAH**.
  6. *Working directory* dan *Staging Area* Anda **TIDAK DISENTUH**.

* **Saat `git pull origin main` dijalankan**:
  1. Melakukan seluruh siklus `git fetch` di atas.
  2. Mengidentifikasi cabang aktif saat ini.
  3. Memanggil algoritma penggabungan: `git merge origin/main` ke cabang aktif saat ini.
  4. Jika terdapat perubahan non-overlapping, working directory diperbarui. Jika bertabrakan, status berubah menjadi *Conflict state*.

### 3. Logika Verifikasi `git push`
Ketika Anda menjalankan `git push origin main`:
```
Server mengevaluasi:
Apakah pointer 'origin/main' saat ini merupakan direct ancestor dari commit baru lokal?
  ├── YA  --> FAST-FORWARD: Pointer remote dimajukan ke SHA commit lokal baru. Push Diterima.
  └── TIDAK --> NON-FAST-FORWARD: Berarti ada commit di remote yang belum diambil ke lokal. 
                Push Ditolak (Rejected).
```

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Siklus Sinkronisasi Terdistribusi

```
+-----------------------------------------------------------------------------------------+
|                                    MESIN PENGEMBANG LOKAL                               |
|                                                                                         |
|  [ Working Dir ] <======> [ Staging Area ] <======> [ Local Branch ]                    |
|         ^                                                 | (refs/heads/main)           |
|         |                                                 |                             |
|         |                 (git merge)                     v                             |
|         |        +----------------------------+      (git push)                         |
|         |        | Integrasi commit lokal     |           |                             |
|         |        | dengan refs/remotes/origin |           |                             |
|         |        +----------------------------+           |                             |
|         |                      ^                          |                             |
|         |                      |                          v                             |
|         +------------ (git pull: fetch + merge)           |                             |
|                                |                          |                             |
|                  +----------------------------+           |                             |
|                  |   Remote-Tracking Branch   |           |                             |
|                  | (refs/remotes/origin/main) |           |                             |
|                  +----------------------------+           |                             |
|                                ^                          |                             |
+--------------------------------|--------------------------|-----------------------------+
                                 |                          |
                     (git fetch) |                          | (git push)
                                 |                          v
+--------------------------------|--------------------------------------------------------+
|                                |                                                        |
|                         [ SERVER PUSAT / HOSTING REMOTE (origin) ]                     |
|                                                                                         |
|                                    refs/heads/main                                      |
|                                 (Database Objek Git)                                    |
+-----------------------------------------------------------------------------------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Skenario: Inisialisasi remote ke repositori kosong dan push pertama.

```bash
# 1. Masuk ke direktori proyek lokal
cd ~/workspace/proyek-dasar

# 2. Inisialisasi Git jika belum
git init -b main

# 3. Buat file awal dan lakukan commit pertama
echo "# Dokumentasi Proyek" > README.md
git add README.md
git commit -m "docs: inisialisasi repositori dengan README"

# 4. Hubungkan remote repository (ganti URI sesuai akun Anda)
git remote add origin git@github.com:developer/proyek-dasar.git

# 5. Verifikasi koneksi remote
git remote -v
# Output:
# origin  git@github.com:developer/proyek-dasar.git (fetch)
# origin  git@github.com:developer/proyek-dasar.git (push)

# 6. Kirim commit lokal ke remote sekaligus konfigurasi upstream tracking
git push -u origin main
# Flag -u (--set-upstream) memastikan asosiasi permanen antara branch lokal 'main'
# dan branch remote 'origin/main'.
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Skenario Real-World: Kolaborasi tim di mana rekan kerja telah melakukan push ke branch `main`, sementara Anda memiliki pekerjaan lokal yang belum disinkronkan. Menggunakan pendekatan defensif (`fetch` -> `diff` -> `merge`).

```bash
# 1. Anda membuat commit lokal baru
echo "function hitungPajak() {}" >> invoice.js
git add invoice.js
git commit -m "feat: tambahkan fungsi kalkulasi pajak"

# 2. Lakukan FETCH, bukan PULL (pendekatan aman)
# Langkah ini memperbarui refs/remotes/origin/main tanpa mengubah file kerja Anda
git fetch origin

# 3. Analisis divergensi riwayat komit
# Bandingkan cabang lokal saat ini dengan cabang remote-tracking
git log --oneline --left-right HEAD...origin/main
# Tanda '<' menunjukkan commit hanya ada di lokal Anda
# Tanda '>' menunjukkan commit ada di remote dan belum terintegrasi ke lokal

# Output:
# < a1b2c3d feat: tambahkan fungsi kalkulasi pajak
# > f4e5d6c fix: perbaiki rounding nilai mata uang

# 4. Tinjau perbedaan kode sebenarnya sebelum merge
git diff HEAD origin/main

# 5. Eksekusi penggabungan (merge)
git merge origin/main
# Git akan memicu three-way merge. Jika tidak ada konflik, file tergabung otomatis.

# 6. Dorong hasil rekonsiliasi ke remote
git push origin main
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi | `git pull` (Default Merge) | `git pull --rebase` | `git fetch` + Manual `merge` |
| :--- | :--- | :--- | :--- |
| **Kelebihan** | Cepat, hanya 1 perintah, mempertahankan riwayat kronologis asli repositori. | Riwayat commit tetap linier, bersih, tanpa *noise* berupa merge commit sepele. | Tingkat kontrol maksimum; pengembang dapat mengaudit kode sebelum dieksekusi ke lokal. |
| **Kekurangan** | Menghasilkan pola percabangan kusut (*merge-bubble clutter*) pada basis tim besar. | Mengubah hash SHA-1 commit lokal; berisiko jika rebase dilakukan pada commit yang telah dipublish. | Membutuhkan langkah eksekusi ganda dan pemahaman refspec tingkat lanjut. |
| **Kapan Digunakan** | Pada integrasi fitur branch lokal yang komprehensif. | Sinkronisasi cabang personal harian dengan branch upstream yang sangat aktif. | Siklus produksi kritis, deployment server, atau saat mencurigai adanya konflik destruktif. |

---

## SEKSI 11 — BEST PRACTICES

1. **Selalu Gunakan Flags Upstream di Awal**: Eksekusi `git push -u origin <branch_name>` pada push perdana sebuah cabang agar operasi selanjutnya cukup memanggil `git push` atau `git pull`.
2. **Fetch Sebelum Merge (Defensive Sync)**: Lakukan `git fetch` secara berkala untuk memperbarui peta dunia remote tanpa mengambil risiko konflik mendadak pada *working tree*.
3. **Hindari Direct Push ke `main`/`master`**: Gunakan remote tracking branches untuk branch fitur personal (`feature/nama-fitur`) dan gunakan mekanisme *Pull Request* / *Merge Request* untuk branch utama.
4. **Verifikasi Status Divergensi**: Gunakan `git status -sb` secara reguler. Perintah ini akan memberitahukan posisi Anda terhadap remote (misal: `ahead 1, behind 2`).
5. **Prune Stale Branches**: Bersihkan referensi remote lokal yang cabangnya sudah dihapus di server:
   ```bash
   git fetch --prune
   ```

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Merespons Non-Fast-Forward Error dengan `--force`
* **Kesalahan**: Saat menerima pesan `error: failed to push some refs... Updates were rejected because the remote contains work that you do not have locally`, pengembang mengeksekusi `git push --force`.
* **Dampak**: Commit rekan kerja yang ada di server remote terhapus secara sepihak dan hilang dari riwayat cabang utama.
* **Solusi**: Tarik perubahan terlebih dahulu menggunakan `git pull` atau `git fetch` + `git merge`, selesaikan konflik jika ada, lalu push kembali.

### 2. Menganggap `git fetch` Mengubah Kode Sumber di Editor
* **Kesalahan**: Pengembang menjalankan `git fetch origin` lalu panik karena baris kode terbaru dari rekannya tidak terlihat di editor teks.
* **Penyebab**: `fetch` hanya mengunduh data metadata ke database `.git/objects/` dan memajukan pointer remote tracking `origin/<branch>`.
* **Solusi**: Integrasikan data tersebut ke cabang lokal dengan `git merge origin/<branch>`.

### 3. Mengubah URL Remote dengan Cara Menghapus Repositori Lokal
* **Kesalahan**: Melakukan kloning ulang repositori hanya karena URL hosting target berubah dari HTTPS ke SSH.
* **Solusi**: Cukup perbarui URL endpoint yang sudah ada menggunakan utilitas Git:
  ```bash
  git remote set-url origin git@github.com:organisasi/repo-baru.git
  ```

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Konfigurasi Multi-Remote Simulasi
1. Buat folder baru bernama `simulasi-upstream` dan inisialisasi sebagai *bare repository*:
   ```bash
   git init --bare simulasi-upstream.git
   ```
2. Buat folder kerja `proyek-lokal`, lalu inisialisasi Git:
   ```bash
   mkdir proyek-lokal && cd proyek-lokal
   git init -b main
   echo "Initial file" > app.txt
   git add app.txt && git commit -m "feat: inisialisasi proyek"
   ```
3. Tambahkan `simulasi-upstream.git` sebagai remote dengan nama `origin`:
   ```bash
   git remote add origin ../simulasi-upstream.git
   git push -u origin main
   ```
4. Tambahkan remote kedua bernama `backup-target`:
   ```bash
   git remote add backup-target ../simulasi-upstream.git
   git remote -v
   ```
   *Ekspektasi Hasil*: Menampilkan dua remote berbeda dengan endpoint masing-masing.

### Latihan 2: Dekonstruksi Mekanisme Fetch vs Pull
1. Buka terminal kedua, buat klon dari `simulasi-upstream.git` ke folder `rekan-kerja`:
   ```bash
   git clone ../simulasi-upstream.git rekan-kerja
   cd rekan-kerja
   echo "Update dari rekan" >> rekan.txt
   git add rekan.txt && git commit -m "docs: penambahan oleh rekan"
   git push origin main
   ```
2. Kembali ke terminal pertama (`proyek-lokal`):
   * Jalankan `git status` (Perhatikan: Git lokal belum menyadari ada komit baru di server).
   * Jalankan `git fetch origin`.
   * Jalankan `git status` (Perhatikan: Git melaporkan: `Your branch is behind 'origin/main' by 1 commit`).
   * Periksa berkas `rekan.txt` di editor Anda (File belum ada di sistem berkas).
   * Jalankan `git merge origin/main`.
   * Periksa kembali berkas `rekan.txt` (File sekarang telah muncul).

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan berikut untuk menguji pemahaman konseptual Anda:

1. Apa perbedaan absolut antara cabang `main` dengan cabang `origin/main` di komputer lokal Anda?
2. Jika Anda mengeksekusi `git fetch origin`, berkas manakah yang diperbarui oleh Git?
   * A. Berkas-berkas di Staging Area.
   * B. Pointer cabang di `.git/refs/heads/`.
   * C. Berkas kerja di Working Directory.
   * D. Pointer cabang di `.git/refs/remotes/origin/`.
3. Mengapa `git push` ditolak (*rejected*) oleh Git saat terdeteksi *non-fast-forward*?
4. Flag apa yang harus disertakan saat melakukan push pertama kali pada sebuah branch untuk mengonfigurasi tracking otomatis terhadap remote branch?
5. Apakah operasi `git pull` dapat dijalankan secara aman jika Working Directory Anda memiliki uncommitted changes yang berbenturan langsung dengan commit remote? Apa yang akan terjadi?

### Kunci Jawaban Singkat:
1. `main` adalah referensi pointer lokal (`refs/heads/main`) yang bisa Anda modifikasi langsung melalui commit. Sedangkan `origin/main` adalah *remote-tracking pointer* (`refs/remotes/origin/main`) yang bersifat *read-only* lokal dan hanya diperbarui saat ada operasi sinkronisasi dengan server remote (`fetch`/`pull`/`push`).
2. **D**.
3. Karena server mendeteksi bahwa commit target di remote memiliki riwayat yang tidak dimiliki oleh commit pengirim lokal. Menerima push tersebut secara otomatis akan menghapus riwayat komit yang berada di antara kedua titik tersebut.
4. Flag `-u` atau `--set-upstream`.
5. Tidak aman. Git akan menolak operasi pull (*abort*) sebelum proses penggabungan dimulai untuk mencegah hilangnya uncommitted changes Anda (*"error: Your local changes to the following files would be overwritten by merge"*), kecuali perubahan tersebut tidak berada pada baris/file yang sama.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Dokumentasi Resmi Git**:
  * Pro Git Book, Bab 2.5: *Git Basics - Working with Remotes* (Scott Chacon & Ben Straub).
  * Manpages: `git-remote(1)`, `git-fetch(1)`, `git-push(1)`.
* **Spesifikasi Git Architecture**:
  * Git Internals: Transfer Protocols (`git-scm.com/book/en/v2/Git-Internals-Transfer-Protocols`).
* **Interactive Tooling**:
  * Visualizing Git Architecture: *Learn Git Branching* (learngitbranching.js.org).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

Kolaborasi remote pada Git bertumpu pada sifat terdistribusi (*DVCS*), di mana setiap instansi repositori lokal membawa seluruh siklus hidup riwayat komit secara utuh. Sinkronisasi bukanlah transmisi stream file real-time, melainkan operasi rekonsiliasi penunjuk referensi (*references*) dan pertukaran *commit objects*.

Perintah `git remote` membangun pemetaan alamat target. `git fetch` memfasilitasi pengambilan data murni tanpa risiko instabilitas pada file kerja lokal dengan cara hanya memperbarui *remote-tracking branches* (`origin/*`). Integrasi mutlak dilakukan secara lokal melalui `git merge` atau `git pull` (yang merupakan otomasi komposit keduanya). Upaya pengiriman data melalui `git push` mewajibkan relasi *fast-forward*, memastikan tidak ada riwayat komit publik yang terhapus secara tidak sengaja oleh perbedaan status lokal.

---

## SEKSI 17 — GLOSARIUM

* **Origin**: Konvensi penamaan default untuk remote repositori utama yang pertama kali dihubungkan atau dikloning.
* **Remote-Tracking Branch**: Penunjuk lokal untuk status cabang remote (`refs/remotes/<remote>/<branch>`). Pengembang tidak bisa berpindah (*checkout*) langsung untuk commit ke branch ini; sifatnya read-only.
* **Upstream Branch**: Cabang pada server remote yang di-track secara eksplisit oleh cabang lokal.
* **Fast-Forward**: Kondisi penggabungan atau pembaruan pointer di mana cabang target tidak memiliki perubahan divergen, sehingga pointer cukup digeser maju ke komit terbaru.
* **Divergent History**: Kondisi di mana cabang lokal dan cabang remote sama-sama memiliki komit baru yang independen sejak titik pemisahan (*fork point*) terakhir.
* **Bare Repository**: Repositori Git yang diinisialisasi tanpa *working directory* (hanya memuat folder `.git`), lazim digunakan sebagai server pusat penerima push.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Poin Penekanan**: Tegaskan bahwa GitHub bukanlah Git. Pisahkan konsep arsitektur internal Git dengan antarmuka grafis atau fitur-fitur eksternal GitHub (Issue, PR, Actions).
* **Demistifikasi `git pull`**: Banyak peserta didik pemula menganggap `pull` adalah satu operasi atomik tunggal. Selalu tekankan rumus: `git pull = git fetch + git merge`. Ini akan membantu mereka saat menghadapi issue konflik atau detached HEAD.
* **Simulasi Tanpa Koneksi Internet**: Demonstrasikan bahwa `git remote add` dan `git fetch/push` dapat bekerja menggunakan file system lokal (protokol berkas lokal: `/path/to/repo.git`), sehingga peserta memahami bahwa Git tidak inheren membutuhkan koneksi internet untuk beroperasi dalam model remote.
* **Area Rawan Frustrasi**: Error *Rejected Push*. Pastikan peserta didik terlatih membaca error log Git secara sistematis sebelum terburu-buru mencari solusi pintas yang destruktif.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0 (Oktober 2023)**:
  * Rilis inisial materi Kolaborasi Jarak Jauh.
  * Penambahan diagram alur kerja fetch-merge-push.
  * Standardisasi format silabus teknik 20 seksi GEMINI.md.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `GGB-01-06-02`: Resolusi Konflik Tingkat Lanjut (*Advanced Merge Conflict Resolution*).
* **Modul Saat Ini**: `GGB-01-07-01`: Kolaborasi Jarak Jauh: Remote Tracking, Sinkronisasi, dan Model Terdistribusi.
* **Modul Berikutnya**: `GGB-01-07-02`: Workflow GitHub: Forking, Branching Strategy, dan Mekanisme Pull Request.