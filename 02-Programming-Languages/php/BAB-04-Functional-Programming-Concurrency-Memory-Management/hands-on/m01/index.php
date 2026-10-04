<?php

declare(strict_types=1);

namespace Production\Engine;

use Fiber;
use SplQueue;
use Throwable;
use DateTimeImmutable;

// ============================================================================
// 1. DOMAIN MODELS (STRICT IMMUTABILITY)
// ============================================================================

readonly class IngestionPayload
{
    public function __construct(
        public string $eventId,
        public string $accountNumber,
        public float $amount,
        public string $signature,
        public DateTimeImmutable $timestamp
    ) {}
}

readonly class ProcessingResult
{
    public function __construct(
        public string $eventId,
        public bool $isSuccess,
        public float $settledAmount,
        public ?string $errorMessage = null
    ) {}
}

// ============================================================================
// 2. FUNCTIONAL CORE PIPELINE (PURE FUNCTIONS)
// ============================================================================

final class PipelineCore
{
    public static function verifySignature(string $secretKey): \Closure
    {
        return static function (IngestionPayload $payload) use ($secretKey): IngestionPayload {
            $expectedSignature = hash_hmac(
                'sha256',
                "{$payload->eventId}:{$payload->accountNumber}:{$payload->amount}",
                $secretKey
            );

            if (!hash_equals($expectedSignature, $payload->signature)) {
                throw new \SecurityException("Compromised payload signature for event: {$payload->eventId}");
            }

            return $payload;
        };
    }

    public static function calculateTax(float $taxRate): \Closure
    {
        return static function (IngestionPayload $payload) use ($taxRate): IngestionPayload {
            $deducted = $payload->amount - ($payload->amount * $taxRate);
            return new IngestionPayload(
                $payload->eventId,
                $payload->accountNumber,
                $deducted,
                $payload->signature,
                $payload->timestamp
            );
        };
    }

    public static function compose(callable ...$stages): \Closure
    {
        return static fn(mixed $input): mixed => array_reduce(
            $stages,
            static fn(mixed $carry, callable $stage): mixed => $stage($carry),
            $input
        );
    }
}

// ============================================================================
// 3. FIBER-BASED CONCURRENT WORKER RUNTIME
// ============================================================================

final class NonBlockingWorkerEngine
{
    /** @var SplQueue<Fiber> */
    private SplQueue $readyQueue;
    private int $processedCounter = 0;
    private const GC_COLLECTION_THRESHOLD = 500; // Trigger cycle collect every 500 tasks

    public function __construct(
        private readonly \Closure $transformationPipeline
    ) {
        $this->readyQueue = new SplQueue();
        
        // Optimasi Zend Engine GC: Matikan auto-run agresif di loop kritis
        gc_enable();
    }

    public function dispatch(IngestionPayload $payload): void
    {
        $fiber = new Fiber(function () use ($payload): void {
            try {
                // I/O Stage: Pre-validation simulated network call
                $this->nonBlockingSleep(5); // Simulated 5ms async I/O

                // Pure Functional Transformation Pipeline Execution
                /** @var IngestionPayload $processed */
                $processed = ($this->transformationPipeline)($payload);

                // I/O Stage: Database write simulation
                $this->nonBlockingSleep(10); // Simulated 10ms async database flush

                $result = new ProcessingResult($processed->eventId, true, $processed->amount);
                $this->handleSuccess($result);

            } catch (Throwable $e) {
                $result = new ProcessingResult($payload->eventId, false, 0.0, $e->getMessage());
                $this->handleFailure($result);
            }
        });

        $this->readyQueue->enqueue($fiber);
    }

    /**
     * Primitive Non-blocking Cooperative Delay
     */
    private function nonBlockingSleep(int $virtualMilliseconds): void
    {
        // Fiber menyerahkan eksekusi kembali ke scheduler loop utama
        $iterations = (int)ceil($virtualMilliseconds / 2);
        for ($i = 0; $i < $iterations; $i++) {
            Fiber::suspend();
        }
    }

    private function handleSuccess(ProcessingResult $res): void
    {
        echo "[SUCCESS] Event: {$res->eventId} | Settled: \${$res->settledAmount}\n";
    }

    private function handleFailure(ProcessingResult $res): void
    {
        echo "[FAILED]  Event: {$res->eventId} | Error: {$res->errorMessage}\n";
    }

    /**
     * Event Loop Execution Engine dengan Interleaved Memory Management
     */
    public function runLoop(): void
    {
        echo "[Engine] Event Loop running. Initial Memory: " . $this->getMemoryUsage() . "\n";

        while (!$this->readyQueue->isEmpty()) {
            $fiber = $this->readyQueue->dequeue();

            try {
                if (!$fiber->isStarted()) {
                    $fiber->start();
                } elseif ($fiber->isSuspended()) {
                    $fiber->resume();
                }

                if ($fiber->isSuspended()) {
                    $this->readyQueue->enqueue($fiber);
                } else {
                    // Task Lifecycle Berakhir
                    $this->processedCounter++;
                    $this->enforceMemoryBoundary();
                }
            } catch (Throwable $critical) {
                echo "[FATAL ENGINE ERROR] " . $critical->getMessage() . "\n";
            }
        }

        echo "[Engine] All tasks terminated. Final Memory: " . $this->getMemoryUsage() . "\n";
    }

    /**
     * ZMM Garbage Collection Boundary Management
     */
    private function enforceMemoryBoundary(): void
    {
        if ($this->processedCounter % self::GC_COLLECTION_THRESHOLD === 0) {
            // Evaluasi eksplisit graph cycle Zend Engine
            $collectedCycles = gc_collect_cycles();
            
            // Bersihkan Zend memory manager cache pools untuk mengembalikan memori OS
            gc_mem_caches();

            echo "--- [ZMM GC CYCLE TRIGGERED] Processed: {$this->processedCounter} | Cycles Cleared: {$collectedCycles} | Current Heap: " . $this->getMemoryUsage() . " ---\n";
        }
    }

    private function getMemoryUsage(): string
    {
        $bytes = memory_get_usage(true); // Real allocated memory from OS
        return sprintf('%.2f MB', $bytes / 1024 / 1024);
    }
}

// ============================================================================
// 4. BOOTSTRAPPER & EXECUTION SIMULATION
// ============================================================================

final class SecurityException extends \RuntimeException {}

$secretKey = "c8f93a1d94b0d87";

// Build Immutable Processing Pipeline
$pipeline = PipelineCore::compose(
    PipelineCore::verifySignature($secretKey),
    PipelineCore::calculateTax(0.12) // 12% Value Added Tax
);

$worker = new NonBlockingWorkerEngine($pipeline);

// Generate 1,500 payload batch untuk mensimulasikan heavy ingestion
for ($i = 1; $i <= 1500; $i++) {
    $evtId = "EVT-" . str_pad((string)$i, 6, "0", STR_PAD_LEFT);
    $amount = 100.0 * $i;
    
    // Generate valid HMAC signature
    $sig = hash_hmac('sha256', "{$evtId}:ACC-99:{$amount}", $secretKey);

    // Injeksikan satu data corrupt secara periodik untuk simulasi kegagalan murni
    if ($i % 300 === 0) {
        $sig = "invalid_signature_hash";
    }

    $payload = new IngestionPayload(
        $evtId,
        "ACC-99",
        $amount,
        $sig,
        new DateTimeImmutable()
    );

    $worker->dispatch($payload);
}

// Eksekusi Non-blocking Event Loop
$worker->runLoop();
