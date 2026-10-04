# BAB 09: Quiz, Challenge, & Knowledge Check
**Standar Tooling Frontend Modern, Kontrol Versi & Git**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Runtime Node.js vs. Browser Environment**  
   Meskipun kode frontend modern dieksekusi di runtime engine browser klien (seperti V8, SpiderMonkey, atau JavaScriptCore), mengapa seorang Software Engineer frontend modern mutlak membutuhkan Node.js di mesin lokalnya? Jelaskan peran Node.js dalam siklus hidup pengembangan (*development lifecycle*), khususnya terkait *module resolution*, *transpilation*, dan *development server*.

2. **Semantic Versioning (SemVer) & Lockfiles**  
   Diberikan definisi dependensi `"lib-ui": "^2.4.1"` dan `"lib-core": "~1.8.0"` di dalam `package.json`.  
   - Jelaskan interpretasi penanda `^` (caret) dan `~` (tilde) berdasarkan spesifikasi SemVer (`MAJOR.MINOR.PATCH`).  
   - Mengapa file `package-lock.json` (atau `pnpm-lock.yaml`) **wajib mutlak** dimasukkan ke dalam Git repository, dan apa bencana arsitektural yang terjadi pada lingkungan deployment jika file ini diabaikan (`.gitignore`)?

3. **Separation of Concerns: Linter vs. Formatter**  
   ESLint dan Prettier sering digunakan bersamaan dalam pipeline frontend enterprise.  
   - Jelaskan perbedaan mendasar antara *Code Quality Rules* (analisis Abstract Syntax Tree / AST) dan *Code Formatting Rules* (re-printing tokens).  
   - Mengapa aturan *formatting* sebaiknya didelegasikan sepenuhnya ke Prettier dan dinonaktifkan di ESLint (misalnya melalui `eslint-config-prettier`)?

4. **Struktur Data Git: Directed Acyclic Graph (DAG) & Object Storage**  
   Git tidak menyimpan perbedaan antar-baris (*delta differences*) seperti sistem VCS lama, melainkan menyimpan *snapshot*.  
   Jelaskan 4 jenis objek primitif dalam Git (`blob`, `tree`, `commit`, `tag`) dan bagaimana Git menyusun referensi objek-objek tersebut secara kriptografis menggunakan *hashing* (SHA-1/SHA-256) hingga membentuk topologi Directed Acyclic Graph (DAG).

5. **Siklus Hidup Status Kode di Git (Four-State Architecture)**  
   Uraikan perjalanan perubahan kode melalui 4 area utama Git:
   - *Working Directory*
   - *Staging Area (Index)*
   - *Local Repository*
   - *Remote Repository*  
   Sebutkan perintah spesifik Git yang memindahkan state antar-area tersebut, serta jelaskan apa yang secara fisik terjadi pada pointer `HEAD` ketika perintah `git commit` dijalankan.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Topologi Merge vs. Rebase**  
   Tinjau dua pendekatan integrasi branch: `git merge feature-branch` dan `git rebase main` dari dalam `feature-branch`.  
   - Bandingkan perbedaan topologi commit graph dari kedua pendekatan tersebut.  
   - Jelaskan apa yang dimaksud dengan *"The Golden Rule of Rebase"* dan diskusikan risiko teknis merusak riwayat kolaborasi jika seorang engineer mengeksekusi `rebase` pada branch publik yang dibagi bersama tim.

2. **Arsitektur Build Tools: Vite (Native ESM + esbuild) vs. Webpack Tradisional**  
   Mengapa pada repository frontend dengan ribuan modul, proses *Cold Start* dan *Hot Module Replacement* (HMR) Webpack mengalami degradasi performa linear ($O(n)$ terhadap jumlah file), sedangkan Vite mampu menyajikan startup hampir instan ($O(1)$) terlepas dari skala proyek? Bedah mekanisme *native ESM bundling* Vite di browser dan peran Go-based compiler `esbuild` dalam pre-bundling dependensi.

3. **Dependency Resolution: NPM/Yarn Flat-tree vs. PNPM Content-Addressable Storage**  
   Apa itu masalah *Phantom Dependencies* (atau *Ghost Dependencies*) yang umum ditemukan pada struktur `node_modules` terhoist (*flat tree*) milik npm/yarn v1? Bagaimana mekanisme hard-linking dan symlinking pada arsitektur content-addressable storage milik `pnpm` secara permanen menyelesaikan masalah ini sekaligus menghemat ruang penyimpanan disk?

4. **Anatomi dan Resolusi Git Conflict Marker**  
   Diberikan struktur conflict marker berikut:
   ```diff
   <<<<<<< HEAD
   const API_BASE_URL = "https://staging.internal.net/v2";
   =======
   const API_BASE_URL = process.env.VITE_API_URL ?? "https://api.production.com";
   >>>>>>> feature/dynamic-config
   ```
   - Jelaskan arti representasi teks di antara `<<<<<<< HEAD`, `=======`, dan `>>>>>>> [branch]`.  
   - Langkah teknis apa yang harus dilakukan oleh Git engine jika konflik terjadi pada file biner atau pada file auto-generated skala besar seperti `pnpm-lock.yaml`?

5. **Mekanisme Data Recovery: `git reflog` & Dangling Commits**  
   Seorang developer secara tidak sengaja mengeksekusi perintah destruktif: `git reset --hard HEAD~5` pada branch lokal dan kehilangan 5 commit penting yang belum di-*push* ke remote.  
   - Jelaskan mengapa data commit tersebut sebenarnya **belum terhapus** dari disk lokal Git.  
   - Tuliskan langkah debugging bertahap menggunakan `git reflog` untuk mengidentifikasi commit hash yang hilang dan memulihkan kondisi branch ke titik tepat sebelum reset dilakukan.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden CI Build Failure Pasca-Deployment Malam Hari
Sebuah aplikasi web frontend enterprise mengalami kegagalan build total di runner CI/CD (GitHub Actions) pada branch `main` pada pukul 02:00 dini hari, meskipun seluruh automated tests lulus di laptop lokal pengembang sebelum di-*merge*. Log CI menunjukkan error:
```text
TypeError: Cannot read properties of undefined (reading 'createRoot')
    at Object.<anonymous> (/node_modules/some-sub-dependency/index.js:14:23)
npm ERR! code 1
```
Investigasi awal menunjukkan bahwa pipeline CI menggunakan perintah `npm install`, sedangkan developer lokal menggunakan versi Node.js yang sedikit berbeda dan menambahkan dependensi baru beberapa jam sebelumnya.

* **Pertanyaan Diagnostik:**
  1. Identifikasi *root cause* mengapa `npm install` di runner CI mengeksekusi modifikasi resolusi paket yang berbeda dari status lokal mesin developer.
  2. Mengapa perintah `npm ci` adalah standar wajib enterprise untuk pipeline otomasi, dan apa prasyarat mutlak sistem agar `npm ci` dapat dieksekusi dengan sukses?
  3. Desain strategi standardisasi environment developer menggunakan `.nvmrc` / `package.json engines` untuk mencegah insiden berulang.

---

### Skenario B: Kerusakan DAG Akibat Force-Push Tak Terkendali di Branch Kolaborasi
Branch `release/v2.1` digunakan bersama oleh 6 developer untuk stabilisasi pra-produksi. Developer X mengalami conflict saat push, panik, lalu mengeksekusi:
```bash
git push origin release/v2.1 --force
```
Dampaknya, 14 commit dari 5 engineer lainnya terhapus dari remote upstream repository, menyebabkan branch lokal anggota tim lainnya mengalami divergensi fatal (*divergent branches*).

* **Pertanyaan Diagnostik:**
  1. Bagaimana cara lead engineer menelusuri riwayat remote audit log (atau memanfaatkan cache commit lokal dari engineer lain) untuk merekonstruksi kembali tip branch `release/v2.1` yang sah?
  2. Perintah apa yang seharusnya digunakan developer jika memang membutuhkan *force-overwrite* secara aman tanpa merusak commit orang lain yang masuk bersamaan (`--force-with-lease`)? Jelaskan mekanisme internal flags tersebut.
  3. Konfigurasi branch protection rule apa yang harus diaktifkan secara permanen di GitHub/GitLab untuk mencegah mitigasi insiden ini di masa depan?

---

### Skenario C: Bottleneck Linting & Pre-commit Hooks pada Monorepo
Sebuah tim frontend mengadopsi monorepo dengan total 15.000 file TypeScript. Lead engineer mengimplementasikan Git Hook via Husky untuk menjalankan audit kualitas:
```json
// package.json (root)
"scripts": {
  "pre-commit": "eslint . && prettier --check ."
}
```
Keluhan serentak muncul dari puluhan engineer: setiap kali melakukan `git commit`, mesin mereka freeze selama 4 menit untuk memvalidasi seluruh codebase, sehingga developer mulai membypass pengujian menggunakan flag `--no-verify`.

* **Pertanyaan Diagnostik:**
  1. Mengapa eksekusi linting menyeluruh pada pre-commit hook merupakan anti-pattern arsitektural pada skala proyek menengah-besar?
  2. Rancang solusi teknis menggunakan kombinasi `lint-staged` dan caching ESLint/Prettier untuk memastikan durasi pre-commit hook terpangkas menjadi di bawah 3 detik.
  3. Bagaimana arsitektur CI/CD harus mengompensasi kemungkinan developer melakukan bypass lokal (`git commit --no-verify`)?

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Zero-Tolerance Tooling & Git Hygiene Pipeline Setup

#### Deskripsi Masalah
Sebuah startup fintech merekrut Anda untuk menata fondasi tooling proyek frontend baru mereka. Saat ini repository mereka mengalami problem kronis: commit message sembarangan (contoh: *"fix bug"*, *"update"*), format kode saling bertubrukan antar-developer (tab vs spasi, semicolon vs non-semicolon), dan kode yang mengandung *syntax error* sering lolos ke remote repository karena tidak ada gatekeeping lokal otomatis.

#### Spesifikasi Requirements
Bangun sebuah blueprint struktur project minimal (menggunakan runtime Node.js LTS) yang mengintegrasikan ekosistem tooling frontend modern dengan ketentuan ketat:

1. **Package Management & Engine Pinning:**
   - Inisialisasi package manager modern (`pnpm` atau `npm`).
   - Kunci versi Node.js menggunakan file `.nvmrc` dan field `"engines"` pada `package.json` secara deterministik.
2. **Standard Linter & Formatter Setup:**
   - Konfigurasi ESLint (Flat Config terbaru atau legacy yang valid) untuk environment modern JavaScript/TypeScript.
   - Konfigurasi Prettier dengan rule eksplisit: `singleQuote: true`, `semi: true`, `trailingComma: "all"`, `tabWidth: 2`.
   - Hilangkan seluruh rule conflict antara ESLint dan Prettier menggunakan `eslint-config-prettier`.
3. **Automated Pre-Commit Validation:**
   - Konfigurasi `husky` untuk mengeksekusi git hook.
   - Integrasikan `lint-staged` sehingga format and lint **hanya** berjalan pada file yang berstatus *staged* (`.js`, `.jsx`, `.ts`, `.tsx`, `.json`, `.css`).
4. **Commit Message Specification (Conventional Commits):**
   - Konfigurasi `@commitlint/cli` dan `@commitlint/config-conventional` menggunakan commit-msg hook di Husky.
   - Hook harus memblokir otomatis commit message yang tidak memenuhi format standar (contoh yang valid: `feat(auth): implement JWT token rotation mechanism`, `fix(ui): resolve layout shift on mobile navbar`).
5. **NPM Automation Scripts:**
   - Sediakan script `npm run format:check`, `npm run format:fix`, `npm run lint`, dan script build stub.

#### Constraints
- Waktu eksekusi commit lokal untuk staged 2 file tidak boleh melebihi **2.5 detik**.
- Seluruh konfigurasi tidak boleh bergantung pada ekstensi VS Code lokal pengembang; validasi wajib berjalan di tingkat OS CLI via terminal shell.
- Repository harus mempertahankan zero-warning policy.

#### Expected Output
1. File konfigurasi: `package.json`, `.nvmrc`, `.prettierrc`, `eslint.config.js` (atau `.eslintrc.js`), `.lintstagedrc` (atau field dalam `package.json`), dan `commitlint.config.js`.
2. Direktori hook: `.husky/pre-commit` dan `.husky/commit-msg` yang executable.
3. Bukti simulasi terminal (log output):
   - Percobaan commit dengan message non-standard (harus ditolak/gagal).
   - Percobaan commit file dengan intentional formatting error (harus diformat otomatis oleh `lint-staged` lalu sukses ter-commit).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mengapa Node.js berfungsi sebagai *host environment* bagi build tools (bundler, transpiler, minifier) dan bukan sekadar runtime backend.
- [ ] Perbedaan deterministik antara `dependencies`, `devDependencies`, dan `peerDependencies`.
- [ ] Cara kerja internal Git berbasis Content-Addressable Storage (SHA hash) dan Directed Acyclic Graph (DAG), bukan sekadar mengingat perintah terminal.
- [ ] Perbedaan operasional dan struktural antara `git merge`, `git merge --squash`, dan `git rebase`.
- [ ] Peran critical `package-lock.json` / `pnpm-lock.yaml` dalam menjamin build idempotency di multi-environment.
- [ ] Alasan Prettier dan ESLint memiliki tanggung jawab domain yang berbeda dalam rekayasa perangkat lunak.

### Saya tidak perlu menghafal:
- [ ] Seluruh flag argumen langka dari perintah kompleks Git (contoh: flag eksperimental pada `git filter-branch` atau `git plumbing commands` tingkat rendah seperti `git mktag`). Cukup pahami *man pages* (`git [command] --help`).
- [ ] Nama seluruh aturan individual rule ESLint (ratusan opsi lint rules). Cukup pahami cara membaca dokumentasi dan mengonfigurasi ruleset rekomendasi (`eslint:recommended`).
- [ ] Algoritma internal hashing SHA-1/SHA-256 yang dieksekusi Git saat mengonversi file menjadi string hash.

### Saya harus bisa melakukan:
- [ ] Menginisialisasi proyek frontend dari awal menggunakan CLI modern (Vite/PNPM) secara mandiri tanpa GUI tools.
- [ ] Mengonfigurasi integrasi *Husky*, *lint-staged*, dan *Commitlint* untuk menegakkan *quality gate* otomatis sebelum kode meninggalkan mesin lokal.
- [ ] Menganalisis, mereproduksi, dan memecahkan merge conflict manual secara terstruktur menggunakan text editor atau CLI.
- [ ] Melakukan operasi penyelamatan commit yang hilang menggunakan `git reflog` dan me-reset state repo secara presisi tanpa merusak data lain.
- [ ] Menulis commit message yang mematuhi spesifikasi *Conventional Commits v1.0.0*.
- [ ] Menjalankan pipeline instalasi deterministik menggunakan `npm ci` atau `pnpm install --frozen-lockfile`.