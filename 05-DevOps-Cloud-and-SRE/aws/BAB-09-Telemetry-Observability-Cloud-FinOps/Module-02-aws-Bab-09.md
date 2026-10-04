# Kurikulum Rekayasa Cloud Enterprise: AWS Observability Lanjutan & Cloud FinOps Engineering

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

*   **Menganalisis & Mengarsitekturkan Telemetri Skala Besar**: Merancang arsitektur telemetri terdistribusi multi-region, multi-account menggunakan *AWS Distro for OpenTelemetry* (ADOT), *Embedded Metric Format* (EMF), dan *AWS X-Ray*.
*   **Mengeliminasi Metric Throttling & Mengoptimasi Ingestion Throughput**: Mengganti panggilan API sinkron `PutMetricData` yang rentan terhadap *rate limit* dengan asynchronous metric ingestion berbasis EMF berkinerja tinggi.
*   **Membangun Engine Korelasi Observabilitas Terpusat**: Mengintegrasikan logs, metrics, dan distributed tracing end-to-end melintasi batas VPC, akun AWS, dan lingkungan container (EKS/ECS).
*   **Mendesain Sistem Deteksi Insiden Berakurasi Tinggi**: Mengimplementasikan *CloudWatch Metric Math* dan *Composite Alarms* untuk memitigasi fenomena *alert fatigue* dan badai notifikasi (*alert storms*).
*   **Mengonstruksi Automated FinOps Data Lake**: Membangun pipeline analitik biaya otomatis menggunakan *Cost and Usage Report (CUR) 2.0*, *AWS Glue*, dan *Amazon Athena* untuk menghitung metrik *Unit Economics* per penyewa (*tenant*) atau per transaksi.
*   **Mengevaluasi Trade-off Arsitektur FinOps & Observabilitas**: Mengambil keputusan berbasis data terkait pemilihan sampling traces (*head-based* vs *tail-based*), retensi log vs biaya penyimpanan *cold storage*, serta alokasi komputasi berbasis *Savings Plans* dan *Spot instances*.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib menguasai:

1.  **Infrastruktur AWS Tingkat Menengah**: Pemahaman mendalam tentang AWS IAM (Resource-based policy, IAM Roles for Service Accounts/IRSA), VPC networking (VPC Endpoints, Peering, Transit Gateway), dan deployment container (Amazon EKS atau Amazon ECS).
2.  **Infrastructure as Code (IaC)**: Kemampuan menulis dan memodifikasi modul Terraform HCL tingkat lanjut (ekspresi dinamis, `for_each`, provider multi-region/multi-account).
3.  **Dasar Telemetri & Linux**: Pemahaman format log JSON, konsep *distributed tracing* (Trace ID, Span ID, W3C Trace Context propagation), dan protokol transmisi log/metrik (OTLP, statsd).
4.  **SQL & Data Querying**: Kemampuan menulis query SQL analitis (window functions, aggregation, subqueries) pada Amazon Athena / Presto engine.

---

## 3. Concept & Internal Architecture

### 3.1 Pipeline Ingestion Telemetri Skala Enterprise: Dari `PutMetricData` ke EMF & ADOT

Pada skala produksi (ratusan juta transaksi/hari), memanggil API `cloudwatch:PutMetricData` secara langsung dari kode aplikasi menimbulkan masalah besar:

1.  **Latensi Tambahan**: Panggilan HTTPS sinkron ke endpoint CloudWatch memblokir alur eksekusi aplikasi jika tidak dikelola oleh thread pool terisolasi.
2.  **API Rate Limiting (Throttling)**: API `PutMetricData` memiliki limit default (1.000 TPS) yang dapat menghambat ingestion metrik saat beban puncak (*peak load*).
3.  **Biaya Tinggi**: CloudWatch Metrics ditagih berdasarkan jumlah metrik kustom per bulan. Ingestion jutaan metrik berdimensi tinggi memicu ledakan biaya (*cost explosion*).

```
[ Traditional Sync Approach: Rawan Latensi & Throttling ]
App Code ---> (HTTPS PutMetricData Synchronous) ---> [ CloudWatch API ] 
                  |--> High Latency Overhead
                  |--> Hard Limit (ThrottlingException)
                  |--> Mahal ($0.30 per custom metric/bln)

[ Modern Asynchronous EMF Approach: Zero-Latency Impact ]
App Code ---> (stdout: Structured JSON Log)
                    |
                    v
            [ Local Collector Agent ] (Fluent Bit / ADOT)
                    |
                    v (Batching / Compression)
            [ CloudWatch Logs Ingestion Engine ]
                    |
                    v (Asynchronous Internal Metric Extraction)
            [ CloudWatch Metrics Store ] (EMF Metric Terbentuk Otomatis)
```

**Mekanisme Internal CloudWatch Embedded Metric Format (EMF):**
Aplikasi menulis log terstruktur JSON ke `stdout` yang mematuhi skema EMF (`_aws` root attribute). Agen telemetri (misal: AWS Distro for OpenTelemetry atau Fluent Bit) membaca log ini dan mengirimkannya ke Amazon CloudWatch Logs melalui panggilan batch `PutLogEvents`. 

Engine ingestion internal CloudWatch Logs membedah payload JSON ini di tingkat infrastruktur AWS, mengekstrak metrik dan dimensinya, lalu memasukkannya ke CloudWatch Metrics secara asinkron. **Hasilnya**: Tidak ada panggilan API `PutMetricData`, latensi aplikasi tetap mendekati nol (*in-memory stdout write*), dan log mentah sekaligus tersedia untuk audit/forensik.

### 3.2 Arsitektur Koleksi OpenTelemetry: AWS Distro for OpenTelemetry (ADOT)

ADOT adalah distribusi bawaan AWS dari proyek Cloud Native Computing Foundation (CNCF) OpenTelemetry. ADOT beroperasi dalam dua pola utama pada Kubernetes (EKS):

*   **DaemonSet Mode (Node Agent)**: Berjalan di setiap node untuk mengumpulkan node-level metrics (e.g., node_exporter, stats cgroup container) dan menerima span/metrics dari aplikasi lokal via port localhost (OTLP gRPC 4317 / HTTP 4318).
*   **Sidecar Mode**: Diinjeksikan ke dalam Pod aplikasi untuk menangani trace dan custom business metrics dengan isolasi resource tinggi.

```
+------------------------------------------------------------------------------------+
| Pod Aplikasi (Kubernetes Worker Node)                                              |
|                                                                                    |
|  +--------------------------------+       +-------------------------------------+  |
|  | Container: App (Go / Java)     |       | Container: ADOT Collector (Sidecar) |  |
|  |                                |       |                                     |  |
|  | [ OpenTelemetry SDK ]          | OTLP  | [ Receivers: otlp (grpc/http) ]     |  |
|  |         |                      |------>|               |                     |  |
|  |         v Trace/Span Context   | :4317 | [ Processors: batch, memory_limiter]|  |
|  | [ W3C Traceparent Header ]     |       |               |                     |  |
|  +--------------------------------+       +---------------+---------------------+  |
+-----------------------------------------------------------|------------------------+
                                                            | AWS SigV4
                              +-----------------------------+-----------------------------+
                              |                                                           |
                              v                                                           v
            +------------------------------------+                      +------------------------------------+
            |          AWS X-Ray Service         |                      |        CloudWatch Logs/Metrics     |
            | - Distributed Trace Graph          |                      | - EMF Parsed Custom Metrics        |
            | - Tail-based & Head Sampling Rules |                      | - Performance Container Insights   |
            +------------------------------------+                      +------------------------------------+
```

### 3.3 Engine Analitik FinOps: Arsitektur Data Lake CUR 2.0 & Korelasi Metrik

Observabilitas FinOps enterprise menuntut korelasi antara **biaya infrastruktur riil** dan **metrik bisnis** (contoh: *Cost-per-API-Request* atau *Cost-per-Active-Tenant*).

```
+-------------------------+
| AWS Organizations       |
| Payer / Management Acct |
+-------------------------+
             |
             | 1. Export Harian/Jam (Parquet Format)
             v
+-------------------------------------------------------+
| S3 Bucket: Centralized CUR 2.0 Destination           |
| s3://enterprise-cur-lake/cur-v2/year=YYYY/month=MM/   |
+-------------------------------------------------------+
             |
             | 2. Notifikasi S3 ObjectCreated (EventBridge)
             v
+-------------------------+
| AWS Glue Crawler        | ---- 3. Update Partisi & Skema Metastore
+-------------------------+
             |
             v
+-------------------------------------------------------+
| AWS Glue Data Catalog                                 |
| Database: `finops_cost_reporting`                     |
| Table: `cur_cost_and_usage_data`                      |
+-------------------------------------------------------+
             ^
             | 4. Analisis Biaya SQL Terfederasi
+-------------------------------------------------------+
| Amazon Athena Engine (Presto/Trino)                   |
| - Query Tag Allocation (`resource_tags_user_tenant_id`)|
| - Join Metric Telemetri (CloudWatch via Athena Data   |
|   Source Connector)                                   |
+-------------------------------------------------------+
             |
             v
+-------------------------------------------------------+
| Visualisasi & Alerting:                               |
| - Amazon QuickSight Dashboard                         |
| - Budget Anomaly Detection via AWS Lambda             |
+-------------------------------------------------------+
```

---

## 4. Why & What

| Dimensi | Pendekatan Reaktif (Tradisional) | Pendekatan Enterprise Observability & FinOps |
| :--- | :--- | :--- |
| **Metode Ingestion Metrik** | Direct API call `cloudwatch:PutMetricData` per event bisnis | Asynchronous logging via Embedded Metric Format (EMF) & ADOT |
| **Distributed Tracing** | Log grep manual / isolated logs per container pod | Distributed W3C Trace Context propagation dengan AWS X-Ray & OTLP |
| **Deteksi Kegagalan** | Single-metric alert threshold (e.g., CPU > 80% langsung paging engineer) | Composite Alarms + Metric Math (e.g., Latency p99 > 2s AND Error Rate 5xx > 5% AND RequestCount > 100) |
| **Alokasi Biaya (FinOps)** | Estimasi manual bulanan berbasis tagihan global invoice | Real-time automated data lake CUR 2.0 di Athena dengan Unit Economics per tenant |
| **Tata Kelola Tagging** | Tagging opsional, audit ad-hoc | Strict Enforcement via AWS Organizations Tag Policies & SCPs |

*   **What is EMF?** Spesifikasi JSON terstruktur yang memungkinkan CloudWatch Logs mengekstrak metrik numerik berdimensi tanpa overhead latensi jaringan pada jalur kritis kode.
*   **What is AWS Distro for OpenTelemetry (ADOT)?** Distribusi open-source yang aman dan didukung resmi oleh AWS, berbasis OpenTelemetry Collector, yang dioptimalkan untuk memancarkan metrik dan trace ke sistem AWS (CloudWatch, X-Ray) maupun sistem pihak ketiga (Datadog, Dynatrace, Prometheus) secara serentak (*fan-out*).
*   **What is CUR 2.0?** Versi modern dari AWS Cost and Usage Report yang terintegrasi langsung dengan skema AWS Data Exports, mengekspor rincian data penagihan granular tingkat resource per jam dalam format Apache Parquet yang dioptimalkan untuk query analitik.

---

## 5. How (Workflow Detail)

### 5.1 End-to-End Tracing & Telemetry Propagation Lifecycle
1.  **Request Ingestion**: Klien luar mengirimkan HTTP Request dengan header tracing standar W3C (`traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`).
2.  **Edge / Gateway Processing**: AWS Application Load Balancer (ALB) atau API Gateway mengekstrak header atau menyuntikkan header `X-Amzn-Trace-Id` jika tidak tersedia.
3.  **Application Ingestion**: SDK OpenTelemetry pada aplikasi Go/NodeJS/Java menangkap context trace dari header HTTP.
4.  **Local Span Exporting**: Aplikasi mencatat span operasi database, HTTP call downstream, dan EMF JSON metric. Payload dipancarkan secara asinkron ke ADOT Collector yang berjalan di `localhost:4317` (gRPC).
5.  **Collector Processing**: ADOT Collector memproses metrik dan tracing data:
    *   Menerapkan *Tail-based Sampling Processor* (misal: simpan 100% trace yang menghasilkan HTTP 5xx atau latensi > 1500ms; simpan 1% trace normal HTTP 200).
    *   Membungkus metadata AWS (Region, Task ARN, EKS Pod Name, Namespace) menggunakan `resourcedetection` processor.
6.  **Fan-out Forwarding**: Trace diekspor ke endpoint AWS X-Ray, sedangkan payload EMF diteruskan ke AWS CloudWatch Logs.

### 5.2 Enterprise FinOps Reporting & Unit Economics Calculation Workflow
1.  **Billing Data Emission**: AWS Billing Engine mengekspor raw usage record setiap 6-12 jam ke Amazon S3 bucket terenkripsi KMS dalam format Parquet, dipartisi berdasarkan tahun dan bulan.
2.  **Catalog Synchronization**: S3 Event notification memicu AWS Glue Crawler untuk memperbarui partisi tabel metastore tanpa intervensi manual.
3.  **Telemetry Data Aggregation**: CloudWatch Metric Math secara otomatis menghitung `Total_API_Invocations` per customer ID dalam rentang waktu yang sama.
4.  **Unit Cost Query Execution**: Athena menjalankan query analitik gabungan:
    $$\text{Unit Cost per Request} = \frac{\sum(\text{Amortized Cost of Service Pods} + \text{Shared DB Cost allocated})}{\text{Total Successful Invocations (dari Telemetri)}}$$
5.  **Continuous Governance**: Jika metrik unit cost melonjak melebihi deviasi standar harian (>20%), EventBridge mendeteksi hasil query Athena dan memicu notifikasi ke tim Engineering terkait.

---

## 6. Analogy & Diagram ASCII

### Analogi: Sistem Radar & Black Box Pesawat Ruang Angkasa vs Telemetri Enterprise

Bayangkan sebuah armada pesawat kargo luar angkasa:
1.  **Direct `PutMetricData`** = Pilot mengirim sinyal radio langsung ke markas komando bumi untuk setiap detik rotasi mesin. Ketika ribuan pesawat bicara bersamaan, frekuensi radio penuh (*throttled*), dan pilot teralihkan dari navigasi (*high latency*).
2.  **Embedded Metric Format (EMF)** = Pilot menulis pembacaan mesin ke dalam *Black Box Recorder* pesawat (asynchronous stdout). Kotak hitam memancarkan rekaman terenkripsi dalam batch besar saat satelit relai lewat. Engine markas komando membaca kotak hitam, secara otomatis memisahkan data diagnostik dan mencatat indikator metrik tanpa pilot kehilangan fokus navigasi.
3.  **Composite Alarms** = Bukan membunyikan sirene evakuasi hanya karena satu sensor panas mesin menyala (bisa jadi sensor rusak). Sirene evakuasi hanya berbunyi jika: *Sensor Suhu Mesin > 1000°C* **DAN** *Tekanan Bahan Bakar Turun Drastis* **DAN** *Alarm Oksigen Kabin Aktif*.
4.  **Cloud FinOps (CUR 2.0)** = Mencatat konsumsi bahan bakar bukan per total galon kapal induk, melainkan menghitung tepat berapa gram cairan bahan bakar yang terbakar untuk mengantar kargo milik *Client A* vs *Client B* sampai ke orbit tujuan.

### Comprehensive Telemetry & FinOps Architecture Flow

```
+---------------------------------------------------------------------------------------------------------+
| AWS MULTI-ACCOUNT / MULTI-REGION ENVIRONMENT                                                            |
+---------------------------------------------------------------------------------------------------------+

  [ ACCOUNT: Workload (EKS Production) ]
   +-----------------------------------------------------------------------------+
   | Kubernetes Worker Node                                                      |
   |                                                                             |
   |  [ Pod: Checkout-Service ]                                                  |
   |   - OpenTelemetry Instrumentation                                           |
   |   - Generates OTLP Spans (W3C context)                                      |
   |   - Emits EMF JSON to stdout                                                |
   |        |                                                                    |
   |        | (Localhost pipe / OTLP gRPC)                                       |
   |        v                                                                    |
   |  [ Pod: ADOT Collector DaemonSet ]                                          |
   |   - Memory Limiter                                                          |
   |   - Tail Sampling Processor (Error: 100%, Slow: 100%, Normal: 1%)           |
   |   - SigV4 Authenticator                                                     |
   +--------|----------------------------------|---------------------------------+
            |                                  |
            | Export Spans (HTTPS:443)         | Export EMF Logs (HTTPS:443)
            v                                  v
   +--------------------+             +-----------------------------------------+
   | AWS X-Ray Core API |             | CloudWatch Logs: `/aws/eks/checkout`    |
   +--------------------+             +-----------------------------------------+
            |                                  |
            | Service Graph                    | Internal CloudWatch Extraction
            v                                  v
   +--------------------+             +-----------------------------------------+
   | AWS X-Ray Console  |             | CloudWatch Metrics Engine               |
   | (Dependency Tree)  |             | - Custom EMF Dimensions                 |
   +--------------------+             +-----------------------------------------+
                                                       |
                                                       | Metric Math Evaluation
                                                       v
                                      +-----------------------------------------+
                                      | CloudWatch Composite Alarm              |
                                      | (Lat > 2s AND Err > 5% AND Traffic > 50)|
                                      +-----------------------------------------+
                                                       |
                                                       | Alarm State Change
                                                       v
                                      +-----------------------------------------+
                                      | Amazon SNS Topic -> PagerDuty / Slack   |
                                      +-----------------------------------------+

  [ ACCOUNT: Central Payer / Billing Management ]
   +-----------------------------------------------------------------------------+
   | AWS Organizations Invoicing & Data Export Engine                            |
   +-----------------------------------------------------------------------------+
            |
            | Scheduled Parquet Export (Hourly partition)
            v
   +-----------------------------------------------------------------------------+
   | Amazon S3: `s3://corp-finops-cur-lake-2026/`                                |
   +-----------------------------------------------------------------------------+
            |
            | S3 Event Notification
            v
   +---------------------------------------+      +------------------------------+
   | AWS Glue Crawler (Metadata discovery) | ---> | AWS Glue Data Catalog        |
   +---------------------------------------+      +------------------------------+
                                                                 |
                                                                 | Partition Schema
                                                                 v
                                                  +------------------------------+
                                                  | Amazon Athena                |
                                                  | Federated FinOps Engine      |
                                                  +------------------------------+
                                                                 |
                                                                 | Analytical SQL
                                                                 v
                                                  +------------------------------+
                                                  | Unit Economics Metric:       |
                                                  | Cost per Tenant / API Call   |
                                                  +------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: High-Throughput Ingestion via Embedded Metric Format (EMF)

Berikut implementasi kode Go murni untuk memancarkan metrik bisnis kustom menggunakan Embedded Metric Format tanpa library eksternal yang membebani alokasi memori.

```go
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"time"
)

// EMFMetadata mendefinisikan struktur _aws sesuai spesifikasi resmi CloudWatch EMF
type EMFMetadata struct {
	Timestamp int64                   `json:"Timestamp"`
	CloudWatchMetrics []MetricDirective `json:"CloudWatchMetrics"`
}

type MetricDirective struct {
	Namespace  string          `json:"Namespace"`
	Dimensions [][]string      `json:"Dimensions"`
	Metrics    []MetricElement `json:"Metrics"`
}

type MetricElement struct {
	Name string `json:"Name"`
	Unit string `json:"Unit"`
}

// PaymentEMFPayload menggabungkan data log kontekstual dengan metrik numerik
type PaymentEMFPayload struct {
	EMFMetadata `json:"_aws"`
	
	// Dimensi (Dimensions)
	Environment string `json:"Environment"`
	TenantID    string `json:"TenantID"`
	PaymentMode string `json:"PaymentMode"`

	// Metrik (Metrics)
	ProcessingLatency float64 `json:"ProcessingLatency"`
	ProcessedAmount   float64 `json:"ProcessedAmount"`
	TransactionCount  int     `json:"TransactionCount"`

	// Konteks Log Opsional (Tersedia untuk query CloudWatch Insights)
	TransactionID string `json:"TransactionId"`
	TraceID       string `json:"TraceId"`
}

func main() {
	start := time.Now()
	
	// Simulasi logika bisnis proses transaksi
	tenantID := "tenant-enterprise-prod-007"
	paymentMethod := "CREDIT_CARD"
	amount := 250.75
	traceID := "1-5f84c7a1-a723e862423984d723"

	time.Sleep(45 * time.Millisecond) // Simulasi eksekusi downstream
	duration := float64(time.Since(start).Milliseconds())

	// Konstruksi skema EMF
	payload := PaymentEMFPayload{
		EMFMetadata: EMFMetadata{
			Timestamp: time.Now().UnixMilli(),
			CloudWatchMetrics: []MetricDirective{
				{
					Namespace: "EnterpriseFinOps/Payments",
					Dimensions: [][]string{
						{"Environment", "TenantID"},
						{"Environment", "PaymentMode"},
					},
					Metrics: []MetricElement{
						{Name: "ProcessingLatency", Unit: "Milliseconds"},
						{Name: "ProcessedAmount", Unit: "None"},
						{Name: "TransactionCount", Unit: "Count"},
					},
				},
			},
		},
		Environment:       "Production",
		TenantID:          tenantID,
		PaymentMode:       paymentMethod,
		ProcessingLatency: duration,
		ProcessedAmount:   amount,
		TransactionCount:  1,
		TransactionID:     "tx-9923847294",
		TraceID:           traceID,
	}

	// Serialisasi ke stdout secara asinkron tanpa memblokir runtime
	jsonEncoder := json.NewEncoder(os.Stdout)
	if err := jsonEncoder.Encode(payload); err != nil {
		fmt.Fprintf(os.Stderr, "Gagal meng-encode EMF log: %v\n", err)
	}
}
```

### 7.2 Practical Example: Enterprise Production Architecture (Terraform)

Arsitektur produksi ini mengonfigurasikan:
1.  **ADOT Collector** di EKS dengan ServiceAccount IAM (IRSA).
2.  **CloudWatch Composite Alarm** multi-faktor.
3.  **AWS Athena Database & Workgroup** untuk CUR 2.0 Data Engine.

```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
  }
}

variable "environment" {
  type    = string
  default = "production"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "eks_cluster_oidc_issuer" {
  type        = string
  description = "URL OIDC Provider dari EKS Cluster tanpa https://"
  default     = "oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE8392019348103"
}

# ==============================================================================
# 1. IAM ROLE FOR SERVICE ACCOUNT (IRSA) - ADOT COLLECTOR
# ==============================================================================
data "aws_iam_policy_document" "adot_assume_role_policy" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"

    condition {
      test     = "StringEquals"
      variable = "${var.eks_cluster_oidc_issuer}:sub"
      values   = ["system:serviceaccount:opentelemetry:adot-collector"]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.eks_cluster_oidc_issuer}:aud"
      values   = ["sts.amazonaws.com"]
    }

    principals {
      type        = "Federated"
      identifiers = ["arn:aws:iam::123456789012:oidc-provider/${var.eks_cluster_oidc_issuer}"]
    }
  }
}

resource "aws_iam_role" "adot_collector_irsa" {
  name               = "adot-collector-${var.environment}-role"
  assume_role_policy = data.aws_iam_policy_document.adot_assume_role_policy.json
}

# Memberikan hak akses pengiriman traces (X-Ray) dan metrics/logs (CloudWatch)
resource "aws_iam_role_policy_attachment" "adot_xray_policy" {
  role       = aws_iam_role.adot_collector_irsa.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}

resource "aws_iam_role_policy_attachment" "adot_cloudwatch_policy" {
  role       = aws_iam_role.adot_collector_irsa.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

# ==============================================================================
# 2. ADVANCED CLOUDWATCH METRIC ALARMS & COMPOSITE ALARM
# ==============================================================================
resource "aws_sns_topic" "critical_incident_notifications" {
  name              = "critical-incident-${var.environment}-topic"
  kms_master_key_id = "alias/aws/sns"
}

# Alarm 1: Latensi p99 Tinggi
resource "aws_cloudwatch_metric_alarm" "high_p99_latency" {
  alarm_name          = "API-High-p99-Latency-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = 2000 # 2000ms
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "e1"
    expression  = "m1"
    label       = "ExecutionLatencyP99"
    return_data = "true"
  }

  metric_query {
    id = "m1"
    metric {
      metric_name = "ProcessingLatency"
      namespace   = "EnterpriseFinOps/Payments"
      period      = 60
      stat        = "p99"
      dimensions = {
        Environment = "Production"
      }
    }
  }
}

# Alarm 2: Error Rate Tinggi (Dihitung Menggunakan Metric Math)
resource "aws_cloudwatch_metric_alarm" "high_error_percentage" {
  alarm_name          = "API-High-Error-Percentage-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = 5 # 5% error rate
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "e1"
    expression  = "(mErrors / mTotal) * 100"
    label       = "CalculatedErrorRate"
    return_data = "true"
  }

  metric_query {
    id = "mErrors"
    metric {
      metric_name = "5XXError"
      namespace   = "AWS/ApplicationELB"
      period      = 60
      stat        = "Sum"
      dimensions = {
        LoadBalancer = "app/prod-alb/50dc6c495c0c9188"
      }
    }
  }

  metric_query {
    id = "mTotal"
    metric {
      metric_name = "RequestCount"
      namespace   = "AWS/ApplicationELB"
      period      = 60
      stat        = "Sum"
      dimensions = {
        LoadBalancer = "app/prod-alb/50dc6c495c0c9188"
      }
    }
  }
}

# Composite Alarm: Menghilangkan False Positives
# Hanya memicu pager jika Latensi p99 Tinggi DAN Error Rate Tinggi terjadi bersamaan
resource "aws_cloudwatch_composite_alarm" "service_critical_composite_alarm" {
  alarm_name        = "Composite-CheckoutService-Degraded-${var.environment}"
  alarm_description = "Layanan Checkout mengalami degradasi parah: Latensi p99 > 2s DAN Error Rate > 5%"

  alarm_rule = "ALARM(${aws_cloudwatch_metric_alarm.high_p99_latency.alarm_name}) AND ALARM(${aws_cloudwatch_metric_alarm.high_error_percentage.alarm_name})"

  alarm_actions = [aws_sns_topic.critical_incident_notifications.arn]
  ok_actions    = [aws_sns_topic.critical_incident_notifications.arn]
}

# ==============================================================================
# 3. ENTERPRISE FINOPS ATHENA DATA ENGINE
# ==============================================================================
resource "aws_s3_bucket" "athena_cur_results" {
  bucket        = "finops-athena-query-results-${var.environment}-123456789012"
  force_destroy = false
}

resource "aws_s3_bucket_server_side_encryption_configuration" "athena_results_encryption" {
  bucket = aws_s3_bucket.athena_cur_results.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_athena_workgroup" "finops_engine_workgroup" {
  name        = "finops-analysis-workgroup"
  description = "Dedicated workgroup for Cost and Usage Data Lake analytics"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = 10737418240 # Limit 10 GB scanning per query untuk kontrol biaya

    result_configuration {
      output_location = "s3://${aws_s3_bucket.athena_cur_results.bucket}/output/"
      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }
}

resource "aws_glue_catalog_database" "finops_catalog" {
  name        = "finops_cost_intelligence"
  description = "Katalog data penagihan CUR 2.0 dan alokasi biaya internal"
}
```

### 7.3 Konfigurasi ADOT Collector DaemonSet (`otel-collector-config.yaml`)

Konfigurasi berikut menunjukkan integrasi OTel Pipeline untuk membedah W3C Trace, tail-sampling, dan routing ke X-Ray & CloudWatch Logs.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: adot-collector-config
  namespace: opentelemetry
data:
  collector.yaml: |
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

      batch:
        send_batch_size: 8192
        timeout: 5s

      # Tail-based Sampling: Hanya simpan jejak transaksi yang bermasalah atau sampel kecil trace sukses
      tail_sampling:
        decision_wait: 10s
        expected_new_traces_per_sec: 2000
        policies:
          - name: latency-policy
            type: numeric_attribute
            numeric_attribute:
              key: http.status_code
              value_condition:
                greater_than_or_equal: 500
          - name: probabilistic-sample
            type: probabilistic
            probabilistic:
              sampling_percentage: 1.0

      resourcedetection:
        detectors: [env, eks, ec2]
        timeout: 2s

    exporters:
      awsxray:
        region: us-east-1
      
      awscloudwatchlogs:
        log_group_name: "/aws/eks/workload-telemetry"
        log_stream_name: "adot-stream"
        region: us-east-1

    service:
      pipelines:
        traces:
          receivers: [otlp]
          processors: [memory_limiter, tail_sampling, resourcedetection, batch]
          exporters: [awsxray]
        metrics:
          receivers: [otlp]
          processors: [memory_limiter, resourcedetection, batch]
          exporters: [awscloudwatchlogs]
```

---

## 8. Real World Case Study: E-Commerce Scale Ingestion Breakdown & FinOps Overhaul

### Konteks & Skala Sistem
*   **Perusahaan**: PayStream Asia (Platform Payment Gateway).
*   **Volume Transaksi**: Rata-rata 180 Juta transaksi per hari; beban puncak 9.000 TPS.
*   **Arsitektur**: 65 Microservices berbasis Go dan Java di 4 EKS Cluster (1.200 Node EC2 m5.2xlarge).

### Titik Kegagalan (The Incident)
Saat kampanye diskon nasional (11.11), seluruh platform mengalami lonjakan latensi payment approval dari 180ms menjadi 14 detik, mengakibatkan tingkat kegagalan pembayaran mencapai 38%.

1.  **Metric Throttling & Bottleneck**: Microservices mengonfigurasi SDK untuk memanggil `PutMetricData` secara sinkron guna mencatat volume transaksi per merchant. Panggilan API ini menabrak batas kuota akun CloudWatch API (1.000 TPS) secara instan.
2.  **Thread Pool Starvation**: Driver HTTP pool Go dan Java kehabisan connection pool karena koneksi ke `monitoring.us-east-1.amazonaws.com` tertahan oleh *exponential backoff retry*. Thread aplikasi terkunci (*starved*), memicu antrean di seluruh ingress controller.
3.  **Alert Fatigue Menghancurkan Komunikasi**: Ratusan alarm CloudWatch individual (berbasis single-metric CPU > 75%) menyala serentak. Tim on-call menerima 1.400 notifikasi PagerDuty dalam 15 menit, mengaburkan akar masalah sebenarnya (*cascading failure* pada connection pool, bukan degradasi CPU).
4.  **Cost Shock FinOps Pasca-Insiden**: Tagihan CloudWatch melonjak hingga **$48,000 USD** dalam bulan tersebut hanya untuk metrik kustom dan pemindaian log mentah tanpa partisi.

### Investigasi Akar Masalah & Tindakan Remediasi
Tim Principal SRE dan FinOps Engineer mengambil langkah arsitektural:

```
[ Solusi Teknis Terpadu PayStream Asia ]

1. Refactoring Telemetri Aplikasi:
   - Menghapus total pemanggilan library CloudWatch SDK PutMetricData.
   - Mengimplementasikan Structured Logging format EMF ke standard output.
   - Menginjeksikan ADOT Collector DaemonSet dengan tail-based sampling.

2. Restrukturisasi Sistem Paging Alarm:
   - Menghapus 450 alarm single-metric.
   - Mengonfigurasi 12 Composite Alarms berbasis Metric Math (Correlation: ALB 5xx + Latency + Error Rate).

3. Inisiasi FinOps Intelligence Pipeline:
   - Mengonfigurasi AWS Data Exports (CUR 2.0) format Parquet ke S3 Glacier Flexible Archive lifecycle.
   - Membangun dashboard alokasi biaya berbasis tenant via Athena SQL.
```

### Query Analitik Athena: Mengidentifikasi Unit Economics per Tenant (Cost per 1,000 Requests)
Untuk menghitung biaya yang dihabiskan untuk melayani setiap pelanggan institusi (*tenant*), query berikut dijalankan pada Athena:

```sql
WITH usage_data AS (
    SELECT
        line_item_usage_start_date,
        resource_tags_user_tenant_id AS tenant_id,
        line_item_resource_id,
        line_item_product_code,
        line_item_unblended_cost AS cost
    FROM
        "finops_cost_intelligence"."cur_cost_and_usage_data"
    WHERE
        year = '2026' AND month = '03'
        AND resource_tags_user_tenant_id IS NOT NULL
),
telemetry_data AS (
    -- Data metrik transaksi diekstraksi dari CloudWatch Metric export harian di S3
    SELECT
        tenant_id,
        SUM(transaction_count) AS total_requests
    FROM
        "finops_cost_intelligence"."aggregated_tenant_metrics"
    WHERE
        event_year = '2026' AND event_month = '03'
    GROUP BY
        tenant_id
)
SELECT
    u.tenant_id,
    ROUND(SUM(u.cost), 2) AS total_direct_aws_cost_usd,
    t.total_requests,
    ROUND((SUM(u.cost) / t.total_requests) * 1000, 4) AS cost_per_1000_requests_usd
FROM
    usage_data u
JOIN
    telemetry_data t ON u.tenant_id = t.tenant_id
GROUP BY
    u.tenant_id,
    t.total_requests
ORDER BY
    total_direct_aws_cost_usd DESC;
```

### Hasil Pasca-Remediasi
*   **Latensi P99**: Turun drastis dari 14 detik menjadi 110ms di bawah beban puncak (9.000 TPS).
*   **Pengurangan Tagihan CloudWatch**: Biaya observabilitas turun dari **$48,000/bulan** menjadi **$6,200/bulan** (penurunan sebesar 87%).
*   **Alert Noise Reduction**: False positive alerts berkurang sebesar 94%. Insiden kritis kini secara akurat ditangkap oleh Composite Alarms.
*   **Visibilitas FinOps**: PayStream berhasil mengidentifikasi 3 merchant yang menggunakan 62% komputasi namun hanya membayar kontrak minimum, memungkinkan tim bisnis memperbarui kontrak berbasis *usage-based pricing model*.

---

## 9. Trade-offs & Engineering Decisions

Dalam merancang observabilitas enterprise dan FinOps, seorang architect harus memilih serangkaian kompromi fundamental:

| Parameter Arsitektur | Opsi A | Opsi B | Analisis Trade-off Rekayasa |
| :--- | :--- | :--- | :--- |
| **Distributed Tracing Sampling** | **Head-based Sampling**<br>*(Sampling ditentukan di awal request di gateway/client, misal: 5%)* | **Tail-based Sampling**<br>*(Sampling dievaluasi setelah trace selesai di level collector)* | **Head Sampling**: Sangat hemat resource collector, namun risiko kehilangan transaksi anomali atau error yang jarang terjadi.<br><br>**Tail Sampling**: Menangkap 100% error dan transaksi lambat secara akurat, namun menuntut resource CPU & RAM tinggi di ADOT collector untuk buffering in-memory. |
| **Penyimpanan Metrik Bisnis** | **CloudWatch Custom Metrics (via EMF)** | **Prometheus / VictoriaMetrics terkelola (AMP)** | **CloudWatch EMF**: Serverless, zero maintenance, native AWS integration. Mahal untuk cardinality ekstrim ($0.30/metric).<br><br>**Managed Prometheus**: Jauh lebih murah untuk jutaan metric series bervolume tinggi, namun membutuhkan manajemen rule recording dan operational overhead. |
| **Mesin Analitik Log Terpusat** | **Amazon CloudWatch Logs Insights** | **Amazon OpenSearch Service (Dedicated Cluster)** | **CloudWatch Insights**: Serverless pay-per-query ($0.005/GB scanned). Sangat hemat jika query investigasi jarang dijalankan.<br><br>**OpenSearch**: Sangat cepat untuk search teks bebas skala enterprise secara konstan, namun biaya kluster komputasi/storage berjalan 24/7 meskipun tidak ada engineer yang query. |
| **Alokasi FinOps Compute** | **100% On-Demand + Compute Savings Plans (3 Tahun)** | **Spot Instances Mix + Spot Fleet Orchestrator** | **Savings Plans**: Diskon signifikan (hingga 66%), zero operational risk, workload tidak akan diinterupsi.<br><br>**Spot Instances**: Diskon hingga 90%, namun menuntut sistem arsitektur stateless yang fault-tolerant dan toleran terhadap terminasi 2 menit. |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Ledakan Kardinalitas EMF (Metric Cardinality Explosion)
*   **Gejala**: Tagihan AWS CloudWatch tiba-tiba melonjak puluhan ribu dolar dalam 24 jam.
*   **Penyebab**: Memasukkan `UserID`, `UUID Order`, atau `IP Address` ke dalam array `Dimensions` pada skema EMF. CloudWatch memperlakukan setiap kombinasi unik dimensi sebagai satu Custom Metric baru yang ditagih terpisah.
*   **Solusi & Troubleshooting**: Pisahkan antara **Dimension** dan **Log Attribute**. Identitas dengan kardinalitas tinggi (high-cardinality values) harus ditempatkan sebagai property biasa di dalam JSON EMF di luar array `Dimensions`, sehingga tetap dapat dicari (*searchable*) via CloudWatch Logs Insights tanpa memicu penciptaan Custom Metric berbayar.

### Mistake 2: Hilangnya Konteks W3C Trace pada Antrean Asinkron (SQS / EventBridge)
*   **Gejala**: Service Graph di AWS X-Ray terputus menjadi dua segmen terisolasi antara producer dan consumer.
*   **Penyebab**: Producer memasukkan data ke SQS tanpa menyematkan trace header di `MessageAttributes`. Consumer membaca pesan baru dan X-Ray SDK menginisialisasi Trace ID baru secara mandiri.
*   **Solusi**: Pastikan aplikasi memetakan W3C context ke `MessageSystemAttributeNames` atau `MessageAttribute`:
    ```go
    // Injeksi Context ke SQS SendMessage
    carrier := propagation.MapCarrier{}
    otel.GetTextMapPropagator().Inject(ctx, carrier)
    
    msgInput := &sqs.SendMessageInput{
        QueueUrl:    aws.String(queueURL),
        MessageBody: aws.String(body),
        MessageAttributes: map[string]types.MessageAttributeValue{
            "traceparent": {
                DataType:    aws.String("String"),
                StringValue: aws.String(carrier["traceparent"]),
            },
        },
    }
```

### Mistake 3: Kesalahan Partisi Glue Catalog pada CUR 2.0 (Athena Scans Seluruh S3 Bucket)
*   **Gejala**: Query Athena FinOps memerlukan waktu bermenit-menit dan biaya pemindaian (bytes scanned) sangat mahal.
*   **Penyebab**: Query tidak menyertakan predikat partisi `WHERE year = 'YYYY' AND month = 'MM'`, memaksa Athena membaca seluruh direktori data historis bertahun-tahun.
*   **Solusi**: Wajibkan parameter partisi dalam setiap template analitik FinOps dan aktifkan fitur *Athena Partition Projection* jika struktur subdirektori S3 teratur.

### Panduan Diagnostik ADOT Collector CrashLoopBackOff:
Jika ADOT DaemonSet pod terus-menerus *crash*:
1.  Periksa error log: `kubectl logs -n opentelemetry -l app.kubernetes.io/name=adot-collector -c adot-collector --tail=100`.
2.  Cek pesan `memory_limiter`: Jika terdapat log `Memory usage limit exceeded, dropping data`, tingkatkan alokasi pod memory request/limit di Kubernetes manifests atau turunkan throughput upstream.
3.  Cek SigV4 Authentication: Pastikan Pod IAM Role memiliki Trust Policy yang tepat terhadap OIDC Provider EKS cluster. Jika unauthorized, akan muncul pesan error: `AccessDenied: User is not authorized to perform: xray:PutTraceSegments`.

---

## 11. Best Practices (Production Checklist)

### Observabilitas Lanjutan
- [ ] **Tanpa Synchronous `PutMetricData`**: Tidak ada satupun service produksi yang memanggil API CloudWatch PutMetricData secara sinkron di jalur kritis request.
- [ ] **Standardisasi W3C TraceContext**: Semua downstream HTTP client dan producer messaging menyertakan header `traceparent` dan `tracestate`.
- [ ] **Koleksi Log Terpusat**: Semua node dan container memancarkan log terstruktur JSON ke stdout, diekstraksi secara asinkron menggunakan collector agent.
- [ ] **Tail Sampling Aktif**: ADOT Collector mengonfigurasi tail-based sampling: 100% traces untuk HTTP 5xx dan latensi > SLA, 1% traces untuk transaksi normal sukses.
- [ ] **Composite Alarms**: Semua eskalasi PagerDuty tingkat tinggi (P1/P2) wajib menggunakan CloudWatch Composite Alarms untuk menghindari badai alert saat dependensi inti (database/jaringan) mengalami gangguan.

### Arsitektur FinOps & Governance
- [ ] **Enforcement Tagging Organisasi**: AWS Tag Policies diterapkan di root AWS Organizations. Resource tanpa tag wajib (`Environment`, `Owner`, `TenantID`, `CostCenter`) ditolak proses provisioning-nya melalui Service Control Policies (SCPs).
- [ ] **CUR 2.0 Otomatis via Parquet**: AWS Data Export CUR 2.0 diaktifkan ke bucket S3 terenkripsi KMS dengan kompresi Parquet.
- [ ] **Athena Query Cutoff Limits**: Seluruh Athena Workgroup FinOps memiliki batasan hard cutoff per-query (misal: max 10GB - 50GB scanned) untuk mencegah eksekusi SQL yang tidak sengaja memindai seluruh data lake.
- [ ] **Storage Lifecycle Rules**: CloudWatch Log Groups memiliki batas retensi eksplisit (misal: 30 hari di CloudWatch, lalu diekspor ke S3 Glacier Flexible Archive untuk compliance).
- [ ] **Rasio Coverage Savings Plans & Spot**: Workload stateless container (EKS) memanfaatkan minimum 50% Spot Instances, didukung Compute Savings Plans untuk baseline load 24/7.

---

## 12. Hands-on Practice

Dalam praktikum ini, Anda akan:
1.  Menyusun skrip emisi EMF performa tinggi.
2.  Memvalidasi pembentukan Custom Metric secara instan tanpa `PutMetricData`.
3.  Menjalankan query CloudWatch Logs Insights untuk korelasi telemetri.

### Langkah 1: Persiapan Environment Lokal
Buat direktori kerja baru:
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

### Langkah 2: Buat Skrip Python Pengemisi EMF (`emit_telemetry.py`)
Tulis skrip berikut untuk mensimulasikan sistem ingest metrik pesanan multi-tenant:

```python
#!/usr/bin/env python3
import json
import time
import random
import sys

def generate_emf_payload(order_id, tenant_id, amount, latency_ms, status_code):
    return {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": "EnterpriseFinOps/Orders",
                    "Dimensions": [["TenantID"], ["TenantID", "StatusCode"]],
                    "Metrics": [
                        {"Name": "OrderAmount", "Unit": "None"},
                        {"Name": "ProcessingTime", "Unit": "Milliseconds"},
                        {"Name": "OrderCount", "Unit": "Count"}
                    ]
                }
            ]
        },
        "TenantID": tenant_id,
        "StatusCode": str(status_code),
        "OrderID": order_id,
        "OrderAmount": float(amount),
        "ProcessingTime": float(latency_ms),
        "OrderCount": 1
    }

if __name__ == "__main__":
    tenants = ["enterprise-acme", "fintech-alpha", "retail-beta"]
    print("Memulai emisi 50 event EMF ke CloudWatch Log Stream...", file=sys.stderr)
    
    for i in range(50):
        t_id = random.choice(tenants)
        amt = round(random.uniform(10.0, 500.0), 2)
        lat = round(random.uniform(45.0, 850.0), 2)
        code = 200 if random.random() > 0.1 else 500
        
        emf_event = generate_emf_payload(f"ord-{1000+i}", t_id, amt, lat, code)
        # Tulis JSON string satu baris ke stdout
        print(json.dumps(emf_event))
        time.sleep(0.05)
```

### Langkah 3: Ingestion ke CloudWatch Logs Menggunakan AWS CLI
Jalankan perintah ini untuk membuat Log Group & Stream khusus, kemudian streaming output EMF:

```bash
# Set environment variables
export AWS_REGION="us-east-1"
export LOG_GROUP="/aws/workload/enterprise-emf-poc"
export LOG_STREAM="stream-$(date +%s)"

# 1. Buat Log Group & Log Stream
aws logs create-log-group --log-group-name "$LOG_GROUP" --region "$AWS_REGION" 2>/dev/null || true
aws logs create-log-stream --log-group-name "$LOG_GROUP" --log-stream-name "$LOG_STREAM" --region "$AWS_REGION"

# 2. Emisikan data, bungkus ke format PutLogEvents, lalu kirim ke AWS
python3 emit_telemetry.py | jq -c -R '{"timestamp": (now * 1000 | floor), "message": .}' | jq -s -c '.' > raw_events.json

# Kirim payload log ke CloudWatch Logs
aws logs put-log-events \
  --log-group-name "$LOG_GROUP" \
  --log-stream-name "$LOG_STREAM" \
  --log-events file://raw_events.json \
  --region "$AWS_REGION"

echo "Data EMF berhasil dikirimkan ke $LOG_GROUP / $LOG_STREAM"
```

### Langkah 4: Validasi Metrik Terbentuk di CloudWatch Metrics
Buka terminal dan jalankan query berikut untuk memverifikasi bahwa CloudWatch Logs engine berhasil mengekstrak metrik kustom dari log secara asinkron:

```bash
aws cloudwatch list-metrics \
  --namespace "EnterpriseFinOps/Orders" \
  --region "$AWS_REGION"
```
*Output harus menampilkan metrik `OrderAmount`, `ProcessingTime`, dan `OrderCount` dengan dimensi `TenantID`.*

### Langkah 5: Eksekusi Query Analitik CloudWatch Logs Insights
Jalankan query analitik untuk menganalisis p95 latensi dan total revenue per tenant:

```bash
QUERY_ID=$(aws logs start-query \
  --log-group-name "$LOG_GROUP" \
  --start-time $(date -v-1H +%s) \
  --end-time $(date +%s) \
  --query-string 'stats count(*) as Transaksi, percentile(ProcessingTime, 95) as LatencyP95, sum(OrderAmount) as GrossVolume by TenantID | sort GrossVolume desc' \
  --region "$AWS_REGION" \
  --output text --query 'queryId')

sleep 5

aws logs get-query-results --query-id "$QUERY_ID" --region "$AWS_REGION"
```

---

## 13. Exercises

### 1. Level Easy: CloudWatch Metric Math
*   **Soal**: Buat deklarasi Terraform untuk CloudWatch Metric Alarm yang memantau utilitas CPU rata-rata dari Auto Scaling Group (`AWS/EC2`), namun alarm hanya boleh aktif jika **Memory Utilization** (dari kustom CloudWatch agent) juga bernilai di atas 80% secara bersamaan menggunakan *Metric Math*.
*   **Petunjuk**: Gunakan `metric_query` dengan ekspresi logika `IF(mCPU > 80 AND mMem > 80, 1, 0)`.

### 2. Level Medium: Tail-Sampling Rule ADOT Collector
*   **Soal**: Modifikasi konfigurasi `collector.yaml` ADOT Collector agar:
    1.  Menangkap 100% traces untuk setiap request yang melewati endpoint `/checkout/pay` tanpa memedulikan status kodenya.
    2.  Menangkap 100% traces untuk request apapun yang memiliki atribut numerik `http.status_code >= 400`.
    3.  Membuang seluruh span health-check yang menuju ke path `/healthz` atau `/metrics`.
*   **Petunjuk**: Manfaatkan `tail_sampling` processor dengan `string_attribute`, `numeric_attribute`, dan filter processor.

### 3. Level Hard: Athena Cost Intelligence Joiner
*   **Soal**: Tulis query SQL Athena CUR 2.0 tingkat produksi yang menghitung alokasi biaya harian Amazon S3 bucket storage per tim. Ketentuannya:
    1.  Kelompokkan berdasarkan tag biaya `resource_tags_user_team`.
    2.  Hitung total unblended cost.
    3.  Tampilkan persentase kontribusi biaya masing-masing tim terhadap total tagihan S3 organisasi pada bulan tersebut (*Window function: `SUM(...) OVER()`*).

---

## 14. Challenges (Architectural Scenario)

### Skenario Kasus: Global FinOps & Multi-Cluster Telemetry Pipeline

**Konteks Enterprise**:
Anda adalah Principal Infrastructure Architect di sebuah bank digital global yang beroperasi di 3 Region AWS: `us-east-1` (Primary), `eu-west-1` (Compliance Europe), dan `ap-southeast-1` (Regional Hub). Setiap region memiliki cluster Amazon EKS dengan ribuan pods mikroservis. Organisasi menggunakan akun AWS terpisah:
1.  *12 Workload Accounts* (Dev, Staging, Prod per region).
2.  *1 Shared Security & Logging Account*.
3.  *1 Central Payer / FinOps Master Account*.

**Permasalahan Nyata**:
1.  Tim kepatuhan regulasi menuntut seluruh distributed traces transaksi finansial yang gagal disimpan selama 7 tahun dalam format yang tidak dapat diubah (*immutable/WORM*), namun anggaran observabilitas dipangkas sebesar 40%.
2.  Terdapat kebutuhan untuk menghitung unit cost real-time: **"Berapa biaya infrastruktur AWS murni yang dihabiskan untuk memproses satu otentikasi biometrik nasabah di region ap-southeast-1 vs eu-west-1?"**.
3.  Penggunaan AWS X-Ray di multi-account mengalami fragmentasi karena trace id tidak terfederasi secara otomatis saat request melintasi batas VPC dan batas Akun AWS via Transit Gateway.

**Tugas Arsitektur Anda**:
*   Rancang dokumen arsitektur komprehensif (spesifikasi alur data, komponen AWS, format data, dan strategi sampling).
*   Jelaskan desain pipeline retensi data bertingkat (*tiered storage*) untuk menyeimbangkan kebutuhan audit kepatuhan 7 tahun dengan pemotongan anggaran 40%.
*   Gambarkan diagram alir cross-account observability menggunakan AWS Organizations, ADOT, CloudWatch Cross-Account Observability, dan S3 Glacier Vault Lock.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Konsep Dasar (5 Soal)

1.  **Apa perbedaan mendasar antara memanggil API `PutMetricData` secara langsung dibandingkan menggunakan CloudWatch Embedded Metric Format (EMF)?**
    *   *Jawaban & Penjelasan*: `PutMetricData` adalah panggilan API HTTPS sinkron yang membebani latensi aplikasi dan dibatasi oleh kuota API (throttling). EMF adalah pencatatan log terstruktur JSON secara asinkron ke `stdout` yang diekstraksi oleh backend CloudWatch Logs menjadi metrik tanpa menimbulkan latensi kritis pada aplikasi dan bebas dari rate-limiting `PutMetricData`.

2.  **Mengapa menambahkan User ID unik (high cardinality) ke dalam `Dimensions` pada Embedded Metric Format dianggap sebagai anti-pattern berat?**
    *   *Jawaban & Penjelasan*: Karena CloudWatch memperlakukan setiap nilai dimensi unik sebagai sebuah Custom Metric baru yang ditagih terpisah ($0.30 per metrik per bulan). Menambahkan jutaan User ID unik ke dalam dimensi akan memicu *Metric Cardinality Explosion* dan melipatgandakan tagihan AWS secara drastis.

3.  **Apa fungsi utama dari prosesor `tail_sampling` pada ADOT Collector dibandingkan `head_sampling` di level SDK?**
    *   *Jawaban & Penjelasan*: `head_sampling` memutuskan apakah trace akan disimpan atau dibuang di awal transaksi saat hasil (sukses/gagal/latensi) belum diketahui. `tail_sampling` menahan data trace di buffer memori collector hingga seluruh alur request selesai, memungkinkan collector menyimpan 100% traces yang mengalami error atau transaksi berlatensi tinggi, sambil membuang mayoritas trace normal yang sukses.

4.  **Format file kompresi data apa yang menjadi standar industri pada ekspor AWS CUR 2.0 untuk query berkecepatan tinggi di Athena, dan mengapa?**
    *   *Jawaban & Penjelasan*: Format **Apache Parquet**. Parquet adalah format penyimpanan berbasis kolom (columnar storage) yang memungkinkan Amazon Athena hanya memindai kolom-kolom spesifik yang diperlukan oleh query SQL (misal: hanya membaca kolom `cost` dan `usage_date`), sehingga menghemat waktu proses query dan mengurangi biaya data scanning secara dramatis.

5.  **Bagaimana CloudWatch Composite Alarm membantu mengurangi "Alert Fatigue" bagi tim SRE?**
    *   *Jawaban & Penjelasan*: Composite Alarm mengevaluasi beberapa kondisi alarm menggunakan operator logika Boolean (AND, OR, NOT). Ini mencegah pager engineer berbunyi hanya karena anomali sesaat pada satu metrik (misal: CPU spike singkat), dan hanya mengirimkan alert jika beberapa gejala kegagalan nyata terjadi secara serentak (misal: Error Rate tinggi DAN Latensi tinggi).

### Bagian B: Konsep Lanjutan (5 Soal)

6.  **Bagaimana W3C Trace Context (`traceparent`) dipropagasikan melintasi service boundary yang dipisahkan oleh Amazon SQS?**
    *   *Jawaban & Penjelasan*: Karena SQS tidak secara default membedah payload HTTP, aplikasi pengirim (producer) harus mengekstrak string `traceparent` dari konteks tracing aktif dan menyematkannya ke dalam `MessageAttributes` SQS. Aplikasi penerima (consumer) membaca atribut pesan tersebut dan menggunakannya untuk menyambung (*inject*) context ke span baru.

7.  **Dalam arsitektur AWS Multi-Account, apa fungsi dari `AWS Cross-Account Observability` (CloudWatch OAM)?**
    *   *Jawaban & Penjelasan*: Memungkinkan akun sentral (Monitoring Account) mencari, memvisualisasikan, dan mengkorelasikan logs, metrics, dan traces yang berasal dari puluhan akun AWS lainnya (Source Accounts) secara aman tanpa perlu membangun pipeline data duplikat atau cross-account IAM role assumptions yang rumit.

8.  **Apa perbedaan mendasar antara *Unblended Cost*, *Blended Cost*, dan *Amortized Cost* dalam pelaporan analitik FinOps AWS?**
    *   *Jawaban & Penjelasan*:
        *   *Unblended Cost*: Biaya murni penggunaan riil pada hari tagihan dibuat (cash basis).
        *   *Blended Cost*: Rata-rata biaya penggunaan di seluruh akun dalam AWS Organization yang sama (seringkali mengaburkan data riil).
        *   *Amortized Cost*: Biaya yang merefleksikan nilai riil penggunaan dengan mendistribusikan biaya komitmen di muka (Upfront Savings Plans / Reserved Instances) secara proporsional setiap jam/hari ke resource yang mengonsumsinya.

9.  **Mengapa Anda harus mengonfigurasi `memory_limiter` processor di urutan paling awal pada pipeline ADOT Collector?**
    *   *Jawaban & Penjelasan*: Untuk mencegah container collector mengalami kondisi *Out of Memory* (OOM) dan dihentikan oleh Linux Kernel (OOMKilled) ketika terjadi lonjakan beban telemetri (*traffic spike*). `memory_limiter` memonitor alokasi heap dan mulai melakukan drop data atau membatasi intake sebelum penggunaan RAM menyentuh batas maksimum.

10. **Bagaimana cara menerapkan tata kelola penagihan agar developer tidak dapat membuat resource AWS tanpa tag `CostCenter`?**
    *   *Jawaban & Penjelasan*: Menerapkan **Tag Policies** pada level AWS Organizations untuk standarisasi huruf/format tag, dikombinasikan dengan **Service Control Policies (SCP)** yang memiliki statement `Deny` dengan kondisi `Null: aws:RequestTag/CostCenter = true` pada aksi-aksi pembuatan resource (seperti `ec2:RunInstances`, `rds:CreateDBInstance`).

### Bagian C: Skenario Kasus Produksi Riil (3 Soal)

11. **Skenario 1**: Aplikasi API pembayaran Anda di Amazon EKS tiba-tiba kehilangan jejak korelasi distributed tracing di AWS X-Ray setelah memanggil layanan perbankan pihak ketiga (eksternal). Log trace berakhir tepat sebelum panggilan HTTP keluar. Apa analisis arsitektur Anda dan bagaimana memperbaikinya?
    *   *Analisis & Solusi*: Pihak ketiga kemungkinan besar tidak meneruskan header W3C `traceparent` atau mengembalikan trace ID baru yang tidak kompatibel. Solusinya: Buat subsegment klien X-Ray eksplisit tepat sebelum panggilan HTTP keluar yang menandai downstream sebagai layanan independen/eksternal (*remote dependency*), lalu rekam status respon HTTP eksternal ke dalam metadata span tersebut agar segment tetap tertutup dengan valid.

12. **Skenario 2**: Perusahaan Anda memproses 50 TB logs per hari di CloudWatch Logs. Biaya pencarian interaktif via CloudWatch Logs Insights melonjak hingga $7,500 per bulan karena para engineer menjalankan pencarian `*` tanpa batas filter waktu. Solusi arsitektur tanpa mematikan visibilitas engineer?
    *   *Analisis & Solusi*:
        1. Alirkan raw logs secara real-time dari CloudWatch Logs ke Amazon S3 menggunakan Amazon Kinesis Data Firehose (terkompresi Parquet dengan dynamic partitioning berbasis tanggal/service).
        2. Terapkan lifecycle policy: simpan logs di CloudWatch Logs hanya selama 3-7 hari (untuk triage instan), lalu delegasikan query analitik historis mendalam ke Amazon Athena dengan pembatasan *bytes-scanned limit* pada workgroup.

13. **Skenario 3**: Sebuah microservice berbasis Go mengalami lonjakan CPU hingga 100% sesaat setelah Anda mengaktifkan OpenTelemetry auto-instrumentation dengan X-Ray SDK. Traffic transaksi tidak bertambah. Apa kemungkinan kegagalan di level runtime Go dan bagaimana mitigasinya?
    *   *Analisis & Solusi*: Kemungkinan besar terjadi alokasi memori objek runtime tracing yang sangat masif (*high memory allocation rate*) yang memicu kerja ekstrem pada Go Garbage Collector (GC thrashing). Mitigasinya: Turunkan frekuensi sampling tracing, nonaktifkan capture stack trace pada level INFO/DEBUG, gunakan buffer channel asynchronous untuk pengiriman span, dan pastikan membatasi segment subcall database yang terlalu granular dalam loop sekuensial.

---

## 16. Summary

1.  **Modern Cloud Observability** memindahkan ingestion metrik dari panggilan API sinkron yang rawan *throttling* (`PutMetricData`) menuju asynchronous ingestion berbasis skema melalui **Embedded Metric Format (EMF)** dan **AWS Distro for OpenTelemetry (ADOT)**.
2.  **AWS Distro for OpenTelemetry (ADOT)** berfungsi sebagai fondasi telemetri terstandarisasi CNCF untuk mengumpulkan traces, metrics, dan logs dengan pemrosesan tingkat lanjut seperti **Tail-based Sampling**, melindungi sistem downstream dari lonjakan beban dan menghemat biaya ingestion.
3.  Pencegahan **Alert Fatigue** pada sistem terdistribusi skala enterprise diwujudkan menggunakan kombinasi **CloudWatch Metric Math** dan **Composite Alarms**, memastikan notifikasi paging hanya dikirimkan jika beberapa anomali performa dan kegagalan fungsional terdeteksi secara serentak.
4.  **Cloud FinOps Modern** menuntut transisi dari peninjauan invoice bulanan reaktif menuju arsitektur analitik terotomatisasi. Mengintegrasikan **AWS Cost and Usage Report (CUR) 2.0**, **AWS Glue**, dan **Amazon Athena** memungkinkan organisasi mengkorelasikan telemetri teknis dengan data penagihan riil untuk mendapatkan visibilitas **Unit Economics** (biaya per transaksi/tenant) yang akurat.