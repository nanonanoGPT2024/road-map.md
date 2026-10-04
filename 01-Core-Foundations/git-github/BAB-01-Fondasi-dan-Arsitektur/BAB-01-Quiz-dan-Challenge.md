# BAB 01: Quiz, Challenge, & Knowledge Check
**Core Architecture & Plumbing vs. Porcelain**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Struktur Header dan Formulasi Hash Objek Git**  
   Git adalah sistem penyimpanan *content-addressable*. Saat Git melakukan hashing pada sebuah file (misalnya untuk membuat `blob`), jelaskan secara spesifik format header yang disisipkan sebelum payload data sebelum proses komputasi SHA-1/SHA-256 dilakukan. Mengapa format `type <size>\0<content>` ini krusial untuk mencegah serangan tabrakan tipe objek (*type-confusion collision*)?

2. **Divergensi Arsitektural: Blob vs. Tree Object**  
   Jelaskan perbedaan struktural mendasar antara `blob` dan `tree`. Mengapa Git mendesain `blob` murni hanya sebagai penyimpan data mentah tanpa metadata file (seperti nama file, path, dan permission bits), dan bagaimana `tree` object merekonstruksi struktur direktori hierarkis dari pemisahan tanggung jawab tersebut?

3. **Mekanisme Stat Cache pada Index (`.git/index`)**  
   Index atau Staging Area bukan sekadar daftar staging sementara, melainkan file biner yang menyimpan struktur data kompleks. Bagaimana Git memanfaatkan metadata filesystem (seperti `mtime`, `ctime`, `inode`, `file size`, dan `file mode`) di dalam `.git/index` untuk mendeteksi perubahan file di *Working Directory* secara instan tanpa perlu membaca dan menghitung ulang hash seluruh isi file?

4. **Siklus Hidup Data: Plumbing Transition Pipeline**  
   Uraikan urutan eksekusi *plumbing commands* tingkat rendah yang setara dengan eksekusi *porcelain* standar `git add .` dan `git commit -m "feat: init"`. Jelaskan bagaimana data mengalir mulai dari `git hash-object`, `git update-index`, `git write-tree`, hingga `git commit-tree`, serta bagaimana `.git/refs/heads/<branch>` akhirnya diperbarui.

5. **Immutabilitas dan Formulasi Commit DAG**  
   Sebuah *commit object* bersifat *immutable* (tidak dapat diubah). Sebutkan seluruh komponen payload teks yang dikandung oleh sebuah *commit object*. Mengapa perubahan satu karakter pada *commit message* atau pergeseran 1 detik pada *committer timestamp* akan merombak seluruh identitas hash commit tersebut dan seluruh commit turunan (*descendants*) di dalam DAG (*Directed Acyclic Graph*)?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Cascading Corruption & DAG Verification**  
   Misalkan sebuah *bit flip* fisik terjadi pada disk tepat di dalam file loose object bertipe `tree` pada commit yang dibuat satu tahun lalu. Jika commit tersebut memiliki 500 commit turunan di atasnya:
   - Bagaimana perilaku `git fsck --full` saat memverifikasi integritas repositori?
   - Mengapa korupsi pada `tree` tua tersebut tidak serta merta merusak SHA commit turunan teratas secara matematis, namun merusak kemampuan checkout atau *diff traversal* ke commit yang terinfeksi?

2. **Resolusi Symbolic Ref dan Anatomi Detached HEAD**  
   Jelaskan perbedaan representasi internal pada filesystem antara kondisi branch normal dengan kondisi **Detached HEAD** di dalam file `.git/HEAD`. Bagaimana perintah plumbing `git symbolic-ref HEAD` merespons kedua kondisi tersebut, dan apa mekanisme exit code yang dihasilkan ketika repositori berada dalam status detached?

3. **Konkurensi dan Atomisitas Reference Update**  
   Ketika dua proses Git (misalnya, dua push hooks paralel atau concurrent CI/CD workers) mencoba memperbarui reference yang sama secara simultan, bagaimana Git mencegah race condition? Jelaskan mekanisme *lockfile pattern* (`.git/refs/heads/<branch>.lock`) dan bagaimana syscall atomik (seperti `rename()`) menjamin integritas referensi Git.

4. **Dekomposisi Biner Tree Object vs. Output Cat-File**  
   Ketika Anda menjalankan `git cat-file -p <tree-hash>`, Git mencetak output yang mudah dibaca manusia (berisi mode, tipe, SHA, dan filename). Namun, bagaimana representasi biner mentah (*raw binary serialization*) dari sebuah `tree` object disimpan di disk setelah didekompresi menggunakan `zlib`? Jelaskan bagaimana Git memisahkan boundary antar entry dalam satu tree.

5. **Mitigasi Hash Collision dan Penanganan Loose Object Namespace**  
   Di dalam direktori `.git/objects`, Git membagi 40 karakter hash heksadesimal menjadi struktur `2-karakter-subdirektori/38-karakter-filename`. 
   - Apa alasan performa tingkat OS (khususnya filesystem inode limits dan directory lookup overhead) di balik pemecahan 2/38 ini?
   - Bagaimana arsitektur Git mendeteksi jika terjadi *hash collision* aktual ketika objek baru yang ditulis memiliki hash yang identik dengan objek lama tetapi payload-nya berbeda?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Monorepo Bottleneck & Index Sprawl pada Skala Enterprise
Sebuah monorepo enterprise sebesar 65 GB dengan 1,2 juta file mengalami degradasi performa ekstrem: eksekusi `git status` membutuhkan waktu hingga 58 detik pada mesin developer, padahal hanya ada satu file `.ts` yang dimodifikasi. Pemeriksaan awal menunjukkan bahwa direktori `.git/objects` memiliki lebih dari 800.000 *loose objects* dan ukuran file `.git/index` membengkak hingga 280 MB.
- **Diagnostik:** Apa yang menyebabkan `git status` berjalan sangat lambat ditinjau dari arsitektur `.git/index` dan stat cache?
- **Root Cause:** Mengapa *loose object sprawl* memperburuk I/O disk sistem operasi?
- **Remediasi Plumbing:** Rancang urutan perintah plumbing dan optimasi internal untuk membersihkan, memadatkan objek, dan membangun ulang index cache guna memangkas latensi `git status` kembali ke sub-detik (< 1 detik).

### Skenario B: Race Condition & Ref Locking Failure pada CI/CD Multi-Agent
Sistem build orchestration menjalankan 8 agent paralel yang bekerja pada shared workspace (menggunakan shared network volume NFSv4). Setiap agent mencoba mencatat hasil deployment ke branch audit logs dengan mengeksekusi pipeline custom yang mengupdate Git reference secara langsung. Secara acak, 3 dari 8 agent mengalami *crash* dengan pesan error fatal:
```text
fatal: Unable to create '/workspace/.git/refs/heads/audit-log.lock': File exists.
```
Setelah insiden tersebut, ditemukan beberapa commit yang dibuat agent tertinggal sebagai *dangling commit* (tidak terikat pada ref branch mana pun).
- **Diagnostik:** Jelaskan mengapa arsitektur ref-locking Git mengalami kegagalan fatal pada shared network filesystem seperti NFS.
- **Analisis Dampak:** Mengapa kegagalan pembuatan `.lock` dapat menghasilkan *dangling commits* di object store?
- **Arsitektur Solusi:** Bagaimana mendesain ulang proses update ref pada lingkungan konkuren tanpa merusak atomisitas dan integritas commit history menggunakan perintah plumbing `git update-ref --stdin`?

### Skenario C: Custom Git Storage Engine untuk High-Security Audit Ledger
Sebuah bank digital ingin memanfaatkan Git internal sebagai immutable event-store audit-trail untuk dokumen transaksi finansial. Dokumen transaksi berformat JSON masuk dengan throughput 200 transaksi/detik. Arsitek sistem melarang penggunaan perintah *porcelain* (`git add`, `git commit`) karena overhead I/O dari Working Directory dianggap tidak dapat diterima (*unacceptable I/O latency*).
- **Trade-off Arsitektural:** Evaluasi perbandingan antara menggunakan *bare repository* murni dengan operasi in-memory plumbing (`hash-object --stdin`, `mktree`, `commit-tree`) melawan pendekatan tradisional dengan filesystem working directory.
- **Bottleneck Analisis:** Di mana titik jenuh (*bottleneck threshold*) dari penyimpanan loose object Git pada throughput tinggi tersebut, dan kapan strategi *packfile generation* (`git pack-objects`) harus dipicu secara programmatic?
- **Integritas:** Bagaimana memvalidasi rantai hash commit programmatically untuk membuktikan kepada auditor regulasi perbankan bahwa tidak ada riwayat transaksi yang mengalami manipulasi (*tampering*)?

---

## 4. Chapter Challenge

### Tantangan Praktis: Zero-Porcelain Engine (Membangun Commit Graph Murni Menggunakan Plumbing)

#### Problem
Anda ditugaskan membuktikan pemahaman mendalam tentang arsitektur Git dengan cara menginisiasi repositori, membuat file, mengindeks struktur direktori hierarkis multi-level, membuat commit bercabang, dan melakukan merge graph **tanpa sekali pun menggunakan perintah Porcelain tingkat tinggi**. 

DILARANG KERAS menggunakan perintah berikut:
- `git add`
- `git commit`
- `git checkout`
- `git branch`
- `git merge`
- `git status`

#### Requirements
1. Inisialisasi repositori Git kosong secara manual (hanya boleh menggunakan `git init`).
2. Buat pohon direktori berikut langsung ke dalam Git Object database:
   ```text
   ├── app/
   │   └── server.py   (Isi: "print('v1.0-alpha')\n")
   └── config.json     (Isi: "{\"env\": \"production\"}\n")
   ```
   *File permissions: `server.py` harus memiliki executable bit aktif (`100755`), sedangkan `config.json` normal (`100644`).*
3. Buat Commit Object pertama (Root Commit) dengan identitas:
   - Author/Committer: `Principal Engineer <architect@enterprise.internal>`
   - Message: `feat: architectural bootstrap`
4. Buat branch baru bernama `feature/metrics` yang merujuk pada commit pertama tadi, murni menggunakan manipulasi ref tingkat rendah.
5. Buat commit kedua pada branch `feature/metrics` yang menambahkan file:
   ```text
   └── app/
       ├── metrics.py   (Isi: "def collect(): pass\n", mode: 100644)
       └── server.py   (Isi: "print('v1.1-metrics')\n", mode: 100755)
   ```
6. Arahkan pointer `HEAD` repositori Anda ke branch `feature/metrics` secara manual tanpa merusak tracking working tree.

#### Constraints
- Seluruh manipulasi state harus dieksekusi secara manual via CLI menggunakan kombinasi: `git hash-object`, `git update-index`, `git write-tree`, `git commit-tree`, `git update-ref`, `git symbolic-ref`, dan `git mktree`.
- Integritas data repositori harus 100% valid tanpa *dangling objects* atau *broken links*.

#### Expected Output
1. Output validasi integritas repositori:
   ```bash
   $ git fsck --full --strict
   # Harus menghasilkan output bersih tanpa error, tanpa dangling blob/tree/commit!
   ```
2. Output riwayat commit graph:
   ```bash
   $ git log --graph --oneline --decorate --all
   * <hash-commit-2> (HEAD -> refs/heads/feature/metrics) feat: implement metrics
   * <hash-commit-1> (refs/heads/main) feat: architectural bootstrap
   ```
3. Verifikasi payload commit via:
   ```bash
   $ git cat-file -p HEAD
   tree <tree-hash>
   parent <commit-1-hash>
   author Principal Engineer <architect@enterprise.internal> <timestamp> +0000
   committer Principal Engineer <architect@enterprise.internal> <timestamp> +0000

   feat: implement metrics
   ```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Format spesifik header objek Git (`type size\0content`) dan bagaimana representasi SHA-1/SHA-256 mengunci integritas kriptografis objek.
- [ ] Peran 4 tipe objek dasar Git (`blob`, `tree`, `commit`, `tag`) dan perbedaan isolasi fungsionalnya di dalam *Object Store*.
- [ ] Perbedaan fungsionalitas dan use-case antara perintah *Plumbing* (mekanisme internal) dan *Porcelain* (antarmuka developer).
- [ ] Arsitektur internal berkas biner `.git/index` sebagai stat cache performa tinggi antara Working Directory dan Object Store.
- [ ] Mekanisme resolusi referensi Git: Direct refs (`.git/refs/heads/*`), Symbolic refs (`.git/HEAD`), dan Packed refs (`.git/packed-refs`).
- [ ] Karakteristik *Directed Acyclic Graph* (DAG) dan bagaimana prinsip immutabilitas menjamin *tamper-proof history*.
- [ ] Mekanisme atomisitas file locking (`.lock`) dalam mencegah konkurensi koruptif pada update pointer reference.

### Saya tidak perlu menghafal:
- [ ] Struktur bit-level offset spesifik (binary packing format) internal dari file `.git/index` (seperti offset bit per-entry index format v2/v3/v4).
- [ ] Algoritma kompresi internal library `zlib` / Huffman coding yang digunakan Git saat menulis objek ke disk.
- [ ] Kode sumber C Git untuk syscall atomik pointer swapping pada arsitektur POSIX vs Windows.

### Saya harus bisa melakukan:
- [ ] Memeriksa tipe, ukuran, dan payload dari objek apa pun di dalam repositori menggunakan `git cat-file -t`, `git cat-file -s`, dan `git cat-file -p`.
- [ ] Menghitung hash objek secara deterministik tanpa menulis ke database menggunakan `git hash-object` (dan menulisnya dengan flag `-w`).
- [ ] Membangun dan memodifikasi *tree object* secara dinamis menggunakan perintah plumbing `git mktree` atau `git write-tree`.
- [ ] Menjalin commit baru secara manual ke dalam DAG menggunakan `git commit-tree` dengan mendefinisikan *parent nodes* eksplisit.
- [ ] Menggeser branch pointers dan merekayasa symbolic refs secara atomik dan aman menggunakan `git update-ref` dan `git symbolic-ref`.
- [ ] Menginvestigasi dan mendiagnosis kerusakan repositori (*repository corruption*) menggunakan `git fsck --full`.