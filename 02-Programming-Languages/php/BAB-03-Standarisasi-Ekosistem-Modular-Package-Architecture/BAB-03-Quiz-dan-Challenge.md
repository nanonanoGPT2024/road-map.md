# BAB 03: Quiz, Challenge, & Knowledge Check
**Standarisasi Ekosistem & Modular Package Architecture**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Evolusi Standar Autoloading: PSR-0 vs. PSR-4**  
   Analisis perbedaan mekanis dalam resolusi path direktori antara spesifikasi PSR-0 dan PSR-4. Mengapa PSR-4 memangkas redundansi struktur direktori secara signifikan, dan bagaimana perbedaan ini berdampak langsung pada jumlah operasi *system call* I/O (seperti `stat` dan `access`) pada sistem operasi berbasis POSIX ketika mencari file kelas?

2. **Deterministik Dependensi: `composer.json` vs. `composer.lock`**  
   Secara arsitektural, jelaskan siklus hidup resolusi dependensi oleh SAT-based solver pada Composer. Mengapa eksekusi perintah `composer update` sangat dilarang pada environment CI/CD production, dan bagaimana `composer.lock` menjamin integritas kriptografis serta determinisme pohon dependensi lintas environment runtime yang heterogen?

3. **Batasan Semantik Versioning (SemVer) pada Transisi Versi Nol (`0.x.y`)**  
   Spesifikasi SemVer menetapkan bahwa *breaking changes* menaikkan angka MAJOR, fitur backward-compatible menaikkan MINOR, dan bugfix menaikkan PATCH. Namun, apa implikasi matematis dan operasional operator caret (`^`) dan tilde (`~`) pada Composer ketika mengevaluasi package yang masih berada pada versi pra-rilis (`0.y.z`)? Berikan contoh risiko instalasi dependensi tidak stabil akibat kesalahpahaman ini.

4. **Namespace Resolution Engine pada Level Opcode PHP**  
   Bedakan bagaimana Zend Engine menyelesaikan *Unqualified Name*, *Qualified Name*, dan *Fully Qualified Name (FQN)* saat runtime kompilasi AST (Abstract Syntax Tree) ke opcode. Mengapa penambahan prefix backslash (`\`) pada pemanggilan fungsi native global PHP (seperti `\count()` atau `\in_array()`) di dalam namespace lokal dapat mengeliminasi *opcode fallback lookups*?

5. **Pentingnya Abstraksi Melalui PSR-11 (Container) dan PSR-14 (Event Dispatcher)**  
   Dalam merancang reusable package yang agnostik terhadap framework, jelaskan mengapa sebuah package tidak boleh bergantung langsung pada dependensi konkret seperti `Illuminate\Container` atau `Symfony\Component\DependencyInjection`. Bagaimana pengadopsian antarmuka PSR-11 dan PSR-14 memutus *tight-coupling* antar-vendor sekaligus menjaga interoperabilitas tingkat tinggi?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Dinamika Level Optimasi Autoloader Composer**  
   Bandingkan secara komparatif mekanisme kerja dari:
   - Default autoloader (`composer dump-autoload`)
   - Classmap optimization (`-o` / `--optimize`)
   - Authoritative classmap (`-a` / `--classmap-authoritative`)
   - APCu classmap cache (`--apcu`)  
   
   Identifikasi skenario teknis di mana penggunaan flag `--classmap-authoritative` justru menyebabkan aplikasi mengalami fatal error `Class not found` saat runtime.

2. **Resolusi "Diamond Dependency Conflict" dan Namespace Isolation**  
   Package A membutuhkan Package C `^1.0`, sedangkan Package B membutuhkan Package C `^2.0`. Aplikasi utama mengonsumsi Package A dan Package B secara bersamaan.  
   Jelaskan mengapa PHP natively gagal menangani situasi ini secara simultan (ketiadaan *class-loader multiple aliasing*). Bagaimana *tooling* isolasi bytecode seperti `php-scoper` atau `humbug/box` memodifikasi token AST untuk merestrukturisasi namespace pihak ketiga demi menghindari benturan global symbol?

3. **Overhead Memori dan I/O pada Direktif `autoload.files`**  
   Banyak pengembang menggunakan direktif `files` di `composer.json` untuk memuat fungsi utilitas global. Bedakan siklus pemuatan direktif `files` dengan `psr-4` saat worker PHP-FPM menangani *stateless request lifecycle*. Mengapa akumulasi berlebihan dari file-file pembantu yang dimuat via `files` dapat merusak performa *opcache memory footprint* dan memperlambat throughput konkurensi tinggi?

4. **Framework Agnostic Package Discovery & Provider Decoupling**  
   Bagaimana mekanisme internal *package discovery* otomatis yang digunakan oleh ekosistem modern (seperti Laravel `extra.laravel` pada `composer.json`) bekerja di balik layar? Bagaimana Anda menyusun package yang menyediakan integrasi seamless (auto-configure) ke dalam Laravel dan Symfony secara simultan, tanpa mereferensikan dependensi framework tersebut ke dalam blok `require` root package?

5. **Deep Memory Profiling SAT Solver Composer**  
   Saat menjalankan resolusi dependensi pada monorepo raksasa, Composer sering mengalami *Out of Memory* (OOM). Secara algoritma, apa yang menyebabkan kompleksitas komputasi Boolean Satisfiability (SAT) solver melonjak secara eksponensial? Sebutkan perbaikan arsitektural yang diterapkan pada Composer v2 (seperti *metadata on-demand fetching* dan *parallel curl downloads*) yang memitigasi bottleneck ini.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Degradation Akibat Disk I/O Saturation pada Cluster PHP-FPM
Sebuah kluster microservice PHP 8.3 berjalan di Kubernetes menggunakan persistent storage berbasis NFS (Network File System) dengan replikasi multi-pod. Saat traffic melonjak hingga 15.000 RPS, p99 response time membengkak dari 45ms menjadi 1.200ms. Profiling via `strace` pada salah satu worker PHP-FPM menunjukkan jutaan *system call* `stat()` dan `open()` yang mengembalikan nilai `ENOENT (No such file or directory)` berulang kali pada path vendor Composer.

- **Pertanyaan Diagnostik:**
  1. Analisis arsitektur Composer autoloader apa yang menyebabkan banjir `stat()` I/O calls tersebut?
  2. Langkah optimasi autoloader spesifik apa pada tahap build Dockerfile yang wajib dieksekusi untuk mereduksi disk I/O network calls ke titik nol?
  3. Bagaimana OPcache memengaruhi resolusi file ini, dan direktif OPcache apa (`opcache.validate_timestamps`, `opcache.revalidate_freq`, dll.) yang harus dikonfigurasi pada environment tersebut?

### Skenario B: "Ghost Class" Collision Pasca-Canary Deployment
Sebuah tim merekayasa proses modularisasi aplikasi monolit menjadi package internal terpisah (`corp/payment-core`). Package ini dipublikasikan via Private Satis/Packagist. Pada pipeline CI/CD canary release, container pod baru diluncurkan dengan update package `corp/payment-core: 1.4.0`.  
Namun, sejumlah pod secara acak melempar *Fatal Error: Cannot declare class Corp\Payment\Gateway, because the name is already in use*. Masalah ini tidak dapat direproduksi di lokal staging, tetapi terjadi secara sporadis pada 5% request di production.

- **Pertanyaan Diagnostik:**
  1. Identifikasi akar masalah potensial pada struktur namespace, mekanisme class preloading (PHP 8 preloading script), atau symlink deployment release yang memicu deklarasi ganda ini.
  2. Bagaimana modifikasi skrip preloading atau siklus hidup worker PHP-FPM pasca-deployment canary untuk memusnahkan duplikasi symbol di memori bersama (shared memory)?
  3. Prosedur audit dependensi apa yang harus dipasang pada CI pipeline untuk mendeteksi *transitive namespace overlap* sebelum rilis?

### Skenario C: Dilema Arsitektur: Monorepo vs. Multi-Repo Package Decoupling
Perusahaan Anda memiliki 40 layanan microservice dan 15 shared internal libraries (database wrapper, telemetry, auth context, model contracts). Selama ini, shared libraries dipisah ke 15 repository Git berbeda dengan integrasi via Composer version tags.  
Masalah muncul: setiap ada perubahan kecil pada interface core auth, developer harus membuat 15 Pull Request terpisah, menunggu tagging SemVer, dan melakukan update bertingkat (`cascade dependency hell`), yang mengakibatkan rilis tertunda hingga beberapa hari. Tim arsitektur mengajukan migrasi ke arsitektur **Monorepo** yang dikelola via tooling seperti Symplify MonorepoBuilder atau Git Subtree.

- **Pertanyaan Diagnostik:**
  1. Lakukan analisis *trade-off* komparatif: Apa kerugian arsitektural dan operasional (CI caching, deployment blast radius, access control) jika beralih ke Monorepo?
  2. Jika tetap mempertahankan multi-repo, strategi *path repository symlink mapping* dan automated semantic dependency management apa yang dapat meminimalkan friksi development di local environment?
  3. Desain kontrak API package (Interface Segregation Principle) seperti apa yang seharusnya diterapkan agar perubahan implementasi auth tidak merusak kompatibilitas ke-15 consumer packages?

---

## 4. Chapter Challenge

### Tantangan Praktis: Merancang Standalone PSR-Compliant Modular Package dengan Local Classmap Compiler & Fallback Telemetry

#### Problem
Anda ditugaskan merancang sebuah package framework-agnostic berkinerja tinggi bernama `ZeroLatency\Observability`. Package ini harus mencatat metrik internal aplikasi tanpa bergantung pada library vendor besar (seperti Guzzle atau Monolog) secara langsung. Package ini harus mampu diinstal di Laravel, Symfony, atau Native PHP murni dengan overhead instalasi mendekati nol, mematuhi standar PSR terkini, dan menyediakan mekanisme optimasi autoload mandiri saat di-deploy di environment read-only container.

#### Requirements
1. **Struktur Direktori Standar PSR-4:**
   - Package harus memisahkan code implementation (`src/`), test suite (`tests/`), dan integration adapters (`adapters/`).
   - Terapkan pemisahan antarmuka (contracts) murni pada namespace `ZeroLatency\Observability\Contracts`.
2. **Kepatuhan Standar PSR:**
   - Implementasikan listener/dispatcher berbasis **PSR-14 (Event Dispatcher)** murni untuk menangkap trace performance metrics.
   - Sediakan adapter logging berbasis **PSR-3 (Logger Interface)** tanpa mengikat package ke Monolog.
3. **Framework Agnostic Discovery:**
   - Sediakan integrasi zero-config untuk Laravel (via Laravel Package Auto-Discovery pada `composer.json` mengarah ke `ZeroLatency\Observability\Adapters\Laravel\ObservabilityServiceProvider`).
   - Sediakan bundle interface untuk Symfony (`ZeroLatency\Observability\Adapters\Symfony\ObservabilityBundle`).
4. **Custom Autoload Validation Pre-Script:**
   - Buat skrip deployment standalone (`bin/verify-package-integrity.php`) yang memeriksa seluruh file kelas PHP di dalam `src/`, memvalidasi bahwa FQN (Fully Qualified Name) kelas, interface, atau trait sesuai 100% dengan path direktori PSR-4 secara real-time, dan melempar *non-zero exit code* jika ditemukan mismatch case-sensitivity file.

#### Constraints
- Root dependencies (`require` di `composer.json`) hanya boleh berisi:
  - `"php": ">=8.2"`
  - `"psr/event-dispatcher": "^1.0"`
  - `"psr/log": "^3.0"`
- Dilarang keras menaruh framework (`laravel/framework`, `symfony/http-kernel`) pada blok `require`. Framework tersebut hanya boleh berada di `require-dev` atau `suggest`.
- Seluruh codebase wajib memenuhi standar analisis statis PHPStan level 8/Max dan format PSR-12.

#### Expected Output
1. File `composer.json` yang dikonfigurasi sempurna (lengkap dengan autoload, autoload-dev, extra auto-discovery, suggest, dan branch-alias).
2. File interface: `src/Contracts/MetricCollectorInterface.php` dan `src/Contracts/TraceEventInterface.php`.
3. File implementasi event dispatcher PSR-14: `src/EventDispatcher/NativeEventDispatcher.php`.
4. Script audit kepatuhan: `bin/verify-package-integrity.php` yang dapat dieksekusi via CLI (`php bin/verify-package-integrity.php`).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Aturan resolusi namespace internal PHP (Unqualified, Qualified, FQN) dan kaitannya dengan bytecode optimization.
- [ ] Arsitektur internal autoloader Composer dan hierarki pencarian (Classmap, PSR-4, PSR-0, Fallback).
- [ ] Perbedaan fungsional antara `require`, `require-dev`, `suggest`, `replace`, dan `provide` dalam `composer.json`.
- [ ] Mekanisme kerja algoritma SAT solver pada Composer dan mitigasi memory leak/performance bottleneck saat resolving pohon dependensi.
- [ ] Prinsip Semantic Versioning (SemVer) serta pemetaan operator versi Composer (`^`, `~`, wildcard, exact match).
- [ ] Standar fundamental PHP-FIG: PSR-1, PSR-3, PSR-4, PSR-7, PSR-11, PSR-12/PER-CS, PSR-14, dan PSR-17.
- [ ] Konsekuensi operasional pemuatan file autoload terhadap shared memory OPcache dan I/O disk di sistem kontainer.

### Saya tidak perlu menghafal:
- [ ] Daftar lengkap seluruh nomor PSR yang pernah diusulkan (hanya perlu memahami PSR yang berstatus *Accepted* dan dominan di industri).
- [ ] Parameter konfigurasi internal SAT solver Composer (`rules`, `watches`, `decisions` internal state).
- [ ] Seluruh sintaks dan opsi flag baris perintah CLI Composer (cukup kuasai flag inti: `install`, `update`, `dump-autoload`, `--optimize`, `--classmap-authoritative`, `--no-dev`).

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi dan mengoptimalkan performa autoloader Composer untuk skala enterprise production menggunakan `--classmap-authoritative` dan pre-warmed OPcache.
- [ ] Mengisolasi dependensi vendor yang mengalami benturan (diamond dependency) menggunakan toolchain rewrites/namespace scoping.
- [ ] Membangun package modular yang sepenuhnya decoupled (agnostik) dari framework, namun menyediakan integrasi plug-and-play ke ekosistem besar via contract abstractions (PSR).
- [ ] Melakukan debugging dan profiling performa Composer solver menggunakan environmental variables (`COMPOSER_MEMORY_LIMIT`, `-vvv`, `COMPOSER_DEBUG_SRCS`).
- [ ] Menulis custom tooling atau automation script untuk memvalidasi kepatuhan arsitektur modular, integritas autoloading, dan conformance testing terhadap standar PSR.