# Kurikulum Rekayasa Perangkat Lunak Enterprise: Django Core & Architecture
## Bab 10: Kontainerisasi, High Availability & Production Deployment
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Menganalisis dan mengonfigurasi model konkurensi runtime WSGI/ASGI (Gunicorn/Uvicorn) berdasarkan profiling karakteristik I/O-bound vs CPU-bound pada aplikasi Django.
- Merancang arsitektur kontainer *multi-stage production-grade* berbasis non-root user dengan optimasi caching layer, minimal surface attack, dan image footprint di bawah 150MB.
- Mengimplementasikan pola High Availability (HA) pada Kubernetes, mencakup integrasi zero-downtime deployment (RollingUpdate), lifecycle hooks (`preStop`), serta kalibrasi *liveness*, *readiness*, dan *startup probes*.
- Mengatasi *connection exhaustion* pada layer database melalui arsitektur PgBouncer session/transaction pooling yang disinkronkan dengan lifecycle TCP Django persistent connections (`CONN_MAX_AGE`).
- Mengisolasi dan memvalidasi penanganan UNIX signals (`SIGTERM`, `SIGQUIT`, `SIGHUP`) untuk memastikan zero-dropped requests selama proses scaling dan rolling deploy.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, engineer wajib menguasai:
- **Django Core Internals**: Siklus request-response, middleware execution chain, dan mekanisme ORM database routing/connection pool bawaan Django 4.2/5.0+.
- **Sistem Operasi & Jaringan**: Model proses POSIX (forking, IPC, file descriptors), TCP handshake, lifecycle socket UNIX domain vs TCP socket, dan signal handling.
- **Docker Engine**: OCI standard, Union File Systems (OverlayFS), cgroups v2, namespace isolation, dan build cache engine (BuildKit).
- **Dasar Kubernetes**: Pods, Deployments, Services, ConfigMaps, Secrets, dan konsep Ingress Controller.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. WSGI/ASGI Concurrency Runtime Architecture
Django pada dasarnya bersifat synchronous-first dengan kapabilitas asynchronous yang terus berkembang. Ketika dijalankan di production, Django tidak menangani socket HTTP secara langsung, melainkan bergantung pada WSGI (*Web Server Gateway Interface*, PEP 3333) atau ASGI (*Asynchronous Server Gateway Interface*).

```
[ Ingress Controller (Nginx / Envoy / ALB) ]
                       │
       HTTP/2 or HTTP/1.1 over TLS (Public)
                       │
                       ▼
           [ Upstream Reverse Proxy ]
                       │
       HTTP/1.1 over Cleartext (Private Pod Network)
                       │
                       ▼
          [ Master Process (Gunicorn) ]
           ├─ Arbiter Loop (Signal Handler: HUP, TERM, CHLD)
           ├─ Worker Heartbeat Engine (Shared Memory /dev/shm)
           │
           ├── Worker 1 (gunicorn.workers.sync.SyncWorker)
           │    └── Django WSGI Handler (Thread-confined)
           ├── Worker 2 (uvicorn.workers.UvicornWorker)
           │    └── Asyncio Event Loop (uvloop + httptools)
           └── Worker N ...
```

1. **Master Process (Arbiter)**:
   - Bertanggung jawab membaca konfigurasi, menginisiasi listening socket, dan melakukan fork worker processes.
   - Tidak memproses request HTTP client secara langsung.
   - Memonitor worker via signal handler (`SIGCHLD`) dan file *heartbeat* di temporary memory filesystem (`/dev/shm`). Jika worker tidak memperbarui timestamp heartbeat dalam rentang `timeout`, Arbiter membunuh worker tersebut via `SIGABRT` atau `SIGKILL` lalu melakukan respawn.
2. **Worker Models**:
   - **Sync Worker**: Menggunakan 1 proses per 1 koneksi konkuren. Jika aplikasi melakukan synchronous I/O blocking (misal: query database lambat atau panggilan API pihak ketiga tanpa timeout), worker tersebut sepenuhnya terblokir. Formula standar alokasi worker:
     $$\text{Workers} = (2 \times \text{vCPU Cores}) + 1$$
   - **Gevent/Eventlet Worker**: Menggunakan Green Threads (coroutine cooperatif) yang mem-patch library standar Python (socket, time) menjadi non-blocking via monkey patching.
   - **UvicornWorker (ASGI)**: Menjalankan single-threaded event loop berbasis `uvloop` (binding C ke `libuv`) di dalam setiap worker process. Sangat optimal untuk Django Async Views, Channels (WebSockets), dan Server-Sent Events (SSE).

#### B. Database Connection Lifecycle & Multiplexing
Django ORM secara default membuka koneksi database TCP baru pada request pertama di setiap thread/proses dan menutupnya di akhir request jika `CONN_MAX_AGE = 0`. Mengaktifkan `CONN_MAX_AGE > 0` memungkinkan penggunaan kembali koneksi yang ada, namun pada arsitektur multi-worker container (misal: 10 replica pod $\times$ 4 workers = 40 koneksi minimum), hal ini dapat memicu *connection exhaustion* pada PostgreSQL (`max_connections` terlampaui).

Solusi arsitektur enterprise mewajibkan layer *connection pooler multiplexer* eksternal seperti **PgBouncer**:
- **Session Pooling**: Satu koneksi PostgreSQL dialokasikan penuh selama koneksi klien (Django worker) terbuka. Kurang efektif untuk scaling pod dinamis.
- **Transaction Pooling**: Koneksi PostgreSQL hanya dipinjam dari pool selama transaksi database aktif (`BEGIN` sampai `COMMIT`/`ROLLBACK`). Begitu selesai, koneksi fisik PostgreSQL dikembalikan ke pool PgBouncer, meskipun koneksi TCP antara Django dan PgBouncer tetap terbuka.

> **PENTING**: Transaction pooling tidak mendukung fitur PostgreSQL tingkat session seperti Django ORM `SET SESSION timezone`, prepared statements tanpa handling khusus (`connect_timeout`, `server_reset_query`), atau temporary tables.

---

### 4. Why & What

| Dimensi | Development / Naive Production | Enterprise High-Availability Production |
| :--- | :--- | :--- |
| **Execution Layer** | `python manage.py runserver` (Single-threaded, insecure) | Gunicorn + Uvicorn Workers di balik Envoy/Nginx ingress |
| **Container Base** | `python:latest` atau `ubuntu` (Size > 1GB, high CVE count) | Multi-stage distroless / minimal Debian-slim (Size < 150MB, zero root) |
| **Lifecycle Hooks** | Pod langsung di-kill via `SIGKILL` oleh kubelet | Trapping `SIGTERM`, graceful socket draining via `preStop` hook (sleep 5-15s) |
| **Static & Media** | Serving statik via Django views (`django.views.static`) | WhiteNoise dengan Brotli/Gzip atau Cloud Object Storage (S3) + CDN bypass |
| **DB Topology** | Direct TCP connection ke instance PostgreSQL tunggal | Dual-layer: Django Persistent Pool $\to$ PgBouncer Pooler $\to$ Primary/Replica HA |
| **Health Probes** | Endpoint `/` membebani database di setiap pengecekan | Probe terisolasi: `/healthz/live` (shallow) dan `/healthz/ready` (deep check) |

---

### 5. How (Workflow Detail)

Alur Zero-Downtime Deployment dan Graceful Request Termination pada Kubernetes:

```
[ Deploy Baru Di-Trigger: kubectl set image / ArgoCD Sync ]
                         │
                         ▼
        [ Kubernetes Kubelet membuat Pod Baru ]
                         │
                         ├─ 1. Jalankan InitContainer: Verifikasi DB Migration & TCP check
                         ├─ 2. Start Main Container (Django + Gunicorn)
                         ├─ 3. StartupProbe berjalan hingga status SUCCESS
                         ├─ 4. ReadinessProbe mulai evaluasi (Cek cache, local status)
                         │
                         ▼
   [ ReadinessProbe = 200 OK -> Pod Masuk ke Endpoints Service ]
                         │
                         ▼
             [ Traffic Diteruskan ke Pod Baru ]
                         │
                         ▼
        [ Kubelet Memulai Eviksi pada Pod Lama ]
                         │
                         ├─ 1. Hapus Pod Lama dari Endpoints Service (Stop traffic baru)
                         ├─ 2. Eksekusi Hook `preStop`: sleep 10 detik (Drain in-flight socket proxy)
                         ├─ 3. Kirim sinyal SIGTERM ke Master Gunicorn Process
                         ├─ 4. Gunicorn berhenti me-listen port; worker diberi waktu graceful_timeout
                         ├─ 5. Worker menyelesaikan request aktif yang tersisa
                         └─ 6. Jika melebihi terminationGracePeriodSeconds -> Sinyal SIGKILL dikirim
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Airport Shuttle System
- **Client Request**: Penumpang yang datang ke bandara.
- **Ingress Controller**: Pintu masuk terminal yang mengarahkan penumpang ke bus yang tepat.
- **Gunicorn Arbiter**: Komandan terminal bus yang mengawasi supir.
- **Worker Process**: Bus itu sendiri.
  - *Sync Worker*: Taksi privat. 1 mobil hanya bawa 1 orang sampai tempat tujuan, baru bisa ambil orang lain. Jika macet (blocking DB), taksi berhenti total.
  - *Async/Eventlet Worker*: Bus rapid transit. Mengangkut banyak orang secara parsial, menurunkan/menaikkan penumpang bergantian tanpa harus menunggu penumpang lain selesai berbelanja.
- **Kubernetes Pod Rolling Update**: Mengganti armada bus tua dengan bus baru tanpa menutup terminal. Bus tua dilarang menerima penumpang baru, menyelesaikan rute yang sedang berjalan, menurunkan semua penumpang, lalu keluar dari garasi secara rapi.

```
       +-------------------------------------------------------+
       |               KUBERNETES POD BOUNDARY                 |
       |                                                       |
       |  +--------------------+       +--------------------+  |
       |  | Readiness Probe    |       | In-Flight Request  |  |
       |  +---------+----------+       +---------+----------+  |
       |            │                            │             |
       |     GET /healthz/ready           HTTP /api/v1/orders  |
       |            │                            │             |
       |            ▼                            ▼             |
       |  +-------------------------------------------------+  |
       |  |            Master Gunicorn Arbiter              |  |
       |  |  Signals: [SIGTERM] -> Graceful Shutdown Mode   |  |
       |  +-------------------------+-----------------------+  |
       |                            │                          |
       |             +--------------+--------------+           |
       |             │ /dev/shm Heartbeat          │           |
       |             ▼                             ▼           |
       |      [ Worker Process 1 ]          [ Worker Process 2 ]|
       |      State: PROCESSING             State: DRAINING     |
       |      CONN_MAX_AGE = 60s            CONN_MAX_AGE = 60s  |
       +-------------│-----------------------------│-----------+
                     │                             │
                     +--------------+--------------+
                                    │ TCP Unix/Socket
                                    ▼
                         [ PgBouncer Pooler Pod ]
                                    │ Transaction Mode (Max 50 Conns)
                                    ▼
                         [ PostgreSQL HA Cluster ]
```

---

### 7. Simple Example & Practical Example

#### A. Multi-Stage Distroless/Minimal Dockerfile (`Dockerfile`)
Menggunakan pattern multi-stage caching, user non-root eksplisit, dan proteksi dependencies poisoning.

```dockerfile
# syntax=docker/dockerfile:1.4
# ==========================================
# STAGE 1: Dependency Builder
# ==========================================
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    POETRY_VERSION=1.8.2

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip setuptools wheel && \
    /opt/venv/bin/pip install --no-deps -r requirements.txt

# ==========================================
# STAGE 2: Final Runtime Engine
# ==========================================
FROM python:3.12-slim-bookworm AS runner

# Definisi security ID eksplisit
ARG APP_USER=appuser
ARG APP_UID=10001

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE="config.settings.production"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Hardening: Jangan gunakan user root
RUN groupadd --gid ${APP_UID} ${APP_USER} && \
    useradd --uid ${APP_UID} --gid ${APP_USER} --shell /bin/false --no-create-home ${APP_USER}

WORKDIR /app

# Salin pre-compiled virtualenv dari stage builder
COPY --from=builder /opt/venv /opt/venv
COPY --chown=${APP_USER}:${APP_USER} . /app

# Validasi integrity & permission
RUN chown -R ${APP_USER}:${APP_USER} /app

USER ${APP_UID}

EXPOSE 8000

# Healthcheck fallback container level
HEALTHCHECK --interval=10s --timeout=3s --retries=3 --start-period=15s \
    CMD curl -f http://127.0.0.1:8000/healthz/live/ || exit 1

ENTRYPOINT ["gunicorn", "-c", "config/gunicorn.conf.py", "config.wsgi:application"]
```

#### B. Enterprise Gunicorn Configuration (`config/gunicorn.conf.py`)
Menerapkan signal handling, dynamic worker sizing, memory leak containment, dan graceful timeout.

```python
import multiprocessing
import os

# Binding Socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker Process Sizing
# Konkurensi: Menghindari worker bloating di container multicore dengan batas ceiling
cpu_count = multiprocessing.cpu_count()
workers = int(os.getenv("GUNICORN_WORKERS", default=str((2 * cpu_count) + 1)))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")
threads = int(os.getenv("GUNICORN_THREADS", "4"))

# Worker Lifecycle & Memory Leak Protection
# Restart worker setelah 5000 request dengan jitter acak agar tidak restart bersamaan
max_requests = 5000
max_requests_jitter = 500

# Graceful Termination Protocols
timeout = 30           # Kill worker yang hang melewati batas 30 detik
graceful_timeout = 25  # Waktu bagi worker untuk menyelesaikan in-flight request pasca SIGTERM
keepalive = 5

# Shared Memory Heartbeat Directory (Menghindari masalah worker timeouts pada I/O blocking)
worker_tmp_dir = "/dev/shm"

# Logging Pipeline
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
access_log_format = (
    '{"time": "%(t)s", "remote_ip": "%(h)s", "request_id": "%({X-Request-ID}i)s", '
    '"status": "%(s)s", "response_length": "%(b)s", "duration_usec": %(D)s}'
)

def on_starting(server):
    server.log.info("Master Gunicorn Arbiter terinisialisasi. Menunggu workers...")

def worker_int(worker):
    worker.log.warning(f"Worker {worker.pid} menerima SIGINT/SIGQUIT. Melakukan graceful exit.")

def worker_abort(worker):
    worker.log.error(f"Worker {worker.pid} terdeteksi hang (timeout heartbeat). Melakukan force terminate.")
```

#### C. Database-agnostic Probes Implementation (`common/views.py`)

```python
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from rest_framework.views import View

class LivenessProbeView(View):
    """
    Shallow Check: Hanya memvalidasi proses web server merespons HTTP request.
    JANGAN cek database/cache di sini untuk mencegah cascading failure berantai.
    """
    def get(self, request, *args, **kwargs):
        return JsonResponse({"status": "live", "engine": "django"}, status=200)

class ReadinessProbeView(View):
    """
    Deep Check: Memvalidasi ketersediaan dependensi kritis (DB & Cache).
    Jika gagal, Pod dikeluarkan dari daftar routing Service tapi TIDAK di-restart.
    """
    def get(self, request, *args, **kwargs):
        diagnostics = {}
        
        # 1. Database Connectivity Validation
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                cursor.fetchone()
            diagnostics["database"] = "healthy"
        except Exception as exc:
            diagnostics["database"] = f"unhealthy: {str(exc)}"

        # 2. Redis/Cache Connectivity Validation
        try:
            cache.set("readiness_check", 1, timeout=5)
            if cache.get("readiness_check") == 1:
                diagnostics["cache"] = "healthy"
            else:
                diagnostics["cache"] = "unhealthy: cache validation failed"
        except Exception as exc:
            diagnostics["cache"] = f"unhealthy: {str(exc)}"

        is_healthy = all(status == "healthy" for status in diagnostics.values())
        status_code = 200 if is_healthy else 503
        
        return JsonResponse({
            "status": "ready" if is_healthy else "unready",
            "components": diagnostics
        }, status=status_code)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Financial Gateway "FinCore API"
- **Skala**: 40.000 Request Per Second (RPS) pada peak hours.
- **Problem**: Setiap deployment baru via ArgoCD menghasilkan lonjakan error HTTP 502 (Bad Gateway) sebanyak 0.8% selama durasi 3 menit rollout, serta PostgreSQL mengalami `FATAL: remaining connection slots are reserved for non-replication superuser connections`.
- **Akar Masalah (Root-Cause Analysis)**:
  1. Kubelet mematikan Pod lama secara agresif saat endpoint Kubernetes Service belum selesai disinkronkan ke seluruh Ingress Proxy nodes (race condition antara kube-proxy iptables update dan container SIGKILL).
  2. Django instances diatur dengan `CONN_MAX_AGE=600`. Saat Pod scaling naik dari 20 ke 80 replicas, total koneksi langsung ke PostgreSQL melompat dari 320 koneksi menjadi 1.280 koneksi, melebihi limit PostgreSQL (`max_connections=500`).

#### Solusi Arsitektur Terintegrasi:

1. **Implementasi `preStop` hook sleep dan grace period alignment**:
   Pod dicegah berhenti selama 15 detik untuk memberi waktu pada Ingress Controller memutus lalu lintas traffic ke pod tersebut.

2. **Penyisipan Layer PgBouncer HA (Transaction Mode)**:
   Django dikonfigurasi dengan `CONN_MAX_AGE=0` atau pooling level mikro, lalu diarahkan ke cluster PgBouncer stateful set dengan pool limit terdistribusi.

```yaml
# kubernetes/production/django-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fincore-api
  namespace: production
  labels:
    app.kubernetes.io/name: fincore-api
    app.kubernetes.io/part-of: core-banking
spec:
  replicas: 40
  revisionHistoryLimit: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%
      maxUnavailable: 0
  selector:
    matchLabels:
      app: fincore-api
  template:
    metadata:
      labels:
        app: fincore-api
    spec:
      terminationGracePeriodSeconds: 45
      containers:
        - name: application
          image: registry.fincore.internal/banking/api:v2.4.1
          imagePullPolicy: IfNotPresent
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 15"]
          envFrom:
            - configMapRef:
                name: fincore-config
            - secretRef:
                name: fincore-secrets
          resources:
            requests:
              cpu: "1000m"
              memory: "1536Mi"
            limits:
              cpu: "2000m"
              memory: "2048Mi"
          ports:
            - name: http
              containerPort: 8000
          startupProbe:
            httpGet:
              path: /healthz/live/
              port: http
            initialDelaySeconds: 10
            periodSeconds: 3
            failureThreshold: 20
          livenessProbe:
            httpGet:
              path: /healthz/live/
              port: http
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /healthz/ready/
              port: http
            periodSeconds: 5
            timeoutSeconds: 2
            successThreshold: 1
            failureThreshold: 2
```

---

### 9. Trade-offs

| Pendekatan Arsitektur | Keuntungan | Kerugian / Konsekuensi | Mitigasi Trade-off |
| :--- | :--- | :--- | :--- |
| **Gunicorn `sync` workers** | Model eksekusi sederhana, thread-safe secara natural, isolasi memory fault antar worker sempurna. | Sangat rapuh terhadap high-latency I/O downstream; kapasitas concurrency terbatas oleh vCPU (`(2*N)+1`). | Gunakan `gthread` atau `uvicorn.workers.UvicornWorker` untuk endpoints non-CPU-bound. |
| **PgBouncer Transaction Pooling** | Mengurangi ribuan koneksi Django menjadi puluhan koneksi aktif di PostgreSQL; konsumsi RAM DB sangat rendah. | Menghilangkan fungsionalitas Session-level (Prepared Statements, `LISTEN`/`NOTIFY`, transient variables). | Konfigurasi PgBouncer `max_prepared_statements` atau gunakan mode binary protocol direct pada endpoint khusus. |
| **Container Image: Alpine Linux** | Ukuran base image sangat kecil (~5MB). | Menggunakan musl libc (bukan glibc), menyebabkan kompilasi wheels C (seperti `numpy`, `psycopg2`) melambat drastis dan memory allocator fragmentasi. | Gunakan Debian-slim (`python:3.12-slim-bookworm`) untuk stabilitas ekosistem enterprise C-extensions. |
| **`preStop` Sleep Hook pada Pod** | Menjamin 100% Zero Dropped Connections selama traffic in-flight berlangsung saat rolling update. | Durasi deployment pipeline (CI/CD) menjadi lebih lambat sebanding dengan waktu sleep dikali jumlah replica batch. | Kalibrasi durasi sleep seminimal mungkin berdasarkan metrik propagasi ingress update (biasanya 5–15 detik). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Zombie Worker Akibat Penggunaan `/tmp` Sebagai Heartbeat Directory
* **Symptom**: Gunicorn tiba-tiba membunuh worker (`[CRITICAL] WORKER TIMEOUT`) setiap beberapa jam, meskipun beban CPU normal.
* **Root Cause**: Gunicorn menggunakan disk temporary file untuk mekanisme heartbeat antar arbiter dan worker. Pada platform berbasis container atau VPS dengan I/O burst throttling, operasi filesystem `/tmp` mengalami latency spike, memicu timeout palsu.
* **Solusi**: Alihkan parameter Gunicorn `worker_tmp_dir` ke shared-memory virtual disk:
  ```python
  worker_tmp_dir = "/dev/shm"
  ```
  Pada Kubernetes, definisikan `emptyDir` dengan medium `Memory` dan mount ke container jika `/dev/shm` default dibatasi ukurannya.

#### 2. Cascading Failure Akibat Deep Health Checks pada Liveness Probe
* **Symptom**: Ketika Database mengalami degradasi performa minor, Kubernetes mulai me-restart **seluruh** pod Django secara massal bersamaan, yang berujung pada HTTP 503 Outage total.
* **Root Cause**: Menempatkan dependency checking (koneksi Database/Redis) di dalam endpoint `livenessProbe`. Kubelet menginterpretasikan Database timeout sebagai kematian web server dan me-restart Pod. Restart massal tersebut membanjiri DB yang sedang degraded dengan ribuan startup connections baru (*Thundering Herd*).
* **Solusi**: Pisahkan probe secara ketat. Endpoint liveness (`/healthz/live`) **hanya** mengecek apakah proses web server merespons (shallow). Endpoint readiness (`/healthz/ready`) mengecek dependensi external (deep).

#### 3. Pod OOMKilled Saat Menjalankan `collectstatic` dalam Container Startup
* **Symptom**: Container crash dengan Exit Code 137 saat pertama kali boot.
* **Root Cause**: Mengompilasi dan mengompresi asset statik (`python manage.py collectstatic --noinput`) di dalam script `entrypoint.sh` saat container inisialisasi di bawah alokasi memory limit Kubernetes Pod yang ketat.
* **Solusi**: Jalankan `collectstatic` secara mutlak pada waktu image build (`Dockerfile` stage builder) atau gunakan pipeline CI/CD eksternal yang langsung mengunggah file statik ke CDN Object Storage (S3/GCS).

---

### 11. Best Practices (Production Checklist)

1. [ ] **Non-Root Execution**: Container wajib berjalan di bawah user non-root (misal: UID 10001) tanpa akses sudo/privilege escalation (`allowPrivilegeEscalation: false`).
2. [ ] **Signal Termination**: Master runtime wajib merespons `SIGTERM` secara tertib dan meneruskannya ke semua child processes.
3. [ ] **Pre-Stop Draining Hook**: Konfigurasi minimal `lifecycle.preStop.exec.command: ["/bin/sh", "-c", "sleep 10"]` di seluruh pod web-facing.
4. [ ] **Database Connection Pooling**: Tidak menghubungkan Django pod directly ke bare PostgreSQL di skala $>20$ pods tanpa PgBouncer/Pgpool-II.
5. [ ] **Readiness vs Liveness Isolation**: Liveness TIDAK BOLEH memanggil network I/O eksternal (DB, Cache, 3rd party APIs).
6. [ ] **Resource Limits & Requests**: Selalu tetapkan batas CPU & Memory request dan limits yang simetris atau terkontrol untuk menghindari kernel starvation.
7. [ ] **Immutable Infrastructure**: Jangan pernah menjalankan `manage.py migrate` secara otomatis di dalam startup Pod app runtime. Eksekusi migration sebagai Kubernetes `Job` terpisah sebelum Pod baru dideploy.
8. [ ] **Stateless Storage**: Local filesystem container harus diperlakukan secara ephemeral. Semua upload media wajib diarahkan ke S3-compatible object storage via `django-storages`.

---

### 12. Hands-on Practice

Struktur direktori praktikum yang harus dibangun di `hands-on/m02/`:

```
hands-on/m02/
├── app/
│   ├── config/
│   │   ├── __init__.py
│   │   ├── gunicorn.conf.py
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── views.py
│   └── manage.py
├── k8s/
│   ├── deployment.yaml
│   └── service.yaml
├── Dockerfile
├── requirements.txt
└── test_graceful_shutdown.sh
```

#### Langkah 1: Siapkan `requirements.txt`
```text
Django>=5.0,<5.1
gunicorn>=22.0.0
psycopg2-binary>=2.9.9
redis>=5.0.3
```

#### Langkah 2: Buat Skrip Health Checking di `app/core/views.py`
Implementasikan kode views shallow & deep checks seperti yang dijelaskan pada Seksi 7.C.

#### Langkah 3: Konfigurasi URL Routing di `app/config/urls.py`
```python
from django.urls import path
from core.views import LivenessProbeView, ReadinessProbeView

urlpatterns = [
    path('healthz/live/', LivenessProbeView.as_view(), name='healthz_live'),
    path('healthz/ready/', ReadinessProbeView.as_view(), name='healthz_ready'),
]
```

#### Langkah 4: Bangun Docker Image
```bash
docker build -t django-enterprise-m02:v1.0.0 .
```

#### Langkah 5: Eksekusi Graceful Shutdown Validation Test
Buat file `test_graceful_shutdown.sh` untuk memverifikasi bahwa server tetap merespons request yang sedang berjalan saat menerima sinyal `SIGTERM`:

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "==> Menjalankan kontainer Django..."
CONTAINER_ID=$(docker run -d -p 8000:8000 django-enterprise-m02:v1.0.0)

# Tunggu container boot
sleep 3

echo "==> Melakukan simulasi long-running request (5 detik)..."
# Menjalankan background request
curl -s "http://127.0.0.1:8000/healthz/live/" &
BG_PID=$!

echo "==> Mengirim sinyal SIGTERM ke Container..."
docker kill --signal="SIGTERM" "$CONTAINER_ID"

echo "==> Menunggu status curl background..."
wait $BG_PID

echo "==> Memeriksa Exit Code Container..."
CONTAINER_EXIT_CODE=$(docker inspect "$CONTAINER_ID" --format='{{.State.ExitCode}}')
echo "Container Exit Code: $CONTAINER_EXIT_CODE"

docker rm "$CONTAINER_ID" > /dev/null
echo "==> Pengujian selesai."
```

---

### 13. Exercise

#### Level: Easy
1. Modifikasi konfigurasi Gunicorn pada `config/gunicorn.conf.py` agar logging format mencetak JSON string lengkap yang berisi field `http_user_agent`, `request_time`, dan `x_forwarded_for`.
2. Ubah `Dockerfile` agar menggunakan distroless image (`gcr.io/distroless/python3-debian12`) sebagai target runner stage dan identifikasi kendala akses shell debugging-nya.

#### Level: Medium
1. Tulis konfigurasi PgBouncer (`pgbouncer.ini`) dengan mode pooling `transaction`, default client connections 1000, dan reserve pool 10. Sambungkan Django settings `DATABASES` ke instance PgBouncer ini dan lakukan verifikasi transaksi atomic menggunakan block `django.db.transaction.atomic`.
2. Susun manifes Kubernetes `HorizontalPodAutoscaler` (HPA v2) yang menargetkan Deployment Django dengan scaling threshold: Target Average CPU Utilization 70% dan Target Custom Metric HTTP Requests Per Second (RPS) 500.

#### Level: Hard
1. Implementasikan kustom Gunicorn Worker class turunan dari `gthread` yang mampu mengintercept sinyal `SIGTERM`. Worker harus menghentikan penerimaan koneksi TCP baru, menyuntikkan header HTTP `Connection: close` pada seluruh response yang sedang diolah dalam masa draining, dan mencatat trace dump memory allocation active threads ke stdout sebelum worker dihancurkan.

---

### 14. Challenge

**Skenario**:
Sebuah platform E-Commerce berskala enterprise mengalami kondisi "Thundering Herd" dan deadlock session pooler saat momen Flash Sale. Dalam waktu 5 detik pasca peluncuran flash sale, traffic melonjak dari 1.000 RPS menjadi 60.000 RPS. 

Arsitektur sistem saat ini:
- 120 Pods Django berjalan di cluster EKS.
- 2 PgBouncer instance terpasang di depan 1 Master Aurora PostgreSQL DB.
- Django mengaktifkan middleware otentikasi session standar yang membaca database untuk memvalidasi user session token di setiap incoming HTTP request.

**Tantangan Arsitektur**:
Rancang dan dokumentasikan proposal arsitektural komprehensif untuk merombak sistem ini agar mampu bertahan tanpa error HTTP 5xx:
1. Rekayasa ulang layer otentikasi agar melepaskan session store dari direct transactional query DB tanpa mengorbankan fungsionalitas instant revocation token.
2. Hitung kalkulasi matematis kapasitas socket: Formula ukuran pooler Gunicorn workers, pool limits PgBouncer, dan parameter OS network tuning (`somaxconn`, `tcp_max_syn_backlog`) di tingkat Linux worker nodes.
3. Rancang mitigasi Kubernetes Pod eviction cascade jika salah satu node Kubernetes mengalami Kernel Out-Of-Memory (OOM). Tuliskan spesifikasi tolerations, podAntiAffinity, dan PriorityClass yang wajib diterapkan.

*(Dokumentasikan solusi dalam bentuk diagram arsitektur komponen, rumus sizing kapasitas, dan potongan manifes infrastruktur tanpa menggunakan library SaaS pihak ketiga).*

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa perintah bawaan `python manage.py runserver` secara fundamental dilarang keras dijalankan pada lingkungan production?
2. Apa perbedaan mendasar antara worker model tipe `sync` dan `gthread` pada Gunicorn saat menangani latency tinggi dari pemanggilan third-party API?
3. Mengapa parameter `worker_tmp_dir` pada Gunicorn di lingkungan kontainer Docker/Kubernetes disarankan diarahkan ke `/dev/shm` dan bukan ke `/tmp` bawaan?
4. Mengapa kita harus menggunakan image berukuran kecil (seperti Debian-slim atau distroless) dan mengeksekusi container menggunakan user non-root dari perspektif security lifecycle?
5. Apa konsekuensi logis terhadap koneksi database jika Anda menyetel konfigurasi Django `CONN_MAX_AGE = None` pada lingkungan deployment autoscale dinamis (HPA)?

#### B. Pertanyaan Intermediate
6. Pada arsitektur Kubernetes, jelaskan skenario di mana sebuah Pod Django dapat mengembalikan respons HTTP 502/Bad Gateway ke Ingress Controller selama proses Rolling Update, dan bagaimana `preStop` hook mengeliminasi isu ini!
7. Mengapa mode pooling `Transaction` pada PgBouncer dapat merusak fungsi `django.db.connection.cursor()` jika aplikasi menggunakan fitur prepared statements atau variable session level?
8. Bagaimana Arbiter Gunicorn mendeteksi bahwa sebuah worker mengalami infinite loop atau hang, dan aksi sistem apa yang diambil arbiter tersebut?
9. Apa perbedaan esensial dari kacamata Kubelet antara kegagalan status pada `readinessProbe` dibandingkan dengan kegagalan pada `livenessProbe`?
10. Bagaimana cara kerja directive `max_requests` dan `max_requests_jitter` pada Gunicorn dalam memitigasi memory leak yang lazim terjadi di aplikasi Python?

#### C. Skenario Kasus Produksi
11. **Skenario Kasus 1**: Tim Anda baru saja merilis versi terbaru aplikasi Django. Seluruh Pod baru lolos `startupProbe` dan `livenessProbe`, tetapi Ingress Controller sama sekali tidak mengalihkan request ke Pod baru tersebut. Di sisi lain, Pod lama tidak dihapus oleh deployment engine. Investigasi akar masalahnya di level Kubernetes specs!
12. **Skenario Kasus 2**: Sebuah worker Django berbasis Uvicorn/ASGI memproses traffic websocket dan HTTP API bersamaan. Ketika CPU usage Pod mencapai 95%, koneksi websocket drop massal, dan HTTP API merespons dengan timeout. Metrik database PostgreSQL menunjukkan utilisasi CPU hanya 15%. Analisis letak bottleneck arsitektural ini dan tentukan solusinya!
13. **Skenario Kasus 3**: Database PostgreSQL Anda mengalami restart tak terduga selama 30 detik pada jam 02.00 dini hari. Meskipun server PostgreSQL sudah kembali online dan berstatus normal, Pod Django tetap terus-menerus mengembalikan error `psycopg2.OperationalError: server closed the connection unexpectedly` hingga akhirnya seluruh pod di-restart secara manual. Konfigurasi apa di Django atau network layer yang luput diimplementasikan?

---

### 16. Summary

1. **Layer Eksekusi HTTP**: Arsitektur enterprise Django memisahkan layer runtime server ke dalam Master Arbiter dan Worker Pool yang terisolasi. Penggunaan model thread pool (`gthread`) atau Async worker (`uvicorn`) adalah keharusan mutlak saat melayani incoming request dengan dominasi I/O-bound.
2. **Koneksi Database Skala Besar**: Django Persistent Connections (`CONN_MAX_AGE`) harus diselaraskan secara matematis dengan connection pooler eksternal (PgBouncer). Direct connection dari puluhan autoscaled Pods langsung ke DB instance merupakan anti-pattern yang menyebabkan keruntuhan sistem akibat pool exhaustion.
3. **High Availability Orchestration**: Zero-downtime deployment bukan hanya perihal mengganti kontainer; hal ini memerlukan sinkronisasi tepat antara TCP socket draining, Kubernetes routing state table propagation via `preStop` delays (5-15s), dan isolasi tanggung jawab antara `startupProbe`, `livenessProbe`, dan `readinessProbe`.
4. **Resilience & Graceful Handling**: Master process web server harus menjadi first-class citizen di sistem operasi dengan merespons sinyal POSIX (`SIGTERM`, `SIGHUP`) secara elegan, mengamankan request in-flight, membersihkan memori via request-jitter recycling, dan menghindari filesystem bottlenecks via ramdisk shared memory (`/dev/shm`).