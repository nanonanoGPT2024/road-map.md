# BAB 08: Observability, Metrics & Production Operations
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengonfigurasi dan mengoperasikan **Micrometer Observation API** pada Spring Boot 3.x untuk menyatukan pengumpulan metrik (*metrics*) dan pelacakan terdistribusi (*distributed tracing*) dalam satu abstraksi terpadu.
- Mengimplementasikan propagasi konteks (*context propagation*) W3C Trace Context lintas batas jaringan (*network boundaries*) dan konkurensi asinkron (*thread pools*, Virtual Threads).
- Merancang custom metrics tingkat lanjut (**DistributionSummary**, **Timer** dengan SLA/percentiles, **Counter**, dan **Gauge**) dengan memitigasi risiko *cardinality explosion*.
- Mengonfigurasi Kubernetes Probes (*Liveness* & *Readiness*) berbasis custom `HealthIndicator` dan transisi `ApplicationAvailability` secara terisolasi.
- Mengamankan endpoint Spring Boot Actuator di tingkat arsitektur jaringan (*mTLS*, reverse proxy) dan otorisasi berbasis Spring Security.
- Mengimplementasikan structured logging JSON terintegrasi tracing context (MDC) yang siap dikonsumsi oleh OpenSearch/Elasticsearch tanpa *log parsing overhead*.

---

### 2. Prerequisites

Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- **Core Spring Framework & Spring Boot 3.x**: Arsitektur Inversion of Control (IoC), Dependency Injection, Auto-configuration.
- **Java 21 LTS**: Konkurensi dasar, CompletableFuture, dan pemahaman Virtual Threads (Project Loom).
- **Protokol Jaringan & HTTP**: Pemahaman header HTTP, status code, model klien-server, dan arsitektur microservices.
- **Docker & Kubernetes Dasar**: Pod lifecycle, container resource constraints, port forwarding, dan file manifes deployment.
- **Bab 08 Module 01**: Dasar-dasar Spring Boot Actuator, Micrometer dasar, dan integrasi Prometheus endpoint default.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Unifikasi Observabilitas: Micrometer Observation API
Pada Spring Boot 3.x, paradigma instrumentasi bergeser dari penggunaan API terpisah (misalnya Micrometer untuk metrik dan Spring Cloud Sleuth untuk tracing) menjadi satu model deklaratif dan programatik tunggal: **Micrometer Observation API**.

```
                           +---------------------------+
                           |  Micrometer Observation   |
                           |          API              |
                           +-------------+-------------+
                                         |
                +------------------------+------------------------+
                |                                                 |
                v                                                 v
    +-----------------------+                         +-----------------------+
    | MeterObservation      |                         | TracingObservation    |
    | Handler (Metrics)     |                         | Handler (Tracing)     |
    +-----------+-----------+                         +-----------+-----------+
                |                                                 |
                v                                                 v
    +-----------------------+                         +-----------------------+
    |   Prometheus Meter    |                         |  OpenTelemetry /      |
    |       Registry        |                         |     Brave Tracer      |
    +-----------+-----------+                         +-----------+-----------+
                |                                                 |
                v                                                 v
       Prometheus TSDB                                      Jaeger / Tempo
```

Ketika sebuah unit kerja dibungkus ke dalam sebuah `Observation`:
1. `ObservationRegistry` mengeksekusi rantai `ObservationHandler`.
2. `MeterObservationHandler` menterjemahkan siklus hidup *observation* (start, stop, error) menjadi `Timer` dan `Counter` pada `MeterRegistry`.
3. `TracingObservationHandler` menterjemahkan siklus hidup yang sama menjadi `Span` (start, annotate, error tag, finish) melalui tracer backend (OpenTelemetry atau Brave).
4. Data metrik dan trace secara otomatis memiliki relasi silang (*correlation*) melalui **Exemplars**, di mana trace ID disuntikkan langsung ke bucket histogram Prometheus.

#### 3.2 Context Propagation & W3C Trace Context
Tracing terdistribusi bergantung pada kemampuan propagasi metadata lintas batas thread dan proses jaringan. Standar yang digunakan adalah **W3C Trace Context**:
- `traceparent`: `version-trace_id-parent_id-trace_flags` (contoh: `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`).
- `tracestate`: Data pasangan *key-value* spesifik vendor sistem tracing.

Secara internal, `ContextRegistry` dari library `io.micrometer:context-propagation` mengelola transfer thread-local variable saat task dialihkan ke thread pool lain atau saat menggunakan reaktif/virtual thread. Jika transfer ini gagal, trace context terputus (*trace split*), menghasilkan trace ID baru yang terisolasi dan menghilangkan visibilitas rantai dependensi end-to-end.

#### 3.3 Kubernetes Probe Lifecycle & Actuator Internals
Spring Boot memisahkan status kesehatan aplikasi menjadi dua konsep Kubernetes:
1. **Liveness Probe** (`/actuator/health/liveness`): Menentukan apakah container harus di-restart oleh kubelet. Memvalidasi status internal runtime (contoh: deadlock, JVM corrupted state). Terikat pada `LivenessState.CORRECT`.
2. **Readiness Probe** (`/actuator/health/readiness`): Menentukan apakah aplikasi siap menerima traffic routing dari Kubernetes Service. Jika unhealthy, Pod dikeluarkan dari endpoints routing tanpa membunuh container. Terikat pada `ReadinessState.ACCEPTING_TRAFFIC`.

Secara arsitektural, delegasi pemeriksaan dilakukan oleh `ApplicationAvailability` interface yang mempublikasikan event `AvailabilityChangeEvent`. Indikator eksternal seperti database, message broker, atau HTTP clients **hanya boleh** memengaruhi *Readiness Probe*, bukan *Liveness Probe*. Pelanggaran atas prinsip ini akan memicu *cascading failure* di seluruh cluster k8s.

---

### 4. Why & What

| Dimensi | Mengapa Dibutuhkan (Why) | Apa yang Diimplementasikan (What) |
| :--- | :--- | :--- |
| **Korelasi Data** | Metrik memberi tahu *kapan* dan *komponen apa* yang bermasalah; Tracing menjelaskan *mengapa* komponen tersebut gagal. | Penggabungan Trace ID dan Span ID ke dalam logs via MDC dan ke dalam Prometheus metrics via **Exemplars**. |
| **Reliabilitas K8s** | Crash pada dependensi eksternal (misal PostgreSQL down) tidak boleh mematikan container aplikasi secara rekursif (*crash loop*). | Custom `ReadinessState` handler yang menghentikan penerimaan traffic pod tanpa merusak pod lifecycle (*graceful shedding*). |
| **Keamanan Sistem** | Endpoint actuator mengekspos topologi heap, metadata env, thread dump, dan konfigurasi sensitif. | Hardening Actuator: port isolasi internal, network-level ingress filtering, dan segmentasi RBAC via Spring Security. |
| **Efisiensi Log Engine**| Log teks bebas (*unstructured log*) memerlukan parsing RegEx intensif di Logstash/Fluentd yang membebani CPU. | **Logstash Logback Encoder** untuk memproduksi JSON terstruktur native dengan *zero-regex consumption*. |

---

### 5. How (Workflow Detail)

Alur penanganan HTTP request dari gateway hingga monitoring backend:

```
[Client Request] 
      │ (Headers: traceparent=00-abc...-01)
      ▼
[Reverse Proxy / Ingress] ── (TLS Termination & Routing)
      ▼
[Tomcat / Netty Engine]
      ▼
[ObservationFilter / TraceFilter]
      ├─ Ekstraksi W3C traceparent dari HTTP Request Header
      ├─ Inisialisasi Span & TraceContext di ThreadLocal / ContextSnapshot
      ├─ Injeksi traceId & spanId ke SLF4J MDC
      ▼
[SecurityFilterChain] ────── (RBAC Validation: Permit vs Deny)
      ▼
[DispatcherServlet -> Controller -> Service Layer]
      ├─ Eksekusi Business Logic
      ├─ Custom Observation (@Observed / ObservationRegistry)
      │     ├─ Record Timer Execution
      │     ├─ Record Metric DistributionSummary
      │     └─ Append Span Event / Tags
      ▼
[Outgoing Infrastructure (Database / WebClient)]
      ├─ ClientRequest Observation
      ├─ Injeksi W3C Header ke downstream request
      ▼
[Response Pipeline]
      ├─ Finalisasi Span (Duration, Error Tagging)
      ├─ Stop Observation
      ├─ Clear MDC
      ▼
[Asynchronous Scrape / Push]
      ├─ Prometheus Engine menarik endpoint /actuator/prometheus
      │     └─ Metrik disajikan beserta Exemplar (Trace ID)
      └─ OpenTelemetry Exporter mendorong Span ke Tempo/Jaeger (OTLP gRPC)
```

---

### 6. Analogy & Diagram ASCII

#### 6.1 Analogi Sistem
Bayangkan observabilitas aplikasi enterprise seperti sistem **Penerbangan Maskapai Komersial**:
- **Metrics (Prometheus)**: Panel instrumen di kokpit (Speedometer, Altimeter, Fuel Gauge). Memberi tahu *kondisi agregat real-time* secara instan. Mengetahui konsumsi bahan bakar naik 20% tidak menjelaskan penumpang mana yang menyebabkan muatan berlebih.
- **Distributed Tracing (Tempo/Jaeger)**: *Boarding pass* unik penumpang. Dari bandara asal (Frontend), security check (API Gateway), bagasi (Worker Thread), hingga boarding gate (Database). Anda dapat melacak rute tepat satu penumpang tertentu di tengah ribuan penumpang lain.
- **Logs (Loki/Elasticsearch)**: Percakapan kokpit dengan ATC dan catatan suara black-box. Menggambarkan detail menit-ke-menit peristiwa yang terjadi.
- **Exemplars**: Tombol di speedometer yang ketika ditekan langsung menampilkan *boarding pass* penumpang spesifik yang terbang pada saat kecepatan kritis terjadi.

#### 6.2 Visualisasi Trace Context Propagation

```
Trace ID: 4bf92f3577b34da6a3ce929d0e0e4736 (Global untuk seluruh flow)

[API Gateway Service] 
Span ID: a1b2c3d4e5f60001
Duration: 120ms
│
├── (HTTP Call dengan header traceparent: ...a1b2c3d4e5f60001...)
│
▼
[Order Processing Service]
Span ID: b2c3d4e5f6a10002 (Parent: a1b2c3d4e5f60001)
Duration: 95ms
│
├── [Database Query: INSERT INTO orders...]
│   Span ID: c3d4e5f6a1b20003 (Parent: b2c3d4e5f6a10002)
│   Duration: 15ms
│
└── [Kafka Producer: publish order-created]
    Span ID: d4e5f6a1b2c30004 (Parent: b2c3d4e5f6a10002)
    Duration: 8ms
    │
    └── (Kafka Record Header: traceparent: ...d4e5f6a1b2c30004...)
        │
        ▼
    [Notification Service - Kafka Consumer]
    Span ID: e5f6a1b2c3d40005 (Parent: d4e5f6a1b2c30004)
    Duration: 30ms
```

---

### 7. Implementation: Simple & Practical Example

Struktur implementasi enterprise-grade berbasis Spring Boot 3.3+, Java 21, dan Micrometer.

#### 7.1 Dependensi `build.gradle.kts`
```kotlin
plugins {
    java
    id("org.springframework.boot") version "3.3.4"
    id("io.spring.dependency-management") version "1.1.6"
}

java {
    toolchain {
        languageVersion.set(JavaLanguageVersion.of(21))
    }
}

dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.springframework.boot:spring-boot-starter-actuator")
    implementation("org.springframework.boot:spring-boot-starter-security")
    implementation("org.springframework.boot:spring-boot-starter-aop")

    // Metrics & Monitoring
    implementation("io.micrometer:micrometer-registry-prometheus")
    
    // Distributed Tracing via OpenTelemetry Protocol (OTLP)
    implementation("io.micrometer:micrometer-tracing-bridge-otel")
    implementation("io.opentelemetry:opentelemetry-exporter-otlp")
    implementation("io.micrometer:context-propagation")

    // Structured Logging
    implementation("net.logstash.logback:logstash-logback-encoder:7.4")

    testImplementation("org.springframework.boot:spring-boot-starter-test")
}
```

#### 7.2 Structured Logging Configuration (`src/main/resources/logback-spring.xml`)
Mengonfigurasi log JSON terstruktur yang otomatis menyuntikkan trace metadata dari MDC:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration scan="false">
    <springProperty scope="context" name="appName" source="spring.application.name" defaultValue="spring-app"/>

    <appender name="CONSOLE_JSON" class="ch.qos.logback.core.ConsoleAppender">
        <encoder class="net.logstash.logback.encoder.LoggingEventCompositeJsonEncoder">
            <providers>
                <timestamp>
                    <timeZone>UTC</timeZone>
                </timestamp>
                <version/>
                <logLevel/>
                <loggerName/>
                <threadName/>
                <message/>
                <mdc>
                    <includeMdcKeyName>traceId</includeMdcKeyName>
                    <includeMdcKeyName>spanId</includeMdcKeyName>
                </mdc>
                <pattern>
                    <pattern>
                        {
                            "app": "${appName}",
                            "class": "%logger{40}",
                            "stack_trace": "%xEx"
                        }
                    </pattern>
                </pattern>
            </providers>
        </encoder>
    </appender>

    <root level="INFO">
        <appender-ref ref="CONSOLE_JSON"/>
    </root>
</configuration>
```

#### 7.3 Konfigurasi Observabilitas & Keamanan Actuator

```java
package com.enterprise.observability.config;

import io.micrometer.core.aop.TimedAspect;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.observation.ObservationRegistry;
import io.micrometer.observation.aop.ObservedAspect;
import org.springframework.boot.actuate.autoconfigure.security.servlet.EndpointRequest;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.web.SecurityFilterChain;

@Configuration(proxyBeanMethods = false)
@EnableWebSecurity
public class ObservabilitySecurityConfig {

    @Bean
    public ObservedAspect observedAspect(ObservationRegistry observationRegistry) {
        return new ObservedAspect(observationRegistry);
    }

    @Bean
    public TimedAspect timedAspect(MeterRegistry registry) {
        return new TimedAspect(registry);
    }

    @Bean
    @Order(1)
    public SecurityFilterChain actuatorSecurityFilterChain(HttpSecurity http) throws Exception {
        http
            .securityMatcher(EndpointRequest.toAnyEndpoint())
            .authorizeHttpRequests(authorize -> authorize
                // Endpoint liveness dan readiness terbuka untuk k8s kubelet
                .requestMatchers(EndpointRequest.to("health")).permitAll()
                .requestMatchers(EndpointRequest.to("info")).permitAll()
                // Prometheus scraper diizinkan lewat role spesifik atau segmen internal
                .requestMatchers(EndpointRequest.to("prometheus")).hasRole("METRICS_SCRAPER")
                // Endpoint kritis lainnya memerlukan proteksi administratif
                .anyRequest().hasRole("ADMIN")
            )
            .httpBasic(Customizer.withDefaults())
            .csrf(csrf -> csrf.disable());

        return http.build();
    }
}
```

#### 7.4 Custom Health Indicator (Isolasi Liveness vs Readiness)

```java
package com.enterprise.observability.health;

import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.boot.actuate.health.Status;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.Socket;

/**
 * Memvalidasi kesiapan koneksi broker pihak ketiga.
 * Hanya memengaruhi Readiness probe via Health aggregation.
 */
@Component("paymentGatewayHealthIndicator")
public class PaymentGatewayHealthIndicator implements HealthIndicator {

    private static final String GATEWAY_HOST = "10.0.12.50";
    private static final int GATEWAY_PORT = 8443;
    private static final int TIMEOUT_MS = 1500;

    @Override
    public Health health() {
        boolean reachable = checkSocketReachability(GATEWAY_HOST, GATEWAY_PORT, TIMEOUT_MS);

        if (!reachable) {
            return Health.status(Status.DOWN)
                    .withDetail("target_host", GATEWAY_HOST)
                    .withDetail("target_port", GATEWAY_PORT)
                    .withDetail("error", "Socket connection timeout to external payment provider")
                    .build();
        }

        return Health.status(Status.UP)
                .withDetail("target_host", GATEWAY_HOST)
                .withDetail("latency_status", "OPTIMAL")
                .build();
    }

    private boolean checkSocketReachability(String host, int port, int timeout) {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress(host, port), timeout);
            return true;
        } catch (IOException ex) {
            return false;
        }
    }
}
```

#### 7.5 Production Service Menggunakan Micrometer Observation API

```java
package com.enterprise.observability.service;

import io.micrometer.core.instrument.DistributionSummary;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.observation.Observation;
import io.micrometer.observation.ObservationRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.concurrent.ThreadLocalRandom;

@Service
public class PaymentProcessingService {

    private static final Logger log = LoggerFactory.getLogger(PaymentProcessingService.class);

    private final ObservationRegistry observationRegistry;
    private final DistributionSummary paymentAmountSummary;

    public PaymentProcessingService(ObservationRegistry observationRegistry, MeterRegistry meterRegistry) {
        this.observationRegistry = observationRegistry;

        // Distribusi ukuran transaksi finansial (Custom DistributionSummary)
        this.paymentAmountSummary = DistributionSummary.builder("payment.transaction.amount")
                .description("Distribution of payment amounts processed")
                .baseUnit("IDR")
                .maximumExpectedValue(100_000_000.0) // 100 Juta
                .minimumExpectedValue(10_000.0)     // 10 Ribu
                .publishPercentiles(0.5, 0.75, 0.95, 0.99)
                .register(meterRegistry);
    }

    public PaymentResponse processPayment(PaymentRequest request) {
        // High-cardinality values (seperti request.transactionId()) DILARANG masuk tag metrik.
        // Micrometer Observation menangani Tracing Tags (High Cardinality) vs Metric Tags (Low Cardinality)
        return Observation.createNotStarted("payment.execution", this.observationRegistry)
                .lowCardinalityKeyValue("payment.provider", request.provider())
                .lowCardinalityKeyValue("payment.currency", request.currency())
                .highCardinalityKeyValue("payment.transaction.id", request.transactionId())
                .highCardinalityKeyValue("payment.customer.id", request.customerId())
                .observe(() -> executeTransactionFlow(request));
    }

    private PaymentResponse executeTransactionFlow(PaymentRequest request) {
        log.info("Processing transaction of amount {} via provider {}", request.amount(), request.provider());

        try {
            // Simulasi operasi I/O jaringan
            long duration = ThreadLocalRandom.current().nextLong(50, 300);
            Thread.sleep(duration);

            if ("FAIL".equalsIgnoreCase(request.provider())) {
                throw new IllegalStateException("Simulated upstream provider outage");
            }

            // Catat besaran uang yang diproses ke DistributionSummary
            paymentAmountSummary.record(request.amount().doubleValue());

            log.info("Transaction successfully committed");
            return new PaymentResponse(request.transactionId(), "SETTLED", "SUCCESS");

        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            log.error("Transaction execution interrupted", e);
            throw new RuntimeException("Thread interrupted during transaction execution", e);
        } catch (Exception ex) {
            log.error("Transaction execution failed for id: {}", request.transactionId(), ex);
            throw ex;
        }
    }

    public record PaymentRequest(
            String transactionId,
            String customerId,
            String provider,
            String currency,
            BigDecimal amount
    ) {}

    public record PaymentResponse(
            String transactionId,
            String status,
            String message
    ) {}
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: FinTech Settlement Engine (10.000 TPS)
Sebuah bank digital memproses kliring pembayaran dengan volume 10.000 TPS pada jendela waktu pukul 17:00 - 18:00 WIB. Sistem mereka mengalami fenomena berkala: *P99 latency melonjak dari 45ms ke 12.000ms tanpa adanya kenaikan penggunaan CPU atau memori JVM yang terdeteksi di grafis metrik standar Prometheus*.

#### Akar Masalah (*Root Cause Analysis*)
1. **Prometheus Scraping Gap**: Prometheus dikonfigurasi dengan interval scrape 15 detik. Lonjakan latensi bersifat mikro (*micro-bursting*) yang disamarkan oleh rata-rata metrik (agregasi rate/irate).
2. **Context Leakage pada ForkJoinPool**: Settlement engine mengeksekusi validasi KYC dan Anti-Money Laundering (AML) secara paralel menggunakan Java `CompletableFuture.supplyAsync()` tanpa mewariskan `MDC` dan `TraceContext`. Akibatnya, trace terputus saat request berpindah ke worker pool.
3. **Ketiadaan Korelasi Exemplars**: Tim engineer tidak dapat melacak request persis mana yang mencapai 12.000ms karena trace ID hilang dan tidak ada sampel konkret di grafik histogram P99.

#### Arsitektur Solusi
1. **Implementasi `ContextExecutorService`**: Membungkus standard thread pools menggunakan `ContextExecutorService.wrap()` dari library Micrometer Context Propagation, memastikan trace context bermigrasi mulus ke worker thread.
2. **Exemplar Integration**: Mengaktifkan OpenTelemetry Histogram Exemplar Reservoir pada Spring Boot Actuator. Setiap bucket Prometheus `payment_execution_seconds_bucket` menyimpan trace ID sampel yang mewakili transaksi dengan durasi > 10 detik.
3. **Penerapan Dynamic Sampling**: Konfigurasi `Sampler` berbasis Parent-based trace ratio (10% untuk transaksi normal, 100% untuk transaksi yang melebihi ambang batas latensi 2.000ms).

```
Grafana Histogram (Prometheus)
Latensi P99 Spike: 12.4s ─────────> [DOT DI GRAFIK: Exemplar Ditemukan]
                                             │
                                             │ Klik "Query Tempo"
                                             ▼
Grafana Tempo (Trace Engine)
Trace ID: 0e8913ac99dfba10
Span Tree:
├─ [POST /api/v1/settlement] 12.4s
│  ├─ [LocalValidator] 1.2ms
│  ├─ [ForkJoin Task: KYC Engine] 12.38s  <--- BOTTLENECK TERDETEKSI
│  │  └─ [HTTP POST to Eksternal Dukcapil API] 12.35s (Timeout gateway 15s)
│  └─ [Database Batch Insert] 8.1ms
```
Hasil temuan: Penyebab sebenarnya adalah degradasi jaringan pada downstream API Dukcapil pihak ketiga yang tidak memiliki fallback circuit breaker berbasis timeout ketat.

---

### 9. Trade-offs

| Dimensi | Opsi A | Opsi B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Tracing Sampling Rate** | **100% Sampling** (Semua request ditrace) | **Probabilistic Sampling** (1% - 5% request ditrace) | **100% Sampling** memberikan visibilitas absolut namun membebani I/O jaringan, storage backend (Tempo/Jaeger), dan overhead CPU serialisasi OTLP hingga 15-20% pada high load. **Probabilistic** memangkas cost storage sebesar ~95% namun berisiko melewatkan transaksi anomali langka. |
| **Metric Tag Cardinality** | **High Cardinality** (Menyertakan `user_id`, `order_id` di Prometheus tags) | **Low Cardinality** (Hanya menyertakan status code, method, exception class) | Menyimpan nilai unik tak terbatas pada Prometheus tag memicu **Cardinality Explosion**, menyebabkan RAM Prometheus TSDB melonjak eksponensial hingga OOM crash. Identitas unik harus diarahkan ke Tracing Span Tags atau Structured Logs, bukan Metrics. |
| **Health Probe Evaluation** | **Deep Checking** (Ping DB, Redis, Kafka di endpoint `/liveness`) | **Shallow Checking** (Hanya cek internal JVM status di `/liveness`, dependensi di `/readiness`) | Deep Checking pada Liveness Probe adalah antipattern fatal: kegagalan sementara koneksi database akan membuat Kubernetes me-restart seluruh Pod container secara serentak, memicu *Restart Storm* dan memperburuk down time sistem. |
| **Log Format** | **Plain Text Standard** (`%d %level %logger - %msg`) | **Logstash JSON Encoder** | JSON log memerlukan alokasi string buffer sedikit lebih besar per baris, tetapi mengeliminasi 100% kebutuhan pipeline parser Logstash yang memakan resource komputasi tinggi di sisi cluster log aggregator. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Cardinality Explosion pada Prometheus Tags
- **Kesalahan Fatal**: Menambahkan dynamic ID seperti email user, nomor pesanan, atau dynamic URL path ke dalam Micrometer tags.
  ```java
  // SALAH BESAR - MEMBUAT PROMETHEUS CRASH
  meterRegistry.counter("http.requests", "user_id", user.getId()).increment();
  ```
- **Solusi**: Gunakan tag diskrit dengan domain terbatas (maksimum puluhan variasi status).
  ```java
  // BENAR
  meterRegistry.counter("http.requests", "tier", user.getSubscriptionTier()).increment();
  ```

#### 10.2 Broken Tracing Context pada Asynchronous Threads
- **Gejala**: Log di dalam `CompletableFuture` atau thread `@Async` kehilangan `traceId` dan `spanId`, atau memunculkan traceId lama dari thread pooling yang di-reuse.
- **Troubleshooting**: Inject Spring `AsyncTaskExecutor` yang telah dibungkus `ContextPropagatingTaskDecorator`.
  ```java
  @Bean
  public TaskDecorator contextPropagatingTaskDecorator() {
      return ContextSnapshotFactory.builder().build()::captureAll;
  }
  ```

#### 10.3 Blocking Call di Dalam Custom HealthIndicator
- **Gejala**: Kubelet gagal membaca `/actuator/health` tepat waktu (`Readiness probe failed: Get ... net/http: request canceled while waiting for connection (Client.Timeout exceeded)`). Pod dikeluarkan secara keliru dari traffic.
- **Troubleshooting**: Set network socket timeout yang sangat agresif (maksimal 1.000ms - 1.500ms) di setiap internal health probe. Jangan pernah biarkan health check memblokir request thread pool default Tomcat.

---

### 11. Best Practices (Production Checklist)

- [ ] **Actuator Port Isolation**: Pisahkan port actuator dari port utama aplikasi (`management.server.port=8081` vs `server.port=8080`). Blokir port 8081 pada Edge Ingress Controller publik.
- [ ] **Liveness vs Readiness Hygiene**: Pastikan indikator koneksi eksternal (DB, Redis, Message Queue) dikecualikan dari kelompok liveness:
  ```properties
  management.endpoint.health.group.liveness.include=livenessState
  management.endpoint.health.group.readiness.include=readinessState,db,diskSpace
  ```
- [ ] **Metric Whitelisting & Denying**: Gunakan `MeterFilter` untuk menonaktifkan metrik bawaan yang tidak terpakai guna menghemat footprint memori registry.
- [ ] **Explicit Histogram Bucketing**: Hindari infinite default buckets. Definisikan SLA buckets eksplisit pada request HTTP:
  ```properties
  management.metrics.distribution.slo.http.server.requests=50ms,100ms,250ms,500ms,1s,3s
  ```
- [ ] **Graceful Shutdown**: Aktifkan graceful shutdown agar koneksi in-flight selesai sebelum kontainer dihancurkan oleh K8s SIGTERM:
  ```properties
  server.shutdown=graceful
  spring.lifecycle.timeout-per-shutdown-phase=30s
  ```

---

### 12. Hands-on Practice

Buatlah struktur direktori kerja berikut pada repositori lokal Anda:
```
hands-on/m02/
├── build.gradle.kts
└── src
    └── main
        ├── java
        │   └── com
        │       └── enterprise
        │           └── observability
        │               ├── ObservabilityApp.java
        │               ├── controller
        │               │   └── OrderController.java
        │               ├── service
        │               │   └── OrderProcessingService.java
        │               └── health
        │                   └── ExternalWarehouseHealthIndicator.java
        └── resources
            ├── application.yml
            └── logback-spring.xml
```

#### Langkah 1: Buat Konfigurasi `application.yml`
```yaml
server:
  port: 8080
  shutdown: graceful

management:
  server:
    port: 8081 # Port terisolasi untuk management
  endpoints:
    web:
      exposure:
        include: "health,info,metrics,prometheus"
  endpoint:
    health:
      show-details: when_authorized
      probes:
        enabled: true
      group:
        liveness:
          include: livenessState
        readiness:
          include: readinessState,externalWarehouseHealthIndicator
  metrics:
    tags:
      application: ${spring.application.name}
    distribution:
      percentiles-histogram:
        http.server.requests: true
      slo:
        order.processing.time: 100ms, 300ms, 500ms, 1000ms
  tracing:
    sampling:
      probability: 1.0 # 100% untuk lab lokal

spring:
  application:
    name: order-tracking-system
```

#### Langkah 2: Implementasi Controller dengan Context Exposure
Simpan di `src/main/java/com/enterprise/observability/controller/OrderController.java`:

```java
package com.enterprise.observability.controller;

import com.enterprise.observability.service.OrderProcessingService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/orders")
public class OrderController {

    private static final Logger log = LoggerFactory.getLogger(OrderController.class);
    private final OrderProcessingService processingService;

    public OrderController(OrderProcessingService processingService) {
        this.processingService = processingService;
    }

    @PostMapping("/{orderId}/checkout")
    public ResponseEntity<String> checkout(@PathVariable String orderId, @RequestParam double amount) {
        log.info("Received checkout request for order: {}", orderId);
        processingService.processOrder(orderId, amount);
        return ResponseEntity.ok("Order successfully queued and processed");
    }
}
```

#### Langkah 3: Uji Coba & Verifikasi
1. Jalankan aplikasi via terminal:
   ```bash
   ./gradlew bootRun
   ```
2. Picu HTTP traffic:
   ```bash
   curl -X POST "http://localhost:8080/api/v1/orders/ORD-9902/checkout?amount=450000"
   ```
3. Periksa log konsol JSON. Pastikan field `traceId` dan `spanId` terisi:
   ```json
   {"@timestamp":"2023-10-27T08:12:00.123Z","level":"INFO","message":"Received checkout request for order: ORD-9902","traceId":"653b6f80a4f526b772c72b2ffc821102","spanId":"72c72b2ffc821102","app":"order-tracking-system"}
   ```
4. Periksa ketersediaan metrics & exemplar di endpoint Actuator yang terisolasi:
   ```bash
   curl -s http://localhost:8081/actuator/prometheus | grep "order_processing_time"
   ```
5. Periksa status probes Kubernetes:
   ```bash
   curl -s http://localhost:8081/actuator/health/liveness
   curl -s http://localhost:8081/actuator/health/readiness
   ```

---

### 13. Exercise

#### Level Easy
Konfigurasikan sebuah custom `MeterFilter` bean untuk menolak (*deny*) semua metrik JVM memory buffer pool (`jvm.buffer.count` dan `jvm.buffer.total.capacity`) agar tidak masuk ke registry Prometheus guna meminimalisasi footprint penyimpanan data metrik.

#### Level Medium
Buat sebuah REST Client menggunakan `RestClient` (tersedia di Spring Boot 3.2+) yang mengonsumsi endpoint publik dummy. Pastikan client tersebut mengotomatisasi propagasi header tracing W3C (`traceparent`) menggunakan autokonfigurasi `RestClient.Builder` yang disuntikkan Spring. Buktikan melalui verifikasi mock HTTP server bahwa header `traceparent` benar-benar terkirim.

#### Level Hard
Rancang dan implementasikan custom `AvailabilityChangeException` listener yang memantau performa thread execution. Jika persentase thread pool Tomcat active mencapai > 90% selama 3 kali pengecekan berturut-turut, sistem harus mempublikasikan `AvailabilityChangeEvent` yang memodifikasi status aplikasi menjadi `ReadinessState.REFUSING_TRAFFIC`. Begitu utilisasi turun kembali di bawah 70%, kembalikan status ke `ReadinessState.ACCEPTING_TRAFFIC` secara dinamis tanpa me-restart Pod.

---

### 14. Challenge

**Skenario**: Anda memimpin tim arsitektur pada platform logistik dengan throughput tinggi. Aplikasi memproses event logistik asynchronous dari Apache Kafka. Konsumen memproses *batch* order yang berisi ratusan sub-order dari database lokal.
- **Tuntutan**:
  1. Buat pipeline yang mengekstrak metadata trace W3C dari Kafka Header payload.
  2. Mulai sebuah **Observation Baru** bertipe span child untuk setiap entitas order individual yang diproses di dalam batch loop.
  3. Pastikan MDC diperbarui per sub-order sehingga setiap baris log memiliki `traceId` parent Kafka, tetapi `spanId` unik untuk unit kerja sub-order tersebut.
  4. Lakukan sanitasi data: Tag metrik hanya boleh mencatat ukuran batch dan kategori logistik (`DOMESTIC`, `INTERNATIONAL`). Dilarang keras mengekspos identifier order ke tag metrik.
  5. Kirimkan laporan metrik latency agregat per kategori logistik menggunakan Micrometer `Timer` yang terkonfigurasi percentiles histogram (P50, P90, P99).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Apa fungsi dari W3C `traceparent` header dalam distributed tracing?
   - A. Menyimpan payload data transaksi dalam bentuk JSON terenkripsi.
   - B. Menyediakan format standar propagasi metadata identitas tracing lintas platform.
   - C. Menggantikan token otentikasi JWT pada incoming HTTP request.
   - D. Menjadi storage unik metrik histogram Prometheus.

2. Manakah komponen yang BERTANGGUNG JAWAB langsung menyatukan metrik dan pelacakan terdistribusi pada Spring Boot 3.x?
   - A. Spring Cloud Sleuth API.
   - B. Micrometer Observation API.
   - C. Dropwizard Metrics Core.
   - D. Logback MDC Context Handler.

3. Kapan sebuah container Kubernetes me-restart Pod yang bermasalah?
   - A. Ketika `/actuator/health/readiness` mengembalikan status DOWN.
   - B. Ketika `/actuator/health/liveness` mengembalikan status DOWN.
   - C. Ketika metrik CPU memicu alert 85%.
   - D. Ketika log format JSON mengalami parsing failure.

4. Apa dampak negatif langsung dari *Cardinality Explosion* pada Prometheus TSDB?
   - A. Kehilangan korelasi Trace ID pada distributed tracing.
   - B. Kegagalan parser Logstash pada pembacaan file log.
   - C. Lonjakan eksponensial konsumsi RAM pada instance Prometheus hingga terjadi Out of Memory crash.
   - D. Penurunan throughput jaringan Tomcat thread pool secara permanen.

5. Manakah konfigurasi properti yang benar untuk memindahkan endpoint Actuator ke port yang berbeda demi alasan keamanan jaringan?
   - A. `server.actuator.port=8081`
   - B. `management.server.port=8081`
   - C. `spring.actuator.management.port=8081`
   - D. `management.endpoints.network.port=8081`

#### Bagian 2: Intermediate (Pilihan Ganda)
6. Mengapa dependensi eksternal seperti database PostgreSQL **TIDAK BOLEH** didaftarkan ke dalam pemeriksaan Liveness Probe?
   - A. Karena PostgreSQL tidak mendukung arsitektur socket non-blocking.
   - B. Karena kegagalan DB akan menyebabkan kubelet me-restart aplikasi secara berulang-ulang (*crash loop back-off*), membebani jaringan tanpa menyelesaikan masalah DB.
   - C. Karena Prometheus tidak memiliki permission untuk membaca status koneksi DataSource.
   - D. Karena status DOWN pada database otomatis menghentikan Tomcat servlet container.

7. Perhatikan potongan kode berikut:
   ```java
   Observation.createNotStarted("job.run", registry)
       .lowCardinalityKeyValue("tenant", tenantId)
       .highCardinalityKeyValue("order.id", orderId)
       .observe(runnable);
   ```
   Bagaimana Micrometer memproses kedua tag tersebut saat diekspor?
   - A. `tenant` masuk ke tracing span; `order.id` masuk ke Prometheus metrics.
   - B. Keduanya masuk ke Prometheus metrics dan tracing span.
   - C. `tenant` masuk ke Prometheus metrics dan tracing span; `order.id` hanya masuk ke tracing span.
   - D. Keduanya otomatis diabaikan jika tidak didaftarkan di `application.yml`.

8. Bagaimana cara kerja **Exemplars** dalam menghubungkan Prometheus metrics dengan distributed tracing?
   - A. Exemplar menduplikasi seluruh log teks ke dalam database time-series Prometheus.
   - B. Exemplar mereferensikan sampel Trace ID spesifik langsung ke bucket data histogram metrik pada waktu scrape tertentu.
   - C. Exemplar mengubah payload span OpenTelemetry menjadi file grafik SVG visual.
   - D. Exemplar menyimpan snapshot heap dump saat sebuah request memicu exception HTTP 500.

9. Apa fungsi antarmuka `ContextSnapshotFactory` pada pustaka Micrometer Context Propagation?
   - A. Mengompresi payload request body agar hemat bandwidth saat tracing aktif.
   - B. Mengambil (*capture*) nilai ThreadLocal (seperti tracing context dan MDC) dan memulihkannya (*restore*) ke thread lain secara aman.
   - C. Menghubungkan database pool connection ke context security Spring.
   - D. Mengubah format structured logging Logstash menjadi format XML secara dinamis.

10. Mengapa structured logging berbasis JSON lebih direkomendasikan pada arsitektur microservices enterprise dibandingkan logging berbasis pola teks (PatternLayout)?
    - A. JSON log memakan memori JVM 80% lebih sedikit daripada string plain text.
    - B. Menghilangkan komputasi RegEx yang intensif pada log aggregator (Elasticsearch/Logstash) karena log di-ingest langsung sebagai structured object.
    - C. Format JSON mengizinkan enkripsi otomatis tanpa membutuhkan sertifikat TLS.
    - D. Format teks biasa tidak diizinkan oleh standar kepatuhan PCI-DSS.

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario 1**: Cluster Kubernetes Anda mendeteksi bahwa aplikasi sering menerima alert `OOMKilled` (Exit Code 137). Saat diinvestigasi, metrik heap memory JVM normal (hanya terpakai 40%), tetapi konsumsi memory non-heap (native/resident set size) Pod terus meningkat hingga melampaui Kubernetes memory limits. Analisis akar masalah observabilitas apa yang paling tepat?
12. **Skenario 2**: Sebuah microservice memproses pembayaran batch. Saat terjadi insiden kegagalan transaksi massal, seluruh log yang dicetak pada batch worker menampilkan `traceId` yang bernilai sama persis untuk ratusan transaksi pelanggan yang berbeda. Di mana kesalahan konfigurasi context propagation terjadi?
13. **Skenario 3**: Tim sekuritas perusahaan menemukan bahwa attacker berhasil memetakan topologi jaringan internal dan membaca konfigurasi environment variabel sistem. Endpoint mana yang berpotensi menjadi celah kebocoran, dan apa 3 langkah remediasi arsitektural yang wajib diambil?

---

### Jawaban dan Pembahasan Kuis

#### Bagian 1 & 2
1. **B** - `traceparent` adalah spesifikasi standar W3C untuk melacak request lintas batas jaringan tanpa bergantung pada vendor tertentu.
2. **B** - Micrometer Observation API adalah arsitektur Spring Boot 3.x yang menyatukan instrumentasi metrik dan tracing di bawah satu API.
3. **B** - Kubelet hanya me-restart container apabila endpoint yang didaftarkan pada `livenessProbe` mengembalikan respons non-2xx (atau timeout).
4. **C** - Prometheus TSDB menyimpan time series per kombinasi unik key-value tag. Dynamic tag tak terbatas melipatgandakan time series hingga memori habis (OOM).
5. **B** - Properti `management.server.port` memisahkan socket HTTP Actuator dari port traffic bisnis aplikasi.
6. **B** - Dependensi eksternal yang down harus ditangani oleh *Readiness probe* untuk menghentikan routing lalu lintas; me-restart aplikasi (*Liveness*) tidak akan memperbaiki database yang down dan memicu *restart storm*.
7. **C** - Micrometer memisahkan `lowCardinalityKeyValue` (untuk Metrics & Tracing) dari `highCardinalityKeyValue` (Tracing saja) guna memitigasi ledakan metrik.
8. **B** - Exemplars mengasosiasikan trace ID individual secara presisi dengan bucket histogram data agregat pada output scrape OpenMetrics.
9. **B** - `ContextSnapshotFactory` menangkap context ThreadLocal untuk dipropagasikan lintas context switching (Thread pools / Virtual Threads).
10. **B** - Log JSON menghilangkan kebutuhan regex parser pada log shipper (Filebeat/Logstash), memotong konsumsi CPU klaster logging secara signifikan.

#### Bagian 3: Analisis Kasus Produksi
11. **Analisis Skenario 1**:
    - **Akar Masalah**: Pustaka OpenTelemetry / Micrometer Tracing secara default dapat mengalokasikan byte buffer secara native melalui gRPC sender (Netty native memory) untuk mengekspor spans ke tempo/collector. Jika collector tracing lambat merespons atau drop network, buffer native memory akan terus menumpuk di luar JVM heap.
    - **Tindakan**: Konfigurasi exporter batch size, pasang queue limit (`management.otlp.tracing.export.queue-size`), atur timeout ketat pada exporter gRPC, atau beralih ke HTTP sender dengan explicit bounded memory limits.
12. **Analisis Skenario 2**:
    - **Akar Masalah**: Worker batch menggunakan kembali (*reusing*) thread yang sama dari pool tanpa membersihkan atau membuat konteks baru (`TraceContext` leaking). Akibatnya, `traceId` yang pertama kali disuntikkan ke dalam thread tersebut melekat selamanya di SLF4J MDC.
    - **Tindakan**: Bungkus eksekusi loop per-transaksi menggunakan `Observation.createNotStarted(...)` atau panggil `tracer.nextSpan()` secara manual, dan pastikan blok try-finally mengeksekusi penutupan span serta pembersihan MDC (`MDC.clear()` / `span.end()`).
13. **Analisis Skenario 3**:
    - **Akar Celah**: Endpoint Actuator `/actuator/env` dan `/actuator/beans` terekspos ke jaringan publik tanpa otentikasi.
    - **Langkah Remediasi**:
      1. Isolasi port Actuator (`management.server.port=8081`) dan cegah port tersebut dirouting oleh Ingress controller ke internet publik.
      2. Terapkan Spring Security filter chain ketat pada `EndpointRequest.toAnyEndpoint()` dengan otentikasi mTLS atau basic auth berbasis RBAC peran `ADMIN`.
      3. Matikan endpoint sensitif yang tidak terpakai melalui `management.endpoints.web.exposure.include=health,info,prometheus`, secara eksplisit menolak eksposur `env`, `heapdump`, dan `beans`.

---

### 16. Summary

```
                       ARSIKTEKTUR PRODUKSI OBSERVABILITAS
+-----------------------------------------------------------------------------+
|                            Spring Boot 3.x Engine                           |
|                                                                             |
|  [Incoming HTTP / Kafka]                                                    |
|           │ (W3C traceparent)                                               |
|           ▼                                                                 |
|  [Micrometer Observation API] ─────────────────┐                            |
|           ├─ Low-Cardinality Tags               ├─ High-Cardinality Tags     |
|           ▼                                     ▼                           |
|  [Prometheus MeterRegistry]           [OpenTelemetry Tracer Bridge]         |
|           │                                     │                           |
|           ├─ Metrics + Exemplar (TraceID) ◄─────┘ (Trace Correlation)       |
|           │                                     │                           |
|           ▼                                     ▼                           |
|   /actuator/prometheus                    Tempo / Jaeger                    |
|           │                                     ▲                           |
|           ▼                                     │ (Trace Query)             |
|   Prometheus TSDB                               │                           |
|           └─────────── Grafana Dashboard ───────┘                           |
|                                                                             |
|  [SLF4J + MDC Context] ────> [Logstash JSON Encoder] ────> Log Engine       |
|                                                                             |
|  [Kubernetes Probes]                                                        |
|   ├─ /actuator/health/liveness  ───> Internal JVM State Only                |
|   └─ /actuator/health/readiness ───> External Dependencies Aggregation     |
+-----------------------------------------------------------------------------+
```

Observabilitas kelas enterprise bukan sekadar menambahkan dependensi visualisasi dashboard, melainkan penerapan disiplin rekayasa sistem yang terpadu:
1. **Unifikasi API**: Menggantikan instrumentasi manual yang terfragmentasi dengan **Micrometer Observation API**, yang secara atomik mensinkronkan metrik dan tracing.
2. **Higienitas Kardinalitas**: Menjaga integritas server monitoring (Prometheus) dengan mengisolasi identitas data transaksi bervolume tinggi (*high-cardinality data*) eksklusif ke tracing spans dan JSON logs, menjauhkan data tersebut dari tags metrik.
3. **Resiliensi Deployment**: Memisahkan secara tegas antara kesehatan runtime aplikasi (*Liveness*) dengan kesiapan infrastruktur pendukung (*Readiness*) untuk mencegah fenomena bencana *cascading Pod restarts* di klaster Kubernetes produksi.