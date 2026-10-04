# Kurikulum Enterprise: Spring Boot 3.x & Java 21
## Kategori: 04-Backend-and-Database
### BAB 04: RESTful API Engineering & Web Layer Resilience
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Principal/Staff Engineer dan Lead Backend Developer diharapkan mampu:
1. **Menganalisis dan Membedah Internal Spring MVC**: Menguasai siklus hidup request pada `DispatcherServlet`, rantai kerja `HandlerMapping`, `HandlerAdapter`, `HandlerMethodArgumentResolver`, `HandlerMethodReturnValueHandler`, serta ekosistem `HttpMessageConverter`.
2. **Merancang Layer Web Resilien Berkecepatan Tinggi**: Mengimplementasikan *pattern* ketahanan (*resilience*) seperti *Rate Limiting* berbasis Token Bucket (Bucket4j/Redis), *Circuit Breaking*, *Bulkhead*, dan *Timeout Budgeting* langsung pada batas Web Layer.
3. **Mengoptimalkan Concurrency Model Modern**: Mengonfigurasi dan memanfaatkan Java 21 Virtual Threads (Project Loom) pada embedded Apache Tomcat untuk mencapai throughput masif tanpa kompleksitas pemrograman reaktif.
4. **Menerapkan Standar Produksi Enterprise**: Mengisolasi kegagalan runtime menggunakan RFC 9457/7807 *Problem Details*, standarisasi payload audit kontekstual via MDC (*Mapped Diagnostic Context*), dan custom argument resolution untuk metadata perbankan/fintech.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
*   **Java 21 Core**: *Records*, *Pattern Matching*, *Sealed Classes*, dan konsep *Virtual Threads* (`Thread.ofVirtual()`).
*   **Spring Boot Fundamentals**: Dependency Injection, Auto-configuration, Spring Bean Lifecycle.
*   **Protokol HTTP/1.1 & HTTP/2**: Header propagation, status codes, keep-alive semantics, dan streaming payload.
*   **Tooling**: Maven/Gradle, Docker, Apache JMeter / `k6` untuk profiling throughput, dan cURL/HTTPie.

---

### 3. Concept & Internal Architecture

#### 3.1 Anatomi DispatcherServlet dan Siklus Hidup Eksekusi Request
Pada Spring MVC, `DispatcherServlet` bertindak sebagai *Front Controller*. Request HTTP dari klien tidak langsung menuju `@RestController`, melainkan melalui alur pemrosesan berlapis yang sangat terstruktur:

```
[HTTP Request] 
      │
      ▼
[Tomcat Engine: StandardHostValve]
      │
      ▼
[SecurityFilterChain (Servlet Filters)]
      │
      ▼
[DispatcherServlet (doDispatch)]
      │
      ├── 1. HandlerMapping.getHandler() ──────► Mengembalikan HandlerExecutionChain
      │                                          (Berisi Handler + List<HandlerInterceptor>)
      │
      ├── 2. HandlerInterceptor.preHandle() ───► Eksekusi interceptor sebelum controller
      │
      ├── 3. HandlerAdapter.handle() ──────────► RequestMappingHandlerAdapter
      │       │
      │       ├── HandlerMethodArgumentResolver ─► Resolusi parameter (@RequestBody, @PathVariable)
      │       │                                    via HttpMessageConverter (Jackson)
      │       ▼
      │   [@RestController Method Invocation]  ──► Eksekusi logika bisnis / Service layer
      │       │
      │       └── HandlerMethodReturnValueHandler ─► Menangani output, trigger ResponseBodyAdvice
      │                                            dan HttpMessageConverter
      │
      ├── 4. HandlerInterceptor.postHandle() ──► Pasca eksekusi method (tidak terpanggil jika rest/error)
      │
      └── 5. processDispatchResult() ──────────► Exception Handling via HandlerExceptionResolver
              │                                  (Trigger @ExceptionHandler / ProblemDetails)
              ▼
         HandlerInterceptor.afterCompletion() ─► Pembersihan resource (MDC.clear(), dsb.)
```

#### 3.2 Java 21 Virtual Threads (Loom) vs Classic Platform Threads
Pada model arsitektur thread-per-request klasik:
*   Tomcat mengalokasikan satu **Platform Thread** (OS Thread) per koneksi masuk.
*   Batas thread pool (default 200) membatasi konkurensi. Jika Controller melakukan pemanggilan I/O lambat (database query, downstream REST call), platform thread akan masuk status *BLOCKED*, mengonsumsi ~1MB stack memory per thread dan menyebabkan *thread pool starvation*.

Dengan mengaktifkan Virtual Threads di Spring Boot 3.2+:
*   Tomcat mengikat incoming request ke **Virtual Thread**.
*   Ketika eksekusi masuk fase blocking I/O, JVM melepaskan (*unmount*) Virtual Thread dari *Carrier Thread* (OS Thread). Carrier thread bebas melayani Virtual Thread lain.
*   Begitu operasi I/O tuntas, JVM memasang kembali (*mount*) Virtual Thread ke Carrier Thread yang tersedia. Tidak diperlukan lagi arsitektur reaktif non-blocking (WebFlux) hanya demi skalabilitas I/O.

---

### 4. Why & What

| Dimensi | Pendekatan Naif (Default MVC) | Pendekatan Produksi Resilien (Enterprise) |
| :--- | :--- | :--- |
| **Penanganan Error** | Menangkap `Exception` generik, mengembalikan HTTP 500 mentah atau format custom acak. | RFC 9457/7807 `ProblemDetail` yang terstruktur, standar IETF, dilengkapi *trace-id* dan *error codes*. |
| **Isolasi Beban** | Tidak ada limitasi; lonjakan request melumpuhkan database pool dan downstream service. | Rate limiting per-tenant (Bucket4j/Redis) dan Circuit Breaker (Resilience4j) di Web Boundary. |
| **Resolusi Metadata** | Mengambil token/header manual di setiap controller (`@RequestHeader`). | Custom `HandlerMethodArgumentResolver` yang melakukan unpacking dan validasi kontekstual terisolasi. |
| **Model Threading** | Platform threads terbatas (Tomcat 200 worker threads). Resiko kehabisan thread saat latency downstream naik. | Virtual Threads (`spring.threads.virtual.enabled=true`) dengan throughput maksimal pada workload I/O-bound. |

---

### 5. How: Alur Kerja Validasi & Resilience Pipeline

Diagram berikut menunjukkan bagaimana incoming request diverifikasi, dilindungi, dan dikonversi sebelum masuk ke logic domain:

```
[Inbound Request]
       │
       ▼
[RateLimitingFilter] ──── (Token habis?) ───► [Return HTTP 429 Too Many Requests]
       │ (Token tersedia)
       ▼
[CorrelationIdFilter] ───► Injeksi X-Request-ID ke MDC & Response Header
       │
       ▼
[DispatcherServlet]
       │
       ▼
[Custom Argument Resolvers] ─── (Validasi signature/HMAC gagal) ──► [HTTP 401/403 ProblemDetail]
       │
       ▼
[Resilience4j Decorator] ───── (Circuit OPEN / Bulkhead Full) ────► [HTTP 503 Service Unavailable]
       │
       ▼
[Business Logic Controller]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional VVIP
Bayangkan Controller Anda adalah **Ruang Tamu VVIP (Business Lounge)**:
*   **Platform Thread (Klasik)**: Mirip menyediakan 1 mobil limusin khusus beserta supirnya untuk setiap tamu dari pintu gerbang bandara hingga duduk di lounge. Jika tamu berhenti membaca koran selama 2 jam, supir dan limusin menganggur menunggu di tempat, tidak bisa dipakai tamu lain. Kapasitas bandara dibatasi jumlah limusin.
*   **Virtual Thread (Modern)**: Tamu diberikan gelang pintar. Ketika tamu berjalan, eskalator membawanya. Ketika tamu berhenti membaca, eskalator tetap berjalan melayani orang lain. Begitu tamu siap melangkah lagi, eskalator berikutnya langsung menyambutnya.
*   **Bucket4j (Rate Limiter)**: Pintu putar otomatis di gerbang masuk. Hanya mengizinkan 10 orang per menit. Sisanya disuruh menunggu di luar sebelum memadati koridor.
*   **Circuit Breaker**: Sakelar otomatis pada jembatan penyeberangan (*aerobridge*). Jika jembatan bergoyang/rusak (downstream service error), pintu jembatan langsung dikunci dari dalam agar penumpang tidak melangkah ke jurang, dan penumpang langsung diarahkan ke pintu darurat (*fallback*).

---

### 7. Implementation: Simple vs Practical Example

#### 7.1 Setup Maven Dependencies (`pom.xml`)
Gunakan dependensi modern Spring Boot 3.3.x / 3.4.x:

```xml
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
        <groupId>com.bucket4j</groupId>
        <artifactId>bucket4j-core</artifactId>
        <version>8.10.1</version>
    </dependency>
    <dependency>
        <groupId>io.github.resilience4j</groupId>
        <artifactId>resilience4j-spring-boot3</artifactId>
        <version>2.2.0</version>
    </dependency>
</dependencies>
```

Konfigurasi `application.yml` untuk mengaktifkan Virtual Threads:
```yaml
server:
  port: 8080
  tomcat:
    threads:
      max: 200 # Tetap ada sebagai boundary, namun diabaikan jika virtual threads aktif
spring:
  threads:
    virtual:
      enabled: true # Mengaktifkan Virtual Threads untuk Tomcat & Async task execution

resilience4j:
  circuitbreaker:
    instances:
      paymentGatewayCircuit:
        slidingWindowSize: 20
        failureRateThreshold: 50
        waitDurationInOpenState: 10000ms
        permittedNumberOfCallsInHalfOpenState: 5
```

#### 7.2 Custom Argument Resolver: Mengurai Konteks Enterprise
Alih-alih mengurai identitas client manual di controller, buat annotasi `@ClientContext` dan implementasikan resolver-nya.

```java
package com.enterprise.web.annotation;

import java.lang.annotation.*;

@Target(ElementType.PARAMETER)
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface AuthenticatedClient {
}
```

```java
package com.enterprise.web.model;

public record ClientMetadata(
    String clientId,
    String tenantId,
    String clientIp,
    String correlationId
) {}
```

```java
package com.enterprise.web.resolver;

import com.enterprise.web.annotation.AuthenticatedClient;
import com.enterprise.web.model.ClientMetadata;
import org.springframework.core.MethodParameter;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;
import org.springframework.web.server.ResponseStatusException;

@Component
public class ClientMetadataArgumentResolver implements HandlerMethodArgumentResolver {

    private static final String HEADER_CLIENT_ID = "X-Client-Id";
    private static final String HEADER_TENANT_ID = "X-Tenant-Id";
    private static final String HEADER_CORRELATION_ID = "X-Correlation-Id";

    @Override
    public boolean supportsParameter(MethodParameter parameter) {
        return parameter.hasParameterAnnotation(AuthenticatedClient.class) 
            && parameter.getParameterType().equals(ClientMetadata.class);
    }

    @Override
    public Object resolveArgument(
            MethodParameter parameter,
            ModelAndViewContainer mavContainer,
            NativeWebRequest webRequest,
            WebDataBinderFactory binderFactory) {

        String clientId = webRequest.getHeader(HEADER_CLIENT_ID);
        String tenantId = webRequest.getHeader(HEADER_TENANT_ID);
        String correlationId = webRequest.getHeader(HEADER_CORRELATION_ID);
        String remoteAddr = webRequest.getNativeRequest(jakarta.servlet.http.HttpServletRequest.class)
                .getRemoteAddr();

        if (clientId == null || clientId.isBlank() || tenantId == null || tenantId.isBlank()) {
            throw new ResponseStatusException(
                HttpStatus.UNAUTHORIZED, 
                "Kredensial header X-Client-Id atau X-Tenant-Id wajib disertakan."
            );
        }

        return new ClientMetadata(clientId, tenantId, remoteAddr, correlationId);
    }
}
```

#### 7.3 Interceptor & Rate Limiting Web-Layer (Bucket4j)
Mekanisme proteksi request menggunakan Token Bucket algorithm di level Servlet Interceptor.

```java
package com.enterprise.web.interceptor;

import io.github.bucket4j.Bandwidth;
import io.github.bucket4j.Bucket;
import io.github.bucket4j.Refill;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Component
public class RateLimitingInterceptor implements HandlerInterceptor {

    private final Map<String, Bucket> cache = new ConcurrentHashMap<>();

    private Bucket createNewBucket() {
        // Limit: 50 request per menit per Client-Id
        Refill refill = Refill.greedy(50, Duration.ofMinutes(1));
        Bandwidth limit = Bandwidth.classic(50, refill);
        return Bucket.builder().addLimit(limit).build();
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        String clientId = request.getHeader("X-Client-Id");
        
        // Lewati jika request internal/health check
        if (request.getRequestURI().startsWith("/actuator")) {
            return true;
        }

        if (clientId == null || clientId.isBlank()) {
            // Biarkan ArgumentResolver yang melempar exception spesifik jika lolos
            return true;
        }

        Bucket bucket = cache.computeIfAbsent(clientId, k -> createNewBucket());

        if (bucket.tryConsume(1)) {
            return true;
        } else {
            response.setStatus(HttpStatus.TOO_MANY_REQUESTS.value());
            response.setContentType("application/json");
            response.setHeader("X-Rate-Limit-Retry-After-Seconds", "60");
            response.getWriter().write("""
                {
                    "type": "https://api.enterprise.com/errors/rate-limit-exceeded",
                    "title": "Terlalu Banyak Permintaan",
                    "status": 429,
                    "detail": "Kapasitas request untuk client ini telah terlampaui. Coba lagi nanti."
                }
                """);
            return false;
        }
    }
}
```

#### 7.4 Registrasi WebMvcConfigurer

```java
package com.enterprise.web.config;

import com.enterprise.web.interceptor.RateLimitingInterceptor;
import com.enterprise.web.resolver.ClientMetadataArgumentResolver;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.List;

@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    private final RateLimitingInterceptor rateLimitingInterceptor;
    private final ClientMetadataArgumentResolver clientMetadataArgumentResolver;

    public WebMvcConfig(
            RateLimitingInterceptor rateLimitingInterceptor,
            ClientMetadataArgumentResolver clientMetadataArgumentResolver) {
        this.rateLimitingInterceptor = rateLimitingInterceptor;
        this.clientMetadataArgumentResolver = clientMetadataArgumentResolver;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(rateLimitingInterceptor)
                .addPathPatterns("/api/**");
    }

    @Override
    public void addArgumentResolvers(List<HandlerMethodArgumentResolver> resolvers) {
        resolvers.add(clientMetadataArgumentResolver);
    }
}
```

#### 7.5 Enterprise Exception Handler (RFC 9457 Problem Details)

```java
package com.enterprise.web.exception;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.server.ResponseStatusException;

import java.net.URI;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

@RestControllerAdvice
public class GlobalResilienceExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalResilienceExceptionHandler.class);

    @ExceptionHandler(ResponseStatusException.class)
    public ProblemDetail handleResponseStatusException(ResponseStatusException ex) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(ex.getStatusCode(), ex.getReason());
        problem.setType(URI.create("https://api.enterprise.com/errors/http-error"));
        problem.setTitle("Permintaan Gagal Diproses");
        problem.setProperty("timestamp", Instant.now());
        problem.setProperty("traceId", MDC.get("X-Correlation-Id"));
        return problem;
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ProblemDetail handleValidationException(MethodArgumentNotValidException ex) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, "Payload request tidak lolos validasi.");
        problem.setType(URI.create("https://api.enterprise.com/errors/validation-failed"));
        problem.setTitle("Validasi Error");

        Map<String, String> fieldErrors = new HashMap<>();
        ex.getBindingResult().getFieldErrors().forEach(error -> 
            fieldErrors.put(error.getField(), error.getDefaultMessage())
        );

        problem.setProperty("invalidFields", fieldErrors);
        problem.setProperty("timestamp", Instant.now());
        problem.setProperty("traceId", MDC.get("X-Correlation-Id"));
        return problem;
    }

    @ExceptionHandler(Exception.class)
    public ProblemDetail handleGenericException(Exception ex) {
        log.error("Unhandled system failure detected: ", ex);
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(
                HttpStatus.INTERNAL_SERVER_ERROR, 
                "Terjadi anomali pada sistem internal. Silakan hubungi support dengan menyertakan Trace ID."
        );
        problem.setType(URI.create("https://api.enterprise.com/errors/internal-server-error"));
        problem.setTitle("Internal Server Error");
        problem.setProperty("timestamp", Instant.now());
        problem.setProperty("traceId", MDC.get("X-Correlation-Id"));
        return problem;
    }
}
```

#### 7.6 Controller Resilien Produksi

```java
package com.enterprise.web.controller;

import com.enterprise.web.annotation.AuthenticatedClient;
import com.enterprise.web.model.ClientMetadata;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/payments")
public class PaymentController {

    public record PaymentRequest(
        @NotBlank(message = "Akun tujuan transfer wajib diisi")
        String destinationAccount,

        @NotNull(message = "Nominal pembayaran wajib diisi")
        @DecimalMin(value = "10000.00", message = "Minimum transfer adalah IDR 10,000.00")
        BigDecimal amount,

        @NotBlank(message = "Idempotency key wajib disertakan")
        String idempotencyKey
    ) {}

    public record PaymentResponse(
        String transactionId,
        String status,
        String destinationAccount,
        BigDecimal amount,
        String processedByTenant
    ) {}

    @PostMapping
    @CircuitBreaker(name = "paymentGatewayCircuit", fallbackMethod = "executeFallbackPayment")
    public ResponseEntity<PaymentResponse> processPayment(
            @AuthenticatedClient ClientMetadata client,
            @Valid @RequestBody PaymentRequest request) {

        // Simulasi latensi eksekusi I/O downstream (Virtual Thread akan unmount secara efisien)
        try {
            Thread.sleep(150); 
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }

        // Return model respon standar industri
        return ResponseEntity.ok(new PaymentResponse(
                UUID.randomUUID().toString(),
                "SUCCESS",
                request.destinationAccount(),
                request.amount(),
                client.tenantId()
        ));
    }

    // Fallback signature wajib mencocokkan signature controller + Exception parameter di akhir
    public ResponseEntity<PaymentResponse> executeFallbackPayment(
            ClientMetadata client, 
            PaymentRequest request, 
            Throwable t) {
        
        return ResponseEntity.status(503).body(new PaymentResponse(
                "N/A",
                "DEGRADED_MODE: Sistem switching sedang sibuk, transaksi Anda masuk antrean rekonsiliasi.",
                request.destinationAccount(),
                request.amount(),
                client.tenantId()
        ));
    }
}
```

---

### 8. Real World Case Study: Open Banking API Gateway (BI-FAST Gateway Engine)

#### Konteks & Latar Belakang
Bank Swasta Nasional mengintegrasikan sistemnya ke infrastruktur BI-FAST nasional. Gateway API menerima lonjakan transaksi hingga 15.000 TPS saat jam sibuk (pukul 09:00 - 11:00 WIB). Downstream core-banking memiliki SLA response time 300ms, namun dapat terdegradasi menjadi 4.000ms saat proses *end-of-day* parsial berlangsung.

#### Masalah
1. **Thread Exhaustion**: Tomcat default kehabisan thread (200 threads jenuh dalam hitungan detik) saat downstream melambat, menyebabkan seluruh domain API lain (seperti pengecekan mutasi dan login) ikut *hang* (Cascading Failure).
2. **Cascading Retry Storm**: Channel mobile banking mengirimkan retry otomatis setiap 2 detik karena timeout tidak terkontrol, melipatgandakan beban downstream hingga mati total.

#### Solusi Arsitektur
1. **Penerapan Spring Boot 3 + Java 21 Virtual Threads**: Menghapus limitasi platform thread pada Tomcat. Konkurensi 15.000 request ditangani oleh Virtual Threads dengan footprint memory hanya ~150MB stack memory (dibandingkan ~15GB jika menggunakan platform threads).
2. **Circuit Breaker & Bulkhead via Resilience4j**: Batas konkurensi menuju downstream core-banking diatur maksimal 2.000 panggilan simultan. Jika rasio error melebihi 40% dalam window 5 detik, Circuit Breaker langsung masuk status **OPEN**, langsung mengembalikan RFC 9457 `ProblemDetail` (HTTP 503) dalam 2ms tanpa menyentuh core-banking.
3. **Idempotency Interceptor**: Mencegah double-debit akibat network retry dengan validasi Redis lock berbasis header `Idempotency-Key` sebelum `DispatcherServlet` mengeksekusi controller.

---

### 9. Trade-offs

| Opsi Arsitektur | Keuntungan | Biaya & Kompensasi (Trade-offs) |
| :--- | :--- | :--- |
| **Virtual Threads (Loom)** | Pemrograman tetap imperatif, mudah di-debug, skalabilitas konkurensi I/O mendekati Reactive. | Tidak mempercepat kalkulasi intensif CPU (CPU-bound). Hati-hati dengan *Thread Pinning* jika menggunakan `synchronized` block lama (ganti dengan `ReentrantLock`). |
| **Servlet Filter vs Interceptor Rate Limiting** | Filter mencegat request lebih awal sebelum Spring Context memproses argument. Interceptor memiliki akses langsung ke method handler (`Object handler`). | Filter mengeksekusi request di luar kontrol handler abstraction Spring, menyulitkan pengecualian path controller secara dinamis berbasis anotasi. |
| **WebFlux (Reactive) vs Virtual Threads (MVC)** | Dukungan native backpressure stream di level socket network (Netty). | Kompleksitas tinggi (kode sulit di-debug, stack trace terfragmentasi), curva belajar tim sangat tinggi. |

---

### 10. Common Mistakes & Troubleshooting

#### Kasus 1: Thread Pinning pada Java 21 Virtual Threads
*   **Gejala**: Throughput anjlok saat beban tinggi, memory naik drastis, Virtual Threads tidak ter-unmount.
*   **Akar Masalah**: Pustaka legacy menggunakan blok `synchronized (lock)` saat melakukan I/O blocking. Ini menyebabkan Virtual Thread "terpaku" (*pinned*) ke Platform Carrier Thread, melumpuhkan scheduler Loom.
*   **Deteksi**: Jalankan JVM dengan flag diagnostik:
    ```bash
    -Djdk.tracePinnedThreads=full
    ```
*   **Solusi**: Ganti blok `synchronized` dengan `java.util.concurrent.locks.ReentrantLock`.

#### Kasus 2: Memory Leak pada MDC / ThreadLocal
*   **Gejala**: Trace ID transaksi nasabah A bocor dan tertulis pada log transaksi nasabah B.
*   **Akar Masalah**: Virtual thread atau thread pool Tomcat menggunakan kembali (*reuse*) thread yang sama tanpa membersihkan thread context. Interceptor tidak mengimplementasikan method `afterCompletion()`.
*   **Solusi**:
    ```java
    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response, Object handler, Exception ex) {
        MDC.clear(); // WAJIB DIJALANKAN DI SINI
    }
    ```

#### Kasus 3: Fallback Method Resilience4j Tidak Terpanggil
*   **Gejala**: Terjadi error `NoSuchMethodException` saat fallback dipicu.
*   **Akar Masalah**: Tanda tangan parameter (*parameter signature*) method fallback tidak persis sama dengan method target, atau tidak menyertakan parameter `Throwable` di urutan terakhir.

---

### 11. Best Practices (Production Checklist)

- [ ] Aktifkan `spring.threads.virtual.enabled=true` di environment Java 21+.
- [ ] Implementasikan standar IETF RFC 9457 untuk semua respons error HTTP menggunakan `ProblemDetail`.
- [ ] Bersihkan semua `ThreadLocal` dan `MDC` di dalam blok `afterCompletion()` pada interceptor.
- [ ] Terapkan `server.servlet.encoding.force=true` dan validasi encoding UTF-8 secara ketat.
- [ ] Atur HTTP Keep-Alive dan Timeout eksplisit pada level server container:
  ```yaml
  server:
    tomcat:
      connection-timeout: 20000ms
      keep-alive-timeout: 15000ms
      max-keep-alive-requests: 1000
  ```
- [ ] Lakukan isolasi failover menggunakan Circuit Breaker di layer terluar integrasi eksternal.
- [ ] Definisikan DTO request/response menggunakan Java 21 `record` untuk immutability absolut dan efisiensi memori.
- [ ] Jangan mengekspos internal stack trace ke response HTTP produksi (nonaktifkan `server.error.include-stacktrace: never`).
- [ ] Terapkan header idempotensi (`Idempotency-Key`) untuk semua method `POST` dan `PATCH` transaksional finansial.

---

### 12. Hands-on Practice

Buatlah implementasi project terstruktur pada direktori `hands-on/m02/`.

#### Langkah 1: Struktur Proyek
```text
hands-on/m02/
├── pom.xml
└── src/
    └── main/
        ├── java/
        │   └── com/enterprise/resilience/
        │       ├── ResilienceApplication.java
        │       ├── controller/
        │       │   └── OrderController.java
        │       ├── filter/
        │       │   └── CorrelationMdcFilter.java
        │       ├── interceptor/
        │       │   └── TokenBucketRateLimiterInterceptor.java
        │       ├── resolver/
        │       │   └── TenantHeaderArgumentResolver.java
        │       └── exception/
        │           └── GlobalExceptionHandler.java
        └── resources/
            └── application.yml
```

#### Langkah 2: Mengimplementasikan Correlation Filter
Simpan di `src/main/java/com/enterprise/resilience/filter/CorrelationMdcFilter.java`:

```java
package com.enterprise.resilience.filter;

import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.UUID;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class CorrelationMdcFilter implements Filter {

    public static final String CORRELATION_HEADER = "X-Correlation-Id";

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        
        HttpServletRequest httpRequest = (HttpServletRequest) request;
        HttpServletResponse httpResponse = (HttpServletResponse) response;

        String correlationId = httpRequest.getHeader(CORRELATION_HEADER);
        if (correlationId == null || correlationId.isBlank()) {
            correlationId = UUID.randomUUID().toString();
        }

        MDC.put(CORRELATION_HEADER, correlationId);
        httpResponse.setHeader(CORRELATION_HEADER, correlationId);

        try {
            chain.doFilter(request, response);
