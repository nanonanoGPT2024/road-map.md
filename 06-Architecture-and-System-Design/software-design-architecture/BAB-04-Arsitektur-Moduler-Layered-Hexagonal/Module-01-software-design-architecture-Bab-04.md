## SEKSI 01 — IDENTITAS MODUL

*   **Modul ID:** `ARCH-04-01`
*   **Track:** `06-Architecture-and-System-Design`
*   **Kurikulum:** `software-design-architecture`
*   **Bab:** `04 — Arsitektur Moduler & Layered: Monolith Modern hingga Hexagonal`
*   **Modul:** `01 — Layered, Onion, Clean Architecture, Ports & Adapters, dan Modular Monolith`
*   **Prasyarat:**
    *   Pemahaman mendalam mengenai Prinsip SOLID (terutama *Dependency Inversion Principle*).
    *   Pemahaman Object-Oriented Programming (OOP) tingkat lanjut atau functional paradigm dengan abstraksi tipe data kuat.
    *   Pengalaman membangun aplikasi *monolithic* berbasis basis data relasional.
*   **Target Audiens:** Senior Software Engineer, Technical Lead, Application Architect, System Architect.
*   **Estimasi Waktu:** 8–10 jam pembelajaran mandiri dan implementasi hands-on.
*   **Tingkat Kesulitan:** Advanced (Tingkat Lanjut).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Mendekonstruksi Paradigma Arsitektur N-Tier Tradisional:** Mengidentifikasi secara kritis kelemahan fundamental *Database-Centric Layered Architecture* yang memicu keterikatan ketat (*tight coupling*) dan degradasi integritas domain.
2.  **Menganalisis Mekanisme Dependency Inversion pada Arsitektur Modern:** Menjelaskan perbedaan mendasar antara *Control Flow* (alur eksekusi) dan *Dependency Flow* (arah ketergantungan kode sumber) dalam arsitektur terisolasi.
3.  **Membedakan Hexagonal, Onion, dan Clean Architecture:** Mengidentifikasi variasi taksonomi, titik temu (*common grounds*), serta perbedaan implementatif antara konsep Alistair Cockburn (*Ports & Adapters*), Jeffrey Palermo (*Onion*), dan Robert C. Martin (*Clean Architecture*).
4.  **Mengimplementasikan Pola Ports and Adapters:** Merancang dan membangun domain aplikasi murni tanpa dependensi eksternal, mengekspos *Inbound (Driving) Ports*, dan mengabstraksi dependensi infrastruktur melalui *Outbound (Driven) Ports*.
5.  **Merancang Modular Monolith Berdaya Tahan Tinggi:** Menyusun batas-batas modul (*in-process module boundaries*) dengan *encapsulation*, mencegah kebocoran model domain antar-modul, serta memfasilitasi komunikasi asinkron via *in-memory event bus* atau *facade interfaces*.
6.  **Menegakkan Aturan Arsitektur (*Architectural Fitness Functions*):** Menerapkan alat verifikasi otomatis (*architectural linters*) untuk memvalidasi bahwa arah dependensi tidak dilanggar oleh anggota tim dalam proses CI/CD.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                              [ARQUITECTURE EVOLUTION]
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
     [Database-Centric N-Tier]                     [Domain-Centric / Inverted]
     - UI -> Service -> Data Access                - Dependensi mengarah ke Core
     - Logic terikat skema database                - Business Logic sepenuhnya independen
                 │                                               │
                 │                               ┌───────────────┴───────────────┐
                 │                               ▼                               ▼
                 │                   [Ports and Adapters]               [Onion / Clean]
                 │                   - Driving/Inbound Ports           - Domain Model di inti
                 │                   - Driven/Outbound Ports           - Use Cases / App Layer
                 │                   - Adapters di batas terluar       - Interface Adapters / Infra
                 │                               │                               │
                 └───────────────────────┬───────┴───────────────────────────────┘
                                         ▼
                             [Modular Monolith Engine]
                             - Logical Bounded Contexts
                             - Strict Encapsulation (Package-Private)
                             - Intra-process Events / Contracts
                             - Deployability: Monolith | Scalability: Isolated
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Selama dekade 2000-an hingga pertengahan 2010-an, pendekatan standar pembangunan aplikasi enterprise bertumpu pada **Arsitektur N-Tier Tradisional** (sering kali direpresentasikan sebagai: *Presentation Layer* $\rightarrow$ *Business Logic Layer* $\rightarrow$ *Data Access Layer* $\rightarrow$ *Database*). 

Meskipun memisahkan komponen secara fungsional, arsitektur ini memiliki kelemahan fatal: **Arah dependensi kode sumber searah dengan alur kontrol fisik menuju basis data.** Konsekuensinya:
1.  **Database-Centric Modeling:** Desain entitas perangkat lunak sering kali merupakan pencerminan skema relasional tabel SQL (*anemic domain models* yang sarat dengan *getter/setter* tanpa *invariants*).
2.  **Kerapuhan terhadap Perubahan Eksternal:** Perubahan pada struktur tabel basis data, library ORM, atau API pihak ketiga secara berantai merusak *Data Access Layer*, merembes ke *Business Logic Layer*, hingga menyentuh *Presentation Layer*.
3.  **Kesulitan Pengujian (*Impaired Testability*):** Menjalankan unit test terhadap logika bisnis memerlukan dependensi aktif terhadap database atau mock yang sangat kompleks karena isolasi antarmuka yang lemah.

Sebagai reaksi ekstrem terhadap masalah ini, industri berayun ke arah **Microservices**. Namun, banyak organisasi terjebak dalam perangkap *Distributed Monolith*: latensi jaringan membengkak, koordinasi transaksi terdistribusi gagal (*dual-write/Saga hell*), dan kompleksitas operasional melumpuhkan produktivitas tim.

**Arsitektur Inverted (Ports & Adapters, Onion, Clean)** dan **Modular Monolith** hadir sebagai jawaban metodologis yang matang:
*   Membawa *business domain* ke pusat semesta perangkat lunak.
*   Mengisolasi total aturan bisnis dari *framework*, basis data, UI, dan perangkat eksternal melalui pembalikan dependensi (*Dependency Inversion*).
*   Menawarkan struktur modular terisolasi dalam satu proses deployment tunggal (*Modular Monolith*), menghasilkan sistem yang mudah diuji, murah dioperasikan, dan siap diekstrak menjadi microservices jika skala organisasi dan beban sistem memang menuntutnya.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Classic Layered Architecture (N-Tier)
Arsitektur ini mengatur kode ke dalam lapisan-lapisan horizontal. Setiap lapisan hanya bergantung pada lapisan di bawahnya secara berurutan.
*   **Presentation / UI:** Menerima input pengguna, merender tampilan, atau mendistribusikan HTTP Response.
*   **Business Logic Layer (BLL):** Melakukan validasi, orkestrasi aturan bisnis, dan kalkulasi.
*   **Data Access Layer (DAL):** Berkomunikasi langsung dengan SQL, file system, atau penyimpanan lain.
*   *Titik Kritis:* Lapisan atas transitif bergantung pada infrastruktur bawah ($UI \rightarrow BLL \rightarrow DAL$).

### 2. Ports and Adapters (Hexagonal Architecture)
Diciptakan oleh Alistair Cockburn pada tahun 2005. Arsitektur ini menolak pemikiran "lapisan atas dan bawah" dan menggantinya dengan "dalam (*inside*)" dan "luar (*outside*)".
*   **The Inside (Application Core):** Terdiri dari model domain dan use case logika bisnis murni. Inti ini tidak mengenal HTTP, gRPC, PostgreSQL, AWS S3, atau terminal CLI.
*   **Ports:** Batas (*boundary*) antarmuka abstrak.
    *   *Inbound / Driving Port:* Antarmuka yang mendefinisikan apa yang bisa dieksekusi dari luar terhadap inti aplikasi (misalnya: `PlaceOrderUseCase`).
    *   *Outbound / Driven Port:* Antarmuka yang mendefinisikan apa yang dibutuhkan inti aplikasi dari dunia luar (misalnya: `OrderRepositoryPort`, `PaymentGatewayPort`).
*   **Adapters:** Implementasi konkret dari atau terhadap Ports.
    *   *Driving Adapter:* Mengonversi trigger luar ke pemanggilan Inbound Port (misalnya: REST Controller, Message Consumer, CLI).
    *   *Driven Adapter:* Mengimplementasikan Outbound Port menggunakan teknologi konkret (misalnya: `PostgresOrderRepository`, `StripePaymentAdapter`).

### 3. Onion Architecture
Diusulkan oleh Jeffrey Palermo pada tahun 2008. Menekankan konsentrisitas dependensi:
*   Semua kode bergantung ke arah dalam (ke arah *Core*).
*   Lapisan terdalam adalah **Domain Model** (Entities & Value Objects).
*   Mengelilingi Domain Model adalah **Domain Services**.
*   Di luarnya terdapat **Application Services** (Use Cases).
*   Lapisan paling luar adalah **Infrastructure**, UI, dan Test.

### 4. Clean Architecture
Dipopulerkan oleh Robert C. Martin ("Uncle Bob") pada tahun 2012, menyatukan Hexagonal, Onion, dan DCI (*Data, Context, and Interaction*):
*   **The Dependency Rule:** Kode di lingkaran dalam tidak boleh tahu apa pun tentang kode di lingkaran luar. Nama kelas, fungsi, variabel, atau format data di lapisan luar tidak boleh disebut di lapisan dalam.
*   Struktur lingkaran konsentris dari dalam ke luar:
    1.  *Entities* (Enterprise Business Rules)
    2.  *Use Cases* (Application Business Rules)
    3.  *Interface Adapters* (Controllers, Gateways, Presenters)
    4.  *Frameworks & Drivers* (Database, Web Frameworks, Devices)

### 5. Modular Monolith
Pola arsitektur di mana keseluruhan sistem berjalan dalam **satu runtime dan satu basis kode (single deployable unit)**, namun dibagi secara kaku ke dalam modul-modul fungsional independen (*Bounded Contexts*).
*   Setiap modul memiliki batasan arsitektur internal sendiri (sering kali menerapkan Clean/Hexagonal di dalam masing-masing modul).
*   Akses antar-modul dibatasi secara ketat melalui *Public API/Contract* atau *Domain Events*.
*   Akses lintas-modul secara langsung ke basis data modul lain dilarang keras.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### Mekanisme Dependency Inversion pada Pemisahan Batas
Kunci utama dari Hexagonal, Onion, dan Clean Architecture adalah eksploitasi penuh dari **Dependency Inversion Principle (DIP)**:
> *"Modul tingkat tinggi tidak boleh bergantung pada modul tingkat rendah. Keduanya harus bergantung pada abstraksi."*

```
Alur Eksekusi (Runtime Control Flow):
[HTTP Request] ──> [Controller] ──> [Use Case Interactor] ──> [Repository Impl] ──> [Database Engine]

Arah Dependensi Kode Sumber (Compile-time Source Code Dependency):
[Controller] ──> [Use Case Port (Interface)] 
                          ▲
                          │
             [Use Case Interactor (Core Logic)] ──> [Repository Port (Interface)]
                                                              ▲
                                                              │
                                                [Postgres Repository Impl]
```

1.  **Runtime Control Flow:** Permintaan masuk dari pengguna, diarahkan oleh *Controller*, diproses oleh *Use Case*, yang kemudian memanggil *Repository* untuk menyimpan state ke basis data fisik.
2.  **Source Code Dependency:** 
    *   *Controller* bergantung pada antarmuka *Use Case* (Inbound Port).
    *   *Use Case Interactor* mengimplementasikan antarmuka *Use Case* dan bergantung **hanya** pada abstraksi antarmuka *Repository* (Outbound Port).
    *   *Postgres Repository Implementation* berada di lapisan luar infrastruktur dan bergantung pada abstraksi antarmuka *Repository* di lapisan dalam.
    *   Dengan demikian, **arah ketergantungan kode sumber dibalik 180 derajat** melawan alur kontrol eksekusi. Lapisan Domain dan Use Case sama sekali tidak memiliki dependensi terhadap driver database atau ORM.

### Boundary Crossing: DTO vs Domain Entities
Masalah umum dalam arsitektur berorientasi lapisan adalah kebocoran representasi internal ke luar (*data leakage*). Mekanisme transmisi data diatur dengan aturan isolasi:
*   Data masuk melintasi batas sistem dikonversi menjadi **Request Data Transfer Object (DTO)** atau **Command Object**.
*   Use Case memvalidasi command, lalu menginstansiasi atau memuat **Domain Entity**.
*   Domain Entity mengeksekusi aturan bisnis invariant murni.
*   Data keluar dipetakan dari Domain Entity menjadi **Response DTO** atau dikirim melalui **Presenter Interface** sebelum keluar ke Presenter/Controller. Domain Entity tidak pernah diekspos langsung ke lapisan Web API.

### Isolasi Modul pada Modular Monolith
Dalam Modular Monolith, partisi sistem diatur berdasarkan kemampuan bisnis (*Business Capabilities*), bukan fungsi teknis (*Layer-by-layer across the entire app*).
*   **Vertical Slices:** Modul `Billing`, Modul `Inventory`, Modul `Identity`.
*   Setiap modul memiliki struktur direktori internal mandiri.
*   Ketergantungan antar-modul hanya diizinkan via kontrak publik yang didefinisikan secara eksplisit (misalnya `BillingModuleApi`), sedangkan kelas-kelas internal dilindungi menggunakan mekanisme visibilitas bahasa (*package-private* di Java/Kotlin, `internal` di C#, atau pembatasan file ekspor di TypeScript/Go via *linter*).
*   Komunikasi antar-modul yang tidak memerlukan konsistensi seketika (*immediate consistency*) dialirkan melalui **In-Memory Event Dispatcher** untuk memutus keterikatan temporal.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Perbandingan Struktural: N-Tier Tradisional vs Clean / Hexagonal

```
===============================================================================
A. DATABASE-CENTRIC N-TIER (Ketergantungan Mengalir ke Bawah)
===============================================================================

       ┌────────────────────────┐
       │   Presentation Layer   │  (Web, API, CLI)
       └───────────┬────────────┘
                   │ Mengimpor / Bergantung Pada
                   ▼
       ┌────────────────────────┐
       │  Business Logic Layer  │  (Domain Services, "Business" Logic)
       └───────────┬────────────┘
                   │ Mengimpor / Bergantung Pada
                   ▼
       ┌────────────────────────┐
       │   Data Access Layer    │  (Entity Framework, Hibernate, SQL Client)
       └───────────┬────────────┘
                   │ Mengakses Fisik
                   ▼
       ┌────────────────────────┐
       │    Database Storage    │
       └────────────────────────┘

===============================================================================
B. CLEAN / HEXAGONAL ARCHITECTURE (Ketergantungan Mengalir ke Inti)
===============================================================================

                 INFRASTRUCTURE & ADAPTERS (LAPISAN LUAR)
 ┌───────────────────────────────────────────────────────────────────────────┐
 │                                                                           │
 │   [DRIVING ADAPTERS]                                                      │
 │   ┌────────────────┐                                                      │
 │   │ REST / gRPC    │───┐                                                  │
 │   │ Controllers    │   │                                                  │
 │   └────────────────┘   │                                                  │
 │   ┌────────────────┐   │                                                  │
 │   │ Event Consumer │───┼──────────┐                                       │
 │   └────────────────┘   │          │                                       │
 │                        │          │                                       │
 │                        ▼          ▼                                       │
 │              APPLICATION CORE (LAPISAN DALAM)                             │
 │             ┌───────────────────────────────────────────────┐             │
 │             │                                               │             │
 │             │   [INBOUND / DRIVING PORTS]                   │             │
 │             │   - CheckoutUseCaseInterface                  │             │
 │             │   - CancelOrderUseCaseInterface               │             │
 │             │                          ▲                    │             │
 │             │                          │ Mengimplementasikan│             │
 │             │   [USE CASE SERVICES / INTERACTORS]           │             │
 │             │   - Mengorkestrasi Entity                     │             │
 │             │   - Menjamin Transaction Boundaries           │             │
 │             │                          │                    │             │
 │             │                          ▼                    │             │
 │             │   [DOMAIN MODEL (ENTITIES & VOs)]             │             │
 │             │   - Order, OrderItem, Money                   │             │
 │             │   - Invariants & Business Calculations        │             │
 │             │                          ▲                    │             │
 │             │                          │ Mengonsumsi        │             │
 │             │   [OUTBOUND / DRIVEN PORTS]                   │             │
 │             │   - OrderRepositoryPort (Interface)           │             │
 │             │   - PaymentGatewayPort (Interface)            │             │
 │             │   - NotificationPort (Interface)              │             │
 │             │                          ▲                    │             │
 │             └──────────────────────────┼────────────────────┘             │
 │                                        │                                  │
 │   [DRIVEN ADAPTERS]                    │ Mengimplementasikan              │
 │   ┌────────────────────────────────────┴───────────────┐                  │
 │   │ PostgresOrderRepository (Menggunakan ORM / Driver) │                  │
 │   └────────────────────────────────────────────────────┘                  │
 │   ┌────────────────────────────────────────────────────┐                  │
 │   │ StripePaymentGatewayAdapter (HTTP Client SDK)      │                  │
 │   └────────────────────────────────────────────────────┘                  │
 │   ┌────────────────────────────────────────────────────┐                  │
 │   │ SmtpEmailNotificationAdapter (Mail Service)        │                  │
 │   └────────────────────────────────────────────────────┘                  │
 │                                                                           │
 └───────────────────────────────────────────────────────────────────────────┘
```

### 2. Arsitektur Modular Monolith: Boundary Enforcement

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ MODULAR MONOLITH BOUNDARY RUNTIME                                                      │
│                                                                                        │
│  ┌────────────────────────────────────────┐   ┌─────────────────────────────────────┐  │
│  │ MODULE: ORDERING                       │   │ MODULE: INVENTORY                   │  │
│  │                                        │   │                                     │  │
│  │  [Public API / Facade]                 │   │  [Public API / Facade]              │  │
│  │  └── OrderingModuleService (Contract)  │   │  └── InventoryModuleService         │  │
│  │                                        │   │                                     │  │
│  │  [Internal Core (Protected)]           │   │  [Internal Core (Protected)]        │  │
│  │  ├── Domain Entities (Order, LineItem) │   │  ├── Domain Entities (StockItem)    │  │
│  │  ├── Use Cases (CreateOrder, Cancel)   │   │  ├── Use Cases (ReserveStock)       │  │
│  │  └── Internal Ports & Adapters         │   │  └── Internal Ports & Adapters      │  │
│  │                                        │   │                                     │  │
│  │  [Private Data Source Isolation]       │   │  [Private Data Source Isolation]    │  │
│  │  └── 'orders' schema tables only       │   │  └── 'inventory' schema tables only │  │
│  └───────────────────┬────────────────────┘   └──────────────────▲──────────────────┘  │
│                      │                                           │                     │
│                      │ 1. Publishes "OrderPlacedDomainEvent"     │                     │
│                      ▼                                           │                     │
│           ┌─────────────────────────────────────────────┐        │                     │
│           │       IN-PROCESS ASYNCHRONOUS EVENT BUS     │────────┘                     │
│           │   (Decoupled Module-to-Module Interaction)  │  2. Subscribes & Reserves    │
│           └─────────────────────────────────────────────┘     Stock Async              │
│                                                                                        │
│  TIDAK DIIZINKAN:                                                                      │
│  [Ordering Core] ───X (Direct Class Import) ───> [Inventory Internal Entities]         │
│  [Ordering Adapters] ───X (Direct SQL Join) ───> [inventory.stock_items Table]         │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah ilustrasi minimalis penerapan prinsip *Ports and Adapters* dalam TypeScript, mendemonstrasikan bagaimana domain diisolasi sepenuhnya dari infrastruktur.

### 1. Domain Model & Outbound Port (Lapisan Inti)
```typescript
// Core Domain Entity (Murni tanpa library)
export class Account {
  constructor(
    public readonly id: string,
    private balance: number
  ) {}

  public debit(amount: number): void {
    if (amount <= 0) {
      throw new Error("Nominal debit harus bernilai positif.");
    }
    if (this.balance < amount) {
      throw new Error("Saldo tidak mencukupi untuk melakukan transaksi.");
    }
    this.balance -= amount;
  }

  public getBalance(): number {
    return this.balance;
  }
}

// Outbound Port (Interface abstraksi penyimpanan)
export interface AccountRepositoryPort {
  findById(id: string): Promise<Account | null>;
  save(account: Account): Promise<void>;
}
```

### 2. Inbound Port & Use Case Interactor (Lapisan Aplikasi)
```typescript
// Inbound Port (Contract Use Case)
export interface TransferFundsCommand {
  accountId: string;
  amount: number;
}

export interface TransferFundsUseCase {
  execute(command: TransferFundsCommand): Promise<void>;
}

// Use Case Implementation
export class TransferFundsService implements TransferFundsUseCase {
  constructor(private readonly accountRepo: AccountRepositoryPort) {}

  async execute(command: TransferFundsCommand): Promise<void> {
    const account = await this.accountRepo.findById(command.accountId);
    if (!account) {
      throw new Error(`Akun dengan ID ${command.accountId} tidak ditemukan.`);
    }

    account.debit(command.amount);
    await this.accountRepo.save(account);
  }
}
```

### 3. Driven Adapter (Lapisan Infrastruktur)
```typescript
// Driven Adapter konkret (In-Memory atau Database)
export class InMemoryAccountRepositoryAdapter implements AccountRepositoryPort {
  private database: Map<string, Account> = new Map();

  async findById(id: string): Promise<Account | null> {
    const account = this.database.get(id);
    return account ? new Account(account.id, account.getBalance()) : null;
  }

  async save(account: Account): Promise<void> {
    this.database.set(account.id, account);
  }
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Pada skenario enterprise nyata, kita akan mengimplementasikan skenario checkout pada e-commerce dengan paradigma **Hexagonal Architecture** di dalam struktur modul mandiri.

### Struktur Proyek
```
src/modules/order/
├── domain/
│   ├── entities/
│   │   └── order.entity.ts
│   ├── value-objects/
│   │   └── money.vo.ts
│   └── exceptions/
│       └── order-domain.exception.ts
├── application/
│   ├── ports/
│   │   ├── inbound/
│   │   │   └── checkout.use-case.ts
│   │   └── outbound/
│   │       ├── order-repository.port.ts
│   │       └── payment-gateway.port.ts
│   └── use-cases/
│       └── checkout.service.ts
└── infrastructure/
    ├── adapters/
    │   ├── driving/
    │   │   └── order-http.controller.ts
    │   └── driven/
    │       ├── postgres-order-repository.adapter.ts
    │       └── stripe-payment-gateway.adapter.ts
    └── mappers/
        └── order-persistence.mapper.ts
```

### 1. Domain Entities & Value Objects (Zero Dependencies)

```typescript
// src/modules/order/domain/value-objects/money.vo.ts
export class Money {
  constructor(public readonly amount: number, public readonly currency: string) {
    if (amount < 0) {
      throw new Error("Nominal uang tidak boleh bernilai negatif.");
    }
    if (!currency || currency.length !== 3) {
      throw new Error("Kode mata uang ISO 3 huruf tidak valid.");
    }
  }

  public add(other: Money): Money {
    if (this.currency !== other.currency) {
      throw new Error("Operasi penambahan gagal: Perbedaan mata uang.");
    }
    return new Money(this.amount + other.amount, this.currency);
  }

  public equals(other: Money): boolean {
    return this.amount === other.amount && this.currency === other.currency;
  }
}

// src/modules/order/domain/entities/order.entity.ts
export type OrderStatus = "PENDING" | "PAID" | "CANCELLED";

export class OrderItem {
  constructor(
    public readonly productId: string,
    public readonly unitPrice: Money,
    public readonly quantity: number
  ) {
    if (quantity <= 0) throw new Error("Kuantitas produk minimal harus 1.");
  }

  public calculateSubtotal(): Money {
    return new Money(this.unitPrice.amount * this.quantity, this.unitPrice.currency);
  }
}

export class Order {
  private constructor(
    public readonly id: string,
    public readonly customerId: string,
    private readonly items: OrderItem[],
    private status: OrderStatus
  ) {}

  public static create(id: string, customerId: string, items: OrderItem[]): Order {
    if (!items || items.length === 0) {
      throw new Error("Pesanan tidak dapat dibuat tanpa minimal satu item.");
    }
    return new Order(id, customerId, items, "PENDING");
  }

  public static restore(id: string, customerId: string, items: OrderItem[], status: OrderStatus): Order {
    return new Order(id, customerId, items, status);
  }

  public calculateTotal(): Money {
    const baseCurrency = this.items[0].unitPrice.currency;
    return this.items.reduce(
      (acc, item) => acc.add(item.calculateSubtotal()),
      new Money(0, baseCurrency)
    );
  }

  public markAsPaid(): void {
    if (this.status !== "PENDING") {
      throw new Error(`Transisi status tidak valid dari ${this.status} ke PAID.`);
    }
    this.status = "PAID";
  }

  public getStatus(): OrderStatus {
    return this.status;
  }

  public getItems(): ReadonlyArray<OrderItem> {
    return [...this.items];
  }
}
```

### 2. Outbound Ports (Kontrak Infrastruktur)

```typescript
// src/modules/order/application/ports/outbound/order-repository.port.ts
import { Order } from "../../../domain/entities/order.entity";

export interface OrderRepositoryPort {
  save(order: Order): Promise<void>;
  findById(id: string): Promise<Order | null>;
}

// src/modules/order/application/ports/outbound/payment-gateway.port.ts
import { Money } from "../../../domain/value-objects/money.vo";

export interface ChargeRequest {
  orderId: string;
  amount: Money;
  paymentToken: string;
}

export interface PaymentGatewayPort {
  charge(request: ChargeRequest): Promise<{ transactionId: string; success: boolean }>;
}
```

### 3. Inbound Port & Use Case Interactor

```typescript
// src/modules/order/application/ports/inbound/checkout.use-case.ts
export interface CheckoutItemDTO {
  productId: string;
  unitPrice: number;
  currency: string;
  quantity: number;
}

export interface CheckoutCommand {
  orderId: string;
  customerId: string;
  items: CheckoutItemDTO[];
  paymentToken: string;
}

export interface CheckoutResultDTO {
  orderId: string;
  status: string;
  totalAmount: number;
  currency: string;
  transactionId: string;
}

export interface CheckoutUseCase {
  execute(command: CheckoutCommand): Promise<CheckoutResultDTO>;
}

// src/modules/order/application/use-cases/checkout.service.ts
import { CheckoutUseCase, CheckoutCommand, CheckoutResultDTO } from "../ports/inbound/checkout.use-case";
import { OrderRepositoryPort } from "../ports/outbound/order-repository.port";
import { PaymentGatewayPort } from "../ports/outbound/payment-gateway.port";
import { Order, OrderItem } from "../../domain/entities/order.entity";
import { Money } from "../../domain/value-objects/money.vo";

export class CheckoutService implements CheckoutUseCase {
  constructor(
    private readonly orderRepository: OrderRepositoryPort,
    private readonly paymentGateway: PaymentGatewayPort
  ) {}

  public async execute(command: CheckoutCommand): Promise<CheckoutResultDTO> {
    // 1. Validasi & Map Input DTO ke Domain Objects
    const domainItems = command.items.map(
      (item) => new OrderItem(item.productId, new Money(item.unitPrice, item.currency), item.quantity)
    );

    const order = Order.create(command.orderId, command.customerId, domainItems);
    const totalAmount = order.calculateTotal();

    // 2. Eksekusi Pembayaran via Outbound Port
    const paymentResult = await this.paymentGateway.charge({
      orderId: order.id,
      amount: totalAmount,
      paymentToken: command.paymentToken,
    });

    if (!paymentResult.success) {
      throw new Error(`Transaksi pembayaran gagal untuk Order ID: ${order.id}`);
    }

    // 3. Mutasi State Domain & Persistensi
    order.markAsPaid();
    await this.orderRepository.save(order);

    // 4. Transformasikan hasil ke Response DTO
    return {
      orderId: order.id,
      status: order.getStatus(),
      totalAmount: totalAmount.amount,
      currency: totalAmount.currency,
      transactionId: paymentResult.transactionId,
    };
  }
}
```

### 4. Driven Adapters (Postgres & External Stripe Mock)

```typescript
// src/modules/order/infrastructure/adapters/driven/postgres-order-repository.adapter.ts
import { OrderRepositoryPort } from "../../../application/ports/outbound/order-repository.port";
import { Order, OrderItem } from "../../../domain/entities/order.entity";
import { Money } from "../../../domain/value-objects/money.vo";

// Simulasi Database Client
interface DatabaseClient {
  query(sql: string, params: any[]): Promise<any>;
}

export class PostgresOrderRepositoryAdapter implements OrderRepositoryPort {
  constructor(private readonly db: DatabaseClient) {}

  public async save(order: Order): Promise<void> {
    // Memetakan Entity Domain ke format skema tabel Database (Persistence Mapping)
    const sqlOrder = `
      INSERT INTO orders (id, customer_id, status, total_amount, currency)
      VALUES ($1, $2, $3, $4, $5)
      ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status;
    `;
    const total = order.calculateTotal();
    await this.db.query(sqlOrder, [order.id, order.customerId, order.getStatus(), total.amount, total.currency]);

    for (const item of order.getItems()) {
      const sqlItem = `
        INSERT INTO order_items (order_id, product_id, price, currency, quantity)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT DO NOTHING;
      `;
      await this.db.query(sqlItem, [
        order.id,
        item.productId,
        item.unitPrice.amount,
        item.unitPrice.currency,
        item.quantity,
      ]);
    }
  }

  public async findById(id: string): Promise<Order | null> {
    const rawOrder = await this.db.query("SELECT * FROM orders WHERE id = $1", [id]);
    if (!rawOrder || rawOrder.length === 0) return null;

    const rawItems = await this.db.query("SELECT * FROM order_items WHERE order_id = $1", [id]);
    const domainItems = rawItems.map(
      (r: any) => new OrderItem(r.product_id, new Money(parseFloat(r.price), r.currency), r.quantity)
    );

    return Order.restore(rawOrder[0].id, rawOrder[0].customer_id, domainItems, rawOrder[0].status);
  }
}
```

```typescript
// src/modules/order/infrastructure/adapters/driven/stripe-payment-gateway.adapter.ts
import { PaymentGatewayPort, ChargeRequest } from "../../../application/ports/outbound/payment-gateway.port";

export class StripePaymentGatewayAdapter implements PaymentGatewayPort {
  constructor(private readonly apiKey: string) {}

  public async charge(request: ChargeRequest): Promise<{ transactionId: string; success: boolean }> {
    // Di dunia nyata: Memanggil library Stripe SDK / Axios POST ke api.stripe.com
    if (!this.apiKey) throw new Error("Stripe API Key belum terkonfigurasi.");
    
    // Asumsi transaksi berhasil jika token valid
    const isSuccess = !request.paymentToken.includes("fail");
    return {
      transactionId: `ch_stripe_${Math.random().toString(36).substring(7)}`,
      success: isSuccess,
    };
  }
}
```

### 5. Driving Adapter (REST HTTP Controller)

```typescript
// src/modules/order/infrastructure/adapters/driving/order-http.controller.ts
import { CheckoutUseCase } from "../../../application/ports/inbound/checkout.use-case";

// Tipikal antarmuka request/response dari Framework (Express/Fastify)
export interface HttpRequest {
  body: any;
}
export interface HttpResponse {
  status(code: number): this;
  json(data: any): void;
}

export class OrderHttpController {
  constructor(private readonly checkoutUseCase: CheckoutUseCase) {}

  public async handleCheckout(req: HttpRequest, res: HttpResponse): Promise<void> {
    try {
      const payload = req.body;

      // Parsing & Delegasi langsung ke Inbound Port
      const result = await this.checkoutUseCase.execute({
        orderId: payload.order_id,
        customerId: payload.customer_id,
        paymentToken: payload.payment_token,
        items: payload.items.map((i: any) => ({
          productId: i.product_id,
          unitPrice: i.price,
          currency: i.currency,
          quantity: i.qty,
        })),
      });

      res.status(201).json({
        message: "Pesanan berhasil diproses.",
        data: result,
      });
    } catch (error: any) {
      res.status(400).json({
        error: error.message || "Terjadi kesalahan internal pada server.",
      });
    }
  }
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Mengadopsi Ports and Adapters, Onion, Clean Architecture, maupun Modular Monolith bukanlah keputusan bebas biaya. Perhatikan matriks komparasi berikut:

| Parameter Evaluasi | N-Tier Tradisional | Clean / Hexagonal Architecture | Modular Monolith | Microservices |
| :--- | :--- | :--- | :--- | :--- |
| **Kurva Pembelajaran & Overhead Awal** | Sangat Rendah | Tinggi (Banyak abstraksi & pemetaan tipe data) | Sedang - Tinggi (Disiplin isolasi domain ketat) | Sangat Tinggi (DevOps, Observability, Network) |
| **Isolasi Logika Bisnis** | Rendah (Bocor ke ORM & SQL) | Sempurna (100% Core decoupled) | Sempurna per Modul | Sempurna per Service |
| **Biaya Kognitif (Boilerplate)** | Minimal (Langsung CRUD) | Signifikan (DTO, Mapper, Port, Adapter) | Moderat | Tinggi |
| **Kecepatan Pengujian Unit** | Lambat (Ketergantungan ke DB mock) | Sangat Cepat (Cukup mock memory ports) | Sangat Cepat | Kompleks (Contract & End-to-End) |
| **Kompleksitas Operasional (Infra)** | Minimal | Minimal | Minimal (Single Deployable Unit) | Sangat Rumit |
| **Risiko Vendor Lock-in (Framework/DB)** | Sangat Rentan | Hampir Nol di Core Domain | Hampir Nol di Core Modul | Bervariasi |

### Kapan Menggunakan Clean / Hexagonal Architecture?
*   Aplikasi memiliki domain bisnis yang kompleks (*rich domain model*), regulasi ketat, serta siklus hidup panjang (5–10+ tahun).
*   Sistem sering dihadapkan pada perubahan integrasi pihak ketiga (misalnya: migrasi payment provider dari Stripe ke Midtrans, atau migrasi sistem antrean pesan).
*   Kebutuhan pengujian unit (*pure unit testing*) dengan cakupan tinggi tanpa overhead menjalankan kontainer database.

### Kapan Pola Ini Berubah Menjadi Anti-Pattern?
*   **Simple CRUD / Data Entry App:** Jika sistem hanya bertindak sebagai antarmuka input formulir ke baris tabel tanpa kalkulasi atau aturan invariant domain yang kompleks, mengimplementasikan Clean Architecture menghasilkan fenomena *Pass-Through Architecture* (Controller memanggil Use Case yang hanya memanggil Repository tanpa memproses apa pun). Gunakan pola *Transaction Script* sederhana.

---

## SEKSI 11 — BEST PRACTICES

1.  **Strict Rule of Independence:** Pastikan direktori `domain` tidak mengimpor pustaka eksternal apa pun selain modul core bahasa pemrograman standar. Jangan izinkan dekorator ORM (seperti TypeORM, Hibernate, Prisma, Entity Framework) masuk mencemari entitas domain.
2.  **DTO Mapping di Titik Perbatasan:** Buat objek mapper eksplisit di dalam Adapter (Driving dan Driven). Entitas domain tidak boleh keluar menuju HTTP Response, dan entitas ORM database tidak boleh masuk melampaui Driven Adapter.
3.  **Boundary Enforcement dengan Linter Otomatis:** Pasang *Architectural Fitness Function* menggunakan pustaka seperti **Dependency-Cruiser** (Node.js), **ArchUnit** (Java/Kotlin), atau **NetArchTest** (.NET) dalam pipeline CI/CD untuk memastikan dependensi terlarang memicu *build error*.
4.  **Desain Modul Berdasarkan Bounded Context:** Dalam Modular Monolith, partisi modul jangan dilakukan secara horizontal (misalnya: folder `controllers`, `services`, `repositories`), melainkan secara vertikal fungsional (misalnya: `modules/ordering`, `modules/inventory`, `modules/billing`).
5.  **Gunakan In-Process Events untuk Dekopling Antar-Modul:** Jika Modul A memerlukan tindakan dari Modul B, jangan panggil method internal Modul B secara langsung. Gunakan event internal (`OrderPlacedEvent`) yang dikonsumsi oleh subscriber Modul B secara asinkron.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. The Anemic Domain Disguised as Clean Architecture
**Gejala:** Entitas domain hanya berupa sekumpulan *property* publik dengan getter dan setter kosong (`get/set`), sedangkan seluruh logika ditaruh di Use Case Interactor.
**Bahaya:** Hilangnya enkapsulasi (*leaky abstraction*). Status entitas dapat diubah secara ilegal dari mana saja tanpa validasi invariant domain.
**Solusi:** Terapkan *Rich Domain Model*. Tempatkan validasi state dan kalkulasi bisnis langsung di dalam entitas domain atau value object.

### 2. Dependency Inversion Fake-Out (Interface Segregation Illusion)
**Gejala:** Membuat interface `OrderRepository` di Core, tetapi method-nya mengembalikan tipe bawaan database library (misalnya: `Promise<TypeOrmQueryRunner>` atau `MongooseDocument`).
**Bahaya:** Lapisan Core tetap secara transitif terikat kuat pada library eksternal.
**Solusi:** Interface Port di Core hanya boleh menerima dan mengembalikan tipe data primitif, Value Objects, atau Domain Entities asli.

### 3. Modular Monolith: "Cross-Module Database Join"
**Gejala:** Developer dari modul `Ordering` menulis SQL query yang melakukan `INNER JOIN` langsung ke tabel `inventory_items` milik modul `Inventory`.
**Bahaya:** Merusak total batas independensi modul. Refactoring skema basis data `Inventory` akan merusak modul `Ordering` secara tak terduga.
**Solusi:** Isolasi skema database per modul (pisahkan schema SQL atau pisahkan table prefix). Dapatkan data lintas-modul melalui *Public Interface contract* atau replikasi lokal via *Domain Events*.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Refactoring Legacy Layered ke Hexagonal Architecture
*   **Skenario:** Anda diberikan potongan kode Express.js di mana sebuah endpoint `/users/register` membaca data `req.body`, memvalidasi hashing password menggunakan `bcrypt`, memanggil `pg.Pool.query("INSERT INTO users...")`, lalu mengirim email menggunakan `nodemailer` langsung dalam satu fungsi controller monolitik 70 baris.
*   **Tugas:** Dekonstruksi kode tersebut menjadi:
    1.  Entitas Domain `User` dengan validasi kekuatan password dan aturan status user.
    2.  Use Case `RegisterUserUseCase` (Inbound Port & Implementation).
    3.  Outbound Ports: `UserRepositoryPort`, `NotificationServicePort`.
    4.  Implementasi Adapters untuk PostgreSQL dan Nodemailer.

### Latihan 2: Konfigurasi Architectural Guardrail (Dependency-Cruiser)
*   **Tugas:** Buat file aturan konfigurasi `.dependency-cruiser.js` pada repositori modul Anda dengan kriteria validasi:
    1.  File di dalam direktori `domain` **DILARANG KERAS** mengimpor apa pun dari `infrastructure` maupun `application`.
    2.  File di dalam direktori `application` dilarang mengimpor apa pun dari `infrastructure`.
    3.  File di dalam modul `modules/order` dilarang mengimpor file privat di dalam `modules/billing` (hanya boleh mengimpor dari `modules/billing/public-api.ts`).

### Latihan 3: Implementasi In-Memory Event Dispatcher untuk Modular Monolith
*   **Tugas:**
    1.  Rancang `DomainEventPublisher` internal yang mengekspos metode `publish<T>(event: T): void` dan `subscribe<T>(eventName: string, handler: (event: T) => Promise<void>): void`.
    2.  Ketika `CheckoutService` di Modul Ordering berhasil memproses pesanan, terbitkan `OrderPlacedEvent`.
    3.  Buat subscriber pada modul `Inventory` yang menangkap event tersebut dan secara otomatis memotong stok barang secara asinkron tanpa memblokir alur balik HTTP Controller Ordering.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Apa perbedaan konseptual paling mendasar antara Inbound (Driving) Port dan Outbound (Driven) Port pada Hexagonal Architecture?**
   * A. Inbound Port menangani koneksi database, Outbound Port menangani UI.
   * B. Inbound Port mendefinisikan antarmuka use case yang dipanggil oleh dunia luar ke dalam inti, sedangkan Outbound Port mendefinisikan antarmuka yang dipanggil oleh inti ke layanan/infrastruktur luar.
   * C. Inbound Port selalu asinkron, Outbound Port selalu sinkron.
   * D. Inbound Port menggunakan protokol gRPC, Outbound Port menggunakan HTTP REST.

2. **Mengapa Robert C. Martin ("Uncle Bob") melarang entitas Domain mengimpor anotasi/decorator langsung dari framework ORM seperti TypeORM atau JPA/Hibernate?**
   * A. Karena decorator ORM membuat proses kompilasi kode menjadi 50% lebih lambat.
   * B. Karena anotasi tersebut menghubungkan entitas domain secara permanen dengan skema relasional tabel dan framework pihak ketiga tertentu, melanggar batas kemurnian domain.
   * C. Karena ORM tidak mendukung operasi matematika di domain.
   * D. Karena kode JavaScript tidak dapat mengeksekusi decorator di level production.

3. **Di mana implementasi kelas adapter konkret (seperti `PostgresRepository` atau `StripePaymentService`) harus diletakkan dalam Clean Architecture?**
   * A. Di lapisan Entities paling dalam.
   * B. Di lapisan Use Cases.
   * C. Di lapisan terluar (Frameworks, Drivers & Infrastructure / Interface Adapters).
   * D. Di modul utilitas bersama (*shared kernel*).

4. **Dalam skenario Modular Monolith, pendekatan mana yang paling tepat jika modul 'Invoicing' membutuhkan informasi profil pelanggan dari modul 'Customer'?**
   * A. Modul Invoicing menjalankan query langsung ke tabel basis data `customers`.
   * B. Mengimpor entitas privat `Customer` langsung ke dalam Use Case Invoicing.
   * C. Memanggil `CustomerPublicService` yang didefinisikan sebagai antarmuka kontrak publik modul Customer, atau mendengarkan event perubahan data profil pelanggan secara lokal.
   * D. Menggabungkan kedua modul tersebut menjadi satu folder tanpa batas.

5. **Apa yang dimaksud dengan "Architectural Fitness Function"?**
   * A. Uji beban performa CPU dan RAM server saat arsitektur dijalankan.
   * B. Tes otomatis yang mengevaluasi apakah arsitektur kode mematuhi batasan struktural dan aturan dependensi yang telah disepakati.
   * C. Perhitungan jumlah baris kode (LOC) dalam sebuah Use Case.
   * D. Pengujian UI menggunakan Selenium atau Cypress.

---

### Kunci Jawaban & Rasional

1. **Jawaban: B.** Inbound Port dioperasikan oleh Driving Adapters (seperti Controller) untuk memerintahkan Use Case bekerja. Outbound Port dipanggil oleh Use Case Interactor untuk mengeksekusi kebutuhan eksternal (Database, Mailer, External API) yang diimplementasikan oleh Driven Adapters.
2. **Jawaban: B.** Entitas domain harus merupakan representasi aturan bisnis murni (*Plain Old Objects*). Memasukkan anotasi ORM mengikat logika bisnis ke mekanisme persistensi tabel, yang berarti perubahan skema tabel atau library database berisiko merusak model domain.
3. **Jawaban: C.** Driven Adapters merupakan detail infrastruktur teknis konkret yang berada di lapisan terluar. Inti aplikasi hanya menyediakan abstraksi (interface), dan adapter mengimplementasikan interface tersebut di perimeter sistem.
4. **Jawaban: C.** Prinsip utama Modular Monolith adalah isolasi data dan logika. Membaca tabel modul lain secara langsung atau mengimpor kelas internal merusak batas enkapsulasi (*leaky boundaries*). Akses harus melalui Public API modul terkait atau melalui konsumsi event.
5. **Jawaban: B.** Architectural Fitness Functions (misalnya via ArchUnit, Dependency-Cruiser) adalah pengujian otomatis yang dijalankan pada proses CI/CD untuk memastikan pengembang tidak melanggar hierarki dependensi (contoh: memvalidasi bahwa domain tidak pernah mengimpor layer UI atau Database).

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1.  **Buku & Karya Akademik:**
    *   Martin, Robert C. (2017). *Clean Architecture: A Craftsman's Guide to Software Structure and Design*. Prentice Hall.
    *   Palermo, Jeffrey (2008). *The Onion Architecture*. Serial Esai Arsitektur.
    *   Cockburn, Alistair (2005). *Hexagonal Architecture (Ports and Adapters)*. Alistair.Cockburn.us.
    *   Millett, Scott & Tune, Nick (2015). *Patterns, Principles, and Practices of Domain-Driven Design*. John Wiley & Sons.
    *   Fowler, Martin (2002). *Patterns of Enterprise Application Architecture*. Addison-Wesley.
2.  **Artikel & Panduan Industri:**
    *   Lilienthal, Carola (2019). *Sustainable Software Architecture: Analyze and Reduce Technical Debt*. dpunkt.verlag.
    *   Kamil Grzybek (2020). *Modular Monolith: A Primer*. Seri Repositori GitHub Panduan Praktis Modular Monolith.
3.  **Peralatan Enkapsulasi & Analisis Statis:**
    *   *ArchUnit (Java/Kotlin)*: `https://www.archunit.org/`
    *   *Dependency-Cruiser (JavaScript/TypeScript)*: `https://github.com/sverweij/dependency-cruiser`
    *   *NetArchTest (.NET)*: `https://github.com/BenMorris/NetArchTest`

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

*   **Pembalikan Dependensi adalah Landasan:** Arsitektur modern membalikkan ketergantungan kode sumber. Runtime eksekusi tetap mengalir dari luar ke dalam lalu keluar lagi, tetapi kode sumber selalu mengarah ke lapisan konsentris terdalam: **Domain**.
*   **Pemisahan Inside vs Outside:** Inti aplikasi (*Domain & Use Cases*) bertindak sebagai *Inside* yang tidak peduli pada protokol komunikasi (HTTP, Message Broker) maupun media penyimpanan (Postgres, Mongo, File). Seluruh faktor eksternal ini dianggap sebagai *Outside* yang dihubungkan melalui *Ports & Adapters*.
*   **Boundary Crossing Membutuhkan Pemetaan Data Eksplisit:** Mengalirkan data melewati batas lapisan mewajibkan konversi: Request $\rightarrow$ DTO $\rightarrow$ Domain Entity $\rightarrow$ Response DTO. Kebocoran satu objek ORM ke presentasi merusak seluruh garansi isolasi arsitektur.
*   **Modular Monolith Sebagai Solusi Pragmatis Terdepan:** Sebelum meloncat ke jurang kompleksitas operasional Microservices, rancang sistem sebagai Modular Monolith. Sistem terbagi rapi ke dalam *bounded contexts*, terisolasi secara data dan logika, dapat diuji secara independen, namun tetap beroperasi dalam unit deployment tunggal yang efisien.
*   **Penegakan Aturan Arsitektur Wajib Otomatis:** Dokumentasi arsitektur tertulis akan basi tanpa penegakan. Gunakan *Architectural Fitness Functions* (linter dependensi) dalam CI/CD pipeline untuk menggagalkan merge commit yang melanggar batas lapisan arsitektur.

---

## SEKSI 17 — GLOSARIUM

*   **Inbound Port (Driving Port):** Antarmuka Use Case yang mengekspos kapabilitas aplikasi ke lapisan luar (contoh: antarmuka eksekusi perintah pendaftaran user).
*   **Outbound Port (Driven Port):** Antarmuka yang didefinisikan oleh aplikasi inti untuk mengabstraksikan layanan eksternal yang diperlukannya (contoh: interface repository atau payment gateway).
*   **Driving Adapter:** Komponen di perimeter luar yang menangkap pemicu dari luar (HTTP request, CLI command, pesan RabbitMQ) dan memanggil Inbound Port.
*   **Driven Adapter:** Komponen di perimeter luar yang mengimplementasikan Outbound Port menggunakan pustaka atau driver teknologi konkret (contoh: adaptor Prisma, adaptor Mailgun).
*   **Modular Monolith:** Struktur aplikasi monolitik yang dibagi menjadi modul-modul independen berdasarkan konteks bisnis, dengan pembatasan akses kode internal antar-modul secara eksplisit.
*   **Architectural Fitness Function:** Uji otomatis berbasis kode untuk memvalidasi bahwa integritas struktural arsitektur sistem (seperti arah dependensi) tidak dilanggar selama siklus pengembangan.
*   **Anemic Domain Model:** Anti-pattern di mana objek domain hanya berisi data/properti tanpa logika bisnis, membiarkan status entitas rentan dimanipulasi secara tidak aman dari luar.
*   **Bounded Context:** Batasan eksplisit dalam arsitektur domain di mana model domain tertentu berlaku secara terisolasi tanpa benturan makna dengan model di domain lain.

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Tantangan Utama Peserta:** Peserta sering merasa penulisan Ports, Adapters, DTO, dan Mappers menghasilkan "kode berulang-ulang" (*boilerplate* berlebih) dibandingkan pendekatan direct ORM.
*   **Pedoman Fasilitasi:** Arahkan peserta melalui simulasi kasus: *"Bagaimana jika perusahaan memutuskan mengganti database relasional ke Document store, atau mengganti provider SMS ke vendor baru besok pagi?"* Tunjukkan secara visual bagaimana pada Clean Architecture modifikasi hanya terjadi di lapisan luar (*Driven Adapter*) tanpa menyentuh satu baris pun di level logika bisnis (*Core Use Case*).
*   **Simulasi Hands-on:** Pastikan pada sesi praktik peserta benar-benar mencoba membuat tes unit untuk `CheckoutService` dengan melempar *Fake Adapter in-memory*, dan buktikan bahwa tes dapat tuntas dalam hitungan milidetik tanpa perlu menyalakan kontainer database lokal.
*   **Penekanan Konsep:** Jangan biarkan peserta terjebak dalam perdebatan terminologi antara Onion vs Hexagonal vs Clean. Tekankan bahwa ketiganya membagikan prinsip fundamental yang sama: **Pembalikan Dependensi (DIP) dan Isolasi Logika Inti**.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **v1.0.0 (Maret 2026):**
    *   Rilis awal materi kurikulum arsitektur enterprise standar.
    *   Diagram komprehensif ASCII untuk N-Tier, Hexagonal, Clean, dan Modular Monolith.
    *   Implementasi kode end-to-end berbasis TypeScript modern (Strict Domain Invariants, Ports, Adapters, dan Web Controller).
    *   Penyusunan modul latihan terstruktur dan fitness function guide.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya:** `ARCH-03-03 — Domain-Driven Design Strategic & Tactical Patterns`
*   **Modul Saat Ini:** `ARCH-04-01 — Arsitektur Moduler & Layered: Monolith Modern hingga Hexagonal`
*   **Modul Berikutnya:** `ARCH-04-02 — Event-Driven Architecture: Broker Topology, Choreography vs Orchestration, and Outbox Pattern`