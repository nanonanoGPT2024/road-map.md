# Bab 09 Module 01: Enterprise Testing Strategy & Quality Assurance

---

### Seksi 01: Identitas Modul
* **Track:** Backend and Database Engineering
* **Kategori:** 04-Backend-and-Database
* **Framework:** Laravel 11.x / PHP 8.3+
* **Topik:** Enterprise Testing Strategy & Quality Assurance
* **Level:** Advanced (L4/L5)
* **Prasyarat:** Pemahaman mendalam tentang Laravel Service Container, Database Migrations/Transactions, HTTP Middleware, Mocking Concept, serta PHPUnit/Pest dasar.

---

### Seksi 02: Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. Merancang dan mengimplementasikan piramida testing enterprise (Unit, Feature, Integration, Contract, dan Architecture Tests) menggunakan **Pest PHP v3** dan **PHPUnit 11**.
2. Mengisolasi state database secara efisien pada skala ribuan test suite menggunakan kombinasi `LazilyRefreshDatabase`, SQLite in-memory, dan transactional fixtures.
3. Menerapkan teknik advanced mocking dan virtualisasi third-party I/O via Laravel Facades (`Http::fake()`, `Event::fake()`, `Queue::fake()`, `Notification::fake()`, `Storage::fake()`).
4. Mengimplementasikan Mutation Testing menggunakan **Infection PHP** untuk mengidentifikasi false positives dan blind spots pada code coverage.
5. Membangun pipeline CI/CD yang terdistribusi menggunakan GitHub Actions matrix execution dan database sharding untuk mempertahankan execution time di bawah 3 menit.

---

### Seksi 03: Concept Map Diagram ASCII
```
+-------------------------------------------------------------------------+
|                  ENTERPRISE TEST SUITE ARCHITECTURE                     |
+-------------------------------------------------------------------------+
                                     |
         +---------------------------+---------------------------+
         |                                                       |
+------------------+                                   +------------------+
| ARCHITECTURE/QA  |                                   |  EXECUTION ENGINE|
| - Pest Arch      |                                   |  - Paratest (CI) |
| - PHPStan Level 9|                                   |  - Mutation Test |
| - Infection PHP  |                                   |    (Infection)   |
+--------+---------+                                   +--------+---------+
         |                                                       |
+--------v-------------------------------------------------------v---------+
|                         THE TESTING PYRAMID                             |
+-------------------------------------------------------------------------+
| [ E2E / CONTRACT ]  Pact PHP / Playwright API                           |
|                     - Schema compatibility, Provider Verification       |
+-------------------------------------------------------------------------+
| [ INTEGRATION    ]  Feature Tests (External Boundaries)                 |
|                     - Redis Cache, Elasticsearch, Third-Party Gateways  |
+-------------------------------------------------------------------------+
| [ FEATURE / HTTP ]  Laravel HTTP Tests + Database State                 |
|                     - Routing, Middleware, Policies, DB Transactions    |
|                     - Lazy Database Refresh Strategy                    |
+-------------------------------------------------------------------------+
| [ UNIT / DOMAIN  ]  Pure Domain Engine (Zero Framework Dependency)      |
|                     - Business Calculations, Value Objects, Aggregates |
|                     - Fast In-Memory Execution                          |
+-------------------------------------------------------------------------+
```

---

### Seksi 04: Mengapa Relevan
Dalam arsitektur enterprise berskala besar, kode tanpa automated testing yang komprehensif adalah *technical debt* yang tertunda. 
* **Regresi yang Mahal:** Biaya perbaikan bug pada production environment bisa mencapai 30x lipat lebih mahal dibandingkan penanganan pada fase CI.
* **Code Coverage Illusion:** Test suite dengan 100% line coverage sering kali memberikan rasa aman palsu (false sense of security) jika assertion logic tidak memverifikasi boundary state atau invariant domain secara ketat.
* **Execution Bottlenecks:** Test suite yang lambat (10-30+ menit) memicu *broken window syndrome*, di mana developer mulai mengabaikan test lokal dan membypass CI, menurunkan *lead time to changes* secara drastis.

---

### Seksi 05: Anatomi Konsep Inti

#### 1. The Pyramid Breakdown
* **Unit Tests:** Memverifikasi unit terkecil (fungsi, class method, value object) tanpa menyentuh I/O, database, atau framework container. Eksekusi dalam hitungan mikrodetik.
* **Feature Tests:** Menguji use case aplikasi end-to-end melalui transport layer (HTTP Request/Job/CLI Command) dengan dependency database yang diisolasi.
* **Integration Tests:** Memvalidasi integrasi antar subsistem (misal: Service Layer dengan Redis Cache, S3 Storage, atau Message Queue).
* **Architecture Tests:** Memastikan batasan arsitektur (misal: Controller tidak boleh memanggil Model secara langsung, Domain Entity tidak boleh depend pada Framework).

#### 2. Isolation Strategy: LazilyRefreshDatabase vs DatabaseTransactions
* `RefreshDatabase`: Menjalankan migrasi pada awal run, lalu membungkus setiap test case dalam database transaction.
* `LazilyRefreshDatabase`: Hanya melakukan rollback/transaction jika test case mengakses database via Eloquent/Query Builder. Menghemat alokasi I/O untuk test suite yang mixed.

#### 3. Mutation Testing (Infection PHP)
Mutation testing memodifikasi source code (misal: mengubah `>` menjadi `>=`, `true` menjadi `false`, menghapus pemanggilan method) dan menjalankan test suite. Jika test suite tetap *pass*, mutasi tersebut **Lolos (Escaped)**, menandakan assertion yang lemah.

---

### Seksi 06: Panduan Implementasi Step-by-Step

#### Step 1: Instalasi Core Dependencies
Instalasi Pest v3, Pest Plugin Laravel, Pest Plugin Architecture, dan Infection PHP via Composer.

```bash
composer require pestphp/pest --dev --with-all-dependencies
composer require pestphp/pest-plugin-laravel --dev
composer require pestphp/pest-plugin-arch --dev
composer require infection/infection --dev
```

#### Step 2: Konfigurasi PHPUnit & Environment
Sesuaikan `phpunit.xml` untuk performa maksimal dan isolasi testing.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<phpunit xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:noNamespaceSchemaLocation="./vendor/phpunit/phpunit/phpunit.xsd"
         bootstrap="vendor/autoload.php"
         colors="true"
         executionOrder="depends,defects"
         beStrictAboutOutputDuringTests="true"
         failOnRisky="true"
         failOnWarning="true">
    <testsuites>
        <testsuite name="Architecture">
            <directory>tests/Architecture</directory>
        </testsuite>
        <testsuite name="Unit">
            <directory>tests/Unit</directory>
        </testsuite>
        <testsuite name="Feature">
            <directory>tests/Feature</directory>
        </testsuite>
        <testsuite name="Integration">
            <directory>tests/Integration</directory>
        </testsuite>
    </testsuites>
    <source>
        <include>
            <directory>app</directory>
        </include>
    </source>
    <php>
        <env name="APP_ENV" value="testing"/>
        <env name="BCRYPT_ROUNDS" value="4"/>
        <env name="CACHE_STORE" value="array"/>
        <env name="DB_CONNECTION" value="sqlite"/>
        <env name="DB_DATABASE" value=":memory:"/>
        <env name="MAIL_MAILER" value="array"/>
        <env name="QUEUE_CONNECTION" value="sync"/>
        <env name="SESSION_DRIVER"