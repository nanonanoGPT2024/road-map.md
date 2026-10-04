# Modul Pembelajaran: Event-Driven Architecture (EDA) & Pola Konsistensi Data

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: ARCH-0701
* **Nama Modul**: Event-Driven Architecture (EDA) & Pola Konsistensi Data: Event Notification, Event-Carried State Transfer, CQRS, Event Sourcing, Outbox Pattern, Eventual Consistency
* **Kategori**: 06-Architecture-and-System-Design
* **Tingkat Kesulitan**: Tingkat Lanjut (Advanced)
* **Prasyarat**: 
  * Pemahaman mendalam tentang Domain-Driven Design (DDD): Bounded Context, Aggregate Root, Domain Events.
  * Dasar-dasar Transaksi Database: ACID, MVCC, Isolation Levels.
  * Paradigma Komunikasi Terdistribusi: Sinkron (REST/gRPC) vs. Asinkron (Message Broker).
  * Pengalaman operasional dengan salah satu Message Broker/Streaming Engine (misal: Apache Kafka, RabbitMQ, atau AWS SQS/SNS).
* **Estimasi Waktu Belajar**: 12–16 Jam (Teori, Analisis Kasus, dan Implementasi Lab)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Memilih Pola Distribusi Event**: Mengidentifikasi trade-off arsitektural antara *Event Notification* dan *Event-Carried State Transfer* (ECST) berdasarkan metrik coupling, latensi, konsumsi bandwidth, dan otonomi data antar Bounded Context.
2. **Menyelesaikan Masalah Dual-Write**: Mengidentifikasi risiko korupsi data akibat kegagalan parsial (*dual-write problem*) dan mengimplementasikan *Transactional Outbox Pattern* berbasis Change Data Capture (CDC) atau Transactional Polling.
3. **Merancang Sistem Berbasis Event Sourcing**: Membangun *Aggregate Root* yang memvalidasi domain invariants dari event masa lalu (*rehydration*) dan menulis perubahan state hanya dalam bentuk *append-only event log*.
4. **Mengimplementasikan Command Query Responsibility Segregation (CQRS)**: Memisahkan model penulisan (*Command/Write Model*) yang dioptimalkan untuk transaksional dari model pembacaan (*Query/Read Model*) yang didenormalisasi secara asinkron.
5. **Menavigasi dan Memitigasi Eventual Consistency**: Merancang strategi UX dan teknis untuk mengatasi anomali konsistensi data terdistribusi, seperti *Read-Your-Own-Writes*, *Lost Updates*, dan pemrosesan out-of-order event dengan *Idempotent Consumer*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                     [EVENT-DRIVEN ARCHITECTURE (EDA)]
                                     |
         +---------------------------+---------------------------+
         |                                                       |
 [DATA EXCHANGE PATTERNS]                                [CONSISTENCY & STATE]
         |                                                       |
   +-----+-----+                                           +-----+-----+
   |           |                                           |           |
[Event]     [Event-Carried                              [ACID]     [BASE / Eventual
Notification] State Transfer]                           (Local)      Consistency]
   |           |                                           |           |
 (Thin)      (Fat)                                         v           v
                                                    [Dual-Write   [Idempotent
                                                      Problem]     Consumers]
                                                           |           ^
                                                           v           |
                                                    [Transactional     |
                                                    Outbox Pattern]----+
                                                           |
                                                           v
                                                [EVENT PERSISTENCE & QUERY]
                                                           |
                                                    +------+------+
                                                    |             |
                                             [Event Sourcing]  [CQRS]
                                                    |             |
                                                    v             v
                                              [Append-Only]  [Optimized
                                              [Event Store]  Read Projections]
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Dalam arsitektur monolitik tradisional, batas konsistensi ditegakkan melalui transaksi database relasional lokal (ACID). Ketika sebuah operasi bisnis mencakup beberapa entitas, mesin basis data menjamin atomisitas secara absolut: semua perubahan berhasil, atau semuanya dibatalkan secara deterministik.

Ketika arsitektur dipecah menjadi sistem mikroservis (*decoupled services*) untuk mencapai skalabilitas organisasi dan operasional, batas transaksi ACID terfragmentasi. Setiap servis kini mengisolasi databasenya sendiri (*Database-per-Service Pattern*). Komunikasi sinkron melalui HTTP/gRPC sering kali diadopsi secara naif untuk mengoordinasikan status antar-servis. 

Pendekatan sinkron ini menimbulkan tiga krisis utama:

1. **Temporal Coupling & Cascading Failures**: Jika Servis A memanggil Servis B, ketersediaan Servis A adalah fungsi perkalian dari ketersediaan seluruh dependensinya ($Availability_{total} = A_1 \times A_2 \times \dots \times A_n$). Satu servis yang mengalami latensi atau *downtime* akan melumpuhkan seluruh rantai bisnis.
2. **Kerapuhan Koordinasi Transaksional (Distributed Transactions Anti-Pattern)**: Mencoba menerapkan ACID di jaringan menggunakan *Two-Phase Commit* (2PC) pada sistem modern menghancurkan throughput, memblokir thread, rentan terhadap *deadlock* jaringan, dan tidak didukung oleh arsitektur *cloud-native* modern.
3. **The Dual-Write Problem**: Sebuah servis memperbarui database lokalnya lalu mencoba mempublikasikan pesan ke Message Broker. Jika aplikasi mati di antara kedua operasi tersebut, sistem akan berada dalam status *split-brain* permanen: database terupdate tetapi broker tidak menerima pesan, atau sebaliknya.

Penerapan Event-Driven Architecture (EDA), Event Sourcing, Outbox Pattern, dan CQRS bukan sekadar tren teknologi, melainkan fondasi matematis dan arsitektural untuk membangun sistem yang **otonom**, **dapat diskalakan secara independen**, **memiliki auditabilitas mutlak**, dan **tahan terhadap kegagalan partisi jaringan** (*Partition Tolerance*) sesuai Teorema CAP.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Event Notification vs. Event-Carried State Transfer (ECST)
* **Event Notification**: Pola di mana event bertindak sebagai sinyal primitif bahwa sesuatu telah terjadi. Payload bersifat minimalis (hanya ID entitas dan metadata dasar).
  * *Contoh*: `{"eventId": "evt-123", "eventType": "OrderPlaced", "orderId": "ord-999"}`
  * *Implikasi*: Konsumen yang membutuhkan data detail harus melakukan panggilan balik (*callback*) melalui API sinkron ke produsen event. Pola ini menjaga kerahasiaan skema produsen, namun meningkatkan beban jaringan dan menimbulkan temporal coupling saat event diproses secara masif.
* **Event-Carried State Transfer (ECST)**: Pola di mana event membawa seluruh *snapshot* atau delta perubahan data yang dibutuhkan oleh konsumen.
  * *Contoh*: Event memuat `orderId`, `customerId`, `lineItems`, `shippingAddress`, hingga `totalAmount`.
  * *Implikasi*: Konsumen dapat memperbarui data lokal (*replicated view*) tanpa perlu memanggil servis produsen. Memaksimalkan otonomi dan ketahanan sistem, namun meningkatkan ukuran paket pesan (*payload bloat*) dan menimbulkan tantangan *schema evolution*.

### 2. The Dual-Write Problem
Anomali arsitektur yang terjadi saat sebuah aplikasi harus memperbarui status pada dua sistem penyimpanan terdistribusi yang berbeda (misalnya basis data PostgreSQL lokal dan Apache Kafka) tanpa mekanisme koordinasi transaksi atomik. Jika salah satu operasi gagal setelah operasi lainnya berhasil, integritas data sistem rusak.

### 3. Transactional Outbox Pattern
Pola solusi untuk masalah *Dual-Write*. Alih-alih langsung mempublikasikan event ke broker eksternal, event disimpan ke dalam tabel basis data lokal (`outbox`) yang berada dalam konteks transaksi ACID yang sama dengan mutasi status bisnis. Komponen terpisah (*Message Relay* atau CDC engine) kemudian membaca tabel `outbox` dan meneruskannya ke Message Broker dengan jaminan *At-Least-Once Delivery*.

### 4. Event Sourcing (ES)
Paradigma persistensi data di mana status suatu entitas tidak disimpan sebagai snapshot mutabel yang di-overwrite (seperti `UPDATE users SET status = 'ACTIVE'`), melainkan direkam sebagai urutan urut-waktu dari event-event bisnis (*append-only log*) yang tidak dapat diubah (*immutable*). Status terkini dari entitas direkonstruksi secara deterministik dengan memainkan ulang (*replaying*) seluruh event tersebut dari awal masa hidupnya hingga titik waktu tertentu.

### 5. Command Query Responsibility Segregation (CQRS)
Pola arsitektur yang secara eksplisit memisahkan jalur eksekusi untuk modifikasi data (*Command*) dari jalur pembacaan data (*Query*). 
* **Command Side**: Dioptimalkan untuk validasi aturan bisnis (*invariants*), konsistensi transaksional tinggi, dan operasi tulis intensif (umumnya menggunakan Event Sourcing atau database normalisasi tinggi 3NF).
* **Query Side**: Menggunakan basis data denormalisasi (misalnya Elasticsearch untuk pencarian teks, Redis untuk agregasi cepat, atau tabel relasional flat) yang diperbarui secara asinkron dari event-event yang dihasilkan oleh Command Side.

### 6. Eventual Consistency
Karakteristik dari model konsistensi terdistribusi (BASE: *Basically Available, Soft state, Eventual consistency*) di mana sistem menjamin bahwa, jika tidak ada mutasi baru yang terjadi pada suatu item data, semua replika atau proyeksi data di seluruh sistem pada akhirnya (*eventually*) akan konvergen dan menghasilkan nilai yang identik.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### Alur Eksekusi Terpadu: Command -> Outbox -> Projection -> Query

```
               [KLIEN / PENGGUNA]
                  |          ^
         1. Send  |          | 8. Query Read Model
         Command  |          |    (High-performance Read)
                  v          |
          +---------------+  |   +-----------------------+
          | WRITE SERVICE |  |   |     READ SERVICE      |
          +---------------+  |   +-----------------------+
            |           |    |               ^
   Persist  |   Persist |    +---------------+
   Domain   |   Outbox  |                    | 7. Update Projection
   Events   |   Record  |                    |    (Denormalized DB)
   (ACID)   |   (ACID)  |                    |
            v           v                    |
       +---------+  +---------+   6. Consume |
       |  EVENT  |  | OUTBOX  |     Events   |
       |  STORE  |  |  TABLE  |              |
       +---------+  +---------+              |
                         |                   |
            2. CDC Poll /|                   |
               Log Tail  |                   |
                         v                   |
                 +---------------+           |
                 | RELAY WORKER  |           |
                 +---------------+           |
                         |                   |
                3. Publish Message           |
                         |                   |
                         v                   |
                 +---------------+           |
                 |    MESSAGE    |-----------+
                 |    BROKER     |
                 +---------------+
```

1. **Penerimaan Command**: Klien mengirimkan instruksi perubahan status (misal: `PlaceOrderCommand`). Write Service memuat riwayat event entitas terkait dari `Event Store` untuk memvalidasi *business invariants*.
2. **Commit Transaksional Lokal**:
   * Event baru (misal: `OrderPlacedEvent`) di-*append* ke `Event Store`.
   * Bersamaan dengan itu, representasi serial dari event tersebut dimasukkan ke dalam tabel `outbox` dalam cakupan transaksi database lokal yang sama (`BEGIN ... COMMIT`).
3. **Penyaluran Event (Message Relay)**:
   * Proses latar belakang (seperti Debezium menggunakan CDC atau polling engine) mendeteksi baris baru pada tabel `outbox`.
   * Record diteruskan ke Apache Kafka / RabbitMQ.
   * Setelah broker memberikan konfirmasi (*acknowledgement*), baris pada `outbox` ditandai selesai (*processed*) atau dihapus.
4. **Konsumsi & Proyeksi CQRS (Read Side)**:
   * Read Service mengonsumsi `OrderPlacedEvent` dari broker.
   * Mekanisme *Idempotent Consumer* memeriksa apakah event dengan `eventId` tersebut telah diproses untuk menghindari duplikasi (*at-least-once deduplication*).
   * Data diekstrak dan ditulis ke Read Model (misal: tabel database read-only terdenormalisasi atau document store).
5. **Penyajian Data Konsisten**: Klien membaca data melalui Read API. Terdapat jendela waktu mikrodetik hingga beberapa detik di mana Read Model berada pada status *eventually consistent* sebelum proyeksi selesai dilakukan.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Diagram 1: Anatomi Dual-Write Problem vs. Transactional Outbox Pattern

```
SCENARIO A: THE DUAL-WRITE PROBLEM (ANTI-PATTERN)
==================================================
Thread Application
       |
       |-- (1) BEGIN TRANSACTION
       |-- (2) UPDATE Orders SET status = 'PAID' WHERE id = 101;
       |-- (3) COMMIT TRANSACTION  ---> [ DATABASE: SUCCESS ]
       |
       |-- [ CRASH / NETWORK PARTITION TERJADI DI SINI ]
       |
       X-- (4) broker.publish("OrderPaid", {orderId: 101}) ---> [ BROKER: TIDAK PERNAH TERKIRIM ]
       
RESULT: DATABASE KONSISTEN LOKAL, SISTEM HILIR (DOWNSTREAM) TIDAK PERNAH TAHU. DATA RUSAK SISTEMIK.

-------------------------------------------------------------------------------------------------

SCENARIO B: TRANSACTIONAL OUTBOX PATTERN (SOLUSI ARSITEKTURAL)
==============================================================
Thread Application
       |
       |-- (1) BEGIN TRANSACTION (ACID Local Boundary)
       |-- (2) UPDATE Orders SET status = 'PAID' WHERE id = 101;
       |-- (3) INSERT INTO Outbox (id, event_type, payload, status)
       |       VALUES ('evt-1', 'OrderPaid', '{"orderId": 101}', 'PENDING');
       |-- (4) COMMIT TRANSACTION  ---> [ DATABASE LOKAL MENJAMIN ATOMISITAS (1) & (2) ]
       |
   [DATABASE ENGINE TRANSACTION LOG (WAL)]
       |
       | Log Mining (Debezium / PostgreSQL pgoutput / Transactional Poller)
       v
[Relay Worker Engine]
       |
       |-- (5) broker.publish(event.type, event.payload)
       |       |<--- [ ACK from Kafka/RabbitMQ ]
       |
       |-- (6) UPDATE Outbox SET status = 'PUBLISHED' WHERE id = 'evt-1';
               (Atau DELETE FROM Outbox WHERE id = 'evt-1')

RESULT: JAMINAN "AT-LEAST-ONCE DELIVERY" TERCAPAI TANPA DISTRIBUTED TRANSACTIONS.
```

---

### Diagram 2: Siklus Hidup Event Sourcing & CQRS Projections

```
=====================================================================================================
COMMAND PIPELINE (WRITE MODEL)                         QUERY PIPELINE (READ MODEL)
=====================================================================================================

 [ HTTP POST /orders ]                                  [ HTTP GET /orders/101 ]
          |                                                       |
          v                                                       v
  +---------------+                                       +---------------+
  | CommandHandler|                                       | QueryHandler  |
  +---------------+                                       +---------------+
          |                                                       |
          | 1. Load History Events                                | 6. Fast Flat Read
          v                                                       v
   +--------------+                                      +-----------------+
   | Aggregate    |                                      | Projection View |
   | Rehydration  |                                      | (PostgreSQL View|
   +--------------+                                      | /Elasticsearch) |
          |                                              +-----------------+
          | 2. Execute Business Logic                             ^
          |    (Assert invariant: total > 0)                      |
          v                                                       | 5. Apply Projection
   +--------------+                                               |    (Denormalize)
   | Emit Event   |                                               |
   | [OrderPlaced]|                                       +---------------+
   +--------------+                                       | EventConsumer |
          |                                               +---------------+
          | 3. Append To Log                                      ^
          v                                                       | 4. Subscribe
  [ EVENT STORE ]=================================================+
   (Append-Only)
   Streams:
   - Event 1: OrderCreated
   - Event 2: OrderItemAdded
   - Event 3: OrderPlaced (NEW)
=====================================================================================================
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut perbandingan implementasi pola *Event Notification* vs. *Event-Carried State Transfer (ECST)* dalam bentuk struktur event payload JSON.

### Event Notification (Thin Event)
Konsumen hanya diberi tahu bahwa sebuah peristiwa terjadi. Detail mutasi harus diambil sendiri melalui RPC.

```json
{
  "specversion": "1.0",
  "id": "a8f3b610-86b2-4d2b-9279-d26b7ef999bb",
  "source": "/order-service/orders",
  "type": "com.enterprise.order.status_changed",
  "time": "2026-03-30T10:15:30Z",
  "datacontenttype": "application/json",
  "data": {
    "orderId": "ORD-98214",
    "status": "APPROVED"
  }
}
```
*Kelemahan*: Servis penagihan (Billing Service) dan servis logistik (Shipping Service) yang menerima event ini harus membombardir `Order Service` dengan HTTP request `GET /orders/ORD-98214` untuk mengetahui item pesanan dan alamat tujuan.

### Event-Carried State Transfer (Rich/Fat Event)
Semua state snapshot data yang relevan dikemas langsung di dalam pesan. Konsumen bersifat otonom.

```json
{
  "specversion": "1.0",
  "id": "e4b2d184-c689-4d2b-8a89-9a2f7c001aef",
  "source": "/order-service/orders",
  "type": "com.enterprise.order.order_placed",
  "time": "2026-03-30T10:15:30Z",
  "datacontenttype": "application/json",
  "data": {
    "orderId": "ORD-98214",
    "customerId": "CUST-4412",
    "status": "PLACED",
    "lineItems": [
      {
        "sku": "SKU-PRO-MACBOOK",
        "quantity": 1,
        "price": 2400.00
      }
    ],
    "shippingAddress": {
      "street": "Sudirman Central Business District",
      "city": "Jakarta Selatan",
      "postalCode": "12190"
    },
    "totalAmount": 2400.00,
    "currency": "USD",
    "version": 1
  }
}
```
*Keuntungan*: Konsumen langsung memperbarui database internalnya sendiri secara lokal. Tidak ada pemanggilan API balik, jaringan terlindungi dari lonjakan beban mendadak (*stampeding herd*).

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Implementasi arsitektur nyata: **Order Processing Engine** yang menerapkan **Event Sourcing**, **Transactional Outbox**, dan **CQRS Projection Engine** menggunakan Node.js/TypeScript dan basis data PostgreSQL.

### 1. Struktur Database Relasional (DDL)

```sql
-- DDL PostgreSQL untuk Event Store, Outbox, dan CQRS Read Model

CREATE TABLE event_store (
    id BIGSERIAL PRIMARY KEY,
    aggregate_id VARCHAR(64) NOT NULL,
    aggregate_type VARCHAR(64) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    version INT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_aggregate_version UNIQUE (aggregate_id, version)
);

CREATE TABLE outbox (
    id UUID PRIMARY KEY,
    aggregate_type VARCHAR(64) NOT NULL,
    aggregate_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ NULL
);

-- CQRS Read Model: Flat denormalized table untuk optimasi pembacaan
CREATE TABLE read_order_projections (
    order_id VARCHAR(64) PRIMARY KEY,
    customer_id VARCHAR(64) NOT NULL,
    total_amount NUMERIC(12, 2) NOT NULL,
    status VARCHAR(32) NOT NULL,
    item_count INT NOT NULL,
    last_updated TIMESTAMPTZ NOT NULL
);
```

### 2. Implementasi Aggregate Root & Event Sourcing (Write Side)

```typescript
// domain/order-aggregate.ts

export interface DomainEvent {
  aggregateId: string;
  eventType: string;
  payload: any;
  version: number;
}

export class OrderAggregate {
  private _id: string;
  private _customerId: string;
  private _status: 'DRAFT' | 'CONFIRMED' | 'CANCELLED';
  private _totalAmount: number = 0;
  private _version: number = 0;
  private _uncommittedEvents: DomainEvent[] = [];

  constructor(id: string) {
    this._id = id;
    this._status = 'DRAFT';
  }

  get id(): string { return this._id; }
  get version(): number { return this._version; }
  get uncommittedEvents(): DomainEvent[] { return [...this._uncommittedEvents]; }

  // Rehidrasi State dari Histori Event
  public static rehydrate(id: string, history: DomainEvent[]): OrderAggregate {
    const aggregate = new OrderAggregate(id);
    for (const event of history) {
      aggregate.apply(event, false);
    }
    return aggregate;
  }

  // Bisnis Logic: Command Handling
  public createOrder(customerId: string, totalAmount: number): void {
    if (this._version !== 0) {
      throw new Error(`Order ${this._id} telah diinisialisasi sebelumnya.`);
    }
    if (totalAmount <= 0) {
      throw new Error("Total amount harus lebih besar dari 0.");
    }

    const event: DomainEvent = {
      aggregateId: this._id,
      eventType: 'OrderCreated',
      payload: { customerId, totalAmount },
      version: this._version + 1
    };

    this.apply(event, true);
  }

  public confirmOrder(): void {
    if (this._status !== 'DRAFT') {
      throw new Error(`Hanya order dengan status DRAFT yang dapat dikonfirmasi.`);
    }

    const event: DomainEvent = {
      aggregateId: this._id,
      eventType: 'OrderConfirmed',
      payload: { confirmedAt: new Date().toISOString() },
      version: this._version + 1
    };

    this.apply(event, true);
  }

  // State Mutator: Memetakan Event ke State Internal
  private apply(event: DomainEvent, isNew: boolean): void {
    switch (event.eventType) {
      case 'OrderCreated':
        this._customerId = event.payload.customerId;
        this._totalAmount = event.payload.totalAmount;
        this._status = 'DRAFT';
        break;
      case 'OrderConfirmed':
        this._status = 'CONFIRMED';
        break;
      default:
        throw new Error(`Event type tidak dikenali: ${event.eventType}`);
    }

    this._version = event.version;

    if (isNew) {
      this._uncommittedEvents.push(event);
    }
  }

  public clearUncommittedEvents(): void {
    this._uncommittedEvents = [];
  }
}
```

### 3. Repository dengan Atomic Transactional Outbox Pattern

```typescript
// infrastructure/order-repository.ts
import { Pool, PoolClient } from 'pg';
import { OrderAggregate, DomainEvent } from '../domain/order-aggregate';
import { randomUUID } from 'crypto';

export class OrderRepository {
  constructor(private pool: Pool) {}

  public async getById(orderId: string): Promise<OrderAggregate> {
    const client = await this.pool.connect();
    try {
      const res = await client.query(
        'SELECT event_type, payload, version FROM event_store WHERE aggregate_id = $1 ORDER BY version ASC',
        [orderId]
      );

      if (res.rows.length === 0) {
        throw new Error(`Aggregate Order ${orderId} tidak ditemukan.`);
      }

      const events: DomainEvent[] = res.rows.map(row => ({
        aggregateId: orderId,
        eventType: row.event_type,
        payload: row.payload,
        version: row.version
      }));

      return OrderAggregate.rehydrate(orderId, events);
    } finally {
      client.release();
    }
  }

  public async save(aggregate: OrderAggregate): Promise<void> {
    const client: PoolClient = await this.pool.connect();
    const eventsToCommit = aggregate.uncommittedEvents;

    if (eventsToCommit.length === 0) return;

    try {
      await client.query('BEGIN');

      for (const event of eventsToCommit) {
        // 1. Simpan ke Event Store (Append-Only)
        await client.query(
          `INSERT INTO event_store (aggregate_id, aggregate_type, event_type, payload, version)
           VALUES ($1, $2, $3, $4, $5)`,
          [event.aggregateId, 'ORDER', event.eventType, JSON.stringify(event.payload), event.version]
        );

        // 2. Simpan ke Outbox dalam Transaksi ACID yang SAMA
        const outboxId = randomUUID();
        await client.query(
          `INSERT INTO outbox (id, aggregate_type, aggregate_id, event_type, payload)
           VALUES ($1, $2, $3, $4, $5)`,
          [outboxId, 'ORDER', event.aggregateId, event.eventType, JSON.stringify(event.payload)]
        );
      }

      await client.query('COMMIT');
      aggregate.clearUncommittedEvents();
    } catch (error) {
      await client.query('ROLLBACK');
      throw new Error(`Persistensi Aggregate Gagal: ${(error as Error).message}`);
    } finally {
      client.release();
    }
  }
}
```

### 4. Background Relay Worker (Outbox Dispatcher)

```typescript
// workers/outbox-relay.ts
import { Pool } from 'pg';

export class OutboxRelayWorker {
  private isRunning: boolean = false;

  constructor(private pool: Pool) {}

  public async start(): Promise<void> {
    this.isRunning = true;
    while (this.isRunning) {
      await this.processBatch();
      await new Promise(resolve => setTimeout(resolve, 500)); // Polling interval
    }
  }

  private async processBatch(): Promise<void> {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');

      // Ambil data dengan lock baris agar aman dari multi-instance worker
      const selectRes = await client.query(
        `SELECT id, aggregate_id, event_type, payload 
         FROM outbox 
         WHERE processed_at IS NULL 
         ORDER BY created_at ASC 
         LIMIT 50 
         FOR UPDATE SKIP LOCKED`
      );

      for (const row of selectRes.rows) {
        // Simulasi pengiriman ke Message Broker eksternal (Kafka / RabbitMQ)
        await this.publishToBroker(row);

        // Update status proses
        await client.query(
          'UPDATE outbox SET processed_at = NOW() WHERE id = $1',
          [row.id]
        );
      }

      await client.query('COMMIT');
    } catch (err) {
      await client.query('ROLLBACK');
      console.error('Relay Worker Error:', err);
    } finally {
      client.release();
    }
  }

  private async publishToBroker(event: any): Promise<void> {
    // Implementasi producer Kafka/RabbitMQ aktual di sini
    // Jaminan at-least-once: kegagalan di sini melempar error dan menunda mark processed
    console.log(`[Broker Published] Event: ${event.event_type} for Aggregate: ${event.aggregate_id}`);
  }

  public stop(): void {
    this.isRunning = false;
  }
}
```

### 5. CQRS Projection Engine (Read Side)

```typescript
// projections/order-projection-handler.ts
import { Pool } from 'pg';

export class OrderProjectionHandler {
  constructor(private pool: Pool) {}

  // Idempotent handler untuk mengonsumsi event dan memperbarui read model
  public async handle(event: { event_type: string; aggregate_id: string; payload: any }): Promise<void> {
    const client = await this.pool.connect();
    try {
      if (event.event_type === 'OrderCreated') {
        await client.query(
          `INSERT INTO read_order_projections 
             (order_id, customer_id, total_amount, status, item_count, last_updated)
           VALUES ($1, $2, $3, $4, $5, NOW())
           ON CONFLICT (order_id) DO NOTHING`,
          [event.aggregate_id, event.payload.customerId, event.payload.totalAmount, 'DRAFT', 1]
        );
      } else if (event.event_type === 'OrderConfirmed') {
        await client.query(
          `UPDATE read_order_projections 
           SET status = 'CONFIRMED', last_updated = NOW() 
           WHERE order_id = $1`,
          [event.aggregate_id]
        );
      }
    } finally {
      client.release();
    }
  }
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Menerapkan EDA, Outbox, CQRS, dan Event Sourcing memerlukan pertimbangan untung-rugi yang objektif:

| Pola Arsitektural | Keuntungan Utama (Pros) | Konsekuensi Negatif (Cons / Trade-offs) | Kapan Digunakan | Kapan Dihindari |
| :--- | :--- | :--- | :--- | :--- |
| **Event Sourcing** | Audit trail otomatis 100% tanpa celah; analisis time-travel debugging; fleksibilitas membangun proyeksi baru di masa depan. | Kompleksitas evolusi skema (*upcasting*); kueri agregat tidak dapat dilakukan langsung pada event store; learning curve tim tinggi. | Domain keuangan, asuransi, sistem checkout, pelacakan inventaris teregulasi. | Aplikasi CRUD sederhana di mana riwayat mutasi tidak memiliki nilai bisnis. |
| **CQRS** | Penskalaan independen antara Read dan Write; optimasi performa skema pembacaan secara ekstrem (*zero joins*). | Konsistensi data tertunda (*eventual consistency lag*); kode redundant (dua domain model); kebutuhan sinkronisasi database ganda. | Sistem dengan perbandingan read/write sangat timpang (misal 99:1); domain pelaporan masif. | Aplikasi kecil dengan traffic seimbang di mana data konsisten absolut (*strong consistency*) dibutuhkan seketika. |
| **Transactional Outbox** | Mengeliminasi *dual-write problem*; menjamin *at-least-once delivery* menggunakan transaksi basis data lokal yang reliabel. | Meningkatkan beban I/O basis data write; membutuhkan *worker polling* atau konfigurasi kompleks CDC (Debezium, WAL parser). | Setiap microservice yang memublikasikan event bisnis penting ke message broker. | Layanan telemetry/logging non-kritis di mana kehilangan data tidak merusak status bisnis. |
| **Event-Carried State Transfer** | Konsumen otonom penuh; kueri antar-servis berkurang drastis; latensi sistem hilir sangat cepat. | *Payload bloat*; duplikasi penyimpanan data antar tim; pelanggaran enkapsulasi domain jika seluruh field internal terekspos. | Sistem terdistribusi skala enterprise lintas wilayah dengan latensi jaringan antar servis tinggi. | Servis internal satu tim di mana bandwidth terbatas atau struktur data sangat sering berubah (*unstable schema*). |

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan Idempotency Keys di Sisi Konsumen**:
   Pola pengiriman di hampir semua broker adalah *at-least-once*. Pastikan setiap konsumen mengimplementasikan *Idempotent Consumer Pattern* (menggunakan tabel `processed_messages` atau Redis SETNX) dengan acuan `event_id` sebelum mengeksekusi logika bisnis.
2. **Pisahkan Event Schema Contract Menggunakan Registry**:
   Manfaatkan Schema Registry (Apache Avro, Protobuf, atau JSON Schema). Larang perubahan yang merusak (*breaking changes* seperti menghapus field wajib atau mengubah tipe data primitif) untuk memastikan backward/forward compatibility.
3. **Optimalkan Event Sourcing dengan Snapshotting**:
   Untuk agregat dengan siklus hidup panjang (ribuan event), proses *rehydration* dapat memicu *high memory* dan latensi lambat. Buat *Snapshot* setiap 50 atau 100 event. Ketika meload agregat, muat snapshot terakhir lalu mainkan ulang event sisanya.
4. **Implementasikan Correlation ID dan Causation ID**:
   Setiap event harus menyertakan metadata:
   * `correlationId`: ID unik alur transaksi dari hulu (dimulai dari request HTTP klien awal).
   * `causationId`: ID pesan/command spesifik yang memicu lahirnya event ini.
   Ini adalah prasyarat mutlak untuk *distributed tracing* (OpenTelemetry).
5. **Mitigasi Masalah "Read-Your-Own-Writes" di Frontend**:
   Karena adanya eventual consistency lag antara Write Model dan Read Model CQRS, klien web/mobile mungkin mengalami kebingungan setelah mutasi. Gunakan strategi:
   * *Optimistic UI*: Render perubahan lokal secara langsung di frontend sebelum server mengonfirmasi.
   * *Version Token / ETag*: Kirim versi aggregate kembali ke klien. Klien melakukan polling API Read sampai versi tersebut sama atau lebih besar dari token transaksi.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Dual-Write Naif
```typescript
// ANTI-PATTERN: JANGAN DILAKUKAN
async function updateOrder(orderId: string, status: string) {
  // Operasi 1
  await db.query("UPDATE orders SET status = $1 WHERE id = $2", [status, orderId]);
  
  // Operasi 2 (Jika koneksi jaringan ke Kafka putus, pesan hilang selamanya)
  await kafkaProducer.send({ topic: 'orders', message: { orderId, status } });
}
```
*Koreksi*: Gunakan Transactional Outbox Pattern dengan mengemas kedua operasi dalam satu transaksi SQL lokal.

### 2. Menggunakan Event Sourcing untuk Status Semata (Mutasi State Langsung)
Mengubah state agregat secara langsung di dalam command handler tanpa melalui mekanisme event:
```typescript
// SALAH: Merusak determinisme event store
class Order {
  confirm() {
    this.status = 'CONFIRMED'; // Salah!
    this.events.push(new OrderConfirmed());
  }
}

// BENAR: Ubah state hanya di method mutator berbasis event
class Order {
  confirm() {
    this.apply(new OrderConfirmed()); // State internal diubah di dalam method apply()
  }
}
```

### 3. Mengubah Event Masa Lalu (Rewriting History)
Memodifikasi struktur atau nilai dari event yang sudah tersimpan di Event Store.
*Koreksi*: Event store harus strictly *immutable*. Jika terjadi kesalahan transaksi kompensasi, terbitkan event pembatalan baru (*Compensating Event* seperti `OrderCancelled` atau `InvoiceAdjusted`), jangan pernah melakukan SQL `UPDATE` atau `DELETE` pada tabel event store.

### 4. Menjadikan Event Broker sebagai Database Primer Kueri
Mencoba membaca stream Kafka secara langsung dari antarmuka API pengguna untuk mencari entitas tertentu.
*Koreksi*: Message broker dirancang untuk streaming dan publish/subscribe. Gunakan CQRS untuk memproyeksikan data ke database yang tepat (PostgreSQL, MongoDB, Elasticsearch) untuk melayani kueri klien secara efisien.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Deteksi dan Evaluasi Pola Integrasi (Tingkat Dasar)
Sebuah arsitektur e-commerce memiliki `Inventory Service` dan `Order Service`. Ketika pesanan dibuat, `Inventory Service` harus mengurangi stok barang. Jika menggunakan *Event Notification*, apa langkah yang harus diambil `Inventory Service`? Bandingkan dengan jika menggunakan *Event-Carried State Transfer*.
* **Instruksi**: Tuliskan payload event JSON untuk kedua skenario dan buat tabel perbandingan total HTTP call yang terjadi saat 1.000 pesanan masuk bersamaan.

### Latihan 2: Implementasi Idempotent Consumer (Tingkat Menengah)
Simulasikan skenario di mana broker mengirimkan event yang sama sebanyak tiga kali berturut-turut karena kegagalan ACK jaringan.
* **Instruksi**: Buat modul penanganan event dalam TypeScript/JavaScript yang menggunakan skema penyimpanan lokal untuk mengecek deduplikasi event berbasis `event_id`. Pastikan event kedua dan ketiga diabaikan tanpa melempar runtime exception yang memutus consumer pipeline.

### Latihan 3: Implementasi CQRS Projection Replay Engine (Tingkat Lanjut)
Model tabel proyeksi pembacaan `read_order_projections` mengalami korupsi atau skema database perlu dirombak total (misalnya penambahan kolom baru `customer_tier`).
* **Instruksi**: Buat skrip *re-indexing* yang:
  1. Mengosongkan (*truncate*) tabel proyeksi pembacaan lama.
  2. Membaca secara streaming seluruh baris dari tabel `event_store` dari ID awal secara berurutan.
  3. Memproyeksikan ulang seluruh data ke skema baru tanpa downtime pada write-model.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan-pertanyaan skenario berikut untuk menguji pemahaman arsitektural Anda:

1. **Mengapa protokol Two-Phase Commit (2PC) dihindari dalam sistem mikroservis modern berskala besar?**
   * A. Karena 2PC tidak didukung oleh database relasional.
   * B. Karena 2PC bersifat memblokir (blocking protocol), meningkatkan latensi secara ekstrem, dan menciptakan titik kegagalan tunggal (*single point of failure*) di Distributed Transaction Coordinator.
   * C. Karena 2PC hanya bekerja pada sistem NoSQL.
   * D. Karena 2PC melanggar prinsip Single Responsibility.

2. **Pada pola Transactional Outbox, apa peran utama dari Change Data Capture (CDC) seperti Debezium?**
   * A. Memvalidasi skema event sebelum dimasukkan ke database.
   * B. Membaca commit log / write-ahead log (WAL) database secara langsung dan mengalirkan data outbox ke message broker tanpa membebani database dengan query polling berulang.
   * C. Menjalankan fungsi enkripsi otomatis pada event.
   * D. Menjamin pengiriman pesan dengan semantik *Exactly-Once* secara native tanpa perlu penanganan idempotensi di sisi konsumen.

3. **Kapan teknik Snapshotting WAJIB dipertimbangkan dalam sistem yang menggunakan Event Sourcing?**
   * A. Ketika data aggregate harus diekspor ke format CSV.
   * B. Ketika jumlah event dalam satu instance aggregate mencapai ribuan, sehingga proses memuat ulang event untuk merekonstruksi status (*rehydration*) menyebabkan latensi CPU dan memori yang tidak dapat ditoleransi.
   * C. Ketika outbox table mengalami kepenuhan kapasitas hard disk.
   * D. Ketika kueri CQRS membutuhkan data realtime.

4. **Bagaimana cara paling aman menangani perubahan skema (*Schema Evolution*) pada Event Sourcing di mana ada penambahan field baru yang mandatory pada event masa depan?**
   * A. Menjalankan query `UPDATE event_store SET payload = ...` untuk mengubah seluruh record event lama di database.
   * B. Mengabaikan event lama dan menghapus histori transaksi yang sudah lewat dari satu tahun.
   * C. Menerapkan pola *Upcaster* di lapisan infrastruktur, yang bertugas mencegat event lama saat dibaca dari database dan mentransformasikannya ke format versi terbaru sebelum dikirim ke aggregate.
   * D. Mengganti nama database dan memulai event store dari nol.

5. **Apa yang dimaksud dengan semantik "At-Least-Once Delivery" dan apa implikasinya bagi perancang arsitektur perangkat lunak hilir?**
   * A. Pesan dijamin terkirim tepat satu kali; konsumen tidak perlu melakukan apa-apa.
   * B. Pesan dijamin terkirim setidaknya satu kali, tetapi ada kemungkinan pesan duplikat diterima; oleh karena itu konsumen WAJIB bersifat idempoten (*idempotent*).
   * C. Pesan hanya dikirim jika konsumen sedang aktif, jika tidak maka pesan akan hilang.
   * D. Pesan dijamin sampai sebelum durasi timeout HTTP tercapai.

### Kunci Jawaban & Penjelasan Singkat
* **1: B** — 2PC memperkenalkan penguncian sumber daya (*resource locking*) di seluruh partisipan jaringan, merusak skalabilitas dan toleransi partisi.
* **2: B** — CDC memanfaatkan transaction log mesin database (misal WAL PostgreSQL) secara asinkron tanpa overhead polling SQL (`SELECT FOR UPDATE`).
* **3: B** — Tanpa snapshotting, memutar ulang (*replaying*) ribuan event untuk satu agregat akan menyebabkan penurunan drastis pada Throughput Command API.
* **4: C** — Event store harus immutable. Upcaster memungkinkan software beradaptasi dengan skema baru tanpa merusak rekaman historis asli.
* **5: B** — Kegagalan jaringan setelah proses commit pesan sering kali memicu pengiriman ulang (*retry*); idempotensi pada konsumen adalah kompensasi wajib untuk reliabilitas terdistribusi.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku**:
  * *Designing Data-Intensive Applications* oleh Martin Kleppmann (O'Reilly Media) — Rujukan fundamental konsistensi data terdistribusi, replikasi, dan partisi.
  * *Microservices Patterns: With examples in Java* oleh Chris Richardson (Manning Publications) — Analisis mendalam mengenai Transactional Outbox, Saga, dan Event-Driven Architecture.
  * *Patterns, Principles, and Practices of Domain-Driven Design* oleh Scott Millett & Nick Tune (Wrox) — Panduan desain Aggregate dan implementasi Event Sourcing.
* **Artikel Arsitektural Klasik**:
  * Martin Fowler: *"What do you mean by 'Event-Driven'?"* (2017) — Taksonomi empat pola utama EDA.
  * Greg Young: *"CQRS and Event Sourcing"* Video Series & Whitepapers — Fondasi matematis dan operasional CQRS.
* **Dokumentasi & Spesifikasi Terbuka**:
  * CloudEvents Specification (CNCF): `https://cloudevents.io/` — Standar industri terbuka untuk metadata pertukaran event lintas platform.
  * Debezium Documentation: `https://debezium.io/documentation/` — Pola implementasi Change Data Capture (CDC) modern untuk Outbox Pattern.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. Sistem terdistribusi menuntut dekomposisi data, yang secara inheren mengorbankan transaksi ACID global demi ketersediaan dan ketahanan jaringan (Teorema CAP).
2. Pola **Event Notification** menjaga privasi data produsen namun menciptakan dependensi kueri balik, sedangkan **Event-Carried State Transfer (ECST)** memberikan otonomi maksimal bagi konsumen dengan mengorbankan beban payload.
3. Masalah **Dual-Write** diselesaikan secara elegan menggunakan **Transactional Outbox Pattern**, yang menjamin atomisitas lokal antara manipulasi data bisnis dan pencatatan event sebelum diteruskan ke broker via CDC atau Relaying.
4. **Event Sourcing** merevolusi persistensi dengan mencatat setiap peristiwa sebagai fakta historis *immutable* (*append-only*), menjamin pelacakan audit dan kemampuan memproyeksikan ulang data kapan pun diperlukan.
5. **CQRS** mengisolasi kompleksitas write-model (yang sarat validasi bisnis) dari read-model (yang sarat optimasi kueri), memungkinkan penskalaan infrastruktur data yang presisi dan independen.
6. Konsistensi dalam arsitektur berbasis event bersifat **Eventual Consistency**. Sistem harus dibangun dengan asumsi bahwa kegagalan pengiriman dan duplikasi pesan adalah keniscayaan: semantik *At-Least-Once Delivery* menuntut penanganan *Idempotent Consumer* di seluruh batas sistem.

---

## SEKSI 17 — GLOSARIUM

* **Aggregate Root**: Entitas utama dalam Domain-Driven Design yang bertindak sebagai gerbang tunggal untuk menegakkan aturan validitas transaksi (*invariants*) bagi seluruh entitas di dalam batasnya.
* **Append-Only Log**: Struktur data di mana data baru hanya dapat ditambahkan di akhir file/tabel; modifikasi atau penghapusan data lama tidak diizinkan.
* **Change Data Capture (CDC)**: Sekumpulan pola perangkat lunak untuk mengidentifikasi dan menangkap data yang telah diubah dalam basis data dan mengirimkannya ke sistem hilir secara realtime.
* **Dual-Write Problem**: Kegagalan sistemik saat mencoba menulis data ke dua media penyimpanan yang berbeda tanpa koordinasi transaksi terdistribusi yang aman.
* **Event Sourcing (ES)**: Pola persistensi di mana perubahan status aplikasi direkam secara berurutan sebagai serangkaian event.
* **Eventual Consistency**: Model konsistensi di mana replika data dijamin akan menjadi konsisten jika tidak ada update baru setelah jangka waktu tertentu.
* **Idempotent**: Karakteristik suatu operasi yang menghasilkan status sistem yang sama persis meskipun dieksekusi berkali-kali dengan input yang identik.
* **Rehydration**: Proses merekonstruksi status agregat terkini dengan cara membaca dan memainkan ulang seluruh event historisnya dari awal secara sekuensial.
* **Upcasting**: Mekanisme transformasi yang mencegat event usang dari database dan mengonversinya secara dinamis ke skema versi terbaru sebelum dikonsumsi oleh aplikasi.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Penekanan Khusus**:
  * Pastikan siswa tidak menyamakan Event Sourcing dengan Event-Driven Architecture. Jelaskan secara tegas: *EDA adalah pola arsitektur komunikasi antar-servis, sedangkan Event Sourcing adalah pola persistensi internal dalam satu servis*. Sebuah sistem bisa menerapkan EDA tanpa Event Sourcing, begitu pula sebaliknya.
  * Hindari jebakan mengimplementasikan Event Sourcing di seluruh bagian sistem. Tekankan konsep "Aggregate Boundary": hanya modul dengan nilai audit tinggi, kompleksitas transaksional tinggi, atau alur kerja multi-tahap yang membutuhkan Event Sourcing. Bagian generik/CRUD harus tetap menggunakan pendekatan Active Record atau Data Mapper konvensional.
* **Simulasi Kelas**:
  * Matikan koneksi docker container Kafka sesaat setelah database lokal melakukan commit transaksi SQL untuk mendemonstrasikan secara visual apa yang terjadi saat sistem terkena krisis *Dual-Write*.
  * Tunjukkan bagaimana tabel `outbox` menahan status tersebut hingga container broker kembali menyala tanpa ada data yang hilang.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi**: 1.0.0
* **Tanggal Rilis**: 30 Maret 2026
* **Catatan Perubahan**:
  * Rilis modul perdana kurikulum Software Design & Architecture.
  * Cakupan komprehensif EDA, CQRS, Event Sourcing, Outbox Pattern, dan Eventual Consistency.
  * Penambahan kode implementasi produksi Node.js/TypeScript dengan PostgreSQL.
  * Diagram arsitektur visual ASCII interaktif untuk alur Dual-Write dan Proyeksi CQRS.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `ARCH-0604` — Microservices Decomposition Strategies & Database-per-Service Anti-patterns
* **Modul Berikutnya**: `ARCH-0702` — Distributed Sagas: Choreography vs. Orchestration & Compensating Transactions
* **Daftar Modul Terkait**:
  * `ARCH-0502` — Domain-Driven Design: Strategic & Tactical Modeling
  * `DATA-0301` — Distributed Data Management, Partitioning, and Replication
  * `SYSD-0402` — Message Brokers Internals: Kafka Partitions, RabbitMQ Exchanges, & Delivery Semantics