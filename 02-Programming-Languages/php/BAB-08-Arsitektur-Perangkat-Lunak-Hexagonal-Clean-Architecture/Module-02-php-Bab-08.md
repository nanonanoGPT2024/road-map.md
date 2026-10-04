# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (Hexagonal & Clean Architecture)

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik pada level Senior Engineer / Tech Lead diharapkan mampu:
- **Merancang & Mengimplementasikan** struktur enterprise *Hexagonal Architecture* (Ports and Adapters) dan *Clean Architecture* menggunakan PHP 8.2/8.3 secara agnostik terhadap framework.
- **Mengisolasi Domain Core** dari *infrastructure leakages* dengan menerapkan teknik *tactical Domain-Driven Design (DDD)*: Aggregates, Entities, Value Objects, Domain Events, dan Domain Services.
- **Membangun Kontrak Driven & Driving Ports** yang *resilient* menggunakan teknik *Inversion of Control (IoC)*, *Data Transfer Objects (DTO)*, dan *Interface Segregation*.
- **Mengintegrasikan Pola Persistensi Modern** tanpa merusak *invariance* Domain (memisahkan Doctrine ORM / Native DBAL dari model Domain inti menggunakan *Data Mappers* manual atau *Custom Hydrators*).
- **Mengeksekusi Pola Transaksional Tingkat Lanjut** seperti *Transactional Outbox Pattern* dan *Unit of Work* untuk menjaga integritas data lintas port driven.
- **Mendeteksi dan Memvalidasi Batasan Arsitektur (Architectural Fitness Functions)** secara otomatis pada CI/CD menggunakan *Deptrac* dan *PHPStan (Level 8+)*.

---

## 2. Prerequisite
Sebelum mendalami modul lanjutan ini, engineer wajib menguasai:
- **Pemrograman Berorientasi Objek Lanjutan (PHP 8.2+)**: `readonly classes`, `Enums`, `First-class callable syntax`, `Intersection types`, dan manipulasi *Attributes*.
- **Prinsip SOLID Tingkat Dalam**: Khususnya pemahaman mendalam atas *Dependency Inversion Principle (DIP)* dan *Interface Segregation Principle (ISP)*.
- **Pola Desain Dasar**: Repository, Adapter, Strategy, Factory, dan Command Pattern.
- **Tooling Ekosistem PHP Modern**: Composer autoloader optimization, PHPUnit 10+, PHPStan/Psalm, dan dasar abstraksi SQL (PDO/Doctrine DBAL).

---

## 3. Concept & Internal Architecture (Mendalam)

### A. Anatomi Port and Adapters vs. Clean Architecture
Meskipun dicetuskan oleh figur berbeda (Alistair Cockburn untuk Hexagonal dan Robert C. Martin untuk Clean Architecture), keduanya memiliki satu tujuan inti: **The Dependency Rule**. Ketergantungan kode hanya boleh mengarah ke dalam, menuju domain bisnis.

```
       [ HTTP / CLI / AMQP ] (Driving Adapters / Primary)
                │
                ▼
     [ Driving Ports / Input Ports ] (Interfaces/UseCases)
                │
┌───────────────┼────────────────────────────────────────┐
│ DOMAIN CORE   │                                        │
│               ▼                                        │
│       [ Application / Use Cases ]                      │
│               │                                        │
│               ▼                                        │
│       [ Domain Model (Entities, VOs, Events) ]         │
│               ▲                                        │
│               │                                        │
│     [ Driven Ports / Output Ports ] (Interfaces)       │
└───────────────┼────────────────────────────────────────┘
                │
                ▼
    [ Driven Adapters / Secondary ]
  (MySQL, Redis, S3, Stripe, Outbox)
```

1. **Domain Core (The Hexagon Interior):**
   - **Enterprise Business Rules (Domain Layer):** Berisi *Entities*, *Value Objects*, *Domain Exceptions*, dan *Domain Services*. Layer ini **sama sekali tidak boleh** memiliki dependensi eksternal (bahkan library HTTP Client atau ORM sekalipun). Bebas dari anotasi framework.
   - **Application Business Rules (Application Layer):** Berisi *Use Cases / Command Handlers*, *Driving Port Interfaces*, dan *Driven Port Interfaces*. Mengatur alur eksekusi logika bisnis dan transaksi tanpa mengetahui *bagaimana* data disimpan atau dari mana request berasal.

2. **Ports (The Boundaries):**
   - **Driving (Primary / Inbound) Ports:** Kontrak API aplikasi yang menentukan aksi apa saja yang diizinkan untuk memicu Domain. Biasanya berupa *Use Case Interfaces* atau *Command/Query Handlers*.
   - **Driven (Secondary / Outbound) Ports:** Kontrak yang dibutuhkan oleh Domain untuk berinteraksi dengan dunia luar. Misalnya: `OrderRepositoryInterface`, `PaymentGatewayInterface`, `EventDispatcherInterface`. Didefinisikan di dalam Application/Domain layer, namun diimplementasikan di luar.

3. **Adapters (The Infrastructure):**
   - **Driving (Primary) Adapters:** Mentranslasikan sinyal luar (HTTP Request, CLI Arguments, Antrean Kafka/RabbitMQ) menjadi DTO/Command internal yang dipahami oleh Driving Port.
   - **Driven (Secondary) Adapters:** Mengimplementasikan Driven Port. Mengubah perintah internal Domain menjadi query SQL, API call eksternal, atau mutasi cache Redis.

### B. Isolasi Persistensi Tanpa Framework Leaks
Kesalahan fatal implementasi PHP enterprise adalah memasang anotasi ORM (seperti `#[ORM\Entity]`) langsung pada Domain Entities. Ini menyebabkan *leaky abstraction* di mana daur hidup Entity diatur oleh *Identity Map* dan *Proxy Generator* milik ORM, bukan oleh *Domain Invariant*.

Pendekatan Clean Architecture murni mengharuskan:
- **Domain Entity Murni:** PHP Plain Old Class Object (POPO) tanpa atribut ORM. Konstruktor memvalidasi *invariants*.
- **Data Mapper:** Kelas infrastruktur yang memetakan baris database (atau entitas persistensi Doctrine terpisah) menjadi Domain Entity murni via *Reflection* atau *Named Constructors*, dan sebaliknya.

---

## 4. Why & What

| Dimensi | Pendekatan Monolit Tradisional (Active Record / Fat Controller) | Pendekatan Hexagonal / Clean Architecture Terisolasi |
| :--- | :--- | :--- |
| **Kopling Framework** | Terikat erat pada framework (mis. Eloquent/Symfony Form). Upgrade mayor framework membutuhkan refactor bisnis. | Agnostik. Framework hanyalah driving adapter (delivery mechanism). Ganti framework tanpa menyentuh Domain. |
| **Testabilitas** | Membutuhkan database mock yang lambat atau database transaksi sungguhan untuk integrasi. | Unit test berjalan 100% *in-memory* menggunakan test doubles murni (Fakes/Stubs), mengeksekusi ribuan test dalam milidetik. |
| **Batas Domain (Invariants)**| State dapat diubah dari mana saja (`$user->status = 'ACTIVE'; $user->save()`). Validasi tersebar di Form Request, Controller, dan Observer. | State hanya dapat dimutasi melalui metode perilaku aggregate (`$user->activate(ActivationToken $token)`). State tidak konsisten mustahil dibuat. |
| **Skalabilitas Tim** | Sering terjadi konflik merge pada file model dan controller gemuk (*god classes*). | Batasan yang jelas memungkinkan tim infrastruktur dan tim domain bekerja secara paralel berdasarkan kontrak port. |

---

## 5. How (Workflow Detail)

Alur eksekusi transaksi produksi dalam arsitektur ini mengikuti urutan berikut:

```
[HTTP Request]
       │
       ▼
1. Web Controller (Driving Adapter)
       │ - Ekstraksi raw request
       │ - Validasi sintaks dasar (HTTP 422 jika format JSON rusak)
       │ - Instansiasi Command/DTO
       ▼
2. Use Case Interactor (Driving Port Implementation)
       │ - Membuka transaksi via Driven Port (UnitOfWork / DB Transaction)
       │ - Mengambil Aggregate via Driven Port (Repository)
       │ - Menjalankan logika bisnis internal Aggregate
       │ - Menangkap Domain Events yang dihasilkan
       │ - Menyimpan state baru Aggregate via Driven Port (Repository)
       │ - Menyimpan Domain Events ke Outbox via Driven Port
       │ - Commit transaksi
       ▼
3. Presenter / Response Formatter (Driving Adapter)
       │ - Menangkap output DTO dari Use Case
       │ - Mentranslasikan ke standar API Response (JSON:API / RFC 7807 Problem Details)
       ▼
[HTTP Response]
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Sound System Konser Musik
Pikirkan sebuah **Unit Digital Signal Processing (DSP)** mixer audio profesional.
- **Domain Core:** Sirkuit komputasi DSP yang memproses efek suara, dynamic EQ, dan compression. Sirkuit ini tidak peduli apakah suara berasal dari mikrofon kabel analog XLR, gitar elektrik via jack 6.5mm, atau stream instrumen digital via port USB/Bluetooth.
- **Driving Ports:** Lubang colokan input (XLR Female, 1/4" TRS).
- **Driving Adapters:** Pre-amp dan konverter sinyal yang mengubah gelombang fisik instrumen menjadi sinyal digital yang dimengerti DSP.
- **Driven Ports:** Lubang colokan output (Master XLR Line Out, Monitor Jack Out).
- **Driven Adapters:** Speaker monitor panggung, unit pemancar rekaman siaran TV, atau modul kartu SD recorder. Jika speaker panggung rusak dan diganti merk lain, sirkuit DSP tidak perlu diubah.

```
       DRIVING ADAPTERS                  DOMAIN CORE                  DRIVEN ADAPTERS
    ┌────────────────────┐          ┌───────────────────┐          ┌───────────────────┐
    │  REST API (Symfony)│          │     USE CASES     │          │ Doctrine ORM / PDO│
    │  Controller        │──(DTO)──>│   CreateTransfer  │──(Port)─>│ LedgerPostgreSQL  │
    └────────────────────┘          │                   │          └───────────────────┘
                                    │   [Aggregates]    │
    ┌────────────────────┐          │   LedgerAccount   │          ┌───────────────────┐
    │  AMQP Consumer     │          │   Money (VO)      │          │ Redis Cache       │
    │  RabbitMQ Worker   │──(DTO)──>│   DomainEvents    │──(Port)─>│ AccountCacheAdapter│
    └────────────────────┘          │                   │          └───────────────────┘
                                    │    INTERFACES     │
    ┌────────────────────┐          │ LedgerRepository  │          ┌───────────────────┐
    │  Console CLI       │          │ TransactionManager│          │ Transactional     │
    │  cron/artisan      │──(DTO)──>│ OutboxRepository  │──(Port)─>│ Outbox SQL Engine │
    └────────────────────┘          └───────────────────┘          └───────────────────┘
```

---

## 7. Practical Example (Enterprise-Grade Ledger System)

Implementasi sistem transfer ledger finansial yang menerapkan **Hexagonal Architecture** murni menggunakan PHP 8.3.

### 7.1 Domain Core: Value Objects & Aggregate Root

```php
<?php

declare(strict_types=1);

namespace Enterprise\Ledger\Domain\Model;

// 1. Value Object: Currency
enum Currency: string
{
    case USD = 'USD';
    case IDR = 'IDR';
    case EUR = 'EUR';
}

// 2. Value Object: Money (Immutable, self-validating)
final readonly class Money
{
    public function __construct(
        public int $amountInCents,
        public Currency $currency
    ) {
        if ($this->amountInCents < 0) {
            throw new \InvalidArgumentException('Nilai moneter tidak boleh negatif.');
        }
    }

    public function add(self $other): self
    {
        $this->assertSameCurrency($other);
        return new self($this->amountInCents + $other->amountInCents, $this->currency);
    }

    public function subtract(self $other): self
    {
        $this->assertSameCurrency($other);
        if ($other->amountInCents > $this->amountInCents) {
            throw new \UnderflowException('Saldo tidak mencukupi untuk melakukan pengurangan.');
        }
        return new self($this->amountInCents - $other->amountInCents, $this->currency);
    }

    private function assertSameCurrency(self $other): void
    {
        if ($this->currency !== $other->currency) {
            throw new \InvalidArgumentException("Ketidakcocokan mata uang: {$this->currency->value} vs {$other->currency->value}");
        }
    }
}

// 3. Domain Event Interface & Implementation
interface DomainEventInterface
{
    public function occurredOn(): \DateTimeImmutable;
}

final readonly class FundsTransferredEvent implements DomainEventInterface
{
    public function __construct(
        public string $sourceAccountId,
        public string $destinationAccountId,
        public int $amountInCents,
        public string $currency,
        public \DateTimeImmutable $occurredOn = new \DateTimeImmutable()
    ) {}

    public function occurredOn(): \DateTimeImmutable
    {
        return $this->occurredOn;
    }
}

// 4. Aggregate Root: LedgerAccount
final class LedgerAccount
{
    /** @var list<DomainEventInterface> */
    private array $recordedEvents = [];

    public function __construct(
        private readonly string $accountId,
        private Money $balance,
        private bool $isFrozen = false
    ) {}

    public function debit(Money $amount): void
    {
        $this->assertAccountOperable();
        $this->balance = $this->balance->subtract($amount);
    }

    public function credit(Money $amount): void
    {
        $this->assertAccountOperable();
        $this->balance = $this->balance->add($amount);
    }

    public function recordTransferTo(LedgerAccount $recipient, Money $amount): void
    {
        $this->debit($amount);
        $recipient->credit($amount);

        $this->recordThat(new FundsTransferredEvent(
            sourceAccountId: $this->accountId,
            destinationAccountId: $recipient->getId(),
            amountInCents: $amount->amountInCents,
            currency: $amount->currency->value
        ));
    }

    private function assertAccountOperable(): void
    {
        if ($this->isFrozen) {
            throw new \DomainException("Akun [{$this->accountId}] dibekukan. Mutasi dilarang.");
        }
    }

    private function recordThat(DomainEventInterface $event): void
    {
        $this->recordedEvents[] = $event;
    }

    /** @return list<DomainEventInterface> */
    public function releaseEvents(): array
    {
        $events = $this->recordedEvents;
        $this->recordedEvents = [];
        return $events;
    }

    public function getId(): string
    {
        return $this->accountId;
    }

    public function getBalance(): Money
    {
        return $this->balance;
    }
}
```

### 7.2 Driven Ports: Abstraksi Penyimpanan & Transaksi

```php
<?php

declare(strict_types=1);

namespace Enterprise\Ledger\Application\Port\Driven;

use Enterprise\Ledger\Domain\Model\DomainEventInterface;
use Enterprise\Ledger\Domain\Model\LedgerAccount;

interface LedgerAccountRepositoryInterface
{
    public function lockForUpdate(string $accountId): ?LedgerAccount;
    public function save(LedgerAccount $account): void;
}

interface OutboxRepositoryInterface
{
    public function append(DomainEventInterface $event): void;
}

interface TransactionManagerInterface
{
    /**
     * @template T
     * @param callable(): T $operation
     * @return T
     */
    public function transactional(callable $operation): mixed;
}
```

### 7.3 Driving Port & Use Case Interactor

```php
<?php

declare(strict_types=1);

namespace Enterprise\Ledger\Application\Port\Driving;

use Enterprise\Ledger\Application\Port\Driven\LedgerAccountRepositoryInterface;
use Enterprise\Ledger\Application\Port\Driven\OutboxRepositoryInterface;
use Enterprise\Ledger\Application\Port\Driven\TransactionManagerInterface;
use Enterprise\Ledger\Domain\Model\Currency;
use Enterprise\Ledger\Domain\Model\Money;

final readonly class TransferFundsCommand
{
    public function __construct(
        public string $sourceAccountId,
        public string $targetAccountId,
        public int $amountInCents,
        public string $currencyCode
    ) {}
}

final readonly class TransferResultDTO
{
    public function __construct(
        public bool $success,
        public string $transactionReference,
        public ?string $errorMessage = null
    ) {}
}

interface TransferFundsUseCaseInterface
{
    public function execute(TransferFundsCommand $command): TransferResultDTO;
}

final readonly class TransferFundsInteractor implements TransferFundsUseCaseInterface
{
    public function __construct(
        private LedgerAccountRepositoryInterface $accountRepo,
        private OutboxRepositoryInterface $outboxRepo,
        private TransactionManagerInterface $txManager
    ) {}

    public function execute(TransferFundsCommand $command): TransferResultDTO
    {
        $currency = Currency::from($command->currencyCode);
        $amount = new Money($command->amountInCents, $currency);

        return $this->txManager->transactional(function () use ($command, $amount): TransferResultDTO {
            // Ambil data dengan pessimistic lock untuk mencegah race conditions
            $source = $this->accountRepo->lockForUpdate($command->sourceAccountId);
            $target = $this->accountRepo->lockForUpdate($command->targetAccountId);

            if ($source === null || $target === null) {
                throw new \InvalidArgumentException('Satu atau kedua entitas akun tidak ditemukan.');
            }

            // Eksekusi core domain invariance
            $source->recordTransferTo($target, $amount);

            // Simpan status aggregate
            $this->accountRepo->save($source);
            $this->accountRepo->save($target);

            // Emit events ke outbox table (Transactional Outbox Pattern)
            foreach ($source->releaseEvents() as $event) {
                $this->outboxRepo->append($event);
            }

            return new TransferResultDTO(
                success: true,
                transactionReference: bin2hex(random_bytes(16))
            );
        });
    }
}
```

### 7.4 Driven Adapter: Database Implementation (PDO Native / DBAL)

```php
<?php

declare(strict_types=1);

namespace Enterprise\Ledger\Infrastructure\Adapter\Driven\Persistence;

use Enterprise\Ledger\Application\Port\Driven\LedgerAccountRepositoryInterface;
use Enterprise\Ledger\Application\Port\Driven\OutboxRepositoryInterface;
use Enterprise\Ledger\Application\Port\Driven\TransactionManagerInterface;
use Enterprise\Ledger\Domain\Model\Currency;
use Enterprise\Ledger\Domain\Model\DomainEventInterface;
use Enterprise\Ledger\Domain\Model\LedgerAccount;
use Enterprise\Ledger\Domain\Model\Money;

final readonly class PdoTransactionManager implements TransactionManagerInterface
{
    public function __construct(private \PDO $pdo) {}

    public function transactional(callable $operation): mixed
    {
        $this->pdo->beginTransaction();
        try {
            $result = $operation();
            $this->pdo->commit();
            return $result;
        } catch (\Throwable $e) {
            if ($this->pdo->inTransaction()) {
                $this->pdo->rollBack();
            }
            throw $e;
        }
    }
}

final readonly class SqlLedgerAccountRepository implements LedgerAccountRepositoryInterface
{
    public function __construct(private \PDO $pdo) {}

    public function lockForUpdate(string $accountId): ?LedgerAccount
    {
        $stmt = $this->pdo->prepare('SELECT id, balance_cents, currency, is_frozen FROM accounts WHERE id = :id FOR UPDATE');
        $stmt->execute(['id' => $accountId]);
        $row = $stmt->fetch(\PDO::FETCH_ASSOC);

        if (!$row) {
            return null;
        }

        // Hydration murni: Tanpa ORM, memetakan state DB ke Aggregate Domain
        return new LedgerAccount(
            accountId: (string)$row['id'],
            balance: new Money((int)$row['balance_cents'], Currency::from($row['currency'])),
            isFrozen: (bool)$row['is_frozen']
        );
    }

    public function save(LedgerAccount $account): void
    {
        $stmt = $this->pdo->prepare('UPDATE accounts SET balance_cents = :balance WHERE id = :id');
        $stmt->execute([
            'id' => $account->getId(),
            'balance' => $account->getBalance()->amountInCents,
        ]);
    }
}

final readonly class SqlOutboxRepository implements OutboxRepositoryInterface
{
    public function __construct(private \PDO $pdo) {}

    public function append(DomainEventInterface $event): void
    {
        $stmt = $this->pdo->prepare(
            'INSERT INTO outbox_events (event_type, payload, created_at) VALUES (:type, :payload, :created_at)'
        );
        $stmt->execute([
            'type' => $event::class,
            'payload' => json_encode($event, JSON_THROW_ON_ERROR),
            'created_at' => $event->occurredOn()->format('Y-m-d H:i:s.u'),
        ]);
    }
}
```

### 7.5 Driving Adapter: HTTP Controller

```php
<?php

declare(strict_types=1);

namespace Enterprise\Ledger\Infrastructure\Adapter\Driving\Web;

use Enterprise\Ledger\Application\Port\Driving\TransferFundsCommand;
use Enterprise\Ledger\Application\Port\Driving\TransferFundsUseCaseInterface;

final readonly class TransferFundsController
{
    public function __construct(
        private TransferFundsUseCaseInterface $useCase
    ) {}

    /**
     * @param array<string, mixed> $requestData Payload HTTP yang sudah didecode
     * @return array<string, mixed> JSON API Response Payload
     */
    public function handle(array $requestData): array
    {
        // 1. Ekstraksi dan Validasi Sintaks HTTP dasar
        if (!isset($requestData['from_account'], $requestData['to_account'], $requestData['amount'], $requestData['currency'])) {
            http_response_code(400);
            return ['error' => 'Payload request tidak lengkap.'];
        }

        // 2. Translasi ke Command
        $command = new TransferFundsCommand(
            sourceAccountId: (string)$requestData['from_account'],
            targetAccountId: (string)$requestData['to_account'],
            amountInCents: (int)$requestData['amount'],
            currencyCode: (string)$requestData['currency']
        );

        // 3. Delegasi ke Driving Port
        try {
            $result = $this->useCase->execute($command);
            http_response_code(200);
            return [
                'status' => 'success',
                'reference' => $result->transactionReference,
            ];
        } catch (\UnderflowException $e) {
            http_response_code(422);
            return ['error' => 'Saldo akun asal tidak mencukupi.', 'detail' => $e->getMessage()];
        } catch (\DomainException $e) {
            http_response_code(403);
            return ['error' => 'Pelanggaran aturan domain.', 'detail' => $e->getMessage()];
        } catch (\Throwable $e) {
            http_response_code(500);
            return ['error' => 'Internal server error saat pemrosesan ledger.'];
        }
    }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Konteks Sistem
Platform E-Commerce B2B Global memproses 1.200 transaksi per detik (*peak load*) pada event Flash Sale. Masalah utama arsitektur lama berbasis MVC Active Record:
- Mutasi inventaris menimbulkan *deadlock* pada baris tabel PostgreSQL.
- Transaksi database menggantung selama 4–7 detik akibat pemanggilan payment gateway pihak ketiga di dalam satu siklus controller yang sama.
- Event listener database mentrigger antrean HTTP eksternal yang gagal saat transaksi rollback, menyebabkan ketidaksinkronan data pembayaran.

### Solusi Arsitektur Hexagonal Berbasis DDD & Outbox Pattern
1. **Pemisahan Konkurensi melalui Hexagon Boundary:**
   - Logika pemotongan stok dipisahkan ke dalam `InventoryReservationUseCase`.
   - Menggunakan Driven Port `InventoryRepositoryInterface` dengan implementasi Redis Lua Script untuk penahanan kuota cepat atomik (< 2ms), sebelum disinkronkan ke PostgreSQL melalui batch worker.
2. **Penerapan Transactional Outbox Pattern:**
   - Tidak ada lagi API Call ke payment gateway di dalam Use Case mutasi database.
   - Peristiwa `OrderPlacedDomainEvent` ditulis langsung ke tabel `outbox_events` di dalam transaksi database yang sama dengan entitas `Order`.
   - Proses terpisah (*Kafka Debezium CDC Connector* atau *PHP Outbox Poller Worker*) membaca tabel outbox secara asinkron dan menembakkan event ke Apache Kafka.
3. **Hasil Metrik Produksi:**
   - Latensi p99 HTTP turun dari 4.800 ms menjadi **68 ms**.
   - Deadlock database berkurang hingga **0%**.
   - Kehilangan domain event akibat network partition berkurang ke taraf **Zero Data Loss (RPO = 0)**.

---

## 9. Trade-offs

| Dimensi | Keuntungan (+)| Kerugian / Biaya (-) |
| :--- | :--- | :--- |
| **Performance & Latency** | Query SQL dapat dioptimalkan secara atomik per port. Model in-memory ringan tanpa metadata ORM berlebih. | Terjadi overhead pemetaan data (*data hydration*) dua arah: DB -> Adapter -> Domain Entity -> DTO -> Response. Membutuhkan alokasi memori tambahan ~5-12%. |
| **Complexity & File Count**| *Cognitive load* per file rendah; berkas terfokus tunggal (*Single Responsibility*). | Jumlah berkas meningkat 3x hingga 4x lipat dibanding Active Record standar. Memerlukan abstraksi interface untuk hampir semua interaksi I/O. |
| **Scalability (Team & Code)**| Memungkinkan puluhan engineer mengedit adapter berbeda tanpa menimbulkan merge conflict pada core business logic. | Kurva belajar tim tergolong terjal. Engineer junior rentan salah menaruh logika bisnis ke dalam Adapter atau sebaliknya. |
| **Maintenance Cost** | Jangka panjang sangat murah. Framework/library PHP dapat di-upgrade atau di-swap kapan saja tanpa risiko kerusakan sistem core. | Biaya investasi awal (TCO tahap inisiasi) tinggi. Waktu perilisan MVP (Time-to-Market) lebih lambat dibanding scaffolding monolit konvensional. |

---

## 10. Common Mistakes & Troubleshooting

### A. Leaking Entities to the Outer World (Leaky Ports)
- **Gejala Buruk:** Web Controller mengembalikan Domain Entity langsung ke view/serializer:
  ```php
  // FATAL: Domain Entity bocor ke luar
  return json_encode($ledgerAccount);
  ```
- **Bahaya:** Jika struktur internal Entity berubah (enkapsulasi), schema API JSON publik rusak seketika. Serializer dapat menyebabkan loop tak terbatas jika terdapat relasi sirkular, atau membocorkan data sensitif.
- **Solusi:** Selalu petakan output Domain ke dalam Application Output DTO atau Response Model sebelum dikirim ke Driving Adapter.

### B. Meneruskan Konsep Infrastruktur ke Domain Port
- **Gejala Buruk:** Mendefinisikan port repository dengan tipe data milik library pihak ketiga:
  ```php
  // FATAL: Leaky Infrastructure Port
  interface AccountRepositoryInterface {
      public function findByCriteria(Doctrine\Common\Collections\Criteria $criteria): mixed;
  }
  ```
- **Solusi:** Port harus didefinisikan menggunakan tipe data native PHP murni atau Domain Value Objects:
  ```php
  interface AccountRepositoryInterface {
      public function findBySpecification(AccountSpecificationInterface $spec): AccountCollection;
  }
  ```

### C. Anemic Domain Model Berlindung di Balik Arsitektur Hexagonal
- **Gejala Buruk:** Semua logika bisnis ditaruh di dalam Use Case (Interactor), sementara Entity hanya berisi Getter dan Setter kosong. Ini adalah anti-pattern prosedural (*Transaction Script*) yang dibungkus folder Hexagonal.
- **Solusi:** Pindahkan semua aturan validasi invarian ke dalam Aggregate Root dan Value Objects. Use Case hanya bertugas sebagai orkestrator (koordinator alur kerja).

---

## 11. Best Practices (Production Checklist)

- [ ] **Enforce Architectural Fitness Functions (Deptrac):** Pasang `qossmic/deptrac` di pipa CI/CD untuk menggagalkan build otomatis jika layer Domain memanggil layer Infrastructure atau Application.
- [ ] **Domain Entity Pure Invariants:** Pastikan seluruh Entity tidak memiliki method `setXxx()` publik sembarangan. Gunakan method berorientasi perilaku bisnis seperti `suspend()`, `applyDiscount()`, atau `reconcile()`.
- [ ] **Static Analysis Level 8+:** Gunakan PHPStan pada level tertinggi tanpa error baseline pada layer Domain dan Application.
- [ ] **In-Memory Fake Adapters:** Sediakan implementasi Fake berbasis array in-memory untuk setiap driven port repository guna mempercepat eksekusi Unit Test tanpa container database.
- [ ] **Transactional Outbox Strategy:** Jangan pernah memanggil external REST API / Message Broker di dalam satu transaksi database lokal bersama penulisan Aggregate. Tulis ke tabel outbox terlebih dahulu.
- [ ] **Identity Generation di Domain:** Gunakan UUID v7 (time-ordered) yang digenerate oleh Domain/Application layer, bukan Auto-Increment Sequence bawaan database, agar identitas aggregate sudah valid sebelum operasi persistensi terjadi.

---

## 12. Hands-on Practice

Langkah praktikum terstruktur untuk disimpan di repositori lokal `hands-on/m02/`.

### Langkah 1: Inisialisasi Proyek dan Setup Deptrac
Jalankan di terminal Anda:
```bash
mkdir -p hands-on/m02/src/{Domain,Application,Infrastructure}
mkdir -p hands-on/m02/tests
cd hands-on/m02
composer init --no-interaction
composer require --dev phpstan/phpstan qossmic/deptrac-shim phpunit/phpunit
```

Perbarui konfigurasi `composer.json` untuk namespace PSR-4:
```json
{
  "autoload": {
    "psr-4": {
      "Enterprise\\": "src/"
    }
  },
  "autoload-dev": {
    "psr-4": {
      "Enterprise\\Tests\\": "tests/"
    }
  }
}
```
Jalankan: `composer dump-autoload`

### Langkah 2: Buat Aturan Boundary (deptrac.yaml)
Simpan file ini di `hands-on/m02/deptrac.yaml`:
```yaml
deptrac:
  paths:
    - ./src
  layers:
    - name: Domain
      collectors:
        - type: directory
          value: src/Domain/.*
    - name: Application
      collectors:
        - type: directory
          value: src/Application/.*
    - name: Infrastructure
      collectors:
        - type: directory
          value: src/Infrastructure/.*
  ruleset:
    Domain: ~ # Domain TIDAK BOLEH bergantung pada layer manapun
    Application:
      - Domain
    Infrastructure:
      - Domain
      - Application
```

### Langkah 3: Eksekusi Pengecekan Integritas Arsitektur
Ciptakan pelanggaran sengaja (misalnya mengimpor kelas dari `Infrastructure` ke dalam file di `Domain`), lalu eksekusi:
```bash
./vendor/bin/deptrac analyze --config-file=deptrac.yaml
```
Pastikan Deptrac mendeteksi error pelanggaran ketergantungan tersebut secara presisi.

---

## 13. Exercise

### Level Easy
Buat sebuah Value Object `EmailAddress` di dalam `Domain\Model` yang:
1. Memvalidasi sintaks email menggunakan `filter_var`.
2. Menerapkan lowercase normalisasi otomatis pada konstruktor.
3. Bersifat immutable (`final readonly class`).
4. Lempar `InvalidEmailDomainException` jika format salah.

### Level Medium
Rancang Use Case `RegisterUserUseCase`:
1. Buat Driving Port `RegisterUserCommand` dan `RegisterUserUseCaseInterface`.
2. Buat Driven Port `UserRepositoryInterface` (hanya interface method: `existsByEmail(EmailAddress $email): bool` dan `save(User $user): void`).
3. Buat implementasi interactor yang memvalidasi keunikan email sebelum aggregate `User` diinstansiasi.
4. Buat unit test murni menggunakan **In-Memory Fake Repository** (tanpa mocking library seperti Mockery/Prophecy).

### Level Hard
Implementasikan **Transactional Outbox Worker**:
1. Buat Driving Adapter CLI Command (menggunakan script PHP native atau Symfony Console).
2. Adapter ini memanggil Driven Port `OutboxRepositoryInterface::fetchUnprocessed(int $batchSize): array`.
3. Gunakan loop dengan kontrol graceful shutdown (`pcntl_signal` untuk penanganan `SIGTERM`/`SIGINT`).
4. Tandai record outbox sebagai `PROCESSED` atau `FAILED` dengan mekanisme penambahan delay eksponensial (*exponential backoff retry*).

---

## 14. Challenge

### Studi Kasus: Sistem Settlement Multi-Mata Uang Terdistribusi
Sebuah platform remitansi global membutuhkan sistem *Clearing & Settlement* yang mematuhi Clean Architecture murni dengan tantangan berikut:

**Skenario Masalah:**
1. Mutasi transaksi melibatkan multi-party: Pengirim, Platform Escrow, dan Bank Penerima Lokal.
2. Nilai tukar valas (*Exchange Rate*) berfluktuasi secara real-time dan harus dikunci (*locked*) menggunakan *Rate Guarantee Token* yang valid selama tepat 60 detik.
3. Database PostgreSQL utama mengalami beban baca masif dari dashboard operasional, sehingga skema penulisan (*Command*) harus dipisahkan dari skema pembacaan (*Query*) menggunakan prinsip CQRS di layer port/adapter.

**Tugas Anda:**
1. Desain diagram arsitektur teks/ASCII yang memetakan:
   - Driving Adapters (Webhook Provider Valas, REST Client).
   - Core Domain Boundaries (ExchangeRate Engine, Ledger Aggregate).
   - Driven Adapters (PostgreSQL Write DB, Read Replica / Elasticsearch Read DB, Redis Rate Lock).
2. Tuliskan kode implementasi Aggregate Root `RemittanceOrder` beserta validasi transisi state-nya (`DRAFT` -> `RATE_LOCKED` -> `FUNDS_DEPOSITED` -> `SETTLED` / `EXPIRED`).
3. Tunjukkan implementasi Driven Port untuk penguncian kurs yang mengisolasi Redis tanpa membocorkan tipe data `Predis` atau `Redis` ke dalam Application Layer.
4. Buat file `deptrac.yaml` komprehensif yang menjamin layer CQRS (Write Model vs Read Model) tidak saling mencemari.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic (Pilihan Ganda & Konseptual)

1. **Apa perbedaan esensial antara Driving Port dan Driven Port dalam Hexagonal Architecture?**
   - A. Driving Port adalah abstract class, Driven Port adalah interface.
   - B. Driving Port menentukan bagaimana aplikasi dipicu dari luar; Driven Port menentukan bagaimana aplikasi berkomunikasi dengan infrastruktur luar.
   - C. Driving Port berjalan di CLI, Driven Port berjalan di Web.
   - D. Driving Port selalu synchronous, Driven Port selalu asynchronous.
   *Kunci: B. Driving (Inbound) dipanggil oleh driving adapters (misal Controller); Driven (Outbound) diimplementasikan oleh driven adapters (misal DB Repo).*

2. **Mengapa Domain Entity tidak boleh mengimplementasikan interface `JsonSerializable` bawaan PHP?**
   - A. Karena PHP tidak mendukung serialisasi readonly properties.
   - B. Karena hal tersebut mengaitkan representasi presentasi JSON eksternal langsung ke dalam model domain bisnis internal, merusak pemisahan tanggung jawab.
   - C. Karena interface tersebut menurunkan performa eksekusi OPcache.
   - D. Karena Domain Entity hanya boleh dieksekusi di background worker.
   *Kunci: B. Domain Entity hanya bertugas menjaga state invariant dan aturan bisnis, bukan memikirkan serialization contract untuk API clients.*

3. **Di layer manakah interface `UserRepositoryInterface` harus didefinisikan?**
   - A. `Infrastructure\Persistence\Doctrine`
   - B. `Driving\Http\Controller`
   - C. `Domain` atau `Application`
   - D. `Vendor\SharedKernel`
   *Kunci: C. Sesuai Dependency Inversion Principle, kontrak interface dimiliki oleh konsumen logika bisnis di Domain/Application, bukan oleh penyedia infrastruktur.*

4. **Karakteristik utama dari sebuah Value Object adalah:**
   - A. Memiliki Primary Key auto-increment di database.
   - B. Bersifat mutable dan memiliki setter eksplisit.
   - C. Bersifat immutable dan kesetaraannya ditentukan oleh nilai atributnya, bukan oleh ID konseptual.
   - D. Harus berupa class yang ditandai dengan attribute ORM.
   *Kunci: C. Value Object tidak memiliki identitas unik; dua VO dianggap identik jika seluruh nilainya sama.*

5. **Apa fungsi utama dari Transactional Outbox Pattern?**
   - A. Mempercepat eksekusi query `SELECT` database.
   - B. Menjamin bahwa penulisan mutasi domain aggregate dan pencatatan event pesan terjadi secara atomik dalam satu transaksi database lokal.
   - C. Menggantikan kebutuhan message broker seperti Kafka atau RabbitMQ.
   - D. Menyimpan log file server langsung ke S3.
   *Kunci: B. Mencegah kondisi split-brain di mana data tersimpan di DB namun event gagal terkirim ke broker karena crash.*

---

### Bagian B: Intermediate (Analisis Arsitektur)

6. **Perhatikan potongan kode berikut:**
   ```php
   namespace Enterprise\Billing\Domain\Model;
   
   class Invoice {
       public function calculateTotal(Symfony\Component\HttpFoundation\Request $request): void {
           // ...
       }
   }
   ```
   **Apa kesalahan arsitektural fatal pada kode di atas?**
   - A. Penggunaan nama method kalkulasi tidak mengikuti standar PSR-12.
   - B. Layer Domain bocor karena mengimpor kelas komponen HTTP framework (`HttpFoundation\Request`).
   - C. Method kalkulasi tidak mengembalikan nilai integer.
   - D. Tidak ada kesalahan, ini adalah praktik standar controller binding.
   *Kunci: B. Pelanggaran keras Dependency Rule. Domain terkontaminasi oleh HTTP request delivery mechanism.*

7. **Bagaimana cara menangani transaksi database (Begin/Commit/Rollback) tanpa memasukkan syntax database ke dalam Use Case?**
   - A. Mengeksekusi query `BEGIN TRANSACTION` via raw SQL string di dalam Entity.
   - B. Menggunakan abstraksi Driven Port seperti `TransactionManagerInterface` yang membungkus callable block di dalam interactor.
   - C. Menyerahkan seluruh transaksi kepada webserver Nginx.
   - D. Transaksi database tidak diperlukan jika sudah menggunakan Clean Architecture.
   *Kunci: B. Port memfasilitasi kebutuhan transaksi sementara Adapter yang menentukan teknologi spesifiknya (PDO, Doctrine, MySQLi).*

8. **Mengapa Aggregate Root harus menjadi satu-satunya gerbang akses untuk memutasi child entities di dalamnya?**
   - A. Untuk menghemat memori PHP execution thread.
   - B. Untuk memastikan seluruh aturan bisnis dan invarian konsistensi transaksi data di dalam boundary aggregate selalu terpenuhi secara utuh.
   - C. Agar migration database dapat digenerate secara otomatis.
   - D. Karena PHP tidak mendukung multi-threading.
   *Kunci: B. Aggregate Root bertanggung jawab penuh melindungi konsistensi internal semua entitas di bawah naungannya.*

9. **Apa keuntungan arsitektural penggunaan Unit Testing pada Use Case yang menerapkan Ports and Adapters murni dibandingkan end-to-end integration testing?**
   - A. Membutuhkan runtime database aktif seperti Docker PostgreSQL.
   - B. Eksekusi berjalan murni di memori (CPU-bound) menggunakan Test Double / Fake Repository, menghasilkan kecepatan ratusan test per detik tanpa I/O bottleneck.
   - C. Tidak memerlukan framework testing seperti PHPUnit.
   - D. Menguji validitas sintaks network switch dan load balancer.
   *Kunci: B. Tes domain murni terbebas dari latensi I/O disk maupun network.*

10. **Kapan sebuah logika validasi harus ditempatkan di Controller (Driving Adapter) dan kapan harus di Domain Entity?**
    - A. Validasi format/sintaks (misal: "apakah payload berupa JSON valid dan field bertipe string") di Controller; Validasi aturan bisnis/invarian (misal: "saldo tidak boleh negatif setelah transfer") di Domain Entity.
    - B. Seluruh validasi harus selalu berada di Controller.
    - C. Seluruh validasi harus selalu berada di database stored procedure.
    - D. Validasi sintaks di Domain, validasi bisnis di Controller.
    *Kunci: A. Pemisahan tanggung jawab: Input validation vs Business rule enforcement.*

---

### Bagian C: Skenario Kasus Produksi (Senior Architectural Analysis)

11. **Skenario Kasus 1:**
    Sebuah tim engineer memigrasikan sistem monolit legacy ke Hexagonal Architecture. Mereka membuat Driving Port `GetProductQueryInterface` dan mengimplementasikannya di Application layer. Namun, di dalam Driving Adapter (Controller), mereka membutuhkan pagination metadata dan relasi dinamis yang kompleks untuk kebutuhan GraphQL. Engineer junior menyarankan untuk mengembalikan query builder Doctrine langsung dari Driven Port Repository ke Controller agar controller bisa menambah klausa `where` dan `paginate` secara fleksibel.
    
    **Evaluasi tindakan ini dari sudut pandang arsitektur enterprise dan berikan solusi yang tepat!**
    - *Jawaban Analitis yang Diharapkan:*
      Tindakan tersebut adalah **Anti-Pattern Leaky Abstraction fatal**. Mengembalikan Query Builder dari Driven Port ke Controller menghancurkan batas isolasi arsitektur; Controller kini terikat erat dengan implementasi ORM Doctrine, dan Use Case dilewati begitu saja. Jika skema database diubah, Controller akan langsung rusak.
      **Solusi:** Terapkan pemisahan CQRS. Untuk kebutuhan query kompleks/GraphQL, buat jalur khusus *Read Model Port* yang menerima Value Object kriteria pencarian (`SearchCriteriaDTO(page: 1, limit: 20, filters: [...])`) dan mengembalikan representasi Read-only DTO murni (`PaginatedProductResponseDTO`), bukan Active Record/ORM Query Builder.

12. **Skenario Kasus 2:**
    Pada event Black Friday, sistem checkout berbasis Hexagonal mengalami lonjakan error HTTP 500. Analisis log menunjukkan Use Case `ProcessOrderUseCase` memanggil Driven Port `PaymentGatewayPort`. Driven adapter payment menggunakan Guzzle HTTP client ke vendor luar. Saat vendor luar mengalami latency spike hingga 15 detik, worker pool PHP-FPM habis terpakai (*thread exhaustion*), menyebabkan server down total untuk seluruh user.
    
    **Bagaimana Anda merestrukturisasi port, adapter, dan interaksi interactor tersebut untuk melindungi sistem secara keseluruhan?**
    - *Jawaban Analitis yang Diharapkan:*
      Masalah ini diakibatkan oleh interaksi I/O eksternal blocking di dalam alur sinkron transaksi checkout.
      **Solusi Restrukturisasi:**
      1. Terapkan pola *Asynchronous Processing*: Ubah Use Case `ProcessOrderUseCase` untuk hanya memvalidasi order, mengurangi alokasi inventaris, menyimpan pesanan berstatus `PENDING_PAYMENT`, dan mencatat `OrderPlacedEvent` ke Outbox Table secara atomik lokal (< 10ms).
      2. Pindahkan eksekusi `PaymentGatewayPort` ke background queue worker independen yang mengonsumsi event outbox tersebut.
      3. Pasang *Circuit Breaker Pattern* pada adapter HTTP payment gateway untuk memutus panggilan seketika (fail-fast) jika tingkat kegagalan vendor pihak ketiga melampaui ambang batas tertentu.

13. **Skenario Kasus 3:**
    Sistem Anda menggunakan framework Symfony untuk dependency injection container. Anda ingin memastikan bahwa kode di dalam `src/Domain` 100% agnostik framework dan tidak dapat mengakses container Symfony, sementara kelas-kelas Use Case di `src/Application` tetap dapat di-wire secara otomatis (*autowiring*). Di sisi lain, Anda memiliki entitas domain yang membutuhkan perhitungan pajak rumit yang rumusnya diperbarui setiap hari melalui microservice perpajakan eksternal.
    
    **Bagaimana arsitektur Anda memfasilitasi kebutuhan Domain tersebut tanpa melanggar Dependency Inversion Principle?**
    - *Jawaban Analitis yang Diharapkan:*
      1. Domain Core tidak boleh memanggil microservice eksternal secara langsung, dan tidak boleh mengambil service dari DI container Symfony.
      2. Buat sebuah Driven Port di dalam Domain layer: `interface TaxCalculatorInterface { public function calculateTax(Money $baseAmount, TaxZone $zone): Money; }`.
      3. Di layer Infrastructure (`src/Infrastructure/Adapter/Driven/ExternalService`), implementasikan interface tersebut: `final class RemoteApiTaxCalculator implements TaxCalculatorInterface` yang memanggil HTTP microservice pajak.
      4. Jika formula pajak murni matematis, rumus tersebut dijalankan sebagai Domain Service. Jika harus bergantung pada I/O luar, Use Case bertugas mengambil data via Driven Port tersebut, lalu menyerahkan nilainya ke Domain Entity murni sebagai argumen pemanggilan method: `$order->applyTax($calculatedTax)`.
      5. Konfigurasi `services.yaml` Symfony hanya memetakan interface port ke adapter implementor di file konfigurasi tanpa meletakkan anotasi/atribut framework apa pun di dalam source code Domain.

---

## 16. Summary

1. **Inti Hexagonal & Clean Architecture** bukanlah tentang penamaan folder yang rumit, melainkan penegakan mutlak **The Dependency Rule**: domain bisnis berada di pusat semesta aplikasi, steril dari detail teknologi seperti database, framework HTTP, queue worker, dan library pihak ketiga.
2. **Ports adalah Kontrak (Interfaces):** Driving Ports mendefinisikan batas kemampuan aplikasi yang dapat diminta oleh pengguna atau sistem lain. Driven Ports mendefinisikan apa yang dibutuhkan domain dari dunia luar untuk menyelesaikan tugasnya.
3. **Adapters adalah Penerjemah Teknis:** Adapter bertugas mengubah sinyal-sinyal lingkungan spesifik (HTTP Request, SQL Result Set, AMQP Messages, Cloud Storage API) menjadi struktur data native yang dimengerti oleh core aplikasi.
4. **Proteksi Mutlak Invariant:** Bisnis yang kuat dibangun di atas Aggregate Root dan Value Objects yang memvalidasi integritas dirinya sendiri secara mandiri. Jangan biarkan data invalid lahir atau tersimpan ke dalam domain model.
5. **Tooling sebagai Penjaga Batas:** Jangan mengandalkan disiplin manusia semata untuk menjaga batas arsitektur enterprise. Gunakan automated architectural fitness functions seperti **Deptrac** dan static analysis **PHPStan Level 8+** di dalam continuous integration pipeline untuk mendeteksi pelanggaran arsitektur sejak dini.