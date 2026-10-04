# BAB 10: Enterprise Observability, Logpush, SIEM & Capstone
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik pada level Senior DevOps/Platform/Security Engineer diharapkan mampu:
- Merancang dan mengoperasikan pipeline telemetri edge Cloudflare skala enterprise menggunakan Cloudflare Logpush v2 ke berbagai target sink (Amazon S3, Datadog, Splunk, dan Custom HTTP Receiver).
- Mengonfigurasi dan memvalidasi filtering lanjutan berbasis ekspresi filter (*Logpush job filters*), seleksi field teroptimasi (*dynamic field extraction*), serta sampling rate adaptif guna mereduksi *data ingestion cost* hingga 60%.
- Mengimplementasikan mekanisme sanitasi dan de-identifikasi data PII (*Personally Identifiable Information*) langsung pada pipeline observabilitas edge sebelum data masuk ke sistem SIEM/data lake.
- Membangun pipeline observabilitas terdistribusi dengan toleransi kegagalan (*fault-tolerant telemetry buffer*) memanfaatkan intermediate vector layer (Vector.dev / Kafka) untuk ingestion jutaan event per detik (EPS).
- Mengaudit, melacak, dan men-debug latensi pipeline serta integritas log (*log loss detection*) menggunakan checksum metadata dan Cloudflare Audit Logs.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta harus telah menguasai:
- **Cloudflare Fundamentals & Architecture**: Pemahaman mendalam tentang Anycast DNS, Reverse Proxy lifecycle, Workers runtime, dan WAF edge execution order.
- **Enterprise Networking & Protocols**: Pemahaman protokol HTTP/2, HTTP/3, TLS 1.3 handshakes, TCP termination, dan format encoding data (JSON, Apache Parquet, Gzip).
- **Infrastructure as Code (IaC)**: Kemahiran menulis modul Terraform/OpenTofu tingkat lanjut (HCL) untuk provisi cloud resource.
- **Data Engineering / SIEM Ingestion Basics**: Pemahaman arsitektur sink SIEM (Splunk HEC, Datadog Logs API, ElasticSearch/OpenSearch, ClickHouse) dan distributed queuing (Apache Kafka / AWS Kinesis).

---

### 3. Concept & Internal Architecture (Mendalam)

Arsitektur observabilitas edge Cloudflare beroperasi langsung pada layer kernel dan user-space proxy Cloudflare yang tersebar di lebih dari 330 kota di seluruh dunia. Ketika request melewati proxy engine (*FL / Front-Line Proxy* dan *Core Proxy* berbasis NGINX/Rust micro-proxies), setiap state mesin dari koneksi, negosiasi TLS, evaluasi rule WAF, eksekusi Workers, hingga respon origin diekstraksi ke dalam shared memory ring-buffer.

```
+------------------------------------------------------------------------------------+
|                         CLOUDFLARE EDGE DATACENTER (ANYCAST)                       |
|                                                                                    |
|  [ Ingress Request ]                                                               |
|          │                                                                         |
|          ▼                                                                         |
|  [ Rust / FL Edge Proxy ] ─── (WAF / Workers / Bot Engine) ───► [ Origin Server ]  |
|          │                                                              ▲          |
|          │ (Metrics & Traces)                                           │          |
|          ▼                                                              │          |
|  [ Edge Shared Ring-Buffer ] (Per-core Lockless Circular Buffer)        │          |
|          │                                                                         |
|          ▼                                                                         |
|  [ Log Collector Daemon ] ── (Filter Engine: Pre-aggregate, Sample, Filter)        |
+----------┬-------------------------------------------------------------------------+
           │
           │ Micro-batches over TLS (gRPC / mTLS)
           ▼
+------------------------------------------------------------------------------------+
|                        CLOUDFLARE GLOBAL LOGPUSH PIPELINE                          |
|                                                                                    |
|  [ Log Aggregator & Sorter ] ──► [ Parquet / GZIP Serializer ]                     |
|                                            │                                       |
|                                            ▼                                       |
|                       [ Batching Engine (Max 30s / 100k records) ]                 |
+--------------------------------------------┬---------------------------------------+
                                             │
               ┌─────────────────────────────┼─────────────────────────────┐
               ▼                             ▼                             ▼
       Direct Ingestion               Buffered Pipeline             Direct Storage
   +───────────────────────+     +───────────────────────+     +───────────────────────+
   | Datadog / Splunk HEC  |     | Vector / Kafka Buffer |     | AWS S3 / GCS / R2     |
   | (Real-time Analytics) |     | (PII Masking & ETL)   |     | (Cold Storage/Parquet)|
   +-----------------------+     +───────────────────────+     +───────────────────────+
```

#### Komponen Internal Logpush
1. **Edge Shared Ring-Buffer**: Struktur data sirkular *lockless* pada level RAM per CPU-core di setiap edge server. Begitu transaksi HTTP selesai, metadata request disalin ke ring buffer dalam waktu sub-mikrodetik tanpa menginterupsi *hot-path* forwarding lalu lintas aplikasi.
2. **Edge Log Daemon**: Mengambil event dari buffer, mengevaluasi aturan filter Logpush job secara paralel (misal: hanya WAF event atau non-200 status), melakukan *sampling* acak jika dikonfigurasi, dan mengirim payload terkompresi ke pipeline agregasi global.
3. **Global Logpush Aggregator**: Kluster regional yang menerima stream dari ribuan edge node. Komponen ini bertanggung jawab menyatukan micro-batches, mengurutkan log berdasarkan timestamp (*EdgeStartTimestamp*), mengenkapsulasi format file (GZIP-compressed JSON atau Snappy-compressed Apache Parquet), dan membuka koneksi keluar (*egress*) ke destination endpoint yang didefinisikan.
4. **Reliability & Backpressure Subsystem**: Logpush menjamin pengiriman log dengan mekanisme *at-least-once delivery*. Jika target destination merespons dengan status HTTP `429 (Too Many Requests)` atau `5xx`, Logpush mengimplementasikan exponential backoff dengan jitter hingga 24 jam sebelum menyatakan paket gagal.

---

### 4. Why & What

#### Why: Mengapa Tidak Menggunakan Logging Tradisional di Origin?
- **Blind Spot pada Edge Attack**: Permintaan berbahaya seperti serangan DDoS volumetrik, scraping bot agresif, atau request yang di-block oleh Cloudflare WAF/IP Access Rules tidak pernah mencapai origin server. Origin logging tidak memiliki visibilitas terhadap jutaan ancaman yang ditahan di edge.
- **Overhead Origin**: Logging setiap request pada origin backend membebani CPU, I/O disk, dan bandwidth origin.
- **Latency Measurement Accuracy**: Origin logging hanya merekam latensi internal pemrosesan aplikasi, bukan *Round Trip Time* (RTT) klien yang sebenarnya, waktu jabat tangan TLS edge-to-client, atau performa cache hit/miss global.

#### What: Dataset Logpush Cloudflare
Logpush menyediakan dataset granular untuk berbagai layer proteksi dan komputasi:
- `http_requests`: Metadata komprehensif transaksi HTTP edge-to-client dan edge-to-origin.
- `firewall_events`: Rincian aksi WAF, rule ID yang terpicu, skor Machine Learning Bot Management, dan fingerprint request.
- `workers_trace_events`: Log eksekusi JavaScript/Wasm pada Cloudflare Workers, exception uncaught, CPU runtime, dan status subrequest (`fetch`).
- `audit_logs`: Rekam jejak perubahan konfigurasi oleh administrator pada dashboard atau API Cloudflare.
- `nel_reports` & `dns_logs`: Telemetri Network Error Logging dan resolusi DNS query tingkat enterprise.

---

### 5. How (Workflow Detail)

Alur kerja end-to-end produksi untuk pipeline observabilitas enterprise terbagi dalam 5 tahap:

1. **Job Initialization & Validation**:
   - Operator mendefinisikan Logpush Job melalui API/Terraform.
   - Cloudflare mengirimkan *challenge file* unik ke target sink (misal: S3 path atau HTTP endpoint).
   - Operator mengambil token validasi dari destination dan mengirimkannya kembali ke API Cloudflare untuk memverifikasi kepemilikan storage (*destination ownership verification*).
2. **Filtering & Field Pruning**:
   - Payload log dikurangi di level edge menggunakan parameter `filter` (mengeliminasi aset statis non-kritis seperti ekstensi `.jpg`, `.css` jika hanya memonitor API).
   - Hanya field yang dipilih dalam array `output_options.field_names` yang diserialisasi, menghemat ukuran data transfer hingga 70%.
3. **Format Serialization**:
   - Logpush melakukan batching data dalam interval 30 detik atau hingga batas 100.000 record per file tercapai.
   - Serialisasi dilakukan langsung ke format Apache Parquet dengan kompresi Snappy untuk penyimpanan kolumnar di S3/Data Lake, atau JSON terkompresi GZIP untuk ingestion HTTP SIEM.
4. **Transport via Egress Gateways**:
   - Micro-batch dikirim via TLS 1.3 langsung ke endpoint SIEM / Cloud Storage bucket melalui alamat IP Egress resmi Cloudflare Logpush.
5. **Decoupled Ingestion & Masking**:
   - Jika diarahkan ke ingestion aggregator (seperti Vector atau Logstash), data di-parse, field sensitif (seperti Authorization headers atau Cookies) di-masking, lalu diindeks ke SIEM (Datadog/Splunk/ClickHouse).

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengawasan Gerbang Tol Otomatis Global
Bayangkan Cloudflare Edge sebagai ribuan **Pintu Gerbang Tol Internasional**. Setiap mobil (HTTP Request) yang lewat diperiksa oleh sensor kecepatan, kamera pelat nomor, dan detektor muatan (WAF).
- Menggunakan log origin sama seperti *hanya mencatat mobil yang sampai di tempat parkir toko tujuan akhir*: Anda tidak tahu ada 10.000 truk bermuatan ilegal yang sudah diputar balik atau ditilang di gerbang tol terluar.
- **Logpush** adalah sistem kamera canggih di gerbang tol yang secara real-time mengambil foto plat mobil, membuang foto kendaraan internal gerbang yang tidak penting (filtering aset statis), mengepak foto ke dalam amplop terkunci per 30 detik (micro-batching), dan mengirimkannya dengan kurir khusus ke kantor pusat audit kepolisian (SIEM Anda).

#### Diagram Alir Data Logpush Enterprise
```
+------------------+       +------------------+       +------------------+
|  Client Request  |       |  Client Request  |       |  Client Request  |
|  (Clean Traffic) |       |  (WAF Block 403) |       |  (Static Assets) |
+--------┬---------+       +--------┬---------+       +--------┬---------+
         │                          │                          │
         ▼                          ▼                          ▼
+────────────────────────────────────────────────────────────────────────+
|                       CLOUDFLARE EDGE ENGINE                           |
|                                                                        |
|  [ Process Request ]     [ Execute WAF Rule ]       [ Serve from Cache]|
|           │                          │                          │      |
|           ▼                          ▼                          ▼      |
|  Emit Event: Pass        Emit Event: Block          Emit Event: Hit    |
+-----------┬──────────────────────────┬──────────────────────────┬------+
            │                          │                          │
            └──────────────────────────┼──────────────────────────┘
                                       │
                                       ▼
                     +───────────────────────────────────+
                     |      LOGPUSH FILTER ENGINE        |
                     |  Condition:                       |
                     |  ClientRequestPath NOT LIKE *.png |
                     |  AND EdgeResponseStatus >= 400    |
                     +-----------------┬-----------------+
                                       │ (Filtered Stream)
                                       ▼
                     +───────────────────────────────────+
                     |        OUTPUT SERIALIZER          |
                     |  - Format: Apache Parquet         |
                     |  - Prune: 25 selected fields      |
                     +-----------------┬-----------------+
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            ▼                                                     ▼
+───────────────────────+                             +───────────────────────+
|      TARGET A         |                             |       TARGET B        |
|  AWS S3 (Data Lake)   |                             |  Intermediate Proxy   |
|  s3://prod-logs-lake/ |                             |  (Vector Collector)  |
+───────────────────────+                             +───────────┬───────────+
                                                                  │
                                                      (Sanitize & PII Masking)
                                                                  │
                                                                  ▼
                                                      +───────────────────────+
                                                      |     TARGET B-FINAL    |
                                                      |   Splunk / Datadog    |
                                                      +───────────────────────+
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Mengambil Daftar Field Tersedia via cURL
Mengekstrak skema dataset `http_requests` untuk audit kelayakan field:
```bash
curl -s -X GET "https://api.cloudflare.com/client/v4/zones/${CLOUDFLARE_ZONE_ID}/logpush/datasets/http_requests/fields" \
     -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
     -H "Content-Type: application/json" | jq '.result | to_entries[] | {field: .key, description: .value}'
```

#### Practical Example: Arsitektur Produksi Terraform End-to-End
Konfigurasi Logpush tingkat enterprise dengan target AWS S3 dalam format Parquet, dilengkapi Logpush Filter untuk mengisolasi traffic anomali (Error 4xx/5xx dan Action WAF non-allow) serta menyaring field telemetri kritis:

```hcl
# main.tf
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.30.0"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40.0"
    }
  }
}

variable "cloudflare_zone_id" {
  type        = string
  description = "Target Zone ID Cloudflare Enterprise"
}

variable "aws_region" {
  type        = string
  default     = "us-east-1"
}

# 1. Bucket S3 untuk Sink Cold Storage
resource "aws_s3_bucket" "cf_logpush_bucket" {
  bucket        = "enterprise-cf-telemetry-lake-prod"
  force_destroy = false
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cf_logpush_enc" {
  bucket = aws_s3_bucket.cf_logpush_bucket.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# 2. Bucket Policy: Memberikan izin write terbatas ke Cloudflare Logpush Principal
resource "aws_s3_bucket_policy" "cf_logpush_policy" {
  bucket = aws_s3_bucket.cf_logpush_bucket.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowCloudflareLogpushJobAccess"
        Effect    = "Allow"
        Principal = {
          AWS = "arn:aws:iam::395540211218:root" # Official Cloudflare Logpush AWS Account
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.cf_logpush_bucket.arn}/*"
      }
    ]
  })
}

# 3. Ownership Challenge Token Provisi (Automated Validation)
resource "cloudflare_logpush_ownership_challenge" "s3_ownership_challenge" {
  zone_id          = var.cloudflare_zone_id
  destination_conf = "s3://${aws_s3_bucket.cf_logpush_bucket.bucket}/http_requests?region=${var.aws_region}"
}

# 4. Enterprise Logpush Job Definition
resource "cloudflare_logpush_job" "edge_http_error_pipeline" {
  zone_id          = var.cloudflare_zone_id
  name             = "prod-edge-http-anomalies-parquet"
  dataset          = "http_requests"
  enabled          = true
  destination_conf = "s3://${aws_s3_bucket.cf_logpush_bucket.bucket}/http_requests?region=${var.aws_region}"
  ownership_challenge = cloudflare_logpush_ownership_challenge.s3_ownership_challenge.ownership_challenge_filename

  # JSON encoded output options
  output_options {
    field_names = [
      "ClientIP",
      "ClientRequestHost",
      "ClientRequestMethod",
      "ClientRequestURI",
      "EdgeResponseStatus",
      "EdgeStartTimestamp",
      "EdgeEndTimestamp",
      "ClientRequestBytes",
      "EdgeResponseBytes",
      "EdgePathingOp",
      "EdgePathingSrc",
      "EdgePathingStatus",
      "SecurityAction",
      "SecurityRuleID",
      "SecurityRuleDescription",
      "ClientCountry",
      "ClientDeviceType",
      "ClientRequestUserAgent",
      "ClientSSLProtocol",
      "OriginResponseStatus",
      "OriginResponseTime"
    ]
    output_type = "parquet"
    record_delimiter = ""
    timestamp_format = "rfc3339"
  }

  # Structured Filtering Expression: Hanya rekam error status >= 400 ATAU WAF Block
  filter = jsonencode({
    where = {
      and = [
        {
          key      = "EdgeResponseStatus"
          operator = "greater_than_or_equal"
          value    = 400
        },
        {
          key      = "ClientRequestPath"
          operator = "does_not_contain"
          value    = "/healthz"
        }
      ]
    }
  })
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Masalah
Perusahaan FinTech Global tier-1 melayani 4,5 miliar request per hari (puncak: 95.000 RPS). Mereka mengirim seluruh un-sampled edge logs mentah langsung ke Datadog menggunakan Cloudflare Logpush v1 format JSON.
- **Problem 1 (Cost Explosion)**: Biaya ingestion Datadog membengkak hingga $140.000/bulan hanya untuk komponen edge access logs.
- **Problem 2 (Compliance Breach)**: Header otorisasi (`Bearer <token>`) dan query parameter URL terkirim dalam keadaan plaintext tanpa sanitasi, melanggar standar kepatuhan PCI-DSS 4.0 dan GDPR.
- **Problem 3 (Ingestion Saturation)**: Ketika diserang Layer-7 DDoS (250.000 RPS), API Datadog mengalami rate limit (`HTTP 429`), mengakibatkan dropped logs pada audit trail keamanan.

#### Solusi Arsitektural Multi-Tier
Tim Platform/SRE merekayasa ulang alur observabilitas:

```
+-------------------------------------------------------------+
|                     CLOUDFLARE EDGE                         |
|   - Logpush Filter: Drop 2xx statics (*.png, *.js, *.css)   |
|   - Sample 10% of 2xx clean dynamic requests                |
|   - Sample 100% of Security Events & Errors (>=400)         |
+------------------------------┬------------------------------+
                               │ Egress via Logpush (GZIP JSON)
                               ▼
+-------------------------------------------------------------+
|             INTERMEDIATE VECTOR BUFFER CLUSTER              |
|                     (Auto-scaling on EKS)                   |
|                                                             |
|   1. VRL (Vector Remap Language) Processor:                 |
|      - Strip Authorization / Cookie Headers                 |
|      - Hash ClientIP (SHA-256 with dynamic salt)            |
|      - Mask URL query param values (`?token=***`)           |
|   2. Split Stream Logic:                                    |
+--------------┬───────────────────────────────┬--------------+
               │ (100% Security/Errors)        │ (Cold Data / Parquet)
               ▼                               ▼
      +─────────────────+             +─────────────────+
      |  Datadog SIEM   |             |   AWS S3 Lake   |
      | (Alerting & IR) |             |  (Athena/Audit) |
      +─────────────────+             +─────────────────+
```

Konfigurasi Vector Remap Language (VRL) pada intermediate node:
```vrl
# vector-transforms.vrl
. = parse_json!(.message)

# 1. PCI-DSS Compliance: Strip PII dari URL Query
if exists(.ClientRequestURI) {
    .ClientRequestURI = replace(.ClientRequestURI, r'([?&](token|card|cvv|password)=)[^&]+', "${1}REDACTED")
}

# 2. Hash IP jika region tunduk GDPR
if .ClientCountry == "de" || .ClientCountry == "fr" {
    .ClientIP = sha256(.ClientIP + "enterprise_salt_key")
}

# 3. Routing tags
.env = "production"
.pipeline_received_at = now()
```

#### Hasil Metrik
- **Cost Reduction**: Penurunan volume ingestion Datadog sebesar **68%**, menghemat $95.200/bulan.
- **Compliance Audit**: Berhasil lolos audit PCI-DSS 4.0 tanpa temuan PII pada log SIEM.
- **Buffer Reliability**: Buffer Vector menyerap lonjakan 250k RPS selama 45 menit serangan DDoS tanpa kehilangan satu event pun (*zero data loss*).

---

### 9. Trade-offs

| Parameter Desain | Opsi A: Direct to SIEM (Datadog/Splunk) | Opsi B: Direct to S3/GCS Data Lake (Parquet) | Opsi C: Intermediate Buffer (Vector/Kafka) |
| :--- | :--- | :--- | :--- |
| **Ingestion Latency** | Rendah (30 - 60 detik) | Menengah (1 - 3 menit) | Menengah (45 - 90 detik) |
| **Biaya Ingestion** | Sangat Tinggi ($0.10 - $0.25 per GB) | Sangat Rendah ($0.02 per GB S3 storage) | Rendah ke Menengah (Compute overhead) |
| **Sanitasi PII** | Terbatas (Tergantung rule vendor SIEM) | Nihil (Tersimpan mentah sesuai kiriman edge)| Penuh & Kustom (via transformasi kustom) |
| **Kompleksitas Ops** | Sangat Rendah (Serverless SaaS) | Rendah (Managed Cloud Storage) | Tinggi (Perlu me-manage cluster Vector/Kafka) |
| **Search & Query** | Real-time Indexing, Lucene, Dashboards | Query via Presto/Athena/ClickHouse (Ad-hoc) | Sesuai consumer akhir |
| **Resistensi Lonjakan** | Rentan terkena rate-limiting (HTTP 429) | Sangat Kuat (S3 menangani jutaan PUT/s) | Ekstrem (Buffer di level queue) |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Fatal Destinasi S3: "Ownership Verification Failed"
- **Penyebab**: Logpush mewajibkan bucket policy mengizinkan Cloudflare Logpush System AWS Account (`arn:aws:iam::395540211218:root`). Jika policy mengaktifkan enforced SSE-KMS tanpa memberi delegasi decrypt/generate-data-key pada ARN tersebut, proses verifikasi validasi kepemilikan bucket akan gagal seketika.
- **Solusi**: Pastikan KMS Key policy menyertakan Cloudflare Account ARN atau gunakan Amazon S3 Managed Keys (`AES256`).

#### 2. Log Data Loss Akibat Misconfigured Sampling
- **Penyebab**: Operator mengatur `sample_rate = 0.01` (1%) secara global pada dataset `http_requests` untuk menghemat biaya, tanpa memisahkan event keamanan. Dampaknya, 99% serangan WAF, SQLi, dan brute force terbuang dan tidak pernah tercatat di SIEM.
- **Solusi**: Jangan pernah melakukan *global blind sampling*. Buat dua Logpush Job terpisah: Job 1 khusus Keamanan (`SecurityAction != "none"`, sampling 100%), Job 2 khusus Laporan Umum (sampling 10%).

#### 3. Log Parser Failure pada SIEM Akibat Custom Delimiter
- **Penyebab**: Menggunakan delimiter default newline pada pipeline yang mengekspos payload JSON bersarang (*nested arrays*) tanpa sanitasi escape string, merusak struktur JSON di collector parser.
- **Solusi**: Gunakan output terenkapsulasi standar industri: Parquet untuk analytical queries atau format JSON satu baris (*NDJSON*) dengan `record_delimiter = "\n"`.

#### Debugging Command Matrix
Jika log berhenti mengalir, jalankan serangkaian audit berikut:

```bash
# 1. Periksa status operasional Logpush Job
curl -s -X GET "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/logpush/jobs/${JOB_ID}" \
     -H "Authorization: Bearer ${API_TOKEN}" | jq '.result | {id: .id, enabled: .enabled, last_complete: .last_complete, error: .error_message}'

# 2. Validasi uji coba pengiriman paksa (Instant Validation)
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/logpush/validate/destination" \
     -H "Authorization: Bearer ${API_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{"destination_conf": "s3://my-bucket/logs?region=us-east-1"}' | jq .
```

---

### 11. Best Practices (Production Checklist)

#### Architecture & Configuration
- [ ] **Dual-Job Strategy**: Pisahkan security audit logs (dataset `firewall_events` / WAF events) dengan sample rate 100% dari HTTP traffic logs umum.
- [ ] **Field Optimization**: Buang field non-esensial. Sertakan selalu `RayID`, `EdgeStartTimestamp`, `ClientIP`, `EdgeResponseStatus`, `ClientRequestURI`, dan `OriginResponseTime`.
- [ ] **Format Parquet untuk Long-Term Storage**: Selalu gunakan Apache Parquet jika target adalah S3, Google Cloud Storage, atau Cloudflare R2 untuk menekan ukuran data hingga 80% dibanding raw JSON.
- [ ] **Data Partitioning**: Pastikan destination URL menyertakan dynamic pathing jika didukung (misal: S3 prefix per tahun/bulan/hari/jam) untuk mempercepat segmentasi query Athena/Snowflake.

#### Security & Compliance
- [ ] **PII Scrubbing**: Jangan kirim header sensitif (`Cookie`, `Authorization`, `Proxy-Authorization`) ke platform pihak ketiga tanpa proses masking di intermediate proxy.
- [ ] **Least Privilege S3 Bucket**: Kunci bucket S3 hanya untuk ARN Cloudflare Logpush dan batasi akses pembacaan hanya untuk IAM Role worker parser analitik.
- [ ] **Audit Trail Monitoring**: Pasang notifikasi jika Logpush Job di-nonaktifkan (`enabled = false`) menggunakan dataset `audit_logs`.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum ini di direktori kerja: `hands-on/m02/`

#### Langkah 1: Setup Lingkungan & File Konfigurasi Mock Destination
Kita akan membuat mock receiver HTTP SIEM lokal berbasis Docker untuk memverifikasi streaming payload Logpush dan struktur JSON-nya.

Buat file `hands-on/m02/docker-compose.yml`:
```yaml
version: '3.8'
services:
  log-sink:
    image: python:3.11-slim
    container_name: enterprise-log-sink
    working_dir: /app
    volumes:
      - ./server.py:/app/server.py
      - ./received_logs:/app/received_logs
    command: python /app/server.py
    ports:
      - "8080:8080"
```

Buat file `hands-on/m02/server.py` (Mock High-Throughput Ingestion Server):
```python
import gzip
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import time

LOG_DIR = "/app/received_logs"
os.makedirs(LOG_DIR, exist_ok=True)

class LogSinkHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_encoding = self.headers.get('Content-Encoding')
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        if content_encoding == 'gzip':
            payload = gzip.decompress(post_data).decode('utf-8')
        else:
            payload = post_data.decode('utf-8')

        filename = f"{LOG_DIR}/logbatch_{int(time.time() * 1000)}.json"
        with open(filename, "w") as f:
            f.write(payload)

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response = json.dumps({"status": "received", "bytes": len(payload)})
        self.wfile.write(response.encode('utf-8'))

    def do_GET(self):
        # Digunakan untuk ownership challenge mock
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

if __name__ == "__main__":
    server = HTTPServer(('0.0.0.0', 8080), LogSinkHandler)
    print("Log Sink listening on port 8080...")
    server.serve_forever()
```

Jalankan mock receiver:
```bash
cd hands-on/m02/
docker compose up -d
```

#### Langkah 2: Simulasi Logpush Filtering Payload Script
Buat script simulasi filter untuk memvalidasi performa filtering ekspresi edge sebelum diterapkan ke Cloudflare.

Buat file `hands-on/m02/filter_engine.py`:
```python
import json
import sys

raw_events = [
    {"RayID": "87e1a01", "EdgeResponseStatus": 200, "ClientRequestURI": "/static/app.js", "SecurityAction": "none"},
    {"RayID": "87e1a02", "EdgeResponseStatus": 403, "ClientRequestURI": "/api/v1/transfer", "SecurityAction": "block"},
    {"RayID": "87e1a03", "EdgeResponseStatus": 502, "ClientRequestURI": "/api/v1/checkout", "SecurityAction": "none"},
    {"RayID": "87e1a04", "EdgeResponseStatus": 200, "ClientRequestURI": "/api/v1/user", "SecurityAction": "none"},
    {"RayID": "87e1a05", "EdgeResponseStatus": 401, "ClientRequestURI": "/admin/login", "SecurityAction": "challenge"}
]

def evaluate_filter(record):
    # Rule: EdgeResponseStatus >= 400 OR SecurityAction != 'none'
    is_error = record.get("EdgeResponseStatus", 0) >= 400
    is_threat = record.get("SecurityAction", "none") != "none"
    return is_error or is_threat

filtered_stream = [rec for rec in raw_events if evaluate_filter(rec)]

print(f"Total Events Ingested: {len(raw_events)}")
print(f"Events Emitted to SIEM: {len(filtered_stream)}")
print("Emitted Payload Sample:")
print(json.dumps(filtered_stream, indent=2))
```

Eksekusi:
```bash
python3 filter_engine.py
```

#### Langkah 3: Pipeline Sanitasi VRL (Vector Emulation)
Jalankan verifikasi transformasi string untuk memastikan tidak ada credential yang lolos ke downstream logging.

Buat file `hands-on/m02/test_sanitization.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail

SAMPLE_LOG='{"RayID":"1a2b3c","ClientRequestURI":"/api/login?user=admin&token=ey000xyz123&pin=9988","ClientIP":"198.51.100.42"}'

echo "Original Log:"
echo "$SAMPLE_LOG"

echo "Sanitized Log:"
echo "$SAMPLE_LOG" | jq '
  .ClientRequestURI |= (gsub("([?&](token|pin)=)[^&]+"; "\(. )" | gsub("=[^&]+"; "=REDACTED"))) |
  .ClientIP = "HASHED_" + (.ClientIP | @base64)
'
```

Jalankan test:
```bash
chmod +x test_sanitization.sh
./test_sanitization.sh
```

---

### 13. Exercise

#### Exercise 1 (Easy)
- **Tugas**: Tulis query `cURL` untuk menarik 5 job Logpush terakhir yang aktif pada akun enterprise Anda, lalu saring respons menggunakan `jq` agar hanya menampilkan field: `id`, `dataset`, `enabled`, dan `destination_conf`.
- **Expected Output**: Array JSON bersih yang berisi metadata esensial dari job yang sedang berjalan.

#### Exercise 2 (Medium)
- **Tugas**: Buat file konfigurasi Terraform (`logpush_firewall.tf`) yang mengonfigurasi job Logpush khusus dataset `firewall_events`.
  - Target: Datadog Logs API (`https://http-intake.logs.datadoghq.com/api/v2/logs`).
  - Filter: Hanya kirim event yang dieksekusi dengan aksi `drop`, `block`, atau `challenge`.
  - Output: JSON format terkompresi GZIP dengan timestamp format unix nano.

#### Exercise 3 (Hard)
- **Tugas**: Rancang pipeline multi-cloud ingestion. Tulis modul OpenTofu/Terraform yang mendistribusikan telemetri Cloudflare ke dua tujuan paralel:
  1. Dataset `http_requests` dengan status `>= 500` dikirim ke PagerDuty via Webhook / Generic HTTP Sink untuk alerting instan.
  2. Seluruh log lalu lintas (termasuk status 200, sampling rate 5%) dikirim ke Cloudflare R2 bucket dalam format Apache Parquet untuk analytical reporting.
  - Sediakan handling untuk `ownership_challenge` pada kedua target tersebut tanpa menggunakan plain static token di source code.

---

### 14. Challenge

**Skenario**:
Sebuah platform E-Commerce multinasional mengalami anomali kebocoran kredensial di dark web. Tim forensic mencurigai adanya eksfiltrasi data via header HTTP atau parameter URL dari route `/api/v3/cart/checkout`. Di saat yang bersamaan, tim Finance menuntut penurunan biaya Cloudflare Logpush dan Datadog sebesar 50% dalam 7 hari ke depan. 

Karakteristik traffic:
- Rata-rata traffic normal: 80.000 RPS (85% adalah GET ke CDN image/assets statis).
- Endpoint checkout menerima 2.500 RPS dengan response status 200, 400, dan 500.
- Regulasi: Log yang memuat data pelanggan Eropa harus disensor (IP Anonymization) sebelum melewati border US.

**Tugas Arsitektur**:
Rancang dan dokumentasikan spesifikasi desain arsitektur produksi lengkap (diagram detail, konfigurasi Terraform Logpush filter rules, dan arsitektur processing layer intermediate) yang memenuhi 3 kriteria:
1. Menghilangkan 100% beban log aset statis dari pipeline Logpush.
2. Mengamankan dan mengaudit jalur `/api/v3/cart/*` secara utuh tanpa melanggar GDPR (PII Scrubbing).
3. Memastikan pemotongan cost ingestion SIEM tercapai minimal 50% tanpa menghilangkan akurasi deteksi ancaman WAF di seluruh dunia.

*(Kerjakan rancangan sistem ini dalam dokumen arsitektur tanpa menggunakan solusi instan).*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Apa perbedaan mendasar antara Cloudflare Logpull dan Cloudflare Logpush?**
   - A. Logpull mengirim log secara proaktif via push webhook, sedangkan Logpush menunggu request GET.
   - B. Logpull mewajibkan client melakukan pooling API Cloudflare berulang kali, sedangkan Logpush mendorong log secara micro-batch otomatis mendekati real-time ke remote destination.
   - C. Logpush hanya dapat digunakan untuk data DNS, sedangkan Logpull untuk HTTP traffic.
   - D. Logpull tidak membebani kuota API Cloudflare, sedangkan Logpush membebani.

2. **Format serialisasi log default mana yang memberikan efisiensi penyimpanan dan kecepatan scan analytical query tertinggi untuk AWS Athena / BigQuery?**
   - A. Plain Text NDJSON
   - B. XML terkompresi BZIP2
   - C. Apache Parquet terkompresi Snappy
   - D. CSV terkompresi GZIP

3. **Berapa interval waktu maksimum atau ambang batas record yang memicu pengiriman micro-batch pada pipeline Logpush global?**
   - A. 5 menit atau 1.000.000 record
   - B. 30 detik atau 100.000 record
   - C. 1 detik atau 10 record
   - D. 10 menit atau 500.00 record

4. **Tujuan utama dari `ownership_challenge` saat mengonfigurasi Cloudflare Logpush job adalah...**
   - A. Memvalidasi bahwa API Token Cloudflare memiliki hak super administrator.
   - B. Mengenkripsi lalu lintas data antara edge proxy dan core proxy.
   - C. Membuktikan bahwa pembuat job memiliki kendali dan otorisasi sah atas bucket/endpoint target penyimpanan.
   - D. Menghitung estimasi biaya egress cloud provider secara otomatis.

5. **Dataset Logpush manakah yang secara spesifik menyimpan histori eksekusi kode JavaScript pada platform Edge Computing Cloudflare?**
   - A. `http_requests`
   - B. `nel_reports`
   - C. `firewall_events`
   - D. `workers_trace_events`

#### Bagian 2: Intermediate (5 Pertanyaan)
6. **Jika Anda mengonfigurasi parameter filter berikut pada Logpush Job:**
   `{"where":{"and":[{"key":"EdgeResponseStatus","operator":"greater_than","value":499},{"key":"ClientCountry","operator":"equals","value":"id"}]}}`
   **Log mana yang akan diteruskan ke SIEM?**
   - A. Semua error 5xx dari seluruh negara ditambah semua request dari Indonesia.
   - B. Hanya HTTP request yang menghasilkan status 500 ke atas DAN berasal dari klien dengan IP geolocation Indonesia.
   - C. Request yang gagal di-cache pada datacenter Jakarta (CGK).
   - D. Request yang menghasilkan status 499 khusus dari Indonesia.

7. **Mengapa menyimpan kunci dekripsi enkripsi AWS KMS (Customer Managed Key) pada bucket target Logpush tanpa trust policy akun AWS Cloudflare menyebabkan error pipeline?**
   - A. Karena Cloudflare Logpush tidak mendukung transfer data terenkripsi.
   - B. Logpush mengirim data langsung dari AWS account Cloudflare (`arn:aws:iam::395540211218:root`), sehingga KMS menolak izin `kms:GenerateDataKey` jika principal tersebut tidak terdaftar di Key Policy.
   - C. Logpush hanya menerima enkripsi hardware HSM on-premise.
   - D. Bucket policy S3 secara otomatis mematikan Logpush jika KMS diaktifkan.

8. **Bagaimana cara paling efektif mengurangi volume ingestion SIEM tanpa kehilangan visibilitas serangan keamanan?**
   - A. Mengaktifkan global sampling rate 50% di dashboard Cloudflare.
   - B. Mematikan logging untuk semua response selain 200 OK.
   - C. Memisahkan job: Logging 100% pada dataset `firewall_events` dan sampling agresif atau selektif filter status code `>= 400` pada dataset `http_requests`.
   - D. Mematikan Logpush dan beralih ke local logging di origin backend.

9. **Jika target SIEM Anda mengalami downtime atau rate limit HTTP 429 selama lonjakan traffic, bagaimana mekanisme penanganan retensi data pada Cloudflare Logpush?**
   - A. Logpush langsung menghapus record yang gagal terkirim demi menjaga memory edge.
   - B. Logpush menyimpan log di edge server selama 30 hari.
   - C. Logpush melakukan *retry* dengan exponential backoff dan jitter hingga rentang waktu 24 jam sebelum log dinyatakan hilang (*dropped*).
   - D. Logpush mengalihkan traffic klien ke mode maintenance page secara otomatis.

10. **Field `OriginResponseTime` pada dataset `http_requests` mengukur parameter apa secara akurat?**
    - A. Waktu DNS lookup domain origin oleh client browser.
    - B. Waktu total sejak Cloudflare edge mengirim request ke origin server hingga edge menerima byte respons terakhir dari origin.
    - C. Waktu durasi client mengunduh file statis dari cache Cloudflare.
    - D. Total durasi eksekusi database internal di origin server.

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)
11. **Skenario 1**:
    Sebuah aplikasi FinTech baru saja meluncurkan job Logpush ke S3. Namun, setelah 2 jam berjalan, folder target di S3 tetap kosong dan field `last_complete` pada API bernilai `null`. Saat dicek, status job adalah `enabled: true`. 
    Langkah investigasi urutan pertama manakah yang paling tepat untuk mendiagnosis akar masalah?
    - A. Langsung menghapus job dan membuat ulang via Web Console UI.
    - B. Memeriksa API Cloudflare endpoint `GET /zones/{zone_id}/logpush/jobs/{job_id}` untuk melihat isi pesan `error_message`, dan memvalidasi apakah bucket policy S3 memblokir write action dari Cloudflare IAM principal.
    - C. Mengubah format output dari Parquet ke JSON.
    - D. Menghubungi tim AWS Support untuk membuka port 443 di bucket S3.

12. **Skenario 2**:
    Tim Keamanan Siber mendeteksi adanya request injection bypass WAF yang lolos ke origin. Mereka membutuhkan bukti forensics: `ClientIP`, `ClientRequestHeaders`, dan payload WAF rule yang dievaluasi. Namun, pada dashboard SIEM, field header request kosong.
    Apa penyebab arsitektural dari ketiadaan data header tersebut?
    - A. Cloudflare WAF tidak dapat membaca request header.
    - B. Pipeline Logpush secara default tidak memuat semua header dinamis; header kustom atau raw headers harus didefinisikan secara eksplisit atau di-log melalui Cloudflare Workers `trace_events` atau custom field extraction.
    - C. SIEM secara otomatis memblokir semua request header karena proteksi firewall lokal.
    - D. Format Apache Parquet tidak dapat menampung data tipe teks header.

13. **Skenario 3**:
    Perusahaan Anda mengalami serangan Layer-7 credential stuffing masif terhadap endpoint `/auth/v1/token`. Volume log melonjak dari 5 GB/jam menjadi 120 GB/jam. Sistem Datadog SIEM Anda hampir melebihi kuota bulanan. Anda diminta menahan log serangan tersebut untuk analisa tim SOC tanpa menaikkan biaya Datadog.
    Keputusan arsitektur tercepat dan paling efisien yang harus diambil adalah:
    - A. Mematikan seluruh WAF rules agar tidak ada event yang tercatat.
    - B. Mengupdate konfigurasi Terraform Logpush: alihkan destination `firewall_events` sementara ke Amazon S3 Data Lake (Parquet) atau Cloudflare R2, dan batasi ingestion ke Datadog hanya untuk data metrik agregat.
    - C. Mematikan endpoint `/auth/v1/token` dari DNS.
    - D. Menghapus dataset `http_requests` dan beralih menggunakan software agent di server origin.

---

### Kunci Jawaban Evaluasi

#### Bagian 1: Basic
1. **B** — Logpull mewajibkan client melakukan pulling (polling) manual via REST API, sedangkan Logpush mendorong log otomatis secara micro-batch near real-time ke target.
2. **C** — Apache Parquet dengan kompresi Snappy dirancang khusus untuk analytical query berbasis kolom, menghemat biaya komputasi scan dan storage secara signifikan.
3. **B** — Logpush mem-batch data dengan interval maksimal 30 detik atau setiap kali volume mencapai 100.000 record per batch.
4. **C** — Ownership challenge membuktikan bahwa pemohon konfigurasi benar-benar memiliki otoritas write access terhadap bucket atau endpoint receiver tersebut.
5. **D** — `workers_trace_events` adalah dataset telemetri runtime untuk mengevaluasi eksekusi Cloudflare Workers.

#### Bagian 2: Intermediate
6. **B** — Operator logika `and` mengevaluasi kedua kondisi secara bersamaan: respons error `>= 500` DAN request berasal dari negara Indonesia (`id`).
7. **B** — AWS KMS memvalidasi otorisasi caller. Jika principal AWS account Logpush Cloudflare tidak diizinkan menggunakan key tersebut untuk enkripsi payload S3, request upload akan ditolak (*Access Denied*).
8. **C** — Memisahkan concern telemetri: mengalirkan seluruh event keamanan (100%) untuk audit, namun melakukan filtering dan sampling selektif pada request HTTP normal.
9. **C** — Cloudflare Logpush mengimplementasikan exponential backoff retry hingga jendela waktu 24 jam saat destination mengalami error HTTP 429/5xx.
10. **B** — Mengukur durasi koneksi edge-to-origin: sejak paket request dikirim dari proxy Cloudflare sampai seluruh respons origin diterima proxy Cloudflare.

#### Bagian 3: Skenario Kasus Produksi
11. **B** — Langkah diagnostik primer SRE adalah memeriksa status objek job via API untuk membaca error sistematis (`error_message`) serta memvalidasi bucket policy permission.
12. **B** — Atribut header dinamis tidak dipetakan otomatis ke dalam root fields dataset `http_requests` standar untuk mencegah ledakan skema dan kebocoran credential sensitif; perlu konfigurasi eksplisit.
13. **B** — Mengalihkan destination Logpush ke storage dingin berbasis objek (S3/R2) menampung lonjakan volume data forensik secara murah tanpa terkena biaya ingestion SIEM premium.

---

### 16. Summary

Implementasi Cloudflare Logpush v2 pada skala enterprise menjembatani jarak visibilitas antara edge network terdistribusi dan centralized observability platform (SIEM/Data Lake). Dengan memanfaatkan kapabilitas filtering native pada edge engine, arsitek sistem dapat memisahkan antara *high-value security events* dan *routine telemetry noise*, menghasilkan reduksi biaya ingestion hingga lebih dari 60%.

Keberhasilan pipeline observabilitas edge bertumpu pada tiga pilar utama:
1. **Kepatuhan Data & Sanitasi**: Menjamin pembersihan PII sebelum data keluar dari batas perimeter keamanan organisasi.
2. **Resiliensi Ingestion**: Menggunakan pola arsitektur buffered (Vector/Kafka) atau storage bertingkat (S3 Parquet untuk cold storage, SIEM untuk alerting real-time).
3. **Automasi Deklaratif**: Seluruh konfigurasi job, filtering rules, dan policy kepemilikan bucket dikelola mutlak melalui Infrastructure as Code (Terraform) untuk mencegah deviasi konfigurasi antar-environment.