# BAB 03 / MODUL 01: ARCHITECTURAL STYLES & PARADIGMS

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `ARCH-06-03-01`
* **Nama Modul**: Architectural Styles & Paradigms: Monolith, Microservices, Event-Driven, Space-Based, Service-Oriented, Hexagonal / Ports & Adapters Architecture
* **Kategori**: `06-Architecture-and-System-Design`
* **Jalur Kurikulum (Track)**: `software-architect`
* **Tingkat Kemahiran**: Advanced / Senior Technical Specialist
* **Prasyarat**:
  * Penguasaan mendalam terhadap Object-Oriented Design (SOLID) dan Functional Programming Paradigms.
  * Pemahaman mendalam mengenai Network Fallacies, distributed consensus, CAP/PACELC Theorem.
  * Pengalaman minimal 4+ tahun dalam perancangan dan implementasi sistem produksi berskala besar.
* **Estimasi Waktu Belajar**: 14 Jam Kerja Terfokus (Teori Mendalam, Analisis Kasus, dan Hands-On Implementasi)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Membedakan** secara matematis dan empiris karakteristik struktural, trade-off komputasi, serta karakteristik kopling dari gaya arsitektur Monolith, Microservices, Event-Driven (EDA), Space-Based (SBA), Service-Oriented (SOA), dan Hexagonal.
2. **Merancang Boundary Domain dan Topologi Sistem** menggunakan *Hexagonal Architecture (Ports and Adapters)* guna mengisolasi *pure enterprise domain logic* dari infrastruktur eksternal, framework, dan transport protocols.
3. **Mengevaluasi Kebutuhan Skalabilitas Ekstrem** untuk menentukan kelayakan adopsi *Space-Based Architecture* dengan memanfaatkan *In-Memory Data Grid (IMDG)* dan replikasi asinkron guna mengatasi *database write-bottleneck*.
4. **Mengorkestrasikan dan Menerapkan Pola Event-Driven** (Broker vs. Mediator) dengan mitigasi komprehensif terhadap tantangan *eventual consistency*, *out-of-order execution*, *idempotency*, dan *distributed transaction failures* (melalui Saga Pattern dan Outbox Pattern).
5. **Menjustifikasi Keputusan Arsitektur** melalui pembuatan *Architectural Decision Record (ADR)* yang defensif dan kuantitatif, menyeimbangkan *operational complexity*, *cost of change*, *latency*, dan *organizational topology (Conway’s Law)*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                              ARCHITECTURAL PARADIGMS
                                         │
         ┌───────────────────────────────┴───────────────────────────────┐
         │                                                               │
  STRUCTURAL TOPOLOGY                                             DOMAIN ISOLATION
  (System-Level Distribution)                                     (Application-Level)
         │                                                               │
         ├─► Monolith (Modular vs. Unified Execution)                    └─► Hexagonal / Ports & Adapters
         ├─► Microservices (Distributed Bounded Contexts)                      ├─ Inbound/Driving Ports
         ├─► Service-Oriented (Enterprise Bus Integration)                     ├─ Outbound/Driven Ports
         ├─► Event-Driven (Asynchronous Decoupled Messaging)                   └─ Domain Core (Zero Deps)
         │     ├─ Broker Topology
         │     └─ Mediator Topology
         └─► Space-Based (Tuple Space & Linear In-Memory Scale)
               ├─ Processing Unit (PU)
               ├─ Virtualized Middleware
               │    ├─ Messaging Grid
               │    ├─ Data Grid (IMDG)
               │    └─ Processing Grid
               └─ Data Pump & Asynchronous Writer
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Kegagalan terbesar dalam evolusi perangkat lunak skala enterprise jarang diakibatkan oleh bug sintaksis atau pemilihan framework semata; kegagalan fatal hampir selalu berakar pada **ketidakcocokan mendasar antara karakteristik arsitektur yang dipilih dengan karakteristik domain bisnis serta model beban operasional (*workload profile*)**.

1. **Ilusi Solusi Tunggal (Silver Bullet Fallacy)**: Banyak organisasi melakukan migrasi prematur dari *Monolith* ke *Microservices* yang didorong oleh *hype*, hanya untuk mendapati bahwa mereka mengganti kompilator waktu-nyata (*compile-time safety*) dan performa *in-memory function call* (nanodetik) dengan latensi jaringan (milidetik), serialisasi/deserialisasi payload, kegagalan parsial (*partial network partitions*), dan biaya koordinasi transaksi terdistribusi yang sangat masif (*Distributed Monolith Antipattern*).
2. **Kesesuaian Skalabilitas vs. Konsistensi**: Sistem finansial dengan throughput jutaan transaksi per detik tidak dapat mengandalkan database relasional terpusat (*ACID single bottleneck*). Memahami *Space-Based Architecture* memungkinkan eliminasi *database lock contention* secara total di *critical path*. Sebaliknya, memaksakan *Event-Driven Architecture* pada domain yang membutuhkan konsistensi instan (*strong consistency*) tanpa toleransi rekonsiliasi dapat merusak integritas sistem finansial.
3. **Isolasi Domain Sebagai Aset Termahal**: Frameworks, basis data, dan library protokol komunikasi (HTTP, gRPC, Kafka) selalu berganti (*ephemeral*). *Hexagonal Architecture* menjaga agar *core domain business rules* tetap murni (*deterministic* dan *testable*), terlindung dari degradasi teknologi dan *vendor lock-in*.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Monolith (Unified Deployment Unit)
Gaya arsitektur di mana seluruh fungsionalitas sistem dikemas, diuji, dan disebarkan (*deployed*) sebagai satu unit biner yang dapat dieksekusi secara mandiri.
* **Modular Monolith**: Kode dipartisi secara ketat ke dalam modul domain dengan boundary logis, dependensi satu arah, dan larangan bypass langsung ke penyimpanan internal modul lain, namun tetap berjalan di satu runtime memory space.
* **Spaghetti/Monolithic Ball of Mud**: Modul terikat secara erat (*tightly coupled*), berbagi skema database global, dan dependensi sirkular merajalela.

### 2. Microservices Architecture
Gaya arsitektur terdistribusi di mana aplikasi disusun sebagai kumpulan layanan independen yang berukuran kecil, terorganisir di sekitar Bounded Context domain bisnis (*Domain-Driven Design*), memiliki basis data terisolasi sendiri (*database-per-service*), dan berkomunikasi melalui protokol jaringan ringan (*dumb pipes, smart endpoints*).

### 3. Service-Oriented Architecture (SOA)
Paradigma arsitektur berskala enterprise yang mengonsolidasikan layanan heterogen di seluruh divisi organisasi melalui integrasi berbasis bus middleware terpusat (*Enterprise Service Bus / ESB*). ESB bertanggung jawab atas transformasi protokol, orkestrasi alur kerja, validasi skema pesan, dan perutean (*smart pipes, dumb endpoints*).

### 4. Event-Driven Architecture (EDA)
Paradigma arsitektur asinkron yang berpusat pada penangkapan (*capturing*), pemrosesan, dan persistensi perubahan status yang tidak dapat diubah (*immutable events*).
* **Broker Topology**: Event dikirim ke broker terpusat tanpa orkestrator; konsumen bereaksi secara otonom (*choreography*).
* **Mediator Topology**: Event diterima oleh sebuah mediator orkestrator yang mengoordinasikan langkah-langkah pemrosesan multi-tahap dan mengontrol aliran domain complex.

### 5. Space-Based Architecture (SBA / Tuple Space Pattern)
Arsitektur yang dirancang untuk mengatasi *scalability and concurrency bottlenecks* dengan meniadakan ketergantungan langsung database terpusat pada *transaction processing path*. Status data direplikasi dan didistribusikan langsung ke dalam memori RAM (*In-Memory Data Grid*) dari masing-masing unit komputasi independen (*Processing Units*). Pembaruan database dilakukan secara asinkron (*write-behind*).

### 6. Hexagonal Architecture (Ports and Adapters)
Pola arsitektur aplikasi (tingkat komponen/layanan) yang memisahkan logika domain inti dari dunia luar melalui antarmuka kontrak (*Ports*) dan kode implementasi konversi teknis (*Adapters*). Logika domain tidak memiliki dependensi terhadap framework, database, UI, atau protokol eksternal apa pun (*Dependency Inversion Principle*).

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### 1. Dekonstruksi Mekanisme Hexagonal (Ports & Adapters)
Logika internal sistem dibagi secara konsentris:
* **Core Domain Logic**: Entitas, Value Objects, dan Pure Domain Services.
* **Inbound / Driving Ports**: Interface yang diekspos oleh domain/aplikasi untuk memberi tahu dunia luar tentang operasi yang dapat dilakukannya (contoh: `PlaceOrderUseCase`). Adapter masuk (Driver: Controller REST, CLI, Consumer Event) memanggil port ini.
* **Outbound / Driven Ports**: Interface yang didefinisikan oleh domain/aplikasi yang mewakili kebutuhan eksternal sistem (contoh: `OrderRepository`, `NotificationGateway`). Adapter keluar (Driven: Database SQL Adapter, Kafka Producer Adapter) mengimplementasikan port ini.

### 2. Mekanisme Space-Based Architecture (SBA)
* **Processing Unit (PU)**: Menggabungkan *application logic* dan *in-memory data slice* ke dalam satu wadah runtime.
* **Virtualized Middleware**:
  * *Data Grid*: Mengelola replikasi data antar-PU (misalnya Hazelcast, Apache Ignite) dengan konsistensi terdistribusi.
  * *Processing Grid*: Mengelola alokasi beban kerja komputasi terdistribusi antar PU.
  * *Messaging Grid*: Mengelola perutean pesan/permintaan masuk ke PU yang tepat.
  * *Deployment Manager*: Secara dinamis menyalakan atau mematikan instance PU berdasarkan throughput beban kerja.
* **Data Pump & Data Writer**: Membaca event mutasi dari *In-Memory Data Grid* secara asinkron dan melakukan batch update ke Database Relasional/NoSQL sekunder di luar alur transaksi kritis.

### 3. Dynamic Interaction: EDA Broker vs. Mediator

```
+---------------------------------------------------------------------------------------+
|                                     EDA TOPOLOGIES                                    |
+---------------------------------------------------------------------------------------+

Broker Topology (Choreography):
  [Event Initiator] ──(publishes: OrderPlaced)──► [Event Broker (Exchange/Topic)]
                                                          │
                    ┌─────────────────────────────────────┴─────────────────────────────────────┐
                    ▼                                                                           ▼
       [Inventory Service (Consumer)]                                              [Payment Service (Consumer)]
                    │                                                                           │
        (publishes: StockReserved)                                                  (publishes: PaymentCaptured)
                    │                                                                           │
                    ▼                                                                           ▼
          [Broker (Topic: Inventory)]                                                 [Broker (Topic: Payment)]

Mediator Topology (Orchestration):
  [Event Initiator] ──(publishes: OrderInitiated)──► [Event Broker] ──► [Order Orchestration Mediator]
                                                                                   │
                                  ┌────────────────────────────────────────────────┼────────────────────────────────────────────────┐
                                  │ (Command 1)                                    │ (Command 2)                                    │ (Command 3)
                                  ▼                                                ▼                                                ▼
                         [Payment Service]                                [Inventory Service]                              [Shipping Service]
                                  │                                                │                                                │
                          (returns: Ok/Fail)                               (returns: Ok/Fail)                               (returns: Ok/Fail)
```

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Komparasi Komprehensif: Hexagonal Inside Microservices vs. Space-Based Architecture

```
====================================================================================================
1. HEXAGONAL ARCHITECTURE (PORTS & ADAPTERS INTERACTION MODEL)
====================================================================================================

      INBOUND / DRIVING SIDE                                             OUTBOUND / DRIVEN SIDE
  +-----------------------------+                                    +-----------------------------+
  |    HTTP / REST Controller   |                                    |    Postgres SQL Adapter     |
  |     (Driving Adapter)       |                                    |       (Driven Adapter)      |
  +--------------+--------------+                                    +--------------▲--------------+
                 │ Calls                                                            │ Implements
                 ▼                                                                  │
  +-----------------------------+                                    +--------------┴--------------+
  |  <<Inbound / Driving Port>> |                                    |  <<Outbound / Driven Port>> |
  |      PlaceOrderCommand      |                                    |       OrderRepository       |
  +--------------▲--------------+                                    +--------------▲--------------+
                 │ Implemented by                                                   │ Injected Into
  +--------------┴──────────────────────────────────────────────────────────────────┴--------------+
  |                                     APPLICATION CORE BOUNDARY                                  |
  |                                                                                                |
  |     +------------------------------------------------------------------------------------+     |
  |     | Application Service: PlaceOrderHandler                                             |     |
  |     |                                                                                    |     |
  |     |   Execute(cmd):                                                                    |     |
  |     |      1. Domain validation                                                          |     |
  |     |      2. Invoke Domain Model logic: order.CalculateTotal()                          |     |
  |     |      3. Persist via Driven Port: orderRepo.Save(order)                             |     |
  |     |      4. Emit domain events                                                         |     |
  |     +-----------------------------------------▲------------------------------------------+     |
  |                                               │ Operates on                                    |
  |     +-----------------------------------------┴------------------------------------------+     |
  |     | PURE DOMAIN MODEL:                                                                 |     |
  |     |   - Entities: Order, OrderItem                                                     |     |
  |     |   - Value Objects: Money, SKU, CustomerId                                          |     |
  |     |   - Domain Events: OrderCreated, ItemOutOfStock                                    |     |
  |     |   (Strictly NO dependencies on SQL, ORM, Web Frameworks, or External Libs)         |     |
  |     +------------------------------------------------------------------------------------+     |
  +------------------------------------------------------------------------------------------------+

====================================================================================================
2. SPACE-BASED ARCHITECTURE (SBA) ENGINE TOPOLOGY
====================================================================================================

                                       [ Client Requests ]
                                                │
                                                ▼
  +────────────────────────────────────────────────────────────────────────────────────────────────+
  |                                      VIRTUALIZED MIDDLEWARE                                    |
  |                                                                                                |
  |    +──────────────────────────────────────────────────────────────────────────────────────+    |
  |    | Messaging Grid (Dynamic Load Balancer / Session Router / Sticky Message Router)       |    |
  |    +──────────────────────────────────────────┬───────────────────────────────────────────+    |
  +───────────────────────────────────────────────┼────────────────────────────────────────────────+
                                                  │ Routes work payloads
               ┌──────────────────────────────────┴──────────────────────────────────┐
               ▼                                                                     ▼
  +─────────────────────────+                                           +─────────────────────────+
  |  PROCESSING UNIT (PU 1) |                                           |  PROCESSING UNIT (PU 2) |
  |                         |                                           |                         |
  |  +───────────────────+  |      Replicated / Partitioned State       |  +───────────────────+  |
  |  | Business Engine   |  | ◄═══════════════════════════════════════► |  | Business Engine   |  |
  |  +─────────┬─────────+  |             (IMDG Sync Link)              |  +─────────┬─────────+  |
  |            │ In-Memory  |                                           |            │ In-Memory  |
  |            ▼ Read/Write |                                           |            ▼ Read/Write |
  |  +───────────────────+  |                                           |  +───────────────────+  |
  |  | In-Memory Data    |  |                                           |  | In-Memory Data    |  |
  |  | Grid Node (IMDG)  |  |                                           |  | Grid Node (IMDG)  |  |
  |  +─────────┬─────────+  |                                           |  +─────────┬─────────+  |
  +────────────┼────────────+                                           +────────────┼────────────+
               │                                                                     │
               │ Async In-Memory Replication Pump                                    │ Async Pump
               ▼                                                                     ▼
  +────────────────────────────────────────────────────────────────────────────────────────────────+
  | Data Pump / Asynchronous Queue Middleware (Persistent Buffering Engine)                        |
  +───────────────────────────────────────────────┬────────────────────────────────────────────────+
                                                  │ Batch Writer Execution
                                                  ▼
                                    +───────────────────────────+
                                    | Central Database (RDBMS)  |
                                    | (Non-blocking background) |
                                    +───────────────────────────+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Implementasi minimal pola **Hexagonal Architecture** dalam TypeScript murni tanpa runtime framework. Menunjukkan decoupling mutlak antara domain, primary port, secondary port, dan adapters.

### 1. Domain Entities & Value Objects (Pure Core)
```typescript
// domain/wallet.ts
export class InsufficientFundsError extends Error {
  constructor(message = "Insufficient funds for this transaction") {
    super(message);
    this.name = "InsufficientFundsError";
  }
}

export class Wallet {
  constructor(
    public readonly id: string,
    public readonly ownerId: string,
    private balance: number
  ) {
    if (balance < 0) throw new Error("Balance cannot be negative");
  }

  public getBalance(): number {
    return this.balance;
  }

  public debit(amount: number): void {
    if (amount <= 0) throw new Error("Debit amount must be positive");
    if (this.balance < amount) throw new InsufficientFundsError();
    this.balance -= amount;
  }

  public credit(amount: number): void {
    if (amount <= 0) throw new Error("Credit amount must be positive");
    this.balance += amount;
  }
}
```

### 2. Ports (Contracts for Inbound & Outbound)
```typescript
// ports/outbound/wallet-repository.port.ts
import { Wallet } from "../../domain/wallet";

export interface WalletRepositoryPort {
  findById(id: string): Promise<Wallet | null>;
  save(wallet: Wallet): Promise<void>;
}

// ports/inbound/debit-wallet.usecase.ts
export interface DebitWalletCommand {
  walletId: string;
  amount: number;
}

export interface DebitWalletUseCase {
  execute(command: DebitWalletCommand): Promise<{ newBalance: number }>;
}
```

### 3. Application Core Service (implements Inbound Port, uses Outbound Port)
```typescript
// application/debit-wallet.service.ts
import { DebitWalletUseCase, DebitWalletCommand } from "../ports/inbound/debit-wallet.usecase";
import { WalletRepositoryPort } from "../ports/outbound/wallet-repository.port";

export class DebitWalletService implements DebitWalletUseCase {
  constructor(private readonly walletRepo: WalletRepositoryPort) {}

  async execute(command: DebitWalletCommand): Promise<{ newBalance: number }> {
    const wallet = await this.walletRepo.findById(command.walletId);
    if (!wallet) {
      throw new Error(`Wallet ${command.walletId} not found`);
    }

    // Eksekusi pure domain logic
    wallet.debit(command.amount);

    // Persistensi via Driven/Outbound Port
    await this.walletRepo.save(wallet);

    return { newBalance: wallet.getBalance() };
  }
}
```

### 4. Outbound / Driven Adapter (Memory or SQL Adapter)
```typescript
// adapters/outbound/in-memory-wallet.adapter.ts
import { WalletRepositoryPort } from "../../ports/outbound/wallet-repository.port";
import { Wallet } from "../../domain/wallet";

export class InMemoryWalletAdapter implements WalletRepositoryPort {
  private store: Map<string, Wallet> = new Map();

  async findById(id: string): Promise<Wallet | null> {
    const w = this.store.get(id);
    if (!w) return null;
    // Return copy to prevent mutation escape
    return new Wallet(w.id, w.ownerId, w.getBalance());
  }

  async save(wallet: Wallet): Promise<void> {
    this.store.set(wallet.id, wallet);
  }
}
```

### 5. Inbound / Driving Adapter (CLI/HTTP Entrypoint)
```typescript
// adapters/inbound/cli.ts
import { DebitWalletService } from "../../application/debit-wallet.service";
import { InMemoryWalletAdapter } from "../outbound/in-memory-wallet.adapter";
import { Wallet } from "../../domain/wallet";

async function main() {
  const repoAdapter = new InMemoryWalletAdapter();
  await repoAdapter.save(new Wallet("wal-101", "usr-888", 5000));

  // Dependency Inversion: Wire Adapters via Ports
  const useCase = new DebitWalletService(repoAdapter);

  const result = await useCase.execute({ walletId: "wal-101", amount: 1500 });
  console.log(`[CLI Adapter] Debit success! Balance remaining: ${result.newBalance}`);
}

main().catch(console.error);
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus Produksi: **High-Throughput Flash-Sale Order Processing Engine** memadukan pendekatan **Hexagonal Architecture** dengan **Space-Based (In-Memory Grid) & Outbox Pattern**.

### Desain Arsitektur
1. Domain Core memvalidasi alokasi inventaris instan tanpa disk I/O.
2. In-Memory Data Grid (IMDG) menyimpan inventaris dan status pesanan.
3. Transactional Outbox mempublikasikan event `OrderPlaced` ke Messaging Grid secara andal tanpa *two-phase commit (2PC)*.

```typescript
// ============================================================================
// 1. CORE DOMAIN: Pure Entities, Events, & Invariant Enforcement
// ============================================================================
export interface DomainEvent {
  occurredOn: Date;
  eventType: string;
}

export class OrderCreatedEvent implements DomainEvent {
  public readonly occurredOn = new Date();
  public readonly eventType = "OrderCreatedEvent";
  constructor(
    public readonly orderId: string,
    public readonly itemId: string,
    public readonly quantity: number,
    public readonly totalAmount: number
  ) {}
}

export class FlashSaleOrder {
  private events: DomainEvent[] = [];

  constructor(
    public readonly id: string,
    public readonly customerId: string,
    public readonly itemId: string,
    public readonly quantity: number,
    public readonly unitPrice: number,
    private status: "PENDING" | "CONFIRMED" | "FAILED" = "PENDING"
  ) {
    if (quantity <= 0) throw new Error("Invalid quantity");
    this.events.push(new OrderCreatedEvent(id, itemId, quantity, quantity * unitPrice));
  }

  public getStatus() { return this.status; }
  public confirm() { this.status = "CONFIRMED"; }
  public fail() { this.status = "FAILED"; }
  public pullEvents(): DomainEvent[] {
    const recorded = [...this.events];
    this.events = [];
    return recorded;
  }
}

// ============================================================================
// 2. PORTS DEFINITION (Hexagonal Interfaces)
// ============================================================================

// Outbound: In-Memory Data Grid Partition Access
export interface InventoryGridPort {
  decrementIfAvailable(itemId: string, qty: number): Promise<boolean>;
  rollback(itemId: string, qty: number): Promise<void>;
}

// Outbound: Atomic Outbox & Order State Storage (IMDG-backed)
export interface OrderStateGridPort {
  save(order: FlashSaleOrder, outboxEvents: DomainEvent[]): Promise<void>;
}

// Inbound Port
export interface PlaceOrderCommand {
  orderId: string;
  customerId: string;
  itemId: string;
  quantity: number;
  unitPrice: number;
}

export interface PlaceOrderUseCase {
  execute(command: PlaceOrderCommand): Promise<{ status: "CONFIRMED" | "REJECTED"; reason?: string }>;
}

// ============================================================================
// 3. APPLICATION SERVICE (Use Case Implementation)
// ============================================================================
export class FlashSaleOrderService implements PlaceOrderUseCase {
  constructor(
    private readonly inventoryGrid: InventoryGridPort,
    private readonly orderGrid: OrderStateGridPort
  ) {}

  async execute(command: PlaceOrderCommand): Promise<{ status: "CONFIRMED" | "REJECTED"; reason?: string }> {
    // Langkah 1: Lock-Free In-Memory Atomic Operation pada IMDG
    const reserved = await this.inventoryGrid.decrementIfAvailable(command.itemId, command.quantity);
    if (!reserved) {
      return { status: "REJECTED", reason: "OUT_OF_STOCK" };
    }

    try {
      // Langkah 2: Bangun Domain Entity
      const order = new FlashSaleOrder(
        command.orderId,
        command.customerId,
        command.itemId,
        command.quantity,
        command.unitPrice
      );
      order.confirm();

      // Ambil Domain Events
      const events = order.pullEvents();

      // Langkah 3: Persistensi atomik ke Memory Space & Outbox Buffer
      await this.orderGrid.save(order, events);

      return { status: "CONFIRMED" };
    } catch (err: any) {
      // Rollback memory grid item stock jika pipeline logic internal gagal
      await this.inventoryGrid.rollback(command.itemId, command.quantity);
      return { status: "REJECTED", reason: err.message };
    }
  }
}

// ============================================================================
// 4. ADAPTER IMPLEMENTATIONS (Infrastructure / Driven Layer)
// ============================================================================

// Adapter: In-Memory Data Grid Simulator (Space-Based Architecture Partition)
export class HazelcastDataGridAdapter implements InventoryGridPort, OrderStateGridPort {
  // Simulasi memory partition lokal / remote IMDG node
  private stockStore = new Map<string, number>();
  private orderStore = new Map<string, FlashSaleOrder>();
  private outboxQueue: Array<{ event: DomainEvent; published: boolean }> = [];

  constructor() {
    // Seed initial stock
    this.stockStore.set("FLASH-SKU-99", 5);
  }

  async decrementIfAvailable(itemId: string, qty: number): Promise<boolean> {
    const current = this.stockStore.get(itemId) ?? 0;
    if (current >= qty) {
      this.stockStore.set(itemId, current - qty);
      return true; // Berhasil didecrement secara atomic di RAM
    }
    return false;
  }

  async rollback(itemId: string, qty: number): Promise<void> {
    const current = this.stockStore.get(itemId) ?? 0;
    this.stockStore.set(itemId, current + qty);
  }

  async save(order: FlashSaleOrder, outboxEvents: DomainEvent[]): Promise<void> {
    this.orderStore.set(order.id, order);
    for (const evt of outboxEvents) {
      this.outboxQueue.push({ event: evt, published: false });
    }
  }

  // Komponen Data Pump (Background Worker SBA)
  public async flushOutboxToBroker(brokerCallback: (event: DomainEvent) => Promise<void>) {
    for (const item of this.outboxQueue.filter((i) => !i.published)) {
      await brokerCallback(item.event);
      item.published = true;
    }
  }

  public getStockSnapshot(itemId: string): number {
    return this.stockStore.get(itemId) ?? 0;
  }
}

// ============================================================================
// 5. RUNTIME COMPOSITION & TEST HARNESS
// ============================================================================
async function runProductionScenario() {
  const imdgAdapter = new HazelcastDataGridAdapter();
  const orderService = new FlashSaleOrderService(imdgAdapter, imdgAdapter);

  console.log(`[INIT] Stock SKU: FLASH-SKU-99 = ${imdgAdapter.getStockSnapshot("FLASH-SKU-99")}`);

  // Simulasi 6 request pesanan masuk serentak
  const requests = Array.from({ length: 6 }).map((_, idx) =>
    orderService.execute({
      orderId: `ORD-00${idx + 1}`,
      customerId: `CUST-${100 + idx}`,
      itemId: "FLASH-SKU-99",
      quantity: 1,
      unitPrice: 150000,
    })
  );

  const results = await Promise.all(requests);
  results.forEach((res, i) => {
    console.log(`Order ORD-00${i + 1} Result: ${res.status} ${res.reason ? `(${res.reason})` : ""}`);
  });

  console.log(`[POST] Sisa Stok di RAM Grid: ${imdgAdapter.getStockSnapshot("FLASH-SKU-99")}`);

  // Asynchronous Data Pump Execution
  console.log("\n[DATA PUMP ENGINE] Mengalirkan Outbox ke Event Broker...");
  await imdgAdapter.flushOutboxToBroker(async (evt) => {
    console.log(` -> Dispatched Event: ${evt.eventType} at ${evt.occurredOn.toISOString()}`);
  });
}

runProductionScenario();
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Memilih arsitektur adalah latihan mengelola kompromi (*trade-offs*). Matriks di bawah ini merangkum perbandingan dimensi teknis kritis:

| Dimensi Arsitektural | Monolith (Modular) | Microservices | Event-Driven (EDA) | Space-Based (SBA) | Service-Oriented (SOA) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Complexity Level** | Rendah - Menengah | Sangat Tinggi | Tinggi | Sangat Tinggi | Sangat Tinggi |
| **Deployment Independence** | Tunggal (All-or-Nothing) | Penuh per-layanan | Parsial hingga Penuh | Penuh per Processing Unit | Terikat koordinasi ESB |
| **Data Consistency** | ACID (Ketat) | Eventual Consistency | Eventual Consistency | Eventual (Write-Behind) | ACID / 2PC via ESB |
| **Throughput / Latency** | Ultra-Low Latency (RAM) | High Latency (Network) | Menengah (Async Broker) | Ultra-Low Latency (RAM Grid) | Menengah-Rendah (ESB Overhead) |
| **Elastic Scalability** | Vertikal (Keterbatasan HW) | Horizontal Dinamis | Horizontal Dinamis | Linier Ekstrem (In-Memory) | Horisontal Kompleks |
| **Fault Isolation** | Rendah (Crash = All Down) | Tinggi (Isolasi Layanan) | Sangat Tinggi | Tinggi (Unit Autonomous) | Menengah (ESB = Single SPOF) |
| **Operational Cost** | Rendah | Sangat Tinggi (K8s, Mesh)| Tinggi (Broker Management)| Ekstrem (RAM Hardware Cost)| Sangat Tinggi (Vendor Licenses)|

---

## SEKSI 11 — BEST PRACTICES

1. **Law of Bounded Context Alignment**: Jangan memecah microservices berdasarkan tabel database atau entitas visual UI. Pecah layanan hanya di sepanjang batasan bounded context linguistik domain (*Domain-Driven Design*).
2. **Ports as Invariants Protectors**: Letakkan *Primary Ports* dan *Secondary Ports* di dalam lapisan logika domain/aplikasi. Jangan pernah biarkan adapter menentukan kontrak domain. Interface dimiliki oleh pemanggil (*consumer*), bukan penyedia implementasi.
3. **Idempotency by Design pada EDA**: Semua event consumer wajib berstatus idempoten. Gunakan `MessageId` unik dengan pola *Deduplication Store* berbasis Redis/Database untuk mencegah pemrosesan ganda akibat transmisi jaringan (*at-least-once delivery*).
4. **Data Grid Partitioning Strategy (SBA)**: Tentukan *Partition Key* secara hati-hati pada Space-Based Architecture. Pastikan entitas yang saling berelasi erat (contoh: `Customer` dan `Orders`) berada dalam satu partisi fisik memori yang sama (*Colocation*) untuk mencegah latensi *cross-node join*.
5. **Decouple Broker Topology**: Pada EDA, hindari menggunakan topik tunggal untuk banyak tipe event yang tidak berkorelasi. Pisahkan topik berdasarkan semantik bisnis dan skala throughput konsumsi.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **The Distributed Monolith**: Memecah kode ke dalam repositori atau kontainer microservice yang terpisah, namun tetap mengikat seluruh layanan tersebut ke dalam satu basis data terpusat yang sama (*Shared Database Antipattern*). Mengakibatkan skema database tidak dapat diubah tanpa merusak layanan lain.
2. **Dual-Write Hazard**: Melakukan penulisan ke database lokal, kemudian segera mengirim HTTP request atau pesan broker dalam thread yang sama tanpa transaksi atomik. Jika broker mati, data di DB tersimpan namun event tidak pernah terkirim (*inconsistent state*). **Solusi**: Terapkan *Transactional Outbox Pattern* dengan Debezium / Change Data Capture (CDC).
3. **Smart Pipes, Dumb Consumers (ESB Re-emergence)**: Meletakkan aturan bisnis kompleks di dalam message broker (seperti skrip transformasi berat di Apache Kafka stream routing) alih-alih di dalam consumer. Ini mengulang kegagalan arsitektur SOA kuno.
4. **Leaky Hexagonal Abstraction**: Memasukkan anotasi database ORM (misal: `@Entity`, `@Column`, `@Table`) langsung ke dalam domain core kelas entitas. Hal ini mengikat logika bisnis murni dengan vendor persistence eksternal.
5. **Ignoring Network Latency in EDA/Microservices**: Mengasumsikan latensi jaringan bernilai nol dan throughput tak terbatas (*Fallacies of Distributed Computing*), memicu fenomena kaskade kegagalan (*cascading failures*) tanpa implementasi *Circuit Breaker* dan *Bulkhead*.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Refactoring Spaghetti ke Hexagonal Architecture
* **Skenario**: Diberikan sebuah fungsi controller monolitik Express.js sebesar 400 baris yang langsung mengeksekusi parsing JSON, validasi data, raw SQL query ke database PostgreSQL, serta integrasi API Stripe.
* **Tugas**: 
  1. Ekstrak *Core Domain Model* dan *Value Objects*.
  2. Definisikan Inbound Port (`ProcessPaymentUseCase`) dan Outbound Ports (`PaymentGatewayPort`, `TransactionRepositoryPort`).
  3. Implementasikan Controller sebagai Driving Adapter dan PostgreSQL/Stripe sebagai Driven Adapters.

### Latihan 2: Desain Transaksi EDA dengan Saga Orchestration
* **Skenario**: Sistem *E-Commerce Travel Booking* yang melibatkan tiga layanan: Penerbangan (*Flight*), Hotel (*Accommodation*), dan Pembayaran (*Billing*).
* **Tugas**:
  1. Buat sequence diagram ASCII untuk skenario kegagalan: Reservasi penerbangan berhasil, reservasi hotel gagal.
  2. Rancang *Compensating Transactions* untuk membatalkan reservasi penerbangan secara konsisten.
  3. Tuliskan pseudocode *Saga Orchestrator* yang menangani timeout dan out-of-order acknowledgment.

### Latihan 3: Kalkulasi Dimensi Kapasitas Space-Based Architecture
* **Skenario**: Sistem bursa kripto menerima 250.000 transaksi/detik pada peak hour. Setiap transaksi mutasi memerlukan payload memori 1,2 KB.
* **Tugas**:
  1. Hitung kebutuhan throughput memori minimum per detik (MB/s).
  2. Rancang topologi partisi IMDG dengan replikasi faktor $R=2$ untuk menjamin *zero data loss* saat 1 host mati mendadak.
  3. Tentukan batas latensi *asynchronous data pump* ke database dingin agar tidak terjadi saturasi heap memori RAM.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Apa perbedaan mendasar antara Driving Adapter dan Driven Adapter pada Hexagonal Architecture?**
   * A. Driving Adapter berinteraksi dengan database, sedangkan Driven Adapter berinteraksi dengan UI.
   * B. Driving Adapter memanggil Inbound Port untuk mengeksekusi operasi domain, sedangkan Driven Adapter mengimplementasikan Outbound Port yang dipanggil oleh domain logic.
   * C. Driving Adapter ditulis dengan TypeScript, sedangkan Driven Adapter harus ditulis dengan SQL.
   * D. Driven Adapter mengontrol lifecycle seluruh aplikasi secara deterministik.
   * *Jawaban yang Benar*: **B**. Driving adapter menginisiasi aksi (drive) ke dalam sistem, Driven adapter digerakkan (driven) oleh sistem.

2. **Karakteristik utama Space-Based Architecture yang menyebabkannya mampu menangani traffic write yang masif dibandingkan arsitektur tradisional adalah:**
   * A. Menggunakan database NoSQL berkinerja tinggi.
   * B. Mengeliminasi database terpusat dari *synchronous transaction path* dengan memindahkan seluruh state ke *In-Memory Data Grid* yang terpartisi.
   * C. Mengimplementasikan caching HTTP reverse proxy di layer terdepan.
   * D. Menghubungkan seluruh service melalui enterprise service bus yang cepat.
   * *Jawaban yang Benar*: **B**. SBA menghilangkan bottleneck I/O database transaksional dengan memproses mutasi state murni dalam memori terdistribusi.

3. **Kapan Event-Driven Broker Topology lebih disukai dibandingkan Mediator Topology?**
   * A. Ketika alur transaksi membutuhkan orkestrasi berurutan yang ketat, sentralisasi kontrol, dan kompensasi eksplisit.
   * B. Ketika bisnis membutuhkan koordinasi workflow yang kompleks antar 10 departemen berbeda.
   * C. Ketika sistem memprioritaskan decoupling tinggi, extensibilitas cepat, dan alur pemrosesan event bersifat independen serta reaktif tanpa butuh sentralisasi flow.
   * D. Ketika database ACID dua fasa (2PC) diwajibkan oleh regulator perbankan.
   * *Jawaban yang Benar*: **C**. Broker topology menggunakan koreografi alami di mana service bereaksi secara otonom tanpa adanya *central point of orchestration*.

4. **Masalah utama yang timbul akibat "Database-per-Service" pattern pada Microservices adalah:**
   * A. Biaya lisensi database otomatis berlipat ganda.
   * B. Hilangnya kemampuan eksekusi atomic cross-domain ACID transactions dan tantangan berat dalam melakukan agregasi query data join.
   * C. Tidak dapat melakukan auto-scaling secara dinamis di Kubernetes.
   * D. Wajib menggunakan schema-less database seperti MongoDB.
   * *Jawaban yang Benar*: **B**. Isolasi data memutus integritas referensial dan foreign key joins antar bounded context, menuntut adopsi eventual consistency (Saga/CQRS).

5. **Di bawah hukum Conway (Conway's Law), dampak dari merancang Microservices dengan tim pengembang yang terspesialisasi secara horizontal (Tim Frontend, Tim Backend, Tim DBA terpisah) adalah:**
   * A. Lahirnya microservices yang murni berorientasi pada domain bisnis yang modular.
   * B. Peningkatan performa deploy tanpa friksi komunikasi.
   * C. Terciptanya layanan yang merefleksikan silo fungsional teknis (Service UI, Service Logic, Service DB) yang saling tergantung erat, bukan layanan berbasis bounded context.
   * D. Otomatisasi CI/CD berjalan lebih cepat.
   * *Jawaban yang Benar*: **C**. Struktur komunikasi organisasi mendikte arsitektur sistem; isolasi layer teknis menghasilkan ketergantungan silo teknis horizontal.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku Fundamental**:
  * Richards, Mark & Ford, Neal. (2020). *Fundamentals of Software Architecture: An Engineering Approach*. O'Reilly Media.
  * Cockburn, Alistair. (2005). *Hexagonal Architecture (Ports and Adapters Pattern)*. Alistair.Cockburn.us.
  * Newman, Sam. (2021). *Building Microservices: Designing Fine-Grained Systems (2nd Edition)*. O'Reilly Media.
  * Hohpe, Gregor & Woolf, Bobby. (2003). *Enterprise Integration Patterns: Designing, Building, and Deploying Messaging Solutions*. Addison-Wesley Professional.
* **Makalah Akademis & Standar Industri**:
  * Gelernter, David. (1985). *Generative Communication in Linda* (Basis teori Tuple Space dan Space-Based Architecture). ACM Transactions on Programming Languages and Systems.
  * Vogels, Werner. (2009). *Eventually Consistent - Revisited*. Communications of the ACM.
* **Artikel Lanjutan**:
  * Fowler, Martin. (2014). *Microservices: a definition of this new architectural term*. martinfowler.com.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **Arsitektur Bukan Keputusan Hitam-Putih**: Tidak ada arsitektur yang superior secara absolut. Monolith unggul dalam kesederhanaan operasional dan latensi lokal; Microservices unggul dalam otonomi tim skala besar; EDA unggul dalam elastisitas event asinkron; Space-Based Architecture adalah solusi definitif untuk throughput ekstrim yang melampaui kemampuan database I/O konvensional.
2. **Hexagonal Architecture sebagai Fondasi**: Apapun gaya distribusi tingkat makro yang dipilih (Monolith, Microservices, atau Space-Based), menjaga isolasi *Core Domain* melalui *Ports and Adapters* menjamin sistem tetap dapat diuji, adaptif terhadap evolusi teknologi, dan bebas dari dependensi infrastruktur.
3. **Konsekuensi Sistem Terdistribusi**: Memilih arsitektur terdistribusi berarti siap membayar pajak kompleksitas: hilangnya integritas transaksional instan (ACID digantikan BASE), latensi jaringan, kebutuhan observabilitas yang kompleks (Distributed Tracing), dan tantangan konsistensi data.

---

## SEKSI 17 — GLOSARIUM

* **Bounded Context**: Batasan eksplisit dalam model domain di mana istilah, model data, dan aturan bisnis memiliki arti spesifik dan tidak ambigu.
* **Enterprise Service Bus (ESB)**: Perangkat lunak middleware arsitektur SOA yang memusatkan orkestrasi, transformasi protokol, dan perutean pesan antar layanan enterprise.
* **In-Memory Data Grid (IMDG)**: Kumpulan node komputasi yang membagi dan menyinkronkan data status ke dalam memori RAM secara terdistribusi untuk akses data berkecepatan tinggi.
* **Processing Unit (PU)**: Unit penyebaran independen dalam Space-Based Architecture yang berisi logika komputasi bisnis dan node slice memori data grid.
* **Idempotency**: Properti dari suatu operasi di mana eksekusi berulang kali dengan input yang sama menghasilkan state akhir sistem yang sama persis seperti eksekusi tunggal.
* **Transactional Outbox Pattern**: Pola desain di mana pesan/event disimpan terlebih dahulu ke dalam penyimpanan lokal secara atomik bersamaan dengan mutasi entitas, sebelum dipublikasikan ke event broker oleh worker terpisah.
* **Dependency Inversion Principle (DIP)**: Prinsip desain perangkat lunak yang menyatakan bahwa modul tingkat tinggi tidak boleh bergantung pada modul tingkat rendah; keduanya harus bergantung pada abstraksi (antarmuka).
* **Write-Behind Caching**: Pola persistensi di mana pembaruan data ditulis terlebih dahulu ke cache/in-memory grid, kemudian dialirkan ke basis data persisten sekunder secara asinkron.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Pedagogical Strategy**: 
  * Jangan biarkan peserta terjebak dalam perdebatan "Monolith vs Microservices" tanpa konteks bisnis nyata. Paksa peserta mendefinisikan *throughput requirements*, ukuran tim organisasi, dan toleransi konsistensi data sebelum memperbolehkan mereka memilih gaya arsitektur.
  * Berikan perhatian khusus pada *Space-Based Architecture*. Banyak peserta senior belum pernah melihat implementasi SBA secara praktis dan cenderung mencoba menyelesaikan beban konkurensi tinggi semata-mata dengan menambah read-replica database konvensional yang tidak menyelesaikan masalah *write-lock contention*.
* **Titik Kritis Diskusi**:
  * Bahas secara tajam perbedaan filosofis antara SOA (Enterprise Bus, orkestrasi terpusat) dan Microservices (Smart Endpoints, Dumb Pipes, otonomi penuh).
  * Tantang peserta untuk menunjukkan baris kode mana dalam *Hexagonal Architecture* yang membuktikan bahwa domain tidak terkontaminasi framework (misalnya: tidak adanya dependensi package eksternal pada file entitas).

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi**: `1.0.0`
* **Status**: Production-Ready / Stable
* **Tanggal Rilis**: 2025-05-18
* **Author**: Senior Technical Curriculum Architect
* **Riwayat Perubahan**:
  * `1.0.0` (2025-05-18): Rilis modul lengkap mencakup 6 paradigma arsitektur utama, kode praktis TypeScript production-grade, analisis SBA mendalam, diagram ASCII detail, dan matriks trade-offs.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `ARCH-06-02-03` — Advanced Distributed System Fundamentals & Network Fallacies
* **Modul Berikutnya**: `ARCH-06-03-02` — Microservices Decomposition Strategies: Domain-Driven Design, Saga, and CQRS/Event Sourcing Patterns
* **Track Index**: `software-architect` / `06-Architecture-and-System-Design`