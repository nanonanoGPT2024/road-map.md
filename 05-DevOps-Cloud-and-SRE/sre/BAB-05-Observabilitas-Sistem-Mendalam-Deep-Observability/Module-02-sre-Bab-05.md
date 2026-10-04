# BAB 05: Observabilitas Sistem Mendalam (Deep Observability)
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengoperasikan arsitektur pipeline telemetri terdistribusi skala enterprise menggunakan OpenTelemetry (OTel) Collector dengan mekanisme *tail-based sampling*, *memory limiter*, dan *batching*.
- Mengimplementasikan propagasi konteks terdistribusi (*distributed context propagation*) lintas batas proses menggunakan standar W3C Trace Context pada protokol HTTP/REST dan gRPC.
- Mengonfigurasi mitigasi *high-cardinality explosion* pada metrik Prometheus/Mimir dan log OpenSearch/Loki melalui teknik transformasi data OTel OTTL (*OpenTelemetry Transformation Language*).
- Menghubungkan tiga pilar observabilitas (Traces, Metrics, Logs) secara atomik dengan *Continuous Profiling* (Pyroscope/Parca) dan eBPF (*Extended Berkeley Packet Filter*) untuk visibilitas tingkat kernel tanpa memodifikasi kode sumber.
- Merancang arsitektur penyimpanan observabilitas multi-tier dengan strategi retensi berbasis nilai teknis dan optimasi biaya (*cost-to-value governance*).

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib memahami:
- **Konsep Dasar Observabilitas**: Perbedaan fundamental antara Monitoring (Black-box) dan Observability (White-box).
- **Protokol Jaringan**: Pemahaman mendalam tentang HTTP/1.1, HTTP/2, gRPC frame lifecycle, dan manipulasi TCP headers.
- **Sistem Terdistribusi**: Mekanisme asinkron (Kafka/RabbitMQ), RPC, dan arsitektur microservices.
- **Dasar Linux Kernel**: Pengetahuan tentang system calls (`sys_enter`, `sys_exit`), cgroups v2, dan namespace.
- **Bahasa Pemrograman & Runtime**: Pemahaman intermediate pada Go atau Java (memory management, runtime scheduling, concurrency).

---

### 3. Concept & Internal Architecture (Mendalam)

Observabilitas modern tingkat enterprise menolak pendekatan isolasi pilar (*siloed telemetry*). Fokus arsitektur bergeser ke **Correlated High-Resolution Telemetry Pipeline**.

```
[ Application Runtime / eBPF Engine ]
               │
               ▼ (OTLP over gRPC/Protobuf)
┌────────────────────────────────────────────────────────┐
│         OpenTelemetry Collector (Agent Layer)          │
│  - Memory Limiter Processor                            │
│  - Batching & Resource Detection                       │
└──────────────────────┬─────────────────────────────────┘
                       │
                       ▼ (Routing by Tenant/TraceID)
┌────────────────────────────────────────────────────────┐
│     OpenTelemetry Collector (Gateway/Cluster Layer)    │
│  - Tail-based Sampling Processor                       │
│  - Transform Processor (OTTL Redaction & Normalization)│
│  - Load Balancing Exporter                             │
└──────────┬─────────────────┬──────────────────┬────────┘
           │                 │                  │
           ▼                 ▼                  ▼
  ┌─────────────────┐ ┌─────────────┐ ┌──────────────────┐
  │ Metrics Backend │ │ Trace Engine│ │ Log Analytics    │
  │ (Mimir/Thanos)  │ │ (Tempo/Jae) │ │ (Loki/ClickHouse)│
  └─────────────────┘ └─────────────┘ └──────────────────┘
           ▲                 ▲                  ▲
           └─────────────────┼──────────────────┘
                             │
                  [ Continuous Profiler ]
                  (Pyroscope / Parca eBPF)
```

#### A. Data Pipeline Anatomy pada OpenTelemetry Collector
OTel Collector dibangun di atas model pipeline asinkron berbasis *pipeline stages*:
1. **Receivers**: Komponen *push* (gRPC/HTTP OTLP receiver) atau *pull* (Prometheus scraper). Data dialirkan ke internal pipeline dalam format in-memory `pdata` (Pluggable Data Model) tanpa alokasi memori berlebih via direct pointer passing.
2. **Processors**: Dieksekusi secara sekuensial:
   - `memory_limiter`: Menggunakan dynamic memory check dari Go runtime (`runtime.ReadMemStats`). Jika memori mendekati batas *hard limit*, processor memicu backpressure (mengembalikan status code `UNAVAILABLE` ke sender) dan mengeksekusi *data dropping* terjadwal untuk mencegah `OOMKilled`.
   - `transform` (OTTL): Membedah payload `pdata`, memangkas label ber-kardinalitas tinggi, dan melakukan *PII scrubbing* via regex level binary.
   - `tail_sampling`: Mengakumulasi rentang trace dalam *in-memory cache* selama rentang waktu $T$ (misal: 30 detik) berdasarkan `trace_id`. Keputusan sampling (simpan/buang) dieksekusi **hanya setelah** seluruh span dalam trace selesai atau ditemukan span dengan status `Error` atau latensi $\ge \text{SLO Threshold}$.
3. **Exporters**: Mengonversi `pdata` ke format target backend (Tempo, Prometheus remote write, ClickHouse) dengan memanfaatkan buffer retry terdistribusi dan *connection pool reuse*.

#### B. Propagasi Konteks (Context Propagation)
Transmisi metadata trace lintas layanan mengandalkan injeksi dan ekstraksi spesifikasi W3C Trace Context:
- **`traceparent`**: Berukuran 4-part string format: `version-trace_id-parent_id-trace_flags`
  - Contoh: `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`
  - `01` menandakan trace di-sample (*recorded*).
- **`tracestate`**: Menyimpan metadata spesifik vendor/tenant berupa key-value pairs (misal: `congo=t61rcWkgMzE,rojo=00f067a`).

#### C. Continuous Profiling & eBPF Telemetry
Continuous profiling modern tidak menggunakan instrumentasi manual kode, melainkan memanfaatkan interrupt timer kernel Linux (via `perf_event_open` syscall):
1. Kernel menginterupsi eksekusi CPU setiap interval tetap (misal: 100 Hz / 10ms per thread).
2. Engine profiling (seperti Parca atau Pyroscope) membaca *Instruction Pointer* (IP) dan menelusuri Frame Pointer / DWARF debug information untuk mengkonstruksi stack trace.
3. Melalui eBPF, kernel maps mengagregasikan stack trace langsung di ring buffer kernel, meminimalisir context switch dari kernel space ke user space.
4. Data divisualisasikan dalam bentuk **Flame Graph**, yang dipetakan secara horizontal berdasarkan total alokasi memori (*alloc_space/inuse_space*) atau pemakaian CPU (*cpu_time*).

---

### 4. Why & What

| Dimensi | Observabilitas Tradisional | Deep Observability Enterprise |
| :--- | :--- | :--- |
| **Mekanisme Pengumpulan** | Scrape-based polling (Pull metrics) & log shipping agent terpisah (Logstash/Fluentd). | Unified streaming pipeline via OTel Collector & zero-overhead eBPF probes. |
| **Strategi Sampling** | *Head-based sampling* (keputusan sampling dibuat saat request dimulai; potensi kehilangan data spike latensi/error). | *Tail-based sampling* (keputusan sampling dibuat setelah request selesai; 100% trace error tersimpan). |
| **Korelasi Data** | Manual correlation menggunakan Timestamp (lemah, rawan drift clock antarmesin). | Trace-to-Metrics-to-Logs-to-Profiles correlation via field `TraceID`, `SpanID`, dan dynamic link attributes. |
| **Tingkat Visibilitas** | User-space execution code saja. | User-space runtime, system call overhead, network transport buffer, dan kernel scheduler delay. |
| **Tata Kelola Biaya** | Ingest all, pay later (biaya melonjak eksponensial seiring traffic). | Edge aggregation, Cardinality pruning, dynamic rate-limiting, and tiered storage lifecycle. |

---

### 5. How (Workflow Detail)

Alur kerja propagasi end-to-end data telemetri:

```
[Client] ──(1. HTTP Req)──► [Edge API Gateway]
                                   │
                                   ├─► (2. Inject W3C Context)
                                   ▼
                            [Service A (Go)]
                                   │
                                   ├─► (3. Extract & Mutate Span)
                                   ├─► (4. Correlate Log & Profile)
                                   │
                                   ▼ (5. gRPC Client Call with Trace Context)
                            [Service B (Node/Rust)]
                                   │
                                   ▼ (6. Send OTLP Batch via TCP)
                      [OTel Agent (DaemonSet)]
                                   │
                                   ▼ (7. Load-balance by TraceID)
                      [OTel Gateway (Cluster)]
                                   │
                                   ├─► (8. Evaluate Tail-Sampling Engine)
                                   │       ├── Latency > 1.5s? -> KEEP
                                   │       ├── Status == Error? -> KEEP
                                   │       └── Default -> 1% Random Sample
                                   ▼
                      [Target Storage Backends]
```

1. **Client Execution**: Permintaan masuk ke gateway layer tanpa trace context. Gateway menginisialisasi Root Span, men-generate `TraceID` 128-bit unik, dan menyematkan header `traceparent` pada request downstream.
2. **Context Passing**: Client SDK di Service A membaca header via `TextMapPropagator`. Context diinjeksi ke dalam Go `context.Context` internal.
3. **Log & Profile Linking**: Framework logger menginjeksi `trace_id` dan `span_id` secara otomatis ke format JSON logs. Continuous profiler membaca trace active context dari TLS (*Thread Local Storage*) dan menyematkannya ke profiling metadata (*pprof labels*).
4. **Transport**: Semua metrics, traces, dan logs dikirimkan asinkron via OTLP/gRPC port `4317` ke OTel Collector lokal (DaemonSet) untuk memangkas overhead koneksi remote.
5. **Gateway Routing**: Agent Collector mendistribusikan trace spans ke Gateway Collector menggunakan routing hash konsisten berbasis `trace_id`, memastikan seluruh spans untuk `trace_id` yang sama tiba di instans Gateway yang identik untuk evaluasi sampling.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional Skala Besar
- **Traditional Observability**: Pengawas bandara hanya menghitung jumlah penumpang yang masuk gerbang utama setiap jam (Metrics counter) dan membaca keluhan penumpang di kotak saran (Logs). Jika ada koper hilang, tidak ada cara sistematis untuk merekonstruksi rutenya.
- **Deep Observability**: Setiap penumpang dan kopernya diberi gelang RFID dengan ID global unik (**Trace ID**).
  - Setiap checkpoint (Imigrasi, X-Ray, Boarding) mencatat stempel waktu dan ID petugas (**Spans & Context Propagation**).
  - Kamera CCTV canggih (**Continuous Profiler**) merekam gerak-gerik internal saat ada antrean macet.
  - Alih-alih menyimpan jutaan jam rekaman CCTV orang yang berjalan normal, sistem hanya menyimpan rekaman penumpang yang kopernya tertinggal, sakit, atau mengalami keterlambatan ekstrim (**Tail-based Sampling**).

#### Diagram Transisi Trace & Flame Graph
```
Timeline ──► 0ms           50ms          100ms         150ms         200ms
Trace:       [ HTTP POST /checkout ----------------------------------------]
Span A:      [ AuthValidate ]
Span B:                      [ InventoryReserve ]
Span C:                                         [ ProcessPayment ----------]
                                                    │
                                                    ▼
Profile      ┌─────────────────────────────────────────────────────────────┐
(Flamegraph) │ runtime.gcBgMarkWorker (30%)                                │
             ├──────────────────────────────────────────────┬──────────────┤
             │ payment.CryptoVerifySignature (55%)          │ db.Write(15%)│
             └──────────────────────────────────────────────┴──────────────┘
```

---

### 7. Simple Example & Practical Example (Standar Industri)

#### A. Konfigurasi Produksi OTel Collector Gateway (`otel-gateway-config.yaml`)
Konfigurasi ini mendemonstrasikan tail-based sampling, dynamic routing, memory control, dan data transforming.

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
        max_concurrent_streams: 1024
      http:
        endpoint: 0.0.0.0:4318

processors:
  memory_limiter:
    check_interval: 1s
    limit_percentage: 75
    spike_limit_percentage: 20

  transform/scrub_pii:
    error_mode: ignore
    trace_statements:
      - context: span
        statements:
          - replace_pattern(attributes["http.request.body"], "password=([^&]+)", "password=REDACTED")
          - delete_key(attributes, "user.credit_card")
    metric_statements:
      - context: datapoint
        statements:
          - delete_key(attributes, "user_email")

  tail_sampling:
    decision_wait: 10s
    num_traces: 100000
    expected_new_traces_per_sec: 5000
    policies:
      [
        {
          name: drop_healthchecks,
          type: string_attribute,
          string_attribute: { key: http.target, values: [ "/healthz", "/ready" ], enabled_regex_matching: false, invert_match: true }
        },
        {
          name: sample_errors,
          type: status_code,
          status_code: { statuses: [ ERROR ] }
        },
        {
          name: sample_high_latency,
          type: numeric_attribute,
          numeric_attribute: { key: http.status_code, value_condition: { greater_than_or_equal: 500 } }
        },
        {
          name: sample_latency_outliers,
          type: latency,
          latency: { threshold_ms: 1500 }
        },
        {
          name: probabilistic_normal_traffic,
          type: probabilistic,
          probabilistic: { sampling_percentage: 2.5 }
        }
      ]

  batch:
    send_batch_size: 8192
    timeout: 5s
    send_batch_max_size: 16384

exporters:
  otlp/tempo:
    endpoint: tempo-distributor.monitoring.svc.cluster.local:4317
    tls:
      insecure: true
  prometheusremotewrite:
    endpoint: http://mimir-distributor.monitoring.svc.cluster.local:8080/api/v1/push
    external_labels:
      cluster: production-us-east-1

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, transform/scrub_pii, tail_sampling, batch]
      exporters: [otlp/tempo]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, transform/scrub_pii, batch]
      exporters: [prometheusremotewrite]
  telemetry:
    metrics:
      address: 0.0.0.0:8888
```

#### B. Implementasi Manual Instrumentasi Go Lanjutan dengan Correlation (`main.go`)

```go
package main

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go