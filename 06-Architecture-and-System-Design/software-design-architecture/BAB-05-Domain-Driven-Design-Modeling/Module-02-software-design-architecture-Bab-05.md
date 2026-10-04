# BAB 05: Domain-Driven Design Modeling
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang Batasan Agregat (*Aggregate Boundaries*) Presisi Tinggi:** Mengisolasi *invariants* bisnis dalam satu batas konsistensi transaksional ACID tanpa memicu *database lock contention*.
- **Mengimplementasikan Pola Transaksional Lanjutan:** Mengintegrasikan *Domain Events* dengan *Transactional Outbox Pattern* dan *Optimistic Concurrency Control* (OCC) untuk menjamin konsistensi *at-least-once delivery* tanpa *distributed two-phase commit* (2PC).
- **Mencegah Kebocoran Lapisan (*Decoupled Domain Layer*):** Memisahkan secara mutlak representasi *Domain Entity* murni dari *Data Mapper/ORM Persistence Model* menggunakan prinsip *Hexagonal Architecture*.
- **Mengatasi Masalah Konkurensi Skala Enterprise:** Menangani *write-skew*, *lost updates*, dan *deadlock* pada domain kompleks menggunakan *versioning* dan *aggregate splitting*.
- **Mengevaluasi & Merefaktor Desain Domain:** Mengaudit *anti-pattern* seperti *Anemic Domain Model*, *God Aggregate*, dan kebocoran repositori ke dalam *Aggregate Root*.

---

### 2. Prerequisite

Peserta wajib menguasai:
1. **Konsep Fondasi DDD:** Entitas (*Entity*), Objek Nilai (*Value Object*), Layanan Domain (*Domain Service*), dan *Aggregate Root* dasar.
2. **Arsitektur Perangkat Lunak:** Pemahaman solid terhadap *Hexagonal / Ports and Adapters / Clean Architecture*.
3. **Mekanisme Database:** Transaksi ACID (*Atomicity, Consistency, Isolation, Durability*), level isolasi transaksi SQL (*Read Committed*, *Repeatable Read*, *Serializable*), dan *row-level locking* (`SELECT ... FOR UPDATE`).
4. **Sistem Terdistribusi:** Karakteristik *Event-Driven Architecture*, broker pesan (Apache Kafka atau RabbitMQ), serta semantik pengiriman pesan (*At-least-once, Idempotency*).
5. **Bahasa Pemrograman:** Kemampuan membaca dan menulis kode TypeScript/Node.js modern dengan *strict type system*.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Anatomi Aggregate Root & Batasan Invariant

*Aggregate* bukan sekadar pengelompokan objek atau tabel database demi kenyamanan struktural; **Aggregate adalah kluster tertutup dari domain objects yang diperlakukan sebagai satu kesatuan tunggal untuk perubahan data (Consistency Boundary)**.

```
                    AGGREGATE CONSISTENCY BOUNDARY
   +-------------------------------------------------------------+
   |  [Aggregate Root: Order] (Version: 4)                       |
   |   - OrderID (Identity)                                      |
   |   - CustomerID (Reference by Identity Only)                 |
   |   - OrderStatus: PENDING_PAYMENT                            |
   |   - Invariant: Max total value <= $50,000 per single order  |
   |                                                             |
   |   +-----------------------+     +-----------------------+   |
   |   | Entity: OrderLine     |     | Value Object: Money   |   |
   |   |  - LineID             |     |  - Amount: 1500.00    |   |
   |   |  - ProductID (Ref)    |     |  - Currency: USD      |   |
   |   |  - Quantity: 2        |     +-----------------------+   |
   |   +-----------------------+                                 |
   |                                                             |
   |   Uncommitted Domain Events:                                |
   |     * OrderItemAddedDomainEvent                             |
   +-------------------------------------------------------------+
```

##### Aturan Utama Perancangan Agregat Tingkat Produksi:
1. **Akses Hanya Melalui Root:** Objek di luar *Aggregate Boundary* dilarang keras mereferensikan atau memanipulasi *Internal Entity* secara langsung. Semua mutasi harus memanggil metode publik pada *Aggregate Root*.
2. **Referensi Antar-Agregat Hanya Berbasis Identitas:** Agregat `Order` dilarang memegang referensi memori langsung ke agregat `Customer` (`order.customer.name` adalah pelanggaran batas). Gunakan `CustomerID` (*Identity Reference*). Ini memutus *cascading lock* di tingkat database.
3. **Satu Transaksi = Satu Mutasi Agregat:** Dalam satu transaksi database lokal ACID, modifikasi data hanya boleh dieksekusi pada **satu** *Aggregate Root instance*. Perubahan pada agregat lain wajib didistribusikan melalui *Eventual Consistency* menggunakan *Domain Events*.
4. **Invariants Wajib Bersifat Sinkron:** *Business Invariant* (aturan bisnis yang harus selalu benar setiap saat) diisolasi di dalam batas Agregat dan divalidasi seketika (*immediate consistency*). Jika validasi membutuhkan data agregat lain secara sinkron, desain batasan agregat Anda kemungkinan salah, atau aturan tersebut sebenarnya toleran terhadap konsistensi tertunda (*eventual consistency*).

#### 3.2 Transactional Outbox Pattern & Siklus Hidup Domain Event

Menyimpan data mutasi bisnis ke database dan mempublikasikan event ke Message Broker dalam dua operasi terpisah menghasilkan risiko fatal: kegagalan parsial (*dual-write problem*). Solusi standar industri adalah **Transactional Outbox Pattern**.

```
[Application Layer]
       │
       ▼
 1. Mutate Aggregate State
 2. aggregate.PullDomainEvents()
 3. BEGIN TRANSACTION (SQL)
    ├── INSERT/UPDATE Aggregate Data (Table: orders)
    └── INSERT Event Payloads (Table: outbox_messages)
    COMMIT TRANSACTION
       │
[Debezium CDC Engine OR Polling Worker]
       │
       ▼
 4. Read unpublished messages from 'outbox_messages'
 5. Publish payload to Kafka/RabbitMQ Topic
 6. Mark message as PUBLISHED / DELETE row
```

---

### 4. Why & What

| Dimensi | Anemic / Naive CRUD Architecture | Advanced Tactical DDD (Production Grade) |
| :--- | :--- | :--- |
| **Penyimpanan State** | Langsung ke ORM Entity yang diekspos ke controller/service. | Objek Domain murni, dipetakan ke Persistence Model secara eksplisit via Data Mapper. |
| **Integritas Bisnis (Invariants)** | Tersebar di Controller, Service, Database Trigger, atau Frontend. | Terenkapsulasi mutlak di dalam *Aggregate Root* dan *Value Objects*. |
| **Konkurensi** | *Pessimistic table/row locking* atau *Last-Write-Wins* (kehilangan data silently). | *Optimistic Concurrency Control* (OCC) menggunakan field `version` / ETag. |
| **Komunikasi Antar Modul** | Pemanggilan synchronous RPC / Service-to-Service DB joins. | *Domain Events* terisolasi, ditransmisikan via *Outbox Pattern*. |
| **Dampak Perubahan Skema** | Mengubah kolom database merusak logika bisnis. | Perubahan skema database terisolasi di repositori / persistence schema. |

---

### 5. How (Workflow Detail)

Alur eksekusi mutasi domain pada aplikasi skala produksi:

```
[HTTP/gRPC Controller]
          │
          │ 1. DTO Request
          ▼
[Application Service / Command Handler]
          │
          │ 2. Command (e.g., AddItemCommand)
          ▼
[Order Repository Interface]
          │
          │ 3. LoadAggregateById(orderId)
          ▼
[Database (PostgreSQL)] ────(Raw Rows)────► [Persistence Data Mapper]
                                                      │
                                                      │ 4. Reconstruct pure Order Aggregate
                                                      ▼
[Order Aggregate Root] ◄────────────────────── [Application Service]
          │
          │ 5. order.AddItem(productId, price, quantity)
          │    - Invariant Checks (Total limit, item limits)
          │    - State Mutation
          │    - Record Domain Event
          │
          ▼
[Application Service]
          │ 6. Extract Recorded Domain Events: aggregate.PullDomainEvents()
          ▼
[Unit of Work / Transaction Scope]
   BEGIN TX
     ├── 7. orderRepository.Save(order) [UPDATE orders SET ..., version = version + 1 WHERE id = ... AND version = 3]
     │      (Throws OptimisticConcurrencyLockError if rows_affected == 0)
     └── 8. outboxRepository.Append(domainEvents) [INSERT INTO outbox_messages ...]
   COMMIT TX
          │
          ▼
[HTTP Response 200 OK / 202 Accepted]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Notaris dan Rekening Bersama (Escrow)
Bayangkan Agregat sebagai map berkas legal yang disegel oleh Notaris (*Aggregate Root*). Anda tidak bisa mengambil selembar kertas (*Internal Entity: OrderLine*) dari dalam map dan mencoret nominal harganya secara sepihak di luar kantor notaris. 

Setiap modifikasi harus diajukan ke Notaris. Notaris mengecek seluruh dokumen pendukung, aturan hukum, dan batas wewenang (*Invariant Checks*). Setelah divalidasi, Notaris mencatat transaksi di buku besar rahasia internal kantor (*Outbox Table*), lalu membubuhkan stempel resmi versi baru. Panitera (*CDC Worker*) secara berkala melihat buku besar tersebut dan mengirimkan salinan pengumuman ke dinas luar (*Message Broker*).

```
   +──────────────────────────────────────────────────────────+
   |                   PERSISTENCE BOUNDARY                   |
   |                                                          |
   |  TABLE: orders                                           |
   |  +----+---------+-------------+---------+-------------+  |
   |  | id | cust_id | total_cents | status  | version (OCC) |
   |  +----+---------+-------------+---------+-------------+  |
   |  | 91 |  C-101  |    150000   | CREATED |      4      |  |
   |  +----+---------+-------------+---------+-------------+  |
   |                                                          |
   |  TABLE: order_items                                      |
   |  +----+----------+------------+-----+-------------+      |
   |  | id | order_id | product_id | qty | unit_cents  |      |
   |  +----+----------+------------+-----+-------------+      |
   |  | 01 |    91    |   PROD-A   |  2  |    75000    |      |
   |  +----+----------+------------+-----+-------------+      |
   |                                                          |
   |  TABLE: outbox_messages                                  |
   |  +-----+------------------+-----------------------+      |
   |  | id  | event_type       | payload_json          |      |
   |  +-----+------------------+-----------------------+      |
   |  | E-1 | OrderItemAdded   | {"orderId":91, ...}   |      |
   |  +-----+------------------+-----------------------+      |
   +──────────────────────────────────────────────────────────+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Pure Value Object dengan Validasi Invariant

Value Object harus *immutable*, memiliki kesetaraan struktural (*structural equality*), dan tidak dapat diciptakan dalam *state* yang tidak valid (*self-validating*).

```typescript
// Money.ts
export class Money {
  private readonly _amountInCents: bigint;
  private readonly _currency: string;

  private constructor(amountInCents: bigint, currency: string) {
    this._amountInCents = amountInCents;
    this._currency = currency;
    Object.freeze(this);
  }

  public static create(amount: number, currency: string): Money {
    if (!Number.isFinite(amount)) {
      throw new Error("Amount must be a finite number.");
    }
    if (amount < 0) {
      throw new Error("Negative monetary amounts are not permitted.");
    }
    const cleanCurrency = currency.trim().toUpperCase();
    if (!/^[A-Z]{3}$/.test(cleanCurrency)) {
      throw new Error("Currency must follow ISO-4217 format (e.g. USD, IDR).");
    }

    const amountInCents = BigInt(Math.round(amount * 100));
    return new Money(amountInCents, cleanCurrency);
  }

  public static fromCents(cents: bigint, currency: string): Money {
    if (cents < 0n) throw new Error("Cents cannot be negative.");
    return new Money(cents, currency.trim().toUpperCase());
  }

  public get amount(): number {
    return Number(this._amountInCents) / 100;
  }

  public get cents(): bigint {
    return this._amountInCents;
  }

  public get currency(): string {
    return this._currency;
  }

  public add(other: Money): Money {
    this.assertSameCurrency(other);
    return new Money(this._amountInCents + other._amountInCents, this._currency);
  }

  public multiply(multiplier: number): Money {
    if (multiplier < 0) throw new Error("Multiplier cannot be negative.");
    const factor = BigInt(Math.round(multiplier * 10000));
    const calculatedCents = (this._amountInCents * factor) / 10000n;
    return new Money(calculatedCents, this._currency);
  }

  public equals(other: Money): boolean {
    return this._amountInCents === other._amountInCents && this._currency === other._currency;
  }

  private assertSameCurrency(other: Money): void {
    if (this._currency !== other._currency) {
      throw new Error(`Currency mismatch: cannot operate on ${this._currency} and ${other._currency}`);
    }
  }
}
```

#### 7.2 Practical Example: Enterprise-Grade Aggregate Root, OCC & Transactional Outbox

Berikut adalah implementasi agregat produksi tanpa dependensi pada *framework* eksternal untuk modul domain.

##### Step 1: Base Building Blocks

```typescript
// SharedKernel.ts
export interface DomainEvent {
  readonly eventId: string;
  readonly occurredOn: Date;
  readonly eventType: string;
  readonly aggregateId: string;
  readonly payload: Record<string, unknown>;
}

export abstract class AggregateRoot<TId> {
  private _domainEvents: DomainEvent[] = [];
  protected abstract _id: TId;
  private _version: number = 0;

  public get id(): TId {
    return this._id;
  }

  public get version(): number {
    return this._version;
  }

  // Restore existing aggregate from database
  public setVersion(version: number): void {
    this._version = version;
  }

  protected addDomainEvent(event: DomainEvent): void {
    this._domainEvents.push(event);
  }

  public pullDomainEvents(): DomainEvent[] {
    const events = [...this._domainEvents];
    this._domainEvents = [];
    return events;
  }
}
```

##### Step 2: Order Aggregate Root & Domain Logic

```typescript
// OrderAggregate.ts
import { Money } from "./Money";
import { AggregateRoot, DomainEvent } from "./SharedKernel";
import { randomUUID } from "crypto";

export enum OrderStatus {
  DRAFT = "DRAFT",
  CONFIRMED = "CONFIRMED",
  CANCELLED = "CANCELLED"
}

export class OrderLine {
  constructor(
    public readonly lineId: string,
    public readonly productId: string,
    public readonly unitPrice: Money,
    private _quantity: number
  ) {
    if (_quantity <= 0 || !Number.isInteger(_quantity)) {
      throw new Error("Quantity must be a positive integer.");
    }
  }

  public get quantity(): number {
    return this._quantity;
  }

  public increaseQuantity(amount: number): void {
    if (amount <= 0) throw new Error("Increment amount must be positive.");
    this._quantity += amount;
  }

  public get subtotal(): Money {
    return this.unitPrice.multiply(this._quantity);
  }
}

export class OrderItemAddedEvent implements DomainEvent {
  public readonly eventId = randomUUID();
  public readonly occurredOn = new Date();
  public readonly eventType = "Order.ItemAdded";

  constructor(
    public readonly aggregateId: string,
    public readonly payload: {
      productId: string;
      quantity: number;
      unitPriceCents: bigint;
      currency: string;
      totalOrderAmountCents: bigint;
    }
  ) {}
}

export class Order extends AggregateRoot<string> {
  protected _id: string;
  private _customerId: string;
  private _status: OrderStatus;
  private _lines: Map<string, OrderLine>;
  private _currency: string;

  // Invariant constraints
  private static readonly MAX_ORDER_LIMIT_CENTS = 5000000n; // $50,000.00
  private static readonly MAX_LINE_ITEMS = 50;

  private constructor(id: string, customerId: string, currency: string) {
    super();
    this._id = id;
    this._customerId = customerId;
    this._currency = currency;
    this._status = OrderStatus.DRAFT;
    this._lines = new Map();
  }

  public static create(id: string, customerId: string, currency: string): Order {
    if (!id || !customerId) throw new Error("ID and CustomerID cannot be empty.");
    return new Order(id, customerId, currency);
  }

  public static reconstitute(
    id: string,
    customerId: string,
    status: OrderStatus,
    currency: string,
    version: number,
    lines: OrderLine[]
  ): Order {
    const order = new Order(id, customerId, currency);
    order.setVersion(version);
    order._status = status;
    for (const line of lines) {
      order._lines.set(line.productId, line);
    }
    return order;
  }

  public addLineItem(productId: string, unitPrice: Money, quantity: number): void {
    // 1. Invariant: Status check
    if (this._status !== OrderStatus.DRAFT) {
      throw new Error(`Cannot modify order in ${this._status} status.`);
    }

    // 2. Invariant: Currency compatibility
    if (unitPrice.currency !== this._currency) {
      throw new Error(`Currency mismatch. Order currency is ${this._currency}`);
    }

    // 3. Invariant: Max unique items count check
    if (!this._lines.has(productId) && this._lines.size >= Order.MAX_LINE_ITEMS) {
      throw new Error(`Cannot exceed max line items limit (${Order.MAX_LINE_ITEMS}).`);
    }

    // Mutasi state internal
    const existing = this._lines.get(productId);
    if (existing) {
      existing.increaseQuantity(quantity);
    } else {
      this._lines.set(productId, new OrderLine(randomUUID(), productId, unitPrice, quantity));
    }

    // 4. Invariant: Maximum Total Order Value
    const total = this.calculateTotal();
    if (total.cents > Order.MAX_ORDER_LIMIT_CENTS) {
      // Rollback mutasi jika invariant dilanggar
      if (existing) {
        existing.increaseQuantity(-quantity);
      } else {
        this._lines.delete(productId);
      }
      throw new Error(`Order limit exceeded. Maximum allowed is $50,000.00.`);
    }

    // 5. Emit Domain Event
    this.addDomainEvent(
      new OrderItemAddedEvent(this._id, {
        productId,
        quantity,
        unitPriceCents: unitPrice.cents,
        currency: this._currency,
        totalOrderAmountCents: total.cents
      })
    );
  }

  public calculateTotal(): Money {
    let totalCents = 0n;
    for (const line of this._lines.values()) {
      totalCents += line.subtotal.cents;
    }
    return Money.fromCents(totalCents, this._currency);
  }

  public get lines(): readonly OrderLine[] {
    return Array.from(this._lines.values());
  }

  public get status(): OrderStatus {
    return this._status;
  }

  public get customerId(): string {
    return this._customerId;
  }
}
```

##### Step 3: Application Service & Transactional Outbox Unit of Work

```typescript
// AddItemToOrderUseCase.ts
import { Order, OrderStatus } from "./OrderAggregate";
import { Money } from "./Money";
import { DomainEvent } from "./SharedKernel";

export interface DatabaseClient {
  query(sql: string, params: unknown[]): Promise<{ rowCount: number; rows: any[] }>;
}

export interface IOrderRepository {
  findById(id: string): Promise<Order | null>;
  saveWithOutbox(order: Order, events: DomainEvent[]): Promise<void>;
}

export class PostgresOrderRepository implements IOrderRepository {
  constructor(private readonly db: DatabaseClient) {}

  async findById(id: string): Promise<Order | null> {
    const orderRes = await this.db.query(
      `SELECT id, customer_id, status, currency, version FROM orders WHERE id = $1`,
      [id]
    );
    if (orderRes.rowCount === 0) return null;

    const row = orderRes.rows[0];
    const itemsRes = await this.db.query(
      `SELECT id, product_id, unit_cents, currency, quantity FROM order_lines WHERE order_id = $1`,
      [id]
    );

    const lines = itemsRes.rows.map(
      (r) => new OrderLine(r.id, r.product_id, Money.fromCents(BigInt(r.unit_cents), r.currency), r.quantity)
    );

    return Order.reconstitute(row.id, row.customer_id, row.status as OrderStatus, row.currency, row.version, lines);
  }

  async saveWithOutbox(order: Order, events: DomainEvent[]): Promise<void> {
    const currentVersion = order.version;
    const nextVersion = currentVersion + 1;

    // Begin Unit of Work Simulation
    await this.db.query("BEGIN", []);
    try {
      // Optimistic Concurrency Control Check on Orders table
      const updateResult = await this.db.query(
        `UPDATE orders 
         SET status = $1, version = $2, updated_at = NOW() 
         WHERE id = $3 AND version = $4`,
        [order.status, nextVersion, order.id, currentVersion]
      );

      if (updateResult.rowCount === 0) {
        throw new Error(
          `OCC Conflict: Order [${order.id}] was modified by another concurrent transaction.`
        );
      }

      // Upsert lines
      for (const line of order.lines) {
        await this.db.query(
          `INSERT INTO order_lines (id, order_id, product_id, unit_cents, currency, quantity)
           VALUES ($1, $2, $3, $4, $5, $6)
           ON CONFLICT (id) DO UPDATE 
           SET quantity = EXCLUDED.quantity`,
          [line.lineId, order.id, line.productId, line.unitPrice.cents.toString(), line.unitPrice.currency, line.quantity]
        );
      }

      // Append events to Outbox table within the SAME transaction
      for (const event of events) {
        await this.db.query(
          `INSERT INTO outbox_messages (id, aggregate_id, event_type, payload, status, created_at)
           VALUES ($1, $2, $3, $4, 'PENDING', $5)`,
          [event.eventId, event.aggregateId, event.eventType, JSON.stringify(event.payload), event.occurredOn]
        );
      }

      await this.db.query("COMMIT", []);
      order.setVersion(nextVersion);
    } catch (error) {
      await this.db.query("ROLLBACK", []);
      throw error;
    }
  }
}

export class AddItemToOrderService {
  constructor(private readonly orderRepo: IOrderRepository) {}

  public async execute(command: {
    orderId: string;
    productId: string;
    unitPrice: number;
    currency: string;
    quantity: number;
  }): Promise<void> {
    const order = await this.orderRepo.findById(command.orderId);
    if (!order) {
      throw new Error(`Order with ID ${command.orderId} not found.`);
    }

    const price = Money.create(command.unitPrice, command.currency);
    
    // Mutasi murni di level Domain
    order.addLineItem(command.productId, price, command.quantity);

    // Dapatkan domain events
    const domainEvents = order.pullDomainEvents();

    // Persist secara atomic (Domain State + Outbox) dengan OCC
    await this.orderRepo.saveWithOutbox(order, domainEvents);
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem:
Sistem Digital Wallet & Core Ledger di platform FinTech dengan volume transaksi rata-rata **8.000 transaksi/detik (TPS)** dan puncak lonjakan hingga **35.000 TPS** saat *flash sale*.

#### Masalah Utama Arsitektur:
Awalnya, tim merekayasa Agregat Dompet Tunggal (`WalletAggregate`):
```typescript
// DESAIN AWAL YANG GAGAL
class WalletAggregate {
  private walletId: string;
  private balance: Money;
  private ledgerEntries: LedgerEntry[];
  
  transferTo(destination: WalletAggregate, amount: Money) { ... }
}
```
Ketika transaksi tinggi, eksekusi pemindahan dana mentransfer balance antara dua dompet dalam satu transaksi ACID database. Terjadi **Database Row Lock Contention masif** dan *deadlock*:
- User A mengirim uang ke User B. Transaksi 1 mengunci Row A lalu mengunci Row B.
- Secara bersamaan, User B mengirim uang ke User A. Transaksi 2 mengunci Row B lalu mengunci Row A.
- Hasil: Deadlock (`SQLSTATE 40P01`), p99 *latency* melonjak hingga 14 detik, dan 38% request mengalami HTTP 500.

```
       DEADLOCK CYCLE
Transaction 1: Lock(Wallet A) ──(wants)──► Lock(Wallet B)
                      ▲                         │
                      │                         │
                  (holding)                 (holding)
                      │                         ▼
Transaction 2: Lock(Wallet A) ◄──(wants)── Lock(Wallet B)
```

#### Solusi Tingkat Lanjut (DDD Refactoring):
1. **Pecah Batasan Agregat Menggunakan Teknik Double-Entry Ledger:**
   Hapus mutasi langsung pada `balance` yang saling bergantung. Agregat dipecah menjadi:
   - `LedgerAccount` (Hanya identitas & status akun: ACTIVE, SUSPENDED).
   - `PostingTransaction` (Agregat independen yang merekam dua atau lebih *Ledger Entries* yang seimbang: Debit dan Kredit).
2. **Pola Immutability (Append-Only):**
   `PostingTransaction` tidak pernah meng-update row yang ada. Setiap transfer dana adalah insert baru.
   - Database tidak pernah melakukan *exclusive update lock* pada row dompet yang sama untuk menghitung saldo. Saldo dihitung menggunakan *Read Projection* (CQRS) yang di-cache di Redis.
3. **Mekanisme Validasi Overdraft (Invariant):**
   Untuk mencegah penarikan melebihi saldo (*insufficient funds*) tanpa locking:
   - Akun diklasifikasikan ke dalam *Reservation Aggregates* berbasis *shard token* jika limit ketat dibutuhkan.
   - Pengecekan saldo dilakukan via *Optimistic Balance Check* pada snapshot akun read model, lalu verifikasi akhir didelegasikan ke *Saga Orchestrator* yang dapat meng-kompensasi (*reverse transaction*) jika hasil agregasi ledger menunjukkan anomali.

#### Hasil:
- *Lock wait timeout* turun dari 38% menjadi **0%**.
- p99 Latency turun drastis dari **14.200 ms** menjadi **34 ms**.
- Throughput transfer ledger meningkat 12x lipat tanpa membutuhkan infrastruktur database berukuran monster.

---

### 9. Trade-offs

```
                  CONSISTENCY vs PERFORMANCE SPECTRUM
                  
   [ACID / Large Aggregate]                     [BASE / Small Aggregate + Outbox]
   ◄────────────────────────────────────────────────────────────────────────────►
   - Strong Consistency                          - Eventual Consistency
   - Immediate Invariant Enforced                - Complex Orchestration (Sagas)
   - High Latency & Lock Contention              - Low Latency, Infinite Scale
   - Low Architectural Complexity                - High Architectural Complexity
```

| Parameter | Agregat Besar (Monolithic Aggregate) | Agregat Terpisah Presisi + Outbox (Rekomendasi) |
| :--- | :--- | :--- |
| **Performance** | Rendah. Terjadi *database contention* saat banyak proses mencoba mengubah sub-entitas yang sama. | Sangat Tinggi. Operasi tulis terisolasi pada id Agregat yang spesifik. |
| **Latency** | Bervariasi liar di beban tinggi akibat waktu tunggu penguncian (*lock queueing*). | Stabil dan terprediksi (*sub-50ms writes*). |
| **Scalability** | Mentok pada batasan penskalaan vertikal database relasional. | Sangat mudah diskalakan horizontal melalui sharding berbasis *Aggregate ID*. |
| **Operational Cost** | Murah dalam kompleksitas kode, mahal pada biaya *hardware* database server. | Lebih tinggi pada infrastruktur (membutuhkan Debezium/Kafka/Redis worker). |
| **Cognitive Load** | Tim mudah memprogram (gaya prosedural CRUD), rawan bug tersembunyi. | Membutuhkan kedewasaan tim dalam memahami konsistensi asinkron (*asynchronous invariants*). |

---

### 10. Common Mistakes & Troubleshooting

#### Mistake 1: Memory & Data Leak Melalui Getter Koleksi Internal
*Anti-pattern:* Mengembalikan referensi langsung ke array/map internal agregat.
```typescript
// BUGGY: Objek luar bisa bypass aturan bisnis agregat
public get lines(): OrderLine[] {
  return this._lines; // Array mutable asli terekspos!
}
// Client code bisa: order.lines.push(new OrderLine(...)) tanpa validasi Invariant!
```
*Fix:* Kembalikan *immutable copy* atau *read-only projection*.
```typescript
public get lines(): readonly OrderLine[] {
  return Object.freeze([...this._lines.values()]);
}
```

#### Mistake 2: Menyuntikkan Dependency Repositori ke dalam Entity / Aggregate
*Anti-pattern:* Memasukkan `UserRepository` ke dalam method `Order.confirm(userRepo)`.
*Mengapa Salah:* Agregat menjadi tidak *pure*, sulit diuji dalam *unit test*, dan memicu *hidden network I/O* di dalam logika domain.
*Fix:* Ambil data yang dibutuhkan di *Application Layer*, lalu berikan hasil evaluasinya ke agregat sebagai nilai murni (*primitive/value object*).

#### Mistake 3: Gagal Menangani Optimistic Lock Exception
*Gejala Produksi:* Muncul error HTTP 500 secara sporadis ketika dua user mengedit agregat yang sama dalam waktu berdekatan.
*Troubleshooting:*
1. Pastikan Application Layer menangkap error OCC (`OptimisticConcurrencyLockError`).
2. Terapkan strategi *Exponential Backoff with Jitter Retry*:
```typescript
async function executeWithRetry<T>(fn: () => Promise<T>, maxRetries = 3): Promise<T> {
  let attempt = 0;
  while (attempt < maxRetries) {
    try {
      return await fn();
    } catch (err: any) {
      if (err.name === 'OptimisticConcurrencyLockError' && attempt < maxRetries - 1) {
        attempt++;
        const jitter = Math.random() * 100;
        const delay = Math.pow(2, attempt) * 50 + jitter;
        await new Promise((res) => setTimeout(res, delay));
        continue;
      }
      throw err;
    }
  }
  throw new Error("Max retries exceeded");
}
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Batasan Agregat Kecil:** Desain agregat sekecil mungkin yang mampu menjaga *invariants*. Entitas internal hanya dibuat jika memiliki identitas independen dalam siklus hidup agregat tersebut.
- [ ] **ID Agregat yang Kuat (*Strongly Typed IDs*):** Hindari menggunakan raw `string` untuk ID. Gunakan `OrderId`, `CustomerId` sebagai Value Objects untuk menghindari kesalahan parameter tertukar.
- [ ] **Optimistic Locking Aktif:** Seluruh tabel database agregat wajib memiliki kolom `version INT DEFAULT 0`. Klausa `UPDATE` wajib menyertakan `WHERE id = $id AND version = $version`.
- [ ] **Zero Database Dependencies di Domain Layer:** Pastikan package `domain` tidak mengimpor modul PostgreSQL, TypeORM, Prisma, Mongoose, atau Kafka. Domain harus 100% *Vanilla Language Code*.
- [ ] **Penyimpanan Outbox Terpadu (*Atomic Outbox*):** Mutasi tabel domain dan tabel `outbox_messages` wajib berada dalam blok transaksi database lokal yang persis sama.
- [ ] **Idempotent Consumers:** Konsumen event outbox wajib mengimplementasikan tabel/cache idempotensi untuk menangani skenario *at-least-once delivery duplicates*.

---

### 12. Hands-on Practice

Buat scaffold proyek untuk menguji implementasi aggregate, OCC, dan outbox pattern secara langsung.

#### Struktur Direktori
```
hands-on/m02/
├── package.json
├── tsconfig.json
├── src/
│   ├── domain/
│   │   ├── Money.ts
│   │   ├── OrderAggregate.ts
│   │   └── SharedKernel.ts
│   ├── infrastructure/
│   │   └── InMemoryDatabase.ts
│   └── application/
│       └── OrderService.ts
└── test/
    └── OrderConcurrency.test.ts
```

#### Langkah Eksekusi

1. **Inisialisasi Project:**
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
npm init -y
npm install typescript @types/node ts-node --save-dev
npx tsc --init
```

2. **Buat file implementasi mock database in-memory dengan OCC simulasi:**
```typescript
// src/infrastructure/InMemoryDatabase.ts
export class InMemoryEngine {
  public orders = new Map<string, { data: any; version: number }>();
  public outbox: Array<{ id: string; event: string; payload: string }> = [];

  public async commit(
    orderId: string, 
    data: any, 
    expectedVersion: number, 
    events: any[]
  ): Promise<void> {
    const existing = this.orders.get(orderId);
    const currentVersion = existing ? existing.version : 0;

    if (currentVersion !== expectedVersion) {
      const err = new Error("OCC Conflict detected!");
      err.name = "OptimisticConcurrencyLockError";
      throw err;
    }

    // Atomic update simulation
    this.orders.set(orderId, { data, version: currentVersion + 1 });
    for (const ev of events) {
      this.outbox.push({
        id: ev.eventId,
        event: ev.eventType,
        payload: JSON.stringify(ev.payload)
      });
    }
  }
}
```

3. **Jalankan Verifikasi Uji Balap Konkurensi (*Race Condition Test*):**
Buat unit test yang memicu dua eksekusi paralel pada aggregate yang sama untuk memastikan OCC melempar error dan Outbox tidak terkorupsi.

---

### 13. Exercise

#### Level: Easy
Implementasikan Value Object `EmailAddress` yang melakukan validasi format email, normalisasi domain (huruf kecil), dan mencegah pembuatan instance jika panjang melebihi 255 karakter. Buat fungsi kesetaraannya (`equals`).

#### Level: Medium
Refaktor Agregat `Order` pada *Practical Example* agar mendukung method `cancelOrder(reason: string)`. Aturan bisnis (*invariant*): 
- Order hanya bisa dibatalkan jika statusnya adalah `DRAFT` atau `CONFIRMED`.
- Jika sudah `CONFIRMED`, batalkan hanya diperbolehkan jika alasan pembatalan memiliki panjang minimal 10 karakter.
- Penerbitan event `OrderCancelledEvent` harus masuk ke dalam outbox.

#### Level: Hard
Bangun implementasi `InventoryReservationAggregate` dengan kemampuan menangani pemesanan stok produk:
- *Invariants:* Stok tidak boleh bernilai negatif; Setiap reservasi memiliki waktu kedaluwarsa (*time-to-live*) selama 15 menit.
- Sediakan metode `reserve(orderId: string, quantity: number): ReservationToken` dan `releaseExpiredReservations(currentTime: Date)`.
- Buat skrip simulasi konkurensi di mana 5 *worker* mencoba memesan stok tersisa 10 secara simultan (masing-masing meminta 3 unit). Pastikan sistem secara deterministik menolak worker ke-4 dan ke-5 tanpa *oversell*.

---

### 14. Challenge

**Skenario Sistem Tiket Konser Skala Global (High-Contention Seat Allocation):**

Anda adalah Principal Architect sebuah platform tiket. Konser artis global membuka penjualan untuk 80.000 kursi di stadion. Sebanyak 1.500.000 pengguna mengakses aplikasi secara bersamaan pada detik pertama pembukaan tiket.

**Tantangan Arsitektur:**
1. Jika setiap kursi dimodelkan sebagai Agregat terpisah, transaksi agregat kecil, tetapi Anda menghadapi *query explosion* untuk memilih sekelompok kursi yang berdekatan.
2. Jika seluruh denah stadion dimodelkan sebagai 1 Agregat `Stadium`, terjadi *lock contention* total yang membekukan transaksi pada request kedua dan seterusnya.
3. Rancang strategi pemodelan domain taktis (DDD) untuk sistem reservasi ini:
   - Bagaimana Anda mendefinisikan batasan *Aggregate*?
   - Bagaimana Anda menegakkan invariant: "Kursi bersebelahan tidak boleh meninggalkan celah 1 kursi kosong (*no single-seat orphan rule*)" tanpa mengunci seluruh baris kursi secara global?
   - Rancang arsitektur persistensi dan mekanisme penanganan konkurensi (optimistic vs pessimistic vs distributed reservation pipeline).
   - Susun dokumen desain teknis ringkas (maksimum 400 kata) yang menjelaskan struktur Agregat, siklus Domain Events, dan strategi alokasi memorinya.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Konseptual Dasar (5 Soal)

1. **Apa perbedaan fundamental antara Entity dan Value Object?**
   - A. Entity memiliki database primary key, Value Object tidak memiliki database.
   - B. Entity diidentifikasi berdasarkan kontinuitas identitas unik sepanjang waktu, sedangkan Value Object diidentifikasi murni berdasarkan kesamaan nilai atributnya (struktural) dan bersifat *immutable*.
   - C. Value Object dapat bermutasi tanpa Aggregate Root, Entity tidak bisa.
   - D. Entity hanya digunakan di Application Layer, Value Object di Domain Layer.

2. **Mengapa sebuah Agregat dilarang memegang referensi langsung berupa objek memori ke Agregat lain?**
   - A. Karena bahasa pemrograman seperti TypeScript atau Java melarang asosiasi pointer antar kelas.
   - B. Agar ukuran file kode program tidak melebihi batasan memori.
   - C. Untuk mencegah penggabungan batasan transaksi (*transactional boundary coupling*), mencegah *cascading lock* di database, dan memfasilitasi arsitektur terdistribusi/microservices.
   - D. Karena semua agregat harus selalu diakses melalui Global Domain Registry.

3. **Kapan sebuah aturan bisnis (*business rule*) harus ditegakkan secara sinkron (*immediate consistency*) dan kapan secara asinkron (*eventual consistency*)?**
   - A. Jika aturan tersebut berada di dalam satu batas Agregat, tegakkan secara sinkron. Jika melibatkan lintas agregat atau lintas Bounded Context, tegakkan secara asinkron.
   - B. Semua aturan finansial harus sinkron, semua aturan non-finansial harus asinkron.
   - C. Tergantung apakah kita menggunakan SQL (sinkron) atau NoSQL (asinkron).
   - D. Aturan bisnis selalu wajib sinkron tanpa pengecualian.

4. **Apa bahaya terbesar dari pola *Anemic Domain Model* pada enterprise application?**
   - A. Penggunaan memori RAM server menjadi dua kali lipat lebih boros.
   - B. Logika bisnis dan penegakan *invariants* tercecer di berbagai *Application Services*, menyebabkan duplikasi kode, inkonsistensi data, dan hilangnya integritas domain seiring pertumbuhan sistem.
   - C. Aplikasi tidak dapat dikompilasi menjadi *native executable*.
   - D. ORM tidak dapat memetakan tabel secara otomatis.

5. **Apa fungsi utama dari Transactional Outbox Pattern?**
   - A. Mengirim email pemberitahuan ke pengguna secara real-time.
   - B. Menjamin bahwa penyimpanan status mutasi data dan penerbitan event terjadi secara atomik (*all-or-nothing*) untuk mencegah inkonsistensi *dual-write*.
   - C. Menggantikan peran Apache Kafka dengan tabel SQL biasa.
   - D. Mengoptimalkan performa kueri baca (*read-query acceleration*).

---

#### Bagian B: Analisis Tingkat Lanjut (5 Soal)

6. **Bagaimana mekanisme Optimistic Concurrency Control (OCC) mendeteksi benturan data (*write collision*)?**
   - A. Mengunci baris database menggunakan sintaks `LOCK TABLES WRITE`.
   - B. Membandingkan atribut versi (*version number* atau *timestamp*) saat membaca data dengan versi saat mengeksekusi *UPDATE*. Jika versi database telah berubah (baris terpengaruh = 0), transaksi dibatalkan.
   - C. Menggunakan distributed lock Redis dengan masa sewa (*lease time*).
   - D. Memeriksa file log Apache Kafka sebelum commit transaksi.

7. **Pada sebuah Agregat `Order`, method `calculateDiscount(promotionService)` membutuhkan data kupon diskon dari luar. Pendekatan mana yang paling mematuhi prinsip DDD murni?**
   - A. Menginjeksi `PromotionRepository` langsung ke dalam konstruktor `Order`.
   - B. Memanggil API HTTP kupon promosi langsung dari dalam method `calculateDiscount`.
   - C. Mengambil data diskon pada Application Service, lalu mengirimkan nilai diskon murni (misal: objek `DiscountPercentage`) sebagai argumen parameter ke method `Order.applyDiscount(discount)`.
   - D. Memindahkan seluruh agregat `Order` ke dalam `PromotionBoundedContext`.

8. **Apa konsekuensi arsitektur dari penggunaan Aggregate yang terlalu besar (*God Aggregate*)?**
   - A. Kegagalan serialisasi JSON pada controller.
   - B. Tingginya frekuensi benturan konkurensi (OCC aborts), latensi database melonjak karena payload I/O besar, dan memory footprint aplikasi membengkak.
   - C. Domain model kehilangan dukungan terhadap tipe data primitif.
   - D. Kode tidak dapat diuji menggunakan Unit Test standar.

9. **Di mana penanganan transaksi database (`BEGIN TRANSACTION`, `COMMIT`, `ROLLBACK`) harus diorkestrasi dalam arsitektur berbasis DDD?**
   - A. Di dalam *Value Object*.
   - B. Di dalam method *Aggregate Root*.
   - C. Di dalam *Domain Service*.
   - D. Di dalam *Application Layer* (Command Handler) atau infrastruktur Unit of Work.

10. **Bagaimana cara menangani *Domain Events* yang diterbitkan oleh agregat jika transaksi database di Application Service mengalami kegagalan (*rollback*)?**
    - A. Mengirim pesan pembatalan manual ke broker Kafka.
    - B. Domain Events hanya diekstrak dan disimpan ke Outbox dalam transaksi database yang sama; jika transaksi di-*rollback*, rekaman Outbox otomatis ikut terhapus sehingga event tidak pernah terkirim.
    - C. Mematikan worker background sementara waktu.
    - D. Menulis ulang riwayat git commit sistem.

---

#### Bagian C: Skenario Kasus Produksi (3 Soal)

11. **Skenario 1:**
    Sebuah aplikasi *e-commerce* mengalami lonjakan pembatalan pesanan karena *stock mismatch*. Tim mendapati bahwa ketika agregat `Order` dibuat, ia memanggil method `inventoryService.deductStock()` secara langsung via synchronous REST API di dalam blok transaksi order. Jika network terputus di tengah jalan, stok terpotong tetapi order gagal disimpan. 
    *Bagaimana solusi arsitektur DDD yang tepat untuk mengeliminasi kelemahan ini?*

12. **Skenario 2:**
    Pada modul `BillingAccount`, dua proses batch otomatis mengeksekusi pemotongan saldo bulanan secara bersamaan pada pukul 00:00 UTC untuk akun yang sama. Kedua proses membaca saldo $100, masing-masing memotong $30, lalu menulis kembali saldo menjadi $70. Seharusnya saldo akhir adalah $40. 
    *Jelaskan analisis akar masalah kegagalan domain ini dan susun solusi konkritnya pada level persistensi & aggregate.*

13. **Skenario 3:**
    Seorang insinyur perangkat lunak menggunakan ORM (seperti Hibernate atau TypeORM) dan memetakan tabel database `users`, `addresses`, dan `roles` secara relasional. Seluruh relasi menggunakan `cascade: true` dan didefinisikan sebagai Agregat `User`. Ketika sistem memiliki 2 juta pengguna, operasi update sederhana pada nama pengguna memakan waktu 3 detik dan menghasilkan puluhan kueri SQL otomatis.
    *Lakukan audit arsitektur: Apa kesalahan konseptual yang terjadi dan bagaimana langkah restrukturisasinya?*

---

#### Kunci Jawaban & Rationale Quiz

##### Bagian A:
1. **B** — Identitas adalah distingsi utama: Entity dibedakan oleh ID unik yang persisten; Value Object dibedakan murni dari nilainya dan harus immutable.
2. **C** — Memegang referensi pointer objek agregat lain mengaburkan batasan konsistensi transaksional dan memicu keterikatan penguncian data di database.
3. **A** — Konsistensi langsung (ACID) hanya wajib di dalam satu Agregat tunggal. Lintas agregat menggunakan Eventual Consistency.
4. **B** — Anemic model memisahkan data dari perilaku, memicu penyebaran aturan bisnis ke luar domain, dan merusak garansi invariants.
5. **B** — Mengatasi masalah *dual-write* terdistribusi dengan memanfaatkan transaksi lokal database untuk menyimpan data dan event outbox secara atomik.

##### Bagian B:
6. **B** — OCC memanfaatkan atomisitas klausa SQL: `UPDATE ... WHERE id = :id AND version = :readVersion`. Jika nilai versi tidak cocok, baris tidak ter-update, menandakan adanya tabrakan modifikasi data.
7. **C** — Menjaga Domain Layer tetap independen dari I/O atau Repositori eksternal (*Purity of Domain Model*). Data eksternal disuplai via parameter.
8. **B** — Agregat besar mengunci banyak data sekaligus, menyebabkan benturan OCC yang tinggi dan konsumsi sumber daya komputasi yang masif.
9. **D** — Batas transaksi adalah perhatian operasional (*orchestration concerns*), yang merupakan tanggung jawab Application Layer / Unit of Work, bukan domain logic.
10. **B** — Transactional Outbox menjamin atomisitas siklus hidup event bersamaan dengan status entitas; jika terjadi rollback di DB, outbox record lenyap bersama seluruh modifikasi state.

##### Bagian C:
11. **Solusi Skenario 1:**
    Hentikan panggilan synchronous RPC di dalam domain/transaksi. Terapkan pola *Choreography Saga* atau *Orchestrated Saga*:
    - Agregat `Order` dibuat dalam status `PENDING_INVENTORY_RESERVATION`.
    - Simpan order dan masukkan event `OrderCreatedDomainEvent` ke Outbox Table secara atomik.
    - Message relay mengirim event ke Message Broker.
    - Layanan Inventory mengonsumsi event, mengeksekusi reservasi stok di agregatnya sendiri, lalu mempublikasikan event `InventoryReserved` atau `InventoryReservationFailed`.
    - Layanan Order mendengarkan event balasan dan mengupdate status Agregat `Order` menjadi `CONFIRMED` atau `REJECTED`.

12. **Solusi Skenario 2:**
    - **Akar Masalah:** Terjadi anomali konkurensi *Lost Update* akibat tiadanya isolasi transaksi yang memadai atau tidak diterapkannya version control (*naive write*).
    - **Solusi DDD & Persistensi:**
      1. Tambahkan atribut `version: number` pada `BillingAccount`.
      2. Terapkan OCC pada Repository: `UPDATE billing_accounts SET balance = :balance, version = version + 1 WHERE id = :id AND version = :currentVersion`.
      3. Proses batch kedua yang membaca versi lama akan gagal (0 row updated) dan memicu `OptimisticConcurrencyLockError`.
      4. Application service menangkap error OCC, melakukan reload aggregate terbaru (saldo kini $70), mengeksekusi ulang pemotongan $30, lalu commit berhasil (saldo akhir menjadi $40).

13. **Solusi Skenario 3:**
    - **Akar Masalah:** Kerancuan antara pemodelan relasi database relasional (ERD) dengan pemodelan DDD (*Data Modeling vs Domain Modeling*). Penggunaan *heavy ORM cascading* memaksa sistem me-load seluruh grafik relasi ke memori.
    - **Langkah Restrukturisasi:**
      1. Putus siklus cascading ORM. Pisahkan `User`, `Address`, dan `Role` menjadi boundary yang tepat.
      2. Jika `Address` hanyalah data pelengkap, modelkan sebagai *Value Object* yang disimpan menyatu (*embedded/JSON column*) di tabel `users`.
      3. Pisahkan `Role` menjadi referensi identitas (`roleIds: string[]`), bukan relasi objek aktif.
      4. Bangun Persistence Data Mapper eksplisit yang hanya memuat field yang benar-benar esensial bagi invariant `User`.

---

### 16. Summary

Implementasi lanjutan Domain-Driven Design (DDD) di tingkat produksi berpusat pada penegakan batas integritas (*integrity boundaries*):
1. **Aggregate Root** berfungsi sebagai gerbang pengawal mutlak aturan bisnis (*invariants*). Batasan agregat harus dirancang sekecil mungkin untuk memaksimalkan performa dan meminimalkan benturan konkurensi.
2. **Keterpisahan Mutlak Domain:** Domain murni tidak boleh terpolusi oleh anotasi ORM, dependensi pustaka web framework, atau dependensi infrastruktur database/broker.
3. **Ketahanan Transaksional:** Mengawinkan **Optimistic Concurrency Control (OCC)** dengan **Transactional Outbox Pattern** merupakan arsitektur standar industri untuk menjamin *consistency* dan *reliability* pada sistem berkinerja tinggi, mengeliminasi risiko kegagalan *dual-write* dan kebocoran konkurensi data.