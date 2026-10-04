# Bab 07 Module 01: Event-Driven Architecture & Enterprise Messaging

---

## 01: Identitas Modul
* **Track:** Backend and Database Engineering
* **Kategori:** 04-Backend-and-Database
* **Teknologi Utama:** Spring Boot 3.3.x, Apache Kafka, Spring Cloud Stream, Spring Kafka
* **Tingkat Kesulitan:** Advanced / Enterprise-Grade
* **Prasyarat Konseptual:** Spring Boot Fundamentals, JPA/Hibernate, ACID Transactions, Microservices Patterns, Docker & Testcontainers.

---

## 02: Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. Mendiagnosis batasan sinkronisasi HTTP/REST dan merancang topologi Event-Driven Architecture (EDA) yang resilien.
2. Mengimplementasikan Publisher-Subscriber Pattern dan Competing Consumers menggunakan Apache Kafka dan Spring Kafka.
3. Menyelesaikan anomali inkonsistensi data lintas distributed service dengan Transactional Outbox Pattern dan Idempotent Consumer.
4. Membangun abstraksi messaging yang portable menggunakan Spring Cloud Stream.
5. Menghindari data loss dan split-brain scenario melalui konfigurasi zero-data-loss producer dan consumer.
6. Menerapkan Dead Letter Queue (DLQ), Exponential Backoff Retry, dan Schema Evolution menggunakan Avro/Schema Registry.

---

## 03: Concept Map Diagram ASCII
```
+-----------------------------------------------------------------------------------+
|                        EVENT-DRIVEN ARCHITECTURE WITH KAFKA                       |
+-----------------------------------------------------------------------------------+
                                          |
                   +----------------------+----------------------+
                   |                                             |
        [1. CORE MESSAGING ENGINE]                   [2. RELIABILITY PATTERNS]
                   |                                             |
         +---------+---------+                         +---------+---------+
         |                   |                         |                   |
    [Topic & Partitions] [Consumer Groups]    [Transactional Outbox]  [Idempotent Consumer]
         |                   |                         |                   |
    - Broker Cluster     - Load Balancing          - Local DB Tx       - Dedup Key (UUID)
    - Replication (ISR)  - Partition Rebalance     - Debezium / CDC    - In-flight Lock
    - Segment Log        - Offset Commit           - Outbox Table      - State Store (Redis/RDBMS)
                   |                                             |
                   +----------------------+----------------------+
                                          |
                            [3. SPRING INTEGRATION TIER]
                                          |
                     +--------------------+--------------------+
                     |                                         |
             [Spring for Apache Kafka]              [Spring Cloud Stream]
                     |                                         |
             - KafkaTemplate                        - Functional Binders (Supplier/
             - @KafkaListener                         Function/Consumer)
             - ContainerFactory (Batch/Single)      - Destination Binding Abstraction
             - CommonErrorHandler (DLQ/Retry)       - Schema Registry Integration
```

---

## 04: Mengapa Relevan
Pada arsitektur monolitik tradisional, sinkronisasi state antar domain dieksekusi dalam satu transaksi database lokal (ACID). Ketika sistem beralih ke microservices, komunikasi berbasis HTTP REST menghasilkan *temporal coupling*—jika downstream service mengalami degradasi latensi atau downtime, upstream service akan mengalami *cascading failure*.

Event-Driven Architecture (EDA) mendekopel relasi waktu (temporal) dan ruang (spatial) antar service. Komunikasi berlangsung secara asinkron melalui event immutable yang dialirkan ke message broker (seperti Apache Kafka). 

Namun, messaging terdistribusi memperkenalkan tantangan kompleks: *dual-write problem* (inkonsistensi database vs broker), *duplicate messages* (at-least-once delivery semantics), *poison-pill events*, dan *out-of-order execution*. Modul ini memberikan blueprint teknis untuk membangun enterprise event pipeline dengan jaminan *exactly-once processing semantics* pada boundary aplikasi.

---

## 05: Anatomi Konsep Inti

```
+---------------------------------------------------------------------------------------+
| PRODUCER RUNTIME              KAFKA BROKER CLUSTER                 CONSUMER RUNTIME   |
|                                                                                       |
| +-------------------+         +-----------------------+         +-------------------+ |
| | Business Logic    |         | Topic: order-events   |         | @KafkaListener    | |
| +--------+----------+         +-----------+-----------+         +---------+---------+ |
|          |                                |                               |           |
| +--------v----------+         +-----------v-----------+         +---------v---------+ |
| | Transactional     |=======> | Partition 0 (Leader)  | =======>| RecordInterceptor | |
| | Outbox Table      | (Poll)  |   - ISR: [B1, B2]     |         +---------+---------+ |
| +--------+----------+         +-----------+-----------+                   |           |
|          | CDC                    Log Segment (Append)          +---------v---------+ |
| +--------v----------+                                           | Idempotent Engine | |
| | KafkaTemplate     |                                           | (Processed Events)| |
| +-------------------+                                           +---------+---------+ |
|          | acks=all                                                       |           |
|          v                                                      +---------v---------+ |
| [Broker Acknowledged]                                           | Target Domain Svc | |
|                                                                 +-------------------+ |
+---------------------------------------------------------------------------------------+
```

### 1. Delivery Semantics
* **At-Most-Once:** Event dikirim tanpa retry (`acks=0`). Consumer melakukan commit offset sebelum memproses pesan. Risiko: *Data Loss*.
* **At-Least-Once:** Producer melakukan retry sampai broker mengirim `ack` (`acks=all`). Consumer melakukan commit offset setelah pemrosesan selesai. Risiko: *Duplicate Processing*.
* **Effectively-Once / Exactly-Once:** Kombinasi idempotency pada producer (`enable.idempotence=true`), transaksi Kafka, dan *Idempotent Consumer Pattern* di sisi downstream consumer.

### 2. Dual-Write Problem & Transactional Outbox
Dual-write terjadi saat aplikasi harus memperbarui Database lokal dan mengirim event ke Kafka. Jika DB Commit sukses namun Kafka Publish gagal (atau sebaliknya), sistem jatuh ke status inkonsisten.
* **Solusi:** Transactional Outbox Pattern. Modifikasi status domain dan event disimpan di database yang sama dalam satu transaksi ACID lokal. Poller thread atau Change Data Capture (CDC Engine seperti Debezium) membaca Outbox table dan mem-publish-nya ke Kafka.

### 3. Kafka Partitions & Concurrency
* Skalabilitas konsumsi ditentukan oleh jumlah partisi.
* Hanya satu consumer thread di dalam single Consumer Group yang dapat membaca satu partisi pada waktu yang sama.
* Untuk menjaga *strict ordering*, event dengan context yang sama (misal: `order_id`) harus menggunakan Partition Key yang sama.

---

## 06: Panduan Implementasi Step-by-Step

### Step 1: Konfigurasi Dependency (`pom.xml`)
Gunakan Spring Boot 3.3+ dengan dependencies Spring Kafka, Spring Cloud Stream, and PostgreSQL.

```xml
<dependencies>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-data-jpa</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.kafka</groupId>
        <artifactId>spring-kafka</artifactId>
    </dependency>
    <dependency>
        <groupId>org.postgresql</groupId>
        <artifactId>postgresql</artifactId>
        <scope>runtime</scope>
    </dependency>
    <dependency>
        <groupId>com.fasterxml.jackson.core</groupId>
        <artifactId>jackson-databind</artifactId>
    </dependency>
</dependencies>
```

### Step 2: Konfigurasi Producer & Consumer Resilient (`application.yml`)
Konfigurasi wajib untuk *Zero Data Loss* dan *Graceful Poison Pill Handling*.

```yaml
spring:
  application:
    name: order-processing-service
  datasource:
    url: jdbc:postgresql://localhost:5432/order_db
    username: postgres
    password: postgrespassword
    driver-class-name: org.postgresql.Driver
  jpa:
    hibernate:
      ddl-auto: update
    properties:
      hibernate.dialect: org.hibernate.dialect.PostgreSQLDialect
  kafka:
    bootstrap-servers: localhost:9092
    producer:
      acks: all
      retries: 2147483647 # Max Integer
      properties:
        enable.idempotence: true
        max.in.flight.requests.per.connection: 5
        compression.type: zstd
        linger.ms: 10
        batch.size: 32768
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: org.springframework.kafka.support.serializer.JsonSerializer
    consumer:
      group-id: order-fulfillment-group
      auto-offset-reset: earliest
      enable-auto-commit: false # Manual Ack required
      properties:
        isolation.level: read_committed
        spring.json.trusted.packages: "com.enterprise.messaging.dto,com.enterprise.messaging.event"
      key-deserializer: org.apache.kafka.common.serialization.StringDeserializer
      value-deserializer: org.springframework.kafka.support.serializer.ErrorHandlingDeserializer
      properties.spring.deserializer.value.delegate.class: org.springframework.kafka.support.serializer.JsonDeserializer

app:
  kafka:
    topics:
      order-events: enterprise.order.events.v1
      order-dlq: enterprise.order.events.v1.DLQ
```

---

## 07: Contoh Kasus Sederhana (Pub-Sub Dasar)

Model pub-sub dasar dengan `KafkaTemplate` dan `@KafkaListener`.

### Event Payload
```java
package com.enterprise.messaging.event;

public record NotificationEvent(String recipient, String message, long timestamp) {}
```

### Simple Producer
```java
package com.enterprise.messaging.producer;

import com.enterprise.messaging.event.NotificationEvent;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

@Service
public class SimpleNotificationProducer {
    private final KafkaTemplate<String, Object> kafkaTemplate;

    public SimpleNotificationProducer(KafkaTemplate<String, Object> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    public void sendNotification(String userId, String msg) {
        NotificationEvent event = new NotificationEvent(userId, msg, System.currentTimeMillis());
        kafkaTemplate.send("simple.notification.topic", userId, event);
    }
}
```

### Simple Consumer
```java
package com.enterprise.messaging.consumer;

import com.enterprise.messaging.event.NotificationEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;

@Service
public class SimpleNotificationConsumer {
    private static final Logger log = LoggerFactory.getLogger(SimpleNotificationConsumer.class);

    @KafkaListener(topics = "simple.notification.topic", groupId = "notification-simple-group")
    public void handleNotification(NotificationEvent event) {
        log.info("Received notification for: {} - Content: {}", event.recipient(), event.message());
    }
}
```

---

## 08: Implementasi Production-Grade Lengkap

Implementasi skenario e-Commerce Core: **Transactional Outbox Pattern Publisher** yang mempublikasikan `OrderCreatedEvent`, dan **Idempotent Consumer** downstream yang memproses order dengan **Exponential Backoff Error Handling & Dead Letter Topic (DLT)**.

```
PROJECT STRUCTURE:
src/main/java/com/enterprise/messaging/
├── config/
│   ├── KafkaConsumerConfig.java
│   └── KafkaTopicConfig.java
├── domain/
│   ├── Order.java
│   ├── OutboxMessage.java
│   └── ProcessedEvent.java
├── dto/
│   └── CreateOrderRequest.java
├── event/
│   └── OrderCreatedEvent.java
├── repository/
│   ├── OrderRepository.java
│   ├── OutboxRepository.java
│   └── ProcessedEventRepository.java
├── service/
│   ├── IdempotentOrderConsumer.java
│   ├── OrderCommandService.java
│   └── OutboxPublisherScheduler.java
```

### 1. Topic Configuration (`config/KafkaTopicConfig.java`)
```java
package com.enterprise.messaging.config;

import org.apache.kafka.clients.admin.NewTopic;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.TopicBuilder;

@Configuration
public class KafkaTopicConfig {

    @Value("${app.kafka.topics.order-events}")
    private String orderEventsTopic;

    @Value("${app.kafka.topics.order-dlq}")
    private String orderDlqTopic;

    @Bean
    public NewTopic orderEventsTopic() {
        return TopicBuilder.name(orderEventsTopic)
                .partitions(3)
                .replicas(1) // Sesuaikan dengan jumlah cluster broker di production (misal: 3)
                .build();
    }

    @Bean
    public NewTopic orderDlqTopic() {
        return TopicBuilder.name(orderDlqTopic)
                .partitions(3)
                .replicas(1)
                .build();
    }
}
```

### 2. Domain Entities & Repositories

#### `domain/Order.java`
```java
package com.enterprise.messaging.domain;

import jakarta.persistence.*;
import java.math.BigDecimal;
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
    private BigDecimal totalAmount;
    
    @Column(nullable = false)
    private String status;
    
    @Column(nullable = false)
    private Instant createdAt;

    public Order() {}

    public Order(UUID id, String customerId, BigDecimal totalAmount, String status, Instant createdAt) {
        this.id = id;
        this.customerId = customerId;
        this.totalAmount = totalAmount;
        this.status = status;
        this.createdAt = createdAt;
    }

    public UUID getId() { return id; }
    public String getCustomerId() { return customerId; }
    public BigDecimal getTotalAmount() { return totalAmount; }
    public String getStatus() { return status; }
    public Instant getCreatedAt() { return createdAt; }
}
```

#### `domain/OutboxMessage.java`
```java
package com.enterprise.messaging.domain;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "outbox_messages", indexes = {
    @Index(name = "idx_outbox_status_created", columnList = "status, createdAt")
})
public class OutboxMessage {
    @Id
    private UUID id;

    @Column(nullable = false)
    private String aggregateType;

    @Column(nullable = false)
    private String aggregateId;

    @Column(nullable = false)
    private String eventType;

    @Column(columnDefinition = "TEXT", nullable = false)
    private String payload;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private OutboxStatus status;

    @Column(nullable = false)
    private Instant createdAt;

    private Instant processedAt;
    private int retryCount;

    public enum OutboxStatus { PENDING, PROCESSING, COMPLETED, FAILED }

    public OutboxMessage() {}

    public OutboxMessage(UUID id, String aggregateType, String aggregateId, String eventType, String payload, Instant createdAt) {
        this.id = id;
        this.aggregateType = aggregateType;
        this.aggregateId = aggregateId;
        this.eventType = eventType;
        this.payload = payload;
        this.status = OutboxStatus.PENDING;
        this.createdAt = createdAt;
        this.retryCount = 0;
    }

    public UUID getId() { return id; }
    public String getAggregateType() { return aggregateType; }
    public String getAggregateId() { return aggregateId; }
    public String getEventType() { return eventType; }
    public String getPayload() { return payload; }
    public OutboxStatus getStatus() { return status; }
    public void setStatus(OutboxStatus status) { this.status = status; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getProcessedAt() { return processedAt; }
    public void setProcessedAt(Instant processedAt) { this.processedAt = processedAt; }
    public int getRetryCount() { return retryCount; }
    public void setRetryCount(int retryCount) { this.retryCount = retryCount; }
}
```

#### `domain/ProcessedEvent.java` (Idempotency Record)
```java
package com.enterprise.messaging.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;

@Entity
@Table(name = "processed_events")
public class ProcessedEvent {
    @Id
    private String eventId;

    @Column(nullable = false)
    private Instant processedAt;

    public ProcessedEvent() {}

    public ProcessedEvent(String eventId, Instant processedAt) {
        this.eventId = eventId;
        this.processedAt = processedAt;
    }

    public String getEventId() { return eventId; }
    public Instant getProcessedAt() { return processedAt; }
}
```

#### Repositories
```java
package com.enterprise.messaging.repository;

import com.enterprise.messaging.domain.Order;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.UUID;

public interface OrderRepository extends JpaRepository<Order, UUID> {}
```

```java
package com.enterprise.messaging.repository;

import com.enterprise.messaging.domain.OutboxMessage;
import jakarta.persistence.LockModeType;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.UUID;

public interface OutboxRepository extends JpaRepository<OutboxMessage, UUID> {
    
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("SELECT o FROM OutboxMessage o WHERE o.status = :status ORDER BY o.createdAt ASC")
    List<OutboxMessage> findPendingMessagesForProcessing(@Param("status") OutboxMessage.OutboxStatus status, Pageable pageable);
}
```

```java
package com.enterprise.messaging.repository;

import com.enterprise.messaging.domain.ProcessedEvent;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ProcessedEventRepository extends JpaRepository<ProcessedEvent, String> {}
```

### 3. Events & DTO
```java
package com.enterprise.messaging.dto;

import java.math.BigDecimal;

public record CreateOrderRequest(String customerId, BigDecimal amount) {}
```

```java
package com.enterprise.messaging.event;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

public record OrderCreatedEvent(
    UUID eventId,
    UUID orderId,
    String customerId,
    BigDecimal totalAmount,
    Instant timestamp
) {}
```

### 4. Producer Application Tier

#### `service/OrderCommandService.java`
```java
package com.enterprise.messaging.service;

import com.enterprise.messaging.domain.Order;
import com.enterprise.messaging.domain.OutboxMessage;
import com.enterprise.messaging.dto.CreateOrderRequest;
import com.enterprise.messaging.event.OrderCreatedEvent;
import com.enterprise.messaging.repository.OrderRepository;
import com.enterprise.messaging.repository.OutboxRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.UUID;

@Service
public class OrderCommandService {

    private final OrderRepository orderRepository;
    private final OutboxRepository outboxRepository;
    private final ObjectMapper objectMapper;

    public OrderCommandService(OrderRepository orderRepository, OutboxRepository outboxRepository, ObjectMapper objectMapper) {
        this.orderRepository = orderRepository;
        this.outboxRepository = outboxRepository;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public UUID createOrder(CreateOrderRequest request) {
        UUID orderId = UUID.randomUUID();
        Instant now = Instant.now();

        // 1. Mutasi State Domain Utama
        Order order = new Order(orderId, request.customerId(), request.amount(), "CREATED", now);
        orderRepository.save(order);

        // 2. Buat Event Payload
        UUID eventId = UUID.randomUUID();
        OrderCreatedEvent event = new OrderCreatedEvent(eventId, orderId, request.customerId(), request.amount(), now);

        // 3. Simpan ke Outbox Table dalam Transaksi ACID yang sama
        try {
            String payloadJson = objectMapper.writeValueAsString(event);
            OutboxMessage outbox = new OutboxMessage(
                    eventId,
                    "ORDER",
                    orderId.toString(),
                    "OrderCreatedEvent",
                    payloadJson,
                    now
            );
            outboxRepository.save(outbox);
        } catch (Exception e) {
            throw new RuntimeException("Gagal melakukan serialisasi event ke outbox", e);
        }

        return orderId;
    }
}
```

#### `service/OutboxPublisherScheduler.java`
```java
package com.enterprise.messaging.service;

import com.enterprise.messaging.domain.OutboxMessage;
import com.enterprise.messaging.repository.OutboxRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.PageRequest;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;

@Component
@EnableScheduling
public class OutboxPublisherScheduler {
    private static final Logger log = LoggerFactory.getLogger(OutboxPublisherScheduler.class);

    private final OutboxRepository outboxRepository;
    private final KafkaTemplate<String, Object> kafkaTemplate;

    @Value("${app.kafka.topics.order-events}")
    private String orderEventsTopic;

    public OutboxPublisherScheduler(OutboxRepository outboxRepository, KafkaTemplate<String, Object> kafkaTemplate) {
        this.outboxRepository = outboxRepository;
        this.kafkaTemplate = kafkaTemplate;
    }

    @Scheduled(fixedDelay = 1000)
    @Transactional
    public void publishOutboxMessages() {
        List<OutboxMessage> pendingMessages = outboxRepository.findPendingMessagesForProcessing(
                OutboxMessage.OutboxStatus.PENDING,
                PageRequest.of(0, 100)
        );

        for (OutboxMessage msg : pendingMessages) {
            try {
                // Publish ke Kafka: Key diisi aggregateId untuk menjamin partition ordering
                kafkaTemplate.send(orderEventsTopic, msg.getAggregateId(), msg.getPayload())
                        .whenComplete((result, ex) -> {
                            if (ex != null) {
                                log.error("Kafka send async failure for outbox id: {}", msg.getId(), ex);
                            }
                        });

                msg.setStatus(OutboxMessage.OutboxStatus.COMPLETED);
                msg.setProcessedAt(Instant.now());
                outboxRepository.save(msg);
            } catch (Exception ex) {
                log.error("Outbox forwarder failed on message id: {}", msg.getId(), ex);
                msg.setRetryCount(msg.getRetryCount() + 1);
                if (msg.getRetryCount() > 5) {
                    msg.setStatus(OutboxMessage.OutboxStatus.FAILED);
                }
                outboxRepository.save(msg);
            }
        }
    }
}
```

### 5. Consumer Configuration Tier

#### `config/KafkaConsumerConfig.java`
```java
package com.enterprise.messaging.config;

import org.apache.kafka.common.TopicPartition;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.annotation.EnableKafka;
import org.