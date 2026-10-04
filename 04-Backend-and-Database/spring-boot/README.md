# Kurikulum Master Enterprise Spring Boot: Dari Fondasi Arsitektur Hingga Cloud-Native Engineering

---

## 1. Course Overview & Mindset

### Filosofi Kurikulum
Spring Boot sering disalahpahami sebagai "framework instan berbasis magis" (*magic annotations*). Kurikulum ini dirancang untuk membongkar abstraksi tersebut hingga ke level mekanika internal JVM, membedah siklus hidup *ApplicationContext*, memetakan eksekusi *Bytecode Manipulation*, serta menyingkap cara kerja auto-configuration secara deterministik.

Kurikulum ini mengadopsi standar rekayasa perangkat lunak skala enterprise (Fortune 500 & FinTech-grade), di mana keandalan sistem, latensi rendah, konsistensi data terdistribusi (*distributed transactions*), serta observabilitas tingkat tinggi merupakan persyaratan mutlak.

```
       [ Client Request ]
               │
               ▼
┌─────────────────────────────┐
│    Security Filter Chain    │  <- Stateless Authentication (OAuth2 / JWT)
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│      DispatcherServlet      │  <- Reflection & HandlerMapping
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│       Service Layer         │  <- Declarative Transaction (@Transactional Proxy)
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  Data Access (Spring Data)  │  <- HikariCP Pool & Hibernate L1/L2 Cache
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Distributed Infrastructure  │  <- Kafka Broker, Redis Cache, RDBMS
└─────────────────────────────┘
```

### Rekayasa Berpikir (The Engineering Mindset)
1. **Zero-Magic Tolerance:** Memahami secara mendalam *bagaimana* dan *mengapa* sebuah anotasi bekerja via proxy dinamis (`CGLIB` dan `JDK Dynamic Proxies`).
2. **Defensive Enterprise Architecture:** Mengisolasi *domain logic* dari infrastruktur eksternal, mengimplementasikan *resilience patterns* (Circuit Breaker, Rate Limiting, Retry), dan mencegah kegagalan fatal seperti kebocoran memori (*OOM*) dan *connection pool starvation*.
3. **Mechanical Sympathy:** Memahami karakteristik alokasi memori JVM, *Garbage Collection overhead*, serta optimasi I/O non-blocking demi throughput maksimal.

---

## 2. Learning Roadmap

```plaintext
Enterprise Spring Boot Roadmap
│
├── [BAB 01] Core Architecture, IoC, & Inversion of Control Internals
│
├── [BAB 02] Configuration Engine, Profiles, & Bootstrapping Mechanism
│
├── [BAB 03] Data Access Layer & Persistence Architecture
│
├── [BAB 04] RESTful API Engineering & Web Layer Resilience
│
├── [BAB 05] Enterprise Security Architecture (Spring Security 6+ & OAuth2)
│
├── [BAB 06] Reactive Systems & Asynchronous Processing with Spring WebFlux
│
├── [BAB 07] Event-Driven Architecture & Enterprise Messaging
│
├── [BAB 08] Observability, Metrics, & Production Operations
│
├── [BAB 09] Enterprise Testing Strategy: Unit to Distributed Integration
│
└── [BAB 10] Cloud-Native Deployment, GraalVM Native Images, & High-Scale Tuning
```

---

## 3. Navigasi Detail Bab

### [BAB 01: Core Architecture, IoC, & Inversion of Control Internals](./01-core-architecture-and-ioc-engine)
Membedah fondasi kompilasi dan *runtime* Spring Framework, mekanisme *reflection*, serta siklus hidup *bean* dari inisialisasi hingga terminasi.

*   [Modul 01: Anatomi ApplicationContext & BeanFactory](./01-core-architecture-and-ioc-engine/01-spring-container-internals.md)
    *   *Topik:* Siklus hidup `BeanFactory`, mutasi metadata via `BeanFactoryPostProcessor`, registrasi `BeanDefinition`, dan hierarki konteks modular.
*   [Modul 02: Siklus Hidup Bean, Inisialisasi, & Proxy CGLIB/JDK](./01-core-architecture-and-ioc-engine/02-bean-lifecycle-and-proxy-mechanisms.md)
    *   *Topik:* `BeanPostProcessor`, fase `@PostConstruct` / `InitializingBean`, dynamic runtime bytecode generation menggunakan CGLIB vs JDK Dynamic Proxy, pencegahan *circular dependency trap*.
*   [Modul 03: Mekanika Dekonstruksi Anotasi Komposisi & Conditional Scanning](./01-core-architecture-and-ioc-engine/03-deep-dive-conditional-configuration.md)
    *   *Topik:* Implementasi kustom `ConditionEvaluator`, pengujian logika evaluasi `@ConditionalOnClass`, `@ConditionalOnMissingBean`, dan urutan pemindaian *classpath*.

---

### [BAB 02: Configuration Engine, Profiles, & Bootstrapping Mechanism](./02-configuration-and-bootstrapping)
Menganalisis proses bootstrapping `SpringApplication` dari pemanggilan `main()` hingga aplikasi siap menerima trafik produksi.

*   [Modul 01: Siklus Hidup Eksekusi `SpringApplication.run()` Step-by-Step](./02-configuration-and-bootstrapping/01-spring-application-run-cycle.md)
    *   *Topik:* `SpringApplicationRunListener`, fase parsing `Environment`, penanganan kegagalan inisialisasi konteks (*failure analyzers*), serta *graceful shutdown hook*.
*   [Modul 02: Externalized Configuration & Type-Safe Properties](./02-configuration-and-bootstrapping/02-type-safe-configuration-properties.md)
    *   *Topik:* `@ConfigurationProperties`, validasi `JSR-380` deklaratif pada konfigurasi, precedence ordering environment, *profile tree inheritance*, dan mutasi konfigurasi dinamis.
*   [Modul 03: Desain dan Pembuatan Custom Auto-Configuration Starter](./02-configuration-and-bootstrapping/03-custom-autoconfiguration-starters.md)
    *   *Topik:* Standardisasi `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`, optimasi urutan `@AutoConfigureBefore`/`@AutoConfigureAfter`, pembuatan *starter kit library* internal perusahaan.

---

### [BAB 03: Data Access Layer & Persistence Architecture](./03-data-access-and-persistence)
Mendesain lapisan persistensi yang tangguh, efisien, bebas masalah konkurensi data, serta tahan terhadap beban transaksi tinggi.

*   [Modul 01: Hibernate ORM Internals & Spring Data JPA Deep Dive](./03-data-access-and-persistence/01-spring-data-jpa-hibernate-internals.md)
    *   *Topik:* *Persistence Context (First Level Cache)*, *Dirty Checking engine*, eliminasi *N+1 query problem* menggunakan `EntityGraph` & *join fetch*, serta optimasi paginasi keyset/slice.
*   [Modul 02: Arsitektur Transaksi, Isolasi ACID, & HikariCP Tuning](./03-data-access-and-persistence/02-high-performance-hikaricp-and-connection-management.md)
    *   *Topik:* Transaksi deklaratif `@Transactional`, *propagation modes*, *isolation levels*, *phantom reads mitigation*, kalkulasi kapasitas *HikariCP connection pool* berbasis metrik core hardware.
*   [Modul 03: Skema Migrasi Enterprise: Flyway & Liquibase](./03-data-access-and-persistence/03-schema-migrations-flyway-liquibase.md)
    *   *Topik:* Strategi *zero-downtime database deployment* (Expand/Contract pattern), *stateful schema versioning*, dan penguncian tabel (*table locks*) dalam lingkungan multi-instance.

---

### [BAB 04: RESTful API Engineering & Web Layer Resilience](./04-restful-api-engineering)
Membangun web layer yang mampu menangani ratusan ribu konkurensi request dengan integritas payload tinggi dan arsitektur non-blocking.

*   [Modul 01: Anatomi DispatcherServlet & HTTP Handler Pipeline](./04-restful-api-engineering/01-spring-mvc-dispatcher-servlet-deep-dive.md)
    *   *Topik:* Pemetaan *HandlerMapping*, integrasi *HandlerAdapter*, implementasi kustom *HandlerInterceptor*, serta arsitektur *HttpMessageConverter* serialisasi Jackson.
*   [Modul 02: Global Error Architecture, RFC 7807, & Input Validation](./04-restful-api-engineering/02-enterprise-validation-error-handling.md)
    *   *Topik:* Implementasi RFC 7807 / RFC 9457 `ProblemDetail`, pemusatan eksepsi menggunakan `@ControllerAdvice`, dan interceptor validasi kustom *payload sanitization*.
*   [Modul 03: API Versioning Strategy, HATEOAS, & Virtual Threads (Java 21+)](./04-restful-api-engineering/03-api-versioning-and-hypermedia-hateoas.md)
    *   *Topik:* URI/Header versioning governance, HATEOAS REST maturity Level 3, dan benchmarking adopsi *Project Loom Virtual Threads* pada Spring Boot 3.2+.

---

### [BAB 05: Enterprise Security Architecture (Spring Security 6+ & OAuth2)](./05-enterprise-security-spring-security)
Penerapan arsitektur zero-trust, kontrol akses granular, dan pengamanan endpoint sesuai standar PCI-DSS dan OWASP Top 10.

*   [Modul 01: Arsitektur SecurityFilterChain Internals](./05-enterprise-security-spring-security/01-security-filter-chain-architecture.md)
    *   *Topik:* Filter chaining sequencing, delegasi `DelegatingFilterProxy`, otentikasi kustom berbasis `AuthenticationProvider`, dan mitigasi serangan CSRF, CORS, Session Fixation.
*   [Modul 02: Stateless JWT Authentication & OAuth2 / OIDC Resource Server](./05-enterprise-security-spring-security/02-stateless-jwt-and-oauth2-resource-server.md)
    *   *Topik:* Verifikasi asymmetric signature (JWKS/RSA), integrasi dengan identity provider enterprise (Keycloak / Okta), token revocation lists, dan claims enrichment.
*   [Modul 03: Granular Method Security, SpEL, & Role-Based Access Control (RBAC)](./05-enterprise-security-spring-security/03-method-security-and-fine-grained-rbac.md)
    *   *Topik:* Otorisasi tingkat deklaratif dengan `@PreAuthorize` / `@PostAuthorize`, evaluasi Spring Expression Language (SpEL), dan dynamic permission evaluation melalui `PermissionEvaluator`.

---

### [BAB 06: Reactive Systems & Asynchronous Processing with Spring WebFlux](./06-reactive-programming-spring-webflux)
Pergeseran paradigma dari model *thread-per-request* menuju komputasi reaktif sepenuhnya untuk sistem dengan latensi ultra-rendah.

*   [Modul 01: Project Reactor Core (Mono, Flux, & Reactive Streams)](./06-reactive-programming-spring-webflux/01-project-reactor-mono-flux-fundamentals.md)
    *   *Topik:* Paradigma Event Loop Netty, mekanisme *Backpressure*, thread switching menggunakan `Schedulers`, *error recovery operators*, dan pencegahan *blocking calls*.
*   [Modul 02: Reactive WebFlux & Non-Blocking Database via R2DBC](./06-reactive-programming-spring-webflux/02-reactive-webflux-r2dbc-pipeline.md)
    *   *Topik:* Perancangan API non-blocking via `WebClient`, pipeline database reaktif R2DBC, *Connection Pooling R2DBC*, dan streaming response *Server-Sent Events (SSE)*.

---

### [BAB 07: Event-Driven Architecture & Enterprise Messaging](./07-event-driven-and-messaging)
Desain integrasi terdistribusi asynchronous yang reliable, fault-tolerant, dan menjamin integritas data antar-service.

*   [Modul 01: Spring Domain Events & Transactional Event Listeners](./07-event-driven-and-messaging/01-domain-events-application-events.md)
    *   *Topik:* Pemisahan domain via `ApplicationEventPublisher`, sinkronisasi `@TransactionalEventListener` pada fase *AFTER_COMMIT*, serta orkestrasi internal domain event.
*   [Modul 02: Event Streaming dengan Apache Kafka & RabbitMQ](./07-event-driven-and-messaging/02-message-driven-kafka-rabbitmq.md)
    *   *Topik:* Consumer groups, deserialisasi Avro/JSON schema registry, *Dead Letter Queues (DLQ)*, dan penanganan idempotensi pesan menggunakan Redis distributed lock.
*   [Modul 03: Reliable Messaging via Transactional Outbox Pattern](./07-event-driven-and-messaging/03-transactional-outbox-pattern.md)
    *   *Topik:* Penulisan atomik database dan *event store*, polling log CDC (*Change Data Capture* via Debezium) terintegrasi Spring Boot, dan pencegahan *dual-write distributed failures*.

---

### [BAB 08: Observability, Metrics, & Production Operations](./08-observability-and-production-readiness)
Menjamin transparansi penuh kondisi aplikasi di lingkungan produksi melalui tiga pilar observabilitas: Metrics, Tracing, dan Logging.

*   [Modul 01: Custom Spring Boot Actuator Endpoints & Health Indicators](./08-observability-and-production-readiness/01-actuator-health-endpoints-customization.md)
    *   *Topik:* Desain *HealthIndicator* kustom untuk downstream dependencies, eksposur *Actuator endpoints* aman via JMX/Web, dan kustomisasi info metadata runtime.
*   [Modul 02: Micrometer, Prometheus, & Grafana Production Dashboarding](./08-observability-and-production-readiness/02-micrometer-prometheus-metrics-collection.md)
    *   *Topik:* Custom Timers, Gauges, Counters, pemantauan *HikariCP connection saturation*, *JVM GC pauses*, serta integrasi visualisasi Prometheus & Grafana.
*   [Modul 03: Distributed Tracing: Micrometer Tracing, OpenTelemetry, & Zipkin](./08-observability-and-production-readiness/03-distributed-tracing-opentelemetry.md)
    *   *Topik:* Propagasi W3C TraceContext di seluruh batas jaringan HTTP/Kafka, konfigurasi *Baggage Fields*, pelacakan latensi antar-service via Jaeger/Zipkin.

---

### [BAB 09: Enterprise Testing Strategy: Unit to Distributed Integration](./09-enterprise-testing-strategy)
Standar pengujian piramida testing menyeluruh tanpa mock yang rapuh, menjamin stabilitas saat *continuous deployment*.

*   [Modul 01: Testing Slice Architecture (`@DataJpaTest`, `@WebMvcTest`)](./09-enterprise-testing-strategy/01-slice-testing-mockmvc-datajpatest.md)
    *   *Topik:* Optimasi eksekusi pengujian dengan context caching, pengujian isolasi web layer via `MockMvc`, dan verifikasi SQL statements via `@DataJpaTest`.
*   [Modul 02: Real-World Testing Menggunakan Testcontainers](./09-enterprise-testing-strategy/02-real-world-integration-testcontainers.md)
    *   *Topik:* Integrasi Testcontainers untuk PostgreSQL, Apache Kafka, dan Redis pada fase CI; penghapusan total dependensi mock in-memory H2.
*   [Modul 03: ArchUnit & Contract Testing via Spring Cloud Contract](./09-enterprise-testing-strategy/03-architectural-fitness-functions-archunit.md)
    *   *Topik:* Penegakan arsitektur heksagonal menggunakan *Fitness Functions (ArchUnit)*, pencegahan pelanggaran paket *layering*, dan Consumer-Driven Contract Testing.

---

### [BAB 10: Cloud-Native Deployment, GraalVM Native Images, & High-Scale Tuning](./10-cloud-native-graalvm-optimization)
Transformasi aplikasi Spring Boot menjadi sistem berkinerja tinggi, berorientasi kontainer, serta optimalisasi sumber daya runtime.

*   [Modul 01: Ahead-Of-Time (AOT) Compilation & GraalVM Native Image](./10-cloud-native-graalvm-optimization/01-graalvm-native-images-aot-engine.md)
    *   *Topik:* Eliminasi overhead runtime JVM, *AOT code generation*, konfigurasi *Reachability Metadata*, *instant startup* (<50ms), dan reduksi konsumsi memori (*RSS*).
*   [Modul 02: Containerization Terbaik, OCI Images, & Kubernetes Readiness](./10-cloud-native-graalvm-optimization/02-containerization-docker-k8s-readiness.md)
    *   *Topik:* Cloud-Native Buildpacks, optimasi layer Dockerfile multi-stage, konfigurasi *Liveness* & *Readiness Probes*, dan handling sinyal OS `SIGTERM`.
*   [Modul 03: Advanced Performance Tuning: Memory Profiling & GC Optimization](./10-cloud-native-graalvm-optimization/03-jvm-memory-profiling-performance-tuning.md)
    *   *Topik:* Analisis heap dump (Eclipse Memory Analyzer), thread dump profiling, tuning ZGC / G1GC untuk skenario throughput tinggi dan latensi rendah.

---

## 4. Capstone Project: Enterprise Distributed Core-Banking & Settlement Engine

Di akhir kurikulum ini, peserta akan membangun satu sistem berskala enterprise: **Global Ledger & Real-time Settlement Platform**.

```
                           [ API Gateway ]
                                  │
                  ┌───────────────┴───────────────┐
                  ▼                               ▼
       ┌─────────────────────┐         ┌─────────────────────┐
       │   Account Service   │         │  Transaction Engine │
       └──────────┬──────────┘         └──────────┬──────────┘
                  │                               │
                  │        ┌──────────────┐       │
                  └───────>│ Kafka Broker │<──────┘
                           └──────┬───────┘
                                  │
                                  ▼
                       ┌─────────────────────┐
                       │  Settlement Worker  │ (Outbox Processor)
                       └──────────┬──────────┘
                                  │
                                  ▼
                         [ PostgreSQL Shards ]
```

### Kebutuhan Arsitektur dan Spesifikasi Sistem:
1. **Core Processing Engine:**
   * Desain Multi-Service berbasis Spring Boot 3.x / Java 21 LTS dengan *Virtual Threads*.
   * Eksekusi transaksi debit/kredit yang *idempotent* menggunakan Redis distributed lock dan DB row-level locking (*Pessimistic Locking*).
2. **Data Consistency & Resiliency:**
   * Mengimplementasikan arsitektur **Transactional Outbox Pattern** untuk koordinasi transfer antar-bank dengan jaminan konsistensi *at-least-once*.
   * Menggunakan Debezium CDC dan Apache Kafka untuk menyebarkan domain event secara asinkron.
   * Migrasi skema database zero-downtime menggunakan **Flyway**.
3. **Security Standards:**
   * Autentikasi dan otorisasi menggunakan Keycloak via OAuth2 / OIDC dengan otentikasi stateless (JWT) bertanda tangan RS256.
   * Kontrol akses berbasis peran (RBAC) pada setiap endpoint dengan *Method Security* terenkripsi mTLS antar-service.
4. **Observability Stack:**
   * Pemantauan metrik penuh: integrasi Micrometer dengan Prometheus dan visualisasi performa pada Grafana.
   * Pelacakan terdistribusi (*Distributed Tracing*) ujung-ke-ujung menggunakan OpenTelemetry dan Jaeger.
5. **Quality Assurance & Deployment:**
   * Cakupan pengujian unit dan slice > 85% dengan implementasi Testcontainers untuk pengujian integrasi database dan broker pesan.
   * Aturan arsitektural diverifikasi secara otomatis menggunakan **ArchUnit**.
   * Pipeline deployment cloud-native: image multi-stage OCI teroptimasi yang siap dideploy pada klaster Kubernetes dengan *probes readiness/liveness* terkonfigurasi.