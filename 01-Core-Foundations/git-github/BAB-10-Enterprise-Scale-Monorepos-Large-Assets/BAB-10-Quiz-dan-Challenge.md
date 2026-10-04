# BAB 10: Quiz, Challenge, & Knowledge Check
**Enterprise Scale, Monorepos, & Large Asset Management**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Mekanisme Smudge & Clean Filter pada Git LFS:**
   Jelaskan secara presisi siklus hidup objek ketika file biner dikelola menggunakan Git Large File Storage (Git LFS). Bagaimana interaksi internal antara *working tree*, *staging area (index)*, dan Git object database (`.git/objects`) via *smudge filter* saat `checkout` dan *clean filter* saat `git add`? Apa struktur spesifik dari *pointer file* yang tersimpan di basis data Git?

2. **Diferensiasi Shallow Clone vs Partial Clone:**
   Bandingkan arsitektur dan trade-off antara *Shallow Clone* (`--depth=N`) dan *Partial Clone* (`--filter=blob:none` vs `--filter=tree:0`). Mengapa *Partial Clone* dianggap sebagai standar de facto baru untuk CI/CD pipeline pada monorepo skala enterprise dibandingkan *Shallow Clone* konvensional?

3. **Sparse-Checkout: Cone Mode vs Non-Cone Mode:**
   Bagaimana algoritma pencocokan pola internal bekerja pada Sparse-Checkout saat menggunakan **Cone Mode** dibandingkan **Non-Cone Mode**? Mengapa Cone Mode memiliki performa $O(1)$ atau $O(N)$ direktori, sementara Non-Cone Mode terdegradasi menjadi $O(M \times K)$ pola regex yang melumpuhkan performa repository dengan ratusan ribu direktori?

4. **Git Submodules vs Git Subtrees:**
   Uraikan perbedaan fundamental penyimpanan referensi antara Git Submodule (menggunakan pointer Gitlink mode `160000` dan file `.gitmodules`) dengan Git Subtree (menyimpan tree objek langsung pada commit history). Apa implikasi struktural keduanya terhadap atomisitas commit dan dependensi cross-repository?

5. **Skalabilitas Filesystem: FSMonitor dan Untracked Cache:**
   Pada monorepo dengan lebih dari 500.000 file, perintah sederhana seperti `git status` dapat memakan waktu puluhan detik akibat overhead `lstat()` sistem operasi. Jelaskan bagaimana integrasi Git FSMonitor (memanfaatkan *filesystem event daemon* seperti Watchman atau OS native) dan *Untracked Cache* mengeliminasi bottleneck I/O traversal ini.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Diagnostik Server-Side Resource Exhaustion (`git-pack-objects`):**
   Ketika ratusan *runner* CI melakukan checkout paralel secara bersamaan dari server Git enterprise (misal: GitHub Enterprise Server / GitLab Self-Managed), utilisasi CPU dan memori host server melonjak hingga 100% dan menyebabkan OOM (*Out Of Memory*). Jelaskan bagaimana mekanisme pembuatan packfile dinamis (*delta compression* on-the-fly) memicu beban ini, dan bagaimana konfigurasi `commit-graph`, *reachability bitmaps*, serta packfile offloading dapat memitigasinya.

2. **Mitigasi Insiden Broken LFS Pointer:**
   Seorang pengembang melakukan `push` ke branch utama, namun pipeline staging gagal dengan error `Encountered X file(s) that should have been pointers, but were not` atau LFS download error `404 Object Not Found`. Uraikan alur investigasi untuk menentukan apakah file biner asli terlanjur terserap ke dalam Git object database sebagai loose blob, atau pointer ter-commit tanpa upload asset ke LFS storage backend. Perintah plumbing apa yang digunakan untuk mendiagnosis hash blob tersebut?

3. **Dampak Blobless Clone terhadap Git Operations Latency:**
   Dalam setup *blobless partial clone* (`--filter=blob:none`), disk space developer sangat hemat saat clone awal. Namun, jelaskan apa yang terjadi di balik layar (protokol transfer jaringan dan latency penalty) ketika developer mengeksekusi:
   * `git log -S "DEPRECATED_API" -p`
   * `git blame src/core/engine.c`
   * `git checkout feature-branch-from-6-months-ago`

4. **Commit-Graph File & Generation Numbers:**
   Jelaskan secara struktural bagaimana file `.git/objects/info/commit-graph` mempercepat operasi penelusuran riwayat commit seperti `git merge-base` atau penentuan *ancestry* commit pada monorepo jutaan commit. Apa peran matematis dari *Topological Levels* dan *Corrected Commit Dates* (Generation Numbers) dalam memangkas traversal DFS/BFS?

5. **Resolusi Detached HEAD & State Desynchronization pada Submodule:**
   Saat menjalankan `git checkout --recurse-submodules` di monorepo, developer mendapati submodule berada dalam kondisi *Detached HEAD*, lalu melakukan commit lokal di direktori submodule tersebut tanpa membuat branch. Ketika branch monorepo utama di-*switch*, commit submodule seolah "hilang". Jelaskan secara teknis bagaimana Git menyimpan referensi submodule dan langkah pemulihan (*disaster recovery*) untuk menyelamatkan commit submodule yang tidak terlacak (*dangling commit*) tersebut.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: CI/CD Deadlock & Git Server Meltdown
* **Konteks:** Perusahaan fintech mengoperasikan monorepo sebesar 120 GB (berisi 15 tahun riwayat, 800.000 file, dan puluhan tim microservice). Setiap kali ada merge ke branch `main`, 40 job CI terpicu serentak.
* **Gejala:** Server Git internal mengalami down berkala. Developer menerima error `fatal: the remote end hung up unexpectedly` dan `fatal: early EOF`. Waktu kloning CI memakan waktu 35 menit per runner.
* **Pertanyaan Diagnostik & Solusi:**
  1. Strategi cloning dan fetching apa yang harus diimplementasikan pada konfigurasi runner CI secara bertahap untuk mereduksi beban I/O server dan durasi clone dari 35 menit ke bawah 2 menit?
  2. Parameter arsitektur apa pada sisi server Git (misal: pack reuse, bitmap coverage, delta cache) yang wajib dituning untuk mencegah CPU thrashing akibat thread `git-pack-objects` yang dipanggil berulang kali?

### Skenario B: Accidental Binary Push & History Corruption
* **Konteks:** Seorang data scientist secara tidak sengaja meng-commit dataset SQLite mentah sebesar 12 GB ke repository tanpa mengonfigurasi Git LFS. Commit tersebut telah di-push ke remote repository dan di-pull oleh 20 anggota tim lain sebelum disadari.
* **Gejala:** Ukuran packfile lokal dan remote melonjak drastis. Kuota hosting enterprise terlampaui, dan perintah `git push` ditolak oleh server hook karena melampaui batas ukuran file tunggal (misal: limit 2 GB).
* **Pertanyaan Diagnostik & Solusi:**
  1. Mengapa eksekusi `git rm dataset.sqlite && git commit` sama sekali tidak menyelesaikan masalah ini pada Git object storage?
  2. Rancang rencana remediasi end-to-end menggunakan utility `git-filter-repo` (bukan `git filter-branch`) untuk mencabut blob biner tersebut dari seluruh riwayat tree dan tags tanpa merusak tanda tangan PGP (jika ada) atau commit timestamps tim, serta protokol migrasi yang harus diinstruksikan kepada 20 developer terdampak untuk mencegah blob tersebut masuk kembali (*resurrection*).

### Skenario C: Arsitektur Migrasi: Polyrepo ke Monorepo Skala Enterprise
* **Konteks:** Engineering leadership memutuskan untuk menggabungkan 60 polyrepo microservices independen ke dalam satu unified monorepo untuk menyederhanakan dependensi internal dan sinkronisasi rilis. Masing-masing repo memiliki rata-rata 10.000 commit.
* **Gejala:** Tim khawatir kehilangan commit history asli, author identity, dan file lineage saat proses penggabungan. Selain itu, ada kekhawatiran benturan nama direktori root (seperti `README.md`, `.gitignore`, `Makefile`) dari masing-masing repo asal.
* **Pertanyaan Diagnostik & Solusi:**
  1. Bagaimana Anda merancang skrip migrasi menggunakan `git-filter-repo` atau `git subtree` untuk memindahkan seluruh riwayat commit dari 60 repo tersebut ke subdirektori unik masing-masing (misal: `/services/service-A/`) sebelum digabungkan, dengan tetap mempertahankan commit SHA lineage dan metadata asli?
  2. Setelah monorepo terbentuk, strategi kontrol akses apa (seperti *Branch Protection Rules* dan *CODEOWNERS matrix*) yang harus diterapkan untuk memastikan tim Service A tidak dapat mengubah kode Service B secara sepihak, meskipun mereka berada di dalam workspace yang sama?

---

## 4. Chapter Challenge

**Tantangan Praktis: Enterprise Monorepo Optimization & Disaster Remediation**

### Problem Statement
Anda diangkat sebagai Lead SRE / Infrastructure Architect di sebuah perusahaan e-commerce. Anda diberikan repository tiruan (sandbox) monorepo berukuran 4.5 GB yang lambat, berisi file biner terkomit secara tidak sah, memiliki waktu traversal `git status` lebih dari 10 detik, dan pipeline CI yang membutuhkan waktu 18 menit hanya untuk tahap checkout.

### Requirements & Task List
1. **Repository Audit & Bloat Identification:**
   * Temukan 5 blob terbesar yang bersarang di dalam riwayat commit repository menggunakan Git plumbing command (`git verify-pack`, `git rev-list`).
2. **History Rewriting & LFS Conversion:**
   * Bersihkan file biner bervolume besar (>50 MB) dari seluruh riwayat repository menggunakan `git-filter-repo`.
   * Konfigurasikan `.gitattributes` untuk memastikan ekstensi `.psd`, `.zip`, dan model artifacts (`.onnx`, `.bin`) otomatis dialihkan ke Git LFS di masa depan.
3. **Client-Side Optimization Deployment (Scalar & Features):**
   * Terapkan konfigurasi enterprise monorepo pada repository lokal:
     * Aktifkan Cone Mode Sparse-Checkout untuk membatasi checkout hanya pada direktori `apps/backend/` dan shared library `libs/core/`.
     * Konfigurasikan FSMonitor terintegrasi, Untracked Cache (`core.untrackedCache true`), dan `core.preloadIndex true`.
     * Tuliskan file konfigurasi atau perintah terminal yang mengotomatisasi aktivasi tool suite **Scalar** (atau konfigurasi git config ekuivalen: `fetch.writeCommitGraph`, `index.version 4`).
4. **CI/CD Optimization Script:**
   * Buat bash script checkout pipeline yang mengimplementasikan **Blobless Partial Clone** (`--filter=blob:none`) dikombinasikan dengan Sparse-Checkout Cone Mode.

### Constraints
* Dilarang menghapus commit fungsional atau commit message developer selama proses pembersihan.
* History rewrites harus menghasilkan SHA baru yang konsisten di semua branch tanpa meninggalkan *dangling references* pada namespace `refs/original/` atau reflogs.
* Setup sparse-checkout tidak boleh memecahkan path build dependensi internal antara `apps/backend` dan `libs/core`.

### Expected Output
1. **Laporan Audit:** Tabel berisi Hash Blob, Ukuran Asli, Ukuran Terkompresi, dan Path File dari 5 binary terbesar yang ditemukan.
2. **Kumpulan Perintah Shell/Bash:** Skrip eksekusi end-to-end pembersihan riwayat dan konversi LFS.
3. **File Konfigurasi:** File `.gitattributes` dan `.git/config` final yang telah dioptimasi.
4. **Benchmark Report:** Bukti perbandingan ukuran folder `.git/` (sebelum vs sesudah) dan waktu eksekusi `git status` serta durasi clone pipeline.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi pointer file Git LFS (OID SHA-256, Size) dan protokol komunikasi Git LFS client-server (Batch API).
- [ ] Perbedaan struktural dan beban komputasi antara *blobless clone* (`--filter=blob:none`) dan *treeless clone* (`--filter=tree:0`).
- [ ] Algoritma Cone Mode Sparse-Checkout dan pembatasan ekspresi polanya dibanding globbing non-cone konvensional.
- [ ] Cara kerja file `commit-graph`, Bitmap Indexes (`.bitmap`), dan dampaknya terhadap throughput operasi traversal graph.
- [ ] Dampak arsitektural dari Monorepo vs Polyrepo terhadap continuous integration, shared dependencies, dan disk I/O.
- [ ] Risiko keamanan dan integritas git hook (`smudge`/`clean`) serta mitigasi supply chain attack pada repository raksasa.

### Saya tidak perlu menghafal:
- [ ] Struktur byte-level header dari binary format file `.git/objects/info/commit-graph`.
- [ ] Seluruh flag sintaks legasi dari perintah yang sudah usang seperti `git filter-branch`.
- [ ] Spesifikasi REST payload lengkap dari GitHub LFS Batch API JSON request/response schema.

### Saya harus bisa melakukan:
- [ ] Mengidentifikasi dan mengekstrak daftar file terbesar yang terkubur dalam riwayat commit Git menggunakan kombinasi perintah plumbing (`git rev-list`, `git cat-file`).
- [ ] Menulis dan mengeksekusi skrip pembersihan repository massal secara aman menggunakan tool modern `git-filter-repo`.
- [ ] Menginisialisasi, mengonfigurasi, dan men-debug Sparse-Checkout Cone Mode pada repository monorepo.
- [ ] Menyiapkan skrip clone CI/CD berkinerja tinggi menggunakan teknik partial clone dan reference repo caching.
- [ ] Mengonfigurasi `Scalar` atau parameter `git config` tingkat lanjut (`core.fsmonitor`, `core.untrackedcache`, `commitGraph.generationVersion`) untuk mereduksi latensi interaksi lokal developer pada monorepo jutaan baris kode.