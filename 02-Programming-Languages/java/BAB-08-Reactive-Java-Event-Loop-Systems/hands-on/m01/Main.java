package com.architect.reactive.production;

import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;
import reactor.util.context.Context;

import java.time.Duration;
import java.time.Instant;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

public class ProductionPaymentIngestionEngine {

    // Monitoring metrics internal
    private static final AtomicLong PROCESSED_COUNTER = new AtomicLong(0);
    private static final AtomicLong DROPPED_COUNTER = new AtomicLong(0);

    public record PaymentWebhookPayload(
            String transactionId,
            String merchantId,
            double amount,
            String signature,
            long timestamp
    ) {}

    public record ProcessingResult(
            String transactionId,
            String status,
            String executionThread,
            Instant processedAt
    ) {}

    public static void main(String[] args) throws InterruptedException {
        ProductionPaymentIngestionEngine engine = new ProductionPaymentIngestionEngine();

        // 1. Mensimulasikan sumber banjir data webhook (Burst 10.000 incoming requests)
        Flux<PaymentWebhookPayload> highThroughputStream = Flux.range(1, 10_000)
                .map(i -> new PaymentWebhookPayload(
                        UUID.randomUUID().toString(),
                        "MERCHANT_" + (i % 50),
                        150.00 + i,
                        "HMAC_SIGNATURE_MOCK_" + i,
                        System.currentTimeMillis()
                ));

        // 2. Mendaftarkan stream transaksi ke Ingestion Engine
        engine.processTransactionStream(highThroughputStream)
                .contextWrite(Context.of("TRACE_ID", UUID.randomUUID().toString()))
                .doOnNext(res -> {
                    long count = PROCESSED_COUNTER.incrementAndGet();
                    if (count % 1000 == 0) {
                        System.out.printf("[METRICS] Processed: %d events | Dropped: %d%n",
                                count, DROPPED_COUNTER.get());
                    }
                })
                .blockLast(); // Block hanya untuk demo runner lifecycle

        System.out.println("Processing Terminated. Final Processed: " + PROCESSED_COUNTER.get());
    }

    public Flux<ProcessingResult> processTransactionStream(Flux<PaymentWebhookPayload> inboundFlux) {
        return inboundFlux
                // Mitigasi Overpressure: Gunakan Backpressure Drop Strategy jika downstream tidak mampu
                .onBackpressureBuffer(
                        500, // Kapasitas buffer maksimal
                        droppedItem -> {
                            DROPPED_COUNTER.incrementAndGet();
                            System.err.println("[BACKPRESSURE DROP] Dropping transaction: " + droppedItem.transactionId());
                        }
                )
                // Isolasi validasi kriptografi ke pool parallel (CPU-Bound)
                .publishOn(Schedulers.parallel(), 128) // Prefetch 128 items
                .flatMap(payload -> validateCryptographicSignature(payload)
                        .filter(Boolean::booleanValue)
                        .map(valid -> payload)
                        .switchIfEmpty(Mono.error(new SecurityException("Invalid HMAC signature"))),
                        64 // Concurrency level untuk flatMap
                )
                // Isolasi persistensi database dan legacy bank API ke pool boundedElastic (I/O Bound)
                .publishOn(Schedulers.boundedElastic(), 128)
                .flatMap(validPayload -> executeDownstreamSettlement(validPayload)
                        // Ketahanan: Retry dengan Exponential Backoff + Jitter
                        .retryWhen(reactor.util.retry.Retry.backoff(3, Duration.ofMillis(50))
                                .maxBackoff(Duration.ofMillis(500))
                                .filter(ex -> !(ex instanceof SecurityException))
                        )
                        // Fallback jika bank downstream down total
                        .onErrorResume(ex -> fallbackDeadLetterQueue(validPayload, ex)),
                        32 // Konkurensi panggilan keluar dibatasi 32 untuk mencegah exhaust socket
                );
    }

    private Mono<Boolean> validateCryptographicSignature(PaymentWebhookPayload payload) {
        return Mono.deferContextual(ctxView -> {
            String traceId = ctxView.getOrDefault("TRACE_ID", "UNKNOWN");
            // Simulasi komputasi HMAC hash non-blocking
            boolean isValid = payload.signature() != null && payload.signature().startsWith("HMAC_");
            return Mono.just(isValid);
        });
    }

    private Mono<ProcessingResult> executeDownstreamSettlement(PaymentWebhookPayload payload) {
        return Mono.deferContextual(ctxView -> {
            String traceId = ctxView.getOrDefault("TRACE_ID", "UNKNOWN");
            
            // Mensimulasikan latensi jaringan I/O yang fluktuatif ke bank
            long simulatedLatency = 10 + (long)(Math.random() * 40);
            
            return Mono.delay(Duration.ofMillis(simulatedLatency))
                    .thenReturn(new ProcessingResult(
                            payload.transactionId(),
                            "SETTLED",
                            Thread.currentThread().getName(),
                            Instant.now()
                    ));
        });
    }

    private Mono<ProcessingResult> fallbackDeadLetterQueue(PaymentWebhookPayload payload, Throwable cause) {
        return Mono.fromCallable(() -> {
            // Simulasi penyimpanan lokal ke fail-safe disk queue / Kafka DLQ
            return new ProcessingResult(
                    payload.transactionId(),
                    "FAILED_QUEUED_DLQ: " + cause.getMessage(),
                    Thread.currentThread().getName(),
                    Instant.now()
            );
        }).subscribeOn(Schedulers.boundedElastic());
    }
}
