# BAB 10: Quiz, Challenge, & Knowledge Check
**Observability, Cloud-Native Deployment & GraalVM Native Image**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Closed-World Assumption (CWA) vs. Open-World Assumption (OWA):**  
   Jelaskan secara arsitektural perbedaan mendasar antara model eksekusi HotSpot JVM (Open-World Assumption) dan GraalVM AOT Compilation (Closed-World Assumption). Bagaimana CWA membatasi kapabilitas dinamis Java seperti Reflection, Dynamic Class Loading, JNI, dan Dynamic Proxies pada saat runtime?
2. **Context Propagation dalam Distributed Tracing:**  
   Bagaimana standar W3C Trace Context (`traceparent` dan `tracestate`) bekerja dalam melacak request yang melintasi multiple service boundaries? Apa implikasi teknisnya ketika request berpindah thread melalui *thread pool*, *reactive stream*, atau *virtual thread* (`java.lang.VirtualThread`), dan bagaimana tracing library mempertahankan *Trace State* tanpa kebocoran memori?
3. **Container-Aware Memory Management:**  
   Sebelum mekanisme `-XX:+UseContainerSupport` diimplementasikan secara matang, mengapa JVM sering mengalami `OOMKilled` (Exit Code 137) di lingkungan Linux Container (Docker/Kubernetes)? Jelaskan bagaimana JVM membaca batas alokasi memori melalui subsistem cgroups (`cgroups v1` vs `cgroups v2`) dan bagaimana perhitungan `-XX:MaxRAMPercentage` diturunkan menjadi Max Heap (`-Xmx`).
4. **Karakteristik Garbage Collection pada GraalVM Native Image:**  
   Bandingkan arsitektur Garbage Collector default pada GraalVM Native Image (Community Edition: *Serial GC*) dengan HotSpot GC modern (seperti *G1* atau *ZGC*). Mengapa *latency profile* dan *peak throughput* dari native image bisa tertinggal dibandingkan HotSpot JVM yang telah mencapai fase *steady-state*, meskipun startup time dan footprint memori native image jauh lebih unggul?
5. **Observability: Metrics Aggregation vs. High-Cardinality Tracing:**  
   Dalam perancangan metrik cloud-native (menggunakan OpenTelemetry atau Micrometer/Prometheus), mengapa Anda harus menghindari penyertaan atribut dengan kardinalitas tinggi (seperti `user_id`, `order_id`, atau `email`) ke dalam *dimensional metrics (tags)*? Apa dampak internalnya terhadap struktur data memori TSDB (Time Series Database), dan bagaimana Anda membagi peran antara *Metrics* dan *Distributed Traces* untuk data berdimensi tinggi?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **SubstrateVM Static Analysis & Tracing Agent:**  
   Sebuah aplikasi Java yang dikompilasi menjadi GraalVM Native Image mengalami `ClassNotFoundException` atau `NoSuchMethodException` saat runtime untuk kelas yang dipanggil via Jackson `ObjectMapper`. Mengapa compiler tidak mendeteksi kebutuhan ini saat *build time*, dan bagaimana cara kerja `native-image-agent` (Tracing Agent) dalam merekam metadata refleksi ke dalam format JSON (`reflect-config.json`, `serialization-config.json`)?
2. **Profile-Guided Optimization (PGO) pada GraalVM:**  
   Kompilasi AOT murni kehilangan keuntungan runtime profiling yang dimiliki JIT Compiler (C2). Jelaskan siklus kerja *Profile-Guided Optimization (PGO)* pada GraalVM Enterprise/Oracle GraalVM: mulai dari pembuatan *instrumented binary*, pengumpulan file `.iprof`, hingga kompilasi AOT final. Optimasi spesifik apa yang dihasilkan oleh PGO terhadap *inlining heuristics* dan *branch prediction*?
3. **MDC (Mapped Diagnostic Context) Leaks pada Virtual Threads:**  
   Ketika mengadopsi Java 21 Virtual Threads pada framework berbasis thread-per-request konvensional, penggunaan `ThreadLocal` untuk SLF4J MDC (Mapped Diagnostic Context) dapat menimbulkan masalah degradasi performa atau jejak log yang tercampur (*log pollution*). Analisis akar masalah struktural dari `ThreadLocal` pada jutaan Virtual Threads, dan jelaskan bagaimana `ScopedValue` (JEP 446/481) menyelesaikan problem overhead memori dan *immutability* konteks eksekusi.
4. **Kubernetes Probe Tuning vs. JVM JIT Warm-up:**  
   Sebuah microservice berbasis Spring Boot pada Kubernetes sering gagal melewati `readinessProbe` dan mengalami *CrashLoopBackOff* saat menerima lonjakan trafik (*pod autoscaling* via HPA). Padahal, memori dan CPU limit sudah diset cukup tinggi. Analisis korelasi antara *CPU throttling* (CFS Quota), proses JIT compilation (Tiered Compilation C1/C2), dan penentuan nilai `initialDelaySeconds`, `failureThreshold`, serta pemanfaatan `startupProbe` untuk mencegah *premature traffic routing*.
5. **Native Memory Tracking (NMT) & Metaspace Debugging:**  
   Pod Kubernetes microservice Java Anda terbunuh oleh kernel Linux karena melanggar *container memory limit* (misal: pod limit 2GiB), padahal flag JVM telah diatur `-Xmx1200m`. Bagaimana Anda memanfaatkan *Native Memory Tracking* (`-XX:NativeMemoryTracking=summary|detail` dan `jcmd <pid> VM.native_memory baseline/detail.diff`) untuk mengidentifikasi kontributor memori *off-heap* (seperti Metaspace, GC Overhead, DirectByteBuffers, Thread Stacks, dan JIT CodeCache)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Cold-Start Spike & CPU Throttling Cascade
* **Konteks:** Sistem *Flash Sale* e-commerce memicu Kubernetes Horizontal Pod Autoscaler (HPA) untuk menambah pod dari 10 menjadi 100 replika dalam waktu 2 menit. Microservice ditulis menggunakan OpenJDK 21 HotSpot biasa dengan container CPU limit sebesar `1000m` (1 core) per pod.
* **Gejala:** Pod-pod baru yang berstatus `Running` menerima lonjakan trafik HTTP secara langsung. Seketika, response time API melonjak dari 15ms menjadi 8.000ms. Metrik Prometheus menunjukkan utilisasi CPU mencapai 100% dari quota (CFS Quota Throttling mencapai 65%), dan sebagian pod mati mendadak dengan status `OOMKilled`. Pod yang sudah lama hidup (warm pods) tetap berjalan normal.
* **Pertanyaan Diagnostik:**
  1. Identifikasi apa yang terjadi di dalam JVM runtime selama 60 detik pertama pod menerima trafik tinggi dengan alokasi CPU terbatas (1 core).
  2. Jelaskan interaksi antara C1/C2 Compiler Threads, Class Loading, dan alokasi resource CFS (Completely Fair Scheduler) Linux.
  3. Rancang strategi remediasi: Apa yang harus diubah dari sisi konfigurasi Kubernetes probes, JVM compilation flags (misal: `-XX:TieredStopAtLevel`), resource limits (burstable vs guaranteed), atau migrasi ke GraalVM Native Image?

### Skenario B: Broken Trace Context pada Distributed Asynchronous Pipeline
* **Konteks:** Sebuah microservice *Order Settlement* mengonsumsi pesan dari Apache Kafka, melakukan beberapa panggilan gRPC non-blocking menggunakan Netty event loop, lalu mengeksekusi asynchronous batch update ke database melalui thread pool terpisah (`ThreadPoolTaskExecutor`).
* **Gejala:** Tim SRE mendapati bahwa pada Jaeger/Grafana Tempo, trace terputus (*broken trace*). Span dari Kafka Consumer muncul sebagai root span baru tanpa relasi ke producer span dari API Gateway. Selain itu, span gRPC downstream dan database queries memiliki `trace_id` yang berbeda sama sekali atau tidak memiliki metadata trace (`trace_id: 0000000000000000`). Log di Datadog tidak dapat dikorelasikan karena MDC kosong.
* **Pertanyaan Diagnostik:**
  1. Pada titik mana saja konteks OpenTelemetry terdistorsi atau hilang dalam alur eksekusi asinkronus multi-threaded di atas?
  2. Bagaimana cara mengimplementasikan *Trace Context Extraction* dari Kafka Headers secara manual menggunakan OpenTelemetry API (`W3CTraceContextPropagator`) jika auto-instrumentation gagal?
  3. Bagaimana pola wrapping atau decorator yang benar untuk `ExecutorService` atau Reactor/Netty pipelines agar `Context` OpenTelemetry tetap terikat (*bound*) ke context execution saat terjadi *thread hopping*?

### Skenario C: Architectural Trade-off – GraalVM Native Image vs. HotSpot C2 + ZGC
* **Konteks:** Anda adalah Principal Architect yang memimpin evaluasi migrasi untuk core engine sistem kliring finansial real-time yang memproses 50.000 transaksi per detik. Karakteristik sistem membutuhkan latensi p99 di bawah 5 milidetik secara konsisten selama 24/7. Tim mempertimbangkan dua jalur:
  * *Opsi 1:* Kompilasi ke GraalVM Native Image (Oracle Enterprise edition dengan PGO dan G1 Native GC).
  * *Opsi 2:* Menjalankan OpenJDK 21 HotSpot dengan Generational ZGC, alokasi memori berlimpah, dan proses warm-up terisolasi sebelum dimasukkan ke target load balancer.
* **Pertanyaan Diagnostik:**
  1. Bandingkan trade-off performa puncak (*peak throughput*) dan p99 latency guarantees antara kedua arsitektur tersebut setelah fase warm-up selesai. Mengapa HotSpot C2 dengan Generational ZGC berpotensi mengungguli GraalVM Native Image dalam skenario latency-critical ultra-high throughput?
  2. Tinjau dari aspek Developer Experience (DevEx) dan CI/CD Lifecycle: Berapa estimasi waktu build time, konsumsi resource runner CI/CD, dan kompleksitas debugging (dumping heap, profiling JFR) pada Native Image versus HotSpot?
  3. Berikan keputusan akhir arsitektural yang didukung justifikasi berbasis metrik: Dalam kondisi spesifik apa Opsi 1 menjadi pemenang mutlak, dan dalam kondisi apa Opsi 2 wajib dipertahankan?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Resilience, Zero-Cold-Start Microservice dengan GraalVM Native Image & OpenTelemetry End-to-End

#### Problem Statement
Anda ditugaskan merancang, membangun, dan menguji sebuah *high-throughput payment webhook processor* yang harus di-deploy ke Kubernetes. Service ini harus mampu menangani lonjakan trafik mendadak (*zero cold-start penalty*), memiliki observability end-to-end yang mengekspor Traces dan Metrics ke OpenTelemetry Collector, serta memiliki footprint memori RSS di bawah 64 MB per pod pada saat idle.

#### Requirements
1. **Framework & Runtime:**  
   Gunakan Java 21 LTS dengan framework pendukung Native Image kelas enterprise (Quarkus 3.x, Micronaut 4.x, atau Spring Boot 3.x dengan Spring AOT).
2. **GraalVM Native Image Compilation:**  
   Aplikasi harus dapat dikompilasi menggunakan GraalVM Native Build Tools menghasilkan single executable binary di dalam container *distroless* atau *alpine-based* minimal.
3. **Observability Integration:**  
   - Integrasikan OpenTelemetry SDK / Micrometer Tracing.
   - Implementasikan context propagation manual dan otomatis untuk request inbound (REST), database query (H2/PostgreSQL non-blocking/reactive atau JDBC via connection pool), dan outbound HTTP client.
   - Ekspor data spans dan metrics melalui protokol OTLP/gRPC ke OpenTelemetry Collector.
   - Inject `trace_id` dan `span_id` secara konsisten ke dalam structured JSON logs.
4. **Cloud-Native Hardening:**  
   - Konfigurasikan Kubernetes Manifest dengan *cgroups v2-aware* resource allocation (Requests/Limits).
   - Implementasikan *Graceful Shutdown* yang memastikan transaksi in-flight selesai diproses dalam window shutdown Kubernetes (`preStop` hook & `terminationGracePeriodSeconds`).
   - Sediakan endpoint `/health/liveness` dan `/health/readiness` yang memvalidasi koneksi dependensi kritis secara non-blocking.

#### Constraints
* **Base Container Image:** Tidak boleh menggunakan base image yang mengandung JDK/JRE runtime utuh saat fase produksi. Binary native harus berjalan di image minimal (`distroless/static-debian12` atau `scratch`).
* **Reflection & Dynamic Serialization:** Aplikasi harus menggunakan setidaknya satu library pihak ketiga yang bergantung pada refleksi atau Jackson serialization, dan Anda diwajibkan menulis atau men-generate *reachability metadata* secara benar tanpa runtime crash.
* **Resource Ceiling:** Pod Kubernetes dibatasi pada CPU Limit: `500m` dan Memory Limit: `128Mi`. Heap native tidak boleh melebihi batas ini di bawah pengujian beban 500 RPS.

#### Expected Output
1. **Source Code & Configuration:**
   - Direktori `src/` yang berisi kode endpoint, DTO, dan integrasi HTTP Client/DB.
   - File konfigurasi reachability metadata: `reflect-config.json`, `resource-config.json` (atau plugin configuration yang sesuai jika di-generate via tracing agent).
   - `Dockerfile` multi-stage: Stage 1 (Build native image dengan tracing agent atau metadata generation), Stage 2 (Minimal distroless runtime container).
2. **Deployment Artifacts:**
   - File `deployment.yaml` yang mencakup resource limits, liveness/readiness probes, security context (non-root), dan OTLP exporter environment variables.
3. **Observability Evidence:**
   - Cuplikan JSON Log yang memuat field: `timestamp`, `level`, `message`, `trace_id`, `span_id`.
   - File JSON Trace Dump atau screenshot Jaeger/Tempo yang membuktikan *parent-child relationship* span dari inbound HTTP -> internal service -> outbound call tidak terputus.
4. **Verification Report:**
   - Hasil benchmark: Startup time (dalam milidetik), Memory RSS consumption (idle vs peak 500 RPS), dan latensi p95/p99.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Batasan teknis dan trade-off mendasar dari *Closed-World Assumption* (CWA) pada GraalVM Native Image dibanding HotSpot JIT.
- [ ] Anatomi propagasi konteks OpenTelemetry (W3C Trace Context, `traceparent`, format span header) melintasi protokol HTTP, gRPC, dan Message Broker (Kafka/RabbitMQ).
- [ ] Mekanisme deteksi CPU dan Memory limit oleh JVM di dalam Linux Container via cgroups (`cpu.cfs_quota_us`, `memory.max` pada cgroups v2).
- [ ] Perbedaan fundamental lifecycle logging MDC antara traditional OS threads, thread pool execution, dan Java 21 Virtual Threads (`ScopedValue`).
- [ ] Mengapa Native Image menghasilkan startup time super cepat dan memory footprint kecil, tetapi membutuhkan runtime tuning berbeda (PGO, GC tuning) untuk menyamai peak throughput HotSpot JIT.
- [ ] Arsitektur internal SubstrateVM (komponen runtime native yang disematkan ke dalam compiled native binary).

### Saya tidak perlu menghafal:
- [ ] Seluruh skema sintaksis JSON manual untuk `reflect-config.json`, `jni-config.json`, dan `proxy-config.json` (Gunakan `native-image-agent` untuk men-generate file ini).
- [ ] Spesifikasi byte-level encoding dari protokol binary OTLP (Cukup pahami model data gRPC/Protobuf dan HTTP/JSON transport-nya).
- [ ] Flag internal compiler GraalVM yang berstatus eksperimental (`-H:+...`) di luar parameter operasional standar production.

### Saya harus bisa melakukan:
- [ ] Menjalankan GraalVM Tracing Agent (`-agentlib:native-image-agent`) pada pengujian integration test HotSpot untuk mengekstraksi Reachability Metadata secara otomatis.
- [ ] Membaca dan menganalisis thread dump, heap histogram, dan Native Memory Tracking (`jcmd <pid> VM.native_memory`) untuk membedakan kebocoran memori heap vs off-heap.
- [ ] Mengonfigurasi distributed tracing OpenTelemetry SDK secara programmatic atau agentless pada aplikasi Java, memastikan propagasi konteks tidak putus pada thread boundaries.
- [ ] Menulis multi-stage `Dockerfile` untuk memproduksi container GraalVM Native Image berukuran ultra-kecil (distroless) dengan tingkat keamanan tinggi (non-root execution).
- [ ] Melakukan troubleshooting kegagalan Kubernetes pods (analisis penyebab OOMKilled code 137, CFS CPU throttling, liveness probe flapping, dan readiness delay) menggunakan data metrik dan log sistem.