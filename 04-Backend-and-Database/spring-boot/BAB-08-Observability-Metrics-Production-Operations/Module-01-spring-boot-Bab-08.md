# Bab 08 Module 01: Observability, Metrics, & Production Operations

---

## 01. Identitas Modul
* **Mata Kuliah / Jalur Pembelajaran:** Backend & Enterprise Architecture Engineering
* **Kategori:** 04-Backend-and-Database
* **Teknologi Utama:** Spring Boot 3.3+, Spring Boot Actuator, Micrometer, Prometheus, OpenTelemetry (OTel), Logback, Grafana Tempo/Loki
* **Level Keterampilan:** Advanced (Senior Engineer / Principal Architect)
* **Prasyarat Konseptual:** 
  * Pemahaman mendalam arsitektur mikroservis & HTTP runtime engine (Tomcat/Netty).
  * Penguasaan Spring Boot IoC, AOP, dan Filter Chain.
  * Pemahaman dasar tentang distributed tracing, model data time-series (metrics), dan structured logging.
* **Waktu Pengerjaan:** 8 - 12 Jam (Teori, Analisis Kode, Lab, dan Benchmarking)

---

## 02. Learning Objectives
1. **Mendesain dan Mengonfigurasi Telemetri Holistik:** Mengintegrasikan Spring Boot Actuator, Micrometer Core, dan OpenTelemetry SDK untuk menangkap tiga pilar observabilitas (Metrics, Logs, Traces) secara terpadu.
2. **Implementasi Distributed Tracing & W3C Trace Context:** Mengonfigurasi propagasi konteks trace (`traceparent`, `tracestate`) lintas batas mikroservis menggunakan Micrometer Tracing dan OTel Bridge.
3. **Mengembangkan Custom Metrics & Dynamic Gauges:** Membangun instrumen kustom (`Counter`, `Timer`, `Gauge`, `DistributionSummary`) untuk Business-Level Metrics dan System Saturation.
4. **Mengeksekusi Dynamic Runtime Observability:** Melakukan inspeksi thread dumps, memory heap dumps, dynamic log-level switching, dan health grouping tanpa melakukan restart pod/service.
5. **Menerapkan Hardening Keamanan pada Actuator:** Mengamankan production endpoint dari kebocoran data sensitif (*credential scrubbing*) menggunakan Spring Security RBAC dan network isolation.

---

## 03. Concept Map Diagram ASCII

```
+========================================================================================================+
|                                    APPLICATION RUNTIME ENGINE (JVM)                                    |
|                                                                                                        |
|  +--------------------------------------------------------------------------------------------------+  |
|  |                                  BUSINESS & INFRASTRUCTURE LAYER                                 |  |
|  |   [ Inbound REST/gRPC ] ---> [ Service Layer / Domain ] ---> [ Outbound WebClient / DB Layer ]   |  |
|  +--------------------------------------------------------------------------------------------------+  |
|         |                                      |                                      |                |
|         v (Automatic & Manual Instrument)      v (Observation API / AOP)              v (Context Prop) |
|  +--------------------------------------------------------------------------------------------------+  |
|  |                               MICROMETER OBSERVATION REGISTRY                                    |  |
|  |  - ObservationHandler                                                                            |  |
|  |  - KeyValues Provider (Low/High Cardinality Tags)                                                |  |
|  +--------------------------------------------------------------------------------------------------+  |
|            |                                            |                                |             |
|            v                                            v                                v             |
|  +--------------------+                     +----------------------+           +--------------------+  |
|  |   METRICS ENGINE   |                     |    TRACING BRIDGE    |           | STRUCTURED LOGGING |  |
|  | (Micrometer Core)  |                     |  (Micrometer Tracing |           | (Logback JSON /    |  |
|  |                    |                     |   + OTel Tracer)     |           |  MDC Integration)  |  |
|  +--------------------+                     +----------------------+           +--------------------+  |
|            |                                            |                                |             |
+============|============================================|================================|=============+
             |                                            |                                |
             v (/actuator/prometheus)                     v (OTLP / gRPC)                  v (Stdout / Filebeat)
+---------------------------+                +-------------------------+      +--------------------------+
|    PROMETHEUS ENGINE      |                |   OPENTELEMETRY / TEMPO |      |     GRAFANA LOKI / ELK   |
| (Pull Model Time-Series)  |                |  (Distributed Tracing)  |      |   (Log Aggregation Log)  |
+---------------------------+                +-------------------------+      +--------------------------+
             \                                            |                               /
              \                                           |                              /
               +------------------------------------------+-----------------------------+
                                                          |
                                                          v
                                            +---------------------------+
                                            |     GRAFANA DASHBOARD     |
                                            |  (Single Pane of Glass)   |
                                            +---------------------------+
```

---

## 04. Mengapa Relevan
Dalam arsitektur *distributed systems* skala enterprise, kegagalan sistem bersifat non-deterministik (*partial failures*, *network jitter*, *memory leaks*, dan *cascading timeouts*). Pendekatan *monitoring* konvensional (berbasis *blackbox ping* atau *log grepping*) tidak lagi memadai untuk menjawab pertanyaan: *"Mengapa 1% permintaan pengguna mengalami latency > 2 detik pada jam sibuk?"*

Observabilitas (*Observability*) memungkinkan tim *engineering* memahami status internal sistem hanya berdasarkan data eksternal yang diemisikan (Metrics, Traces, Logs). Spring Boot 3 mengadopsi standar industri melalui integrasi native **Micrometer Observation API**, menggabungkan metrik dan pelacakan terdistribusi di bawah satu abstraksi deklaratif. 

Menguasai modul ini penting untuk:
1. Menghindari *blind spot* operasional di lingkungan Kubernetes.
2. Meminimalisasi *Mean Time to Detect* (MTTD) dan *Mean Time to Resolve* (MTTR).
3. Mencegah degradasi performa akibat *overhead instrumentation* yang buruk.
4. Memenuhi standar *Service Level Objectives* (SLO) dan *Service Level Indicators* (SLI).

---

## 05. Anatomi Konsep Inti

### 1. Tiga Pilar Observabilitas
* **Metrics (Aggregatable Data):** Representasi numerik yang diukur dalam interval waktu tertentu. Cocok untuk *alerting* dan visualisasi tren makro. Karakteristik utama: berbiaya penyimpanan rendah, *cardinality-sensitive*.
* **Traces (Request Lifecycles):** Representasi jalur eksekusi sebuah permintaan saat melewati berbagai *hop* layanan. Setiap trace terdiri dari kumpulan *Span* (unit kerja dengan *start time*, *duration*, dan *tags*).
* **Logs (Event Details):** Catatan tekstual terstruktur (*JSON-formatted*) yang memuat kejadian tertentu lengkap dengan metadata konteks (`traceId`, `spanId`, `tenantId`).

### 2. Spring Boot Actuator Architecture
Actuator mengekspos endpoint internal JVM dan aplikasi melalui HTTP/JMX. Pada Spring Boot 3:
* `/actuator/health`: Menggunakan arsitektur komposit (`CompositeHealthContributor`) untuk merangkum status liveness & readiness.
* `/actuator/metrics`: Menampilkan metrik in-memory yang terdaftar di `MeterRegistry`.
* `/actuator/prometheus`: Mengekspos metrik dalam format eksposisi Prometheus (scraping target).
* `/actuator/env`, `/actuator/threaddump`, `/actuator/heapdump`: Runtime debugging endpoints.

### 3. Micrometer Observation API
Sebelum Spring Boot 3, tracing (Spring Cloud Sleuth) dan metrics (Micrometer) diinisialisasi secara terpisah. **Micrometer Observation** menyatukan keduanya. Ketika sebuah `Observation` dibuat:
1. `Timer` / `Counter` metrik dipicu.
2. `Span` baru dibuat dan dimasukkan ke dalam `Tracer`.
3. `MDC` (Mapped Diagnostic Context) Logback dimodifikasi secara otomatis untuk mencakup `traceId` dan `spanId`.

### 4. Cardinality: The Silent Killer
* **Low Cardinality Tags:** Tag dengan rentang nilai terbatas yang dapat diprediksi (misal: `http_status_code` = 200, 400, 500; `payment_method` = CC, VA, EWALLET). **Aman untuk Metrics dan Traces.**
* **High Cardinality Tags:** Tag dengan nilai dinamis tak terbatas (misal: `user_id`, `order_id`, `email`, `credit_card_number`). **Hanya boleh masuk ke Tracing Spans atau Structured Logs!** Memasukkan tag *high-cardinality* ke dalam Prometheus Metrics akan meledakkan memori Prometheus TSDB (*out-of-memory crash*).

---

## 06. Panduan Implementasi Step-by-Step

### Langkah 1: Konfigurasi Dependency Management (`pom.xml`)
Gunakan Spring Boot 3.3.x dengan dependensi Actuator, Prometheus, dan OpenTelemetry Tracer.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.3.0</version>
        <relativePath/>
    </parent>
    <groupId>com.enterprise.observability</groupId>
    <artifactId>payment-gateway</artifactId>
    <version>1.0.0</version>
    <name>payment-gateway</name>

    <properties>
        <java.version>21</java.version>
    </properties>

    <dependencies>
        <!-- Spring Boot Starters -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-security</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-aop</artifactId>
        </dependency>

        <!-- Metrics Engine: Prometheus -->
        <dependency>
            <groupId>io.micrometer</groupId>
            <artifactId>micrometer-registry-prometheus</artifactId>
            <scope>runtime</scope>
        </dependency>

        <!-- Tracing: Micrometer Tracing Bridge with OpenTelemetry -->
        <dependency>
            <groupId>io.micrometer</groupId>
            <artifactId>micrometer-tracing-bridge-otel</artifactId>
        </dependency>

        <!-- Exporter: OpenTelemetry Protocol (OTLP) to Collector / Tempo -->
        <dependency>
            <groupId>io.opentelemetry</groupId>
            <artifactId>opentelemetry-exporter-otlp</artifactId>
        </dependency>

        <!-- Structured Logging JSON -->
        <dependency>
            <groupId>net.logstash.logback</groupId>
            <artifactId>logstash-logback-encoder</artifactId>
            <version>7.4</version>
        </dependency>
        
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <optional>true</optional>
        </dependency>
    </dependencies>
</project>
```

### Langkah 2: Production Configuration (`application.yml`)
Konfigurasikan eksposisi Actuator, OTLP tracing export, sampling probability, dan integrasi logging MDC.

```yaml
server:
  port: 8080
  shutdown: graceful

spring:
  application:
    name: payment-engine-service
  lifecycle:
    timeout-per-shutdown-phase: 30s

management:
  server:
    port: 8081 # Isolasi port internal Actuator dari network public
  endpoints:
    web:
      exposure:
        include: health, info, prometheus, metrics, loggers, threaddump
      base-path: /actuator
  endpoint:
    health:
      show-details: when_authorized
      roles: SYSTEM_ADMIN
      probes:
        enabled: true
      group:
        readiness:
          include: readinessState, db, diskSpace
        liveness:
          include: livenessState
    prometheus:
      enabled: true
  metrics:
    distribution:
      percentiles-histogram:
        http.server.requests: true
        payment.processing.time: true
      sla:
        http.server.requests: 50ms, 100ms, 250ms, 500ms, 1s
    tags:
      application: ${spring.application.name}
      environment: production
      region: ap-southeast-1
  tracing:
    sampling:
      probability: 0.1 # 10% Tracing Sampling Rate untuk beban produksi tinggi
    propagation:
      type: W3C # W3C Trace Context (traceparent, tracestate)
  otlp:
    tracing:
      endpoint: http://otel-collector.observability.svc.cluster.local:4318/v1/traces
      timeout: 2s

logging:
  pattern:
    level: "%5p [${spring.application.name:},%X{traceId:-},%X{spanId:-}]"
```

### Langkah 3: Konfigurasi Structured JSON Logging (`logback-spring.xml`)
Format log ke format JSON terstruktur untuk konsumsi langsung oleh Grafana Loki atau Elasticsearch.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <include resource="org/springframework/boot/logging/logback/defaults.xml"/>

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
                <context/>
                <pattern>
                    <pattern>
                        {
                            "traceId": "%mdc{traceId:-N/A}",
                            "spanId": "%mdc{spanId:-N/A}",
                            "app": "${spring.application.name:-unknown}",
                            "message": "%message",
                            "exception": "%ex{short}"
                        }
                    </pattern>
                </pattern>
                <stackTrace>
                    <throwableConverter class="net.logstash.logback.stacktrace.ShortenedThrowableConverter">
                        <maxDepthPerThrowable>30</maxDepthPerThrowable>
                        <maxLength>2048</maxLength>
                        <shortenedClassNameLength>20</shortenedClassNameLength>
                        <rootCauseFirst>true</rootCauseFirst>
                    </throwableConverter>
                </stackTrace>
            </providers>
        </encoder>
    </appender>

    <root level="INFO">
        <appender-ref ref="CONSOLE_JSON"/>
    </root>
</configuration>
```

---

## 07. Contoh Kasus Sederhana: Basic Custom Metrics

Implementasi dasar pelacakan jumlah transaksi yang masuk menggunakan Micrometer Core `Counter`.

```java
package com.enterprise.observability.service;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.stereotype.Service;

@Service
public class SimpleOrderService {

    private final Counter orderCounter;

    // Dependency injection MeterRegistry secara otomatis oleh Spring Boot
    public SimpleOrderService(MeterRegistry meterRegistry) {
        this.orderCounter = Counter.builder("ecommerce.orders.created.total")
                .description("Jumlah total order yang berhasil dibuat")
                .tag("service", "order-engine")
                .register(meterRegistry);
    }

    public void processOrder(String orderId) {
        // Business logic execution
        System.out.println("Processing order: " + orderId);
        
        // Menginkrementasi counter metrik
        this.orderCounter.increment();
    }
}
```

---

## 08. Implementasi Production-Grade Lengkap Kode

Berikut adalah implementasi sistem pembayaran enterprise yang menggunakan **Micrometer Observation API**, Custom Context Holder, Dynamic Metric Timers, Outbound Trace Propagation, dan Custom Health Indicators.

### 1. Payment Request DTO
```java
package com.enterprise.observability.dto;

import java.math.BigDecimal;

public record PaymentRequest(
        String transactionId,
        String customerId,
        BigDecimal amount,
        String paymentMethod,
        String idempotencyKey
) {}
```

### 2. Custom Business Observation Context
```java
package com.enterprise.observability.observation;

import io.micrometer.observation.Observation;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class PaymentObservationContext extends Observation.Context {
    private final String transactionId;
    private final String paymentMethod;
    private final double amount;
    private String gatewayStatus = "UNKNOWN";

    public PaymentObservationContext(String transactionId, String paymentMethod, double amount) {
        this.transactionId = transactionId;
        this.paymentMethod = paymentMethod;
        this.amount = amount;
    }
}
```

### 3. Custom Observation Handler (Audit & SLA Tracker)
```java
package com.enterprise.observability.observation;

import io.micrometer.observation.Observation;
import io.micrometer.observation.ObservationHandler;
import io.micrometer.tracing.Tracer;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class PaymentObservationHandler implements ObservationHandler<PaymentObservationContext> {

    private static final Logger log = LoggerFactory.getLogger(PaymentObservationHandler.class);
    private final Tracer tracer;

    @Override
    public boolean supportsContext(Observation.Context context) {
        return context instanceof PaymentObservationContext;
    }

    @Override
    public void onStart(PaymentObservationContext context) {
        log.info("Memulai observasi transaksi [ID: {}, Method: {}, Amount: {}]",
                context.getTransactionId(), context.getPaymentMethod(), context.getAmount());
    }

    @Override
    public void onStop(PaymentObservationContext context) {
        // Inject tag bernilai low-cardinality ke Tracing Span dan Meter Registry
        context.addLowCardinalityKeyValue(
                io.micrometer.common.KeyValue.of("payment.method", context.getPaymentMethod())
        );
        context.addLowCardinalityKeyValue(
                io.micrometer.common.KeyValue.of("payment.status", context.getGatewayStatus())
        );
        
        // High-cardinality HANYA di-attach pada tracing span
        context.addHighCardinalityKeyValue(
                io.micrometer.common.KeyValue.of("payment.transaction_id", context.getTransactionId())
        );

        if (this.tracer.currentSpan() != null) {
            this.tracer.currentSpan().tag("audit.sla_cleared", "true");
        }

        log.info("Transaksi selesai dieksekusi [Status: {}]", context.getGatewayStatus());
    }

    @Override
    public void onError(PaymentObservationContext context) {
        log.error("Kegagalan pada eksekusi observasi transaksi [ID: {}]", context.getTransactionId(), context.getError());
    }
}
```

### 4. Enterprise Custom Health Indicator
```java
package com.enterprise.observability.health;

import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.stereotype.Component;

import java.net.HttpURLConnection;
import java.net.URI;

@Component("paymentGatewayHealthIndicator")
public class PaymentGatewayHealthIndicator implements HealthIndicator {

    private static final String UPSTREAM_GATEWAY_PING = "https://core-bank.mock.internal/health";

    @Override
    public Health health() {
        try {
            long startTime = System.currentTimeMillis();
            boolean isReachable = checkConnection(UPSTREAM_GATEWAY_PING);
            long latency = System.currentTimeMillis() - startTime;

            if (isReachable) {
                return Health.up()
                        .withDetail("upstreamGateway", "CORE-BANK-SETTLEMENT")
                        .withDetail("latencyMs", latency)
                        .withDetail("circuitBreakerState", "CLOSED")
                        .build();
            } else {
                return Health.down()
                        .withDetail("upstreamGateway", "CORE-BANK-SETTLEMENT")
                        .withDetail("error", "Gateway response timed out")
                        .build();
            }
        } catch (Exception ex) {
            return Health.down(ex)
                    .withDetail("upstreamGateway", "CORE-BANK-SETTLEMENT")
                    .withDetail("reason", "Critical network route unreachable")
                    .build();
        }
    }

    private boolean checkConnection(String targetUrl) {
        // Simulasi koneksi socket check internal
        return true; 
    }
}
```

### 5. Payment Processing Service dengan Observation API
```java
package com.enterprise.observability.service;

import com.enterprise.observability.dto.PaymentRequest;
import com.enterprise.observability.observation.PaymentObservationContext;
import io.micrometer.observation.Observation;
import io.micrometer.observation.ObservationRegistry;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.UUID;

@Service
@RequiredArgsConstructor
public class EnterprisePaymentService {

    private static final Logger log = LoggerFactory.getLogger(EnterprisePaymentService.class);
    private final ObservationRegistry observationRegistry;

    public String processPayment(PaymentRequest request) {
        PaymentObservationContext context = new PaymentObservationContext(
                request.transactionId(),
                request.paymentMethod(),
                request.amount().doubleValue()
        );

        return Observation.createNotStarted("payment.execution", () -> context, observationRegistry)
                .observe(() -> {
                    log.info("Menjalankan settlement logika bisnis untuk trxId: {}", request.transactionId());
                    
                    try {
                        // Simulasi operasi database dan API call downstream
                        Thread.sleep(120); 

                        if (request.amount().doubleValue() > 100_000_000.0) {
                            throw new IllegalArgumentException("Limit transaksi harian terlampaui");
                        }

                        context.setGatewayStatus("SUCCESS");
                        return "SETTLED-" + UUID.randomUUID();
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                        context.setGatewayStatus("INTERRUPTED");
                        throw new RuntimeException("Transaksi terputus", e);
                    } catch (Exception ex) {
                        context.setGatewayStatus("FAILED");
                        throw ex;
                    }
                });
    }
}
```

### 6. Controller Layer
```java
package com.enterprise.observability.controller;

import com.enterprise.observability.dto.PaymentRequest;
import com.enterprise.observability.service.EnterprisePaymentService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/payments")
@RequiredArgsConstructor
public class PaymentController {

    private final EnterprisePaymentService paymentService;

    @PostMapping("/process")
    public ResponseEntity<String> executePayment(@RequestBody PaymentRequest request) {
        String referenceCode = paymentService.processPayment(request);
        return ResponseEntity.ok(referenceCode);
    }
}
```

---

## 09. Diagram Alur Kerja ASCII

```
[ Inbound HTTP Request: POST /api/v1/payments/process ]
                         |
                         v
   [ 1. Web Filter: Trace ID Propagation Injection ]
                         |
           (MDC: traceId=a1b2c3, spanId=f4e5d6)
                         |
                         v
   [ 2. ObservationRegistry.createNotStarted() ]
                         |
                         v
+------------------------+------------------------+
| 3. OnStart Phase: Audit Logging Initialization   |
+-------------------------------------------------+
                         |
                         v
       [ 4. Core Business Settlement Execution ]
                         |
           +-------------+-------------+
           |                           |
    (Success Flow)              (Exception Flow)
           |                           |
           v                           v
[ status = "SUCCESS" ]        [ status = "FAILED" ]
           |                           |
           +-------------+-------------+
                         |
                         v
+-------------------------------------------------+
| 5. OnStop Phase: Telemetry Metric Finalization  |
|    - Low Cardinality Tags -> MeterRegistry      |
|    - High Cardinality Tags -> Tracing Spans     |
|    - Increment: payment_execution_total         |
|    - Record Latency: payment_execution_duration |
+-------------------------------------------------+
                         |
                         v
    [ 6. Outbound HTTP Response + Tracing Headers ]
```

---

## 10. Analisis Trade-offs

| Pendekatan Observabilitas | Kelebihan | Kekurangan & Konsekuensi |
| :--- | :--- | :--- |
| **High Sampling Tracing (100%)** | Memberikan visualisasi 1:1 tanpa kehilangan data transaksi. Sangat baik untuk audit sistem dengan volume rendah. | Membebani I/O jaringan, *storage footprint* masif pada Jaeger/Tempo, dan menambah penalti latensi sebesar 3-7% pada skala beban tinggi. |
| **Probabilistic Sampling Tracing (5-10%)** | Mengurangi beban overhead I/O secara drastis dengan tetap menjaga akurasi distribusi statistik latensi pada traffic masif. | Transaksi edge-case / intermittent errors yang jarang terjadi berpotensi lolos dari trace capture. |
| **High Cardinality Metrics (Tagging IDs)** | Memungkinkan filtering metrik Prometheus hingga tingkat individu (`userId`, `orderId`). | **Anti-Pattern Berbahaya.** Mengakibatkan *Cardinality Explosion* yang mematikan *Time Series Database* (OOM crash) dan merusak indexing RAM Prometheus. |
| **Pull-Based Metrics (Prometheus Scraping)** | Aplikasi bersifat pasif, decoupling monitoring state, Prometheus mengontrol laju scraping sendiri. | Sulit menjangkau ephemerally-lived instances (contoh: serverless AWS Lambda) tanpa bantuan Pushgateway. |

---

## 11. Best Practices & Antipatterns

### ✅ Best Practices
1. **Pemisahan Port Manajemen:** Selalu alokasikan port terpisah untuk Actuator (misal: `management.server.port: 8081`) dan cegah *public internet ingress* merutekan request ke port tersebut.
2. **Standardisasi Trace Context:** Gunakan format W3C `traceparent` (`00-{traceId}-{spanId}-{flags}`) agar kompatibel dengan API Gateway, Service Mesh (Istio), dan platform downstream lainnya.
3. **Graceful Degradation Tracing:** Pastikan kegagalan saat mengekspor OTLP Spans ke remote collector bersifat *asynchronous* dan tidak memblokir rantai eksekusi *request thread*.
4. **Log Correlation ID:** Sisipkan selalu `traceId` dan `spanId` secara otomatis di konfigurasi layout logging via MDC provider.

### ❌ Antipatterns
1. **Exposing All Endpoints (`include: "*"`):** Membuka endpoint berbahaya seperti `/actuator/env`, `/actuator/heapdump`, atau `/actuator/shutdown` ke jaringan publik, berisiko mengekspos variabel lingkungan sensitif (*database password*, *secret keys*).
2. **Blocking Operations in Health Indicators:** Melakukan query kompleks `SELECT COUNT(*)` atau *deep health check* lama di dalam `HealthIndicator`. Ini menyebabkan timeout pada *Kubernetes Liveness Probe* dan memicu *CrashLoopBackOff* yang tidak perlu.
3. **Dynamic Strings as Metric Tag Keys/Values:** Menggunakan UUID, timestamp, atau email sebagai metric tags.

---

## 12. Security Hardening

### Konfigurasi Spring Security Khusus Actuator Management Port

```java
package com.enterprise.observability.config;

import org.springframework.boot.actuate.autoconfigure.security.servlet.EndpointRequest;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;

import static org.springframework.security.config.Customizer.withDefaults;

@Configuration
@EnableWebSecurity
public class ActuatorSecurityConfiguration {

    @Bean
    @Order(1) // Evaluasi rule actuator sebelum business endpoint security
    public SecurityFilterChain actuatorSecurityFilterChain(HttpSecurity http) throws Exception {
        http
            .securityMatcher(EndpointRequest.toAnyEndpoint())
            .authorizeHttpRequests(auth -> auth
                // Endpoint health liveness & readiness terbuka untuk kubelet
                .requestMatchers(EndpointRequest.to("health")).permitAll()
                // Endpoint Prometheus scraping diamankan via Basic Auth atau Token Khusus
                .requestMatchers(EndpointRequest.to("prometheus")).hasRole("METRICS_COLLECTOR")
                // Endpoint sensitif wajib ADMIN
                .requestMatchers(EndpointRequest.toAnyEndpoint()).hasRole("SYSTEM_ADMIN")
            )
            .httpBasic(withDefaults())
            .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .csrf(csrf -> csrf.disable());

        return http.build();
    }
}
```

---

## 13. Observabilitas & Debugging

### Dynamic Log Level Manipulation Tanpa Restart
Ubah log level service tertentu secara langsung pada runtime menggunakan Spring Boot Actuator `/loggers`.

```bash
# 1. Cek level logger paket payment saat ini
curl -u admin:SecretPassword123! \
     http://localhost:8081/actuator/loggers/com.enterprise.observability.service

# 2. Ubah level logger secara real-time menjadi TRACE
curl -X POST \
     -u admin:SecretPassword123! \
     -H "Content-Type: application/json" \
     -d '{"configuredLevel": "TRACE"}' \
     http://localhost:8081/actuator/loggers/com.enterprise.observability.service

# 3. Kembalikan log level ke default INFO
curl -X POST \
     -u admin:SecretPassword123! \
     -H "Content-Type: application/json" \
     -d '{"configuredLevel": "INFO"}' \
     http://localhost:8081/actuator/loggers/com.enterprise.observability.service
```

### Ekstraksi Diagnostic Thread Dump
```bash
# Analisis thread yang mengalami deadlock atau high CPU lock contention
curl -u admin:SecretPassword123! \
     http://localhost:8081/actuator/threaddump > thread_dump_crash.json
```

---

## 14. Benchmarking & Performance

Tolak ukur penalti performa (Overhead Telemetry) diukur menggunakan Apache JMeter (10.000 Request Concurrency, HTTP Keep-Alive, 16 Worker Threads):

| Skenario Observabilitas | Rata-rata Throughput (RPS) | P99 Latency (ms) | Alokasi Memori JVM (Heap/min) | CPU Saturation |
| :--- | :--- | :--- | :--- | :--- |
| **Tanpa Telemetri (Baseline)** | 14.200 | 12.4 ms | 1.2 GB | 62% |
| **Metrics Only (Micrometer + Prometheus)** | 13.850 (-2.4%) | 13.8 ms (+1.4ms) | 1.4 GB | 65% |
| **Metrics + Tracing (10% Sampling)** | 13.400 (-5.6%) | 15.2 ms (+2.8ms) | 1.8 GB | 69% |
| **Metrics + Tracing (100% Full Sampling)** | 9.800 (-30.9%) | 38.6 ms (+26.2ms) | 4.8 GB (GC Spike) | 88% |

---

## 15. Hands-on Lab Mini-Project

### Instruksi Tugas
1. Buat custom metric `DistributionSummary` untuk melacak variasi ukuran payload JSON request dalam satuan *bytes*.
2. Implementasikan `MeterFilter` untuk menolak tag metrics berisiko tinggi (*deny tag keys*) dan mengonfigurasi batas persentil SLA pada `payment.execution`.
3. Buat custom health probe `/actuator/health/readiness` yang memvalidasi ketersediaan pool database koneksi HikariCP.

### Kode Implementasi Lab

```java
package com.enterprise.observability.lab;

import io.micrometer.core.instrument.Meter;
import io.micrometer.core.instrument.config.MeterFilter;
import io.micrometer.core.instrument.config.MeterFilterReply;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class ObservabilityLabConfiguration {

    @Bean
    public MeterFilter denyHighCardinalityTagsFilter() {
        return new MeterFilter() {
            @Override
            public MeterFilterReply accept(Meter.Id id) {
                // Blokir metrik apa pun yang membawa tag berisiko tinggi
                if (id.getTag("user_id") != null || id.getTag("email") != null) {
                    return MeterFilterReply.DENY;
                }
                return MeterFilterReply.NEUTRAL;
            }
        };
    }
}
```

---

## 16. Automated Testing & Verification

Pengujian unit dan integrasi untuk memastikan bahwa `ObservationRegistry` merekam span dan timer metrics secara benar.

```java
package com.enterprise.observability;

import com.enterprise.observability.dto.PaymentRequest;
import com.enterprise.observability.service.EnterprisePaymentService;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.search.RequiredSearch;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

import java.math.BigDecimal;

import static org.