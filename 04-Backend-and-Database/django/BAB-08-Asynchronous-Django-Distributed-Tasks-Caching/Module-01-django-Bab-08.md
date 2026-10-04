# Bab 08 Module 01: Asynchronous Django, Distributed Tasks, & Caching

---

## 01 Identitas Modul
* **Mata Kuliah / Jalur**: Backend & Database Architecture
* **Kategori**: 04-Backend-and-Database
* **Kode Modul**: DJG-0801-ASYNC-TASK-CACHE
* **Level Keterampilan**: Advanced / Principal Engineer Level
* **Prasyarat**: Django ORM & Database Layer, Network Protocols (HTTP, TCP, WebSocket), Redis Internals, Concurrency Fundamentals (OS Threads, Processes, Event Loop).

---

## 02 Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. Mengonfigurasi dan mengoperasikan server ASGI (Uvicorn/Gunicorn) untuk menangani request asynchronous (`async def`) bersamaan dengan eksekusi synchronous ORM secara aman via `asgiref`.
2. Merancang arsitektur distributed task processing berbasis Celery dengan Redis/RabbitMQ sebagai message broker, menerapkan retry policy eksponensial, dead-letter queue, dan dynamic task routing.
3. Mengimplementasikan multi-tier caching strategy (Template, View, Low-Level, Per-Query) menggunakan Redis Cache backend dengan proteksi terhadap Cache Stampede (Dogpiling) dan Cache Avalanche.
4. Menerapkan locking terdistribusi (*distributed locks*) menggunakan Redis Redlock pattern untuk mencegah *race conditions* pada sistem transaksional.
5. Membangun pipeline observabilitas untuk asynchronous view latency, worker throughput, dan queue lag menggunakan Prometheus metrics serta OpenTelemetry instrumentation.

---

## 03 Concept Map Diagram ASCII
```
+---------------------------------------------------------------------------------------+
|                                    CLIENT REQUEST                                     |
+-------------------------------------------+-------------------------------------------+
                                            |
                         +------------------+------------------+
                         | ASGI / WSGI Gateway (Uvicorn/Nginx) |
                         +------------------+------------------+
                                            |
         +----------------------------------+----------------------------------+
         | (Sync HTTP / Latency-Critical)                                      | (Async I/O / Long-Polling)
         v                                                                     v
+-----------------------+                                             +-----------------------+
| Sync Django View      |                                             | Async View (async def)|
+-----------+-----------+                                             +-----------+-----------+
            |                                                                     |
            |-- [Read-Through Cache] ----> +-------------------+ <----------------+
            |                              | Redis Cache Tier  | (TTL, Invalidation, Lock)
            |-- [Sync-to-Async Bridge] --> | (Memcached/Redis) |
            |                              +-------------------+
            | (Offload Background Tasks)
            v
+-----------------------+
| Celery Task Producer  |
+-----------+-----------+
            |
            | (AMQP / Redis Protocol)
            v
+---------------------------------------------------------------------------------------+
| MESSAGE BROKER (RabbitMQ / Redis Broker)                                              |
|  +--------------------+   +--------------------+   +-------------------------------+  |
|  | High-Priority Queue|   | Default Queue      |   | Dead-Letter Queue (DLQ)       |  |
|  +---------+----------+   +---------+----------+   +---------------+---------------+  |
+------------|------------------------|------------------------------|------------------+
             |                        |                              |
             v                        v                              v
+---------------------------------------------------------------------------------------+
| CELERY WORKER POOL                                                                    |
|  +--------------------+   +--------------------+   +-------------------------------+  |
|  | Worker 1 (CPU-Bound|   | Worker 2 (I/O-Bound|   | Worker DLQ Consumer           |  |
|  | Prefork Pool)      |   | Gevent/Eventlet)   |   | (Failure Alerting/Re-drive)   |  |
|  +---------+----------+   +---------+----------+   +---------------+---------------+  |
+------------|------------------------|------------------------------|------------------+
             |                        |                              |
             +------------------------+------------------------------+
                                      |
                                      v
                        +---------------------------+
                        | CELERY RESULT BACKEND     |
                        | (Redis / Postgres RDS)    |
                        +---------------------------+
```

---

## 04 Mengapa Relevan
Model pemrosesan synchronous berbasis *thread-per-request* tradisional pada WSGI memiliki keterbatasan fundamental (*C10k Problem*). Ketika sebuah request membutuhkan operasi I/O intensif (seperti memanggil external payment gateway API, mengekspor berkas CSV ukuran gigabyte, atau melakukan query analitik kompleks), thread WSGI akan *blocked*. Ini menyebabkan:
* **Thread Starvation**: Seluruh worker pool terpakai hanya untuk menunggu I/O, menolak koneksi request baru.
* **Degradasi Latensi**: Pengguna tertahan menunggu proses background yang sebenarnya tidak diperlukan dalam response HTTP langsung.
* **Database Overload**: Ketiadaan caching layer terdistribusi memaksa setiap hit membaca disk storage database.

Modul ini mengintegrasikan **ASGI (Asynchronous Server Gateway Interface)**, **Celery Task Queues**, dan **Redis Caching Strategy** guna memisahkan *request-response cycle* dari pemrosesan background, menjamin p99 latency di bawah 100ms dan ketersediaan sistem hingga jutaan request konkruen.

---

## 05 Anatomi Konsep Inti

### 1. ASGI vs. WSGI Architecture
* **WSGI (Web Server Gateway Interface)**: Bersifat synchronous. Satu thread menangani satu request dari awal hingga selesai. Jika I/O memakan waktu 2 detik, thread tersebut tidak dapat digunakan oleh request lain selama 2 detik.
* **ASGI (Asynchronous Server Gateway Interface)**: Berbasis Python `asyncio` event loop. Mendukung protokol HTTP/1.1, HTTP/2, dan WebSockets. Ketika request mengeksekusi operasi non-blocking I/O (`await`), event loop mengalihkan eksekusi ke request lain.

### 2. Thread Safety & Database Access (`sync_to_async` / `async_to_sync`)
Django ORM secara internal bersifat synchronous dan tidak aman terhadap *thread/coroutine concurrency* tanpa penanganan khusus.
* `sync_to_async(thread_sensitive=True)`: Menjalankan eksekusi ORM di thread terdedikasi terpisah dari event loop utama, mencegah deadlocks dan *race conditions* pada context database connection pooling.

### 3. Distributed Task Queue (Celery)
* **Producer**: Django application layer yang mendelegasikan tugas (`task.delay(*args, **kwargs)`).
* **Broker**: Antrean pesan terdistribusi (RabbitMQ/Redis) yang menjamin pengiriman pesan *at-least-once*.
* **Worker**: Proses komputasi terpisah yang mengonsumsi pesan dari antrean dan mengeksekusinya.
* **Result Backend**: Storage untuk menyimpan status tugas (`SUCCESS`, `FAILURE`, `PENDING`) dan *return values*.

### 4. Advanced Caching Topologies
* **Cache-Aside (Lazy Loading)**: Aplikasi mencari data di cache; jika *miss*, query database, simpan di cache, lalu return.
* **Write-Through / Write-Invalidate**: Mutasi database memicu pembaruan atau penghapusan entry cache seketika via Django signals atau middleware.
* **Cache Stampede Defense**: Menggunakan *probabilistic early expiration* (XFetch algorithm) atau *distributed locking* via Redis untuk memastikan hanya 1 worker yang meregenerasi cache ketika expired.

---

## 06 Panduan Implementasi Step-by-Step

### Step 1: Base Environment Setup
Pastikan dependency berikut terpasang dalam environment Python Anda:
```bash
pip install django redis celery uvicorn[standard] psycopg2-binary django-redis flower
```

### Step 2: Konfigurasi ASGI pada Django
Edit `core/asgi.py`:
```python
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Inisialisasi ASGI application Django sedini mungkin
django_asgi_app = get_asgi_application()

async def application(scope, receive, send):
    if scope['type'] == 'http':
        await django_asgi_app(scope, receive, send)
    elif scope['type'] == 'websocket':
        raise NotImplementedError("WebSocket handler belum dikonfigurasi.")
    else:
        raise NotImplementedError(f"Scope type {scope['type']} tidak didukung.")
```

### Step 3: Konfigurasi Celery Core
Tambahkan file `core/celery.py`:
```python
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('core')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load auto-discovered tasks dari semua modul installed apps
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Celery Request ID: {self.request.id}')
```

Edit `core/__init__.py`:
```python
from .celery import app as celery_app

__all__ = ('celery_app',)
```

### Step 4: Konfigurasi Cache & Celery di Settings
Tambahkan ke `core/settings.py`:
```python
import os

# Caching Configuration via django-redis
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv("REDIS_CACHE_URL", "redis://127.0.0.1:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {"max_connections": 100, "retry_on_timeout": True},
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
        },
        "KEY_PREFIX": "production_cache"
    }
}

# Celery Broker & Backend Configuration
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/2")
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 Menit Hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 28 * 60  # 28 Menit Soft limit
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Fair task distribution
```

---

## 07 Contoh Kasus Sederhana

Implementasi background task pengiriman email notifikasi dan async view health-check.

### Task Definition (`notifications/tasks.py`)
```python
import time
from celery import shared_task
from django.core.mail import send_mail

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_welcome_email_task(self, user_email: str, username: str):
    try:
        # Simulasi operasi I/O pengiriman email
        print(f"Mengirim email ke {user_email}...")
        time.sleep(2)
        return {"status": "SUCCESS", "recipient": user_email}
    except Exception as exc:
        raise self.retry(exc=exc)
```

### Async Health View (`core/views.py`)
```python
import asyncio
from django.http import JsonResponse
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User

async def async_health_check(request):
    # Non-blocking sleep simulasi network I/O
    await asyncio.sleep(0.05)
    
    # Eksekusi synchronous ORM secara aman di async context
    user_count = await sync_to_async(User.objects.count, thread_sensitive=True)()
    
    return JsonResponse({
        "status": "HEALTHY",
        "active_users": user_count,
        "engine": "ASGI"
    })
```

---

## 08 Implementasi Production-Grade Lengkap Kode

Berikut adalah arsitektur sistem Invoice Processing & Financial Analytics Engine berdaya tahan tinggi, lengkap dengan caching terproteksi dari *stampede*, distributed lock, dynamic routing, dan robust error handling.

### 1. Robust Distributed Caching Layer (`analytics/cache_manager.py`)
```python
import time
import math
import random
import logging
from typing import Callable, Any
from django.core.cache import cache
from django_redis import get_redis_connection

logger = logging.getLogger(__name__)

class CacheStampedeProtectedManager:
    """
    Mengimplementasikan XFetch (Probabilistic Early Expiration)
    dan Redis Distributed Lock Pattern untuk mitigasi Cache Stampede.
    """

    @staticmethod
    def get_or_set_xfetch(key: str, compute_func: Callable[[], Any], ttl_seconds: int = 3600, beta: float = 1.0) -> Any:
        cached_data = cache.get(key)
        
        # Format cache: {'data': value, 'delta': computation_time, 'expiry': time.time() + ttl}
        now = time.time()
        
        should_recompute = False
        if cached_data is None:
            should_recompute = True
        else:
            delta = cached_data.get('delta', 1)
            expiry = cached_data.get('expiry', now + ttl_seconds)
            # Probabilistic early recomputation: -beta * delta * ln(random())
            if (now - (delta * beta * math.log(random.random()))) >= expiry:
                should_recompute = True

        if should_recompute:
            redis_client = get_redis_connection("default")
            lock_key = f"lock:{key}"
            # Acquire distributed lock (TTL 10 detik untuk proses compute)
            acquired = redis_client.set(lock_key, "locked", nx=True, ex=10)
            
            if acquired:
                try:
                    start_time = time.time()
                    fresh_data = compute_func()
                    compute_delta = time.time() - start_time
                    
                    payload = {
                        'data': fresh_data,
                        'delta': compute_delta,
                        'expiry': time.time() + ttl_seconds
                    }
                    cache.set(key, payload, timeout=ttl_seconds * 2) # Buffer TTL
                    return fresh_data
                finally:
                    redis_client.delete(lock_key)
            else:
                # Jika gagal acquire lock, return data lama jika ada (stale-while-revalidate)
                if cached_data is not None:
                    return cached_data.get('data')
                # Fallback: sleep sebentar dan baca kembali dari cache
                time.sleep(0.1)
                fallback_data = cache.get(key)
                return fallback_data.get('data') if fallback_data else compute_func()
        
        return cached_data.get('data')
```

### 2. Task Definitions dengan Dynamic Routing & DLQ (`billing/tasks.py`)
```python
import logging
from celery import shared_task
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from .models import Invoice, InvoiceStatus

logger = logging.getLogger(__name__)

class PermanentProcessingError(Exception):
    """Exception khusus untuk kegagalan deterministik (tidak perlu retry)."""
    pass

@shared_task(
    bind=True,
    name="billing.tasks.process_invoice_batch",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_kwargs={'max_retries': 5},
    retry_backoff=True,
    retry_backoff_max=600, # Max backoff 10 menit
    retry_jitter=True,     # Menghindari Thundering Herd pada backend
    queue="high_priority"
)
def process_invoice_batch(self, invoice_id: int):
    logger.info(f"Memulai pemrosesan invoice {invoice_id} | Attempt: {self.request.retries}")
    
    try:
        with transaction.atomic():
            # Mengunci row invoice dengan SELECT FOR UPDATE
            invoice = Invoice.objects.select_for_update().get(id=invoice_id)
            
            if invoice.status == InvoiceStatus.PAID:
                logger.warning(f"Invoice {invoice_id} sudah terbayar. Idempotent skip.")
                return {"status": "ALREADY_PROCESSED"}

            # Eksekusi bisnis kalkulasi kompleks
            invoice.calculate_taxes_and_discounts()
            invoice.status = InvoiceStatus.PROCESSING
            invoice.save(update_fields=['status', 'updated_at', 'total_amount'])

        # Integrasi Third-Party API Payment Gateway
        # Di luar blok atomic transaction untuk mencegah long database lock
        external_reference = execute_external_payment(invoice)

        with transaction.atomic():
            invoice = Invoice.objects.select_for_update().get(id=invoice_id)
            invoice.status = InvoiceStatus.PAID
            invoice.external_reference = external_reference
            invoice.save(update_fields=['status', 'external_reference', 'updated_at'])

        return {"status": "SUCCESS", "invoice_id": invoice_id, "ref": external_reference}

    except ObjectDoesNotExist:
        logger.critical(f"Invoice ID {invoice_id} tidak ditemukan. Membatalkan task.")
        raise PermanentProcessingError(f"Invoice ID {invoice_id} tidak valid.")

    except Exception as exc:
        logger.error(f"Error pada processing invoice {invoice_id}: {str(exc)}", exc_info=True)
        if self.request.retries >= self.max_retries:
            logger.critical(f"Task {self.request.id} melebihi batas retry. Mengirim ke DLQ alert.")
            route_to_dead_letter_handler(invoice_id, str(exc))
        raise exc

def execute_external_payment(invoice: Invoice) -> str:
    # Simulasi interaksi eksternal API
    import uuid
    return f"PAY-EXT-{uuid.uuid4()}"

def route_to_dead_letter_handler(invoice_id: int, error_reason: str):
    # Logika fallback alerting (Sentry, PagerDuty, atau Database DLQ Table)
    pass
```

### 3. Asynchronous Streaming & Reporting View (`billing/views.py`)
```python
import json
import logging
from django.http import JsonResponse, StreamingHttpResponse
from asgiref.sync import sync_to_async
from .models import Invoice
from .tasks import process_invoice_batch
from analytics.cache_manager import CacheStampedeProtectedManager

logger = logging.getLogger(__name__)

async def trigger_batch_invoice_processing(request):
    """
    Async view untuk dispatching batch task secara non-blocking.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
        invoice_ids = payload.get("invoice_ids", [])
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    dispatched_tasks = []
    for inv_id in invoice_ids:
        # Dispatching ke Celery queue
        task_signature = process_invoice_batch.delay(inv_id)
        dispatched_tasks.append({"invoice_id": inv_id, "task_id": task_signature.id})

    return JsonResponse({
        "status": "DISPATCHED",
        "total_tasks": len(dispatched_tasks),
        "tasks": dispatched_tasks
    }, status=202)

async def async_realtime_metrics(request):
    """
    Async view yang membaca data cache terproteksi dari stampede
    dan mengalirkan metrik bisnis secara efisien.
    """
    def compute_expensive_metrics():
        # Komputasi aggregasi ORM
        return {
            "total_revenue": float(Invoice.objects.filter(status='PAID').count() * 1500000),
            "generated_at": time.time()
        }

    # Wrap compute_expensive_metrics via sync_to_async
    async_cache_fetch = sync_to_async(
        CacheStampedeProtectedManager.get_or_set_xfetch,
        thread_sensitive=True
    )
    
    metrics = await async_cache_fetch(
        key="global_financial_metrics",
        compute_func=compute_expensive_metrics,
        ttl_seconds=300
    )

    return JsonResponse({"status": "SUCCESS", "metrics": metrics})
```

---

## 09 Diagram Alur Kerja ASCII

### Alur Eksekusi Task & Cache Stampede Invalidation
```
[Client Request] 
      │
      ├──────────────────────────────┐
      ▼ (POST /trigger-batch)        ▼ (GET /realtime-metrics)
+───────────────────+          +─────────────────────────────+
| Async View Engine |          | Cache Stampede Protected    |
+─────────┬─────────+          | Manager                     |
          │                    +──────────────┬──────────────+
          │ (Dispatch Task)                   │
          ▼                                   ├──── [Key Exist & Valid] ──> [Return Fast Cache]
+───────────────────+                         │
| Redis Task Broker |                         ├──── [Key Expired / Probabilistic XFetch]
+─────────┬─────────+                         │
          │                                   ▼
          ▼ (Pull Message)              +─────────────────────────────+
+───────────────────────────+           | Acquire Redis Lock (NX)     |
| Celery Worker Node        |           +──────────────┬──────────────+
| (high_priority queue)     |                          │
+─────────┬─────────────────+           +──────────────┴──────────────+
          │                             │                             │
          ├─> [DB SELECT FOR UPDATE]    ▼ (Lock Acquired)             ▼ (Lock Busy)
          │                             +--------------------+        +---------------------+
          ├─> [Call Payment Gateway]    | Sync ORM Query     |        | Return Stale Data / |
          │                             | & Rebuild Cache    |        | Wait for Resolution |
          ├─> [Update Status: PAID]     +---------┬----------+        +---------------------+
          │                                       │
          └─> [Set Cache Invalidation] ───────────┘
```

---

## 10 Analisis Trade-offs

| Pendekatan / Teknologi | Keuntungan (Pros) | Biaya & Konsekuensi (Cons) | Skenario Penggunaan yang Tepat |
| :--- | :--- | :--- | :--- |
| **ASGI Native Async Views** | Efisiensi tinggi pada high-concurrency I/O-bound views (SSE, WebSocket, external API pooling). Mengurangi footprint memori thread. | Database access (`sync_to_async`) menambahkan overhead context switching. Risiko thread deadlock jika `thread_sensitive=False`. | Micro-dashboard real-time, external API aggregator, proxy endpoints. |
| **WSGI Classic Multi-Thread** | Sangat stabil, eksekusi ORM synchronous murni tanpa *wrapper latency*, ekosistem debugging matang. | Membutuhkan alokasi resource server besar (RAM/CPU) pada lonjakan koneksi lambat (*Slowloris attacks*). | Standar monolithic CRUD internal, CPU-heavy backend computations. |
| **Celery Tasks + Redis Broker** | Skalabilitas horizontal tak terbatas, rich ecosystem (monitoring Flower, canvas workflows, auto-retry). | Kompleksitas operasional infrastruktur broker, overhead network latency serialization (JSON). | Batch processing, sending bulk email, report generation, processing order state. |
| **Probabilistic Cache (XFetch)** | Zero downtime recomputation, eliminasi 100% *Cache Stampede*, degradasi latency p99 terdistribusi rata. | Overhead komputasi kalkulasi logaritmik random pada setiap cache access. Struktur data cache membengkak karena metadata. | Metrik analitik agregasi berat dengan traffic baca mencapai ribuan hit/detik. |

---

## 11 Best Practices & Antipatterns

### Best Practices
* **Selalu Pasang Hard & Soft Time Limits**: Cegah task zombie memonopoli worker dengan menyetel `time_limit` dan `soft_time_limit`.
* **Idempotency Execution**: Desain setiap background task agar aman dieksekusi berulang kali (menggunakan UUID tracing atau database unique constraint).
* **Dedicated Task Routing**: Pisahkan queue berdasarkan SLA (`high_priority`, `low_priority`, `io_heavy`, `cpu_bound`).
* **Connection Pooling**: Aktifkan connection reuse pada Redis dan Database ORM (`CONN_MAX_AGE`).

### Antipatterns yang Dilarang
* ❌ **Passing Django Model Instances directly into Celery Tasks**:
  ```python
  # BURUK: Objek model akan stale ketika task dieksekusi di masa depan
  my_task.delay(user_instance) 
  
  # BAIK: Pass ID/Primary Key saja
  my_task.delay(user_instance.id)
  ```
* ❌ **Blocking Event Loop pada Async View**:
  ```python
  # BURUK: Menghentikan seluruh concurrent coroutine di worker ASGI
  async def bad_view(request):
      time.sleep(5) 
      return JsonResponse({})
  
  # BAIK: Gunakan async driver atau asyncio sleep
  async def good_view(request):
      await asyncio.sleep(5)
      return JsonResponse({})
  ```
* ❌ **N+1 Queries di dalam Background Task Loop**: Memproses ratusan baris data menggunakan loop synchronous individual query alih-alih `bulk_create` / `bulk_update`.

---

## 12 Security Hardening

```
+-------------------------------------------------------------------------------+
|                       SECURITY COMPLIANCE BOUNDARY                            |
+-------------------------------------------------------------------------------+
| 1. Broker Authentication: TLS v1.3 + Redis ACL (AUTH requirepass / ACL setuser)|
| 2. Payload Encryption: Celery Cryptography Serializer (AES-256 Signatures)   |
| 3. Network Isolation: Worker node berada di Private VPC (No Public IP)        |
| 4. Poison-Pill Prevention: Explicit JSON serialization (Disable Pickle)       |
+-------------------------------------------------------------------------------+
```

1. **Pickle Deserialization Vulnerability (RCE Prevention)**:
   Jangan pernah menggunakan `pickle` sebagai serializer Celery. Penyerang yang dapat memanipulasi payload broker dapat mengeksekusi *arbitrary remote code*.
   ```python
   # WAJIB di settings.py
   CELERY_ACCEPT_CONTENT = ['json']
   CELERY_TASK_SERIALIZER = 'json'
   CELERY_RESULT_SERIALIZER = 'json'
   ```

2. **Redis In-Flight Data Encryption & Access Control**:
   Gunakan TLS connection string (`rediss://`) dan Redis ACL pengguna terisolasi:
   ```python
   CACHES = {
       "default": {
           "BACKEND": "django_redis.cache.RedisCache",
           "LOCATION": "rediss://cache_user:SecureP@ssw0rd!@redis.internal.vpc:6380/1",
           "OPTIONS": {
               "CONNECTION_POOL_KWARGS": {
                   "ssl_cert_reqs": "required",
                   "ssl_ca_certs": "/etc/ssl/certs/redis-ca.pem"
               }
           }
       }
   }
   ```

3. **Rate Limiting Task Spawning**: Cegah task flooding via DoS attack dengan memanfaatkan Celery task rate limits:
   ```python
   @shared_task(rate_limit="100/m") # Maksimal 100 eksekusi per menit
   def public_endpoint_task(ip_address):
       pass
   ```

---

## 13 Observabilitas & Debugging

### Monitoring Setup (Celery Prometheus Exporter)
Ekspos metrik worker, queue lag, dan task failure rate ke Prometheus menggunakan `celery-prometheus-exporter`.

### Custom Instrumentation Middleware (`core/middleware.py`)
```python
import time
import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("performance")

class PerformanceObservabilityMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.start_time = time.time()

    def process_response(self, request, response):
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            response['X-Response-Time-Seconds'] = f"{duration:.4f}"
            
            if duration > 1.0:
                logger.warning(
                    f"SLOW TRANSACTION DETECTED: Path={request.path} | "
                    f"Duration={duration:.4f}s | Method={request.method}"
                )
        return response
```

### Structured Task Logger Setup
```python
from celery.signals import task_failure, task_prerun
import structlog

logger = structlog.get_logger("celery.tasks")

@task_prerun.connect
def task_prerun_handler(task_id, task, *args, **kwargs):
    logger.info("task_started", task_id=task_id, task_name=task.name)

@task_failure.connect
def task_failure_handler(task_id, exception, traceback, *args, **kwargs):
    logger.error(
        "task_execution_failed",
        task_id=task_id,
        exception=str(exception),
        traceback=traceback
    )
```

---

## 14 Benchmarking & Performance

Jalankan benchmarking menggunakan `wrk` atau `locust` untuk membandingkan throughput endpoint sync vs async.

### Skenario Benchmark: 10,000 Concurrent Connections
```bash
# Uji Concurrency Async ASGI View vs Sync WSGI View
wrk -t12 -c1000 -d30s --latency http://127.0.0.1:8000/api/v1/metrics/
```

### Komparasi Metrik Hasil Beban

| Metric Indicator | Django WSGI (Gunicorn 4 Workers) | Django ASGI (Uvicorn 4 Workers) | Celery Offloaded (Async Edge) |
| :--- | :--- | :--- | :--- |
| **Requests / Second (RPS)**| 420 req/s | 3,850 req/s | 11,200 req/s |
| **p50 Latency** | 230 ms | 24 ms | 6 ms |
| **p99 Latency** | 2,800 ms | 115 ms | 18 ms |
| **Failed Requests (5xx / Timeouts)**| 14.2% | 0.01% | 0.00% |
| **RAM Footprint (Avg)** | 480 MB | 210 MB | 180 MB |

---

## 15 Hands-on Lab Mini-Project

### Instruksi Mandiri:
1. Implementasikan endpoint distributed rate-limiting berbasis Redis Sliding Window Token Bucket via ASGI Middleware.
2. Buat skenario data migration 1,000,000 user record yang dieksekusi secara asinkron menggunakan Celery Chunks and Canvas Chaining (`chord`, `group`, `chain`).
3. Terapkan Cache Warming Background Worker yang secara dinamis merefresh cache setiap interval 10 menit sebelum metrik diakses oleh endpoint publik.

---

## 16 Automated Testing & Verification

Pengujian arsitektur async dan Celery tasks memerlukan penanganan mock broker dan async event loop execution.

### Test Suite (`billing/tests/test_async_and_tasks.py`)
```python
import pytest
from unittest.mock import patch, MagicMock
from django.test import AsyncClient, TestCase
from billing.tasks import process_invoice_batch
from billing.models import Invoice, InvoiceStatus

@pytest.mark.django_db
@pytest.mark.asyncio
async def test_async_realtime_metrics_endpoint():
    client = AsyncClient()
    response = await client.get("/api/v1/realtime-metrics/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "SUCCESS"
    assert "total_revenue" in payload["metrics"]

class CeleryTaskTestCase(TestCase):
    def setUp(self):
        self.invoice = Invoice.objects.create(
            status=InvoiceStatus.PENDING,
            total_amount=100000
        )

    @patch("billing.tasks.execute_external_payment")
    def test_process_invoice_batch_success(self, mock_payment):
        mock_payment.return_value = "PAY-EXT-MOCK-12345"
        
        # Eksekusi task secara direct synchronous (Celery eager simulation)
        result = process_invoice_batch.apply(args=[self.invoice.id]).get()
        
        self.assertEqual(result["status"], "SUCCESS")
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, InvoiceStatus.PAID)
        self.assertEqual(self.invoice.external_reference, "PAY-EXT-MOCK-12345")

    @patch("billing.tasks.execute_external_payment")
    def test_process_invoice_batch_retry_on_network_failure(self, mock_payment):
        mock_payment.side_effect = ConnectionError("Gateway Timeout")
        
        # Simulasi task retry
        with self.assertRaises(ConnectionError):
            process_invoice_batch.apply(args=[self.invoice.id], throw=True)
            
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, InvoiceStatus.PROCESSING)
```

---

## 17 Troubleshooting Guide

| Gejala Masalah (Symptom) | Akar Masalah (Root Cause) | Prosedur Solusi / Remediasi |
| :--- | :--- | :--- |
| **Error: `SynchronousOnlyOperation`** | Django ORM dipanggil langsung di dalam thread async coroutine tanpa synchronous-to-asynchronous bridge. | Bungkus pemanggilan ORM menggunakan `await sync_to_async(orm_operation, thread_sensitive=True)()`. |
| **Worker OOM (Out Of Memory) Crash** | Memory leak pada eksekusi task berulang atau akumulasi batch query tanpa chunking. | Konfigurasi `--max-tasks-per-child=1000` dan `--max-memory-per-child=200000` (KB) pada service worker Celery. |
| **Queue Lag Menumpuk Tajam** | Concurrency worker jenuh