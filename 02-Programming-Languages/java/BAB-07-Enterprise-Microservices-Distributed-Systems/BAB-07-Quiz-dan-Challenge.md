# BAB 07: Quiz, Challenge, & Knowledge Check
**Enterprise Microservices & Distributed Systems**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **CAP Theorem & PACELC Theorem dalam Konteks Java Enterprise**  
   Jelaskan mengapa Two-Phase Commit (2PC) melalui Java Transaction API (JTA/XA) hampir selalu dihindari dalam sistem terdistribusi skala tinggi modern. Analisis keterbatasan 2PC ditinjau dari teorema PACELC saat terjadi *network partition* ($P$) dan saat sistem berada dalam kondisi normal ($A/E$).

2. **Idempotensi pada Komunikasi Asinkron dan Sinkron**  
   Definisikan apa yang dimaksud dengan idempotensi dalam distributed systems. Bagaimana implementasi teknis `Idempotency-Key` pada HTTP REST API layer dan bagaimana penerapannya pada Kafka consumer yang bekerja di bawah semantik pengiriman *at-least-once*?

3. **Saga Pattern: Choreography vs. Orchestration**  
   Bandingkan arsitektur *Choreography-based Saga* dan *Orchestration-based Saga*. Parameter teknis dan kondisi domain bisnis apa saja yang menentukan bahwa tim Anda harus beralih dari Choreography ke Orchestration (misalnya menggunakan engine seperti Temporal atau Camunda/Zeebe)?

4. **Service Discovery & Client-Side Load Balancing**  
   Bagaimana mekanisme kerja Client-Side Load Balancing (contoh: Spring Cloud LoadBalancer) berinteraksi dengan Service Registry (misalnya HashiCorp Consul atau Netflix Eureka)? Jelaskan siklus hidup *cache invalidation* pada *instance list* lokal ketika sebuah microservice *node* mengalami *crash* mendadak tanpa melalui proses *graceful shutdown*.

5. **Event-Driven Architecture: Event Sourcing vs. State Tracking**  
   Jelaskan perbedaan fundamental antara menyimpan *Current State* (model CRUD relasional standar) dengan *Event Sourcing* (menyimpan delta perubahan sebagai append-only log). Apa trade-off performa write vs. read pada arsitektur Event Sourcing, dan bagaimana CQRS (*Command Query Responsibility Segregation*) menyelesaikan masalah performa pada sisi read?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Internal State Machine pada Resilience4j Circuit Breaker**  
   Gambarkan dan jelaskan transisi state internal dari Resilience4j (`CLOSED`, `OPEN`, `HALF_OPEN`). Bagaimana algoritma *sliding window* (berbasis hitungan *count-based* vs waktu *time-based*) menghitung rasio kegagalan (*failure rate threshold*)? Apa implikasi alokasi memori JVM jika sliding window dikonfigurasi terlalu besar pada *throughput* transaksi puluhan ribu RPS?

2. **Context Propagation pada Distributed Tracing (W3C TraceContext)**  
   Bagaimana mekanisme internal OpenTelemetry atau Micrometer Tracing mentransmisikan metadata context (`traceparent`, `tracestate`) menembus batasan thread JVM lokal (`ThreadLocal`) dan batasan jaringan (*network hop*) antar protokol yang heterogen (HTTP/REST -> Apache Kafka -> gRPC)? Masalah apa yang timbul ketika aplikasi menggunakan Java 21 Virtual Threads atau reactive framework (Project Reactor)?

3. **Anatomi The Dual-Write Problem & Solusi Transactional Outbox**  
   Diberikan sebuah skenario kode di mana sebuah method Spring bertanda `@Transactional` melakukan penyimpanan data ke database (PostgreSQL) kemudian memanggil `kafkaTemplate.send()`. Analisis dua kegagalan fatal (*failure modes*) yang pasti terjadi pada pendekatan ini. Bagaimana Transactional Outbox Pattern yang dipadukan dengan Change Data Capture (Debezium) mengeliminasi problem tersebut secara deterministik?

4. **Debugging Thread Starvation pada RestTemplate / WebClient Pool**  
   Sebuah microservice Java tiba-tiba berhenti merespons traffic (HTTP 504 Gateway Timeout di API Gateway). Saat dilakukan analisis heap dump dan thread dump, mayoritas worker thread berada pada status `WAITING` di `org.apache.http.pool.AbstractConnPool.getPoolEntryBlocking`. Lakukan *root cause analysis* (RCA) terhadap konfigurasi `maxConnTotal`, `maxConnPerRoute`, serta interaksi koneksi HTTP keep-alive downstream service yang mengalami silent packet drop.

5. **gRPC vs. REST: Mekanisme Multiplexing HTTP/2 dan Serialization Overhead**  
   Secara arsitektur internal, mengapa gRPC berbasis Protocol Buffers menghasilkan latensi dan konsumsi CPU yang signifikan lebih rendah dibanding REST berbasis JSON over HTTP/1.1? Jelaskan mekanisme *HTTP/2 binary framing layer*, *multiplexing over single TCP connection*, dan eliminasi overhead parsing string di JVM level.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Cascading Failure & Epoll Thread Saturation pada Payment Gateway
Sistem Core Payment mengalami lonjakan traffic saat Flash Sale (15.000 RPS). Arsitektur terdiri dari:
- **API Gateway (Spring Cloud Gateway - Reactive/Netty)**
- **Order Service (Spring Boot MVC - Tomcat)**
- **Third-Party Fraud Detection Service (Eksternal, latensi normal 50ms)**

Tiba-tiba Third-Party Fraud Detection Service mengalami degradasi dan latensinya melonjak menjadi 12.000ms per request tanpa me-reject koneksi. Dalam kurun waktu 90 detik, Order Service kehabisan thread Tomcat (`max-threads=200` saturated), menyebabkan CPU Order Service 100%, health-check Kubernetes liveness probe gagal, pods di-restart berulang kali (*crash loop backoff*), dan akhirnya memicu antrean ribuan socket di Netty event-loop API Gateway hingga seluruh ekosistem down.

**Pertanyaan Diagnostik:**
1. Desain arsitektur resilience berlapis (kombinasi *Bulkhead*, *Circuit Breaker*, dan *Timeout*) yang harus diimplementasikan pada Order Service untuk mengisolasi kegagalan Third-Party Fraud Detection Service. Tentukan angka timeout dan sizing bulkhead yang rasional.
2. Mengapa kegagalan downstream pada arsitektur non-blocking (Netty) di API Gateway dapat menyebabkan *out-of-direct-memory* jika tidak ada *backpressure* mekanik yang tepat?
3. Langkah konfigurasi Kubernetes liveness/readiness probe apa yang salah sehingga pod yang sedang saturated justru dibunuh secara prematur dan memperburuk *cascading failure*?

---

### Skenario B: Split-Brain & Data Inconsistency pada Asynchronous Ledger Service
Perusahaan FinTech memproses transfer balance antar user. Arsitektur menggunakan asynchronous messaging:
1. `Transfer Service` memvalidasi saldo, menulis record ledger, dan mempublikasikan event `TransferInitiated` ke Kafka Topic `transfer-events` (partition count: 12).
2. Tiga instance `Balance Worker Service` mengonsumsi event tersebut dan mengupdate balance pada database PostgreSQL shards.
3. Terjadi jaringan flapping (*network partition*) selama 45 detik antara instance broker Kafka dan group consumer. 
4. Kafka Coordinator memicu Consumer Group Rebalance berulang kali. 
5. Hasil pasca-insiden: Beberapa transaksi diproses dua kali (double balance deduction) dan urutan mutasi balance user menjadi acak (out-of-order execution), menghasilkan saldo minus.

**Pertanyaan Diagnostik:**
1. Jelaskan bagaimana mekanisme Consumer Group Rebalance dapat menyebabkan *duplicate consumption* pada worker yang belum menyelesaikan commit offset (`enable.auto.commit=true` vs manual synchronous/asynchronous commit).
2. Rancang skema partitioning Kafka key dan database row-level locking (atau OCC - *Optimistic Concurrency Control*) untuk menjamin mutasi saldo untuk akun yang sama diproses secara strictly ordered dan idempotent.
3. Jika worker mengalami garbage collection freeze (Stop-The-World) yang melebihi durasi `max.poll.interval.ms`, bagaimana Kafka broker memperlakukan worker tersebut dan bagaimana distributed lock berbasis Redis/Redisson dapat rusak akibat fenomena ini jika tidak menggunakan *fencing token*?

---

### Skenario C: Migrasi Monolith-to-Microservices: Dilema Distributed Query & Two-Phase Reporting
Aplikasi e-commerce enterprise bermigrasi dari monolitik database PostgreSQL raksasa ke arsitektur microservices database-per-service:
- `Order DB` (menyimpan order header dan line items)
- `Customer DB` (menyimpan KYC, profiling, tiering diskon)
- `Warehouse DB` (menyimpan status stok fisik dan fulfillment)

Tim Product membutuhkan Dashboard Analitik Real-Time dengan query kompleks: *"Tampilkan 50 order bernilai tinggi dalam 1 jam terakhir beserta detail nama customer tier 'PLATINUM', lokasi warehouse asal barang, dan status pengiriman saat ini."*

Sebelum migrasi, query ini adalah single SQL `JOIN` sederhana (eksekusi 45ms). Setelah migrasi, tim engineer mencoba melakukan *In-Memory Application Join* dengan memanggil 3 HTTP endpoint REST antar-service secara paralel melalui `CompletableFuture.allOf()`, yang berakibat latensi melonjak menjadi 3.800ms dan sering mengalami timeout saat query pagination.

**Pertanyaan Diagnostik:**
1. Analisis mengapa anti-pattern distributed JOIN via HTTP REST gagal memenuhi SLA sistem. Hitung dampak network latency serialization overhead jika query melibatkan ratusan record.
2. Rancang arsitektur data alternatif berbasis Event-Driven Read Model menggunakan Change Data Capture (CDC) Debezium, Apache Kafka, dan Read-Optimized Storage (Elasticsearch atau single Read-Replica database) untuk mendukung dashboard tersebut dengan pola CQRS.
3. Bagaimana strategi menangani *eventual consistency lag* (kondisi di mana dashboard membaca projection data yang tertinggal 500ms dibanding data faktual di write-database)? Berikan pendekatan teknis di layer frontend/backend untuk mitigasi user experience.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput & Fault-Tolerant "Transactional Outbox & Idempotent Consumer" Engine

#### Deskripsi Masalah
Dalam sistem microservices perbankan modern, integritas data lintas batas database dan message broker adalah harga mati. Anda ditugaskan membangun engine core library modular menggunakan **Java 17/21** dan framework enterprise (**Spring Boot 3 / Quarkus**) yang menyelesaikan masalah *dual-write* dan menjamin konsumsi data yang *idempotent* dan *fault-tolerant*.

#### Requirements Arsitektur
1. **Outbox Publisher Engine (Transactional Outbox Pattern):**
   - Sediakan API atau anotasi deklaratif (misal: `@PublishEventOutbox`) yang memastikan data domain bisnis dan event tersimpan dalam database yang sama di bawah **satu transaksi database lokal ACID**.
   - Implementasikan *Background Poller* menggunakan thread pool terisolasi (Virtual Threads jika Java 21) atau CDC reader yang membaca table `outbox_events` dengan skema locking yang aman dari *race-condition* multi-instance (`SELECT ... FOR UPDATE SKIP LOCKED`).
   - Kirim event ke broker Kafka dengan jaminan retry jika broker sementara offline, menerapkan *exponential backoff* dan *jitter*.
   - Ubah status record outbox menjadi `PROCESSED` (atau hapus) setelah `RecordMetadata` Kafka ack diterima dari broker.

2. **Idempotent Consumer Engine:**
   - Bangun reusable consumer pipeline yang meng-intercept pesan Kafka yang masuk sebelum diserahkan ke method listener domain.
   - Gunakan tabel `processed_messages` (dengan primary key `message_id`) atau distributed in-memory lock + DB state untuk melakukan pengecekan deduplikasi pesan.
   - Mekanisme deduplikasi harus atomik: jika pemrosesan bisnis gagal (misal throw `BusinessException`), status pemrosesan harus di-*rollback* sehingga pesan dapat di-retry oleh mekanisme consumer group.
   - Sediakan penanganan khusus untuk Poison Pill / Malformed messages: arahkan ke Dead Letter Queue (DLQ) setelah 3 kali retry gagal, lengkap dengan header error context (`x-exception-message`, `x-original-topic`, `x-retry-count`).

3. **Telemetry & Distributed Tracing:**
   - Setiap outbox record harus menyimpan trace context (`traceparent`).
   - Consumer harus mengekstrak context tersebut dan me-restore tracing scope sehingga log dari Publisher -> DB Outbox -> Kafka -> Consumer berada di bawah satu `Trace ID` yang sama pada dashboard observabilitas (Jaeger/Zipkin compatible).

#### Constraints & Non-Functional Requirements
- **Throughput Target:** Minimal 2.500 event/detik pada publisher tanpa menyebabkan database lock contention yang parah pada tabel outbox.
- **Resilience:** Matikan broker Kafka secara sengaja saat publisher sedang memproses data; sistem tidak boleh melempar unhandled exception yang merusak state transaksi bisnis lokal.
- **No Global Locks:** Dilarang menggunakan global table locking (`LOCK TABLE outbox`). Gunakan `SKIP LOCKED` atau partition-based polling.

#### Expected Output
1. Source code implementasi lengkap (Project Maven/Gradle).
2. Script migrasi database (Flyway/Liquibase) untuk tabel `outbox_events` dan `processed_messages`.
3. Integration Test suite berbasis **Testcontainers** (menggunakan Testcontainers PostgreSQL dan Kafka) yang memvalidasi skenario:
   - *Happy path*: Order created -> Outbox committed -> Published to Kafka -> Consumed idempotently.
   - *Duplicate delivery*: Pengiriman event yang sama 2x ke Kafka topic hanya mengeksekusi domain logic consumer 1x.
   - *Network partition simulation*: Mematikan Kafka broker, memicu transaksi baru, menyalakan Kafka broker kembali, dan memverifikasi outbox records terkirim secara utuh tanpa data loss.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Batasan teoritis Teorema CAP dan PACELC, serta mengapa arsitektur enterprise modern memilih *BASE (Basically Available, Soft state, Eventual consistency)* dibanding *ACID 2PC* murni di level terdistribusi.
- [ ] Mekanisme kerja Transactional Outbox Pattern dan Change Data Capture (CDC) dalam menyelesaikan the *dual-write problem*.
- [ ] State lifecycle Circuit Breaker, strategi alokasi Bulkhead (Thread Pool vs. Semaphore Isolation), dan implementasi Rate Limiting (Token Bucket / Leaky Bucket).
- [ ] Anatomi propagasi Distributed Tracing sesuai standar W3C TraceContext di atas protokol transport sinkron (HTTP, gRPC) dan asinkron (Kafka, RabbitMQ).
- [ ] Perbedaan model arsitektur Saga Choreography (desentralisasi via event) vs Saga Orchestration (sentralisasi via orchestrator state machine).
- [ ] Konsekuensi operasional dari *At-Least-Once Delivery* pada message broker dan keharusan membangun *Idempotent Consumer* di sisi worker.
- [ ] Karakteristik performa dan networking gRPC/Protobuf over HTTP/2 dibandingkan JSON over HTTP/1.1.

### Saya tidak perlu menghafal:
- [ ] Seluruh signature method internal dari framework low-level seperti Netty channel pipeline atau interceptor internal Apache Kafka client.
- [ ] Sintaksis persis file konfigurasi deployment untuk semua service mesh (misal: ribuan baris YAML Istio VirtualService atau Envoy Filter).
- [ ] Kode byte protokol internal Protocol Buffers atau wire-format detail serialization Apache Avro.
- [ ] Nilai default ratusan parameter konfigurasi Kafka Producer/Consumer (cukup memahami parameter kritis: `acks`, `retries`, `enable.idempotence`, `max.poll.interval.ms`, `isolation.level`).

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi dan mengintegrasikan Resilience4j / Spring Cloud Circuit Breaker pada layer inter-service client (OpenFeign / WebClient / RestClient).
- [ ] Mengimplementasikan pattern Transactional Outbox menggunakan database PostgreSQL dengan polling efisien (`SELECT FOR UPDATE SKIP LOCKED`) atau Debezium CDC engine.
- [ ] Menulis Testcontainers-based integration test untuk memverifikasi keandalan microservices saat dependent systems (Kafka, PostgreSQL, Redis) down.
- [ ] Mengonfigurasi OpenTelemetry Java Agent atau Micrometer Tracing untuk menyuntikkan trace ID ke MDC (Mapped Diagnostic Context) SLF4J dan context header HTTP/Kafka.
- [ ] Mendiagnosis dan mengurai insiden *cascading failure* di production melalui analisis distributed traces, network metrics, dan Java thread dump analysis.
- [ ] Merancang arsitektur asynchronous event-driven yang kebal terhadap kegagalan *out-of-order execution* dan *duplicate event delivery*.