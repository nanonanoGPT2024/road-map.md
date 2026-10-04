# Bab 02 Module 01: Arsitektur Internal Git: Model Objek dan Content-Addressable Storage

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Membedah dan mengonstruksi ulang struktur data internal Git (`.git/objects`) secara manual menggunakan perintah *plumbing*.
- Menganalisis relasi struktural antara empat objek fundamental Git: `blob`, `tree`, `commit`, dan `annotated tag`.
- Menjelaskan mekanisme *Content-Addressable Storage* berbasis hashing kriptografis (SHA-1/SHA-256) serta implikasi integritas data (*cryptographic immutability*).
- Melacak *pointer mutation*, kompresi `zlib`, dan pemecahan dependensi Directed Acyclic Graph (DAG) langsung dari tingkat *filesystem*.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, Anda harus memahami:
- Konsep dasar shell Unix/Linux (navigasi direktori, visualisasi file biner, manipulasi I/O pipe).
- Prinsip dasar fungsi *cryptographic hash* (input deterministik, *one-way function*, resistansi tabrakan).
- Pemahaman dasar pengoperasian Git tingkat permukaan (*porcelain*): `git init`, `git add`, dan `git commit`.

---

### 3. Concept
Secara fundamental, Git bukanlah sistem pelacak perbedaan file (*delta-based version control*) seperti VCS generasi pendahulu (CVS, SVN). Git adalah **Content-Addressable Key-Value Store** berbasis filesystem yang dibungkus oleh antarmuka sistem kontrol versi terdistribusi.

Inti dari sistem penyimpanan Git bekerja dengan aturan matematis deterministik:
$$\text{Object ID (Key)} = \text{Hash}(\text{header} + \text{content})$$

Header Git memiliki format universal:
$$\text{header} = \text{"<type> <size>\0"}$$
di mana `<type>` adalah salah satu dari tipe objek valid, `<size>` adalah ukuran muatan data dalam satuan *byte* (representasi ASCII), diikuti oleh karakter null byte (`\0` atau `0x00`).

Setiap kali data disimpan ke dalam Git:
1. Header dan payload dikompilasi menjadi satu kesatuan byte.
2. Hash SHA-1 (40 karakter heksadesimal) atau SHA-256 (64 karakter heksadesimal) dihitung dari struktur byte tersebut. Hash ini bertindak sebagai *Key*.
3. Data dikompresi menggunakan algoritma `zlib` (level kompresi *deflate* standar).
4. Hasil kompresi ditulis ke dalam path `.git/objects/hh/hhhh...`, di mana 2 karakter pertama hash menjadi nama direktori dan 38/62 karakter sisanya menjadi nama file. Ini bertindak sebagai *Value*.

Setiap mutasi pada payload atau metadata akan menghasilkan hash yang berbeda, mewujudkan sifat *immutability* absolut. Objek lama tidak pernah ditimpa secara in-place; Git selalu menulis objek baru dan memindahkan pointer penunjuk (*references*).

---

### 4. Why
Memahami lapisan *porcelain* (antarmuka tingkat tinggi seperti `git commit`, `git checkout`) saja tidak cukup untuk menangani insiden korupsi repositori, perancangan arsitektur *monorepo* skala besar, atau optimasi kinerja Git dalam jalur *pipeline* CI/CD enterprise. 

Urgensi teknis memahami arsitektur internal ini meliputi:
- **Deteksi & Resolusi Korupsi Data:** Mampu memulihkan repositori yang rusak akibat *hardware failure*, disk terputus, atau proses Git yang terhenti secara abnormal menggunakan manipulasi langsung pada basis data objek.
- **Efisiensi Penyimpanan Skala Besar:** Mengidentifikasi penyebab membengkaknya ukuran repositori (misal: penyisipan artefak biner yang tidak didelegasikan ke Git LFS) dengan menganalisis ukuran `blob` mentah.
- **Eksekusi Custom Tooling & Automation:** Membangun parser, auditor keamanan (pemeriksaan kebocoran rahasia secara deterministik), atau integrasi custom Git berbasis operasi *plumbing* yang jauh lebih cepat daripada memanggil sub-shell *porcelain*.

---

### 5. What
Git mendefinisikan 4 tipe objek fundamental yang membentuk fondasi DAG:

1. **Blob (*Binary Large Object*):**
   - Hanya menyimpan data mentah isi file.
   - **Tidak** menyimpan metadata file (nama file, *permission mode* Unix, stempel waktu modifikasi). Dua file dengan nama berbeda namun berisikan karakter yang identik akan merujuk ke satu objek blob yang sama persis.
2. **Tree:**
   - Merepresentasikan sebuah entitas direktori.
   - Berisi daftar pemetaan yang memuat: *file mode* (misal `100644` untuk normal file, `100755` untuk executable, `040000` untuk sub-direktori), tipe objek yang dirujuk (`blob` atau `tree`), hash SHA dari objek target, dan nama file/direktori.
3. **Commit:**
   - Menyimpan status snapshot pada suatu waktu.
   - Metadata commit terdiri dari: *pointer* ke satu objek `root tree`, *pointer* ke objek `parent commit` (bisa bernilai nol untuk *root commit*, satu untuk commit biasa, atau lebih dari satu untuk *merge commit*), data *author* (nama, email, timestamp), data *committer*, dan pesan log commit (*commit message*).
4. **Annotated Tag:**
   - Objek permanen yang menunjuk langsung ke commit tertentu (atau objek lainnya).
   - Memiliki payload metadata mandiri: penanda tangan, tanggal pembuatan, pesan tag (*tag message*), dan opsional tanda tangan kriptografis GPG.

---

### 6. How
Alur kerja konversi file dari sistem lokal menuju Directed Acyclic Graph (DAG) di dalam repositori:

```
[Local File] 
     │
     ▼ (git hash-object -w)
[Blob Object] ──┐
                ├──► [Tree Object] ◄── [Sub-Tree Object]
[File Metadata] ┘           │
                            ▼ (git commit-tree)
                     [Commit Object] ◄── [Commit Object (Child)]
                            ▲
                            │ (git tag -a)
                   [Annotated Tag Object]
```

1. **Fase Ingesti File (Working Tree ke Staging Area/Index):**
   Saat `git add <file>` dieksekusi, Git membaca konten file, menghitung hash-nya bersama header, mengompresinya dengan `zlib`, dan menuliskannya ke `.git/objects/` sebagai tipe `blob`. Secara bersamaan, path dan hash file tersebut dicatat ke file biner `.git/index`.
2. **Fase Pembentukan Struktur Direktori (Index ke Tree):**
   Saat proses commit berjalan (atau via `git write-tree`), Git membaca `.git/index` dan mengompilasi representasi direktori saat itu menjadi satu atau lebih objek `tree`.
3. **Fase Snapshot State (Tree ke Commit):**
   Objek `commit` diinisiasi (via `git commit-tree`). Hash dari `root tree` dipasangkan ke objek ini bersama hash commit saat ini (`HEAD`) sebagai `parent`. File `.git/refs/heads/<branch>` kemudian dimutasi agar mengarah ke hash commit yang baru dibuat ini.

---

### 7. Analogy
Bayangkan sebuah **Arsip Dokumen Rahasia Perusahaan**:
- **Blob:** Lembaran kertas putih polos yang hanya memuat teks paragraf sebuah laporan, tanpa judul file, tanpa nomor halaman, dan tanpa informasi laci mana kertas itu ditaruh. Jika Anda menyalin teks yang sama ke lembar kedua, arsiparis membuang lembar kedua dan hanya menyimpan satu lembar fisik asli karena isinya sama persis.
- **Tree:** Sebuah folder/map berkas fisik dengan daftar isi tertera di sampulnya: *"Halaman A adalah lembar ID #83a1, Sub-folder Keuangan adalah map ID #9f2b"*. Map ini memberikan konteks struktural terhadap lembaran kertas polos tadi.
- **Commit:** Sebuah memo bertanda tangan resmi direksi yang ditempelkan di luar map: *"Status Arsip Finansial Q3 disetujui oleh Jane Doe pada 12 Oktober; Map yang berlaku adalah #e21c; Memo ini memperbarui Memo Acuan sebelumnya ID #a1b0"*.
- **Annotated Tag:** Segel sertifikat lilin emas resmi bertuliskan *"RELEASE V1.0 - AUDITED"* yang direkatkan permanen ke memo direksi tertentu.

---

### 8. Diagram
Struktur relasi objek Git di dalam memori dan filesystem:

```
+-----------------------------------------------------------------------------------+
| COMMIT OBJECT (Hash: 9a3f2b...)                                                   |
| - tree: 4c2e1a...                                                                 |
| - parent: 1b8d0c... (Commit sebelumnya)                                           |
| - author: Engineer <eng@corp.internal> 1700000000 +0700                           |
| - committer: Engineer <eng@corp.internal> 1700000000 +0700                        |
|                                                                                   |
| Initial production setup                                                          |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+------------------------------------------+----------------------------------------+
| ROOT TREE OBJECT (Hash: 4c2e1a...)                                                |
| - 100644 blob 8b3a5c...    .env.example                                           |
| - 100644 blob e69de2...    README.md                                              |
| - 040000 tree 7d1f9a...    src                                                    |
+---------------------------------------------------+-------------------------------+
                                                    |
                                                    v
                    +-------------------------------+-------------------------------+
                    | SUB-TREE OBJECT: src (Hash: 7d1f9a...)                        |
                    | - 100755 blob a94a8f...    server.sh                          |
                    | - 100644 blob 3b18e5...    main.go                            |
                    +-------------------+-------------------------------------------+
                                        |
                                        v
                    +-------------------+-------------------------------------------+
                    | BLOB OBJECT (Hash: 3b18e5...)                                 |
                    | [Isi mentah source code main.go tanpa metadata]               |
                    +---------------------------------------------------------------+
```

---

### 9. Simple Example
Mengonstruksi sebuah Git Blob dari baris perintah murni tanpa perintah tingkat tinggi (`git add`):

```bash
# Inisialisasi sandbox
mkdir git-internals-lab && cd git-internals-lab
git init

# 1. Hitung SHA-1 secara manual menggunakan plumbing command tanpa menulis ke disk
echo "system-kernel-init" | git hash-object --stdin
# Output: 5f1bca7f79435b84d4d84c107be58a034ee5cfa3

# 2. Simpan konten ke dalam object database Git (-w = write)
echo "system-kernel-init" | git hash-object -w --stdin
# Output: 5f1bca7f79435b84d4d84c107be58a034ee5cfa3

# 3. Verifikasi keberadaan file fisik di .git/objects/
ls -la .git/objects/5f/1bca7f79435b84d4d84c107be58a034ee5cfa3

# 4. Inspeksi tipe objek melalui plumbing command (-t = type)
git cat-file -t 5f1bca7f79435b84d4d84c107be58a034ee5cfa3
# Output: blob

# 5. Baca payload asli tanpa kompresi zlib (-p = pretty-print)
git cat-file -p 5f1bca7f79435b84d4d84c107be58a034ee5cfa3
# Output: system-kernel-init
```

---

### 10. Practical Example
Membuat commit penuh secara terprogram murni menggunakan perintah *plumbing*, memperlihatkan apa yang dilakukan `git commit` di balik layar:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Inisialisasi environment repositori kosong
rm -rf plumbing-repo && mkdir plumbing-repo && cd plumbing-repo
git init --initial-branch=main

# 1. Menulis konten file langsung ke dalam database objek (.git/objects)
BLOB_HASH=$(printf 'package main\n\nfunc main() {}\n' | git hash-object -w --stdin)
echo "Blob created: ${BLOB_HASH}"

# 2. Menulis entri secara langsung ke Index (Staging Area) tanpa Working Directory
# Format: git update-index --add --cacheinfo <mode> <object-hash> <path>
git update-index --add --cacheinfo 100644 "${BLOB_HASH}" "src/main.go"

# 3. Menulis representasi index menjadi objek Tree
TREE_HASH=$(git write-tree)
echo "Tree created: ${TREE_HASH}"

# Verifikasi struktur Tree yang terbuat
echo "Inspecting Tree:"
git cat-file -p "${TREE_HASH}"

# 4. Membentuk objek Commit yang menunjuk ke Tree tersebut
COMMIT_HASH=$(echo "feat(core): initial micro-kernel bootstrap" | git commit-tree "${TREE_HASH}")
echo "Commit created: ${COMMIT_HASH}"

# Verifikasi struktur Commit
echo "Inspecting Commit:"
git cat-file -p "${COMMIT_HASH}"

# 5. Mengarahkan branch reference (HEAD -> refs/heads/main) ke objek commit tersebut
git update-ref refs/heads/main "${COMMIT_HASH}"

# 6. Verifikasi menggunakan Porcelain command standar
echo "Verification via git log:"
git log -n 1 --stat
```

---

### 11. Real World Example
**Skenario Kasus: Forensik & Mitigasi Terhadap Insiden Korupsi Repositori Produksi pada Infrastruktur Perbankan**

*Latar Belakang Masalah:*  
Sebuah runner CI/CD enterprise mengalami *kernel panic* di tengah operasi `git rebase` otomatis pada monorepo inti backend sistem transfer dana. Ketika server menyala kembali, runner lain mencoba mengeksekusi pipeline dan gagal total dengan pesan kesalahan kritis:
```
error: object file .git/objects/3a/7b2e... is empty
fatal: loose object 3a7b2e... is corrupt
fatal: git upload-pack: aborting due to possible repository corruption
```

*Analisis Tingkat Internal:*
Sistem berkas mengalami pemotongan penulisan (*zero-length file flush*) saat penulisan *loose object*. Akibat sifat *content-addressable*, Git mendeteksi adanya file 0-byte dengan nama hash tertentu, yang melanggar checksum SHA-1. Repositori menolak melayani operasi *push* atau *pull* untuk mencegah propagasi korupsi data ke developer lain.

*Langkah Resolusi Menggunakan Manipulasi Plumbing:*
1. Mengidentifikasi file objek yang korup menggunakan verifikasi integritas:
   ```bash
   git fsck --full
   ```
   *Temuan:* `empty loose object: .git/objects/3a/7b2e...`
2. Mencari riwayat objek yang terputus dari referensi:
   Tim engineer forensik mengonfirmasi bahwa hash `3a7b2e...` merupakan file `transaction_engine.go` dari commit terakhir yang staging-nya belum selesai ditulis sempurna.
3. Menghapus file loose object yang 0-byte:
   ```bash
   rm -f .git/objects/3a/7b2e*
   ```
4. Melakukan *re-hashing* manual terhadap file `transaction_engine.go` dari working tree yang utuh:
   ```bash
   NEW_HASH=$(git hash-object -w src/core/transaction_engine.go)
   ```
5. Membangun ulang DAG yang hilang dan menyambungkan kembali *head ref* tanpa harus mengkloning ulang repositori sebesar 400 GB tersebut dari remote storage, mengurangi masa henti (*downtime*) dari estimasi 4 jam menjadi hanya 6 menit.

---

### 12. Trade-offs

| Aspek | Directed Acyclic Graph (DAG) Content-Addressable | Delta-based Storage (misal: SCCS, RCS, SVN Tradisional) |
| :--- | :--- | :--- |
| **Advantages** | - Integritas data kriptografis terjamin; manipulasi historis mustahil disembunyikan.<br>- Operasi branching dan merging berkisar dalam kompleksitas $O(1)$ secara mutasi pointer.<br>- Deduplikasi file identik secara inheren di level objek. | - Sangat hemat ruang penyimpanan untuk file biner berukuran besar yang sedikit berubah di tiap revisi.<br>- Konsep mental linier yang jauh lebih sederhana untuk diverifikasi pemula. |
| **Disadvantages**| - Repositori dapat membengkak drastis jika file biner non-kompresi bermutasi berkala (tiap perubahan 1 byte menduplikasi seluruh ukuran blob). | - Operasi *branching* dan *merging* membutuhkan waktu komputasi besar ($O(N)$ bergantung ukuran file) dan kalkulasi server terpusat. |
| **Complexity**   | Kompleksitas arsitektur tinggi. Pemahaman struktur graf internal diwajibkan untuk pemulihan bencana sistem. | Kompleksitas arsitektur rendah, namun kompleksitas sinkronisasi jaringan tinggi. |
| **Performance**  | Operasi perbandingan lokal instan (cukup membandingkan string hash pohon/tree tanpa membaca byte konten file satu per satu). | Operasi lambat; diffing memerlukan kalkulasi delta bertingkat dari basis awal hingga perubahan akhir. |
| **Cost**         | Mengorbankan ruang *Random Access Memory* (RAM) dan penyimpanan lokal developer untuk efisiensi kecepatan. | Mengorbankan bandwidth jaringan konstan dan dependensi ketersediaan *single-point-of-failure* server. |

---

### 13. When To Use
- **Audit Jejak Keamanan Forensik:** Ketika Anda harus memverifikasi apakah ada modifikasi tidak sah pada commit lama (*cryptographic signature checking* & DAG walking).
- **Membangun Internal Git Developer Tools:** Pembuatan CLI khusus (seperti deteksi credential leaks pre-receive hooks) yang mengevaluasi performa tanpa *overhead porcelain commands*.
- **Pembersihan Bersih Berkas Besar Secara Retrospektif:** Menggunakan utilitas seperti `git filter-repo` yang bekerja memetakan ulang seluruh hash tree dan commit objek dari basis data.

---

### 14. When NOT To Use
- **Pengembangan Rutin Sehari-hari:** Jangan gunakan perintah *plumbing* (`git hash-object`, `git write-tree`) untuk alur kerja fitur reguler. Selalu gunakan *porcelain* (`git add`, `git commit`) guna menjaga *guards/hooks* standar tetap terpicu.
- **Penyimpanan Aset Biner Dinamis Skala Besar:** Jangan mengandalkan Git storage internal untuk dataset ML (file `.bin`, `.parquet` gigabyte) atau rekaman video 4K tanpa ekstensi Git LFS. Sifat immutability Git akan menduplikasi objek utuh setiap kali ada modifikasi minor, mengakibatkan *repository bloat*.

---

### 15. Common Mistakes
1. **Mengira Git Menyimpan File Delta/Diff:**
   *Kesalahan:* Developer berasumsi commit hanya menyimpan baris perubahan (`+` dan `-`). 
   *Koreksi:* Git menyimpan snapshot file secara utuh dalam bentuk `blob` pada commit tersebut, kecuali saat proses pemadatan *Packfile* (`git gc`) dijalankan di belakang layar.
2. **Asumsi Nama File Ada di Dalam Objek Blob:**
   *Kesalahan:* Mencari nama file saat mengekstrak blob via hash.
   *Koreksi:* Blob murni hanya berisi konten mentah. Nama file dan hak akses (*permissions*) secara eksklusif disimpan di dalam objek `tree`.
3. **Memodifikasi Isi Objek di `.git/objects` Secara Manual Menggunakan Teks Editor:**
   *Kesalahan:* Mengedit file objek menggunakan editor teks biasa.
   *Koreksi:* Objek dikompresi dengan `zlib` dan divalidasi dengan hash-nya. Mengubah 1 byte konten file biner di dalam `.git/objects` akan merusak hash checksum, menyebabkan status `corrupted loose object` dan error integritas sistem.

---

### 16. Best Practices (Production Checklist)
- [ ] **Gunakan Hash SHA-256 untuk Repositori Baru:** Pertimbangkan inisialisasi repositori dengan proteksi tabrakan SHA-1 tingkat lanjut menggunakan `git init --object-format=sha256`.
- [ ] **Batasi Loose Objects:** Pastikan repositori produksi pada server internal menjadwalkan `git gc --auto` atau `git maintenance run` secara berkala untuk memadatkan ribuan *loose objects* menjadi *Packfiles* yang terindeks efisien.
- [ ] **Isolasi Aset Biner:** Jangan izinkan file biner dengan kompresi internal non-teks masuk ke `.git/objects`. Terapkan `.gitattributes` terpusat untuk mendelegasikannya ke Git LFS.
- [ ] **Gunakan Immutable Commits Validation:** Validasi integritas graf branch melalui pipeline CI dengan menjalankan `git fsck --strict` sebelum melakukan deployment ke node staging/produksi.

---

### 17. Troubleshooting

#### Masalah: "fatal: loose object <hash> is corrupt"
- **Penyebab:** Kerusakan sektor disk fisik atau penghentian proses penulisan *loose object* yang belum tuntas, menghasilkan berkas objek biner dengan checksum zlib yang tidak valid.
- **Solusi:**
  1. Identifikasi path file yang bermasalah: `.git/objects/hh/hhhh...`
  2. Periksa apakah objek tersedia di node developer lain atau remote server (`origin`):
     ```bash
     ssh remote-server "find .git/objects/ -name '<partial-hash>*'"
     ```
  3. Salin berkas objek biner yang sehat dari remote server atau lokal branch rekan tim ke path file yang rusak di repositori Anda.
  4. Jalankan `git fsck` untuk memvalidasi pemulihan integritas DAG.

#### Masalah: "error: Object <hash> is a blob, not a tree"
- **Penyebab:** Metadata cache indeks internal (`.git/index`) tertulis salah, atau terjadi manipulasi tingkat *plumbing* yang keliru memetakan hash pointer.
- **Solusi:**
  1. Hapus index cache lokal (aman dilakukan karena index bersifat ephemeral):
     ```bash
     rm .git/index
     ```
  2. Pulihkan index cache dari commit terakhir:
     ```bash
     git reset --mixed HEAD
     ```

---

### 18. Exercise
Kerjakan skenario berikut langsung di terminal Anda:
1. Buat folder repositori baru bernama `git-lab-core`.
2. Buat file bernama `notes.txt` berisi teks persis: `hello world architecture`.
3. Hitung nilai hash manual dari teks tersebut di terminal menggunakan perintah Unix standard (`printf` dan `sha1sum`) yang mensimulasikan mekanisme internal Git:
   $$\text{Format:} \quad \text{"blob 25\0hello world architecture"}$$
4. Simpan file tersebut menggunakan `git hash-object -w notes.txt`.
5. Bandingkan hasil hash kalkulasi manual Unix Anda dengan output dari perintah `git hash-object`. Pastikan kedua hash tersebut bernilai identik 100%.

---

### 19. Challenge
**Tantangan Arsitektur:** Konstruksi Pohon Bertingkat (*Nested Tree Construction*) Manual.

Tanpa menggunakan instruksi `git add`, `touch`, `git merge`, atau `git commit`:
1. Buat sebuah struktur proyek di dalam repositori kosong murni melalui *plumbing*:
   ```
   app/
   ├── config/
   │   └── database.yml (isi: "driver: postgres")
   └── main.py (isi: "print('running')")
   ```
2. Anda hanya diizinkan menggunakan:
   - `git hash-object -w --stdin`
   - `git update-index`
   - `git write-tree`
   - `git commit-tree`
   - `git update-ref`
3. Hasil akhir harus diverifikasi dengan memicu `git status` dan `git log -p`. Perintah `git status` wajib melaporkan: `nothing to commit, working tree clean`, dan `git log -p` harus menampilkan kedua file tersebut dalam satu struktur commit pohon yang benar.

---

### 20. Summary
- Git adalah **Content-Addressable Key-Value Database** di mana kunci (*key*) merupakan hash kriptografis dari header plus muatan data, dan nilai (*value*) adalah konten biner yang dikompresi dengan `zlib`.
- Sistem kontrol versi Git diwujudkan melalui empat objek dasar:
  - **Blob:** Konten file murni (agnostik terhadap metadata).
  - **Tree:** Struktur hirarki file, memetakan nama file, izin akses, dan hash objek target.
  - **Commit:** Snapshot status direktori (pointer ke Tree), riwayat graf (pointer ke Parent Commit), dan metadata pembuat.
  - **Tag:** Penunjuk permanen eksplisit yang memiliki metadata serta tanda tangan opsional.
- Setiap operasi commit adalah penciptaan simpul baru pada **Directed Acyclic Graph (DAG)**. Manipulasi historis akan merusak hash rantai berikutnya, memberikan jaminan integritas data yang kokoh.