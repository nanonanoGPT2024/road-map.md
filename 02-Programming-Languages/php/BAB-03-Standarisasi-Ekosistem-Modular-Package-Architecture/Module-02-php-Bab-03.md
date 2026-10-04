# BAB 03: Standarisasi Ekosistem & Modular Package Architecture
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengonstruksi arsitektur *Enterprise Modular Monolith* dan *Multi-Package Ecosystem* menggunakan Composer secara native dan deterministik.
- Membedah dan mengoptimalkan mekanisme internal Composer Autoloader (Classmap Generation, Static Class Maps, APCu Caching, dan Bytecode Cache).
- Merancang serta merilis *Private Package Registry* berbasis internal Satis / Private Packagist dengan otentikasi zero-trust token.
- Mengembangkan *Custom Composer Plugin* untuk validasi arsitektural dan manipulasi runtime event hook saat dependensi diresolusi.
- Mengelola dependensi monorepo terdistribusi via *Path Repositories* tanpa memicu *dependency hell* atau *circular reference*.
- Mengimplementasikan isolasi dependensi tingkat lanjut (Dependency Scoping) menggunakan tools seperti PHP-Scoper untuk mencegah konflik vendor upstream.

---

### 2. Prerequisite

Peserta wajib menguasai:
- **PHP 8.2/8.3 Core:** Enums, Readonly Classes, Attributes, Typesystem strict (`declare(strict_types=1)`).
- **Composer Basics:** Operasi `composer.json`, `composer.lock`, semantic versioning constraints (`^`, `~`, exact pinned versions).
- **PSR Standar:** PSR-4 (Autoloading), PSR-7/PSR-17 (HTTP Factory/Messages), PSR-11 (Container), PSR-14 (Event Dispatcher).
- **Tooling:** Docker, Linux CLI environment (Bash), Git flow level enterprise.

---

### 3. Concept & Internal Architecture

#### A. Composer SAT Solving Engine & Autoloading Internals
Composer tidak bekerja dengan resolusi graf dependensi linier. Composer menggunakan implementasi algoritma **Boolean Satisfiability Problem (SAT Solver)** berbasis solver *glucose* (via package `composer/semver` dan library `composer/composer` core SAT package).

```
   [ composer.json Dependencies ] 
                 │
                 ▼
     [ Pool Builder (Repo/Cache) ] ──> Mengumpulkan kandidat paket & metadata
                 │
                 ▼
      [ SAT Solver (Glucose) ]   ──> Mengonversi relasi versi ke klausa logika CNF
                 │                     (Conjunctive Normal Form)
                 ▼
       [ Transaction Plan ]     ──> Ekstraksi list operasi: install, update, remove
                 │
                 ▼
   [ Download / Extraction ]
                 │
                 ▼
 [ Generator: classmap / autoload ]
```

Pada fase Autoloading:
1. **Unoptimized Autoload (Development):** Composer mendaftarkan instance `Composer\Autoload\ClassLoader`. Saat class `Vendor\Domain\Entity` dipanggil, classloader melakukan traversi filesystem `file_exists()` linear berdasarkan array prefix namespace di `autoload_psr4.php`. I/O disk sangat intensif.
2. **Optimized Autoload Level 1 (`-o` / `--optimize-autoloader`):** Mengonversi class PSR-4/PSR-0 menjadi array hash map statis di `autoload_classmap.php`. Kompleksitas pencarian turun dari $O(N)$ filesystem checks menjadi $O(1)$ array key lookup.
3. **Classmap Authoritative (`-a` / `--classmap-authoritative`):** Jika sebuah class tidak ditemukan di dalam `autoload_classmap.php`, autoloader langsung melempar error tanpa fallback mengecek filesystem melalui aturan PSR-4. Ini menghentikan system call `lstat()` atau `open()` pada path yang tidak eksis.
4. **APCu Cache Integration (`--apcu`):** Menyimpan cache hit dan cache miss dari pencarian class ke dalam memori bersama (Shared Memory via APCu extension). Mengeliminasi kalkulasi array PHP di level process worker.

#### B. Modular Package Architecture & Decoupling Strategy
Pada skala enterprise, monolit raksasa dipecah menjadi modul independen. Pola arsitektur yang diterapkan:
- **Contract Package (Zero-Dependency):** Hanya berisi Interface, DTO, dan Enums. Bebas dari implementasi framework pihak ketiga (Laravel, Symfony).
- **Core Implementation Package:** Bergantung hanya pada Contract Package.
- **Infrastructure Adapter Package:** Mengikat implementasi ke driver tertentu (e.g., Doctrine, AWS SDK, Redis).

```
               ┌───────────────────────────┐
               │    Domain Contract (Pkg)  │
               │  - Repositories (Interface)│
               │  - Messages / Events      │
               └─────────────▲─────────────┘
                             │
            ┌────────────────┴────────────────┐
            │                                 │
┌───────────┴─────────────┐       ┌───────────┴─────────────┐
│  Core Domain Logic (Pkg)│       │ Infrastructure-AWS (Pkg)│
│  - Services             │       │ - SQS Queue Adapter     │
│  - Aggregate Roots      │       │ - S3 Storage Adapter    │
└─────────────────────────┘       └─────────────────────────┘
```

---

### 4. Why & What

| Dimensi | Mengapa Dibutuhkan (Why) | Apa Karakteristiknya (What) |
| :--- | :--- | :--- |
| **Monorepo Path Repos** | Mengurangi friksi integrasi multi-repo dan sinkronisasi cross-package versioning pada fase active development. | Menggunakan skema `"type": "path"` pada composer.json yang me-link direktori lokal secara symlink tanpa publish ke remote. |
| **Custom Composer Plugins** | Menjaga governance arsitektur (misal: memblokir instalasi paket berlisensi non-komersial atau melarang instalasi dependensi tanpa signature valid). | Package PHP bertipe `composer-plugin` yang mengimplementasikan `PluginInterface` dan berlangganan ke event lifecycle Composer. |
| **Dependency Scoping** | Mencegah konflik versi transitif (misal: Package A butuh Guzzle 6, Host Monolith butuh Guzzle 7). | Menggunakan automasi rewrites (namespace prefixing) pada level AST untuk memindahkan seluruh dependensi internal ke vendor namespace unik. |

---

### 5. How (Workflow Detail)

#### Workflow Produksi: Private Monorepo ke Standalone Package via Subtree & Satis
1. **Arsitektur Monorepo:** Seluruh paket internal diletakkan di bawah direktori `packages/`.
2. **Local Linking:** Root `composer.json` mengarahkan repositori ke `packages/*` menggunakan symlink aktif (`"options": {"symlink": true}`).
3. **Continuous Integration (CI):** 
   - Step 1: Jalankan static analysis across modules (`phpstan analyse`).
   - Step 2: Validasi kepatuhan Composer (`composer validate --strict`).
   - Step 3: Git Subtree Splitter mendistribusikan direktori `packages/<pkg-name>` ke remote git repository independen (misal: `github.com/enterprise-org/pkg-payment-contract.git`).
4. **Distribution Pipeline:** 
   - Webhook mentrigger internal **Satis** instance.
   - Satis me-rebuild metadata index `packages.json`.
   - Artifact static disajikan melalui secure Nginx server di balik VPN/VPC internal.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Pelabuhan Kontainer vs Sistem Pengiriman Barang Manual
- **Unoptimized PSR-4:** Kurir mencari alamat rumah satu per satu secara acak di seluruh kota setiap kali ada pesanan barang (I/O disk berulang kali memeriksa file di disk).
- **Authoritative Classmap:** Buku register manifest kontainer kargo di pelabuhan. Setiap nomor kontainer sudah terpetakan persis ke koordinat dermaga (Slot A-1, Rak 3). Jika nomor kontainer tidak ada di buku manifest, kapal langsung ditolak masuk dermaga tanpa harus menyisir gudang.

```
+---------------------------------------------------------------------------------------+
|                                RUNTIME AUTOLOAD SEQUENCE                              |
+---------------------------------------------------------------------------------------+
  Application Code
        │
        │ [1] new \Enterprise\Billing\InvoiceService()
        ▼
  +────────────────────────────────────────────────────────+
  | Composer Autoloader Engine                             |
  |                                                        |
  |   +--------------------------------------------------+ |
  |   | Step 1: Check In-Memory APCu Hash Map            | |
  |   +───┬──────────────────────────────────────────────+ |
  |       │ HIT -> Load Class Bytecode directly            |
  |       │ MISS                                           |
  |   +───▼──────────────────────────────────────────────+ |
  |   | Step 2: Check Static Classmap (Array Lookup)     | |
  |   +───┬──────────────────────────────────────────────+ |
  |       │ HIT -> require $file; Cache to APCu            |
  |       │ MISS                                           |
  |   +───▼──────────────────────────────────────────────+ |
  |   | Classmap Authoritative Flag Active?              | |
  |   +───┬──────────────────────────────────────────────+ |
  |       ├── [YES] ──> FATAL: Class Not Found (Fast Fail) |
  |       └── [NO]  ──> Fallback: Step 3 (PSR-4 Path Scan) |
  |                     lstat() / file_exists() across disk|
  +────────────────────────────────────────────────────────+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Path Repository Setup pada Monorepo
Struktur Folder:
```text
monorepo/
├── composer.json (Root)
└── packages/
    └── telemetry-contract/
        ├── composer.json
        └── src/
            └── TracerInterface.php
```

Root `composer.json`:
```json
{
    "name": "enterprise/monorepo",
    "require": {
        "php": ">=8.3",
        "enterprise/telemetry-contract": "@dev"
    },
    "repositories": [
        {
            "type": "path",
            "url": "packages/telemetry-contract",
            "options": {
                "symlink": true
            }
        }
    ],
    "config": {
        "sort-packages": true,
        "optimize-autoloader": true
    },
    "minimum-stability": "dev",
    "prefer-stable": true
}
```

`packages/telemetry-contract/composer.json`:
```json
{
    "name": "enterprise/telemetry-contract",
    "type": "library",
    "license": "proprietary",
    "autoload": {
        "psr-4": {
            "Enterprise\\Telemetry\\Contract\\": "src/"
        }
    },
    "require": {
        "php": ">=8.3"
    }
}
```

`packages/telemetry-contract/src/TracerInterface.php`:
```php
<?php

declare(strict_types=1);

namespace Enterprise\Telemetry\Contract;

interface TracerInterface
{
    public function trace(string $spanName, callable $callback): mixed;
}
```

#### B. Practical Example: Custom Enterprise Composer Policy Plugin
Memastikan bahwa tidak ada developer yang dapat menginstall package pihak ketiga yang tidak terdaftar di approved vendor list internal.

`SecurityPolicyPlugin.php`:
```php
<?php

declare(strict_types=1);

namespace Enterprise\ComposerPlugin;

use Composer\Composer;
use Composer\EventDispatcher\EventSubscriberInterface;
use Composer\Installer\PackageEvent;
use Composer\Installer\PackageEvents;
use Composer\IO\IOInterface;
use Composer\Plugin\PluginInterface;
use RuntimeException;

final class SecurityPolicyPlugin implements PluginInterface, EventSubscriberInterface
{
    private const ALLOWED_ORGS = [
        'psr/',
        'symfony/',
        'enterprise/',
        'monolog/',
    ];

    private IOInterface $io;

    public function activate(Composer $composer, IOInterface $io): void
    {
        $this->io = $io;
    }

    public function deactivate(Composer $composer, IOInterface $io): void
    {
    }

    public function uninstall(Composer $composer, IOInterface $io): void
    {
    }

    public static function getSubscribedEvents(): array
    {
        return [
            PackageEvents::PRE_PACKAGE_INSTALL => 'validatePackageOrigin',
        ];
    }

    public function validatePackageOrigin(PackageEvent $event): void
    {
        $operation = $event->getOperation();
        
        // Composer 2: Method resolution via operation
        $package = method_exists($operation, 'getPackage') 
            ? $operation->getPackage() 
            : $operation->getInitialPackage();

        $packageName = $package->getName();

        foreach (self::ALLOWED_ORGS as $allowedPrefix) {
            if (str_starts_with($packageName, $allowedPrefix)) {
                $this->io->write("<info>[SECURITY AUDIT PASSED]</info> {$packageName}");
                return;
            }
        }

        throw new RuntimeException(
            sprintf(
                "ABORTING INSTALL: Package '%s' is not within Enterprise Whitelisted Organizations. Contact InfoSec.",
                $packageName
            )
        );
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Transaksi Finansial Omni-Channel (Bank/Fintech Tier-1)
Sebuah bank digital memproses 40 juta transaksi per hari dengan PHP backend service.
- **Problem:** Aplikasi monolithic core framework mengalami degradasi performa I/O tinggi saat proses cold start pada serverless worker dan Docker container scale-out. Waktu autoload class mencapai 18% dari total execution time saat booting framework. Terjadi insiden dependensi transitif di mana package AWS SDK meng-override package Guzzle client ke versi lama yang mengandung memory leak.
- **Solusi Arsitektural:**
  1. Monolith dipisahkan menjadi 15 decoupling packages via Monorepo.
  2. Implementasi Enterprise Contract Packages (`bank/ledger-contract`, `bank/idempotency-contract`) tanpa dependensi eksternal.
  3. Mengaktifkan Authoritative Classmap Compilation + APCu Autoloader Cache pada container deployment:
     ```bash
     composer dump-autoload --optimize --classmap-authoritative --apcu
     ```
  4. Penggunaan PHP-Scoper pada *Infrastructure Packages* yang mengisolasi Guzzle and AWS SDK ke namespace internal `Enterprise\VendorScoped\GuzzleHttp`.
- **Hasil:**
  - Latensi cold boot berkurang dari 180ms menjadi 22ms.
  - File disk hit (`open_basedir` checks) berkurang menjadi 0 saat runtime autoload.
  - Zero-dependency collision antar package payment gateway yang memiliki dependensi SDK vendor yang bertolak belakang.

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Biaya / Trade-off |
| :--- | :--- | :--- |
| **Authoritative Classmap (`-a`)** | Performa execution speed maksimal ($O(1)$ lookup via memory), zero I/O disk checking. | Tidak mentoleransi dynamic runtime class loading (seperti proxy generator atau eval code) jika file belum terindeks saat build pipeline. |
| **Monorepo (Path Repositories)** | Memudahkan refactoring atomik, single source of truth, sinkronisasi linting/CI mudah. | Git history menjadi sangat besar; resolusi dependency tree lokal monorepo membutuhkan RAM besar saat run `composer update`. |
| **Dependency Scoping (PHP-Scoper)** | Mencegah dependency hell total; package dapat membawa dependencies versi apapun secara terisolasi. | Kompleksitas build pipeline meningkat drastis; debugging stack trace menjadi lebih sulit karena namespace yang diubah otomatis. |
| **Private Satis Registry** | Kontrol penuh, offline availability, compliance lisensi dan security scanning internal. | Beban operasional maintenance infrastruktur Satis, build metadata time lambat saat jumlah tag git mencapai puluhan ribu. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Dynamic Class Generation Error pada Classmap Authoritative
- **Symptom:** `Fatal error: Uncaught Error: Class 'DoctrineProxies\__CG__\App\Entity\User' not found`.
- **Root Cause:** Framework men-generate proxy class secara dinamis di runtime ke folder cache, namun Composer diset Authoritative sehingga classloader menolak mengecek filesystem.
- **Solusi:** Daftarkan autoloader kedua khusus runtime dynamic proxy, atau pastikan generate proxy terjadi saat **build phase** sebelum `composer dump-autoload -a` dieksekusi.

#### Kesalahan 2: Pinned Commit Reference pada Monorepo Path Repositories
- **Symptom:** `composer install` gagal di CI/CD dengan error: `The service was not found in path...`
- **Root Cause:** `composer.lock` menyimpan path absolut mesin lokal developer.
- **Solusi:** Gunakan relative path di composer.json (`packages/my-package`), dan pastikan flag `"symlink": false` atau copy strategy diaktifkan untuk container packaging environment via env variable: `COMPOSER_MIRROR_PATH_REPOS=1`.

#### Kesalahan 3: Missing Version Tags pada Path Repositories saat Resolusi Semver
- **Symptom:** Root project menolak require package lokal dengan alasan versi tidak cocok: `Could not satisfy version constraint ^2.0`.
- **Root Cause:** Path repositori mengambil versi dari git branch lokal yang tidak memiliki tag valid.
- **Solusi:** Definisikan explicit version di `composer.json` lokal package khusus saat fase isolasi monorepo, atau gunakan alias branch: `"enterprise/telemetry": "dev-main as 2.0.0"`.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Lockfile Integrity:** `composer.lock` **wajib** di-commit ke Version Control System untuk root projects; **dilarang keras** di-commit untuk library packages publik.
2. [ ] **CI Validation:** Selalu jalankan `composer validate --strict --no-check-all` di dalam pre-commit hook dan pipeline CI.
3. [ ] **Production Autoload Strategy:** Gunakan parameter build:
   ```bash
   composer install --no-dev --prefer-dist --optimize-autoloader --classmap-authoritative --no-progress
   ```
4. [ ] **Platform Target Locking:** Pin PHP platform di `composer.json` untuk mencegah developer dengan PHP runtime lokal lebih baru menginstal dependencies yang tidak didukung server produksi:
   ```json
   "config": {
       "platform": {
           "php": "8.3.4"
       }
   }
   ```
5. [ ] **Audit Script Injection:** Matikan script otomatis pihak ketiga saat deployment pipeline: gunakan flag `--no-scripts`.
6. [ ] **Zero-Vendor Overhead:** Pastikan `vendor-bin` pattern digunakan untuk tooling QA (PHPStan, Rector, PHPCS) agar dependensi tooling developer tidak bocor ke runtime produksi.

---

### 12. Hands-on Practice

Buat dan implementasikan struktur multi-package monorepo enterprise di dalam folder: `hands-on/m02/`.

#### Langkah 1: Inisialisasi Struktur Workspace
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
mkdir -p packages/core-contracts/src
mkdir -p packages/metrics-collector/src
mkdir -p app/src
```

#### Langkah 2: Buat Contract Package
File: `packages/core-contracts/composer.json`
```json
{
    "name": "corporate/core-contracts",
    "version": "1.0.0",
    "type": "library",
    "autoload": {
        "psr-4": {
            "Corporate\\Contracts\\": "src/"
        }
    },
    "require": {
        "php": ">=8.3"
    }
}
```

File: `packages/core-contracts/src/MetricsInterface.php`
```php
<?php

declare(strict_types=1);

namespace Corporate\Contracts;

interface MetricsInterface
{
    public function increment(string $key, array $tags = []): void;
    public function timing(string $key, float $milliseconds, array $tags = []): void;
}
```

#### Langkah 3: Buat Implementation Package
File: `packages/metrics-collector/composer.json`
```json
{
    "name": "corporate/metrics-collector",
    "version": "1.0.0",
    "type": "library",
    "autoload": {
        "psr-4": {
            "Corporate\\Metrics\\": "src/"
        }
    },
    "require": {
        "php": ">=8.3",
        "corporate/core-contracts": "^1.0"
    }
}
```

File: `packages/metrics-collector/src/LogMetricsCollector.php`
```php
<?php

declare(strict_types=1);

namespace Corporate\Metrics;

use Corporate\Contracts\MetricsInterface;

final readonly class LogMetricsCollector implements MetricsInterface
{
    public function increment(string $key, array $tags = []): void
    {
        echo sprintf("[METRIC-INC] %s | Tags: %s\n", $key, json_encode($tags));
    }

    public function timing(string $key, float $milliseconds, array $tags = []): void
    {
        echo sprintf("[METRIC-TIME] %s: %.2fms | Tags: %s\n", $key, $milliseconds, json_encode($tags));
    }
}
```

#### Langkah 4: Hubungkan ke Monolith Root
File: `composer.json` (Root)
```json
{
    "name": "corporate/root-application",
    "type": "project",
    "require": {
        "php": ">=8.3",
        "corporate/core-contracts": "@dev",
        "corporate/metrics-collector": "@dev"
    },
    "repositories": [
        {
            "type": "path",
            "url": "packages/*",
            "options": {
                "symlink": true
            }
        }
    ],
    "autoload": {
        "psr-4": {
            "App\\": "app/src/"
        }
    },
    "config": {
        "optimize-autoloader": true,
        "sort-packages": true
    },
    "minimum-stability": "dev",
    "prefer-stable": true
}
```

#### Langkah 5: Eksekusi Instalasi & Pengujian Runtime
Jalankan di shell:
```bash
composer install
```

File: `app/src/Kernel.php`
```php
<?php

declare(strict_types=1);

namespace App;

use Corporate\Contracts\MetricsInterface;

final readonly class Kernel
{
    public function __construct(
        private MetricsInterface $metrics
    ) {}

    public function run(): void
    {
        $start = microtime(true);
        $this->metrics->increment('application.boot');
        
        // Simulate workload
        usleep(10000); // 10ms
        
        $duration = (microtime(true) - $start) * 1000;
        $this->metrics->timing('application.execution', $duration);
    }
}
```

File: `index.php`
```php
<?php

declare(strict_types=1);

require_once __DIR__ . '/vendor/autoload.php';

use App\Kernel;
use Corporate\Metrics\LogMetricsCollector;

$metricsService = new LogMetricsCollector();
$kernel = new Kernel($metricsService);
$kernel->run();
```

Eksekusi:
```bash
php index.php
```

Output:
```text
[METRIC-INC] application.boot | Tags: []
[METRIC-TIME] application.execution: 10.15ms | Tags: []
```

---

### 13. Exercise

#### Level Easy
Ubah implementasi `index.php` dan buat `NullMetricsCollector` di dalam namespace package `corporate/core-contracts` yang mengimplementasikan `MetricsInterface` (pola Null Object Pattern) tanpa mencetak output apapun. Update autoloader dan buktikan kodenya bekerja.

#### Level Medium
Buat script automation PHP standalone `packages/build-authoritative-check.php`. Script ini bertugas membaca file `vendor/composer/autoload_classmap.php`, kemudian memvalidasi apakah ada class di dalam folder `packages/` yang belum terdaftar di map. Jika ada class yang tertinggal, lemparkan non-zero exit code (`exit(1)`).

#### Level Hard
Buat implementasi custom classloader decorator yang membungkus instance Composer ClassLoader bawaan. Autoloader decorator ini harus mengukur total alokasi memori (`memory_get_usage()`) dan micro-duration yang dihabiskan untuk me-`require` file class, lalu meng-output metrik tersebut ke custom structured log file (`autoload_perf.log`).

---

### 14. Challenge

**Skenario Kasus Kompleks:**
Sebuah enterprise fintech ingin memigrasikan monorepo mereka ke public-private hybrid distribution model. Anda ditugaskan merancang arsitektur automation:
1. Pisahkan package internal `corporate/core-contracts` dan `corporate/payment-engine` secara dinamis menggunakan script pipeline.
2. Package `corporate/payment-engine` secara transitif bergantung pada package pihak ketiga `vendor-x/secure-crypto` versi `^1.0`. Namun, Host Monolith sudah menggunakan `vendor-x/secure-crypto` versi `^2.0` yang memiliki breaking signature changes.
3. Anda **dilarang** meng-upgrade package di Monolith dan **dilarang** mengubah kode dari `vendor-x/secure-crypto`.

**Tantangan:**
Rancang konfigurasi build pipeline menggunakan `php-scoper` atau tool namespace isolating serupa yang:
- Mengisolasi dependensi `vendor-x/secure-crypto:^1.0` ke dalam namespace prefix unik (`Corporate\IsolatedVendor\...`) di dalam artefak distribusi `corporate/payment-engine`.
- Memastikan autoloader Composer di Monolith tetap bisa mengeksekusi method payment engine tanpa mengalami namespace clash fatal error: `Cannot declare class ... because the name is already in use`.
- Tuliskan file konfigurasi `scoper.inc.php` minimal yang valid dan jelaskan struktur artefak hasil build.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Basic (Pilihan Ganda)
1. **Perbedaan utama antara flags `--optimize-autoloader` (-o) dan `--classmap-authoritative` (-a) adalah:**
   - A. `-o` mengkompilasi class ke byte code, `-a` mengkompilasi class ke binary file.
   - B. `-o` hanya memetakan class PSR-4, sedangkan `-a` menghentikan traversal filesystem fallback jika class tidak ditemukan di classmap.
   - C. `-a` hanya bekerja pada sistem operasi Linux/UNIX.
   - D. `-o` mengaktifkan APCu cache secara default.

2. **File Composer mana yang bertugas menyimpan deterministik *state* dependency tree yang wajib diikutsertakan ke dalam repositori monolith?**
   - A. `composer.json`
   - B. `composer.lock`
   - C. `installed.json`
   - D. `autoload_real.php`

3. **Format namespace autoloader default yang diadopsi ekosistem PHP modern sesuai PHP-FIG adalah:**
   - A. PSR-0
   - B. PSR-2
   - C. PSR-4
   - D. PSR-12

4. **Bagaimana Composer menangani package internal di dalam monorepo saat didefinisikan dengan skema path repository dan symlink bernilai `true`?**
   - A. Composer menyalin (copy) seluruh direktori fisik ke dalam folder `vendor/`.
   - B. Composer membuat symlink filesystem dari folder `packages/` langsung ke `vendor/<vendor-name>/<package-name>`.
   - C. Composer mengompres package menjadi file `.tar.gz` di dalam local cache.
   - D. Composer men-deploy package ke GitHub secara otomatis.

5. **Apa fungsi dari package type `composer-plugin`?**
   - A. Mempercepat eksekusi PHP OPcache.
   - B. Memberikan antarmuka ekstensi bagi Composer runtime untuk menyisipkan lifecycle logic custom.
   - C. Menjadi wrapper PHP untuk C-extension library.
   - D. Menghasilkan unit test secara otomatis.

#### B. Intermediate (Analisis Singkat)
1. Analisis mengapa menggunakan `"minimum-stability": "dev"` tanpa mengonfigurasi `"prefer-stable": true` dapat merusak arsitektur paket enterprise.
2. Jelaskan bahaya keamanan dari opsi `COMPOSER_ALLOW_SUPERUSER=1` jika dieksekusi di dalam pipeline CI/CD tanpa isolasi unprivileged user.
3. Mengapa package bertipe *Contract* sama sekali tidak boleh mendefinisikan dependensi vendor implementasi concrete di dalam block `require` `composer.json`-nya?
4. Apa dampak penggunaan APCu autoloading (`--apcu`) pada container PHP-FPM yang memiliki worker proses tinggi dan alokasi memori terbatas?
5. Bagaimana Composer SAT solver menangani skenario konflik versi circular dependency antara Package A dan Package B?

#### C. Skenario Kasus Produksi
1. **Skenario Logika:** Sebuah library internal `enterprise/logger` di-update ke versi `1.2.0` dan dipublikasikan ke Satis server. Namun, saat tim Monolith menjalankan `composer update enterprise/logger`, versi yang terpasang tetap `1.1.4`. Sebutkan 3 kemungkinan root cause arsitektural yang menyebabkan SAT Solver Composer menolak meng-upgrade package tersebut.
2. **Skenario Kinerja:** Pada load testing berskala 50,000 req/sec, tracing NewRelic menunjukkan latency bottleneck berada pada function `Composer\Autoload\ClassLoader::findFileWithExtension`. Arsitektur autoloader apa yang belum diimplementasikan, dan bagaimana langkah mitigasi pastinya pada level build pipeline Docker?
3. **Skenario Keamanan:** Terjadi insiden supply-chain attack di mana repository public eksternal yang digunakan oleh tim frontend secara transitif menimpa nama package internal enterprise (`enterprise/auth-token`). Pola konfigurasi repositori apa di `composer.json` yang harus diterapkan untuk memitigasi *dependency confusion attack* ini?

---

### Kunci Jawaban Quiz

#### Bagian A (Basic)
1. **B** — `-a` menginstruksikan Composer ClassLoader untuk tidak pernah melakukan fallback pemeriksaan disk fisik (PSR-4/PSR-0 checking) jika class target tidak ada di classmap.
2. **B** — `composer.lock`.
3. **C** — PSR-4.
4. **B** — Membuat symlink langsung di filesystem lokal.
5. **B** — Mengizinkan ekstensi fungsionalitas lifecycle Composer via `PluginInterface`.

#### Bagian B (Intermediate)
1. `minimum-stability: dev` mengizinkan resolusi dependensi ditarik dari unstable/untested dev branch across vendor tree. Tanpa `prefer-stable: true`, SAT solver akan memprioritaskan commit dev labil daripada release tag yang stabil.
2. Eksekusi Composer sebagai root (`SUPERUSER`) membuka risiko Remote Code Execution (RCE). Package pihak ketiga yang memiliki lifecycle script (`post-install-cmd`) dapat mengeksekusi binary arbitrary dengan privilege tertinggi sistem dan mengompromikan host/container environment.
3. *Contract Package* harus murni menjadi abstraction layer (ISP & DIP Solid Principles). Mengotori contract dengan concrete implementation dependencies akan memaksa consumer contract menginstall dependensi implementasi tersebut (transitive dependency bloat).
4. Jika alokasi memory pool `apc.shm_size` habis, APCu cache thrashing terjadi. Setiap worker akan saling lock (`cache stampede`) untuk meng-update map namespace yang miss, mengakibatkan spike penggunaan CPU dan memory contention.
5. SAT solver (Glucose logic) memetakan dependency tree ke dalam conjunctive normal form boolean clause. Jika circular dependency tidak memiliki solusi version matching yang beririsan (satisfiable), solver melempar `SolverProblemsException` dan membatalkan transaksi dependensi.

#### Bagian C (Skenario Produksi)
1. **Root Cause:**
   - Adanya batasan versi inkonsisten pada root `composer.json` (misal explicit constraint `"enterprise/logger": "1.1.*"`).
   - Package internal lain memiliki transitive lock dependency yang mengikat kuat ke `1.1.4` (misal `"enterprise/payment": "requires enterprise/logger: 1.1.4"`).
   - Platform constraint check: `enterprise/logger: 1.2.0` mensyaratkan ekstensi PHP atau versi engine yang tidak kompatibel dengan `config.platform.php` di host.
2. **Mitigasi:**
   - Host belum mengaktifkan authoritative classmap compilation.
   - Jalankan `composer dump-autoload --classmap-authoritative --optimize` pada multi-stage Docker build pipeline sebelum container image final di-packing.
3. **Mitigasi Serangan Dependency Confusion:**
   - Konfigurasikan explicit repository priority menggunakan property `only` atau `exclude` pada definisi repository di root `composer.json`. Pastikan vendor `enterprise/*` hanya diarahkan secara eksklusif ke endpoint private Satis internal:
   ```json
   "repositories": [
       {
           "type": "composer",
           "url": "https://satis.internal.enterprise.com",
           "only": ["enterprise/*"]
       },
       {
           "packagist.org": false
       }
   ]
   ```

---

### 16. Summary

1. Arsitektur ekosistem package modern PHP bertumpu pada resolusi relasi matematis SAT Solver dan standar PSR-4.
2. Menghindari inefisiensi I/O di environment produksi dilakukan dengan mengonversi dynamic autoload checking menjadi $O(1)$ static array lookup melalui **Authoritative Classmap Compilation** (`--classmap-authoritative`).
3. Pemisahan tanggung jawab (*Separation of Concerns*) pada skala enterprise mengharuskan segmentasi paket yang rigid: **Contract** (Interface murni), **Implementation** (Core business), dan **Infrastructure** (External adapters).
4. Pola monorepo modern di PHP dikelola secara terpusat memanfaatkan Composer **Path Repositories**, menjaga sinkronisasi refactoring kode lokal tanpa mengorbankan isolasi antar paket.
5. Perlindungan pipeline produksi dari *dependency confusion* dan *runtime collisions* dicapai melalui isolasi private package registries, custom policy validation plugins, dan teknik *namespace scoping*.