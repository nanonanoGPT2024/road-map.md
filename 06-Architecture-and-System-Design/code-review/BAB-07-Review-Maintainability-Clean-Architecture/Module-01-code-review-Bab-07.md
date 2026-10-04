# Bab 07 Module 01 — Review Khusus: Maintainability, Clean Architecture, & Testing: Batas Modul, Dependensi Struktural, Coupling & Cohesion, Strategi Testing Bermakna, Mocking Boundaries

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** `CR-ARC-07-01`
* **Kategori:** 06-Architecture-and-System-Design
* **Tingkat Kemahiran:** Advanced / Senior Software Engineer & Tech Lead
* **Prasyarat:** Pemahaman mendalam mengenai Object-Oriented Programming (OOP) / Functional Programming (FP), Dependency Injection, Git Flow, Unit Testing dasar, dan prinsip SOLID.
* **Alokasi Waktu Pembelajaran:** 8 Jam (Teori, Review Studi Kasus, & Simulasi PR)
* **Target Eksekusi:** Code Reviewer, Technical Lead, Staff/Principal Engineer, Software Architect

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Mendiagnosis Pelanggaran Arsitektural dalam Pull Request (Analyze):** Mengidentifikasi *leaky abstractions*, siklus dependensi (*cyclic dependencies*), dan pelanggaran *Dependency Rule* pada struktur Clean Architecture / Hexagonal Architecture secara presisi.
2. **Mengukur Metrik Coupling & Cohesion Secara Kualitatif dan Kuantitatif (Evaluate):** Menilai tingkat ketergantungan antar-modul (*Afferent* vs *Efferent Coupling*, *Instability Index*) serta kohesi fungsional modul sebelum menyetujui perubahan kode.
3. **Mengevaluasi Kualitas Batas Testing (*Testing & Mocking Boundaries*) (Evaluate):** Membedakan antara pengujian perilaku (*behavior-driven testing*) vs pengujian detail implementasi (*implementation detail testing*), serta menentukan validitas titik *mocking* pada batas I/O sistem.
4. **Merumuskan Rekomendasi Refaktorisasi Terstruktur (Synthesize):** Menuliskan komentar *code review* yang berbobot arsitektural, berbasis *trade-offs*, dan mengarahkan author menuju pemisahan *Domain Core* dari *Infrastructure Layer*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                    ┌────────────────────────────────────────────────────────┐
                    │            STRATEGI REVIEW ARSITEKTUR & UJI            │
                    └───────────────────────────┬────────────────────────────┘
                                                │
         ┌──────────────────────────────────────┴──────────────────────────────────────┐
         ▼                                                                             ▼
┌─────────────────────────────────┐                                   ┌─────────────────────────────────┐
│     STRUKTUR & BATAS MODUL      │                                   │     STRATEGI TESTING BERMAKNA   │
├─────────────────────────────────┤                                   ├─────────────────────────────────┤
│ • Dependency Inversion Principle│                                   │ • Sociable vs Solitary Tests    │
│ • The Dependency Rule (Inward)  │                                   │ • Test-Induced Design Damage    │
│ • Stable Dependencies Principle │                                   │ • Mocking at Architectural I/O  │
│ • High Cohesion, Low Coupling   │                                   │ • Anti-fragile Assertions       │
└────────────────┬────────────────┘                                   └────────────────┬────────────────┘
                 │                                                                     │
                 └──────────────────────────────┬──────────────────────────────────────┘
                                                ▼
                               ┌─────────────────────────────────┐
                               │   HASIL EVALUASI CODE REVIEW    │
                               ├─────────────────────────────────┤
                               │ • Isolasi Domain Murni          │
                               │ • Zero I/O Leaks di Use Cases   │
                               │ • Test yang Tahan Refaktorisasi │
                               │ • Dependensi Eksplisit & Terarah│
                               └─────────────────────────────────┘
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Penyebab utama kegagalan sebuah sistem jangka panjang bukanlah algoritma yang lambat, melainkan **erosi arsitektural (*architectural drift*)**. Erosi ini terjadi secara perlahan, 10 baris per PR, ketika reviewer meloloskan pelanggaran kecil: dependensi database yang masuk ke entitas domain, instansiasi service pihak ketiga secara langsung di *use case*, atau tes yang melakukan *mocking* terhadap setiap kelas internal.

Dampaknya terhadap lifecycle software bersifat eksponensial:
1. **Regresi Berantai (*High Blast Radius*):** Perubahan kecil pada skema database merusak logika kalkulasi bisnis karena model ORM digunakan sebagai entitas domain.
2. **Kerapuhan Tes (*Test Brittleness*):** Tim takut melakukan refaktorisasi internal karena tes ditulis terlalu terikat dengan implementasi teknis (*mock-heavy test*). Mengubah nama fungsi privat atau struktur internal mematahkan 50 pengujian meskipun perilaku eksternalnya identik.
3. **Ketergantungan Siklik (*Tight Coupling*):** Modul tidak dapat dideploy atau diuji secara independen. Waktu kompilasi melonjak, dan waktu onboarding tim baru melambat drastis.

Reviewer adalah benteng pertahanan terakhir untuk menjaga agar integritas arsitektural tidak dikorbankan demi kecepatan jangka pendek.

---

## SEKSI 05 — APA ITU (WHAT)

Review arsitektural dan pengujian mencakup lima pilar utama:

### 1. Clean Architecture & The Dependency Rule
Aturan universal menyatakan bahwa **kode lapisan dalam (core domain/use case) tidak boleh mengetahui keberadaan kode lapisan luar (database, framework, transport layer/HTTP, UI)**. Ketergantungan kode sumber hanya boleh mengarah ke dalam (*inward dependency*).

### 2. Batas Modul (*Module Boundaries*)
Batas fisik atau logis (misalnya: *package*, *namespace*, atau *workspace*) yang membungkus kapabilitas bisnis tertentu. Batas ini harus mengekspos seminimal mungkin detail internal (*information hiding*).

### 3. Coupling & Cohesion
* **Coupling:** Tingkat saling ketergantungan antar-modul. Target: *Afferent Coupling* ($C_a$) terpusat pada komponen stabil; *Efferent Coupling* ($C_e$) dibatasi via abstraksi.
* **Cohesion:** Seberapa erat seluruh elemen di dalam sebuah modul bekerja untuk satu tanggung jawab bisnis (*Single Responsibility Principle* pada level modul).

### 4. Strategi Testing Bermakna
Pengujian yang memverifikasi spesifikasi bisnis dan invariant sistem, bukan struktur kode internal. Pengujian ini fokus pada *sociable unit testing* (menguji unit beserta kolaborator aslinya di memori) dibanding *solitary testing* (mengisolasi setiap modul dengan *mock* buatan).

### 5. Mocking Boundaries
Penentuan garis batas isolasi pengujian yang benar. *Mocking* hanya boleh diizinkan pada komponen yang melintasi batasan proses (*out-of-process boundaries*), seperti: *network calls*, *file system*, I/O perangkat keras, atau *clock primitives*. Menggunakan mock pada objek domain murni merupakan *code smell* arsitektural.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

Reviewer harus menggunakan pendekatan sistematis saat meninjau PR yang melibatkan perubahan arsitektural dan pengujian. Terapkan algoritma review berikut:

```
[Mulai Review PR]
       │
       ▼
[Analisis Impor & Dependensi]: Apakah ada layer dalam yang mengimpor layer luar?
       ├───────► (Ya) ──► TOLAK: Laporkan pelanggaran Dependency Rule.
       ▼ (Tidak)
[Evaluasi Entitas Domain]: Apakah Entity terkontaminasi anotasi ORM/Web Framework?
       ├───────► (Ya) ──► REKOMENDASI: Pisahkan Persistence Model dari Domain Model.
       ▼ (Tidak)
[Pemeriksaan Batas Modul]: Apakah interface dimiliki oleh klien (consumer) atau penyedia (provider)?
       ├───────► (Provider) ──► REKOMENDASI: Inversi dependensi (Interface Segregation).
       ▼ (Consumer)
[Inspeksi Strategi Mocking pada Test]: Apakah test mem-mock domain entity/value object/collaborator internal?
       ├───────► (Ya) ──► REFACTOR TEST: Larang over-mocking, uji via Public API.
       ▼ (Tidak)
[Verifikasi Ketahanan Test]: Apakah test akan gagal jika struktur kelas internal diubah tanpa mengubah output bisnis?
       ├───────► (Ya) ──► REFACTOR TEST: Fokus ke assertion State/Output, bukan Call Counts.
       ▼ (Tidak)
[SETUJUI PR / APPROVE]
```

### Prosedur Audit Komponen:
1. **Periksa File `import` / `using` / `require`:** 
   Pastikan tidak ada dependensi yang melanggar aturan layer:
   * `domain` $\rightarrow$ tidak boleh mengimpor `infrastructure`, `presentation`, `usecase`.
   * `usecase` $\rightarrow$ tidak boleh mengimpor `infrastructure`, `controllers`, `framework`.
   * `infrastructure` $\rightarrow$ boleh mengimpor `usecase` dan `domain` (mengimplementasikan *driven ports*).
2. **Evaluasi Definisi Interface:**
   Pastikan interface (*ports*) didefinisikan di lapisan konsumen (*Application Core*), bukan di lapisan implementasi (*Infrastructure*).
3. **Audit Assertions pada Test:**
   Cari penggunaan `.verify()`, `.toHaveBeenCalledWith()`, atau verifikasi pemanggilan metode privat yang berlebihan. Alihkan ke pengecekan nilai kembalian (*state verification*) atau mutasi *observable state*.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Pelanggaran Dependensi vs Dependensi Bersih

```
ARUS DEPENDENSI SALAH (Kotor/Coupled)
┌────────────────┐        ┌────────────────┐        ┌────────────────┐
│   Controller   ├───────►│    UseCase     ├───────►│  PostgresRepo  │
└────────────────┘        └────────────────┘        └────────────────┘
(Framework/HTTP)             (Business)                (Infrastructure/DB)
                                                            ▲
                                                            │ (Direct Dependency)
                                                   Beban I/O Bocor ke Core!

───────────────────────────────────────────────────────────────────────────

ARUS DEPENDENSI BERSIH (Clean Architecture / Ports & Adapters)
Boundary: [ Core / Domain ]
┌────────────────────────────────────────────────────────┐
│                                                        │
│  ┌────────────────┐           ┌─────────────────────┐  │
│  │    UseCase     ├──────────►│  «Port/Interface»   │  │
│  │                │           │     OrderRepo       │  │
│  └────────────────┘           └──────────▲──────────┘  │
│                                          │             │
└──────────────────────────────────────────┼─────────────┘
                                           │ (Implements / Inverts)
Boundary: [ Infrastructure / Out-of-Process]│
                                ┌──────────┴──────────┐
                                │   PostgresAdapter   │
                                └─────────────────────┘
```

### 2. Batas Mocking yang Benar vs Salah

```
SALAH: Over-Mocked Solitary Testing (Fragile)
┌───────────────────────────────────────────────────────────────────────┐
│ [TEST RUNNER]                                                         │
│     │                                                                 │
│     ├────► (Executes) ──► [UseCase]                                   │
│     │                        │                                        │
│     ├─(Mock Validator) ◄─────┤ (Terkunci ke struktur internal)        │
│     ├─(Mock Domain Entity) ◄─┤ (Test tahu detail kalkulasi privat)    │
│     └─(Mock Database Port) ◄─┘                                        │
└───────────────────────────────────────────────────────────────────────┘
Hasil: Refaktorisasi nama method internal merusak tes secara instan.

BENAR: Sociable Unit Test pada Batas Arsitektural (Resilient)
┌───────────────────────────────────────────────────────────────────────┐
│ [TEST SUITE]                                                          │
│     │                                                                 │
│     ▼                                                                 │
│ ┌────────────────────────────────────────────────┐                    │
│ │ Core Context Under Test                        │                    │
│ │                                                │                    │
│ │  [UseCase] ──► [Validator] ──► [Domain Entity] │                    │
│ │     │           (Real/Asli)      (Real/Asli)   │                    │
│ └─────┼──────────────────────────────────────────┘                    │
│       │ (Melintasi Batas I/O Luar)                                    │
│       ▼                                                               │
│ ┌────────────────────────────────────────────────┐                    │
│ │ [Mock / In-Memory Database Adapter]            │◄── Titik Isolasi   │
│ └────────────────────────────────────────────────┘     yang Sah       │
└───────────────────────────────────────────────────────────────────────┘
Hasil: Struktur internal bisa bebas direfaktor tanpa merusak tes sama sekali.
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah contoh kebocoran detail implementasi (ORM Entity) ke domain logic dan perbaikannya.

### Kode Bermasalah (Anti-Pattern)

```typescript
// model/user.model.ts (Infrastructure Layer - TypeORM)
import { Entity, Column, PrimaryGeneratedColumn } from "typeorm";

@Entity()
export class UserModel {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column()
  name!: string;

  @Column()
  balance!: number;

  @Column()
  lastTransactionAt!: Date;
}

// services/billing.service.ts (Domain/Use-case Layer)
import { UserModel } from "../model/user.model"; // REVIEW VIOLATION: Core mengimpor Infra ORM!

export class BillingService {
  public debitUser(user: UserModel, amount: number): void {
    if (user.balance < amount) {
      throw new Error("Insufficient funds");
    }
    // Manipulasi langsung model database
    user.balance -= amount;
    user.lastTransactionAt = new Date();
  }
}
```

### Masalah Arsitektural:
1. `BillingService` bergantung langsung pada `UserModel` yang dipenuhi anotasi TypeORM.
2. Jika skema database diubah atau ORM diganti (misalnya ke Prisma/Kysely), domain logic ikut rusak.
3. Unit test untuk `BillingService` terpaksa membawa dependensi modul database.

### Kode Solusi (Refactored)

```typescript
// domain/entities/user.entity.ts (Pure Domain Layer - No DB dependency)
export class User {
  constructor(
    private readonly id: string,
    private balance: number,
    private lastTransactionAt: Date
  ) {}

  public debit(amount: number): void {
    if (amount <= 0) {
      throw new Error("Debit amount must be positive");
    }
    if (this.balance < amount) {
      throw new Error("Insufficient funds");
    }
    this.balance -= amount;
    this.lastTransactionAt = new Date();
  }

  public getBalance(): number {
    return this.balance;
  }
}

// ports/user-repository.port.ts (Application Layer)
import { User } from "../domain/entities/user.entity";

export interface UserRepositoryPort {
  findById(id: string): Promise<User | null>;
  save(user: User): Promise<void>;
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus Produksi: Sistem Pemrosesan Pembayaran (*Order Payment Settlement*). Kita akan melihat bagaimana PR yang buruk menggabungkan controller, ORM, third-party payment gateway, serta pengujian yang *over-mocked*, lalu merefaktornya ke Clean Architecture dengan sociable testing.

### 1. Versi Sebelum Review (PR Mengandung Anti-Pattern)

```typescript
// order.service.ts (Campuran Presentasi, Bisnis, Database, dan Vendor SDK)
import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { OrderEntity } from './order.entity';
import Stripe from 'stripe'; // Leaky third-party library

@Injectable()
export class OrderService {
  private stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, { apiVersion: '2023-10-16' });

  constructor(
    @InjectRepository(OrderEntity)
    private readonly orderRepo: Repository<OrderEntity>,
  ) {}

  async processPayment(orderId: string, amount: number, paymentMethodId: string) {
    const order = await this.orderRepo.findOne({ where: { id: orderId } });
    if (!order) throw new Error("Order not found");
    if (order.status === 'PAID') throw new Error("Already paid");

    // Side-effect langsung tanpa abstraksi
    const paymentIntent = await this.stripe.paymentIntents.create({
      amount: amount * 100,
      currency: 'usd',
      payment_method: paymentMethodId,
      confirm: true,
    });

    if (paymentIntent.status === 'succeeded') {
      order.status = 'PAID';
      order.stripeChargeId = paymentIntent.id;
      return await this.orderRepo.save(order);
    } else {
      order.status = 'FAILED';
      await this.orderRepo.save(order);
      throw new Error("Payment failed");
    }
  }
}
```

```typescript
// order.service.spec.ts (FRAGILE ANTI-PATTERN: Mengetes detail implementasi & over-mocking)
describe('OrderService', () => {
  it('should process payment', async () => {
    const mockRepo = { findOne: jest.fn(), save: jest.fn() };
    const service = new OrderService(mockRepo as any);
    
    // Test harus tahu internal Stripe implementation
    (service as any).stripe = {
      paymentIntents: {
        create: jest.fn().mockResolvedValue({ status: 'succeeded', id: 'ch_123' })
      }
    };

    mockRepo.findOne.mockResolvedValue({ id: '1', status: 'PENDING' });
    mockRepo.save.mockImplementation(o => Promise.resolve(o));

    await service.processPayment('1', 50, 'pm_card');

    // Test sangat rapuh: Memeriksa struktur objek payload stripe internal
    expect((service as any).stripe.paymentIntents.create).toHaveBeenCalledWith({
      amount: 5000,
      currency: 'usd',
      payment_method: 'pm_card',
      confirm: true,
    });
    expect(mockRepo.save).toHaveBeenCalledTimes(1);
  });
});
```

---

### 2. Versi Sesudah Review (Refactored Clean Architecture & Meaningful Testing)

#### Lapisan Core / Domain

```typescript
// src/core/domain/order.ts
export type OrderStatus = 'PENDING' | 'PAID' | 'FAILED';

export class Order {
  constructor(
    private readonly id: string,
    private status: OrderStatus,
    private paymentReference: string | null = null
  ) {}

  public markAsPaid(paymentRef: string): void {
    if (this.status === 'PAID') {
      throw new Error("DomainError: Order is already paid.");
    }
    this.status = 'PAID';
    this.paymentReference = paymentRef;
  }

  public markAsFailed(): void {
    if (this.status === 'PAID') {
      throw new Error("DomainError: Cannot fail a paid order.");
    }
    this.status = 'FAILED';
  }

  public getStatus(): OrderStatus {
    return this.status;
  }

  public getId(): string {
    return this.id;
  }

  public getPaymentReference(): string | null {
    return this.paymentReference;
  }
}
```

#### Lapisan Application / Ports

```typescript
// src/core/ports/payment-gateway.port.ts
export interface ChargeRequest {
  amountInCents: number;
  paymentToken: string;
}

export interface ChargeResult {
  isSuccess: boolean;
  transactionReference: string;
}

export interface PaymentGatewayPort {
  charge(request: ChargeRequest): Promise<ChargeResult>;
}

// src/core/ports/order-repository.port.ts
import { Order } from '../domain/order';

export interface OrderRepositoryPort {
  findById(id: string): Promise<Order | null>;
  save(order: Order): Promise<void>;
}
```

#### Lapisan Use Case

```typescript
// src/core/use-cases/settle-order.use-case.ts
import { OrderRepositoryPort } from '../ports/order-repository.port';
import { PaymentGatewayPort } from '../ports/payment-gateway.port';

export interface SettleOrderCommand {
  orderId: string;
  amount: number;
  paymentToken: string;
}

export class SettleOrderUseCase {
  constructor(
    private readonly orderRepo: OrderRepositoryPort,
    private readonly paymentGateway: PaymentGatewayPort
  ) {}

  async execute(command: SettleOrderCommand): Promise<void> {
    const order = await this.orderRepo.findById(command.orderId);
    if (!order) {
      throw new Error(`OrderNotFound: ${command.orderId}`);
    }

    const chargeResult = await this.paymentGateway.charge({
      amountInCents: Math.round(command.amount * 100),
      paymentToken: command.paymentToken,
    });

    if (chargeResult.isSuccess) {
      order.markAsPaid(chargeResult.transactionReference);
    } else {
      order.markAsFailed();
    }

    await this.orderRepo.save(order);
  }
}
```

#### Pengujian Bermakna (Sociable Unit Testing pada Batas I/O)

```typescript
// test/use-cases/settle-order.use-case.spec.ts
import { SettleOrderUseCase } from '../../src/core/use-cases/settle-order.use-case';
import { Order } from '../../src/core/domain/order';
import { OrderRepositoryPort } from '../../src/core/ports/order-repository.port';
import { PaymentGatewayPort, ChargeRequest, ChargeResult } from '../../src/core/ports/payment-gateway.port';

// FAKE in-memory adapter (bukan mock library yang fragile)
class InMemoryOrderRepository implements OrderRepositoryPort {
  public orders = new Map<string, Order>();

  async findById(id: string): Promise<Order | null> {
    return this.orders.get(id) || null;
  }

  async save(order: Order): Promise<void> {
    this.orders.set(order.getId(), order);
  }
}

class FakePaymentGateway implements PaymentGatewayPort {
  public shouldSucceed = true;
  public generatedReference = "tx_valid_123";

  async charge(req: ChargeRequest): Promise<ChargeResult> {
    return {
      isSuccess: this.shouldSucceed,
      transactionReference: this.shouldSucceed ? this.generatedReference : "tx_failed_000",
    };
  }
}

describe('SettleOrderUseCase (Architectural & Meaningful Test)', () => {
  let orderRepo: InMemoryOrderRepository;
  let paymentGateway: FakePaymentGateway;
  let useCase: SettleOrderUseCase;

  beforeEach(() => {
    orderRepo = new InMemoryOrderRepository();
    paymentGateway = new FakePaymentGateway();
    useCase = new SettleOrderUseCase(orderRepo, paymentGateway);
  });

  it('berhasil memproses pembayaran: status menjadi PAID dan menyimpan transaction reference', async () => {
    // Arrange: Siapkan state domain asli
    const initialOrder = new Order('ord-1', 'PENDING');
    await orderRepo.save(initialOrder);

    // Act: Jalankan Use Case via public API
    await useCase.execute({
      orderId: 'ord-1',
      amount: 100.50,
      paymentToken: 'tok_visa',
    });

    // Assert: Verifikasi perubahan State akhir, bukan verifikasi hit method internal
    const savedOrder = await orderRepo.findById('ord-1');
    expect(savedOrder?.getStatus()).toBe('PAID');
    expect(savedOrder?.getPaymentReference()).toBe('tx_valid_123');
  });

  it('gagal memproses pembayaran: status menjadi FAILED tanpa melempar unhandled crash', async () => {
    const initialOrder = new Order('ord-2', 'PENDING');
    await orderRepo.save(initialOrder);
    paymentGateway.shouldSucceed = false;

    await useCase.execute({
      orderId: 'ord-2',
      amount: 45.00,
      paymentToken: 'tok_declined',
    });

    const savedOrder = await orderRepo.findById('ord-2');
    expect(savedOrder?.getStatus()).toBe('FAILED');
  });

  it('menolak memproses jika order berstatus PAID (Domain Invariant Protection)', async () => {
    const paidOrder = new Order('ord-3', 'PAID', 'tx_prior');
    await orderRepo.save(paidOrder);

    await expect(
      useCase.execute({ orderId: 'ord-3', amount: 10.0, paymentToken: 'tok_any' })
    ).rejects.toThrow("DomainError: Order is already paid.");
  });
});
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Saat mereview arsitektur dan testing, reviewer tidak boleh dogmatis. Terapkan tabel trade-off berikut untuk menimbang konteks aplikasi:

| Dimensi | Keputusan A: Ekstrem Clean Architecture | Keputusan B: Pragmatic Layered Approach | Rekomendasi Kontekstual Reviewer |
| :--- | :--- | :--- | :--- |
| **Separation of Models** | Domain Model dan ORM Entity dipisah secara mutlak 100% menggunakan Mapper. | Model ORM digunakan langsung sebagai Entity jika aplikasi sebatas CRUD sederhana. | Gunakan Pemisahan Mutlak jika terdapat logika bisnis yang kompleks/kritis (Billing, Core Banking). Izinkan penyatuan model pada CRUD Microservice yang berumur pendek. |
| **Testing Strategy** | **Sociable Tests** dengan In-Memory Fakes untuk database dan HTTP ports. | **Solitary Unit Tests** dengan Mocking framework (`jest.fn()`, `Mockito`) di setiap interface. | **Prioritaskan Sociable Tests.** Mocking internal collaborators menimbulkan kerapuhan tinggi dan kepercayaan rendah pada kebenaran sistem. |
| **Mocking Strategy** | Mocking hanya dilakukan pada *System Boundaries* (HTTP Third-Party, Clock, File I/O). | Mocking dilakukan hingga ke level use-case dependencies internal. | **Tolak Mocking pada Internal Class**. Jika sebuah kelas tidak melintasi batas I/O proses sistem, gunakan implementasi asli. |
| **Beban Boilerplate** | Menulis DTO, Domain Model, Persistence Entity, Port Interfaces, dan Mappers. | Satu kelas Entity merangkap DTO API dan ORM Model. | Untuk Enterprise & Long-lived Systems: Terima boilerplate demi membatasi *blast radius*. Untuk prototyping/MVP: Kompromikan mapping layer, namun jaga isolasi test. |

---

## SEKSI 11 — BEST PRACTICES

### Panduan Reviewer (Checklist Arsitektur & Testing)

#### 1. Batas Modul & Arsitektur
* [ ] **Aturan Satu Arah:** Pastikan layer inti (*Domain*) tidak mengimpor modul dari framework luar (*Express*, *NestJS*, *TypeORM*, *Spring Web*).
* [ ] **Port Ownership:** Periksa apakah interface didefinisikan oleh modul pemanggil (konsumen), bukan modul penyedia implementasi.
* [ ] **Zero Leaky Types:** Pastikan tipe data pengembalian repository atau port adalah objek Domain Murni atau Value Object, bukan tipe vendor database (`QueryRunner`, `ObjectId`, dsb).
* [ ] **Explicit Dependency Injection:** Semua dependensi use-case harus diinjeksi via konstruktor, tidak boleh ada inisialisasi internal menggunakan `new Service()` di dalam use case.

#### 2. Testing & Mocking
* [ ] **Uji Behavior, Bukan Implementasi:** Jangan menyetujui assertion yang memverifikasi jumlah panggilan metode internal privat (misal: `expect(service['calculateTax']).toHaveBeenCalledTimes(1)`).
* [ ] **Mocking Hanya di Batas I/O:** Pastikan *mock* hanya digunakan untuk I/O jaringan (Payment Gateway, Webhook Eksternal, SMTP) atau operasi asinkron berat.
* [ ] **Prefer Fakes over Mocks:** Sarankan penggunaan *In-Memory Repository* (menggunakan Map/Array) daripada membuat mock stubbing repo yang kompleks di setiap file test.
* [ ] **Domain Invariant Testing:** Pastikan semua state yang tidak valid (contoh: saldo negatif, kuantitas 0) diuji langsung pada unit test Domain Entity tanpa membutuhkan container or use case runner.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. The Interface-Soup Anti-Pattern
**Gejala:** Author membuat interface untuk setiap kelas tunggal tanpa ada variasi implementasi polimorfik, hanya demi memfasilitasi mocking (`IUserService` untuk `UserService`, `IOrderService` untuk `OrderService`).
**Bahaya:** Menambah kompleksitas navigasi kode tanpa nilai fleksibilitas riil.
**Review Comment:** *"Hindari pembuatan interface 1:1 untuk layer aplikasi jika tujuannya hanya untuk mocking. Gunakan implementasi konkret langsung dalam pengujian atau cukup mock pada batas I/O (Repository/Gateway)."*

### 2. Mocking What You Don't Own
**Gejala:** Melakukan mock langsung pada pustaka pihak ketiga yang rumit, seperti SDK AWS, Stripe, atau Knex.
**Bahaya:** Jika pustaka memperbarui perilakunya (misal pergeseran nama property), test tetap lulus (*green*) padahal aplikasi *crash* di produksi (*runtime failure*).
**Review Comment:** *"Jangan lakukan mock langsung pada library pihak ketiga (`stripe.charges.create`). Bungkus vendor SDK tersebut di dalam Adapter internal (`StripePaymentAdapter`), lalu mock Port/Interface adapter kita sendiri di level Use Case."*

### 3. Database Entity Leaking to Presentation Layer
**Gejala:** Controller mengembalikan objek `@Entity()` TypeORM/JPA langsung ke JSON response.
**Bahaya:** Mengakibatkan *over-fetching*, potensi kebocoran kredensial/hash password secara tidak sengaja, dan kegagalan serialisasi siklis (*circular serialization*).
**Review Comment:** *"Gunakan explicit DTO atau Response ViewModel. Jangan paparkan Database Entity langsung ke Presentation Layer."*

### 4. Test-Induced Design Damage
**Gejala:** Mengubah visibilitas method atau state dari `private` menjadi `public` hanya agar bisa diuji oleh unit test.
**Bahaya:** Merusak enkapsulasi objek dan mengundang konsumen lain memodifikasi internal state secara liar.
**Review Comment:** *"Jangan jadikan method privat menjadi publik hanya untuk testing. Uji method privat tersebut secara tidak langsung melalui public interface dari kelas tersebut."*

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Review: Pull Request Pemeriksaan Medis (E-Health System)

Tinjau cuplikan PR berikut. Temukan minimal **3 pelanggaran arsitektur struktural** dan **2 kecacatan strategi testing**, lalu tuliskan komentar perbaikan resmi setara Technical Lead.

#### Diff Kode: `MedicalPrescriptionService.ts`

```typescript
1  import { Injectable } from '@nestjs/common';
2  import { Repository } from 'typeorm';
3  import { InjectRepository } from '@nestjs/typeorm';
4  import { PrescriptionEntity } from './prescription.entity';
5  import axios from 'axios'; // External HTTP
6
7  @Injectable()
8  export class MedicalPrescriptionService {
9    constructor(
10     @InjectRepository(PrescriptionEntity)
11     private repo: Repository<PrescriptionEntity>
12   ) {}
13
14   async issuePrescription(patientId: string, medicationId: string, dosageMg: number) {
15     if (dosageMg > 500) {
16       throw new Error("Dosage exceeds safety threshold");
17     }
18     
19     // Panggilan langsung ke API eksternal BPJS/Asuransi
20     const response = await axios.post('https://api.insurance.local/validate', {
21       patientId,
22       medicationId
23     });
24     
25     if (!response.data.approved) {
26       throw new Error("Insurance rejected prescription");
27     }
28
29     const entity = this.repo.create({ patientId, medicationId, dosageMg, status: 'ISSUED' });
30     return await this.repo.save(entity);
31   }
32 }
```

#### Diff Test: `MedicalPrescriptionService.spec.ts`

```typescript
1  import { MedicalPrescriptionService } from './MedicalPrescriptionService';
2  import axios from 'axios';
3  
4  jest.mock('axios'); // Mocking library yang tidak dimiliki
5
6  describe('MedicalPrescriptionService', () => {
7    it('should issue prescription when valid', async () => {
8      const mockRepo = { create: jest.fn(), save: jest.fn() };
9      const service = new MedicalPrescriptionService(mockRepo as any);
10     
11     (axios.post as jest.Mock).mockResolvedValue({ data: { approved: true } });
12     mockRepo.create.mockReturnValue({ id: '123' });
13     mockRepo.save.mockResolvedValue({ id: '123', status: 'ISSUED' });
14
15     const result = await service.issuePrescription('p-1', 'm-1', 250);
16
17     // Pengecekan internal call count dan library pihak ketiga
18     expect(axios.post).toHaveBeenCalledTimes(1);
19     expect(mockRepo.create).toHaveBeenCalledWith({ patientId: 'p-1', medicationId: 'm-1', dosageMg: 250, status: 'ISSUED' });
20     expect(result.status).toBe('ISSUED');
21   });
22 });
```

---

### Format Tugas Peserta:
Tuliskan review terstruktur dengan template berikut:
1. **Identifikasi Masalah (File & Baris):** Sebutkan pelanggaran spesifik.
2. **Kategori Pelanggaran:** (Coupling / Dependency Rule / Testing Fragility / Boundary Leak).
3. **Komentar Review Konstruktif:** Jelaskan argumen teknis dan minta refaktorisasi konkret.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan skenario berikut untuk memverifikasi kesiapan evaluasi PR arsitektur:

1. **Sebuah PR memindahkan validasi invariant Domain Entity (misal: "Saldo tidak boleh minus") ke dalam Database Constraint (Check Constraint di PostgreSQL). Bagaimana respon reviewer yang tepat?**
   * A. Setujui, karena database adalah sumber kebenaran mutlak data (*single source of truth*).
   * B. Tolak, karena memindahkan validasi domain ke database memaksa domain logic bergantung pada error runtime database, merusak isolasi domain murni dan membuat pengujian logika membutuhkan database hidup.
   * C. Setujui, asalkan database menggunakan trigger yang memanggil stored procedure.
   * D. Tolak, karena validasi hanya boleh berada di Form Request controller.

2. **Kapan teknik *Sociable Unit Testing* lebih disukai daripada *Solitary Unit Testing*?**
   * A. Ketika berinteraksi dengan API eksternal pihak ketiga yang memiliki rate limit.
   * B. Ketika menguji interaksi antara Use Case, Domain Entities, dan Domain Services yang seluruhnya berada di dalam memori tanpa melintasi batasan proses I/O.
   * C. Ketika menguji performa query basis data SQL.
   * D. Ketika modul yang diuji bergantung pada hardware peripheral printer kasir.

3. **Di sebuah pull request, author menulis interface `UserRepository` di dalam direktori `src/infrastructure/database/repositories/`. Apa komentar reviewer yang benar secara Clean Architecture?**
   * A. Sudah benar, karena interface harus diletakkan bersama dengan implementasinya.
   * B. Salah. Sesuai *Dependency Inversion Principle*, interface (Port) harus dimiliki oleh lapisan pemanggil (*Core/Domain/Application*), sedangkan implementasinya berada di *Infrastructure*.
   * C. Salah. Interface harus diletakkan di global types shared kernel bersama HTTP DTO.
   * D. Bebas, lokasi interface tidak berdampak pada struktur kompilasi dependensi modul.

4. **Apa indikasi utama sebuah unit test mengalami *Test-Induced Fragility* akibat *over-mocking*?**
   * A. Test gagal karena skema koneksi database Docker berubah.
   * B. Test berjalan sangat cepat di pipeline CI/CD (<10 milidetik).
   * C. Ketika developer melakukan refaktorisasi internal (misal: memecah satu method private menjadi dua tanpa mengubah input-output publik), banyak unit test yang *fail* (gagal).
   * D. Test coverage naik melebihi 90%.

5. **Manakah dari dependensi berikut yang SAH untuk diimpor oleh entitas domain murni?**
   * A. Framework validasi pihak ketiga seperti `@nestjs/common` atau `@Entity()` TypeORM.
   * B. Library helper primitif seperti pustaka matematika murni atau parsing tanggal berbasis standar ISO (yang tidak melakukan I/O).
   * C. Klien gRPC untuk memanggil microservice lain.
   * D. Instance dari HTTP Request context untuk membaca auth header.

---

### Kunci Jawaban & Rasional Self-Assessment

* **1: B** — Logika domain harus mampu menolak state yang tidak valid di memori sebelum menyentuh I/O database. Mengandalkan database constraint untuk logika domain merusak siklus feedback cepat dari unit testing.
* **2: B** — Sociable unit testing menguji unit bersama komponen riil di memori, memberikan keyakinan (*confidence*) yang jauh lebih tinggi tanpa kerapuhan mocking berlebih.
* **3: B** — Inversi dependensi menuntut agar abstraksi didefinisikan oleh modul tingkat tinggi (*higher-level policy*), bukan modul tingkat rendah (*low-level detail*).
* **4: C** — Kerapuhan tes (*test brittleness*) dicirikan oleh kegagalan pengujian saat refaktorisasi dilakukan, meskipun fungsionalitas dan output publiknya tidak berubah.
* **5: B** — Lapisan domain murni dapat menggunakan pustaka algoritma deterministik murni, tetapi dilarang keras bergantung pada framework, I/O, atau komponen transport eksternal.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku Standar Industri:**
  * *Clean Architecture: A Craftsman's Guide to Software Structure and Design* — Robert C. Martin (Uncle Bob).
  * *Unit Testing Principles, Practices, and Patterns* — Vladimir Khorikov (Referensi definitif untuk Sociable vs Solitary testing dan Mocking Boundaries).
  * *Domain-Driven Design: Tackling Complexity in the Heart of Software* — Eric Evans.
  * *Working Effectively with Legacy Code* — Michael Feathers.
* **Makalah & Arsitektur Referensi:**
  * *Hexagonal Architecture (Ports and Adapters)* — Alistair Cockburn.
  * *The Onion Architecture* — Jeffrey Palermo.
* **Peralatan Architectural Linter (Automated Architecture Testing):**
  * **ArchUnit** (Java/Kotlin) / **ArchUnitNET** (.NET) / **ts-arch** (TypeScript): Pustaka untuk menulis tes otomatis yang memverifikasi bahwa layer domain tidak mengimpor layer infra di level CI pipeline.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **Review arsitektur adalah pelindung integritas modularitas.** Menyetujui pelanggaran dependensi kecil hari ini akan mengakibatkan utang teknis (*technical debt*) yang melumpuhkan kemampuan sistem untuk berevolusi di masa depan.
2. **The Inward Dependency Rule adalah hukum absolut.** Framework, transport HTTP, dan implementasi database adalah detail di lapisan luar (*Infrastructure*). Lapisan inti (*Domain & Use Case*) tidak boleh memiliki dependensi kode ke lapisan luar.
3. **Hindari over-mocking.** Mocking terhadap kelas internal adalah penyebab utama pengujian yang rapuh (*brittle tests*). Lakukan mocking secara eksklusif hanya pada batasan fisik I/O atau batasan proses (*network, disk, clock primitives*).
4. **Pilih Sociable Testing daripada Solitary Testing.** Biarkan objek-objek domain bekerja sama secara riil di memori dalam unit test Anda untuk memvalidasi *state* dan *behavior*, bukan sekadar menguji verifikasi pemanggilan fungsi (*interaction verification*).

---

## SEKSI 17 — GLOSARIUM

* **Afferent Coupling ($C_a$):** Jumlah kelas/modul di luar modul ini yang bergantung pada kelas/modul di dalam modul ini. (Tingkat tanggung jawab modul).
* **Efferent Coupling ($C_e$):** Jumlah kelas/modul di luar modul ini yang digunakan oleh modul ini. (Tingkat ketergantungan modul terhadap lingkungan luar).
* **Instability Index ($I$):** Rasio $I = \frac{C_e}{(C_a + C_e)}$. Nilai 0 berarti modul sangat stabil (sulit diubah, banyak yang bergantung padanya); nilai 1 berarti modul sangat tidak stabil (mudah diubah, bergantung pada banyak modul lain).
* **Sociable Unit Testing:** Pendekatan unit test di mana kelas yang diuji (*System Under Test*) menggunakan kolaborator aslinya di memori tanpa mem-mock mereka, selama kolaborator tersebut tidak melakukan operasi I/O jaringan/disk.
* **Solitary Unit Testing:** Pendekatan unit test di mana semua dependensi dan kolaborator dari *System Under Test* digantikan dengan *Test Doubles* (Mock/Stub), mengisolasi kelas sepenuhnya dari ekosistemnya.
* **Leaky Abstraction:** Kondisi di mana detail implementasi teknis dari lapisan bawah menyusup atau terpaksa diketahui oleh lapisan di atasnya yang seharusnya bersih dari abstraksi tersebut.
* **Port:** Interface yang mengekspresikan kebutuhan abstraksi dari use case atau domain (*Driving* atau *Driven* port).
* **Adapter:** Implementasi konkret dari sebuah Port yang berkomunikasi dengan teknologi luar tertentu (contoh: PostgreSQL adapter mengimplementasikan `OrderRepositoryPort`).

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Poin Penekanan Materi:**
  * Tekankan bahwa menolak PR karena alasan arsitektural membutuhkan empati teknis. Reviewer harus memberikan alternatif implementasi (*diff code* pembanding), bukan hanya sekadar memberikan label "Arsitektur Salah".
  * Pastikan siswa memahami bahaya metrik Code Coverage: PR dengan 100% test coverage bisa saja memiliki nilai uji mendekati 0 jika seluruh tesnya menggunakan over-mocking dan hanya memeriksa *interaction verification* (`expect(mock).toHaveBeenCalled()`).
* **Format Simulasi Workshop:**
  * Sediakan repository Git tiruan dengan 3 PR bermasalah.
  * Tugaskan siswa berperan sebagai Tech Lead yang melakukan audit dependensi modul menggunakan diagram coupling, lalu menolak PR tersebut dengan catatan arsitektural yang mendalam.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0 (Maret 2025):**
  * Rilis inisial kurikulum Advanced Code Review Architecture & Testing.
  * Penambahan materi Sociable vs Solitary testing dan batas mocking.
  * Standardisasi format silabus 20-seksi.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `06-Architecture-and-System-Design/06-03-Scalability-Concurrency-Resilience-Review.md`
* **Modul Berikutnya:** `06-Architecture-and-System-Design/07-02-Reviewing-Distributed-Systems-Events-Sagas.md`
* **Root Index:** `code-review/curriculum-manifest.md`