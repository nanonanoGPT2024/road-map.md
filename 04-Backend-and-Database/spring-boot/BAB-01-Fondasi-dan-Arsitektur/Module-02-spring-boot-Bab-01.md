# Kurikulum Rekayasa Perangkat Lunak Enterprise: Spring Boot
## BAB 01: Fondasi dan Arsitektur
### Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Membedah Siklus Hidup Bootstrap Spring Boot 3.x**: Menguraikan fase eksekusi `SpringApplication.run()` dari inisialisasi *Environment*, *ApplicationContext creation*, pemanggilan *BeanFactoryPostProcessor*, hingga fase *BeanPostProcessor* dan *Embedded Web Server binding*.
2. **Menguasai Mekanisme Auto-Configuration Engine**: Mengembangkan custom auto-configuration dan starter kelas enterprise menggunakan SPI (`AutoConfiguration.imports`), kondisi bersyarat (`@ConditionalOn*`), dan mengoptimalkan urutan pemuatan auto-configuration (`@AutoConfigureOrder`, `@AutoConfigureBefore`/`After`).
3. **Mendiagnosis dan Mengoptimalkan Context Initialization**: Mengurangi startup latency aplikasi melalui integrasi Spring AOT (Ahead-of-Time Engine), GraalVM Native Image considerations, serta adopsi Virtual Threads (Project Loom) pada embedded runtime container.
4. **Mencegah Masalah Kritis Arsitektur**: Mengeliminasi bottleneck umum produksi seperti *classloader leaks*, *circular dependencies*, context pollution pada multi-module builds, dan *thread pinning* pada Java Virtual Threads.

---

### 2. Prerequisite
Sebelum mendalami modul ini, peserta wajib menguasai:
*   **Java Core (Lanjutan)**: Java 17/21 (Record, Sealed Classes, Reflection API, Dynamic Proxies, ServiceLoader mechanism, Memory Model, Garbage Collection semantics).
*   **Fondasi Spring Framework**: Inversion of Control (IoC), Dependency Injection (DI), Spring Bean Scopes, dan ApplicationContext lifecycles.
*   **Build Automation**: Maven atau Gradle (Dependency resolution, shade/fat-jar packaging, plugin management).
*   **Module 01**: Penguasaan konsep arsitektur dasar Spring Boot, struktur file proyek standar, dan dasar-dasar anotasi Spring Boot.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Anatomi Bootstrap Engine: Siklus Hidup `SpringApplication.run()`
Saat metode `SpringApplication.run(Application.class, args)` dipanggil, proses runtime tidak langsung menginstansiasi bean. Terjadi serangkaian tahapan deterministik pada JVM:

```
[Main Thread]
      │
      ▼
1. Instansiasi SpringApplication ──► Deteksi WebApplicationType (SERVLET, REACTIVE, NONE)
      │                          ──► Muat BootstrapRegistryInitializer via SpringFactoriesLoader
      │                          ──► Muat ApplicationContextInitializer & ApplicationListener
      ▼
2. Eksekusi run()
      │
      ├──► Buat & Jalankan SpringApplicationRunListeners (event: starting)
      │
      ├──► Setup ConfigurableEnvironment (System Props, Env Vars, Profiles, Properties)
      │    └──► Event: environmentPrepared (EnvironmentPostProcessor dipanggil)
      │
      ├──► Print Banner (Jika aktif)
      │
      ├──► Instansiasi ConfigurableApplicationContext
      │    (Contoh: AnnotationConfigServletWebServerApplicationContext)
      │
      ├──► Context Preparation:
      │    ├──► Pasang Environment ke Context
      │    ├──► Jalankan ApplicationContextInitializer
      │    └──► Daftarkan BeanDefinition dasar (args, primary sources)
      │
      ├──► Context Refresh (AbstractApplicationContext.refresh()):
      │    ├──► invokeBeanFactoryPostProcessors() (Termasuk ConfigurationClassPostProcessor)
      │    ├──► registerBeanPostProcessors()
      │    ├──► initMessageSource() & initApplicationEventMulticaster()
      │    ├──► onRefresh() ──► Start Embedded Tomcat/Jetty/Undertow
      │    ├──► finishBeanFactoryInitialization() ──► Instansiasi Non-Lazy Singletons
      │    └──► finishRefresh() ──► Publish ContextRefreshedEvent & Web Server Start
      │
      └──► Post-Initialization Callbacks:
           ├──► CommandLineRunner & ApplicationRunner dijalankan
           └──► Event: applicationReady
```

#### 3.2 Auto-Configuration Engine & Conditional Evaluation Matrix
Mulai Spring Boot 2.7 hingga 3.x, mekanisme Service Provider Interface (SPI) untuk konfigurasi otomatis beralih dari `META-INF/spring.factories` ke file deklarasi standar:
`META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`

Mekanisme ini ditenagai oleh `AutoConfigurationImportSelector` yang mengevaluasi kondisi menggunakan `ConditionEvaluator`. Fase evaluasi kondisi terbagi menjadi dua tahap:
1.  **ConfigurationPhase.PARSE_CONFIGURATION**: Mengevaluasi apakah sebuah kelas `@Configuration` harus diabaikan secara total sebelum parsing bytecode definisi bean di dalamnya.
2.  **ConfigurationPhase.REGISTER_BEAN**: Mengevaluasi kondisi spesifik pada level `@Bean` saat definisi bean sedang didaftarkan ke `BeanDefinitionRegistry`.

Jika sebuah kondisi (misal `@ConditionalOnClass`) gagal, seluruh cabang konfigurasi dipangkas (*pruned*) dari *metaspace*, meminimalkan footprint memori.

#### 3.3 Bean Lifecycle: Internal Hooks (`BeanFactoryPostProcessor` vs `BeanPostProcessor`)
Perbedaan fundamental ini sangat krusial dalam rekayasa framework internal Spring:
*   **`BeanFactoryPostProcessor` (BFPP)**: Beroperasi pada metadata (`BeanDefinition`). Dipanggil ketika definisi bean telah dimuat tetapi **belum ada instance bean yang dibuat**. Digunakan untuk mengubah konfigurasi bean definition (misalnya merelasikan properti, memanipulasi profil, memodifikasi dependensi).
*   **`BeanPostProcessor` (BPP)**: Beroperasi pada objek runtime instansiasi bean. Dipanggil dua kali untuk setiap bean: `postProcessBeforeInitialization` (sebelum `@PostConstruct` / `InitializingBean`) dan `postProcessAfterInitialization` (setelah inisialisasi bean selesai, sering digunakan untuk membuat AOP dynamic proxy / CGLIB wrapper).

#### 3.4 Spring Boot 3, Virtual Threads, dan AOT Runtime
*   **Virtual Threads (Project Loom)**: Dengan mengaktifkan `spring.threads.virtual.enabled=true`, Tomcat menggunakan virtual thread executor (`Executors.newVirtualThreadPerTaskExecutor()`). Ini memutus korelasi 1:1 antara OS thread dan Java Thread, mengubah model konkurensi menjadi *M:N scheduling*.
*   **AOT (Ahead-of-Time) Engine**: Mentransformasi evaluasi dinamis (refleksi, scanning classpath, parsing anotasi) saat build-time. Outputnya berupa kode Java generik teroptimasi yang mendaftarkan `BeanDefinition` secara langsung tanpa refleksi, memungkinkan kompilasi native via GraalVM dengan startup time di bawah 50ms dan footprint memori minimal.

---

### 4. Why & What

| Dimensi | Pendekatan Monolitik Manual (Spring Legacy / Vanilla Java) | Pendekatan Enterprise Spring Boot 3.x |
| :--- | :--- | :--- |
| **Wiring Bean** | Manual XML atau lusinan kelas `@Configuration` eksplisit, rawan human error dan regresi runtime. | *Convention-over-Configuration* berbasis evaluasi kondisi otomatis berkinerja tinggi. |
| **Runtime Server** | Deployment WAR ke external servlet container terpisah (Tomcat/JBoss); versi server dan aplikasi decoupling tidak konsisten. | *Self-contained executable JAR* dengan embedded server terintegrasi, memudahkan deployment containerized (Docker/K8s). |
| **Observability** | Integrasi logging manual, métrik vendor-locked, dan health check yang dibangun sendiri dari nol. | Standar enterprise bawaan via Micrometer, Actuator, dan OpenTelemetry-ready metrics tracing. |
| **Bootstrap Cost** | Waktu parsing lambat, scanning classpath berulang-ulang tanpa batasan domain yang jelas. | Modul modular, AOT optimization, lazy initialization bertarget, serta integrasi native thread scheduling. |

---

### 5. How (Workflow Detail)

1.  **Eksekusi JVM**: OS mengeksekusi instruksi: `java -jar application.jar`.
2.  **Arsip Packaging (Launcher)**: `JarLauncher` membaca struktur `BOOT-INF/classes` dan `BOOT-INF/lib`, menginisialisasi `LaunchedURLClassLoader` khusus Spring Boot untuk isolasi dependensi.
3.  **Bootstrapping Environment**:
    *   Membuat `ApplicationEnvironmentPreparedEvent`.
    *   `RandomValuePropertySource`, `application.properties`/`application.yml`, OS Environment, dan Java System Properties digabungkan ke dalam hierarki `MutablePropertySources`.
4.  **Auto-Configuration Resolution**:
    *   Membaca semua entri di `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`.
    *   Menerapkan filter predikat melalui `OnClassCondition`, `OnPropertyCondition`, `OnWebApplicationCondition`.
5.  **Context Creation & Refresh**:
    *   Instansiasi `AnnotationConfigServletWebServerApplicationContext`.
    *   Pendaftaran Bean Definition dari `@SpringBootApplication`.
    *   Inisialisasi Servlet Engine (Tomcat/Jetty instance) pada port target (default: 8080).
6.  **State Transition to Ready**:
    *   Bean yang bersifat non-lazy diinisialisasi melalui `DefaultListableBeanFactory.preInstantiateSingletons()`.
    *   Validasi siklus hidup selesai, `ApplicationReadyEvent` dikirimkan ke semua listener terdaftar.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Pabrik Manufaktur Otomatis Cerdas
Bayangkan Anda membangun pabrik mobil:
*   **BeanFactoryPostProcessor (Blueprint Inspector)**: Sebelum perakitan dimulai, inspektur memeriksa cetak biru (*BeanDefinition*). Jika ada instruksi "Gunakan mesin diesel", cetak biru diubah menjadi "Gunakan motor listrik" sebelum ada satu pun komponen fisik dipesan atau dirakit.
*   **Bean Instantiation**: Mesin fisik dicetak di lini perakitan.
*   **BeanPostProcessor (Quality Control & Custom Modder)**: Sebelum mobil dikirim ke konsumen, teknisi modifikasi memasang sensor telemetry (Proxying/Tracing) atau mengecat ulang bodi mobil (Decorating/AOP wrapping).
*   **Embedded Tomcat**: Gudang pabrik tidak lagi mengirim sasis mobil ke garasi eksternal untuk dipasangi roda; pabrik memiliki jalan tol sendiri yang langsung terhubung ke sistem logistik global.

```
       ARUS SIKLUS HIDUP BEAN DALAM SPRING APPLICATION CONTEXT
       ═══════════════════════════════════════════════════════

   [ Classpath Scanning / Auto-Configuration ]
                       │
                       ▼
       ┌───────────────────────────────┐
       │   BeanDefinition Registry     │
       └───────────────┬───────────────┘
                       │
                       ▼
       ┌───────────────────────────────┐
       │ BeanFactoryPostProcessor      │  ◄── Modifikasi Metadata
       │ (e.g., PropertySourcesPlaceholderConfigurer)
       └───────────────┬───────────────┘
                       │
                       ▼  Instansiasi Instans Bean Mentah (Constructor Injection)
       ┌───────────────────────────────┐
       │    Bean Instance Created      │
       └───────────────┬───────────────┘
                       │
                       ▼  Populate Properties (Field/Setter Injection)
       ┌───────────────────────────────┐
       │     Dependency Injection      │
       └───────────────┬───────────────┘
                       │
                       ▼
       ┌───────────────────────────────┐
       │ BeanPostProcessor:            │  ◄── Hook Pra-Inisialisasi
       │ postProcessBeforeInitialization
       └───────────────┬───────────────┘
                       │
                       ▼
       ┌───────────────────────────────┐
       │ Initializing Hooks:           │
       │ 1. @PostConstruct             │  ◄── Eksekusi Logika Inisialisasi
       │ 2. InitializingBean           │
       │ 3. custom init-method         │
       └───────────────┬───────────────┘
                       │
                       ▼
       ┌───────────────────────────────┐
       │ BeanPostProcessor:            │  ◄── Wrapping Proxy (Spring AOP,
       │ postProcessAfterInitialization│      Security, Transactional)
       └───────────────┬───────────────┘
                       │
                       ▼
       ┌───────────────────────────────┐
       │       READY TO USE BEAN       │
       │   (Stored in Singleton Cache) │
       └───────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Dynamic Custom Condition Evaluator
Mekanisme evaluasi kondisi kustom yang mendeteksi apakah aplikasi berjalan di lingkungan berkinerja tinggi (berdasarkan core CPU runtime).

```java
package com.enterprise.architecture.condition;

import org.springframework.context.annotation.Condition;
import org.springframework.context.annotation.ConditionContext;
import org.springframework.core.type.AnnotatedTypeMetadata;

public class HighPerformanceEnvironmentCondition implements Condition {

    @Override
    public boolean matches(ConditionContext context, AnnotatedTypeMetadata metadata) {
        int availableProcessors = Runtime.getRuntime().availableProcessors();
        String performanceTier = context.getEnvironment().getProperty("app.performance.tier", "standard");
        
        // Memeriksa kondisi apakah sistem memenuhi kriteria high-compute
        return availableProcessors >= 4 && "high-performance".equalsIgnoreCase(performanceTier);
    }
}
```

Penggunaan kondisi pada konfigurasi bean:

```java
package com.enterprise.architecture.config;

import com.enterprise.architecture.condition.HighPerformanceEnvironmentCondition;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Conditional;
import org.springframework.context.annotation.Configuration;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

@Configuration(proxyBeanMethods = false)
public class ThreadingConfiguration {

    @Bean(name = "workerThreadPool")
    @Conditional(HighPerformanceEnvironmentCondition.class)
    public ExecutorService highPerformanceExecutor() {
        return Executors.newFixedThreadPool(16);
    }

    @Bean(name = "workerThreadPool")
    public ExecutorService defaultExecutor() {
        return Executors.newSingleThreadExecutor();
    }
}
```

#### 7.2 Practical Example: Enterprise Production Starter Module
Implementasi Enterprise-Grade Starter internal yang menyediakan tracing latensi otomatis dan dynamic security token verification menggunakan custom `BeanPostProcessor` dan auto-configuration berstandar Spring Boot 3.

##### Langkah 1: Buat Anotasi Audit Tracing
```java
package com.enterprise.starter.audit;

import java.lang.annotation.*;

@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface EnterpriseAuditTrace {
    String operationName() default "";
    boolean logPayload() default false;
}
```

##### Langkah 2: Buat Dynamic Proxy BeanPostProcessor
```java
package com.enterprise.starter.audit;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.BeansException;
import org.springframework.beans.factory.config.BeanPostProcessor;
import org.springframework.cglib.proxy.Enhancer;
import org.springframework.cglib.proxy.MethodInterceptor;

import java.lang.reflect.Method;
import java.util.Arrays;

public class AuditTraceBeanPostProcessor implements BeanPostProcessor {

    private static final Logger log = LoggerFactory.getLogger(AuditTraceBeanPostProcessor.class);

    @Override
    public Object postProcessAfterInitialization(Object bean, String beanName) throws BeansException {
        Class<?> targetClass = bean.getClass();
        
        // Periksa apakah ada method yang dianotasi @EnterpriseAuditTrace
        boolean hasMonitoredMethods = Arrays.stream(targetClass.getMethods())
                .anyMatch(m -> m.isAnnotationPresent(EnterpriseAuditTrace.class));

        if (!hasMonitoredMethods) {
            return bean; // Kembalikan bean asli tanpa overhead proxy
        }

        Enhancer enhancer = new Enhancer();
        enhancer.setSuperclass(targetClass);
        enhancer.setCallback((MethodInterceptor) (obj, method, args, proxy) -> {
            EnterpriseAuditTrace annotation = method.getAnnotation(EnterpriseAuditTrace.class);
            if (annotation == null) {
                return proxy.invoke(bean, args);
            }

            long startTime = System.nanoTime();
            String operation = annotation.operationName().isEmpty() ? method.getName() : annotation.operationName();
            
            try {
                log.info("[AUDIT-START] Operation: {} on Bean: {}", operation, beanName);
                Object result = proxy.invoke(bean, args);
                long duration = (System.nanoTime() - startTime) / 1_000_000;
                log.info("[AUDIT-SUCCESS] Operation: {} completed in {} ms", operation, duration);
                return result;
            } catch (Exception ex) {
                long duration = (System.nanoTime() - startTime) / 1_000_000;
                log.error("[AUDIT-FAIL] Operation: {} failed after {} ms. Reason: {}", operation, duration, ex.getMessage());
                throw ex;
            }
        });

        return enhancer.create();
    }
}
```

##### Langkah 3: Auto-Configuration Class
```java
package com.enterprise.starter.audit;

import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;

@AutoConfiguration
@EnableConfigurationProperties(AuditProperties.class)
@ConditionalOnProperty(prefix = "enterprise.audit", name = "enabled", havingValue = "true", matchIfMissing = true)
public class EnterpriseAuditAutoConfiguration {

    @Bean
    public AuditTraceBeanPostProcessor auditTraceBeanPostProcessor() {
        return new AuditTraceBeanPostProcessor();
    }
}
```

##### Langkah 4: Configuration Properties
```java
package com.enterprise.starter.audit;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "enterprise.audit")
public class AuditProperties {
    private boolean enabled = true;
    private String environment = "production";

    public boolean isEnabled() { return enabled; }
    public void setEnabled(boolean enabled) { this.enabled = enabled; }
    public String getEnvironment() { return environment; }
    public void setEnvironment(String environment) { this.environment = environment; }
}
```

##### Langkah 5: Pendaftaran SPI Modern (Spring Boot 3.x)
File: `src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`
```text
com.enterprise.starter.audit.EnterpriseAuditAutoConfiguration
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Fintech Payment Core (Payment Gateway)
Sebuah perusahaan Unicorn Payment memproses hingga 25.000 Transaksi Per Detik (TPS) pada momen flash sale nasional. Arsitektur backend menggunakan Spring Boot 3 dengan deployment Kubernetes (EKS).

#### Masalah Kritis:
1.  **Puncak Latensi Cold-Start**: Ketika auto-scaling K8s terpicu (HPA), pod baru membutuhkan waktu 42 detik untuk mencapai status `Ready`. Selama rentang waktu ini, beban dialihkan ke pod yang ada sehingga menyebabkan cascading latency spike (P99 naik dari 60ms ke 3.200ms).
2.  **Thread Pool Starvation**: Driver database JDBC tradisional memblokir platform threads sistem saat terjadi query berkepanjangan pada PostgreSQL connection pool, mengakibatkan thread exhaustion pada Tomcat.
3.  **Startup Metadata Overhead**: Classpath scanning terhadap ribuan komponen pihak ketiga menyebabkan JVM memakan 1.2 GB Metaspace sebelum melayani request pertama.

#### Solusi Arsitektur:
1.  **Eliminasi Komponen Tidak Diperlukan via Configuration Pruning**:
    Melalui penonaktifan autoconfiguration yang tidak dipakai pada production service:
    ```yaml
    spring:
      autoconfigure:
        exclude:
          - org.springframework.boot.autoconfigure.websocket.servlet.WebSocketServletAutoConfiguration
          - org.springframework.boot.autoconfigure.thymeleaf.ThymeleafAutoConfiguration
          - org.springframework.boot.autoconfigure.mail.MailSenderAutoConfiguration
    ```
2.  **Aktivasi Virtual Threads & Hikari Connection Tuning**:
    ```yaml
    spring:
      threads:
        virtual:
          enabled: true
      datasource:
        hikari:
          maximum-pool-size: 50
          minimum-idle: 20
          idle-timeout: 300000
          connection-timeout: 2000
    ```
    *Mitigasi Virtual Thread Pinning*: Memastikan tidak ada *synchronized block* yang membungkus pemanggilan I/O eksternal (menggantinya dengan `ReentrantLock`).
3.  **Penerapan Spring Boot 3 AOT Native Build**:
    Mentransformasi core service menjadi GraalVM Native Image executable untuk worker pod yang berorientasi pada horizontal autoscaling dinamis.

#### Hasil Metrik Produksi:
*   **Startup Time**: Turun dari **42 detik** menjadi **0.18 detik** (menggunakan GraalVM native image) dan **4.8 detik** (menggunakan JVM AOT cache).
*   **Metaspace Footprint**: Turun 68%, dari 1.2 GB menjadi 384 MB.
*   **P99 Latency under 25k TPS**: Stabil pada **38ms** (turun dari 3.200ms).
*   **Resource Cost Optimization**: Penghematan biaya komputasi AWS EC2 sebesar 35% karena peningkatan density per core instance.

---

### 9. Trade-offs

| Aspek / Pilihan Arsitektur | Keuntungan | Biaya / Kerugian | Rekomendasi Konteks |
| :--- | :--- | :--- | :--- |
| **GraalVM Native Image vs JVM Tradisional** | Startup instan (< 100ms), footprint RAM sangat rendah, kebal deserialization injection vectors. | Build time sangat lambat (membutuhkan pipeline CI/CD tinggi RAM), hilangnya optimasi dynamic runtime JIT profiling (C2 compiler). | Cocok untuk serverless/FaaS, edge computing, K8s rapid scale workers. Kurang cocok untuk monolit monolitik masif dengan banyak refleksi dinamis. |
| **Virtual Threads (Loom) vs Reactive (WebFlux)** | Kode imperatif linier, debugging sederhana, call stack utuh, kompatibel dengan legacy code. | Memerlukan review pustaka pihak ketiga untuk menghindari thread pinning (`synchronized` keyword pada blok I/O). | Standar de-facto untuk I/O bound business logic baru berbasis Spring Boot 3. |
| **Custom Auto-Configurations vs Explicit Config** | Reusability masif lintas ratusan repositori microservice, standar engineering seragam. | Abstraksi berlebih; engineer pemula sulit menelusuri sumber definisi bean jika dokumentasi SPI buruk. | Sangat direkomendasikan untuk Platform / Core Architecture Team di level enterprise. |
| **Lazy Initialization (`spring.main.lazy-initialization=true`)** | Waktu bootstrap lokal dan environment testing sangat cepat. | Kesalahan konfigurasi bean baru terdeteksi saat runtime/first request, bukan saat boot; first request latency naik drastis. | Gunakan HANYA pada profil lokal dev/unit testing; **DILARANG** diaktifkan pada production. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Silent Circular Dependency Failures
*   **Gejala**: `BeanCurrentlyInCreationException` saat context startup.
*   **Penyebab**: Mulai Spring Boot 2.6+, circular dependencies dinonaktifkan secara *default* (`spring.main.allow-circular-references=false`). Mengaktifkan flag ini adalah anti-pattern yang menutupi cacat desain coupling.
*   **Solusi**: Refaktor rancangan arsitektur menggunakan *Domain Events* (`ApplicationEventPublisher`) atau pisahkan dependency ke interface baru/mediator pattern.

```java
// ANTI-PATTERN: Pemecahan malas via @Lazy
@Service
public class OrderService {
    @Autowired @Lazy private PaymentService paymentService; // BAD PRACTICE
}

// BEST PRACTICE: Event-Driven Decoupling
@Service
public class OrderService {
    private final ApplicationEventPublisher eventPublisher;

    public OrderService(ApplicationEventPublisher eventPublisher) {
        this.eventPublisher = eventPublisher;
    }

    public void completeOrder(Order order) {
        // Emit domain event, PaymentService mendengarkan event ini
        eventPublisher.publishEvent(new OrderCompletedEvent(order.getId()));
    }
}
```

#### 10.2 Diagnostic Tool: Actuator Conditions Evaluation Report
Jika bean auto-configuration Anda tidak dimuat secara misterius, jangan menebak-nebak. Jalankan aplikasi dengan argumen JVM debug atau periksa endpoint conditions:
```bash
java -Ddebug=true -jar target/app.jar
```
Atau akses endpoint produksi:
```http
GET /actuator/conditions
```
Periksa bagian `"negativeMatches"` untuk mengetahui kondisi mana yang gagal terpenuhi:
```json
{
  "contexts": {
    "application": {
      "unconditionalClasses": [],
      "negativeMatches": {
        "EnterpriseAuditAutoConfiguration": {
          "notMatched": [
            {
              "condition": "OnPropertyCondition",
              "message": "@ConditionalOnProperty (enterprise.audit.enabled=true) did not find property 'enterprise.audit.enabled'"
            }
          ]
        }
      }
    }
  }
}
```

#### 10.3 Virtual Thread Pinning Diagnosis
Jika throughput anjlok saat virtual thread aktif, JVM platform thread mungkin mengalami *pinning* karena blok `synchronized`.
*   **Deteksi**: Jalankan JVM dengan flag diagnostik:
    ```bash
    -Djdk.tracePinnedThreads=full
    ```
*   **Solusi**: Temukan stack trace yang mengarah ke `synchronized (lock)` pada operasi I/O dan ganti dengan `java.util.concurrent.locks.ReentrantLock`.

---

### 11. Best Practices (Production Checklist)

- [ ] **Eksplisitkan Bean Injection**: Gunakan *Constructor Injection* murni. Jangan pernah menggunakan field injection (`@Autowired` pada field), karena merusak immutability dan menyulitkan isolasi unit test.
- [ ] **Proxy Bean Methods**: Pasang `@Configuration(proxyBeanMethods = false)` jika kelas konfigurasi Anda tidak memanggil method `@Bean` lain secara internal. Ini mengeliminasi pembuatan subclass CGLIB dan menghemat memori startup.
- [ ] **Standarisasi Conditional Ordering**: Selalu tetapkan `@AutoConfigureOrder` atau deklarasikan dependensi eksplisit via `@AutoConfigureAfter` pada custom starter agar hierarki instansiasi tidak acak.
- [ ] **Aktifkan Graceful Shutdown**: Cegah terputusnya koneksi inflight saat deployment Kubernetes:
  ```yaml
  server:
    shutdown: graceful
  spring:
    lifecycle:
      timeout-per-shutdown-phase: 20s
  ```
- [ ] **Hardening Actuator Endpoints**: Jangan pernah membuka endpoint `/actuator/env`, `/actuator/heapdump`, atau `/actuator/beans` ke publik. Batasi hanya `/actuator/health` dan `/actuator/prometheus` pada network internal infra.
- [ ] **Validasi Metadata Configuration**: Selalu sertakan `spring-boot-configuration-processor` pada modul konfigurasi kustom untuk menghasilkan metadata IDE auto-completion bagi developer internal.

---

### 12. Hands-on Practice

Target path direktori: `hands-on/m02/`

#### Skenario Laboratorium:
Membangun custom dynamic rate-limiter starter yang memanfaatkan `BeanFactoryPostProcessor` dan runtime `BeanPostProcessor` untuk mencegat request pada layer service.

#### Struktur Direktori:
```text
hands-on/m02/
├── pom.xml
└── src
    ├── main
    │   ├── java
    │   │   └── com
    │   │       └── enterprise
    │   │           └── platform
    │   │               ├── CoreApplication.java
    │   │               ├── annotation
    │   │               │   └── EnforceRateLimit.java
    │   │               ├── autoconfigure
    │   │               │   └── RateLimiterAutoConfiguration.java
    │   │               ├── interceptor
    │   │               │   └── RateLimiterPostProcessor.java
    │   │               └── service
    │   │                   └── PaymentExecutionService.java
    │   └── resources
    │       ├── application.yml
    │       └── META-INF
    │           └── spring
    │               └── org.springframework.boot.autoconfigure.AutoConfiguration.imports
    └── test
        └── java
            └── com
                └── enterprise
                    └── platform
                        └── RateLimiterIntegrationTest.java
```

#### File 1: `pom.xml`
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

    <groupId>com.enterprise.platform</groupId>
    <artifactId>hands-on-m02</artifactId>
    <version>1.0.0-SNAPSHOT</version>

    <properties>
        <java.version>21</java.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
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

#### File 2: `src/main/java/com/enterprise/platform/annotation/EnforceRateLimit.java`
```java
package com.enterprise.platform.annotation;

import java.lang.annotation.*;

@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface EnforceRateLimit {
    int maxRequestsPerSecond() default 5;
}
```

#### File 3: `src/main/java/com/enterprise/platform/interceptor/RateLimiterPostProcessor.java`
```java
package com.enterprise.platform.interceptor;

import com.enterprise.platform.annotation.EnforceRateLimit;
import org.springframework.beans.BeansException;
import org.springframework.beans.factory.config.BeanPostProcessor;
import org.springframework.cglib.proxy.Enhancer;
import org.springframework.cglib.proxy.MethodInterceptor;

import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

public class RateLimiterPostProcessor implements BeanPostProcessor {

    private final Map<String, AtomicInteger> requestCounters = new ConcurrentHashMap<>();
    private final Map<String, Long> windowTimestamps = new ConcurrentHashMap<>();

    @Override
    public Object postProcessAfterInitialization(Object bean, String beanName) throws BeansException {
        Class<?> beanClass = bean.getClass();
        
        boolean hasAnnotation = Arrays.stream(beanClass.getMethods())
                .anyMatch(m -> m.isAnnotationPresent(EnforceRateLimit.class));

        if (!hasAnnotation) {
            return bean;
        }

        Enhancer enhancer = new Enhancer();
        enhancer.setSuperclass(beanClass);
        enhancer.setCallback((MethodInterceptor) (obj, method, args, proxy) -> {
            EnforceRateLimit rateLimit = method.getAnnotation(EnforceRateLimit.class);
            if (rateLimit != null) {
                String key = beanName + "#" + method.getName();
                long currentWindow = System.currentTimeMillis() / 1000;
                
                windowTimestamps.compute(key, (k, oldVal) -> {
                    if (oldVal == null || oldVal != currentWindow) {
                        requestCounters.put(key, new AtomicInteger(0));
                        return currentWindow;
                    }
                    return oldVal;
                });

                int currentCount = requestCounters.get(key).incrementAndGet();
                if (currentCount > rateLimit.maxRequestsPerSecond()) {
                    throw new IllegalStateException("Rate limit exceeded for operation: " + key + 
                            ". Max allowed: " + rateLimit.maxRequestsPerSecond());
                }
            }
            return proxy.invoke(bean, args);
        });

        return enhancer.create();
    }
}
```

#### File 4: `src/main/java/com/enterprise/platform/autoconfigure/RateLimiterAutoConfiguration.java`
```java
package com.enterprise.platform.autoconfigure;

import com.enterprise.platform.interceptor.RateLimiterPostProcessor;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;

@AutoConfiguration
@ConditionalOnProperty(name = "enterprise.ratelimiter.enabled", havingValue = "true", matchIfMissing = true)
public class RateLimiterAutoConfiguration {

    @Bean
    public RateLimiterPostProcessor rateLimiterPostProcessor() {
        return new RateLimiterPostProcessor();
    }
}
```

#### File 5: `src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`
```text
com.enterprise.platform.autoconfigure.RateLimiterAutoConfiguration
```

#### File 6: `src/main/java/com/enterprise/platform/service/PaymentExecutionService.java`
```java
package com.enterprise.platform.service;

import com.enterprise.platform.annotation.EnforceRateLimit;
import org.springframework.stereotype.Service;

@Service
public class PaymentExecutionService {

    @EnforceRateLimit(maxRequestsPerSecond = 2)
    public String executeTransaction(String txId) {
        return "SUCCESS-" + txId;
    }
}
```

#### File 7: `src/main/java/com/enterprise/platform/CoreApplication.java`
```java
package com.enterprise.platform;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class CoreApplication {
    public static void main(String[] args) {
        SpringApplication.run(CoreApplication.class, args);
    }
}
```

#### File 8: `src/test/java/com/enterprise/platform/RateLimiterIntegrationTest.java`
```java
package com.enterprise.platform;

import com.enterprise.platform.service.PaymentExecutionService;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest(classes = CoreApplication.class)
class RateLimiterIntegrationTest {

    @Autowired
    private PaymentExecutionService paymentService;

    @Test
    void shouldBlockWhenRateLimitExceeded() {
        // Panggilan ke-1 & ke-2 harus berhasil (maxRequestsPerSecond = 2)
        Assertions.assertEquals("SUCCESS-1", paymentService.executeTransaction("1"));
        Assertions.assertEquals("SUCCESS-2", paymentService.executeTransaction("2"));

        // Panggilan ke-3 dalam detik yang sama harus memicu Exception
        Assertions.assertThrows(IllegalStateException.class, () -> {
            paymentService.executeTransaction("3");
        });
    }
}
```

---

### 13. Exercise

#### Level Easy
1.  Buat custom conditional annotation `@ConditionalOnMemoryAvailable(minMegabytes = 512)` yang mengevaluasi apakah memori bebas pada JVM runtime (`Runtime.getRuntime().freeMemory()`) mencukupi sebelum memuat bean caching in-memory.

#### Level Medium
1.  Implementasikan sebuah `EnvironmentPostProcessor` kustom yang membaca encrypted environment secret (contoh: `ENC(a8df7h93...)`) dari `application.yml`, mendekripsinya menggunakan algoritma AES-GCM, dan memasukkan nilai plain-text kembali ke `ConfigurableEnvironment` sebelum bean lifecycle dimulai.

#### Level Hard
1.  Rancang mekanisme dynamic multi-tenant datasource routing menggunakan `AbstractRoutingDataSource` yang dikonfigurasi melalui Custom Auto-Configuration Starter. Starter harus membaca definisi tenant dari properti dinamis:
    ```yaml
    tenants:
      datasource:
        tenant-a:
          url: jdbc:postgresql://...
        tenant-b:
          url: jdbc:postgresql://...
    ```
    Starter harus mampu menginstansiasi DataSource per-tenant secara lazy tanpa mendefinisikan bean manual satu per satu di file konfigurasi utama.

---

### 14. Challenge

#### Skenario Kasus Kompleks: Dynamic Zero-Downtime Hot-Reload Plugin Architecture
Sebuah bank digital membutuhkan sistem deteksi fraud yang aturannya (*rules engine*) berubah setiap minggu. Regulasi perbankan melarang keras terjadinya downtime sekecil apa pun (*Zero Application Context Restarts*).

#### Spesifikasi Tantangan:
1.  Rancang mekanisme arsitektur menggunakan Spring Boot 3 di mana modul JAR aturan fraud eksternal dapat diletakkan di sebuah direktori lokal (`/opt/plugins/`).
2.  Gunakan ClassLoader kustom (anak dari `LaunchedURLClassLoader`) yang mendeteksi kedatangan file JAR baru via Java `WatchService`.
3.  Definisikan dan daftarkan bean di dalam file JAR tersebut secara dinamis langsung ke dalam Spring `GenericApplicationContext` yang sedang berjalan (`registerBeanDefinition()`) tanpa memicu pemanggilan `context.refresh()`.
4.  Jika versi file JAR baru diperbarui, starter harus secara aman melakukan *destroy* pada bean lama (`DefaultListableBeanFactory.destroySingleton()`), membebaskan referensi ClassLoader lama untuk mencegah JVM Metaspace OOM Leak, dan mendaftarkan implementasi bean yang baru.
5.  Pastikan eksekusi transaksi yang sedang berjalan (*in-flight threads*) tidak mengalami `ClassNotFoundException` atau thread locks saat penggantian instance berlangsung.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic
1.  **Kapan tepatnya metode `postProcessBeforeInitialization` pada `BeanPostProcessor` dipanggil oleh Spring Container?**
    *   A. Sebelum constructor bean dipanggil.
    *   B. Setelah constructor dan dependency injection selesai, sebelum `@PostConstruct` atau method init.
    *   C. Tepat setelah metode shutdown lifecycle dipanggil.
    *   D. Sebelum `BeanFactoryPostProcessor` dijalankan.
    *   *Jawaban yang Benar*: B. BPP beroperasi pada instance yang sudah dibentuk oleh constructor dan propertinya sudah diinjeksi, namun sebelum initialization hooks dijalankan.

2.  **Apa perbedaan mendasar antara `META-INF/spring.factories` dan `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`?**
    *   A. Tidak ada perbedaan, hanya penamaan folder.
    *   B. `spring.factories` berbasis format properties dan dievaluasi secara eager, sedangkan file `.imports` baru diperkenalkan di Spring Boot 2.7/3.x khusus untuk memisahkan auto-configuration selector secara efisien dan mendukung AOT compilation.
    *   C. File `.imports` hanya dapat digunakan jika aplikasi berjalan di GraalVM Native Image.
    *   D. `spring.factories` tidak lagi didukung untuk jenis konfigurasi apa pun pada Spring Boot 3.
    *   *Jawaban yang Benar*: B. File `.imports` memisahkan parsing auto-configuration dari SPI umum lainnya untuk efisiensi build time dan AOT compatibility.

3.  **Anotasi manakah yang digunakan untuk memastikan bahwa sebuah kelas konfigurasi otomatis hanya dievaluasi jika bean tertentu belum didaftarkan oleh pengguna?**
    *   A. `@ConditionalOnClass`
    *   B. `@ConditionalOnMissingBean`
    *   C. `@ConditionalOnMissingClass`
    *   D. `@ConditionalOnAvailableBean`
    *   *Jawaban yang Benar*: B. `@ConditionalOnMissingBean` memungkinkan developer meng-override bean default bawaan framework dengan bean kustom mereka sendiri.

4.  **Apa fungsi dari atribut `proxyBeanMethods = false` pada anotasi `@Configuration`?**
    *   A. Mencegah konfigurasi tersebut dimuat oleh Spring context.
    *   B. Menginstruksikan CGLIB untuk tidak membuat dynamic subclass proxy atas kelas konfigurasi, sehingga method `@Bean` diperlakukan sebagai method pabrik biasa (menghemat memori dan waktu startup).
    *   C. Menonaktifkan dependency injection pada kelas konfigurasi tersebut.
    *   D. Mengaktifkan fitur multi-threading otomatis pada setiap method `@Bean`.
    *   *Jawaban yang Benar*: B. Tanpa proxy CGLIB, pemanggilan berulang antar method `@Bean` tidak akan mengembalikan singleton yang sama, namun mengurangi alokasi memori runtime.

5.  **Peristiwa (event) manakah yang menandai bahwa Spring Boot telah selesai sepenuhnya melakukan inisialisasi dan siap melayani HTTP traffic?**
    *   A. `ContextRefreshedEvent`
    *   B. `ApplicationEnvironmentPreparedEvent`
    *   C. `ApplicationReadyEvent`
    *   D. `ApplicationStartedEvent`
    *   *Jawaban yang Benar*: C. `ApplicationReadyEvent` dikirimkan paling akhir setelah seluruh listener, runners, dan server bindings selesai beroperasi.

---

#### Bagian 2: Intermediate
6.  **Mengapa modifikasi `BeanDefinition` di dalam metode `BeanPostProcessor` dianggap sebagai arsitektur anti-pattern yang berbahaya?**
    *   A. Karena `BeanPostProcessor` tidak memiliki akses ke context.
    *   B. Karena pada fase `BeanPostProcessor`, pohon metadata definisi bean sudah terkunci dan instansiasi bean sedang berjalan; modifikasi definisi bean pada tahap ini memicu instansiasi prematur yang melangkahi `BeanFactoryPostProcessor` lainnya.
    *   C. Karena memicu `ClassCastException` pada level JVM security manager.
    *   D. Karena compiler Java melarang manipulasi metadata di runtime.
    *   *Jawaban yang Benar*: B. Modifikasi metadata struktur bean wajib dilakukan di `BeanFactoryPostProcessor`. Memanggil factory dari BPP dapat menyebabkan *premature bean creation* dan hilangnya AOP proxies.

7.  **Jika terdapat dua auto-configuration, `ClassA` dan `ClassB`, di mana `ClassB` bergantung pada bean yang dihasilkan oleh `ClassA`. Bagaimana cara paling tepat menjamin urutan eksekusi pemuatannya?**
    *   A. Menggunakan anotasi `@Order(1)` pada `ClassA` dan `@Order(2)` pada `ClassB`.
    *   B. Menambahkan anotasi `@AutoConfigureAfter(ClassA.class)` pada deklarasi kelas `ClassB`.
    *   C. Menuliskan nama `ClassA` di baris atas nama `ClassB` di file `.imports`.
    *   D. Menggunakan anotasi `@Priority` standar Java.
    *   *Jawaban yang Benar*: B. `@Order` tidak bekerja secara deterministik pada urutan kelas auto-configuration. Harus menggunakan `@AutoConfigureAfter`, `@AutoConfigureBefore`, atau `@AutoConfigureOrder`.

8.  **Apa yang terjadi di belakang layar jika Anda mengaktifkan `spring.threads.virtual.enabled=true` pada aplikasi web berbasis Spring Boot 3 Servlet (Tomcat)?**
    *   A. Tomcat digantikan secara otomatis oleh Netty reactive engine.
    *   B. Tomcat mengabaikan `max-threads` standar dan menggunakan `VirtualThreadExecutor` internal Java 21, di mana setiap request HTTP masuk dilayani oleh virtual thread baru yang ringan.
    *   C. Setiap thread platform OS akan menduplikasi proses memori sebanyak 10 kali.
    *   D. Fitur asynchronous method (`@Async`) dimatikan otomatis.
    *   *Jawaban yang Benar*: B. Protokol handler Tomcat Servlet beralih menggunakan Virtual Thread per request executor, meniadakan pooling thread terbatas pada level platform OS.

9.  **Mengapa implementasi dynamic proxy CGLIB pada `BeanPostProcessor` kustom dapat menyebabkan hilangnya referensi anotasi pada method controller asli jika tidak ditangani dengan benar?**
    *   A. Karena CGLIB membuat subclass baru saat runtime; jika framework pencari anotasi tidak menggunakan `AnnotationUtils.findAnnotation()` melainkan refleksi Java standar (`Method.getAnnotation()`), anotasi pada interface atau superclass tidak akan terbaca.
    *   B. Karena CGLIB menghapus metadata class file dari disk.
    *   C. Karena anotasi Java otomatis hilang saat masuk ke JVM PermGen.
    *   D. Karena CGLIB hanya mendukung pemanggilan tipe data primitif.
    *   *Jawaban yang Benar*: A. Refleksi Java standar (`Class.getMethod().getAnnotation()`) tidak mendeteksi anotasi warisan pada level method proxy; utilitas pencari hierarki Spring (seperti `AnnotationUtils` atau `AnnotatedElementUtils`) wajib digunakan.

10. **Bagaimana cara mencegah `EnvironmentPostProcessor` kustom memicu inisialisasi bean secara prematur (*early bean initialization*)?**
    *   A. Mengubah visibilitas kelas menjadi `private`.
    *   B. Jangan pernah menyuntikkan atau meng-autowire Spring bean ke dalam `EnvironmentPostProcessor`; ia hanya boleh berinteraksi murni dengan low-level `ConfigurableEnvironment` dan SPI primitives.
    *   C. Mendaftarkannya di dalam file `application.yml`.
    *   D. Menggunakan anotasi `@Lazy` pada method constructor environment.
    *   *Jawaban yang Benar*: B. `EnvironmentPostProcessor` dieksekusi sangat awal sebelum context refresh terjadi. Memanggil bean pada fase ini akan merusak seluruh siklus inisialisasi context.

---

#### Bagian 3: Production Scenario Cases
11. **Skenario Kasus 1**:
    Sebuah tim microservice melaporkan bahwa ketika mereka menambahkan library observabilitas enterprise internal ke dalam proyek Spring Boot 3 mereka, seluruh endpoint API mengembalikan status HTTP 500 dengan pesan kesalahan:
    `java.lang.IllegalArgumentException: Cannot subclass final class com.enterprise.app.OrderRepository`.
    Setelah diinvestigasi, library internal menggunakan custom `BeanPostProcessor` yang menggunakan manipulasi CGLIB standar.
    *Pertanyaan Arsitektur*: Mengapa hal ini terjadi dan bagaimana arsitektur starter observabilitas tersebut harus diperbaiki agar kompatibel secara enterprise?
    *Solusi Rekayasa*: CGLIB memodifikasi kelas target dengan cara membuat subclass turunan secara runtime. Jika kelas target dideklarasikan sebagai `final` (atau record), CGLIB akan gagal secara fatal. Tim platform harus mengubah mekanisme BPP agar memeriksa apakah kelas target final atau mengimplementasikan interface. Jika mengimplementasikan interface, gunakan standard **JDK Dynamic Proxies** (`java.lang.reflect.Proxy`), atau jika target merupakan concrete final class, gunakan pendekatan Spring AOP berbasis standard pointcuts atau decorators (pola delegasi/wrapping) alih-alih pemaksaan subclassing CGLIB.

12. **Skenario Kasus 2**:
    Aplikasi Spring Boot 3 yang melayani transaksi volume tinggi mengalami crash berkala setiap 6 jam dengan pesan error `java.lang.OutOfMemoryError: Metaspace`. Hasil memory heap dump menunjukkan tidak ada memory leak pada Java Heap, namun terdapat ratusan ribu instansiasi kelas dengan penamaan pola:
    `com.enterprise.service.PaymentService$$EnhancerBySpringCGLIB$$...`
    *Pertanyaan Arsitektur*: Apa akar permasalahan internal pada implementasi arsitektur Spring di aplikasi tersebut?
    *Solusi Rekayasa*: Terjadi kebocoran pembentukan dynamic proxy secara berulang. Hal ini lazimnya disebabkan oleh adanya `BeanPostProcessor` kustom yang diterapkan pada bean ber-scope `prototype`, atau pemanggilan manual CGLIB `Enhancer` di dalam eksekusi alur logic method transaksi berulang tanpa melakukan caching terhadap instance `Enhancer` atau classloader. Di Metaspace, metadata definisi kelas yang di-generate runtime oleh CGLIB tidak dapat di-garbage collect jika ClassLoader yang mendefinisikannya masih memiliki strong reference. Solusinya: pindahkan pembentukan proxy hanya pada initialization bean lifecycle (singleton phase), aktifkan CGLIB naming policy cache (`enhancer.setUseCache(true)`), dan pastikan scope bean target adalah singleton.

13. **Skenario Kasus 3**:
    Sebuah sistem perbankan bertransisi ke Java 21 dan mengaktifkan Spring Virtual Threads. Saat load test mencapai 15.000 TPS, sistem mendadak mengalami kelambatan ekstrem. Thread dump menunjukkan ribuan Virtual Thread dalam status `WAITING`, dan platform threads (carrier threads) dari JVM OS terkunci di angka 16 (sesuai jumlah core) dan tidak bergerak. Stack dump menunjukkan jejak pemanggilan terhenti pada:
    `com.enterprise.security.LegacyCryptoProvider.encrypt(LegacyCryptoProvider.java:42)` yang memiliki signature:
    `public synchronized byte[] encrypt(byte[] data) { ... socket.write(...) }`.
    *Pertanyaan Arsitektur*: Identifikasi fenomena internal JVM apa yang sedang terjadi dan formulasikan solusinya secara presisi!
    *Solusi Rekayasa*: Fenomena ini disebut **Virtual Thread Pinning**. Ketika virtual thread melakukan operasi blocking I/O (seperti `socket.write`) di dalam blok atau method yang menggunakan keyword `synchronized`, runtime Java tidak dapat melepas (*unmount*) virtual thread tersebut dari platform carrier thread-nya. Akibatnya, seluruh 16 carrier OS thread terikat (*pinned*) secara permanen oleh thread yang menunggu respons socket, menyebabkan seluruh virtual thread lain antre tanpa CPU time (*carrier thread starvation*). Solusi: Ganti keyword `synchronized` pada kelas tersebut menggunakan `java.util.concurrent.locks.ReentrantLock`, yang memungkinkan unmounting virtual thread secara mulus saat proses I/O berlangsung.

---

### 16. Summary
Modul ini telah mengupas tuntas arsitektur terdalam Spring Boot 3.x:
1.  **Arsitektur Siklus Hidup**: Pemahaman presisi terhadap pemisahan fase *Environment Prepared*, *BeanFactoryPostProcessor* (operasi metadata `BeanDefinition`), *BeanPostProcessor* (modifikasi instance runtime & dynamic proxying), hingga *ApplicationContext Refresh*.
2.  **Mekanisme Auto-Configuration SPI**: Transisi fundamental ke file `org.springframework.boot.autoconfigure.AutoConfiguration.imports`, perancangan filter kondisi deterministik via `@ConditionalOn*`, dan kontrol ordering dependensi.
3.  **Kesiapan Arsitektur Modern**: Pemanfaatan Java 21 Virtual Threads yang menuntut mitigasi *thread pinning*, pemangkasan dependensi untuk optimasi footprint Metaspace, serta jalur integrasi AOT GraalVM Native Image untuk latensi startup ultra-rendah.

Pemahaman mendalam mengenai arsitektur internal ini menjadi prasyarat esensial sebelum melangkah ke **Module 03**, yang akan membahas integrasi data tingkat lanjut, optimasi koneksi database, dan rekayasa transaksi terdistribusi.