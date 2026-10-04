# BAB 08: Quiz, Challenge, & Knowledge Check
**Ekosistem GitHub: Pull Requests, Issues, & Project Governance**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Ontologi Pull Request vs Git Core
Secara fundamental arsitektural, Git murni (*distributed version control system*) tidak mengenal entitas yang bernama "Pull Request" (PR). Git hanya mengenal objek *commit*, *tree*, *blob*, *tag*, serta referensi *branch* dan *remote*. 
* Jelaskan bagaimana platform *forge* seperti GitHub mengabstraksikan Pull Request di atas Git engine! 
* Bagaimana GitHub menyimpan metadata PR tersebut di internal server-nya menggunakan namespace referensi `refs/pull/`?

### Soal 1.2: Analisis Topologi DAG pada Tiga Strategi Integrasi PR
GitHub menyediakan tiga strategi penggabungan (*merge strategies*) untuk Pull Request: **Create a merge commit**, **Squash and merge**, dan **Rebase and merge**.
* Bedah dampak dari masing-masing strategi tersebut terhadap topologi *Directed Acyclic Graph* (DAG) dan riwayat commit (*commit history*) pada branch target (`main`)!
* Sebutkan trade-off terpenting dari masing-masing metode terkait keterlacakan (*traceability*), isolasi perubahan fitur, dan kemampuan eksekusi `git bisect` di masa depan!

### Soal 1.3: Mekanisme Resolusi Issue Otomatis (*Closing Keywords*)
GitHub mendukung penutupan Issue secara otomatis melalui commit message atau PR description menggunakan *keywords* seperti `Closes #123`, `Fixes #123`, atau `Resolves #123`.
* Jelaskan mekanisme *event-driven* internal GitHub dalam mendeteksi dan mengeksekusi penutupan issue tersebut!
* Mengapa penulisan `Fixes #123` di dalam commit message pada *feature branch* yang belum di-merge **tidak** menutup issue tersebut seketika, dan mengapa penulisan keyword tersebut di dalam nama branch (contoh: `fix-123-bug`) tidak memicu penutupan issue secara otomatis?

### Soal 1.4: Arsitektur Governance: CODEOWNERS vs Branch Protection Rules
Jelaskan perbedaan peran fungsional dan level abstraksi antara file konfigurasi `.github/CODEOWNERS` dengan konfigurasi **Branch Protection Rules** (atau **Repository Rulesets**) pada GitHub!
* Bagaimana kedua komponen ini berkolaborasi untuk menegakkan aturan *two-man rule* (pemisahan kewenangan)?
* Apa yang terjadi jika file `.github/CODEOWNERS` menetapkan `@core-team` sebagai penanggung jawab direktori `/src/security/`, tetapi Branch Protection Rule pada branch `main` tidak mengaktifkan opsi *"Require review from Code Owners"*?

### Soal 1.5: Standarisasi Masukan Menggunakan GitHub Issue Forms vs Markdown Templates
GitHub menyediakan dua mekanisme standardisasi issue: *Legacy Markdown Templates* (file `.md`) dan *GitHub Issue Forms* (file `.yml`).
* Mengapa *Issue Forms* berbasis schema YAML dianggap jauh lebih unggul dalam konteks tata kelola enterprise (*project governance*) dibanding template Markdown murni?
* Bagaimana validasi input, integrasi *labeling* otomatis, dan pencegahan *garbage input* dieksekusi oleh GitHub menggunakan skema Form ini?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Batasan Mesin Resolusi Konflik GitHub UI
Ketika sebuah Pull Request mengalami konflik dengan target branch, terkadang GitHub UI mengizinkan pengembang menyelesaikan konflik secara visual melalui tombol *"Resolve conflicts"*, namun di lain waktu tombol tersebut berstatus *disabled* (*grayed out*) dengan pesan bahwa konflik terlalu rumit dan harus diselesaikan secara lokal melalui CLI.
* Analisis batasan teknis internal dari *conflict resolution parser* milik GitHub UI! Kondisi diff apa saja (misalnya: *binary files*, *renamed files*, *directory-file collisions*, konflik ukuran besar) yang memaksa GitHub menolak resolusi melalui web UI?

### Soal 2.2: Mekanisme Ephemeral Refs: `refs/pull/[PR_NUMBER]/head` vs `refs/pull/[PR_NUMBER]/merge`
GitHub mengekspos dua *ephemeral references* untuk setiap PR yang dibuat:
1. `refs/pull/<ID>/head`
2. `refs/pull/<ID>/merge`
* Jelaskan perbedaan fundamental dari status commit yang ditunjuk oleh kedua ref tersebut!
* Mengapa workflow CI (seperti GitHub Actions) yang dipicu oleh event `on: pull_request` secara default mengeksekusi kode pada commit yang ditunjuk oleh `refs/pull/<ID>/merge` dan bukan `refs/pull/<ID>/head`? Apa implikasi arsitekturalnya terhadap integritas validasi pra-merge?

### Soal 2.3: Root Cause Analysis: Failure of CODEOWNERS Enforcement
Sebuah tim pengembang menemukan insiden di mana sebuah PR yang memodifikasi file `/src/payment/gateway.ts` berhasil di-merge ke branch `main` tanpa ada approval dari `@payment-lead`, padahal file `.github/CODEOWNERS` mendefinisikan:
```text
/src/payment/ @payment-lead
```
Branch Protection Rules pada branch `main` sudah aktif dengan opsi *"Require pull request reviews before merging"* (1 approval) dan *"Require review from Code Owners"* dicentang.
* Lakukan *root cause analysis* sistemik! Sebutkan minimal 3 kemungkinan penyebab konfigurasi atau arsitektur repository yang membuat aturan tersebut lolos tanpa persetujuan `@payment-lead`!

### Soal 2.4: Bottleneck Serialisasi pada "Require branches to be up to date before merging"
Pada repositori skala besar dengan *merge velocity* tinggi (misalnya 100 engineer melakukan merge per hari), mengaktifkan branch protection rule *"Require branches to be up to date before merging"* (Strict Status Checks) sering kali memicu fenomena yang disebut *CI Stampede* atau *Merge Congestion*.
* Jelaskan mengapa fitur ini memaksa serialisasi eksekusi integrasi branch!
* Bagaimana mekanisme *race condition* terjadi ketika PR A dan PR B sama-sama siap di-merge, PR A di-merge terlebih dahulu, dan status PR B langsung terdegradasi (*invalidated*)?
* Bagaimana GitHub **Merge Queue** memecahkan masalah ini pada level internal?

### Soal 2.5: Isolasi Keamanan Forking & Supply Chain Attacks pada GitHub Actions
Ketika seorang kontributor luar membuat Pull Request dari *forked repository* ke repositori publik organisasi Anda, GitHub secara otomatis membatasi akses workflow CI yang dipicu oleh PR tersebut:
* Mengapa default privilege untuk `GITHUB_TOKEN` pada event `pull_request` dari fork berstatus *read-only* dan tidak dapat membaca *GitHub Secrets* repositori upstream?
* Jelaskan risiko keamanan fatal (seperti *exfiltration of secrets* atau *remote code execution*) jika administrator ceroboh mengubah pemicu workflow menjadi `on: pull_request_target` tanpa memvalidasi commit SHA yang di-checkout!

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden "Merge Queue Deadlock" di Hari Rilis Produksi
* **Konteks:** Tim Enterprise Financial Core sedang mempersiapkan rilis akhir sprint pada Jumat pukul 16:00. Repositori dilindungi dengan branch protection ketat pada branch `main`:
  1. *Require a pull request before merging*.
  2. *Require approvals: 2 engineers*.
  3. *Require status checks to pass before merging: Strict (Branch must be up to date)*.
  4. CI pipeline memakan waktu eksekusi tepat 20 menit (unit test, integration test, linting, SAST).
* **Insiden:** Terdapat 15 PR fitur yang semuanya telah mendapatkan 2 approvals dan siap di-merge.
  - Engineer 1 mengklik *"Update branch with main"*, CI berjalan 20 menit, lalu mengklik *"Merge"*.
  - Segera setelah PR 1 masuk ke `main`, 14 PR lainnya langsung berubah status menjadi *"This branch is out-of-date with the base branch"* dan tombol *Merge* terkunci kembali.
  - Engineer 2, 3, dan 4 secara bersamaan menekan tombol *"Update branch"*, memicu 3 pipeline CI paralel selama 20 menit. Engineer 2 selesai sedikit lebih cepat dan menekan *"Merge"*. Seketika PR 3 dan PR 4 kembali *out-of-date* dan CI mereka harus diulang dari awal.
  - Terjadi kepanikan; proses rilis memakan waktu lebih dari 6 jam hanya untuk menggabungkan 15 PR sederhana, mengakibatkan pembatalan jadwal deployment.
* **Pertanyaan Diagnostik:**
  1. Identifikasi secara matematis dan prosedural mengapa model penggabungan berbasis *Strict Status Check* individual mengalami kegagalan skalabilitas linear ketika throughput PR meningkat!
  2. Rancang solusi arsitektural menggunakan fitur bawaan GitHub Enterprise untuk mengotomatisasi penggabungan ini secara paralel atau *batched* tanpa menurunkan standar integritas pengujian!
  3. Jika GitHub Merge Queue belum tersedia pada lisensi organisasi Anda, tuliskan workflow alternatif berbasis branch staging (misal: `release-candidate`) untuk mengatasi bottleneck tersebut secara logis!

---

### Skenario B: Audit Trail Breach & "Ghost Commits" pada Branch Produksi
* **Konteks:** Perusahaan teknologi kesehatan (*HealthTech*) yang terikat audit kepatuhan HIPAA dan SOC 2 Tipe II mengalami temuan audit serius. Auditor menemukan bahwa sebuah commit yang mengandung bug berbahaya masuk ke branch `main` pada tanggal 12 Mei.
* **Hasil Investigasi Awal:**
  - Branch protection mewajibkan: 1 PR approval, status check CI hijau, dan mematikan *"Allow force pushes"*.
  - PR #405 dibuat oleh Junior Dev pada 10 Mei, telah di-review dan di-approve secara resmi oleh Senior Dev pada 11 Mei pukul 10:00.
  - Namun, riwayat Git menunjukkan commit yang menyebabkan bug fatal memiliki commit timestamp 11 Mei pukul 14:00 (4 jam setelah approval diberikan).
  - Senior Dev bersumpah bahwa kode yang mengandung bug tersebut tidak ada saat ia memberikan tombol *Approve*.
* **Pertanyaan Diagnostik:**
  1. Bagaimana celah keamanan prosedural ini bisa terjadi di GitHub meskipun branch protection aktif? Konfigurasi spesifik apa pada Branch Protection Rule yang absen sehingga memungkinkan perubahan commit disisipkan ke dalam PR **setelah** approval diberikan?
  2. Apa perbedaan mekanisme antara opsi *"Dismiss stale pull request approvals when new commits are pushed"* dengan *"Require approval of the most recent reviewable push"*?
  3. Susun daftar checklist hardening (*aturan tata kelola defensif*) pada level repositori GitHub agar manipulasi commit pasca-approval mustahil dilakukan di masa depan!

---

### Skenario C: Monorepo Dilemma: Chaos Notifikasi dan Konflik CODEOWNERS
* **Konteks:** Perusahaan e-commerce mengkonsolidasikan 30 repositori microservices ke dalam satu arsitektur Monorepo besar di GitHub. Struktur monorepo dibagi berdasarkan folder:
  - `/services/auth/`
  - `/services/payment/`
  - `/services/catalog/`
  - `/infra/k8s/`
* **Masalah Tata Kelola:**
  - Tim DevOps membuat file `.github/CODEOWNERS` yang menunjuk tim spesifik untuk masing-masing direktori.
  - Masalah 1: Setiap kali tim `auth` membuat PR yang secara tidak sengaja memodifikasi file root (seperti `package.json`, `pnpm-lock.yaml`, atau file config global), seluruh lead dari semua layanan (auth, payment, catalog, infra) tiba-tiba ter-assign secara otomatis sebagai *required reviewer*. Hal ini memicu banjir notifikasi (*notification fatigue*) dan PR macet selama berhari-hari karena menunggu tanda tangan tim yang tidak relevan.
  - Masalah 2: CI GitHub Actions yang didefinisikan pada PR berjalan untuk seluruh unit test dari ke-30 layanan, memakan waktu 45 menit untuk setiap perubahan kecil satu baris kode di `/services/catalog/`.
* **Pertanyaan Diagnostik:**
  1. Bagaimana arsitektur aturan hierarki pada file `CODEOWNERS` dievaluasi oleh GitHub (aturan urutan penulisan *top-down* vs *specificity*)? Tuliskan contoh perbaikan file `CODEOWNERS` untuk mencegah file-file root memicu approval dari tim yang tidak diinginkan secara sembarangan!
  2. Rancang arsitektur filtering CI menggunakan GitHub Actions filter path (`paths` / `paths-ignore` atau tooling monorepo seperti Turborepo / Nx) agar PR hanya memicu test pada modul yang terdampak secara deterministik!
  3. Bagaimana mengonfigurasi status check pada GitHub Branch Protection ketika nama job CI menjadi dinamis berdasarkan path yang berubah?

---

## 4. Chapter Challenge

### Tantangan Praktis: Merancang & Mengimplementasikan Enterprise-Grade Repository Governance Framework

#### Problem Statement
Anda baru saja ditunjuk sebagai Lead Platform Engineer di sebuah startup FinTech yang sedang bersiap menghadapi audit regulasi perbankan. Repositori utama mereka, `core-ledger-service`, saat ini berada dalam kondisi kacau:
1. Tidak ada standardisasi pelaporan bug atau pengajuan fitur. Issue dibuat tanpa informasi lingkungan atau langkah reproduksi yang jelas.
2. Pengembang sering melakukan merge PR tanpa konteks bisnis, tanpa mencantumkan kaitan ke Issue, dan tanpa checklist kepatuhan (seperti pengujian keamanan dan lisensi dependensi).
3. Pengembang di luar domain finansial sering kali secara tidak sengaja mengubah skema kalkulasi akuntansi tanpa persetujuan dari tim *Core Accounting*.
4. Branch `main` tidak memiliki proteksi berbasis aturan deklaratif; siapa pun yang memiliki hak akses `Write` dapat melakukan push langsung.

Tugas Anda adalah membangun kerangka tata kelola (*governance framework*) repositori yang lengkap, terstruktur, dan siap produksi menggunakan ekosistem GitHub murni.

#### Requirements & Implementation Steps

1. **Konstruksi Directory Structure:**
   Buat pohon direktori tata kelola di bawah root `.github/`:
   ```text
   .github/
   ├── ISSUE_TEMPLATE/
   │   ├── bug_report.yml
   │   ├── feature_request.yml
   │   └── config.yml
   ├── PULL_REQUEST_TEMPLATE/
   │   └── pull_request_template.md
   └── CODEOWNERS
   ```

2. **Standardisasi Issue Forms (YAML):**
   * Buat `.github/ISSUE_TEMPLATE/bug_report.yml` yang memiliki validasi wajib (*required*):
     - Dropdown pilihan environment (`Production`, `Staging`, `Development`).
     - Input teks untuk versi aplikasi.
     - Textarea terstruktur untuk *Steps to Reproduce*, *Expected Behavior*, dan *Actual Behavior*.
     - Checkbox persetujuan bahwa pelapor telah memeriksa log sistem.
   * Buat `.github/ISSUE_TEMPLATE/config.yml` yang menonaktifkan pembuatan issue dengan format bebas (*blank issues disabled*) dan mengarahkan pengguna ke forum diskusi jika ingin bertanya.

3. **Pull Request Protocol Template:**
   * Buat `.github/PULL_REQUEST_TEMPLATE/pull_request_template.md` yang mewajibkan:
     - Referensi ke Issue ID menggunakan GitHub closing keyword (misal: `Fixes #...`).
     - Tipe perubahan (Dropdown/Checkbox: Bugfix, Feature, Breaking Change, Refactoring).
     - Rangkuman perubahan teknis (*Technical Summary*).
     - Checklist audit kepatuhan internal:
       - [ ] Unit tests ditambahkan/diperbarui.
       - [ ] Tidak ada hardcoded credentials/secrets.
       - [ ] Dokumentasi API telah disinkronkan.

4. **Strukturasi CODEOWNERS Defensif:**
   * Tulis file `.github/CODEOWNERS` dengan ketentuan tata kelola berikut:
     - Seluruh repositori secara default dimiliki oleh tim `@enterprise-org/core-maintainers`.
     - Direktori arsitektur `/docs/` dapat di-review oleh siapa saja dari `@enterprise-org/tech-writers`.
     - Direktori modul akuntansi `/src/accounting/` dan `/src/ledger/` secara mutlak hanya boleh disetujui oleh `@enterprise-org/finance-leads`.
     - Konfigurasi deployment `/deploy/` dan `.github/workflows/` wajib disetujui oleh `@enterprise-org/devops-security`.

5. **Dokumentasi Blueprint Branch Protection Rules:**
   * Tuliskan dokumen spesifikasi kebijakan proteksi branch (`BRANCH_RULES.md`) yang mendikte pengaturan eksplisit yang harus diaktifkan pada branch `main` pada menu konfigurasi GitHub (atau via API JSON GitHub Rulesets).

#### Constraints
* File Issue template **wajib** menggunakan sintaks valid GitHub Issue Forms (format YAML v2), bukan Markdown biasa.
* File `CODEOWNERS` harus memperhitungkan prioritas pembacaan aturan (*most specific path wins*) agar tidak terjadi tumpang tindih kepemilikan yang membingungkan.
* Template PR harus ramah terhadap mesin linter markdown dan tidak boleh menggunakan tag HTML kotor di luar kebutuhan visual checklist.

#### Expected Output
Anda harus menghasilkan seluruh artefak file konfigurasi (`bug_report.yml`, `config.yml`, `pull_request_template.md`, `CODEOWNERS`) secara lengkap tanpa placeholder (`...`), serta spesifikasi teknis `BRANCH_RULES.md` yang mendefinisikan postur pertahanan branch secara komprehensif.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kesiapan teknis Anda terkait ekosistem GitHub, Pull Requests, Issues, dan Project Governance sebelum melanjutkan ke bab integrasi otomatisasi (GitHub Actions & CI/CD).

### Saya harus memahami:
- [ ] Perbedaan fundamental antara model branching Git murni dengan abstraksi Pull Request pada platform forge.
- [ ] Dampak matematis/topologis dari tiga jenis merge strategy (Merge Commit, Squash, Rebase) terhadap linearitas riwayat Git dan SHA-1 integrity.
- [ ] Arsitektur internal GitHub ref namespace (`refs/pull/<id>/head` dan `refs/pull/<id>/merge`).
- [ ] Cara kerja parsing otomatis GitHub closing keywords (`Fixes`, `Closes`, `Resolves`) dan event lifecycle yang memicu penutupan issue.
- [ ] Tata cara hierarki evaluasi aturan file `CODEOWNERS` (aturan paling bawah yang lebih spesifik menimpa aturan di atasnya).
- [ ] Peran Branch Protection Rules dan GitHub Repository Rulesets dalam menegakkan kepatuhan industri (SOC 2, ISO 27001).
- [ ] Keterbatasan teknis web-based conflict resolution pada GitHub UI dan kapan penyelesaian manual di lokal bersifat mutlak.
- [ ] Batasan keamanan token `GITHUB_TOKEN` pada konteks forked pull requests untuk mitigasi serangan supply chain.

### Saya tidak perlu menghafal:
- [ ] Seluruh variasi kata kerja closing keywords bahasa Inggris yang didukung GitHub (cukup pahami pola dasarnya seperti `Fixes #ID` atau `Closes #ID`).
- [ ] Sintaks JSON payload API mentah dari GitHub Webhook events untuk Pull Requests (cukup pahami konteks lifecycle-nya: `opened`, `synchronize`, `closed`).
- [ ] Setiap parameter konfigurasi CSS styling untuk tampilan visualisasi GitHub Projects board.

### Saya harus bisa melakukan:
- [ ] Menulis file validasi input issue enterprise menggunakan GitHub Issue Forms berbasis skema YAML.
- [ ] Menyusun template PR profesional yang menuntut akuntabilitas teknis dan checklist kepatuhan audit.
- [ ] Mengonfigurasi file `.github/CODEOWNERS` dengan sintaks path matching dan penetapan tim yang tepat tanpa menimbulkan *deadlock review*.
- [ ] Melakukan troubleshooting konflik PR rumit secara lokal menggunakan Git CLI melalui *fetch PR ref* dan rebase/merge manual.
- [ ] Mengonfigurasi Branch Protection Rules yang mencakup: branch up-to-date enforcement, minimum approvals, dismiss stale reviews, dan code owners validation.
- [ ] Melakukan integrasi penutupan issue otomatis yang terhubung rapi antara deskripsi PR dengan issue tracking board.