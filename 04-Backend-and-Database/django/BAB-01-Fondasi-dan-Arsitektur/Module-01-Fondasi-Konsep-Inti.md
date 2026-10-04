# Bab 01 Module 01: Arsitektur Inti Django, Siklus Hidup Request-Response, dan Pola MVT

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Menganalisis** siklus hidup internal eksekusi HTTP request dari lapisan WSGI/ASGI handler hingga socket response buffer pada Django core.
*   **Menguraikan** perbedaan arsitektural antara Model-View-Controller (MVC) klasik dan Model-View-Template (MVT) Django beserta implikasi pembagian tanggung jawab (*separation of concerns*).
*   **Mengimplementasikan** middleware kustom dengan pemahaman deterministik terhadap urutan eksekusi *onion model* (fase *request*, *view*, *exception*, dan *response*).
*   **Mendiagnosis** dan memitigasi degradasi performa pada *URL resolving*, *middleware overhead*, dan kebocoran state antar-request pada lingkungan multi-threaded/asynchronous.

---

### 2. Conceptual Foundation
Django dibangun di atas filosofi desain *Don't Repeat Yourself* (DRY), *Explicit is better than implicit*, dan *Loose Coupling with Tight Cohesion*. Secara historis, Django dirancang pada tahun 2003 di lingkungan ruang redaksi surat kabar (Lawrence Journal-World) untuk mengakomodasi tenggat waktu yang ketat sembari mempertahankan arsitektur perangkat lunak web yang bersih dan terstruktur.

Pondasi arsitektur Django berakar pada varian pola arsitektur MVC yang disebut **Model-View-Template (MVT)**:
*   **Model**: Lapisan abstraksi data berbasis Object-Relational Mapping (ORM) yang merangkum skema basis data, validasi bisnis, dan integritas relasional. Model tidak mengetahui bagaimana data akan direpresentasikan secara visual.
*   **View**: Lapisan logika aplikasi (*controller* fungsional) yang memproses HTTP request, berinteraksi dengan ORM, dan mengembalikan objek `HttpResponse`. View di Django bukan representasi visual, melainkan mediator logika.
*   **Template**: Lapisan presentasi deklaratif yang memisahkan sintaks desain dari eksekusi kode Python murni. Django Template Language (DTL) dirancang sengaja tidak mengeksekusi sembarang kode Python (*sandboxed execution*) guna mencegah polusi logika domain di lapisan antarmuka.

Di tingkat sistem operasi dan jaringan, Django mengabstraksi protokol HTTP melalui standar WSGI (PEP 3333) atau ASGI. Django bertindak sebagai aplikasi callable yang menerima environ dictionary dan start_response callable dari application server (seperti Gunicorn, uWSGI, atau Daphne).

---

### 3. Why This Matters
Memahami siklus hidup internal request-response dan abstraksi MVT adalah pembeda fundamental antara junior developer yang sekadar menyalin konfigurasi dengan senior engineer yang mampu merancang sistem berskala besar (*high-throughput*).

Tanpa pemahaman siklus request-response yang mendalam:
1.  **Kegagalan Skalabilitas**: Eksekusi query basis data secara tidak sengaja di dalam template (*N+1 queries*) atau middleware blocking yang mematikan thread pool server.
2.  **State Contamination**: Menyimpan state berbasis mutasi global atau thread-local yang tidak dibersihkan dengan benar, memicu kebocoran data pengguna (*data cross-contamination*) pada web server berbasis multi-threading (misalnya Gunicorn dengan worker gthread).
3.  **Kesalahan Diagnostik**: Ketidakmampuan melacak di mana suatu exception terjadi dalam pipeline (apakah di routing layer, middleware stack, view processing, atau template rendering engine).

---

### 4. What It Is: Technical Breakdown
Sistem Django beroperasi berdasarkan rantai komponen hierarkis:

```
[Client Socket] 
       │ (HTTP Protocol)
[Reverse Proxy: Nginx] 
       │ (Unix Socket / TCP)
[WSGI/ASGI Server: Gunicorn/Uvicorn] 
       │ (PEP 3333 / ASGI Spec)
[Django Entrypoint: wsgi.py / asgi.py]
       │
[WSGIHandler / ASGIHandler]
       │
[Middleware Stack (Onion Pattern)]
       │
[URL Resolver: URLConf Pattern Matching]
       │
[View Processing (CBV / FBV)]
       ├── [Model Layer / ORM] ──> [Database Engine]
       └── [Template Engine]   ──> [Disk Cache / Compiled Nodes]
       │
[Middleware Response Chain]
       │
[HTTP Response Serialization]
```

#### Komponen Internal Kunci:
1.  **`WSGIHandler` (`django.core.handlers.wsgi.WSGIHandler`)**: Turunan dari `base.BaseHandler`. Menginisialisasi request factory, memuat middleware stack ke memori saat server start-up, dan menangani alur eksekusi request melalui metode `__call__(environ, start_response)`.
2.  **`WSGIRequest` (`django.core.handlers.wsgi.WSGIRequest`)**: Representasi objek Python dari `environ` WSGI. Mengurai header HTTP, query parameter, dan payload body secara malas (*lazy parsing*).
3.  **`URLResolver` (`django.urls.resolvers.URLResolver`)**: Membaca konfigurasi `ROOT_URLCONF`. Mengompilasi regex/path pattern menjadi pohon rute (*routing tree*) dalam memori untuk mencocokkan URI path dengan view handler yang tepat.
4.  **Middleware Chain**: Rangkaian fungsi pembungkus (*wrappers*) berstruktur *Russian Doll* / *Onion Model*. Middleware membungkus view ke dalam closure berlapis menggunakan pola desain Chain of Responsibility.

---

### 5. How It Works
Eksekusi sebuah HTTP Request di Django berjalan melalui tahapan kronologis berikut:

1.  **Inisialisasi Request**: Server WSGI menerima HTTP request, mem-parsing header ke dictionary `environ`, lalu memanggil instance `WSGIHandler`.
2.  **Instansiasi `WSGIRequest`**: Handler membungkus `environ` ke dalam objek `django.http.HttpRequest` (spesifiknya `WSGIRequest`). Objek ini dialokasikan di memori thread kerja.
3.  **Traversing Middleware (Fase Masuk)**:
    *   Eksekusi dimulai dari middleware terluar hingga terdalam.
    *   Kode sebelum pemanggilan `get_response(request)` dieksekusi secara berurutan.
    *   Jika salah satu middleware mengembalikan objek `HttpResponse` langsung (short-circuit), eksekusi rantai di bawahnya dan view dibatalkan seketika, langsung melompat ke fase keluar middleware.
4.  **URL Resolution**:
    *   Django memanggil `resolve(request.path_info)`.
    *   `URLResolver` mencocokkan string URI terhadap pola regex/path yang ditentukan di `ROOT_URLCONF`.
    *   Resolusi menghasilkan `ResolverMatch` yang berisi referensi callable view, argumen posisi (`args`), dan argumen kata kunci (`kwargs`).
5.  **View Execution**:
    *   Middleware yang mengimplementasikan `process_view()` dieksekusi secara berurutan.
    *   View callable dipanggil dengan signature `view_func(request, *args, **kwargs)`.
    *   View berinteraksi dengan ORM (menjalankan query SQL lazily via database connection cursor) atau layanan eksternal.
6.  **Template Rendering (Jika ada)**:
    *   View memanggil engine template dengan context dictionary.
    *   Token parsing dan node rendering mengubah template tree menjadi plain string (HTML/JSON).
    *   Middleware yang mengimplementasikan `process_template_response()` dipanggil jika response merupakan instance dari `SimpleTemplateResponse`.
7.  **Traversing Middleware (Fase Keluar)**:
    *   View mengembalikan instance `HttpResponse`.
    *   Kode setelah `response = get_response(request)` pada middleware dieksekusi dalam urutan terbalik (*reverse order* / LIFO).
8.  **Proses Exception**:
    *   Jika terjadi exception yang tidak tertangani di lapisan view, handler menelusuri stack middleware secara terbalik untuk mencari metode `process_exception()`. Jika tidak ada yang menangani, Django mengeksekusi handler bawaan (`handler500`).
9.  **Response Return & Socket Transmission**:
    *   `WSGIHandler` mengubah status code, headers, dan payload body `HttpResponse` menjadi argumen `start_response` WSGI.
    *   Buffer byte dialirkan kembali ke WSGI server untuk dikirim melalui TCP socket ke client.

---

### 6. Architecture & Data Flow Diagram

```
                 HTTP Request (TCP Socket via Web Server)
                                    │
                                    ▼
                     ┌─────────────────────────────┐
                     │     WSGI/ASGI Handler       │
                     │  (Instansiasi WSGIRequest)  │
                     └──────────────┬──────────────┘
                                    │
                                    ▼
┌───────────────────────────────────┴───────────────────────────────────┐
│                          MIDDLEWARE STACK                             │
│                                                                       │
│   Middleware 1 (Inbound)                                              │
│     │  request modified / short-circuit check                         │
│     ▼                                                                 │
│   Middleware 2 (Inbound)                                              │
│     │  Authentication, Session hydration                              │
│     ▼                                                                 │
│   Middleware N (Inbound)                                              │
│     │  Security checks, CSRF validation                               │
│     ▼                                                                 │
│   ┌───────────────────────────────────────────────────────────────┐   │
│   │                        URL RESOLVER                           │   │
│   │   Regex / Path Match -> Resolve URL to View Callable          │   │
│   └───────────────────────────────┬───────────────────────────────┘   │
│                                   │                                   │
│                                   ▼                                   │
│   ┌───────────────────────────────────────────────────────────────┐   │
│   │                         VIEW LOGIC                            │   │
│   │                                                               │   │
│   │    ┌──────────────┐                       ┌──────────────┐    │   │
│   │    │  ORM Model   │ <--- DB Engine        │   Template   │    │   │
│   │    │ (Data Query) │      (PostgreSQL)     │ (DTL Engine) │    │   │
│   │    └──────┬───────┘                       └──────┬───────┘    │   │
│   │           └───────────────┬──────────────────────┘            │   │
│   │                           ▼                                   │   │
│   │            Return HttpResponse Instance                       │   │
│   └───────────────────────────────┬───────────────────────────────┘   │
│                                   │                                   │
│   Middleware N (Outbound)         ▼                                   │
│     │  Modify response headers, Set-Cookie                            │
│     ▼                                                                 │
│   Middleware 2 (Outbound)                                             │
│     │  Cache controls, GZip compression                               │
│     ▼                                                                 │
│   Middleware 1 (Outbound)                                             │
│     │  Logging metrics, Telemetry                                     │
└───────────────────────────────────┬───────────────────────────────────┘
                                    │
                                    ▼
                 HTTP Response (Status, Headers, Content)
```

---

### 7. Minimal Deterministic Example
Berikut adalah implementasi aplikasi Django *single-file* mandiri yang mendemonstrasikan siklus hidup request-response secara deterministik tanpa scaffold `django-admin startproject`.

Simpan kode ini sebagai `app.py`:

```python
import sys
from django.conf import settings
from django.core.handlers.wsgi import WSGIHandler
from django.core.management import execute_from_command_line
from django.http import HttpRequest, HttpResponse
from django.urls import path

# 1. Konfigurasi Sistem Minimalis
if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY="deterministic-insecure-secret-key-for-demonstration-purposes-only",
        ROOT_URLCONF=__name__,
        ALLOWED_HOSTS=["*"],
        MIDDLEWARE=[
            "__main__.LifecycleLoggingMiddleware",
        ],
    )

# 2. Middleware Demonstrasi Alur Eksekusi
class LifecycleLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        print("[Middleware] 1. Request masuk, menuju ke routing dan view.")
        
        # Eksekusi rantai request menuju view
        response = self.get_response(request)
        
        print("[Middleware] 2. Response keluar, bersiap dikirim ke client.")
        response.headers["X-Lifecycle-Check"] = "Passed"
        return response

# 3. View Processing (Logika Inti)
def index_view(request: HttpRequest) -> HttpResponse:
    print("[View] Processing request di index_view.")
    return HttpResponse(
        "<h1>Django Request-Response Pipeline Aktif</h1>",
        content_type="text/html; charset=utf-8",
        status=200
    )

# 4. Routing URL Configuration
urlpatterns = [
    path("", index_view, name="index"),
]

# 5. Handler Instantiation
application = WSGIHandler()

if __name__ == "__main__":
    execute_from_command_line(sys.argv)
```

Jalankan dengan perintah:
```bash
python app.py runserver 127.0.0.1:8000
```

---

### 8. Practical Production Implementation
Contoh berikut merepresentasikan struktur arsitektur modular tingkat produksi untuk melacak latensi sistem dan audit request menggunakan custom middleware berbasis async-compatible callable, disertai penanganan error terstruktur.

#### `middleware.py`
```python
import time
import logging
import uuid
from typing import Callable
from django.http import HttpRequest, HttpResponse, JsonResponse

logger = logging.getLogger("core.telemetry")

class ProductionRequestLifecycleMiddleware:
    """
    Middleware industri: Menangani inject correlation ID, perhitungan durasi
    eksekusi request, dan isolasi penanganan unhandled exceptions secara aman.
    """
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Generate atau ekstrak Request ID untuk trace logging terdistribusi
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.request_id = request_id
        start_time = time.perf_counter()

        logger.info(
            "Request Started: method=%s path=%s request_id=%s",
            request.method,
            request.path,
            request_id
        )

        try:
            response = self.get_response(request)
        except Exception as exc:
            # Delegasi log sistematis sebelum diserahkan ke process_exception
            logger.exception(
                "Unhandled Exception Caught: request_id=%s error=%s",
                request_id,
                str(exc)
            )
            response = JsonResponse(
                {
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "Terjadi kesalahan internal pada pemrosesan server.",
                        "request_id": request_id,
                    }
                },
                status=500
            )

        duration = time.perf_counter() - start_time
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration:.6f}s"

        logger.info(
            "Request Finished: status=%d duration=%.6fs request_id=%s",
            response.status_code,
            duration,
            request_id
        )
        return response

    def process_view(self, request: HttpRequest, view_func: Callable, view_args: tuple, view_kwargs: dict) -> None:
        """
        Dijalankan tepat sebelum Django memanggil view handler.
        Dapat digunakan untuk validasi skema runtime atau metadata injection.
        """
        request.view_name = f"{view_func.__module__}.{view_func.__name__}"
        return None
```

#### `views.py`
```python
import logging
from django.http import HttpRequest, JsonResponse
from django.views import View

logger = logging.getLogger("core.views")

class SystemHealthCheckView(View):
    """
    CBV (Class-Based View) untuk health probe orkestrator (e.g., Kubernetes)
    yang mematuhi kontrak isolasi siklus request-response.
    """
    def get(self, request: HttpRequest) -> JsonResponse:
        logger.debug("Mengeksekusi SystemHealthCheckView.get() untuk request_id=%s", request.request_id)
        
        payload = {
            "status": "healthy",
            "metadata": {
                "request_id": getattr(request, "request_id", "unknown"),
                "view": getattr(request, "view_name", "SystemHealthCheckView"),
            }
        }
        return JsonResponse(payload, status=200)
```

---

### 9. Edge Cases & Defensive Engineering

*   **Payload Streaming & Memory Exhaustion**: Jika klien mengirim payload besar (misal multipart file upload) tanpa batas, membaca `request.body` secara langsung akan memuat seluruh byte ke RAM.
    *   *Defensive Pattern*: Gunakan `request.read()` secara chunked atau serahkan proses upload file ke backend `FileUploadHandler` (`FILE_UPLOAD_HANDLERS`). Jangan pernah memanggil `request.body` jika Anda mengantisipasi payload bertipe non-JSON besar.
*   **Modifikasi Thread-Safety pada Instance Middleware**: Middleware diinisialisasi **satu kali** saat server melakukan boot (`__init__` dieksekusi sekali).
    *   *Defensive Pattern*: Jangan pernah menyimpan request-specific state pada `self` di dalam middleware (misal `self.current_user = request.user`). Pada multi-threaded worker, data pengguna akan bocor antar-request yang berbeda. Semua context harus disimpan di dalam atribut objek `request`.
*   **Broken Pipe pada Client Disconnection**: Klien memutus koneksi sebelum server selesai menulis response stream.
    *   *Defensive Pattern*: Tangkap `ClientDisconnected` atau `socket.error` saat mengembalikan streaming responses menggunakan `StreamingHttpResponse`.

```python
# Contoh pertahanan mutasi state ilegal di middleware
class InsecureStatefulMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.client_ip = None  # BAHAYA: State bersama lintas thread!

    def __call__(self, request):
        self.client_ip = request.META.get("REMOTE_ADDR") # RACE CONDITION!
        return self.get_response(request)

class SecureStatelessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # BENAR: Simpan secara eksklusif di dalam objek request
        request.client_ip = request.META.get("REMOTE_ADDR")
        return self.get_response(request)
```

---

### 10. Performance & Optimization Heuristics
1.  **Middleware Pruning**: Evaluasi setiap middleware di `settings.MIDDLEWARE`. Rantai middleware dieksekusi pada *setiap request* yang masuk, termasuk request aset statis jika tidak dipisahkan oleh reverse proxy. Membuang middleware yang tidak digunakan secara langsung memangkas latensi dasar (*overhead footprint*).
2.  **Order of Resolution in `ROOT_URLCONF`**: `URLResolver` melakukan linear scan $O(N)$ terhadap pola regex/path dari urutan teratas ke terbawah.
    *   *Heuristik*: Letakkan rute API dengan frekuensi panggilan tertinggi (high-throughput endpoints) di bagian paling atas berkas `urls.py`. Kelompokkan rute menggunakan `include()` untuk membagi search tree secara logis.
3.  **Hindari Evaluasi ORM Eager di Middleware**: Jangan mengeksekusi query database (`request.user.profile`) di dalam middleware masuk kecuali benar-benar esensial untuk otorisasi global. Manfaatkan `SimpleLazyObject` agar query hanya terjadi bila atribut tersebut diakses oleh view.

---

### 11. Anti-Patterns & Pitfalls

#### Anti-Pattern 1: Bisnis Logika di Template
*Salah (Melanggar MVT Separation of Concerns):*
```html
<!-- template.html -->
{% for order in user.order_set.all %}
    {% if order.calculate_tax > 50000 and order.status == 'COMPLETED' %}
        <p>{{ order.id }} Membutuhkan Audit</p>
    {% endif %}
{% endfor %}
```
*Benar:*
```python
# views.py / models.py
orders_requiring_audit = user.orders.filter(
    status='COMPLETED'
).filter_high_tax(threshold=50000)

# template.html
{% for order in orders_requiring_audit %}
    <p>{{ order.id }} Membutuhkan Audit</p>
{% endfor %}
```

#### Anti-Pattern 2: Short-circuiting Middleware Tanpa Mengembalikan HttpResponse
*Salah:*
```python
class BrokenAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.headers.get("Authorization"):
            # Salah: Tidak mengembalikan response apapun (None)
            print("Unauthorized request!")
            return
        return self.get_response(request)
```
*Benar:*
```python
class RobustAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.headers.get("Authorization"):
            # Mengembalikan response eksplisit secara deterministik
            return HttpResponse("Unauthorized", status=401)
        return self.get_response(request)
```

---

### 12. Operational Runbook & Debugging

#### Triage Siklus Request Gagal:
1.  **Validasi Routing**: Jalankan django-extensions shell untuk memvalidasi apakah path terpetakan dengan benar:
    ```bash
    python manage.py show_urls
    ```
2.  **Trace Pipeline via Debug Toolbar / Logging**: Konfigurasikan file logging handler pada root level untuk menangkap alur request:
    ```python
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "console": {"class": "logging.StreamHandler"},
        },
        "loggers": {
            "django.request": {
                "handlers": ["console"],
                "level": "DEBUG",
                "propagate": False,
            },
        },
    }
    ```
3.  **Investigasi Middleware Stack**: Cetak daftar urutan middleware aktual yang berjalan pada instance:
    ```python
    python manage.py shell -c "from django.conf import settings; print('\n'.join(settings.MIDDLEWARE))"
    ```

---

### 13. Security Considerations
*   **SecurityMiddleware & Clickjacking**: Harus diletakkan di puncak `MIDDLEWARE` array untuk memastikan header proteksi seperti `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, dan HTTP Strict Transport Security (HSTS) disuntikkan bahkan saat view di bawahnya mengalami crash.
*   **CSRF Middleware Lifecycle**: `django.middleware.csrf.CsrfViewMiddleware` memvalidasi token pada fase `process_view`. Mematikan middleware ini secara global membuka aplikasi pada serangan *Cross-Site Request Forgery*. Jika bypass diperlukan untuk specific webhook, gunakan decorator `@csrf_exempt` secara granular, jangan menghapus dari pipeline global.
*   **Host Header Injection**: `CommonMiddleware` memvalidasi header `Host` terhadap `ALLOWED_HOSTS`. Jika `ALLOWED_HOSTS = ["*"]` diaktifkan di production, aplikasi rentan terhadap poison password-reset emails dan cache poisoning.

---

### 14. Comparative Trade-offs

| Fitur / Arsitektur | Django (MVT Built-in) | FastAPI (Routing + DI) | Flask (Microframework) |
| :--- | :--- | :--- | :--- |
| **Request Handling** | WSGI / ASGI Berlapis Middleware | Native ASGI Pipeline | WSGI Stack (Werkzeug) |
| **Routing Model** | Centralized Tree Scanning (`urls.py`) | Decentralized Decorator Matching | Decentralized Decorator Matching |
| **Separation Style** | MVT (Strict separation template/logic) | API-Centric (No native view templates) | MVC Bebas (Fleksibel tanpa struktur baku) |
| **Lifecycle Overhead** | Menengah ke Tinggi (Fitur lengkap out-of-the-box) | Sangat Rendah (Asynchronous event-loop) | Sangat Rendah (Hanya mengeksekusi ekstensi terpilih) |
| **Security Defaults** | *Secure by default* (CSRF, XSS protection active) | Manual via dependensi dan schema pydantic | Bergantung pada ekstensi eksternal pengguna |

---

### 15. Verification & Testing Strategy
Pengujian arsitektur siklus request-response harus memvalidasi integritas eksekusi middleware dan penanganan HTTP response menggunakan `RequestFactory` (unit testing terisolasi) dan `Client` (integrasi penuh end-to-end).

```python
# tests/test_lifecycle.py
from django.test import TestCase, RequestFactory
from django.http import HttpResponse
from middleware import ProductionRequestLifecycleMiddleware

class MiddlewareLifecycleTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_production_lifecycle_middleware_injects_headers(self):
        # 1. Arrange: Buat dummy response callable
        def dummy_get_response(request):
            return HttpResponse("OK", status=200)

        middleware = ProductionRequestLifecycleMiddleware(dummy_get_response)
        request = self.factory.get("/test-endpoint/")

        # 2. Act: Eksekusi middleware
        response = middleware(request)

        # 3. Assert: Validasi mutasi state dan header kontrak
        self.assertEqual(response.status_code, 200)
        self.assertTrue("X-Request-ID" in response.headers)
        self.assertTrue("X-Response-Time" in response.headers)
        self.assertIsNotNone(request.request_id)

    def test_production_lifecycle_middleware_handles_exception(self):
        # Arrange: Buat callable yang memicu unhandled exception
        def crashing_get_response(request):
            raise ValueError("Koneksi eksternal terputus secara mendadak.")

        middleware = ProductionRequestLifecycleMiddleware(crashing_get_response)
        request = self.factory.get("/crash-endpoint/")

        # Act: Middleware menangkap exception dan mengembalikan HTTP 500 JSON
        response = middleware(request)

        # Assert: Verifikasi format error response graceful
        self.assertEqual(response.status_code, 500)
        self.assertIn("INTERNAL_SERVER_ERROR", response.content.decode("utf-8"))
```

---

### 16. Production Migration / Adoption Vector
Jika Anda memigrasikan sistem monolitik berbasis function-based view legacy ke standardisasi arsitektural yang strict:
1.  **Fase 1 (Observabilitas)**: Suntikkan middleware telemetri request lifecycle secara non-intrusif di lingkungan staging untuk mengukur baseline latency profile.
2.  **Fase 2 (Normalisasi Exception)**: Standarisasi respons error JSON global di middleware terluar tanpa mengubah logika internal view lama.
3.  **Fase 3 (Zero-Downtime Deployment)**: Saat menambahkan middleware baru yang memodifikasi parsing header, deploy menggunakan canary deployment atau feature flag berbasis environment variables untuk memastikan kompatibilitas client API legacy sebelum pengalihan trafik 100%.

---

### 17. Real-World Case Study
**Insiden**: Sebuah platform e-commerce berbasis Django mengalami lonjakan latensi P99 dari 120ms menjadi 4500ms saat kampanye Flash Sale, memicu *cascading failure* ke seluruh thread pool web server.

**Analisis Akar Masalah (Root Cause)**:
Developer menambahkan middleware otentikasi kustom untuk membaca sesi pelanggan:
```python
# KODE BERMASALAH
class BadSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Setiap request memanggil query sinkron ke tabel user_session
        user_id = request.COOKIES.get("session_id")
        request.custom_session = UserSession.objects.get(pk=user_id) # BLOCKING DB QUERY DI SETIAP REQUEST!
        return self.get_response(request)
```
Middleware ini dieksekusi secara membabi-buta, bahkan untuk request aset statis dan health check endpoint orchestrator, menghabiskan seluruh connection pool database PostgreSQL.

**Resolusi Arsitektur**:
1.  Mengubah loading objek menjadi lazy loading via `django.utils.functional.SimpleLazyObject`.
2.  Menambahkan filter bypass pada path sistemik.
```python
# KODE PERBAIKAN (Production Patch)
from django.utils.functional import SimpleLazyObject

class OptimizedSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(("/static/", "/healthz/")):
            return self.get_response(request)

        def get_user_session():
            session_id = request.COOKIES.get("session_id")
            if not session_id:
                return None
            return UserSession.objects.filter(pk=session_id).first()

        # Database hit HANYA terjadi jika view mengakses request.custom_session
        request.custom_session = SimpleLazyObject(get_user_session)
        return self.get_response(request)
```
*Hasil*: Latensi P99 pulih kembali ke normal (95ms), beban connection pool database menurun 70%.

---

### 18. Ergonomic Tooling & Ecosystem
*   **Django Debug Toolbar**: Menampilkan dekonstruksi waktu eksekusi setiap tahapan request lifecycle, query SQL yang dijalankan, dan middleware chain via browser overlay.
*   **`django-extensions`**: Menyediakan perintah manajemen seperti `show_urls` untuk audit routing tree resolusi secara visual di CLI.
*   **Silk**: Profiler open-source untuk Django yang mencegat HTTP request dan response secara persisten di database internal guna profiling performa mendalam.
*   **Linters (`flake8-django`, `ruff`)**: Memvalidasi kesesuaian arsitektural kode terhadap standar konvensi Django secara statis.

---

### 19. Future-Proofing & Evolution
*   **Asynchronous Lifecycle (ASGI Transition)**: Django secara aktif bertransisi dari synchronous-only framework ke dual-engine (Sync/Async). Sejak Django 3.1+, method middleware dapat mengimplementasikan `async def __call__(self, request)` untuk mendukung concurrency non-blocking via ASGI (`django.core.handlers.asgi.ASGIHandler`).
*   **Decoupled View Logic**: Pola MVT klasik berevolusi menjadi API-driven backend (Django REST Framework / Django Ninja) di mana lapisan *Template* digantikan oleh arsitektur *Headless* (React, Vue, mobile apps) yang memanfaatkan JSON serialization lifecycle.

---

### 20. Synthesis & Takeaways
1.  **MVT bukanlah MVC Biasa**: Pada Django, View adalah *Controller*, dan Template adalah representasi visual murni (*View*). Jangan mencemari template dengan komputasi atau query bisnis.
2.  **Siklus Bersifat Reversibel**: Middleware bekerja dengan mekanisme simetris masuk-keluar (*Onion Architecture*). Kode sebelum `get_response` berjalan secara top-down, sedangkan kode setelah `get_response` berjalan secara bottom-up.
3.  **Hormati State Boundaries**: Instance middleware hidup sepanjang lifecycle web process server. Jangan menyimpan context request pada atribut instance middleware; gunakan objek `request` yang terisolasi secara per-request.

#### Pertanyaan Evaluasi Mandiri:
*   Jika sebuah middleware memanggil `return HttpResponse()` pada tahapan masuk sebelum `get_response(request)`, apa yang terjadi pada middleware di bawahnya dan view callable yang bersangkutan?
*   Mengapa operasi blocking I/O pada middleware kustom dianggap anti-pattern yang berbahaya bagi throughput WSGI worker?
*   Bagaimana mekanisme `SimpleLazyObject` mengoptimalkan alokasi memori dan koneksi database dalam siklus request Django?