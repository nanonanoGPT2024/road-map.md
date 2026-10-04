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
