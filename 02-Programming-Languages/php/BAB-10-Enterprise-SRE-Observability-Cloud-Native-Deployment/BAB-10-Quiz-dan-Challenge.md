# BAB 10: Quiz, Challenge, & Knowledge Check
**Enterprise SRE, Observability & Cloud-Native Deployment**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: The Four Golden Signals & Karakteristik Share-Nothing PHP
Jelaskan penerapan *Four Golden Signals* (Latency, Traffic, Errors, Saturation) pada sistem berbasis PHP. Secara spesifik, bagaimana model eksekusi *share-nothing* pada PHP-FPM membedakan metrik *Saturation* dibandingkan dengan *runtime* berbasis event-loop atau multi-threaded (seperti Node.js, Go, atau Java)? Apa indikator saturasi paling kritikal yang harus dipantau pada level OS, FPM worker pool, dan cgroup container?

### Soal 1.2: Distributed Tracing & W3C TraceContext Propagation
Dalam arsitektur *distributed tracing* berbasis OpenTelemetry (OTel), jelaskan mekanisme propagasi konteks (*context propagation*) menggunakan standar W3C TraceContext (`traceparent` dan `tracestate`). Bagaimana PHP—yang prosesnya bersifat *short-lived*—meneruskan konteks penelusuran ini secara deterministik dari HTTP *ingress request*, melalui *distributed job queue* (misalnya RabbitMQ/Kafka), hingga ke *downstream microservice* tanpa kehilangan *parent-span linkage*?

### Soal 1.3: Telemetry Collection: Push vs. Pull Paradigm pada PHP
Prometheus secara default menggunakan model *pull/scrape*, sedangkan arsitektur cloud-native modern sering mengandalkan OpenTelemetry Collector dengan model *push* via OTLP (gRPC/HTTP). Jelaskan dilema mendasar implementasi Prometheus *pull model* pada PHP-FPM standar! Analisis trade-off antara penggunaan Prometheus Pushgateway, ekstensi APCu/Redis scraping exporter, dan *OTel Collector agent* yang berjalan sebagai Kubernetes *DaemonSet* atau *Sidecar*.

### Soal 1.4: 12-Factor App: Disposability & Signal Handling
Faktor ke-9 dari *Twelve-Factor App* menetapkan bahwa aplikasi harus memaksimalkan ketahanan dengan *fast startup* dan *graceful shutdown*. Uraikan alur transmisi sinyal POSIX (`SIGTERM`, `SIGQUIT`, `SIGKILL`) dari Linux kernel / Kubernetes runtime ke master process PHP-FPM hingga ke child worker. Bagaimana Anda mengonfigurasi `process_control_timeout` pada PHP-FPM dan `terminationGracePeriodSeconds` pada Kubernetes Pod Spec untuk mencegah transaksi database terputus di tengah jalan (*mid-flight request drop*)?

### Soal 1.5: Kubernetes Health Probes Semantics
Jelaskan perbedaan semantik dan operasional antara `startupProbe`, `livenessProbe`, dan `readinessProbe` dalam konteks *workload* PHP di Kubernetes. Mengapa mengeksekusi *deep dependency check* (misalnya memvalidasi koneksi PostgreSQL atau Redis) di dalam `livenessProbe` dianggap sebagai *anti-pattern* fatal yang dapat memicu *cascading failure*? Berikan desain endpoint `/healthz` vs `/readyz` yang benar secara arsitektur.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: PHP-FPM Process Manager Tuning & Cgroup OOM Killer
Sebuah Pod PHP-FPM dengan batas cgroup `limits.memory = 2Gi` mengalami *silent restart* secara berkala dengan *exit code 137* (OOMKilled). Konfigurasi pool menggunakan `pm = dynamic`, `pm.max_children = 50`, `pm.start_servers = 10`, `pm.min_spare_servers = 5`, `pm.max_spare_servers = 20`. 
- Formulasikan perhitungan kapasitas `pm.max_children` yang presisi berbasis *P95 memory consumption* per worker, *buffer cache*, dan OPcache footprint!
- Mengapa model `pm = static` lebih direkomendasikan untuk beban kerja *high-throughput cloud-native* dibandingkan `dynamic` atau `ondemand`?

### Soal 2.2: Context-Aware Structured Logging & Correlation ID
Saat mengintegrasikan Monolog dengan OpenTelemetry SDK, log transaksi harus memiliki korelasi 1:1 dengan trace APM aktif. Tunjukkan arsitektur internal *Log Processor* atau *Handler* kustom di PHP yang menginjeksi metadata berikut ke setiap *log record* JSON secara non-blocking:
- `trace_id` dan `span_id` aktif dari OTel TracerContext.
- Resource attributes (e.g., `k8s.pod.name`, `service.version`).
Bagaimana Anda menjamin bahwa operasi penulisan log berkecepatan tinggi ke `stdout` (`/dev/stdout` atau `/proc/self/fd/2`) tidak memicu *blocking I/O* atau masalah *file lock contention* (`flock`) di bawah beban 10.000 RPS?

### Soal 2.3: Socket Depletion & Ephemeral Port Exhaustion
Pada infrastruktur PHP-FPM berskala masif yang berkomunikasi dengan kluster Redis dan REST API pihak ketiga, sistem tiba-tiba mencatat error `cURL error 7: Failed to connect: Cannot assign requested address` dan `RedisException: Connection refused (errno 99)`.
- Diagnosis akar masalah pada level TCP socket state machine (fokus pada status `TIME_WAIT` dan port ephemeral Linux)!
- Evaluasi solusi mitigasi: kapan harus melakukan tuning kernel sysctl (`net.ipv4.tcp_tw_reuse`, `net.ipv4.ip_local_port_range`), kapan harus menggunakan *connection pooling* via sidecar/reverse-proxy (Envoy/PgBouncer), dan apa limitasi koneksi *persistent* (`pconnect`) pada PHP-FPM?

### Soal 2.4: Continuous Profiling & Zero-Overhead Production Debugging
Aplikasi mengalami degradasi latensi P99 dari 45ms menjadi 1.200ms di fase *peak*, namun APM distributed trace hanya menunjukkan *gap* waktu kosong tanpa span database atau network call lambat.
- Mengapa profiler tradisional seperti Xdebug dilarang keras diaktifkan di production?
- Jelaskan prinsip kerja *sampling profiler* berbasis eBPF atau signal-interrupt (misalnya SPX, Tideways, atau Pyroscope eBPF agent) dalam menangkap *wall-time* vs *CPU-time flamegraph* pada PHP dengan *runtime overhead* di bawah 1-2%!

### Soal 2.5: Zero-Downtime Rolling Update & FastCGI Socket Race Condition
Saat melakukan rolling deployment (`kubectl rollout restart deployment`) pada arsitektur Pod dual-container (Nginx + PHP-FPM via Unix Domain Socket atau Localhost TCP):
Klien mendeteksi lonjakan HTTP 502 Bad Gateway selama 3-5 detik saat pod lama diterminasi.
- Uraikan *race condition* yang terjadi antara pembaruan `EndpointSlice` pada `kube-proxy`, sinyal `SIGTERM` ke pod, penghentian proses Nginx, dan penutupan *listen socket* PHP-FPM!
- Tuliskan urutan *lifecycle preStop hook*, konfigurasi `sleep`, dan *readiness gate* yang menjamin transisi nol-kegagalan (*zero-downtime*).

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: The Thundering Herd & Cascading Failure Loop
Sebuah platform reservasi tiket mengalami *traffic spike* 50.000 RPS secara mendadak. 
- **Gejala:** Latensi melonjak ke >30 detik. Database utama PostgreSQL mengalami *connection spike* hingga mencapai `max_connections = 1000`. Kubernetes Horizontal Pod Autoscaler (HPA) mendeteksi beban CPU Pod PHP-FPM >90% dan langsung melakukan scaling dari 50 Pod ke 400 Pod dalam hitungan detik. Seketika database kolaps total, memicu error `504 Gateway Timeout` di seluruh frontend dan HPA mulai membunuh serta me-restart Pod secara liar (*crash loop*).
- **Pertanyaan Diagnostik & Solusi:**
  1. Identifikasi *anti-pattern* arsitektur autoscaling pada skenario di atas dan jelaskan konsep *positive feedback loop of doom*.
  2. Rancang strategi penanganan insiden: Bagaimana implementasi *Circuit Breaker*, *Admission Control / Rate Limiting* di level ingress/Envoy, dan *adaptive concurrency limits* di level aplikasi PHP untuk menstabilkan sistem?
  3. Bagaimana arsitektur *connection pooling* harus dirombak agar kenaikan jumlah Pod PHP tidak mendegradasi kapasitas PostgreSQL?

### Skenario B: Silent Context Loss & Data Drift pada Distributed Queue Worker
Sistem pemrosesan mutasi perbankan menggunakan Symfony Messenger yang dijalankan via *long-running CLI worker* (`php bin/console messenger:consume`) di Kubernetes.
- **Gejala:** SRE mendeteksi bahwa ribuan pesan transaksi di Kafka berhasil diproses (status HTTP/Job: ACK), namun saldo akhir pelanggan mengalami *drift* (inkonsistensi data). Pada dashboard APM Datadog/Jaeger, seluruh span transaksi dari worker tersebut tercatat di bawah satu *root trace ID* yang sama yang telah berjalan selama 7 hari, sehingga jejak riil tiap pesan transaksi individual menjadi anonim dan *untraceable*.
- **Pertanyaan Diagnostik & Solusi:**
  1. Mengapa eksekutor *long-running PHP CLI* mempertahankan konteks memori global, Static State, dan OpenTelemetry Scope jika tidak di-reset secara manual antar pesan?
  2. Tuliskan arsitektur middleware worker (*event-driven lifecycle*) yang wajib mengeksekusi: *Scope cleanup*, re-ekstraksi trace context dari Kafka message header, memory leak mitigation, dan reconnect logic untuk database driver yang *stale*.
  3. Mengapa *database transaction level isolation* (misalnya `REPEATABLE READ`) dalam kombinasi dengan koneksi PDO yang tidak pernah ditutup pada *long-running process* dapat menyebabkan worker membaca data saldo *snapshot* lama (*stale read*)?

### Skenario C: Modernisasi Runtime: Nginx + PHP-FPM vs. FrankenPHP (Worker Mode)
Divisi arsitektur sedang mengevaluasi modernisasi *runtime stack* untuk platform enterprise dengan membandingkan arsitektur tradisional:
*Pilihan 1:* Ingress -> Envoy Service Mesh -> Pod (Nginx container + PHP-FPM container)
*Pilihan 2:* Ingress -> Pod (FrankenPHP single container menggunakan Caddy webserver dengan worker mode aktif).
- **Pertanyaan Diagnostik & Solusi:**
  1. Analisis perbandingan *lifecycle* memori antara PHP-FPM (destroy state per request) vs FrankenPHP Worker Mode (persistent in-memory state mirip Node/Go). Apa risiko fatal *state bleeding* antar *concurrent request* jika developer menulis kode non-stateless (misalnya menggunakan static properties, singleton service, atau globals)?
  2. Bagaimana perbedaan jejak utilisasi CPU/Memory dan efisiensi *I/O multiplexing* antara kedua arsitektur tersebut saat menangani 20.000 *concurrent keep-alive HTTP/2 or HTTP/3 connections*?
  3. Berikan matriks evaluasi risiko (Security, Operational Complexity, Debuggability, Rollback Plan) bagi Chief Architect untuk memutuskan apakah migrasi ke FrankenPHP Worker Mode layak diambil untuk sistem finansial tier-1.

---

## 4. Chapter Challenge

### Tantangan Praktis: Architecting an Enterprise Cloud-Native Observability & High-Availability Mesh for PHP Microservices

#### 1. Deskripsi Masalah
Anda adalah Principal Infrastructure Architect untuk layanan *Payment Orchestration Core*. Layanan ini dibangun menggunakan framework PHP modern (Laravel/Symfony) dan di-deploy ke Kubernetes kluster multi-zona. Sistem saat ini memiliki visibilitas telemetri yang sangat buruk, sering mengalami *sporadic 502 errors* selama deployment, dan worker asinkron kerap mati tanpa jejak saat memproses transaksi berskala besar.

#### 2. Kebutuhan Teknis (Requirements)
Anda diminta untuk mendesain dan mengimplementasikan artefak produksi terpadu:
1. **Instrumentasi OpenTelemetry SDK (PHP):**
   - Tuliskan skrip bootstrapping integrasi OpenTelemetry SDK ke dalam aplikasi PHP.
   - Implementasikan *tracing spans* manual untuk operasi database eksternal dan HTTP outgoing calls.
   - Pastikan propagasi header `traceparent` diinjeksi secara otomatis ke outgoing HTTP client (Guzzle / Symfony HttpClient).
2. **Kubernetes Production Deployment Spec:**
   - Manifest Deployment yang mencakup Pod dual-container (Nginx reverse-proxy & PHP-FPM).
   - Pengaturan konfigurasi `securityContext` (non-root, read-only root filesystem, drop capabilities).
   - Definisi `resources` (requests dan limits) yang presisi berbasis cgroup v2.
   - Definisi `startupProbe`, `readinessProbe`, dan `livenessProbe`.
   - Implementasi `lifecycle.preStop` hook yang sempurna untuk mencegah HTTP 502/drop connection saat rolling-update.
3. **Graceful Worker Execution & Signal Trapping:**
   - Kode PHP worker (`consumer.php`) yang mendengarkan sinyal POSIX (`SIGTERM`, `SIGINT`).
   - Worker harus menyelesaikan pekerjaan aktif yang sedang berjalan sebelum keluar (*drain active job*), menolak pekerjaan baru, membersihkan koneksi resource, dan melakukan exit dengan kode status 0.
4. **SLO / Alerting Rule Specification:**
   - Tuliskan definisi Prometheus Alerting Rule (PromQL) untuk mendeteksi *Error Budget Burn Rate* (mengacu pada Google SRE Handbook) dengan target SLO Availability 99.9% pada window 1 jam dan 6 jam.

#### 3. Batasan Teknis (Constraints)
- Overhead instrumen telemetri OTel pada latensi P95 tidak boleh melebihi 3ms.
- Pod PHP-FPM tidak boleh menggunakan *root privileges* (`runAsNonRoot: true`, `runAsUser: 10001`).
- Rolling deployment harus diuji dengan skrip benchmark (`k6` atau `hey`): 0 kegagalan request (0% dropped requests) di bawah traffic konstan 2.000 RPS selama fase *rollout*.
- Log stdout harus 100% compliant dengan format OpenTelemetry Structured JSON.

#### 4. Expected Output
Dokumen deliverable teknis yang mencakup:
- [ ] Kode PHP (`telemetry_bootstrap.php`, `WorkerConsumer.php`).
- [ ] Kubernetes Manifest (`deployment.yaml`, `configmap.yaml`, `service.yaml`).
- [ ] PromQL SLO Alerting definition file (`prometheus_slo_rules.yaml`).
- [ ] Ringkasan arsitektur alur sinyal (*signal sequence diagram*) dari saat `kubectl delete pod` diinisiasi hingga worker selesai melakukan *graceful termination*.

---

## 5. Knowledge Check & Checklist

Verifikasi kesiapan engineering Anda terhadap standar SRE enterprise sebelum mempublikasikan beban kerja PHP ke sistem produksi:

### Saya harus memahami:
- [ ] Mekanisme kerja siklus hidup proses POSIX (`fork`, `exec`, `SIGTERM`, `SIGQUIT`, `SIGKILL`) di Linux kernel dan cara PHP-FPM/CLI merespons sinyal tersebut.
- [ ] Spesifikasi formal distributed tracing: W3C TraceContext (`traceparent`, `tracestate`), OpenTelemetry semantic conventions, dan propagasi context عبر batas-batas sistem (HTTP, AMQP, gRPC).
- [ ] Arsitektur internal cgroups (v1 vs v2), mekanisme alokasi memori Linux (RSS, Cache, Swap), dan penyebab deterministic pemicu Linux Out-Of-Memory (OOM) Killer pada container PHP.
- [ ] Prinsip matematis Google SRE: Perhitungan Service Level Indicator (SLI), Service Level Objective (SLO), Service Level Agreement (SLA), dan multi-window multi-burn-rate alerting.
- [ ] Konsep networking Linux/Kubernetes: TCP handshake state transition, *socket backlog queues* (`somaxconn`), ephemeral port limits, iptables/eBPF routing di kube-proxy, dan perambatan EndpointSlice.

### Saya tidak perlu menghafal:
- [ ] Nama-nama field spesifik di dalam schema raw JSON OpenTelemetry protocol (OTLP) yang di-generate oleh SDK serializer.
- [ ] Seluruh flag kompilasi konfigurasi kernel Linux untuk networking sysctl secara verbatim.
- [ ] Sintaks baris-per-baris dari library pihak ketiga; cukup pahami *runtime lifecycle hooks* dan kontrak antarmukanya.

### Saya harus bisa melakukan:
- [ ] Menghitung dan mengonfigurasi alokasi *concurrency limits* dan kapasitas pool worker PHP-FPM secara matematis berdasarkan profil konsumsi memori dan spesifikasi node Kubernetes.
- [ ] Mengonfigurasi Kubernetes manifest kelas produksi dengan probe, lifecycle hooks, dan security contexts yang sepenuhnya meniadakan HTTP 502/504 errors pada saat *auto-scaling* dan *rolling updates*.
- [ ] Mengintegrasikan OpenTelemetry SDK pada aplikasi PHP untuk mengekspor distributed traces dan metrics ke OpenTelemetry Collector tanpa menghambat eksekusi synchronous request pipeline.
- [ ] Mendiagnosis degradasi performa P99 dan *memory leak* di production menggunakan distributed traces, flamegraphs, sampling profiler (eBPF/continuous profiler), dan metric dashboard.
- [ ] Menulis script worker PHP-CLI yang tahan banting (*fault-tolerant*), mampu menangani sinyal OS, mencegah *state bleeding*, dan mengelola *lifecycle* koneksi database/cache secara deterministik.