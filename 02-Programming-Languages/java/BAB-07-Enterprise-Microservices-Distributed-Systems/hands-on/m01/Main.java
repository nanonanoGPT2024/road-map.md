package com.enterprise.distributed.client;

import io.github.resilience4j.circuitbreaker.CallNotPermittedException;
import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.CircuitBreakerConfig;
import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import io.github.resilience4j.retry.Retry;
import io.github.resilience4j.retry.RetryConfig;
import io.github.resilience4j.retry.RetryRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

import java.time.Duration;
import java.util.Objects;
import java.util.function.Supplier;

public class ExternalPaymentClient {

    private static final Logger log = LoggerFactory.getLogger(ExternalPaymentClient.class);

    private final RestClient restClient;
    private final CircuitBreaker circuitBreaker;
    private final Retry retry;

    public record PaymentRequest(String transactionId, String accountId, long amountInCents) {}
    public record PaymentResponse(String paymentReference, String status, String message) {}

    public ExternalPaymentClient(RestClient.Builder restClientBuilder, String baseUrl) {
        this.restClient = restClientBuilder
                .baseUrl(baseUrl)
                .build();

        // 1. Konfigurasi Circuit Breaker
        CircuitBreakerConfig cbConfig = CircuitBreakerConfig.custom()
                .slidingWindowType(CircuitBreakerConfig.SlidingWindowType.COUNT_BASED)
                .slidingWindowSize(10)
                .minimumNumberOfCalls(5)
                .failureRateThreshold(50.0f) // Trip jika >= 50% call gagal
                .slowCallRateThreshold(70.0f)
                .slowCallDurationThreshold(Duration.ofMillis(1500))
                .waitDurationInOpenState(Duration.ofSeconds(5))
                .permittedNumberOfCallsInHalfOpenState(3)
                .automaticTransitionFromOpenToHalfOpenEnabled(true)
                .recordExceptions(ResourceAccessException.class, RemoteServerException.class)
                .build();

        CircuitBreakerRegistry cbRegistry = CircuitBreakerRegistry.of(cbConfig);
        this.circuitBreaker = cbRegistry.circuitBreaker("paymentServiceBreaker");

        // 2. Konfigurasi Retry dengan Exponential Backoff
        RetryConfig retryConfig = RetryConfig.custom()
                .maxAttempts(3)
                .waitDuration(Duration.ofMillis(200))
                .intervalFunction(io.github.resilience4j.core.IntervalFunction.ofExponentialBackoff(200, 2.0))
                .retryExceptions(ResourceAccessException.class) // Hanya retry masalah I/O jaringan transient
                .ignoreExceptions(CallNotPermittedException.class) // Jangan retry jika Circuit Breaker OPEN
                .build();

        RetryRegistry retryRegistry = RetryRegistry.of(retryConfig);
        this.retry = retryRegistry.retry("paymentServiceRetry");
    }

    public PaymentResponse executePayment(PaymentRequest request) {
        Objects.requireNonNull(request, "PaymentRequest cannot be null");

        // Membungkus invocation dengan Decorator Chain: CircuitBreaker -> Retry -> Execution
        Supplier<PaymentResponse> decoratedCall = DecoratorContext.decorateSupplier(
                circuitBreaker,
                retry,
                () -> invokeRemotePaymentApi(request)
        );

        try {
            return decoratedCall.get();
        } catch (CallNotPermittedException e) {
            log.error("Circuit Breaker OPEN. Payment rejected for txn: {}", request.transactionId());
            return new PaymentResponse(null, "FAIL_CIRCUIT_OPEN", "Service unavailable. Try again later.");
        } catch (Exception e) {
            log.error("Execution failed after retries for txn: {}", request.transactionId(), e);
            return new PaymentResponse(null, "FAIL_SYSTEM_ERROR", e.getMessage());
        }
    }

    private PaymentResponse invokeRemotePaymentApi(PaymentRequest request) {
        log.info("Sending payment outbound request: {}", request.transactionId());
        
        return restClient.post()
                .uri("/v1/payments")
                .contentType(MediaType.APPLICATION_JSON)
                .body(request)
                .retrieve()
                .onStatus(HttpStatusCode::is5xxServerError, (req, res) -> {
                    throw new RemoteServerException("Server Error from Payment Gateway: " + res.getStatusCode());
                })
                .body(PaymentResponse.class);
    }

    public static class RemoteServerException extends RuntimeException {
        public RemoteServerException(String message) {
            super(message);
        }
    }

    private static final class DecoratorContext {
        public static <T> Supplier<T> decorateSupplier(CircuitBreaker cb, Retry retry, Supplier<T> supplier) {
            Supplier<T> retriedSupplier = Retry.decorateSupplier(retry, supplier);
            return CircuitBreaker.decorateSupplier(cb, retriedSupplier);
        }
    }
}
