# BAB-01-Fondasi-dan-Arsitektur: Quiz, Challenge, & Knowledge Check

Dokumen evaluasi mandiri ini dirancang untuk menguji penguasaan konsep dasar, arsitektur internal, siklus request-response WSGI/ASGI, struktur modular, serta konfigurasi environment Django pada level production-grade.

---

## Bagian 1: 5 Basic Questions

### Soal 1
**Apa perbedaan arsitektural mendasar antara pola MVC (Model-View-Controller) klasik dan pola MVT (Model-View-Template) yang diadopsi oleh Django?**
- A. Django tidak memiliki komponen controller sama sekali dan menyerahkan routing ke web server.
- B. Django View bertindak sebagai Controller dalam terminologi MVC, sedangkan Django Template bertindak sebagai View, dan Django Framework core bertindak sebagai perantara controller tingkat rendah (URL dispatcher & request handler).
- C. Model pada Django berfungsi ganda sebagai routing table dan business logic layer.
- D. Django MVT menghapus abstraksi data layer dan langsung mengeksekusi raw query SQL di dalam template engine.

> **Kunci Jawaban:** **B**  
> **Pembahasan Teknis:**  
> Dalam arsitektur Django MVT, peran logika pemrosesan dan orchestration (Controller dalam MVC) diemban oleh **View** (baik function-based view maupun class-based view). Tampilan antarmuka atau presentasi (View dalam MVC) diimplementasikan oleh **Template**. URL dispatcher (`urls.py`) dan WSGI/ASGI handler dari core Django berfungsi sebagai Controller tingkat sistem yang mengarahkan request masuk ke view yang sesuai. Model tetap memegang peranan sebagai abstraksi database (ORM).

---

### Soal 2
**Manakah urutan siklus hidup (lifecycle) pemrosesan HTTP request yang benar sejak diterima oleh web server hingga response dikembalikan ke client pada Django?**
- A. Web Server $\rightarrow$ WSGI/ASGI Handler $\rightarrow$ URL Resolver $\rightarrow$ Middlewares (`process_request`) $\rightarrow$ View $\rightarrow$ Template Rendering $\rightarrow$ Middlewares (`process_response`) $\rightarrow$ Client Response.
- B. Web Server $\rightarrow$ View $\rightarrow$ Middlewares $\rightarrow$ URL Resolver $\rightarrow$ Database ORM $\rightarrow$ Client Response.
- C. Web Server $\rightarrow$ WSGI/ASGI Handler $\rightarrow$ Middleware Stack $\rightarrow$ URL Resolver $\rightarrow$ View $\rightarrow$ Middleware Stack (reverse order) $\rightarrow$ Web Server $\rightarrow$ Client Response.
- D. Web Server $\rightarrow$ Template Rendering $\rightarrow$ URL Resolver $\rightarrow$ Middleware $\rightarrow$ View $\rightarrow$ Client Response.

> **Kunci Jawaban:** **C**  
> **Pembahasan Teknis:**  
> Request masuk melalui Web Server (Nginx/Traefik) ke antarmuka WSGI/ASGI (Gunicorn/Uvicorn), lalu dikonversi menjadi objek `HttpRequest`. Objek ini melewati rantai middleware dari atas ke bawah (lapisan luar ke dalam). Setelah itu, `URLConf` mencocokkan pattern URI dan memanggil callable View. View menghasilkan `HttpResponse`, yang kemudian melewati rantai middleware secara terbalik (dari dalam ke luar) sebelum dikembalikan ke server dan client.

---

### Soal 3
**Apa implikasi teknis paling fatal dari mengekspos `DEBUG = True` pada environment production?**
- A. Django akan menonaktifkan fitur caching otomatis pada static files.
- B. Django akan menampilkan detailed traceback, environment variables, configuration parameters, dan sensitive keys saat terjadi unhandled exception, serta memakan memori berlebih karena mencatat riwayat setiap SQL query (`connection.queries`).
- C. Koneksi database PostgreSQL otomatis di-downgrade menjadi SQLite file-based in-memory database.
- D. Request HTTP otomatis ditolak dan hanya request melalui SSH tunnel yang diizinkan masuk.

> **Kunci Jawaban:** **B**  
> **Pembahasan Teknis:**  
> Saat `DEBUG = True`, error page Django menyertakan informasi diagnostik mendalam termasuk stack trace, locals frame variables, setting Django (yang berpotensi membocorkan `SECRET_KEY` atau kredensial database). Selain itu, Django ORM menyimpan metadata seluruh query ke dalam memori via `django.db.connection.queries`, yang dapat menyebabkan memory leak parah di bawah beban traffic produksi.

---

### Soal 4
**Mengapa arsitektur Django memisahkan entry point `wsgi.py` dan `asgi.py` pada root direktori project?**
- A. `wsgi.py` hanya digunakan untuk development server (`runserver`), sedangkan `asgi.py` wajib untuk PostgreSQL.
- B. `wsgi.py` menerapkan standar sinkronus PEP 3333 untuk traditional synchronous HTTP workers, sedangkan `asgi.py` menerapkan asynchronous specification untuk menangani protokol async seperti WebSockets, long polling, dan HTTP/2 streaming.
- C. `wsgi.py` dikhususkan untuk Python 2, sementara `asgi.py` dikhususkan untuk Python 3.
- D. `asgi.py` adalah pengganti usang dari `wsgi.py` yang sudah tidak didukung sejak rilis Django 4.0.

> **Kunci Jawaban:** **B**  
> **Pembahasan Teknis:**  
> WSGI (Web Server Gateway Interface, PEP 3333) bersifat blocking synchronous: 1 worker thread/process melayani 1 request hingga tuntas. ASGI (Asynchronous Server Gateway Interface) merupakan evolusi modern berbasis event loop `asyncio` yang memungkinkan eksekusi non-blocking concurrency, integrasi protokol real-time (WebSockets via Django Channels), and background streaming tanpa memblokir thread pool.

---

### Soal 5
**Perintah manakah yang benar untuk membuat aplikasi modular baru di dalam project Django tanpa mengacaukan struktur root direktori?**
- A. `django-admin makemodule my_app`
- B. `python manage.py startapp my_app apps/my_app` (setelah membuat folder `apps/my_app`)
- C. `python manage.py createapp --isolated my_app`
- D. `pip install my_app && django-admin link my_app`

> **Kunci Jawaban:** **B**  
> **Pembahasan Teknis:**  
> Perintah `python manage.py startapp <app_name> [destination_path]` memungkinkan penempatan source code aplikasi ke subdirektori modular (seperti `apps/my_app` atau `core/my_app`). Cara ini menjaga repository tetap rapi saat project memiliki puluhan domain context terpisah.

---

## Bagian 2: 5 Intermediate Questions

### Soal 6
**Perhatikan snippet middleware berikut:**

```python
class RequestMetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Tahap A
        response = self.get_response(request)
        # Tahap B
        return response
```

**Jika sebuah exception terjadi di dalam View dan TIDAK ditangkap (unhandled), bagaimanakah alur eksekusi pada middleware ini jika tidak ada `process_exception` yang didefinisikan?**
- A. Tahap B tetap dieksekusi dengan `response` bernilai status HTTP 500.
- B. Tahap B dilewati sepenuhnya; exception propagate ke middleware pembungkus di atasnya hingga mencapai handler exception Django core.
- C. Django mengulang pemanggilan `self.get_response(request)` hingga 3 kali.
- D. Middleware otomatis merubah status response menjadi HTTP 400 Bad Request.

> **Kunci Jawaban:** **B**  
> **Pembahasan Teknis:**  
> Pada closure-based middleware modern (Django 1.10+), `response = self.get_response(request)` membungkus middleware berikutnya atau view. Jika view memicu unhandled exception dan tidak ada hook `process_exception` yang menangkap dan mengembalikan `HttpResponse`, python call stack akan memotong eksekusi normal. Kode pada **Tahap B** tidak akan pernah dieksekusi, dan exception akan terus dilempar ke atas hingga ditangkap oleh exception handler Django root untuk merender halaman HTTP 500.

---

### Soal 7
**Dalam konfigurasi `ALLOWED_HOSTS = ['api.example.com', '.example.com']`, manakah domain berikut yang AKAN DITOLAK oleh `CommonMiddleware` atau security check Django?**
- A. `sub.example.com`
- B. `api.example.com`
- C. `test.sub.example.com`
- D. `example.com.attacker.com`

> **Kunci Jawaban:** **D**  
> **Pembahasan Teknis:**  
> Awalan titik (`.example.com`) pada `ALLOWED_HOSTS` adalah wildcard subdomain yang mencocokkan `example.com`, `sub.example.com`, hingga `test.sub.example.com`. Domain `example.com.attacker.com` memiliki suffix top-level domain yang berbeda sama sekali (`attacker.com`), sehingga validasi header HTTP `Host` akan memicu `DisallowedHost` exception (HTTP 400).

---

### Soal 8
**Apa perbedaan fungsional utama antara file `settings/base.py`, `settings/production.py`, dan `settings/local.py` dalam pola Twelve-Factor App Django?**
- A. `base.py` berisi credential rahasia, sedangkan `production.py` berisi mock testing unit.
- B. `base.py` berisi konfigurasi domain agnostik (installed apps, middleware, template engine, logging formatters), sedangkan `production.py` dan `local.py` meng-override konfigurasi spesifik infrastruktur (database backend, debug toggle, SSL redirect, caching engine, cookie security flag) yang diisi via environment variables.
- C. `production.py` wajib dikompilasi menjadi bytecode `.pyc` sebelum dapat dieksekusi, sedangkan `local.py` tidak.
- D. `local.py` menonaktifkan migration engine dan ORM.

> **Kunci Jawaban:** **B**  
> **Pembahasan Teknis:**  
> Pola pemisahan setting multi-environment mengikuti prinsip Twelve-Factor App (Config in Environment). `base.py` memuat konfigurasi fondasi yang konsisten di semua target deployment. `local.py` mengutamakan developer ergonomics (`DEBUG=True`, console email backend, relaxed CORS). `production.py` menerapkan hardening security (`DEBUG=False`, `SECURE_SSL_REDIRECT=True`, `SESSION_COOKIE_SECURE=True`, persistent connection pooling, connection ke managed Postgres/Redis cluster via environment variables).

---

### Soal 9
**Mengapa penggunaan `SECRET_KEY` statis yang di-commit ke Git repository publik/internal sangat berbahaya pada Django, bahkan jika aplikasi tidak menggunakan session database?**
- A. `SECRET_KEY` digunakan untuk men-generate primary key integer pada PostgreSQL.
- B. `SECRET_KEY` adalah salt cryptographic untuk cryptographic signing: CSRF tokens, signed cookies, password reset tokens, dan session data terenkripsi. Penyerang yang mengetahui `SECRET_KEY` dapat memalsukan session token atau melakukan replay attack.
- C. Django akan gagal startup jika mendeteksi git commit hash pada file settings.
- D. `SECRET_KEY` membuka endpoint debugger `/django-admin-secret/` secara otomatis.

> **Kunci Jawaban:** **B**  
> **Pembahasan Teknis:**  
> Modul `django.core.signing` mengandalkan `SECRET_KEY` sebagai kunci HMAC. Jika secret key bocor, penyerang dapat merekayasa payload signed cookie (`django.contrib.sessions.backends.signed_cookies`), memalsukan token reset kata sandi, membypass proteksi form CSRF, atau membongkar signed message yang dikirimkan antara service internal.

---

### Soal 10
**Pada Django 4.2+ / 5.0+, apa fungsi dari setting `STORAGES` dictionary yang menggantikan `DEFAULT_FILE_STORAGE` dan `STATICFILES_STORAGE`?**
- A. Mengatur partisi tabel database untuk media files.
- B. Menyediakan konfigurasi terpusat dan decoupled untuk backend storage (misal: `"default"` untuk user media upload seperti AWS S3/GCS dan `"staticfiles"` untuk manifest static collection via WhiteNoise atau CDN).
- C. Mengganti penggunaan file sistem Linux dengan RAM disk in-memory secara mutlak.
- D. Membatasi ukuran upload file langsung dari kernel level.

> **Kunci Jawaban:** **B**  
> **Pembahasan Teknis:**  
> Sejak Django 4.2, arsitektur storage dirombak menjadi dictionary `STORAGES = {"default": {...}, "staticfiles": {...}}`. Hal ini merapikan integrasi library third-party (seperti `django-storages` untuk S3/MinIO atau `WhiteNoise` untuk `ManifestStaticFilesStorage`) dengan konfigurasi options independen untuk caching header, expiration, dan custom buckets.

---

## Bagian 3: 3 Skenario Kasus Nyata Produksi

---

### Skenario 1: Incident Reverse Proxy & Infinite Redirect Loop pada HTTPS

#### Latar Belakang Masalah
Tim DevOps memasang arsitektur baru: Load Balancer / Reverse Proxy (AWS ALB / Cloudflare / Nginx) di depan Django Gunicorn instance. Komunikasi dari browser ke Cloudflare menggunakan HTTPS (`443`), namun komunikasi antara Cloudflare ke Django di VM internal menggunakan HTTP biasa (`8080`) untuk menghemat resource SSL termination.

Setelah mengaktifkan setting hardening keamanan:
```python
SECURE_SSL_REDIRECT = True
```
Pengguna melaporkan bahwa website tidak bisa dibuka dengan pesan browser:  
`ERR_TOO_MANY_REDIRECTS` (HTTP 301 loop tanpa henti).

#### Root Cause Analysis
1. Browser mengakses `https://example.com/api/v1/resource/`.
2. Cloudflare menerima request via HTTPS, lalu melakukan SSL termination dan mem-forward request ke Gunicorn/Django via HTTP: `http://10.0.1.15:8080/api/v1/resource/`.
3. Django memeriksa `request.is_secure()`. Karena request internal masuk lewat HTTP socket biasa, Django menganggap request tersebut tidak aman (`request.is_secure() == False`).
4. Karena `SECURE_SSL_REDIRECT = True`, middleware `SecurityMiddleware` mengembalikan response `301 Moved Permanently` mengarah kembali ke `https://example.com/api/v1/resource/`.
5. Browser menerima 301, mengirim request ulang ke HTTPS, Cloudflare kembali mengirim HTTP internal, dan loop berulang tanpa batas.

#### Solusi Arsitektural & Implementasi
Konfigurasikan Django agar membaca header reverse proxy standar (seperti `X-Forwarded-Proto`) dan pastikan web server upstream mengirimkan header tersebut secara terpercaya:

**1. Update `settings/production.py`:**
```python
# Memberitahu Django bahwa request aman (HTTPS) jika proxy menyertakan header ini
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
```

**2. Verifikasi Upstream (Contoh Nginx Config):**
```nginx
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header Host $http_host;
```

> **Warning Keamanan:** Jangan pernah mengaktifkan `SECURE_PROXY_SSL_HEADER` jika instance Django dapat diakses langsung oleh publik tanpa melalui reverse proxy terpercaya, karena attacker dapat menginjeksi header `X-Forwarded-Proto: https` palsu untuk membypass pemeriksaan keamanan.

---

### Skenario 2: Memory Leak Spike Akibat Misplaced Database Profiling di Production

#### Latar Belakang Masalah
Aplikasi e-commerce Django mengalami lonjakan pemakaian RAM (OOM - *Out Of Memory Killer*) setiap beberapa jam setelah traffic promosi diluncurkan. Jumlah worker Gunicorn berangsur-angsur membengkak dari 150 MB per worker menjadi lebih dari 2.5 GB per worker hingga server mengalami kernel panic.

#### Root Cause Analysis
Setelah inspeksi codebase, ditemukan potongan kode auditing yang dipasang developer untuk debugging query lambat:

```python
# core/middlewares.py (Anti-pattern berbahaya)
from django.db import connection
import logging

logger = logging.getLogger(__name__)

class QueryAuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Menulis query log jika query lebih dari 20
        if len(connection.queries) > 20:
            logger.warning(f"High query count on {request.path}: {len(connection.queries)}")
        return response
```

Dan di `settings/production.py`:
```python
# Developer lupa mengubah flag ini sebelum release
DEBUG = True
```

Ketika `DEBUG = True`, Django ORM akan meng-append setiap query SQL yang dieksekusi beserta timing dan stack trace-nya ke dalam list in-memory `connection.queries`. Pada request berbeban tinggi atau long-running worker process, list ini tidak pernah di-garbage collect secara instan, sehingga memakan memori hingga ratusan megabyte per seribu request.

#### Solusi Arsitektural & Implementasi
1. **Wajib Mematikan DEBUG:**
   ```python
   # settings/production.py
   DEBUG = False
   ```
2. **Hapus Akses `connection.queries` di Production Code:**
   Gunakan tools Application Performance Monitoring (APM) standar industri seperti Sentry, OpenTelemetry, atau `django-prometheus` tanpa mengorbankan memory heap.
3. **Jika Ingin Menghitung Query Tanpa Menyimpan Trace List:**
   Gunakan wrapper connection hook atau library `django-silk` (hanya di staging) atau implementasikan counter lightweight:
   ```python
   # Lightweight Query Counter tanpa menyimpan query strings
   from django.db import connection
   from django.db.backends.utils import CursorDebugWrapper

   class SafeQueryCountMiddleware:
       def __init__(self, get_response):
           self.get_response = get_response

       def __call__(self, request):
           initial_queries = len(connection.queries) if settings.DEBUG else 0
           response = self.get_response(request)
           return response
   ```
4. **Konfigurasi Restart Worker Gunicorn Secara Periodik (Mitigasi OOM):**
   ```bash
   gunicorn core.wsgi:application \
       --workers 4 \
       --max-requests 1000 \
       --max-requests-jitter 100 \
       --bind 0.0.0.0:8000
   ```
   Opsi `--max-requests` dan `--max-requests-jitter` memaksa worker me-recycle process setelah memproses sejumlah request, membebaskan alokasi heap fragmentation.

---

### Skenario 3: Cross-Site Request Forgery (CSRF) Failure pada Arsitektur Decoupled SPA / Mobile App

#### Latar Belakang Masalah
Frontend web berbasis Next.js (berjalan di domain `https://app.client.com`) mengonsumsi REST API Django yang berada di domain `https://api.client.com`. Ketika user melakukan request `POST /api/v1/checkout/`, Django mengembalikan error:  
`HTTP 403 Forbidden - CSRF verification failed. Request aborted.`

Developer tergoda untuk langsung menonaktifkan CSRF dengan decorator `@csrf_exempt` di seluruh endpoint API.

#### Evaluasi & Dampak Keamanan `@csrf_exempt`
Menonaktifkan `@csrf_exempt` secara massal membuka celah eksploitasi CSRF jika autentikasi backend menggunakan session berbasis cookie (`SessionAuthentication`). Jika attacker membuat website phising, browser korban yang memiliki valid session cookie dapat dipaksa melakukan transaksi checkout tanpa disadari.

#### Solusi Arsitektural Sesuai Standard Keamanan
Tergantung pada arsitektur autentikasi yang digunakan:

**Solusi A: Jika Menggunakan Cookie-Based Session (Cross-Domain SPA):**
1. Konfigurasikan CORS dan Cookie attributes di `settings/production.py`:
   ```python
   # Izinkan origin frontend
   CORS_ALLOWED_ORIGINS = [
       "https://app.client.com",
   ]
   CORS_ALLOW_CREDENTIALS = True

   # Izinkan domain terpercaya untuk verifikasi CSRF
   CSRF_TRUSTED_ORIGINS = [
       "https://app.client.com",
       "https://api.client.com",
   ]

   # Cookie settings untuk cross-subdomain
   SESSION_COOKIE_DOMAIN = ".client.com"
   CSRF_COOKIE_DOMAIN = ".client.com"
   CSRF_COOKIE_SAMESITE = 'Lax'
   SESSION_COOKIE_SAMESITE = 'Lax'
   CSRF_COOKIE_HTTPONLY = False  # Agar frontend JavaScript bisa membaca token CSRF jika diperlukan
   CSRF_COOKIE_SECURE = True
   SESSION_COOKIE_SECURE = True
   ```
2. Frontend wajib membaca nilai cookie `csrftoken` dan menyertakannya di HTTP request header `X-CSRFToken`.

**Solusi B: Jika Pure Stateless REST API / Mobile App (Token-Based / JWT):**
Jika autentikasi sepenuhnya menggunakan header `Authorization: Bearer <token>`, maka endpoint API **secara arsitektural imun terhadap browser CSRF attack** (karena browser tidak otomatis melampirkan header Authorization khusus). Dalam konteks ini, penggunaan middleware CSRF dapat diisolasi:
1. Pastikan view API menggunakan Django REST Framework dengan `DEFAULT_AUTHENTICATION_CLASSES = ['rest_framework.authentication.TokenAuthentication']` atau JWT, bukan `SessionAuthentication`.
2. Jangan hapus `CsrfViewMiddleware` dari global pipeline, melainkan delegasikan proteksi kepada DRF authentication class yang secara native menonaktifkan CSRF check untuk non-session authentication.

---

## Bagian 4: Practical Chapter Challenge

### Judul Tantangan: "The Enterprise Multi-Environment & Healthcheck Scaffold"

#### Objektif
Rancang dan susun struktur direktori proyek Django standar enterprise yang mengisolasi konfigurasi environment (`base`, `local`, `production`), memuat environment variable secara aman, dan mengimplementasikan Custom Middleware pencatat latency request beserta custom Healthcheck endpoint untuk orkestrasi Docker/Kubernetes.

#### Spesifikasi Kebutuhan

1. **Struktur Direktori:**
   ```text
   enterprise_core/
   ├── manage.py
   ├── apps/
   │   └── common/
   │       ├── __init__.py
   │       ├── apps.py
   │       ├── urls.py
   │       └── views.py
   ├── enterprise_core/
   │   ├── __init__.py
   │   ├── wsgi.py
   │   ├── asgi.py
   │   ├── urls.py
   │   └── settings/
   │       ├── __init__.py
   │       ├── base.py
   │       ├── local.py
   │       └── production.py
   ```

2. **File `enterprise_core/settings/base.py`:**
   - Membaca `SECRET_KEY` dari environment variable. Jika tidak ada dan `DJANGO_ENV=production`, lempar `django.core.exceptions.ImproperlyConfigured`.
   - Konfigurasi `INSTALLED_APPS` memuat `apps.common.apps.CommonConfig`.
   - Rantai `MIDDLEWARE` wajib memuat custom middleware `apps.common.middleware.RequestLatencyMetricMiddleware`.

3. **Custom Middleware (`apps/common/middleware.py`):**
   - Mengukur durasi eksekusi request dalam milidetik (ms) menggunakan `time.perf_counter()`.
   - Menyisipkan custom header `X-Response-Time-Ms` pada setiap response keluar.
   - Mengabaikan logging pada static/media request.

4. **Health Check Endpoint (`/healthz`):**
   - Melakukan ping aktif ke koneksi database utama (`django.db.connection.ensure_connection()`).
   - Jika database responsif: mengembalikan `JsonResponse({"status": "healthy", "database": "connected"}, status=200)`.
   - Jika koneksi database putus/error: mengembalikan `JsonResponse({"status": "unhealthy", "error": str(err)}, status=503)`.

#### Blueprint Kode Solusi

##### 1. `apps/common/middleware.py`
```python
import time
import logging

logger = logging.getLogger("enterprise.performance")

class RequestLatencyMetricMiddleware:
    """
    Middleware untuk mencatat latency eksekusi request-response cycle
    dan menyematkan header X-Response-Time-Ms.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Catat waktu awal
        start_time = time.perf_counter()

        # Eksekusi rantai middleware berikutnya dan view
        response = self.get_response(request)

        # Hitung durasi (ms)
        duration = (time.perf_counter() - start_time) * 1000
        duration_formatted = f"{duration:.2f}"

        # Pasang header diagnostic
        response["X-Response-Time-Ms"] = duration_formatted

        # Log jika request lambat (> 500ms)
        if duration > 500:
            logger.warning(
                f"[SLOW REQUEST] {request.method} {request.get_full_path()} "
                f"took {duration_formatted}ms | Status: {response.status_code}"
            )

        return response
```

##### 2. `apps/common/views.py`
```python
from django.http import JsonResponse
from django.db import connection
from django.db.utils import OperationalError
import logging

logger = logging.getLogger("enterprise.healthcheck")

def liveness_probe(request):
    """
    Liveness probe sederhana: Memastikan HTTP worker hidup.
    """
    return JsonResponse({"status": "alive"}, status=200)

def readiness_healthz(request):
    """
    Readiness probe untuk Kubernetes/Load Balancer.
    Memverifikasi koneksi fisik ke database.
    """
    try:
        connection.ensure_connection()
        return JsonResponse(
            {
                "status": "healthy",
                "database": "connected",
                "engine": connection.vendor
            },
            status=200
        )
    except OperationalError as exc:
        logger.error(f"Healthcheck failed: Database unreachable - {exc}")
        return JsonResponse(
            {
                "status": "unhealthy",
                "database": "disconnected",
                "detail": "Database service unavailable"
            },
            status=503
        )
```

##### 3. `enterprise_core/settings/production.py`
```python
import os
from enterprise_core.settings.base import *
from django.core.exceptions import ImproperlyConfigured

DEBUG = False

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY environment variable wajib didefinisikan di production!")

ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",")
if not ALLOWED_HOSTS or ALLOWED_HOSTS == [""]:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS wajib diisi dengan domain valid!")

# Security Hardening Settings
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000  # 1 Tahun
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

---

## Bagian 5: Checklist Pemahaman Mandiri

Berikan tanda centang ($[\checkmark]$) jika Anda telah memahami konsep-konsep inti berikut sebelum melangkah ke bab berikutnya:

- [ ] **Siklus Request-Response:** Mampu memetakan secara detail perjalanan objek `HttpRequest` melalui WSGI/ASGI handler, urutan eksekusi Middleware pipeline, URL routing resolution, eksekusi View, hingga serialisasi `HttpResponse`.
- [ ] **Arsitektur MVT:** Memahami secara mendalam batas tanggung jawab antara Model (Data & Storage abstraction), View (Controller orchestration & Business logic), dan Template (Representation presentation).
- [ ] **Pemisahan Environment Konfigurasi:** Menguasai pola modular settings (`base.py`, `local.py`, `production.py`) dan anti-hardcoding credential menggunakan Twelve-Factor App principles.
- [ ] **Middleware Internals:** Memahami siklus `__init__`, `__call__`, exception bubbling, dan implikasi urutan registrasi pada array `MIDDLEWARE`.
- [ ] **Security Fundamentals:** Memahami bahaya kebocoran `SECRET_KEY`, resiko performa/kebocoran data saat `DEBUG = True`, cara kerja proteksi CSRF, dan konfigurasi SSL Termination dengan `SECURE_PROXY_SSL_HEADER`.
- [ ] **Health & Observability:** Mampu membangun endpoint diagnostic ketersediaan database (`/healthz`) untuk orkestrasi deployment zero-downtime (Docker/K8s).
