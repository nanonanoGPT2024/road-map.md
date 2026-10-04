# Kurikulum Enterprise Rekayasa Perangkat Lunak: Laravel
## Kategori: 04-Backend-and-Database
### BAB-03: Deep Dive Eloquent ORM & Advanced Data Modeling
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Principal Software Engineer/Senior Backend Engineer diharapkan mampu:
1. **Membedah & Mengoptimasi Pipeline Hidrasi Eloquent**: Menganalisis alur internal siklus hidup Eloquent dari PDO raw fetch, instansiasi model, deserialisasi atribut via Custom Casts bernilai objek (*Value Objects*), hingga penanganan memori pada dataset skala jutaan baris.
2. **Mengimplementasikan Polimorfisme Skala Produksi yang Aman**: Menghindari *string coupling* dan degradasi performa pada relasi polimorfik menggunakan *Strict Morph Maps* dan integrasi relasi polimorfik banyak-ke-banyak (*Many-to-Many Polymorphic*) yang terindeks secara optimal.
3. **Mengisolasi Domain Logic Menggunakan Custom Query Builders & Custom Collections**: Merefaktor kueri ad-hoc dan scope prosedural menjadi *Domain-Specific Query Builders* berorientasi objek yang memperkuat *encapsulation*, *type safety*, dan *composability*.
4. **Mendesain Pola Single Table Inheritance (STI) & Class Table Inheritance (CTI)**: Mengatasi keterbatasan native Eloquent dalam memetakan hierarki pewarisan data tanpa merusak integritas relasional maupun integritas domain model.
5. **Mengelola Siklus Transaksi Kompleks & Savepoints**: Memitigasi deadlock, race condition, dan fragmentasi transaksional menggunakan nested database transactions, savepoints, serta *dirty tracking control* untuk operasi atomik bertransaksi tinggi.

---

### 2. Prerequisite

Sebelum menelaah modul ini, peserta wajib menguasai:
*   **PHP 8.2/8.3 Core**: Strict typing (`declare(strict_types=1);`), Enums, Readonly Classes/Properties, Weak References, dan Fiber/Generators.
*   **Relational Database Internals (MySQL 8.0+ / PostgreSQL 15+)**: ACID, Transaction Isolation Levels (khususnya *Read Committed* vs *Repeatable Read*), Locking Mechanisms (*Pessimistic vs Optimistic, Gap Locks, Intention Locks*), B-Tree Indexing, dan Partisi Data.
*   **Fundamental Laravel Eloquent**: Active Record pattern, Query Builder dasar, Migration, Seeder, dan Relasi Standar (`hasMany`, `belongsTo`, `belongsToMany`).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Anatomi Siklus Hidrasi (Hydration Lifecycle) Eloquent
Active Record pada Laravel mengenkapsulasi baris database ke dalam instance model. Namun, proses konversi raw SQL result set menjadi kumpulan Model Eloquent membawa overhead komputasi dan memori yang masif jika arsitekturnya tidak dipahami:

```
[Database Engine]
       │
       ▼ (Raw Buffer over Socket)
[PDO Statement / Driver]
       │  PDO::FETCH_ASSOC (Array of strings/primitives)
       ▼
[Illuminate\Database\Connection]
       │  runQueryCallback() -> Statement Execution
       ▼
[Illuminate\Database\Eloquent\Builder]
       │  get() -> Pipeline
       ▼
[Illuminate\Database\Eloquent\Model::hydrate()]
       │
       ├─► Loop raw arrays
       │   ├─► newFromBuilder()
       │   │   ├─► newInstance() [Allocation of zval, attributes, original]
       │   │   ├─► setRawAttributes($attributes, sync = true)
       │   │   └─► fireModelEvent('retrieved', halt = false)
       │   └─► Mutator / Cast Evaluation (Lazy, unless eager-accessed)
       │
       ▼
[Illuminate\Database\Eloquent\Collection]
```

Ketika statement dieksekusi, PDO mengembalikan raw memory array. Eloquent menjalankan loop melalui method `hydrate()`. Untuk setiap baris data:
1. `newFromBuilder()` dieksekusi tanpa memicu constructor domain default (`__construct`).
2. Array mentah disimpan dalam array internal `$attributes`.
3. Array tersebut digandakan ke dalam internal array `$original` untuk memfasilitasi algoritma *dirty checking* (`isDirty()`, `getDirty()`).
4. Hook event `retrieved` ditembakkan melalui Event Dispatcher.

*Dampak Memori*: Satu baris raw SQL berisi 10 kolom varchar hanya memakan ~1 KB memori di level database. Namun, setelah dihidrasi menjadi model Eloquent lengkap dengan tracking dirty state, relasi, mutator cache, dan event dispatcher link, footprint memory PHP membengkak hingga ~8 KB - 15 KB per instance model. Mengambil 100.000 record sekaligus melalui `Model::all()` akan menghabiskan lebih dari 150 MB memori PHP dan memicu `Fatal Error: Allowed memory size exhausted`.

#### 3.2. Dynamic & Custom Query Builders
Secara default, pemanggilan statik pada Eloquent Model seperti `User::query()` mengembalikan instance dari `Illuminate\Database\Eloquent\Builder`, yang kemudian membungkus `Illuminate\Database\Query\Builder` (Base Query Builder).

Arsitektur enterprise modern memisahkan tanggung jawab kueri dengan melakukan override pada method:
```php
public function newEloquentBuilder($query): CustomModelBuilder
```
Dengan menginjeksikan Custom Eloquent Builder, kita memindahkan logika bisnis query (*query scopes*) dari traits model yang bloated ke kelas spesifik yang *strongly typed*, memiliki *IDE autocompletion* penuh, dan dapat dites secara terisolasi tanpa memicu instansiasi model yang berat.

#### 3.3. Transaksi Tingkat Lanjut & Savepoints
Ketika menjalankan nested transaction di Laravel:
```php
DB::transaction(function () {
    // Transaksi Utama (Level 1)
    DB::transaction(function () {
        // Transaksi Tersarang (Level 2)
    });
});
```
Database engine (seperti MySQL atau PostgreSQL) tidak mendukung *true nested physical transactions*. Laravel menyelesaikan ini melalui abstraksi **Database Savepoints**.
*   Level 1: Menjalankan query SQL murni: `START TRANSACTION` / `BEGIN`.
*   Level 2: Laravel mendeteksi `$transactions > 0`, lalu mengeksekusi: `SAVEPOINT trans2`.
*   Jika Level 2 rollback: Laravel mengeksekusi `ROLLBACK TO SAVEPOINT trans2`. Transaksi utama di Level 1 tetap aman dan berjalan.
*   Jika Level 1 rollback: Menjalankan `ROLLBACK`, membatalkan seluruh operasi termasuk state sebelum dan sesudah savepoint.

Pahami bahwa *Savepoint Release* (`RELEASE SAVEPOINT`) memiliki overhead internal lock management di database engine; pemanggilan savepoint yang terlalu dalam pada loop intensif akan mendegradasi *concurrency throughput*.

---

### 4. Why & What

| Pendekatan Konvensional (Naive) | Pendekatan Enterprise (Advanced Eloquent) | Mengapa Berbeda? (Impact & Rationale) |
| :--- | :--- | :--- |
| Relasi Polimorfik menyimpan FQCN String (`App\Models\Invoice`) di kolom DB. | **Strict Morph Map** terdaftar eksplisit (`invoice`, `order`). | **Schema Agnostic & Decoupling**. Mencegah refactoring class/namespace merusak data historis DB dan menghemat byte storage indexing. |
| Logika kueri ditumpuk dalam *Local Scopes* (`scopeActive`, `scopePaid`) di dalam model. | **Domain-Specific Query Builders** terdedikasi per agregat. | **Separation of Concerns**. Model terbebas dari ribuan baris query logic, memfasilitasi *Single Responsibility Principle* dan composability kueri yang kompleks. |
| Cast database disimpan dan dimanipulasi sebagai primitive types (array, string). | **Value Object Casts** (`CastsAttributes`) dengan immutable class (e.g. `Money`, `Address`). | Mencegah **Primitive Obsession**, menjamin invariant domain valid sejak data diambil dari database, dan tipe data sepenuhnya aman (*type-safe*). |
| Penanganan batching data besar menggunakan `Model::all()` atau `Model::chunk()`. | **ChunkById** atau **LazyCollection via Cursor** (`cursor()`). | Mencegah memory ballooning dan mengeliminasi bug data skipping pada mutasi query running di pagination/chunk standar. |

---

### 5. How (Workflow Detail)

Alur eksekusi kueri terenkapsulasi enterprise menggunakan Custom Eloquent Builder dan Value Object:

```
[Client / Service Layer]
       │
       ▼ 1. User invokes Order::query()->wherePaid()->whereFulfilledBy(WarehouseId)
[Custom OrderQueryBuilder]
       │
       ▼ 2. Applies domain-level SQL constraints via Base Query Builder
[Database Connection (Read Replica)]
       │
       ▼ 3. SQL execution: "SELECT * FROM orders WHERE status = ? AND warehouse_id = ?"
[Raw Data Set (PDO Buffer)]
       │
       ▼ 4. Hydration Pipeline
[Order Model]
       │
       ▼ 5. Custom Cast Activation (Money, TrackingNumber Value Objects)
[Domain Order Model Fully Hydrated]
       │
       ▼ 6. Execution of Business Invariant
[Service marks state Dirty: $order->markAsDispatched()]
       │
       ▼ 7. Transaction Initiated (Write Master Node)
[Savepoint Created -> Model Saved -> Events Emitted via Transactional Lifecycle]
```

1. **Inisialisasi**: Service memanggil entry point kueri model domain.
2. **Abstraksi Builder**: Custom Builder menyusun AST (Abstract Syntax Tree) query tanpa mengekspos detail implementasi tabel (seperti nama kolom mentah database).
3. **Dispatching**: Database Manager mengarahkan query ke connection pool yang sesuai (Write Master vs Read Replica) secara dinamis.
4. **Hydration Phase**: Record baris database dihidrasi menjadi model. Nilai kolom serialisasi (seperti format JSON, integer sen) diubah seketika menjadi immutable Value Object melalui implementasi `CastsAttributes`.
5. **State Mutation**: Domain logic memodifikasi entity. Eloquent membandingkan `$attributes` vs `$original`.
6. **Persistence**: Perubahan ditulis ke Master DB dalam boundary transaksi ber-savepoint aman. Model Event dieksekusi hanya saat transaksi berhasil di-commit secara fisik (`afterCommit`).

---

### 6. Analogy & Diagram ASCII

#### 6.1. Pola Hidrasi Eloquent: Pabrik Manufaktur Berat vs Rakitan Ringan
Bayangkan **Raw PDO** seperti menerima paket kontainer kayu murni berisi baut mentah (sangat cepat dipindahkan, sangat sedikit memakan ruang penataan).
**Eloquent Hydration** ibarat pabrik manufaktur yang membuka setiap kotak baut, membubuhkan stempel sertifikasi keamanan, memasang sensor GPS (*dirty checking*), menyambungkan kabel listrik ke sistem pusat (*model events & database connection*), dan menaruh baut tersebut pada rak pajangan beludru (*Eloquent Collection*). 

Jika Anda butuh 5 baut untuk dirakit (transaksi detail), overhead ini memberikan kenyamanan dan proteksi absolut. Jika Anda memproses 500.000 baut sekaligus untuk disortir, pabrik Anda akan meledak karena kehabisan ruang dan daya listrik (*OOM Crash*).

#### 6.2. Arsitektur Polimorfik: Generic Foreign Key Matrix
```
             ┌────────────────────────┐
             │     AuditLog Model     │
             ├────────────────────────┤
             │ id: bigint (PK)        │
             │ auditable_type: string │  <-- Morph Map ("order", "invoice")
             │ auditable_id: bigint   │  <-- Target Record ID
             │ changes: json          │
             └───────────┬────────────┘
                         │
         ┌───────────────┴───────────────┐
         │ (auditable_type, auditable_id) │
         ▼ Index Composite Key           ▼
┌─────────────────┐             ┌─────────────────┐
│   Order Model   │             │  Invoice Model  │
├─────────────────┤             ├─────────────────┤
│ id: 1001        │             │ id: 504         │
│ total: $500.00  │             │ status: UNPAID  │
└─────────────────┘             └─────────────────┘
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Strict Morph Maps & Custom Cast Value Object

##### Value Object: `App\ValueObjects\Money.php`
```php
<?php

declare(strict_types=1);

namespace App\ValueObjects;

use InvalidArgumentException;
use JsonSerializable;

final readonly class Money implements JsonSerializable
{
    public function __construct(
        public int $amountInCents,
        public string $currency = 'IDR'
    ) {
        if ($this->amountInCents < 0) {
            throw new InvalidArgumentException("Money amount cannot be negative.");
        }
    }

    public static function fromCents(int $amount, string $currency = 'IDR'): self
    {
        return new self($amount, $currency);
    }

    public function toDecimal(): float
    {
        return $this->amountInCents / 100;
    }

    public function jsonSerialize(): array
    {
        return [
            'amount_in_cents' => $this->amountInCents,
            'decimal' => $this->toDecimal(),
            'currency' => $this->currency,
        ];
    }
}
```

##### Custom Cast: `App\Casts\MoneyCast.php`
```php
<?php

declare(strict_types=1);

namespace App\Casts;

use App\ValueObjects\Money;
use Illuminate\Contracts\Database\Eloquent\CastsAttributes;
use Illuminate\Database\Eloquent\Model;
use InvalidArgumentException;

/**
 * @implements CastsAttributes<Money, Money>
 */
class MoneyCast implements CastsAttributes
{
    public function get(Model $model, string $key, mixed $value, array $attributes): ?Money
    {
        if ($value === null) {
            return null;
        }

        $currency = $attributes['currency'] ?? 'IDR';

        return new Money((int) $value, (string) $currency);
    }

    public function set(Model $model, string $key, mixed $value, array $attributes): ?int
    {
        if ($value === null) {
            return null;
        }

        if (!$value instanceof Money) {
            throw new InvalidArgumentException("The attribute {$key} must be an instance of " . Money::class);
        }

        return $value->amountInCents;
    }
}
```

##### Strict Morph Map Registration: `App\Providers\AppServiceProvider.php`
```php
<?php

declare(strict_types=1);

namespace App\Providers;

use App\Models\Invoice;
use App\Models\Order;
use Illuminate\Database\Eloquent\Relations\Relation;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    public function boot(): void
    {
        // Mematikan FQCN fallback. Wajib eksplisit!
        Relation::enforceMorphMap([
            'order' => Order::class,
            'invoice' => Invoice::class,
        ]);
    }
}
```

---

#### 7.2. Practical Example: Enterprise Multi-Ledger with Custom Builder & STI Pattern

Berikut adalah implementasi sistem Single Table Inheritance (STI) untuk transaksi FinTech (Deposit, Withdrawal, Transfer) yang berjalan di atas satu tabel ledger fisik (`ledger_entries`), namun terpecah menjadi domain model spesifik via Custom Query Builder dan Global Scopes.

##### Migration: `create_ledger_entries_table.php`
```php
<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        Schema::create('ledger_entries', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->uuid('account_id')->index();
            $table->string('type', 32)->index(); // Discriminator column
            $table->bigInteger('amount_cents');
            $table->string('currency', 3);
            $table->string('status', 32)->index();
            $table->json('metadata')->nullable();
            $table->timestamps();

            // Compound index for high performance reporting queries
            $table->index(['account_id', 'type', 'created_at']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('ledger_entries');
    }
};
```

##### Custom Query Builder: `App\Builders\LedgerEntryBuilder.php`
```php
<?php

declare(strict_types=1);

namespace App\Builders;

use Illuminate\Database\Eloquent\Builder;

/**
 * @template TModelClass of \App\Models\LedgerEntry
 * @extends Builder<TModelClass>
 */
class LedgerEntryBuilder extends Builder
{
    public function whereSettled(): self
    {
        return $this->where('status', 'SETTLED');
    }

    public function wherePending(): self
    {
        return $this->where('status', 'PENDING');
    }

    public function forAccount(string $accountId): self
    {
        return $this->where('account_id', $accountId);
    }

    public function olderThanDays(int $days): self
    {
        return $this->where('created_at', '<=', now()->subDays($days));
    }
}
```

##### Base Model: `App\Models\LedgerEntry.php`
```php
<?php

declare(strict_types=1);

namespace App\Models;

use App\Builders\LedgerEntryBuilder;
use App\Casts\MoneyCast;
use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

/**
 * @property string $id
 * @property string $account_id
 * @property string $type
 * @property \App\ValueObjects\Money $amount
 * @property string $currency
 * @property string $status
 * @property array|null $metadata
 * @property \Carbon\CarbonImmutable $created_at
 * @property \Carbon\CarbonImmutable $updated_at
 */
class LedgerEntry extends Model
{
    use HasUuids;

    protected $table = 'ledger_entries';

    protected $guarded = ['id'];

    protected $casts = [
        'amount_cents' => MoneyCast::class,
        'metadata' => 'array',
        'created_at' => 'immutable_datetime',
        'updated_at' => 'immutable_datetime',
    ];

    /**
     * Override method newEloquentBuilder untuk memasang Custom Builder
     */
    public function newEloquentBuilder($query): LedgerEntryBuilder
    {
        return new LedgerEntryBuilder($query);
    }
}
```

##### Derived Class (STI): `App\Models\DepositEntry.php`
```php
<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Builder;

class DepositEntry extends LedgerEntry
{
    protected static function booted(): void
    {
        static::addGlobalScope('deposit_type', function (Builder $builder) {
            $builder->where('type', 'DEPOSIT');
        });

        static::creating(function (self $model) {
            $model->type = 'DEPOSIT';
        });
    }
}
```

##### Derived Class (STI): `App\Models\WithdrawalEntry.php`
```php
<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Builder;

class WithdrawalEntry extends LedgerEntry
{
    protected static function booted(): void
    {
        static::addGlobalScope('withdrawal_type', function (Builder $builder) {
            $builder->where('type', 'WITHDRAWAL');
        });

        static::creating(function (self $model) {
            $model->type = 'WITHDRAWAL';
        });
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Ledger Transaksi E-Commerce Finansial Global (PT Global Retail Nusantara)
*   **Throughput**: 45.000 transaksi/menit pada *flash sale*.
*   **Masalah Arsitektural**: Sistem audit log menggunakan polymorphic relation Eloquent default (`auditable_type` menyimpan nama FQCN kelas `App\Models\Order`).
*   **Petaka Produksi**:
    1. Tim engineers melakukan refactoring modularisasi sistem. Kelas `App\Models\Order` dipindahkan ke sub-domain `App\Domain\Ordering\Models\Order`.
    2. Seketika itu juga, ratusan juta record audit log lama kehilangan relasi parent model karena mismatch FQCN. Dashboard finansial menghasilkan jutaan 500 response akibat fatal null-pointer exception pada `$log->auditable->id`.
    3. Indeks polimorfik MySQL `(auditable_type, auditable_id)` membengkak secara masif karena menyimpan string FQCN yang panjang (50+ karakter per baris), menyebabkan Buffer Pool Thrashing.

#### Arsitektur Solusi Terintegrasi
1. **Penerapan Migration Enforcement & Morph Map**: Mengunci identifier polimorfik menjadi string singkat (`ord`, `inv`, `wth`).
2. **Read/Write Splitting Aware with Sticky Connections**: Mencegah *read-your-own-writes race condition* akibat lag replikasi master-replica menggunakan konfigurasi sticky connection.
3. **Database Ledger Locking & Savepoints**: Eksekusi mutasi saldo wajib menggunakan pessimistic row-locking (`lockForUpdate()`) dibungkus transaksi ber-savepoint terisolasi.

##### Implementasi Solusi Transaksional Aman:
```php
<?php

declare(strict_types=1);

namespace App\Services;

use App\Models\DepositEntry;
use App\Models\WithdrawalEntry;
use App\ValueObjects\Money;
use Illuminate\Support\Facades\DB;
use Throwable;

final class HighThroughputLedgerService
{
    /**
     * Transfer saldo antar entitas secara atomik tanpa risiko deadlocks antar-node
     */
    public function transfer(
        string $sourceAccountId,
        string $destinationAccountId,
        Money $amount,
        string $referenceId
    ): void {
        // Urutkan UUID secara leksikografis untuk mencegah database deadlock!
        $orderedAccounts = [$sourceAccountId, $destinationAccountId];
        sort($orderedAccounts, SORT_STRING);

        DB::transaction(function () use ($sourceAccountId, $destinationAccountId, $amount, $referenceId, $orderedAccounts) {
            // 1. Lock rows dengan deterministik berurutan
            foreach ($orderedAccounts as $accId) {
                DB::table('accounts')->where('id', $accId)->lockForUpdate()->first();
            }

            // 2. Operasi Withdrawal dalam Nested Savepoint
            DB::transaction(function () use ($sourceAccountId, $amount, $referenceId) {
                WithdrawalEntry::query()->create([
                    'account_id' => $sourceAccountId,
                    'amount_cents' => $amount,
                    'currency' => $amount->currency,
                    'status' => 'SETTLED',
                    'metadata' => ['ref' => $referenceId, 'step' => 'debit'],
                ]);
            });

            // 3. Operasi Deposit dalam Nested Savepoint
            DB::transaction(function () use ($destinationAccountId, $amount, $referenceId) {
                DepositEntry::query()->create([
                    'account_id' => $destinationAccountId,
                    'amount_cents' => $amount,
                    'currency' => $amount->currency,
                    'status' => 'SETTLED',
                    'metadata' => ['ref' => $referenceId, 'step' => 'credit'],
                ]);
            });
        }, 5); // Otomatis retry 5 kali jika terdeteksi deadlock transient level DBMS
    }
}
```

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

```
                     ARBITRASE ARSITEKTUR ELOQUENT
                     
       Fleksibilitas Abstraksi               Throughput / Efisiensi Memori
      (Domain-Driven Development)            (Data Heavy / Batch Processing)
                │                                          │
                ├─► Full Eloquent Model                    ├─► DB Facade / Raw PDO
                │   (Hydration, Observers,                 │   (Zero-hydration, Low Mem,
                │    Dirty Tracking, Casts)                │    Zero Object Overhead)
                │                                          │
                ▼                                          ▼
   Latency:     +1.5ms - 3.0ms per model      Latency:     <0.1ms per record
   Memory:      ~8KB - 15KB per row           Memory:      ~0.5KB per row
   Scalability: Max 5k records / process      Scalability: Juta records / cursor
```

| Parameter | Full Eloquent Hydration | Raw DB / Query Builder | LazyCollection (Cursor) |
| :--- | :--- | :--- | :--- |
| **Object Allocation** | Sangat Tinggi (Instansiasi kelas per row + internal array caching). | Nol (Hanya pure PHP `stdClass` atau `array`). | Rendah (Satu instance model dihidrasi bergantian melalui iterator). |
| **Throughput (Writes)** | Sedang (~2.000 ops/sec karena lifecycle events & dirty checks). | Sangat Tinggi (~25.000+ ops/sec via multi-insert statement murni). | N/A (Khusus streaming read). |
| **Domain Invariant Safety** | Sangat Terproteksi (Enkapsulasi via Casts, Observers, Types). | Lemah (Raw types, resiko SQL tampering jika logic tercecer). | Terproteksi (Model lifecycle tetap terpicu per row). |
| **Infrastructure Cost** | Server RAM tinggi (Horizontal scaling web worker lebih cepat). | Minim RAM, optimasi I/O maksimal. | Optimal untuk background processing (CLI/Worker). |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Kesalahan Fatal: Skip Data pada Modifikasi Saat Iterasi `chunk()`
Pengembang kerap menjalankan migrasi data atau mutasi massal seperti ini:
```php
// ANTI-PATTERN: Data skipping bug!
LedgerEntry::where('status', 'PENDING')->chunk(100, function ($entries) {
    foreach ($entries as $entry) {
        $entry->update(['status' => 'SETTLED']);
    }
});
```
*Penyebab*: `chunk(100)` internalnya mengaplikasikan SQL `LIMIT 100 OFFSET 0`, lalu `LIMIT 100 OFFSET 100`. Ketika batch pertama (100 row) diubah statusnya menjadi `SETTLED`, row tersebut keluar dari kondisi kueri `where('status', 'PENDING')`. Batch kedua dengan `OFFSET 100` akan melompati 100 data yang bergeser ke atas!
*Solusi Enterprise*: Gunakan `chunkById()` yang berpijak pada primary key deterministik, bukan limit-offset pagination:
```php
LedgerEntry::where('status', 'PENDING')->chunkById(100, function ($entries) {
    foreach ($entries as $entry) {
        $entry->update(['status' => 'SETTLED']);
    }
});
```

#### 10.2. N+1 Polimorfik pada Eager Loading
Memanggil eager loading polimorfik secara parsial sering memicu eksekusi query liar:
```php
// BAHAYA: N+1 tersembunyi
$comments = Comment::with('commentable')->get();
```
Jika model `commentable` adalah polimorfik antar `Post`, `Video`, dan `Photo`, Eloquent mengeksekusi 1 query untuk mengambil entitas relasi per setiap jenis class yang ada di result set. Pastikan index gabungan `(commentable_type, commentable_id)` eksis. Jika hanya butuh subset kolom dari relasi yang berbeda tipe, gunakan *morph eager loading morph constraints*:
```php
use Illuminate\Database\Eloquent\Relations\MorphTo;

$comments = Comment::with([
    'commentable' => function (MorphTo $morphTo) {
        $morphTo->morphWith([
            Post::class => ['author'],
            Video::class => ['uploader'],
        ]);
    }
])->get();
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Enforce Morph Maps**: Nonaktifkan dynamic class resolving di `AppServiceProvider` menggunakan `Relation::enforceMorphMap([...])`. Jangan pernah biarkan nama FQCN disimpan di DB.
- [ ] **Disable Model Lazy Loading di CI/Staging**: Pasang `Model::preventLazyLoading(! app()->isProduction())` di development pipeline untuk menangkap N+1 queries sebelum menyentuh server produksi.
- [ ] **Enforce Immutable Datetime Casts**: Ganti seluruh binding `datetime` default dengan `immutable_datetime` agar instance Carbon tidak termutasi tanpa sengaja saat manipulasi tanggal.
- [ ] **Batasi Pemanggilan `all()` Tanpa Limit**: Larang pemanggilan static `Model::all()` melalui code sniffer (misal PHPStan rule). Wajib gunakan cursor atau pagination terindeks.
- [ ] **Kunci Kolom Timestamp saat Bulk Insert**: Ingat bahwa method `insert()` murni tidak mengeksekusi Eloquent lifecycle; pastikan `created_at` dan `updated_at` diisi manual jika menggunakan bulk operations.
- [ ] **Kelola Deadlock via Deterministic Ordering**: Kunci resource baris database secara urut (misal sorting berdasarkan ID/UUID sebelum memanggil `lockForUpdate()`).
- [ ] **Gunakan Transactional Events**: Pastikan event dispatching yang berdampak pada infrastruktur luar (Redis, Email, Queue) hanya dieksekusi setelah database selesai commit dengan trait `use Dispatchable, InteractsWithSockets, SerializesModels` dan property `$afterCommit = true`.

---

### 12. Hands-on Practice

Buat skenario enterprise di direktori `hands-on/m02/` yang mengimplementasikan Custom Eloquent Builder, Custom Cast Value Object, dan Strict Morph Mapping.

#### Langkah 1: Siapkan Struktur Direktori
```bash
mkdir -p hands-on/m02/app/Casts
mkdir -p hands-on/m02/app/ValueObjects
mkdir -p hands-on/m02/app/Builders
mkdir -p hands-on/m02/app/Models
mkdir -p hands-on/m02/database/migrations
```

#### Langkah 2: Buat Skema Migration
Simpan ke `hands-on/m02/database/migrations/2026_03_30_000001_create_polymorphic_wallets_tables.php`:
```php
<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        Schema::create('merchants', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->string('name');
            $table->timestamps();
        });

        Schema::create('customers', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->string('email')->unique();
            $table->timestamps();
        });

        Schema::create('wallets', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->string('holder_type', 32);
            $table->uuid('holder_id');
            $table->bigInteger('balance_cents')->default(0);
            $table->string('currency', 3)->default('IDR');
            $table->string('status', 32)->default('ACTIVE');
            $table->timestamps();

            $table->unique(['holder_type', 'holder_id']);
            $table->index(['status', 'currency']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('wallets');
        Schema::dropIfExists('customers');
        Schema::dropIfExists('merchants');
    }
};
```

#### Langkah 3: Implementasikan Value Object & Cast
Simpan ke `hands-on/m02/app/ValueObjects/Balance.php`:
```php
<?php

declare(strict_types=1);

namespace App\ValueObjects;

use RuntimeException;

final readonly class Balance
{
    public function __construct(
        public int $cents,
        public string $currency = 'IDR'
    ) {}

    public function debit(int $cents): self
    {
        if ($cents > $this->cents) {
            throw new RuntimeException("Insufficient wallet balance.");
        }
        return new self($this->cents - $cents, $this->currency);
    }

    public function credit(int $cents): self
    {
        return new self($this->cents + $cents, $this->currency);
    }
}
```

Simpan ke `hands-on/m02/app/Casts/BalanceCast.php`:
```php
<?php

declare(strict_types=1);

namespace App\Casts;

use App\ValueObjects\Balance;
use Illuminate\Contracts\Database\Eloquent\CastsAttributes;
use Illuminate\Database\Eloquent\Model;
use InvalidArgumentException;

class BalanceCast implements CastsAttributes
{
    public function get(Model $model, string $key, mixed $value, array $attributes): Balance
    {
        return new Balance(
            (int) ($value ?? 0),
            (string) ($attributes['currency'] ?? 'IDR')
        );
    }

    public function set(Model $model, string $key, mixed $value, array $attributes): int
    {
        if (! $value instanceof Balance) {
            throw new InvalidArgumentException("Value must be instance of Balance.");
        }
        return $value->cents;
    }
}
```

#### Langkah 4: Implementasikan Builder & Model Polimorfik
Simpan ke `hands-on/m02/app/Builders/WalletBuilder.php`:
```php
<?php

declare(strict_types=1);

namespace App\Builders;

use Illuminate\Database\Eloquent\Builder;

class WalletBuilder extends Builder
{
    public function whereActive(): self
    {
        return $this->where('status', 'ACTIVE');
    }

    public function whereSufficientFor(int $cents): self
    {
        return $this->where('balance_cents', '>=', $cents);
    }
}
```

Simpan ke `hands-on/m02/app/Models/Wallet.php`:
```php
<?php

declare(strict_types=1);

namespace App\Models;

use App\Builders\WalletBuilder;
use App\Casts\BalanceCast;
use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\MorphTo;

class Wallet extends Model
{
    use HasUuids;

    protected $guarded = ['id'];

    protected $casts = [
        'balance_cents' => BalanceCast::class,
    ];

    public function newEloquentBuilder($query): WalletBuilder
    {
        return new WalletBuilder($query);
    }

    public function holder(): MorphTo
    {
        return $this->morphTo();
    }
}
```

#### Langkah 5: Skrip Uji Eksekusi Transaksional
Simpan file runtime ke `hands-on/m02/test_run.php`:
```php
<?php

declare(strict_types=1);

require __DIR__ . '/../../vendor/autoload.php';

use App\Models\Customer;
use App\Models\Wallet;
use App\ValueObjects\Balance;
use Illuminate\Database\Eloquent\Relations\Relation;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

// Bootstrapping Strict Morph Map
Relation::enforceMorphMap([
    'customer' => Customer::class,
]);

// Simulasi Transaksi Mutasi Saldo Aman
DB::transaction(function () {
    $walletId = (string) Str::uuid();
    $customerId = (string) Str::uuid();

    // Raw simulation query insert to test Cast & Hydration
    $wallet = Wallet::query()->create([
        'id' => $walletId,
        'holder_type' => 'customer',
        'holder_id' => $customerId,
        'balance_cents' => new Balance(150000, 'IDR'),
        'currency' => 'IDR',
        'status' => 'ACTIVE',
    ]);

    echo "Wallet hydrated. Current balance: " . $wallet->balance_cents->cents . "\n";

    // Re-fetch via Custom Query Builder
    $retrievedWallet = Wallet::query()
        ->whereActive()
        ->whereSufficientFor(50000)
        ->findOrFail($walletId);

    // Mutate via Value Object
    $retrievedWallet->balance_cents = $retrievedWallet->balance_cents->debit(50000);
    $retrievedWallet->save();

    echo "Wallet debited. New balance: " . $retrievedWallet->balance_cents->cents . "\n";
});
```

---

### 13. Exercise

#### Level: Easy
1. Buat Custom Cast `EncryptedStringCast` yang mengenkripsi data sensitif (misal Nomor KTP) sebelum masuk ke database, dan men-dekripsinya saat dihidrasi ke model. Gunakan implementasi `Illuminate\Contracts\Database\Eloquent\CastsAttributes`.

#### Level: Medium
1. Refaktor skema User Profile konvensional menjadi polymorphic metadata system. Buat tabel `metadata` (`id`, `metadatable_type`, `metadatable_id`, `key`, `value`). Bangun Custom Collection `MetadataCollection` yang mewarisi `Illuminate\Database\Eloquent\Collection` dengan helper method `getValue(string $key, mixed $default = null)`.

#### Level: Hard
1. Buat mekanisme **Optimistic Locking Engine** custom tanpa package eksternal. 
   * Tambahkan kolom `lock_version: integer` pada model.
   * Override method `performUpdate()` di dalam BaseModel milik Anda.
   * Jika versi di memory tidak sama dengan versi di database saat query `UPDATE ... WHERE id = ? AND lock_version = ?` dieksekusi, throw domain exception `StaleModelLockingException`.
   * Model harus secara otomatis meng-inkrementasi `lock_version` setiap kali operasi save terjadi secara atomik.

---

### 14. Challenge

Anda ditunjuk sebagai Principal Architect untuk platform **High-Frequency Flash-Sale Ticketing**.
Terdapat batasan teknis ekstrem:
*   Sebuah tiket konser (`TicketTier`) memiliki kuota terbatas (`remaining_quantity`).
*   Saat flash-sale dibuka, 100.000 user mengirim request secara bersamaan untuk membeli tiket pada tier yang sama dalam rentang 3 detik.
*   Tiket tidak boleh over-allocated (*Zero Overselling Guarantee*).
*   Setiap reservasi tiket harus mencatat jejak polimorfik audit log ke dalam tabel `reservation_audits` yang mencatat user agent, IP, dan timestamp mikrodetik.

**Instruksi**:
Rancang arsitektur data persistence Eloquent yang menggabungkan:
1. Custom Eloquent Builder dengan atomic conditional updates.
2. Penggunaan Read-Replica Lag bypass mechanism.
3. Transaksi berbasis savepoint yang mengisolasi reservasi kuota dan pembuatan payment token, di mana kegagalan payment token tidak membatalkan reservasi tiket, melainkan memicu state transition ke `RESERVATION_PENDING_PAYMENT`.
*Tuliskan kode lengkap kelas Model, Migration, Custom Builder, dan Transaction Service tanpa menggunakan Raw SQL query murni secara langsung (tetap pertahankan abstraksi Eloquent).*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda / Konseptual Cepat)
1. **Mengapa method `Relation::enforceMorphMap()` sangat disarankan untuk dipasang pada environment produksi?**
   - A. Untuk mengaktifkan caching query secara otomatis.
   - B. Untuk memutus keterikatan database dengan Full Qualified Class Name (FQCN) namespace PHP code dan menghemat ukuran memori indeks.
   - C. Untuk mengubah seluruh query polymorphic menjadi inner join.
   - D. Untuk menghindari keharusan membuat migrations file.

2. **Apa yang secara internal dilakukan Eloquent saat method `setRawAttributes($attributes, sync: true)` dipanggil?**
   - A. Menjalankan query update langsung ke PostgreSQL.
   - B. Memasukkan raw data ke array internal `$attributes` sekaligus menyalinnya identik ke array `$original`.
   - C. Meng-enkripsi seluruh field yang bertipe data string.
   - D. Menghapus seluruh cache observer.

3. **Perbedaan mendasar antara `chunk(100)` dan `cursor()` pada model Eloquent adalah:**
   - A. `chunk()` membaca seluruh tabel sekaligus ke RAM, sedangkan `cursor()` hanya mengambil 1 data.
   - B. `chunk()` melakukan paginasi berbasis limit-offset query, sedangkan `cursor()` menggunakan PHP Generator berbasis unbuffered query PDO stream.
   - C. `cursor()` hanya bisa digunakan pada koneksi database PostgreSQL.
   - D. `chunk()` tidak mendukung closure callback function.

4. **Bagaimana Laravel menangani pemanggilan `$model->isDirty()` secara internal?**
   - A. Mengirim query SELECT ke database untuk memeriksa status terkini.
   - B. Membandingkan kesamaan nilai secara rekursif antara array internal `$attributes` dengan array `$original`.
   - C. Menghitung checksum MD5 dari file PHP Model.
   - D. Memeriksa log event database MySQL.

5. **Apa fungsi utama interface `Illuminate\Contracts\Database\Eloquent\CastsAttributes`?**
   - A. Untuk melakukan sanitasi query SQL dari injeksi hacker.
   - B. Mengubah representasi data mentah database menjadi tipe data/objek domain saat dibaca (`get`) dan sebaliknya saat disimpan (`set`).
   - C. Menentukan relasi foreign key secara otomatis.
   - D. Mempercepat eksekusi database migration index.

---

#### Bagian 2: Intermediate (Analisis Kode & Mekanika Engine)
6. **Perhatikan cuplikan berikut:**
   ```php
   DB::transaction(function () {
       $order = Order::find(1);
       DB::transaction(function () use ($order) {
           $order->update(['status' => 'PROCESSING']);
           throw new Exception("Payment Gateway Timeout");
       });
   });
   ```
   **Apa yang terjadi pada row `$order` di database MySQL jika exception tertangkap atau gagal?**
   - A. Kolom status berubah menjadi 'PROCESSING' karena transaksi dalam sudah di-commit duluan.
   - B. Laravel memicu `ROLLBACK TO SAVEPOINT trans2`, namun jika outer exception tidak ditangani, outer transaction membatalkan seluruh perubahan (Rollback penuh).
   - C. Database terkunci secara permanen (deadlock state).
   - D. Laravel secara default menolak nested closure transaction dan melempar `LogicException`.

7. **Mengapa menambahkan Global Scope pada Parent Model pada pola Single Table Inheritance (STI) bisa menimbulkan kerentanan bug jika kita memanggil method `replicate()`?**
   - A. Karena query clone akan mematikan koneksi primary key.
   - B. Karena global scope otomatis menambahkan query constraint `WHERE type = 'X'`, yang bisa membatasi validasi mutasi data jika object diubah tipenya sebelum persistensi.
   - C. Replicate tidak memvalidasi casts.
   - D. Karena `replicate()` berjalan via Raw PDO statement.

8. **Kapan instance model memicu event `retrieved`?**
   - A. Saat method `new` dipanggil di memory.
   - B. Tepat setelah data selesai dihidrasi dari raw query result via builder (`newFromBuilder`).
   - C. Sebelum query SQL dikirimkan ke driver PDO.
   - D. Saat query compiler selesai mengonversi SQL string.

9. **Jika method `withoutGlobalScope()` dipanggil pada Custom Query Builder, bagian pipeline mana yang dimodifikasi?**
   - A. File konfigurasi `database.php`.
   - B. Property internal `$scopes` array pada instance `Eloquent\Builder` di mana constraint closure target dihapus dari query execution tree.
   - C. Indeks fisik pada schema tabel database.
   - D. Database read-replica pool connection.

10. **Apa resiko menggunakan `$touches` property pada relasi hierarki yang dalam (deep nested models) di traffic tinggi?**
    - A. Memori PHP bocor karena circular reference.
    - B. Cascade update timestamp memicu serangkaian lock query individual yang memperlambat I/O transaksi dan meningkatkan drastis peluang terjadinya deadlocks.
    - C. Laravel mematikan transaction isolation level secara sepihak.
    - D. Format tanggal otomatis berubah menjadi UNIX timestamp integer.

---

#### Bagian 3: Real-World Enterprise Production Scenarios
11. **Skenario Kasus 1: Replikasi Lag & Read-After-Write Consistency**
    Sebuah aplikasi marketplace menggunakan cluster multi-database (1 Primary Master untuk Write, 3 Replica Nodes untuk Read). 
    Seorang customer melakukan checkout, lalu secara instan dialihkan ke halaman `/order/{id}`. Seringkali halaman menampilkan `404 Not Found` padahal data berhasil dipersistensi di Primary. Namun setelah browser di-refresh 1 detik kemudian, data muncul.
    
    *Pertanyaan Kasus:*
    Mekanisme internal Eloquent apa yang harus dikonfigurasi pada level connection/model untuk mengeliminasi issue replikasi lag ini tanpa memindahkan seluruh read traffic ke Primary Master? Jelaskan trade-off dari solusi tersebut!

12. **Skenario Kasus 2: Polymorphic Memory Overhead pada Heavy Data Pipelines**
    Perusahaan Anda memiliki worker background job yang mengekstrak 2.000.000 record dari tabel `notifications` yang memiliki relasi polymorphic `notifiable` (bisa mengarah ke `User`, `Company`, atau `Vendor`).
    Worker mengalami Out Of Memory (`OOM Killed`) pada offset ke-50.000 meskipun sudah menggunakan `chunk(5000)`. Saat diinspeksi via profiling APM, penggunaan memori tidak pernah turun di akhir setiap chunk cycle.
    
    *Pertanyaan Kasus:*
    Identifikasi 2 penyebab utama mengapa memori tidak terbebaskan pada siklus hidrasi polimorfik Eloquent tersebut, dan tuliskan pendekatan rekonstruksi pipeline kueri untuk menstabilkan konsumsi RAM di bawah 50 MB!

13. **Skenario Kasus 3: Phantom Reads & Model Race Condition pada Status Transition**
    Dalam sistem perbankan terdistribusi, dua worker memproses webhook yang sama secara simultan untuk mengubah status entitas `Disbursement` dari `PENDING` ke `APPROVED` dan `REJECTED`. 
    Implementasi awal menggunakan:
    ```php
    $disbursement = Disbursement::find($id);
    if ($disbursement->status === 'PENDING') {
        $disbursement->status = $request->newStatus;
        $disbursement->save();
    }
    ```
    Kedua worker membaca status `PENDING` pada mikrodetik yang sama, mengeksekusi transisi status yang saling bertentangan, dan mencatat audit log yang korup.
    
    *Pertanyaan Kasus:*
    Bagaimana mendesain ulang lapisan persistensi model ini menggunakan kombinasi **Custom Query Builder**, **Pessimistic Locking**, dan **Atomic SQL Constraints** agar transisi status memiliki garansi idempotensi absolut? Tuliskan potongan kode refactoring-nya!

---

### Kunci Jawaban & Pembahasan Evaluasi

#### Bagian 1 & 2
1. **B** — Morph Maps mengisolasi arsitektur kode dari skema data dan memotong footprint storage pada index composite.
2. **B** — `setRawAttributes` mengisi atribut mentah sekaligus menyamakan state `$original` agar model dalam kondisi 'clean' (`isDirty() === false`).
3. **B** — `chunk()` memakai multiple queries dengan limit & offset, sementara `cursor()` mempertahankan socket PDO unbuffered stream aktif melalui PHP Generator, memangkas alokasi array.
4. **B** — Eloquent melakukan komparasi nilai skalar/objek antara array internal `$attributes` terhadap array copy `$original`.
5. **B** — Interface tersebut adalah kontrak dua arah: `get` mendeserialisasi data storage mentah ke domain value object, dan `set` mengonversi domain value object kembali ke tipe penyimpanan database.
6. **B** — Transaksi tersarang Laravel menggunakan database savepoint (`SAVEPOINT trans2`). Rollback pada sub-transaksi me-rollback savepoint lokal, dan exception yang naik membatalkan outer transaction via standard ACID rollback.
7. **B** — Global scope menyuntikkan query builder constraint otomatis yang bisa membatasi mutasi identitas state baru saat mereplikasi struktur instance.
8. **B** — Hook event `retrieved` ditembakkan segera setelah instance dibuat via `newFromBuilder()` dan data mentah terpasang.
9. **B** — Scope closure dicopot dari registry query builder internal sebelum SQL dikompilasi oleh compiler grammar.
10. **B** — Menghidupkan `$touches` secara rekursif memicu kaskade update timestamp per record individual. Ini mengunci banyak baris secara acak dan memperbesar frekuensi database lock wait timeouts / deadlocks.

#### Bagian 3: Pembahasan Skenario Kasus Produksi
11. **Pembahasan Skenario 1**:
    *Solusi*: Aktifkan fitur **Sticky Connections** di `config/database.php` pada koneksi MySQL: `'sticky' => true`. 
    *Mekanisme*: Saat opsi ini aktif, jika di dalam satu siklus lifecycle request HTTP yang sama telah dieksekusi query mutasi (INSERT/UPDATE/DELETE), Laravel secara otomatis mengarahkan seluruh query SELECT berikutnya di lifecycle tersebut ke Master Database node, mengabaikan Read Replicas.
    *Alternatif Level Query*: Gunakan method `$order = Order::onWriteConnection()->findOrFail($id);` secara eksplisit pada controller endpoint pembacaan detail instan.
    *Trade-off*: Beban query SELECT pada Master DB akan sedikit meningkat pasca-aksi penulisan, namun konsistensi data terjamin instan tanpa bug 404 akibat replikasi delay (Eventual Consistency gap).

12. **Pembahasan Skenario 2**:
    *Penyebab OOM*: 
    1. Penggunaan `chunk()` mengakibatkan degradasi performa I/O karena `OFFSET` yang semakin dalam, dan memicu penumpukan circular reference pada query log jika database query logging aktif (`DB::enableQueryLog()`).
    2. Eloquent Event Dispatcher mereferensikan instance model yang lama di memory, dan garbage collector (Zend Engine GC) terhambat membersihkan polymorphic relation cache jika terdapat circular links pada relationship relations.
    *Solusi Arsitektur*:
    - Nonaktifkan Query Logging: `DB::disableQueryLog()`.
    - Ganti `chunk()` menjadi `LazyCollection` via `cursor()` atau `chunkById()` menggunakan batch processing yang mengeksekusi model hydration secara bergantian.
    - Panggil `unset($model)` dan jalankan `gc_collect_cycles()` secara deterministik setiap 1.000 iterasi.
    - Jika hanya butuh parsing data murni tanpa domain invariant, bypass Eloquent dan gunakan `DB::table('notifications')->cursor()`.

13. **Pembahasan Skenario 3**:
    *Solusi*: Ubah kode menjadi operasi atomic conditional update melalui Custom Query Builder yang terproteksi Pessimistic Write Lock (`FOR UPDATE`), atau atomic conditional where statement.
    ```php
    // Implementasi Idempotent State Transition
    final class AtomicDisbursementService
    {
        public function transitionStatus(string $id, string $expectedOldStatus, string $newStatus): bool
        {
            return DB::transaction(function () use ($id, $expectedOldStatus, $newStatus) {
                // Kunci baris data di level storage engine
                $disbursement = Disbursement::query()
                    ->where('id', $id)
                    ->lockForUpdate()
                    ->first();

                if (! $disbursement || $disbursement->status !== $expectedOldStatus) {
                    // State sudah berubah secara simultan oleh proses lain, gagalkan secara aman
                    return false;
                }

                $disbursement->status = $newStatus;
                $disbursement->save();

                return true;
            });
        }
    }
    ```
    Alternatif direct single-statement atomic update (paling efisien):
    ```php
    $affected = Disbursement::query()
        ->where('id', $id)
        ->where('status', 'PENDING') // Conditional atomic constraint
        ->update(['status' => $newStatus]);

    if ($affected === 0) {
        throw new TransitionAbortedException("Invalid transition state or race condition occurred.");
    }
    ```

---

### 16. Summary

1. **Hydration Engine**: Memahami alur `PDO -> Connection -> Builder -> hydrate() -> newFromBuilder()` adalah garis demarkasi antara junior developer dan Enterprise Systems Architect. Gunakan Eloquent saat domain invariants, validasi tipe, dan siklus hidup relasional mutlak diperlukan; bypass Eloquent menuju raw streaming unbuffered cursors saat memproses throughput masif.
2. **Polymorphic Safety**: String FQCN adalah *technical debt* laten di database relasional. Penggunaan `Relation::enforceMorphMap()` memastikan integritas struktural database terisolasi dari refaktorisasi namespace kode PHP.
3. **Advanced Composability**: Logika kueri bukan milik model, melainkan milik Domain Query Builders. Mengekstrak scope ke dalam Custom Eloquent Builder menghasilkan basis kode yang *type-safe*, elegan, dan modular.
4. **Resiliency in Concurrency**: Pengetahuan mendalam mengenai nested savepoints, pessimistic row locking (`lockForUpdate`), dan determinisme pengurutan entitas adalah fondasi tak tergantikan dalam merekayasa aplikasi finansial berdaya tahan tinggi yang bebas dari race condition dan deadlocks.