# BAB 02: Quiz, Challenge, & Knowledge Check
**Inisialisasi, Konfigurasi, & Siklus Hidup Objek Git**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Anatomi Direktori `.git` dan Paradigma Content-Addressable Storage**  
   Ketika perintah `git init` dieksekusi pada direktori kosong, Git menginisialisasi subdirektori tersembunyi `.git/`. Jelaskan fungsi arsitektural dari komponen `HEAD`, `config`, `objects/`, dan `refs/`. Mengapa Git diklasifikasikan secara fundamental sebagai sistem penyimpanan berbasis *content-addressable key-value datastore*, bukan sekadar *delta-based version control system*?

2. **Hirarki dan Mekanisme Resolusi Konfigurasi Git**  
   Git menerapkan empat tingkatan konfigurasi: `--system`, `--global`, `--local`, dan `--worktree`. Jelaskan urutan presedensi (precedence order) saat Git mengevaluasi sebuah variabel konfigurasi (misalnya `user.signingkey` atau `core.autocrlf`). Bagaimana Git menangani konflik jika sebuah kunci didefinisikan pada keempat level tersebut secara bersamaan?

3. **Empat Objek Fundamental Git dan Pemisahan Tanggung Jawab Data**  
   Model data Git dibangun di atas empat tipe objek: `blob`, `tree`, `commit`, dan `annotated tag`. Uraikan struktur payload data dari masing-masing objek tersebut. Secara spesifik, jelaskan mengapa metadata file seperti nama file (*filename*), hak akses (*file mode/permissions*), dan struktur hierarki direktori **tidak** disimpan di dalam objek `blob`, melainkan di dalam objek `tree`.

4. **Kalkulasi Header dan Hashing SHA-1/SHA-256**  
   Git tidak melakukan hashing langsung terhadap *raw content* sebuah berkas, melainkan menyusun header khusus sebelum kalkulasi hash dilakukan: `printf "<type> <bytes-length>\0<content>" | sha1sum`. Mengapa penyertaan tipe objek dan ukuran payload (dipisahkan oleh null byte `\0`) secara arsitektural krusial untuk mencegah serangan manipulasi integritas data (*hash collision / type confusion attack*)?

5. **Diferensiasi Arsitektur: Standard Repository vs. Bare Repository**  
   Jelaskan perbedaan struktural antara repositori standar (`git init`) dan bare repository (`git init --bare`). Mengapa push langsung ke non-bare repository pada branch yang sedang aktif (*checked-out branch*) dilarang secara default oleh Git, dan mengapa server hosting Git (seperti GitHub, GitLab, atau internal git server) wajib menyimpan repositori dalam format bare?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Mekanisme Mutasi Internal Saat Eksekusi `git add`**  
   Telusuri langkah demi langkah apa yang terjadi di level filesystem dan internal storage ketika sebuah file baru bernama `main.go` (berisi kode sumber) dipindahkan dari *Working Directory* ke *Staging Area* via `git add main.go`. Kapan tepatnya objek `blob` ditulis ke disk di `.git/objects/`, dan bagaimana representasi file tersebut diperbarui pada berkas biner `.git/index`?

2. **Deduplikasi Objek dan Independensi Path File**  
   Sebuah repositori memiliki dua file di lokasi berbeda: `src/auth/token.go` dan `pkg/crypto/token.go`. Keduanya memiliki isi berkas yang byte-for-byte identik. 
   - Berapa banyak objek `blob` yang terbentuk di dalam `.git/objects/`?
   - Objek apa yang bertanggung jawab untuk memetakan bahwa kedua path yang berbeda tersebut mereferensikan payload yang sama persis? Buktikan bagaimana integritas struktural ini menghemat konsumsi disk Git.

3. **Forensik Objek Menggunakan Plumbing Commands**  
   Jika sebuah repositori mengalami status *detached HEAD* atau commit commit-nya tampak "hilang" dari output `git log`, bagaimana Anda menggunakan low-level plumbing commands (`git cat-file -t`, `git cat-file -p`, dan `git fsck`) untuk memverifikasi tipe objek, menginspeksi isi payload raw dari sebuah SHA-1 hash, dan menemukan *dangling/unreachable commit*?

4. **Siklus Hidup: Loose Objects ke Packed Objects (`packfiles`)**  
   Secara default, penambahan file baru menghasilkan *loose object* yang dikompresi dengan zlib (1 file per objek). Kapan Git mengonsolidasikan loose objects ini menjadi *packfile* (`.pack`) beserta indeksnya (`.idx`)? Jelaskan konsep *sliding window delta compression* yang digunakan Git untuk menghemat ruang disk pada packfile tanpa mengorbankan performa *read access*.

5. **Mismatch Konfigurasi Lintas Platform: `core.autocrlf` dan `core.filemode`**  
   Sebuah tim yang terdiri dari pengguna Windows dan Linux mengalami masalah di mana setiap kali developer Linux melakukan `git status`, ratusan file yang tidak diedit dilaporkan termodifikasi (*modified*). Setelah diinspeksi, perubahan hanya terkait line endings (`CRLF` vs `LF`) atau izin eksekusi berkas (`chmod +x`). Bedah bagaimana interaksi antara konfigurasi `core.autocrlf`, `core.filemode`, dan index cache menyebabkan false-positive drift ini dan bagaimana standardisasi arsitekturalnya via `.gitattributes`.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Bloated Repository Akibat Uncompressed Artifacts
Sebuah pipeline CI/CD enterprise mengalami degradasi performa ekstrem: durasi clone repositori melonjak dari 15 detik menjadi 42 menit. Investigasi menunjukkan bahwa seorang developer secara tidak sengaja menambahkan file model machine learning biner berukuran 4 GB ke staging area (`git add model.bin`), menyadarinya sebelum commit, lalu mengeksekusi `git reset model.bin` dan menghapus file tersebut dari working tree. Commit berikutnya bersih dari file tersebut.
* **Pertanyaan Diagnostik:**
  1. Mengapa ukuran direktori `.git/` pada mesin developer dan server tetap membengkak sebesar 4 GB meskipun `model.bin` tidak pernah masuk ke dalam riwayat commit (`git commit`)?
  2. Bagaimana Anda mengidentifikasi SHA-1 dari objek orphan/dangling tersebut di dalam `.git/objects/` dan langkah mitigasi pembersihan apa yang harus dieksekusi untuk mereduksi ukuran repositori tanpa merusak riwayat git yang valid?

### Skenario B: Race Condition dan File Locking pada Shared Environment
Sebuah runner automation pipeline mengeksekusi script deployment multi-thread paralel yang mengakses satu working directory repositori Git yang sama. Beberapa proses mencoba mengeksekusi `git add .` dan `git commit` secara simultan. Tiba-tiba proses gagal dengan pesan kesalahan fatal:  
`fatal: Unable to create '/path/to/repo/.git/index.lock': File exists.`
* **Pertanyaan Diagnostik:**
  1. Mengapa Git menerapkan mekanisme locking berbasis file biner (`index.lock`) pada index Git, dan status integritas apa yang sedang dilindungi oleh locking ini?
  2. Jika proses runner mati mendadak (*SIGKILL*) saat penulisan index sedang berlangsung, apa dampak residu pada working directory? Bagaimana prosedur otomatisasi yang aman (*fail-safe recovery*) untuk mendiagnosis apakah `index.lock` merupakan stale lock atau sedang aktif digunakan oleh proses lain?

### Skenario C: Desain Konfigurasi Multi-Identitas Developer Enterprise
Seorang principal engineer menggunakan satu laptop komputasi perusahaan untuk dua kepentingan: repositori open-source publik (GitHub personal: `john.doe@gmail.com` dengan SSH key A dan signing key GPG A) dan repositori internal perusahaan (Enterprise GitLab: `j.doe@enterprise-corp.com` dengan SSH key B dan signing key GPG B). Terjadi insiden kepatuhan (*compliance*) di mana commit internal perusahaan tidak sengaja terdorong menggunakan alamat email dan GPG key personal.
* **Pertanyaan Diagnostik:**
  1. Mengapa mengandalkan konfigurasi `--local` rentan terhadap *human error* pada repositori yang baru di-clone?
  2. Rancang arsitektur konfigurasi Git menggunakan fitur `includeIf` pada `~/.gitconfig` berdasarkan segmentasi direktori (misal: `~/work/` vs `~/personal/`) untuk mengisolasi identitas (`user.name`, `user.email`, `user.signingKey`, dan konfigurasi SSH `core.sshCommand`) secara deterministik tanpa intervensi manual developer.

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekonstruksi Siklus Hidup Commit Menggunakan Git Plumbing (Zero Porcelain Commands)

#### Problem Statement
Dalam abstraksi level tinggi (*porcelain*), developer menggunakan perintah kenyamanan seperti `git add` dan `git commit`. Namun, abstraksi ini menyembunyikan keterkaitan langsung antara storage engine, staging cache, dan DAG (*Directed Acyclic Graph*). Anda ditantang untuk membuktikan penguasaan siklus hidup objek Git dengan **membangun commit yang valid dari awal tanpa menyentuh perintah porcelain sama sekali**.

#### Constraints
* **DILARANG KERAS** menggunakan perintah *porcelain*: `git add`, `git commit`, `git rm`, `git status`, `git checkout`, `git switch`.
* **HANYA DIPERBOLEHKAN** menggunakan perintah *plumbing*:
  * `git hash-object`
  * `git update-index`
  * `git write-tree`
  * `git commit-tree`
  * `git update-ref`
  * `git cat-file`
  * `git read-tree`

#### Requirements
1. Inisialisasi repositori Git baru di direktori `/tmp/plumbing-lab`.
2. Secara manual buat struktur file berikut di *working directory*:
   ```text
   /tmp/plumbing-lab
   ├── app/
   │   └── server.py   (Isi: "print('Server v1')\n")
   └── README.md       (Isi: "# Core System\n")
   ```
3. Generate objek `blob` ke dalam `.git/objects/` langsung dari file-file tersebut menggunakan `git hash-object -w`. Catat hash SHA-1 yang dihasilkan.
4. Daftarkan file-file tersebut ke dalam file staging `.git/index` menggunakan `git update-index --add --cacheinfo ...` dengan permission mode POSIX yang tepat (`100644`).
5. Materialisasi struktur pohon direktori dari staging area menjadi objek `tree` permanen menggunakan `git write-tree`. Verifikasi hash root tree yang terbentuk.
6. Buat objek `commit` pertama (*root commit*) dari root tree tersebut menggunakan `git commit-tree` dengan pesan `"feat: initial architecture via plumbing"`. Konfigurasi author dan committer secara programmatic via environment variables (`GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, dll).
7. Arahkan pointer branch `refs/heads/main` ke SHA-1 commit baru tersebut menggunakan `git update-ref`.
8. Sinkronisasikan symbolic reference `HEAD` agar merujuk ke branch `refs/heads/main`.
9. Lakukan modifikasi pada `app/server.py` menjadi `"print('Server v2')\n"`, lalu ulangi siklus plumbing untuk menghasilkan commit kedua (*child commit*) yang secara eksplisit mereferensikan root commit sebagai *parent hash* (`-p`).

#### Expected Output
1. Eksekusi `git log --graph --oneline` menampilkan:
   ```text
   * <hash_commit_2> (HEAD -> main) feat: update server logic to v2
   * <hash_commit_1> feat: initial architecture via plumbing
   ```
2. Eksekusi `git status` melaporkan:
   ```text
   On branch main
   nothing to commit, working tree clean
   ```
3. Eksekusi `git cat-file -p HEAD` membuktikan bahwa commit kedua mereferensikan tree baru dan parent commit yang valid.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Struktur internal direktori `.git/` (`objects`, `refs`, `index`, `HEAD`, `config`).
- [ ] Prinsip *Content-Addressable Storage* dan formula hashing Git (`<type> <size>\0<payload>`).
- [ ] Perbedaan fundamental antara objek `blob`, `tree`, `commit`, dan `annotated tag`.
- [ ] Peran berkas biner `.git/index` sebagai *caching layer* antara working tree dan object store.
- [ ] Hirarki evaluasi konfigurasi Git: System $\rightarrow$ Global $\rightarrow$ Local $\rightarrow$ Worktree.
- [ ] Perbedaan fungsional dan struktural antara *Standard Repository* dan *Bare Repository*.
- [ ] Mekanisme kompresi zlib pada *loose objects* dan optimasi *packfiles* (`.pack` dan `.idx`).
- [ ] Mengapa Git memisahkan metadata file (nama file & permission bits) dari isi data berkas.

### Saya tidak perlu menghafal:
- [ ] Algoritma kompresi internal zlib atau detail byte-offset di dalam berkas biner `.git/index`.
- [ ] Struktur bitwise spesifik dari header packfile v2 (`PACK` signature format).
- [ ] Nilai 40-karakter (SHA-1) atau 64-karakter (SHA-256) hash string secara manual di luar sesi debugging langsung.
- [ ] Seluruh opsi flag sintaksis dari low-level plumbing commands yang jarang digunakan sehari-hari.

### Saya harus bisa melakukan:
- [ ] Menginisialisasi repositori standar (`git init`) dan bare repositori (`git init --bare`) sesuai use-case arsitektural.
- [ ] Mengonfigurasi identitas developer, signing keys, dan line-ending handling pada level local maupun global.
- [ ] Mengonfigurasi isolasi identitas otomatis menggunakan direktif `includeIf` pada berkas `~/.gitconfig`.
- [ ] Menginspeksi tipe dan isi objek Git menggunakan perintah plumbing `git cat-file -t <hash>` dan `git cat-file -p <hash>`.
- [ ] Menemukan dan mendiagnosis objek dangling atau repositori corrupt menggunakan `git fsck`.
- [ ] Membangun dan memperbarui object graph (blob $\rightarrow$ tree $\rightarrow$ commit $\rightarrow$ ref) secara manual menggunakan plumbing commands saat abstraksi porcelain gagal atau corrupt.