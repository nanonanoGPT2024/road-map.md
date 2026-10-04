# KATEGORI 06: ARCHITECTURE & SYSTEM DESIGN
## TOPIK 02: Software Design & Architecture
### MODUL 01: Prinsip Desain Tingkat Kode: Object-Oriented, SOLID, & GRASP

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `ARC-SDA-0201`
* **Nama Modul**: Prinsip Desain Tingkat Kode: Object-Oriented, SOLID, & GRASP
* **Tingkat Kesulitan**: Intermediate to Advanced
* **Prasyarat**:
  * Pemahaman mendalam tentang Object-Oriented Programming (Class, Interface, Polymorphism, Inheritance, Encapsulation).
  * Pengalaman minimal 1 tahun menulis kode produksi dalam bahasa bertipe statis (TypeScript, Java, C#, atau Go).
  * Pemahaman dasar tentang siklus hidup refactoring dan unit testing.
* **Target Audiens**: Software Engineers, Backend Developers, Technical Lead, dan aspiring Software/Solution Architects.
* **Estimasi Waktu Penyelesaian**: 8 jam teori terpandu + 12 jam implementasi hands-on.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik memiliki kemampuan terukur untuk:

1. **Menganalisis dan Membedah Pelanggaran Desain**: Mengidentifikasi *code smells* struktural dan pelanggaran prinsip SOLID serta anti-pattern dalam basis kode yang sudah ada secara sistematis.
2. **Menerapkan 5 Prinsip SOLID Secara Presisi**: Merekayasa ulang arsitektur kelas agar mematuhi *Single Responsibility*, *Open-Closed*, *Liskov Substitution*, *Interface Segregation*, dan *Dependency Inversion* tanpa menimbulkan *over-engineering*.
3. **Mengorkestrasi Tanggung Jawab Menggunakan 9 Pola GRASP**: Menentukan alokasi *responsibility* pada objek bisnis menggunakan pola GRASP (*Information Expert*, *Creator*, *Controller*, *Low Coupling*, *High Cohesion*, *Polymorphism*, *Pure Fabrication*, *Indirection*, *Protected Variations*).
4. **Memvalidasi Kontrak Subtipe (Behavioral Subtyping)**: Membuktikan kepatuhan Liskov Substitution Principle menggunakan aturan *Preconditions*, *Postconditions*, dan *Invariants* matematika/logika formal.
5. **Mengintegrasikan SOLID dan GRASP**: Mengkombinasikan pola penalaran tanggung jawab GRASP sebagai pondasi konseptual untuk menghasilkan implementasi struktural yang memenuhi standar SOLID.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                         ┌────────────────────────────────────────┐
                         │      DESAIN TINGKAT KODE BERKUALITAS   │
                         └───────────────────┬────────────────────┘
                                             │
               ┌─────────────────────────────┴─────────────────────────────┐
               ▼                                                           ▼
┌──────────────────────────────┐                           ┌──────────────────────────────┐
│        GRASP PATTERNS        │                           │       SOLID PRINCIPLES       │
│ (Alokasi Tanggung Jawab)     │                           │ (Struktur & Evolusi Kelas)   │
└──────────────┬───────────────┘                           └──────────────┬───────────────┘
               │                                                           │
 ┌─────────────┴─────────────┐                               ┌─────────────┴─────────────┐
 │ • Information Expert      │                               │ • Single Responsibility   │
 │ • Creator                 │                               │ • Open-Closed             │
 │ • Controller              │                               │ • Liskov Substitution     │
 │ • Low Coupling            │                               │ • Interface Segregation   │
 │ • High Cohesion           │                               │ • Dependency Inversion    │
 │ • Polymorphism            │                               └───────────────────────────┘
 │ • Pure Fabrication        │                                             ▲
 │ • Indirection             │                                             │
 │ • Protected Variations    │                                             │
 └─────────────┬─────────────┘                                             │
               │                                                           │
               └────────────────── Fondasi Konseptual ─────────────────────┘
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Kode yang buruk (*spaghetti code*) jarang bermula dari niat buruk. Ia hampir selalu berakar dari ketidakmampuan tim rekayasa perangkat lunak dalam mendistribusikan tanggung jawab (*responsibilities*) secara terukur ketika kompleksitas sistem bertambah. Tanpa fondasi prinsip desain tingkat kode:

1. **Rigidity (Kekakuan)**: Setiap perubahan fungsionalitas kecil memaksa rentetan perubahan tak terduga pada lusinan modul lain (*cascade effect*).
2. **Fragility (Kerapuhan)**: Memperbaiki *bug* di satu modul memicu kerusakan fatal pada modul terpencil yang secara logis tidak berhubungan.
3. **Immobility (Ketidakmampuan Berpindah)**: Komponen kode tidak dapat digunakan kembali (*reusable*) di bagian lain atau sistem baru karena terikat erat (*tightly coupled*) dengan konteks aslinya.
4. **Viscosity (Viskositas Arsitektural)**: Melakukan hal yang benar secara arsitektural menjadi jauh lebih sulit daripada melakukan *hacky workaround*. Akibatnya, degradasi kualitas terjadi secara eksponensial.

Menguasai SOLID dan GRASP membedakan seorang *code-monkey* yang sekadar membuat fitur berjalan dari seorang *Software Engineer* yang membangun aset perangkat lunak bernilai tinggi, adaptif terhadap evolusi bisnis, dan meminimalkan *Cost of Change* sepanjang *software development lifecycle* (SDLC).

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Object-Oriented Principles: The Bedrock
Fondasi pemrograman berorientasi objek modern bukan sekadar sintaks `class`, melainkan empat pilar ortogonal:
* **Encapsulation**: Menyembunyikan *state* internal dan invariant mutasi, hanya mengekspos protokol interaksi kontraktual.
* **Abstraction**: Menyederhanakan kompleksitas dengan menyembunyikan detail teknis di balik representasi antarmuka deklaratif.
* **Inheritance**: Mekanisme pembagian kode dan taksonomi tipe (namun harus tunduk pada *composition over inheritance*).
* **Polymorphism**: Kemampuan mengeksekusi perilaku yang berbeda melalui antarmuka seragam tunggal saat *runtime*.

---

### 2. Prinsip SOLID

#### S — Single Responsibility Principle (SRP)
> *"A module should be responsible to one, and only one, actor."* — Robert C. Martin.

*Responsibility* diukur bukan dari apa yang dieksekusi metode secara teknis, melainkan kepada **aktor bisnis** mana modul tersebut melapor. Jika kelas `OrderService` menangani kalkulasi diskon (aktor: Tim Finansial/Pemasaran), persistensi SQL (aktor: Tim DBA/Infrastruktur), dan pengiriman notifikasi email (aktor: Tim Operasional), maka kelas tersebut memiliki tiga alasan untuk berubah (*multiple axes of change*).

#### O — Open-Closed Principle (OCP)
> *"Software entities (classes, modules, functions) should be open for extension, but closed for modification."* — Bertrand Meyer.

Sistem perangkat lunak yang matang berevolusi melalui penambahan kode baru (*extension via polymorphism/strategy*), bukan dengan membedah dan mengubah kode sumber lama yang telah berjalan stabil dan teruji (*modification*).

#### L — Liskov Substitution Principle (LSP)
> *"Let $\Phi(x)$ be a property provable about objects $x$ of type $T$. Then $\Phi(y)$ should be true for objects $y$ of type $S$ where $S$ is a subtype of $T$."* — Barbara Liskov.

Subtipe tidak boleh merusak invariant atau ekspektasi yang dijamin oleh supertipe. Secara spesifik:
* **Preconditions tidak boleh diperketat** pada subtipe (subtipe tidak boleh menuntut lebih banyak dari pemanggil).
* **Postconditions tidak boleh diperlemah** pada subtipe (subtipe harus mengembalikan jaminan minimal yang sama).
* **Invariants tipe dasar harus dipertahankan** sepenuhnya.
* **History Rule**: Subtipe tidak boleh memodifikasi *state* melalui metode baru yang tidak diizinkan oleh supertipe (misal: mutable subtype dari immutable supertype).

#### I — Interface Segregation Principle (ISP)
> *"Clients should not be forced to depend upon interfaces that they do not use."*

Lebih baik memiliki banyak antarmuka kecil yang spesifik untuk klien (*role interfaces*) daripada satu antarmuka raksasa (*fat interface*). ISP mencegah efek *ripple* ketika perubahan metode yang tidak dibutuhkan oleh klien memaksanya untuk dikompilasi ulang atau dites ulang.

#### D — Dependency Inversion Principle (DIP)
> *"High-level modules should not depend on low-level modules. Both should depend on abstractions. Abstractions should not depend on details. Details should depend on abstractions."*

DIP membalikkan alur ketergantungan konvensional. Logika domain inti (*high-level policy*) tidak boleh mengimpor driver database, pustaka parsing JSON, atau protokol jaringan (*low-level detail*). Keduanya harus bergantung pada abstraksi antarmuka (*interface*), di mana implementasi detail berada di lapisan luar yang tunduk pada kontrak lapisan dalam.

---

### 3. General Responsibility Assignment Software Patterns (GRASP)
Dirumuskan oleh Craig Larman, GRASP adalah metodologi berbasis pola mental (*mental patterns*) untuk mendistribusikan tanggung jawab (*responsibilities*) ke dalam objek-objek kolaborator:

1. **Information Expert**: Berikan tanggung jawab kepada kelas yang memiliki informasi yang paling lengkap untuk memenuhinya.
2. **Creator**: Objek $A$ harus membuat objek $B$ jika: $A$ mengagregasi $B$, $A$ mencatat $B$, $A$ menggunakan $B$ secara intensif, atau $A$ memiliki data inisialisasi untuk $B$.
3. **Controller**: Objek pertama di luar antarmuka pengguna yang menerima dan mengoordinasikan operasi sistem (*system operation*). Bertindak sebagai fasilitator alur, bukan penampung logika domain.
4. **Low Coupling**: Ukuran seberapa kuat sebuah elemen terhubung dengan, memiliki pengetahuan tentang, atau bergantung pada elemen lain. Tujuannya adalah meminimalkan dependensi yang tidak esensial.
5. **High Cohesion**: Ukuran seberapa fokus dan terikatnya fungsionalitas di dalam suatu modul. Tanggung jawab yang berhubungan erat harus dikelompokkan bersama.
6. **Polymorphism**: Ketika perilaku bervariasi berdasarkan tipe/kategori objek, distribusikan tanggung jawab tersebut menggunakan operasi polimorfik, bukan percabangan kondisional (`if/else` atau `switch`).
7. **Pure Fabrication**: Kelas buatan yang tidak merepresentasikan konsep domain riil (misal: *Repository*, *Service*, *Adapter*) yang diciptakan untuk menjaga *Low Coupling* dan *High Cohesion* ketika *Information Expert* gagal memenuhi batas arsitektur.
8. **Indirection**: Menugaskan tanggung jawab ke objek perantara untuk memutus hubungan langsung antar dua komponen, memfasilitasi decoupling.
9. **Protected Variations**: Identifikasi titik-titik variasi atau instabilitas yang diprediksi akan terjadi, bungkus menggunakan antarmuka, dan gunakan polimorfisme untuk menciptakan struktur yang stabil terhadap perubahan.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

Implementasi integrasi SOLID dan GRASP bekerja melalui alur penataan tanggung jawab terstruktur:

```
[Kebutuhan Bisnis Baru]
          │
          ▼
┌───────────────────┐
│ 1. Tentukan Aktor │ ───(SRP)───► Pisahkan Boundary Konteks Aktor
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 2. Petakan State  │ ───(Information Expert & Creator)───► Alokasikan Data & Lifecycle
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 3. Identifikasi   │ ───(Protected Variations & OCP)───► Isolasi Titik Variabilitas
│    Variabilitas   │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 4. Tentukan Batas │ ───(ISP & DIP)───► Definisikan Role Interfaces
│    Kontrak        │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 5. Validasi Tipe  │ ───(LSP)───► Verifikasi Pre/Postconditions & Invariants
└───────────────────┘
```

1. **Identifikasi Kebutuhan & Tanggung Jawab**: Ambil *use-case* bisnis dan ekstrak tanggung jawab kognitif (*knowing*) dan eksekutif (*doing*).
2. **Gunakan Information Expert & Creator**: Tempatkan *state* dan algoritma dasar pada entitas yang memiliki datanya secara alami.
3. **Deteksi Viskositas & Variabilitas**: Jika suatu algoritma atau aturan bisnis memiliki kemungkinan berubah atau memiliki banyak strategi:
   * Terapkan **Protected Variations** (GRASP) dengan membungkusnya dalam antarmuka.
   * Ini secara otomatis memenuhi **Open-Closed Principle** (SOLID).
4. **Isolasi Infrastruktur Melalui Pure Fabrication & Indirection**:
   * Jangan biarkan entitas domain menyentuh I/O (Database, API pihak ketiga).
   * Ciptakan kelas tiruan non-domain (*Pure Fabrication*) seperti `OrderRepository` atau `PaymentGatewayAdapter`.
   * Ini mereduksi *coupling* dan menegakkan **Single Responsibility Principle**.
5. **Bangun Kontrak Berorientasi Klien**:
   * Jangan buat antarmuka monolitik. Terapkan **Interface Segregation Principle**.
   * Hubungkan modul tingkat tinggi ke modul tingkat rendah hanya melalui abstraksi kontraktual ini (**Dependency Inversion Principle**).
6. **Audit Substitusi Subtipe**:
   * Verifikasi bahwa setiap implementasi antarmuka/subkelas mematuhi kontrak secara semantik (**Liskov Substitution Principle**). Subtipe dilarang melempar `NotSupportedException` untuk metode yang diwarisi.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Pelanggaran SOLID & Anti-Pattern (God Object / Spaghetti Architecture)

```
+-----------------------------------------------------------------------------------+
|                                 OrderController                                   |
| (Violations: SRP, OCP, DIP, Fat Interface, Low Cohesion, High Coupling)           |
+-----------------------------------------------------------------------------------+
| - connectionString: string                                                        |
| - httpClient: HttpClient                                                          |
+-----------------------------------------------------------------------------------+
| + checkout(orderData: JSON): void                                                 |
|     |-- 1. Parsing & Validation                                                   |
|     |-- 2. Calculate tax based on country code (switch-case)  <-- Breaks OCP      |
|     |-- 3. SQL Query: INSERT INTO orders VALUES (...)         <-- Breaks SRP/DIP  |
|     |-- 4. Execute HTTP Post to Stripe API                    <-- Breaks SRP/DIP  |
|     |-- 5. Construct HTML string and send SMTP email          <-- Breaks SRP/DIP  |
+-----------------------------------------------------------------------------------+
          |                     |                      |                      |
          v                     v                      v                      v
    Direct Database       Stripe API             SMTP Server            Direct Logs
```

### 2. Arsitektur Hasil Refactoring: Harmonisasi SOLID & GRASP

```
                           [ Controller ]
                       CheckoutController (GRASP: Controller)
                                 │
                                 │ calls
                                 ▼
                     [ Pure Fabrication / High Cohesion ]
                           CheckoutUseCase
                                 │
         ┌───────────────────────┼───────────────────────┐
         │ (uses)                │ (uses)                │ (uses)
         ▼                       ▼                       ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   TaxCalculator  │    │  IPaymentGateway │    │ IOrderRepository │
│   (GRASP: PV)    │    │  (GRASP: Indir)  │    │  (GRASP: PF)     │
│   (SOLID: OCP)   │    │  (SOLID: DIP)    │    │  (SOLID: DIP)    │
└────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘
         │                       │                       │
 ┌───────┴───────┐               │                       │
 │ (implements)  │               │ (implements)          │ (implements)
 ▼               ▼               ▼                       ▼
┌────────┐  ┌────────┐  ┌──────────────────┐    ┌──────────────────┐
│ IDTax  │  │ USTax  │  │ StripeAdapter    │    │ PostgresOrderRepo│
│ (LSP)  │  │ (LSP)  │  │ (LSP / DIP)      │    │ (LSP / DIP)      │
└────────┘  └────────┘  └──────────────────┘    └──────────────────┘

   Legend:
   - PV    : Protected Variations
   - PF    : Pure Fabrication
   - Indir : Indirection
   - OCP   : Open-Closed Principle
   - DIP   : Dependency Inversion Principle
   - LSP   : Liskov Substitution Principle
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut demonstrasi pelanggaran dan perbaikan **Liskov Substitution Principle (LSP)** yang sering disalahpahami dalam domain geometri/arsitektur dasar.

### Kode Buruk: Pelanggaran LSP Klasik (Rectangle-Square Anti-Pattern)

```typescript
// VIOLATION: Square memodifikasi ekspektasi perilaku Rectangle
class Rectangle {
  protected _width: number = 0;
  protected _height: number = 0;

  public setWidth(width: number): void {
    this._width = width;
  }

  public setHeight(height: number): void {
    this._height = height;
  }

  public getWidth(): number {
    return this._width;
  }

  public getHeight(): number {
    return this._height;
  }

  public getArea(): number {
    return this._width * this._height;
  }
}

class Square extends Rectangle {
  public override setWidth(width: number): void {
    this._width = width;
    this._height = width; // Efek samping tak terduga bagi klien supertipe!
  }

  public override setHeight(height: number): void {
    this._width = height; // Efek samping tak terduga bagi klien supertipe!
    this._height = height;
  }
}

// Client code yang membuktikan kerusakan substitusi
function resizeAndCalculateArea(rect: Rectangle): void {
  rect.setWidth(5);
  rect.setHeight(10);
  
  // Ekspektasi: 5 * 10 = 50
  // Realita jika Square diberikan: 10 * 10 = 100 -> LSP BROKEN!
  if (rect.getArea() !== 50) {
    throw new Error(`Integritas Kontrak Rusak! Luas: ${rect.getArea()}`);
  }
}
```

### Refactoring Bersih: Sesuai LSP & ISP

Persegi panjang dan bujur sangkar memiliki invarian geometri yang berbeda dalam konteks mutasi. Maka, jangan paksakan *inheritance* mutasi jika tidak memenuhi kontrak perilaku. Ubah menjadi antarmuka pembacaan murni (*role interface*) atau pisahkan mutator.

```typescript
// Kontrak bentuk geometri murni: Read-Only (LSP Safe)
interface Shape {
  getArea(): number;
}

class Rectangle implements Shape {
  constructor(
    private readonly width: number,
    private readonly height: number
  ) {
    if (width <= 0 || height <= 0) {
      throw new Error("Dimensi harus lebih besar dari nol.");
    }
  }

  public getArea(): number {
    return this.width * this.height;
  }
}

class Square implements Shape {
  constructor(private readonly side: number) {
    if (side <= 0) {
      throw new Error("Panjang sisi harus lebih besar dari nol.");
    }
  }

  public getArea(): number {
    return this.side * this.side;
  }
}

// Client mengonsumsi abstraksi tanpa asumsi mutasi implisit
function printArea(shape: Shape): void {
  console.log(`Luas objek: ${shape.getArea()}`);
}

const rect: Shape = new Rectangle(5, 10);
const sq: Shape = new Square(5);

printArea(rect); // Output: Luas objek: 50
printArea(sq);   // Output: Luas objek: 25
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus dunia nyata: Pemrosesan Pembayaran Transaksi E-Commerce Tingkat Produksi.
Kita akan mengimplementasikan skenario ini dengan menerapkan secara komprehensif seluruh prinsip **SOLID** dan pola **GRASP**.

### Domain Entities & Value Objects (Information Expert)

```typescript
// Value Object: Uang dengan Invariant Kuat
export class Money {
  constructor(
    public readonly amount: number,
    public readonly currency: string
  ) {
    if (amount < 0) {
      throw new Error("Jumlah uang tidak boleh bernilai negatif.");
    }
    if (!currency || currency.length !== 3) {
      throw new Error("Mata uang harus 3 digit kode ISO (e.g. IDR, USD).");
    }
  }

  public add(other: Money): Money {
    if (this.currency !== other.currency) {
      throw new Error(`Incompatible currency: ${this.currency} vs ${other.currency}`);
    }
    return new Money(this.amount + other.amount, this.currency);
  }
}

// Domain Entity: OrderItem
export class OrderItem {
  constructor(
    public readonly productId: string,
    public readonly unitPrice: Money,
    public readonly quantity: number
  ) {
    if (quantity <= 0) {
      throw new Error("Kuantitas barang harus lebih dari 0.");
    }
  }

  // GRASP: Information Expert (OrderItem tahu harga dan jumlahnya)
  public getSubtotal(): Money {
    return new Money(this.unitPrice.amount * this.quantity, this.unitPrice.currency);
  }
}

// Domain Entity: Order (Information Expert & Creator)
export class Order {
  private readonly items: OrderItem[] = [];
  private isPaid: boolean = false;

  constructor(
    public readonly orderId: string,
    public readonly customerId: string
  ) {}

  // GRASP: Creator (Order membuat dan mengelola OrderItem miliknya)
  public addItem(productId: string, unitPrice: Money, quantity: number): void {
    if (this.isPaid) {
      throw new Error("Tidak dapat menambah barang ke pesanan yang sudah dibayar.");
    }
    this.items.push(new OrderItem(productId, unitPrice, quantity));
  }

  // GRASP: Information Expert
  public calculateTotal(): Money {
    if (this.items.length === 0) {
      return new Money(0, "IDR");
    }
    const baseCurrency = this.items[0].unitPrice.currency;
    return this.items.reduce(
      (total, item) => total.add(item.getSubtotal()),
      new Money(0, baseCurrency)
    );
  }

  public markAsPaid(): void {
    if (this.isPaid) {
      throw new Error("Pesanan ini sudah berstatus lunas.");
    }
    this.isPaid = true;
  }

  public getItems(): readonly OrderItem[] {
    return Object.freeze([...this.items]);
  }

  public getPaymentStatus(): boolean {
    return this.isPaid;
  }
}
```

### Abstraksi dan Kontrak (ISP & DIP & Protected Variations)

```typescript
// SOLID: ISP - Interface kecil yang spesifik untuk domain audit
export interface IAuditable {
  logAudit(event: string, meta: Record<string, unknown>): Promise<void>;
}

// SOLID: ISP - Interface untuk persistensi transaksi
export interface IOrderRepository {
  findById(orderId: string): Promise<Order | null>;
  save(order: Order): Promise<void>;
}

export interface PaymentResult {
  readonly success: boolean;
  readonly transactionId: string;
  readonly failureReason?: string;
}

// SOLID: DIP & GRASP: Protected Variations
// Menyembunyikan kompleksitas komunikasi vendor payment di balik abstraksi
export interface IPaymentGateway {
  charge(amount: Money, token: string): Promise<PaymentResult>;
}

// SOLID: OCP & Strategy Pattern via Protected Variations
// Aturan perhitungan pajak dapat diekstensikan tanpa mengubah Core Processor
export interface ITaxStrategy {
  calculateTax(baseAmount: Money): Money;
}

export class IndonesianDomesticTaxStrategy implements ITaxStrategy {
  public calculateTax(baseAmount: Money): Money {
    // PPN 11%
    return new Money(baseAmount.amount * 0.11, baseAmount.currency);
  }
}

export class TaxExemptStrategy implements ITaxStrategy {
  public calculateTax(baseAmount: Money): Money {
    return new Money(0, baseAmount.currency);
  }
}
```

### Pure Fabrication & Indirection (Use-Case Coordinator)

```typescript
// DTO untuk eksekusi Use-Case
export interface CheckoutRequest {
  orderId: string;
  paymentToken: string;
}

export interface CheckoutResponse {
  success: boolean;
  orderId: string;
  totalPaid: Money;
  transactionId?: string;
  errorMessage?: string;
}

// GRASP: Pure Fabrication & High Cohesion
// SOLID: Single Responsibility Principle (Aktor: Alur Bisnis Checkout)
// SOLID: Dependency Inversion Principle (Bergantung pada abstraksi)
export class CheckoutService {
  constructor(
    private readonly orderRepository: IOrderRepository,
    private readonly paymentGateway: IPaymentGateway,
    private readonly taxStrategy: ITaxStrategy,
    private readonly auditor: IAuditable
  ) {}

  public async execute(request: CheckoutRequest): Promise<CheckoutResponse> {
    // 1. Ambil Order (Low Coupling via Repository)
    const order = await this.orderRepository.findById(request.orderId);
    if (!order) {
      throw new Error(`Order dengan ID ${request.orderId} tidak ditemukan.`);
    }

    if (order.getPaymentStatus()) {
      throw new Error(`Order ${request.orderId} sudah pernah diproses.`);
    }

    // 2. Kalkulasi Nilai Akhir (Polymorphic Tax Strategy)
    const baseTotal = order.calculateTotal();
    const tax = this.taxStrategy.calculateTax(baseTotal);
    const finalAmount = baseTotal.add(tax);

    // 3. Eksekusi Pembayaran via Abstraksi (DIP)
    const paymentResult = await this.paymentGateway.charge(
      finalAmount,
      request.paymentToken
    );

    if (!paymentResult.success) {
      await this.auditor.logAudit("PAYMENT_FAILED", {
        orderId: order.orderId,
        reason: paymentResult.failureReason,
      });

      return {
        success: false,
        orderId: order.orderId,
        totalPaid: finalAmount,
        errorMessage: paymentResult.failureReason,
      };
    }

    // 4. Update Mutasi Domain
    order.markAsPaid();
    await this.orderRepository.save(order);

    // 5. Audit Trailing
    await this.auditor.logAudit("PAYMENT_SUCCESS", {
      orderId: order.orderId,
      txId: paymentResult.transactionId,
      amount: finalAmount.amount,
    });

    return {
      success: true,
      orderId: order.orderId,
      totalPaid: finalAmount,
      transactionId: paymentResult.transactionId,
    };
  }
}
```

### Implementasi Infrastruktur Kongkret (Low-Level Modules)

```typescript
// Implementasi Low-Level Concrete: Stripe Payment Gateway
export class StripePaymentGateway implements IPaymentGateway {
  public async charge(amount: Money, token: string): Promise<PaymentResult> {
    // Simulasi integrasi I/O HTTP API Stripe
    console.log(`[Stripe] Charging ${amount.currency} ${amount.amount} with token: ${token}`);
    
    // Asumsi eksekusi jaringan berhasil
    return {
      success: true,
      transactionId: `ch_stripe_${Date.now()}`,
    };
  }
}

// Implementasi In-Memory Repository untuk keperluan Demo/Testing
export class InMemoryOrderRepository implements IOrderRepository {
  private database = new Map<string, Order>();

  public async findById(orderId: string): Promise<Order | null> {
    return this.database.get(orderId) || null;
  }

  public async save(order: Order): Promise<void> {
    this.database.set(order.orderId, order);
  }
}

export class CloudWatchAuditor implements IAuditable {
  public async logAudit(event: string, meta: Record<string, unknown>): Promise<void> {
    console.log(`[Audit][${event}] Payload:`, JSON.stringify(meta));
  }
}
```

### Eksekusi & Pengujian Integrasi Komponen

```typescript
async function bootstrapDemo() {
  // 1. Setup Data & Infrastructure Dependencies
  const orderRepo = new InMemoryOrderRepository();
  const paymentGateway = new StripePaymentGateway();
  const taxStrategy = new IndonesianDomesticTaxStrategy();
  const auditor = new CloudWatchAuditor();

  // 2. Setup Pesanan Awal
  const order = new Order("ORD-9901", "CUST-007");
  order.addItem("PROD-MACBOOK", new Money(20000000, "IDR"), 1);
  order.addItem("PROD-MOUSE", new Money(1000000, "IDR"), 2);
  await orderRepo.save(order);

  // 3. Inject ke Application Service (CheckoutService)
  const checkoutService = new CheckoutService(
    orderRepo,
    paymentGateway,
    taxStrategy,
    auditor
  );

  // 4. Eksekusi Pembayaran
  console.log("--- Memulai Proses Checkout ---");
  const response = await checkoutService.execute({
    orderId: "ORD-9901",
    paymentToken: "tok_visa_valid_4242",
  });

  console.log("Checkout Response:", response);
}

bootstrapDemo().catch(console.error);
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi | Prinsip Tanpa Kontrol (Over-Engineering) | Kompromi Seimbang (Pragmatis) | Ketiadaan Pola (Under-Engineering) |
|---|---|---|---|
| **Jumlah File / Indirection** | Eksplosif. Setiap fungsi satu interface, 1-method class di mana-mana. Mengaburkan alur baca. | Abstraksi dibuat hanya pada batas subsistem penting atau titik variabilitas nyata. | Minimalis (1 file besar). Alur linier namun terjadi *tight coupling* ekstrem. |
| **Kecepatan Development (Time-to-Market)** | Lambat di awal karena butuh banyak *boilerplate*, *dependency injection*, dan perancangan antarmuka. | Cepat pada iterasi lanjutan; arsitektur siap diuji dan didelegasikan secara modular. | Sangat cepat di sprint 1-3, lalu melambat drastis akibat regresi dan *technical debt*. |
| **Kemudahan Testing (Testability)** | Sangat mudah diuji secara modular (*mocking* trivial), namun resiko tes memvalidasi implementasi semu. | Pengujian modular pada *business domain*, integrasi pada lapisan *infra/adapter*. | Sulit diuji. Butuh inisialisasi database aktif dan HTTP server langsung untuk unit test. |
| **Overhead Performa Runtime** | Terjadi overhead minor dari *virtual method dispatch*, alokasi memori berlebih, & *stack trace indirection*. | Overhead dapat diabaikan untuk 99% aplikasi web/enterprise modern. | Efisiensi CPU maksimal, namun pemeliharaan kode bernilai jutaan dolar menjadi beban. |

---

## SEKSI 11 — BEST PRACTICES

1. **Rule of Three untuk Abstraksi**: Jangan langsung membuat antarmuka generic untuk implementasi pertama. Tunggu variasi implementasi kedua atau ketiga sebelum mengekstrak antarmuka generik (*Premature abstraction is the root of architectural failure*).
2. **Favor Composition Over Inheritance**: Hindari memperluas fungsionalitas melalui hirarki *deep inheritance tree* (>2 level). Gunakan delegasi objek (*composition*) untuk mematuhi LSP dan ISP.
3. **Desain Interface dari Sudut Pandang Klien**: Tentukan antarmuka berdasarkan apa yang dibutuhkan oleh modul pemanggil, bukan berdasarkan apa yang dapat disediakan oleh modul pelaksana.
4. **Enkapsulasi State secara Ketat**: Dilarang membiarkan properti domain terbuka secara publik (`public get/set`). Mutasi internal hanya boleh dilakukan melalui metode domain yang memvalidasi *business invariant*.
5. **Fail-Fast via Invariants**: Verifikasi setiap argumen konstruktor atau metode di baris teratas (*guard clauses*). Pastikan objek tidak pernah berada dalam kondisi invalid (*invalid state*).

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Interface Pollution (Pseudo-ISP/DIP)
Menciptakan antarmuka 1:1 untuk setiap kelas tanpa dasar variabilitas yang jelas.
```typescript
// BAD: Polusi interface yang redundan
interface IUserService {
  getUser(id: string): User;
}
class UserService implements IUserService {
  getUser(id: string): User { ... }
}
// Tidak ada implementasi alternatif yang pernah dibuat sepanjang usia produk!
```
*Solusi*: Jika kelas tersebut adalah *domain logic* internal murni yang tidak memiliki variasi implementasi dan tidak bertindak sebagai *boundary*, ketergantungan langsung antar kelas internal tidak melanggar esensi DIP. Gunakan interface untuk *I/O boundaries* atau polimorfisme sejati.

### 2. Anemic Domain Model vs. God Object
* **Anemic Model**: Entitas hanya berupa penampung data (*getter/setter* belaka) sementara seluruh logika bisnis dimuntahkan ke kelas *Service* raksasa. Ini melanggar pola *Information Expert* dan *High Cohesion*.
* **God Object**: Menaruh seluruh tanggung jawab persistensi, validasi, dan notifikasi ke dalam satu entitas domain tunggal, melanggar *Single Responsibility Principle*.

### 3. Throwing NotSupportedException / UnsupportedOperationException (LSP Violation)
```typescript
// BAD: Subtipe menolak kontrak supertipe
interface Storage {
  read(path: string): Buffer;
  write(path: string, data: Buffer): void;
}

class ReadOnlyS3Storage implements Storage {
  read(path: string): Buffer { return /* logic */; }
  write(path: string, data: Buffer): void {
    // PELANGGARAN LSP: Merusak ekspektasi klien yang membutuhkan abstraksi Storage
    throw new UnsupportedOperationException("S3 ini Read-Only!");
  }
}
```
*Solusi*: Pisahkan antarmuka menggunakan **ISP**: `ReadableStorage` dan `WritableStorage`.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Identifikasi dan Dekomposisi Pelanggaran SRP & OCP (Tingkat: Dasar)
Diberikan fungsi monolitik `generateAndExportReport(type: string, data: any)`.
* **Tugas**: Pisahkan tanggung jawab ekstraksi data, formating (PDF, CSV, JSON), dan distribusi (Email, S3 Storage).
* **Instruksi**: Buat antarmuka `IReportFormatter` dan `IReportExporter`, lalu hubungkan keduanya menggunakan *Strategy Pattern* yang memenuhi OCP.

### Latihan 2: Memperbaiki Pelanggaran Liskov Substitution Principle (Tingkat: Menengah)
Diberikan arsitektur akun bank berikut:
```typescript
abstract class BankAccount {
  abstract deposit(amount: number): void;
  abstract withdraw(amount: number): void; // Menarik uang tunai
}
class FixedDepositAccount extends BankAccount {
  // Rekening deposito berjangka tidak mengizinkan penarikan sebelum jatuh tempo!
}
```
* **Tugas**: Refactor hirarki tipe di atas agar tidak ada subtipe yang melempar exception saat pemanggilan `withdraw()`, menggunakan pemisahan kontrak antarmuka yang bersih (*ISP & LSP*).

### Latihan 3: Merancang Sistem Notification Gateway Menggunakan GRASP (Tingkat: Mahir)
Sebuah sistem butuh mengirim notifikasi ke banyak *channel* (SMS via Twilio, Push Notification via Firebase, Email via Sendgrid) dengan aturan *fallback* (jika SMS gagal, coba Email).
* **Tugas**:
  * Tentukan kelas mana yang bertindak sebagai *Controller*, *Pure Fabrication*, dan *Protected Variations*.
  * Implementasikan *Circuit Breaker* atau *Fallback Policy* tanpa mengubah kelas pengirim utama (memenuhi OCP).
  * Lengkapi dengan unit test yang memvalidasi bahwa subtipe *provider* baru dapat disematkan tanpa memodifikasi kode koordinator.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Sebuah class `Customer` memiliki metode `saveToPostgres()` dan `generateTaxInvoicePDF()`. Mengapa ini melanggar Single Responsibility Principle (SRP) menurut definisi Robert C. Martin?**
   * A. Karena class tersebut memiliki lebih dari dua metode.
   * B. Karena class tersebut melayani dua aktor yang berbeda: DBA/DevOps dan Departemen Finansial/Akuntansi.
   * C. Karena fungsi PDF tidak boleh ditulis dalam bahasa yang sama dengan database driver.
   * D. Karena metode `saveToPostgres` harus menggunakan kata kerja pasif.
   * *Jawaban yang Benar*: **B**. SRP mendefinisikan tanggung jawab berdasarkan aktor/pemangku kepentingan perubahan (*reasons to change*).

2. **Manakah dari situasi berikut yang TIDAK melanggar Liskov Substitution Principle (LSP)?**
   * A. Subkelas memperketat validasi input (preconditions) dengan melempar exception untuk rentang angka yang diizinkan oleh kelas induk.
   * B. Subkelas mengembalikan subset data yang lebih sempit namun tetap memenuhi tipe kembalian (return type) kelas induk.
   * C. Subkelas menolak menjalankan satu metode dari interface dengan melempar `NotImplementedException`.
   * D. Subkelas mengubah nilai invariant yang dijamin selalu konstan oleh kelas induk.
   * *Jawaban yang Benar*: **B**. Mengembalikan nilai kembalian yang lebih spesifik (kovarian) diizinkan selama memenuhi kontrak tipe dasar.

3. **Pola GRASP manakah yang membenarkan pembuatan kelas seperti `UserRepository` atau `EmailDispatcher` padahal konsep tersebut tidak ada di dunia nyata fisik?**
   * A. Information Expert.
   * B. Creator.
   * C. Pure Fabrication.
   * D. Polymorphism.
   * *Jawaban yang Benar*: **C**. Pure Fabrication adalah pembuatan konsep buatan (artifisial) non-domain untuk mendukung *high cohesion* dan *low coupling*.

4. **Kapan penerapan Dependency Inversion Principle (DIP) berubah menjadi anti-pattern Over-Engineering?**
   * A. Ketika dependensi tingkat tinggi diarahkan langsung ke class model domain internal yang stabil dan tidak berubah.
   * B. Ketika membuat interface baru untuk setiap kelas utilitas string/array internal yang deterministik dan tidak memiliki efek samping I/O.
   * C. Ketika menggunakan Container Inversion of Control (IoC).
   * D. Ketika memisahkan database SQL dari entity bisnis.
   * *Jawaban yang Benar*: **B**. Membungkus kelas murni internal (*pure functions/stable utilities*) ke dalam interface tanpa kemungkinan variasi hanya menciptakan kompleksitas struktural tanpa nilai arsitektur.

5. **Apa korelasi struktural mendasar antara pola GRASP 'Protected Variations' dan SOLID 'Open-Closed Principle'?**
   * A. Keduanya adalah konsep yang saling bertolak belakang.
   * B. Protected Variations adalah mekanisme tingkat implementasi mikro, sedangkan OCP hanya berlaku pada tingkat deployment file JAR/DLL.
   * C. Protected Variations adalah motif konseptual/pola pikir untuk melindungi sistem dari instabilitas, sedangkan OCP adalah ekspresi struktural dari motif tersebut via polimorfisme/abstraksi.
   * D. Tidak ada korelasi; Protected Variations khusus untuk functional programming.
   * *Jawaban yang Benar*: **C**. Protected Variations menjelaskan *tujuan* proteksi desain, sementara OCP mendefinisikan aturan pemenuhan strukturalnya.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku Referensi Standar**:
  * Martin, Robert C. (2017). *Clean Architecture: A Craftsman's Guide to Software Structure and Design*. Prentice Hall.
  * Larman, Craig. (2004). *Applying UML and Patterns: An Introduction to Object-Oriented Analysis and Design and Iterative Development (3rd Edition)*. Prentice Hall.
  * Feathers, Michael. (2004). *Working Effectively with Legacy Code*. Prentice Hall.
  * Fowler, Martin. (2018). *Refactoring: Improving the Design of Existing Code (2nd Edition)*. Addison-Wesley.
* **Makalah Akademis**:
  * Liskov, Barbara; Wing, Jeannette. (1994). *A Behavioral Notion of Subtyping*. ACM Transactions on Programming Languages and Systems.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **Arsitektur Berkelanjutan Dimulai dari Kode**: Arsitektur tingkat tinggi (Microservices, Event-Driven) akan kolaps jika struktur kelas di tingkat kode dasar melanggar batas modularitas dasar.
2. **SOLID Menyediakan Batasan Struktural**:
   * **SRP**: Pisahkan modul berdasarkan aktor perubahan bisnis.
   * **OCP**: Buat komponen baru untuk fitur baru; jangan bongkar kode lama yang stabil.
   * **LSP**: Pertahankan kontrak subtipe tanpa melanggar ekspektasi pemanggil.
   * **ISP**: Pecah antarmuka monolitik menjadi kontrak kecil berorientasi fungsi klien.
   * **DIP**: Arahkan alur ketergantungan kode menuju abstraksi stabil, bukan implementasi detail.
3. **GRASP Memberikan Panduan Alokasi Tanggung Jawab**:
   * Tugaskan tugas komputasi ke pemegang data (**Information Expert**).
   * Jaga sistem tetap adaptif dengan membungkus titik risiko variasi (**Protected Variations**).
   * Manfaatkan kelas non-domain buatan (**Pure Fabrication**) untuk menjaga agar domain tetap bersih dari detail infrastruktur.

---

## SEKSI 17 — GLOSARIUM

* **Precondition**: Syarat atau kondisi yang wajib bernilai benar sebelum sebuah metode diizinkan untuk dieksekusi oleh pemanggil.
* **Postcondition**: Jaminan kondisi yang dipastikan bernilai benar oleh metode tepat setelah eksekusinya selesai.
* **Invariant**: Kondisi logis dari suatu objek yang harus selalu bernilai benar sepanjang masa hidup objek tersebut (kecuali saat terjadi mutasi internal sementara).
* **Coupling**: Derajat ketergantungan dan pengetahuan langsung antara satu komponen perangkat lunak terhadap komponen lainnya.
* **Cohesion**: Derajat keterikatan fungsional antara elemen-elemen di dalam suatu modul tunggal.
* **Role Interface**: Antarmuka berukuran ramping yang didesain secara spesifik untuk melayani perspektif kebutuhan satu klien pemanggil tertentu (antitesis dari *Header Interface* atau *Fat Interface*).
* **Pure Fabrication**: Objek artifisial yang sengaja diciptakan untuk menyelesaikan persoalan teknis struktural tanpa merepresentasikan padanan konsep dalam domain dunia nyata.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Hambatan Konseptual Utama Siswa**:
  * Peserta didik sering mengacaukan pemahaman SRP dengan *"melakukan satu hal saja"* (seperti satu fungsi matematika). Tekankan kembali bahwa tanggung jawab adalah fungsi dari **aktor perubahan manusia/organisasional**, bukan jumlah baris kode instruksi CPU.
  * Peserta sering kali memalsukan penerapan LSP: mereka mengira bahwa selama program berhasil dikompilasi (*type checks pass*), maka LSP terpenuhi. Jelaskan secara mendalam tentang **Behavioral Subtyping** (misal: melempar `RuntimeException` baru atau mengubah nilai mutasi global melanggar kontrak perilaku implisit meskipun lolos kompilasi).
* **Metodologi Pengajaran yang Disarankan**:
  * Gunakan metode *Code Smells First*: Tunjukkan kode yang buruk dan diskusikan rasa frustrasi saat menambahkan fitur baru, sebelum memperkenalkan istilah singkatan prinsip SOLID.
  * Jangan ajarkan prinsip desain sebagai dogma agama; selalu uji dengan trade-off kompleksitas sistem (*YAGNI - You Aren't Gonna Need It*).

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi**: 2.0.0
* **Tanggal Rilis**: 2025-01-15
* **Author**: Lead Curriculum Architect
* **Catatan Perubahan**:
  * Penulisan ulang penuh materi untuk menyelaraskan konsep teoritis SOLID dengan pola mental alokasi tanggung jawab GRASP.
  * Penambahan implementasi produksi Checkout E-Commerce lengkap berbasis TypeScript dengan penanganan invariant dan concurrency safety.
  * Penambahan batasan matematis eksplisit (Preconditions, Postconditions, Invariants) pada Liskov Substitution Principle.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `ARC-SDA-0102: Paradigma Pemrograman & Trade-off Ekosistem Modern`
* **Modul Saat Ini**: `ARC-SDA-0201: Prinsip Desain Tingkat Kode: Object-Oriented, SOLID, & GRASP`
* **Modul Berikutnya**: `ARC-SDA-0202: Pola Desain Gang of Four (GoF) Tingkat Lanjut: Implementasi Konkret & Modern Idiom`