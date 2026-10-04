## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** ARC-06-09-01
* **Nama Modul:** Cloud-Native Infrastructure & Observability: Containerization, Kubernetes Orchestration, Service Mesh, Telemetry Three Pillars (Metrics, Logs, Traces), OpenTelemetry
* **Kategori:** 06-Architecture-and-System-Design
* **Tingkat Kesulitan:** Advanced / Lintas-Disiplin Arsitektur
* **Prasyarat:** Pemahaman arsitektur microservices, networking dasar (TCP/IP, HTTP/2, gRPC), Linux OS fundamentals (namespaces, cgroups), dan distributed systems fundamentals.
* **Estimasi Waktu Belajar:** 16 Jam (Teori, Desain Arsitektur, Analisis Kode, dan Hands-On Lab)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Principal Architect / Lead Architect diharapkan mampu:

1. **Mengevaluasi dan Mendesain Runtime Fondasi Cloud-Native:** Menentukan batas isolasi komputasi berbasis OCI (*Open Container Initiative*), cgroups v2, dan Linux namespaces untuk menjamin multi-tenancy, efisiensi resource, dan determinisme aplikasi.
2. **Merancang Topologi Orkestrasi Kubernetes Skala Enterprise:** Mengonstruksi arsitektur kluster Kubernetes berbasis *declarative reconciliation loop*, mencakup *custom controllers*, *pod scheduling constraints*, *topology spread constraints*, dan strategi isolasi jaringan *control plane/data plane*.
3. **Mengarsitekturi Pola Komunikasi Service Mesh:** Mengambil keputusan adopsi *Service Mesh* (Envoy-based, Istio/Linkerd, sidecar vs. ambient/daemonset model) untuk mengimplementasikan *zero-trust security* (mTLS), *advanced traffic routing* (canary, circuit breaking), dan *resilience policies*.
4. **Membangun Ekosistem Observabilitas Terpadu (The Three Pillars):** Mengonseptualisasikan korelasi struktural antara *Metrics* (time-series agregat), *Logs* (structured discrete events), dan *Distributed Traces* (causal execution graphs) untuk mereduksi *Mean Time to Detection* (MTTD) dan *Mean Time to Resolution* (MTTR).
5. **Mengimplementasikan OpenTelemetry (OTel) Standard:** Merancang pipeline telemetri vendor-agnostik menggunakan OpenTelemetry Collector (Receivers, Processors, Exporters), W3C TraceContext *propagation*, serta strategi *sampling* (head-based vs. tail-based) pada sistem berskala masif.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       [CLOUD-NATIVE PLATFORM]
                                  │
       ┌──────────────────────────┴──────────────────────────┐
       ▼                                                     ▼
[INFRASTRUCTURE RUNTIME]                             [OBSERVABILITY FABRIC]
  │                                                    │
  ├─► Containerization (OCI, runc, cgroups v2)         ├─► Three Pillars of Observability
  │                                                    │    ├─► Metrics (Prometheus/OpenMetrics)
  ├─► Orchestration (Kubernetes)                       │    ├─► Logs (Structured JSON, Correlation IDs)
  │    ├─ Control Plane (etcd, API Server, Sched)      │    └─► Traces (DAG, W3C TraceContext)
  │    └─ Worker Nodes (kubelet, CRI, CNI, CSI)        │
  │                                                    ├─► OpenTelemetry Standard
  └─► Service Mesh Interconnect                        │    ├─► OTel API & SDK (Instrumentation)
       ├─ Data Plane (Envoy, Sidecar/Ambient)          │    └─► OTel Collector (Recv/Proc/Export)
       └─ Control Plane (Istiod, xDS v3 API)           │
                                                       └─► Telemetry Routing & Storage
                                                            (Tempo, Prometheus, Loki/ClickHouse)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Transisi dari arsitektur monolitik statis ke sistem terdistribusi dinamis (*ephemeral*, auto-scaling microservices) memperkenalkan kompleksitas non-linear:

1. **Kegagalan Paradigma Monitoring Tradisional:** Monitoring berbasis host/IP gagal total ketika umur kontainer menyusut menjadi menit atau detik, dan alamat IP terus berubah secara dinamis.
2. **Degradasi Dependensi Tak Kasat Mata (*Cascading Failures*):** Dalam topologi ribuan layanan mikro, bottleneck performa sering kali tidak terjadi pada layanan penerima traffic langsung, melainkan 6 hop downstream pada antrian database atau resource contention CPU throttle. Tanpa distributed tracing, melacak root-cause memerlukan investigasi manual lintas tim yang memakan waktu berjam-jam.
3. **Keharusan Zero-Trust Network Architecture:** Di lingkungan cloud publik, batas perimeter jaringan tradisional telah runtuh. Identitas workload harus dibuktikan secara kriptografis melalui sertifikat dinamis jangka pendek (*mutual TLS*) yang dikelola tanpa intervensi kode aplikasi.
4. **Vendor Lock-in Telemetri:** Menggunakan agent proprietari (seperti Datadog, New Relic) mengunci format data dan kontrol biaya. OpenTelemetry mengembalikan kedaulatan data telemetri ke arsitek sistem melalui instrumentasi standar terbuka.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Kontainerisasi & OCI Runtime
Bukan virtualisasi hardware, melainkan virtualisasi sistem operasi. Kontainer memanfaatkan primitif kernel Linux:
* **Namespaces:** Memberikan isolasi view sistem (PID, NET, MNT, IPC, UTS, USER).
* **Cgroups (Control Groups v2):** Membatasi, mencatat, dan mengisolasi penggunaan resource fisik (CPU shares/quotas, Memory hard/soft limits, I/O bandwidth).
* **RootFS (OverlayFS):** Layering file system read-only berbasis image OCI dengan layer ephemeral copy-on-write (CoW).

### 2. Orkestrasi Kubernetes
Kubernetes adalah sistem terdistribusi berbasis state deklaratif yang menjalankan *reconciliation loop* terus menerus untuk menyamakan *actual state* dengan *desired state*:
* **Control Plane:** Menyimpan state tunggal sumber kebenaran pada `etcd` (Raft consensus), diekspos melalui `kube-apiserver`, dievaluasi oleh `kube-controller-manager`, dan dialokasikan ke node fisik melalui `kube-scheduler`.
* **Data Plane Node:** Dijalankan oleh `kubelet` (berkomunikasi lewat Container Runtime Interface / CRI), `kube-proxy` / eBPF agent (berkomunikasi lewat Container Network Interface / CNI), dan plugin Container Storage Interface (CSI).

### 3. Service Mesh
Lapisan infrastruktur khusus untuk menangani komunikasi antar-layanan (East-West traffic). 
* **Data Plane:** Proxy berkinerja tinggi (seperti Envoy) yang diinjeksikan secara transparan (sidecar container atau node-level eBPF) untuk mencegat seluruh traffic jaringan masuk dan keluar.
* **Control Plane:** Menerjemahkan konfigurasi tingkat tinggi (seperti VirtualService, DestinationRule) menjadi instruksi konfigurasi dinamis (xDS API: LDS, RDS, CDS, EDS) ke data plane proxy.

### 4. Tiga Pilar Telemetri & OpenTelemetry
* **Metrics:** Data time-series teragregasi numerik dengan dimensi label/atribut. Mengukur kuantitas performa sistem secara makro (*throughput*, *error rate*, *saturation*).
* **Logs:** Catatan diskrit berbasis teks terstruktur (JSON) dengan timestamp presisi tinggi mengenai suatu peristiwa spesifik.
* **Traces:** Grafik asiklik terarah (*Directed Acyclic Graph* / DAG) dari *Spans*, yang merepresentasikan alur eksekusi end-to-end dari satu permintaan yang melintasi berbagai batas proses dan jaringan.
* **OpenTelemetry:** Standar industri CNCF yang mendefinisikan API netral-bahasa, SDK implementasi, dan pipeline pemrosesan data (*Collector*) untuk mengekstraksi ketiga pilar telemetri secara terpadu melalui protokol OTLP (OpenTelemetry Protocol).

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### Alur Eksekusi Kontainer dan Orkestrasi Pod
1. Arsitek menerapkan manifes pod ke `kube-apiserver`.
2. `kube-apiserver` memvalidasi skema, memproses *mutating* dan *validating admission webhooks*, lalu menulis state ke `etcd`.
3. `kube-scheduler` mendeteksi pod tanpa assignment node, menjalankan filter (*node affinity*, *taints/tolerations*, resource availability) dan scoring, kemudian mengikat pod ke node target.
4. `kubelet` pada node mendeteksi penugasan via watch loop API, menginstruksikan CNI plugin untuk mengalokasikan IP dan veth pair, lalu memanggil runtime (containerd via CRI).
5. Containerd memanggil `runc` (OCI runtime) untuk membuat isolasi namespaces, menetapkan batas cgroups, memasang OverlayFS, dan mengeksekusi entrypoint aplikasi.

### Intersepsi Jaringan Service Mesh (Envoy Sidecar)
1. Inisialisasi container (`istio-init`) memodifikasi tabel `iptables` pada network namespace pod menggunakan aturan `PREROUTING` dan `OUTPUT` via `REDIRECT`.
2. Ketika aplikasi mengirim HTTP request keluar, socket call dialihkan oleh iptables ke port loopback lokal tempat Envoy mendengarkan (contoh: port 15001).
3. Envoy mengekstrak tujuan asli via `SO_ORIGINAL_DST`, mengevaluasi policy mTLS, mengenkripsi traffic menggunakan sertifikat SPIFFE yang dirotasi secara otomatis, lalu mengirimkannya melalui mTLS over HTTP/2 ke Envoy proxy pod tujuan.
4. Envoy penerima mendekripsi traffic, memvalidasi identitas SAN (Subject Alternative Name), memverifikasi otorisasi RBAC, dan meneruskannya ke port lokal aplikasi utama.

### Alur Context Propagation OpenTelemetry
```
Client Request -> [HTTP Header: traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01]
                   │
                   ▼
Service A (Extract Context -> Start Server Span -> Execute Biz Logic -> Inject Context)
                   │
                   ▼ [HTTP Header: traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-5fb397be34d23b0f-01]
Service B (Extract Context -> Start Server Span -> Process -> Export via OTLP gRPC)
                   │
                   ▼
OpenTelemetry Collector (Receiver -> Batch Processor -> Tail-based Sampler -> Exporter)
                   │
                   ▼
Backend Storage (Jaeger/Tempo [Traces], Prometheus [Metrics], Loki/ClickHouse [Logs])
```

Format W3C `traceparent` mematuhi struktur:
`version (2 hex) - trace_id (32 hex) - parent_id / span_id (16 hex) - trace_flags (2 hex)`

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

```
========================================================================================================
                                ARSITEKTUR CLUSTER CLOUD-NATIVE & OBSERVABILITAS
========================================================================================================

 [ Kubernetes Cluster Boundary ]
 ┌────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │  INGRESS LAYER                                                                                     │
 │    Ingress Gateway / Envoy Proxy (External TLS Termination, W3C TraceContext Generation)           │
 └──────────────────────────────────┬─────────────────────────────────────────────────────────────────┘
                                    │ Routing with Header Propagation
                                    ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │  APPLICATION NAMESPACE (Service Mesh Managed)                                                      │
 │                                                                                                    │
 │   ┌──────────────────────────────────────────────┐  mTLS (SPIFFE)   ┌────────────────────────────┐ │
 │   │ Pod: order-service                           │  HTTP/2 Wire     │ Pod: payment-service       │ │
 │   │                                              │ ═══════════════► │                            │ │
 │   │  ┌─────────────────┐    ┌─────────────────┐  │                  │  ┌──────────────────────┐  │ │
 │   │  │ App Container   │    │ Sidecar Envoy   │  │                  │  │ App Container        │  │ │
 │   │  │ (Go / OTel SDK) │    │ (Proxy Data Pln)│  │                  │  │ (Java / OTel Agent)  │  │ │
 │   │  └────────┬────────┘    └────────┬────────┘  │                  │  └──────────┬───────────┘  │ │
 │   │           │ localhost            │           │                  │             │              │ │
 │   │           │ (OTLP gRPC)          │ Statsd    │                  │             │ OTLP gRPC    │ │
 │   │           ▼                      ▼           │                  │             ▼              │ │
 │   └───────────┼──────────────────────┼───────────┘                  └─────────────┼──────────────┘ │
 └───────────────┼──────────────────────┼────────────────────────────────────────────┼────────────────┘
                 │                      │                                            │
                 │ OTLP:4317            │ Stats:9102                                 │ OTLP:4317
                 ▼                      ▼                                            ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │  OBSERVABILITY PIPELINE (Namespace: monitoring)                                                    │
 │                                                                                                    │
 │   ┌────────────────────────────────────────────────────────────────────────────────────────────┐   │
 │   │ OpenTelemetry Collector DaemonSet / Deployment                                             │   │
 │   │                                                                                            │   │
 │   │  [ Receivers ]                                                                             │   │
 │   │    ├── OTLP Receiver (gRPC: 4317, HTTP: 4318) ◄── (Traces, Metrics, Logs)                  │   │
 │   │    └── Prometheus Scrape Receiver (Envoy Stats, Node Exporter)                             │   │
 │   │                                                                                            │   │
 │   │  [ Processors ]                                                                            │   │
 │   │    ├── Memory Limiter (Mencegah OOM Collector)                                             │   │
 │   │    ├── K8s Attributes Processor (Auto-inject pod name, namespace, container name)          │   │
 │   │    ├── Batch Processor (Buffer telemetri untuk throughput tinggi)                          │   │
 │   │    └── Tail-based Sampler (100% simpan error & slow trace, sample 1% trace sukses)          │   │
 │   │                                                                                            │   │
 │   │  [ Exporters ]                                                                             │   │
 │   │    ├── Prometheus Exporter / Remote-Write ───────────────┐                                 │   │
 │   │    ├── OTLP gRPC Exporter (Traces) ─────────────────┐     │                                │   │
 │   │    └── Loki / Elasticsearch Exporter (Logs) ──┐     │     │                                │   │
 │   └───────────────────────────────────────────────┼─────┼─────┼────────────────────────────────┘   │
 └───────────────────────────────────────────────────┼─────┼─────┼────────────────────────────────────┘
                                                     │     │     │
                                 ┌───────────────────┘     │     └───────────────────┐
                                 ▼                         ▼                         ▼
                      ┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
                      │    LOG STORE     │      │   TRACE STORE    │      │   METRIC STORE   │
                      │  (Grafana Loki / │      │ (Grafana Tempo / │      │ (Prometheus M3DB/│
                      │   ClickHouse)    │      │     Jaeger)      │      │    Thanos)       │
                      └─────────┬────────┘      └────────┬─────────┘      └────────┬─────────┘
                                │                        │                         │
                                └────────────────────────┼─────────────────────────┘
                                                         ▼
                                              ┌───────────────────────┐
                                              │ Grafana Unified UI    │
                                              │ (Correlation Graph:   │
                                              │ TraceID <-> Log <->   │
                                              │ Metric Exemplar)      │
                                              └───────────────────────┘
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah implementasi minimal Go service yang menerapkan tracing kontekstual OpenTelemetry secara mandiri tanpa framework invasif, mencakup context injection dan span generation:

```go
package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/stdout/stdouttrace"
	"go.opentelemetry.io/otel/propagation"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
	trace "go.opentelemetry.io/otel/trace"
)

var tracer trace.Tracer

func initTracer() (*sdktrace.TracerProvider, error) {
	// Exporter sederhana menulis ke Stdout untuk demonstrasi
	exporter, err := stdouttrace.New(stdouttrace.WithPrettyPrint())
	if err != nil {
		return nil, err
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(sdktrace.NewResource(
			semconv.ServiceNameKey.String("simple-order-service"),
			attribute.String("environment", "development"),
		)),
	)
	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))
	return tp, nil
}

func handleOrder(w http.ResponseWriter, r *http.Request) {
	// Extract incoming W3C Context dari request header
	ctx := otel.GetTextMapPropagator().Extract(r.Context(), propagation.HeaderCarrier(r.Header))
	
	// Start span turunan
	ctx, span := tracer.Start(ctx, "HandleOrder",
		trace.WithSpanKind(trace.SpanKindServer),
	)
	defer span.End()

	span.SetAttributes(
		attribute.String("http.route", "/order"),
		attribute.String("user.id", "usr-88910"),
	)

	// Simulasi sub-operasi internal
	processPayment(ctx)

	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"status":"PROCESSED"}`))
}

func processPayment(ctx context.Context) {
	_, span := tracer.Start(ctx, "processPayment",
		trace.WithSpanKind(trace.SpanKindInternal),
	)
	defer span.End()

	// Simulasi latency pemrosesan
	time.Sleep(50 * time.Millisecond)
	span.AddEvent("Payment Gateway Accepted", trace.WithAttributes(
		attribute.Float64("payment.amount", 450.50),
	))
}

func main() {
	tp, err := initTracer()
	if err != nil {
		log.Fatalf("Gagal inisialisasi tracer: %v", err)
	}
	defer func() {
		if err := tp.Shutdown(context.Background()); err != nil {
			log.Printf("Gagal mematikan TracerProvider: %v", err)
		}
	}()

	tracer = otel.GetTracerProvider().Tracer("order-service-tracer")

	http.HandleFunc("/order", handleOrder)
	log.Println("Server aktif pada port 8080...")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		log.Fatal(err)
	}
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus arsitektur produksi: Konfigurasi kluster Kubernetes yang menjalankan service kritis, terintegrasi dengan Istio Service Mesh, instrumentasi OpenTelemetry SDK, dan perutean data melalui OpenTelemetry Collector.

### 1. Kubernetes Workload Manifest (`order-deployment.yaml`)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-processing-service
  namespace: e-commerce
  labels:
    app.kubernetes.io/name: order-processing
    app.kubernetes.io/part-of: checkout-engine
spec:
  replicas: 3
  selector:
    matchLabels:
      app: order-processing
  template:
    metadata:
      labels:
        app: order-processing
      annotations:
        # Service Mesh Sidecar Injection
        sidecar.istio.io/inject: "true"
        sidecar.istio.io/proxyCPU: "200m"
        sidecar.istio.io/proxyMemory: "256Mi"
        # Prometheus Scraping Pod Configuration
        prometheus.io/scrape: "true"
        prometheus.io/port: "9090"
        prometheus.io/path: "/metrics"
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app
                      operator: In
                      values: ["order-processing"]
                topologyKey: "topology.kubernetes.io/zone"
      containers:
        - name: app
          image: internal-registry.enterprise.io/checkout/order-service:v2.4.1
          imagePullPolicy: IfNotPresent
          env:
            - name: OTEL_SERVICE_NAME
              value: "order-processing-service"
            - name: OTEL_EXPORTER_OTLP_ENDPOINT
              value: "http://otel-collector.monitoring.svc.cluster.local:4317"
            - name: OTEL_EXPORTER_OTLP_PROTOCOL
              value: "grpc"
            - name: POD_IP
              valueFrom:
                fieldRef:
                  fieldPath: status.podIP
          ports:
            - containerPort: 8080
              name: http-app
            - containerPort: 9090
              name: http-metrics
          resources:
            requests:
              cpu: "500m"
              memory: "512Mi"
            limits:
              cpu: "2000m"
              memory: "1024Mi"
          readinessProbe:
            httpGet:
              path: /healthz/ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
            timeoutSeconds: 2
          livenessProbe:
            httpGet:
              path: /healthz/live
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 15
            timeoutSeconds: 2
```

### 2. OpenTelemetry Collector Pipeline Configuration (`otel-collector-config.yaml`)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: otel-collector-config
  namespace: monitoring
data:
  collector.yaml: |
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 0.0.0.0:4317
          http:
            endpoint: 0.0.0.0:4318

      prometheus:
        config:
          scrape_configs:
            - job_name: 'kubernetes-pods'
              kubernetes_sd_configs:
                - role: pod
              relabel_configs:
                - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
                  action: keep
                  regex: true

    processors:
      memory_limiter:
        check_interval: 1s
        limit_percentage: 75
        spike_limit_percentage: 20

      k8sattributes:
        auth_type: "serviceAccount"
        passthrough: false
        extract:
          metadata:
            - k8s.pod.name
            - k8s.pod.uid
            - k8s.deployment.name
            - k8s.namespace.name
            - k8s.node.name

      batch:
        send_batch_size: 8192
        timeout: 2s
        send_batch_max_size: 16384

      tail_sampling:
        decision_wait: 5s
        num_traces: 50000
        expected_new_traces_per_sec: 2000
        policies:
          - name: error-conditions
            type: status_code
            status_code: { status_codes: [ ERROR ] }
          - name: high-latency
            type: latency
            latency: { threshold_ms: 1000 }
          - name: probabilistic-sampling
            type: probabilistic
            probabilistic: { sampling_percentage: 5.0 }

    exporters:
      otlp/tempo:
        endpoint: tempo-distributor.monitoring.svc.cluster.local:4317
        tls:
          insecure: true

      prometheusremotewrite:
        endpoint: http://thanos-receive.monitoring.svc.cluster.local:19291/api/v1/receive
        tls:
          insecure: true

      logging:
        loglevel: warn

    service:
      telemetry:
        logs:
          level: "info"
      pipelines:
        traces:
          receivers: [otlp]
          processors: [memory_limiter, k8sattributes, tail_sampling, batch]
          exporters: [otlp/tempo]
        metrics:
          receivers: [otlp, prometheus]
          processors: [memory_limiter, k8sattributes, batch]
          exporters: [prometheusremotewrite]
```

### 3. Implementasi Produksi Go: Context Injection & Propagation

```go
package client

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/propagation"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
	"go.opentelemetry.io/otel/trace"
)

type InstrumentedClient struct {
	httpClient *http.Client
	tracer     trace.Tracer
}

func NewInstrumentedClient() *InstrumentedClient {
	return &InstrumentedClient{
		httpClient: &http.Client{Timeout: 5 * time.Second},
		tracer:     otel.GetTracerProvider().Tracer("external-http-client"),
	}
}

func (c *InstrumentedClient) ExecuteDownstreamCall(ctx context.Context, targetURL string) (*http.Response, error) {
	// Memulai Span HTTP Client
	ctx, span := c.tracer.Start(ctx, fmt.Sprintf("HTTP GET %s", targetURL),
		trace.WithSpanKind(trace.SpanKindClient),
		trace.WithAttributes(
			semconv.HTTPURLKey.String(targetURL),
			semconv.HTTPMethodKey.String(http.MethodGet),
		),
	)
	defer span.End()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, targetURL, nil)
	if err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, err.Error())
		return nil, fmt.Errorf("failed creating request: %w", err)
	}

	// INJEKSI KRITIS: Menulis context trace saat ini ke dalam W3C header HTTP downstream
	otel.GetTextMapPropagator().Inject(ctx, propagation.HeaderCarrier(req.Header))

	resp, err := c.httpClient.Do(req)
	if err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, "network failure")
		return nil, err
	}

	span.SetAttributes(semconv.HTTPStatusCodeKey.Int(resp.StatusCode))
	if resp.StatusCode >= 400 {
		span.SetStatus(codes.Error, fmt.Sprintf("HTTP error: %d", resp.StatusCode))
	} else {
		span.SetStatus(codes.Ok, "Success")
	}

	return resp, nil
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Arsitektural | Pendekatan A | Pendekatan B | Analisis Trade-off Arsitek |
| :--- | :--- | :--- | :--- |
| **Pola Service Mesh** | **Sidecar Pattern** (Envoy container per Pod) | **Ambient / Node-level Proxy** (eBPF + shared L7 proxy) | **Sidecar:** Isolasi resource tajam, blast radius kecil, namun konsumsi memory tinggi di kluster skala ribuan pod (~50MB per pod).<br>**Ambient:** Overhead compute/memory sangat rendah, upgrade proxy tanpa restart pod aplikasi, namun model isolasi security mTLS multi-tenant di level node lebih kompleks. |
| **Tracing Sampling** | **Head-Based Sampling** (Diputuskan di ingress gateway) | **Tail-Based Sampling** (Diputuskan di OTel Collector setelah trace selesai) | **Head-Based:** Sangat hemat bandwidth jaringan internal; trace di-drop sejak awal. Kelemahan fatal: request lambat atau error yang tak terduga bisa lolos tidak tercatat jika tidak masuk sampel.<br>**Tail-Based:** Menggaransi 100% error dan anomaly tertangkap; membutuhkan buffer memori masif pada OpenTelemetry Collector untuk menahan traces hingga status span akhir selesai. |
| **Metric Cardinality** | **High Cardinality** (Label memuat `user_id`, `ip_address`) | **Bounded Low Cardinality** (Label hanya memuat `status_code`, `route`) | **High Cardinality:** Diagnosa granularitas mikro langsung dari metric dashboard, namun dapat menyebabkan *Prometheus TSDB Out of Memory crash* dan biaya penyimpanan tak terkendali.<br>**Bounded:** Kluster TSDB stabil dan query instan, investigasi granular dialihkan ke Tracing dan Logs via *Exemplars*. |
| **Transmisi Log** | **Synchronous Direct Push** (App -> Logging Backend via HTTP) | **Decoupled Out-of-Process** (Stdout -> Node Log Agent via filesystem/socket) | **Direct Push:** Metadata terisolasi, namun backpressure logging backend langsung memblokir main loop thread aplikasi.<br>**Decoupled:** Non-blocking untuk aplikasi, performa I/O tinggi, namun risiko kehilangan log jika node mengalami hard power loss sebelum agent membaca file log. |

---

## SEKSI 11 — BEST PRACTICES

### Kubernetes Resilience
1. **Atur Requests = Limits untuk Memory (QoS: Guaranteed):** Menghindari proses terminasi acak akibat *Out-of-Memory (OOM) Killer* kernel Linux saat node kehabisan memori.
2. **Definisikan Pod Topology Spread Constraints:** Mencegah scheduler menempatkan semua replika layanan pada failure-domain yang sama (misalnya: node yang sama atau Availability Zone yang sama).
3. **Pisahkan Probe Semantics:**
   * `StartupProbe`: Tangani beban inisialisasi lambat (cold starts, loading caches).
   * `ReadinessProbe`: Menentukan apakah pod siap menerima traffic (jangan arahkan ke dependensi database eksternal; pod gagal jika DB lambat, memperparah kaskade kegagalan).
   * `LivenessProbe`: Hanya untuk merestart pod saat deadlock internal terjadi (harus sangat konservatif).

### Observabilitas & OpenTelemetry
1. **Standarisasi Semantic Conventions CNCF:** Gunakan penamaan standar atribut (`http.status_code`, bukan `http_code` atau `status`). Hal ini memungkinkan korelasi otomatis lintas platform dan dashboard Grafana generik.
2. **Aktifkan Exemplars pada Metrik Prometheus:** Sertakan `TraceID` dalam metrik histogram latency secara transparan. Saat spike latensi terjadi pada metrik 99th percentile, arsitek dapat mengklik titik metrik dan langsung beralih ke distributed trace yang tepat di Tempo/Jaeger.
3. **Gunakan Batch Processor dengan Memory Limiter:** Dalam konfigurasi OTel Collector, selalu tempatkan `memory_limiter` sebelum `batch` processor guna mencegah crash OOM saat spike traffic tiba-tiba.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. High Cardinality Metric Explosion
* **Anti-Pattern:** Menyertakan entitas dinamis tak terbatas sebagai label metrik Prometheus.
  ```go
  // FATAL: Menyebabkan crash Prometheus TSDB
  httpRequestsTotal.WithLabelValues(r.Method, r.URL.Path, userID).Inc()
  ```
* **Solusi Arsitek:** Batasi dimensi label metrik pada domain terbatas (*finite state*). Gunakan *parameterized route* (contoh: `/orders/:id`, bukan `/orders/1298418`) dan transfer identifikasi `userID` ke dalam OpenTelemetry Trace Attribute.

### 2. Broken Context Propagation dalam Goroutine / Async Thread
* **Anti-Pattern:** Menjalankan background worker goroutine dengan mengambil `context.Background()` baru secara terisolasi tanpa mewarisi trace context parent.
  ```go
  // FATAL: Jejak tracing terputus di sini!
  go func() {
      newCtx := context.Background()
      executeAsyncJob(newCtx)
  }()
  ```
* **Solusi Arsitek:** Turunkan context dari parent thread namun putuskan pembatalan deadline (`context.WithoutCancel(ctx)` pada Go 1.21+) agar metadata tracing tetap utuh tanpa terputus saat HTTP request utama selesai.

### 3. Readiness Probe Bergantung pada Hard Dependencies
* **Anti-Pattern:** Readiness probe memverifikasi kueri `SELECT 1` ke database relational utama.
* **Dampak Sistemik:** Ketika database mengalami lonjakan query lambat, *seluruh* pod aplikasi di kluster dinyatakan `NotReady` oleh kubelet, traffic diputus dari seluruh pod, memicu kegagalan total sistem (*mass service outage*) secara instan.
* **Solusi Arsitek:** Readiness probe hanya boleh memvalidasi kesiapan socket dan dependensi internal pod itu sendiri. Dependensi eksternal ditangani menggunakan pola *Circuit Breaker* pada level aplikasi.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Merancang Pipeline Tail-Based Sampling
**Skenario:** Sistem e-commerce memproses 50.000 request per detik. 99,5% transaksi berjalan normal di bawah 50ms, namun 0,5% mengalami transaksi lambat (>1200ms) atau error HTTP 500. Anggaran penyimpanan traces hanya mampu menampung 2.500 trace per detik.
* **Tugas:**
  1. Tuliskan blok konfigurasi `processors.tail_sampling` pada OTel Collector YAML.
  2. Implementasikan policy: Simpan 100% trace yang memiliki tag error, simpan 100% trace dengan latensi > 1200ms, dan lakukan sampling acak 2% untuk sisanya.
  3. Hitung estimasi kapasitas throughput traces baru yang dikirim ke backend storage.

### Latihan 2: Debugging Putusnya Distributed Trace
**Skenario:** Trace ID muncul di Service A (API Gateway), namun trace yang ada di Service C (Payment Service) memiliki Trace ID yang sama sekali baru, padahal request dialirkan melalui Service B (Order Service).
* **Tugas:**
  1. Identifikasi di layer mana kemungkinan kebocoran propagasi konteks terjadi.
  2. Buat skrip curl / http client test untuk memverifikasi apakah header `traceparent` di-strip oleh Envoy Proxy atau diabaikan oleh kode HTTP client internal Service B.
  3. Perbaiki kode HTTP forwarder di Service B menggunakan standar `otel.GetTextMapPropagator()`.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Apa perbedaan mendasar antara mekanisme isolasi kontainer OCI Linux dengan VM Hypervisor tipe 1?**
   * *Jawaban Singkat:* Kontainer berbagi kernel Linux host tunggal dan mengisolasi process table, network stack, dan file mount menggunakan primitives kernel (`namespaces` & `cgroups`), menghasilkan startup time instan dan efisiensi memori. VM memvirtualisasi hardware fisik secara menyeluruh, menjalankan kernel OS tamu terpisah di atas hypervisor, memberikan boundary isolasi hardware-level yang lebih kuat namun dengan overhead resource signifikan.

2. **Mengapa *tail-based sampling* harus diletakkan pada tier OpenTelemetry Collector, bukan di dalam aplikasi pengirim (in-process)?**
   * *Jawaban Singkat:* Trace span individual dibuat sepanjang masa hidup permintaan yang melintasi puluhan microservices. Keputusan apakah suatu trace mengandung error atau melebihi threshold latensi hanya dapat diketahui ketika span terakhir telah tuntas (di ujung alur eksekusi). Collector bertindak sebagai agregator yang mengumpulkan seluruh span dari trace ID yang sama sebelum menentukan apakah trace tersebut disimpan atau dibuang.

3. **Bagaimana Envoy Proxy mencegat traffic pod secara transparan pada model Sidecar Service Mesh?**
   * *Jawaban Singkat:* Selama proses pod startup, container inisialisasi (`istio-init`) menggunakan hak akses `NET_ADMIN` untuk mengatur aturan `iptables` di dalam network namespace pod tersebut. Aturan ini me-redirect seluruh paket TCP masuk dan keluar pod menuju port loopback lokal tempat proses proxy Envoy mendengarkan (*transparent interception*).

4. **Kapan seorang arsitek harus memilih Prometheus pull-model vs. OTLP push-model untuk pengumpulan metrik?**
   * *Jawaban Singkat:* Pull-model (Prometheus) ideal untuk layanan statis/semi-statis yang dapat di-*service discover* via K8s API, mencegah overloading server backend saat terjadi spike traffic lokal. Push-model (OTLP) sangat ideal untuk environment jangka pendek (*ephemeral workloads*, serverless functions, batch jobs) dan jaringan edge yang berada di balik NAT/firewall di mana target tidak dapat dihubungi langsung dari server telemetri.

5. **Apa fungsi dari W3C `tracestate` header di samping `traceparent`?**
   * *Jawaban Singkat:* `traceparent` membawa identitas trace tunggal yang wajib (`trace-id`, `parent-id`, `flags`), sedangkan `tracestate` membawa pasangan key-value spesifik vendor/sistem (opaque metadata) untuk memungkinkan interoperabilitas lintas vendor tracing berbeda tanpa merusak integritas trace graf.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku:**
  * *Cloud Native Infrastructure: Patterns for Scalable Infrastructure and Applications* - Justin Garrison & Kris Nova (O'Reilly).
  * *Distributed Tracing in Practice* - Austin Parker, Daniel Spoonhower, Jonathan Mace, Ben Sigelman (O'Reilly).
  * *Kubernetes in Action, Second Edition* - Marko Lukša (Manning Publications).
* **Spesifikasi & Standar CNCF:**
  * OpenTelemetry Specification (Tracing, Metrics, Logs, Semantic Conventions): `https://opentelemetry.io/docs/specs/`
  * W3C Recommendation: Trace Context Level 2: `https://www.w3.org/TR/trace-context/`
  * Envoy Data Plane API Documentation (v3 xDS API): `https://www.envoyproxy.io/docs/envoy/latest/api-v3/api`

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                          RINGKASAN ARSITEKTUR KUNCI                              │
├──────────────────────────────────────────────────────────────────────────────────┤
│ 1. Container Engine    : Linux Namespaces (Isolasi View) + Cgroups (Resource     │
│                          Cap) + OverlayFS (Image Layering).                      │
│ 2. Kubernetes Engine   : Declarative Reconciler (Actual State -> Desired State). │
│ 3. Service Mesh        : Abstraksi Komunikasi Jaringan (Zero-Trust mTLS, Routing,│
│                          Resilience) di luar proses kode bisnis.                 │
│ 4. Observability       : Mengukur Unknown-Unknowns melalui korelasi struktural:   │
│                          • Metrics -> "Ada anomali terdeteksi" (What/Where)      │
│                          • Traces  -> "Anomali terjadi di microservice X" (Who)  │
│                          • Logs    -> "Penyebab error adalah exception Y" (Why)  │
│ 5. OpenTelemetry       : Standar de facto vendor-neutral instrumentasi dan       │
│                          pipeline collector telemetri terdistribusi.             │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## SEKSI 17 — GLOSARIUM

* **Cgroup (Control Group):** Fitur kernel Linux yang membatasi, menghitung, dan mengisolasi penggunaan resource (CPU, memory, disk I/O, network) dari sekumpulan proses.
* **Control Plane vs. Data Plane:** Control plane memegang otoritas keputusan arsitektur, kalkulasi topologi, dan distribusi policy; Data plane mengeksekusi routing paket, pemrosesan komputasi, dan transmisi payload secara real-time.
* **Distributed Tracing:** Metode melacak siklus hidup eksekusi request saat melompat melewati batas jaringan, thread, dan proses pada sistem terdistribusi.
* **Envoy Proxy:** High-performance programmable proxy C++ yang umum digunakan sebagai data plane default pada service mesh dan cloud-native API gateways.
* **Exemplar:** Fitur OpenMetrics/Prometheus yang mengaitkan referensi ID trace spesifik ke sebuah bucket data agregat time-series metrik tertentu.
* **mTLS (Mutual Transport Layer Security):** Proses otentikasi dua arah di mana kedua entitas (klien dan server) memverifikasi sertifikat kriptografis X.509 satu sama lain sebelum membentuk koneksi terenkripsi.
* **OTLP (OpenTelemetry Protocol):** Protokol serialisasi data telemetri bawaan CNCF berbasis Protobuf via transport gRPC atau HTTP.
* **Span:** Unit kerja atomik individual dalam sebuah distributed trace, merepresentasikan operasi spesifik dengan waktu mulai, durasi, tag, dan status.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Fokus Penekanan:** Tegaskan kepada murid bahwa *Observability bukanlah Monitoring yang berganti nama*. Monitoring memberi tahu arsitek saat sistem rusak (*known-unknowns*); Observabilitas memungkinkan arsitek men-debug mengapa sistem bertingkah aneh tanpa perlu merilis kode baru (*unknown-unknowns*).
* **Simulasi Kelas:** Gunakan skenario kegagalan jaringan acak (chaos injection via Chaos Mesh atau Istio fault injection) untuk mendemonstrasikan bagaimana korelasi Trace -> Log -> Metric mempercepat investigasi insiden dari 45 menit menjadi kurang dari 3 menit.
* **Peringatan Laboratorium:** Pastikan kluster Kubernetes latihan memiliki alokasi memori minimal 8GB, karena menjalankan Istio Control Plane, Prometheus, Tempo, dan OTel Collector secara paralel memerlukan baseline RAM fisik yang substansial.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0 (Maret 2026):** Rilis arsitektur awal. Standardisasi materi pada OpenTelemetry SDK v1.24+, Istio Ambient Mesh topology comparisons, Linux Cgroups v2 specifications, dan integrasi tracing kontekstual berbasis W3C TraceContext standar.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `ARC-06-08-01: Microservices Deconstruction, DDD Strategic Patterns, & Distributed Transactions (Saga, Outbox, Event-Driven)`
* **Modul Saat Ini:** `ARC-06-09-01: Cloud-Native Infrastructure & Observability: Containerization, Kubernetes Orchestration, Service Mesh, Telemetry Three Pillars (Metrics, Logs, Traces), OpenTelemetry`
* **Modul Selanjutnya:** `ARC-06-10-01: High-Performance Networking, Zero-Trust Security Architecture, Distributed Storage Systems, & Edge Computing Topologies`