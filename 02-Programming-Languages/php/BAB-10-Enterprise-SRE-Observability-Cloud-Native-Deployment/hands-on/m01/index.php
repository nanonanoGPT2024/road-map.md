<?php
declare(strict_types=1);

namespace Enterprise\Telemetry;

use OpenTelemetry\API\Common\Time\SystemClock;
use OpenTelemetry\API\Trace\Propagation\TraceContextPropagator;
use OpenTelemetry\API\Trace\SpanKind;
use OpenTelemetry\API\Trace\StatusCode;
use OpenTelemetry\API\Trace\TracerInterface;
use OpenTelemetry\Context\Context;
use OpenTelemetry\Context\Propagation\ArrayAccessGetterSetter;
use OpenTelemetry\Contrib\Otlp\SpanExporter;
use OpenTelemetry\SDK\Common\Attribute\Attributes;
use OpenTelemetry\SDK\Resource\ResourceInfo;
use OpenTelemetry\SDK\Resource\ResourceInfoFactory;
use OpenTelemetry\SDK\Trace\Sampler\ParentBased;
use OpenTelemetry\SDK\Trace\Sampler\TraceIdRatioBasedSampler;
use OpenTelemetry\SDK\Trace\SpanProcessor\BatchSpanProcessor;
use OpenTelemetry\SDK\Trace\TracerProvider;
use OpenTelemetry\SemConv\ResourceAttributes;
use Throwable;

final class TelemetryManager
{
    private static ?TracerProvider $tracerProvider = null;
    private static ?TracerInterface $tracer = null;

    /**
     * Inisialisasi Tracing Provider dengan konfigurasi Enterprise
     */
    public static function init(string $serviceName, string $environment, float $sampleRate = 0.1): void
    {
        $resource = ResourceInfoFactory::emptyResource()->merge(
            ResourceInfo::create(Attributes::create([
                ResourceAttributes::SERVICE_NAME => $serviceName,
                ResourceAttributes::DEPLOYMENT_ENVIRONMENT => $environment,
                ResourceAttributes::HOST_NAME => gethostname(),
                ResourceAttributes::PROCESS_PID => getmypid(),
            ]))
        );

        // Ekspor ke OTel Collector lokal melalui gRPC atau HTTP Protobuf
        $exporter = new SpanExporter(
            endpoint: getenv('OTEL_EXPORTER_OTLP_ENDPOINT') ?: 'http://otel-collector:4318/v1/traces'
        );

        // Batch processor untuk efisiensi buffering I/O
        $spanProcessor = new BatchSpanProcessor(
            exporter: $exporter,
            clock: SystemClock::getInstance(),
            maxQueueSize: 2048,
            scheduledDelayMillis: 200,
            exportTimeoutMillis: 1000,
            maxExportBatchSize: 512
        );

        // Sampler: Parent-based dengan fallback ke sampling rasio (misal 10%)
        $sampler = new ParentBased(new TraceIdRatioBasedSampler($sampleRate));

        self::$tracerProvider = new TracerProvider(
            spanProcessors: [$spanProcessor],
            sampler: $sampler,
            resource: $resource
        );

        self::$tracer = self::$tracerProvider->getTracer('enterprise.telemetry.core', '1.0.0');
    }

    public static function getTracer(): TracerInterface
    {
        if (self::$tracer === null) {
            throw new \RuntimeException('TelemetryManager must be initialized before use.');
        }
        return self::$tracer;
    }

    /**
     * Eksekusi callable dalam konteks Span terisolasi dengan auto context-propagation
     */
    public static function traceOperation(string $operationName, callable $callback, array $attributes = []): mixed
    {
        $tracer = self::getTracer();
        
        // Ekstraksi context dari HTTP Request Headers jika ada
        $carrier = getallheaders();
        $context = TraceContextPropagator::getInstance()->extract($carrier, ArrayAccessGetterSetter::getInstance());

        $span = $tracer->spanBuilder($operationName)
            ->setParent($context)
            ->setSpanKind(SpanKind::SPAN_KIND_SERVER)
            ->setAttributes($attributes)
            ->startSpan();

        $scope = $span->activate();

        try {
            return $callback($span);
        } catch (Throwable $e) {
            $span->recordException($e, [
                'exception.escaped' => true,
            ]);
            $span->setStatus(StatusCode::STATUS_ERROR, $e->getMessage());
            throw $e;
        } finally {
            $span->end();
            $scope->detach();
        }
    }

    /**
     * Menjalankan flushing non-blocking pasca response FastCGI selesai
     */
    public static function shutdown(): void
    {
        if (function_exists('fastcgi_finish_request')) {
            fastcgi_finish_request(); // Lepaskan client HTTP socket secara instan
        }

        if (self::$tracerProvider !== null) {
            self::$tracerProvider->shutdown();
        }
    }
}
