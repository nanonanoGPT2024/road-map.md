# BAB-02: Advanced Object-Oriented PHP & Metaprogramming
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis Internal Zend Engine**: Membedah representasi objek, `zend_class_entry`, alokasi `zval`, serta siklus hidup kompilasi atribut ke dalam memori OPcache.
2. **Merancang Custom Metaprogramming Engines**: Mengimplementasikan arsitektur *Aspect-Oriented Programming* (AOP) dan *Dynamic Proxy Generation* memanfaatkan PHP 8.2+ Attributes dan Reflection API dengan latensi minimal.
3. **Mengoptimalkan Performa Runtime Reflection**: Menerapkan teknik *metadata caching*, *bytecode preloading*, dan *warm-up compilation* guna mengeliminasi penalti eksekusi refleksi dinamis pada aplikasi ber-throughput tinggi (>50.000 RPS).
4. **Membangun Enterprise Dependency Injection & Interception Framework**: Mengintegrasikan atribut deklaratif untuk transaksi database, audit logging, dan validasi tanpa mengotori domain logic (*Separation of Concerns*).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib memahami:
* Konsep OOP lanjutan: Pewarisan, Polimorfisme, Trait, Interface Segregation, dan Late Static Binding (`static::` vs `self::`).
* Sintaks modern PHP 8.x: First-class callable syntax, Named Arguments, Constructor Promotion, Readonly Classes, Union & Intersection Types.
* Memori dasar PHP: Siklus hidup request stateless PHP-FPM, pemanfaatan OPcache dasar, dan Composer Autoloading (PSR-4).

---

### 3. Concept & Internal Architecture (Mendalam)

#### Representasi Objek pada Zend Virtual Machine (Zend VM)
Pada level C internal PHP (Zend Engine), sebuah kelas didefinisikan sebagai struktur `zend_class_entry` (`ce`), sedangkan setiap instance dari kelas tersebut dialokasikan dalam *object store* (`zend_objects_store`) dan direpresentasikan sebagai pointer `zend_object`.

```
                    Zend Engine Internal Structure
  +---------------------------------------------------------------+
  |                      zend_class_entry                         |
  |  - name: zend_string*                                         |
  |  - type: ZEND_USER_CLASS | ZEND_INTERNAL_CLASS                |
  |  - function_table: HashTable (zend_function*)                 |
  |  - properties_info: HashTable (zend_property_info*)           |
  |  - constants_table: HashTable (zend_class_constant*)          |
  |  - attributes: HashTable (zend_attribute*)                    |
  +---------------------------------------------------------------+
                                  ^
                                  | ce pointer
  +-------------------------------+-------------------------------+
  |                        zend_object                            |
  |  - gc: zend_refcounted_h                                      |
  |  - handle: uint32_t (Index pada zend_objects_store)           |
  |  - ce: zend_class_entry*                                      |
  |  - handlers: const zend_object_handlers*                      |
  |  - properties_table: zval[1] (Flexible Array Member)          |
  +---------------------------------------------------------------+
```

Ketika objek dibuat (`$instance = new OrderService();`):
1. **Alokasi Heap**: Zend Engine memanggil `zend_objects_new()` yang mengalokasikan blok memori seukuran `sizeof(zend_object) + (sizeof(zval) * (ce->default_properties_count - 1))`.
2. **Object Handle Registration**: Pointer objek didaftarkan ke `EG(objects_store).object_buckets` untuk manajemen garbage collection (`gc`) dan pelacakan *cyclical reference*.
3. **Direct Property Slot**: Properti internal tidak disimpan dalam `HashTable` hashmap string, melainkan diakses melalui *offset indeks integer* terkompilasi (`properties_table`) yang merujuk pada `properties_info`.

#### Mekanisme Atribut PHP 8+ vs Metadata Komentar Tradisional
Dahulu, metadata deklaratif diekstrak dari DocBlock (`/** @Annotation */`) menggunakan regex parsing via library pihak ketiga (*Doctrine Annotations*). Pendekatan ini tidak efisien karena:
* Mengharuskan string parsing runtime berulang.
* Rentan terhadap *OPcache comment stripping* (`opcache.save_comments=0`).
* Tidak memiliki type safety dan validation saat parsing AST.

Pada PHP 8+, **Attributes** adalah *first-class language citizens*:
1. **Compilation Phase**: Parser Zend VM mengonversi sintaks `#[MyAttribute(param: 'value')]` menjadi struktur `zend_attribute` yang disimpan langsung di dalam pointer `zend_class_entry->attributes`, `zend_function->attributes`, atau `zend_property_info->attributes`.
2. **OPcache Persistence**: Jika OPcache aktif, struktur `zend_attribute` diintern ke dalam *shared memory* (SHM) bersama *bytecode/opcodes*.
3. **Lazy Instantiation**: Memanggil `ReflectionClass::getAttributes()` tidak menginstansiasi objek atribut secara instan. Zend Engine hanya mengembalikan array `ReflectionAttribute`. Instansiasi kelas atribut baru dieksekusi ketika method `ReflectionAttribute::newInstance()` dipanggil secara eksplisit oleh runtime engine Anda.

---

### 4. Why & What

| Paradigma | Implementasi Tradisional | Metaprogramming Terstruktur (Attributes + Reflection + Proxy) |
| :--- | :--- | :--- |
| **Cross-Cutting Concerns** | Logika transaksi, logging, dan metrik ditempelkan manual di dalam *Domain Service*. Menghasilkan *spaghetti code* dan duplikasi tinggi. | Dideklarasikan via Atribut (`#[Transactional]`, `#[AuditLog]`). Engine proxy mencegat (*intercept*) eksekusi tanpa mengubah isi business logic. |
| **Dependency Injection** | Binding manual berbasis konfigurasi array XML/YAML besar yang sulit di-refactor secara statis. | Menggunakan *Attribute-based Autowiring*. Resolusi metadata dilakukan via reflection satu kali saat container compile-time. |
| **Maintenance & Clarity** | Logika tersembunyi di framework layer terpisah atau tersebar di banyak helper. | Deklarasi intensi terlihat langsung di deklarasi class, property, atau method (*Self-describing code*). |

---

### 5. How (Workflow Detail)

Alur kerja eksekusi AOP dinamis berbasis Atribut dan Dynamic Proxy:

```
  Client Code
       │
       ▼
 [Proxy Object] ────> intercepts call via __call() / Dynamic Subclass
       │
       ├─► 1. Trigger Aspect Engine: Pipeline Interceptor
       │        ├─► Eksekusi Pre-Handlers (e.g., #[RateLimit], #[Authorize])
       │        └─► Eksekusi Transaction Start (e.g., #[Transactional])
       │
       ├─► 2. Invocation: Panggil method target asli pada Target Instance
       │        └─► Tangkap Return Value atau Tangkap Exception
       │
       ├─► 3. Post-Handlers:
       │        ├─► Commit DB / Rollback DB jika Exception
       │        └─► Eksekusi Logging (e.g., #[AuditLog])
       │
       └─► Return Hasil ke Client
```

---

### 6. Analogy & Diagram ASCII

Bayangkan sebuah **Bank Brankas (Target Class)**:
* **Direct Call (Tanpa Metaprogramming)**: Nasabah langsung masuk ke ruang brankas, menghitung uang sendiri, mencatat log sendiri, mengunci pintu sendiri. Jika nasabah lupa mengunci, sistem kolaps.
* **Metaprogramming / Dynamic Proxy**: Nasabah berbicara dengan **Teller Kaca (Proxy)**. Di kaca terpasang stiker aturan: `#[PeriksaKTP]`, `#[CatatBukuBank]`.
* Teller membaca stiker (Reflection atas Atribut), menjalankan validasi KTP, lalu membukakan brankas di balik tirai (Target Instance), dan mencatat transaksi secara otomatis setelah brankas ditutup kembali.

```
+───────────────────────────────────────────────────────────────+
|                          RUNTIME MEMORY                       |
|                                                               |
|  [Client]                                                     |
|     │                                                         |
|     ▼                                                         |
|  [Dynamic Proxy: BankAccountProxy]                            |
|     ├── Implements: BankAccountInterface                      |
|     ├── Holds: Target -> BankAccountInstance                  |
|     │                                                         |
|     ├── Method: transfer(...)                                 |
|     │     │                                                   |
|     │     ├── InterceptorRegistry::execute(target, method)    |
|     │     │     │                                             |
|     │     │     ├── (Attribute) #[Transactional]              |
|     │     │     │     └─► PDO::beginTransaction()             |
|     │     │     │                                             |
|     │     │     ├── Invocation::proceed() ──────────────────┐ |
|     │     │     │                                           │ |
|     │     │     │   ┌──────────────────────────────────┐    │ |
|     │     │     │   │ Target: BankAccountInstance      │    │ |
|     │     │     │   │   └─► Eksekusi Logic Domain      │◄───┘ |
|     │     │     │   └──────────────────────────────────┘      |
|     │     │     │                                             |
|     │     │     ├── (Attribute) #[Transactional]              |
|     │     │     │     └─► PDO::commit()                       |
|     │     │     │                                             |
|     │     │     └─► Return result                             |
+───────────────────────────────────────────────────────────────+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Custom Attribute & Reflection Extraction
Memahami siklus hidup dasar definisi dan pembacaan atribut pada runtime.

```php
<?php

declare(strict_types=1);

namespace App\Foundation\Attributes;

use Attribute;
use ReflectionClass;

#[Attribute(Attribute::TARGET_PROPERTY | Attribute::TARGET_PARAMETER)]
final readonly class SensitiveData
{
    public function __construct(
        public string $maskCharacter = '*',
        public int $visibleSuffixLength = 4
    ) {}
}

final class UserProfile
{
    public function __construct(
        public string $username,
        #[SensitiveData(maskCharacter: '#', visibleSuffixLength: 3)]
        public string $taxIdentificationNumber
    ) {}
}

// Runtime Inspector
$user = new UserProfile('johndoe', 'ID-994828190-X');
$reflector = new ReflectionClass($user);

foreach ($reflector->getProperties() as $property) {
    $attributes = $property->getAttributes(SensitiveData::class);
    
    if (!empty($attributes)) {
        /** @var SensitiveData $meta */
        $meta = $attributes[0]->newInstance();
        $rawValue = (string) $property->getValue($user);
        
        $maskedLength = max(0, strlen($rawValue) - $meta->visibleSuffixLength);
        $maskedValue = str_repeat($meta->maskCharacter, $maskedLength) 
            . substr($rawValue, -$meta->visibleSuffixLength);
            
        echo "Property {$property->getName()}: {$maskedValue}\n";
    }
}
```

#### B. Practical Enterprise Example: AOP Transactional & Logging Proxy Generator
Implementasi *dynamic proxy* berbasis interface untuk membungkus operasi database enterprise tanpa merusak SRP (*Single Responsibility Principle*).

```php
<?php

declare(strict_types=1);

namespace App\Infrastructure\Aop;

use Attribute;
use ReflectionClass;
use ReflectionMethod;
use Throwable;
use RuntimeException;
use Psr\Log\LoggerInterface;
use PDO;

#[Attribute(Attribute::TARGET_METHOD)]
final readonly class Transactional
{
    public function __construct(
        public int $retryAttempts = 1,
        public string $isolationLevel = 'READ COMMITTED'
    ) {}
}

#[Attribute(Attribute::TARGET_METHOD)]
final readonly class TimedMetric
{
    public function __construct(public string $metricKey) {}
}

interface PaymentProcessorInterface
{
    public function processSettlement(string $orderId, int $amountInCents): bool;
}

final class PaymentProcessor implements PaymentProcessorInterface
{
    public function __construct(private PDO $db) {}

    #[Transactional(retryAttempts: 3)]
    #[TimedMetric(metricKey: 'payment.settlement.latency')]
    public function processSettlement(string $orderId, int $amountInCents): bool
    {
        // Simulasi mutasi database kritis
        $stmt = $this->db->prepare("UPDATE accounts SET balance = balance - :amount WHERE id = :id");
        $stmt->execute(['amount' => $amountInCents, 'id' => $orderId]);
        
        if ($amountInCents > 1_000_000_00) { // Limit trigger simulasi
            throw new RuntimeException("Suspicious settlement threshold exceeded.");
        }

        return true;
    }
}

/**
 * Enterprise Dynamic Proxy Interceptor Engine
 */
final class AspectProxyEngine
{
    /**
     * @template T of object
     * @param class-string<T> $interface
     * @param T $target
     * @return T
     */
    public static function createProxy(
        string $interface, 
        object $target, 
        PDO $db, 
        LoggerInterface $logger
    ): object {
        return new class($target, $db, $logger) implements PaymentProcessorInterface {
            private object $target;
            private PDO $db;
            private LoggerInterface $logger;
            private ReflectionClass $reflection;

            public function __construct(object $target, PDO $db, LoggerInterface $logger)
            {
                $this->target = $target;
                $this->db = $db;
                $this->logger = $logger;
                $this->reflection = new ReflectionClass($target);
            }

            public function processSettlement(string $orderId, int $amountInCents): bool
            {
                $methodName = 'processSettlement';
                $refMethod = $this->reflection->getMethod($methodName);
                
                $transactionalAttr = $refMethod->getAttributes(Transactional::class)[0] ?? null;
                $metricAttr = $refMethod->getAttributes(TimedMetric::class)[0] ?? null;

                $startTime = microtime(true);
                $attempts = 0;
                $maxAttempts = $transactionalAttr ? $transactionalAttr->newInstance()->retryAttempts : 1;

                while ($attempts < $maxAttempts) {
                    $attempts++;
                    try {
                        if ($transactionalAttr !== null) {
                            $this->db->beginTransaction();
                        }

                        // Eksekusi logic aktual
                        $result = $this->target->processSettlement($orderId, $amountInCents);

                        if ($transactionalAttr !== null) {
                            $this->db->commit();
                        }

                        $this->logMetrics($metricAttr, $startTime);
                        return $result;
                    } catch (Throwable $e) {
                        if ($transactionalAttr !== null && $this->db->inTransaction()) {
                            $this->db->rollBack();
                        }

                        $this->logger->error("AOP Intercepted Failure on {$methodName}", [
                            'attempt' => $attempts,
                            'error' => $e->getMessage(),
                            'order_id' => $orderId
                        ]);

                        if ($attempts >= $maxAttempts) {
                            $this->logMetrics($metricAttr, $startTime);
                            throw $e;
                        }
                    }
                }

                throw new RuntimeException("Exhausted retry attempts without resolution.");
            }

            private function logMetrics(?\ReflectionAttribute $metricAttr, float $startTime): void
            {
                if ($metricAttr === null) {
                    return;
                }
                
                $duration = (microtime(true) - $startTime) * 1000;
                /** @var TimedMetric $metric */
                $metric = $metricAttr->newInstance();
                $this->logger->info("[Metric] {$metric->metricKey}: {$duration}ms");
            }
        };
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Arsitektur FinTech Core Banking dengan rata-rata beban 65.000 RPS. Sistem memerlukan pelacakan audit terdistribusi secara *strict* (*zero-omission*) pada setiap mutasi saldo, perubahan data nasabah, dan otorisasi limit pinjaman. 

#### Tantangan Teknis
1. Developer sering lupa memanggil fungsi audit dispatcher secara manual di tingkat controller atau domain layer.
2. Penggunaan Reflection murni di setiap HTTP request menambahkan latensi +4.8ms per request, menurunkan kapasitas konkurensi PHP-FPM.

#### Solusi Arsitektur
Membangun **Compile-Time Pre-generated Proxy Pipeline**.
1. **Developer Level**: Menempelkan atribut `#[AuditLog(topic: 'ledger_mutation')]` pada method service.
2. **Build / CI/CD Phase**: Script pre-compiler membaca seluruh kelas domain, mengurai atribut reflection, dan men-generate kelas Proxy fisik ke disk (`Generated/Proxies/OrderServiceProxy.php`), bukan dievaluasi secara dinamis saat runtime.
3. **Runtime Phase**: DIC Container secara otomatis menginjeksi instance proxy fisik ter-generate tersebut. OPcache memuat file proxy secara langsung sebagai *pure compiled C-bytecode*.

```
   [Build Pipeline: composer compile-metadata]
                       │
                       ▼
         [Reflection & Attribute Scanner]
                       │
                       ▼
       [Code Generator: AST/String Templating]
                       │
                       ▼
    [Write to Disk: /var/cache/proxies/*.php]
                       │
                       ▼
    [PHP-FPM Production Runtime: O(1) Overhead via OPcache]
```

Hasil:
* **Overhead Reflection di Runtime**: Turun dari 4.8ms menjadi **0.00ms** (Zero dynamic reflection during request lifecycle).
* **Coverage Audit**: 100% konsisten, terstandarisasi, dan terbebas dari kelalaian *human-error*.

---

### 9. Trade-offs

| Dimensi | Dynamic Reflection Runtime | Pre-compiled Proxy Generation | Magic Methods Interception (`__call`) |
| :--- | :--- | :--- | :--- |
| **Throughput & Latency** | **Rendah**: Panggilan berulang `ReflectionClass::newInstance()` memakan alokasi heap dan CPU cycles per-request. | **Tinggi (Near Native)**: Tidak ada overhead refleksi; dieksekusi sebagai plain bytecode via OPcache. | **Menengah-Rendah**: Eksekusi `__call` memotong opcode optimasi VM, bypassing JIT inlining. |
| **Scalability** | Skalabilitas CPU tertekan saat beban tinggi; memerlukan instance PHP-FPM lebih banyak. | Skalabilitas optimal; pemakaian CPU terpusat murni pada domain logic. | Meningkatkan memory overhead karena kegagalan resolusi symbol cache pada Zend engine. |
| **Developer DX** | **Sangat Baik**: Cukup pasang atribut, langsung jalan tanpa step kompilasi manual. | **Menengah**: Membutuhkan command warm-up saat build deployment (`composer compile-proxies`). | **Buruk**: Hilangnya autocomplete IDE, static analysis (PHPStan/Psalm) menjadi sangat rumit. |
| **Cold-Start Penalty** | Nol saat deployment, namun lambat di *first-hit*. | Membutuhkan waktu beberapa detik saat proses CI/CD build deployment. | Nol, namun lambat secara konsisten di seluruh request. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Menjalankan Reflection di Dalam Perulangan (Loop)
*Bad Practice:*
```php
foreach ($thousandsOfEntities as $entity) {
    // FATAL: Menginisialisasi Reflection engine pada setiap iterasi loop!
    $reflector = new ReflectionClass($entity);
    $attr = $reflector->getAttributes(Serializable::class);
}
```
*Remediasi (Memoization/Static Cache):*
```php
// Simpan instance refleksi berdasarkan Class Name string key
static $reflectionCache = [];
$class = $entity::class;
$reflector = $reflectionCache[$class] ??= new ReflectionClass($class);
```

#### 2. Ketiadaan Penanganan Tipe Objek Bersarang (Nested Circular References)
Saat membangun object-mapper berbasis reflection, rekursi tanpa pelacakan memori akan menyebabkan *Maximum function nesting level* atau *Segmentation Fault*.
*Remediasi*: Simpan stack array `$visitedInstances = new \SplObjectStorage()` untuk mendeteksi *identity loop* sebelum melakukan rekursi parsing metadata.

#### 3. Rusaknya Metadata Akibat Konfigurasi OPcache
Pada deployment Docker production:
```ini
; FATAL: Mengakibatkan getAttributes() dan DocBlocks bernilai kosong!
opcache.save_comments=0
```
*Remediasi*: Pastikan konfigurasi pada `php.ini` production selalu:
```ini
opcache.save_comments=1
```
*(Catatan: Atribut internal PHP 8 disimpan sebagai token terpisah, namun menjaga `save_comments=1` tetap vital jika sistem beroperasi dalam lingkungan hybrid atau menggunakan legacy annotations).*

---

### 11. Best Practices (Production Checklist)

- [ ] **Strict Typing**: Seluruh file metaprogramming wajib menyertakan `declare(strict_types=1);`.
- [ ] **Immutable Attributes**: Selalu deklarasikan kelas atribut dengan flag `final readonly class`.
- [ ] **Attribute Target Scoping**: Batasi target penggunaan atribut secara spesifik menggunakan bitwise operator (contoh: `#[Attribute(Attribute::TARGET_METHOD | Attribute::TARGET_FUNCTION)]`).
- [ ] **Proxy Cache Warming**: Jangan pernah mengevaluasi kode proxy dinamis dengan `eval()` di lingkungan production. Tulis output ke file fisik dan masukkan ke OPcache.
- [ ] **PHPStan / Psalm Integration**: Sediakan extension statis (misal: *PHPStan Class Reflection Extension*) agar static analyzer mengenali method yang disuntikkan secara dinamis oleh proxy.
- [ ] **Fail-Fast Initialization**: Lakukan validasi parameter atribut di dalam constructor atribut itu sendiri, bukan saat interceptor engine berjalan.

---

### 12. Hands-on Practice

Buatlah proyek pengujian metaprogramming lokal pada workspace Anda.

#### Struktur Direktori
```text
hands-on/m02/
├── composer.json
├── src/
│   ├── Attributes/
│   │   └── Cacheable.php
│   ├── Interceptor/
│   │   └── CachingProxyGenerator.php
│   └── Service/
│       ├── UserRepositoryInterface.php
│       └── UserRepository.php
└── test_proxy.php
```

#### Langkah 1: Inisialisasi Composer
Simpan di `hands-on/m02/composer.json`:
```json
{
  "name": "enterprise/metaprogramming-deepdive",
  "require": {
    "php": ">=8.2"
  },
  "autoload": {
    "psr-4": {
      "App\\": "src/"
    }
  }
}
```
Jalankan di terminal:
```bash
composer dump-autoload
```

#### Langkah 2: Buat Definisi Atribut
Simpan di `hands-on/m02/src/Attributes/Cacheable.php`:
```php
<?php

declare(strict_types=1);

namespace App\Attributes;

use Attribute;

#[Attribute(Attribute::TARGET_METHOD)]
final readonly class Cacheable
{
    public function __construct(
        public int $ttlInSeconds = 60,
        public string $cachePrefix = 'default'
    ) {}
}
```

#### Langkah 3: Definisikan Kontrak dan Target Service
Simpan di `hands-on/m02/src/Service/UserRepositoryInterface.php`:
```php
<?php

declare(strict_types=1);

namespace App\Service;

interface UserRepositoryInterface
{
    public function findById(int $id): array;
}
```

Simpan di `hands-on/m02/src/Service/UserRepository.php`:
```php
<?php

declare(strict_types=1);

namespace App\Service;

use App\Attributes\Cacheable;

final class UserRepository implements UserRepositoryInterface
{
    #[Cacheable(ttlInSeconds: 300, cachePrefix: 'user_entity')]
    public function findById(int $id): array
    {
        // Simulasi query lambat I/O
        usleep(200_000); // 200ms
        return [
            'id' => $id,
            'name' => 'Alice Developer',
            'role' => 'Enterprise Architect'
        ];
    }
}
```

#### Langkah 4: Bangun Interceptor Proxy Generator
Simpan di `hands-on/m02/src/Interceptor/CachingProxyGenerator.php`:
```php
<?php

declare(strict_types=1);

namespace App\Interceptor;

use App\Attributes\Cacheable;
use ReflectionClass;
use ReflectionMethod;

final class CachingProxyGenerator
{
    /**
     * @template T of object
     * @param class-string<T> $interface
     * @param T $target
     * @return T
     */
    public static function createProxy(string $interface, object $target): object
    {
        return new class($target) implements \App\Service\UserRepositoryInterface {
            private object $target;
            private array $inMemoryCache = [];
            private ReflectionClass $reflector;

            public function __construct(object $target)
            {
                $this->target = $target;
                $this->reflector = new ReflectionClass($target);
            }

            public function findById(int $id): array
            {
                $method = $this->reflector->getMethod('findById');
                $attributes = $method->getAttributes(Cacheable::class);

                if (empty($attributes)) {
                    return $this->target->findById($id);
                }

                /** @var Cacheable $config */
                $config = $attributes[0]->newInstance();
                $cacheKey = "{$config->cachePrefix}:{$id}";

                if (isset($this->inMemoryCache[$cacheKey])) {
                    $entry = $this->inMemoryCache[$cacheKey];
                    if ($entry['expires_at'] > microtime(true)) {
                        echo "[CACHE HIT] Ambil dari cache: {$cacheKey}\n";
                        return $entry['payload'];
                    }
                }

                echo "[CACHE MISS] Query target aktual...\n";
                $result = $this->target->findById($id);

                $this->inMemoryCache[$cacheKey] = [
                    'payload' => $result,
                    'expires_at' => microtime(true) + $config->ttlInSeconds
                ];

                return $result;
            }
        };
    }
}
```

#### Langkah 5: Eksekusi File Driver
Simpan di `hands-on/m02/test_proxy.php`:
```php
<?php

declare(strict_types=1);

require_once __DIR__ . '/vendor/autoload.php';

use App\Service\UserRepository;
use App\Service\UserRepositoryInterface;
use App\Interceptor\CachingProxyGenerator;

$realRepository = new UserRepository();
/** @var UserRepositoryInterface $proxiedRepo */
$proxiedRepo = CachingProxyGenerator::createProxy(
    UserRepositoryInterface::class, 
    $realRepository
);

$start = microtime(true);
$data1 = $proxiedRepo->findById(42);
$latency1 = (microtime(true) - $start) * 1000;
printf("Panggilan 1 selesai dalam: %.2f ms\n", $latency1);

$start = microtime(true);
$data2 = $proxiedRepo->findById(42);
$latency2 = (microtime(true) - $start) * 1000;
printf("Panggilan 2 selesai dalam: %.2f ms\n", $latency2);

assert($data1 === $data2);
```

Jalankan:
```bash
php test_proxy.php
```

---

### 13. Exercise

#### Level Easy
Buat atribut `#[ValidateString(minLength: 5, maxLength: 20)]`. Buat fungsi validator `validateObject(object $dto): void` yang mengekstrak seluruh properti bertipe string dan melemparkan `InvalidArgumentException` jika batasan panjang string dilanggar.

#### Level Medium
Buat atribut `#[CircuitBreaker(failureThreshold: 3, resetTimeoutSeconds: 5)]`. Bangun interceptor proxy yang melacak eksekusi exception. Jika target method gagal 3 kali berturut-turut, panggilan ke-4 harus langsung melempar `RuntimeException("Circuit is OPEN")` tanpa mengeksekusi target method hingga batas waktu reset terlewati.

#### Level Hard
Rancang komponen **Metadata Code Generator**:
Buat class yang menerima FQCN (*Fully Qualified Class Name*), membaca seluruh method dan atribut AOP-nya, lalu menghasilkan string kode PHP valid untuk kelas proxy yang berdiri sendiri (menulis file `.php` ke sistem direktori cache). Proxy yang di-generate harus mengimplementasikan interface target tanpa menggunakan anonymous class atau string evaluation (`eval`).

---

### 14. Challenge

Anda adalah Principal Architect pada platform E-Commerce berskala global. Sistem Anda memiliki *Payment Gateway Service* yang memproses otentikasi signature HMAC, enkripsi payload, dan pembatasan frekuensi akses (*rate-limiting*).

**Tantangan**:
Rancang dan bangun sebuah **Pipeline Metaprogramming Terkompilasi (Static Proxy Engine)** dengan spesifikasi ketat:
1. Tidak boleh ada pemanggilan kelas `Reflection*` saat request berlangsung (semua metadata harus di-*bake* ke dalam static array atau native code pada saat warm-up).
2. Terapkan 3 atribut berurutan pada satu method:
   - `#[AuthenticateSigner]`
   - `#[DecryptPayload(algorithm: 'AES-256-GCM')]`
   - `#[RateLimit(requestsPerMinute: 60)]`
3. Pipeline interceptor harus mematuhi urutan eksekusi (*chain of responsibility*) dan mampu membatalkan (*short-circuit*) eksekusi method utama jika ada tahapan atribut yang gagal.
4. Tolok ukur (*Benchmark*): Kode proxy yang dihasilkan harus memiliki latency overhead tidak lebih dari **0.05ms** dibandingkan pemanggilan method langsung tanpa interceptor.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Kapan struktur `zend_attribute` diproses oleh Zend VM?
   - A. Hanya saat fungsi `eval()` dipanggil.
   - B. Saat fase kompilasi file PHP berlangsung ke AST dan disimpan di zend_class_entry.
   - C. Saat request HTTP selesai (Shutdown phase).
   - D. Di-resolve secara manual oleh runtime Composer autoloader.
2. Apa fungsi parameter `Attribute::TARGET_METHOD` saat mendefinisikan custom attribute?
   - A. Mengizinkan atribut dipasang di atas function atau anonymous function saja.
   - B. Membatasi penempatan atribut agar hanya valid dievaluasi di atas deklarasi method kelas.
   - C. Memaksa method untuk dieksekusi secara otomatis saat instansiasi.
   - D. Menghubungkan method ke tabel routing framework.
3. Fungsi mana pada `ReflectionAttribute` yang mengubah metadata menjadi instance objek PHP sesungguhnya?
   - A. `ReflectionAttribute::instantiate()`
   - B. `ReflectionAttribute::getObject()`
   - C. `ReflectionAttribute::newInstance()`
   - D. `ReflectionAttribute::compile()`
4. Mengapa konfigurasi `opcache.save_comments=1` kritikal dipertahankan pada arsitektur modern?
   - A. Mencegah error alokasi memory heap pada Zend VM.
   - B. Mengaktifkan fitur JIT (Just-In-Time) compiler.
   - C. Menjamin DocBlock annotations dan dokumentasi refleksi tetap terbaca di runtime shared memory.
   - D. Mempercepat eksekusi database queries.
5. Manakah karakteristik objek yang benar pada Zend Engine internal?
   - A. Objek disimpan sebagai plain associative array di level C.
   - B. Properti objek diakses melalui lookup string hashmap terus-menerus tanpa optimasi slot.
   - C. Objek dikelola via `zend_object` yang memiliki pointer ke `zend_class_entry` dan slot indeks array terkompilasi untuk properti.
   - D. Setiap instansiasi objek menyalin seluruh `function_table` milik kelas ke memori lokal.

#### Bagian 2: Intermediate (Pilihan Ganda)
6. Apa dampak performa utama penggunaan `ReflectionClass::newInstance()` berulang kali di dalam loop dengan 10.000 iterasi?
   - A. Terjadinya CPU context switching drastis dan alokasi memory allocation berlebihan karena pembuatan metadata wrapper objek baru di setiap siklus.
   - B. Database connection pool langsung habis seketika.
   - C. Zend VM secara otomatis mematikan OPcache.
   - D. Tidak ada dampak performa sama sekali karena sudah di-cache oleh engine C.
7. Di antara pilihan berikut, manakah cara paling optimal menerapkan AOP tanpa penalti performa runtime reflection?
   - A. Menggunakan `__call()` pada seluruh Domain Model.
   - B. Menggunakan `debug_backtrace()` untuk menganalisis caller method secara dinamis.
   - C. Melakukan kompilasi proxy ke file fisik saat build pipeline lalu mengaktifkan OPcache preloading.
   - D. Melakukan dekonstruksi kode sumber menggunakan `token_get_all()` pada setiap request lifecycle.
8. Apa yang terjadi jika target kelas yang ingin dibungkus (*wrapped*) oleh Dynamic Proxy bertipe `final`?
   - A. Proxy inheritance subclassing (`extends TargetClass`) akan gagal pada tahap parsing class declaration.
   - B. Zend VM otomatis menghapus keyword `final` secara dinamis.
   - C. Proxy hanya bisa dibuat jika OPcache dimatikan.
   - D. Kelas tersebut dikonversi otomatis menjadi Interface.
9. Atribut PHP 8 mendukung bitwise flags berikut, KECUALI:
   - A. `Attribute::TARGET_CLASS`
   - B. `Attribute::TARGET_PROPERTY`
   - C. `Attribute::IS_REPEATABLE`
   - D. `Attribute::TARGET_GLOBAL_VARIABLE`
10. Bagaimana representasi memori sebuah Atribut jika method target tidak pernah dipanggil melalui Reflection API?
    - A. Memori atribut bocor (*leak*) di heap.
    - B. Atribut tetap berupa representasi struktur internal engine di OPcache dan objek kelas Atribut TIDAK PERNAH diinstansiasi ke memori runtime.
    - C. PHP crash dengan pesan Fatal Memory Error.
    - D. Zend VM menghapus class entry dari function table.

#### Bagian 3: Skenario Kasus Produksi (Analisis Kasus)
11. **Skenario 1**: Sebuah microservice billing mencatat lonjakan CPU hingga 100% dan latency melonjak dari 15ms ke 800ms setelah deployment fitur validasi baru berbasis Atribut. Tim menemukan bahwa validator mengekstrak atribut dari DTO menggunakan `(new ReflectionClass($dto))->getProperties()` di dalam loop parsing 5.000 baris transaksi CSV. Bagaimana langkah rekayasa Anda untuk mengatasi masalah ini seketika tanpa menghapus sistem validasi atribut?
12. **Skenario 2**: Anda sedang mengaudit sistem warisan (*legacy*) yang membungkus database call menggunakan method magic `__call()`. Hasil profiling Blackfire/Xdebug menunjukkan 40% durasi eksekusi tersita pada pemanggilan method magic tersebut. Jelaskan mengapa Zend VM lambat dalam mengeksekusi `__call()` berulang kali dan berikan arsitektur alternatifnya!
13. **Skenario 3**: Sebuah tim ingin mengimplementasikan `#[Cacheable]` proxy. Namun, pada method yang mengembalikan `Generator` (`yield`), nilai kembalian yang di-cache justru menghasilkan bug: request kedua mendapatkan generator yang sudah tertutup (*exhausted/closed generator*). Bagaimana arsitektur proxy harus dirancang untuk menangani objek bertipe `Generator` atau *deferred execution*?

---

### Kunci Jawaban & Pembahasan Quiz

#### Bagian 1: Basic
1. **B** - Kompiler Zend VM langsung memproses token atribut ke dalam AST dan menyematkannya ke struktur data internal `zend_class_entry` saat file diparse.
2. **B** - `Attribute::TARGET_METHOD` adalah bitmask internal yang membatasi penempatan sintaksis atribut hanya diizinkan di atas fungsi anggota kelas (method).
3. **C** - `newInstance()` mengeksekusi constructor kelas atribut dengan argumen yang didefinisikan secara deklaratif dan mengembalikan instance objek PHP aktif.
4. **C** - Mengaktifkan `save_comments=1` vital untuk ekosistem PHP agar informasi docblock dan meta bytecode tetap dipreservasi di shared memory.
5. **C** - Objek di Zend VM dikelola secara efisien via `zend_object` yang mereferensikan satu definisi `zend_class_entry` bersama, dengan data variabel lokal dipetakan pada indexed slot array.

#### Bagian 2: Intermediate
6. **A** - Panggilan `new ReflectionClass()` instansiasi wrapper PHP userland berulang kali, mengalokasikan memory frame baru dan memaksa garbage collector bekerja keras.
7. **C** - Membangun class proxy fisik ke disk saat build time menjamin pemanggilan method berjalan sebagai *direct method dispatch* standar yang dapat di-cache dan di-JIT oleh OPcache secara native.
8. **A** - Keyword `final` melarang inheritance secara fundamental di level engine. Solusinya harus beralih ke komposisi/delegasi (Interface proxy) daripada pewarisan kelas (*subclass proxy*).
9. **D** - Zend Engine tidak memiliki konsep atribut untuk variabel lokal atau variabel global; scope atribut hanya mencakup unit struktural (Class, Method, Function, Property, Parameter, Class Constant).
10. **B** - *Lazy Instantiation*: Atribut hanya berwujud metadata biner di `zend_attribute`. Objek kelas userland tidak akan pernah dialokasikan di memory heap jika tidak ada script yang memicu `->newInstance()`.

#### Bagian 3: Skenario Kasus Produksi
11. **Pembahasan Skenario 1**:
    Akar masalah adalah instansiasi `ReflectionClass` dan traversal metadata secara berulang untuk 5.000 iterasi.
    *Langkah Perbaikan*: Implementasikan **Metadata Identity Cache / Memoization**. Buat static map `$metadataCache = []` di dalam service validator. Lakukan refleksi satu kali saja per tipe class DTO, lalu petakan list property dan aturan validasinya ke dalam bentuk *pure plain array of rules*. Pada 4.999 iterasi berikutnya, validator cukup mengambil *rule array* dari static memory cache tanpa pernah menyentuh Reflection API.
12. **Pembahasan Skenario 2**:
    *Penyebab*: Pemanggilan `__call()` menonaktifkan optimasi internal *polymorphic inline caching* pada Zend VM. VM terpaksa mengalokasikan stack frame dinamis, menyalin parameter ke dalam array, melakukan lookup runtime method resolver, lalu mengeksekusi handler.
    *Arsitektur Alternatif*: Ganti pendekatan magic `__call()` dengan men-generate interface kontrak eksplisit dan menggunakan **Concrete Typed Proxies** yang mendeklarasikan seluruh method secara gamblang. Hal ini memungkinkan Zend Engine memetakan pemanggilan secara langsung (*direct vtable dispatch*) dan membuka peluang JIT compiler melakukan inlining code.
13. **Pembahasan Skenario 3**:
    *Penyebab*: `Generator` di PHP adalah *forward-only iterator* berbasis state machine internal Zend VM. Ketika generator selesai di-iterasi (`yield`), state-nya menjadi *closed* dan tidak dapat di-rewind atau dibaca ulang.
    *Arsitektur Solusi*: Interceptor Proxy harus mendeteksi return type method melalui Reflection (`$method->hasReturnType() && $method->getReturnType()->getName() === Generator::class`). Jika return type adalah `Generator`, proxy tidak boleh menyimpan objek Generator mentah ke dalam cache. Proxy harus mengonsumsi generator tersebut menjadi buffer data (misal: array flat menggunakan `iterator_to_array()`), menyimpan array tersebut ke cache, lalu me-yield kembali nilainya menggunakan `yield from $cachedArray`.

---

### 16. Summary

1. **Internal Representation**: Pemahaman atas `zend_class_entry`, alokasi `zval`, dan layout memori instance `zend_object` membedakan arsitek software tingkat lanjut dengan pemrogram PHP biasa dalam mengidentifikasi bottleneck performa.
2. **Attributes as First-Class Citizens**: Hadirnya Atribut native pada PHP 8.x mengeliminasi kelemahan docblock annotation konvensional, menghasilkan metadata yang terstruktur, statis, aman secara tipe (*type-safe*), dan tersimpan efisien di OPcache.
3. **Decoupled Architecture via AOP**: Memanfaatkan *Dynamic Proxy* dan *Attributes* memungkinkan pemisahan total antara logika domain inti dengan operasi periferal seperti manajemen transaksi, audit trail, otentikasi, dan caching.
4. **Performance Paradigm**: Dalam arsitektur berskala enterprise, refleksi dinamis saat runtime request harus diminimalisasi atau dihilangkan sepenuhnya menggunakan teknik **Compile-Time Code Generation** dan **Static Proxying** untuk memaksimalkan throughput server.