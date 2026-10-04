# BAB 05: Quiz, Challenge, & Knowledge Check
**Integrasi Kode: Fast-Forward, 3-Way Merge, dan Rebase Dasar**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Mekanisme Pointer Fast-Forward vs Non-Fast-Forward (`--no-ff`)
Jelaskan secara struktural apa yang terjadi pada *Directed Acyclic Graph* (DAG) dan pointer referensi Git ketika sebuah integrasi cabang diklasifikasikan sebagai *Fast-Forward*. Mengapa dalam arsitektur repositori skala enterprise, tim rekayasa perangkat lunak sering kali secara eksplisit menonaktifkan perilaku ini menggunakan flag `--no-ff` meskipun integrasi *Fast-Forward* dimungkinkan secara topologi?

### Soal 1.2: Anatomi Triangulasi 3-Way Merge
Operasi 3-Way Merge tidak hanya membandingkan commit ujung (*tip*) dari cabang target (`ours`) dan cabang sumber (`theirs`), melainkan membutuhkan commit ketiga yaitu *Merge Base* (titik leluhur bersama / *common ancestor*). Uraikan bagaimana algoritma Git mengevaluasi modifikasi file menggunakan ketiga titik referensi ini untuk menentukan apakah suatu baris kode dapat digabungkan secara otomatis (*clean merge*) atau memicu *merge conflict*.

### Soal 1.3: Ontologi Rebase vs Merge: Linearitas vs Integritas Historis
Ditinjau dari ontologi pencatatan riwayat Git, jelaskan perbedaan filosofis mendasar antara `git merge` dan `git rebase`. Mengapa `git rebase` secara teknis didefinisikan sebagai operasi yang "menulis ulang sejarah" (*rewriting history*), dan apa yang sebenarnya terjadi pada identitas SHA-1 dari commit-commit yang dipindahkan selama proses rebase berlangsung?

### Soal 1.4: Pergerakan Pointer HEAD dan Relasi Reflog Selama Rebase
Ketika Anda mengeksekusi `git checkout feature && git rebase main`, bagaimana pergerakan pointer `HEAD` dan branch reference `feature` dimanipulasi oleh Git dari awal hingga akhir proses? Apa status pointer `HEAD` di tengah proses rebase jika terjadi konflik pada commit ke-2 dari 5 commit yang sedang di-*replay*?

### Soal 1.5: Struktur Internal Marker Konflik
Ketika Git gagal melakukan integrasi otomatis dan mencetak status konflik pada sebuah file, Git akan menginjeksi *conflict markers* ke dalam working tree. Bedah struktur anatomi dari penanda berikut:
```text
<<<<<<< HEAD
// Segment A
=======
// Segment B
>>>>>>> feature-branch
```
Jelaskan apa representasi data dari `Segment A`, pemisah `=======`, dan `Segment B`, serta mengapa Git menghentikan proses eksekusi dan menyerahkan resolusi sepenuhnya ke *working tree* pengguna.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Resolusi Merge-Base pada *Criss-Cross Merge*
Pada topologi commit yang kompleks, sering kali ditemukan situasi di mana dua cabang memiliki lebih dari satu *common ancestor* independen (dikenal sebagai anomali *Criss-Cross Merge*). Bagaimana algoritma default Git (`ort` atau `recursive`) menangani kondisi ketika terdapat dua atau lebih *merge-base* kandidat? Jelaskan konsep pembuatan *virtual merge base* untuk mengatasi ambiguitas tersebut.

### Soal 2.2: Violasi "The Golden Rule of Rebasing" dan Dampak Cascading
Jelaskan landasan teknis di balik *The Golden Rule of Rebasing*: *"Jangan pernah melakukan rebase pada commit yang telah dipublikasikan ke remote repository publik/bersama"*. Jika seorang engineer melanggar aturan ini pada branch kolaboratif dan melakukan `git push --force`, jelaskan skenario anomali *cascading duplicate commits* yang akan dihadapi oleh anggota tim lain saat mereka melakukan `git pull`.

### Soal 2.3: State Machine Rollback: `.git/MERGE_HEAD` vs `.git/rebase-merge`
Ketika integrasi mengalami kebuntuan konflik:
1. File artefak apa yang disimpan Git di dalam direktori `.git/` selama kegagalan `git merge` (misal: status `MERGE_HEAD`, `MERGE_MSG`)?
2. Bagaimana struktur direktori internal Git berubah saat berada di tengah proses rebase yang berkonflik (misal: `.git/rebase-apply` atau `.git/rebase-merge`)?
3. Jelaskan perbedaan mendasar operasi `git merge --abort` dibanding `git reset --hard ORIG_HEAD`.

### Soal 2.4: Fenomena *Repetitive Conflict* Selama Iterasi Rebase Replay
Seorang engineer melakukan rebase terhadap cabang yang memiliki 10 commit di atas cabang `main`. Pada commit ke-1, muncul konflik pada file konfigurasi `application.yml` dan diselesaikan via `git add application.yml && git rebase --continue`. Mengapa konflik pada file yang sama persis bisa muncul kembali pada commit ke-3 dan commit ke-7 dalam satu sesi rebase yang sama? Mengapa fitur `git rerere` (*reuse recorded resolution*) menjadi krusial dalam skenario ini?

### Soal 2.5: Squash Merge vs Rebase Linear: Autopsi Metadata Author dan Committer
Banyak platform (seperti GitHub/GitLab) menyediakan opsi *Squash and Merge* dan *Rebase and Merge*. Dari sudut pandang struktur Git Object (khususnya commit object fields: `tree`, `parent`, `author`, dan `committer`):
1. Apa perbedaan esensial antara hasil dari sebuah *Squash Merge* dibanding *Interactive Rebase + Fast-Forward Merge*?
2. Apa konsekuensi jangka panjang terhadap penelusuran regresi menggunakan `git bisect` untuk kedua pendekatan tersebut?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Pipeline CI/CD Akibat Fast-Forward di Production Release Branch
**Konteks Insiden:**
Sebuah tim platform menerapkan Continuous Deployment ke kluster produksi yang dipicu secara otomatis oleh commit baru pada cabang `production`. Deployment pipeline membaca commit message untuk menentukan versi rilis SemVer dan men-generate release notes secara otomatis via Git tag parsing.

Seorang engineer mengintegrasikan branch `hotfix/memleak-fix` ke `production` menggunakan `git merge hotfix/memleak-fix` tanpa flag tambahan. Karena cabang `production` tidak memiliki commit baru sejak hotfix dicabangkan, Git mengeksekusi *Fast-Forward merge*. Akibatnya:
- Tidak ada merge commit baru yang terbuat.
- Pipeline CI/CD mendeteksi rentetan 6 commit granular developer (misal: "fix typo", "retest memory", "wip") yang langsung masuk ke `production`.
- Sistem rilis otomatis gagal membedakan batas integrasi rilis dan men-trigger multiple rogue builds ke server produksi, menyebabkan downstream cache invalidation race condition.

**Pertanyaan Diagnostik:**
1. Mengapa eksekusi *Fast-Forward* menghancurkan metadata struktural integrasi dalam konteks rilis otomatis ini?
2. Bagaimana cara mengembalikan (*rollback*) branch `production` secara instan ke state tepat sebelum merge terjadi tanpa menghapus riwayat reflog lokal?
3. Kebijakan branch protection dan konfigurasi merge strategi apa yang harus dikonfigurasi di level Git repository config / GitHub settings untuk menjamin insiden ini tidak terulang?

---

### Skenario B: *Semantic Conflict* Tersembunyi (Clean 3-Way Merge Berujung Fatal di Staging)
**Konteks Insiden:**
Dua fitur dikembangkan secara paralel:
- Cabang `feature/refactor-auth`: Mengubah signature fungsi inti dari:
  `authenticate(user: String, pass: String): Boolean`
  menjadi:
  `authenticate(credentials: AuthContext): AuthResult`
  (Semua pemanggilan fungsi di file internal auth telah diubah).
- Cabang `feature/payment-v2`: Menambahkan endpoint baru di controller `PaymentController.kt` yang memanggil fungsi lama:
  `authenticate(currentUser, currentToken)`.

Branch `feature/refactor-auth` di-merge ke cabang `develop` via 3-way merge dengan sukses tanpa konflik. Setengah jam kemudian, `feature/payment-v2` di-merge ke `develop`. Git melaporkan:
`Auto-merging src/controllers/PaymentController.kt`
`Merge made by the 'ort' strategy.`
Tidak ada conflict marker yang muncul. Namun, branch `develop` langsung mengalami kegagalan kompilasi total (*build breakage*) di staging pipeline.

**Pertanyaan Diagnostik:**
1. Mengapa Git menyatakan operasi merge tersebut *CLEAN* padahal kode secara semantik rusak parah? Jelaskan batasan Git sebagai *content tracker* tekstual berbasis chunk baris kode.
2. Jika tim Anda menerapkan workflow *Feature Branch Integration*, mekanisme pengujian pre-merge apa (*pre-merge validation*) yang harus dipasang untuk mendeteksi *semantic conflict* ini sebelum commit penggabungan diizinkan mendarat di branch utama?
3. Langkah teknis apa yang harus dilakukan engineer `feature/payment-v2` di lokal untuk mengintegrasikan perubahan terbaru dari `develop` sebelum membuka Pull Request ulang? Bandingkan eksekusi via `git merge origin/develop` vs `git rebase origin/develop`.

---

### Skenario C: Dilema Arsitektur Git DAG pada Monorepo Skala Besar
**Konteks Arsitektur:**
Perusahaan Anda memiliki monorepo dengan 400 engineer aktif yang melakukan rata-rata 600 commit per hari. Tim Core Infrastructure sedang memperdebatkan standarisasi strategi integrasi branch fitur ke branch `main`.

- **Fraksi A (Purist Linear DAG):** Menuntut penggunaan *Pure Rebase + Fast-Forward*. Argumentasi: Riwayat commit menjadi 100% linear, sangat mudah dibaca menggunakan `git log`, mempermudah troubleshooting insiden dengan `git bisect`, dan eliminasi "merge bubbles" yang berantakan.
- **Fraksi B (True Topology DAG):** Menuntut penggunaan *Merge Non-Fast-Forward (`--no-ff`)* untuk setiap Pull Request. Argumentasi: Mempertahankan batasan kontekstual fitur secara utuh (*atomic group of commits*), tidak memanipulasi waktu pembuatan commit asli, dan mempermudah revert satu fitur penuh hanya dengan membatalkan satu merge commit (`git revert -m 1 <merge-commit-sha>`).

**Pertanyaan Diagnostik:**
1. Bedah kelemahan teknis dari **Fraksi A** pada lingkungan monorepo dengan 600 commit per hari jika pengujian CI/CD membutuhkan waktu 20 menit per commit run. Jelaskan konsep *rebase thrashing / merge race condition*.
2. Bedah kelemahan teknis dari **Fraksi B** ketika tim harus melakukan debugging mendalam pada insiden kritis menggunakan `git bisect`.
3. Sebagai Senior Principal Engineer, usulkan solusi arsitektural jalan tengah (misalnya: *Semi-linear history* / *Squash-merge policy* / *Merge Queue*) beserta evaluasi trade-off komputasi CI dan keterbacaan riwayat repo.

---

## 4. Chapter Challenge

### Tantangan Praktis: Simulasi Krisis Divergensi dan Resolusi Rebase Kompleks

#### Problem
Anda ditugaskan menyelamatkan repositori layanan `core-ledger` yang mengalami divergensi historis parah. Cabang `feature/tax-engine` tertinggal 4 commit di belakang cabang `main`. Sementara itu, cabang `main` telah menerapkan security hotfix yang merestrukturisasi path file konfigurasi dari `config/app.json` ke `config/v2/app.json`. 

Cabang `feature/tax-engine` memiliki 3 commit berurutan yang memodifikasi file `config/app.json` (lama) dan menambahkan file `tax/calculator.go`. Jika Anda melakukan integrasi langsung secara sembarangan, file konfigurasi lama akan bangkit kembali (*resurrected file*) atau memicu konflik buntu yang merusak riwayat commit.

#### Requirements
1. **Inisialisasi Lingkungan Simulasi (Shell Script/CLI):**
   - Buat Git repository baru di folder lokal.
   - Buat cabang `main` dengan commit awal: file `config/app.json` dan `ledger/ledger.go`.
   - Buatkan cabang `feature/tax-engine` dari titik ini.
   - Di cabang `feature/tax-engine`, buat 3 commit granular:
     - Commit 1: `tax: add calculation skeleton` (tambah `tax/calculator.go`)
     - Commit 2: `config: update tax limits` (ubah `config/app.json`)
     - Commit 3: `tax: implement logic` (ubah `tax/calculator.go`)
   - Kembali ke `main`, buat 2 commit independen:
     - Commit A: `ledger: refactor entry points` (ubah `ledger/ledger.go`)
     - Commit B: `security: migrate config to v2 path` (pindahkan `config/app.json` ke `config/v2/app.json` menggunakan `git mv` dan modifikasi isinya).

2. **Eksekusi Rebase Terkendali:**
   - Lakukan rebase cabang `feature/tax-engine` ke atas cabang `main`.
   - Selesaikan konflik pemindahan path file `config/app.json` vs `config/v2/app.json` pada commit terkait secara deterministik (perubahan limit pajak dari feature branch harus berhasil masuk ke path baru `config/v2/app.json`, dan file lama `config/app.json` tidak boleh muncul kembali).
   - Pastikan histori 3 commit dari `feature/tax-engine` tetap utuh dan tersusun rapi di atas commit `security: migrate config to v2 path`.

3. **Finalisasi Integrasi:**
   - Pindahkan pointer `main` ke cabang `feature/tax-engine` menggunakan strategi integrasi yang menghasilkan riwayat linear sempurna (*Fast-Forward*).

#### Constraints
- Dilarang menghapus repositori dan mengulang dari awal saat konflik terjadi.
- Dilarang menggunakan `git merge` dalam proses penyelesaian cabang; seluruh proses alignment histori wajib dieksekusi via `git rebase`.
- File konfigurasi lama `config/app.json` tidak boleh ada di cabang `main` setelah operasi selesai.

#### Expected Output
Tampilkan verifikasi visual riwayat repository menggunakan perintah:
```bash
git log --graph --oneline --decorate --all
```
Dan pastikan output menampilkan struktur linear tanpa merge bubbles:
```text
* <SHA-6> (HEAD -> main, feature/tax-engine) tax: implement logic
* <SHA-5> config: update tax limits
* <SHA-4> tax: add calculation skeleton
* <SHA-3> security: migrate config to v2 path
* <SHA-2> ledger: refactor entry points
* <SHA-1> initial commit
```
Sertakan juga verifikasi working tree:
```bash
git ls-tree -r --name-only HEAD
```
Menunjukkan file terdaftar:
```text
config/v2/app.json
ledger/ledger.go
tax/calculator.go
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan deterministik antara pergerakan pointer pada integrasi *Fast-Forward* dan pembuatan commit objek baru pada *3-Way Merge*.
- [ ] Fungsi matematis *Merge Base* dalam mendeteksi divergensi perubahan teks baris kode.
- [ ] Mengapa operasi `git rebase` menciptakan objek commit baru dengan SHA-1 yang sama sekali berbeda meskipun teks perubahannya (*diff*) identik.
- [ ] Risiko struktural *force pushing* (`--force` vs `--force-with-lease`) terhadap cabang kolaboratif pasca-rebase.
- [ ] Batasan Git dalam mendeteksi dependensi kode logis (*semantic conflicts*) di luar lingkup pencocokan teks statis.
- [ ] State lifecycle dari direktori internal `.git/` saat proses merge/rebase tertahan oleh konflik.

### Saya tidak perlu menghafal:
- [ ] Detail implementasi byte-code komputasi algoritma pemecah konflik recursive internal (`histogram diff` vs `myers diff`).
- [ ] Format biner internal dari file indeks Git (`.git/index`).
- [ ] Sintaks puluhan parameter konfigurasi tingkat rendah dari `git merge-file`.

### Saya harus bisa melakukan:
- [ ] Mengeksekusi integrasi cabang lokal menggunakan `git merge --no-ff` untuk mempreservasi dokumentasi topologi fitur.
- [ ] Melakukan `git rebase <upstream>` untuk menyelaraskan riwayat commit cabang fitur lokal terhadap perubahan terbaru dari branch kolaboratif.
- [ ] Menghentikan dan mengembalikan repository ke kondisi bersih saat proses integrasi gagal via `git merge --abort` atau `git rebase --abort`.
- [ ] Menganalisis dan menyelesaikan teks konflik secara manual di working tree dengan menghapus penanda `<<<<<<<`, `=======`, dan `>>>>>>>` secara presisi.
- [ ] Menginspeksi titik persimpangan leluhur bersama (*common ancestor*) antara dua cabang menggunakan perintah `git merge-base branch-a branch-b`.
- [ ] Melakukan audit commit tree pasca-integrasi menggunakan kombinasi logging visual `git log --graph --oneline --boundary`.