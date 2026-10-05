# BAB-10-Kontainerisasi-High-Availability-Production-Deployment: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang sebagai instrumen pengujian pemahaman konseptual, kemampuan troubleshooting arsitektur, dan kecakapan rekayasa operasional produksi terkait kontainerisasi Django, orkestrasi High Availability (HA), zero-downtime rolling update, reverse proxy caching, horizontal pod autoscaling, serta strategi observability di level enterprise.

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1.1: Multi-Stage Build & Image Footprint
**Pertanyaan:**
Mengapa multi-stage Docker build sangat direkomendasikan untuk men-deploy aplikasi Django ke production dibandingkan single-stage Dockerfile biasa? Sebutkan setidaknya dua keuntungan dari aspek keamanan dan performa runtime.

**Jawaban & Pembahasan:**
Multi-stage build memisahkan tahap kompilasi/pembangunan dependensi (build environment) dari image runtime akhir. Pada tahap pertama (`builder stage`), perkakas kompilasi seperti `gcc`, `g++`, header kernel C (`libpq-dev`, `python3-dev`), dan dependensi build tools diinstal untuk mengompilasi package wheel C-extension Python. Setelah itu, pada tahap final, hanya virtualenv yang sudah terkompilasi bersih dan artefak runtime yang disalin ke base image minimal (misalnya `python:3.12-slim` atau Alpine).

Keuntungan utama:
1. **Keamanan (Attack Surface Reduction):** Image runtime akhir tidak mengandung compiler, debugger, build utilities, atau paket development package manager yang berpotensi dieksploitasi oleh penyerang jika terjadi Remote Code Execution (RCE).
2. **Performa & Efisiensi Distribusi:** Ukuran image (image footprint) tereduksi secara drastis (seringkali dari ~1.2 GB turun menjadi <180 MB), mempercepat proses CI/CD image pushing/pulling, cold-start time pada orkestrator (Kubernetes/ECS), dan menghemat konsumsi bandwidth storage container registry.

---

### Soal 1.2: Root vs Non-Root User dalam Container
**Pertanyaan:**
Mengapa container Django di production tidak boleh dijalankan dengan user default `root` (`UID 0`), dan bagaimana sintaks deklarasi non-root user di Dockerfile?

**Jawaban & Pembahasan:**
Menjalankan container sebagai `root` meningkatkan risiko *container breakout*. Jika aplikasi memiliki celah keamanan (misal CVE traversal atau arbitrary code execution), penyerang akan mewarisi privilege root di namespace container. Jika konfigurasi runtime atau isolasi kernel memiliki celah, privilege tersebut dapat berpotensi mengeksekusi aksi eskalasi hak akses ke host Linux di luar container.

Deklarasi yang benar pada Dockerfile:
```dockerfile
# Buat group dan user sistem khusus tanpa shell interaktif
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /sbin/nologin -d /app appuser

# Berikan hak kepemilikan direktori kerja
WORKDIR /app
COPY --chown=appuser:appgroup . /app

# Alihkan konteks eksekusi runtime ke non-root user
USER 10001
```

---

### Soal 1.3: Peran Reverse Proxy (Nginx) di Depan Gunicorn/Uvicorn
**Pertanyaan:**
Jika Gunicorn atau Uvicorn sudah mampu menangani HTTP request dan menjalankan aplikasi WSGI/ASGI Django, mengapa kita tetap memerlukan reverse proxy seperti Nginx, Traefik, atau AWS ALB di lapis terdepan?

**Jawaban & Pembahasan:**
WSGI server seperti Gunicorn dioptimalkan untuk mengeksekusi logika Python secara efisien, bukan untuk mengelola beban koneksi HTTP edge. Nginx ditempatkan di depan untuk:
1. **Slow Client Protection (Buffering):** Klien dengan koneksi lambat akan menahan worker thread/process Gunicorn jika terhubung langsung. Nginx melakukan request/response buffering di memori, membebaskan worker Python segera setelah payload di-generate.
2. **Serving Static & Media Files:** Nginx menangani file statis langsung via kernel system call (`sendfile`) tanpa overhead memori Python runtime.
3. **SSL/TLS Termination & HTTP/2 / HTTP/3 Negotiation:** Enkripsi/dekripsi TLS ditangani oleh Nginx/ALB dengan akselerasi hardware OpenSSL native.
4. **Header Normalization & Security Filtering:** Memblokir malformed HTTP headers, membatasi ukuran body payload (`client_max_body_size`), serta menangani forwarding header IP (`X-Forwarded-For`, `X-Forwarded-Proto`).

---

### Soal 1.4: Stateless Container Architecture & Local Storage
**Pertanyaan:**
Apa yang akan terjadi jika aplikasi Django di dalam Docker menyimpan file user upload (`MEDIA_ROOT`) ke direktori lokal container filesystem (`/app/media`) pada cluster dengan 4 replica instance?

**Jawaban & Pembahasan:**
Container filesystem bersifat sementara (*ephemeral*) dan terisolasi untuk masing-masing container. Jika pengguna mengunggah gambar ke instance A:
1. File tersebut hanya tersimpan di disk layer container A.
2. Ketika user lain (atau user yang sama pada request berikutnya yang di-load-balance) mengakses gambar tersebut dan diarahkan ke container B, C, atau D, server akan mengembalikan respon HTTP 404 Not Found.
3. Ketika instance container di-restart, di-reschedule oleh Kubernetes, atau di-deploy ulang, seluruh file pada layer lokal tersebut akan musnah permanen.

Solusinya adalah mematuhi prinsip *12-Factor App*: jadikan container sepenuhnya *stateless*, simpan media asset ke Object Storage terpusat (seperti AWS S3, Cloudflare R2, MinIO, atau Google Cloud Storage) menggunakan pustaka seperti `django-storages` + `boto3`.

---

### Soal 1.5: Mekanisme Django `collectstatic` dalam Docker
**Pertanyaan:**
Pada tahap apa command `python manage.py collectstatic --noinput` sebaiknya dieksekusi: saat `docker build` (di dalam Dockerfile) atau saat runtime kontainer dijalankan (`docker run` / Kubernetes entrypoint script)? Jelaskan pertimbangannya.

**Jawaban & Pembahasan:**
`collectstatic` sebaiknya dieksekusi pada saat **`docker build`** (build time).

Pertimbangan:
1. **Immutability & Determinism:** Artefak statis menjadi bagian dari image yang di-versioning secara immutable. Seluruh aset hash statis (`ManifestStaticFilesStorage`) terkunci seragam di seluruh cluster.
2. **Startup Time (Cold Start):** Jika `collectstatic` dijalankan saat startup container (`entrypoint.sh`), setiap replika pod yang baru menyala (terutama saat autoscaling burst) akan memakan waktu puluhan detik hingga menit hanya untuk mengumpulkan file statis, menyebabkan request timeout atau kegagalan liveness probe.
3. **Database Independence:** `collectstatic` standar tidak memerlukan koneksi aktif ke database produksi asalkan `settings.py` dikonfigurasi dengan dummy/fallback credentials jika diperlukan, sehingga dapat dieksekusi secara aman di CI/CD build runner.

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 2.1: Database Connection Pooling & Gunicorn Worker Concurrency
**Pertanyaan:**
Jika Anda mengonfigurasi Gunicorn dengan 4 worker process dan masing-masing worker menggunakan 4 thread (`--workers 4 --threads 4`), berapakah jumlah koneksi database PostgreSQL yang berpotensi dibuka oleh 1 container Django dengan setting `CONN_MAX_AGE = 600`? Apa implikasinya terhadap batas `max_connections` di PostgreSQL ketika instance di-scale menjadi 10 kontainer?

**Jawaban & Pembahasan:**
Django mengelola koneksi database secara independen per thread per proses:
- Jumlah thread per container = `4 worker × 4 thread = 16 thread concurrent execution`.
- Dengan `CONN_MAX_AGE = 600`, koneksi TCP ke PostgreSQL dipertahankan tetap terbuka (persistent connection) selama 600 detik per thread.
- Satu container berpotensi mempertahankan hingga **16 koneksi aktif**.
- Ketika cluster di-scale menjadi 10 kontainer, total koneksi potensial yang dialokasikan adalah `10 kontainer × 16 koneksi = 160 koneksi`.

Jika parameter PostgreSQL `max_connections` diatur pada default 100, database server akan mengalami connection exhaustion dan menolak transaksi dengan error: `FATAL: remaining connection slots are reserved for non-replication superuser connections`.
Solusi arsitektur wajib menyertakan connection pooler eksternal berlatensi rendah seperti **PgBouncer** (dengan mode transaction pooling) di depan PostgreSQL.

---

### Soal 2.2: Kubernetes Probes: Liveness vs Readiness vs Startup
**Pertanyaan:**
Jelaskan perbedaan mendasar fungsi antara `livenessProbe`, `readinessProbe`, dan `startupProbe` pada pod Django, serta tuliskan contoh endpoint `/healthz` yang tepat agar liveness probe tidak mematikan pod secara keliru saat database mengalami degradasi sementara.

**Jawaban & Pembahasan:**
1. **`startupProbe`:** Menilai apakah aplikasi sudah berhasil inisialisasi awal (misal: load model cache, warm-up modul). Selama probe ini belum sukses, probe lain dinonaktifkan.
2. **`readinessProbe`:** Menilai apakah pod siap menerima traffic dari Kubernetes Service load balancer. Jika gagal, pod **tidak di-kill**, melainkan endpoint IP-nya dikeluarkan dari routing Service agar tidak ada user request yang terkena error 502/503.
3. **`livenessProbe`:** Menilai apakah proses aplikasi masih hidup (tidak deadlock). Jika gagal berturut-turut melebihi threshold, kubelet akan **mematikan dan me-restart container**.

**Anti-Pattern Umum:** Mengecek koneksi database pada `livenessProbe`. Jika PostgreSQL mengalami spike beban 10 detik, liveness probe di 20 pod Django gagal bersamaan, menyebabkan kubelet me-restart seluruh 20 pod serentak (*cascading failure* / *thundering herd*).

**Desain Endpoint yang Tepat:**
- `/healthz/live` (Liveness): Hanya mengecek apakah proses web server internal Python merespon (shallow health check, memori/event-loop responsive).
- `/healthz/ready` (Readiness): Melakukan *deep check* (konektivitas DB, Redis cache, broker dependency).

Implementasi view Django:
```python
from django.http import HttpResponse, JsonResponse
from django.db import connection

def liveness_check(request):
    # Shallow check: pastikan interpreter dan HTTP loop hidup
    return HttpResponse("OK", status=200)

def readiness_check(request):
    # Deep check: pastikan dependency esensial tersedia
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ready", "database": "up"}, status=200)
    except Exception as exc:
        return JsonResponse({"status": "unavailable", "reason": str(exc)}, status=503)
```

---

### Soal 2.3: Zero-Downtime Database Migration Strategy
**Pertanyaan:**
Mengapa menjalankan perintah `python manage.py migrate` secara langsung di dalam Kubernetes `entrypoint.sh` pada deployment berskala multi-replica berisiko tinggi merusak sistem, dan bagaimana pola yang benar untuk mengeksekusi migrasi tanpa downtime?

**Jawaban & Pembahasan:**
Menjalankan migrasi pada `entrypoint.sh` container web app menyebabkan:
1. **Race Condition:** Jika 5 pod baru menyala bersamaan saat deployment, 5 container akan mencoba mengeksekusi `migrate` ke database secara serentak, memicu lock contention pada tabel `django_migrations` atau schema deadlocks di PostgreSQL.
2. **Crash Loop:** Jika salah satu migrasi gagal, seluruh pod crash serentak sebelum ada yang sempat melayani traffic.
3. **Breaking Schema Changes:** Jika pod versi baru melakukan migrasi destruktif (misal: menghapus kolom `old_price`), pod versi lama yang masih aktif melayani traffic akan langsung crash saat melakukan query ke kolom tersebut.

**Pola Zero-Downtime yang Benar:**
1. Gunakan **Kubernetes Job** atau **ArgoCD Pre-Sync Hook** untuk menjalankan migrasi hanya sekali secara terisolasi sebelum rolling update pod versi baru dimulai.
2. Terapkan strategi **Expand and Contract (Two-Phase Migration)**:
   - *Fase 1 (Expand):* Tambahkan kolom baru (`new_price`), biarkan kode lama tetap berjalan membaca kolom lama, deploy kode baru yang menulis ke kedua kolom.
   - *Fase 2 (Backfill):* Sinkronisasi data lama ke kolom baru via background task.
   - *Fase 3 (Contract):* Deploy kode yang hanya membaca kolom baru, lalu jalankan migrasi terpisah untuk menghapus kolom lama.

---

### Soal 2.4: Signal Handling (SIGTERM) & Graceful Shutdown di Gunicorn
**Pertanyaan:**
Ketika Kubernetes menghentikan pod (misalnya saat rolling update atau autoscaling scale-down), sinyal apa yang dikirimkan ke container, dan bagaimana konfigurasi Gunicorn serta `preStop` hook agar tidak ada request transaksi user yang terputus (HTTP 502 Bad Gateway)?

**Jawaban & Pembahasan:**
Kubernetes mengirimkan sinyal `SIGTERM` ke proses PID 1 di dalam container, menunggu selama `terminationGracePeriodSeconds` (default 30 detik), lalu mengirimkan `SIGKILL` jika proses belum selesai.

Masalah: Saat pod berstatus `Terminating`, Service controller membutuhkan waktu beberapa detik untuk memperbarui iptables/IPVS di seluruh worker node. Jika Gunicorn langsung berhenti seketika menerima `SIGTERM`, request baru yang masih dalam perjalanan dari load balancer akan menerima koneksi tertutup (TCP RST) atau 502 Bad Gateway.

**Solusi Konfigurasi:**
1. Tambahkan `preStop` lifecycle hook di Kubernetes manifest untuk menahan terminasi selama 5-10 detik:
```yaml
lifecycle:
  preStop:
    exec:
      command: ["/bin/sh", "-c", "sleep 5"]
```
2. Pastikan Dockerfile menggunakan format `exec` pada entrypoint (`CMD ["gunicorn", ...]` atau `exec gunicorn "$@"` di shell script) agar sinyal diteruskan langsung ke master process Gunicorn (PID 1).
3. Konfigurasikan Gunicorn graceful timeout:
```bash
gunicorn myproject.wsgi:application \
    --bind 0.0.0.0:8000 \
    --timeout 30 \
    --graceful-timeout 30
```
Dengan konfigurasi ini, Gunicorn menolak koneksi baru setelah timer preStop berakhir dan memberikan waktu 30 detik bagi worker untuk menyelesaikan in-flight transaction yang sedang berjalan.

---

### Soal 2.5: Host Header Injection & `ALLOWED_HOSTS` di Lingkungan Ingress/Load Balancer
**Pertanyaan:**
Pada deployment Kubernetes dengan Traefik/Ingress Nginx yang mengarahkan traffic domain `api.perusahaan.com` ke Service internal `django-service:8000`, mengapa menyetel `ALLOWED_HOSTS = ['*']` dilarang keras, dan bagaimana konfigurasi Django `settings.py` yang benar untuk menangani SSL forwarding?

**Jawaban & Pembahasan:**
Menyetel `ALLOWED_HOSTS = ['*']` membuka celah fatal terhadap **HTTP Host Header Attack**, di mana penyerang mengirimkan request dengan header `Host: attacker-controlled-domain.com`. Jika Django menggunakan `request.build_absolute_uri()` (misalnya saat menghasilkan tautan reset password, verifikasi email, atau OAuth redirect callback), token sensitif pengguna akan dikirimkan langsung ke server milik penyerang (password reset poisoning).

Konfigurasi yang aman dan benar:
```python
# settings.py
import os

ALLOWED_HOSTS = [
    'api.perusahaan.com',
    'django-service',            # Internal DNS cluster jika dipanggil antar-pod
    'django-service.default.svc.cluster.local',
]

# Percayakan header forwarded proto dari reverse proxy terpercaya (Ingress/ALB)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Paksa secure cookie
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# CSRF Trusted Origins untuk proteksi cross-site
CSRF_TRUSTED_ORIGINS = [
    'https://api.perusahaan.com',
]
```

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Skenario)

### Skenario 1: Bad Gateway (502) & Pod Crash Loop saat Flash Sale
**Deskripsi Masalah:**
Sebuah platform e-commerce berbasis Django di-deploy di cluster Kubernetes. Saat promo Flash Sale pukul 12:00 dimulai, traffic melonjak dari 500 RPS menjadi 15.000 RPS. Dalam 90 detik, status pod berubah menjadi `OOMKilled` berulang kali, load balancer mengembalikan status HTTP 502 Bad Gateway secara massal, dan sistem lumpuh total.

**Analisis Akar Masalah (Root Cause Analysis):**
1. **Memory Leak / Unbounded Queryset:** View katalog produk menggunakan ORM query tanpa pagination ketat dan memanggil `.all()` pada jutaan baris data, menginstansiasi Python model instance masif di heap memory worker.
2. **Worker Concurrency Over-Allocation:** Gunicorn dijalankan dengan sync worker bawaan (`-k sync -w 16`) per container, dengan limit memori Kubernetes `limits.memory: 512Mi`. Ketika 16 worker memproses query besar secara bersamaan, total konsumsi memori melampaui 512 MiB, memicu Linux Kernel OOM Killer menembak proses container.
3. **Thundering Herd di PostgreSQL:** Tanpa connection pooling, ribuan koneksi konkuren langsung membanjiri database, membuat latency query melesat dari 5ms ke 12.000ms. Worker Gunicorn menjadi hanging menunggu I/O socket, antrean request di ingress meluap, dan pod baru yang dispawn HPA langsung terbunuh sebelum readiness probe lolos.

**Langkah Penanganan & Solusi Arsitektur:**
1. **Hotfix Runtime:**
   - Turunkan worker Gunicorn ke formula aman: `(2 x $NUM_CORES) + 1` (misal 3-4 worker per pod) dengan thread mode (`-k gthread --threads 4`).
   - Naikkan Kubernetes pod limits ke `memory: 1Gi` atau `2Gi`, dengan request `memory: 512Mi`.
2. **Database & Connection Layer:**
   - Pasang PgBouncer di mode `transaction pooling` di antara Ingress dan PostgreSQL cluster.
3. **Aplikasi & Caching:**
   - Pasang Redis Cache cluster di depan katalog flash sale (`django.core.cache`) dengan TTL 15 detik untuk mengabsorbsi 99% read traffic.
   - Paksa paginasi ketat pada ORM level (`QuerySet[:50]`) dan gunakan `.only()` atau `.values()` untuk menghindari instansiasi model instance berlebihan.
4. **HPA Tuning:** Konfigurasikan Horizontal Pod Autoscaler berbasis CPU (threshold 60%) dan Custom Metric HTTP requests per second, dilengkapi PDB (*PodDisruptionBudget*) minimal 50% available.

---

### Skenario 2: Cold-Start Latency & Thundering Herd saat Rolling Update
**Deskripsi Masalah:**
Setiap kali tim engineering melakukan deployment versi baru via CI/CD, pengguna aktif melaporkan lonjakan latency drastis (response time naik dari 80ms ke 6.500ms) selama sekitar 2-3 menit pertama, disertai sejumlah timeout pada request pertama.

**Analisis Akar Masalah (Root Cause Analysis):**
1. **Ketiadaan App Warm-up:** Saat container baru dinyatakan "Ready", aplikasi Django belum menginisialisasi modul berat, koneksi pool DB belum dibuat, bytecode Python belum ter-cache di memori, dan data translasi/konfigurasi runtime baru di-load saat request pertama tiba (*lazy loading overhead*).
2. **Cache Stampede:** Deployment baru memicu invalidasi total cache versi sebelumnya, sehingga ribuan request masuk secara serentak memukul database untuk mengisi ulang cache yang kosong (*cold cache*).
3. **Readiness Probe yang Prematur:** Probe HTTP hanya mengecek status socket open (`TCP Socket Probe`) bukan kesiapan fungsional aplikasi, sehingga Service langsung mengalirkan beban penuh ke pod yang baru hidup.

**Langkah Penanganan & Solusi Arsitektur:**
1. **Gunakan Startup Probe dengan Endpoint Warm-up:**
```yaml
startupProbe:
  httpGet:
    path: /healthz/startup
    port: 8000
  failureThreshold: 30
  periodSeconds: 2
```
2. **Implementasikan Warm-up Logic di Handler `/healthz/startup`:**
   - Lakukan trigger eksekusi query penting sekali (warm-up DB connection).
   - Pre-load model ORM dan template engines.
   - Panggil cache priming routine jika memungkinkan.
3. **Rolling Update Strategy Rate Limiting:**
   Atur `maxSurge` dan `maxUnavailable` di Kubernetes Deployment manifest secara konservatif:
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 25%
    maxUnavailable: 0
```
   Memastikan tidak ada pod lama yang dimatikan sebelum pod baru 100% siap dan telah terisi cache.

---

### Skenario 3: File Asset Statis & Admin Panel Corrupted (CSS Hilang) Pasca Release
**Deskripsi Masalah:**
Setelah proses release production selesai menggunakan multi-instance container di Kubernetes, halaman Django Admin dan frontend statis menampilkan antarmuka tanpa CSS/JS (tampilan polos HTML rusak). Pada browser console terlihat ribuan error `404 Not Found` untuk file dengan hash seperti `/static/admin/css/base.b94b0d069695.css`.

**Analisis Akar Masalah (Root Cause Analysis):**
1. **Penyimpanan Statis Lokal Berbeda Hash:** Masing-masing pod kontainer menjalankan `collectstatic` sendiri pada waktu build yang berbeda atau menggunakan `ManifestStaticFilesStorage`. Pod versi lama yang masih melayani sebagian traffic merujuk pada hash file versi lama, sedangkan file fisik statis di-mount dari volume bersama yang sudah ditimpa oleh pod versi baru (atau sebaliknya).
2. **Reverse Proxy Tidak Terhubung ke Central Static Storage:** Nginx lokal di dalam container hanya memetakan direktori statis miliknya sendiri, sehingga saat traffic di-load balance secara acak antar-pod, terjadi mismatch antara HTML yang di-render pod A dengan file statis yang dicari di pod B.

**Langkah Penanganan & Solusi Arsitektur:**
1. **Offload Static Files ke CDN / S3:**
   - Gunakan `django-storages` dengan backend `S3Boto3Storage` atau Google Cloud Storage.
   - Jalankan `collectstatic` sekali saja pada pipeline CI/CD sebelum deployment pod dimulai:
```bash
python manage.py collectstatic --noinput
```
   - Seluruh aset statis diunggah langsung ke S3 Bucket dengan versioned prefix atau hash file unik.
2. **Penyedia CDN Global (Cloudflare / AWS CloudFront):**
   - Arahkan `STATIC_URL = "https://cdn.perusahaan.com/static/"`.
   - Karena file di-hash permanen (misal `base.b94b0d069695.css`), file versi lama dan versi baru dapat hidup berdampingan di S3/CDN tanpa saling menimpa, menjamin rolling update berjalan mulus bagi pengguna yang masih membuka halaman versi lama.

---

## Bagian 4: Practical Chapter Challenge

### Tantangan Praktis: Multi-Container Production-Grade Stack dengan Zero-Downtime Resilience

**Objektif:**
Bangun arsitektur deployment produksi lengkap berbasis `docker-compose.prod.yml` untuk aplikasi Django yang terhubung dengan PostgreSQL, Redis, PgBouncer, Nginx Reverse Proxy, dan Prometheus Exporter, dengan isolasi security non-root dan health check otomatis.

#### Arsitektur Direktori Target:
```text
production-stack/
├── docker-compose.prod.yml
├── nginx/
│   ├── Dockerfile
│   └── nginx.conf
├── pgbouncer/
│   ├── pgbouncer.ini
│   └── userlist.txt
├── django-app/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── requirements.txt
│   └── gunicorn.conf.py
```

#### Spesifikasi Kebutuhan Teknis:

1. **Dockerfile Django (Multi-Stage Build):**
   - Stage 1 (`builder`): Menggunakan base `python:3.12-slim`, install dependensi kompilasi OS, buat virtualenv di `/opt/venv`, compile dependencies dari `requirements.txt`.
   - Stage 2 (`runtime`): Base `python:3.12-slim`, salin hanya virtualenv `/opt/venv`, buat non-root user `appuser:appgroup` (UID/GID 10001), salin source code aplikasi dengan hak akses kepemilikan yang tepat.
   - Set environment variable: `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`, `PATH="/opt/venv/bin:$PATH"`.
   - Port ekspos: `8000`. User aktif: `10001`.

2. **Gunicorn Configuration (`gunicorn.conf.py`):**
   - Bind ke `0.0.0.0:8000`.
   - Workers: `3`, worker class: `gthread`, threads per worker: `3`.
   - Timeout: `30`, graceful timeout: `30`, keepalive: `5`.
   - Max requests: `1000` dengan jitter `100` (untuk mencegah memory leak akumulatif).

3. **PgBouncer Integration:**
   - Bertindak sebagai connection pooler di antara Django dan PostgreSQL.
   - Pool mode: `transaction`.
   - Default pool size: `20`, max client conn: `200`.

4. **Nginx Reverse Proxy:**
   - Menangani SSL termination (atau port 80 simulasi produksi).
   - Serving static files langsung via volume share `/app/staticfiles/` dengan caching header `Cache-Control "public, max-age=31536000, immutable"`.
   - Proxy pass ke upstream `django-app` dengan header:
     - `X-Forwarded-For $proxy_add_x_forwarded_for;`
     - `X-Forwarded-Proto $scheme;`
     - `Host $http_host;`
   - Buffer tuning: `proxy_buffers 16 16k; proxy_buffer_size 32k;`.

5. **Docker Compose Health Checks & Dependency Ordering:**
   - PostgreSQL harus memiliki `healthcheck` (`pg_isready`).
   - PgBouncer bergantung pada status `healthy` PostgreSQL.
   - Django app bergantung pada status `healthy` PgBouncer dan Redis.
   - Nginx bergantung pada Django app.

#### Acceptance Criteria:
- Menjalankan `docker compose -f docker-compose.prod.yml up -d --build` berhasil menaikkan seluruh container dalam status `Up (healthy)`.
- Mengakses `curl -I http://localhost/healthz/live` mengembalikan status `HTTP/1.1 200 OK`.
- Mengakses `curl -I http://localhost/static/admin/css/base.css` dilayani langsung oleh Nginx (memverifikasi header caching).
- Menjalankan `docker exec -it <django_container> whoami` menghasilkan output `appuser` (bukan root).
- Menguji penghentian kontainer secara graceful: `docker stop --time=35 <django_container>` menunjukkan proses menyelesaikan request aktif tanpa memicu error SIGKILL prematur.

---

## Bagian 5: Checklist Pemahaman Evaluasi Mandiri

Tandai `[x]` jika Anda telah menguasai konsep dan implementasi berikut:

- [ ] **Docker Engine & Image Security:**
  - [ ] Memahami perbedaan Alpine vs Debian-slim untuk ekosistem C-extension Python.
  - [ ] Mampu mengimplementasikan multi-stage build untuk meminimalkan image size dan membuang package compiler dari image final.
  - [ ] Mengonfigurasi container execution context menggunakan user non-root (UID > 10000).
  - [ ] Menggunakan `.dockerignore` komprehensif untuk mencegah kebocoran file kredensial `.env`, direktori `.git`, dan file cache Python.

- [ ] **WSGI/ASGI Production Tuning:**
  - [ ] Menghitung alokasi worker dan thread Gunicorn/Uvicorn berdasarkan formula kapasitas CPU host dan tipe workload (I/O bound vs CPU bound).
  - [ ] Mengonfigurasi worker recycling (`max_requests` dan `max_requests_jitter`) untuk menetralkan kebocoran memori (memory leak).
  - [ ] Mengonfigurasi timeout dan graceful termination window terhadap sinyal SIGTERM.

- [ ] **High Availability & Reverse Proxy:**
  - [ ] Mengonfigurasi Nginx untuk request buffering, gzip/brotli compression, dan SSL header forwarding (`X-Forwarded-Proto`).
  - [ ] Memisahkan serving static dan media files dari application process layer.
  - [ ] Mengonfigurasi connection pooler (PgBouncer) untuk mencegah database connection starvation pada scaling multi-instance.

- [ ] **Orkestrasi Kubernetes & Zero Downtime:**
  - [ ] Membedakan peruntukan `livenessProbe`, `readinessProbe`, dan `startupProbe` serta risikonya terhadap kaskade kegagalan pod.
  - [ ] Mampu menyusun workflow zero-downtime database migration menggunakan two-phase schema evolution dan isolated migration jobs.
  - [ ] Mengonfigurasi lifecycle hook `preStop` dan `terminationGracePeriodSeconds` untuk menghilangkan HTTP 502 saat rolling deploy.
  - [ ] Menentukan batasan `resources.requests` dan `resources.limits` untuk mencegah starvation dan OOMKilled liar pada node cluster.
