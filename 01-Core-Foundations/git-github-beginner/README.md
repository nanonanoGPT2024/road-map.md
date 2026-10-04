# Kurikulum Komprehensif: Git & GitHub untuk Pemula (Enterprise-Grade)

Selamat datang di silabus resmi **Git & GitHub Beginner**. Kurikulum ini dirancang untuk mengubah pemahaman instingtif/coba-coba (*trial-and-error*) menjadi penguasaan mekanistik berbasis model mental direktori terdistribusi (*Directed Acyclic Graph* / DAG). Anda tidak hanya diajarkan menghafal sintaksis CLI, melainkan memahami bagaimana Git mengelola *content-addressable storage*, memanipulasi pointer referensi, serta bagaimana GitHub mengorkestrasi kolaborasi multi-kontributor skala enterprise.

---

## 1. Ringkasan Kursus & Pola Pikir (Mindset)

Git bukan sekadar alat pencadangan berkas (*backup tool*), melainkan sistem kendali versi terdistribusi (*Distributed Version Control System* - DVCS) yang memodelkan riwayat proyek sebagai graf asiklik terarah (DAG) dari *immutable snapshots*. GitHub bertindak sebagai lapisan kolaborasi, tata kelola (*governance*), dan otomatisasi di atas fondasi Git tersebut.

### Paradigma yang Ditanamkan:
1. **State-Driven, Bukan Delta-Driven**: Git menyimpan *snapshot* kondisi penuh dari berkas proyek melalui *tree objects* dan *blob objects*, bukan rekaman selisih baris (diff) antar versi.
2. **Kebenaran Mutlak Lokal (*Local First*)**: Hampir semua operasi Git dieksekusi secara lokal tanpa latensi jaringan. Server jarak jauh (*remote*) hanyalah simpul replikasi lain dalam topologi terdistribusi.
3. **Integritas Kriptografis SHA-1/SHA-256**: Riwayat komit bersifat *tamper-proof*. Mengubah satu karakter di masa lalu akan mengubah seluruh hash anak cucunya dalam graf.
4. **Disiplin Kebersihan Riwayat (*History Hygiene*)**: Komit adalah unit dokumentasi logis. Kita menerapkan prinsip *Atomic Commits* dan konvensi pesan komit berbasis standar industri (*Conventional Commits*).

---

## 2. Peta Jalan Pembelajaran (Learning Roadmap)

```text
git-github-beginner/
│
├── [Bab 01] Anatomi & Filosofi Version Control System (VCS)
│   ├── Modul 01: Arsitektur Distributed VCS vs Centralized VCS & Mental Model Git
│   └── Modul 02: Tiga State Git: Working Directory, Staging Area, dan Repository
│
├── [Bab 02] Inisialisasi, Konfigurasi, & Siklus Hidup Objek Git
│   ├── Modul 01: Global/Local Configuration, SSH Keys, & Otentikasi GPG
│   └── Modul 02: Plumbing vs Porcelain: Blob, Tree, Commit, dan Referensi HEAD
│
├── [Bab 03] Penjelajahan Riwayat & Manajemen Perubahan (Commits & Diffs)
│   ├── Modul 01: Atomic Commits, Conventional Commits, dan Hygiene Log Komit
│   └── Modul 02: Investigasi Perubahan Menggunakan git diff, git log, dan git blame
│
├── [Bab 04] Percabangan Terisolasi (Branching Strategies & Mechanics)
│   ├── Modul 01: Mekanisme Pointer HEAD dan Pembuatan Cabang Terisolasi
│   └── Modul 02: Pola Percabangan Industri: Git Flow, GitHub Flow, & Trunk-Based
│
├── [Bab 05] Integrasi Kode: Fast-Forward, 3-Way Merge, dan Rebase Dasar
│   ├── Modul 01: git merge (Fast-Forward vs Non-Fast-Forward / --no-ff)
│   └── Modul 02: git rebase Linier vs Merge Commits: Kapan Memilih Salah Satunya
│
├── [Bab 06] Resolusi Konflik (Merge Conflict Resolution & State Recovery)
│   ├── Modul 01: Anatomi Merge Conflict Markers dan Taktik Resolusi Deterministik
│   └── Modul 02: Manajemen State Sementara: git stash, git clean, dan Cherry-Pick
│
├── [Bab 07] Kolaborasi Jarak Jauh (Remote Repositories & Protocol Plumbing)
│   ├── Modul 01: Remote Tracking Branches: Origin, Upstream, fetch, dan pull
│   └── Modul 02: Sinkronisasi Remote: Push Flags, Upstream Tracking, & Safety Guards
│
├── [Bab 08] Ekosistem GitHub: Pull Requests, Issues, & Project Governance
│   ├── Modul 01: Issue Tracking, Milestones, dan GitHub Projects Boards
│   └── Modul 02: Anatomi Pull Request Enterprise: Review Loops, Diffs, & CODEOWNERS
│
├── [Bab 09] Tata Kelola Kolaborasi & Keamanan Repositori (Governance & Security)
│   ├── Modul 01: Branch Protection Rules, Status Checks, dan Signed Commits Enforcement
│   └── Modul 02: Pertahanan Repositori: .gitignore Mutlak, Secret Scanning, & Git Hooks
│
└── [Bab 10] Otomasi Dasar CI/CD Menggunakan GitHub Actions
    ├── Modul 01: Arsitektur Workflow: Events, Jobs, Steps, Runners, dan Secrets
    └── Modul 02: Penerapan Linter, Automated Testing, dan Auto-Validation pada PR
```

---

## 3. Navigasi Detail Modul

### [Bab 01: Anatomi & Filosofi Version Control System (VCS)](./bab-01-fundamental/README.md)
*   [Modul 01: Arsitektur Distributed VCS vs Centralized VCS & Mental Model Git](./bab-01-fundamental/modul-01.md)
    *   Komparasi arsitektural: SVN/Perforce vs Git.
    *   Konsep *immutable Directed Acyclic Graph (DAG)*.
    *   Integritas data berbasis *hashing* kriptografis.
*   [Modul 02: Tiga State Git: Working Directory, Staging Area, dan Repository](./bab-01-fundamental/modul-02.md)
    *   Transisi siklus hidup berkas: *Untracked*, *Tracked*, *Staged*, *Committed*.
    *   Peran krusial *Index/Staging Area* sebagai buffer kurasi perubahan.
    *   Eksplorasi direktori internal `.git` secara mekanistik.

### [Bab 02: Inisialisasi, Konfigurasi, & Siklus Hidup Objek Git](./bab-02-konfigurasi-objek/README.md)
*   [Modul 01: Global/Local Configuration, SSH Keys, & Otentikasi GPG](./bab-02-konfigurasi-objek/modul-01.md)
    *   Hirarki konfigurasi: `system` vs `global` vs `local` vs `worktree`.
    *   Setup kredensial aman: SSH Ed25519 dan verifikasi komit berbasis GPG.
    *   Normalisasi *end-of-line* (`core.autocrlf`) lintas platform OS.
*   [Modul 02: Plumbing vs Porcelain: Blob, Tree, Commit, dan Referensi HEAD](./bab-02-konfigurasi-objek/modul-02.md)
    *   Pembedahan internal objek Git via `git cat-file` dan `git hash-object`.
    *   Dekomposisi struktur *commit object* dan keterkaitannya dengan *tree object*.
    *   Mekanisme referensi penunjuk dinamis: file `.git/HEAD`.

### [Bab 03: Penjelajahan Riwayat & Manajemen Perubahan (Commits & Diffs)](./bab-03-riwayat-perubahan/README.md)
*   [Modul 01: Atomic Commits, Conventional Commits, dan Hygiene Log Komit](./bab-03-riwayat-perubahan/modul-01.md)
    *   Standarisasi struktur pesan: Conventional Commits (`feat`, `fix`, `chore`, `refactor`).
    *   Strategi *Atomic Commits*: satu tanggung jawab tunggal per komit.
    *   Teknik pementasan parsial: `git add -p` (*patch staging*).
*   [Modul 02: Investigasi Perubahan Menggunakan git diff, git log, dan git blame](./bab-03-riwayat-perubahan/modul-02.md)
    *   Analisis perbandingan granular: `git diff`, `git diff --staged`, dan `git diff branchA..branchB`.
    *   Teknik inspeksi riwayat tingkat lanjut: format custom `git log --graph --oneline --decorate`.
    *   Audit forensik baris kode menggunakan `git blame` dan `git log -S`.

### [Bab 04: Percabangan Terisolasi (Branching Strategies & Mechanics)](./bab-04-percabangan/README.md)
*   [Modul 01: Mekanisme Pointer HEAD dan Pembuatan Cabang Terisolasi](./bab-04-percabangan/modul-01.md)
    *   Definisi cabang (*branch*) sebagai *lightweight movable pointer*.
    *   Operasi navigasi: perbandingan mendalam `git checkout` vs `git switch`.
    *   Detached HEAD State: diagnosis penyebab, mitigasi risiko, dan restorasi referensi.
*   [Modul 02: Pola Percabangan Industri: Git Flow, GitHub Flow, & Trunk-Based](./bab-04-percabangan/modul-02.md)
    *   Studi komparasi Git Flow (kompleks) vs GitHub Flow (agil) vs Trunk-Based Development (CI/CD murni).
    *   Penetapan taksonomi nama cabang di lingkungan enterprise (`feature/*`, `bugfix/*`, `release/*`).
    *   Manajemen *branch lifecycle*: eliminasi cabang basi (*stale branches*).

### [Bab 05: Integrasi Kode: Fast-Forward, 3-Way Merge, dan Rebase Dasar](./bab-05-integrasi-kode/README.md)
*   [Modul 01: git merge (Fast-Forward vs Non-Fast-Forward / --no-ff)](./bab-05-integrasi-kode/modul-01.md)
    *   Mekanisme Fast-Forward Merge: kondisi kelayakan dan pergerakan pointer.
    *   Mekanisme 3-Way Merge: perhitungan Common Ancestor (*merge base*), Ours, dan Theirs.
    *   Implikasi audit flag `--no-ff` vs `--squash`.
*   [Modul 02: git rebase Linier vs Merge Commits: Kapan Memilih Salah Satunya](./bab-05-integrasi-kode/modul-02.md)
    *   Mekanisme `git rebase`: pencabutan dan penanaman ulang komit (*replay* komit).
    *   Perbandingan riwayat linier vs riwayat topologis riil.
    *   *The Golden Rule of Rebasing*: pantangan rebase pada cabang publik/bersama.

### [Bab 06: Resolusi Konflik (Merge Conflict Resolution & State Recovery)](./bab-06-resolusi-konflik/README.md)
*   [Modul 01: Anatomi Merge Conflict Markers dan Taktik Resolusi Deterministik](./bab-06-resolusi-konflik/modul-01.md)
    *   Dekomposisi penanda konflik: `<<<<<<<`, `=======`, dan `>>>>>>>`.
    *   Konfigurasi flag `merge.conflictStyle diff3` untuk konteks *base common ancestor*.
    *   Verifikasi integritas kode pasca-resolusi konflik sebelum finalisasi komit.
*   [Modul 02: Manajemen State Sementara: git stash, git clean, dan Cherry-Pick](./bab-06-resolusi-konflik/modul-02.md)
    *   Isolasi kerja darurat menggunakan `git stash push -m`, `pop`, `apply`, dan `drop`.
    *   Pembersihan file tak terlacak yang aman via `git clean -nd` dan `git clean -fd`.
    *   Adopsi perubahan selektif antar cabang menggunakan `git cherry-pick`.

### [Bab 07: Kolaborasi Jarak Jauh (Remote Repositories & Protocol Plumbing)](./bab-07-kolaborasi-remote/README.md)
*   [Modul 01: Remote Tracking Branches: Origin, Upstream, fetch, dan pull](./bab-07-kolaborasi-remote/modul-01.md)
    *   Topologi multi-remote: konvensi penamaan `origin` vs `upstream` (Forking Model).
    *   Operasi sinkronisasi non-destruktif: `git fetch` dan inspeksi `origin/main`.
    *   Operasi gabungan: `git pull` (`git fetch` + `git merge`) vs `git pull --rebase`.
*   [Modul 02: Sinkronisasi Remote: Push Flags, Upstream Tracking, & Safety Guards](./bab-07-kolaborasi-remote/modul-02.md)
    *   Konfigurasi upstream binding eksplisit menggunakan `git push -u origin <branch>`.
    *   Bahaya `git push --force` destruktif vs mitigasi aman `git push --force-with-lease`.
    *   Manajemen tag lokal dan remote: pembagian *lightweight* vs *annotated release tags*.

### [Bab 08: Ekosistem GitHub: Pull Requests, Issues, & Project Governance](./bab-08-ekosistem-github/README.md)
*   [Modul 01: Issue Tracking, Milestones, dan GitHub Projects Boards](./bab-08-ekosistem-github/modul-01.md)
    *   Pemanfaatan Issue Forms berbasis Markdown/YAML untuk bug report dan feature request.
    *   Orkestrasi Kanban Board otomatisasi event-driven via GitHub Projects.
    *   Penghubungan isu secara deklaratif melalui pesan komit (*Closing keywords*).
*   [Modul 02: Anatomi Pull Request Enterprise: Review Loops, Diffs, & CODEOWNERS](./bab-08-ekosistem-github/modul-02.md)
    *   Standarisasi dokumen: `.github/pull_request_template.md`.
    *   Siklus peninjauan kode: Inline Commenting, Sugested Changes, dan Resolve Threads.
    *   Implementasi aturan alokasi peninjau otomatis menggunakan file `.github/CODEOWNERS`.

### [Bab 09: Tata Kelola Kolaborasi & Keamanan Repositori (Governance & Security)](./bab-09-tata-kelola-keamanan/README.md)
*   [Modul 01: Branch Protection Rules, Status Checks, dan Signed Commits Enforcement](./bab-09-tata-kelola-keamanan/modul-01.md)
    *   Proteksi cabang `main`: minimal persetujuan review, penolakan force push, & linear history.
    *   Pemberlakuan *Required Status Checks* sebelum tombol *Merge* aktif.
    *   Verifikasi identitas kontributor: penolakan komit tanpa tanda tangan (*Require signed commits*).
*   [Modul 02: Pertahanan Repositori: .gitignore Mutlak, Secret Scanning, & Git Hooks](./bab-09-tata-kelola-keamanan/modul-02.md)
    *   Penyusunan pola `.gitignore` defensif (environment files, binaries, build caches).
    *   Penanganan insiden kebocoran kredensial dan aktivasi *GitHub Push Protection / Secret Scanning*.
    *   Proteksi sisi klien: integrasi pre-commit hooks untuk validasi format dan kredensial.

### [Bab 10: Otomasi Dasar CI/CD Menggunakan GitHub Actions](./bab-10-otomasi-github-actions/README.md)
*   [Modul 01: Arsitektur Workflow: Events, Jobs, Steps, Runners, dan Secrets](./bab-10-otomasi-github-actions/modul-01.md)
    *   Dekomposisi sintaksis YAML workflow di direktori `.github/workflows/`.
    *   Event trigger selektif: filtrasi perubahan berbasis path dan event `pull_request` target `main`.
    *   Manajemen environment variables dan GitHub Encrypted Secrets secara aman.
*   [Modul 02: Penerapan Linter, Automated Testing, dan Auto-Validation pada PR](./bab-10-otomasi-github-actions/modul-02.md)
    *   Pembangunan workflow integrasi berkelanjutan: instalasi runtime, caching dependency, linter, test run.
    *   Mekanisme pemblokiran merge otomatis jika unit test atau linter mengalami kegagalan.
    *   Pemberian sinyal status check ke dalam Pull Request.

---

## 4. Spesifikasi Capstone Project Enterprise

Sebagai syarat kelulusan kursus, siswa diwajibkan menyelesaikan **Simulasi Kontributor Open-Source Skala Enterprise**. Proyek ini mereplikasi skenario dunia nyata di mana peserta harus berkontribusi pada repositori inti (*upstream*) yang memiliki proteksi ketat dan jalur integrasi terotomasi.

### Nama Proyek:
`Core-Nexus: Enterprise Microservices Platform Simulator`

### Ruang Lingkup & Skenario:
Siswa berperan sebagai *Software Engineer* baru yang bertugas mengimplementasikan modul autentikasi baru, menyelesaikan insiden *merge conflict* dengan fitur paralel dari tim lain, dan mematuhi seluruh *quality gate* otomatis.

### Kriteria Kelulusan Teknis (Acceptance Criteria):

```text
[Upstream: main]  <--- Branch Protection Active (Require 1 Approval + Status Check Pass)
       │
       ├── PR #1: feat(auth): implement token generator (Dikerjakan Siswa)
       │     ├── Branch: feature/auth-token-engine
       │     ├── Conventional Commits (Min. 3 Atomic Commits terverifikasi GPG)
       │     ├── Branch Protection Compliant (.github/CODEOWNERS terpenuhi)
       │     └── Passing CI Pipeline (.github/workflows/ci.yml)
       │
       └── PR #2: refactor(core): update base config interface (Di-merge mendahului Siswa)
             └── Mengakibatkan intentional Merge Conflict pada PR #1
```

1. **Topologi Repositori & Forking**:
   * Melakukan *fork* dari repositori pusat ke akun personal.
   * Melakukan kloning lokal dan mengonfigurasi dua remote: `origin` (personal fork) dan `upstream` (repositori pusat).

2. **Pengembangan Fitur & Branching**:
   * Membuat cabang bernama `feature/auth-token-engine` dari cabang `upstream/main` terbaru.
   * Menghasilkan minimal 3 komit terpisah (*atomic*) yang mematuhi standar *Conventional Commits*:
     * `feat(auth): define user token interface`
     * `test(auth): add unit test coverage for token generation`
     * `feat(auth): complete token signing implementation`
   * Seluruh komit wajib terverifikasi kriptografis (*Verified badge* via GPG/SSH signing).

3. **Infrastruktur Tata Kelola Repositori**:
   * Memastikan repositori memiliki berkas proteksi:
     * `.gitignore` komprehensif (memblokir file `.env`, dependensi, dan cache).
     * `.github/pull_request_template.md` yang memuat checklist peninjauan kode.
     * `.github/CODEOWNERS` yang menunjuk tim spesifik untuk path fitur.

4. **Skenario Resolusi Konflik Bersyarat**:
   * Tim instruktur/simulasi akan menginjeksikan komit ke `upstream/main` yang mengubah baris kode yang sama dengan branch siswa.
   * Siswa wajib:
     1. Menarik perubahan terbaru via `git fetch upstream`.
     2. Melakukan sinkronisasi menggunakan metode `git rebase upstream/main`.
     3. Menyelesaikan konflik secara deterministik (mempertahankan integritas kedua fungsi).
     4. Menuntaskan proses rebase tanpa membuat komit merge baru.
     5. Melakukan pembaruan ke remote fork via `git push origin feature/auth-token-engine --force-with-lease`.

5. **Integrasi CI/CD & Validasi Pull Request**:
   * Workflow GitHub Actions `.github/workflows/verify-pr.yml` harus terpicu secara otomatis.
   * Pipeline harus mengeksekusi:
     * Linter checking (standar sintaksis kode).
     * Unit testing pipeline (memastikan semua tes lulus 100%).
     * Format komit linter (memvalidasi format Conventional Commits).
   * Pull Request dinyatakan sah dan siap dimerge hanya jika berstatus **All checks have passed** dan seluruh thread diskusi peninjauan telah ditandai **Resolved**.

---
*Materi silabus ini dipelihara secara ketat di bawah standar rekayasa kurikulum teknis enterprise. Dilarang mengubah alur instruksi tanpa pengujian dependensi antar bab.*