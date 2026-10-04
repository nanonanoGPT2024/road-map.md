# Kurikulum Enterprise Java: BAB-07 Enterprise Microservices & Distributed Systems
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Mendiagnosis dan mengeliminasi masalah *Dual-Write* pada sistem terdistribusi menggunakan **Transactional Outbox Pattern** berbasis Change Data Capture (CDC) Debezium dan Apache Kafka.
- Mengimplementasikan **Saga Orchestration Pattern** dengan *Compensating Transactions* yang *resilient* dan *idempotent* menggunakan Java 21, Spring Boot 3.x, dan Spring State Machine/Temporal.
- Mengonfigurasi isolasi kesalahan tingkat lanjut (*Fault Tolerance*) menggunakan **Resilience4j** (Circuit Breaker, Rate Limiter, Bulkhead) yang diintegrasikan dengan *Virtual Threads* (Project Loom).
- Mengintegrasikan pelacakan terdistribusi (*Distributed Tracing*) *end-to-end* menggunakan **OpenTelemetry (OTel)** dan Micrometer Tracing yang mematuhi standar W3C TraceContext melalui Kafka Headers dan HTTP calls.
- Merancang arsitektur microservices *production-grade* yang tahan terhadap kegagalan jaringan (*split-brain*, *network partitions*, dan *poison-pill messages*).

---

### 2. Prerequisite
- **Java Platform:** Java Development Kit (JDK) 21 LTS (penguasaan mendalam atas *Records*, *Pattern Matching*, dan *Virtual Threads*).
- **Frameworks:** Spring Boot 3.2+ / Quarkus 3.x, Spring Data JPA, Spring Kafka.
- **Infrastruktur Terdistribusi:** Docker & Docker Compose, Apache Kafka 3.6+ (KRaft mode), PostgreSQL 16+.
- **Konsep:** Pemahaman teorema CAP/PACELC, ACID vs BASE, messaging semantics (*at-least-once*, *at-most-once*, *exactly-once*).

---

### 3. Concept & Internal Architecture

#### A. Anatomi Dual-Write Problem & Transactional Outbox Pattern
Masalah mendasar dalam sistem terdistribusi adalah ketidakmampuan database relasional (RDBMS) dan *Message Broker* (Kafka) untuk berpartisipasi dalam satu transaksi atomik lokal tanpa menggunakan protokol *Two-Phase Commit* (2PC) yang lambat dan memblokir thread (*locking*).

```
[Anti-Pattern: Naive Dual-Write]
Client ---> [Microservice API]
                 |
                 +---> 1. DB.save(Order) [COMMIT OK]
                 |
                 +---> 2. Kafka.send(OrderCreatedEvent) [NETWORK FAILS / BROKER DOWN]
```
Jika langkah 2 gagal, state antara DB dan Broker mengalami *desynchronization*. 

**Solusi Arsitektur: Transactional Outbox**
State mutasi domain dan event integrasi ditulis ke dalam unit transaksi basis data yang sama secara atomik (ACID):
1. Transaksi lokal mengeksekusi mutasi tabel bisnis (misal: `orders`) dan menulis *payload* event ke dalam tabel `outbox`.
2. Mesin *Change Data Capture* (Debezium Engine) membaca Postgres Write-Ahead Log (WAL) melalui *Logical Replication Stream* dan meneruskannya ke Kafka secara asinkron tanpa membebani thread aplikasi.

```
[Production Outbox via CDC]
[Application Service]
    │  BEGIN TRANSACTION
    ├──> INSERT INTO orders (...)
    └──> INSERT INTO outbox_events (id, aggregate_type, aggregate_id, payload, ...)
       COMMIT TRANSACTION
             │
      [Postgres WAL] (Write-Ahead Log)
             │
      [Debezium CDC Connector] (Reads WAL via pgoutput)
             │
      [Apache Kafka] (Distributed Event Backbone)
```

#### B. Saga Orchestration vs. Choreography
Pada sistem skala enterprise dengan alur kerja yang kompleks, *Choreography* sering kali menjadi *anti-pattern* yang menghasilkan "Event Spaghetti" di mana siklus *dependency* sulit dilacak dan tidak ada *single source of truth* untuk status proses bisnis global. 

*Saga Orchestration* memusatkan logika alur transaksi pada satu komponen pengendali (*Orchestrator*):
- Mengirimkan *command* ke *participating services*.
- Menunggu *event* balasan.
- Mengeksekusi *compensating transaction* (transaksi kompensasi balik) jika terjadi kegagalan fatal pada langkah mana pun untuk mencapai status *eventual consistency*.

#### C. Integrasi Project Loom (Virtual Threads) dan Distributed Systems
Java 21 membawa *Virtual Threads* (JEP 444). Dalam arsitektur microservices:
- Pemanggilan I/O terdistribusi (HTTP/gRPC/R2DBC) yang memblokir tidak lagi mengonsumsi *OS-level platform thread*.
- JVM melepaskan (*unmount*) Virtual Thread dari *Carrier Thread* saat operasi I/O terblokir, memungkinkan satu instans microservice menangani puluhan ribu panggilan jaringan simultan tanpa *thread pool exhaustion*.
- **Peringatan Produksi:** Hindari `synchronized` block di sekitar I/O terdistribusi untuk mencegah *Thread Pinning*. Gunakan `java.util.concurrent.locks.ReentrantLock`.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional | Pendekatan Enterprise Produksi |
| :--- | :--- | :--- |
| **Konsistensi Transaksi** | Two-Phase Commit (XA Transactions) | Saga Pattern + Transactional Outbox (BASE) |
| **Konektivitas Service** | Sinkronus (REST over HTTP) terus-menerus | *Smart Endpoints*: Async Event-Driven + gRPC untuk mutasi internal |
| **Isolasi Kegagalan** | Retry naif tanpa batas / No Circuit Breaker | Resilience4j: Adaptive Circuit Breaking + Distributed Bulkhead |
| **Tracing** | Log terisolasi per-service (MDC lokal) | OpenTelemetry Distributed Context Propagation (W3C standard) |
| **Concurreny Model** | Platform Thread per Request (Tomcat Default) | Virtual Threads (Java 21) dengan Work-Stealing ForkJoinPool |

---

### 5. How (Workflow Detail)

Alur transaksi pesanan (*Order Fulfillment Flow*) terdistribusi:

```
[Order Service]         [Outbox Table]     [Debezium / Kafka]      [Payment Service]       [Inventory Service]
       │                       │                   │                       │                       │
 1. Create Pending Order       │                   │                       │                       │
 2. Insert Outbox Event ──────>│                   │                       │                       │
    (COMMIT LOCAL TX)          │                   │                       │                       │
                               │── 3. Read WAL ───>│                       │                       │
                                                   │── 4. Consume Cmd ────>│                       │
                                                   │                       │ 5. Process Payment    │
                                                   │<─ 6. Payment Success ─│                       │
                                                   │                                               │
                                                   │── 7. Reserve Stock ──────────────────────────>│
                                                   │                                               │ 8. Out of Stock!
                                                   │<─ 9. Stock Allocation Failed ─────────────────│
                                                   │
 10. Consume Failure Event <───────────────────────│
 11. Trigger Compensation:
     - Cancel Order Locally
     - Send Refund Command ───────────────────────>│
                                                   │ 12. Execute Refund (Compensate)
```

1. **Inisiasi:** `Order Service` menerima pesanan, menyimpan `Order` dengan status `PENDING`, dan menulis event `OrderCreated` ke tabel `outbox_events` dalam satu transaksi ACID lokal.
2. **Streaming:** Debezium mengekstrak event dari WAL PostgreSQL dan mengirimkannya ke topik `order-events` di Kafka.
3. **Orchestrator Execution:** Orchestrator mengonsumsi event, kemudian memanggil `Payment Service` melalui Kafka command topic.
4. **Kondisi Sukses & Kompensasi:** Jika `Payment Service` berhasil memotong saldo namun `Inventory Service` gagal mengalokasikan stok (stok habis):
    - `Inventory Service` memublikasikan event `InventoryAllocationFailed`.
    - Saga Orchestrator menangkap kegagalan tersebut dan memicu *compensating transaction*:
        - Mengirim event `RefundPaymentCommand` ke `Payment Service`.
        - Memperbarui status pesanan lokal menjadi `FAILED_OUT_OF_STOCK`.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Agen Perjalanan Wisata (Saga Orchestration)
Bayangkan Anda memesan paket liburan melalui Agen Perjalanan:
1. Agen memesan tiket pesawat (Langkah 1: Berhasil).
2. Agen memesan kamar hotel (Langkah 2: Gagal, hotel penuh).
3. Agen tidak membiarkan Anda memegang tiket pesawat tanpa hotel. Agen secara otomatis menghubungi maskapai untuk membatalkan tiket pesawat dan meminta pengembalian dana (*Kompensasi*). Anda tidak pernah berada dalam kondisi setengah terpesan.

#### Arsitektur Transactional Outbox + Event Stream

```
+-----------------------------------------------------------------------------------------+
| MICROSERVICE BOUNDARY                                                                   |
|                                                                                         |
|  [ HTTP POST ]                                                                          |
|       │                                                                                 |
|       ▼                                                                                 |
|  [Spring Controller] ── (Virtual Thread)                                                |
|       │                                                                                 |
|       ▼                                                                                 |
|  [Order Service Layer]                                                                  |
|       │                                                                                 |
|       +--- (Local ACID Transaction) --------------------------------+                   |
|       │                                                             │                   |
|       ▼                                                             ▼                   |
|  [Tabel: orders]                                           [Tabel: outbox_events]       |
|  ├─ id: UUID                                               ├─ id: UUID                  |
|  ├─ status: PENDING                                        ├─ aggregate_type: ORDER     |
|  └─ amount: 1500000                                        ├─ payload: JSONB            |
|                                                            └─ status: UNPROCESSED       |
+-------------------------------------------------------------------------│---------------+
                                                                          │ (DB WAL Engine)
                                                                          ▼
                                                             [PostgreSQL Write-Ahead Log]
                                                                          │
                                                                          │ (CDC Streaming)
                                                                          ▼
                                                             [Debezium Kafka Connector]
                                                                          │
                                                                          ▼
                                                             [Kafka Broker: orders.events]
```

---

### 7. Simple Example & Practical Example

#### A. Entitas Domain & Outbox Event (Java 21)

```java
package com.enterprise.order.domain;

import jakarta.persistence.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "orders")
public class Order {
    @Id
    private UUID id;
    
    @Column(nullable = false)
    private UUID customerId;

    @Column(nullable = false)
    private BigDecimal totalAmount;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private OrderStatus status;

    protected Order() {} // JPA Requirement

    public Order(UUID customerId, BigDecimal totalAmount) {
        this.id = UUID.randomUUID();
        this.customerId = customerId;
        this.totalAmount = totalAmount;
        this.status = OrderStatus.PENDING;
    }

    public void markAsFailed() {
        this.status = OrderStatus.FAILED;
    }

    public void markAsCompleted() {
        this.status = OrderStatus.COMPLETED;
    }

    // Getters omitted for brevity
    public UUID getId() { return id; }
    public BigDecimal getTotalAmount() { return totalAmount; }
    public OrderStatus getStatus() { return status; }
}

enum OrderStatus {
    PENDING, COMPLETED, FAILED
}
```

```java
package com.enterprise.order.domain;

import jakarta.persistence.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;
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

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb", nullable = false)
    private String payload;

    @Column(nullable = false)
    private Instant createdAt;

    protected OutboxEvent() {}

    public OutboxEvent(String aggregateType, String aggregateId, String type, String payload) {
        this.id = UUID.randomUUID();
        this.aggregateType = aggregateType;
        this.aggregateId = aggregateId;
        this.type = type;
        this.payload = payload;
        this.createdAt = Instant.now();
    }

    public UUID getId() { return id; }
    public String getPayload() { return payload; }
}
```

#### B. Service Layer Mengimplementasikan Transactional Outbox

```java
package com.enterprise.order.service;

import com.enterprise.order.domain.Order;
import com.enterprise.order.domain.OutboxEvent;
import com.enterprise.order.repository.OrderRepository;
import com.enterprise.order.repository.OutboxRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.UUID;

@Service
public class OrderApplicationService {

    private final OrderRepository orderRepository;
    private final OutboxRepository outboxRepository;
    private final ObjectMapper objectMapper;

    public OrderApplicationService(OrderRepository orderRepository, 
                                   OutboxRepository outboxRepository, 
                                   ObjectMapper objectMapper) {
        this.orderRepository = orderRepository;
        this.outboxRepository = outboxRepository;
        this.objectMapper = objectMapper;
    }

    public record CreateOrderCommand(UUID customerId, BigDecimal amount) {}
    public record OrderCreatedPayload(UUID orderId, UUID customerId, BigDecimal amount) {}

    @Transactional(isolation = Isolation.READ_COMMITTED)
    public UUID handleCreateOrder(CreateOrderCommand cmd) {
        // 1. Mutasi Bisnis Domain
        Order order = new Order(cmd.customerId(), cmd.amount());
        orderRepository.save(order);

        // 2. Siapkan Event Integrasi
        OrderCreatedPayload eventPayload = new OrderCreatedPayload(
                order.getId(),
                cmd.customerId(),
                order.getTotalAmount()
        );

        try {
            String jsonPayload = objectMapper.writeValueAsString(eventPayload);
            OutboxEvent outboxEvent = new OutboxEvent(
                    "ORDER",
                    order.getId().toString(),
                    "OrderCreated",
                    jsonPayload
            );
            
            // 3. Simpan ke Outbox dalam Transaksi DB yang SAMA
            outboxRepository.save(outboxEvent);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("Gagal melakukan serialisasi payload event outbox", e);
        }

        return order.getId();
    }
}
```

#### C. Idempotent Kafka Consumer dengan Distributed Tracing Context Propagation

```java
package com.enterprise.payment.consumer;

import io.micrometer.tracing.Tracer;
import io.opentelemetry.api.trace.Span;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.UUID;

@Component
public class PaymentCommandConsumer {

    private static final Logger log = LoggerFactory.getLogger(PaymentCommandConsumer.class);
    private final JdbcClient jdbcClient;
    private final Tracer tracer;

    public PaymentCommandConsumer(JdbcClient jdbcClient, Tracer tracer) {
        this.jdbcClient = jdbcClient;
        this.tracer = tracer;
    }

    @KafkaListener(topics = "order-events", groupId = "payment-group", containerFactory = "kafkaListenerContainerFactory")
    @Transactional
    public void consume(ConsumerRecord<String, String> record, Acknowledgment ack) {
        String eventId = record.key(); // Asumsikan Key adalah Message UUID
        String payload = record.value();
        
        String traceId = tracer.currentSpan() != null ? 
                         tracer.currentSpan().context().traceId() : "no-trace";

        log.info("Memproses event konsumsi. EventId: {}, TraceId: {}", eventId, traceId);

        // Mekanisme Idempotensi Menggunakan Deduplication Table di Postgres
        try {
            int inserted = jdbcClient.sql("""
                    INSERT INTO processed_messages (message_id, handler_name, processed_at)
                    VALUES (:id, :handler, :processedAt)
                    ON CONFLICT (message_id) DO NOTHING
                    """)
                    .param("id", UUID.fromString(eventId))
                    .param("handler", "PaymentCommandConsumer")
                    .param("processedAt", Instant.now())
                    .update();

            if (inserted == 0) {
                log.warn("Duplikasi terdeteksi! EventId: {} sudah pernah diproses. Melewati eksekusi.", eventId);
                ack.acknowledge();
                return;
            }

            // Eksekusi Logika Bisnis Nyata (Mutasi Finansial)
            executePaymentLogic(payload);

            // Commit manual acknowledgment setelah penulisan DB berhasil
            ack.acknowledge();
            log.info("EventId: {} berhasil diproses dan di-acknowledge.", eventId);

        } catch (Exception e) {
            log.error("Kegagalan memproses EventId: {}. Pesan akan di-retry sesuai Redelivery Policy.", eventId, e);
            throw new RuntimeException("Triggering Kafka backoff retry", e);
        }
    }

    private void executePaymentLogic(String payload) {
        // Simulasi eksekusi pembayaran ke payment gateway
        log.info("Menjalankan debet dana transaksi: {}", payload);
    }
}
```

#### D. Production-Grade Resilience4j Configuration (Resilience + Virtual Threads)

```java
package com.enterprise.common.config;

import io.github.resilience4j.circuitbreaker.CircuitBreakerConfig;
import io.github.resilience4j.timelimiter.TimeLimiterConfig;
import org.springframework.cloud.circuitbreaker.resilience4j.Resilience4JCircuitBreakerFactory;
import org.springframework.cloud.circuitbreaker.resilience4j.Resilience4JConfigBuilder;
import org.springframework.cloud.client.circuitbreaker.Customizer;
import org.springframework.