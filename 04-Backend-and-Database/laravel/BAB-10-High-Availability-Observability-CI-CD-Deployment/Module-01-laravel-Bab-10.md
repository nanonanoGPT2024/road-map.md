# Bab 10 Module 01: High Availability, Observability, CI/CD & Deployment

---

## 01: Identitas Modul
* **Track:** Backend and Database Architect
* **Kategori:** 04-Backend-and-Database
* **Topik:** High Availability, Observability, CI/CD & Deployment
* **Tingkat Kesulitan:** Advanced / Enterprise Grade (Level 400)
* **Target Stack:** Laravel 11.x, PHP 8.3 FPM, Nginx, PostgreSQL/MySQL Read-Write Cluster, Redis Cluster/Sentinel, OpenTelemetry, Prometheus, Grafana, Docker, GitHub Actions, Traefik/AWS ALB.
* **Prasyarat:** Menguasai arsitektur inti Laravel, Queue Worker internals, Caching, Containerization dasar, serta administrasi Linux/Network stack.

---

## 02: Learning Objectives
Setelah menyelesaikan modul ini, peserta didik mampu:
1. Merancang dan mengimplementasikan arsitektur Laravel *Zero-Downtime* berbasis *stateless compute layer* dengan *database replication split*.
2. Membangun pipeline CI/CD deklaratif (*GitOps-ready*) menggunakan GitHub Actions untuk pengujian otomatis, static analysis, asset compilation, dan zero-downtime rolling/blue-green deployment.
3. Mengonfigurasi instrumentasi *Observability* 3-Pillar (Metrics, Logs, Traces) memanfaatkan Laravel Pulse, OpenTelemetry (OTel), Prometheus exporter, dan structured JSON logging.
4. Menangani state konsistensi, cache invalidation, serta queue draining otomatis saat deployment rilis baru.
5. Menerapkan pengamanan runtime production: secure headers, secret management, immutable infrastructure, dan zero-trust internal networking.

---

## 03: Concept Map Diagram
```
                          [ Client Request Traffic ]
                                      |
                                      v
                        [ Anycast DNS / Cloudflare ]
                                      |
                       [ TLS Termination / Ingress ]
                         (AWS ALB / Traefik Proxy)
                                      |
         +----------------------------+----------------------------+
         |                                                         |
         v                                                         v
 [ Laravel Node 01 ]                                       [ Laravel Node 02 ]
  - PHP 8.3 FPM (Stateless)                                 - PHP 8.3 FPM (Stateless)
  - OpenTelemetry Trace                                     - OpenTelemetry Trace
  - Health Endpoint (/up)                                   - Health Endpoint (/up)
         |                                                         |
         +----------------------------+----------------------------+
                                      |
     +--------------------------------+--------------------------------+
     |                                |                                |
     v                                v                                v
[ Primary DB (Write) ]      [ Replica DB (Read) ]             [ Redis Cluster ]
 - Schema Migrations         - Read-Heavy Traffic              - Distributed Session
 - Transactions              - Read-Scale                      - Cache / Mutex Locks
                             (Replica Sync <--)                - Horizon Queue Broker
                                                                       |
                                                                       v
                                                             [ Queue Worker Node ]
                                                              - Graceful Shutdown
                                                              - Telemetry Collector
```

---

## 04: Mengapa Relevan
Dalam skala enterprise, downtime sekecil apa pun berarti kehilangan revenue dan rusaknya reputasi sistem. Laravel secara tradisional sering dideploy menggunakan model *monolithic single-server*, yang menciptakan Single Point of Failure (SPOF). 

Modul ini mentransformasi aplikasi Laravel menjadi sistem terdistribusi, *cloud-native*, tahan bencana (*high availability*), transparan dalam metrik performa (*observability*), dan dapat dirilis secara independen tanpa interupsi (*zero-downtime CI/CD*). Pemahaman ini wajib dimiliki oleh Principal Engineer dan Enterprise Architect untuk menopang jutaan transaksi per hari.

---

## 05: Anatomi Konsep Inti

### 1. Stateless Compute & Ephemeral Nodes
Agar horizontal auto-scaling dapat berjalan mulus:
* **Session & Cache Storage:** Harus dialihkan dari filesystem lokal (`storage/framework/sessions`) ke *in-memory distributed datastore* (Redis Cluster).
* **Asset & File Uploads:** Dilarang menyimpan file pengguna di hard drive lokal node; wajib menggunakan S3-compatible Object Storage via Flysystem.
* **Logging:** Output stream dialihkan ke `stdout/stderr` dalam format JSON terstruktur untuk dikonsumsi Log Collector (Vector/FluentBit), bukan file lokal `laravel.log`.

### 2. Database Read-Write Splitting & Connection Handling
Laravel mendukung pemisahan koneksi database secara native. Konfigurasi `config/database.php` dipartisi menjadi `write` dan `read`:
```php
'mysql' => [
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
    'sticky' => true, // Mencegah replikasi lag membaca data basi pasca write dalam request yang sama
    // ...
],
```

### 3. Graceful Queue Draining & Zero-Downtime Releases
Deployment rilis baru tidak boleh mematikan worker seketika saat memproses task aktif.
* Sinyal `SIGTERM` / `php artisan horizon:terminate` atau `php artisan queue:restart` memberi instruksi kepada worker untuk menyelesaikan job berjalan, lalu keluar secara elegan agar container orchestrator/supervisor menaikkan container dengan kode baru.
* Migrasi skema database harus backward-compatible (metode *Expand/Contract pattern*).

### 4. Telemetry Pillars: Traces, Metrics, Logs
* **Logs:** Format JSON kontekstual yang menyertakan `trace_id`, `span_id`, dan `tenant_id`.
* **Metrics:** Prometheus endpoint yang mengekspos queue length, memory heap usage, event latency, dan HTTP status counts.
* **Traces:** Distributed Tracing OTel yang mengaitkan request HTTP masuk, DB query execution time, cache hit/miss ratio, hingga outgoing third-party API calls.

---

## 06: Panduan Implementasi Step-by-Step

### Fase 1: Konfigurasi Logging Terstruktur & Health Checks
Modifikasi `config/logging.php` untuk memancarkan log berformat JSON ke `stdout`:
```php
'channels' => [
    'stdout' => [
        'driver' => 'monolog',
        'handler' => Monolog\Handler\StreamHandler::class,
        'formatter' => Monolog\Formatter\JsonFormatter::class,
        'with' => [
            'stream' => 'php://stdout',
        ],
        'level' => env('LOG_LEVEL', 'info'),
    ],
],
```

Definisikan endpoint Health Check di `routes/web.php` (Laravel 11 menyediakan endpoint bawaan `/up`):
```php
use Illuminate\Support\Facades\Route;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Redis;

Route::get('/healthz', function () {
    try {
        DB::connection()->getPdo();
        Redis::connection()->ping();
        return response()->json([
            'status' => 'healthy',
            'timestamp' => now()->toIso8601String(),
            'version' => config('app.version', 'v1.0.0')
        ], 200);
    } catch (\Throwable $e) {
        return response()->json([
            'status' => 'unhealthy',
            'error' => $e->getMessage()
        ], 503);
    }
});
```

### Fase 2: Instrumentasi OpenTelemetry Tracing
Pasang dependensi resmi OpenTelemetry:
```bash
composer require open-telemetry/sdk open-telemetry/opentelemetry-auto-laravel
```
Konfigurasi middleware untuk menginjeksi trace context ke dalam response header dan log context.

### Fase 3: Pembuatan Immutable Docker Container
Buat multi-stage build `Dockerfile` yang mengoptimalkan cache layer, OPcache preload, serta permissions tanpa root privilege.

---

## 07: Contoh Kasus Sederhana: Observability Traced Service
Implementasi middleware global untuk menyisipkan `trace_id` di setiap request dan log entry.

```php
namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Str;
use Symfony\Component\HttpFoundation\Response;

class TraceContextMiddleware
{
    public function handle(Request $request, Closure $next): Response
    {
        $traceId = $request->header('X-Trace-Id', (string) Str::uuid());
        
        // Inject trace context ke Monolog context
        Log::withContext([
            'trace_id' => $traceId,
            'ip' => $request->ip(),
            'url' => $request->fullUrl(),
            'method' => $request->method(),
        ]);

        $response = $next($request);
        $response->headers->set('X-Trace-Id', $traceId);

        return $response;
    }
}
```

---

## 08: Implementasi Production-Grade Lengkap Kode

### 1. Multi-Stage Dockerfile (`Dockerfile`)
```dockerfile
# syntax=docker/dockerfile:1.4
FROM php:8.3-fpm-alpine AS base

# Install system dependencies & PHP extensions
RUN apk add --no-cache \
    postgresql-dev \
    libzip-dev \
    zip \
    unzip \
    linux-headers \
    $PHPIZE_GROUP_RELATED \
    && pecl install redis igbinary \
    && docker-php-ext-enable redis igbinary \
    && docker-php-ext-install pdo_pgsql pgsql pdo_mysql bcmath opcache pcntl

WORKDIR /var/www/html

# --- Vendor Build Stage ---
FROM composer:2.7 AS vendor
WORKDIR /app
COPY composer.json composer.lock ./
RUN composer install --no-dev --no-scripts --no-autoloader --prefer-dist --ignore-platform-reqs

COPY . .
RUN composer dump-autoload --optimize --classmap-authoritative --no-dev

# --- Production Runtime Stage ---
FROM base AS runtime

COPY --from=vendor /app/vendor ./vendor
COPY . .

# Konfigurasi Production OPcache & PHP-FPM
COPY ./docker/php/opcache.ini /usr/local/etc/php/conf.d/opcache.ini
COPY ./docker/php/php-fpm.conf /usr/local/etc/php-fpm.d/zz-docker.conf

# Setup non-root execution
RUN chown -R www-data:www-data /var/www/html/storage /var/www/html/bootstrap/cache \
    && chmod -R 775 /var/www/html/storage /var/www/html/bootstrap/cache

USER www-data

EXPOSE 9000
CMD ["php-fpm", "-F"]
```

### 2. OPcache Production Configuration (`docker/php/opcache.ini`)
```ini
[opcache]
opcache.enable=1
opcache.enable_cli=1
opcache.memory_consumption=256
opcache.interned_strings_buffer=16
opcache.max_accelerated_files=20000
opcache.validate_timestamps=0
opcache.save_comments=1
opcache.fast_shutdown=1
```

### 3. Production GitHub Actions CI/CD Pipeline (`.github/workflows/deploy.yml`)
```yaml
name: CI/CD Production Pipeline

on:
  push:
    branches:
      - main

permissions:
  contents: read
  id-token: write

jobs:
  test-and-analyze:
    name: Code Quality & Automated Tests
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Setup PHP Environment
        uses: shivammathur/setup-php@v2
        with:
          php-version: '8.3'
          extensions: mbstring, pdo, pdo_pgsql, redis
          coverage: none

      - name: Install Composer Dependencies
        run: composer install --prefer-dist --no-interaction --no-progress

      - name: Run Static Analysis (PHPStan)
        run: ./vendor/bin/phpstan analyse --memory-limit=2G

      - name: Execute Tests via Pest / PHPUnit
        run: php artisan test --parallel

  build-and-deploy:
    name: Build Container & Rolling Deployment
    needs: test-and-analyze
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and Push Docker Image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ghcr.io/${{ github.repository }}/app:${{ github.sha }},ghcr.io/${{ github.repository }}/app:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Trigger Rolling Deployment (SSH/K8s/ECS)
        env:
          RELEASE_VERSION: ${{ github.sha }}
        run: |
          echo "Deploying release ${RELEASE_VERSION} with zero downtime..."
          # Eksekusi deployment trigger via webhook / deployment agent
          # Contoh: kubectl set image deployment/laravel-app laravel=ghcr.io/${{ github.repository }}/app:${RELEASE_VERSION}
```

---

## 09: Diagram Alur Kerja CI/CD & Traffic Management
```
[ Developer Push ke 'main' ]
             |
             v
[ GitHub Actions Runner ]
  - Linting & PHPStan (Level 8)
  - Unit & Integration Testing
  - Multi-Stage Docker Image Build
  - Push Image ke Registry
             |
             v
[ Orchestrator Deployment Trigger ]
             |
    +--------+--------+
    | (Zero Downtime) |
    v                 v
[ Spawn New Pods/Containers v2 ]
  - Run: php artisan optimize
  - Run: php artisan migrate --force
  - Pass Healthcheck (/healthz)
             |
             v
[ Load Balancer Dynamic Switching ]
  - Shift 100% Traffic ke v2
  - Send SIGTERM ke Pods/Containers v1
             |
             v
[ Old Workers v1 Drain & Terminate ]
  - Horizon workers finish running jobs
  - Graceful Shutdown selesai
```

---

## 10: Analisis Trade-offs
| Pendekatan | Keuntungan | Kerugian / Biaya | Mitigasi |
| :--- | :--- | :--- | :--- |
| **Sticky Read-Write Split** | Mengurangi load read pada database master secara drastis. | Potensi *Replication Lag* saat data baru ditulis tapi belum sinkron di replica. | Aktifkan konfigurasi `sticky => true` di Laravel agar request yang melakukan write langsung membaca dari master. |
| **Stateless Architecture** | Horizontal scaling instan, recovery node rusak tanpa data loss. | Ketergantungan tinggi pada throughput network Redis & Object Storage. | Gunakan Redis Sentinel/Cluster performa tinggi dengan private dedicated VPC peering. |
| **Validate Timestamps = 0 (OPcache)** | Eksekusi PHP mendekati kecepatan binary murni tanpa disk I/O check. | Perubahan file PHP tidak akan dibaca sebelum PHP-FPM direstart / reload. | Jalankan `php-fpm reload` otomatis dalam siklus pipeline deployment container. |

---

## 11: Best Practices & Antipatterns

### Best Practices
* **Jalankan Cache Warming Saat Deployment:** Eksekusi `php artisan config:cache`, `php artisan route:cache`, dan `php artisan view:cache` di dalam image build atau rilis init-container sebelum menerima traffic.
* **Terapkan Read-Only Root Filesystem:** Cegah penulisan payload berbahaya langsung ke container disk; arahkan `/tmp` dan temporary path ke memory mount (`tmpfs`).
* **Non-Blocking Horizon Termination:** Pastikan `timeout` pada worker Horizon diset lebih rendah daripada container termination grace period (misal worker timeout 60s, orchestrator grace period 90s).

### Antipatterns
* ❌ **Menjalankan `php artisan migrate` di Semua Pod Bersamaan:** Mengakibatkan *race condition* dan *deadlock* pada tabel migrasi. Jalankan migrasi melalui isolated *pre-deploy release job*.
* ❌ **Menyimpan Uploaded File di `public/uploads` Lokal Node:** Menghancurkan statelessness saat cluster scale-up atau autoscaling down.
* ❌ **Menggunakan `env()` di Luar File Konfigurasi:** Ketika `config:cache` aktif, pemanggilan `env()` akan selalu mengembalikan `null`.

---

## 12: Security Hardening

```php
namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class SecurityHeadersMiddleware
{
    public function handle(Request $request, Closure $next): Response
    {
        $response = $next($request);

        $response->headers->set('X-Frame-Options', 'DENY');
        $response->headers->set('X-Content-Type-Options', 'nosniff');
        $response->headers->set('Referrer-Policy', 'strict-origin-when-cross-origin');
        $response->headers->set('Strict-Transport-Security', 'max-age=31536000; includeSubDomains; preload');
        $response->headers->set('Content-Security-Policy', "default-src 'self'; script-src 'self' 'nonce-RANDOM_SEED'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:;");

        return $response;
    }
}
```

---

## 13: Observabilitas & Debugging

### Custom Metric Exporter via Prometheus Standard
Registrasikan Prometheus middleware untuk mengukur execution latency:

```php
namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Prometheus\CollectorRegistry;
use Symfony\Component\HttpFoundation\Response;

class PrometheusMetricsMiddleware
{
    public function __construct(private CollectorRegistry $registry) {}

    public function handle(Request $request, Closure $next): Response
    {
        $start = microtime(true);
        $response = $next($request);
        $duration = microtime(true) - $start;

        $route = $request->route() ? $request->route()->uri() : 'unknown';
        
        $counter = $this->registry->getOrRegisterCounter(
            'laravel', 'http_requests_total', 'Total HTTP Requests', ['method', 'route', 'status']
        );
        $counter->inc([$request->method(), $route, (string) $response->getStatusCode()]);

        $histogram = $this->registry->getOrRegisterHistogram(
            'laravel', 'http_request_duration_seconds', 'HTTP Duration', ['route'], [0.05, 0.1, 0.25, 0.5, 1, 2.5]
        );
        $histogram->observe($duration, [$route]);

        return $response;
    }
}
```

---

## 14: Benchmarking & Performance
Verifikasi throughput node statis vs teroptimasi menggunakan `k6`:

### `loadtest.js`
```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 50 },  // Ramp-up
    { duration: '1m', target: 200 },  // Sustained high concurrency
    { duration: '20s', target: 0 },   // Cool-down
  ],
  thresholds: {
    http_req_duration: ['p(95)<200'], // 95% response harus di bawah 200ms
    http_req_failed: ['rate<0.01'],    // Error rate < 1%
  },
};

export default function () {
  const res = http.get('http://laravel-app.internal/healthz');
  check(res, {
    'status is 200': (r) => r.status === 200,
  });
  sleep(0.1);
}
```

---

## 15: Hands-on Lab Mini-Project
**Target:** Buat konfigurasi production runtime stack menggunakan Docker Compose yang mencakup:
1. Web Layer (Nginx reverse proxy).
2. App Layer (PHP 8.3-FPM Multi-worker).
3. Data Layer (Redis + MySQL Primary/Replica Simulation).

### `docker-compose.prod.yml`
```yaml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./docker/nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - app
    networks:
      - production-tier

  app:
    build:
      context: .
      target: runtime
    environment:
      APP_ENV: production
      APP_DEBUG: "false"
      CACHE_STORE: redis
      SESSION_DRIVER: redis
      QUEUE_CONNECTION: redis
      REDIS_HOST: redis
    networks:
      - production-tier

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --requirepass "SecretAuthRedisPass"
    volumes:
      - redis-data:/data
    networks:
      - production-tier

networks:
  production-tier:
    driver: bridge

volumes:
  redis-data:
```

---

## 16: Automated Testing & Verification
Tulis Pest PHP test untuk memastikan route `/healthz` merespons payload terstruktur dan status code yang valid:

```php
describe('System Health Endpoint', function () {
    it('returns 200 and healthy metadata when infrastructure is alive', function () {
        $response = $this->getJson('/healthz');

        $response->assertStatus(200)
                 ->assertJsonStructure([
                     'status',
                     'timestamp',
                     'version'
                 ])
                 ->assertJson([
                     'status' => 'healthy'
                 ]);
    });
});
```

---

## 17: Troubleshooting Guide

| Gejala Masalah | Akar Masalah (*Root Cause*) | Solusi & Tindakan Korektif |
| :--- | :--- | :--- |
| Request menghasilkan 500 error pasca deployment: `Class "..." not found` | OPcache masih meng-cache file PHP lama yang posisinya telah bergeser/dihapus. | Jalankan `php artisan opcache:clear` atau lakukan reload pada master process PHP-FPM (`kill -USR2 1`). |
| Database Write Lock / Deadlock saat deploy | Beberapa container menjalankan `php artisan migrate --force` secara simultan. | Pindahkan proses migrasi ke *isolated release step* tunggal di pipeline CI/CD sebelum deployment pods dilakukan. |
| Memory usage worker membengkak terus menerus (*Memory Leak*) | Service class menampung static state atau query log menumpuk pada long-running process. | Panggil `DB::disableQueryLog()` pada worker init, atau gunakan flag `--max-jobs=500` / `--max-time=3600` di worker command. |

---

## 18: Checklist Produksi
- [ ] `APP_DEBUG=false` dipastikan aktif pada konfigurasi runtime environment.
- [ ] Driver `session`, `cache`, dan `queue` menggunakan shared distributed instances (Redis Cluster).
- [ ] `php artisan config:cache`, `route:cache`, dan `view:cache` tereksekusi tanpa kegagalan.
- [ ] Healthcheck endpoint `/healthz` atau `/up` terintegrasi dengan load balancer probe (interval 10s, timeout 5s).
- [ ] Structured JSON logging ke `stdout` aktif dengan level `info` atau `error`.
- [ ] Distributed Tracing context (OTel / OpenTelemetry) tertanam di HTTP Header dan Database Query wrapper.
- [ ] Queue Worker dikonfigurasi dengan graceful timeout dan terikat pada process manager/orchestrator handling sinyal `SIGTERM`.

---

## 19: Ringkasan Eksekutif
Membangun High Availability dan Zero Downtime pada aplikasi Laravel menuntut transformasi arsitektur dari *stateful single server* menjadi *stateless ephemeral compute nodes*. Stateful layers didelegasikan sepenuhnya ke database cluster dengan skema *read-write split* dan *distributed cache/session memory stores*. 

Observabilitas yang dibangun di atas 3 pilar utama (Logs, Metrics, Traces) menjamin transparansi operasional secara real-time. Dengan mengintegrasikan build pipeline multi-stage Docker yang immutable dan graceful handling pada proses deployment worker, enterprise dapat mencapai availability SLA 99.99% dengan frekuensi delivery rilis harian tanpa gesekan.

---

## 20: Referensi & Bacaan Lanjutan
* **Laravel Official Documentation (11.x):** *Deployment, Octane, Horizon, and Pulse Guides.*
* **OpenTelemetry PHP Documentation:** *https://opentelemetry.io/docs/languages/php/*
* **Twelve-Factor App Methodology:** *https://12factor.net/*
* **Nygard, Michael T.** *Release It!: Design and Deploy Production-Ready Software (2nd Edition).* Pragmatic Bookshelf.
* **Turnbull, James.** *The Art of Monitoring.* Turnbull Press.