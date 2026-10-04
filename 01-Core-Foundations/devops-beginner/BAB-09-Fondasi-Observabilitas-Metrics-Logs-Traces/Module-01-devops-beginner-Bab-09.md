## SEKSI 01 — IDENTITAS MODUL

*   **Modul ID:** `DO-CF-09-01`
*   **Track:** `devops-beginner`
*   **Kategori:** `01-Core-Foundations`
*   **Nama Modul:** Fondasi Observabilitas: Metrics, Logs, & Traces
*   **Tingkat Kesulitan:** Beginner to Intermediate
*   **Prasyarat:** Pemahaman dasar arsitektur sistem operasi Linux, konsep dasar *networking* (TCP/IP, HTTP), dasar pemrograman (Python atau Go), serta familiaritas dengan konsep kontainerisasi dasar (Docker).
*   **Estimasi Waktu Belajar:** 180 Menit (Teori: 60 Menit, Praktik Hands-On: 120 Menit)
*   **Tech Stack:** OpenTelemetry (OTel), Prometheus, Grafana Loki, Jaeger, Python (FastAPI/Structlog).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Menganalisis** perbedaan fundamental antara *Monitoring* tradisional (kondisi *known-unknowns*) dan *Observability* modern (kondisi *unknown-unknowns*) berdasarkan prinsip sistem kontrol.
2.  **Mengidentifikasi dan Membedakan** karakteristik, kelebihan, serta batasan dari Tiga Pilar Telemetri (*Metrics*, *Logs*, *Traces*).
3.  **Mengimplementasikan** *Structured Logging* berbasis JSON dengan injeksi metadata korelasi (*Trace ID* dan *Span ID*) ke dalam aplikasi mikroservis.
4.  **Menerapkan** instrumentasi metrik dasar menggunakan standar *Google's Four Golden Signals* (Latency, Traffic, Errors, Saturation) dan metodologi RED (*Rate*, *Errors*, *Duration*).
5.  **Mengonfigurasi** distributed tracing sederhana menggunakan standar OpenTelemetry untuk melacak alur *request* lintas layanan.
6.  **Mengevaluasi** risiko *high cardinality* pada metrik dan implikasinya terhadap performa serta biaya infrastruktur.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
                             [ OBSERVABILITAS SISTEM ]
                                        │
           ┌────────────────────────────┼────────────────────────────┐
           ▼                            ▼                            ▼
      [ METRICS ]                    [ LOGS ]                    [ TRACES ]
  (Aggregable / Numerical)    (Discrete / Event-based)      (Contextual / Journey)
           │                            │                            │
   Karakteristik:               Karakteristik:               Karakteristik:
   - Time-series data           - Timestamped text/JSON      - Span & Trace IDs
   - Low storage footprint      - High context / detail      - Causal dependency
   - High alertability          - High storage volume        - Latency profiling
           │                            │                            │
   Metodologi:                  Format Standar:              Standar Industri:
   - RED / USE Methods          - Structured Logging (JSON)  - W3C TraceContext
   - Golden Signals             - Semantic Conventions       - OpenTelemetry (OTel)
           │                            │                            │
           └────────────────────────────┼────────────────────────────┘
                                        │
                                        ▼
                        [ KORELASI TELEMETRI ]
                  (Metrics memicu Alert ──> Traces
                   mengisolasi Bottleneck ──> Logs
                   mengungkap Akar Masalah / Root Cause)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Dalam sistem monolitik tradisional, penelusuran insiden cukup dilakukan dengan masuk via SSH ke satu server dan mengeksekusi `tail -f /var/log/application.log`. Namun, pada era arsitektur terdistribusi (*microservices*, *serverless*, *Kubernetes*), satu transaksi pengguna dapat melintasi belasan dependensi mikroservis, antrean pesan (*message brokers*), dan kluster basis data.

1.  **Mitigasi MTTR (Mean Time to Resolution):** Tanpa observabilitas terstruktur, tim *engineering* menghabiskan 80% waktu insiden hanya untuk mendebat letak kesalahan (*finger-pointing*) dan mencoba mereproduksi masalah. Korelasi telemetri yang tepat mereduksi fase lokalisasi masalah dari hitungan jam menjadi hitungan menit.
2.  **Navigasi Kondisi "Unknown-Unknowns":** *Monitoring* tradisional menguji apakah sistem bekerja sesuai dengan skenario kegagalan yang sudah diprediksi (*known-unknowns*). Observabilitas memberikan kemampuan investigatif untuk menginterogasi sistem pada kondisi anomali yang belum pernah terjadi sebelumnya (*unknown-unknowns*).
3.  **Dampak Finansial Downtime:** Downtime pada ekosistem produksi modern bernilai ribuan hingga jutaan dolar per jam. Tanpa telemetri yang memadai, degradasi performa laten (*silent failures* atau kenaikan p99 latency) akan luput dari deteksi hingga pelanggan mengeluh di media sosial.

---

## SEKSI 05 — APA ITU (WHAT)

### Definisi Observabilitas
Secara mekanis dan matematis (berakar dari *Control Theory* oleh Rudolf E. Kálmán), **Observabilitas** adalah ukuran seberapa baik keadaan internal (*internal state*) suatu sistem dapat disimpulkan hanya berdasarkan pengetahuan tentang keluaran eksternalnya (*external outputs*).

Dalam rekayasa perangkat lunak, sistem dikatakan *observable* jika teknisi dapat memahami mekanisme internal, alur eksekusi, serta anomali pada aplikasi tanpa perlu menginjeksi kode baru atau menjalankan *interactive debugger* di server produksi.

### Tiga Pilar Telemetri (M.E.L.T. Foundation)

| Pilar | Definisi Teknis | Tipe Data | Keunggulan Utama | Kelemahan Utama |
| :--- | :--- | :--- | :--- | :--- |
| **Metrics** | Representasi numerik teragregasi dari data yang diukur sepanjang interval waktu (*time-series*). | Counter, Gauge, Histogram, Summary | Ringan, komputasi cepat, ideal untuk *alerting* otomatis. | Minim konteks detail; rentan terhadap ledakan kardinalitas (*cardinality explosion*). |
| **Logs** | Catatan tekstual terpisah (*discrete event*) yang diimbuhi stempel waktu (*timestamp*) mengenai kejadian tertentu. | Plain text, JSON (Structured) | Kaya akan konteks, pesan kesalahan, dan *payload state*. | Volume data masif, mahal untuk disimpan dan diindeks, sulit dianalisis lintas server tanpa *parser*. |
| **Traces** | Representasi jalur eksekusi ujung-ke-ujung (*end-to-end*) dari sebuah *request* yang melintasi sistem terdistribusi. | Tree of Spans (DAG - Directed Acyclic Graph) | Memetakan dependensi sistem, mengisolasi *bottleneck* latensi secara presisi. | Kompleksitas implementasi instrumentasi dan biaya transfer jaringan data trace. |

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

Alur kerja observabilitas modern mengandalkan instrumentasi di level kode yang diekstraksi ke *collector*, lalu diarahkan ke sistem penyimpanan terspesialisasi sebelum divisualisasikan.

### 1. Injeksi & Propagasi Konteks (Context Propagation)
Ketika sebuah HTTP request masuk:
*   Komponen *tracer* membuat **Trace ID** unik (16-byte integer acak).
*   Operasi lokal diwakili oleh **Span ID** (8-byte integer).
*   Saat layanan A memanggil layanan B, Layanan A menginjeksi Trace ID dan Parent Span ID ke dalam header HTTP (mengikuti standar **W3C TraceContext**: `traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`).
*   Layanan B mengekstrak header tersebut dan melanjutkan konteks *trace* yang sama.

### 2. Log Correlation
Framework logging (misal: Structlog, Zerolog) mengambil Trace ID dan Span ID aktif dari *thread-local storage* atau *Context API* dan menyematkannya ke dalam setiap baris log berformat JSON secara otomatis.

### 3. Metric Aggregation
Engine metrik menghitung operasi (inkremen counter, rekaman durasi pada bucket histogram) secara *in-memory* pada *client side* untuk meminimalkan *network overhead*. Metrik ini di-*scrape* (metode pull via HTTP `/metrics`) secara periodik oleh server seperti Prometheus atau dikirim (*push*) via OTLP (OpenTelemetry Protocol).

### 4. Triase Insiden Terkorelasi
Siklus deteksi hingga penyelesaian masalah berjalan melalui rantai berikut:
1.  **Alerting (Metrics):** Prometheus mendeteksi kenaikan metrik `http_requests_total{status="500"}` melewati ambang batas SLO.
2.  **Localization (Traces):** Teknisi membuka Jaeger/Tempo, mencari trace dengan status error pada rentang waktu insiden, dan menemukan bahwa *Span* `database_query` pada Service C memakan waktu 8 detik sebelum timeout.
3.  **Root Cause Analysis (Logs):** Teknisi menyalin `Trace ID` dari span tersebut, melakukan query pada Loki/Elasticsearch: `{trace_id="4bf92f35..."}`, dan menemukan log detail: `ConnectionPoolExhaustedException: maximum connections (100) reached`.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

Berikut adalah arsitektur aliran data telemetri terintegrasi dari aplikasi hingga visualisasi:

```text
+---------------------------------------------------------------------------------------+
|                                    APPLICATION LAYER                                  |
|                                                                                       |
|   +-------------------------------------------------------------------------------+   |
|   | App Instance (e.g., Order Service)                                            |   |
|   |                                                                               |   |
|   |  [Incoming HTTP] ---> [W3C Context Extraction]                                |   |
|   |                             │                                                 |   |
|   |      ┌──────────────────────┼──────────────────────┐                          |   |
|   |      ▼                      ▼                      ▼                          |   |
|   |  [Tracer SDK]         [Metrics SDK]          [Logger SDK]                     |   |
|   |  - Start Span         - Inc Counter          - Extract active TraceID         |   |
|   |  - Inject Header      - Observe Latency      - Output JSON to stdout          |   |
|   +──────┬──────────────────────┬──────────────────────┬──────────────────────────+   |
+──────────┼──────────────────────┼──────────────────────┼──────────────────────────────+
           │ OTLP (gRPC)          │ OTLP (gRPC)          │ Stdout / Container Logs
           │                      │                      │
+──────────▼──────────────────────▼──────────────────────┼──────────────────────────────+
|                                                        │                              |
|   +──────────────────────────────────────────────+     │  +────────────────────────+  |
|   | OpenTelemetry (OTel) Collector               |     │  | Node / Host Logging    |  |
|   |                                              |     │  | Daemon (e.g., Promtail)|  |
|   |  [ Receivers: OTLP (Port 4317) ]             |     │  +───────────┬────────────+  |
|   |                       │                      |     │              │               |
|   |  [ Processors: Batch, Memory Limiter, Tail ] │     │              │ Tail Log Files|
|   |                       │                      |     │              │ Docker Socket |
|   |  [ Exporters: Prometheus, OTLP-gRPC ]        |     │              │               |
|   +──────────┬──────────────────┬────────────────+     │              │               |
+──────────────┼──────────────────┼──────────────────────┼──────────────┼───────────────+
               │                  │                      │              │
               │ Push Traces      │ Pull Metrics         │ Push Logs    │
               │                  │ (/metrics endpoint)  │              │
               ▼                  ▼                      ▼              ▼
     +-----------------+  +-----------------+  +--------------------------------+
     | Storage / APM   |  | Time-Series DB  |  | Log Aggregator                 |
     | (Jaeger/Tempo)  |  | (Prometheus)    |  | (Grafana Loki / Elasticsearch) |
     +────────┬────────+  +────────┬────────+  +──────────────┬────────────────-+
              │                    │                          │
              └────────────────────┼──────────────────────────┘
                                   ▼
              +------------------------------------------+
              |           UNIFIED DASHBOARD              |
              |               (Grafana)                  |
              |                                          |
              | [Graph] ──jump-to──> [Trace] ──jump-to──>|
              |  Metrics              Timeline    Logs   |
              +------------------------------------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Contoh dasar berikut mendemonstrasikan integrasi *manual correlation* di Python tanpa framework kompleks untuk memahami esensi Trace ID injection pada Log.

```python
import uuid
import time
import json
import sys

class SimpleTelemetryContext:
    def __init__(self):
        self.trace_id = None
        self.span_id = None

    def start_trace(self):
        # Generate ID 16-byte hex simetris standar OTel
        self.trace_id = uuid.uuid4().hex
        self.span_id = uuid.uuid4().hex[:16]

    def log(self, level: str, message: str, **extra):
        log_entry = {
            "timestamp": time.time(),
            "level": level,
            "message": message,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "context": extra
        }
        # Logs HARUS selalu berupa single-line JSON ke standard output
        sys.stdout.write(json.dumps(log_entry) + "\n")
        sys.stdout.flush()

# Inisialisasi
telemetry = SimpleTelemetryContext()

# Simulasi Request Masuk
telemetry.start_trace()
telemetry.log("INFO", "Request inbound", path="/api/v1/checkout", method="POST")

start_time = time.time()
try:
    # Simulasi eksekusi logika bisnis
    time.sleep(0.05)
    telemetry.log("DEBUG", "Querying database for inventory", item_id="item-982")
    
    # Hitung metrik sederhana
    duration = time.time() - start_time
    telemetry.log("INFO", "Request completed", status_code=200, duration_seconds=duration)
except Exception as e:
    telemetry.log("ERROR", "Unhandled exception occurred", error=str(e))
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Penerapan standar produksi menggunakan Python FastAPI dengan instrumentasi OpenTelemetry resmi, injeksi Structlog untuk JSON logging, serta eksposisi metrik via Prometheus format.

### 1. Inisialisasi Dependensi (`requirements.txt`)
```text
fastapi==0.110.0
uvicorn==0.28.0
structlog==24.1.0
opentelemetry-api==1.24.0
opentelemetry-sdk==1.24.0
opentelemetry-instrumentation-fastapi==0.45b0
prometheus-client==0.20.0
```

### 2. Implementasi Layanan Produksi (`main.py`)
```python
import time
import structlog
from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# ---------------------------------------------------------
# A. INSTRUMENTASI TRACING (OpenTelemetry)
# ---------------------------------------------------------
trace.set_tracer_provider(TracerProvider())
tracer_provider = trace.get_tracer_provider()
# Menggunakan ConsoleExporter untuk demonstrasi lokal; ganti dengan OTLPSpanExporter di produksi
tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
tracer = trace.get_tracer("payment-service", "1.0.0")

# ---------------------------------------------------------
# B. INSTRUMENTASI METRICS (Prometheus Client)
# ---------------------------------------------------------
HTTP_REQUEST_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests processed",
    ["method", "endpoint", "status"]
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency distributions",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
)

# ---------------------------------------------------------
# C. INSTRUMENTASI LOGGING (Structlog JSON)
# ---------------------------------------------------------
def add_opentelemetry_spans(_, __, event_dict):
    span = trace.get_current_span()
    if span != trace.INVALID_SPAN:
        ctx = span.get_span_context()
        if ctx.is_valid:
            event_dict["trace_id"] = f"{ctx.trace_id:032x}"
            event_dict["span_id"] = f"{ctx.span_id:016x}"
    return event_dict

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        add_opentelemetry_spans,
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()

# ---------------------------------------------------------
# D. CORE APPLICATION
# ---------------------------------------------------------
app = FastAPI(title="Payment Service")

@app.middleware("http")
async def telemetry_middleware(request: Request, call_next):
    start_time = time.time()
    endpoint = request.url.path
    method = request.method
    
    # Jalankan request dalam konteks Span OpenTelemetry
    with tracer.start_as_current_span(f"{method} {endpoint}") as span:
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            status_code = 500
            span.record_exception(exc)
            span.set_status(trace.StatusCode.ERROR, str(exc))
            raise exc from None
        finally:
            duration = time.time() - start_time
            # Observasi metrics
            HTTP_REQUEST_TOTAL.labels(method=method, endpoint=endpoint, status=status_code).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=endpoint).observe(duration)
            
            # Emit structured access log terkorelasi otomatis dengan TraceID
            logger.info(
                "http_request_finished",
                method=method,
                endpoint=endpoint,
                status=status_code,
                duration=duration
            )

@app.get("/api/v1/pay")
async def process_payment(amount: float):
    logger.info("processing_payment_started", amount=amount)
    
    # Sub-span untuk tracing operasi internal
    with tracer.start_as_current_span("authorize_with_bank"):
        if amount > 1000:
            logger.warn("high_value_transaction_flagged", amount=amount)
            time.sleep(0.15) # Simulasi latensi verifikasi tambahan
        else:
            time.sleep(0.02)
            
    return {"status": "SUCCESS", "amount": amount}

@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi | Pendekatan Terlalu Minim (Under-instrumentation) | Pendekatan Optimal | Pendekatan Berlebih (Over-instrumentation) |
| :--- | :--- | :--- | :--- |
| **CPU & Memory Overhead** | Ringan (<1% resource overhead), namun sistem menjadi *black box*. | 2-5% CPU overhead dengan batch processing span dan asynchronous log writing. | >25% CPU overhead akibat kalkulasi trace regex berlebihan atau tracing per baris fungsi kode. |
| **Penyimpanan (Storage)** | Murah; kapasitas disk terpakai sangat kecil. | Terkendali dengan retensi log adaptif (misal: 14 hari) dan *head/tail sampling* pada tracing. | Bengkak (*disk full*); biaya database log/trace meningkat drastis akibat menyimpan jutaan log debug di produksi. |
| **Kardinalitas Metrik** | Hanya metrik sistem generik (CPU, Memory). Analisis bisnis mustahil. | Dimensi label terkendali (misal: `status_code`, `method`, `service_name`). | **Cardinality Explosion**: Menjadikan `user_id`, `email`, atau `order_id` sebagai label Prometheus yang merusak memory server. |
| **Sampling Rate Tracing** | 0% Traces (Hanya menebak alur masalah). | *Adaptive Sampling* (100% sampel pada rute error/berlatensi tinggi, 1-5% pada rute sukses). | 100% tracing statis pada jutaan RPS, menjenuhkan I/O jaringan dan storage backend APM. |

---

## SEKSI 11 — BEST PRACTICES

1.  **Gunakan Format JSON untuk Logging:** Jangan pernah menggunakan *unstructured string formatting* di level aplikasi (hindari format teks polos `2023-01-01 [INFO] user logged in`). Terapkan format JSON satu baris (*ndjson*) agar *log shipper* (seperti FluentBit, Vector) dapat langsung menguraikan data tanpa regex kompleks.
2.  **Standardisasi Label/Tag Telemetri (Semantic Conventions):** Gunakan standar nama tag dari OpenTelemetry, misalnya `http.status_code`, `service.name`, `db.system`. Hindari variasi inkonsisten antar tim (seperti `service_name` vs `app` vs `application`).
3.  **Terapkan Metodologi RED untuk Microservices:**
    *   **Rate:** Jumlah permintaan per detik (`rate(http_requests_total[1m])`).
    *   **Errors:** Jumlah permintaan yang gagal (`rate(http_requests_total{status=~"5.."}[1m])`).
    *   **Duration:** Lama eksekusi permintaan dalam persentil p50, p95, p99 (`histogram_quantile(...)`).
4.  **Terapkan Metodologi USE untuk Infrastruktur:**
    *   **Utilization:** Persentase waktu resource sibuk (misal: CPU Usage %).
    *   **Saturation:** Antrean pekerjaan ekstra yang tidak bisa langsung dilayani (misal: CPU Load Average / Run Queue).
    *   **Errors:** Jumlah kejadian error pada level perangkat keras/driver jaringan.
5.  **Inject Trace ID ke Header Response:** Kirimkan Trace ID kembali ke klien melalui response header (contoh: `X-Trace-Id`). Ketika pengguna mengalami kendala, tim customer support cukup meminta ID ini untuk langsung menemukan trace dan log terkait.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1.  **High Cardinality Explosion pada Metrik:**
    *   *Anti-pattern:* Menambahkan label dinamis tanpa batas ke Prometheus.
        ```python
        # FATAL! Memory Prometheus akan meledak (OOM Kill)
        PAYMENT_COUNTER.labels(user_id=user.id, order_id=order.id).inc()
        ```
    *   *Solusi:* Simpan `user_id` dan `order_id` di dalam Log atau Tracing Span Attributes, **bukan** pada dimensi metrik.
2.  **Logging Data Sensitif (PII Leakage):**
    *   *Anti-pattern:* Melakukan dumping request payload mentah ke log (`logger.info("Payload", body=request.json)`), yang berpotensi memuat nomor kartu kredit, password, atau identitas pribadi.
    *   *Solusi:* Buat layer *sanitization* atau *masking* otomatis sebelum data dicetak ke stdout.
3.  **Logging Sync Blocking:**
    *   *Anti-pattern:* Menulis log langsung ke file fisik di disk secara synchronous dalam thread request processing. Disk I/O bottleneck akan langsung mendegradasi seluruh throughput aplikasi.
    *   *Solusi:* Tulis log ke `stdout`/`stderr` secara non-blocking; delegasikan penanganan buffering dan disk write ke container runtime atau log agent.
4.  **Menyamakan Health Check dengan Deep Dependency Testing:**
    *   *Anti-pattern:* Menjalankan query database berat di endpoint `/healthz` yang diakses Kubernetes setiap 5 detik. Hal ini dapat membebani basis data (*cascading failure*).
    *   *Solusi:* Bedakan `/live` (apakah web engine hidup) dan `/ready` (apakah dependensi siap menerima traffic).

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Lab Setup
Pastikan sistem telah terinstal Python 3.10+, Docker, dan `curl`.

```bash
mkdir -p observability-lab && cd observability-lab
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn structlog prometheus-client opentelemetry-api opentelemetry-sdk
```

---

### Latihan 1: Guided (Membangun Structured Logging & Context Correlation)
**Tujuan:** Menghubungkan log dengan Trace ID secara deterministik.
1. Buat file `lab1.py`.
2. Salin kode dari **SEKSI 09 (Contoh Praktis)**.
3. Jalankan aplikasi: `uvicorn lab1:app --host 0.0.0.0 --port 8000`.
4. Eksekusi request menggunakan curl:
   ```bash
   curl -X GET "http://localhost:8000/api/v1/pay?amount=500"
   ```
5. **Tugas Inspeksi:** Periksa log terminal stdout. Pastikan bahwa log `processing_payment_started` dan log `http_request_finished` memiliki nilai `trace_id` yang identik.

---

### Latihan 2: Semi-Guided (Mencegah Cardinality Explosion)
**Tujuan:** Menguji dan memperbaiki bug kardinalitas pada metrik.
1. Di `lab1.py`, seorang engineer pemula menambahkan metrik berikut:
   ```python
   USER_LOGINS = Counter("user_logins_total", "Count logins", ["user_email"])
   ```
2. **Tugas Anda:** 
   * Identifikasi mengapa implementasi tersebut melanggar best practices di lingkungan produksi berskala 100.000 pengguna.
   * Modifikasi kode tersebut untuk mencatat tipe login menggunakan bounded value (misal: label `auth_method` yang hanya bernilai `"google"`, `"password"`, atau `"sso"`).
   * Pindahkan identitas pengguna (`user_email`) agar hanya tercatat di log konteks dan trace attributes.

---

### Latihan 3: Challenge (Implementasi Latency Anomaly & Metrics Scrape)
**Tujuan:** Membuat endpoint baru yang memiliki probabilitas latensi acak dan memverifikasinya melalui metrik histogram.
1. Tambahkan endpoint `/api/v1/heavy-task` pada aplikasi.
2. Atur mekanisme di mana 80% request selesai dalam < 50ms, dan 20% request mengalami degradasi (sleep antara 1.5 - 2 detik).
3. Buat kegagalan acak (*status 500 Internal Error*) sebesar 10% dari total request.
4. Jalankan *load testing* mini menggunakan loop bash:
   ```bash
   for i in {1..50}; do curl -s "http://localhost:8000/api/v1/heavy-task" > /dev/null; done
   ```
5. Akses `http://localhost:8000/metrics` menggunakan curl, temukan bucket `http_request_duration_seconds_bucket`, dan analisis:
   * Berapa jumlah request yang jatuh pada bucket `>= 1.0` detik?
   * Berapa hitungan metrik `http_requests_total` dengan status code 500?

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan-pertanyaan berikut untuk menguji pemahaman Anda:

#### 1. Perusahaan Anda mengalami insiden di mana p99 latency melonjak drastis, tetapi rata-rata CPU dan memory utilisation server normal (30%). Pilar telemetri mana yang HARUS pertama kali Anda periksa untuk mengisolasi komponen yang bermasalah?
*   A. Metrics host server.
*   B. Distributed Traces untuk melihat waterfall chart durasi tiap span.
*   C. Log sistem operasi via `dmesg`.
*   D. Status interface jaringan router fisik.

#### 2. Apa yang akan terjadi jika Anda menggunakan `credit_card_number` sebagai label dalam metrik Prometheus?
*   A. Prometheus akan otomatis mengenkripsi data tersebut.
*   B. Terjadi *High Cardinality Explosion*, yang menyebabkan konsumsi RAM Prometheus meningkat drastis hingga *crash* (OOM).
*   C. Format ditolak oleh compiler Python.
*   D. Kecepatan query Prometheus menjadi lebih cepat karena datanya unik.

#### 3. Manakah format log berikut yang paling ideal untuk diparsing oleh log collector otomatis di production?
*   A. `2023-10-24 10:00:00 ERROR connection timeout to db-slave-01`
*   B. `[Oct 24 10:00:00] [error] [pid 1234] connection timeout`
*   C. `{"timestamp":"2023-10-24T10:00:00Z","level":"ERROR","message":"connection timeout","target":"db-slave-01","trace_id":"e3b0c442"}`
*   D. `db-slave-01 failed at 10:00:00 with connection timeout!`

#### 4. Header HTTP standar yang disepakati oleh W3C untuk mendistribusikan konteks tracing lintas microservice adalah...
*   A. `X-Request-ID`
*   B. `traceparent`
*   C. `X-B3-TraceId`
*   D. `Authorization`

#### 5. Kapan sebaiknya Anda menggunakan Metrics dibandingkan Logs?
*   A. Saat Anda butuh mengetahui detail pesan *stack trace* error dari sebuah crash.
*   B. Saat Anda ingin menyimpan snapshot parameter input payload dari sebuah transaksi.
*   C. Saat Anda ingin mendeteksi tren performa jangka panjang dan mengonfigurasi aturan peringatan (*alerting rules*).
*   D. Saat Anda butuh audit compliance per user yang masuk ke sistem.

---

### Kunci Jawaban & Rasional

1.  **Jawaban: B.** Distributed traces dirancang khusus untuk membedah *latency breakdown* ujung-ke-ujung dan mengidentifikasi dependensi lambat (*bottleneck*) dalam pemanggilan bertingkat.
2.  **Jawaban: B.** Setiap kombinasi unik label menciptakan satu *time-series* baru di Prometheus. Jutaan nomor kartu unik akan melipatgandakan jumlah time-series, menghabiskan memori RAM server, dan berpotensi melanggar kepatuhan PCI-DSS.
3.  **Jawaban: C.** JSON terstruktur satu baris (*structured JSON*) dapat diparsing langsung oleh agent telemetri modern secara efisien tanpa memerlukan kompilasi regular expression (*regex*) yang lambat dan rentan error.
4.  **Jawaban: B.** Standar resmi W3C TraceContext menetapkan `traceparent` sebagai header utama pembawa Trace ID dan Span ID lintas dependensi HTTP.
5.  **Jawaban: C.** Metrics sangat efisien dalam komputasi dan penyimpanan, menjadikannya pilihan ideal untuk *time-series alerting*, agregasi matematis, dan visualisasi grafik tren jangka panjang.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

*   **Buku:**
    *   *Observability Engineering: Achieving Production Excellence* (Charity Majors, Liz Fong-Jones, George Miranda) - O'Reilly Media.
    *   *Site Reliability Engineering: How Google Runs Production Systems* (Niall Richard Murphy et al.) - Bab: Practical Alerting from Time-Series Data.
*   **Dokumentasi Resmi & Standar:**
    *   OpenTelemetry Documentation: [https://opentelemetry.io/docs/](https://opentelemetry.io/docs/)
    *   W3C Trace Context Specification: [https://www.w3.org/TR/trace-context/](https://www.w3.org/TR/trace-context/)
    *   Prometheus Best Practices (Metric and Label Naming): [https://prometheus.io/docs/practices/naming/](https://prometheus.io/docs/practices/naming/)
*   **Video / Whitepaper:**
    *   Google Cloud Architecture Center: *The Google SRE Perspective on Monitoring and Alerting*.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1.  **Fondasi Sistem Kontrol:** Observabilitas bukan sekadar alat monitoring yang diperbarui, melainkan kemampuan inferensi keadaan internal sistem dari representasi data eksternalnya.
2.  **Tiga Pilar & Sinerginya:**
    *   **Metrics:** Mengukur *apakah ada masalah* dan seberapa masif skalanya.
    *   **Traces:** Menemukan *di mana letak masalah* dalam topologi jaringan terdistribusi.
    *   **Logs:** Mendiagnosis *mengapa masalah terjadi* lewat konteks detail kejadian.
3.  **Korelasi adalah Kunci:** Telemetri yang terisolasi menciptakan *information silos*. Korelasi deterministik melalui injeksi `Trace ID` ke dalam structured log JSON merupakan syarat fundamental arsitektur observabilitas modern.
4.  **Disiplin Kardinalitas:** Jaga agar dimensi label metrik tetap terbatas (*bounded values*). Hindari memasukkan *unique identifiers* ke dalam storage metrik time-series.

---

## SEKSI 17 — GLOSARIUM

*   **Observability:** Derajat visibilitas keadaan internal sistem perangkat lunak yang disimpulkan dari data telemetrinya.
*   **Telemetry:** Data operasional yang dipancarkan secara otomatis oleh aplikasi/infrastruktur (Metrics, Events, Logs, Traces).
*   **High Cardinality:** Tingginya jumlah kemungkinan kombinasi nilai unik pada sebuah label atau dimensi kumpulan data.
*   **Span:** Satuan unit kerja terkecil dalam distributed tracing yang merepresentasikan sebuah operasi dengan waktu awal dan durasi tertentu.
*   **Trace:** Koleksi satu atau lebih *Spans* yang merepresentasikan perjalanan ujung-ke-ujung dari suatu request/eksekusi.
*   **Context Propagation:** Proses serialisasi dan transfer metadata tracing (Trace ID, Span ID) melintasi batas proses (*process boundaries*), seperti thread atau jaringan HTTP/gRPC.
*   **Structured Logging:** Praktik penulisan pesan log menggunakan skema terstruktur yang mudah diparsing mesin (biasanya JSON), bukan teks bebas.
*   **SLO (Service Level Objective):** Target reliabilitas layanan terukur yang disepakati secara formal (misalnya: 99.9% request harus berhasil dengan latensi di bawah 200ms).

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Poin Penekanan Materi:** Pastikan peserta memahami bahwa *Observability* adalah karakteristik arsitektur sistem, bukan sekadar instalasi software monitoring seperti Prometheus atau Grafana.
*   **Jebakan Konseptual Pemula:** Peserta pemula sering kali mencampuradukkan konsep Trace ID dan Span ID. Tekankan analogi: *Trace ID adalah identitas satu tiket perjalanan kereta, sedangkan Span ID adalah karcis per segmen stasiun yang dilewati*.
*   **Fasilitasi Lab:** Jika peserta mengalami kegagalan pada saat instalasi package OpenTelemetry, pastikan environment Python bersih menggunakan *virtual environment* (`venv`). Demonstrasikan cara melihat raw output JSON di console untuk memastikan pemahaman bentuk data telemetri sebelum beralih ke UI visual seperti Jaeger.

---

## SEKSI 19 — CHANGELOG & VERSI

| Versi | Tanggal Rilis | Penulis / Maintainer | Catatan Perubahan |
| :--- | :--- | :--- | :--- |
| `1.0.0` | 2024-03-29 | Senior Technical Curriculum Architect | Rilis kurikulum awal, standar format 20 seksi berbasis OpenTelemetry dan Python FastAPI. |

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya:** `DO-CF-08-01`: Dasar-Dasar Networking & Security untuk Praktisi DevOps.
*   **Modul Saat Ini:** `DO-CF-09-01`: Fondasi Observabilitas: Metrics, Logs, & Traces.
*   **Modul Berikutnya:** `DO-CF-10-01`: Pengenalan Distributed Tracing dengan Jaeger & Grafana Tempo.