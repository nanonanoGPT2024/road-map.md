# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 09: Enterprise Testing Strategy & Quality Assurance — Kategori: 04-Backend-and-Database (Laravel)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis Internal Lifecycle Mesin Pengujian Laravel**: Membedah bagaimana `Illuminate\Foundation\Testing\TestCase` melakukan *bootstrapping*, manajemen Service Container per-test, serta siklus hidup isolasi state database (`DatabaseTransactions`, `RefreshDatabase`, `LazilyRefreshDatabase`).
2. **Merancang Pipeline Testing Paralel Berkinerja Tinggi**: Mengonfigurasi dan mengoptimasi eksekusi pengujian multi-proses via ParaTest/Laravel Parallel Testing dengan tokenisasi database dinamis untuk memangkas *runtime* pipeline CI/CD hingga di bawah 3 menit untuk ribuan test cases.
3. **Mengimplementasikan Strategi Mutation Testing**: Mengintegrasikan Infection PHP untuk mendeteksi *escaped mutants*, mengukur ketahanan test suite secara objektif melampaui metrik *code coverage* tradisional.
4. **Membangun Architecture Testing Enforcing System**: Menggunakan Pest Architecture Testing untuk memvalidasi batasan arsitektural (misal: Hexagonal/Clean Architecture, DDD boundaries) secara deterministik di level kompilasi test.
5. **Mengelola Mocking & Contract Testing Tingkat Lanjut**: Mengisolasi dependensi eksternal pihak ketiga (misal: Core Banking Engine, Payment Gateway) secara deterministik tanpa menimbulkan *memory leak* atau *container state pollution* lintas skenario uji.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
* Konsep OOP PHP 8.2/8.3 tingkat lanjut (*reflection*, *attributes*, *anonymous classes*, *fibers*, dan *weak references*).
* Arsitektur internal Laravel: Service Container resolution, Service Providers, Middleware pipeline, dan Event-Driven Architecture.
* Dasar-dasar PHPUnit atau Pest: *Assertions*, *Data Providers*, *Fixtures*, dan *Lifecycle Hooks* (`setUp`, `tearDown`).
* Konsep transaksi basis data ACID, isolasi level transaksi (*Read Committed*, *Repeatable Read*, *Snapshot Isolation*), serta engine locking.
* Penggunaan Docker & Docker Compose untuk orkestrasi *ephemeral test environment* (PostgreSQL/MySQL, Redis, RabbitMQ/Kafka).

---

## 3. Concept & Internal Architecture

### 3.1 Siklus Hidup Test Execution Engine Laravel

Setiap kali skenario pengujian dieksekusi di Laravel (`php artisan test` atau `phpunit`), runtime framework tidak bekerja secara statis seperti aplikasi monolitik konvensional. Framework melewati tahapan orkestrasi per-test class dan per-test method:

```
[Start Test Runner]
        │
        ▼
[Instantiate TestCase]
        │
        ├──> setUpBeforeClass() (PHPUnit static)
        │
        ▼
[Execution per Test Method]
        │
        ├──> setUp()
        │      ├──> $this->createApplication()
        │      │      ├──> Bootstrap Kernel (Fakade, Env, Providers)
        │      │      └──> Service Container Initialized ($app)
        │      ├──> Trait Bootstrapping:
        │      │      ├──> Database Isolation Setup (e.g. LazilyRefreshDatabase)
        │      │      ├──> Event/Queue/Bus Fakes Registry
        │      │      └──> Mockery Container Lifecycle Binding
        │      └──> Custom setUp Logic (User Land)
        │
        ├──> RUN TEST METHOD (Assertion, System Under Test / SUT)
        │
        └──> tearDown()
               ├──> Custom tearDown Logic (User Land)
               ├──> $this->beforeApplicationDestroyedCallbacks()
               ├──> Mockery::close() (Verify Mock Expectations)
               ├──> Database Rollback / Schema Truncate
               ├──> Flush Container (Unset $app, clear static instances)
               └──> Garbage Collection Hook
```

#### Komponen Internal Vital:
1. **`CreatesApplication` Trait**: Menginisialisasi `Illuminate\Foundation\Application` baru untuk setiap *method test*. Ini menjamin *state isolation*, tetapi membebani alokasi memori I/O jika ratusan Service Provider di-*re-register* berulang kali.
2. **Container Pollution**: Singleton yang mendaftarkan event listener statis atau me-resolve instance ke memory heap luar dapat bertahan jika `$this->app->flush()` tidak membersihkan seluruh static reference.
3. **Database Isolation Internals**:
   * `DatabaseTransactions`: Membungkus eksekusi test dalam `$db->beginTransaction()` pada `setUp()` dan mengeksekusi `$db->rollBack()` pada `tearDown()`. *Kelemahan*: Gagal memvalidasi transaksi yang memiliki `commit()` eksplisit di dalam kode produksi, dan tidak mendukung database DDL.
   * `RefreshDatabase`: Menginisialisasi migrasi penuh pada run pertama, lalu menggunakan transaksi per-test. Jika koneksi non-default digunakan, transaksi sekunder berisiko tidak terisolasi.
   * `LazilyRefreshDatabase`: Varian optimal dari `RefreshDatabase` yang hanya mengaktifkan transaksi basis data jika test bersangkutan benar-benar menyentuh model Eloquent atau Query Builder via `DB::table()`.

### 3.2 Dynamic Database Tokenization pada Parallel Testing

Ketika dijalankan dengan opsi `-p` (`--parallel`), Laravel memanfaatkan `brianium/paratest` yang membangkitkan *worker pool* independen berbasis sub-proses. 

Setiap worker dialokasikan token unik via environment variable `TEST_TOKEN`:
* Worker 1: `TEST_TOKEN=1` -> Basis Data: `testing_db_1`
* Worker 2: `TEST_TOKEN=2` -> Basis Data: `testing_db_2`

Laravel menangani migrasi paralel dengan menginjeksi schema dump terkompresi secara serentak ke masing-masing *worker schema*, menghindari race condition DDL locking pada satu basis data testing bersama.

---

## 4. Why & What

| Dimensi | Pendekatan Monolitik Naif (Legacy QA) | Pendekatan Enterprise Testing Strategy |
| :--- | :--- | :--- |
| **Database Isolation** | Truncate seluruh tabel per-test menggunakan SQLite in-memory. | Transaksi terisolasi PostgreSQL/MySQL dengan `LazilyRefreshDatabase` & DB tokenization. |
| **Verifikasi Mocking** | Mocking parsial manual, sering meninggalkan mock aktif yang mencemari test suite lain. | Strict Mock Lifecycle via Mockery/Pest Spies, bound langsung ke container lifecycle dengan validasi strict-types. |
| **Pipeline Throughput** | Serial execution, runtime 30-60 menit pada scale > 2.000 test cases. | Parallel execution distributed runners, runtime target < 3 menit via container caching & chunking. |
| **Kualitas Suite** | Line Code Coverage (persentase baris kode yang dieksekusi). | Mutation Score Indicator (MSI) via Infection, validasi semantic assertion boundary. |
| **Boundary Guard** | Code review manual via PR review tanpa jaminan mekanis. | Pest Architectural Testing yang memblokir PR jika domain model bocor ke layer infrastruktur. |

---

## 5. How (Workflow Detail)

Alur kerja enterprise testing terintegrasi dalam pipeline Continuous Delivery:

```
[Developer Commit / Push]
        │
        ├──> STAGE 1: Static Analysis & Architecture Rules
        │      ├──> PHPStan / Psalm (Level 8/Max)
        │      └──> Pest Architecture Assertions (Arch Tests)
        │
        ├──> STAGE 2: Fast Parallel Unit Tests
        │      └──> php artisan test --parallel --testsuite=Unit
        │
        ├──> STAGE 3: Parallel Integration & DB Feature Tests
        │      ├──> Spin up ephemeral DB & Redis (Docker Service Containers)
        │      └──> php artisan test --parallel --recreate-databases --testsuite=Feature
        │
        ├──> STAGE 4: Mutation Testing (Differential Analysis)
        │      └──> infection --threads=4 --min-msi=80 --git-diff-lines
        │
        └──> STAGE 5: External Contract Validation
               └──> OpenAPI Validator / Contract Provider Tests
```

---

## 6. Analogy & Diagram ASCII

Bayangkan sistem pengujian enterprise sebagai **Lini Perakitan Otomotif Berkecepatan Tinggi**:

* **Legacy Testing (Serial SQLite In-Memory)**: Menguji mesin mobil sungguhan menggunakan simulasi mesin mainan plastik (*SQLite in-memory*). Cepat, tetapi saat mobil asli diisi bahan bakar bensin bertekanan tinggi (*PostgreSQL transactions/locks*), mesin meledak di jalan raya karena karakteristik mesin mainan tidak memiliki batasan fisik mesin asli.
* **Enterprise Testing Architecture**: Mengoperasikan 8 jalur pengujian paralel independen (*ParaTest Workers*). Setiap jalur memiliki ruang uji baja kedap suara (*Isolated Database Schema `db_test_N`*). Saat satu mobil diuji benturan (*Feature Test Transaction*), sensor hidrolik (*LazilyRefreshDatabase*) langsung mengembalikan mobil ke kondisi utuh dalam hitungan milidetik (*Rollback*) tanpa perlu membangun ulang seluruh pabrik (*Drop & Re-migrate*).

```
   PARALLEL TEST EXECUTION ENGINE
   ┌────────────────────────────────────────────────────────┐
   │                  ParaTest Orchestrator                 │
   └───────────┬────────────────┬────────────────┬──────────┘
               │                │                │
     Worker 1 (PID 101)  Worker 2 (PID 102)  Worker N (PID 10N)
     TEST_TOKEN=1        TEST_TOKEN=2        TEST_TOKEN=N
         │                   │                   │
   ┌─────▼───────┐     ┌─────▼───────┐     ┌─────▼───────┐
   │ Postgres DB │     │ Postgres DB │     │ Postgres DB │
   │ Schema:     │     │ Schema:     │     │ Schema:     │
   │ tenant_db_1 │     │ tenant_db_2 │     │ tenant_db_N │
   └─────────────┘     └─────────────┘     └─────────────┘
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Dynamic Container Rebinding & Spy Verification

Contoh ini menunjukkan cara menguji service internal tanpa membocorkan state mock ke test berikutnya menggunakan lifecycle callback bawaan Laravel.

```php
declare(strict_types=1);

namespace Tests\Unit\Services;

use App\Contracts\SmsGatewayInterface;
use App\Services\NotificationDispatcher;
use Mockery;
use Mockery\MockInterface;
use Tests\TestCase;

final class NotificationDispatcherTest extends TestCase
{
    private SmsGatewayInterface&MockInterface $smsGatewayMock;
    private NotificationDispatcher $dispatcher;

    protected function setUp(): void
    {
        parent::setUp();

        // Mendaftarkan mock ke Container dan memastikan dibersihkan otomatis
        $this->smsGatewayMock = $this->mock(SmsGatewayInterface::class);
        $this->dispatcher = $this->app->make(NotificationDispatcher::class);
    }

    public function test_it_dispatches_sms_with_formatted_recipient(): void
    {
        // Arrange
        $rawPhone = '08123456789';
        $normalizedPhone = '+628123456789';
        $message = 'Kode OTP Anda: 994821';

        $this->smsGatewayMock
            ->shouldReceive('send')
            ->once()
            ->with($normalizedPhone, $message)
            ->andReturn(true);

        // Act
        $result = $this->dispatcher->sendOtp($rawPhone, '994821');

        // Assert
        $this->assertTrue($result);
    }
}
```

### 7.2 Practical Example: Enterprise Multi-Ledger High-Throughput Integration Test

Implementasi skenario riil finansial: Pengujian orkestrasi transaksi ledger transfer balance atomik dengan external lock validation, event assertion, dan outbox transactional safety.

```php
declare(strict_types=1);

namespace Tests\Feature\Banking;

use App\Domain\Ledger\Events\TransferCompleted;
use App\Domain\Ledger\Exceptions\InsufficientBalanceException;
use App\Domain\Ledger\Models\Account;
use App\Domain\Ledger\Services\TransferService;
use App\Domain\Ledger\ValueObjects\Money;
use App\Infrastructure\External\FraudDetectionClient;
use Illuminate\Foundation\Testing\LazilyRefreshDatabase;
use Illuminate\Support\Facades\Event;
use Mockery\MockInterface;
use Tests\TestCase;

final class HighThroughputTransferTest extends TestCase
{
    use LazilyRefreshDatabase;

    private TransferService $service;
    private FraudDetectionClient&MockInterface $fraudClientMock;

    protected function setUp(): void
    {
        parent::setUp();

        Event::fake([TransferCompleted::class]);

        $this->fraudClientMock = $this->mock(FraudDetectionClient::class);
        $this->service = $this->app->make(TransferService::class);
    }

    public function test_it_executes_atomic_money_transfer_successfully(): void
    {
        // Arrange: Siapkan state akun via factory dengan lock versioning
        /** @var Account $sourceAccount */
        $sourceAccount = Account::factory()->create([
            'balance_cents' => 1_000_000, // IDR 10,000.00
            'currency' => 'IDR',
            'is_active' => true,
        ]);

        /** @var Account $destinationAccount */
        $destinationAccount = Account::factory()->create([
            'balance_cents' => 200_000,
            'currency' => 'IDR',
            'is_active' => true,
        ]);

        $transferAmount = new Money(amountInCents: 500_000, currency: 'IDR');

        // Setup contract expectation untuk fraud client
        $this->fraudClientMock
            ->shouldReceive('evaluateTransaction')
            ->once()
            ->with(Mockery::on(fn (array $payload): bool => 
                $payload['source_account_id'] === $sourceAccount->id &&
                $payload['amount_cents'] === 500_000
            ))
            ->andReturn(true);

        // Act: Eksekusi domain service
        $transaction = $this->service->transfer(
            sourceAccountId: $sourceAccount->id,
            destinationAccountId: $destinationAccount->id,
            amount: $transferAmount,
            referenceNote: 'Settlement Invoice #INV-2024-001'
        );

        // Assert: Validasi mutasi state database secara presisi
        $this->assertDatabaseHas('accounts', [
            'id' => $sourceAccount->id,
            'balance_cents' => 500_000,
        ]);

        $this->assertDatabaseHas('accounts', [
            'id' => $destinationAccount->id,
            'balance_cents' => 700_000,
        ]);

        $this->assertDatabaseHas('ledger_transactions', [
            'id' => $transaction->id,
            'source_account_id' => $sourceAccount->id,
            'destination_account_id' => $destinationAccount->id,
            'amount_cents' => 500_000,
            'status' => 'COMPLETED',
        ]);

        // Verifikasi domain event terlempar dengan metadata valid
        Event::assertDispatched(TransferCompleted::class, static function (TransferCompleted $event) use ($transaction): bool {
            return $event->transactionId === $transaction->id &&
                   $event->amount->amountInCents === 500_000;
        });
    }

    public function test_it_rolls_back_atomically_when_source_balance_is_insufficient(): void
    {
        // Arrange
        $sourceAccount = Account::factory()->create([
            'balance_cents' => 100_000,
            'currency' => 'IDR',
        ]);

        $destinationAccount = Account::factory()->create([
            'balance_cents' => 50_000,
            'currency' => 'IDR',
        ]);

        $transferAmount = new Money(amountInCents: 500_000, currency: 'IDR');

        $this->fraudClientMock
            ->shouldReceive('evaluateTransaction')
            ->never();

        // Expectation & Act
        $this->expectException(InsufficientBalanceException::class);

        try {
            $this->service->transfer(
                sourceAccountId: $sourceAccount->id,
                destinationAccountId: $destinationAccount->id,
                amount: $transferAmount,
                referenceNote: 'Failed Transfer'
            );
        } finally {
            // Assert state tidak termutasi sama sekali (ACID guarantees)
            $this->assertDatabaseHas('accounts', [
                'id' => $sourceAccount->id,
                'balance_cents' => 100_000,
            ]);

            $this->assertDatabaseHas('accounts', [
                'id' => $destinationAccount->id,
                'balance_cents' => 50_000,
            ]);

            Event::assertNotDispatched(TransferCompleted::class);
        }
    }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Payment Switch Gateway (PT Transaksi Finansial Nusantara)
* **Konteks**: Sistem memproses 8.000 TPS, memiliki 4.200 unit & feature test cases.
* **Permasalahan**:
  1. Waktu eksekusi pipeline CI/CD mencapai **48 menit**, menghambat deployment hotfix produksi.
  2. Sering terjadi insiden *flaky tests* (1 dari 5 run gagal secara acak) karena *deadlock* pada koneksi database PostgreSQL terpusat saat test berjalan bersamaan.
  3. Metrik line-coverage mencapai 92%, namun bug kebocoran floating-point money precision lolos ke environment staging.

### Solusi Arsitektural:
1. **Parallel Test Runner Migration**:
   Mengimplementasikan ParaTest dengan alokasi 8 worker pool menggunakan arsitektur dynamic test DB naming:
   ```bash
   php artisan test --parallel --recreate-databases
   ```
2. **Deterministic Locking Strategy**:
   Mengubah isolasi test dari *DatabaseTruncation* menjadi `LazilyRefreshDatabase` yang dipadukan dengan PostgreSQL *Unlogged Tables* khusus environment testing untuk mereduksi I/O disk Write-Ahead Logging (WAL).
3. **Mutation Testing Enforcement via Infection**:
   Mengintegrasikan Infection CI differential analysis untuk mengeksekusi mutasi hanya pada line yang berubah di pull request:
   ```json
   {
       "source": {
           "directories": ["app/Domain"]
       },
       "mutators": {
           "@default": true,
           "FloatingPointRounding": true,
           "Cast": true
       }
   }
   ```

### Hasil:
* Runtime pipeline anjlok dari **48 menit** menjadi **2 menit 45 detik**.
* Tingkat kegagalan *flaky test* turun menjadi **0%**.
* Mutasi assertion menemukan 14 *boundary bugs* tersembunyi pada engine kalkulasi kurs valuta asing sebelum menyentuh branch `main`.

---

## 9. Trade-offs

| Pendekatan / Teknologi | Keuntungan (Pros) | Biaya / Konsekuensi (Cons) | Rekomendasi Penggunaan |
| :--- | :--- | :--- | :--- |
| **SQLite In-Memory (`:memory:`)** | Eksekusi sangat cepat, nol network I/O latency. | Dialek SQL berbeda dengan PostgreSQL/MySQL; tidak mendukung JSON path queries rumit, transactional locking (`SELECT FOR UPDATE`), & foreign key constraints bawaan. | Hanya untuk pengujian murni unit testing tanpa dependensi spesifik driver RDBMS. |
| **Testcontainers / Ephemeral Engine** | 100% paritas fungsional terhadap RDBMS target produksi (PostgreSQL/MySQL). | Memerlukan waktu *warm-up* container Docker (startup latency 5-15 detik) dan konsumsi RAM besar. | Wajib untuk Integration, Feature, dan Database Concurrency Testing di CI/CD. |
| **Comprehensive Mocking** | Menghilangkan latency dependensi jaringan eksternal; isolasi deterministik. | Rentan terhadap *False Positives* jika API eksternal mengubah payload spec tanpa pembaruan mock contract. | Padukan dengan Contract Testing (Pact / Prism OpenAPI schema validation). |
| **Full Mutation Testing (`infection`)** | Memberikan gambaran objektif kualitas pengujian; mengekspos logic gaps. | Sangat lambat dan memakan komputasi CPU intensif karena mengeksekusi test suite ratusan/ribuan kali per mutan. | Batasi eksekusi Mutation Testing hanya pada Pull Request diff (`--git-diff-lines`) di CI. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Memory Leak Akibat Event Listener atau Static Singleton
* **Gejala**: Pipeline parallel testing crash dengan pesan `Fatal error: Allowed memory size of X bytes exhausted`.
* **Akar Masalah**: Pendaftaran listener pada Service Provider atau third-party package yang menambahkan referensi closure ke variabel global/statis tanpa dibersihkan saat `$app->flush()`.
* **Solusi**: Tambahkan explicit cleanup pada `tearDown()`:
  ```php
  protected function tearDown(): void
  {
      Event::forget('custom.domain.event');
      Mockery::close();
      parent::tearDown();
  }
  ```

### 10.2 ParaTest Worker Deadlock pada Database Non-Isolated
* **Gejala**: Pipeline parallel berhenti (*hang*) tanpa error output, worker timeout setelah 10 menit.
* **Akar Masalah**: Test case Feature menggunakan koneksi basis data mentah yang mengabaikan `TEST_TOKEN`, sehingga Worker 1 dan Worker 2 memperebutkan lock table yang sama.
* **Solusi**: Pastikan koneksi basis data di `config/database.php` membaca token paralel:
  ```php
  'database' => env('DB_DATABASE', 'forge') . (parallel_testing_token() ? '_' . parallel_testing_token() : ''),
  ```

### 10.3 Asynchronous Queue Dispatched Assertions Missed
* **Gejala**: `Queue::assertPushed(ProcessSettlement::class)` gagal meskipun method memicu dispatch job.
* **Akar Masalah**: Job dieksekusi secara sinkron sebelum assert karena environment testing menggunakan driver `QUEUE_CONNECTION=sync`.
* **Solusi**: Gunakan `Queue::fake()` sebelum logic dijalankan, yang secara otomatis mengalihkan driver queue ke mock driver memori tanpa mengeksekusi job worker:
  ```php
  Queue::fake([ProcessSettlement::class]);
  // Execute SUT
  Queue::assertPushed(ProcessSettlement::class, 1);
  ```

---

## 11. Best Practices (Production Checklist)

- [ ] **Database Engine Parity**: Selalu gunakan database engine yang identik antara environment test dan environment produksi (cth: PostgreSQL 16 di kedua environment, bukan SQLite di test dan PostgreSQL di prod).
- [ ] **Gunakan `LazilyRefreshDatabase`**: Prioritaskan daripada `RefreshDatabase` reguler untuk memangkas overhead transaksi pada test yang tidak mengakses DB.
- [ ] **Deterministic Time Travel**: Hindari penggunaan `sleep()` dalam testing. Gunakan `$this->travelTo(now()->addDays(7))` atau `Carbon::setTestNow()`.
- [ ] **Strict Mock Expectations**: Hindari mock pasif tanpa batasan pemanggilan (`->shouldReceive('call')->zeroOrMoreTimes()`). Gunakan `once()`, `never()`, dan validasi argumen presisi via `Mockery::on()`.
- [ ] **Architecture Assertions**: Pasang Pest Architecture Test untuk menjaga domain boundaries.
- [ ] **Unlogged Database Tables di Testing**: Konfigurasikan instance DB PostgreSQL testing dengan `ALTER TABLE ... SET UNLOGGED` untuk akselerasi I/O drastis.
- [ ] **Zero Network Policy**: Pastikan CI pipeline menjalankan test suite dengan blokade jaringan keluar (isolasi sandbox) guna memastikan tidak ada test yang bergantung pada API eksternal live.

---

## 12. Hands-on Practice

Buat skenario hands-on berikut pada direktori: `hands-on/m02/`

### File Structure:
```
hands-on/m02/
├── composer.json
├── phpunit.xml
├── tests/
│   ├── ArchTest.php
│   ├── Feature/
│   │   └── PaymentGatewayTest.php
│   └── TestCase.php
```

### Langkah 1: Siapkan Konfigurasi `phpunit.xml` untuk Optimal Parallel Execution
Simpan pada `hands-on/m02/phpunit.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<phpunit xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:noNamespaceSchemaLocation="https://schema.phpunit.de/10.5/phpunit.xsd"
         bootstrap="vendor/autoload.php"
         colors="true"
         cacheDirectory=".phpunit.cache"
         executionOrder="depends,defects"
         beStrictAboutOutputDuringTests="true"
         failOnRisky="true"
         failOnWarning="true">
    <testsuites>
        <testsuite name="Arch">
            <directory>tests/ArchTest.php</directory>
        </testsuite>
        <testsuite name="Feature">
            <directory>tests/Feature</directory>
        </testsuite>
    </testsuites>
    <php>
        <env name="APP_ENV" value="testing"/>
        <env name="BCRYPT_ROUNDS" value="4"/>
        <env name="CACHE_STORE" value="array"/>
        <env name="DB_CONNECTION" value="pgsql_testing"/>
        <env name="QUEUE_CONNECTION" value="sync"/>
        <env name="SESSION_DRIVER" value="array"/>
    </php>
</phpunit>
```

### Langkah 2: Definisikan Pest Architecture Rules
Simpan pada `hands-on/m02/tests/ArchTest.php`:
```php
<?php

declare(strict_types=1);

test('Domain layer must not depend on Infrastructure or Controllers')
    ->expect('App\Domain')
    ->not->toUse([
        'App\Http\Controllers',
        'App\Infrastructure',
        'Illuminate\Http',
    ]);

test('Models must strictly reside within Domain namespace')
    ->expect('App\Domain\*\Models')
    ->toExtend('Illuminate\Database\Eloquent\Model');

test('Controllers must only interact with Application Actions or Queries')
    ->expect('App\Http\Controllers')
    ->not->toUse('Illuminate\Support\Facades\DB');

test('Strict typing must be enforced across all codebase')
    ->expect('App')
    ->toUseStrictTypes();
```

### Langkah 3: Integrasikan Feature Test dengan Mocking Resilient
Simpan pada `hands-on/m02/tests/Feature/PaymentGatewayTest.php`:
```php
<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Domain\Payment\Contracts\StripeClientInterface;
use App\Domain\Payment\DTOs\ChargeRequest;
use App\Domain\Payment\DTOs\ChargeResponse;
use App\Domain\Payment\Exceptions\PaymentGatewayTimeoutException;
use App\Domain\Payment\Services\CheckoutProcessor;
use Illuminate\Foundation\Testing\LazilyRefreshDatabase;
use Mockery\MockInterface;
use Tests\TestCase;

final class PaymentGatewayTest extends TestCase
{
    use LazilyRefreshDatabase;

    private StripeClientInterface&MockInterface $stripeClient;
    private CheckoutProcessor $processor;

    protected function setUp(): void
    {
        parent::setUp();

        $this->stripeClient = $this->mock(StripeClientInterface::class);
        $this->processor = $this->app->make(CheckoutProcessor::class);
    }

    public function test_it_handles_gateway_timeout_with_circuit_breaker_record(): void
    {
        // Arrange
        $chargeRequest = new ChargeRequest(
            orderId: 'ORD-99120',
            amountCents: 150000,
            idempotencyKey: 'idem-uuid-001'
        );

        $this->stripeClient
            ->shouldReceive('charge')
            ->once()
            ->withArgs(fn (ChargeRequest $req): bool => $req->orderId === 'ORD-99120')
            ->andThrow(new PaymentGatewayTimeoutException('Gateway timeout after 5000ms'));

        // Expectation
        $this->expectException(PaymentGatewayTimeoutException::class);

        // Act
        try {
            $this->processor->processCheckout($chargeRequest);
        } finally {
            // Assert audit trail tercatat meskipun terjadi exception eksternal
            $this->assertDatabaseHas('payment_audit_logs', [
                'order_id' => 'ORD-99120',
                'status' => 'FAILED_TIMEOUT',
            ]);
        }
    }
}
```

---

## 13. Exercise

### Tingkat Easy
Buat Unit Test untuk kelas Value Object `Email` (`App\Domain\Shared\ValueObjects\Email`).
* **Kebutuhan**: Validasi format email RFC 5322, verifikasi pelemparan `InvalidArgumentException` jika format salah, pastikan method `equals()` membandingkan case-insensitively.

### Tingkat Medium
Buat Feature Test untuk REST API Endpoint: `POST /api/v1/subscriptions/cancel`.
* **Kebutuhan**:
  1. Pastikan user terotentikasi via Laravel Sanctum.
  2. Mock external billing provider (`StripeClient::cancelSubscription`).
  3. Verifikasi kolom `cancels_at` di table `subscriptions` terisi timestamp yang sesuai dengan end-of-billing period.
  4. Uji kasus race-condition jika pembatalan dipanggil dua kali secara bersamaan (*Idempotency check*).

### Tingkat Hard
Bangun Custom Test Fixture Driver untuk menguji *Event-Driven Outbox Pattern*.
* **Kebutuhan**:
  1. Buat test suite yang memverifikasi transaksi database lokal dan entri tabel outbox ter-commit secara atomik.
  2. Implementasikan *Background Worker Simulation* yang mengambil data outbox dan mem-publish-nya ke in-memory bus.
  3. Simulasikan *Worker Crash* tepat setelah DB commit tetapi sebelum event terkirim, lalu buktikan bahwa worker berikutnya dapat me-resume tanpa event duplication.

---

## 14. Challenge

**Skenario**: Anda adalah Principal Software Engineer di bursa kripto tier-1. Sistem memiliki fitur *Flash-Order Matching Engine* yang mengeksekusi hingga ribuan order per detik pada database relasional terdistribusi.

**Tantangan**:
Rancang dan implementasikan Test Suite konseptual (lengkap dengan skenario concurrency assertion) yang membuktikan bahwa engine Anda **kebal terhadap serangan double-spending race conditions** ketika dua thread paralel mencoba menarik saldo dompet yang sama persis (misal balance: IDR 10.000.000, thread A mencoba menarik IDR 10.000.000 dan thread B mencoba menarik IDR 10.000.000 pada milidetik yang sama).

**Batasan Teknis**:
* Jangan gunakan delay statis (`sleep` / `usleep`).
* Pengujian harus mendeteksi deadlock resolution atau pessimistic locking isolation level (`SELECT FOR UPDATE`).
* Harus membuktikan secara matematis bahwa tepat satu transaksi berhasil (`COMPLETED`) dan transaksi kedua gagal dengan `InsufficientBalanceException` atau tertahan oleh transaction queue.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Konsep Dasar (5 Pertanyaan)
1. Apa perbedaan mekanisme kerja antara `DatabaseTransactions` dan `LazilyRefreshDatabase` pada pengujian Laravel?
2. Mengapa penggunaan `:memory:` pada SQLite sering menghasilkan *false positive* saat menguji fitur yang menggunakan database produksi PostgreSQL?
3. Apa fungsi environment variable `TEST_TOKEN` pada eksekusi test paralel bawaan Laravel?
4. Kapan method `Mockery::close()` dieksekusi dalam lifecycle pengujian berbasis `Illuminate\Foundation\Testing\TestCase`?
5. Apa dampak dari tidak membersihkan event listener yang didaftarkan secara statis selama proses `setUp()`?

### Bagian B: Analisis Lanjutan (5 Pertanyaan)
1. Jelaskan bagaimana *Mutation Score Indicator* (MSI) pada Mutation Testing memberikan metrik yang lebih akurat dibandingkan *Line Coverage Percentage*!
2. Bagaimana cara menguji Event Subscriber yang mengirimkan payload ke Queue tanpa benar-benar menjalankan proses queue worker pada environment testing?
3. Mengapa method `$this->freezeTime()` atau `$this->travelTo()` lebih disarankan daripada melakukan manipulasi langsung pada timestamp Carbon di dalam database factories?
4. Bagaimana arsitektur Pest Architecture Testing dapat mendeteksi pelanggaran batasan Clean Architecture tanpa perlu mengeksekusi logika method aplikasi?
5. Apa risiko potensial penggunaan `app()->instance()` untuk mocking singleton jika dependensi tersebut memiliki referensi siklik (*circular reference*)?

### Bagian C: Skenario Kasus Produksi (3 Pertanyaan)

#### Skenario 1: The Phantom Flaky Failure
Di pipeline CI/CD, test suite berjalan lancar ketika dieksekusi secara lokal pada mesin developer (`php artisan test`). Namun, saat berjalan di GitHub Actions dengan 8 thread paralel (`php artisan test --parallel`), 3 test case pada modul invoicing gagal secara acak dengan pesan:
`QueryException: Deadlock found when trying to get lock; try restarting transaction`.
*Jelaskan akar penyebab masalahnya di layer basis data dan berikan solusi arsitekturalnya!*

#### Skenario 2: The Mutant Apocalypse
Sebuah endpoint kritis verifikasi KYC memiliki code coverage 100%. Namun saat tim QA menjalankan Infection PHP, skor mutasi (MSI) hanya mencapai 38%, dengan sebagian besar mutan bertipe `LogicalAndNegation` dan `GreaterThanOrEqualToToGreaterThan` berstatus *Escaped*.
*Apa arti dari metrik ini terhadap integritas sistem verifikasi KYC Anda, dan langkah apa yang harus diambil pada test assertions Anda?*

#### Skenario 3: Memory Exhaustion on Massive Test Suite
Sebuah test suite enterprise yang memiliki 6.000 test cases mengalami crash pada test ke-3.500 dengan pesan `Out of Memory (Allocated 2GB)`. Developer menduga ada kebocoran memori pada Service Container Laravel.
*Bagaimana langkah sistematis Anda untuk melacak referensi memori yang tidak ter-garbage collect pada lifecycle TestCase Laravel?*

---

## 16. Summary

1. **Deterministic Lifecycle**: Pengujian enterprise menuntut pemahaman mendalam tentang bagaimana Laravel TestCase me-reboot aplikasi, mengisolasi container bindings, dan merestorasi basis data antar-skenario untuk menjamin zero cross-test pollution.
2. **True Database Parity**: Hindari ilusi kecepatan SQLite in-memory untuk pengujian integrasi enterprise. Manfaatkan Docker ephemeral PostgreSQL/MySQL instances bersama `LazilyRefreshDatabase` dan unlogged tables guna memperoleh validasi ACID sejati tanpa degradasi performa.
3. **Beyond Coverage Metrics**: *Code coverage* 100% dapat menyembunyikan kerapuhan logika assertion. Gunakan *Mutation Testing* untuk memverifikasi secara matematis bahwa test suite Anda benar-benar mampu menggagalkan perubahan logika tak terduga (*escaped mutants*).
4. **Architectural Enforcement**: Manfaatkan Architecture Testing secara terprogram untuk memvalidasi pemisahan dependensi (Domain vs Infrastructure) secara otomatis di pipeline CI/CD, mencegah erosi arsitektural seiring bertambahnya skala tim engineering.