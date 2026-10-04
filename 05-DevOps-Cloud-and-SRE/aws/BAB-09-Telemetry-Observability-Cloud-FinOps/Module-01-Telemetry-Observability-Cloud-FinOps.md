# Modul 01: Telemetry, Observability & Cloud Financial Ops (FinOps)

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Merancang dan mengimplementasikan pilar observabilitas (Metrics, Logs, Traces) pada arsitektur AWS skala enterprise menggunakan Amazon CloudWatch, CloudWatch Logs Insights, dan AWS X-Ray.
- Menyusun alerting framework berbasis SLO/SLI menggunakan CloudWatch Metric Math, Anomaly Detection, dan Composite Alarms untuk meminimalkan *alert fatigue*.
- Mengonfigurasi audit trail keamanan multi-region dan multi-account yang immutable menggunakan AWS CloudTrail, Log File Validation, dan Athena partitioning.
- Menguasai disiplin Cloud Financial Operations (FinOps): menganalisis profil biaya dengan AWS Cost Explorer, menetapkan guardrail otomatis dengan AWS Budgets, dan merancang strategi komitmen finansial (Savings Plans vs Reserved Instances).
- Mengintegrasikan analisis biaya prediktif ke dalam CI/CD pipeline menggunakan Infracost untuk pergeseran paradigma FinOps ke arah *shift-left cost visibility*.

---

## 2. Prerequisite
Untuk memahami materi ini secara optimal, peserta harus memiliki:
- Pemahaman mendalam tentang arsitektur komputasi AWS (EC2, ECS, AWS Lambda) dan jaringan (VPC, NAT Gateway, VPC Endpoints).
- Kemampuan menulis Infrastructure as Code (IaC) menggunakan HashiCorp Terraform v1.5+.
- Pemahaman protokol distributed systems (HTTP/gRPC, context propagation, correlation IDs).
- Pemahaman dasar akuntansi cloud: CapEx vs OpEx, amortisasi, unit economics, dan alokasi biaya berbasis tagging.
- Akses ke AWS Management Console dan AWS CLI v2 yang terotentikasi dengan hak akses administratif IAM.

---

## 3. Concept
Dalam ekosistem *cloud-native*, keandalan sistem (*reliability*) dan efisiensi biaya (*cost efficiency*) adalah dua sisi dari mata uang yang sama. 

**Observability** bukanlah sekadar mengumpulkan data telemetri, melainkan kemampuan untuk menyimpulkan kondisi internal suatu sistem yang kompleks hanya dari output eksternalnya. Tiga pilar observabilitas mencakup:
1. **Metrics**: Data numerik teragregasi berbasis time-series yang merefleksikan kesehatan sistem (misal: utilisasi CPU, throughput, p99 latency).
2. **Logs**: Catatan diskrit berbasis waktu (timestamped event records) dengan payload terstruktur (JSON) yang memberikan konteks mendalam mengenai eksekusi kode atau audit sistem.
3. **Traces**: Representasi perjalanan end-to-end dari sebuah request saat melintasi berbagai batasan jaringan mikroservis, mengungkap bottleneck latensi dan kegagalan dependensi downstream.

**FinOps (Cloud Financial Operations)** adalah disiplin kultural dan praktik operasional yang membawa akuntabilitas finansial ke dalam model pengeluaran variabel cloud. FinOps menyelaraskan Engineering, Finance, dan Business untuk mendorong keputusan berbasis data melalui siklus berkelanjutan: *Inform* (visibilitas biaya), *Optimize* (reduksi pemborosan dan optimalisasi rate), dan *Operate* (integrasi tata kelola biaya otomatis ke dalam alur kerja rekayasa perangkat lunak).

---

## 4. Why
Mengapa integrasi Observability dan FinOps merupakan kapabilitas non-negosiasi bagi Principal Cloud/SRE Engineer?
- **Mean Time to Resolution (MTTR) Compression**: Tanpa distributed tracing dan log aggregation terpusat, troubleshooting insiden pada klaster mikroservis terdistribusi membutuhkan waktu berjam-jam (koleksi manual log EC2/container). Observabilitas terintegrasi memangkas MTTR menjadi hitungan menit.
- **Alert Fatigue Prevention**: Alarm statis konvensional (misal: "CPU > 80%") menghasilkan false-positive kronis. Penerapan Metric Math, Dynamic Anomaly Detection, dan Composite Alarms memastikan engineer hanya dibangunkan oleh degradasi performa nyata yang mengancam Service Level Objectives (SLO).
- **Compliance & Forensics Immutability**: Regulasi industri (PCI-DSS, SOC 2, ISO 27001) mewajibkan audit trail yang tahan manipulasi. AWS CloudTrail menyediakan rantai bukti historis atas seluruh API call di cloud perimeter.
- **Bill Shock Mitigation**: Model konsumsi cloud yang elastis dapat menyebabkan pembengkakan biaya tak terkontrol akibat provisioning yang salah (misal: loop rekursif Lambda atau over-provisioned provisioned IOPS EBS). FinOps guardrails mencegah kebangkrutan operasional melalui budgeting real-time dan analisis biaya prediktif di tahap Pull Request.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Amazon CloudWatch Core Architecture
CloudWatch beroperasi sebagai hub telemetri terpusat AWS:
- **High-Resolution Metrics**: Metrik standar beresolusi 1 menit. Metrik kustom dapat dipublikasikan dengan resolusi tinggi hingga 1 detik (*high-resolution metrics* via parameter `StorageResolution=1`), krusial untuk sub-minute spike detection.
- **Metric Math**: Memungkinkan eksekusi operasi matematika pada multiple time-series metrics. Sintaks mendukung fungsi analitik seperti `RATE()`, `AVG()`, `PERCENTILE()`, dan logika boolean `IF(condition, true_val, false_val)`.
- **Metric Anomaly Detection**: Menerapkan machine learning algorithms pada pola historis metrik untuk menghasilkan *expected band of values* yang menyesuaikan variasi diurnal, tren mingguan, dan musiman tanpa intervensi manual.
- **Composite Alarms**: Alarm yang mengevaluasi status beberapa alarm anak (*child alarms*) menggunakan operator logika (`AND`, `OR`, `NOT`). Pendekatan ini secara drastis mengurangi noise dengan hanya menembakkan peringatan ketika kondisi multivariat terpenuhi (misal: Latency Tinggi `AND` Error 5xx Naik `AND NOT` Status Deployment Aktif).

```
                      +---------------------------------------+
                      |       Composite Alarm Evaluator       |
                      | (Alarm A AND Alarm B) AND NOT Alarm C |
                      +-------------------+-------------------+
                                          |
                +-------------------------+-------------------------+
                |                                                   |
      +---------v---------+                               +---------v---------+
      |  Latency High p99 |                               |  HTTP 5xx Spike   |
      |   (Metric Math)   |                               | (Anomaly Detection|
      +-------------------+                               +-------------------+
```

### 5.2 CloudWatch Logs Insights
Mesin query interaktif terdistribusi untuk menganalisis log tanpa mengelola cluster log indexing. Menggunakan bahasa query deklaratif berbasis pipeline:
```sql
fields @timestamp, @message, status, responseLatency
| filter status >= 500
| stats count(*) as ErrorCount, pct(responseLatency, 99) as p99Latency by bin(5m)
| sort ErrorCount desc
| limit 20
```

### 5.3 AWS X-Ray Distributed Tracing
X-Ray melacak alur request end-to-end dengan menginjeksi dan mempropagasi trace context header melalui HTTP:
`X-Amzn-Trace-Id: Root=1-5759e988-bd862e3fe1be46a994272767;Parent=53995cbe316bb7bb;Sampled=1`
- **Segments**: Data komputasi yang dihasilkan oleh server resource yang melayani request (resource name, metadata runtime, HTTP attributes).
- **Subsegments**: Detail granular breakdown pekerjaan dalam service yang sama (panggilan downstream database queries, HTTP calls ke eksternal API, eksekusi fungsi internal).
- **Sampling Rules**: Mengontrol volume trace data yang dikirim ke X-Ray untuk mengoptimasi biaya tracing. Format konfigurasi mencakup atribut `ReservoirSize` (jumlah trace minimum per detik yang dijamin di-sample) dan `FixedRate` (persentase request berikutnya di-sample).

### 5.4 AWS CloudTrail Audit Architecture
CloudTrail merekam aktivitas API di seluruh akun AWS:
- **Management Events**: Operasi bidang kontrol (*control plane*) seperti pembuatan resource (`CreateBucket`, `RunInstances`, `ModifySecurityGroupRules`). Diaktifkan secara default untuk 90 hari pertama via Event History.
- **Data Events**: Operasi bidang data (*data plane*) bervolume tinggi seperti pemanggilan objek S3 (`GetObject`, `PutObject`) dan eksekusi fungsi Lambda (`Invoke`). Berbayar per 100.000 event, memerlukan pertimbangan seleksi tag yang ketat.
- **Log File Validation**: Menggunakan public key cryptography (RSA) dan hashing SHA-256 untuk memverifikasi bahwa log files tidak dimodifikasi, dihapus, atau di-tamper setelah ditulis oleh CloudTrail ke S3 bucket. Menghasilkan *digest files* setiap jam yang berisi hash dari file log yang dikirimkan.

### 5.5 FinOps Governance, Cost Modeling & Shift-Left
- **AWS Cost Explorer**: Mesin agregasi dan forecasting multidimensi. Memungkinkan visualisasi data cost & usage dengan granularitas harian atau bulanan, difilter berdasarkan Usage Type, Service, Region, dan Cost Allocation Tags.
- **Savings Plans vs Reserved Instances (RI)**:
  - *Compute Savings Plans*: Fleksibilitas tertinggi. Komitmen pengeluaran tetap per jam ($/jam) selama 1 atau 3 tahun. Diskon hingga 66%. Berlaku otomatis untuk EC2 (tanpa memandang family, OS, Region), Fargate, dan Lambda.
  - *EC2 Instance Savings Plans*: Fleksibilitas sedang. Komitmen pada famili instance tertentu di suatu Region (misal: famili `m6i` di `ap-southeast-1`). Diskon hingga 72%. Mengakomodasi perubahan ukuran (size), OS, dan tenancy.
  - *Standard Reserved Instances*: Kurang fleksibel dibanding Savings Plans modern, namun tetap relevan untuk RDS, ElastiCache, OpenSearch, dan Redshift.
- **AWS Budgets**: Memicu notifikasi email, SNS, atau eksekusi aksi otomatis (AWS Systems Manager runbook / IAM Policy restriction) saat aktual atau perkiraan (*forecasted*) biaya melampaui ambang batas persentase anggaran yang ditentukan.
- **Infracost**: Alat CLI dan CI/CD scanner yang mem-parsing Terraform AST (Abstract Syntax Tree) sebelum eksekusi `terraform apply`, memetakan definisi resource ke pricing API Cloud Provider, dan menghasilkan diff biaya langsung di Pull Request code review.

---

## 6. How
Implementasi menyeluruh Observability dan FinOps melibatkan empat tahapan siklus hidup:
1. **Instrumentasi Kode & Runtime**:
   - Pasang AWS OpenTelemetry (ADOT) SDK atau Native X-Ray SDK ke codebase aplikasi.
   - Format log output stdout aplikasi ke struktur JSON standar yang mencakup field metadata wajib: `trace_id`, `environment`, `service_name`, `severity`.
2. **Provisioning Infrastruktur Telemetri**:
   - Buat CloudTrail multi-region dengan Log File Validation aktif dan pengiriman ke S3 bucket yang diproteksi S3 Object Lock (WORM).
   - Konfigurasi CloudWatch Log Retention Policy (misal: 30 hari untuk development, 90 hari untuk production, dialihkan ke S3 Glacier via Lifecycle Policy untuk arsip kepatuhan tahunan).
3. **Konfigurasi Alarm Berbasis SLO**:
   - Terapkan CloudWatch Metric Math untuk mengekstrak Error Budget Consumption:
     $$\text{ErrorRate} = \left(\frac{\text{HTTP 5xx}}{\text{Total HTTP Requests}}\right) \times 100$$
   - Buat Composite Alarms yang menggabungkan Error Budget depletion dengan infrastruktur bottleneck alarms.
4. **Automasi FinOps Shift-Left**:
   - Terapkan kebijakan penandaan resource (*Resource Tagging Enforcement*) via AWS Organizations Service Control Policies (SCPs) untuk tag wajib: `Environment`, `Owner`, `CostCenter`, `Project`.
   - Pasang GitHub Actions workflow dengan integrasi Infracost untuk memblokir pull request yang menambah estimasi biaya bulanan di luar ambang batas tanpa approval FinOps team.

---

## 7. Analogy
Bayangkan Anda mengoperasikan maskapai penerbangan komersial skala internasional:
- **CloudWatch Metrics** adalah panel instrumen kokpit pesawat (altimeter, speedometer, sensor temperatur mesin). Menunjukkan angka kuantitatif real-time, memberi tahu Anda jika pesawat menukik turun atau mesin kepanasan.
- **CloudWatch Logs** adalah kotak hitam (*Flight Data Recorder*) dan rekaman suara kokpit. Jika terjadi anomali pada instrumen, log menyediakan catatan mendalam detik demi detik tentang tombol apa yang ditekan dan pesan kesalahan apa yang dicetak subsistem.
- **AWS X-Ray** adalah sistem pelacak bagasi dan alur penumpang terpadu dari tiket counter, security check, boarding gate, baggage handling, hingga baggage claim di bandara tujuan. Anda dapat melihat secara presisi konveyor mana yang macet dan menyebabkan penundaan 40 menit.
- **AWS CloudTrail** adalah menara pengawas lalu lintas udara dan log audit keamanan bandara. Merekam siapa yang masuk ke hanggar, siapa yang mengotorisasi pengisian bahan bakar, dan instruksi runway apa yang diberikan oleh kontroler ATC.
- **FinOps & Infracost** adalah departemen efisiensi rute dan pengadaan bahan bakar pesawat. Infracost memprediksi berapa banyak avtur yang akan dihabiskan *sebelum* rute penerbangan baru disetujui, sementara Savings Plans adalah kontrak lindung nilai (*hedging*) bahan bakar jangka panjang untuk mendapatkan diskon grosir daripada membeli avtur dengan harga eceran harian di bandara (*On-Demand rate*).

---

## 8. Diagram (ASCII)

```
========================================================================================================
                         AWS OBSERVABILITY & FINOPS END-TO-END BLUEPRINT
========================================================================================================

 [ Developer / CI/CD ]
          │
          ├── (1) Git Push / Pull Request ─────────► [ Infracost CLI ]
          │                                                  │ (Evaluasi Delta Biaya)
          │                                                  ▼
          │                                           [ PR Block / Warn ]
          │
          └── (2) Terraform Deploy
                     │
                     ▼
       ┌────────────────────────────── AWS VPC (ap-southeast-1) ──────────────────────────────────┐
       │                                                                                          │
       │    [ Client Traffic ]                                                                    │
       │            │                                                                             │
       │            ▼                                                                             │
       │    [ Application Load Balancer ] ──────► Access Logs ────────┐                            │
       │            │                                                 │                            │
       │            │ X-Amzn-Trace-Id Propagation                     │                            │
       │            ▼                                                 │                            │
       │    [ ECS Task / EKS Pod ]                                    ▼                            │
       │      │  ├── Microservice (App Code)                   [ S3 Bucket: WORM ]                 │
       │      │  │     └── Injects: Metrics, JSON Logs, Traces (Immutable Audit Storage)          │
       │      │  └── ADOT / X-Ray Daemon                              ▲                            │
       │      │                                                       │ (Digest & Log files)       │
       │      └─────────────────┬──────────────────┐                  │                            │
       │                        │                  │                  │                            │
       └────────────────────────┼──────────────────┼──────────────────┼────────────────────────────┘
                                │                  │                  │
                Telemetry Data  │                  │ Traces           │ API Control Plane
                                ▼                  ▼                  │
            ┌───────────────────────┐   ┌──────────────────────┐      │
            │ Amazon CloudWatch     │   │     AWS X-Ray        │      │
            ├───────────────────────┤   ├──────────────────────┤      │
            │ Metrics & Metric Math │   │ Distributed Tracing  │      │
            │ Logs Insights Query   │   │ Service Dependency   │      │
            │ Anomaly Detection     │   │ Latency Percentiles  │      │
            │ Composite Alarms      │   └──────────────────────┘      │
            └───────────┬───────────┘                                 │
                        │                                             │
                        ▼                                             │
               [ Amazon SNS Topic ]                                   │
                        │                                             │
                        ├──────────────────────┐                      │
                        ▼                      ▼                      │
              [ PagerDuty / Slack ]   [ Auto-Remediation ]            │
                                         (SSM / Lambda)               │
                                                                      │
       ┌─────────────────────── FINOPS & AUDIT SUITE ─────────────────┴────────────────────────────┐
       │                                                                                           │
       │  [ AWS CloudTrail ] ──────────► S3 Object Lock + CloudWatch Logs Group                     │
       │  [ AWS Cost Explorer ] ───────► Machine Learning Cost Forecasting                         │
       │  [ AWS Budgets ] ─────────────► Action Framework (Auto Stop Non-Prod, Restrict IAM Policy)│
       │  [ Savings Plans / RI ] ──────► Compute & EC2 Coverage Optimizer (Coverage Target: 80%+)  │
       └───────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Simple Example
Berikut adalah contoh implementasi query CloudWatch Logs Insights untuk mengekstrak error rate dan visualisasi Metric Math sederhana:

### Log Analysis Query:
```sql
fields @timestamp, @message
| filter @message like /ERROR/ or @message like /Exception/
| stats count(*) as ErrorCount by bin(1m)
| sort @timestamp desc
```

### Konfigurasi Metric Math Formula:
Jika Anda memiliki dua metrik:
- `m1` = CloudWatch metric untuk ALB `HTTPCode_Target_5XX_Count`
- `m2` = CloudWatch metric untuk ALB `RequestCount`

Maka ekspresi persentase kegagalan (*Failure Rate*):
```
Expression: (m1 / m2) * 100
Id: e1
Label: "HTTP 5xx Failure Percentage"
```

---

## 10. Practical Example (Konfigurasi CLI / Terraform / Hands-on)

Berikut adalah arsitektur infrastruktur Terraform lengkap dan modular yang mengimplementasikan:
1. CloudTrail dengan Log File Validation, S3 Storage, dan enkripsi KMS.
2. CloudWatch Log Group dengan retention policy terkelola.
3. CloudWatch Metric Alarm dengan Metric Math untuk mendeteksi Error Rate HTTP ALB.
4. AWS Budgets dengan ambang batas alerting berbasis biaya aktual dan *forecasted*.

```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "ap-southeast-1"
  default_tags = {
    Environment = "production"
    CostCenter  = "core-infra-101"
    ManagedBy   = "terraform"
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ==============================================================================
# 1. AWS CLOUDTRAIL WITH LOG FILE VALIDATION & KMS
# ==============================================================================

resource "aws_kms_key" "cloudtrail_kms" {
  description             = "KMS Key for CloudTrail Log Encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow CloudTrail to encrypt logs"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action = [
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_s3_bucket" "audit_bucket" {
  bucket        = "corp-audit-logs-${data.aws_caller_identity.current.account_id}"
  force_destroy = false
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit_bucket_crypto" {
  bucket = aws_s3_bucket.audit_bucket.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.cloudtrail_kms.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "audit_bucket_pab" {
  bucket                  = aws_s3_bucket.audit_bucket.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "audit_bucket_policy" {
  bucket = aws_s3_bucket.audit_bucket.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AWSCloudTrailAclCheck"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "s3:GetBucketAcl"
        Resource = aws_s3_bucket.audit_bucket.arn
      },
      {
        Sid    = "AWSCloudTrailWrite"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.audit_bucket.arn}/prefix/AWSLogs/${data.aws_caller_identity.current.account_id}/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }
        }
      }
    ]
  })
}

resource "aws_cloudtrail" "main_audit_trail" {
  name                          = "enterprise-governance-trail"
  s3_bucket_name                = aws_s3_bucket.audit_bucket.id
  s3_key_prefix                 = "prefix"
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true
  kms_key_id                    = aws_kms_key.cloudtrail_kms.arn

  depends_on = [aws_s3_bucket_policy.audit_bucket_policy]
}

# ==============================================================================
# 2. CLOUDWATCH LOG GROUP & METRIC MATH ERROR RATE ALARM
# ==============================================================================

resource "aws_cloudwatch_log_group" "application_logs" {
  name              = "/aws/apps/production-gateway"
  retention_in_days = 90
  kms_key_id        = aws_kms_key.cloudtrail_kms.arn
}

resource "aws_sns_topic" "sre_alerts" {
  name = "sre-high-severity-notifications"
}

resource "aws_cloudwatch_metric_alarm" "api_error_rate_alarm" {
  alarm_name          = "alb-high-5xx-error-rate-slo-breach"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = 5.0 # Ambang batas persentase 5%
  datapoints_to_alarm = 2
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.sre_alerts.arn]
  ok_actions    = [aws_sns_topic.sre_alerts.arn]

  # Metric Math: Menghitung persentase 5xx dari total requests
  metric_query {
    id          = "e1"
    expression  = "(m1 / m2) * 100"
    label       = "Calculated HTTP 5xx Rate (%)"
    return_data = true
  }

  metric_query {
    id = "m1"
    metric {
      namespace   = "AWS/ApplicationELB"
      metric_name = "HTTPCode_Target_5XX_Count"
      period      = 60
      stat        = "Sum"
      dimensions = {
        LoadBalancer = "app/prod-alb/50dc6c495c0c9188"
      }
    }
  }

  metric_query {
    id = "m2"
    metric {
      namespace   = "AWS/ApplicationELB"
      metric_name = "RequestCount"
      period      = 60
      stat        = "Sum"
      dimensions = {
        LoadBalancer = "app/prod-alb/50dc6c495c0c9188"
      }
    }
  }
}

# ==============================================================================
# 3. AWS BUDGETS: ACTUAL & FORECASTED FINANCIAL GUARDRAILS
# ==============================================================================

resource "aws_budgets_budget" "monthly_production_budget" {
  name              = "monthly-production-workload-budget"
  budget_type       = "COST"
  limit_amount      = "5000"
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = "2026-01-01_00:00"

  cost_filter {
    name   = "TagKeyValue"
    values = ["Environment$production"]
  }

  # Alert 1: Aktual biaya mencapai 85%
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 85
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = ["finops-alerts@corporation.com"]
  }

  # Alert 2: Forecast pengeluaran melampaui 100% dari alokasi budget
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = ["sre-lead@corporation.com", "finops-alerts@corporation.com"]
  }
}
```

---

## 11. Real World Example
Sebuah platform fintech unicorn memproses 40.000 transaksi pembayaran per detik selama acara belanja nasional (11.11).

**Permasalahan:**
Pada pukul 00:05, volume *failed transactions* melonjak drastis dari 0.01% ke 12%. Alarm statis konvensional (CPU Usage) pada auto-scaling group payment worker tetap berada di kisaran normal 45%. SRE on-call mengalami *alert deluge* dari 30 microservice berbeda secara bersamaan tanpa kejelasan sumber masalah.

**Investigasi Berbasis Observability Terpadu:**
1. SRE memeriksa **AWS X-Ray Service Map**. Terlihat node microservice `payment-core` berubah warna menjadi merah tua, dengan downstream call ke payment gateway eksternal pihak ketiga memiliki latensi p99 sebesar 14.2 detik (baseline normal: 350 milidetik).
2. SRE mengeksekusi query **CloudWatch Logs Insights** secara cross-account:
   ```sql
   fields @timestamp, correlationId, error.code, downstreamHost
   | filter service = "payment-core" and httpStatus >= 500
   | stats count(*) by downstreamHost, error.code
   ```
   Query mengonfirmasi bahwa 98.7% kegagalan berasal dari koneksi *read timeout* ke bank partner tertentu (`gw-partner-b.banking.net`).
3. **Composite Alarm** mendeteksi kegagalan tersebut bukan karena infrastruktur internal, melainkan dependency eksternal, sehingga workflow auto-remediation mengaktifkan *circuit breaker* secara otomatis ke bank cadangan.

**Dampak FinOps Pasca-Insiden:**
- Pada sisi FinOps, lonjakan retry loop yang tidak terkontrol sebelumnya menghasilkan 120 juta invocations AWS Lambda tak berujung, memicu peringatan AWS Budgets tingkat "Forecasted Breach".
- Tim FinOps dan SRE merevisi arsitektur retry dengan *exponential backoff and jitter*, serta mengaplikasikan *Compute Savings Plans* 3 tahun untuk base workload layer Lambda dan Fargate, menghemat $14.500 per bulan (pengurangan biaya 42%).

---

## 12. Trade-offs

| Parameter Desain | Opsi A | Opsi B | Implikasi Teknis & Biaya |
| :--- | :--- | :--- | :--- |
| **X-Ray Sampling Rate** | **High Fixed Rate (e.g., 50-100%)** | **Dynamic Low Rate (e.g., 5% + Reservoir)** | Sampling 100% memberikan visibilitas absolut namun biaya penagihan X-Ray melonjak eksponensial pada throughput tinggi ($5.00 per juta traces). Dynamic sampling menjaga efisiensi biaya tanpa kehilangan representasi statistik latensi p99. |
| **Log Retention Policy** | **Indefinite (Never Expire)** | **Tiered Lifecycle (CW Logs -> S3 -> Glacier)** | Menyimpan log di CloudWatch Logs selamanya berharga $0.03/GB/bulan. Menurunkannya ke S3 Standard ($0.023/GB) dan Glacier Flexible Deep Archive ($0.00099/GB) menghemat >95% storage cost. |
| **FinOps Commitment** | **Standard Reserved Instances** | **Compute Savings Plans** | RI menawarkan diskon sedikit lebih tinggi pada konfigurasi kaku (tipe instance/Region tetap), namun Savings Plans memberikan adaptabilitas multi-arsitektur (misal migrasi EC2 x86 ke Graviton arm64 atau container Fargate). |
| **Metric Resolution** | **High-Resolution (1s)** | **Standard Resolution (1m)** | 1-second metric resolution memungkinkan deteksi spike mikro secara presisi, namun menghasilkan biaya tambahan ($0.30 per high-resolution metric/bulan) dan overhead transmisi data yang lebih intensif. |

---

## 13. When To Use
- Gunakan **CloudWatch Metric Math** saat metrik mentah tunggal (*single raw metric*) tidak mencerminkan Service Level Indicator (SLI) bisnis. Sangat esensial untuk rasio perbandingan (Success/Error ratio, Cache Hit/Miss ratio).
- Gunakan **AWS X-Ray** pada arsitektur microservices terdistribusi, event-driven architecture (EventBridge, SQS, SNS, Lambda), dan API multi-tier dengan dependensi downstream yang banyak.
- Gunakan **AWS CloudTrail dengan Log File Validation** pada semua lingkungan production yang diwajibkan memenuhi audit kepatuhan regulasi finansial, perbankan, kesehatan, atau perlindungan data pribadi.
- Terapkan **Infracost** di tahap pipeline pull-request jika Anda memiliki tim engineer multi-skuad independen yang kerap mem-provision resource cloud via Terraform tanpa supervisi sentral terus-menerus.

---

## 14. When NOT To Use
- Jangan gunakan **CloudWatch Logs** sebagai platform analisis log berbasis analitik ad-hoc bervolume petabyte harian yang memerlukan aggregasi full-text search kompleks secara real-time jangka panjang; untuk skenario tersebut, alihkan streaming log ke OpenSearch Service atau gunakan S3 dengan AWS Athena.
- Jangan gunakan **CloudWatch Alarms pada metrik instan CPU** sebagai trigger tunggal auto-scaling mikroservis web; gunakan metrik latensi p90/p99 atau *RequestCountPerTarget* ALB yang merefleksikan user experience secara langsung.
- Jangan membeli **EC2 Reserved Instances / Savings Plans 3 Tahun All-Upfront** untuk workload eksperimental, MVP startup yang arsitektur dasarnya belum teruji matang, atau resource yang direncanakan akan di-decommission dalam waktu dekat (< 6 bulan).

---

## 15. Common Mistakes
1. **Unindexed / Unstructured Logging**: Memancarkan log aplikasi dalam plain-text string multiline tak terstruktur. Hal ini melipatgandakan waktu query di CloudWatch Logs Insights dan menyulitkan ekstraksi field otomatis.
2. **Failure to Enable Log File Validation**: Mengaktifkan CloudTrail tanpa Log File Validation. Jika penyerang menyusup ke lingkungan AWS dan mengompromikan bucket S3, mereka dapat mengubah isi log tanpa meninggalkan jejak hash tampered integrity.
3. **Alerting on Symptoms Instead of SLOs**: Mengonfigurasi ratusan alarm pada utilisasi CPU, memory, dan disk queue secara individual. Ini memicu *alert fatigue* parah di mana tim SRE mengabaikan alarm kritis saat terjadi outage nyata.
4. **Ignoring Data Events Cost in CloudTrail**: Mengaktifkan CloudTrail S3 Data Events untuk bucket yang memproses miliaran objek per hari tanpa filtering prefix. Biaya CloudTrail dapat membengkak hingga puluhan ribu dollar hanya dari event ingestion.
5. **Overcommitting FinOps Plans**: Membeli Savings Plans berdasarkan utilisasi puncak (*peak utilization*) alih-alih beban kerja dasar (*baseline demand*), sehingga kapasitas komitmen tidak terutilisasi secara efisien saat jam sepi.

---

## 16. Best Practices
1. **Structure Everything as JSON**: Paksa seluruh output aplikasi memancarkan log berformat JSON terstruktur yang memuat atribut: `timestamp`, `level`, `trace_id`, `service`, `user_id`, dan `latency_ms`.
2. **Implement Composite Alarms**: Kelompokkan alarm infrastruktur (low-level) dan alarm bisnis (high-level) ke dalam Composite Alarm untuk memastikan notifikasi on-call hanya berdering saat degradasi berdampak langsung pada pelanggan.
3. **Tag-First Governance Architecture**: Terapkan AWS Organizations SCP untuk memblokir aksi `ec2:RunInstances`, `s3:CreateBucket`, dan provisioning resource database jika request tidak menyertakan tag wajib FinOps (`Environment`, `CostCenter`, `Project`).
4. **Target 75% - 85% Savings Plans Coverage**: Pertahankan komitmen Compute Savings Plans pada tingkat 75% hingga 85% dari beban kerja dasar konstan. Tangani sisa lonjakan trafik elastis (*spikes*) menggunakan instance On-Demand atau Spot Instances.
5. **Shift-Left Cost Estimation**: Wajibkan integrasi Infracost di CI/CD pull request gatekeeper. Berikan status *failure* jika commit meningkatkan estimasi bulanan lebih dari batas toleransi yang disepakati tanpa persetujuan eksplisit tim FinOps.

---

## 17. Troubleshooting

### Problem 1: X-Ray Traces Tidak Muncul di Service Map
- **Penyebab**: Konteks header HTTP `X-Amzn-Trace-Id` terputus di level reverse proxy, atau service downstream tidak meneruskan header context ke panggilan berikutnya.
- **Investigasi**: Jalankan `curl -Iv -H "X-Amzn-Trace-Id: Root=1-5759e988-bd862e3fe1be46a994272767" <endpoint>` dan verifikasi apakah daemon X-Ray menerima tracing packet pada UDP port 2000.
- **Solusi**: Pastikan IAM Role memiliki policy `arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess` dan aplikasi mengonfigurasi interceptor/middleware HTTP client untuk meneruskan header tracing.

### Problem 2: Tag Alokasi Biaya (Cost Allocation Tags) Tidak Muncul di AWS Cost Explorer
- **Penyebab**: Penambahan tag pada resource AWS tidak secara otomatis mengaktifkannya sebagai dimensi filter di Cost Explorer.
- **Investigasi**: Periksa menu AWS Billing -> Cost Allocation Tags. Status tag kemungkinan masih *Inactive*.
- **Solusi**: Tandai tag yang bersangkutan (misal: `CostCenter`, `Environment`) dan klik **Activate**. Perlu diingat bahwa AWS membutuhkan waktu hingga 24 jam untuk mulai memproses data tag pada mesin kalkulasi Cost Explorer.

### Problem 3: CloudWatch Logs Insights Lambat dan Mahal saat Menjalankan Query
- **Penyebab**: Query memindai volume data terabyte tanpa pembatasan rentang waktu atau penargetan sub-log stream yang tepat.
- **Investigasi**: Tinjau metrik `BytesScanned` pada hasil execution query CloudWatch Logs Insights.
- **Solusi**: Persempit window waktu query (misal: kurangi dari 7 hari menjadi rentang 15 menit insiden). Gunakan filter `@logStream` spesifik atau indeks log menggunakan subscription filters yang mendistribusikan data ke storage khusus analitik.

---

## 18. Exercise
Selesaikan skenario berikut untuk menguji pemahaman Anda:
1. Tulis query CloudWatch Logs Insights yang mengambil persentil ke-95 (`p95`) dan persentil ke-99 (`p99`) dari field respon latensi (`request_duration_ms`), dikelompokkan berdasarkan field `api_endpoint` untuk log dengan kode status HTTP di atas `400` dalam rentang waktu 3 jam terakhir.
2. Hitung persentase penghematan biaya jika sebuah workload berjalan dengan 10 instance `c6i.2xlarge` Linux di region `ap-southeast-1` ($0.408/jam per instance On-Demand) dialihkan secara penuh ke Compute Savings Plans 3 Tahun All-Upfront (dengan diskon ekuivalen 54%). Berapa penghematan absolut per bulan (asumsi 730 jam per bulan)?

---

## 19. Challenge
Rancang arsitektur telemetri mandiri dan tahan gangguan:
- Buat sebuah sistem pemantauan berbasis Terraform yang mengumpulkan log VPC Flow Logs dari 3 VPC production yang berbeda, memfilter paket yang ditolak (`REJECT`), mempublikasikan metrik kustom ke CloudWatch dengan Storage Resolution 1 detik jika jumlah reject melampaui 1.000 paket/menit, dan secara bersamaan memicu automasi AWS Network Firewall untuk memblokir IP penyerang menggunakan Lambda, seraya memastikan seluruh biaya pemanggilan Lambda dicatat di bawah Cost Allocation Tag `Security-Remediation`.

---

## 20. Summary
- **Observabilitas Modern** melampaui monitoring reaktif dengan memadukan metrics, structured logs, dan distributed traces ke dalam suatu ekosistem kontekstual yang holistik.
- **CloudWatch Metric Math & Composite Alarms** adalah senjata utama SRE untuk mengatasi fenomena *alert fatigue*, memungkinkan pembuatan alarm yang selaras langsung dengan Service Level Agreements (SLA) dan Service Level Objectives (SLO) bisnis.
- **AWS CloudTrail** menyediakan landasan immutable auditing yang esensial bagi postur tata kelola dan forensik keamanan melalui integritas kriptografis Log File Validation.
- **FinOps Terintegrasi** bukan merupakan agenda pemotongan anggaran semata, melainkan akselerator efisiensi rekayasa. Pendekatan ini memanfaatkan visibilitas biaya, komitmen terukur melalui Savings Plans, dan pergeseran *shift-left* analisis estimasi biaya ke pipeline CI/CD via Infracost untuk mencegah *bill shock* di skala cloud enterprise.