# MODUL PEMBELAJARAN: ENTERPRISE MICROSERVICES & DISTRIBUTED SYSTEMS
**Kategori:** 02-Programming-Languages | **Track:** Java Enterprise Architecture | **Bab 07:** Modul 01

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** `JAVA-ENT-0701`
* **Mata Pelajaran / Topik:** Enterprise Microservices & Distributed Systems Architecture
* **Tingkat Kemahiran:** Advanced / Principal Engineer Level
* **Prasyarat Teknis:**
  * Penguasaan mendalam Java Core (Java 17/21 LTS), Concurrency & Multithreading (JUC, Virtual Threads).
  * Penguasaan Spring Boot 3.x, Spring Data JPA, dan mekanisme Spring Dependency Injection.
  * Pemahaman tentang Relational Database Management Systems (PostgreSQL) dan Messaging Broker (Apache Kafka).
  * Pengalaman membangun RESTful API dan pemahaman dasar tentang protokol HTTP/2, gRPC, serta Docker.
* **Target Runtime & Framework:** 
  * OpenJDK 21 LTS (Temurin/Corretto)
  * Spring Boot 3.3.x / Spring Cloud 2023.0.x (Leyton)
  * Resilience4j 2.2.x
  * Micrometer Tracing & OpenTelemetry SDK
* **Estimasi Waktu Penyelesaian:** 12 - 16 Jam Studi Intensif & Praktikum Terpandu

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik memiliki kapabilitas terukur untuk:
1. **Menganalisis & Menguraikan Sistem Monolitik:** Merumuskan dekomposisi sistem monolitik menjadi bounded context microservices menggunakan metodologi Strategic Domain-Driven Design (DDD) tanpa menimbulkan *distributed monolith*.
2. **Mengimplementasikan Pola Ketahanan Sistem (Fault Tolerance):** Mengonfigurasi dan memvalidasi Circuit Breaker, Rate Limiter, Retry dengan Exponential Backoff, dan Bulkhead pattern menggunakan Resilience4j secara non-blocking pada sistem berbasis Spring Boot 3.
3. **Mengeksekusi Konsistensi Data Terdistribusi:** Mengkonstruksi mekanisme *Transactional Outbox Pattern* dan *Saga Pattern* (Orchestration & Choreography) guna menjamin konsistensi *Eventual Consistency* tanpa mengandalkan Two-Phase Commit (2PC / XA Transactions).
4. **Menerapkan Desain Komunikasi Idempoten:** Membangun API consumer dan event handler yang kebal terhadap duplikasi transmisi jaringan (*at-least-once delivery*) dengan mengimplementasikan distributed deduplication keys.
5. **Menerapkan Observabilitas Terdistribusi End-to-End:** Mengonfigurasi distributed tracing konteks W3C menggunakan OpenTelemetry dan Micrometer Tracing untuk melacak latensi dan kegagalan lintas batas layanan independen.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Dari In-Memory Calling ke Fallible Networks
Dalam arsitektur monolitik, pemanggilan antar-komponen terjadi pada memori fisik yang sama (`invokeinterface` / `invokevirtual` pada JVM). Eksekusi bersifat deterministik: fungsi dieksekusi, menghasilkan *return value*, atau melempar runtime exception secara sinkron. Waktu eksekusi diukur dalam skala nanodetik hingga mikrodetik.

Pada sistem terdistribusi, batas eksekusi berpindah ke jaringan fisik (*network hop*). Anda harus menginternalisasi **8 Fallacies of Distributed Computing**:
1. Jaringan selalu dapat diandalkan (*The network is reliable*).
2. Latensi adalah nol (*Latency is zero*).
3. Bandwidth tidak terbatas (*Bandwidth is infinite*).
4. Jaringan aman (*The network is secure*).
5. Topologi jaringan tidak berubah (*Topology doesn't change*).
6. Hanya ada satu administrator (*There is one administrator*).
7. Biaya transportasi data adalah nol (*Transport cost is zero*).
8. Jaringan bersifat homogen (*The network is homogeneous*).

```
MONOLITHIC IN-MEMORY CALL:
[Caller Thread] ---> [OrderService.process()] ---> [Memory Heap Reference]
(Deterministic, Synchronous, Sub-microsecond)

DISTRIBUTED BOUNDARY CALL:
[Service A] --(TCP Handshake)--> [Router/Firewall] --(Latency/Jitter)--> [Service B]
                     \                                                /
                      \---------> [PACKET LOSS / TIMEOUT] <----------/
(Nondeterministic, Partial Failures, Indeterminate State: SENT? EXECUTED? LOST?)
```

### The Dual-Write Problem
Mental model paling krusial dalam sistem terdistribusi adalah pengakuan bahwa **menulis ke dua sistem penyimpanan independen secara atomik tanpa overhead ekstrem adalah hal yang mustahil secara native**.

```java
// ANTI-PATTERN: THE NAIVE DUAL-WRITE
@Transactional
public void createOrder(Order order) {
    orderRepository.save(order);       // Database Transaction Commit
    kafkaTemplate.send("orders", order); // Jaringan Kafka bisa putus di sini!
}
```
Jika `kafkaTemplate.send()` gagal karena timeout jaringan, database lokal telah ter-commit (data inkonsisten). Jika keduanya dibalik, database bisa mengalami constraint violation, namun pesan event sudah telanjur terkirim ke downstream services. Solusi untuk masalah ini adalah **Transactional Outbox Pattern**, di mana event disimpan pada tabel basis data lokal yang sama menggunakan satu transaksi ACID lokal, sebelum di-relay oleh poller/CDC (*Change Data Capture*) ke broker.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Arsitektur Global: Transactional Outbox Pattern dengan CDC/Poller

```
+---------------------------------------------------------------------------------------+
| SERVICE ORDER (Context Boundary)                                                      |
|                                                                                       |
|  [REST Client]                                                                        |
|        │                                                                              |
|        ▼                                                                              |
|  [OrderController]                                                                    |
|        │                                                                              |
|        ▼                                                                              |
|  [OrderApplicationService]                                                            |
|        │                                                                              |
|        ├──(Local ACID Transaction)──────────────────────┐                             |
|        │                                                │                             |
|        ▼                                                ▼                             |
|  [orders Table]                              [outbox_events Table]                    |
|  (ID, Status, Payload)                       (ID, AggregateType, Event, Status)       |
+---------------------------------------------------------│-----------------------------+
                                                          │
                    ┌─────────────────────────────────────┘
                    │ (Asynchronous Relay Engine)
                    ▼
       +─────────────────────────+
       |   Outbox Publisher      |
       |  (Spring Scheduled /    |
       |   Debezium CDC)         |
       +────────────┬────────────+
                    │
                    ▼ (Idempotent Message Transmission)
       +─────────────────────────+
       |   Apache Kafka Topic    |
       |   ("order-events")      |
       +────────────┬────────────+
                    │
                    ▼
+---------------------------------------------------------------------------------------+
| SERVICE PAYMENT (Context Boundary)                                                    |
|                                                                                       |
|   [Kafka Consumer] ──▶ [Idempotency Deduplication Filter]                             |
|                                  │                                                    |
|                                  ├── (Exists) ──▶ [ACK & Skip]                        |
|                                  │                                                    |
|                                  └── (Not Exists) ──▶ [Local Payment Transaction]     |
+---------------------------------------------------------------------------------------+
```

### 2. State Machine: Resilience4j Circuit Breaker State Transition

```
                        Failure Rate > Threshold
                        Slow Call Rate > Threshold
                   ┌──────────────────────────────────┐
                   │                                  │
                   ▼                                  │
          +──────────────────+             +──────────────────+
          |                  |             |                  |
   ┌─────▶|      CLOSED      |             |       OPEN       |◀────┐
   │      | (Normal Traffic) |             | (Fails Fast,     |     │
   │      |                  |             |  Fallback Exec)  |     │
   │      +──────────────────+             +──────────────────+     │
   │               ▲                                  │             │
   │               │                                  │ Wait        │
   │  Success Rate │                                  │ Duration    │
   │  >= Threshold │                                  ▼ Elapsed     │
   │               │                       +──────────────────+     │
   │               │                       |                  |     │
   │               └───────────────────────|    HALF-OPEN     |─────┘
   │                                       | (Trial Traffic)  |  Failure Rate >=
   │                                       |                  |  Threshold
   └───────────────────────────────────────+──────────────────+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Sliding Window Metrics pada Resilience4j
Resilience4j tidak mengalokasikan timer thread per request. Alih-alih demikian, ia menggunakan struktur data cincin memori (*circular array*) dengan alokasi statis berbasis **Count-Based** atau **Time-Based**.

*   **Count-based Sliding Window:** Menggunakan array melingkar berukuran $N$. Jika ukuran jendela adalah 100, array menyimpan metrik dari 100 eksekusi pemanggilan terakhir. Pemanggilan ke-101 akan menggeser jendela dengan menimpa data pemanggilan tertua ($O(1)$ time complexity).
*   **Time-based Sliding Window:** Menggunakan array melingkar berukuran $N$ detik. Setiap slot menyimpan hasil agregasi (sukses, gagal, lambat) dari detik tertentu. Saat waktu bergeser, slot lama direset dan digunakan kembali.

Threshold dihitung sebagai persentase:
$$\text{Failure Rate} = \left( \frac{\text{Jumlah Gagal}}{\text{Total Panggilan Terukur}} \right) \times 100\%$$

Ketika `Failure Rate >= failureRateThreshold`, circuit breaker beralih dari state `CLOSED` ke `OPEN`. Semua thread yang masuk berikutnya langsung dialihkan ke fallback atau menerima `CallNotPermittedException` tanpa melakukan eksekusi jaringan.

### 2. Context Propagation & Distributed Tracing (W3C Standard)
Tracing terdistribusi beroperasi dengan menginjeksi metadata telemetri ke dalam transport carrier (HTTP header atau Kafka record header). Standar W3C Trace Context mendefinisikan dua header utama:

1.  `traceparent`: Berformat `version-trace_id-parent_id-trace_flags`
    *   *Example:* `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`
    *   `trace_id` (32 hex characters): Identitas global transaksi yang melintasi puluhan microservices.
    *   `parent_id` (16 hex characters): Identitas pemanggilan lokal (span ID pengirim).
    *   `trace_flags` (8-bit field, `01` berarti di-*sample* untuk disimpan).
2.  `tracestate`: Menyediakan pasangan key-value khusus vendor monitoring.

Pada thread runtime Java, metadata ini disimpan di dalam thread-local storage (`ThreadLocal`). Saat virtual thread atau reactive pipeline digunakan, tracing framework (seperti Micrometer Tracing) harus melakukan transfer konteks (*context capture & restoration*) secara eksplisit antar unit eksekusi.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### CAP & PACELC Theorem
Teorema CAP menyatakan bahwa di dalam sistem data terdistribusi yang mengalami partisi jaringan ($P$), arsitektur hanya dapat memilih salah satu di antara:
*   **Consistency ($C$):** Setiap pembacaan menerima penulisan terbaru atau error.
*   **Availability ($A$):** Setiap permintaan non-failing node menerima respon non-error, tanpa jaminan bahwa respon memuat penulisan data terbaru.

Teorema **PACELC** memperluas CAP untuk kondisi di mana jaringan berjalan normal:
*   Jika terjadi Partisi ($P$), bagaimana trade-off antara Ketersediaan ($A$) dan Konsistensi ($C$)?
*   **Else ($E$):** Ketika sistem berjalan normal tanpa partisi, bagaimana trade-off antara Latensi ($L$) dan Konsistensi ($C$)?

Sistem enterprise e-commerce modern umumnya memilih model **PA/EL**: Mengorbankan konsistensi absolut (*strict serializability*) demi ketersediaan tinggi saat partisi jaringan, dan mengorbankan konsistensi ketat demi latensi rendah saat operasi normal, dengan menerapkan **BASE (Basically Available, Soft state, Eventual consistency)**.

### Saga Pattern: Orchestration vs Choreography
Ketika transaksi ACID lokal tidak dapat menjangkau beberapa layanan, Saga Pattern diterapkan melalui serangkaian transaksi lokal yang saling terhubung:

| Dimensi | Choreography (Event-Driven) | Orchestration (Command-Driven) |
| :--- | :--- | :--- |
| **Kopling** | Loose coupling. Komponen bereaksi terhadap event domain. | Tightly coupled ke orchestrator central. |
| **Kompleksitas Alur** | Sulit dianalisis secara visual saat sistem memiliki > 10 layanan. Risiko circular dependency. | Terpusat. Mudah dipantau status status saganya melalui orchestrator state machine. |
| **Titik Kegagalan (SPOF)** | Terdistribusi. Tidak ada single orchestrator failure point. | Orchestrator merupakan critical point (harus di-cluster). |
| **Implementasi Kompensasi** | Setiap layanan wajib mendengarkan compensation event balik. | Orchestrator secara eksplisit mengirim rollback command ke layanan terkait. |

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi klien HTTP terdistribusi yang tangguh menggunakan Spring 6 `RestClient` yang diintegrasikan secara native dengan Resilience4j CircuitBreaker dan Retry programatik, tanpa mengandalkan *magic annotation* yang sering menyembunyikan thread-safety issue.

### File: `ExternalPaymentClient.java`
```java
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
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis komponen arsitektur pada kode Seksi 07:

1.  **Baris 24-25 (`record PaymentRequest`, `record PaymentResponse`):**
    Menggunakan *Immutable Java Records*. Mencegah terjadinya *state mutation* secara konkuren antar-thread pool ketika request object dioperasikan lintas decorator.
2.  **Baris 33-46 (`CircuitBreakerConfig cbConfig`):**
    *   `slidingWindowType(COUNT_BASED)` dengan ukuran 10: Pengukuran kegagalan dihitung murni dari 10 panggilan eksekusi terakhir.
    *   `minimumNumberOfCalls(5)`: Menghentikan circuit breaker berpindah ke `OPEN` sebelum sampel minimal (5 panggilan) terpenuhi, mencegah false-positive saat aplikasi baru booting (*cold start*).
    *   `failureRateThreshold(50.0f)`: Jika 5 dari 10 eksekusi melempar exception yang terdaftar, circuit breaker berpindah ke status `OPEN`.
    *   `permittedNumberOfCallsInHalfOpenState(3)`: Pada kondisi `HALF-OPEN`, hanya 3 panggilan pengujian yang diizinkan lewat secara deterministik untuk mengevaluasi pemulihan downstream.
3.  **Baris 51-57 (`RetryConfig retryConfig`):**
    *   `ofExponentialBackoff(200, 2.0)`: Upaya pertama menunggu 200ms, upaya kedua menunggu 400ms ($200 \times 2^1$). Ini mencegah fenomena *Thundering Herd* pada gateway pembayaran eksternal.
    *   `retryExceptions(ResourceAccessException.class)`: Retry **hanya** diterapkan pada level I/O timeout jaringan murni.
    *   `ignoreExceptions(CallNotPermittedException.class)`: Krusial. Jika circuit breaker sudah `OPEN`, proses retry tidak boleh dilakukan karena beban komputasi hanya akan membuang thread time.
4.  **Baris 70-74 (`DecoratorContext.decorateSupplier(...)`):**
    Menyusun urutan wrapping. Sirkuit diuji terlebih dahulu sebelum mengeksekusi mekanisme retry. Jika sirkuit `OPEN`, decorator langsung menghentikan request tanpa mengeksekusi logika retry sama sekali.
5.  **Baris 89-94 (`restClient.post()...onStatus(...)`):**
    Menerjemahkan *HTTP 5xx Server Error* secara eksplisit menjadi unchecked exception bertipe `RemoteServerException`. Tanpa mapping ini, Spring `RestClient` tidak melempar tipe spesifik yang dibutuhkan oleh sliding window matcher.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Sistem Manajemen Pembayaran E-Commerce Skala Tinggi
*   **Permasalahan Lapangan:** Platform marketplace memproses lonjakan transaksi $10.000$ Checkout per Detik (TPS). Layanan Order (`OrderService`) melakukan koordinasi pemesanan dan pemotongan inventaris. Selama promo flash sale, jaringan antar-layanan mengalami *packet loss* 4% dan latensi acak antara $800\text{ms}$ hingga $4500\text{ms}$.
*   **Dampak Buruk:**
    1.  Terjadi fenomena *Double Debit*: Pengguna dikenakan biaya dua kali karena client melakukan *auto-retry* saat connection timeout, sementara backend payment service tetap menyelesaikan penulisan mutasi pertama.
    2.  *Cascading Failure*: Ketiadaan circuit breaker pada `OrderService` mengakibatkan thread pool Tomcat (maksimum 200 thread) habis total (*exhausted*) hanya untuk menunggu respon lambat dari payment gateway. Akibatnya, modul pencarian katalog dan pembatalan pesanan ikut tumbang.
*   **Solusi Rekayasa Terdistribusi:**
    *   Menerapkan **Transactional Outbox Pattern** untuk mengamankan integrasi event ke Apache Kafka.
    *   Pemberian **Idempotency Execution Filter** pada consumer backend berbasis Redis cluster distributed lock dan PostgreSQL transactional upsert record.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah arsitektur lengkap implementasi Transactional Outbox Pattern dan Idempotent Consumer pada Java 21 dan Spring Boot 3.

```
                  ORDER SERVICE                                KAFKA BROKER             PAYMENT SERVICE
 +─────────────────────────────────────────────+                     |        +──────────────────────────────────+
 | [Thread]                                    |                     |        |                                  |
 |    │                                        |                     |        |                                  |
 |    ▼                                        |                     |        |                                  |
 |  Begin Transaction                          |                     |        |                                  |
 |    ├── Insert into "orders"                 |                     |        |                                  |
 |    └── Insert into "outbox_events"          |                     |        |                                  |
 |  Commit Transaction                         |                     |        |                                  |
 |                                             |                     |        |                                  |
 | [Background Poller]                         |                     |        |                                  |
 |    │ (Polling table "outbox_events")        |                     |        |                                  |
 |    ▼                                        |                     |        |                                  |
 |  KafkaTemplate.send() ──────────────────────┼── "order-events" ───┼───────▶|  @KafkaListener                  |
 |    │                                        |                     |        |    │                             |
 |  Mark Outbox as PROCESSED                   |                     |        |    ▼                             |
 +─────────────────────────────────────────────+                     |        |  Check Idempotency Table         |
                                                                     |        |    ├── If Processed: Skip        |
                                                                     |        |    └── If New: Process Payment   |
                                                                     |        +──────────────────────────────────+
```

### 1. Entitas & Outbox Table (Domain & Infrastruktur)
```java
package com.enterprise.distributed.domain;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "orders")
public class Order {
    @Id
    private UUID id;
    
    @Column(nullable = false)
    private String customerId;
    
    @Column(nullable = false)
    private Long amountInCents;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private OrderStatus status;

    public enum OrderStatus { PENDING, CONFIRMED, FAILED }

    protected Order() {}

    public Order(UUID id, String customerId, Long amountInCents) {
        this.id = id;
        this.customerId = customerId;
        this.amountInCents = amountInCents;
        this.status = OrderStatus.PENDING;
    }

    public UUID getId() { return id; }
    public String getCustomerId() { return customerId; }
    public Long getAmountInCents() { return amountInCents; }
    public OrderStatus getStatus() { return status; }
}
```

```java
package com.enterprise.distributed.outbox;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "outbox_events")
public class OutboxEvent {
    @Id
    private UUID id;

    @Column(nullable = false)
    private String aggregateType;

    @Column(nullable = false)
    private String aggregateId;

    @Column(nullable = false)
    private String type;

    @Lob
    @Column(nullable = false)
    private String payload;

    @Column(nullable = false)
    private Instant createdAt;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private OutboxStatus status;

    public enum OutboxStatus { PENDING, PUBLISHED, FAILED }

    protected OutboxEvent() {}

    public OutboxEvent(String aggregateType, String aggregateId, String type, String payload) {
        this.id = UUID.randomUUID();
        this.aggregateType = aggregateType;
        this.aggregateId = aggregateId;
        this.type = type;
        this.payload = payload;
        this.createdAt = Instant.now();
        this.status = OutboxStatus.PENDING;
    }

    public UUID getId() { return id; }
    public String getPayload() { return payload; }
    public String getAggregateId() { return aggregateId; }
    public void markAsPublished() { this.status = OutboxStatus.PUBLISHED; }
}
```

### 2. Service Layer: Transaksi Atomik Lokal
```java
package com.enterprise.distributed.service;

import com.enterprise.distributed.domain.Order;
import com.enterprise.distributed.outbox.OutboxEvent;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.persistence.EntityManager;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Service
public class OrderApplicationService {

    private final EntityManager entityManager;
    private final ObjectMapper objectMapper;

    public record CreateOrderCommand(String customerId, Long amountInCents) {}
    public record OrderCreatedEvent(UUID orderId, String customerId, Long amountInCents) {}

    public OrderApplicationService(EntityManager entityManager, ObjectMapper objectMapper) {
        this.entityManager = entityManager;
        this.objectMapper = objectMapper;
    }

    @Transactional(isolation = Isolation.READ_COMMITTED)
    public UUID handleCreateOrder(CreateOrderCommand cmd) {
        UUID orderId = UUID.randomUUID();
        Order order = new Order(orderId, cmd.customerId(), cmd.amountInCents());
        entityManager.persist(order);

        OrderCreatedEvent eventData = new OrderCreatedEvent(order.getId(), order.getCustomerId(), order.getAmountInCents());
        
        try {
            String eventPayload = objectMapper.writeValueAsString(eventData);
            OutboxEvent outboxEvent = new OutboxEvent(
                    "ORDER",
                    order.getId().toString(),
                    "OrderCreated",
                    eventPayload
            );
            entityManager.persist(outboxEvent);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("Failed to serialize order event payload", e);
        }

        // Keduanya (order & outboxEvent) ter-commit bersamaan secara atomik dalam 1 DB Transaction
        return orderId;
    }
}
```

### 3. Outbox Publisher: Asynchronous Message Relay
```java
package com.enterprise.distributed.outbox;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import jakarta.persistence.EntityManager;

import java.util.List;

@Component
public class OutboxEventPublisher {

    private static final Logger log = LoggerFactory.getLogger(OutboxEventPublisher.class);
    private static final String TOPIC = "order-events";

    private final EntityManager entityManager;
    private final KafkaTemplate<String, String> kafkaTemplate;

    public OutboxEventPublisher(EntityManager entityManager, KafkaTemplate<String, String> kafkaTemplate) {
        this.entityManager = entityManager;
        this.kafkaTemplate = kafkaTemplate;
    }

    @Scheduled(fixedDelay = 2000)
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void publishPendingOutboxEvents() {
        List<OutboxEvent> pendingEvents = entityManager.createQuery(
                "SELECT o FROM OutboxEvent o WHERE o.status = :status ORDER BY o.createdAt ASC", 
                OutboxEvent.class)
                .setParameter("status", OutboxEvent.OutboxStatus.PENDING)
                .setMaxResults(50)
                .getResultList();

        for (OutboxEvent event : pendingEvents) {
            try {
                // Menjadikan aggregateId sebagai Kafka Record Key menjamin keterurutan partisi
                kafkaTemplate.send(TOPIC, event.getAggregateId(), event.getPayload())
                        .whenComplete((result, ex) -> {
                            if (ex == null) {
                                log.info("Successfully published outbox event ID: {}", event.getId());
                            } else {
                                log.error("Broker rejection for outbox ID: {}", event.getId(), ex);
                            }
                        });

                event.markAsPublished();
                entityManager.merge(event);
            } catch (Exception e) {
                log.error("Failed to forward outbox message ID: {}", event.getId(), e);
                // Biarkan status tetap PENDING agar diproses pada siklus berikutnya
            }
        }
    }
}
```

### 4. Consumer: Idempotent Event Processor
```java
package com.enterprise.distributed.consumer;

import jakarta.persistence.Entity;
import jakarta.persistence.EntityManager;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;

@Component
public class PaymentProcessingConsumer {

    private static final Logger log = LoggerFactory.getLogger(PaymentProcessingConsumer.class);
    private final EntityManager entityManager;

    public PaymentProcessingConsumer(EntityManager entityManager) {
        this.entityManager = entityManager;
    }

    @Entity
    @Table(name = "processed_messages")
    public static class ProcessedMessage {
        @Id
        private String messageKey;
        private Instant processedAt;

        protected ProcessedMessage() {}
        public ProcessedMessage(String messageKey) {
            this.messageKey = messageKey;
            this.processedAt = Instant.now();
        }
    }

    @KafkaListener(topics = "order-events", groupId = "payment-processor-group")
    @Transactional
    public void onOrderCreatedEvent(ConsumerRecord<String, String> record) {
        String deduplicationKey = "ORDER_EVENT_" + record.key();

        // 1. Cek & Simpan Kunci Idempoten Menggunakan Database Constraint
        try {
            ProcessedMessage marker = new ProcessedMessage(deduplicationKey);
            entityManager.persist(marker);
            entityManager.flush(); // Paksa flush untuk trigger Unique Key Constraint secara dini
        } catch (DataIntegrityViolationException e) {
            log.warn("Duplicated message intercepted! Key: {} already processed. Skipping operation.", deduplicationKey);
            return; // ACK pesan ke broker tanpa eksekusi ulang logika pembayaran
        }

        // 2. Eksekusi Business Logic Pembayaran Terdistribusi
        log.info("Processing unique financial debit for Aggregate ID: {}, Payload: {}", record.key(), record.value());
        // Lakukan eksekusi pemotongan saldo atau otorisasi kartu kredit di sini...
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Arsitektur Data Terdistribusi: ACID Tradisional vs Saga Pattern

| Matriks Komparasi | Two-Phase Commit (2PC / XA) | Saga Orchestration | Saga Choreography |
| :--- | :--- | :--- | :--- |
| **Konsistensi Data** | *Immediate Consistency* (Strict). | *Eventual Consistency*. | *Eventual Consistency*. |
| **Throughput & Skalabilitas** | **Sangat Rendah**. Latensi dibatasi oleh node terlambat karena global transaction lock. | **Tinggi**. Setiap DB lokal commit mandiri tanpa blocking lock global. | **Sangat Tinggi**. Fully decoupled event pipeline via Kafka cluster. |
| **Ketersediaan Jaringan** | Rentan (*Single Coordinator failure locks all resource managers*). | Tinggi. Orchestrator dapat melanjutkan state saat node bangkit. | Maksimum. Tidak ada coordinator terpusat. |
| **Kompleksitas Debugging** | Rendah (Database engine menangani rollback otomatis). | Menengah. Alur tersentralisasi di orchestrator definition. | Sangat Tinggi. Melacak eksekusi event butuh distributed tracing matang. |
| **Dampak Kegagalan** | Kunci database ditahan hingga batas waktu timeout transaksi habis. | Orchestrator mengeksekusi kompensasi balik terencana (*compensating tx*). | Setiap consumer wajib memprogram alur kompensasinya sendiri. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1.  **Zombie Service & Broken Leases pada Service Discovery:**
    Instans mikroservis mengalami garbage collection pause yang ekstrem (Full GC *Stop-The-World* > 30 detik). Service discovery mengira instans telah mati dan mencopotnya dari registry. Namun JVM instans tersebut kemudian melanjutkan eksekusi dan memproses request lama yang seharusnya sudah dibatalkan atau dialihkan ke instans lain.
    *Mitigasi:* Gunakan short lease timeouts, implementasikan fencing tokens pada distributed resource lock.
2.  **Outbox Table Bloat (Poller Degradation):**
    Saat throughput mencapai puluhan juta event per hari, ukuran tabel `outbox_events` membengkak drastis. Eksekusi polling `SELECT ... WHERE status = 'PENDING'` mengalami degradasi eksponensial karena *index scan overhead*.
    *Mitigasi:* Terapkan partisi tabel (*Table Partitioning*) berdasarkan rentang waktu harian pada PostgreSQL, atau beralih sepenuhnya ke Change Data Capture (Debezium Engine) berbasis log write-ahead (`pg_wal`).
3.  **Poison Pill Messages pada Messaging Broker:**
    Pesan serialisasi rusak atau memiliki struktur data yang tidak dapat diuraikan oleh consumer. Akibatnya: Consumer crash, Kafka melakukan rebalance, partisi dialihkan ke thread/node lain, node baru mencoba parsing dan crash kembali (*infinite restart crash loop*).
    *Mitigasi:* Bungkus consumer dengan `ErrorHandlingDeserializer` dan Dead Letter Queue (DLQ) strategy dengan parameter max redelivery count.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. The Distributed Exception Leak Anti-Pattern
```java
// KESALAHAN UMUM:
public OrderResponse callOrderService() {
    try {
        return restTemplate.getForObject("http://order-service/orders/1", OrderResponse.class);
    } catch (Exception e) {
        // MENGABAIKAN ATAU MELEMPAR ULANG TANPA MEMBEDAKAN PENYEBABNYA
        throw new RuntimeException("Call failed", e); 
    }
}
```
**Mengapa Keliru?** Aplikasi tidak membedakan antara *client timeout* (TCP syn-sent timeout), *remote server error* (500), atau *bad request* (400). Mengaktifkan circuit breaker pada respons HTTP 400 (bad user request) akan menutup circuit secara keliru untuk seluruh user yang valid.
**Solusi Benar:** Klasifikasikan exception secara eksplisit. Abaikan `HttpClientErrorException` (4xx) dari sliding window metrics circuit breaker.

### 2. Memanggil Remote Service di Dalam Transaksi Database Lokal
```java
// KESALAHAN FATAL:
@Transactional
public void processOrder(OrderCmd cmd) {
    Order order = orderRepository.save(new Order(cmd)); // Mengambil koneksi DB dari HikariCP
    
    // NETWORK CALL DI TENGAH-TENGAH TRANSAKSI ACID
    paymentGatewayClient.charge(order.getAmount()); 
    
    order.markAsPaid();
}
```
**Mengapa Keliru?** Koneksi JDBC ditahan (*held open*) selama pemanggilan jaringan berlangsung ($100\text{ms} - 3000\text{ms}$). Dalam kondisi traffic padat, seluruh pool HikariCP akan terkuras habis (*pool starvation*), mematikan seluruh operasi database aplikasi monolitik maupun microservices.
**Solusi Benar:** Selesaikan transaksi database lokal secepat mungkin ($< 5\text{ms}$), lalu lakukan network call di luar batas `@Transactional`.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Consumer-Driven Contracts (Pact Testing):** Jangan mengandalkan integrasi runtime untuk mendeteksi breaking changes pada skema payload JSON antar-tim. Wajibkan penggunaan pengujian kontrak otomatis via Pact atau Spring Cloud Contract pada CI/CD pipeline.
2.  **Graceful Shutdown & Liveness/Readiness Probes:** Konfigurasikan Spring Boot dengan `server.shutdown=graceful`. Saat menerima sinyal `SIGTERM`, kontainer harus segera mengembalikan status `Readiness = OUT_OF_SERVICE` agar Kubernetes melepaskannya dari Ingress pool, dan menunggu durasi toleransi (misalnya 20 detik) untuk menyelesaikan request in-flight sebelum memutus JVM process.
3.  **Distributed Trace ID Injection pada Mapped Diagnostic Context (MDC):** Setiap log statement wajib memuat `trace_id` dan `span_id` secara terstruktur:
    ```
    {"timestamp":"2026-03-30T10:00:00Z","level":"INFO","trace_id":"4bf92f3577b34da6a3ce929d0e0e4736","span_id":"00f067aa0ba902b7","message":"Order validated successfully"}
    ```

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Migrasi ke Virtual Threads (Project Loom) pada I/O Bound Microservices
Pada Java 21 dan Spring Boot 3.2+, aktifkan virtual threads via konfigurasi:
```properties
spring.threads.virtual.enabled=true
```
Virtual thread melepaskan thread platform operasi (OS thread) saat eksekusi mengalami pemblokiran jaringan (misalnya menunggu parsing response HTTP atau I/O JDBC). 

*Peringatan Keras Rekayasa:* Hindari penggunaan blok `synchronized` yang membalut pemanggilan I/O terdistribusi, karena hal ini menyebabkan *carrier thread pinning* yang melumpuhkan kemampuan scheduling dari ForkJoinPool milik Virtual Thread. Gantilah secara ketat dengan `java.util.concurrent.locks.ReentrantLock`.

### 2. Tuning Klien HTTP Terdistribusi (Apache HttpClient 5 / HTTP/2)
Hindari inisialisasi client baru pada setiap request. Terapkan connection pooling persisten:
```java
PoolingHttpClientConnectionManager connectionManager = PoolingHttpClientConnectionManagerBuilder.create()
        .setMaxConnTotal(500)
        .setMaxConnPerRoute(100)
        .setDefaultSocketConfig(SocketConfig.custom().setSoTimeout(Timeout.ofMilliseconds(2000)).build())
        .build();
```

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Zero-Trust mTLS & Header Identity Propagation
Mikroservis tidak boleh memercayai koneksi jaringan internal hanya karena berada di dalam satu virtual private cloud (VPC). Setiap komunikasi service-to-service wajib diamankan dengan **mutual TLS (mTLS)** untuk otentikasi identitas dua arah.

### 2. JWT Cryptographic Verification Context
Saat API Gateway menerima JWT dari user, gateway melakukan validasi signature dan mengekstrak claim. Gateway meneruskan *sanitized internal header* (`X-User-Id`, `X-User-Roles`) ke internal microservice. Microservice downstream tidak boleh memercayai header mentah dari publik tanpa validasi cryptographic context atau shared identity assertion token:

```java
package com.enterprise.distributed.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpStatus;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

public class InternalSecurityFilter extends OncePerRequestFilter {

    private final String expectedInternalSecret;

    public InternalSecurityFilter(String expectedInternalSecret) {
        this.expectedInternalSecret = expectedInternalSecret;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, 
                                    HttpServletResponse response, 
                                    FilterChain filterChain) throws ServletException, IOException {
        
        String authHeader = request.getHeader("X-Internal-Service-Auth");
        if (authHeader == null || !authHeader.equals(expectedInternalSecret)) {
            response.sendError(HttpStatus.FORBIDDEN.value(), "Direct internal microservice invocation forbidden");
            return;
        }

        filterChain.doFilter(request, response);
    }
}
```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Integrasikan distributed tracing secara native dengan Spring Boot 3 Actuator dan OpenTelemetry.

### Konfigurasi `application.yml`
```yaml
management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
  tracing:
    sampling:
      probability: 1.0 # 100% trace capture untuk non-production profiling
  zipkin:
    tracing:
      endpoint: http://otel-collector.internal:9411/api/v2/spans
logging:
  pattern:
    level: "%5p [${spring.application.name:},%X{traceId:-},%X{spanId:-}]"
```

### Manual Custom Tracing Annotation Implementation
```java
package com.enterprise.distributed.observability;

import io.micrometer.tracing.Span;
import io.micrometer.tracing.Tracer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.function.Supplier;

@Component
public class TraceableExecutor {

    private static final Logger log = LoggerFactory.getLogger(TraceableExecutor.class);
    private final Tracer tracer;

    public TraceableExecutor(Tracer tracer) {
        this.tracer = tracer;
    }

    public <T> T executeWithSpan(String spanName, Supplier<T> operation) {
        Span newSpan = this.tracer.nextSpan().name(spanName).start();
        try (Tracer.SpanInScope ws = this.tracer.withSpan(newSpan.start())) {
            log.info("Starting traced operation: {}", spanName);
            newSpan.tag("execution.type", "business-critical");
            return operation.get();
        } catch (Exception e) {
            newSpan.error(e);
            newSpan.tag("error.message", e.getMessage());
            throw e;
        } finally {
            newSpan.end();
            log.info("Finalized span: {}", spanName);
        }
    }
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```
+───────────────────────+──────────────────────────────────+─────────────────────────────────────────────+
| POLA DISTRIBUSI       | TUJUAN ARSITEKTUR                | SOLUSI TEKNOLOGI JAVA/SPRING                |
+───────────────────────+──────────────────────────────────+─────────────────────────────────────────────+
| Circuit Breaker       | Mencegah cascading failure       | Resilience4j (Sliding Window, Count/Time)   |
| Transactional Outbox  | Menghindari Dual-Write Problem   | JPA Local Transaction + Kafka Poller / CDC  |
| Idempotent Consumer   | Mengatasi duplikasi pesan        | Deduplication Key via DB / Redis Unique Key |
| Distributed Tracing   | Mengidentifikasi bottleneck hop  | Micrometer Tracing + W3C Trace Context      |
| Virtual Threads       | Throughput I/O maksimal          | Java 21 LTS (`spring.threads.virtual=true`) |
| Saga Pattern          | Konsistensi lintas bounded ctx   | Event-Driven Choreography atau Camunda/Temporal
+───────────────────────+──────────────────────────────────+─────────────────────────────────────────────+
```

*   **Penyebab Kegagalan Terdistribusi Utama:** Jaringan tidak deterministik; timeout adalah kondisi ambigu (bukan penanda pasti operasi gagal).
*   **Golden Rule:** Jangan pernah melakukan call jaringan di dalam deklarasi `@Transactional` database lokal.
*   **Idempotensi:** Semua API non-GET wajib didesain aman terhadap *repeated call* dengan payload identik.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Bagian 1: Basic Scenarios

1. **Apa bahaya utama dari arsitektur yang melakukan penulisan database lokal dan pengiriman event Apache Kafka secara berturut-turut dalam satu method dengan anotasi `@Transactional` standar?**
   * A. Transaksi Kafka akan memperlambat koneksi JDBC secara otomatis.
   * B. Transaksi komit database lokal tidak menjamin event berhasil terkirim ke broker jika jaringan putus di tengah eksekusi (*The Dual-Write Problem*).
   * C. Kafka tidak mendukung payload berupa format data JSON.
   * D. Anotasi `@Transactional` secara otomatis mengonversi transaksi Kafka menjadi Two-Phase Commit.
   * *Jawaban:* **B**
   * *Rasional:* Kafka template tidak berpartisipasi dalam JDBC Transaction Manager lokal. Jika broker down sesaat setelah JDBC commit, event hilang permanen sementara data DB tersimpan.

2. **Mengapa *Exponential Backoff* sangat penting dalam konfigurasi Retry Pattern sistem terdistribusi?**
   * A. Untuk menghemat alokasi memori heap JVM.
   * B. Untuk membatasi ukuran packet frame pada protokol TCP.
   * C. Untuk mencegah efek *Thundering Herd* yang membanjiri downstream service yang baru saja pulih.
   * D. Karena algoritma linear backoff dilarang oleh standar HTTP/2.
   * *Jawaban:* **C**
   * *Rasional:* Jika ribuan klien melakukan retry serentak pada interval waktu yang sama persis, lonjakan trafik (*thundering herd*) akan kembali merusak server target yang sedang berusaha pulih.

3. **Komponen apa dalam format header W3C `traceparent` (`00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`) yang bertindak sebagai pengidentifikasi unik transaksi dari ujung ke ujung?**
   * A. `00`
   * B. `4bf92f3577b34da6a3ce929d0e0e4736`
   * C. `00f067aa0ba902b7`
   * D. `01`
   * *Jawaban:* **B**
   * *Rasional:* 32 karakter heksadesimal kedua merupakan `trace_id` yang konsisten di semua log mikroservis untuk siklus request yang sama. Bagian ketiga adalah `parent_id` (span id).

4. **Bagaimana status internal Resilience4j Circuit Breaker ketika mengevaluasi pemulihan sistem target menggunakan sejumlah kecil traffic uji coba?**
   * A. `OPEN`
   * B. `PENDING`
   * C. `HALF-OPEN`
   * D. `DISABLED`
   * *Jawaban:* **C**
   * *Rasional:* Pada state `HALF-OPEN`, circuit breaker mengizinkan sejumlah limited request uji coba (`permittedNumberOfCallsInHalfOpenState`) untuk mengecek apakah failure rate sudah berada di bawah threshold normal.

5. **Apa fungsi utama dari database constraint (misal: Primary Key / Unique Index) pada implementasi Consumer Idempoten?**
   * A. Mempercepat eksekusi query JPA mapping.
   * B. Memastikan pesan yang sama tidak diproses dua kali secara paralel maupun serial dengan memanfaatkan garansi atomisitas ACID database engine.
   * C. Menghindari kebutuhan indexing pada tabel transaksi bisnis utama.
   * D. Mengurangi konsumsi CPU broker Kafka saat partisi rebalance.
   * *Jawaban:* **B**
   * *Rasional:* Database constraint adalah mekanisme deterministik paling andal untuk menolak duplikasi key secara atomik ketika dua thread consumer memproses pesan duplikat secara paralel.

---

### Bagian 2: Intermediate Architectural Scenarios

6. **Sebuah service A memanggil service B via HTTP. Terjadi socket read timeout setelah 3000ms. Apa kesimpulan teknis yang valid tentang status transaksi pada Service B?**
   * A. Transaksi pada Service B pasti gagal dieksekusi.
   * B. Transaksi pada Service B pasti berhasil tetapi respon HTTP hilang di jalan.
   * C. Status transaksi pada Service B tidak dapat ditentukan (*Indeterminate/Unknown*): bisa belum dieksekusi, sedang berjalan, atau sudah selesai.
   * D. Database Service B secara otomatis melakukan rollback saat membaca event socket hangup.
   * *Jawaban:* **C**
   * *Rasional:* Timeout terjadi pada boundary client. Client tidak mengetahui apakah data request sampai ke server, atau server sudah selesai memproses dan baru mengalami kegagalan saat transmisi respon balik.

7. **Pada Spring Boot 3.2+ yang berjalan di atas Java 21, mengapa penggunaan blok `synchronized` yang membungkus pemanggilan I/O eksternal berbahaya saat mengaktifkan Virtual Threads?**
   * A. Menimbulkan exception `IllegalMonitorStateException` seketika.
   * B. Terjadi *Carrier Thread Pinning*, di mana Virtual Thread menempel secara permanen pada Carrier OS Thread dan mencegah thread unmounting selama I/O blocking.
   * C. Garbage collection dipaksa berhenti total (*Permanent JVM freeze*).
   * D. Virtual thread scheduler tidak mendukung multithreading.
   * *Jawaban:* **B**
   * *Rasional:* Keyword `synchronized` saat ini mengunci underlying OS carrier thread (*pinning*). Jika I/O lambat, carrier thread terblokir dan performa sistem terdegradasi ke level platform thread konvensional. Gunakan `ReentrantLock`.

8. **Manakah dari strategi berikut yang paling efektif untuk memecahkan masalah keusangan data (*data staleness*) pada arsitektur CQRS (Command Query Responsibility Segregation)?**
   * A. Memaksa Read Model melakukan direct lock pada Write Model database.
   * B. Menghindari arsitektur CQRS sama sekali jika query memerlukan konsistensi baca.
   * C. Mengembalikan versi revisi agregat (*Aggregate Version*) pada Command response, dan Query Client menunggu polling lokal hingga Read Store mencapai minimal versi tersebut (*Read-your-own-writes consistency*).
   * D. Menyetel sync replication secara hard-blocking pada Kafka broker.
   * *Jawaban:* **C**
   * *Rasional:* Pola version checking memungkinkan sistem eventual consistency memberikan garansi "Read-your-own-writes" bagi user interaktif tanpa memberlakukan global lock terdistribusi.

9. **Mengapa pattern Two-Phase Commit (2PC / XA Transactions) dihindari secara luas pada arsitektur mikroservis modern skala tinggi?**
   * A. Protokol 2PC tidak didukung oleh database relasional modern seperti PostgreSQL.
   * B. Protokol 2PC adalah arsitektur non-blocking yang menyebabkan inkonsistensi memori.
   * C. 2PC merupakan protokol sinkron yang sangat rapuh terhadap partisi jaringan, menahan resource locks dalam durasi lama, dan performa dibatasi oleh node terlemah (hukum Amdahl).
   * D. 2PC mewajibkan seluruh microservices memakai source code Java yang sama.
   * *Jawaban:* **C**
   * *Rasional:* 2PC menahan database lock selama fase "Prepare" hingga "Commit". Satu node yang lambat atau putus jaringan akan memblokir pelepasan lock di seluruh node lain, menghancurkan ketersediaan dan latensi sistem.

10. **Bagaimana mitigasi terbaik jika Transactional Outbox Pattern menggunakan database polling reguler menyebabkan beban I/O query yang tinggi pada database relasional utama?**
    * A. Menghapus tabel Outbox dan kembali melakukan direct Kafka emit di controller.
    * B. Mengalihkan mekanisme polling berbasis SQL interval ke Log-based Change Data Capture (CDC) menggunakan tools seperti Debezium yang membaca transaction log database (WAL/Binlog).
    * C. Mengurangi thread worker polling menjadi 1 thread per hari.
    * D. Menjalankan query polling tanpa index database.
    * *Jawaban:* **B**
    * *Rasional:* CDC membaca write-ahead log (WAL) database secara asinkron tanpa mengeksekusi kueri `SELECT ... FOR UPDATE` reguler pada tabel database, menghilangkan query overhead secara total terhadap engine relasional.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: "Resilient Distributed Order-Inventory Saga Engine"

#### Deskripsi Skenario
Rancang dan bangun arsitektur mikroservis mandiri menggunakan Java 21 dan Spring Boot 3 yang mengimplementasikan **Choreography-based Saga** antara dua servis terpisah: `Order-Service` dan `Inventory-Service`, menggunakan Apache Kafka sebagai transport message.

```
       ORDER-SERVICE                          KAFKA                        INVENTORY-SERVICE
  +─────────────────────+              +─────────────────+              +─────────────────────+
  |  POST /orders       |              |                 |              |                     |
  |  (Reserve Order)    |              |                 |              |                     |
  |         │           |              |                 |              |                     |
  |         ▼           |              |                 |              |                     |
  |  Insert Local DB &  |              |                 |              |                     |
  |  Transactional      |── Emit ─────▶|  order-created  |───── Consume▶|  Deduplicate &      |
  |  Outbox Event       |              |                 |              |  Check Stock        |
  |                     |              +─────────────────+              |         │           |
  |                     |                                               |         ├── Success ──┐
  |                     |              +─────────────────+              |         │             │
  |  Update Order to    |◀── Consume ──| inventory-status|◀──── Emit ───┴─────────┴── Failed ──┘
  |  CONFIRMED / FAILED |              +─────────────────+
  +─────────────────────+
```

#### Spesifikasi Fungsional:
1.  **Layanan `Order-Service`:**
    *   Endpoint `POST /api/v1/orders` menerima request order, menyimpan transaksi order berstatus `PENDING`, dan mencatat event `OrderCreated` ke tabel Outbox dalam satu transaksi basis data lokal.
    *   Outbox processor mempublikasikan event tersebut ke topic Kafka `order-created`.
2.  **Layanan `Inventory-Service`:**
    *   Mendengarkan topic `order-created`.
    *   Menerapkan tabel `processed_messages` untuk deduplikasi mutlak.
    *   Memeriksa stok barang pada database inventaris:
        *   Jika stok mencukupi: Kurangi stok, kirim event `InventoryReserved` ke topic `inventory-status`.
        *   Jika stok tidak mencukupi: Kirim event `InventoryReservationFailed` ke topic `inventory-status`.
3.  **Kompensasi pada `Order-Service`:**
    *   Mendengarkan topic `inventory-status`.
    *   Jika status `InventoryReserved`: Perbarui status order menjadi `CONFIRMED`.
    *   Jika status `InventoryReservationFailed`: Perbarui status order menjadi `REJECTED_OUT_OF_STOCK` (Kompensasi lokal).
4.  **Resilience4j Challenge:**
    *   Bungkus pemanggilan downstream atau database I/O dengan Circuit Breaker dan Retry.
    *   Uji ketahanan dengan mematikan node Kafka/DB secara sengaja (*chaos testing*), lalu buktikan data kembali konsisten tanpa intervensi manual setelah node hidup kembali.

#### Syarat Kelulusan Kode (Acceptance Criteria):
*   Zero Dual-Write: Tidak ada pemanggilan Kafka template yang dibalut satu transaksi langsung dengan domain order table.
*   Zero Idempotency Leak: Injeksi 10 pesan Kafka yang identik secara manual hanya mengeksekusi pemotongan inventaris tepat 1 kali.
*   Log telemetri menampilkan `traceId` yang sama persis dari thread `Order-Service` awal hingga log final di `Inventory-Service`.
*   Tidak ada penggunaan `Thread.sleep()` untuk kontrol sinkronisasi; seluruh koordinasi bersifat non-blocking event-driven.