# BAB 03: Quiz, Challenge, & Knowledge Check
**Penjelajahan Riwayat & Manajemen Perubahan (Commits & Diffs)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Pemetaan State Komparasi pada Tripartit Git
Jelaskan secara teknis dan semantik perbedaan status data yang diinspeksi oleh ketiga perintah berikut:
1. `git diff` (tanpa argumen tambahan)
2. `git diff --staged` (atau `git diff --cached`)
3. `git diff HEAD`

Bagaimana peran *Index* (Staging Area) bertindak sebagai mediator isolasi perubahan di antara *Working Tree* dan *Commit Graph* pada ketiga skenario tersebut?

---

### Soal 1.2: Anatomi dan Imutabilitas Objek Commit
Sebuah *Commit Object* di Git merupakan representasi kriptografis yang bersifat *immutable*. 
- Sebutkan komponen-komponen struktural yang menyusun payload dari sebuah *commit object* sebelum dilakukan *hashing*!
- Jelaskan mengapa perubahan sekecil tanda baca pada *commit message*, perubahan satu detik pada *author/committer timestamp*, atau perubahan pada data identitas developer menghasilkan *commit SHA* yang sepenuhnya berbeda, meskipun isi file sumber (*blob*) tidak berubah sama sekali!

---

### Soal 1.3: Semantik Navigasi Relatif: Caret (`^`) vs Tilde (`~`)
Diberikan sebuah graf riwayat Git non-linear yang mengandung *merge commits*. 
- Jelaskan perbedaan mendasar antara operator *Caret* (`^`) dan operator *Tilde* (`~`) dalam traversal pohon commit!
- Apa perbedaan semantik dan hierarki pencarian leluhur antara ekspresi `HEAD~2`, `HEAD^^`, dan `HEAD^2`?

---

### Soal 1.4: Paradigma Penyimpanan Git: Snapshot vs Per-File Delta
Sering terjadi miskonsepsi bahwa Git menyimpan riwayat perubahan sebagai kumpulan perbedaan (*delta/diff patches*) antar revisi seperti halnya VCS tradisional (misal: SVN). 
- Mengapa model Git diklasifikasikan sebagai *Directed Acyclic Graph (DAG) of snapshots* dan bukan *delta chain*?
- Jika Git menyimpan *full snapshot* pada setiap commit, bagaimana arsitektur internal Git mencegah pembengkakan (*bloat*) ukuran repositori ketika sebuah commit hanya memodifikasi 1 baris kode dalam proyek berukuran ratusan megabyte?

---

### Soal 1.5: Spektrum Resolusi Riwayat Menggunakan `git log`
Bandingkan efisiensi kognitif dan tujuan diagnostik dari visualisasi log berikut:
1. `git log --oneline --graph --decorate --all`
2. `git log -p` (atau `--patch`)
3. `git log --stat`

Kapan seorang Principal Engineer mewajibkan penggunaan `--stat` dibandingkan visualisasi graf ringkas saat melakukan *code review* atau *audit triage* pra-rilis?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Dikotomi Notasi Titik: Log vs Diff
Notasi dua titik (`..`) dan tiga titik (`...`) memiliki semantik yang berbanding terbalik secara konsep ketika diaplikasikan pada `git log` versus `git diff`.
- Jelaskan arti operasional dari `git log feature..main` versus `git log feature...main` (*symmetric difference*)!
- Jelaskan arti operasional dari `git diff feature..main` versus `git diff feature...main`!
- Mengapa `git diff feature...main` menjadi standar de-facto yang digunakan oleh GitHub/GitLab saat menampilkan *Pull Request diff view*?

---

### Soal 2.2: Algoritma Diffing dan Implikasinya pada Refactoring
Secara *default*, Git menggunakan algoritma *Myers diff*. Namun, Git juga menyediakan algoritma alternatif seperti *Minimal*, *Patience*, dan *Histogram* via flag `--diff-algorithm`.
- Masalah keterbacaan (*noise diff*) apa yang sering muncul pada algoritma *Myers* ketika developer melakukan pemindahan (*reordering*) blok fungsi atau pengubahan indentasi secara masif?
- Bagaimana algoritma *Histogram* atau *Patience* mengatasi anomali pencocokan sintaks kurung kurawal/baris kosong tersebut?

---

### Soal 2.3: Forensic Code Search: Pickaxe (`-S`) vs Regex Log (`-G`)
Anda ditugaskan mencari riwayat pengenalan dan penghapusan sebuah token kritis `SECRET_API_KEY`.
- Jelaskan perbedaan mendasar dalam cara kerja mesin pencari Git saat mengeksekusi `git log -S"SECRET_API_KEY"` dibandingkan dengan `git log -G"SECRET_API_KEY"`!
- Kasus modifikasi kode seperti apa yang akan tertangkap oleh flag `-G` namun **diabaikan** oleh flag `-S`?

---

### Soal 2.4: Heuristik Deteksi Rename dan Modifikasi Struktur File
Git tidak pernah mencatat metadata eksplisit bahwa suatu file telah di-*rename* atau di-*move* di dalam objek commit-nya.
- Bagaimana Git mendeteksi operasi *rename* secara dinamis ketika Anda menjalankan `git log --follow <file>` atau `git diff -M`?
- Parameter ambang batas kesamaan (*similarity index threshold*) apa yang digunakan Git, dan apa yang terjadi pada pelacakan riwayat jika sebuah file di-rename sekaligus mengalami *rewriting* logika lebih dari 60% baris kodenya?

---

### Soal 2.5: Algoritma Pencarian Regresi Deterministik via `git bisect`
Pada sebuah repositori monorepo dengan rentang 2.048 commit antara versi stabil terakhir (*tag* `v2.4.0`) dan commit *HEAD* yang bermasalah, ditemukan sebuah *silent regression*.
- Berapa jumlah iterasi maksimal pengujian yang dibutuhkan `git bisect` secara matematis untuk menemukan commit penyebab *bug*? Jelaskan kompleksitas waktunya ($O$)!
- Bagaimana cara menangani kondisi di mana salah satu titik commit uji di tengah proses biseksi mengalami *broken build* (tidak dapat di-compile karena dependensi rusak independen), sehingga Anda tidak bisa menentukan apakah commit tersebut *good* atau *bad*?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Monorepo – Regresi Performa Transaksi di Production
*Konteks:* Tepat setelah deployment tengah malam, sistem pemrosesan pembayaran mengalami lonjakan *latency* dari 80ms menjadi 2.400ms. Riwayat Git menunjukkan ada 380 PR yang di-*merge* ke branch `main` dalam 72 jam terakhir oleh 40 engineer berbeda. Tim infrastruktur mengonfirmasi bahwa utilisasi CPU melonjak pada modul kalkulasi diskon (`DiscountEngine.java`).

**Pertanyaan Diagnostik:**
1. Rancang urutan perintah Git CLI berkecepatan tinggi yang mengecualikan *merge commits* dan hanya memfilter perubahan spesifik pada file `src/main/java/com/engine/DiscountEngine.java` dalam rentang waktu 72 jam terakhir!
2. Jika kode tersebut ternyata diubah secara modular di beberapa commit berbeda, bagaimana Anda memadukan skrip Bash automated test runner dengan `git bisect run` untuk menemukan commit pemecah performa (*performance regression*) secara nirawak (*unattended*)?

---

### Skenario B: Anomali Diff PR – Bencana Karakter Line-Ending & Encoding
*Konteks:* Seorang junior developer mengajukan Pull Request (PR) yang diklaim hanya mengubah 2 baris validasi logika pada file konfigurasi `application.yml`. Namun, ketika dilihat di web UI GitHub dan via `git diff`, PR tersebut menampilkan bahwa **seluruh 3.500 baris file tersebut telah dihapus dan dibuat ulang**. Git menandai seluruh baris sebagai perubahan merah dan hijau.

```diff
- server:
-   port: 8080
+ server:
+   port: 8080
```

**Pertanyaan Diagnostik:**
1. Apa akar masalah internal Git terkait *line-ending standard* (`CRLF` vs `LF`) atau *Byte Order Mark* (BOM UTF-8) yang memicu anomali visual dan integritas data ini?
2. Perintah `git diff` dengan flag apa yang dapat Anda jalankan di terminal lokal untuk membuktikan hipotesis bahwa perubahannya murni variasi *whitespace* atau *line break*?
3. Solusi konfigurasi repositori jangka panjang apa (`.gitattributes`) yang harus di-commit ke repositori guna menghentikan insiden serupa terjadi kembali di seluruh mesin developer (lintas OS Windows, macOS, Linux)?

---

### Skenario C: Arsitektur & Trade-off Sistem – Extreme History Traversal Timeout
*Konteks:* Di sebuah perusahaan finansial besar, repositori *core-banking* telah berumur 12 tahun, berukuran 85 GB, dan memiliki lebih dari 1.200.000 commit. Setiap kali CI/CD pipeline atau developer menjalankan perintah `git log` atau `git diff` lintas branch rilis tahunan, operasi mengalami CPU freeze atau *memory exhaustion* (OOM).

**Pertanyaan Diagnostik:**
1. Dari perspektif arsitektur Git internals, mengapa traversal commit graph berskala jutaan node dapat melumpuhkan alokasi memori lokal?
2. Evaluasi trade-off dari implementasi fitur Git modern:
   - Penggunaan `commit-graph` file (`git commit-graph write`).
   - Shallow clone (`--depth`) vs Partial clone (`--filter=blob:none`).
3. Mengapa shallow clone berpotensi merusak akurasi investigasi `git merge-base` dan `git diff branchA...branchB` pada workflow CI/CD pipeline yang kompleks?

---

## 4. Chapter Challenge

### Tantangan Praktis: The Forensic Archeology Challenge (Post-Mortem Logic Bug Tracking)

#### Deskripsi Skenario
Sebuah bug silent corruption terjadi di production: algoritma pemotongan pajak pengguna memotong nilai 0% alih-alih 15% untuk kategori akun `ENTERPRISE`. Insiden ini menyebabkan kerugian finansial. 

Anda diberikan sebuah repositori Git simulasi dengan riwayat bercabang padat (ratusan commit dengan nama commit yang tidak jelas: "wip", "fix stuff", "update", "linting"). File target adalah `src/tax_calculator.py`.

#### Problem Requirements
1. **Identifikasi Commit Pelaku:** Temukan satu commit spesifik (*Commit SHA*, *Author*, dan *Date*) yang pertama kali memperkenalkan mutasi logika pengabaian pajak `ENTERPRISE` tersebut.
2. **Identifikasi Korban Diff:** Temukan commit lain yang secara keliru mengubah penamaan fungsi dari `calculate_enterprise_tax` menjadi `calc_ent_tax` tanpa memperbarui unit test, yang menyembunyikan bug tersebut dari pantauan automated tests.
3. **Penyusunan Forensic Report:** Ekstrak patch spesifik dari commit tersebut menggunakan perintah Git murni tanpa mengubah status *Working Tree* saat ini.

#### Constraints
- Wajib menggunakan **Git CLI murni** (dilarang menggunakan visual UI/GitHub/GitKraken).
- Dilarang merusak atau mengubah pointer branch saat ini (operasi harus *read-only* terhadap state repositori).
- Eksekusi pelacakan bug harus memanfaatkan integrasi antara `git bisect` atau `git log` dengan argumen *pickaxe/pathspec*.

#### Expected Output
Dokumentasikan laporan forensik teknis dalam format Markdown:
```markdown
### FORENSIC AUDIT REPORT: INCIDENT #TAX-009

1. Offending Commit Identifier:
   - Commit Hash: [SHA-1 / SHA-256 Penuh]
   - Author: [Nama & Email]
   - Commit Timestamp: [ISO-8601 Format]
   - Commit Subject: [Pesan Commit Asli]

2. Forensic Command Trace:
   - [Daftar CLI commands yang digunakan untuk mengisolasi commit secara deterministik]

3. Exact Logic Diff Patch:
   - [Output raw patch dari `git show <SHA> -- file` yang membuktikan baris cacat logika]

4. Architectural Root Cause:
   - [Penjelasan teknis 1 paragraf: Mengapa bug ini lolos dari deteksi diff konvensional]
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara objek commit, objek tree, dan objek blob dalam struktur basis data Git.
- [ ] Alur pergerakan data di antara tiga area: *Working Tree*, *Index/Staging Area*, dan *Repository/Commit Graph*.
- [ ] Representasi matematis DAG (*Directed Acyclic Graph*) pada Git dan bagaimana referensi commit menunjuk ke satu atau lebih *parent commits*.
- [ ] Perbedaan fungsional notasi dua titik (`..`) dan tiga titik (`...`) pada operasi komparasi `log` dan `diff`.
- [ ] Mekanisme deteksi konten *rename* berbasis heuristik kesamaan konten, bukan pelacakan metadata file.
- [ ] Kompleksitas pencarian biner ($O(\log N)$) pada `git bisect` dalam mengisolasi regresi kode.
- [ ] Implikasi normalisasi karakter *line-ending* (`LF` vs `CRLF`) terhadap kalkulasi hash diff Git.

### Saya tidak perlu menghafal:
- [ ] Seluruh flag CLI langka dan obscure dari `git log` (cukup pahami flag vital: `-p`, `--stat`, `--oneline`, `--graph`, `-S`, `-G`, `--follow`).
- [ ] Rincian implementasi matematis dari algoritma komparasi teks Myers secara mendalam pada level kode C Git.
- [ ] Nilai byte heksadesimal representasi header objek Git sebelum di-*deflate* menggunakan Zlib compression.

### Saya harus bisa melakukan:
- [ ] Menginspeksi modifikasi yang belum di-stage menggunakan `git diff`.
- [ ] Menginspeksi modifikasi yang sudah di-stage tetapi belum di-commit menggunakan `git diff --staged`.
- [ ] Melacak riwayat modifikasi sebuah baris kode atau string fungsi tertentu sepanjang sejarah repositori menggunakan *Pickaxe* (`git log -S<string>`).
- [ ] Membatasi visualisasi riwayat log berdasarkan rentang tanggal (`--since`, `--until`), batas commit (`-n`), atau filter penulis (`--author`).
- [ ] Mengaudit seluruh riwayat sebuah file meskipun file tersebut telah dipindahkan jalurnya atau diubah namanya menggunakan `git log --follow <path>`.
- [ ] Menavigasi pohon commit secara relatif menggunakan referensi HEAD (`HEAD~`, `HEAD^`, `HEAD~n`).
- [ ] Mengotomatisasi pelacakan akar penyebab regresi (*bug hunting*) dengan merangkaikan `git bisect` bersama skrip unit test otomatis.
- [ ] Mengonfigurasi file `.gitattributes` untuk menegakkan konsistensi normalisasi *end-of-line* di seluruh sistem operasi anggota tim.