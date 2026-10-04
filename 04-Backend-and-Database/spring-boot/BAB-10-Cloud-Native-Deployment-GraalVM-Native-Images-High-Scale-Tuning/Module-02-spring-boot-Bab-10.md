# BAB 10: Cloud Native Deployment, GraalVM Native Images & High-Scale Tuning
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, software engineer diharapkan mampu:
- Membedakan arsitektur eksekusi OpenJDK HotSpot (JIT) dan GraalVM Substrate VM (AOT) secara komprehensif pada level *memory layout*, *compilation phases*, dan *runtime execution*.
- Menguasai *Ahead-of-Time* (AOT) engine pada Spring Boot 3, termasuk siklus hidup `AotProcessor`, generasi kode sumber C-like native, dan resolusi metadata.
- Merancang dan mengimplementasikan `RuntimeHintsRegistrar` kustom untuk menjembatani *reflection*, *dynamic proxy*, *resource loading*, dan *serialization* yang tidak terdeteksi otomatis oleh *static analysis*.
- Mengonfigurasi *pipeline* containerisasi multi-stage OCI (*Open Container Initiative*) berbasis GraalVM Native Build Tools dan Cloud Native Buildpacks (Paketo).
- Mendiagnosis dan menyelesaikan *runtime failure* khas GraalVM (*Closed-World Assumption violation*) menggunakan Native Image Tracing Agent.
- Mengoptimalkan throughput, latensi p99, dan *Resident Set Size* (RSS) pada Kubernetes menggunakan Substrate VM *Garbage Collector* (Serial GC vs G1-like Enterprise GC) dan *Profile-Guided Optimization* (PGO).

---

### 2. Prerequisite
Untuk menyerap materi ini secara optimal, Anda wajib menguasai:
- **Core Java & JVM Internals**: Memahami Java Memory Model (Heap, Metaspace, Stack), mekanisme *Class Loading*, *Bytecode verification*, serta perbedaan interpreter, C1 (Client), dan C2 (Server) JIT compiler.
- **Spring Boot 3 Core**: Memahami konsep *ApplicationContext*, *BeanDefinition*, *BeanFactoryPostProcessor*, dan *Proxy-based AOP*.
- **Containerization & Linux Internals**: Memahami *cgroups v2*, *namespaces*, POSIX signals (`SIGTERM`, `SIGKILL`), glibc vs musl libc, dan Docker multi-stage builds.
- **Tools Terpasang**: GraalVM JDK 21 (Mandrel atau Oracle GraalVM), Docker Engine 24+, Maven 3.9+, dan Kubernetes CLI (`kubectl`).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Closed-World Assumption & Points-to Analysis
GraalVM Native Image mengompilasi *bytecode* Java langsung menjadi *native machine code* (ELF biner pada Linux, Mach-O pada macOS, PE pada Windows) melalui proses Ahead-of-Time (AOT). Fondasi utama dari kompilasi ini adalah **Closed-World Assumption (CWA)**.

```
+-----------------------------------------------------------------------------------+
|                        GRAALVM AOT COMPILATION PIPELINE                           |
+-----------------------------------------------------------------------------------+
  Application Bytecode + Dependencies + JDK Class Library
                          |
                          v
        +-----------------------------------+
        |       Points-to Analysis          | <--- Runtime Metadata (JSON / Hints)
        |  (Static Reachability Analysis)   |      (Reflection, JNI, Proxy, Resources)
        +-----------------------------------+
                          |
             Identifies reachable elements
                          |
                          v
        +-----------------------------------+
        |       Substrate VM Runtime        |
        |   (Thread Scheduler, Minimal GC,  |
        |        Signal Handling, etc.)     |
        +-----------------------------------+
                          |
                          v
        +-----------------------------------+
        |     Graal Compiler (Backend)      |
        |   Native Code Generation (LIR)    |
        +-----------------------------------+
                          |
                          v
              Standalone Native Executable (ELF/Mach-O)
```

1. **Points-to Analysis**: Compiler memulai analisis statis dari *entry point* aplikasi (`public static void main(String[] args)`). Compiler menelusuri seluruh *call tree*, memeriksa setiap instruksi *bytecode* untuk mendeteksi tipe data, metode, dan *field* mana saja yang benar-benar dapat dijangkau (*reachable*).
2. **Dead Code Elimination (Tree Shaking)**: Semua *class*, *method*, dan *field* yang tidak terbukti dapat dijangkau secara transitif akan dibuang secara permanen dari biner akhir.
3. **Heap Snapshotting**: Selama proses kompilasi, GraalVM menjalankan *static initializers* (`<clinit>`) dari kelas-kelas tertentu. Status *in-memory* dari objek-objek yang diinisialisasi pada fase *build time* ini dibekukan (*snapshotted*) dan ditulis langsung ke segmen data biner (*native image heap*). Ketika biner dijalankan, heap ini langsung dipetakan ke memori tanpa perlu inisialisasi ulang.

#### 3.2 Spring Boot 3 AOT Engine
Pada Spring Boot standar berbasis HotSpot, *ApplicationContext* dibentuk secara dinamis saat aplikasi dijalankan: membaca anotasi melalui refleksi, mengevaluasi kondisi `@Conditional`, mengurai konfigurasi XML/YAML, membentuk *synthesized annotations*, dan membungkus bean ke dalam CGLIB proxy. 

Pada mode Native, Spring Boot memindahkan seluruh komputasi dinamis tersebut ke fase **Build-Time AOT Processing**:
- **Phase 1: Inspection & Evaluation**: `AotProcessor` membaca *classpath* aplikasi, mengevaluasi semua konfigurasi Spring, memvalidasi `@ConditionalOnClass` / `@ConditionalOnProperty`.
- **Phase 2: Code Generation**: Spring AOT Engine menghasilkan *Java Source Code* baru (di direktori `target/spring-aot/main/sources`) yang secara imperatif mendaftarkan setiap bean langsung ke `DefaultListableBeanFactory` via metode instansiasi langsung (meniadakan refleksi runtime).
- **Phase 3: Metadata Generation**: Spring AOT Engine mencatat setiap pemanggilan refleksi, registrasi JDK dynamic proxy, atau akses resource file yang masih tak terhindarkan ke dalam file `reflect-config.json`, `proxy-config.json`, dan `resource-config.json`.

#### 3.3 Substrate VM vs HotSpot JVM
Biner yang dihasilkan tidak berjalan di atas JVM konvensional. Sebagai gantinya, GraalVM menyematkan runtime minimalis bernama **Substrate VM**:
- **No ClassLoader**: Struktur runtime tidak memiliki subsistem *Dynamic Class Loading*. Seluruh tipe kelas sudah tetap (*fixed*).
- **No Bytecode JIT**: Tidak ada interpreter dan JIT compiler (secara default), sehingga CPU langsung mengeksekusi instruksi assembly mesin.
- **Memory Footprint**: Metaspace JVM konvensional dieliminasi. Objek dikelola oleh *Native Image Heap* yang lebih ringkas.
- **Garbage Collector**: Menggunakan **Serial GC** (secara default di Community Edition) yang dioptimalkan untuk memori rendah (*low footprint*) dan *pause time* singkat pada heap kecil (< 4GB). Oracle GraalVM menyediakan opsi **G1-like Enterprise GC** untuk heap berskala puluhan gigabyte.

---

### 4. Why & What

#### Mengapa Beralih ke GraalVM Native Image?
1. **Instant Startup Time**: Startup aplikasi dipangkas dari hitungan detik (biasanya 3–15 detik pada HotSpot JVM) menjadi **10–50 milidetik**. Hal ini krusial untuk arsitektur *Scale-to-Zero* (Serverless Knative/AWS Lambda) dan *rapid autoscaling* saat lonjakan trafik mendadak (*flash crowds*).
2. **Minimal Memory Footprint (RSS)**: HotSpot JVM memerlukan overhead memori dasar yang signifikan untuk menyimpan *JIT Compiler Data structures*, *Code Cache*, *Metaspace*, dan *Class Metadata* (umumnya minimum 250MB–512MB RSS). Substrate VM dapat berjalan stabil pada rentang **30MB–80MB RSS**.
3. **Immutability & Attack Surface Reduction**: Ketiadaan dynamic class loading dan penyingkiran kode mati secara agresif meminimalisasi vektor serangan (misalnya eksploitasi berbasis *gadget-chain deserialization* seperti Log4Shell).

#### Kapan Native Image Menjadi Pilihan yang Kurang Tepat?
- **High-Throughput Monoliths**: HotSpot C2 Compiler memiliki kemampuan *Profile-Guided Dynamic Recompilation* yang dapat mengoptimalkan eksekusi runtime berdasarkan profil trafik nyata (inlining, de-optimization). Tanpa PGO (Profile-Guided Optimization), performa peak-throughput native image bisa 10–20% lebih rendah dibanding HotSpot C2 jangka panjang.
- **Extreme Build Duration**: Proses kompilasi AOT membutuhkan memori CPU dan RAM yang sangat besar pada CI/CD (bisa mencapai 8–16 GB RAM dan 5–15 menit waktu build per servis).

---

### 5. How (Workflow Detail)

Alur produksi dari source code Java hingga deployment Native Image di Kubernetes:

```
[Developer Code: Spring Boot 3]
               |
               v
 [mvn clean package -Pnative]
   |--> Step 1: spring-boot-maven-plugin:process-aot
   |            Generates BeanDefinitions & Core Hints
   |--> Step 2: native-maven-plugin:compile
   |            Triggers GraalVM native-image CLI
   |            Input: Generated Source + Bytecode + Reachability Metadata
               |
               v
 [Executable Native Binary: app] (Linux ELF 64-bit)
               |
               v
 [Multi-Stage Docker Build]
   |--> Stage 1: Build & Native Compile (GraalVM image)
   |--> Stage 2: Distroless Minimal Image (gcr.io/distroless/cc-debian12)
               |
               v
 [Ultra-Secure, Minimal Container (~80MB)]
               |
               v
 [Kubernetes Deployment with High-Scale Tuning]
```

1. **Dependency Analysis**: Memastikan seluruh library eksternal sudah menyediakan *Reachability Metadata* (via `native-image.properties` internal atau via repo *GraalVM Reachability Metadata Repository*).
2. **Execution via Tracing Agent**: Untuk dependensi non-standar, jalankan aplikasi pada HotSpot JVM dengan `-agentlib:native-image-agent` untuk merekam interaksi reflektif nyata ke format JSON.
3. **Compile Phase**: Native Image Builder membaca konfigurasi dan melakukan AOT compilation ke *target platform assembly*.
4. **Distroless Packaging**: Biner dikemas ke dalam *base image* minimalis (seperti `distroless/cc-debian12` atau `alpine` via musl-libc) tanpa JDK di dalamnya.
5. **K8s High-Density Scheduling**: Mengalokasikan Pod dengan CPU/Memory resource requests yang jauh lebih rapat (*dense pod allocation*).

---

### 6. Analogy & Diagram ASCII

#### Analogi: Restoran Tradisional vs Makanan Siap Saji MRE
- **HotSpot JVM (Restoran Tradisional)**: Koki membawa seluruh bahan mentah, buku resep lengkap, dan peralatan ke dapur. Setiap pesanan masuk, koki mencicipi, mengevaluasi selera pelanggan, mengubah teknik memasak secara *real-time* (*JIT Tiered Compilation*). Startup lama, konsumsi dapur besar, namun rasa pesanan berulang bisa disesuaikan sempurna (*Peak Throughput Optimization*).
- **GraalVM Native Image (MRE - Meal, Ready-to-Eat)**: Dapur pabrik mengolah, memasak, membuang sisa makanan yang tidak perlu, dan menyegel makanan ke dalam kaleng steril saat fase produksi (*Build-time AOT*). Konsumen cukup membuka kaleng dan mengonsumsinya instan (< 10ms). Tidak ada bahan mentah tambahan, ukuran sangat ringkas, namun resep tidak dapat diubah di tempat jika ada request baru yang tidak tercatat di pabrik (*Closed-World Assumption*).

#### Perbandingan Memory Layout (HotSpot vs Substrate VM)

```
HOTSPOT JVM PROCESS MEMORY                     SUBSTRATE VM PROCESS MEMORY
+--------------------------------------+       +--------------------------------------+
| Resident Set Size (RSS) ~ 450MB      |       | Resident Set Size (RSS) ~ 65MB       |
|                                      |       |                                      |
|  +--------------------------------+  |       |  +--------------------------------+  |
|  | Heap Space (Young / Old Gen)   |  |       |  | Native Image Heap              |  |
|  | Objek aktif, 256MB             |  |       |  | (Snapshotted data + App data)  |  |
|  +--------------------------------+  |       |  | 40MB                           |  |
|  +--------------------------------+  |       |  +--------------------------------+  |
|  | Metaspace (Dynamic Classes)    |  |       |  +--------------------------------+  |
|  | 80MB                           |  |       |  | Executable Code (.text segment)|  |
|  +--------------------------------+  |       |  | Native machine assembly        |  |
|  +--------------------------------+  |       |  | 20MB                           |  |
|  | Code Cache (JIT Compiled Code) |  |       |  +--------------------------------+  |
|  | 64MB                           |  |       |  +--------------------------------+  |
|  +--------------------------------+  |       |  | Substrate Minimal Runtime &    |  |
|  | JVM Internal / GC / Threads    |  |       |  | Thread Stacks: 5MB             |  |
|  | 50MB                           |  |       |  +--------------------------------+  |
|  +--------------------------------+  |       +--------------------------------------+
+--------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Runtime Hints Implementation
Ketika library third-party mengakses field privat melalui *reflection* atau menggunakan Jackson deserialization dinamis yang tidak dideklarasikan secara eksplisit di controller signature, compiler AOT tidak dapat mendeteksinya. Kita harus mendaftarkannya via `RuntimeHintsRegistrar`.

##### Dynamic Payload Record
```java
package com.enterprise.nativeapp.model;

public record TransactionEvent(
    String transactionId,
    Long amountInCents,
    String currency,
    String signature
) {}
```

##### Custom RuntimeHintsRegistrar
```java
package com.enterprise.nativeapp.hints;

import com.enterprise.nativeapp.model.TransactionEvent;
import org.springframework.aot.hint.MemberCategory;
import org.springframework.aot.hint.RuntimeHints;
import org.springframework.aot.hint.RuntimeHintsRegistrar;

public class PaymentGatewayRuntimeHints implements RuntimeHintsRegistrar {

    @Override
    public void registerHints(RuntimeHints hints, ClassLoader classLoader) {
        // Daftarkan refleksi untuk parsing Jackson dinamis
        hints.reflection().registerType(
            TransactionEvent.class,
            MemberCategory.INVOKE_PUBLIC_CONSTRUCTORS,
            MemberCategory.INVOKE_PUBLIC_METHODS,
            MemberCategory.DECLARED_FIELDS
        );

        // Daftarkan pemuatan resource file yang dibaca saat runtime
        hints.resources().registerPattern("certificates/payment-gateway-public.pem");
    }
}
```

##### Pendaftaran Hints ke Konfigurasi Spring
```java
package com.enterprise.nativeapp.config;

import com.enterprise.nativeapp.hints.PaymentGatewayRuntimeHints;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.ImportRuntimeHints;

@Configuration(proxyBeanMethods = false)
@ImportRuntimeHints(PaymentGatewayRuntimeHints.class)
public class NativeConfiguration {
    // Bean definitions native-compatible
}
```

---

#### 7.2 Practical Example: Enterprise-Grade Microservice Setup

Berikut adalah konfigurasi produksi menyeluruh meliputi `pom.xml`, *Multi-Stage Dockerfile* aman berbasis Distroless, dan implementasi service native-ready.

##### File: `pom.xml` (Kompilasi GraalVM Native Tools)
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

    <groupId>com.enterprise</groupId>
    <artifactId>high-scale-payment-service</artifactId>
    <version>1.0.0-SNAPSHOT</version>

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
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
                <configuration>
                    <image>
                        <builder>bellsoft/buildpacks.builder:musl</builder>
                    </image>
                </configuration>
            </plugin>
        </plugins>
    </build>

    <profiles>
        <profile>
            <id>native</id>
            <build>
                <plugins>
                    <plugin>
                        <groupId>org.graalvm.buildtools</groupId>
                        <artifactId>native-maven-plugin</artifactId>
                        <version>0.10.2</version>
                        <extensions>true</extensions>
                        <executions>
                            <execution>
                                <id>build-native</id>
                                <goals>
                                    <goal>compile-no-fork</goal>
                                </goals>
                                <phase>package</phase>
                            </execution>
                        </executions>
                        <configuration>
                            <imageName>payment-native-exec</imageName>
                            <buildArgs>
                                <buildArg>--no-fallback</buildArg>
                                <buildArg>-H:+ReportExceptionStackTraces</buildArg>
                                <buildArg>-H:+AddAllCharsets</buildArg>
                                <buildArg>--enable-http</buildArg>
                                <buildArg>--enable-https</buildArg>
                            </buildArgs>
                        </configuration>
                    </plugin>
                </plugins>
            </build>
        </profile>
    </profiles>
</project>
```

##### File: `PaymentController.java`
```java
package com.enterprise.nativeapp.controller;

import com.enterprise.nativeapp.model.TransactionEvent;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/payments")
public class PaymentController {

    private static final Logger log = LoggerFactory.getLogger(PaymentController.class);

    @PostMapping("/process")
    public ResponseEntity<Map<String, Object>> processPayment(@Valid @RequestBody TransactionEvent event) {
        log.info("Processing transaction: {} for amount: {}", event.transactionId(), event.amountInCents());
        
        return ResponseEntity.ok(Map.of(
            "status", "APPROVED",
            "transactionId", event.transactionId(),
            "processedAt", Instant.now().toString()
        ));
    }
}
```

##### File: `Dockerfile` (Multi-Stage Production Build)
```dockerfile
# Stage 1: Build the native binary using GraalVM JDK
FROM ghcr.io/graalvm/native-image-community:21-ol9 AS builder

WORKDIR /build

# Copy Maven wrapper and dependencies specification
COPY pom.xml mvnw ./
COPY .mvn .mvn

# Resolve dependencies offline
RUN ./mvnw dependency:go-offline -B

# Copy application sources
COPY src src

# Run AOT processing and Native Compilation
RUN ./mvnw clean package -Pnative -DskipTests

# Stage 2: Ultra-minimal distroless execution environment
FROM gcr.io/distroless/cc-debian12:nonroot

WORKDIR /app

# Copy compiled ELF binary from builder stage
COPY --from=builder /build/target/payment-native-exec /app/payment-native-exec

# Configure standard non-root user
USER nonroot:nonroot

# Expose HTTP port
EXPOSE 8080

# Environment flags for Substrate VM GC and Thread limits
ENV MALLOC_ARENA_MAX=2

ENTRYPOINT ["/app/payment-native-exec", "-XX:MaximumHeapSizePercent=80", "-XX:+PrintGC"]
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Tier-1 Financial Core Payment Gateway (Flash Sale Scale-to-Zero)
- **Karakteristik Trafik**: Volume normal 50 req/sec, melonjak drastis hingga 45.000 req/sec dalam rentang waktu < 2 menit saat flash sale/event transfer gratis.
- **Problem Statement (HotSpot JVM Eksisting)**:
  - Startup waktu pod JVM rata-rata 18 detik.
  - Saat HPA (Horizontal Pod Autoscaler) memicu *scale-out*, pod baru belum siap menerima trafik, menyebabkan p99 latensi melonjak hingga 4.8 detik dan terjadi *Cascading Failures* akibat *readiness probe timeouts*.
  - Alokasi memori klaster: Tiap pod JVM meminta `requests: 512Mi`, `limits: 1Gi`. Untuk menampung 300 pod cadangan, perusahaan membuang biaya idle ratusan juta rupiah per bulan.

#### Solusi Arsitektur Menggunakan Spring Boot 3 & GraalVM Native:
1. **Migration Pipeline**:
   - Menghapus dependensi yang bergantung pada manipulasi runtime bytecode (CGLIB dinamis murni digantikan standard interface proxies).
   - Menggunakan `native-image-agent` saat integration test untuk mengumpulkan pola dynamic call pada library enkripsi pihak ketiga (*Hardware Security Module client*).
2. **Knative Autoscaling Deployment**:
   - Mengonfigurasi autoscaler Knative dengan target konkurensi 100 req/pod.
   - Startup pod native berkurang dari 18 detik menjadi **38 milidetik**. Pod instan melayani trafik tanpa fase pemanasan (*JVM Warm-up/C2 JIT compilation penalty*).
3. **Resource Footprint Transformation**:
   - Memori diturunkan drastis: `requests: 64Mi`, `limits: 128Mi`.
   - Node density meningkat 4.5x lipat: Setiap Worker Node Kubernetes (m5.2xlarge - 32GB RAM) yang tadinya hanya mampu memuat 28 Pod JVM, kini mampu menampung hingga 140 Pod Native Image dengan stabil.
4. **Hasil Produksi**:
   - p99 Latency turun dari 4.8 detik ke **18 milidetik** saat lonjakan trafik masif.
   - Biaya infrastruktur klaster bulanan terpangkas hingga **62%**.

---

### 9. Trade-offs (Analisis Komparasi)

| Vektor Arsitektur | HotSpot JVM (C1/C2 JIT) | GraalVM Native Image (Substrate VM) | Justifikasi Rekayasa Sistem |
| :--- | :--- | :--- | :--- |
| **Startup Time** | Lambat (2 – 20 detik) | Instan (10 – 50 ms) | Native unggul mutlak untuk Serverless, Knative, CLI, dan Fast Autoscaling. |
| **Memory Footprint (RSS)** | Besar (250MB – 1GB+) | Sangat Rendah (30MB – 90MB) | Native mengeliminasi bytecode metadata, metaspace, dan compiler JIT internal. |
| **Peak Throughput** | Maksimal (Adaptif) | Moderat s/d Sangat Tinggi (Jika PGO aktif) | HotSpot melakukan deoptimasi runtime dinamis berdasarkan data profiling nyata; Native membutuhkan Profile-Guided Optimization (PGO) untuk menyamai throughput HotSpot. |
| **Build Duration** | Cepat (Detik s/d 1-2 Menit) | Sangat Lambat (4 – 15 Menit) | AOT Compiler menganalisis seluruh call-graph semesta (*whole-world analysis*), menguras memori dan CPU pipeline CI/CD. |
| **Dynamic Capabilities**| Tak Terbatas (Dynamic Classloading, Bytecode Injection) | Sangat Terbatas (Semua refleksi/proxy wajib terdaftar statis) | Native memberlakukan *Closed-World Assumption*; pemanggilan reflektif tanpa registrasi metadata akan melempar runtime error. |
| **Observability/Profiling**| Universal (JFR, Async-Profiler, VisualVM, JMX)| Terbatas (JFR terbatas, Native Core Dumps, Linux `perf`, GDB) | Debugging memori native image memerlukan pemahaman struktur pointer sistem operasi C/C++. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Runtime NoSuchMethodException / ClassNotFoundException
- **Gejala**: Aplikasi berhasil dikompilasi ke file biner, tetapi langsung crash saat endpoint tertentu diakses dengan error:
  `java.lang.NoSuchMethodException: com.enterprise.model.UserDto.<init>()`
- **Penyebab**: Class `UserDto` hanya dipakai sebagai target deserialization Jackson dan tidak pernah dipanggil secara eksplisit melalui kode instansiasi langsung di dalam program. Analisis *Points-to* GraalVM menganggap konstruktor tersebut sebagai kode mati dan membuangnya.
- **Solusi**: Daftarkan class tersebut ke `RuntimeHintsRegistrar` atau tambahkan anotasi `@RegisterReflectionForBinding(UserDto.class)` pada konfigurasi Spring Boot 3.

#### 10.2 Substrate VM Out-Of-Memory Error pada Container K8s
- **Gejala**: Pod mengalami `OOMKilled` oleh Linux Kernel (Exit Code 137), meskipun metrik heap native jauh di bawah batas limits.
- **Penyebab**: Alokator glibc standar pada Linux membuat beberapa alokasi *memory arena* secara agresif (`MALLOC_ARENA_MAX`) saat menangani konkurensi thread tinggi, menyebabkan fragmentasi memori off-heap yang masif.
- **Solusi**: Tambahkan variabel lingkungan pada container:
  ```dockerfile
  ENV MALLOC_ARENA_MAX=2
  ```
  Dan pastikan heap maksimum dikonfigurasi secara eksplisit pada entrypoint:
  `-XX:MaximumHeapSizePercent=75`

#### 10.3 Native Compilation Kehabisan Memori di Mesin CI/CD (Exit Code 137 saat Build)
- **Gejala**: Build gagal saat fase `[native-image-plugin] Analysis...` dengan log terputus tiba-tiba atau `Killed`.
- **Penyebab**: GraalVM Native Image Compiler secara default mengalokasikan hingga 80% RAM fisik mesin. Jika Docker daemon atau runner CI hanya memiliki batas memori 4GB, compiler akan di-kill oleh OOM killer OS.
- **Solusi**: Batasi konsumsi memori native builder pada `pom.xml`:
  ```xml
  <configuration>
      <buildArgs>
          <buildArg>-J-Xmx6g</buildArg>
      </buildArgs>
  </configuration>
  ```

---

### 11. Best Practices (Production Checklist)

1. **Gunakan Distroless atau Scratch Base Image**: Jangan gunakan image Ubuntu/Debian penuh untuk membungkus binary native. Gunakan `gcr.io/distroless/cc-debian12` yang hanya membawa `glibc`, `libstdc++`, dan `zlib`.
2. **Aktifkan Profile-Guided Optimization (PGO)**: Untuk performa throughput tinggi (menyamai C2 JIT):
   - Build instrumen biner: `native-image --pgo-instrument`
   - Berikan beban trafik representatif (benchmark) selama 10 menit.
   - Biner akan menghasilkan file `default.iprof`.
   - Lakukan kompilasi final: `native-image --pgo=default.iprof`.
3. **Konfigurasi Container Readiness & Liveness Probes Secara Agresif**: Karena startup native hanya butuh < 100ms:
   ```yaml
   readinessProbe:
     httpGet:
       path: /actuator/health/readiness
       port: 8080
     initialDelaySeconds: 1
     periodSeconds: 2
   ```
4. **Implementasikan Graceful Shutdown**: Pastikan sinyal POSIX `SIGTERM` ditangkap dengan benar oleh Substrate VM untuk memutus koneksi database pooling (HikariCP):
   ```properties
   server.shutdown=graceful
   spring.lifecycle.timeout-per-shutdown-phase=20s
   ```
5. **Gunakan Automated Reachability Metadata Repository**: Aktifkan fitur pencarian metadata otomatis di maven plugin agar library pihak ketiga (seperti driver JDBC, AWS SDK) otomatis diinjeksi konfigurasinya:
   ```xml
   <metadataRepository>
       <enabled>true</enabled>
   </metadataRepository>
   ```

---

### 12. Hands-on Practice

Buat seluruh struktur direktori dan file berikut di workstation Anda di bawah path `hands-on/m02/`.

#### Struktur Direktori
```
hands-on/m02/
├── Dockerfile
├── k8s/
│   └── deployment.yaml
├── pom.xml
└── src/
    └── main/
        ├── java/
        │   └── com/
        │       └── enterprise/
        │           └── nativeapp/
        │               ├── Application.java
        │               ├── config/
        │               │   └── NativeReflectionConfig.java
        │               ├── controller/
        │               │   └── AccountController.java
        │               └── model/
        │                   └── AccountPayload.java
        └── resources/
            └── application.properties
```

#### File: `hands-on/m02/pom.xml`
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
    <groupId>com.enterprise</groupId>
    <artifactId>native-hands-on</artifactId>
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
    </dependencies>
    <profiles>
        <profile>
            <id>native</id>
            <build>
                <plugins>
                    <plugin>
                        <groupId>org.graalvm.buildtools</groupId>
                        <artifactId>native-maven-plugin</artifactId>
                        <version>0.10.2</version>
                        <extensions>true</extensions>
                        <executions>
                            <execution>
                                <goals>
                                    <goal>compile-no-fork</goal>
                                </goals>
                                <phase>package</phase>
                            </execution>
                        </executions>
                        <configuration>
                            <imageName>native-hands-on</imageName>
                            <buildArgs>
                                <buildArg>--no-fallback</buildArg>
                            </buildArgs>
                        </configuration>
                    </plugin>
                </plugins>
            </build>
        </profile>
    </profiles>
</project>
```

#### File: `hands-on/m02/src/resources/application.properties`
```properties
server.port=8080
spring.application.name=native-hands-on
management.endpoints.web.exposure.include=health,info,prometheus
management.endpoint.health.probes.enabled=true
```

#### File: `hands-on/m02/src/main/java/com/enterprise/nativeapp/model/AccountPayload.java`
```java
package com.enterprise.nativeapp.model;

public record AccountPayload(
    String accountId,
    String ownerName,
    Double balance
) {}
```

#### File: `hands-on/m02/src/main/java/com/enterprise/nativeapp/config/NativeReflectionConfig.java`
```java
package com.enterprise.nativeapp.config;

import com.enterprise.nativeapp.model.AccountPayload;
import org.springframework.aot.hint.MemberCategory;
import org.springframework.aot.hint.RuntimeHints;
import org.springframework.aot.hint.RuntimeHintsRegistrar;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.ImportRuntimeHints;

@Configuration(proxyBeanMethods = false)
@ImportRuntimeHints(NativeReflectionConfig.DirectHints.class)
public class NativeReflectionConfig {

    static class DirectHints implements RuntimeHintsRegistrar {
        @Override
        public void registerHints(RuntimeHints hints, ClassLoader classLoader) {
            hints.reflection().registerType(
                AccountPayload.class,
                MemberCategory.INVOKE_DECLARED_CONSTRUCTORS,
                MemberCategory.INVOKE_PUBLIC_METHODS
            );
        }
    }
}
```

#### File: `hands-on/m02/src/main/java/com/enterprise/nativeapp/controller/AccountController.java`
```java
package com.enterprise.nativeapp.controller;

import com.enterprise.nativeapp.model.AccountPayload;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/accounts")
public class AccountController {

    @PostMapping
    public ResponseEntity<AccountPayload> createAccount(@RequestBody AccountPayload request) {
        AccountPayload created = new AccountPayload(
            UUID.randomUUID().toString(),
            request.ownerName(),
            request.balance()
        );
        return ResponseEntity.ok(created);
    }
}
```

#### File: `hands-on/m02/src/main/java/com/enterprise/nativeapp/Application.java`
```java
package com.enterprise.nativeapp;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}
```

#### File: `hands-on/m02/Dockerfile`
```dockerfile
FROM ghcr.io/graalvm/native-image-community:21-ol9 AS builder
WORKDIR /workspace
COPY pom.xml mvnw ./
COPY .mvn .mvn
RUN ./mvnw dependency:go-offline -B
COPY src src
RUN ./mvnw clean package -Pnative -DskipTests

FROM gcr.io/distroless/cc-debian12:nonroot
WORKDIR /
COPY --from=builder /workspace/target/native-hands-on /native-hands-on
USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/native-hands-on"]
```

#### File: `hands-on/m02/k8s/deployment.yaml`
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: native-hands-on-deployment
  labels:
    app: native-hands-on
spec:
  replicas: 3
  selector:
    matchLabels:
      app: native-hands-on
  template:
    metadata:
      labels:
        app: native-hands-on
    spec:
      containers:
      - name: payment-native
        image: native-hands-on:1.0.0
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8080
        resources:
          requests:
            memory: "64Mi"
            cpu: "50m"
          limits:
            memory: "128Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /actuator/health/liveness
            port: 8080
          initialDelaySeconds: 2
          periodSeconds: 5
        readinessProbe:
          httpGet:
            path: /actuator/health/readiness
            port: 8080
          initialDelaySeconds: 1
          periodSeconds: 3
```

#### Eksekusi Hands-on
```bash
# Masuk ke direktori
cd hands-on/m02/

# Build binary native menggunakan multi-stage Docker
docker build -t native-hands-on:1.0.0 .

# Verifikasi ukuran Docker image (Pastikan ukuran < 120MB)
docker images | grep native-hands-on

# Jalankan container secara lokal
docker run --rm -p 8080:8080 --name native-test native-hands-on:1.0.0

# Di terminal lain, uji responsivitas endpoint
curl -X POST http://localhost:8080/accounts \
  -H "Content-Type: application/json" \
  -d '{"ownerName":"Budi Santoso","balance":15000000.0}'

# Periksa startup time di log output container (Harus di bawah 0.100s)
```

---

### 13. Exercise

#### Level Easy
Ubah konfigurasi `hands-on/m02/pom.xml` agar nama biner executable yang dihasilkan bernama `enterprise-service-bin`. Buktikan melalui log build Maven di mana biner tersebut dihasilkan.

#### Level Medium
Sebuah class utilitas pihak ketiga bernama `ExternalAuditLogger` membaca properti privat menggunakan refleksi:
```java
package com.thirdparty;
public class ExternalAuditLogger {
    private String secretKey = "AES-SECRET";
}
```
Implementasikan unit test atau kelas konfigurasi Spring Boot AOT menggunakan API `RuntimeHints` untuk mendaftarkan akses pembacaan field `secretKey` tanpa memodifikasi source code class `ExternalAuditLogger`.

#### Level Hard
Buat script automasi (Bash atau Python) yang mengeksekusi integrasi native test dengan Native Image Tracing Agent:
1. Menjalankan JAR aplikasi standar HotSpot dengan `-agentlib:native-image-agent=config-output-dir=src/main/resources/META-INF/native-image`.
2. Mengeksekusi serangkaian tes cURL integration tests yang memicu eksekusi dinamis.
3. Menghentikan aplikasi secara graceful (`SIGINT` / `SIGTERM`) agar file konfigurasi JSON tersimpan otomatis.
4. Memvalidasi bahwa file `reflect-config.json` yang dihasilkan berisi tipe data yang dipanggil oleh skenario pengujian.

---

### 14. Challenge

**Skenario**: Perusahaan Anda mengintegrasikan sistem perbankan lama berbasis library *Legacy ISO-8583 XML Serializer*. Library ini menggunakan runtime bytecode generation internal (berbasis ASM tua) dan custom class loader dinamis yang dilarang keras oleh *Substrate VM Closed-World Assumption*. Perusahaan tidak memiliki akses ke source code dependensi tersebut (hanya binary JAR komersial).

**Instruksi Masalah**:
1. Rancang arsitektur transisi yang memungkinkan servis Spring Boot Native Image tetap memanfaatkan fungsionalitas engine legacy tersebut tanpa merusak batasan Substrate VM.
2. Identifikasi apakah arsitektur harus memisahkan komponen ke dalam pola *Sidecar Architecture* (misalnya: Pod K8s dengan satu container Native Image Spring Boot berperforma tinggi yang berkomunikasi via IPC/gRPC/Unix Domain Socket ke JVM HotSpot Container minimalis khusus pembaca XML ISO-8583).
3. Buat rancangan spesifikasi deployment Kubernetes multi-container (Pod spec) yang mendemonstrasikan integrasi inter-process communication (UDS over shared `emptyDir` volume) untuk mempertahankan latensi sub-milidetik antar kedua proses tersebut.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda & Konseptual Singkat)
1. **Apa yang dimaksud dengan Closed-World Assumption (CWA) pada GraalVM?**
   - A. Aplikasi tidak boleh terhubung ke jaringan internet publik saat berjalan.
   - B. Seluruh bytecode yang mungkin dieksekusi saat runtime harus dapat diidentifikasi dan dianalisis secara statis pada fase kompilasi (build-time).
   - C. Database harus berjalan di dalam cluster yang sama dengan native image.
   - D. Substrate VM mengunci port aplikasi agar tidak dapat diakses secara dinamis.
   *Kunci Jawaban: B. Karena compiler AOT harus membuang kode mati secara deterministik.*

2. **Komponen apa yang menggantikan HotSpot JVM di dalam biner executable GraalVM?**
   - A. OpenJ9
   - B. CoreCLR
   - C. Substrate VM
   - D. Dalvik Engine
   *Kunci Jawaban: C. Substrate VM menyediakan alokasi memori, garbage collector, dan threading runtime minimal.*

3. **Kapan static initializers (`<clinit>`) dijalankan secara default pada kompilasi Spring Boot 3 Native?**
   - A. Selalu saat runtime ketika kelas di-load pertama kali.
   - B. Saat fase Build Time untuk optimasi pemotretan heap (*heap snapshotting*) sesuai konfigurasi GraalVM/Spring.
   - C. Saat container Docker ditutup.
   - D. Tidak pernah dijalankan.
   *Kunci Jawaban: B.*

4. **Metaspace pada HotSpot JVM menyimpan metadata kelas. Bagaimana Substrate VM mengelola metadata ini?**
   - A. Disimpan di AWS S3 bucket.
   - B. Dialokasikan secara dinamis di Swap Space Linux.
   - C. Dieliminasi; informasi layout kelas langsung dikompilasi menjadi representasi C/C++ native data structures dalam image heap.
   - D. Menggunakan database SQLite lokal.
   *Kunci Jawaban: C.*

5. **Apa fungsi dari argumen `--no-fallback` pada konfigurasi Native Image Plugin?**
   - A. Memaksa compiler gagal jika tidak mampu membuat native image murni, mencegah generasi fallback executable berbasis JVM reguler.
   - B. Mencegah aplikasi restart saat terjadi uncaught exception.
   - C. Menonaktifkan Circuit Breaker pattern.
   - D. Menghindari pembatalan koneksi database.
   *Kunci Jawaban: A.*

#### Bagian 2: Intermediate (Analisis Kasus Singkat)
6. **Mengapa aplikasi Spring Boot 3 native image memiliki startup time puluhan milidetik dibanding JVM biasa?**
   *Jawaban Evaluasi*: Karena Substrate VM tidak melakukan inisialisasi class loading dinamis, tidak mengurai anotasi saat runtime, tidak menjalankan bytecode interpretation, dan tidak memerlukan pemanasan JIT compiler. Heap awal sudah siap pakai dalam biner dan langsung dipetakan ke memori via OS syscall (`mmap`).

7. **Sebutkan minimal 3 kategori runtime hints yang didukung oleh interface `RuntimeHints` Spring Boot 3!**
   *Jawaban Evaluasi*: 
   1) `hints.reflection()` (registrasi kelas, konstruktor, method, field).
   2) `hints.resources()` (registrasi file static, properties, pem pattern file).
   3) `hints.proxies()` (registrasi JDK Dynamic Proxies).
   *(Bisa juga `hints.serialization()` atau `hints.jni()`)*.

8. **Apa kerugian terbesar dari GC bawaan (Serial GC) pada GraalVM Community Edition jika digunakan untuk beban kerja High-Throughput dengan Heap 16GB?**
   *Jawaban Evaluasi*: Serial GC adalah *single-threaded*, *stop-the-world collector*. Pada ukuran heap yang besar (16GB), pembersihan memori (*full GC pause*) akan menghentikan seluruh thread aplikasi selama ratusan milidetik hingga beberapa detik, merusak batas SLA latensi p99.

9. **Apa kegunaan dari `native-image-agent` yang disediakan oleh GraalVM?**
   *Jawaban Evaluasi*: Menjalankan aplikasi di atas JVM reguler seraya mengintersepsi seluruh pemanggilan dinamis (refleksi, JNI, proxy, resources) dan secara otomatis menuliskan metadata tersebut ke dalam file konfigurasi JSON (`reflect-config.json`, dll.) tanpa perlu dicatat manual oleh engineer.

10. **Bagaimana Spring Boot 3 AOT menangani proxy CGLIB pada native image?**
    *Jawaban Evaluasi*: CGLIB menghasilkan bytecode baru secara dinamis saat runtime, hal yang tidak dimungkinkan di Substrate VM. Spring AOT memecahkan ini dengan menggeser generasi subclass proxy tersebut ke fase build-time via kode Java statis atau menggantinya dengan JDK Dynamic Interface Proxies.

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario Produksi 1 (Build Time Out-Of-Memory)**:
    - *Kasus*: Pipeline Jenkins CI/CD mati mendadak dengan status `Exit Code 137` saat menjalankan perintah `./mvnw clean package -Pnative`. Mesin builder memiliki 8 Core CPU dan 8GB RAM fisik.
    - *Analisis*: GraalVM Native Image compiler membutuhkan alokasi RAM yang sangat besar saat menganalisis call graph global. Secara default, compiler mendeteksi 8GB dan mencoba mengalokasikan hampir seluruhnya, namun terbentur batas proses OS dan alokasi container runner CI itu sendiri sehingga dimatikan oleh Linux OOM Killer.
    - *Solusi Tepat*: Batasi memory compiler dengan menambahkan argument `-J-Xmx5g` dan batasi thread parallelism compiler menggunakan `-H:NumberOfThreads=4` di Maven/Gradle buildArgs untuk mengurangi beban memori serentak.

12. **Skenario Produksi 2 (Reflection Failure pada Third-Party Library)**:
    - *Kasus*: Aplikasi berhasil startup dalam 25ms di Kubernetes. Namun saat memproses pembayaran kartu kredit, muncul log `NullPointerException` atau `InstantiationException` pada library payment gateway `com.acme.gateway.SdkClient`.
    - *Analisis*: `SdkClient` melakukan instansiasi class driver secara dinamis via `Class.forName("...")` berdasarkan konfigurasi database. Points-to analysis GraalVM tidak menemukan hubungan statis kelas ini saat build-time, sehingga class driver tersebut dibuang (*tree-shaken*).
    - *Solusi Tepat*: Buat implementasi `RuntimeHintsRegistrar` untuk mendaftarkan target driver class ke reflection registry dengan kategori `MemberCategory.INVOKE_DECLARED_CONSTRUCTORS` dan `MemberCategory.INVOKE_PUBLIC_METHODS`, kemudian impor kelas hints tersebut via `@ImportRuntimeHints`.

13. **Skenario Produksi 3 (CPU CFS Quota Throttling Pasca Deployment)**:
    - *Kasus*: Native Image dideploy ke Kubernetes dengan `cpu requests: 100m` dan `cpu limits: 500m`. Saat benchmark dengan 5.000 konkurensi request, latensi aplikasi melonjak drastis, dan metrik `container_cpu_cfs_throttled_periods_total` menunjukkan angka tinggi.
    - *Analisis*: Native Image mengeksekusi instruksi mesin secara sangat cepat tanpa jeda I/O interpreter. Dengan batas CPU CFS yang ketat (500 millicores), aplikasi cepat sekali menghabiskan jatah CPU kuota dalam periode 100ms CFS window, menyebabkan kernel Linux menahan thread aplikasi (*throttling*).
    - *Solusi Tepat*: Hapus parameter `cpu limits` pada deployment (biarkan pod melakukan bursting sesuai kapasitas node) atau tingkatkan limits CPU menjadi minimal 2-4 core untuk mengimbangi eksekusi native assembly yang sangat padat.

---

### 16. Summary

1. **Paradigma Pergeseran Runtime**: GraalVM Native Image mengubah model eksekusi Java dari pendekatan tradisional *interpret-and-compile* (HotSpot C1/C2) menjadi *ahead-of-time statically compiled binary* berbasis Substrate VM.
2. **Kepatuhan Closed-World Assumption**: Semua dependensi, refleksi, manipulasi bytecode, dan pemanggilan proxy harus bersifat deterministik dan terdaftar sejak fase kompilasi.
3. **Spring Boot 3 Core Engine**: Bertindak sebagai akselerator AOT dengan menggantikan pemindaian anotasi dinamis berbasis refleksi menjadi generasi kode deklaratif statis saat proses *build*.
4. **Keunggulan Cloud Native**: Memangkas waktu inisialisasi aplikasi ke ranah *millisecond latency* dan mereduksi alokasi RAM hingga 80%, menjadikannya standar baku untuk deployment berdensitas tinggi (*high-density clusters*) dan sistem *Serverless Scale-to-Zero*.
5. **Trade-off Sadar Rekayasa**: Keuntungan startup dan memori dibayar dengan durasi pipeline build yang lama, penanganan konfigurasi reflektif manual via `RuntimeHintsRegistrar`, dan perlunya *Profile-Guided Optimization* (PGO) untuk aplikasi yang memprioritaskan peak continuous throughput.