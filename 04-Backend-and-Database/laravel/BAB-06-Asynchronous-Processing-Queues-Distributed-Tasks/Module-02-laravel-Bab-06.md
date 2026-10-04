# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 06: Asynchronous Processing, Queues & Distributed Tasks**  
**Kategori: 04-Backend-and-Database (Laravel Enterprise)**

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menganalisis *lifecycle* internal dari `Illuminate\Queue\Worker`, *event loop*, dan interaksi *low-level* dengan Redis Engine (struktur data `List`, `ZSet`, dan mekanisme evaluasi skrip Lua).
- Mengimplementasikan pola orkestrasi pemrosesan *distributed tasks* kompleks menggunakan *Job Chaining*, *Job Batching* dengan *dynamic pruning*, serta *Unique Jobs* terisolasi berbasis *distributed lock*.
- Mendesain mekanisme *Fault-Tolerant* dan *Strict Idempotency* untuk mencegah *duplicate execution* pada arsitektur terdistribusi *at-least-once delivery*.
- Mengonfigurasi strategi *Rate Limiting*, *Dynamic Backpressure*, dan mitigasi *worker starvation* pada kluster Laravel Horizon berskala tinggi.
- Mengidentifikasi, mengisolasi, dan merekayasa mitigasi terhadap *memory leaks*, *serialization overhead*, *unhandled worker signals* (SIGTERM/SIGKILL), dan *deadlocks* antrean produksi.

---

## 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Arsitektur Internal PHP-CLI & Process Management**: Pemahaman alokasi memori per-proses PHP, daemons, garbage collection, serta penanganan sinyal UNIX OS (POSIX signals: `SIGTERM`, `SIGINT`, `SIGHUP`).
- **Laravel Framework Core**: Pengetahuan mendalam mengenai Service Container lifecycle, Contextual Binding, Eloquent Lifecycle, dan Event Dispatcher.
- **Redis Core Internals**: Struktur data primitif Redis (`LPUSH`, `RPOPLPUSH`, `BLPOP`, `ZADD`, `ZRANGEBYSCORE`) dan atomisitas transaksi via Redis Lua Scripting.
- **Networking & Distributed Systems Basics**: Konsep *At-Least-Once Delivery*, *Network Partitioning*, *Clock Drift*, dan *Data Consistency*.

---

## 3. Concept & Internal Architecture

### 3.1 Siklus Hidup `Illuminate\Queue\Worker` & Runtime Engine
Worker pada Laravel bukanlah *HTTP Request-Response cycle* yang mati setelah script selesai dieksekusi. Worker adalah proses CLI *long-lived* yang mengeksekusi *infinite loop*:

```
while (true) {
    $job = $this->getNextJob($connection, $queue);
    if ($job) {
        $this->runJob($job, $connection, $options);
    } else {
        $this->sleep($options->sleep);
    }
    $this->stopIfNecessary($options, $status);
}
```

Perbedaan mendasar antara `queue:listen` dan `queue:work`:
- `queue:listen`: Menjalankan instance framework baru untuk setiap job yang dieksekusi melalui sub-proses PHP. Bersifat sangat lambat (*cold boot* framework per job) namun aman dari *memory leaks*.
- `queue:work`: Melakukan *bootstrap* framework satu kali di awal, lalu mengeksekusi job berulang kali dalam satu alokasi *memory footprint* yang sama. Jauh lebih cepat, namun rentan mengalami akumulasi state, *memory leaks*, dan *stale database connections*.

Saat memproses pekerjaan dalam loop `queue:work`:
1. **Memory State Persistence**: Variabel statis, singleton instance dalam service container, dan *in-memory cache* (seperti `DB::getQueryLog()`) tidak di-reset secara otomatis kecuali framework secara eksplisit memicu event `LoopReset` dan memanggil method pembersih (*flush state*).
2. **Database Connection Stabilities**: Koneksi PDO yang idle saat antrean kosong dapat diputus oleh database server (`wait_timeout`). Laravel Worker mengatasinya melalui method `reconnector` internal sebelum eksekusi payload dimulai.

### 3.2 Interaksi Low-Level Redis Driver
Ketika menggunakan driver Redis, Laravel tidak menggunakan satu antrean tunggal, melainkan membagi tugas ke dalam beberapa *key* Redis:
- `queues:{queue_name}`: Berupa Redis `List`. Berisi job yang siap dieksekusi segera (*immediate execution*). Worker mengambil data menggunakan perintah atomik (atau skrip Lua yang membungkus `RPOPLPUSH` / `LMOVE`).
- `queues:{queue_name}:delayed`: Berupa Redis `Sorted Set (ZSet)`. Nilai *Score* merupakan representasi *Unix Timestamp* kapan job diizinkan untuk dipindahkan ke antrean utama. Worker menjalankan skrip Lua secara periodik untuk memindahkan job dari *delayed ZSet* ke antrean *List* utama jika `score <= current_timestamp`.
- `queues:{queue_name}:reserved`: Berupa Redis `Sorted Set (ZSet)`. Menyimpan job yang sedang diproses oleh worker. *Score* adalah `current_timestamp + retry_after`. Jika worker mati mendadak (SIGKILL/OOM), job yang tertahan di *reserved* akan dipindahkan kembali ke *List* utama setelah melampaui batas waktu `retry_after`.
- `queues:{queue_name}:notify`: Berupa Redis `Stream` atau mekanisme `BLPOP` untuk implementasi *blocking pop* guna meminimalkan CPU polling.

### 3.3 Serialisasi Payload dan `SerializesModels`
Ketika fungsi `dispatch(new ProcessTransaction($transaction))` dipanggil:
1. Trait `SerializesModels` mengekstrak kelas target dan properti *primary key* model tersebut (misal: `App\Models\Transaction`, ID: `882194`).
2. Objek Job di-serialize menjadi string JSON berstandar internal Laravel:
   ```json
   {
       "uuid": "99c8f94d-1698-4c8d-8ad4-b4a3a6ad001a",
       "displayName": "App\\Jobs\\ProcessTransaction",
       "job": "Illuminate\\Queue\\CallQueuedHandler@call",
       "maxTries": 3,
       "timeout": 60,
       "data": {
           "commandName": "App\\Jobs\\ProcessTransaction",
           "command": "O:28:\"App\\Jobs\\ProcessTransaction\":1:{s:11:\"transaction\";O:45:\"Illuminate\\Contracts\\Database\\ModelIdentifier\":4:{s:5:\"class\";s:24:\"App\\Models\\Transaction\";s:2:\"id\";i:882194;s:9:\"relations\";a:0:{}s:10:\"connection\";s:5:\"mysql\";}}"
       }
   }
   ```
3. Worker yang mengambil payload ini akan melakukan proses *unserialize*, lalu Service Container melakukan *re-query* ke database: `Transaction::query()->findOrFail(882194)`. 
*Peringatan Arsitektural*: Jika record telah dihapus dari database sebelum worker memproses job, akan terjadi pengecualian `ModelNotFoundException` kecuali trait mengimplementasikan *soft-deletes* atau flag `$deleteWhenMissingModels = true`.

---

## 4. Why & What

### Mengapa Distributed Queue Vital?
Dalam aplikasi enterprise, penundaan eksekusi HTTP tidak dapat ditoleransi. Pemrosesan sinkron terhadap integrasi pihak ketiga (Payment Gateway, Webhook Ingestion, PDF Processing, Fraud Analysis) memicu:
- Peningkatan drastis *Latency Percentile* (p99/p99.9).
- Terjadinya *Cascading Failure* saat downstream service mengalami penurunan performa atau *downtime*.
- Tingginya konsumsi proses web server (seperti PHP-FPM pool exhaustion), yang menyebabkan penolakan *incoming traffic* (HTTP 502/504).

### Apa yang Diselesaikan oleh Queue Architecture Lanjutan?
- **Load Leveling (Spike Arresting)**: Mengubah kurva *traffic spike* ekstrem menjadi aliran beban pemrosesan yang stabil dan konsisten.
- **Strict Decoupling**: Menghapus dependensi temporal antar sistem melalui isolasi komputasi berbasis domain event.
- **Resilience Engine**: Menyediakan jaminan pemrosesan melalui retry strategies eksponensial, *dead-letter queue (DLQ)*, dan mekanisme sirkuit terputus (*circuit breaker*).

---

## 5. How (Workflow Detail)

Alur komprehensif dari *dispatch* hingga penyelesaian atau kegagalan tugas:

```
+---------------------------------------------------------------------------------------+
|                                    PRODUCER (HTTP/CLI)                                |
| 1. Instansiasi Job -> 2. Evaluasi Middleware -> 3. Serialize -> 4. Kirim ke Driver     |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                                    BROKER (REDIS)                                     |
|  Delay > 0?                                                                           |
|    |-- YES --> ZADD queues:name:delayed [timestamp] [payload]                         |
|    +-- NO  --> LPUSH queues:name [payload]                                            |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                                    CONSUMER (WORKER)                                  |
| 1. Memeriksa migrasi Delayed -> Ready via Skrip Lua (ZPOPMIN / ZRANGEBYSCORE)         |
| 2. Eksekusi atomik LMOVE / RPOPLPUSH (Pindah dari List Ready ke ZSet Reserved)        |
| 3. Unserialize Command & Model Rehydration (Ambil record DB via primary key)         |
| 4. Inisialisasi Environment Worker (Timeout timer, signal handlers SIGALRM/SIGTERM)   |
| 5. Eksekusi Job Middleware Stack Pipeline                                             |
| 6. Invoke Job::handle()                                                               |
+---------------------------------------------------------------------------------------+
           |                                                                 |
   [EKSEKUSI SUKSES]                                                 [EKSEKUSI GAGAL]
           |                                                                 |
           v                                                                 v
+-----------------------+                         +-------------------------------------+
| 1. ZREM ZSet Reserved |                         | 1. Tangkap Throwable Exception      |
| 2. DB Commit          |                         | 2. Evaluasi Job::tries & retryUntil |
| 3. Fire JobProcessed  |                         +-------------------------------------+
+-----------------------+                                            |
                                              +----------------------+----------------------+
                                              |                                             |
                                    [Masih Ada Kuota Retry]                     [Batas Retry Habis]
                                              |                                             |
                                              v                                             v
                                  +-----------------------+                     +-----------------------+
                                  | 1. Hitung Backoff     |                     | 1. Job::failed() call |
                                  | 2. ZREM ZSet Reserved |                     | 2. Pindah ke failed_  |
                                  | 3. ZADD ZSet Delayed  |                     |    jobs (DLQ via DB)  |
                                  +-----------------------+                     | 3. ZREM ZSet Reserved |
                                                                                +-----------------------+
```

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem Pos dan Ekspedisi Logistik Terdistribusi
Bayangkan kantor pusat logistik kargo:
- **Client (Producer)**: Pelanggan yang memasukkan formulir dokumen paket ke kotak drop box antrean.
- **Job Payload**: Dokumen tertutup berisi instruksi manifest ("Kirim palet barang ke gudang X, ID barang: #9948").
- **Redis List (Ready Queue)**: Sabuk berjalan (*conveyor belt*) barang siap angkut.
- **Redis ZSet (Delayed/Reserved Queue)**: Area karantina dengan waktu pelepasan terkunci (*time-lock vault*).
- **Worker Process**: Truk ekspedisi khusus yang mengambil satu kontainer, mencatat tanda terima di buku peminjaman (*Reserved*), memproses pengiriman, dan menghapus catatan pinjam setelah sampai di tujuan.
- **Dead-Letter Queue (DLQ)**: Gudang barang rusak/salah alamat yang tidak dapat dikirim setelah 3 kali percobaan untuk diinvestigasi secara manual oleh tim forensik logistik.

### Diagram Arsitektur Multi-Worker & Failover Engine

```
+----------------------------------------------------------------------------------------------------+
|                                    LARAVEL HORIZON ORCHESTRATION                                   |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  Master Supervisor (PID: 1001)                                                                      |
|  ├── Process Monitor & Signal Router (Listens to SIGTERM, SIGCONT)                                 |
|  ├── Auto-scaler Engine (Evaluates queue wait time metrics & workload capacity)                    |
|  │                                                                                                 |
|  ├── Queue Supervisor: default (PID: 1010)                                                         |
|  │   ├── Child Worker [01] (PID: 1011) <---> Redis connection (Pool A)                            |
|  │   ├── Child Worker [02] (PID: 1012) <---> Redis connection (Pool A)                            |
|  │   └── Child Worker [03] (PID: 1013) <---> Redis connection (Pool A)                            |
|  │                                                                                                 |
|  └── Queue Supervisor: critical-financial (PID: 1020)                                              |
|      ├── Dedicated Worker [01] (PID: 1021) <---> Redis Cluster Primary Node                        |
|      └── Dedicated Worker [02] (PID: 1022) <---> Redis Cluster Primary Node                        |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
                                      |                                  ^
                                      v                                  |
+-------------------------------------------------------------+          | Metrics / Heartbeat
|                       REDIS DATA LAYER                      |          |
|  - queues:default (List)                                    |----------+
|  - queues:critical-financial (List)                         |
|  - queues:default:reserved (ZSet)                           |
|  - queues:default:delayed (ZSet)                            |
|  - horizon:masters / horizon:supervisors (Hashes)           |
+-------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### Simple Example: Job Standar dengan Validasi Idempotensi Sederhana
Job dasar yang aman dieksekusi ulang tanpa menyebabkan duplikasi pemrosesan data.

```php
<?php

namespace App\Jobs;

use App\Models\User;
use App\Notifications\WelcomeNotification;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Log;

class SendWelcomeEmailJob implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public int $tries = 3;
    public int $timeout = 30;

    public function __construct(
        public User $user
    ) {}

    public function handle(): void
    {
        // Pengecekan Idempotensi: Jika flag status sudah aktif, hentikan eksekusi
        if ($this->user->welcome_mail_sent_at !== null) {
            Log::info("Idempotency guard: Welcome email already sent to User ID: {$this->user->id}");
            return;
        }

        $this->user->notify(new WelcomeNotification());

        $this->user->updateQuietly([
            'welcome_mail_sent_at' => now(),
        ]);
    }
}
```

### Practical Example: Enterprise Distributed Batch Settlement Job
Implementasi lanjutan dengan *Job Batching*, *Unique Lock*, penanganan *Middleware Rate-Limiting*, dan penanganan *Signal Safety*.

```php
<?php

namespace App\Jobs;

use App\Models\Merchant;
use App\Models\Settlement;
use App\Services\Banking\BankingGatewayClient;
use App\Exceptions\BankingNetworkTransientException;
use Illuminate\Bus\Batchable;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldBeUnique;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\Middleware\RateLimited;
use Illuminate\Queue\Middleware\WithoutOverlapping;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Throwable;

class ProcessMerchantSettlementJob implements ShouldQueue, ShouldBeUnique
{
    use Batchable, Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    /**
     * Alokasi percobaan ulang maksimum.
     */
    public int $tries = 5;

    /**
     * Waktu eksekusi maksimum dalam detik sebelum dipaksa terminasi oleh OS (SIGKILL).
     */
    public int $timeout = 120;

    /**
     * Jumlah detik penguncian уникаль (ShouldBeUnique lock duration).
     */
    public int $uniqueFor = 600;

    public function __construct(
        public Merchant $merchant,
        public string $settlementDate,
        public string $idempotencyKey
    ) {
        $this->onQueue('financial-settlements');
    }

    /**
     * Identifier spesifik untuk Unique Lock pada antrean.
     */
    public function uniqueId(): string
    {
        return "settlement_{$this->merchant->id}_{$this->settlementDate}";
    }

    /**
     * Konfigurasi middleware antrean yang dieksekusi sebelum method handle().
     */
    public function middleware(): array
    {
        return [
            // Membatasi interaksi ke Banking Core Gateway (misal: max 10 calls/detik)
            new RateLimited('bank-core-gateway'),
            
            // Penguncian overlapping berbasis ID Merchant, rilis kunci setelah 120 detik
            (new WithoutOverlapping($this->merchant->id))->expireAfter(120),
        ];
    }

    /**
     * Algoritma Backoff Eksponensial dengan Penambahan Jitter.
     */
    public function backoff(): array
    {
        return [5, 15, 60, 180, 300];
    }

    public function handle(BankingGatewayClient $bankClient): void
    {
        // 1. Periksa apakah batch pembungkus telah dibatalkan
        if ($this->batch()?->cancelled()) {
            Log::warning("Batch cancelled. Aborting settlement for Merchant ID: {$this->merchant->id}");
            return;
        }

        Log::info("Starting settlement for Merchant: {$this->merchant->id}, Date: {$this->settlementDate}");

        // 2. Transaksi Database dengan Pesimistic Locking untuk Idempotency Enforcement
        $settlement = DB::transaction(function () {
            $record = Settlement::where('idempotency_key', $this->idempotencyKey)
                ->lockForUpdate()
                ->first();

            if ($record && $record->status === Settlement::STATUS_COMPLETED) {
                return $record;
            }

            if (!$record) {
                $record = Settlement::create([
                    'merchant_id' => $this->merchant->id,
                    'settlement_date' => $this->settlementDate,
                    'idempotency_key' => $this->idempotencyKey,
                    'status' => Settlement::STATUS_PROCESSING,
                    'amount' => $this->merchant->calculateUnsettledBalance($this->settlementDate),
                    'attempts' => 1,
                ]);
            } else {
                $record->increment('attempts');
            }

            return $record;
        });

        // 3. Early exit jika record telah sukses sebelumnya (Duplicate Delivery Guard)
        if ($settlement->status === Settlement::STATUS_COMPLETED) {
            Log::info("Settlement {$settlement->id} was already completed. Skipping payment dispatch.");
            return;
        }

        // 4. Eksekusi Integrasi API Eksternal
        try {
            $transferReceipt = $bankClient->disburseFunds([
                'reference_no' => $settlement->idempotency_key,
                'destination_account' => $this->merchant->bank_account_number,
                'bank_code' => $this->merchant->bank_code,
                'amount' => $settlement->amount,
            ]);

            // 5. Update Status Final secara Atomik
            DB::transaction(function () use ($settlement, $transferReceipt) {
                $settlement->update([
                    'status' => Settlement::STATUS_COMPLETED,
                    'external_reference' => $transferReceipt->transactionId,
                    'completed_at' => now(),
                ]);
            });

            Log::info("Settlement {$settlement->id} processed successfully.");

        } catch (BankingNetworkTransientException $exception) {
            Log::error("Network issue with Bank Gateway for settlement {$settlement->id}. Retrying...", [
                'error' => $exception->getMessage(),
            ]);

            // Trigger retry melalui pelemparan error ke queue worker engine
            throw $exception;
        }
    }

    /**
     * Penanganan kegagalan permanen setelah seluruh jatah retry habis.
     */
    public function failed(Throwable $exception): void
    {
        Log::critical("Settlement for Merchant {$this->merchant->id} FAILED PERMANENTLY.", [
            'idempotency_key' => $this->idempotencyKey,
            'exception' => $exception->getMessage(),
            'trace' => $exception->getTraceAsString(),
        ]);

        Settlement::where('idempotency_key', $this->idempotencyKey)
            ->update([
                'status' => Settlement::STATUS_FAILED,
                'failure_reason' => substr($exception->getMessage(), 0, 1000),
            ]);
            
        // Trigger alert via pagerduty / slack notification di level enterprise
    }
}
```

---

## 8. Real World Case Study

### Kasus: Flash Sale E-Commerce & Payment Settlement Engine
- **Volume**: 50.000 transaksi/menit pada saat event diskon puncak (Payday Sale).
- **Infrastruktur**: 8 Node Web Server, 1 Redis Cluster (3 Primary, 3 Replica), 10 Dedicated Worker Nodes (eksekusi via Laravel Horizon).

### Titik Kegagalan (Problem Statement):
1. **Worker Starvation**: Antrean notifikasi email/push notification membanjiri antrean utama, sehingga pemrosesan potong saldo (`ProcessLedgerDeduction`) mengalami antrean panjang hingga 45 menit.
2. **Database Connection Exhaustion**: 200 worker proses melakukan instansiasi koneksi langsung ke PostgreSQL Primary instance secara bersamaan, memicu error: `FATAL: remaining connection slots are reserved for non-replication superuser connections`.
3. **Ghost Jobs via SIGKILL**: Kubernetes menembakkan termination timeout (default 30 detik) saat melakukan auto-scaling down worker node, membunuh proses worker di tengah transaksi bank. Hal ini mengakibatkan data transaksi *in-flight* tersangkut di ZSet `reserved` tanpa update DB.

### Solusi Arsitektur Enterprise:
1. **Multi-Queue Routing**: 
   Memisahkan domain antrean secara absolut:
   - `high-financial`: Job pergerakan saldo, batas latensi maks < 2 detik.
   - `inventory-sync`: Job reservasi stok gudang, batas latensi < 5 detik.
   - `low-notifications`: Job email/marketing, batas latensi toleran hingga 1 jam.
2. **Connection Pooling via PgBouncer**:
   Mengarahkan seluruh Laravel Worker ke connection pooler berkonfigurasi *Transaction-Level Pooling*, memangkas pemakaian real connection dari 200 ke 25 koneksi persisten ke DB.
3. **Graceful Worker Draining (K8s & Horizon Lifecycle Sync)**:
   Mengonfigurasi `terminationGracePeriodSeconds: 180` pada pod Kubernetes worker, dan menambahkan hook `preStop` yang menembakkan instruksi: `php artisan horizon:terminate`. Master supervisor berhenti mengambil job baru dari Redis dan menunggu hingga job *in-flight* yang sedang dieksekusi tuntas hingga 120 detik sebelum OS mengirimkan `SIGKILL`.

---

## 9. Trade-offs

| Parameter | Database Queue Driver | Redis Queue Driver | AWS SQS / RabbitMQ |
| :--- | :--- | :--- | :--- |
| **Throughput Capacity** | Rendah (< 500 job/dtk). Terkendala *table lock* & I/O disk. | Sangat Tinggi (> 50.000 job/dtk). Seluruh operasi via *In-Memory*. | Sangat Tinggi (Hampir tak terbatas / Scalable Managed Services). |
| **Processing Latency** | Tinggi (Poll interval query `SELECT ... FOR UPDATE`). | Rendah (Operasi atomik memory & Redis streams notification). | Menengah (Tergantung konektivitas jaringan HTTP REST API/AMQP protocol). |
| **Complexity & Ops** | Sangat Rendah (Menggunakan DB operasional yang sudah ada). | Menengah (Membutuhkan manajemen Redis Cluster, Memory tuning, Sentinel/HA). | Tinggi (Memerlukan setup infrastruktur IAM, VPC Peering, atau konfigurasi AMQP Exchange). |
| **Fault Isolation** | Rendah (Antrean bermasalah dapat menumbangkan basis data utama). | Tinggi (Terisolasi di storage layer terpisah dari sistem DB transactional). | Sangat Tinggi (Sistem queue terpisah total dari compute & database instances). |
| **Fitur Lanjutan (Batch/Horizon)** | Terbatas (Tidak didukung oleh ekosistem Laravel Horizon). | Sempurna (Native integrasi dashboard Horizon, Batch metrics, Auto-tuning). | Terbatas (Harus menggunakan wrapper kustom, tidak ada metrics native Horizon). |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Akumulasi Memory Leak pada Worker Daemon
- **Gejala**: Penggunaan memori worker melonjak dari 40MB menjadi 1GB+ setelah berjalan selama beberapa jam, memicu *Linux OOM Killer*.
- **Penyebab Utama**: Menjalankan profiling query SQL dengan `DB::enableQueryLog()`, menyimpan state besar di *class static variables*, atau menambahkan event listener closure berulang kali tanpa unregister.
- **Solusi**: Matikan query log di lingkungan worker (`DB::disableQueryLog()`). Batasi usia hidup worker via flag `--max-jobs=1000` atau `--max-time=3600`, atau definisikan memory ceiling di Horizon (`memory: 128`).

### 10.2 Model Deserialization Data Drift
- **Gejala**: Worker mengeksekusi data model yang sudah kedaluwarsa atau berbeda statusnya dengan kondisi basis data terkini.
- **Penyebab**: Mengirim objek Model yang sudah dimodifikasi di memory controller tanpa menyimpannya ke DB sebelum dispatch. Worker hanya menerima Primary Key dan akan membaca ulang data dari DB.
- **Solusi**: Selalu lakukan `save()` atau `refresh()` sebelum dispatch, atau kirimkan data primitif (DTO/Array) ke constructor Job daripada binding Active Record Model jika data belum di-persist.

### 10.3 Queue Starvation Akibat Urutan Prioritas Statis
- **Gejala**: Job pada antrean `low` tidak pernah diproses sama sekali.
- **Penyebab**: Menjalankan worker dengan argumen: `queue:work --queue=high,low`. Jika antrean `high` selalu memiliki muatan, worker tidak akan pernah menyentuh antrean `low`.
- **Solusi**: Gunakan pembagian worker pool yang terdedikasi di file `config/horizon.php` dengan alokasi proses minimum untuk masing-masing antrean, atau aktifkan worker balancing strategi: `balance: 'auto'` / `'simple'`.

---

## 11. Best Practices (Production Checklist)

- [ ] **Enforce Strict Idempotency**: Setiap job finansial atau pengubahan state data wajib memiliki verifikasi status database atau skema kunci atomic (`Cache::lock`) sebelum eksekusi logic bisnis.
- [ ] **Implement Exponential Backoff with Jitter**: Hindari penyerangan serentak ke downstream service (*thundering herd problem*) saat service pulih dengan menyusun waktu retry yang memiliki randomisasi waktu tunda.
- [ ] **Avoid Dispatching Inside Uncommitted DB Transactions**: Gunakan method `DB::afterCommit()` saat memanggil job dispatch, untuk mencegah worker membaca data sebelum transaksi database di-commit:
  ```php
  DB::transaction(function () use ($order) {
      $order->save();
      OrderCreatedJob::dispatch($order)->afterCommit();
  });
  ```
- [ ] **Configure Robust Timeout Limits**:
  - Nilai `$timeout` di dalam kelas Job **wajib selalu lebih rendah** daripada konfigurasi `retry_after` di `config/queue.php`.
  - Misal: Jika `$timeout = 60`, maka set `retry_after = 90`. Jika tidak, job yang masih berjalan akan dianggap mati dan diambil oleh worker lain, memicu *duplicate execution*.
- [ ] **Dead-Letter Queue (DLQ) Monitoring**: Pastikan alerting metric aktif untuk tabel `failed_jobs` atau Redis failed list menggunakan Prometheus/Datadog alerting jika lonjakan kegagalan melampaui ambang batas (> 1% dari total throughput).

---

## 12. Hands-on Practice

Buat dan implementasikan modul antrean ini pada direktori: `hands-on/m02/`.

### Langkah 1: Inisialisasi Project & Konfigurasi Horizon
Buka terminal dan navigasikan ke direktori kerja:
```bash
mkdir -p hands-on/m02/ && cd hands-on/m02/
laravel new enterprise-queue-app --no-interaction
cd enterprise-queue-app
composer require laravel/horizon predis/predis
php artisan horizon:install
```

### Langkah 2: Konfigurasi Horizon Environment
Buka `config/horizon.php` dan modifikasi supervisor environments untuk menangani pemrosesan multi-antrean:

```php
'environments' => [
    'production' => [
        'supervisor-financial' => [
            'connection' => 'redis',
            'queue' => ['financial-settlements'],
            'balance' => 'simple',
            'processes' => 10,
            'tries' => 3,
            'timeout' => 90,
        ],
        'supervisor-default' => [
            'connection' => 'redis',
            'queue' => ['default', 'notifications'],
            'balance' => 'auto',
            'autoScalingStrategy' => 'time',
            'minProcesses' => 2,
            'maxProcesses' => 15,
            'balanceMaxShift' => 2,
            'balanceCooldown' => 3,
            'tries' => 3,
            'timeout' => 60,
        ],
    ],
    'local' => [
        'supervisor-local' => [
            'connection' => 'redis',
            'queue' => ['financial-settlements', 'default', 'notifications'],
            'balance' => 'auto',
            'minProcesses' => 1,
            'maxProcesses' => 5,
            'tries' => 3,
        ],
    ],
],
```

### Langkah 3: Setup Tabel Database Migrations
Jalankan migrasi untuk antrean batches dan model data:
```bash
php artisan queue:batches-table
php artisan queue:failed-table
php artisan make:model Settlement -m
```

Buka migration file settlement yang baru dibuat di `database/migrations/` dan sesuaikan skema:
```php
Schema::create('settlements', function (Blueprint $table) {
    $table->id();
    $table->foreignId('merchant_id')->index();
    $table->string('settlement_date');
    $table->string('idempotency_key')->unique();
    $table->string('status')->index();
    $table->decimal('amount', 15, 2);
    $table->unsignedInteger('attempts')->default(0);
    $table->string('external_reference')->nullable();
    $table->text('failure_reason')->nullable();
    $table->timestamp('completed_at')->nullable();
    $table->timestamps();
});
```
Jalankan eksekusi migrasi:
```bash
php artisan migrate
```

### Langkah 4: Implementasi Rate Limiter di `AppServiceProvider`
Buka `app/Providers/AppServiceProvider.php` dan tambahkan limitasi Redis pada method `boot()`:
```php
use Illuminate\Support\Facades\RateLimiter;

public function boot(): void
{
    RateLimiter::for('bank-core-gateway', function ($job) {
        // Izinkan maksimal 5 eksekusi per 10 detik per koneksi
        return \Illuminate\Cache\RateLimiting\Limit::perSeconds(10, 5);
    });
}
```

### Langkah 5: Simulasikan Dispatcher Orchestration via Command
Buat Artisan Command pengujian:
```bash
php artisan make:command SimulateSettlementPipeline
```
Modifikasi `app/Console/Commands/SimulateSettlementPipeline.php`:
```php
<?php

namespace App\Console\Commands;

use App\Jobs\ProcessMerchantSettlementJob;
use App\Models\Merchant;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Bus;
use Illuminate\Support\Str;

class SimulateSettlementPipeline extends Command
{
    protected $signature = 'simulate:settlements {count=50}';
    protected $description = 'Dispatch concurrent merchant settlement batch to queue';

    public function handle(): void
    {
        $count = (int) $this->argument('count');
        $this->info("Creating and dispatching {$count} batch settlement jobs...");

        $jobs = [];
        for ($i = 1; $i <= $count; $i++) {
            // Mock instance merchant
            $merchant = new Merchant();
            $merchant->id = $i;
            $merchant->bank_account_number = 'ACC-' . rand(100000, 999999);
            $merchant->bank_code = 'BNI';

            $jobs[] = new ProcessMerchantSettlementJob(
                merchant: $merchant,
                settlementDate: now()->toDateString(),
                idempotencyKey: 'IDEMP-' . Str::uuid()->toString()
            );
        }

        // Orchestrate via Bus Batch
        $batch = Bus::batch($jobs)
            ->name('Nightly Merchant Settlement')
            ->allowFailures()
            ->dispatch();

        $this->info("Batch dispatched successfully! Batch ID: {$batch->id}");
    }
}
```

Jalankan Horizon dan trigger command:
```bash
php artisan horizon &
php artisan simulate:settlements 20
```

---

## 13. Exercise

### Level Easy
Modifikasi kelas `SendWelcomeEmailJob` pada sub-bab 7 agar mengimplementasikan interval backoff selama 10 detik, 30 detik, dan 60 detik jika terjadi error koneksi SMTP.
- **Expected Outcome**: Saat SMTP connection error, queue worker tidak langsung membuang job ke tabel `failed_jobs`, melainkan menjadwalkan ulang ke ZSet `delayed` dengan rentang jeda yang telah ditentukan.

### Level Medium
Buat sebuah Job Middleware bernama `App\Jobs\Middleware\TenantDatabaseSelector` yang mendeteksi parameter `tenant_id` dari properti payload job, lalu secara dinamis mengubah koneksi basis data default menggunakan `DB::purge()` dan `DB::setDefaultConnection()` sebelum method `handle()` job dieksekusi.
- **Expected Outcome**: Seluruh query yang dipanggil di dalam job secara otomatis terisolasi ke database schema tenant yang sesuai tanpa kebocoran (*leakage*) context ke job berikutnya.

### Level Hard
Desain sebuah sistem orchestrator job batching yang memproses 10.000 import file CSV. Jika terdapat 1 baris yang gagal, batch **tidak boleh dibatalkan** (`allowFailures`), namun sistem harus mencatat index baris yang rusak ke Redis Set secara non-blocking, lalu mengirimkan rekapitulasi rangkuman *error matrix* pada event `then()` atau `finally()` batch tersebut.
- **Expected Outcome**: Batch selesai memproses baris valid, baris invalid terkumpul di memory Redis, dan satu notifikasi ringkasan terkirim ke administrator tanpa menurunkan throughput worker.

---

## 14. Challenge

Rancang arsitektur pemrosesan antrean data terdistribusi berskala enterprise dengan batasan kondisi (*constraints*) berikut:
1. **Scenario**: Aplikasi Anda terintegrasi dengan Vendor API Pihak Ketiga (Core Banking) yang memiliki batasan ketat: *Maksimal 100 concurrent requests secara global di seluruh kluster server*. Jika melebihi batasan ini, IP server akan diblokir selama 1 jam.
2. **Cluster Topology**: Anda menjalankan 10 mesin worker di AWS Auto-Scaling Group, di mana masing-masing mesin menjalankan 20 proses worker (Total = 200 proses worker aktif).
3. **Problem**: Penggunaan middleware lokal `RateLimited` tidak cukup aman jika cluster mengalami *network latency variance*, dan race condition pada pembacaan counter Redis dapat memicu lonjakan ke 105 request pada detik yang sama.

**Tugas Arsitektur**:
- Desain mekanisme *Global Concurrency Limiter* menggunakan Redis Skrip Lua teratomisasi atau implementasi Token Bucket / Leaky Bucket algorithm.
- Rancang fallback mechanism jika Redis mengalami kegagalan (*Redis down/split-brain*), bagaimana worker harus bersikap tanpa melanggar batasan konkurensi Vendor API?
- Tuliskan implementasi kode class Middleware Queue custom tersebut secara lengkap dan jelaskan kompleksitas algoritmanya ($O(1)$ vs $O(N)$).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Konsep Dasar (5 Pertanyaan)
1. Apa perbedaan arsitektural utama antara mengeksekusi antrean via `php artisan queue:work` dibandingkan dengan `php artisan queue:listen`?
2. Mengapa method `afterCommit()` sangat penting dipanggil ketika melempar *job dispatch* di dalam sebuah blok `DB::transaction`?
3. Struktur data Redis apa yang digunakan Laravel Queue untuk mengelola antrean pekerjaan yang memiliki instruksi jeda waktu (*delayed dispatch*)?
4. Apa fungsi dari trait `InteractsWithQueue` di dalam sebuah kelas Job Laravel?
5. Sinyal POSIX OS apa yang dikirimkan oleh orchestrator (seperti Kubernetes atau Supervisor) untuk memerintahkan worker berhenti secara aman (*graceful termination*)?

### Bagian B: Analisis Menengah (5 Pertanyaan)
1. Sebuah job memiliki konfigurasi public property `$tries = 3` dan `$timeout = 30`. Konfigurasi koneksi antrean di `queue.php` memiliki nilai `'retry_after' => 25`. Anomali arsitektur apa yang berpotensi fatal terjadi di sistem produksi?
2. Bagaimana mekanisme kerja antarmuka `ShouldBeUnique` dalam mencegah duplikasi job yang identik saat masih berada di dalam antrean?
3. Mengapa eksekusi fungsi `DB::enableQueryLog()` di dalam pemrosesan queue worker berkapasitas tinggi dapat mengakibatkan *crash* sistem?
4. Bagaimana cara kerja internal fitur *Job Batching* di Laravel dalam melacak bahwa seluruh koleksi job telah selesai dieksekusi secara terdistribusi?
5. Apa fungsi dari perintah `php artisan queue:restart` dan bagaimana worker yang sedang berjalan mendeteksi eksekusi perintah tersebut?

### Bagian C: Skenario Kasus Produksi (3 Pertanyaan)

#### Skenario 1: The "Ghost Deduction" Failure
Sistem e-commerce Anda mengalami masalah di mana saldo pelanggan terpotong dua kali untuk satu ID pesanan yang sama saat terjadi lonjakan traffic flash-sale. Setelah diperiksa:
- Redis server mengalami *high CPU load* (99%).
- Tabel `failed_jobs` kosong.
- Nilai konfigurasi `retry_after` adalah 60 detik.
- Log server menunjukkan waktu eksekusi job rata-rata adalah 65-70 detik akibat lambatnya respons database.  
**Pertanyaan**: Analisis akar penyebab (*root-cause*) terjadinya pemotongan saldo ganda tersebut berdasarkan cara kerja internal `reserved` queue Laravel, dan berikan solusi arsitekturnya!

#### Skenario 2: Deadlock Ingestion Webhook Kluster
Sebuah webhook endpoint menerima 500 callback per detik dari payment gateway dan memasukkannya ke antrean `high`. Setiap job mengeksekusi:
```php
$user = User::where('id', $this->userId)->first();
$user->increment('balance', $this->amount);
```
Setelah 5 menit, throughput antrean drop drastis hingga mendekati 0, dan ribuan transaksi mengalami status timeout.  
**Pertanyaan**: Identifikasi fenomena database lock apa yang terjadi di layer worker dan bagaimana merekayasa ulang job logic tersebut agar antrean kembali berjalan lancar?

#### Skenario 3: Serialization Trap pada Soft-Deleted Model
Sebuah job `ArchiveUserDataJob` didispatch ke antrean dengan delay 10 menit. Selama rentang waktu 10 menit tersebut, user melakukan penutupan akun yang memicu operasi soft-delete (`$user->delete()`). Saat worker mengambil job tersebut setelah 10 menit, job langsung gagal dengan error `ModelNotFoundException` sebelum method `handle()` sempat dieksekusi.  
**Pertanyaan**: Mengapa error terjadi sebelum baris pertama method `handle()`? Properti atau konfigurasi apa yang harus ditambahkan pada kelas Job untuk menangani skenario ini secara elegan?

---

## Kunci Jawaban & Panduan Solusi Quiz

### Bagian A: Konsep Dasar
1. `queue:work` melakukan bootstrap framework Laravel hanya satu kali dan terus memproses antrean dalam memori yang sama (cepat, rentan memory leak). `queue:listen` membuat sub-proses PHP baru untuk mem-bootstrap ulang seluruh framework pada setiap eksekusi job (lambat, terisolasi sempurna dari memory leak).
2. Jika job didispatch sebelum transaksi DB di-commit, worker yang berjalan sangat cepat di thread/proses lain dapat langsung mengambil job tersebut dari Redis dan mencoba mencari record DB yang secara aktual belum tersimpan (*uncommitted/dirty read*), menyebabkan error `ModelNotFoundException`.
3. Menggunakan Redis `Sorted Set (ZSet)`. Timestamp waktu eksekusi dijadikan sebagai *Score*, dan Worker menggunakan nilai score tersebut untuk mengambil job yang telah memenuhi syarat eksekusi.
4. Trait tersebut menyediakan method internal untuk berinteraksi langsung dengan status runtime antrean worker yang sedang aktif, seperti: `$this->release()`, `$this->delete()`, `$this->attempts()`, dan `$this->fail()`.
5. Sinyal `SIGTERM`. Worker akan menangkap sinyal ini, menyelesaikan pemrosesan job yang sedang *in-flight*, lalu menghentikan proses loop secara normal (*graceful shutdown*).

### Bagian B: Analisis Menengah
1. **Konflik Fatal Timeout vs Retry After**: Nilai `retry_after` (25s) lebih pendek dari `$timeout` (30s). Jika job berjalan selama 26 detik, sistem antrean Redis menganggap worker telah mati dan melepaskan job tersebut kembali ke antrean utama untuk diambil oleh worker kedua, padahal worker pertama masih bekerja. Ini memicu *Duplicate Parallel Processing*.
2. Memanfaatkan Redis Lock. Ketika job didispatch, Laravel mencoba membuat lock key di cache berbasis method `uniqueId()`. Jika lock berhasil didapatkan, job dimasukkan ke antrean. Jika lock sudah ada, job dibatalkan atau diabaikan hingga job awal selesai dieksekusi dan melepaskan lock tersebut.
3. Karena `queue:work` adalah proses *long-lived*. `enableQueryLog()` menyimpan seluruh histori string query SQL, bindings, dan execution time ke dalam array memori PHP. Tanpa dibersihkan, memori akan terus terakumulasi hingga menyentuh batas `memory_limit` dan mematikan proses via OOM.
4. Framework mencatat ID Batch di tabel `job_batches` (atau Redis). Setiap job yang tergabung dalam batch menyimpan ID Batch tersebut. Saat sebuah job selesai, framework secara atomik mengurangi counter `pending_jobs`. Ketika counter mencapai 0, Laravel mengeksekusi callback `then()` atau `finally()`.
5. Perintah tersebut memperbarui nilai timestamp di cache storage sistem (`illuminate:queue:restart`). Setiap kali worker menyelesaikan satu siklus iterasi job, worker akan mengevaluasi apakah timestamp restart di cache lebih besar daripada waktu worker tersebut pertama kali di-boot. Jika ya, worker mematikan dirinya sendiri agar process manager (Supervisor) dapat me-restart proses baru yang bersih.

### Bagian C: Skenario Kasus Produksi

#### Solusi Skenario 1:
- **Akar Masalah**: Job membutuhkan waktu 65-70 detik, melebihi konfigurasi `retry_after` (60 detik). Sebelum worker 1 selesai, Redis reserved monitor memindahkan kembali payload transaksi tersebut ke ready queue karena dianggap hang. Worker 2 langsung mengambil job yang sama dan mengeksekusinya kembali. Hal ini memicu eksekusi pemotongan saldo ganda (*double deduction*).
- **Solusi Arsitektural**:
  1. Tingkatkan nilai `retry_after` minimal 2x lipat dari durasi maksimum `$timeout` (misal: `$timeout = 60`, `retry_after = 120`).
  2. Implementasikan *Strict Idempotency Key* berbasis database locking (`SELECT ... FOR UPDATE`) atau Redis Atomic Lock sebelum mengeksekusi pemotongan dana. Jika record status ledger sudah berstatus `PROCESSED`, job worker kedua harus langsung return void.

#### Solusi Skenario 2:
- **Akar Masalah**: *Row-Level Lock Contention* pada baris tabel user yang sama. 500 job/detik berebut melakukan update lock pada ID user yang sama secara bersamaan, memicu antrean kunci transaksi DB (*Lock Wait Queue*) yang menyebabkan starvation, timeout, dan deadlock pada database pool.
- **Solusi Arsitektural**:
  1. Jangan lakukan update agregat balance secara sinkron per-event webhook. Ubah pola menjadi *Append-Only Ingestion*: Masukkan histori transaksi ke tabel mutasi (`ledger_entries`) tanpa mengunci tabel induk.
  2. Gunakan konsolidasi pemrosesan (Batch Aggregator): Kumpulkan mutasi saldo dalam satu rentang waktu (misal: per 10 detik via Redis memory aggregation), lalu lakukan update akumulasi saldo induk secara tunggal (*single atomic aggregate query*).

#### Solusi Skenario 3:
- **Akar Masalah**: Trait `SerializesModels` mengeksekusi pemanggilan `findOrFail($id)` saat melakukan proses *Model Rehydration* (unserialize). Karena model telah di-soft-delete, query standar gagal menemukan record aktif tersebut dan melempar `ModelNotFoundException` sebelum mencapai fungsi `handle()`.
- **Solusi Arsitektural**:
  Tambahkan properti publik pada kelas Job tersebut untuk mengizinkan pemrosesan model yang telah di-soft-delete atau menghapus job secara diam-diam tanpa mencatat failure:
  ```php
  // Opsi 1: Otomatis hapus job tanpa trigger failed_jobs jika model hilang
  public bool $deleteWhenMissingModels = true;
  ```
  Atau jika data soft-delete masih harus diproses di dalam method `handle()`:
  ```php
  // Opsi 2: Definisikan type-hint model denganwithTrashed pada serialisasi
  // Laravel secara otomatis merehidrasi Soft Deletes jika model mengimplementasikan SoftDeletes trait.
  ```

---

## 16. Summary
- Pemrosesan antrean pada kelas enterprise menuntut pemahaman mendalam mengenai arsitektur *long-lived process*, batasan alokasi memori runtime PHP-CLI, dan siklus hidup event loop.
- Kombinasi driver Redis yang mengeksploitasi struktur data `List` dan `ZSet` menjamin kecepatan throughput komputasi, namun mensyaratkan sinkronisasi presisi antara nilai parameter `$timeout` dengan konfigurasi driver `retry_after`.
- Kegagalan sistem terdistribusi adalah keniscayaan (*design for failure*). Menjaga idempotensi logika bisnis, mencegah model deserialization drift, dan menerapkan *Graceful Draining* pada orkestrator kontainer (Kubernetes/Horizon) merupakan pembeda fundamental antara sistem antrean amatir dengan sistem transaksi terdistribusi berstandar industri perbankan dan enterprise global.