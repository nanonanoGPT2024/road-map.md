# MODUL PEMBELAJARAN TEKNIKAL: JAVA CLOUD-NATIVE ENGINE

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** `MOD-J-10-01`
* **Mata Pelajaran/Topik:** Cloud-Native Java, Modern Observability, dan GraalVM Native Image
* **Kategori:** 02-Programming-Languages / Java
* **Prasyarat:**
  * Penguasaan Java Core (Java 17/21 LTS): Concurrency, Streams, Reflection API, dan Virtual Threads.
  * Pemahaman ekosistem build tool: Maven atau Gradle.
  * Konsep dasar containerization (Docker) dan orchestration (Kubernetes).
  * Pengetahuan networking dasar (HTTP/REST, gRPC, TCP/IP sockets).
* **Target Audience:** Senior Software Engineers, Backend Architects, DevOps/Platform Engineers yang mengelola microservices berbasis Java skala enterprise.
* **Estimasi Waktu Penyelesaian:** 12 - 16 Jam (Teori, Hands-on Lab, dan Troubleshooting Skenario).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik memiliki kapabilitas terukur untuk:
1. **Menganalisis dan Membedakan** runtime mechanics antara JVM HotSpot (JIT) dan GraalVM Native Image (AOT) dalam konteks resource constraints di cloud.
2. **Mengonfigurasi dan Mengimplementasikan** pilar observabilitas (Distributed Tracing, Custom Metrics, Structured Logging) menggunakan OpenTelemetry (OTel) Java SDK dan Micrometer.
3. **Mengatasi** batasan *Closed-World Assumption* pada GraalVM dengan memetakan dynamic features (Reflection, Dynamic Proxy, JNI) menggunakan *Reachability Metadata*.
4. **Membangun** pipeline container multi-stage Docker berbasis Distroless/Scratch yang menghasilkan artefak biner native berukuran minimal dan berkemampuan startup sub-millisecond.
5. **Mendiagnosis dan Menangani** edge case kompilasi native seperti class initialization lifecycle (`build-time` vs `run-time`), missing dynamic proxies, dan SSL CA bundle linkage.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam komputasi tradisional, JVM dirancang sebagai server monolitik jangka panjang. Paradigma HotSpot adalah **"Run, Profile, Speculate, Optimize"**:

```
+-----------------------------------------------------------------------+
| TRADISIONAL HOTSPOT JVM (Long-Lived Process)                         |
|                                                                       |
| [Bytecode] -> [Interpreter] -> [C1 Compiler (Tier 1-3)]               |
|                                     |                                 |
|                                     v                                 |
|                        [C2 Compiler (Tier 4 Peak)] <--- Profiling data|
|                                                                       |
| Karakteristik: High Startup Latency, Memory Hog, Peak Throughput Maks |
+-----------------------------------------------------------------------+
```

Model ini gagal memenuhi tuntutan arsitektur Cloud-Native modern:
* **Scale-to-Zero / Serverless:** Latensi startup 3-15 detik tidak dapat ditoleransi.
* **High-Density Orchestration (Kubernetes):** Menjalankan ratusan pod microservice yang masing-masing mengonsumsi baseline 512MB RAM adalah pemborosan biaya infrastruktur yang masif.
* **Ephemeral Instances:** Pod sering dimusnahkan dan dibuat ulang (rolling update, auto-scaling), membatalkan investasi waktu warmup JIT compiler.

Mental model harus bertransformasi menjadi **Ahead-Of-Time (AOT) Execution & Observability-by-Design**:

```
+-----------------------------------------------------------------------+
| CLOUD-NATIVE GRAALVM AOT (Ephemeral, Immutable Executable)            |
|                                                                       |
| [Source Code] -> [Bytecode] -> [Closed-World Static Analysis]         |
|                                     |                                 |
|                                     v                                 |
|                             [Substrate VM]                            |
|                                     |                                 |
|                                     v                                 |
|                           [OS Native Binary ELF]                      |
|                                                                       |
| Karakteristik: Sub-millisecond Startup, Minimal RSS, Zero Warmup     |
+-----------------------------------------------------------------------+
```

### Konsekuensi Mental Model Ini:
1. **Closed-World Assumption (CWA):** Semua kelas, method, dan field yang akan dieksekusi saat runtime HARUS dapat diidentifikasi secara statis saat build-time. Apa yang tidak terdeteksi akan dibuang (*dead-code elimination*).
2. **Shift-Left Computational Cost:** Waktu dan sumber daya CPU dialokasikan secara agresif saat *compile-time* agar runtime menjadi ramping, instan, dan deterministik.
3. **Observability As First-Class Citizen:** Pada sistem microservices terdistribusi dengan ratusan container native yang hidup-mati dengan cepat, ketiadaan tracing terstandarisasi (W3C TraceContext) dan metrik presisi mengakibatkan sistem berada dalam kondisi "kebutaan operasional".

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Kompilasi GraalVM AOT vs Eksekusi Tradisional

```
[Java Source (.java)]
        |
        v  (javac)
[Bytecode (.class)] 
        |
        +-----------------------------------+
        |                                   |
        v                                   v
   [HotSpot JVM]                    [GraalVM native-image]
        |                                   |
 +---------------+                  +---------------+
 | - ClassLoader |                  | - Points-To   | <--- [Reachability Metadata]
 | - Interpreter |                  |   Analysis    |      (reflection-config.json)
 | - C1/C2 JIT   |                  | - Dead Code   |
 | - Full GC     |                  |   Elimination |
 +---------------+                  +---------------+
        |                                   |
        v                                   v
[Dynamic Machine Code]              [Substrate VM + App]
 (in-memory at runtime)                     |
                                            v
                                   [Standalone Native Binary]
                                   (Self-contained OS Executable)
```

### 2. End-to-End Distributed Telemetry Pipeline

```
+-----------------------------------------------------------------------------+
| KUBERNETES POD: java-cloud-native-service                                    |
|                                                                             |
|  [Incoming HTTP Req]                                                        |
|         | (Traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01)
|         v                                                                   |
|  +-----------------------------------------------------------------------+  |
|  | OpenTelemetry Tracing Filter / Interceptor                            |  |
|  |  - Extract W3C Context -> Activate Span in Context                    |  |
|  +-----------------------------------------------------------------------+  |
|         |                                                                   |
|         v                                                                   |
|  +-----------------------------------------------------------------------+  |
|  | Application Business Logic                                            |  |
|  |  - MeterRegistry (Micrometer Counter/Timer Update)                    |  |
|  |  - Structured Logging with TraceID & SpanID via SLF4J/Logback (MDC)   |  |
|  +-----------------------------------------------------------------------+  |
|         |                                                                   |
|         +-----------------------+-------------------------+                 |
|                                 |                         |                 |
|                                 v                         v                 |
|                     [BatchSpanProcessor]       [Prometheus Endpoint]        |
|                     (Buffer in Memory)          (Scrape: /actuator/prometheus)|
|                                 |                         |                 |
+---------------------------------|-------------------------|-----------------+
                                  | (OTLP/gRPC)             | (HTTP Scrape)
                                  v                         v
                   +------------------------+   +-----------------------+
                   | OpenTelemetry Collector|   | Prometheus Server     |
                   +------------------------+   +-----------------------+
                                  |
                   +--------------+-------------+
                   |                            |
                   v                            v
          [Grafana Tempo / Jaeger]       [Grafana Dashboard]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Substrate VM
GraalVM Native Image tidak menyertakan JVM HotSpot tradisional ke dalam biner biner. Sebagai gantinya, ia menanamkan **Substrate VM**, sebuah komponen runtime minimal yang ditulis dalam subset bahasa Java dan dikompilasi langsung ke native code.

Substrate VM menyediakan layanan esensial:
* **Memory Management & Garbage Collection:** Secara default menggunakan *Serial GC* (dioptimalkan untuk *low-memory footprint* dan waktu jeda pendek pada heap kecil). Versi GraalVM Enterprise/Oracle JDK mendukung *G1-like GC* untuk throughput tinggi.
* **Thread Scheduling:** Memetakan thread Java langsung ke OS native threads (`pthread` pada Linux).
* **Stack Walking & Deoptimization Mechanics:** Fitur inspeksi stack trace saat throw exception tanpa overhead runtime interpreter.

### 2. Points-To Analysis (Static Reachability)
Algoritma static analysis menelusuri graf pemanggilan metode dari *entry point* aplikasi (`public static void main`):
* Melacak semua jalur eksekusi yang *reachable*.
* Semua kelas, antarmuka, field, dan metode yang tidak dapat dibuktikan dapat diakses melalui rantai pemanggilan statis akan **dihapus secara permanen** dari biner final.
* Implikasi: Kode library pihak ketiga yang besar hanya akan dimasukkan sebagian kecil ke biner native jika sebagian besar fungsinya tidak pernah dipanggil.

### 3. Build-Time vs Run-Time Initialization
Inisialisasi kelas (`<clinit>`) dalam Java native image dapat terjadi pada dua tahap berbeda:
* **Build-Time Initialization (`--initialize-at-build-time`):**
  * Kode static initializer dijalankan oleh host JVM selama kompilasi.
  * State objek statis yang dihasilkan disimpan langsung ke dalam *Image Heap* (bagian dari segmen data biner biner).
  * Keuntungan: Eksekusi runtime instan karena setup state statis telah selesai.
  * Bahaya: Membuka koneksi socket, file descriptor, atau mengambil seed random saat build-time akan menyebabkan state beku (*frozen invalid state*) di runtime.
* **Run-Time Initialization (`--initialize-at-run-time`):**
  * Static initializer dieksekusi saat kelas pertama kali diakses pada runtime (perilaku standar HotSpot).
  * Wajib untuk kelas yang mengakses resource dinamis OS (Network, Filesystem, PID, Random).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Tiga Pilar Observabilitas Modern

#### 1. Distributed Tracing & W3C TraceContext
Untuk melacak request melintasi batas jaringan, trace context harus dipropagasikan menggunakan header standar W3C:
* `traceparent`: Format: `version-trace_id-parent_id-trace_flags`
  * Contoh: `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`
  * `trace_id` (16 bytes hex): Unik secara global untuk seluruh alur transaksi.
  * `parent_id` / `span_id` (8 bytes hex): Unik untuk unit kerja saat ini.
  * `trace_flags` (`01` = Sampled).
* `tracestate`: Menyimpan metadata vendor-specific (key-value).

#### 2. Metrik Berdimensi Tinggi (Micrometer & Prometheus)
Berbeda dari sistem metrik lama (seperti Graphite) yang menggunakan penamaan hierarkis dot-separated, metrik modern bersifat dimensional menggunakan label:
```
http_server_requests_seconds_count{method="POST",uri="/api/v1/orders",status="200"} 4521
```
* **Counter:** Nilai monoton naik (misalnya, total pesanan diproses).
* **Timer/Histogram:** Mengukur durasi sekaligus distribusi latensi (percentile: p50, p95, p99).
* **Gauge:** Nilai fluktuatif sesaat (misalnya, alokasi memori heap, pool koneksi database).

#### 3. Structured Logging dengan Context Injection
Log tidak lagi berbentuk teks bebas tak beraturan. Log modern wajib berupa JSON terstruktur yang diperkaya dengan konteks korelasi tracing melalui Mapped Diagnostic Context (MDC):
```json
{
  "timestamp": "2026-03-30T10:15:30.123Z",
  "level": "INFO",
  "thread": "main",
  "logger": "com.enterprise.order.OrderService",
  "message": "Payment processed successfully",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "order_id": "ORD-99812",
  "amount": 1500000.00
}
```

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi Java murni (core SDK) yang mendemonstrasikan integrasi OpenTelemetry Tracing dan Micrometer Metrics tanpa framework magic.

```java
package com.enterprise.telemetry;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.api.common.AttributeKey;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.StatusCode;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Scope;
import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.resources.Resource;
import io.opentelemetry.sdk.trace.SdkTracerProvider;
import io.opentelemetry.sdk.trace.export.SimpleSpanProcessor;
import io.opentelemetry.sdk.trace.export.SpanExporter;

import java.time.Duration;
import java.util.concurrent.TimeUnit;

public final class TelemetryEngine {

    private final Tracer tracer;
    private final MeterRegistry meterRegistry;
    private final Counter transactionCounter;
    private final Timer transactionTimer;

    public TelemetryEngine() {
        // 1. Inisialisasi OpenTelemetry SDK
        Resource resource = Resource.getDefault().merge(
            Resource.create(Attributes.of(AttributeKey.stringKey("service.name"), "core-payment-engine"))
        );

        SpanExporter loggingExporter = new InMemoryLoggingSpanExporter();
        SdkTracerProvider tracerProvider = SdkTracerProvider.builder()
            .addSpanProcessor(SimpleSpanProcessor.create(loggingExporter))
            .setResource(resource)
            .build();

        OpenTelemetry openTelemetry = OpenTelemetrySdk.builder()
            .setTracerProvider(tracerProvider)
            .build();

        this.tracer = openTelemetry.getTracer("com.enterprise.telemetry", "1.0.0");

        // 2. Inisialisasi Micrometer Registry
        this.meterRegistry = new SimpleMeterRegistry();
        this.transactionCounter = Counter.builder("transactions.processed.total")
            .description("Total number of processed transactions")
            .tag("env", "production")
            .register(meterRegistry);

        this.transactionTimer = Timer.builder("transactions.latency")
            .description("Latency distribution of transactions")
            .tag("env", "production")
            .publishPercentiles(0.5, 0.95, 0.99)
            .register(meterRegistry);
    }

    public void executeTrackedOperation(String transactionId, double amount) {
        Span parentSpan = tracer.spanBuilder("executeTrackedOperation")
            .setAttribute("transaction.id", transactionId)
            .setAttribute("transaction.amount", amount)
            .startSpan();

        long startTimeNs = System.nanoTime();

        try (Scope scope = parentSpan.makeCurrent()) {
            // Simulasi Business Logic
            processBusinessLogic(transactionId);
            
            parentSpan.setStatus(StatusCode.OK);
            transactionCounter.increment();
        } catch (Exception ex) {
            parentSpan.setStatus(StatusCode.ERROR, ex.getMessage());
            parentSpan.recordException(ex);
            throw ex;
        } finally {
            long durationNs = System.nanoTime() - startTimeNs;
            transactionTimer.record(durationNs, TimeUnit.NANOSECONDS);
            parentSpan.end();
        }
    }

    private void processBusinessLogic(String transactionId) {
        Span childSpan = tracer.spanBuilder("validateAndPersist")
            .startSpan();
        try (Scope childScope = childSpan.makeCurrent()) {
            Thread.sleep(20); // Simulasi delay eksekusi
            childSpan.addEvent("Database Write Completed", Attributes.of(AttributeKey.stringKey("db.table"), "transactions"));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Execution interrupted", e);
        } finally {
            childSpan.end();
        }
    }

    // Dummy exporter untuk testing konsol
    private static class InMemoryLoggingSpanExporter implements SpanExporter {
        @Override
        public io.opentelemetry.sdk.common.CompletableResultCode export(java.util.Collection<io.opentelemetry.sdk.trace.data.SpanData> spans) {
            for (var span : spans) {
                System.out.printf("[TRACE] SpanName: %s | TraceId: %s | SpanId: %s | Duration: %d ms%n",
                    span.getName(), span.getTraceId(), span.getSpanId(), 
                    Duration.ofNanos(span.getEndEpochNanos() - span.getStartEpochNanos()).toMillis());
            }
            return io.opentelemetry.sdk.common.CompletableResultCode.ofSuccess();
        }

        @Override
        public io.opentelemetry.sdk.common.CompletableResultCode flush() {
            return io.opentelemetry.sdk.common.CompletableResultCode.ofSuccess();
        }

        @Override
        public io.opentelemetry.sdk.common.CompletableResultCode shutdown() {
            return io.opentelemetry.sdk.common.CompletableResultCode.ofSuccess();
        }
    }

    public static void main(String[] args) {
        TelemetryEngine engine = new TelemetryEngine();
        engine.executeTrackedOperation("TX-10023", 450000.0);
        
        System.out.println("\n--- MICROMETER METRICS SUMMARY ---");
        System.out.println("Counter Value: " + engine.transactionCounter.count());
        System.out.println("Timer Mean Latency (ms): " + engine.transactionTimer.mean(TimeUnit.MILLISECONDS));
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis dari kode implementasi di atas:

* **Baris 29–31:** Mengonfigurasi objek `Resource`. Dalam semantic convention OpenTelemetry, entitas ini mendefinisikan metadata statis layanan (misalnya `service.name`, `service.version`, `k8s.pod.name`). Metadata ini dilekatkan ke semua telemetry data yang dihasilkan.
* **Baris 33–37:** Instansiasi `SdkTracerProvider`. Menggunakan `SimpleSpanProcessor` yang meneruskan span secara sinkron ke exporter segera setelah operasi selesai. Pada mode produksi, ini harus diganti dengan `BatchSpanProcessor` untuk meminimalkan blocking I/O pada thread worker.
* **Baris 45–54:** Setup `SimpleMeterRegistry` (Micrometer). Pembuatan counter dan timer dilakukan secara eksplisit menggunakan fluent builder. Deklarasi `.publishPercentiles(0.5, 0.95, 0.99)` menginstruksikan registry untuk secara dinamis menghitung *Quantiles* menggunakan algoritma reservoir sampling (e.g., HdrHistogram).
* **Baris 57–60:** `tracer.spanBuilder("executeTrackedOperation")` membuat representasi unit kerja. Atribut domain-specific (`transaction.id`, `amount`) disuntikkan langsung ke span.
* **Baris 64:** `try (Scope scope = parentSpan.makeCurrent())`: Menyimpan referensi span aktif ke dalam `ThreadLocalContext`. Operasi downstream berikutnya pada thread yang sama (atau reactive pipeline yang terhubung) dapat mengekstrak trace context ini secara implisit.
* **Baris 69–73:** Exception handling pattern. Jika logic gagal, status span diatur ke `StatusCode.ERROR`, dan method `recordException(ex)` merekam error stack trace sebagai OpenTelemetry Event log terstruktur di dalam span, sebelum melempar exception ke atas.
* **Baris 74–77:** Blok `finally`. Sangat krusial: `parentSpan.end()` dan perekaman durasi timer harus dieksekusi terlepas dari apakah proses berhasil atau crash. Ketiadaan invocation `.end()` akan menyebabkan *memory leak* pada span buffer dan trace yang menggantung selamanya.
* **Baris 81–93:** Menunjukkan pembuatan *Child Span* (`validateAndPersist`). Karena dieksekusi di dalam lingkup `parentSpan.makeCurrent()`, OpenTelemetry SDK secara otomatis menetapkan `parentSpan.spanId` sebagai `parent_id` dari child span ini, membentuk pohon visualisasi hierarkis di backend tracing UI.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Flash Sale Checkout Engine
* **Klien:** Platform E-Commerce Asia Tenggara.
* **Problem Statement:**
  * Saat *Flash Sale* (pukul 00:00), traffic melonjak dari 1.000 RPS menjadi 150.000 RPS dalam waktu kurang dari 30 detik.
  * Aplikasi berjalan di Kubernetes dengan JVM OpenJDK 21 HotSpot konvensional.
  * Kubernetes Horizontal Pod Autoscaler (HPA) memicu pembuatan 100 Pod baru.
  * **Kegagalan:** Pod HotSpot membutuhkan waktu **8 hingga 14 detik** untuk startup (initial class loading, Spring context initialization, HikariCP warm-up). Selama masa startup, traffic yang dialihkan ke pod tersebut mengalami *HTTP 503 Service Unavailable* dan *Connection Refused*.
  * **Resource Waste:** Setiap pod HotSpot membutuhkan batas minimum RAM 768MB (RSS) untuk beroperasi stabil tanpa terkena Linux OOM-Killer. Total RAM yang terikat: ~76GB.
  * **Visibility Vacuum:** Tidak ada trace ID yang terpropagasi saat pod crash, menyulitkan post-mortem analysis.

### Solusi Rekayasa Sistem:
1. Migrasi kompilasi service checkout ke **GraalVM Native Image** dengan konfigurasi runtime initialization yang ketat.
2. Embed runtime observabilitas berbasis **OpenTelemetry Agentless Native** + **Micrometer Prometheus**.
3. Bungkus artefak binary ke dalam container image **Google Distroless Static**.

### Hasil Transformasi:
* **Cold-start Latency:** Turun dari **11.200 ms** menjadi **18 ms** (pod siap melayani traffic seketika).
* **Baseline Memory Footprint (RSS):** Turun dari **680 MB** per pod menjadi **42 MB** per pod.
* **Autoscaling:** HPA scale-up dari 10 pod ke 100 pod terselesaikan secara mulus dalam **4 detik** (termasuk pull image & container init).
* **Tracing:** 100% request end-to-end terhubung melalui W3C TraceContext headers, diekspor via OTLP gRPC ke distributed collector.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi microservice mandiri berbasis HTTP server internal Java 21, dirancang secara khusus agar kompatibel penuh dengan GraalVM Native Image dan diekspor ke Prometheus serta OTLP backend.

### 1. Struktur Direktori Proyek

```
flash-sale-service/
├── pom.xml
├── src/
│   └── main/
│       ├── java/
│       │   └── com/enterprise/cloudnative/
│       │       ├── Application.java
│       │       └── PaymentPayload.java
│       └── resources/
│           └── META-INF/
│               └── native-image/
│                   └── reflect-config.json
└── Dockerfile
```

### 2. Kode Aplikasi (`Application.java`)

```java
package com.enterprise.cloudnative;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;
import io.micrometer.prometheusmetrics.PrometheusConfig;
import io.micrometer.prometheusmetrics.PrometheusMeterRegistry;
import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Scope;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.Executors;

public final class Application {

    private static final PrometheusMeterRegistry prometheusRegistry = 
        new PrometheusMeterRegistry(PrometheusConfig.DEFAULT);
    private static final Tracer tracer = 
        GlobalOpenTelemetry.getTracer("flash-sale-native", "1.0.0");

    public static void main(String[] args) throws IOException {
        int port = Integer.parseInt(System.getenv().getOrDefault("PORT", "8080"));
        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);

        server.createContext("/healthz", new HealthHandler());
        server.createContext("/metrics", new MetricsHandler());
        server.createContext("/api/v1/checkout", new CheckoutHandler());

        // Menggunakan Virtual Threads untuk high-throughput handling (Java 21)
        server.setExecutor(Executors.newVirtualThreadPerTaskExecutor());
        
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            System.out.println("[SHUTDOWN] Menghentikan server secara graceful...");
            server.stop(2);
        }));

        System.out.println("[BOOT] Native Server running on port: " + port);
        server.start();
    }

    static class HealthHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            byte[] response = "{\"status\":\"UP\"}".getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, response.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(response);
            }
        }
    }

    static class MetricsHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            String scrapeData = prometheusRegistry.scrape();
            byte[] response = scrapeData.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "text/plain; version=0.0.4");
            exchange.sendResponseHeaders(200, response.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(response);
            }
        }
    }

    static class CheckoutHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"POST".equalsIgnoreCase(exchange.getRequestMethod())) {
                exchange.sendResponseHeaders(405, -1);
                return;
            }

            Span span = tracer.spanBuilder("HandleCheckoutRequest").startSpan();
            long startNanos = System.nanoTime();

            try (Scope scope = span.makeCurrent()) {
                // Simulasi parsing & business transaction
                String responseBody = "{\"status\":\"SUCCESS\",\"orderId\":\"ORD-89211\"}";
                byte[] bytes = responseBody.getBytes(StandardCharsets.UTF_8);

                prometheusRegistry.counter("checkout.orders.success", "type", "native").increment();

                exchange.getResponseHeaders().set("Content-Type", "application/json");
                exchange.sendResponseHeaders(200, bytes.length);
                try (OutputStream os = exchange.getResponseBody()) {
                    os.write(bytes);
                }
                span.setAttribute("app.checkout.status", "SUCCESS");
            } catch (Exception e) {
                span.recordException(e);
                prometheusRegistry.counter("checkout.orders.failure", "type", "native").increment();
                exchange.sendResponseHeaders(500, -1);
            } finally {
                long duration = System.nanoTime() - startNanos;
                prometheusRegistry.timer("checkout.duration").record(duration, java.util.concurrent.TimeUnit.NANOSECONDS);
                span.end();
            }
        }
    }
}
```

### 3. Reachability Metadata Configuration (`reflect-config.json`)

File ini wajib ada di `src/main/resources/META-INF/native-image/reflect-config.json` jika terdapat dynamic reflection:

```json
[
  {
    "name": "com.enterprise.cloudnative.PaymentPayload",
    "allDeclaredConstructors": true,
    "allPublicConstructors": true,
    "allDeclaredMethods": true,
    "allPublicMethods": true,
    "allDeclaredFields": true,
    "allPublicFields": true
  }
]
```

### 4. Multi-Stage Distroless Dockerfile

```dockerfile
# ==========================================
# STAGE 1: Build the Native Executable
# ==========================================
FROM ghcr.io/graalvm/native-image-community:21-ol9 AS build-engine

WORKDIR /app

# Install maven wrapper / tools
RUN microdnf install -y maven findutils

COPY pom.xml .
RUN mvn dependency:go-offline -B

COPY src ./src

# Kompilasi Native Image
# Flag penjelas:
# --no-fallback: Pastikan kegagalan static analysis membatalkan build dan TIDAK mundur ke standar HotSpot
# -H:+ReportExceptionStackTraces: Tampilkan tracing lengkap saat error
RUN mvn clean package -Pnative -DskipTests

# ==========================================
# STAGE 2: Distroless Minimal Runtime
# ==========================================
FROM gcr.io/distroless/cc-debian12:nonroot

WORKDIR /

# Salin binary yang dihasilkan dari Stage 1
COPY --from=build-engine /app/target/flash-sale-service /flash-sale-service

# Konfigurasi User Non-Root untuk Keamanan Pod
USER 65532:65532

EXPOSE 8080

ENTRYPOINT ["/flash-sale-service"]
```

### 5. Kubernetes Deployment Manifest (`k8s-deployment.yaml`)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: flash-sale-native-engine
  labels:
    app: flash-sale-native
spec:
  replicas: 3
  selector:
    matchLabels:
      app: flash-sale-native
  template:
    metadata:
      labels:
        app: flash-sale-native
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: native-service
        image: enterprise/flash-sale-service:latest
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8080
        env:
        - name: PORT
          value: "8080"
        resources:
          requests:
            memory: "64Mi"
            cpu: "50m"
          limits:
            memory: "128Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8080
          initialDelaySeconds: 1
          periodSeconds: 3
        readinessProbe:
          httpGet:
            path: /healthz
            port: 8080
          initialDelaySeconds: 1
          periodSeconds: 3
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Memilih antara HotSpot JIT dan GraalVM AOT menuntut analisis kompromi arsitektural yang presisi:

| Vektor Evaluasi | Tradisional OpenJDK HotSpot (JIT) | GraalVM Native Image (AOT) |
| :--- | :--- | :--- |
| **Startup Time** | Lambat (2s – 20s tergantung dependensi) | Nyaris Instan (10ms – 50ms) |
| **Memory Footprint (RSS)** | Tinggi (Baseline 300MB – 1GB+) | Sangat Rendah (Baseline 25MB – 80MB) |
| **Peak Throughput** | **Sangat Tinggi**. Dynamic runtime profiling & de-optimizations mengoptimalkan loop secara real-time. | **Moderat hingga Tinggi**. Tidak memiliki runtime profile (kecuali menggunakan profile-guided optimization / PGO). |
| **Build Duration** | Sangat Cepat (Detik via `javac`) | Sangat Lambat (2 – 10 menit, memakan resource CPU & RAM build node masif). |
| **Dynamic Capabilities** | Penuh. Dynamic Class Loading, Bytecode instrumentation runtime (e.g., standard Java Agents). | Terbatas secara ketat. Semua dynamic reflection harus didaftarkan di metadata. Dynamic classloading dilarang. |
| **Debugging & Profiling** | Sangat Mudah (JConsole, VisualVM, JFR, Remote Debugging port 5005). | Kompleks. Membutuhkan GDB, Native Memory Tracking, atau tools level OS seperti `perf` dan `eBPF`. |
| **Ideal Workload** | Monoliths, Batch processing intensif berdurasi panjang, Stateful enterprise systems. | Serverless (AWS Lambda, Knative), Microservices skala dinamis, CLI tools. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1. **Static Initializer Trap (Build-time vs Runtime State Leaks):**
   * *Masalah:* Jika sebuah kelas memiliki deklarasi:
     ```java
     private static final String RUNTIME_HOST = System.getenv("HOSTNAME");
     ```
     Bila kelas ini diinisialisasi saat build-time (`--initialize-at-build-time`), nilai `HOSTNAME` dari build worker (misal: Docker build runner) akan **terpatri permanen** ke dalam biner biner. Saat dijalankan di pod Kubernetes, aplikasi akan membaca hostname build machine, bukan pod.
   * *Solusi:* Pastikan kelas yang membaca environment dinamis atau membuat socket network explicitly di-flag dengan `--initialize-at-run-time=com.enterprise.cloudnative.ConfigLoader`.

2. **Hilangnya Dynamic Proxies pada Serialization/RPC:**
   * Framework lama (seperti Java Native Serialization, RMI, atau library JSON lama) membuat kelas proksi secara runtime via `java.lang.reflect.Proxy`.
   * Di GraalVM, seluruh kombinasi interfaces untuk Dynamic Proxy harus didaftarkan sebelumnya di `dynamic-proxy-config.json`. Jika terlewat, eksekusi akan melempar `IllegalArgumentException: Proxy class not found`.

3. **Missing SSL/TLS Root Certificates:**
   * Di container scratch/distroless murni, GraalVM native executable membutuhkan sertifikat CA lokal untuk memverifikasi HTTPS outbound call.
   * Jika executable dikompilasi tanpa flag `-H:+InstallExitHandlers` atau flag `-H:+EnableURLProtocols=http,https`, panggilan HTTPS via `HttpClient` akan melempar `SSLException: No trust anchors found`.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Mengabaikan "Fallback Image"
* **Anti-Pattern:** Menjalankan perintah build tanpa `--no-fallback`. Jika GraalVM menemukan dynamic feature yang gagal dianalisis secara statis, ia akan diam-diam menghasilkan biner "fallback" yang memerlukan instalasi JRE penuh di host target.
* **Perbaikan:** Selalu gunakan argumen `--no-fallback` pada konfigurasi Maven/Gradle. Jika AOT gagal, build harus langsung *fail-fast*.

### Kesalahan 2: Membuat Metadata JSON Manual dari Awal
* **Anti-Pattern:** Menulis ribuan baris `reflect-config.json` secara manual untuk library eksternal. Ini memakan waktu dan rawan typo.
* **Perbaikan:** Gunakan **GraalVM Tracing Agent**. Jalankan aplikasi pada HotSpot JVM menggunakan flag:
  ```bash
  java -agentlib:native-image-agent=config-output-dir=./src/main/resources/META-INF/native-image -jar app.jar
  ```
  Lakukan automated testing/end-to-end load testing. Agent akan merekam seluruh aksi reflection aktual dan otomatis menggenerasi file metadata JSON.

### Kesalahan 3: Tidak Menangani Thread Interruption pada Shutdown
* **Anti-Pattern:** Mengandalkan Finalizers (`finalize()`) yang dilarang keras di Substrate VM, atau mengabaikan graceful shutdown pada HTTP server.
* **Perbaikan:** Gunakan runtime standard shutdown hook (`Runtime.getRuntime().addShutdownHook`) dan pastikan thread pool di-terminate menggunakan pola `.shutdown()` diikuti `.awaitTermination()`.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Standardisasi Semantic Conventions:**
   * Selalu ikuti **OpenTelemetry Semantic Conventions** untuk penamaan metrik dan tracing attribute (misal: gunakan `http.response.status_code`, bukan `http_code` atau `status`).
2. **Minimal Layer Distroless Base:**
   * Hindari menggunakan base image berbasis Ubuntu atau Alpine jika aplikasi tidak memerlukan shell runtime. Gunakan image `gcr.io/distroless/base-nossl` atau `cc-debian12` dengan non-root user ID (`nonroot:nonroot` / UID 65532) untuk menegakkan postur zero-trust container.
3. **MDC Propagation via ThreadLocal Cleanup:**
   * Jika mendistribusikan context melalui MDC SLF4J, selalu gunakan wrapper autocloseable atau blok `try-finally` untuk memastikan `MDC.clear()` dipanggil, mencegah context leaking antar worker thread di pool.
4. **Health Check Probes Segregation:**
   * Pisahkan endpoint **Liveness** (`/healthz/liveness` - hanya validasi proses running) dan **Readiness** (`/healthz/readiness` - validasi koneksi downstream seperti database/message broker). Kegagalan temporary pada DB tidak boleh mematikan pod liveness, melainkan hanya mencabutnya dari load balancer readiness.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Profile-Guided Optimization (PGO)
Kelemahan terbesar AOT dibanding JIT adalah ketiadaan runtime execution profile. Dengan Oracle GraalVM, terapkan pendekatan PGO dua langkah:
1. Bangun instrumented binary:
   ```bash
   native-image --pgo-instrument -jar app.jar -o app-pgo
   ```
2. Jalankan binary tersebut di bawah beban traffic representatif untuk menghasilkan file `default.iprof`.
3. Bangun kembali binary produksi menggunakan profil tersebut:
   ```bash
   native-image --pgo=default.iprof -jar app.jar -o app-final
   ```
   *Hasil:* Throughput biner AOT terdongkrak mendekati atau melampaui performa HotSpot C2 Compiler.

### 2. Tuning Garbage Collection Substrate VM
Native image secara default menggunakan Serial GC.
* Batasi heap secara ketat pada runtime container melalui parameter:
  ```bash
  /flash-sale-service -XX:MaximumHeapSizePercent=80 -Xmx64m
  ```
* Jika beban bersifat *high-throughput*, gunakan G1 GC (tersedia pada GraalVM Enterprise):
  ```bash
  native-image --gc=G1 -jar app.jar
  ```

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Eliminasi Attack Vector via Dead-Code Elimination:**
   * Keuntungan inheren GraalVM: Jika library yang terpasang mengandung kelas rentan (misalnya class deserialization RCE pada package Apache Commons yang tidak terpakai), analisis statis Substrate VM akan secara otomatis membuang class tersebut dari native executable.
2. **Read-Only Root Filesystem:**
   * Jalankan container pod dengan flag Kubernetes security context:
     ```yaml
     securityContext:
       readOnlyRootFilesystem: true
       allowPrivilegeEscalation: false
       runAsNonRoot: true
       runAsUser: 65532
       capabilities:
         drop:
         - ALL
     ```
3. **Penyimpanan Sertifikat Aman:**
   * Hindari hardcoding sertifikat TLS internal ke dalam image. Mount `ca-certificates` via Kubernetes ConfigMap ke `/etc/ssl/certs` secara runtime.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Structured JSON Logging dengan Trace Injection
Gunakan configuration Logback (`logback.xml`) teroptimasi native untuk memancarkan log langsung ke STDOUT dalam format JSON:

```xml
<configuration>
    <appender name="CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
        <encoder class="net.logstash.logback.encoder.LogstashEncoder">
            <includeMdcKeyName>trace_id</includeMdcKeyName>
            <includeMdcKeyName>span_id</includeMdcKeyName>
            <fieldNames>
                <timestamp>timestamp</timestamp>
                <message>message</message>
                <logger>logger</logger>
                <level>level</level>
                <thread>thread</thread>
            </fieldNames>
        </encoder>
    </appender>
    <root level="INFO">
        <appender-ref ref="CONSOLE" />
    </root>
</configuration>
```

### 2. Debugging Native Crash (Core Dump Analysis)
Jika native executable mengalami crash Segmentation Fault (`SIGSEGV`):
1. Aktifkan penulisan core dump pada host OS:
   ```bash
   ulimit -c unlimited
   ```
2. Jalankan aplikasi menggunakan argumen debugging Substrate VM:
   ```bash
   ./flash-sale-service -XX:+InstallSegvHandler
   ```
3. Analisis crash log native menggunakan GNU Debugger (GDB):
   ```bash
   gdb ./flash-sale-service core
   (gdb) bt
   ```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### GraalVM Native Image CLI Flags Esensial
```bash
# Wajib untuk production container:
--no-fallback                   # Gagal build jika AOT tidak 100% murni
-H:+ReportExceptionStackTraces  # Tampilkan diagnosa mendalam saat error analisis
--install-exit-handlers         # Menangani sinyal OS (SIGTERM/SIGINT) dengan anggun

# Lifecycle Class Initialization:
--initialize-at-build-time=pkg  # Jalankan class clinit saat build (state masuk image heap)
--initialize-at-run-time=pkg    # Tunda class clinit hingga runtime (standar JVM)

# Observability & Profiling:
-H:+DashboardAll                # Hasilkan dashboard diagnostik HTML visualisasi native image
--enable-monitoring=heapdump,jfr # Aktifkan kapabilitas flight recorder & heap dump di native
```

### Aturan Emas Native Image
1. *Apa yang tidak bisa dijangkau oleh static call-graph dari `main()`, tidak akan ada di binary executable.*
2. *Hindari static state yang mengikat file descriptor, network socket, atau randomness pada saat build-time.*
3. *Tracing agent adalah jalan terbaik untuk menghasilkan metadata reflection, hindari tebak-tebakan manual.*

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Basic (1–5)

1. **Apa perbedaan mendasar antara cara kerja JIT Compiler pada HotSpot dengan AOT Compiler pada GraalVM?**
   * A. JIT mengompilasi kode ke native sebelum aplikasi dijalankan, AOT mengompilasi kode saat runtime.
   * B. JIT menginterpretasi bytecode dan mengompilasi hot paths ke machine code secara runtime berdasarkan profiling; AOT mengompilasi seluruh aplikasi menjadi machine code sebelum runtime via static analysis.
   * C. AOT mengabaikan seluruh instruksi bytecode dan langsung membaca source code `.java`.
   * D. JIT tidak membutuhkan alokasi memori heap, sedangkan AOT memerlukan alokasi heap tak terbatas.

2. **Apa yang dimaksud dengan *Closed-World Assumption* (CWA) pada GraalVM Native Image?**
   * A. Aplikasi tidak dapat berkomunikasi ke jaringan luar (internet).
   * B. Seluruh bytecode pihak ketiga harus di-enkripsi menggunakan sertifikat SSL.
   * C. Asumsi bahwa seluruh kelas, metode, dan tipe data yang dapat diakses pada runtime harus diketahui dan dapat dianalisis secara statis pada saat kompilasi.
   * D. Host container Kubernetes harus dikunci menggunakan aturan AppArmor yang ketat.

3. **Komponen minimal pengganti runtime JVM yang disematkan ke dalam biner GraalVM Native Image adalah...**
   * A. Substrate VM
   * B. Dalvik VM
   * C. OpenJ9 Engine
   * D. CoreCLR

4. **Kapan static initializer (`<clinit>`) dieksekusi jika sebuah kelas dikonfigurasi dengan `--initialize-at-build-time`?**
   * A. Saat container pod Kubernetes berstatus `Running`.
   * B. Saat proses kompilasi native image berlangsung di build machine.
   * C. Saat kelas pertama kali di-instansiasi via operator `new` oleh thread user.
   * D. Saat application context menerima incoming HTTP request pertama.

5. **Format standar W3C TraceContext untuk distributed tracing terdiri dari dua HTTP headers utama, yaitu...**
   * A. `x-b3-traceid` dan `x-b3-spanid`
   * B. `traceparent` dan `tracestate`
   * C. `authorization` dan `x-request-id`
   * D. `otel-trace-id` dan `otel-context`

---

### Soal Intermediate (6–10)

6. **Sebuah aplikasi native mengalami crash saat parsing JSON dengan error: `NoSuchMethodException: com.model.User.<init>()`. Apa akar masalah dan solusinya?**
   * A. File JSON korup; lakukan validasi skema JSON di reverse proxy.
   * B. Substrate VM kehabisan memori; naikkan alokasi flag `-Xmx`.
   * C. Refleksi kelas `User` tidak didaftarkan saat build; daftarkan konstruktor `User` ke dalam `reflect-config.json`.
   * D. User non-root container tidak memiliki izin baca; ubah chmod file JSON ke 777.

7. **Mengapa menyimpan instance `java.security.SecureRandom` pada variabel static yang diinisialisasi saat build-time (`--initialize-at-build-time`) dikategorikan sebagai kerentanan keamanan fatal?**
   * A. Hal itu akan membatalkan proses kompilasi native image secara otomatis.
   * B. Random seed akan di-generate sekali saat build-time dan membeku di image heap; seluruh deployment pod akan menghasilkan urutan pseudorandom yang identik di runtime.
   * C. `SecureRandom` mengonsumsi memori native lebih dari 2GB.
   * D. Substrate VM tidak mendukung enkripsi kriptografi modern.

8. **Perhatikan skenario berikut: Pod native image memiliki CPU limit 0.5 core di Kubernetes. Metrik Timer Micrometer melaporkan latensi p99 sebesar 250ms, namun monitoring cgroup pod melaporkan *high throttling*. Apa tindakan perbaikan arsitektural yang paling tepat?**
   * A. Mengubah runtime GC native image menjadi Manual Free Memory.
   * B. Menghilangkan logging JSON.
   * C. Menghapus CPU limit pada manifest Kubernetes atau menaikkan limits untuk menghindari starvation pada OS thread Substrate VM.
   * D. Mengganti OpenTelemetry SDK dengan print console standar.

9. **Apa peran utama dari `BatchSpanProcessor` dibandingkan `SimpleSpanProcessor` dalam pipeline OpenTelemetry di aplikasi berkinerja tinggi?**
   * A. `BatchSpanProcessor` mengekspor span satu per satu secara sinkron di worker thread aplikasi.
   * B. `BatchSpanProcessor` mengumpulkan spans dalam buffer memori in-memory dan mengirimkannya secara asinkron dalam batch, mencegah degradasi performa I/O pada alur request utama.
   * C. `BatchSpanProcessor` mengenkripsi trace data sebelum dikirimkan ke collector.
   * D. `BatchSpanProcessor` membuang semua span yang durasinya di bawah 10 milidetik.

10. **Kapan Anda TIDAK disarankan memilih GraalVM Native Image dan sebaiknya tetap menggunakan OpenJDK HotSpot tradisional?**
    * A. Saat aplikasi dibangun untuk target AWS Lambda scale-to-zero.
    * B. Saat aplikasi berjalan di server batch processing jangka panjang yang memproses jutaan perhitungan matematis tanpa henti selama berminggu-minggu di mana peak execution throughput adalah prioritas absolut.
    * C. Saat aplikasi membutuhkan startup time di bawah 100 milidetik.
    * D. Saat infrastruktur berbasis Kubernetes dengan resource pod yang sangat terbatas (RAM < 128MB).

---

### Kunci Jawaban & Pembahasan

1. **B** — JIT memprofil aplikasi secara dinamis saat runtime; AOT menganalisis secara statis dan mengompilasi machine code saat build time.
2. **C** — Closed-World Assumption mengharuskan semua elemen kode yang dapat dipanggil telah terdefinisi saat build.
3. **A** — Substrate VM adalah komponen lightweight C-like runtime yang mengelola GC dan thread untuk executable native.
4. **B** — Inisialisasi build-time mengeksekusi `<clinit>` saat kompilasi dan menyimpan snapshot object graph ke Image Heap.
5. **B** — Standar W3C meregulasi header `traceparent` (menyimpan trace ID, parent span ID, flags) dan `tracestate` (data vendor).
6. **C** — Dynamic reflection memerlukan deklarasi eksplisit di `reflect-config.json` agar tidak dihapus oleh static analysis dead-code elimination.
7. **B** — Pembekuan instance pseudorandom generator pada image heap menyebabkan semua kontainer turunan memancarkan urutan angka acak yang sama persis, menghancurkan entropi keamanan token/kunci.
8. **C** — CPU throttling pada cgroup Linux membatasi alokasi CPU time slice, menyebabkan thread scheduler Substrate VM terhenti; menghapus/menaikkan limit menyelesaikan masalah starvation.
9. **B** — Operasi sinkron exporter (`SimpleSpanProcessor`) akan memblokir request thread bisnis; `BatchSpanProcessor` memindahkan I/O network export ke background thread.
10. **B** — Untuk komputasi jangka panjang yang stabil (*long-running monolith/data crunching*), HotSpot JIT (C2 Compiler) memiliki keunggulan throughput puncak karena optimasi dinamis berdasarkan runtime profiling yang agresif.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: "Native Telemetry Sentinel"
Bangun sebuah microservice native berbasis Java 21 yang berfungsi sebagai pemroses event transaksi perbankan berlatensi ultra-rendah, dilengkapi instrumentasi metrik dan tracing komprehensif.

### Kriteria & Spesifikasi Teknis:
1. **Core Runtime:**
   * Wajib menggunakan Java 21 LTS (gunakan `HttpServer` bawaan atau framework modern seperti Javalin/Helidon/Quarkus murni).
   * Dilarang menggunakan Spring Boot konvensional (untuk memahami arsitektur low-level native configuration).
2. **Instrumentasi Observabilitas:**
   * Implementasikan endpoint HTTP POST `/api/v1/transfer`.
   * Ekstrak W3C TraceContext dari header HTTP (`traceparent`). Jika tidak ada, buat Root Span baru.
   * Catat atribut tracing: `banking.account.source`, `banking.account.destination`, `banking.amount`.
   * Definisikan Prometheus metric:
     * `transfer_operations_total` (Counter dengan labels: `status`, `currency`).
     * `transfer_execution_time_seconds` (Timer/Histogram dengan SLA buckets).
   * Buat endpoint `/metrics` yang menyajikan metrik Prometheus dalam format scrape standar.
3. **GraalVM Native Image Packaging:**
   * Konfigurasikan dynamic reflection metadata menggunakan `reflect-config.json` untuk payload DTO transaksi transfer.
   * Buat multi-stage `Dockerfile` berbasis `gcr.io/distroless/cc-debian12:nonroot`.
   * Pastikan image biner yang dihasilkan tidak melebihi ukuran **65 MB**.
4. **Verifikasi & Validasi Keberhasilan:**
   * Aplikasi wajib beroperasi penuh dengan alokasi memory limit container **64MiB** pada Docker run:
     ```bash
     docker run --rm -m 64m --memory-swap 64m -p 8080:8080 sentinel-native:latest
     ```
   * Waktu startup tercatat pada log: `< 30ms`.
   * Lakukan pengujian 1.000 request menggunakan tool load test (misalnya: `wrk` atau `k6`), buktikan bahwa tidak terjadi `OutOfMemoryError` dan metrik terekspos secara valid di endpoint `/metrics`.