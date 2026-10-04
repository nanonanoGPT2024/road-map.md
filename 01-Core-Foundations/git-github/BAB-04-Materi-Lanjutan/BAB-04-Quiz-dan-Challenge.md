# BAB 04: Quiz, Challenge, & Knowledge Check
**History Rewriting, Recovery, and Auditing**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Prinsip Immutability pada Directed Acyclic Graph (DAG) Git**  
   Secara arsitektural, setiap *commit object* diidentifikasi oleh kalkulasi kriptografis (SHA-1 atau SHA-256). Jelaskan mengapa memodifikasi pesan commit tertua dari sebuah branch secara matematis memaksa Git untuk menulis ulang (*rewrite*) identitas hash dari seluruh commit turunannya (*descendant commits*) hingga ke `HEAD`.

2. **Diferensiasi Mekanisme Internal Mutasi Head: `git reset` Variants**  
   Analisis perbedaan mendalam antara `git reset --soft`, `git reset --mixed`, dan `git reset --hard` dari perspektif status transisi tiga komponen arsitektur Git: pointer `HEAD`, *Index* (Staging Area), dan *Working Directory*. Sertakan status integritas data pada masing-masing state.

3. **Mekanisme Pelacakan dan Retensi Objek: `git reflog` vs `git log`**  
   Jelaskan mengapa `git log` gagal menampilkan commit yang telah terlepas dari tip branch (*orphaned/unreachable commits*) pasca-rebase, sementara `git reflog` mampu melacaknya. Apa batas waktu retensi default objek di reflog sebelum Git Garbage Collector (`git gc`) mengeksekusi *pruning*?

4. **Integritas Shared Branch: `git revert` vs `git reset`**  
   Mengapa pada *public/shared branch* (misal: `main` atau `release`), pembatalan perubahan wajib menggunakan `git revert` alih-alih `git reset` atau `git rebase -i`? Jelaskan dampaknya terhadap kolaborator lain yang telah melakukan *pull* terhadap branch tersebut.

5. **Anatomi Eksekusi `git cherry-pick`**  
   Saat Anda mengeksekusi `git cherry-pick <commit-hash>`, Git mengaplikasikan perubahan dari commit tersebut ke branch target. Mengapa operasi ini selalu menghasilkan SHA hash baru meskipun isi kode (*patch diff*), author, dan commit message identik dengan commit aslinya?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Automasi Root-Cause Analysis via `git bisect run`**  
   Bagaimana mekanisme internal `git bisect` dalam mengisolasi regresi menggunakan algoritma binary search pada DAG? Jelaskan arti spesifik dari kode keluar (*exit codes*) skrip automasi: `0`, `125`, dan `1-127 (kecuali 125)`, serta bagaimana Git menangani commit yang ditandai *untestable* di tengah merge commit.

2. **Analisis Semantik Pencarian: `git log -S<string>` (Pickaxe) vs `git log -G<regex>`**  
   Jelaskan perbedaan mendasar antara kedua parameter tersebut dalam mendeteksi riwayat kode. Pada skenario mana `git log -S` tidak akan memicu hasil meskipun string yang dicari ada di dalam diff, dan bagaimana perbedaan algoritma filtering keduanya memengaruhi beban I/O pada repository berskala puluhan gigabyte?

3. **Restorasi State Tanpa Referensi: Traversal Dangling Objects**  
   Jika seorang engineer menghapus branch lokal dan secara bersamaan membersihkan reflog secara prematur (`git reflog expire --expire=now --all`), bagaimana Anda memanfaatkan `git fsck --lost-found` untuk merekonstruksi commit yang hilang dari database `.git/objects/`? Jelaskan bagaimana Anda membedakan tipe objek *dangling commit* dan *dangling blob*.

4. **Scrubbing Secrets: `git-filter-repo` vs `git filter-branch`**  
   Mengapa komunitas Git secara resmi mendeprekasi `git filter-branch` demi `git-filter-repo` (atau BFG Repo-Cleaner)? Analisis dari segi arsitektur I/O disk, pembuatan subshell per-commit, manipulasi DAG tree, dan jaminan keamanan penulisan ulang referensi (*ref namespaces*).

5. **Mekanisme Garbage Collection Tuning & Dangling Commit Preservation**  
   Jelaskan relasi parameter konfigurasi `gc.reflogExpire`, `gc.reflogExpireUnreachable`, dan `gc.pruneExpire`. Jika sebuah insiden penghapusan branch terjadi di remote bare repository yang tidak memiliki reflog aktif, apa yang menentukan apakah commit-commit tersebut masih dapat diselamatkan sebelum `git gc --prune=now` dieksekusi oleh server maintenance cron?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Kebocoran Kredensial Produksi pada Active Monorepo
*Konteks*: Seorang developer secara tidak sengaja memasukkan private key AWS (`credentials.json`) ke branch `main` pada sebuah monorepo berukuran 40 GB dengan 200+ kontributor aktif. Commit tersebut telah terdorong (*pushed*) ke remote 3 hari yang lalu, dan di atas commit tersebut telah ada 75 commit baru yang di-merge oleh tim lain.
* **Pertanyaan Diagnostik & Solusi:**
  1. Rancang protokol insiden darurat: Apa tindakan pertama yang harus diambil pada level infrastruktur AWS sebelum menyentuh Git?
  2. Tuliskan urutan pipeline perintah menggunakan `git-filter-repo` untuk membersihkan file tersebut secara permanen dari seluruh history commit, tags, dan branches tanpa merusak commit history lainnya.
  3. Bagaimana strategi mitigasi agar 200 kontributor lokal tidak menginjeksikan kembali (*re-introduce*) commit lama yang membawa secret tersebut saat mereka melakukan `git pull` berikutnya?

### Skenario B: Force-Push Race Condition & Data Recovery pada Bare Repository
*Konteks*: Developer A melakukan *interactive rebase* untuk merapikan 3 commit miliknya, lalu menjalankan perintah destruktif `git push --force origin feature/billing`. Tanpa disadarinya, 10 menit sebelumnya, Developer B telah me-merge 15 commit penting ke branch yang sama. Karena Developer A tidak menggunakan `--force-with-lease`, commit milik Developer B terlepas dari pointer branch di remote bare repository. Remote bare repository tidak memiliki reflog yang aktif secara default.
* **Pertanyaan Diagnostik & Solusi:**
  1. Bagaimana cara mendiagnosis commit SHA terakhir milik Developer B yang tertimpa jika log audit CI/CD atau Pull Request UI tidak dapat diakses?
  2. Di mana saja jejak commit Developer B yang hilang tersebut dapat diekstraksi (baik dari sisi developer lokal maupun langsung di server remote via object store)?
  3. Formulasikan perintah exact recovery untuk mengembalikan branch `feature/billing` ke state yang menggabungkan pekerjaan Developer A dan Developer B secara non-destruktif.

### Skenario C: Regresi Skala Besar Terhalang Code Formatting Massacre
*Konteks*: Ditemukan memory leak critical pada aplikasi backend yang diperkirakan masuk antara tag `v2.1.0` (stable) dan `v2.2.0` (leaking). Rentang tersebut mencakup 1.200 commit. Masalahnya, di commit ke-400, seorang lead engineer menjalankan auto-formatting global (Prettier/Black) yang menyentuh 95% baris kode di seluruh repository. Akibatnya, `git blame` dan manual inspection menjadi tidak berguna.
* **Pertanyaan Diagnostik & Solusi:**
  1. Bagaimana Anda mengonfigurasi `git bisect` agar secara otomatis mengeksekusi integrasi test suite (misal: `npm test` atau `pytest`) yang memvalidasi kebocoran memori pada tiap iterasi binary search?
  2. Jika commit reformat (commit ke-400) menyebabkan test suite gagal berjalan karena dependency breaking sementara (bukan karena memory leak), bagaimana skrip bisect harus merespons menggunakan exit status agar Git melompati (*skip*) commit tersebut secara presisi?
  3. Bagaimana Anda mengonfigurasi `.git-blame-ignore-revs` secara institusional di tim agar insiden reformatting massal ini tidak merusak utilitas audit `git blame` selamanya?

---

## 4. Chapter Challenge

### Tantangan Praktis: The Forensic Post-Mortem & Repository Salvage Pipeline

#### Problem Statement
Sebuah insiden deployment kritis terjadi:
1. Sebuah branch rilis bernama `release/v4.12` dirusak oleh rebase kotor yang menggabungkan commit experimental, menghapus 5 commit fitur krusial, dan memasukkan file rahasia perusahaan (`internal_auth_token.pem`).
2. Seseorang mengeksekusi `git push --force` ke remote server.
3. Test suite otomatis mendeteksi adanya breaking bug misterius yang tersembunyi di antara 50 commit terakhir pada branch tersebut.
Anda ditunjuk sebagai Incident Lead untuk membersihkan file sensitif, memulihkan commit yang hilang, dan mengisolasi commit yang membawa bug secara presisi menggunakan automasi.

#### Requirements
1. **Salvage**: Temukan dan pulihkan 5 commit fitur yang hilang akibat force-push dengan memanfaatkan simulasi reflog lokal atau manipulasi dangling pointer.
2. **Purge**: Hapus file `internal_auth_token.pem` dari seluruh commit history branch tanpa mengubah histori pesan commit atau author asli dari commit legal lainnya.
3. **Bisect Automation**: Tulis bash script executable (`bisect_validator.sh`) yang mendeteksi bug (simulasikan kegagalan logika via script yang me-return `exit 1` jika fungsi tertentu broken, dan `exit 0` jika normal). Jalankan `git bisect run` untuk menandai commit offending pertama secara otomatis.
4. **Audit Log**: Hasilkan visualisasi log linear (`git log --graph --oneline`) yang bersih, membuktikan secret telah hilang dan kelima commit fitur telah terintegrasi kembali dengan benar.

#### Constraints
- Dilarang membuat repositori baru; seluruh perbaikan harus dilakukan in-place pada repositori yang terkontaminasi.
- Seluruh commit SHA yang dihasilkan pasca-sanitisasi harus terverifikasi integritasnya melalui `git fsck --full`.
- Penulisan ulang history wajib mempertahankan original author date dan author name.

#### Expected Output
1. File artefak `salvage_audit.log` yang berisi:
   - Output log commit hash yang terisolasi oleh `git bisect run`.
   - Laporan verifikasi `git log -S "internal_auth_token.pem"` yang menghasilkan output kosong (membuktikan secret purged).
   - Tampilan ringkas tree history 10 commit terakhir yang bersih dan fungsional.
2. Skrip `bisect_validator.sh` yang idempotent dan menangani non-zero exit code secara deterministik.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal DAG Git: hubungan hierarkis antara *commit*, *tree*, *blob*, dan *annotated tag*.
- [ ] Dampak cascading cryptographic hash saat memodifikasi parent tree pada commit terdahulu.
- [ ] Perbedaan operasional dan risiko integritas antara `git push --force` vs `git push --force-with-lease` vs `--force-if-includes`.
- [ ] Siklus hidup objek unreachable dan algoritma pruning Git Garbage Collection (`git gc`).
- [ ] Algoritma pickaxe (`-S`) vs regular expression diff search (`-G`) dalam pelacakan riwayat perubahan kode.
- [ ] Penanganan boundary commit, merge base, dan un-testable revisions pada `git bisect`.

### Saya tidak perlu menghafal:
- [ ] Seluruh argument/flags legacy dari `git filter-branch` yang telah digantikan oleh `git-filter-repo`.
- [ ] Rumus matematika internal dari hashing SHA-1 atau SHA-256.
- [ ] Struktur byte header level rendah dari packfiles (`.pack`) dan pack-index (`.idx`).

### Saya harus bisa melakukan:
- [ ] Melakukan interactive rebase tingkat lanjut: `squash`, `fixup`, `edit`, `reword`, dan reorganisasi urutan commit tanpa kehilangan data.
- [ ] Memulihkan commit yang terhapus secara sengaja maupun tidak menggunakan `git reflog` dan pointer dereferencing.
- [ ] Mengekstraksi objek yang terputus dari DAG menggunakan `git fsck --lost-found`.
- [ ] Menulis skrip automasi verifikasi berbasis testing suite untuk dieksekusi secara otonom oleh `git bisect run`.
- [ ] Membersihkan file sensitif atau artefak biner besar secara permanen dari history repositori menggunakan `git-filter-repo`.
- [ ] Mengonfigurasi dan memelihara file `.git-blame-ignore-revs` untuk mengeliminasi noise refactoring skala masif dari output auditing.