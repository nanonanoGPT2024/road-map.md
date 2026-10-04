## SEKSI 01 — IDENTITAS MODUL

*   **Mata Pelajaran / Jalur**: Git & GitHub Enterprise Engineering
*   **Kategori**: `01-Core-Foundations`
*   **Bab 07**: Pull Request Workflows & Code Review Mechanics
*   **Modul 01**: Anatomi Pull Request, Siklus Hidup Review, dan Integrasi Cabang
*   **Tingkat Kesulitan**: Intermediate to Advanced
*   **Prasyarat**:
    *   Pemahaman mendalam tentang Git DAG (*Directed Acyclic Graph*), Three-Tree Architecture (`Working Directory`, `Index/Staging`, `HEAD`).
    *   Kemahiran dalam strategi pencabangan dasar (*feature branching*, *trunk-based development*).
    *   Kemampuan mengeksekusi operasi plumbing & porcelain dasar: `git commit`, `git checkout`/`git switch`, `git rebase`, `git merge`, dan `git fetch`.
*   **Estimasi Waktu Penyelesaian**: 180 Menit (Teori: 60 Menit, Praktik Hands-On: 120 Menit)
*   **Versi Kurikulum**: v2.4.0 (Update Q2/2025)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Menganalisis (C4)** arsitektur internal Pull Request (PR), termasuk mekanisme ref remote khusus GitHub (`refs/pull/<id>/head` dan `refs/pull/<id>/merge`) serta algoritma penentuan *three-way diff* berbasis `git merge-base`.
2.  **Mengimplementasikan (C3)** alur kerja PR hulu-ke-hilir menggunakan antarmuka grafis GitHub dan GitHub CLI (`gh`), dari pembentukan *draft PR*, otomatisasi metadata, hingga eksekusi merge.
3.  **Mengevaluasi (C5)** kode sumber secara objektif melalui kerangka kerja *Structured Code Review*, memanfaatkan *multi-line comments*, saran revisi (*suggestion blocks*), dan pengelompokan feedback (*Nitpick*, *Blocking*, *FYI*).
4.  **Mengoperasikan (C3)** mitigasi iterasi review dengan teknik *amend*, *interactive rebase*, dan pembaruan ref cabang menggunakan `git push --force-with-lease` tanpa merusak riwayat ulasan (*review history*).
5.  **Merumuskan (C6)** strategi integrasi cabang (*Merge Commit*, *Squash and Merge*, *Rebase and Merge*) yang optimal berdasarkan parameter tata kelola proyek, integritas riwayat git (*git log provenance*), dan kesiapan rilis.
6.  **Mengonfigurasi (C3)** aturan proteksi cabang (*Branch Protection Rules* & *Repository Rulesets*) serta `CODEOWNERS` untuk menegakkan tata kelola kualitas dan keamanan sebelum integrasi kode ke cabang utama (*trunk*).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       [ Pull Request Architecture ]
                                     |
         +---------------------------+---------------------------+
         |                                                       |
         v                                                       v
[ Internal Mechanics ]                                [ Collaboration Layer ]
  ├── refs/pull/<id>/head                               ├── PR Life-Cycle (Draft/Ready)
  ├── refs/pull/<id>/merge                              ├── Review States (Approve/Changes)
  ├── 3-Way Diff (merge-base)                           ├── Suggestion Blocks
  └── Status Checks (CI/CD)                             └── Branch Protection & Rulesets
         |                                                       |
         +---------------------------+---------------------------+
                                     |
                                     v
                        [ Branch Integration Strategy ]
                                     |
         +---------------------------+---------------------------+
         |                           |                           |
         v                           v                           v
  [ Merge Commit ]           [ Squash & Merge ]          [ Rebase & Merge ]
  (--no-ff, preserve         (Atomic commit, clean       (Linear history,
   context & DAG history)     history, drops context)     preserves individual commits)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Dalam lanskap rekayasa perangkat lunak modern, kode sumber tidak pernah ditulis dalam isolasi absolut. *Pull Request* (istilah GitLab: *Merge Request*) bukan sekadar tombol pada antarmuka web, melainkan sebuah **kontrak kolaborasi teknis** dan **gerbang kendali mutu (quality gate)** utama dalam fase *continuous integration*.

Secara industri, PR memegang peranan krusial dalam:

1.  **Asynchronous Quality Assurance**: Memungkinkan tim terdistribusi melakukan inspeksi statis dan dinamis terhadap perubahan kode sebelum menyentuh cabang produksi. Mengeliminasi dependensi komunikasi sinkronus yang menghambat skalaritas tim.
2.  **Pengurangan Beban Kognitif (Cognitive Load)**: Melalui atomisitas tinjauan, anggota tim dapat memverifikasi logika bisnis, potensi kebocoran keamanan (*security vulnerability*), dan performa dalam lingkup kecil yang terkonsentrasi.
3.  **Audit Trail & Knowledge Distribution**: PR menyediakan catatan historis permanen mengenai *mengapa* (*why*) sebuah perubahan dilakukan, bukan hanya *apa* (*what*) yang berubah. Diskusi PR mendokumentasikan konteks keputusan arsitektur yang sangat berharga bagi pemeliharaan jangka panjang (*long-term maintainability*).
4.  **Automated Policy Enforcement**: Menghubungkan proses *human review* dengan *machine validation* (linter, unit test, build check, vulnerability scanner). Jika proteksi ini diabaikan, *trunk/main* akan rentan mengalami regresi (*broken build*), yang secara eksponensial meningkatkan biaya siklus remediasi perangkat lunak (*software defect remediation cost*).

---

## SEKSI 05 — APA ITU (WHAT)

### Definisi Formal Pull Request
Secara esensial, **Pull Request** adalah konstruksi tingkat aplikasi (disediakan oleh platform seperti GitHub, GitLab, atau Bitbucket) dan **bukan** merupakan fitur asli (*native*) dari Git CLI inti. PR adalah permintaan formal dari seorang kontributor kepada pemelihara repositori (*maintainer*) untuk menarik (*pull*) serangkaian komit dari sebuah cabang (baik di dalam repositori yang sama maupun repositori *fork*) dan menggabungkannya (*merge*) ke cabang target.

### Anatomi Fisik Pull Request
Sebuah PR yang komprehensif terdiri atas:
*   **Base Branch**: Cabang hilir (*downstream/target*) tempat komit akan disatukan (misal: `main`, `develop`).
*   **Head/Compare Branch**: Cabang hulu (*upstream/source*) yang membawa serangkaian komit baru (misal: `feature/user-auth`).
*   **Metadata**: Judul konvensional, deskripsi komprehensif, label, penugasan (*assignees*), peninjau (*reviewers*), *milestones*, dan *linked issues*.
*   **Diff Context**: Tampilan perbedaan kode (*diff*) yang dihitung dari *common ancestor* terakhir.
*   **Timeline Event Stream**: Representasi kronologis komit, komentar kode, hasil uji otomatisasi CI/CD, dan status perubahan ulasan.

### Status Siklus Hidup Pull Request
```
[ Open / Draft ] ──(Mark as Ready)──> [ Open / In Review ] ──(Approved)──> [ Merged ]
       |                                      |                                ^
       |                                      v                                |
       +──────────────────────────────> [ Closed ] ───────────────────────────+
```
*   **Draft PR**: Status yang menandakan pekerjaan masih berjalan (*work in progress*). PR tidak dapat di-merge, dan peninjau yang ditugaskan tidak diberi notifikasi agresif.
*   **Open (Ready for Review)**: PR siap ditinjau secara formal. Status checks CI dieksekusi, dan notifikasi dikirimkan kepada reviewer/CODEOWNERS.
*   **Changes Requested**: Peninjau mengidentifikasi kekurangan atau cacat kritis yang wajib diremediasi sebelum kode dapat disatukan.
*   **Approved**: Kode telah memenuhi standar arsitektur dan fungsionalitas, siap masuk fase integrasi.
*   **Merged**: Seluruh perubahan telah disatukan ke *base branch*, dan cabang *head* lazimnya dihapus.
*   **Closed**: PR ditutup tanpa penggabungan kode (dibatalkan, diganti, atau tidak relevan).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Mekanisme Internal GitHub Refs
Ketika sebuah PR dibuat di GitHub, platform membuat referensi Git tersembunyi (*hidden refs*) di server:
*   `refs/pull/<PR_ID>/head`: Menunjuk tepat pada commit tip terbaru dari *compare branch*.
*   `refs/pull/<PR_ID>/merge`: Representasi komit penggabungan simulatif (pre-merge commit) antara *head branch* dan *base branch*. Objek ref ini dihitung secara dinamis oleh GitHub untuk menentukan apakah PR dapat di-merge secara otomatis (*clean*) atau terjadi konflik (*merge conflict*), serta digunakan sebagai target uji CI runner.

Kita dapat mengunduh dan memeriksa ref ini secara lokal tanpa menambah remote kontributor:
```bash
git fetch origin pull/42/head:pr-42-local
git checkout pr-42-local
```

### 2. Algoritma Three-Way Diffing (`merge-base`)
GitHub tidak menampilkan diff antara *HEAD* dari *base branch* saat ini dan *HEAD* dari *feature branch*. Diff yang ditampilkan dihitung berdasarkan **Merge Base**:

$$\text{Merge Base} = \text{Ancestor}(Base, Head)$$

```bash
# Perhitungan manual git diff yang identik dengan tampilan default PR di GitHub
MERGE_BASE=$(git merge-base origin/main feature/login)
git diff $MERGE_BASE..feature/login
# Atau menggunakan sintaks 3-dot diff:
git diff origin/main...feature/login
```
Artinya, perubahan yang masuk ke `origin/main` *setelah* cabang fitur dibuat **tidak akan tampil** di tab "Files Changed" PR, kecuali ada sinkronisasi ulang cabang.

### 3. Review Lifecyle Mechanics
Siklus review kode modern terdiri dari 3 fase:
1.  **Inspection & Threading**: Peninjau memilih rentang baris tertentu (*multi-line diff*), memberikan analisis kontekstual, atau membuat instruksi perubahan.
2.  **Suggested Changes**: Peninjau dapat memanfaatkan sintaks Markdown khusus GitHub untuk menyarankan kode pengganti:
    ````markdown
    ```suggestion
    const timeoutMs = 5000;
    ```
    ````
    Pemilik PR dapat langsung menerima saran tersebut dengan membuat komit otomatis langsung melalui UI GitHub (*batch apply*).
3.  **State Evaluation**: Reviewer memberikan keputusan formal:
    *   **Comment**: Masukan informatif tanpa memblokir proses merge.
    *   **Approve**: Menyetujui penggabungan.
    *   **Request Changes**: Memblokir merge secara imperatif hingga ada komit perbaikan.

### 4. Branch Protection Rules & Rulesets
Merupakan konfigurasi keamanan tingkat repositori yang memastikan alur kerja tidak dapat dilompati (*bypass*):
*   Memerlukan sejumlah persetujuan ulasan minimum (*minimum approving reviews*).
*   Mengharuskan resolusi seluruh utas ulasan (*require conversation resolution*).
*   Memerlukan lulus uji CI (*status checks must pass*) sebelum merge.
*   Mengharuskan cabang fitur mutakhir (*require branches to be up to date before merging*).
*   Mewajibkan *Signed Commits* (GPG/SSH).

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Diagram 1: Topologi Refs dan Perhitungan Diff GitHub PR
```
Commit Tree:
      A --- B --- C  (origin/main)
             \
              \  <-- Merge Base: (B)
               \
                D --- E --- F  (feature/payment)
                            ^
                            |
                   (origin/refs/pull/101/head)

Simulasi GitHub PR Diff:
Diff View = git diff B...F (Hanya menampilkan mutasi komit D, E, dan F)

Simulasi GitHub Pre-Merge CI Test:
      A --- B --- C --------- M'  (origin/refs/pull/101/merge)
             \               /
              D --- E --- F -
      (M' adalah ephemeral commit untuk mengeksekusi test runner CI)
```

### Diagram 2: Perbandingan Topologi Merge Strategy
```
Initial State:
main:    A --- B --- C
                \
feature:         D --- E

1. MERGE COMMIT (git merge --no-ff feature)
main:    A --- B --- C --------- M (Merge Commit memiliki 2 parent: C dan E)
                \               /
                 D ----------- E

2. SQUASH AND MERGE (Kompresi D + E menjadi satu unit komit baru S)
main:    A --- B --- C --- S
         (History D dan E dilepas dari base branch; S memiliki 1 parent: C)

3. REBASE AND MERGE (Replay D dan E di atas HEAD main saat ini)
main:    A --- B --- C --- D' --- E'
         (Linear history tanpa merge commit; SHA D dan E berubah menjadi D' dan E')
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah demonstrasi pembuatan dan manajemen PR dari terminal menggunakan **GitHub CLI (`gh`)**, yang mencerminkan alur kerja standar insinyur perangkat lunak:

```bash
# 1. Pastikan berada di cabang main yang mutakhir
git checkout main
git pull --ff-only origin main

# 2. Buat cabang fitur baru
git checkout -b feature/update-readme-metrics

# 3. Lakukan modifikasi kode
echo "## Engineering Metrics: 99.99% Uptime" >> README.md
git add README.md
git commit -m "docs: add engineering metrics to readme"

# 4. Dorong cabang ke remote server
git push -u origin feature/update-readme-metrics

# 5. Buka PR via GitHub CLI (Mode Draft)
gh pr create \
  --title "docs: update uptime SLA metrics in README" \
  --body "Menambahkan SLA availability terbaru sesuai standar Q2." \
  --draft \
  --base main

# 6. Mengubah status Draft menjadi Ready for Review
gh pr ready

# 7. Memeriksa status dan feedback PR
gh pr status
gh pr view --comments
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut skenario end-to-end integrasi fitur perbankan berskala enterprise dengan penanganan ulasan ketat, rebase interaktif, dan `push --force-with-lease`.

### 1. Inisialisasi Template Pull Request
Simpan berkas pada repositori di `.github/PULL_REQUEST_TEMPLATE.md`:
```markdown
## Deskripsi Masalah
<!-- Jelaskan latar belakang teknis atau referensi Issue #ID -->
Fixes #452

## Tipe Perubahan
- [ ] Bug fix (perubahan non-breaking perbaikan isu)
- [x] New feature (perubahan non-breaking penambahan fitur)
- [ ] Breaking change (perbaikan atau fitur yang merusak kompatibilitas lama)

## Dampak Arsitektur & Kinerja
- Query database dioptimalkan dengan indeks majemuk pada `(tenant_id, account_id)`.

## Checklist Kepatuhan
- [x] Unit test & Integration test telah ditambahkan/diperbarui.
- [x] Lulus analisis statis (linter & sonar scanner).
- [x] Dokumentasi API (OpenAPI spec) dimutakhirkan.
```

### 2. Skenario Pengembangan & Iterasi Ulasan
Seorang insinyur membuat implementasi fitur validasi transaksi:

```bash
git checkout -b feature/tx-idempotency
# (Melakukan komit kode implementasi)
git commit -am "feat: implement redis idempotency lock for transaction"
git push -u origin feature/tx-idempotency

# Membuat PR resmi via GitHub CLI
gh pr create --template ".github/PULL_REQUEST_TEMPLATE.md"
```

### 3. Skenario Feedback Peninjau (Reviewer)
Reviewer menemukan bahwa durasi TTL kunci Redis terlalu singkat dan meninggalkan saran di PR:
> *"TTL Redis 2 detik terlalu agresif untuk jaringan dengan latency spike. Ubah ke 10 detik dan gunakan konstanta terdefinisi."*

### 4. Resolusi Masalah oleh Penulis PR Secara Elegan
Penulis kode tidak boleh membuat komit baru yang berantakan seperti `"fix typo review"`, `"fix review 2"`. Riwayat komit lokal dirapikan sebelum diintegrasikan:

```bash
# Modifikasi berkas konfigurasi
sed -i 's/LOCK_TTL = 2/LOCK_TTL = 10/' src/config/idempotency.ts

# Lakukan pengujian lokal
npm run test:unit

# Tambahkan perubahan ke stage
git add src/config/idempotency.ts

# Gabungkan perbaikan langsung ke komit sebelumnya menggunakan amend
git commit --amend --no-edit

# Sinkronisasikan dengan origin/main jika main telah bergerak maju
git fetch origin main
git rebase origin/main

# Dorong pembaruan ke GitHub secara aman menggunakan lease check!
# DILARANG MENGGUNAKAN: git push --force (karena berisiko menimpa komit orang lain)
git push --force-with-lease origin feature/tx-idempotency
```

### 5. Eksekusi Penggabungan (Merge)
Setelah menerima ulasan status `Approved` dari 2 Tech Lead dan seluruh check CI (Sonar, Tests) berwarna hijau:

```bash
# Menjalankan Squash & Merge via CLI dan menghapus cabang lokal/remote otomatis
gh pr merge feature/tx-idempotency --squash --delete-branch
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Memilih strategi penggabungan PR (*Merge Strategies*) membawa konsekuensi struktural langsung pada riwayat Git.

### Perbandingan Strategi Merge

| Dimensi Parameter | Create a Merge Commit (`--no-ff`) | Squash and Merge | Rebase and Merge |
| :--- | :--- | :--- | :--- |
| **Bentuk Riwayat (History)** | Non-linear, membentuk percabangan dan konvergensi DAG yang nyata. | Linear sempurna. Satu komit per PR di cabang target. | Linear sempurna. Seluruh komit individu ditarik ke atas base. |
| **Konteks Historis Perubahan** | Sangat Tinggi. Melestarikan setiap komit parsial beserta timestamp dan metadata aslinya. | Rendah. Seluruh pesan komit parsial dimampatkan menjadi satu pesan tunggal. | Tinggi. Mempertahankan pembagian langkah komit, namun SHA berubah. |
| **Kemudahan `git revert`** | Sulit. Harus menentukan flag `-m parent-number` (lazimnya `-m 1`). | Sangat Mudah. Cukup menjalankan `git revert <squash-commit-sha>`. | Sulit jika PR memiliki 20 komit, harus me-revert semuanya secara berurutan. |
| **Kinerja `git bisect`** | Cepat, dapat melompati seluruh branch PR dalam satu evaluasi biner. | Sangat Efektif dan granularitasnya setingkat fungsionalitas PR. | Berpotensi terhambat jika ada komit intermediate yang merusak build (*broken intermediate commit*). |
| **Use Case Terbaik** | Rilis modul besar, integrasi branch lingkungan (`develop` to `main`). | Alur *Trunk-Based Development*, tim berskala besar, fitur reguler. | Tim yang sangat disiplin dengan aturan komit mikro yang bersih dan *atomic*. |

---

## SEKSI 11 — BEST PRACTICES

1.  **Batasi Ukuran PR (Inverted Pyramid Principle)**:
    Ukuran PR ideal adalah **< 400 baris kode (LOC)** dengan waktu peninjauan < 60 menit. Riset SmartBear membuktikan bahwa defek yang ditemukan per 1.000 baris kode menurun drastis ketika ukuran ulasan melampaui 500 baris (fenomena *"Rubber Stamping"*).
2.  **Gunakan Format Konvensional pada Judul PR**:
    Selaraskan dengan spesifikasi *Conventional Commits*:
    *   `feat(auth): integrate OAuth2 PKCE workflow`
    *   `fix(db): resolve deadlocks in transaction processing`
3.  **Terapkan Standar Kode Etik Review (Conventional Comments)**:
    Labeli komentar ulasan dengan intonasi yang transparan:
    *   `praise:` "Pemisahan dependensi di kelas ini sangat rapi!"
    *   `nitpick (non-blocking):` "Penamaan variabel `usrIdx` bisa lebih deklaratif menjadi `userIndex`."
    *   `issue (blocking):` "Kueri ini berpotensi N+1 pada data relasional berskala besar."
    *   `question:` "Mengapa memilih algoritma polling dibanding webhook?"
4.  **Konfigurasi Berkas `CODEOWNERS`**:
    Tentukan hak veto ulasan otomatis berdasarkan path berkas di `.github/CODEOWNERS`:
    ```
    # Infrastruktur Terraform wajib di-review tim DevOps
    /infra/terraform/ @company/devops-team

    # Konfigurasi keamanan dan autentikasi
    /src/auth/        @company/security-champions
    ```
5.  **Dilarang Melakukan *Blind Approval***:
    Pemberian status ulasan *Approve* tanpa memeriksa implementasi unit testing atau implikasi *side-effect* adalah pelanggaran tata kelola rekayasa perangkat lunak yang berisiko tinggi (*engineering liability*).

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Monster Pull Requests (The Mega-PR)
*   **Kasus**: PR yang memuat perubahan 5.000 baris, mengubah 80 berkas yang mencakup refaktorisasi arsitektur, fitur baru, dan penggantian linter styling secara acak.
*   **Dampak**: Menghancurkan efektivitas reviewer. Berpotensi besar lolosnya cacat keamanan (*critical bugs*) karena reviewer mengalami keletihan visual (*visual fatigue*).
*   **Solusi**: Pecah fitur menjadi PR parsial menggunakan pola *Feature Toggles / Feature Flags*. Rilis infrastruktur dasar terlebih dahulu, kemudian logika bisnis di PR berikutnya.

### 2. Menggunakan `git push --force` di Cabang Kolaboratif
*   **Kasus**: Menjalankan `git push -f origin feature/branch` setelah rebase interaktif.
*   **Dampak**: Jika reviewer atau developer rekanan menambahkan komit bantuan langsung ke cabang tersebut, komit mereka akan terhapus (*obliterated*) dari riwayat remote.
*   **Solusi**: Jadikan `git push --force-with-lease` sebagai alias permanen. Opsi ini menolak dorongan komit jika ref remote telah bergeser dari apa yang diketahui oleh ref lokal.

### 3. Mengintegrasikan PR dengan Broken CI State
*   **Kasus**: Pengembang menggunakan hak akses administrator repositori untuk mem-bypass peringatan gagal pada runner unit-test, dengan dalih "hanya kegagalan linter minor".
*   **Dampak**: Memutus integritas rantai integrasi. Rekan kerja lain yang menarik cabang `main` akan mendapati kegagalan lokal yang bukan disebabkan oleh kode mereka.
*   **Solusi**: Kunci cabang `main` melalui ruleset: nonaktifkan opsi *Allow administrators to bypass branch protections*.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Lab
Anda ditugaskan menambahkan validasi email pada modul autentikasi repositori lokal, membuat PR secara remote, menerima ulasan penolakan (*changes requested*), merapikan riwayat secara elegan, dan menyatukannya (*merge*).

#### Tugas 1: Persiapan Cabang dan Modul
```bash
# 1. Masuk ke direktori latihan
mkdir -p /tmp/pr-workflow-lab && cd /tmp/pr-workflow-lab
git init -b main

# 2. Buat berkas awal
echo "console.log('App Initialized');" > app.js
git add app.js
git commit -m "chore: initial commit"

# 3. Buat cabang fitur
git checkout -b feature/email-validation
```

#### Tugas 2: Pembuatan Fitur & Komit Awal
```bash
# 1. Tambahkan kode validasi sederhana (mengandung celah logika)
cat << 'EOF' >> app.js
function validateEmail(email) {
    // BUG: validasi naif tanpa pengecekan format domain yang benar
    return email.includes('@');
}
EOF

git commit -am "feat: implement basic email check"
```

#### Tugas 3: Simulasi Simulasi Reviewer Memberikan Feedback
Anggaplah PR telah dibuka dan reviewer memberikan feedback:
*"Validasi `email.includes('@')` tidak memadai. Gunakan ekspresi reguler yang memvalidasi domain dan TLD."*

Lakukan perbaikan kode secara atomik:
```bash
# Ganti fungsi dengan regex yang valid
cat << 'EOF' > app.js
console.log('App Initialized');
function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(String(email).toLowerCase());
}
EOF

# Jalankan amend agar tidak meninggalkan jejak komit 'fix typo'
git commit -am "feat(auth): implement RFC-compliant email regex validation" --amend

# Verifikasi riwayat log lokal bersih
git log --oneline
```

#### Tugas 4: Simulasi Integrasi Terhadap Perubahan `main` (Upstream Divergence)
Selagi Anda bekerja, asumsikan cabang `main` menerima perubahan dari rekan lain:
```bash
git checkout main
echo "const APP_VERSION = '1.0.0';" >> config.js
git add config.js
git commit -m "feat(config): add app version tracking"

# Kembali ke cabang fitur dan lakukan rebase
git checkout feature/email-validation
git rebase main

# Verifikasi cabang Anda linear di atas main
git log --graph --oneline --all
```

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawab pertanyaan-pertanyaan berikut untuk menguji pemahaman Anda:

1.  **Jika branch `origin/main` telah bergerak maju sebanyak 5 komit sejak Anda membuat branch `feature/api`, apa yang terjadi pada tampilan komit dan diff di antarmuka Pull Request GitHub jika Anda BELUM melakukan rebase atau merge `main` ke branch Anda?**
    *   A. PR akan otomatis menampilkan 5 komit dari `main` tersebut di tab commits.
    *   B. Diff PR hanya akan menampilkan perbedaan antara `feature/api` dan titik temu terakhir (*merge-base*), mengabaikan 5 komit baru di `main`.
    *   C. GitHub akan memblokir rendering diff sampai rebase manual dieksekusi.
    *   D. PR akan otomatis tertutup karena statusnya invalid.

2.  **Apa perbedaan mendasar antara opsi perintah `git push --force` dan `git push --force-with-lease`?**
    *   A. `--force-with-lease` hanya berlaku untuk repositori open-source.
    *   B. `--force-with-lease` memeriksa apakah ref remote pada remote-tracking branch lokal identik dengan ref di remote server sebelum menimpa riwayat.
    *   C. `--force-with-lease` tidak mengubah SHA komit di server.
    *   D. Tidak ada perbedaan fungsional; keduanya adalah sinonim langsung.

3.  **Kapan penggunaan strategi *Squash and Merge* TIDAK disarankan dalam sebuah alur kerja repositori enterprise?**
    *   A. Ketika branch fitur berukuran sangat kecil (< 50 baris kode).
    *   B. Ketika branch fitur memuat serangkaian perbaikan arsitektur modular yang masing-masing komitnya dirancang independen dan harus dapat di-`revert` atau dilacak secara individual di kemudian hari.
    *   C. Ketika tim menggunakan Trunk-Based Development.
    *   D. Ketika branch protection rules mengaktifkan opsi *Require signed commits*.

4.  **Apa fungsi utama dari berkas `.github/CODEOWNERS`?**
    *   A. Menentukan hak akses write/admin pada level basis data repositori.
    *   B. Menentukan secara otomatis individu atau tim yang wajib menjadi *reviewer* ketika berkas pada path tertentu dimodifikasi dalam sebuah PR.
    *   C. Menyediakan daftar kredit pengembang untuk rilis open-source.
    *   D. Mengunci berkas agar tidak dapat diubah oleh siapapun selain pemiliknya.

### Kunci Jawaban & Pembahasan
1.  **Jawaban: B**. GitHub PR menggunakan pendekatan 3-dot diff (`git diff merge-base..HEAD`), sehingga modifikasi baru pada target branch (`main`) tidak ditampilkan pada tab perubahan berkas sampai branch target tersebut di-merge/rebase ke dalam branch PR.
2.  **Jawaban: B**. `--force-with-lease` bertindak sebagai *atomic compare-and-swap*. Jika ada orang lain yang mendorong komit ke cabang yang sama pada remote saat Anda melakukan rebase lokal, dorongan paksa Anda akan ditolak karena tracking ref lokal Anda telah usang.
3.  **Jawaban: B**. *Squash and Merge* menghancurkan identitas komit individu dan melebur semuanya ke dalam satu komit tunggal. Jika riwayat detail individual sangat krusial untuk pelacakan regresi modularitas, strategi ini akan menghilangkan konteks berharga tersebut.
4.  **Jawaban: B**. `CODEOWNERS` bertindak sebagai router perizinan otomatis GitHub untuk menugaskan tim/individu yang bertanggung jawab atas komponen path direktori tertentu agar masuk sebagai *mandatory reviewer*.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

*   **Buku Teks**:
    *   *Pro Git*, 2nd Edition (Scott Chacon & Ben Straub) — Bab 5: Distributed Git & Bab 6: GitHub.
    *   *Software Engineering at Google* (Titus Winters, Tom Manshreck, Hyrum Wright) — Bab 19: Code Review.
*   **Dokumentasi Resmi**:
    *   [GitHub Enterprise Docs: About Pull Requests](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests)
    *   [GitHub Docs: About Protected Branches and Rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches)
    *   [Conventional Comments Specification](https://conventionalcomments.org/)
*   **Peralatan Eksternal**:
    *   [GitHub CLI (`gh`) Official Manual](https://cli.github.com/manual/)

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1.  **Pull Request Bukan Objek Asli Git**: PR adalah lapisan orkestrasi kolaborasi di atas Git yang mengelola *intent to merge* dari sebuah *head branch* ke *base branch*.
2.  **Tiga Strategi Merge**: 
    *   *Merge Commit* menjaga riwayat non-linearitas DAG dan integritas konteks waktu.
    *   *Squash & Merge* memampatkan seluruh riwayat menjadi satu komit atomik (linear).
    *   *Rebase & Merge* menempatkan komit individu secara linear di atas HEAD target tanpa merge commit.
3.  **Keselamatan Penulisan Ulang Sejarah**: Jangan gunakan `push --force` di cabang kolaboratif. Selalu terapkan `git push --force-with-lease` untuk melindungi hasil kerja kontributor lain.
4.  **Budaya Code Review Efektif**: Review yang sukses bersandar pada ukuran perubahan kecil (< 400 LOC), penggunaan sintaks ulasan berlabel (*Conventional Comments*), otomatisasi *checks* via CI/CD, dan penegakan tata kelola melalui `CODEOWNERS` serta *Branch Rulesets*.

---

## SEKSI 17 — GLOSARIUM

*   **Atomic Commit**: Praktik membuat komit yang merepresentasikan satu unit perubahan fungsional terkecil yang lengkap dan tidak merusak kemampuan kompilasi/eksekusi kode.
*   **Branch Protection Rule**: Fitur tata kelola repositori untuk mengunci cabang tertentu agar kebal terhadap penghapusan, push langsung tanpa PR, atau penggabungan sebelum lolos kriteria proteksi.
*   **CODEOWNERS**: Berkas konfigurasi deklaratif yang memetakan pola jalur berkas (*file path patterns*) ke akun pengguna atau tim yang bertanggung jawab meninjaunya.
*   **Draft PR**: Entitas Pull Request yang sengaja ditandai belum siap digabungkan, digunakan untuk visibilitas progres awal tanpa memicu notifikasi review wajib.
*   **Fast-Forward Merge**: Operasi penggabungan cabang di mana *base branch* hanya memindahkan pointer HEAD-nya ke ujung *feature branch* tanpa membuat komit penggabungan baru, dimungkinkan jika tidak ada percabangan divergen.
*   **LGTM**: Akronim industri dari *"Looks Good To Me"*, secara informal mengindikasikan persetujuan ulasan kode.
*   **Merge Base**: Titik komit leluhur bersama (*common ancestor*) terdekat antara dua cabang yang sedang diperbandingkan.
*   **Nitpick (Nit)**: Komentar ulasan berkategori minor yang tidak bersifat memblokir (*non-blocking*), umumnya seputar preferensi gaya bahasa atau optimasi estetika kode.
*   **Pull Request Diff**: Visualisasi perbedaan status baris kode (tambah/hapus) yang dihitung secara dinamis dari titik `merge-base` hingga tip cabang compare.
*   **Review Suggestion Block**: Blok kode Markdown interaktif di PR GitHub yang memungkinkan reviewer menyarankan kode pengganti yang dapat di-commit langsung oleh pembuat PR.
*   **Trunk-Based Development**: Pola percabangan di mana seluruh pengembang secara teratur menggabungkan PR berukuran kecil ke cabang inti tunggal (*trunk* atau `main`).

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Model Pedagogi
Saat membimbing modul ini, fokus utama bukan hanya pada antarmuka web GitHub, melainkan pada **mekanika pointer Git** yang beroperasi di belakang layar. Instruktur harus mendemonstrasikan bahwa UI GitHub hanyalah representasi visual dari algoritma `git merge-base` dan manipulasi ref.

### Kesulitan Umum Siswa
*   Siswa sering kali bingung mengapa perubahan terbaru di `main` tidak muncul di tab "Files Changed" PR mereka. Demonstrasikan secara langsung di papan tulis atau terminal menggunakan `git merge-base main feature` vs `git diff main..feature`.
*   Banyak siswa takut melakukan *interactive rebase* karena khawatir merusak PR di web. Tunjukkan bahwa selama mereka menggunakan `--force-with-lease`, tab ulasan GitHub secara cerdas akan mengelompokkan riwayat baru ke dalam *"Force-pushed"* event tanpa menghilangkan komentar review terdahulu.

### Panduan Setup Sesi Praktik
Pastikan seluruh peserta telah memasang **GitHub CLI (`gh`)** versi terbaru dan telah terautentikasi melalui `gh auth login` menggunakan protokol SSH atau Personal Access Token yang memiliki cakupan izin `repo`.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi 2.4.0 (Mei 2025)**:
    *   Pembaruan materi proteksi cabang mencakup fitur GitHub Enterprise **Repository Rulesets**.
    *   Penambahan standardisasi format ulasan *Conventional Comments*.
    *   Penggantian instruksi `git checkout` lama ke format modern (`git switch`).
    *   Penambahan visualisasi ASCII topologi *merge-base* dan strategi merge.
*   **Versi 2.0.0 (Januari 2024)**:
    *   Integrasi panduan ekstensif penggunaan GitHub CLI (`gh`).
    *   Pengetatan panduan mitigasi push menggunakan parameter `--force-with-lease`.
*   **Versi 1.0.0 (Agustus 2022)**:
    *   Rilis kurikulum awal fondasi PR & Code Review.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   ⏮️ **Modul Sebelumnya**: `01-Core-Foundations / Bab 06 Module 02 — Git Remote Architecture, Upstream Tracking, and Protocol Mechanics`
*   ⏹️ **Modul Saat Ini**: `01-Core-Foundations / Bab 07 Module 01 — Pull Request Workflows & Code Review Mechanics`
*   ⏭️ **Modul Berikutnya**: `01-Core-Foundations / Bab 07 Module 02 — Merge Conflicts Resolution Patterns & Three-Way Merging Engine`