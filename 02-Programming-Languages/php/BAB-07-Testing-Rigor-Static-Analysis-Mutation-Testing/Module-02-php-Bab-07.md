# Kurikulum Rekayasa Perangkat Lunak Enterprise: PHP
## Bab 07: Testing Rigor, Static Analysis & Mutation Testing
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Principal Software Engineer / Lead Architect diharapkan mampu:
- Mengonfigurasi, mengoptimasi, dan memvalidasi sistem penjaminan mutu statis level tertinggi (PHPStan Level 9/Max) dengan aturan inferensi tipe kustom (*custom AST rules*).
- Menjelaskan dan membongkar mekanisme internal *Static Analysis Engine* berbasis AST (*Abstract Syntax Tree*) serta *Mutation Testing Runner* pada PHP 8.2+.
- Membongkar ilusi *vanity metrics* dari *Code Coverage* 100% dan menggantikannya dengan *Mutation Score Indicator* (MSI) menggunakan Infection PHP.
- Mendesain arsitektur *Continuous Inspection Pipeline* di tingkat produksi yang mengeksekusi analisis mutasi secara paralel dan inkremental dengan konsumsi *compute resource* yang terukur.
- Mendiagnosis dan mengeliminasi *equivalent mutants* serta *escaped mutants* pada modul domain finansial berisiko tinggi (*high-stakes domain*).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **PHP 8.2+ Advanced Typing:** Union types, intersection types, disjunctive normal form (DNF) types, *generics via docblocks* (`@template`, `@implements`, `@extends`).
- **PHPUnit 10/11 Architecture:** Lifecycles, data providers, test doubles (mocks/stubs), assertion semantics.
- **Engine Internals Dasar:** Tokenization (`token_get_all`), Lexical Analysis, AST parsing via `nikic/php-parser`.
- **Ekstensi PHP CLI & Debugging:** Konfigurasi PCOV vs Xdebug untuk generasi coverage report.

---

### 3. Concept & Internal Architecture

#### 3.1 Anatomi AST dan Static Analysis Engine (PHPStan Internals)
Static Analyzer modern tidak mengeksekusi kode (*non-runtime execution*). Analisis dilakukan melalui lima tahapan berurutan:

```
[Source Code: .php]
       │
       ▼
[1. Lexer (Tokens)]  ─────────► Mengubah stream karakter menjadi lexical tokens (T_VARIABLE, dsb)
       │
       ▼
[2. Parser (nikic/php-parser)] ► Membentuk Abstract Syntax Tree (AST Nodes: Stmt, Expr, Scalar)
       │
       ▼
[3. Node Traverser & Scope Resolver] ──► Mengisi Symbol Table, melacak tipe variabel & variabel scope
       │
       ▼
[4. Type Inference Engine] ────► Evaluasi Dynamic Return Types, Generics Resolution, DNF Types
       │
       ▼
[5. Rule Evaluator]  ──────────► Menjalankan Registry Rule: Validasi tipe, pengecekan unreachable code
```

- **Lexer & Parser:** Mengurai *source code* menjadi representasi pohon berbasis node objek (`PhpParser\Node`).
- **Scope Resolver:** Ketika berjalan menyusuri AST, PHPStan mempertahankan objek `Scope`. Objek ini merekam *contextual state*: tipe variabel saat ini, apakah ada inferensi tipe via *type narrowing* (`instanceof`, `assert`), serta tipe *return* fungsi.
- **Type Inference Engine:** Menggunakan aljabar tipe (*type algebra*). Sebagai contoh: jika tipe awal adalah `string|null`, kemudian terdapat kontrol alur `if ($val === null) throw ...`, *engine* mereduksi tipe `$val` di baris berikutnya menjadi `string` (*non-empty type narrowing*).
- **Rule Engine:** Kumpulan *rules* yang mendaftar pada kelas node tertentu (misalnya `MethodCall`, `PropertyFetch`). Setiap kali *traverser* menyentuh node tersebut, `Rule::processNode(Node $node, Scope $scope)` dievaluasi untuk mendeteksi deviasi.

#### 3.2 Anatomi Mutation Testing (Infection PHP Internals)
*Line Coverage* hanya membuktikan bahwa sebuah baris dieksekusi oleh mesin PHP runtime, **bukan** bahwa baris tersebut memiliki spesifikasi assertif yang benar. Analisis Mutasi (*Mutation Testing*) menyuntikkan defek buatan ke dalam source code untuk menguji keandalan *test suite*.

Siklus Eksekusi Infection:
1. **Initial Suite Execution:** Mengeksekusi PHPUnit dengan PCOV untuk membuat baseline code coverage XML dan JUnit log. Baris tanpa coverage diabaikan (*optimization step*).
2. **AST Mutation Injection:** Membaca source code yang terlindungi test ke bentuk AST menggunakan `nikic/php-parser`. Mengaplikasikan kumpulan *Mutator* (misalnya: mengganti `>` menjadi `>=`, membalik `true` menjadi `false`, menghapus pemanggilan method void).
3. **AST Pretty Printing:** Menghasilkan source code PHP baru yang telah terinfeksi mutan di memori atau *temporary file*.
4. **Sandboxed Fork Process Execution:** Mengeksekusi test suite spesifik yang mencakup baris termutasi di dalam *isolated sub-process* menggunakan `symfony/process` dan driver konkurensi paralel (PCNTL).
5. **Verdict Classification:**
   - **Killed:** Test gagal (assertion exception / fatal error). Ini adalah hasil yang diinginkan: test menangkap mutan.
   - **Escaped:** Seluruh test tetap *pass* meskipun logika kode telah dirusak. Menandakan *assertion deficiency* pada test suite.
   - **Timeout:** Mutasi menyebabkan infinite loop. Dianggap *killed* berdasarkan ambang batas waktu.
   - **Error:** Mutasi menyebabkan syntax error fatal yang merusak runner.

Formulasi Metrik:
$$\text{Mutation Score Indicator (MSI)} = \frac{\text{Killed} + \text{Timeout} + \text{Error}}{\text{Total Mutants Generated}} \times 100\%$$

$$\text{Covered Code MSI} = \frac{\text{Killed} + \text{Timeout} + \text{Error}}{\text{Covered Mutants}} \times 100\%$$

---

### 4. Why & What

| Dimensi | Line Coverage (Tradisional) | Static Analysis (PHPStan Max) | Mutation Testing (Infection) |
| :--- | :--- | :--- | :--- |
| **Fokus Deteksi** | Eksekusi baris saat runtime | Inkonsistensi tipe, kontrak, & syntax parsing | Ketahanan semantik assertions |
| **Metrik Sukses** | Persentase baris terlewati (%) | Nol level-violation error | MSI $\ge 85\%$ |
| **Kelemahan Fatal** | Mengabaikan assertion logic (test tanpa assert tetap 100% cover) | Tidak mendeteksi kesalahan algoritma runtime | Komputasi CPU & waktu eksekusi sangat tinggi |
| **Siklus Evaluasi**| Per-commit / Pull Request | Pre-commit & CI Stage 1 (< 10 detik) | Pull Request (Delta) & Nightly CI |

---

### 5. How (Workflow detail)

```
[Developer pushes branch to Remote]
                │
                ▼
┌────────────────────────────────────────────────────────┐
│ Stage 1: Fast Feedback (< 30s)                         │
│ - PHPStan Analyze (Level: Max, Error format: github)   │
│ - Validasi Generics & Tipe DNF via Symbol Table cache  │
└───────────────────────┬────────────────────────────────┘
                        │ PASS
                        ▼
┌────────────────────────────────────────────────────────┐
│ Stage 2: Verification Engine (< 90s)                   │
│ - PHPUnit execution dengan Driver PCOV                 │
│ - Generate coverage-xml & junit-log                    │
└───────────────────────┬────────────────────────────────┘
                        │ PASS
                        ▼
┌────────────────────────────────────────────────────────┐
│ Stage 3: Mutation Rigor Engine (Delta-only via git)    │
│ - Infection PHP dijalankan dengan filter diff:         │
│   `infection --git-diff-filter=AM --min-msi=90`        │
│ - Parsing Covered AST -> Mutator -> Fork Execution     │
└───────────────────────┬────────────────────────────────┘
                        │
       ┌────────────────┴────────────────┐
     FAIL                              PASS
       ▼                                 ▼
 [Reject PR: Escaped Mutants]    [Merge Permitted]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem Keamanan Bangunan
- **Code Coverage:** Petugas keamanan berjalan melewati seluruh koridor gedung sambil menyalakan checklist. Pintu-pintu dilewati, tetapi ia tidak pernah memeriksa apakah kunci pintu tersebut terpasang atau rusak.
- **Static Analysis (PHPStan):** Pengecekan cetak biru arsitektur gedung oleh inspektur sipil. Memastikan bahwa dinding penopang tidak terbuat dari triplek dan tidak ada pipa air yang melintasi kabel tegangan tinggi terbuka sebelum semen dituangkan.
- **Mutation Testing (Infection):** Tim *Red Team Penetration Testing* diam-diam merusak sistem alarm, mencongkel engsel jendela, dan memutus suplai listrik cadangan secara acak untuk membuktikan apakah sistem deteksi keamanan benar-benar memicu alarm bahaya saat integritasnya dilanggar.

#### Pipeline Data Flow
```
        SOURCE FILE: OrderSettlement.php
                      │
                      ├──────────────────────────┐
                      ▼                          ▼
               PHPStan Engine             Infection Engine
                      │                          │
        ┌─────────────┴─────────────┐            ▼
        │ Parsing AST (Nikic)       │      Parse to AST
        │ Type Inference Engine     │            │
        │ Check: Generic Invariant  │            ▼
        └─────────────┬─────────────┘    Mutator Applied:
                      │                  "if ($balance > 0)"
                      │                  -> "if ($balance >= 0)"
                      ▼                          │
                PASS / FAIL                      ▼
                                          Execute PHPUnit
                                          (Process Fork)
                                                 │
                                        ┌────────┴────────┐
                                        ▼                 ▼
                                    Exit 0:            Exit 1+:
                                 MUTANT ESCAPED      MUTANT KILLED
                                 (Pipeline FAIL)    (Pipeline PASS)
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Ilusi 100% Coverage vs Mutation Failure

##### Source Code: `src/BoundaryCheck.php`
```php
<?php

declare(strict_types=1);

namespace Enterprise\Testing;

final class BoundaryCheck
{
    public function isSeniorCitizen(int $age): bool
    {
        // Mutator dapat mengubah '>' menjadi '>='
        if ($age > 60) {
            return true;
        }

        return false;
    }
}
```

##### Flawed Test: `tests/BoundaryCheckTest.php`
```php
<?php

declare(strict_types=1);

namespace Enterprise\Testing\Tests;

use Enterprise\Testing\BoundaryCheck;
use PHPUnit\Framework\TestCase;

final class BoundaryCheckTest extends TestCase
{
    /**
     * Test ini memberikan Line Coverage 100%, tetapi MUTATION TEST AKAN ESCAPED!
     * Alasan: Tidak ada pengujian pada boundary condition (age = 60).
     */
    public function testSeniorCitizenEvaluation(): void
    {
        $checker = new BoundaryCheck();
        
        self::assertTrue($checker->isSeniorCitizen(70));
        self::assertFalse($checker->isSeniorCitizen(30));
    }
}
```
*Hasil Infection:* Mutator mengganti `$age > 60` menjadi `$age >= 60`. Mutan dieksekusi dengan argumen 70 (tetap true) dan 30 (tetap false). Test lolos! Mutan **ESCAPED**. Skor MSI turun.

---

#### 7.2 Practical Enterprise Example: Financial Double-Entry Ledger Engine

Arsitektur riil domain perbankan dengan immutable value objects, PHPStan generic template contracts, dan assertion rigor tinggi.

##### Configuration: `phpstan.neon`
```neon
parameters:
    level: max
    paths:
        - src
    checkGenericClassInNonGenericObjectType: true
    checkMissingIterableValueType: true
    checkExplicitMixedMissingReturn: true
    treatPhpDocTypesAsCertain: true
```

##### Configuration: `infection.json5`
```json5
{
    "$schema": "vendor/infection/infection/resources/schema.json",
    "source": {
        "directories": [
            "src"
        ]
    },
    "logs": {
        "text": "infection.log",
        "html": "build/infection.html"
    },
    "mutators": {
        "@default": true,
        "MethodCallRemoval": {
            "ignore": [
                "Enterprise\\Ledger\\Domain\\Model\\Balance::assertNotNegative"
            ]
        }
    },
    "minMsi": 90,
    "minCoveredMsi": 95
}
```

##### Source Code: `src/Domain/Model/Money.php`
```php
<?php

declare(strict_types=1);

namespace Enterprise\Ledger\Domain\Model;

use InvalidArgumentException;

/**
 * Value Object Immutable untuk Operasi Moneter Presisi Tinggi.
 */
final readonly class Money
{
    /**
     * @param int<0, max> $amount Sen atau unit terkecil
     * @param non-empty-string $currency ISO-4217 code
     */
    public function __construct(
        public int $amount,
        public string $currency
    ) {
        if ($this->amount < 0) {
            throw new InvalidArgumentException("Amount cannot be negative: {$this->amount}");
        }

        if (strlen($this->currency) !== 3) {
            throw new InvalidArgumentException("Invalid ISO currency code: {$this->currency}");
        }
    }

    public function add(self $other): self
    {
        $this->assertSameCurrency($other);

        /** @var int<0, max> $newAmount */
        $newAmount = $this->amount + $other->amount;

        return new self($newAmount, $this->currency);
    }

    public function subtract(self $other): self
    {
        $this->assertSameCurrency($other);

        if ($this->amount < $other->amount) {
            throw new InvalidArgumentException(
                "Insufficient funds: {$this->amount} minus {$other->amount}"
            );
        }

        /** @var int<0, max> $newAmount */
        $newAmount = $this->amount - $other->amount;

        return new self($newAmount, $this->currency);
    }

    public function isGreaterThan(self $other): bool
    {
        $this->assertSameCurrency($other);
        return $this->amount > $other->amount;
    }

    private function assertSameCurrency(self $other): void
    {
        if ($this->currency !== $other->currency) {
            throw new InvalidArgumentException(
                "Currency mismatch: {$this->currency} !== {$other->currency}"
            );
        }
    }
}
```

##### Source Code: `src/Domain/Model/TransactionJournal.php`
```php
<?php

declare(strict_types=1);

namespace Enterprise\Ledger\Domain\Model;

use LogicException;

/**
 * Invariant: Jumlah Debit HARUS EQUAL dengan Kredit (Double-Entry Bookkeeping).
 */
final class TransactionJournal
{
    /**
     * @var list<Money>
     */
    private array $debits = [];

    /**
     * @var list<Money>
     */
    private array $credits = [];

    /**
     * @param non-empty-string $referenceId
     */
    public function __construct(
        public readonly string $referenceId
    ) {}

    public function addDebit(Money $money): void
    {
        $this->debits[] = $money;
    }

    public function addCredit(Money $money): void
    {
        $this->credits[] = $money;
    }

    public function verifySettlementBalance(): bool
    {
        if (count($this->debits) === 0 || count($this->credits) === 0) {
            throw new LogicException('A journal entry must contain at least one debit and one credit.');
        }

        $currency = $this->debits[0]->currency;

        $totalDebit = new Money(0, $currency);
        foreach ($this->debits as $debit) {
            $totalDebit = $totalDebit->add($debit);
        }

        $totalCredit = new Money(0, $currency);
        foreach ($this->credits as $credit) {
            $totalCredit = $totalCredit->add($credit);
        }

        return $totalDebit->amount === $totalCredit->amount;
    }
}
```

##### Test Suite Lengkap: `tests/Domain/Model/LedgerTest.php`
```php
<?php

declare(strict_types=1);

namespace Enterprise\Ledger\Tests\Domain\Model;

use Enterprise\Ledger\Domain\Model\Money;
use Enterprise\Ledger\Domain\Model\TransactionJournal;
use InvalidArgumentException;
use LogicException;
use PHPUnit\Framework\TestCase;

final class LedgerTest extends TestCase
{
    public function testMoneyInstantiationEnforcesInvariants(): void
    {
        $money = new Money(1000, 'USD');
        self::assertSame(1000, $money->amount);
        self::assertSame('USD', $money->currency);

        $this->expectException(InvalidArgumentException::class);
        /** @phpstan-ignore-next-line Edge case validation */
        new Money(-1, 'USD');
    }

    public function testMoneyInvalidCurrencyLength(): void
    {
        $this->expectException(InvalidArgumentException::class);
        $this->expectExceptionMessage('Invalid ISO currency code: US');
        new Money(100, 'US');
    }

    public function testMoneyAdditionAndSubtraction(): void
    {
        $m1 = new Money(100, 'IDR');
        $m2 = new Money(50, 'IDR');

        $resultAdd = $m1->add($m2);
        self::assertSame(150, $resultAdd->amount);

        $resultSub = $m1->subtract($m2);
        self::assertSame(50, $resultSub->amount);
    }

    public function testSubtractionPreventsNegativeBalance(): void
    {
        $m1 = new Money(50, 'IDR');
        $m2 = new Money(100, 'IDR');

        $this->expectException(InvalidArgumentException::class);
        $this->expectExceptionMessage('Insufficient funds');
        $m1->subtract($m2);
    }

    public function testCurrencyMismatchThrowsException(): void
    {
        $usd = new Money(100, 'USD');
        $idr = new Money(100, 'IDR');

        $this->expectException(InvalidArgumentException::class);
        $this->expectExceptionMessage('Currency mismatch: USD !== IDR');
        $usd->add($idr);
    }

    public function testIsGreaterThanBoundary(): void
    {
        $lower = new Money(99, 'USD');
        $current = new Money(100, 'USD');
        $higher = new Money(101, 'USD');

        self::assertTrue($current->isGreaterThan($lower));
        self::assertFalse($current->isGreaterThan($current)); // Kills GreaterThanOrEqualTo Mutator!
        self::assertFalse($current->isGreaterThan($higher));
    }

    public function testSettlementEmptyEntriesThrowsLogicException(): void
    {
        $journal = new TransactionJournal('TX-001');

        $this->expectException(LogicException::class);
        $this->expectExceptionMessage('at least one debit and one credit');
        $journal->verifySettlementBalance();
    }

    public function testSettlementBalancedPasses(): void
    {
        $journal = new TransactionJournal('TX-002');
        $journal->addDebit(new Money(500, 'USD'));
        $journal->addDebit(new Money(500, 'USD'));
        $journal->addCredit(new Money(1000, 'USD'));

        self::assertTrue($journal->verifySettlementBalance());
    }

    public function testSettlementUnbalancedFails(): void
    {
        $journal = new TransactionJournal('TX-003');
        $journal->addDebit(new Money(500, 'USD'));
        $journal->addCredit(new Money(499, 'USD'));

        self::assertFalse($journal->verifySettlementBalance()); // Kills boolean logic mutators
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### 8.1 Konteks Masalah
Sebuah platform Payment Aggregator memproses 12.000 settlement transaksi per detik. Sistem memiliki 98.4% unit test coverage. Namun, terjadi insiden finansial: dana terdebit ganda (*double payout*) senilai \$240.000 pada akun penjual tertentu saat eksekusi *batch reconciliation job*.

#### 8.2 Root Cause Analysis via Static Analysis & Mutation
Kode awal:
```php
// BatchSettlementService.php
foreach ($settlements as $settlement) {
    if ($settlement->isProcessed() || $settlement->isCancelled()) {
        continue;
    }
    
    // Injeksi API Transaksi
    $this->gateway->dispatchPayout($settlement);
}
```

- **Celah Tes Tradisional:** Unit test mock yang ada hanya mengevaluasi satu item dalam *array*, dengan status transaksi yang valid. Tes tidak menguji permutasi transaksi dengan berbagai kombinasi status (`isProcessed = true`, `isCancelled = false`, dll).
- **Mutasi yang Terlewat (Escaped):** Mutator Infection mengubah `||` menjadi `&&` (*LogicalOr to LogicalAnd*).
```php
// Mutated Code
if ($settlement->isProcessed() && $settlement->isCancelled()) {
    continue;
}
```
Ketika mutan ini diterapkan, test suite payment yang lama **tetap pass**! Ini membuktikan bahwa tidak ada assertion yang memverifikasi bahwa status `isProcessed()` secara mandiri mampu menghentikan eksekusi payout.

#### 8.3 Solusi Skala Produksi
1. Memperbaiki Test Assertion dengan *Truth Matrix Data Provider* yang mencakup 4 kuadran kondisi boolean.
2. Menerapkan PHPStan Rule kustom (`DisallowBooleanOrInCriticalPathRule`) untuk melarang logic statement bersarang pada domain finansial tanpa isolasi *Policy Method*.
3. Mengaktifkan Infection CI gate blocking pada git PR stage.

---

### 9. Trade-offs

```
                  Complexity / Coverage Rigor
                            ▲
                            │                  [Infection Mutation Testing]
                            │                  - Catch subtle bugs
                            │                  - Huge CPU/Time cost
                            │
                            │        [PHPStan Level Max]
                            │        - Zero runtime overhead
                            │        - High dev cognitive load
                            │
        [Unit Test (Line Cov)]
        - Fast, Cheap
        - Low defect fidelity
        ─────────────────────────────────────────────────────────────► Resource Cost / Execution Latency
```

| Pendekatan | Latency CI Pipeline | CPU & Resource Cost | Developer Cognitive Overhead | Fault Prevention Fidelity |
| :--- | :--- | :--- | :--- | :--- |
| **Line Coverage > 80%** | Sangat Rendah (< 1m) | Rendah (1 vCPU) | Rendah | Buruk (Bugs lolos) |
| **PHPStan Level Max** | Rendah (~10-30s) | Sedang (Memory intensive untuk AST)| Tinggi (Generics & Strict DNF) | Sangat Tinggi (Kontrak type-safe) |
| **Infection Full Suite** | Sangat Tinggi (10-45m) | Ekstrem (Multi-core scale)| Sedang (Menulis assertion ketat) | Tertinggi (Verifikasi logika semantik) |
| **Infection Git-Diff Only**| Sedang (1-3m) | Terkendali (Parallel execution) | Sedang | Tinggi (Terkonsentrasi pada perubahan) |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Equivalent Mutants (Mutan Setara)
**Problem:** Mutasi terjadi pada kode yang secara matematis/logis menghasilkan output yang sama persis, sehingga mutan mustahil dibunuh (*unkillable*). Hal ini merusak metrik MSI secara artifisial.
```php
// Original
for ($i = 0; $i < $total; $i++)

// Mutant (Infection)
for ($i = 0; $i <= $total - 1; $i++) // Nilai eksekusi identik!
```
**Troubleshooting:**
Konfigurasi `infection.json5` untuk mengabaikan mutator tertentu pada baris tersebut via docblock `@infection-ignore-all`, atau restrukturisasi menggunakan konstruksi modern PHP seperti `foreach ($items as $item)`.

#### 10.2 PHPStan Generics Baseline Abuse
**Problem:** Tim memaksakan PHPStan Level Max pada legacy code dengan cara men-generate `phpstan-baseline.neon` berukuran 10.000 baris. Pengembang baru menyembunyikan dynamic type errors ke dalam baseline daripada memperbaikinya.
**Troubleshooting:**
Gunakan tool `phpstan-baseline-analysis` pada CI. Tetapkan hard failure jika jumlah entri pada baseline bertambah:
```bash
vendor/bin/phpstan-baseline-analysis phpstan-baseline.neon --max-errors=150
```

#### 10.3 PCOV vs Xdebug Memory Exhaustion
**Problem:** Infection crash dengan `Out of Memory (OOM)` saat memproses coverage data report.
**Troubleshooting:**
Jangan gunakan Xdebug untuk mengumpulkan coverage di CI. Gunakan ekstensi **PCOV**.
Tambahkan parameter runtime pada PHP CLI:
```ini
php -d extension=pcov.so -d pcov.enabled=1 -d memory_limit=2G vendor/bin/infection --threads=max
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Strict Typing Pragma:** Seluruh file produksi dan test mengawali baris dengan `declare(strict_types=1);`.
- [ ] **PHPStan Max Level Zero-Tolerance:** Pipeline PR memblokir merge jika terdapat satu pun error pada PHPStan Level Max.
- [ ] **Type Narrowing Invariants:** Tidak pernah menggunakan `@phpstan-ignore` kecuali disertai link Issue Tracker dan justifikasi teknis arsitektural.
- [ ] **PCOV Integration:** CI Runner dikonfigurasi menggunakan PCOV driver untuk instrumentasi eksekusi AST yang 5-10x lebih cepat dibanding Xdebug.
- [ ] **Differential Mutation Testing:** Pada level Pull Request, jalankan infection hanya pada perubahan file (`--git-diff-filter=AM`).
- [ ] **Nightly Full Mutation Audit:** Full mutation testing dijalankan terjadwal di malam hari pada base branch utama untuk memetakan technical debt.
- [ ] **Target MSI Threshold:** Nilai Covered Code MSI (Mutation Score Indicator) dipatok minimal $\ge 85\%$ untuk modul domain core/billing.

---

### 12. Hands-on Practice

Struktur direktori yang disiapkan:
```
hands-on/m02/
├── composer.json
├── phpstan.neon
├── infection.json5
├── phpunit.xml
├── src/
│   └── DiscountCalculator.php
└── tests/
    └── DiscountCalculatorTest.php
```

#### Step 1: Inisialisasi Environment
Simpan konfigurasi paket pada `hands-on/m02/composer.json`:
```json
{
    "name": "enterprise/hands-on-m02",
    "type": "project",
    "autoload": {
        "psr-4": {
            "Enterprise\\HandsOn\\": "src/"
        }
    },
    "autoload-dev": {
        "psr-4": {
            "Enterprise\\HandsOn\\Tests\\": "tests/"
        }
    },
    "require-dev": {
        "phpunit/phpunit": "^11.0",
        "phpstan/phpstan": "^1.11",
        "infection/infection": "^0.29"
    },
    "config": {
        "allow-plugins": {
            "infection/extension-installer": true
        }
    }
}
```
Jalankan di shell terminal:
```bash
composer install
```

#### Step 2: Konfigurasi Tooling Enterprise
Simpan file `hands-on/m02/phpunit.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<phpunit xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:noNamespaceSchemaLocation="https://schema.phpunit.de/11.0/phpunit.xsd"
         bootstrap="vendor/autoload.php"
         colors="true"
         executionOrder="random"
         failOnRisky="true"
         failOnWarning="true">
    <testsuites>
        <testsuite name="Enterprise Hands-On Suite">
            <directory>tests</directory>
        </testsuite>
    </testsuites>
    <source>
        <include>
            <directory>src</directory>
        </include>
    </source>
</phpunit>
```

Simpan file `hands-on/m02/phpstan.neon`:
```neon
parameters:
    level: max
    paths:
        - src
        - tests
```

Simpan file `hands-on/m02/infection.json5`:
```json5
{
    "$schema": "vendor/infection/infection/resources/schema.json",
    "source": {
        "directories": [
            "src"
        ]
    },
    "mutators": {
        "@default": true
    }
}
```

#### Step 3: Implementasi Source Code
Simpan pada `hands-on/m02/src/DiscountCalculator.php`:
```php
<?php

declare(strict_types=1);

namespace Enterprise\HandsOn;

use InvalidArgumentException;

final class DiscountCalculator
{
    /**
     * Hitung diskon berdasarkan tier pesanan.
     *
     * @param int<0, max> $totalAmount
     * @return int<0, max>
     */
    public function calculateDiscount(int $totalAmount, bool $isVipMember): int
    {
        if ($totalAmount < 0) {
            throw new InvalidArgumentException('Total amount must not be negative');
        }

        if ($totalAmount >= 1000) {
            return $isVipMember ? 200 : 100;
        }

        if ($totalAmount >= 500) {
            return $isVipMember ? 100 : 50;
        }

        return 0;
    }
}
```

#### Step 4: Menulis Test Suite Pertama (Memiliki Celah Mutasi)
Simpan pada `hands-on/m02/tests/DiscountCalculatorTest.php`:
```php
<?php

declare(strict_types=1);

namespace Enterprise\HandsOn\Tests;

use Enterprise\HandsOn\DiscountCalculator;
use PHPUnit\Framework\TestCase;

final class DiscountCalculatorTest extends TestCase
{
    public function testDiscountBaseCases(): void
    {
        $calculator = new DiscountCalculator();

        // Mencapai 100% line coverage, TETAPI rentan terhadap mutasi boundary (>=)
        self::assertSame(200, $calculator->calculateDiscount(1500, true));
        self::assertSame(50, $calculator->calculateDiscount(600, false));
        self::assertSame(0, $calculator->calculateDiscount(100, false));
    }
}
```

#### Step 5: Eksekusi dan Analisis Celah Mutasi
Jalankan validasi statis dan PHPUnit:
```bash
vendor/bin/phpstan analyse
vendor/bin/phpunit --coverage-xml=build/coverage/coverage-xml --log-junit=build/coverage/junit.xml
```
*Hasil:* PHPStan Max lolos, PHPUnit 100% line coverage.

Jalankan Infection:
```bash
vendor/bin/infection --coverage=build/coverage
```
*Observasi Terminal:* Anda akan melihat mutan berstatus **ESCAPED**.
Infection memodifikasi `$totalAmount >= 1000` menjadi `$totalAmount > 1000`. Test suite tetap hijau karena input yang digunakan (1500) jauh melampaui boundary value (1000).

#### Step 6: Eliminasi Escaped Mutants
Perbarui `hands-on/m02/tests/DiscountCalculatorTest.php` untuk membunuh semua mutan:
```php
<?php

declare(strict_types=1);

namespace Enterprise\HandsOn\Tests;

use Enterprise\HandsOn\DiscountCalculator;
use InvalidArgumentException;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

final class DiscountCalculatorTest extends TestCase
{
    #[DataProvider('discountMatrixProvider')]
    public function testCalculateDiscountThoroughly(
        int $amount,
        bool $isVip,
        int $expectedDiscount
    ): void {
        $calculator = new DiscountCalculator();
        self::assertSame($expectedDiscount, $calculator->calculateDiscount($amount, $isVip));
    }

    /**
     * @return array<string, array{int, bool, int}>
     */
    public static function discountMatrixProvider(): array
    {
        return [
            'tier1-vip-above-threshold'    => [1500, true, 200],
            'tier1-vip-exact-boundary'     => [1000, true, 200], // Kills >= to > mutant
            'tier1-regular-exact-boundary' => [1000, false, 100],
            'tier2-vip-exact-boundary'     => [500, true, 100],  // Kills >= to > mutant
            'tier2-regular-exact-boundary' => [500, false, 50],
            'below-tier2-vip'              => [499, true, 0],    // Boundary check low
            'below-tier2-regular'          => [499, false, 0],
            'zero-amount'                  => [0, false, 0],
        ];
    }

    public function testNegativeAmountThrowsException(): void
    {
        $calculator = new DiscountCalculator();
        $this->expectException(InvalidArgumentException::class);
        /** @phpstan-ignore-next-line Negative testing */
        $calculator->calculateDiscount(-1, false);
    }
}
```

Jalankan ulang:
```bash
vendor/bin/phpunit --coverage-xml=build/coverage/coverage-xml --log-junit=build/coverage/junit.xml
vendor/bin/infection --coverage=build/coverage
```
*Hasil Akhir:* **Mutation Score Indicator (MSI) mencapai 100%. Semua mutan killed.**

---

### 13. Exercise

#### Level: Easy
1. Modifikasi class `Money` pada Bagian 7.2. Tambahkan method `isZero(): bool`.
2. Tulis PHPUnit assertion yang memiliki 100% Line Coverage, tetapi sengaja biarkan mutasi `=== 0` menjadi `== 0` atau `< 0` berstatus *Escaped*.
3. Perbaiki test tersebut sehingga Infection memverifikasi status *Killed*.

#### Level: Medium
1. Implementasikan Generic Collection class: `TypedCollection<T of object>`. Class harus mengimplementasikan `IteratorAggregate` dan `Countable`.
2. Validasi dengan PHPStan Level Max sehingga seluruh pemanggilan iterator mempertahankan *type safety* tanpa runtime casting (`@var`).
3. Buat implementasi fungsi sorting di dalamnya dan capai MSI Infection minimal 92%.

#### Level: Hard
1. Buat sistem state machine: `OrderStateMachine` (`DRAFT`, `PENDING_PAYMENT`, `PAID`, `CANCELLED`).
2. Transisi hanya boleh terjadi via method `transitionTo(OrderState $newState): void`.
3. Terapkan validasi matrix transisi yang kompleks.
4. Buat test suite yang mematikan mutasi Infection pada mutator: `TrueValue`, `FalseValue`, `LogicalAnd`, `LogicalOr`, dan `IdenticalEqual`. Gating ketat: MSI harus 100% tanpa eksepsi *ignore*.

---

### 14. Challenge

#### Deskripsi Masalah Nyata
Sebuah bank investasi internasional mempekerjakan Anda untuk merekayasa ulang komponen settlement dividen saham otomatis (`DividendDistributionEngine.php`). Komponen ini mendistribusikan dividen tunai kepada investor dengan ketentuan:
1. Investor dengan status `SUSPENDED` tidak boleh menerima alokasi saldo, dan alokasi mereka harus dimasukkan ke dalam sub-akun escrow khusus.
2. Pajak dividen dipotong otomatis: 10% untuk entitas domestik, 20% untuk non-residen, 0% untuk entitas dengan sertifikat bebas pajak terverifikasi.
3. Seluruh pembagian nominal tidak boleh kehilangan nilai fraksional uang (menggunakan Banker's Rounding / Round Half To Even).
4. Total nominal dividen yang terbagi + potongan pajak + escrow HARUS sama presisi secara absolut dengan total pool dividen yang disediakan korporasi. Selisih 1 sen sekalipun harus melempar domain exception `ImbalancedDistributionPoolException` dan membatalkan seluruh transaksi secara atomic.

#### Instruksi Pengerjaan (Production Mandate)
- Implementasikan engine domain di atas dengan strict types dan PHPStan Level Max (Level 9). Tidak boleh ada error, tidak boleh ada file baseline.
- Tulis test suite komprehensif menggunakan PHPUnit 11.
- Jalankan Infection Mutation Testing dengan konfigurasi seluruh mutator default aktif.
- **Syarat Kelulusan Challenge:** **Mutation Score Indicator (MSI) WAJIB $\ge 95\%$** dan seluruh invariant akuntansi terlindungi tanpa ada false positive equivalents.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: 5 Pertanyaan Basic
1. Mengapa Line Coverage 100% tidak menjamin perangkat lunak bebas dari bug logika?
2. Pada arsitektur internal Static Analyzer, apa fungsi dari tahapan *Lexer*?
3. Sebutkan perbedaan esensial antara *Escaped Mutant* dan *Killed Mutant* pada Infection PHP!
4. Mengapa konfigurasi `declare(strict_types=1);` mutlak diwajibkan untuk memaksimalkan efektivitas PHPStan Level Max?
5. Mengapa driver PCOV lebih direkomendasikan dibanding Xdebug untuk kebutuhan Mutation Testing pada CI pipeline?

#### Bagian B: 5 Pertanyaan Intermediate
6. Jelaskan apa yang dimaksud dengan *Type Narrowing* pada PHPStan dan berikan contoh kodenya!
7. Apa yang dimaksud dengan *Equivalent Mutant*, dan mengapa fenomena tersebut menjadi masalah pada analisis mutasi?
8. Bagaimana Infection menentukan test suite mana yang harus dieksekusi untuk memvalidasi baris kode yang dimutasi?
9. Apa perbedaan dampak performa antara menjalankan analisis mutasi secara penuh (*full run*) dengan pendekatan *git-diff filtering*?
10. Pada PHPStan, bagaimana cara kerja inferensi tipe untuk array generik menggunakan notasi PHPDoc `@param array<string, int>`?

#### Bagian C: 3 Skenario Kasus Produksi
11. **Skenario 1:** Sebuah tim backend mengeluh bahwa pipeline CI mereka berjalan selama 75 menit semenjak Infection PHP ditambahkan. Analisis konfigurasi apa yang harus dilakukan dan bagaimana strategi arsitektur untuk memangkas waktu eksekusi hingga di bawah 5 menit tanpa menurunkan MSI?
12. **Skenario 2:** Anda menemukan sebuah method verifikasi otorisasi user `isActionAllowed(): bool` memiliki 100% line coverage pada unit test, namun mutator `LogicalOr` pada method tersebut tetap *Escaped*. Apa defisiensi terstruktur yang ada pada test suite tersebut dan bagaimana mendesain ulang tesnya?
13. **Skenario 3:** CI Anda mendeteksi error PHPStan: `Method Order::getCreatedAt() should return DateTimeImmutable but returns DateTimeInterface`. Di sisi lain, interface database driver memang hanya mendeklarasikan return type `DateTimeInterface`. Bagaimana cara Anda menyelesaikan konflik tipe ini di Level Max tanpa merusak type safety runtime?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian A: Konseptual
1. Karena Line Coverage hanya memverifikasi bahwa *instruction pointer* PHP melewati baris tersebut saat dieksekusi. Ia tidak memverifikasi apakah ada assertion yang memeriksa nilai output, efek samping (*side effects*), atau handling *edge case*.
2. Lexer mengubah urutan string mentah kode program menjadi token-token individual terstruktur (`T_STRING`, `T_IF`, dll.) sebelum dibentuk menjadi pohon sintaksis oleh Parser.
3. *Killed Mutant:* Mutasi kode buatan menyebabkan setidaknya satu test gagal (ekspektasi benar). *Escaped Mutant:* Mutasi kode buatan tidak menyebabkan satupun test gagal (test suite lemah dalam mendeteksi perubahan semantik).
4. Tanpa strict types, PHP akan melakukan *coercive typing* (misal string "1" dikonversi otomatis menjadi integer 1). PHPStan tidak dapat menggaransi invariansi tipe jika runtime coercion masih diizinkan secara implisit.
5. PCOV adalah ekstensi C khusus untuk coverage analysis yang membypass overhead komputasi besar milik Xdebug (seperti debugger breakpoints, stack profiling, dan tracing), menghasilkan eksekusi coverage hingga 10x lebih cepat.

#### Bagian B: Analisis Mendalam
6. *Type Narrowing* adalah reduksi himpunan tipe data dari suatu variabel di dalam kontrol alur tertentu. Contoh: Dari `string|null`, setelah blok `if ($val !== null)`, PHPStan memperlakukan tipe `$val` di dalam blok tersebut murni sebagai `string`.
7. Mutasi yang menghasilkan semantik perilaku dan komputasi runtime yang 100% setara dengan kode aslinya, sehingga mustahil dibuatkan assertion gagal. Hal ini menjadi masalah karena menurunkan metrik MSI secara tidak akurat.
8. Infection memanfaatkan output JUnit report dan PCOV coverage XML. File coverage tersebut memetakan setiap baris *source code* secara spesifik ke kelas dan method test mana saja yang melewatinya. Infection hanya memanggil unit test terpetakan tersebut saat menguji mutan.
9. *Full Run* melakukan parsing seluruh file, membentuk mutan untuk seluruh aplikasi, dan mengeksekusi ribuan sub-proses PHP. *Git-diff filtering* hanya menganalisis AST file yang berubah pada git index commit bersangkutan, mereduksi mutasi dari ribuan menjadi puluhan saja.
10. PHPStan parser memetakan string docblock tersebut ke dalam internal structure `ArrayType(StringType, IntegerType)`. Engine kemudian memvalidasi setiap assignment key-value pada array tersebut terhadap type validator engine.

#### Bagian C: Kasus Produksi
11. **Solusi Pipeline Skenario 1:**
    - Ganti Xdebug dengan PCOV di CI runner.
    - Ubah eksekusi pull request menjadi inkremental: tambahkan flag `--git-diff-filter=AM --git-diff-base=origin/main`.
    - Aktifkan utilisasi CPU multi-threading: `--threads=max`.
    - Simpan `infection-cache` antar eksekusi CI via actions cache key.
    - Jalankan full scan hanya pada schedule *nightly build*.
12. **Solusi Assertion Skenario 2:**
    - Defisiensi: Test suite kemungkinan besar hanya menguji skenario positif di mana kedua kondisi bernilai benar, atau hanya menguji nilai kembalian tanpa mengisolasi setiap branch logika.
    - Perbaikan: Tulis *combinatorial matrix test* (menggunakan PHPUnit `DataProvider`) yang mengevaluasi seluruh nilai kebenaran: `(true, false)`, `(false, true)`, `(false, false)`, dan `(true, true)`.
13. **Solusi PHPStan Max Skenario 3:**
    - Lakukan runtime validation (*type assertion narrowing*):
      ```php
      $date = $repository->getCreatedAt();
      if (! $date instanceof DateTimeImmutable) {
          throw new UnexpectedValueException('Expected DateTimeImmutable instance');
      }
      return $date;
      ```
    - Cara ini memberi tahu PHPStan Scope Resolver bahwa tipe telah ter-narrowing menjadi `DateTimeImmutable`, mempertahankan keamanan statis dan integritas runtime.

---

### 16. Summary

- **Static Analysis (PHPStan Max)** bertindak sebagai pelindung arsitektur struktural sebelum runtime, menjamin bahwa sistem kontrak antarmuka dan tipe data bersifat koheren, deterministik, dan bebas dari fatal typing errors.
- **Code Coverage** adalah metrik kuantitas, bukan kualitas. Skor 100% Line Coverage tanpa rigor assertion adalah ilusi keamanan kode.
- **Mutation Testing (Infection)** adalah verifikator kualitas assertion yang objektif. Dengan memodifikasi logika AST secara terprogram, pengembang dapat membuktikan keandalan test suite dalam menangkap defek.
- Menjalankan Continuous Inspection modern memerlukan strategi berimbang: analisis statis yang cepat pada level pre-commit, analisis mutasi inkremental berbasis *git-diff* pada level Pull Request, dan pengujian audit mutasi mendalam secara terjadwal di level master branch. Kombinasi ini menjamin sistem enterprise tahan banting tanpa mengorbankan kecepatan siklus *delivery*.