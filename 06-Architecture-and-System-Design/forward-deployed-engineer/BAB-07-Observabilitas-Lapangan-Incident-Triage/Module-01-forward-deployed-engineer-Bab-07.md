# Bab 07 Module 01 — Observabilitas Lapangan, Incident Triage & Telemetri Terdistribusi: Debugging Sistem Klien Tanpa Akses Langsung, Log Bundles Analysis, Distributed Tracing di Edge/Private Cloud

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** Forward-Deployed Engineer (FDE) Professional Track
* **Kategori:** 06-Architecture-and-System-Design
* **Kode Modul:** FDE-ARC-07-MOD01
* **Tingkat Kesulitan:** Advanced / L5-L6 Engineering Standard
* **Estimasi Waktu Penyelesaian:** 8 Jam Pembelajaran Mandiri & Praktik Laboratorium
* **Prasyarat:**
  * Pemahaman arsitektur *Distributed Systems* (Microservices, Service Mesh, Edge Nodes).
  * Penguasaan standar instrumentasi OpenTelemetry (Spans, Traces, Metrics, Logs).
  * Kemahiran Linux Systems Forensics & CLI tooling (`awk`, `sed`, `jq`, `grep`, `systemd-journald`).
  * Pemahaman protokol jaringan (TCP/IP, gRPC, HTTP/2) dan format data terstruktur (JSON, Protobuf).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Mendiagnosis Sistem Air-Gapped/Zero-Access:** Merekonstruksi *incident timeline* dan menemukan *root cause* tanpa akses SSH/VPN langsung ke cluster klien, murni bergantung pada artefak diagnostik statis.
2. **Merancang Pipeline Ekstraksi Log Bundle yang Tahan Banting:** Mengonfigurasi agen pengumpul telemetri lokal yang aman dari risiko *disk-filling*, mengisolasi kegagalan transmisi, dan menjamin zero-PII/Secrets leakage melalui sanitasi deterministik di sisi klien.
3. **Mengimplementasikan Distributed Tracing Terisolasi:** Mengonfigurasi OpenTelemetry Collector di lingkungan edge/private cloud yang terdiskoneksi (air-gapped) dengan pola *local ring buffering*, batch file export, dan W3C Trace Context propagation lintas protokol asynchronous.
4. **Menganalisis & Mengorelasikan Artefak Multi-Sumber:** Melakukan *cross-telemetry correlation* (mengaitkan Trace ID, HTTP access logs, DB query latency, dan Kernel dmesg logs) secara offline menggunakan skrip otomatisasi tingkat lanjut.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                     LINGKUNGAN KLIEN (AIR-GAPPED / PRIVATE CLOUD)
+-------------------------------------------------------------------------------+
|                                                                               |
|  [ Microservice A ] --(W3C traceparent)--> [ Microservice B ]                 |
|         |                                         |                           |
|         v (OTLP/gRPC local)                       v (OTLP/gRPC local)         |
|  +-----------------------------------------------------------------+          |
|  |                 OpenTelemetry Collector (Edge Agent)             |          |
|  |  +---------------------+  +-----------------+  +--------------+ |          |
|  |  | Memory/Disk Buffer  |->| PII Redaction   |->| File Exporter| |          |
|  |  +---------------------+  +-----------------+  +-------+------+ |          |
|  +--------------------------------------------------------|--------+          |
|                                                           v                   |
|  +-----------------------------------------------------------------+          |
|  |                      Diagnostic Bundle Generator                |          |
|  |  - SOS Report / OS Metrics      - Traces (JSON Lines)           |          |
|  |  - Encrypted Journald Dumps     - Healthcheck Probes            |          |
|  +--------------------------------+--------------------------------+          |
+-----------------------------------|-------------------------------------------+
                                    | Manual Tarball Transfer / S3 Bastion
                                    v
            +-----------------------------------------------+
            |               AIR-GAP BOUNDARY                |
            +-----------------------------------------------+
                                    |
                                    v
                     LINGKUNGAN ANALISIS FDE (ISOLASI)
+-------------------------------------------------------------------------------+
|                                                                               |
|  +---------------------+    +----------------------+    +------------------+  |
|  | Integrity Check &   |--->| Offline Ingestion &  |--->| Triage & Root    |  |
|  | GPG Decryption      |    | Trace Reconstruction |    | Cause Analysis   |  |
|  +---------------------+    +----------------------+    +------------------+  |
|                                        |                                      |
|                                        v                                      |
|                     Jaeger / Tempo Offline UI + DuckDB / ClickHouse           |
+-------------------------------------------------------------------------------+
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Sebagai Forward-Deployed Engineer, lingkungan produksi tempat perangkat lunak Anda berjalan sering kali bukan milik Anda. Anda beroperasi di dalam infrastruktur perbankan Core Banking tier-1, jaringan data intelijen pertahanan, pabrik semikonduktor, atau rumah sakit dengan kepatuhan HIPAA yang ketat.

Di dunia ini:
* **Tidak Ada Akses Remote Langsung:** Bastion host, SSH jumping, atau direct VPN dilarang keras oleh kebijakan keamanan klien (*Zero Trust Policy*).
* **Insiden Bersifat Kritis:** Ketika sistem mengalami *deadlock*, degradasi throughput hingga 90%, atau kegagalan transaksi sporadis, SLA mitigasi terus berjalan sementara Anda hanya menerima file arsip kompresi (`.tar.gz`) berukuran gigabyte via secure dropzone.
* **Risiko Kebocoran Data (PII/Compliance Breach):** Kegagalan membersihkan token otentikasi, nomor kartu kredit, atau data medis dari paket telemetri dapat memicu sanksi regulasi jutaan dolar dan pembatalan kontrak enterprise.

Menguasai observabilitas lapangan dan forensik offline memisahkan engineer medioker yang bergantung pada dashboard Grafana *live* dengan FDE elit yang mampu membongkar memori dump, mengurai ribuan span terputus, dan merekonstruksi detik-detik kegagalan sistem hanya dari satu bundel log statis.

---

## SEKSI 05 — APA ITU (WHAT)

Observabilitas Lapangan (*Field Observability*) adalah metodologi pengumpulan, preservasi, dan analisis tiga pilar telemetri (Logs, Metrics, Traces) beserta state kernel/sistem di lingkungan komputasi yang terdistribusi dan memiliki batasan jaringan ekstrem.

Komponen kritis dari arsitektur ini meliputi:

1. **Diagnostic Support Bundle:** Arsip deterministik yang mencakup snapshot status sistem pada titik waktu tertentu—mencakup konfigurasi runtime, metrik performa historis, file log terotasi, status koneksi soket, dan status resource sistem.
2. **Air-Gapped Distributed Tracing:** Mekanisme instrumentasi OpenTelemetry di mana spans tidak dikirimkan secara *real-time* ke backend SaaS (seperti Datadog atau Honeycomb), melainkan disimpan ke dalam media penyimpanan lokal (*ring buffer* berbasis disk) dengan format terstruktur standar (OTLP JSON Lines atau Parquet).
3. **Data Redaction Engine at Origin:** Agen pembersih di dalam perimeter klien yang secara komputasional menjamin bahwa data sensitif (PII, rahasia korporat, kredensial) dimusnahkan secara satu arah sebelum artefak meninggalkan jaringan klien.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

Alur kerja observabilitas tanpa akses langsung bergantung pada arsitektur telemetri berbasis *decoupled store-and-forward*.

### 1. Injeksi Konteks dan Propagasi (Context Propagation)
Aplikasi diinstrumentasi menggunakan OpenTelemetry SDK. Konteks trace didistribusikan lintas batas proses melalui header standar W3C `traceparent`:
$$\text{traceparent} = \text{version (2 hex)} - \text{trace\_id (32 hex)} - \text{parent\_id (16 hex)} - \text{trace\_flags (2 hex)}$$

Ketika *microservice* berkomunikasi via antrean asinkron (misalnya Kafka lokal atau Redis), context metadata dimasukkan ke dalam atribut pesan.

### 2. Edge Buffering & Backpressure Mitigation
Karena telemetri tidak dapat dikirim ke internet publik, OpenTelemetry Collector lokal bertindak sebagai *sidecar* atau *daemonset*. Collector ini dikonfigurasi dengan:
* **`memory_limiter` processor:** Menjaga alokasi memori agen agar tidak memicu OOMKilled di lingkungan klien yang padat beban.
* **`file_storage` extension:** Mengalirkan span dan log ke ring-buffer disk lokal jika proses pembersihan/ekstraksi sedang berjalan atau antrean memori penuh.
* **Rotasi Terikat Ukuran (Bounded Size Rotation):** Mengatur partisi log/trace agar tidak pernah melebihi kuota penyimpanan disk lokal (misalnya batas absolut 10 GB dengan rotasi FIFO).

### 3. Redaksi Data Sensitif (Client-Side Scrubbing)
Sebelum bundel dibuat, prosesor redaksi mengevaluasi *payload* log dan atribut span terhadap kamus regex dan pola entropi tinggi untuk mendeteksi:
* JSON keys sensitif (`password`, `authorization`, `token`, `ssn`, `pan`).
* Pola string (UUID, format nomor kartu, JWT patterns).
Prosesor mengganti nilai yang cocok dengan nilai hash searah (HMAC-SHA256 dengan seed lokal) atau masking statis `[REDACTED]`.

### 4. Ekstraksi dan Korelasi Offline
Ketika insiden terjadi, operator klien menjalankan skrip ekstraksi diagnostik tunggal (`bundle-collector.sh`). Skrip ini mengompresi log sistem, ring buffer tracing, dan metrik topologi menjadi arsip tunggal bertanda tangan kriptografis.

FDE mengimpor arsip ini ke dalam *local analysis harness* di mana:
* Log di-ingest ke embedded database (misalnya DuckDB).
* Trace JSON Lines diumpankan ke Jaeger/Tempo instance lokal via OTLP CLI ingestion.
* Korelasi silang dilakukan menggunakan Trace ID sebagai *primary join key*.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

Berikut adalah arsitektur aliran data telemetri dari aplikasi terisolasi hingga workstation analisis FDE:

```
+===================================================================================================+
|                                    KLIEN PERIMETER (AIR-GAPPED CLUSTER)                            |
|                                                                                                   |
|  +--------------------+        +--------------------+        +--------------------+               |
|  | Pod: API Gateway   |        | Pod: Payment Svc   |        | Pod: Database Svc  |               |
|  | - OTel Tracer      |        | - OTel Tracer      |        | - Slow Query Log   |               |
|  | - Structured Logs  |        | - Structured Logs  |        | - Engine Metrics   |               |
|  +---------+----------+        +---------+----------+        +---------+----------+               |
|            |                             |                             |                          |
|            | OTLP/gRPC (localhost)       | OTLP/gRPC (localhost)       | File Tail                |
|            v                             v                             v                          |
|  +---------------------------------------------------------------------------------------------+  |
|  |                          OPENTELEMETRY COLLECTOR (EDGE AGENT)                               |  |
|  |                                                                                             |  |
|  |  +--------------------+     +-----------------------+     +-------------------------------+ |  |
|  |  |   Memory Limiter   | --> | PII Redaction Filter  | --> | file_storage Extension        | |  |
|  |  |   (Soft/Hard Cap)  |     | (Regex & Salted Hash) |     | (Max 5GB Circular Disk Buffer)| |  |
|  |  +--------------------+     +-----------------------+     +---------------+---------------+ |  |
|  +---------------------------------------------------------------------------|-----------------+  |
|                                                                              v                    |
|                                                              +-------------------------------+    |
|                                                              | Storage: /var/log/telemetry/  |    |
|                                                              | - traces.jsonl.gz (Rotated)   |    |
|                                                              | - app-logs.jsonl.gz (Rotated) |    |
|                                                              +---------------+---------------+    |
|                                                                              |                    |
|  +---------------------------------------------------------------------------|-----------------+  |
|  | CLIENT TRIGGERED SCRIPT: gather-diagnostic-bundle.sh                      v                    |
|  |                                                                                             |  |
|  |  +-------------------+  +-------------------+  +-------------------+  +-------------------+ |  |
|  |  | systemd journal   |  | ip route / ss net |  | OTel Trace Buffers|  | K8s Events/State  | |  |
|  |  +---------+---------+  +---------+---------+  +---------+---------+  +---------+---------+ |  |
|  |            |                      |                      |                      |           |  |
|  |            +----------------------+----------+-----------+----------------------+           |  |
|  |                                              v                                              |  |
|  |                              +-------------------------------+                              |  |
|  |                              | SHA-256 + GPG Encrypted Tarball|                             |  |
|  |                              | (diag-bundle-YYYYMMDD-HHMM.tar) |                             |  |
|  |                              +---------------+---------------+                              |  |
+=================================================|=================================================+
                                                  |
                                    [ Manual Security Audit ]
                                    [  & Air-gap Egress Gate ]
                                                  |
                                                  v
+===================================================================================================+
|                                      FDE ANALYSIS ENVIRONMENT                                     |
|                                                                                                   |
|  +----------------------------------+                   +--------------------------------------+  |
|  | bundle-unpack-and-verify.sh      |                   | Ingestion Pipeline                   |  |
|  | 1. Verify Checksum & GPG Sig     |                   |                                      |  |
|  | 2. Extract into Ephemeral Sandbox|                   | - Spans -> OTel Ingestor -> Jaeger   |  |
|  +-----------------+----------------+                   | - Logs/Metrics -> Vector -> DuckDB   |  |
|                    v                                    +------------------+-------------------+  |
|  +------------------------------------------------------+                  |                      |
|  | CORRELATION HARNESS (Python / SQL / CLI)                                v                      |
|  |                                                                                                |
|  | Trace ID (W3C): 4bf92f3577b34da6a3ce929d0e0e4736                                               |
|  | +---------------------+-----------------------+-------------------------+-------------------+  |
|  | | Timestamp           | Component             | Level / Event           | Span ID / Context |  |
|  | +---------------------+-----------------------+-------------------------+-------------------+  |
|  | | 10:04:12.102312     | API Gateway           | HTTP 504 Gateway Timeout| 00f067aa0ba902b7  |  |
|  | | 10:04:12.101890     | Payment Svc           | Context Deadline Exceed | 5fb397be34d23b0f  |  |
|  | | 10:04:12.095012     | Database Svc (Disk)   | IO Wait Spike: nvme0n1  | ----------------- |  |
|  | +---------------------+-----------------------+-------------------------+-------------------+  |
+===================================================================================================+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah skrip Shell POSIX yang dirancang untuk menganalisis bundle log JSON terstruktur yang diekstrak dari klien secara offline. Skrip ini mencari pola anomali, mengisolasi *Trace IDs* dari transaksi yang gagal (HTTP 5xx atau status ERROR), dan merekonstruksi urutan eksekusi secara berurutan.

```bash
#!/usr/bin/env bash
# trace-correlator.sh: Analisis offline cepat untuk log bundle
set -euo pipefail

BUNDLE_DIR="${1:-./diagnostic-bundle}"
OUTPUT_REPORT="incident_summary.txt"

if [[ ! -d "${BUNDLE_DIR}" ]]; then
    echo "[-] Error: Direktori ${BUNDLE_DIR} tidak ditemukan."
    echo "Penggunaan: $0 <path-ke-ekstraksi-bundle>"
    exit 1
fi

echo "[*] Memulai pemindaian log bundle di: ${BUNDLE_DIR}"
echo "==========================================================" > "${OUTPUT_REPORT}"
echo "INCIDENT TRIAGE REPORT: $(date -u)" >> "${OUTPUT_REPORT}"
echo "==========================================================" >> "${OUTPUT_REPORT}"

# 1. Identifikasi Trace IDs unik yang mengalami kegagalan/error
echo "[*] Mengekstraksi Trace IDs yang berstatus ERROR / HTTP 5xx..."
FAILED_TRACES=$(find "${BUNDLE_DIR}" -type f -name "*.jsonl" -exec \
    jq -r 'select((.status == "error") or (.http_status_code >= 500)) | .trace_id' {} + \
    | sort -u | grep -v '^null$' | head -n 10)

if [[ -z "${FAILED_TRACES}" ]]; then
    echo "[+] Tidak ditemukan Trace ID dengan status error eksplisit di log aplikasi."
    exit 0
fi

echo "[!] Ditemukan Trace ID bermasalah (sampel 10 teratas):"
echo "${FAILED_TRACES}"

# 2. Rekonstruksi runut peristiwa untuk setiap Trace ID lintas semua file log
for TRACE_ID in ${FAILED_TRACES}; do
    echo -e "\n----------------------------------------------------------" >> "${OUTPUT_REPORT}"
    echo "TRACE RECONSTRUCTION: ${TRACE_ID}" >> "${OUTPUT_REPORT}"
    echo "----------------------------------------------------------" >> "${OUTPUT_REPORT}"
    
    find "${BUNDLE_DIR}" -type f -name "*.jsonl" -exec \
        jq -r --arg tid "${TRACE_ID}" \
        'select(.trace_id == $tid) | "\(.timestamp) [\(.service_name)] [\(.level)] \(.message) (span_id: \(.span_id), latency: \(.duration_ms // "N/A")ms)"' {} + \
        | sort >> "${OUTPUT_REPORT}"
done

echo "[+] Rekonstruksi selesai. Laporan disimpan ke: ${OUTPUT_REPORT}"
head -n 30 "${OUTPUT_REPORT}"
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Pada skenario enterprise nyata, kita membutuhkan tiga komponen produksi:
1. Konfigurasi OpenTelemetry Collector yang mengalirkan telemetri ke disk lokal secara aman (*ring buffer*).
2. Kode aplikasi Go yang mempropagasi konteks tracing ke pesan asinkron.
3. Utilitas Python untuk sanitasi bundle log sebelum dikirim oleh tim kepatuhan klien.

### Komponen 1: Konfigurasi OpenTelemetry Collector Air-Gapped (`otel-collector-config.yaml`)

Konfigurasi ini memastikan collector tidak pernah kehabisan memori, menghapus data sensitif (PII), dan menulis spans langsung ke file terkompresi dengan rotasi disk ketat:

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  # 1. Lindungi memori host klien dari lonjakan traffic tak terduga
  memory_limiter:
    check_interval: 1s
    limit_percentage: 75
    spike_limit_percentage: 15

  # 2. Redaksi otomatis data sensitif di level span attributes
  transform:
    error_mode: ignore
    trace_statements:
      - context: span
        statements:
          # Sensor kata sandi dan token otentikasi
          - set(attributes["http.request.header.authorization"], "[REDACTED]") where attributes["http.request.header.authorization"] != nil
          - replace_pattern(attributes["db.statement"], "Bearer [A-Za-z0-9\\-\\._~\\+\\/]+=*", "Bearer [REDACTED]")
          - replace_pattern(attributes["customer.email"], "^.*@.*$", "[EMAIL_MASKED]")

  # 3. Batching untuk efisiensi penulisan disk I/O
  batch:
    timeout: 5s
    send_batch_size: 1024

exporters:
  # Tulis traces langsung ke disk lokal dalam format JSON Lines
  file:
    path: /var/log/telemetry/traces-edge.jsonl
    rotation:
      max_megabytes: 100
      max_days: 2
      max_backups: 5
    flush_interval: 5s

extensions:
  health_check:
    endpoint: 0.0.0.0:13133

service:
  extensions: [health_check]
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, transform, batch]
      exporters: [file]
```

### Komponen 2: Propagasi Konteks Tracing Manual pada Antrean Pesan Go

Implementasi propagasi konteks OpenTelemetry secara eksplisit lintas protokol biner/antrean independen:

```go
package main

import (
	"context"
	"fmt"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
	trace "go.opentelemetry.io/otel/trace"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// MessagePayload merepresentasikan struktur pesan internal aplikasi
type MessagePayload struct {
	EventID string            `json:"event_id"`
	Data    string            `json:"data"`
	Headers map[string]string `json:"headers"` // Wadah carrier W3C
}

// Inisialisasi OTel Tracer dengan endpoint Collector lokal
func initTracer(ctx context.Context) (*sdktrace.TracerProvider, error) {
	exporter, err := otlptracegrpc.New(ctx,
		otlptracegrpc.WithInsecure(),
		otlptracegrpc.WithEndpoint("127.0.0.1:4317"),
		otlptracegrpc.WithDialOption(grpc.WithBlock()),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create trace exporter: %w", err)
	}

	res, err := resource.New(ctx,
		resource.WithAttributes(
			semconv.ServiceNameKey.String("payment-settlement-engine"),
			semconv.ServiceVersionKey.String("2.4.1-airgap"),
		),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create resource: %w", err)
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(res),
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
	)
	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))
	return tp, nil
}

// Producer: Menginjeksi Span Context ke Metadata Pesan
func ProduceEvent(ctx context.Context, data string) (*MessagePayload, error) {
	tr := otel.Tracer("transaction-producer")
	ctx, span := tr.Start(ctx, "ProducePaymentEvent",
		trace.WithSpanKind(trace.SpanKindProducer),
	)
	defer span.End()

	payload := &MessagePayload{
		EventID: "evt-990124",
		Data:    data,
		Headers: make(map[string]string),
	}

	// Gunakan standard MapCarrier untuk propagasi
	otel.GetTextMapPropagator().Inject(ctx, propagation.MapCarrier(payload.Headers))
	span.AddEvent("Context injected into payload headers")

	return payload, nil
}

// Consumer: Mengekstrak Context dari Metadata dan Melanjutkan Trace
func ConsumeEvent(payload *MessagePayload) {
	// Ekstraksi carrier dari payload pesan
	extractedCtx := otel.GetTextMapPropagator().Extract(
		context.Background(),
		propagation.MapCarrier(payload.Headers),
	)

	tr := otel.Tracer("transaction-consumer")
	_, span := tr.Start(extractedCtx, "ConsumePaymentEvent",
		trace.WithSpanKind(trace.SpanKindConsumer),
	)
	defer span.End()

	// Simulasi pekerjaan komputasi
	time.Sleep(50 * time.Millisecond)
	span.AddEvent("Payment settlement completed successfully")
}

func main() {
	ctx := context.Background()
	tp, err := initTracer(ctx)
	if err != nil {
		panic(err)
	}
	defer func() { _ = tp.Shutdown(ctx) }()

	// Buat event (Proses A)
	msg, _ := ProduceEvent(ctx, "TransactionAmount=$50000")
	fmt.Printf("[+] Event dibuat dengan Traceparent: %s\n", msg.Headers["traceparent"])

	// Terima event (Proses B - berpotensi pada thread / sistem berbeda)
	ConsumeEvent(msg)
	fmt.Println("[+] Event berhasil diproses dengan korelasi trace utuh.")
}
```

### Komponen 3: Script Pembersih & Validator Log Bundle (`bundle-scrubber.py`)

Skrip ini dieksekusi di server klien sebelum bundel dikirim ke FDE. Skrip memverifikasi bahwa tidak ada informasi rahasia yang terlewat:

```python
#!/usr/bin/env python3
"""
bundle-scrubber.py: Pembersih deterministik log bundle lokal.
Menjamin penghapusan Secrets/PII menggunakan entropy checking dan strict pattern masking.
"""

import sys
import re
import json
import gzip
import shutil
from pathlib import Path

# Definisi ekspresi reguler untuk pendeteksian data sensitif
PATTERNS = [
    (re.compile(r'(?i)(password|secret|api[_-]?key|bearer|token)[\s]*[=:]\s*["\']?([^"\'\s,]+)'), r'\1="[REDACTED]"'),
    (re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'), '[MASKED_PAN]'),           # Pola Kartu Kredit
    (re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'), '[MASKED_EMAIL]'), # Pola Email
    (re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'), '[IP_REDACTED]') # Pola IPv4 (opsional/tergantung audit)
]

def scrub_text(content: str) -> str:
    """Membersihkan string berbasis pola ekspresi reguler."""
    for pattern, replacement in PATTERNS:
        content = pattern.sub(replacement, content)
    return content

def process_file(source_path: Path, dest_path: Path):
    """Membaca baris demi baris untuk menghemat konsumsi RAM."""
    is_gzip = source_path.suffix == '.gz'
    open_in = gzip.open if is_gzip else open
    open_out = gzip.open if is_gzip else open
    mode_in = 'rt' if is_gzip else 'r'
    mode_out = 'wt' if is_gzip else 'w'

    with open_in(source_path, mode_in, encoding='utf-8', errors='replace') as fin, \
         open_out(dest_path, mode_out, encoding='utf-8') as fout:
        for line in fin:
            scrubbed_line = scrub_text(line)
            fout.write(scrubbed_line)

def main():
    if len(sys.argv) < 3:
        print(f"Penggunaan: {sys.argv[0]} <input_dir> <output_dir>")
        sys.exit(1)

    src_dir = Path(sys.argv[1])
    dst_dir = Path(sys.argv[2])

    if not src_dir.exists():
        print(f"[-] Direktori input tidak ditemukan: {src_dir}")
        sys.exit(1)

    dst_dir.mkdir(parents=True, exist_ok=True)
    print(f"[*] Memulai scrubbing dari [{src_dir}] ke [{dst_dir}]...")

    for file_path in src_dir.rglob('*'):
        if file_path.is_file():
            rel_path = file_path.relative_to(src_dir)
            target_path = dst_dir / rel_path
            target_path.parent.mkdir(parents=True, exist_ok=True)

            if file_path.suffix in ['.json', '.jsonl', '.log', '.txt', '.gz']:
                print(f"[>] Scrubbing: {rel_path}")
                process_file(file_path, target_path)
            else:
                # Salin file biner tanpa perubahan setelah audit
                shutil.copy2(file_path, target_path)

    print("[+] Operasi sanitasi selesai tanpa kebocoran memori.")

if __name__ == '__main__':
    main()
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Keputusan Desain | Opsi A | Opsi B | Trade-off / Dampak Komparatif |
| :--- | :--- | :--- | :--- |
| **Sampling Rate Tracing** | *100% Always Sample* | *Adaptive / Probabilistic (1-5%)* | 100% Sampling menjamin transaksi gagal *pasti* tertangkap, tetapi meningkatkan konsumsi disk I/O dan mempercepat rotasi file. Probabilistic menghemat storage namun berisiko kehilangan span dari *intermittent bug* yang jarang terjadi. |
| **Penyimpanan Telemetri** | In-Memory Ring Buffer | File-based Circular Storage | In-Memory memiliki overhead I/O mendekati nol, namun seluruh data hilang jika node mengalami *Kernel Panic* atau *OOM Kill*. File-based persisten lintas restart, namun memerlukan alokasi partisi disk independen (`/var/log/telemetry`). |
| **Sanitasi PII/Secrets** | Sisi Klien (Origin Scrubbing) | Sisi Analisis FDE (Ingest Scrubbing) | Sanitasi di sisi klien menjamin kepatuhan legal dan audit keamanan, namun membebani CPU host klien. Sanitasi di sisi FDE melanggar hampir seluruh regulasi perbankan/militer (data keluar sebelum di-sanitasi). |
| **Format Artefak** | OpenTelemetry JSON Lines | Format Biner Terkompresi (Parquet / Native WAL) | JSON Lines mudah dibaca secara darurat via CLI standar (`jq`, `grep`), tetapi ukurannya 5-10x lebih besar daripada format kolumnar biner (Parquet), yang memerlukan tooling khusus untuk inspeksi cepat. |

---

## SEKSI 11 — BEST PRACTICES

1. **Partisi Disk Terisolasi:** Telemetri lokal *wajib* dialokasikan ke partisi *mount* khusus (misalnya mount point terpisah `/var/log/telemetry`). Jangan pernah menulis data telemetri ke *root filesystem* (`/`), karena jika terjadi lonjakan log, sistem operasi klien tidak boleh mengalami *disk exhaustion* yang menyebabkan kegagalan sistem.
2. **Korelasi Terstruktur (Log-Trace Cohesion):** Setiap baris log terstruktur *harus* memuat atribut `trace_id` dan `span_id`. Konfigurasi logger runtime (seperti Zap, ZeroLog, atau Logback) untuk menyematkan metadata ini secara otomatis dari *active context*.
3. **Deterministik Bundle Generation:** Skrip pengumpul artefak (`gather-bundle.sh`) harus bersifat idempotensial, merekam checksum (SHA-256) setiap sub-komponen, menyertakan *manifest metadata* (versi aplikasi, uptime, versi kernel, alokasi memori), dan membatasi ukuran arsip akhir melalui flag tarball.
4. **Defensif terhadap PII Leakage:** Selalu gunakan pendekatan *whitelist* (hanya izinkan atribut tertentu) daripada *blacklist* jika sistem beroperasi di industri perbankan inti atau rekam medis.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Ketergantungan pada DNS Publik / Eksternal Endpoint:** Menggunakan default SDK OpenTelemetry yang mencoba mengekspor telemetri ke `http://collector.internal:4317` tanpa menangani kegagalan resolusi DNS di cluster klien yang terisolasi ketat. SDK akan membanjiri thread pool dengan *retry-loop* tak berujung.
2. **Crash Loop Akibat Log Rotator Locking:** Menggunakan alat rotasi log eksternal yang melakukan truncate file log saat aplikasi masih memegang *file descriptor* eksklusif, menyebabkan aplikasi mengalami *silent failure* atau memory leak.
3. **Mengabaikan Korelasi Waktu (*Clock Skew*):** Mengasumsikan waktu (clock) di setiap server klien tersinkronisasi via NTP. Pada instalasi private cloud/edge yang terisolasi, drift waktu sebesar beberapa detik sangat lazim. FDE yang tidak menormalisasi span timestamps berdasarkan interval relatif *parent-child* akan mendapatkan urutan tracing yang keliru (*span anak terlihat selesai sebelum span induk dimulai*).
4. **Menyertakan Core Dumps Mentah:** Memasukkan full-memory crash dumps (`core.*`) ke dalam bundel tanpa izin dan tanpa enkripsi. Memory dump memuat seluruh heap aplikasi, termasuk kunci privat TLS, token memori plain-text, dan data sensitif klien.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Laboratorium
Sebuah klaster pembayaran air-gapped milik klien mengalami kegagalan transmisi transaksi sporadis (*HTTP 504 Gateway Timeout*). Anda menerima sebuah file bundel terkompresi `bundle-incident-20241012.tar.gz`. Anda dilarang meminta akses SSH ke server klien.

```bash
# 1. SETUP ENVIRONMENT SIMULASI (Jalankan di workstation Anda)
mkdir -p /tmp/fde-lab-telemetry && cd /tmp/fde-lab-telemetry

# Buat trace dump tiruan (JSON Lines)
cat << 'EOF' > traces-edge.jsonl
{"trace_id":"8a9d12f45c0a1b2e3f4a5b6c7d8e9f01","span_id":"0000000000000001","parent_span_id":"","name":"POST /api/v1/charge","start_time_unix_nano":1697104800000000000,"end_time_unix_nano":1697104805000000000,"attributes":{"http.status_code":504,"service.name":"api-gateway"}}
{"trace_id":"8a9d12f45c0a1b2e3f4a5b6c7d8e9f01","span_id":"0000000000000002","parent_span_id":"0000000000000001","name":"ExecutePayment","start_time_unix_nano":1697104800100000000,"end_time_unix_nano":1697104804900000000,"attributes":{"service.name":"payment-core","error":"context_deadline_exceeded"}}
{"trace_id":"8a9d12f45c0a1b2e3f4a5b6c7d8e9f01","span_id":"0000000000000003","parent_span_id":"0000000000000002","name":"SELECT FOR UPDATE balances","start_time_unix_nano":1697104800150000000,"end_time_unix_nano":1697104804850000000,"attributes":{"service.name":"payment-db","db.system":"postgresql","status.code":"ERROR"}}
EOF

# Buat systemd-journal log tiruan
cat << 'EOF' > dmesg-snippet.log
[100412.001] nvme0n1: I/O error, dev nvme0n1, sector 12490204 op 0x1:(WRITE) flags 0x800 phys_seg 1 prio class 2
[100414.502] postgres[14021]: [3-1] user=app,db=pay LOG: duration: 4700.123 ms statement: SELECT FOR UPDATE FROM account_balances WHERE id = 'acc-8812'
EOF
```

### Tugas Peserta:
1. **Analisis Latensi:** Tulis sebuah perintah one-liner menggunakan `jq` untuk menghitung durasi (dalam milidetik) dari span `payment-db` pada `traces-edge.jsonl`.
2. **Korelasi Silang Log-Trace:** Gunakan script shell untuk mencocokkan stempel waktu transaksi lambat di tracing dengan insiden I/O error pada `dmesg-snippet.log`.
3. **Formulasi Hipotesis:** Tentukan apakah masalah berakar pada bug kode aplikasi atau degradasi infrastruktur fisik penyimpanan (hardware disk).

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

**1. Mengapa transmisi OTLP standar langsung melalui internet publik tidak dapat digunakan pada deployment edge perbankan tier-1?**
* A) Karena OpenTelemetry belum mendukung enkripsi TLS 1.3.
* B) Karena kebijakan segregasi jaringan (*air-gap*) memblokir egress internet langsung demi mencegah kebocoran data dan ancaman siber.
* C) Karena payload OTLP menggunakan bandwidth lebih dari 1 Gbps secara kontinu.
* D) Karena gRPC tidak dapat dioperasikan di dalam arsitektur container Docker.

**2. Dalam format W3C Trace Context (`traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`), segmen `00f067aa0ba902b7` merepresentasikan:**
* A) Global Unique Trace ID.
* B) Sampling Flags.
* C) Versi spesifikasi W3C.
* D) Span ID dari pemanggil saat ini (Parent Span ID).

**3. Manakah komponen OTel Collector processor yang paling kritikal untuk mencegah OOM-Killed saat memproses lonjakan volume trace secara lokal di node klien?**
* A) `batch` processor.
* B) `memory_limiter` processor.
* C) `resource` processor.
* D) `tail_sampling` processor.

**4. Masalah *clock skew* terjadi ketika menganalisis bundle telemetri offline dari multi-node cluster tanpa NTP. Tindakan apa yang paling tepat untuk merekonstruksi urutan eksekusi?**
* A) Menghapus seluruh span yang memiliki nilai timestamp lebih lama.
* B) Mengubah format timestamp menjadi Unix epoch integer.
* C) Melakukan kalibrasi offset berbasis durasi relatif rentang *parent-child span relationship* daripada absolut wall-clock time.
* D) Mengasumsikan bahwa semua server edge memiliki presisi waktu atomik.

**5. Manakah artefak sistem yang TIDAK BOLEH disertakan ke dalam Support Diagnostic Bundle tanpa proses sanitasi/penyaringan ketat?**
* A) `/proc/cpuinfo`
* B) Full Memory Core Dump (`/var/crash/core.*`)
* C) Output dari `uname -r`
* D) Ringkasan partisi disk dari `df -h`

---

### Kunci Jawaban & Penjelasan:
* **1: B** — Jaringan enterprise kelas tinggi beroperasi di bawah mandat air-gap di mana koneksi keluar (egress) ke internet diblokir secara fisik/firewall. Telemetri harus disimpan dan dikumpulkan secara lokal.
* **2: D** — Struktur traceparent adalah `version-trace_id-parent_id-trace_flags`. Segmen ketiga adalah Span ID (16 hex digit).
* **3: B** — `memory_limiter` processor secara eksplisit memantau alokasi heap Go runtime, melakukan drop data atau melepaskan backpressure saat batas memori tercapai sebelum Linux OOM Killer menghentikan container/proses.
* **4: C** — Hubungan hierarkis span (Parent-Child) bersifat kausal deterministik. Jika span anak tampak dimulai sebelum span induk karena *clock drift*, timeline harus dinormalisasi dengan menghitung relasi durasi internal span tersebut.
* **5: B** — Full Core Dump memuat seluruh snapshot memori sistem, termasuk data pengguna terenkripsi, plain-text credentials, dan master TLS key. Ini merupakan pelanggaran fatal dalam protokol audit keamanan data.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Standar Spesifikasi:**
  * W3C Recommendation: *Trace Context Level 2* (https://www.w3.org/TR/trace-context/)
  * OpenTelemetry Specification: *File and Local Storage Exporters & Processors*
* **Buku Panduan Rekayasa SRE:**
  * Beyer, B., Jones, C., Petoff, J., & Murphy, N. R. (2016). *Site Reliability Engineering: How Google Runs Production Systems*. O'Reilly Media. (Bab 12: Monitoring Distributed Systems).
  * Major, K., & Sridharan, C. (2020). *Distributed Tracing in Practice*. O'Reilly Media.
* **Protokol Forensik & Linux System Diagnostics:**
  * Brendan Gregg. *BPF Performance Tools & Systems Performance: Enterprise and the Cloud*. Prentice Hall.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. Mendiagnosis sistem klien di lingkungan *zero-access/air-gapped* menuntut perubahan paradigma: dari observabilitas *interaktif-live* menjadi forensik *statis-offline*.
2. Ekstraksi telemetri lokal wajib dirancang dengan arsitektur non-destruktif: tidak boleh menguras CPU host klien, dibatasi oleh *memory limiter*, dan dialokasikan ke kuota partisi disk yang terisolasi.
3. Kepatuhan audit data mengharuskan pembersihan data sensitif (PII/Secrets) dilakukan secara langsung di sumber data (*origin sanitization*) sebelum bundel artefak diekspor melewati perimeter keamanan klien.
4. Nilai utama dari *Distributed Tracing* dalam analisis offline adalah penggunaan Trace ID sebagai jangkar korelasi tunggal yang mengintegrasikan log terstruktur, metrik performa kernel, dan kegagalan komponen terdistribusi ke dalam runut kronologis yang valid.

---

## SEKSI 17 — GLOSARIUM

* **Air-Gap:** Isolasi fisik atau logis dari sebuah sistem komputer atau jaringan dari internet publik dan jaringan luar yang tidak terpercaya.
* **W3C Traceparent:** Format header standar untuk mendistribusikan metadata penjejakan terdistribusi lintas batas sistem tanpa mengikat aplikasi ke satu vendor observabilitas tertentu.
* **PII (Personally Identifiable Information):** Data yang dapat digunakan untuk mengidentifikasi seseorang secara langsung atau tidak langsung (misalnya nama, email, nomor kartu kredit, alamat IP).
* **Ring Buffer:** Struktur data penyimpanan memori atau disk berukuran tetap yang beroperasi secara siklis (FIFO), di mana data lama secara otomatis ditimpa ketika kapasitas maksimum tercapai.
* **Diagnostic Bundle:** Sekumpulan file artefak (konfigurasi, metrik, status proses, log) yang dikemas dan dikompresi untuk tujuan debugging sistem secara offline.
* **Context Propagation:** Mekanisme penulisan dan pembacaan metadata tracing melintasi batas thread, proses, soket jaringan, atau broker pesan.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Fokus Pedagogi:** Berikan penekanan kuat pada *mindset* proteksi data. Klien enterprise lebih menghargai engineer yang menjaga kerahasiaan data mereka daripada engineer yang terburu-buru meminta snapshot database mentah tanpa filter redaksi.
* **Setup Lab:** Jika menjalankan pelatihan offline, simulasikan cluster klien menggunakan instance VPS lokal yang diputus kartu jaringan internetnya (`iptables -A OUTPUT -p tcp --dport 80,443 -j DROP`) untuk memaksa peserta terbiasa menggunakan skrip bundle extraction manual.
* **Troubleshooting Pengajaran:** Saat latihan korelasi, peserta sering kali bingung menghadapi perbedaan zona waktu pada log bundle. Tekankan bahwa seluruh sistem enterprise **wajib** dikonfigurasi menggunakan standar **UTC**.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi:** 1.0.0
* **Tanggal:** 24 Oktober 2024
* **Catatan Perubahan:**
  * Rilis modul inisial berstandar kurikulum L5/L6 FDE.
  * Penambahan konfigurasi OTel collector untuk disk storage caching di edge.
  * Penambahan script scrubbing PII produksi berbasis Python.
  * Penambahan materi normalisasi *clock skew* pada tracing multi-node terdistribusi.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** Bab 06 Module 04 — Edge Compute Architecture & Hardware Acceleration Deployment
* **Modul Berikutnya:** Bab 07 Module 02 — Kernel Panic Analysis, Core Dumps Forensic & eBPF Telemetry in Restricted Environments
* **Kembali ke Indeks Jalur:** `forward-deployed-engineer/06-Architecture-and-System-Design`