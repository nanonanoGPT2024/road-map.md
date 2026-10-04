## SEKSI 01 — IDENTITAS MODUL

*   **Kode Modul:** SDA-06-03-01
*   **Nama Modul:** Pola Desain Klasik (GoF Patterns) & Idiom Arsitektur Modern: Creational, Structural, Behavioral Patterns dalam Konteks Bahasa Modern, Dependency Injection
*   **Kategori:** 06-Architecture-and-System-Design
*   **Track:** Software Design & Architecture
*   **Tingkat Kesulitan:** Advanced / Senior Engineer
*   **Prasyarat:** Pemahaman mendalam mengenai Object-Oriented Programming (OOP), Functional Programming (FP) basics, prinsip SOLID, pemodelan sistem modular, dan sistem pengetikan statis (static typing).
*   **Estimasi Waktu Penyelesaian:** 12 - 16 Jam Belajar Mandiri & Hands-on Lab

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Mendekonstruksi Pola Gang of Four (GoF):** Mengidentifikasi implementasi kanonikal dari *Creational*, *Structural*, dan *Behavioral patterns* serta mengevaluasi relevansinya di era komputasi modern.
2.  **Mentransformasi Pola Klasik ke Idiom Modern:** Mengganti boilerplate berbasis inheritance berlebih dengan kapabilitas bahasa modern (first-class functions, higher-order functions, algebraic data types, structural typing, dan pattern matching).
3.  **Mengarsitekturi Dependency Injection (DI) Engine:** Menganalisis cara kerja internal Dependency Injection Container, siklus hidup objek (*transient*, *scoped*, *singleton*), dan bahaya arsitektur seperti *Captive Dependency*.
4.  **Mengimplementasikan Pure DI vs Framework DI:** Mengambil keputusan arsitektural kapan harus mengadopsi IoC Container komersial/framework dan kapan harus menyusun *Composition Root* secara manual (*Pure DI*).
5.  **Menerapkan Strategi Decoupling Skala Enterprise:** Menggabungkan pola *Strategy*, *Decorator*, *Adapter*, dan *Builder* untuk membangun pipeline pemrosesan data terisolasi, *resilient*, dan mudah diuji secara modular tanpa *side-effects* yang tersembunyi.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                              [ARUS ARSITEKTUR PERANGKAT LUNAK]
                                             │
                      ┌──────────────────────┴──────────────────────┐
                      ▼                                             ▼
        [GoF Patterns Klasik (1994)]                  [Idiom Bahasa Modern & FP]
        - Creational (Factory, Builder)               - First-Class Functions (Lambdas)
        - Structural (Adapter, Decorator)             - Algebraic Data Types & Pattern Matching
        - Behavioral (Strategy, Observer)             - Immutability & Structural Subtyping
                      │                                             │
                      └──────────────────────┬──────────────────────┘
                                             ▼
                             [Sintesis: Modernized Patterns]
               ┌─────────────────────────────┼─────────────────────────────┐
               ▼                             ▼                             ▼
       [Modern Creational]          [Modern Structural]          [Modern Behavioral]
       Builder via Fluent/Types     Proxy via Reflection/Engine  Strategy via Function Injection
       Factory via Dynamic Reg.     Decorator via Middleware     Observer via Reactive Streams
                                             │
                                             ▼
                         [Pemisahan Dependensi & Komposisi]
               ┌─────────────────────────────┴─────────────────────────────┐
               ▼                                                           ▼
     [Dependency Inversion Principle (DIP)]                     [Inversion of Control (IoC)]
               │                                                           │
               └─────────────────────────────┬─────────────────────────────┘
                                             ▼
                              [Dependency Injection (DI)]
               ┌─────────────────────────────┼─────────────────────────────┐
               ▼                             ▼                             ▼
          [Pure DI]                   [IoC Containers]          [Lifecycle Management]
     - Explicit Wiring             - Reflection/Code-gen       - Transient
     - Zero Magic                  - Autowiring                - Scoped
     - Compile-time safety         - Service Locator Trap      - Singleton
                                                               - Captive Dependency Bug
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Pola Desain Gang of Four (GoF) yang diperkenalkan pada tahun 1994 dirancang dalam ekosistem C++ dan Smalltalk era awal, di mana paradigma *object-oriented* murni yang kaku mendominasi, dan fitur bahasa seperti *lambdas*, *generics*, dan *type inference* belum tersedia secara luas. 

Dalam pengembangan perangkat lunak modern:
1.  **Over-Engineering Akibat Kepatuhan Buta:** Menerapkan GoF secara harfiah di bahasa modern seperti TypeScript, Go, Rust, atau C# sering kali menghasilkan ratusan kelas abstrak yang sebenarnya dapat direduksi menjadi satu fungsi tingkat tinggi (*higher-order function*) atau *type union*.
2.  **Kebutuhan Decoupling Skala Tinggi:** Kebutuhan pengujian unit (*mocking/stubbing*), integrasi multi-cloud, dan sistem microservices menuntut batas isolasi (*boundary isolation*) yang sangat ketat. Di sinilah pemahaman mutakhir tentang *Structural Patterns* dan *Dependency Injection* menjadi fondasi mutlak.
3.  **Manajemen State dan Lifecycle Objek:** Pada aplikasi berskala besar, kebocoran memori (*memory leak*), *race condition*, dan instansiasi tak terkendali sering kali berakar dari salah paham atas siklus hidup DI (*Singleton* vs *Transient*).
4.  **Cognitive Load & Maintainability:** Arsitek harus mampu membedakan abstraksi yang bernilai versus kompleksitas yang sia-sia (*accidental complexity*). Memahami evolusi pola klasik ke idiom modern menghindarkan tim dari sindrom menulis kembali boilerplate enterprise Java era 2000-an di dalam ekosistem modern.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Klasifikasi Pola GoF
*   **Creational Patterns:** Menangani mekanisme pembuatan objek, mengisolasi logika pembuatan dari representasi objek itu sendiri (*Factory Method, Abstract Factory, Builder, Singleton, Prototype*).
*   **Structural Patterns:** Memfokuskan diri pada komposisi kelas atau objek untuk membentuk struktur yang lebih besar sambil mempertahankan fleksibilitas dan efisiensi (*Adapter, Decorator, Facade, Composite, Proxy*).
*   **Behavioral Patterns:** Berkaitan erat dengan algoritma dan penugasan tanggung jawab antar objek, mendefinisikan tidak hanya pola objek atau kelas, tetapi juga pola komunikasi di antara mereka (*Strategy, Observer, Command, State, Chain of Responsibility*).

### 2. Idiom Modern
Konsep arsitektural di mana fitur bahasa tingkat lanjut menggantikan struktur hierarki kelas yang berat:
*   *Strategy Pattern* $\rightarrow$ First-class functions atau closures.
*   *Command Pattern* $\rightarrow$ Anonymous functions / Callbacks / Data actions.
*   *Decorator Pattern* $\rightarrow$ Higher-Order Functions / Pipeline composition / Middleware chaining.
*   *State/Visitor Pattern* $\rightarrow$ Discriminated Unions + Pattern Matching.

### 3. Dependency Injection (DI) & Inversion of Control (IoC)
*   **Inversion of Control (IoC):** Prinsip arsitektural di mana alur kontrol (*flow of control*) program dibalik; alih-alih kode kita memanggil pustaka framework, framework yang memanggil kode kita.
*   **Dependency Inversion Principle (DIP):** Modul tingkat tinggi tidak boleh bergantung pada modul tingkat rendah. Keduanya harus bergantung pada abstraksi.
*   **Dependency Injection (DI):** Pola desain struktural untuk menerapkan DIP, di mana dependensi suatu objek *diinjeksikan* dari luar (melalui konstruktor, parameter method, atau properti), bukan dibuat secara internal via instansiasi langsung (`new MyService()`).
*   **IoC Container:** Utilitas runtime/compile-time yang mengotomatisasi resolusi dependensi, instansiasi, dan siklus hidup objek secara rekursif berdasarkan konfigurasi atau metadata.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### 1. Evolusi Pola Creational: Dari Verbose Builder ke Type-Safe Config
Pada GoF klasik, *Builder* membutuhkan `Director`, `AbstractBuilder`, `ConcreteBuilder`, dan `Product`. Dalam arsitektur modern, teknik *Type-Safe Fluent Builder* memanfaatkan sistem tipe statis untuk memvalidasi kelengkapan properti saat waktu kompilasi (*compile-time verification*), mencegah runtime error akibat atribut wajib yang belum diinisialisasi.

### 2. Evolusi Pola Behavioral: Strategy Pattern via Functional Composition
*Classic Strategy*: Memerlukan `Context`, antarmuka `IStrategy`, dan berbagai kelas `ConcreteStrategyA`, `ConcreteStrategyB`. 
*Modern Idiom*: Menggunakan *Function Types*. Variasi algoritma hanyalah sebuah fungsi yang cocok dengan kontrak tanda tangan (*signature*):
$$\text{Algorithm} = f(A) \to B$$
Kelas `Context` hanya menerima fungsi ini sebagai parameter konstruktor tanpa perlu memelihara hierarki kelas terpisah.

### 3. Resolusi Dependency Injection Engine
Dependency Injection Container bekerja berdasarkan traversal grafik asiklik terarah (*Directed Acyclic Graph* / DAG) dari dependensi:

```
[Request: Controller]
         │
         ▼
[Resolve Controller] ──requires──► [Resolve Service]
                                          │
                                          ▼
                                   [Resolve Repository] ──requires──► [Resolve DatabaseContext]
```

Langkah-langkah resolusi internal:
1.  **Registrasi:** Container mencatat pemetaan: $\text{Interface} \mapsto \text{Concrete Class/Factory}$ beserta spesifikasi *Lifecycle*.
2.  **Inspeksi (Reflection / AST Parsing):** Saat suatu tipe diminta, container membaca tanda tangan konstruktor untuk mendeteksi dependensi yang dibutuhkan.
3.  **Grafik Ketergantungan:** Container memvalidasi bahwa tidak ada *Circular Dependency* (A membutuhkan B, B membutuhkan A). Jika ada, container melempar *Cyclic Dependency Exception*.
4.  **Alokasi Siklus Hidup (Lifecycle Resolution):**
    *   **Transient:** Selalu instansiasi objek baru tiap kali dependensi diminta.
    *   **Singleton:** Instansiasi satu kali pada tingkat container root, simpan referensi di memori, kembalikan referensi yang sama untuk semua permintaan berikutnya.
    *   **Scoped:** Buat satu instans per siklus request konteks (misal: satu HTTP Request). Objek dibersihkan (*disposed*) saat konteks berakhir.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Perbandingan Alur: Classic Strategy vs Modern Functional Strategy

```
CLASSIC GOF STRATEGY PATTERN:
+-------------------+             +---------------------+
|      Context      |◇───────────>|     <<interface>>   |
|                   |             |      IPayment       |
+-------------------+             +---------------------+
| +executePayment() |             | +pay(amount: float) |
+-------------------+             +---------------------+
                                             ▲
                                             │
                     ┌───────────────────────┴───────────────────────┐
                     │                                               │
          +---------------------+                         +---------------------+
          |   CreditCardPayment |                         |    CryptoPayment    |
          +---------------------+                         +---------------------+
          | +pay(amount: float) |                         | +pay(amount: float) |
          +---------------------+                         +---------------------+

MODERN FUNCTIONAL DISPATCH (First-Class Functions):
+------------------------------------+
|            OrderService            |
+------------------------------------+
| - paymentHandler: PaymentProcessor |
+------------------------------------+
                  │
                  │ invokasi langsung fungsi: (amount: number) => Promise<PaymentResult>
                  ▼
┌────────────────────────────────────────────────────────────────┐
| Pure Function Pipeline:                                        |
| const creditCardPay: PaymentProcessor = (amt) => { ... }       |
| const cryptoPay: PaymentProcessor = (amt) => { ... }           |
└────────────────────────────────────────────────────────────────┘
```

### 2. Arsitektur Resolusi DI Container & Captive Dependency Hazard

```
ROOT CONTAINER (Singleton Scope)
+---------------------------------------------------------------+
| Singletons: [DatabaseConnection, MetricCollector]             |
|                                                               |
|   HTTP REQUEST 1 (Scope A)       HTTP REQUEST 2 (Scope B)     |
|   +--------------------------+   +--------------------------+ |
|   | Scoped: [UnitOfWork]     |   | Scoped: [UnitOfWork]     | |
|   |                          |   |                          | |
|   | Transient: [OrderCmd]    |   | Transient: [OrderCmd]    | |
|   +--------------------------+   +--------------------------+ |
+---------------------------------------------------------------+

BAHAYA: CAPTIVE DEPENDENCY (Siklus Hidup Terjebak)
+---------------------------------------------------------------+
| [SingletonService] (Hidup selamanya)                          |
|         │                                                     |
|         ▼ (Diinjeksikan dependensi scoped ke dalam konstruktor)
| [ScopedContext] (HARUSNYA mati setelah 1 HTTP request)        |
+---------------------------------------------------------------+
HASIL: ScopedContext bocor ke luar request boundaries, 
mengakibatkan stale data, thread-safety violations, atau memory leak!
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah komparasi refactoring dari Pola Behavioral/Structural Klasik ke Pola Modern menggunakan TypeScript.

### Kasus: Validasi & Pemrosesan Diskon (Strategy + Decorator)

#### Pendekatan Klasik (GoF Verbose)
```typescript
// Classic Strategy
interface DiscountStrategy {
  calculate(price: number): number;
}

class RegularDiscount implements DiscountStrategy {
  calculate(price: number): number {
    return price * 0.95;
  }
}

class VIPDiscount implements DiscountStrategy {
  calculate(price: number): number {
    return price * 0.80;
  }
}

class PriceCalculator {
  constructor(private strategy: DiscountStrategy) {}

  setStrategy(strategy: DiscountStrategy) {
    this.strategy = strategy;
  }

  compute(amount: number): number {
    return this.strategy.calculate(amount);
  }
}
```

#### Pendekatan Modern Idiom (Functional Composition)
```typescript
// Modern: Type Alias untuk function signature
type DiscountFn = (price: number) => number;

// Concrete strategies as pure functions
const regularDiscount: DiscountFn = (price) => price * 0.95;
const vipDiscount: DiscountFn = (price) => price * 0.80;

// Decorator sebagai Higher-Order Function (HOC)
const withTax = (taxRate: number) => (next: DiscountFn): DiscountFn => {
  return (price: number) => {
    const discounted = next(price);
    return discounted + (discounted * taxRate);
  };
};

// Komposisi Dinamis (Structural Decorator + Strategy tanpa class)
const standardVipPipeline = withTax(0.11)(vipDiscount);

console.log(standardVipPipeline(100)); 
// Evaluasi: (100 * 0.80) = 80 -> Tax 11% = 80 + 8.8 = 88.8
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus arsitektur enterprise: Subsistem Transaksi Pembayaran dengan integrasi **Modern Builder**, **Strategy Pipeline**, **Middleware Decorator**, dan **IoC Container Resolusi Otomatis**.

```typescript
// ============================================================================
// 1. DOMAIN & ABSTRACTION BOUNDARIES (DIP)
// ============================================================================

export interface Transaction {
  readonly id: string;
  readonly amount: number;
  readonly currency: string;
  readonly recipient: string;
}

export interface PaymentResult {
  readonly success: boolean;
  readonly transactionId: string;
  readonly message: string;
  readonly timestamp: number;
}

export interface IPaymentGateway {
  process(transaction: Transaction): Promise<PaymentResult>;
}

// ============================================================================
// 2. CREATIONAL: TYPE-SAFE IMMUTABLE BUILDER
// ============================================================================

export class TransactionBuilder {
  private id?: string;
  private amount?: number;
  private currency?: string;
  private recipient?: string;

  private constructor() {}

  public static create(): TransactionBuilder {
    return new TransactionBuilder();
  }

  public withId(id: string): this {
    this.id = id;
    return this;
  }

  public withAmount(amount: number): this {
    if (amount <= 0) throw new Error("Nominal transaksi harus lebih dari nol");
    this.amount = amount;
    return this;
  }

  public withCurrency(currency: string): this {
    this.currency = currency;
    return this;
  }

  public toRecipient(recipient: string): this {
    this.recipient = recipient;
    return this;
  }

  public build(): Transaction {
    if (!this.id || !this.amount || !this.currency || !this.recipient) {
      throw new Error("Gagal membangun transaksi: field mandatori belum lengkap.");
    }

    return Object.freeze({
      id: this.id,
      amount: this.amount,
      currency: this.currency,
      recipient: this.recipient,
    });
  }
}

// ============================================================================
// 3. ADAPTERS & STRATEGIES (Gateways)
// ============================================================================

export class StripeGatewayAdapter implements IPaymentGateway {
  async process(transaction: Transaction): Promise<PaymentResult> {
    // Simulasi interaksi eksternal Stripe API
    return {
      success: true,
      transactionId: `STRIPE_${transaction.id}`,
      message: `Berhasil diproses via Stripe untuk ${transaction.recipient}`,
      timestamp: Date.now(),
    };
  }
}

export class BankTransferGatewayAdapter implements IPaymentGateway {
  async process(transaction: Transaction): Promise<PaymentResult> {
    // Simulasi interaksi eksternal Core Banking API
    return {
      success: true,
      transactionId: `VA_${transaction.id}`,
      message: `Virtual Account dibuat untuk ${transaction.recipient}`,
      timestamp: Date.now(),
    };
  }
}

// ============================================================================
// 4. STRUCTURAL: DECORATOR PATTERN UNTUK CROSS-CUTTING CONCERNS
// ============================================================================

export class TelemetryPaymentDecorator implements IPaymentGateway {
  constructor(private readonly innerGateway: IPaymentGateway) {}

  async process(transaction: Transaction): Promise<PaymentResult> {
    const startTime = performance.now();
    console.log(`[TELEMETRY] [START] Memulai transaksi ID: ${transaction.id}`);

    try {
      const result = await this.innerGateway.process(transaction);
      const duration = (performance.now() - startTime).toFixed(2);
      console.log(`[TELEMETRY] [END] Selesai: ${result.transactionId} dlm ${duration}ms`);
      return result;
    } catch (error) {
      console.error(`[TELEMETRY] [FAIL] Terjadi kegagalan pada: ${transaction.id}`, error);
      throw error;
    }
  }
}

// ============================================================================
// 5. APPLICATION SERVICE DENGAN DEPENDENCY INJECTION
// ============================================================================

export class CheckoutService {
  // Injeksi abstraksi, bukan implementasi konkret (DIP)
  constructor(private readonly paymentGateway: IPaymentGateway) {}

  public async executeCheckout(orderId: string, amount: number, account: string): Promise<PaymentResult> {
    const transaction = TransactionBuilder.create()
      .withId(orderId)
      .withAmount(amount)
      .withCurrency("IDR")
      .toRecipient(account)
      .build();

    return await this.paymentGateway.process(transaction);
  }
}

// ============================================================================
// 6. DEPENDENCY INJECTION CONTAINER ENGINE DENGAN LIFECYCLE MANAGEMENT
// ============================================================================

type Lifetime = "TRANSIENT" | "SINGLETON";

interface ServiceDescriptor<T = unknown> {
  factory: (container: Container) => T;
  lifetime: Lifetime;
  instance?: T;
}

export class Container {
  private readonly registry = new Map<string, ServiceDescriptor>();

  public register<T>(key: string, factory: (container: Container) => T, lifetime: Lifetime = "TRANSIENT"): void {
    this.registry.set(key, { factory, lifetime });
  }

  public resolve<T>(key: string): T {
    const descriptor = this.registry.get(key);
    if (!descriptor) {
      throw new Error(`Dependensi tidak terdaftar: ${key}`);
    }

    if (descriptor.lifetime === "SINGLETON") {
      if (!descriptor.instance) {
        descriptor.instance = descriptor.factory(this);
      }
      return descriptor.instance as T;
    }

    // TRANSIENT: generate instance baru
    return descriptor.factory(this) as T;
  }
}

// ============================================================================
// 7. COMPOSITION ROOT (Titik Bootstrapping Aplikasi)
// ============================================================================

function bootstrap(): void {
  const container = new Container();

  // Registrasi dependensi infra
  container.register<IPaymentGateway>("RawPaymentGateway", () => {
    // Logika pemilihan strategy saat runtime
    const useStripe = true; 
    return useStripe ? new StripeGatewayAdapter() : new BankTransferGatewayAdapter();
  }, "SINGLETON");

  // Structural composition: Membungkus Gateway dengan Decorator Telemetry
  container.register<IPaymentGateway>("PaymentGateway", (c) => {
    const rawGateway = c.resolve<IPaymentGateway>("RawPaymentGateway");
    return new TelemetryPaymentDecorator(rawGateway);
  }, "SINGLETON");

  // Registrasi domain service (Transient)
  container.register<CheckoutService>("CheckoutService", (c) => {
    return new CheckoutService(c.resolve<IPaymentGateway>("PaymentGateway"));
  }, "TRANSIENT");

  // --- RESOLUSI & TESTING RUNTIME ---
  const checkout = container.resolve<CheckoutService>("CheckoutService");

  checkout.executeCheckout("TX-99081", 450000, "acct_corp_8819")
    .then((res) => console.log("[HASIL AKHIR]:", JSON.stringify(res, null, 2)))
    .catch((err) => console.error("[CRITICAL ERROR]:", err));
}

bootstrap();
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Arsitektural | Pendekatan GoF Murni (OOP) | Pendekatan Modern Idiom / FP | Analisis Kritis & Trade-off |
| :--- | :--- | :--- | :--- |
| **Kompleksitas Kode** | Sangat Tinggi (Banyak kelas, antarmuka, dan file terpisah). | Rendah hingga Sedang (Fungsi, lambda, structural types). | Pola modern mengurangi file sprawl, tetapi jika tidak dijaga bisa memicu inline implementation yang sulit diuji secara terisolasi. |
| **Performance Overhead** | Sedang (Virtual method dispatch, memory indirection). | Sangat Rendah (Monomorphic function calls, JIT optimizations). | Inlining pada mesin JS/V8 atau Rust jauh lebih optimal dengan *first-class functions* dibandingkan pointer traversal objek polimorfik bertingkat. |
| **Type Safety** | Tergantung interface inheritance manual. | Sangat Tinggi via Static Inference & Union Types. | Menggunakan *discriminated unions* menghilangkan kebutuhan pola *Visitor* sekaligus memvalidasi exhaustive handling saat kompilasi. |
| **Dependency Injection** | Runtime DI via Reflection/Annotations (e.g., Spring/NestJS). | Pure DI / Compile-time DI (e.g., Wire di Go, manual wiring). | Runtime DI mempermudah autowiring namun mengorbankan performa startup dan mendeteksi kesalahan konfigurasi dependensi hanya saat runtime. |

---

## SEKSI 11 — BEST PRACTICES

1.  **Gunakan Constructor Injection Secara Mutlak:** Jangan pernah menggunakan *Field Injection* atau *Setter Injection* untuk dependensi mandatori. Objek harus selalu berada dalam kondisi valid (*valid state*) segera setelah dikonstruksi.
2.  **Terapkan Explicit Composition Root:** Pusatkan inisialisasi seluruh dependensi aplikasi hanya di satu tempat (pintu masuk aplikasi, misal `main.ts` atau `Program.cs`). Dilarang keras melakukan resolusi container langsung di dalam domain logic.
3.  **Hormati Batas Lifecycle (Cegah Captive Dependency):** 
    *   *Singleton* TIDAK BOLEH memegang referensi ke objek *Scoped* atau *Transient*.
    *   *Scoped* boleh memegang *Scoped* lain atau *Singleton*.
    *   *Transient* bebas bergantung pada apa pun karena durasi hidupnya singkat.
4.  **Favor Composition Over Inheritance:** Jika suatu perilaku dapat diganti dengan melewatkan fungsi/antarmuka (Strategy/HOC), prioritaskan cara ini daripada membuat subclass baru.
5.  **Interface Segregation pada Kontrak Dependensi:** Klien tidak boleh dipaksa bergantung pada method yang tidak mereka gunakan. Desain antarmuka DI sekecil dan sefokus mungkin (*Single-method interfaces* bila memungkinkan).

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. The Service Locator Anti-Pattern
Melewatkan instance container langsung ke dalam *service* domain untuk mengambil dependensi secara *ad-hoc*.
```typescript
// BURUK: Service Locator Anti-Pattern!
class BadOrderService {
  constructor(private container: Container) {} // Ketergantungan tersembunyi!

  process() {
    const payment = this.container.resolve<IPaymentGateway>("PaymentGateway");
    // Sulit diuji, menyembunyikan dependensi sebenarnya dari API publik.
  }
}

// BENAR: Explicit Dependency Injection
class GoodOrderService {
  constructor(private payment: IPaymentGateway) {} // Transparan dan decoupled.
}
```

### 2. The God-Builder & Missing Immutability
Membuat *Builder* yang mempertahankan *mutable state* setelah pemanggilan `.build()`, atau membiarkan objek domain diekspos dengan mutator publik (*setter*) sehingga prinsip *invariants* rusak. Objek hasil instansiasi wajib bersifat *immutable* (`Object.freeze()` atau tipe `readonly`).

### 3. Factory Tanpa Kebutuhan Jelas (Factory-itis)
Membuat `UserFactoryFactory` untuk objek primitif yang hanya memiliki data struktural tanpa variasi logika pembuatan. Gunakan konstruktor standar atau *object literal* jika tidak ada invariant kompleks atau variasi polimorfisme.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Soal Latihan: Message Notification Router dengan Decorator & Strategy

#### Konteks
Anda ditugaskan mendesain sistem notifikasi perusahaan yang mampu mengirim pesan ke berbagai vendor (**Slack**, **Email**, **SMS**) berdasarkan preferensi pengguna, dilengkapi proteksi **Rate-Limiting** dan **Audit Logging**.

#### Persyaratan Arsitektural:
1.  Buat abstraksi `INotificationChannel` dengan method `send(userId: string, message: string): Promise<boolean>`.
2.  Terapkan 2 concrete strategy: `EmailChannel` dan `SlackChannel`.
3.  Implementasikan `RateLimiterDecorator` yang membatasi pengiriman maksimal 2 pesan per detik per instance channel; jika melebihi, throw Error.
4.  Susun sebuah custom `NotificationService` yang menerima map channel strategi via Constructor Injection.
5.  Rakit seluruh subsistem di dalam fungsi `main()` menggunakan konsep **Pure DI** (Manual Assembly tanpa framework IoC eksternal).

#### Solusi Implementasi
```typescript
// 1. Abstraksi
interface INotificationChannel {
  send(userId: string, message: string): Promise<boolean>;
}

// 2. Concrete Strategies
class EmailChannel implements INotificationChannel {
  async send(userId: string, message: string): Promise<boolean> {
    console.log(`[EMAIL] Mengirim ke user ${userId}: ${message}`);
    return true;
  }
}

class SlackChannel implements INotificationChannel {
  async send(userId: string, message: string): Promise<boolean> {
    console.log(`[SLACK] Mengirim ke user ${userId}: ${message}`);
    return true;
  }
}

// 3. Decorator
class RateLimiterDecorator implements INotificationChannel {
  private lastRun = 0;
  private readonly minIntervalMs = 500; // maks 2 call per detik

  constructor(private readonly inner: INotificationChannel) {}

  async send(userId: string, message: string): Promise<boolean> {
    const now = Date.now();
    if (now - this.lastRun < this.minIntervalMs) {
      throw new Error(`[RATE LIMIT EXCEEDED] Terlalu banyak permintaan pada channel ini.`);
    }
    this.lastRun = now;
    return await this.inner.send(userId, message);
  }
}

// 4. Domain Service
class NotificationService {
  constructor(private readonly channels: Map<string, INotificationChannel>) {}

  async dispatch(channelType: string, userId: string, message: string): Promise<void> {
    const channel = this.channels.get(channelType);
    if (!channel) {
      throw new Error(`Channel tipe ${channelType} tidak didukung.`);
    }
    await channel.send(userId, message);
  }
}

// 5. Composition Root (Pure DI)
async function runPureDI() {
  // Manual wiring
  const emailStrategy = new RateLimiterDecorator(new EmailChannel());
  const slackStrategy = new RateLimiterDecorator(new SlackChannel());

  const channelMap = new Map<string, INotificationChannel>();
  channelMap.set("email", emailStrategy);
  channelMap.set("slack", slackStrategy);

  const notifier = new NotificationService(channelMap);

  // Verifikasi
  await notifier.dispatch("email", "USR-001", "Verifikasi Akun Anda");
  await notifier.dispatch("slack", "USR-002", "Peringatan Incident P1");
}

runPureDI().catch(console.error);
```

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan analisis arsitektural berikut untuk menguji pemahaman Anda:

1.  **Analisis Siklus Hidup:** Sebuah service `NotificationEngine` didaftarkan sebagai `Singleton` di DI Container. Service tersebut membutuhkan `UserSessionContext` yang didaftarkan sebagai `Scoped` (berubah setiap HTTP Request). Jelaskan apa implikasi kegagalan runtime yang akan terjadi dan bagaimana solusi arsitektur yang benar untuk mengatasinya!
2.  **GoF vs Modern:** Mengapa pengadopsian pola *Visitor* klasik sering kali dianggap sebagai *anti-pattern* pada bahasa modern yang mendukung *Pattern Matching* dan *Algebraic Data Types* (ADT)?
3.  **Decoupling vs Boilerplate:** Kapan penggunaan *Pure DI* (manual assembly) lebih dipilih dibandingkan menggunakan pustaka eksternal seperti InversifyJS, NestJS DI, atau Spring Framework?
4.  **Structural Integrity:** Apa perbedaan mendasar secara intensi arsitektural antara *Adapter Pattern* dan *Facade Pattern*?
5.  **IoC Boundary:** Anda mendapati kode berikut di layer Domain:
    `const db = Container.getInstance().resolve("Database");`
    Prinsip arsitektur apa saja yang dilanggar dan mengapa hal ini berdampak fatal pada maintainability sistem jangka panjang?

---

### Kunci Jawaban & Penilaian

1.  **Analisis Captive Dependency:**
    *   *Implikasi:* Objek `UserSessionContext` (Scoped) akan terperangkap (*captive*) di dalam memori `NotificationEngine` (Singleton) seumur hidup aplikasi. Akibatnya, data sesi request pertama akan tersimpan permanen dan dipakai oleh seluruh request berikutnya dari pengguna lain (*Stale Data / Data Leak across tenants*), atau menyebabkan memory leak.
    *   *Solusi:* Ubah `NotificationEngine` menjadi `Scoped`, atau gunakan *Factory pattern* di mana `NotificationEngine` mengabstraksi pembuatan/pembacaan context saat pemanggilan method saja via provider scoped (`IUserSessionContextProvider.getCurrent()`).
2.  **Visitor Pattern vs ADT:**
    Pola *Visitor* klasik memecah fungsi operasi dengan menambahkan method `accept(Visitor)` ke seluruh kelas domain dan memelihara hierarki interface visitor ganda (*Double Dispatch*). Pola ini sangat kaku terhadap perubahan (menambah varian node merusak semua visitor). Dengan *Algebraic Data Types* (Sum Types) dan *Pattern Matching*, domain data bebas dari dependensi perilaku luar, dan operasi baru dapat ditulis sebagai fungsi murni dengan *compile-time exhaustive check*.
3.  **Pure DI vs Framework DI:**
    *Pure DI* lebih superior pada aplikasi berskala kecil hingga menengah, CLI, microservices dengan dependensi terbatas, atau library/SDK. Keuntungannya: Tidak ada runtime overhead reflection, 100% aman saat kompilasi (*compile-time safety*), zero framework lock-in, dan penelusuran error via native stack-trace tanpa terhalang layer internal framework.
4.  **Adapter vs Facade:**
    *   *Adapter:* Mengubah satu antarmuka yang ada agar cocok dengan antarmuka target yang diharapkan klien tanpa mengubah perilaku internal (fokus pada kompatibilitas 1-ke-1).
    *   *Facade:* Menyederhanakan antarmuka yang kompleks atau menyatukan banyak subsistem yang rumit menjadi satu antarmuka tingkat tinggi yang mudah digunakan (fokus pada kemudahan integrasi 1-ke-banyak).
5.  **Pelanggaran Service Locator:**
    *   Melanggar **Dependency Inversion Principle (DIP)** karena domain secara eksplisit tahu keberadaan Container global.
    *   Melanggar prinsip **Information Hiding**: Public API dari class tidak lagi mencerminkan dependensi sesungguhnya.
    *   Menghilangkan kemampuan pengujian unit (*Unit Testing*): Kita tidak bisa sekadar menyuntikkan *mock database* via konstruktor tanpa menginisialisasi state container statis.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

*   **Buku Wajib:**
    *   Gamma, E., Helm, R., Johnson, R., & Vlissides, J. (1994). *Design Patterns: Elements of Reusable Object-Oriented Software*. Addison-Wesley.
    *   Seemann, M., & Deursen, S. van. (2019). *Dependency Injection Principles, Practices, and Patterns*. Manning Publications.
    *   Martin, R. C. (2017). *Clean Architecture: A Craftsman's Guide to Software Structure and Design*. Prentice Hall.
*   **Makalah & Artikel Ilmiah:**
    *   Fowler, M. (2004). *Inversion of Control Containers and the Dependency Injection pattern*. martinfowler.com.
*   **Repositori Arsitektur Acuan:**
    *   *Microsoft Architecture Guides*: Cloud Design Patterns & Dependency Injection in .NET Core.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1.  Pola Desain GoF adalah solusi teruji atas masalah berulang, namun harus dilihat dari lensa komputasi modern; fitur bahasa modern sering kali mengeliminasi kebutuhan pembuatan hierarki kelas yang kaku.
2.  *Strategy* dan *Command* bertransformasi menjadi *First-Class Functions*; *Decorator* bertransformasi menjadi *Higher-Order Functions / Pipeline Middlewares*; *Visitor* digantikan oleh *Discriminated Unions* dan *Pattern Matching*.
3.  *Dependency Inversion Principle* (DIP) adalah tujuan arsitektural (aturan decoupling tingkat tinggi), sedangkan *Dependency Injection* (DI) adalah mekanisme taktis pemenuhan prinsip tersebut.
4.  Manajemen siklus hidup objek (*Transient*, *Scoped*, *Singleton*) pada IoC Container sangat krusial. Kelalaian memahami alokasi siklus hidup memicu bug *Captive Dependency* yang sangat berbahaya pada lingkungan multithreaded/concurrent.
5.  *Composition Root* adalah satu-satunya lokasi sah dalam sistem untuk melakukan *wiring* dependensi. Menghindari *Service Locator* adalah kewajiban mutlak untuk menjaga kode tetap *testable*, terisolasi, dan mudah dipelihara.

---

## SEKSI 17 — GLOSARIUM

*   **Composition Root:** Lokasi terpusat dan unik di dalam aplikasi tempat grafik dependensi disusun (*bootstrapped*), biasanya terletak sedekat mungkin dengan titik masuk eksekusi (*entry point*).
*   **Captive Dependency:** Kondisi kesalahan arsitektur di mana komponen dengan siklus hidup pendek (*scoped/transient*) disuntikkan ke dalam komponen dengan siklus hidup lebih panjang (*singleton*), menahan objek pendek tersebut hidup melampaui batas waktu yang seharusnya.
*   **Pure DI:** Praktik menerapkan Dependency Injection secara manual tanpa menggunakan framework IoC Container pihak ketiga.
*   **Higher-Order Function (HOC):** Fungsi yang menerima satu atau lebih fungsi sebagai argumen, atau mengembalikan fungsi sebagai hasilnya.
*   **Structural Typing:** Sistem pengetikan di mana kompatibilitas dan kesetaraan tipe ditentukan oleh bentuk atau struktur tipe tersebut (*shape of type*), bukan deklarasi identitas eksplisit (nominal typing).
*   **Inversion of Control (IoC):** Pola rancang di mana kendali eksekusi program diserahkan kepada framework atau runtime environment, membalik pola kontrol program prosedural konvensional.

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Penekanan Pedagogis:**
    *   Saat mengajarkan materi ini, jangan biarkan peserta didik menghafal diagram UML GoF secara dogmatis. Selalu tanyakan: *"Bagaimana bahasa modern menyederhanakan diagram ini tanpa kehilangan sifat decoupling-nya?"*
    *   Wajibkan peserta mengidentifikasi bahaya *Captive Dependency* melalui skenario simulasi multithreaded atau simulasi web request context.
*   **Jebakan Konseptual Peserta:**
    *   Banyak peserta mengira bahwa *Dependency Injection* identik dengan framework (seperti NestJS, Spring, ASP.NET Core). Tegaskan berulang-ulang bahwa DI adalah sebuah pola desain arsitektural; framework hanyalah alat bantu otomasi (*automation tool*). Menulis *Pure DI* adalah cara terbaik melatih intuisi arsitektural mereka.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi 1.0.0 (Maret 2026):**
    *   Rilis awal kurikulum arsitektur perangkat lunak modern.
    *   Transformasi komparasi kanonikal GoF ke TypeScript modern / Functional Idioms.
    *   Penyusunan panduan lifecycle DI Container dan analisis bahaya Captive Dependency.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya:** `SDA-06-02-02: SOLID Principles Deep Dive & Modularity Metrics`
*   **Modul Berikutnya:** `SDA-06-03-02: Architectural Styles: Layered, Hexagonal (Ports & Adapters), and Clean Architecture`
*   **Arah Pembelajaran Jangka Panjang:** Menguasai decoupling di tingkat objek dan fungsi (Modul ini) adalah fondasi wajib sebelum memasuki perancangan arsitektur tingkat sistem makro seperti Domain-Driven Design (DDD), Hexagonal Architecture, dan Event-Driven Microservices.