# BAB 07: Quiz, Challenge, & Knowledge Check
**Testing Rigor, Static Analysis & Mutation Testing**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Code Coverage vs. Mutation Score Indicator (MSI)
Jelaskan secara mendalam mengapa metrik *Line/Branch Code Coverage* 100% sering kali memberikan ilusi keamanan (*false sense of security*) pada sistem finansial atau misi-kritis. Bagaimana *Mutation Testing* (melalui Mutation Score Indicator / MSI pada Infection PHP) mengukur efektivitas rangkaian pengujian secara matematis dan semantik dibandingkan sekadar metrik eksekusi baris kode konvensional?

### Soal 1.2: Mekanisme Inferensi Tipe AST pada Static Analyzer
Bagaimana PHPStan dan Psalm melakukan analisis kode tanpa mengeksekusinya (*non-runtime evaluation*)? Jelaskan tahapan konversi kode sumber PHP menjadi *Abstract Syntax Tree* (AST), resolusi simbol, analisis aliran kontrol (*Control Flow Graph*), hingga *Type Narrowing* yang memungkinkan pendeteksian potensi `TypeError` atau `null pointer dereference` pada level analisis tertinggi (*Level 8 / Max*).

### Soal 1.3: Taksonomi Test Doubles (Gerard Meszaros)
Dalam domain testing modern, istilah "*Mock*" sering disalahgunakan untuk merujuk pada semua jenis *Test Double*. Bedakan secara presisi berdasarkan state vs. behavior verification karakteristik dari:
1. *Dummy Object*
2. *Fake Object*
3. *Stub*
4. *Spy*
5. *Mock Object*

Kapan penggunaan *Mocking* yang berlebihan (*over-mocking*) justru merusak nilai dari unit test dan menghasilkan arsitektur yang rapuh (*tautological tests*)?

### Soal 1.4: Isolasi State Database: Transaction Rollback vs. Database Migration Fixtures
Dalam *Integration Testing*, dua pendekatan populer untuk menjaga isolasi state database adalah: (1) Membungkus setiap test case di dalam transaksi database dan melakukan `ROLLBACK` di `tearDown()`, atau (2) Menjalankan migrasi ulang / me-reset skema menggunakan *in-memory* SQLite atau dedicated testing database. Analisis kelemahan fatal dari pendekatan *Transaction Rollback* ketika kode yang diuji melibatkan *nested database transactions* (Savepoints), DDL statements implisit commit, atau asynchronous worker yang membaca database pada koneksi terpisah.

### Soal 1.5: Static Analysis Annotations & Type System Extension
Jelaskan peran anotasi PHPDoc tingkat lanjut seperti `@template`, `@param class-string<T>`, dan `@return T` dalam bridging kelemahan sistem tipe PHP yang bertipe nominal dinamis. Bagaimana anotasi generics tersebut dievaluasi oleh engine static analysis untuk menjamin *type-safety* tanpa menimbulkan overhead performa di level runtime engine Zend?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Arsitektur Internal Infection PHP & Penanganan Infinite Loop
Infection PHP bekerja dengan cara memanipulasi AST menggunakan `nikic/php-parser` untuk menyuntikkan mutasi (*Mutators* seperti `MethodCallRemoval`, `LogicalAndNegation`, dll.). Ketika sebuah mutasi secara tidak sengaja menghasilkan *infinite loop* (misalnya mutasi pada kondisi terminasi `while` atau `for`), jelaskan mekanisme internal Infection PHP dalam mengisolasi proses eksekusi, mendeteksi `TimeoutException`, dan menandai mutasi tersebut sebagai *Timed Out* alih-alih menyebabkan seluruh test suite mengalami hanging.

### Soal 2.2: Memory Leak Profiling pada PHPUnit Test Suites Skala Masif
Sebuah test suite enterprise yang memiliki 12.000 test cases mengalami kegagalan *Out of Memory* (OOM) fatal di CI/CD runner meskipun `memory_limit` PHP telah dinaikkan ke 2GB. Telusuri bagaimana PHPUnit secara internal mereferensikan instance `TestCase`, fixtures, dan *event listeners* di memori selama siklus hidup pengujian. Properti internal apa yang sering menahan siklus hidup objek (*circular references*), dan bagaimana strategi mitigasi kode untuk membersihkan state memori pada `tearDown()`?

### Soal 2.3: Custom Dynamic Return Type Extensions di PHPStan
Bayangkan Anda memiliki arsitektur Service Locator atau Factory kustom:
```php
class ServiceContainer {
    public function get(string $serviceId): object { ... }
}
```
Secara default, PHPStan hanya mengetahui bahwa metode ini mengembalikan tipe `object`. Jelaskan secara teknis arsitektur untuk membangun *PHPStan Dynamic Method Return Type Extension* (`DynamicMethodReturnTypeExtension`) agar ketika pemanggil mengeksekusi `$container->get(PaymentGateway::class)`, PHPStan dapat menginferensikan tipenya secara presisi sebagai `PaymentGateway` tanpa perlu melakukan *type casting* manual atau anotasi `@var`.

### Soal 2.4: Mengatasi Limitasi Final Classes & Readonly Properties pada Mocking Engine
PHP 8.1 dan 8.2 memperkenalkan kata kunci `readonly` dan penggunaan luas `final class` untuk menjamin immutability dalam Domain-Driven Design (DDD). Namun, engine mock standar (seperti PHPUnit Mocks atau Mockery) gagal membuat proxy/subclass untuk class final dan tidak dapat dengan mudah memodifikasi state `readonly`. Bedakan solusi arsitektural yang elegan: kapan Anda harus menggunakan stream-wrapper runtime hacking (misal: `dg/bypass-finals`) vs. refactoring murni menggunakan interfaces dan *Fake Objects*?

### Soal 2.5: Konkurensi Paratest dan Race Condition State Fixture
Saat mempercepat runtime CI menggunakan Paratest (eksekusi paralel berbasis sub-process), sering kali terjadi *flaky tests* akibat *race condition* pada shared resource (misalnya database atau Redis cache). Jelaskan bagaimana arsitektur segregasi environment (seperti env variable `TEST_TOKEN`) diimplementasikan untuk menyediakan dynamic test database provisioning (`test_db_1`, `test_db_2`, dst.), serta bagaimana menangani data seeding yang idempotent antar worker.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck CI/CD Pipeline pada Monolith Skala Enterprise
* **Konteks:** Perusahaan fintech memiliki repositori monolitik PHP 8.3 dengan 18.000 automated tests. Pipeline CI membutuhkan waktu 65 menit untuk menyelesaikan seluruh tahapan: Linting, PHPStan Level Max, PHPUnit, dan Infection Mutation Testing. Lamanya pipeline ini menghambat deployment *hotfix* darurat ke sistem produksi.
* **Kondisi Eksisting:**
  * PHPUnit berjalan single-thread di mesin CI dengan 16 CPU cores.
  * Infection dijalankan pada seluruh codebase secara menyeluruh setiap push branch.
  * PHPStan tidak menggunakan result cache di persistent volume CI.
* **Pertanyaan Diagnostik & Solusi:**
  1. Rancang arsitektur pipeline CI/CD yang terdistribusi dan efisien. Bagaimana pembagian job (matrix/parallelization) harus diatur?
  2. Bagaimana cara mengonfigurasi Infection PHP agar hanya menguji mutasi pada baris kode yang berubah (*git diff/staged changes*) pada Pull Request tanpa mengorbankan integritas keseluruhan codebase?
  3. Bagaimana strategi caching layer untuk AST PHPStan dan Paratest database fixtures untuk memangkas execution time dari 65 menit menjadi di bawah 8 menit?

### Skenario B: Silent Under-Billing Bug Akibat Lemahnya Test Assertion
* **Konteks:** Sebuah platform payment gateway global memproses transaksi dengan parsing mata uang berbasis satuan terkecil (cents/sen). Bug lolos ke produksi di mana transaksi bernilai JPY (Zero-Decimal Currency) salah dikalikan dengan 100, menyebabkan *over-billing*, sedangkan transaksi EUR/USD mengalami truncation pembulatan float precision.
* **Kondisi Eksisting:**
  * Unit test memiliki *Line Coverage* 100% pada class `CurrencyConverter` dan `PaymentChargeService`.
  * Rangkaian test lulus tanpa error.
  * Berikut adalah implementasi kode dan unit test-nya:
    ```php
    // Implementasi
    public function calculateSmallestUnit(float $amount, string $currency): int 
    {
        $factor = $this->isZeroDecimal($currency) ? 1 : 100;
        return (int) round($amount * $factor);
    }

    // Unit Test Eksisting
    public function testCalculateSmallestUnit(): void 
    {
        $service = new CurrencyConverter();
        $result = $service->calculateSmallestUnit(10.50, 'USD');
        $this->assertNotNull($result);
        $this->assertIsInt($result);
    }
    ```
* **Pertanyaan Diagnostik & Solusi:**
  1. Identifikasi secara detail mengapa pengujian unit di atas masuk dalam kategori *assertion-free / weak-assertion anti-pattern*. Mutator apa pada Infection PHP yang akan *escaped* jika dijalankan pada test tersebut?
  2. Rekonstruksi unit test tersebut menggunakan pendekatan *Boundary Value Analysis* (BVA) dan *Equivalence Partitioning*, lengkap dengan data provider untuk berbagai format mata uang dan floating-point precision edge-cases.
  3. Konfigurasikan aturan PHPStan (termasuk *strict-rules* dan larangan loose float comparison) untuk mencegah konversi casting tipe yang tidak aman pada kalkulasi moneter.

### Skenario C: Modernisasi Legacy Codebase Tanpa Type Hinting ke PHPStan Level Max
* **Konteks:** Anda diangkat sebagai Lead Architect untuk memodernisasi aplikasi enterprise e-commerce PHP 7.4 yang sedang di-porting ke PHP 8.3. Codebase terdiri dari 350.000 baris kode yang ditulis tanpa deklarasi tipe (*type-hints*), menggunakan array multi-dimensi tanpa struktur pasti, dan sarat dengan `stdClass`. Saat PHPStan dijalankan pada Level 8, ditemukan 14.850 errors.
* **Kondisi Bisnis:** Manajemen menuntut agar fitur baru tetap dirilis setiap minggu. Menghentikan pengembangan (*code freeze*) untuk memperbaiki 14.850 errors adalah hal yang mustahil secara komersial.
* **Pertanyaan Diagnostik & Solusi:**
  1. Bagaimana Anda merancang strategi adopsi *Static Analysis Baseline* tanpa membiarkan *new technical debt* menyusup ke PR baru? Jelaskan mekanisme `phpstan --generate-baseline`.
  2. Buatlah *Architecture Decision Record* (ADR) singkat yang menentukan batas-batas toleransi migrasi tipe: kapan tim harus menggunakan `ArrayShape` (`array{id: int, name: string}`), kapan harus mengonversi menjadi PHP 8.2 `readonly` DTO, dan bagaimana peran conditional return types.
  3. Bagaimana aturan *Branch Protection* di GitHub/GitLab harus dikonfigurasi terkait status baseline dan skor MSI Infection untuk mengamankan proses modernisasi secara gradual?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Precision Core Accounting Ledger Engine dengan Quality Gate Mutlak

#### Problem Statement
Anda ditugaskan membangun modul inti akuntansi *Double-Entry Ledger Engine* yang bertugas membagi dan mengalokasikan saldo transaksi secara proporsional ke beberapa akun penampung (*Split Allocation Engine*), misalnya alokasi biaya platform, pajak, dan pencairan dana merchant. 

Sistem ini tidak boleh mengalami pembulatan yang hilang (*penny rounding errors*)—total debit dan kredit harus selalu seimbang hingga satuan terkecil. Modul ini adalah inti dari seluruh perputaran uang di perusahaan. Anda harus membuktikan bahwa modul ini mustahil ditembus oleh mutasi logika dan kelemahan tipe data.

#### Requirements
1. **Core Domain Model:**
   * Bangun Value Object `Money` yang immutable (menolak floating point, murni berbasis string/integer precision arithmetic menggunakan ekstensi `BCMath`).
   * Bangun `LedgerTransactionSplitter` yang memiliki fungsi mendistribusikan total amount ke beberapa target persentase (misal: 70%, 20%, 10%). Selisih sisa pecahan pembagian sen (*remainder penny*) harus dialokasikan ke entitas dengan bobot terbesar untuk menjamin *conservation of money*.
2. **Quality Gate Setup:**
   * **PHPStan Level Max + PHPStan Strict Rules:** Kode domain tidak boleh memiliki type-casting implisit, no dynamic properties, and explicit array shapes.
   * **PHPUnit 10+ Test Suite:** Menguji boundary values, validasi zero values, negative allocations, dan floating-point precision traps.
   * **Infection PHP:** Konfigurasi Mutation Testing dengan ambang batas **Min MSI (Mutation Score Indicator) = 100%** dan **Min Covered Code MSI = 100%** untuk domain `src/Domain/Ledger/`.

#### Constraints
* **Dilarang Keras** menggunakan floating-point primitives (`float`, `double`) dalam seluruh operasi kalkulasi.
* **Zero Escaped Mutants:** Tidak boleh ada mutator yang berstatus *Escaped* di dalam layer domain.
* **No Mocking Libraries allowed for Domain Logic:** Pengujian pada `LedgerTransactionSplitter` dan `Money` harus murni menggunakan state verification dan pure value objects (Zero Test Doubles).
* CI Execution Time untuk modul ini harus selesai dalam waktu kurang dari 15 detik.

#### Expected Output
1. File implementasi: `Money.php` (Value Object) dan `LedgerTransactionSplitter.php` (Domain Service).
2. File konfigurasi: `phpstan.neon` (dengan konfigurasi `level: max`, `treatPhpDocTypesAsCertain: true`, dan `phpstan-strict-rules`).
3. File konfigurasi: `infection.json5` dengan mutators kustom yang ketat dan konfigurasi MSI threshold 100%.
4. File unit test: `LedgerTransactionSplitterTest.php` yang tahan banting terhadap segala mutasi logika, mengantisipasi edge-cases pembagian sen tak hingga (misal sepertiga dari Rp 100).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan teoritis dan praktis antara Code Coverage (Line, Branch, Path) vs Mutation Testing (MSI, Mutation Code Coverage).
- [ ] Kategori dan semantik Test Doubles menurut standar Gerard Meszaros: Dummy, Stub, Fake, Spy, Mock.
- [ ] Cara kerja Static Analysis engine (AST generation, Symbol Table resolution, Control Flow Graph, Dynamic Type Inference).
- [ ] Mengapa floating-point IEEE 754 tidak boleh digunakan untuk perhitungan moneter, dan bagaimana membuktikannya via Static Analysis & Testing.
- [ ] Siklus hidup mutasi pada Infection PHP: Mutant Generation, Filtering, Test Execution per Mutant, Process Isolation, dan Metrics Aggregation.
- [ ] Perbedaan antara *Escaped Mutant*, *Killed Mutant*, *Errored Mutant*, dan *Timed Out Mutant*.
- [ ] Mengapa Transaction Rollback dalam database integration testing dapat menyembunyikan kegagalan transaksi riil di level produksi (Savepoint masking & Autocommit side effects).
- [ ] Mekanisme Dynamic Return Types dan Generics (`@template`, `@extends`, `@implements`) di PHPStan/Psalm.

### Saya tidak perlu menghafal:
- [ ] Seluruh sintaks node AST internal dari pustaka `nikic/php-parser`.
- [ ] Nama-nama konfigurasi spesifik dari setiap puluhan mutators bawaan Infection PHP (cukup memahami kategori logikanya: Conditionals, Boolean, Return Values, Arithmetic).
- [ ] Regular expression boilerplate untuk konfigurasi custom path filter di file konfigurasi XML/NEON.

### Saya harus bisa melakukan:
- [ ] Mendesain arsitektur pengujian piramida (Unit, Integration, E2E) yang seimbang tanpa terjebak dalam *over-mocking anti-pattern*.
- [ ] Mengonfigurasi dan mengintegrasikan PHPStan pada Level Max dengan package `phpstan/phpstan-strict-rules` dan `phpstan/phpstan-deprecation-rules`.
- [ ] Membaca laporan mutasi Infection PHP, melacak *Escaped Mutant*, dan menulis assertion yang presisi untuk membunuh mutant tersebut (*killing the mutant*).
- [ ] Menulis custom PHPStan dynamic return type extension untuk container dependency injection atau dynamic factory.
- [ ] Mengimplementasikan Test Data Fixtures yang terisolasi dan bebas race condition untuk pengujian konkuren via Paratest.
- [ ] Mengonfigurasi dan mengelola *PHPStan Baseline* untuk memandu proses refactoring aplikasi legacy secara terukur tanpa menghentikan velocity tim.