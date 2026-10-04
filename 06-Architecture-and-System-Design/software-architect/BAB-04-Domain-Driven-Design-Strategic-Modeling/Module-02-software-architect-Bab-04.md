# BAB 04: Domain-Driven Design (Strategic Modeling)
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda sebagai Principal/Staff Software Architect diharapkan mampu:

1. **Merancang Boundary Konteks Lanjutan**: Mengidentifikasi batas-batas otonom (*Bounded Contexts*) secara presisi menggunakan analisis linguistik semantik, siklus hidup invarian, dan interaksi *subdomain* (Core, Supporting, Generic).
2. **Menguasai Integrasi Context Mapping**: Mengimplementasikan pola-pola integrasi strategis: *Anti-Corruption Layer (ACL)*, *Open Host Service (OHS) / Published Language (PL)*, *Shared Kernel (SK)*, *Customer-Supplier (CS)*, dan *Conformist (CF)* pada level kode dan topologi jaringan.
3. **Mendesain Transisi Event-Driven Antar-Konteks**: Memisahkan secara tegas antara *Domain Event* internal (privat/taktikal) dan *Integration Event* publik (kontrak strategis eksternal) menggunakan *Transactional Outbox Pattern* dan skema evolutif (Protobuf/Avro/JSON Schema).
4. **Menyelaraskan Conway’s Law & Team Topologies**: Mengorganisasi struktur tim lintas fungsi (*Stream-Aligned*, *Platform*, *Complicated Subsystem*, *Enabling*) yang selaras 1:1 dengan kepemilikan *Bounded Context* guna meminimalkan biaya koordinasi kognitif organisasi.
5. **Mengevaluasi Trade-off Arsitektural Produksi**: Menilai dampak latensi, konsistensi data (*strong* vs *eventual consistency*), partisi jaringan, kompleksitas deployment, serta beban operasional saat menentukan batas modular monolit versus *microservices*.

---

### 2. Prerequisite

Sebelum mempelajari materi ini, Anda wajib menguasai:
- **Konsep Dasar DDD Strategis (Modul 01)**: Definisi *Ubiquitous Language*, Subdomain classification (Core, Generic, Supporting), dan pemahaman konseptual awal Bounded Context.
- **Enterprise Distributed Systems**: Pola komunikasi Asynchronous (Message Brokers/Event Streaming: Apache Kafka, RabbitMQ), RESTful API, dan gRPC/Protobuf.
- **Transaksional Lanjutan**: *Two-Phase Commit (2PC)* limitations, *ACID vs BASE*, dan *Saga Pattern (Choreography & Orchestration)*.
- **Design Patterns**: *Adapter Pattern*, *Facade Pattern*, *Translator/Mapper Pattern*, *Repository Pattern*.

---

### 3. Concept & Internal Architecture (Mendalam)

Strategic Domain-Driven Design bukan sekadar teknik analisis bisnis, melainkan disiplin rekayasa sistem yang membatasi ambiguitas semantik model domain di dalam perimeter komputasi yang terisolasi.

```
+---------------------------------------------------------------------------------------+
|                                    BUSINESS DOMAIN                                    |
+---------------------------------------------------------------------------------------+
     |                                   |                                   |
     v                                   v                                   v
+-----------------------+   +-----------------------+   +-----------------------+
|     CORE DOMAIN       |   |   SUPPORTING DOMAIN   |   |    GENERIC DOMAIN     |
| (Diferensiasi Bisnis, |   | (Komplementer, Custom |   | (Solusi Komoditas,    |
|  Kompleksitas Tinggi) |   |  Build, Spesifik)     |   |  SaaS / Off-the-Shelf)|
+-----------------------+   +-----------------------+   +-----------------------+
     |                                   |                                   |
     +-----------------------------------+-----------------------------------+
                                         |
                                         v
                         MODELING BOUNDARY DELINEATION
                                         |
     +-----------------------------------+-----------------------------------+
     |                                                                       |
     v                                                                       v
+---------------------------------------+   +---------------------------------------+
|       BOUNDED CONTEXT: ORDERING       |   |       BOUNDED CONTEXT: BILLING        |
|                                       |   |                                       |
| Ubiquitous Language:                  |   | Ubiquitous Language:                  |
| - "Order" (Item, Total, Status, Addr) |   | - "Invoice" (LineItem, Tax, DueDate)  |
| - "Customer" (Buyer Identity, Cart)   |   | - "Debtor" (CreditLimit, Balance)     |
|                                       |   |                                       |
| +-----------------------------------+ |   | +-----------------------------------+ |
| |          Domain Model             | |   | |          Domain Model             | |
| +-----------------------------------+ |   | +-----------------------------------+ |
|                   |                   |   |                   ^                   |
|                   v                   |   |                   |                   |
|       [Outbox / Integration Event]    |   |       [Anti-Corruption Layer]         |
+-------------------|-------------------+   +-------------------|-------------------+
                    |                                           |
                    +================ Kafka Topic ==============+
                               (Published Language)
```

#### 3.1. Anatomi Leksikal dan Semantik Bounded Context
Sebuah Bounded Context menetapkan batas teritorial di mana model perangkat lunak berlaku secara konsisten. Masalah terbesar pada sistem enterprise adalah polisemik (*polysemy*)—satu istilah memiliki makna berbeda dalam konteks berbeda:
- Dalam konteks **Ordering**: `Customer` adalah pihak yang memilih barang, memiliki alamat pengiriman, dan menerapkan kupon diskon.
- Dalam konteks **Risk & Fraud**: `Customer` adalah entitas dengan sidik jari perangkat, skor reputasi IP, dan jejak riwayat transaksi mencurigakan.
- Dalam konteks **Billing**: `Customer` adalah subjek pajak (*Tax Entity*) dengan Nomor Pokok Wajib Pajak dan alamat penagihan legal.

Memaksakan satu entitas database tunggal `Customer` untuk seluruh konteks akan menghasilkan *God Class*, ketergantungan antartim yang berbelit, dan fragmentasi logika validasi.

#### 3.2. Taksonomi Context Mapping Terapan
Hubungan antara dua Bounded Context selalu memiliki orientasi kekuasaan teknis dan kendali domain (*Upstream/Downstream dynamic*):
- **Upstream ($U$)**: Penyedia data/layanan. Perubahan pada upstream memengaruhi downstream.
- **Downstream ($D$)**: Konsumen data/layanan. Bergantung pada upstream.

```
       [ Upstream: U ]  ------------------------>  [ Downstream: D ]
       (Menentukan API/Kontrak)                    (Menerima Dampak Perubahan)
```

1. **Shared Kernel ($SK$)**:
   - Dua konteks berbagi sebagian model domain dan basis kode/basis data secara langsung.
   - *Risiko*: Kopling tinggi. Setiap modifikasi pada *shared kernel* mewajibkan kedua tim melakukan pengujian dan deployment terkoordinasi.
2. **Customer-Supplier ($C/S$)**:
   - Upstream bertindak sebagai *Supplier*, Downstream bertindak sebagai *Customer*. Kebutuhan Downstream dinegosiasikan ke Upstream dan dimasukkan ke dalam *backlog* Upstream secara prioritas.
3. **Conformist ($CF$)**:
   - Downstream sepenuhnya tunduk pada model data Upstream tanpa melakukan transformasi. Terjadi ketika Upstream adalah sistem monopoli internal atau tim Downstream tidak memiliki daya tawar (leverage).
4. **Anti-Corruption Layer ($ACL$)**:
   - Downstream membangun lapisan isolasi (berisi *Translators*, *Adapters*, dan *Facades*) untuk menerjemahkan model asing dari Upstream ke dalam model domain internal Downstream yang murni (*pristine*).
5. **Open Host Service / Published Language ($OHS/PL$)**:
   - Upstream menyediakan protokol akses publik yang stabil (misalnya REST/JSON atau gRPC/Protobuf) dengan dokumentasi formal dan versioning ketat, memperlakukan downstream sebagai konsumen independen.
6. **Separate Ways ($SW$)**:
   - Integrasi dihentikan karena biaya integrasi lebih tinggi daripada membangun kembali solusi fungsional secara terpisah di masing-masing konteks.

---

### 4. Why & What

| Dimensi | Pendekatan Kanonikal Monolitik (Legacy) | Strategic Domain-Driven Design (Modern) |
| :--- | :--- | :--- |
| **Batas Data** | *Shared Database*, skema global tunggal yang diakses semua modul. | *Decoupled Data Store*, tiap Bounded Context memiliki persistensi privat terisolasi. |
| **Struktur Model** | Skema tabel generik (*one-size-fits-all*), ribuan baris kode per kelas entitas. | Model semantik lokal terisolasi; atribut model hanya relevan dengan invariant konteks tersebut. |
| **Strategi Integrasi** | Direct Foreign Keys, pemanggilan prosedur basis data (Triggers/Stored Procedures). | Kontrak eksplisit melalui REST/gRPC (*OHS*) atau Event Streaming (*Integration Events*) dengan *ACL*. |
| **Dampak Perubahan** | *Ripple effect*; modifikasi satu kolom tabel dapat merusak puluhan subsistem lain. | *Blast radius* terlokalisasi dalam batas konteks; implementasi internal bebas di-refactor. |
| **Topologi Tim** | Tim horizontal berbasis teknologi (Frontend, Backend, DBA) yang terfragmentasi. | *Stream-aligned teams* yang memiliki konteks spesifik dari domain logic hingga infrastruktur. |

---

### 5. How (Workflow Detail)

Untuk menerapkan dekomposisi berbasis Strategic DDD pada sistem skala besar, ikuti siklus metodologi berikut:

```
[Tahap 1: Domain Discovery]
       |
       v
  EventStorming (Big Picture) -> Temukan Domain Events & Business Invariants
       |
       v
[Tahap 2: Bounded Context Delimitation]
       |
       +---> Leksikal: Apakah ada definisi kata ganda (Polysemy)?
       +---> Transaksional: Di mana batas konsistensi ACID yang absolut?
       +---> Organisasional: Siapa tim yang mengelola domain ini secara independen?
       |
       v
[Tahap 3: Context Mapping Synthesis]
       |
       +---> Definisikan relasi: U/D, OHS, ACL, Conformist, Shared Kernel.
       |
       v
[Tahap 4: Contract Engineering]
       |
       +---> Desain Skema Kontrak Publik (Protobuf, OpenAPI, JSON Schema).
       +---> Pisahkan Internal Domain Event dari External Integration Event.
       |
       v
[Tahap 5: Implementasi Defensive Boundaries]
       |
       +---> Implementasi Anti-Corruption Layer (Inbound/Outbound Adapter).
       +---> Setup Transactional Outbox Worker untuk publikasi asinkron.
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Kedutaan Besar dan Protokol Diplomatik
Sebuah Bounded Context bekerja seperti kedaulatan sebuah negara:
- Bahasa internal negara A adalah bahasa lokal (bahasa domain internal).
- Ketika negara B (Upstream) mengirimkan dokumen regulasi dalam bahasanya, negara A tidak langsung memaksa seluruh birokrasi internalnya menggunakan bahasa negara B.
- Negara A menempatkan **Kedutaan / Atase Diplomatik (Anti-Corruption Layer)** di perbatasan. Kedutaan menerima dokumen, memvalidasi integritasnya, dan menerjemahkannya (*Translator*) ke dalam bahasa lokal sebelum diteruskan ke kementerian internal.
- Jika sebuah negara adalah adidaya yang melayani banyak negara lain, ia merilis piagam perjanjian resmi internasional yang distandardisasi (misalnya Bahasa PBB = *Open Host Service / Published Language*).

#### Diagram Interaksi Konteks dan Boundaries

```
+------------------------------------------------------------------------------------+
| UPSTREAM CONTEXT: ORDER MANAGEMENT SYSTEM (OHS / PL)                                |
|                                                                                    |
|  [Aggregate: Order]                                                                |
|          |                                                                         |
|  (State: Placed)                                                                   |
|          |                                                                         |
|          v                                                                         |
|  [Internal Domain Event: OrderPlacedDomainEvent]                                   |
|          |                                                                         |
|          v                                                                         |
|  [Outbox Publisher (Transactional Outbox)]                                         |
|          |                                                                         |
|          v                                                                         |
|  [Integration Event Schema: OrderCreatedV1] (Published Language)                   |
+----------|-------------------------------------------------------------------------+
           |
           | Network Boundary (Kafka Topic: "ecommerce.orders.v1")
           v
+------------------------------------------------------------------------------------+
| DOWNSTREAM CONTEXT: FULFILLMENT & LOGISTICS (D)                                    |
|                                                                                    |
|  +-------------------------------------------------------------------------------+ |
|  | ANTI-CORRUPTION LAYER (ACL)                                                    | |
|  |                                                                               | |
|  |  [Event Listener Adapter]                                                     | |
|  |          |                                                                    | |
|  |          v                                                                    | |
|  |  [Schema Validator & Deserializer]                                            | |
|  |          |                                                                    | |
|  |          v                                                                    | |
|  |  [Context Translator / Model Mapper]                                          | |
|  |          | Menerjemahkan 'OrderCreatedV1' menjadi 'ProvisionDeliveryJobCommand' |
|  +----------|--------------------------------------------------------------------+ |
|             v                                                                      |
|  [Application Service: DeliveryManager]                                            |
|             |                                                                      |
|             v                                                                      |
|  [Aggregate: DeliveryTask] (Model internal bebas murni dari istilah Ordering)       |
+------------------------------------------------------------------------------------+
```

---

### 7. Practical Implementation Code

Berikut adalah implementasi skala enterprise berbasis **TypeScript (Node.js)** menggunakan arsitektur Hexagonal/Ports & Adapters, yang mendemonstrasikan **Anti-Corruption Layer (ACL)**, **Integration Event vs Domain Event**, dan **Open Host Service Mapper**.

#### 7.1. Upstream Contract (Published Language DTO)

```typescript
// File: src/upstream-contracts/order-events.ts
/**
 * PUBLISHED LANGUAGE: Kontrak publik yang diekspos oleh Upstream (Order Context).
 * Didesain stabil, backward-compatible, dan agnostic terhadap struktur internal DB.
 */
export interface OrderCreatedV1Payload {
  eventId: string;
  occurredAt: string; // ISO8601
  aggregateId: string;
  data: {
    orderNumber: string;
    buyerId: string;
    currency: string;
    lineItems: Array<{
      sku: string;
      unitPrice: number;
      qty: number;
    }>;
    destination: {
      recipientName: string;
      streetAddress: string;
      postalCode: string;
      countryCode: string;
    };
  };
}
```

#### 7.2. Downstream Internal Domain Model (Pristine, Tanpa Ketergantungan Eksternal)

```typescript
// File: src/fulfillment/domain/models/shipping-manifest.ts
export class Coordinates {
  constructor(public readonly latitude: number, public readonly longitude: number) {}
}

export class PostalCode {
  private readonly value: string;

  constructor(raw: string) {
    if (!/^[0-9]{5}$/.test(raw.trim())) {
      throw new Error(`Invalid postal code format: ${raw}`);
    }
    this.value = raw.trim();
  }

  getValue(): string {
    return this.value;
  }
}

export enum ConsignmentStatus {
  UNASSIGNED = 'UNASSIGNED',
  ROUTED = 'ROUTED',
  IN_TRANSIT = 'IN_TRANSIT',
  DELIVERED = 'DELIVERED'
}

export interface ParcelItem {
  trackingSku: string;
  itemWeightGrams: number;
  quantity: number;
}

export class ConsignmentAggregate {
  private status: ConsignmentStatus;

  constructor(
    public readonly consignmentId: string,
    public readonly externalReference: string,
    public readonly postalDestination: PostalCode,
    private readonly items: ParcelItem[],
    status?: ConsignmentStatus
  ) {
    this.status = status || ConsignmentStatus.UNASSIGNED;
  }

  public getStatus(): ConsignmentStatus {
    return this.status;
  }

  public getTotalWeightGrams(): number {
    return this.items.reduce((acc, curr) => acc + curr.itemWeightGrams * curr.quantity, 0);
  }

  public markAsRouted(): void {
    if (this.status !== ConsignmentStatus.UNASSIGNED) {
      throw new Error(`Cannot transition consignment from ${this.status} to ROUTED`);
    }
    this.status = ConsignmentStatus.ROUTED;
  }
}
```

#### 7.3. Anti-Corruption Layer (ACL): Translators & Adapters

```typescript
// File: src/fulfillment/acl/order-to-consignment-translator.ts
import { OrderCreatedV1Payload } from '../../upstream-contracts/order-events';
import { ConsignmentAggregate, PostalCode, ParcelItem } from '../domain/models/shipping-manifest';
import { randomUUID } from 'crypto';

export class OrderToConsignmentTranslator {
  /**
   * Menerjemahkan skema Published Language eksternal ke dalam Invariant Internal Domain.
   * Melakukan translasi terminologi:
   * - orderNumber -> externalReference
   * - SKU -> trackingSku (diasosiasikan dengan estimasi berat default lokal)
   * - postalCode (string) -> PostalCode Value Object
   */
  public static toConsignmentAggregate(event: OrderCreatedV1Payload): ConsignmentAggregate {
    const defaultWeightPerSkuGrams = 250; // Asumsi domain Fulfillment

    const parcelItems: ParcelItem[] = event.data.lineItems.map((item) => ({
      trackingSku: `FULFILL-${item.sku}`,
      itemWeightGrams: defaultWeightPerSkuGrams,
      quantity: item.qty
    }));

    const destinationPostalCode = new PostalCode(event.data.destination.postalCode);

    return new ConsignmentAggregate(
      randomUUID(),
      event.data.orderNumber,
      destinationPostalCode,
      parcelItems
    );
  }
}
```

```typescript
// File: src/fulfillment/acl/order-event-consumer.ts
import { OrderCreatedV1Payload } from '../../upstream-contracts/order-events';
import { OrderToConsignmentTranslator } from './order-to-consignment-translator';
import { ConsignmentAggregate } from '../domain/models/shipping-manifest';

export interface ConsignmentRepository {
  save(consignment: ConsignmentAggregate): Promise<void>;
  existsByReference(reference: string): Promise<boolean>;
}

export class OrderEventKafkaConsumerACL {
  constructor(private readonly consignmentRepo: ConsignmentRepository) {}

  /**
   * Defensive Boundary: Mengisolasi sistem downstream dari anomali data,
   * duplikasi event (idempotency), dan ketidaksesuaian skema.
   */
  public async handle(rawPayload: unknown): Promise<void> {
    // 1. Structural Inbound Validation
    if (!this.isValidPayload(rawPayload)) {
      console.error('[ACL-REJECT] Invalid payload structure received from Upstream', rawPayload);
      return; // Route ke Dead Letter Queue (DLQ) pada implementasi produksi
    }

    const event = rawPayload as OrderCreatedV1Payload;

    // 2. Idempotency Check (Defensive Design)
    const alreadyProcessed = await this.consignmentRepo.existsByReference(event.data.orderNumber);
    if (alreadyProcessed) {
      console.warn(`[ACL-IDEMPOTENT] Order ${event.data.orderNumber} already processed. Skipping.`);
      return;
    }

    try {
      // 3. Translation via ACL Layer
      const domainModel = OrderToConsignmentTranslator.toConsignmentAggregate(event);

      // 4. Persistence into pristine downstream state
      await this.consignmentRepo.save(domainModel);
      console.info(`[ACL-SUCCESS] Ingested Order ${event.data.orderNumber} as Consignment ${domainModel.consignmentId}`);
    } catch (domainError: any) {
      // Melindungi Downstream agar invariant failure upstream tidak merusak state downstream
      console.error(`[ACL-CORRUPTION-PREVENTED] Data violates downstream invariant: ${domainError.message}`);
      // Lemparkan ke sistem triage manual / alert ops
    }
  }

  private isValidPayload(payload: any): payload is OrderCreatedV1Payload {
    return (
      payload &&
      typeof payload.eventId === 'string' &&
      payload.data &&
      typeof payload.data.orderNumber === 'string' &&
      Array.isArray(payload.data.lineItems) &&
      payload.data.destination &&
      typeof payload.data.destination.postalCode === 'string'
    );
  }
}
```

---

### 8. Real-World Case Study (Enterprise Scale)

#### Kasus: Transformasi Perbankan Digital "Bank Global Nusantara (BGN)"
BGN memiliki aplikasi monolitik "Core Banking" berbasis mainframe IBM/AS400. Seluruh fungsi bisnis—Kredit Finansial, Deteksi Fraud, Tabungan, dan Kartu Kredit—membaca dan menulis tabel database yang sama (`TBL_ACCOUNT_MASTER`).

#### Permasalahan:
1. **Model Anomali**: Tim Kartu Kredit memerlukan saldo berorientasi *Credit Limit*, sedangkan Tim Tabungan memerlukan *Available Ledger Balance*. Setiap kali ada tim yang menambahkan *stored procedure* untuk mengubah skema, tim lain terdampak *regression bug*.
2. **Koordinasi Kognitif**: Rilis fitur baru membutuhkan sinkronisasi rapat 6 tim teknis berbeda selama 3 minggu.

#### Eksekusi Strategi DDD:
1. **Delineasi Subdomain**:
   - *Core Domain*: Real-Time Ledger Engine & Core Settlement (In-house Custom Build).
   - *Supporting Domain*: Pengajuan Kartu Kredit & Onboarding KYC (Custom Build).
   - *Generic Domain*: Notification Engine (Beli solusi SaaS / Twilio / SendGrid).
2. **Context Mapping & Boundary Design**:
   - Memecah monolit menjadi dua bounded context: `Accounts & Ledger Context` dan `Credit Card Issuance Context`.
   - Pola Integrasi: **Customer-Supplier dengan Anti-Corruption Layer**.
   - `Accounts Context` bertindak sebagai Upstream ($U$) yang mengimplementasikan Open Host Service via Apache Kafka dengan Protobuf schemas.
   - `Credit Card Context` bertindak sebagai Downstream ($D$). Mereka menolak menggunakan skema data AS400 mentah dan membangun **ACL Service terisolasi**.
3. **Hasil Arsitektur**:
   - Frekuensi rilis tim kartu kredit melonjak dari 1 kali per kuartal menjadi 4 kali per minggu.
   - *Failure blast radius* berkurang drastis: kegagalan migrasi di skema penagihan kartu kredit tidak lagi mengunci sistem otorisasi penarikan ATM di Core Ledger.

---

### 9. Trade-offs Analysis

```
Pola Integrasi:
[Shared Kernel]  --------------------------------------->  [Anti-Corruption Layer (ACL)]
 - Kopling Sangat Tinggi                                   - Zero Domain Coupling
 - Latensi Eksekusi Rendah                                 - Ada Overhead Latensi Serialisasi & Translasi
 - Biaya Infrastruktur Minimal                             - Butuh Maintenance Kode Tambahan
 - Kompleksitas Koordinasi Tinggi                          - Skalabilitas & Otonomi Tim Maksimal
```

| Kriteria | Shared Kernel (SK) | Conformist (CF) | Anti-Corruption Layer (ACL) | Open Host Service (OHS/PL) |
| :--- | :--- | :--- | :--- | :--- |
| **Performance & Latensi** | **Tertinggi** (In-memory / direct DB access). | **Tinggi** (Translasi 0, direct parsing DTO). | **Sedang-Rendah** (CPU cycle terpakai untuk parsing, validasi, dan translasi model). | **Tinggi** (Tergantung protokol: binary gRPC vs text JSON). |
| **Domain Purity** | **Rendah** (Model harus kompromi antar tim). | **Nol** (Model downstream terpolusi model upstream). | **Sempurna (100%)** (Model internal downstream tetap murni). | **Tinggi** (Model upstream tidak bocor sembarangan). |
| **Team Autonomy** | **Sangat Rendah** (Perubahan wajib rapat konsensus). | **Rendah** (Downstream pasrah pada roadmap upstream). | **Sangat Tinggi** (Downstream bebas refactor kapan saja). | **Tinggi** (Kontrak publik stabil dan diverifikasi semver). |
| **Cost & Overhead** | Biaya dev awal rendah; biaya pemeliharaan akhir eksponensial. | Biaya terendah di awal; risiko teknis tinggi di kemudian hari. | Biaya dev awal tinggi (harus menulis adapter, mapper, unit test). | Biaya dev dan tata kelola API/Schema Registry tinggi. |

---

### 10. Common Mistakes & Troubleshooting

#### Mistake 1: Shared Database Dipakai Sebagai Context Integration
- **Gejala**: Dua bounded context berbeda mengakses skema database PostgreSQL yang sama secara langsung melalui ORM masing-masing.
- **Root Cause**: Developer enggan menangani *network latency* atau belum menyediakan message broker.
- **Dampak**: *Data corruption*, race conditions, penguncian tabel (*deadlock* antar-service), dan ketidakmampuan mengubah skema DB secara independen.
- **Solusi**: Terapkan *Database-per-Context*. Isolasi penuh level database instance atau minimal logical database schema terpisah dengan kredensial akses berbeda.

#### Mistake 2: Membocorkan Internal Domain Model ke Event Bus (Domain Event leaks as Integration Event)
- **Gejala**: Aggregate root internal langsung diserialisasi menjadi JSON dan dikirim ke Kafka.
- **Root Cause**: Malas mendefinisikan *Data Transfer Object (DTO)* terpisah untuk *Integration Event*.
- **Dampak**: Setiap refactoring kelas internal pada domain Upstream akan serta-merta merusak (*breaking change*) puluhan subsistem konsumer Downstream.
- **Solusi**: Terapkan isolasi dua lapis. Aggregate memancarkan `DomainEvent` (privat). Application service menangkapnya, mengonversinya menjadi `IntegrationEvent` (publik yang mengikuti versi semantik), lalu mengirimkannya via *Transactional Outbox Pattern*.

---

### 11. Best Practices (Production Checklist)

Gunakan daftar periksa ini sebelum meloloskan desain arsitektur strategis ke tahap implementasi:

- [ ] **Boundary Verification**: Model tidak mengandung *polysemic terms* tanpa pemisahan konteks yang jelas.
- [ ] **Contract Versioning**: Semua payload integrasi antarkonteks (REST/gRPC/Events) wajib menerapkan *Semantic Versioning* (misal: `v1.2.0`) dan skema didefinisikan secara deklaratif (Protobuf, Avro, atau JSON Schema).
- [ ] **Context Map Formally Documented**: Tersedia dokumen atau diagram repositori yang secara tegas menandai batas upstream ($U$), downstream ($D$), ACL, dan OHS.
- [ ] **No Direct Cross-Context Foreign Keys**: Larang relasi tabel langsung antar Bounded Context di level DDL database. Integrasi id referensi hanya diperbolehkan berupa tipe skalar primitif (UUID/String).
- [ ] **Asynchronous Decoupling**: Untuk integrasi lintas batas yang tidak membutuhkan konsistensi instan, gunakan komunikasi asinkron berbasis *Transactional Outbox* untuk menghindari *distributed transaction (2PC)*.
- [ ] **Defensive Invariant Check di ACL**: Pastikan Anti-Corruption Layer melakukan validasi integritas model sebelum data menyentuh lapisan *Domain Model* downstream.
- [ ] **Team Topology Alignment**: Satu bounded context dimiliki secara eksklusif oleh **satu** tim teknis. Hindari kondisi satu context dikeroyok banyak tim tanpa kepemilikan jelas.

---

### 12. Hands-on Practice

Buatlah implementasi Anti-Corruption Layer dan Integration Contract pada direktori `hands-on/m02/`.

#### Langkah 1: Setup Proyek
```bash
mkdir -p hands-on/m02/src/{upstream,downstream,shared}
cd hands-on/m02
npm init -y
npm install typescript @types/node tsx --save-dev
npx tsc --init
```

#### Langkah 2: Buat Skema Upstream & Published Language
Buat file `src/upstream/billing-events.ts`:
```typescript
export interface InvoiceSettledPayloadV1 {
  event_name: 'INVOICE_SETTLED';
  schema_version: 1;
  payload: {
    invoice_id: string;
    debtor_code: string;
    amount_in_cents: number;
    settled_timestamp: number;
    billing_channel: 'SNAP_VA' | 'CREDIT_CARD' | 'E_WALLET';
  };
}
```

#### Langkah 3: Buat Model Downstream yang Terisolasi
Buat file `src/downstream/domain.ts`:
```typescript
export class AccountBalance {
  constructor(
    public readonly accountId: string,
    private currentFunds: number
  ) {}

  public credit(amount: number): void {
    if (amount <= 0) throw new Error("Amount must be strictly positive");
    this.currentFunds += amount;
  }

  public getBalance(): number {
    return this.currentFunds;
  }
}
```

#### Langkah 4: Buat Anti-Corruption Layer (ACL)
Buat file `src/downstream/billing-acl.ts`:
```typescript
import { InvoiceSettledPayloadV1 } from '../upstream/billing-events';
import { AccountBalance } from './domain';

export class BillingACLAdapter {
  public static parseAndCredit(
    rawMessage: unknown,
    targetAccount: AccountBalance
  ): void {
    const event = rawMessage as InvoiceSettledPayloadV1;

    // Boundary Defense: Validasi kontrak eksternal
    if (event.event_name !== 'INVOICE_SETTLED' || event.schema_version !== 1) {
      throw new Error(`[ACL] Incompatible schema or event type`);
    }

    // Translasi mata uang: cents (upstream) -> standard monetary units (downstream)
    const nominalConverted = event.payload.amount_in_cents / 100;

    // Mutasi invariant domain downstream
    targetAccount.credit(nominalConverted);
  }
}
```

#### Langkah 5: Eksekusi Test Harness
Buat file `src/main.ts`:
```typescript
import { BillingACLAdapter } from './downstream/billing-acl';
import { AccountBalance } from './downstream/domain';

const userAccount = new AccountBalance("ACC-1002", 50.0);
console.log("Initial Balance:", userAccount.getBalance());

const incomingKafkaEvent = {
  event_name: 'INVOICE_SETTLED',
  schema_version: 1,
  payload: {
    invoice_id: 'INV-2026-X99',
    debtor_code: 'CUST-883',
    amount_in_cents: 125000, // 1250.00
    settled_timestamp: Date.now(),
    billing_channel: 'SNAP_VA'
  }
};

BillingACLAdapter.parseAndCredit(incomingKafkaEvent, userAccount);
console.log("Updated Balance post-ACL translation:", userAccount.getBalance());
```
Jalankan menggunakan:
```bash
npx tsx src/main.ts
```

---

### 13. Exercise

#### Level Easy
Jelaskan perbedaan mendasar antara *Domain Event* dan *Integration Event*. Modifikasi file `src/upstream/billing-events.ts` pada hands-on di atas untuk menambahkan metadata korelasi transaksi (*correlationId* dan *causationId*) guna memastikan traceability.

#### Level Medium
Sebuah sistem logistik Upstream mengirimkan status pengiriman paket dengan payload:
`{ "st": 3, "loc": "CGK", "timestamp": 1711234567 }`. Di mana kode integer `3` melambangkan "DELIVERED".
Buatlah translation engine di dalam Anti-Corruption Layer downstream yang memetakan kode integer status tersebut ke dalam Rich Domain Enum:
`DeliveryState.DELIVERED_TO_DESTINATION` dan melakukan verifikasi validitas kode bandara IATA ("CGK"). Jika kode tidak valid, tolak pemrosesan dan lemparkan *domain invariant exception*.

#### Level Hard
Rancang arsitektur implementasi **Transactional Outbox Pattern** untuk skenario *Multi-Bounded Context Integration*.
Tulis pseudocode / TypeScript implementation yang mencakup:
1. Menyimpan state entitas Domain bersamaan dengan *Outbox Record* dalam satu unit transaksi database atomik (ACID).
2. Sebuah background poller / CDC processor (Debezium pattern) yang membaca tabel *Outbox* dan mempublikasikannya ke message bus.
3. Mekanisme deduplikasi di downstream subscriber yang memastikan *exactly-once processing semantics* di level aplikasi.

---

### 14. Challenge

**Skenario**:
Anda ditunjuk sebagai Chief Enterprise Architect di sebuah startup Decacorn Fintech yang sedang melakukan merger dengan perusahaan logistik multinasional. Monolit warisan logistik beroperasi dengan database DB2 berusia 15 tahun tanpa API publik, sementara Fintech Anda beroperasi dengan 100+ microservices berbasis Kubernetes, Event-Driven (Kafka), dan Go/gRPC.

**Tantangan Arsitektural**:
1. Buat dokumen desain teknis (*Architecture Design Document*) yang merinci pemetaan context mapping antara konteks **"Payment & Wallet" (Fintech)** dengan **"Parcel Freight Management" (Logistik)**.
2. Identifikasi bagaimana Anda mencegah model usang dari monolit DB2 merusak (*polluting*) Ubiquitous Language dan model komputasi sistem Fintech Anda tanpa menghentikan operasi bisnis monolitik yang sedang berjalan.
3. Rancang strategi migrasi bertahap (*Strangler Fig Application*) menggunakan pendekatan Strategic DDD: Tentukan mana yang menjadi Core, Supporting, dan Generic Domain dari gabungan entitas bisnis baru tersebut, serta tentukan alur propagasi konsistensi data akhir (*eventual consistency*) antar sistem.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)

1. Apa definisi yang paling tepat untuk Bounded Context dalam Strategic DDD?
   - A. Batas deployment virtual machine di mana aplikasi berjalan.
   - B. Batas batas semantik dan linguistik di mana sebuah model domain tertentu berlaku secara valid dan konsisten.
   - C. Struktur folder modular dalam monolitik repositori.
   - D. Satu cluster database tunggal yang melayani berbagai modul.

2. Hubungan Context Mapping di mana downstream sepenuhnya menerima model upstream tanpa adaptasi disebut:
   - A. Anti-Corruption Layer
   - B. Open Host Service
   - C. Conformist
   - D. Separate Ways

3. Pola yang digunakan untuk melindungi kemurnian domain internal downstream dari perubahan skema upstream adalah:
   - A. Shared Kernel
   - B. Anti-Corruption Layer (ACL)
   - C. Big Ball of Mud
   - D. Event Sourcing

4. Apa dampak negatif terbesar dari penggunaan pola "Shared Kernel"?
   - A. Latensi jaringan meningkat tinggi.
   - B. Membutuhkan lisensi software pihak ketiga yang mahal.
   - C. Eratnya kopling antartim; perubahan pada skema kernel mengharuskan koordinasi rilis bersama yang kaku.
   - D. Tidak dapat disimpan di relational database.

5. Istilah untuk mendeskripsikan sebuah kata yang sama namun memiliki banyak arti berbeda di berbagai konteks bisnis adalah:
   - A. Polymorphism
   - B. Monomorphic
   - C. Polysemy
   - D. Ubiquitous Overload

---

#### Bagian 2: Intermediate (Pilihan Ganda & Analisis Pendek)

6. Mengapa Domain Event internal tidak disarankan untuk langsung dipublikasikan ke Kafka sebagai konsumsi publik Bounded Context lain?
   - A. Karena ukuran payload JSON Domain Event selalu melebihi kuota Kafka 1MB.
   - B. Karena mengekspos Domain Event internal menyebabkan kebocoran struktur data internal privat, mematahkan enkapsulasi konteks.
   - C. Karena Kafka tidak mendukung pemrosesan event bertipe Domain Event.
   - D. Karena Domain Event hanya dapat dijalankan di memori RAM dan tidak dapat diserialisasi.

7. Perhatikan relasi dua konteks: Konteks Akuntansi ($D$) bergantung pada Konteks Penjualan ($U$). Konteks Penjualan menolak mengubah API-nya untuk kebutuhan Akuntansi, namun Akuntansi tidak ingin model internalnya dirusak oleh format Penjualan. Pola integrasi apa yang wajib dibangun oleh tim Akuntansi?
   - A. Customer-Supplier dengan Penjualan membangun OHS.
   - B. Conformist secara langsung.
   - C. Anti-Corruption Layer (ACL) di sisi Akuntansi.
   - D. Membagi database menjadi Shared Kernel.

8. Menurut hukum Conway (Conway's Law), bagaimana seharusnya struktur tim diselaraskan dengan Bounded Context?
   - A. Satu tim backend mengerjakan semua Bounded Context agar seragam.
   - B. Satu tim memiliki dan mengelola satu atau beberapa Bounded Context secara otonom, tanpa ada satu Bounded Context yang dimiliki bersama oleh banyak tim independen.
   - C. Tim dibagi berdasarkan layer: Tim Controller, Tim Service, dan Tim Database.
   - D. Seluruh Bounded Context didelegasikan pengembangannya ke pihak ketiga.

9. Manakah karakteristik utama dari Subdomain bertipe "Core Domain"?
   - A. Fungsionalitas standar yang dapat dibeli dari vendor SaaS off-the-shelf.
   - B. Modul pembantu yang penting namun tidak memberikan diferensiasi kompetitif di pasar.
   - C. Bagian dari sistem yang menjadi keunggulan kompetitif utama perusahaan, memiliki kompleksitas tinggi, dan harus dikembangkan secara in-house.
   - D. Skema database legacy yang tidak berani diubah oleh tim engineering.

10. Dalam implementasi Open Host Service (OHS), dokumen atau skema yang mendefinisikan payload data publik disebut sebagai:
    - A. Internal Entity Representation
    - B. Published Language (PL)
    - C. Domain Transfer Entity
    - D. Anti-Corruption Gateway

---

#### Bagian 3: Skenario Kasus Produksi (Analisis Arsitektural)

11. **Skenario 1 (Breaking Contract Failure)**:
    Konteks *Inventory Management* mengubah struktur payload integrasi event dari camelCase ke snake_case dan menghapus field `warehouse_id` yang digantikan oleh array `facility_assignments`. Sesaat setelah deploy, sistem *Order Checkout* mengalami *crash cascading* hingga checkout terhenti total selama 4 jam. 
    *Pertanyaan*: Apa kelemahan arsitektural strategis yang terjadi, dan mekanisme defensif apa yang seharusnya dipasang di Downstream Checkout Context?

12. **Skenario 2 (The Distributed Monolith Trap)**:
    Sebuah organisasi memecah aplikasi monolit mereka menjadi 25 *microservices*. Namun, setiap kali ada perubahan proses bisnis kecil, mereka harus melakukan deployment serentak (*orchestrated lockstep release*) pada 8 *service* yang berbeda karena seluruh *service* tersebut membaca tabel shared database yang sama.
    *Pertanyaan*: Analisislah kegagalan desain Strategic DDD apa yang terjadi di sini, dan bagaimana langkah mitigasi untuk memetakan ulang batas-batas konteks tersebut?

13. **Skenario 3 (Data Invariant Poisoning via Asynchronous Event)**:
    Konteks *Payment Gateway* memancarkan event `PaymentSucceededEvent` dengan nilai transaksi negatif (`-50000 USD`) akibat bug internal. Konteks *Ledger* yang berlangganan event tersebut langsung mencatat mutasi kredit ke database utama tanpa validasi defensif, merusak kalkulasi neraca keuangan perusahaan.
    *Pertanyaan*: Jelaskan di layer mana kegagalan terjadi dan bagaimana desain Anti-Corruption Layer seharusnya menangani insiden data poisoning ini.

---

### Kunci Jawaban Quiz

#### Bagian 1: Basic
1. **B** — Bounded Context adalah perimeter eksplisit tempat sebuah model domain berlaku valid secara semantik dan linguistik.
2. **C** — *Conformist* terjadi ketika downstream tunduk sepenuhnya pada model upstream.
3. **B** — *Anti-Corruption Layer (ACL)* bertindak sebagai penerjemah isolatif untuk menjaga kemurnian model downstream.
4. **C** — *Shared Kernel* menciptakan kopling bilateral yang tinggi antartim; modifikasi model memerlukan rapat konsensus dan rilis sinkron.
5. **C** — *Polysemy* adalah fenomena satu kata memiliki multi-makna pada domain yang berbeda.

#### Bagian 2: Intermediate
6. **B** — Domain event internal adalah implementasi teknis privat aggregate; mempublikasikannya langsung akan membocorkan invariant internal dan mematahkan enkapsulasi arsitektur.
7. **C** — Anti-Corruption Layer di Downstream ($D$) mengisolasi model Akuntansi dari model Penjualan tanpa memerlukan perubahan di Upstream.
8. **B** — Team Topologies dan Inverse Conway Maneuver menyarankan kepemilikan 1:1 antara Stream-Aligned Team dan Bounded Context untuk menghilangkan *coordination overhead*.
9. **C** — *Core Domain* adalah inti diferensiasi bisnis yang menciptakan nilai kompetitif unik dan harus dibangun secara mandiri.
10. **B** — *Published Language* adalah model data atau skema standar yang digunakan bersama oleh OHS untuk berinteraksi dengan konsumen eksternal.

#### Bagian 3: Panduan Evaluasi Skenario Kasus Produksi
11. **Analisis Skenario 1**:
    - *Akar Masalah*: Upstream melanggar kontrak publik tanpa Semantic Versioning yang jelas (*backward incompatibility*), dan Downstream bertindak sebagai *Conformist* yang rentan (*tightly coupled*).
    - *Solusi Defensif*: Downstream harus menerapkan **Anti-Corruption Layer** yang memvalidasi struktur schema inbound. Jika schema tidak sesuai, ACL akan menolak payload secara anggun (*graceful failure*), melempar pesan ke Dead Letter Queue (DLQ), menyalakan alerting, dan tidak menyebabkan *thread exhaustion / unhandled exception crash* pada proses checkout inti. Upstream harus menerapkan OHS dengan versioning rilis paralel (`v1` dan `v2`).
12. **Analisis Skenario 2**:
    - *Akar Masalah*: Pemecahan *microservices* dilakukan berdasarkan partisi fungsional semu (*entity-based service* atau *technical layer*) alih-alih *semantic Bounded Context*. Penggunaan *Shared Database* membatalkan otonomi.
    - *Solusi Mitigasi*: Lakukan dekomposisi ulang menggunakan analisis linguistik (*EventStorming*). Gabungkan (*merge*) service-service yang memiliki siklus transaksi ACID identik menjadi satu Bounded Context (Modular Monolith terlebih dahulu). Hapus akses direct database; isolasi database untuk masing-masing konteks.
13. **Analisis Skenario 3**:
    - *Akar Masalah*: Pelanggaran prinsip *Boundary Defense*; Downstream mempercayai upstream secara mutlak tanpa memvalidasi invariant bisnis downstream (*Blind Trust Assumption*).
    - *Solusi Mitigasi*: Downstream ACL harus menolak data tersebut di pintu gerbang. Ketika translator ACL mencoba membuat domain Value Object / Entity (misal `TransactionAmount`), invariant konstruktor downstream wajib mengeksekusi validasi bahwa nilai uang harus $> 0$. Jika validasi gagal, ACL memblokir propagasi mutasi ke *Ledger Domain Model*, mencatat audit failure log, dan mengisolasi event rusak tersebut.

---

### 16. Summary

1. **Strategic DDD adalah Tata Kelola Kompleksitas Skala Besar**: Sebelum menulis satu baris pun kode aggregate atau repository, arsitek sistem harus terlebih dahulu menarik garis perimeter (*Bounded Context*) yang tegas dan mendefinisikan bahasa domain yang tidak ambigu (*Ubiquitous Language*).
2. **Context Mapping Menentukan Hubungan Kekuasaan Teknis**: Hubungan antarsistem selalu memiliki konsekuensi upstream/downstream ($U/D$). Mengabaikan desain context mapping akan menggiring arsitektur menuju sistem monolit terdistribusi (*Distributed Big Ball of Mud*).
3. **ACL Menjamin Otonomi dan Kemurnian Domain**: Gunakan *Anti-Corruption Layer* saat mengintegrasikan sistem baru dengan modul warisan (*legacy*) atau saat downstream menolak tunduk pada model upstream demi menjaga kemurnian logikanya.
4. **Pisahkan Komunikasi Privat dari Publik**: Domain Event adalah implementasi internal transaksional lokal; Integration Event adalah kontrak publik stabil (*Published Language*) yang diekspos melalui pola *Open Host Service* menggunakan infrastruktur messaging andal.
5. **Kesesuaian Sosio-Teknis**: Arsitektur perangkat lunak dan topologi tim saling memantulkan dampaknya (Conway's Law). Batas context yang sehat akan menghasilkan tim yang independen, otonom, dan memiliki kecepatan delivery yang eksponensial di level produksi enterprise.