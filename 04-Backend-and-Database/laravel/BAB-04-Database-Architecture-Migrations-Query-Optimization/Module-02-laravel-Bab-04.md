# BAB 04: Database Architecture, Migrations & Query Optimization
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengonfigurasi dan mengoperasikan arsitektur database multi-node (*Read/Write Splitting*) dengan mitigasi *replication lag* secara deterministik pada Laravel.
- Menerapkan metodologi migrasi skema tanpa henti (*Zero-Downtime Schema Migration*) menggunakan pola *Expand/Contract* (Parallel Run) pada sistem bertransaksi tinggi.
- Menguasai teknik query optimization tingkat lanjut: implementasi *Covering Index*, *Composite Indexing rule-of-thumb*, pemanfaatan *Common Table Expressions* (CTE), dan *Window Functions* melalui Query Builder.
- Memitigasi risiko *lock contention* dan *deadlock* melalui pemilihan strategi konkurensi yang tepat (*Pessimistic vs. Optimistic Locking*) pada engine InnoDB/PostgreSQL.
- Menganalisis alokasi memori runtime dan throughput I/O pada pemrosesan dataset masif menggunakan `lazy()`, `cursor()`, dan *Keyset Pagination* (bukan *Offset Pagination*).

---

### 2. Prerequisite
- Pemahaman mendalam tentang Laravel Service Container, Service Providers, dan Eloquent ORM fundamental.
- Penguasaan engine database relasional (MySQL 8.0+ InnoDB atau PostgreSQL 14+ MVCC).
- Penguasaan dasar perintah DDL, DML, transaksi ACID (`BEGIN`, `COMMIT`, `ROLLBACK`), serta tingkat isolasi transaksi (*Transaction Isolation Levels*).
- Docker dan Docker Compose untuk orkestrasi klaster database lokal.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Siklus Hidup Database Connection & PDO Instance di Laravel
Laravel mengabstraksi koneksi database melalui class `Illuminate\Database\DatabaseManager`. Ketika sebuah model Eloquent atau Query Builder dieksekusi:

```
[Eloquent / DB Facade] 
       │
       ▼
[DatabaseManager] ──(resolve connection name)──► [ConnectionFactory]
                                                        │
                                                        ▼
                                                [PDO Instance (Lazy)]
                                                        │
                                                        ▼
                                            [Driver-specific Connection]
                                        (MySqlConnection / PostgresConnection)
```

1. **Lazy Connection Resolution**: Laravel tidak langsung membuka koneksi soket TCP ke host database saat aplikasi menerima request. Inisialisasi PDO ditunda (*deferred*) hingga query pertama dieksekusi.
2. **Read/Write Splitting Internals**: Saat opsi `read` dan `write` didefinisikan dalam `config/database.php`, `ConnectionFactory` membuat dua instance PDO terpisah (atau satu jika host sama): satu untuk *reader* (biasanya load balanced via round-robin DNS / HAProxy / AWS Aurora Read Endpoint) dan satu untuk *writer* (Primary/Master node).
3. **Sticky Context (Replication Lag Mitigation)**: Jika opsi `'sticky' => true` diaktifkan, Laravel mencatat dalam memori siklus request berjalan: jika ada satu operasi DML (Write) yang terjadi, semua operasi `SELECT` berikutnya dalam siklus request yang sama akan dialihkan secara paksa ke koneksi *write*. Hal ini mencegah anomali *Read-Your-Own-Writes* yang disebabkan oleh asinkronnya replikasi binlog/WAL antar-node.

#### B. Anatomi Memory-Safe Data Streaming
Dalam pemrosesan data berjumlah jutaan baris:
- `Model::all()` atau `DB::table()->get()`: Mengalokasikan array PHP utuh ke dalam memori. Mengambil 100.000 row hydration Eloquent dengan 20 kolom dapat menghabiskan >300 MB RAM, berisiko memicu `Fatal Error: Allowed memory size exhausted`.
- `DB::table()->chunk($count, $callback)`: Membagi query menggunakan SQL `LIMIT` dan `OFFSET`. Masalah: Kompleksitas $O(N)$ pada database engine. `OFFSET 500000 LIMIT 1000` memaksa disk engine memindai 501.000 baris indeks, membuang 500.000 baris pertama, lalu mengembalikan 1.000 baris. Performa terdegradasi secara eksponensial seiring bertambahnya halaman.
- `DB::table()->cursor()` / `Model::lazy()`: Menggunakan **PDO Unbuffered Queries** (pada MySQL: `PDO::MYSQL_ATTR_USE_BUFFERED_QUERY => false`) dipadukan dengan PHP `Generator` (`yield`). Data ditarik satu per satu langsung dari network socket buffer database engine. Memory footprint konstan $O(1)$ di level runtime PHP, terlepas dari apakah ada 10 atau 10.000.000 baris data.

#### C. Mekanisme Locking & Transaksi Concurrency
Engine modern seperti InnoDB menggunakan MVCC (*Multi-Version Concurrency Control*) untuk query baca reguler (*Non-locking Consistent Read*). Namun, untuk operasi mutasi kritis:
- **Pessimistic Locking (`SELECT ... FOR UPDATE` via `lockForUpdate()`)**: Mengakuisisi *Exclusive Lock* (X-lock) pada row index. Transaksi lain yang mencoba membaca dengan lock atau memodifikasi row tersebut akan di-blokir sampai transaksi pertama melakukan `COMMIT` atau `ROLLBACK`.
- **Shared Locking (`SELECT ... LOCK IN SHARE MODE` via `sharedLock()`)**: Mengakuisisi *Shared Lock* (S-lock). Transaksi lain dapat membaca, namun tidak dapat memodifikasi baris tersebut. Rentan terhadap *deadlock* jika dua transaksi bersamaan memegang S-lock kemudian keduanya mencoba menaikkannya menjadi X-lock.
- **Optimistic Locking**: Menggunakan application-level version control (kolom `version` integer atau timestamp). Query validasi dilakukan saat `UPDATE ... WHERE id = :id AND version = :current_version`. Mengeliminasi database-level lock overhead, sangat efisien untuk sistem *read-heavy, low-contention write*.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional / Pemula | Pendekatan Enterprise Production |
| :--- | :--- | :--- |
| **Arsitektur Koneksi** | Single Node DB; writer menangani semua analitik & reporting. | Read/Write Splitting, Dedicated Analytics Read Pool, Dynamic Sticky Connection. |
| **Migrasi Skema** | `php artisan migrate` langsung mengubah tipe kolom atau drop kolom pada tabel 50 juta row (Tabel terkunci / Lock table). | Zero-Downtime Migration: Expand/Contract pattern, Shadow Tables, Online Schema Change (gh-ost/pt-osc). |
| **Pagination** | `paginate($perPage)` standar (`OFFSET / LIMIT`). Query breakdown di page > 1.000. | Keyset (Cursor-based) Pagination via `cursorPaginate()`, memanfaatkan tuple comparison berbasis B-Tree index. |
| **Batch Processing** | `Model::all()` atau `chunkById()` tanpa indexing deterministik. | Unbuffered Cursor via `lazy()` atau `cursor()`, dikombinasikan dengan Keyset chunking. |
| **Data Integrity** | Validasi hanya di level FormRequest Laravel. Race conditions diabaikan. | Two-Phase validation: Database-level strict constraints (Foreign keys, Unique compound) + Transaction Isolation + Distributed Locks / Pessimistic Locks. |

---

### 5. How (Workflow Detail)

#### Implementasi Expand/Contract Migration Pattern
Untuk melakukan perubahan struktural (misal: memecah kolom `name` menjadi `first_name` dan `last_name`, atau mengubah tipe data kolom besar) tanpa downtime:

```
Fase 1: Expand
┌────────────────────────────────────────────────────────┐
│ 1. Buat kolom baru (nullable) via migrasi DDL reguler. │
│ 2. Update kode aplikasi:                               │
│    - WRITE ke kolom lama DAN kolom baru (Dual Write).  │
│    - READ tetap dari kolom lama.                       │
│ 3. Deploy aplikasi.                                    │
└────────────────────────────────────────────────────────┘
                           │
                           ▼
Fase 2: Backfill Data
┌────────────────────────────────────────────────────────┐
│ 1. Jalankan Background Queue Job / Artisan Command     │
│    menggunakan Keyset Cursor untuk memigrasikan data   │
│    lama ke kolom baru secara bertahap.                 │
│ 2. Pastikan replication lag tidak melonjak (Throttling)│
└────────────────────────────────────────────────────────┘
                           │
                           ▼
Fase 3: Switch Read
┌────────────────────────────────────────────────────────┐
│ 1. Update kode aplikasi:                               │
│    - READ dialihkan ke kolom baru.                     │
│    - WRITE tetap berjalan ke kedua kolom.              │
│ 2. Deploy aplikasi. Monitor error logs.                │
└────────────────────────────────────────────────────────┘
                           │
                           ▼
Fase 4: Contract
┌────────────────────────────────────────────────────────┐
│ 1. Update kode: Hapus dependensi ke kolom lama.        │
│    (Hanya write & read ke kolom baru).                 │
│ 2. Deploy aplikasi.                                    │
│ 3. Migrasi DDL terakhir: Drop kolom lama secara aman.  │
└────────────────────────────────────────────────────────┘
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Lalu Lintas Jalan Raya
Bayangkan database sebagai gerbang tol utama kota:
- **Single Connection (Tanpa Splitting)**: Truk tronton kontainer (Query analitik/reporting bulanan) masuk ke loket yang sama dengan sepeda motor kurir ekspres kilat (transaksi checkout pengguna). Antrean mengular, latency melonjak (*Head-of-Line Blocking*).
- **Read/Write Splitting**: Memisahkan gerbang tol logistik (Read Replicas untuk analitik & baca katalog) dari gerbang tol express darurat (Primary node khusus write transaksi).
- **Offset vs Keyset Pagination**:
  - *Offset*: Membaca buku tebal dengan cara membuka halaman dari lembar ke-1 sampai ke-500.000 setiap kali Anda ingin membaca halaman 500.001.
  - *Keyset*: Menggunakan penanda buku fisik (*bookmark*). Langsung membuka lembar tepat setelah ID kartu perpustakaan terakhir yang Anda tandai.

#### Diagram Arsitektur Database Enterprise di Laravel
```
                              ┌───────────────────────────┐
                              │    Laravel Application    │
                              │       (API Node)          │
                              └─────────────┬─────────────┘
                                            │
               ┌────────────────────────────┴───────────────────────────┐
               │                                                        │
          [Write Ops]                                              [Read Ops]
   (INSERT/UPDATE/DELETE/Sticky)                              (SELECT / Analytics)
               │                                                        │
               ▼                                                        ▼
   ┌───────────────────────┐                                ┌───────────────────────┐
   │     Primary Node      │                                │  Read Replica Pool    │
   │      (Read/Write)     │                                │  (Load Balanced)      │
   └───────────┬───────────┘                                └───────────▲───────────┘
               │                                                        │
               │         Binary Log / WAL Replication Stream            │
               └───────────────────(Async / Semi-Sync)──────────────────┘
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Mengaktifkan Read/Write Splitting & Sticky Connection
File: `config/database.php`
```php
<?php

return [
    'default' => env('DB_CONNECTION', 'mysql'),
    'connections' => [
        'mysql' => [
            'driver' => 'mysql',
            'read' => [
                'host' => [
                    env('DB_READ_HOST_1', '10.0.1.11'),
                    env('DB_READ_HOST_2', '10.0.1.12'),
                ],
            ],
            'write' => [
                'host' => [
                    env('DB_WRITE_HOST', '10.0.1.10'),
                ],
            ],
            'sticky'    => true, // Kritis: Mitigasi Replication Lag untuk transaksi sekuensial
            'database'  => env('DB_DATABASE', 'forge'),
            'username'  => env('DB_USERNAME', 'forge'),
            'password'  => env('DB_PASSWORD', ''),
            'charset'   => 'utf8mb4',
            'collation' => 'utf8mb4_unicode_ci',
            'prefix'    => '',
            'strict'    => true,
            'engine'    => 'InnoDB',
            'options'   => [
                PDO::ATTR_EMULATE_PREPARES => false, // Memastikan native prepared statements
                PDO::ATTR_STRINGIFY_FETCHES => false,
                PDO::ATTR_TIMEOUT => 3, // Fail-fast connection timeout
            ],
        ],
    ],
];
```

#### Practical Example: High-Throughput Ledger Transaction Engine
Implementasi mutasi saldo akuntansi dengan *Pessimistic Locking*, penanganan *Deadlock retry*, mitigasi query buffered, dan indeks komposit.

```php
<?php

declare(strict_types=1);

namespace App\Services\Ledger;

use App\Exceptions\InsufficientBalanceException;
use App\Models\Account;
use App\Models\Transaction;
use Illuminate\Support\Facades\DB;
use Psr\Log\LoggerInterface;
use Throwable;

final class BalanceTransferService
{
    private const MAX_TRANSACTION_RETRIES = 5;

    public function __construct(
        private readonly LoggerInterface $logger
    ) {}

    /**
     * Mentransfer dana antar akun secara atomik dengan mitigasi Deadlock.
     *
     * @throws InsufficientBalanceException|Throwable
     */
    public function transfer(int $sourceAccountId, int $targetAccountId, int $amountCents): Transaction
    {
        if ($amountCents <= 0) {
            throw new \InvalidArgumentException("Transfer amount must be positive.");
        }

        // Deterministic Lock Ordering: Hindari Deadlock dengan mengunci ID terendah lebih dulu
        $firstLockId = min($sourceAccountId, $targetAccountId);
        $secondLockId = max($sourceAccountId, $targetAccountId);

        return DB::transaction(function () use ($sourceAccountId, $targetAccountId, $amountCents, $firstLockId, $secondLockId) {
            
            // Akuisisi Pessimistic Exclusive Lock secara terurut
            $firstAccount = Account::where('id', $firstLockId)->lockForUpdate()->firstOrFail();
            $secondAccount = Account::where('id', $secondLockId)->lockForUpdate()->firstOrFail();

            $sourceAccount = ($firstAccount->id === $sourceAccountId) ? $firstAccount : $secondAccount;
            $targetAccount = ($firstAccount->id === $targetAccountId) ? $firstAccount : $secondAccount;

            if ($sourceAccount->balance_cents < $amountCents) {
                throw new InsufficientBalanceException("Account {$sourceAccountId} has insufficient balance.");
            }

            // Eksekusi mutasi matematis
            $sourceAccount->decrement('balance_cents', $amountCents);
            $targetAccount->increment('balance_cents', $amountCents);

            // Buat audit log transaksi (Write-ahead audit log)
            $transaction = Transaction::create([
                'source_account_id' => $sourceAccountId,
                'target_account_id' => $targetAccountId,
                'amount_cents'      => $amountCents,
                'status'            => 'COMPLETED',
                'executed_at'       => now(),
            ]);

            $this->logger->info("Transfer executed successfully", [
                'transaction_id' => $transaction->id,
                'amount' => $amountCents
            ]);

            return $transaction;
        }, self::MAX_TRANSACTION_RETRIES);
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Anomali Checkout Flash-Sale pada Sistem E-Commerce (120.000 Request/Menit)
**Problem Breakdown**:
Pada skenario promo kilat, tabel `inventory_items` dan `orders` mengalami lonjakan *traffic*. Terjadi dua masalah fatal:
1. *Overselling*: 100 stok fisik terjual ke 180 user karena pembacaan stok dilakukan tanpa isolasi level tinggi (Race Condition: dua thread membaca `stock = 1` bersamaan, lalu keduanya lolos validasi dan melakukan `decrement`).
2. *Deadlock Cascading Failures*: Transaksi Order dan Inventory saling mengunci baris data dengan urutan berbeda, membanjiri log MySQL dengan error `1213: Deadlock found when trying to get lock; try restarting transaction`. Hal ini menguras thread pool PHP-FPM, meningkatkan latency API gateway dari 45ms ke 12.000ms (504 Gateway Timeout).

**Solusi Arsitektur**:
1. **Penerapan Keyset Indexing & Strict Composite Index**:
   Tabel `orders` diindeks komposit `(user_id, status, created_at)` untuk mencegah *full index scan* saat pengguna me-refresh halaman status pesanan.
2. **Deterministic Locking Strategy**:
   Semua mutasi multi-item diurutkan berdasarkan `inventory_id ASC` sebelum di-lock via `SELECT ... FOR UPDATE`. Jika Thread A membutuhkan Item 5 dan 10, dan Thread B membutuhkan Item 10 dan 5; kedua thread dipaksa meminta lock Item 5 terlebih dahulu, lalu Item 10. Eliminasi total potensi siklus saling tunggu (*Cyclic Lock Graph*).
3. **Atomic Decrement Pattern**:
   Alih-alih membaca dan memperbarui:
   ```sql
   -- Rentan Race Condition tanpa Lock
   SELECT stock FROM inventories WHERE id = 10;
   UPDATE inventories SET stock = stock - 1 WHERE id = 10;
   ```
   Diubah menjadi atomic direct condition update:
   ```sql
   UPDATE inventories 
   SET stock = stock - 1 
   WHERE id = 10 AND stock >= 1;
   ```
   Pada Laravel:
   ```php
   $affected = DB::table('inventories')
       ->where('id', $productId)
       ->where('stock', '>=', $quantityRequested)
       ->decrement('stock', $quantityRequested);

   if ($affected === 0) {
       throw new OutOfStockException("Stok produk tidak mencukupi.");
   }
   ```
   Eksekusi ini bersandar langsung pada atomisitas single row-lock engine storage database tanpa overhead *read-before-write*.

---

### 9. Trade-offs

```
                       [ Konsistensi Ketat (ACID) ]
                                    ▲
                                   / \
                                  /   \
                                 /     \
                                /       \
                               /         \
  [ Latency Rendah (In-Memory) ]───────────[ Skalabilitas Horizontal ]
```

| Pendekatan | Keuntungan | Biaya / Trade-off |
| :--- | :--- | :--- |
| **Read/Write Splitting** | Skalabilitas baca meningkat linear seiring penambahan read replica node. Primary node terlindungi dari kejenuhan I/O. | Risiko inkonsistensi sementara akibat *replication lag*. Memerlukan routing pintar (`sticky => true`) dan tuning buffer jaringan. |
| **Pessimistic Locking (`lockForUpdate`)** | Menjamin integritas data mutlak; mencegah anomali *double-spending* atau *overselling*. | Throughput menurun drastic. Database thread pool cepat terisi jika durasi transaksi panjang. Risiko *Deadlock* tinggi bila developer tidak disiplin. |
| **Optimistic Locking (Column Versioning)** | Tidak ada database lock; performa tinggi, throughput read/write maksimal. | Memerlukan penanganan kegagalan (*retry logic*) di level aplikasi. Tidak cocok pada skenario persaingan tinggi (*high-contention hotspot*), karena tingkat kegagalan update akan sangat tinggi. |
| **Keyset Pagination vs Offset** | Kecepatan query konstan $O(1)$ berapapun kedalaman halaman (page 1 hingga page 10.000.000 memiliki latency identik). | Tidak mendukung navigasi acak lompat ke halaman tertentu (misal: "Langsung ke Halaman 47"). Hanya mendukung tombol "Next" dan "Previous". |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Melakukan HTTP Call atau Enqueue Job Berat di Dalam Blok Transaksi Database
*Anti-pattern*:
```php
// SALAH: Koneksi database terkunci selama panggilan jaringan pihak ketiga
DB::transaction(function () use ($paymentData) {
    $order = Order::create([...]);
    $paymentResponse = Http::timeout(10)->post('https://api.payment.com/charge', [...]); 
    // Jika API pihak ketiga lag 10 detik, row lock dan koneksi DB ditahan selama 10 detik!
    $order->update(['payment_id' => $paymentResponse['id']]);
});
```
*Solusi*: Jauhkan operasi I/O jaringan non-database dari siklus transaksi DB. Dapatkan token pembayaran lebih dahulu, atau selesaikan mutasi DB lalu tembak HTTP call via background asynchronous queue job.

#### 2. N+1 Problem pada Polimorphic & Dynamic Relationship
*Identifikasi*: Debugbar atau APM menunjukkan puluhan query identik:
```sql
SELECT * FROM comments WHERE post_id = ?;
```
*Solusi*: Selalu manfaatkan Eager Loading dengan *constraint definition* eksplisit:
```php
$posts = Post::with(['comments' => function ($query) {
    $query->select(['id', 'post_id', 'body', 'created_at'])
          ->latest()
          ->limit(5);
}])->paginate(20);
```

#### 3. Kehilangan Indeks akibat SARGable Violation
Jika sebuah kolom diindeks, penggunaan fungsi database pada kolom tersebut akan membatalkan penggunaan B-Tree Index:
```sql
-- NON-SARGable: B-Tree Index pada `created_at` diabaikan, memicu Full Table Scan!
SELECT * FROM orders WHERE DATE(created_at) = '2023-10-01';

-- SARGable: Mengoptimalkan pemanfaatan Index Range Scan
SELECT * FROM orders WHERE created_at >= '2023-10-01 00:00:00' AND created_at <= '2023-10-01 23:59:59';
```
Pada Laravel Eloquent:
```php
// HINDARI
Order::whereDate('created_at', '2023-10-01')->get();

// GUNAKAN
Order::whereBetween('created_at', ['2023-10-01 00:00:00', '2023-10-01 23:59:59'])->get();
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Strict Connection Settings**: Pasang `PDO::ATTR_EMULATE_PREPARES => false` di `config/database.php` untuk parsing native prepared statements dari database engine.
- [ ] **Prevent Destructive Commands**: Tambahkan `DB::prohibitDestructiveCommands($this->app->isProduction())` di `AppServiceProvider::boot()` untuk memblokir perintah fatal seperti `migrate:fresh`, `migrate:reset`, atau `db:wipe` di production.
- [ ] **Indexing Cardinality Check**: Pastikan urutan indeks komposit mengikuti aturan *Equality first, Range second* ($[E, R]$ rule).
- [ ] **Replication Lag Shield**: Pastikan opsi `'sticky' => true` aktif jika sistem menggunakan arsitektur Read Replicas.
- [ ] **Locking Timeout Enforcement**: Tetapkan timeout transaksi eksplisit di level database driver (misal: MySQL `innodb_lock_wait_timeout = 3` detik) untuk memotong antrean lock yang membeku sebelum menenggelamkan pool koneksi.
- [ ] **Keyset Pagination**: Gunakan `cursorPaginate()` untuk endpoint API dengan volume data besar, hindari `paginate()`.
- [ ] **Lazy Hydration**: Gunakan `Model::lazy()` atau `DB::cursor()` pada batch processing untuk menjaga alokasi RAM tetap konstan di level runtime PHP CLI.

---

### 12. Hands-on Practice

Berikut panduan langkah demi langkah implementasi arsitektur database enterprise yang akan disimpan pada direktori target: `hands-on/m02/`.

#### Langkah 1: Siapkan Struktur Proyek
Buat direktori kerja jika belum tersedia:
```bash
mkdir -p hands-on/m02/database/migrations
mkdir -p hands-on/m02/app/Models
mkdir -p hands-on/m02/app/Services
```

#### Langkah 2: Buat Migrasi Zero-Downtime Expand-Contract
Simpan kode berikut di `hands-on/m02/database/migrations/2026_03_30_000001_create_accounts_and_transactions_table.php`:

```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        Schema::create('accounts', function (Blueprint $table) {
            $table->id();
            $table->string('account_number', 64)->unique();
            $table->unsignedBigInteger('balance_cents')->default(0);
            $table->unsignedInteger('lock_version')->default(0); // For Optimistic Lock
            $table->timestamps();

            $table->index(['account_number', 'balance_cents'], 'idx_accounts_lookup');
        });

        Schema::create('transactions', function (Blueprint $table) {
            $table->id();
            $table->foreignId('source_account_id')->constrained('accounts')->cascadeOnDelete();
            $table->foreignId('target_account_id')->constrained('accounts')->cascadeOnDelete();
            $table->unsignedBigInteger('amount_cents');
            $table->string('status', 32);
            $table->timestamp('executed_at');
            $table->timestamps();

            // Composite Index: Covering queries for user transaction history
            $table->index(['source_account_id', 'status', 'executed_at'], 'idx_tx_history_covering');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('transactions');
        Schema::dropIfExists('accounts');
    }
};
```

#### Langkah 3: Implementasi Model Eloquent
Simpan kode model di `hands-on/m02/app/Models/Account.php`:

```php
<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

final class Account extends Model
{
    protected $fillable = [
        'account_number',
        'balance_cents',
        'lock_version',
    ];

    protected $casts = [
        'balance_cents' => 'integer',
        'lock_version' => 'integer',
    ];

    public function outgoingTransactions(): HasMany
    {
        return $this->hasMany(Transaction::class, 'source_account_id');
    }
}
```

Simpan kode model transaksi di `hands-on/m02/app/Models/Transaction.php`:

```php
<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

final class Transaction extends Model
{
    protected $fillable = [
        'source_account_id',
        'target_account_id',
        'amount_cents',
        'status',
        'executed_at',
    ];

    protected $casts = [
        'amount_cents' => 'integer',
        'executed_at' => 'datetime',
    ];

    public function sourceAccount(): BelongsTo
    {
        return $this->belongsTo(Account::class, 'source_account_id');
    }

    public function targetAccount(): BelongsTo
    {
        return $this->belongsTo(Account::class, 'target_account_id');
    }
}
```

#### Langkah 4: Implementasi Window Function & Keyset Pagination pada Repository
Simpan kode berikut di `hands-on/m02/app/Services/TransactionReportingService.php`:

```php
<?php

declare(strict_types=1);

namespace App\Services;

use App\Models\Transaction;
use Illuminate\Contracts\Pagination\CursorPaginator;
use Illuminate\Support\Facades\DB;

final class TransactionReportingService
{
    /**
     * Mengambil riwayat transaksi dengan Keyset Pagination (O(1) memory & speed).
     */
    public function getAccountHistoryCursor(int $accountId, int $perPage = 25): CursorPaginator
    {
        return Transaction::query()
            ->where('source_account_id', $accountId)
            ->where('status', 'COMPLETED')
            ->orderBy('id', 'desc') // Deterministic cursor sorting
            ->cursorPaginate($perPage);
    }

    /**
     * Menghitung Running Total kumulatif menggunakan SQL Window Function.
     */
    public function getRunningBalanceReport(int $accountId): array
    {
        return DB::table('transactions')
            ->select([
                'id',
                'amount_cents',
                'executed_at',
                DB::raw('SUM(amount_cents) OVER (
                    PARTITION BY source_account_id 
                    ORDER BY executed_at, id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) as cumulative_spent_cents')
            ])
            ->where('source_account_id', $accountId)
            ->where('status', 'COMPLETED')
            ->get()
            ->toArray();
    }
}
```

#### Langkah 5: Skrip Uji Concurrency & Memory Test
Simpan kode runner di `hands-on/m02/test_runner.php`:

```php
<?php

require_once __DIR__ . '/../../vendor/autoload.php';

// Bootstrap Laravel Application context
$app = require_once __DIR__ . '/../../bootstrap/app.php';
$kernel = $app->make(Illuminate\Contracts\Console\Kernel::class);
$kernel->bootstrap();

use App\Models\Account;
use App\Services\Ledger\BalanceTransferService;
use Illuminate\Support\Facades\DB;

DB::beginTransaction();
try {
    $acc1 = Account::create(['account_number' => 'ACC-001', 'balance_cents' => 500000]);
    $acc2 = Account::create(['account_number' => 'ACC-002', 'balance_cents' => 100000]);
    DB::commit();
} catch (\Throwable $e) {
    DB::rollBack();
    exit("Setup failed: " . $e->getMessage());
}

$service = app(BalanceTransferService::class);

echo "Memulai transfer aman...\n";
$startMemory = memory_get_usage(true);

$service->transfer($acc1->id, $acc2->id, 50000);

$endMemory = memory_get_usage(true);
echo "Transfer Selesai. Memory delta: " . ($endMemory - $startMemory) . " bytes\n";
echo "Saldo Acc 1: " . $acc1->fresh()->balance_cents . "\n";
echo "Saldo Acc 2: " . $acc2->fresh()->balance_cents . "\n";
```

---

### 13. Exercise

#### Level Easy
Tuliskan sintaks Query Builder Laravel untuk menarik 50 transaksi terakhir yang memiliki status `FAILED`, menggunakan metode `select` eksplisit hanya pada 3 kolom (`id`, `amount_cents`, `created_at`), pastikan indeks `(status, created_at)` digunakan secara optimal, dan gunakan pagination berbasis cursor.
- *Petunjuk*: Gunakan `select()`, `where()`, `orderBy()`, dan `cursorPaginate()`.

#### Level Medium
Buat sebuah class migration migrasi kustom yang memecah kolom `address` (tipe teks tunggal) menjadi `street_address`, `city`, dan `postal_code` pada tabel `merchants` yang memiliki 5 juta baris, menggunakan strategi *Expand-Contract* tanpa mengunci tabel (*Zero-Downtime*). Sertakan perintah artisan migrasi bertahap.

#### Level Hard
Rancang modul ekspor data ledger akuntansi berjumlah 10.000.000 row ke file CSV. Modul harus:
1. Menjaga alokasi RAM tetap konstan di bawah 25 MB di level PHP runtime.
2. Tidak memblokir thread penulisan database (non-blocking read) menggunakan unbuffered PDO stream.
3. Menghitung running balance secara inline per baris menggunakan Window Function SQL tanpa kalkulasi memori PHP.

---

### 14. Challenge

#### Skenario Kasus: High-Frequency Ticket Reservation Engine
Anda ditunjuk sebagai Principal Architect untuk platform tiket konser berskala global. 
- **Beban Puncak**: 80.000 user merebutkan 10.000 tiket yang sama persis dalam rentang 15 detik pertama penjualan dibuka.
- **Kondisi Database**: Cluster Aurora MySQL dengan 1 Primary Writer dan 3 Read Replicas.

**Tugas Anda (Rancang Arsitektur & Pseudocode)**:
1. Buat skema database dan mekanisme reservasi kursi (Hold tiket selama 10 menit).
2. Tentukan bagaimana alur locking dirancang agar Primary Node tidak mati akibat *Thread Pool Saturation* atau *Deadlock Cascade*, dengan tetap menjamin 0% kemungkinan tiket terpesan ganda (*double-booking*).
3. Atasi batasan *Replication Lag* di mana read replica bisa tertinggal 100ms di belakang Primary saat pembacaan ketersediaan kursi dilakukan secara masif oleh pengunjung halaman awal.
4. Tuliskan mitigasi recovery jika proses pembayaran pihak ketiga mati/timeout saat reservasi sedang di-hold.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Basic Questions
1. Mengapa opsi `'sticky' => true` sangat krusial saat mengonfigurasi Read/Write splitting pada Laravel?
2. Apa perbedaan internal yang paling mendasar antara `chunk($size)` dan `cursor()` dalam penggunaan memori PHP?
3. Sebutkan satu skenario di mana B-Tree index pada kolom database gagal digunakan akibat penulisan query pada Query Builder.
4. Apa fungsi dari perintah `DB::prohibitDestructiveCommands()` dan di lingkungan mana perintah ini wajib dijalankan?
5. Mengapa `OFFSET 1000000 LIMIT 10` memiliki latency eksekusi yang jauh lebih buruk dibandingkan `cursorPaginate()`?

#### B. Intermediate Questions
1. Jelaskan bagaimana pengurutan deterministic ID (*Deterministic Lock Ordering*) dapat mengeliminasi potensi terjadinya database deadlock pada transfer dana dua arah!
2. Kapan sebaiknya Anda memilih Optimistic Locking dibandingkan Pessimistic Locking (`lockForUpdate()`)? Jelaskan trade-off throughput-nya.
3. Apa implikasi performa dari pengaturan `PDO::ATTR_EMULATE_PREPARES => false` di tingkat interaksi driver jaringan?
4. Bagaimana cara kerja SQL Window Function `SUM() OVER(PARTITION BY ... ORDER BY ...)` dan mengapa ini lebih efisien dibandingkan agregasi manual via sub-query di Eloquent?
5. Dalam pola Expand-Contract, mengapa penghapusan kolom lama (*Contract Phase*) tidak boleh dilakukan bersamaan pada rilis kode aplikasi baru?

#### C. Skenario Kasus Produksi
1. **Skenario 1**: Database Primary Anda mengalami lonjakan CPU 100% dan Connection Exhaustion (Max Connections Reached). Analisis APM menunjukkan 70% query yang masuk ke node Primary adalah query `SELECT` laporan bulanan yang lambat. Apa akar masalah arsitektur ini di konfigurasi Laravel, dan bagaimana cara memulihkannya secara instan tanpa restart aplikasi?
2. **Skenario 2**: Anda menjalankan background command pembersihan data usang `DB::table('logs')->where('created_at', '<', now()->subDays(90))->delete();`. Tabel `logs` memiliki 40 juta baris. Seketika itu juga seluruh sistem transaksi down karena transaksi baru yang masuk ke tabel `logs` terblokir (*Lock Wait Timeout Exceeded*). Jelaskan apa yang terjadi di level storage engine dan bagaimana seharusnya skrip pembersihan data masif ditulis!
3. **Skenario 3**: Sebuah aplikasi e-commerce menggunakan dua read replica dan satu writer. Seorang user mengedit profilnya, menekan tombol "Simpan", lalu diarahkan kembali (*redirected*) ke halaman detail profil. Pengguna komplain data yang baru saja ia ubah tidak muncul (masih menampilkan data lama), namun jika halaman di-refresh beberapa detik kemudian data baru muncul. Jelaskan penyebab teknis fenomena ini dan tuliskan perbaikan konfigurasinya di Laravel!

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Jawaban A (Basic)
1. **Fungsi Sticky**: Memastikan bahwa jika terjadi operasi mutasi (Write) dalam siklus request yang sama, seluruh pembacaan (Read) berikutnya langsung dialihkan ke node Primary (Writer), mencegah membaca data usang (*stale data*) akibat jeda replikasi (*replication lag*).
2. **Perbedaan Alokasi Memori**: `chunk()` tetap mengambil array kumpulan data ke memori PHP setiap interval offset, sedangkan `cursor()` menggunakan PDO Unbuffered Query dan PHP Generator (`yield`) untuk mengalirkan 1 row data per waktu dari network buffer, menjaga konsumsi RAM konstan $O(1)$.
3. **Penyebab Index Batal**: Menggunakan fungsi database pada kolom berindeks (Non-SARGable query), contoh: `whereYear('created_at', '2023')` atau `whereRaw('UPPER(email) = ?', [$email])`.
4. **Fungsi Prohibit Destructive**: Mencegah eksekusi perintah destruktif skema database (`migrate:fresh`, `db:wipe`, dll.) secara sengaja maupun tidak sengaja di environment `production`.
5. **Kelemahan Offset**: Database engine wajib memindai (*scan*) dan membangun tabel di memori untuk seluruh data dari indeks ke-0 hingga indeks ke-(offset+limit), lalu membuang data sejumlah offset tersebut. Sedangkan Keyset langsung melompat ke posisi baris menggunakan operator komparasi B-Tree (`WHERE id > :last_seen_id LIMIT 10`).

#### Jawaban B (Intermediate)
1. **Deterministic Lock Ordering**: Mencegah *Deadlock* dengan memastikan semua thread bertransaksi meminta *exclusive lock* pada sumber daya dalam urutan yang identik (misal selalu ID terkecil dahulu, `min(id1, id2)`). Hal ini mematahkan kondisi *Circular Wait* (salah satu dari 4 kondisi Coffman penyebab deadlock).
2. **Optimistic Locking Kapan & Trade-off**: Digunakan saat probabilitas persaingan data rendah (*low contention write*), misalnya pembaruan biodata profil user. Keuntungannya: tidak ada database row lock (throughput sangat tinggi). Trade-off: jika ada tabrakan pembaruan, sistem aplikasi harus melempar exception atau meminta user mengulang pengisian formulir.
3. **Implikasi Emulate Prepares = False**: Menjamin keamanan SQL Injection yang lebih absolut karena parsing query dipisahkan secara fisik dari payload parameter di engine database, serta mengembalikan tipe data asli dari kolom engine relasional (misal: integer dikembalikan sebagai integer di PHP, bukan selalu string).
4. **Keunggulan Window Function**: Window Function melakukan kalkulasi agregat dalam satu lintasan pemindaian partisi data (*Single Scan Pass*) di storage engine, tanpa perlu memicu join internal atau sub-query baru yang berulang kali membaca tabel yang sama.
5. **Alasan Fase Contract Terpisah**: Jika kolom di-drop saat rilis kode baru berlangsung, proses *rolling update* server (di mana server A masih menjalankan kode lama dan server B menjalankan kode baru) akan memicu fatal error 500 pada server A karena kolom yang dicari sudah tidak ada lagi di skema fisik.

#### Jawaban C (Skenario Kasus Produksi)
1. **Solusi Skenario 1**:
   - *Akar Masalah*: Konfigurasi Query Builder / Repository membaca langsung ke default connection (Writer), atau query analitik dijalankan di request API yang sama setelah transaksi write tanpa melepas sticky session.
   - *Solusi Cepat*: Paksa query analitik diarahkan eksplisit ke Read Connection Pool menggunakan `DB::connection('mysql::read')->table(...)` atau pisahkan koneksi reporting ke pool database reporting tersendiri dalam `config/database.php`.
2. **Solusi Skenario 2**:
   - *Akar Masalah*: Perintah `DELETE` tanpa batasan limit pada range besar mengunci rentang baris data yang masif (*Gap Lock* dan *Next-Key Lock* pada InnoDB), serta membebani Undo Log secara luar biasa, membekukan operasi DML lain yang menyentuh tabel tersebut.
   - *Solusi Perbaikan*: Lakukan chunking deletion berbasis primary key dengan jeda (sleep) throttling:
     ```php
     do {
         $deleted = DB::table('logs')
             ->where('created_at', '<', now()->subDays(90))
             ->limit(1000)
             ->delete();
         usleep(50000); // 50ms pause untuk memberi ruang worker DML lain
     } while ($deleted > 0);
     ```
3. **Solusi Skenario 3**:
   - *Akar Masalah*: Terjadi fenomena *Replication Lag*. Saat diarahkan via redirect (HTTP Request baru), aplikasi membaca data dari Read Replica yang belum selesai mereplikasi perubahan binary log dari Primary node.
   - *Solusi Perbaikan*: Aktifkan `'sticky' => true` pada driver koneksi di `config/database.php`. Pastikan session state pengguna mempertahankan timestamp mutasi terakhir sehingga middleware dapat mengarahkan read request ke Writer selama beberapa detik pasca-mutasi.

---

### 16. Summary

1. **Database Connection Routing**: Read/Write splitting memproteksi Primary node dari kelelahan I/O, namun menuntut developer mengelola risiko *replication lag* menggunakan fitur `'sticky' => true` atau eksplisit connection targeting.
2. **Zero-Downtime DDL**: Modifikasi skema pada tabel masif wajib mengadopsi metodologi *Expand/Contract* (Dual-Write -> Data Backfilling -> Switch Read -> Contract) untuk mengeliminasi tabel terkunci (*Exclusive Table Locks*).
3. **Concurrency Control**: Gunakan *Deterministic Pessimistic Locking* untuk data finansial/inventaris berkepadatan tinggi guna mengeliminasi race condition dan deadlock. Gunakan *Optimistic Locking* untuk sistem dengan frekuensi tabrakan rendah demi throughput maksimal.
4. **Memory & Query Efficiency**: Hindari *Offset Pagination* pada dataset besar dan gantikan dengan *Keyset (Cursor) Pagination*. Manfaatkan *Unbuffered Queries* (`lazy()`, `cursor()`) dan *Window Functions* untuk pemrosesan jutaan baris tanpa membebani runtime memory PHP.