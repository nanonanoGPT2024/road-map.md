# BAB 07: Event-Driven Architecture & Enterprise Messaging
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Mendesain & Mengimplementasikan Pola Transactional Outbox** menggunakan Spring Boot 3.x dan Spring Data JPA untuk menjamin konsistensi *dual-write* tanpa *distributed two-phase commit* (2PC).
2. **Membangun Resilient Consumer Pipeline** dengan strategi *Non-Blocking Retries*, *Backoff with Jitter*, dan *Dead Letter Topic (DLT)* multi-tier menggunakan Spring Kafka.
3. **Mengimplementasikan Idempotent Consumer Pattern** berbasis distributed lock/state store (Redis & Database Deduplication) untuk mengatasi skenario pengiriman *at-least-once*.
4. **Mengonfigurasi High-Throughput & Low-Latency Consumer/Producer** melalui tuning batching, compression, transactional producer, concurrency tuning, dan partition management.
5. **Menerapkan Distributed Context Propagation** (W3C Trace Context / OpenTelemetry) melintasi sekat proses asinkron untuk end-to-end observability.

---

### 2. Prerequisite

Sebelum mempelajari modul lanjutan ini, Anda wajib memahami:
*   **Java 21**: Virtual Threads, Records, Sealed Interfaces, `CompletableFuture`.
*   **Spring Boot 3.x Core**: Dependency Injection, Auto-Configuration, Transaction Management (`@Transactional`).
*   **Dasar Apache Kafka**: Broker, Zookeeper/KRaft, Topics, Partitions, Offset, Consumer Groups, Producer Acks (`acks=0, 1, all`).
*   **Relational Database Engine**: PostgreSQL MVCC, row-level locking (`SELECT ... FOR UPDATE`), dan transactional isolation levels (Read Committed, Repeatable Read).
*   **Docker & Docker Compose**: Untuk orkestrasi kluster multi-broker Kafka, Schema Registry, dan PostgreSQL.

---

### 3. Concept & Internal Architecture

Implementasi enterprise messaging pada sistem terdistribusi skala tinggi menghadapi tiga tantangan fundamental: **Dual-Write Problem**, **Consumer Poison Pill & Head-of-Line Blocking**, serta **Rebalance Storms**.

#### 3.1 Dual-Write Problem & Transactional Outbox
Ketika sebuah service harus memperbarui database lokal sekaligus memublikasikan event ke Kafka, eksekusi dua operasi I/O terpisah ini tidak pernah atomik. Jika database commit berhasil tetapi broker Kafka unreachable, event hilang (*silent data loss*). Jika event terkirim tetapi database transaksi rollback, downstream service memproses data phantom (*ghost state*).

```
   [Client Request] 
          │
          ▼
   ┌───────────────┐
   │ Spring Boot   │ ──(1) BEGIN TX ────────────────────────┐
   │ Application   │ ──(2) UPDATE tbl_orders               │
   │               │ ──(3) INSERT tbl_outbox (Event Record) │
   │               │ ──(4) COMMIT TX ───────────────────────┘
   └──────┬────────┘
          │ (Asynchronous Polling / CDC via Debezium)
          ▼
   ┌───────────────┐
   │ Outbox Relay  │ ──(5) Read Outbox & Produce ──► [ Kafka Broker ]
   └───────────────┘
```

Mekanisme ini menghilangkan kebutuhan *distributed transaction* (XA/2PC) yang memiliki throughput rendah dan latency tinggi. Transaksi lokal menjamin integritas data dan keberadaan event secara bersamaan.

#### 3.2 Non-Blocking Retry Architecture
Secara default, jika Kafka listener melempar exception saat memproses record, consumer akan memblokir partisi tersebut dan melakukan retry secara berulang (*Head-of-Line Blocking*). Ini menurunkan throughput seluruh partisi ke angka 0.

Spring Kafka menyediakan arsitektur retry non-blocking dengan memanfaatkan *delay topics*:
1. Pesan gagal diproses pada topic utama (`order-events`).
2. Pesan dipublikasikan ke topic retry bertingkat (`order-events-retry-1000`, `order-events-retry-5000`).
3. Offset pada topic utama di-commit, sehingga consumer dapat segera memproses pesan berikutnya.
4. Consumer terpisah mendengarkan retry topic dengan delay backoff terkonfigurasi.
5. Jika seluruh threshold retry terlampaui, pesan dialihkan ke Dead Letter Topic (`order-events-dlt`).

```
[order-events] ──► [Consumer: Main] ──(Fail)──► [order-events-retry-1s]
                        │                            │
                     (Commit)                  (Delay Consumer)
                        │                            │
                 [Next Message]               (Fail 3x Max)
                                                     │
                                                     ▼
                                            [order-events-dlt]
```

#### 3.3 Consumer Internals, Coordinators, dan Rebalancing
Di balik layar, Spring Kafka membungkus `KafkaConsumer` Java standard dalam `KafkaMessageListenerContainer` atau `ConcurrentMessageListenerContainer`.

*   **Group Coordinator**: Salah satu broker Kafka yang ditugaskan mengelola keanggotaan consumer group.
*   **Heartbeat Thread**: Thread latar belakang independen yang mengirimkan sinyal periodik (`heartbeat.interval.ms`) ke Group Coordinator untuk menandakan bahwa consumer masih aktif.
*   **Poll Loop (`max.poll.interval.ms`)**: Thread pemrosesan utama menjalankan loop `poll()`. Jika waktu eksekusi logika bisnis melampaui `max.poll.interval.ms`, broker menganggap consumer mati dan memicu **Rebalance**, memindahkan kepemilikan partisi ke consumer lain.

---

### 4. Why & What

| Dimensi | Pendekatan Naif (Direct Publish) | Enterprise EDA (Outbox + Non-Blocking DLT) |
| :--- | :--- | :--- |
| **Integritas Dual-Write** | Potensi inkonsistensi data parah saat broker down. | Jaminan konsistensi transaksional 100% (*At-Least-Once Delivery* terverifikasi). |
| **Handling Error Spurious** | Consumer freeze atau pesan langsung dibuang (*loss*). | Isolasi kegagalan bertahap; zero head-of-line blocking. |
| **Skalabilitas Consumer** | Lambat akibat thread lock saat retry. | Throughput stabil, partisi terus bergerak memproses pesan normal. |
| **Auditability** | Sulit melacak lifecycle event yang hilang. | Jejak tersimpan di tabel outbox dan DLT untuk audit post-mortem. |

---

### 5. How (Workflow Detail)

Alur kerja arsitektur produksi terdiri dari dua pipeline independen:

#### Pipeline 1: Producer & Transactional Outbox
1. **Inisiasi Permintaan**: HTTP request masuk ke Controller layer.
2. **Atomic State Write**: Service layer membuka transaksi database ACID lokal.
   * State entity bisnis diperbarui (contoh: status order diubah menjadi `PAID`).
   * Event payload diserialisasi ke JSON dan dimasukkan ke tabel `tbl_outbox` dengan status `PENDING`.
3. **Commit Transaksi**: Database melakukan commit. Transaksi selesai.
4. **Relay Engine**: Worker terjadwal (atau Debezium CDC Engine) membaca baris `PENDING` dengan kueri berindeks:
   ```sql
   SELECT * FROM tbl_outbox WHERE status = 'PENDING' ORDER BY created_at ASC LIMIT 100 FOR UPDATE SKIP LOCKED;
   ```
5. **Publish ke Message Broker**: Worker mengirimkan event ke topic Kafka tujuan dengan jaminan `acks=all`.
6. **Mark as Processed**: Setelah broker mengembalikan ACK (offset dan partition terkonfirmasi), worker memperbarui status row di `tbl_outbox` menjadi `PUBLISHED` atau menghapusnya.

#### Pipeline 2: Resilient Idempotent Consumer
1. **Poll Batch**: `KafkaMessageListenerContainer` menarik batch pesan dari broker.
2. **Deduplication Check**: Untuk setiap pesan, consumer mengekstrak business key unik atau event ID dari metadata/header. Consumer memeriksa database atau Redis:
   * Jika ID sudah tercatat berstatus `PROCESSED`, record langsung di-*skip* (ACK dikirim).
3. **Business Logic Execution**: Eksekusi logika bisnis downstream.
4. **Atomic Processing & Idempotency Store**: Simpan hasil proses dan tandai event ID sebagai `PROCESSED` dalam satu transaksi lokal.
5. **Error & Routing**:
   * Jika terjadi transient exception (network error, timeout), Spring Kafka me-route record ke *retry topic* dengan metadata delay header.
   * Jika retry habis atau terjadi non-transient error (`IllegalArgumentException`, schema mismatch), kirim ke DLT secara otomatis.
6. **Manual Offset Commit**: Consumer meng-commit offset ke Kafka broker setelah batch sukses.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Kantor Pos dan Buku Catatan Pengiriman
Bayangkan Anda seorang staf akuntansi yang harus mendistribusikan invoice:
*   **Pendekatan Naif**: Anda mencatat invoice di komputer, lalu langsung berjalan ke kotak pos. Jika di tengah jalan Anda pingsan, invoice di komputer tercatat terkirim padahal belum masuk kotak pos.
*   **Transactional Outbox**: Anda mencatat invoice di software akuntansi dan sekaligus menulis tugas pengiriman di buku agenda fisik (*outbox table*). Kurir kantor secara periodik mengecek buku agenda tersebut, mengambil dokumen, mengirimkannya ke kantor pos, lalu menandai baris di agenda sebagai "Terkirim".
*   **Dead Letter Queue**: Jika kurir menemukan amplop dengan alamat yang rusak/salah, kurir tidak berdiri seharian di depan rumah target (membuat pengiriman surat lain macet). Amplop itu dimasukkan ke kotak "Bermasalah" (*DLT*) untuk diteliti staf investigasi nanti sore, sementara kurir langsung melanjutkan pengiriman surat reguler lainnya.

#### Diagram Arsitektur Runtime
```
+---------------------------------------------------------------------------------------+
|                                    PRODUCER SERVICE                                   |
|                                                                                       |
|   +-------------------+    (Writes)    +-------------------+    (Writes)              |
|   |   Order Service   | -------------> | tbl_order         |                          |
|   +---------+---------+                +-------------------+                          |
|             |                                                                         |
|             +------------------------> +-------------------+                          |
|                 [ACID Transaction]     | tbl_outbox        |                          |
|                                        +---------+---------+                          |
|                                                  |                                    |
|   +-------------------+    (Pulls)               |                                    |
|   |   Outbox Relay    | <------------------------+                                    |
|   +---------+---------+                                                               |
+-------------|-------------------------------------------------------------------------+
              | (Kafka Producer: acks=all)
              ▼
+---------------------------------------------------------------------------------------+
|                                      KAFKA CLUSTER                                    |
|                                                                                       |
|   [ Topic: order-created ] ---------> [ Topic: order-created-retry-1s ]               |
|            |                                        |                                 |
|            |                                        | (Retry Exhausted)               |
|            |                                        v                                 |
|            |                             [ Topic: order-created-dlt ]                 |
+------------|----------------------------------------+---------------------------------+
             |                                        |
             ▼                                        ▼
+------------------------------------+  +-----------------------------------------------+
|     CONSUMER SERVICE               |  |     DLQ MONITOR SERVICE                       |
|                                    |  |                                               |
|  +------------------------------+  |  |  +-----------------------------------------+  |
|  | Idempotency Deduplication    |  |  |  | Alerting, Manual Replay & Root-Cause    |  |
|  | Check (Redis / PostgreSQL)   |  |  |  | Analysis Dashboard                      |  |
|  +--------------+---------------+  |  +-----------------------------------------+--+  |
|                 |                  |                                                  |
|                 v                  |                                                  |
|  +------------------------------+  |                                                  |
|  | Business Mutation Executed   |  |                                                  |
|  +------------------------------+  |                                                  |
+------------------------------------+  +-----------------------------------------------+
```

---

### 7. Practical Example (Production-Ready Code)

Implementasi enterprise-grade berbasis **Spring Boot 3.3.x**, **Spring Kafka**, dan **Spring Data JPA**.

#### 7.1 Schema Database (PostgreSQL)

```sql
-- DDL untuk entities dan outbox
CREATE TABLE tbl_orders (
    order_id UUID PRIMARY KEY,
    customer_id VARCHAR(64) NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE tbl_outbox (
    id UUID PRIMARY KEY,
    aggregate_type VARCHAR(64) NOT NULL,
    aggregate_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(32) NOT NULL,
    retry_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_outbox_fetch ON tbl_outbox (status, created_at ASC);

CREATE TABLE tbl_processed_events (
    event_id UUID PRIMARY KEY,
    consumer_group VARCHAR(128) NOT NULL,
    processed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

#### 7.2 Entity & Repository Layer

```java
package com.enterprise.eda.domain.outbox;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "tbl_outbox")
public class OutboxMessage {

    @Id
    private UUID id;

    @Column(name = "aggregate_type", nullable = false)
    private String aggregateType;

    @Column(name = "aggregate_id", nullable = false)
    private String aggregateId;

    @Column(name = "event_type", nullable = false)
    private String eventType;

    @Column(columnDefinition = "jsonb", nullable = false)
    private String payload;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private OutboxStatus status;

    @Column(name = "retry_count", nullable = false)
    private int retryCount;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    public enum OutboxStatus { PENDING, PROCESSING, PUBLISHED, FAILED }

    protected OutboxMessage() {}

    public OutboxMessage(UUID id, String aggregateType, String aggregateId, String eventType, String payload) {
        this.id = id;
        this.aggregateType = aggregateType;
        this.aggregateId = aggregateId;
        this.eventType = eventType;
        this.payload = payload;
        this.status = OutboxStatus.PENDING;
        this.retryCount = 0;
        this.createdAt = Instant.now();
        this.updatedAt = Instant.now();
    }

    // Getters and Mutators
    public UUID getId() { return id; }
    public String getPayload() { return payload; }
    public String getAggregateId() { return aggregateId; }
    public String getEventType() { return eventType; }
    public void markPublished() {
        this.status = OutboxStatus.PUBLISHED;
        this.updatedAt = Instant.now();
    }
    public void incrementRetry() {
        this.retryCount++;
        this.updatedAt = Instant.now();
    }
}
```

```java
package com.enterprise.eda.domain.outbox;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import java.util.List;
import java.util.UUID;

public interface OutboxRepository extends JpaRepository<OutboxMessage, UUID> {

    @Query(value = """
        SELECT * FROM tbl_outbox 
        WHERE status = 'PENDING' 
        ORDER BY created_at ASC 
        LIMIT :batchSize 
        FOR UPDATE SKIP LOCKED
        """, nativeQuery = true)
    List<OutboxMessage> fetchPendingMessagesForProcessing(@Param("batchSize") int batchSize);
}
```

#### 7.3 Outbox Relay Worker (Scheduler + Spring Kafka Producer)

```java
package com.enterprise.eda.infrastructure.outbox;

import com.enterprise.eda.domain.outbox.OutboxMessage;
import com.enterprise.eda.domain.outbox.OutboxRepository;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.header.internals.RecordHeader;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.UUID;

@Component
public class OutboxPublisher {

    private static final Logger log = LoggerFactory.getLogger(OutboxPublisher.class);
    private static final String TOPIC_ORDERS = "enterprise.order.events.v1";

    private final OutboxRepository outboxRepository;
    private final KafkaTemplate<String, String> kafkaTemplate;

    public OutboxPublisher(OutboxRepository outboxRepository, KafkaTemplate<String, String> kafkaTemplate) {
        this.outboxRepository = outboxRepository;
        this.kafkaTemplate = kafkaTemplate;
    }

    @Scheduled(fixedDelayString = "${app.outbox.poll-rate-ms:1000}")
    @Transactional
    public void processOutbox() {
        List<OutboxMessage> messages = outboxRepository.fetchPendingMessagesForProcessing(50);
        if (messages.isEmpty()) {
            return;
        }

        for (OutboxMessage message : messages) {
            try {
                ProducerRecord<String, String> record = new ProducerRecord<>(
                        TOPIC_ORDERS,
                        message.getAggregateId(),
                        message.getPayload()
                );
                
                // Distributed Tracing Context & Event Metadata Header Injection
                record.headers().add(new RecordHeader("x-event-id", message.getId().toString().getBytes(StandardCharsets.UTF_8)));
                record.headers().add(new RecordHeader("x-event-type", message.getEventType().getBytes(StandardCharsets.UTF_8)));

                kafkaTemplate.send(record).whenComplete((result, ex) -> {
                    if (ex == null) {
                        log.debug("Event successfully published to Kafka. EventId: {}, Offset: {}", 
                                message.getId(), result.getRecordMetadata().offset());
                    } else {
                        log.error("Failed sending event to Kafka. EventId: {}", message.getId(), ex);
                    }
                });

                message.markPublished();
            } catch (Exception ex) {
                log.error("Error dispatching outbox record ID: {}", message.getId(), ex);
                message.incrementRetry();
            }
        }
    }
}
```

#### 7.4 Enterprise Idempotent Consumer & Non-Blocking Retry Configuration

```java
package com.enterprise.eda.infrastructure.kafka;

import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.annotation.EnableKafka;
import org.