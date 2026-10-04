# Bab 10 Module 01: Kontainerisasi, High Availability, & Production Deployment

---

## 01: Identitas Modul
* **Track:** Backend & Database
* **Domain:** Django Enterprise Architecture
* **Topik:** Kontainerisasi, High Availability, & Production Deployment
* **Tingkat Kesulitan:** Advanced (Level 400)
* **Prasyarat:** Pemahaman mendalam tentang arsitektur Django, ASGI/WSGI, relasional database (PostgreSQL), networking dasar (TCP/IP, HTTP/HTTPS), dan konsep orkestrasi sistem Linux.

---

## 02: Learning Objectives
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. Merancang dan mengonfigurasi *multi-stage build* Dockerfile teroptimasi yang menghasilkan *image* Django berukuran minimal, aman, dan *non-root*.
2. Membangun topologi *High Availability* (HA) menggunakan Gunicorn/Uvicorn, Nginx sebagai *reverse proxy*, PgBouncer untuk *connection pooling*, dan PostgreSQL *replicated cluster*.
3. Menerapkan konfigurasi `settings.py` yang terisolasi penuh berbasis environment, memenuhi standar *Twelve-Factor App*, serta memisahkan aset statis/media via Object Storage (S3-compatible).
4. Menyusun arsitektur *zero-downtime rolling update* dan mitigasi konkurensi migrasi database menggunakan *orchestrator-ready health checks*.
5. Mengintegrasikan sistem observabilitas terdistribusi (Prometheus, Grafana, OpenTelemetry, Sentry) dan menerapkan *CIS Benchmarks Security Hardening* pada kontainer aplikasi.

---

## 03: Concept Map Diagram
```
+-----------------------------------------------------------------------------------+
|                        INGRESS TRAFFIC / CLIENT APPLICATION                       |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|               EDGE LAYER: Cloudflare / AWS CloudFront (CDN & WAF)                 |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|            LOAD BALANCING: Nginx Reverse Proxy (SSL/TLS Termination)              |
+-----------------------------------------------------------------------------------+
                     │                                           │
       ┌─────────────┴─────────────┐               ┌─────────────┴─────────────┐
       ▼                           ▼               ▼                           ▼
+───────────────+           +───────────────+     +───────────────────────────────+
| Django Pod #1 |           | Django Pod #2 | ... | Static/Media Assets (S3/MinIO)|
| (Gunicorn WSGI|           | (Gunicorn WSGI|     +───────────────────────────────+
| + Non-root)   |           | + Non-root)   |
+───────────────+           +───────────────+
       │                           │
       └─────────────┬─────────────┘
                     ▼
+-----------------------------------------------------------------------------------+
|                 DATABASE PROXY LAYER: PgBouncer (Transaction Pool)                |
+-----------------------------------------------------------------------------------+
                     │
       ┌─────────────┴─────────────┐
       ▼                           ▼
+────────────────────────+  +────────────────────────+
| PostgreSQL Primary     |  | PostgreSQL Replica     |
| (Read/Write Operations)|─►| (Read-Only Streaming)  |
+────────────────────────+  +────────────────────────+
```

---

## 04: Mengapa Relevan
Menjalankan Django dengan perintah `python manage.py runserver` di lingkungan produksi adalah kesalahan fatal yang mengorbankan stabilitas, performa, dan keamanan. Di lingkungan *enterprise*:
* Django membutuhkan lapisan *Web Server Gateway Interface* (WSGI/ASGI) yang mampu mengelola konkurensi berbasis *pre-forked worker* atau *asynchronous event loop*.
* Beban I/O yang intensif pada PostgreSQL tanpa *connection pooling* dapat menyebabkan kehabisan koneksi (*connection starvation*) saat terjadi lonjakan trafik (*traffic spikes*).
* Kontainerisasi monolitik tanpa *multi-stage builds* menyisakan *build dependencies* (seperti compiler C/gcc) yang memperbesar ukuran *image* (meningkatkan *attack surface*) dan memperlambat proses *Continuous Integration/Continuous Deployment* (CI/CD).

Modul ini memberikan cetak biru (*blueprint*) arsitektur standar industri untuk memastikan aplikasi Django memiliki ketersediaan tinggi (*High Availability*), dapat diskalakan secara horizontal, dan tahan terhadap kegagalan infrastruktur (*fault-tolerant*).

---

## 05: Anatomi Konsep Inti

### 1. Multi-Stage Docker Builds
Pemisahan fase kompilasi dependencies (`wheels`) dengan fase *runtime*. *Runtime stage* hanya menyalin artefak biner yang diperlukan tanpa menyertakan compiler tooling (`gcc`, `musl-dev`), menghasilkan image minimalis (Distroless atau Alpine/Slim base).

### 2. WSGI/ASGI Concurrency Model
* **Gunicorn:** Master process mengelola *worker processes*. Formula kapasitas konkurensi: 
  $$\text{Workers} = (2 \times \text{CPU Cores}) + 1$$
* **Uvicorn Worker:** Menjalankan ASGI loop untuk fungsionalitas asinkron (WebSockets, Async Views).

### 3. Database Connection Pooling (PgBouncer)
Django membuka koneksi TCP baru untuk setiap worker secara *stateless*. Tanpa pooling, limit koneksi PostgreSQL (`max_connections`) akan cepat habis. PgBouncer mengimplementasikan *Transaction-level pooling* yang mendaur ulang koneksi database tepat setelah suatu query/transaksi selesai dieksekusi.

### 4. Zero-Downtime Deployment Lifecycle
* **Liveness Probes:** Memverifikasi apakah kontainer masih berjalan.
* **Readiness Probes:** Memverifikasi apakah kontainer siap menerima trafik (koneksi DB dan Cache aktif).
* **Safe Migrations:** Strategi transisi skema database tanpa *breaking changes* (aturan: Expand $\rightarrow$ Contract).

---

## 06: Panduan Implementasi Step-by-Step

### Langkah 1: Struktur Repositori Enterprise
```
django-enterprise/
├── .dockerignore
├── docker-compose.prod.yml
├── Dockerfile
├── entrypoint.sh
├── nginx/
│   └── default.conf
├── pgbouncer/
│   └── pgbouncer.ini
├── src/
│   ├── manage.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── settings/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   └── production.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   └── requirements/
│       ├── base.txt
│       └── production.txt
└── gunicorn.conf.py
```

### Langkah 2: Membangun `.dockerignore`
Kecualikan semua file yang tidak relevan untuk menjaga ukuran *build context* tetap minimal:
```
.git
.gitignore
.env
.venv
env/
venv/
__pycache__
*.pyc
*.pyo
*.pyd
.Python
htmlcov/
.tox/
.coverage
.coverage.*
.pytest_cache/
media/
static/
Dockerfile
docker-compose*.yml
README.md
```

### Langkah 3: Ekstraksi Konfigurasi Environment Variable
Gunakan `django-environ` atau `pydantic-settings` untuk membaca konfigurasi dari *kernel environment*.

---

## 07: Contoh Kasus Sederhana (Mental Model)
Visualisasi migrasi request sederhana dari Client ke Database:

1. **Client** mengirim `GET /api/v1/health/`.
2. **Nginx** menerima paket di port 80/443, memeriksa file statis. Jika path dynamic, paket dioper ke upstream `unix:/run/gunicorn.sock` atau `http://django_app:8000`.
3. **Gunicorn Master** mengarahkan request ke salah satu **Worker Process** yang sedang *idle*.
4. **Django** mengeksekusi middleware, URL routing, dan view.
5. **Django ORM** mengirim query `SELECT 1` melalui **PgBouncer** di port 6432.
6. **PgBouncer** meminjamkan satu koneksi aktif ke **PostgreSQL Primary** di port 5432.
7. Query dieksekusi, hasil dikembalikan ke Django, PgBouncer melepas koneksi kembali ke pool.
8. Gunicorn membungkus respon WSGI dan mengirimkannya kembali ke Nginx $\rightarrow$ Client.

---

## 08: Implementasi Production-Grade Lengkap Kode

### 1. `Dockerfile` (Multi-stage Build & Non-root Execution)
```dockerfile
# ==============================================================================
# Stage 1: Build dependencies and wheels
# ==============================================================================
FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY src/requirements/ /build/requirements/
RUN pip install --upgrade pip setuptools wheel
RUN pip wheel --no-deps --wheel-dir /build/wheels -r /build/requirements/production.txt

# ==============================================================================
# Stage 2: Final minimal runtime image
# ==============================================================================
FROM python:3.12-slim-bookworm AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=core.settings.production \
    PORT=8000

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Security: Create non-root system group & user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

# Copy pre-compiled wheels from builder stage
COPY --from=builder /build/wheels /wheels
COPY --from=builder /build/requirements /requirements
RUN pip install --no-cache /wheels/*

# Copy application source code
COPY --chown=appuser:appgroup ./src /app
COPY --chown=appuser:appgroup ./gunicorn.conf.py /app/gunicorn.conf.py
COPY --chown=appuser:appgroup ./entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health/readiness/ || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "-c", "gunicorn.conf.py", "core.wsgi:application"]
```

### 2. `entrypoint.sh`
```bash
#!/bin/sh
set -e

# Verifikasi kesiapan PgBouncer/Postgres sebelum lanjut
echo "==> Menunggu database online..."
while ! curl -s http://pgbouncer:6432 > /dev/null 2>&1 && ! nc -z pgbouncer 6432; do
  sleep 0.5
done
echo "==> Database terhubung."

# Jalankan command (contoh: gunicorn)
exec "$@"
```

### 3. `gunicorn.conf.py` (Kalkulasi Otomatis Worker & Telemetri)
```python
import multiprocessing
import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = int(os.getenv("GUNICORN_WORKERS", (multiprocessing.cpu_count() * 2) + 1))
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", 2))
worker_connections = 1000
timeout = 30
keepalive = 5

# Memory Leak Mitigation
max_requests = 2000
max_requests_jitter = 400

# Logging & Monitoring
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

def on_starting(server):
    server.log.info("Memulai Master Gunicorn Process...")

def worker_int(worker):
    worker.log.info(f"Worker {worker.pid} dihentikan oleh sinyal INT/QUIT.")
```

### 4. `src/core/settings/production.py`
```python
import os
import environ
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env()

DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

# Database Configuration (Routing via PgBouncer)
DATABASES = {
    "default": env.db("DATABASE_URL"),
}
DATABASES["default"]["CONN_MAX_AGE"] = 0  # Wajib 0 jika menggunakan Transaction-mode PgBouncer
DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True

# Security Headers & Hardening
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Static & Media Storage via AWS S3 / MinIO
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "storages",
    "rest_framework",
]

AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default=None)
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="us-east-1")
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}
AWS_DEFAULT_ACL = None

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
    },
    "staticfiles": {
        "BACKEND": "storages.backends.s3boto3.S3StaticStorage",
    },
}
```

### 5. `docker-compose.prod.yml`
```yaml
version: "3.8"

services:
  django_app:
    build:
      context: .
      dockerfile: Dockerfile
    restart: always
    environment:
      DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY}
      DJANGO_ALLOWED_HOSTS: "api.domain.com,nginx"
      DATABASE_URL: "postgres://${DB_USER}:${DB_PASSWORD}@pgbouncer:6432/${DB_NAME}"
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}
      AWS_STORAGE_BUCKET_NAME: ${AWS_STORAGE_BUCKET_NAME}
    depends_on:
      pgbouncer:
        condition: service_healthy
    networks:
      - backend_net
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: "1.50"
          memory: 1024M
        reservations:
          cpus: "0.50"
          memory: 512M

  pgbouncer:
    image: edoburu/pgbouncer:1.22.0
    restart: always
    environment:
      DB_USER: ${DB_USER}
      DB_PASSWORD: ${DB_PASSWORD}
      DB_HOST: postgres_primary
      DB_NAME: ${DB_NAME}
      POOL_MODE: transaction
      MAX_CLIENT_CONN: 1000
      DEFAULT_POOL_SIZE: 50
      RESERVE_POOL_SIZE: 10
      AUTH_TYPE: md5
    networks:
      - backend_net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -h 127.0.0.1 -p 6432 -U ${DB_USER}"]
      interval: 10s
      timeout: 3s
      retries: 5

  postgres_primary:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - backend_net

  nginx:
    image: nginx:1.25-alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - django_app
    networks:
      - backend_net

networks:
  backend_net:
    driver: bridge

volumes:
  pgdata:
```

### 6. `nginx/default.conf`
```nginx
upstream django_cluster {
    least_conn;
    server django_app:8000 max_fails=3 fail_timeout=10s;
}

server {
    listen 80;
    server_name api.domain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.domain.com;

    ssl_certificate /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    client_max_body_size 20M;

    location / {
        proxy_pass http://django_cluster;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_connect_timeout 30s;
        proxy_read_timeout 60s;
    }

    location /health/ {
        proxy_pass http://django_cluster;
        access_log off;
    }
}
```

---

## 09: Diagram Alur Kerja (Zero-Downtime Deployment)
```
[CI/CD Pipeline]
       │
       ├─► 1. Run Unit/Integration Tests
       ├─► 2. Build Docker Multi-Stage Image
       ├─► 3. Push Image to Private Registry (ECR/GAR)
       │
       ▼
[Deployment Controller]
       │
       ├─► 4. Apply Database Migration (Backward-Compatible)
       │      (Run isolated: django-admin migrate --noinput)
       │
       ├─► 5. Trigger Rolling Update (e.g., K8s or Docker Compose)
       │      ├── Spin up New Container Pod (v2)
       │      ├── Probe: /health/readiness/ returns 200 OK
       │      ├── Update Load Balancer Upstream (Route traffic to v2)
       │      └── Send SIGTERM to Old Container Pod (v1)
       │
       ▼
[Old Pod Graceful Shutdown]
       │
       ├─► 6. Finish executing ongoing HTTP Requests (Drain Timeout: 30s)
       └─► 7. Terminate Container v1 safely
```

---

## 10: Analisis Trade-offs

| Pendekatan / Komponen | Keuntungan | Biaya / Kerugian | Alternatif Terkait |
| :--- | :--- | :--- | :--- |
| **Multi-Stage Build** | Ukuran image minimal (~150MB vs ~900MB), serangan attack surface berkurang signifikan. | Waktu build di CI/CD sedikit lebih lama saat cache invalidasi. | Single-stage Build dengan package removal manual. |
| **PgBouncer (Transaction Pool)** | Mengurangi konsumsi RAM DB hingga 80%, mampu menangani ribuan koneksi konkuren. | Prepared Statements dan named cursors tidak didukung secara default tanpa konfigurasi khusus. | Session Pooling (PgBouncer) atau AWS RDS Proxy. |
| **Gunicorn + gthread** | Menghemat memori dibandingkan worker `sync`, efisien untuk I/O ringan. | Masih terjadi GIL blocking jika aplikasi menjalankan kalkulasi intensif CPU di thread yang sama. | `gevent` (Monkey-patching I/O) atau Uvicorn ASGI. |
| **S3 Storage untuk Static/Media** | Pod Django menjadi sepenuhnya *stateless*; skalabilitas horizontal tidak terbatas. | Latensi network ekstra untuk upload file jika tidak menggunakan Direct Pre-signed URL. | Volume Sharing via NFS/EFS (Memiliki isu performa file lock). |

---

## 11: Best Practices & Antipatterns

### Best Practices
* **Jalankan Migrasi sebagai Isolated Job:** Jangan pernah mengeksekusi `python manage.py migrate` di dalam perintah startup `CMD` kontainer aplikasi utama karena saat kontainer diskalakan (misal 5 replika bersamaan), akan terjadi *race condition* atau *table locking deadlock*.
* **Gunakan Explicit Non-Root User:** Selalu deklarasikan `USER nonroot` di Dockerfile untuk mematuhi prinsip *Least Privilege* dan mencegah privilege escalation breakout ke host kernel.
* **Terapkan Dynamic Graceful Timeout:** Konfigurasikan Gunicorn untuk menangani `SIGTERM` secara halus dengan menyelesaikan request aktif sebelum mematikan worker.

### Antipatterns
* **Antipattern: Serving Static Files via Gunicorn:** Menyajikan file statis (`.css`, `.js`, `.png`) langsung melalui Django/Gunicorn di lingkungan produksi. 
  * *Solusi:* Delegasikan aset statis ke Nginx lokal atau CDN Object Storage.
* **Antipattern: Menggunakan `DEBUG = True` di Production:** Membocorkan tracebacks lengkap, kredensial konfigurasi, dan environment variables ke user saat terjadi exception internal 500.
* **Antipattern: `CONN_MAX_AGE > 0` dengan PgBouncer Transaction Mode:** Menyebabkan koneksi stale yang terputus secara sepihak oleh pooler dan memicu error `DatabaseError: closed connection`.

---

## 12: Security Hardening (Defense-in-Depth)

1. **Docker Security Directives:**
   ```bash
   # Jalankan kontainer dengan filesystem Read-Only, kecuali direktori sementara
   docker run --read-only --tmpfs /tmp --tmpfs /run --cap-drop=ALL --cap-add=NET_BIND_SERVICE ...
   ```
2. **Kompilasi Dependencies:** Jalankan pip security audit pada pipeline CI/CD:
   ```bash
   pip install pip-audit && pip-audit -r src/requirements/production.txt
   ```
3. **HTTP Strict Transport Security (HSTS):** Memaksa browser hanya berkomunikasi melalui enkripsi TLS/HTTPS selama 1 tahun, termasuk seluruh subdomain.

---

## 13: Observabilitas & Debugging

### Implementasi Health Check View (`src/core/views.py`)
```python
from django.http import JsonResponse
from django.db import connections
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

def readiness_probe(request):
    """
    Memvalidasi koneksi ke Database dan Cache layer.
    Digunakan oleh Kubernetes/Nginx load balancer.
    """
    status = {"database": "healthy", "cache": "healthy"}
    http_code = 200

    # Test Database Connection
    try:
        db_conn = connections["default"]
        with db_conn.cursor() as cursor:
            cursor.execute("SELECT 1;")
    except Exception as e:
        logger.error(f"Readiness DB Failure: {str(e)}")
        status["database"] = "unhealthy"
        http_code = 503

    # Test Cache Connection
    try:
        cache.set("health_check_ping", "pong", timeout=5)
        if cache.get("health_check_ping") != "pong":
            raise ValueError("Cache read/write mismatch")
    except Exception as e:
        logger.error(f"Readiness Cache Failure: {str(e)}")
        status["cache"] = "unhealthy"
        http_code = 503

    return JsonResponse(status, status=http_code)

def liveness_probe(request):
    """
    Hanya memverifikasi apakah Web Server merespon permintaan HTTP.
    """
    return JsonResponse({"status": "alive"}, status=200)
```

---

## 14: Benchmarking & Performance

Jalankan uji beban menggunakan **k6** untuk menguji ketahanan konkurensi arsitektur Django + Gunicorn + PgBouncer.

### Script Load Testing: `load_test.js`
```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '30s', target: 50 },  // Ramp-up ke 50 VUs
    { duration: '1m', target: 200 },   // Spike ke 200 VUs
    { duration: '30s', target: 0 },    // Ramp-down
  ],
  thresholds: {
    http_req_duration: ['p(95)<200'],  // 95% request harus selesai di bawah 200ms
    http_req_failed: ['rate<0.01'],    // Error rate < 1%
  },
};

export default function () {
  let res = http.get('http://api.domain.com/health/readiness/');
  check(res, {
    'status is 200': (r) => r.status === 200,
  });
  sleep(0.1);
}
```

Eksekusi:
```bash
k6 run load_test.js
```

---

## 15: Hands-on Lab Mini-Project

### Skenario:
Bangun arsitektur deployment Django yang memisahkan traffic Read dan Write menggunakan PgBouncer dan Nginx Reverse Proxy secara lokal menggunakan Docker Compose.

### Task List:
1. Konfigurasikan file `Dockerfile` multi-stage build sesuai standar Seksi 08.
2. Setup PostgreSQL master instance dengan PgBouncer pooler.
3. Terapkan custom healthcheck URL di `/health/liveness/` dan `/health/readiness/`.
4. Jalankan perintah:
   ```bash
   docker compose -f docker-compose.prod.yml up --build -d --scale django_app=2
   ```
5. Verifikasi bahwa Nginx mendistribusikan request secara merata ke kedua worker container:
   ```bash
   for i in {1..10}; do curl -I http://localhost/health/readiness/; done
   ```

---

## 16: Automated Testing & Verification

Gunakan pytest untuk memvalidasi konfigurasi keamanan lingkungan produksi:

```python
# tests/test_production_settings.py
import pytest
from django.conf import settings

def test_production_security_settings():
    assert settings.DEBUG is False, "DEBUG mode tidak boleh aktif di production!"
    assert settings.SECURE_SSL_REDIRECT is True
    assert settings.SESSION_COOKIE_SECURE is True
    assert settings.CSRF_COOKIE_SECURE is True
    assert settings.SECURE_HSTS_SECONDS >= 31536000
    assert "django.middleware.security.SecurityMiddleware" in settings.MIDDLEWARE

def test_database_connection_pooling_safety():
    db_config = settings.DATABASES["default"]
    # Jika menggunakan PgBouncer transaction mode, CONN_MAX_AGE harus bernilai 0
    assert db_config.get("CONN_MAX_AGE", 0) == 0
```

Jalankan pengujian:
```bash
pytest tests/test_production_settings.py
```

---

## 17: Troubleshooting Guide

### Masalah 1: `DatabaseError: server closed the connection unexpectedly`
* **Gejala:** Muncul secara acak pada endpoint yang memproses transaksi database.
* **Akar Masalah:** Django mencoba menggunakan kembali koneksi TCP lama yang telah diputus atau di-recycle oleh PgBouncer pool timeout.
* **Solusi:** Atur `CONN_MAX_AGE = 0` pada konfigurasi `DATABASES['default']` dan nonaktifkan server-side cursors (`DISABLE_SERVER_SIDE_CURSORS = True`).

### Masalah 2: `Invalid HTTP_HOST header: 'nginx'`
* **Gejala:** Nginx membalas `Bad Request (400)` saat meneruskan request ke Gunicorn.
* **Akar Masalah:** Host header ditimpa menjadi nama upstream service dan nama tersebut tidak terdaftar di `ALLOWED_HOSTS`.
* **Solusi:** Pastikan Nginx memiliki baris `proxy_set_header Host $http_host;` dan masukkan domain publik yang valid ke `ALLOWED_HOSTS`.

### Masalah 3: Permission Denied pada Log atau Media Uploads
* **Gejala:** Kontainer crash saat startup atau gagal memproses file upload.
* **Akar Masalah:** User `appuser` (UID 10001) tidak memiliki hak akses tulis ke volume direktori lokal kontainer.
* **Solusi:** Jalankan `chown -R 10001:10001 /path/to/volume` pada host, atau gunakan Object Storage (S3) untuk file media sehingga kontainer tetap *fully stateless*.

---

## 18: Checklist Produksi

- [ ] Variabel `DEBUG` bernilai mutlak `False`.
- [ ] `SECRET_KEY` diinjeksi via environment variable rahasia (HashiCorp Vault/AWS Secrets Manager), bukan dari codebase.
- [ ] Kontainer dijalankan dengan identitas user non-root (`UID != 0`).
- [ ] Multi-stage Docker build bebas dari *build tools* (`gcc`, `g++`, `make`).
- [ ] Nginx membatasi ukuran request payload (`client_max_body_size`).
- [ ] SSL/TLS Certificate menggunakan cipher modern (TLS 1.2 / TLS 1.3).
- [ ] Database connection dikelola oleh connection pooler (misal: PgBouncer) dengan konfigurasi `CONN_MAX_AGE = 0`.
- [ ] Migrasi database otomatis dijalankan terpisah dari startup container web worker.
- [ ] Healthcheck endpoints `/health/liveness/` dan `/health/readiness/` terdaftar dan aktif.
- [ ] Seluruh log dikirim langsung ke `stdout`/`stderr` dalam format terstruktur (JSON format) untuk diolah centralized logging.

---

## 19: Ringkasan Eksekutif
Menerapkan aplikasi Django pada skala enterprise memerlukan pemisahan tanggung jawab yang jelas antara layer komputasi aplikasi, proxy, dan data persistence. 

Dengan memanfaatkan **Multi-Stage Docker Builds**, kita meminimalkan celah keamanan serta mengoptimalkan distribusi image. Penggunaan **Gunicorn** dengan thread worker yang dipadukan dengan **PgBouncer** menjamin throughput tinggi dan mencegah kegagalan database akibat bottleneck koneksi. 

Terakhir, isolasi penuh pada aset statis/media menuju **Cloud Object Storage** menjadikan kontainer Django sepenuhnya *stateless*, memungkinkan orkestrasi infrastruktur melakukan *horizontal scaling* dan *rolling updates* tanpa *downtime*.

---

## 20: Referensi & Bacaan Lanjutan
1. **Django Documentation:** *Deploying Django* — https://docs.djangoproject.com/en/stable/howto/deployment/
2. **Docker Documentation:** *Best practices for building Docker images* — https://docs.docker.com/develop/develop-images/dockerfile_best-practices/
3. **PgBouncer Architecture:** *PgBouncer Documentation & Usage* — https://www.pgbouncer.org/
4. **The Twelve-Factor App Methodology:** https://12factor.net/
5. **Nginx High-Performance Caching & Load Balancing Guide:** https://docs.nginx.com/nginx/admin-guide/load-balancer/http-load-balancer/