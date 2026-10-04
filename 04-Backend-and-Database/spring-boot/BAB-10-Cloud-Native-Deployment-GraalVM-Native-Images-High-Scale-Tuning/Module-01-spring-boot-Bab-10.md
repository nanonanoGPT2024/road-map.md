# Module 01: Cloud-Native Deployment, GraalVM Native Images, & High-Scale Tuning

---

## 01. Identitas Modul
* **Track:** Backend and Database Engineering
* **Kategori:** 04-Backend-and-Database
* **Topik:** Spring Boot Enterprise Architecture
* **Bab:** 10 (Advanced Operations, Deployment, & Performance Optimization)
* **Modul:** 01
* **Level:** Advanced / Principal Engineer
* **Prasyarat:** Pemahaman mendalam tentang JVM Internals, Spring Boot 3.x, Linux Containers (Docker/OCI), Kubernetes primitives, dan reactive/non-blocking I/O concepts.

---

## 02. Learning Objectives
Setelah menyelesaikan modul ini, Anda akan mampu:
1. Memahami arsitektur Ahead-Of-Time (AOT) engine dan GraalVM Native Image compilation workflow pada Spring Boot 3.x.
2. Mengonfigurasi `RuntimeHints` dan `native-maven-plugin` untuk memecahkan Dynamic Reflection, Dynamic Proxy, Resource Loading, dan Serialization gaps saat kompilasi Native Image.
3. Mengemas aplikasi Spring Boot ke dalam distroless OCI container image yang aman dan berbobot minimal (<50MB) dengan cold startup time <50ms.
4. Mengonfigurasi Kubernetes Deployment spec secara presisif: CPU Request/Limit, Memory Limits, cgroups v2 dynamic tuning, Graceful Shutdown hooks, dan Custom Probes (Liveness/Readiness/Startup).
5. Menganalisis trade-off performa antara HotSpot C2 dynamic JIT compilation (peak throughput) vs GraalVM SubstrateVM AOT (fast startup, low RSS memory).
6. Mengimplementasikan JVM garbage collector tuning (G1GC vs ZGC vs Epsilon/Serial GC pada Native Image) untuk skenario beban konkurensi ekstrem.

---

## 03. Concept Map Diagram (ASCII)

```
+----------------------------------------------------------------------------------------------------+
|                               SPRING BOOT 3.x WORKLOAD DEPLOYMENT MATRIX                           |
+----------------------------------------------------------------------------------------------------+
                                                  |
                 +--------------------------------+--------------------------------+
                 |                                                                 |
                 v                                                                 v
   +---------------------------+                                     +---------------------------+
   |   HOTSPOT JVM DEPLOYMENT  |                                     |   GRAALVM NATIVE IMAGE    |
   +---------------------------+                                     +---------------------------+
   | * JIT Optimization (C2)   |                                     | * AOT (Ahead-Of-Time) Eng |
   | * Peak Raw Throughput     |                                     | * Instant Startup (<50ms) |
   | * Dynamic Class Loading   |                                     | * Minimal RSS (<80MB)     |
   | * High Memory Footprint   |                                     | * Closed-World Assumption |
   +---------------------------+                                     +---------------------------+
                 |                                                                 |
                 +--------------------------------+--------------------------------+
                                                  |
                                                  v
                   +---------------------------------------------------------------+
                   |                   OCI DISTROLESS CONTAINER                    |
                   |   - No Shell, No Package Manager, Non-Root UID (65532)        |
                   |   - cgroups v2 Awareness (OOMKilled prevention)               |
                   +---------------------------------------------------------------+
                                                  |
                                                  v
                   +---------------------------------------------------------------+
                   |             KUBERNETES HIGH-SCALE ORCHESTRATION               |
                   |   - Startup/Liveness/Readiness via Spring Actuator Probes     |
                   |   - Graceful Phase Termination (SIGTERM vs PreStop Hook)      |
                   |   - HPA Trigger: Custom Metrics (Prometheus / Micrometer)     |
                   +---------------------------------------------------------------+
```

---

## 04. Mengapa Relevan
Dalam arsitektur *cloud-native* modern, efisiensi resource infrastructure (finops), elastisitas auto-scaling (HPA), dan cold-start resilience menentukan keandalan serta biaya operasional sistem. 

JVM konvensional dengan HotSpot runtime memerlukan waktu kompilasi bertingkat (Tiered Compilation: C1/C2 JIT) dan memory warmup sebelum mencapai performa optimal. Hal ini menjadi hambatan fatal pada arsitektur Serverless (FaaS), transient worker jobs, dan autoscaling agresif ketika terjadi traffic spike mendadak. 

Sebaliknya, GraalVM Native Image melalui Spring Boot 3 AOT Engine memungkinkan eliminasi dead-code, pre-initializing classes, dan menghasilkan binary executable mandiri dengan konsumsi memory baseline yang sangat rendah serta startup time fraksi milidetik, tanpa mengorbankan keamanan type-safety ekosistem enterprise Java.

---

## 05. Anatomi Konsep Inti

### 1. Spring AOT Processing & Closed-World Assumption
GraalVM Substrate VM beroperasi di bawah prinsip **Closed-World Assumption**: semua bytecode yang akan dieksekusi saat runtime harus dapat diidentifikasi dan dianalisis selama fase build (Static Analysis).
* **Spring AOT Engine (`spring-core/aot`):** Berjalan pada fase kompilasi untuk mengevaluasi kondisi bean (`@ConditionalOnProperty`, dll.), menyusun metadata bean definition ke dalam kode Java reguler, dan menonaktifkan reflection engine Spring yang dinamis.
* **Reachability Metadata:** Komponen seperti dynamic class loading, JDK dynamic proxies, serialization, dan Java Native Interface (JNI) yang tidak terdeteksi oleh static analyzer harus didaftarkan secara eksplisit melalui file `reflect-config.json`, `proxy-config.json`, atau programmatic `RuntimeHintsRegistrar`.

### 2. Substrate VM Memory Model
Native image tidak berjalan di atas JVM standar, melainkan di atas Substrate VM yang tersemat langsung di dalam binary:
* **No Dynamic Bytecode Execution:** Tidak ada class loading dinamis.
* **Garbage Collector:** Secara default menggunakan *Serial GC* (dioptimalkan untuk footprint rendah) atau *G1GC* (tersedia di GraalVM Enterprise/Oracle GraalVM untuk latency rendah pada heap besar).

### 3. Container Resource Isolation: cgroups v2
Pada Linux Kernel 4.15+, cgroups v2 mengonsolidasikan hierarki alokasi resource:
* `cpu.max`: Menentukan quota CPU bandwidth period.
* `memory.max` & `memory.high`: Menentukan limit konsumsi fisik memory.
* JVM modern (JDK 17+) secara native mendeteksi cgroups v2, tetapi GraalVM native binary membutuhkan konfigurasi eksplisit flag heap (`-XX:MaxRAMPercentage`, `-Xmx`) agar tidak tereliminasi oleh Linux Out-Of-Memory (OOM) Killer.

---

## 06. Panduan Implementasi Step-by-Step

### Step 1: Konfigurasi Native Plugin pada `pom.xml`
Gunakan `native-maven-plugin` dari GraalVM Native Build Tools yang terintegrasi dengan Spring Boot 3.

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0" 
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.2.3</version>
        <relativePath/>
    </parent>
    
    <groupId>com.enterprise.cloudnative</groupId>
    <artifactId>native-highscale-service</artifactId>
    <version>1.0.0</version>
    
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
    </dependencies>
    
    <build>
        <plugins>
            <plugin>
                <groupId>org.graalvm.buildtools</groupId>
                <artifactId>native-maven-plugin</artifactId>
                <configuration>
                    <buildArgs>
                        <buildArg>-H:+ReportExceptionStackTraces</buildArg>
                        <buildArg>--no-fallback</buildArg>
                        <buildArg>--enable-http</buildArg>
                        <buildArg>--enable-https</buildArg>
                    </buildArgs>
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

### Step 2: Registrasi Programmatic Runtime Hints
Jika menggunakan third-party library yang memanfaatkan dynamic reflection (misalnya legacy payload reflection), deklarasikan `RuntimeHintsRegistrar`.

---

## 07. Contoh Kasus Sederhana: DTO Reflection Gaps

### Masalah
Third-party serialization library memanggil field DTO melalui dynamic string lookup yang tidak di-generate oleh standard Spring AOT inference engine.

### Solusi
Implementasikan `RuntimeHintsRegistrar` untuk mendaftarkan kelas DTO ke Native Static Analyzer.

```java
package com.enterprise.cloudnative.hints;

import com.enterprise.cloudnative.dto.LegacyOrderPayload;
import org.springframework.aot.hint.MemberCategory;
import org.springframework.aot.hint.RuntimeHints;
import org.springframework.aot.hint.RuntimeHintsRegistrar;

public class CustomPayloadHintsRegistrar implements RuntimeHintsRegistrar {
    @Override
    public void registerHints(RuntimeHints hints, ClassLoader classLoader) {
        hints.reflection().registerType(
            LegacyOrderPayload.class,
            MemberCategory.INVOKE_PUBLIC_CONSTRUCTORS,
            MemberCategory.INVOKE_PUBLIC_METHODS,
            MemberCategory.DECLARED_FIELDS
        );
    }
}
```

---

## 08. Implementasi Production-Grade Lengkap Kode

Berikut implementasi lengkap microservice high-scale yang memuat:
1. Production DTO & Service dengan Telemetry Micrometer.
2. Dynamic Runtime Hints registration.
3. Multi-stage Distroless Containerfile (Native Image build).
4. Kubernetes Deployment Specification dengan Zero-Downtime, cgroups limits, dan lifecycle hooks.

### 1. Spring Boot Application & Controller
```java
package com.enterprise.cloudnative;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.ImportRuntimeHints;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.Map;

@SpringBootApplication
@ImportRuntimeHints(com.enterprise.cloudnative.hints.CustomPayloadHintsRegistrar.class)
@RestController
@RequestMapping("/api/v1/orders")
public class HighScaleApplication {

    private final Counter orderCounter;

    public HighScaleApplication(MeterRegistry registry) {
        this.orderCounter = Counter.builder("business_orders_processed_total")
                .description("Total high-scale orders executed")
                .register(registry);
    }

    public static void main(String[] args) {
        SpringApplication.run(HighScaleApplication.class, args);
    }

    @PostMapping
    public ResponseEntity<Map<String, Object>> processOrder(@RequestBody OrderRequest request) {
        this.orderCounter.increment();
        return ResponseEntity.ok(Map.of(
                "orderId", request.orderId(),
                "status", "PROCESSED",
                "timestamp", Instant.now().toString(),
                "engine", System.getProperty("org.graalvm.nativeimage.imagecode") != null ? "GraalVM-Native" : "JVM-HotSpot"
        ));
    }
}

record OrderRequest(String orderId, String sku, int quantity) {}
```

### 2. Multi-Stage Distroless Dockerfile
```dockerfile
# syntax=docker/dockerfile:1.4
# Stage 1: Build Native Binary with Oracle GraalVM
FROM container-registry.oracle.com/graalvm/native-image:21-ol9 AS build-stage

WORKDIR /app
COPY .mvn/ .mvn
COPY mvnw pom.xml ./
RUN ./mvnw dependency:go-offline -B

COPY src ./src
RUN ./mvnw -Pnative native:compile -DskipTests

# Stage 2: Distroless Minimal Execution Layer
FROM gcr.io/distroless/cc-debian12:nonroot

WORKDIR /workspace
COPY --from=build-stage --chown=nonroot:nonroot /app/target/native-highscale-service /workspace/service

EXPOSE 8080 8081
USER nonroot:nonroot

ENTRYPOINT ["/workspace/service", "-Dspring.profiles.active=prod", "-XX:MaxRAMPercentage=75.0"]
```

### 3. Production Kubernetes Manifest (`deployment.yaml`)
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: highscale-order-service
  namespace: production
  labels:
    app.kubernetes.io/name: highscale-order-service
    app.kubernetes.io/part-of: e-commerce-engine
spec:
  replicas: 10
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%
      maxUnavailable: 0
  selector:
    matchLabels:
      app: highscale-order-service
  template:
    metadata:
      labels:
        app: highscale-order-service
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/path: "/actuator/prometheus"
        prometheus.io/port: "8081"
    spec:
      terminationGracePeriodSeconds: 45
      containers:
      - name: order-service
        image: internal-registry.enterprise.com/apps/order-service:1.0.0
        imagePullPolicy: IfNotPresent
        securityContext:
          readOnlyRootFilesystem: true
          runAsNonRoot: true
          runAsUser: 65532
          allowPrivilegeEscalation: false
          capabilities:
            drop:
              - ALL
        ports:
        - name: http
          containerPort: 8080
        - name: management
          containerPort: 8081
        resources:
          requests:
            cpu: "250m"
            memory: "96Mi"
          limits:
            cpu: "1000m"
            memory: "256Mi"
        env:
        - name: MANAGEMENT_SERVER_PORT
          value: "8081"
        - name: MANAGEMENT_ENDPOINTS_WEB_EXPOSURE_INCLUDE
          value: "health,prometheus,info"
        - name: MANAGEMENT_ENDPOINT_HEALTH_PROBES_ENABLED
          value: "true"
        - name: SERVER_SHUTDOWN
          value: "graceful"
        - name: SPRING_LIFECYCLE_TIMEOUT_PER_SHUTDOWN_PHASE
          value: "30s"
        startupProbe:
          httpGet:
            path: /actuator/health/liveness
            port: 8081
          initialDelaySeconds: 1
          periodSeconds: 2
          failureThreshold: 10
        livenessProbe:
          httpGet:
            path: /actuator/health/liveness
            port: 8081
          periodSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /actuator/health/readiness
            port: 8081
          periodSeconds: 3
          failureThreshold: 2
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sleep", "10"]
```

---

## 09. Diagram Alur Kerja (ASCII)

```
[Inbound Traffic] -> [Ingress/Service Mesh]
                            |
    +-----------------------+-----------------------+
    |                                               | (SIGTERM Sent by K8s)
    v                                               v
[Active Native Pod]                         [Terminating Native Pod]
    |                                               |
    |-- Serving Traffic                             |-- 1. Ingress updates endpoint slice (No new traffic)
    |                                               |-- 2. preStop Hook executes (sleep 10s)
    |                                               |-- 3. Spring initiates Graceful Shutdown
    |                                               |      - Stops accepting HTTP requests
    |                                               |      - Completes pending executions (Max: 30s)
    |                                               |-- 4. Native Substrate VM exits cleanly (Code 0)
```

---

## 10. Analisis Trade-offs

| Dimensi | HotSpot JVM (C2 JIT) | GraalVM Native Image (AOT) |
| :--- | :--- | :--- |
| **Startup Latency** | Lambat (2–15 detik) | Nyaris Instan (10–50 milidetik) |
| **Memory Baseline (RSS)** | Tinggi (256MB – 1GB+) | Sangat Rendah (30MB – 90MB) |
| **Peak Throughput** | Maksimal (Dynamic Profiling runtime optimizations) | Rendah ke Moderat (kecuali menggunakan PGO + G1 Enterprise) |
| **Build Time / CI Pipeline** | Cepat (1–2 menit) | Lambat & CPU Intensive (4–15 menit) |
| **Dynamic Capabilities** | Fleksibel (Dynamic bytecode, full reflection) | Ketat (Wajib AOT Hints, No dynamic class loading) |
| **Container Image Size** | 200MB – 450MB (Base JRE + Fat JAR) | 30MB – 60MB (Distroless Binary) |

---

## 11. Best Practices & Antipatterns

### Best Practices
* **Manfaatkan Profile-Guided Optimization (PGO):** Jika membutuhkan throughput setara JIT C2 pada native image, kumpulkan profil eksekusi beban produksi (`-XX:ProfileOutput`) dan compile ulang native image dengan data profil tersebut.
* **Gunakan Distroless Image:** Selalu jalankan binary native di atas image kosong tanpa OS shell (`gcr.io/distroless/cc-debian12`) untuk meminimalisasi CVE surface area.
* **Terapkan Graceful Termination Terkoordinasi:** Selalu sinkronkan `lifecycle.preStop.exec.sleep` Kubernetes dengan `spring.lifecycle.timeout-per-shutdown-phase` agar tidak ada koneksi HTTP yang terputus mendadak (*connection reset by peer*).

### Antipatterns
* **Mengandalkan Reflection Tanpa Dynamic Hints:** Menjalankan third-party JSON/XML parser lawas tanpa menguji execution path di Native Image, memicu `ClassNotFoundException` atau `NullPointerException` secara sporadis saat runtime.
* **Menyamakan JVM Flags HotSpot dengan SubstrateVM:** Menetapkan argumen JVM kompleks seperti `-XX:+UseCMSGC` atau parameter G1GC HotSpot ke dalam GraalVM Native Image binary yang dapat memicu kegagalan runtime startup.

---

## 12. Security Hardening

```
+-------------------------------------------------------------------------+
|                  CONTAINER SECURITY HARDENING BOUNDARY                  |
+-------------------------------------------------------------------------+
| [Layer 1] Distroless Container Base (No Shell, No Package Manager, No Coreutils)
| [Layer 2] Non-Root Execution (UID: 65532:nonroot)                       |
| [Layer 3] Linux Capabilities: DROP ALL (CapDrop=ALL)                     |
| [Layer 4] ReadOnlyRootFilesystem=true (Write locks applied to root)     |
| [Layer 5] Prevent Privilege Escalation (allowPrivilegeEscalation=false)  |
+-------------------------------------------------------------------------+
```

1. **Immutable File System:** Aktifkan `readOnlyRootFilesystem: true` pada Kubernetes security context. Binary native tidak membutuhkan write access ke OS root. Jika logging butuh scratch space, mount `emptyDir` ke `/tmp`.
2. **Minimal Static Binaries:** Mengeliminasi shell (`/bin/sh`, `/bin/bash`) mencegah eksekusi payload arbitrary command execution meskipun terdapat vulnerability Remote Code Execution (RCE) tingkat aplikasi.

---

## 13. Observabilitas & Debugging

### 1. Actuator Native Endpoints Configuration
Konfigurasikan ports terisolasi antara internal management metric dengan public HTTP traffic:

```properties
server.port=8080
management.server.port=8081
management.endpoints.web.exposure.include=health,prometheus,info
management.endpoint.health.probes.enabled=true
management.endpoint.health.show-details=always
```

### 2. Debugging Native Memory Leaks
Substrate VM tidak memiliki HotSpot tooling standar (seperti `jcmd` atau `jmap`). Diagnostik alokasi memory native dilakukan via Native Image tracing:
* Jalankan kompilasi dengan flag: `-H:+PrintAnalysisCallTree` dan `-H:+NativeImageTracer`.
* Pantau Linux OS level memory allocation menggunakan standard eBPF tools (`bcc/memleak` atau `valgrind`).

---

## 14. Benchmarking & Performance

Perbandingan performa startup dan memory footprint pada service yang sama:

```
Metric: Cold Startup Time (Milliseconds - Lower is Better)
HotSpot JVM: [========================================] 3,420 ms
GraalVM AOT: [=] 28 ms

Metric: Idle Memory Footprint / RSS (Megabytes - Lower is Better)
HotSpot JVM: [==============================] 285 MB
GraalVM AOT: [===] 34 MB

Metric: Peak Latency P99 Under Sustained Load (Milliseconds - Lower is Better)
HotSpot JVM: [==] 2.1 ms  (With JIT optimization)
GraalVM AOT: [====] 4.8 ms (Serial GC standard mode)
```

---

## 15. Hands-on Lab Mini-Project

### Skenario
Bangun pipeline kompilasi Native Image dan uji cold-start auto-scaling resilience menggunakan script testing.

### Instruksi Implementasi

1. **Generate Binary Native:**
   ```bash
   ./mvnw clean native:compile -Pnative
   ```
2. **Uji Jalankan Binary Lokal:**
   ```bash
   ./target/native-highscale-service
   ```
   *Perhatikan baris console log startup: `Started HighScaleApplication in 0.038 seconds (process running for 0.042)`.*

3. **Build & Tag OCI Container Image:**
   ```bash
   docker build -t highscale-order-service:1.0.0 .
   ```

4. **Eksekusi Stress Test Latency:**
   Gunakan tools load generator (seperti `k6` atau `hey`):
   ```bash
   hey -n 10000 -c 100 -m POST \
       -H "Content-Type: application/json" \
       -d '{"orderId":"ORD-999","sku":"SKU-X","quantity":2}' \
       http://localhost:8080/api/v1/orders
   ```

---

## 16. Automated Testing & Verification

Gunakan `@SpringBootTest` dengan mode AOT verification untuk memastikan bahwa semua context wiring valid di bawah constraint AOT processing.

```java
package com.enterprise.cloudnative;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class HighScaleApplicationTests {

    @Autowired
    private TestRestTemplate restTemplate;

    @Test
    void contextLoadsAndOrderEndpointResponds() {
        OrderRequest payload = new OrderRequest("TEST-123", "SKU-ABC", 5);
        ResponseEntity<String> response = restTemplate.postForEntity("/api/v1/orders", payload, String.class);
        
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).contains("PROCESSED");
        assertThat(response.getBody()).contains("TEST-123");
    }
}
```

---

## 17. Troubleshooting Guide

| Gejala Masalah | Akar Masalah (Root Cause) | Solusi Perbaikan |
| :--- | :--- | :--- |
| `ClassNotFoundException` atau `NoSuchMethodException` saat Native execution | Class dynamic lookup tidak terdaftar pada AOT build phase. | Definisikan `RuntimeHintsRegistrar` untuk mendaftarkan kelas/metode ke metadata reflection. |
| Pod terkena status `OOMKilled` (Exit Code 137) pada Kubernetes | Native image mengalokasikan memory melebihi `resources.limits.memory`. Substrate VM heap default dapat mengonsumsi physical host capacity. | Tambahkan flag `-XX:MaxRAMPercentage=75.0` atau tentukan hard limit `-Xmx<value>` pada Entrypoint. |
| HTTP 502 / 503 saat deployment rolling update | Pod dimatikan seketika oleh Kubernetes sebelum load balancer / service mesh memperbarui routing table. | Terapkan `lifecycle.preStop.exec` dengan command `sleep 10` dan pastikan `server.shutdown=graceful`. |
| Kompilasi native build gagal karena Memory Exhaustion (Out of Memory) | GraalVM Native Image compiler membutuhkan minimal 8–16GB RAM fisik selama proses Static Analysis. | Tingkatkan allocated swap/memory pada Docker daemon atau build server runner (CI/CD agent). |

---

## 18. Checklist Produksi

- [ ] **AOT Engine Compatibility:** Seluruh 3rd-party dependencies kompatibel dengan GraalVM reachability metadata (verifikasi via native-image agent).
- [ ] **Distroless Runtime:** Container berbasis `nonroot` tanpa file binaries yang tidak perlu (no shell, package manager, standard compilers).
- [ ] **Probes Isolation:** Port Actuator/Management diisolasi secara internal dan dilindungi dari ingress public exposure.
- [ ] **cgroups Alignment:** Parameter `-XX:MaxRAMPercentage` dikonfigurasi presisi sesuai alokasi Kubernetes memory limits.
- [ ] **Graceful Shutdown Validated:** Konfigurasi `server.shutdown=graceful` dan `preStop` hook teruji bebas dari error *HTTP 502 connection drop* saat rolling upgrade.
- [ ] **CI Native Testing:** Automated Native Test execution (`mvn test-compile native:test`) berjalan secara berkala pada CI build pipeline.

---

## 19. Ringkasan Eksekutif
GraalVM Native Image pada Spring Boot 3 mentransformasi paradigma komputasi enterprise Java menjadi kapabilitas sejati *cloud-native*. Melalui eksekusi prinsip *Ahead-Of-Time (AOT)* compilation dan *Closed-World Assumption*, aplikasi Spring Boot memangkas waktu startup dari skala detik menjadi hitungan milidetik serta mereduksi konsumsi baseline memory (RSS) secara drastis hingga <50MB.

Namun, implementasi ini menuntut disiplin teknis:
* Penghapusan ketergantungan pada runtime dynamic reflection tak terdaftar.
* Penyesuaian container lifecycle hooks pada orchestration layer (Kubernetes).
* Pemahaman mendalam mengenai trade-off antara instant startup vs peak JIT compilation performance.

Kombinasi antara GraalVM Native Binary, Distroless container, dan konfigurasi Kubernetes primitives yang presisi menghasilkan infrastruktur microservice yang scalable, cost-efficient, dan resilient terhadap spike beban transaksi ekstrem.

---

## 20. Referensi & Bacaan Lanjutan
* **Spring Framework Documentation:** *Ahead of Time Optimizations & Runtime Hints Support* (docs.spring.io)
* **GraalVM Official Manual:** *Native Image Basics & Substrate VM Architecture* (graalvm.org)
* **Kubernetes Documentation:** *Container Lifecycle Hooks & Resource Management for Pods* (kubernetes.io)
* **Oracle Labs:** *Profile-Guided Optimizations (PGO) in GraalVM Native Image* (oracle.com/graalvm)