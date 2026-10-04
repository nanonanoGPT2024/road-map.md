# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 07: Review Maintainability & Clean Architecture**  
**Topik: Code Review | Kategori: 06-Architecture-and-System-Design**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Mengidentifikasi Pelanggaran Batas Arsitektural (*Architectural Boundary Violations*)**: Menganalisis *Pull Request* (PR) untuk mendeteksi *dependency inversion breach*, kebocoran abstraksi (*leaky abstractions*), dan percampuran domain logic dengan detail infrastruktur (database, network, framework).
2. **Menegakkan Integritas Domain & Ports/Adapters**: Mengaudit kode domain agar tetap murni (*pure domain*), bebas dari dependensi pustaka pihak ketiga (*third-party libraries*), anotasi framework ORM, atau protokol transport (HTTP/gRPC/Kafka).
3. **Mengotomatisasi Pemeriksaan Arsitektural dalam CI/CD**: Merancang dan mengimplementasikan *Architectural Fitness Functions* (menggunakan perkakas seperti ArchUnit atau `dependency-cruiser`) untuk memblokir regresi arsitektur secara otomatis sebelum tahap manual review.
4. **Memberikan Feedback Terstruktur & Aksi Refaktorisasi Terukur**: Menulis komentar code review level arsitektur yang solutif, membedakan antara *strategic design flaw* dengan *cosmetic code issue*, serta memberikan rekomendasi pola (*design patterns*) yang tepat.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
* Prinsip SOLID (khususnya *Single Responsibility*, *Interface Segregation*, dan *Dependency Inversion Principle*).
* Fondasi Clean Architecture (Robert C. Martin), Hexagonal Architecture (Alistair Cockburn), dan dasar Domain-Driven Design (Tactical Patterns: Entity, Value Object, Aggregate, Domain Service, Repository Interface).
* Pengalaman membaca dan mengaudit Git diff pada sistem berskala menengah hingga besar (>50.000 baris kode).
* Pemahaman dasar tentang static analysis dan konfigurasi CI/CD pipeline (GitHub Actions/GitLab CI).

---

## 3. Concept & Internal Architecture (Mendalam)

### The Dependency Rule & Boundary Integrity
Dalam Clean Architecture dan Hexagonal Architecture, aturan fundamental yang tidak boleh dilanggar adalah **The Dependency Rule**: *Source code dependencies must point only inward, toward higher-level policies*.

```
+-----------------------------------------------------------------+
| Frameworks & Drivers (Web, DB, UI, External Interfaces, Devices) |
|   +-----------------------------------------------------------+  |
|   | Interface Adapters (Controllers, Gateways, Presenters)     |  |
|   |   +-----------------------------------------------------+  |  |
|   |   | Application Business Rules (Use Cases / Interactors)|  |  |
|   |   |   +-----------------------------------------------+ |  |  |
|   |   |   | Enterprise Business Rules (Entities / Domain) | |  |  |
|   |   |   +-----------------------------------------------+ |  |  |
|   |   +-----------------------------------------------------+  |  |
|   +-----------------------------------------------------------+  |
+-----------------------------------------------------------------+
           Inward Dependency Vector ---> [ Core Domain ]
```

Saat melakukan review, seorang reviewer senior harus memeriksa arah vektor dependensi pada setiap deklarasi `import` atau `package dependency`.

### Anatomi Pelanggaran Arsitektur dalam Code Review

1. **Leaky Framework Annotations**:
   * *Masalah*: Entitas domain diberi anotasi ORM seperti `@Entity`, `@Table`, `@Column` (JPA/Hibernate) atau tag struct `gorm:"primaryKey"` / `@Prop()` (Mongoose/TypeORM).
   * *Dampak*: Domain terikat secara siklis dengan skema database relasional atau dokumen. Perubahan driver/ORM memaksa modifikasi pada core domain model.
2. **Context Poisoning (Protocol Coupling)**:
   * *Masalah*: Melewatkan objek HTTP request/response (`http.Request`, `express.Request`, `gin.Context`) ke dalam layer Use Case atau Domain Service.
   * *Dampak*: Logika bisnis tidak dapat dieksekusi melalui antarmuka alternatif (misal: CLI, gRPC, background worker Kafka) tanpa memalsukan (*mocking*) struktur HTTP.
3. **Implicit Dual-State Mutation (Bypass Port)**:
   * *Masalah*: Use Case memanggil client SDK infrastruktur secara langsung (misal: AWS S3 SDK, Redis Client) tanpa melalui abstraksi Port (*interface*).
   * *Dampak*: Menghancurkan unit-testability, mengunci sistem ke vendor spesifik (*vendor lock-in*), dan mempersulit implementasi *circuit breaker* atau *fallbacks*.

### Architectural Fitness Functions
Review manual rentan terhadap *human error* dan *reviewer fatigue*. Oleh karena itu, arsitektur harus dilindungi oleh pengujian terprogram (*architectural fitness functions*). Pemeriksaan ini mengevaluasi struktur graf kode (AST - *Abstract Syntax Tree*) untuk memastikan tidak ada edge impor yang melanggar aturan layer.

---

## 4. Why & What

| Dimensi | Sintaks / Clean Code Review | Architectural Code Review |
| :--- | :--- | :--- |
| **Fokus Utama** | Gaya penulisan (*naming convention*, format kode, kompleksitas siklomatis kecil, *code smells* lokal). | Batas modul (*module boundaries*), arah dependensi (*coupling/cohesion*), segregasi fungsional, dan pemisahan state vs side-effects. |
| **Dampak Kegagalan Deteksi** | Penurunan keterbacaan kode (*readability*), bug lokal minor. | Erosi arsitektur (*architectural drift*), *shotgun surgery* (perubahan satu fitur merusak 15 modul lain), *monolithic entanglement*. |
| **Metrik Evaluasi** | SonarQube rules, ESLint, Checkstyle, cognitive complexity index. | Afferent Coupling ($Ca$), Efferent Coupling ($Ce$), Instability ($I = \frac{Ce}{Ca + Ce}$), Abstractness ($A$), Distance from the Main Sequence ($D$). |
| **Frekuensi Perbaikan** | Refaktorisasi instan (menit/jam). | Restrukturisasi besar (hari/minggu/kuartal). |

Seorang reviewer arsitektur senior bertindak sebagai gerbang (*gatekeeper*) yang memastikan bahwa peningkatan kecepatan jangka pendek (*velocity shortcut*) tidak menghasilkan *technical debt* struktural yang melumpuhkan skalabilitas sistem di masa depan.

---

## 5. How (Workflow Detail)

Berikut adalah 5-tahap standar alur review arsitektur saat memeriksa *Pull Request*:

```
[PR Diajukan]
      │
      ▼
┌────────────────────────────────────────────────────────┐
│ Tahap 1: Evaluasi Automated Fitness Functions          │
│ - Apakah ArchUnit / dependency-cruiser lolos di CI?    │
└──────────────────────────┬─────────────────────────────┘
                           │ Lolos
                           ▼
┌────────────────────────────────────────────────────────┐
│ Tahap 2: Tinjau Manifest Dependensi & Struktur Modul    │
│ - Apakah ada modul/library eksternal baru di Domain?   │
│ - Periksa package.json / go.mod / pom.xml              │
└──────────────────────────┬─────────────────────────────┘
                           │ Sesuai
                           ▼
┌────────────────────────────────────────────────────────┐
│ Tahap 3: Validasi Domain Purity & Boundary Crossings   │
│ - Cek Domain: Adakah kebocoran ORM, HTTP, atau Cloud?  │
│ - Cek Use Case: Apakah komunikasi via Port (Interface)?│
└──────────────────────────┬─────────────────────────────┘
                           │ Sesuai
                           ▼
┌────────────────────────────────────────────────────────┐
│ Tahap 4: Verifikasi Data Flow & DTO Boundary Crossing  │
│ - Apakah Entity terekspos keluar Use Case?             │
│ - Apakah Adapter menggunakan Input/Output DTO & Mapper?│
└──────────────────────────┬─────────────────────────────┘
                           │ Sesuai
                           ▼
┌────────────────────────────────────────────────────────┐
│ Tahap 5: Audit Test Topology & Mocking Strategy       │
│ - Domain: Murni Unit Test tanpa Mocking Framework?     │
│ - Use Case: Mocking dibatasi hanya pada Port Interface?│
│ - Adapter: Contract/Integration Tests nyata?           │
└──────────────────────────┬─────────────────────────────┘
                           │ Valid
                           ▼
                     [PR Disetujui]
```

### Panduan Operasional Reviewer per Tahap:
1. **Verifikasi Fitness Check**: Tolak PR secara otomatis jika fitness check CI gagal. Jangan buang waktu manusia untuk PR yang melanggar batasan dependensi statis.
2. **Audit Import Statements**: Buka file diff pada direktori `core/domain` atau `domain/`. Gunakan regex `grep -E "import .* from .*(infra|framework|http|express|database)"` untuk mendeteksi kontaminasi.
3. **Analisis Injeksi Dependensi**: Periksa constructor/factory function di Application Layer. Pastikan dependensi yang diterima adalah *Interface type*, bukan *Struct/Class type* konkret dari layer Infrastructure.
4. **Inspeksi Antikorupsi (ACL)**: Pastikan data eksternal dari Third-Party API dipetakan (*mapped*) ke dalam domain model menggunakan *Mapper/Translator*, bukan digunakan mentah-mentah di Use Case.

---

## 6. Analogy & Diagram ASCII

Bayangkan sebuah **Ruang Operasi Rumah Sakit Bersih (*Sterile Operating Room*)**:

* **Domain Model = Pasien & Dokter Bedah (Zona Steril)**: Tidak boleh ada kuman, lumpur, atau pakaian jalanan. Hanya alat medis murni yang diizinkan masuk.
* **Ports (Interfaces) = *Air Lock Chamber* / Kotak Transfer**: Sarana pertukaran instrumen medis dan material secara higienis tanpa membuka akses langsung ke udara luar.
* **Adapters = Staf Pendukung & Logistik Luar**: Menyediakan listrik, oksigen, dan antibiotik dari luar. Mereka menyesuaikan tegangan listrik kota atau format suplai agar sesuai dengan standar ruang operasi.

Jika seorang dokter bedah (Domain) keluar ke trotoar becek (Database/HTTP) hanya untuk mengambil pisau bedah, seluruh ruang operasi terkontaminasi.

```
+-----------------------------------------------------------------------------------+
| INFRASTRUCTURE / ADAPTERS LAYER (Kotor / Penuh Dependensi Luar)                   |
|                                                                                   |
|  [PostgreSQL Adapter]      [REST API Controller]      [Kafka Event Publisher]     |
|          │                           │                          ▲                 |
|          │ implements                │ calls                    │ implements      |
|          ▼                           ▼                          │                 |
|  ┌───────────────┐           ┌───────────────┐          ┌──────────────────────┐  |
|  │ SecondaryPort │           │  PrimaryPort  │          │   SecondaryPort      │  |
|  │ (Repository)  │           │   (UseCase)   │          │ (MessageBusPort)     │  |
+──┴───────▲───────┴───────────┴───────▲───────┴──────────┴──────────▲───────────┴──+
           │                           │                             │
═══════════╪═══════════════════════════╪═════════════════════════════╪═══════════════
           │ BOUNDARY LINE: DEPENDENCY INVERSION BARRIER              │
═══════════╪═══════════════════════════╪═════════════════════════════╪═══════════════
           │                           │                             │
+──────────┴───────────────────────────┴─────────────────────────────┴──────────────+
| CORE APPLICATION & DOMAIN LAYER (Steril / Pure TypeScript/Go/Java)                |
|                                                                                   |
|          ┌──────────────────────────────────────────────────┐                     |
|          │ OrderFulfillmentUseCase (Application Service)    │                     |
|          └─────────────────────────┬────────────────────────┘                     |
|                                    │ orchestrates                                 |
|                                    ▼                                              |
|                    ┌───────────────────────────────┐                              |
|                    │  Order (Domain Aggregate)     │                              |
|                    │  - calculateTax()             │                              |
|                    │  - addLineItem()              │                              |
|                    └───────────────────────────────┘                              |
+-----------------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### Simple Example: Pelanggaran Kebocoran ORM vs Solusi Bersih

#### BAD (Diff PR yang Ditolak Reviewer)
Domain Aggregate terkontaminasi oleh TypeORM library dan format persistensi data.

```typescript
// File: src/domain/entities/Order.ts
import { Entity, PrimaryGeneratedColumn, Column } from "typeorm"; // PELANGGARAN: Domain terikat Framework!

@Entity("orders")
export class Order {
  @PrimaryGeneratedColumn("uuid")
  public id!: string;

  @Column({ type: "varchar", length: 100 })
  public customerName!: string;

  @Column({ type: "decimal", precision: 10, scale: 2 })
  public totalAmount!: number;

  // Masalah: Mengabaikan invariant bisnis; setter terbuka bebas, mutasi sembarangan
}
```

#### GOOD (Perbaikan yang Direkomendasikan Reviewer)
Domain murni tanpa dekorator ORM, menerapkan enkapsulasi invarian domain.

```typescript
// File: src/domain/entities/Order.ts
export class Order {
  private constructor(
    private readonly id: string,
    private customerName: string,
    private totalAmount: number
  ) {}

  public static create(id: string, customerName: string): Order {
    if (!customerName || customerName.trim().length === 0) {
      throw new Error("Customer name cannot be empty.");
    }
    return new Order(id, customerName, 0);
  }

  public addLineItem(price: number, quantity: number): void {
    if (price <= 0 || quantity <= 0) {
      throw new Error("Price and quantity must be positive values.");
    }
    this.totalAmount += price * quantity;
  }

  public getId(): string { return this.id; }
  public getCustomerName(): string { return this.customerName; }
  public getTotalAmount(): number { return this.totalAmount; }
}
```

---

### Practical Example: Flow Registrasi Pengguna Skala Enterprise

Berikut adalah contoh komprehensif sistem registrasi akun. Kita membandingkan implementasi cacat yang sering lolos review santai dengan implementasi standar produksi Clean Architecture.

#### Skenario PR Buruk (Melanggar Arsitektur)

```typescript
// File: src/usecases/RegisterUser.ts
import { Request, Response } from "express"; // PELANGGARAN 1: Terikat Protocol HTTP!
import bcrypt from "bcrypt";                  // PELANGGARAN 2: Terikat Detail Kriptografi Langsung
import { dbConnection } from "../infra/db";  // PELANGGARAN 3: Hard-coupled ke DB Client konkret

export class RegisterUserController {
  // Masalah: Menggabungkan Use Case, Controller, dan Data Access
  public async handle(req: Request, res: Response): Promise<void> {
    const { email, password } = req.body;

    // Validasi logic bercampur di controller
    const userExists = await dbConnection.query("SELECT * FROM users WHERE email = $1", [email]);
    if (userExists.rows.length > 0) {
      res.status(400).json({ error: "Email already taken" });
      return;
    }

    const hashedPassword = await bcrypt.hash(password, 10);
    const result = await dbConnection.query(
      "INSERT INTO users (email, password) VALUES ($1, $2) RETURNING id",
      [email, hashedPassword]
    );

    res.status(201).json({ userId: result.rows[0].id });
  }
}
```

#### Skenario Refaktor Standar Produksi (Approved Architecture)

##### 1. Domain Layer: Murni dan Bebas Dependensi
```typescript
// File: src/core/domain/value-objects/Email.ts
export class Email {
  private readonly value: string;

  private constructor(email: string) {
    this.value = email;
  }

  public static create(email: string): Email {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email || !emailRegex.test(email)) {
      throw new Error("Invalid email address format.");
    }
    return new Email(email.toLowerCase().trim());
  }

  public getValue(): string {
    return this.value;
  }
}

// File: src/core/domain/entities/User.ts
import { Email } from "../value-objects/Email";

export class User {
  private constructor(
    private readonly id: string,
    private readonly email: Email,
    private readonly passwordHash: string,
    private readonly createdAt: Date
  ) {}

  public static create(id: string, email: Email, passwordHash: string): User {
    return new User(id, email, passwordHash, new Date());
  }

  public getId(): string { return this.id; }
  public getEmail(): Email { return this.email; }
  public getPasswordHash(): string { return this.passwordHash; }
}
```

##### 2. Application Layer: Ports & Use Case
```typescript
// File: src/core/application/ports/outbound/UserRepositoryPort.ts
import { User } from "../../../domain/entities/User";

export interface UserRepositoryPort {
  findByEmail(email: string): Promise<User | null>;
  save(user: User): Promise<void>;
}

// File: src/core/application/ports/outbound/PasswordHasherPort.ts
export interface PasswordHasherPort {
  hash(plainText: string): Promise<string>;
  compare(plainText: string, hashed: string): Promise<boolean>;
}

// File: src/core/application/ports/inbound/RegisterUserUseCase.ts
export interface RegisterUserCommand {
  email: string;
  plainPassword: string;
}

export interface RegisterUserResponse {
  userId: string;
}

export interface RegisterUserUseCase {
  execute(command: RegisterUserCommand): Promise<RegisterUserResponse>;
}

// File: src/core/application/usecases/RegisterUserInteractor.ts
import { RegisterUserUseCase, RegisterUserCommand, RegisterUserResponse } from "../ports/inbound/RegisterUserUseCase";
import { UserRepositoryPort } from "../ports/outbound/UserRepositoryPort";
import { PasswordHasherPort } from "../ports/outbound/PasswordHasherPort";
import { Email } from "../../domain/value-objects/Email";
import { User } from "../../domain/entities/User";

export class RegisterUserInteractor implements RegisterUserUseCase {
  constructor(
    private readonly userRepo: UserRepositoryPort,
    private readonly hasher: PasswordHasherPort,
    private readonly idGenerator: () => string
  ) {}

  public async execute(command: RegisterUserCommand): Promise<RegisterUserResponse> {
    const emailVO = Email.create(command.email);

    const existingUser = await this.userRepo.findByEmail(emailVO.getValue());
    if (existingUser !== null) {
      throw new Error("ConflictException: User with this email already exists.");
    }

    if (command.plainPassword.length < 8) {
      throw new Error("ValidationException: Password must be at least 8 characters.");
    }

    const hashedPassword = await this.hasher.hash(command.plainPassword);
    const newUser = User.create(this.idGenerator(), emailVO, hashedPassword);

    await this.userRepo.save(newUser);

    return { userId: newUser.getId() };
  }
}
```

##### 3. Infrastructure / Adapter Layer: Concrete Implementations
```typescript
// File: src/adapters/outbound/database/PostgresUserRepository.ts
import { UserRepositoryPort } from "../../../core/application/ports/outbound/UserRepositoryPort";
import { User } from "../../../core/domain/entities/User";
import { Email } from "../../../core/domain/value-objects/Email";
import { Pool } from "pg";

export class PostgresUserRepository implements UserRepositoryPort {
  constructor(private readonly dbPool: Pool) {}

  public async findByEmail(email: string): Promise<User | null> {
    const query = "SELECT id, email, password_hash FROM users WHERE email = $1 LIMIT 1";
    const { rows } = await this.dbPool.query(query, [email]);

    if (rows.length === 0) return null;

    const row = rows[0];
    return User.create(row.id, Email.create(row.email), row.password_hash);
  }

  public async save(user: User): Promise<void> {
    const query = "INSERT INTO users (id, email, password_hash) VALUES ($1, $2, $3)";
    await this.dbPool.query(query, [
      user.getId(),
      user.getEmail().getValue(),
      user.getPasswordHash()
    ]);
  }
}

// File: src/adapters/inbound/http/RegisterUserController.ts
import { Request, Response } from "express";
import { RegisterUserUseCase } from "../../../core/application/ports/inbound/RegisterUserUseCase";

export class RegisterUserController {
  constructor(private readonly useCase: RegisterUserUseCase) {}

  public async handle(req: Request, res: Response): Promise<void> {
    try {
      const { email, password } = req.body;
      const result = await this.useCase.execute({
        email,
        plainPassword: password
      });
      res.status(201).json(result);
    } catch (error: any) {
      if (error.message.startsWith("ConflictException")) {
        res.status(409).json({ error: error.message });
      } else if (error.message.startsWith("ValidationException") || error.message.includes("Invalid email")) {
        res.status(400).json({ error: error.message });
      } else {
        res.status(500).json({ error: "Internal server error" });
      }
    }
  }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario Insiden: Payment Service Core Banking Entanglement
* **Perusahaan**: Platform FinTech Payment Gateway dengan transaksi 12.000 TPS (*Transactions Per Second*).
* **Insiden**: Kegagalan rilis v3.4 yang menyebabkan *cascading failure* database selama 45 menit saat peak load.
* **Akar Masalah (Root Cause)**:
  PR fitur *"Multi-Currency Dynamic Fee"* disetujui tanpa audit arsitektural yang ketat. Pengembang menyuntikkan `EntityManager` ORM langsung ke dalam Domain Entity `Payment` untuk mengambil kurs valuta asing secara *lazy-loading*.
  
  ```typescript
  // PR Berbahaya yang lolos review
  class Payment {
    calculateTotal() {
      // Bencana: Lazy loading query terpanggil di dalam loop agregat domain
      const rate = this.entityManager.find(ExchangeRate, this.currency); 
      return this.amount * rate.multiplier;
    }
  }
  ```

* **Dampak**:
  1. Ketika pemrosesan batch pembayaran berjalan, pemanggilan kalkulasi memicu masalah query $N+1$ di tingkat koneksi database, menghabiskan seluruh connection pool RDS (1.500 koneksi drop total).
  2. Entity tidak lagi dapat diuji secara independen tanpa *full-blown relational database running*. Unit test digantikan oleh mocking kompleks yang rapuh (*brittle tests*).

### Intervensi & Koreksi Arsitektur (Review Remediation Plan)
Lead Architect memblokir deployment dan menginstruksikan perbaikan sebagai berikut:
1. **Penerapan Anti-Corruption Layer (ACL)**: Kurs mata uang harus disediakan sebagai *Value Object* `ExchangeRate` yang di-fetch secara eksplisit di level Application Interactor sebelum memanggil method `Payment.calculateTotal(rate: ExchangeRate)`.
2. **Fitness Gate Enforcement**: Menambahkan aturan statis yang melarang impor *persistence layer packages* pada seluruh direktori domain. PR langsung di-reject jika terdapat import `@orm` atau `EntityManager`.
3. **Hasil**: Database load turun 82%, throughput transaksi kembali stabil pada 14.500 TPS tanpa lag replikasi, dan cakupan unit test murni untuk domain naik menjadi 98%.

---

## 9. Trade-offs

Mengimplementasikan dan menegakkan Clean Architecture secara kaku memiliki konsekuensi teknis dan operasional yang harus dipahami oleh reviewer:

| Parameter | Desain Murni (Clean Architecture Rigor) | Desain Pragmatis / Cepat (Direct Scripting) | Analisis Trade-off |
| :--- | :--- | :--- | :--- |
| **Throughput & Latensi** | Sedikit penalti memori & siklus CPU akibat konversi DTO $\leftrightarrow$ Domain Entity $\leftrightarrow$ DB Model. | Performa mentah lebih cepat karena membaca/menulis data langsung dari/ke stream DB/HTTP. | Dalam 99% aplikasi enterprise, overhead mapping (<2ms) dapat diabaikan dibanding I/O database latency (10-50ms). |
| **Boilerplate & File Footprint** | Sangat tinggi. Butuh Interface, Interactor, DTO, Mapper, dan Model terpisah. | Sangat rendah. 1 Controller melayani seluruh query dan respons. | Peningkatan kompleksitas struktural (*accidental complexity*) dapat memperlambat tim junior pada fase awal proyek (MVP). |
| **Maintainability & Refactoring** | Ekstrem tinggi. Penggantian database atau transport library tidak memicu regresi domain. | Rendah. Perubahan skema DB berdampak langsung ke representasi API dan domain. | Investasi arsitektur terbayar lunas ketika sistem berusia >12 bulan atau dikerjakan oleh >3 tim pengembang. |
| **Cognitive Load saat Review** | Reviewer harus melompat antar 4-6 file per fitur untuk memvalidasi alur. | Reviewer cukup membaca 1 file script monolitik secara sekuensial. | Reviewer memerlukan pemahaman komprehensif mengenai dependency graph, bukan sekadar logika baris per baris. |

---

## 10. Common Mistakes & Troubleshooting

### Anti-Pattern 1: The "Anemic Domain" with God Interactor
* *Gejala*: Seluruh entity hanya berisi getter/setter tanpa logic (seperti plain DTO), sementara seluruh aturan validasi dan perhitungan bisnis menumpuk di Interactor Use Case hingga ribuan baris.
* *Solusi Reviewer*: Instruksikan author untuk memindahkan logika pemrosesan state ke dalam Domain Entity atau Domain Service jika melibatkan multiple-entities.

### Anti-Pattern 2: The "Pass-Through" Use Case
* *Gejala*: Interactor Use Case tidak melakukan apapun selain menerima DTO dari Controller dan memanggil `repository.save()` secara langsung tanpa validasi bisnis.
* *Solusi Reviewer*: Identifikasi apakah ada kebutuhan *Command/Query Responsibility Segregation* (CQRS). Untuk alur Read murni, lewati Use Case domain dan buat read-only adapter query khusus (*bypass to read model*) guna mencegah over-engineering.

### Anti-Pattern 3: Interface Bloat (The 1:1 Interface Anti-Pattern)
* *Gejala*: Membuat interface untuk setiap class tanpa alasan abstraksi (misal `UserServiceImpl` mengimplementasikan `UserService`), tetapi tidak ada polimorfisme ataupun batasan layer.
* *Solusi Reviewer*: Terapkan *Interface Segregation Principle* (ISP). Interface hanya wajib dibuat pada batasan dependensi (*architectural boundaries*) di mana Dependency Inversion dibutuhkan (misal: Application $\rightarrow$ Infrastructure).

### Panduan Troubleshooting Dependensi Sirkular (*Circular Dependency Detection*)
Jika build gagal akibat circular imports pasca pemisahan modul:
1. Gambar dependency directed acyclic graph (DAG).
2. Temukan simpul yang menyebabkan siklus (biasanya Use Case A memanggil Use Case B, dan B memanggil A).
3. **Penyelesaian**: 
   * Gabungkan kedua logic jika kohesi temporalnya tinggi.
   * Ekstrak domain event menggunakan Publisher-Subscriber Port. Use Case A menerbitkan `OrderCreatedDomainEvent`, dan Handler Use Case B mendengarkan secara asinkron/terisolasi.

---

## 11. Best Practices (Production Checklist)

### Checklist untuk Code Reviewer

- [ ] **Dependency Direction**: Apakah seluruh tanda panah dependensi mengarah ke dalam? Pastikan tidak ada dependensi dari `core/domain` ke layer manapun di luarnya.
- [ ] **Domain Purity**: Bebas dari framework HTTP (Express, Nest, Gin, Spring MVC), database client (TypeORM, Prisma, Mongo, JPA), dan vendor SDK (AWS, GCP, Stripe).
- [ ] **Interface Ownership**: Apakah Interface Port diletakkan di layer yang mengonsumsinya (*Application Layer*), bukan di layer implementasinya (*Infrastructure Layer*)?
- [ ] **Data Encapsulation**: Apakah invariant domain terlindungi? Tidak ada public setter yang mengekspos internal mutable state.
- [ ] **DTO Leaks**: Apakah output API Controller me-return Entity Domain secara langsung ke klien? Pastikan wajib menggunakan Presenter / Output DTO Mapper.
- [ ] **Error Handling Boundaries**: Apakah exception database (misal: `PgError: unique violation`) diterjemahkan menjadi Domain/Application Exception (misal: `EntityAlreadyExistsException`) sebelum melewati port batas?
- [ ] **Automated Fitness**: Apakah unit test domain tidak menggunakan database nyata maupun mocking engine yang kompleks?

### Checklist untuk PR Author

- [ ] Menjalankan verifikasi static architecture checker (`npm run lint:arch` atau `./gradlew testArch`) secara lokal sebelum membuka PR.
- [ ] Menyertakan diagram boundary traversal singkat pada deskripsi PR jika menambahkan modul interaksi baru.
- [ ] Memastikan tidak membagikan Entity Database schema yang sama ke dalam Domain Layer.

---

## 12. Hands-on Practice

Dalam sesi praktikum ini, Anda akan menyiapkan tool verifikasi arsitektur statis otomatis menggunakan `dependency-cruiser` di environment Node.js / TypeScript. 

### Langkah Praktikum:

#### 1. Struktur Direktori Proyek
Buat direktori kerja di `hands-on/m02/`:
```bash
mkdir -p hands-on/m02/src/{core/{domain,application},adapters/{inbound,outbound}}
cd hands-on/m02
npm init -y
npm install --save-dev dependency-cruiser typescript @types/node
```

Pastikan struktur file Anda sebagai berikut:
```
hands-on/m02/
├── .dependency-cruiser.js
├── package.json
├── tsconfig.json
└── src/
    ├── core/
    │   ├── domain/
    │   │   └── User.ts
    │   └── application/
    │       ├── ports/
    │       │   └── UserRepositoryPort.ts
    │       └── RegisterUser.ts
    └── adapters/
        ├── inbound/
        │   └── UserController.ts
        └── outbound/
            └── PostgresUserRepository.ts
```

#### 2. Konfigurasi `tsconfig.json`
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true
  }
}
```

#### 3. Buat Aturan Arsitektur `.dependency-cruiser.js`
File ini bertindak sebagai fitness function yang memvalidasi bahwa core domain tidak dapat mengimpor adapter atau application layer.

```javascript
// hands-on/m02/.dependency-cruiser.js
module.exports = {
  forbidden: [
    {
      name: "domain-must-not-depend-on-outer-layers",
      comment: "Aturan Utama Clean Architecture: Domain Core tidak boleh bergantung pada Application atau Adapters",
      severity: "error",
      from: { path: "^src/core/domain" },
      to: { path: "^src/(core/application|adapters)" }
    },
    {
      name: "application-must-not-depend-on-adapters",
      comment: "Application Core hanya boleh bergantung pada Domain, dilarang direct dependency ke Adapters",
      severity: "error",
      from: { path: "^src/core/application" },
      to: { path: "^src/adapters" }
    },
    {
      name: "adapters-cannot-cross-talk-directly",
      comment: "Inbound adapters tidak boleh mengimpor Outbound adapters secara langsung tanpa melalui Core",
      severity: "error",
      from: { path: "^src/adapters/inbound" },
      to: { path: "^src/adapters/outbound" }
    }
  ],
  options: {
    doNotFollow: {
      path: "node_modules"
    },
    tsPreCompilationDeps: true
  }
};
```

#### 4. Buat File Kode Demonstrasi Pelanggaran

Buat file `src/core/domain/User.ts` yang sengaja melanggar aturan arsitektur:

```typescript
// hands-on/m02/src/core/domain/User.ts
// KESALAHAN SENGAJA: Mengimpor adapter dari dalam domain
import { PostgresUserRepository } from "../../adapters/outbound/PostgresUserRepository";

export class User {
  constructor(public id: string, public name: string) {}

  public saveBadPractice(): void {
    const repo = new PostgresUserRepository();
    repo.persist(this);
  }
}
```

Buat mock adapter `src/adapters/outbound/PostgresUserRepository.ts`:
```typescript
// hands-on/m02/src/adapters/outbound/PostgresUserRepository.ts
export class PostgresUserRepository {
  public persist(data: any): void {
    console.log("Saving to DB...", data);
  }
}
```

#### 5. Eksekusi Pengujian Arsitektur Otomatis
Tambahkan skrip pada `package.json`:
```json
"scripts": {
  "lint:arch": "depcruise --config .dependency-cruiser.js src"
}
```

Jalankan perintah pengujian:
```bash
npm run lint:arch
```

**Hasil Terminal yang Diharapkan (Build Gagal Otomatis)**:
```text
  error domain-must-not-depend-on-outer-layers: src/core/domain/User.ts -> src/adapters/outbound/PostgresUserRepository.ts

3 modules, 1 dependencies cruised. 1 error, 0 warnings.
```

#### 6. Refaktorisasi Perbaikan (Memperbaiki Diff PR)
Hapus import kotor pada `src/core/domain/User.ts` dan pindahkan operasi penyimpanan ke Application layer melalui Interface Port. Jalankan kembali `npm run lint:arch` dan pastikan status keluar adalah `0 error`.

---

## 13. Exercise

### Level Easy
Seorang software engineer junior mengajukan PR di mana pada file `src/core/domain/Account.ts` terdapat impor:
`import { formatCurrency } from "@/shared/utils/date-formatter";`  
Lakukan audit review: Apakah impor utilitas umum (*common utility*) diizinkan di dalam core domain? Apa potensi risikonya jika utility tersebut mengonsumsi runtime browser atau library berat seperti `moment.js`? Tuliskan komentar review Anda secara formal.

### Level Medium
Periksa cuplikan kode PR berikut untuk fitur transfer saldo:

```typescript
export class TransferMoneyService {
  constructor(private accountRepo: AccountRepository) {}

  async transfer(fromId: string, toId: string, amount: number) {
    const from = await this.accountRepo.get(fromId);
    const to = await this.accountRepo.get(toId);

    from.balance -= amount;
    to.balance += amount;

    await this.accountRepo.update(from);
    await this.accountRepo.update(to);
  }
}
```
Temukan 3 kelemahan maintainability dan arsitektural (pertimbangkan enkapsulasi domain, penanganan konkurensi/transaksi data, dan invariant state). Tuliskan rekomendasi refaktorisasi konkret.

### Level Hard
Sebuah tim sedang mengintegrasikan multi-tenant database routing. Di dalam PR yang diajukan, developer meletakkan logic pengecekan header `x-tenant-id` di dalam middleware, lalu menyuntikkan string `tenantId` tersebut ke semua signature fungsi domain:  
`user.calculateDiscount(tenantId: string, voucherCode: string)`.  
Rancang arsitektur review yang solutif untuk mengabstraksikan tenant isolation context tanpa mengotori domain signature method menggunakan teknik *Execution Context / AsyncLocalStorage Port*.

---

## 14. Challenge

### Konteks Kasus Produksi
Anda adalah Principal Engineer di platform e-Commerce Global. Tim Checkout sedang melakukan migrasi dari monolit legasi ke arsitektur modular (*Hexagonal*). 

Mereka membuka PR raksasa (*+2.400 baris diff*) dengan deskripsi: *"Implementasi Checkout Saga Menggunakan RabbitMQ dan Postgres Outbox Pattern"*.

### Temuan Awal saat Review:
1. File domain `OrderPlacedEvent` berisi objek transport RabbitMQ `amqplib.Message`.
2. Di dalam Use Case `CheckoutOrderUseCase`, transaksi database dikelola dengan memanggil `DatabaseTransactionManager.beginTransaction()` konkret dari PostgreSQL driver library.
3. Tim beralasan: *"Ini diperlukan agar kita bisa mempublikasikan pesan outbox dalam transaksi database yang sama (Atomicity)."*
4. Tidak ada batasan modul otomatis di CI; dependensi antar-layer hanya diatur oleh kesepakatan lisan tim.

### Tugas Tantangan:
1. Susun **Review Block Document** resmi yang menolak PR ini secara konstruktif namun tegas. Jelaskan dampak kegagalan operasional jika PR ini di-merge ke sistem produksi.
2. Buat rancangan refaktorisasi arsitektur (*code sketch*) yang menunjukkan bagaimana transaksi atomik (Outbox Pattern) dapat dieksekusi dari Application Layer tanpa mengekspos dependency library Postgres ke dalam interactor bisnis inti.
3. Rancang fitness function rule (berbasis AST atau file pattern) untuk memastikan tidak ada engineer lain yang bisa memanggil SQL transaction manager secara telanjang di dalam core business logic.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)

#### Q1. Apa tujuan mendasar dari "The Dependency Rule" dalam Clean Architecture?
A. Memastikan kode dikompilasi lebih cepat dengan meminimalkan file.  
B. Menjamin bahwa komponen internal (kebijakan bisnis) tidak mengetahui apapun tentang komponen eksternal (mekanisme delivery/penyimpanan).  
C. Mengharuskan setiap tabel database memiliki satu representasi file class yang identik di domain.  
D. Memaksa pengembang menggunakan framework microservice modern.  
*Jawaban*: **B**  
*Penjelasan*: Inti aturan dependensi adalah mengisolasi model bisnis tingkat tinggi dari volatilitas perubahan framework, basis data, antarmuka pengguna, dan library eksternal.

#### Q2. Apa indikator paling jelas dari pelanggaran domain purity pada pull request?
A. Tidak adanya komentar JSDoc/Javadoc pada public method.  
B. Adanya decorator ORM (seperti `@Column`) atau framework HTTP (seperti `@Param`) di dalam entitas domain.  
C. Penggunaan tipe data primitif seperti `string` atau `number`.  
D. Jumlah baris kode dalam file lebih dari 100 baris.  
*Jawaban*: **B**  
*Penjelasan*: Entitas domain murni hanya boleh bergantung pada tipe data internal bahasa dan pustaka logika murni, bukan metadata persistensi atau transport.

#### Q3. Istilah "Anemic Domain Model" mengacu pada kondisi di mana:
A. Domain tidak memiliki koneksi langsung ke driver SQL.  
B. Domain model hanya bertindak sebagai struktur data pasif (getter/setter) dan kehilangan logika perilaku bisnis operasionalnya.  
C. Domain model terlalu banyak mengonsumsi RAM server.  
D. Domain menggunakan interface yang tidak memiliki implementasi.  
*Jawaban*: **B**  
*Penjelasan*: Anemic Domain Model terjadi ketika entitas bisnis kehilangan tanggung jawab komputasi logikanya, yang kemudian tercecer di controller atau interactor.

#### Q4. Dimana lokasi deklarasi Port Interface yang benar menurut arsitektur Hexagonal?
A. Di dalam Infrastructure Layer bersama database adapters.  
B. Di file konfigurasi `.env`.  
C. Di dalam Core Application Layer tempat use case dijalankan.  
D. Di dalam Third-Party SDK.  
*Jawaban*: **C**  
*Penjelasan*: Sesuai Dependency Inversion Principle, tingkat abstraksi yang lebih tinggi (Application) mendefinisikan port yang dibutuhkannya; adapter konkret di luar yang mengimplementasikannya.

#### Q5. Apa fungsi utama DTO (Data Transfer Object) saat melewati batas arsitektur (*crossing boundaries*)?
A. Mempercepat serialisasi JSON menjadi byte array.  
B. Mengisolasi representasi internal domain entity agar tidak terekspos langsung ke kontrak luar API atau skema tabel.  
C. Menyediakan cache cadangan di memori CPU.  
D. Menghilangkan kebutuhan untuk menulis unit test.  
*Jawaban*: **B**  
*Penjelasan*: DTO berfungsi sebagai media kontrak isolasi data murni antar-lapisan untuk mencegah keterikatan struktur internal domain dengan payload eksternal.

---

### Bagian 2: Intermediate (Analisis Singkat)

#### Q6. Mengapa melempar SQL-specific Exception langsung dari Repository ke Use Case dianggap sebagai bad practice saat di-review?
*Jawaban*: Karena merusak abstraksi layer (*leaky abstraction*). Jika Use Case harus menangkap `NpgsqlException` atau `MongoServerError`, Use Case tersebut secara tidak langsung terikat ke engine database spesifik. Repository harus memetakan exception tersebut menjadi domain-specific error (contoh: `EntityNotFoundException` atau `DuplicateKeyException`).

#### Q7. Jelaskan bahaya penggunaan pola "Shared Kernel" yang tidak terkendali antar modul bounded context dalam repo monolitik!
*Jawaban*: Shared Kernel menciptakan *high afferent coupling*. Perubahan minor pada salah satu class utilitas atau model di Shared Kernel dapat memicu efek domino (*shotgun surgery*), mematahkan build dan fungsi di berbagai bounded context yang independen.

#### Q8. Kapan seorang code reviewer harus menolak mocking terhadap Domain Entity dalam unit test?
*Jawaban*: Reviewer harus SELALU menolak mocking terhadap domain entity. Domain entity harus berupa *Plain Old Object* yang deterministik dan cepat dieksekusi di memori tanpa I/O. Jika sebuah entity perlu di-mock, itu merupakan *smell* kuat bahwa entity tersebut telah terkontaminasi dependensi eksternal atau I/O.

#### Q9. Apa perbedaan esensial dalam me-review "Input Port" vs "Output Port"?
*Jawaban*: Input Port merepresentasikan *entry point* Use Case yang dipanggil oleh Inbound Adapter (misal: Controller memanggil `RegisterUserUseCase`). Output Port adalah interface dependensi yang dipanggil oleh Use Case dan diimplementasikan oleh Outbound Adapter (misal: Use Case memanggil `UserRepositoryPort` yang diimplementasikan oleh `PostgresUserRepository`).

#### Q10. Developer mengajukan PR yang menggunakan `EventEmitter` global internal Node.js untuk orkestrasi transaksi keuangan antar use case. Bagaimana Anda mengevaluasinya?
*Jawaban*: PR harus ditolak. Menggunakan global in-memory event emitter untuk transaksi finansial berbahaya: ketiadaan jaminan *at-least-once delivery*, rentan *lost events* saat pod/server restart, hilangnya boundary transaksi, dan mempersulit penelusuran aliran eksekusi (*stack trace decoupling hell*). Harus diarahkan menggunakan transactional outbox atau domain events yang persisten.

---

### Bagian 3: Evaluasi Kasus Produksi Riil

#### Kasus A: The Fast-Paced Startup Debt
* **Kasus**: Sebuah startup fintech rilis cepat meloloskan kode di mana API handler membaca request payload, membuka transaksi MongoDB, melakukan hash password, memanggil Stripe API, lalu mengirim email konfirmasi dalam satu fungsi handler 180 baris. Perusahaan kini berkembang dan ingin menambahkan interface antarmuka gRPC untuk integrasi internal.
* **Pertanyaan Reviewer**: Apa hambatan struktural terbesar yang dihadapi tim? Susun roadmap 3 langkah refaktorisasi bertahap tanpa menghentikan delivery fitur baru!
* **Solusi**:
  1. *Hambatan*: Logic Stripe, Mongo, dan hashing terkunci rapat di HTTP transport framework (gRPC tidak bisa memanggil fungsi tersebut tanpa mensimulasikan objek HTTP).
  2. *Langkah 1*: Ekstrak seluruh business logic kalkulasi dan validasi dari handler ke Interactor Use Case baru dengan parameter plain Command Object (DTO).
  3. *Langkah 2*: Abstraksikan Stripe dan MongoDB ke dalam Output Ports (Interfaces). Implementasikan adapter untuk MongoDB dan Stripe secara terpisah.
  4. *Langkah 3*: Buat gRPC Handler baru yang memanggil Use Case yang sama persis seperti yang dipanggil oleh HTTP handler.

#### Kasus B: The Shared Entity Trap
* **Kasus**: Developer membuat class `UserEntity` yang digunakan bersama oleh 3 Bounded Context: `AuthenticationContext`, `BillingContext`, dan `ShippingDeliveryContext`. Saat tim Shipping menambahkan field alamat, build tim Auth gagal karena validasi model pecah.
* **Pertanyaan Reviewer**: Mengapa DRY (Don't Repeat Yourself) disalahartikan dalam konteks ini? Bagaimana arsitektur yang benar dalam memisahkan entitas tersebut?
* **Solusi**:
  1. *Kesalahan DRY*: Developer menyamakan duplikasi kode struktural (*code shape*) dengan duplikasi domain logic (*business behavior*). Konteks Auth, Billing, dan Delivery memiliki siklus hidup dan alasan perubahan (*reasons to change*) yang sama sekali berbeda.
  2. *Solusi*: Pecah menjadi 3 entitas terpisah: `AuthUser` (hanya id, email, password), `BillingCustomer` (hanya id, payment method, invoice address), dan `Recipient` (hanya id, nama penerima, koordinat pengiriman). Gunakan id global bersama untuk korelasi antar-konteks.

#### Kasus C: The Vendor-Locked Domain
* **Kasus**: Tim data streaming mengajukan PR pipeline agregasi real-time. Di domain core, mereka mengimpor decorator `@KafkaListener` dari library framework vendor langsung di method kalkulasi risiko penipuan (*fraud detection aggregate*).
* **Pertanyaan Reviewer**: Apa risiko jangka panjang terhadap kemampuan pengujian (*testability*) dan upgrade framework? Bagaimana desain Adapter yang benar untuk kasus event streaming ini?
* **Solusi**:
  1. *Risiko*: Kalkulasi fraud tidak bisa diuji tanpa memutar Kafka test runner container (*high test execution time*). Upgrade library Kafka berisiko mematahkan domain logic bisnis.
  2. *Desain*: Buat Inbound Adapter `KafkaFraudEventConsumer` yang bertugas menangkap event Kafka, membedah (*deserialize*) payload, memvalidasi schema message, lalu meneruskannya sebagai plain Command Object ke `EvaluateFraudUseCase.execute(command)`. Domain logic murni dari framework streaming.

---

## 16. Summary

1. **Review Arsitektur Bukan Review Sintaks**: Fokus utama seorang Senior Reviewer pada Bab ini adalah menegakkan **The Dependency Rule**, mencegah erosi arsitektural (*architectural drift*), dan memastikan isolasi murni pada Core Domain.
2. **Kedaulatan Core Domain**: Domain layer adalah aset intelektual tertinggi sistem; ia tidak boleh memiliki pengetahuan tentang framework, database, network transport, ataupun vendor SDK pihak ketiga.
3. **Ports & Adapters Sebagai Firewall**: Komunikasi dari Use Case ke dunia luar wajib melalui abstraksi *Port (Interface)*. Infrastruktur konkret berada di luar dan bergantung pada domain melalui *Dependency Inversion*.
4. **Otomatisasi via Fitness Functions**: Kerapuhan review manual manusia harus ditopang oleh alat evaluasi arsitektur statis otomatis (*ArchUnit, dependency-cruiser*) dalam CI/CD pipeline untuk secara mutlak mencegah masuknya pelanggaran dependensi ke trunk utama kode produksi.