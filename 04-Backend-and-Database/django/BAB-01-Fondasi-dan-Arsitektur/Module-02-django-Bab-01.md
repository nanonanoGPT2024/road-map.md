# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 01: Fondasi dan Arsitektur — Django Enterprise Architecture Series**

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- **Menganalisis dan Membedah Siklus Hidup Request-Response Django**: Menginspeksi alur eksekusi internal dari socket OS, antarmuka WSGI/ASGI (`WSGIHandler`/`ASGIHandler`), pipeline middleware *onion*, URL resolver regex-tree, hingga view dispatching dan database connection lifecycle.
- **Menguasai Mekanisme Async vs Sync Runtime**: Mengimplementasikan arsitektur hybrid WSGI/ASGI, memahami batasan thread pool execution (`sync_to_async` / `async_to_sync`), dan mengeliminasi overhead context-switching pada operasi I/O bound.
- **Mendesain Arsitektur Enterprise Settings & Modularisasi Project**: Menerapkan arsitektur konfigurasi stateless berbasis *Twelve-Factor App* dengan `django-split-settings` atau dynamic environment variable injection, decoupling logic aplikasi dari infrastruktur.
- **Mengoptimalkan Database Connection Management & Pooling**: Mendiagnosis degradasi latensi yang disebabkan oleh lifecycle koneksi database default Django, mengonfigurasi `CONN_MAX_AGE`, dan mengintegrasikan PgBouncer untuk arsitektur database berskala puluhan ribu RPS.
- **Mengaudit & Menghindari Bottleneck Django Signals**: Membedah mekanisme dispatching synchronous in-memory Django Signals, mengevaluasi *weak references*, dan menggantinya dengan implementasi Domain Events berbasis explicit service layer.

---

## 2. Prerequisite
Sebelum mendalami modul ini, engineer wajib memiliki pemahaman mendalam tentang:
- **Python Lanjutan**: Profiling memory, GIL (*Global Interpreter Lock*), thread-safety, `contextvars`, asyncio event loop, dan Python descriptors.
- **Protokol Web & Jaringan**: Spesifikasi WSGI (PEP 3333), ASGI 3.0, HTTP/1.1 vs HTTP/2, TCP socket state (*TIME_WAIT*, *CLOSE_WAIT*), dan Linux epoll/kqueue.
- **Dasar Django**: Model-View-Template/Model-View-Set, dasar ORM, dan routing URLs.
- **Database Internals**: Koneksi TCP PostgreSQL/MySQL, transaksi ACID, connection exhaustion, dan locking semantics.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 WSGIHandler vs ASGIHandler: Dekonstruksi Socket Lifecycle
Ketika HTTP request masuk ke environment produksi:
1. Web server reverse-proxy (e.g., Nginx) menerima frame TCP, meneruskan request melalui Unix Domain Socket atau TCP loopback ke application server (Gunicorn/Uvicorn).
2. Worker memanggil callable target Django: `WSGIHandler` (sinkron) atau `ASGIHandler` (asinkron).
3. `django.core.handlers.wsgi.WSGIHandler`:
   - Menginisialisasi `WSGIRequest(environ)`.
   - Mengambil instance `BaseHandler` yang memegang middleware chain.
   - Mengoper objek `request` melalui pipeline middleware via pointer cascading.
4. `django.core.handlers.asgi.ASGIHandler`:
   - Membaca dictionary `scope` (berisi metadata koneksi) dan channel primitives `receive` dan `send`.
   - Mengemas HTTP stream ke dalam `ASGIRequest`.
   - Menjalankan middleware pipeline secara asinkron menggunakan coroutine stack. Jika middleware atau view berupa sync execution, Django memindahkan eksekusinya ke thread pool terpisah menggunakan `asgiref.sync.sync_to_async` (ThreadPoolExecutor) untuk mencegah blocking pada event loop utama.

```
+------------------------------------------------------------------------------------+
|                                    Nginx / ALB                                     |
+------------------------------------------------------------------------------------+
                                          |
                         Unix Domain Socket / TCP Loopback
                                          v
+------------------------------------------------------------------------------------+
|                         Application Server (Gunicorn / Uvicorn)                    |
+------------------------------------------------------------------------------------+
        |                                                            |
   (WSGI Mode)                                                  (ASGI Mode)
        v                                                            v
+-----------------------+                                  +-------------------------+
|     WSGIHandler       |                                  |       ASGIHandler       |
|  (PEP 3333 Runtime)   |                                  |    (Event Loop Loop)    |
+-----------------------+                                  +-------------------------+
        |                                                            |
        +----------------------------+-------------------------------+
                                     |
                                     v
+------------------------------------------------------------------------------------+
|                           BaseHandler: Middleware Pipeline                         |
|   Request -> Security -> Session -> Auth -> Custom -> URL Resolution -> View      |
+------------------------------------------------------------------------------------+
```

### 3.2 Middleware Onion Architecture & Contextvars
Middleware Django tidak diimplementasikan sebagai observer terisolasi, melainkan menggunakan struktur data fungsi berlapis (*onion-layered callable*). 

Pada fase inisialisasi (`BaseHandler.load_middleware`):
- Django membaca daftar `MIDDLEWARE` dari konfigurasi secara terbalik (*reverse order*).
- Setiap middleware membungkus middleware berikutnya: `handler = middleware(handler)`.
- Hasil akhirnya adalah rantai pointer eksekusi tunggal `_middleware_chain`.

```
          Request Ingress ====================================>
     +------------------------------------------------------------+
     | Middleware 1 (Outer Layer)                                 |
     |   +----------------------------------------------------+   |
     |   | Middleware 2                                       |   |
     |   |   +--------------------------------------------+   |   |
     |   |   | Middleware 3 (Inner Layer)                 |   |   |
     |   |   |   +------------------------------------+   |   |   |
     |   |   |   | View Function Execution            |   |   |   |
     |   |   |   | (URL Resolver -> Handler Execution)|   |   |   |
     |   |   |   +------------------------------------+   |   |   |
     |   |   +--------------------------------------------+   |   |
     |   +----------------------------------------------------+   |
     +------------------------------------------------------------+
          <=================================== Response Egress
```

Sebelum Python 3.7, state per-request sering disimpan via thread-local storage (`threading.local()`). Pada arsitektur asinkron modern, thread-local menyebabkan kebocoran state atau cross-contamination data karena coroutine dapat berpindah-pindah thread worker secara non-deterministik. Django core sekarang menggunakan primitif `contextvars.ContextVar` untuk mengisolasi state per execution-context (task/thread-agnostic).

### 3.3 Database Connection Engine & Lifecycle
Secara default, Django membuka koneksi database baru untuk setiap HTTP request dan menutupnya segera setelah response dikirim (`django.db.close_old_connections`).
- **Overhead**: Handshake TCP + SSL Negotiation + Authentication di PostgreSQL memakan 20ms - 70ms per request.
- **`CONN_MAX_AGE`**: Menginstruksikan Django untuk mempertahankan koneksi terbuka (*persistent connection*) hingga masa pakai mencapai $N$ detik. Koneksi tidak dibagikan antar thread atau worker; setiap thread/worker process mempertahankan koneksinya sendiri.
- **Bahaya Tersembunyi**: Jika menjalankan Gunicorn dengan 16 worker process dan masing-masing menggunakan threaded worker (misal 10 thread), maka potensi koneksi database terbuka adalah $16 \times 10 = 160$ koneksi per instance container.

### 3.4 Signal Dispatching Mechanics & Gotchas
`django.dispatch.Signal` bekerja secara **sinkronis** (*in-memory procedural execution*), bukan asinkron via message queue.
- Ketika `Signal.send()` dipanggil, Django melakukan iterasi linear pada array internal receiver:
  ```python
  # Representasi konseptual kode internal django.dispatch.dispatcher
  for receiver in self._live_receivers(sender):
      response = receiver(signal=self, sender=sender, **named)
  ```
- Jika receiver memanggil API eksternal (misal: kirim email/notifikasi), request pengguna akan terblokir (*freeze*) hingga panggilan I/O selesai atau timeout.
- Sinyal menggunakan *weak references* secara default (`weak=True`). Jika receiver dideklarasikan sebagai fungsi anonim atau fungsi lokal (closure) tanpa referensi kuat di scope modul, receiver tersebut dapat dihapus oleh Garbage Collector secara tidak terduga di tengah eksekusi program.

---

## 4. Why & What

| Fitur / Komponen | Arsitektur Standar (Development) | Arsitektur Enterprise (Produksi) | Mengapa Diperlukan? |
| :--- | :--- | :--- | :--- |
| **Settings Management** | Monolithic `settings.py` | Modular split (`base.py`, `prod.py`, `test.py`) + Environment Enforcer | Mencegah kebocoran credential, isolasi profiling, konfigurasi dinamis cloud-native container. |
| **DB Lifecycle** | `CONN_MAX_AGE = 0` (Open/Close per Request) | `CONN_MAX_AGE = 60` s/d `300` + Session/Transaction Pooler (PgBouncer) | Mengurangi connection setup latency PostgreSQL dari puluhan ms ke sub-milidetik. |
| **WSGI vs ASGI** | Gunicorn Sync Workers | Gunicorn + Uvicorn Worker (`UvicornWorker`) atau Async Custom Handler | Mencegah thread exhaustion akibat I/O blocking (Websocket, SSE, microservice calls). |
| **Event Handling** | Django `post_save` / `pre_save` signals | Domain Service Pattern + Transactional Outbox (Message Broker) | Menghindari tight coupling, latensi tersembunyi, dan eksekusi side-effect saat DB rollback. |

---

## 5. How (Workflow Detail)

### Alur Eksekusi HTTP Request Level Enterprise:
```
[Client Request]
       |
       v
[Linux Kernel TCP Socket]
       |
       v
[Nginx Reverse Proxy]  ---> (SSL Termination, Static Files, Gzip/Brotli)
       |
  (Proxy Pass via Unix Socket)
       |
       v
[Gunicorn Master Process]
       |
  (Worker Selection: Uvicorn/Sync Worker)
       |
       v
[ASGI/WSGI Application Entrypoint: get_wsgi_application()]
       |
       v
[BaseHandler: Request Middleware Pipeline]
  1. SecurityMiddleware (HSTS, SSL Redirect)
  2. CustomTraceMiddleware (Inject contextvars X-Correlation-ID)
  3. SessionMiddleware (Read session data from Redis/Cache)
  4. AuthenticationMiddleware (Lazy load user object into request.user)
       |
       v
[URL Resolver: Regex/Path Engine]
  - Iterasi Route Tree URLconf
  - Callback resolution & Type casting Path Converters
       |
       v
[View Middleware & Decorators]
  - CSRF verification, Permission classes
       |
       v
[Target Controller / View Execution]
  - Domain Service Layer Execution
  - ORM Query Construction (Lazy)
  - Connection Check (`close_old_connections`)
  - SQL Execution -> PgBouncer -> PostgreSQL
       |
       v
[Response Middleware Pipeline] (Arah terbalik / Bubbling)
  - Response transformation, Cache-Control headers
  - Metrics Collection (Prometheus latency tracking)
       |
       v
[Worker Socket Flush -> Nginx -> Client]
       |
       v
[Signals / Lifecycle Cleanup]
  - `request_finished` signal trigger
  - Evaluasi batas `CONN_MAX_AGE` (tutup socket DB jika kedaluwarsa)
```

---

## 6. Analogy & Diagram ASCII

### Analogi Middleware: Kontrol Keamanan Bandara Internasional
Bayangkan request client sebagai penumpang pesawat. 
- Gerbang Masuk: Penumpang masuk melalui Pintu Keamanan 1 (Metal Detector / SecurityMiddleware), Pintu Identitas 2 (Pengecekan Paspor / AuthenticationMiddleware), dan Gate Custom 3 (Bea Cukai / Trace ID).
- Tujuan: Penumpang sampai di Ruang Tunggu Keberangkatan (Target View).
- Arah Keluar (Response): Saat terjadi pembatalan atau arah balik, penumpang harus melewati rute yang sama dari dalam ke luar dengan urutan terbalik: Gate Custom 3 -> Pintu Identitas 2 -> Pintu Keamanan 1. Jika di Gate 2 paspor palsu (Auth gagal), penumpang langsung diputar balik ke luar tanpa pernah menyentuh Ruang Tunggu Keberangkatan.

### Diagram Arsitektur Deployment Produksi Enterprise
```
                           +------------------------+
                           |   Cloud Load Balancer  |
                           +------------------------+
                                       |
                +----------------------+----------------------+
                |                                             |
                v                                             v
     +---------------------+                       +---------------------+
     |    Nginx Ingress    |                       |    Nginx Ingress    |
     +---------------------+                       +---------------------+
                |                                             |
                +----------------------+----------------------+
                                       | (Unix Sockets)
                                       v
                     +-----------------------------------+
                     | Gunicorn Cluster (K8s Pod / EC2)  |
                     | +-------------------------------+ |
                     | | Worker 1 (Uvicorn Worker)     | |
                     | |  - ASGI Handler               | |
                     | |  - Async Contextvars          | |
                     | +-------------------------------+ |
                     | | Worker 2 (Uvicorn Worker)     | |
                     | |  - ASGI Handler               | |
                     | |  - Async Contextvars          | |
                     | +-------------------------------+ |
                     +-----------------------------------+
                             |                   |
            (Persistent conn)|                   | (Redis Protocol)
                             v                   v
                     +---------------+   +-------------------+
                     |   PgBouncer   |   |   Redis Sentinel  |
                     |  (Transaction |   |  (Session/Cache)  |
                     |    Pooling)   |   +-------------------+
                     +---------------+
                             |
                             v
                     +---------------+
                     |   PostgreSQL  |
                     |   (Primary)   |
                     +---------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Modular Production Settings Architecture
Struktur modular berbasis domain lingkungan runtime:

```
myproject/
└── settings/
    ├── __init__.py
    ├── base.py
    ├── development.py
    ├── production.py
    └── testing.py
```

`myproject/settings/base.py`:
```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party Enterprise Apps
    "rest_framework",
    # Local Apps
    "apps.core",
    "apps.banking",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.RequestTraceMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "myproject.urls"
WSGI_APPLICATION = "myproject.wsgi.application"
ASGI_APPLICATION = "myproject.asgi.application"

# Standar Security Baseline
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
```

`myproject/settings/production.py`:
```python
import os
from .base import *

DEBUG = False
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")

# Pooling Database via PgBouncer/Persistent Handler
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.environ["DB_HOST"],
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", 60)),
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "connect_timeout": 5,
            "sslmode": "require",
        },
    }
}

# Strict TLS Security Headers
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000  # 1 Tahun
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

---

### 7.2 Practical Example: Enterprise Request Tracing Middleware & Async Controller

File: `apps/core/middleware.py`
```python
import time
import uuid
import structlog
from contextvars import ContextVar
from django.utils.deprecation import MiddlewareMixin

# Isolasi konteks trace_id per coroutine/thread
trace_context: ContextVar[str] = ContextVar("trace_context", default="unknown")
logger = structlog.get_logger(__name__)

class RequestTraceMiddleware:
    """
    Middleware produksi untuk observability:
    1. Menyuntikkan X-Request-ID unik untuk didistribusikan ke log agregat.
    2. Menghitung latensi eksekusi request.
    3. Mendukung sync dan async callable secara dinamis.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        import asyncio
        self._is_coroutine = asyncio.iscoroutinefunction(get_response)

    def __call__(self, request):
        if self._is_coroutine:
            return self.__acall__(request)

        # Sync Execution Path
        start_time = time.monotonic()
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        token = trace_context.set(request_id)
        
        request.trace_id = request_id

        response = self.get_response(request)

        duration = time.monotonic() - start_time
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Seconds"] = f"{duration:.4f}"

        logger.info(
            "request_processed",
            path=request.path,
            method=request.method,
            status_code=response.status_code,
            duration=duration,
            trace_id=request_id
        )

        trace_context.reset(token)
        return response

    async def __acall__(self, request):
        # Async Execution Path
        start_time = time.monotonic()
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        token = trace_context.set(request_id)

        request.trace_id = request_id

        response = await self.get_response(request)

        duration = time.monotonic() - start_time
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Seconds"] = f"{duration:.4f}"

        logger.info(
            "async_request_processed",
            path=request.path,
            method=request.method,
            status_code=response.status_code,
            duration=duration,
            trace_id=request_id
        )

        trace_context.reset(token)
        return response
```

File: `apps/banking/views.py`
```python
import httpx
from django.http import JsonResponse
from asgiref.sync import sync_to_async
from django.views import View
from apps.banking.models import AccountLedger

class AsyncTransferStatusView(View):
    """
    Async View mengombinasikan Non-blocking Microservice I/O
    dengan Optimized Threaded ORM Lookup.
    """
    async def get(self, request, transaction_ref: str):
        # 1. Non-blocking external HTTP call
        async with httpx.AsyncClient(timeout=3.0) as client:
            try:
                upstream_resp = await client.get(
                    f"https://clearing.internal.bank/status/{transaction_ref}",
                    headers={"X-Correlation-ID": getattr(request, "trace_id", "")}
                )
                upstream_data = upstream_resp.json()
            except httpx.RequestError as exc:
                return JsonResponse({"error": "Clearing house unreachable", "detail": str(exc)}, status=503)

        # 2. Database read via sync_to_async (isolasi thread pool agar connection tidak block async loop)
        try:
            ledger_entry = await sync_to_async(
                AccountLedger.objects.select_related("account").get,
                thread_sensitive=True
            )(reference_number=transaction_ref)
        except AccountLedger.DoesNotExist:
            return JsonResponse({"error": "Transaction reference not found"}, status=404)

        return JsonResponse({
            "reference": transaction_ref,
            "account_number": ledger_entry.account.account_number,
            "amount": str(ledger_entry.amount),
            "state": ledger_entry.state,
            "clearing_status": upstream_data.get("status")
        })
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Flash-Sale Platform Tiket (45,000 RPS Peak Traffic)
*Problem*: 
Sebuah platform penjualan tiket mengalami kegagalan total (*502 Bad Gateway* dan *PostgreSQL Max Client Connections Exhaustion*) saat *flash sale* dimulai. Arsitektur lama menggunakan:
- Gunicorn sync workers: 32 container, masing-masing dengan 8 worker process ($32 \times 8 = 256$ total worker).
- `CONN_MAX_AGE = 0` (Koneksi database dibuat dan dihancurkan setiap request).
- Logika audit logging ditaruh pada Django signal `post_save`. Di dalam signal handler, dibuat pemanggilan synchronous HTTP ke service analitik eksternal.

*Root Cause Analysis (RCA)*:
1. Panggilan HTTP synchronous analitik dalam signal memakan waktu 800ms. Seluruh 256 Gunicorn worker terblokir menunggu response HTTP analitik. Request baru tertumpuk di antrean backlog Nginx, menyebabkan TCP socket timeout.
2. Saat traffic mencapai 45,000 RPS, Django berulang kali memanggil `connect()` ke PostgreSQL (45,000 TCP/SSL handshakes per detik), menghabiskan CPU PostgreSQL hingga 100% hanya untuk inisialisasi koneksi.

*Solusi Arsitektural*:
1. **Eliminasi Signal untuk Panggilan Eksternal**: Menghapus `post_save` signal. Menggantinya dengan **Transactional Outbox Pattern**. Record event disimpan ke tabel database lokal dalam satu transaksi ACID, lalu dibaca oleh worker Celery/Kafka terpisah secara background.
2. **Koneksi Pooling Layer**: Mengimplementasikan **PgBouncer** di depan PostgreSQL dengan mode `pool_mode = transaction`.
3. **Optimasi Django Connection**:
   - Di Django: Mengatur `CONN_MAX_AGE = 300` detik dan `CONN_HEALTH_CHECKS = True`. Django menahan koneksi ke PgBouncer.
   - PgBouncer mendistribusikan puluhan ribu virtual client connections ke hanya 150 koneksi fisik langsung ke PostgreSQL core engine.
4. **Worker Migration**: Mengganti worker Gunicorn dari `sync` ke hybrid `UvicornWorker` untuk endpoint I/O intensif, membebaskan kapasitas worker pool.

*Hasil*:
Throughput sistem meningkat dari 1,800 RPS (sebelum crash) menjadi 45,000 RPS stabil. P99 Latency turun drastis dari 4.2 detik ke 48 milidetik. Utilisasi CPU PostgreSQL turun dari 100% ke 32%.

---

## 9. Trade-offs

| Pendekatan | Keuntungan | Kerugian / Risiko | Skenario Pemilihan |
| :--- | :--- | :--- | :--- |
| **WSGI (Gunicorn Sync)** | Stabil, isolasi memori per process kuat, debug stack-trace deterministik, kompatibilitas 100% dengan ekosistem library lawas. | Tidak tahan terhadap I/O blocking. Membutuhkan jumlah worker besar untuk throughput tinggi, konsumsi RAM besar. | Aplikasi CPU-bound murni, standard CRUD internal perusahaan dengan concurrency rendah hingga menengah. |
| **ASGI (Uvicorn / Daphne)** | Concurrency sangat tinggi pada operasi I/O bound (streaming, WebSocket, third-party API calls), jejak RAM lebih kecil. | Risiko event loop terblokir jika developer secara tidak sengaja memanggil sync library blocking, debugging async trace lebih rumit. | High-traffic API gateways, microservices integration, real-time messaging, platform agregator. |
| **Django Persistent Connections (`CONN_MAX_AGE > 0`)** | Menghilangkan overhead latency TCP/SSL handshake database tanpa infrastruktur tambahan. | Jika tanpa PgBouncer, berpotensi meledakkan limit `max_connections` PostgreSQL ketika auto-scaling container bertambah banyak. | Skala medium (hingga ~3,000 RPS) dengan jumlah worker processes yang terkontrol ketat. |
| **External Connection Pooler (PgBouncer)** | Mendukung puluhan ribu koneksi client simultan dengan overhead engine DB minimal. | Fitur PostgreSQL tertentu (seperti `PREPARE` statement terikat session, LISTEN/NOTIFY, atau temporary tables) tidak didukung pada Transaction Pooling mode. | Skala enterprise, traffic burst tinggi, auto-scaling Kubernetes dengan ratusan replica pod. |
| **Django Signals vs Service Layer** | Loosely coupled secara konseptual, mudah dipasang di aplikasi modular kecil. | Implicit execution (aliran kode sulit dilacak), rawan race-condition, synchronous blocking, berisiko dieksekusi saat transaksi belum commit. | Service Layer eksplisit selalu lebih dipilih untuk enterprise; sinyal hanya untuk internal core third-party library caching. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Event Loop Starvation dalam ASGI
*Kesalahan*: Menggunakan ORM default atau fungsi synchronous blocking di dalam async view tanpa membungkusnya dengan `sync_to_async`.
```python
# FATAL: Memblokir seluruh event loop thread!
async def bad_view(request):
    data = Account.objects.filter(is_active=True).first() # Blocking call!
    return JsonResponse({"id": data.id})
```
*Solusi*: Gunakan API ORM asinkron resmi Django (`afirst()`, `aget()`) atau bungkus eksplisit.
```python
async def good_view(request):
    data = await Account.objects.filter(is_active=True).afirst()
    return JsonResponse({"id": data.id})
```

### 10.2 Database Connection Leakage pada Background Threads
*Kesalahan*: Menjalankan operasi database di thread buatan manual (`threading.Thread`) tanpa menutup koneksi secara eksplisit. Django mengaitkan koneksi database ke thread ID. Karena thread manual tidak memicu sinyal `request_finished`, socket koneksi akan menggantung (*leak*) selamanya.
*Troubleshooting*:
```python
import threading
from django.db import connection

def safe_worker():
    try:
        # Lakukan operasi DB
        pass
    finally:
        connection.close() # WAJIB dipanggil secara manual pada custom background thread!

t = threading.Thread(target=safe_worker)
t.start()
```

### 10.3 Signal Handlers Menembus Batas Rollback Transaksi
*Kesalahan*: Mengirim event eksternal pada sinyal `post_save` yang dieksekusi sebelum transaksi database utama di-commit. Jika transaksi di-rollback setelah error berikutnya, event eksternal sudah terlanjur terkirim (*phantom state*).
*Solusi*: Gunakan `transaction.on_commit`:
```python
from django.db import transaction

def on_account_created(sender, instance, created, **kwargs):
    if created:
        transaction.on_commit(lambda: push_to_kafka_broker(instance.id))
```

---

## 11. Best Practices (Production Checklist)

1. [ ] **Non-root Container User**: Pastikan process Django di container berjalan di bawah `uid:gid` non-root (misal: `appuser:appgroup`).
2. [ ] **Formula Konfigurasi Worker**: Gunakan formula standar industri untuk WSGI sync worker:
   $$\text{Workers} = (2 \times \text{CPU Cores}) + 1$$
   Untuk async worker (Uvicorn), isolasi 2 s/d 4 worker per container pod, biarkan K8s Horizontal Pod Autoscaler (HPA) mengontrol penskalaan.
3. [ ] **Koleksi Database Health Check**: Aktifkan `CONN_HEALTH_CHECKS = True` pada Django $\ge 4.1$ jika menggunakan `CONN_MAX_AGE` untuk mendeteksi koneksi TCP stale yang diputus firewall sebelum eksekusi query.
4. [ ] **Stateless Storage**: Larang keras upload file media ke filesystem lokal container. Gunakan abstraction layer `django-storages` ke S3/GCS.
5. [ ] **Explicit Outbound Timeouts**: Pastikan seluruh external network request via `requests` atau `httpx` memiliki timeout ketat (maksimum connect: 1.5 detik, read: 3.0 detik).
6. [ ] **Structured Logging**: Konfigurasikan library seperti `structlog` untuk mengeluarkan format JSON langsung ke stdout agar mudah di-ingest oleh vector/Fluentd ke ElasticSearch/Datadog.

---

## 12. Hands-on Practice

Buatlah implementasi project yang menonaktifkan konfigurasi default, mengonfigurasi split-settings, middleware terisolasi context, dan endpoint hybrid sync/async. Simpan file-file berikut pada folder: `hands-on/m02/`.

### Struktur Direktori:
```
hands-on/m02/
├── Dockerfile
├── docker-compose.yml
├── manage.py
├── config/
│   ├── __init__.py
│   ├── asgi.py
│   ├── wsgi.py
│   └── settings/
│       ├── __init__.py
│       ├── base.py
│       └── production.py
└── core/
    ├── __init__.py
    ├── middleware.py
    └── views.py
```

### Langkah 1: Base Configuration
Buat file `config/settings/base.py`:
```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "fallback-secret-for-dev-only-32bytes-min")
DEBUG = False
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.EnterpriseCorrelationMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"
WSGI_APPLICATION = "config.wsgi.application"
```

### Langkah 2: Production Configuration
Buat file `config/settings/production.py`:
```python
from .base import *
import os

DEBUG = False
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3", # Gunakan SQLite memory-mode untuk simulasi hands-on mandiri
        "NAME": BASE_DIR / "prod.sqlite3",
        "CONN_MAX_AGE": 120,
    }
}
```

### Langkah 3: Correlation ID Middleware
Buat file `core/middleware.py`:
```python
import uuid
import contextvars
from django.utils.deprecation import MiddlewareMixin

request_id_var = contextvars.ContextVar("request_id", default="")

class EnterpriseCorrelationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.correlation_id = req_id
        request_id_var.set(req_id)

    def process_response(self, request, response):
        req_id = getattr(request, "correlation_id", "unknown")
        response["X-Request-ID"] = req_id
        return response
```

### Langkah 4: Async Engine Verification View
Buat file `core/views.py`:
```python
import asyncio
from django.http import JsonResponse
from core.middleware import request_id_var

async def healthz_async(request):
    current_trace = request_id_var.get()
    # Non-blocking pause simulasi Async I/O engine
    await asyncio.sleep(0.05)
    return JsonResponse({
        "status": "healthy",
        "engine": "asgi_coroutine",
        "trace_id": current_trace
    })
```

---

## 13. Exercise

### Level Easy
Modifikasi file `core/middleware.py` untuk mengukur durasi waktu pemrosesan view secara presisi hingga microsecond. Sisipkan durasi tersebut ke dalam response header `X-Process-Time-Microseconds`.
*Kriteria Penerimaan*:
- Header terpasang di setiap response HTTP (baik view sukses 200 maupun error 404/500).
- Waktu diukur menggunakan `time.perf_counter()`.

### Level Medium
Buat sebuah decorator `@idempotent_consumer(cache_ttl_seconds=60)` yang membungkus Django View. Decorator harus mengekstrak header `X-Idempotency-Key`. Jika key yang sama dikirimkan dua kali dalam jangka waktu TTL, kembalikan HTTP response yang dicache langsung tanpa mengeksekusi view controller lagi.
*Kriteria Penerimaan*:
- Menggunakan `django.core.cache.cache`.
- Penanganan race-condition menggunakan `cache.add` (atomic primitive) untuk locking key selama eksekusi.

### Level Hard
Implementasikan custom WSGI Middleware di luar Django application pipeline (ditaruh langsung di `config/wsgi.py`) yang mengimplementasikan circuit breaker sederhana: jika rasio response 5xx dari Django mencapai lebih dari 50% dalam 100 request terakhir, middleware harus langsung memutus koneksi dan merespons client dengan statis `503 Service Temporarily Unavailable` tanpa memanggil Django `WSGIHandler`.
*Kriteria Penerimaan*:
- Dibangun langsung di level interface PEP 3333 (menerima `environ`, `start_response`).
- Menggunakan rolling sliding window berbasis memory `collections.deque` yang thread-safe.

---

## 14. Challenge

Rancang arsitektur micro-service transaction processing sistem lelang (*bidding engine*) menggunakan Django yang mampu menangani event burst 15,000 bids per detik pada satu item lelang tanpa mengalami deadlock transaksi database.

**Parameter & Batasan Sistem**:
1. Penawaran harga (*bid*) tidak boleh hilang, tidak boleh double charge, dan harus diproses strictly sequenced (sesuai urutan kedatangan).
2. Django ORM standar dengan `select_for_update()` murni pada baris database item lelang akan mengakibatkan *lock contention* parah dan database pool exhaustion.
3. Anda diminta membuat proposal blueprint teknis komprehensif yang menjelaskan:
   - Bagaimana request diterima di edge layer (Reverse Proxy -> Worker Pool Django).
   - Strategi offloading transactional concurrency: Apakah menggunakan atomic in-memory processing (Redis Lua scripting) digabungkan dengan delayed database writeback, atau Actor model?
   - Skema mitigasi kegagalan: Bagaimana jika node Redis atau worker Django mati mendadak di tengah proses bidding?
   - Sketsa kode untuk custom Middleware dan View handler penanganan transaksi ini dengan zero database lock-wait timeout.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. **Apa perbedaan mendasar antara spesifikasi PEP 3333 (WSGI) dan ASGI pada Django?**
   - A. WSGI berbasis event loop asinkron, ASGI berbasis multi-process synchronous.
   - B. WSGI dirancang untuk arsitektur sinkronis synchronous single-request-per-worker, sedangkan ASGI mendukung antarmuka asinkron (HTTP, WebSocket) yang berjalan di atas event loop.
   - C. WSGI tidak mendukung middleware, sedangkan ASGI mewajibkan middleware.
   - D. WSGI berjalan di Nginx, ASGI hanya bisa dijalankan di Apache.

2. **Apa yang terjadi secara default pada koneksi database PostgreSQL jika parameter `CONN_MAX_AGE` tidak dikonfigurasi (bernilai 0)?**
   - A. Koneksi disimpan selamanya sampai PostgreSQL dimatikan.
   - B. Koneksi dibuka di awal request dan ditutup segera setelah request selesai via handler `request_finished`.
   - C. Terjadi memory leak pada pool database.
   - D. Django menggunakan PgBouncer secara otomatis.

3. **Di mana middleware pertama kali didefinisikan untuk membungkus seluruh siklus eksekusi aplikasi?**
   - A. Di dalam method `save()` pada Model.
   - B. Di dalam file `urls.py`.
   - C. Di dalam variabel tuple/list `MIDDLEWARE` pada settings project.
   - D. Pada decorator `@login_required`.

4. **Apakah Django Signal `post_save` dieksekusi secara asinkron di background thread terpisah secara default?**
   - A. Ya, berjalan otomatis pada thread terpisah via threading Python.
   - B. Ya, berjalan otomatis di message queue Celery.
   - C. Tidak, Django Signals dieksekusi secara sinkron dan in-memory pada thread yang sama yang memanggil `save()`.
   - D. Bergantung pada apakah database yang digunakan PostgreSQL atau MySQL.

5. **Mengapa thread-local storage (`threading.local`) berbahaya digunakan pada arsitektur Django ASGI modern?**
   - A. Karena thread-local storage menghabiskan kuota koneksi internet.
   - B. Karena pada arsitektur asinkron, eksekusi satu request coroutine dapat berpindah thread pada thread-pool runtime, menyebabkan potensi pembacaan state request yang salah (cross-leak).
   - C. Karena thread-local tidak didukung oleh Python 3.
   - D. Karena database PostgreSQL tidak mengenali thread-local.

---

### Bagian 2: Intermediate (5 Pertanyaan)
6. **Kapan instance dari middleware class diinisialisasi oleh Django?**
   - A. Setiap kali HTTP request baru masuk ke server.
   - B. Hanya satu kali pada saat server process pertama kali boot dan menjalankan startup sequence (`BaseHandler.load_middleware`).
   - C. Setiap kali URL resolver menemukan routing yang cocok.
   - D. Setiap kali transaksi database di-commit.

7. **Pada kasus Django di balik proxy (seperti Cloudflare atau Nginx Ingress), setting apa yang wajib diaktifkan agar method `request.is_secure()` mendeteksi protokol HTTPS dengan benar?**
   - A. `DEBUG = False`
   - B. `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')`
   - C. `CSRF_COOKIE_SECURE = False`
   - D. `CONN_HEALTH_CHECKS = True`

8. **Apa dampak langsung pemanggilan fungsi sinkronis murni yang membutuhkan waktu 5 detik (misal: `requests.get()`) di dalam sebuah Django Async View (`async def`)?**
   - A. View langsung memunculkan syntax error saat runtime.
   - B. Seluruh event loop thread worker terblokir selama 5 detik, mencegah coroutine request pengguna lain diproses pada thread tersebut.
   - C. Django secara otomatis mengonversi library `requests` menjadi non-blocking call.
   - D. Gunicorn worker langsung dihentikan oleh sistem operasi melalui SIGKILL.

9. **Apa fungsi utama dari konfigurasi `CONN_HEALTH_CHECKS = True` yang diperkenalkan pada Django 4.1?**
   - A. Menghapus data transaksi lama secara otomatis dari storage.
   - B. Memverifikasi keabsahan dan keaktifan socket koneksi DB yang di-pool sebelum mengeksekusi query, mencegah exception jika socket telah diputus sepihak oleh database/firewall.
   - C. Melakukan auto-repair table jika terjadi index corruption.
   - D. Mengubah engine SQLite menjadi PostgreSQL secara otomatis.

10. **Perhatikan kode berikut: `transaction.on_commit(callback)`. Mengapa pendekatan ini lebih disukai daripada mengeksekusi side-effect di dalam Django Signal `post_save`?**
    - A. Karena `on_commit` berjalan lebih lambat sehingga hemat CPU.
    - B. Karena `on_commit` menjamin callback hanya dieksekusi jika dan hanya jika transaksi database induk berhasil di-commit secara permanen ke storage engine.
    - C. Karena `on_commit` tidak membutuhkan database driver.
    - D. Karena sinyal `post_save` sudah dihapus dari standar Django.

---

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario Kasus Database Exhaustion**:
    Aplikasi Django enterprise Anda dideploy di Kubernetes dengan Horizontal Pod Autoscaler (HPA) yang melakukan scaling dari 5 pod ke 40 pod saat load tinggi. Konfigurasi setiap pod menggunakan 4 Gunicorn sync workers dengan parameter `CONN_MAX_AGE = 600`. Limit `max_connections` PostgreSQL Anda adalah 120. Saat traffic melonjak, seluruh pod melaporkan error `OperationalError: FATAL: remaining connection slots are reserved for non-replication superuser connections`.
    *Mengapa hal ini terjadi dan bagaimana arsitektur yang benar untuk memperbaikinya tanpa menaikkan limit PostgreSQL ke angka yang membahayakan RAM server?*

12. **Skenario Latency Spike pada Logging**:
    Sebuah aplikasi perbankan berbasis Django mencatat peningkatan latency P99 dari 20ms ke 1.2 detik saat volume transaksi naik. Tim audit menemukan bahwa sebuah Middleware kustom dipasang untuk mencatat setiap HTTP body payload ke table database audit:
    ```python
    class AuditLogMiddleware:
        def __init__(self, get_response):
            self.get_response = get_response
        def __call__(self, request):
            response = self.get_response(request)
            AuditLog.objects.create(url=request.path, payload=request.body)
            return response
    ```
    *Analisis minimal 2 kelemahan fatal arsitektur middleware di atas yang menyebabkan lonjakan latensi, serta tuliskan perbaikan solusinya.*

13. **Skenario Async Memory Contamination**:
    Pada sebuah aplikasi Django berbasis ASGI, tim developer melaporkan insiden keamanan kritis: Pengguna A secara acak dapat melihat data profil Pengguna B pada response endpoint async. Diidentifikasi terdapat class singleton helper yang menyimpan current context user menggunakan variabel class internal:
    ```python
    class SecurityContextHolder:
        _current_user = None
        @classmethod
        def set_user(cls, user):
            cls._current_user = user
        @classmethod
        def get_user(cls):
            return cls._current_user
    ```
    *Jelaskan akar penyebab insiden keamanan ini dalam konteks ASGI event loop runtime, dan apa mekanisme native Python yang harus digunakan untuk mengatasinya secara aman?*

---

### Kunci Jawaban & Evaluasi

#### Bagian 1: Basic
1. **B**: WSGI (PEP 3333) merupakan standar sinkronis per request, sedangkan ASGI (Asynchronous Server Gateway Interface) menangani eksekusi asinkron berbasis coroutine/event loop.
2. **B**: Secara default (`CONN_MAX_AGE = 0`), Django membersihkan dan menutup koneksi database pada akhir setiap lifecycle HTTP request.
3. **C**: Konfigurasi middleware dipasang pada array `MIDDLEWARE` di file settings, yang kemudian dimuat secara berantai oleh handler Django saat start.
4. **C**: Sinyal Django berjalan in-memory secara synchronous pada thread/eksekusi pemanggil, kecuali jika developer secara eksplisit mendistribusikannya ke queue asinkron eksternal.
5. **B**: Coroutine async dapat berpindah-pindah thread OS secara dinamis saat proses context switching IO; thread-local storage akan mengikat data ke thread ID, bukan ke alur request, menghasilkan *race-condition* antar user.

#### Bagian 2: Intermediate
6. **B**: Django menginisialisasi middleware class chain hanya sekali saat bootstrap aplikasi (boot time) demi efisiensi resource.
7. **B**: Proxy seperti AWS ALB atau Nginx menyematkan header `X-Forwarded-Proto`. Nilai konfigurasi tersebut memberi tahu Django untuk mempercayai header upstream tersebut dalam menentukan enkripsi SSL.
8. **B**: Single thread event loop worker tidak dapat menjalankan event lain jika terjadi blocking call OS; seluruh concurrent requests lain yang menumpang pada worker tersebut akan tertahan (*starved*).
9. **B**: `CONN_HEALTH_CHECKS` melakukan ping test ringan pada koneksi pool yang ada sebelum menggunakannya kembali untuk mendeteksi apakah koneksi telah mati di sisi network/DB server.
10. **B**: Menjalankan action/side-effects via `transaction.on_commit` mencegah terjadinya bug di mana notifikasi/event terkirim padahal status di database mengalami kegagalan/rollback di akhir transaksi.

#### Bagian 3: Skenario Kasus Produksi
11. **Analisis Solusi Kasus 11**:
    - *Akar Masalah*: Potensi koneksi Django ke PostgreSQL adalah: $\text{Pods} \times \text{Workers} \times (\text{Thread/DB per process}) = 40 \times 4 \times 1 = 160$ koneksi persisten. Angka ini melebihi `max_connections = 120` PostgreSQL, menyebabkan connection starvation.
    - *Solusi Arsitektural*: 
      1. Turunkan atau pasang layer middleware connection pooler seperti **PgBouncer** di antara Pod dan database PostgreSQL menggunakan `pool_mode = transaction`.
      2. Dengan PgBouncer, 40 Pod (160 koneksi Django client) dapat di-multiplexing secara aman ke hanya $10 - 20$ koneksi database real, menghilangkan error socket exhaustion tanpa menambah beban memory RAM pada server database.

12. **Analisis Solusi Kasus 12**:
    - *Kelemahan Fatal*:
      1. Operasi write DB synchronous (`AuditLog.objects.create`) disisipkan langsung pada alur kritis HTTP egress. Latensi request bertambah dengan waktu eksekusi IO insert database.
      2. Jika database mengalami slow lock, waktu request user melonjak tajam.
      3. Akses `request.body` secara naif dapat menyebabkan issue jika request payload berupa multipart stream file ukuran besar (mengonsumsi memori besar seketika).
    - *Solusi*:
      Keluarkan proses audit log dari request lifecycle Django menggunakan background asynchronous logging: Dorong log payload ke stream message queue lokal (Redis buffer, Kafka, atau async Celery worker) atau catat ke local stdout log file terstruktur, yang kemudian di-ship ke external storage secara asynchronous via daemon log collector (e.g., Vector/Promtail).

13. **Analisis Solusi Kasus 13**:
    - *Akar Masalah*: Variable class (`cls._current_user`) bersifat global dan dibagi (*shared state*) ke seluruh worker process di memori. Dalam ASGI runtime, banyak request diproses secara bersamaan oleh event loop yang sama. Ketika Request A memanggil `set_user(UserA)`, lalu terjadi operasi async blocking (misal: await DB), Request B masuk dan memanggil `set_user(UserB)`. Saat Request A resume kembali, variabel class sudah tertimpa oleh data Pengguna B.
    - *Solusi Perbaikan*: Ganti penyimpanan state global class dengan `contextvars.ContextVar`. Primitif `ContextVar` di Python secara native menjamin isolasi variabel di level execution context coroutine/task, sehingga perpindahan context async tidak akan pernah mencemari data antar request coroutine yang berbeda.

---

## 16. Summary

1. **Request Lifecycle Orchestration**: Jalur request Django adalah proses cascading berlapis. Memahami pemisahan antara web server gateway (WSGI/ASGI), middleware onion chain, dan controller view execution adalah kunci mendiagnosis degradasi latency sistem secara saintifik.
2. **Sync vs Async Runtime Boundary**: Menjalankan Django pada mode ASGI memberikan skalabilitas masif untuk throughput I/O bound, namun membutuhkan disiplin isolasi konteks eksekusi (`contextvars`) dan pencegahan synchronous blocking calls di dalam event loop.
3. **Database Connection Engineering**: Arsitektur enterprise wajib mengontrol lifecycle koneksi database melalui kalkulasi akurat worker footprint, pemanfaatan `CONN_MAX_AGE` yang dikombinasikan dengan health checks, dan penggunaan pooling layer eksternal (seperti PgBouncer) untuk skala tinggi.
4. **Decoupled Architecture**: Hindari penggunaan Django Signals untuk logika bisnis penting atau operasi synchronous eksternal. Gunakan Service Layer eksplisit yang dikombinasikan dengan Transactional Outbox Pattern guna menjamin data integrity dan fault tolerance tingkat tinggi.