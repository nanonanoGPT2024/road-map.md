# BAB 04: Quiz, Challenge, & Knowledge Check
**Version Control System Terapan: Git Enterprise**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Struktur Data Internal Git (Content-Addressable Storage):**
   Jelaskan secara mendalam bagaimana Git mengorganisir data di dalam direktori `.git/objects`. Bedakan struktur, fungsi, dan relasi antara empat objek fundamental Git (*blob*, *tree*, *commit*, dan *annotated tag*), serta jelaskan peran algoritma hashing kriptografis (SHA-1/SHA-256) dalam menjamin integritas data (*immutability*).

2. **Mekanisme Staging Area (The Index):**
   Secara arsitektural, apa sebenarnya file `.git/index`? Jelaskan perbedaannya dengan *Working Directory* dan *Commit History*, serta uraikan apa yang terjadi pada *index* ketika Anda mengeksekusi `git add -p` dibandingkan `git add .` dari perspektif pelacakan *hunk* dan penyusunan *tree object* baru.

3. **Fast-Forward vs. True Merge (3-Way Merge):**
   Analisis perbedaan mendasar antara *Fast-Forward merge* dan *3-Way merge* (menggunakan strategi ortodoks seperti *ort* atau *recursive*). Bagaimana Git menentukan *Common Ancestor* (Merge Base), dan apa implikasi topologis dari kedua metode tersebut terhadap keterbacaan riwayat Directed Acyclic Graph (DAG) di repositori skala besar?

4. **Kondisi "Detached HEAD":**
   Apa yang secara teknis terjadi pada referensi pointer di `.git/HEAD` ketika repositori berada dalam status *detached HEAD*? Jika seorang *developer* melakukan *commit* dalam status ini lalu berpindah ke branch lain (`git checkout main`), bagaimana nasib commit-commit baru tersebut di dalam sistem penyimpanan Git? Jelaskan siklus hidupnya hingga mekanisme *Garbage Collection* (`git gc`).

5. **Soft, Mixed, dan Hard Reset:**
   Jelaskan dampak dari ketiga flag eksekusi perintah reset: `git reset --soft`, `git reset --mixed`, dan `git reset --hard` terhadap tiga area Git (*Working Directory*, *Staging Area/Index*, dan *Commit History/HEAD pointer*). Tentukan skenario operasional yang tepat untuk masing-masing flag tersebut.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Resolusi Konflik Internal: Git Rebase vs. Git Merge:**
   Ketika terjadi konflik saat `git rebase` dibandingkan `git merge`, bagaimana siklus penanganan perubahannya berbeda dari sisi *patch application*? Mengapa `git rebase` menulis ulang (*rewrite*) hash commit, dan apa bahaya strukturalnya jika diterapkan pada commit yang telah dipublikasikan ke remote branch bersama?

2. **Disaster Recovery dengan Git Reflog:**
   Seorang insinyur tidak sengaja menjalankan `git reset --hard HEAD~5` lalu melakukan `git push --force` ke branch eksperimental pribadinya, menyebabkan 5 commit penting hilang dari riwayat log biasa. Jelaskan langkah-demi-langkah rekonstruksi DAG menggunakan `git reflog`, dan bagaimana cara memulihkan branch tersebut ke posisi persis sebelum destruksi terjadi.

3. **Integritas dan Verifikasi Kriptografis (Commit Signing):**
   Bagaimana mekanisme *GPG/SSH Commit Signing* bekerja untuk memvalidasi identitas kontributor dalam rantai pasok perangkat lunak (*software supply chain security*)? Mengapa atribut `Author` dan `Committer` di metadata Git dapat dipalsukan (*spoofed*) dengan sangat mudah tanpa adanya signature cryptographic verification?

4. **Performa Repositori Skala Besar (Git Bloat & LFS):**
   Jelaskan dampak performa jika sebuah file biner berukuran 2 GB dimasukkan ke dalam Git tanpa Git LFS (*Large File Storage*), lalu diubah sebanyak 5 kali. Bagaimana arsitektur Git LFS mengubah cara Git menyimpan file biner tersebut (mekanisme *pointer file* vs *smudge/clean filter*) untuk menjaga ukuran `.git` tetap optimal?

5. **Monorepo Tooling: Sparse-Checkout dan Shallow Clone:**
   Dalam repositori monorepo enterprise sebesar 100 GB, waktu clone CI/CD menjadi bottleneck utama. Uraikan perbedaan mekanisme kerja, kelebihan, dan keterbatasan teknis dari implementasi `git clone --depth 1` (*shallow clone*) versus `git sparse-checkout` berbasis cone pattern dalam mengoptimalkan pipeline otomatisasi.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Kebocoran Kredensial Kritis pada Repositori Publik
*   **Konteks:** Seorang *junior developer* secara tidak sengaja meng-commit dan melakukan *push* file `.env` yang berisi private key cloud provider tingkat root ke branch `main`. Tiga puluh menit kemudian, insiden disadari setelah bot deteksi secret internal membunyikan alarm. Selama rentang waktu tersebut, ada 3 commit baru yang di-push oleh anggota tim lain di atas commit bermasalah tersebut.
*   **Pertanyaan Diagnostik & Solusi:**
    1. Mengapa eksekusi `git rm .env` diikuti commit baru sama sekali **tidak menyelesaikan** risiko keamanan ini?
    2. Rancang prosedur mitigasi darurat: bandingkan efektivitas penggunaan `git-filter-repo` (atau `BFG Repo-Cleaner`) versus `git rebase -i` untuk memusnahkan blob kredensial tersebut dari seluruh riwayat commit (*commit history*).
    3. Apa langkah operasional non-Git yang wajib dan kritis dilakukan segera setelah insiden terjadi, terlepas dari keberhasilan pembersihan riwayat Git?

### Skenario B: Race Condition dan Divergent History pada Branch Release
*   **Konteks:** Menjelang *deployment freeze*, tim Core Services dan tim Payment secara bersamaan melakukan hotfix mendesak pada branch `release/v2.4.0`. Keduanya mengambil basis dari commit yang sama. Tim Core Services melakukan `git push` normal terlebih dahulu. Tim Payment, mendapati push-nya ditolak (*non-fast-forward*), mengeksekusi `git pull` tanpa konfigurasi rekonsiliasi yang ketat, menghasilkan *merge commit* yang merusak integritas *cherry-pick* release pipeline otomatis.
*   **Pertanyaan Diagnostik & Solusi:**
    1. Apa perbedaan deterministik antara konfigurasi `pull.rebase false` (default), `pull.rebase true`, dan `pull.ff only` dalam konteks integritas branch release enterprise?
    2. Jika tim Payment tidak sengaja menimpa perubahan tim Core menggunakan `git push --force`, bagaimana cara Anda mendeteksi state remote sebelum insiden (menggunakan pointer `origin/release/v2.4.0` atau audit log server Git) dan mengembalikan commit yang hilang tanpa melakukan *downtime* pipeline?
    3. Bagaimana rancangan Branch Protection Rules yang seharusnya diimplementasikan untuk mencegah eksekusi *force push* sekaligus memastikan riwayat commit tetap linear?

### Skenario C: Krisis Arsitektur Branching Strategy: Gitflow vs. Trunk-Based
*   **Konteks:** Sebuah organisasi finansial memproses 40 rilis per hari menggunakan arsitektur microservices. Namun, repositori inti mereka masih mengadopsi model *classic Gitflow* dengan branch `develop`, `release/*`, `hotfix/*`, dan `main`. Tim engineering mengalami *merge hell* harian, proses integrasi tertunda berhari-hari, dan siklus verifikasi QA menjadi bottleneck kronis.
*   **Pertanyaan Diagnostik & Solusi:**
    1. Lakukan analisis teknis trade-off mengapa Gitflow gagal mendukung kapabilitas High-Frequency Deployment / DORA Metrics kelas *Elite Performer*.
    2. Rancang peta transformasi migrasi dari Gitflow ke *Trunk-Based Development* (TBD), termasuk strategi penanganan fitur yang belum selesai menggunakan *Feature Flags / Toggles*.
    3. Bagaimana peran *ephemeral preview environments* (berbasis short-lived branch) dalam menjamin kualitas kode tanpa memerlukan branch staging/develop yang persisten?

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekonstruksi & Sanitasi Repositori Enterprise Pasca-Insiden (Git Disaster Recovery Drill)

#### Problem:
Sebuah repositori microservice kritis mengalami kerusakan topologi dan insiden keamanan ganda:
1. Terjadi *commit injection* file binary dummy database (`db_dump.sql`, ukuran 450MB) yang menyebabkan clone pipeline CI/CD timeout.
2. Secret dummy API Token (`API_SECRET_KEY=prod-live-998877665544`) bocor pada commit dengan hash yang terletak 4 commit di belakang `HEAD`.
3. Terdapat merge commit bersilang (*diamond graph defect*) yang menyebabkan commit duplikat pada branch `main`.

#### Requirements:
Anda ditugaskan bertindak sebagai Site Reliability / Platform Engineer untuk menormalkan repositori tersebut secara lokal dan mempersiapkannya untuk audit:
1. **Sanitasi Total:** Gunakan tool modern (direkomendasikan `git-filter-repo`) untuk memusnahkan file biner 450MB dan mereduksi ukuran packfile Git di `.git/objects/pack/`.
2. **Pembersihan Secret:** Hapus nilai string `API_SECRET_KEY=...` dari riwayat commit tanpa mengubah pesan commit asli atau merusak author metadata.
3. **Linearisasi Riwayat:** Ubah topologi riwayat Git menjadi linear murni (Trunk-Based standard) menggunakan interaktif rebase; kompres (*squash*) fix-commit yang tidak perlu menjadi representasi *Conventional Commits* (`feat:`, `fix:`, `chore:`).
4. **Verifikasi & Enforce Hook:** Buat sebuah client-side hook `pre-commit` menggunakan Bash shell script murni yang secara lokal menolak *commit* jika:
   - Terdeteksi file yang berukuran > 5MB.
   - Terdeteksi string berformat `API_SECRET_KEY=` di dalam *staged changes*.

#### Constraints:
* Dilarang membuat repositori baru secara manual (wajib memodifikasi dan membersihkan *existing history*).
* Wajib mendemonstrasikan eksekusi `git reflog expire` dan `git gc --prune=now` untuk membersihkan dangling/unreachable objects.
* Hook harus ditulis dalam POSIX-compliant shell script (kompatibel dengan Linux/macOS).

#### Expected Output:
1. **Laporan Audit Repositori:** Screenshot/teks log output dari `git count-objects -vH` sebelum dan sesudah sanitasi yang membuktikan reduksi ukuran repositori.
2. **Topologi Bersih:** Tampilan grafik linear riwayat Git menggunakan `git log --graph --oneline --decorate`.
3. **Source Code Hook:** File `.git/hooks/pre-commit` yang fungsional dan teruji dengan *exit code* `1` saat validasi gagal.
4. **Dokumen Runbook:** Panduan 1 halaman langkah-langkah *force-push safely* menggunakan parameter `--force-with-lease` untuk mengunggah DAG baru ke remote server tanpa menimpa kerja developer lain yang tidak terafiliasi dengan insiden.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal Git: Blob, Tree, Commit, Tag, dan keterhubungannya di dalam Directed Acyclic Graph (DAG).
- [ ] Perbedaan fundamental antara *Working Tree*, *Index (Staging Area)*, dan *Git Repository (Object Store)*.
- [ ] Logika penentuan *Merge Base* (Ancestor) pada 3-Way Merge dan algoritma merge *ort*.
- [ ] Perbedaan destruktif dan mekanisme internal dari `git reset (--soft, --mixed, --hard)` vs `git revert`.
- [ ] Mengapa Git immutability menyebabkan rewriting history (`rebase`, `commit --amend`) mengubah seluruh SHA commit turunan (*cascading hash change*).
- [ ] Cara kerja `git reflog` sebagai jaring pengaman utama (*safety net*) sebelum referensi yang tidak terjangkau dibersihkan oleh `git gc`.
- [ ] Perbedaan teknis dan implikasi alur kerja antara Gitflow, GitHub Flow, dan Trunk-Based Development.
- [ ] Risiko keamanan dari credential exposure di riwayat Git dan keterbatasan penanganan berbasis `git rm`.

### Saya tidak perlu menghafal:
- [ ] Seluruh opsi flag CLI tingkat rendah (plumbing commands) seperti `git hash-object`, `git cat-file -p`, `git mktree` (cukup pahami fungsinya saat debugging arsitektural).
- [ ] Syntax kompleks regex untuk git hook (cukup pahami mekanisme exit code dan standard I/O dari hook).
- [ ] Algoritma kompresi zlib internal yang digunakan Git untuk mengompresi objek loose dan packfiles.
- [ ] Seluruh parameter konfigurasi formatting `git log --pretty=format:...` (dapat dilihat via dokumentasi referensi saat dibutuhkan).

### Saya harus bisa melakukan:
- [ ] Menavigasi, menganalisis, dan membedah objek Git secara langsung dari direktori `.git/` menggunakan perintah plumbing dasar.
- [ ] Membatalkan kesalahan commit, unstage perubahan, dan merekonstruksi commit yang hilang akibat force push/hard reset menggunakan `git reflog`.
- [ ] Menyelesaikan konflik merge dan rebase yang kompleks secara percaya diri di terminal, serta membatalkan proses rebase yang macet (`git rebase --abort`).
- [ ] Mengisolasi commit bermasalah di riwayat rilis menggunakan automated binary search via `git bisect`.
- [ ] Mengonfigurasi penandatanganan commit berbasis cryptographic keys (GPG atau SSH) dan memverifikasinya.
- [ ] Mengimplementasikan script otomatisasi Git Hooks (seperti `pre-commit` atau `commit-msg`) untuk standarisasi tim (misal: Conventional Commits enforcement).
- [ ] Menggunakan parameter `git push --force-with-lease` sebagai pengganti `--force` konvensional untuk mencegah insiden overwrite pada branch bersama.