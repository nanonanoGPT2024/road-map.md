# BAB 07: Quiz, Challenge, & Knowledge Check
**Kolaborasi Jarak Jauh (Remote Repositories & Protocol Plumbing)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Arsitektur Pemisahan State Lokal vs. Remote-Tracking**:
   Jelaskan secara struktural perbedaan antara local branch (`refs/heads/feature`), remote-tracking branch (`refs/remotes/origin/feature`), dan remote branch sebenarnya yang ada di server. Dalam siklus hidup Git, peristiwa spesifik apa saja yang memicu mutasi nilai hash SHA pada `refs/remotes/origin/feature`?
2. **Dekomposisi Mekanisme `git fetch` vs. `git pull`**:
   Secara arsitektural, `git pull` sering disebut sebagai *opinionated compound command*. Bedah operasi internal yang dieksekusi Git saat menjalankan `git fetch` dibandingkan dengan `git pull`, serta jelaskan mutasi apa saja yang terjadi pada file-file pointer di dalam direktori `.git/` untuk kedua perintah tersebut.
3. **Anatomi dan Semantik Refspec**:
   Sebuah remote standar menghasilkan konfigurasi default `fetch = +refs/heads/*:refs/remotes/origin/*`. Analisis fungsi dari tanda plus (`+`), karakter wildcard (`*`), sisi kiri (source), dan sisi kanan (destination) titik dua (`:`). Apa risiko integritas data lokal jika tanda `+` dihilangkan atau dimodifikasi secara keliru?
4. **Evaluasi Protokol Transportasi (SSH vs. HTTPS)**:
   Bandingkan penggunaan protokol Secure Shell (SSH) dengan Hypertext Transfer Protocol Secure (HTTPS) dalam interaksi remote Git tingkat enterprise. Tinjau dari aspek traversal firewall/proxy jaringan, mekanisme autentikasi (kredensial token vs. asimetris keypair), serta *overhead* kriptografi saat payload berukuran multi-gigabyte.
5. **Mekanisme Pelacakan Cabang (Upstream Tracking)**:
   Saat mengeksekusi `git push -u origin main` atau `git branch --set-upstream-to=origin/main`, metadata apa yang ditulis Git ke dalam file `.git/config`? Bagaimana Git memanfaatkan relasi upstream ini untuk menghitung kalkulasi metrik *ahead/behind* secara lokal tanpa melakukan request jaringan?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Plumbing Wire Protocol: Smart HTTP vs. Dumb HTTP**:
   Jelaskan bagaimana Git Server dan Client menegosiasikan referensi objek melalui *Smart HTTP Protocol*. Apa peran endpoint `/info/refs?service=git-upload-pack` dan `/git-upload-pack` dalam fase discovery dan transmisi data, serta bagaimana fase ini mencegah duplikasi transfer objek yang sudah dimiliki oleh client?
2. **Diagnostik Non-Fast-Forward Push Failure**:
   Ketika perintah `git push origin main` ditolak dengan galat `[rejected - non-fast-forward]`, algoritma graf apa yang dijalankan oleh remote Git server untuk menentukan bahwa push tersebut harus ditolak? Mengapa server tidak membutuhkan eksekusi checkout fisik dari working tree untuk menolak transaksi tersebut?
3. **Lifecycle Management & Zombie References (`Pruning`)**:
   Jika seorang kolaborator menghapus branch `feat/payment` di GitHub, mengapa branch `origin/feat/payment` di workstation lokal Anda tetap bertahan meski Anda telah mengeksekusi `git fetch origin` berulang kali? Jelaskan mekanisme internal `git remote prune origin` (atau `git fetch -p`) dalam menyinkronkan namespace `refs/remotes/origin/`.
4. **Optimistic Concurrency Control (`--force-with-lease`)**:
   Secara internal, bagaimana mekanisme Compare-and-Swap (CAS) diimplementasikan pada perintah `git push --force-with-lease`? Skenario race condition spesifik apa yang dicegah oleh opsi ini dibandingkan dengan `git push --force` destruktif biasa?
5. **Troubleshooting SSH Transport Layer**:
   Sebuah workstation developer gagal melakukan cloning dengan pesan `Permission denied (publickey)`. Bagaimana Anda melakukan proses debugging mendalam hingga level socket transport menggunakan perintah Git dan flags SSH yang relevan untuk memvalidasi penggunaan identity file, SSH Agent forwarding, dan host fingerprint?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck I/O pada Monorepo CI/CD Skala Masif
Sebuah monorepo enterprise berukuran 80 GB dengan riwayat commit selama 7 tahun menyebabkan pipeline CI/CD sering mengalami *timeout* pada tahap `git clone origin main` di ratusan *runner* ephemeral Kubernetes. Waktu clone rata-rata mencapai 18 menit dan menghabiskan *egress bandwidth* infrastruktur.
* **Pertanyaan Diagnostik & Solusi**:
  1. Identifikasi komponen data Git apa saja yang membebani transfer network pada default clone.
  2. Rancang strategi plumbing transport Git (kombinasi shallow clone, blobless/treeless clone via *partial clone filter*, dan caching remote-tracking) untuk memangkas waktu inisialisasi pipeline menjadi di bawah 45 detik tanpa merusak kapabilitas kompilasi aplikasi.

### Skenario B: Race Condition dan Deteksi "Silently Overwritten History"
Pada branch rilis bersama `staging`, Tim Backend A melakukan force push (`push --force`) setelah melakukan rebase lokal untuk membersihkan commit history. Tepat 3 detik sebelumnya, Tim Backend B baru saja mem-push perbaikan hotfix kritikal ke branch tersebut via fast-forward push standar. Komit Tim B hilang dari branch tip `staging` tanpa disadari, dan issue baru terdeteksi saat deployment ke environment integrasi gagal.
* **Pertanyaan Diagnostik & Solusi**:
  1. Jelaskan bagaimana *race condition* ini terjadi pada remote branch reference.
  2. Tanpa memiliki akses ke server hosting Git (GitHub Enterprise / GitLab instance admin backend), langkah-langkah forensik apa yang dapat dilakukan oleh Tim B menggunakan referensi lokal mereka (`reflog`, `ORIG_HEAD`, dangling commits) untuk merekonstruksi, memulihkan, dan memvalidasi payload yang terhapus?
  3. Konfigurasi branch protection dan push rule spesifik apa yang harus diimplementasikan di remote repository untuk mengeliminasi celah insiden ini secara permanen?

### Skenario C: Multi-Remote Architecture (Fork-and-Pull / Open Source Maintainer Model)
Sebagai Principal Architect sistem core banking, Anda mengelola repository upstream inti (`upstream`). Developer internal hanya diberikan akses read-only dan diwajibkan bekerja di fork personal mereka (`origin`). Sering terjadi insiden developer secara keliru mem-push branch kotor lokal langsung ke `upstream` saat privilege developer diperluas, atau branch lokal mereka tertinggal (desynchronized) dari `upstream/main` sehingga menyebabkan PR conflict yang kompleks.
* **Pertanyaan Diagnostik & Solusi**:
  1. Rancang konfigurasi arsitektur multi-remote pada lokal developer (definisi remote URL, push URL dummy/disabled untuk upstream, dan fetch refspec terisolasi) menggunakan perintah `git remote` dan `git config`.
  2. Formulasikan Standar Prosedur Operasional (SOP) sanitasi branch lokal bagi developer untuk menyinkronkan branch kerja mereka dengan perubahan terbaru dari `upstream/main` tanpa menghasilkan *merge bubble commit* yang mengotori linear history.

---

## 4. Chapter Challenge

**Tantangan Praktis: Multi-Remote Topology Plumbing & Optimistic Push Disaster Recovery**

### Deskripsi Tantangan
Anda ditugaskan mengonfigurasi dan memperbaiki topologi remote repository yang rusak pada lingkungan simulasi lokal, mengonversi metode autentikasi transport, memanipulasi low-level refspec, serta memulihkan branch yang terkena konflik push secara aman menggunakan Compare-and-Swap primitives.

### Requirements:
1. **Simulasi Arsitektur Multi-Remote**:
   - Buat dua direktori "bare" remote: `/tmp/upstream-repo.git` dan `/tmp/fork-repo.git`.
   - Inisialisasi local repository, kaitkan kedua remote tersebut dengan alias `upstream` dan `origin`.
   - Konfigurasikan remote `upstream` agar memiliki `pushurl` bernilai `DISABLED` untuk memvalidasi proteksi salah-push di level client.
2. **Kustomisasi Refspec Tingkat Lanjut**:
   - Modifikasi konfigurasi `.git/config` sehingga eksekusi `git fetch origin` hanya mengambil branch yang memiliki prefix `feature/*` ke dalam tracking namespace `refs/remotes/origin/feature/*`, dan mengabaikan namespace lainnya.
3. **Simulasi CAS Push Failure & Safe Recovery**:
   - Simulasikan kondisi konflik di mana remote branch tip bergerak mendahului local tracking branch.
   - Eksekusi pengiriman update menggunakan mekanisme *Optimistic Concurrency Control* (`git push --force-with-lease`).
   - Tunjukkan bahwa push ditolak jika remote-tracking pointer lokal tidak sinkron.
   - Lakukan rekonsiliasi state via plumbing `git fetch` dan rebase, kemudian selesaikan push secara sukses.
4. **Remote Branch Sanitization**:
   - Hapus sebuah branch di remote secara programatis, lalu validasi status branch lokal yang dangling.
   - Bersihkan tracking references yang mati (*dead tracking pointers*) tanpa menyentuh branch lokal yang masih aktif.

### Constraints:
- Dilarang keras menggunakan perintah destruktif absolut `git push --force` / `git push -f`.
- Seluruh manipulasi remote tracking harus diverifikasi menggunakan low-level output inspection (`git ls-remote`, `git rev-parse`, atau pemeriksaan langsung pada file `.git/refs/remotes/`).
- Waktu pengerjaan maksimal 30 menit.

### Expected Output:
- Cuplikan isi file `.git/config` yang terstruktur dan bersih.
- Log command line yang menunjukkan penolakan eksplisit dari `upstream` saat mencoba melakukan push.
- Log eksekusi penolakan `git push --force-with-lease` saat terjadi konflik, diikuti keberhasilan eksekusi pasca sinkronisasi tracking reference.
- Output dari `git remote prune` atau `git fetch --prune` yang menunjukkan deregistrasi pointer reference remote yang telah dihapus.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur layer data: Pemisahan state commit antara local HEAD, remote-tracking reference (`refs/remotes/`), dan remote server HEAD.
- [ ] Struktur sintaks Refspec: `<flag><src>:<dst>` dan dampaknya terhadap pemetaan commit graf lokal.
- [ ] Perbedaan deterministik antara `git fetch` (non-mutating to local working tree) dan `git pull` (fetch + merge/rebase).
- [ ] Mekanisme Compare-and-Swap (CAS) yang mendasari `git push --force-with-lease` sebagai standar pengganti `git push --force`.
- [ ] Wire transport protocol Git: Mekanisme dasar SSH multiplexing vs. Smart HTTP packfile negotiation.
- [ ] Dampak persistensi zombie reference saat branch di server hosting dihapus dan peran command `git prune`.

### Saya tidak perlu menghafal:
- [ ] Format biner internal dari *pkt-line framing* pada transmisi data Git Smart HTTP Protocol.
- [ ] Seluruh parameter flags kriptografi SSH cipher suite saat melakukan debugging koneksi.
- [ ] Algoritma kompresi zlib/pack-index internal (`.idx` dan `.pack`) saat Git membuat thin packfile via network.

### Saya harus bisa melakukan:
- [ ] Menambahkan, mengganti nama, memodifikasi URL, dan menghapus remote repository menggunakan `git remote`.
- [ ] Melakukan isolasi push URL pada level `.git/config` untuk mencegah insiden penulisan data ke remote upstream yang dilindungi.
- [ ] Mengonfigurasi custom refspec untuk mengatur selectively fetched branches dari remote.
- [ ] Mengatasi kegagalan push non-fast-forward secara profesional melalui rebase/merge flow tanpa merusak history kolaborator.
- [ ] Mengaudit status sinkronisasi pointer remote vs. lokal menggunakan `git remote show <name>` dan `git ls-remote`.
- [ ] Membersihkan remote-tracking references lokal yang sudah kadaluarsa menggunakan `git fetch --prune`.