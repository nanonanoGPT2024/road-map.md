# Kurikulum Rekayasa Perangkat Lunak Enterprise: Java
## Kategori: 02-Programming-Languages
### BAB-06: Framework Architecture Spring Boot 3 Deep Dive
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
*   Menganalisis mekanisme internal siklus hidup *ApplicationContext*, resolusi dependensi, dan dynamic proxying (JDK Dynamic Proxies vs. CGLIB) pada runtime Spring Boot 3.
*   Menguasai arsitektur *Ahead-Of-Time* (AOT) engine dan GraalVM Native Image compilation untuk mereduksi footprint memori dan cold-start latency secara signifikan.
*   Mengimplementasikan observabilitas holistik (*three pillars of observability*) menggunakan Micrometer Observation API, Micrometer Tracing, dan OpenTelemetry context propagation.
*   Merancang dan mengoptimalkan throughput sistem IO-bound menggunakan integrasi Java 21 Virtual Threads (Project Loom) pada embedded container Tomcat.
*   Mendeteksi, merekonstruksi, dan memitigasi anomali produksi kritis seperti Virtual Thread Pinning, Proxy Self-Invocation Transaction Trap, dan AOT Reflection Metadata Missing.

---

### 2. Prerequisite

*   **Java Runtime & Language**: Pemahaman mendalam tentang Java 17/21 (Records, Sealed Classes, Pattern Matching, Foreign Function & Memory API basics).
*   **Concurrency**: Pemahaman mendalam tentang Java Memory Model (JMM), *happens-before* relationship, platform threads vs virtual threads execution model.
*   **Spring Core**: Pemahaman fundamental tentang Inversion of Control (IoC), Dependency Injection (DI), dan siklus hidup Bean standar.
*   **Networking & OS**: Pengetahuan mengenai thread state (`WAITING`, `TIMED_WAITING`, `RUNNABLE`), non-blocking IO (epoll/kqueue), dan segmentasi memori JVM (Heap, Non-Heap, Metaspace).

---

### 3. Concept & Internal Architecture

#### 3.1. Siklus Hidup ApplicationContext & Dynamic Proxying
Spring Boot 3 mengorkestrasi inisialisasi aplikasi melalui rantai fase deterministik di dalam `SpringApplication.run()`:

```
[Bootstrap/Environment Prep]
           │
           ▼
[ApplicationContext Creation] ──► AnnotationConfigServletWebServerApplicationContext
           │
           ▼
[BeanFactoryPostProcessor Run] ──► ConfigurationClassPostProcessor (Parsing @Configuration)
           │
           ▼
[BeanPostProcessor Registration] ──► CommonAnnotationBeanPostProcessor, AutowiredAnnotationBeanPostProcessor
           │
           ▼
[Singleton Instantiation Phase] ──► InstantiationAwareBeanPostProcessor (applyBeanPostProcessorsBeforeInstantiation)
           │                        ├── Instantiation (Constructor Reflection / Factory Method)
           │                        ├── MergedBeanDefinitionPostProcessor
           │                        ├── Populate Bean (Dependency Injection)
           │                        ├── applyBeanPostProcessorsBeforeInitialization
           │                        ├── Init Methods (@PostConstruct, InitializingBean)
           │                        └── applyBeanPostProcessorsAfterInitialization (Proxy Creation Hook!)
           ▼
[SmartLifecycle & Event Notification] ──► ApplicationReadyEvent
```

Spring Framework menerapkan dynamic proxying untuk aspek transversal (AOP, `@Transactional`, `@Async`, `@Cacheable`):
1.  **JDK Dynamic Proxy**: Digunakan jika target bean mengimplementasikan antarmuka (*interface*) dan konfigurasi `spring.aop.proxy-target-class=false`. Proxy dibentuk secara dinamis di runtime menggunakan `java.lang.reflect.Proxy`. Kelemahan: Injeksi field langsung ke kelas konkret akan memicu `BeanNotOfRequiredTypeException`.
2.  **CGLIB (Byte-Buddy) Proxy**: Standar default Spring Boot 3 (`spring.aop.proxy-target-class=true`). Menghasilkan *subclass* dinamis dari kelas target.
    *   Syarat mutlak: Kelas dan method sasaran **tidak boleh** berstatus `final`.
    *   Method invocations dicegat oleh interceptor stack (`MethodInterceptor`) yang mengeksekusi `ReflectiveMethodInvocation.proceed()`.

#### 3.2. Spring Boot 3 Ahead-of-Time (AOT) & GraalVM Engine
Tradisional JIT (Just-In-Time) compilation melakukan pembacaan *classpath*, interpretasi anotasi, evaluasi ekspresi SpEL, dan pembuatan metadata refleksi secara dinamis setiap kali aplikasi dinyalakan.

Spring AOT mengubah paradigma ini:
*   **AOT Processing Phase**: Dijalankan pada saat fase *build* (Maven/Gradle). Classpath dipindai, `@Configuration` dievaluasi, kondisi `@Conditional` divalidasi, dan struktur BeanDefinition disimpan sebagai *generated Java code*.
*   **Static Analysis**: GraalVM Native Image compiler melakukan analisis *closed-world assumption*. Seluruh kode yang tidak terdeteksi dapat dijangkau (*unreachable code*) dari *entry point* (`main`) akan dibuang (*dead-code elimination*).
*   **Reflection & JNI Registration**: Karena refleksi dinamis tidak dapat diprediksi secara utuh pada analisis statis, Spring Boot AOT menghasilkan berkas JSON metadata secara otomatis (`reflect-config.json`, `resource-config.json`) atau memanfaatkan antarmuka `RuntimeHintsRegistrar`.

#### 3.3. Micrometer Observation API Architecture
Berbeda dari instrumen Spring Boot 2 yang memisahkan metrik (`MeterRegistry`) dan tracing (`Tracer`), Spring 6 / Boot 3 memperkenalkan **Unified Observation API**:

```
                       ┌─────────────────────────┐
                       │     Observation         │
                       └────────────┬────────────┘
                                    │ notifies
           ┌────────────────────────┼────────────────────────┐
           ▼                        ▼                        ▼
┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐
│  Timer / Counter     │ │  Tracing (Otel/B3)   │ │  Logging Context     │
│  (Micrometer Core)   │ │  Span Creation       │ │  MDC Key-Value       │
└──────────────────────┘ └──────────────────────┘ └──────────────────────┘
```

Sebuah siklus eksekusi instrumen dibungkus ke dalam batas observasi:
*   `Observation.start()`: Mengalokasikan konteks, membuka *tracing span*, memulai *timer*.
*   `ObservationContext`: Menyimpan metadata (low-cardinality tags untuk metrik, high-cardinality tags untuk tracing context).
*   `ObservationHandler`: Komponen yang bereaksi terhadap siklus observasi (`onStart`, `onStop`, `onError`, `onEvent`).

#### 3.4. Java 21 Virtual Threads Runtime Integration
Diaktifkan melalui `spring.threads.virtual.enabled=true`.
*   Spring Boot mengonfigurasi embedded Tomcat untuk menggunakan `Executors.newVirtualThreadPerTaskExecutor()` sebagai request processing executor.
*   Virtual Thread adalah entitas `java.lang.Thread` ringan yang dikelola langsung oleh JVM, bukan kernel thread OS.
*   **Carrier Threads**: Berupa pool *platform threads* (biasanya sejumlah core CPU, `ForkJoinPool`). Ketika virtual thread melakukan operasi blocking IO (contoh: socket read dari database JDBC), JVM melakukan operasi `park()` dan melepaskan carrier thread untuk melayani virtual thread lain.
*   **Pinning Risk**: Jika blocking IO terjadi di dalam blok `synchronized` atau memanggil Foreign Function/Native Memory (JNI), virtual thread tertahan (*pinned*) pada carrier thread. Akibatnya, skalabilitas menurun drastis karena carrier thread tidak dapat dilepaskan.

---

### 4. Why & What

| Dimensi | Spring Boot 2.x (Legacy Baseline) | Spring Boot 3.x (Modern Architecture) | Implikasi Rekayasa Enterprise |
| :--- | :--- | :--- | :--- |
| **Java Baseline** | Java 8 atau 11 | Java 17 atau Java 21 | Memaksa modernisasi codebase; memanfaatkan records, sealed types, dan JVM vector/memory improvements. |
| **Java EE Namespace**| `javax.*` | `jakarta.*` (Jakarta EE 9/10) | Membutuhkan refactoring menyeluruh pada JPA (`jakarta.persistence`), Servlet API (`jakarta.servlet`), dan Validation. |
| **Compilation Model**| Traditional JIT (JVM bytecode interpret + compile) | Dual Mode: Standard JIT & GraalVM Native AOT | Native image memberikan startup time sub-100ms dan memory footprint turun hingga 80%, ideal untuk autoscaling K8s. |
| **Instrumentation** | Terpisah: Spring Cloud Sleuth + Micrometer | Unified: Micrometer 1.11+ Observation API | Menghilangkan duplikasi overhead kalkulasi metrik dan span generation. Single instrumentation codebase. |
| **Concurrency Model**| Platform Thread-per-request (Tomcat standard) atau Reactive (WebFlux) | Platform Threads, Reactive, atau **Virtual Threads (Loom)** | Kode imperatif sinkronus yang mudah dibaca/didebug kini dapat mencapai skalabilitas IO setara reactive programming. |

---

### 5. How (Workflow Detail)

#### Virtual Thread Lifecycle & IO Unmounting Workflow
Diagram berikut menunjukkan state machine carrier thread saat virtual thread melakukan operasi blocking IO (misal: JDBC call):

```
Platform Pool       [Carrier Thread 1]          [Carrier Thread 2]
                          │                            │
                          ▼                            ▼
                      [Mounts]                         │
                          │                            │
Virtual Threads     [VThread-A: Executing]             │
                          │                            │
                     Database Read (I/O)               │
                          │                            │
                      [Unmounts]                       │
                          ├── VThread-A states PARKED  │
                          │   in Heap Context          │
                          ▼                            ▼
Virtual Threads     [Carrier Thread 1 Free] ──► [Mounts VThread-B]
                          │                            │
                     OS epoll ready                    │
                          │                            │
                          ▼                            ▼
                    [Unparks VThread-A]                │
                          │                            │
                          ▼                            ▼
                    Carrier Thread 2 ──────────► [Mounts VThread-A]
                    (resumes execution)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional (Arsitektur Runtime Boot 3)
*   **Platform Threads (Legacy)**: Jalur landasan pacu eksklusif untuk satu pesawat charter kecil. Jika pesawat charter perlu menurunkan kargo secara manual selama 3 jam (Blocking IO), landasan pacu tersebut diblokir total dan tidak bisa digunakan pesawat lain.
*   **Virtual Threads (Project Loom)**: Ruang tunggu terminal dengan puluhan ribu penumpang (Virtual Threads). Terdapat hanya 8 gate masuk pesawat (Carrier Threads). Ketika penumpang A harus menunggu validasi paspor (Blocking IO), penumpang A diparkir di kursi santai (Heap Context), dan gate langsung digunakan oleh penumpang B.
*   **Native Image (AOT Compilation)**: Alih-alih merakit pesawat dari nol di landasan saat jadwal lepas landas (JIT classloading & reflection parsing saat startup), pesawat sudah dirakit utuh secara unibody di pabrik (Build-time compilation), siap tinggal landas dalam hitungan milidetik.

#### Arsitektur Deep AOT & Observation Pipeline

```
+---------------------------------------------------------------------------------------+
| BUILD TIME (AOT Engine Pipeline)                                                      |
|                                                                                       |
|  Source Code       Spring Bytecode Scanner       AOT Processors       Native Binary   |
| [Java 21 / Boot 3] ───────────────────────► [Generate Source/Hints] ────────► [GraalVM]  |
|                                                     │                                 |
|                                           ┌─────────┴─────────┐                       |
|                                           ▼                   ▼                       |
|                                    reflect-config.json  proxy-config.json             |
+---------------------------------------------------------------------------------------+
| RUNTIME EXECUTION ENGINE                                                              |
|                                                                                       |
| Incoming HTTP Request                                                                 |
|         │                                                                             |
|         ▼                                                                             |
| [Tomcat Virtual Thread Executor]                                                      |
|         │                                                                             |
|         ▼                                                                             |
| [Micrometer Observation Filter]  ───► OpenTelemetry TraceContext (Span Start)         |
|         │                                                                             |
|         ▼                                                                             |
| [CGLIB Interceptor Stack]        ───► Security / Transactional Aspect                 |
|         │                                                                             |
|         ▼                                                                             |
| [Target Service Bean]            ───► Logic Execution                                 |
|         │                                                                             |
|         ▼                                                                             |
| [Observation Context Stop]       ───► Stop Timer + Export Metrics to Prometheus       |
|                                  ───► Close Trace Span & Inject to Response Header    |
+---------------------------------------------------------------------------------------+
```

---

### 7. Practical Implementation

#### 7.1. Konfigurasi Produksi Virtual Threads & Observability
File: `src/main/resources/application.yml`
```yaml
server:
  port: 8080
  tomcat:
    threads:
      max: 200 # Digunakan jika virtual threads dinonaktifkan
  shutdown: graceful

spring:
  threads:
    virtual:
      enabled: true # Mengaktifkan Virtual Threads untuk Tomcat & @Async
  datasource:
    hikari:
      maximum-pool-size: 50 # Pool size disesuaikan kapasitas database, bukan jumlah thread!
      minimum-idle: 10
      idle-timeout: 300000
      connection-timeout: 20000

management:
  endpoints:
    web:
      exposure:
        include: health,info,prometheus,metrics
  tracing:
    sampling:
      probability: 1.0 # Ubah ke 0.1 untuk downstream production bervolume tinggi
  metrics:
    distribution:
      percentiles-histogram:
        http.server.requests: true
        payment.orchestration: true
```

#### 7.2. Custom Runtime Hints untuk GraalVM AOT Compilation
File: `src/main/java/com/enterprise/config/aot/CustomAotRuntimeHints.java`
```java
package com.enterprise.config.aot;

import org.springframework.aot.hint.MemberCategory;
import org.springframework.aot.hint.RuntimeHints;
import org.springframework.aot.hint.RuntimeHintsRegistrar;

import java.lang.reflect.Method;

public class CustomAotRuntimeHints implements RuntimeHintsRegistrar {

    @Override
    public void registerHints(RuntimeHints hints, ClassLoader classLoader) {
        // Registrasi refleksi untuk DTO pihak ketiga atau dynamic dynamic payload
        // yang tidak terjangkau static analysis GraalVM
        hints.reflection().registerType(
            com.enterprise.dto.DynamicPayloadRequest.class,
            MemberCategory.INVOKE_PUBLIC_CONSTRUCTORS,
            MemberCategory.INVOKE_PUBLIC_METHODS,
            MemberCategory.DECLARED_FIELDS
        );

        // Registrasi resource file non-Java yang harus dipaketkan ke dalam image binary
        hints.resources().registerPattern("crypto-keys/*.pem");
        hints.resources().registerPattern("db/migration/custom-triggers.sql");
    }
}
```

Daftarkan ke sistem AOT melalui `src/main/resources/META-INF/spring/aot.factories`:
```properties
org.springframework.aot.hint.RuntimeHintsRegistrar=\
  com.enterprise.config.aot.CustomAotRuntimeHints
```

#### 7.3. Production Enterprise-Grade Observation Instrumentation
File: `src/main/java/com/enterprise/service/PaymentOrchestratorService.java`
```java
package com.enterprise.service;

import io.micrometer.observation.Observation;
import io.micrometer.observation.ObservationRegistry;
import io.micrometer.observation.annotation.Observed;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.Duration;
import java.util.UUID;

@Service
public class PaymentOrchestratorService {

    private static final Logger log = LoggerFactory.getLogger(PaymentOrchestratorService.class);
    private final ObservationRegistry observationRegistry;

    public PaymentOrchestratorService(ObservationRegistry observationRegistry) {
        this.observationRegistry = observationRegistry;
    }

    public record PaymentCommand(UUID transactionId, String customerId, BigDecimal amount) {}
    public record PaymentResult(UUID transactionId, String status, String approvalCode) {}

    public PaymentResult orchestratePayment(PaymentCommand command) {
        // Menggunakan Observation API untuk instrumentasi terpadu (Tracing + Metrik)
        return Observation.createNotStarted("payment.orchestration", observationRegistry)
                .lowCardinalityKeyValue("customer.tier", resolveTier(command.customerId()))
                .highCardinalityKeyValue("transaction.id", command.transactionId().toString())
                .observe(() -> executePipeline(command));
    }

    private PaymentResult executePipeline(PaymentCommand command) {
        log.info("Memulai eksekusi pembayaran untuk TX: {}", command.transactionId());

        // Simulasi pemeriksaan blocking I/O (Virtual Threads melepaskan carrier di sini)
        try {
            Thread.sleep(Duration.ofMillis(80)); // Safe non-pinning blocking call
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Transaksi terinterupsi", e);
        }

        if (command.amount().compareTo(new BigDecimal("100000000")) > 0) {
            throw new IllegalArgumentException("Limit transaksi terlampaui untuk akun tunggal");
        }

        return new PaymentResult(command.transactionId(), "APPROVED", "AUTH-" + UUID.randomUUID().toString().substring(0, 8));
    }

    private String resolveTier(String customerId) {
        return customerId.startsWith("CORP") ? "ENTERPRISE" : "RETAIL";
    }
}
```

---

### 8. Real World Case Study: High-Throughput Core Banking Ledger

#### Arsitektur Sistem
Sebuah Bank Nasional menghadapi lonjakan transaksi harian dari 2.000 TPS menjadi 25.000 TPS saat periode gajian (*payroll*) dan *flash sale*. Arsitektur lama berbasis Spring Boot 2.7 dengan Apache Tomcat default (200 OS Platform Threads) mengalami *thread starvation*, di mana thread pool Tomcat habis (`HTTP 503 Service Unavailable`) karena rata-rata latensi downstream database dan core network gateway berada di kisaran 150ms.

#### Solusi Arsitektur
1.  **Migrasi ke Spring Boot 3.2+ dan Java 21**.
2.  Mengaktifkan `spring.threads.virtual.enabled=true`.
3.  Mengganti dependensi *legacy HTTP client* yang menggunakan blok `synchronized` internal ke `HttpClient` bawaan Java 11/21 (yang kompatibel penuh dengan unmounting Virtual Thread).
4.  Mengintegrasikan Micrometer Observation API dengan eksport OpenTelemetry collector untuk melacak trace context lintas microservices per-transaksi per-virtual thread.

#### Metrik Kinerja Pasca Migrasi
```
Indikator                    Spring Boot 2.7 (JIT Platform)   Spring Boot 3.2 (Virtual Threads + AOT)
Startup Time                 18.4 Detik                      0.082 Detik (Native Binary)
Memory RSS Baseline          1.4 GB                          128 MB
Peak Throughput              2,100 TPS (Saturasi Thread)     28,500 TPS (Saturasi CPU Database)
P99 Latency pada 5,000 TPS   3,450 ms                        182 ms
Carrier Pinning Incidents    N/A                             0 Event
```

---

### 9. Trade-offs

| Aspek | Spring Boot 3 JIT (Standard JVM) | Spring Boot 3 GraalVM Native Image | Virtual Threads (Project Loom) | Reactive (Spring WebFlux) |
| :--- | :--- | :--- | :--- | :--- |
| **Throughput (I/O Bound)** | Terbatas oleh pool Platform Threads | Terbatas oleh pool Platform Threads | Sangat Tinggi (Saturasi CPU/DB) | Sangat Tinggi |
| **Throughput (CPU Bound)** | Sangat Tinggi (JIT Runtime Profile) | Tinggi (Kurang optimasi PGO lanjutan) | Standar (Tidak ada keunggulan) | Standar |
| **Memory Footprint** | Tinggi (~512MB - 2GB+) | Sangat Rendah (~50MB - 150MB) | Rendah per context (+beban Heap) | Sangat Rendah |
| **Build Time** | Cepat (1-2 menit via Maven) | Lambat (5-15 menit kompilasi C++) | Cepat | Cepat |
| **Debugging Complexity** | Rendah (Stack trace standar) | Tinggi (Native debugging simbolik) | Rendah (Stack trace sinkronus utuh)| Sangat Tinggi (Mono/Flux stack trace terfragmentasi) |
| **Library Compatibility** | 100% ekosistem Java | Butuh Metadata Hints bila ada refleksi | Butuh audit `synchronized` blocking | Butuh driver reaktif non-blocking |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Virtual Thread Pinning Akibat Blok `synchronized`
*   **Penyebab**: Driver database atau pustaka internal pihak ketiga mengeksekusi blocking I/O di dalam blok `synchronized (lock)`. JVM tidak dapat melepaskan carrier thread (*pinned*), mereduksi virtual thread pool menjadi setara thread pool platform OS biasa.
*   **Deteksi**:
    Gunakan JVM flag diagnostik saat startup:
    `-Djdk.tracePinnedThreads=full`
*   **Solusi**:
    Gantikan `synchronized` dengan `java.util.concurrent.locks.ReentrantLock`.
    ```java
    // SALAH: Memicu Carrier Thread Pinning jika doBlockingNetworkCall() memblokir I/O
    public synchronized String fetchRemoteData() {
        return doBlockingNetworkCall();
    }

    // BENAR: ReentrantLock secara eksplisit unmount Virtual Thread saat park
    private final ReentrantLock lock = new ReentrantLock();

    public String fetchRemoteDataSafe() {
        lock.lock();
        try {
            return doBlockingNetworkCall();
        } finally {
            lock.unlock();
        }
    }
    ```

#### 10.2. The `@Transactional` Self-Invocation Proxy Trap
*   **Penyebab**: Pemanggilan method beranotasi `@Transactional` dari dalam method lain di *instance* kelas yang sama (`this.method()`). Interceptor proxy CGLIB tidak terpanggil, sehingga transaksi database tidak pernah diinisiasi.
*   **Deteksi**: Data tidak ter-rollback saat runtime exception terjadi di method internal.
*   **Solusi**:
    Ekstraksi method ke Service terpisah, atau injeksikan dependensi bean diri sendiri secara aman menggunakan `ObjectProvider`:
    ```java
    @Service
    public class OrderFulfillmentService {

        private final ObjectProvider<OrderFulfillmentService> selfProvider;

        public OrderFulfillmentService(ObjectProvider<OrderFulfillmentService> selfProvider) {
            this.selfProvider = selfProvider;
        }

        public void processBatch() {
            // Melalui Proxy CGLIB, transaksi berjalan dengan semantik ACID yang tepat
            selfProvider.getObject().processSingleOrderTransactional();
        }

        @Transactional(propagation = Propagation.REQUIRES_NEW)
        public void processSingleOrderTransactional() {
            // Operasi mutasi state database
        }
    }
    ```

#### 10.3. AOT Missing Reflection Metadata pada Dynamic JSON Serialization
*   **Penyebab**: DTO deserialisasi via Jackson yang diproses secara dinamis tanpa anotasi Spring AOT eksplisit akan menghasilkan `InstantiationException` atau *empty fields* pada binary Native Image GraalVM.
*   **Solusi**: Terapkan `@RegisterReflectionForBinding` pada level Controller/Config:
    ```java
    @Configuration
    @RegisterReflectionForBinding({
        com.enterprise.dto.IncomingPaymentWebhook.class,
        com.enterprise.dto.ThirdPartyPayload.class
    })
    public class NativeMetadataConfiguration {}
    ```

---

### 11. Best Practices (Production Checklist)

*   [ ] **Virtual Threads ThreadLocal Audit**: Hindari penggunaan `ThreadLocal` dengan payload berukuran besar (misal: byte buffer 10MB) karena pembuatan 100.000 virtual thread dapat langsung memicu `OutOfMemoryError` di heap.
*   [ ] **Database Connection Pool Sizing**: Jangan pernah menyamakan ukuran connection pool HikariCP dengan perkiraan jumlah Virtual Thread. Sizing database pool tetap terikat pada kapasitas core/disk database engine:
    $$\text{Connections} = (\text{Core Count} \times 2) + \text{Effective Spindle Count}$$
*   [ ] **GraalVM Native Tracing Agent**: Jalankan aplikasi binary JVM standar dengan javaagent GraalVM tracing (`-agentlib:native-image-agent=config-output-dir=src/main/resources/META-INF/native-image`) selama regression test untuk merekam seluruh jejak refleksi dinamis secara otomatis.
*   [ ] **Actuator Metric Cardinality Guard**: Jangan gunakan identifier dengan kardinalitas tak terbatas (seperti `UUID`, `Email`, `Timestamp`) ke dalam tag *low-cardinality* pada `ObservationRegistry`. Hal ini akan membuat memory leak di time-series Prometheus database.
*   [ ] **Graceful Shutdown Integration**: Pasang konfigurasi `server.shutdown=graceful` dan `spring.lifecycle.timeout-per-shutdown-phase=30s` untuk memberi waktu bagi virtual threads menyelesaikan in-flight requests.

---

### 12. Hands-on Practice

Struktur direktori yang harus disiapkan di workspace:
```
hands-on/m02/
├── pom.xml
└── src
    └── main
        ├── java
        │   └── com
        │       └── enterprise
        │           └── platform
        │               ├── PlatformApplication.java
        │               ├── config
        │               │   └── ObservationConfig.java
        │               ├── controller
        │               │   └── AccountLedgerController.java
        │               └── service
        │                   └── AccountLedgerService.java
        └── resources
            └── application.yml
```

#### Langkah 1: Siapkan `hands-on/m02/pom.xml`
Gunakan Spring Boot 3.2.x atau 3.3.x dengan Java 21:
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
    <groupId>com.enterprise.platform</groupId>
    <artifactId>module-02-deep-dive</artifactId>
    <version>0.0.1-SNAPSHOT</version>

    <properties>
        <java.version>21</java.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>
        <dependency>
            <groupId>io.micrometer</groupId>
            <artifactId>micrometer-registry-prometheus</artifactId>
        </dependency>
        <dependency>
            <groupId>io.micrometer</groupId>
            <artifactId>micrometer-tracing-bridge-otel</artifactId>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
```

#### Langkah 2: Konfigurasi Virtual Threads & Actuator di `src/main/resources/application.yml`
```yaml
server:
  port: 8080
spring:
  application:
    name: ledger-orchestrator
  threads:
    virtual:
      enabled: true
management:
  endpoints:
    web:
      exposure:
        include: "*"
  tracing:
    sampling:
      probability: 1.0
```

#### Langkah 3: Konfigurasi Observation Custom Handler
Buat file `src/main/java/com/enterprise/platform/config/ObservationConfig.java`:
```java
package com.enterprise.platform.config;

import io.micrometer.observation.Observation;
import io.micrometer.observation.ObservationHandler;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
public class ObservationConfig {

    private static final Logger log = LoggerFactory.getLogger(ObservationConfig.class);

    @Bean
    public ObservationHandler<Observation.Context> customLoggingObservationHandler() {
        return new ObservationHandler<>() {
            @Override
            public void onStart(Observation.Context context) {
                log.info("TRACE EVENT: Mulai Observasi Context [{}]", context.getName());
            }

            @Override
            public void onStop(Observation.Context context) {
                log.info("TRACE EVENT: Selesai Observasi Context [{}]. Durasi Context Tersimpan.", context.getName());
            }

            @Override
            public boolean supportsContext(Observation.Context context) {
                return true;
            }
        };
    }
}
```

#### Langkah 4: Implementasi Core Service dengan Virtual Thread Logging
Buat file `src/main/java/com/enterprise/platform/service/AccountLedgerService.java`:
```java
package com.enterprise.platform.service;

import io.micrometer.observation.ObservationRegistry;
import io.micrometer.observation.annotation.Observed;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.time.Duration;

@Service
public class AccountLedgerService {

    private static final Logger log = LoggerFactory.getLogger(AccountLedgerService.class);

    @Observed(name = "ledger.mutation.process", contextualName = "process-ledger-mutation")
    public String executeMutation(String accountId, double amount) {
        log.info("Memproses mutasi akun: {} dengan thread: {}", accountId, Thread.currentThread());
        
        if (Thread.currentThread().isVirtual()) {
            log.info("Thread terverifikasi bertipe VIRTUAL THREAD (Project Loom).");
        } else {
            log.warn("PERINGATAN: Berjalan di atas Platform OS Thread!");
        }

        try {
            // Simulasi I/O delay
            Thread.sleep(Duration.ofMillis(50));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException(e);
        }

        return "SUCCESS-" + accountId + ":" + amount;
    }
}
```

#### Langkah 5: Rest Controller Interface
Buat file `src/main/java/com/enterprise/platform/controller/AccountLedgerController.java`:
```java
package com.enterprise.platform.controller;

import com.enterprise.platform.service.AccountLedgerService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/ledger")
public class AccountLedgerController {

    private final AccountLedgerService ledgerService;

    public AccountLedgerController(AccountLedgerService ledgerService) {
        this.ledgerService = ledgerService;
    }

    @PostMapping("/mutate")
    public ResponseEntity<String> mutate(@RequestParam String accountId, @RequestParam double amount) {
        return ResponseEntity.ok(ledgerService.executeMutation(accountId, amount));
    }
}
```

#### Langkah 6: Main Entry Point
Buat file `src/main/java/com/enterprise/platform/PlatformApplication.java`:
```java
package com.enterprise.platform;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class PlatformApplication {
    public static void main(String[] args) {
        SpringApplication.run(PlatformApplication.class, args);
    }
}
```

#### Langkah 7: Eksekusi dan Verifikasi
Jalankan perintah berikut:
```bash
# Kompilasi dan eksekusi
mvn clean spring-boot:run

# Pada terminal terpisah, kirim request
curl -X POST "http://localhost:8080/api/v1/ledger/mutate?accountId=ACC-9901&amount=50000.0"

# Periksa log aplikasi di terminal, pastikan muncul:
# Thread terverifikasi bertipe VIRTUAL THREAD (Project Loom) -> [VirtualThread[#...]]

# Periksa exposure metrik Prometheus untuk Observation API:
curl -s http://localhost:8080/actuator/prometheus | grep ledger_mutation_process
```

---

### 13. Exercise

#### Level Easy
Ubah konfigurasi pada `hands-on/m02/src/main/resources/application.yml` untuk mematikan virtual threads (`spring.threads.virtual.enabled=false`). Jalankan kembali `curl` request dan catat perbedaan struktur string representasi `Thread.currentThread()` pada output logger terminal.

#### Level Medium
Tambahkan *Custom Tag Key-Value Provider* menggunakan `ObservationConvention<Observation.Context>` kustom pada `AccountLedgerService` agar setiap mutasi rekening di atas `10,000.0` secara otomatis menambahkan tag metrik `risk.tier=HIGH`, sedangkan di bawahnya diberi tag `risk.tier=LOW`.

#### Level Hard
Konfigurasikan integrasi database in-memory (H2) dengan JPA pada projek hands-on. Simulasikan skenario *Virtual Thread Pinning* dengan membuat sebuah blocking database write yang dibungkus oleh sebuah method sinkronisasi native Java `synchronized`. Aktifkan flag JVM `-Djdk.tracePinnedThreads=full` dan amati stack-trace warning pinning yang dipancarkan oleh runtime JVM pada konsol. Refactor kode tersebut menggunakan `ReentrantLock` hingga warning pinning hilang sepenuhnya dari konsol runtime.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Enterprise Architect di sebuah institusi pembayaran finansial global. Sistem microservice orkestrasi kliring transaksi berbasis Spring Boot 3 menghadapi kendala:
1.  Sistem harus mampu melayani **40.000 concurrent socket connections** melalui WebSockets dan HTTP/2 streaming.
2.  Beberapa SDK integrasi pihak ketiga ke mainframe perbankan lama ditulis menggunakan native code C++ via Java Native Interface (JNI) dan banyak memanfaatkan blok monitor `synchronized`.
3.  Aplikasi harus di-deploy ke environment Kubernetes dengan *memory limit* ketat (maksimal 256MB RAM per pod) dan *zero tolerance* terhadap cold-start delay ketika pod baru di-*spin-up* akibat autoscaling HPA.

**Tantangan Arsitektur**:
*   Tentukan arsitektur kompilasi dan runtime execution model yang paling tepat (Pilihan antara: Standard JVM + Virtual Threads, Native GraalVM Image, atau Hybrid Worker Architecture).
*   Rancang strategi isolasi arsitektur agar pemanggilan native code JNI yang memblokir tidak merusak/mem-pin carrier threads Tomcat Virtual Threads secara global.
*   Rumuskan diagram arsitektur interkoneksi service, konfigurasi thread pool isolation, dan strategi pendaftaran reachability metadata GraalVM jika Native Image diadopsi.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1.  **Apakah perbedaan struktural mendasar antara JDK Dynamic Proxy dan CGLIB Proxy dalam arsitektur Spring Boot?**
    *   *Jawaban*: JDK Dynamic Proxy membutuhkan implementasi *interface* dan menghasilkan proxy kelas berbasis refleksi `java.lang.reflect.Proxy`. CGLIB (Byte-Buddy) menghasilkan subclass turunan dinamis dari kelas konkret target di runtime, sehingga tidak membutuhkan interface tetapi mensyaratkan kelas dan method target tidak berstatus `final`.
2.  **Pada fase siklus hidup Bean yang mana proxy CGLIB Spring dibentuk?**
    *   *Jawaban*: Pada fase `applyBeanPostProcessorsAfterInitialization` menggunakan implementasi `BeanPostProcessor` internal (seperti `AbstractAutoProxyCreator`).
3.  **Mengapa Spring Framework 6 dan Spring Boot 3 memindahkan seluruh baseline package enterprise dari `javax.*` ke `jakarta.*`?**
    *   *Jawaban*: Karena pengalihan tata kelola Java EE dari Oracle ke Eclipse Foundation yang memunculkan brand Jakarta EE, di mana hak paten atas nama namespace merek dagang `javax.*` tetap dipegang oleh Oracle.
4.  **Apa yang terjadi pada carrier thread ketika Virtual Thread memanggil `Thread.sleep(1000)` pada Java 21?**
    *   *Jawaban*: Virtual thread akan di-*unmount* dari carrier thread dan dimasukkan ke dalam status `PARKED` pada heap. Carrier thread kembali berstatus `RUNNABLE` dan bebas mengeksekusi virtual thread lainnya.
5.  **Properti konfigurasi apa yang digunakan pada Spring Boot 3.2+ untuk mendelegasikan Tomcat Request Processing ke Virtual Threads?**
    *   *Jawaban*: `spring.threads.virtual.enabled=true`.

#### Intermediate (5 Soal)
6.  **Bagaimana Micrometer Observation API menyatukan konsep Metrik (Metrics) dan Pelacakan Jejak (Tracing)?**
    *   *Jawaban*: Observation API menyediakan siklus hidup observasi tunggal (`start`, `stop`, `error`). Handler terdaftar (`ObservationHandler`) mengekstrak data dari siklus ini secara bersamaan: satu handler mengubah durasi menjadi metrik `Timer` (Micrometer Core), dan handler lain membuat distributed context `Span` (OpenTelemetry/Brave).
7.  **Apa yang dimaksud dengan "Closed-World Assumption" dalam kompilasi GraalVM Native Image pada Spring Boot 3?**
    *   *Jawaban*: Paradigma bahwa seluruh kode bytecode, kelas, method, anotasi, dan resource yang akan dieksekusi pada runtime harus diketahui dan dapat dijangkau (*reachable*) secara statis saat waktu kompilasi (*build time*). Kode yang tidak terdeteksi dianggap tidak ada dan dibuang.
8.  **Jelaskan mekanisme terjadinya "Virtual Thread Pinning"!**
    *   *Jawaban*: Kondisi ketika virtual thread tidak dapat di-unmount dari carrier thread saat melakukan blocking I/O karena frame eksekusi terkunci di dalam blok/metode `synchronized` native JVM atau sedang mengeksekusi Foreign Function/JNI call.
9.  **Mengapa injeksi method beranotasi `@Async` yang dipanggil dari dalam kelas yang sama (*self-invocation*) gagal dieksekusi secara asinkronus?**
    *   *Jawaban*: Karena pemanggilan internal langsung mengeksekusi metode melalui referensi instance lokal (`this`) tanpa melewati proxy interceptor stack Spring yang membungkus bean tersebut.
10. **Bagaimana peran antarmuka `RuntimeHintsRegistrar` dalam arsitektur Spring AOT?**
    *   *Jawaban*: Menyediakan mekanisme terprogram (*programmatic contract*) bagi developer untuk mendaftarkan metadata refleksi, serialisasi, dynamic proxy, dan resource file ke compiler AOT Spring yang tidak dapat dideteksi secara otomatis melalui analisis statis.

#### Skenario Kasus Produksi (3 Soal)
11. **Skenario 1**: Sebuah microservice Spring Boot 3.2 yang menggunakan Virtual Threads mengalami degradasi performa akut setelah library audit log database versi lama dimasukkan ke classpath. CPU usage server melonjak ke 100% sementara throughput anjlok hingga 90%. Dari mana Anda memulai troubleshooting?
    *   *Jawaban*: Pasang flag `-Djdk.tracePinnedThreads=full` pada container startup argument. Amati log stdout apakah pustaka audit log tersebut menggunakan blok `synchronized` saat mengeksekusi query database blocking I/O (menimbulkan Carrier Thread Pinning massal). Solusinya adalah memodernisasi library driver atau mengisolasi eksekusi logging tersebut ke dalam custom bounded Platform Thread Pool terpisah.
12. **Skenario 2**: Aplikasi Spring Boot 3 berhasil dikompilasi ke GraalVM Native Image tanpa error. Namun saat dijalankan di staging, deserialisasi webhook payload dari payment gateway selalu menghasilkan objek DTO dengan seluruh field bernilai `null`. Mengapa ini terjadi dan bagaimana solusinya?
    *   *Jawaban*: Closed-world analysis GraalVM membuang metadata refleksi setter/field dari DTO payment gateway karena DTO tersebut tidak pernah direferensikan secara eksplisit oleh compiler sebagai target deserialisasi reflektif. Solusinya: Daftarkan kelas DTO tersebut menggunakan anotasi `@RegisterReflectionForBinding({PaymentWebhookDto.class})` atau daftarkan via `RuntimeHintsRegistrar`.
13. **Skenario 3**: Sebuah bank mengaktifkan `spring.threads.virtual.enabled=true` dan menaikkan parameter HikariCP `maximum-pool-size` dari 30 menjadi 5.000 dengan asumsi dapat mendukung 5.000 transaksi paralel virtual threads. Apa dampak arsitektural yang akan terjadi pada sistem database PostgreSQL mereka?
    *   *Jawaban*: Database PostgreSQL mengalokasikan satu dedicated process per connection. Membuat 5.000 koneksi akan menghancurkan performa database akibat tingginya memory overhead, lock contention, dan konteks switching CPU OS database. Best practice: Tetap pertahankan connection pool HikariCP pada ukuran rasional (sesuai CPU core database, misal: 30-100), biarkan jutaan Virtual Threads mengantre secara efisien di level memori heap aplikasi Spring Boot saat meminjam koneksi (*connection lease*).

---

### 16. Summary

Modul ini telah membedah arsitektur internal Spring Boot 3 dari level bytecode, runtime dynamic proxying, hingga integrasi kernel concurrency Java modern. 

Pergeseran ke Spring Boot 3 bukan sekadar pembaruan versi ketergantungan, melainkan transformasi arsitektur menyeluruh:
1.  **Core Foundation**: Migrasi ke namespace `jakarta.*` dan adopsi penuh Java 17/21 sebagai baseline fundamental.
2.  **Ahead-Of-Time (AOT)**: Menjembatani ekosistem Spring yang dinamis berbasis refleksi dengan runtime GraalVM Native Image deterministik untuk komputasi cloud native berlatensi rendah.
3.  **Project Loom Execution Engine**: Mengubah total pola konkurensi throughput tinggi dengan pemanfaatan Virtual Threads, menggantikan kebutuhan rekayasa non-blocking reactive yang rumit untuk skenario umum I/O bound.
4.  **Unified Observability**: Menyatukan metrik dan distributed tracing di bawah satu abstraksi Micrometer Observation API terpadu yang meminimalisir footprint instrumen pada tataran produksi enterprise.