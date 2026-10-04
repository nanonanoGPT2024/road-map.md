# Bab 09: Cloud-Native Infrastructure & Observability
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, seorang Software Architect / Principal Engineer diharapkan mampu:
1. **Mendesain Arsitektur Observability Skala Enterprise:** Merancang arsitektur ingest data telemetri (Metrics, Logs, Traces) multi-region yang sanggup menangani beban lebih dari 1.000.000 spans/detik tanpa membebani performa aplikasi (*low overhead*).
2. **Menguasai Advanced OpenTelemetry (OTel) Pipeline:** Mengonfigurasi dan mengoperasikan OpenTelemetry Collector Topologies (Agent, Gateway, Load-Balanced Aggregator) dengan *Tail-Based Sampling*, *Memory Limiter*, dan *Batch Processing*.
3. **Mengeliminasi High-Cardinality Explosion:** Menerapkan mitigasi struktural terhadap ledakan kardinalitas pada TSDB (Time Series Database) dan mendesain skema penyimpanan efisien berbasis *Columnar Store* (ClickHouse/Mimir/Tempo).
4. **Membangun Context Correlation End-to-End:** Mengintegrasikan metrik, log, dan trace secara presisi menggunakan W3C TraceContext, Baggage API, dan OpenTelemetry *Exemplars* untuk investigasi insiden sub-detik.
5. **Mengimplementasikan Observability Berbasis Kernel (eBPF):** Mengevaluasi dan mengintegrasikan instrumentasi berbasis eBPF (Extended Berkeley Packet Filter) bersamaan dengan instrumentasi berbasis SDK untuk visibilitas jaringan L4/L7 *zero-code modification*.

---

### 2. Prerequisite
Untuk memahami materi ini secara mendalam, peserta wajib menguasai:
* Pemahaman fundamental kontainerisasi (Kubernetes pods, DaemonSet, StatefulSet, CRD).
* Pengetahuan protokol komunikasi jaringan: HTTP/2, gRPC, Protobuf, dan TCP/IP fundamentals.
* Konsep dasar Tiga Pilar Observability (Module 01: Metrik, Log, Trace).
* Bahasa pemrograman Go (Golang) tingkat menengah untuk implementasi SDK telemetri.
* Pemahaman dasar arsitektur sistem terdistribusi (CAP Theorem, distributed queueing, event sourcing).

---

### 3. Concept & Internal Architecture (Mendalam)

Observability skala enterprise bukan sekadar mengumpulkan data, melainkan memproses data operasional sistem secara real-time tanpa mengganggu proses bisnis. Di skala besar, sistem observabilitas itu sendiri adalah sistem terdistribusi masif yang menghadapi tantangan *throughput*, *storage cost*, dan *query latency*.

```
+---------------------------------------------------------------------------------------------------+
|                                  APLIKASI / COMPUTE LAYER                                         |
|  +------------------------+      +------------------------+      +-----------------------------+  |
|  | Pod A (App + OTel SDK) |      | Pod B (App + OTel SDK) |      | eBPF Kernel Probe (Host L4) |  |
|  +-----------+------------+      +-----------+------------+      +--------------+--------------+  |
+--------------|-------------------------------|----------------------------------|-----------------+
               | gRPC (OTLP)                   | gRPC (OTLP)                      | Kernel Ring Buffer
+--------------v-------------------------------v----------------------------------v-----------------+
|                                 EDGE LAYER (DaemonSet Collector)                                  |
|  - In-Memory Ring Buffer                                                                          |
|  - Resource Detection & Attribute Decorator (k8s.pod.name, host.id)                               |
|  - Memory Limiter (Hard Drop / Backpressure Mechanism)                                            |
+----------------------------------------------+----------------------------------------------------+
                                               | Load-Balanced gRPC Export
+----------------------------------------------v----------------------------------------------------+
|                             GATEWAY AGGREGATOR CLUSTER (Stateful/HPA)                             |
|  +---------------------------------------------------------------------------------------------+  |
|  | TAIL-BASED SAMPLING PROCESSOR:                                                              |  |
|  | 1. Trace Buffer (Latency Window: e.g., 30s)                                                 |  |
|  | 2. Decision Engine:                                                                         |  |
|  |    - HTTP Status >= 500  -> Retain 100%                                                     |  |
|  |    - P99 Latency > 1.5s  -> Retain 100%                                                     |  |
|  |    - HTTP Status 200     -> Sample 1% (Probabilistic)                                       |  |
|  +---------------------------------------------------------------------------------------------+  |
+----------------------+-----------------------+-----------------------------+----------------------+
                       |                       |                             |
      (Metrics via PRW)|         (Traces via OTLP)                  (Logs via OTLP/ClickHouse)
+----------------------v----+ +----------------v-----------+ +---------------v----------------------+
| Prometheus / Grafana Mimir| | Grafana Tempo / ClickHouse | | Grafana Loki / ClickHouse            |
| (Block Storage: S3/GCS)   | | (Parquet/Object Storage)   | | (Indexed Streams / Chunk Storage)    |
+---------------------------+ +----------------------------+ +--------------------------------------+
```

#### Komponen Kritis Arsitektur Telemetri

1. **Edge DaemonSet Collector (Agent Topology):**
   * Berjalan di setiap node Kubernetes.
   * Bertindak sebagai *local absorption buffer* menggunakan gRPC non-blocking over UDS (Unix Domain Socket) atau localhost TCP.
   * Menambahkan metadata Kubernetes (`k8s.namespace.name`, `k8s.pod.uid`, `k8s.node.name`) melalui integrasi langsung ke Kubelet API secara lokal tanpa membebani Kubernetes API Server.

2. **Aggregator Gateway Cluster (Load-Balanced Trace Routing):**
   * Menggunakan routing berbasis trace ID konsisten (`trace_id_ratio_based` hash ring) agar seluruh span dari satu Trace ID bermuara pada worker yang sama.
   * Melakukan evaluasi *Tail-Based Sampling*. Berbeda dengan *Head-Based Sampling* (penentuan sampel di awal siklus hidup request oleh SDK), *Tail-Based Sampling* menahan seluruh span dari trace tertentu di memori selama kurun waktu tertentu ($T_{window}$ misal 30 detik) hingga transaksi selesai, lalu mengevaluasi apakah trace tersebut layak disimpan atau dibuang berdasarkan status error atau durasi eksekusi.

3. **TSDB Inverted Index vs. Columnar Storage Engine:**
   * **Prometheus/Mimir (TSDB):** Menggunakan *inverted index* untuk memetakan label set ke Time Series ID (`Series ID -> Chunk Pointer`). Sangat cepat untuk agregasi waktu, namun sangat rentan terhadap ledakan kardinalitas jika sebuah label memiliki jutaan variasi nilai unik (contoh: `user_id`, `order_id`).
   * **ClickHouse (Columnar Storage):** Menyimpan setiap kolom data (Timestamp, ServiceName, TraceID, Duration, Tags) secara terpisah di storage. Kompresi sangat tinggi (menggunakan algoritma ZSTD / Double-Delta) dan mampu memindai miliaran baris per detik secara paralel tanpa *index explosion*.

---

### 4. Why & What

| Dimensi | Implementasi Naive / Standar | Arsitektur Enterprise Produksi |
| :--- | :--- | :--- |
| **Sampling Tracing** | **Head-based 100% atau Fixed Rate (10%):** Membuang trace error jika request kebetulan tidak terpilih di awal, atau over-budget storage. | **Dynamic Tail-based Sampling:** 100% request gagal (HTTP 5xx) dan request lambat (> P95) disimpan; hanya 1% request sukses yang disimpan. |
| **Metrik Kardinalitas** | Label dinamis disuntikkan sembarangan (`user_id`, `email`) menyebabkan TSDB OOM (*Out Of Memory*). | Kebijakan *Metric Relabeling*, normalisasi *dynamic paths* (`/orders/{id}` -> `/orders/:id`), dan isolasi field unik ke Traces/Logs. |
| **Context Propagation** | HTTP headers dikirim manual; tracing terputus di Message Broker (Kafka/RabbitMQ). | OTel W3C standard injector/extractor terpasang otomatis pada producer-consumer middleware di TCP/gRPC/AMQP/Kafka headers. |
| **Korelasi Data** | Engineer menyalin TraceID secara manual dari log ke search engine tracing (manual copy-paste). | **Exemplars:** Metrik latency pada dashboard Grafana memiliki titik data interaktif yang jika diklik langsung melompat ke Trace ID spesifik. |
| **Resource Overhead** | SDK APM konvensional melakukan monkey-patching runtime secara agresif, menaikkan CPU overhead 15-25%. | Hybrid SDK + eBPF, zero-copy buffer, memory allocator yang dioptimasi, batas hard memory overhead < 2.5% CPU. |

---

### 5. How (Workflow Detail)

Alur pemrosesan telemetri dari aplikasi hingga storage analitik:

```
[Aplikasi: Request Masuk]
           │
           ▼
[OTel SDK: Inject Context] ──► Inject W3C headers (traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01)
           │
           ▼
[Span Lifecycle] ───────────► Mulai Child Span, catat StartTime, eksekusi logika bisnis
           │
           ▼
[Span Completion] ──────────► Catat EndTime, kalkulasi Duration, catat Exemplar pada Metrik Latency
           │
           ▼
[BatchSpanProcessor] ───────► Masukkan Span ke In-Memory Ring Buffer (Drop jika buffer penuh)
           │ (Flush Periodik / Batch Size tercapai)
           ▼
[gRPC Export over UDS] ─────► Kirim OTLP payload ke Local DaemonSet OTel Collector
           │
           ▼
[Local Collector] ──────────► Memory Limiter -> Filter -> Kubernetes Attribute Enricher -> Load-Balanced Exporter
           │ (Routing via hash(TraceID) % N)
           ▼
[Aggregator Cluster] ───────► Grouping Trace Spans di Memory Cache selama 30 detik
           │
           ├──► Apakah Trace mengandung status.code == ERROR? ──► YES ──► EXPORT TO STORAGE
           │
           ├──► Apakah Trace Latency > SLA Threshold (mis. 2s)? ──► YES ──► EXPORT TO STORAGE
           │
           └──► ELSE (Normal Transaction) ─────────────────────► Probabilistic 1% Random Pass
                                                                        │
                                                                        ▼
                                                             [TEMPO / CLICKHOUSE STORAGE]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem
Bayangkan observabilitas skala besar seperti **Sistem Inspeksi Kualitas pada Pabrik Mobil Otomatis**:
* **Head-Based Sampling:** Petugas gerbang memutuskan untuk memeriksa mobil ke-10, ke-20, ke-30 tanpa tahu apakah mobil tersebut rusak di ujung perakitan. Jika mobil ke-15 meledak di tengah jalan, insiden tersebut tidak terekam karena tidak masuk sampel inspeksi.
* **Tail-Based Sampling:** Setiap mobil dipasangi sensor telemetry murah selama proses berjalan. Di ujung pabrik, seluruh mobil yang mengeluarkan asap, berbunyi aneh, atau lambat berjalan **langsung dibelokkan ke hanggar investigasi mendalam (100% sampel)**. Mobil-mobil yang berjalan sempurna hanya diambil 1 dari 100 unit sebagai sampel arsip.
* **Exemplars:** Di grafik performa kecepatan pabrik, terdapat titik lonjakan warna merah. Anda mengeklik titik merah tersebut, dan sistem langsung memperlihatkan rekaman video dan blueprint perakitan dari mobil spesifik yang menyebabkan lonjakan tersebut.

#### ASCII Architectural Topology
```
Kubernetes Node 01                                Kubernetes Node 02
+------------------------------------+            +------------------------------------+
| Pod: Checkout                      |            | Pod: Payment                       |
| [OTel SDK]                         |            | [OTel SDK]                         |
|   | (UDS Socket: /var/run/otel.sock)            |   | (UDS Socket: /var/run/otel.sock)
|   v                                |            |   v                                |
| [OTel Collector - DaemonSet Agent] |            | [OTel Collector - DaemonSet Agent] |
|   |                                |            |   |                                |
+---|--------------------------------+            +---|--------------------------------+
    |                                                 |
    +------------------------+  +---------------------+
                             |  | (gRPC OTLP Route based on TraceID)
                             v  v
+--------------------------------------------------------------------------------------+
| KUBERNETES GATEWAY CLUSTER (StatefulSet OTel Collector)                              |
| Pod Aggregator-0           Pod Aggregator-1             Pod Aggregator-2             |
| [Trace Buffer Ring]        [Trace Buffer Ring]          [Trace Buffer Ring]          |
| [Tail-Sampling Engine]     [Tail-Sampling Engine]       [Tail-Sampling Engine]       |
+--------------------------------------------------------------------------------------+
         |                                |                               |
         v                                v                               v
   [Mimir (Metrics)]              [Tempo (Traces)]                [Loki (Logs)]
   + MinIO / S3 Backend           + MinIO / S3 Backend            + MinIO / S3 Backend
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Konfigurasi OpenTelemetry Collector dengan Tail-Based Sampling
File: `otel-collector-gateway.yaml`

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  memory_limiter:
    check_interval: 1s
    limit_percentage: 75
    spike_limit_percentage: 20

  tail_sampling:
    decision_wait: 10s
    num_traces: 100000
    expected_new_traces_per_sec: 5000
    policies:
      # Policy 1: Simpan semua trace yang mengalami error
      - name: drop-errors-policy
        type: status_code
        status_code: { status_codes: [ ERROR ] }
      
      # Policy 2: Simpan trace dengan durasi lambat (> 1000ms)
      - name: high-latency-policy
        type: latency
        latency: { threshold_ms: 1000 }
      
      # Policy 3: Sample 1% dari transaksi HTTP 200 normal
      - name: probabilistic-sample-policy
        type: probabilistic
        probabilistic: { sampling_percentage: 1.0 }

  batch:
    send_batch_size: 8192
    timeout: 5s
    send_batch_max_size: 10240

exporters:
  otlp/tempo:
    endpoint: tempo-distributor.monitoring.svc.cluster.local:4317
    tls:
      insecure: true

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, tail_sampling, batch]
      exporters: [otlp/tempo]
```

#### Practical Example: Instrumentasi Lanjutan pada Go Microservice dengan Prometheus Exemplar
Implementasi HTTP Server tingkat produksi yang menyuntikkan trace context, memproduksi histogram latency dengan dukungan Exemplar, dan mengalirkan telemetri secara non-blocking.

File: `main.go`

```go
package main

import (
	"context"
	"fmt"
	"math/rand"
	"net/http"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go