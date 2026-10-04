# BAB 01: Quiz, Challenge, & Knowledge Check
**Anatomi & Filosofi Version Control System (VCS)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Paradigma Penyimpanan: Snapshot vs. Delta-based (Diff Chaining)**  
   Sistem kontrol versi terpusat lawas (seperti SVN atau CVS) umumnya merekam riwayat perubahan sebagai kumpulan berkas basis beserta serangkaian perbedaan delta (*diffs*). Sebaliknya, Git memperlakukan data sebagai serangkaian *snapshot* dari sistem berkas mini. Jelaskan implikasi performa dan integritas arsitektural dari pendekatan *snapshot* ini ketika Git mengeksekusi operasi percabangan (*branching*), *context-switching* (*checkout*), dan kalkulasi riwayat proyek!

2. **Dekomposisi Three-Tier State Architecture**  
   Git memisahkan siklus hidup berkas ke dalam tiga area lokal utama: *Working Tree*, *Staging Area* (Index), dan *Git Directory / Object Store* (`.git/`). Mengapa Git secara sengaja menyisipkan *Staging Area* sebagai lapisan perantara eksplisit, alih-alih langsung memindahkan perubahan dari *Working Tree* ke repositori lokal seperti pada sebagian besar DVCS primitif? Analisis dari sudut pandang *atomic commit design*.

3. **Prinsip Content-Addressable Storage**  
   Git pada dasarnya adalah sebuah *content-addressable filesystem* dengan antarmuka VCS di atasnya. Jelaskan apa yang dimaksud dengan *content-addressable storage* dalam konteks Git! Jika terdapat dua buah berkas di dalam subdirektori yang berbeda dengan nama yang berbeda, namun memiliki byte data (isi) yang identik 100%, bagaimana Git menyimpannya di dalam `.git/objects`?

4. **Failure Domains: Centralized VCS (CVCS) vs. Distributed VCS (DVCS)**  
   Bandingkan topologi ketahanan sistem antara CVCS dan DVCS. Apabila server penyimpanan pusat mengalami kerusakan disk permanen (*catastrophic storage corruption*) tanpa ketersediaan cadangan (*backup*) data offsite, jelaskan skenario terburuk pada arsitektur CVCS dibandingkan dengan kapabilitas pemulihan bencana (*disaster recovery*) yang inheren pada arsitektur DVCS!

5. **Imutabilitas dan Sifat Deterministik Hash Kriptografis**  
   Setiap simpul (*commit*) dalam Git diidentifikasi secara unik oleh nilai *hash* (SHA-1 atau SHA-256). Sebutkan komponen-komponen metadata dan struktural apa saja yang menyusun nilai *commit hash* tersebut! Mengapa perubahan satu spasi saja pada pesan komit (*commit message*) 10 level di masa lalu secara matematis merusak dan mengubah seluruh identitas rantai komit berikutnya?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Dangling Objects dan Siklus Hidup Objek Lepas (*Loose Objects*)**  
   Ketika seorang *developer* mengeksekusi perintah `git add sensitive_data.txt`, objek *blob* langsung ditulis ke direktori `.git/objects/`. Jika *developer* tersebut menyadari kesalahannya dan segera membatalkannya dengan perintah reset sebelum melakukan komit, apakah berkas `sensitive_data.txt` tersebut langsung terhapus dari sistem penyimpanan Git? Jelaskan mekanisme internal yang mengatur retensi dan pembersihan objek yatim (*dangling/unreferenced objects*) tersebut!

2. **Mitigasi Ledakan Ruang: Loose Objects vs. Packfiles**  
   Jika Git mengabstraksikan setiap berkas sebagai *snapshot* independen, secara teoretis ukuran direktori `.git` akan mengalami ledakan eksponensial (*storage explosion*) seiring bertambahnya revisi minor pada berkas besar. Mekanisme internal apa yang digunakan Git untuk mengompresi dan mengonsolidasi objek-objek lepas tersebut tanpa mengorbankan filosofi *snapshot*? Jelaskan konsep *sliding window compression* pada *packfiles*!

3. **Efisiensi Status via `.git/index` Stat Cache**  
   Perintah `git status` mampu memvalidasi status modifikasi puluhan ribu berkas dalam hitungan milidetik tanpa harus membaca ulang (*I/O disk read*) seluruh konten fisik berkas dari *Working Tree*. Atribut sistem berkas (*filesystem metadata*) apa saja yang dicatat dan dicocokkan oleh berkas biner `.git/index` untuk mendeteksi perubahan berkas secara instan?

4. **Biaya Komputasi Graf Asiklik Terarah (*Directed Acyclic Graph* / DAG)**  
   Secara arsitektur internal, sebuah cabang (*branch*) pada Git bukanlah salinan fisik (*duplication*) dari direktori berkas, melainkan sekadar pointer referensi yang dapat berpindah (*movable pointer*). Buktikan mengapa pembuatan cabang baru di Git beroperasi pada kompleksitas waktu dan ruang $O(1)$, sedangkan operasi serupa pada CVCS seperti SVN umumnya beroperasi pada kompleksitas $O(N)$!

5. **Integritas Struktural Merkle Tree**  
   Bagaimana Git mengimplementasikan struktur data *Merkle Tree* untuk menghubungkan objek *blob*, *tree*, dan *commit*? Jika terjadi perubahan 1-bit akibat *bit-rot* pada *storage drive* di dalam objek *blob* terdalam dari sebuah struktur proyek multi-level, bagaimana Git mendeteksi anomali ini saat pembacaan hierarki pohon direktori tingkat atas?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Monorepo Scale Bottleneck & Network Failure
Sebuah perusahaan skala *enterprise* memutuskan memigrasikan repositori monolitik berumur 10 tahun (berisi total 450.000 berkas dan 1,2 juta riwayat komit dengan ukuran total repositori mentah mencapai 95 GB) dari SVN ke Git murni. Pada hari peluncuran, seluruh *software engineer* mencoba melakukan `git clone` secara bersamaan. Server Git mengalami lonjakan pemakaian CPU hingga 100%, penggunaan RAM mencapai batas *swap*, proses I/O disk macet total, dan mayoritas koneksi klien mengalami *timeout* atau *broken pipe*.

*   **Pertanyaan Diagnostik:**
    1. Mengapa karakteristik inheren DVCS (yang mengharuskan *cloning* riwayat penuh secara lokal) menjadi bumerang pada skala monorepo sebesar ini?
    2. Identifikasi dua faktor komputasi terberat yang terjadi pada sisi *server* Git saat melayani permintaan transfer objek dalam volume masif tersebut!
    3. Solusi arsitektural Git tingkat lanjut apa saja (misalnya: *Blobless/Treeless Clones*, *Sparse Checkout*, *Git LFS*, atau *Scalar*) yang harus diimplementasikan untuk memecahkan kebuntuan skalabilitas ini tanpa perlu memecah monorepo?

### Skenario B: Silent Bit-Rot & Local Repository Corruption
Seorang *site reliability engineer* (SRE) sedang melakukan audit forensik pada server *build runner* CI/CD yang terisolasi (*air-gapped*). Proses *build* mendadak gagal dengan pesan galat fatal:  
`error: object file .git/objects/4b/825dc642cb6eb9a060e54bf8d69288fbee4904 is empty`  
`fatal: loose object 4b825dc642cb6eb9a060e54bf8d69288fbee4904 (stored in .git/objects/4b/825dc642cb6eb9a060e54bf8d69288fbee4904) is corrupt`

*   **Pertanyaan Diagnostik:**
    1. Apa penyebab teknis di balik fenomena objek kosong (*zero-byte object file*) ini pada tingkat sistem berkas (misal: kegagalan *flush write-buffer*, pemadaman listrik, atau *hard reboot*)?
    2. Bagaimana cara memverifikasi apakah objek yang rusak tersebut merupakan *commit*, *tree*, atau *blob* tanpa bantuan *porcelain command* standar?
    3. Rancang prosedur mitigasi dan pemulihan objek yang rusak tersebut dengan memanfaatkan integritas referensi dari mesin *developer* lain dalam kluster tim!

### Skenario C: Audit Kepatuhan Finansial vs. Git History Rewriting
Sebuah bank digital diwajibkan oleh regulator keuangan untuk menerapkan prinsip *non-repudiation* dan *strict audit trail*: riwayat kode produksi yang telah dideploy tidak boleh dimodifikasi, dihapus, atau dipalsukan stempel waktunya oleh pihak mana pun, termasuk oleh tim internal berhak akses *root*. Namun di sisi lain, tim pengembang secara rutin menggunakan teknik `git rebase -i` dan `git commit --amend` untuk menjaga kerapian riwayat komit lokal mereka sebelum digabungkan (*merge*).

*   **Pertanyaan Diagnostik:**
    1. Dari kacamata integritas data Git, jelaskan mengapa operasi seperti `git commit --amend` atau `git rebase` sebenarnya tidak "mengedit" komit yang ada, melainkan menciptakan komit baru yang sepenuhnya berbeda!
    2. Mengapa hash Git standar (SHA-1/SHA-256) saja belum cukup menjamin identitas pengarang (*authorship*) yang tidak terbantahkan (*non-repudiation*) jika hanya bergantung pada data string `GIT_AUTHOR_NAME` dan `GIT_AUTHOR_EMAIL`?
    3. Rancang arsitektur kebijakan VCS (*branch protection*, *cryptographic signing* dengan GPG/SSH, dan *immutable audit logging*) yang menyeimbangkan fleksibilitas manipulasi riwayat di lingkungan lokal pengembang dengan syarat kepatuhan absolut pada cabang rilis utama (*mainline*)!

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekonstruksi Komit Git Secara Manual Menggunakan Git Plumbing API (Low-Level)

#### Deskripsi Masalah
Mayoritas pengembang menggunakan Git sebatas perintah tingkat tinggi (*porcelain commands*) seperti `git add` dan `git commit` tanpa memahami bagaimana pointer dan objek fisik dialokasikan di dalam sistem berkas `.git`. Pada tantangan ini, Anda dilarang keras menggunakan perintah *porcelain* untuk memanipulasi berkas. Anda ditantang untuk membuat struktur direktori, membuat berkas, menaruhnya ke dalam *index*, menulis pohon hierarki objek, dan mencetak sebuah *commit* valid yang tercatat di cabang `master`/`main` murni menggunakan perintah *low-level* (*plumbing commands*).

#### Persyaratan Teknis (Requirements)
1. Inisialisasi direktori kosong murni bernama `manual-git-lab` hanya menggunakan `git init`.
2. Buat berkas bernama `architecture.txt` dengan isi `"Core Foundations of VCS"` dan berkas `config/app.json` dengan isi `{"status": "initialized"}`.
3. Masukkan konten kedua berkas tersebut ke dalam *Object Database* (`.git/objects`) secara manual menggunakan `git hash-object`. Catat SHA-1 *hash* yang dihasilkan untuk masing-masing *blob*.
4. Masukkan kedua berkas tersebut ke dalam *Index* (Staging Area) menggunakan perintah `git update-index --add` dengan memanfaatkan representasi mode oktal sistem berkas standar (`100644`).
5. Tuliskan representasi *Staging Area* menjadi objek *tree* menggunakan `git write-tree`.
6. Buat objek komit pertama (*root commit*) dari *tree* tersebut menggunakan `git commit-tree` dengan pesan komit: `"feat: initial architectural bootstrap via plumbing"`.
7. Perbarui referensi cabang `refs/heads/main` secara manual menggunakan `git update-ref` agar mengarah tepat ke *hash commit* yang dihasilkan dari langkah sebelumnya.
8. Pastikan `HEAD` mereferensikan cabang `refs/heads/main`.

#### Batasan (Constraints)
*   Dilarang menggunakan: `git add`, `git commit`, `git checkout`, `git switch`, `git branch`.
*   Semua manipulasi status harus terekam secara deterministik di dalam `.git/objects` dan `.git/refs`.

#### Hasil yang Diharapkan (Expected Output)
Ketika perintah pembaca riwayat tingkat tinggi berikut dieksekusi:
```bash
git log --stat --summary
```
Terminal wajib menampilkan luaran riwayat komit yang sepenuhnya valid dan sehat tanpa galat struktural:
```text
commit [HASH_COMMIT_ANDA] (HEAD -> main)
Author: [Nama Anda] <[Email Anda]>
Date:   [Waktu Eksekusi]

    feat: initial architectural bootstrap via plumbing

 architecture.txt | 1 +
 config/app.json  | 1 +
 2 files changed, 2 insertions(+)
 create mode 100644 architecture.txt
 create mode 100644 config/app.json
```
Perintah diagnostik integritas berikut juga harus menghasilkan status repositori yang bersih (*clean working tree*):
```bash
git status
# Output: On branch main, nothing to commit, working tree clean
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara arsitektur penyimpanan terpusat (*Delta/Diff-based CVCS*) dan terdistribusi (*Snapshot-based DVCS*).
- [ ] Peran dan representasi fisik dari Tiga Area Inti Git: *Working Tree*, *Staging Area (Index)*, dan *Git Directory (Repository)*.
- [ ] Konsep *Content-Addressable Storage* dan cara kerja kalkulasi hash berbasis isi data + header tipe objek.
- [ ] Empat tipe objek internal Git: `blob`, `tree`, `commit`, dan `annotated tag`.
- [ ] Struktur data *Directed Acyclic Graph* (DAG) dan *Merkle Tree* dalam menjaga integritas riwayat komit secara berantai.
- [ ] Mengapa manipulasi riwayat masa lalu selalu menghasilkan identitas hash baru (*immutability principle*).
- [ ] Perbedaan fungsionalitas antara lapisan *Plumbing commands* (antarmuka inti internal) dan *Porcelain commands* (antarmuka ramah pengguna).

### Saya tidak perlu menghafal:
- [ ] Rumus matematika internal algoritma kompresi zlib atau struktur biner presisi dari bit-shift tabel offset pada *packfile* `.idx`.
- [ ] 40 karakter heksadesimal lengkap dari *hash* objek spesifik saat melakukan operasi harian.
- [ ] Setiap parameter atau *flags* langka dari perintah-perintah *plumbing* berderajat rendah (seperti `git mktag` atau `git unpack-objects`).

### Saya harus bisa melakukan:
- [ ] Menggunakan perintah `git cat-file (-t, -p, -s)` untuk menginspeksi tipe, isi data, dan ukuran objek apa pun di dalam `.git/objects`.
- [ ] Melacak bagaimana mutasi pada *Working Tree* berpindah secara bertahap ke *Index*, lalu terkristalisasi di dalam *Object Store*.
- [ ] Mengidentifikasi kondisi repositori lokal yang korup menggunakan perintah integritas `git fsck`.
- [ ] Membaca isi berkas biner `.git/index` menggunakan perintah diagnosa seperti `git ls-files --stage`.
- [ ] Menjelaskan dan mendemonstrasikan bahwa sebuah cabang (*branch*) pada Git pada dasarnya hanyalah sebuah berkas teks sederhana berisi 40 karakter *hash* di dalam direktori `.git/refs/heads/`.