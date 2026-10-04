# Bab 07 Module 01: Testing Rigor, Static Analysis & Mutation Testing

---

## SEKSI 01 — IDENTITAS MODUL

* **Module ID:** `PHP-MOD-07-01`
* **Track:** 02-Programming-Languages / PHP
* **Level:** Advanced (L4 - Staff/Principal Engineer Foundation)
* **Prerequisites:** 
  * Arsitektur Berorientasi Objek & OOP Tingkat Lanjut PHP 8.2+
  * Penguasaan Dasar Unit Testing (PHPUnit 10+)
  * Konsep Abstract Syntax Tree (AST) & Type System
  * Dasar CI/CD Workflow (GitHub Actions/GitLab CI)
* **Tech Stack & Tooling:** 
  * PHP 8.2 / 8.3
  * PHPUnit 10.5+
  * PHPStan 1.10+ (Level Max / Bleeding Edge)
  * Infection PHP 0.29+
  * Composer 2.6+
  * Xdebug 3.3+ / PCOV 1.0+ (Driver Code Coverage)

---

## SEKSI 02 — LEARNING OBJECTIVES

1. **Mendekonstruksi Paradoks Line Coverage:** Membuktikan secara empiris mengapa 100% Line Coverage sering kali memberikan ilusi keamanan palsu (*false sense of security*) dalam rekayasa perangkat lunak mission-critical.
2. **Menguasai Static Analysis Tingkat Ekstrem:** Mengkonfigurasi, menerapkan, dan memperluas PHPStan hingga Level Max, memanfaatkan *generics*, *conditional return types*, serta type-narrowing yang ketat tanpa mengandalkan *mixed-types*.
3. **Mengoperasikan Mutation Testing dengan Infection:** Menganalisis cara kerja engine mutasi berbasis AST (`nikic/php-parser`), mengevaluasi *Mutants* (Killed, Escaped, Uncovered, Timed Out), dan mengukur *Mutation Score Indicator* (MSI).
4. **Membangun Testing Pipeline Deterministik:** Mengintegrasikan static analysis, dynamic assertion, dan mutation testing ke dalam continuous integration pipeline dengan execution-time teroptimasi via diff-filtering.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Ilusi Line Coverage vs Validasi Semantik
Sebagian besar tim rekayasa perangkat lunak menganggap metrik *Code Coverage* sebagai tolok ukur kualitas pengujian. Ini adalah jebakan mental mendasar. 

* **Line Coverage** hanya menjawab: *"Apakah baris kode ini dieksekusi oleh runtime saat test berjalan?"*
* **Assertion Testing** menjawab: *"Apakah output yang dihasilkan sesuai dengan ekspektasi spesifik penguji?"*
* **Static Analysis** menjawab: *"Apakah kode ini valid secara matematis dan tipe data untuk seluruh domain input yang mungkin, tanpa perlu menjalankannya?"*
* **Mutation Testing** menjawab: *"Jika implementasi logika diubah secara acak dan deterministik, apakah rangkaian test yang ada memiliki daya deteksi untuk menggagalkannya?"*

```
[ Mental Model: Kualitas Pengujian Multi-Dimensi ]

     Daya Deteksi Semantik
               ^
               |               [Mutation Testing (Infection)]
               |               - Memvalidasi kualitas assertions
               |               - Mengekspos boundary bugs
               |
               |      [Dynamic Unit Testing (PHPUnit)]
               |      - Memvalidasi 'happy path' & known edge cases
               |      - Tolok ukur: Line/Branch Coverage
               |
               | [Static Analysis (PHPStan Level Max)]
               | - Pembuktian tipe formal tanpa runtime execution
               | - Menjamin konsistensi domain types
               +--------------------------------------------------> 
                                                   Kompleksitas & Waktu
```

Mutation testing memandang rangkaian unit test Anda bukan sebagai penguji kode aplikasi, melainkan memperlakukan rangkaian test tersebut sebagai **sistem yang sedang diuji kualitasnya**. Kode aplikasi diinjeksikan cacat (*mutants*); jika test suite Anda tetap hijau (*passing*), test suite Anda cacat. Mutan tersebut dinyatakan **Escaped**. Test suite baru terbukti tangguh jika ia pecah (*red/failing*) ketika mutan diinjeksikan. Mutan tersebut dinyatakan **Killed**.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Pipeline Verifikasi Kode Multi-Lapis

Berikut adalah arsitektur verifikasi kode modern yang memadukan Static Analysis, Unit Testing, dan Mutation Testing dalam siklus pengembangan:

```
[ Source Code (PHP 8.2+) ]
           |
           +-----------------------------------------------+
           |                                               |
           v                                               v
[ Static Analysis Engine ]                     [ Dynamic Execution Engine ]
 (PHPStan Level Max + AST)                      (PHPUnit Tests + Coverage)
           |                                               |
    Is AST Sound?                                 Does Code Pass Tests?
    Type-Safe? Generics?                                   |
           |                                               v
     +-----+-----+                                 [ Code Coverage Engine ]
     |           |                                    (PCOV / Xdebug)
    FAIL        PASS                                       |
     |           |                                         v
   Abort         +--------------------------------> [ Coverage XML/Junit ]
                                                           |
                                                           v
                                              [ Mutation Testing (Infection) ]
                                                           |
                                             +-------------+-------------+
                                             | Mutator Engine (AST mod)  |
                                             | Creates N Mutation Forks  |
                                             +-------------+-------------+
                                                           |
                                                           v
                                              [ Run Tests Against Mutants ]
                                                           |
                                      +--------------------+--------------------+
                                      |                    |                    |
                                      v                    v                    v
                                   [KILLED]            [ESCAPED]           [TIMED OUT]
                                (Test Failed)        (Test Passed)       (Infinite Loop)
                                 Status: OK!        Status: DEFECT!        Status: OK!
                                                           |
                                                           v
                                              Calculate MSI Threshold
                                              (Target: >= 85% MSI)
```

### Siklus Hidup Eksekusi Mutasi Internal Infection

```
  Source File (.php)
         |
         v
  [nikic/php-parser] ---> Parse ke AST
         |
         v
  [Infection Mutators] -> Identifikasi Node AST yang bisa diubah (e.g. `>` ke `>=`)
         |
         v
  [Mutated Code In-Memory / Tmp]
         |
         v
  [Parallel Process Worker] -> Eksekusi PHPUnit Process (Targeted Tests via Coverage Map)
         |
         +--> Worker Exit Code != 0  ==> MUTANT KILLED (Sukses)
         +--> Worker Exit Code == 0  ==> MUTANT ESCAPED (Kegagalan Kualitas Test)
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Abstract Syntax Tree (AST) & Type Inference pada PHPStan
PHPStan tidak mengeksekusi kode PHP secara langsung (`eval` atau runtime execution dihindari demi keamanan dan isolasi). PHPStan mem-parsing token PHP menjadi Abstract Syntax Tree menggunakan parser internal (turunan dari `nikic/php-parser`). 
* **Reflection Provider:** Mengumpulkan metadata tentang classes, interfaces, methods, functions, dan constants dari kode sumber maupun extensions.
* **Type Inference Engine:** Menggunakan aljabar tipe (Union types, Intersection types, Template/Generics types) untuk menelusuri alur eksekusi variabel (*control-flow analysis*). Ketika sebuah baris memanggil `$order->calculateTotal()`, PHPStan melakukan narrow down tipe dari `$order` dari namespace root hingga local scope.

### 2. Mekanisme Mutasi AST pada Infection
Infection membaca coverage report dari PHPUnit (khususnya format `junit` dan format index coverage `coverage-xml`).
* **Coverage Mapping:** Infection tidak mengeksekusi seluruh test suite untuk setiap mutan. Infection membaca mapping: *"Baris X pada File Y dieksekusi oleh Test Z"*.
* **AST Mutator Nodes:** Infection memiliki koleksi *mutator class* (seperti `GreaterThanOrEqualTo`, `PublicVisibility`, `LogicalAnd`, `MethodCallRemoval`). Mutator ini mencegat node AST dan menggantinya. 
  Contoh:
  ```php
  // Node Asli: PhpParser\Node\Expr\BinaryOp\Identical (===)
  if ($status === 'ACTIVE') { ... }

  // Node Mutasi: PhpParser\Node\Expr\BinaryOp\NotIdentical (!==)
  if ($status !== 'ACTIVE') { ... }
  ```
* **Process Isolation:** Mutan disimpan di temporary file atau diinjeksikan via stream wrapper/autoload interceptor. Infection membuat sub-proses PHPUnit terisolasi melalui symfony/process untuk mengevaluasi apakah test suite mendeteksi mutasi tersebut.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Metrik-Metrik Mutasi Kritis
Dalam mutation testing, metrik kuantitatif yang paling esensial adalah:

1. **Mutation Score Indicator (MSI):**
   Persentase mutan yang berhasil ditangani secara efektif oleh test suite.
   $$\text{MSI} = \frac{\text{Killed} + \text{TimedOut} + \text{Error}}{\text{Total Mutants}} \times 100$$
2. **Mutation Code Coverage (Covered MSI):**
   Mengukur efektivitas test suite hanya pada baris kode yang memang ter-cover oleh unit test.
   $$\text{Covered MSI} = \frac{\text{Killed} + \text{TimedOut} + \text{Error}}{\text{Covered Mutants}} \times 100$$
3. **Escaped Mutants:**
   Mutan yang tetap membuat test suite berstatus *green* (exit code `0`). Mengindikasikan celah logika, assertion yang lemah, atau *missing boundary tests*.

### PHPStan Rule Levels & Bleeding Edge
PHPStan beroperasi dari Level 0 hingga Level 9 (atau `max`):
* **Level 0-2:** Pengecekan sintaks dasar, class/method yang tidak eksis, argument count.
* **Level 3-5:** Validasi return types, dead code branches, type-hint validation.
* **Level 6:** Pelaporan missing typehints (termasuk array shapes).
* **Level 7-8:** Validasi union types secara ketat, pencegahan akses property/method pada `nullable` tanpa null-check.
* **Level 9:** Validasi `mixed` type secara radikal; operasi apapun terhadap `mixed` tanpa explicit casting/asserting dianggap *error*.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah demonstrasi celah logika fundamental: sebuah kelas kalkulator diskon yang memiliki **100% Line Coverage**, namun memiliki **MSI 0%** karena ketiadaan asserting boundary conditions.

### 1. File Sumber Aplikasi: `src/DiscountService.php`

```php
<?php

declare(strict_types=1);

namespace App\Engine;

final readonly class DiscountService
{
    /**
     * Menghitung nilai diskon berbasis total belanja.
     * Rule: 
     * - Belanja >= 100_000 mendapatkan diskon 10%
     * - Belanja < 100_000 tidak mendapatkan diskon (0)
     */
    public function calculateDiscount(int $totalAmountInCents): int
    {
        if ($totalAmountInCents >= 100_000) {
            return (int) ($totalAmountInCents * 0.10);
        }

        return 0;
    }
}
```

### 2. File Test yang Lemah (100% Line Coverage, Rapuh): `tests/DiscountServiceTest.php`

```php
<?php

declare(strict_types=1);

namespace App\Tests;

use App\Engine\DiscountService;
use PHPUnit\Framework\TestCase;

final class DiscountServiceTest extends TestCase
{
    public function testCalculateDiscountExecutesAllLines(): void
    {
        $service = new DiscountService();

        // Mengeksekusi branch True (>= 100_000)
        $discountHigh = $service->calculateDiscount(200_000);
        // Assert lemah: hanya memastikan nilainya lebih besar dari 0
        $this->assertGreaterThan(0, $discountHigh);

        // Mengeksekusi branch False (< 100_000)
        $discountLow = $service->calculateDiscount(50_000);
        $this->assertSame(0, $discountLow);
        
        // CATATAN: Seluruh baris (100%) ter-cover, 
        // tapi boundary tepat di 100_000 tidak diuji secara deterministik nilainya!
    }
}
```

### 3. File Konfigurasi: `phpstan.neon`

```neon
parameters:
    level: max
    paths:
        - src
        - tests
    checkGenericClassInNonGenericObjectType: true
    checkMissingIterableValueType: true
```

### 4. File Konfigurasi: `infection.json5`

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
        "html": "infection.html"
    },
    "mutators": {
        "@default": true
    },
    "minMsi": 100,
    "minCoveredMsi": 100
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Kasus Fundamental

1. **`DiscountService.php` (Baris 16):**
   ```php
   if ($totalAmountInCents >= 100_000) {
   ```
   *Infection Mutator:* `GreaterThanOrEqualTo` akan mengubah operator ini menjadi `GreaterThan` (`>`).
   
2. **`DiscountServiceTest.php` (Baris 18):**
   ```php
   $discountHigh = $service->calculateDiscount(200_000);
   $this->assertGreaterThan(0, $discountHigh);
   ```
   *Ketika mutasi terjadi (`$totalAmountInCents > 100_000`):*
   Input `200_000` tetap bernilai `> 100_000`. Hasil kalkulasi adalah `20_000`. Assertion `$this->assertGreaterThan(0, 20000)` **tetap PASS**.
   
3. **Hasil Eksekusi Infection:**
   Mutan `GreaterThanOrEqualTo` pada baris 16 **ESCAPED**.
   *Penyebab:* Pengujian tidak menguji nilai boundary tepat pada titik kritis `100_000`. Jika input `100_000` dimasukkan saat mutasi berjalan:
   * Kode asli: `100_000 >= 100_000` $\to$ `true`, diskon = `10_000`.
   * Kode mutan: `100_000 > 100_000` $\to$ `false`, diskon = `0`.
   Karena test tidak menguji input `100_000`, kecacatan ini tidak terdeteksi oleh unit test meskipun Line Coverage mencapai 100%.

---

## SEKSI 09 — STUDI KASUS NYATA

### Production Scenario: High-Precision Multi-Tier Ledger Fee Engine
Pada platform perbankan digital / Payment Gateway, kalkulasi biaya transaksi (*fee calculation*) memiliki implikasi hukum dan finansial langsung. Kegagalan validasi batas (misalnya transaksi tepat Rp 1.000.000 masuk ke tier tarif yang salah) atau manipulasi pembulatan sen dapat menyebabkan defisit neraca keuangan atau denda audit kepatuhan regulasi.

Kita akan membangun modul domain: `FeeCalculationEngine` yang menangani multi-tier transactional fees, batasan minimum/maksimum fee cap, serta pembebasan fee untuk akun korporat berstatus khusus (*tax-exempt*). 

Kita akan menerapkan:
1. Static analysis ketat via PHPStan Level Max (Custom Value Objects, Generic Collections).
2. Unit Testing yang tahan uji.
3. Infection Mutation Testing untuk menjamin pertahanan batas (*boundary robustness*).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

### Struktur File

```text
src/
├── ValueObject/
│   ├── Money.php
│   └── FeeTier.php
└── Service/
    └── TransactionFeeEngine.php
tests/
└── Service/
    └── TransactionFeeEngineTest.php
phpstan.neon
infection.json5
```

### 1. `src/ValueObject/Money.php`

```php
<?php

declare(strict_types=1);

namespace App\ValueObject;

use InvalidArgumentException;

final readonly class Money
{
    public function __construct(
        public int $amountInCents,
        public string $currency = 'IDR'
    ) {
        if ($this->amountInCents < 0) {
            throw new InvalidArgumentException('Money amount cannot be negative.');
        }

        if ($this->currency !== 'IDR') {
            throw new InvalidArgumentException('Only IDR currency is supported currently.');
        }
    }

    public static function fromCents(int $amount): self
    {
        return new self($amount);
    }

    public function add(self $other): self
    {
        $this->assertSameCurrency($other);
        return new self($this->amountInCents + $other->amountInCents, $this->currency);
    }

    public function subtract(self $other): self
    {
        $this->assertSameCurrency($other);
        $diff = $this->amountInCents - $other->amountInCents;
        
        if ($diff < 0) {
            throw new InvalidArgumentException('Resulting money cannot be negative.');
        }

        return new self($diff, $this->currency);
    }

    public function isGreaterThanOrEqualTo(self $other): bool
    {
        $this->assertSameCurrency($other);
        return $this->amountInCents >= $other->amountInCents;
    }

    public function isGreaterThan(self $other): bool
    {
        $this->assertSameCurrency($other);
        return $this->amountInCents > $other->amountInCents;
    }

    private function assertSameCurrency(self $other): void
    {
        if ($this->currency !== $other->currency) {
            throw new InvalidArgumentException('Currency mismatch operation.');
        }
    }
}
```

### 2. `src/ValueObject/FeeTier.php`

```php
<?php

declare(strict_types=1);

namespace App\ValueObject;

final readonly class FeeTier
{
    /**
     * @param Money $threshold Min amount to reach this tier
     * @param float $percentage Fee percentage (e.g. 0.02 for 2%)
     * @param Money $fixedFee Fixed fee component
     */
    public function __construct(
        public Money $threshold,
        public float $percentage,
        public Money $fixedFee
    ) {
        if ($this->percentage < 0.0 || $this->percentage > 1.0) {
            throw new \InvalidArgumentException('Percentage must be between 0.0 and 1.0.');
        }
    }
}
```

### 3. `src/Service/TransactionFeeEngine.php`

```php
<?php

declare(strict_types=1);

namespace App\Service;

use App\ValueObject\FeeTier;
use App\ValueObject\Money;

final readonly class TransactionFeeEngine
{
    /**
     * @param array<int, FeeTier> $tiers
     */
    public function __construct(
        private array $tiers,
        private Money $minFeeCap,
        private Money $maxFeeCap
    ) {
        if ($this->minFeeCap->isGreaterThan($this->maxFeeCap)) {
            throw new \InvalidArgumentException('Min fee cap cannot exceed Max fee cap.');
        }
    }

    /**
     * Menghitung total fee berdasarkan tiering volume transaksi.
     */
    public function calculateFee(Money $transactionAmount, bool $isFeeExempt): Money
    {
        if ($isFeeExempt) {
            return Money::fromCents(0);
        }

        if ($transactionAmount->amountInCents === 0) {
            return Money::fromCents(0);
        }

        $appliedTier = null;

        // Tiers diasumsikan terurut menurun berdasarkan threshold
        foreach ($this->tiers as $tier) {
            if ($transactionAmount->isGreaterThanOrEqualTo($tier->threshold)) {
                $appliedTier = $tier;
                break;
            }
        }

        if ($appliedTier === null) {
            return $this->minFeeCap;
        }

        $variableFee = (int) \round($transactionAmount->amountInCents * $appliedTier->percentage);
        $totalCalculated = Money::fromCents($variableFee)->add($appliedTier->fixedFee);

        if ($this->minFeeCap->isGreaterThan($totalCalculated)) {
            return $this->minFeeCap;
        }

        if ($totalCalculated->isGreaterThan($this->maxFeeCap)) {
            return $this->maxFeeCap;
        }

        return $totalCalculated;
    }
}
```

### 4. `tests/Service/TransactionFeeEngineTest.php`

Test suite ini dirancang secara matematis untuk **membunuh setiap mutan** yang mungkin dibuat oleh Infection pada operator aritmatika, perbandingan logika, boundary value, dan rounding.

```php
<?php

declare(strict_types=1);

namespace App\Tests\Service;

use App\Service\TransactionFeeEngine;
use App\ValueObject\FeeTier;
use App\ValueObject\Money;
use InvalidArgumentException;
use PHPUnit\Framework\TestCase;

final class TransactionFeeEngineTest extends TestCase
{
    private TransactionFeeEngine $engine;
    private Money $minCap;
    private Money $maxCap;

    protected function setUp(): void
    {
        parent::setUp();

        $this->minCap = Money::fromCents(2_500);   // Min Rp 25.00
        $this->maxCap = Money::fromCents(50_000);  // Max Rp 500.00

        // Definisi Tiers (Harus terurut dari threshold terbesar)
        $tiers = [
            new FeeTier(Money::fromCents(1_000_000), 0.01, Money::fromCents(1_000)), // Tier 1: >= 1jt -> 1% + 10
            new FeeTier(Money::fromCents(100_000), 0.02, Money::fromCents(500)),     // Tier 2: >= 100k -> 2% + 5
        ];

        $this->engine = new TransactionFeeEngine($tiers, $this->minCap, $this->maxCap);
    }

    public function testConstructorRejectsInvalidCaps(): void
    {
        $this->expectException(InvalidArgumentException::class);
        $this->expectExceptionMessage('Min fee cap cannot exceed Max fee cap.');

        new TransactionFeeEngine(
            [],
            Money::fromCents(50_000),
            Money::fromCents(10_000) // Invalid: Min > Max
        );
    }

    public function testExemptTransactionYieldsZeroFee(): void
    {
        $result = $this->engine->calculateFee(Money::fromCents(5_000_000), true);
        $this->assertSame(0, $result->amountInCents);
    }

    public function testZeroAmountTransactionYieldsZeroFee(): void
    {
        $result = $this->engine->calculateFee(Money::fromCents(0), false);
        $this->assertSame(0, $result->amountInCents);
    }

    public function testAmountBelowAllTiersHitsMinFeeCap(): void
    {
        // 50_000 cents is below lowest tier threshold (100_000)
        $result = $this->engine->calculateFee(Money::fromCents(50_000), false);
        $this->assertSame($this->minCap->amountInCents, $result->amountInCents);
    }

    public function testExactLowerBoundaryOfLowestTier(): void
    {
        // Boundary testing at exact 100_000 cents (Tier 2)
        // Expected: (100_000 * 0.02) + 500 = 2000 + 500 = 2500 cents (Matches Min Cap exact)
        $result = $this->engine->calculateFee(Money::fromCents(100_000), false);
        $this->assertSame(2_500, $result->amountInCents);
    }

    public function testValueJustBelowLowestTierBoundary(): void
    {
        // 99_999 cents -> Below 100_000 -> Fallback to MinCap (2500)
        $result = $this->engine->calculateFee(Money::fromCents(99_999), false);
        $this->assertSame(2_500, $result->amountInCents);
    }

    public function testExactUpperTierBoundary(): void
    {
        // Boundary testing at exact 1_000_000 cents (Tier 1)
        // Expected: (1_000_000 * 0.01) + 1000 = 10_000 + 1000 = 11_000 cents
        $result = $this->engine->calculateFee(Money::fromCents(1_000_000), false);
        $this->assertSame(11_000, $result->amountInCents);
    }

    public function testValueJustBelowUpperTierBoundary(): void
    {
        // 999_999 cents -> Falls into Tier 2 (0.02 + 500)
        // (999_999 * 0.02) = 19999.98 -> round to 20000 + 500 = 20_500 cents
        $result = $this->engine->calculateFee(Money::fromCents(999_999), false);
        $this->assertSame(20_500, $result->amountInCents);
    }

    public function testCalculatedFeeHittingMaxCap(): void
    {
        // 10_000_000 cents (Tier 1) -> (10_000_000 * 0.01) + 1000 = 101_000 cents
        // Max Cap is 50_000 cents -> Result must be capped at 50_000
        $result = $this->engine->calculateFee(Money::fromCents(10_000_000), false);
        $this->assertSame($this->maxCap->amountInCents, $result->amountInCents);
    }

    public function testCalculatedFeeHittingMinCapWhenFeeIsLower(): void
    {
        // Custom engine with high minCap to trigger MinCap branch
        $highMinCap = Money::fromCents(15_000);
        $engine = new TransactionFeeEngine(
            [new FeeTier(Money::fromCents(100_000), 0.01, Money::fromCents(0))],
            $highMinCap,
            Money::fromCents(100_000)
        );

        // 200_000 * 0.01 = 2000 cents. Since 2000 < 15000, must return minCap
        $result = $engine->calculateFee(Money::fromCents(200_000), false);
        $this->assertSame(15_000, $result->amountInCents);
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Dimensi Evaluasi | PHPStan (Static Analysis) | PHPUnit (Dynamic Unit Test) | Infection (Mutation Testing) | Rector (Automated Refactoring) |
| :--- | :--- | :--- | :--- | :--- |
| **Fase Eksekusi** | Compile/Pre-test phase | Runtime execution | Post-Unit Test (Dynamic Metatest) | Pre-commit/Ad-hoc AST rewrite |
| **Kebutuhan Resource** | Rendah (CPU & Memory ringan) | Menengah (Tergantung I/O mock) | Sangat Tinggi (CPU intensive fork) | Menengah |
| **Waktu Eksekusi** | Detik (~2 - 10 detik) | Detik (~5 - 30 detik) | Menit (~2 - 20 menit) | Detik |
| **Deteksi False-Positive**| Sedang (Bisa ditekan via baseline)| Nol (Jika test deterministik) | Rendah (Kecuali Equivalent Mutants)| Sangat Rendah |
| **Cakupan Deteksi** | Validasi Tipe, Missing Call, AST | Fungsionalitas spesifik, Jalur I/O | Kerapuhan assertion, Boundary bugs | Pattern obsolescence, Engine rules |
| **ROI Finansial** | Sangat Tinggi (Mencegah Typo/TypeError) | Tinggi (Fondasi CI/CD) | Ekstrem untuk Core Domain Engine | Tinggi untuk migrasi versi PHP |

### Equivalent Mutants (Trade-Off Utama Infection)
Tantangan terbesar Mutation Testing adalah **Equivalent Mutants**: Mutan yang mengubah sintaks kode sumber, namun secara semantik menghasilkan perilaku runtime yang identik dengan aslinya.
Contoh:
```php
// Original
for ($i = 0; $i < 10; $i++) { ... }

// Mutated
for ($i = 0; $i != 10; $i++) { ... }
```
Kedua loop di atas menghasilkan eksekusi yang persis sama. Infection tidak akan pernah bisa membunuh mutan ini via test, sehingga MSI tidak bisa mencapai absolut 100% pada sistem legacy besar tanpa konfigurasi `ignoreMutators` spesifik.

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Floating-Point Precision Trap dalam Mutasi
Operator aritmatika floating point pada PHP rentan terhadap pembulatan binary IEEE 754:
```php
// JANGAN LAKUKAN:
$fee = $amount * 0.1; // Infection akan memutasi 0.1 menjadi 1.1 atau 0.0
```
*Solusi:* Selalu konversi nilai finansial ke representasi bilangan bulat terkecil (cents, satoshi, wei) menggunakan tipe data `int`, atau gunakan ekstensi `ext-bcmath` untuk arbitary precision.

### 2. Infinite Loop Mutants & Process Timeout
Mutator seperti `IncrementInteger` atau `While_` dapat secara tidak sengaja menghasilkan loop tak terbatas (*infinite loop*).
*Mitigasi:* Infection secara default membatasi runtime worker menggunakan timeout multiplier (`timeout: 10` detik atau `1.5x` dari baseline test time). Pastikan konfigurasi CI Anda tidak mematikan flag timeout ini.

### 3. Static Analysis vs Dynamic Property Injection
Pada framework seperti Laravel atau sistem lama yang menggunakan `__get()` dynamic property access, PHPStan level max akan melaporkan ratusan error palsu (*false positives*).
*Mitigasi:* Wajib menggunakan extension resmi seperti `larastan/larastan` atau mendefinisikan `@property` phpdoc tags secara eksplisit pada class definition.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Anti-Pattern 1: Assertion-Free Testing (Coverage Chasing)
Pengembang mengejar metrik coverage 100% dengan mengeksekusi method tanpa assertions yang berarti.
```php
// BURUK: Menghasilkan 100% coverage, 0% perlindungan logika
public function testProcessOrder(): void
{
    $processor = new OrderProcessor();
    $processor->process(new Order());
    $this->assertTrue(true); // FAKE ASSERTION!
}
```
*Solusi:* Aktifkan proteksi PHPUnit pada `phpunit.xml`:
```xml
<phpunit beStrictAboutTestsThatDoNotTestAnything="true"
         beStrictAboutOutputDuringTests="true">
```

### Anti-Pattern 2: Baseline Abuse pada Static Analysis
Menggunakan `phpstan-baseline.neon` sebagai "tempat sampah" untuk menyembunyikan technical debt secara permanen tanpa target resolusi.
*Solusi:* Kunci file baseline pada Git. Setiap PR yang menambah jumlah baris pada baseline harus di-*reject* secara otomatis di CI pipeline.

### Anti-Pattern 3: Penyalahgunaan `@phpstan-ignore`
Menghilangkan pesan error dengan directive `@phpstan-ignore-next-line` tanpa dokumentasi alasan matematis mengapa safe-typing tersebut valid.
*Solusi:* Gunakan custom type assertion helper atau runtime type checking via `webmozart/assert` / `assert()` bawaan PHP daripada mematikan analyzer.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Strict Type Safety Wajib:** Letakkan `declare(strict_types=1);` di baris paling pertama seluruh file tanpa pengecualian.
2. **Fail-Fast CI Pipeline:** Urutkan job pipeline CI dari yang paling cepat dan murah ke yang paling berat:
   ```text
   Linting (PHP-CS-Fixer) -> Static Analysis (PHPStan) -> Unit Tests (PHPUnit) -> Mutation Testing (Infection)
   ```
3. **Targeted Mutation Testing (Git Diff Filters):** Jangan jalankan Infection pada seluruh codebase monorepo di setiap *Pull Request*. Jalankan hanya pada file-file yang berubah menggunakan parameter:
   ```bash
   vendor/bin/infection --git-diff-filter=AM --git-diff-base=origin/main
   ```
4. **Immutability First:** Gunakan fitur `final readonly class` pada Domain Entities dan Value Objects untuk mencegah *state-mutation side effects* yang tidak terdeteksi oleh static analyzer.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

Mutation testing terkenal lambat secara komputasi karena mengeksekusi test suite ratusan hingga ribuan kali. Terapkan strategi optimasi berikut:

### 1. Gunakan Driver Coverage Cepat: PCOV
Hindari penggunaan Xdebug untuk pengumpulan coverage di CI/CD. Gunakan **PCOV**.
* Benchmark: PCOV biasanya **5x - 10x lebih cepat** dibandingkan Xdebug dalam menghasilkan coverage metadata.

```bash
# Instalasi & aktivasi PCOV
pecl install pcov
php -d pcov.enabled=1 vendor/bin/phpunit --coverage-xml=var/coverage/coverage-xml --log-junit=var/coverage/junit.xml
```

### 2. Multiprocessing & Threading
Tentukan alokasi core CPU secara optimal saat menjalankan Infection:
```bash
vendor/bin/infection --threads=$(nproc) --skip-initial-tests --coverage=var/coverage
```
* `--skip-initial-tests`: Menggunakan artefak coverage XML yang sudah dieksekusi oleh step PHPUnit sebelumnya, memangkas double-execution test suite awal.

### 3. Tmpfs Execution
Jalankan temporary build directories Infection di dalam RAM disk (`tmpfs`) untuk memangkas latency disk I/O akibat penulisan mutan secara terus-menerus.

---

## SEKSI 16 — KEAMANAN & HARDENING

Penerapan static analysis dan mutation testing memiliki korelasi langsung dengan ketahanan keamanan (*security posture*):

### 1. Taint Analysis & Static Security Scanning
PHPStan dapat diperluas untuk mendeteksi celah keamanan Injection (SQLi, XSS, Path Traversal) sebelum runtime menggunakan library analisis aliran data tainted.
Tambahkan `phpstan/phpstan-strict-rules` dan rules keamanan:
```neon
includes:
    - vendor/phpstan/phpstan-strict-rules/rules.neon
```

### 2. Pencegahan Broken Access Control melalui Mutasi Logika
Celah keamanan kritis sering terjadi akibat pertukaran logika autorisasi:
```php
// Kode Asli
if ($currentUser->id === $document->ownerId || $currentUser->hasRole('ADMIN'))

// Mutasi yang lolos jika test tidak lengkap:
if ($currentUser->id !== $document->ownerId || $currentUser->hasRole('ADMIN'))
```
Mutation testing secara sistematis mengubah `===` menjadi `!==`, dan `||` menjadi `&&`. Jika mutasi ini lolos (*Escaped*), aplikasi Anda berpotensi memiliki celah keamanan **IDOR (Insecure Direct Object References)** di production.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### Menganalisis File Log Infection (`infection.log`)
Ketika mutan berstatus `Escaped`, buka log untuk melihat exact diff dari mutasi yang gagal ditangkap test Anda:

```text
Escaped mutants:
================
1) /home/app/src/Service/TransactionFeeEngine.php:48    [M] GreaterThanOrEqualTo

--- Original
+++ New
@@ @@
-        if ($transactionAmount->isGreaterThanOrEqualTo($tier->threshold)) {
+        if ($transactionAmount->isGreaterThan($tier->threshold)) {
             $appliedTier = $tier;
             break;
         }
```

### Debugging Langkah Demi Langkah:
1. **Identifikasi File & Baris:** Buka file sumber pada baris yang tertera (contoh: baris 48).
2. **Analisis Mutator yang Digunakan:** Mutator di atas adalah `GreaterThanOrEqualTo` yang diubah menjadi `GreaterThan`.
3. **Cari Skenario Boundary yang Hilang:** Kode mutan berarti: jika `$transactionAmount == $tier->threshold`, kondisi menjadi `false`.
4. **Buat Unit Test Reproduksi:** Tambahkan assertion spesifik pada test file yang menyuplai `$transactionAmount` bernilai persis sama dengan `$tier->threshold`.
5. **Re-run Infection:** Pastikan mutan tersebut kini berstatus `[K] Killed`.

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### Perintah Esensial Terminal

```bash
# 1. Menjalankan PHPStan dengan memory limit tak terbatas
vendor/bin/phpstan analyse -c phpstan.neon --memory-limit=-1

# 2. Menghasilkan PHPStan Baseline (Untuk legacy codebase)
vendor/bin/phpstan analyse -c phpstan.neon --generate-baseline

# 3. Menghasilkan Code Coverage XML via PHPUnit & PCOV
php -d pcov.enabled=1 vendor/bin/phpunit --coverage-xml=build/coverage-xml --log-junit=build/junit.xml

# 4. Eksekusi Infection berbasis Coverage yang sudah ada
vendor/bin/infection --threads=4 --coverage=build --skip-initial-tests

# 5. Eksekusi Infection HANYA pada file yang diubah di Git branch (Fast PR Check)
vendor/bin/infection --threads=4 --git-diff-filter=AM --git-diff-base=origin/main --min-msi=80
```

### Quick Reference Mutator Infection

* `LogicalAnd` / `LogicalOr`: Mengubah `&&` $\leftrightarrow$ `||`
* `GreaterThanOrEqualTo` / `GreaterThan`: Mengubah `>=` $\leftrightarrow$ `>`
* `TrueValue` / `FalseValue`: Mengubah `true` $\leftrightarrow$ `false`
* `MethodCallRemoval`: Menghapus baris pemanggilan method void (mengecek apakah pemanggilan fungsi benar-benar memiliki dampak sampingan yang diassert).
* `PublicVisibility`: Mengubah method `public` menjadi `protected` (memvalidasi API surface).

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Pilihan Ganda (Tingkat Dasar)

#### Q1. Apa arti utama dari status "Mutant Escaped" pada Infection?
* A. Kode aplikasi memiliki bug sintaksis yang mencegah PHP berjalan.
* B. Suite pengujian (unit tests) tetap berstatus PASS meskipun ada perubahan logika pada kode aplikasi.
* C. Infection gagal membaca file Abstract Syntax Tree dari PHP-Parser.
* D. PHPUnit mengalami timeout saat mengeksekusi infinite loop.

#### Q2. Pada PHPStan Level 9, bagaimana perlakuan engine terhadap tipe `mixed`?
* A. `mixed` diabaikan sepenuhnya untuk backward compatibility.
* B. Operasi eksplisit pada tipe `mixed` tanpa type-narrowing dianggap sebagai error.
* C. PHPStan secara otomatis mengonversi `mixed` menjadi `stdClass`.
* D. `mixed` hanya diizinkan pada argumen fungsi, dilarang pada return type.

#### Q3. Mengapa metrik 100% Line Coverage tidak menjamin tidak adanya bug batas (boundary bugs)?
* A. Karena line coverage tidak menghitung execution time.
* B. Karena satu baris kode dapat dieksekusi tanpa assertion terhadap output atau tanpa menguji tepi operator logika (misal: `>=`).
* C. Karena line coverage hanya berlaku untuk functional tests, bukan unit tests.
* D. Karena PHPUnit tidak mendukung multi-threading coverage.

#### Q4. Driver pengumpul coverage mana yang paling direkomendasikan untuk pipeline CI performa tinggi?
* A. Xdebug 2
* B. Xdebug 3
* C. PCOV
* D. Blackfire Profiler

#### Q5. Apa kegunaan utama dari parameter `--git-diff-filter=AM` pada Infection?
* A. Menghapus file git commit yang tidak memiliki unit test.
* B. Membatasi mutation testing hanya pada file baru (*Added*) dan file termodifikasi (*Modified*) di Git.
* C. Memaksa git merge sebelum pengujian dijalankan.
* D. Mengabaikan file PHP yang memiliki ekstensi `.am`.

---

### Soal Kasus Logika (Tingkat Menengah)

#### Q6. Diberikan kode berikut:
```php
public function isAdult(int $age): bool {
    return $age >= 18;
}
```
Suite pengujian hanya memanggil `$this->assertTrue($service->isAdult(25));` dan `$this->assertFalse($service->isAdult(15));`.
Mutator `GreaterThanOrEqualToNegotiation` mengubah `>=` menjadi `>`. Apakah mutan akan Escaped atau Killed? Jelaskan!

#### Q7. Mengapa static analysis (PHPStan) harus dijalankan SEBELUM unit test dan mutation test di CI pipeline?
Jelaskan secara struktural dari aspek efisiensi biaya komputasi dan determinisme build!

#### Q8. Jelaskan bahaya dari "Equivalent Mutants" terhadap skor MSI tim engineering dan sebutkan satu contoh konkret kode yang menghasilkannya!

#### Q9. Diberikan potongan kode:
```php
/** @param array<string, mixed> $payload */
public function parseUser(array $payload): string {
    return $payload['name'];
}
```
Mengapa kode di atas memicu error pada PHPStan Level Max/9, dan bagaimana refactor yang benar tanpa mematikan type-checking?

#### Q10. Sebuah test suite memiliki 100 mutants: 75 Killed, 5 Escaped, 10 Uncovered, 5 Timed Out, 5 Error. Berapakah nilai Mutation Score Indicator (MSI)?

---

### Kunci Jawaban & Pembahasan

* **Q1:** **B**. Escaped berarti mutasi kode disuntikkan, tetapi test runner tidak mendeteksi kegagalan (tetap hijau), membuktikan suite test lemah.
* **Q2:** **B**. Level 9 memberlakukan penanganan ketat terhadap `mixed`; Anda wajib mempersempit tipe (`is_string()`, `instanceof`, dll.) sebelum menggunakannya.
* **Q3:** **B**. Line coverage mencatat baris tersentuh, bukan kebenaran kondisi semantik atau kelengkapan assertion.
* **Q4:** **C**. PCOV dirancang khusus untuk coverage deterministik berkecepatan tinggi tanpa overhead debugging seperti Xdebug.
* **Q5:** **B**. Optimasi untuk PR review agar mutation test selesai dalam hitungan detik/menit dengan hanya menguji delta perubahan.
* **Q6:** **Mutan akan ESCAPED**. Karena input `25` tetap bernilai `true` baik pada `25 >= 18` maupun `25 > 18`, dan input `15` tetap `false` pada keduanya. Nilai batas kritis `18` tidak pernah diuji!
* **Q7:** **Efisiensi Fail-Fast**: PHPStan menganalisis AST murni in-memory tanpa bootstrapping framework, DB mocking, atau spawning processes. Waktu eksekusi PHPStan (detik) jauh lebih cepat daripada unit testing atau mutation testing (menit). Menangkap error sintaks/tipe di awal menghemat resource runner CI secara masif.
* **Q8:** Equivalent Mutants mendistorsi metrik MSI sehingga target 100% tidak realistis tercapai tanpa wasting effort. Contoh:
  ```php
  // Original
  $count = count($items);
  if ($count === 0) { return null; }
  // Mutated
  if ($count < 0) { return null; } // count() tidak pernah negatif, tapi jika test hanya mengecek non-empty, mutan bisa lolos.
  ```
  Atau perulangan `for ($i = 0; $i < 5; ++$i)` vs `for ($i = 0; $i != 5; ++$i)`.
* **Q9:** PHPStan Level 9 melarang implicit return dari array bernilai `mixed` ke return type `string`. Refactor:
  ```php
  /** @param array{name: string} $payload */ // Array shape
  // ATAU:
  if (!isset($payload['name']) || !\is_string($payload['name'])) {
      throw new \InvalidArgumentException('Invalid name');
  }
  return $payload['name'];
  ```
* **Q10:** Rumus: $\frac{\text{Killed} + \text{TimedOut} + \text{Error}}{\text{Total}} \times 100 = \frac{75 + 5 + 5}{100} \times 100 = \mathbf{85\%}$.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Project: High-Security Escrow Balance Lock Engine

#### Deskripsi
Anda diminta merancang sistem manajemen escrow akun finansial. Sistem ini bertugas mengunci saldo (*hold balance*), merilis saldo (*release hold*), dan mengeksekusi penalti (*slash penalty*). Kegagalan pada sistem ini dapat mengakibatkan double-spending atau insolvency pada balance pengguna.

#### Spesifikasi Domain
1. Class `EscrowAccount`:
   * Field `availableBalance` (Money), `heldBalance` (Money).
   * Method `hold(Money $amount): void`:
     * Syarat: `$amount` harus $> 0$.
     * Syarat: `$amount` harus $\le$ `availableBalance`.
     * Efek: `availableBalance` berkurang, `heldBalance` bertambah.
   * Method `release(Money $amount): void`:
     * Syarat: `$amount` harus $> 0$.
     * Syarat: `$amount` harus $\le$ `heldBalance`.
     * Efek: `heldBalance` berkurang, `availableBalance` bertambah.
   * Method `slash(Money $amount, float $burnPercentage): array{burned: Money, fee: Money}`:
     * Menghitung persentase saldo held yang dimusnahkan (`burned`) dan sisa potongan dialihkan ke `fee`.
     * Pembulatan wajib menggunakan algoritma deterministik `PHP_ROUND_HALF_UP`.

#### Kriteria Kelulusan (Definition of Done)
1. **PHPStan Compliance:** Dijalankan dengan level `max` tanpa file baseline dan tanpa flag ignore:
   ```bash
   vendor/bin/phpstan analyse src tests --level=max
   # Result: [OK] No errors
   ```
2. **Dynamic Testing:** Seluruh skenario happy-path dan edge-cases (zero amount, negative amount, insufficient balance, overflow boundary) diuji via PHPUnit.
3. **Mutation Testing Rigor:** Infection dijalankan pada domain service tersebut dengan target mutlak:
   * **Mutation Score Indicator (MSI) = 100%**
   * **Covered Code MSI = 100%**
   * **0 Escaped Mutants**
4. Pipeline script otomatisasi disimpan dalam file executable `./run-verification.sh`.