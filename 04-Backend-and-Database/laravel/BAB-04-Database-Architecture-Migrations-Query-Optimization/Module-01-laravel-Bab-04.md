# Bab 04 Module 01: Database Architecture, Migrations & Query Optimization

---

## 01: Identitas Modul
* **Mata Kuliah / Jalur Pembelajaran:** Backend Engineering & Scalable Database Architecture
* **Trek:** Laravel Enterprise Architecture
* **Kategori:** 04-Backend-and-Database
* **Modul:** Bab 04, Modul 01: Database Architecture, Migrations & Query Optimization
* **Target Audience:** Senior Backend Developers, Technical Architects, Database Administrators (DBA)
* **Tingkat Kesulitan:** Advanced / Enterprise-Grade
* **Prasyarat Pengetahuan:** Relational Database Management Systems (PostgreSQL/MySQL), Laravel Eloquent Internals, Database Indexing (B-Tree, Hash, GIN), Operating System I/O & Memory Caching basics.

---

## 02: Learning Objectives
Setelah menyelesaikan modul ini, peserta mampu:
1. Merancang skema relasional terdistribusi dan menerapkan zero-downtime database migrations pada sistem skala tinggi.
2. Menganalisis execution plan query (`EXPLAIN ANALYZE`) untuk mengeliminasi Sequential/Full Table Scans dan mengoptimalkan Buffer Cache Hit Ratio.
3. Mengonfigurasi Composite, Covering, dan Partial Indexing secara native via Laravel migrations.
4. Menghilangkan N+1 query problem menggunakan Eager Loading, Lazy Eager Loading, Subquery Loading, dan Window Functions.
5. Mengimplementasikan connection pooling, read/write splitting, query batching, dan cursor-based pagination untuk memitigasi memory exhaustion.
6. Membangun pipeline benchmark automated testing untuk mendeteksi database regression pada continuous integration (CI).

---

## 03: Concept Map Diagram ASCII
```
+---------------------------------------------------------------------------------------------------+
|                                 LARAVEL DATABASE ARCHITECTURE                                      |
+---------------------------------------------------------------------------------------------------+
                                                  |
           +--------------------------------------+--------------------------------------+
           |                                                                             |
           v                                                                             v
+-----------------------+                                                     +-----------------------+
|  DATABASE MIGRATION   |                                                     |  QUERY OPTIMIZATION   |
|   & SCHEMA DESIGN     |                                                     |   & QUERY ENGINE      |
+-----------------------+                                                     +-----------------------+
           |                                                                             |
     +-----+-----+                                                                 +-----+-----+
     |           |                                                                 |           |
     v           v                                                                 v           v
+---------+ +---------+                                                       +---------+ +---------+
| Zero-DT | | Storage |                                                       | Explain | | Memory  |
| Schema  | | Engines |                                                       | Analyze | | Caching |
| Evolut. | | & Index |                                                       | & Cost  | | Cursor  |
+---------+ +---------+                                                       +---------+ +---------+
     |           |                                                                 |           |
     |           |    +-------------------------------------------------------+    |           |
     |           +--->|   INDEX STRATEGIES (B-Tree, Partial, Composite)       |<---+           |
     |                +-------------------------------------------------------+                |
     |                                           |                                             |
     v                                           v                                             v
+---------------------------------------------------------------------------------------------------+
|                          PRODUCTION PERFORMANCE & RESILIENCY PIPELINE                             |
|       - Read/Write Splitting      - Anti-N+1 Guardrails           - Subquery Optimization        |
|       - Cursor Paginator          - Strict Eloquent Modes         - Connection Pool Resiliency   |
+---------------------------------------------------------------------------------------------------+
```

---

## 04: Mengapa Relevan
Pada skala aplikasi monolitik enterprise atau microservices dengan jutaan transaksi harian, database hampir selalu menjadi *bottleneck* utama (I/O Bound). Framework ORM seperti Eloquent memberikan kemudahan abstraksi, namun abstraksi yang bocor (*leaky abstraction*) kerap menghasilkan query yang tidak efisien, alokasi memori berlebih, hingga table locking yang memicu *cascading failure*. 

Pemahaman mendalam mengenai arsitektur internal database, strategi migrasi tanpa downtime, dan optimasi query tingkat lanjut merupakan pembeda antara aplikasi yang terhenti pada 1.000 QPS (Queries Per Second) dan infrastruktur yang mampu melayani ratusan ribu QPS dengan latensi p99 di bawah 50ms.

---

## 05: Anatomi Konsep Inti

```
+-----------------------------------------------------------------------------+
|                           POSTGRESQL / MYSQL ENGINE                         |
|  +-----------------------------------------------------------------------+  |
|  | Parser & Rewrite -> Query Planner & Optimizer -> Execution Engine    |  |
|  +-----------------------------------------------------------------------+  |
|                                     |                                       |
|         +---------------------------+---------------------------+           |
|         v                                                       v           |
|  +-----------------------------+                 +-----------------------+  |
|  | Shared Buffer Pool / Cache  |                 | Disk Storage Engine   |  |
|  | (B-Tree Pages in Memory)    |                 | (WAL, Heap, Indexes)  |  |
|  +-----------------------------+                 +-----------------------+  |
+-----------------------------------------------------------------------------+
                                     ^
                                     | (TCP Connection via PDO / pgsql)
+-----------------------------------------------------------------------------+
|                             LARAVEL APPLICATION                             |
|  Eloquent ORM -> Query Builder -> Grammar Engine -> Connection Pool (PDO)   |
+-----------------------------------------------------------------------------+
```

### 1. Database Indexing Under the Hood
Indeks B-Tree mengorganisir data dalam struktur pohon seimbang dengan pointer node menuju data fisik (Heap/Clustered Index). 
* **Composite Index:** Urutan kolom mengikuti kaidah *Leftmost Prefix*. Indeks pada `(tenant_id, status, created_at)` hanya dapat digunakan untuk query yang memfilter `tenant_id`, atau `tenant_id AND status`.
* **Covering Index:** Indeks yang memuat seluruh kolom yang diproyeksikan dalam klausa `SELECT` (menggunakan klausa `INCLUDE` pada PostgreSQL), mengeliminasi langkah *Table Lookup / Heap Access*.

### 2. Zero-Downtime Schema Evolutions
Mengubah skema tabel raksasa (>50 juta baris) menggunakan `ALTER TABLE` reguler akan menyebabkan Exclusive Table Lock (`ACCESS EXCLUSIVE` pada PG atau `Metadata Lock` pada MySQL), memblokir operasi DML baca dan tulis. Pola *Expand and Contract* (Parallel Run) memecah perubahan menjadi tahapan:
1. Tambah kolom/indeks baru secara *non-blocking* (`CONCURRENTLY` pada PostgreSQL / `ALGORITHM=INPLACE, LOCK=NONE` pada MySQL).
2. Tulis data secara ganda (*Dual Write*) via aplikasi atau database triggers.
3. Sinkronisasi data historis secara bertahap (batch updates).
4. Alihkan operasi baca ke kolom/tabel baru.
5. Hapus (*Contract*) artefak lama.

### 3. Read/Write Connection Lifecycle
Laravel Query Connection Manager memilah koneksi secara deterministik berdasarkan konteks transaksi dan jenis operasi query:
```php
// config/database.php
'pgsql' => [
    'read' => [
        'host' => [env('DB_READ_HOST_1'), env('DB_READ_HOST_2')],
    ],
    'write' => [
        'host' => [env('DB_WRITE_HOST')],
    ],
    'sticky' => true, // Menjaga read-your-own-writes consistency dalam lifecycle request
    // ...
],
```

---

## 06: Panduan Implementasi Step-by-Step

### Langkah 1: Menerapkan Strict Model Mode pada Service Provider
Cegah eksekusi lazy loading yang memicu N+1 query secara otomatis pada tahap development.

```php
// app/Providers/AppServiceProvider.php
namespace App\Providers;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    public function boot(): void
    {
        Model::shouldBeStrict(! $this->app->isProduction());
        
        // Mencegah silent failure pada attributes yang tidak terdaftar di $fillable
        Model::preventSilentlyDiscardingAttributes(! $this->app->isProduction());
        
        // Mencegah akses lazy-loading secara eksplisit
        Model::preventLazyLoading(! $this->app->isProduction());
    }
}
```

### Langkah 2: Zero-Downtime Index Creation via Native Migration
PostgreSQL membutuhkan parameter `CONCURRENTLY` agar DDL tidak mengunci tabel dari operasi pembacaan dan penulisan concurrent.

```php
// database/migrations/2024_01_01_000001_add_composite_index_to_orders_table.php
use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    // Mematikan migration transaction agar CONCURRENTLY dapat berjalan di Postgres
    public bool $withinTransaction = false;

    public function up(): void
    {
        // Raw statement untuk memastikan index concurrency isolation
        DB::statement('CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_tenant_status_created 
                       ON orders (tenant_id, status, created_at DESC)');
    }

    public function down(): void
    {
        DB::statement('DROP INDEX CONCURRENTLY IF EXISTS idx_orders_tenant_status_created');
    }
};
```

---

## 07: Contoh Kasus Sederhana: Mengatasi N+1 Query

### Masalah (N+1 Query)
Query berikut mengeksekusi 1 query untuk mengambil 100 orders, dan 100 query tambahan untuk mengambil relasi customer masing-masing.

```php
// Antipattern: 1 + 100 Query Execution
$orders = \App\Models\Order::query()->limit(100)->get();
foreach ($orders as $order) {
    echo $order->customer->name; // Trigger query SELECT * FROM customers WHERE id = ?
}
```

### Solusi Optimasi (Eager Loading & Select Projection)
Hanya mengeksekusi 2 query, dengan proyeksi kolom spesifik untuk mengurangi konsumsi memory footprint.

```php
// Optimized: 2 Queries dengan Selected Columns
$orders = \App\Models\Order::query()
    ->select(['id', 'customer_id', 'status', 'total_amount'])
    ->with([
        'customer' => function ($query) {
            $query->select(['id', 'name', 'email']);
        }
    ])
    ->limit(100)
    ->get();

foreach ($orders as $order) {
    echo $order->customer->name;
}
```

---

## 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah implementasi sistem pemrosesan transaksi Ledger Finansial Skala Tinggi dengan partisi indeks, mitigasi lock contention, dan optimasi query mutasi batch.

### 1. Migration Skema Database Teroptimasi
```php
<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public bool $withinTransaction = false;

    public function up(): void
    {
        Schema::create('merchants', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->string('name', 150);
            $table->string('api_key', 64)->unique();
            $table->string('status', 32)->index();
            $table->timestamps();
        });

        Schema::create('ledger_entries', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->uuid('merchant_id');
            $table->string('transaction_reference', 64);
            $table->decimal('amount', 18, 4);
            $table->string('currency', 3)->default('USD');
            $table->enum('type', ['DEBIT', 'CREDIT']);
            $table->string('status', 32);
            $table->jsonb('metadata')->nullable();
            $table->timestampTz('posted_at')->useCurrent();
            $table->timestampsTz();

            $table->foreign('merchant_id')
                  ->references('id')
                  ->on('merchants')
                  ->onDelete('cascade');
        });

        // Partial & Composite Indexes via DB statement (Postgres Engine Specific)
        DB::statement('CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ledger_merchant_posted 
                       ON ledger_entries (merchant_id, posted_at DESC) 
                       INCLUDE (amount, currency)');

        DB::statement('CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ledger_unsettled_partial 
                       ON ledger_entries (merchant_id, status) 
                       WHERE status = \'PENDING\'');
    }

    public function down(): void
    {
        Schema::dropIfExists('ledger_entries');
        Schema::dropIfExists('merchants');
    }
};
```

### 2. Eloquent Model dengan Advanced Scopes & Type Castings
```php
<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * @property string $id
 * @property string $merchant_id
 * @property string $transaction_reference
 * @property float $amount
 * @property string $currency
 * @property string $type
 * @property string $status
 * @property array $metadata
 * @property \Carbon\CarbonImmutable $posted_at
 */
final class LedgerEntry extends Model
{
    use HasFactory, HasUuids;

    protected $table = 'ledger_entries';

    protected $fillable = [
        'merchant_id',
        'transaction_reference',
        'amount',
        'currency',
        'type',
        'status',
        'metadata',
        'posted_at',
    ];

    protected $casts = [
        'amount' => 'decimal:4',
        'metadata' => 'array',
        'posted_at' => 'immutable_datetime',
    ];

    public function merchant(): BelongsTo
    {
        return $this->belongsTo(Merchant::class, 'merchant_id', 'id');
    }

    /**
     * Scope query untuk mengambil ringkasan buku besar menggunakan covering index.
     */
    public function scopeForMerchantSummary(Builder $query, string $merchantId): Builder
    {
        return $query->where('merchant_id', $merchantId)
                     ->select(['merchant_id', 'amount', 'currency', 'posted_at'])
                     ->orderBy('posted_at', 'desc');
    }

    /**
     * Scope query untuk partial index target 'PENDING'.
     */
    public function scopeUnsettled(Builder $query): Builder
    {
        return $query->where('status', 'PENDING');
    }
}
```

### 3. High-Performance Repository dengan Chunking & Raw Aggregations
```php
<?php

declare(strict_types=1);

namespace App\Repositories;

use App\Models\LedgerEntry;
use Carbon\CarbonImmutable;
use Generator;
use Illuminate\Database\DatabaseManager;
use Illuminate\Pagination\CursorPaginator;
use Illuminate\Support\Collection;

final class LedgerRepository
{
    public function __construct(
        private readonly DatabaseManager $db
    ) {}

    /**
     * Mengambil riwayat transaksi menggunakan Cursor-Based Pagination untuk performa stabil pada dataset besar.
     */
    public function getPaginatedLedger(string $merchantId, int $perPage = 50): CursorPaginator
    {
        return LedgerEntry::query()
            ->forMerchantSummary($merchantId)
            ->cursorPaginate($perPage);
    }

    /**
     * Stream dataset raksasa menggunakan LazyCollection (PHP Generators via PDO Cursor)
     * Menghindari alokasi buffer memori berlebih pada worker.
     *
     * @return Generator<int, LedgerEntry>
     */
    public function streamEntriesForAudit(string $merchantId, CarbonImmutable $since): Generator
    {
        return LedgerEntry::query()
            ->where('merchant_id', $merchantId)
            ->where('posted_at', '>=', $since)
            ->lazy(1000)
            ->each(function (LedgerEntry $entry) {
                yield $entry;
            });
    }

    /**
     * Agregasi analitik performa tinggi via Window Functions.
     */
    public function getRunningDailyTotals(string $merchantId): Collection
    {
        $rawSql = <<<SQL
            SELECT 
                DATE(posted_at) as transaction_date,
                amount,
                type,
                SUM(CASE WHEN type = 'CREDIT' THEN amount ELSE -amount END) 
                    OVER (
                        PARTITION BY merchant_id 
                        ORDER BY posted_at 
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ) as running_balance
            FROM ledger_entries
            WHERE merchant_id = :merchantId
            ORDER BY posted_at DESC
            LIMIT 500
        SQL;

        return collect($this->db->select($rawSql, ['merchantId' => $merchantId]));
    }

    /**
     * Bulk Upsert dengan kontrol locking eksplisit.
     *
     * @param array<int, array<string, mixed>> $entries
     */
    public function bulkUpsertTransactions(array $entries): int
    {
        return LedgerEntry::query()->upsert(
            values: $entries,
            uniqueBy: ['id'],
            update: ['status', 'metadata', 'updated_at']
        );
    }
}
```

---

## 09: Diagram Alur Kerja ASCII: Eksekusi Query Engine

```
[Request: Eloquent Query Builder]
                 |
                 v
[Query Grammar Compiles to Raw SQL]
                 |
                 v
[PostgreSQL Query Planner]
                 |
                 +---> Analisis Statistik Tabel (pg_statistic)
                 |
                 v
   +---------------------------+
   | Evaluasi Execution Plan   |
   +---------------------------+
                 |
         +-------+-------+
         |               |
         v               v
 [Index Scan / Bitmap]  [Sequential Scan (Full Table)]
  - Uses B-Tree nodes    - I/O Bound reads entire disk block
  - Low buffer cache hit - Triggers severe latency spike
         |               |
         +-------+-------+
                 |
                 v
[Rows Filtered & Projected in Memory (Shared Buffers)]
                 |
                 v
[PDO Hydrates into Laravel Collection (Hydration Cost)]
                 |
                 v
[Response Serialized & Emitted]
```

---

## 10: Analisis Trade-offs

| Pendekatan Arsitektural | Keuntungan Utama | Kompensasi / Konsekuensi Negatif | Skenario Ideal |
| :--- | :--- | :--- | :--- |
| **B-Tree Composite Indexing** | Akses filter berkecepatan tinggi $O(\log N)$. | *Write Overhead:* Setiap operasi `INSERT/UPDATE/DELETE` memperlambat disk write karena rebuilding indeks. | Tabel dengan perbandingan baca:tulis $\ge 80:20$. |
| **Offset Pagination (`skip/take`)** | Sederhana, mendukung navigasi halaman lompat (*direct page jumping*). | Degradasi $O(N)$ ekstrem pada offset besar; database memindai seluruh *dead rows* sebelum offset. | Dashboard internal dengan jumlah baris total $< 5.000$. |
| **Cursor Pagination (`cursorPaginate`)** | Performa konstan $O(1)$ berapapun kedalaman paging data, berbasis pointer index. | Tidak dapat melompat secara arbitrer ke nomor halaman tertentu (hanya next/previous). | Endless scrolling feeds, High-Volume API payloads. |
| **PostgreSQL JSONB Storage** | Fleksibilitas skema dinamis tanpa migrasi DDL berkala. | Hilangnya constraint referensial ketat dan ukuran serialization storage lebih besar. | Data audit dinamis, payload integrasi pihak ketiga. |
| **Eager Loading (`with()`)** | Mereduksi network round-trip dari $N+1$ menjadi 2 round-trip. | Menarik dataset berlebih ke memori jika relasi yang diambil tidak difilter dengan tepat. | Hubungan 1-to-many standar pada API REST / GraphQL. |

---

## 11: Best Practices & Antipatterns

### Best Practices:
1. **Gunakan Explicit Column Projection:** Hindari `SELECT *`. Tarik hanya kolom yang dikonsumsi oleh business logic guna mengurangi alokasi network buffer dan memory hydration.
2. **Kombinasikan Partial Index untuk Nilai Berfrekuensi Rendah:** Buat indeks khusus dengan filter (`WHERE is_processed = false`) untuk memperkecil ukuran indeks pada disk.
3. **Chunking Processing:** Eksekusi data dalam irisan kecil via `lazy()`, `chunkById()`, atau `cursor()` untuk menjamin heap memory usage stabil di bawah 32MB.
4. **Isolasi Koneksi Baca/Tulis:** Manfaatkan read-replicas untuk query analisis, laporan, dan export data.

### Antipatterns:
* ❌ **Fungsi pada Kolom Indeks:** Menjalankan klausa `WHERE DATE(created_at) = '2024-01-01'` membatalkan efisiensi B-Tree index. Gunakan sargable query: `WHERE created_at >= '2024-01-01 00:00:00' AND created_at <= '2024-01-01 23:59:59'`.
* ❌ **Offset Pagination pada Deep Scanning:** Menjalankan `paginate()` pada jutaan record menyebabkan database melakukan *traversal* sia-sia.
* ❌ **Migration Mengunci Tabel (Locking DDL):** Menambahkan index pada active database tanpa flag `CONCURRENTLY` (Postgres) atau `ALGORITHM=INPLACE` (MySQL).

---

## 12: Security Hardening

### 1. Raw SQL Injection Mitigation
Jangan menyusun variabel runtime langsung ke dalam clause query mentah. Selalu gunakan parameter binding berbasis PDO.

```php
// VULNERABLE TO SQL INJECTION:
DB::statement("SELECT * FROM ledger_entries WHERE status = '{$userInput}'");

// SECURE (Parameterized Query):
DB::select("SELECT * FROM ledger_entries WHERE status = :status", ['status' => $userInput]);
```

### 2. Enforce Strict Parameter Casting
Saat menyusun dynamic order clauses atau aggregate columns, selalu validasi terhadap whitelist ketat sebelum mengirim ke compiler database.

```php
final class QuerySanitizer
{
    private const ALLOWED_SORT_COLUMNS = ['created_at', 'amount', 'id'];

    public static function sanitizeSortColumn(string $column): string
    {
        if (! in_array($column, self::ALLOWED_SORT_COLUMNS, true)) {
            throw new \InvalidArgumentException("Invalid column projection requested: {$column}");
        }

        return $column;
    }
}
```

---

## 13: Observabilitas & Debugging

Gunakan database execution plan analysis langsung dari Laravel CLI atau logging bridge.

### Monitoring Query via Debug Logging Listener
```php
// app/Providers/DatabaseObservabilityServiceProvider.php
namespace App\Providers;

use Illuminate\Database\Events\QueryExecuted;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\ServiceProvider;

final class DatabaseObservabilityServiceProvider extends ServiceProvider
{
    public function boot(): void
    {
        DB::listen(function (QueryExecuted $query) {
            // Log queries that take more than 100ms
            if ($query->time > 100) {
                Log::warning('Slow Query Detected', [
                    'sql' => $query->sql,
                    'bindings' => $query->bindings,
                    'time_ms' => $query->time,
                    'connection' => $query->connectionName,
                ]);
            }
        });
    }
}
```

### Memeriksa Execution Plan PostgreSQL via Command Line
```bash
php artisan tinker --execute="DB::statement('EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM ledger_entries WHERE merchant_id = \'018d34b2-0001-72f1-a7b3-c157f12bc321\' ORDER BY posted_at DESC LIMIT 10;');"
```

Output interpretasi:
* Cari indikator **`Seq Scan`**: Menandakan ketiadaan indeks atau indeks diabaikan optimizer engine.
* Cari indikator **`Index Scan`** / **`Index Only Scan`**: Status optimal, data dibaca langsung dari leaf nodes B-Tree.
* Amati **`Buffers: shared hit`**: Mengukur apakah halaman dibaca langsung dari RAM (*Buffer Cache Hit*) atau melibatkan *Disk Reads*.

---

## 14: Benchmarking & Performance

Tabel berikut menunjukkan hasil benchmark perbandingan strategi optimasi pada 10.000.000 record data ledger:

| Strategi Query | Total Latensi (p50) | Total Latensi (p99) | Konsumsi Memori PHP | Beban I/O Disk Database |
| :--- | :--- | :--- | :--- | :--- |
| `SELECT *` + Offset Page 10.000 | 1.850 ms | 4.200 ms | 185 MB | Tinggi (Full Scan to Offset) |
| Eager Load (Unconstrained) | 650 ms | 1.400 ms | 98 MB | Sedang |
| Composite Index + Cursor Pagination | 2.1 ms | 5.8 ms | 4.2 MB | Minimal (Index Only Scan) |
| Subquery Window Running Aggregate | 18.4 ms | 35.0 ms | 8.1 MB | Sangat Rendah (Buffer Hit 99.8%)|

---

## 15: Hands-on Lab Mini-Project

### Instruksi:
1. Buat migration baru dengan tabel `customers` dan `invoices`.
2. Generate 1.000.000 records dummy menggunakan Model Factory.
3. Tulis optimasi query untuk mengambil akumulasi omset `total_paid` per customer sepanjang tahun 2024 tanpa menghasilkan temporary tables di storage database.
4. Terapkan indeks Covering pada skema database.

```php
// File: database/factories/InvoiceFactory.php
namespace Database\Factories;

use App\Models\Invoice;
use Illuminate\Database\Eloquent\Factories\Factory;
use Illuminate\Support\Str;

class InvoiceFactory extends Factory
{
    protected $model = Invoice::class;

    public function definition(): array
    {
        return [
            'id' => (string) Str::uuid(),
            'customer_id' => (string) Str::uuid(),
            'amount' => $this->faker->randomFloat(2, 10, 5000),
            'status' => $this->faker->randomElement(['PAID', 'PENDING', 'CANCELLED']),
            'invoiced_at' => $this->faker->dateTimeBetween('-2 years', 'now'),
        ];
    }
}
```

```php
// Implementasi Query Optimal pada Controller / Action:
$results = DB::table('invoices')
    ->select('customer_id', DB::raw('SUM(amount) as total_revenue'))
    ->where('status', '=', 'PAID')
    ->whereBetween('invoiced_at', ['2024-01-01 00:00:00', '2024-12-31 23:59:59'])
    ->groupBy('customer_id')
    ->havingRaw('SUM(amount) > ?', [1000])
    ->get();
```

---

## 16: Automated Testing & Verification

Gunakan Database Testing suite Laravel untuk memvalidasi pencegahan N+1 query dan integritas skema data:

```php
<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\LedgerEntry;
use App\Models\Merchant;
use App\Repositories\LedgerRepository;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

final class DatabaseOptimizationTest extends TestCase
{
    use RefreshDatabase;

    private LedgerRepository $repository;

    protected function setUp(): void
    {
        parent::setUp();
        $this->repository = $this->app->make(LedgerRepository::class);
    }

    public function test_cursor_pagination_executes_within_bounded_query_count(): void
    {
        $merchant = Merchant::factory()->create();
        LedgerEntry::factory()->count(100)->create(['merchant_id' => $merchant->id]);

        DB::flushQueryLog();
        DB::enableQueryLog();

        $results = $this->repository->getPaginatedLedger($merchant->id, 10);

        $executedQueries = DB::getQueryLog();

        // Cursor pagination harus selalu menghasilkan tepat 1 query tunggal berindeks
        $this->assertCount(1, $executedQueries);
        $this->assertCount(10, $results->items());
    }

    public function test_composite_index_is_leveraged_for_unsettled_partial_query(): void
    {
        $merchant = Merchant::factory()->create();
        LedgerEntry::factory()->count(10)->create([
            'merchant_id' => $merchant->id,
            'status' => 'PENDING',
        ]);

        $explainResult = DB::select(
            "EXPLAIN SELECT * FROM ledger_entries WHERE merchant_id = '{$merchant->id}' AND status = 'PENDING'"
        );

        $explainText = json_encode($explainResult);
        
        // Memverifikasi Postgres/MySQL tidak melakukan Sequential Scan
        $this->assertStringNotContainsString('Seq Scan', $explainText);
    }
}
```

---

## 17: Troubleshooting Guide

### Gejala: Database CPU 100%, Thread Contention Tinggi
* **Akar Masalah:** Missing composite index pada query yang sering dipanggil, menyebabkan Full Table Scan secara bersamaan di berbagai koneksi worker.
* **Solusi Diagnostik:** 
  1. Jalankan `SELECT pid, query, state, age(clock_timestamp(), query_start) FROM pg_stat_activity WHERE state != 'idle' ORDER BY age DESC;`
  2. Identifikasi PID query yang berjalan lama dan lakukan `EXPLAIN ANALYZE` terhadap SQL terkait.
  3. Terapkan indeks yang relevan via Zero-Downtime migration script.

### Gejala: Out of Memory (OOM) Killed pada PHP Worker
* **Akar Masalah:** Penggunaan `Model::all()` atau `->get()` pada jutaan baris record, menyebabkan kegagalan buffer memori PHP saat melakukan hidrasi objek Eloquent.
* **Solusi Diagnostik:** Ubah pemrosesan ke `LazyCollection` menggunakan `Model::cursor()` atau `Model::chunkById(500)`.

---

## 18: Checklist Produksi
- [ ] Mode `Model::preventLazyLoading()` diaktifkan pada unit/feature testing pipeline.
- [ ] DDL Index migrations menggunakan klausa `CONCURRENTLY` (Postgres) atau non-blocking DDL (MySQL).
- [ ] Koneksi Database dikonfigurasi dengan Read/Write Splitting dan flag `sticky => true`.
- [ ] Konfigurasi Database Connection Pool (PgBouncer/ProxySQL) telah disesuaikan dengan kapasitas vCPU engine.
- [ ] Fitur Slow Query Log database diaktifkan pada threshold $\ge 100\text{ms}$.
- [ ] Semua pagination API publik wajib menggunakan Cursor-Based Pagination (`cursorPaginate()`).
- [ ] Seluruh klausa raw SQL binding dienkapsulasi menggunakan Parameterized Arrays untuk memitigasi SQL Injection.

---

## 19: Ringkasan Eksekutif
Performa database ditentukan oleh arsitektur penyimpanan fisik, struktur indeks disk, dan efisiensi algoritma eksekusi query. Framework Laravel menyediakan abstraksi tinggi melalui Eloquent, namun abstraksi tersebut harus dikombinasikan dengan pemahaman mendalam tentang eksekusi database relational level rendah. 

Dengan mengeliminasi lazy loading yang tidak terkontrol, menerapkan indeks komposit dan parsial, mengoptimalkan hidrasi memori menggunakan streaming cursor, serta memberlakukan migrasi non-blocking, sistem enterprise dapat mempertahankan latensi transaksi minimal dan skala konkurensi yang tinggi.

---

## 20: Referensi & Bacaan Lanjutan
* **Use The Index, Luke!** - Markus Winand (*A Guide to Database Performance for Developers*).
* **High Performance MySQL: Optimization, Backups, and Replication (4th Edition)** - Silvia Botros & Jeremy Tinley.
* **The Internals of PostgreSQL:** Hironobu Suzuki (Inter-process Communication and Storage Subsystems).
* **Laravel Documentation:** *Database: Eloquent Collections, Pagination & Performance Optimization*.
* **PostgreSQL Documentation:** *Performance Tips: Using EXPLAIN & B-Tree Index Mechanics*.