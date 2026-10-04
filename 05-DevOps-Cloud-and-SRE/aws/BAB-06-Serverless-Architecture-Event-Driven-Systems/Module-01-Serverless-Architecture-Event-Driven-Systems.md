# Modul 01: Serverless Architecture & Event-Driven Systems di AWS

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Menganalisis siklus hidup eksekusi **AWS Lambda**, mengoptimalkan *cold starts*, mengelola *concurrency* (Reserved vs Provisioned), serta mendesain strategi mitigasi latensi berbasis Firecracker microVM.
- Menentukan pemilihan tipe **Amazon API Gateway** (REST API, HTTP API, WebSocket API) berdasarkan kebutuhan fungsionalitas, performa, latensi, dan model biaya.
- Mengimplementasikan pola asinkronus menggunakan **Amazon SQS** (Standard vs FIFO, *Message Deduplication*, *Message Group ID*, *Visibility Timeout*, *Dead-Letter Queues*) dan **Amazon SNS** (*fan-out pattern*, *message filtering*).
- Merancang arsitektur decoupled berbasis **Amazon EventBridge** (*event buses*, *content-based routing rules*, *schema registry*, *replay/archive*).
- Mengorkestrasi distributed workflows dan mengimplementasikan **Saga Pattern** dengan transaksi kompensasi (*compensating transactions*) menggunakan **AWS Step Functions** (Standard vs Express Workflows).
- Mengintegrasikan metrik observabilitas, penanganan error (*retries with exponential backoff and jitter*), serta kebijakan fail-safe pada sistem terdistribusi berskala enterprise.

---

## 2. Prerequisite
Sebelum mempelajari modul ini, Anda harus memahami:
- Konsep dasar jaringan AWS: VPC, Subnet, Security Group, NAT Gateway, dan VPC Endpoints (PrivateLink).
- Pengetahuan solid tentang protokol HTTP/HTTPS, REST, WebSockets, dan format pertukaran data JSON.
- Model keamanan IAM: IAM Roles, IAM Policies (Resource-based vs Identity-based), dan prinsip *least privilege*.
- Konsep dasar sistem terdistribusi: *idempotency*, *eventual consistency*, CAP theorem, dan *asynchronous messaging*.
- Kemampuan membaca dan menulis kode dalam Python atau Node.js serta dasar-dasar Terraform/OpenTofu atau AWS Cloud Development Kit (CDK).

---

## 3. Concept
**Serverless Computing** adalah paradigma arsitektur di mana penyedia cloud mengelola alokasi, provisi, penskalaan, dan *patching* infrastruktur komputasi secara dinamis. Konsumen hanya membayar sumber daya yang dikonsumsi secara aktual saat kode dieksekusi (skala hingga nol / *scale-to-zero*).

**Event-Driven Architecture (EDA)** adalah pola arsitektur perangkat lunak di mana komponen-komponen decoupled saling berinteraksi secara asinkron melalui penangkapan (*capture*), pemrosesan, dan persistensi *events* (perubahan status sistem yang signifikan). Karakteristik fundamental EDA:
1. **Producer tidak mengetahui Consumer**: *Publisher* memancarkan *event* ke *event broker/bus* tanpa ketergantungan langsung pada siapa yang memprosesnya.
2. **Asinkronus secara Alami**: Pengirim tidak memblokir thread eksekusi untuk menunggu respons downstream.
3. **Penyimpanan Status Sementara (Buffering)**: Komponen seperti antrean (queue) menyerap lonjakan trafik (*load leveling*) untuk melindungi dependensi downstream.

---

## 4. Why
Monolitik tradisional dan sistem berbasis microservices sinkron (HTTP request-response chaining) menghadapi limitasi fundamental:
- **Cascading Failures**: Jika Service A memanggil Service B, dan B memanggil Service C secara sinkron, kegagalan pada Service C menyebabkan timeout berantai hingga ke klien awal, menghabiskan thread pool dan kapasitas memori.
- **Tightly Coupled Scaling**: Komponen penulisan berkecepatan tinggi harus diskalakan bersamaan dengan komponen pembacaan yang lambat, mengakibatkan pemborosan alokasi resource CPU/Memory.
- **Operational Overhead**: Pengelolaan klaster server (VM/Kontainer) memerlukan auto-scaling policies yang rumit, patching OS berkala, dan kapasitas cadangan (*headroom*) yang mahal saat beban rendah.

Serverless dan EDA di AWS menyelesaikan permasalahan ini dengan:
- Menghilangkan *idle cost* melalui model eksekusi *pay-as-you-go*.
- Mengisolasi domain kegagalan: antrean dan bus event bertindak sebagai *shock absorbers*.
- Menyediakan kemampuan *autoscaling* otomatis dari 0 hingga puluhan ribu eksekusi paralel per detik dalam hitungan milidetik.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 AWS Lambda Internals
AWS Lambda mengeksekusi kode di atas sistem virtualisasi berbasis **Firecracker microVM**.

#### Siklus Hidup Eksekusi (Execution Lifecycle):
1. **Init Phase**:
   - *Extension Init*: Memulai ekstensi Lambda (misal: Datadog, AWS Distro for OpenTelemetry).
   - *Runtime Init*: Menginisialisasi runtime bahasa (Python, Node.js, JVM).
   - *Function Init*: Mengeksekusi kode statis/global di luar handler utama (memuat dependencies, inisialisasi koneksi database, mendekode variabel lingkungan).
2. **Invoke Phase**:
   - Lambda memanggil handler fungsi.
   - Durasi invoke dihitung per milidetik.
3. **Shutdown Phase**:
   - Jika fungsi tidak menerima trafik dalam jangka waktu tertentu, microVM dihentikan (*terminated*). Ekstensi diberikan alokasi waktu singkat untuk membersihkan resource.

```
+-------------------------------------------------------------------+
|                        Lambda Execution Lifecycle                  |
+-------------------------------------------------------------------+
| [INIT PHASE]                                                      |
|   ├── Extension Init (Max 2s)                                     |
|   ├── Runtime Init                                                |
|   └── Function Init (Static imports, DB pools, SDK clients)       |
|       ===> COLD START OCCURS HERE                                  |
+-------------------------------------------------------------------+
| [INVOKE PHASE]                                                    |
|   ├── Handler Execution (Event processing, context generation)    |
|   └── Response sent back to invoker                               |
|       ===> WARM INVOCATIONS RE-RUN ONLY THIS PHASE                |
+-------------------------------------------------------------------+
| [SHUTDOWN PHASE]                                                  |
|   ├── Runtime shutdown                                            |
|   └── Extension cleanup                                           |
+-------------------------------------------------------------------+
```

#### Cold Start vs Warm Invocation:
- **Cold Start**: Terjadi saat tidak ada microVM siap pakai (*idle warm container*). Lambda harus membuat microVM baru, mengunduh image/arsip ZIP, dan menjalankan *Init Phase*. Menghasilkan latensi tambahan dari 100ms (Node.js/Python) hingga beberapa detik (Java/C#).
- **Warm Invocation**: Permintaan datang saat container yang sudah diinisialisasi masih tersedia. Hanya menjalankan handler (*Invoke Phase*). Latensi overhead penyedia mendekati < 5ms.

#### Model Concurrency:
- **Formula Kapasitas**: $\text{Concurrency} = \text{Requests Per Second (RPS)} \times \text{Average Duration (seconds)}$.
- **Unreserved Concurrency**: Kapasitas bawaan akun (default: 1.000 per region), dibagi rata ke seluruh fungsi yang tidak memiliki batasan.
- **Reserved Concurrency**: Menjamin kuota konkurensi tertentu untuk fungsi spesifik, sekaligus membatasi batas atasnya agar fungsi tersebut tidak menghabiskan kuota akun (*throttling protection*).
- **Provisioned Concurrency**: Menginisialisasi sejumlah *execution environments* sebelumnya (menjalankan Init Phase di awal). Mengeliminasi cold start secara penuh untuk endpoint yang sensitif terhadap latensi SLA.
- **Lambda SnapStart** (untuk Java): Mengambil snapshot memori microVM yang telah terinisialisasi dan menyimpannya di cache terenkripsi; saat cold start, microVM di-restore dari snapshot dengan latensi sub-detik.

---

### 5.2 API Gateway: REST vs HTTP vs WebSocket

| Fitur / Parameter | API Gateway HTTP API | API Gateway REST API | API Gateway WebSocket API |
| :--- | :--- | :--- | :--- |
| **Protokol** | HTTP/1.1, HTTP/2 | HTTP/1.1 | WS / WSS (Stateful) |
| **Latensi** | Sangat Rendah (~50% lebih cepat dari REST) | Standar | Persisten (Sub-millisecond framing) |
| **Biaya Relatif** | ~70% lebih murah dibanding REST | Paling mahal di antara ketiganya | Bayar per menit koneksi + pesan |
| **Fitur Otorisasi** | JWT authorizers native, Lambda Request Authorizer | Lambda Authorizers, IAM, Cognito User Pools | Lambda Authorizers, IAM |
| **Validasi Request** | Tidak ada native validation | Schema Validation berbasis JSON Schema | Validasi pada handler aplikasi |
| **Integrasi AWS** | Langsung ke Lambda, HTTP endpoints, beberapa private ALB | Hampir semua service AWS secara langsung (VTL engine) | Lambda, HTTP, AWS Services |
| **Usage Plans & Keys** | Tidak didukung | Didukung secara native (API Keys, Quotas, Throttle) | Tidak didukung |
| **Kasus Penggunaan Utama**| Microservices ringan, webhook intake, backends mobile | Enterprise API publik, monetisasi API, integrasi WAF kompleks | Chat apps, live financial dashboards, real-time sync |

---

### 5.3 Amazon SQS: Standard vs FIFO

```
Standard Queue:
Producer ---> [ Msg 1 ] [ Msg 2 ] [ Msg 3 ] ---> Consumer
(Throughput hampir tanpa batas, At-Least-Once, Best-Effort Ordering)
Bisa terjadi: Msg 2 diterima sebelum Msg 1, atau Msg 1 diterima dua kali.

FIFO Queue:
Producer ---> [ Msg 1 ] [ Msg 2 ] [ Msg 3 ] ---> Consumer
(Strict Order via MessageGroupId, Exactly-Once Processing via DeduplicationId)
Maksimal: 300 msg/s (atau 3.000-70.000 dengan High Throughput FIFO batching).
```

#### Mekanisme Kunci SQS:
- **Visibility Timeout**: Durasi di mana pesan disembunyikan dari consumer lain setelah diambil oleh suatu worker. Jika worker gagal menyelesaikan pemrosesan dan tidak menghapus pesan sebelum timeout habis, pesan menjadi visible kembali untuk di-consume ulang.
- **Dead-Letter Queue (DLQ)**: Antrean tujuan untuk pesan-pesan yang gagal diproses setelah $N$ kali percobaan (`maxReceiveCount`). Mencegah kondisi *Poison Pill* yang memblokir pipeline.
- **Message Deduplication ID**: Token unik pada antrean FIFO untuk mengenali duplikasi dalam jendela 5 menit.
- **Message Group ID**: Tag pada FIFO queue yang menentukan partisi pesan; pesan dalam satu group ID diproses secara berurutan (*strictly in-order*), namun group ID berbeda dapat diproses paralel.

---

### 5.4 Amazon SNS & Fan-Out Pattern
Amazon SNS adalah message broker publish/subscribe bertipe *push-based*.
- **Fan-Out Pattern**: Mengirimkan satu pesan dari producer ke sebuah SNS Topic, yang kemudian didistribusikan secara paralel ke berbagai subscriber (antrean SQS, Lambda, webhook HTTPS, atau nomor telepon SMS).
- **Message Filtering**: Atribut pesan dievaluasi terhadap filter policy subscription individual. Consumer hanya menerima pesan yang relevan tanpa harus membuangnya di lapisan kode aplikasi.
- **Dead-Letter Queues untuk Subscription**: Menjamin pesan yang gagal dikirimkan ke subscriber tidak hilang begitu saja.

---

### 5.5 Amazon EventBridge
Amazon EventBridge adalah serverless event bus terkelola yang merutekan data berbasis aturan deklaratif (*content-based filtering*).

```
[ Sources ]               [ EventBridge Event Bus ]                  [ Targets ]
Custom Apps   ----+                                              +--> Lambda (Payment)
AWS Services  ----+---> [ Rules: content-based evaluation ] ----+--> SQS (Audit Trail)
SaaS (Shopify)+-+|                                              +--> Step Functions
                  v                                                   (Order Saga)
             [Archive & Replay]
```

- **Perbedaan Arsitektural dengan SNS**:
  - SNS dioptimalkan untuk performa tinggi, latency sangat rendah (<30ms), direct messaging dengan ribuan hingga jutaan endpoint fan-out.
  - EventBridge dioptimalkan untuk event parsing mendalam (JSON content filtering), integrasi native ke >200 layanan AWS tanpa glue code, terintegrasi dengan Partner SaaS (Datadog, PagerDuty, MongoDB), dan memiliki fitur mutlak seperti **Schema Registry** serta **Event Archiving and Replay**.
- **Event Pattern Matching**: Mampu mengevaluasi JSON keys, numerik, prefix, exact match, dan negation secara langsung pada level bus.

---

### 5.6 AWS Step Functions: Distributed Workflows & Saga Pattern
Step Functions adalah visual state machine terkelola untuk mengoordinasikan sistem terdistribusi.

#### Standard vs Express Workflows:
- **Standard**: *Exactly-once execution*, durasi hingga 1 tahun, visual execution history penuh di konsol AWS, model penetapan harga per transisi status (*state transition*). Ideal untuk alur bisnis inti (*order processing*, *loan approval*).
- **Express**: *At-least-once execution*, durasi maksimal 5 menit, throughput sangat tinggi (>100.000 executions/s), biaya berbasis durasi komputasi dan memori. Cocok untuk IoT data ingestion dan streaming event transformation.

#### Distributed Saga Pattern:
Dalam microservices terdistribusi, transaksi dua fase (2PC) dihindari karena overhead locking yang tinggi. **Saga Pattern** menggantikannya dengan serangkaian transaksi lokal. Jika salah satu langkah gagal, Step Functions mengeksekusi **Compensating Transactions** secara mundur untuk memulihkan konsistensi data.

```
+---------------+      Success      +--------------------+      Success      +-------------------+
| ChargeCredit  | ----------------> | ReserveInventory   | ----------------> | ConfirmShipment   |
+---------------+                   +--------------------+                   +-------------------+
        |                                     |                                        |
        | Fail                                | Fail                                   | Fail
        v                                     v                                        v
  [End: Failed]                     +--------------------+                   +-------------------+
                                    | RefundCredit       |                   | ReleaseInventory  |
                                    +--------------------+                   +-------------------+
                                              ^                                        |
                                              |----------------------------------------+
```

---

## 6. How
Implementasi menyeluruh pola arsitektur event-driven serverless melibatkan langkah integrasi sistem:
1. **Definisikan Interface**: Menggunakan OpenAPI spec pada API Gateway atau schema JSON pada EventBridge Schema Registry.
2. **Setup Asynchronous Boundary**: Tempatkan SQS atau EventBridge tepat di belakang entrypoint untuk memutus dependensi langsung.
3. **Konfigurasi Error Handling**:
   - Tentukan `MaximumRecordAgeInSeconds`, `MaximumRetryAttempts`, dan dead-letter queues (DLQ) pada Event Source Mapping (ESM) Lambda.
   - Konfigurasi `Retry` blocks pada Step Functions dengan parameter `BackoffRate: 2.0` dan `Jitter: FULL`.
4. **Isolasi Database & Koneksi**:
   - Gunakan RDS Proxy saat berinteraksi dengan database relasional (PostgreSQL/MySQL) untuk mencegah Lambda kehabisan *pool* koneksi akibat lonjakan konkurensi.

---

## 7. Analogy
Bayangkan operasional sebuah restoran cepat saji:
- **HTTP Request Sinkron**: Anda memesan burger ke kasir, kasir berdiri mematung menunggu koki memanggang daging, membungkus burger, hingga menyerahkannya kepada Anda. Seluruh antrean kasir berhenti total jika kompor gas koki macet (*thread blocking* dan *cascading latency*).
- **Event-Driven Asinkron (SQS/SNS)**: Anda memesan ke kasir. Kasir memberikan Anda selembar tiket bernomor (kemudian merespons Anda dengan HTTP `202 Accepted`), lalu menempelkan tiket pesanan ke papan dapur. Koki mengambil tiket dari papan sesuai antrean (*load leveling via SQS*). Kasir langsung melayani orang berikutnya.
- **EventBridge**: Sebuah pengeras suara pintar yang mengumumkan "Burger #105 Selesai". Karyawan saus menambahkan saus (Rule 1), staf packaging membungkusnya (Rule 2), dan sistem akuntansi mencatat penjualan bahan baku (Rule 3) tanpa pengeras suara perlu tahu siapa saja yang mendengarkan.
- **Step Functions (Saga)**: Manajer restoran yang memegang SOP: Ambil roti $\rightarrow$ Panggang daging $\rightarrow$ Masukkan keju. Jika keju habis di tengah proses, ia menjalankan prosedur darurat: Batalkan pesanan roti $\rightarrow$ Kembalikan daging ke kulkas $\rightarrow$ Kembalikan uang pelanggan (*compensating actions*).

---

## 8. Diagram (ASCII)

Berikut adalah arsitektur enterprise checkout order yang menggabungkan seluruh komponen:

```
[ Web/Mobile Client ]
         |
    (POST /order)
         |
         v
+------------------+
| API Gateway HTTP |
+------------------+
         |
         v
+------------------+       Send Event       +-------------------------+
|  Ingestion Lambda| ---------------------> | Amazon EventBridge Bus  |
+------------------+                        +-------------------------+
                                                         |
         +-----------------------------------------------+-------------------------------+
         | (Rule: source = order.service)                                                | (Rule: audit = true)
         v                                                                               v
+------------------+                                                             +------------------+
| AWS Step Function| (Orchestration Saga)                                        |  SQS FIFO Queue  |
+------------------+                                                             +------------------+
  |-- Step 1: Lambda Reserve Inventory (Compensate: Release Inventory)                    |
  |-- Step 2: Lambda Charge Payment   (Compensate: Refund Payment)                       v
  |-- Step 3: Publish to SNS Fan-out                                             +------------------+
                                                                                 | Audit Log Engine |
                                                                                 +------------------+
                 | (SNS: order.completed)
         +-------+-------+
         |               |
         v               v
  +-------------+ +-------------+
  | SQS Worker  | | SQS Worker  |
  | Email Notif | | ERP Sync    |
  +-------------+ +-------------+
```

---

## 9. Simple Example
Inisialisasi fungsi AWS Lambda Python yang menerima payload dari SQS dan menerapkan pemrosesan idempoten:

```python
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info("Processing SQS Batch. Total records: %d", len(event['Records']))
    
    batch_item_failures = []
    
    for record in event['Records']:
        message_id = record['messageId']
        try:
            body = json.loads(record['body'])
            order_id = body.get("order_id")
            
            if not order_id:
                raise ValueError("Missing 'order_id' parameter")
                
            logger.info("Successfully processed order: %s", order_id)
            
        except Exception as exc:
            logger.error("Failed processing message %s: %s", message_id, str(exc))
            # Laporkan individual failure untuk partial batch response SQS
            batch_item_failures.append({"itemIdentifier": message_id})
            
    return {"batchItemFailures": batch_item_failures}
```

---

## 10. Practical Example (Infrastruktur Terraform)
Berikut adalah konfigurasi Terraform (v1.5+) yang mendirikan antrean SQS Standard dengan Dead-Letter Queue terisolasi, SNS Topic fan-out, dan Event Source Mapping ke Lambda.

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
  region = "us-east-1"
}

# 1. SQS Dead-Letter Queue
resource "aws_sqs_queue" "order_dlq" {
  name                      = "order-processing-dlq"
  message_retention_seconds = 1209600 # 14 hari
}

# 2. Main SQS Queue dengan Redrive Policy
resource "aws_sqs_queue" "order_queue" {
  name                       = "order-processing-queue"
  visibility_timeout_seconds = 60 # 6x durasi Lambda timeout (10 detik)
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.order_dlq.arn
    maxReceiveCount     = 3
  })
}

# 3. SNS Topic untuk Fan-Out
resource "aws_sns_topic" "order_events" {
  name = "order-events-topic"
}

# 4. Langganan SNS ke SQS (Fan-Out Subscription)
resource "aws_sns_topic_subscription" "order_queue_sub" {
  topic_arn = aws_sns_topic.order_events.arn
  protocol  = "sqs"
  endpoint  = aws_sqs_queue.order_queue.arn

  # Filter Policy: Hanya proses transaksi yang disetujui
  filter_policy = jsonencode({
    status = ["APPROVED", "COMPLETED"]
  })
}

# 5. Kebijakan Akses SQS agar SNS diizinkan mengirim pesan
resource "aws_sqs_queue_policy" "order_queue_policy" {
  queue_url = aws_sqs_queue.order_queue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowSNSSendMessages"
        Effect    = "Allow"
        Principal = { Service = "sns.amazonaws.com" }
        Action    = "sqs:SendMessage"
        Resource  = aws_sqs_queue.order_queue.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_sns_topic.order_events.arn
          }
        }
      }
    ]
  })
}
```

---

## 11. Real World Example
**Skenario**: Platform Tiket Konser Berskala Nasional (High Peak Concurrency).
- **Tantangan**: Ketika tiket konser grup musik internasional dibuka pada pukul 10.00, sistem menerima 80.000 permintaan per detik secara bersamaan. Backend basis data relasional (RDS Aurora) akan kolaps jika dibanjiri 80.000 koneksi bersamaan.
- **Solusi Arsitektur**:
  1. Klien mengirim permintaan checkout ke **API Gateway HTTP API** yang terintegrasi langsung dengan endpoint IAM-authorized Lambda.
  2. Lambda `Queue-Ingestor` hanya melakukan validasi token JWT awal, menghasilkan `correlation_id`, lalu mendorong event pembelian ke **Amazon EventBridge**.
  3. EventBridge merutekan order ke **Amazon SQS FIFO Queue** yang dibagi berdasarkan `MessageGroupId: event_category_id`.
  4. Sekelompok worker Lambda mengambil pesan dari antrean dengan kecepatan terkendali (*concurrency limit* = 50 instance), berkomunikasi dengan RDS melalui **AWS RDS Proxy** untuk connection pooling.
  5. Jika alokasi kursi gagal dipesan, **Step Functions Saga** mengeksekusi pengembalian limit kartu kredit secara otomatis.
- **Hasil**: Klien menerima status instan `202 Accepted` dalam kurun waktu < 75 milidetik, sementara sistem pemrosesan transaksi berjalan stabil pada utilisasi CPU 65% tanpa ada *connection timeout* pada database relasional.

---

## 12. Trade-offs

```
+------------------------------------+---------------------------------------+
| Keuntungan Arsitektur              | Konsekuensi / Kerugian Komparatif     |
+------------------------------------+---------------------------------------+
| Zero Idle Cost                     | Biaya tidak linear pada throughput    |
| (Hemat biaya saat trafik rendah)   | tinggi konstan (Container/EC2 lebih   |
|                                    | ekonomis untuk beban konstan)         |
+------------------------------------+---------------------------------------+
| Autoscaling Elastis                | Tantangan Cold Start dan Downstream   |
| (0 -> ribuan container otomatis)   | Saturation (database bisa kolaps)     |
+------------------------------------+---------------------------------------+
| Loose Coupling & Fault Isolation   | Eventual Consistency                  |
| (Komponen gagal tidak merusak flow)| (Kompleksitas tracking data state)    |
+------------------------------------+---------------------------------------+
| Observabilitas Terkelola           | Sulitnya Distributed Tracing          |
| (CloudWatch native logs & metrics) | (Wajib X-Ray / OTel trace context)    |
+------------------------------------+---------------------------------------+
```

---

## 13. When To Use
Gunakan Serverless & Event-Driven Systems saat:
- Pola beban kerja berfluktuasi tajam, tidak dapat diprediksi secara pasti, atau memiliki jam operasional mati (*dormant periods*).
- Membangun arsitektur microservices modern di mana setiap domain layanan harus mandiri dan tidak saling memblokir (*non-blocking*).
- Sistem memproses pipeline data asinkron seperti pemrosesan file S3, ingestion webhook pihak ketiga, atau sistem notifikasi multi-kanal.
- Kecepatan rilis produk (*Time-to-Market*) menjadi prioritas utama tanpa beban pemeliharaan klaster OS dan orkestrator kontainer yang berat.

---

## 14. When NOT To Use
Jangan gunakan paradigma ini ketika:
- Sistem menjalankan beban kerja komputasi berat secara non-stop 24/7 (misalnya pemrosesan video rendering terus menerus, model LLM training, atau komputasi grid finansial) — klaster Amazon ECS/EKS dengan EC2 Spot Instances jauh lebih hemat biaya.
- Aplikasi memerlukan latensi ultra-rendah tingkat perangkat keras (< 2 milidetik pada persentil p99.9) di mana cold start Lambda tidak dapat ditoleransi sama sekali.
- Arsitektur mewajibkan transaksi berbasis ACID terdistribusi secara kaku dalam satu *single monolithic transaction boundary* tanpa toleransi model *eventual consistency*.

---

## 15. Common Mistakes
1. **Underestimating Visibility Timeout**: Mengatur `VisibilityTimeout` pada antrean SQS lebih kecil dari Lambda `Timeout`. Hal ini menyebabkan pesan yang sedang diproses oleh Lambda aktif diambil kembali oleh Lambda lain, mengakibatkan pemrosesan ganda (*duplicate execution*). Aturan baku: **Visibility Timeout SQS $\ge$ 6 $\times$ Lambda Timeout**.
2. **Lambda Inside VPC Misconfiguration**: Menempatkan Lambda di private VPC tanpa menyediakan VPC Endpoints (PrivateLink) atau NAT Gateway, menyebabkan Lambda tidak dapat mengakses AWS Services publik seperti SSM Parameter Store, SQS, atau DynamoDB, memicu *function timeout*.
3. **Lambda Monolith (Fat Lambda)**: Mengemas seluruh rute REST API ke dalam satu fungsi Lambda berukuran ratusan megabyte. Ini memperburuk durasi cold start dan melanggar prinsip isolasi hak akses IAM.
4. **Tidak Menggunakan Exponential Backoff dengan Jitter**: Melakukan retry panggilan downstream secara kaku setiap interval waktu tetap. Ini memicu fenomena *Thundering Herd* yang merobohkan downstream service yang baru pulih.
5. **Mengabaikan Idempotency**: Mengasumsikan antrean pesan menjamin *exactly-once delivery*. Pada sistem terdistribusi riil, kegagalan jaringan acak menyebabkan transmisi ulang (*at-least-once*), sehingga ketiadaan *Idempotency Key* memicu tagihan pembayaran ganda.

---

## 16. Best Practices
- **Implementasikan Idempotency Native**: Gunakan pustaka seperti **AWS Lambda Powertools** untuk menyimpan status token idempoten ke Amazon DynamoDB secara atomik sebelum eksekusi mutasi state.
- **Kombinasi Reserved Concurrency dan Alerts**: Pasang `ReservedConcurrentExecutions` pada fungsi penting dan konfigurasikan CloudWatch Alarm untuk metrik `Throttles` dan `ConcurrentExecutions`.
- **Tuning Konfigurasi Memori**: Alokasi CPU pada AWS Lambda diskalakan secara linear terhadap memori (1.769 MB = 1 full vCPU). Gunakan tools seperti *AWS Lambda Power Tuning* untuk menemukan titik temu optimal antara biaya (cost) dan durasi (execution speed).
- **Connection Reuse**: Inisialisasi koneksi database, HTTP clients, dan AWS SDK clients di luar handler (`global scope`) untuk memanfaatkan microVM container reuse antar-pemanggilan warm.
- **Manfaatkan DLQ Redrive**: Gunakan fitur SQS Dead-Letter Queue Redrive untuk memindahkan pesan yang telah diperbaiki langsung dari DLQ kembali ke source queue via AWS Console/CLI.

---

## 17. Troubleshooting

| Gejala Masalah | Akar Masalah Potensial | Langkah Remediasi Terstruktur |
| :--- | :--- | :--- |
| **HTTP 504 Endpoint Request Timed-out** pada API Gateway | Durasi backend (Lambda/HTTP) melebihi limit keras API Gateway (29 detik untuk REST/HTTP API). | Pindahkan proses berat ke pola asinkron: API Gateway $\rightarrow$ SQS $\rightarrow$ Background Lambda, kembalikan HTTP `202 Accepted` secara cepat. |
| **Lambda `ThrottlingException` (HTTP 429)** | Concurrency fungsi mencapai batas `ReservedConcurrency` atau kuota regional akun habis. | Tingkatkan Service Quotas untuk regional concurrency; implementasikan SQS di depan Lambda untuk menyerap lonjakan trafik (*buffer*). |
| **Pesan Terus Berputar di SQS dan Menumpuk** (*Poison Pill*) | Payload JSON tidak valid atau bug pada kode downstream yang menyebabkan eksekusi crash tanpa error handling. | Periksa CloudWatch Logs; konfigurasikan DLQ dengan `maxReceiveCount` $\le 5$ agar pesan bermasalah diisolasi dari antrean utama. |
| **Koneksi Database RDS Habis (*Too many connections*)** | Concurrency Lambda meningkat tajam, setiap microVM membuka connection pool baru ke database. | Terapkan **Amazon RDS Proxy** di antara Lambda dan database; batasi `ReservedConcurrency` pada Lambda worker database. |
| **EventBridge Rule Tidak Memicu Target** | Skema filter pada Event Pattern tidak cocok (*mismatch* tipe data numerik vs string) atau Resource Policy EventBridge/Target hilang. | Gunakan CloudWatch Metric `FailedInvocations` pada EventBridge; uji event pattern menggunakan EventBridge Sandbox tool pada konsol AWS. |

---

## 18. Exercise
**Skenario Latihan**:
1. Buat sebuah SQS Queue bernama `user-registration-queue.fifo` dengan fitur FIFO diaktifkan dan `ContentBasedDeduplication` disetel ke `true`.
2. Buat sebuah fungsi Lambda sederhana (Python 3.11) bernama `process-user-registration` yang mengeksekusi simulasi pembuatan profil pengguna dan sengaja melempar exception jika username adalah `"error_user"`.
3. Hubungkan antrean ke Lambda menggunakan Event Source Mapping dengan batch size = 5.
4. Kirimkan pesan percobaan berikut menggunakan AWS CLI:
```bash
aws sqs send-message \
    --queue-url <QUEUE_URL> \
    --message-body '{"username": "error_user", "email": "err@corp.internal"}' \
    --message-group-id "user_group_1"
```
5. Amati perilaku percobaan ulang di AWS CloudWatch Logs, lalu verifikasi perpindahan pesan ke DLQ setelah jumlah retry terlampaui.

---

## 19. Challenge
Rancang arsitektur nir-server berstandar produksi untuk sistem *Payment Processing Gateway* yang mematuhi kepatuhan regulasi finansial:
1. **Persyaratan**:
   - Endpoint menerima request pembayaran via API Gateway HTTP API.
   - Pembayaran harus diproses dalam waktu < 3 detik.
   - Jika downstream provider bank merespons dengan timeout, sistem harus melakukan *retry* dengan formula Full Jitter Exponential Backoff sebanyak 3 kali.
   - Jika pembayaran gagal total, seluruh mutasi kredit sementara pada dompet akun pelanggan harus dibatalkan (*compensated*) secara atomik.
   - Setiap mutasi finansial wajib dicatat ke antrean audit trail yang tidak boleh kehilangan satu pesan pun (*zero data loss guarantee*).
2. **Keluaran yang Diharapkan**:
   - Sketsa diagram arsitektur komponen AWS.
   - Definisi State Machine Step Functions (ASL - Amazon States Language) yang mencakup penanganan blok `Catch` dan `Retry`.

---

## 20. Summary
- **AWS Lambda** menyediakan unit komputasi elastis; optimasi cold start dapat dicapai dengan runtime efisien, inisialisasi koneksi di luar handler, serta pemanfaatan Provisioned Concurrency atau SnapStart.
- **Amazon API Gateway** bertindak sebagai gerbang terdepan: gunakan **HTTP API** untuk kebutuhan modern yang mengutamakan latensi dan efisiensi biaya, serta **REST API** saat membutuhkan fitur enterprise seperti WAF dan usage plans terkelola.
- **Amazon SQS** dan **SNS** adalah fondasi decoupling: SQS mengontrol kecepatan konsumsi data (*load leveling*), sedangkan SNS mengeksekusi distribusi *fan-out* satu-ke-banyak.
- **Amazon EventBridge** memfasilitasi integrasi event berbasis konten yang luas di seluruh sistem perusahaan dengan kemampuan schema validation dan event replay.
- **AWS Step Functions** memimpin orkestrasi transaksi kompleks lintas microservices melalui implementasi **Saga Pattern**, menjamin integritas data terdistribusi tanpa memerlukan resource locking yang rapuh.

---