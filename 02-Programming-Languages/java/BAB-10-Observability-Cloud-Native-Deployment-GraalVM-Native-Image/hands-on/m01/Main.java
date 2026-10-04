package com.enterprise.telemetry;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.api.common.AttributeKey;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.StatusCode;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Scope;
import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.resources.Resource;
import io.opentelemetry.sdk.trace.SdkTracerProvider;
import io.opentelemetry.sdk.trace.export.SimpleSpanProcessor;
import io.opentelemetry.sdk.trace.export.SpanExporter;

import java.time.Duration;
import java.util.concurrent.TimeUnit;

public final class TelemetryEngine {

    private final Tracer tracer;
    private final MeterRegistry meterRegistry;
    private final Counter transactionCounter;
    private final Timer transactionTimer;

    public TelemetryEngine() {
        // 1. Inisialisasi OpenTelemetry SDK
        Resource resource = Resource.getDefault().merge(
            Resource.create(Attributes.of(AttributeKey.stringKey("service.name"), "core-payment-engine"))
        );

        SpanExporter loggingExporter = new InMemoryLoggingSpanExporter();
        SdkTracerProvider tracerProvider = SdkTracerProvider.builder()
            .addSpanProcessor(SimpleSpanProcessor.create(loggingExporter))
            .setResource(resource)
            .build();

        OpenTelemetry openTelemetry = OpenTelemetrySdk.builder()
            .setTracerProvider(tracerProvider)
            .build();

        this.tracer = openTelemetry.getTracer("com.enterprise.telemetry", "1.0.0");

        // 2. Inisialisasi Micrometer Registry
        this.meterRegistry = new SimpleMeterRegistry();
        this.transactionCounter = Counter.builder("transactions.processed.total")
            .description("Total number of processed transactions")
            .tag("env", "production")
            .register(meterRegistry);

        this.transactionTimer = Timer.builder("transactions.latency")
            .description("Latency distribution of transactions")
            .tag("env", "production")
            .publishPercentiles(0.5, 0.95, 0.99)
            .register(meterRegistry);
    }

    public void executeTrackedOperation(String transactionId, double amount) {
        Span parentSpan = tracer.spanBuilder("executeTrackedOperation")
            .setAttribute("transaction.id", transactionId)
            .setAttribute("transaction.amount", amount)
            .startSpan();

        long startTimeNs = System.nanoTime();

        try (Scope scope = parentSpan.makeCurrent()) {
            // Simulasi Business Logic
            processBusinessLogic(transactionId);
            
            parentSpan.setStatus(StatusCode.OK);
            transactionCounter.increment();
        } catch (Exception ex) {
            parentSpan.setStatus(StatusCode.ERROR, ex.getMessage());
            parentSpan.recordException(ex);
            throw ex;
        } finally {
            long durationNs = System.nanoTime() - startTimeNs;
            transactionTimer.record(durationNs, TimeUnit.NANOSECONDS);
            parentSpan.end();
        }
    }

    private void processBusinessLogic(String transactionId) {
        Span childSpan = tracer.spanBuilder("validateAndPersist")
            .startSpan();
        try (Scope childScope = childSpan.makeCurrent()) {
            Thread.sleep(20); // Simulasi delay eksekusi
            childSpan.addEvent("Database Write Completed", Attributes.of(AttributeKey.stringKey("db.table"), "transactions"));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Execution interrupted", e);
        } finally {
            childSpan.end();
        }
    }

    // Dummy exporter untuk testing konsol
    private static class InMemoryLoggingSpanExporter implements SpanExporter {
        @Override
        public io.opentelemetry.sdk.common.CompletableResultCode export(java.util.Collection<io.opentelemetry.sdk.trace.data.SpanData> spans) {
            for (var span : spans) {
                System.out.printf("[TRACE] SpanName: %s | TraceId: %s | SpanId: %s | Duration: %d ms%n",
                    span.getName(), span.getTraceId(), span.getSpanId(), 
                    Duration.ofNanos(span.getEndEpochNanos() - span.getStartEpochNanos()).toMillis());
            }
            return io.opentelemetry.sdk.common.CompletableResultCode.ofSuccess();
        }

        @Override
        public io.opentelemetry.sdk.common.CompletableResultCode flush() {
            return io.opentelemetry.sdk.common.CompletableResultCode.ofSuccess();
        }

        @Override
        public io.opentelemetry.sdk.common.CompletableResultCode shutdown() {
            return io.opentelemetry.sdk.common.CompletableResultCode.ofSuccess();
        }
    }

    public static void main(String[] args) {
        TelemetryEngine engine = new TelemetryEngine();
        engine.executeTrackedOperation("TX-10023", 450000.0);
        
        System.out.println("\n--- MICROMETER METRICS SUMMARY ---");
        System.out.println("Counter Value: " + engine.transactionCounter.count());
        System.out.println("Timer Mean Latency (ms): " + engine.transactionTimer.mean(TimeUnit.MILLISECONDS));
    }
}
