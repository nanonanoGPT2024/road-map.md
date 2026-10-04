## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 06-Architecture-and-System-Design
*   **Mata Kuliah / Domain:** API Design & Engineering
*   **Bab 03:** Contract-First Design & Formal Specifications
*   **Modul 01:** OpenAPI 3.1, JSON Schema 2020-12, Protobuf v3, Schema Evolution Rules, AsyncAPI untuk Event-Driven & Streaming
*   **Tingkat Kesulitan:** Advanced / Senior Engineer
*   **Prasyarat:** Pemahaman mendalam tentang HTTP/1.1, HTTP/2, TCP/IP, REST architecture, format data JSON/Binary, serta konsep dasar distributed systems dan microservices messaging.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Mengartikulasikan dan Menerapkan Paradigma Contract-First:** Mengisolasi siklus hidup desain API dari detail implementasi kode backend menggunakan formal specification sebagai *Single Source of Truth* (SSOT).
2.  **Menguasai OpenAPI Specification (OAS) 3.1 & JSON Schema 2020-12:** Menyusun spesifikasi RESTful API modern yang memanfaatkan keselarasan penuh (100% dialect alignment) antara OAS 3.1 dan JSON Schema Draft 2020-12, termasuk evaluasi `unevaluatedProperties`, *dynamic anchors*, dan definisi *type arrays*.
3.  **Merancang Binary Contract Menggunakan Protocol Buffers v3 (proto3):** Mengimplementasikan skema gRPC/Protobuf yang efisien, memahami alokasi *field numbers*, aturan *wire format* (varints, length-delimited), dan semantik *field presence*.
4.  **Menerapkan Schema Evolution & Compatibility Rules Secara Matematis:** Menjamin *Backward*, *Forward*, dan *Full Compatibility* pada ekosistem terdistribusi menggunakan *Schema Registry* serta menghindari skenario *breaking changes*.
5.  **Mendesain Arsitektur Event-Driven Menggunakan AsyncAPI:** Menyusun spesifikasi formal untuk sistem *message-driven* berbasis Apache Kafka, RabbitMQ, atau WebSocket dengan definisi channels, operations, messages, dan protocol bindings yang presisi.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                         [CONTRACT-FIRST PARADIGM]
                                    |
          +-------------------------+-------------------------+
          |                                                   |
   [SYNCHRONOUS RPC/REST]                             [ASYNCHRONOUS EVENTS]
          |                                                   |
   +------+------+                                            |
   |             |                                            |
[OpenAPI 3.1] [Protobuf v3]                              [AsyncAPI 3.0]
   |             |                                            |
   +------+------+                                            |
          |                                                   |
[JSON Schema 2020-12]                                  [Channel/Operation]
(Validation Engine)                                   (Kafka/RabbitMQ/WS)
          |                                                   |
          +-------------------------+-------------------------+
                                    |
                      [SCHEMA EVOLUTION & GOVERNANCE]
                                    |
           +------------------------+------------------------+
           |                        |                        |
     [Compatibility]      [Automated Linters]       [Schema Registry]
     - Backward           - Spectral (REST)         - Confluent / Apicurio
     - Forward            - Buf CLI (Protobuf)      - CI/CD Breaking Blockers
     - Full
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Dalam arsitektur *distributed systems* skala besar, integrasi antar-servis yang rapuh menjadi sumber latensi operasional dan *downtime* terparah. Pendekatan konvensional *Code-First*—di mana dokumentasi atau representasi skema diekstrak secara otomatis dari anotasi kode controller—menghasilkan beberapa kelemahan arsitektural:

1.  **Implementation Leakage:** Detail internal database model atau bahasa pemrograman sering kali bocor ke antarmuka publik tanpa filter yang ketat.
2.  **Accidental Breaking Changes:** Modifikasi tipe data lokal yang tampaknya sepele oleh seorang developer dapat merusak puluhan downstream consumers yang bergantung pada payload tersebut.
3.  **Tinggi Biaya Koordinasi:** Tim frontend, mobile, dan data engineers harus menunggu implementasi backend selesai sebelum dapat memulai integrasi, meniadakan efisiensi *parallel development*.

*Contract-First Design* menempatkan artefak skema (OpenAPI, Protobuf, AsyncAPI) sebagai kontrak hukum (*binding technical contract*) yang disepakati oleh produsen dan konsumen **sebelum baris kode pertama ditulis**. Kontrak ini berfungsi sebagai fondasi pembuatan:
*   *Mock servers* otomatis untuk memblokir ketergantungan antar-tim.
*   *Stub generator* client dan server-side skeleton.
*   *Automated contract testing* (consumer-driven contracts).
*   *Runtime validation guards* pada API Gateway atau Ingress.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. OpenAPI 3.1 & JSON Schema 2020-12
OpenAPI Specification 3.1 merupakan lompatan evolusioner dari OAS 3.0. Fitur terpentingnya adalah integrasi penuh dengan **JSON Schema Core Specification Draft 2020-12**. Pada OAS 3.0, skema hanya merupakan *extended subset* dari JSON Schema Draft 00, memicu inkonsistensi sintaksis seperti penggunaan `nullable: true` alih-alih `type: ["string", "null"]`. OAS 3.1 menghilangkan dikotomi ini dan memperkenalkan dukungan native untuk webhooks (`webhooks:` object), mutual TLS, dan identifikasi lisensi SPDX.

### 2. Protocol Buffers v3 (proto3)
Format serialisasi biner independen dari platform dan bahasa yang dikembangkan oleh Google. Berbeda dengan payload teks berbasis JSON, Protobuf mengompilasi skema `.proto` ke dalam representasi biner yang sangat padat (*dense wire format*), memanfaatkan mekanisme encoding seperti *Varints* dan *ZigZag encoding* untuk meminimalkan alokasi CPU dan overhead jaringan pada komunikasi gRPC berkecepatan tinggi.

### 3. Schema Evolution Rules
Seperangkat aturan deterministik yang mengatur bagaimana sebuah skema dapat dimodifikasi tanpa merusak integritas sistem yang sedang berjalan.
*   **Backward Compatibility:** Konsumen dengan skema baru dapat membaca data yang diproduksi oleh produsen berskema lama.
*   **Forward Compatibility:** Konsumen dengan skema lama dapat membaca data yang diproduksi oleh produsen berskema baru (mengabaikan field yang belum dikenal).
*   **Full Compatibility:** Memenuhi syarat Backward dan Forward secara bersamaan.

### 4. AsyncAPI
Standar terbuka yang mengadaptasi filosofi OpenAPI ke dalam paradigma *Event-Driven Architectures* (EDA). AsyncAPI mendokumentasikan broker, antrean/topik (*channels*), arah aliran pesan (*send/receive operations*), protokol runtime (*Kafka, AMQP, MQTT, WebSocket bindings*), serta validasi muatan (*payload schemas*).

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### Mekanisme Wire Format Protobuf v3
Di balik kecepatan eksekusinya, Protobuf tidak mengirimkan nama field teks (misalnya `"transaction_id"`), melainkan pasangan biner yang terdiri dari nomor tag field (*field number*) dan tipe *wire* (*wire type*).

Tag dihitung menggunakan rumus bitwise:
$$\text{Key} = (\text{field\_number} \ll 3) \mid \text{wire\_type}$$

| Wire Type | ID | Arti | Format Data |
| :--- | :--- | :--- | :--- |
| `VARINT` | 0 | `int32, int64, uint32, bool, enum` | Variable length 1–10 bytes |
| `I64` | 1 | `fixed64, sfixed64, double` | Tepat 8 bytes |
| `LEN` | 2 | `string, bytes, embedded messages, packed repeated` | Panjang dinamis + byte array |
| `SGROUP` | 3 | Start group (deprecated) | Diabaikan di proto3 |
| `EGROUP` | 4 | End group (deprecated) | Diabaikan di proto3 |
| `I32` | 5 | `fixed32, sfixed32, float` | Tepat 4 bytes |

Ketika parser proto3 menerima sebuah field tag yang tidak terdaftar di dalam skema lokalnya, parser **tidak melempar exception**. Parser membaca header *wire type*, melompati byte data tersebut menggunakan *length marker*, lalu menyimpannya dalam buffer *unknown fields* untuk mempertahankan data tersebut saat dilakukan serialisasi ulang (*round-trip serialization*).

### JSON Schema 2020-12 Dynamic Evaluation Engine
JSON Schema 2020-12 menggunakan sistem evaluasi berbasis *applicators* dan *assertions*. Fitur kunci seperti `unevaluatedProperties` bekerja bersama keyword navigasi skema:
1. Validator memeriksa seluruh *in-place applicators* (`allOf`, `anyOf`, `oneOf`, `$ref`).
2. Schema melacak field mana saja yang telah dievaluasi oleh keyword `properties` atau `patternProperties`.
3. `unevaluatedProperties: false` menjatuhkan validasi jika terdapat properti tambahan dalam payload yang belum "disentuh" oleh cabang validasi mana pun, termasuk validasi yang didelegasikan melalui `$ref`.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Siklus Validasi & Parsing Kontrak (Sync & Async)

```
========================================================================================
                                CONTRACT ARTIFACT PIPELINE
========================================================================================

  [ OpenAPI 3.1 YAML ]        [ Protobuf v3 Schema ]        [ AsyncAPI 3.0 YAML ]
           │                           │                             │
           ▼                           ▼                             ▼
  ┌─────────────────┐         ┌─────────────────┐           ┌─────────────────┐
  │ Spectral Linter │         │  Buf CLI Lint   │           │ AsyncAPI CLI    │
  │ (Style & Rules) │         │  & Breaking     │           │ (Spec Validator)│
  └────────┬────────┘         └────────┬────────┘           └────────┬────────┘
           │ Passes                    │ Passes                      │ Passes
           ▼                           ▼                             ▼
  ┌─────────────────┐         ┌─────────────────┐           ┌─────────────────┐
  │ Schema Registry │◄────────┴─────────────────┴──────────►│ Confluent Schema│
  │ (REST Endpoints)│       Enforce Backward Compatibility  │ Registry (Kafka)│
  └────────┬────────┘                                       └────────┬────────┘
           │                                                         │
           ├───────────────────────────────┬─────────────────────────┤
           ▼                               ▼                         ▼
  ┌─────────────────┐             ┌─────────────────┐       ┌─────────────────┐
  │ SDK Generator   │             │ Gateway Route & │       │ Message Broker  │
  │ (OpenAPI Gen /  │             │ Request Guard   │       │ Event Deserial- │
  │  Protoc / Buf)  │             │ (Envoy / Kong)  │       │ izer (Workers)  │
  └─────────────────┘             └─────────────────┘       └─────────────────┘

========================================================================================
                      PROTOBUF v3 WIRE FORMAT DESERIALIZATION
========================================================================================

 Incoming Raw Byte Stream: [ 0x08, 0x96, 0x01, 0x12, 0x04, 0x74, 0x65, 0x73, 0x74 ]
                             │
                             ├─ 0x08 -> (Binary: 0000 1000)
                             │   ├── Field Number: 00001 (1)  (Shift right 3: 0000 1000 >> 3)
                             │   └── Wire Type:    000   (0)  -> VARINT
                             │
                             ├─ 0x96, 0x01 -> Varint Payload: 150
                             │   ├── 0x96 = 1001 0110 (MSB 1: read next byte) -> 001 0110
                             │   └── 0x01 = 0000 0001 (MSB 0: terminal byte)  -> 000 0001
                             │   └── Result: (000 0001 << 7) | (001 0110) = 1001 0110 = 150
                             │
                             ├─ 0x12 -> (Binary: 0001 0010)
                             │   ├── Field Number: 00010 (2)  (Shift right 3: 0001 0010 >> 3)
                             │   └── Wire Type:    010   (2)  -> LENGTH-DELIMITED
                             │
                             ├─ 0x04 -> Length: 4 Bytes to follow
                             │
                             └─ 0x74, 0x65, 0x73, 0x74 -> Raw UTF-8 String: "test"

========================================================================================
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah translasi domain sederhana: **Order Notification Event** yang didefinisikan ke dalam dua standar berbeda.

### Versi Protobuf v3 (`order_event.proto`)
```protobuf
syntax = "proto3";

package commerce.orders.v1;

option go_package = "github.com/enterprise/gen/v1/orders;ordersv1";
option java_multiple_files = true;
option java_package = "com.commerce.orders.v1";

enum OrderStatus {
  // Aturan proto3: Nilai pertama enum HARUS bernilai 0
  ORDER_STATUS_UNSPECIFIED = 0;
  ORDER_STATUS_PENDING = 1;
  ORDER_STATUS_PAID = 2;
  ORDER_STATUS_CANCELLED = 3;
}

message OrderEvent {
  // Tag 1-15 hanya membutuhkan 1 byte overhead pada wire format
  string order_id = 1;
  int64 customer_id = 2;
  OrderStatus status = 3;
  double total_amount = 4;
  int64 timestamp_epoch_ms = 5;
}
```

### Versi JSON Schema 2020-12 (`order_event.schema.json`)
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://api.enterprise.com/schemas/commerce/orders/v1/order_event.json",
  "title": "OrderEvent",
  "type": "object",
  "properties": {
    "order_id": {
      "type": "string",
      "format": "uuid"
    },
    "customer_id": {
      "type": "integer",
      "minimum": 1
    },
    "status": {
      "type": "string",
      "enum": ["PENDING", "PAID", "CANCELLED"]
    },
    "total_amount": {
      "type": "number",
      "exclusiveMinimum": 0.0
    },
    "timestamp_epoch_ms": {
      "type": "integer"
    }
  },
  "required": ["order_id", "customer_id", "status", "total_amount", "timestamp_epoch_ms"],
  "unevaluatedProperties": false
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Mari kita bedah skenario produksi: Sistem Payment Processing Enterprise yang mengekspos endpoint sinkron RESTful (OpenAPI 3.1), RPC internal performa tinggi (Protobuf v3), dan integrasi event-driven ke Apache Kafka (AsyncAPI 3.0).

### 1. OpenAPI 3.1: Kontrak Payment Ingestion (`payment-service.openapi.yaml`)
Perhatikan penggunaan syntax JSON Schema Draft 2020-12 native: array types untuk nullability dan keyword `unevaluatedProperties`.

```yaml
openapi: 3.1.0
info:
  title: Payment Gateway Service
  version: 1.4.0
  description: Mission-critical payment processing contract enforcing JSON Schema 2020-12 semantics.
servers:
  - url: https://api.enterprise.com/v1
    description: Production Cluster
paths:
  /payments:
    post:
      summary: Submit a payment transaction
      operationId: submitPayment
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/PaymentRequest'
      responses:
        '201':
          description: Payment Authorized Successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/PaymentResponse'
        '422':
          description: Schema Validation Failure
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ValidationErrorPayload'
components:
  schemas:
    PaymentRequest:
      type: object
      required:
        - idempotency_key
        - amount
        - currency
        - payment_method
      properties:
        idempotency_key:
          type: string
          format: uuid
        amount:
          type: integer
          description: Nilai terkecil mata uang (misal: Cent, Satuan Rupiah penuh)
          minimum: 100
        currency:
          type: string
          pattern: '^[A-Z]{3}$'
        payment_method:
          $ref: '#/components/schemas/PaymentMethod'
        metadata:
          type: ["object", "null"]
          additionalProperties:
            type: string
      unevaluatedProperties: false

    PaymentMethod:
      type: object
      oneOf:
        - required: [card]
        - required: [virtual_account]
      properties:
        card:
          type: object
          required: [token, cvc]
          properties:
            token: { type: string }
            cvc: { type: string, pattern: '^[0-9]{3,4}$' }
          unevaluatedProperties: false
        virtual_account:
          type: object
          required: [bank_code]
          properties:
            bank_code: { type: string, enum: [BCA, MANDIRI, BNI] }
          unevaluatedProperties: false

    PaymentResponse:
      type: object
      required:
        - transaction_id
        - status
        - authorized_at
      properties:
        transaction_id:
          type: string
          format: uuid
        status:
          type: string
          enum: [AUTHORIZED, CAPTURED, FAILED]
        authorized_at:
          type: string
          format: date-time
      unevaluatedProperties: false

    ValidationErrorPayload:
      type: object
      required:
        - error_code
        - message
        - field_violations
      properties:
        error_code: { type: string }
        message: { type: string }
        field_violations:
          type: array
          items:
            type: object
            required: [field, description]
            properties:
              field: { type: string }
              description: { type: string }
```

### 2. Protobuf v3: Kontrak Internal Settlement Worker (`settlement_service.proto`)
Memperlihatkan penataan tag, evolusi aman dengan tag *reserved*, dan semantik tipe modern.

```protobuf
syntax = "proto3";

package enterprise.payments.settlement.v1;

import "google/protobuf/timestamp.proto";

option go_package = "github.com/enterprise/payments/gen/v1;settlementv1";

// Layanan internal gRPC untuk penyelesaian transaksi antar-bank
service SettlementService {
  rpc ProcessSettlement (SettlementRequest) returns (SettlementResponse);
}

message SettlementRequest {
  // Mencegah penggunaan kembali ID dan nama yang sudah dihapus demi forward/backward safety
  reserved 3, 7 to 10;
  reserved "legacy_auth_code", "terminal_identifier";

  string transaction_id = 1;
  int64 settlement_amount_cents = 2;
  string target_account_number = 4;
  
  // Field presence eksplisit menggunakan proto3 optional keyword
  optional string routing_transit_number = 5;
  google.protobuf.Timestamp execution_deadline = 6;
}

message SettlementResponse {
  enum ExecutionResult {
    EXECUTION_RESULT_UNSPECIFIED = 0;
    EXECUTION_RESULT_SUCCESS = 1;
    EXECUTION_RESULT_QUEUED = 2;
    EXECUTION_RESULT_FAILED_INSUFFICIENT_FUNDS = 3;
    EXECUTION_RESULT_FAILED_NETWORK = 4;
  }

  string settlement_batch_id = 1;
  ExecutionResult result = 2;
  google.protobuf.Timestamp processed_at = 3;
}
```

### 3. AsyncAPI 3.0: Topik Streaming Transaksi Kafka (`payment-events.asyncapi.yaml`)
Menetapkan kontrak pesan asinkron untuk down-stream streaming analytics and audit trail.

```yaml
asyncapi: 3.0.0
info:
  title: Payment Streaming Infrastructure API
  version: 2.0.0
  description: Event streams published to Apache Kafka detailing payment states.
defaultContentType: application/json

servers:
  production-kafka:
    host: kafka-broker.internal.enterprise.com:9092
    protocol: kafka
    description: Core Production Kafka Cluster

channels:
  paymentEventsChannel:
    address: enterprise.payments.events.v1
    messages:
      PaymentCapturedEvent:
        $ref: '#/components/messages/PaymentCaptured'
    bindings:
      kafka:
        topic: enterprise.payments.events.v1
        partitions: 12
        replicas: 3

operations:
  onPaymentCapturedPublish:
    action: send
    channel:
      $ref: '#/channels/paymentEventsChannel'
    summary: Emitted directly when a payment captures money successfully.
    messages:
      - $ref: '#/channels/paymentEventsChannel/messages/PaymentCapturedEvent'

components:
  messages:
    PaymentCaptured:
      name: PaymentCaptured
      title: Payment Captured Notification
      payload:
        schema:
          type: object
          $schema: "https://json-schema.org/draft/2020-12/schema"
          required:
            - transaction_id
            - captured_amount
            - currency
            - timestamp
          properties:
            transaction_id:
              type: string
              format: uuid
            captured_amount:
              type: integer
              minimum: 1
            currency:
              type: string
              pattern: '^[A-Z]{3}$'
            timestamp:
              type: string
              format: date-time
          unevaluatedProperties: false
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Arsitektural | OpenAPI 3.1 (REST/HTTP) | Protobuf v3 (gRPC/IPC) | AsyncAPI 3.0 (Streaming/EDA) |
| :--- | :--- | :--- | :--- |
| **Payload Overhead** | Tinggi (Teks JSON verbose, header HTTP string). | Terendah (Biner terkodekan, field name dikompresi ke varint tags). | Bergantung payload (biasanya JSON atau Protobuf terenkapsulasi). |
| **Parsing Latency** | Menengah–Tinggi (Alokasi memory string, scanning tipe data). | Ekstrim Rendah (Serialisasi/deserialisasi biner zero-copy parsing). | Sangat tergantung broker transport dan engine deserialisasi worker. |
| **Human Readability** | Sangat Tinggi (Bisa di-inspect langsung via `curl` atau Web Inspector). | Buruk (Membutuhkan decoding `.proto` atau reflection engine). | Rendah–Menengah (Memerlukan consumer tooling untuk inspect topic/queue). |
| **Tooling & Toolchain** | Sangat matang, integrasi UI gratis (Swagger UI, Redoc, Stoplight). | Terstandarisasi via `protoc`, ekosistem Buf yang modern namun kaku. | Berkembang pesat, belum sematang ekosistem OpenAPI. |
| **Network Intermediary** | Sangat ramah proxy (Edge proxies, API Gateway, CDN caching). | Sulit (Membutuhkan HTTP/2 gRPC support di L7 load balancer seperti Envoy). | Melalui broker message terpusat; tidak melalui HTTP routing layer reguler. |

---

## SEKSI 11 — BEST PRACTICES

1.  **Immutability of Field Tags (Protobuf):** Nomor tag Protobuf tidak boleh diubah atau ditukar posisinya seumur hidup aplikasi. Tag 1 hingga 15 harus dicadangkan secara ketat hanya untuk field payload transaksi yang paling sering dieksekusi guna menghemat bandwidth (hanya butuh 1 byte tag overhead).
2.  **Explicit Property Locking dengan JSON Schema 2020-12:** Hindari penggunaan `additionalProperties: false` jika API Anda menggunakan komposisi hierarkis via `allOf`. Gunakan selalu `unevaluatedProperties: false` agar evaluasi skema modular berjalan valid dan tidak false-negative.
3.  **Gunakan Reserved Names & Tags pada Penghentian Field:** Ketika menghapus atribut dari Protobuf, jangan sekadar menghapus kodenya. Nyatakan field tersebut ke dalam blok `reserved` untuk mencegah developer masa depan memakai ulang nomor atau nama field tersebut secara tidak sengaja.
    ```protobuf
    // BENAR
    reserved 4, 11 to 15;
    reserved "customer_tax_id", "billing_address";
    ```
4.  **Otomasi CI Linter & Breaking Change Detectors:** Integrasikan linter formal ke dalam siklus pipeline Git.
    *   Gunakan **Spectral** untuk OpenAPI 3.1 validation berbasis ruleset korporat.
    *   Gunakan **Buf CLI** (`buf breaking --against '.git#branch=main'`) untuk mendeteksi pelanggaran backward compatibility di level Protobuf secara deterministik.
5.  **Single Source of Truth Repository:** Seluruh file `.proto`, `.yaml` (OpenAPI/AsyncAPI) harus disimpan dalam repositori tersentralisasi (*Schema Monorepo*) atau di-*publish* ke private *Artifact Registry* (misal: Confluent Schema Registry, Buf Schema Registry), di mana artifact SDK di-*generate* secara independen ke berbagai bahasa (Go, Java, TypeScript, Rust).

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Mengubah Tipe Data Field Tanpa Memutus Versi (Breaking Evolution)
*Contoh Kesalahan:* Mengubah field OpenAPI dari `type: integer` menjadi `type: string` secara langsung, atau mengubah tipe Protobuf dari `int32` ke `string`.
*   *Dampak Fatal:* Client lama akan mengalami *fatal unmarshaling exception* ketika menerima payload baru, memicu *cascading failures* di sistem hulu (*upstream*).

### 2. Default Zero-Value Misinterpretation pada Protobuf v3
*Contoh Kesalahan:* Mengasumsikan bahwa integer bernilai `0`, boolean bernilai `false`, atau string kosong `""` dikirimkan secara fisik melalui jaringan di proto3 secara default.
*   *Dampak Fatal:* Pada wire format proto3 baku, nilai default **tidak diserialisasi sama sekali** untuk efisiensi ruang. Sistem penerima tidak dapat membedakan antara field bernilai nol secara sengaja (*explicit zero*) vs field yang lupa diisi oleh produsen (*unset*). 
*   *Solusi:* Gunakan keyword `optional` di proto3 modern untuk mempertahankan *field presence tracking*, atau bungkus dalam `google.protobuf.Int32Value` wrapper message.

### 3. Migrasi Sintaksis Cacat: Menggunakan `nullable: true` di OpenAPI 3.1
*Contoh Kesalahan:*
```yaml
# SALAH PADA OPENAPI 3.1
properties:
  middle_name:
    type: string
    nullable: true
```
*   *Dampak:* OpenAPI 3.1 telah mengadopsi 100% dialek JSON Schema Draft 2020-12 di mana keyword `nullable` telah resmi dihapus (*deprecated/invalid*).
*   *Solusi yang Benar:*
```yaml
# BENAR PADA OPENAPI 3.1
properties:
  middle_name:
    type: ["string", "null"]
```

### 4. Menghapus atau Mengubah Index Nomor Enum pada Protobuf
*Contoh Kesalahan:*
```protobuf
// SEBELUMNYA
enum Status { STATUS_UNSPECIFIED = 0; ACTIVE = 1; INACTIVE = 2; }
// DIUBAH MENJADI
enum Status { STATUS_UNSPECIFIED = 0; SUSPENDED = 1; ACTIVE = 2; } // BAHAYA!
```
*   *Dampak Fatal:* Wire format mengirim representasi enum sebagai varint integer. Pesan lama yang mengirim angka `1` yang awalnya diartikan sebagai `ACTIVE`, kini akan dibaca secara salah sebagai `SUSPENDED` oleh consumer baru.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Latihan:
Anda memimpin arsitektur sistem untuk layanan ekspedisi logistik. Anda diminta merancang evolusi skema untuk pelacakan armada truk (*Fleet Tracking System*).

### Tugas 1: Mendesain Kontrak Protobuf v3 Berketahanan Tinggi
Buat file `fleet_tracking.proto` dengan kriteria:
1. Package `logistics.fleet.v1`.
2. Sebuah enum `VehicleStatus` yang mematuhi proto3 zero-value convention.
3. Message `TelemetryPing` yang merekam:
    * `vehicle_id` (string, tag 1)
    * `latitude` & `longitude` (double, tags 2 & 3)
    * `current_speed_kph` (float, tag 4)
    * `engine_temperature` (optional float, tag 5)
    * `recorded_at` (menggunakan standard protobuf Timestamp, tag 6)
4. Pastikan nomor tag 7 sampai 12 telah di-*reserved* untuk migrasi sensor masa depan.

### Tugas 2: Menuliskan OpenAPI 3.1 dengan Evaluasi Dinamis JSON Schema 2020-12
Tuliskan blok skema OpenAPI 3.1 untuk endpoint `POST /fleet/telemetry` yang menerima payload array dari `TelemetryPing` di atas, dengan validasi:
* `latitude` harus berada pada rentang `-90.0` sampai `90.0`.
* `longitude` harus berada pada rentang `-180.0` sampai `180.0`.
* Menolak segala bentuk property siluman di luar skema (`unevaluatedProperties: false`).

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1.  **Mengapa tag 1 hingga 15 dalam Protobuf v3 sangat bernilai dan harus dialokasikan secara hati-hati?**
    *   *Jawaban Ideal:* Tag 1–15 diserialisasikan ke dalam satu byte tunggal (4 bit nomor field, 3 bit tipe wire, 1 bit MSB). Tag 16 ke atas memerlukan 2 byte atau lebih pada wire format, sehingga alokasi tag 1–15 harus dihemat khusus untuk field dengan frekuensi kemunculan tertinggi.

2.  **Apa perbedaan mendasar antara `additionalProperties: false` dan `unevaluatedProperties: false` pada JSON Schema 2020-12?**
    *   *Jawaban Ideal:* `additionalProperties` hanya memvalidasi properti yang berada dalam konteks lokal skema bersangkutan dan tidak dapat "melihat" properti yang didefinisikan di dalam keyword aplikator seperti `allOf` atau dynamic `$ref`. Sebaliknya, `unevaluatedProperties` mampu mengevaluasi properti di seluruh percabangan skema yang dikomposisikan, memungkinkan enkapsulasi modular tanpa menolak properti valid yang didefinisikan di sub-skema turunan.

3.  **Jika sebuah producer menambahkan field baru ke dalam skema Protobuf, apa yang terjadi pada consumer lama yang belum meng-update berkas `.proto` miliknya?**
    *   *Jawaban Ideal:* Consumer lama akan tetap membaca payload tersebut tanpa error (*Forward Compatibility*). Parser akan mengenali tag baru melalui wire format length/varint, mengabaikan field tersebut pada payload utama, dan menyimpannya di dalam buffer *unknown fields* untuk mencegah hilangnya data jika consumer tersebut mem-forward payload ke service lain.

4.  **Manakah konfigurasi Backward Compatible yang sah pada AsyncAPI payload schema saat menghapus sebuah field?**
    *   A. Menghapus field yang berstatus `required` tanpa persetujuan consumer.
    *   B. Mengubah tipe payload dari string tanggal ISO-8601 ke Epoch timestamp integer.
    *   C. Menghapus sebuah field opsional dan memastikan semua consumer telah memperbarui implementasinya untuk menangani nilai default/null.
    *   *Jawaban Ideal:* **C**. Penghapusan field opsional mempertahankan validitas pembacaan skema lama, asalkan skema tidak mengeksekusi validasi restriktif yang memaksa keberadaan field tersebut.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

*   **Spesifikasi Formal:**
    *   *OpenAPI Specification v3.1.0:* [https://spec.openapis.org/oas/v3.1.0](https://spec.openapis.org/oas/v3.1.0)
    *   *JSON Schema 2020-12 Core & Validation Specification:* [https://json-schema.org/draft/2020-12/json-schema-core.html](https://json-schema.org/draft/2020-12/json-schema-core.html)
    *   *Protocol Buffers Language Guide (proto3):* [https://protobuf.dev/programming-guides/proto3/](https://protobuf.dev/programming-guides/proto3/)
    *   *AsyncAPI Specification v3.0.0:* [https://www.asyncapi.com/docs/specifications/v3.0.0](https://www.asyncapi.com/docs/specifications/v3.0.0)
*   **Tooling Arsitektural:**
    *   *Buf Build CLI:* Protobuf linter dan compatibility breaker blocker terdepan ([https://buf.build](https://buf.build)).
    *   *Spectral by Stoplight:* Flexible JSON/YAML linter untuk API description languages ([https://stoplight.io/open-source/spectral](https://stoplight.io/open-source/spectral)).
    *   *Confluent Schema Registry:* Production-grade centralized schema management engine ([https://docs.confluent.io/platform/current/schema-registry/index.html](https://docs.confluent.io/platform/current/schema-registry/index.html)).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

*   **Contract-First Paradigm** menggeser fase integrasi teknis ke hulu siklus rekayasa, menstandarisasi artefak antarmuka sebelum implementasi kode dimulai, secara drastis memangkas friksi koordinasi sistem terdistribusi.
*   **OpenAPI 3.1** menuntaskan fragmentasi ekosistem REST dengan mengintegrasikan mesin validasi **JSON Schema Draft 2020-12** secara komprehensif, mengadopsi native polymorphism, dan menghilangkan modifikasi ad-hoc seperti `nullable`.
*   **Protobuf v3** memaksimalkan throughput transmisi melalui binary wire format berbasis kombinasi bitwise *(field_number << 3 | wire_type)*, mengharuskan pemahaman ketat terhadap alokasi nomor tag dan reservasi field.
*   **Schema Evolution** didasari oleh kontrak matematis: produsen dan konsumen harus berevolusi secara asinkron tanpa memutus komunikasi, ditunjang deteksi otomatis oleh tools seperti Buf atau Spectral.
*   **AsyncAPI** memperluas tata kelola kontrak formal ke ranah arsitektur Event-Driven, menyelaraskan channels, message streaming, dan queue routing di bawah disiplin spesifikasi yang setara dengan sistem REST.

---

## SEKSI 17 — GLOSARIUM

*   **SSOT (Single Source of Truth):** Satu-satunya dokumen acuan kanonikal dalam sebuah repositori yang mendikte seluruh detail kontrak antarmuka sistem.
*   **Wire Format:** Format fisik representasi data biner ketika pesan dikodekan dan dialirkan melalui kabel jaringan fisik atau buffer memory.
*   **Varint (Variable-Length Quantity):** Metode serialisasi integer yang menggunakan satu atau beberapa byte, di mana nilai yang lebih kecil menggunakan jumlah byte yang lebih sedikit.
*   **Idempotency Key:** Token identifikasi unik yang dikirimkan oleh consumer untuk memastikan operasi mutasi payload yang dikirim berkali-kali tidak akan diduplikasi di sistem penerima.
*   **Backward Compatibility:** Kemampuan sistem atau kode baru untuk memproses artefak input data yang dihasilkan oleh sistem versi lama tanpa kegagalan fungsional.
*   **Forward Compatibility:** Kemampuan sistem lama untuk secara anggun (*gracefully*) memproses atau mentoleransi artefak input yang dihasilkan oleh versi sistem yang lebih mutakhir.
*   **Dynamic Anchor (`$dynamicAnchor`):** Mekanisme JSON Schema Draft 2020-12 yang memungkinkan referensi rekursif dinamis melintasi batasan pohon skema modular.

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Fokus Pedagogis:** Tekankan kepada peserta didik bahwa *Contract-First* bukan sekadar masalah memilih tool file YAML atau Proto, melainkan perubahan paradigma organisasional (*cultural & governance shift*).
*   **Poin Rawan Miskonsepsi:** Mahasiswa sering kali mengira Proto3 `optional` sama dengan konsep `nullable` di database SQL. Jelaskan secara fisik bahwa Protobuf `optional` hanya menambahkan *presence bitfield mask* pada runtime struct untuk membedakan keberadaan payload default dari payload kosong.
*   **Setup Lingkungan Demo:** Pastikan CLI toolchain berikut telah terpasang di mesin workstation lab:
    ```bash
    # Install Spectral CLI
    npm install -g @stoplight/spectral-cli
    
    # Install Buf CLI (MacOS/Linux)
    brew install bufbuild/buf/buf
    ```
*   **Saran Diskusi Kelas:** Tanyakan skenario mitigasi nyata: *"Bagaimana strategi Anda jika tim data engineering secara sepihak menambahkan property baru di Kafka event yang menyebabkan crash di worker consumer lama?"* Arahkan diskusi ke penerapan *Schema Registry automated validation rules* pada fase Git push.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi 1.0.0 (Oktober 2023):**
    *   Inisialisasi draf awal kurikulum.
    *   Penyelarasan bab OpenAPI 3.0 dan proto2 legacy.
*   **Versi 2.0.0 (Maret 2024):**
    *   *Major Rewrite:* Migrasi total OpenAPI 3.0 ke OpenAPI 3.1.
    *   Penggantian JSON Schema Draft 00 dengan dialek kanonikal JSON Schema Draft 2020-12 (`unevaluatedProperties`, array-typed nullable).
    *   Penambahan pembahasan mendalam Wire Format biner Protobuf v3 dan integrasi AsyncAPI 3.0.
    *   Implementasi struktur komprehensif standar format materi pembelajaran enterprise.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya:** `06-Architecture-and-System-Design / Bab 02: API Protocols Deep Dive: REST, GraphQL, gRPC, and WebSockets`
*   **Modul Berikutnya:** `06-Architecture-and-System-Design / Bab 03 - Modul 02: Automated API Governance, Spectral Rule-Sets, and Buf Schema Registries in Enterprise CI/CD`
*   **Repositori Terkait:** `github.com/enterprise-curriculum/api-design-specifications`