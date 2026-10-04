# Framework Architecture: Spring Boot 3 Deep Dive

---

## SEKSI 01 — IDENTITAS MODUL

*   **Track:** Java Architecture & Enterprise Engineering
*   **Kategori:** 02-Programming-Languages
*   **Bab:** 06 — Framework Architecture & Internals
*   **Modul:** 01 — Framework Architecture: Spring Boot 3 Deep Dive
*   **Prasyarat:**
    *   Penguasaan Java 17+ (Record, Sealed Classes, Pattern Matching)
    *   Pemahaman mendalam Java Reflection, Dynamic Proxy, dan ClassLoader
    *   Pengalaman dasar Inversion of Control (IoC) dan Dependency Injection (DI)
*   **Tech Stack:** Java 21, Spring Boot 3.2+, Spring Framework 6.1+, GraalVM Native Image Tooling, Maven/Gradle

---

## SEKSI 02 — LEARNING OBJECTIVES

1.  **Membongkar Mekanisme Bootstrapping Spring Boot 3:** Mengidentifikasi dan menganalisis secara presisi urutan eksekusi fase `SpringApplication.run()`, inisialisasi `ApplicationContext`, serta manipulasi runtime melalui `BeanFactoryPostProcessor` dan `BeanPostProcessor`.
2.  **Menguasai Anatomi Auto-Configuration:** Merancang, mengabstraksi, dan mengimplementasikan *custom auto-configuration* menggunakan modularitas modern `AutoConfiguration.imports` serta evaluasi conditional beans tingkat lanjut (`@ConditionalOnClass`, `@ConditionalOnMissingBean`, dll.).
3.  **Mengoptimalkan Kompatibilitas Spring Boot 3 & Jakarta EE 10:** Mengatasi hambatan migrasi arsitektur dari `javax.*` ke `jakarta.*` serta memanfaatkan fondasi Spring Framework 6 untuk integrasi cloud-native.
4.  **Mengevaluasi Pipeline Ahead-Of-Time (AOT) & GraalVM:** Mengonfigurasi dan mengevaluasi siklus hidup kompilasi AOT untuk runtime Native Image, meminimalkan *reflection overhead* dan *memory footprint*.
5.  **Mengoperasikan Observabilitas Terintegrasi:** Menerapkan Micrometer Observation API untuk unifikasi metrik, tracing, dan logging tanpa overhead instrumentasi tradisional.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Spring Boot Bukan Sekadar Framework, Melainkan "Opinionated Orchestrator"

Mayoritas software engineer menganggap Spring Boot sebagai framework monolitik yang penuh "sihir" (*black magic*). Paradigma ini keliru. Spring Boot secara fundamental adalah **meta-framework**: mesin otomatisasi yang bertugas menyusun, mengonfigurasi, dan menyuntikkan ketergantungan komponen Spring Framework inti berdasarkan *classpath inspection*, ketersediaan bean, dan environment properties.

```
       [ Mental Model Tradisional ]                  [ Mental Model Enterprise ]
 +---------------------------------------+      +---------------------------------------+
 | "Spring Boot otomatis jalan sendiri,  |  vs  | "Spring Boot adalah state-machine     |
 |  banyak anotasi ajaib tanpa kendali"  |      |  deterministik yang mengevaluasi     |
 |                                       |      |  katalog konfigurasi bersyarat."      |
 +---------------------------------------+      +---------------------------------------+
```

### Prinsip Inti: Convention-over-Configuration Berbasis Kondisi Deterministik

1.  **No Code Generation at Boot:** Auto-configuration tidak menulis kode Java baru saat dijalankan. Ia bekerja murni melalui pendaftaran `BeanDefinition` ke dalam `DefaultListableBeanFactory` secara dinamis.
2.  **Fail-Fast Context Building:** Fase startup didesain untuk gagal sedini mungkin (*fail-fast*) jika kontrak dependensi, alokasi port, atau parsing konfigurasi gagal divalidasi.
3.  **The Cloud-Native Shift (AOT):** Sejak Spring Boot 3, paradigma berpindah dari *Dynamic Runtime Evaluation* (evaluasi runtime reflektif CGLIB/JDK Proxies) menuju *Ahead-Of-Time Closed-World Assumption*. Perubahan ini menuntut pemahaman ketat terhadap registrasi metadata refleksi untuk native binary execution.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Siklus Hidup Eksekusi `SpringApplication.run()`

Diagram berikut menggambarkan urutan fase internal runtime Spring Boot 3 dari inisialisasi *entry point* hingga context stabil (*ready state*):

```
+-------------------------------------------------------------------------------+
|                             SpringApplication.run()                           |
+-------------------------------------------------------------------------------+
                                        |
                                        v
       [1] Create & Start StopWatch / BootstrapContext (DefaultBootstrapContext)
                                        |
                                        v
       [2] Configure Headless Property & Listeners (SpringApplicationRunListeners)
                                        |
                                        v
       [3] Prepare Environment (StandardEnvironment / ApplicationEnvironmentPreparedEvent)
           - Bind ConfigurationProperties (spring.profiles, configs, etc.)
                                        |
                                        v
       [4] Print Banner & Instantiate ApplicationContext
           - (e.g., AnnotationConfigServletWebServerApplicationContext)
                                        |
                                        v
       [5] Prepare Context (postProcessApplicationContext, applyInitializers)
           - Register Spring Boot specific beans (arguments, banner)
                                        |
                                        v
       [6] Refresh Context (AbstractApplicationContext.refresh())
           +--------------------------------------------------------------------+
           |  a. invokeBeanFactoryPostProcessors()                              |
           |     -> ConfigurationClassPostProcessor parses @Configuration       |
           |     -> Process META-INF/spring/org.springframework.boot...imports  |
           |     -> Evaluate @Conditional clauses                               |
           |  b. registerBeanPostProcessors()                                   |
           |  c. initMessageSource() & initApplicationEventMulticaster()        |
           |  d. onRefresh() -> Instantiate Embedded Web Container (Tomcat)     |
           |  e. finishBeanFactoryInitialization()                             |
           |     -> Instantiate Singletons eagerly                              |
           |     -> Apply BeanPostProcessors (AOP Proxies, Validation)          |
           +--------------------------------------------------------------------+
                                        |
                                        v
       [7] Call Run Runners (ApplicationRunner, CommandLineRunner)
                                        |
                                        v
       [8] Application Ready State (Publish ApplicationReadyEvent)
```

### Mekanisme Auto-Configuration Discovery Engine

```
                          ClassPath Scanning Phase
                                     |
                                     v
+---------------------------------------------------------------------------+
| Search META-INF/spring/org.springframework.boot.autoconfigure.            |
| AutoConfiguration.imports                                                 |
+---------------------------------------------------------------------------+
                                     |
                                     v
+---------------------------------------------------------------------------+
| Instantiation of Candidate Configuration Classes                          |
| (Contoh: DataSourceAutoConfiguration, SecurityAutoConfiguration)           |
+---------------------------------------------------------------------------+
                                     |
                                     v
+---------------------------------------------------------------------------+
| Evaluation via ConditionEvaluator                                         |
|  - @ConditionalOnClass (Is Driver on ClassPath?)                          |
|  - @ConditionalOnProperty (Is feature enabled via YAML?)                  |
|  - @ConditionalOnMissingBean (Has user already declared their own Bean?)  |
+---------------------------------------------------------------------------+
                      |                                   |
              [Condition Passes]                  [Condition Fails]
                      |                                   |
                      v                                   v
        +---------------------------+           +--------------------+
        | Register BeanDefinition   |           | Prune Configuration|
        | into BeanFactory Registry |           | from Context Graph |
        +---------------------------+           +--------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Perubahan Mekanisme Discovery: SPI Baru di Spring Boot 3

Sebelum Spring Boot 2.7/3.0, discovery auto-configuration bergantung pada `META-INF/spring.factories` yang menggunakan mekanisme `SpringFactoriesLoader`. 

Di Spring Boot 3, discovery konfigurasi otomatis diubah ke file modular:
`META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`

Pendekatan baru ini memisahkan registrasi auto-configuration dari komponen sistem internal (seperti initializers atau failure analyzers), mengeliminasi overhead parsing berkas tunggal yang berukuran masif serta menyederhanakan tracing kompilasi AOT.

### 2. Dualitas Processor: `BeanFactoryPostProcessor` vs `BeanPostProcessor`

Pahami pemisahan tanggung jawab (*separation of concerns*) di dalam siklus hidup bean:

*   **`BeanFactoryPostProcessor` (BFPP):** Beroperasi pada level **Metadata** bean definition. BFPP dapat memodifikasi konfigurasi bean (nama kelas, scope, argumen konstruktor) *sebelum* instance objek sebenarnya dialokasikan di Java Heap.
    *   *Implementasi Kunci:* `ConfigurationClassPostProcessor`. Kelas ini bertugas mencari anotasi `@Configuration`, memparsing `@Bean`, mengevaluasi kondisi auto-configuration, dan mendaftarkan `BeanDefinition` baru.
*   **`BeanPostProcessor` (BPP):** Beroperasi pada level **Instance** objek bean. BPP dieksekusi *setelah* objek dibuat oleh container (instantiation) dan sesudah properti di-inject. BPP berwenang membungkus instance asli dengan CGLIB/JDK dynamic proxy (misal: penanganan `@Transactional`, validasi bean `@Valid`, atau integrasi Spring AOP).

```
[BeanDefinition Registry]
         |
         v
+-----------------------------------+
|     BeanFactoryPostProcessor      |  <-- Modifikasi Blueprint/Metadata Bean
+-----------------------------------+
         |
         v (Instansiasi Objek Raw di Heap)
+-----------------------------------+
|      BeanPostProcessor: Before    |  <-- Sebelum @PostConstruct
+-----------------------------------+
         |
         v (Inisialisasi)
+-----------------------------------+
|      BeanPostProcessor: After     |  <-- Pembuatan Dynamic AOP Proxy Bean
+-----------------------------------+
         |
         v
  [Fully Usable Bean]
```

### 3. Pipeline Evaluasi Anotasi `@Conditional`

Spring Boot mengevaluasi kondisi secara lazy dan deterministik melalui kelas `ConditionEvaluator`. Pipeline ini memiliki dua fase evaluasi (`ConfigurationPhase`):

1.  `PARSE_CONFIGURATION`: Dievaluasi saat kelas konfigurasi diuraikan. Jika kondisi gagal pada fase ini, seluruh anotasi `@Configuration` beserta seluruh deklarasi method `@Bean` di dalamnya diabaikan sepenuhnya.
2.  `REGISTER_BEAN`: Dievaluasi saat satu metode `@Bean` spesifik hendak didaftarkan sebagai `BeanDefinition`. Berguna saat kelas induknya lolos seleksi, namun implementasi method spesifik dibatasi kondisi kontekstual (misal: `@ConditionalOnMissingBean`).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Transisi Arsitektur Jakarta EE 10 (Spring Framework 6 Baseline)

Spring Boot 3 dibangun di atas Spring Framework 6 yang mensyaratkan Java 17 sebagai baseline minimum dan beralih sepenuhnya dari namespace `javax.*` ke `jakarta.*`. 
*   **Penyebab:** Perubahan hak kekayaan intelektual (IP) dari Java EE di Oracle ke Eclipse Foundation (Jakarta EE).
*   **Implikasi Teknis:** Seluruh komponen server seperti Servlet 6.0 (`jakarta.servlet.*`), JPA 3.1 (`jakarta.persistence.*`), dan Bean Validation 3.0 (`jakarta.validation.*`) tidak lagi kompatibel di tingkat bytecode dengan library versi lawas berbasis `javax.*`. Framework harus melakukan refactoring internal pada engine pipeline filter, ORM session boundary, dan interceptor stack.

### 2. AOT (Ahead-Of-Time) Processing & GraalVM Native Image

Dalam JVM mode konvensional:
*   Classpath dipindai saat *runtime startup*.
*   Bytecode dianalisis menggunakan refleksi.
*   Proxy dibuat secara dinamis menggunakan CGLIB runtime code generation.

Dalam AOT mode Spring Boot 3:
1.  **Closed-World Assumption:** Asumsi bahwa seluruh kelas, dependensi, dan resource aplikasi sudah bersifat pasti dan tertutup saat proses kompilasi (*build-time*). Kode atau kelas baru tidak dapat ditambahkan di runtime.
2.  **AOT Compilation Engine:** Engine Spring AOT mengevaluasi auto-configuration pada saat *compile time* dan menghasilkan *source code generator* Java baru. Kode baru ini meregistrasikan `BeanDefinition` dan instansiasi bean melalui kode imperatif murni tanpa refleksi berat.
3.  **Reachability Metadata Generation:** Kompilator GraalVM native image membutuhkan deklarasi eksplisit untuk kelas, field, dan method yang diakses via refleksi. Spring Boot 3 secara otomatis memproduksi file metadata reachability (`reflect-config.json`, `resource-config.json`) melalui inspect framework contracts.

### 3. Virtual Threads (Project Loom) Integration

Mulai Spring Boot 3.2+, integrasi penuh dengan Virtual Threads (Java 21) diimplementasikan melalui abstraksi `AsyncTaskExecutor`. 

```
[Platform Threads - 1:1 OS Thread]
Thread Request 1 ===> [OS Thread A] ===> Blocking I/O (Database Query: 50ms Idle)
Thread Request 2 ===> [OS Thread B] ===> Memory Consumption: ~1MB Stack/Thread

[Virtual Threads - M:N Carrier Thread (Spring Boot 3.2+)]
Virtual Thread 1 \
Virtual Thread 2  ===> [Carrier Thread Pool] ===> Virtual Thread Unmounted during I/O
Virtual Thread 3 /
```

Saat properti `spring.threads.virtual.enabled=true` diaktifkan:
*   Tomcat web server dialihkan untuk menggunakan `VirtualThreadPerTaskExecutor`.
*   Tiap request HTTP inbound ditangani oleh virtual thread mandiri yang ringan (*lightweight*), menghindarkan bahaya thread starvation saat melakukan pemanggilan I/O sinkron/blocking (JDBC, REST client, dll.).

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah perancangan custom auto-configuration modular tingkat lanjut sesuai standar Spring Boot 3. Modul ini menyediakan service monitoring latensi terenkripsi jika terdapat dependency tertentu di classpath dan pengguna belum mendefinisikan bean alternatif.

### 1. Service Definition & Properties Binding

```java
package com.enterprise.infra.monitoring;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

@ConfigurationProperties(prefix = "enterprise.monitoring")
public record LatencyMonitorProperties(
    boolean enabled,
    Duration alertThreshold,
    String environmentLabel
) {
    // Memberikan nilai default secara defensif menggunakan canonical constructor
    public LatencyMonitorProperties {
        if (alertThreshold == null) {
            alertThreshold = Duration.ofMillis(500);
        }
        if (environmentLabel == null || environmentLabel.isBlank()) {
            environmentLabel = "production";
        }
    }
}
```

```java
package com.enterprise.infra.monitoring;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class HighPrecisionLatencyMonitor {
    private static final Logger log = LoggerFactory.getLogger(HighPrecisionLatencyMonitor.class);
    
    private final LatencyMonitorProperties properties;

    public HighPrecisionLatencyMonitor(LatencyMonitorProperties properties) {
        this.properties = properties;
    }

    public void recordTransaction(String transactionId, long durationNs) {
        long durationMs = durationNs / 1_000_000;
        if (durationMs > properties.alertThreshold().toMillis()) {
            log.warn("[ALERT] [{}] Tx: {} breached threshold: {}ms > {}ms",
                    properties.environmentLabel(), transactionId, durationMs, properties.alertThreshold().toMillis());
        } else {
            log.debug("[OK] [{}] Tx: {} completed in {}ms", properties.environmentLabel(), transactionId, durationMs);
        }
    }
}
```

### 2. Auto-Configuration Class

```java
package com.enterprise.infra.monitoring.autoconfigure;

import com.enterprise.infra.monitoring.HighPrecisionLatencyMonitor;
import com.enterprise.infra.monitoring.LatencyMonitorProperties;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;

@AutoConfiguration
@ConditionalOnClass(HighPrecisionLatencyMonitor.class)
@EnableConfigurationProperties(LatencyMonitorProperties.class)
@ConditionalOnProperty(
    prefix = "enterprise.monitoring", 
    name = "enabled", 
    havingValue = "true", 
    matchIfMissing = false
)
public class LatencyMonitorAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean
    public HighPrecisionLatencyMonitor latencyMonitor(LatencyMonitorProperties properties) {
        return new HighPrecisionLatencyMonitor(properties);
    }
}
```

### 3. Service Provider Registration (Standar Spring Boot 3)

Letakkan konfigurasi berikut pada direktori:
`src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`

```text
com.enterprise.infra.monitoring.autoconfigure.LatencyMonitorAutoConfiguration
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis komponen fundamental di atas:

### Kelas `LatencyMonitorProperties.java`
*   `@ConfigurationProperties(prefix = "enterprise.monitoring")`: Mendaftarkan objek ini ke `ConfigurationPropertiesBindingPostProcessor`. Framework membaca namespace konfigurasi YAML/Properties dan memetakannya secara aman (type-safe).
*   `public record LatencyMonitorProperties(...)`: Penggunaan Java Record menjamin immutabilitas konfigurasi sistem. State konfigurasi runtime tidak dapat dirusak melalui mutasi objek pasca-instansiasi.
*   `public LatencyMonitorProperties { ... }`: Compact constructor record digunakan untuk validasi invarian dan penerapan fallback default logic sebelum nilai dipetakan ke field internal.

### Kelas `LatencyMonitorAutoConfiguration.java`
*   `@AutoConfiguration`: Anotasi khusus Spring Boot 3 yang merupakan meta-annotation dari `@Configuration(proxyBeanMethods = false)`. Menghentikan pembuatan proxy CGLIB pada kelas konfigurasi ini untuk akselerasi startup time dan penghematan memori, karena tidak ada dependensi intra-method call bean di dalamnya.
*   `@ConditionalOnClass(HighPrecisionLatencyMonitor.class)`: Dievaluasi oleh `OnClassCondition`. Memverifikasi apakah byte stream dari kelas target ada di `ClassLoader`. Jika library di-*exclude*, parsing konfigurasi diputus sedini mungkin.
*   `@EnableConfigurationProperties(LatencyMonitorProperties.class)`: Mendaftarkan `LatencyMonitorProperties` sebagai bean internal di context agar dapat disuntikkan (*injected*) ke dalam method deklarasi `@Bean`.
*   `@ConditionalOnProperty(...)`: Engine memverifikasi ketersediaan flag `enterprise.monitoring.enabled=true`. Atribut `matchIfMissing = false` mewajibkan deklarasi properti secara eksplisit untuk mencegah inisialisasi yang tidak disengaja.
*   `@Bean`: Menginstruksikan container bahwa method ini menghasilkan instance bean terkelola.
*   `@ConditionalOnMissingBean`: Dievaluasi pada fase `REGISTER_BEAN`. Jika software engineer pengguna starter ini telah mendefinisikan bean `HighPrecisionLatencyMonitor` mereka sendiri di `@Configuration` aplikasi utama, method auto-configuration ini di-bypass (*overridden* secara graceful).

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Masalah: Thundering Herd & State Synchronization pada Multi-Tenant Data Platform

Sebuah platform financial gateway melayani 500+ entitas perbankan (tenants) secara dinamis. Platform membutuhkan mekanisme routing database otomatis:
1.  Koneksi database setiap tenant bersifat heterogen dan dinamis (terbaca dari central secret vault).
2.  Setiap tenant membutuhkan failover pooling otomatis (HikariCP) yang diisolasi di runtime.
3.  Aplikasi tidak boleh melakukan restart saat tenant baru didaftarkan.
4.  Jika tenant credential tidak valid, context utama tidak boleh crash.

### Solusi Arsitektur
Membangun **Dynamic Multi-Tenant Routing Engine** berbasis auto-configuration Spring Boot 3 dengan memanfaatkan:
*   `AbstractRoutingDataSource` untuk switching context JDBC dinamis.
*   Custom `BeanFactoryPostProcessor` & scoped proxy.
*   Observation API untuk melacak tenant database execution latency.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut implementasi lengkap modular multi-tenant routing engine:

### 1. Tenant Context Thread Boundary

```java
package com.enterprise.multitenant.context;

public final class TenantContextHolder {
    private static final ThreadLocal<String> CURRENT_TENANT = new ThreadLocal<>();

    private TenantContextHolder() {}

    public static void setTenantId(String tenantId) {
        if (tenantId == null || tenantId.isBlank()) {
            throw new IllegalArgumentException("Tenant ID cannot be null or empty");
        }
        CURRENT_TENANT.set(tenantId);
    }

    public static String getTenantId() {
        return CURRENT_TENANT.get();
    }

    public static void clear() {
        CURRENT_TENANT.remove();
    }
}
```

### 2. Dynamic Routing Data Source

```java
package com.enterprise.multitenant.datasource;

import com.enterprise.multitenant.context.TenantContextHolder;
import org.springframework.jdbc.datasource.lookup.AbstractRoutingDataSource;

import javax.sql.DataSource;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class DynamicTenantRoutingDataSource extends AbstractRoutingDataSource {

    private final Map<Object, Object> targetDataSources = new ConcurrentHashMap<>();
    private final DataSource defaultDataSource;

    public DynamicTenantRoutingDataSource(DataSource defaultDataSource) {
        this.defaultDataSource = defaultDataSource;
        super.setDefaultTargetDataSource(defaultDataSource);
        super.setTargetDataSources(this.targetDataSources);
    }

    @Override
    protected Object determineCurrentLookupKey() {
        return TenantContextHolder.getTenantId();
    }

    public synchronized void addTenantDataSource(String tenantId, DataSource dataSource) {
        targetDataSources.put(tenantId, dataSource);
        super.setTargetDataSources(targetDataSources);
        super.afterPropertiesSet(); // Refresh internal lookup map
    }

    public boolean containsTenant(String tenantId) {
        return targetDataSources.containsKey(tenantId);
    }
}
```

### 3. Tenant DataSource Registry & Auto-Configuration

```java
package com.enterprise.multitenant.autoconfigure;

import com.enterprise.multitenant.datasource.DynamicTenantRoutingDataSource;
import com.zaxxer.hikari.HikariDataSource;
import io.micrometer.observation.ObservationRegistry;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;

import javax.sql.DataSource;
import java.util.HashMap;
import java.util.Map;

@ConfigurationProperties(prefix = "enterprise.multitenant")
record MultiTenantProperties(
    String defaultTenantId,
    Map<String, String> urls,
    String commonUsername,
    String commonPassword
) {
    public MultiTenantProperties {
        if (urls == null) urls = new HashMap<>();
        if (defaultTenantId == null) defaultTenantId = "master";
    }
}

@AutoConfiguration(before = DataSourceAutoConfiguration.class)
@ConditionalOnClass({DynamicTenantRoutingDataSource.class, HikariDataSource.class})
@EnableConfigurationProperties(MultiTenantProperties.class)
public class DynamicMultiTenantAutoConfiguration {

    @Bean
    @Primary
    @ConditionalOnMissingBean
    public DataSource dynamicRoutingDataSource(
            MultiTenantProperties properties,
            ObservationRegistry observationRegistry) {

        // Instansiasi DataSource Default (Master Data Source)
        HikariDataSource defaultSource = new HikariDataSource();
        defaultSource.setPoolName("TenantPool-Master");
        defaultSource.setJdbcUrl(properties.urls().getOrDefault("master", "jdbc:h2:mem:masterdb"));
        defaultSource.setUsername(properties.commonUsername());
        defaultSource.setPassword(properties.commonPassword());

        DynamicTenantRoutingDataSource routingDataSource = new DynamicTenantRoutingDataSource(defaultSource);

        // Pre-populate DataSources yang didefinisikan di environment
        properties.urls().forEach((tenantId, url) -> {
            if (!"master".equalsIgnoreCase(tenantId)) {
                HikariDataSource ds = new HikariDataSource();
                ds.setPoolName("TenantPool-" + tenantId);
                ds.setJdbcUrl(url);
                ds.setUsername(properties.commonUsername());
                ds.setPassword(properties.commonPassword());
                routingDataSource.addTenantDataSource(tenantId, ds);
            }
        });

        return routingDataSource;
    }
}
```

### 4. Servlet Filter for Automated Thread Boundary Maintenance

```java
package com.enterprise.multitenant.web;

import com.enterprise.multitenant.context.TenantContextHolder;
import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import java.io.IOException;

public class TenantBoundaryFilter implements Filter {

    public static final String TENANT_HEADER = "X-Tenant-Id";

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        
        HttpServletRequest httpRequest = (HttpServletRequest) request;
        HttpServletResponse httpResponse = (HttpServletResponse) response;

        String tenantId = httpRequest.getHeader(TENANT_HEADER);

        if (tenantId == null || tenantId.isBlank()) {
            httpResponse.sendError(HttpServletResponse.SC_BAD_REQUEST, "Missing required X-Tenant-Id header");
            return;
        }

        try {
            TenantContextHolder.setTenantId(tenantId.trim());
            chain.doFilter(request, response);
        } finally {
            // Mandatori: Mengeliminasi risiko thread contamination pada thread pooling environment
            TenantContextHolder.clear();
        }
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Matrix Analisis Arsitektur

| Karakteristik | Traditional JVM Mode (Spring Boot 3) | GraalVM Native Image (AOT) | Reactive WebFlux Engine |
| :--- | :--- | :--- | :--- |
| **Startup Time** | Sedang - Lambat (1.5s – 15s) | Ekstrem Cepat (10ms – 100ms) | Sedang (1.0s – 5s) |
| **Memory Footprint (RSS)** | Tinggi (250MB – 1GB+) | Sangat Rendah (25MB – 80MB) | Rendah – Sedang (80MB – 200MB) |
| **Peak Throughput** | Maksimal (JIT C2 Optimization) | Sedang – Tinggi (Tanpa profiling) | Maksimal untuk I/O Bound |
| **Dynamic Capabilities** | Penuh (Reflection, CGLIB Proxies) | Sangat Terbatas (Closed-World) | Penuh (namun strictly non-blocking) |
| **Build Time** | Cepat (Detik) | Sangat Lambat (Menit, resource-heavy) | Cepat (Detik) |
| **Debugging & Profiling** | Sangat Mudah (JDWP, JFR, VisualVM) | Kompleks (GDB, Native Tracers) | Sulit (Reactive Stack Traces) |

### Perbandingan: Auto-Configuration vs Explicit Bean Declarations

*   **Auto-Configuration:** 
    *   *Kelebihan:* Mengurangi *boilerplate code*, standarisasi cross-cutting concerns di level enterprise, self-healing configuration (menyesuaikan isi classpath).
    *   *Kekurangan:* Analisis debugging lebih kompleks jika terjadi konflik kondisi dependensi, memerlukan pemahaman lifecycle container yang mendalam.
*   **Explicit Configuration (`@Configuration` manual):**
    *   *Kelebihan:* Deterministik absolut, alur deklarasi bean terbaca secara eksplisit tanpa asumsi, waktu startup marjinal lebih cepat.
    *   *Kekurangan:* Duplikasi konfigurasi masif di setiap repositori microservice, resisten terhadap adaptasi standarisasi platform tim infra.

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Deadlock ClassLoader pada Conditional Ordering
Ketika membuat custom auto-configuration yang saling bergantung, kegagalan menentukan urutan sequencing menyebabkan bean fallback dievaluasi sebelum bean primer siap.
*   *Solusi:* Wajib menggunakan anotasi `@AutoConfigureOrder(Ordered.HIGHEST_PRECEDENCE)`, `@AutoConfigureBefore(AnotherAutoConfig.class)`, atau `@AutoConfigureAfter(BaseAutoConfig.class)`.

### 2. Virtual Thread Pinning (Java 21 + Spring Boot 3)
Virtual Thread tidak boleh di-*block* di dalam blok `synchronized` atau pemanggilan JNI (Java Native Interface). Blok `synchronized` akan me-mount virtual thread ke platform carrier thread (disebut **Pinning**).
*   *Gejala:* Utilisasi resource OS thread melonjak ke 100%, throughput anjlok drastis menyamai platform thread biasa.
*   *Solusi:* Migrasikan blok `synchronized` kritis ke `java.util.concurrent.locks.ReentrantLock`.

### 3. Circular Dependency Strict Blocking
Sejak Spring Boot 2.6 dan berlanjut secara ketat di Spring Boot 3, **circular references dinonaktifkan secara default** (`spring.main.allow-circular-references=false`). Context refresh akan melemparkan `BeanCurrentlyInCreationException`.
*   *Bahaya Mengaktifkan Flag:* Mengaktifkan flag fallback (`allow-circular-references=true`) menutupi kecacatan perancangan arsitektur domain dan berisiko menghasilkan uninitialized proxy states.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan Fatal 1: Menaruh `@ComponentScan` Bersebelahan dengan `@SpringBootApplication`

```java
// KESALAHAN FATAL
@SpringBootApplication
@ComponentScan(basePackages = "com.enterprise.service") // MENIMPA ROOT CONFIGURATION!
public class Application { ... }
```
*   *Mengapa Salah:* `@SpringBootApplication` sudah mencakup `@ComponentScan` pada package kelas tersebut dan sub-packagenya. Menambahkan `@ComponentScan` eksplisit secara parsial akan membatasi scan, mengabaikan package internal auto-configuration, dan menyebabkan bean-bean fundamental hilang (*silently missing beans*).
*   *Cara Menghindari:* Jika membutuhkan registrasi modular, gunakan `@Import` atau strukturkan package mengikuti konvensi root namespace hirarkis.

### Kesalahan Fatal 2: Overhead Pembuatan Proxy pada Method `@Bean`

```java
// KESALAHAN UMUM
@Configuration(proxyBeanMethods = true) // Nilai DEFAULT pada @Configuration standar
public class DatabaseConfig {

    @Bean
    public DataSource dataSource() { return new HikariDataSource(); }

    @Bean
    public JdbcTemplate jdbcTemplate() { 
        // Memanggil method dataSource() di dalam kelas configuration
        return new JdbcTemplate(dataSource()); 
    }
}
```
*   *Mengapa Salah:* `proxyBeanMethods = true` memaksa Spring menggunakan CGLIB subclass proxying untuk memotong method invocation agar menghasilkan single bean. Ini menambah alokasi memori dan memperlambat startup time hingga 5-10%.
*   *Cara Menghindari:* Selalu gunakan parameter injection dan nonaktifkan CGLIB jika tidak diperlukan intra-bean method calls:

```java
// CARA BENAR & EFISIEN
@Configuration(proxyBeanMethods = false)
public class DatabaseConfig {

    @Bean
    public DataSource dataSource() { return new HikariDataSource(); }

    @Bean
    public JdbcTemplate jdbcTemplate(DataSource dataSource) { // Inject lewat parameter
        return new JdbcTemplate(dataSource); 
    }
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Immutability pada Injeksi Dependensi:** Hapus seluruh field injection (`@Autowired private MyService myService;`). Wajib gunakan **Constructor Injection** mutlak bersama `final` fields. Constructor injection mempermudah unit testing independen, menjamin objek immutable, dan mencegah partial initialization.
2.  **Modular Test Slices:** Hindari anotasi rakus `@SpringBootTest` untuk setiap testing integration. Gunakan *Test Slices*:
    *   `@WebMvcTest` untuk controller layer.
    *   `@DataJpaTest` untuk persistence layer test.
    *   `@JsonTest` untuk payload serialization/deserialization.
3.  **Defensive Configuration Properties:** Validasi configuration properties menggunakan validasi declarative `jakarta.validation` (`@Validated`, `@NotNull`, `@Min`, `@Max`) langsung pada Java Record configuration holder.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Optimasi Startup Melalui CDS (Class Data Sharing)

Di Spring Boot 3 + Java 17/21, optimalkan startup microservice menggunakan Application Class Data Sharing (AppCDS).

```bash
# Langkah 1: Ekstraksi CDS Archive saat build/packaging
java -XX:ArchiveClassesAtExit=application.jsa -Dspring.context.exit=onRefresh -jar app.jar

# Langkah 2: Menjalankan container/binary dengan memory-mapped CDS
java -XX:SharedArchiveFile=application.jsa -jar app.jar
```
*   *Hasil:* Waktu startup terpangkas 30% - 50%, utilisasi resident memory berkurang karena metadata class di-share oleh OS kernel.

### 2. Aktivasi Mode Virtual Threads (Java 21 Engine)

Cukup tambahkan deklarasi berikut pada `application.yml`:

```yaml
spring:
  threads:
    virtual:
      enabled: true
```
Konfigurasi ini secara otomatis mengganti thread executor Tomcat dan framework `@Async` task pooling untuk memanfaatkan lightweight virtual threads tanpa perlu menulis satu baris kode concurrency manual.

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Mitigasi Exposure Actuator Endpoints

Endpoint Actuator yang bocor ke jaringan publik menyajikan vektor serangan ekstrim (Remote Code Execution melalui `/env` atau memory heap dumping melalui `/heapdump`).

```yaml
# application-prod.yml
management:
  endpoints:
    enabled-by-default: false # Default deny all
    web:
      exposure:
        include: "health,prometheus" # Hanya buka yang esensial
      base-path: /internal/actuator # Pindahkan base path sistem
  endpoint:
    health:
      enabled: true
      show-details: never # JANGAN PERNAH buka detail trace DB di publik
```

### 2. Secret Masking Framework Configuration

Pastikan sanitizer environment diaktifkan untuk masking credentials otomatis pada crash traces dan logs:

```yaml
management:
  endpoint:
    env:
      keys-to-sanitize:
        - ".*password.*"
        - ".*secret.*"
        - ".*key.*"
        - ".*token.*"
        - ".*credentials.*"
```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Arsitektur Micrometer Observation API (Spring Boot 3 Baseline)

Spring Boot 3 menyatukan tracing (sebelumnya Spring Cloud Sleuth) dan metrik melalui **Micrometer Observation API**. Satu instrumentasi menghasilkan logs bertag context, metrics, dan distributed trace spans sekaligus.

```java
package com.enterprise.infra.observability;

import io.micrometer.observation.Observation;
import io.micrometer.observation.ObservationRegistry;
import org.springframework.stereotype.Service;

@Service
public class OrderProcessingService {

    private final ObservationRegistry observationRegistry;

    public OrderProcessingService(ObservationRegistry observationRegistry) {
        this.observationRegistry = observationRegistry;
    }

    public void processOrder(String orderId) {
        // Unifikasi: Tracing Span + Prometheus Counter/Timer terotomatisasi
        Observation.createNotStarted("order.processing", observationRegistry)
            .lowCardinalityKeyValue("order.type", "retail")
            .highCardinalityKeyValue("order.id", orderId)
            .observe(() -> {
                // Logika bisnis transaksi
                executeBusinessLogic(orderId);
            });
    }

    private void executeBusinessLogic(String orderId) {
        // Simulasi kalkulasi
    }
}
```

### 2. Auto-Configuration Diagnostic Flags

Untuk menganalisis mengapa suatu auto-configuration aktif atau tidak aktif, jalankan aplikasi menggunakan execution flag:

```bash
java -jar app.jar --debug
```
Atau analisis programmatically lewat laporan startup:

```
============================
CONDITIONS EVALUATION REPORT
============================

Positive matches:
-----------------
   DynamicMultiTenantAutoConfiguration matched:
      - @ConditionalOnClass found required classes (DynamicTenantRoutingDataSource, HikariDataSource)

Negative matches:
-----------------
   MongoDataAutoConfiguration:
      Did not match:
         - @ConditionalOnClass did not find required class 'com.mongodb.client.MongoClient'
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### Anotasi Esensial Arsitektur Spring Boot 3

| Anotasi | Scope / Target | Fungsi Kunci |
| :--- | :--- | :--- |
| `@AutoConfiguration` | Type (Class) | Mendeklarasikan entry point konfigurasi otomatis (menggantikan `@Configuration` pada modular starters). |
| `@ConditionalOnClass` | Type / Method | Bean hanya dibuat jika binary file `.class` ditemukan di runtime ClassPath. |
| `@ConditionalOnMissingBean` | Method | Fallback pattern: Bean hanya dibuat jika context belum memiliki implementasi serupa. |
| `@ConditionalOnProperty` | Type / Method | Evaluasi nilai boolean/string pada `Environment` properties sebelum registrasi. |
| `@EnableConfigurationProperties` | Type (Class) | Mendaftarkan Type-Safe Properties Mapping Holder (Record/POJO) ke context. |

### Lokasi Metadata Konfigurasi

*   **Discovery File (Spring Boot 3):**
    `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`
*   **Configuration Metadata Indexing:**
    `META-INF/spring-configuration-metadata.json`
*   **Native Reachability Metadata (AOT):**
    `META-INF/native-image/<group-id>/<artifact-id>/reflect-config.json`

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Basic

1. **Di manakah lokasi file deklarasi konfigurasi otomatis (*auto-configuration imports*) yang valid dan direkomendasikan pada Spring Boot 3?**
   * A. `META-INF/spring.factories`
   * B. `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`
   * C. `src/main/resources/application.factories`
   * D. `META-INF/services/org.springframework.boot.AutoConfiguration`
   * *Jawaban:* **B**. Spring Boot 3 mendepresiasi pendaftaran auto-configuration melalui `spring.factories` dan memindahkannya ke file `.imports` modular khusus.

2. **Perubahan fundamental apa yang terjadi pada layer enterprise specification di Spring Boot 3 akibat transisi Spring Framework 6?**
   * A. Migrasi total namespace dari `javax.*` ke `jakarta.*`.
   * B. Penghentian dukungan terhadap embedded Tomcat.
   * C. Penghapusan anotasi `@Transactional`.
   * D. Larangan penggunaan relational database driver.
   * *Jawaban:* **A**. Spring Framework 6 dan Spring Boot 3 beralih ke Jakarta EE 10 baseline, mengubah semua package core `javax.*` (Servlet, JPA, Validation) menjadi `jakarta.*`.

3. **Apa kegunaan utama parameter `proxyBeanMethods = false` pada anotasi `@Configuration` atau `@AutoConfiguration`?**
   * A. Mengizinkan pemanggilan bean method berulang kali untuk menghasilkan singleton.
   * B. Menonaktifkan pembuatan CGLIB dynamic proxy subclass untuk akselerasi performa startup dan efisiensi memori.
   * C. Mengubah bean menjadi ber-scope prototype secara paksa.
   * D. Menginstruksikan container untuk mengabaikan anotasi `@Bean`.
   * *Jawaban:* **B**. Dengan menonaktifkan method proxying, JVM menghindari evaluasi interceptor CGLIB saat parsing class configuration.

4. **Kapan kondisi `@ConditionalOnMissingBean` dievaluasi oleh Spring Boot?**
   * A. Saat compile-time javac berjalan.
   * B. Pada fase `PARSE_CONFIGURATION` saat pembacaan metadata class awal.
   * C. Pada fase `REGISTER_BEAN` setelah bean kustom milik pengguna didaftarkan.
   * D. Saat application context dihancurkan (*destroyed*).
   * *Jawaban:* **C**. Agar pengguna dapat menimpa (*override*) bean bawaan framework, evaluasi kondisi ini dilakukan di akhir registrasi blueprint bean.

5. **Apa sifat utama thread yang digunakan jika flag `spring.threads.virtual.enabled=true` diaktifkan di Spring Boot 3.2+?**
   * A. Thread langsung dipetakan 1:1 ke kernel OS thread.
   * B. Lightweight user-mode threads yang dikelola oleh JVM runtime (Project Loom).
   * C. Thread dieksekusi secara asinkronus menggunakan arsitektur non-blocking Reactive Event Loop.
   * D. Mengharuskan penulisan reactive stream menggunakan project Reactor (`Mono`/`Flux`).
   * *Jawaban:* **B**. Virtual threads adalah thread ringan yang dikelola oleh JVM runtime di mana I/O blocking call akan secara otomatis melepas (*unmount*) thread dari platform OS carrier thread.

---

### Soal Intermediate

6. **Apa yang terjadi secara internal jika terdapat dua auto-configuration kelas X dan Y, di mana X memiliki anotasi `@AutoConfigureAfter(Y.class)`?**
   * A. Kelas X dikompilasi setelah kelas Y oleh compiler `javac`.
   * B. Urutan pembacaan dan eksekusi `BeanDefinition` milik X ditunda hingga `BeanDefinition` milik Y selesai diproses oleh `ConfigurationClassPostProcessor`.
   * C. Seluruh bean di dalam X akan otomatis memiliki scope Prototype.
   * D. Spring akan melemparkan exception jika Y tidak didefinisikan sebagai bean eksplisit oleh user.
   * *Jawaban:* **B**. Anotasi tersebut menginstruksikan `ConfigurationClassPostProcessor` untuk menyortir urutan evaluasi kelas konfigurasi sebelum parsing method bean dilakukan.

7. **Mengapa penggunaan blok `synchronized` konvensional berbahaya di aplikasi Spring Boot 3 berbasis Virtual Threads?**
   * A. Menyebabkan compiler GraalVM Native Image gagal melakukan kompilasi AOT.
   * B. Menyebabkan fenomena Virtual Thread Pinning yang mengunci carrier OS thread, meniadakan efisiensi concurrency.
   * C. Spring Boot context akan langsung crash dengan `IllegalMonitorStateException`.
   * D. Menyebabkan deadlock otomatis pada `HikariCP` connection pool.
   * *Jawaban:* **B**. Operasi blok monitor `synchronized` menahan thread OS fisik (*carrier thread*), sehingga thread virtual tidak dapat digeser (*unmounted*) saat I/O blocking berlangsung.

8. **Manakah interface yang bertanggung jawab memodifikasi objek bean SETELAH instansiasi dan pemetaan properti selesai, tetapi SEBELUM method inisialisasi dijalankan?**
   * A. `BeanFactoryPostProcessor`
   * B. `ApplicationContextInitializer`
   * C. Method `postProcessBeforeInitialization` pada `BeanPostProcessor`
   * D. Method `postProcessAfterInitialization` pada `BeanPostProcessor`
   * *Jawaban:* **C**. `postProcessBeforeInitialization` dieksekusi tepat sebelum lifecycle callback seperti `@PostConstruct` atau `InitializingBean.afterPropertiesSet()` berjalan.

9. **Mengapa aplikasi Spring Boot 3 yang dikompilasi menggunakan GraalVM Native Image memerlukan "Reachability Metadata"?**
   * A. Karena binary native GraalVM tidak memiliki JIT compiler dinamis dan mengadopsi Closed-World Assumption, sehingga seluruh refleksi harus didaftarkan saat build time.
   * B. Untuk menghubungkan aplikasi dengan remote database secara dinamis.
   * C. Agar Spring Security dapat memverifikasi JWT token tanpa validasi public key.
   * D. Metadata tersebut dibutuhkan oleh sistem operasi Linux untuk mengalokasikan virtual memory swap.
   * *Jawaban:* **A**. Native image mengharuskan seluruh kelas, method, atau resource yang diakses secara reflektif teridentifikasi secara absolut sebelum binary file ditutup (*sealed*).

10. **Apa perbedaan fungsional antara `ObservationRegistry` di Spring Boot 3 dengan implementasi `Tracer` manual di Spring Cloud Sleuth terdahulu?**
    * A. `ObservationRegistry` hanya mendukung logging format JSON, tidak mendukung metrics.
    * B. `ObservationRegistry` menyatukan penangkapan data single lifecycle event menjadi metrik dimensional (Micrometer) dan trace distribution spans (OpenTelemetry) secara atomik.
    * C. `ObservationRegistry` mengharuskan penggunaan reactive programming.
    * D. `ObservationRegistry` tidak dapat dikonfigurasi melalui properties file.
    * *Jawaban:* **B**. Observation API bertindak sebagai single source of truth instrumentasi; developers cukup membuat satu `Observation`, dan framework mendistribusikan metadata tersebut ke tracing spans, log correlation IDs, dan metrics counters/timers secara paralel.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Misi Arsitektur: Membangun "Enterprise Dynamic Rate-Limiter Auto-Configure Starter"

Rancang dan bangun modul library Spring Boot 3 independen dengan spesifikasi rekayasa enterprise berikut:

#### Kebutuhan Spesifikasi:
1.  **Starter Separation:**
    *   Buat modul terpisah: `rate-limiter-spring-boot-autoconfigure` (berisi logika konfigurasi dan engine) dan `rate-limiter-spring-boot-starter` (berisi POM agregasi ketergantungan).
2.  **Kondisi Auto-Configuration:**
    *   Starter otomatis aktif jika anotasi kustom `@EnableRateLimiting` disematkan pada konfigurasi aplikasi klien ATAU properti `enterprise.ratelimit.enabled=true` disetel.
    *   Secara default, sediakan in-memory Token Bucket algorithm implementation berbasis `AtomicInteger` & Scheduled Executor.
    *   Jika dependency `org.springframework.boot:spring-boot-starter-data-redis` ditemukan di ClassPath dan Redis connection factory tersedia, switch implementasi secara otomatis menggunakan **Redis Lua Scripting distributed rate-limiter** via conditional checks.
3.  **Cross-Cutting Execution:**
    *   Buat custom annotation `@RateLimit(requestsPerSecond = X)`.
    *   Gunakan `BeanPostProcessor` atau Spring AOP Aspect (`@Around`) untuk mengintersepsi target method controller dan mengeksekusi algoritma pembatasan traffic.
    *   Jika batas rate limit terlampaui, lemparkan exception kustom `RateLimitExceededException` yang secara otomatis dipetakan ke HTTP Status 429 oleh custom `HandlerExceptionResolver`.
4.  **Observability & AOT Readiness:**
    *   Instrumentasikan event penolakan request rate-limit ke dalam `ObservationRegistry` metrik counter.
    *   Tulis file hints `RuntimeHintsRegistrar` untuk mendaftarkan method dan anotasi kustom tersebut agar lolos uji kompilasi Ahead-Of-Time (GraalVM Native Image).

#### Kriteria Pengujian Ekstrem:
*   Uji starter Anda pada microservice dummy yang menjalankan mode **Java 21 Virtual Threads**.
*   Simulasikan *thundering herd* 10.000 concurrent request menggunakan JMeter atau k6.
*   Buktikan bahwa tidak terjadi class pinning pada virtual thread selama proses eksekusi rate limiting berlangsung.