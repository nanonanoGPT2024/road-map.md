# Kurikulum Enterprise: Laravel Backend Engineering
## BAB 10: High Availability, Observability, CI/CD & Deployment
### MODUL 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Merancang dan mengoperasikan topologi Laravel *High-Availability* (HA) nir-status (*stateless*) pada skala multi-node.
- Mengimplementasikan pipeline zero-downtime deployment menggunakan paradigma *Expand/Contract* untuk migrasi skema database tanpa *table-locking*.
- Membangun stack *Enterprise Observability* mencakup metrik real-time Prometheus, distributed tracing berbasis OpenTelemetry (OTel), dan structured JSON logging dengan propagasi *Correlation ID*.
- Mengonfigurasi *runtime engine* berperforma tinggi (FrankenPHP / Laravel Octane) yang kompatibel dengan graceful termination dan container orchestration (Kubernetes/ECS).
- Menghindari jebakan arsitektural fatal pada *shared-state*, *cache stampede*, dan *zombie worker queues*.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, Anda wajib menguasai:
- **PHP 8.3+ Internals**: Memory management, opcache preloading, fiber/asynchronous basics, dan process signals (`SIGTERM`, `SIGINT`).
- **Laravel Core Architecture**: Service Container, Request Lifecycle, Horizon, Queue Workers, Event Listeners, dan Middlewares.
- **Infrastruktur Dasar**: Docker multi-stage builds, reverse proxy (Nginx/Traefik), Redis replication/sentinel, serta database connection pooling (PgBouncer/ProxySQL).

---

### 3. Concept & Internal Architecture

#### A. The Stateless Application Node Paradigm
Secara default, Laravel menyimpan *state* sementara di filesystem lokal:
- Sesi pengguna (`storage/framework/sessions`)
- Cache berbasis file (`storage/framework/cache`)
- Token upload temporary / file user (`storage/app`)
- Log aplikasi (`storage/logs/laravel.log`)

Untuk mencapai status *High Availability*, node aplikasi Laravel harus bersifat *ephemeral* dan *disposable*. Jika sebuah node mati mendadak, tidak ada data transaksional maupun status user yang hilang.

```
                  ┌──────────────────────────────┐
                  │ Layer 4 / Layer 7 AWS ALB    │
                  └──────────────┬───────────────┘
                                 │ Round-Robin / Least Conn
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
  ┌──────────────┐        ┌──────────────┐        ┌──────────────┐
  │ App Node 01  │        │ App Node 02  │        │ App Node 03  │
  │ (Stateless)  │        │ (Stateless)  │        │ (Stateless)  │
  └──────┬───────┘        └──────┬───────┘        └──────┬───────┘
         │                       │                       │
         ├───────────────────────┴───────────────────────┤
         ▼                                               ▼
┌──────────────────────────────┐               ┌───────────────────┐
│ Redis Sentinel / Cluster     │               │ AWS Aurora MySQL  │
│ (Sessions, Cache, Queues)    │               │ (Write/Read Split)│
└──────────────────────────────┘               └───────────────────┘
```

#### B. The Zero-Downtime Deployment & Database Migration Dichotomy
Downtime deployment paling sering disebabkan oleh:
1. **Locking Migrations**: Eksekusi perintah `ALTER TABLE` seperti penambahan kolom atau modifikasi tipe data yang mengunci tabel (DML queue terhambat hingga timeout).
2. **Race Condition Assets/Code**: Request yang sedang berjalan di node masih mengeksekusi kode versi $N$, sementara request baru memanggil dependensi versi $N+1$.

Solusi arsitektur: Menggunakan **Expand/Contract Pattern**:
- **Fase 1 (Expand)**: Tambahkan kolom/tabel baru (bersifat *nullable* atau memiliki default value). Deploy kode versi baru yang menulis ke kolom lama dan kolom baru.
- **Fase 2 (Backfill)**: Sinkronisasi data lawas ke skema baru via background job.
- **Fase 3 (Contract)**: Update kode untuk hanya membaca dan menulis ke kolom baru. Deploy.
- **Fase 4 (Cleanup)**: Hapus kolom/tabel lama via migrasi independen di luar jam sibuk.

#### C. Full-Stack Observability Model
Observability bukan sekadar *monitoring*. Tiga pilar utamanya harus saling berkorelasi via metadata kontekstual:

1. **Metrics**: Kuantitatif time-series (CPU, RAM, Request Rate, Latency P95/P99 via Prometheus).
2. **Logs**: Peristiwa diskret berformat JSON struktural, diinjeksi dengan `trace_id` dan `span_id`.
3. **Traces**: Alur hidup lengkap sebuah request lintas microservice/worker menggunakan context propagation standar W3C `traceparent`.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional | Pendekatan Enterprise HA |
| :--- | :--- | :--- |
| **Penyimpanan Sesi & Cache** | File lokal / Database tunggal | Redis Cluster / Sentinel terisolasi |
| **Asset Storage** | `public/storage` symlink lokal | S3-Compatible Object Storage + CDN |
| **Worker Process** | `php artisan queue:work` via systemd | Containerized worker pool + Graceful shutdown drain via `SIGTERM` |
| **Eksekusi Migrasi** | `php artisan migrate --force` saat rolling update | Expand/Contract decoupled via pre-deployment step |
| **Log Management** | Single file per server (rotasi harian) | JSON Streams stdout -> FluentBit/Promtail -> Loki/Elasticsearch |
| **Tracing** | Manual dump via `Log::info()` | OpenTelemetry Tracing Agent terdistribusi |

---

### 5. How (Workflow Detail)

#### 1. Inisialisasi Lifecycle Request
1. Gateway/Load Balancer menerima traffic, menginjeksi header `X-Request-ID` dan W3C `traceparent`.
2. Laravel HTTP Middleware mencegat request, mendaftarkan `CorrelationContext` ke Service Container sebagai singleton.
3. OpenTelemetry Middleware memulai *root span*.

#### 2. Eksekusi Runtime
1. Autentikasi session ditarik dari Redis primary/replica via non-blocking connection.
2. Query database dipisah: operasi `SELECT` diarahkan ke Read Replicas via connection array di `config/database.php`, operasi `INSERT/UPDATE/DELETE` diarahkan ke Primary Node.

#### 3. Terminasi & Observabilitas
1. Middleware mencatat metrics: status HTTP, waktu eksekusi, penggunaan memori (dikirim ke OpenTelemetry SDK / Prometheus exporter).
2. Monolog Processor menambahkan `trace_id`, `user_id`, dan `ip_address` ke seluruh log record.
3. Node merespons client, *root span* ditutup.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional Skala Enterprise
- **Node Statis Tradisional**: Stasiun kereta lokal di mana tiket fisik disimpan di laci loket 1. Jika loket 1 rusak, antrean terhenti dan tiket hilang.
- **Node HA Stateless**: Bandara modern. Penumpang membawa tiket digital dengan QR Code (*Token/Stateless Session*). Loket mana pun (Node 1, 2, atau 100) dapat memindai tiket karena data validasi tersimpan di cloud database pusat. Jika loket 2 ditutup (*pod killed*), penumpang langsung dialihkan ke loket 3 tanpa hambatan.

```
TRACE PROPAGATION FLOW:
[ Client Request ]
       │
       ▼ (Header: traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01)
┌────────────────────────────────────────────────────────┐
│ HTTP Kernel / OpenTelemetry Middleware                 │
│ ├─ Extract traceparent                                 │
│ ├─ Generate Context Span                               │
│ └─ Bind to Monolog Context                             │
└──────────────────────────┬─────────────────────────────┘
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
┌─────────────────────────┐ ┌─────────────────────────────┐
│ Database Query Event    │ │ External HTTP (Http::get)   │
│ Parent: [Span 00f067...]│ │ Propagate header via PSR-18 │
│ Child:  [Span 8a3c21...]│ │ Parent: [Span 00f067...]    │
└─────────────────────────┘ └─────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### Practical Implementation: Correlation Context & Structured Logging

##### Langkah 1: Correlation ID Middleware
```php
<?php

declare(strict_types=1);

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Str;
use Symfony\Component\HttpFoundation\Response;

class CorrelationIdMiddleware
{
    public const HEADER_NAME = 'X-Correlation-ID';

    public function handle(Request $request, Closure $next): Response
    {
        $correlationId = $request->header(self::HEADER_NAME) 
            ?? (string) Str::uuid();

        // Inject ke request attributes agar dapat diakses downstream
        $request->attributes->set('correlation_id', $correlationId);

        // Bind ke container untuk diakses service layer
        app()->instance('correlation_id', $correlationId);

        /** @var Response $response */
        $response = $next($request);

        // Kembalikan header ke client untuk traceability
        $response->headers->set(self::HEADER_NAME, $correlationId);

        return $response;
    }
}
```

##### Langkah 2: Monolog Processor untuk Structured Context
```php
<?php

declare(strict_types=1);

namespace App\Logging;

use Monolog\LogRecord;
use Monolog\Processor\ProcessorInterface;

class OpenTelemetryLogProcessor implements ProcessorInterface
{
    public function __invoke(LogRecord $record): LogRecord
    {
        $correlationId = app()->bound('correlation_id') 
            ? app('correlation_id') 
            : null;

        $extra = [
            'correlation_id' => $correlationId,
            'environment'    => config('app.env'),
            'runtime'        => php_sapi_name(),
        ];

        // Integrasi Otel Span jika ekstensi terpasang
        if (class_exists(\OpenTelemetry\API\Trace\Span::class)) {
            $currentSpan = \OpenTelemetry\API\Trace\Span::getCurrent();
            $context = $currentSpan->getContext();
            if ($context->isValid()) {
                $extra['trace_id'] = $context->getTraceId();
                $extra['span_id']  = $context->getSpanId();
            }
        }

        return $record->with(extra: array_merge($record->extra, $extra));
    }
}
```

##### Langkah 3: Konfigurasi Logging (`config/logging.php`)
```php
'channels' => [
    'stack' => [
        'driver' => 'stack',
        'channels' => ['stdout'],
        'ignore_exceptions' => false,
    ],

    'stdout' => [
        'driver' => 'monolog',
        'handler' => \Monolog\Handler\StreamHandler::class,
        'formatter' => \Monolog\Formatter\JsonFormatter::class,
        'processors' => [
            \App\Logging\OpenTelemetryLogProcessor::class,
        ],
        'with' => [
            'stream' => 'php://stdout',
        ],
    ],
],
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Flash Sale E-Commerce Tier-1 (100.000 Request/Detik)
- **Problem**: Saat event Midnight Sale, kluster Laravel 10 (30 pod di Kubernetes) mengalami *cascade failure*. Database MySQL crash karena koneksi melonjak hingga batas maksimal (`Too many connections`), dan waktu latensi memuncak dari 80ms menjadi 15.000ms.
- **Root Cause Analysis (RCA)**:
  1. *State Contention*: Session masih disimpan di MySQL (`sessions` table), mengunci row saat update timestamp.
  2. *Cache Stampede*: Cache harga produk kadaluarsa secara serentak, membuat puluhan ribu worker langsung query ke DB secara bersamaan (*dog-piling effect*).
  3. *Unmanaged Migrations*: Menjalankan `php artisan migrate` saat sale berlangsung untuk menambahkan indeks baru, menyebabkan `ALTER TABLE` mengunci tabel `orders`.
- **Architectural Solution Implemented**:
  1. **Session & Cache Offloading**: Memindahkan session dan cache ke kluster AWS ElastiCache for Redis Multi-AZ dengan Redis Sentinel.
  2. **Cache Stampede Mitigation**: Menggunakan atomic locks dan probabilistik early expiration:
     ```php
     Cache::lock('product:price:101:lock', 10)->block(3, function () {
         return Cache::remember('product:price:101', 3600, fn() => DB::table('prices')->find(101));
     });
     ```
  3. **Read/Write Splitting & ProxySQL Connection Multiplexing**: Mengarahkan seluruh query pembacaan ke 4 Aurora Read Replicas dengan connection pooler ProxySQL, membatasi max backend connection ke database master hanya 200 koneksi persisten.

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Konsekuensi / Kerugian |
| :--- | :--- | :--- |
| **Stateless Local Disk via S3 Sync** | Murah, arsitektur dasar tidak banyak berubah | Latensi tinggi (*I/O bound*), inkonsistensi data antar-node jika sync tertunda |
| **Native S3 Driver (Flysystem)** | Skalabilitas tak terbatas, data konsisten lintas node | Biaya API call (PUT/GET), latensi upload bertambah jika file besar (wajib direct presigned-url) |
| **Redis Centralized Sessions** | Skalabilitas horizontal instan, zero node-affinity | Redis menjadi *Single Point of Failure* jika tidak memakai Sentinel/Cluster Multi-AZ |
| **Laravel Octane (Swoole/FrankenPHP)** | Throughput naik 400-800%, resource utilization rendah | Resiko *memory leaks*, *static property leakage* antar request, dependensi C-extension |
| **OpenTelemetry Deep Tracing** | Visibilitas performa granular hingga level query | Overhead CPU (2-5%), konsumsi bandwidth jaringan untuk data telemetry |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Insecure Local Storage Assumption
- **Error**: File invoice yang digenerate oleh Node A tidak ditemukan saat diunduh user via Node B (`FileNotFoundException: storage/invoices/inv-01.pdf`).
- **Fix**: Jangan pernah menulis aset unduhan publik ke disk lokal pod. Gunakan `Storage::disk('s3')->put()` atau stream secara langsung ke output buffer via signed S3 link.

#### 2. Worker Unclean Shutdown (Data Corruption)
- **Error**: Saat deploy, pod Kubernetes langsung dimatikan (`SIGKILL`), memutus job pembayaran yang sedang di tengah-tengah transaksi payment gateway.
- **Fix**: Tangani sinyal OS secara graceful pada container entrypoint dan konfigurasi lifecycle container:
  ```dockerfile
  STOPSIGNAL SIGTERM
  ```
  Di konfigurasi Kubernetes:
  ```yaml
  spec:
    terminationGracePeriodSeconds: 120
    containers:
      - name: laravel-worker
        lifecycle:
          preStop:
            exec:
              command: ["php", "artisan", "queue:restart"]
  ```

#### 3. Log Spamming & Unstructured Strings
- **Error**: Menulis log plaintext panjang via `Log::error($e->getMessage())` tanpa stack trace terstruktur. Menghambat parsing log di OpenSearch/Loki.
- **Fix**: Selalu lewatkan data sebagai context array:
  ```php
  Log::error('Gagal memproses transaksi', [
      'exception' => $e,
      'order_id'  => $order->id,
      'payload'   => $request->sanitizedPayload(),
  ]);
  ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Config & Route Cache**: Eksekusi `php artisan config:cache`, `route:cache`, `view:cache`, dan `event:cache` pada proses image build Docker, bukan saat boot runtime pod.
- [ ] **Read/Write Splitting Verification**: Pastikan `sticky => true` di `config/database.php` untuk mencegah race-condition replication lag langsung setelah penulisan data.
- [ ] **Health Checks API**: Buat endpoint `/healthz` yang memeriksa dependensi vital (Database ping, Redis ping) secara efisien (gunakan timeout maksimal 1.5 detik).
- [ ] **Dynamic Opcache Configuration**:
  ```ini
  opcache.enable=1
  opcache.memory_consumption=256
  opcache.max_accelerated_files=20000
  opcache.validate_timestamps=0
  opcache.save_comments=1
  ```
- [ ] **Secrets Management**: Jangan simpan file `.env` di image container. Gunakan HashiCorp Vault, AWS Secrets Manager, atau Kubernetes Secrets yang diinjeksi via environment variables.

---

### 12. Hands-on Practice

Buat skenario zero-downtime healthcheck dan pipeline observabilitas pada direktori `hands-on/m02/`.

#### Langkah 1: Persiapan HealthCheck Controller
Simpan di `hands-on/m02/app/Http/Controllers/HealthCheckController.php`:

```php
<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Redis;
use Throwable;

class HealthCheckController
{
    public function __invoke(): JsonResponse
    {
        $status = 'healthy';
        $checks = [
            'database' => 'operational',
            'redis'    => 'operational',
        ];

        try {
            DB::connection()->getPdo();
        } catch (Throwable $e) {
            $checks['database'] = 'unhealthy';
            $status = 'unhealthy';
        }

        try {
            Redis::connection()->ping();
        } catch (Throwable $e) {
            $checks['redis'] = 'unhealthy';
            $status = 'unhealthy';
        }

        $httpCode = $status === 'healthy' ? 200 : 503;

        return response()->json([
            'status'     => $status,
            'timestamp'  => now()->toIso8601String(),
            'components' => $checks,
        ], $httpCode);
    }
}
```

#### Langkah 2: Production Container Engine Dockerfile
Simpan di `hands-on/m02/Dockerfile`:

```dockerfile
# Multi-stage Enterprise Build
FROM php:8.3-fpm-alpine AS base

# Install system dependencies
RUN apk add --no-cache \
    linux-headers \
    libpng-dev \
    libxml2-dev \
    libzip-dev \
    pcre-dev \
    ${PHPIZE_DEPS}

# Install PHP extensions
RUN docker-php-ext-install bcmath pdo_mysql opcache \
    && pecl install redis \
    && docker-php-ext-enable redis

# Install Composer
COPY --from=composer:2.7 /usr/bin/composer /usr/bin/composer

WORKDIR /var/www/html

# Stage 2: Vendor Build
FROM base AS vendor
COPY composer.json composer.lock ./
RUN composer install --no-dev --no-scripts --no-autoloader --prefer-dist

COPY . .
RUN composer dump-autoload --optimize --no-dev

# Stage 3: Runtime
FROM base AS runtime
COPY --from=vendor /var/www/html /var/www/html
COPY ./docker/php/opcache.ini /usr/local/etc/php/conf.d/opcache.ini

# Set permissions
RUN chown -R www-data:www-data /var/www/html/storage

USER www-data

EXPOSE 9000
CMD ["php-fpm", "-F"]
```

#### Langkah 3: CI/CD Pipeline (GitHub Actions Enterprise Stage)
Simpan di `hands-on/m02/.github/workflows/deploy.yml`:

```yaml
name: Production Zero-Downtime Deployment

on:
  push:
    branches: [ "main" ]

jobs:
  test-and-analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup PHP
        uses: shivammathur/setup-php@v2
        with:
          php-version: '8.3'
          extensions: mbstring, pdo, pdo_mysql, redis
          coverage: none

      - name: Install Dependencies
        run: composer install --prefer-dist --no-progress --no-interaction

      - name: Run Static Analysis (PHPStan)
        run: ./vendor/bin/phpstan analyse --level=8 app

      - name: Run Test Suite
        run: php artisan test --parallel

  deploy-canary:
    needs: test-and-analyze
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Pre-Deployment DB Migration (Expand Only)
        env:
          DB_HOST: ${{ secrets.PROD_DB_HOST }}
          DB_PASSWORD: ${{ secrets.PROD_DB_PASS }}
        run: |
          php artisan migrate --force --isolated

      - name: Deploy Containers to Kubernetes Cluster
        run: |
          echo "Rolling update deployment via Helm/Kustomize to prevent downtime"
          # kubectl rollout status deployment/laravel-app --timeout=120s
```

---

### 13. Exercise

#### Level Easy
Ubah konfigurasi driver cache dan session Laravel dari default `file` menjadi `redis` yang scalable pada environment `.env` dan `config/database.php`. Verifikasi fungsionalitas menggunakan artisan command.

#### Level Medium
Buat sebuah Custom Logging Monolog Processor yang bertugas menyensor (masking) field sensitif seperti `password`, `credit_card_number`, dan `authorization_bearer` dari context array sebelum payload log ditulis ke stdout.

#### Level Hard
Implementasikan sebuah custom Queue Worker Watchdog menggunakan event listener Laravel (`JobProcessing`, `JobFailed`, `JobProcessed`). Worker harus mencatat metrik latensi eksekusi queue ke sistem Prometheus exporter format secara real-time dan mendeteksi kondisi jika sebuah worker mendadak silent (*zombie loop*) lebih dari 300 detik.

---

### 14. Challenge

> **Tantangan Rekayasa**: "Zero-Lock Realtime Migration pada Transaksi 50 Juta Baris Data"
> 
> **Kondisi**:
> Anda mengelola sistem core-ledger perbankan dengan tabel `transactions` yang berisi 50.000.000 row data aktif. Sistem menerima rata-rata 3.500 transaksi per detik (TPS) secara konsisten. 
> 
> **Kebutuhan**:
> Manajemen membutuhkan pemisahan field `amount` (INTEGER) menjadi dua field: `amount_cents` (BIGINT) dan `currency_code` (VARCHAR(3)).
> 
> **Batasan Ketat**:
> 1. Dilarang menggunakan perintah `ALTER TABLE transactions ADD COLUMN ...` konvensional yang dapat menyebabkan database read/write locks lebih dari 100 milidetik.
> 2. Zero-downtime total: Tidak boleh ada request nasabah yang *timeout* atau gagal (*502 Bad Gateway* / *504 Gateway Timeout*).
> 3. Data konsistensi harus 100% atomik (tidak boleh ada uang yang hilang atau ganda selama proses sinkronisasi).
> 
> **Tugas Anda**:
> Tuliskan arsitektur tahapan deploy (Expand/Contract Pipeline), rancang strategi dual-writing di Eloquent Event/Model Layer, dan siapkan script worker backfilling asinkron yang bekerja di background tanpa menghabiskan CPU load database (di bawah ambang batas 40% CPU usage).

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa driver session `file` default Laravel tidak boleh digunakan dalam kluster multi-node High-Availability?
2. Apa bahaya menjalankan `php artisan config:cache` langsung di level runtime kontainer Kubernetes saat node baru di-scale otomatis?
3. Sinyal sistem operasi apa yang wajib dikirim ke process manager Laravel Worker agar ia menyelesaikan job yang sedang berjalan sebelum pod dihancurkan?
4. Apa fungsi dari opsi `--isolated` pada eksekusi `php artisan migrate`?
5. Mengapa driver `log` berbasis rotasi file lokal (`single` atau `daily`) sangat dihindari dalam ekosistem containerized cloud-native?

#### B. Pertanyaan Intermediate
1. Jelaskan bagaimana mekanisme race-condition replication lag terjadi pada konfigurasi Database Read/Write Splitting di Laravel, dan bagaimana cara parameter `sticky` memecahkan masalah tersebut!
2. Dalam implementasi Laravel Octane (FrankenPHP/Swoole), mengapa deklarasi variabel static atau singleton binding di Service Provider rentan menghasilkan *state leakage* antar request user yang berbeda?
3. Bagaimana format standar header HTTP OpenTelemetry W3C Distributed Tracing untuk menyambungkan span request dari Load Balancer ke aplikasi Laravel?
4. Jelaskan perbedaan mendasar antara Health Check tipe `livenessProbe` dan `readinessProbe` pada deployment pod Laravel di Kubernetes!
5. Apa konsekuensi arsitektural jika fitur `queue:restart` tidak dieksekusi setelah image container worker diupdate dengan kode PHP baru?

#### C. Skenario Kasus Produksi
1. **Skenario 1**: Setelah melakukan rolling update cluster Laravel 11 di AWS EKS, 15% user mengalami logout otomatis dan mendapati pesan error "419 Page Expired (CSRF token mismatch)". Apa akar masalah arsitektural ini dan bagaimana mitigasi permanennya?
2. **Skenario 2**: Sistem Anda mengalami traffic spike mendadak. Pods di autoscaler naik dari 10 menjadi 80 pod. Seketika itu pula, seluruh pod mati serempak (*CrashLoopBackOff*) dengan error: `RedisException: Connection refused`. Analisis urutan kegagalan (*failure chain*) dan berikan solusinya!
3. **Skenario 3**: Tim Anda merilis migrasi kolom baru menggunakan tipe data JSON pada tabel `orders` yang memiliki ukuran 200 GB di Amazon RDS MySQL. Beberapa detik setelah migrasi dijalankan, API checkout utama freeze total dan latensi melonjak drastis. Mengapa hal ini terjadi dan bagaimana mekanisme mitigasi *Expand/Contract* yang seharusnya dilakukan?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Jawaban Basic
1. Driver file menyimpan data pada hard drive lokal node. Karena load balancer membagi request antar-node yang berbeda secara dinamis, request kedua dari user yang sama akan mendarat di node lain yang tidak memiliki file session tersebut, mengakibatkan user otomatis ter-logout.
2. Karena direktori storage/bootstrap mungkin read-only pada pod, dan kompilasi cache runtime memakan resource CPU/Memory node produksi. Konfigurasi harus di-compile statis pada tahap *Docker build time*.
3. Sinyal `SIGTERM`. Ini memberitahu worker untuk masuk mode drain (menyelesaikan job aktif hingga selesai) dan menolak mengambil job baru dari queue.
4. Opsi `--isolated` menggunakan cache lock atomik untuk memastikan hanya tepat 1 node yang menjalankan migrasi database, mencegah eksekusi duplikasi saat beberapa kontainer baru boot secara bersamaan.
5. Karena container bersifat *ephemeral* (mudah dihancurkan dan dibuat ulang); jika container di-terminate, file log lokal akan musnah permanen jika tidak di-stream ke *standard output* (`php://stdout`).

#### Jawaban Intermediate
1. Replikasi database dari Primary (Master) ke Replica (Slave) membutuhkan waktu milidetik (*replication lag*). Jika user membuat record baru lalu segera di-redirect ke halaman detail, query read di replica bisa gagal menemukan data jika proses replikasi belum tuntas. Parameter `sticky` memastikan bahwa koneksi akan tetap memakai Master selama siklus lifecycle request/sesi tersebut jika operasi penulisan baru saja terjadi.
2. Octane menjaga aplikasi Laravel tetap hidup di memory (RAM) antar request tanpa me-reset engine PHP. Objek singleton atau properti class `static` yang telah dimodifikasi pada request User A tidak dibersihkan secara otomatis, sehingga berisiko terbaca atau terekspos ke request User B berikutnya.
3. Standar W3C menggunakan header `traceparent` dengan format `version-trace_id-parent_id-trace_flags` (contoh: `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`).
4. `livenessProbe` menentukan apakah container masih hidup (jika gagal, container di-*restart*). `readinessProbe` menentukan apakah container siap menerima traffic dari load balancer (jika gagal, traffic dihentikan dari node ini sementara proses inisialisasi/recovery berlangsung).
5. Queue worker berjalan secara persisten di memory. Jika tidak di-restart, worker akan terus mengeksekusi versi bytecode PHP lama yang tersimpan di OPcache/RAM sebelum image baru di-*pull*.

#### Jawaban Skenario Kasus Produksi
1. **Akar Masalah**: Cluster menggunakan `APP_KEY` yang berbeda pada pod yang baru diluncurkan dibanding pod lawas (mungkin di-generate dinamis di runtime), atau session storage masih diarahkan ke cache/disk lokal pod alih-alih Redis terpusat. Akibatnya enkripsi dekripsi payload CSRF mismatch. **Mitigasi**: Pastikan `APP_KEY` statis dan seragam via Secret Manager dan ubah `SESSION_DRIVER=redis` dengan cluster endpoint seragam.
2. **Akar Masalah**: *Connection exhaustion* pada instance Redis. Ketika jumlah pod naik 8x lipat, tiap process worker/FPM membuka koneksi TCP baru ke Redis tanpa pooling, menghabiskan limit `maxclients` Redis dan memicu penolakan koneksi. **Mitigasi**: Konfigurasikan pooling connection, perbesar limit koneksi Redis, gunakan Redis Sentinel/Cluster, atau tempatkan caching proxy layer (misal: AWS ElastiCache serverless scaling).
3. **Akar Masalah**: MySQL melakukan exclusive table lock saat mengeksekusi DDL `ALTER TABLE` pada tabel InnoDB berukuran besar, memblokir seluruh antrean transaksi DML (INSERT/UPDATE). **Mitigasi**: Gunakan tooling Online Schema Change (seperti `gh-ost` atau `pt-online-schema-change`) atau terapkan strategi *Expand/Contract*: buat tabel bayangan atau tambahkan tabel relasi baru yang terisolasi, sinkronisasikan via event listener, lalu alihkan pointer data tanpa mengunci tabel utama.

---

### 16. Summary
High Availability dan Observability pada Laravel menuntut pergeseran paradigma dari *monolithic single-server mindset* ke *distributed cloud-native architecture*. 

Aplikasi Laravel di lingkungan enterprise harus diisolasi menjadi entitas **stateless** murni, mendelegasikan state ke cluster penyimpanan terdistribusi (Redis, S3, Aurora). Seluruh siklus deployment wajib mengadopsi model **zero-downtime** melalui pemisahan siklus migrasi skema database (*Expand/Contract* pattern) dan orkestrasi container yang menangani OS signals (`SIGTERM`) secara graceful. Dengan melengkapi ekosistem runtime menggunakan standar **OpenTelemetry** dan **Structured JSON Logging**, latensi dan kegagalan aplikasi tidak lagi menjadi misteri, melainkan anomali terukur yang dapat diinvestigasi secara presisi.