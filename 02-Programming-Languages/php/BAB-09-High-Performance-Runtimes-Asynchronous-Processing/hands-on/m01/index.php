<?php

declare(strict_types=1);

use Nyholm\Psr7\Response;
use Nyholm\Psr7\Factory\Psr17Factory;
use Spiral\RoadRunner\Worker;
use Spiral\RoadRunner\Http\PSR7Worker;

require_once __DIR__ . '/vendor/autoload.php';

/**
 * ContextContainer: Mengisolasi dependensi dan state yang hanya berlaku per satu request.
 * Mencegah kebocoran data antar transaksi (State Contamination).
 */
final class RequestContext
{
    private static ?self $current = null;

    public function __construct(
        public readonly string $traceId,
        public readonly float $startTime
    ) {}

    public static function setCurrent(?self $context): void
    {
        self::$current = $context;
    }

    public static function get(): self
    {
        if (self::$current === null) {
            throw new \RuntimeException("Tidak ada active execution context.");
        }
        return self::$current;
    }
}

/**
 * Service pemrosesan webhook (Stateless Singleton)
 */
final readonly class WebhookProcessor
{
    public function __construct(
        private string $secretKey
    ) {}

    public function process(string $signature, string $payload): bool
    {
        // CPU-bound Signature Verification
        $computed = hash_hmac('sha256', $payload, $this->secretKey);
        
        if (!hash_equals($computed, $signature)) {
            return false;
        }

        // Simulasi non-blocking publish ke internal broker / database storage
        // Pada production nyata, gunakan asynchronous client driver
        return true;
    }
}

// === BOOTSTRAP FASE (Hanya berjalan SATU KALI saat worker di-spawn) ===
$psr17Factory = new Psr17Factory();
$worker = Worker::create();
$psr7Worker = new PSR7Worker($worker, $psr17Factory, $psr17Factory, $psr17Factory);

$processor = new WebhookProcessor(getenv('WEBHOOK_SECRET') ?: 'default-secret-key');

// === EVENT LOOP REQUEST WORKER ===
while (true) {
    try {
        $request = $psr7Worker->waitRequest();
        
        if ($request === null) {
            // Worker diberhentikan oleh master supervisor RoadRunner (Graceful Shutdown)
            break;
        }
    } catch (\Throwable $e) {
        $psr7Worker->respond(new Response(400, [], 'Bad Request Protocol'));
        continue;
    }

    // Inisialisasi Context Baru untuk Request Ini
    $traceId = $request->getHeaderLine('X-Trace-ID') ?: bin2hex(random_bytes(16));
    RequestContext::setCurrent(new RequestContext($traceId, microtime(true)));

    try {
        $signature = $request->getHeaderLine('X-Signature-SHA256');
        $body = (string)$request->getBody();

        if (empty($signature) || empty($body)) {
            $response = new Response(400, ['Content-Type' => 'application/json'], json_encode([
                'error' => 'Missing signature or payload',
                'trace_id' => $traceId
            ], JSON_THROW_ON_ERROR));
            
            $psr7Worker->respond($response);
            continue;
        }

        $isValid = $processor->process($signature, $body);

        if (!$isValid) {
            $response = new Response(401, ['Content-Type' => 'application/json'], json_encode([
                'error' => 'Invalid HMAC signature',
                'trace_id' => $traceId
            ], JSON_THROW_ON_ERROR));
            
            $psr7Worker->respond($response);
            continue;
        }

        // Berhasil memproses webhook
        $response = new Response(200, ['Content-Type' => 'application/json'], json_encode([
            'status' => 'acknowledged',
            'trace_id' => $traceId
        ], JSON_THROW_ON_ERROR));

        $psr7Worker->respond($response);

    } catch (\Throwable $e) {
        // Tangkap fatal exception tanpa membunuh worker process
        $errorPayload = json_encode([
            'error' => 'Internal Processing Error',
            'trace_id' => $traceId
        ], JSON_THROW_ON_ERROR);

        $psr7Worker->respond(new Response(500, ['Content-Type' => 'application/json'], $errorPayload));
    } finally {
        // === CRITICAL CLEANUP: Wajib membersihkan context state ===
        RequestContext::setCurrent(null);

        // Jika terdeteksi akumulasi memori mendekati ambang batas tertentu, paksa restart
        if (memory_get_usage(true) > 64 * 1024 * 1024) { // 64MB Threshold
            $worker->stop();
            break;
        }
    }
}
