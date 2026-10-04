# SEKSI 01 — IDENTITAS MODUL

| Parameter | Spesifikasi |
| :--- | :--- |
| **Modul ID** | `LANG-PHP-08-01` |
| **Kategori** | `02-Programming-Languages` |
| **Mata Kuliah / Jalur** | `Modern PHP Software Engineering` |
| **Bab / Modul** | `Bab 08: Software Architecture & Enterprise Patterns / Modul 01` |
| **Judul Modul** | Arsitektur Perangkat Lunak: Hexagonal & Clean Architecture |
| **Tingkat Kesulitan** | Lanjutan (*Advanced*) |
| **Prasyarat Teknis** | Pemahaman mendalam tentang OOP (PHP 8.2+), SOLID Principles, Dependency Injection, Interface Polymorphism, Composer & PSR-4 Autoloading |
| **Alokasi Waktu Belajar** | 6 - 8 Jam Intensif |
| **Target Runtime/Stack** | PHP 8.2 / 8.3 CLI & FPM, Strict Typing Diaktifkan |

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini secara menyeluruh, peserta didik diharapkan mampu:

1. **Mendekomposisi Sistem Kompleks (C4 - Analysis)**: Menganalisis batas-batas domain dan memisahkan logika bisnis inti murni (*core domain logic*) dari mekanisme pengiriman (*delivery mechanisms*) dan infrastruktur eksternal.
2. **Merancang Antarmuka Ports & Adapters (C5 - Synthesis)**: Mengembangkan arsitektur Hexagonal murni menggunakan *Primary/Driving Ports* dan *Secondary/Driven Ports* berbasis abstraksi antarmuka (*interfaces*) PHP 8.
3. **Menerapkan Aturan Dependensi Clean Architecture (C3 - Application)**: Mengisolasi dependensi kode sumber agar selalu mengarah ke dalam (*inward-pointing dependency rule*), memastikan lapisan Domain tidak mengimpor namespace Framework, ORM, atau pustaka I/O.
4. **Mengeliminasi *Framework Lock-in* (C6 - Evaluation)**: Menilai dan merefaktor arsitektur *ActiveRecord-heavy* (seperti default Eloquent/Yii) menjadi *Domain-Driven Data Mapper* murni untuk menjamin portabilitas dan kemudahan pengujian unit (*unit testability*).
5. **Membangun Pipeline Pengujian Bebas I/O (C5 - Synthesis)**: Mengimplementasikan sistem pengujian unit otomatis berskala besar yang menguji 100% alur bisnis pada Use Case tanpa menggunakan koneksi database atau jaringan nyata.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Analogi Papan Induk Komputer (*Motherboard Analogy*)

Bayangkan sebuah *Motherboard* komputer modern. 
* Motherboard memiliki CPU dan sirkuit pemrosesan inti (ini adalah **Domain & Logic Bisnis** Anda).
* Motherboard tidak peduli apakah monitor Anda bermerek Dell atau Samsung, terhubung melalui HDMI, DisplayPort, atau VGA. Motherboard hanya menyediakan *port* standar (misal: antarmuka bus PCIe/display output).
* Motherboard juga tidak peduli apakah data disimpan di NVMe SSD, SATA HDD, atau Flashdisk USB. Motherboard hanya berbicara melalui antarmuka penyimpanan standar.

**Arsitektur Tradisional (Layered/MVC Klasik):**
Seperti menyolder kabel monitor HDMI dan kabel harddisk langsung ke sirkuit CPU. Jika standar kabel berubah atau monitor rusak, Anda harus membongkar seluruh CPU. Ini adalah analogi saat Entity aplikasi Anda mewarisi `Model` bawaan framework yang terikat langsung ke driver database MySQL PDO.

**Arsitektur Hexagonal & Clean:**
CPU hanya mengekspos soket (*Ports*). Vendor periferal eksternal wajib membuat colokan yang sesuai dengan soket tersebut (*Adapters*).

```
[ Framework / Database / UI ]  ---> Bergantung Pada --->  [ Domain Abstraction ]
               (Adapter)                                       (Port)
```

### Hukum Inti: The Dependency Rule
> *Ketergantungan kode sumber (source code dependencies) HANYA BOLEH menunjuk ke arah dalam, menuju kebijakan tingkat tinggi (High-level Policies / Core Business).*

Tidak ada elemen di dalam lingkaran dalam (Entities, Use Cases) yang boleh mengetahui apa pun tentang elemen di lingkaran luar (Framework, Database, HTTP Request/Response, CLI, Third-party SDKs).

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram Arsitektur Hexagonal (Ports & Adapters)

```
       +-----------------------------------------------------------------------+
       |                        INFRASTRUCTURE LAYER                           |
       |                                                                       |
       |   [ Driving / Primary Adapters ]                                      |
       |   +--------------------------+                                        |
       |   | - Web Controller (HTTP)  |                                        |
       |   | - Console Command (CLI)  |----+                                   |
       |   | - Queue Consumer (AMQP)  |    |                                   |
       |   +--------------------------+    | (Calls)                           |
       |                                   v                                   |
       |       +-------------------------------------------------------+       |
       |       |                   APPLICATION LAYER                   |       |
       |       |                                                       |       |
       |       |      +-----------------------------------------+      |       |
       |       |      |     Driving Ports (Use Case Interfaces) |      |       |
       |       |      +-----------------------------------------+      |       |
       |       |                           ^                           |       |
       |       |                           | (Implements)              |       |
       |       |      +-----------------------------------------+      |       |
       |       |      |        Use Case Interactors             |      |       |
       |       |      +-----------------------------------------+      |       |
       |       |                           |                           |       |
       |       |              +------------+------------+              |       |
       |       |              | (Uses)                  | (Invokes)    |       |
       |       |              v                         v              |       |
       |       |   +--------------------+     +---------------------+  |       |
       |       |   |    DOMAIN LAYER    |     | Driven Ports        |  |       |
       |       |   |                    |     | (SPI / Interfaces)  |  |       |
       |       |   | - Pure Entities    |     +---------------------+  |       |
       |       |   | - Value Objects    |                ^             |       |
       |       |   | - Domain Services  |                |             |       |
       |       |   | - Domain Events    |                | (Implements)|       |
       |       |   +--------------------+                |             |       |
       |       +-----------------------------------------|-------------+       |
       |                                                 |                     |
       |   [ Driven / Secondary Adapters ]               |                     |
       |   +---------------------------------------------+---------+           |
       |   | - Doctrine / PDO Repository (Database)                |           |
       |   | - Stripe / Xendit Gateway (Payment)                   |           |
       |   | - SmtpMailer / SesMailer (Email)                      |           |
       |   +-------------------------------------------------------+           |
       +-----------------------------------------------------------------------+
```

### Alur Eksekusi Data vs Alur Dependensi (*Inversion of Control*)

```
[HTTP Request]
     |
     v
[Primary Adapter: OrderController]
     |
     | invokes UseCaseInterface
     v
[Use Case Interactor: CreateOrderUseCase] -------------> [Domain Entity: Order]
     |                                             (Mutates & Applies Invariants)
     | invokes DrivenPortInterface
     v
[Driven Port Interface: OrderRepositoryPort]
     ^
     | implements
[Secondary Adapter: PdoOrderRepository]
     |
     v
[Physical Database / Engine]
```

*Perhatikan bahwa panah ketergantungan dibalik:* `OrderRepositoryPort` didefinisikan di dalam Application/Domain layer, sedangkan `PdoOrderRepository` yang mengimplementasikannya berada di luar (Infrastructure layer).

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

Pemisahan tanggung jawab dipecah ke dalam empat lapisan batas tegas:

| Lapisan (*Layer*) | Komponen Utama | Karakteristik Ketergantungan | Aturan Mutlak |
| :--- | :--- | :--- | :--- |
| **Domain** | Entities, Value Objects, Domain Events, Domain Exceptions | **Zero Dependencies**. Tidak mengimpor pustaka eksternal apapun kecuali PHP Standard Library (SPL). | Tidak boleh ada anotasi ORM (seperti `#[ORM\Entity]`), tidak ada turunan dari base class framework. |
| **Application** | Use Cases / Interactors, DTOs (Data Transfer Objects), Driving Ports, Driven Ports | Hanya bergantung pada **Domain Layer**. | Tidak boleh mengeksekusi query database mentah, tidak boleh menangani objek HTTP Request/Response (PSR-7, Symphony Request). |
| **Adapters (In/Out)** | Controller, Presenter, CLI Command, Repository Implementation, Mailer Service, Payment Adapter | Bergantung pada **Application** dan **Domain**. Mengubah format data eksternal ke format internal (dan sebaliknya). | Berisi logika konversi (*mapping*). Semua implementasi interface I/O ditempatkan di sini. |
| **Infrastructure / Config**| DI Container (`PHP-DI`, `Symfony DI`), Framework Kernel, Routing, Migrasi DB | Bergantung pada **Semua Lapisan**. Mengawinkan abstraksi dan implementasi konkret. | Tempat berkumpulnya *side-effects* teknis dan bootstrap konfigurasi sistem. |

### Mekanisme Pengiriman Data Antar Lapisan

1. **Request Boundaries**: Data mentah dari HTTP Request (JSON payload) diserialisasi menjadi **Request DTO** murni pada Primary Adapter sebelum dikirim ke Use Case.
2. **Use Case Execution**: Use Case memvalidasi hak akses dan alur kerja aplikasi, memanggil Domain Model untuk eksekusi logika aturan bisnis murni (*business invariants*).
3. **Infrastructure Boundary Crossing**: Ketika Use Case perlu persistensi data, Use Case memanggil Driven Port (Interface). 
4. **Data Hydration/Dehydration**: Secondary Adapter mengambil data dari Domain Entity, mengubahnya (*dehydrate*) menjadi representasi tabel relasional / dokumen BSON, dan menyimpannya. Saat membaca, Adapter merekonstruksi (*hydrate*) entitas murni dari baris database.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Hexagonal Architecture (Alistair Cockburn, 2005)
Arsitektur Hexagonal, dikenal sebagai *Ports and Adapters*, melihat sistem sebagai kesatuan komputasi yang terisolasi dari dunia luar. "Hexagon" hanyalah representasi visual grafis untuk menunjukkan banyak batas koneksi (*ports*), bukan berarti sistem memiliki 6 sisi.
* **Driving Side (Kiri/Atas)**: Aktor yang menginisiasi interaksi ke aplikasi (Pengguna, Scheduler CRON, Message Bus Consumer).
* **Driven Side (Kanan/Bawah)**: Aktor yang diinisiasi oleh aplikasi (Database, Pihak Ketiga, Message Queue Producer, Cache Storage).

### 2. Clean Architecture (Robert C. Martin / Uncle Bob, 2012)
Clean Architecture mengintegrasikan Hexagonal Architecture, Onion Architecture (Jeffrey Palermo), dan Screaming Architecture ke dalam konsensus formal. Clean Architecture memperkenalkan pemisahan eksplisit antara:
* **Enterprise Business Rules (Entities)**: Logika yang tidak berubah meskipun aplikasi dipindahkan dari web ke terminal desktop atau dipecah menjadi microservices.
* **Application Business Rules (Use Cases)**: Alur automasi sistem tertentu yang mengarahkan entitas untuk mencapai tujuan bisnis spesifik.

### 3. Dependency Inversion Principle (DIP) dalam Arsitektur
DIP menyatakan:
1. Modul tingkat tinggi (*High-level modules*) tidak boleh bergantung pada modul tingkat rendah (*Low-level modules*). Keduanya harus bergantung pada abstraksi.
2. Abstraksi tidak boleh bergantung pada detail. Detail harus bergantung pada abstraksi.

Dalam konteks arsitektur PHP:
* Modul Tingkat Tinggi = `RegisterUserUseCase` (Application)
* Modul Tingkat Rendah = `MySqlUserRepository` (Infrastructure)
* Abstraksi = `UserRepositoryInterface` (Application/Domain Port)

### 4. Mengapa Active Record Menghancurkan Clean Architecture?
Pola Active Record (seperti Laravel Eloquent) menyatukan dua tanggung jawab berbeda (*Single Responsibility Principle Violation*):
1. **Aturan Bisnis & State** (Pengecekan kredit saldo, aturan diskon).
2. **Operasi I/O Database** (`save()`, `delete()`, `belongsTo()`).

Ketika Domain Model Anda mewarisi `Illuminate\Database\Eloquent\Model`, Domain Anda secara permanen terkontaminasi oleh koneksi database runtime, dependensi framework, dan skema tabel relational database (RDBMS). Jika ingin berpindah penyimpanan ke DynamoDB, atau sekadar menulis *Unit Test* instan tanpa koneksi database SQLite in-memory yang lambat, Anda akan terhalang secara teknis.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah demonstrasi fundamental pemisahan entitas domain, port, use case, dan adapter untuk skenario **Pembukaan Rekening Tabungan Baru**.

### 1. Domain Layer: Entity & Value Object (PHP 8.2+)

```php
<?php

declare(strict_types=1);

namespace Architecture\Domain\Account;

use DateTimeImmutable;
use InvalidArgumentException;

// Value Object: Email
final readonly class Email
{
    public string $value;

    public function __construct(string $email)
    {
        if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
            throw new InvalidArgumentException("Format email tidak valid: {$email}");
        }
        $this->value = strtolower(trim($email));
    }
}

// Value Object: Money (Mencegah floating point inaccuracies)
final readonly class Money
{
    public function __construct(
        public int $amountInCents,
        public string $currency = 'IDR'
    ) {
        if ($this->amountInCents < 0) {
            throw new InvalidArgumentException("Jumlah uang tidak boleh bernilai negatif.");
        }
    }

    public function add(Money $other): self
    {
        if ($this->currency !== $other->currency) {
            throw new InvalidArgumentException("Mata uang tidak cocok.");
        }
        return new self($this->amountInCents + $other->amountInCents, $this->currency);
    }
}

// Pure Domain Entity
final class Account
{
    public function __construct(
        private readonly string $accountId,
        private readonly Email $ownerEmail,
        private Money $balance,
        private readonly DateTimeImmutable $createdAt
    ) {}

    public static function open(string $accountId, Email $ownerEmail, Money $initialDeposit): self
    {
        if ($initialDeposit->amountInCents < 50_000_00) { // Rp 50.000,00 minimal deposit
            throw new InvalidArgumentException("Setoran awal minimal adalah Rp 50.000.");
        }

        return new self(
            $accountId,
            $ownerEmail,
            $initialDeposit,
            new DateTimeImmutable()
        );
    }

    public function deposit(Money $amount): void
    {
        $this->balance = $this->balance->add($amount);
    }

    public function getAccountId(): string { return $this->accountId; }
    public function getOwnerEmail(): Email { return $this->ownerEmail; }
    public function getBalance(): Money { return $this->balance; }
    public function getCreatedAt(): DateTimeImmutable { return $this->createdAt; }
}
```

### 2. Application Layer: Ports & Use Case

```php
<?php

declare(strict_types=1);

namespace Architecture\Application\Account;

use Architecture\Domain\Account\Account;
use Architecture\Domain\Account\Email;
use Architecture\Domain\Account\Money;

// Driven/Secondary Port: Persistence
interface AccountRepositoryInterface
{
    public function save(Account $account): void;
    public function existsByEmail(Email $email): bool;
}

// Driven/Secondary Port: Identifier Generator
interface IdGeneratorInterface
{
    public function generate(): string;
}

// Input DTO (Data Transfer Object)
final readonly class OpenAccountCommand
{
    public function __construct(
        public string $email,
        public int $initialDepositInCents
    ) {}
}

// Response DTO
final readonly class OpenAccountResult
{
    public function __construct(
        public string $accountId,
        public string $email,
        public int $balanceInCents
    ) {}
}

// Driving Port: Use Case Interface
interface OpenAccountUseCaseInterface
{
    public function execute(OpenAccountCommand $command): OpenAccountResult;
}

// Use Case Interactor
final readonly class OpenAccountUseCase implements OpenAccountUseCaseInterface
{
    public function __construct(
        private AccountRepositoryInterface $accountRepository,
        private IdGeneratorInterface $idGenerator
    ) {}

    public function execute(OpenAccountCommand $command): OpenAccountResult
    {
        $email = new Email($command->email);

        if ($this->accountRepository->existsByEmail($email)) {
            throw new \DomainException("Akun dengan email ini sudah terdaftar.");
        }

        $deposit = new Money($command->initialDepositInCents, 'IDR');
        $accountId = $this->idGenerator->generate();

        // Eksekusi pure business logic
        $account = Account::open($accountId, $email, $deposit);

        // Simpan via Driven Port
        $this->accountRepository->save($account);

        return new OpenAccountResult(
            $account->getAccountId(),
            $account->getOwnerEmail()->value,
            $account->getBalance()->amountInCents
        );
    }
}
```

### 3. Infrastructure Layer: Adapters

```php
<?php

declare(strict_types=1);

namespace Architecture\Infrastructure\Persistence;

use Architecture\Application\Account\AccountRepositoryInterface;
use Architecture\Domain\Account\Account;
use Architecture\Domain\Account\Email;
use Architecture\Domain\Account\Money;
use PDO;

// Secondary Adapter: PDO Implementation
final readonly class PdoAccountRepository implements AccountRepositoryInterface
{
    public function __construct(private PDO $pdo) {}

    public function save(Account $account): void
    {
        $stmt = $this->pdo->prepare(
            'INSERT INTO accounts (id, email, balance_cents, currency, created_at) 
             VALUES (:id, :email, :balance, :currency, :created_at)
             ON DUPLICATE KEY UPDATE balance_cents = :balance'
        );

        $stmt->execute([
            'id' => $account->getAccountId(),
            'email' => $account->getOwnerEmail()->value,
            'balance' => $account->getBalance()->amountInCents,
            'currency' => $account->getBalance()->currency,
            'created_at' => $account->getCreatedAt()->format('Y-m-d H:i:s'),
        ]);
    }

    public function existsByEmail(Email $email): bool
    {
        $stmt = $this->pdo->prepare('SELECT COUNT(*) FROM accounts WHERE email = :email');
        $stmt->execute(['email' => $email->value]);
        return (int) $stmt->fetchColumn() > 0;
    }
}

namespace Architecture\Infrastructure\Identification;

use Architecture\Application\Account\IdGeneratorInterface;

final readonly class UuidGenerator implements IdGeneratorInterface
{
    public function generate(): string
    {
        // Menggunakan native random_bytes (PHP 7/8) atau ramsey/uuid
        return bin2hex(random_bytes(16));
    }
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis File: `Domain/Account/Account.php`

1. **`final class Account`**: Dideklarasikan `final` untuk mencegah *subclassing* yang tidak terkontrol. Desain domain lebih baik diubah via komposisi ketimbang *inheritance*.
2. **`private readonly string $accountId`**: PHP 8.1+ `readonly` memastikan identitas entitas (*identity integrity*) bersifat imutabel setelah instansiasi.
3. **`public static function open(...)`**: Pola *Named Constructor* (Factory Method). Mengabadikan istilah Ubiquitous Domain Language ("open an account" alih-alih generic `new Account()`).
4. **`if ($initialDeposit->amountInCents < 50_000_00)`**: Validasi *Invariants* bisnis mutlak. Tidak peduli pemanggilnya dari Web Controller, CLI, atau Seeder DB, aturan "Deposit minimal 50 ribu" tidak bisa dilewati.

### Analisis File: `Application/Account/OpenAccountUseCase.php`

1. **`interface AccountRepositoryInterface`**: Ini adalah **Driven Port**. Ditempatkan di Application namespace. Use Case hanya tahu antarmuka ini, ia sama sekali tidak peduli ada kata `PDO`, `MySQL`, atau `Redis` di dunia nyata.
2. **`OpenAccountCommand` & `OpenAccountResult`**: DTO terisolasi. Kita tidak pernah mengalirkan variabel global `$_POST` atau objek framework `Request` ke dalam Use Case. Ini menjaga integritas Use Case agar tidak bergantung pada layer web.
3. **`public function execute(...)`**: Use Case bertindak sebagai orkestrator:
   * Mengonversi tipe primitif dari command menjadi domain Value Objects.
   * Melakukan pengecekan konflik (koordinasi repository).
   * Menyerahkan komputasi state kepada Entity (`Account::open`).
   * Melakukan persistensi hasil mutasi via Port.
   * Mengembalikan DTO output.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Enterprise Subscription Billing Engine
Sebuah platform SaaS B2B membutuhkan sistem *Automated Subscription Renewal*.

**Persyaratan Bisnis:**
1. Sistem berjalan via Scheduled Daemon / CLI (Cron).
2. Sistem menagih pelanggan sesuai paket langganan.
3. Pembayaran harus dapat berganti antara Stripe, Xendit, atau Mock Gateway untuk testing.
4. Jika pembayaran berhasil, perpanjang masa aktif akun dan kirim faktur via Email/Webhook.
5. Jika pembayaran gagal, tandai status langganan menjadi `PAST_DUE` dan matikan fitur berbayar tanpa merusak data organisasi.

**Tantangan Arsitektur:**
Logika perpanjangan dan pemotongan saldo harus bebas dari pengaruh jaringan (API eksternal bisa down, timeout, dsb). Framework PHP tidak boleh mengunci alur logika bisnis ini. Pengujian otomatis harus mampu menguji skenario pembayaran gagal secara deterministik dalam hitungan milidetik tanpa memanggil endpoint gateway sungguhan.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Struktur direktori modul:
```text
src/
|-- Core/
|   |-- Domain/
|   |   |-- Model/Subscription.php
|   |   |-- Model/SubscriptionId.php
|   |   |-- Model/SubscriptionStatus.php
|   |-- Application/
|   |   |-- Port/In/RenewSubscriptionUseCaseInterface.php
|   |   |-- Port/Out/SubscriptionRepositoryPort.php
|   |   |-- Port/Out/PaymentGatewayPort.php
|   |   |-- Port/Out/NotificationEventPort.php
|   |   |-- Service/RenewSubscriptionService.php
|   |   |-- DTO/RenewSubscriptionCommand.php
|-- Infrastructure/
|   |-- Adapter/In/Cli/RenewSubscriptionConsoleCommand.php
|   |-- Adapter/Out/Persistence/SqlSubscriptionRepository.php
|   |-- Adapter/Out/Payment/StripePaymentAdapter.php
|   |-- Adapter/Out/Notification/LogNotificationAdapter.php
```

### 1. Domain Layer: Subscription Aggregate

```php
<?php

declare(strict_types=1);

namespace Core\Domain\Model;

use DateTimeImmutable;
use DomainException;

enum SubscriptionStatus: string
{
    case ACTIVE = 'ACTIVE';
    case PAST_DUE = 'PAST_DUE';
    case CANCELED = 'CANCELED';
}

final readonly class SubscriptionId
{
    public function __construct(public string $value)
    {
        if (empty(trim($this->value))) {
            throw new DomainException("Subscription ID tidak boleh kosong.");
        }
    }
}

final class Subscription
{
    public function __construct(
        private readonly SubscriptionId $id,
        private readonly string $customerId,
        private readonly int $renewalAmountInCents,
        private SubscriptionStatus $status,
        private DateTimeImmutable $expiresAt
    ) {}

    public function renewSuccessfully(DateTimeImmutable $now): void
    {
        if ($this->status === SubscriptionStatus::CANCELED) {
            throw new DomainException("Tidak dapat memperpanjang langganan yang sudah dibatalkan.");
        }

        $this->status = SubscriptionStatus::ACTIVE;
        // Tambahkan 1 bulan dari batas kedaluwarsa terakhir, atau sekarang
        $baseDate = ($this->expiresAt > $now) ? $this->expiresAt : $now;
        $this->expiresAt = $baseDate->modify('+1 month');
    }

    public function markAsPaymentFailed(): void
    {
        if ($this->status === SubscriptionStatus::CANCELED) {
            return;
        }
        $this->status = SubscriptionStatus::PAST_DUE;
    }

    public function getId(): SubscriptionId { return $this->id; }
    public function getCustomerId(): string { return $this->customerId; }
    public function getRenewalAmountInCents(): int { return $this->renewalAmountInCents; }
    public function getStatus(): SubscriptionStatus { return $this->status; }
    public function getExpiresAt(): DateTimeImmutable { return $this->expiresAt; }
}
```

### 2. Application Layer: Ports & Use Case Orchestration

```php
<?php

declare(strict_types=1);

namespace Core\Application\Port\Out;

use Core\Domain\Model\Subscription;
use Core\Domain\Model\SubscriptionId;

interface SubscriptionRepositoryPort
{
    public function findById(SubscriptionId $id): ?Subscription;
    public function save(Subscription $subscription): void;
}

interface PaymentGatewayPort
{
    /**
     * @throws \Core\Application\Exception\PaymentFailedException
     */
    public function charge(string $customerId, int $amountInCents, string $idempotencyKey): void;
}

interface NotificationEventPort
{
    public function notifyPaymentFailed(string $customerId, string $reason): void;
    public function notifySubscriptionRenewed(string $customerId, \DateTimeImmutable $newExpiry): void;
}
```

```php
<?php

declare(strict_types=1);

namespace Core\Application\DTO;

final readonly class RenewSubscriptionCommand
{
    public function __construct(public string $subscriptionId) {}
}

final readonly class RenewSubscriptionResponse
{
    public function __construct(
        public string $subscriptionId,
        public bool $success,
        public string $message
    ) {}
}
```

```php
<?php

declare(strict_types=1);

namespace Core\Application\Port\In;

use Core\Application\DTO\RenewSubscriptionCommand;
use Core\Application\DTO\RenewSubscriptionResponse;

interface RenewSubscriptionUseCaseInterface
{
    public function execute(RenewSubscriptionCommand $command): RenewSubscriptionResponse;
}
```

```php
<?php

declare(strict_types=1);

namespace Core\Application\Service;

use Core\Application\Port\In\RenewSubscriptionUseCaseInterface;
use Core\Application\Port\Out\SubscriptionRepositoryPort;
use Core\Application\Port\Out\PaymentGatewayPort;
use Core\Application\Port\Out\NotificationEventPort;
use Core\Application\DTO\RenewSubscriptionCommand;
use Core\Application\DTO\RenewSubscriptionResponse;
use Core\Domain\Model\SubscriptionId;
use DateTimeImmutable;
use Exception;

final readonly class RenewSubscriptionService implements RenewSubscriptionUseCaseInterface
{
    public function __construct(
        private SubscriptionRepositoryPort $repository,
        private PaymentGatewayPort $paymentGateway,
        private NotificationEventPort $notifier
    ) {}

    public function execute(RenewSubscriptionCommand $command): RenewSubscriptionResponse
    {
        $id = new SubscriptionId($command->subscriptionId);
        $subscription = $this->repository->findById($id);

        if (!$subscription) {
            return new RenewSubscriptionResponse($command->subscriptionId, false, "Subscription not found");
        }

        $now = new DateTimeImmutable();
        $idempotencyKey = sprintf("sub_%s_%s", $subscription->getId()->value, $now->format('Ym'));

        try {
            // Eksekusi I/O ke Payment Provider melalui Driven Port
            $this->paymentGateway->charge(
                $subscription->getCustomerId(),
                $subscription->getRenewalAmountInCents(),
                $idempotencyKey
            );

            // Mutasi status domain secara murni
            $subscription->renewSuccessfully($now);

            // Persistensi perubahan
            $this->repository->save($subscription);

            // Notifikasi asinkron/sinkron via Port
            $this->notifier->notifySubscriptionRenewed($subscription->getCustomerId(), $subscription->getExpiresAt());

            return new RenewSubscriptionResponse($subscription->getId()->value, true, "Renewal successful");
        } catch (Exception $e) {
            // Tangani kegagalan: Update model ke status PAST_DUE
            $subscription->markAsPaymentFailed();
            $this->repository->save($subscription);

            $this->notifier->notifyPaymentFailed($subscription->getCustomerId(), $e->getMessage());

            return new RenewSubscriptionResponse(
                $subscription->getId()->value, 
                false, 
                "Payment failed: " . $e->getMessage()
            );
        }
    }
}
```

### 3. Infrastructure Layer: Adapters (In & Out)

```php
<?php

declare(strict_types=1);

namespace Infrastructure\Adapter\Out\Payment;

use Core\Application\Port\Out\PaymentGatewayPort;
use RuntimeException;

final readonly class StripePaymentAdapter implements PaymentGatewayPort
{
    public function __construct(
        private string $apiKey,
        private string $apiUrl = 'https://api.stripe.com/v1'
    ) {}

    public function charge(string $customerId, int $amountInCents, string $idempotencyKey): void
    {
        // Simulasi HTTP Client (Guzzle / cURL murni)
        // Di aplikasi nyata: panggil Stripe SDK client di dalam adapter ini.
        if ($amountInCents > 10_000_000_00) { // Skenario gagal jika di atas 100 juta (contoh simulasi)
            throw new RuntimeException("Kartu kredit ditolak: Saldo tidak mencukupi.");
        }

        // Contoh: Stripe Charge Logic
        // POST $this->apiUrl . '/charges' dengan header Idempotency-Key
    }
}
```

```php
<?php

declare(strict_types=1);

namespace Infrastructure\Adapter\Out\Persistence;

use Core\Application\Port\Out\SubscriptionRepositoryPort;
use Core\Domain\Model\Subscription;
use Core\Domain\Model\SubscriptionId;
use Core\Domain\Model\SubscriptionStatus;
use DateTimeImmutable;
use PDO;

final readonly class SqlSubscriptionRepository implements SubscriptionRepositoryPort
{
    public function __construct(private PDO $connection) {}

    public function findById(SubscriptionId $id): ?Subscription
    {
        $stmt = $this->connection->prepare(
            'SELECT id, customer_id, amount_cents, status, expires_at FROM subscriptions WHERE id = :id'
        );
        $stmt->execute(['id' => $id->value]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);

        if (!$row) {
            return null;
        }

        // Hydration logic: Mengubah raw SQL data menjadi Pure Domain Entity
        return new Subscription(
            new SubscriptionId($row['id']),
            $row['customer_id'],
            (int) $row['amount_cents'],
            SubscriptionStatus::from($row['status']),
            new DateTimeImmutable($row['expires_at'])
        );
    }

    public function save(Subscription $subscription): void
    {
        $stmt = $this->connection->prepare(
            'INSERT INTO subscriptions (id, customer_id, amount_cents, status, expires_at)
             VALUES (:id, :customer_id, :amount, :status, :expires_at)
             ON DUPLICATE KEY UPDATE status = :status, expires_at = :expires_at'
        );

        $stmt->execute([
            'id' => $subscription->getId()->value,
            'customer_id' => $subscription->getCustomerId(),
            'amount' => $subscription->getRenewalAmountInCents(),
            'status' => $subscription->getStatus()->value,
            'expires_at' => $subscription->getExpiresAt()->format('Y-m-d H:i:s'),
        ]);
    }
}
```

```php
<?php

declare(strict_types=1);

namespace Infrastructure\Adapter\In\Cli;

use Core\Application\Port\In\RenewSubscriptionUseCaseInterface;
use Core\Application\DTO\RenewSubscriptionCommand;

// Primary Adapter: CLI Command runner
final readonly class RenewSubscriptionConsoleCommand
{
    public function __construct(
        private RenewSubscriptionUseCaseInterface $useCase
    ) {}

    public function run(array $argv): int
    {
        $subscriptionId = $argv[1] ?? null;

        if (!$subscriptionId) {
            fwrite(STDERR, "Error: Argumen Subscription ID wajib diisi.\n");
            return 1;
        }

        $command = new RenewSubscriptionCommand($subscriptionId);
        $response = $this->useCase->execute($command);

        if ($response->success) {
            fwrite(STDOUT, "SUCCESS: {$response->message} for ID: {$response->subscriptionId}\n");
            return 0;
        }

        fwrite(STDERR, "FAILURE: {$response->message} for ID: {$response->subscriptionId}\n");
        return 1;
    }
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Mengadopsi Hexagonal / Clean Architecture bukanlah keputusan tanpa biaya (*no free lunch*).

### Matriks Perbandingan Arsitektur

| Kriteria / Metrik | Klasik Layered / MVC (ActiveRecord) | Clean / Hexagonal Architecture |
| :--- | :--- | :--- |
| **Kecepatan Awal (Time-to-Market Prototyping)** | **Sangat Tinggi**. Scaffolding cepat bawaan framework (Laravel Breeze, Filament, Yii Gii). | **Rendah**. Harus mendefinisikan interface, DTO, mapper, dan model agregat terpisah. |
| **Ketergantungan Framework (Coupling)** | **Tinggi (Terkunci)**. Migrasi framework berarti menulis ulang seluruh aplikasi. | **Nol pada Domain Core**. Framework hanya berperan sebagai delivery mechanism di layer luar. |
| **Kecepatan Unit Test (Test Execution Speed)** | **Lambat**. Pengujian sering membutuhkan boot database, koneksi HTTP mocking terpusat. | **Sangat Cepat**. 10.000 test dapat berjalan dalam 2 detik karena 100% menggunakan memory-mocked ports. |
| **Beban Kognitif Pengembang (*Boilerplate*)** | **Rendah**. File lebih sedikit; controller langsung berinteraksi dengan model. | **Tinggi**. Membutuhkan konversi (*mapping*) konstan: DB Record -> Entity -> DTO -> Response. |
| **Ketahanan Refactoring Domain** | **Rentan Rusak**. Perubahan skema tabel berdampak langsung pada business logic layer. | **Sangat Kuat**. Domain entity terisolasi dari skema fisik database berkat data mapper. |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Masalah Transaksi Database Lintas-Repositori (*Cross-Aggregate Transactions*)
* **Masalah**: Jika Use Case memanggil `$repoA->save($entityA)` dan `$repoB->save($entityB)`, bagaimana menjamin ACID transaction tanpa mengimpor antarmuka `PDO` atau `DB::transaction` ke dalam Use Case?
* **Solusi Edge Case**: Buat Driven Port untuk Unit of Work atau Transaction Manager:
```php
namespace Core\Application\Port\Out;

interface TransactionManagerPort
{
    /**
     * @template T
     * @param callable(): T $operation
     * @return T
     */
    public function transactional(callable $operation): mixed;
}
```

### 2. Kebocoran Abstraksi Melalui Lazy-Loading
* **Masalah**: Adapter mengirim Domain Entity yang memiliki properti relasi yang belum di-fetch dari DB. Ketika Domain mengecek `$order->getItems()`, ORM di belakang layar memicu trigger I/O runtime (*lazy evaluation*).
* **Solusi**: Entitas Domain murni tidak boleh memiliki relasi dynamic lazy-proxy ORM. Seluruh agregat harus di-load lengkap (*fully hydrated aggregate root*) di dalam Repository Adapter sebelum dikembalikan ke Application layer.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Mengimpor Kelas HTTP Request ke Dalam Use Case
* **Kesalahan Fatal**:
  ```php
  // SALAH BESAR di Application Layer
  use Psr\Http\Message\ServerRequestInterface;

  class CreateOrderUseCase {
      public function execute(ServerRequestInterface $request): void {
          $body = $request->getParsedBody();
          // ...
      }
  }
  ```
* **Cara Memperbaiki**: Jangan biarkan Use Case tahu konsep HTTP. Ekstrak data di Controller, buat `CreateOrderCommand` (DTO murni tanpa dependensi eksternal), dan oper DTO tersebut ke Use Case.

### 2. Kebocoran Anotasi ORM ke Domain Entity
* **Kesalahan Fatal**:
  ```php
  // SALAH di Domain Layer
  use Doctrine\ORM\Mapping as ORM;

  #[ORM\Entity]
  #[ORM\Table(name: "users")]
  class User { ... }
  ```
* **Cara Memperbaiki**: Pisahkan Entity Domain dari Entity ORM. Jika menggunakan Doctrine, gunakan XML/YAML mapping di Infrastructure layer, atau buat kelas `DoctrineUserEntity` di Infrastructure yang di-map ke `User` (Domain Entity) melalui mapper manual.

### 3. Anemic Domain Models
* **Kesalahan**: Membuat Entity yang hanya berisi properti privat dengan *getter* dan *setter* publik tanpa method bisnis (hanya sekadar struktur penampung data), sementara seluruh validasi dan kalkulasi ditaruh di Use Case.
* **Cara Memperbaiki**: Pindahkan logika validasi dan aturan mutasi ke dalam Entity. Gunakan pola enkapsulasi: jangan sediakan setter; buat method eksplisit seperti `$account->freeze()`, `$subscription->cancel()`.

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Aturan Struktur Direktori PSR-4**:
   Bagi struktur namespace secara tegas:
   * `Vendor\Project\Domain\`
   * `Vendor\Project\Application\`
   * `Vendor\Project\Infrastructure\`
2. **Strict Typing Mutlak**: Selalu gunakan `declare(strict_types=1);` di baris pertama setiap file PHP tanpa terkecuali.
3. **Immutability First**: Manfaatkan `readonly class` pada PHP 8.2+ untuk seluruh Value Objects dan DTO guna mencegah manipulasi *state* secara tidak sengaja di luar alur bisnis.
4. **Interface Segregation**: Hindari satu repository raksasa (`UserRepositoryInterface` dengan 50 method). Pecah menjadi antarmuka yang ramping: `UserReaderInterface`, `UserWriterInterface` jika diperlukan oleh bounded context berbeda.
5. **Architectural Testing dengan PHPAT atau Deptrac**: Pasang library analisis statis (seperti `qossmic/deptrac`) di pipeline CI/CD untuk menggagalkan build jika ada kelas di `Domain/` yang memanggil namespace `Infrastructure/` atau `Symfony/`.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Menghilangkan Overhead Mapping Menggunakan Generator untuk Koleksi Besar
Ketika mengambil 50.000 record untuk pelaporan, me-map seluruh baris menjadi Domain Entity murni secara simultan akan menghabiskan memori RAM secara signifikan.
* **Solusi**: Gunakan PHP `Generator` (`yield`) pada Port dan Repository Adapter:

```php
// Port Definition
interface LargeDatasetPort
{
    /** @return \Generator<int, TransactionEntity> */
    public function streamAll(): \Generator;
}

// Adapter Implementation
public function streamAll(): \Generator
{
    $stmt = $this->pdo->query('SELECT * FROM transactions');
    while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
        yield $this->hydrate($row); // Memory footprint konstan < 2MB
    }
}
```

### 2. Command Query Responsibility Segregation (CQRS) Ringan
Jangan gunakan alur Hexagonal penuh (Domain Aggregate -> Mapping -> Presenter) hanya untuk menampilkan data read-only sederhana di tabel grid dashboard.
* **Write Path**: Gunakan full Hexagonal / Clean Architecture (Command -> UseCase -> Domain Entity -> Driven Port -> DB).
* **Read Path**: Lewati Domain layer! Controller langsung memanggil Driven Port Query Service yang mengeksekusi query database teroptimasi langsung ke Read-DTO untuk performa maksimal.

---

# SEKSI 16 — KEAMANAN & HARDENING

```
[Untrusted HTTP Payload] 
       |
       v
[Controller / Primary Adapter]  <--- Filter Sanitasi, Casting Tipe Data & CSRF/Auth
       |
       v (DTO Primitif Bersih)
[Use Case Boundary]             <--- Otentikasi Akses & Permission Checks
       |
       v
[Domain Boundary / Entity]      <--- Invariant Integrity: Validasi Regex, Enkapsulasi Mutlak
```

1. **Batas Sanitasi String**: Jangan biarkan format data kotor masuk ke Domain. Domain mengasumsikan tipe data sudah terfilter secara sintaksis, namun Domain wajib memvalidasi aturan semantik (contoh: Domain melempar exception jika format IBAN bank tidak sesuai checksum).
2. **Defensive Copying**: Ketika mengekspos state internal dari sebuah Aggregate, jangan pernah mengembalikan referensi objek yang *mutable*. Kembalikan *cloned object* atau *immutable primitives*.

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Di Clean Architecture, kita tidak mengotori domain dengan pemanggilan langsung `$logger->info()`. Gunakan **Decorator Pattern** untuk membungkus Use Case atau Port guna keperluan tracing dan observabilitas:

```php
<?php

declare(strict_types=1);

namespace Infrastructure\Monitoring;

use Core\Application\Port\In\RenewSubscriptionUseCaseInterface;
use Core\Application\DTO\RenewSubscriptionCommand;
use Core\Application\DTO\RenewSubscriptionResponse;
use Psr\Log\LoggerInterface;

// Logging Decorator transparan membungkus Driving Port
final readonly class LoggingRenewSubscriptionDecorator implements RenewSubscriptionUseCaseInterface
{
    public function __construct(
        private RenewSubscriptionUseCaseInterface $inner,
        private LoggerInterface $logger
    ) {}

    public function execute(RenewSubscriptionCommand $command): RenewSubscriptionResponse
    {
        $startTime = microtime(true);
        $this->logger->info("Memulai proses perpanjangan langganan.", [
            'subscription_id' => $command->subscriptionId
        ]);

        try {
            $response = $this->inner->execute($command);

            $duration = microtime(true) - $startTime;
            $this->logger->info("Selesai proses perpanjangan langganan.", [
                'subscription_id' => $command->subscriptionId,
                'status' => $response->success ? 'SUCCESS' : 'FAILED',
                'duration_ms' => round($duration * 1000, 2)
            ]);

            return $response;
        } catch (\Throwable $e) {
            $this->logger->error("Fatal error saat eksekusi Use Case perpanjangan langganan.", [
                'subscription_id' => $command->subscriptionId,
                'error' => $e->getMessage()
            ]);
            throw $e;
        }
    }
}
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### The "Can-See-What" Matrix

| Dari Layer \ Ke Layer | Domain | Application | Infrastructure | Framework / External |
| :--- | :---: | :---: | :---: | :---: |
| **Domain** | **YA** | **TIDAK** | **TIDAK** | **TIDAK** |
| **Application** | **YA** | **YA** | **TIDAK** | **TIDAK** |
| **Adapters** | **YA** | **YA** | **YA** | **YA** |
| **Infrastructure Bootstrap** | **YA** | **YA** | **YA** | **YA** |

### Checklist Pengujian Cepat
* Apakah domain Anda mengimpor sesuatu di luar SPL PHP? Jika ya, perbaiki dependensi tersebut.
* Bisakah Anda menguji alur use case bisnis tanpa mendirikan database test SQLite/MySQL? Jika tidak, domain Anda masih mengalami *leakage* dependensi I/O.
* Apakah nama-nama direktori di folder proyek Anda mencerminkan problem domain (misal: `Billing`, `LoanApplication`) alih-alih nama struktur framework (misal: `Controllers`, `Models`, `Views`)? Arsitektur yang baik harus *berteriak* (*Screaming Architecture*) tentang bisnis yang dijalankan.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Pilihlah satu jawaban yang paling tepat untuk setiap pertanyaan.

### Tingkat Dasar (Basic)

1. **Apa perbedaan mendasar antara Driving Port dan Driven Port dalam arsitektur Hexagonal?**
   * A. Driving Port adalah interface untuk database; Driven Port adalah interface untuk UI.
   * B. Driving Port mengontrol Use Case dari luar sistem (misal: Controller); Driven Port dikontrol oleh Use Case untuk interaksi eksternal (misal: Database).
   * C. Driving Port hanya boleh dibuat menggunakan Abstract Class, sedangkan Driven Port menggunakan Interface.
   * D. Driven Port mengeksekusi HTTP Request, Driving Port mengirimkan pesan RabbitMQ.

2. **Berdasarkan The Dependency Rule dalam Clean Architecture, namespace manakah yang TIDAK BOLEH diimpor di dalam file Domain Entity?**
   * A. `DateTimeImmutable`
   * B. `InvalidArgumentException`
   * C. `Illuminate\Support\Collection`
   * D. `Core\Domain\Model\ValueObject`

3. **Apa peran utama dari sebuah Data Transfer Object (DTO) pada batas Use Case?**
   * A. Mengonfigurasi tabel skema database secara otomatis.
   * B. Mengalirkan data primitif masuk dan keluar dari Use Case tanpa mengaitkan layer dalam dengan format transport seperti HTTP atau JSON.
   * C. Menggantikan peran Domain Entity secara permanen.
   * D. Menyediakan method persistensi data seperti `save()` dan `update()`.

4. **Di lapisan manakah letak antarmuka `UserRepositoryInterface` (Port) yang digunakan oleh Use Case untuk menyimpan data pengguna?**
   * A. Infrastructure Layer
   * B. Delivery/Web Layer
   * C. Application atau Domain Layer
   * D. Vendor Layer

5. **Mengapa pola ActiveRecord tradisional bertentangan dengan prinsip Clean Architecture?**
   * A. Karena performa runtime ActiveRecord lebih lambat dibanding query raw SQL.
   * B. Karena ActiveRecord menggabungkan logika komputasi bisnis dengan detail persistensi basis data secara erat.
   * C. Karena ActiveRecord tidak mendukung PHP 8.2+.
   * D. Karena file migrasi ActiveRecord sulit ditulis.

---

### Tingkat Menengah (Intermediate)

6. **Bagaimana cara Use Case mengeksekusi operasi ACID Transaction pada beberapa Secondary Ports tanpa melanggar Dependency Rule?**
   * A. Memanggil class `\PDO::beginTransaction()` langsung di dalam kode Use Case.
   * B. Menggunakan Driving Adapter untuk menangani koneksi database mentah.
   * C. Membuat Driven Port abstraksi (misal `TransactionManagerInterface`) yang diimplementasikan di Infrastructure Layer.
   * D. Mengabaikan ACID transaction karena Clean Architecture tidak mendukungnya.

7. **Kapan sebaiknya kita menolak implementasi Hexagonal / Clean Architecture pada suatu proyek software?**
   * A. Saat proyek memiliki banyak integrasi API pihak ketiga.
   * B. Saat aplikasi berupa Simple CRUD, prototipe throw-away, atau sistem dengan kompleksitas bisnis yang sangat minim.
   * C. Saat sistem akan dipasang pada platform server berbasis Docker.
   * D. Saat menggunakan PHP-FPM alih-alih PHP-CLI.

8. **Apa bahaya terbesar membiarkan pustaka ORM memicu "Lazy Loading" di dalam lapisan Domain atau Presenter?**
   * A. Mengakibatkan memory leak pada semua eksekusi CLI script.
   * B. Menghancurkan isolasi lapisan dengan memicu I/O database tersembunyi yang tidak terkontrol di luar boundary infrastructure.
   * C. Memaksa web browser melakukan parsing ulang CSS file.
   * D. Menghapus data session Redis secara asinkron.

9. **Teknik apa yang paling tepat untuk menambahkan integrasi Audit Logging pada sebuah Use Case tanpa merubah baris kode pada kelas Use Case tersebut?**
   * A. Mengubah access modifier method dari private menjadi public.
   * B. Menerapkan Decorator Pattern pada interface Driving Port yang membungkus Use Case sebenarnya.
   * C. Menggunakan fungsi `debug_backtrace()` di dalam Domain Entity.
   * D. Memasukkan pemanggilan database statis `Audit::log()` di Use Case.

10. **Bagaimana pendekatan CQRS (Command Query Responsibility Segregation) melengkapi Clean Architecture secara optimal?**
    * A. Dengan menghapus seluruh kebutuhan akan Unit Test.
    * B. Dengan menduplikasi database menjadi MySQL dan PostgreSQL secara bersamaan.
    * C. Dengan mengizinkan pembacaan data sederhana (*Query*) mengambil langsung dari Read Storage tanpa harus melalui pemodelan Aggregate Domain yang berat.
    * D. Dengan melarang penggunaan SQL SELECT statements.

---

### Kunci Jawaban & Rasional Singkat

1. **B**: Driving port mengarahkan alur masuk ke aplikasi, Driven port diarahkan keluar oleh aplikasi.
2. **C**: Paket Laravel Illuminate adalah pustaka framework eksternal; domain murni harus bebas dari dependensi framework pihak ketiga.
3. **B**: DTO berfungsi sebagai pembawa data agnostik antar lapisan perbatasan.
4. **C**: Port didefinisikan oleh modul tingkat tinggi (Application/Domain) yang membutuhkan fungsionalitas tersebut, bukan oleh infrastruktur yang mengimplementasikannya.
5. **B**: ActiveRecord melanggar pemisahan tanggung jawab (SRP) dengan menyatukan representasi state bisnis dan persistence IO.
6. **C**: Sesuai Dependency Inversion Principle, abstraksi port dibuat di dalam layer inti, sedangkan implementasi teknis eksekusinya ditempatkan di infrastruktur.
7. **B**: Arsitektur ini memiliki biaya *overhead scaffolding* yang tinggi. Aplikasi CRUD sederhana lebih efisien diselesaikan dengan pola klasik.
8. **B**: Lazy loading menyamarkan operasi jaringan/disk seolah-olah hanya akses properti memori biasa, merusak kepastian deterministik Clean Architecture.
9. **B**: Decorator Pattern mengizinkan penambahan *cross-cutting concerns* (logging, caching, metrics) tanpa melanggar *Open-Closed Principle*.
10. **C**: Mengurangi overhead komputasi dan mapping layer yang tidak perlu saat sistem hanya bertugas menampilkan baris data tabular ke UI.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Deskripsi Mini Project Praktikum
Bangunlah sub-komponen terisolasi murni: **"Multi-Tenant Invoice Generation Engine"** menggunakan arsitektur Hexagonal murni tanpa menggunakan framework apapun (Pure PHP 8.2+).

### Batasan Teknis & Aturan Main:
1. **Dilarang keras** menggunakan composer dependency selain:
   * Engine pengujian: `phpunit/phpunit` (untuk test runner dev).
2. **Domain Boundaries**:
   * Entitas: `Invoice`, `InvoiceLineItem`, `TaxRate`.
   * Value Objects: `InvoiceNumber`, `Money`.
   * Aturan Bisnis: Total faktur dihitung dari: `Subtotal + (Subtotal * TaxRate) - Discount`. Diskon tidak boleh melebihi nilai subtotal.
3. **Application Layer**:
   * Buat `CreateInvoiceUseCaseInterface` (Driving Port).
   * Buat `InvoiceRepositoryPort` (Driven Port).
   * Buat `TaxRateCalculatorPort` (Driven Port).
4. **Infrastructure Layer**:
   * Buat `InMemoryInvoiceRepository` untuk kebutuhan test.
   * Buat `FixedTaxRateAdapter` untuk implementasi Driven Port.
5. **Kriteria Kelulusan Mutlak**:
   * Tuliskan sebuah Test Unit PHPUnit komprehensif yang menguji pembuatan invoice dengan skenario valid dan skenario melempar `DomainException` saat kalkulasi diskon tidak valid.
   * Seluruh tes unit wajib berjalan tuntas dalam waktu kurang dari 50ms tanpa menyentuh disk I/O sama sekali.
   * Lakukan verifikasi manual bahwa tidak ada kata kunci `PDO`, `mysqli`, atau namespace framework eksternal yang diimpor di direktori `Domain/` dan `Application/`.