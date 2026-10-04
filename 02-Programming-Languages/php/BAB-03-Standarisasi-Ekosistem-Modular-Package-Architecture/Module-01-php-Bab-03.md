# STANDARISASI EKOSISTEM & MODULAR PACKAGE ARCHITECTURE

---

## SEKSI 01 — IDENTITAS MODUL

* **Kategori Kurikulum:** `02-Programming-Languages`
* **Track:** `PHP Enterprise & Modern Backend Engineering`
* **Bab:** `03 — Ecosystem Architecture, Package Design & Interoperability`
* **Modul:** `01 — Standarisasi Ekosistem & Modular Package Architecture`
* **Tingkat Kesulitan:** `Advanced / L3-L4 Backend Engineer`
* **Prasyarat Pengetahuan:**
  * Penguasaan mendalam PHP 8.1+ Object-Oriented Programming (Classes, Interfaces, Attributes, Enums).
  * Pemahaman tentang Dependency Management menggunakan Composer.
  * Pemahaman dasar tentang algoritma resolusi graf dan HTTP lifecycle.
* **Target Runtime:** PHP >= 8.2, Composer >= 2.6

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Mengimplementasikan PHP Standards Recommendations (PSR):** Menguasai penerapan operasional dan filosofi desain dari PSR-1, PSR-4, PSR-7 (HTTP Message Interface), PSR-11 (Container Interface), PSR-14 (Event Dispatcher), dan PER Coding Style 2.0.
2. **Membedah Algoritma Resolusi Dependensi & Autoloader Engine:** Menjelaskan secara matematis dan prosedural cara kerja Composer SAT Solver (Boolean Satisfiability) dan membedakan strategi autoloader (Classmap, PSR-4, Optimizations `--classmap-authoritative`).
3. **Mendesain Modular Package Architecture:** Membangun reusable package yang *framework-agnostic* dengan *zero side-effects*, mengisolasi API publik dari implementasi internal via *package boundary* dan Composer configuration.
4. **Menerapkan Semantic Versioning (SemVer) & Deprecation Lifecycle:** Merancang strategi breaking changes, backward compatibility (BC) promise, dan otomatisasi release via CI/CD.
5. **Mengelola Private Package Distribution:** Mengonfigurasi dan memelihara enterprise package repository menggunakan Satis/Private Packagist dengan enkripsi kredensial dan audit keamanan dependensi.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### 1. The Interoperability Contract (Abstraksi di Atas Konkret)
Sebelum era PHP-FIG (PHP Framework Interop Group), ekosistem PHP terfragmentasi ke dalam "walled gardens": library milik Symfony tidak dapat digunakan di Zend Framework; ORM milik Doctrine sulit diintegrasikan ke framework custom. Mental model modern memandang library bukan sebagai sekumpulan fungsi, melainkan **implementasi dari sebuah kontrak abstrak formal (Interface)**. Framework hanyalah orchestration engine, sedangkan fungsionalitas bisnis harus bersifat framework-agnostic.

```
       TRADISIONAL (Tightly Coupled)             MODERN PSR-CENTRIC (Decoupled)

   +------------------------------------+     +-----------------------------------+
   |         Framework Monolithic       |     |        Application Domain         |
   |  +--------------+  +------------+  |     +-----------------+-----------------+
   |  | Custom Cache |  | Custom Log |  |                       |
   |  +--------------+  +------------+  |           PSR Interface Contracts
   +------------------------------------+           (PSR-3, PSR-6, PSR-11)
                                                                |
                                              +-----------------+-----------------+
                                              |                 |                 |
                                      +-------v-------+ +-------v-------+ +-------v-------+
                                      | Monolog (PSR3)| | Redis (PSR-6) | | Custom Package|
                                      +---------------+ +---------------+ +---------------+
```

### 2. Dependency Resolution sebagai Graf Logika Proposisi
Jangan menganggap Composer sekadar program pengunduh file `.zip`. Composer adalah mesin inferensi matematika. Ketika mendefinisikan *constraint* versi (misal: `^2.1` dan `~1.0`), Composer mentranslasikan setiap versi package, requirement, dan konflik menjadi formula logika proposisi dalam bentuk **Conjunctive Normal Form (CNF)**, kemudian mengeksekusi algoritma *Boolean Satisfiability (SAT) Solver* untuk menemukan konfigurasi versi yang valid tanpa paradoks dependensi.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Composer Execution Lifecycle & Autoloader Generation

```
                     composer.json + composer.lock
                                  │
                                  ▼
                 ┌─────────────────────────────────┐
                 │  Pool Builder & Sat Solver      │
                 │  - Evaluasi Repository Pool     │
                 │  - CNF Formulation & Solving   │
                 └────────────────┬────────────────┘
                                  │
                                  ▼
                 ┌─────────────────────────────────┐
                 │  Dependency Graph Resolved      │
                 │  - Ekstraksi ke Vendor Path     │
                 └────────────────┬────────────────┘
                                  │
                                  ▼
      ┌────────────────────────────────────────────────────────┐
      │              Autoload Generation Engine                │
      │                                                        │
      │  ┌────────────────────┐      ┌──────────────────────┐  │
      │  │ Dynamic PSR-4 Map  │      │ Static Classmap Map  │  │
      │  └─────────┬──────────┘      └──────────┬───────────┘  │
      └────────────┼────────────────────────────┼──────────────┘
                   │                            │
                   └──────────────┬─────────────┘
                                  │
                  (Jika --classmap-authoritative)
                                  │
                                  ▼
                  ┌───────────────────────────────┐
                  │ vendor/composer/              │
                  │   autoload_classmap.php       │ ◄── O(1) Hash-Map Lookup
                  │   (In-Memory Array Match)     │     Zero Filesystem I/O
                  └───────────────────────────────┘
```

### Alur Resolusi Runtime Autoloader (PSR-4 vs Classmap Authoritative)

```
[ PHP Script ]
      │
      │ Trigger Class Reference: \Acme\Domain\Invoice
      ▼
[ Composer Autoloader Engine ] (Registered via spl_autoload_register)
      │
      ├─► Apakah classmap authorative aktif?
      │     ├─► YA: Cek array key lookup di autoload_classmap.php
      │     │         ├─ Ditemukan: require $path -> FINISH
      │     │         └─ Tidak ditemukan: throw ClassNotFoundException (FAIL FAST)
      │     │
      │     └─► TIDAK (Fallback PSR-4 Dynamic):
      │               │
      │               ▼
      │         Cek Namespace Prefix (\Acme\Domain\)
      │               │
      │               ▼
      │         Ubah Sub-namespace & Class menjadi File Path
      │         \Acme\Domain\Invoice  ──►  src/Invoice.php
      │               │
      │               ▼
      │         Lakukan file_exists($path) I/O Disk Check
      │               ├─► Ada: require $path -> SUCCESS
      │               └─► Tidak ada: Lanjut ke autoloader berikutnya / Error
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Anatomi composer.json Standar Enterprise
Setiap deklarasi dalam konfigurasi Composer merefleksikan batas arsitektural (*boundary*):

```json
{
  "$schema": "https://getcomposer.org/schema.json",
  "name": "enterprise/payment-core",
  "description": "Enterprise-grade decoupled payment abstraction layer.",
  "type": "library",
  "license": "proprietary",
  "minimum-stability": "stable",
  "prefer-stable": true,
  "authors": [
    {
      "name": "Backend Architecture Team",
      "email": "architecture@enterprise.internal"
    }
  ],
  "require": {
    "php": ">=8.2",
    "psr/http-message": "^2.0",
    "psr/log": "^3.0",
    "psr/container": "^2.0"
  },
  "require-dev": {
    "phpunit/phpunit": "^11.0",
    "phpstan/phpstan": "^1.11",
    "squizlabs/php_codesniffer": "^3.10"
  },
  "autoload": {
    "psr-4": {
      "Enterprise\\PaymentCore\\": "src/"
    }
  },
  "autoload-dev": {
    "psr-4": {
      "Enterprise\\PaymentCore\\Tests\\": "tests/"
    }
  },
  "config": {
    "optimize-autoloader": true,
    "sort-packages": true,
    "allow-plugins": {
      "dealerdirect/phpcodesniffer-composer-installer": true
    }
  }
}
```

### 2. Mekanisme Internal Dynamic Path Resolver (PSR-4)
PSR-4 menetapkan pemetaan formal antara *Fully Qualified Class Name* (FQCN) dengan struktur direktori fisik di disk:

* Aturan PSR-4:
  1. Prefix namespace yang berurutan (Vendor Namespace + Sub-namespaces) dipetakan ke direktori dasar (*base directory*).
  2. Nama class setelah prefix namespace berkorespondensi 1:1 dengan nama file yang berakhiran `.php`.
  3. Karakter pemisah namespace (`\`) dikonversi menjadi *directory separator* sistem operasi (`/` pada Unix, `\` pada Windows).

Secara internal, Composer memelihara struktur data array tree yang memetakan prefix terpanjang lebih dahulu (*longest prefix match*) untuk menghindari tabrakan namespace.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Standar PHP-FIG Utama
* **PSR-1 & PER Coding Style 2.0 (Evolusi PSR-12):**
  Mengatur konsistensi sintaksis tingkat rendah. Kelas HARUS menggunakan `StudlyCaps`, konstanta `ALL_UPPER_CASE_WITH_UNDERSCORES`, method `camelCase`. Tidak boleh ada side-effects saat file di-include (misal: memodifikasi `ini_set`, mencetak output, menginisialisasi state global).
* **PSR-4 (Autoloading Standard):**
  Mengeliminasi kebutuhan deklarasi path eksplisit seperti pada era PHP purba (`require_once`). Autoloader bekerja on-demand (*lazy loading*) saat simbol diakses pertama kali pada memori eksekusi.
* **PSR-7 (HTTP Message Interfaces):**
  Mendefinisikan representasi immutable dari HTTP Request, Response, URI, Uploaded File, dan Streams. Immutability (`withHeader()`, `withStatus()`) menjamin bahwa HTTP state tidak dapat dimutasi secara tak terduga (*accidental state mutation*) saat melewati pipeline middleware.
* **PSR-11 (Container Interface):**
  Mendefinisikan interface dependensi paling mendasar: `get(string $id)` dan `has(string $id)`. Tujuannya bukan untuk membuat framework bergantung pada library tertentu, melainkan memungkinkan modul pihak ketiga mengambil dependensi tanpa terikat pada implementasi konkret container (Laravel Service Container, Symfony DependencyInjection, PHP-DI).

### 2. SAT Solver Matematika di Composer
Composer mengimplementasikan algoritma SAT solver berbasis varian **DPLL (Davis-Putnam-Logemann-Loveland)** dan **CDCL (Conflict-Driven Clause Learning)** via package internal `composer/pcre` dan `composer/semver`.
Ketika Package A membutuhkan `foo/bar: ^1.0` dan Package B membutuhkan `foo/bar: ^2.0`, solver memetakan:
$$\text{Clause 1: } A \implies (\text{foo/bar } 1.0 \lor \text{foo/bar } 1.1 \lor \dots)$$
$$\text{Clause 2: } B \implies (\text{foo/bar } 2.0 \lor \text{foo/bar } 2.1 \lor \dots)$$
$$\text{Clause 3: } \neg (\text{foo/bar } 1.x \land \text{foo/bar } 2.x) \quad \text{[Eksklusivitas Versi]}$$
Jika persamaan logika tersebut menghasilkan kontradiksi matematika ($False$), Composer menghentikan eksekusi (*abort*) dan mencetak *Conflict Diagnostic Graph*.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah perancangan modular package micro-kernel yang mengimplementasikan **PSR-11 (Container)** dan **PSR-4 autoloading** murni tanpa framework eksternal.

### Struktur Direktori Package
```text
modular-core/
├── composer.json
└── src/
    ├── Container/
    │   ├── ContainerException.php
    │   ├── NotFoundException.php
    │   └── ServiceContainer.php
    └── Contract/
        └── ServiceProviderInterface.php
```

### 1. `src/Container/NotFoundException.php`
```php
<?php

declare(strict_types=1);

namespace Enterprise\ModularCore\Container;

use Psr\Container\NotFoundExceptionInterface;
use Exception;

final class NotFoundException extends Exception implements NotFoundExceptionInterface
{
    public static function forIdentifier(string $id): self
    {
        return new self(sprintf("Service '%s' is not registered in the container.", $id));
    }
}
```

### 2. `src/Container/ContainerException.php`
```php
<?php

declare(strict_types=1);

namespace Enterprise\ModularCore\Container;

use Psr\Container\ContainerExceptionInterface;
use RuntimeException;
use Throwable;

final class ContainerException extends RuntimeException implements ContainerExceptionInterface
{
    public static function failedToInstantiate(string $id, Throwable $previous): self
    {
        return new self(
            sprintf("Failed to instantiate service '%s' due to internal error.", $id),
            0,
            $previous
        );
    }
}
```

### 3. `src/Contract/ServiceProviderInterface.php`
```php
<?php

declare(strict_types=1);

namespace Enterprise\ModularCore\Contract;

use Psr\Container\ContainerInterface;

interface ServiceProviderInterface
{
    /**
     * Daftarkan dependensi ke container.
     */
    public function register(ContainerInterface $container): void;
}
```

### 4. `src/Container/ServiceContainer.php`
```php
<?php

declare(strict_types=1);

namespace Enterprise\ModularCore\Container;

use Psr\Container\ContainerInterface;
use Closure;
use Throwable;

final class ServiceContainer implements ContainerInterface
{
    /**
     * @var array<string, Closure(self): mixed>
     */
    private array $definitions = [];

    /**
     * @var array<string, mixed>
     */
    private array $resolvedInstances = [];

    public function set(string $id, Closure $factory): void
    {
        unset($this->resolvedInstances[$id]);
        $this->definitions[$id] = $factory;
    }

    public function get(string $id): mixed
    {
        if (isset($this->resolvedInstances[$id])) {
            return $this->resolvedInstances[$id];
        }

        if (!$this->has($id)) {
            throw NotFoundException::forIdentifier($id);
        }

        try {
            $factory = $this->definitions[$id];
            $instance = $factory($this);
            $this->resolvedInstances[$id] = $instance;

            return $instance;
        } catch (Throwable $e) {
            throw ContainerException::failedToInstantiate($id, $e);
        }
    }

    public function has(string $id): bool
    {
        return isset($this->definitions[$id]) || isset($this->resolvedInstances[$id]);
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Pada implementasi di atas:
1. **`declare(strict_types=1);`**: Mematikan type coercion PHP. Wajib pada seluruh implementasi PSR untuk mencegah silent bug ketika string dikonversi otomatis menjadi integer/float.
2. **`implements NotFoundExceptionInterface` & `implements ContainerExceptionInterface`**: PSR-11 mewajibkan implementor melempar exception yang menurunkan kedua interface tersebut. Dengan meng-implement keduanya, kode pemanggil dapat menangkap error menggunakan `catch (\Psr\Container\ContainerExceptionInterface $e)` secara seragam, lepas dari implementasi internal exception vendor.
3. **`private array $definitions` & `private array $resolvedInstances`**: Mengimplementasikan pola *Lazy Instantiation* dan *Singleton Registry Pattern*. Service tidak pernah di-instansiasi sebelum metode `get()` dipanggil.
4. **`$this->definitions[$id] = $factory;`**: Definisi dependensi disimpan sebagai *invokable closure*.
5. **Handling Error di `get()`**: Block `try-catch (\Throwable $e)` mengkapsulasi seluruh failure (termasuk fatal engine errors seperti `TypeError`) dan membungkusnya (*wrapping*) ke dalam `ContainerException` yang kompatibel dengan PSR-11, mempertahankan *exception chain* melalui parameter `$previous`.

---

## SEKSI 09 — STUDI KASUS NYATA

### Konteks: Gateway Pembayaran Multi-Tenant Enterprise
Sebuah arsitektur platform SaaS e-commerce enterprise membutuhkan subsistem pembayaran yang modular. Subsistem ini harus:
1. Mendukung berbagai penyedia (*Payment Providers*): Stripe, Midtrans, Adyen.
2. Tidak boleh terikat pada framework web tertentu (dapat dijalankan via Laravel Worker, Symfony CLI, atau stateless microservice RoadRunner/Swoole).
3. Menggunakan representasi HTTP Request/Response standar PSR-7.
4. Memberikan mekanisme audit logging terstandar PSR-3 tanpa mempedulikan apakah log target adalah Logstash, AWS CloudWatch, atau standard output (`stdout`).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut arsitektur produksi modular package: `enterprise/payment-gateway-contract` dan implementasinya.

### 1. Kontrak Transaksi: `src/Contract/PaymentGatewayInterface.php`
```php
<?php

declare(strict_types=1);

namespace Enterprise\PaymentGateway\Contract;

use Psr\Log\LoggerInterface;

readonly class PaymentRequest
{
    public function __construct(
        public string $transactionId,
        public int $amountInCents,
        public string $currency,
        public array $metadata = []
    ) {}
}

enum PaymentStatus: string
{
    case SUCCESS = 'SUCCESS';
    case PENDING = 'PENDING';
    case FAILED  = 'FAILED';
}

readonly class PaymentResult
{
    public function __construct(
        public PaymentStatus $status,
        public ?string $providerReferenceId,
        public ?string $errorMessage = null
    ) {}
}

interface PaymentGatewayInterface
{
    public function process(PaymentRequest $request): PaymentResult;
    public function setLogger(LoggerInterface $logger): void;
}
```

### 2. Implementasi Provider Stripe Terisolasi: `src/Provider/StripePaymentGateway.php`
```php
<?php

declare(strict_types=1);

namespace Enterprise\PaymentGateway\Provider;

use Enterprise\PaymentGateway\Contract\PaymentGatewayInterface;
use Enterprise\PaymentGateway\Contract\PaymentRequest;
use Enterprise\PaymentGateway\Contract\PaymentResult;
use Enterprise\PaymentGateway\Contract\PaymentStatus;
use Psr\Http\Client\ClientInterface;
use Psr\Http\Message\RequestFactoryInterface;
use Psr\Log\LoggerInterface;
use Psr\Log\NullLogger;
use Throwable;

final class StripePaymentGateway implements PaymentGatewayInterface
{
    private LoggerInterface $logger;

    public function __construct(
        private readonly ClientInterface $httpClient,
        private readonly RequestFactoryInterface $requestFactory,
        private readonly string $apiKey,
        ?LoggerInterface $logger = null
    ) {
        $this->logger = $logger ?? new NullLogger();
    }

    public function setLogger(LoggerInterface $logger): void
    {
        $this->logger = $logger;
    }

    public function process(PaymentRequest $request): PaymentResult
    {
        $this->logger->info("Processing Stripe payment", [
            'transaction_id' => $request->transactionId,
            'amount' => $request->amountInCents,
        ]);

        try {
            $httpRequest = $this->requestFactory->createRequest('POST', 'https://api.stripe.com/v1/charges')
                ->withHeader('Authorization', 'Bearer ' . $this->apiKey)
                ->withHeader('Content-Type', 'application/x-www-form-urlencoded');

            $body = http_build_query([
                'amount' => $request->amountInCents,
                'currency' => strtolower($request->currency),
                'metadata' => array_merge($request->metadata, [
                    'internal_txn_id' => $request->transactionId
                ]),
            ]);

            $httpRequest->getBody()->write($body);

            // Eksekusi HTTP Client berbasis PSR-18
            $httpResponse = $this->httpClient->sendRequest($httpRequest);

            if ($httpResponse->getStatusCode() === 200) {
                $payload = json_decode((string) $httpResponse->getBody(), true, 512, JSON_THROW_ON_ERROR);

                $this->logger->info("Payment successfully settled", [
                    'stripe_charge_id' => $payload['id']
                ]);

                return new PaymentResult(
                    status: PaymentStatus::SUCCESS,
                    providerReferenceId: $payload['id']
                );
            }

            $this->logger->warning("Stripe non-200 transaction", [
                'status_code' => $httpResponse->getStatusCode(),
                'body' => (string) $httpResponse->getBody()
            ]);

            return new PaymentResult(
                status: PaymentStatus::FAILED,
                providerReferenceId: null,
                errorMessage: "HTTP Response code: " . $httpResponse->getStatusCode()
            );

        } catch (Throwable $exception) {
            $this->logger->error("Critical failure during Stripe API dispatch", [
                'error' => $exception->getMessage(),
                'trace' => $exception->getTraceAsString()
            ]);

            return new PaymentResult(
                status: PaymentStatus::FAILED,
                providerReferenceId: null,
                errorMessage: $exception->getMessage()
            );
        }
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### 1. Monorepo vs. Polyrepo Package Management

| Karakteristik | Polyrepo (Satu Git Repo per Package) | Monorepo (Banyak Package dalam Satu Repo) |
| :--- | :--- | :--- |
| **Isolasi dependensi** | Kuat; dependensi dan rilis benar-benar independen. | Perlu tooling (seperti Symplify/MonorepoBuilder) agar dependensi tidak bocor. |
| **Atomic Refactoring** | Sulit. Perubahan interface memerlukan multi-pull request di berbagai repository. | Sangat mudah. Breaking change interface dan consumer dapat diubah dalam satu commit. |
| **CI/CD Overhead** | Kecil per repo, namun kompleksitas orkestrasi pipeline antar repo tinggi. | Pipeline CI/CD lebih berat; membutuhkan *diff-aware caching*. |
| **Kesesuaian Tim** | Skala tim kecil atau open-source distributed library. | Skala enterprise besar dengan banyak domain logic terdistribusi. |

### 2. Autoloader Strategy: Standard vs Authoritative Classmap

| Metrik | Dynamic PSR-4 (`composer dump-autoload`) | Authoritative Classmap (`-a` / `-o`) |
| :--- | :--- | :--- |
| **Kecepatan Runtime** | Lambat. Terjadi syscall `stat` dan `file_exists` berulang di filesystem. | Sangat Cepat. Resolusi $O(1)$ in-memory hash array. |
| **Filesystem I/O** | Bergantung pada kedalaman direktori namespace. | Nyaris Nol. |
| **Fleksibilitas Debug** | Class baru yang ditambahkan langsung terbaca seketika. | Class baru TIDAK BISA ditemukan tanpa dump autoloader ulang. |
| **Rekomendasi Lingkungan**| Khusus Lingkungan Development. | Wajib di Seluruh Lingkungan Production. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Sensitivitas Huruf Besar/Kecil (*Case-Sensitivity*) Antara OS
* **Skenario:** Developer mengembangkan package di macOS/Windows (filesystem case-insensitive: APFS/NTFS). File dinamai `src/Userpayment.php`, tetapi class didefinisikan sebagai `class UserPayment`.
* **Konsekuensi:** Berjalan mulus di development. Ketika di-deploy ke Linux production container (ext4 case-sensitive), Composer autoloader gagal menemukan file dan melemparkan fatal error: `Class "Enterprise\UserPayment" not found`.
* **Mitigasi:** Gunakan validasi `composer exec phpcs` dengan konfigurasi PSR-12 ketat di CI pipeline Linux native container.

### 2. Autoloading Duplikasi Namespace (Namespace Collision)
Jika dua package mendefinisikan namespace PSR-4 yang identik pada `composer.json` masing-masing:
```json
// Package A
"autoload": { "psr-4": { "Common\\Utils\\": "src/" } }
// Package B
"autoload": { "psr-4": { "Common\\Utils\\": "lib/" } }
```
Composer akan menggabungkan path ini menjadi array: `['src/', 'lib/']`. Composer akan mencari file secara berurutan. Jika ada class dengan nama yang sama persis di kedua path tersebut, file pertama yang ditemukan yang akan di-*load*. Ini menyebabkan bug fatal *ghost-class overwrite* yang sangat sulit dilacak.
* **Solusi Arsitektur:** Selalu gunakan *Vendor-Specific Prefix Namespace* berjenjang (contoh: `Enterprise\Domain\Subsystem\`).

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Commit `vendor/` Directory ke Source Control
* **Kesalahan:** Meng-commit folder `vendor/` ke Git repository.
* **Dampak:** Repo membengkak ratusan megabyte, terjadi merge conflict file autoloader biner, dan perbedaan platform-specific packages (misal: extension binaries).
* **Solusi:** Selalu tambahkan `/vendor/` ke dalam `.gitignore`. Hanya commit file `composer.json` dan `composer.lock`.

### 2. Memodifikasi `composer.lock` Secara Manual
* **Kesalahan:** Menyunting hash atau versi di `composer.lock` via text editor saat merge conflict.
* **Dampak:** Hash validasi (`content-hash`) di `composer.lock` menjadi tidak sinkron dengan konfigurasi internal, menyebabkan pipeline CI gagal via verifikasi integritas.
* **Solusi:** Selesaikan conflict pada `composer.json`, kemudian eksekusi:
  ```bash
  composer update --lock
  ```
  Perintah ini mengkalkulasi ulang lock file tanpa meng-update package ke versi terbaru yang tidak diinginkan.

### 3. Salah Penggunaan Tilde (`~`) vs Caret (`^`) Constraint
* `~1.2.3`: Mengizinkan versi `>= 1.2.3 < 1.3.0` (hanya patch updates).
* `~1.2`: Mengizinkan versi `>= 1.2.0 < 2.0.0` (minor updates diizinkan).
* `^1.2.3`: Mengizinkan versi `>= 1.2.3 < 2.0.0` (seluruh minor dan patch updates).
* **Kesalahan Fatal:** Menggunakan `*` atau `dev-master` di level production. Ini melanggar determinisme build dan berisiko merusak sistem sewaktu-waktu dependency merilis breaking change.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Semantic Versioning 2.0 Guardrails:**
   * **MAJOR:** Perubahan yang memecah backward compatibility (BC Break) seperti mengubah signature method publik, menghapus method, atau menambah interface method tanpa default implementation.
   * **MINOR:** Penambahan fungsionalitas baru yang tetap kompatibel ke belakang (*backward-compatible feature*), atau menandai class sebagai `@deprecated`.
   * **PATCH:** Perbaikan bug internal tanpa mengubah public contract (*backward-compatible bug fix*).

2. **Decoupling Interface dari Framework Specific Logic:**
   Seluruh core domain interfaces HARUS diletakkan pada repository/package terpisah (`contracts`), tanpa menyertakan library berat seperti database driver atau HTTP network engine.

3. **PHP-CS-Fixer Automation:**
   Enforce standard PER Coding Style 2.0 secara otomatis melalui git pre-commit hook via Husky atau GrumPHP:
   ```bash
   vendor/bin/php-cs-fixer fix --rules=@PER-CS2.0
   ```

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Optimasi Autoloader di Production Docker Container
Jangan pernah menjalankan runtime production menggunakan autoloader standar development. Jalankan perintah optimasi berikut saat proses container compilation (Dockerfile multi-stage build):

```dockerfile
# Dockerfile snippet
RUN composer install --no-dev --prefer-dist --no-interaction \
    --optimize-autoloader \
    --classmap-authoritative \
    --apcu-autoloader
```

### Analisis Parameter:
1. `--optimize-autoloader` (`-o`): Mengonversi aturan PSR-4/PSR-0 menjadi array statis `autoload_classmap.php`. Menghemat traversal filesystem.
2. `--classmap-authoritative` (`-a`): Memberitahu PHP engine bahwa *seluruh* class sistem HANYA ada di classmap. Jika class tidak ditemukan di classmap, Composer langsung melempar error **tanpa** mengecek filesystem menggunakan fallback rules PSR-4. Ini mengeliminasi 100% filesystem I/O misses.
3. `--apcu-autoloader`: Memanfaatkan shared memory APCu untuk caching fallback autoloader lookup (berguna jika tidak bisa menggunakan `--classmap-authoritative`).

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Audit Kerentanan Dependensi (CVE Detection)
Tambahkan static scanning dependensi dalam CI/CD pipeline menggunakan Composer Native Audit Engine:
```bash
composer audit --format=json
```
Perintah ini mengecek seluruh *dependency tree* terhadap database kerentanan keamanan publik (Packagist Advisory Database). CI HARUS menggagalkan build (*fail pipeline*) jika ditemukan tingkat keparahan minimum `HIGH`.

### 2. Membatasi Eksekusi Composer Plugin Hook
Composer plugin memiliki akses eksekusi script arbitrary shell pada server. Batasi izin eksekusi plugin secara ketat pada `composer.json`:
```json
"config": {
    "allow-plugins": {
        "phpstan/extension-installer": true,
        "dealerdirect/phpcodesniffer-composer-installer": false
    }
}
```
Setiap plugin baru yang masuk dependensi tidak boleh tereksekusi tanpa izin eksplisit dalam konfigurasi tersebut.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Ketika autoloader gagal menemukan simbol atau terjadi resolusi kelas ganda yang membingungkan:

### 1. Memeriksa Dynamic Path Mapping
Jalankan command internal Composer untuk menelusuri lokasi fisik pemetaan class:
```bash
composer dump-autoload -vvv
```

### 2. Runtime Debugging Autoloader Lookup
Gunakan script verifikasi runtime untuk menganalisis autoloader stack:
```php
<?php

declare(strict_types=1);

require_once __DIR__ . '/vendor/autoload.php';

$className = \Enterprise\PaymentGateway\Provider\StripePaymentGateway::class;

// 1. Tampilkan seluruh autoloader stack terdaftar
$autoloaders = spl_autoload_functions();
echo "Total Registered Autoloaders: " . count($autoloaders) . PHP_EOL;

// 2. Evaluasi apakah class sudah tersimpan di Classmap Composer
$classMap = require __DIR__ . '/vendor/composer/autoload_classmap.php';
if (array_key_exists($className, $classMap)) {
    echo "Class found in Static Classmap: " . $classMap[$className] . PHP_EOL;
} else {
    echo "Class NOT in Classmap. Autoloader will rely on PSR-4 dynamic fallback." . PHP_EOL;
}

// 3. Tes refleksi instansiasi
try {
    $reflection = new ReflectionClass($className);
    echo "Class File Resolved to: " . $reflection->getFileName() . PHP_EOL;
} catch (ReflectionException $e) {
    echo "Autoload Failure: " . $e->getMessage() . PHP_EOL;
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **PSR-1/PER-CS**: Konsistensi gaya penulisan kode, zero side-effects saat require/include.
* **PSR-4**: Autoloading deklaratif berbasis hierarki FQCN ke filesystem paths.
* **PSR-7 & PSR-18**: Abstraksi standard HTTP Message (Immutable) & HTTP Client interface.
* **PSR-11**: Kontrak minimum Dependency Injection Container (`get()`, `has()`).
* **Semantic Versioning**:
  * $X.y.z$ $\implies$ MAJOR (Breaking change).
  * $x.Y.z$ $\implies$ MINOR (Fitur baru, non-breaking).
  * $x.y.Z$ $\implies$ PATCH (Bug fix, non-breaking).
* **Production Deployment Flags**:
  `composer install --no-dev -o -a` adalah konfigurasi autoloader tercepat dan teraman untuk production.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Basic (5 Soal)

1. **Apa perbedaan fungsional utama antara direktori `autoload` dan `autoload-dev` pada file `composer.json`?**
   * A. `autoload` digunakan untuk PHP >= 8.0, sedangkan `autoload-dev` untuk versi legacy.
   * B. `autoload-dev` hanya dieksekusi ketika flag `--no-dev` disertakan.
   * C. `autoload-dev` di-load untuk testing/development, dan diabaikan ketika package di-install sebagai dependency di project lain atau saat flag `--no-dev` digunakan.
   * D. Tidak ada perbedaan, keduanya digabung secara identik saat production release.

2. **Diberikan konfigurasi PSR-4: `{"Acme\\Service\\": "src/"}`. File mana yang akan di-include secara otomatis oleh Composer jika class `\Acme\Service\Auth\TokenValidator` dipanggil?**
   * A. `src/Auth/TokenValidator.php`
   * B. `src/Service/Auth/TokenValidator.php`
   * C. `src/Acme/Service/Auth/TokenValidator.php`
   * D. `src/Acme/Auth/TokenValidator.php`

3. **Prinsip desain utama apa yang diwajibkan oleh PSR-7 pada objek HTTP Request dan Response?**
   * A. Mutable Singleton
   * B. Immutability (Objek tidak dapat diubah setelah diinstansiasi)
   * C. Synchronous Active Record
   * D. Static Factory Pattern

4. **Karakter operator versi manakah yang mengizinkan update minor dan patch tetapi melarang major breaking release (misal: `>=1.4.0 <2.0.0`)?**
   * A. `~1.4.0`
   * B. `*1.4.0`
   * C. `^1.4.0`
   * D. `@1.4.0`

5. **Apa fungsi utama dari PSR-11?**
   * A. Menetapkan format JSON untuk Composer.
   * B. Menyediakan interface standar untuk Dependency Injection Container.
   * C. Mengatur penamaan migration database.
   * D. Menangani enkripsi password secara kriptografis.

---

### Soal Tingkat Intermediate (5 Soal)

6. **Apa dampak arsitektur dari pengaktifan flag `--classmap-authoritative` saat menjalankan build di server production?**
   * A. Semua file PHP dikompilasi menjadi bytecode C secara permanen.
   * B. Composer mengabaikan seluruh aturan dinamis PSR-4; jika file class tidak ada di classmap hash array, sistem langsung gagal tanpa pengecekan filesystem I/O.
   * C. Composer mengizinkan eksekusi plugin arbitrary tanpa otentikasi.
   * D. Dependensi `require-dev` dipaksa ter-install ke dalam production.

7. **Sebuah class melempar exception saat resolving di container. Berdasarkan standar PSR-11, tipe exception apa yang HARUS ditangkap oleh pemanggil untuk menangani semua kemungkinan internal container error?**
   * A. `\RuntimeException`
   * B. `\Psr\Container\ContainerExceptionInterface`
   * C. `\Psr\Container\NotFoundExceptionInterface`
   * D. `\Error`

8. **Jika package A membutuhkan `vendor/lib: ^1.2` dan package B membutuhkan `vendor/lib: ^2.0`, tindakan apa yang dilakukan oleh SAT Solver Composer?**
   * A. Menginstal kedua versi secara bersamaan di sub-folder vendor yang terpisah.
   * B. Memilih versi tertinggi (`^2.0`) dan mengabaikan requirement package A.
   * C. Menghentikan instalasi dan memberikan pesan galat konflik dependensi yang tidak terpecahkan.
   * D. Melakukan fallback otomatis ke versi `1.0.0`.

9. **Mengapa modifikasi file di dalam direktori `vendor/` secara langsung dianggap sebagai antipattern fatal dalam rekayasa perangkat lunak PHP modern?**
   * A. Karena PHP runtime akan memblokir perubahan tersebut via proteksi read-only filesystem.
   * B. Karena perubahan akan hilang seketika saat perintah `composer install` atau `composer update` berikutnya dijalankan.
   * C. Karena syntax PHP modern tidak diizinkan berada di sub-folder vendor.
   * D. Karena direktori `vendor/` dienkripsi secara default oleh Composer.

10. **Manakah dari perubahan interface berikut yang dianggap sebagai BREAKING CHANGE menurut Semantic Versioning (SemVer) jika package Anda sudah mencapai status rilis stabil (`>= 1.0.0`)?**
    * A. Menambahkan method baru ke dalam interface publik yang sudah ada.
    * B. Memperbaiki bug logic internal di class implementor tanpa mengubah parameter atau return type.
    * C. Menambahkan class implementasi baru ke dalam namespace package.
    * D. Memperbarui dependensi dev PHPUnit ke versi yang lebih baru.

---

### Kunci Jawaban & Pembahasan

1. **C**: Konfigurasi `autoload-dev` ditujukan khusus untuk development tooling dan unit tests. Ketika package diunduh oleh aplikasi lain sebagai dependensi root, Composer secara otomatis mengabaikan aturan `autoload-dev` package tersebut untuk efisiensi memori.
2. **A**: Prefix `Acme\Service\` dipetakan ke root `src/`. Oleh karena itu, sub-namespace berikutnya `Auth\TokenValidator` dikonversi menjadi sub-direktori `Auth/TokenValidator.php` di dalam `src/`.
3. **B**: Objek PSR-7 bersifat *immutable*. Setiap modifikasi (misal: `withHeader()`) menghasilkan salinan (*clone*) baru dari objek tersebut, mencegah bug efek samping mutasi state antar-middleware.
4. **C**: Caret operator (`^`) mengunci angka paling kiri yang bukan nol. Untuk `^1.4.0`, batasan versinya adalah `>=1.4.0 <2.0.0`. Sebaliknya, `~1.4.0` mengunci minor version (`>=1.4.0 <1.5.0`).
5. **B**: PSR-11 menetapkan `ContainerInterface` yang menyediakan method `get()` dan `has()`, memungkinkan abstraksi dependensi decoupling dari service locator atau container framework tertentu.
6. **B**: `--classmap-authoritative` mematikan mekanisme *filesystem scanning fallback* PSR-4. Autoloader hanya mengandalkan hash map array. Memberikan performa eksekusi tertinggi di production, namun memerlukan rebuild classmap setiap ada penambahan class.
7. **B**: `ContainerExceptionInterface` adalah base interface untuk seluruh exception yang dilempar oleh PSR-11 container. `NotFoundExceptionInterface` sendiri mengekstensi `ContainerExceptionInterface`.
8. **C**: PHP tidak mendukung class multiversion runtime di thread/address space yang sama. Composer memetakan ini sebagai kontradiksi logika pada SAT Solver, membatalkan operasi, dan mencetak conflict graph.
9. **B**: Direktori `vendor/` bersifat *ephemeral* dan dikelola penuh oleh package manager. Setiap kali eksekusi resolusi dependencies, file di dalamnya dapat dihapus, diganti, atau di-rewrite.
10. **A**: Menambahkan method baru pada interface yang telah dipublikasikan akan merusak seluruh implementasi konkret pihak ketiga yang meng-implement interface tersebut (menyebabkan fatal error karena class belum mengimplementasikan method baru tersebut). Ini adalah breaking change yang mewajibkan bump versi **MAJOR**.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Rancang & Bangun Framework-Agnostic Rate Limiter Package

#### Instruksi Proyek:
Anda ditugaskan merancang modular package independen bernama `enterprise/traffic-shield`. Package ini bertindak sebagai token bucket rate limiter yang framework-agnostic.

#### Kebutuhan Fungsional & Spesifikasi Teknis:
1. **Inisialisasi Project:**
   * Buat struktur direktori terpisah dengan standar tata letak Composer modern:
     ```text
     traffic-shield/
     ├── composer.json
     ├── src/
     │   ├── Contract/
     │   │   ├── StorageAdapterInterface.php
     │   │   └── RateLimiterInterface.php
     │   ├── Exception/
     │   │   └── RateLimitExceededException.php
     │   ├── Storage/
     │   │   └── InMemoryStorageAdapter.php
     │   └── TokenBucketLimiter.php
     └── tests/
         └── TokenBucketLimiterTest.php
     ```
2. **Kepatuhan PSR:**
   * Wajib mengikuti **PSR-12 / PER Coding Style 2.0**.
   * Integrasikan logging status limitasi menggunakan **PSR-3 (LoggerInterface)**.
   * Konfigurasi PSR-4 autoloading di `composer.json` dengan namespace `Enterprise\TrafficShield\`.
3. **Core Engine:**
   * `StorageAdapterInterface` harus mendefinisikan method atomik: `get(string $key): int`, `set(string $key, int $value, int $ttl): void`.
   * `RateLimiterInterface` harus mengekspos: `public function hit(string $identifier, int $maxRequests, int $decaySeconds): void`.
   * Jika batas rate limit terlampaui, lemparkan custom exception: `RateLimitExceededException` yang menyertakan informasi metadata `$retryAfterSeconds`.
4. **Verifikasi Quality Gate:**
   * Tulis unit test komprehensif menggunakan PHPUnit minimum 3 skenario: *Allowed Request*, *Blocked Request on Limit Hit*, dan *State Restoration after TTL*.
   * Eksekusi dump autoloader dengan optimasi mode:
     ```bash
     composer dump-autoload --optimize --classmap-authoritative
     ```
   * Verifikasi integritas autoloader yang dihasilkan dengan menjalankan test suite tanpa runtime warnings.