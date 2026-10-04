# BAB 02: Configuration Engine, Profiles, & Bootstrapping Mechanism
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Principal Software Engineer / Lead Backend Engineer diharapkan mampu:
1. **Menganalisis Internal Bootstrapping**: Menguraikan siklus hidup eksekusi `SpringApplication.run()`, interaksi `BootstrapContext`, peran `ApplicationContextInitializer`, hingga fase instansiasi `ApplicationListener`.
2. **Menguasai Hierarki Resolusi Konfigurasi**: Menavigasi dan memanipulasi lebih dari 17 layer `PropertySource` di dalam `ConfigurableEnvironment` tanpa menimbulkan ambiguitas resolusi.
3. **Mengimplementasikan Config Data API Modern**: Menggunakan fitur `spring.config.import` untuk mengintegrasikan volume Kubernetes (`configtree:`), Consul, dan HashiCorp Vault.
4. **Menerapkan Validasi Type-Safe Immutable**: Mengembangkan objek `@ConfigurationProperties` yang *immutable* (`@ConstructorBinding`) dengan validasi deklaratif JSR-380 (`jakarta.validation`) dan *custom converters*.
5. **Mendesain Mekanisme Dynamic Configuration Refresh**: Membangun mekanisme pembaruan konfigurasi *runtime* tanpa *restart* pod, serta memahami trade-off konkurensi memori antara Spring Cloud `@RefreshScope` dan thread-safe snapshotting berbasis `AtomicReference`.

---

### 2. Prerequisite
Sebelum mendalami modul ini, peserta wajib menguasai:
* Pemahaman fundamental Spring Core (IoC, DI, *Bean Lifecycle*, `BeanPostProcessor`, `BeanFactoryPostProcessor`).
* Java 17/21 LTS (*Records*, *Sealed Interfaces*, *Pattern Matching*, *Virtual Threads* basics).
* Dasar orkestrasi kontainer (Kubernetes `ConfigMap`, `Secret`, *Volume Mounts*, *Rolling Update*).
* Model konkurensi Java Memory Model (JMM), khususnya *visibility semantics* (`volatile`, `AtomicReference`, CAS).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Anatomi Siklus Hidup `SpringApplication.run()`
Proses bootstrap Spring Boot bukan sekadar instansiasi kelas Java standar, melainkan orkestrasi peristiwa berurutan:

```
[JVM Starts]
     │
     ▼
[SpringApplication.<init>]
     ├─ Deduksi WebApplicationType (NONE, SERVLET, REACTIVE) via Classpath inspection
     ├─ Pemuatan BootstrapRegistryInitializer (META-INF/spring.factories)
     ├─ Pemuatan ApplicationContextInitializer
     └─ Pemuatan ApplicationListener
     │
     ▼
[SpringApplication.run()]
     ├─ 1. Start StopWatch
     ├─ 2. Inisialisasi DefaultBootstrapContext
     ├─ 3. Trigger Event: ApplicationStartingEvent
     ├─ 4. Resolusi Arguments & Environment Configuration
     │     ├─ Create ConfigurableEnvironment (misal: StandardServletEnvironment)
     │     ├─ Eksekusi EventListener: ApplicationEnvironmentPreparedEvent
     │     └─ Process ConfigDataLoaders via ConfigFileApplicationListener / ConfigDataEnvironmentPostProcessor
     ├─ 5. Print Banner
     ├─ 6. Instansiasi ApplicationContext via ApplicationContextFactory
     │     └─ AnnotationConfigServletWebServerApplicationContext (untuk MVC)
     ├─ 7. Context Preparation (prepareContext)
     │     ├─ Asosiasi Environment ke Context
     │     ├─ Eksekusi ApplicationContextInitializer.initialize()
     │     ├─ Trigger Event: ApplicationContextInitializedEvent
     │     ├─ Registrasi Bootstrap Context Beans ke BeanFactory
     │     └─ Trigger Event: ApplicationPreparedEvent
     ├─ 8. Context Refresh (refreshContext -> AbstractApplicationContext.refresh())
     │     ├─ invokeBeanFactoryPostProcessors() (Termasuk ConfigurationClassPostProcessor)
     │     ├─ registerBeanPostProcessors() (Termasuk ConfigurationPropertiesBindingPostProcessor)
     │     ├─ onRefresh() -> WebServer creation (Embedded Tomcat/Netty start)
     │     ├─ finishBeanFactoryInitialization() -> Pre-instantiate singletons
     │     └─ finishRefresh() -> LifecycleProcessor start, trigger ContextRefreshedEvent
     ├─ 9. Trigger Event: ApplicationStartedEvent
     ├─ 10. Eksekusi ApplicationRunner & CommandLineRunner
     └─ 11. Trigger Event: ApplicationReadyEvent
```

#### B. Resolusi ConfigData API & Hierarki `PropertySource`
Mulai Spring Boot 2.4+, arsitektur pembacaan file properti dirombak total menggunakan **Config Data API**. Mekanisme lama (`ConfigFileApplicationListener`) digantikan oleh `ConfigDataEnvironmentPostProcessor`. Resolusi konfigurasi berjalan secara hierarkis. Jika terdapat kunci properti yang sama, urutan prioritas berikut berlaku (dari prioritas **tertinggi** ke **terendah**):

1. **Devtools global settings properties** (`~/.config/spring-boot-devtools.properties`).
2. **`@TestPropertySource`** pada test suite integration.
3. **`@SpringBootTest#properties`** annotation attribute.
4. **Command-line arguments** (e.g., `--server.port=9090`).
5. **Spring Boot Config Argument** (`SPRING_APPLICATION_JSON`).
6. **ServletConfig / ServletContext init parameters**.
7. **JNDI attributes** (`java:comp/env`).
8. **System Properties** (`System.getProperties()`, e.g., `-Dapp.rate-limit=100`).
9. **OS Environment Variables** (e.g., `APP_RATE_LIMIT=100`).
10. **RandomValuePropertySource** (`random.*`).
11. **Profile-specific application properties di luar packaged jar** (`config/application-{profile}.properties` atau `.yaml`).
12. **Profile-specific application properties di dalam packaged jar** (`src/main/resources/application-{profile}.properties`).
13. **Application properties di luar packaged jar** (`config/application.properties`).
14. **Application properties di dalam packaged jar** (`src/main/resources/application.properties`).
15. **`@PropertySource` annotations** pada `@Configuration` classes.
16. **Default properties** (`SpringApplication.setDefaultProperties`).

#### C. Mekanisme Binding `@ConfigurationProperties`
Binding properti ke Java Object ditangani oleh `ConfigurationPropertiesBindingPostProcessor`. 
Ketika Spring menemukan kelas beranotasi `@ConfigurationProperties`:
1. `ConfigurationPropertyName` menguraikan nama konfigurasi menjadi canonical tokens (contoh: `app.payment-service.timeout-ms` dipecah menjadi list token `[app, payment-service, timeout-ms]`).
2. **Relaxed Binding Engine** memetakan format *kebab-case*, *camelCase*, *snake_case*, dan *UPPER_SNAKE_CASE* ke dalam variabel target yang sama.
3. Objek diinstansiasi:
   * **Java Record / Constructor Binding**: `ConstructorParametersBinder` memanfaatkan refleksi parameter konstruktor untuk mencocokkan setiap nilai properti, mengonversinya via `ConversionService`, lalu memvalidasi via Bean Validation API sebelum objek selesai dikonstruksi (*fully initialized immutable object*).
   * **Java Bean (Setter Binding)**: Instansiasi default constructor dipanggil, diikuti pemanggilan mutator (`setter`). Jika properti tidak ditemukan, field bernilai null atau default.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (`@Value`) | Pendekatan Enterprise Modern (`@ConfigurationProperties` Immutable) |
| :--- | :--- | :--- |
| **Type Safety** | Lemah. Mengandalkan `String` parsing via SpEL (`@Value("${app.timeout:1000}")`). | Sangat Kuat. Strongly-typed, mapped langsung ke tipe domain (`Duration`, `DataSize`, Custom Records). |
| **Fail-Fast Behavior** | Gagal saat bean diinjeksi atau saat runtime method dieksekusi jika terjadi type mismatch. | Gagal total saat bootstrap (*Startup Phase*). Mencegah aplikasi melayani trafik dalam kondisi konfigurasi parsial. |
| **Immutability** | Buruk. Field umumnya membutuhkan modifikasi atau direct injection; rentan manipulasi internal. | Sempurna. Menggunakan Java Records atau `@ConstructorBinding` tanpa *setter*, menjamin *thread-safety*. |
| **Validation** | Sangat Terbatas. Validasi manual imperatif di `@PostConstruct`. | Deklaratif & Komprehensif. Mengintegrasikan `@Validated` dan JSR-380 (`@NotNull`, `@Min`, custom constraints). |
| **Grouping & Structure** | Terfragmentasi di berbagai service/controller. | Terpusat dalam satu boundary domain class; mudah diekspor menjadi dokumentasi konfigurasi (*Metadata Generator*). |

---

### 5. How (Workflow Detail)

Alur kerja resolusi konfigurasi eksternal pada runtime Kubernetes adalah sebagai berikut:

```
[Pod Start]
    │
    ├─► 1. Kubernetes memuat ConfigMap/Secret ke Volume Mount: /etc/config/app/
    │
    ├─► 2. JVM diinstansiasi dengan args:
    │      --spring.config.import=configtree:/etc/config/app/
    │
    ├─► 3. Spring Boot Bootstrapping memicu ConfigDataEnvironmentPostProcessor
    │      │
    │      ├─ Parser membaca directory tree:
    │      │  /etc/config/app/database/url -> file content dibaca sbg property 'database.url'
    │      │  /etc/config/app/database/pool-size -> property 'database.pool-size'
    │      │
    │      └─ Injeksi ConfigTreePropertySource ke dalam ConfigurableEnvironment
    │
    ├─► 4. ConfigurationPropertiesBindingPostProcessor membaca Environment
    │      │
    │      ├─ Relaxed Binding mengonversi kebab-case/directory-name ke target fields
    │      ├─ Konversi String "5000ms" -> Duration.ofMillis(5000)
    │      └─ Eksekusi ValidatorFactory -> Validasi batasan JSR-380
    │
    └─► 5. Konfigurasi berhasil di-bind ke Immutable Record Context -> Bean siap digunakan
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Pasokan Daya Industri
Bayangkan aplikasi backend sebagai sebuah pabrik manufaktur modern berdaya tinggi:
* **`Environment`**: Sistem panel distribusi listrik utama pabrik. Sumber listrik bisa berasal dari Generator Cadangan Lokal (`application.properties`), Jalur PLN Nasional (`OS Environment Variables`), atau Direct Bypass Transformer (`Command Line Arguments`).
* **`PropertySources`**: Berbagai terminal input ke panel tersebut. Terminal prioritas tinggi akan memutus (override) pasokan dari terminal berprioritas lebih rendah jika keduanya aktif.
* **`ConfigurationProperties`**: Regulator dan adaptor daya spesifik yang menjamin bahwa mesin presisi (Business Logic Services) hanya menerima arus dengan voltase, frekuensi, dan impedansi yang tepat. Jika voltase dari panel tidak sesuai (gagal validasi), sekring utama putus seketika sebelum mesin dinyalakan (*fail-fast at startup*).

#### Diagram Resolusi Prioritas
```
+-------------------------------------------------------------+
| PRIORITAS TERTINGGI: Command Line Args (--server.port=8080) |
+-------------------------------------------------------------+
                              │ (Overrides)
                              ▼
+-------------------------------------------------------------+
| Java System Properties (-Dserver.port=9090)                 |
+-------------------------------------------------------------+
                              │ (Overrides)
                              ▼
+-------------------------------------------------------------+
| OS Environment Variables (SERVER_PORT=80)                   |
+-------------------------------------------------------------+
                              │ (Overrides)
                              ▼
+-------------------------------------------------------------+
| ConfigTree / spring.config.import (Kubernetes Secret/Config)|
+-------------------------------------------------------------+
                              │ (Overrides)
                              ▼
+-------------------------------------------------------------+
| Packaged Config (src/main/resources/application.yaml)       |
+-------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Fundamental Immutable Configuration Properties
Implementasi pembacaan konfigurasi HTTP client dasar dengan Java Record.

```java
package com.enterprise.config;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;
import org.springframework.validation.annotation.Validated;

import java.time.Duration;

@Validated
@ConfigurationProperties(prefix = "integrations.payment-gateway")
public record PaymentGatewayProperties(
        @NotBlank
        String baseUrl,

        @NotBlank
        String apiKey,

        @Min(100) @Max(10000)
        @DefaultValue("2500")
        int connectTimeoutMs,

        @DefaultValue("5s")
        Duration readTimeout
) {}
```

#### B. Practical Example: Production-Grade Resilient Configuration Engine
Implementasi tingkat enterprise mencakup:
1. Custom Converter untuk masked sensitive data.
2. Custom JSR-380 Validator untuk validasi dependensi antar-field.
3. Immutable nested properties dengan dynamic metrics reporting via snapshotting pattern.

```java
package com.enterprise.infra.config;

import jakarta.validation.Constraint;
import jakarta.validation.ConstraintValidator;
import jakarta.validation.ConstraintValidatorContext;
import jakarta.validation.Payload;
import jakarta.validation.constraints.NotNull;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.boot.convert.ApplicationConversionService;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.convert.converter.Converter;
import org.springframework.format.FormatterRegistry;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.lang.annotation.*;
import java.time.Duration;
import java.util.List;
import java.util.Map;

// ==========================================
// 1. DOMAIN MODELS & IMMUTABLE PROPERTIES
// ==========================================

@Validated
@ValidCircuitBreakerConfig
@ConfigurationProperties(prefix = "resilience.engine")
public record ResilienceEngineProperties(
        boolean enabled,
        @NotNull ExecutionMode executionMode,
        CircuitBreakerSettings circuitBreaker,
        Map<String, TargetServicePolicy> services
) {
    public enum ExecutionMode { FAIL_FAST, GRACEFUL_DEGRADATION }

    public record CircuitBreakerSettings(
            int slidingWindowSize,
            float failureRateThreshold,
            Duration waitDurationInOpenState,
            MaskedSecret internalApiKey
    ) {}

    public record TargetServicePolicy(
            String endpoint,
            Duration timeout,
            int maxRetryAttempts,
            List<Integer> retryableStatusCodes
    ) {}
}

// Objek khusus untuk melindungi secret agar tidak bocor via heap dump / logging
public record MaskedSecret(String rawSecret) {
    @Override
    public String toString() {
        return "******[PROTECTED]******";
    }
}

// ==========================================
// 2. CUSTOM CONVERTER
// ==========================================

public class StringToMaskedSecretConverter implements Converter<String, MaskedSecret> {
    @Override
    public MaskedSecret convert(String source) {
        if (source == null || source.isBlank()) {
            return new MaskedSecret("");
        }
        return new MaskedSecret(source.trim());
    }
}

// ==========================================
// 3. JSR-380 CUSTOM CLASS-LEVEL VALIDATOR
// ==========================================

@Target({ElementType.TYPE})
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = CircuitBreakerConfigValidator.class)
@Documented
@interface ValidCircuitBreakerConfig {
    String message() default "failureRateThreshold must be between 1.0 and 100.0, and slidingWindowSize must be >= 10";
    Class<?>[] groups() default {};
    Class<? extends Payload>[] payload() default {};
}

public class CircuitBreakerConfigValidator implements ConstraintValidator<ValidCircuitBreakerConfig, ResilienceEngineProperties> {
    @Override
    public boolean isValid(ResilienceEngineProperties value, ConstraintValidatorContext context) {
        if (value == null || !value.enabled()) {
            return true;
        }

        var cb = value.circuitBreaker();
        if (cb == null) {
            context.disableDefaultConstraintViolation();
            context.buildConstraintViolationWithTemplate("Circuit breaker settings must be present when enabled is true")
                    .addPropertyNode("circuitBreaker")
                    .addConstraintViolation();
            return false;
        }

        boolean validSlidingWindow = cb.slidingWindowSize() >= 10;
        boolean validThreshold = cb.failureRateThreshold() >= 1.0f && cb.failureRateThreshold() <= 100.0f;

        return validSlidingWindow && validThreshold;
    }
}

// ==========================================
// 4. REGISTRATION CONTEXT
// ==========================================

@Configuration(proxyBeanMethods = false)
@ConfigurationPropertiesScan(basePackages = "com.enterprise.infra.config")
public class ResilienceConfigurationInfrastructure implements WebMvcConfigurer {

    // Registrasi konverter khusus ke ConversionService Spring Boot
    @Configuration(proxyBeanMethods = false)
    public static class CustomConverterConfiguration {
        public CustomConverterConfiguration(org.springframework.core.convert.support.ConfigurableConversionService conversionService) {
            conversionService.addConverter(new StringToMaskedSecretConverter());
        }
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Arsitektur Transaksi Global Financial Switch (50.000 TPS)
Sebuah bank tier-1 multinasional memigrasikan infrastruktur *Core Payment Routing* ke Kubernetes.

#### Permasalahan:
1. **Security Isolation**: API Key transaksi tidak boleh masuk ke Git atau tersimpan di file plaintext image kontainer.
2. **Operational Latency**: Penggantian profile timeout rute payment (misal: Visa, Mastercard, JCB) harus terjadi tanpa *application restart* (Zero-Downtime), namun penggunaan `@RefreshScope` dari Spring Cloud menyebabkan micro-stutter (latensi spike p99 hingga 800ms) akibat lock contention saat sinkronisasi bean singleton.
3. **Multi-Tenancy Drift**: Format environment variable dari Kubernetes ConfigMap kerap kali mismatch dengan variabel di Helm Chart (contoh: pemakaian tanda minus `-` vs garis bawah `_`).

#### Solusi Arsitektur:
1. **ConfigTree Engine**: Memanfaatkan `spring.config.import=configtree:/var/run/secrets/payment/` untuk membaca Kubernetes Mounted Secret volume secara native tanpa dependency agent eksternal.
2. **Zero-Lock Atomic Dynamic Config**: Mengganti `@RefreshScope` dengan decoupled configuration subscriber menggunakan `AtomicReference`.
3. **Environment PostProcessor Interceptor**: Memvalidasi integritas environment saat fase `ApplicationEnvironmentPreparedEvent`.

#### Implementasi Dynamic Dynamic Routing Engine (Atomic Hot-Swap):

```java
package com.enterprise.routing;

import com.enterprise.infra.config.ResilienceEngineProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.core.env.Environment;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.concurrent.atomic.AtomicReference;

@Component
public class HighThroughputPaymentRouter {
    private static final Logger log = LoggerFactory.getLogger(HighThroughputPaymentRouter.class);

    private final Environment environment;
    // Menggunakan AtomicReference untuk pembacaan lock-free pada throughput 50k TPS
    private final AtomicReference<ResilienceEngineProperties> activeConfig;

    public HighThroughputPaymentRouter(Environment environment, ResilienceEngineProperties initialProps) {
        this.environment = environment;
        this.activeConfig = new AtomicReference<>(initialProps);
    }

    /**
     * Memperbarui konfigurasi tanpa mengunci thread eksekusi utama.
     * Mekanisme ini membaca ulang ConfigurableEnvironment dan me-rebind objek record.
     */
    public synchronized void reloadConfigurationExplicitly() {
        log.info("Memulai re-binding konfigurasi secara atomik...");
        
        Binder binder = Binder.get(environment);
        ResilienceEngineProperties updatedProps = binder
                .bind("resilience.engine", ResilienceEngineProperties.class)
                .orElseThrow(() -> new IllegalStateException("Gagal me-rebind resilience.engine"));

        // Validasi state baru sebelum swap
        if (updatedProps.circuitBreaker().failureRateThreshold() < 5.0f) {
            log.error("Konfigurasi baru ditolak: failure rate threshold terlalu rendah!");
            return;
        }

        // Lock-free pointer swap
        this.activeConfig.set(updatedProps);
        log.info("Konfigurasi berhasil diperbarui tanpa downtime transaksi.");
    }

    public void executeRouting(String networkId) {
        // Eksekusi baca O(1) tanpa thread contention sama sekali
        ResilienceEngineProperties props = this.activeConfig.get();
        var servicePolicy = props.services().get(networkId);

        if (servicePolicy == null) {
            throw new UnsupportedOperationException("Jalur rute belum terdaftar: " + networkId);
        }

        // Eksekusi pemanggilan downstream
        log.debug("Routing transaksi ke [{}] dengan timeout: {}ms", 
                servicePolicy.endpoint(), servicePolicy.timeout().toMillis());
    }
}
```

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Kerugian | Latency Impact | Operational Cost |
| :--- | :--- | :--- | :--- | :--- |
| **Spring Cloud `@RefreshScope`** | Otomatis me-reload bean context via Actuator `/actuator/refresh`; declarative. | Menghancurkan singleton instance dan merekonstruksinya saat next request. Terjadi synchronized lock pada `GenericScope`. | **Tinggi (Spike p99)**. Menyebabkan GC pressure dan thread blocking pada sistem throughput tinggi. | Rendah dari sisi kode, tinggi dari stabilitas infra. |
| **`AtomicReference` / Dynamic Snapshot** | Non-blocking (Lock-free O(1) read); isolasi mutasi data; sangat stabil di high TPS. | Perlu implementasi custom controller atau scheduled poller untuk memicu re-binding via `Binder`. | **Hampir Nol**. Sesuai untuk sistem low-latency / real-time. | Sedang. Butuh disiplin kode dalam mengelola stateful beans. |
| **Kubernetes Pod Restart (Immutable Infra)** | Zero runtime complexity. Tidak ada state drift antar-pod; konfigurasi deterministik. | Perlu proses rolling update Kubernetes. Membutuhkan waktu 30-120 detik per deployment. | **Nol pada request**, tetapi latensi deployment bertambah. | Tinggi resource overhead (komputasi CPU/Memory cluster naik saat rolling). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Circular Reference pada `EnvironmentPostProcessor`
* **Gejala**: Aplikasi crash saat startup dengan `NullPointerException` atau `BeanDefinitionStoreException`.
* **Akar Masalah**: Mencoba me-inject Spring Bean (`@Autowired`) di dalam `EnvironmentPostProcessor`. Tahap ini dieksekusi **sebelum** `ApplicationContext` atau `BeanFactory` dibuat.
* **Solusi**: Hanya berinteraksi dengan `ConfigurableEnvironment` dan API Spring berbasis primitives di dalam EPP.

#### 2. Relaxed Binding Name Collision pada OS Environment Variables
* **Gejala**: Properti YAML `app.payment-service.timeout-ms` tidak ter-override oleh OS environment variable `APP_PAYMENT_SERVICE_TIMEOUT_MS`.
* **Akar Masalah**: Ambiguitas pemisah token. Di Spring Boot, satu underscore `_` adalah pemisah path token, sedangkan dua underscore `__` digunakan untuk token kebab-case yang mempertahankan struktur nama field.
* **Solusi**: Gunakan `APP_PAYMENTSERVICE_TIMEOUTMS` atau format standar Canonical System: `APP_PAYMENT_SERVICE_TIMEOUT_MS` (Spring Boot dapat memecahnya jika tipe record field bernama `paymentService` -> `timeoutMs`). Gunakan flag debugging logging: `--logging.level.org.springframework.boot.context.properties=DEBUG`.

#### 3. Properti Bernilai Null pada Immutable Properties
* **Gejala**: Nilai field pada record `@ConfigurationProperties` bernilai `null` padahal file YAML terisi.
* **Akar Masalah**: Kurangnya anotasi `@ConfigurationPropertiesScan` atau dependensi `spring-boot-configuration-processor` tidak terpasang di `pom.xml`/`build.gradle`, menyebabkan parameter metadata nama constructor arguments hilang saat runtime tanpa flag Java compiler `-parameters`.
* **Solusi**: Pastikan plugin compiler menyertakan flag `-parameters`:
```xml
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-compiler-plugin</artifactId>
    <configuration>
        <parameters>true</parameters>
    </configuration>
</plugin>
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan Type-Safe Records**: Seluruh konfigurasi sistem WAJIB didefinisikan sebagai Java Record dengan `@ConfigurationProperties`. Dilarang menggunakan `@Value("${...}")` untuk konfigurasi bisnis kritis.
- [ ] **Aktifkan Configuration Processor**: Selalu sertakan `spring-boot-configuration-processor` agar IDE menghasilkan *auto-completion* dan metadata `spring-configuration-metadata.json`.
- [ ] **Deklarasikan Strict Validation**: Pasang constraint JSR-380 (`@NotNull`, `@Min`, `@Max`, `@Pattern`, `@Positive`) di setiap leaf property.
- [ ] **Secure Sensitive Values**: Masking properti kredensial menggunakan custom wrapper type (seperti `MaskedSecret`) agar tidak terekspos di actuator `/env` atau stack trace logging.
- [ ] **Sanitasi Actuator Endpoint**: Matikan sanitasi bawaan yang longgar dan kunci *keys-to-sanitize* di `management.endpoint.env.keys-to-sanitize=password,secret,key,token,credential`.
- [ ] **Gunakan `spring.config.import`**: Pisahkan konfigurasi sensitif (Secret volume mounts) dari file internal menggunakan direktif `configtree:`.
- [ ] **Explicit Profiles Semantics**: Hindari multi-document YAML ganda yang berantakan; gunakan struktur profile terpusat dan hindari profile `default` di environment produksi.
- [ ] **Tentukan Timeout Default**: Properti konfigurasi waktu wajib berjenis `java.time.Duration` dengan explicit fallback value.

---

### 12. Hands-on Practice

Simpan seluruh file berikut ke dalam direktori: `hands-on/m02/`

#### Langkah 1: Inisialisasi Project Descriptor
Buat file `hands-on/m02/pom.xml`:
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
        <version>3.2.3</version>
        <relativePath/>
    </parent>
    <groupId>com.enterprise.handson</groupId>
    <artifactId>bootstrapping-deepdive</artifactId>
    <version>1.0.0-SNAPSHOT</version>

    <properties>
        <java.version>17</java.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-configuration-processor</artifactId>
            <optional>true</optional>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <configuration>
                    <parameters>true</parameters>
                </configuration>
            </plugin>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
```

#### Langkah 2: Buat Custom Bootstrap Environment Post Processor
Buat file `hands-on/m02/src/main/java/com/enterprise/handson/SecurityEnvironmentPostProcessor.java`:
```java
package com.enterprise.handson;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.env.EnvironmentPostProcessor;
import org.springframework.core.Ordered;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.MapPropertySource;

import java.util.Map;

/**
 * Menginjeksi properti keamanan dinamis sebelum ApplicationContext terbentuk.
 */
public class SecurityEnvironmentPostProcessor implements EnvironmentPostProcessor, Ordered {

    @Override
    public void postProcessEnvironment(ConfigurableEnvironment environment, SpringApplication application) {
        // Enforce TLS policy di runtime env
        Map<String, Object> enforcedSecurityProperties = Map.of(
                "server.ssl.enabled-protocols", "TLSv1.3",
                "infra.engine.initialized-by", "EnterpriseEPP"
        );

        MapPropertySource customSource = new MapPropertySource("enforcedSecurityRules", enforcedSecurityProperties);
        environment.getPropertySources().addFirst(customSource);
    }

    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE;
    }
}
```

#### Langkah 3: Daftarkan Post Processor via `org.springframework.boot.env.EnvironmentPostProcessor`
Buat file `hands-on/m02/src/main/resources/META-INF/spring.factories`:
```properties
org.springframework.boot.env.EnvironmentPostProcessor=com.enterprise.handson.SecurityEnvironmentPostProcessor
```

#### Langkah 4: Tulis Implementasi Aplikasi dan Rest Controller
Buat file `hands-on/m02/src/main/java/com/enterprise/handson/HandsOnApplication.java`:
```java
package com.enterprise.handson;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.core.env.Environment;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@SpringBootApplication
@ConfigurationPropertiesScan
public class HandsOnApplication {

    public static void main(String[] args) {
        SpringApplication.run(HandsOnApplication.class, args);
    }

    @Validated
    @ConfigurationProperties(prefix = "cluster.node")
    public record ClusterNodeProperties(
            @NotBlank String datacenter,
            @NotBlank String rackId,
            @NotNull Integer heartbeatIntervalMs
    ) {}

    @RestController
    public static class InspectionController {
        private final ClusterNodeProperties properties;
        private final Environment environment;

        public InspectionController(ClusterNodeProperties properties, Environment environment) {
            this.properties = properties;
            this.environment = environment;
        }

        @GetMapping("/inspect")
        public Object inspect() {
            return Map.of(
                    "configuredDatacenter", properties.datacenter(),
                    "configuredRack", properties.rackId(),
                    "heartbeat", properties.heartbeatIntervalMs(),
                    "tlsEnforced", environment.getProperty("server.ssl.enabled-protocols"),
                    "initializedBy", environment.getProperty("infra.engine.initialized-by")
            );
        }
    }
}
```

#### Langkah 5: Buat File Konfigurasi
Buat file `hands-on/m02/src/main/resources/application.yaml`:
```yaml
server:
  port: 8085

cluster:
  node:
    datacenter: "ap-southeast-1"
    rack-id: "rack-alpha-09"
    heartbeat-interval-ms: 1000
```

#### Langkah 6: Eksekusi dan Pengujian
Jalankan perintah berikut di terminal:
```bash
# 1. Compile project
mvn clean package

# 2. Jalankan aplikasi
java -jar target/bootstrapping-deepdive-1.0.0-SNAPSHOT.jar

# 3. Verifikasi payload melalui endpoint
curl -s http://localhost:8085/inspect
```

Output yang diharapkan:
```json
{
  "configuredDatacenter": "ap-southeast-1",
  "configuredRack": "rack-alpha-09",
  "heartbeat": 1000,
  "tlsEnforced": "TLSv1.3",
  "initializedBy": "EnterpriseEPP"
}
```

---

### 13. Exercise

#### Level: Easy
1. Ubah konfigurasi `heartbeatIntervalMs` agar memiliki batasan JSR-380 minimal `500` dan maksimal `5000`. Coba jalankan aplikasi dengan nilai `100` via parameter command line: `--cluster.node.heartbeat-interval-ms=100`.
2. **Ekspektasi Hasil**: Aplikasi harus melempar `ConfigurationPropertiesBindException` dan menghentikan proses startup dengan exit code non-zero.

#### Level: Medium
1. Buat custom property binding converter yang menerima input string format IP CIDR (contoh: `10.244.0.0/16`) dan secara otomatis memetakannya ke objek domain buatan Anda: `record IpNetwork(InetAddress networkAddress, int prefixLength)`.
2. Pasang converter tersebut dan bind ke dalam field record konfigurasi. Lakukan verifikasi bahwa saat string CIDR tidak valid (misal: `invalid-ip/99`), aplikasi *fail-fast* saat inisialisasi.

#### Level: Hard
1. Buat mekanisme *Dynamic Priority PropertySource* menggunakan `EnvironmentPostProcessor` yang memeriksa keberadaan direktori `/var/override/`.
2. Jika file `/var/override/runtime.properties` ada di host machine, baca file tersebut dan letakkan pada urutan prioritas **paling atas** (mengalahkan command line argument). 
3. Jika file tidak ada, lewati tanpa error log. Tuliskan mekanisme thread-safe test menggunakan `@SpringBootTest`.

---

### 14. Challenge

**Studi Kasus**: Arsitektur Zero-Downtime Secret Rotation dengan Zero Third-Party Discovery Agents.

Sebuah platform perbankan mewajibkan sertifikat mTLS dan private key internal database dirotasi setiap 2 jam sekali oleh DaemonSet internal Kubernetes ke dalam directory volume `/etc/vault/tls/`. 

**Tantangan Arsitektur**:
1. Buat arsitektur bootstrapping Spring Boot yang memantau perubahan file pada direktori `/etc/vault/tls/` menggunakan Java NIO `WatchService` yang berjalan di platform thread terpisah (*Virtual Thread*).
2. Ketika event `ENTRY_MODIFY` terdeteksi pada file konfigurasi:
   * Muat dan validasi struktur konfigurasi baru tanpa merestart pod Spring Boot.
   * Lakukan validasi bahwa private key dan sertifikat baru membentuk pasangan kunci kriptografi yang valid (*cryptographic key-pair integrity check*).
   * Lakukan swap *connection pool credentials* secara atomik di memory sehingga koneksi database baru menggunakan secret baru, sementara transaksi yang sedang *in-flight* dapat menyelesaikan pekerjaannya hingga selesai menggunakan kredensial lama.
3. **Syarat Kritis**: Tidak boleh menggunakan library Spring Cloud (`spring-cloud-starter-bootstrap` atau `spring-cloud-context`). Semua harus dibangun secara native menggunakan Spring Boot Core SPI & primitives.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Konsep Dasar (Basic)
1. **Di manakah letak eksekusi method `ApplicationContextInitializer#initialize` dalam siklus hidup `SpringApplication.run()`?**
   * A. Setelah seluruh singleton bean diinstansiasi.
   * B. Sebelum `ApplicationEnvironmentPreparedEvent` dipancarkan.
   * C. Setelah `ConfigurableApplicationContext` dibuat tetapi sebelum bean definitions di-load (*before refresh*).
   * D. Setelah embedded web server (Tomcat) menyala sempurna.

2. **Manakah urutan prioritas yang benar antara OS Environment Variables dan Java System Properties (`-D`) pada Spring Boot?**
   * A. OS Environment Variables meng-override Java System Properties.
   * B. Java System Properties meng-override OS Environment Variables.
   * C. Keduanya memiliki prioritas identik; nilai terakhir di file jar yang menang.
   * D. Bergantung pada urutan deklarasi di class `application.yaml`.

3. **Anotasi apa yang wajib digunakan agar Java Record dapat dipetakan dari file konfigurasi menggunakan constructor injection secara aman?**
   * A. `@Value`
   * B. `@ConfigurationProperties`
   * C. `@Component` dengan `@Autowired`
   * D. `@DynamicPropertySource`

4. **Kapan `EnvironmentPostProcessor` dieksekusi oleh Spring Boot?**
   * A. Saat HTTP request pertama kali masuk.
   * B. Pada fase `ApplicationEnvironmentPreparedEvent` via SPI `spring.factories`.
   * C. Di dalam method `postProcessBeanFactory`.
   * D. Tepat sebelum JVM shutdown hook dijalankan.

5. **Apa fungsi utama dari artefak `spring-boot-configuration-processor`?**
   * A. Mengenkripsi password di dalam file `application.properties`.
   * B. Menghasilkan metadata JSON untuk auto-completion dan validasi konfigurasi di IDE saat compile time.
   * C. Mengunduh konfigurasi dari remote server Git secara otomatis.
   * D. Menangani komunikasi antar thread pada konfigurasi dinamis.

#### Bagian B: Analisis & Mekanisme (Intermediate)
6. **Jika terdapat konfigurasi `app.max-retry-attempts=3` di `application.yaml` dan variabel OS `APP_MAX_RETRY_ATTEMPTS=5`, berapakah nilai yang akan di-bind ke dalam Java Record field `int maxRetryAttempts`? Jelaskan mekanismenya.**
   * A. `3`, karena file internal YAML memiliki akses lebih dekat ke classpath.
   * B. `5`, karena OS Environment variables memiliki urutan layer prioritas lebih tinggi dibanding application.yaml internal.
   * C. Terjadi exception `AmbiguousPropertyException`.
   * D. Nilai bernilai default `0`.

7. **Mengapa penggunaan `@RefreshScope` pada bean yang melayani operasi berkecepatan tinggi (high-throughput low-latency) berisiko menimbulkan spike latensi pada sistem?**
   * A. Karena `@RefreshScope` menghapus JVM bytecode dari metaspace.
   * B. Karena scope cache di-clear dan proses re-instansiasi singleton memicu locking thread (`synchronized`) pada bean accessor saat request bersamaan tiba.
   * C. Karena GC melakukan full-stop-the-world selama 5 detik.
   * D. Karena port embedded tomcat ditutup sementara selama proses refresh.

8. **Bagaimana format relaxed binding yang valid untuk OS Environment Variable yang merepresentasikan properti kebab-case: `service.client-id`?**
   * A. `SERVICE.CLIENT-ID`
   * B. `service_client_id`
   * C. `SERVICE_CLIENTID` atau `SERVICE_CLIENT_ID`
   * D. `$SERVICE_CLIENT_ID`

9. **Apa keuntungan arsitektural utama memuat konfigurasi menggunakan direktif `spring.config.import=configtree:/path/` di lingkungan Kubernetes?**
   * A. Memungkinkan Spring Boot membaca file biner secara langsung tanpa parsing.
   * B. Mengizinkan pemetaan setiap file di dalam directory tree menjadi key-value terpisah pada Environment secara native sesuai standar K8s Secret/ConfigMap volume mounts.
   * C. Mengabaikan validasi tipe data sehingga mempercepat bootstrap aplikasi.
   * D. Menghilangkan kebutuhan JVM Garbage Collector untuk file konfigurasi.

10. **Apa yang terjadi jika constraint JSR-380 (seperti `@Positive`) gagal divalidasi pada class `@ConfigurationProperties` yang tidak dipasangi anotasi `@Validated`?**
    * A. Startup aplikasi gagal total dengan melempar `MethodArgumentNotValidException`.
    * B. Nilai invalid tetap lolos dan diinjeksikan ke dalam bean tanpa error sama sekali.
    * C. Spring Boot otomatis mengubah nilainya menjadi angka 1.
    * D. Konfigurasi dilewati dan bean bernilai `null`.

#### Bagian C: Skenario Kasus Produksi (Enterprise Analysis)
11. **Skenario 1**: Sebuah tim platform engineering meluncurkan microservice ke Kubernetes. Pada deployment YAML, mereka mendefinisikan environment variable `SPRING_CONFIG_IMPORT=vault://secret-path`. Namun, saat container dimulai, pod gagal dalam status `CrashLoopBackOff` dengan pesan: `Unsupported config data location: 'vault://secret-path'`.
    * **Analisis**: Apa yang menyebabkan kegagalan ini di tingkat Spring Boot core bootstrap, dan apa yang harus ditambahkan agar Spring Boot mengenali prefix URI tersebut?

12. **Skenario 2**: Dalam cluster multi-node, tim DevOps melakukan hot-swap file konfigurasi pada volume mount Kubernetes. Mereka memperhatikan bahwa pod lama yang tidak di-restart tetap menggunakan konfigurasi usang meskipun file di disk `/etc/config/` telah berubah.
    * **Analisis**: Mengapa Spring Boot secara *default* tidak langsung memperbarui properti di memory saat isi file volume berubah, dan strategi apa yang paling tepat untuk mendeteksi perubahan tersebut secara efisien tanpa restart pod?

13. **Skenario 3**: Sebuah bank mengimplementasikan sistem enkripsi internal. Mereka mendaftarkan `EnvironmentPostProcessor` kustom untuk mendekripsi database password yang disimpan dalam format `ENC(cipherText)`. Namun, saat dijalankan di production, aplikasi crash dengan error `Database connection failed: Access Denied for user 'root'@'...' (using password: NO)`. Pada saat logging di trace, nilai password ternyata masih berupa plaintext string `ENC(...)`.
    * **Analisis**: Mengapa `EnvironmentPostProcessor` milik mereka gagal mendekripsi nilai tersebut sebelum DataSource dibuat? Komponen urutan (*ordering*) apa yang terlewatkan?

---

### Jawaban dan Pembahasan Quiz

#### Kunci Jawaban Bagian A:
1. **C** — `ApplicationContextInitializer` dipanggil pada method `prepareContext()`, setelah context terbentuk tetapi sebelum definisi bean di-load dan method `refresh()` dieksekusi.
2. **B** — Dalam 17 urutan hierarki Spring Boot, Java System Properties (Layer 8) memiliki prioritas lebih tinggi daripada OS Environment Variables (Layer 9).
3. **B** — `@ConfigurationProperties` (disertai `@ConfigurationPropertiesScan` atau `@EnableConfigurationProperties`) adalah mekanisme deklaratif resmi untuk constructor binding ke Java Record.
4. **B** — `EnvironmentPostProcessor` dijalankan oleh `ConfigDataEnvironmentPostProcessor` melalui event `ApplicationEnvironmentPreparedEvent` via SPI `META-INF/spring.factories`.
5. **B** — Artefak ini mengekstrak metadata dari kode Java saat kompilasi untuk menyediakan auto-complete dan dokumentasi properti di IDE.

#### Kunci Jawaban Bagian B:
6. **B** — OS Environment Variable berada di layer prioritas yang lebih tinggi daripada file konfigurasi internal yang dipaketkan di dalam JAR. Relaxed binder secara otomatis memetakan `APP_MAX_RETRY_ATTEMPTS` ke `app.maxRetryAttempts`.
7. **B** — `@RefreshScope` mengosongkan proxy target. Ketika banyak thread memanggil bean tersebut secara bersamaan pada TPS tinggi, pemanggilan dikunci (`synchronized`) untuk merekonstruksi instance bean baru, mengakibatkan penumpukan thread dan spike latensi.
8. **C** — Spring relaxed binding mengizinkan penulisan tanpa underscore untuk camelCase atau pemisahan underscore standar untuk kebab-case (`SERVICE_CLIENT_ID`).
9. **B** — `configtree:` didesain khusus untuk paradigma Kubernetes di mana setiap file dalam direktori melambangkan nama key dan konten file melambangkan nilainya.
10. **B** — Spring Boot membutuhkan `@Validated` pada kelas `@ConfigurationProperties` untuk mengaktifkan validasi JSR-380. Tanpa `@Validated`, constraint annotation seperti `@Positive` akan diabaikan.

#### Kunci Jawaban & Analisis Bagian C:
11. **Analisis Skenario 1**:
    * **Akar Masalah**: Spring Boot Core tidak memiliki built-in resolver untuk custom protocol prefix `vault://`.
    * **Solusi**: Tim harus menyertakan library abstraction yang mengimplementasikan SPI `ConfigDataLoader` dan `ConfigDataLocationResolver` (seperti Spring Cloud Vault) ke dalam classpath, atau mendaftarkan resolver kustom di `META-INF/spring.factories` agar Spring Boot memahami cara membaca skema URI tersebut saat fase bootstrap.
12. **Analisis Skenario 2**:
    * **Akar Masalah**: `ConfigurableEnvironment` membaca properti ke dalam struktur in-memory saat fase startup. File I/O tidak dipantau secara default untuk menghemat resource CPU/disk.
    * **Solusi**: Terapkan mekanisme pengawasan disk via Java NIO `WatchService` atau polling Actuator `/refresh`. Sebagai alternatif arsitektur cloud-native modern, gunakan Kubernetes Controller/Operator yang memicu rolling-restart pod secara bertahap, atau gunakan decoupled `AtomicReference` reader.
13. **Analisis Skenario 3**:
    * **Akar Masalah**: Masalah urutan prioritas (`Ordered`). Kemungkinan custom `EnvironmentPostProcessor` tidak mengimplementasikan interface `Ordered` atau memiliki order lebih rendah daripada post processor Spring Boot default, sehingga DataSource initialization mencoba membaca properti sebelum post processor selesai melakukan mutasi pada `PropertySource`.
    * **Solusi**: Implementasikan `Ordered` pada EPP dengan prioritas tertinggi: `public int getOrder() { return Ordered.HIGHEST_PRECEDENCE; }` dan pastikan memodifikasi `PropertySource` di urutan pertama (`environment.getPropertySources().addFirst(...)`).

---

### 16. Summary

1. **Bootstrapping Deterministic Lifecycle**: Inisialisasi Spring Boot melalui `SpringApplication.run()` memisahkan fase bootstrap secara tegas: penyiapan Environment (`ConfigurableEnvironment`), inisialisasi Context (`ApplicationContextInitializer`), loading bean definitions, dan eksekusi lifecycle refresh.
2. **Layered Configuration Resolution**: Spring Boot menerapkan sistem prioritas 17 layer. Konfigurasi paling luar (Command Line & System Properties) selalu menimpa konfigurasi internal (YAML classpath). Memahami urutan ini adalah syarat mutlak mencegah konfigurasi yang terlewat atau tidak sengaja tertimpa (*unintended property shadowing*).
3. **Immutability & Robust Typing**: Pendekatan modern enterprise menolak penggunaan `@Value` untuk logika bisnis berskala besar. Penggunaan Java Records yang dikombinasikan dengan `@ConfigurationProperties`, `@Validated`, dan JSR-380 menyediakan type-safety, fail-fast behavior saat bootstrap, serta thread-safety mutlak.
4. **Dynamic High-Throughput Adaptation**: Untuk sistem transaksi berkecepatan tinggi, hindari `@RefreshScope` yang blocking. Gunakan pola pointer hotswap berbasis `AtomicReference` yang dipadukan dengan Spring `Binder` API untuk menghasilkan pembaruan konfigurasi runtime tanpa latensi jitter.