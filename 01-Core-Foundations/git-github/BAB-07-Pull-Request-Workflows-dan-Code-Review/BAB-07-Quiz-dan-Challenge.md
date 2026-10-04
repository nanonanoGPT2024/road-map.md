# BAB 07: Quiz, Challenge, & Knowledge Check
**Pull Request Workflows & Code Review Mechanics**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Diferensiasi Ontologis: Git Core vs. Git Hosting Platform**  
   Jelaskan secara struktural mengapa objek *Pull Request* (PR) atau *Merge Request* (MR) tidak eksis di dalam direktori internal `.git` lokal Anda. Bagaimana platform seperti GitHub/GitLab memetakan PR ke dalam Git references (`refs/pull/*/head` dan `refs/pull/*/merge`) untuk memungkinkan komputasi diff dan pengujian CI secara deterministik?

2. **Dinamika Merge Strategies & Topologi Riwayat**  
   Bandingkan secara mendalam tiga strategi penggabungan PR utama: **Merge Commit (`--no-ff`)**, **Squash and Merge**, dan **Rebase and Merge**. Analisis dampak masing-masing strategi terhadap:
   - Kemampuan pelacakan regresi menggunakan `git bisect`.
   - Granularitas atomisitas commit (*revertability* fitur parsial).
   - Integritas tanda tangan kriptografis (*GPG/SSH signature verification*).

3. **Mekanisme Three-Way Merge dan `git merge-base`**  
   Ketika GitHub menampilkan *"Able to merge"* atau mendeteksi konflik pada sebuah PR, bagaimana Git hosting engine memanfaatkan perintah `git merge-base` di balik layar untuk menemukan *common ancestor* antara branch target (`base`) dan branch fitur (`head`)? Apa yang memicu kalkulasi ulang diff ketika branch `base` diperbarui?

4. **Arsitektur dan Evaluasi Deklaratif `CODEOWNERS`**  
   Bagaimana algoritma parsing file `.github/CODEOWNERS` bekerja ketika terdapat aturan yang saling tumpang tindih (*overlapping patterns*)? Jelaskan urutan presedensinya (apakah *first-match*, *last-match*, atau *most-specific-match*) dan bagaimana integrasinya dengan aturan *Protected Branch* untuk memblokir merger tanpa persetujuan eksplisit dari tim pemilik domain.

5. **Strict vs. Loose Branch Protection Rules**  
   Dalam konteks *Branch Protection Rules*, jelaskan perbedaan fungsional antara mengaktifkan opsi **"Require branches to be up to date before merging"** (Strict status checks) versus membiarkannya nonaktif (Loose status checks). Risiko integritas kode apa yang muncul pada sistem produksi jika opsi strict dimatikan pada repositori dengan frekuensi commit tinggi?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Anatomi Force-Push dan Review Continuity Tracking**  
   Seorang *developer* melakukan `git push --force` setelah melakukan rebase interaktif lokal untuk merespons komentar review. Jelaskan mengapa tindakan ini merusak histori *inline review comments* pada GitHub UI. Mengapa penggunaan `git push --force-with-lease` lebih aman dalam lingkungan kolaboratif, dan bagaimana platform modern mempertahankan *inter-diff* (perbandingan antar *force-pushes*)?

2. **Debugging Merge Conflict Semantik (*Semantic Conflict*) vs. Leksikal**  
   Dua PR yang berjalan paralel dinyatakan *"Mergeable: Clean"* (bebas konflik leksikal oleh Git) dan keduanya lolos seluruh unit test di CI masing-masing. Namun, segera setelah keduanya di-merge ke branch `main`, *build* pada `main` langsung gagal (*broken build*). 
   - Analisis secara mekanis bagaimana anomali ini dapat terjadi.
   - Perubahan arsitektur validasi apa yang harus diterapkan pada pipeline CI untuk mencegat kasus ini sebelum PR di-merge?

3. **Mekanisme Re-merging pasca Squash and Merge Divergence**  
   Sebuah *long-lived feature branch* di-merge sebagian ke `main` menggunakan metode *Squash and Merge*. Beberapa hari kemudian, developer melanjutkan pekerjaan pada branch yang sama dan mencoba membuka PR kedua ke `main`. Mengapa Git mendeteksi ratusan konflik dan menduplikasi commit lama yang sebenarnya sudah masuk ke `main`? Bagaimana cara menyelesaikan kondisi ini secara deterministik?

4. **Security Vector: Public Fork Pull Requests & CI Secrets Exploitation**  
   Pada repositori *open-source*, mengapa event trigger `pull_request` mengeksekusi workflow CI di dalam konteks read-only tanpa akses ke repository secrets, sedangkan event `pull_request_target` memberikan akses ke secrets dan context branch `base`? Jelaskan skenario eksploitasi di mana penyerang (*malicious contributor*) dapat mencuri secrets produksi melalui PR berbahaya jika `pull_request_target` salah dikonfigurasi bersama tindakan `actions/checkout`.

5. **Resolusi Mass-Formatting Noise Menggunakan `.git-blame-ignore-revs`**  
   Ketika sebuah PR menerapkan linter/formatter otomatis (misal: Prettier atau Black) pada 500 file secara bersamaan, riwayat `git blame` akan terpolusi oleh commit formatting tersebut. Bagaimana Anda mengonfigurasi repositori dan menginstruksikan tim agar Git CLI serta antarmuka web hosting platform mengabaikan SHA commit pemformatan massal ini secara permanen tanpa kehilangan jejak kepemilikan kode historis?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Merge Queue pada Monorepo Skala Enterprise
**Konteks Insiden:**  
Sebuah organisasi FinTech mengelola monorepo yang menampung 40 microservices dengan 150 insinyur aktif. Repositori menerapkan *Strict Status Checks* (branch harus *up-to-date* sebelum merge). Setiap pipeline CI membutuhkan waktu 20 menit untuk menjalankan seluruh test suite. 

**Masalah:**  
Terjadi fenomena *throughput starvation*: Ketika PR #101 di-merge ke `main`, seluruh PR lain yang siap di-merge (#102, #103, #104) langsung dinyatakan *outdated*. Developer harus mengklik tombol *"Update branch"*, memicu ulang CI selama 20 menit. Akibatnya, dalam satu hari kerja 8 jam, repositori maksimal hanya mampu memproses $\approx 24$ PR, sementara antrean PR mencapai 70+ PR per hari. Produktivitas tim teknik anjlok drastis.

**Pertanyaan Diagnostik & Solusi:**
1. Rancang arsitektur implementasi **Merge Queue** (seperti GitHub Merge Queue atau Bors-NG) berbasis *speculative execution* / *optimistic batching* untuk memecahkan bottleneck ini.
2. Bagaimana algoritma antrean tersebut memvalidasi kombinasi batch PR (`PR #102 + PR #103`) secara paralel, dan bagaimana mekanismenya melakukan *bisect & eject* jika salah satu PR di tengah antrean memicu kegagalan test?

---

### Skenario B: Race Condition dan Data Schema Drift
**Konteks Insiden:**  
Dua tim bekerja pada fitur berbeda:
- **Tim Auth (PR #501):** Mengubah kolom database `users.phone_number` menjadi `users.msisdn` melalui file migrasi `V12__rename_phone.sql` dan memperbarui kode servis autentikasi.
- **Tim Notification (PR #502):** Menambahkan fitur SMS blasting baru yang melakukan *query* langsung ke kolom `users.phone_number` melalui migrasi `V13__add_sms_index.sql`.

Kedua PR dibuka dari base commit yang sama (`main@commit_001`). CI pada masing-masing PR sukses 100%. Tim Auth melakukan merge PR #501 pada pukul 14:00. Lima menit kemudian, tanpa memperbarui branch-nya, Tim Notification me-merge PR #502 karena tombol merge masih berwarna hijau (Loose protection aktif). 

**Masalah:**  
Aplikasi produksi langsung *crash* dengan error `UndefinedColumn: column "phone_number" does not exist` saat servis notifikasi dieksekusi.

**Pertanyaan Diagnostik & Solusi:**
1. Mengapa Git Three-Way Merge Engine sama sekali tidak membunyikan alarm konflik leksikal pada file migrasi database tersebut?
2. Bagaimana Anda merancang sistem validasi arsitektural di level CI PR (misal: *ephemeral database integration testing against target branch head*) untuk mendeteksi *schema drift* semacam ini sebelum penggabungan terjadi?

---

### Skenario C: Audit Compliance vs. Git Hygiene Trade-off (SOC2 / ISO 27001)
**Konteks Arsitektur:**  
Sebuah perusahaan perbankan bersiap untuk audit kepatuhan SOC2 Type II. Auditor mewajibkan bahwa:
- Setiap perubahan kode pada lingkungan produksi harus terikat 1:1 ke sebuah tiket Jira yang telah disetujui.
- Setiap *artifact* commit SHA di branch `main` harus ditandatangani secara kriptografis (*Signed Commits* dengan GPG/KMS) dan memiliki metadata reviewer yang tidak bisa dimanipulasi.

Manajemen engineering menginginkan riwayat Git yang benar-benar linier (*Trunk-Based Development* murni tanpa *merge bubbles*) dan bersih dari commit sampah (*WIP commits*).

**Pertanyaan Evaluasi & Trade-off:**
1. Jika tim memilih strategi **Squash and Merge via GitHub UI**, siapakah yang menjadi penandatangan (*committer/signer*) dari SHA baru yang terbentuk di `main`? Apakah GPG developer lokal tetap valid, atau commit ditandatangani oleh platform web key? Apa dampaknya terhadap audit non-repudiation?
2. Bandingkan trade-off kepatuhan audit antara strategi **Rebase Locally + GPG Sign + Fast-Forward Only Merge** melawan **GitHub Web-Enforced Squash Merge**. Rekomendasikan arsitektur alur kerja PR mana yang paling seimbang antara *developer experience*, kebersihan riwayat (*history cleanliness*), dan *regulatory compliance*.

---

## 4. Chapter Challenge

### Tantangan Praktis: Perancangan Enterprise-Grade PR Protection Pipeline dengan Automated Semantic & Compliance Gate

#### Deskripsi Masalah
Sebagai Principal Engineer, Anda ditugaskan merekayasa sistem tata kelola PR (*PR Governance Pipeline*) pada sebuah repositori inti yang menangani layanan pembayaran kritis. Repositori ini sering mengalami insiden regresi akibat ulasan kode yang terburu-buru, inkonsistensi penamaan commit, dan *bypassing* pemeriksaan keamanan.

#### Spesifikasi Kebutuhan (Requirements)

1. **Konfigurasi `CODEOWNERS` Modular:**
   - Direktori `src/security/` dan `infra/terraform/` wajib mendapatkan persetujuan dari `@enterprise/infosec-leads`.
   - File konfigurasi build (`package.json`, `Dockerfile`, CI workflows) wajib disetujui oleh `@enterprise/platform-engineers`.
   - Jalur kode lainnya (`src/modules/`) wajib disetujui oleh minimal salah satu engineer dari `@enterprise/core-devs`.
   - Aturan keamanan tidak boleh ter-override oleh aturan umum aplikasi.

2. **Automated Gate Pipeline (GitHub Actions / GitLab CI):**
   - Buat workflow CI yang memvalidasi bahwa setiap PR memenuhi kriteria:
     - **Title Linting:** Judul PR harus mematuhi format *Conventional Commits* (contoh: `feat(payment): implement QRIS settlement`).
     - **PR Size Guard:** Menolak atau memberi label peringatan keras jika diff PR melebihi 500 baris kode (tidak termasuk file autogenerated / lockfile) untuk mendorong *atomic micro-PRs*.
     - **Semantic Merge Gate (Pre-merge test against virtual merge target):** Workflow harus mengeksekusi test bukan pada commit HEAD branch fitur semata, melainkan pada hasil virtual merge antara `refs/remotes/origin/main` dan HEAD branch fitur.

3. **Branch Protection Specification Document:**
   - Tuliskan konfigurasi deklaratif (JSON / Terraform format untuk GitHub API) yang memaksakan:
     - Minimum 2 approvals.
     - Dismiss stale pull request approvals when new commits are pushed.
     - Require review from Code Owners.
     - Require status checks to pass before merging (Strict mode).
     - Require signed commits.
     - Block force pushes dan direct branch deletion.

#### Batasan Teknis (Constraints)
- Tidak boleh menggunakan *third-party marketplace actions* yang berbayar atau closed-source; gunakan GitHub Actions resmi (`actions/*`) atau bash script murni di dalam runner container.
- Pipeline harus mengecualikan file `package-lock.json` atau `pnpm-lock.yaml` dari perhitungan baris diff review guard.

#### Expected Output
1. File `.github/CODEOWNERS` yang teruji presedensinya.
2. File `.github/workflows/pr-governance.yml` yang berisi logika:
   - PR Title Linting.
   - PR Diff Size Gate.
   - Virtual Merge Test Runner.
3. Skrip deklaratif konfigurasi Branch Protection (misal: payload API call GitHub REST/GraphQL atau blok Terraform `github_branch_protection`).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara `pull_request` refspec (`refs/pull/<id>/head` vs `refs/pull/<id>/merge`) pada server Git internal GitHub.
- [ ] Perbedaan matematis dan topologis antara strategi `Merge Commit`, `Squash and Merge`, dan `Rebase and Merge`.
- [ ] Mekanisme kerja `git merge-base` dalam mendeteksi konflik Three-Way Merge.
- [ ] Cara parsing dan aturan evaluasi presedensi file `CODEOWNERS`.
- [ ] Dampak aktivasi *Strict Status Checks* terhadap siklus hidup branch dan throughput tim.
- [ ] Mengapa *Semantic Merge Conflicts* lolos dari deteksi standar Git Three-Way Merge leksikal.
- [ ] Trade-off kriptografis dan compliance antara *local commit signing* vs platform-generated commit signing pada alur Squash/Rebase.
- [ ] Risiko keamanan injeksi secrets pada event trigger `pull_request_target` dari public fork.

### Saya tidak perlu menghafal:
- [ ] Format JSON lengkap dari response payload GitHub GraphQL API untuk *PullRequest object*.
- [ ] Seluruh flag CLI eksotik dari perintah `git merge-tree`.
- [ ] Sintaks exact regex dari seluruh implementasi commit linter pihak ketiga (cukup memahami spesifikasi *Conventional Commits*).

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi file `.github/CODEOWNERS` multi-layer dengan presedensi path yang tepat tanpa konflik aturan.
- [ ] Mengaktifkan dan menguji *Branch Protection Rules* tingkat enterprise via Terraform atau GitHub Management Console.
- [ ] Menjalankan simulasi resolusi merge conflict lokal dengan memeriksa *common ancestor* menggunakan `git merge-base` dan `git diff <base>...<head>`.
- [ ] Melakukan investigasi inter-diff antar force-push pada interface review PR untuk mendeteksi perubahan tersembunyi.
- [ ] Mengonfigurasi file `.git-blame-ignore-revs` untuk menjaga kebersihan anotasi historis kode dari commit formatting masal.
- [ ] Merancang pipeline verifikasi CI yang menguji state gabungan (*virtual merge commit*) sebelum PR diizinkan masuk ke branch produksi.