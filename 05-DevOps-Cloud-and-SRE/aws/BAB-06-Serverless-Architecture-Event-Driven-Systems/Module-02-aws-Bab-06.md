# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 06: Serverless Architecture & Event-Driven Systems**
**Kategori: 05-DevOps-Cloud-and-SRE | Topik: AWS**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis Internal Runtime AWS Lambda**: Membedakan fase siklus hidup Lambda (*Init, Invoke, Shutdown*), mekanisme isolasi *Firecracker microVM*, alokasi vCPU/memori, serta mitigasi *cold start* via *Provisioned Concurrency* dan *Lambda SnapStart*.
2. **Merancang Topologi Event-Driven Architecture (EDA)**: Mengombinasikan pola *Choreography* (Amazon EventBridge, SNS, SQS) dan *Orchestration* (AWS Step Functions) untuk alur kerja terdistribusi dengan toleransi kegagalan tinggi.
3. **Mengimplementasikan Idempotensi dan Kontrak Event**: Menerapkan pola idempotensi tingkat aplikasi menggunakan *AWS Lambda Powertools* dan *DynamoDB conditional writes*, serta validasi skema pesan pada *EventBridge Schema Registry*.
4. **Membangun Pipeline Pemrosesan Asinkron Skala Enterprise**: Menerapkan AWS CDK v2 (TypeScript) untuk men-deploy arsitektur produksi yang menangani *poison-pill messages*, *backpressure*, *circuit breaking*, dan *Distributed Tracing* (AWS X-Ray).
5. **Mengoptimalkan Performa dan Biaya**: Mengaudit *cost-performance trade-offs* antara *Step Functions Standard vs. Express*, pola *Polling vs. Push*, serta alokasi memori Lambda berbasis *power-tuning*.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
* Konsep dasar komputasi awan AWS (IAM roles & policies, VPC networking, Security Groups, Subnets).
* Dasar-dasar AWS Lambda, Amazon API Gateway, dan Amazon DynamoDB.
* Pemrograman TypeScript/Node.js atau Python tingkat intermediate.
* Konsep dasar arsitektur terdistribusi: *CAP Theorem, Eventual Consistency, RPC vs. Messaging*.
* Penggunaan CLI: AWS CLI v2 terkonfigurasi, Node.js (v18+ LTS), AWS CDK CLI (`npm install -g aws-cdk`), dan Docker daemon terpasang lokal.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1. Anatomi Runtime AWS Lambda & Firecracker MicroVM

AWS Lambda mengeksekusi kode di dalam lingkungan komputasi terisolasi berbasis **Firecracker**—sebuah Virtual Machine Monitor (VMM) berbasis Kernel-based Virtual Machine (KVM) yang dirancang khusus untuk beban kerja *serverless* dan *container*.

```
+-------------------------------------------------------------------------+
| AWS EC2 Bare-Metal Instance (e.g., i3.metal / c5.metal)                 |
|                                                                         |
|  +---------------------------+       +-------------------------------+  |
|  | Firecracker MicroVM Slot 1|       | Firecracker MicroVM Slot 2    |  |
|  |                           |       |                               |  |
|  |  +---------------------+  |       |  +-------------------------+  |  |
|  |  | Guest OS Kernel     |  |       |  | Guest OS Kernel         |  |  |
|  |  +---------------------+  |       |  +-------------------------+  |  |
|  |  | Lambda Runtime API  |  |       |  | Lambda Runtime API      |  |  |
|  |  +---------------------+  |       |  +-------------------------+  |  |
|  |  | Function Handler    |  |       |  | Function Handler        |  |  |
|  |  | (Init -> Invoke)    |  |       |  | (Warm Invoke)           |  |  |
|  |  +---------------------+  |       |  +-------------------------+  |  |
|  |  | Extensions (Internal)| |       |  | Extensions (Internal)   |  |  |
|  +---------------------------+       +-------------------------------+  |
|               ^                                       ^                 |
|               |                                       |                 |
|  +-------------------------------------------------------------------+  |
|  | Host OS (Linux) / KVM API                                         |  |
|  +-------------------------------------------------------------------+  |
|  | Lambda Worker Manager Agent (Placement, Isolation, Cgroup/Seccomp)|  |
+-------------------------------------------------------------------------+
```

#### Alur Kerja Runtime Lifecycle:
1. **Fase INIT**:
   * *Extension Init*: Menginisialisasi *internal/external extensions* (monitoring agents, secret fetchers).
   * *Runtime Init*: Menjalankan runtime (Node.js engine, Python interpreter, JVM).
   * *Function Init*: Mengeksekusi kode di luar handler fungsi (membuat koneksi database, *instantiate AWS SDK clients*).
   * Fase ini dibatasi maksimal 10 detik. Jika melebihi, runtime di-terminate dan diulang.
2. **Fase INVOKE**:
   * Handler dieksekusi dengan event payload.
   * Batas eksekusi: 1 ms hingga 900 detik (15 menit).
   * Runtime membekukan (*freezes*) proses eksekusi setelah handler mengembalikan respons jika tidak ada invocations berikutnya yang antre.
3. **Fase SHUTDOWN**:
   * Terjadi ketika container di-*reap* karena idle, update konfigurasi, atau instance recycling.
   * Runtime memberikan waktu 300 ms (atau hingga 2 detik untuk external extensions) untuk operasi *graceful cleanup*.

#### Alokasi Sumber Daya:
Lambda mengalokasikan kapasitas CPU secara proporsional linier terhadap konfigurasi memori (128 MB hingga 10,240 MB). 
* Pada **1,769 MB**, fungsi mendapatkan ekuivalen persis **1 full vCPU**.
* Di atas 1,769 MB, Lambda mengaktifkan thread komputasi multi-core (hingga 6 vCPU pada 10 GB). Mengonfigurasi fungsi *single-threaded* di atas 1.7 GB sering kali membuang-buang biaya tanpa peningkatan throughput.

---

### 3.2. EventBridge Routing Engine Internals

Amazon EventBridge menggunakan *content-based filtering engine* berperforma tinggi. Bus tidak sekadar mencocokkan string, melainkan mem-parsing atribut JSON menggunakan *state machine / rule-trie index*.

* **Rule Evaluation**: Setiap event yang masuk dievaluasi secara serentak terhadap seluruh aturan aktif pada event bus dalam waktu sub-milidetik.
* **Payload Constraints**: Batas payload maksimum adalah **256 KB**. Event yang melebihi ukuran ini harus menggunakan pola **Claim Check Pattern** (simpan payload di S3, kirim metadata/URI melalui EventBridge).
* **Delivery Guarantees**: *At-least-once delivery* ke targets. Duplikasi dapat terjadi dalam kondisi partisi jaringan atau retries internal, mewajibkan target memiliki lapisan idempotensi.

---

### 3.3. Orchestration vs. Choreography

| Dimensi Arsitektur | Orchestration (AWS Step Functions) | Choreography (EventBridge / SNS / SQS) |
| :--- | :--- | :--- |
| **Pola Komunikasi** | Terpusat (*Point-to-Point Control*) | Terdesentralisasi (*Publish-Subscribe / Pipeline*) |
| **Status State** | *Stateful* (Dikelola penuh oleh state machine) | *Stateless* (State didistribusikan antar service) |
| **Visibilitas Alur** | Visual execution graph terpusat, audit trail lengkap | Terdistribusi (Membutuhkan trace IDs/X-Ray) |
| **Coupling** | *Tight Coupling* terhadap skema orkestrasi | *Loose Coupling* (Produser tidak mengenal konsumen) |
| **Use Case Utama** | Saga pattern, alur checkout, pemulihan transaksi terdistribusi | Integrasi antar-domain, audit log, webhook ingest |

---

## 4. Why & What

### Mengapa Beralih ke Advanced Serverless & EDA?
Pada arsitektur monolitik atau microservices berbasis HTTP/REST murni:
1. **Cascading Failures**: Ketergantungan sinkron blocking (*request-response chain*) menyebabkan satu layanan yang lambat menghabiskan thread pool hulu (*thread pool exhaustion*).
2. **Resource Inefficiency**: Server provisioning untuk menangani beban puncak menghasilkan pemborosan hingga 70-80% pada periode sepi.
3. **Complex State Management**: Mengelola transaksi lintas microservices dengan database terpisah memicu inkonsistensi data ketika node gagal di tengah jalan.

### Solusi Arsitektur
Dengan mengimplementasikan **Event-Driven Architecture (EDA)** lanjutan:
* **Decoupling Temporal**: Produser dan konsumen beroperasi pada laju yang independen. Konsumen yang down tidak menghentikan produser (antrean ditahan di buffer SQS/EventBridge).
* **Self-Healing State Machines**: AWS Step Functions mengimplementasikan *Saga Pattern* dengan *Compensating Transactions* secara native tanpa perlu menulis *boilerplate state management*.
* **Fine-Grained Concurrency Control**: Lambda concurrency limits mencegah downstream systems (seperti database relasional RDS) dari fenomena *Denial of Service* internal via *Reserved Concurrency*.

---

## 5. How (Workflow Detail)

Alur kerja pemrosesan pesanan enterprise berkecepatan tinggi:

1. **Ingestion Layer**: API Gateway menerima pesanan, memvalidasi JSON schema dasar, dan langsung meneruskannya ke Amazon EventBridge (`PutEvents`) secara asinkron tanpa memanggil Lambda perantara (*direct service integration*).
2. **Event Routing**: EventBridge rule memfilter event `OrderPlaced` dan mengirimkannya ke Amazon SQS FIFO Queue untuk menjaga urutan transaksional per `customerId`.
3. **Throttled Consumer**: AWS Lambda membaca pesan dari SQS via *Event Source Mapping (ESM)* dengan *batch size* terkalibrasi dan *concurrency limit* yang disesuaikan dengan kapasitas database downstream.
4. **Orchestration Execution**: Untuk setiap batch yang valid, Lambda memicu *AWS Step Functions Express/Standard Workflow* guna mengeksekusi orkestrasi transaksi:
   * *Reserve Inventory* (DynamoDB Transaction).
   * *Process Payment* (External Gateway with retry and exponential backoff).
   * *Emit OrderFulfilled event* ke EventBridge.
5. **Exception Handling**: Jika pembayaran gagal atau inventaris habis, Step Functions mengeksekusi cabang kompensasi (*Compensating Transaction*), mengembalikan status stok, mempublikasikan event `OrderFailed`, dan mengirim payload eror ke *Dead-Letter Queue (DLQ)*.

---

## 6. Analogy & Diagram ASCII

### Analogi Dunia Nyata: Dapur Restoran Bintang Lima
* **EventBridge (Head Waiter / Maitre D')**: Menerima pesanan dari meja, membaca jenis pesanan, lalu menempelkan tiket ke papan masing-masing stasiun kerja (Grill, Pastry, Minuman) tanpa menunggu makanan selesai dimasak.
* **SQS (Antrean Tiket Pesanan)**: Menahan tiket pesanan secara berurutan. Koki mengambil tiket hanya jika tangannya sudah kosong, mencegah dapur kewalahan (*backpressure handling*).
* **AWS Lambda (Koki Spesialis)**: Masuk ke dapur saat tiket ada, menyiapkan bahan, memasak, lalu membersihkan meja kerja. Jika pesanan sepi, koki beristirahat (*scale to zero*).
* **Step Functions (Standard Operating Procedure / Check-sheet Terpadu)**: Lembar panduan resep langkah-demi-langkah. Jika daging gosong (error), SOP mewajibkan langkah kompensasi: buang daging gosong, ambil daging baru, catat log *waste*, atau kembalikan uang tamu.

### Diagram Arsitektur Produksi

```
  [ Client Application ]
            |
            v  (HTTPS POST /orders)
  +--------------------+
  | Amazon API Gateway | (Direct Service Integration, Zero-Compute Ingest)
  +--------------------+
            |
            v  (PutEvents)
+========================================================================+
|                       Amazon EventBridge Bus                           |
+========================================================================+
     |                                                  |
     | (Rule: Source="ecommerce.orders")                | (Rule: Event="OrderFailed")
     v                                                  v
+------------------------+                     +------------------------+
|   Amazon SQS FIFO      |                     | Amazon SNS Ops Alert   |
|   (Decoupling/Buffer)  |                     +------------------------+
+------------------------+                                  |
     |                                                      v
     | (Event Source Mapping - Batch 10)         [ PagerDuty / SRE On-Call]
     v
+------------------------+      Failure (Max Retries)
|   AWS Lambda Consumer  | -----------------------------> +--------------------+
|  (Powertools Validated)|                                | SQS Dead Letter Q  |
+------------------------+                                +--------------------+
     |
     v (StartSyncExecution / StartExecution)
+========================================================================+
|                     AWS Step Functions (Order Saga)                   |
|                                                                        |
|    +-------------------+                                               |
|    | Reserve Inventory | (DynamoDB TransactWriteItems)                 |
|    +-------------------+                                               |
|              | Success                                                 |
|              v                                                         |
|    +-------------------+       Failure        +--------------------+   |
|    |  Process Payment  | -------------------> | Rollback Inventory |   |
|    +-------------------+ (Retry 3x Backoff)   +--------------------+   |
|              | Success                                  |              |
|              v                                          v              |
|    +-------------------+                      +--------------------+   |
|    | Emit SuccessEvent |                      |  Emit FailedEvent  |   |
|    +-------------------+                      +--------------------+   |
+========================================================================+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Lambda Idempotent Handler (AWS Lambda Powertools)

File: `handlers/simple-idempotent.py`
Handler ini memastikan pemrosesan transaksi tidak mengalami *double-billing* meskipun event dikirim berkali-kali oleh mekanisme retry SQS/EventBridge.

```python
import os
import json
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.idempotency import (
    DynamoDBPersistenceLayer,
    idempotent,
    IdempotencyConfig
)

logger = Logger(service="payment-processor")
tracer = Tracer(service="payment-processor")

# Konfigurasi persistence layer idempotency menggunakan DynamoDB
persistence_layer = DynamoDBPersistenceLayer(
    table_name=os.environ["IDEMPOTENCY_TABLE_NAME"]
)
idempotency_config = IdempotencyConfig(
    event_key_jmespath="body.transaction_id", # Field penentu unik
    expires_after_seconds=3600               # Masa berlaku token idempotensi
)

@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@idempotent(config=idempotency_config, persistence_store=persistence_layer)
def handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        transaction_id = body["transaction_id"]
        amount = body["amount"]

        logger.info(f"Processing transaction: {transaction_id} for amount: {amount}")

        # Logika bisnis kritis (misal: panggil gateway perbankan)
        result = {
            "status": "COMPLETED",
            "transaction_id": transaction_id,
            "processed_amount": amount,
            "auth_code": "AUTH_99881122"
        }
        
        return {
            "statusCode": 200,
            "body": json.dumps(result)
        }
    except KeyError as e:
        logger.error(f"Missing required parameter: {str(e)}")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"Invalid payload schema: {str(e)}"})
        }
```

---

### 7.2. Practical Example: Production-Grade Infrastructure via AWS CDK v2

Implementasi arsitektur produksi menggunakan AWS CDK (TypeScript). Mencakup EventBridge Custom Bus, DLQ, SQS FIFO, Lambda dengan Powertools layer, dan Step Functions State Machine.

#### File: `infra/lib/serverless-pipeline-stack.ts`

```typescript
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as lambdaEventSources from 'aws-cdk-lib/aws-lambda-event-sources';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import * as path from 'path';

export class ServerlessPipelineStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // 1. Storage & State: DynamoDB Tables
    const ordersTable = new dynamodb.Table(this, 'OrdersTable', {
      partitionKey: { name: 'orderId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // Ubah ke RETAIN untuk produksi riil
      pointInTimeRecovery: true,
    });

    const idempotencyTable = new dynamodb.Table(this, 'IdempotencyTable', {
      partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
      timeToLiveAttribute: 'expiration',
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // 2. Dead-Letter Queue (DLQ) & Main Processing SQS FIFO Queue
    const deadLetterQueue = new sqs.Queue(this, 'OrderProcessingDLQ.fifo', {
      fifo: true,
      contentBasedDeduplication: true,
      retentionPeriod: cdk.Duration.days(14),
    });

    const orderQueue = new sqs.Queue(this, 'OrderProcessingQueue.fifo', {
      fifo: true,
      contentBasedDeduplication: true,
      visibilityTimeout: cdk.Duration.seconds(300),
      deadLetterQueue: {
        maxReceiveCount: 3,
        queue: deadLetterQueue,
      },
    });

    // 3. Central EventBridge Custom Bus
    const eventBus = new events.EventBus(this, 'EnterpriseEventBus', {
      eventBusName: 'ecommerce-enterprise-bus',
    });

    // EventBridge Rule: Meneruskan order event ke SQS FIFO
    new events.Rule(this, 'OrderPlacedRule', {
      eventBus: eventBus,
      eventPattern: {
        source: ['ecommerce.checkout'],
        detailType: ['OrderPlaced'],
      },
      targets: [
        new targets.SqsQueue(orderQueue, {
          messageGroupId: 'OrderGroup',
        }),
      ],
    });

    // 4. AWS Step Functions Saga Orchestration
    const reserveInventoryTask = new tasks.DynamoUpdateItem(this, 'ReserveInventory', {
      table: ordersTable,
      key: { orderId: tasks.DynamoAttributeValue.fromString(sfn.JsonPath.stringAt('$.orderId')) },
      updateExpression: 'SET #st = :status, inventoryStatus = :inv',
      expressionAttributeNames: { '#st': 'status' },
      expressionAttributeValues: {
        ':status': tasks.DynamoAttributeValue.fromString('INVENTORY_RESERVED'),
        ':inv': tasks.DynamoAttributeValue.fromString('ALLOCATED'),
      },
      resultPath: '$.inventoryResult',
    });

    const releaseInventoryTask = new tasks.DynamoUpdateItem(this, 'CompensateInventory', {
      table: ordersTable,
      key: { orderId: tasks.DynamoAttributeValue.fromString(sfn.JsonPath.stringAt('$.orderId')) },
      updateExpression: 'SET #st = :status, inventoryStatus = :inv',
      expressionAttributeNames: { '#st': 'status' },
      expressionAttributeValues: {
        ':status': tasks.DynamoAttributeValue.fromString('INVENTORY_RELEASED'),
        ':inv': tasks.DynamoAttributeValue.fromString('RESTOCKED'),
      },
      resultPath: sfn.JsonPath.DISCARD,
    });

    const emitSuccessEvent = new tasks.EventBridgePutEvents(this, 'EmitOrderProcessedEvent', {
      entries: [
        {
          eventBus: eventBus,
          source: 'ecommerce.ordersaga',
          detailType: 'OrderFulfilled',
          detail: sfn.TaskInput.fromJsonPathAt('$'),
        },
      ],
      resultPath: sfn.JsonPath.DISCARD,
    });

    const workflowDefinition = reserveInventoryTask
      .addCatch(releaseInventoryTask, {
        errors: ['States.ALL'],
        resultPath: '$.sagaError',
      })
      .next(emitSuccessEvent);

    const sagaStateMachine = new sfn.StateMachine(this, 'OrderSagaStateMachine', {
      definitionBody: sfn.DefinitionBody.fromChainable(workflowDefinition),
      stateMachineType: sfn.StateMachineType.EXPRESS, // Latency rendah, throughput tinggi
      timeout: cdk.Duration.seconds(60),
    });

    // 5. Worker Lambda Function (SQS Consumer)
    const workerLambda = new lambda.Function(this, 'OrderProcessorFunction', {
      runtime: lambda.Runtime.NODEJS_20_X,
      architecture: lambda.Architecture.ARM_64, // Graviton2 untuk efisiensi biaya & performa
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../lambda/order-consumer')),
      memorySize: 1024,
      timeout: cdk.Duration.seconds(60),
      environment: {
        STATE_MACHINE_ARN: sagaStateMachine.stateMachineArn,
        IDEMPOTENCY_TABLE_NAME: idempotencyTable.tableName,
        POWERTOOLS_SERVICE_NAME: 'OrderProcessor',
        NODE_OPTIONS: '--enable-source-maps',
      },
      tracing: lambda.Tracing.ACTIVE,
    });

    // Grant permissions
    idempotencyTable.grantReadWriteData(workerLambda);
    sagaStateMachine.grantStartSyncExecution(workerLambda);

    // Sambungkan Lambda ke SQS Queue
    workerLambda.addEventSource(
      new lambdaEventSources.SqsEventSource(orderQueue, {
        batchSize: 5,
        maxBatchingWindow: cdk.Duration.seconds(2),
        reportBatchItemFailures: true, // Granular partial failure reporting
      })
    );
  }
}
```

#### File: `lambda/order-consumer/index.ts`

```typescript
import { SQSBatchResponse, SQSEvent, SQSHandler, SQSRecord } from 'aws-lambda';
import { SFNClient, StartSyncExecutionCommand } from '@aws-sdk/client-sfn';
import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient, PutCommand } from '@aws-sdk/lib-dynamodb';

const sfnClient = new SFNClient({});
const ddbClient = DynamoDBDocumentClient.from(new DynamoDBClient({}));

const STATE_MACHINE_ARN = process.env.STATE_MACHINE_ARN!;
const IDEMPOTENCY_TABLE_NAME = process.env.IDEMPOTENCY_TABLE_NAME!;

export const handler: SQSHandler = async (event: SQSEvent): Promise<SQSBatchResponse> => {
  const batchItemFailures: { itemIdentifier: string }[] = [];

  for (const record of event.Records) {
    try {
      await processMessage(record);
    } catch (error) {
      console.error(`Failed to process message ID ${record.messageId}:`, error);
      // Masukkan ID pesan yang gagal ke array partial failure
      // Pesan ini tidak di-delete dari queue dan akan di-retry oleh SQS
      batchItemFailures.push({ itemIdentifier: record.messageId });
    }
  }

  return { batchItemFailures };
};

async function processMessage(record: SQSRecord): Promise<void> {
  const body = JSON.parse(record.body);
  const detail = body.detail || body;
  const orderId = detail.orderId;

  if (!orderId) {
    throw new Error('Schema Validation Error: orderId missing from detail');
  }

  // 1. Atomic Idempotency Check: Conditional Write ke DynamoDB
  const now = Math.floor(Date.now() / 1000);
  const ttl = now + 86400; // 24 jam TTL

  try {
    await ddbClient.send(
      new PutCommand({
        TableName: IDEMPOTENCY_TABLE_NAME,
        Item: {
          id: `ORDER#${orderId}`,
          status: 'PROCESSING',
          timestamp: now,
          expiration: ttl,
        },
        ConditionExpression: 'attribute_not_exists(id)',
      })
    );
  } catch (err: any) {
    if (err.name === 'ConditionalCheckFailedException') {
      console.warn(`Idempotency hit: Order ${orderId} is already being processed or completed. Skipping.`);
      return; // Skip duplicate message safely
    }
    throw err;
  }

  // 2. Eksekusi Synchronous Express Step Function
  const response = await sfnClient.send(
    new StartSyncExecutionCommand({
      stateMachineArn: STATE_MACHINE_ARN,
      input: JSON.stringify({
        orderId: orderId,
        amount: detail.amount,
        items: detail.items,
        timestamp: new Date().toISOString(),
      }),
    })
  );

  if (response.status !== 'SUCCEEDED') {
    throw new Error(`State machine execution failed with status: ${response.status}. Cause: ${response.cause}`);
  }

  console.log(`Successfully completed saga for order: ${orderId}`);
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Flash Sale E-Commerce Tier-1 (100.000 TPS Surge)
* **Konteks**: Platform retail berskala internasional menyelenggarakan festival belanja tahunan dengan prediksi lonjakan transaksi dari baseline 2.000 TPS menjadi 100.000 TPS dalam rentang 3 detik saat flash sale dibuka.
* **Tantangan Arsitektur**:
  1. *Relational DB Bottleneck*: Database Aurora PostgreSQL utama hanya mampu menangani maksimal 8.000 write connections bersamaan sebelum mengalami *connection pooling starvation*.
  2. *Cold Start Latency*: Peningkatan masif instansiasi Lambda dapat mengakibatkan *cold start spikes* hingga ribuan milidetik.
  3. *Thundering Herd Problem*: Ratusan ribu pengguna menekan tombol "Beli" secara simultan untuk kuantitas produk yang terbatas (misal: 5.000 unit PlayStation 5).

### Implementasi Solusi Terpadu:
1. **Zero-Compute Ingest**: API Gateway memetakan payload langsung ke EventBridge Bus melalui *VPC endpoint integration* tanpa perantara Lambda layer, menghilangkan risiko cold start pada lapisan penerimaan.
2. **Buffering dengan SQS FIFO Partition Keys**: Pesanan diarahkan ke antrean SQS FIFO. `MessageGroupId` diset menggunakan formula `hash(productId) % 50`. Ini menyebarkan beban ke 50 partisi independen tanpa melanggar keterurutan modifikasi stok per produk.
3. **Lambda Concurrency Throttling**: Event Source Mapping dikonfigurasi dengan *Maximum Concurrency* bernilai 400. Ini membatasi konkurensi maksimum fungsi Lambda agar tidak melebihi batas koneksi Aurora melalui AWS RDS Proxy.
4. **DynamoDB Transactional Cache**: Pengurangan stok diverifikasi secara atomik pada DynamoDB menggunakan ekspresi kondisional:
   `attribute_exists(itemId) AND stock >= :qtyRequested`.
5. **Express Step Functions**: Orkestrasi pemrosesan pembayaran dan alokasi logistik dijalankan via Step Functions Express Workflow dengan latensi rata-rata p99 di bawah 450 ms.

### Hasil Metrik Produksi:
* **Availability**: 99.999% selama periode event 4 jam.
* **Zero Data Loss**: 0 dropped messages berkat buffer SQS yang menampung lonjakan antrean hingga kedalaman 1,2 juta pesan.
* **Downstream Safety**: Utilisasi CPU Aurora PostgreSQL terjaga stabil pada 68% berkat kontrol *backpressure* Lambda ESM.

---

## 9. Trade-offs

```
                  [ ARSITEKTUR SERVERLESS ]
                             |
       +---------------------+---------------------+
       |                                           |
  [ Asynchronous Push ]                   [ Buffered Pull ]
  (EventBridge / SNS)                      (SQS / Kinesis)
       |                                           |
  +----+----+                                 +----+----+
  |         |                                 |         |
Pros:     Cons:                             Pros:     Cons:
- Ultra   - Sulit backpressure              - Kontrol - Polling delay
  low       control                           debit     (1-2 detik)
  latency - Potensi membanjiri                beban   - Overhead
- No        downstream DB                   - Aman      manajemen
  buffer    services                          untuk     antrean
  cost                                        DB RDBMS
```

| Parameter | AWS Step Functions (Standard) | AWS Step Functions (Express) | SQS + Direct Lambda (Choreography) |
| :--- | :--- | :--- | :--- |
| **Pricing Model** | $0.025 per 1.000 State Transitions | $1.00 per juta eksekusi + Durasi memori | $0.40 per 1M SQS reqs + Biaya Lambda runtime |
| **Durasi Maksimal** | 1 Tahun | 5 Menit | 15 Menit (Batas runtime Lambda) |
| **Execution Semantics** | *Exactly-once* per state execution | *At-least-once* (Asynchronous) / *At-most-once* (Synchronous) | *At-least-once* |
| **Audit & Visual UI** | Penuh (Setiap event historis tersimpan detail) | CloudWatch Logs murni (Tanpa visual graph interaktif) | AWS X-Ray Trace Graph |
| **Throughput Limit** | ~2.000 execution starts/detik | >100.000 execution starts/detik | Tergantung Lambda Concurrency Quotas |

---

## 10. Common Mistakes & Troubleshooting

### 1. The Lambda-in-VPC Cold Start Myth & Real Misconfiguration
* **Kesalahan**: Mengasumsikan Lambda lambat karena VPC cold start. Sejak AWS memperbarui arsitektur VPC Lambda menggunakan AWS Hyperplane (2019), ENI dipasang saat fungsi dibuat/diupdate, bukan saat invocations.
* **Penyebab Sebenarnya**: Cold start lambat (10-15 detik) hampir selalu diakibatkan oleh:
  * Inisialisasi SDK klien yang berat di dalam function scope (seharusnya di global scope).
  * Resolusi DNS internal VPC yang lambat atau dependensi eksternal yang diblokir oleh NAT Gateway/Security Group yang keliru.
* **Solusi**: Letakkan koneksi DB/klien SDK di luar handler (*global context reuse*). Gunakan *Lambda SnapStart* (untuk Java) atau arsitektur kompilasi esbuild/minify (Node.js).

### 2. SQS FIFO Deadlock karena Poison Pill
* **Masalah**: Pesanan korup (*poison pill*) berada di urutan terdepan SQS FIFO. Karena urutan pesan dalam satu `MessageGroupId` harus ketat, kegagalan berulang pada pesan tersebut memblokir ribuan pesan valid lainnya di belakangnya.
* **Troubleshooting**:
  * Periksa metrik `ApproximateAgeOfOldestMessage` di CloudWatch. Jika nilainya melonjak naik secara linear, antrean mengalami stall.
* **Solusi**:
  1. Aktifkan DLQ dengan `maxReceiveCount` rendah (maksimal 3).
  2. Implementasikan partial batch response (`reportBatchItemFailures: true`) pada Lambda ESM agar SQS hanya me-retry pesan spesifik yang gagal tanpa membatalkan seluruh isi batch.

### 3. Database Connection Exhaustion (Lambda DoS terhadap RDS)
* **Masalah**: Lonjakan event memicu Lambda untuk scale out ke 1.000 instansiasi kontemporer, membuka 1.000 koneksi PostgreSQL secara simultan dan melumpuhkan database (`max_connections exceeded`).
* **Solusi**:
  1. Wajib gunakan **AWS RDS Proxy** di depan Aurora/RDS. Proxy melakukan *connection pooling* dan multiplexing kueri.
  2. Batasi `Reserved Concurrency` pada fungsi Lambda konsumen database tersebut.

---

## 11. Best Practices (Production Checklist)

### Security & IAM
- [ ] Terapkan prinsip *Least Privilege*: Gunakan IAM Policy terperinci dengan batasan ARN eksplisit (hindari resource `*`).
- [ ] Isolasi Credentials: Jangan simpan password DB di environment variables plaintext; gunakan IAM Database Authentication atau AWS Secrets Manager dengan caching runtime extension.
- [ ] Enkripsi: Aktifkan KMS Customer Managed Keys (CMK) pada seluruh SQS Queue, DynamoDB Table, dan EventBridge Bus.

### Resiliency & Architecture
- [ ] Setiap komponen komputasi asinkron harus memiliki Dead-Letter Queue (DLQ) tersendiri.
- [ ] Implementasikan idempotensi tingkat aplikasi di setiap fungsi konsumen menggunakan tabel DynamoDB ber-TTL.
- [ ] Konfigurasikan `reportBatchItemFailures` pada seluruh Lambda SQS Event Source Mapping.
- [ ] Terapkan *exponential backoff with full jitter* pada pemanggilan downstream API.

### Observability & Monitoring
- [ ] Aktifkan **AWS X-Ray Active Tracing** secara end-to-end (API Gateway -> EventBridge -> SQS -> Lambda -> DynamoDB).
- [ ] Gunakan **Structured Logging** (JSON) dengan parameter wajib: `trace_id`, `service`, `environment`, dan `tenant_id`.
- [ ] Set up CloudWatch Alarms untuk:
  - `ApproximateAgeOfOldestMessage` pada SQS (deteksi lag konsumsi).
  - Lambda `Throttles` dan `Errors`.
  - EventBridge `FailedInvocations`.
  - Dead-Letter Queue `ApproximateNumberOfMessagesVisible > 0`.

---

## 12. Hands-on Practice

Dalam praktikum ini, Anda akan membangun pipeline event-driven lengkap dengan AWS CDK:
* Direktori Kerja: Simpan seluruh kode pada direktori: `hands-on/m02/`

### Struktur Direktori Praktikum:
```text
hands-on/m02/
├── bin/
│   └── app.ts
├── cdk.json
├── package.json
├── tsconfig.json
├── lambda/
│   └── order-consumer/
│       └── index.ts
└── lib/
    └── serverless-pipeline-stack.ts
```

### Langkah-langkah Eksekusi:

#### 1. Inisialisasi Proyek CDK
Buka terminal dan jalankan:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
cdk init app --language=typescript
npm install @aws-sdk/client-sfn @aws-sdk/client-dynamodb @aws-sdk/lib-dynamodb
npm install aws-lambda @types/aws-lambda
```

#### 2. Implementasikan Kode CDK dan Lambda
Salin kode dari **Seksi 7.2** ke dalam file masing-masing:
* `hands-on/m02/lib/serverless-pipeline-stack.ts`
* `hands-on/m02/lambda/order-consumer/index.ts`

Pastikan file entrypoint CDK Anda mereferensikan stack dengan benar:

File: `hands-on/m02/bin/app.ts`
```typescript
#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { ServerlessPipelineStack } from '../lib/serverless-pipeline-stack';

const app = new cdk.App();
new ServerlessPipelineStack(app, 'ServerlessPipelineProductionStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
  },
});
```

#### 3. Sintesis dan Deploy CloudFormation
Jalankan kompilasi TypeScript dan deploy stack ke akun AWS Anda:
```bash
npm run build
cdk bootstrap
cdk deploy --require-approval never
```

#### 4. Uji Verifikasi Alur Event
Kirim event uji langsung ke Amazon EventBridge Custom Bus menggunakan AWS CLI:

```bash
aws events put-events --entries '[
  {
    "EventBusName": "ecommerce-enterprise-bus",
    "Source": "ecommerce.checkout",
    "DetailType": "OrderPlaced",
    "Detail": "{\"orderId\":\"ORD-88990011\",\"amount\":1500000,\"items\":[{\"id\":\"ITEM-01\",\"qty\":1}]}"
  }
]'
```

#### 5. Validasi Hasil
1. **Periksa Step Functions Execution**:
   Buka AWS Console -> Step Functions -> Pilih State Machine `OrderSagaStateMachine` -> Lihat eksekusi terbaru. Pastikan statusnya `SUCCEEDED`.
2. **Periksa DynamoDB Table**:
   Jalankan CLI untuk mengecek apakah status pesanan tersimpan:
   ```bash
   aws dynamodb get-item \
     --table-name ServerlessPipelineProductionStack-OrdersTable* \
     --key '{"orderId": {"S": "ORD-88990011"}}'
   ```
3. **Uji Idempotensi**:
   Jalankan kembali perintah `put-events` dengan `orderId` yang persis sama. Amati log CloudWatch Lambda; verifikasi bahwa transaksi dideteksi sebagai duplikat dan diabaikan tanpa error.

#### 6. Clean Up
Hancurkan resource agar tidak memicu biaya:
```bash
cdk destroy -f
```

---

## 13. Exercise

### Level Easy
Modifikasi file `ServerlessPipelineStack`:
1. Tambahkan alarm CloudWatch yang memantau metrik `ApproximateNumberOfMessagesVisible` pada antrean Dead-Letter Queue (DLQ).
2. Set threshold alarm menjadi `>= 1` pesan, dengan periode evaluasi 1 menit, yang memicu SNS Topic `DevOpsAlertsTopic`.

### Level Medium
Perluas alur *Order Saga Step Function*:
1. Tambahkan State Task baru bertipe Lambda Function: `VerifyFraudDetection`.
2. Letakkan task tersebut sebelum `ReserveInventory`.
3. Jika persentase risiko fraud > 80, lempar custom error `FraudDetectedException` dan arahkan transisi langsung ke state `FailOrder`, membatalkan seluruh operasi downstream tanpa melakukan mutasi inventory.

### Level Hard
Implementasikan **Outbox Pattern Serverless**:
1. Buat arsitektur di mana mutasi data transaksi pesanan hanya dilakukan ke Amazon DynamoDB (tanpa pemanggilan API eksternal lain secara sinkron).
2. Aktifkan **DynamoDB Streams (NEW_AND_OLD_IMAGES)** pada tabel tersebut.
3. Buat Lambda Function yang bertindak sebagai *Stream Poller* dengan filter pattern: hanya memproses operasi insert/update dengan atribut `status = "PENDING_PUBLISH"`.
4. Lambda mempublikasikan event ke EventBridge Bus. Gunakan DynamoDB conditional update untuk mengubah status menjadi `"PUBLISHED"` secara atomik guna menjamin konsistensi data 100% tanpa risiko kehilangan event jika runtime mengalami crash.

---

## 14. Challenge

### Studi Kasus: Multi-Region Active-Active Serverless Payment Processor
Sebuah institusi perbankan multinasional mewajibkan arsitektur pemrosesan pembayaran zero-downtime yang beroperasi secara *Active-Active* di dua AWS Region (`ap-southeast-1` Singapura dan `ap-southeast-3` Jakarta).

#### Kondisi Batasan Arsitektur:
1. **Konsistensi Saldo Rekening**: Nasabah dapat melakukan swipe kartu debit di terminal mana pun di dunia. Transaksi dapat mendarat di region Singapura atau Jakarta tergantung routing latensi Route 53 Geoproximity.
2. **No Double Spending**: Pengurangan saldo tidak boleh mengalami *race condition* meskipun dua otorisasi terjadi dalam interval 50 milidetik di dua region berbeda.
3. **Network Partition Tolerance**: Jika koneksi jaringan backbone inter-region AWS terputus, sistem di masing-masing region harus beralih ke mode degradasi graceful (misalnya: membatasi batas transaksi offline maksimum $100) dan merekonsiliasi data secara otomatis tanpa intervensi manual ketika partisi pulih.
4. **Latency Budget**: Latensi otorisasi p99 wajib berada di bawah 800 milidetik dari saat request menyentuh API Gateway hingga respons approval dikembalikan.

#### Tugas Rekayasa:
* Desain diagram arsitektur inter-region terperinci menggunakan DynamoDB Global Tables, EventBridge Cross-Region Targets, Route 53 ARC (Application Recovery Controller), dan Lambda.
* Tulis dokumen strategi resolusi konflik: Bagaimana menangani rekonsiliasi data jika partisi jaringan terputus selama 15 menit dan kedua region memproses mutasi saldo yang saling bertentangan secara bersamaan.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Soal)
1. **Fase siklus hidup AWS Lambda apa saja yang berjalan secara berurutan saat terjadi cold start?**
   * A. Invoke -> Init -> Shutdown
   * B. Init (Extension, Runtime, Function) -> Invoke -> Shutdown
   * C. Allocate -> Execute -> Terminate
   * D. Warmup -> Process -> CoolDown
   * *Jawaban*: B. Siklus hidup resmi Lambda terdiri dari 3 fase: INIT (yang mencakup Extension Init, Runtime Init, dan Function Init), disusul INVOKE, lalu SHUTDOWN saat container didekomposisi.

2. **Berapa alokasi kapasitas vCPU yang didapatkan oleh sebuah fungsi Lambda yang dikonfigurasikan dengan memori sebesar 1.769 MB?**
   * A. Tepat 1 vCPU
   * B. 0.5 vCPU
   * C. 2 vCPU
   * D. Bergantung pada konfigurasi concurrency
   * *Jawaban*: A. Secara internal, AWS Lambda menetapkan bahwa 1.769 MB memori setara dengan 1 vCPU komputasi dedicated.

3. **Berapa ukuran payload maksimum yang diizinkan untuk satu event yang dikirimkan ke Amazon EventBridge?**
   * A. 64 KB
   * B. 1 MB
   * C. 256 KB
   * D. 512 KB
   * *Jawaban*: C. Ukuran payload maksimal Amazon EventBridge adalah 256 KB.

4. **Jenis AWS Step Functions workflow apa yang paling tepat digunakan untuk beban kerja e-commerce dengan volume jutaan eksekusi per jam yang memerlukan latensi rendah?**
   * A. Standard Workflows
   * B. Long-Running Workflows
   * C. Express Workflows
   * D. Dynamic Workflows
   * *Jawaban*: C. Express Workflows dirancang khusus untuk throughput tinggi (hingga 100k+ eksekusi/detik), latensi sangat rendah, dan penagihan berdasarkan runtime serta memori.

5. **Apa fungsi parameter `reportBatchItemFailures` pada konfigurasi AWS Lambda Event Source Mapping untuk Amazon SQS?**
   * A. Menghapus pesan secara otomatis jika ukuran file terlalu besar.
   * B. Mengembalikan daftar ID spesifik pesan yang gagal dalam batch, sehingga SQS hanya me-retry pesan tersebut dan tidak mengulang pemrosesan pesan yang sukses.
   * C. Mengirim seluruh batch langsung ke DLQ jika ada minimal satu pesan yang gagal.
   * D. Menghentikan konsumsi antrean jika terjadi exception fatal.
   * *Jawaban*: B. Fitur ini mencegah duplikasi kerja dengan membiarkan Lambda memproses ulang hanya record yang gagal.

---

### Bagian 2: Intermediate (5 Soal)
6. **Pada arsitektur SQS FIFO, apa implikasi penggunaan `MessageGroupId` yang bernilai statis sama (hardcoded) untuk seluruh pesan yang masuk?**
   * A. Pesan akan didistribusikan secara acak ke seluruh worker Lambda.
   * B. Throughput konsumsi antrean akan terhambat (*serialized*) menjadi hanya 1 proses konsumsi tunggal pada satu waktu, menurunkan performa secara drastis.
   * C. SQS FIFO akan secara otomatis mengubah dirinya menjadi Standard Queue.
   * D. Antrean akan melempar status error `QuotaExceededException`.
   * *Jawaban*: B. Pesan dalam satu `MessageGroupId` diproses secara ketat satu per satu sesuai urutan (*FIFO order*). Menggunakan group ID yang sama membatasi konkurensi menjadi 1 consumer thread.

7. **Bagaimana cara kerja mekanisme AWS Lambda SnapStart untuk memitigasi waktu cold start?**
   * A. Menjaga container tetap berjalan (*idle*) terus-menerus tanpa mematikan runtime.
   * B. Menjalankan fungsi di atas arsitektur bare metal tanpa isolasi Firecracker.
   * C. Menginisialisasi fungsi terlebih dahulu (Init phase), mengambil snapshot memori dan disk dari microVM terenkripsi, lalu me-resume snapshot tersebut saat terjadi invocation baru.
   * D. Melompati proses inisialisasi modul pihak ketiga.
   * *Jawaban*: C. Lambda SnapStart meng-cache snapshot VM yang telah diinisialisasi sehingga invocations baru hanya memerlukan resume memori sub-detik.

8. **Pernyataan mana yang benar mengenai jaminan pengiriman (*delivery guarantees*) Amazon EventBridge?**
   * A. Guaranteed Exactly-Once Delivery dalam semua kondisi.
   * B. At-Least-Once Delivery; konsumen wajib mengimplementasikan lapisan idempotensi untuk mengantisipasi duplikasi.
   * C. At-Most-Once Delivery; event akan dibuang jika target sedang sibuk.
   * D. Strict Transact-Delivery; event dibatalkan jika salah satu target gagal.
   * *Jawaban*: B. EventBridge menjamin *at-least-once delivery*, yang berarti ada probabilitas duplikasi pesan saat terjadi network timeout atau internal retry.

9. **Jika sebuah fungsi Lambda yang terkoneksi ke VPC perlu mengakses Amazon DynamoDB, pendekatan arsitektur mana yang paling optimal secara latensi dan biaya?**
   * A. Melewatkan seluruh traffic melalui NAT Gateway berbayar.
   * B. Membuat Gateway VPC Endpoint untuk Amazon DynamoDB di dalam VPC tanpa biaya data transfer.
   * C. Mengonfigurasi Security Group Lambda untuk mengizinkan outbound 0.0.0.0/0.
   * D. Mengakses DynamoDB melalui public internet proxy EC2.
   * *Jawaban*: B. Gateway VPC Endpoint menyediakan rute privat langsung ke DynamoDB tanpa biaya data transfer dan tanpa latency hop NAT Gateway.

10. **Apa perbedaan mendasar antara implementasi Saga Pattern menggunakan Orchestration dibanding Choreography?**
    * A. Orchestration tidak membutuhkan basis data sama sekali.
    * B. Choreography mengandalkan kontrol koordinator pusat, sedangkan Orchestration menggunakan event terdistribusi.
    * C. Orchestration mengandalkan state machine terpusat untuk memicu langkah dan kompensasi, sedangkan Choreography mengandalkan setiap service menerbitkan dan bereaksi terhadap event secara otonom.
    * D. Choreography secara otomatis menjamin ketiadaan duplikasi data.
    * *Jawaban*: C. Orchestration = komando terpusat (*conductor*). Choreography = koordinasi reaktif otonom (*dancers*).

---

### Bagian 3: Skenario Kasus Produksi (3 Soal)

11. **Skenario 1**: Sebuah tim platform mendapati fungsi Lambda mereka yang memproses stream dari Amazon Kinesis mengalami pembengkakan lag (*IteratorAge* naik drastis) saat event promosi. Fungsi tersebut memakan waktu 400 ms per pemrosesan record, dan setiap shard Kinesis menghasilkan 2.000 record per detik. Apa langkah paling presisi untuk menyelesaikan masalah ini tanpa memodifikasi logika bisnis internal Lambda?
    * A. Tingkatkan memori Lambda ke 10.240 MB.
    * B. Ubah konfigurasi Event Source Mapping dengan menaikkan `Parallelization Factor` (hingga 10) per shard dan aktifkan `Concurrent batches per shard`.
    * C. Turunkan batch size menjadi 1.
    * D. Migrasikan Kinesis ke SQS Standard.
    * *Jawaban*: B. Secara default, 1 shard Kinesis diproses oleh 1 instansiasi Lambda. Dengan menaikkan `Parallelization Factor`, Lambda dapat memproses beberapa batch konkuren secara simultan dari 1 shard yang sama berdasarkan partisi key yang berbeda.

12. **Skenario 2**: Sistem pembayaran Anda memanggil API bank pihak ketiga via Lambda. Bank tersebut sering mengalami *network fluctuation* yang menyebabkan timeout pemanggilan HTTP selama 30 detik sebelum gagal. Karena volume transaksi tinggi, konkurensi Lambda Anda cepat habis (*concurrency exhaustion*), menyebabkan layanan lain di akun AWS yang sama lumpuh (*throttled*). Langkah arsitektur apa yang wajib diimplementasikan segera?
    * A. Menerapkan pola *Circuit Breaker* dengan timeout panggilan HTTP yang agresif (misal: 3 detik) serta mengisolasi fungsi pembayaran tersebut menggunakan dedicated `Reserved Concurrency`.
    * B. Naikkan timeout Lambda menjadi 15 menit agar pemanggilan bank dapat ditunggu sampai berhasil.
    * C. Pindahkan Lambda ke luar VPC tanpa security controls.
    * D. Tambahkan memori Lambda agar thread HTTP pool bertambah besar.
    * *Jawaban*: A. Mengatur timeout HTTP yang agresif dan mengisolasi fungsi dengan `Reserved Concurrency` membatasi dampak ledakan failure (*blast radius*) agar tidak menghabiskan kuota pool akun concurrent executions.

13. **Skenario 3**: Sistem otorisasi finansial menggunakan AWS Step Functions Express. Saat terjadi kegagalan jaringan sementara pada downstream service, Anda mendapati ada data transaksi yang dieksekusi 2 kali oleh state machine. Manakah analisis akar masalah yang tepat?
    * A. Step Functions Express secara bawaan tidak mendukung retry logic.
    * B. Terjadi retry eksekusi asinkron pada Step Functions Express yang memiliki semantik *at-least-once delivery*; sistem tidak menyertakan pengecekan idempotensi unik pada state task tersebut.
    * C. DynamoDB mengalami split brain.
    * D. CloudWatch terlambat membaca event logs.
    * *Jawaban*: B. Asynchronous Express Workflows beroperasi dengan jaminan *at-least-once execution*, sehingga eksekusi ganda dapat terjadi jika ada retry. Setiap task non-idempotent wajib dilindungi dengan token idempotensi.

---

## 16. Summary

1. **Firecracker & Runtime Lifecycle**: AWS Lambda mengisolasi eksekusi menggunakan microVM Firecracker. Pemanfaatan *global execution context reuse*, optimasi fase INIT, dan penggunaan resource CPU yang proporsional terhadap alokasi memori adalah kunci utama arsitektur serverless berperforma tinggi.
2. **Event Routing & Decoupling**: Amazon EventBridge menyediakan abstraksi *content-based routing* terpusat yang memisahkan boundary domain secara bersih. Ketika dikombinasikan dengan SQS FIFO, arsitektur mendapatkan kapasitas penahanan beban (*buffering*) dan perlindungan terhadap kegagalan komponen downstream (*backpressure management*).
3. **Resilience Engineering**: Sistem terdistribusi pasti mengalami kegagalan. Penggunaan *Dead-Letter Queues (DLQ)*, *partial batch failure reporting*, validasi idempotensi atomik via DynamoDB, dan orkestrasi transaksi kompensasi via AWS Step Functions (Saga Pattern) adalah fondasi wajib untuk arsitektur serverless tingkat enterprise yang tangguh.