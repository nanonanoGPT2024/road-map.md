# BAB 05: Quiz, Challenge, & Knowledge Check
**Remote Collaboration & Distributed Architectures**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Anatomi dan Semantik Refspec:**
   Jelaskan secara mendalam struktur string refspec standar:  
   `+refs/heads/*:refs/remotes/origin/*`  
   Uraikan arti dari operator plus (`+`), sumber (*source*), pemisah titik dua (`:`), tujuan (*destination*), dan *wildcard* (`*`). Apa implikasi struktural pada direktori `.git/refs/` di mesin lokal ketika refspec ini dieksekusi saat proses `git fetch`?

2. **Diferensiasi Mekanisme: Fetch vs. Pull (Merge vs. Rebase):**
   Secara arsitektur DAG (*Directed Acyclic Graph*), jelaskan apa perbedaan fundamental antara:
   - `git fetch origin`
   - `git pull origin main` (default merge)
   - `git pull --rebase origin main`
   - `git pull --ff-only origin main`  
   Jelaskan status pointer `HEAD`, `refs/heads/main`, dan `refs/remotes/origin/main` pada masing-masing operasi tersebut.

3. **Remote-Tracking Branch vs. Tracking Configuration:**
   Bedakan konsep ontologis antara **Remote-Tracking Branch** (misal: `origin/main`) dengan **Upstream Configuration** pada file `.git/config` (parameter `branch.<name>.remote` dan `branch.<name>.merge`). Bagaimana Git menggunakan kedua informasi ini untuk menghitung status *"ahead N, behind M"* pada `git status`?

4. **Arsitektur Bare Repository vs. Non-Bare Repository:**
   Mengapa Git secara *default* menolak operasi `git push` yang menargetkan branch yang sedang aktif (*checked out*) pada sebuah non-bare repository (konfigurasi `receive.denyCurrentBranch`)? Jelaskan bahaya *working tree desynchronization* dan apa fungsi esensial dari sebuah *Bare Repository* (`--bare`) dalam topologi kolaborasi terpusat.

5. **Shared Centralized vs. Forking (Triangular) Workflow:**
   Bandingkan model kolaborasi *Shared Repository* (akses tulis langsung via branch permission) dengan *Triangular Workflow* (forking model dengan *downstream clone*, *upstream fetch*, dan *origin push*). Analisis trade-off kedua arsitektur ini dari aspek keamanan kredensial, skalabilitas *code review*, dan manajemen beban I/O pada server repositori.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Graph Reachability & Validasi Non-Fast-Forward Push:**
   Ketika server Git menolak perintah `git push` dengan galat `[rejected - non-fast-forward]`, proses komputasi graph reachability apa yang dijalankan oleh daemon Git di sisi server? Jelaskan algoritma penentuan *merge-base* dan verifikasi *ancestor* yang mendasari keputusan penolakan tersebut.

2. **Git Smart Transfer Protocol: Packfile Negotiation Handshake:**
   Jelaskan fase-fase komunikasi jaringan pada *Smart HTTP* atau *SSH Protocol* saat klien melakukan `git fetch`:
   - Fase *Reference Advertisement*
   - Fase Negosiasi Kemampuan (*Capabilities Negotiation*)
   - Fase Komputasi Graph (*`want` vs `have` lines*)
   - Fase *Packfile Generation* (*thin pack* dan *index generation*)  
   Bagaimana negosiasi ini meminimalkan ukuran data yang ditransfer melalui kabel?

3. **Pruning Semantics & Lifespan Remote References:**
   Saat developer lain menghapus branch `feature/payment` di remote, mengapa perintah `git fetch` standar tidak serta merta menghapus pointer `refs/remotes/origin/feature/payment` di repositori lokal Anda? Bagaimana cara kerja internal flag `--prune` (`-p`), dan apa yang terjadi pada *commit objects* yang direferensikan oleh remote tracking branch tersebut di object store lokal?

4. **Safety Verification: `--force` vs. `--force-with-lease` vs. `--force-if-includes`:**
   Analisis kelemahan kritis dari `git push --force`. Bagaimana `git push --force-with-lease` mengatasi masalah *overwriting uncoordinated commits* dengan memeriksa *expected value* dari ref? Jelaskan pula skenario kegagalan (*blind spot*) dari `--force-with-lease` yang akhirnya dipecahkan oleh penambahan flag `--force-if-includes` di Git versi modern.

5. **Penanganan Transaksional Reference Updates (`--atomic`):**
   Anda menjalankan perintah untuk mem-push 5 branch dan 3 annotated tag sekaligus:  
   `git push origin feature/A feature/B feature/C v1.0 v1.1 --atomic`  
   Jelaskan implementasi backend pada server (misal: penggunaan `.lock` files pada *files backend* vs *reftable backend*) yang menjamin bahwa jika 1 ref gagal diperbarui (misal: non-fast-forward pada `feature/B`), seluruh pembaruan ref lainnya dibatalkan tanpa menyisakan *half-applied state*.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Monorepo CI Thundering Herd Problem
Sebuah perusahaan skala besar memiliki monorepo enterprise sebesar 85GB (berisi 12 tahun histori komit). Terdapat 2.000 CI runner yang melakukan `git clone` dan `git fetch` secara berkala setiap ada merge commit baru di branch `main`. Server Git berbasis self-hosted GitLab/Gitolite mengalami CPU 100% dan OOM (*Out Of Memory*) crash berulang akibat ratusan proses `git-pack-objects` yang berjalan simultan.

*Pertanyaan Diagnostik & Solusi:*
1. Mengapa proses `git-pack-objects` sangat rakus CPU dan RAM dalam skenario ini? Uraikan dari sudut pandang *delta compression* dan *commit-graph traversal*.
2. Rancang strategi arsitektural caching dan optimasi Git di sisi server serta konfigurasi fetch di sisi CI runner (evaluasi opsi: *Blobless/Treeless Clones* via partial clone, Git Commit Graph generation, `git pack-redundant`, dan Commit Bitmap caching) untuk menurunkan beban komputasi server secara drastis!

### Skenario B: Race Condition dan Detached Remote State di Feature Branch
Developer Alice dan Bob sedang mengerjakan branch yang sama: `feature/checkout`. 
- Pukul 10:00: Keduanya berada pada base commit `C1`.
- Pukul 10:15: Bob membuat commit `C2` dan berhasil melakukan `git push origin feature/checkout`.
- Pukul 10:20: Alice, tanpa melakukan fetch, membuat commit lokal `C3` lalu merebase pekerjaannya di atas commit `C4` yang berasal dari `main` lokalnya (`git rebase main`), sehingga base commit-nya berubah.
- Pukul 10:25: Alice menjalankan `git push --force origin feature/checkout`.
- Pukul 10:30: Bob membuat commit `C5`, lalu menjalankan `git pull origin feature/checkout` dan mendapati riwayat commit-nya rusak, kodenya hilang, dan terjadi konflik merge masif di file lokalnya.

*Pertanyaan Diagnostik & Solusi:*
1. Rekonstruksi diagram DAG lokal Bob, lokal Alice, dan status remote pada pukul 10:26 pasca aksi push Alice. Mengapa commit `C2` milik Bob hilang dari pandangan remote?
2. Bagaimana prosedur forensik dan langkah demi langkah (menggunakan tooling bawaan Git: `reflog`, `git fsck`, atau `git log -g`) yang harus dilakukan oleh Bob untuk memulihkan commit `C2` miliknya dan mengintegrasikannya kembali secara bersih tanpa merusak histori Alice?

### Skenario C: Multi-Region Mirroring Data Drift & Partitioning
Organisasi Anda memiliki deployment Git multi-region: Server Primary di US-East dan Read-Only Mirrors di EU-Central dan AP-Southeast. Developer di AP-Southeast melakukan *fetch* dari Mirror lokal untuk efisiensi latensi, namun melakukan *push* langsung ke Primary di US-East via Smart HTTP proxy.
Suatu hari, pipa replikasi asinkron antara Primary ke AP-Southeast terputus (terjadi *network partition* selama 45 menit). Selama jeda ini:
- Developer di AP melakukan push commit `P1` ke Primary (sukses).
- CI pipeline di AP langsung memicu `git fetch` ke Mirror AP-Southeast dan menjalankan build otomatis berdasarkan branch tracking mirror tersebut.
- Build CI gagal secara fatal karena dependensi commit `P1` tidak ditemukan pada Mirror AP-Southeast.

*Pertanyaan Diagnostik & Solusi:*
1. Pola konsistensi data apa yang dilanggar dalam kasus ini (*strong consistency* vs *eventual consistency*)? Mengapa model *read-your-writes consistency* gagal tercapai?
2. Bagaimana Anda merancang mekanisme proteksi atau custom Git hook/proxy logic di sisi klien/server (misal: *read-after-write routing*, custom handshake tokens, atau conditional fetch fallback) untuk mencegah CI pipeline mengeksekusi build dari mirror yang mengalami status *stale/lagging*?

---

## 4. Chapter Challenge

### Tantangan Praktis: Simulasi Distributed Failover & Strict Push Pipeline Orchestration

#### Problem Statement
Anda ditugaskan merancang *automated recovery and synchronization engine* berbasis skrip CLI tingkat lanjut (Bash/Python). Skenarionya: Anda memiliki satu repositori lokal yang harus menyinkronkan status data ke dua remote berbeda: `origin` (Primary Git Server) dan `upstream-mirror` (Disaster Recovery Mirror). Keduanya harus selalu identik secara transaksional untuk semua branch dan tags rilis. Jika salah satu server menolak push atau mengalami *network failure*, sistem harus secara deterministik membatalkan seluruh perubahan atau memulihkan posisi pointer remote ke state semula (zero partial updates).

#### Requirements
1. **Konfigurasi Lingkungan:** Buat automasi berbasis skrip untuk menginisialisasi 3 bare repository di filesystem lokal Anda:
   - `remote-primary.git`
   - `remote-mirror.git`
   - `client-workdir` (sebagai active local repository dengan dua remote terdaftar).
2. **Deterministic Dual-Push Logic:**
   - Kembangkan skrip `sync-engine.sh` yang mengeksekusi push atomic terhadap `origin` dan `upstream-mirror`.
   - Menggunakan validasi `--force-with-lease` dinamis: skrip harus mengekstrak SHA-1 aktual dari kedua remote sebelum melakukan push.
3. **Simulasi Kegagalan & Rollback Hook:**
   - Injeksikan kegagalan secara artifisial pada `remote-mirror.git` menggunakan server-side `pre-receive` hook yang melempar exit code non-zero jika payload mengandung tag rilis baru.
   - Skrip `sync-engine.sh` harus mendeteksi kegagalan pada `remote-mirror.git` tersebut, menangkap error, lalu melakukan proses kompensasi rollback otomatis pada `remote-primary.git` sehingga kedua remote kembali berada pada komit yang sama persis.
4. **Verifikasi Integritas:**
   - Skrip harus mencetak matriks validasi hash SHA-1 dari semua ref di `client-workdir`, `remote-primary.git`, dan `remote-mirror.git`.

#### Constraints
- Wajib menggunakan raw Git CLI commands (tidak boleh menggunakan library abstraction pihak ketiga seperti GitPython atau libgit2).
- Harus menangani edge case: *annotated tags*, branch baru yang belum ada di remote, dan branch yang mengalami perubahan non-linear.
- Eksekusi harus bersifat idempoten.

#### Expected Output
1. File skrip `setup-env.sh` untuk provision lingkungan testing.
2. File hook `pre-receive` untuk simulasi kegagalan pada remote mirror.
3. File skrip `sync-engine.sh` yang berisi logic koordinasi transaksi, failover, kompensasi rollback, dan log pelaporan eksekusi.
4. Output terminal (log ASCII) yang memperlihatkan:
   - Status sebelum transaksi.
   - Skenario failure injection saat sinkronisasi mirror.
   - Eksekusi rollback pada primary.
   - Validasi akhir bahwa graph konsistensi pada kedua remote tetap seragam (*synchronized state*).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Format, parsing, dan semantik internal dari deklarasi Refspec (`+<src>:<dst>`).
- [ ] Perbedaan internal antara `git fetch`, `git merge`, `git rebase`, dan variasi `git pull`.
- [ ] Struktur direktori `.git/refs/remotes/` dan perbedaan daur hidupnya dengan `.git/refs/heads/`.
- [ ] Alur handshake *Smart Protocol* Git (`info/refs`, `upload-pack`, `receive-pack`, dan negosiasi `want`/`have`).
- [ ] Kondisi matematis graph (*ancestry path*) yang membedakan *fast-forward update* dengan *rejected non-fast-forward push*.
- [ ] Perbedaan teknis implementasi proteksi ref update antara `--force`, `--force-with-lease`, dan `--force-if-includes`.
- [ ] Prinsip kerja *Bare Repository* dan peran konfigurasi `receive.denyCurrentBranch`.
- [ ] Arsitektur *Partial Clone* (Blobless & Treeless) serta perannya dalam memitigasi bottleneck I/O pada repositori raksasa.

### Saya tidak perlu menghafal:
- [ ] Seluruh bit-level format dari file `.idx` dan header kompresi zlib pada Packfile Git v2.
- [ ] Nilai numerik persis dari konstanta timeout koneksi TCP pada transfer protokol HTTP/SSH bawaan Git.
- [ ] Ratusan parameter konfigurasi obscure pada `git-daemon` yang tidak relevan dengan workflows produksi modern.
- [ ] Urutan bytes eksak dari magic signature `PACK` dalam packfile binary parsing.

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi dan memodifikasi refspec kustom di file `.git/config` untuk membatasi fetch hanya pada branch spesifik.
- [ ] Melakukan analisis dan pemulihan data unreferenced commits dari branch remote yang terhapus atau tertimpa force push via `git reflog` dan `git fsck`.
- [ ] Mengonfigurasi upstream tracking branch secara manual menggunakan `git branch -u` atau `git push -u`.
- [ ] Mengimplementasikan *atomic multi-ref push* (`git push --atomic`) untuk memastikan transaksi deployment bebas inkonsistensi.
- [ ] Melakukan pembersihan menyeluruh terhadap referensi remote yang sudah stale menggunakan `git remote prune` atau konfigurasi otomatis `fetch.prune`.
- [ ] Melakukan debugging konektivitas dan pertukaran payload protokol Git menggunakan environment variable `GIT_TRACE=1`, `GIT_TRANSFER_TRACE=1`, dan `GIT_CURL_VERBOSE=1`.