## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `GIT-CORE-0801`
* **Jalur Kurikulum**: `git-github-beginner`
* **Kategori**: `01-Core-Foundations`
* **Bab**: `08 — Ekosistem GitHub: Pull Requests, Issues, & Project Governance`
* **Modul**: `01 — Tata Kelola Repositori, Alur Kerja Pull Request, dan Orkestrasi Isu`
* **Tingkat Kesulitan**: Pemula Tingkat Lanjut (*Advanced Beginner*) / Menengah (*Intermediate*)
* **Prasyarat**:
  * Pemahaman Git Branching dasar (`git branch`, `git checkout`, `git switch`).
  * Pemahaman Git Remote dasar (`git push`, `git fetch`, `git pull`, `git remote`).
  * Akun GitHub aktif dan konfigurasi SSH Key / Personal Access Token (PAT).
* **Estimasi Waktu Belajar**: 120 Menit (Teori: 45 Menit, Hands-on Lab: 75 Menit)
* **Target Pembaca**: Perekayasa Perangkat Lunak (*Software Engineers*), Pengembang Web, DevOps Pemula, dan Administrator Repositori yang ingin menguasai kolaborasi tim terstruktur di GitHub.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis Anatomi Pull Request (PR)**: Menjelaskan siklus hidup PR dari pembuatan *branch*, pemindaian CI/CD, tinjauan rekan (*peer review*), resolusi konflik, hingga strategi penggabungan (*merge strategy*).
2. **Mengonfigurasi Tata Kelola Repositori Terstruktur**: Membangun *Issue Templates*, *Pull Request Templates*, dan fail `CODEOWNERS` dalam direktori `.github/` untuk standarisasi komunikasi tim.
3. **Menerapkan Aturan Proteksi Branch (*Branch Protection Rules / Rulesets*)**: Mengamankan cabang utama (`main`/`master`) dari *direct push*, *force push*, dan memastikan lolosnya tinjauan minimum serta *status check*.
4. **Mengorkestrasi Pelacakan Proyek**: Mengintegrasikan GitHub Issues, Labels, Milestones, dan GitHub Projects (Kanban) untuk visibilitas progres pengembangan perangkat lunak secara transparan.
5. **Mengeksekusi Strategi Penggabungan PR**: Memilih dan mengeksekusi secara tepat antara *Create a Merge Commit*, *Squash and Merge*, serta *Rebase and Merge* sesuai kebijakan rekam jejak Git (*Git history hygiene*).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
                               +---------------------------------------------+
                               |     GitHub Collaboration & Governance       |
                               +---------------------------------------------+
                                                      |
            +-----------------------------------------+-----------------------------------------+
            |                                         |                                         |
            v                                         v                                         v
+-----------------------+                 +-----------------------+                 +-----------------------+
|  Problem & Task Mgmt  |                 | Code Review Lifecycle |                 | Repository Governance |
+-----------------------+                 +-----------------------+                 +-----------------------+
| - Issues              |                 | - Pull Requests       |                 | - Branch Protections  |
| - Issue Templates     |                 | - PR Templates        |                 | - CODEOWNERS          |
| - Labels & Milestones |                 | - Peer Reviews        |                 | - Merge Strategies    |
| - GitHub Projects     |                 | - Status Checks (CI)  |                 | - Rulesets            |
+-----------------------+                 +-----------------------+                 +-----------------------+
            |                                         |                                         |
            +-----------------------------------------+-----------------------------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  | Production-Ready Master/Main Branch   |
                                  +---------------------------------------+
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Pada skala individual, Git cukup digunakan sebagai *tool undo* canggih dan sarana pencadangan kode (*backup*). Namun, ketika bertransisi ke lingkungan rekayasa perangkat lunak tim atau proyek sumber terbuka (*open source*), Git lokal tidak memiliki mekanisme intrinsik untuk:
* Melarang seorang pengembang menimpa cabang produksi secara sengaja maupun tidak sengaja.
* Memastikan bahwa setiap baris kode baru telah diperiksa oleh perekayasa senior (*senior engineer*).
* Menghubungkan perubahan kode dengan tiket pekerjaan atau laporan *bug* yang mendasarinya.

Ekosistem GitHub mengatasi masalah ini dengan menyediakan lapisan kolaborasi (*collaboration layer*) di atas Git murni. Tanpa penerapan sistem tata kelola seperti *Pull Requests*, *Issue Templates*, dan *Branch Protection Rules*, tim akan menghadapi:
1. **Regresi Kode (*Code Regression*)**: Fitur yang belum teruji secara otomatis masuk ke cabang produksi.
2. **Riwayat Git yang Kacau (*Polluted Git History*)**: Pesan *commit* ambigu (`fix`, `test1`, `asdf`) yang menyulitkan proses penelusuran masalah (*bisecting*).
3. **Bottleneck Tinjauan**: Ketidakjelasan mengenai siapa yang bertanggung jawab meninjau modul tertentu.

Menguasai ekosistem ini adalah pembeda mendasar antara sekadar "bisa mengetik perintah Git" dengan "mampu bekerja secara profesional dalam tim rekayasa perangkat lunak modern".

---

## SEKSI 05 — APA ITU (WHAT)

### 1. GitHub Issues
*GitHub Issues* adalah sistem pelacakan masalah (*issue tracking system*) terintegrasi yang berfungsi mencatat *bug*, permintaan fitur baru (*feature requests*), optimasi performa, dan diskusi teknis. Isu bukan bagian dari protokol Git murni, melainkan lapisan metadata yang dikelola oleh GitHub.

### 2. Pull Request (PR)
*Pull Request* adalah mekanisme pemberitahuan bahwa seorang pengembang telah menyelesaikan serangkaian perubahan pada suatu cabang (*feature branch*) di repositori lokal/garpu (*fork*), dan meminta administrator repositori asal untuk meninjau (*review*) serta menggabungkan (*merge*) perubahan tersebut ke cabang target (biasanya `main` atau `develop`). PR menyediakan ruang diskusi baris-per-baris (*inline comments*), pengujian otomatis (*CI status checks*), dan analisis *diff*.

### 3. File Tata Kelola (.github/ Directory)
GitHub mengenali fail-fail konfigurasi khusus yang diletakkan pada direktori `.github/` di akar repositori:
* **`PULL_REQUEST_TEMPLATE.md`**: Templat teks bawaan yang muncul ketika pengembang membuat PR baru, memaksa pengembang mengisi konteks, pengujian yang telah dilakukan, dan tiket terkait.
* **`ISSUE_TEMPLATE/`**: Direktori berisi formulir terstruktur (Markdown atau YAML) untuk memandu pengguna melaporkan galat (*bug*) atau fitur baru.
* **`CODEOWNERS`**: Fail deklaratif yang mendefinisikan individu atau tim yang secara otomatis ditunjuk sebagai peninjau wajib (*required reviewer*) jika ada PR yang memodifikasi berkas dalam pola jalur (*path pattern*) tertentu.

### 4. Branch Protection Rules & Rulesets
Fitur keamanan repositori tingkat enterprise yang membatasi hak akses cabang. Aturan ini dapat mengunci cabang sehingga tidak bisa dihapus, menolak eksekusi `git push --force`, mewajibkan PR sebelum digabungkan, dan mewajibkan persetujuan (*approval*) dari satu atau lebih peninjau serta lolosnya tes CI/CD (*Continuous Integration*).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### Alur Kerja Kolaboratif Standar (GitHub Flow Terkelola)

```text
[ Issue Dibuat ] 
       │
       ▼
[ Branch Dibuat: feat/login-oauth ] ─── (Coding & Commit Lokal)
       │
       ▼
[ Push ke Remote Branch ]
       │
       ▼
[ Pembuatan Pull Request ] ◄── (Auto-assigned via CODEOWNERS)
       │
       ├───► [ CI/CD Runner: Run Unit Tests & Linter ] (Status Checks)
       │
       ├───► [ Peer Reviewer: Memberikan Review & Komentar ]
       │            │
       │            ├── If Changes Requested ──► [ Push Commit Tambahan ] ──┐
       │            │                                                       │
       │            └── If Approved ────────────────────────────────────────┤
       ▼                                                                    │
[ Branch Protection: Syarat Terpenuhi ] ◄───────────────────────────────────┘
       │
       ▼
[ Merge Pull Request ] (Squash / Rebase / Merge Commit)
       │
       ▼
[ Cabang Fitur Dihapus & Isu Otomatis Tertutup via Keywords ]
```

### Kata Kunci Penutupan Isu Otomatis (*Closing Keywords*)
GitHub memindai deskripsi PR dan pesan *commit* pada cabang default untuk mencari sintaks penutupan isu otomatis:
* `close`, `closes`, `closed`
* `fix`, `fixes`, `fixed`
* `resolve`, `resolves`, `resolved`

Contoh: `Fixes #42` atau `Closes #108` pada deskripsi PR akan menutup Isu nomor 42 atau 108 secara otomatis ketika PR tersebut di-*merge* ke cabang utama.

### Strategi Penggabungan (*Merge Strategies*)
GitHub menyediakan 3 mekanisme penggabungan PR:

1. **Merge Commit (`--no-ff`)**:
   * Menggabungkan cabang fitur ke cabang target dengan membuat satu *merge commit* khusus yang memiliki dua induk (*two parents*).
   * **Karakteristik**: Riwayat cabang fitur dipertahankan utuh. Topologi visual bercabang.
2. **Squash and Merge**:
   * Memadatkan seluruh *commit* dari cabang fitur menjadi tepat **satu commit baru** pada cabang target.
   * **Karakteristik**: Riwayat cabang target sangat bersih dan linear. Riwayat granular pengerjaan fitur dihilangkan.
3. **Rebase and Merge**:
   * Memindahkan *commit-commit* dari cabang fitur satu per satu ke ujung cabang target tanpa membuat *merge commit*.
   * **Karakteristik**: Riwayat linear sempurna, identitas commit individual dipertahankan, namun SHA commit berubah.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Siklus Hidup Review Pull Request dan Validasi Cabang

```text
DEVELOPER                    GITHUB REMOTE (PR #15)                 CI/CD & REVIEWER
    │                                  │                                    │
    │── 1. git push origin feat/api ──>│                                    │
    │                                  │                                    │
    │── 2. Buka PR via UI/CLI ────────>│                                    │
    │      (Template PR terisi)        │── 3. Triggers Webhook ────────────>│
    │                                  │                                    │ (Menjalankan
    │                                  │                                    │  Unit Test &
    │                                  │                                    │  Linter)
    │                                  │<─ 4. Report Checks (PASS/FAIL) ────│
    │                                  │                                    │
    │                                  │── 5. Notifikasi Review ───────────>│
    │                                  │      (via CODEOWNERS)              │
    │                                  │                                    │
    │                                  │<─ 6. Review: "Changes Requested" ──│
    │                                  │      (Inline Code Comments)        │
    │<─ 7. Menerima Feedback ──────────│                                    │
    │                                  │                                    │
    │── 8. git push (Fixes) ──────────>│                                    │
    │                                  │── 9. Triggers Re-Test ────────────>│
    │                                  │<─ 10. Report Checks (PASS) ────────│
    │                                  │<─ 11. Review: "Approved" ──────────│
    │                                  │                                    │
    │                             [ VALIDASI ]                              │
    │                     - Required Approvals >= 1? [YES]                  │
    │                     - Status Checks PASS?      [YES]                  │
    │                     - Up to date with main?    [YES]                  │
    │                                  │                                    │
    │── 12. Execute Merge ────────────>│                                    │
    │       (Squash / Rebase)          │── 13. Close Issue linked (Auto)    │
    │                                  │── 14. Delete feat/api branch       │
    ▼                                  ▼                                    ▼
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Skenario: Anda ditugaskan memperbaiki galat ketik (*typo*) pada fail dokumentasi repositori proyek.

### Langkah 1: Eksplorasi Isu
Buka repositori di GitHub, temukan isu:
`Issue #12: Typo pada README.md bagian instalasi`.

### Langkah 2: Buat Branch Lokal Khusus
```bash
# Pastikan branch main lokal sinkron dengan upstream remote
git checkout main
git pull origin main

# Buat dan pindah ke branch baru dengan penamaan semantik
git checkout -b fix/readme-typo
```

### Langkah 3: Lakukan Perubahan dan Commit
Sunting `README.md`, lalu simpan.
```bash
git add README.md
git commit -m "docs: perbaiki kesalahan ketik instalasi pada README"
```

### Langkah 4: Dorong (*Push*) ke Repositori Remote
```bash
git push -u origin fix/readme-typo
```

### Langkah 5: Buka Pull Request Melalui Web GitHub atau GitHub CLI
Jika menggunakan GitHub CLI (`gh`):
```bash
gh pr create --title "docs: perbaiki typo pada README.md" \
             --body "Mengoreksi kesalahan penulisan instruksi instalasi dependencies. Closes #12." \
             --base main
```
Atau buka antarmuka GitHub Web, klik tombol kuning **"Compare & pull request"**, isi deskripsi dengan menyertakan `Closes #12`, kemudian klik **Create pull request**.

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut adalah penerapan arsitektur tata kelola enterprise skala menengah-besar menggunakan konfigurasi kode deklaratif di dalam repositori.

### Struktur Repositori
```text
my-enterprise-app/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.yml
│   │   └── feature_request.yml
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── CODEOWNERS
├── src/
│   ├── auth/
│   └── payment/
└── README.md
```

### 1. Konfigurasi Issue Template Form Modern (`.github/ISSUE_TEMPLATE/bug_report.yml`)
Bentuk YAML Schema Form lebih unggul daripada Markdown murni karena memvalidasi masukan pengguna secara terstruktur:

```yaml
name: 🐛 Laporan Bug (Bug Report)
description: Laporkan masalah atau kegagalan sistem agar tim dapat mereproduksinya.
title: "[BUG]: "
labels: ["triage", "bug"]
body:
  - type: markdown
    attributes:
      value: |
        Terima kasih telah melaporkan bug. Harap berikan data yang akurat.
  - type: input
    id: environment
    attributes:
      label: Versi Aplikasi / Lingkungan (Environment)
      description: Sebutkan versi Node.js/Go/Python dan sistem operasi yang digunakan.
      placeholder: "Node.js v20.10.0, Ubuntu 22.04 LTS"
    validations:
      required: true
  - type: textarea
    id: reproduction_steps
    attributes:
      label: Langkah-Langkah Mereproduksi Masalah
      description: Jelaskan runtutan langkah terperinci hingga bug terjadi.
      placeholder: |
        1. Jalankan endpoint POST /api/v1/auth/login
        2. Kirim payload JSON tanpa parameter password
        3. Server mengembalikan status 500 alih-alih 400 Bad Request
    validations:
      required: true
  - type: textarea
    id: expected_behavior
    attributes:
      label: Perilaku yang Diharapkan
      description: Apa yang seharusnya terjadi jika sistem normal?
    validations:
      required: true
```

### 2. Standarisasi PR Template (`.github/PULL_REQUEST_TEMPLATE.md`)

```markdown
## Deskripsi Perubahan
<!-- Rangkum perubahan teknis yang Anda lakukan. Tuliskan konteks dan latar belakang. -->

## Jenis Perubahan
- [ ] 🐛 Perbaikan Bug (Non-breaking change yang menyelesaikan masalah)
- [ ] ✨ Fitur Baru (Non-breaking change yang menambah fungsionalitas)
- [ ] 💥 Perubahan Struktural / Breaking Change (Fitur/perbaikan yang mengubah API lama)
- [ ] 📝 Pembaruan Dokumentasi

## Isu Terkait (Linked Issues)
<!-- Gunakan sintaks otomatis: Fixes #NomorIsu atau Closes #NomorIsu -->
Fixes #

## Daftar Periksa Pengujian (Testing Checklist)
- [ ] Seluruh unit test lokal lolos (`npm test` atau `pytest`)
- [ ] Linting tidak menghasilkan peringatan (`npm run lint`)
- [ ] Telah ditambahkan integration test untuk skenario galat
- [ ] Tidak ada berkas rahasia/kredensial (`.env`) yang ter-commit

## Tangkapan Layar / Log Eksekusi (Opsional)
<!-- Sisipkan bukti visual jika perubahan mempengaruhi UI/UX atau log respon API -->
```

### 3. Konfigurasi Kepemilikan Kode (`.github/CODEOWNERS`)

```text
# Sintaks: [Pola Jalur] [@AkunGitHub atau @Organisasi/NamaTim]

# Secara default, tim Core Platform memiliki akses ke seluruh isi repositori
*                   @my-org/core-platform-leads

# Modul otentikasi wajib di-review oleh tim Keamanan
/src/auth/          @my-org/security-team @alice-infosec

# Modul transaksi dan pembayaran wajib diverifikasi tim FinTech
/src/payment/       @my-org/payment-reviewers

# Dokumentasi dapat ditinjau oleh Technical Writer langsung
/docs/              @charlie-writer
*.md                @charlie-writer
```

### 4. Menegakkan Keamanan Melalui Branch Protection Rules
Berdasarkan fail tata kelola di atas, konfigurasi Branch Protection Rule untuk cabang `main` melalui Settings Repositori:
1. Centang **Require a pull request before merging**.
2. Centang **Require approvals** -> Masukkan angka minimal: `1` atau `2`.
3. Centang **Require review from Code Owners** (secara otomatis mengunci PR hingga tim di `CODEOWNERS` memberikan status *Approve*).
4. Centang **Require status checks to pass before merging** -> Pilih nama pipeline CI (misal: `test-suite`, `lint`).
5. Centang **Require conversation resolution before merging** (mencegah merge jika masih ada komentar review yang menggantung).
6. Centang **Do not allow bypassing the above settings** (berlaku untuk administrator repositori sekalipun).

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Saat mengonfigurasi tata kelola proyek di GitHub, setiap keputusan teknis memiliki implikasi timbal-balik (*trade-offs*):

### Matriks Perbandingan Strategi Penggabungan PR

| Parameter | Merge Commit (`--no-ff`) | Squash and Merge | Rebase and Merge |
| :--- | :--- | :--- | :--- |
| **Kondisi Riwayat Git** | Non-linear, penuh percabangan (*bubble graphs*). | Linear sempurna (tepat 1 commit per PR). | Linear sempurna (banyak commit berurutan per PR). |
| **Penyimpanan Konteks** | Maksimal: mencatat setiap commit mikro pengembang asli. | Rendah: pesan commit individual hilang terpadatkan. | Menengah-Tinggi: commit individu ada, namun SHA berubah. |
| **Kemudahan Revert** | Mudah mengembalikan seluruh PR via satu tombol revert merge commit. | Sangat mudah: cukup lakukan `git revert <single-sha>`. | Sulit: harus me-revert sekumpulan commit secara berurutan. |
| **Kesesuaian Penggunaan** | Proyek open source berskala masif dengan branch rilis jangka panjang. | **Standar industri untuk tim agile modern** (fitur terisolasi). | Tim dengan disiplin penulisan commit mikro yang sangat ketat (*atomic commits*). |

### Trade-offs Tata Kelola (Strictness vs Velocity)
* **Aturan Sangat Ketat (Strict Governance)**: Menuntut 2 reviewer, validasi CODEOWNERS, dan puluhan status check CI.
  * *Keuntungan*: Kualitas kode mendekati zero-defect, mitigasi celah keamanan tinggi.
  * *Kerugian*: Kecepatan rilis (*development velocity*) menurun drastis; tim mengalami *PR fatigue* menunggu persetujuan.
* **Aturan Terlalu Longgar (Permissive Governance)**: Mengizinkan merge tanpa review atau tanpa CI check.
  * *Keuntungan*: Pengiriman fitur sangat cepat (*rapid prototyping*).
  * *Kerugian*: Potensi *production breakdown*, technical debt menumpuk cepat, dan sulit menentukan siapa yang bertanggung jawab atas kegagalan sistem.

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan Draft Pull Requests**: Jika pekerjaan Anda belum tuntas namun Anda membutuhkan *early feedback* atau ingin memicu runner CI, buka PR sebagai **Draft PR**. Ini mengkomunikasikan bahwa kode belum siap di-merge dan tidak akan mengganggu notifikasi Code Owners.
2. **Jaga PR Tetap Berukuran Kecil (*Atomic PRs*)**: PR yang mengubah kurang dari 200–300 baris kode terbukti mendapatkan ulasan yang jauh lebih mendalam dan cepat diselesaikan dibandingkan "PR Raksasa" dengan 2.000+ baris perubahan.
3. **Standarisasi Judul PR dengan Conventional Commits**: Format judul PR Anda: `feat: ...`, `fix: ...`, `refactor: ...`, `chore: ...`. Ketika Anda menggunakan strategi *Squash and Merge*, GitHub secara default dapat menggunakan judul PR ini sebagai pesan commit akhir di cabang target.
4. **Terapkan Taksonomi Label yang Teratur**: Gunakan pewarnaan dan label berstandar industri:
   * Kategori Tipe: `type: bug` (merah), `type: feature` (hijau), `type: chore` (abu-abu).
   * Kategori Prioritas: `priority: critical`, `priority: low`.
   * Kategori Status: `status: blocked`, `status: in-review`.
5. **Konfigurasikan Auto-Delete Head Branches**: Aktifkan fitur **"Automatically delete head branches"** di pengaturan repositori. Ini mencegah penumpukan ratusan cabang fitur usang (*stale branches*) pada server repositori remote setelah PR berhasil di-merge.
6. **Tautkan Isu ke Milestone**: Kelompokkan isu dan PR ke dalam *Milestone* (misal: `Sprint 24`, `Release v1.2.0`) untuk melacak metrik *burn-down* secara otomatis.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. The "Mega PR" (Anti-pattern Monolitik)
* **Kesalahan**: Menggabungkan pekerjaan 3 fitur berbeda dan 5 perbaikan bug ke dalam 1 Pull Request raksasa yang menyentuh 40 fail.
* **Dampak**: Peninjau mengalami kelelahan kognitif (*cognitive overload*), review dilakukan secara dangkal (*rubber-stamping approval*), dan jika terjadi *bug*, proses `git revert` akan membatalkan seluruh fitur lain yang sebenarnya tidak bermasalah.
* **Solusi**: Pecah menjadi beberapa cabang fitur terisolasi dan ajukan PR terpisah secara bertahap.

### 2. Manual Issue Closing (Lupa Mengaitkan Kata Kunci)
* **Kesalahan**: Menulis teks ambigu di PR seperti: "Mengerjakan isu nomor 10" alih-alih `Resolves #10`.
* **Dampak**: Isu tetap berstatus "Open" setelah PR di-merge, menyebabkan data papan proyek (*Project Board*) tidak sinkron dengan kondisi kode nyata.
* **Solusi**: Terapkan *PR Template* yang mewajibkan sintaks resmi (`Fixes #<nomor_isu>`).

### 3. Mengabaikan Tinjauan Resolusi Konflik di Lingkungan Lokal
* **Kesalahan**: Menyelesaikan konflik merge PR yang rumit langsung melalui antarmuka web editor GitHub tanpa menjalankan uji coba/test suite lokal.
* **Dampak**: Sintaks konflik (`<<<<<<< HEAD`) secara tidak sengaja ter-commit, atau kode hasil resolusi gagal di-kompilasi.
* **Solusi**: Selalu tarik cabang target ke lokal, gabungkan atau rebase di lokal, jalankan *test suite*, lalu dorong kembali:
  ```bash
  git checkout feat/my-feature
  git fetch origin
  git merge origin/main
  # Selesaikan konflik pada text editor, verifikasi test:
  npm test
  git commit -m "chore: resolve merge conflicts with main"
  git push origin feat/my-feature
  ```

### 4. Mengizinkan *Force Push* pada Cabang Kolaboratif
* **Kesalahan**: Menjalankan `git push --force` pada branch PR yang sedang dikerjakan bersama anggota tim lain.
* **Dampak**: Menimpa riwayat commit rekan setim, menyebabkan desinkronisasi lokal pada repositori rekan Anda.
* **Solusi**: Gunakan opsi yang lebih aman `git push --force-with-lease` jika rebase benar-benar diperlukan, atau komunikasikan sebelum melakukan rebase.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Laboratorium
Anda bertindak sebagai *Lead Architect* yang harus membangun tata kelola awal pada sebuah repositori baru bernama `github-governance-lab`.

### Tugas:
1. Inisialisasi struktur repositori lokal dan hubungkan ke GitHub.
2. Buat direktori `.github/` yang memuat template PR dan deklarasi CODEOWNERS.
3. Simulasikan pembuatan Isu, pengerjaan di branch baru, dan pembukaan PR terstruktur.

#### Langkah 1: Setup Proyek dan Governance Files
```bash
# Inisialisasi direktori
mkdir github-governance-lab
cd github-governance-lab
git init
echo "# GitHub Governance Lab" > README.md

# Buat struktur direktori .github
mkdir -p .github/ISSUE_TEMPLATE

# Buat Pull Request Template
cat << 'EOF' > .github/PULL_REQUEST_TEMPLATE.md
## Konteks
Fixes #

## Deskripsi Perubahan
- 

## Checklist Mandiri
- [ ] Kode sudah diuji mandiri
EOF

# Inisialisasi commit pertama
git add .
git commit -m "chore: setup awal repositori dan tata kelola github"
git branch -M main

# Buat repositori baru di GitHub (via CLI atau Web)
# Jika via gh CLI:
gh repo create github-governance-lab --public --source=. --remote=origin --push
```

#### Langkah 2: Tambahkan CODEOWNERS
```bash
# Ganti @username-anda dengan username GitHub Anda yang sebenarnya
echo "* @$(gh api user -q .login)" > .github/CODEOWNERS

git add .github/CODEOWNERS
git commit -m "ci: tambahkan konfigurasi CODEOWNERS"
git push origin main
```

#### Langkah 3: Simulasi Alur Kerja End-to-End
```bash
# 1. Buat Isu via GitHub CLI
gh issue create --title "feat: tambahkan modul kalkulator matematika" \
                --body "Kita memerlukan file kalkulator dasar untuk operasi penjumlahan."

# Catat nomor isu yang muncul (asumsikan #1)

# 2. Buat branch fitur baru
git checkout -b feat/calculator-module

# 3. Buat implementasi kode
mkdir -p src
cat << 'EOF' > src/calculator.js
function add(a, b) {
    return a + b;
}
module.exports = { add };
EOF

# 4. Commit dan Push
git add src/calculator.js
git commit -m "feat(calc): implementasi fungsi penambahan matematika"
git push -u origin feat/calculator-module

# 5. Buat PR dengan menautkan Isu #1
gh pr create --title "feat: implementasi fungsi penambahan" \
             --body "Menambahkan modul calculator.js. Fixes #1." \
             --base main
```

#### Langkah 4: Tinjau dan Gabungkan PR
1. Buka URL PR yang dihasilkan oleh CLI di peramban web.
2. Perhatikan bahwa templat PR terisi secara otomatis dan Isu #1 tertaut di bilah kanan (*sidebar*).
3. Lakukan penggabungan menggunakan strategi **Squash and Merge**.
4. Periksa kembali tab **Issues** di GitHub; pastikan Isu #1 telah berpindah ke status **Closed** secara otomatis.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan-pertanyaan di bawah ini untuk mengukur pemahaman teknis Anda:

### Soal Pilihan Ganda

#### 1. Perintah pesan commit atau deskripsi PR manakah yang TIDAK AKAN menutup GitHub Issue nomor 88 secara otomatis saat di-merge ke main?
* A. `Resolves #88`
* B. `Closes #88`
* C. `Fixes #88`
* D. `Addresses #88`

#### 2. Pada file `.github/CODEOWNERS`, terdapat baris: `/docs/* @tech-writer`. Apa implikasi dari baris konfigurasi tersebut terhadap file `/docs/api/v1.md`?
* A. `@tech-writer` secara otomatis diwajibkan mereview berkas tersebut.
* B. `@tech-writer` TIDAK diwajibkan mereview, karena pola `/docs/*` hanya cocok untuk berkas langsung di bawah folder docs, bukan pada subdirektori `/api/`.
* C. Repositori akan menampilkan error sintaks karena format path tidak valid.
* D. Semua berkas berekstensi `.md` akan otomatis diambil alih oleh `@tech-writer`.

#### 3. Kapan sebuah tim rekayasa perangkat lunak sebaiknya memilih strategi "Squash and Merge" dibandingkan "Create a Merge Commit"?
* A. Ketika tim ingin mempertahankan setiap jejak commit mikro eksperimental dan commit typo yang dilakukan oleh developer di cabang fitur.
* B. Ketika tim memprioritaskan riwayat cabang utama (`main`) yang linear, rapi, dan mudah ditelusuri per fungsionalitas fitur.
* C. Ketika cabang fitur memiliki commit yang ditandatangani secara kriptografis (*GPG-signed*) dan identitas individual SHA commit harus dipertahankan secara legal.
* D. Ketika tim dilarang menggunakan Git rebase secara kebijakan internal.

#### 4. Apa yang membedakan Draft Pull Request dengan Pull Request reguler di GitHub?
* A. Draft PR tidak dapat dikompilasi oleh runner GitHub Actions / CI.
* B. Draft PR tidak dapat di-merge ke cabang target dan tidak memicu penugasan review otomatis kepada CODEOWNERS.
* C. Draft PR hanya dapat dilihat oleh pembuat PR dan administrator repositori.
* D. Draft PR secara otomatis tertutup jika tidak ada aktivitas dalam waktu 24 jam.

#### 5. Seorang pengembang mencoba menjalankan `git push origin main` secara langsung dan mendapatkan galat `[remote rejected] main -> main (protected branch hook declined)`. Tindakan teknis apa yang harus dilakukan?
* A. Menjalankan `git push --force origin main`.
* B. Menghapus branch remote `main` dan membuat ulang.
* C. Membuat branch baru dari commit lokal tersebut, mendorong (*push*) branch baru ke remote, lalu membuka Pull Request ke cabang `main`.
* D. Mengubah konfigurasi SSH key lokal karena akses telah kedaluwarsa.

---

### Kunci Jawaban & Rasional

1. **Jawaban: D**. GitHub hanya mengenali kata kerja aksi penutupan tertentu (`close`, `fix`, `resolve` beserta variasi *tenses*-nya). Kata `Addresses` bukan kata kunci resmi penutup isu.
2. **Jawaban: B**. Format glob `/docs/*` hanya berlaku untuk fail langsung di dalam `/docs/`. Agar mencakup subdirektori rekursif seperti `/docs/api/v1.md`, polanya harus ditulis `/docs/` atau `/docs/**`.
3. **Jawaban: B**. *Squash and Merge* menyatukan seluruh commit ranting fitur menjadi 1 unit commit tunggal, menghasilkan riwayat `main` yang bersih dan linear tanpa commit perantara (*noise*).
4. **Jawaban: B**. Draft PR secara eksplisit memblokir tombol *Merge* dan mencegah pengiriman notifikasi peninjauan kepada *Code Owners* sampai statusnya diubah menjadi *"Ready for review"*.
5. **Jawaban: C**. Pesan galat mengindikasikan adanya aturan *Branch Protection*. Developer harus melalui siklus standar: buat cabang fitur terpisah, lakukan *push*, dan buka *Pull Request*.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Dokumentasi Resmi GitHub**:
  * [GitHub Docs: About Pull Requests](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests)
  * [GitHub Docs: About Protected Branches & Rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
  * [GitHub Docs: About Code Owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)
* **Buku Referensi**:
  * Chacon, S., & Straub, B. (2014). *Pro Git* (2nd ed.). Apress. (Bab 6: *GitHub*).
  * Bell, P., & Beer, B. (2014). *Introducing GitHub: A Non-Technical Guide*. O'Reilly Media.
* **Standar Spesifikasi Industri**:
  * [Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **GitHub Collaboration Layer**: GitHub menambahkan fungsionalitas manajemen komunikasi, pengawasan, dan tata kelola di atas sistem kontrol versi Git murni melalui *Issues*, *Pull Requests*, dan konfigurasi `.github/`.
2. **Pull Request Lifecycle**: Alur kerja PR melibatkan isolasi cabang fitur, pembuatan PR berbasis templat, verifikasi otomatis melalui CI/CD *Status Checks*, tinjauan sejawat (*peer review*), pemenuhan proteksi cabang, dan penggabungan ke cabang target.
3. **Branch Protection**: Fondasi keamanan produksi yang mencegah *direct push* ke cabang utama, menuntut jumlah *approval* minimum, dan memastikan seluruh uji kelayakan kode telah sukses dieksekusi sebelum penggabungan.
4. **Strategi Merge**: Pemilihan antara *Merge Commit*, *Squash*, dan *Rebase* bergantung pada kebijakan riwayat proyek. *Squash and Merge* adalah standar de-facto untuk menjaga riwayat cabang utama tetap linear dan modular.
5. **Otomatisasi Tata Kelola**: Pemanfaatan fail deklaratif seperti `CODEOWNERS`, *Issue Form Templates*, dan kata kunci penutup otomatis (`Fixes #ID`) meminimalisasi friksi operasional dan birokrasi manual dalam tim pengembangan.

---

## SEKSI 17 — GLOSARIUM

* **Atomic Pull Request**: Praktik rekayasa perangkat lunak di mana sebuah PR hanya menyelesaikan satu tugas fungsionalitas tunggal yang terisolasi dan mandiri, meminimalkan kompleksitas tinjauan.
* **Branch Protection Rules**: Aturan keamanan tingkat repositori di GitHub untuk membatasi aksi commit, merge, penghapusan, dan force-pushing pada branch tertentu.
* **CODEOWNERS**: Fail konfigurasi di jalur `.github/CODEOWNERS` yang secara otomatis menetapkan akun atau tim pengulas ketika berkas tertentu dimodifikasi dalam PR.
* **Draft PR**: Status Pull Request yang digunakan untuk berbagi progres kerja yang belum selesai tanpa memicu proses approval formal atau notifikasi Code Owners.
* **Linear History**: Bentuk riwayat commit Git yang lurus tanpa adanya percabangan (*merge bubble*), umumnya dicapai menggunakan *Rebase* atau *Squash and Merge*.
* **Merge Conflict**: Kondisi di mana Git tidak dapat menggabungkan dua rangkaian perubahan pada baris berkas yang sama secara otomatis, menuntut resolusi manual oleh manusia.
* **Milestone**: Fitur GitHub untuk mengelompokkan sekumpulan Issues dan Pull Requests guna melacak pencapaian target target rilis tertentu.
* **Peer Review**: Proses inspeksi kode sumber secara sistematis oleh sesama perekayasa perangkat lunak sebelum kode diintegrasikan ke lingkungan produksi.
* **Squash and Merge**: Operasi penggabungan yang mereduksi deretan commit pada branch fitur menjadi satu commit terkonsolidasi pada branch utama.
* **Status Check**: Pemeriksaan latar belakang oleh sistem eksternal (seperti pengujian unit pada CI/CD) yang harus berstatus lulus (*green*) sebelum sebuah PR dapat di-merge.

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Poin Penekanan Materi:
* Tekankan kepada peserta didik bahwa *Pull Request* **bukanlah** perintah bawaan Git (`git pr` tidak ada secara native di instalasi Git dasar). PR adalah konstruksi platform kolaboratif (GitHub, GitLab, Bitbucket).
* Saat sesi latihan, pastikan peserta memahami perbedaan antara *Squash Merge* dan *Regular Merge*. Sering kali pemula panik ketika riwayat commit mikro mereka "hilang" di cabang utama setelah melakukan Squash. Berikan pemahaman bahwa perubahan kodenya tetap utuh, hanya representasi riwayatnya yang dipadatkan.

### Area Rawan Kesalahan Siswa:
* **Penulisan CODEOWNERS**: Kesalahan umum adalah lupa memberikan spasi antar nama akun atau menggunakan nama akun yang bukan anggota repositori/organisasi dengan hak akses tulis (*write access*).
* **Konflik Branch Protection**: Siswa yang mencoba melakukan push langsung ke `main` setelah aturan proteksi diaktifkan sering mengira bahwa kredensial SSH/PAT mereka rusak. Arahkan mereka untuk membaca pesan galat terminal secara teliti.

### Rencana Cadangan untuk Lab:
* Jika peserta terkendala menggunakan GitHub CLI (`gh`), seluruh alur Latihan Hands-on (Seksi 13) dapat dialihkan menggunakan kombinasi antarmuka terminal murni untuk perintah Git dasar dan antarmuka web GUI GitHub untuk pembuatan Isu serta PR.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0** (Tanggal: 2024-03-30)
  * Rilis inisial materi Bab 08 Modul 01 kurikulum `git-github-beginner`.
  * Penambahan skema form Issue modern berbasis YAML.
  * Penambahan konfigurasi komprehensif CODEOWNERS dan PR Templates.
  * Penyusunan matriks perbandingan performa dan histori strategi merge.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `GIT-CORE-0701 — Pengenalan Remote Repositories, Git Fetch, Pull, dan Push`
* **Modul Saat Ini**: `GIT-CORE-0801 — Tata Kelola Repositori, Alur Kerja Pull Request, dan Orkestrasi Isu`
* **Modul Berikutnya**: `GIT-CORE-0802 — GitHub Actions: Fondasi Otomatisasi CI/CD dan Validasi Terintegrasi`