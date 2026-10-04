# Kurikulum Rekayasa Perangkat Lunak Lanjut: PHP Enterprise Ecosystem

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Pembelajaran (Track):** Backend Engineering & Distributed Systems
*   **Kategori:** 02-Programming-Languages
*   **Sub-Kategori / Bahasa:** PHP (Hypertext Preprocessor)
*   **Modul:** Bab 02 Module 01
*   **Judul/Topik:** Advanced Object-Oriented PHP & Meta-programming
*   **Tingkat Kesulitan:** Advanced (Tingkat Lanjut)
*   **Prasyarat:** Pemahaman mendalam tentang Object-Oriented Programming (OOP) fundamental (Inheritance, Polymorphism, Encapsulation, Abstraction), sintaks dasar PHP 8.x, Composer, dan arsitektur runtime PHP (FPM/CLI).
*   **Target Lingkungan Runtime:** PHP 8.2 / 8.3 (Zend Engine v4.x, OPcache Enabled)
*   **Waktu Estimasi Penyelesaian:** 12 - 16 Jam Pembelajaran Mandiri / Praktikum Terbimbing

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Menganalisis dan Membedah Arsitektur Objek Tingkat Rendah:** Mengartikulasikan representasi memori internal objek pada Zend Engine (`zend_class_entry`, `zend_object`, dan *dynamic property buckets*).
2.  **Mengimplementasikan Paradigma Metaprogramming Runtime:** Memanfaatkan PHP *Reflection API* dan *Attributes* (PHP 8+) untuk membangun arsitektur deklaratif berbasis metadata yang decoupled.
3.  **Mengoperasikan Intersepsi Eksekusi Tingkat Rendah:** Mengonfigurasi dan mengendalikan perilaku dinamis objek menggunakan *Magic Methods*, *Anonymous Classes*, dan *Closure Re-binding* (`Closure::bind` / `Closure::bindTo`).
4.  **Membangun Engine Proxy & Aspect-Oriented Programming (AOP):** Merancang pola *Dynamic Proxy* untuk intersepsi logika bisnis, validasi, dan observabilitas tanpa memodifikasi kode domain inti.
5.  **Mengoptimasi Overhead Runtime Metaprogramming:** Merancang strategi *caching* metadata dan *code-generation ahead-of-time (AOT)* guna meminimalkan penalti performa yang disebabkan oleh inspeksi refleksi pada siklus hidup permintaan web.
6.  **Memitigasi Celah Keamanan Dinamis:** Mengidentifikasi dan mengeliminasi risiko injeksi objek, evaluasi kode arbitrer, serta kebocoran enkapsulasi memori yang diakibatkan manipulasi runtime yang tidak aman.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Mental Model: Dari Static Consumer Menjadi Runtime Architect

Dalam rekayasa perangkat lunak PHP tingkat pemula dan menengah, pengembang memandang kelas dan objek sebagai cetak biru statis (*static blueprints*). Kode ditulis, di-parsing oleh Zend Engine, dan dieksekusi secara linear sesuai definisi file teks.

```
Model Pemula: 
[Kode Sumber PHP] ----> [Zend Compiler] ----> [Instansiasi Objek Tetap]
```

Pada tingkat lanjut, Anda harus mengubah mental model Anda: **Objek dan Kode adalah Data yang Dapat Dimanipulasi pada Runtime (*Code as Data*)**. Metaprogramming adalah kapasitas kode untuk memeriksa, memodifikasi, memperluas, atau menghasilkan kode lain selama proses eksekusi program.

```
Model Advanced (Metaprogramming Engine):
[Metadata / Attributes] ---> [Reflection Engine] ---> [Zend Object Interception]
                                    |                           |
                                    v                           v
                           [Dynamic Synthesis] <-----> [Proxy Wrapping / Rebinding]
```

### Hukum Konservasi Metaprogramming
Metaprogramming memberikan abstraksi dan fleksibilitas luar biasa, namun memiliki ongkos yang tak terhindarkan:
1.  **Penalti Waktu Eksekusi (*Execution Time Cost*):** Refleksi melintasi struktur data internal Zend Engine melalui pointer C tak langsung, melewati optimasi OPcache jika tidak dikelola dengan benar.
2.  **Erosi Static Analysis:** Penggunaan properti dinamis dan resolusi pemanggilan metode virtual menyulitkan IDE, PHPStan, dan Psalm untuk menjamin tipe data secara statis.
3.  **Beban Kognitif Sistem:** Keterbacaan kode (*code readability*) menurun drastis jika alur eksekusi disembunyikan di balik *magic execution hooks*.

Seorang arsitek perangkat lunak menggunakan metaprogramming bukan untuk sekadar memamerkan teknik, melainkan untuk membangun platform, framework, pustaka ORM, sistem injeksi dependensi (*Dependency Injection Container*), dan middleware lapisan infrastruktur enterprise yang bersih, modular, dan dapat dikonfigurasi secara deklaratif.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram Alur Runtime: Intersepsi Objek, Refleksi, dan Eksekusi Atribut

Berikut adalah alur arsitektural bagaimana PHP 8.3 menangani instansiasi, evaluasi metadata atribut, dan pemanggilan dinamis melalui proxy:

```
+-----------------------------------------------------------------------------+
|                                KLIEN / PEMANGGIL                            |
+-----------------------------------------------------------------------------+
                                       |
                                       | 1. Instansiasi Target / Resolusi
                                       v
+-----------------------------------------------------------------------------+
|                       ASPECT / PROXY INTERCEPTOR                            |
|  - Mengevaluasi interceptor via ReflectionClass                             |
|  - Mengekstrak ReflectionAttribute instances                                |
+-----------------------------------------------------------------------------+
       |                                                               |
       | 2. Baca Atribut Runtime                                       | 3. Pasang Magic Hook / Proxy
       v                                                               v
+----------------------------+                     +---------------------------+
|  REFLECTION ENGINE         |                     | DYNAMIC PROXY OBJECT      |
|  - Memindai Target Class   |                     | - __call() / __invoke()   |
|  - Parsing metadata AST    |                     | - Closure::bindTo Context |
+----------------------------+                     +---------------------------+
       |                                                               |
       +-------------------------------+-------------------------------+
                                       |
                                       | 4. Evaluasi Pipeline Intersepsi
                                       v
                        +------------------------------+
                        | PRE-PROCESSING HOOKS         |
                        | (e.g., Autentikasi, Log)    |
                        +------------------------------+
                                       |
                                       | 5. Invokasi Target Sebenarnya
                                       v
                        +------------------------------+
                        | ZEND ENGINE EXECUTOR         |
                        | - zend_class_entry           |
                        | - zend_function / zend_op    |
                        | - Native Object State ($this)|
                        +------------------------------+
                                       |
                                       | 6. Evaluasi Pipeline Pasca-Eksekusi
                                       v
                        +------------------------------+
                        | POST-PROCESSING HOOKS        |
                        | (e.g., Transformasi, Metrik) |
                        +------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                          KEMBALIKAN NILAI KE KLIEN                          |
+-----------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Representasi Memori Zend Engine: `zend_class_entry` & `zend_object`

Untuk memahami batas performa metaprogramming, kita harus membedah bagaimana Zend Engine (implementasi C dari runtime PHP) menyimpan struktur OOP di dalam RAM.

```
       zend_class_entry (Struktur C Kelas)
+---------------------------------------------------+
| char *name                -> "App\Domain\User"    |
| uint32_t type             -> ZEND_USER_CLASS      |
| zend_function_entry *fe   -> Array pointer method |
| HashTable function_table  -> Koleksi method       |
| HashTable properties_info -> Metadata properti   |
| HashTable constants_table -> Metadata konstanta  |
| zend_attribute *attributes-> Pointer Atribut C    |
+---------------------------------------------------+
                         ^
                         | (Pointer kelas induk dari instance)
+---------------------------------------------------+
| zend_object (Struktur C Instance Objek)           |
|---------------------------------------------------|
| zend_refcounted_h gc      -> Pelacak GC/Refcount  |
| uint32_t handle           -> ID Unik objek tabel  |
| zend_class_entry *ce      ------------------------+
| const zend_object_handlers *handlers              |
| HashTable *properties     -> Dynamic properties   |
| zval properties_table[1]  -> Slot properti statis |
+---------------------------------------------------+
```

#### 1. Properti Statis vs Properti Dinamis
*   **Properti Terdeklarasi:** Disimpan langsung di dalam array pipih `properties_table` yang diindeks secara integer pada offset tetap. Akses terhadap properti ini memerlukan kompleksitas waktu $O(1)$ dan sangat ramah terhadap *cache locality* prosesor.
*   **Properti Dinamis (Dynamic Properties):** Jika properti tidak dideklarasikan di `zend_class_entry`, PHP harus mengalokasikan tabel hash terpisah (`properties`). Setiap pembacaan atau penulisan memicu pencarian string hash yang membutuhkan alokasi memori heap tambahan, melambatkan akses, dan sejak PHP 8.2 secara bawaan dilempari peringatan `Deprecated: Creation of dynamic property is deprecated` kecuali kelas mewarisi `\stdClass` atau dianotasi `#[AllowDynamicProperties]`.

#### 2. Mekanisme Magic Methods pada Kernel C
Ketika mengeksekusi instruksi seperti `$obj->nonExistentMethod()`, alur eksekusi internal Zend Engine adalah sebagai berikut:
1.  Engine menjalankan opcode `ZEND_INIT_METHOD_CALL`.
2.  Pencarian dilakukan pada tabel hash `ce->function_table`.
3.  Jika lookup gagal, engine memeriksa `ce->__call`.
4.  Jika pointer `__call` tersedia di `handlers`, engine mengubah konteks eksekusi: mengemas nama fungsi asal ke dalam parameter string zval, mengemas argumen ke dalam array zval, lalu mengeksekusi metode `__call` melalui `ZEND_DO_FCALL`. Operasi ini memicu overhead penambahan stack frame dan konversi struktur data secara masif.

#### 3. Resolusi Atribut (PHP 8+)
Atribut dikompilasi ke dalam struktur internal `zend_attribute` yang disimpan langsung di shared memory bersama `zend_class_entry` di bawah OPcache. Atribut **tidak** diinstansiasi menjadi objek PHP hingga method `ReflectionAttribute::newInstance()` dipanggil secara eksplisit oleh kode pengguna. Ini adalah optimasi *lazy-evaluation* krusial yang menghemat alokasi memori runtime.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. PHP Attributes Architecture (Metadata Deklaratif)

Sebelum PHP 8.0, komunitas PHP menggunakan PHPDoc *doc-comments* (misalnya `@ORM\Entity`) yang di-parse menggunakan string regex melalui `ReflectionClass::getDocComment()`. Ini rawan kesalahan sintaksis, lambat, dan tidak memiliki validasi tipe.

PHP 8 Attributes memperlakukan metadata sebagai warga kelas satu (*first-class citizens*). Atribut adalah kelas normal yang ditandai dengan `#[Attribute]`.

#### Flag Konfigurasi Atribut:
*   `Attribute::TARGET_CLASS`: Hanya dapat diterapkan pada deklarasi kelas.
*   `Attribute::TARGET_METHOD`: Hanya untuk fungsi/metode.
*   `Attribute::TARGET_PROPERTY`: Hanya untuk properti.
*   `Attribute::TARGET_PARAMETER`: Untuk parameter fungsi (sangat berguna untuk pemetaan dependensi).
*   `Attribute::IS_REPEATABLE`: Mengizinkan atribut dideklarasikan lebih dari sekali pada target yang sama.

### 2. Reflection API: Deep Inspection & Introspection

Reflection menyediakan kapabilitas *read/write introspection* penuh terhadap seluruh komponen engine PHP.

*   `ReflectionClass<T>`: Menganalisis definisi kelas, parent, traits, interfaces, modifikator (`final`, `readonly`, `abstract`).
*   `ReflectionMethod`: Memeriksa visibilitas, tipe pengembalian (*return types*), parameter, jumlah argumen wajib, status generator, dan closure binding.
*   `ReflectionProperty`: Menginspeksi tipe data, status inisialisasi (`isInitialized`), modifikator `readonly`, dan memungkinkan pemaksaan modifikasi akses enkapsulasi via `setAccessible(true)` (meskipun sejak PHP 8.1, akses private/protected dapat langsung diakses via reflection tanpa pemanggilan eksplisit `setAccessible`).

### 3. Magic Methods: Batas Penggunaan dan Perilaku Internal

Magic methods mengintersepsi interaksi siklus hidup objek:

| Method | Pemicu (Trigger) Internal | Peruntukan Enterprise |
| :--- | :--- | :--- |
| `__get($name)` | Membaca properti yang tidak terdefinisi atau tidak dapat diakses | Virtual Property Hydration, Lazy Loading ORM |
| `__set($name, $val)` | Menulis properti yang tidak terdefinisi atau tidak dapat diakses | Strict Schema Validation, Dynamic DTO Binding |
| `__call($name, $args)` | Memanggil metode instance yang tidak terdefinisi/tidak dapat diakses | Dynamic Proxying, Macro Injection, AOP Decorator |
| `__callStatic($name, $args)` | Memanggil metode statis yang tidak terdefinisi | Dynamic Facades (Gunakan dengan sangat hemat) |
| `__invoke(...$args)` | Menggunakan instance objek secara langsung sebagai callable | Single Responsibility Command/Action objects |
| `__clone()` | Menangani kloning objek ketika operator `clone` dieksekusi | Prototype Pattern, Deep Copying Object Graph |

### 4. Advanced Closure Metaprogramming: Context Rebinding

Fitur paling kuat sekaligus berbahaya dalam PHP OOP adalah kapasitas untuk melepaskan fungsi anonim (*closure*) dari cakupan deklarasinya dan mengikatnya (*re-bind*) ke dalam cakupan objek lain, bahkan menembus enkapsulasi visibilitas `private`.

*   `Closure::bind(Closure $closure, ?object $newThis, object|string|null $newScope = 'static')`: Menghasilkan objek Closure baru dengan konteks `$this` dan batasan visibilitas kelas (`$newScope`) yang baru.
*   `Closure::bindTo(?object $newThis, object|string|null $newScope = 'static')`: Metode instance dari Closure yang melakukan hal serupa.
*   `$closure->call(object $newThis, ...$args)`: Mengikat dan mengeksekusi closure secara langsung dalam satu instruksi CPU, jauh lebih hemat memori dibanding alokasi closure baru via `bindTo`.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kode yang mendemonstrasikan integrasi *Custom Attributes*, *Reflection*, dan *Closure Manipulation* untuk memodifikasi state internal kelas domain tanpa merusak desain aslinya.

```php
<?php

declare(strict_types=1);

namespace App\Core\Fundamental;

use Attribute;
use ReflectionClass;
use ReflectionProperty;
use LogicException;
use RuntimeException;

// 1. Definisikan Custom Attribute dengan bitmask target
#[Attribute(Attribute::TARGET_PROPERTY | Attribute::TARGET_METHOD)]
final readonly class SensitiveData
{
    public function __construct(
        public string $maskStrategy = 'ASTERISK',
        public int $visibleChars = 4
    ) {}
}

// 2. Kelas Domain yang merepresentasikan entitas terisolasi
final class BankAccount
{
    private string $accountHolder;
    
    #[SensitiveData(maskStrategy: 'HASH', visibleChars: 2)]
    private string $accountNumber;

    #[SensitiveData(maskStrategy: 'ASTERISK', visibleChars: 4)]
    private float $balance;

    public function __construct(string $holder, string $accountNumber, float $balance)
    {
        $this->accountHolder = $holder;
        $this->accountNumber = $accountNumber;
        $this->balance = $balance;
    }

    public function getHolder(): string
    {
        return $this->accountHolder;
    }
}

// 3. Metadata Inspector Engine
final class SecurityInspector
{
    /**
     * Membaca dan menyamarkan properti sensitif menggunakan Reflection dan Closure
     *
     * @return array<string, mixed>
     */
    public function extractMaskedState(object $entity): array
    {
        $refClass = new ReflectionClass($entity);
        $state = [];

        foreach ($refClass->getProperties() as $property) {
            $propName = $property->getName();
            
            // Baca nilai properti private menggunakan Closure Binding bypass
            $reader = function & () use ($propName) {
                return $this->{$propName};
            };
            
            $bindedReader = $reader->bindTo($entity, $entity);
            if ($bindedReader === null) {
                throw new RuntimeException("Gagal mengikat scope closure ke target.");
            }
            
            $rawValue = $bindedReader();

            // Cek ada atribut SensitiveData atau tidak
            $attributes = $property->getAttributes(SensitiveData::class);

            if (empty($attributes)) {
                $state[$propName] = $rawValue;
                continue;
            }

            // Inisialisasi atribut secara lazy
            /** @var SensitiveData $meta */
            $meta = $attributes[0]->newInstance();
            $state[$propName] = $this->maskValue((string)$rawValue, $meta);
        }

        return $state;
    }

    private function maskValue(string $val, SensitiveData $meta): string
    {
        if ($meta->maskStrategy === 'HASH') {
            return hash('sha256', $val);
        }

        $length = strlen($val);
        if ($length <= $meta->visibleChars) {
            return str_repeat('*', $length);
        }

        $visiblePart = substr($val, -$meta->visibleChars);
        $maskedPart = str_repeat('*', $length - $meta->visibleChars);

        return $maskedPart . $visiblePart;
    }
}

// Eksekusi Fundamental
$account = new BankAccount("Alexander Graves", "ID-908129841249", 54200000.50);
$inspector = new SecurityInspector();
$sanitizedData = $inspector->extractMaskedState($account);

print_r($sanitizedData);
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi arsitektural dari kode Fundamental pada Seksi 07:

1.  **Baris 11 (`#[Attribute(Attribute::TARGET_PROPERTY | Attribute::TARGET_METHOD)]`)**:
    *   Mendeklarasikan kelas `SensitiveData` sebagai metadata atribut murni pada compiler Zend.
    *   Penggunaan operator bitwise OR (`|`) membatasi penggunaan atribut ini hanya pada properti atau metode kelas. Jika atribut ini dicoba dipasang pada deklarasi kelas induk (`class Foo`), Zend Engine melempar `\Error` fatal pada fase parsing.
2.  **Baris 13 (`public function __construct(...)`)**:
    *   Memanfaatkan *Constructor Property Promotion* dan modifikator `readonly`. Imutabilitas data atribut sangat krusial karena metadata kelas tidak boleh bermutasi selama fase eksekusi runtime.
3.  **Baris 24 (`#[SensitiveData(maskStrategy: 'HASH', visibleChars: 2)]`)**:
    *   Menempelkan instance metadata pada properti `private string $accountNumber`. Metadata ini tidak menghabiskan memory run-time tambahan hingga method refleksi memanggil instansiasinya.
4.  **Baris 52 (`$refClass = new ReflectionClass($entity);`)**:
    *   Membuat handle introspection ke dalam `zend_class_entry` internal dari objek instance `$account`.
5.  **Baris 58-60 (`$reader = function & () use ($propName) { return $this->{$propName}; };`)**:
    *   Mendeklarasikan fungsi anonim dengan pengembalian referensi (`&`). Closure ini belum memiliki konteks `$this` yang valid pada scope eksekusi lokal `extractMaskedState`.
6.  **Baris 62 (`$bindedReader = $reader->bindTo($entity, $entity);`)**:
    *   **Mekanisme Utama Bypassing Enkapsulasi:** Argumen pertama menetapkan objek instance target `$entity` sebagai `$this`. Argumen kedua memberikan *scope resolution* setingkat kelas target `$entity`, memutus rantai proteksi visibilitas `private` properti tanpa harus mengubah visibilitas file domain secara fisik.
7.  **Baris 70 (`$property->getAttributes(SensitiveData::class);`)**:
    *   Menyaring array metadata atribut yang terpasang pada properti. PHP secara otomatis mencocokkan Fully Qualified Class Name (FQCN) dari kelas atribut yang dioperasikan.
8.  **Baris 78 (`$meta = $attributes[0]->newInstance();`)**:
    *   Mengubah representasi internal C `zend_attribute` menjadi objek instansiasi runtime PHP dari kelas `SensitiveData`. Parameter konstruktor dievaluasi dan di-pass secara dinamis.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Enterprise Dynamic Data-Mapper & Transactional Interceptor Engine

**Latar Belakang Kasus:**
Sebuah platform perbankan digital core (*digital banking*) sedang memigrasikan arsitektur monolitis mereka. Mereka menolak penggunaan ORM Active Record berat (seperti Eloquent) karena overhead memori yang masif dan polusi dependensi infrastruktur pada domain murni. Mereka juga menolak Doctrine ORM karena kebutuhan integrasi audit-trail dan enkripsi tingkat kolom (*Column-Level Encryption/CLE*) secara real-time yang harus berjalan transparan.

**Kebutuhan Rekayasa:**
1.  **Pure POPO (Plain Old PHP Objects):** Entitas domain harus sepenuhnya bersih dari pewarisan kelas (*zero base-class inheritance*) dan tidak bergantung pada pustaka eksternal.
2.  **Declarative Field Mapping via Attributes:** Skema basis data, nama kolom, auto-casting, dan enkripsi diatur melalui atribut bawaan PHP.
3.  **Transactional AOP Proxy:** Intersepsi operasi mutasi untuk mencatat event audit dan mengontrol integritas transaksi basis data ACID menggunakan dynamic proxy class generation tanpa modifikasi file fisik.
4.  **Zero Reflection Leakage on Hot Path:** Refleksi hanya diakses sekali untuk kompilasi metadata; proses hidrasi berikutnya wajib menggunakan closures yang telah ter-cache.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Di bawah ini adalah implementasi sistem mikro Data-Mapper ORM & AOP Interceptor produksi dengan pemanfaatan atribut, proxy builder, dan closure compilation.

```php
<?php

declare(strict_types=1);

namespace App\Infrastructure\Engine;

use Attribute;
use ReflectionClass;
use ReflectionMethod;
use ReflectionProperty;
use ReflectionNamedType;
use PDO;
use Closure;
use Exception;
use RuntimeException;
use InvalidArgumentException;

// ============================================================================
// 1. DOMAIN DECLARATIVE METADATA (ATTRIBUTES)
// ============================================================================

#[Attribute(Attribute::TARGET_CLASS)]
final readonly class Table
{
    public function __construct(public string $name) {}
}

#[Attribute(Attribute::TARGET_PROPERTY)]
final readonly class Column
{
    public function __construct(
        public string $name,
        public bool $isPrimary = false,
        public bool $encrypted = false
    ) {}
}

#[Attribute(Attribute::TARGET_METHOD)]
final readonly class Transactional {}

// ============================================================================
// 2. DOMAIN ENTITY (PURE DOMAIN LOGIC, ZERO EXTERNAL DEPENDENCY)
// ============================================================================

#[Table(name: 'bank_customers')]
final class Customer
{
    #[Column(name: 'id', isPrimary: true)]
    private ?int $id = null;

    #[Column(name: 'full_name')]
    private string $name;

    #[Column(name: 'tax_number', encrypted: true)]
    private string $taxNumber;

    #[Column(name: 'account_balance')]
    private float $balance;

    public function __construct(string $name, string $taxNumber, float $balance, ?int $id = null)
    {
        $this->name = $name;
        $this->taxNumber = $taxNumber;
        $this->balance = $balance;
        $this->id = $id;
    }

    public function getId(): ?int { return $this->id; }
    public function getName(): string { return $this->name; }
    public function getTaxNumber(): string { return $this->taxNumber; }
    public function getBalance(): float { return $this->balance; }

    public function credit(float $amount): void
    {
        if ($amount <= 0) {
            throw new InvalidArgumentException("Nominal kredit harus positif.");
        }
        $this->balance += $amount;
    }
}

// ============================================================================
// 3. ENTERPRISE ENCRYPTION SERVICE
// ============================================================================

interface EncryptionServiceInterface
{
    public function encrypt(string $plain): string;
    public function decrypt(string $cipher): string;
}

final class SodiumEncryptionService implements EncryptionServiceInterface
{
    private string $key;

    public function __construct(string $hexKey)
    {
        $this->key = sodium_hex2bin($hexKey);
    }

    public function encrypt(string $plain): string
    {
        $nonce = random_bytes(SODIUM_CRYPTO_SECRETBOX_NONCEBYTES);
        $cipher = sodium_crypto_secretbox($plain, $nonce, $this->key);
        return sodium_bin2hex($nonce . $cipher);
    }

    public function decrypt(string $cipher): string
    {
        $raw = sodium_hex2bin($cipher);
        $nonce = substr($raw, 0, SODIUM_CRYPTO_SECRETBOX_NONCEBYTES);
        $ciphertext = substr($raw, SODIUM_CRYPTO_SECRETBOX_NONCEBYTES);
        
        $plain = sodium_crypto_secretbox_open($ciphertext, $nonce, $this->key);
        if ($plain === false) {
            throw new RuntimeException("Gagal melakukan dekripsi data!");
        }
        return $plain;
    }
}

// ============================================================================
// 4. METADATA COMPILER & COMPILED HYDRATOR (HOT-PATH OPTIMIZATION)
// ============================================================================

final class EntityMetadata
{
    /**
     * @param array<string, array{column: string, encrypted: bool, property: string}> $columns
     */
    public function __construct(
        public string $tableName,
        public string $primaryKeyProperty,
        public string $primaryKeyColumn,
        public array $columns,
        public Closure $hydrator,
        public Closure $extractor
    ) {}
}

final class MetadataRegistry
{
    /** @var array<class-string, EntityMetadata> */
    private static array $cache = [];

    public static function get(string $class, EncryptionServiceInterface $crypto): EntityMetadata
    {
        if (isset(self::$cache[$class])) {
            return self::$cache[$class];
        }

        $refClass = new ReflectionClass($class);

        // Ambil Nama Tabel
        $tableAttrs = $refClass->getAttributes(Table::class);
        if (empty($tableAttrs)) {
            throw new RuntimeException("Kelas {$class} tidak memiliki atribut Table.");
        }
        $tableName = $tableAttrs[0]->newInstance()->name;

        $pkProperty = '';
        $pkColumn = '';
        $columns = [];
        $propertyNames = [];

        foreach ($refClass->getProperties() as $prop) {
            $colAttrs = $prop->getAttributes(Column::class);
            if (empty($colAttrs)) {
                continue;
            }

            /** @var Column $colMeta */
            $colMeta = $colAttrs[0]->newInstance();
            $propName = $prop->getName();
            $propertyNames[] = $propName;

            $columns[$propName] = [
                'column' => $colMeta->name,
                'encrypted' => $colMeta->encrypted,
                'property' => $propName
            ];

            if ($colMeta->isPrimary) {
                $pkProperty = $propName;
                $pkColumn = $colMeta->name;
            }
        }

        // COMPILED CLOSURES UNTUK MENJAMIN PERFORMA TINGGI (MEMOTONG REFLEKSI PADA RUNTIME)
        
        // 1. Fast Hydrator (Database Array -> Uninitialized Object)
        $hydrator = function (array $data, object $instance) use ($columns, $crypto): object {
            foreach ($columns as $prop => $conf) {
                if (!array_key_exists($conf['column'], $data)) {
                    continue;
                }

                $rawVal = $data[$conf['column']];
                if ($rawVal !== null && $conf['encrypted']) {
                    $rawVal = $crypto->decrypt((string)$rawVal);
                }

                // Injeksi state langsung menembus private visibility
                $this->{$prop} = $rawVal;
            }
            return $instance;
        };

        // 2. Fast Extractor (Object -> Database Array)
        $extractor = function (object $instance) use ($columns, $crypto): array {
            $output = [];
            foreach ($columns as $prop => $conf) {
                $val = $this->{$prop} ?? null;
                if ($val !== null && $conf['encrypted']) {
                    $val = $crypto->encrypt((string)$val);
                }
                $output[$conf['column']] = $val;
            }
            return $output;
        };

        return self::$cache[$class] = new EntityMetadata(
            tableName: $tableName,
            primaryKeyProperty: $pkProperty,
            primaryKeyColumn: $pkColumn,
            columns: $columns,
            hydrator: $hydrator->bindTo(null, $class),
            extractor: $extractor->bindTo(null, $class)
        );
    }
}

// ============================================================================
// 5. DATA MAPPER REPOSITORY
// ============================================================================

final class AdvancedDataMapper
{
    public function __construct(
        private PDO $pdo,
        private EncryptionServiceInterface $crypto
    ) {}

    /**
     * @template T of object
     * @param class-string<T> $class
     * @return T|null
     */
    public function find(string $class, int|string $id): ?object
    {
        $meta = MetadataRegistry::get($class, $this->crypto);
        
        $sql = sprintf(
            'SELECT * FROM %s WHERE %s = :id LIMIT 1',
            $meta->tableName,
            $meta->primaryKeyColumn
        );

        $stmt = $this->pdo->prepare($sql);
        $stmt->execute(['id' => $id]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);

        if (!$row) {
            return null;
        }

        // Bikin instance kosong tanpa memanggil constructor (Bypass Constructor Arguments)
        $refClass = new ReflectionClass($class);
        $instance = $refClass->newInstanceWithoutConstructor();

        // Hydrate data via compiled pre-bound closure
        ($meta->hydrator)($row, $instance);

        return $instance;
    }

    public function save(object $entity): void
    {
        $class = $entity::class;
        $meta = MetadataRegistry::get($class, $this->crypto);

        // Ekstraksi data private melalui closure
        $data = ($meta->extractor)($entity);
        $pkValue = $data[$meta->primaryKeyColumn] ?? null;

        if ($pkValue === null) {
            // INSERT
            unset($data[$meta->primaryKeyColumn]);
            $columns = implode(', ', array_keys($data));
            $placeholders = ':' . implode(', :', array_keys($data));
            
            $sql = sprintf('INSERT INTO %s (%s) VALUES (%s)', $meta->tableName, $columns, $placeholders);
            $stmt = $this->pdo->prepare($sql);
            $stmt->execute($data);

            // Set Primary Key kembali ke instance
            $lastId = (int)$this->pdo->lastInsertId();
            $setter = function (string $pk, int $val) {
                $this->{$pk} = $val;
            };
            $setter->bindTo($entity, $class)($meta->primaryKeyProperty, $lastId);
        } else {
            // UPDATE
            $fields = [];
            foreach ($data as $col => $val) {
                if ($col === $meta->primaryKeyColumn) continue;
                $fields[] = "{$col} = :{$col}";
            }
            $sql = sprintf('UPDATE %s SET %s WHERE %s = :pk', $meta->tableName, implode(', ', $fields), $meta->primaryKeyColumn);
            $data['pk'] = $pkValue;
            $stmt = $this->pdo->prepare($sql);
            $stmt->execute($data);
        }
    }
}

// ============================================================================
// 6. ASPECT-ORIENTED TRANSACTION INTERCEPTOR (DYNAMIC PROXY FACTORY)
// ============================================================================

final class TransactionProxyFactory
{
    /**
     * Membungkus service domain dengan Proxy Dynamic Interceptor untuk transaksi database ACID
     *
     * @template T of object
     * @param T $service
     * @return T
     */
    public static function create(object $service, PDO $pdo): object
    {
        $targetClass = new ReflectionClass($service);

        // Memanfaatkan anonymous class untuk membangun proxy struktural dinamis
        return new class($service, $pdo, $targetClass) {
            public function __construct(
                private readonly object $targetInstance,
                private readonly PDO $pdo,
                private readonly ReflectionClass $reflectedTarget
            ) {}

            public function __call(string $name, array $arguments): mixed
            {
                if (!$this->reflectedTarget->hasMethod($name)) {
                    throw new RuntimeException("Metode {$name} tidak ditemukan pada target.");
                }

                $method = $this->reflectedTarget->getMethod($name);
                $isTransactional = !empty($method->getAttributes(Transactional::class));

                if (!$isTransactional) {
                    return $method->invokeArgs($this->targetInstance, $arguments);
                }

                // Jalankan dalam proteksi transaksi ACID
                $this->pdo->beginTransaction();
                try {
                    $result = $method->invokeArgs($this->targetInstance, $arguments);
                    $this->pdo->commit();
                    return $result;
                } catch (Exception $e) {
                    $this->pdo->rollBack();
                    throw new RuntimeException(
                        "Transaksi dibatalkan karena kegagalan internal: " . $e->getMessage(),
                        (int)$e->getCode(),
                        $e
                    );
                }
            }
        };
    }
}

// ============================================================================
// 7. APLIKASI LAYANAN DOMAIN
// ============================================================================

class BankingService
{
    public function __construct(private AdvancedDataMapper $mapper) {}

    #[Transactional]
    public function executeTransfer(int $customerId, float $amount): void
    {
        /** @var Customer|null $customer */
        $customer = $this->mapper->find(Customer::class, $customerId);
        if (!$customer) {
            throw new RuntimeException("Nasabah dengan ID {$customerId} tidak ditemukan.");
        }

        $customer->credit($amount);
        $this->mapper->save($customer);
    }
}

// ============================================================================
// 8. TESTING & PIPELINE DEMONSTRASI (SQLITE IN-MEMORY)
// ============================================================================

// A. Siapkan Database dan Mock Key
$pdo = new PDO('sqlite::memory:', options: [
    PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION
]);

$pdo->exec("
    CREATE TABLE bank_customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        tax_number TEXT NOT NULL,
        account_balance REAL NOT NULL
    )
");

// 256-bit Key acak (32 byte -> 64 karakter hex)
$hexKey = sodium_bin2hex(sodium_crypto_secretbox_keygen());
$crypto = new SodiumEncryptionService($hexKey);
$mapper = new AdvancedDataMapper($pdo, $crypto);

// B. Simpan Customer Baru Melalui DataMapper (Enkripsi Transparan)
$alice = new Customer("Alice Springs", "NPWP-88192-X", 1500000.00);
$mapper->save($alice);
$aliceId = $alice->getId();

echo "--- 1. DATA TERSIMPAN DI DATABASE SECARA FISIK RAW ---\n";
$stmt = $pdo->query("SELECT * FROM bank_customers WHERE id = {$aliceId}");
$rawRow = $stmt->fetch(PDO::FETCH_ASSOC);
print_r($rawRow);

echo "\n--- 2. HYDRATION OBJECT POPO MELALUI COMPILED CLOSURES ---\n";
/** @var Customer $retrievedAlice */
$retrievedAlice = $mapper->find(Customer::class, $aliceId);
echo "Nama           : " . $retrievedAlice->getName() . "\n";
echo "Tax Number Dec : " . $retrievedAlice->getTaxNumber() . "\n";
echo "Saldo Awal     : " . $retrievedAlice->getBalance() . "\n";

echo "\n--- 3. EKSEKUSI AOP DYNAMIC PROXY TRANSACTION INTERCEPTOR ---\n";
$pureService = new BankingService($mapper);

/** @var BankingService $proxyService */
$proxyService = TransactionProxyFactory::create($pureService, $pdo);

// Eksekusi mutasi melalui proxy
$proxyService->executeTransfer($aliceId, 750000.00);

/** @var Customer $updatedAlice */
$updatedAlice = $mapper->find(Customer::class, $aliceId);
echo "Saldo Akhir    : " . $updatedAlice->getBalance() . "\n";
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Dimensi Arsitektural | PHP Reflection API | Magic Methods (`__call`/`__get`) | Static Code Generation (AOT) | PHP Traits |
| :--- | :--- | :--- | :--- | :--- |
| **Kecepatan Eksekusi (CPU)** | **Lambat:** Overhead traversing C struct Zend Engine dan alokasi zval. | **Sedang:** Tambahan 1 frame internal stack + dynamic dispatch lookup. | **Sangat Cepat:** Native PHP opcodes ter-cache penuh di OPcache. | **Sangat Cepat:** Dicompile sejajar dengan native class methods. |
| **Konsumsi Memori** | **Tinggi:** Setiap instance refleksi mengalokasikan memori runtime tersendiri. | **Sangat Rendah:** Menggunakan lookup internal hash table tanpa alokasi baru. | **Rendah:** Struktur data sudah terserialisasi rapi di Shared Memory. | **Rendah:** Memory footprint sama dengan metode reguler. |
| **Kapasitas Static Analysis** | **Nol:** IDE dan PHPStan/Psalm kehilangan konteks analisis sepenuhnya. | **Buruk:** Mengharuskan PHPDoc `@method` dan `@property` virtual hacks. | **Sempurna:** File fisik tersedia, type safety 100% tervalidasi. | **Sempurna:** Native PHP typing berlaku sepenuhnya. |
| **Fleksibilitas Desain** | **Maksimal:** Mampu memanipulasi private scope dan dynamic loading kapan saja. | **Tinggi:** Mengintersepsi method/property yang belum pernah dibuat. | **Kaku:** Membutuhkan langkah build terpisah sebelum kode dijalankan. | **Kaku:** Komposisi bersifat statis pada tahap kompilasi kode sumber. |
| **Debugging / Tracing** | **Sulit:** Stack trace tersembunyi di balik invokasi reflektif. | **Sangat Sulit:** Stack traces terpolusi panggilan virtual engine. | **Mudah:** Baris kode identik dengan file fisik yang di-trace. | **Mudah:** Standard stack trace. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Serialization Malfungsi pada Proxy & Reflection
Instance dari `ReflectionClass`, `ReflectionMethod`, atau objek `Closure` **tidak dapat diserialisasi** secara native (`serialize()` akan melempar `Exception: Serialization of 'Closure' is not allowed`).
*   *Mitigasi:* Jika kelas Domain dibungkus oleh Proxy dinamis atau memanfaatkan Metadata Registry di atas, implementasikan metode ajaib `__sleep()` / `__wakeup()` atau antarmuka `__serialize()` / `__unserialize()` untuk membuang instance refleksi sebelum diserialisasi ke dalam Redis/Session.

### 2. Penghancuran Inisialisasi Melalui `newInstanceWithoutConstructor`
Metode `ReflectionClass::newInstanceWithoutConstructor()` memotong seluruh logika validasi yang diletakkan programmer di dalam constructor.
*   *Bahaya Tersembunyi:* Properti bertipe non-nullable typed (`private string $name;`) akan berada dalam status *uninitialized*. Jika properti ini diakses sebelum hidrator mengisinya, PHP melempar `Error: Typed property App\Customer::$name must not be accessed before initialization`.

### 3. Masalah Inheritance pada Readonly Class (PHP 8.2+)
Jika sebuah kelas ditandai sebagai `readonly`, kelas turunannya juga **wajib** berupa `readonly`.
*   *Konsekuensi:* Dynamic Proxy berbasis pewarisan (*Inheritance-based Mocking/Proxying*) akan gagal total jika mencoba meng-extend kelas `readonly` tanpa mendeklarasikan `readonly` pada anonymous class pembungkusnya.

### 4. Siklus Referensi Memori pada Dynamic Closures
Ketika Anda mengikat closure: `$closure->bindTo($this, $this)`, jika closure tersebut disimpan sebagai properti di dalam `$this`, Anda telah membuat **Circular Reference** langsung (`$this -> closure -> $this`). 
*   *Dampak:* Garbage Collector siklis PHP (*Zend GC*) harus bekerja keras memindai zval nodes, berpotensi memicu kebocoran memori (*memory leak*) pada aplikasi persistent runtime (RoadRunner, Swoole, FrankPHP).

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Mengeksekusi Refleksi di Dalam Loop (The "N+1 Reflection" Anti-Pattern)
*   *Kesalahan Fatal:*
    ```php
    // BAD: Melakukan refleksi di dalam iterasi ratusan record
    foreach ($databaseRows as $row) {
        $ref = new ReflectionClass(Customer::class);
        $obj = $ref->newInstanceWithoutConstructor();
        // Hydrate...
    }
    ```
*   *Perbaikan Arsitektural:*
    Ekstrak metadata refleksi **sekali** sebelum perulangan (simpan dalam cache lokal), lalu gunakan fungsi hidrator compiled closure berulang kali seperti yang dicontohkan pada Seksi 10.

### 2. Menyalahgunakan `__call` untuk Meniru Multiple Inheritance
*   *Kesalahan Fatal:* Menggunakan `__call` untuk mem-forward pemanggilan metode ke 5 sub-objek berbeda untuk menyimulasikan multiple inheritance. Ini menghancurkan arsitektur clean-code, memperlambat pemanggilan fungsi hingga 4-5 kali lipat, dan merusak static analysis tooling.
*   *Perbaikan:* Gunakan Komposisi Murni (*Composition over Inheritance*) atau Traits terstruktur.

### 3. Modifikasi State Objek Readonly Lewat Refleksi
*   *Kesalahan:* Berasumsi bahwa `$refProperty->setValue($readonlyObj, $val)` selalu berhasil. Di PHP 8.1+, menulis ke properti `readonly` yang **sudah terinisialisasi** via refleksi akan tetap menghasilkan fatal error: `Cannot modify readonly property`.
*   *Solusi:* Inisialisasi properti `readonly` hanya sekali saat hidrasi jika objek diinstansiasi via `newInstanceWithoutConstructor`.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Strict Typing Tanpa Pengecualian:** Selalu letakkan `declare(strict_types=1);` di baris pertama setiap file arsitektur metaprogramming untuk mengeliminasi silent type conversions pada dynamic invocations.
2.  **Imutabilitas Atribut:** Selalu deklarasikan kelas Atribut sebagai `final readonly class`. Atribut tidak boleh memiliki mutable state internal; tugasnya murni sebagai pembawa metadata.
3.  **Pisahkan Metadata Parsing dari Request Lifecycle:** Lakukan parsing refleksi berat saat aplikasi melakukan *warm-up* (tahap kompilasi kontainer) dan simpan hasilnya dalam bentuk file konfigurasi native PHP ter-cache (seperti array metadata ter-cache yang siap di-include, ramah OPcache).
4.  **Manfaatkan Generator untuk Dataset Masif:** Jika hidrasi data berbasis refleksi memproses data dalam jumlah masif, gunakan kombinasi `Generator` (`yield`) agar penggunaan memori tetap konstan pada batas minimum ($O(1)$ memory).

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Benchmarking Profiling: Native vs Reflection vs Compiled Closure

Dalam mengeksekusi hydrasi properti private sebanyak 100.000 kali pengulangan (PHP 8.3 CLI):

| Metrik Pendekatan | Waktu Eksekusi (ms) | Peak RAM Allocation |
| :--- | :--- | :--- |
| **Native Direct Setter** | ~12 ms | ~2.1 MB |
| **ReflectionProperty::setValue()** | ~145 ms | ~8.4 MB |
| **Magic Method (`__set`) Loop** | ~68 ms | ~2.3 MB |
| **Compiled Pre-Bound Closure** | ~18 ms | ~2.2 MB |

### Strategi Akselerasi: Compiled Closures
Alih-alih memanggil `ReflectionProperty::setValue()` berulang kali di hot-path aplikasi Anda:

```php
// TEKNIK OPTIMASI KELAS SATU: Compile setter generator
function createOptimizedWriter(string $className, string $propertyName): Closure {
    return Closure::bind(
        function (object $target, mixed $value) use ($propertyName) {
            $target->{$propertyName} = $value;
        },
        null,
        $className
    );
}

// Sekali dikompilasi, setter ini mendekati kecepatan operasi properti native
$customerWriter = createOptimizedWriter(Customer::class, 'balance');
$customerWriter($customerInstance, 950000.00);
```

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Mitigasi Dynamic Class Instantiation Arbitrary Code Execution
Jangan pernah mengizinkan input dari user (seperti payload JSON atau parameter query string) menentukan nama kelas yang diinstansiasi secara dinamis:

```php
// RISIKO TINGGI RCE (Remote Code Execution)
$serviceClass = $_GET['handler'];
$service = new $serviceClass(); // Penyerang dapat mengoper kelas berbahaya
```

*Implementasi Hardening via FQCN Whitelist Registry:*
```php
final class ServiceFactory
{
    private const ALLOWED_SERVICES = [
        'user' => \App\Services\UserService::class,
        'order' => \App\Services\OrderService::class,
    ];

    public static function create(string $alias): object
    {
        if (!isset(self::ALLOWED_SERVICES[$alias])) {
            throw new \SecurityException("Upaya instansiasi kelas ilegal terdeteksi: {$alias}");
        }
        $class = self::ALLOWED_SERVICES[$alias];
        return new $class();
    }
}
```

### 2. Bahaya `unserialize()` RCE Gadget Chains
Metaprogramming sering menggunakan `__wakeup()`, `__destruct()`, atau `__toString()`. Penyerang dapat merangkai fungsi-fungsi internal ini (*POP Gadget Chains*) jika Anda memproses input eksternal menggunakan `unserialize()`.
*   **Aturan Wajib:** Selalu gunakan format data netral seperti JSON (`json_encode` / `json_decode`) untuk serialisasi state objek melalui network. Jangan gunakan `unserialize()` bawaan PHP pada untrusted input.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Debugging kode metaprogramming merupakan salah satu aspek tersulit di produksi karena stack trace standar tidak selalu menampilkan baris pemanggilan target yang dibungkus proxy.

### 1. Menstabilkan Stack Trace pada Dynamic Proxies
Saat membangun proxy runtime (`__call`), tangkap konteks pemanggil menggunakan `debug_backtrace(DEBUG_BACKTRACE_IGNORE_ARGS, 2)` guna menyematkan konteks file asli pada log error ketika terjadi exception:

```php
public function __call(string $method, array $args): mixed
{
    $trace = debug_backtrace(DEBUG_BACKTRACE_IGNORE_ARGS, 1)[0];
    
    $this->logger->debug("Dynamic Invocation Triggered", [
        'method' => $method,
        'caller_file' => $trace['file'] ?? 'unknown',
        'caller_line' => $trace['line'] ?? 0,
        'target_class' => $this->target::class
    ]);

    return $this->target->{$method}(...$args);
}
```

### 2. Pemeriksaan Opcodes Internal
Gunakan utilitas CLI bawaan PHP untuk melihat bagaimana opcode PHP menangani pemanggilan dinamis:
```bash
php -d opcache.enable_cli=1 -d opcache.opt_debug_level=0x10000 my_metaprogramming_script.php
```
Periksa apakah opcode yang dihasilkan berupa instruksi monomorfik langsung atau instruksi polimorfik lambat seperti `ZEND_CALL_TRAMPOLINE` (yang menunjukkan eksekusi jatuh ke dalam magic methods).

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```
+------------------------------------------------------------------------------------+
|               PHP METAPROGRAMMING CORE API CHEAT SHEET                             |
+------------------------------------------------------------------------------------+
| OPERASI                      | METODE IMPLEMENTASI TERTINGGI                       |
+------------------------------------------------------------------------------------+
| Buat Instance tanpa ctor     | $ref->newInstanceWithoutConstructor()               |
| Ambil Atribut Kelas          | $refClass->getAttributes(TargetAttr::class)         |
| Ambil Atribut Nested         | $refProp->getAttributes()                           |
| Fast Private State Read      | Closure::bind(fn($o) => $o->prop, null, $class)     |
| Dynamic Method Invocation    | $closure->call($targetObject, ...$args)             |
| Bypass Private Setter        | (Closure::bind(fn($o, $v) => $o->p = $v, null, $c)) |
| Cek Properti Terinisialisasi | $refProperty->isInitialized($instance)              |
+------------------------------------------------------------------------------------+
```

*   **Attributes:** Gunakan untuk metadata murni deklaratif.
*   **Reflection:** Gunakan untuk inspeksi statis, kompilasi container, dan warm-up cache. Hindari di dalam perulangan runtime hot-path.
*   **Closure Re-binding:** Gunakan untuk manipulasi state terenkapsulasi ultra-cepat (ORM Hydration, Object Cloning, Mocking).
*   **Dynamic Anonymous Proxies:** Gunakan untuk Cross-Cutting Concerns (Logging, Transaksi, Caching, Validasi).

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Uji pemahaman mendalam Anda terhadap arsitektur metaprogramming PHP.

### Pertanyaan Tingkat Dasar (Basic)
1. Kapan tepatnya sebuah kelas atribut PHP diinstansiasi menjadi objek runtime?
2. Mengapa properti dinamis (*dynamic properties*) didepresiasi sejak PHP 8.2? Jelaskan alasannya dari sudut pandang alokasi memori internal Zend Engine!
3. Apa perbedaan fundamental antara metode `$closure->bindTo($obj, $scope)` dan `$closure->call($obj, ...$args)`?
4. Apa yang terjadi jika kode Anda memanggil metode `newInstanceWithoutConstructor()` pada kelas yang memiliki properti non-nullable typed, lalu Anda langsung membaca properti tersebut tanpa mengisinya terlebih dahulu?
5. Apakah Atribut bawaan PHP 8 dapat memodifikasi logika fungsi target secara otomatis tanpa bantuan kode refleksi eksternal?

### Pertanyaan Tingkat Lanjut (Intermediate)
6. Bagaimana cara compiler OPcache mengoptimalkan atribut PHP, dan apa dampaknya terhadap konsumsi memori siklus request?
7. Jelaskan mekanisme kerja opcode trampoline (`ZEND_CALL_TRAMPOLINE`) saat magic method `__call` diaktifkan oleh Zend Engine!
8. Anda sedang merancang framework ORM. Mengapa menggunakan compiled closure (`Closure::bind`) jauh lebih disukai daripada menggunakan `ReflectionProperty::setValue` untuk menghidrasi ribuan baris entitas?
9. Bagaimana Anda mendesain kelas Proxy berbasis *anonymous class* agar mampu meneruskan pemanggilan metode bertipe referensi (`public function &getValue()`) tanpa memicu notice engine?
10. Sebutkan satu skenario di mana operasi pemanggilan `Closure::bind` gagal menembus batas enkapsulasi `private` suatu kelas target!

---

### Kunci Jawaban & Pembahasan Kuis

1. **Jawaban:** Atribut PHP **hanya** diinstansiasi ketika method `ReflectionAttribute::newInstance()` dipanggil secara eksplisit oleh kode program. Atribut tidak diinstansiasi secara otomatis saat kelas target di-load ke memori.
2. **Jawaban:** Properti dinamis memaksa Zend Engine mengalokasikan tabel hash sekunder (`properties`) di luar blok memori utama `zend_object` (`properties_table`). Alokasi heap sekunder ini menyebabkan fragmentasi memori, cache-miss CPU, dan menurunkan efisiensi eksekusi bytecode engine.
3. **Jawaban:** `bindTo()` menghasilkan clone objek Closure baru dengan konteks dan scope baru yang siap dieksekusi di kemudian hari (alokasi memori baru). Sedangkan `call()` langsung mengikat konteks dan mengeksekusi closure tersebut seketika dalam satu instruksi internal tanpa mengalokasikan objek closure persisten di memori.
4. **Jawaban:** Engine melempar error fatal: `Error: Typed property ... must not be accessed before initialization`, karena alokasi memori disiapkan tetapi penanda state `ZVAL_UNDEF` internal belum diganti dengan nilai valid apa pun.
5. **Jawaban:** **Tidak bisa.** Atribut PHP murni berupa metadata deklaratif pasif. Atribut tidak dapat memanipulasi, mengintersepsi, atau menyuntikkan kode ke dalam tubuh metode target tanpa adanya engine eksternal (seperti Proxy, Class Weaver, atau Reflection Inspector) yang secara aktif mengevaluasi atribut tersebut.
6. **Jawaban:** OPcache mengompilasi metadata atribut ke dalam shared memory bersama dengan bytecode kelas. Ini membuat metadata atribut langsung tersedia di memori bersama tanpa perlu re-parsing file disk, memotong memory allocation per-request hingga 0 byte untuk metadata statis.
7. **Jawaban:** Opcode trampoline adalah teknik kernel Zend Engine untuk menghindari alokasi stack frame C penuh yang berlebihan saat memproses `__call`. Engine menggunakan trampoline frame tunggal untuk mengemas parameter dan mengubah target instruksi langsung ke handler penanganan ajaib tanpa menduplikasi overhead fungsi C.
8. **Jawaban:** Karena `ReflectionProperty::setValue` memerlukan dynamic type checking, security scope checks, dan unboxing zval pada setiap pemanggilan tunggal di runtime C layer. Sebaliknya, compiled closure yang di-bind langsung mengeksekusi instruksi native opcode assignment (`ZEND_ASSIGN_OBJ`) secara langsung pada internal object hash/slot.
9. **Jawaban:** Deklarasi magic method `__call` pada anonymous class proxy harus didefinisikan dengan penanda referensi eksplisit: `public function &__call(string $name, array $args)` dan nilai kembalian dari target harus dikembalikan secara referensi (`return $this->target->$name(...$args)`).
10. **Jawaban:** Ketika scope kedua dari `Closure::bind` di-pass parameter string kelas yang salah atau diisi `null`. Jika scope parameter tidak secara eksplisit merujuk pada FQCN kelas pemilik properti `private` tersebut, engine akan menolak akses dan melempar `Fatal Error: Cannot access private property`.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Rancang Bangun: Zero-Dependency Attribute-Driven DI Container dengan Interceptor Hook

Bangun sebuah modul Dependency Injection Container mutakhir dari nol menggunakan berkas PHP tunggal atau lingkungan terisolasi dengan spesifikasi ketat berikut:

#### Spesifikasi Fungsional:
1.  **Attribute Auto-wiring:**
    *   Buat Atribut `#[Inject]` yang dapat diletakkan pada konstruktor atau properti individual untuk menginjeksi dependensi secara otomatis tanpa konfigurasi manual file service.
2.  **Lifecycle Management:**
    *   Buat Atribut `#[Singleton]` untuk menandai bahwa container hanya boleh membuat tepat satu instance dari kelas target di memori selama siklus proses berjalan.
3.  **Cross-Cutting Log Interceptor:**
    *   Buat Atribut `#[Benchmark]` yang jika disematkan pada suatu metode kelas, container akan mengembalikan objek Proxy dinamis yang secara otomatis menghitung durasi waktu eksekusi metode tersebut (dalam satuan mikrodetik) dan mencetaknya ke konsol sebelum mengembalikan data hasil eksekusi ke pemanggil.
4.  **Batas Kinerja:**
    *   Lakukan caching inspeksi constructor reflection. Setiap resolusi dependensi kelas untuk kedua kalinya dan seterusnya **dilarang keras** memanggil kembali `new ReflectionClass()`.

#### Skenario Uji Pembuktian Mandiri:
*   Definisikan antarmuka `PaymentGatewayInterface` dan implementasikan kelas `StripePaymentGateway`.
*   Tandai kelas `StripePaymentGateway` dengan `#[Singleton]`.
*   Definisikan kelas `CheckoutService` yang membutuhkan `PaymentGatewayInterface` di konstruktornya melalui `#[Inject]`, dan berikan anotasi `#[Benchmark]` pada metode `public function processOrder(float $amount)`.
*   Eksekusi container untuk me-resolve `CheckoutService`, jalankan `processOrder(250000)`, dan buktikan bahwa:
    1.  Dependensi terpasang tanpa konfigurasi array container manual.
    2.  Durasi eksekusi metode tercatat secara transparan.
    3.  Instance `PaymentGatewayInterface` yang diinjeksi adalah objek identik (*strictly identical via `===`*) pada pemanggilan ganda.