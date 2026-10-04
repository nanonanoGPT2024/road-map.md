# BAB 10: Observability, Cloud-Native Deployment & GraalVM Native Image
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menguasai arsitektur internal **GraalVM Native Image (Substrate VM)**, mencakup mekanisme *Closed-World Assumption*, *Points-To Analysis*, serta pemisahan siklus hidup *Build-Time vs. Run-Time Initialization*.
- Mengonfigurasi dan mengotomatisasi **Reachability Metadata** untuk kasus dinamis Java (Reflection, Dynamic Proxy, JNI, Resource Loading, dan Serialization) menggunakan Native Image Tracing Agent.
- Mengimplementasikan ekosistem **Full-Stack Observability** berstandar OpenTelemetry (Tracing, Metrics, Logs) secara *native-compatible* tanpa ketergantungan pada runtime bytecode manipulation (Java Agent).
- Mendesain pipeline kontainerisasi multi-stage berbasis **Distroless Container** yang aman, minimalis (< 50MB), dan teroptimasi untuk lingkungan Kubernetes.
- Mengonfigurasi strategi deployment cloud-native tingkat lanjut: zero-downtime rolling update, tuning *Probes* (Startup, Liveness, Readiness), serta alokasi resource limits berbasis karakteristik Serial GC vs. G1 GC pada Substrate VM.

---

### 2. Prerequisite
Sebelum mendalami modul ini, peserta diwajibkan telah memahami:
- **Core Java Internals**: JVM Memory Model, Garbage Collection, Java Reflection API, Classloading hierarchy.
- **BAB 10 - Modul 01**: Dasar-dasar Observability, konsep pemula AOT vs JIT, dan pengenalan kontainerisasi Docker.
- **Build Tools**: Maven atau Gradle (tingkat lanjut, termasuk konfigurasi plugin).
- **Infrastruktur Dasar**: CLI Linux, Docker Engine, dan konsep orkestrasi container Kubernetes (Pod, Deployment, Services).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Substrate VM dan Closed-World Assumption
GraalVM Native Image tidak mengeksekusi bytecode menggunakan interpreter atau JIT (*Just-In-Time*) compiler standar (seperti HotSpot HotSpot C1/C2). Sebagai gantinya, GraalVM menggunakan **Substrate VM**, sebuah runtime minimalis yang ditulis menggunakan bahasa Java namun dikompilasi langsung ke kode mesin (*native machine code*) via **AOT (Ahead-Of-Time) Compilation**.

```
+-------------------------------------------------------------------------------+
|                       GRAALVM NATIVE IMAGE BUILD PIPELINE                     |
+-------------------------------------------------------------------------------+
|  Java Bytecode (.class / .jar) + Reachability Metadata (JSON)                 |
+-------------------------------------------------------------------------------+
                                      │
                                      ▼
+-------------------------------------------------------------------------------+
| Points-To Analysis (Static Code Analysis)                                     |
| - Identifikasi seluruh class, method, field yang reachable dari 'main()'      |
| - Mengabaikan / memangkas (tree-shaking) kode yang tidak terpakai             |
+-------------------------------------------------------------------------------+
                                      │
                                      ▼
+-------------------------------------------------------------------------------+
| Build-Time Heap Snapshotting                                                  |
| - Eksekusi static initializers (class <clinit>) tertentu                      |
| - Snapshot struktur object graph build-time langsung ke Image Heap            |
+-------------------------------------------------------------------------------+
                                      │
                                      ▼
+-------------------------------------------------------------------------------+
| Substrate VM Assembly & AOT Compilation                                       |
| - Kompilasi reachable code menjadi Native Machine Code (x86_64 / AArch64)     |
| - Penyisipan Runtime Substrate (GC Minimalis, Thread Management, Signal)       |
+-------------------------------------------------------------------------------+
                                      │
                                      ▼
+-------------------------------------------------------------------------------+
| Standalone OS Executable Binary (Linux ELF / macOS Mach-O / Windows PE)       |
+-------------------------------------------------------------------------------+
```

Inti dari proses ini adalah **Closed-World Assumption**:
1. **Static Analysis Horizon**: Compiler mengasumsikan bahwa *semua* bytecode yang mungkin dieksekusi saat runtime dapat diprediksi dan dianalisis secara statis pada saat kompilasi.
2. **Dead Code Elimination (DCE)**: Seluruh method, kelas, atau library transitif yang tidak terdeteksi oleh *Points-To Engine* akan dieliminasi dari binary akhir.
3. **Konsekuensi Refleksi**: Dynamic Class Loading via `Class.forName(variable)` secara default akan gagal jika compiler tidak diberikan instruksi eksplisit bahwa kelas tersebut reachable.

#### 3.2 Build-Time vs Run-Time Class Initialization
Salah satu titik krusial arsitektur Substrate VM adalah penentuan kapan `<clinit>` (Class Initialization Block) dieksekusi:

| Parameter | `--initialize-at-build-time` | `--initialize-at-run-time` |
| :--- | :--- | :--- |
| **Kapan Eksekusi** | Saat binary dikompilasi oleh compiler host. | Saat aplikasi native dijalankan pertama kali. |
| **Penyimpanan State** | State objek yang diinisialisasi disimpan ke dalam **Image Heap**. | State dibuat segar di runtime OS memory. |
| **Kecepatan Startup** | Sangat cepat (mendekati 1-5 milidetik). | Normal (perlu eksekusi instruksi inisialisasi). |
| **Bahaya Potensial** | Menangkap state host (misal: Open File Handlers, Socket Connections, Random Seeds, Thread yang berjalan). Mengakibatkan crash runtime fatal. | Konfigurasi refleksi tambahan mungkin diperlukan jika ada referensi terisolasi. |

#### 3.3 Garbage Collection pada Substrate VM
Tidak seperti HotSpot yang kaya akan opsi GC (ZGC, Shenandoah, Parallel, G1), Substrate VM pada edisi Community Edition (CE) hanya menyediakan **Serial GC**:
- Bersifat *stop-the-world*, *non-parallel*, dan *single-threaded*.
- Dioptimalkan untuk footprint memori minimal (overhead footprint ~beberapa MB) dan skenario short-lived runtime (Serverless/FaaS, micro-service task scale-to-zero).
- *Catatan Enterprise*: GraalVM Enterprise Edition (EE) / Oracle GraalVM mendukung **G1 GC** untuk aplikasi high-throughput dengan Image Heap besar.

#### 3.4 OpenTelemetry Architecture: Agent vs. Native SDK
Pada arsitektur JVM klasik, instrumentasi OpenTelemetry sering kali menggunakan Java Agent (`-javaagent:opentelemetry-javaagent.jar`) yang memanfaatkan Byte Buddy untuk melakukan manipulasi bytecode dinamis saat runtime (*dynamic class redefinition*). 

Dalam Native Image, **metode Java Agent dinamis mustahil digunakan** karena tidak ada interpreter bytecode runtime atau compiler JIT di dalam binary Substrate VM. Solusi produksi menuntut:
1. **Compile-time / Source-level Instrumentation**: Menggunakan **OpenTelemetry SDK** langsung via programmatic API atau framework extension (Quarkus OTel / Spring Boot 3 Actuator + Micrometer Tracing).
2. **Context Propagation Manual / Synthetic Wrappers**: W3C Trace Context (`traceparent`, `tracestate`) di-injeksi dan diekstrak secara eksplisit pada HTTP/gRPC boundaries.

---

### 4. Why & What

| Kategori Evaluasi | HotSpot JVM (JIT) | GraalVM Native Image (AOT) |
| :--- | :--- | :--- |
| **Startup Time** | Lambat (1 - 15 detik, terhambat Class Loading & JIT Tiering) | Instan (5 - 50 milidetik) |
| **Peak Throughput** | Maksimal (JIT C2 melakukan profiling dinamis, inlining, de-optimisasi) | Moderat hingga Tinggi (AOT statis tanpa PGO, mendekati JIT jika menggunakan PGO EE) |
| **Memory Footprint (RSS)** | Tinggi (150MB - 1GB+ per instance JVM) | Sangat Rendah (15MB - 80MB per instance) |
| **Build Time & Resource** | Cepat (Beberapa detik, Maven/Gradle build standar) | Sangat Lambat & Intensif (2 - 10 menit, butuh 4-8 core CPU & 8-16GB RAM) |
| **Dynamic Capabilities** | Mendukung dynamic bytecode generation, HotSpot redefinition | Terbatas kaku; harus dideklarasikan via Reachability Metadata |
| **Observability Agent** | Pasif via JVM Agent attachment (`-javaagent`) | Aktif via compiled native OpenTelemetry SDK / Micrometer |

---

### 5. How (Workflow Detail)

Alur kompilasi, tracing reachability, dan kontainerisasi native:

```
[Tahap 1: Analisis Dinamis via Agent]
 Aplikasi JVM Standar + GraalVM Tracing Agent dijalankan
 java -agentlib:native-image-agent=config-output-dir=src/main/resources/META-INF/native-image ...
               │
               ▼ (Eksekusi integrasi test komprehensif memicu refleksi)
 Himpunan File Metadata Terbentuk:
 - reflect-config.json
 - resource-config.json
 - proxy-config.json
 - serialization-config.json
               │
               ▼
[Tahap 2: AOT Compilation dengan Native Image Tooling]
 native-image -jar app.jar --no-fallback -H:+ReportExceptionStackTraces ...
               │
               ▼
 Output: Single Standalone Binary ELF (Linux Executable)
               │
               ▼
[Tahap 3: Distroless Multi-Stage Packaging]
 Docker multi-stage: Base Image GraalVM -> Copy binary -> Base Image Google Distroless Static
 Ukuran Image Akhir: ~30MB - 50MB (Bebas dari OS Vulnerabilities, sh, apt, curl)
               │
               ▼
[Tahap 4: Runtime Deployment Kubernetes]
 Pod running -> Startup Probe lulus dalam 100ms -> OpenTelemetry OTLP Push Traces ke Collector
```

---

### 6. Analogy & Diagram ASCII

#### 6.1 Analogi: Kontraktor Rumah (JIT) vs Moduler Pracetak (AOT)
- **JVM JIT**: Kontraktor membawa bahan mentah (batu bata, semen, cetak biru) ke lokasi pembangunan (server). Mereka membangun perlahan, mengamati cuaca, dan mengubah denah secara dinamis saat pemilik rumah berubah pikiran. Rumah butuh waktu lama untuk siap dihuni, tetapi strukturnya dioptimalkan dengan cermat sesuai kebiasaan penghuni.
- **GraalVM Native Image**: Seluruh rumah dicetak di pabrik pracetak (*build machine*). Jika ada perabotan yang tidak ada dalam daftar manifes pabrik (refleksi), perabotan tersebut tidak bisa dimasukkan. Setelah tiba di lokasi, rumah tinggal diletakkan di atas fondasi dan langsung siap ditinggali dalam hitungan detik.

#### 6.2 Diagram Propagasi Konteks OpenTelemetry di Substrate VM

```
Client Request 
     │
     │ HTTP GET /api/v1/payments (Headers: traceparent=00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01)
     ▼
+──────────────────────────────────────────────────────────────────────────+
| Native Image Binary (Substrate VM)                                       |
|                                                                          |
|  [W3C Context Extractor]                                                 |
|          │                                                               |
|          ▼                                                               |
|  [OpenTelemetry Span Creation] -> Inject SpanContext ke Scope            |
|          │                                                               |
|          ├─► [Micrometer Counter/Timer Increment] (Prometheus Registry)   |
|          │                                                               |
|          ▼                                                               |
|  [Business Logic Execution]                                              |
|          │                                                               |
|          ▼                                                               |
|  [W3C Context Injector] -> Set traceparent ke outbound HTTP/DB Client    |
+──────────────────────────────────────────────────────────────────────────+
     │
     ├──► Push Spans (Protobuf/gRPC) via OTLP Exporter ──► [ OpenTelemetry Collector ]
     │                                                               │
     ▼                                                               ├─► Jaeger / Tempo
Database / Downstream Microservice                                   └─► Prometheus
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Manual Reachability Metadata
Ketika melakukan serialisasi string JSON menggunakan engine yang bergantung pada dynamic reflection tanpa plugin otomatis:

**Domain Model (`UserPayload.java`):**
```java
package com.enterprise.telemetry.domain;

public class UserPayload {
    private String userId;
    private String role;

    // Default constructor diwajibkan untuk instansiasi refleksi
    public UserPayload() {}

    public UserPayload(String userId, String role) {
        this.userId = userId;
        this.role = role;
    }

    public String getUserId() { return userId; }
    public void setUserId(String userId) { this.userId = userId; }
    public String getRole() { return role; }
    public void setRole(String role) { this.role = role; }
}
```

Jika model di atas dipanggil secara dinamis menggunakan `Class.forName("com.enterprise.telemetry.domain.UserPayload")`, buat manifes konfigurasi:

**`src/main/resources/META-INF/native-image/com.enterprise/app/reflect-config.json`:**
```json
[
  {
    "name": "com.enterprise.telemetry.domain.UserPayload",
    "allDeclaredConstructors": true,
    "allPublicConstructors": true,
    "allDeclaredMethods": true,
    "allPublicMethods": true,
    "allDeclaredFields": true
  }
]
```

---

#### 7.2 Practical Example: Enterprise Observability Native Stack
Implementasi manual distributed tracing dengan **OpenTelemetry SDK** terpadu, kompatibel 100% dengan GraalVM AOT tanpa dynamic agent bytecode.

**1. File Konfigurasi Maven (`pom.xml`):**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.enterprise.telemetry</groupId>
    <artifactId>native-observability-core</artifactId>
    <version>1.0.0-SNAPSHOT</version>

    <properties>
        <java.version>21</java.version>
        <opentelemetry.version>1.36.0</opentelemetry.version>
        <graalvm.plugin.version>0.10.1</graalvm.plugin.version>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>

    <dependencyManagement>
        <dependencies>
            <dependency>
                <groupId>io.opentelemetry</groupId>
                <artifactId>opentelemetry-bom</artifactId>
                <version>${opentelemetry.version}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
        </dependencies>
    </dependencyManagement>

    <dependencies>
        <dependency>
            <groupId>io.opentelemetry</groupId>
            <artifactId>opentelemetry-api</artifactId>
        </dependency>
        <dependency>
            <groupId>io.opentelemetry</groupId>
            <artifactId>opentelemetry-sdk</artifactId>
        </dependency>
        <dependency>
            <groupId>io.opentelemetry</groupId>
            <artifactId>opentelemetry-exporter-otlp</artifactId>
        </dependency>
        <dependency>
            <groupId>com.sun.net.httpserver</groupId>
            <artifactId>http</artifactId>
            <version>20070405</version>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>3.12.1</version>
                <configuration>
                    <source>${java.version}</source>
                    <target>${java.version}</target>
                </configuration>
            </plugin>
            <plugin>
                <groupId>org.graalvm.buildtools</groupId>
                <artifactId>native-maven-plugin</artifactId>
                <version>${graalvm.plugin.version}</version>
                <extensions>true</extensions>
                <configuration>
                    <imageName>native-telemetry-server</imageName>
                    <mainClass>com.enterprise.telemetry.NativeObservabilityApplication</mainClass>
                    <buildArgs>
                        <buildArg>--no-fallback</buildArg>
                        <buildArg>-H:+ReportExceptionStackTraces</buildArg>
                        <buildArg>--initialize-at-build-time=org.slf4j.LoggerFactory</buildArg>
                    </buildArgs>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
```

**2. Core Engine & HTTP Server dengan Distributed Tracing (`NativeObservabilityApplication.java`):**
```java
package com.enterprise.telemetry;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;
import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.common.AttributeKey;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.StatusCode;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.api.trace.propagation.W3CTraceContextPropagator;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.Scope;
import io.opentelemetry.context.propagation.TextMapGetter;
import io.opentelemetry.exporter.otlp.trace.OtlpGrpcSpanExporter;
import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.resources.Resource;
import io.opentelemetry.sdk.trace.SdkTracerProvider;
import io.opentelemetry.sdk.trace.export.BatchSpanProcessor;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Collections;
import java.util.List;

public class NativeObservabilityApplication {

    private static final String SERVICE_NAME = "enterprise-payment-orchestrator";
    private static final Tracer TRACER = initOpenTelemetry().getTracer(SERVICE_NAME, "1.0.0");

    private static final TextMapGetter<HttpExchange> GETTER = new TextMapGetter<>() {
        @Override
        public Iterable<String> keys(HttpExchange carrier) {
            return carrier.getRequestHeaders().keySet();
        }

        @Override
        public String get(HttpExchange carrier, String key) {
            List<String> headers = carrier.getRequestHeaders().get(key);
            return (headers != null && !headers.isEmpty()) ? headers.get(0) : null;
        }
    };

    public static void main(String[] args) throws IOException {
        long startTime = System.currentTimeMillis();
        
        int port = 8080;
        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);
        
        server.createContext("/api/v1/checkout", new OrderProcessingHandler());
        server.createContext("/healthz/liveness", exchange -> respond(exchange, 200, "{\"status\":\"UP\"}"));
        server.createContext("/healthz/readiness", exchange -> respond(exchange, 200, "{\"status\":\"READY\"}"));

        server.setExecutor(null); // Gunakan default thread executor
        server.start();

        long bootTime = System.currentTimeMillis() - startTime;
        System.out.printf("[PRODUCTION] %s native binary running on port %d. Cold-start took %d ms%n", 
                SERVICE_NAME, port, bootTime);

        // Pasang Graceful Shutdown Hook
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            System.out.println("[SHUTDOWN] Signal received. Halting server gracefully...");
            server.stop(2);
            System.out.println("[SHUTDOWN] Substrate runtime stopped cleanly.");
        }));
    }

    private static OpenTelemetrySdk initOpenTelemetry() {
        Resource resource = Resource.getDefault().merge(
                Resource.create(Attributes.of(AttributeKey.stringKey("service.name"), SERVICE_NAME))
        );

        String otlpEndpoint = System.getenv().getOrDefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317");

        OtlpGrpcSpanExporter spanExporter = OtlpGrpcSpanExporter.builder()
                .setEndpoint(otlpEndpoint)
                .setTimeout(Duration.ofSeconds(2))
                .build();

        SdkTracerProvider tracerProvider = SdkTracerProvider.builder()
                .addSpanProcessor(BatchSpanProcessor.builder(spanExporter).build())
                .setResource(resource)
                .build();

        return OpenTelemetrySdk.builder()
                .setTracerProvider(tracerProvider)
                .setPropagators(io.opentelemetry.context.propagation.ContextPropagators.create(
                        W3CTraceContextPropagator.getInstance()))
                .buildAndRegisterGlobal();
    }

    private static class OrderProcessingHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            // Ekstraksi trace context dari W3C Header inbound
            Context extractedContext = GlobalOpenTelemetry.getPropagators().getTextMapPropagator()
                    .extract(Context.current(), exchange, GETTER);

            Span span = TRACER.spanBuilder("ExecuteCheckout")
                    .setParent(extractedContext)
                    .startSpan();

            try (Scope scope = span.makeCurrent()) {
                span.setAttribute("http.method", exchange.getRequestMethod());
                span.setAttribute("http.target", exchange.getRequestURI().getPath());

                if (!"POST".equalsIgnoreCase(exchange.getRequestMethod())) {
                    span.setStatus(StatusCode.ERROR, "Invalid Method");
                    respond(exchange, 405, "{\"error\":\"Method Not Allowed\"}");
                    return;
                }

                // Simulasi pemrosesan bisnis yang krusial
                processPaymentLogic(span);

                span.setStatus(StatusCode.OK);
                respond(exchange, 200, "{\"transactionId\":\"tx-9941824\", \"status\":\"CONFIRMED\"}");
            } catch (Exception ex) {
                span.recordException(ex);
                span.setStatus(StatusCode.ERROR, ex.getMessage());
                respond(exchange, 500, "{\"error\":\"Internal Server Error\"}");
            } finally {
                span.end();
            }
        }

        private void processPaymentLogic(Span parentSpan) {
            Span internalSpan = TRACER.spanBuilder("FraudCheckDatabaseQuery")
                    .setParent(Context.current())
                    .startSpan();
            try {
                // Mensimulasikan latensi eksekusi query internal
                Thread.sleep(15);
                internalSpan.setAttribute("db.system", "postgresql");
                internalSpan.setAttribute("db.statement", "SELECT risk_level FROM fraud_cache WHERE id = ?");
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } finally {
                internalSpan.end();
            }
        }
    }

    private static void respond(HttpExchange exchange, int statusCode, String responseJson) throws IOException {
        byte[] bytes = responseJson.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        exchange.sendResponseHeaders(statusCode, bytes.length);
        try (OutputStream os = exchange.getResponseBody()) {
            os.write(bytes);
        }
    }
}
```

---

### 8. Real World Case Study: Flash Sale Infrastructure Transformation

#### 8.1 Latar Belakang & Masalah
Sebuah platform E-Commerce Tier-1 menyelenggarakan program flash sale berskala nasional. Arsitektur lama berbasis HotSpot JVM (Spring Boot di Kubernetes) mengalami kendala serius saat lonjakan trafik masif:
- **Cold Start Latency**: Scaling dari 10 Pods ke 300 Pods membutuhkan waktu rata-rata **45-60 detik per Pod** akibat kombinasi inisialisasi class loading, parsing bean Spring, dan kompilasi bertingkat JIT (C1/C2).
- **Thundering Herd & OOMKills**: JVM yang baru hidup mengonsumsi CPU berlebih untuk warm-up JIT, menyebabkan startup probe terlambat merespons sehingga Kubernetes membunuh pod berulang kali (*CrashLoopBackOff*).
- **Memory Cost**: Setiap JVM memakan *Resident Set Size (RSS)* rata-rata **480MB**, membatasi densitas pod per node worker EC2.

#### 8.2 Solusi Arsitektur
1. Migrasi critical order path ke **GraalVM Native Image** berbasis runtime Java 21 dengan *Distroless Container*.
2. Implementasi **Reachability Metadata Repository** terpusat selama Continuous Integration (CI).
3. Penggantian dynamic Java Agent tracing dengan **OpenTelemetry Direct Native SDK** yang mengalirkan spans menggunakan protocol buffer gRPC secara langsung ke OTel Collector DaemonSet.

#### 8.3 Hasil Metrik Komparasi Produksi

```
Metrik                          HotSpot JVM (JIT)     GraalVM Native (Substrate VM)
Startup to Ready:               52.4 Detik            0.028 Detik (28 ms)
Baseline Memory (Idle):         340 MB RSS            22 MB RSS
Active Load Memory (Peak):      680 MB RSS            74 MB RSS
K8s Scale-Up Time (10->300 pod): 8.5 Menit             12 Detik
Node Cost Savings (AWS EKS):    -                     Hemat 68% (Densitas Pod naik 4x)
```

---

### 9. Trade-offs

```
                  ARSITEKTUR PERFORMA: AOT vs JIT
  
       GraalVM Native Image                    HotSpot JVM
   (Optimal untuk Cloud Native)             (Optimal untuk Monolith)
  ┌───────────────────────────┐           ┌───────────────────────────┐
  │ [Startup Time]   < 50ms   │           │ [Startup Time]   > 10s    │
  │ [Footprint]      < 80MB   │           │ [Footprint]      > 500MB  │
  │ [Build Time]     Menit    │           │ [Build Time]     Detik    │
  │ [Peak Throughput]~90-95%  │           │ [Peak Throughput]100%     │
  └───────────────────────────┘           └───────────────────────────┘
```

#### 9.1 Peak Throughput vs. Startup Time
JIT compiler pada HotSpot mengumpulkan data *profile-guided* secara berkelanjutan saat aplikasi berjalan. JIT dapat melakukan spekulasi de-optimisasi (*speculative optimization*) dan *loop unrolling* yang lebih agresif untuk performa komputasi murni. Native Image (tanpa Enterprise Profile-Guided Optimization / PGO) menghasilkan *peak throughput* sekitar 5-10% lebih rendah dibanding HotSpot yang telah ter-warmup sempurna, namun mengorbankan waktu startup dan kapasitas RAM yang sangat besar.

#### 9.2 Developer Feedback Loop vs. Production Efficiency
Kompilasi native membutuhkan sumber daya CPU dan waktu tinggi (2 hingga 10 menit untuk satu kompilasi microservice). 
- *Trade-off Workflow*: Pengembangan lokal harian tetap dijalankan di JVM HotSpot mode standar, sementara pipeline CI/CD bertugas menguji dan memvalidasi kompilasi Native Image secara terjadwal.

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 `ClassNotFoundException` / `NoSuchMethodException` saat Runtime
- **Penyebab**: Class atau method dipanggil lewat refleksi (misal Jackson deserialization, dynamic database driver load) tetapi tidak terdaftar di `reflect-config.json`.
- **Solusi**: Jangan membuat konfigurasi manual secara terus-menerus. Jalankan JVM test suite menggunakan GraalVM Tracing Agent:
  ```bash
  java -agentlib:native-image-agent=config-merge-dir=src/main/resources/META-INF/native-image -jar target/app.jar
  ```

#### 10.2 Error: "Classes that should be initialized at run time got initialized during image building"
- **Penyebab**: Terjadi kebocoran status objek stateful runtime (seperti `Thread`, `Socket`, `Random`, atau File Pointer) ke dalam fase kompilasi akibat penggunaan anotasi atau opsi `--initialize-at-build-time` yang terlalu luas (misal pada seluruh package root).
- **Troubleshooting**: Terapkan `--initialize-at-run-time` secara granular pada package yang menyimpan network socket atau hardware pointer. Isolasi class initialization:
  ```bash
  --initialize-at-build-time=org.slf4j.LoggerFactory \
  --initialize-at-run-time=io.netty.channel.epoll.NativeDatagramPacketArray
  ```

#### 10.3 Kehilangan Tracing Context (Context Propagation Leak)
- **Penyebab**: Penggunaan custom thread pool atau asynchronous constructs (`CompletableFuture.supplyAsync()`, Project Reactor, Akka) yang tidak mengikat OpenTelemetry `Context` antar boundary thread worker.
- **Solusi**: Bungkus task Runnable / Callable menggunakan decorator kontekstual:
  ```java
  Runnable tracedTask = Context.current().wrap(originalRunnable);
  executorService.submit(tracedTask);
  ```

---

### 11. Best Practices (Production Checklist)

#### 11.1 Native Image Compilation Checklist
- [ ] Opsi `--no-fallback` wajib disertakan agar build gagal jika native image tidak dapat dibentuk sempurna (mencegah fallback ke standard JDK container).
- [ ] Build dilakukan pada container yang identik dengan target platform arsitektur kernel OS (misal: Linux glibc vs musl).
- [ ] Hapus dependensi bytecode manipulator runtime (CGLIB, Javassist, dynamic ASM generation runtime). Gunakan framework modern berbasis compile-time (Micronaut, Quarkus, atau Spring Boot 3 AOT).

#### 11.2 Containerization & Kubernetes Checklist
- [ ] Basis container image menggunakan **Google Distroless Static** atau **Alpine Minimal** untuk meminimalisasi CVE attack surface.
- [ ] Non-root execution: Pastikan UID runtime di-set ke user non-privilege (`USER nonroot:nonroot`).
- [ ] Penyetelan Kubernetes Probe:
  - `startupProbe`: `failureThreshold: 3`, `periodSeconds: 1` (Lolos dalam hitungan < 100ms).
  - `terminationGracePeriodSeconds`: Minimal 15-30 detik untuk memberikan ruang flush buffer distributed traces pada OpenTelemetry SDK BatchProcessor.

---

### 12. Hands-on Practice

Buat dan simpan struktur project di path: `hands-on/m02/`

#### Langkah 1: Siapkan Multi-Stage Dockerfile
Tulis file `hands-on/m02/Dockerfile`:

```dockerfile
# Stage 1: Build Native Executable menggunakan Oracle GraalVM Native Image
FROM container-registry.oracle.com/graalvm/native-image:21-ol9 AS build-engine

WORKDIR /workspace
RUN microdnf install -y findutils

# Copy Maven Wrapper & Dependencies Definition
COPY pom.xml .
COPY src ./src

# Eksekusi kompilasi native
RUN ./mvnw -B package -Pnative -DskipTests

# Stage 2: Final Runtime Distroless Container
FROM gcr.io/distroless/static-debian12:nonroot

WORKDIR /app
COPY --from=build-engine /workspace/target/native-telemetry-server /app/native-telemetry-server

# Non-root user default dari distroless: nonroot (UID 65532)
USER 65532:65532

EXPOSE 8080
ENTRYPOINT ["/app/native-telemetry-server"]
```

#### Langkah 2: Buat Kubernetes Deployment Manifest
Tulis file `hands-on/m02/k8s-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: native-payment-service
  labels:
    app: native-payment
spec:
  replicas: 3
  selector:
    matchLabels:
      app: native-payment
  template:
    metadata:
      labels:
        app: native-payment
    spec:
      containers:
      - name: payment-node
        image: enterprise/native-telemetry-server:1.0.0
        imagePullPolicy: IfNotPresent
        resources:
          limits:
            cpu: "1000m"
            memory: "128Mi"
          requests:
            cpu: "50m"
            memory: "32Mi"
        env:
        - name: OTEL_EXPORTER_OTLP_ENDPOINT
          value: "http://otel-collector.monitoring.svc.cluster.local:4317"
        ports:
        - containerPort: 8080
          name: http
        startupProbe:
          httpGet:
            path: /healthz/readiness
            port: 8080
          initialDelaySeconds: 0
          periodSeconds: 1
          failureThreshold: 5
        readinessProbe:
          httpGet:
            path: /healthz/readiness
            port: 8080
          periodSeconds: 5
        livenessProbe:
          httpGet:
            path: /healthz/liveness
            port: 8080
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: native-payment-service
spec:
  type: ClusterIP
  selector:
    app: native-payment
  ports:
  - port: 80
    targetPort: 8080
```

#### Langkah 3: Eksekusi Build & Verifikasi
Jalankan instruksi berikut di terminal:
```bash
# 1. Build image lokal
docker build -t enterprise/native-telemetry-server:1.0.0 hands-on/m02/

# 2. Periksa ukuran Image
docker images enterprise/native-telemetry-server:1.0.0

# 3. Jalankan container secara terisolasi
docker run --rm -p 8080:8080 enterprise/native-telemetry-server:1.0.0

# 4. Uji endpoint dari terminal terpisah
curl -i -X POST http://localhost:8080/api/v1/checkout \
  -H "traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
```

---

### 13. Exercise

#### Level Easy
Ubah method `initOpenTelemetry` pada `NativeObservabilityApplication.java` agar membaca konfigurasi sampling rate dari environment variable `OTEL_TRACES_SAMPLER_ARG` (tipe Double, default `1.0`). Validasi bahwa trace context tetap diekstraksi meskipun span tidak di-sample.

#### Level Medium
Tambahkan custom OpenTelemetry `SpanProcessor` yang mengintercept setiap span yang berstatus `StatusCode.ERROR` dan menambahkan atribut metadata node native:
- Host architecture (`os.arch`)
- Substrate VM version property

#### Level Hard
Buat implementasi custom serialization reflection config untuk library dynamic RPC pihak ketiga (tanpa bantuan tracing agent). Program harus dapat mendeteksi annotasi kustom `@EnterpriseRpcPayload` menggunakan compile-time Java Annotation Processing (APT) dan men-generate file `META-INF/native-image/.../reflect-config.json` secara otomatis selama fase `compile` Maven.

---

### 14. Challenge

**Skenario**:
Anda ditugaskan mengaudit sistem pemrosesan finansial mission-critical yang baru saja dimigrasikan ke GraalVM Native Image. Di cluster Kubernetes staging, aplikasi mengalami crash secara misterius (*SIGSEGV / segmentation fault*) setiap kali menerima beban 5.000 RPS terus-menerus selama 15 menit, sementara pengujian lokal pada JVM standar berjalan stabil tanpa error. 

Metrik menunjukkan memory consumption terus meningkat secara linier hingga menyentuh batas `limits.memory: 128Mi` tanpa memicu Log Exception Java (`java.lang.OutOfMemoryError`). Tidak ada thread dump yang dihasilkan karena default JVM crash handler tidak berfungsi di dalam image distroless tanpa shell debugging tools.

**Tugas Anda**:
1. Buat hipotesis teknis penyebab kebocoran memori native (*non-heap memory leak*) di level Substrate VM / JNI boundaries.
2. Rancang arsitektur strategi diagnosa untuk mengidentifikasi root cause pada binary native di lingkungan terisolasi Kubernetes tanpa merusak status produksi.
3. Rancang patch konfigurasi build arg GraalVM native image (`native-image.properties`) dan mitigasi memory handling untuk memastikan stabilitas alokasi heap Serial GC di Substrate VM.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda / Konsep Singkat)
1. **Apa fungsi utama dari Closed-World Assumption pada GraalVM Native Image?**
   - A. Menutup koneksi database runtime jika tidak aktif.
   - B. Membatasi akses jaringan aplikasi ke localhost saja.
   - C. Mengasumsikan seluruh class dan method yang reachable dapat dideteksi secara statis pada fase kompilasi.
   - D. Menghindari integrasi dengan platform cloud selain Oracle Cloud.

2. **Mengapa flag `--no-fallback` wajib disertakan dalam kompilasi native enterprise?**
   - A. Mencegah compiler menghasilkan binary standar JVM .jar jika kompilasi native gagal.
   - B. Menonaktifkan rollback transaksi database secara otomatis.
   - C. Mengurangi ukuran image heap sebesar 50%.
   - D. Menginstruksikan CPU untuk mematikan instruksi AVX2.

3. **Komponen apa di dalam Substrate VM yang menggantikan fungsi JVM HotSpot standard?**
   - A. Java ClassLoader.
   - B. Runtime minimal yang terintegrasi langsung di dalam binary mencakup GC sederhana, thread tracking, dan OS signal handling.
   - C. Byte Buddy runtime proxy.
   - D. Spring CGLIB engine.

4. **Bagaimana format standar header W3C Trace Context untuk propagasi distributed tracing?**
   - A. `x-b3-traceid` dan `x-b3-spanid`
   - B. `traceparent` dan `tracestate`
   - C. `Authorization: Bearer TraceToken`
   - D. `X-Request-ID`

5. **Garbage collector default yang digunakan pada GraalVM Community Edition Native Image adalah...**
   - A. ZGC
   - B. G1 GC
   - C. Serial GC
   - D. Shenandoah GC

#### Bagian 2: Intermediate (Analisis Arsitektur)
6. **Jelaskan bahaya mengeksekusi inisialisasi kelas thread pool dengan flag `--initialize-at-build-time`!**
7. **Mengapa OpenTelemetry Java Agent standar (`-javaagent:opentelemetry-javaagent.jar`) tidak dapat digunakan pada GraalVM Native Image?**
8. **Sebutkan tiga file JSON utama yang diproduksi oleh GraalVM Native Tracing Agent beserta fungsinya masing-masing!**
9. **Kapan startup probe Kubernetes dianggap lebih unggul daripada hanya mengandalkan liveness probe pada aplikasi berbasis GraalVM Native?**
10. **Bagaimana cara kerja mekanisme Dead Code Elimination (DCE) dalam mereduksi ukuran binary pada Substrate VM?**

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario A**: Tim Anda memigrasikan microservice ke GraalVM Native Image. Saat deployment di Kubernetes, Pods langsung berstatus `Running`, tetapi setiap kali menerima request pertama yang membaca file resource (`getClass().getClassLoader().getResourceAsStream("certs/private.pem")`), aplikasi melempar `NullPointerException`. Apa akar masalahnya dan bagaimana memperbaikinya di configuration build?
12. **Skenario B**: Aplikasi native berhasil dikompilasi, namun throughput transaksi p99 terdeteksi drop signifikan (melonjak hingga 500ms tiap beberapa menit) saat beban bertambah tinggi, padahal pada HotSpot JVM throughput tetap stabil di bawah 20ms. Analisis arsitektur GC apa yang menjadi pemicunya dan apa rekomendasi arsitekturalnya?
13. **Skenario C**: Sebuah payment gateway mewajibkan zero data loss saat Pod di-terminate oleh autoscaler (*Horizontal Pod Autoscaler*). Log distributed traces menunjukkan spans terakhir sebelum Pod hilang selalu terputus (*broken trace*). Identifikasi bottleneck di level lifecycle native image dan OTel BatchProcessor-nya!

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian 1: Basic
1. **C** — Mengasumsikan seluruh class dan method yang reachable dapat dideteksi secara statis pada fase kompilasi.
2. **A** — Mencegah compiler menghasilkan binary JVM fallback (.jar yang butuh JDK) jika proses AOT native image mendeteksi kesalahan.
3. **B** — Runtime minimal yang terintegrasi langsung di dalam binary (Substrate VM).
4. **B** — `traceparent` dan `tracestate`.
5. **C** — Serial GC.

#### Bagian 2: Intermediate
6. **Bahaya Build-Time ThreadPool Initialization**: Thread yang di-instansiasi pada build-time akan mencoba menangkap context native OS host build. Ketika Image Heap di-snapshot, state thread OS tersebut tidak valid di host runtime OS target, mengakibatkan fatal error `IllegalStateException` atau crash runtime Substrate VM saat boot.
7. **Inkompatibilitas Java Agent**: Agent mengandalkan runtime instrumentation API JVM, class redefinition, dan modifikasi runtime dynamic bytecode. Di Native Image, bytecode interpreter sudah tidak ada; seluruh kode sudah dibekukan menjadi native machine instructions.
8. **Tiga File JSON Metadata**:
   - `reflect-config.json`: Mendaftarkan classes, methods, dan fields yang diakses lewat Java Reflection.
   - `resource-config.json`: Mendaftarkan path file (properties, XML, sertifikat) yang harus dimasukkan ke dalam binary image heap.
   - `proxy-config.json`: Mendaftarkan antarmuka dinamis (*Dynamic Proxies*) yang di-generate via `java.lang.reflect.Proxy`.
9. **Startup Probe vs Liveness Probe**: Meskipun startup GraalVM cepat (< 50ms), startup probe bertindak sebagai pelindung terisolasi agar liveness probe yang agresif tidak membunuh Pod sebelum socket listener benar-benar binding dan koneksi initial pool database selesai.
10. **Mekanisme DCE**: Points-to analysis menelusuri call graph mulai dari `main()`. Method/field/class yang tidak memiliki path eksekusi statis dari titik masuk (*unreachable graph*) akan dipotong (*tree-shaken*) dari kompilasi kode mesin, mereduksi binary size secara drastis.

#### Bagian 3: Skenario Kasus Produksi
11. **Solusi Skenario A**: Substrate VM tidak memasukkan arbitrary application resources ke dalam binary secara otomatis. File `certs/private.pem` tidak terdaftar pada `resource-config.json`. Solusinya: Daftarkan pola file tersebut ke dalam `resource-config.json` menggunakan pattern `{"pattern": "certs/.*"}` atau passing build arg: `-H:IncludeResources=certs/private.pem`.
12. **Solusi Skenario B**: Ini adalah dampak dari **Serial GC** (stop-the-world single thread). Saat alokasi memori transaksi tinggi mencapai batas generation heap, Serial GC memblokir seluruh pemrosesan event loop. Rekomendasi: (1) Tuning heap size menggunakan `-Xmx` dan `-Xms` yang seimbang; (2) Migrasi ke Oracle GraalVM Enterprise untuk memanfaatkan **G1 GC Native** jika aplikasi high-concurrency memory-intensive; atau (3) Evaluasi apakah HotSpot JVM C2 lebih cocok untuk use-case komputasi throughput tinggi jangka panjang tersebut.
13. **Solusi Skenario C**: `BatchSpanProcessor` OpenTelemetry bersifat asynchronous dan menyimpan spans di memori buffer sebelum di-flush secara periodik via network OTLP. Ketika Kubernetes mengirim sinyal `SIGTERM`, aplikasi Substrate VM langsung mati tanpa menyelesaikan batch flush. Solusinya: Implementasikan *Shutdown Hook* eksplisit di Java yang memanggil `sdkTracerProvider.shutdown()` atau `sdkTracerProvider.forceFlush()` dan pastikan `terminationGracePeriodSeconds` di Kubernetes memberikan jeda waktu cukup (minimal 10 detik).

---

### 16. Summary

1. **Substrate VM Paradigm**: GraalVM Native Image menukar fleksibilitas dynamic runtime JVM dengan kecepatan eksekusi instan (< 50ms) dan footprint memori minimal via *Ahead-Of-Time (AOT)* compilation dan *Closed-World Assumption*.
2. **Deterministic Metadata**: Dynamic features (Reflection, JNI, Resources, Serialization) memerlukan **Reachability Metadata**. Gunakan GraalVM Tracing Agent selama integrasi testing otomatis untuk mencegah runtime exception fatal di level produksi.
3. **Observability Native Compatibility**: Ganti dynamic bytecode Java Agent dengan **OpenTelemetry Direct Native SDK** dan Micrometer compile-time instrumentation untuk mendistribusikan context tracing secara deterministik.
4. **Cloud-Native Hardening**: Kombinasi executable binary native dengan **Google Distroless container** menghasilkan image container ultra-minimalis (< 50MB), meminimalkan attack surface, serta menghilangkan cold start penalties pada arsitektur Kubernetes auto-scaling.