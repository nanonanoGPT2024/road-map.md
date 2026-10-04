# Bab 01: Core Architecture & Fundamentals
## Modul 01: Dekonstruksi Spring Boot, IoC Container, dan Mekanisme Auto-Configuration

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- **Menganalisis** siklus hidup inisialisasi runtime Spring Boot dari eksekusi `SpringApplication.run()` hingga status konteks *ready*.
- **Mendekonstruksi** cara kerja Inversion of Control (IoC) Container dan siklus hidup Bean (`BeanDefinition`, instansiasi, populasi properti, hingga terminasi).
- **Menginvestigasi** mekanisme internal Auto-Configuration menggunakan evaluasi kondisi (`@ConditionalOnClass`, `@ConditionalOnMissingBean`, dll.) dan file metadata SPI (`AutoConfiguration.imports`).
- **Merancang** *custom Auto-Configuration starter* berbasis library internal untuk isolasi *cross-cutting concerns*.
- **Mendeteksi dan Memitigasi** *circular dependency*, degradasi waktu booting (*cold-start latency*), dan kebocoran konteks (*context pollution*) pada aplikasi berskala *enterprise*.

---

### 2. Conceptual Foundation
Secara fundamental, Spring Boot bukanlah *framework* baru yang berdiri sendiri, melainkan sebuah lapisan orkestrasi berpendapat (*opinionated abstraction runtime*) di atas Spring Framework core (terdiri dari module `spring-beans`, `spring-context`, dan `spring-core`). 

Pada arsitektur perangkat lunak berbasis objek klasik tanpa IoC, objek mengontrol secara langsung siklus hidup dependensinya (*tightly-coupled instantiation*):
```
[OrderService] ---> instantiates ---> [MySQLOrderRepository]
```
Pola ini memicu kerapuhan struktural: dependensi tidak dapat diganti tanpa modifikasi kode sumber, logika unit testing terdistorsi oleh kebutuhan *mocking* internal yang agresif, dan *cross-cutting concerns* (seperti transaksi dan telemetri) tercampur ke dalam domain logic.

Spring membalikkan kendali ini melalui **Inversion of Control (IoC)** menggunakan teknik **Dependency Injection (DI)**:
```
[IoC Container (BeanFactory)]
        |
        +---> Instantiates [MySQLOrderRepository]
        +---> Injects into ---> [OrderService]
```
IoC Container bertindak sebagai *state machine* sentral yang memetakan, menginstansiasi, mengonfigurasi, dan merangkai dependensi melalui metadata konfigurasi. Spring Boot mengotomatisasi konfigurasi runtime melalui paradigma **Convention-over-Configuration** berbasis *conditional bytecode inspection* pada classpath.

---

### 3. Why It Matters
Aplikasi enterprise modern menuntut modularitas tinggi, skalabilitas horizontal, dan portabilitas lintas infrastruktur cloud. Kegagalan memahami mekanisme internal Spring Boot menyebabkan masalah teknis berat:

- **Kegagalan Startup Silent:** Kesalahan pemahaman resolusi dependensi menghasilkan *bean injection race-conditions* atau *missing bean exceptions* saat runtime di production.
- **Resource Exhaustion:** Menggunakan scope Bean yang salah (misalnya, menaruh stateful mutable data pada Singleton Bean) mengakibatkan *data corruption* multi-threading atau kebocoran memori (*heap bloat*).
- **Cold-Start Penalty:** Auto-Configuration yang tidak dipangkas secara selektif membebani pemindaian classpath (*classpath scanning*) dan evaluasi refleksi yang lambat, menaikkan biaya komputasi pada arsitektur Serverless atau arsitektur autoscaling pod Kubernetes (HPA).
- **Degradasi Pemeliharaan:** Pola konfigurasi serampangan menciptakan arsitektur "Big Ball of Mud", di mana komponen infrastruktur dan logika bisnis terikat erat tanpa batas modular (*bounded context*).

---

### 4. What It Is
Spring Boot adalah platform runtime opini-sentris yang menggabungkan:
1. **Embedded Servlet Container:** Mengabstraksi deployment WAR eksternal menjadi executable JAR mandiri menggunakan server web bawaan (Tomcat, Jetty, atau Undertow).
2. **Spring Initializer & Starter POMs:** Agregator dependensi terkurasi yang memecahkan masalah dependensi transitive (*dependency hell*) dengan matriks kompatibilitas teruji.
3. **Mekanisme Auto-Configuration:** Algoritma berbasis refleksi dan pemindaian metadata kelas yang secara otomatis mendaftarkan Bean ke dalam `ApplicationContext` berdasarkan dependensi JAR yang terdeteksi di classpath.
4. **Externalized Configuration Management:** Resolusi hirarkis properti konfigurasi lintas *environment* (CLI args, environment variables, system properties, file YAML/properties).
5. **Production-Ready Actuator:** Telemetri bawaan untuk kesehatan aplikasi (*health checks*), metrik JVM, dan evaluasi internal beans.

#### Batasan Arsitektur
- **Bukan Pengganti Logic:** Spring Boot tidak menyediakan solusi otomatis untuk konkurensi domain yang rusak atau struktur skema basis data yang suboptimal.
- **Bukan Bytecode Optimizer:** Auto-configuration berjalan via Java Reflection dan Dynamic Proxies pada startup, yang membawa overhead latensi inisialisasi awal.

---

### 5. How It Works
Proses inisialisasi aplikasi dari eksekusi `SpringApplication.run(Main.class, args)` melewati tahapan internal sistem yang ketat:

```
[Bootstrap Phase]
  1. Instansiasi SpringApplication
  2. Resolusi WebApplicationType (NONE, SERVLET, REACTIVE)
  3. Load Bootstrap Registry Initializers & ApplicationContextInitializers (META-INF/spring.factories)
  4. Load ApplicationListeners
       │
[Context Preparation Phase]
  5. Instansiasi DefaultBootstrapContext
  6. Trigger Event: ApplicationStartingEvent
  7. Parsing Command-Line Arguments & Environment Creation (ConfigurableEnvironment)
  8. Print Banner (jika diaktifkan)
  9. Instansiasi AnnotationConfigServletWebServerApplicationContext (untuk Web MVC)
       │
[Context Loading Phase]
  10. Load BeanDefinitions dari Main Configuration Class (@SpringBootApplication)
  11. Invoke BeanFactoryPostProcessors (Termasuk ConfigurationClassPostProcessor untuk proses @Configuration)
  12. Evaluasi Auto-Configuration via AutoConfigurationImportSelector
      - Membaca META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports
      - Filter via @ConditionalOn* (Class, MissingBean, Property, WebApplication)
  13. Register Final BeanDefinitions ke BeanDefinitionRegistry
       │
[Context Refresh Phase - IoC Initialization]
  14. Inisialisasi MessageSource & ApplicationEventMulticaster
  15. Start Embedded Tomcat WebServer (onRefresh())
  16. Instansiasi & Wiring Singleton Beans (preInstantiateSingletons())
      - Resolusi Konstruktor
      - Instansiasi Bean (CGLIB / JDK Dynamic Proxy jika dibutuhkan AOP)
      - Dependency Injection (Populate Properties)
      - Eksekusi Aware Interfaces (BeanNameAware, ApplicationContextAware)
      - BeanPostProcessor.postProcessBeforeInitialization()
      - Initialization Callback (@PostConstruct / InitializingBean.afterPropertiesSet())
      - BeanPostProcessor.postProcessAfterInitialization()
       │
[Startup Finalization]
  17. Embedded Tomcat bind ke TCP Port (e.g., 8080)
  18. Invoke CommandLineRunner & ApplicationRunner Beans
  19. Trigger Event: ApplicationReadyEvent
```

---

### 6. Architecture Diagram

#### Bootstrap & Container Lifecycle Execution
```
+----------------------------------------------------------------------------------------------------+
|                                    JVM Process (Main Thread)                                       |
+----------------------------------------------------------------------------------------------------+
                                                │
                                    SpringApplication.run()
                                                │
                     ┌──────────────────────────┴──────────────────────────┐
                     ▼                                                     ▼
        [ConfigurableEnvironment]                             [ApplicationContext]
     (Profile, CLI, YAML Resolvers)                       (AnnotationConfigServletWebServer)
                     │                                                     │
                     └──────────────────────────┬──────────────────────────┘
                                                │
                                                ▼
                             [ConfigurationClassPostProcessor]
                                                │
             ┌──────────────────────────────────┴──────────────────────────────────┐
             ▼                                                                     ▼
   [@ComponentScan Scanning]                                      [AutoConfigurationImportSelector]
   Reads local package beans                                      Reads AutoConfiguration.imports
             │                                                                     │
             └──────────────────────────────────┬──────────────────────────────────┘
                                                │
                                                ▼
                                    [BeanDefinitionRegistry]
                             (Metadata Map of all Valid Beans)
                                                │
                                                ▼
                                [DefaultListableBeanFactory]
                                                │
             ┌──────────────────────────────────┴──────────────────────────────────┐
             ▼                                                                     ▼
   [Instantiate Singleton]                                                [BeanPostProcessors]
Constructor Resolution via DI                                          AOP Proxies, Lifecycle Hooks
             │                                                                     │
             └──────────────────────────────────┬──────────────────────────────────┘
                                                │
                                                ▼
                                    [Embedded Web Server]
                             (Tomcat/Undertow starts & binds)
                                                │
                                                ▼
                                      APPLICATION READY
```

---

### 7. Minimal Deterministic Example
Implementasi minimal Spring Boot tanpa starter POM eksternal, beroperasi menggunakan dependensi inti.

#### Proyek Struktur (Build Tool: Maven)
File: `pom.xml`
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.3.0</version>
        <relativePath/>
    </parent>
    <groupId>com.architecture.core</groupId>
    <artifactId>minimal-application</artifactId>
    <version>1.0.0</version>
    <properties>
        <java.version>21</java.version>
    </properties>
    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter</artifactId>
        </dependency>
    </dependencies>
</project>
```

#### Entrypoint dan Komponen Mandiri
File: `src/main/java/com/architecture/core/MinimalApplication.java`
```java
package com.architecture.core;

import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.stereotype.Component;

interface GreetingEngine {
    String generateMessage(String subject);
}

@Component
class DeterministicGreetingEngine implements GreetingEngine {
    @Override
    public String generateMessage(String subject) {
        return "Bootstrap Success. System target: " + subject.toUpperCase();
    }
}

@SpringBootApplication
public class MinimalApplication {

    public static void main(String[] args) {
        SpringApplication.run(MinimalApplication.class, args);
    }

    @Bean
    public CommandLineRunner runVerification(GreetingEngine engine) {
        return args -> {
            String output = engine.generateMessage("IoC Engine");
            System.out.println(output);
        };
    }
}
```

---

### 8. Production-Grade Implementation
Implementasi custom Auto-Configuration modular untuk mengaudit waktu eksekusi service berbasis AOP dan conditional bean loading.

#### Struktur Modul Custom Starter
```
audit-spring-boot-starter/
├── pom.xml
└── src/main/java/com/architecture/platform/audit/
    ├── AuditProperties.java
    ├── ExecutionAuditAspect.java
    └── AuditAutoConfiguration.java
└── src/main/resources/META-INF/spring/
    └── org.springframework.boot.autoconfigure.AutoConfiguration.imports
```

#### File: `audit-spring-boot-starter/pom.xml`
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.3.0</version>
        <relativePath/>
    </parent>
    <groupId>com.architecture.platform</groupId>
    <artifactId>audit-spring-boot-starter</artifactId>
    <version>1.0.0</version>
    <properties>
        <java.version>21</java.version>
    </properties>
    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-autoconfigure</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-configuration-processor</artifactId>
            <optional>true</optional>
        </dependency>
        <dependency>
            <groupId>org.aspectj</groupId>
            <artifactId>aspectjweaver</artifactId>
        </dependency>
        <dependency>
            <groupId>org.slf4j</groupId>
            <artifactId>slf4j-api</artifactId>
        </dependency>
    </dependencies>
</project>
```

#### File: `AuditProperties.java`
```java
package com.architecture.platform.audit;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "platform.audit")
public record AuditProperties(
    boolean enabled,
    long executionThresholdMillis
) {
    public AuditProperties {
        if (executionThresholdMillis < 0) {
            throw new IllegalArgumentException("Execution threshold cannot be negative.");
        }
    }
}
```

#### File: `ExecutionAuditAspect.java`
```java
package com.architecture.platform.audit;

import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Aspect
public class ExecutionAuditAspect {

    private static final Logger log = LoggerFactory.getLogger(ExecutionAuditAspect.class);
    private final AuditProperties properties;

    public ExecutionAuditAspect(AuditProperties properties) {
        this.properties = properties;
    }

    @Around("@within(org.springframework.stereotype.Service) || @annotation(com.architecture.platform.audit.Auditable)")
    public Object auditExecutionTime(ProceedingJoinPoint joinPoint) throws Throwable {
        long startTime = System.nanoTime();
        try {
            return joinPoint.proceed();
        } finally {
            long durationMillis = (System.nanoTime() - startTime) / 1_000_000;
            if (durationMillis >= properties.executionThresholdMillis()) {
                log.warn("PERFORMANCE LATENCY ALERT: [{}.{}] executed in {} ms (Threshold: {} ms)",
                    joinPoint.getSignature().getDeclaringTypeName(),
                    joinPoint.getSignature().getName(),
                    durationMillis,
                    properties.executionThresholdMillis());
            } else {
                log.debug("Execution audit: [{}.{}] took {} ms",
                    joinPoint.getSignature().getDeclaringTypeName(),
                    joinPoint.getSignature().getName(),
                    durationMillis);
            }
        }
    }
}
```

#### File: `AuditAutoConfiguration.java`
```java
package com.architecture.platform.audit;

import org.aspectj.lang.annotation.Aspect;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;

@AutoConfiguration
@ConditionalOnClass(Aspect.class)
@EnableConfigurationProperties(AuditProperties.class)
@ConditionalOnProperty(prefix = "platform.audit", name = "enabled", havingValue = "true", matchIfMissing = false)
public class AuditAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean
    public ExecutionAuditAspect executionAuditAspect(AuditProperties properties) {
        return new ExecutionAuditAspect(properties);
    }
}
```

#### File: `src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`
```properties
com.architecture.platform.audit.AuditAutoConfiguration
```

---

### 9. Edge Cases & Failure Modes

| Edge Case / Skenario Masalah | Titik Kegagalan Internal | Indikasi Error / Gejala | Dampak Operasional & Mitigasi |
| :--- | :--- | :--- | :--- |
| **Circular Dependency** | `DefaultSingletonBeanRegistry.getSingleton()` mendeteksi locking siklik. | `BeanCurrentlyInCreationException` | **Fatal.** Aplikasi gagal booting. Pisahkan dependensi menggunakan event mediator atau refactor ke *Interface Segregation*. Jangan gunakan `@Lazy` secara serampangan. |
| **Unsatisfied Conditional Ordering** | `@AutoConfigureBefore` / `@AutoConfigureAfter` tidak diatur antar konfigurasi custom. | Bean dari AutoConfiguration ditimpa atau tidak muncul secara non-deterministik. | AutoConfiguration gagal menyediakan fallback. Selalu definisikan urutan import via anotasi ordering atau batasi ruang lingkup dependensi. |
| **Prototype Bean Leaks di Singleton** | Singleton Bean meng-inject Prototype Bean via Constructor injection secara langsung. | Prototype hanya dibuat 1 kali saat singleton dibangun; state prototype menjadi shared. | **Inkonsistensi State.** Gunakan `ObjectProvider<T>`, `Provider<T>`, atau `@Lookup` method injection untuk menginstansiasi Prototype baru setiap kali diakses. |
| **Unchecked External Properties Binding** | Kegagalan konversi tipe data atau validasi constraint pada class `@ConfigurationProperties`. | `BindValidationException` / `ConversionFailedException` | Boot loop pada pod Kubernetes saat deployment perubahan environment variable. Definisikan `@Validated` dan unit test integritas properti. |

---

### 10. Trade-Off Analysis

#### Pendekatan IoC Container: Reflection vs Source Generation
| Aspek Evaluasi | Reflection Runtime (Spring Boot Standard) | Static Ahead-of-Time / Compile-Time (Quarkus / Micronaut / Dagger) | Trade-Off Decision Matrix |
| :--- | :--- | :--- | :--- |
| **Waktu Booting (Startup Latency)** | Relatif Lambat (1 - 5 detik). Overhead scanning, parsing anotasi, pembuatan CGLIB proxies. | Ultra Cepat (10 - 100 ms). Resolusi graf dependency di-generate saat proses kompilasi. | Gunakan AOT / GraalVM Native Image jika target deployment adalah Serverless Function (AWS Lambda / Cloud Run). |
| **Konsumsi Memori (RSS / Metaspace)** | Tinggi. Menyimpan banyak metadata `Class`, `Method`, dan `BeanDefinition` di Metaspace. | Rendah. Metadata kelas reflektif sangat tereduksi. | Spring Boot standar optimal untuk aplikasi long-running microservices di container orchestration. |
| **Fleksibilitas Runtime Configuration** | Sangat Tinggi. Mampu merekonfigurasi beans dan dynamic proxy secara dinamis saat runtime. | Kaku. Hampir semua wiring telah terkunci saat proses build (`javac`). | Fleksibilitas konfigurasi dinamis enterprise membenarkan penggunaan Spring Boot konvensional. |
| **Ekosistem & Developer Velocity** | Terluas di industri JVM. Hampir semua vendor enterprise menyediakan starter resmi. | Menengah hingga rendah. Pilihan library terbatas pada model AOT yang kompatibel. | Kecepatan delivery fitur bisnis mendikte adopsi ekosistem Spring Boot yang matang. |

---

### 11. Security Considerations
1. **Eksposur Evaluasi Ekspresi SpEL (Spring Expression Language):**
   - Menghindari parsing string mentah yang bersumber dari user input melalui `SpelExpressionParser`. Eksekusi SpEL yang tidak terkontrol memungkinkan Remote Code Execution (RCE) via `T(java.lang.Runtime).getRuntime().exec()`.
2. **Hardcoded Credentials dalam Configuration Properties:**
   - Dilarang menyimpan credentials, tokens, atau encryption keys di dalam file `application.yml`.
   - Gunakan binding abstraction:
   ```yaml
   spring:
     datasource:
       password: ${DB_SECRET_PASSWORD}
   ```
   - Integrasikan dengan HashiCorp Vault atau AWS Secrets Manager menggunakan Spring Cloud Vault.
3. **Information Disclosure Actuator Endpoints:**
   - Mengekspos endpoint Actuator secara ceroboh dapat mengekspos seluruh isi memory heap, environment variable, atau pemetaan path controller internal.
   - Restriksi ketat pada `application.yml`:
   ```yaml
   management:
     endpoints:
       web:
         exposure:
           include: "health,metrics"
     endpoint:
       health:
         show-details: when_authorized
   ```

---

### 12. Performance & Optimization

#### Optimasi Fase Inisialisasi JVM
- **Nonaktifkan JMX:** Jika pemantauan menggunakan Prometheus/OpenTelemetry, matikan JMX untuk mengurangi alokasi thread dan metaspace:
  ```properties
  spring.jmx.enabled=false
  ```
- **Optimasi Classpath Scanning:** Batasi jangkauan `@ComponentScan` hanya pada base package fungsional, hindari melakukan scanning pada root direktori:
  ```java
  @SpringBootApplication(scanBasePackages = "com.architecture.platform.core")
  ```
- **Bytecode Verifier & Tiered Compilation:**
  Untuk instance container dengan resource ketat, kurangi pemakaian CPU startup JVM:
  ```bash
  java -XX:TieredStopAtLevel=1 -Xverify:none -jar app.jar
  ```
  *(Peringatan: Gunakan `-Xverify:none` hanya pada environment terisolasi dan container image terpercaya).*

#### Reduksi Memory Footprint via Lazy Initialization
Mulai Spring Boot 2.2, lazy bean instantiation dapat diaktifkan globally:
```properties
spring.main.lazy-initialization=true
```
*Trade-off*: Mengurangi waktu booting secara drastis, tetapi memindahkan latensi evaluasi runtime ke pemanggilan request HTTP pertama (HTTP First-Request Penalty) dan menunda deteksi error dependensi hingga bean tersebut diakses. Disarankan hanya untuk development lokal.

---

### 13. Observability & Telemetry

Metrik inisialisasi IoC container harus diekspos untuk memantau regresi performa startup aplikasi lintas versi deployment.

#### Spring Boot Startup Tracking Implementation
Tambahkan tracker startup pada entry point:
```java
package com.architecture.core;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.core.metrics.jfr.FlightRecorderApplicationStartup;

@SpringBootApplication
public class ObservableApplication {

    public static void main(String[] args) {
        SpringApplication app = new SpringApplication(ObservableApplication.class);
        // Menggunakan Java Flight Recorder (JFR) untuk merekam timeline profiling startup container
        app.setApplicationStartup(new FlightRecorderApplicationStartup());
        app.run(args);
    }
}
```

#### Structured Logging saat Container Initialization
Gunakan structured JSON logging untuk penelusuran status container:
```json
{
  "timestamp": "2026-03-30T10:15:30.120Z",
  "level": "INFO",
  "thread": "main",
  "logger": "org.springframework.boot.StartupInfoLogger",
  "message": "Started ObservableApplication in 1.452 seconds (process running for 1.892)",
  "context": {
    "environment": "production",
    "jvm_version": "21.0.2+13-LTS",
    "pid": 48102
  }
}
```

---

### 14. Anti-Patterns & Pitfalls

#### Anti-Pattern: Field Injection
Penggunaan `@Autowired` langsung pada private field.

*Buruk:*
```java
@Service
public class PaymentProcessingService {
    @Autowired
    private PaymentGateway paymentGateway; // Mengabaikan enkapsulasi, sulit diuji tanpa reflection frameworks.
}
```

*Refactored (Constructor Injection Immutability):*
```java
@Service
public class PaymentProcessingService {
    private final PaymentGateway paymentGateway;

    // Dependensi eksplisit, immutable (final), dan mudah di-inject secara manual via constructor unit testing.
    public PaymentProcessingService(PaymentGateway paymentGateway) {
        this.paymentGateway = java.util.Objects.requireNonNull(paymentGateway, "PaymentGateway must not be null");
    }
}
```

#### Anti-Pattern: Monolithic God-Configuration Class
Menempatkan puluhan deklarasi `@Bean` infrastruktur yang tidak saling berhubungan di satu kelas `@Configuration`.

*Refactored:*
Pisahkan kelas konfigurasi berdasarkan domain bounded context: `DatabaseConfiguration`, `SecurityConfiguration`, `MessagingConfiguration`. Manfaatkan modular imports via `@Import({DatabaseConfiguration.class, SecurityConfiguration.class})`.

---

### 15. Ecosystem Integration
Spring Boot terintegrasi dengan ekosistem enterprise modern melalui mekanisme plug-in dan build packing:
- **Spring Boot Maven Plugin:** Bertanggung jawab membundel dependensi ke dalam *Fat JAR* / *Uber JAR* dengan skema classloading khusus via `org.springframework.boot.loader.launch.JarLauncher`.
- **Cloud-Native Buildpacks:** Dukungan pembuatan OCI-compliant container image secara langsung tanpa memerlukan Dockerfile:
  ```bash
  mvn spring-boot:build-image -Dspring-boot.build-image.imageName=registry.internal/core-service:v1.0.0
  ```
- **GraalVM Native Image Support:** Menghasilkan native executable binary OS-dependent melalui plugin `native-maven-plugin`.

---

### 16. Verification & Testing

Pola testing slice IoC container yang deterministic: validasi isolasi Auto-Configuration tanpa me-load server web servlet.

File: `src/test/java/com/architecture/platform/audit/AuditAutoConfigurationTest.java`
```java
package com.architecture.platform.audit;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

import static org.assertj.core.api.Assertions.assertThat;

class AuditAutoConfigurationTest {

    private final ApplicationContextRunner contextRunner = new ApplicationContextRunner()
        .withConfiguration(AutoConfigurations.of(AuditAutoConfiguration.class));

    @Test
    @DisplayName("Harus memuat ExecutionAuditAspect ketika properti platform.audit.enabled bernilai true")
    void shouldRegisterAspectWhenPropertyEnabled() {
        this.contextRunner
            .withPropertyValues("platform.audit.enabled=true", "platform.audit.execution-threshold-millis=500")
            .run(context -> {
                assertThat(context).hasSingleBean(ExecutionAuditAspect.class);
                assertThat(context).hasSingleBean(AuditProperties.class);
            });
    }

    @Test
    @DisplayName("Harus TIDAK memuat ExecutionAuditAspect ketika properti platform.audit.enabled bernilai false")
    void shouldBackOffWhenPropertyDisabled() {
        this.contextRunner
            .withPropertyValues("platform.audit.enabled=false")
            .run(context -> {
                assertThat(context).doesNotHaveBean(ExecutionAuditAspect.class);
            });
    }

    @Test
    @DisplayName("Harus menghormati Bean kustom yang disediakan pengguna (ConditionalOnMissingBean)")
    void shouldRespectCustomUserBean() {
        this.contextRunner
            .withPropertyValues("platform.audit.enabled=true")
            .withUserConfiguration(CustomAspectConfiguration.class)
            .run(context -> {
                assertThat(context).hasSingleBean(ExecutionAuditAspect.class);
                assertThat(context).hasBean("customAspect");
            });
    }

    static class CustomAspectConfiguration {
        @org.springframework.context.annotation.Bean
        public ExecutionAuditAspect customAspect(AuditProperties properties) {
            return new ExecutionAuditAspect(properties);
        }
    }
}
```

---

### 17. Troubleshooting Guide

#### Alur Diagnostik Inisialisasi Context
```
                     +-------------------------------+
                     |   Startup Failure Detected    |
                     +-------------------------------+
                                     │
                                     ▼
                +-----------------------------------------+
                | Eksekusi dengan flag debug:             |
                | java -jar app.jar --debug               |
                +-----------------------------------------+
                                     │
                                     ▼
                +-----------------------------------------+
                | Periksa 'CONDITIONS EVALUATION REPORT' |
                +-----------------------------------------+
                                     │
            ┌────────────────────────┴────────────────────────┐
            ▼                                                 ▼
[Kondisi Tidak Terpenuhi]                         [Konflik Duplikasi / Siklik]
Periksa bagian "Negative matches":                Periksa Trace Exception:
- Classpath dependency missing?                   - BeanCurrentlyInCreationException
- @ConditionalOnProperty mismatch?                - ConflictingBeanDefinitionException
            │                                                 │
            ▼                                                 ▼
Perbaiki POM dependencies                         Gunakan @Primary, @Qualifier,
atau sinkronkan environment                       atau perbaiki graf dependensi
```

#### Diagnostic Commands
1. **Analisis Report Evaluasi Kondisi Otomatis:**
   ```bash
   java -jar target/application.jar --debug > condition-report.log
   grep -A 10 "Negative matches:" condition-report.log
   ```
2. **Cek Seluruh Definisi Bean yang Terdaftar:**
   Akses via Actuator:
   ```bash
   curl -s http://localhost:8080/actuator/beans | jq '.contexts.application.beans | keys'
   ```

---

### 18. Real-World Case Study

#### Konteks Sistem
Platform Core Banking bertransisi dari deployment monolitik (WebLogic WAR) ke arsitektur container microservices berbasis Spring Boot.

#### Masalah Produksi
Pada deployment kluster staging berisi 20 microservices, cluster mengalami masalah *thrashing* memori dan waktu deployment memakan waktu hingga 45 menit. Waktu booting satu service mencapai 90 detik. Investigasi menunjukkan bahwa library internal `platform-enterprise-starter` menyertakan auto-configuration legacy yang memindai Hibernate ORM, RabbitMQ, Kafka, dan MongoDB secara simultan, terlepas dari kebutuhan riil service tersebut.

#### Solusi Arsitektural
1. **Dekomposisi Starter:** Memecah `platform-enterprise-starter` menjadi unit granular: `platform-audit-starter`, `platform-messaging-kafka-starter`, dan `platform-rdbms-starter`.
2. **Implementasi Kondisi Ketat:** Menambahkan `@ConditionalOnClass` dan `@ConditionalOnProperty` pada setiap Auto-Configuration.
3. **Pembersihan SPI AutoConfiguration:** Memigrasikan registrasi konfigurasi dari format usang `META-INF/spring.factories` ke `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports` untuk menghindari pemindaian refleksi massal pada startup.

#### Dampak Operasional
```
Metric                       Sebelum Refactoring     Setelah Refactoring    Peningkatan
Startup Time per Service     88.4 detik              4.2 detik              ~95% reduksi
Metaspace Memory Usage       240 MB                  68 MB                  ~71% reduksi
Deployment Duration (20 Pod) 45 menit                3.5 menit              ~92% reduksi
```

---

### 19. Best Practice Checklist

- [ ] **Constructor Injection Mandatory:** Jangan pernah menggunakan field injection (`@Autowired private X x;`). Wajib gunakan constructor injection dengan immutable `final` fields.
- [ ] **Type-Safe Configuration:** Bind konfigurasi external ke `record` atau class menggunakan `@ConfigurationProperties` daripada mengeksekusi `@Value("${property}")` berulang-ulang.
- [ ] **Modularitas Auto-Configuration:** Custom Auto-Configuration internal harus selalu dilindungi oleh pasangan anotasi `@ConditionalOnClass` dan `@ConditionalOnMissingBean`.
- [ ] **Isolasi External Library:** Bungkus integrasi library third-party ke dalam bean adapter agar boundary domain service tidak terkontaminasi API eksternal.
- [ ] **Hindari Logika Bisnis di Komponen Aware:** Antarmuka `ApplicationContextAware` atau `BeanFactoryAware` hanya boleh digunakan untuk ekstensi infrastruktur framework, bukan business logic.
- [ ] **Minimalkan Global Component Scan:** Pastikan base package `@ComponentScan` spesifik dan tidak mencakup root direktori yang tidak perlu.
- [ ] **Matikan Fitur Non-Esensial di Production:** Matikan integrasi banner, JMX, dan endpoint Actuator yang tidak diautentikasi.

---

### 20. Next Architectural Steps
Lanjutkan ke **Bab 01 Modul 02: Advanced Configuration Processing, Property Binding Mechanics, dan Profile Orchestration**. 

Materi selanjutnya akan membongkar internal arsitektur dari:
- `PropertySourceLoader` dan urutan precedence resolusi 17 layer konfigurasi Spring Boot.
- Mekanisme parsing YAML vs Flat Properties melalui `OriginTrackedYamlLoader`.
- Validasi terstruktur data konfigurasi enterprise menggunakan Hibernate Validator SPI terintegrasi.