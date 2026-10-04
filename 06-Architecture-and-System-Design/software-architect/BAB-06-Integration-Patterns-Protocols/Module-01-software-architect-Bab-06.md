# MODUL 06-01: INTEGRATION PATTERNS & COMMUNICATION PROTOCOLS

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `ARC-06-01`
* **Nama Modul**: Integration Patterns & Communication Protocols: Enterprise Integration Patterns (EIP), Synchronous vs Asynchronous Messaging, Message Brokers, RPC vs REST vs GraphQL
* **Kategori**: `06-Architecture-and-System-Design`
* **Tingkat Kesulitan**: *Advanced / Principal Architect Level*
* **Prasyarat**:
  * Pemahaman mendalam tentang *Distributed Systems Fundamentals* (CAP Theorem, Fallacies of Distributed Computing, Base Model).
  * Penguasaan *Networking Protocols* (TCP/IP stack, TLS, HTTP/1.1 vs HTTP/2 vs HTTP/3).
  * Pengalaman operasional dengan arsitektur *microservices*, containerization, dan database transaksional (ACID).
* **Estimasi Waktu Penyelesaian**: 12–16 Jam Pembelajaran Mandiri + 8 Jam Implementasi Laboratorium.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis & Mengklasifikasi** interaksi antarsistem menggunakan katalog *Enterprise Integration Patterns* (EIP) dari Hohpe & Woolf guna memecahkan masalah desentralisasi data dan koordinasi proses bisnis.
2. **Mengevaluasi Karakteristik Protokol** komunikasi sinkron (*Synchronous*) versus asinkron (*Asynchronous*) berdasarkan *latency budget*, *coupling degree*, *throughput*, dan *availability profile*.
3. **Merancang Topologi Pesan Skala Enterprise** dengan memilih secara presisi antara *Smart Endpoints/Dumb Pipes* (e.g., Apache Kafka, Apache Pulsar) versus *Smart Brokers/Dumb Endpoints* (e.g., RabbitMQ, ActiveMQ).
4. **Membedah dan Memilih Gaya Komunikasi API** (gRPC/Protocol Buffers, REST/OpenAPI, GraphQL) berdasarkan konteks *payload size*, *schema enforcement*, *serialization overhead*, serta *client consumption patterns*.
5. **Mengimplementasikan Pola Mitigasi Kegagalan Terdistribusi** seperti *Transactional Outbox Pattern*, *Idempotent Receiver*, *Dead-Letter Queues (DLQ)*, dan *Correlation Identifier* pada sistem produksi nyata.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                                [SYSTEM INTEGRATION DOMAIN]
                                             │
      ┌──────────────────────────────────────┴──────────────────────────────────────┐
      │                                                                             │
[TEMPORAL COUPLING]                                                         [PROTOCOL & DATA STYLE]
      │                                                                             │
      ├─► Synchronous (Blocking)                                                   ├─► RPC (gRPC / Protobuf)
      │     └─► Immediate Response, Cascading Failure Risk                          │     └─► Binary, HTTP/2, East-West Traffic
      │                                                                             │
      └─► Asynchronous (Non-Blocking)                                               ├─► REST (HTTP 1.1/2, JSON)
            ├─► Message-Driven / Event-Driven                                      │     └─► Resource-oriented, North-South Traffic
            └─► Temporal Decoupling, Buffering, Backpressure                        │
                                                                                    └─► GraphQL
                                                                                          └─► Single-endpoint, Client-driven Query
                                                                             
                                [MESSAGE BROKERS ARCHITECTURE]
                                             │
      ┌──────────────────────────────────────┴──────────────────────────────────────┐
      │                                                                             │
[AMQP / Traditional Queues]                                                 [Log-Centric Streaming]
(e.g., RabbitMQ)                                                            (e.g., Apache Kafka)
  ├─► Destructive Reads                                                       ├─► Non-Destructive Reads (Offset based)
  ├─► Complex Routing (Exchange -> Binding -> Queue)                          ├─► High Throughput / Partitioned Log
  └─► Per-Message State & Ack                                                 └─► Distributed Commit Log / Replayability

                                [ENTERPRISE INTEGRATION PATTERNS]
                                             │
      ┌──────────────────────┬───────────────┴───────────────┬──────────────────────┐
      │                      │                               │                      │
[Routing Patterns]     [Transformation]             [Composition]           [System Resilience]
  ├─ Content-Based       ├─ Message Translator        ├─ Aggregator           ├─ Dead-Letter Channel
  ├─ Message Filter      ├─ Envelope Wrapper          ├─ Splitter             ├─ Transactional Outbox
  └─ Dynamic Router      └─ Claim Check               └─ Scatter-Gather       └─ Idempotent Consumer
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Kegagalan mendasar arsitek perangkat lunak pemula saat bermigrasi dari monolit ke arsitektur terdistribusi (*microservices*) adalah memperlakukan jaringan komputer seperti pemanggilan fungsi dalam memori (*in-memory function call*). L. Peter Deutsch merangkum fenomena ini dalam *Fallacies of Distributed Computing*: jaringan tidak pernah dapat diandalkan, latensi tidak pernah nol, bandwidth tidak pernah tak terbatas, dan topologi selalu berubah.

Pilihan protokol komunikasi dan pola integrasi bukan sekadar preferensi sintaksis:
1. **Pencegahan *Cascading Failures***: Integrasi sinkron (seperti rantai panggilan REST/HTTP bertingkat) mengakibatkan korelasi kegagalan temporal. Jika Layanan A memanggil Layanan B, yang memanggil Layanan C, latensi akan terakumulasi secara aditif, dan kegagalan parsial pada Layanan C akan menguras *thread pool* Layanan A dan B hingga memicu *catastrophic outage*.
2. **Efisiensi Sumber Daya & Throughput**: Protokol berbasis teks seperti REST/JSON menelan *CPU cycles* yang signifikan untuk parsing dan serialisasi string, serta transmisi payload yang redundan. Dalam skala puluhan ribu transaksi per detik (*TPS*), beralih ke representasi biner terkompresi (gRPC/Protobuf) menurunkan utilisasi CPU dan alokasi memori secara radikal.
3. **Konsistensi Data Lintas Batas Konteks**: Dalam sistem terdistribusi, transaksi terdistribusi berbasis *Two-Phase Commit (2PC)* sangat rapuh dan memiliki skalabilitas yang buruk. Arsitek modern menggunakan pola integrasi asinkron (EIP) berbasis *Eventual Consistency* yang dijamin melalui pesan persisten yang dapat diputar ulang (*replayable streams*).

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Enterprise Integration Patterns (EIP)
Diresmikan oleh Gregor Hohpe dan Bobby Woolf, EIP adalah katalog pola standar industri untuk menjembatani sistem yang heterogen tanpa mengunci antarmuka mereka satu sama lain. Pola-pola ini memformalkan bagaimana sebuah pesan diproduksi, diubah, disaring, dialihkan, diagregasi, dan dikonsumsi di atas infrastruktur komunikasi.

### 2. Synchronous vs Asynchronous Messaging
* **Synchronous (Sinkron)**: Pola komunikasi *request-reply* yang mengharuskan pemanggil (*caller*) memblokir eksekusi atau mempertahankan konteks transaksi sampai menerima respons eksplisit dari penerima (*receiver*). Terdapat keterikatan waktu (*temporal coupling*).
* **Asynchronous (Asinkron)**: Pola *fire-and-forget* atau *event emission* di mana produsen memancarkan pesan ke media perantara (*message channel/broker*) tanpa menunggu penerima selesai memproses pesan tersebut. Tidak ada keterikatan waktu; produsen dan konsumen beroperasi secara independen.

### 3. Message Broker: Log-based vs Queue-based
* **Queue-Based Broker (e.g., RabbitMQ)**: Mengimplementasikan semantik antrean tradisional. Pesan didistribusikan ke konsumen dan dihapus (*destructive read*) segera setelah ada konfirmasi tanda terima (*ACK*). Broker mengelola status (*stateful*) pengiriman tiap-tiap pesan individual.
* **Log-Based Broker (e.g., Apache Kafka)**: Mengimplementasikan berkas log transaksi berurutan (*append-only log*). Pesan tidak dihapus saat dibaca; melainkan tiap konsumen bertanggung jawab menyimpan penunjuk posisinya sendiri (*offset*). Hal ini memungkinkan pembacaan ulang (*replayability*) dan throughput yang mendekati batas saturasi I/O disk.

### 4. Protokol: RPC vs REST vs GraphQL
* **RPC (gRPC)**: Menitikberatkan pada tindakan (*verbs*). Kontrak antarmuka didefinisikan secara tegas melalui IDL (*Interface Definition Language*) seperti Protocol Buffers, berjalan di atas transport HTTP/2 biner secara *multiplexed*. Optimal untuk komunikasi internal *service-to-service* (*East-West*).
* **REST (Representational State Transfer)**: Arsitektur berbasis sumber daya (*nouns*) yang mengeksploitasi semantik HTTP standar (GET, POST, PUT, DELETE) serta mekanisme *caching* bawaan HTTP. Cocok untuk *public-facing API* dan integrasi pihak ketiga (*North-South*).
* **GraphQL**: Bahasa kueri deklaratif untuk API yang mengekspos skema hierarkis tunggal. Klien mendikte struktur data yang diinginkan, meniadakan *over-fetching* dan *under-fetching*. Optimal untuk agregasi data bagi antarmuka pengguna yang kompleks (BFF pattern).

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### Mekanisme Protokol Transport & Eksekusi

#### A. Komunikasi Sinkron Biner: gRPC via HTTP/2
1. **Kompilasi Kontrak**: Protobuf compiler (`protoc`) mengompilasi berkas `.proto` menjadi kode klien (*stub*) dan server (*skeleton*).
2. **Serialisasi**: Data biner dikodekan dalam format *varint* dan *tag-length-value*, menghasilkan payload 50–80% lebih kecil dibanding JSON string.
3. **HTTP/2 Multiplexing**: Berbeda dari HTTP/1.1 yang mengalami masalah *Head-of-Line (HoL) Blocking* pada level koneksi TCP, HTTP/2 membagi komunikasi menjadi beberapa *stream* independen dalam satu koneksi TCP fisik yang persisten. Masing-masing request-response dipaketkan dalam unit kecil berupa *frames* (DATA, HEADERS).

#### B. Komunikasi Asinkron Antrean: AMQP Routing Model (RabbitMQ)
1. Produsen mengirim pesan ke **Exchange** bersama dengan **Routing Key**.
2. **Exchange** mengevaluasi atribut pesan berdasarkan tipenya:
   * *Direct*: Pesan diteruskan ke antrean yang memiliki *Binding Key* identik.
   * *Topic*: Pencocokan pola regex sederhana menggunakan wildcard (`*` untuk satu kata, `#` untuk nol atau lebih kata).
   * *Fanout*: *Broadcast* tanpa syarat ke seluruh antrean yang terikat.
3. Pesan disimpan dalam struktur **Queue** dalam memori/disk broker.
4. Konsumen menarik (*push model* via prefetch) pesan dan wajib mengirimkan `basic.ack` untuk menghapus pesan, atau `basic.nack` / `basic.reject` untuk mengirimnya ke *Dead-Letter Exchange (DLX)*.

#### C. Komunikasi Asinkron Log-Centric: Partitioned Log Model (Apache Kafka)
1. **Topic** dibagi secara horizontal ke dalam satu atau lebih **Partisi**.
2. Produsen memancarkan *record* berupa pasangan `(Key, Value)`. Algoritma partisi (biasanya murmur2 hash dari *Key* modulo *Jumlah Partisi*) menentukan partisi mana yang menerima *record*. Record yang masuk mendapatkan nilai inkremental deterministik: **Offset**.
3. Sekelompok konsumen bergabung dalam **Consumer Group**. Setiap partisi dalam satu topik hanya dapat dikonsumsi oleh tepat satu instans konsumen dalam satu *group* pada satu waktu.
4. Broker tidak melacak status penerimaan konsumen satu per satu; konsumen secara berkala memperbarui titik baca (*committing offset*) ke topik internal Kafka (`__consumer_offsets`).

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Perbandingan Topologi Komunikasi: Synchronous RPC vs Asynchronous Log Broker

```
========================================================================================
SKENARIO A: SYNCHRONOUS CHAIN (REST/gRPC) - TEMPORAL COUPLING & FAILURE CASCADE
========================================================================================

Client ──[Req 1]──► Service A ──[Req 2]──► Service B ──[Req 3]──► Service C (Database)
                       │                      │                      │
                       │                      │               [High Latency / OOM]
                       ▼                      ▼                      │
                 (Thread Blocked)       (Thread Blocked)      (Fails or Hangs)
                       │                      │                      │
Client ◄──[504 GW]─────┴◄────[504 Timeout]────┴◄────[Connection Drops]┘

Impact: Service A & B mengalami thread exhaustion; seluruh kluster rentan runtuh.

========================================================================================
SKENARIO B: ASYNCHRONOUS EVENT LOG (Kafka) - TEMPORAL DECOUPLING & ISOLATION
========================================================================================

                  ┌────────────────────────────────────────────────────────┐
                  │                 DISTRIBUTED COMMIT LOG                 │
Producer          │                                                        │
(Service A)       │ Topic: orders                                          │
                  │ Partition 0: [Msg 0]─►[Msg 1]─►[Msg 2]─►[Msg 3] (Head)  │
    │             └────────────────────────────────────────────────────────┘
    │ (Write Ack)        ▲                               ▲
    ▼                    │                               │
[Appends Msg]────────────┘                    Offset 1   │   Offset 3
                                                 │       │
                                                 │       │
                                  ┌──────────────┘       └──────────────┐
                                  │                                     │
                     ┌──────────────────────────┐          ┌──────────────────────────┐
                     │ Consumer B (Inventory)   │          │ Consumer C (Notification)│
                     │ State: Processing Msg 2  │          │ State: Up to date        │
                     └──────────────────────────┘          └──────────────────────────┘
                                  │
                          (If Consumer Crashes)
                                  │
                                  ▼
                     Restart -> Fetch from Committed Offset (Msg 1) -> Replay Msg 2
```

### 2. Implementasi EIP: Content-Based Router & Claim Check Pattern

```
                                  [Payload > Threshold Limit]
                          ┌─────────────────────────────────────────┐
                          │                                         │
                          ▼                                         │
                  ┌──────────────┐   Store Large Data  ┌────────────┴───────────┐
 Incoming Msg ───►│ Claim Check  │────────────────────►│ Object Storage (e.g S3)│
                  │ Pattern      │                     └────────────────────────┘
                  └──────┬───────┘                                  ▲
                         │ [Msg Payload Diganti Pointer/UUID]       │
                         ▼                                          │
                  ┌──────────────┐                                  │
                  │ Content-Based│                                  │
                  │ Router (EIP) │                                  │
                  └──────┬───────┘                                  │
                         │                                          │
           ┌─────────────┴─────────────┐                            │
           │ `type == 'ENTERPRISE'`    │ `type == 'RETAIL'`         │
           ▼                           ▼                            │
 ┌───────────────────┐       ┌───────────────────┐                  │
 │ Queue: Enterprise │       │ Queue: Retail     │                  │
 └─────────┬─────────┘       └─────────┬─────────┘                  │
           │                           │                            │
           ▼                           ▼                            │
 ┌───────────────────────────────────────────────┐                  │
 │ Consumer Service                              │                  │
 │ (Resolves UUID Payload via Claim Check Return)├──────────────────┘
 └───────────────────────────────────────────────┘
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah perbandingan implementasi kontrak data antara pendekatan representasi teks REST (JSON) dan representasi skema biner gRPC (Protocol Buffers v3) untuk entitas transaksi pembayaran (*Payment Request*).

### 1. Pendekatan REST/JSON (Contract-less / Implicit Type)
```json
{
  "transaction_id": "8f8b89c2-5c4d-4952-b88e-6701bcf5c366",
  "account_number": 1029384756,
  "amount": 250000.50,
  "currency": "IDR",
  "timestamp": "2023-10-25T14:32:00.123Z",
  "metadata": {
    "ip_address": "192.168.1.10",
    "device": "mobile-android"
  }
}
```
*Kelemahan*: Ukuran payload besar (~250 bytes), overhead parsing tipe data dinamis (angka float vs string, parsing string timestamp RFC3339), tidak ada validasi skema waktu kompilasi (*compile-time schema validation*).

### 2. Pendekatan gRPC/Protobuf (Strictly Typed & Efficient)
File: `payment.proto`
```protobuf
syntax = "proto3";

package payment.v1;

import "google/protobuf/timestamp.proto";

enum Currency {
  CURRENCY_UNSPECIFIED = 0;
  CURRENCY_IDR = 1;
  CURRENCY_USD = 2;
}

message Metadata {
  string ip_address = 1;
  string device = 2;
}

message PaymentRequest {
  string transaction_id = 1;      // UUIDv4 (16 bytes payload raw)
  int64 account_number = 2;       // Encoded as Varint
  double amount = 3;              // 64-bit IEEE 754 float
  Currency currency = 4;          // 1 byte varint enum
  google.protobuf.Timestamp timestamp = 5;
  Metadata metadata = 6;
}

service PaymentService {
  rpc ProcessPayment (PaymentRequest) returns (PaymentResponse);
}

message PaymentResponse {
  bool success = 1;
  string authorization_code = 2;
}
```
*Keunggulan*: Ukuran serialisasi biner berkisar ~60-70 bytes (reduksi >70%), validasi tipe data deterministik di level kode yang dihasilkan oleh compiler (`protoc`), deserialisasi instan pada CPU level assembly tanpa string scanning.

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut adalah contoh sistem pembayaran skala produksi menggunakan **Pola Transaksional Outbox (EIP)** dengan bahasa pemrograman **Go**. Pola ini menjamin semantik pengiriman pesan *At-Least-Once* ke *Message Broker* tanpa terjadi anomali *Dual-Write Failure* (kondisi di mana basis data berhasil di-*commit*, namun broker gagal menerima pesan, atau sebaliknya).

### 1. Skema Database Transaksional (PostgreSQL)
```sql
CREATE TABLE orders (
    order_id UUID PRIMARY KEY,
    customer_id UUID NOT NULL,
    total_amount NUMERIC(12, 2) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE transactional_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type VARCHAR(64) NOT NULL,
    aggregate_id VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ NULL
);

CREATE INDEX idx_outbox_unprocessed ON transactional_outbox (created_at) WHERE processed_at IS NULL;
```

### 2. Implementasi Layer Aplikasi: Order Ingestion (Atomicity Engine)
```go
// order_service.go
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	_ "github.com/lib/pq"
)

type OrderCreatedEvent struct {
	OrderID     string    `json:"order_id"`
	CustomerID  string    `json:"customer_id"`
	Amount      float64   `json:"amount"`
	OccurredAt  time.Time `json:"occurred_at"`
}

type OrderService struct {
	db *sql.DB
}

func (s *OrderService) CreateOrder(ctx context.Context, customerID string, amount float64) (string, error) {
	orderID := uuid.New().String()
	
	// Membuka database transaction
	tx, err := s.db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelReadCommitted})
	if err != nil {
		return "", fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback() // Safe rollback jika tidak sampai commit

	// 1. Mutasi State Bisnis (Table: orders)
	const insertOrderSQL = `
		INSERT INTO orders (order_id, customer_id, total_amount, status, created_at)
		VALUES ($1, $2, $3, $4, $5)`
	now := time.Now().UTC()
	_, err = tx.ExecContext(ctx, insertOrderSQL, orderID, customerID, amount, "PENDING", now)
	if err != nil {
		return "", fmt.Errorf("failed to insert order: %w", err)
	}

	// 2. Tulis Event ke Outbox Table secara atomik dalam transaksi DB yang sama
	eventPayload := OrderCreatedEvent{
		OrderID:    orderID,
		CustomerID: customerID,
		Amount:     amount,
		OccurredAt: now,
	}
	payloadBytes, err := json.Marshal(eventPayload)
	if err != nil {
		return "", fmt.Errorf("failed to serialize event: %w", err)
	}

	const insertOutboxSQL = `
		INSERT INTO transactional_outbox (id, aggregate_type, aggregate_id, payload, created_at)
		VALUES ($1, $2, $3, $4, $5)`
	outboxID := uuid.New().String()
	_, err = tx.ExecContext(ctx, insertOutboxSQL, outboxID, "Order", orderID, payloadBytes, now)
	if err != nil {
		return "", fmt.Errorf("failed to insert outbox event: %w", err)
	}

	// Commit Transaksi: Keduanya (Order & Outbox) persisten secara bersamaan
	if err := tx.Commit(); err != nil {
		return "", fmt.Errorf("failed to commit db transaction: %w", err)
	}

	return orderID, nil
}
```

### 3. Implementasi Outbox Publisher Daemon (Message Relay Engine)
Komponen ini berjalan sebagai proses terpisah (atau goroutine berlatar belakang) untuk membaca outbox table dan merelai pesan ke Message Broker (contoh di bawah diabstraksikan via antarmuka generic `MessagePublisher`).

```go
// outbox_relay.go
package main

import (
	"context"
	"database/sql"
	"log"
	"time"
)

type MessagePublisher interface {
	Publish(ctx context.Context, topic string, routingKey string, payload []byte) error
}

type OutboxRelay struct {
	db        *sql.DB
	publisher MessagePublisher
	batchSize int
}

func (r *OutboxRelay) Start(ctx context.Context, interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			log.Println("Stopping outbox relay worker...")
			return
		case <-ticker.C:
			if err := r.processBatch(ctx); err != nil {
				log.Printf("Error processing outbox batch: %v\n", err)
			}
		}
	}
}

func (r *OutboxRelay) processBatch(ctx context.Context) error {
	// Menghindari race condition antar-worker outbox dengan menggunakan SELECT FOR UPDATE SKIP LOCKED
	const selectSQL = `
		SELECT id, aggregate_id, payload 
		FROM transactional_outbox 
		WHERE processed_at IS NULL 
		ORDER BY created_at ASC 
		LIMIT $1 
		FOR UPDATE SKIP LOCKED`

	tx, err := r.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()

	rows, err := tx.QueryContext(ctx, selectSQL, r.batchSize)
	if err != nil {
		return err
	}
	defer rows.Close()

	type OutboxRecord struct {
		ID          string
		AggregateID string
		Payload     []byte
	}

	var records []OutboxRecord
	for rows.Next() {
		var rec OutboxRecord
		if err := rows.Scan(&rec.ID, &rec.AggregateID, &rec.Payload); err != nil {
			return err
		}
		records = append(records, rec)
	}

	if len(records) == 0 {
		return nil
	}

	const updateSQL = `UPDATE transactional_outbox SET processed_at = $1 WHERE id = $2`
	now := time.Now().UTC()

	for _, record := range records {
		// 1. Publikasikan ke Broker (e.g., Kafka / RabbitMQ)
		err := r.publisher.Publish(ctx, "orders.v1", record.AggregateID, record.Payload)
		if err != nil {
			// Kegagalan pengiriman ke broker: Batalkan transaksi pemrosesan baris ini
			// Record ini akan diambil ulang pada siklus polling berikutnya
			return err
		}

		// 2. Tandai outbox record sebagai telah terkirim
		_, err = tx.ExecContext(ctx, updateSQL, now, record.ID)
		if err != nil {
			return err
		}
	}

	return tx.Commit()
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Memilih protokol dan model perpesanan menuntut kalkulasi komparatif yang ketat:

### 1. Trade-Off Matrix Komunikasi: RPC vs REST vs GraphQL

| Dimensi Parameter | gRPC (Protocol Buffers) | REST (JSON / OpenAPI) | GraphQL |
| :--- | :--- | :--- | :--- |
| **Transport Layer** | HTTP/2 (Multiplexed Streams) | HTTP/1.1 atau HTTP/2 | HTTP/1.1 atau HTTP/2 |
| **Payload Efficiency**| Ekstrem (Biner, Varint, ~70% hemat) | Rendah (String, Verbose JSON) | Fleksibel (JSON, sesuai seleksi field) |
| **Contract Enforcement**| Sangat Kuat (*Compile-time IDL*) | Lemar-Moderat (OpenAPI/Swagger) | Kuat (*Schema Validation Engine*) |
| **Streaming Support** | Native Bi-directional Streaming | Terbatas (Server-Sent Events / Chunked)| Terbatas (GraphQL Subscriptions) |
| **Client Flexibility**| Nol (Terkunci pada representasi RPC)| Moderat (Fixed Endpoints) | Ekstrem (Client mendikte query data) |
| **Caching Mechanism** | Sangat Sulit (Manual at proxy layer) | Native HTTP (Etag, Cache-Control) | Kompleks (POST payload variatif) |
| **Best Used For** | Komunikasi *East-West* antarmikroservis | Eksternal Public API, Webhook integrasi | *Frontend-to-Backend* (BFF Layer) |

### 2. Trade-Off Model Broker: Queue-Centric (RabbitMQ) vs Log-Centric (Kafka)

```
                            [DECISION VECTOR]
                                    │
           Is message replayability / event sourcing required?
                                   / \
                                  /   \
                             YES /     \ NO
                                /       \
                               ▼         ▼
                       [Apache Kafka]    Does the system need complex dynamic
                       [Log-Centric]     routing keys (regex, fanout, topic)?
                                               / \
                                              /   \
                                         YES /     \ NO
                                            /       \
                                           ▼         ▼
                                     [RabbitMQ]   [Direct gRPC / Simple Queue]
```

* **RabbitMQ**:
  * *Pros*: Granularitas rute kompleks, *per-message acknowledgment*, *in-flight message reassignment*, dukungan protokol luas (AMQP, MQTT, STOMP).
  * *Cons*: *Backpressure* buruk jika antrean menumpuk di atas jutaan pesan (beban paging RAM ke disk menurunkan throughput secara eksponensial).
* **Apache Kafka**:
  * *Pros*: Throughput skala jutaan pesan/detik, retensi log berbasis durasi/ukuran memungkinkan *time-traveling analysis* dan *event replay*, arsitektur partisi skala horizontal tinggi.
  * *Cons*: Pola *routing* sederhana (hanya berdasarkan partisi topik), *re-balancing overhead* tinggi pada *consumer group*, tidak dapat menghapus pesan individual.

---

## SEKSI 11 — BEST PRACTICES

1. **Desain Pesan Harus Idempoten (*Idempotent Consumers*)**:
   Jangan pernah berasumsi bahwa jaringan hanya akan mengirimkan pesan satu kali. Broker berkinerja tinggi hanya menjamin semantik *At-Least-Once Delivery*. Konsumen harus menggunakan pola *Deduplication*:
   * Simpan setiap `message_id` atau `idempotency_key` unik dalam tabel database relasional (dengan constraint `UNIQUE`) atau distributed cache berbasis Redis dengan mekanisme atomik `SET NX`.
2. **Propagasi Konteks Terdistribusi (*Distributed Context Propagation*)**:
   Setiap pertukaran pesan (sinkron maupun asinkron) wajib menyertakan metadata pelacakan (*tracing headers*) sesuai standar W3C Trace Context (`traceparent`, `tracestate`).
3. **Pemberian Versi Skema Kontrak (*Schema Evolution Rules*)**:
   * Pada **Protobuf**: Dilarang mengubah nomor tag field (`tag number`) yang sudah dipublikasikan. Jangan pernah menghapus field; gunakan penanda `reserved` untuk mencegah pemakaian ulang nomor tag oleh pengembang lain.
   * Pada **JSON/REST**: Perlakukan field baru sebagai opsional untuk memastikan *backward compatibility*.
4. **Implementasikan Pola *Dead-Letter Queue* (DLQ) dengan *Exponential Backoff & Jitter***:
   Jika terjadi kegagalan pemrosesan pesan akibat galat transien (misalnya *network timeout* database downstream), jangan menolak (*reject*) pesan secara berulang-ulang tanpa jeda (*hot looping*). Lakukan retry berjangka dengan waktu tunggu acak (*jitter*), dan jika ambang batas percobaan terlampaui (e.g., 5 kali), kirim pesan ke DLQ untuk analisis pasca-kegagalan (*post-mortem analysis*).
5. **Pemisahan Trafik *North-South* vs *East-West***:
   * Trafik *North-South* (klien publik luar masuk ke data center): Gunakan REST atau GraphQL di belakang API Gateway. Manfaatkan TLS termination, token validation, rate-limiting, dan WAF.
   * Trafik *East-West* (antarservis di dalam *private service mesh*): Gunakan gRPC via HTTP/2 biner atau message streaming untuk efisiensi latensi dan utilisasi jaringan.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Dual-Write Problem
* **Kesalahan**: Menulis perubahan data ke RDBMS kemudian secara langsung memanggil fungsi `kafkaProducer.send()` dalam blok instruksi yang sama.
* **Dampak**: Jika koneksi jaringan ke Kafka terputus sesaat setelah database di-*commit*, broker tidak pernah menerima event tersebut. Data menjadi tidak konsisten tanpa adanya audit jejak.
* **Solusi**: Gunakan **Transactional Outbox Pattern** atau mekanisme **Change Data Capture (CDC)** seperti Debezium yang membaca *write-ahead log (WAL)* langsung dari mesin database.

### 2. The REST-as-an-ESB Anti-Pattern (Cascading Sync Dependency)
* **Kesalahan**: Membangun proses bisnis monolitik menggunakan panggilan REST sinkron bertingkat antar-10 microservices berbeda secara sekuensial.
* **Dampak**: Waktu respons sistem adalah penjumlahan dari waktu respons 10 servis tersebut ditambah akumulasi latensi jaringan. *Availability* sistem merosot drastis mengikuti hukum probabilitas: $Availability_{total} = \prod_{i=1}^n Availability_i$. Jika masing-masing servis memiliki availability 99%, maka availability keseluruhan adalah $0.99^{10} \approx 90.4\%$.
* **Solusi**: Ubah orkestrasi menjadi koreografi berbasis event (*Event-Driven Choreography*) atau gunakan *Saga Orchestrator* yang bekerja secara asinkron.

### 3. Missing Poison-Pill Handling
* **Kesalahan**: Konsumen Kafka/RabbitMQ mengalami kegagalan panik (*panic crash* atau eksepsi tak tertangani) akibat kesalahan format payload (*poison pill*), lalu broker mendistribusikan ulang (*redelivery*) pesan yang sama secara instan ke instans konsumen baru secara terus-menerus.
* **Dampak**: Konsumen mengalami siklus *crash-loop* terus-menerus (*crash loop backoff*), memblokir pemrosesan partisi tersebut untuk semua pesan berikutnya.
* **Solusi**: Tangkap error eksepsi di blok terluar konsumen (*boundary try-catch*), alihkan pesan bermasalah ke DLQ, lalu *commit* offset pesan tersebut agar pipeline pemrosesan data terus berjalan.

### 4. Overusing GraphQL for Microservice-to-Microservice Integration
* **Kesalahan**: Menggunakan GraphQL sebagai protokol transportasi komunikasi antar-layanan di level internal *backend-to-backend*.
* **Dampak**: Biaya overhead parsing skema AST (*Abstract Syntax Tree*) GraphQL dan validasi kueri pada setiap *hop* jaringan internal sangat tinggi dibanding representasi biner gRPC. Hal ini memboroskan alokasi memori dan CPU.
* **Solusi**: Batasi penggunaan GraphQL pada batas layer presentasi (BFF) untuk agregasi klien aplikasi web/mobile.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario
Sebuah platform *ride-hailing* mengalami lonjakan beban transaksi di mana *Location Tracking Service* memancarkan data koordinat pengemudi setiap 1 detik untuk 50.000 pengemudi aktif. Data ini harus didistribusikan ke:
1. *Passenger Matchmaking Service* (membutuhkan data *real-time*, dapat mentolerir *drop* paket jika pengemudi mengirim koordinat baru).
2. *Fraud & Audit Analytics Service* (memerlukan setiap jejak koordinat tersimpan secara persisten tanpa kehilangan satu pun data).

### Tugas Anda
1. Buat dokumen desain arsitektur integrasi yang menjawab:
   * Mengapa protokol REST HTTP/1.1 tidak dapat digunakan untuk kasus emisi koordinat ini?
   * Pilih protokol jaringan yang paling efisien untuk transmisi dari perangkat IoT/Mobile pengemudi ke Edge Gateway (misalnya: MQTT, WebSocket, atau gRPC Streaming). Berikan justifikasi teknisnya!
   * Desain topologi broker di backend: Apakah Anda akan memilih RabbitMQ atau Apache Kafka untuk mendistribusikan koordinat tersebut ke *Passenger Matchmaking* dan *Audit Analytics*? Tunjukkan bagaimana segmentasi dilakukan.
2. Buat skema kontrak antarmuka menggunakan **Protobuf v3** untuk data transmisi koordinat tersebut, mencakup: `driver_id`, `latitude`, `longitude`, `bearing`, `speed`, `accuracy`, dan `timestamp`.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan-pertanyaan berikut untuk menguji pemahaman arsitektural Anda:

1. **Apa perbedaan mendasar antara *At-Least-Once*, *At-Most-Once*, dan *Effectively-Once (Exactly-Once)* delivery semantics dalam arsitektur perpesanan terdistribusi?**
   * *A.* Tergantung pada apakah basis data menggunakan enkripsi data atau tidak.
   * *B.* At-Least-Once menjamin pesan tidak pernah hilang tetapi dapat terduplikasi; At-Most-Once menjamin pesan tidak pernah terduplikasi namun dapat hilang; Exactly-Once mensyaratkan koordinasi atomik antara offset broker dan status penyimpanan konsumen.
   * *C.* At-Least-Once hanya berlaku untuk REST, sedangkan Exactly-Once hanya ada pada arsitektur gRPC HTTP/2.
   * *D.* Tidak ada perbedaan kinerja; semuanya tergantung pada kecepatan konfigurasi koneksi TCP.

2. **Mengapa *Two-Phase Commit (2PC)* umumnya dihindari dalam integrasi sistem mikroservis modern berskala besar?**
   * *A.* Karena 2PC tidak didukung oleh bahasa pemrograman modern seperti Go atau Rust.
   * *B.* Protokol 2PC memblokir sumber daya lokal selama tahap *prepare-to-commit*, secara drastis meningkatkan latensi transaksi dan menjadi titik rentan terhadap *single-point-of-failure* pada komponen koordinator.
   * *C.* 2PC mengharuskan format data yang digunakan berupa XML murni.
   * *D.* 2PC hanya dapat beroperasi jika seluruh jaringan komputer terhubung menggunakan kabel serat optik privat.

3. **Dalam konteks Apache Kafka, apa yang terjadi jika jumlah konsumen (*consumer instances*) dalam sebuah Consumer Group melebihi jumlah partisi pada topik yang mereka dengarkan?**
   * *A.* Partisi log akan terbagi secara otomatis menjadi sub-partisi tambahan.
   * *B.* Konsumen tambahan tersebut akan berada dalam kondisi siaga (*idle*) dan tidak menerima pesan sama sekali hingga ada konsumen lain yang mati.
   * *C.* Kafka Broker akan melempar pesan kesalahan *OutOfMemoryException*.
   * *D.* Konsumen tambahan akan membaca data secara acak dari topik lain.

4. **Pola EIP manakah yang paling tepat digunakan jika sistem downstream hanya mampu memproses payload maksimal 10 KB, sementara produsen menghasilkan event berukuran 50 MB yang berisi dokumen gambar?**
   * *A.* Splitter Pattern.
   * *B.* Claim Check Pattern.
   * *C.* Content-Based Router.
   * *D.* Message Filter Pattern.

---

### Kunci Jawaban & Evaluasi Diri
* **1: B** — Jaringan terdistribusi tidak mengizinkan pengiriman pesan tunggal yang sempurna tanpa koordinasi status (*state coordination*). Oleh karena itu, *At-Least-Once* yang digabungkan dengan *Idempotent Receiver* adalah standar industri paling tangguh.
* **2: B** — Karakteristik blocking pada 2PC menyebabkan degradasi performa (*low availability* dan *high latency*), yang bertentangan dengan prinsip desentralisasi mikroservis.
* **3: B** — Kafka memegang invarian bahwa satu partisi hanya dialokasikan untuk maksimal satu konsumen dalam grup yang sama guna menjamin urutan pemrosesan pesan per partisi.
* **4: B** — *Claim Check Pattern* menyimpan beban biner masif ke dalam media penyimpanan eksternal (seperti AWS S3 atau Ceph), kemudian hanya mengirimkan data penunjuk referensi berupa ID/URL metadata ke broker pesan.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1. **Buku & Literatur Standar Industri**:
   * Hohpe, Gregor & Woolf, Bobby. (2003). *Enterprise Integration Patterns: Designing, Building, and Deploying Messaging Solutions*. Addison-Wesley Professional.
   * Kleppmann, Martin. (2017). *Designing Data-Intensive Applications: The Big Ideas Behind Reliable, Scalable, and Maintainable Systems*. O'Reilly Media.
   * Newman, Sam. (2021). *Building Microservices: Designing Fine-Grained Systems (2nd Edition)*. O'Reilly Media.
2. **Spesifikasi Standar**:
   * *IETF RFC 7540*: Hypertext Transfer Protocol Version 2 (HTTP/2).
   * *AMQP 0-9-1 Protocol Specification*: Advanced Message Queuing Protocol Specification.
   * *CloudEvents Specification v1.0.2*: A specification for describing event data in common formats (CNCF Standard).
3. **Dokumentasi Resmi Engine**:
   * *Protocol Buffers Language Guide (proto3)*: developers.google.com/protocol-buffers
   * *Apache Kafka Architecture Guide*: kafka.apache.org/documentation

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

Integrasi sistem adalah fondasi pembentuk arsitektur perangkat lunak skala besar. Menggunakan pola komunikasi yang keliru akan melahirkan monolit terdistribusi (*distributed monolith*) yang rapuh dan lambat.

1. **Sinkron vs Asinkron**: Pilih komunikasi sinkron (gRPC/REST) jika pemanggil mutlak membutuhkan jawaban instan untuk menentukan alur eksekusi logika berikutnya. Gunakan komunikasi asinkron (Kafka/RabbitMQ) jika interaksi melibatkan mutasi data, orkestrasi lintas domain, atau memerlukan isolasi temporal (*temporal decoupling*).
2. **Protokol Eksekusi**: Manfaatkan **gRPC** untuk efisiensi transfer data internal (*East-West*), **REST** untuk antarmuka terbuka pihak ketiga (*North-South*), dan **GraphQL** untuk menyajikan data secara terkontrol kepada aplikasi front-end yang kompleks.
3. **Pola Ketahanan Sistem**: Selalu bangun arsitektur perpesanan asinkron di atas prinsip **Idempotency** dan **Transactional Outbox**, guna menjamin konsistensi data absolut tanpa bergantung pada mekanisme locking terdistribusi yang rapuh.

---

## SEKSI 17 — GLOSARIUM

* **Idempotency**: Properti dari suatu operasi di mana eksekusi berulang kali dengan parameter input yang sama menghasilkan state akhir yang identik tanpa efek samping tambahan.
* **Dead-Letter Queue (DLQ)**: Antrean sekunder khusus yang menampung pesan-pesan yang gagal diproses oleh sistem setelah melewati batas maksimal percobaan (*retry limit*).
* **Temporal Coupling**: Ketergantungan waktu di mana dua atau lebih sistem harus aktif, stabil, dan dapat diakses pada detik yang sama agar transaksi dapat berhasil.
* **Head-of-Line (HoL) Blocking**: Fenomena antrean di mana pemrosesan paket data terdepan yang lambat atau terhenti menghambat transfer paket-paket data lain di belakangnya.
* **Partitioned Log**: Struktur data *append-only* terdesentralisasi di mana setiap rekaman data disusun berurutan dan diberi penanda offset unik dalam partisi logik independen.
* **Serialization / Deserialization (SerDe)**: Proses mengubah representasi objek data in-memory ke dalam format biner/teks yang siap dikirimkan melalui jaringan komputer, dan sebaliknya.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Titik Kritis Mahasiswa**: Banyak praktisi sering keliru menganggap *Apache Kafka* sebagai pengganti instan *RabbitMQ*. Tekankan bahwa Kafka adalah distributed log, bukan queuing broker tradisional. Menjalankan skenario *per-message acknowledgment* atau pengacakan *priority queue* pada Kafka adalah bentuk *anti-pattern*.
* **Eksperimen Laboratorium**: Ketika memandu modul ini, instruksikan peserta untuk menyimulasikan kegagalan jaringan (*split-brain* / network drop) menggunakan tools seperti `comcast` atau `pumba`. Demonstrasikan secara visual bagaimana implementasi naif *Dual-Write* berujung pada data korup, kemudian tunjukkan bagaimana *Transactional Outbox Pattern* secara konsisten menyelamatkan integritas sistem.
* **Alokasi Jam Belajar**: Berikan porsi 60% waktu laboratorium pada materi implementasi Idempotency dan Transactional Outbox, karena ini adalah pondasi paling rawan dalam sistem perbankan dan e-commerce nyata.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi**: `v1.0.0` (Oktober 2023)
  * Rilis struktur kurikulum standar awal (20 Seksi).
  * Penambahan skema implementasi nyata Transactional Outbox Engine menggunakan Go dan PostgreSQL.
  * Standarisasi komparasi arsitektural: RPC vs REST vs GraphQL dan RabbitMQ vs Kafka.
  * Integrasi katalog Enterprise Integration Patterns (EIP) Hohpe & Woolf.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `ARC-05-03: Data Architecture, Consistency Models (CAP/PACELC), and Distributed Transactions`
* **Modul Saat Ini**: `ARC-06-01: Integration Patterns & Communication Protocols: Enterprise Integration Patterns (EIP), Synchronous vs Asynchronous Messaging, Message Brokers, RPC vs REST vs GraphQL`
* **Modul Berikutnya**: `ARC-06-02: Microservices Architecture: Decomposition Strategies, Domain-Driven Design Context Boundaries, and Resiliency Patterns`