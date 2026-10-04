# Bab 06 Module 01: Asynchronous Processing, Queues & Distributed Tasks

---

## 01. Identitas Modul
* **Track:** Backend and Database Engineering
* **Kategori:** 04-Backend-and-Database
* **Framework:** Laravel 11.x / 12.x
* **Topik:** Asynchronous Processing, Queues & Distributed Tasks
* **Tingkat Kesulitan:** Advanced / Production-Grade
* **Prasyarat:** Pemahaman arsitektur MVC Laravel, Service Container, Redis Fundamentals, Database Transactions, dan CLI Automation.

---

## 02. Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
1. Menganalisis dan mengidentifikasi *bottleneck* I/O blocking pada siklus Request-Response HTTP, serta memindahkannya ke sistem eksekusi asinkron.
2. Mengonfigurasi, mengelola, dan mengoptimalkan *queue drivers* (Database, Redis, SQS) pada level kernel aplikasi.
3. Mengimplementasikan mekanisme kontrol eksekusi tingkat lanjut: *Rate Limiting*, *Job Throttling*, *Idempotency Keys*, *Exponential Backoff*, dan *Dead Letter Queues (DLQ)*.
4. Menerapkan pola *Job Chaining*, *Batching*, *Dynamic Distribution*, dan *Worker Auto-scaling* menggunakan Laravel Horizon.
5. Membangun strategi pemantauan, mitigasi *memory leak*, dan pengujian otomatis berbasis *Mocking Queue Engine*.

---

## 03. Concept Map Diagram ASCII

```
+-------------------------------------------------------------------------------+
|                             HTTP REQUEST CYCLE                                |
|  [Client] ---> (Fast Response < 50ms) <--- [HTTP Controller]                  |
+---------------------------------------------------|---------------------------+
                                                    | Dispatch (Payload + Meta)
                                                    v
+-------------------------------------------------------------------------------+
|                            QUEUE BROKER / STORAGE                             |
|  +---------------------+   +---------------------+   +---------------------+  |
|  |   Redis (Cluster)   |   |   Amazon SQS / AMQP |   |  Database (Fallback)|  |
|  +----------+----------+   +----------+----------+   +----------+----------+  |
+-------------|-------------------------|-------------------------|-------------+
              |                         |                         |
              +-------------------+     |     +-------------------+
                                  |     |     |
                                  v     v     v
+-------------------------------------------------------------------------------+
|                       DISTRIBUTED WORKER PROCESSES                            |
|                                                                               |
|  +--------------------------------+       +--------------------------------+  |
|  | Worker 1 (Queue: high-priority)|       | Worker 2 (Queue: default)      |  |
|  | - Lock Acquisition (Atomic)    |       | - Middleware: RateLimited      |  |
|  | - Job Execution (Sandbox)      |       | - Exponential Backoff Retries  |  |
|  | - Horizon Heartbeat / Metrics  |       | - Batch Callback Management    |  |
|  +--------------------------------+       +--------------------------------+  |
|                 |                                         |                   |
|                 +--------------------+--------------------+                   |
|                                      |                                        |
|             [Success]                v                [Exhausted Max Retries] |
|                 |             +--------------+                   |            |
|                 v             | State Update |                   v            |
|       [Acknowledge & Delete]  +--------------+          [Dead Letter Queue]   |
|                               (Database/S3/API)         [failed_jobs Table]   |
+-------------------------------------------------------------------------------+
```

---

## 04. Mengapa Relevan
Pada arsitektur monolitik modern maupun *microservices*, latensi siklus HTTP adalah penentu utama *throughput* dan *user experience*. Operasi seperti pembuatan berkas PDF, enkripsi data massal, komunikasi API pihak ketiga (misal: Payment Gateway, Webhooks, Transaksi Notifikasi), dan agregasi metrik analytics tidak boleh dieksekusi secara sinkron di dalam *thread* Web Server (PHP-FPM/Nginx).

Mengabaikan pemrosesan asinkron mengakibatkan *thread exhaustion*, *HTTP 504 Gateway Timeout*, dan kerentanan terhadap lonjakan beban (*traffic spikes*). Sistem antrean (*queues*) terdistribusi mengisolasi beban kerja komputasi tinggi ke *background workers*, mengubah operasi *blocking* I/O menjadi eksekusi deterministik yang terisolasi, resilien, dan terukur.

---

## 05. Anatomi Konsep Inti

```
+--------------------------------------------------------------------+
|                         ANATOMI SEBUAH JOB                         |
|                                                                    |
|  +--------------------------------------------------------------+  |
|  | 1. State & Payload: Models, Data Transfer Objects (DTO)      |  |
|  |    (Serialized via SerializesModels & InteractsWithQueue)    |  |
|  +--------------------------------------------------------------+  |
|  | 2. Execution Strategy: $tries, $backoff, $timeout, $maxExceptions|
|  +--------------------------------------------------------------+  |
|  | 3. Middleware Layer: RateLimiting, Idempotency Locks         |  |
|  +--------------------------------------------------------------+  |
|  | 4. Handler Method: handle(Dependencies via DI Container)     |  |
|  +--------------------------------------------------------------+  |
|  | 5. Failure Protocol: failed(Throwable $exception)            |  |
|  +--------------------------------------------------------------+  |
+--------------------------------------------------------------------+
```

### 1. Serialization Engine & Model Binding (`SerializesModels`)
Laravel tidak melakukan serialisasi terhadap seluruh *memory footprint* dari Eloquent Model yang dikirim ke *Job*. Trait `SerializesModels` hanya mengekstrak Nama Kelas (*Class Name*) dan *Primary Key Identifier*. Saat Worker mengeksekusi *Job*, model di-hidrasi ulang dari basis data via `Eloquent\Model::findOrFail()`. Jika entitas telah dihapus sebelum *Job* dieksekusi, `ModelNotFoundException` dapat dipicu kecuali `$deleteWhenMissingModels = true` diaktifkan.

### 2. Driver Engine: Redis vs. SQS vs. Database
* **Database Driver:** Menggunakan *row-locking* (`SELECT ... FOR UPDATE`). Menimbulkan *database contention* pada beban > 200 jobs/sec. Hanya direkomendasikan untuk *development* atau beban sangat rendah.
* **Redis Driver:** Menggunakan *Redis In-Memory Key-Value & Lua Scripts* untuk memastikan operasi antrean bersifat atomik (`LPUSH`, `RPOPLPUSH` / `ZADD`). Sangat cepat, memiliki latensi sub-milidetik, mendukung metrik *real-time* dengan Laravel Horizon.
* **Amazon SQS:** Antrean berbasis *fully managed cloud service*. Sangat terukur, tetapi memiliki latensi I/O network lebih tinggi pada setiap *poll* dan payload dibatasi hingga 256 KB.

### 3. Worker Lifecycle & Memory Isolation
Proses `php artisan queue:work` adalah proses *long-running daemon*. Berbeda dengan siklus hidup PHP-FPM konvensional (di mana state memori di-reset per request), state memori pada `queue:work` tetap bertahan antar *Jobs*. Oleh karena itu:
* Static variables tidak di-reset otomatis.
* Kebocoran memori (*memory leaks*) dari circular dependencies harus dimitigasi.
* Konfigurasi `--max-jobs` atau `--max-time` digunakan untuk me-restart *worker* secara berkala.
* Perubahan kode sumber membutuhkan *graceful restart* via `php artisan queue:restart`.

### 4. Idempotency & Concurrency Control
Di lingkungan terdistribusi, prinsip *at-least-once delivery* menjamin bahwa *Job* minimal dikirim satu kali, tetapi berpotensi terduplikasi akibat *network timeout* saat *ACK* (acknowledgement). Pola **Idempotency** memastikan eksekusi ulang *Job* dengan payload yang sama tidak mengubah *state* sistem lebih dari satu kali.

---

## 06. Panduan Implementasi Step-by-Step

### Langkah 1: Konfigurasi Connection & Environment
Ubah driver antrean utama pada berkas `.env`:
```dotenv
QUEUE_CONNECTION=redis
REDIS_CLIENT=phpredis
REDIS_HOST=127.0.0.1
REDIS_PASSWORD=null
REDIS_PORT=6379
REDIS_QUEUE_DB=1
REDIS_CACHE_DB=2
```

Pastikan `config/queue.php` terisolasi dengan baik:
```php
'redis' => [
    'driver' => 'redis',
    'connection' => 'default',
    'queue' => env('REDIS_QUEUE', 'default'),
    'retry_after' => 90, // Waktu tunggu sebelum job dianggap timeout dan di-dispatch ulang
    'block_for' => 5,    // Blocking pop timeout untuk menghemat I/O CPU
    'after_commit' => true, // Dispatch hanya jika DB Transaction berhasil committed
],
```

### Langkah 2: Instalasi dan Konfigurasi Laravel Horizon
```bash
composer require laravel/horizon
php artisan horizon:install
php artisan migrate
```

Konfigurasi `config/horizon.php` untuk membagi beban antrean secara terisolasi:
```php
'environments' => [
    'production' => [
        'supervisor-default' => [
            'connection' => 'redis',
            'queue' => ['high', 'default'],
            'balance' => 'auto',
            'autoScalingStrategy' => 'time',
            'minProcesses' => 3,
            'maxProcesses' => 15,
            'balanceMaxShift' => 2,
            'balanceCooldown' => 3,
            'tries' => 3,
            'timeout' => 60,
        ],
        'supervisor-exports' => [
            'connection' => 'redis',
            'queue' => ['exports', 'reports'],
            'balance' => 'simple',
            'processes' => 2,
            'tries' => 1,
            'timeout' => 300,
            'memory' => 512, // Memori khusus report besar
        ],
    ],
],
```

---

## 07. Contoh Kasus Sederhana

Berikut adalah contoh implementasi pengiriman notifikasi pembaruan profil yang dideferensiasi ke *background processing*.

### 1. Definisi Job Sederhana
```php
<?php

declare(strict_types=1);

namespace App\Jobs;

use App\Models\User;
use App\Mail\ProfileUpdatedMail;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Mail;

final class SendProfileUpdatedNotificationJob implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public int $tries = 3;
    public int $backoff = 10;

    public function __construct(
        public readonly User $user
    ) {}

    public function handle(): void
    {
        Mail::to($this->user->email)->send(new ProfileUpdatedMail($this->user));
    }
}
```

### 2. Dispatching dari HTTP Controller
```php
<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Http\Requests\UpdateProfileRequest;
use App\Jobs\SendProfileUpdatedNotificationJob;
use Illuminate\Http\JsonResponse;

final class ProfileController extends Controller
{
    public function update(UpdateProfileRequest $request): JsonResponse
    {
        $user = $request->user();
        $user->update($request->validated());

        // Dispatch job ke antrean default
        SendProfileUpdatedNotificationJob::dispatch($user)
            ->onQueue('default');

        return response()->json([
            'status' => 'success',
            'message' => 'Profil berhasil diperbarui. Notifikasi sedang diproses.',
        ], 200);
    }
}
```

---

## 08. Implementasi Production-Grade Lengkap Kode

Kasus Produksi: **Pemrosesan Transaksi Finansial dan Rekonsiliasi Eksternal (Distributed Payment Webhook Worker)**. Memerlukan penanganan kegagalan atomik, *distributed locking*, *rate limiting*, dan *dead letter callback*.

```php
<?php

declare(strict_types=1);

namespace App\Jobs;

use App\Exceptions\PaymentGatewayTimeoutException;
use App\Models\Transaction;
use App\Services\PaymentGatewayService;
use Carbon\CarbonInterval;
use Illuminate\Bus\Batchable;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Contracts\Queue\ShouldBeUnique;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\Middleware\RateLimited;
use Illuminate\Queue\Middleware\WithoutOverlapping;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Throwable;

final class ProcessPaymentReconciliationJob implements ShouldQueue, ShouldBeUnique
{
    use Batchable, Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    /**
     * Total percobaan sebelum job dialihkan ke Failed Jobs Table.
     */
    public int $tries = 5;

    /**
     * Jumlah maksimum pengecualian yang tidak tertangani yang diizinkan.
     */
    public int $maxExceptions = 3;

    /**
     * Alokasi batas eksekusi script dalam detik.
     */
    public int $timeout = 45;

    /**
     * Batalkan eksekusi jika model sudah dihapus dari database.
     */
    public bool $deleteWhenMissingModels = true;

    /**
     * Unique ID untuk lock idempotency dispatching (ShouldBeUnique).
     */
    public function uniqueId(): string
    {
        return (string) $this->transactionId;
    }

    /**
     * Durasi unique lock bertahan jika terjadi crash sebelum release.
     */
    public int $uniqueFor = 120;

    public function __construct(
        public readonly int $transactionId,
        public readonly string $idempotencyKey,
        public readonly float $settlementAmount
    ) {
        $this->onQueue('high');
    }

    /**
     * Hitung interval waktu backoff eksponensial (detik).
     *
     * @return array<int, int>
     */
    public function backoff(): array
    {
        return [5, 15, 60, 180, 300]; // Multi-tier backoff delay
    }

    /**
     * Middleware eksekusi job.
     */
    public function middleware(): array
    {
        return [
            // Mencegah job yang sama dieksekusi bersamaan oleh worker yang berbeda
            (new WithoutOverlapping((string) $this->transactionId))
                ->releaseAfter(60)
                ->expireAfter(180),
            
            // Mengontrol throughput ke gateway eksternal (misal: 100 req/min)
            new RateLimited('payment-gateway'),
        ];
    }

    /**
     * Eksekusi core payload.
     */
    public function handle(PaymentGatewayService $gateway): void
    {
        // Evaluasi apakah batch dibatalkan
        if ($this->batch()?->cancelled()) {
            return;
        }

        Log::info('Memulai rekonsiliasi transaksi.', [
            'transaction_id' => $this->transactionId,
            'attempt' => $this->attempts(),
        ]);

        /** @var Transaction $transaction */
        $transaction = Transaction::query()->findOrFail($this->transactionId);

        if ($transaction->isSettled()) {
            Log::warning('Transaksi sudah berstatus settled. Menghentikan eksekusi.', [
                'transaction_id' => $this->transactionId,
            ]);
            return;
        }

        // Eksekusi API eksternal dengan timeout handling
        $gatewayResult = $gateway->verifySettlement(
            idempotencyKey: $this->idempotencyKey,
            amount: $this->settlementAmount
        );

        if ($gatewayResult->isPending()) {
            // Rilis job kembali ke queue dengan delay 30 detik
            $this->release(30);
            return;
        }

        // Database Update diisolasi dalam transaksi database ketat
        DB::transaction(function () use ($transaction, $gatewayResult): void {
            $transaction->lockForUpdate();

            $transaction->update([
                'status' => $gatewayResult->status(),
                'settlement_reference' => $gatewayResult->referenceId(),
                'settled_at' => now(),
            ]);

            $transaction->auditLogs()->create([
                'action' => 'PAYMENT_RECONCILED',
                'payload' => $gatewayResult->toArray(),
            ]);
        });

        Log::info('Rekonsiliasi transaksi berhasil dieksekusi.', [
            'transaction_id' => $this->transactionId,
            'reference' => $gatewayResult->referenceId(),
        ]);
    }

    /**
     * Dead Letter Handler: Dieksekusi jika seluruh rentang $tries gagal.
     */
    public function failed(?Throwable $exception): void
    {
        Log::critical('CRITICAL: Rekonsiliasi pembayaran gagal permanen (Dead Letter).', [
            'transaction_id' => $this->transactionId,
            'idempotency_key' => $this->idempotencyKey,
            'error' => $exception?->getMessage(),
            'trace' => $exception?->getTraceAsString(),
        ]);

        // Tandai status record ke database sebagai REQUIRES_MANUAL_REVIEW
        Transaction::query()
            ->where('id', $this->transactionId)
            ->update([
                'status' => 'FAILED_NEEDS_AUDIT',
                'failure_reason' => $exception?->getMessage(),
            ]);
    }
}
```

---

## 09. Diagram Alur Kerja ASCII

```
[Job Dispatched] 
        |
        v
[Database Commit Check] (after_commit == true)
        |
        +---> (Transaction Rolled Back) ---> [Discard Job]
        |
        +---> (Transaction Committed)
                    |
                    v
[Pushed to Redis (LPUSH)] ---> [Worker Fetches Job via BRPOPLPUSH]
                                        |
                                        v
                            [Acquire Idempotency Lock]
                                        |
                 +----------------------+----------------------+
                 | (Lock Acquired)                             | (Lock Failed)
                 v                                             v
     [Rate Limiter Evaluation]                       [Release to Queue with Delay]
                 |
     +-----------+-----------+
     | (Under Limit)         | (Limit Exceeded)
     v                       v
[Execute handle()]     [Release with Backoff]
     |
     +---> [Success] ---> [Commit DB & Release Locks] ---> [ACK Redis (LREM)]
     |
     +---> [Exception Caught]
                 |
                 v
     [Check Current Attempt < $tries]
                 |
                 +---> (True)  ---> [Calculate Exponential Backoff] ---> [Re-queue Job]
                 |
                 +---> (False) ---> [Trigger failed() Callback] ---> [Move to failed_jobs Table]
```

---

## 10. Analisis Trade-offs

| Pendekatan / Driver | Keuntungan Utama | Kelemahan / Konsekuensi | Skenario Ideal |
| :--- | :--- | :--- | :--- |
| **Database Queue** | Tidak butuh dependensi eksternal, integritas ACID terjamin. | *High contention* pada tabel basis data, tidak efisien untuk beban tinggi (>100 RPS). | MVP, Internal Enterprise App berskala kecil. |
| **Redis Queue + Horizon** | Kecepatan sangat tinggi (In-Memory), latensi sub-milidetik, UI/Metrik lengkap. | Data bersifat *volatile* jika persistence (RDB/AOF) salah konfigurasi; butuh alokasi RAM besar. | Standar emas aplikasi berskala *medium-to-high throughput*. |
| **Amazon SQS** | *Zero infrastructure maintenance*, auto-scaling tak terbatas. | Latensi HTTP polling lebih lambat; *cost per request*; ukuran payload terbatas (256KB). | *Cloud-native architecture*, sistem serverless, sistem skala global. |
| **Synchronous (`sync`)** | Eksekusi instan, mempermudah *local unit testing*. | Memblokir HTTP Worker, rentan terhadap *client timeouts*. | Pengujian unit lokal (*testing environment* saja). |

---

## 11. Best Practices & Antipatterns

### Best Practices
* **Keep Payloads Small:** Jangan mengirim objek besar (misal: binary berkas, raw payload puluhan MB) ke dalam antrean. Simpan berkas ke Object Storage (S3) lalu teruskan path string / reference ID ke *Job*.
* **Use `after_commit`:** Selalu aktifkan `after_commit` pada *dispatched jobs* di dalam *Database Transaction* untuk mencegah *Race Condition* di mana Worker memproses *Job* sebelum data berhasil di-*commit* ke database.
* **Granular Queues Isolation:** Pisahkan *queue names* (`high`, `default`, `low`, `exports`). Jangan biarkan *job* laporan berat memblokir *job* transaksional notifikasi OTP.
* **Deterministic Backoff:** Gunakan array backoff (misal: `[5, 30, 120]`) alih-alih nilai tetap untuk memberikan waktu pemulihan bagi *third-party service*.

### Antipatterns
* **Antipattern: Passing Eloquent Collections directly into constructor.**
  * *Dampak:* Payload serialisasi menjadi raksasa di Redis, berpotensi melebihi batas buffer memori dan *stale state*.
  * *Solusi:* Kirim array IDs dan query ulang secara *chunked* di dalam `handle()`.
* **Antipattern: Memanggil `die()` atau `exit()` di dalam kode Job.**
  * *Dampak:* Menghentikan *Worker Daemon* secara abnormal tanpa melepaskan lock atau mencatat failure status.
* **Antipattern: Long sleep (`sleep(60)`) di dalam Worker.**
  * *Dampak:* Worker terblokir dan tidak dapat memproses *heartbeat*, memicu Horizon menganggap proses mengalami *zombie state* / timeout. Gunakan `$this->release(60)`.

---

## 12. Security Hardening

```
+-------------------------------------------------------------------------+
|                  SECURITY BOUNDARIES IN QUEUE PROCESSING                |
|                                                                         |
|  [Queue Payload]                                                        |
|         |                                                               |
|         +---> (1) Redis In-Transit Encryption (TLS)                     |
|         |                                                               |
|         +---> (2) Authentication & ACL (Redis AUTH / IAM Roles)         |
|         |                                                               |
|         +---> (3) Payload Payload Deserialization Sandboxing            |
|         |                                                               |
|         +---> (4) Sensitive Data Masking (Trait: EncryptedCast/Redact)  |
+-------------------------------------------------------------------------+
```

1. **Redis TLS & Authentication:** Konfigurasikan koneksi Redis menggunakan TLS dan sandi yang kuat (`requirepass`) atau IAM Role jika menggunakan AWS ElastiCache.
2. **Sanitisasi Serialisasi Payload:** Trait `SerializesModels` secara inheren aman jika menggunakan model identifier. Namun, hindari menginstansiasi *untrusted serialized raw PHP objects* (`unserialize()`) yang dapat membuka celah *PHP Object Injection*.
3. **Penyembunyian Data Sensitif:** Jangan pernah menyimpan kredensial plain, data kartu kredit (PAN), atau PII di dalam property publik Job:
```php
final class ProcessUserKycJob implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    // Redact property dari error logs dan serialization
    public function __debugInfo(): array
    {
        return [
            'userId' => $this->userId,
            'idCardNumber' => '***REDACTED***',
        ];
    }
}
```
4. **Isolasi Dashboard Horizon:** Kunci akses Horizon UI via `Horizon::auth` di `AppServiceProvider`:
```php
Horizon::auth(function ($request) {
    return app()->environment('local') || 
           ($request->user() && in_array($request->user()->email, config('auth.superadmins'), true));
});
```

---

## 13. Observabilitas & Debugging

Konfigurasikan integrasi *Log Context* dan Metrik *Queue Monitoring* secara terpusat:

```php
// app/Providers/AppServiceProvider.php
use Illuminate\Support\Facades\Queue;
use Illuminate\Queue\Events\JobProcessed;
use Illuminate\Queue\Events\JobProcessing;
use Illuminate\Queue\Events\JobFailed;
use Illuminate\Support\Facades\Log;

public function boot(): void
{
    Queue::before(function (JobProcessing $event) {
        Log::withContext([
            'queue_job_id' => $event->job->getJobId(),
            'queue_job_name' => $event->job->resolveName(),
            'queue_connection' => $event->connectionName,
        ]);
    });

    Queue::failing(function (JobFailed $event) {
        Log::channel('slack')->critical("Queue Job Gagal: {$event->job->resolveName()}", [
            'connection' => $event->connectionName,
            'queue' => $event->job->getQueue(),
            'exception' => $event->exception->getMessage(),
        ]);
    });
}
```

### Horizon Health Metrics via CLI
Gunakan command bawaan untuk integrasi *monitoring agent* (Datadog/Prometheus):
```bash
# Memeriksa status master horizon daemon
php artisan horizon:status

# Memeriksa throughput dan workload
php artisan horizon:snapshot
```

---

## 14. Benchmarking & Performance

Optimasi throughput worker menggunakan perbandingan parameter eksekusi.

| Flag / Parameter | Standard Mode | Optimized Mode (High-Throughput) | Peningkatan Efisiensi |
| :--- | :--- | :--- | :--- |
| `block_for` | `0` (Aggressive Polling) | `5` (Long Polling) | Penurunan CPU utilization Redis hingga ~70% |
| `balance` | `simple` | `auto` (Dynamic scaling via Horizon) | Distribusi beban adaptif saat traffic spike |
| `memory` | Default `128MB` | Alokasi per worker tipe (64MB - 512MB) | Menghindari OOM tanpa pemborosan RAM |
| `max-jobs` | Unlimited | `1000` | Mencegah kebocoran memori (Memory Leak Protection) |

### Pengujian Beban Antrean (Queue Pushing Benchmark)
```bash
# Menjalankan profiling eksekusi worker
php artisan queue:work redis --queue=high --stop-when-empty --memory=256 --tries=3
```

---

## 15. Hands-on Lab Mini-Project

### Skenario
Bangun pipeline export data pengguna ke file CSV secara asinkron menggunakan *Job Batching*, pelaporan progres *real-time*, dan pengiriman notifikasi via email saat seluruh chunking selesai.

### 1. Definisi Export Chunk Job
```php
<?php

declare(strict_types=1);

namespace App\Jobs;

use App\Models\User;
use Illuminate\Bus\Batchable;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Storage;

final class ExportUserChunkJob implements ShouldQueue
{
    use Batchable, Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public function __construct(
        public readonly int $page,
        public readonly int $chunkSize,
        public readonly string $tempFileName
    ) {
        $this->onQueue('exports');
    }

    public function handle(): void
    {
        if ($this->batch()?->cancelled()) {
            return;
        }

        $users = User::query()
            ->orderBy('id')
            ->forPage($this->page, $this->chunkSize)
            ->get(['id', 'name', 'email', 'created_at']);

        $lines = [];
        foreach ($users as $user) {
            $lines[] = implode(',', [
                $user->id,
                '"' . str_replace('"', '""', $user->name) . '"',
                $user->email,
                $user->created_at->toISOString(),
            ]);
        }

        Storage::disk('local')->append($this->tempFileName, implode("\n", $lines));
    }
}
```

### 2. Orchestrator Service
```php
<?php

declare(strict_types=1);

namespace App\Services;

use App\Jobs\ExportUserChunkJob;
use App\Models\User;
use Illuminate\Bus\Batch;
use Illuminate\Support\Facades\Bus;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;
use Throwable;

final class UserExportOrchestrator
{
    public function execute(string $recipientEmail): Batch
    {
        $chunkSize = 1000;
        $totalRecords = User::query()->count();
        $totalPages = (int) ceil($totalRecords / $chunkSize);
        $fileName = 'exports/users_' . Str::uuid() . '.csv';

        // Tulis header CSV
        Storage::disk('local')->put($fileName, "ID,Name,Email,CreatedAt\n");

        $jobs = [];
        for ($page = 1; $page <= $totalPages; $page++) {
            $jobs[] = new ExportUserChunkJob($page, $chunkSize, $fileName);
        }

        return Bus::batch($jobs)
            ->name('export-users-' . now()->timestamp)
            ->onQueue('exports')
            ->then(function (Batch $batch) use ($fileName, $recipientEmail): void {
                Log::info("Batch {$batch->id} selesai. Berkas siap: {$fileName} untuk {$recipientEmail}");
                // Disini dapat di-dispatch Job untuk kirim email link download
            })
            ->catch(function (Batch $batch, Throwable $e): void {
                Log::error("Batch {$batch->id} gagal dieksekusi: {$e->getMessage()}");
            })
            ->finally(function (Batch $batch): void {
                Log::info("Membersihkan temporary state untuk batch {$batch->id}");
            })
            ->dispatch();
    }
}
```

---

## 16. Automated Testing & Verification

Pengujian arsitektur antrean menggunakan `Queue::fake()` dan `Bus::fake()` untuk memvalidasi interaksi tanpa mengeksekusi I/O fisik.

```php
<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Jobs\ProcessPaymentReconciliationJob;
use App\Models\Transaction;
use App\Services\PaymentGatewayService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Bus;
use Illuminate\Support\Facades\Queue;
use Mockery;
use Tests\TestCase;

final class QueueExecutionTest extends TestCase
{
    use RefreshDatabase;

    public function test_payment_reconciliation_job_is_dispatched_correctly(): void
    {
        Queue::fake();

        $transaction = Transaction::factory()->create([
            'status' => 'PENDING',
        ]);

        // Trigger action
        ProcessPaymentReconciliationJob::dispatch($transaction->id, 'IDEM-12345', 150000.00);

        Queue::assertPushedOn('high', ProcessPaymentReconciliationJob::class);

        Queue::assertPushed(ProcessPaymentReconciliationJob::class, function ($job) use ($transaction) {
            return $job->transactionId === $transaction->id && $job->idempotencyKey === 'IDEM-12345';
        });
    }

    public function test_job_execution_updates_database_state(): void
    {
        $transaction = Transaction::factory()->create([
            'status' => 'PENDING',
        ]);

        $gatewayMock = Mockery::mock(PaymentGatewayService::class);
        $gatewayMock->shouldReceive('verifySettlement')
            ->once()
            ->with('IDEM-999', 50000.00)
            ->andReturn(new class {
                public function isPending(): bool { return false; }
                public function status(): string { return 'SUCCESS'; }
                public function referenceId(): string { return 'REF-EXT-888'; }
                public function toArray(): array { return ['gateway_status' => 'OK']; }
            });

        $this->app->instance(PaymentGatewayService::class, $gatewayMock);

        // Eksekusi Job secara sinkron dalam test environment
        $job = new ProcessPaymentReconciliationJob($transaction->id, 'IDEM-999', 50000.00);
        $job->handle($gatewayMock);

        $this->assertDatabaseHas('transactions', [
            'id' => $transaction->id,
            'status' => 'SUCCESS',
            'settlement_reference' => 'REF-EXT-888',
        ]);
    }
}
```

---

## 17. Troubleshooting Guide

```
+-------------------------------------------------------------+
|                DIAGNOSIS KEGAGALAN WORKER                   |
+-------------------------------------------------------------+
| 1. Worker Tidak Memproses Job?                              |
|    - Cek Queue Name: Apakah worker memonitor nama queue     |
|      yang sama dengan dispatching target?                   |
|    - Cek Horizon Status: 'php artisan horizon:status'       |
|                                                             |
| 2. Job Mengalami Infinite Loop / Ter-dispatch Berulang?     |
|    - Nilai config 'retry_after' < timeout eksekusi Job.     |
|      Solusi: Set 'retry_after' minimal 1.5x lebih besar     |
|      daripada properti $timeout Job.                        |
|                                                             |
| 3. Model Not Found di dalam Worker?                         |
|    - Race Condition: Job di-dispatch sebelum commit DB.     |
|      Solusi: Gunakan after_commit => true.                  |
|                                                             |
| 4. Memory Leak (PHP Fatal Error: Allowed memory exhausted)? |
|    - Worker daemon menumpuk state query log.                |
|      Solusi: Jalankan 'DB::disableQueryLog()' pada boot     |
|      worker atau tambahkan flag --max-jobs=1000.            |
+-------------------------------------------------------------+
```

---

## 18. Checklist Produksi

* [ ] Queue driver dikonfigurasi menggunakan cluster Redis/SQS (bukan `sync` atau `database` untuk high load).
* [ ] Supervisor / Systemd dik