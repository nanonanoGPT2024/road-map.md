# KURIKULUM GIT & GITHUB: ZERO TO PRODUCTION
## Kategori: 01-Core-Foundations
### Bab 06 — Resolusi Konflik: Module 01

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `MOD-01-06-01`
* **Nama Modul**: Anatomi dan Resolusi *Merge Conflict* pada Git
* **Tingkat Kesulitan**: *Beginner-to-Intermediate*
* **Estimasi Waktu Penyelesaian**: 90 Menit
* **Prasyarat Pengetahuan**:
  * Pemahaman arsitektur *commit history* dan *Directed Acyclic Graph* (DAG).
  * Kemampuan dasar manipulasi branch (`git branch`, `git switch`, `git checkout`).
  * Pemahaman dasar operasi penggabungan (*merge*) dasar (`git merge`).
  * Kemahiran menggunakan teks editor CLI (Nano, Vim) atau IDE (VS Code).
* **Target Pembaca**: *Junior Software Engineers*, *DevOps Beginners*, dan Pengembang yang bertransisi dari alur kerja solo ke alur kerja kolaboratif tim.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan memiliki kompetensi:

1. **Kognitif (C3 - Analisis & Aplikasi)**:
   * Mengartikulasikan penyebab teknis terjadinya *merge conflict* menggunakan konsep *common ancestor* (*Merge Base*) dan *Three-Way Merge*.
   * Mendekonstruksi anatomi penanda konflik (*conflict markers*) standar Git (`<<<<<<<`, `=======`, `>>>>>>>`) dan format lanjutan (`diff3`).
2. **Psikomotorik (P4 - Artikulasi & Eksekusi)**:
   * Membaca dan menginterpretasikan *Index slots* (Slot 1: Base, Slot 2: Ours, Slot 3: Theirs) melalui inspeksi level rendah (*plumbing commands*).
   * Melakukan isolasi, penyuntingan, pembersihan penanda, staging, dan kompilasi resolusi konflik hingga *working directory* bersih secara deterministik.
   * Mengoperasikan mekanisme pembatalan (*aborting*) dan penelusuran status ketika resolusi mengalami anomali.
3. **Afektif (A3 - Valuasi & Sikap Kerja)**:
   * Menunjukkan ketelitian preventif dalam memvalidasi integritas logika kode gabungan sebelum melakukan komit resolusi.
   * Mengembangkan etika komunikasi lintas tim saat memvalidasi *breaking changes* pada baris kode bersama.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                            [Operasi Git: Merge / Rebase / Pull]
                                            │
                                  Cek Jalur Divergensi
                                            │
                           ┌────────────────┴────────────────┐
                           ▼                                 ▼
                   [Fast-Forward]                 [Three-Way Merge Engine]
                   (Tidak ada deviasi)                       │
                                                  Evaluasi Merge Base vs
                                                   Head (Ours) & Target (Theirs)
                                                             │
                                            ┌────────────────┴────────────────┐
                                            ▼                                 ▼
                                   [Clean Auto-Merge]              [MERGE CONFLICT]
                                   (Delta non-tumpang-tindih)     (Modifikasi pada baris sama
                                                                   atau penghapusan kontradiktif)
                                                                              │
                                                               ┌──────────────┴──────────────┐
                                                               ▼                             ▼
                                                        [Index Staging]             [Working Tree Marker]
                                                      Slot 1: Base (Ancestor)       <<<<<<< HEAD (Ours)
                                                      Slot 2: Ours (Local)          =======
                                                      Slot 3: Theirs (Incoming)     >>>>>>> Branch (Theirs)
                                                               │                             │
                                                               └──────────────┬──────────────┘
                                                                              │
                                                                    [Tindakan Pengembang]
                                                                              │
                                                     ┌────────────────────────┼────────────────────────┐
                                                     ▼                        ▼                        ▼
                                            [Resolusi Manual]         [Strategi Flags]         [Pembatalan]
                                          (Edit Marker -> Simpan)    (--ours / --theirs)      (git merge --abort)
                                                     │                        │                        │
                                                     └───────────┬────────────┘                        ▼
                                                                 │                               [Rollback State]
                                                                 ▼
                                                        [git add <file>]
                                                     (Transisi Slot 1-3 -> Slot 0)
                                                                 │
                                                                 ▼
                                                        [git commit]
                                                    (Finalisasi Merge Commit)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

1. **Realitas Kolaborasi Skala Besar**: Dalam arsitektur tim modern, lusinan pengembang menyentuh basis kode yang sama secara bersamaan. *Merge conflict* bukanlah anomali atau kesalahan sistem, melainkan kondisi deterministik alami dari sistem kendali versi terdistribusi.
2. **Integritas Logika Kode Bisnis**: Git adalah pelacak perubahan baris karakter, bukan penilai semantik logika bisnis bahasa pemrograman. Menyelesaikan konflik secara serampangan dapat meloloskan kesalahan sintaksis, bug logika fatal (*regression*), atau penghapusan kode fungsional milik rekan tim secara tidak sengaja.
3. **Mencegah Kebuntuan *Continuous Integration* (CI)**: Kegagalan dalam mengelola konflik lokal akan merambat ke *Remote Repository*. Hal ini dapat merusak *build pipeline* utama, menahan *deployment cycle*, dan memicu disrupsi produktivitas tim.

---

## SEKSI 05 — APA ITU (WHAT)

### Definisi Formal
*Merge conflict* adalah kondisi kegagalan konkurensi di mana Git mendeteksi adanya mutasi data yang saling berkontradiksi antara dua cabang yang berbeda terhadap satu titik referensi historis yang sama (*common ancestor*), sehingga algoritma penggabungan otomatis tidak dapat menyimpulkan intent pengembang secara deterministik tanpa intervensi manual.

### Skenario Pemicu Konflik
1. **Divergensi Baris Bersama**: Dua cabang mengubah baris teks yang sama (atau rentang baris berdekatan) dengan isi yang berbeda setelah titik pemisahan (*fork point*).
2. **Konflik Modifikasi vs Penghapusan (*Modify/Delete Conflict*)**: Satu cabang memperbarui konten sebuah file, sementara cabang lainnya menghapus file tersebut.
3. **Konflik Struktur File (*Rename/Rename or Rename/Delete*)**: Cabang A mengubah nama file `X` menjadi `Y`, sedangkan cabang B mengubah nama file `X` menjadi `Z`.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Algoritma Three-Way Merge
Ketika Anda mengeksekusi `git merge feature`, Git tidak hanya membandingkan *state* `HEAD` dengan *state* `feature`. Git mencari **Merge Base**—yaitu titik *commit* terakhir di mana kedua branch bertemu.

```
       B---C  (main, HEAD)
      /
  A──o        (A = Merge Base)
      \
       D---E  (feature)
```

Tiga komponen utama yang dievaluasi (*Three-Way*):
* **Base (A)**: Nenek moyang bersama (*Common Ancestor*).
* **Ours (C)**: Status berkas pada branch aktif tempat kita berada (`HEAD`).
* **Theirs (E)**: Status berkas pada branch target yang ingin digabungkan.

Git melakukan kalkulasi delta:
* Delta 1: $D_{ours} = C - A$
* Delta 2: $D_{theirs} = E - A$

Jika $D_{ours}$ dan $D_{theirs}$ memodifikasi baris file yang identik dengan nilai mutasi yang tidak sama, Git menghentikan proses otomatis dan memicu status konflik.

### 2. Mekanisme Internal: The Staging Index Slots
Saat konflik terjadi, status index file normal (Slot 0) dihapus. Git mengisi *staging area* dengan tiga representasi status file tersebut:
* **Slot 1**: Versi *Merge Base* (keadaan awal di komit A).
* **Slot 2**: Versi *Ours* (keadaan lokal di komit C).
* **Slot 3**: Versi *Theirs* (keadaan masuk di komit E).

Anda dapat memeriksa keberadaan slot ini menggunakan perintah *plumbing*:
```bash
git ls-files -u
```

### 3. Injeksi Conflict Markers
Git menuliskan tanda pembatas visual langsung ke dalam file fisik di *working directory*:

```text
<<<<<<< HEAD
Logika atau baris kode lokal Anda (Ours)
=======
Logika atau baris kode dari cabang yang digabungkan (Theirs)
>>>>>>> feature-branch
```

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Visualisasi Status Konflik: Dari Tree Branch Hingga Index Slot

```
1. STRUKTUR HISTORI COMMIT (DAG):

         [Commit A]  <-- Merge Base (Titik Temu Leluhur)
          /      \
         /        \
   [Commit B]   [Commit D]
       |            |
   [Commit C]   [Commit E]  <-- Target Branch (feature)
       ^
       |
    (HEAD / main)


2. PERBEDAAN ISI KODE (File: config.env):

   Merge Base (A)       Ours (C)             Theirs (E)
   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
   │ PORT=3000    │     │ PORT=8080    │     │ PORT=9000    │
   │ DB=mysql     │     │ DB=mysql     │     │ DB=mysql     │
   └──────────────┘     └──────────────┘     └──────────────┘


3. REPRESENTASI PADA GIT INDEX / STAGING:

   +------+----------------+------------------------------------------+
   | Slot | Peran          | Blob SHA                                 |
   +------+----------------+------------------------------------------+
   |  1   | Ancestor (Base)| e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 |
   |  2   | Ours (HEAD)    | 227e8a93a0b82b9b2658e727e0ac010543e5c942 |
   |  3   | Theirs         | a5b9c02ff83b5d8435d08ec42bb90f7c2f8d8392 |
   +------+----------------+------------------------------------------+


4. FILE FISIK PADA WORKING DIRECTORY:

   ┌────────────────────────────────────────────────────────┐
   │ <<<<<<< HEAD                                           │ <-- Batas awal Ours
   │ PORT=8080                                              │ <-- Kode lokal kita
   │ =======                                                │ <-- Pembatas tengah
   │ PORT=9000                                              │ <-- Kode branch tujuan
   │ >>>>>>> feature                                        │ <-- Batas akhir Theirs
   │ DB=mysql                                               │ <-- Baris tanpa konflik
   └────────────────────────────────────────────────────────┘
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah skenario mereproduksi dan menyelesaikan konflik 1-berkas secara manual:

### Langkah 1: Inisialisasi Repository dan File Awal
```bash
mkdir demo-konflik && cd demo-konflik
git init
echo "Versi Awal" > status.txt
git add status.txt
git commit -m "chore: inisialisasi basis data status"
```

### Langkah 2: Buat Branch Baru dan Buat Mutasi
```bash
git switch -c update-alpha
echo "Versi Diperbarui oleh Alpha" > status.txt
git add status.txt
git commit -m "feat: perbarui status melalui cabang alpha"
```

### Langkah 3: Kembali ke Main dan Buat Perubahan Kontradiktif
```bash
git switch main
echo "Versi Diperbarui oleh Main" > status.txt
git add status.txt
git commit -m "fix: modifikasi status langsung di cabang utama"
```

### Langkah 4: Picu Konflik Penggabungan
```bash
git merge update-alpha
```
*Output:*
```
Auto-merging status.txt
CONFLICT (content): Merge conflict in status.txt
Automatic merge failed; fix conflicts and then commit the result.
```

### Langkah 5: Inspeksi Isi File
Buka file `status.txt`:
```text
<<<<<<< HEAD
Versi Diperbarui oleh Main
=======
Versi Diperbarui oleh Alpha
>>>>>>> update-alpha
```

### Langkah 6: Selesaikan Konflik Secara Manual
Edit file `status.txt` menggunakan teks editor pilihan Anda. Hapus semua *conflict markers*, lalu tentukan status final yang valid:
```text
Versi Konsolidasi: Gabungan Main dan Alpha
```

### Langkah 7: Simpan, Stage, dan Selesaikan
```bash
git add status.txt
git commit -m "merge: selesaikan konflik status antara main dan update-alpha"
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus dunia nyata: Penggabungan fitur autentikasi ke branch integrasi di mana berkas konfigurasi *environment* mengalami tabrakan nilai API host dan penambahan baris baru.

### 1. Deteksi dan Analisis Awal
Saat menjalankan `git merge feature/auth-provider`:
```bash
$ git merge feature/auth-provider
Auto-merging api/config.json
CONFLICT (content): Merge conflict in api/config.json
Automatic merge failed; fix conflicts and then commit the result.
```

Periksa status berkas yang terdampak:
```bash
$ git status
On branch staging
You have unmerged paths.
  (fix conflicts and run "git commit")
  (use "git merge --abort" to abort the merge)

Unmerged paths:
  (use "git add <file>..." to mark resolution)
	both modified:   api/config.json
```

### 2. Mengaktifkan Diff3 Style untuk Konteks Lengkap
Format standar Git menyembunyikan kondisi *Merge Base*. Ubah konfigurasi untuk menampilkan apa yang ada sebelum kedua cabang memodifikasinya:
```bash
git config --local merge.conflictStyle diff3
```

Tinjau kembali `api/config.json`:
```json
{
  "service": "identity-gateway",
<<<<<<< HEAD
  "api_port": 8000,
  "rate_limit": 100
||||||| merged common ancestors
  "api_port": 8000
=======
  "api_port": 8080,
  "auth_provider": "oauth2"
>>>>>>> feature/auth-provider
}
```

*Analisis:*
* `merged common ancestors`: Awalnya hanya ada `"api_port": 8000`.
* `HEAD` (Local): Tetap mempertahankan port 8000 dan menambahkan konfigurasi `"rate_limit": 100`.
* `feature/auth-provider` (Incoming): Mengubah port menjadi 8080 dan menambahkan konfigurasi `"auth_provider": "oauth2"`.

### 3. Rekonsiliasi Logika Bisnis
Setelah berdiskusi dengan tim arsitektur, disepakati bahwa port operasional terbaru harus mengikuti `8080`, namun batasan keamanan `rate_limit` lokal dan fitur `auth_provider` baru wajib dipertahankan keduanya.

Sunting `api/config.json` menjadi:
```json
{
  "service": "identity-gateway",
  "api_port": 8080,
  "rate_limit": 100,
  "auth_provider": "oauth2"
}
```

### 4. Eksekusi Validasi Sintaks dan Finalisasi
Pastikan file JSON valid secara sintaksis sebelum melakukan komit:
```bash
# Validasi sintaks format JSON via runtime node
node -e "JSON.parse(require('fs').readFileSync('api/config.json'))"

# Jika sukses tanpa error:
git add api/config.json
git status
```
*Output Staging Area:*
```
All conflicts fixed but you are still merging.
  (use "git commit" to conclude merge)

Changes to be committed:
	modified:   api/config.json
```

Finalisasi dengan komit merge:
```bash
git commit -m "merge(auth): integrasi auth-provider dan resolusi konfigurasi port JSON"
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Strategi / Pendekatan | Keuntungan | Risiko / Kerugian | Rekomendasi Penggunaan |
| :--- | :--- | :--- | :--- |
| **Manual Resolution** (Penyuntingan manual via editor) | Kontrol presisi tinggi; logika bisnis dari kedua belah pihak dapat digabungkan secara granular. | Membutuhkan waktu lebih lama; rentan kesalahan manusia (*typo* sintaks atau penanda terlewat). | Default standar untuk kode logika komputasi, dependensi, dan arsitektur kritis. |
| **Git Checkout Flag: `--ours`** (`git checkout --ours <file>`) | Sangat cepat; langsung mengambil versi branch aktif tanpa memeriksa rincian diff. | Berisiko menghapus seluruh pekerjaan fitur baru milik rekan tim yang ada pada branch incoming. | Digunakan pada berkas tergenerasi (*generated files*) seperti asset terkompilasi, lockfile sementara, atau log. |
| **Git Checkout Flag: `--theirs`** (`git checkout --theirs <file>`) | Sangat cepat; mengadopsi secara total versi branch luar yang di-merge. | Menimpa perubahan lokal yang mungkin krusial untuk branch target saat ini. | Digunakan saat revisi cabang lokal sudah usang dan cabang baru membawa refaktor total yang valid. |
| **Visual Merge Tools** (Kdiff3, VS Code, Meld) | Visualisasi 3-panel terstruktur; navigasi konflik antar-chunk sangat intuitif. | Membutuhkan setup konfigurasi tools eksternal; dependensi GUI pada sistem operasi. | Sangat disarankan untuk pengembang tim aplikasi yang memodifikasi ratusan baris file. |

---

## SEKSI 11 — BEST PRACTICES

1. **Sinkronisasi Berkala (*Frequent Integration*)**: Tarik (*pull*) atau gabungkan perubahan dari branch utama (`main` / `staging`) ke dalam *feature branch* Anda secara harian untuk meminimalisasi jurang perbedaan logika.
2. **Kecilkan Cakupan Fitur (*Small Atomic PRs*)**: *Branch* berumur panjang (*long-lived branches*) adalah kontributor utama *mega-conflict*. Pecah tugas menjadi *Pull Request* kecil (di bawah 300 baris diff).
3. **Standarisasi Code Formatter Tim**: Penggunaan format *prettier* atau *linter* yang berbeda antar developer sering kali memicu konflik palsu (*false conflict*) pada seluruh file hanya karena perbedaan spasi atau *line-ending* (`LF` vs `CRLF`).
4. **Gunakan `merge.conflictStyle diff3`**: Selalu aktifkan opsi ini agar Anda memiliki visibilitas historis terhadap nilai file aslinya, bukan hanya asumsi dua arah yang buta.
   ```bash
   git config --global merge.conflictStyle diff3
   ```
5. **Jangan Mengubah Berkas Autogenerate Secara Manual**: Berkas seperti `package-lock.json` atau `yarn.lock` sebaiknya diregenerasi melalui manajer dependensi (`npm install`) daripada diedit langsung secara tekstual di bagian *conflict marker*.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Menyisakan Conflict Markers pada Kode
Pengembang memodifikasi bagian yang konflik tetapi lupa menghapus penanda visual Git:
```python
# KESALAHAN FATAL: SyntaxError saat runtime
<<<<<<< HEAD
def get_discount():
    return 0.10
=======
def get_discount():
    return 0.15
>>>>>>> origin/main
```
*Dampak*: Kompilasi gagal, *pipeline* CI rusak, atau *production crash*.

### 2. Melakukan Commit Kosong Saat Panik
Ketika mendapati konflik, pemula sering kali langsung mengetik `git commit` tanpa melakukan staging file yang telah diselesaikan. Git akan menolak atau merekam file yang masih terkontaminasi.

### 3. Menggunakan "Force Push" untuk Mengabaikan Konflik
Alih-alih menyelesaikan perbedaan cabang, pengembang mengeksekusi `git push -f` ke branch bersama, yang mengakibatkan commit tim lain tertimpa dan hilang dari *remote branch*.

### 4. Menghapus File Konflik Tanpa Sengaja
Mengetik `git rm <file>` saat panik berniat membatalkan *merge*, yang malah menghapus file tersebut dari pelacakan repositori.

### 5. Lupa Perintah Penyelamat: `git merge --abort`
Banyak pemula tidak mengetahui bahwa kondisi konflik dapat dibatalkan 100% secara aman untuk kembali ke titik semula dengan mengetik:
```bash
git merge --abort
```

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Latihan:
Anda berperan sebagai pengembang backend yang harus menggabungkan patch performa basis data ke branch integrasi tanpa merusak konfigurasi otentikasi yang baru ditambahkan.

#### Tugas 1: Mempersiapkan Workspace dan Simulasi
1. Buat direktori lokal bernama `lab-conflict-resolution`.
2. Inisialisasi Git repositori.
3. Buat file `server.py` dengan konten berikut:
   ```python
   def start_server():
       print("Starting core server...")
       database_timeout = 30
   ```
4. Lakukan komit awal: `git add server.py && git commit -m "feat: server baseline"`.
5. Buat cabang baru `perf/db-tuning` dan pindah ke cabang tersebut.
6. Ubah `database_timeout = 30` menjadi `database_timeout = 10` dan tambahkan `enable_cache = True` tepat di bawahnya.
7. Komit perubahan: `git commit -am "perf: optimasi timeout dan aktifkan cache"`.
8. Pindah kembali ke cabang `main` (atau `master`).
9. Ubah `database_timeout = 30` menjadi `database_timeout = 20` dan tambahkan `audit_logging = True` di baris sebelumnya.
10. Komit perubahan: `git commit -am "security: perketat timeout dan aktifkan audit"`.

#### Tugas 2: Resolusi dan Rekonsiliasi
1. Jalankan penggabungan cabang `perf/db-tuning` ke branch `main`.
2. Analisis laporan konflik di CLI.
3. Tampilkan index slots dari `server.py` menggunakan `git ls-files -u`.
4. Buka file `server.py` dan lakukan penggabungan cerdas dengan spesifikasi:
   * Pertahankan konfigurasi `audit_logging = True`.
   * Pilih nilai timeout yang paling aman di antara kedua update: ambil nilai paling cepat yaitu `10`.
   * Pertahankan `enable_cache = True`.
5. Hapus semua *conflict markers*.
6. Simpan berkas, lakukan staging, dan buat merge commit dengan pesan konvensional.
7. Periksa log visualisasi menggunakan: `git log --graph --oneline --all`.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

### Pertanyaan Evaluasi

1. **Apa fungsi dari Merge Base dalam algoritma penggabungan three-way merge pada Git?**
   * A. Menyimpan status file sementara saat conflict terjadi di RAM.
   * B. Berfungsi sebagai representasi titik leluhur bersama (*common ancestor*) untuk mengevaluasi perubahan relatif dari kedua cabang.
   * C. Menyimpan history dari remote repository agar koneksi internet tidak terputus.
   * D. Menjadi branch default pengganti branch `main` jika terjadi kegagalan commit.

2. **Pada Staging Area Index Slot, angka slot manakah yang merepresentasikan versi file dari commit cabang yang sedang aktif kita gunakan (HEAD/Ours)?**
   * A. Slot 0
   * B. Slot 1
   * C. Slot 2
   * D. Slot 3

3. **Perintah apa yang paling aman dieksekusi jika Anda menyadari bahwa Anda salah strategi saat menyelesaikan konflik merge dan ingin mengembalikan status direktori kerja ke kondisi persis sebelum perintah merge dijalankan?**
   * A. `git reset --hard`
   * B. `git clean -fd`
   * C. `git merge --abort`
   * D. `git revert HEAD`

4. **Karakter manakah yang memisahkan bagian konten cabang lokal kita dengan bagian konten cabang incoming pada standar conflict marker Git?**
   * A. `<<<<<<<`
   * B. `|||||||`
   * C. `>>>>>>>`
   * D. `=======`

5. **Kapan kondisi "Modify/Delete Conflict" terjadi?**
   * A. Dua pengembang mengubah permission berkas yang sama secara bersamaan.
   * B. Satu cabang mengubah konten dari suatu file, sementara cabang lain menghapus file yang bersangkutan.
   * C. File diubah di local directory tetapi file tersebut dihapus oleh rule `.gitignore`.
   * D. Dua file dengan nama yang sama dibuat di dalam dua folder berbeda.

### Kunci Jawaban
1. **B** — Algoritma three-way merge membandingkan Delta cabang A terhadap Base, dan Delta cabang B terhadap Base untuk mengisolasi mutasi kode.
2. **C** — Slot 1 adalah Base, Slot 2 adalah Ours (`HEAD`), dan Slot 3 adalah Theirs.
3. **C** — `git merge --abort` membersihkan status konflik dan me-rollback pointer branch ke kondisi pre-merge secara aman.
4. **D** — Penanda `=======` adalah pembatas tengah (*divider*) antara segmen Ours (atas) dan segmen Theirs (bawah).
5. **B** — Merupakan konflik struktural di mana aksi modifikasi logika bertentangan dengan aksi terminasi berkas.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Dokumentasi Resmi Git**:
  * [Git SC - Advanced Merging Techniques](https://git-scm.com/book/en/v2/Git-Tools-Advanced-Merging)
  * [Git Reference: git-merge Documentation](https://git-scm.com/docs/git-merge)
* **Buku Referensi**:
  * Chacon, S., & Straub, B. (2014). *Pro Git* (2nd ed.). Apress. (Bab 3.2: Basic Branching and Merging).
  * Loeliger, J., & McCullough, M. (2012). *Version Control with Git*. O'Reilly Media.
* **Standar Industri**:
  * Atlassian Git Tutorials: *Comparing Workflows & Merge Conflicts Resolution Standards*.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

* *Merge conflict* adalah kondisi deterministik alami saat Git tidak dapat mengambil keputusan otomatis untuk dua mutasi berbeda yang menyasar baris kode yang sama relatif terhadap *common ancestor*.
* Algoritma *Three-Way Merge* mengandalkan tiga representasi: **Merge Base** (Slot 1), **Ours/Local** (Slot 2), dan **Theirs/Incoming** (Slot 3).
* *Conflict Markers* membatasi area bermasalah dengan penanda struktural (`<<<<<<<`, `=======`, `>>>>>>>`). Seluruh penanda wajib dibersihkan secara manual sebelum komit finalisasi.
* Perintah darurat `git merge --abort` bertindak sebagai mekanisme *fail-safe* untuk membatalkan seluruh operasi penggabungan tanpa meninggalkan status *detached* atau berkas korup.
* Penggunaan `git add <file>` menandakan bahwa konflik pada berkas tersebut telah diselesaikan oleh pengembang dan memindahkan objek berkas kembali ke *Index Slot 0*.

---

## SEKSI 17 — GLOSARIUM

* **Merge Base**: Nenek moyang komit bersama terdekat (*closest common ancestor*) dari dua cabang yang sedang digabungkan.
* **Conflict Markers**: Kumpulan baris string sintetis khusus (`<`, `=`, `>`) yang diinjeksikan Git ke dalam berkas untuk menandai zona divergensi kode.
* **Three-Way Merge**: Metode pemaduan dua set perubahan dengan menyertakan versi komit dasar leluhur sebagai mediator validasi delta.
* **Index Slot**: Ruang penyimpanan metadata internal Git (bernilai 0 hingga 3) di staging area yang digunakan untuk mengisolasi versi file saat terjadi konflik.
* **Fast-Forward Merge**: Operasi penggabungan yang tidak memerlukan rekonsiliasi logika karena cabang target berada persis di jalur lurus historis cabang sumber tanpa adanya percabangan paralel.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Poin Hambatan Siswa**:
  * Siswa pemula sering kali terjebak dalam rasa takut saat melihat teks merah `CONFLICT` di terminal. Tekankan di awal sesi bahwa ini bukan error sistem operasional, melainkan dialog interaktif di mana Git meminta keputusan manusia.
  * Masalah umum pada latihan adalah siswa lupa menghapus baris `=======` atau `>>>>>>>`, yang kemudian menyebabkan *runtime error* saat kode dijalankan. Berikan penekanan visual pada tahap sanitasi kode.
* **Tips Pedagogis**:
  * Tunjukkan secara langsung output dari perintah tingkat rendah `git ls-files -u` di layar proyeksi agar siswa memahami bahwa Git tidak merusak file mereka, melainkan menyimpannya ke dalam tiga slot terpisah di latar belakang.
  * Disarankan untuk mengajarkan mode manual (CLI/Editor Teks dasar) terlebih dahulu sebelum memperkenalkan *GUI Resolve Merge Tool* bawaan VS Code agar mental model fundamental siswa terbentuk kuat.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi**: 1.0.0
* **Tanggal Rilis**: 2025-01-15
* **Author / Maintainer**: Tim Arsitektur Kurikulum Software Engineering
* **Perubahan Terakhir**:
  * Rilis struktur kurikulum standar awal 20 seksi untuk Bab 06 Resolusi Konflik.
  * Penambahan arsitektur *Index Slot Plumbing* dan konfigurasi *diff3*.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* ⬅️ **Modul Sebelumnya**: `MOD-01-05-02`: Mekanisme Penggabungan Cabang (*Git Merge & Fast-Forward Mechanics*)
* 🔄 **Modul Saat Ini**: `MOD-01-06-01`: Anatomi dan Resolusi *Merge Conflict* pada Git
* ➡️ **Modul Berikutnya**: `MOD-01-06-02`: Pengenalan Alat Bantu Visual Resolusi Konflik (*Visual Merge Tools & IDE Integration*)