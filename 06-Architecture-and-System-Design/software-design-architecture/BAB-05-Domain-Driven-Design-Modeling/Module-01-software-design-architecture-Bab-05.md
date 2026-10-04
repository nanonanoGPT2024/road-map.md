# Modul 01: Domain-Driven Design (DDD) — Strategic & Tactical Modeling

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `ARCH-06-05-01`
* **Nama Modul**: Domain-Driven Design: Strategic & Tactical Modeling (Entities, Value Objects, Aggregates, Domain Services, Repositories, Domain Events, Anti-Corruption Layer)
* **Kategori**: `06-Architecture-and-System-Design`
* **Tingkat Kesulitan**: Advanced
* **Prasyarat**: Pemahaman mendalam mengenai Object-Oriented Programming (OOP), SOLID Principles, Design Patterns (GoF), Clean Architecture/Hexagonal Architecture, Relational/NoSQL Persistence.
* **Perkiraan Waktu Penyelesaian**: 8–10 jam belajar mandiri dan praktik coding.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Mengonstruksi Strategic Boundary**: Memetakan domain bisnis kompleks ke dalam Subdomains (Core, Supporting, Generic), mendefinisikan *Bounded Contexts*, serta menyusun *Context Maps* yang mengeliminasi ambiguitas semantik.
2. **Mengisolasi Legacy via Anti-Corruption Layer (ACL)**: Mendesain adapter, translator, dan facade berlapis guna melindungi integritas model domain internal dari kontaminasi dependensi sistem eksternal atau warisan monolit (*legacy monolith*).
3. **Mengimplementasikan Taktikal DDD Secara Presisi**:
   * Membedakan dan mengimplementasikan *Entity* (berbasis identitas siklus hidup) dan *Value Object* (berbasis nilai struktural dan *immutability*).
   * Menetapkan batasan konsistensi transaksional (*transactional boundary*) menggunakan pola *Aggregate* dan mengekspos modifikasi status hanya melalui *Aggregate Root*.
4. **Mengeksekusi Domain Events & Event-Driven Decoupling**: Menghasilkan (*raise/record*) dan menyebarkan (*dispatch/publish*) *Domain Events* secara konsisten dengan memanfaatkan pola transaksional seperti *Transactional Outbox Pattern*.
5. **Mendesain Repositori dan Domain Services Berorientasi Domain**: Merancang repositori murni berbasis koleksi in-memory tanpa kebocoran detail infrastruktur ORM/SQL, serta mengekstrak logika domain yang melibatkan multi-aggregate ke dalam *Domain Services* tanpa mereduksi domain model menjadi *Anemic Domain Model*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       DOMAIN-DRIVEN DESIGN (DDD)
                                   |
         +-------------------------+-------------------------+
         |                                                   |
 [STRATEGIC DESIGN]                                  [TACTICAL DESIGN]
         |                                                   |
         +-- Ubiquitous Language                             +-- Value Objects (Immutability)
         |                                                   +-- Entities (Identity & Lifecycle)
         +-- Subdomains (Core, Generic, Supporting)          +-- Aggregates & Aggregate Roots
         |                                                   |   (Invariants & Transactional Boundary)
         +-- Bounded Contexts                                +-- Domain Services (Cross-Aggregate Logic)
         |                                                   +-- Repositories (Persistence Abstraction)
         +-- Context Mapping                                 +-- Domain Events (State-Change Side Effects)
                 |
                 +-- Anti-Corruption Layer (ACL)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

1. **Mengatasi Jebakan Model Anemik (*Anemic Domain Model*)**: Tanpa DDD, sebagian besar aplikasi korporat berdegenerasi menjadi tumpukan kelas "Entity" yang hanya berisi *getters/setters* (murni data transfer objects) yang dikendalikan oleh "Service Layer" berukuran ribuan baris kode (*procedural script*). Pola ini merusak enkapsulasi, membuat *invariants* (aturan bisnis validitas data) tidak terlindungi, dan menyulitkan pengujian mutasi status.
2. **Resolusi Ambiguitas Konseptual Bisnis**: Dalam perusahaan skala menengah-besar, istilah yang sama memiliki makna yang berbeda bagi departemen yang berbeda. Contoh: kata *"Account"* berarti akun autentikasi bagi tim Security, profil pelanggan bagi tim Marketing, dan buku besar kredit/debit bagi tim Accounting. Menerapkan model tunggal (*canonical data model*) di seluruh sistem menimbulkan kompleksitas komputasi dan politis yang rapuh. DDD memecah sistem berdasarkan *Bounded Contexts*.
3. **Penegakan Batas Konsistensi Data (*Consistency Boundaries*)**: Dalam arsitektur microservices dan sistem terdistribusi, kegagalan umum terjadi ketika batas transaksi dibuat terlalu besar (mengakibatkan *pessimistic lock contention*, kegagalan konkurensi, dan degradasi latensi) atau terlalu kecil (menyebabkan status data tidak konsisten). Konsep *Aggregate* memberikan panduan ketat: satu transaksi database hanya boleh memodifikasi satu instans *Aggregate Root*.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Strategic Design
Strategic Design adalah fase dekonstruksi domain masalah (*problem space*) dan pemetaan solusi teknis (*solution space*).

* **Ubiquitous Language**: Bahasa tunggal yang disepakati bersama oleh pengembang perangkat lunak dan para ahli domain bisnis (*Domain Experts*). Bahasa ini tercermin secara eksplisit pada nama kelas, nama fungsi, nama event, dan variabel dalam kode, tanpa terjemahan teknis buatan.
* **Subdomains**:
  * *Core Domain*: Diferensiator utama bisnis yang memberikan keunggulan kompetitif (misal: algoritma *dynamic pricing* pada ride-hailing).
  * *Supporting Domain*: Kompleksitas tambahan yang mendukung Core Domain tetapi bukan pembeda kompetitif (misal: sistem inventaris gudang kustom).
  * *Generic Domain*: Modul standar yang dapat dibeli atau dialihdayakan ke pustaka open-source/SaaS (misal: modul otentikasi OAuth2, sistem pemrosesan invoice umum).
* **Bounded Context**: Batasan eksplisit tempat model konseptual, terminologi, dan kode diterapkan secara konsisten. Satu kata bermakna tepat satu hal di dalam satu Bounded Context.
* **Context Mapping**: Pola integrasi antar-Bounded Context. Hubungannya mencakup: *Shared Kernel*, *Customer-Supplier*, *Conformist*, *Open Host Service (OHS)*, *Published Language (PL)*, dan *Anti-Corruption Layer (ACL)*.
* **Anti-Corruption Layer (ACL)**: Lapisan isolasi arsitektural yang menerjemahkan model dari subsistem eksternal ke model domain internal tanpa membiarkan semantik eksternal mengotori kode bersih internal.

### 2. Tactical Design
Tactical Design adalah seperangkat blok pembangun (*building blocks*) berbasis kode untuk merepresentasikan model domain di dalam Bounded Context.

* **Value Object (VO)**: Objek yang diidentifikasi murni berdasarkan atribut/nilainya, bukan identitas kontinunya. Bersifat *immutable* (tidak dapat diubah setelah dibuat). Mengganti VO berarti membuat instans baru. Dua VO dianggap ekuivalen jika seluruh nilainya sama.
* **Entity**: Objek yang memiliki identitas unik (*Unique Identity*) yang bertahan sepanjang waktu, melewati perubahan berbagai status/atributnya. Dua Entity dengan data atribut yang identik tetap dianggap berbeda jika ID-nya berbeda.
* **Aggregate & Aggregate Root (AR)**: Klaster Entity dan Value Object yang terikat dalam satu batas konsistensi transaksional. Aggregate Root adalah satu-satunya Entity induk di dalam klaster tersebut yang boleh diakses langsung oleh objek eksternal. Objek di luar klaster dilarang keras memegang referensi ke Entity internal di dalam Aggregate.
* **Domain Service**: Kelas logika domain murni yang mengeksekusi proses bisnis yang secara alami tidak cocok disematkan ke dalam satu Entity/VO tertentu (biasanya operasi komparasi, transformasi, atau koordinasi antar-Aggregate). Berbeda dengan *Application Service* yang mengurusi orkestrasi I/O, transaksi DB, dan otorisasi.
* **Repository**: Abstraksi koleksi (*collection-oriented interface*) yang mensimulasikan penyimpanan in-memory untuk Aggregate Root. Repositori bertugas mengambil dan menyimpan seluruh graf objek Aggregate Root dalam kondisi konsisten.
* **Domain Event**: Rekaman masa lalu yang mendokumentasikan kejadian signifikan dalam domain bisnis (`OrderPlaced`, `AccountOverdrawn`). Bersifat *immutable*, menggunakan penamaan waktu lampau (*past-tense*), dan memicu proses lain di dalam atau lintas-Bounded Context.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### Alur Eksekusi Taktikal DDD

```
[HTTP Request / Controller]
             |
             v
[Application Service] <--- Mengambil Aggregate via Repositori
       |           |
       |           +-------> [Domain Repository] ---> [Database Engine]
       v
[Aggregate Root] <--------- Mengeksekusi Invariant & Mutasi Status
       |
       +---> Menghasilkan [Domain Event] (tersimpan sementara di internal Aggregate)
       |
[Application Service] <--- Menyimpan Aggregate via Repositori
       |
       +---> [Domain Event Dispatcher] ---> Dispatched ke Bus/Outbox
```

1. **Permintaan Masuk**: Pengendali API (*Controller*) memvalidasi format data DTO mentah dan mendelegasikannya ke *Application Service*.
2. **Pengambilan Entitas**: *Application Service* meminta *Repository* memuat *Aggregate Root* berdasarkan ID.
3. **Eksekusi Aturan Bisnis**: *Application Service* memanggil metode pada *Aggregate Root*. Di dalam metode ini:
   * *Invariants* divalidasi. Jika melanggar aturan, eksepsi domain (*Domain Exception*) dilemparkan seketika.
   * State Aggregate dimutasi secara internal.
   * *Aggregate Root* mendaftarkan satu atau beberapa *Domain Events* ke koleksi internalnya.
4. **Persistensi**: *Application Service* memanggil `repository.save(aggregate)`. Transaksi atomik database memastikan status Aggregate dan rekaman Domain Event (jika menggunakan Outbox Pattern) tersimpan ke storage secara konsisten.
5. **Event Dispatching**: Event diteruskan ke *Domain Event Handler* internal (untuk koordinasi dalam Bounded Context yang sama) atau dipublikasikan ke Message Broker (Kafka/RabbitMQ) untuk Bounded Context lain.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Context Map: Integrasi E-Commerce & Legacy Fulfilment via ACL

```
+-------------------------------------------------------------------------------+
|                      ORDERING BOUNDED CONTEXT (Core)                          |
|                                                                               |
|  [Order Aggregate Root]                                                       |
|       |                                                                       |
|       +-- id: OrderId (VO)                                                    |
|       +-- customerId: CustomerId (VO)                                         |
|       +-- items: List<OrderItem> (Entity)                                     |
|       +-- totalAmount: Money (VO)                                             |
|       +-- status: OrderStatus (VO)                                            |
|                                                                               |
+-------------------------------------------------------------------------------+
                                      |
                         Domain Event: OrderPlacedEvent
                                      |
                                      v
+-------------------------------------------------------------------------------+
|                     FULFILMENT BOUNDED CONTEXT (Upstream)                     |
|                                                                               |
|  +-------------------------------------------------------------------------+  |
|  |                   ANTI-CORRUPTION LAYER (ACL)                           |  |
|  |                                                                         |  |
|  |  [OrderEventListener]                                                   |  |
|  |         | (Raw Event Data)                                              |  |
|  |         v                                                               |  |
|  |  [FulfilmentTranslator] ---> Mengonversi OrderPlacedEvent ke            |  |
|  |         |                    model internal LegacyDispatchPackage       |  |
|  |         v                                                               |  |
|  |  [LegacySystemAdapter] ---> Menghubungi Legacy Monolith RPC/SOAP Client |  |
|  +-------------------------------------------------------------------------+  |
|                                     |                                         |
|                                     v                                         |
|  [LEGACY WAREHOUSE LOGISTICS MONOLITH (Downstream)]                           |
|  Tables: T_WH_DISPATCH, T_PKG_LOG, WAREHOUSE_ITEM                            |
+-------------------------------------------------------------------------------+
```

### 2. Anatomi Aggregate Root dan Konsistensi Boundary

```
+-----------------------------------------------------------------------+
| AGGREGATE BOUNDARY (Order Aggregate)                                  |
|                                                                       |
|  +-----------------------------------------------------------------+  |
|  | PRIMARY ROOT: Order (Entity)                                    |  |
|  |   - ID: OrderId                                                 |  |
|  |   - Status: OrderStatus                                         |  |
|  |   - Version: Long (for Optimistic Locking)                      |  |
|  |                                                                 |  |
|  |   Operations:                                                   |  |
|  |     + addItem(productId, quantity, price)                       |  |
|  |     + cancel(reason)                                            |  |
|  |     + pay(paymentToken)                                         |  |
|  +-----------------------------------------------------------------+  |
|           |                                          |                |
|           | (1..n Encapsulated)                      | (References)   |
|           v                                          v                |
|  +-----------------------+                 +-----------------------+  |
|  | OrderLineItem (Entity)|                 | Money (Value Object)  |  |
|  |   - ID: LineItemId    |                 |   - amount: Decimal   |  |
|  |   - ProductId: VO     |                 |   - currency: String  |  |
|  |   - Quantity: Int     |                 +-----------------------+  |
|  |   - Subtotal: Money   |                                            |
|  +-----------------------+                                            |
+-----------------------------------------------------------------------+
        ^
        | AKSES DILUAR BOUNDARY DILARANG MERUJUK LANGSUNG KE OrderLineItem!
        | Akses eksternal WAJIB melalui kelas `Order`
[Client/App Service]
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Implementasi dasar Value Object murni yang menerapkan konsep immutability, self-validation, dan structural equality dalam TypeScript.

```typescript
// Value Object: Money
export class Money {
  private readonly _amount: number;
  private readonly _currency: string;

  constructor(amount: number, currency: string) {
    if (amount < 0) {
      throw new Error("Money amount cannot be negative.");
    }
    if (!currency || currency.length !== 3) {
      throw new Error("Currency code must be a valid 3-character ISO string.");
    }
    this._amount = Math.round(amount * 100) / 100; // Pembulatan 2 desimal
    this._currency = currency.toUpperCase();
    Object.freeze(this); // Memastikan imutabilitas pada level runtime Javascript
  }

  get amount(): number {
    return this._amount;
  }

  get currency(): string {
    return this._currency;
  }

  public add(other: Money): Money {
    this.assertSameCurrency(other);
    return new Money(this._amount + other._amount, this._currency);
  }

  public subtract(other: Money): Money {
    this.assertSameCurrency(other);
    if (this._amount < other._amount) {
      throw new Error("Resulting money cannot be negative.");
    }
    return new Money(this._amount - other._amount, this._currency);
  }

  public equals(other: Money): boolean {
    if (!other) return false;
    return this._amount === other.amount && this._currency === other.currency;
  }

  private assertSameCurrency(other: Money): void {
    if (this._currency !== other._currency) {
      throw new Error(`Currency mismatch: ${this._currency} vs ${other._currency}`);
    }
  }
}

// Uji coba ekualiti struktural
const priceA = new Money(150000, "IDR");
const priceB = new Money(150000, "IDR");
const priceC = new Money(200000, "IDR");

console.log(priceA.equals(priceB)); // Output: true (Meskipun instans memori berbeda)
console.log(priceA.equals(priceC)); // Output: false
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus Produksi: Pemodelan pesanan e-commerce dengan aggregate root yang merekam domain events, repositories interface, serta ACL translator untuk integrasi ke logistik lama.

### 1. Domain Event & Base Contract

```typescript
export interface DomainEvent {
  occurredOn: Date;
  aggregateId: string;
}

export class OrderPlacedEvent implements DomainEvent {
  public readonly occurredOn: Date;
  constructor(
    public readonly aggregateId: string,
    public readonly customerId: string,
    public readonly totalAmount: number,
    public readonly currency: string,
    public readonly items: Array<{ productId: string; quantity: number }>
  ) {
    this.occurredOn = new Date();
  }
}
```

### 2. Value Objects & Entities

```typescript
export class OrderId {
  constructor(private readonly value: string) {
    if (!value || value.trim().length === 0) {
      throw new Error("OrderId cannot be empty.");
    }
  }
  toString(): string { return this.value; }
  equals(other: OrderId): boolean { return this.value === other.value; }
}

export class OrderItem {
  constructor(
    private readonly _productId: string,
    private _quantity: number,
    private readonly _unitPrice: Money
  ) {
    if (_quantity <= 0) throw new Error("Quantity must be greater than zero.");
    this._productId = _productId;
    this._quantity = _quantity;
    this._unitPrice = _unitPrice;
  }

  get productId(): string { return this._productId; }
  get quantity(): number { return this._quantity; }
  get unitPrice(): Money { return this._unitPrice; }

  get subtotal(): Money {
    return new Money(this._unitPrice.amount * this._quantity, this._unitPrice.currency);
  }

  incrementQuantity(added: number): void {
    if (added <= 0) throw new Error("Increment value must be positive.");
    this._quantity += added;
  }
}
```

### 3. Aggregate Root (Penjaga Invariant Bisnis)

```typescript
export class Order {
  private readonly _id: OrderId;
  private readonly _customerId: string;
  private readonly _items: Map<string, OrderItem> = new Map();
  private _status: "DRAFT" | "SUBMITTED" | "PAID" | "CANCELLED";
  private _domainEvents: DomainEvent[] = [];

  constructor(id: OrderId, customerId: string) {
    this._id = id;
    this._customerId = customerId;
    this._status = "DRAFT";
  }

  get id(): OrderId { return this._id; }
  get status(): string { return this._status; }
  get domainEvents(): ReadonlyArray<DomainEvent> { return [...this._domainEvents]; }

  public clearDomainEvents(): void {
    this._domainEvents = [];
  }

  public addItem(productId: string, unitPrice: Money, quantity: number): void {
    if (this._status !== "DRAFT") {
      throw new Error("Cannot mutate order in non-DRAFT status.");
    }

    if (this._items.has(productId)) {
      this._items.get(productId)!.incrementQuantity(quantity);
    } else {
      this._items.set(productId, new OrderItem(productId, quantity, unitPrice));
    }
  }

  public calculateTotal(): Money {
    let total = new Money(0, "IDR");
    for (const item of this._items.values()) {
      total = total.add(item.subtotal);
    }
    return total;
  }

  public submitOrder(): void {
    // Invariant business rules:
    if (this._status !== "DRAFT") {
      throw new Error("Order has already been processed.");
    }
    if (this._items.size === 0) {
      throw new Error("Cannot submit an empty order.");
    }

    const total = this.calculateTotal();
    if (total.amount <= 0) {
      throw new Error("Order total must be greater than zero.");
    }

    this._status = "SUBMITTED";

    // Pendaftaran Domain Event
    const payloadItems = Array.from(this._items.values()).map(item => ({
      productId: item.productId,
      quantity: item.quantity
    }));

    this._domainEvents.push(
      new OrderPlacedEvent(
        this._id.toString(),
        this._customerId,
        total.amount,
        total.currency,
        payloadItems
      )
    );
  }
}
```

### 4. Repository Contract & Anti-Corruption Layer (ACL)

```typescript
// Repository Interface murni domain (bebas dari ORM/SQL)
export interface OrderRepository {
  findById(id: OrderId): Promise<Order | null>;
  save(order: Order): Promise<void>;
}

// Model Subsistem Warisan (Legacy API Payload)
interface LegacySoapShippingRequest {
  ORDER_NUM: string;
  RECIPIENT_REF: string;
  TOTAL_VAL: number;
  CURR_TYPE: string;
  SKU_ENTRIES: Array<{ SKU: string; PCS: number }>;
}

// Legacy Logistics Monolith Adapter
class LegacyLogisticsRpcClient {
  public executeSoapCall(action: string, payload: LegacySoapShippingRequest): void {
    // Simulasi integrasi SOAP API kuno
    console.log(`[LEGACY SYSTEM] Executed ${action} for ORDER_NUM: ${payload.ORDER_NUM}`);
  }
}

// Anti-Corruption Layer: Mencegah model Legacy bocor ke Core Order Context
export class FulfilmentAntiCorruptionLayer {
  constructor(private readonly legacyClient: LegacyLogisticsRpcClient) {}

  public onOrderPlaced(event: OrderPlacedEvent): void {
    // Mengonversi Domain Model/Event ke Format Subsistem Legacy
    const legacyPayload: LegacySoapShippingRequest = this.translateToLegacy(event);
    
    // Memanggil API dengan isolasi kegagalan
    this.legacyClient.executeSoapCall("CREATE_CARGO_DISPATCH_ORDER", legacyPayload);
  }

  private translateToLegacy(event: OrderPlacedEvent): LegacySoapShippingRequest {
    return {
      ORDER_NUM: event.aggregateId,
      RECIPIENT_REF: event.customerId,
      TOTAL_VAL: event.totalAmount,
      CURR_TYPE: event.currency,
      SKU_ENTRIES: event.items.map(i => ({
        SKU: i.productId,
        PCS: i.quantity
      }))
    };
  }
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi | Pendekatan DDD Murni (Rich Domain) | Pendekatan Anemic / CRUD Pattern |
|---|---|---|
| **Kurva Pembelajaran & Waktu Rilis** | Tinggi. Membutuhkan kolaborasi erat dengan Domain Experts dan waktu perancangan boundary. | Rendah. Pengembang dapat langsung membuat tabel DB dan API endpoint dalam hitungan jam. |
| **Beban Overhead Kode (*Boilerplate*)** | Signifikan. Banyak Value Objects, Mappers, Interface Repositori, dan pembungkus tipe eksplisit. | Minimal. Memanfaatkan fitur auto-mapping ORM (ActiveRecord) langsung ke Web DTO. |
| **Integritas Bisnis (*Invariants Protection*)** | Ekstrem. Tidak ada cara memanipulasi status selain melewati Aggregate Root yang terkontrol. | Rendah. Logika bisnis rawan tersebar di puluhan Controller/Services, memicu inkonsistensi data. |
| **Kesesuaian Kompleksitas** | Sangat cocok untuk domain kompleks dengan aturan bisnis yang sering berubah secara dinamis. | Cocok murni untuk aplikasi CRUD standar (misal: sistem entri inventaris sederhana). |
| **Kinerja & Latensi Query** | Memerlukan pemisahan CQRS karena Aggregate Root mengambil seluruh klaster entitas yang dapat membebani I/O. | Optimal untuk read query sederhana karena dapat langsung menulis query `SELECT` join bebas. |

---

## SEKSI 11 — BEST PRACTICES

1. **Aturan 1: Modifikasi Tepat Satu Aggregate per Transaksi Database**: Jika suatu aksi bisnis menuntut mutasi di dua Aggregate berbeda, jangan gunakan transaksi ACID terdistribusi lintas Aggregate. Gunakan pendekatan *Eventual Consistency* via *Domain Events*.
2. **Aturan 2: Desain Aggregate Berukuran Kecil (*Small Aggregates*)**: Jangan memasukkan seluruh relasi entitas ke dalam satu Aggregate raksasa. Buat Aggregate sekecil mungkin yang hanya mencakup data yang mutlak harus konsisten secara atomik (*immediate consistency*). Entitas lain cukup dirujuk via ID-nya (*Identity Reference*), bukan memegang referensi objek langsung.
3. **Validasi Sejak Dini di Konstruktor Value Object**: Jangan biarkan Value Object berada dalam kondisi invalid sekalipun. Terapkan validasi ketat (*guard clauses*) langsung di blok konstruktor atau factory method statis.
4. **Jaga Aggregates Tetap Bebas dari Infrastruktur (*Persistence Ignorant*)**: Jangan mengimpor decorator ORM (seperti `@Entity()` TypeORM atau Hibernate annotations) langsung ke dalam class Domain Entity jika hal itu merusak prinsip isolasi murni domain layer. Gunakan *Data Mappers* terpisah untuk memetakan domain model ke database entity.
5. **Bahasa di Kode Harus Mencerminkan Bahasa Bisnis**: Hindari penamaan generic seperti `updateStatus()`, `processData()`, atau `setCancelled(true)`. Gunakan verba ekspresif seperti `rejectDueToFraud()`, `cancelByCustomer()`, atau `reopenTicket()`.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Jebakan "Getters/Setters Hell" (Anemic Model)**:
   * *Kesalahan*: Menyediakan method `public setQuantity(val)` pada sub-entitas, sehingga layer controller/service luar bisa langsung mengubah data tanpa mengeksekusi validasi aturan bisnis menyeluruh di Aggregate Root.
   * *Perbaikan*: Enkapsulasi seluruh mutasi. Sediakan method yang menyatakan *intent* bisnis pada Aggregate Root, dan buat setters bersifat private.
2. **Aggregate Raksasa (*Mega-Aggregate*)**:
   * *Kesalahan*: Menjadikan `Customer` sebagai Aggregate Root yang memuat seluruh riwayat `List<Order>`, dan setiap `Order` memuat seluruh riwayat `List<Payment>`. Saat customer memiliki 10.000 pesanan, pemanggilan `customerRepository.findById()` menyebabkan degradasi memori dan kegagalan transaksi (*optimistic concurrency collision*).
   * *Perbaikan*: Putus referensi objek langsung. Ubah menjadi `Order` berdiri sebagai Aggregate terpisah yang hanya menyimpan `customerId: CustomerId`.
3. **Mengacaukan Domain Service dengan Application Service**:
   * *Kesalahan*: Memasukkan pemanggilan database, parsing HTTP header, pengiriman email SMTP, atau logging framework ke dalam *Domain Service*.
   * *Perbaikan*: *Domain Service* hanya memproses logika domain murni (misal: validasi kalkulasi bunga gabungan lintas akun). Segala I/O, transaksi DB, dan protokol jaringan wajib diisolasi di *Application Service*.
4. **Kebocoran Model Eksternal Tanpa ACL**:
   * *Kesalahan*: Membaca JSON respons mentah dari payment gateway pihak ketiga (misal: format API Stripe/Xendit) langsung di tengah-tengah logika domain `Order`.
   * *Perbaikan*: Bangun Anti-Corruption Layer yang memetakan format vendor luar tersebut menjadi Value Object domain internal yang terisolasi.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Soal: Sistem Dompet Digital FinTech (E-Wallet)

Rancanglah Bounded Context Dompet Digital dengan batasan fungsional berikut:

#### Kebutuhan Fungsional & Aturan Invariant
1. Sebuah `Wallet` bertindak sebagai *Aggregate Root*. Setiap `Wallet` memiliki identitas unik `WalletId`, dimiliki oleh `UserId`, memiliki saldo `Balance` (Value Object bertipe `Money`), dan status (`ACTIVE`, `FROZEN`).
2. Aturan Invariant:
   * Penarikan uang (*withdraw*) tidak boleh melebihi saldo saat ini.
   * Dompet yang berstatus `FROZEN` dilarang melakukan transaksi debit maupun kredit.
   * Setiap penarikan atau penyetoran harus mencatat transaksi internal `TransactionRecord` (Entity di dalam batas Aggregate).
   * Saldo minimum sebuah wallet aktif adalah nol (dilarang bernilai minus).
3. Jika penarikan berhasil, hasilkan domain event `WalletDebitedEvent`.

#### Tugas Anda:
1. Implementasikan Value Object `Money` dan `WalletId`.
2. Implementasikan Aggregate Root `Wallet` beserta method `deposit()`, `withdraw()`, dan `freeze()`.
3. Demonstrasikan pelemparan eksepsi domain jika invariant dilanggar saat saldo tidak mencukupi atau dompet dalam status `FROZEN`.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Apa perbedaan mendasar antara *Entity* dan *Value Object*?**
   * *Jawaban*: Entity didefinisikan oleh identitas unik yang konsisten sepanjang siklus hidupnya (meskipun atribut nilainya berubah), sedangkan Value Object diidentifikasi murni oleh komposisi nilainya, bersifat *immutable*, dan tidak memiliki identitas terpisah.

2. **Mengapa modifikasi data pada entitas internal Aggregate tidak boleh dipanggil langsung dari luar Aggregate Boundary?**
   * *Jawaban*: Karena modifikasi langsung akan melewati *invariants* (aturan konsistensi bisnis) yang dijaga oleh Aggregate Root, sehingga memicu inkonsistensi status dan perusakan status valid graf objek tersebut.

3. **Kapan sebuah logika harus ditempatkan di *Domain Service* alih-alih di dalam *Aggregate Root*?**
   * *Jawaban*: Ketika operasi bisnis tersebut secara inheren melibatkan kalkulasi atau interaksi multi-Aggregate secara setara, atau ketika meletakkan logika tersebut pada salah satu Aggregate akan merusak pemodelan domain alami (*unnatural responsibility coupling*).

4. **Bagaimana Anti-Corruption Layer (ACL) melindungi integritas arsitektur Bounded Context kita?**
   * *Jawaban*: ACL bertindak sebagai penerjemah dua arah (*translator*) dan pembatas isolasi. ACL mengonversi model data, skema, dan idiom dari sistem luar (upstream) menjadi representasi domain internal yang bersih dan kohesif (downstream), mencegah kontaminasi istilah dan dependensi liar.

5. **Mengapa disarankan untuk hanya mereferensikan Aggregate lain menggunakan identitas ID-nya daripada referensi objek langsung (*Direct Object Reference*)?**
   * *Jawaban*: Untuk membatasi batas transaksi (*transaction boundary*), mencegah konsumsi memori berlebih saat deserialisasi graf data, mengurangi konflik penguncian konkurensi (*locking contention*), dan mempermudah pemisahan penyimpanan lintas microservices secara independen.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku**:
  * *Domain-Driven Design: Tackling Complexity in the Heart of Software* — Eric Evans (Buku Biru asli, rujukan utama konsep Ubiquitous Language & Strategic Design).
  * *Implementing Domain-Driven Design* — Vaughn Vernon (Buku Merah, implementasi teknis paling komprehensif untuk arsitek software).
  * *Domain-Driven Design Distilled* — Vaughn Vernon (Panduan ringkas untuk pengenalan cepat tingkat tim).
* **Makalah & Pola Desain Terkait**:
  * Martin Fowler: *Anemic Domain Model* (https://martinfowler.com/bliki/AnemicDomainModel.html)
  * Microsoft .NET Guides: *Tackling Business Complexity in a Microservice with DDD and CQRS Patterns*.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

* Strategic Design berfokus pada pembagian sistem besar menjadi beberapa **Bounded Contexts** yang otonom dengan batasan bahasa seragam (**Ubiquitous Language**), menghindari pembuatan model terpusat tunggal yang monolitik.
* **Anti-Corruption Layer (ACL)** adalah komponen krusial dalam Context Mapping yang menjamin domain baru tidak tercemar oleh skema kuno dari sistem legasi eksternal.
* Tactical Design menyediakan abstraksi internal: **Value Objects** untuk konsep nilai tanpa identitas, **Entities** untuk kontinuitas beridentitas, dan **Aggregates** sebagai kluster atomik penjaga aturan konsistensi data.
* Repositori hanya mengekspos pemuatan dan penyimpanan pada tingkatan **Aggregate Root**, menjaga batas transaksi tetap kecil, terisolasi, dan aman untuk sistem terdistribusi.

---

## SEKSI 17 — GLOSARIUM

* **Aggregate Root (AR)**: Entitas sentral yang menjadi gerbang utama (*gateway*) suatu klaster objek; objek luar dilarang merujuk entitas dalam selain melewati AR ini.
* **Anti-Corruption Layer (ACL)**: Pola adaptasi struktural untuk mengisolasi subsistem dari dependensi semantik luar.
* **Bounded Context**: Batasan konseptual eksplisit tempat model data dan aturan bisnis tertentu berlaku secara definitif.
* **Domain Event**: Pernyataan faktual mengenai peristiwa penting yang telah terjadi dalam domain bisnis di masa lalu.
* **Invariant**: Aturan bisnis atau batasan validitas logika yang harus selalu bernilai benar (*true*) sepanjang masa hidup objek.
* **Optimistic Concurrency Control**: Strategi manajemen konkurensi (biasanya menggunakan nomor versi atau cap waktu) untuk mencegah penimpaan data tanpa penahanan *lock* database yang lama.
* **Ubiquitous Language**: Kosakata bersama yang digunakan secara konsisten oleh seluruh anggota tim teknis dan domain expert.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Poin Penekanan**:
  * Tekankan bahwa DDD bukanlah tentang menggunakan *framework* tertentu. Ini murni mengenai struktur kode dan permodelan kognitif bisnis.
  * Mahasiswa sering terjebak membuat Aggregate yang terlalu besar karena terbiasa dengan relasi database relational (Foreign Key cascading). Ingatkan aturan: satu transaksi = satu mutasi aggregate.
* **Saran Diskusi Kelas**:
  * Tunjukkan sebuah kelas Entity JPA/TypeORM warisan yang penuh dengan `@Getter`, `@Setter`, dan tanpa konstruktor. Ajak peserta mengidentifikasi berapa banyak aturan invariant yang bisa ditembus secara sengaja maupun tidak sengaja oleh layer Controller.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi**: 1.0.0
* **Tanggal Rilis**: 2025-02-15
* **Author**: Senior Technical Curriculum Architect
* **Catatan Perubahan**:
  * Rilis inisial materi Strategic & Tactical Modeling DDD standar korporat.
  * Penambahan implementasi TypeScript lengkap untuk Value Object, Entity, Aggregate Root, Domain Event, dan ACL.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `ARCH-06-04-03` — *Hexagonal Architecture, Onion Architecture, and Ports & Adapters*
* **Modul Berikutnya**: `ARCH-06-05-02` — *CQRS (Command Query Responsibility Segregation) and Event Sourcing Architectures*
* **Repositori Kurikulum Utama**: `06-Architecture-and-System-Design`