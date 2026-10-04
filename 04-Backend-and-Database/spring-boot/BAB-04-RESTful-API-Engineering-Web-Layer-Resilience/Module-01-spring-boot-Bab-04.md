# Modul 01: RESTful API Engineering & Web Layer Resilience

---

## 01. IDENTITAS MODUL
* **Track:** Backend & Database
* **Domain:** Spring Boot Engineering
* **Level:** Intermediate to Advanced
* **Estimasi Waktu Selesai:** 4 Jam
* **Prasyarat:** Pemahaman Java 21 LTS, Spring Framework Core (Inversion of Control, Dependency Injection), Maven, serta dasar-dasar arsitektur HTTP/1.1 dan HTTP/2.

---

## 02. LEARNING OBJECTIVES
Pada akhir modul ini, peserta didik diharapkan mampu:
1. Merancang API Web Layer berbasis Spring MVC 6.x dan Spring Boot 3.x yang sepenuhnya mematuhi standar RFC 9110 (HTTP Semantics) dan RFC 7807/9457 (Problem Details for HTTP APIs).
2. Mengimplementasikan validasi request terstruktur menggunakan Jakarta Validation Framework (JSR 380) beserta custom validation constraints.
3. Membangun penanganan eksepsi terpusat (*Centralized Exception Handling*) berbasis `@RestControllerAdvice` yang memisahkan boundary domain dari protokol transport.
4. Menerapkan pola ketahanan web layer (*resilience patterns*) seperti Rate Limiting (Token Bucket), Circuit Breaker, dan Timeout handling menggunakan Resilience4j.
5. Membangun dan mengeksekusi automated tests untuk Web Layer menggunakan MockMvc dan WebTestClient secara deterministik.

---

## 03. CONCEPT MAP DIAGRAM ASCII

```
                       [ Incoming HTTP Request ]
                                   │
                                   ▼
                   [ Filter Chain: Security & RateLimit ]
                                   │
                     (Blocked? 429 Too Many Requests)
                                   │ Allowed
                                   ▼
                   [ DispatcherServlet (Spring Web) ]
                                   │
                                   ▼
           [ HandlerInterceptor / Content Negotiation ]
                                   │
                                   ▼
              [ Controller: @RestController Endpoint ]
                                   │
                 ┌─────────────────┴─────────────────┐
                 │ Jakarta Validation (@Valid DTO)   │
                 └─────────────────┬─────────────────┘
                                   │
                 (Invalid? 400 Bad Request via @RestControllerAdvice)
                                   │ Valid Payload
                                   ▼
          [ Domain/Service Layer with Resilience4j Decorators ]
                 │
                 ├──> [ CircuitBreaker (State: CLOSED/OPEN) ]
                 ├──> [ RateLimiter / Bulkhead ]
                 └──> [ Retry Mechanism ]
                                   │
            (Throws Exception? 5xx / 4xx RFC 9457 ProblemDetail)
                                   │ Success
                                   ▼
              [ ResponseEntity<T> Serialization (JSON) ]
                                   │
                                   ▼
                       [ HTTP Response Output ]
```

---

## 04. MENGAPA RELEVAN
Web Layer adalah gerbang masuk (*entry point*) utama dari setiap request eksternal yang menuju ke ekosistem backend. Di lingkungan production, lapisan ini menghadapi ancaman nyata: degradasi performa akibat lonjakan traffic tiba-tiba (*traffic spikes*), payload request yang terfragmentasi atau berbahaya (*malicious/malformed payloads*), dan cascading failures saat layanan hilir (*downstream dependencies*) mengalami kelambatan (*latency degradation*).

Mengandalkan implementasi dasar `@Controller` tanpa mekanisme ketahanan (resilience), standarisasi penanganan galat (*error handling*), dan validasi yang ketat akan mengakibatkan kebocoran detail internal sistem (*stack traces leak*), kehabisan resource (*thread pool exhaustion*), dan kegagalan sistem secara menyeluruh. Penguasaan arsitektur Web Layer modern menjamin API yang dapat diandalkan, aman, terukur, dan mematuhi spesifikasi industri.

---

## 05. ANATOMI KONSEP INTI

### 1. Spring MVC Architecture & DispatcherServlet Pipeline
Spring Web MVC berpusat pada `DispatcherServlet`, sebuah implementasi pola *Front Controller*. Alur pemrosesan request melewati tahapan:
- `HandlerMapping`: Mengidentifikasi controller target berdasarkan URI, HTTP Method, dan Headers.
- `HandlerAdapter`: Menjembatani eksekusi method controller menggunakan argument resolvers dan return value handlers.
- `HttpMessageConverter`: Melakukan serialisasi dan deserialisasi payload (misalnya Jackson untuk JSON).

### 2. RFC 9457 / RFC 7807 (Problem Details for HTTP APIs)
Format standar yang diintegrasikan langsung pada Spring Boot 3.x melalui kelas `org.springframework.http.ProblemDetail`. Struktur standar ini memuat:
- `type`: URI yang mengidentifikasi tipe masalah.
- `title`: Deskripsi singkat yang mudah dipahami manusia.
- `status`: HTTP Status Code.
- `detail`: Penjelasan mendalam mengenai kasus kegagalan spesifik.
- `instance`: URI referensi request yang menyebabkan galat.

### 3. Jakarta Bean Validation (JSR 380)
Validasi deklaratif langsung pada model domain transfer (DTO). Menggunakan anotasi seperti `@NotNull`, `@Size`, `@Pattern`, `@DecimalMin`, atau custom constraint validator. Eksekusi validasi dipicu melalui `@Valid` atau `@Validated`.

### 4. Web Layer Resilience (Resilience4j)
Mekanisme pertahanan level aplikasi untuk menjaga stabilitas memori dan worker thread:
- **Rate Limiting:** Mengatur batas konsumsi throughput request per client/IP menggunakan algoritma Token Bucket.
- **Circuit Breaker:** Memutus panggilan ke dependency yang gagal secara terus-menerus untuk mencegah cascading failure.
- **Time Limiter:** Menetapkan batas waktu maksimum eksekusi thread request non-blocking.

---

## 06. PANDUAN IMPLEMENTASI STEP-BY-STEP

### Langkah 1: Inisialisasi Dependensi Maven
Gunakan Java 21 dan Spring Boot 3.3.x. Tambahkan dependency `spring-boot-starter-web`, `spring-boot-starter-validation`, dan `resilience4j-spring-boot3`.

### Langkah 2: Mengaktifkan Standar Problem Details
Konfigurasikan `application.yml` untuk memancarkan standar ProblemDetail secara otomatis:
```yaml
spring:
  mvc:
    problemdetails:
      enabled: true
```

### Langkah 3: Perancangan Data Transfer Object (DTO) Imutabel
Gunakan Java 21 `record` untuk memastikan imutabilitas data dan deklarasi validasi yang eksplisit.

### Langkah 4: Pembuatan Custom Constraint Validation
Buat anotasi validasi khusus dan kelas validator yang mengimplementasikan `ConstraintValidator<A, T>`.

### Langkah 5: Implementasi Global Exception Handling
Bangun kelas penanganan eksepsi berbasis `@RestControllerAdvice` yang mewarisi `ResponseEntityExceptionHandler`.

### Langkah 6: Konfigurasi Resilience4j Web Resilience
Definisikan rate limiter dan circuit breaker pada level Service/Web boundary via configuration file.

---

## 07. CONTOH KASUS SEDERHANA

Berikut contoh dasar pendefinisian DTO request dan validasi sederhana pada controller:

```java
package com.alamsyah.api.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Positive;
import java.math.BigDecimal;

public record SimpleProductRequest(
    @NotBlank(message = "Nama produk tidak boleh kosong")
    String name,
    
    @Positive(message = "Harga harus bernilai positif")
    BigDecimal price
) {}
```

```java
package com.alamsyah.api.controller;

import com.alamsyah.api.dto.SimpleProductRequest;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/simple-products")
public class SimpleProductController {

    @PostMapping
    public ResponseEntity<SimpleProductRequest> createProduct(@Valid @RequestBody SimpleProductRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED).body(request);
    }
}
```

---

## 08. IMPLEMENTASI PRODUCTION-GRADE LENGKAP KODE

Berikut adalah arsitektur produksi sistem pemrosesan transaksi pembayaran (*Payment Processing System*) yang mencakup validation custom, error handling RFC 9457 terpadu, dan pertahanan web layer.

### 1. File: `pom.xml`
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
    <groupId>com.alamsyah</groupId>
    <artifactId>resilient-web-api</artifactId>
    <version>1.0.0-STABLE</version>
    <name>resilient-web-api</name>
    <properties>
        <java.version>21</java.version>
        <resilience4j.version>2.2.0</resilience4j.version>
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
            <groupId>io.github.resilience4j</groupId>
            <artifactId>resilience4j-spring-boot3</artifactId>
            <version>${resilience4j.version}</version>
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

### 2. File: `src/main/resources/application.yml`
```yaml
server:
  port: 8080
  shutdown: graceful

spring:
  threads:
    virtual:
      enabled: true
  mvc:
    problemdetails:
      enabled: true

resilience4j:
  ratelimiter:
    instances:
      paymentApiRateLimiter:
        limitForPeriod: 5
        limitRefreshPeriod: 1s
        timeoutDuration: 0ms
  circuitbreaker:
    instances:
      paymentGatewayCircuitBreaker:
        slidingWindowType: COUNT_BASED
        slidingWindowSize: 10
        minimumNumberOfCalls: 5
        failureRateThreshold: 50
        waitDurationInOpenState: 10s
        permittedNumberOfCallsInHalfOpenState: 3
        automaticTransitionFromOpen