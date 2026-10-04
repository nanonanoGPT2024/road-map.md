# Module 01: Enterprise Observability, Logpush Pipeline, SIEM, & Capstone Deployment

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
* Merancang, mengonfigurasi, dan mengoperasikan pipeline telemetri Cloudflare Logpush enterprise-grade untuk dataset HTTP Requests, Firewall Events, dan DNS Logs secara real-time.
* Mengintegrasikan Cloudflare Logpush ke berbagai SIEM dan analytical sink (Datadog, AWS S3, Splunk) menggunakan ownership validation, field filtering, dan log sampling.
* Membangun instrumen edge observability berlatensi rendah dan berkardinalitas tinggi menggunakan Cloudflare Workers Analytics Engine via SQL queries.
* Mengotomatisasi audit compliance logging menggunakan Cloudflare Audit Logs API untuk mendeteksi perubahan konfigurasi infrastruktur edge secara definitif.
* Menggelar arsitektur edge capstone terpadu yang memadukan Cloudflare WAF, Zero Trust, Workers, Logpush pipeline, dan SIEM alerting via Terraform.

---

## 2. Prerequisite
Untuk memahami materi ini secara mendalam, peserta didik wajib menguasai:
* Pemahaman mendalam tentang protokol HTTP/2, HTTP/3, TLS 1.3, dan arsitektur DNS recursive/authoritative.
* Pengalaman praktis menggunakan Terraform / OpenTofu (Resource Management, Data Sources, Provider Configuration).
* Konsep format log modern: NDJSON (Newline Delimited JSON) dan kompresi GZIP.
* Familiaritas dengan konsep SIEM (Security Information and Event Management) dan storage data lake (Amazon S3, SQS, Object Lifecycle).
* Pemahaman dasar tentang SQL (SELECT, GROUP BY, aggregations, time-windowing).

---

## 3. Concept
Observabilitas Enterprise pada perimeter edge Cloudflare mengalihkan paradigma monitoring dari *polling-based metrics* tradisional ke *push-based streaming telemetry*. Karena Cloudflare memproses request di ratusan edge data center global, sentralisasi log memerlukan mekanisme streaming andal dengan latensi di bawah 60 detik.

Cloudflare Logpush merupakan fondasi pipeline ini. Fitur ini mendorong log yang diproses di edge langsung ke storage bucket (AWS S3, Google Cloud Storage, Azure Blob) atau endpoint analitik HTTP/SIEM (Datadog, Splunk HTTP Event Collector, Sumo Logic) dalam format NDJSON terkompresi GZIP. Bersamaan dengan itu, Cloudflare Workers Analytics Engine menyediakan penulisan telemetri edge *unlimited cardinality* berkecepatan tinggi tanpa membebani runtime Workers, yang dapat di-query menggunakan sintaks SQL standar.

---

## 4. Why
Mengapa arsitektur logging native dan dashboard bawaan tidak cukup untuk skala enterprise?
1. **Compliance & Forensik Digital:** Regulasi seperti PCI-DSS, SOC 2 Tipe II, dan ISO 27001 mewajibkan retensi log mentah (raw immutable logs) minimal 365 hari. Dashboard Cloudflare hanya menyimpan data agregat selama 3 hingga 30 hari tergantung paket langganan.
2. **Korelasi Ancaman Lintas-Platform:** Edge log harus dikorelasikan secara real-time dengan log application layer, auth provider, dan database di SIEM untuk mendeteksi serangan multi-vektor (misalnya, brute-force edge yang berlanjut ke lateral movement internal).
3. **Cardianlity Explosion:** Memantau jutaan User-Agent unik, IP address, trace ID, dan URL path dinamis membuat time-series database tradisional (seperti Prometheus) mengalami *OOM (Out Of Memory)*. Workers Analytics Engine dirancang khusus untuk menangani high-cardinality edge metrics tanpa batasan metrik konvensional.
4. **Zero-Loss Auditability:** Setiap modifikasi firewall rule, DNS record, atau worker script oleh engineer harus diaudit secara eksternal guna mencegah ancaman *insider threat* atau *compromised credentials*.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Cloudflare Logpush Architecture & Mechanics
Logpush berjalan langsung di layer edge data pipeline Cloudflare. Log dikumpulkan per batch (berdasarkan interval waktu biasanya 30-60 detik atau batas ukuran file ~100MB uncompressed) dan dipush via HTTPS PUT/POST ke target destinasi.

```
       [ Client Request ]
               │
               ▼
   [ Cloudflare Edge Server ] ──── (Process & Serve)
               │
      (Asynchronous Copy)
               │
               ▼
      [ Logpush Engine ]
               │
      ├── Filter Applied (e.g. ClientRequestPath contains /api)
      ├── Sampling Applied (e.g. sample=0.1)
      ├── Field Selection (Drop PII fields)
      └── GZIP Compression (NDJSON output)
               │
               ├───────────────────┬───────────────────┐
               ▼                   ▼                   ▼
       [ Amazon S3 Sink ]   [ Datadog Intake ]   [ Splunk HEC ]
         (Long-term Data)     (Alerting/Ops)      (SecOps/SIEM)
```

#### Supported Datasets
* **HTTP Requests (`http_requests`):** Rincian setiap edge request (RayID, Status, ResponseTime, BotScore, EdgeColoCode, CacheStatus, ClientSSLProtocol).
* **Firewall Events (`firewall_events`):** Aksi WAF, Rate Limiting, IP Access Rules, Bot Management (Action, RuleID, Source, MatchDetails).
* **DNS Logs (`dns_logs`):** DNS queries ke domain authoritative (QueryName, QueryType, ResponseCode, ColocationCode).
* **Spectrum Events (`spectrum_events`):** Log transmisi TCP/UDP level 4.
* **Audit Logs (`audit_logs`):** Jejak audit perubahan akun oleh administrator.

#### Push Mechanism & Ownership Validation
Sebelum Logpush mentransfer log ke destinasi S3 atau generic HTTP endpoint, Cloudflare menjalankan prosedur **Ownership Validation**:
1. Cloudflare mengirimkan file verifikasi sementara yang berisi token acak ke bucket target:
   `s3://my-cloud-log-bucket/ownership-challenge-XXXXXXXX.txt`
2. Operator harus membaca token tersebut dan mengirimkannya kembali ke Cloudflare via API/Terraform untuk memverifikasi hak kepemilikan sink.

### 5.2 Logpush Job Tuning: Filtering, Selection, & Sampling
Menyalurkan seluruh traffic edge ke SIEM komersial (seperti Datadog atau Splunk) tanpa filter akan memicu ledakan biaya ingest (*ingestion cost shock*).
* **Field Selection:** Memilih hanya atribut yang relevan (misalnya dropping `RequestHeaders` dan `ResponseHeaders` jika tidak dibutuhkan untuk analisis forensik).
* **Filtering (`filter` parameter):** Menggunakan format JSON terstruktur untuk mengecualikan asset statis:
  ```json
  {
    "where": {
      "and": [
        {"key": "ClientRequestPath", "operator": "!startsWith", "value": "/static/"},
        {"key": "EdgeResponseStatus", "operator": ">=", "value": 400}
      ]
    }
  }
  ```
* **Sampling Rate:** Mengirim persentase acak dari log (misalnya `sample=0.01` untuk 1% sampel dari traffic 200 OK untuk monitoring latency makro).

### 5.3 Workers Analytics Engine
Workers Analytics Engine menyediakan pipeline penulisan analitik berkapasitas sangat tinggi langsung dari V8 runtime Cloudflare Workers.
* **Write Mechanism:** Menggunakan pemanggilan API non-blocking `env.ANALYTICS_BINDING.writeDataPoint()`.
* **Data Model:**
  * `blobs`: Array string (maksimal 20 field) untuk dimensi kategoris/kardinalitas tinggi (UserID, RayID, APIPath, Region).
  * `doubles`: Array angka float/int (maksimal 20 field) untuk metrik kuantitatif (ExecutionTime, DBQueryLatency, PayloadSize).
  * `indexes`: Array string (maksimal 1 field) untuk primary fast indexing/partitioning key.
* **Query Mechanism:** Di-query melalui Cloudflare REST API menggunakan dialect SQL standar (`SELECT blob1, AVG(double1) FROM table GROUP BY blob1`).

---

## 6. How
Implementasi enterprise observability dilakukan melalui langkah-langkah berikut:
1. **Penyediaan Sink Storage:** Membuat bucket S3 dengan enkripsi AWS KMS dan policy yang mengizinkan Cloudflare Logpush service account melakukan `s3:PutObject`.
2. **Penyediaan SIEM Intake:** Mengonfigurasi Datadog API Key atau Splunk HEC (HTTP Event Collector) token.
3. **Eksekusi Ownership Challenge:** Menyelesaikan challenge handshake kepemilikan bucket/endpoint.
4. **Deployment Logpush via Terraform:** Mendefinisikan konfigurasi infrastruktur as code (IaC) yang memfilter, mengambil field penting, dan melakukan sampling log.
5. **Edge Worker Telemetry Instrumentation:** Menyuntikkan script Workers Analytics Engine untuk melacak SLA internal microsecond latency.
6. **Validasi SIEM Alerting:** Memverifikasi kueri SIEM mendeteksi event WAF Block dan anomali HTTP 5xx.

---

## 7. Analogy
Bayangkan bandara internasional yang sangat sibuk:
* **Cloudflare Edge** adalah gate dan terminal pemeriksaan di mana jutaan penumpang lalu lalang setiap menit.
* **Dashboard Cloudflare Bawaan** adalah papan pengumuman kedatangan/keberangkatan: hanya menampilkan statistik ringkas (berapa pesawat mendarat, delay berapa menit), tetapi tidak mencatat nama penumpang perorangan secara permanen.
* **Logpush Pipeline** adalah sistem kamera CCTV beresolusi tinggi dan pencatat manifes digital otomatis. Setiap kali seorang penumpang (request) melewati gate, fotokopi paspor dan rekaman visual langsung dibungkus, disegel dalam kontainer anti-rusak (GZIP), dan dikirimkan via sabuk berjalan berkecepatan tinggi ke ruang brankas federal (AWS S3) dan ruang kendali keamanan bandara (SIEM Splunk/Datadog) dalam hitungan detik.
* **Workers Analytics Engine** adalah sensor laser real-time di sepatu penumpang yang mengukur kecepatan langkah kaki mereka di lorong transfer tanpa membuat penumpang berhenti berjalan, mencatat telemetri performa mikro secara instan.

---

## 8. Diagram (ASCII)

```
===================================================================================================
                             ENTERPRISE EDGE OBSERVABILITY TOPOLOGY
===================================================================================================

 [ Internet Users / Attackers ]
              │
              ▼
   ┌─────────────────────────────────────────────────────────────────────────────┐
   │                       CLOUDFLARE GLOBAL EDGE NETWORK                        │
   │                                                                             │
   │  [ Layer 3/4 DDoS Mitigation ]                                             │
   │           │                                                                 │
   │  [ WAF & Rate Limiting Engine ] ──────────────┐                             │
   │           │ (Allowed)                         │ (Blocked Events)            │
   │           ▼                                   ▼                             │
   │  [ Cloudflare Workers API ]          [ Firewall Logpush Engine ]            │
   │     │                │                        │                             │
   │     │ (Non-blocking) │ (Proxy to Origin)      │ (GZIP NDJSON Stream)        │
   │     ▼                ▼                        │                             │
   │  [Workers Engine] [Enterprise Origin]         │                             │
   │  (writePoint)        │                        │                             │
   │     │                │                        │                             │
   └─────┼────────────────┼────────────────────────┼─────────────────────────────┘
         │                │                        │
         │                ▼                        │
         │      [ HTTP Requests Logpush ]          │
         │                │                        │
         │                └───────────┬────────────┘
         │                            │
         ▼                            ▼ (HTTPS Push Streaming < 60s)
  ┌──────────────┐     ┌───────────────────────────────────────────────────────┐
  │  Workers SQL │     │               INGESTION & SINK LAYER                  │
  │   Analytics  │     │                                                       │
  │    Engine    │     │  ┌───────────────────────┐  ┌──────────────────────┐  │
  └──────────────┘     │  │ AWS S3 Bucket         │  │ Datadog / Splunk HEC │  │
         │             │  │ (Cold Storage / Audit)│  │ (Hot SIEM / Alerting)│  │
         ▼             │  └───────────────────────┘  └──────────────────────┘  │
  ┌──────────────┐     └───────────────────────────────────────────────────────┘
  │ Grafana / BI │                                 │
  │ Micro-tele-  │                                 ▼
  │ metry Query  │               ┌───────────────────────────────────┐
  └──────────────┘               │ Security Operations Center (SOC)  │
                                 │ - P1 Incident Alerting            │
                                 │ - Automated IP Quarantine         │
                                 │ - Forensic Investigation          │
                                 └───────────────────────────────────┘
```

---

## 9. Simple Example
Contoh konfigurasi Logpush HTTP Request sederhana langsung menggunakan cURL ke Cloudflare API v4 untuk mengirim data ke Datadog.

```bash
# 1. Buat Logpush Job untuk Dataset HTTP Requests langsung ke Datadog Logs API
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/logpush/jobs" \
     -H "X-Auth-Email: ${CF_EMAIL}" \
     -H "X-Auth-Key: ${CF_API_KEY}" \
     -H "Content-Type: application/json" \
     --data '{
       "name": "edge-http-requests-datadog",
       "destination_conf": "datadog://http-intake.logs.datadoghq.com/api/v2/logs?header_DD-API-KEY='${DATADOG_API_KEY}'&ddsource=cloudflare&service=edge-router",
       "dataset": "http_requests",
       "logstream_spec": "edge",
       "output_options": {
         "field_names": [
           "RayID",
           "EdgeStartTimestamp",
           "ClientIP",
           "ClientRequestHost",
           "ClientRequestMethod",
           "ClientRequestURI",
           "EdgeResponseStatus",
           "EdgeResponseBytes"
         ],
         "output_type": "ndjson"
       }
     }'
```

---

## 10. Practical Example (Terraform Pipeline & Workers Code)

Berikut adalah implementasi end-to-end arsitektur produksi menggunakan Terraform untuk memvalidasi ownership AWS S3, konfigurasi Logpush multi-sink, dan Worker dengan Analytics Engine.

### 10.1 Terraform: Enterprise Logpush ke AWS S3 & Datadog

```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.30.0"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "cloudflare_zone_id" {
  type        = string
  description = "Target Zone ID Cloudflare"
}

variable "cloudflare_account_id" {
  type        = string
  description = "Target Account ID Cloudflare"
}

variable "datadog_api_key" {
  type        = string
  sensitive   = true
  description = "API Key untuk Ingest Datadog SIEM"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

# 1. AWS S3 Bucket Setup untuk Cold Storage Logpush
resource "aws_s3_bucket" "edge_logs" {
  bucket        = "corp-enterprise-edge-logs-cold-storage"
  force_destroy = false
}

resource "aws_s3_bucket_server_side_encryption_configuration" "s3_encryption" {
  bucket = aws_s3_bucket.edge_logs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "log_lifecycle" {
  bucket = aws_s3_bucket.edge_logs.id

  rule {
    id     = "archive-and-retention"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }
  }
}

# S3 Policy Mengizinkan Akun Logpush Resmi Cloudflare
resource "aws_s3_bucket_policy" "allow_cloudflare_logpush" {
  bucket = aws_s3_bucket.edge_logs.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "CloudflareLogpushWrite"
        Effect    = "Allow"
        Principal = {
          # Cloudflare production Logpush AWS Account ARN
          AWS = "arn:aws:iam::395540211218:root"
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.edge_logs.arn}/*"
      }
    ]
  })
}

# 2. Ownership Challenge Validation untuk S3
resource "cloudflare_logpush_ownership_challenge" "s3_ownership_challenge" {
  zone_id          = var.cloudflare_zone_id
  destination_conf = "s3://${aws_s3_bucket.edge_logs.bucket}/http_requests?region=${var.aws_region}"
}

# 3. Logpush Job: HTTP Requests ke AWS S3 (Archive / Forensics)
resource "cloudflare_logpush_job" "s3_http_stream" {
  zone_id          = var.cloudflare_zone_id
  name             = "edge-to-s3-compliance-archive"
  destination_conf = "s3://${aws_s3_bucket.edge_logs.bucket}/http_requests?region=${var.aws_region}"
  dataset          = "http_requests"
  enabled          = true
  ownership_challenge = cloudflare_logpush_ownership_challenge.s3_ownership_challenge.ownership_challenge_filename

  output_options {
    field_names = [
      "RayID",
      "ClientIP",
      "ClientCountry",
      "ClientRequestHost",
      "ClientRequestMethod",
      "ClientRequestURI",
      "EdgeResponseStatus",
      "EdgeResponseBytes",
      "EdgeStartTimestamp",
      "EdgeEndTimestamp",
      "SecurityLevel",
      "WAFAction",
      "WAFRuleID"
    ]
    output_type = "ndjson"
    record_delimiter = "\n"
  }
}

# 4. Logpush Job: Firewall Events Terfilter ke Datadog SIEM (Hot Security Alerting)
resource "cloudflare_logpush_job" "datadog_firewall_stream" {
  zone_id          = var.cloudflare_zone_id
  name             = "edge-firewall-events-datadog"
  destination_conf = "datadog://http-intake.logs.datadoghq.com/api/v2/logs?header_DD-API-KEY=${var.datadog_api_key}&ddsource=cloudflare&service=cloudflare-waf"
  dataset          = "firewall_events"
  enabled          = true

  filter = jsonencode({
    where = {
      and = [
        {
          key      = "Action"
          operator = "in"
          value    = ["block", "challenge", "jschallenge", "managed_challenge"]
        }
      ]
    }
  })

  output_options {
    field_names = [
      "RayName",
      "Datetime",
      "Action",
      "ClientIP",
      "ClientCountry",
      "ClientRequestPath",
      "ClientRequestQuery",
      "ClientRequestUserAgent",
      "RuleId",
      "Source",
      "MatchDetails"
    ]
    output_type = "ndjson"
  }
}
```

### 10.2 Workers Analytics Engine Implementation (`worker.js`)

Implementasi edge worker yang memproses request dan memancarkan data point kardinalitas tinggi langsung ke Analytics Engine.

```javascript
export default {
  async fetch(request, env, ctx) {
    const startTime = performance.now();
    const rayId = request.headers.get("cf-ray") || "unknown";
    const country = request.cf ? request.cf.country : "XX";
    const colo = request.cf ? request.cf.colo : "XXX";
    const url = new URL(request.url);

    let upstreamResponse;
    let customStatus = 200;

    try {
      // Forward traffic ke target upstream origin
      upstreamResponse = await fetch(request);
      customStatus = upstreamResponse.status;
      return upstreamResponse;
    } catch (err) {
      customStatus = 502;
      return new Response("Edge Gateway Bad Origin Error", { status: 502 });
    } finally {
      const executionDuration = performance.now() - startTime;

      // Asynchronous, zero-latency overhead logging to Workers Analytics Engine
      if (env.EDGE_METRICS) {
        env.EDGE_METRICS.writeDataPoint({
          blobs: [
            rayId,                   // blob1: Ray ID (high-cardinality)
            country,                 // blob2: Client Country
            colo,                    // blob3: Cloudflare PoP Location
            url.pathname,            // blob4: Resource Path
            request.method           // blob5: HTTP Method
          ],
          doubles: [
            executionDuration,       // double1: Microsecond Edge Duration
            customStatus,            // double2: HTTP Status Code
            request.headers.get("content-length") ? parseInt(request.headers.get("content-length")) : 0 // double3: Request Size
          ],
          indexes: [
            url.hostname             // index1: Customer/Domain Indexing Key
          ]
        });
      }
    }
  }
};
```

---

## 11. Real World Example
Sebuah institusi perbankan multinasional (`Bank X`) memproses rata-rata 120.000 transaksi per detik di edge Cloudflare. Mereka memiliki kendala:
1. Datadog mereka mengalami lonjakan biaya bulanan lebih dari $85.000 hanya karena log HTTP `200 OK` dari aset gambar dan CSS.
2. Tim SOC (Security Operations Center) melewatkan serangan Credential Stuffing karena alert WAF tertimbun oleh jutaan log normal.

**Solusi yang Diterapkan:**
1. **Tiered Telemetry Split:**
   * **Tier 1 (Cold Forensics - S3):** Mengalirkan 100% log HTTP Requests mentah tanpa filter ke AWS S3 Glacier dengan siklus retensi 7 tahun untuk audit regulasi OJK/PCI-DSS.
   * **Tier 2 (Hot SIEM - Splunk):** Hanya mengalirkan dataset `firewall_events` dengan filter `Action != "allow"`, ditambah dataset `http_requests` dengan status `>= 400` dan sampling 1% untuk status `200 OK`.
2. **Workers Analytics Engine Integration:**
   * Memasang instrumentation edge worker pada endpoint `/api/v1/auth/login` untuk mengumpulkan metrik `RayID`, `DeviceFingerprint`, dan `Latency` tanpa menyentuh SIEM ingest.
3. **Hasil:**
   * Penurunan biaya ingest log di SIEM hingga 88%.
   * Mean Time to Detect (MTTD) untuk serangan credential stuffing turun dari 42 menit menjadi 18 detik berkat alert stream spesifik di Firewall Events Logpush.

---

## 12. Trade-offs

| Pendekatan | Kelebihan | Kekurangan / Batasan |
| :--- | :--- | :--- |
| **Direct SIEM Logpush (Datadog/Splunk)** | * Near real-time (< 30s).<br>* Tanpa maintenance infrastructure intermediary.<br>* Pipeline alerting langsung aktif. | * Biaya ingest SIEM sangat tinggi bila traffic tidak difilter.<br>* Bergantung penuh pada uptime ingestion endpoint vendor SIEM. |
| **Object Storage Stage-In (S3 -> SQS -> SIEM)** | * Biaya penyimpanan dingin (cold) sangat murah.<br>* Immutable raw storage untuk kebutuhan forensik compliance.<br>* Buffering alami saat SIEM mengalami maintenance. | * Tambahan latensi ingest (2-5 menit).<br>* Kompleksitas manajemen pipeline IaC tambahan (SNS, SQS, Lambda). |
| **Workers Analytics Engine** | * Tidak membebani runtime thread CPU Workers.<br>* Bebas limit kardinalitas (jutaan data unik tanpa OOM).<br>* Query SQL performa tinggi via API. | * Bukan persistent SIEM; retensi data terbatas.<br>* Field blobs & doubles terbatas maksimal 20 item per tipe. |

---

## 13. When To Use
* Gunakan **Logpush HTTP Requests ke S3/GCS** saat organisasi Anda tunduk pada regulasi compliance data retention ketat (PCI-DSS, HIPAA, GDPR).
* Gunakan **Logpush Firewall Events ke Datadog/Splunk** saat tim SecOps membutuhkan deteksi insiden real-time, korelasi IP reputasi, dan auto-mitigasi WAF.
* Gunakan **Workers Analytics Engine** saat Anda membutuhkan telemetri performa edge API kustom, visualisasi SLA P99 per endpoint dinamis, atau deteksi anomali real-time internal tanpa membayar lisensi SIEM per gigabyte.

---

## 14. When NOT To Use
* **Jangan** gunakan Logpush langsung ke SIEM tanpa *Field Selection* dan *Filtering*: Ini adalah anti-pattern yang mengakibatkan pembengkakan biaya ingestion secara dramatis.
* **Jangan** gunakan Workers Analytics Engine sebagai pengganti Relational Database (seperti D1 atau PostgreSQL): Data Analytics Engine bersifat append-only write-optimized metrics, bukan transactional ACID storage.
* **Jangan** gunakan Cloudflare API Audit Log untuk data analitik traffic web: Audit Log secara eksklusif hanya merekam *manajemen perubahan konfigurasi* (misal: user login dashboard, hapus DNS, ubah security rule).

---

## 15. Common Mistakes
1. **Lupa Menyelesaikan Ownership Challenge:** Mencoba membuat job Logpush via automation sebelum file/token validasi di S3 atau HTTP endpoint diverifikasi, menyebabkan deployment Terraform gagal dengan error `10020: ownership challenge failed`.
2. **Missing KMS / IAM Permission pada S3:** Bucket S3 menolak request dari Cloudflare karena policy tidak mengizinkan AWS Principal Cloudflare Logpush (`arn:aws:iam::395540211218:root`).
3. **Mengirim Uncompressed Payload ke SIEM:** Mengonfigurasi endpoint kustom tanpa mengaktifkan handling dekompresi gzip, mengakibatkan receiver SIEM membaca *corrupted binary stream*.
4. **Kardinalitas Tidak Terkendali pada SIEM Tags:** Memetakan `RayID` atau `ClientIP` sebagai *Facet / Tag Global* di Datadog/Splunk, yang memicu lonjakan biaya metric indexing hingga ribuan dolar.

---

## 16. Best Practices
1. **Sanitasi PII di Edge:** Gunakan *Field Selection* Logpush untuk mengecualikan header cookie sensitif (`Cookie`, `Authorization`, `Set-Cookie`) sebelum payload meninggalkan Cloudflare network.
2. **Multi-Destination Segregation:** Pisahkan job Logpush:
   * Target Storage (S3/GCS) untuk *all traffic* (audit trail/forensics).
   * Target SIEM (Datadog/Splunk) untuk *security signals* (`firewall_events` dan `HTTP status >= 400`).
3. **Terapkan Dynamic Sampling:** Gunakan konfigurasi `sample = 0.05` (5%) pada traffic HTTP 200 OK untuk memantau performa cache dan latency agregat tanpa menghabiskan kuota downstream.
4. **Dead-Letter Monitoring:** Pasang Cloudflare Notification Alert jika ada job Logpush yang mengalami status `failing` lebih dari 15 menit.

---

## 17. Troubleshooting

| Gejala Masalah | Penyebab Utama | Solusi Remediasi |
| :--- | :--- | :--- |
| `ownership challenge failed (code 10020)` | Cloudflare tidak dapat membaca file verifikasi di S3 bucket atau status code validation bukan 200. | Pastikan S3 bucket policy mengizinkan `s3:PutObject` untuk ARN `395540211218`. Lakukan verifikasi manual token file via AWS CLI. |
| Job Logpush otomatis disable (`job state: failing`) | Target SIEM mengembalikan status HTTP 403 (Invalid Token) atau 429 (Rate Limited) secara terus menerus. | Periksa validitas API Key / HEC Token. Tingkatkan rate limit quota pada ingestion gateway Datadog/Splunk Anda. |
| Datadog tidak menampilkan data WAF | Filter Logpush terlalu ketat atau mapping field Datadog salah. | Pastikan field `Action` dan `RuleId` diikutsertakan dalam `field_names`. Periksa log intake Datadog untuk format parsing rule. |
| Query Workers Analytics Engine selalu kosong | Indexing key mismatch atau Worker binding belum diinisialisasi di `wrangler.toml`. | Pastikan binding `EDGE_METRICS` terdaftar pada `wrangler.toml` dan waktu query SQL mencakup window data ingestion (tunggu propagasi 60-90 detik). |

---

## 18. Exercise
Selesaikan instruksi berikut secara mandiri:
1. Tuliskan satu kueri SQL Workers Analytics Engine untuk menghitung persentil ke-95 (`quantile(0.95, double1)`) durasi eksekusi per kode lokasi Cloudflare PoP (`blob3`) dalam 1 jam terakhir.
2. Definisikan sebuah blok JSON filter Cloudflare Logpush yang hanya menangkap request HTTP yang memiliki `EdgeResponseStatus` bernilai `500`, `502`, `503`, atau `504` DENGAN `ClientRequestPath` yang diawali `/checkout/`.

---

## 19. Challenge
Sebuah enterprise fintech mengalami kebocoran data credential akibat token hijacking. Selaku Principal Cloud & SRE Architect, Anda ditugaskan merancang solusi Capstone:
1. Bangun pipeline Terraform lengkap yang memisahkan storage cold-archive (S3) dengan hot SIEM (Datadog).
2. Terapkan WAF Custom Rule yang memblokir IP dengan Bot Score < 30 pada path `/api/v2/transfer`.
3. Buat Workers Analytics Engine script yang mencatat setiap request terindikasi fraud ke tabel telemetri internal lengkap dengan `RayID`, `IP`, `BotScore`, dan `ProcessingLatency`.
4. Rancang alert SIEM kustom yang memicu PagerDuty P1 incident jika terdapat lebih dari 50 event blocked WAF pada endpoint transfer dalam jendela waktu 60 detik.

---

## 20. Summary
* **Cloudflare Logpush** adalah mekanisme pengiriman telemetri edge tingkat enterprise yang menyalurkan jutaan event per detik ke AWS S3, Datadog, atau Splunk dengan latensi sub-menit dan format terstandarisasi (NDJSON GZIP).
* **Efisiensi Biaya SIEM** dicapai melalui filtering log cerdas, field sanitization, dan dynamic sampling langsung di edge sebelum data keluar dari jaringan Cloudflare.
* **Workers Analytics Engine** menutup celah observabilitas internal dengan menyediakan database time-series SQL berbasis edge berkinerja tinggi yang kebal terhadap masalah ledakan kardinalitas metrik.
* **Audit Logs** melengkapi pilar observabilitas dengan memastikan seluruh aktivitas konfigurasi perimeter tercatat secara permanen untuk kebutuhan forensik dan tata kelola kepatuhan keamanan internasional.

---