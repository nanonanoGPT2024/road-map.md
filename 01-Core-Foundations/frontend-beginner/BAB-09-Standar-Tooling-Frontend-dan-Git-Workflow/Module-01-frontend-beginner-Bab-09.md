# BAB 09 MODULE 01: Standar Tooling Frontend Modern, Kontrol Versi & Git

---

## SEKSI 01 — IDENTITAS MODUL

* **Track:** Frontend Development Core
* **Level Kurikulum:** Beginner to Early-Intermediate (`frontend-beginner`)
* **Kategori:** `01-Core-Foundations`
* **Kode Modul:** `FE-FND-0901`
* **Prasyarat:** 
  * `FE-FND-0101` s/d `FE-FND-0801` (HTML5 Semantik, CSS3 Modern, Fundamental JavaScript, DOM Manipulation, & Async JS)
  * Pemahaman dasar penggunaan antarmuka Command Line Interface (CLI/Terminal)
* **Estimasi Waktu Penyelesaian:** 6–8 Jam Belajar Terstruktur (Teori + Hands-on Lab)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini secara tuntas, peserta didik diharapkan mampu:

1. **Menganalisis dan Memilih Ekosistem Package Manager (C4 - Analysis):** Mengidentifikasi perbedaan struktural antara `npm`, `yarn`, dan `pnpm`, serta mengelola dependensi aplikasi menggunakan semantic versioning (`^`, `~`, exact) dan validasi integritas *lockfile*.
2. **Mengonfigurasi Lingkungan Pengembangan Frontend Modern (C3 - Application):** Menginisialisasi proyek berbasis Vite, memahami siklus *Dev Server* berbasis native ES Modules (ESM) versus *Production Bundling* berbasis Rollup/esbuild.
3. **Mengintegrasikan Code Quality Tooling (C3 - Application):** Membangun konfigurasi statis untuk *code linting* dan *code formatting* menggunakan ESLint, Prettier, dan EditorConfig secara harmonis tanpa konflik aturan.
4. **Mengeksekusi Alur Kerja Git Secara Deterministik (C3 - Application):** Mengoperasikan arsitektur tiga level Git (Working Directory, Staging Area, Local Repository) dan remote syncing menggunakan CLI.
5. **Mengelola Strategi Branching dan Menyelesaikan Merge Conflict (C4 - Analysis & C5 - Evaluation):** Mengimplementasikan alur kerja Git Feature Branch, menganalisis divergensi commit history, serta melakukan rekonsiliasi konflik saat operasi `merge` dan `rebase`.
6. **Menerapkan Standar Conventional Commits dan Otomasi Git Hook (C3 - Application):** Menstandarisasi riwayat repositori menggunakan Conventional Commits dan mengintegrasikan Git Hooks berbasis Husky dan lint-staged.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
Ekosistem Tooling Frontend Modern & Git
├── 1. Package Management & Runtimes
│   ├── Node.js / Corepack (Runtime Foundation)
│   ├── Package Managers: npm | yarn | pnpm
│   ├── Manifest & Resolusi: package.json vs Lockfiles (package-lock.json, pnpm-lock.yaml)
│   └── Semantic Versioning (SemVer: MAJOR.MINOR.PATCH)
├── 2. Build Tools & Developer Experience (DX)
│   ├── Evolusi: Manual Script -> Task Runners -> Bundlers (Webpack) -> Native ESM (Vite)
│   ├── Hot Module Replacement (HMR) vs Full Page Reload
│   └── Transpilasi & Kompilasi: esbuild & Rollup
├── 3. Code Quality & Standards Enforcement
│   ├── Linter: ESLint (Abstract Syntax Tree Analysis, Error Prevention)
│   ├── Formatter: Prettier (Stylistic Rules, AST Reparsing)
│   └── Editor-level Sync: .editorconfig
└── 4. Distributed Version Control System (DVCS) — Git
    ├── Model Data Git: Snapshots vs Deltas, Directed Acyclic Graph (DAG)
    ├── Tiga Pohon Git: Working Tree, Index (Staging), Commit History (HEAD)
    ├── Kolaborasi: Remote Branches, Upstream Tracking, Pull Request (PR) Lifecycle
    └── Safety & Integrity: Git Hooks (Husky), Gitignore, dan Rekonsiliasi Konflik
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Pada era awal web development, workflow rekayasa frontend mengandalkan penyertaan file library via elemen `<script src="...">` global dan proses deployment manual melalui FTP. Pendekatan ini memiliki kelemahan kritis:
1. **Pollution Global Scope & Race Conditions:** Urutan pemuatan skrip sangat rapuh. Jika library B bergantung pada library A, kegagalan jaringan pada library A akan merusak seluruh aplikasi.
2. **Ketiadaan Determinisme Versi:** Pembaruan minor pada library pihak ketiga di CDN publik dapat memicu kerusakan (*breaking changes*) di lingkungan produksi tanpa peringatan.
3. **Overhead Kinerja Runtime:** Pengiriman kode mentah tanpa optimasi (*minification*, *tree-shaking*, *dead-code elimination*) membebani alokasi bandwidth dan memori peramban pengguna.
4. **Kolaborasi Tim yang Kaotik:** Tanpa sistem kontrol versi yang ketat, pengembang rentan menimpa pekerjaan satu sama lain (*clobbering*), menyisakan kode usang, dan kehilangan kemampuan pelacakan histori bug (*auditability*).

Standar tooling modern memformalkan rekayasa frontend menjadi disiplin yang terprediksi, terisolasi, dan terotomasi. Penguasaan ekosistem build tools dan Git bukan sekadar aksesoris, melainkan fondasi dasar yang menentukan kelayakan kode untuk beroperasi pada infrastruktur perangkat lunak skala produksi enterprise.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Package Manager & SemVer
* **Package Manager:** Perangkat lunak yang mengotomatisasi instalasi, upgrade, konfigurasi, dan penghapusan paket dependensi kode eksternal.
* **Semantic Versioning (SemVer 2.0.0):** Konvensi penomoran versi tiga digit: `MAJOR.MINOR.PATCH`.
  * `MAJOR`: Perubahan API yang tidak kompatibel dengan versi sebelumnya (*breaking changes*).
  * `MINOR`: Penambahan fungsionalitas baru yang tetap *backward-compatible*.
  * `PATCH`: Perbaikan bug yang *backward-compatible*.
  * Prefiks: `^1.2.3` mengizinkan update minor dan patch (`< 2.0.0`), sedangkan `~1.2.3` hanya mengizinkan update patch (`< 1.3.0`).

### 2. Build Tool Modern (Vite)
* Vite adalah build tool generasi baru yang memanfaatkan ketersediaan modul native JavaScript (Native ESM) di browser. Vite menyediakan server pengembangan lokal dengan kecepatan start nyaris instan dan proses *Hot Module Replacement* (HMR) berkinerja tinggi, didukung oleh *esbuild* (berbasis Go) untuk dependensi pra-bundling, serta Rollup untuk optimasi bundle build produksi akhir.

### 3. ESLint & Prettier
* **ESLint:** Linter kode yang mem-parse kode JavaScript menjadi format *Abstract Syntax Tree* (AST) untuk mendeteksi potensi bug, kebocoran memori, pelanggaran standar keamanan, dan praktik anti-pola.
* **Prettier:** Code formatter berbasis opini (*opinionated*) yang mengabaikan semua styling asli, mem-parse ulang kode menjadi AST, dan mencetaknya kembali dengan aturan styling yang konsisten (panjang baris, tanda kutip, indentasi).

### 4. Git Distributed Version Control System (DVCS)
* Git adalah sistem pelacak perubahan terdistribusi di mana setiap repositori lokal menyimpan histori proyek secara utuh dalam bentuk rantai snapshot objek yang dihubungkan melalui *cryptographic hash* (SHA-1 atau SHA-256).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### Mekanisme Internal Resolusi Dependensi & Lockfile
Ketika Anda mengeksekusi `npm install`, manajer paket membaca manifest `package.json` dan memetakan struktur pohon dependensi (*dependency graph*):
1. **Analisis Graph:** Mengurai seluruh dependensi langsung dan dependensi transitif (dependensi dari dependensi).
2. **Pencocokan Lockfile:** `package-lock.json` bertindak sebagai representasi deterministik dari pohon tersebut. Manajer paket memvalidasi hash integritas kriptografi (`integrity: sha512-...`) untuk menjamin paket yang diunduh tidak terkontaminasi atau mengalami manipulasi transit.
3. **Penyusunan `node_modules`:**
   * **npm/yarn v1:** Menggunakan model *hoisting* (meratakan pohon menjadi datar/flat) untuk meminimalkan duplikasi, tetapi membuka risiko *phantom dependencies* (mengimpor dependensi yang tidak dideklarasikan di `package.json`).
   * **pnpm:** Menggunakan *content-addressable storage* via hard links dan symlinks terisolasi, menghemat kapasitas disk sekaligus mencegah impor paket ilegal secara ketat.

### Mekanisme Cold Start & Hot Module Replacement (HMR) pada Vite
```text
Tradisional (Webpack)           Modern (Vite)
[Entry Point]                  Browser HTTP Request: /src/main.js
     │                                      │
     ▼                                      ▼
[Kompilasi Seluruh Rantai]     Vite Dev Server (Hanya me-resolve file terkait)
     │                                      │
     ▼                                      ▼
[Bundle Memory Ready]          Kompilasi on-the-fly via native ESM
     │                                      │
     ▼                                      ▼
Dev Server Ready               Terkirim instan ke browser
```
1. **Dev Time:** Vite tidak membundel seluruh aplikasi ke dalam satu file memori sebelum dev server siap. Vite langsung mengaktifkan server dan melayani modul secara native via header HTTP `Content-Type: application/javascript`. Browser bertindak sebagai pengurai dependensi modular.
2. **HMR:** Ketika sebuah file diedit, Vite hanya menginvalidasi modul individual tersebut dalam graf dependensi dan mengirim pembaruan via WebSocket ke browser tanpa mereset total state aplikasi.

### Arsitektur Objek Kriptografis Git
Git tidak menyimpan perubahan baris (*diff*), melainkan rangkaian *snapshot* berbasis konten:
* **Blob (Binary Large Object):** Menyimpan murni konten file (tanpa metadata izin/nama file).
* **Tree:** Representasi direktori. Berisi referensi ke Blob (beserta nama file dan mode izinnya) atau referensi ke Tree lain (sub-direktori).
* **Commit:** Mengikat Tree akar (*root tree*), metadata pembuat (author), stempel waktu, commit induk (*parent commit SHA*), dan pesan commit.

Saat Anda memindahkan file dari Working Directory ke Index (`git add`), Git menghitung hash SHA konten, menulis objek blob ke direktori terkompresi `.git/objects/`, dan memperbarui file `.git/index`.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. State Transition Pipeline Git
```text
+-------------------+       git add       +------------------+     git commit     +-------------------+
|                   | ------------------> |                  | -----------------> |                   |
| Working Directory |                     |  Staging Area    |                    |  Local Repository |
| (Modified Files)  | <------------------ |     (Index)      | <----------------- |      (HEAD)       |
+-------------------+   git restore .     +------------------+    git reset/      +-------------------+
        |               git checkout --            |              git restore              |
        |                                          |              --staged                 |
        |                                          |                                       |
        |                                          | git diff --staged                     | git push
        | git diff                                 v                                       v
        +-----------------------------------> [Analisis Log / Diff]               +-------------------+
                                                                                  | Remote Repository |
                                                                                  | (GitHub/GitLab)   |
                                                                                  +-------------------+
                                                                                           |
                                                                                           | git fetch /
                                                                                           | git pull
                                                                                           v
                                                                                  +-------------------+
                                                                                  | Tracking Branch   |
                                                                                  | (origin/main)     |
                                                                                  +-------------------+
```

### 2. Directed Acyclic Graph (DAG): Git Branching, Merge vs. Rebase
```text
Kondisi Awal:
       (commit C1) ─── (commit C2) ─── (commit C3) [main]
                                └─── (commit F1) ─── (commit F2) [feature]

Pilihan 1: Fast-Forward Merge (Jika main tidak memiliki commit baru):
       (commit C1) ─── (commit C2) ─── (commit F1) ─── (commit F2) [main, feature]

Pilihan 2: 3-Way Merge (Jika main berkembang paralel dengan commit C4):
       (commit C1) ─── (commit C2) ─── (commit C3) ─── (commit C4) ─────────── (Merge Commit M1) [main]
                                └─── (commit F1) ─── (commit F2) ──────────┘ [feature]

Pilihan 3: Rebase feature onto main (Linear History):
       (commit C1) ─── (commit C2) ─── (commit C3) ─── (commit C4) [main]
                                                               └─── (commit F1') ─── (commit F2') [feature]
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Menyiapkan repositori lokal, mengabaikan artefak sistem/eksternal via `.gitignore`, dan melakukan commit atomik pertama melalui antarmuka terminal.

### 1. Navigasi & Inisialisasi Repositori
```bash
mkdir simple-frontend-app
cd simple-frontend-app
git init
```
*Output Terminal:*
```text
Initialized empty Git repository in /Users/engineer/simple-frontend-app/.git/
```

### 2. Deklarasi `.gitignore`
Sangat fatal memasukkan file dependensi dan cache lokal ke repositori kontrol versi. Buat file `.gitignore`:
```text
# Dependencies
node_modules/
.pnp
.pnp.js

# Testing and coverage
coverage/

# Production build artifacts
dist/
build/

# Environment Variables (PENTING: Jangan bocorkan secrets)
.env
.env.local
.env.*.local

# Operating System specific files
.DS_Store
Thumbs.db

# IDE / Editor logs and configurations
.idea/
.vscode/*
!.vscode/extensions.json
!.vscode/settings.json
npm-debug.log*
yarn-debug.log*
yarn-error.log*
```

### 3. Operasi Commit Pertama
```bash
echo "# Simple Frontend Project" > README.md
git status
```
*Output:*
```text
On branch main

No commits yet

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	.gitignore
	README.md

nothing added to commit but untracked files present (use "git add" to track)
```

Tambahkan file ke staging area secara selektif, lalu rekam snapshot:
```bash
git add .gitignore README.md
git commit -m "chore: initial project scaffolding with gitignore and readme"
```

Verifikasi struktur log Git:
```bash
git log --oneline
```
*Output:*
```text
a1b2c3d (HEAD -> main) chore: initial project scaffolding with gitignore and readme
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kita akan membangun pipeline setup proyek frontend modern menggunakan Vite, ESLint, Prettier, dan Husky untuk menegakkan aturan kode sebelum commit diizinkan.

### 1. Inisialisasi Proyek dengan Vite (Vanilla JavaScript)
Jalankan scaffold CLI:
```bash
npm create vite@latest modern-tooling-app -- --template vanilla
cd modern-tooling-app
npm install
```

### 2. Instalasi Tooling Kualitas Kode (DevDependencies)
Instal ESLint, Prettier, resolver konfigurasi, serta hook git:
```bash
npm install -D prettier eslint @eslint/js globals eslint-config-prettier husky lint-staged
```

### 3. Konfigurasi Prettier (`.prettierrc.json`)
Buat file `.prettierrc.json` di root direktori:
```json
{
  "semi": true,
  "singleQuote": true,
  "tabWidth": 2,
  "trailingComma": "es5",
  "printWidth": 100,
  "bracketSpacing": true,
  "arrowParens": "avoid"
}
```

Buat juga file `.prettierignore` untuk mencegah pemformatan berulang pada bundel:
```text
dist/
node_modules/
package-lock.json
```

### 4. Konfigurasi ESLint Flat Config (`eslint.config.js`)
Konfigurasikan ESLint v9 Flat Config yang modern:
```javascript
import js from '@eslint/js';
import globals from 'globals';
import prettierConfig from 'eslint-config-prettier';

export default [
  js.configs.recommended,
  prettierConfig, // Mematikan seluruh rule ESLint yang bentrok dengan Prettier
  {
    files: ['**/*.js'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.es2021,
      },
    },
    rules: {
      'no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      'no-console': ['warn', { allow: ['warn', 'error'] }],
      'eqeqeq': ['error', 'always'],
      'prefer-const': 'error',
    },
  },
];
```

### 5. Konfigurasi `package.json`
Perbarui file `package.json` untuk meregistrasikan script eksekusi dan integrasi `lint-staged`:
```json
{
  "name": "modern-tooling-app",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "lint": "eslint .",
    "lint:fix": "eslint . --fix",
    "format": "prettier --write .",
    "format:check": "prettier --check .",
    "prepare": "husky"
  },
  "lint-staged": {
    "*.js": [
      "eslint --fix",
      "prettier --write"
    ],
    "*.{json,css,md,html}": [
      "prettier --write"
    ]
  },
  "devDependencies": {
    "@eslint/js": "^9.15.0",
    "eslint": "^9.15.0",
    "eslint-config-prettier": "^9.1.0",
    "globals": "^15.12.0",
    "husky": "^9.1.7",
    "lint-staged": "^15.2.10",
    "prettier": "^3.3.3",
    "vite": "^6.0.1"
  }
}
```

### 6. Otomasi Pre-Commit Hook via Husky
Inisialisasi direktori hook Husky:
```bash
npx husky init
```
Edit file `.husky/pre-commit` menjadi:
```bash
npx lint-staged
```

### 7. Uji Mutasi Kode & Validasi Otomasi
Buat file JavaScript yang sengaja melanggar aturan di `src/app.js`:
```javascript
// Variable kotor dan unused
var invalidVar = "Hello World";
let equalityViolation = (1 == "1");

export function computeData(a, b) {
    console.log("Menghitung data...");
      return a+b;
}
```

Uji eksekusi stage dan commit:
```bash
git add src/app.js
git commit -m "feat: add app compute module"
```

*Respon Konsol Otomatis:*
ESLint akan langsung mencegat eksekusi commit, mendeteksi penggunaan `var`, pelanggaran operator `==` (harus `===`), serta variabel yang tidak digunakan:
```text
✖ eslint --fix:
/Users/engineer/modern-tooling-app/src/app.js
  2:5   error  'invalidVar' is assigned a value but never used  no-unused-vars
  3:25  error  Expected '===' and instead saw '=='              eqeqeq

husky - pre-commit hook exited with code 1 (error)
```
Commit dibatalkan otomatis oleh sistem sebelum kode rusak sempat masuk ke riwayat branch.

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Aspek / Domain | Pilihan A | Pilihan B | Trade-off & Pertimbangan Teknis |
| :--- | :--- | :--- | :--- |
| **Package Manager** | **npm (Default Node)** | **pnpm (Hard link store)** | `npm` didukung out-of-the-box tanpa dependensi tambahan; namun boros ruang disk dan berisiko *phantom dependencies*. `pnpm` luar biasa cepat dan efisien dalam alokasi storage monorepo, tetapi struktur direktori *nested* virtual `node_modules`-nya sesekali membuat tooling lama yang mengasumsikan pola *hoisting* menjadi bingung. |
| **Dev Server Build Tool** | **Vite (Native ESM)** | **Webpack (Bundler-based)** | `Vite` memiliki kecepatan cold-start dan HMR berorde milidetik tanpa peduli skala proyek; namun untuk aplikasi enterprise lawas dengan sistem modul CommonJS masif atau manipulasi bundle AST custom rumit, ekosistem plugin Webpack masih jauh lebih matang. |
| **Git Synchronization** | **Merge (`git merge`)** | **Rebase (`git rebase`)** | `git merge` mempertahankan keaslian sejarah riwayat mutasi (*historical truth*) secara utuh termasuk timestamp eksplisit cabang; namun menghasilkan *graph topology* kusut penuh commit merge redundan. `git rebase` menghasilkan linear history yang bersih untuk CI/CD traversal; namun berisiko merekayasa ulang sejarah dan sangat berbahaya jika dijalankan pada *public branch*. |
| **Linting vs Formatting** | **ESLint Monolitik (All-in-one)** | **ESLint + Prettier Terpisah** | Menyerahkan aturan format ke ESLint (via aturan indent, quotes) mengurangi dependensi package; namun ESLint secara komputasi jauh lebih lambat dalam memformat styling dibanding Prettier dan sering menghasilkan loop peringatan yang tidak perlu. Pemisahan peran adalah standar industri modern. |

---

## SEKSI 11 — BEST PRACTICES

### 1. Disiplin Semantic Versioning & Lockfiles
* **Jangan Ubah Lockfile Manual:** File `package-lock.json` atau `pnpm-lock.yaml` dihasilkan oleh mesin. Dilarang keras melakukan manipulasi teks manual untuk menyelesaikan merge conflict pada lockfile.
* **Instalasi Deterministik di CI/CD:** Selalu gunakan perintah `npm ci` (Clean Install), bukan `npm install` pada server build pipeline. `npm ci` menghapus `node_modules` lokal dan memvalidasi kode tepat berdasarkan `package-lock.json`. Jika ada desinkronisasi dengan `package.json`, proses build akan langsung digagalkan demi alasan integritas.

### 2. Standarisasi Pesan Commit (Conventional Commits 1.0.0)
Format commit harus mematuhi struktur struktural:
```text
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```
* **Daftar Type Inti:**
  * `feat`: Fitur baru untuk pengguna aplikasi.
  * `fix`: Perbaikan bug produksi.
  * `refactor`: Restrukturisasi kode tanpa mengubah fungsionalitas eksternal.
  * `perf`: Optimalisasi performa komputasi atau render.
  * `docs`: Pembaruan dokumentasi semata.
  * `test`: Penambahan atau perbaikan unit test/integration test.
  * `chore`: Tugas rutin pemeliharaan konfigurasi, dependensi, atau build tool.

### 3. Git Hygiene
* **Commit Atomik:** Satu commit harus mencakup satu representasi unit kerja logis. Jangan menggabungkan refaktor sistem login dengan pembaruan styling tombol footer ke dalam satu commit raksasa.
* **Gunakan Proteksi Push:** Hindari `git push --force`. Jika sejarah branch feature Anda direbase dan memerlukan rewrite pada remote branch pribadi, biasakan selalu menggunakan:
  ```bash
  git push --force-with-lease
  ```
  Ini mencegah Anda menimpa commit rekan kerja yang di-push tanpa sepengetahuan Anda.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Memasukkan Direktori `node_modules` ke Repositori Git
* **Gejala:** Ukuran repositori membengkak hingga ratusan megabyte, proses `git clone` memakan waktu ekstrem, dan merge commit antar pengembang menjadi destruktif.
* **Solusi Root-Cause:** Segera tambahkan `node_modules/` ke file `.gitignore`. Jika folder terlanjur ter-track, hapus metadata dari git cache tanpa menghapus file lokal:
  ```bash
  git rm -r --cached node_modules
  git commit -m "chore: stop tracking node_modules directory"
  ```

### 2. Membocorkan Environment Variables (`.env`)
* **Gejala:** Kunci API (API Key), database secret, atau token autentikasi pihak ketiga terunggah ke platform hosting publik (GitHub/GitLab).
* **Solusi & Mitigasi:** File `.env` wajib berada di baris pertama `.gitignore`. Gunakan file template pendamping bernama `.env.example` yang hanya mendokumentasikan skema *key* tanpa nilai aktual:
  ```text
  # .env.example
  VITE_API_BASE_URL=https://api.example.com/v1
  VITE_ANALYTICS_KEY=
  ```
  *Peringatan:* Jika rahasia sudah ter-push ke GitHub, kunci tersebut harus segera dianggap kompromistis (*compromised*) dan di-revoke (ditarik) secara langsung dari penyedia layanan bersangkutan.

### 3. Menghapus Perubahan Menggunakan `git clean` atau `git reset --hard` Secara Ceroboh
* **Gejala:** Kode yang belum di-commit hilang permanen dari disk lokal.
* **Pencegahan:** Sebelum mengeksekusi perintah destruktif, manfaatkan Git Stash untuk menyimpan pekerjaan sementara di area cadangan aman:
  ```bash
  git stash push -m "WIP: eksperimen logika sorting belum selesai"
  # Kembali ke status bersih dengan aman
  # Jika ingin memulihkan kembali nantinya:
  git stash pop
  ```

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Lab 1: Resolusi Merge Conflict Tingkat Dasar (Guided)
1. Buat folder baru, inisialisasi Git:
   ```bash
   mkdir git-conflict-lab && cd git-conflict-lab
   git init
   ```
2. Buat file `data.txt` berisi:
   ```text
   Baris 1: Core Foundation
   Baris 2: Original Text
   ```
   Lakukan commit ke branch default:
   ```bash
   git add data.txt
   git commit -m "chore: initial commit on main"
   ```
3. Buat branch baru `feature-patch` dan ubah file tersebut:
   ```bash
   git checkout -b feature-patch
   ```
   Ubah baris ke-2 menjadi: `Baris 2: Text dimodifikasi oleh feature-patch`.
   Lalu commit:
   ```bash
   git commit -am "fix: alter line 2 in feature branch"
   ```
4. Pindah kembali ke branch `main`, ubah baris yang sama dengan isi berbeda:
   ```bash
   git checkout main
   ```
   Ubah baris ke-2 menjadi: `Baris 2: Text dimodifikasi langsung di main`.
   Lalu commit:
   ```bash
   git commit -am "fix: alter line 2 directly on main"
   ```
5. Lakukan merge untuk memicu konflik:
   ```bash
   git merge feature-patch
   ```
   *Output CLI:*
   ```text
   Auto-merging data.txt
   CONFLICT (content): Merge conflict in data.txt
   Automatic merge failed; fix conflicts and then commit the result.
   ```
6. **Tugas Anda:** Buka `data.txt`. Analisis penanda konflik Git:
   ```text
   Baris 1: Core Foundation
   <<<<<<< HEAD
   Baris 2: Text dimodifikasi langsung di main
   =======
   Baris 2: Text dimodifikasi oleh feature-patch
   >>>>>>> feature-patch
   ```
   Selesaikan konflik secara manual dengan menggabungkan kedua intensi, hapus marker `<<<<<<<`, `=======`, dan `>>>>>>>`, simpan file, lalu jalankan `git add data.txt` dan `git commit -m "merge: resolve text collision between main and feature-patch"`.

---

### Lab 2: Setup Enterprise Tooling Scaffolding (Unguided)
Buktikan kapabilitas rekayasa Anda secara mandiri:
1. Buat direktori proyek baru bernama `enterprise-scaffold`.
2. Inisialisasi proyek Node.js secara manual (`npm init -y`).
3. Konfigurasikan file `.gitignore` standar industri secara komprehensif.
4. Pasang `vite`, buat file `index.html` dan `src/main.js`. Pastikan skrip `npm run dev` dapat menjalankan server lokal Vite.
5. Konfigurasikan ESLint v9 dan Prettier. Pastikan bahwa:
   * String harus menggunakan *single-quote* (`'`).
   * Titik koma (*semicolon*) diwajibkan di setiap akhir baris instruksi statement.
   * Muncul error linter jika ada variabel yang dideklarasikan menggunakan kata kunci `var`.
6. Tulis script pada `package.json` bernama `"check:all"` yang mengeksekusi format check Prettier dan eksekusi ESLint secara berurutan.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan-pertanyaan berikut untuk mengevaluasi pemahaman konseptual dan teknis Anda:

1. **Apa fungsi utama dari atribut `integrity` berbasis hash SHA pada file `package-lock.json`?**
   * A. Mempercepat proses kompresi zip paket saat diunduh.
   * B. Memastikan paket yang diunduh dari registry tidak mengalami korupsi data atau injeksi skrip jahat (*man-in-the-middle*).
   * C. Menandai arsitektur sistem operasi target (Windows/Linux/macOS).
   * D. Menghubungkan paket secara otomatis ke repositori GitHub pembuatnya.

2. **Perhatikan rentang versi dependensi berikut di `package.json`: `"lodash": "^4.17.21"`. Versi manakah yang TIDAK AKAN PERNAH diinstal secara otomatis oleh `npm update`?**
   * A. `4.17.22`
   * B. `4.18.0`
   * C. `4.19.1`
   * D. `5.0.0`

3. **Perintah Git manakah yang digunakan untuk membatalkan berkas yang sudah masuk ke *Staging Area* agar kembali ke status *Modified Unstaged* tanpa menghilangkan perubahan baris kode?**
   * A. `git checkout -- <file>`
   * B. `git restore --staged <file>`
   * C. `git rm -f <file>`
   * D. `git clean -fd`

4. **Bagaimana mekanisme Vite mencapai status "Instant Server Start" jika dibandingkan dengan webpack pada proyek skala besar?**
   * Mengapa bundler konvensional harus melakukan traversi seluruh pohon dependensi sebelum port lokal dibuka, dan bagaimana native ESM di browser modern memecahkan inefisiensi tersebut? Jelaskan alur transfer datanya secara ringkas!

---

### Kunci Jawaban & Evaluasi

* **Jawaban Soal 1: B.** Hash integritas kriptografis berfungsi sebagai verifikasi mutlak bahwa paket biner/arsip yang diunduh persis sama dengan apa yang pertama kali diresolusi oleh manajer paket, mencegah serangan *package tampering* di jaringan.
* **Jawaban Soal 2: D.** Tanda sisipan (*caret* `^`) membatasi update hanya pada level kompatibilitas *minor* dan *patch* di dalam angka *major* yang sama (`< 5.0.0`). Versi `5.0.0` adalah *breaking change* dan diblokir secara otomatis oleh aturan SemVer ini.
* **Jawaban Soal 3: B.** `git restore --staged <file>` (atau `git reset HEAD <file>` pada Git lawas) melepas snapshot file dari indeks memori staging area tanpa menyentuh kode aktual di working directory Anda. Perintah `git checkout -- <file>` atau `git restore <file>` justru akan menghapus modifikasi kerja Anda.
* **Jawaban Soal 4 (Evaluasi Konseptual):** Webpack harus merayapi, mem-parse, mentranspilasi, dan menggabungkan (*bundle*) seluruh modul ke dalam memori sebelum server siap menerima request HTTP. Vite sebaliknya: server langsung menyala instan tanpa bundling awal; ketika browser meminta file `index.html` yang merujuk ke modul JavaScript, browser modern mengirimkan *HTTP Request* modul secara native (`import`). Vite hanya mengompilasi dan mentransformasi modul tunggal yang diminta browser tersebut secara tepat-waktu (*on-demand compilation*).

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Dokumentasi Resmi Git (Pro Git Book oleh Scott Chacon & Ben Straub):** Bacaan wajib arsitektur internal Git. [git-scm.com/book/en/v2](https://git-scm.com/book/en/v2)
* **Dokumentasi Arsitektur Vite:** Memahami esbuild pre-bundling dan Native ESM HMR. [vite.dev/guide/why.html](https://vite.dev/guide/why.html)
* **Spesifikasi Semantic Versioning 2.0.0:** Pemahaman mendalam aturan format versi. [semver.org](https://semver.org/)
* **ESLint Configuration Guide (Flat Config):** Paradigma konfigurasi statis modern JavaScript. [eslint.org/docs/latest/use/configure/configuration-files](https://eslint.org/docs/latest/use/configure/configuration-files)
* **Conventional Commits Standard:** Standarisasi riwayat perpesanan Git mesin dan manusia. [conventionalcommits.org](https://www.conventionalcommits.org/)

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. Rekayasa frontend modern bertumpu pada runtime Node.js dan manajer paket (`npm`, `pnpm`) yang menggunakan prinsip Semantic Versioning (`MAJOR.MINOR.PATCH`) untuk memastikan keteraturan dependensi eksternal.
2. File `package-lock.json` adalah instrumen mutlak penjamin determinisme instalasi dependensi antar mesin pengembang dan server CI/CD.
3. Vite mendisrupsi paradigma bundler tradisional dengan memanfaatkan Native ES Modules via browser runtime untuk lingkungan development, menghasilkan kecepatan startup dan HMR yang konsisten terlepas dari ukuran aplikasi.
4. Linter (ESLint) bertugas menemukan kesalahan logika dan potensi cacat operasional pada kode (analisis AST), sedangkan Formatter (Prettier) bertugas menyeragamkan aspek estetika visual tata letak kode. Keduanya diintegrasikan secara otomatis pada staging area via Git hooks (Husky & lint-staged).
5. Git merekam snapshot berbasis konten hash kriptografis yang dikelola dalam struktur *Directed Acyclic Graph* (DAG). Penguasaan transisi state dari Working Directory $\rightarrow$ Staging Area $\rightarrow$ Commit History $\rightarrow$ Remote Server adalah prasyarat fundamental kolaborasi software engineering skala profesional.

---

## SEKSI 17 — GLOSARIUM

* **AST (Abstract Syntax Tree):** Representasi struktur data hierarkis berbentuk pohon dari kode sumber bahasa pemrograman yang dihasilkan oleh parser agar kode dapat dianalisis dan dimanipulasi secara programatik.
* **DAG (Directed Acyclic Graph):** Struktur data graf berarah tanpa siklus tertutup; model matematis yang mendasari silsilah hubungan commit pada Git.
* **HMR (Hot Module Replacement):** Mekanisme injeksi, penambahan, atau penghapusan modul kode saat aplikasi sedang berjalan di browser tanpa me-refresh seluruh halaman, mempertahankan state runtime aplikasi.
* **Hoisting (Dependensi):** Teknik optimasi manajer paket untuk mengangkat dependensi bersarang ke tingkat akar `node_modules` demi menghindari duplikasi paket identik.
* **Linting:** Proses analisis statis otomatis terhadap kode sumber untuk mendeteksi bug potensial, kesalahan sintaksis, atau pelanggaran gaya penulisan tanpa mengeksekusi program tersebut.
* **Native ESM (ECMAScript Modules):** Standar resmi JavaScript modular berbasis kata kunci `import` dan `export` yang dieksekusi langsung oleh engine peramban tanpa harus dibundel terlebih dahulu.
* **Rebase:** Operasi Git yang memindahkan atau menerapkan kembali urutan basis commit dari satu cabang ke cabang lain untuk menciptakan riwayat histori linier.
* **Tree Shaking:** Istilah dalam ekosistem JavaScript bundler untuk proses eliminasi dead-code (kode yang tidak pernah dipanggil/dieksekusi) dari bundel produksi akhir guna mereduksi ukuran file.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Peringatan Pedagogis:** Siswa pemula sering kali terjebak dalam kebingungan konseptual antara Git (sistem lokal) dan GitHub (layanan hosting cloud). Tekankan secara berulang bahwa Git beroperasi 100% secara fungsional di mesin lokal tanpa koneksi internet sama sekali.
* **Koreksi Miskonsepsi ESLint vs Prettier:** Siswa pemula sering bingung mengapa mereka membutuhkan keduanya. Analogi yang efektif: *“ESLint adalah editor tata bahasa dan struktur logika esai (mencegah kalimat rancu/salah argumen), sedangkan Prettier adalah juru ketik yang memastikan margin kertas, spasi paragraf, dan ukuran font rapi seragam.”*
* **Sesi Live Coding Wajib:** Jangan hanya memperlihatkan merge yang berhasil mulus. Instruktur **wajib** melakukan demonstrasi langsung memicu merge conflict di terminal, membaca marker konflik bersama kelas, menyelesaikannya secara manual, dan menjelaskan arti dari `HEAD` versus cabang target.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi:** 1.0.0
* **Tanggal Rilis:** 2025-01-15
* **Author:** Tim Kurikulum Rekayasa Frontend Modern
* **Catatan Perubahan:**
  * Inisialisasi rilis modul tooling standar.
  * Standardisasi panduan konfigurasi ke ESLint v9 Flat Config (`eslint.config.js`).
  * Integrasi pipeline otomasi Git Hooks berbasis Husky v9 dan lint-staged v15.
  * Penyusunan modul arsitektur internal Git (Blob, Tree, Commit Hash) dan mitigasi merge conflict.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `FE-FND-0801` — Asynchronous JavaScript: Promises, Fetch API, dan Async/Await
* **Modul Berikutnya:** `FE-FND-0902` — Modularisasi JavaScript Lanjut: ES Modules, Dynamic Imports, dan Build-Optimization
* **Indeks Modul:** Modul 01 dari Bab 09 (Standar Tooling Frontend Modern, Kontrol Versi & Git) pada Jalur Keahlian *Core Foundations*.