# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 02: Prinsip Desain Kode (SOLID & GRASP)**  
**Jalur Pembelajaran: Software Design & Architecture (Enterprise Grade)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan memiliki kapabilitas teknis tingkat *Principal/Lead Architect* untuk:
1. **Menganalisis dan Membedah Runtime Footprint**: Memahami secara mendalam implikasi penerapan abstraksi SOLID dan pola GRASP terhadap *instruction cache*, alokasi memori (heap vs. stack), *virtual method table (vtable)*, dan *branch prediction*.
2. **Eliminasi Architectural Rot**: Mengidentifikasi dan merekayasa ulang *code smell* struktural berskala besar (*Shotgun Surgery*, *Divergent Change*, *Primitive Obsession*, dan *Feature Envy*) menggunakan kombinasi GRASP (*Pure Fabrication*, *Information Expert*) dan SOLID (*Single Responsibility*, *Dependency Inversion*).
3. **Mendesain Sub-Sistem Berskala Enterprise yang Resilien**: Mengimplementasikan arsitektur berorientasi domain (*Domain-Driven Architecture*) berbasis *Liskov Substitution Principle* (LSP) dan *Protected Variations* yang mampu menahan perubahan integrasi pihak ketiga tanpa mengubah *core domain logic*.
4. **Mengukur dan Mengotomatisasi Metrik Kualitas Kode**: Mengintegrasikan metrik kopling dan kohesi (*Instability Index*, *Abstractness*, *Distance from the Main Sequence*) ke dalam *Continuous Integration (CI) pipeline*.

---

## 2. Prerequisite

Peserta wajib menguasai:
* Pemahaman mendalam tentang *Object-Oriented Programming* (OOP) tingkat lanjut: polymorphism, dynamic dispatch, static analysis, generic types.
* Karakteristik eksekusi *runtime engine* (V8, JVM, atau Go Runtime): alokasi memori, garbage collection, dan escape analysis.
* Pola dasar arsitektur perangkat lunak: Monolithic terstruktur, Hexagonal/Ports & Adapters, dan Clean Architecture.
* Pemrograman berbasis TypeScript / Go / Java tingkat menengah ke atas (seluruh contoh kode modul ini menggunakan **TypeScript strict-mode** berstandar enterprise).

---

## 3. Concept & Internal Architecture (Mendalam)

Penerapan prinsip desain berorientasi objek di tingkat enterprise bukan sekadar aturan gaya penulisan kode (*coding style*), melainkan strategi rekayasa untuk mengendalikan **Kinetika Perubahan Perangkat Lunak** (*software change dynamics*) pada level instruksi mesin dan arsitektur sistem.

### 3.1 Mekanisme Dynamic Dispatch dan Biaya Polymorphism (LSP & Polymorphism GRASP)

Secara teoritis, *Polymorphism* (GRASP) dan *Liskov Substitution Principle* (SOLID) memungkinkan substitusi implementasi polimorfik tanpa merusak kontrak (*contract invariants*). Namun, di balik layar, eksekusi pemanggilan metode interface melibatkan overhead:

```
[Object Reference in Heap]
       │
       ▼
┌──────────────────┐
│ Object Header    │
│ Type Descriptor  ├──────► ┌────────────────────────┐
├──────────────────┤        │ VTable (Virtual Table) │
│ Field: balance   │        ├────────────────────────┤
│ Field: accountId │        │ FuncPtr: debit()       │───► [Machine Code: Debit]
└──────────────────┘        │ FuncPtr: credit()      │───► [Machine Code: Credit]
                            └────────────────────────┘
```

1. **VTable Lookups**: Setiap *virtual call* memaksa CPU melakukan *pointer chasing* dereferensi ganda: membaca alamat *vtable* dari header objek, mencari *offset* fungsi, lalu melompat ke alamat memori fungsi tersebut.
2. **Inlining Inhibition**: Kompiler Just-In-Time (JIT) atau kompilator statis tidak dapat melakukan *function inlining* secara agresif jika sebuah target pemanggilan memiliki lebih dari dua implementasi aktif (*megamorphic call-site*).
3. **Branch Target Buffer (BTB) Misses**: Dynamic dispatch yang tidak dapat diprediksi mengakibatkan CPU pipeline flush, meningkatkan latensi eksekusi pada jalur komputasi throughput tinggi (*hot-path*).

### 3.2 Metrik Kuantitatif Martin: Coupling & Cohesion

Arsitektur yang sehat dapat diverifikasi secara matematis menggunakan kalkulus struktural Robert C. Martin:

* **Afferent Coupling ($C_a$)**: Jumlah kelas di luar modul yang bergantung pada kelas di dalam modul (mengukur ketergantungan masuk).
* **Efferent Coupling ($C_e$)**: Jumlah kelas di dalam modul yang bergantung pada kelas di luar modul (mengukur ketergantungan keluar).
* **Instability ($I$)**:
  $$I = \frac{C_e}{C_a + C_e}$$
  Rentang nilai: $0 \le I \le 1$. Nilai $I=0$ menunjukkan komponen sangat stabil (sulit diubah karena banyak yang bergantung padanya), sedangkan $I=1$ menunjukkan komponen sangat tidak stabil (*fragile* atau independen).
* **Abstractness ($A$)**:
  $$A = \frac{N_a}{N_c}$$
  Di mana $N_a$ adalah jumlah kelas/interface abstrak, dan $N_c$ adalah total kelas konkret + abstrak.
* **Normalized Distance from the Main Sequence ($D$)**:
  $$D = |A + I - 1|$$
  Komponen arsitektur yang ideal berada di dekat garis *Main Sequence* ($A + I = 1$). Modul dengan $A=0, I=0$ berada di *Zone of Pain* (kaku, non-abstrak, sulit diubah, dependensi tinggi). Modul dengan $A=1, I=1$ berada di *Zone of Uselessness* (terlalu abstrak tanpa dependensi konkret yang nyata).

```
   Abstractness (A)
   1.0 ┌────────────────────────────────────────┐
       │ Zone of Uselessness                    │
       │                   * (Ideal Abstraction)│
       │                 *                      │
       │               *                        │
       │             * (Main Sequence: A + I=1) │
       │           *                            │
       │         *                              │
       │       *                                │
       │     *                                  │
       │   *                                    │
       │ Zone of Pain                           │
   0.0 └────────────────────────────────────────┘
       0.0                                    1.0  Instability (I)
```

### 3.3 Relasi Simbiotik: SOLID vs. GRASP

GRASP adalah panduan penugasan tanggung jawab mental (*conceptual responsibility assignment*), sedangkan SOLID adalah pedoman restrukturisasi modularitas kode (*structural mechanics*):

| Kategori Masalah | Prinsip GRASP | Prinsip SOLID | Dampak Arsitektural |
| :--- | :--- | :--- | :--- |
| **Lokasi Logika** | *Information Expert* | *Single Responsibility (SRP)* | Mengeliminasi Anemic Domain Model dan kebocoran logika (*shotgun surgery*). |
| **Enkapsulasi Variasi** | *Protected Variations* | *Open/Closed (OCP)* | Menjamin stabilitas *core domain* terhadap perubahan pihak ketiga via isolasi interface. |
| **Penyambungan Modul** | *Low Coupling*, *Indirection* | *Dependency Inversion (DIP)* | Komponen tingkat tinggi tidak terikat detail infrastruktur (I/O, DB, Network). |
| **Fabrikasi Komponen** | *Pure Fabrication* | *Interface Segregation (ISP)* | Mencegah pembengkakan objek domain dengan memisahkan fungsi teknis infrastruktur. |

---

## 4. Why & What

### Mengapa Pendekatan Dogmatis Sering Gagal?
Banyak organisasi menerapkan SOLID dan GRASP secara membabi buta (*cargo-culting*), menghasilkan:
1. **Interface Explosion**: Membuat interface 1:1 untuk setiap kelas tanpa variasi polimorfik nyata. Ini meningkatkan alokasi memori, mempersulit penelusuran kode (*cognitive overhead*), dan merusak *cache locality*.
2. **Anemic Entities dengan God Services**: Salah menafsirkan SRP sehingga entitas domain hanya menjadi pembungkus data (*DTO* pasif), sementara seluruh logika ditarik ke dalam *service* raksasa yang melanggar *Information Expert*.

### Apa Pendekatan yang Benar?
Penerapan SOLID dan GRASP tingkat enterprise memandang arsitektur sebagai sistem kendali batas (*boundary management*):
* **SOLID** digunakan untuk mendikte batasan kompilasi, isolasi kesalahan (*fault domains*), dan struktur paket rilis (*deployable artifacts*).
* **GRASP** digunakan untuk menyusun alur kerja informasi di antara model domain agar invariants bisnis terlindungi secara deterministik di memori sebelum persistensi terjadi.

---

## 5. How (Workflow Detail)

Berikut alur kerja sistematis untuk merekayasa ulang komponen monolitik yang tightly coupled menjadi arsitektur yang terdecoupling menggunakan SOLID dan GRASP:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FASE 1: DIAGNOSIS & PROFILING                   │
│ 1. Ekstraksi Metrik Kopling (Afferent/Efferent, Cyclomatic Complexity).│
│ 2. Identifikasi Hotspot (Komponen dengan frekuensi commit & churn      │
│    tinggi).                                                            │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    FASE 2: REALOKASI TANGGUNG JAWAB                    │
│ 1. Ambil data dari Controller/God Service.                             │
│ 2. Pasang ke Information Expert (Domain Entity) jika memanipulasi data │
│    internal.                                                           │
│ 3. Buat Pure Fabrication untuk operasi lintas domain atau teknis       │
│    (misal: Kriptografi, Format Transformasi, I/O).                    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  FASE 3: ISOLASI INTERFACE & ABSTRAKSI                 │
│ 1. Terapkan ISP: Pecah antarmuka monolitik menjadi role-interfaces     │
│    yang kohesif.                                                       │
│ 2. Bangun abstraksi berbasis Protected Variations untuk mengisolasi    │
│    dependensi eksternal yang rentan perubahan.                         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  FASE 4: INVERSION OF CONTROL & CONTRACT               │
│ 1. Balikkan dependensi menggunakan DIP. Core Domain mendefinisikan      │
│    Ports (Interface), Infrastruktur menyediakan Adapters.              │
│ 2. Validasi kontrak dengan invariant Liskov (LSP Assertion Suite).     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Analogy & Diagram ASCII

Bayangkan sebuah gardu transmisi daya listrik bertegangan tinggi.

* **Pelanggaran SOLID/GRASP**: Seluruh kabel rumah, motor industri, dan generator turbin dihubungkan langsung ke satu blok terminal tembaga monolitik tanpa sekering, transformator, atau isolasi. Ketika tegangan turbin berfluktuasi (*volatility*), seluruh perangkat elektronik konsumen meledak (*shotgun surgery*).
* **Penerapan SOLID/GRASP**:
  * **Protected Variations / OCP**: Trafo step-down menstabilkan output ke 220V 50Hz konstan, apa pun jenis pembangkitnya (Nuklir, Batubara, Solar).
  * **Interface Segregation**: Steker 3-pin arde industri terpisah dari soket peralatan rumah tangga kecil.
  * **Pure Fabrication**: Komponen pemutus sirkuit (*circuit breaker*) bukan bagian dari energi itu sendiri, melainkan instrumen rekayasa murni untuk melindungi sistem.

```
+-------------------------------------------------------------------------------+
| CORE DOMAIN (High Stability, Information Expert, Protected Variations)       |
|                                                                               |
|   ┌───────────────────────────┐         ┌─────────────────────────────────┐   |
|   │ <<Entity>>                │         │ <<Pure Fabrication>>            │   |
|   │ TransactionLedgerEntry    │◄────────┤ LedgerPostingEngine             │   |
|   │ [Information Expert]      │         │ [High Cohesion]                 │   |
|   └─────────────┬─────────────┘         └────────────────┬────────────────┘   |
|                 │                                        │                    |
+─────────────────┼────────────────────────────────────────┼────────────────────+
                  │                                        │
                  ▼                                        ▼
+───────────────────────────────────────────────────────────────────────────────+
| PORTS / BOUNDARY INTERFACES (ISP, DIP)                                        |
|                                                                               |
|   ┌───────────────────────────┐         ┌─────────────────────────────────┐   |
|   │ <<Interface>>             │         │ <<Interface>>                   │   |
|   │ LedgerRepositoryPort      │         │ ForeignExchangeRatePort         │   |
|   └─────────────▲─────────────┘         └────────────────▲────────────────┘   |
|                 │                                        │                    |
+─────────────────┼────────────────────────────────────────┼────────────────────+
                  │                                        │ (Implements)
                  │ (Implements)                           │
+─────────────────┼────────────────────────────────────────┼────────────────────+
| INFRASTRUCTURE / ADAPTERS (Low Stability, I/O Bound)     │                    |
|                                                          │                    |
|   ┌─────────────┴─────────────┐         ┌────────────────┴────────────────┐   |
|   │ PostgresLedgerAdapter     │         │ BloombergFxRateAdapter          │   |
|   │ [PostgreSQL Driver, Pool] │         │ [HTTP/REST, Resilience4j-like]  │   |
|   └───────────────────────────┘         └─────────────────────────────────┘   |
+-------------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Anti-Pattern vs. Refactored (ISP & SRP)

#### Kode Buruk (Pelanggaran SRP, ISP, dan Anemic Domain Model):
```typescript
// ANTI-PATTERN: God Interface dan Anemic Model
interface OrderManager {
  calculateTax(order: any): number;
  saveToDatabase(order: any): void;
  sendNotification(userId: string, msg: string): void;
  processRefund(orderId: string, amount: number): boolean;
}

class OrderService implements OrderManager {
  calculateTax(order: any): number { return order.total * 0.11; }
  saveToDatabase(order: any): void { /* raw db logic */ }
  sendNotification(userId: string, msg: string): void { /* smtp logic */ }
  processRefund(orderId: string, amount: number): boolean { /* refund logic */ }
}
```

#### Kode Bersih (Penerapan SRP, ISP, Information Expert):
```typescript
// Domain Model sebagai Information Expert
export class OrderItem {
  constructor(
    public readonly sku: string,
    public readonly unitPriceCents: bigint,
    public readonly quantity: number
  ) {
    if (quantity <= 0) throw new Error("Quantity must be positive.");
    if (unitPriceCents < 0n) throw new Error("Price cannot be negative.");
  }

  public getSubtotalCents(): bigint {
    return this.unitPriceCents * BigInt(this.quantity);
  }
}

export class Order {
  constructor(
    public readonly id: string,
    private readonly items: ReadonlyArray<OrderItem>,
    private readonly taxRateBasisPoints: number
  ) {}

  // Information Expert: Order yang paling tahu bagaimana menghitung totalnya sendiri
  public calculateNetTotalCents(): bigint {
    return this.items.reduce((acc, item) => acc + item.getSubtotalCents(), 0n);
  }

  public calculateTaxCents(): bigint {
    const net = this.calculateNetTotalCents();
    return (net * BigInt(this.taxRateBasisPoints)) / 10000n;
  }

  public calculateGrossTotalCents(): bigint {
    return this.calculateNetTotalCents() + this.calculateTaxCents();
  }
}

// ISP: Interface dipecah sesuai kebutuhan klien
export interface OrderReader {
  findById(id: string): Promise<Order | null>;
}

export interface OrderWriter {
  save(order: Order): Promise<void>;
}
```

---

### 7.2 Practical Production Example: Core Financial Clearing Gateway

Contoh tingkat produksi ini mengimplementasikan:
1. **DIP & Protected Variations**: Isolasi mekanisme pemrosesan kliring terhadap fluktuasi *third-party payment gateway*.
2. **Pure Fabrication**: `TransactionClearingPipeline` mengatur alur kerja orkestrasi tanpa membebani entitas domain dengan dependensi I/O.
3. **LSP**: Implementasi substitusi gateway yang menjaga kontrak invariansi secara ketat.

```typescript
// ============================================================================
// 1. DOMAIN CORE: VALUE OBJECTS & ENTITIES (Information Expert)
// ============================================================================

export class Money {
  constructor(
    public readonly amountInMinorUnits: bigint,
    public readonly currency: string
  ) {
    if (amountInMinorUnits < 0n) {
      throw new DomainInvariantViolationError("Monetary amounts cannot be negative in this context.");
    }
    if (!/^[A-Z]{3}$/.test(currency)) {
      throw new DomainInvariantViolationError(`Invalid ISO currency: ${currency}`);
    }
  }

  public add(other: Money): Money {
    this.assertSameCurrency(other);
    return new Money(this.amountInMinorUnits + other.amountInMinorUnits, this.currency);
  }

  public subtract(other: Money): Money {
    this.assertSameCurrency(other);
    const result = this.amountInMinorUnits - other.amountInMinorUnits;
    if (result < 0n) {
      throw new DomainInvariantViolationError("Insufficient funds for subtraction.");
    }
    return new Money(result, this.currency);
  }

  private assertSameCurrency(other: Money): void {
    if (this.currency !== other.currency) {
      throw new DomainInvariantViolationError(
        `Currency mismatch: ${this.currency} !== ${other.currency}`
      );
    }
  }
}

export class DomainInvariantViolationError extends Error {
  constructor(message: string) {
    super(`[Domain Invariant Error]: ${message}`);
    this.name = "DomainInvariantViolationError";
  }
}

export enum TransactionStatus {
  INITIALIZED = "INITIALIZED",
  CLEARED = "CLEARED",
  SETTLEMENT_REJECTED = "SETTLEMENT_REJECTED"
}

export class ClearingTransaction {
  private status: TransactionStatus;
  private rejectionReason: string | null = null;

  constructor(
    public readonly transactionId: string,
    public readonly amount: Money,
    public readonly originAccountId: string,
    public readonly destinationAccountId: string
  ) {
    this.status = TransactionStatus.INITIALIZED;
  }

  public markAsCleared(): void {
    if (this.status !== TransactionStatus.INITIALIZED) {
      throw new DomainInvariantViolationError(`Cannot clear transaction in status: ${this.status}`);
    }
    this.status = TransactionStatus.CLEARED;
  }

  public markAsRejected(reason: string): void {
    if (this.status !== TransactionStatus.INITIALIZED) {
      throw new DomainInvariantViolationError(`Cannot reject transaction in status: ${this.status}`);
    }
    this.status = TransactionStatus.SETTLEMENT_REJECTED;
    this.rejectionReason = reason;
  }

  public getStatus(): TransactionStatus {
    return this.status;
  }

  public getRejectionReason(): string | null {
    return this.rejectionReason;
  }
}

// ============================================================================
// 2. PORTS: BOUNDARIES & CONTRACTS (ISP, DIP, Protected Variations)
// ============================================================================

export interface ClearingRequestContract {
  readonly referenceId: string;
  readonly amount: bigint;
  readonly currencyCode: string;
  readonly sourceRoute: string;
  readonly targetRoute: string;
}

export interface ClearingResponseContract {
  readonly isSuccess: boolean;
  readonly clearingProtocolRef: string;
  readonly errorCode?: string;
}

// Interface Segregation: Memisahkan pembacaan instrumen settlement dari eksekusinya
export interface SettlementProviderPort {
  submitClearing(request: ClearingRequestContract): Promise<ClearingResponseContract>;
}

export interface TransactionAuditPort {
  recordAuditTrail(transactionId: string, status: TransactionStatus, note?: string): Promise<void>;
}

export interface TransactionRepositoryPort {
  save(transaction: ClearingTransaction): Promise<void>;
  findById(transactionId: string): Promise<ClearingTransaction | null>;
}

// ============================================================================
// 3. PURE FABRICATION: PIPELINE / SERVICE LAYER (High Cohesion, Controller)
// ============================================================================

export class TransactionClearingPipeline {
  constructor(
    private readonly provider: SettlementProviderPort,
    private readonly repository: TransactionRepositoryPort,
    private readonly auditor: TransactionAuditPort
  ) {}

  public async executeTransaction(transaction: ClearingTransaction): Promise<void> {
    const clearingRequest: ClearingRequestContract = {
      referenceId: transaction.transactionId,
      amount: transaction.amount.amountInMinorUnits,
      currencyCode: transaction.amount.currency,
      sourceRoute: transaction.originAccountId,
      targetRoute: transaction.destinationAccountId
    };

    try {
      const response = await this.provider.submitClearing(clearingRequest);

      if (response.isSuccess) {
        transaction.markAsCleared();
      } else {
        transaction.markAsRejected(response.errorCode ?? "UNKNOWN_PROVIDER_SETTLEMENT_ERROR");
      }
    } catch (infrastructureEx) {
      // Invariant: Kegagalan teknis/jaringan tidak boleh merusak state domain; tandai ditolak terkontrol
      transaction.markAsRejected(`INFRASTRUCTURE_UNAVAILABLE: ${(infrastructureEx as Error).message}`);
    }

    // Persistensi state terbaru & pencatatan audit log
    await this.repository.save(transaction);
    await this.auditor.recordAuditTrail(
      transaction.transactionId,
      transaction.getStatus(),
      transaction.getRejectionReason() ?? undefined
    );
  }
}

// ============================================================================
// 4. INFRASTRUCTURE ADAPTERS (LSP-Compliant Implementations)
// ============================================================================

// Provider A: SWIFT Network Provider Adapter
export class SwiftClearingAdapter implements SettlementProviderPort {
  public async submitClearing(request: ClearingRequestContract): Promise<ClearingResponseContract> {
    // Simulasi payload serialisasi MT103/ISO 20022
    if (request.amount > 100_000_000_00n) { // Di atas $1M butuh otorisasi bertingkat
      return {
        isSuccess: false,
        clearingProtocolRef: `SWIFT-ERR-${Date.now()}`,
        errorCode: "EXCEEDS_SWIFT_SINGLE_LEG_LIMIT"
      };
    }

    return {
      isSuccess: true,
      clearingProtocolRef: `SWIFT-${Buffer.from(request.referenceId).toString("hex").substring(0, 12)}`
    };
  }
}

// Provider B: Local Central Bank RTGS Adapter (Substitutability LSP terpenuhi sempurna)
export class CentralBankRtgsAdapter implements SettlementProviderPort {
  public async submitClearing(request: ClearingRequestContract): Promise<ClearingResponseContract> {
    // RTGS tidak memiliki batas $1M tetapi menolak mata uang non-domestik
    if (request.currencyCode !== "IDR") {
      return {
        isSuccess: false,
        clearingProtocolRef: `BI-FAST-REJ-${Date.now()}`,
        errorCode: "CURRENCY_UNSUPPORTED_BY_LOCAL_RTGS"
      };
    }

    return {
      isSuccess: true,
      clearingProtocolRef: `RTGS-REF-${Date.now()}`
    };
  }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Core Payment Settlement Engine di FinTech Tier-1 (Skala 40.000 TPS)

#### 1. Konteks Masalah
Sebuah platform pembayaran memproses transaksi kartu, dompet digital, dan transfer bank instan. Awalnya, implementasi menggunakan satu servis sentral monolitik bernama `PaymentExecutionEngine`.
* **Ukuran Kelas**: 4.800 baris kode.
* **Afferent Coupling**: Dipanggil oleh 42 modul lain.
* **Efferent Coupling**: Bergantung langsung pada MySQL Driver, Redis Cluster, AWS SQS, dan 7 library pihak ketiga untuk payment gateway.
* **Instability ($I$)**:
  $$I = \frac{7}{42 + 7} = \frac{7}{49} \approx 0.14 \text{ (Sangat Stabil / Sangat Kaku)}$$
* Modul berada langsung di **Zone of Pain** ($A = 0.02, I = 0.14, D = |0.02 + 0.14 - 1| = 0.84$).

#### 2. Dampak Kegagalan Produksi
Ketika satu mitra gateway mengubah spesifikasi respons HTTP dari status `200 OK dengan error payload` menjadi `422 Unprocessable Entity`, engine gagal melakukan parsing. Hal ini memicu unhandled rejection yang memicu *thread starvation* di Node.js event loop:
* Latensi P99 melesat dari 45ms ke 12.800ms.
* Database pool exhaust karena koneksi ditahan menunggu timeout HTTP gateway.
* Kerugian transaksi yang terbengkalai mencapai jutaan dolar dalam waktu 18 menit.

#### 3. Rekayasa Perbaikan (Arsitektur Solusi)
Arsitektur dirombak menggunakan metodologi terstruktur:
1. **Penerapan Protected Variations via Anti-Corruption Layer (ACL)**:
   Setiap vendor pembayaran diisolasi di balik *SettlementProviderPort*. Tidak ada kode domain yang membaca struktur JSON mentah vendor.
2. **Pure Fabrication untuk Routing Dinamis**:
   Dibangun `GatewayRoutingStrategy` yang mengimplementasikan circuit-breaker lokal berbasis *error rate slip*.
3. **Penyelarasan LSP**:
   Dibuat serangkaian *Contract Tests* otomatis. Setiap adapter vendor diverifikasi untuk menjamin:
   * Tidak melempar *unchecked exception* liar ke pipeline.
   * Mengembalikan respons deterministik berformat `ClearingResponseContract`.
   * Mematuhi ambang batas *timeout* 800ms secara konsisten.

#### 4. Hasil Metrik Pasca-Refactoring
* **Zone of Pain Berkurang**: Komponen domain inti kini memiliki $A = 0.85, I = 0.12, D = |0.85 + 0.12 - 1| = 0.03$ (Berada persis di Main Sequence).
* **MTTD (Mean Time to Detect)** berkurang 78%.
* Penambahan vendor baru dapat diselesaikan dalam waktu 3 hari kerja (sebelumnya memerlukan waktu 3 minggu) tanpa menyentuh *core domain logic* sama sekali.

---

## 9. Trade-offs: Clean Architecture vs. High Performance

Penerapan prinsip abstraksi tidak gratis. Terdapat kompromi teknis nyata yang harus dianalisis oleh seorang arsitek:

| Dimensi Rekayasa | Pendekatan Dogmatis SOLID/GRASP | Pendekatan Data-Oriented / Flat Minimalist | Evaluasi Kritis untuk Arsitek |
| :--- | :--- | :--- | :--- |
| **CPU Cache Locality** | Buruk. Objek terfragmentasi di heap memory via referensi pointer polimorfik. | Sangat Baik. Array-of-Structures (AoS) atau Structure-of-Arrays (SoA) berurutan. | Untuk trading berlatensi sub-milidetik, abstraksi interface di jalur kritis (*hot-path*) harus dihindari. |
| **Memory Footprint** | Tinggi. Overhead pointer per-instance, *boxing/unboxing*, metadata vtable. | Sangat Rendah. Menggunakan primitive buffers dan zero-allocation structs. | Pada microservices berkapasitas RAM terbatas (container edge), interface berlebihan meningkatkan frekuensi GC. |
| **Maintainability** | Sangat Tinggi. Modifikasi terisolasi, blasting radius bug sangat rendah. | Rendah pada skala enterprise. Logika tersebar di fungsi-fungsi imperatif raksasa. | SOLID sangat menguntungkan untuk sistem berumur panjang dengan tim besar (skala organisasi puluhan squad). |
| **Developer Velocity** | Sedikit lambat di awal (biaya desain interface), sangat cepat dalam jangka panjang. | Sangat cepat di awal (*quick & dirty*), melambat eksponensial seiring waktu. | Gunakan SOLID/GRASP ketat pada Core Domain; gunakan kode flat/pragmatis pada automasi operasional/CRUD sepele. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Interface Pollution (Mencemari Arsitektur dengan ISP Palsu)
* **Gejala**: Setiap kali membuat kelas `UserService`, pengembang selalu membuat `interface IUserService` dengan satu implementasi saja.
* **Akar Masalah**: Salah mengartikan DIP sebagai keharusan membuat antarmuka untuk segala hal.
* **Koreksi**: Interface hanya dibuat jika: (1) Ada lebih dari satu implementasi riil (misal: *Production* vs. *Mock*), atau (2) Digunakan sebagai batasan arsitektural antar boundary/package independen.

### 10.2 Anemic Domain Model Masquerading as SRP
* **Gejala**: Objek domain hanya berisi *getter* dan *setter*. Semua logika validasi dan operasi bisnis ditempatkan di `UserValidationService`, `UserCalculationService`, `UserRegistrationService`.
* **Akar Masalah**: Menganggap entitas yang memiliki metode kalkulasi melanggar SRP. Padahal menurut GRASP *Information Expert*, pemegang data adalah pihak yang paling tepat untuk mengolah data tersebut.
* **Koreksi**: Kembalikan metode ke dalam domain entity. SRP berlaku pada level tanggung jawab bisnis (*reasons to change*), bukan pembatasan bahwa satu kelas hanya boleh memiliki satu method.

### 10.3 Pelanggaran Kontrak Subtipe (LSP Violation via Runtime Type Checks)
* **Gejala**: Ditemukannya blok pengecekan tipe data runtime:
  ```typescript
  // PELANGGARAN KERAS LSP & OCP
  function processPayout(account: BankAccount) {
    if (account instanceof HighYieldSavingsAccount) {
      account.applySpecialReserveRate();
    }
    account.withdraw();
  }
  ```
* **Koreksi**: Jika Anda perlu memeriksa tipe subkelas riil, abstraksi Anda telah bocor. Angkat perilaku tersebut ke interface dasar melalui delegasi polimorfik atau gunakan pola *Visitor* jika traversal hierarki tidak terhindarkan.

---

## 11. Best Practices & Production Checklist

Gunakan checklist ini saat *Pull Request Review* arsitektur:

### Desain & Struktur
- [ ] Entitas Domain tidak mengimpor modul dari layer Infrastruktur (database, HTTP, external client SDK).
- [ ] Tidak ada metode yang menerima interface besar jika hanya menggunakan satu atau dua properti darinya (ISP).
- [ ] Semua invariant domain dilindungi di level constructor atau factory method; instansiasi ilegal tidak mungkin terjadi.
- [ ] Pola *Pure Fabrication* digunakan untuk logika yang jika ditempatkan di domain model akan mengotori model dengan dependensi sistem operasi atau jaringan.

### Verifikasi Substitusi (LSP)
- [ ] Subkelas atau adapter turunan tidak melempar tipe exception baru yang tidak diantisipasi oleh caller.
- [ ] Preconditions pada subkelas tidak lebih ketat daripada preconditions pada superclass.
- [ ] Postconditions pada subkelas tidak lebih longgar daripada postconditions pada superclass.

### Pipeline Otomasi & Metrik
- [ ] Analisis dependensi dijalankan pada CI (`dependency-cruiser` atau semacamnya) untuk menggagalkan build jika ada dependensi terbalik (*circular dependency* atau core mengimpor infra).
- [ ] Ambang batas *Cyclomatic Complexity* dibatasi maksimal 10 per method.

---

## 12. Hands-on Practice

Implementasikan restrukturisasi modul pembayaran legacy yang melanggar OCP dan Information Expert.

### Direktori Kerja
Buat direktori berikut di komputer lokal Anda:
```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
npm init -y
npm install typescript @types/node ts-node --save-dev
npx tsc --init
```

### Langkah 1: Buat Legacy Monolith (`src/legacy.ts`)
```typescript
// src/legacy.ts
// Kasus: Kelas ini melanggar SRP, OCP, LSP, dan tidak menggunakan Information Expert.
export class LegacyBillingSystem {
  public process(customerType: string, amount: number, dbConnection: any) {
    let discount = 0;
    // Pelanggaran OCP: Perlu edit kelas jika ada tipe pelanggan baru
    if (customerType === "REGULAR") {
      discount = 0.05;
    } else if (customerType === "PREMIUM") {
      discount = 0.15;
    } else if (customerType === "VIP") {
      discount = 0.30;
    }

    const finalAmount = amount - (amount * discount);
    console.log(`Processing charge of $${finalAmount}`);

    // Pelanggaran DIP: Direct Coupling ke objek database
    dbConnection.query(`INSERT INTO invoices (total) VALUES (${finalAmount})`);
  }
}
```

### Langkah 2: Rekayasa Arsitektur Baru (`src/refactored.ts`)
Terapkan:
* **Information Expert**: Objek diskon mandiri.
* **OCP/Protected Variations**: Strategi kalkulasi diskon polimorfik.
* **DIP**: Abstraksi database via Interface Port.

```typescript
// src/refactored.ts

// 1. Domain Types & Invariants
export interface DiscountStrategy {
  calculateDiscountedAmount(baseAmountMinorUnits: bigint): bigint;
}

export class RegularDiscount implements DiscountStrategy {
  calculateDiscountedAmount(baseAmountMinorUnits: bigint): bigint {
    return baseAmountMinorUnits - ((baseAmountMinorUnits * 5n) / 100n);
  }
}

export class VipDiscount implements DiscountStrategy {
  calculateDiscountedAmount(baseAmountMinorUnits: bigint): bigint {
    return baseAmountMinorUnits - ((baseAmountMinorUnits * 30n) / 100n);
  }
}

// 2. Port Abstractions (DIP)
export interface InvoicePersistencePort {
  persistInvoice(id: string, amountMinorUnits: bigint): Promise<void>;
}

// 3. Information Expert
export class BillingInvoice {
  constructor(
    public readonly invoiceId: string,
    public readonly baseAmountMinorUnits: bigint,
    private readonly discountPolicy: DiscountStrategy
  ) {}

  public computePayableTotal(): bigint {
    return this.discountPolicy.calculateDiscountedAmount(this.baseAmountMinorUnits);
  }
}

// 4. Pure Fabrication (Application Coordinator)
export class BillingCoordinatorService {
  constructor(private readonly persistenceAdapter: InvoicePersistencePort) {}

  public async processInvoice(invoice: BillingInvoice): Promise<bigint> {
    const payableAmount = invoice.computePayableTotal();
    await this.persistenceAdapter.persistInvoice(invoice.invoiceId, payableAmount);
    return payableAmount;
  }
}
```

### Langkah 3: Eksekusi dan Verifikasi (`src/main.ts`)
```typescript
// src/main.ts
import { 
  BillingInvoice, 
  BillingCoordinatorService, 
  VipDiscount, 
  InvoicePersistencePort 
} from "./refactored";

class InMemoryInvoiceAdapter implements InvoicePersistencePort {
  public records = new Map<string, bigint>();

  async persistInvoice(id: string, amountMinorUnits: bigint): Promise<void> {
    this.records.set(id, amountMinorUnits);
    console.log(`[Adapter] Persisted invoice ${id} with value: $${Number(amountMinorUnits) / 100}`);
  }
}

async function run() {
  const adapter = new InMemoryInvoiceAdapter();
  const coordinator = new BillingCoordinatorService(adapter);

  // Buat tagihan $100.00 (10000 minor units) dengan diskon VIP (30%)
  const invoice = new BillingInvoice("INV-2026-001", 10000n, new VipDiscount());
  const finalCharge = await coordinator.processInvoice(invoice);

  console.log(`Final Charge Calculated: $${Number(finalCharge) / 100}`);
  console.assert(finalCharge === 7000n, "Perhitungan diskon VIP salah!");
  console.log("Eksekusi berhasil tanpa pelanggaran prinsip desain!");
}

run().catch(console.error);
```

Jalankan di terminal:
```bash
npx ts-node src/main.ts
```

---

## 13. Exercise

### Level Easy
Diberikan cuplikan berikut yang melanggar **Single Responsibility Principle** dan **High Cohesion**:
```typescript
class UserProfile {
  constructor(public id: string, public email: string) {}
  updateEmail(newEmail: string): void { this.email = newEmail; }
  formatAsHtml(): string { return `<div>${this.email}</div>`; }
  sendWelcomeEmail(): void { /* SMTP connection logic */ }
}
```
*Tugas*: Pisahkan menjadi entitas bisnis murni dan dua kelas terpisah menggunakan pola *Pure Fabrication* untuk rendering dan pengiriman email.

### Level Medium
Rancang arsitektur penyimpanan file multi-cloud (*Multi-Cloud Blob Storage Adapter*) yang menerapkan **Interface Segregation Principle** dan **Protected Variations**:
* Sub-sistem harus mendukung S3, Google Cloud Storage, dan Local Disk.
* Klien pembaca file hanya boleh bergantung pada interface yang memiliki method `readStream(path: string)`.
* Klien pengunggah file hanya boleh bergantung pada method `uploadStream(path: string, stream: any)`.
* Tidak ada klien yang boleh terekspos konfigurasi autentikasi API masing-masing cloud provider.

### Level Hard
Bangun sebuah event engine berkinerja tinggi yang memproses order routing finansial. 
* Terapkan **Liskov Substitution Principle** secara ketat pada strategi routing order (Normal Routing, High-Frequency Trading Routing, Contingency Dark-Pool Routing).
* Tulis sebuah kelas *test harness* yang membuktikan bahwa tidak ada sub-strategi yang memperketat pra-kondisi (misal: secara ilegal menolak format order standar) atau melonggarkan pasca-kondisi (misal: mengembalikan status order belum selesai yang melanggar kontrak supertipe).

---

## 14. Challenge: Arsitektur Matching Engine Bebas Alokasi Memori

### Skenario Kasus Riil
Sebuah bursa komoditas aset digital berkecepatan tinggi meminta Anda merancang arsitektur inti dari *Order Matching Engine*. 
Karakteristik teknis sistem:
* Throughput: 150.000 order per detik.
* P99 Latency SLA: $\le 250 \text{ microseconds}$.
* Sistem berjalan pada runtime yang memiliki garbage collection (Go atau Node.js/V8).

### Masalah
Penerapan *SOLID* biasa dengan membuat interface di setiap layer dan menginstansiasi objek `OrderBookEntry` baru untuk setiap order memicu alokasi heap masif. Garbage Collector menyebabkan siklus *Stop-the-World* setiap 4 detik, yang menyebabkan lonjakan latensi hingga 80ms (pelanggaran fatal terhadap SLA).

### Misi Arsitektural Anda
Rancang arsitektur sistem yang memenuhi kriteria berikut tanpa membuang keunggulan keterpeliharaan SOLID & GRASP:
1. **Protected Variations**: Core Engine harus mampu mengganti algoritma matching (Price-Time Priority vs. Pro-Rata Allocation) secara dinamis tanpa kompilasi ulang.
2. **Zero Allocation Hot-Path**: Pemanggilan matching polimorfik tidak boleh memicu instansiasi objek baru di heap memori selama pencocokan order berlangsung.
3. **Information Expert vs DOD**: Bagaimana Anda mendamaikan prinsip *Information Expert* (yang menyatukan data dan perilaku dalam satu kelas/objek) dengan paradigma *Data-Oriented Design* (yang menuntut pemisahan array data primitif pipih untuk memaksimalkan *CPU L1/L2 cache hit rate*)?

*Output yang Diharapkan*: Dokumen spesifikasi desain arsitektur, diagram struktur memori, dan sketsa antarmuka TypeScript/Go yang membuktikan bagaimana pemisahan tanggung jawab tercapai tanpa mengorbankan siklus GC.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic
1. Apa perbedaan mendasar antara prinsip GRASP *Protected Variations* dan prinsip SOLID *Open/Closed Principle*?
2. Bagaimana pelanggaran *Interface Segregation Principle* secara langsung memperbesar *blasting radius* (dampak kerusakan) bug pada sistem monolitik?
3. Berikan contoh kasus nyata kapan sebuah kelas harus dibuat menggunakan prinsip GRASP *Pure Fabrication*!
4. Apa yang dimaksud dengan *Anemic Domain Model*, dan prinsip GRASP mana yang dilanggar secara langsung oleh pola tersebut?
5. Mengapa penggunaan kata kunci `instanceof` atau pengecekan tipe konkrit runtime di dalam blok logika bisnis dianggap sebagai bau kode (*code smell*) pelanggaran LSP?

### 15.2 Pertanyaan Intermediate
6. Bagaimana metrik *Instability Index* ($I$) dihitung, dan apa bahaya arsitektural dari sebuah modul yang memiliki nilai $A = 0$ dan $I = 0$?
7. Pada tingkat sistem operasi dan prosesor, apa dampak dari *deep inheritance tree* terhadap *branch prediction* dan instruksi kompilasi *dynamic dispatch*?
8. Kapan penerapan prinsip *Dependency Inversion Principle* (DIP) justru berubah menjadi *over-engineering* (*Interface Pollution*)? Jelaskan batasannya!
9. Jelaskan bagaimana prinsip GRASP *Indirection* bekerja berdampingan dengan *Low Coupling* untuk mengamankan komunikasi antar dua Bounded Context pada arsitektur Microservices!
10. Bagaimana aturan Liskov Substitution Principle terkait pra-kondisi (*preconditions*) dan pasca-kondisi (*postconditions*) pada metode subkelas?

### 15.3 Skenario Kasus Produksi
11. **Skenario 1**: Sebuah tim mengklaim telah mematuhi SRP dengan memecah sebuah domain model `User` menjadi 12 kelas: `UserEmailUpdater`, `UserPasswordHasher`, `UserAddressValidator`, dan seterusnya. Setiap kelas hanya memiliki tepat satu metode publik `execute()`. Bagaimana Anda sebagai Lead Architect mengevaluasi desain ini dari perspektif *High Cohesion* dan *Cognitive Load*?
12. **Skenario 2**: Anda memiliki pipeline sinkronisasi transaksi bank. Kelas dasar `BankTransferAdapter` mendefinisikan metode:
    ```typescript
    transfer(amount: bigint, recipient: string): Promise<TransferReceipt>;
    ```
    Sebuah adapter baru untuk sistem warisan perbankan, `LegacyBatchTransferAdapter`, mengimplementasikan metode tersebut tetapi melempar exception: `"Asynchronous transfer not supported. Call executeBatch() at midnight"`. Analisis prinsip mana yang dilanggar dan berikan solusi rekonstruksi interface-nya!
13. **Skenario 3**: Sebuah microservice mengalami lonjakan memori secara eksponensial di bawah beban 10.000 koneksi WebSocket konkuren. Profiling memori menunjukkan bahwa 60% alokasi heap dihabiskan oleh closure dan dynamic proxy instance dari framework Dependency Injection yang membungkus antarmuka domain internal. Bagaimana Anda mendesain ulang arsitektur injeksi dependensi sistem agar tetap modular namun hemat memori?

---

## 16. Summary

* **SOLID dan GRASP Bukanlah Dogma Religius**: Prinsip-prinsip ini adalah instrumen mitigasi risiko finansial dan teknis akibat perubahan perangkat lunak (*cost of change*).
* **GRASP Memberi Tanggung Jawab, SOLID Mempertegas Batasan**: Gunakan GRASP (*Information Expert, Creator, Controller*) untuk menata lokasi kode secara intuitif; gunakan SOLID (*SRP, OCP, LSP, ISP, DIP*) untuk mengunci kontrak kompilasi dan isolasi modul.
* **Perhatikan Efek Mekanis**: Setiap interface dan dynamic dispatch memiliki konsekuensi runtime (*vtable lookup*, degradasi *cache locality*, dan beban GC). Di sistem berskala jutaan TPS, arsitektur harus menyeimbangkan kemurnian desain berorientasi objek dengan pendekatan *data-oriented*.
* **Ukur Kesehatan Arsitektur**: Jangan berasumsi. Gunakan metrik Robert C. Martin ($A, I, D$) untuk memverifikasi posisi modul Anda dari *Zone of Pain* dan *Zone of Uselessness* secara otomatis di pipeline CI Anda.