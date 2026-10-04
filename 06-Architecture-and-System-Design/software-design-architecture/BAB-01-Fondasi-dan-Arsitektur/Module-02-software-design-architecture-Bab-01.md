# BAB 01: Fondasi dan Arsitektur
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengonstruksi arsitektur aplikasi berbasis *Domain-Driven Design* (DDD) taktis menggunakan *Hexagonal Architecture* (*Ports and Adapters*) tanpa ketergantungan siklis (*cyclic dependencies*).
- Mengisolasi domain core logic dari framework, I/O, database, dan protokol transport dengan batas abstraksi yang kuat (*strict interface decoupling*).
- Mengimplementasikan pola konsistensi data terdistribusi tingkat lanjut: *Transactional Outbox Pattern* dengan *Aggregate Roots* untuk menjamin semantik pengiriman *at-least-once* tanpa *two-phase commit* (2PC).
- Menganalisis *trade-offs* sistem pada level performa, latensi, konsistensi data (*eventual vs strong*), dan kompleksitas operasional saat memisahkan *Read* dan *Write* models (CQRS).
- Menemukan dan memitigasi *anti-patterns* arsitektural seperti *Anemic Domain Model*, *Leaky Abstractions*, dan *Distributed Monolith*.

---

### 2. Prerequisite
- Pemahaman mendalam tentang OOP/Functional Paradigm dan SOLID Principles (Bab 01 - Modul 01).
- Pengalaman dengan bahasa pemrograman strongly-typed (misal: TypeScript, Go, Java, atau C#).
- Pemahaman dasar tentang transaksi basis data ACID (Atomicity, Consistency, Isolation, Durability) dan *database locking mechanisms*.
- Pemahaman dasar tentang message broker (misal: Apache Kafka, RabbitMQ, atau AWS SQS).

---

### 3. Concept & Internal Architecture (Mendalam)

Arsitektur perangkat lunak enterprise modern berakar pada pemisahan kepentingan (*Separation of Concerns*) dan inversi dependensi (*Dependency Inversion Principle*). Ketika sistem berkembang, arsitektur *Layered (N-Tier)* tradisional sering kali runtuh karena lapisan domain secara gradual terpolusi oleh entitas ORM, anotasi framework, dan dependensi infrastruktur.

```
       [Arsitektur Tradisional]                      [Hexagonal / Ports & Adapters]
      
          UI / Presentation                                 HTTP / CLI / Queue
                 ↓                                                  ↓
          Business Logic                               +---------------------------+
                 ↓                                     |       Driving Port        |
          Database / Infra                             +---------------------------+
                                                                    ↓
    (Domain bergantung langsung                       +-----------------------------+
       ke detail infrastruktur)                       |        Core Domain          |
                                                      |   (Entities, Aggregates,    |
                                                      |       Value Objects)        |
                                                      +-----------------------------+
                                                                    ↑
                                                       +---------------------------+
                                                       |       Driven Port         |
                                                       +---------------------------+
                                                                    ↑
                                                               SQL / NoSQL / Broker
```

#### Komponen Utama Hexagonal Architecture (Alistair Cockburn)

1. **Inside the Hexagon (Core Domain)**:
   - **Domain Entities & Value Objects**: Representasi state dan invariants bisnis murni. Tidak boleh memiliki dependensi ke framework eksternal (misal: `@Entity` dari TypeORM/Hibernate dilarang keras di core domain).
   - **Aggregate Roots**: Batas konsistensi transaksional (*transactional consistency boundary*). Modifikasi terhadap entitas internal aggregate hanya dapat dilakukan melalui root aggregate.
   - **Domain Services**: Logika bisnis murni yang melibatkan multientitas atau aggregate yang tidak cocok diletakkan pada satu entitas tunggal.
   - **Domain Events**: Rekam jejak fakta masa lalu yang terjadi di dalam aggregate (`OrderPlaced`, `PaymentReceived`).

2. **Ports (Batas Hexagon)**:
   - **Primary / Driving Ports (Inbound)**: Interface yang mendefinisikan apa yang domain tawarkan kepada dunia luar. Use-case boundary interfaces diimplementasikan oleh Application Service layer.
   - **Secondary / Driven Ports (Outbound)**: Interface yang mendefinisikan dependensi eksternal yang dibutuhkan oleh domain/application layer (misal: `OrderRepositoryPort`, `EventPublisherPort`, `NotificationServicePort`).

3. **Adapters (Outside the Hexagon)**:
   - **Driving Adapters**: Komponen penerima input dari luar yang memanggil Driving Ports (misal: REST Controllers, GraphQL Resolvers, Kafka Consumers, CLI commands).
   - **Driven Adapters**: Implementasi konkret dari Driven Ports (misal: `PostgresOrderRepository` yang mengimplementasikan `OrderRepositoryPort`, `KafkaEventPublisher` yang mengimplementasikan `EventPublisherPort`).

#### Siklus Transaksional Domain & Transactional Outbox Pattern
Ketika aggregate memodifikasi state dan harus mempublikasikan event bisnis, eksekusi dua operasi berbeda (INSERT/UPDATE ke database dan PUBLISH ke message broker) dalam transaksi non-atomik rentan terhadap *dual-write failure problem*:

```
          Application Layer                      Database               Message Broker
                 │                                   │                         │
                 ├───── 1. BEGIN TX ─────────────────┤                         │
                 ├───── 2. UPDATE Order State ───────┤                         │
                 ├───── 3. INSERT Outbox Event ──────┤                         │
                 ├───── 4. COMMIT TX ────────────────┤                         │
                 │                                   │                         │
                 │              [Transaction Complete Atomically]              │
                 │                                   │                         │
                 │                                   │                         │
         Outbox Processor                            │                         │
                 │                                   │                         │
                 ├───── 5. Poll / Read CDC ──────────┤                         │
                 ├───── 6. Dispatch Event ─────────────────────────────────────►
                 ├───── 7. Mark as Published ────────┤                         │
```

---

### 4. Why & What

| Dimensi | Mengapa Diperlukan (*Why*) | Apa Konkretnya (*What*) |
|---|---|---|
| **Evolusi Bisnis** | Logika bisnis berubah lebih sering daripada dependensi infrastruktur, atau sebaliknya. | Isolasi domain tanpa dependensi terhadap database, UI, atau vendor cloud. |
| **Testabilitas Mutlak** | Pengujian logika bisnis yang melibatkan integrasi database lambat, rapuh, dan sulit diisolasi. | Core domain dapat diuji 100% menggunakan *pure unit test* (tanpa mock database, tanpa container) dalam orde milidetik. |
| **Konsistensi Data Terdistribusi** | Dual-write problem menyebabkan inkonsistensi fatal antara basis data relasional dan message broker saat crash. | Penerapan *Transactional Outbox Pattern* menjamin semantik *at-least-once message delivery*. |
| **Proteksi Invariant** | Modifikasi langsung ke database tabel relasional memotong aturan validasi domain (*anemic model*). | Enkapsulasi seluruh mutasi state di dalam Aggregate Root; state hanya bisa bermutasi melalui pemanggilan *business methods*. |

---

### 5. How (Workflow Detail)

Alur eksekusi enterprise transaction melalui Hexagonal Architecture:

```
[Request]
   │
   ▼
[Driving Adapter] (e.g., Express HTTP Controller)
   │  - Validasi schema transport (zod/joi)
   │  - Unpack HTTP request menjadi DTO
   │
   ▼
[Driving Port / Application Service] (e.g., CheckoutOrderUseCase)
   │  - Eksekusi database unit of work (Begin Transaction)
   │  - Mengambil Domain Aggregate via Driven Port (e.g., OrderRepositoryPort.findById)
   │
   ▼
[Core Domain Engine] (e.g., OrderAggregate)
   │  - Validasi business invariant (e.g., check credit limit, stock constraints)
   │  - Mutasi internal state aggregate
   │  - Catat domain event ke internal buffer aggregate (`this.recordEvent(...)`)
   │
   ▼
[Application Service]
   │  - Simpan Aggregate state ke Database via `OrderRepositoryPort.save`
   │  - Ekstrak recorded domain events dari Aggregate
   │  - Simpan domain events ke tabel `outbox_events` (Driven Port) dalam transaksi database yang SAMA
   │  - Commit Transaction
   │
   ▼
[Driven Adapter] (Postgres Transactional Driver)
   │  - Atomically writes to `orders` and `outbox_events`
   │
   ▼
[Outbox Relay Worker] (Background Poller or Debezium CDC)
   │  - Membaca record dari `outbox_events` yang berstatus `PENDING`
   │  - Mempublikasikannya ke Message Broker (Kafka/RabbitMQ)
   │  - Memperbarui status outbox menjadi `PUBLISHED`
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Hexagonal: Power Socket & Adapter Universal
Bayangkan domain aplikasi Anda adalah peralatan elektronik presisi tinggi buatan Swiss yang beroperasi menggunakan arus DC 12V murni.
- **Hexagon (Domain)**: Perangkat internal Anda yang tidak peduli dari mana sumber listrik berasal, asalkan menerima spesifikasi input yang tepat.
- **Ports**: Soket input standar pada perangkat Anda.
- **Adapters**: Konverter colokan (adaptor US, adaptor UK, adaptor dinding EU, atau aki mobil). Ketika Anda pindah dari Eropa (PostgreSQL) ke Inggris (MongoDB), Anda tidak membongkar sirkuit internal perangkat Anda; Anda hanya mengganti adaptor colokannya.

```
       [ HTTP API ]               [ CLI Script ]
             │                          │
             ▼                          ▼
      +--------------+          +---------------+
      | HTTP Adapter |          |  CLI Adapter  |
      +-------┬------+          +-------┬-------+
              │                         │
              └────────────┬────────────┘
                           ▼
                  +------------------+
                  | Use-Case Port In |
                  +--------┬---------+
                           │
             ==============▼==============
             |      HEXAGON BOUNDARY     |
             |                           |
             |       Aggregate Root      |
             |      [ Business Rules ]   |
             |       Value Objects       |
             |                           |
             ==============┬==============
                           │
                  +--------┴---------+
                  |  Repo Port Out   |
                  +--------┬---------+
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
      +---------------+         +---------------+
      | Postgres Impl |         | DynamoDB Impl |
      +-------┬-------+         +-------┬-------+
              │                         │
              ▼                         ▼
        (PostgreSQL)                (DynamoDB)
```

---

### 7. Simple Example & Practical Example

Berikut adalah implementasi clean Hexagonal Architecture berbasis Domain-Driven Design menggunakan TypeScript.

#### 7.1. Simple Example: Value Object dengan Proteksi Invariant Murni

```typescript
// domain/value-objects/money.vo.ts
export class Money {
  private readonly amount: number;
  private readonly currency: string;

  private constructor(amount: number, currency: string) {
    this.amount = amount;
    this.currency = currency;
  }

  public static create(amount: number, currency: string): Money {
    if (amount < 0) {
      throw new Error("DomainViolation: Money cannot be negative.");
    }
    if (!["IDR", "USD"].includes(currency)) {
      throw new Error(`DomainViolation: Unsupported currency ${currency}.`);
    }
    // Menghindari floating point error dengan representasi fixed precision integer (e.g. cents)
    return new Money(Math.round(amount), currency);
  }

  public add(other: Money): Money {
    if (this.currency !== other.currency) {
      throw new Error("DomainViolation: Currency mismatch during addition.");
    }
    return new Money(this.amount + other.amount, this.currency);
  }

  public getAmount(): number {
    return this.amount;
  }

  public getCurrency(): string {
    return this.currency;
  }

  public equals(other: Money): boolean {
    return this.amount === other.amount && this.currency === other.currency;
  }
}
```

#### 7.2. Practical Enterprise Example: Order Aggregate, Ports, Use Case & Outbox Repository

```typescript
// ==========================================
// 1. DOMAIN LAYER (Pure Logic, Zero Dependency)
// ==========================================

export interface DomainEvent {
  eventId: string;
  occurredOn: Date;
  eventType: string;
  aggregateId: string;
  payload: Record<string, unknown>;
}

export class OrderPlacedEvent implements DomainEvent {
  public readonly eventId = crypto.randomUUID();
  public readonly occurredOn = new Date();
  public readonly eventType = "OrderPlaced";

  constructor(
    public readonly aggregateId: string,
    public readonly payload: { totalAmount: number; currency: string; customerId: string }
  ) {}
}

export class OrderId {
  constructor(private readonly value: string) {
    if (!value || value.length < 8) {
      throw new Error("DomainViolation: Invalid OrderId.");
    }
  }
  public toString(): string {
    return this.value;
  }
}

export enum OrderStatus {
  DRAFT = "DRAFT",
  CONFIRMED = "CONFIRMED",
  CANCELLED = "CANCELLED"
}

// Aggregate Root
export class Order {
  private events: DomainEvent[] = [];

  private constructor(
    private readonly id: OrderId,
    private readonly customerId: string,
    private status: OrderStatus,
    private total: Money
  ) {}

  public static create(id: OrderId, customerId: string, initialTotal: Money): Order {
    const order = new Order(id, customerId, OrderStatus.DRAFT, initialTotal);
    
    // Invariant: Customer ID must exist
    if (!customerId) {
      throw new Error("DomainViolation: CustomerId is required.");
    }

    return order;
  }

  public confirm(): void {
    if (this.status !== OrderStatus.DRAFT) {
      throw new Error(`DomainViolation: Cannot confirm order in status ${this.status}.`);
    }

    if (this.total.getAmount() <= 0) {
      throw new Error("DomainViolation: Cannot confirm an order with zero amount.");
    }

    this.status = OrderStatus.CONFIRMED;

    // Record Event
    this.recordEvent(
      new OrderPlacedEvent(this.id.toString(), {
        totalAmount: this.total.getAmount(),
        currency: this.total.getCurrency(),
        customerId: this.customerId
      })
    );
  }

  private recordEvent(event: DomainEvent): void {
    this.events.push(event);
  }

  public pullDomainEvents(): DomainEvent[] {
    const recordedEvents = [...this.events];
    this.events = [];
    return recordedEvents;
  }

  // Getters for persistence mapping
  public getId(): OrderId { return this.id; }
  public getCustomerId(): string { return this.customerId; }
  public getStatus(): OrderStatus { return this.status; }
  public getTotal(): Money { return this.total; }
}

// ==========================================
// 2. PORTS LAYER (Application Boundary)
// ==========================================

export interface OutboxMessage {
  id: string;
  aggregateId: string;
  eventType: string;
  payload: string;
  createdAt: Date;
  published: boolean;
}

export interface UnitOfWorkSession {
  // Database transaction handle wrapper
  client: unknown;
}

export interface OrderRepositoryPort {
  save(order: Order, session: UnitOfWorkSession): Promise<void>;
  findById(id: OrderId, session: UnitOfWorkSession): Promise<Order | null>;
}

export interface OutboxRepositoryPort {
  saveAll(events: OutboxMessage[], session: UnitOfWorkSession): Promise<void>;
}

export interface TransactionManagerPort {
  runInTransaction<T>(work: (session: UnitOfWorkSession) => Promise<T>): Promise<T>;
}

// Inbound Port (Driving Port)
export interface ConfirmOrderCommand {
  orderId: string;
}

export interface ConfirmOrderUseCasePort {
  execute(command: ConfirmOrderCommand): Promise<void>;
}

// ==========================================
// 3. APPLICATION SERVICE (Use Case Coordinator)
// ==========================================

export class ConfirmOrderUseCase implements ConfirmOrderUseCasePort {
  constructor(
    private readonly orderRepo: OrderRepositoryPort,
    private readonly outboxRepo: OutboxRepositoryPort,
    private readonly txManager: TransactionManagerPort
  ) {}

  public async execute(command: ConfirmOrderCommand): Promise<void> {
    const orderId = new OrderId(command.orderId);

    await this.txManager.runInTransaction(async (session) => {
      const order = await this.orderRepo.findById(orderId, session);
      if (!order) {
        throw new Error(`NotFound: Order ${command.orderId} does not exist.`);
      }

      // Execute Business Logic
      order.confirm();

      // Extract generated domain events
      const events = order.pullDomainEvents();

      const outboxMessages: OutboxMessage[] = events.map((evt) => ({
        id: evt.eventId,
        aggregateId: evt.aggregateId,
        eventType: evt.eventType,
        payload: JSON.stringify(evt.payload),
        createdAt: evt.occurredOn,
        published: false
      }));

      // Atomic Persistence (Repository + Outbox) in the same transaction
      await this.orderRepo.save(order, session);
      await this.outboxRepo.saveAll(outboxMessages, session);
    });
  }
}

// ==========================================
// 4. DRIVEN ADAPTER (Postgres Example)
// ==========================================

import { Pool, PoolClient } from "pg";

export class PostgresTransactionManager implements TransactionManagerPort {
  constructor(private readonly pool: Pool) {}

  public async runInTransaction<T>(work: (session: UnitOfWorkSession) => Promise<T>): Promise<T> {
    const client = await this.pool.connect();
    try {
      await client.query("BEGIN;");
      const session: UnitOfWorkSession = { client };
      const result = await work(session);
      await client.query("COMMIT;");
      return result;
    } catch (error) {
      await client.query("ROLLBACK;");
      throw error;
    } finally {
      client.release();
    }
  }
}

export class PostgresOrderRepository implements OrderRepositoryPort {
  public async save(order: Order, session: UnitOfWorkSession): Promise<void> {
    const client = session.client as PoolClient;
    const query = `
      INSERT INTO orders (id, customer_id, status, total_amount, currency)
      VALUES ($1, $2, $3, $4, $5)
      ON CONFLICT (id) DO UPDATE SET
        status = EXCLUDED.status,
        total_amount = EXCLUDED.total_amount;
    `;
    await client.query(query, [
      order.getId().toString(),
      order.getCustomerId(),
      order.getStatus(),
      order.getTotal().getAmount(),
      order.getTotal().getCurrency()
    ]);
  }

  public async findById(id: OrderId, session: UnitOfWorkSession): Promise<Order | null> {
    const client = session.client as PoolClient;
    const res = await client.query("SELECT * FROM orders WHERE id = $1 FOR UPDATE;", [id.toString()]);
    if (res.rows.length === 0) return null;
    
    const row = res.rows[0];
    const money = Money.create(Number(row.total_amount), row.currency);
    
    // Reconstruction via reflective factory method or reconstitute builder
    const order = Order.create(new OrderId(row.id), row.customer_id, money);
    if (row.status === OrderStatus.CONFIRMED) {
      // Reconstitute state without re-emitting events
      order.confirm();
      order.pullDomainEvents(); // flush replayed events
    }
    return order;
  }
}

export class PostgresOutboxRepository implements OutboxRepositoryPort {
  public async saveAll(events: OutboxMessage[], session: UnitOfWorkSession): Promise<void> {
    if (events.length === 0) return;
    const client = session.client as PoolClient;
    for (const event of events) {
      const query = `
        INSERT INTO outbox_events (id, aggregate_id, event_type, payload, created_at, published)
        VALUES ($1, $2, $3, $4, $5, $6);
      `;
      await client.query(query, [
        event.id,
        event.aggregateId,
        event.eventType,
        event.payload,
        event.createdAt,
        event.published
      ]);
    }
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Ride-Hailing & Logistics Dispatch System
- **Skala Operasi**: 500.000 transaksi/menit, puncaknya 2.000.000 pesan telemetry/detik.
- **Problem**: Layanan dispatch order mengalami kondisi *ghost bookings* (pengemudi menerima notifikasi pemesanan tetapi order dibatalkan oleh database timeout, atau saldo dompet terpotong ganda akibat network retry). Arsitektur lama menyatukan modul *Pricing*, *Driver Matching*, *Wallet Billing*, dan *Tracking* dalam satu shared-database monolith.

```
[Arsitektur Lama - Anti-Pattern Monolith Shared Database]
  [Passenger App]  [Driver App]
         │              │
         ▼              ▼
   +---------------------------+
   |    Monolithic Backend     |
   +-------------┬-------------+
                 │ (Locking table & contention)
                 ▼
      [ Single Relational DB ]
      (orders, wallets, drivers, trips)
```

#### Solusi Arsitektur
1. **Dekomposisi Domain Bounded Context**:
   - *Trip Context*: Bertanggung jawab mengelola status perjalanan via Finite State Machine (FSM).
   - *Billing Context*: Pengelolaan saldo dan otorisasi pembayaran (Strong Consistency).
   - *Fulfillment Context*: Pencocokan pengemudi menggunakan spatial-indexing (Eventual Consistency).

2. **Pola Transaksional & Integrasi**:
   - Pemisahan database per bounded context.
   - Pemanfaatan *Transactional Outbox* menggunakan Debezium CDC engine untuk membaca Write-Ahead Log (WAL) PostgreSQL Trip Database dan melakukan streaming event ke Apache Kafka.
   - Idempotent Consumers pada Driver Matching Service menggunakan deduplication key (`trip_id` + `status_version`).

```
[Arsitektur Baru - Bounded Context & Event Streaming]
 +──────────────── Trip Context ─────────────────+
 │                                               │
 │  [Trip Service] ──► [Postgres DB (Trip)]      │
 │                            │ (WAL)            │
 │                            ▼                  │
 │                    [Debezium CDC]             │
 +────────────────────────────┼──────────────────+
                              │
                              ▼ (Kafka Event: TripCreated)
 +──────────────── Fulfillment Context ──────────+
 │                            │                  │
 │                            ▼                  │
 │                 [Matching Engine (Go)]        │
 │                            │                  │
 │                            ▼                  │
 │                     [Driver Scored]           │
 +───────────────────────────────────────────────+
```

3. **Hasil Metrik**:
   - Database lock contention turun sebesar 92%.
   - Latensi dispatch P99 turun dari 4.200ms ke 320ms.
   - Insiden duplikasi transaksi dompet turun menjadi nol (0 ppm).

---

### 9. Trade-offs

```
                  Hexagonal + Outbox Pattern
                         ▲
                        / \
                       /   \
     [Decoupled & Fault]   [High Complexity]
         Tolerant                 │
           │                      ▼
           ▼            [Latency Overhead in CDC]
   [High Dev Cost] ◄───► [Eventual Consistency]
```

| Dimensi | Keuntungan (*Pros*) | Konsekuensi / Biaya (*Cons*) |
|---|---|---|
| **Performa & Throughput** | Operasi write terisolasi; locking database hanya berlangsung singkat pada aggregate target tanpa menunggu third-party call (misal Kafka network call). | Terjadi *replication lag* antara waktu write di database lokal hingga pesan terkirim ke broker oleh outbox processor (50ms - 500ms). |
| **Latensi Query** | Read-models dapat dioptimasi secara terpisah (misal di-denormalisasi ke Redis/Elasticsearch). | Arsitektur CQRS mengharuskan klien mentoleransi *Eventual Consistency* saat read dilakukan segera setelah write. |
| **Skalabilitas Tim** | Bounded context jelas. Tim logistik dapat bekerja tanpa takut merusak domain penagihan (*zero structural coupling*). | Dibutuhkan investasi tata kelola kontrak (schema registry, proto/avro) yang ketat; modifikasi skema domain memerlukan versioning yang cermat. |
| **Infrastruktur & Cost** | Utilisasi database lebih efisien karena tidak ada thread yang menggantung (*hung threads*) menunggu eksternal I/O. | Tambahan biaya infrastruktur untuk outbox reader (Debezium cluster, Kafka brokers, connector workers, dan observability stack). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Leaking ORM Entities into Domain Core
- **Gejala**: Domain Entity menggunakan decorator ORM (`@Column`, `@Entity`, `@OneToMany`).
- **Dampak Fatal**: Skema database mendikte representasi model bisnis. Perubahan relasi tabel merusak invariant bisnis.
- **Solusi**: Definisikan Entitas Domain murni (Plain Old Language Objects). Buat *Data Mappers* terpisah di dalam Adapter Layer untuk konversi dari/ke struktur ORM/Database Row.

#### 2. Cross-Aggregate Object References
- **Gejala**: Aggregate `Order` menyimpan referensi instance objek `Customer` secara langsung (`this.customer = customerInstance`).
- **Dampak Fatal**: Batas memori aggregate menjadi kabur; persistensi satu aggregate memicu pembaruan tak terkontrol pada aggregate lain, memicu *deadlock* pada transaksi database konkruen.
- **Solusi**: Aggregate hanya boleh mereferensikan Aggregate lain menggunakan **Identity (ID)** murni (`this.customerId = customer.getId()`).

#### 3. Dual-Write Anti-Pattern
- **Gejala**: Memanggil `kafkaProducer.send()` tepat setelah `db.commit()` di Application Service.
- **Dampak Fatal**: Jika koneksi jaringan ke Kafka putus setelah DB commit, state di database telah berubah tetapi event tidak terkirim, membuat downstream services kehilangan sinkronisasi secara permanen.
- **Solusi**: Gunakan Transactional Outbox Pattern dengan mengemas commit database dan penulisan outbox event dalam satu blok transaksi atomik lokal.

---

### 11. Best Practices (Production Checklist)

#### Domain Model Integrity
- [ ] Aggregate Root mengisolasi seluruh mutasi internal: tidak ada *public setters*.
- [ ] Validasi invarians domain dieksekusi di *Constructor* dan *Business Methods*, bukan di Controller.
- [ ] Value Objects bersifat *immutable*: setiap mutasi menghasilkan instance baru.
- [ ] Aggregate tidak memiliki referensi memori ke aggregate lain (hanya menyimpan ID).

#### Infrastructure & Outbox
- [ ] Tabel `outbox_events` dibuat dengan indeks pada `(published, created_at)` untuk efisiensi polling, atau terintegrasi dengan Change Data Capture (CDC Engine).
- [ ] Consumer event downstream didesain bersifat **Idempotent** (menghindari duplikasi akibat semantik *at-least-once delivery*).
- [ ] Transaksi database menggunakan tingkat isolasi (*Isolation Level*) minimal `READ COMMITTED` atau `REPEATABLE READ` dengan *pessimistic locking* (`FOR UPDATE`) jika terjadi race condition ketat pada Aggregate.

---

### 12. Hands-on Practice

Buat dan eksekusi struktur arsitektur modular berikut pada direktori kerja Anda:

```bash
mkdir -p hands-on/m02/src/{domain,application,infrastructure}
cd hands-on/m02
npm init -y
npm install typescript @types/node pg @types/pg --save-dev
npx tsc --init
```

#### Struktur File Direktori
```
hands-on/m02/
├── package.json
├── tsconfig.json
└── src/
    ├── domain/
    │   ├── model.ts          # Aggregate Root & Value Objects
    │   └── events.ts         # Domain Event Interfaces
    ├── application/
    │   ├── ports.ts          # Repository & Use-case Interfaces
    │   └── checkout.ts       # Use-case Interactor
    ├── infrastructure/
    │   ├── in-memory-db.ts   # Test Double Adapter (Simulasi Atomic Tx)
    └── index.ts              # Entrypoint Execution
```

#### File 1: `src/domain/events.ts`
```typescript
export interface DomainEvent {
  eventId: string;
  occurredOn: Date;
  eventType: string;
  aggregateId: string;
  payload: Record<string, unknown>;
}

export class OrderCreatedEvent implements DomainEvent {
  public readonly eventId = crypto.randomUUID();
  public readonly occurredOn = new Date();
  public readonly eventType = "OrderCreated";

  constructor(
    public readonly aggregateId: string,
    public readonly payload: { customerId: string; amount: number }
  ) {}
}
```

#### File 2: `src/domain/model.ts`
```typescript
import { DomainEvent, OrderCreatedEvent } from "./events";

export class Order {
  private events: DomainEvent[] = [];

  constructor(
    public readonly id: string,
    public readonly customerId: string,
    private amount: number,
    private status: "PENDING" | "PAID"
  ) {
    if (amount <= 0) throw new Error("InvalidAmount: Must be greater than zero.");
  }

  public static create(id: string, customerId: string, amount: number): Order {
    const order = new Order(id, customerId, amount, "PENDING");
    order.events.push(new OrderCreatedEvent(id, { customerId, amount }));
    return order;
  }

  public pullEvents(): DomainEvent[] {
    const emitted = [...this.events];
    this.events = [];
    return emitted;
  }

  public getAmount(): number { return this.amount; }
  public getStatus(): string { return this.status; }
}
```

#### File 3: `src/application/ports.ts`
```typescript
import { Order } from "../domain/model";
import { DomainEvent } from "../domain/events";

export interface IUnitOfWork {
  execute<T>(work: () => Promise<T>): Promise<T>;
}

export interface IOrderRepository {
  save(order: Order): Promise<void>;
}

export interface IOutboxRepository {
  append(events: DomainEvent[]): Promise<void>;
}
```

#### File 4: `src/infrastructure/in-memory-db.ts`
```typescript
import { IOrderRepository, IOutboxRepository, IUnitOfWork } from "../application/ports";
import { Order } from "../domain/model";
import { DomainEvent } from "../domain/events";

export class InMemoryStorage implements IUnitOfWork, IOrderRepository, IOutboxRepository {
  public ordersTable = new Map<string, any>();
  public outboxTable: DomainEvent[] = [];

  // Snapshot memory untuk rollback simulasi transaksi
  private ordersSnapshot = new Map<string, any>();
  private outboxSnapshot: DomainEvent[] = [];

  public async execute<T>(work: () => Promise<T>): Promise<T> {
    // Take Snapshot
    this.ordersSnapshot = new Map(this.ordersTable);
    this.outboxSnapshot = [...this.outboxTable];

    try {
      const result = await work();
      return result;
    } catch (error) {
      // Rollback
      this.ordersTable = new Map(this.ordersSnapshot);
      this.outboxTable = [...this.outboxSnapshot];
      throw error;
    }
  }

  public async save(order: Order): Promise<void> {
    this.ordersTable.set(order.id, {
      id: order.id,
      customerId: order.customerId,
      amount: order.getAmount(),
      status: order.getStatus()
    });
  }

  public async append(events: DomainEvent[]): Promise<void> {
    this.outboxTable.push(...events);
  }
}
```

#### File 5: `src/index.ts`
```typescript
import { Order } from "./domain/model";
import { InMemoryStorage } from "./infrastructure/in-memory-db";

async function bootstrap() {
  console.log("=== Memulai Eksekusi Enterprise Hexagonal Outbox Pattern ===");

  const storage = new InMemoryStorage();

  // Test Case 1: Transaksi Sukses
  await storage.execute(async () => {
    const order = Order.create("ORD-001", "CUST-999", 500000);
    const events = order.pullEvents();

    await storage.save(order);
    await storage.append(events);
  });

  console.log("State Berhasil Disimpan:");
  console.log("Orders:", Array.from(storage.ordersTable.entries()));
  console.log("Outbox Events:", storage.outboxTable);

  // Test Case 2: Simulasi Crash dan Atomic Rollback
  try {
    await storage.execute(async () => {
      const orderFail = Order.create("ORD-002", "CUST-888", 250000);
      const events = orderFail.pullEvents();

      await storage.save(orderFail);
      await storage.append(events);

      // Simulasi kegagalan runtime sebelum unit of work selesai
      throw new Error("SystemCrash: Database disk full!");
    });
  } catch (err: any) {
    console.log("\nSimulasi crash tertangkap:", err.message);
  }

  console.log("\nVerifikasi State Pasca Rollback (ORD-002 tidak boleh ada):");
  console.log("Orders:", Array.from(storage.ordersTable.entries()));
  console.log("Outbox Count:", storage.outboxTable.length);
}

bootstrap();
```

Jalankan program menggunakan `npx ts-node src/index.ts`.

---

### 13. Exercise

#### Level: Easy
- **Tugas**: Tambahkan validasi pada `Money` Value Object agar menolak pecahan uang sen negatif dan buat test case yang membuktikan objek tersebut *immutable* (tidak dapat dimodifikasi setelah diinstansiasi).

#### Level: Medium
- **Tugas**: Modifikasi `Order` Aggregate untuk mendukung transisi pembatalan (`cancel()`). 
- **Aturan Bisnis**: 
  - Pembatalan hanya valid jika status saat ini adalah `CONFIRMED`.
  - Pembatalan harus mencatat domain event `OrderCancelledEvent` yang berisi alasan pembatalan (`cancellationReason`).
  - Tuliskan unit test tanpa melibatkan *InMemoryStorage*.

#### Level: Hard
- **Tugas**: Bangun implementasi *Outbox Publisher Relay Worker* yang berjalan di thread terpisah (bisa menggunakan `setInterval` atau worker thread). 
- **Persyaratan**:
  - Relay worker mengambil batch outbox maksimal 10 event berstatus belum dipublikasikan.
  - Mempublikasikannya ke mock broker yang memiliki tingkat kegagalan jaringan 30%.
  - Menerapkan *exponential backoff* dan mencatat *retry count* pada setiap record outbox jika terjadi error transmisi.

---

### 14. Challenge

#### Skenario: Multi-Region Eventual Consistency Inventory Reservation System
Anda memimpin arsitektur platform flash-sale global. Sistem mengalami konkurensi ekstrem dengan stok barang terbatas (100 unit konsol PlayStation 5 diperebutkan oleh 50.000 user dalam 3 detik). 

**Kondisi dan Batasan Sistem**:
1. Basis data di-deploy secara *multi-region active-active* (Singapore dan Tokyo).
2. Latensi sinkronisasi antar region adalah ~65ms.
3. Anda **dilarang** menggunakan *Distributed Locking* (seperti Redlock) karena *network partition* antar region dapat memblokir thread pemrosesan transaksi melebihi SLO batas latensi (P99 < 200ms).
4. Penjualan berlebih (*overselling*) adalah kerugian finansial absolut (denda kepatuhan $100.000 per unit minus).

**Pertanyaan Arsitektural untuk Dijawab & Dirancang**:
- Bagaimana Anda memodelkan *Inventory Aggregate Root* dan batas invariansinya untuk menghindari race condition lintas wilayah?
- Bagaimana Anda memanfaatkan *Pessimistic Locking*, *Optimistic Concurrency Control (OCC)*, atau *Token-Bucket Partitioning* dalam desain Hexagonal Ports & Adapters Anda?
- Gambarkan diagram alur data lengkap dari saat pesanan masuk di region Tokyo, konsumsi stok, hingga resolusi konflik data jika dua region memproses reservasi unit terakhir secara bersamaan.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. **Apa perbedaan mendasar antara *Domain Entity* dan *Value Object*?**
   - *Jawaban*: Entity memiliki identitas unik yang bertahan sepanjang siklus hidupnya (dua entity dengan atribut sama tetap berbeda jika ID-nya berbeda). Value Object tidak memiliki identitas konseptual; kesetaraannya dinilai murni dari kesamaan nilai atributnya (*structural equality*) dan bersifat *immutable*.

2. **Mengapa Domain Model murni dilarang mengimpor library framework (seperti Express, NestJS, atau TypeORM)?**
   - *Jawaban*: Ketergantungan ke framework membuat core business logic terikat pada lifecycle dan breaking changes vendor eksternal, merusak prinsip *Separation of Concerns*, dan mempersulit pengujian independen.

3. **Di layer manakah interface *Driven Port* didefinisikan dalam Hexagonal Architecture?**
   - *Jawaban*: Didefinisikan di dalam Application/Domain layer (Inside Hexagon), tetapi implementasinya diletakkan di Infrastructure layer (Outside Hexagon).

4. **Apa yang dimaksud dengan Aggregate Root dalam konteks transactional consistency?**
   - *Jawaban*: Aggregate Root adalah satu-satunya gerbang entitas luar untuk mengakses atau memodifikasi objek-objek di dalam aggregate boundaries, memastikan seluruh aturan bisnis (*invariants*) selalu valid dalam satu transaksi tunggal.

5. **Apa masalah utama dari pola *Anemic Domain Model*?**
   - *Jawaban*: Anemic Domain Model hanya berisi data getter/setter tanpa business logic. Logika bisnis tercecer di berbagai Service Layer, menyebabkan duplikasi aturan validasi dan risiko manipulasi state yang tidak sah secara bisnis.

#### Intermediate (5 Soal)
1. **Mengapa pola *Dual-Write* (menyimpan ke DB, lalu mengirim ke Kafka dalam application code) dianggap anti-pattern pada distributed systems?**
   - *Jawaban*: Operasi tersebut tidak atomik. Jika aplikasi crash atau jaringan terputus tepat setelah database commit, pesan Kafka tidak akan pernah terkirim, mengakibatkan inkonsistensi data antar-layanan yang tidak dapat dipulihkan secara otomatis.

2. **Bagaimana Transactional Outbox Pattern mengatasi kegagalan pengiriman pesan ke message broker?**
   - *Jawaban*: Dengan menyimpan event ke tabel database relasional (`outbox`) di dalam transaksi ACID yang sama dengan mutasi entity. Proses terpisah (poller atau CDC) kemudian membacanya dan mengirimkannya ke message broker secara andal dengan retry mechanism.

3. **Apa perbedaan antara Driving Adapter dan Driven Adapter? Berikan contohnya.**
   - *Jawaban*: Driving Adapter adalah inisiator yang memicu sistem (misal: REST Controller, CLI command). Driven Adapter diinisiasi oleh sistem internal untuk mengakses kapabilitas luar (misal: database adapter, email gateway client, Kafka producer).

4. **Kapan Anda harus memilih Optimistic Concurrency Control (OCC) dibandingkan Pessimistic Locking pada Aggregate?**
   - *Jawaban*: OCC dipilih jika probabilitas benturan modifikasi rendah (*low contention*) untuk memaksimalkan throughput. Pessimistic Locking dipilih ketika tingkat kontensi sangat tinggi (*high contention*) di mana rollback OCC berulang akan memboroskan sumber daya komputasi secara signifikan.

5. **Bagaimana cara mencegah memory leak atau unbounded query saat memuat Aggregate yang memiliki ribuan child items dari database?**
   - *Jawaban*: Desain aggregate yang salah jika berisi ribuan child items. Desain ulang Aggregate boundary agar lebih kecil (*small aggregate pattern*), dan representasikan relasi skala besar melalui query terpisah atau referensikan Aggregate lain hanya lewat ID.

#### Production Scenarios (3 Soal Kasus)

**Skenario 1**:
Aplikasi checkout Anda sering menghasilkan event outbox ganda karena *network glitch* antara background outbox poller dan Kafka broker. Konsumen downstream di sistem *Billing* memotong saldo pengguna dua kali lipat.
- **Solusi Rekayasa**:
  1. Di sisi Producer: Outbox processor harus menyertakan *idempotency key* unik (berasal dari `outbox_id` atau `event_id`).
  2. Di sisi Consumer: Billing Service wajib mengimplementasikan *Idempotent Consumer Pattern*. Setiap event yang masuk dicek terlebih dahulu ke tabel deduplikasi (`processed_events`) dalam transaksi pembayaran. Jika ID sudah ada, proses dilewati dan event langsung di-ACK.

**Skenario 2**:
Tabel `outbox_events` di sistem PostgreSQL Anda telah mencapai 80 juta baris. Query background poller `SELECT * FROM outbox_events WHERE published = false ORDER BY created_at ASC LIMIT 100` mulai menyebabkan IO spike parah dan mengunci tabel (*table lock contention*).
- **Solusi Rekayasa**:
  1. Hentikan Polling berbasis query SELECT. Ganti mekanisme ke **Change Data Capture (CDC)** non-intrusif menggunakan Debezium yang membaca binary replication log (PostgreSQL WAL) secara streaming.
  2. Jika harus tetap polling, gunakan *Partial Index*: `CREATE INDEX idx_unpub ON outbox_events(created_at) WHERE published = false;` dan implementasikan *SKIP LOCKED* (`SELECT ... FOR UPDATE SKIP LOCKED`) agar worker paralel tidak berebut baris data yang sama.
  3. Terapkan strategi archival/purging terjadwal untuk menghapus baris dengan `published = true` yang berumur lebih dari 7 hari.

**Skenario 3**:
Saat melakukan load test sistem perbankan core, use-case `TransferFunds` mengalami error deadlock PostgreSQL secara berulang ketika dua akun saling mengirimkan uang pada milidetik yang sama (Akun A transfer ke Akun B, bersamaan dengan Akun B transfer ke Akun A).
- **Solusi Rekayasa**:
  1. Penyebab: Kedua transaksi melakukan pessimistic lock (`SELECT FOR UPDATE`) pada resource dengan urutan terbalik: TX1 mengunci A lalu menunggu B; TX2 mengunci B lalu menunggu A.
  2. Resolusi Arsitektur: Terapkan strategi **Deterministic Lock Acquisition Ordering**. Sebelum mengeksekusi lock di database adapter, urutkan ID akun secara leksikografis/alfabetis:
     ```typescript
     const [firstLockId, secondLockId] = [fromId, toId].sort();
     await repo.lockAccount(firstLockId);
     await repo.lockAccount(secondLockId);
     ```
  3. Dengan urutan penguncian yang identik di setiap transaksi, siklus tunggu lingkaran (*circular wait condition*) tereliminasi sepenuhnya, sehingga deadlock mustahil terjadi.

---

### 16. Summary

1. **Hexagonal Architecture** membalikkan dependensi tradisional: Domain Core menjadi pusat yang sepenuhnya independen dari teknologi eksternal, dikelilingi oleh Ports (kontrak abstraksi) dan Adapters (implementasi teknologi konkret).
2. **Aggregate Root** bertindak sebagai perisai konsistensi transaksional. Perubahan internal state harus melalui aggregate root untuk menjamin seluruh *business invariants* terpenuhi setiap saat.
3. **Pemisahan Model & Dual-Write Mitigation**: Mengubah database dan mengirim pesan broker dalam satu blok logika membutuhkan **Transactional Outbox Pattern** untuk mengeliminasi silent data loss dan desinkronisasi sistem terdistribusi.
4. **Resiliensi Tingkat Produksi** mensyaratkan desain aggregate kecil, semantik *at-least-once delivery*, penanganan idempotensi pada downstream consumer, serta eliminasi deadlock melalui pendekatan deterministik. Arsitektur yang kokoh dibangun atas mitigasi terhadap skenario kegagalan, bukan hanya skenario ideal (*happy path*).