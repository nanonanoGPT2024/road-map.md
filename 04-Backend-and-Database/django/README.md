# Kurikulum Enterprise: Django Production Engineering

Selamat datang di repositori kurikulum resmi **Django Production Engineering** berbasis standar kompetensi industri roadmap.sh. Kurikulum ini dirancang untuk mentransformasi rekayasawan perangkat lunak dari tingkat pemula/menengah menjadi arsitek aplikasi enterprise yang mampu merancang, membangun, mengoptimasi, dan mengoperasikan sistem berskala masif berbasis Python dan Django Framework.

---

## 1. Course Overview & Mindset

### Filosofi Kurikulum
Django menganut filosofi *"The web framework for perfectionists with deadlines"* dan prinsip *"Batteries-Included"*. Namun, dalam konteks arsitektur modern berskala enterprise, filosofi ini harus diimbangi dengan pemahaman mendalam tentang abstraksi internal:
- **Eksplisit di atas Implisit:** Memahami siklus hidup internal request-response, metaprogramming di balik Model, dan mekanisme kompilasi SQL oleh Object-Relational Mapping (ORM).
- **Zero-Accidental Complexity:** Menghindari anti-pattern seperti *N+1 queries*, *memory bloat*, *race conditions*, dan *tightly-coupled monoliths*.
- **Production-Ready by Design:** Keamanan (OWASP), konkurensi (ASGI, Celery), caching terdistribusi, serta skalabilitas basis data bukan merupakan pemikiran susulan (*afterthought*), melainkan fondasi sejak hari pertama.

### Arsitektur Mental: Model-Template-View (MTV)
Meskipun industri sering menggunakan istilah Model-View-Controller (MVC), Django secara spesifik mengimplementasikan arsitektur **Model-Template-View (MTV)**:
```
Client Request ---> Web Server (Nginx) ---> WSGI/ASGI (Gunicorn/Uvicorn)
                                                     │
                                                     ▼
                                          Django Middleware Stack
                                                     │
                                                     ▼
                                              URL Dispatcher
                                                     │
                                                     ▼
                                                View / ViewSet
                                                │            │
                         ┌──────────────────────┘            └──────────────────────┐
                         ▼                                                          ▼
                   Model / ORM                                                Template Engine
                         │                                                    (atau Serializer API)
                         ▼                                                          │
                 Database (PostgreSQL)                                              │
                         │                                                          │
                         └───────────────────────► Context ◄────────────────────────┘
                                                     │
                                                     ▼
Client Response <───────────────────────── HTTP Response (JSON/HTML)
```

### Profil Lulusan
Setelah menyelesaikan kurikulum ini, peserta diharapkan mampu:
- Menguasai perancangan skema relasional kompleks dengan Django ORM serta teknik mitigasi query bottleneck secara deterministik.
- Membangun RESTful API kelas enterprise menggunakan Django REST Framework (DRF) lengkap dengan otentikasi stateless, throttling, dan dokumentasi OpenAPI otomatis.
- Mengimplementasikan pemrosesan data asinkron (*distributed task queue*) menggunakan Celery dan Redis serta protokol real-time menggunakan Django Channels.
- Mengamankan dan merilis aplikasi Django ke infrastruktur cloud/container menggunakan Docker, Kubernetes, Nginx, CI/CD pipeline, dan observability stack (Prometheus/Grafana/Sentry).

---

## 2. Learning Roadmap

```
Django Production Engineering
│
├── [BAB 01] Fondasi Arsitektur Django & Ekosistem MTV
├── [BAB 02] Data Modeling Engine & Skema Database Tingkat Lanjut
├── [BAB 03] QuerySet Mastery & Database Performance Optimization
├── [BAB 04] View Layer, URL Routing, & Server-Side Rendering Engine
├── [BAB 05] Forms Processing, Data Validation Pipeline, & Formsets
├── [BAB 06] Autentikasi, Otorisasi, & Manajemen Sesi Enterprise
├── [BAB 07] RESTful API Engineering dengan Django REST Framework (DRF)
├── [BAB 08] Asynchronous Django, Distributed Tasks, & Caching
├── [BAB 09] Testing Strategy, Security Hardening, & Static Analysis
└── [BAB 10] Kontainerisasi, High Availability, & Production Deployment
```

---

## 3. Navigasi Detail Kurikulum

### [BAB 01: Fondasi Arsitektur Django & Ekosistem MTV](./01-fondasi-arsitektur-django/README.md)
Membedah arsitektur internal Django, siklus hidup request-response WSGI/ASGI, struktur modular monolith, dan manajemen konfigurasi enterprise berbasis Twelve-Factor App.
- [Modul 01.1: Request-Response Lifecycle & Middleware Pipeline](./01-fondasi-arsitektur-django/01.1-request-response-lifecycle.md)
  *Eksekusi handler WSGI/ASGI, middleware resolution order, hook exceptions, dan manipulasi objek HttpRequest/HttpResponse.*
- [Modul 01.2: Struktur Proyek Modular & Dekomposisi App](./01-fondasi-arsitektur-django/01.2-struktur-proyek-modular.md)
  *Prinsip Single Responsibility pada Django Apps, coupling vs cohesion, reusable apps, dan isolasi domain logic.*
- [Modul 01.3: Konfigurasi Dinamis 12-Factor & Dependency Management](./01-fondasi-arsitektur-django/01.3-konfigurasi-12-factor.md)
  *Manajemen environment variables (`django-environ`), split settings (base/local/prod), dan dependency tooling modern menggunakan Poetry/uv.*

### [BAB 02: Data Modeling Engine & Skema Database Tingkat Lanjut](./02-data-modeling-engine/README.md)
Eksplorasi mendalam perancangan skema relasional, meta programming Django Models, migrasi atomik, integritas data, dan database constraints tingkat lanjut.
- [Modul 02.1: Model Field Typings, Relational Mapping, & Meta Options](./02-data-modeling-engine/02.1-field-typings-relational-mapping.md)
  *Karakteristik storage fields, relasi ForeignKey, OneToOne, ManyToMany (through models), dan konfigurasi kelas Meta.*
- [Modul 02.2: Database Constraints, Indexes, & Data Integrity](./02-data-modeling-engine/02.2-constraints-dan-indexes.md)
  *Penerapan `CheckConstraint`, `UniqueConstraint`, partial index, composite index, dan GinIndex untuk PostgreSQL.*
- [Modul 02.3: Migrations Engine Internals & Zero-Downtime Migration Strategy](./02-data-modeling-engine/02.3-migrations-engine-internals.md)
  *Cara kerja migration graph, penanganan konflik migrasi, custom data migrations, migrasi atomik, dan strategi zero-downtime deployment.*

### [BAB 03: QuerySet Mastery & Database Performance Optimization](./03-queryset-mastery/README.md)
Menguasai Django ORM hingga ke level query SQL yang dihasilkan. Mengeliminasi bottleneck performa, N+1 queries, dan alokasi memori berlebih.
- [Modul 03.1: QuerySet Anatomy, Lazy Evaluation, & Execution Caching](./03-queryset-mastery/03.1-queryset-anatomy-and-caching.md)
  *Siklus evaluasi QuerySet, iterator pattern, memory footprint, slicing, dan mekanisme ORM internal caching.*
- [Modul 03.2: Eager Loading: select_related vs prefetch_related Deep Dive](./03-queryset-mastery/03.2-eager-loading-deep-dive.md)
  *SQL JOIN vs separate queries, manipulasi `Prefetch` object, nested prefetching, dan eliminasi total masalah N+1.*
- [Modul 03.3: Aggregations, Annotations, Expressions, & Window Functions](./03-queryset-mastery/03.3-aggregations-annotations-expressions.md)
  *Penggunaan objek `F()`, `Q()`, Subquery, Exists, database conditional expressions (`Case`, `When`), serta Window Functions.*

### [BAB 04: View Layer, URL Routing, & Server-Side Rendering Engine](./04-view-layer-dan-ssr/README.md)
Mendalami URL dispatcher, perbandingan fungsional antara Class-Based Views (CBVs) dan Function-Based Views (FBVs), serta Django Template Engine.
- [Modul 04.1: URL Dispatching & Path Converters](./04-view-layer-dan-ssr/04.1-url-dispatching-converters.md)
  *Regex URL patterns, custom path converters, reverse resolution, dan routing namespaces.*
- [Modul 04.2: Class-Based Views Hierarchy, Mixins, & Lifecycle](./04-view-layer-dan-ssr/04.2-cbv-hierarchy-dan-mixins.md)
  *MRO (Method Resolution Order), Generic CBVs (`ListView`, `DetailView`, `CreateView`), dan arsitektur Custom Mixins.*
- [Modul 04.3: Django Template Engine, Custom Tags, Filters, & XSS Mitigation](./04-view-layer-dan-ssr/04.3-template-engine-dan-security.md)
  *Template inheritance, context processors, pembuatan custom template tags & filters, serta mitigasi vulnerability auto-escaping XSS.*

### [BAB 05: Forms Processing, Data Validation Pipeline, & Formsets](./05-forms-validation-formsets/README.md)
Manajemen state formulir, sanitasi input untrusted, pipeline validasi berjenjang, dan pemrosesan data tabular/kompleks.
- [Modul 05.1: Form Lifecycle & Multi-stage Validation Pipeline](./05-forms-validation-formsets/05.1-form-validation-pipeline.md)
  *Tahapan `to_python()`, `validate()`, `run_validators()`, metode `clean_<field>()`, dan cross-field validation di `clean()`.*
- [Modul 05.2: ModelForms, Dynamic Field Manipulation, & Widget Customization](./05-forms-validation-formsets/05.2-modelforms-dan-widgets.md)
  *Ekstraksi skema otomatis dari model, override queryset dinamis pada form runtime, dan styling widget rendering.*
- [Modul 05.3: Formsets, Inline Formsets, & Secure Multi-file Uploads](./05-forms-validation-formsets/05.3-formsets-dan-file-uploads.md)
  *Pengelolaan relasi master-detail via `inlineformset_factory`, memory storage backend, chunks processing, dan sanitasi payload file.*

### [BAB 06: Autentikasi, Otorisasi, & Manajemen Sesi Enterprise](./06-autentikasi-dan-otorisasi/README.md)
Arsitektur keamanan identitas, perluasan model pengguna (*Custom User Model*), RBAC (Role-Based Access Control), dan perlindungan session hijack.
- [Modul 06.1: Custom User Model: AbstractUser vs AbstractBaseUser](./06-autentikasi-dan-otorisasi/06.1-custom-user-model.md)
  *Strategi decoupling model user sejak bootstrap awal, migration traps, dan implementasi identifier kustom (e.g. Email / UUID).*
- [Modul 06.2: Permission Engines, Groups, & Object-Level Permissions](./06-autentikasi-dan-otorisasi/06.2-permissions-dan-rbac.md)
  *Custom permission flags, Django Groups, auth backends custom, dan integrasi object-level permissions (e.g., `django-guardian`).*
- [Modul 06.3: Session Architecture, Cookie Security, & CSRF Internals](./06-autentikasi-dan-otorisasi/06.3-session-dan-csrf-internals.md)
  *Penyimpanan sesi berbasis DB/Cache, rotasi ID sesi, flags cookie (`HttpOnly`, `SameSite`, `Secure`), dan mekanisme proteksi anti-CSRF token.*

### [BAB 07: RESTful API Engineering dengan Django REST Framework (DRF)](./07-django-rest-framework/README.md)
Membangun web API berperforma tinggi dengan standar HTTP spesifikasi ketat, serialisasi performan, otentikasi token/JWT, dan rate limiting.
- [Modul 07.1: Serializers Architecture, Validation, & Nested Relations](./07-django-rest-framework/07.1-serializers-deep-dive.md)
  *Perbedaan Serializer vs ModelSerializer, nested representation, writable nested serializers, dan mitigasi serialisasi lambat.*
- [Modul 07.2: API Views, ViewSets, & Dynamic Content Negotiation](./07-django-rest-framework/07.2-viewsets-dan-routers.md)
  *Implementasi GenericAPIView, ModelViewSet, action decorators, custom Routers, dan Content Negotiation (JSON/CSV/XML).*
- [Modul 07.3: Stateless Authentication (JWT), Throttling, & API Versioning](./07-django-rest-framework/07.3-jwt-throttling-versioning.md)
  *Implementasi `djangorestframework-simplejwt`, custom throttle rates, isolasi scope per-user, dan skema API Versioning.*

### [BAB 08: Asynchronous Django, Distributed Tasks, & Caching](./08-async-tasks-dan-caching/README.md)
Mendukung konkurensi modern dengan integrasi worker terdistribusi menggunakan Celery, event-driven I/O melalui ASGI/Channels, dan caching berlapis.
- [Modul 08.1: Distributed Task Queue Architecture dengan Celery & Redis](./08-async-tasks-dan-caching/08.1-celery-redis-task-queue.md)
  *Konfigurasi broker Celery, idempotent task design, retries dengan exponential backoff, dead-letter queues, dan Celery Beat.*
- [Modul 08.2: Django Cache Framework & Invalidation Patterns](./08-async-tasks-dan-caching/08.2-django-cache-framework.md)
  *Redis cache backend, per-site/per-view/template-fragment caching, low-level cache API, dan penanganan Cache Stampede.*
- [Modul 08.3: Asynchronous Django (ASGI) & WebSockets via Django Channels](./08-async-tasks-dan-caching/08.3-asgi-django-channels.md)
  *Async views (`async def`), ASGI interface, Django Channels architecture, WebSocket consumers, dan Redis channel layers.*

### [BAB 09: Testing Strategy, Security Hardening, & Static Analysis](./09-testing-dan-security-hardening/README.md)
Menjamin reliabilitas kode melalui pengujian komprehensif serta proteksi sistemik terhadap vektor serangan siber standar OWASP Top 10.
- [Modul 09.1: Testing Pipeline: Pytest-Django, Model Factories, & Mocking](./09-testing-dan-security-hardening/09.1-testing-pipeline-pytest.md)
  *Unit testing vs integration testing, fixtures, `factory_boy`, `faker`, mocking downstream services, dan pemantauan code coverage.*
- [Modul 09.2: OWASP Top 10 Defense & Django Security Middleware Audit](./09-testing-dan-security-hardening/09.2-owasp-security-audit.md)
  *Mitigasi SQL Injection, XSS, Clickjacking, Host Header attacks, Content Security Policy (CSP), dan evaluasi perintah `python manage.py check --deploy`.*
- [Modul 09.3: Static Typing & Linter Enforcement (Mypy, Ruff)](./09-testing-dan-security-hardening/09.3-static-typing-dan-linting.md)
  *Penerapan type annotations dengan `django-stubs`, static analysis menggunakan Ruff, dan pre-commit git hooks enforcement.*

### [BAB 10: Kontainerisasi, High Availability, & Production Deployment](./10-deployment-dan-observability/README.md)
Mengoperasikan Django pada level infrastruktur produksi dengan container orchestration, reverse proxy, zero-downtime static assets, dan observability stack.
- [Modul 10.1: Production Dockerization & Multi-Stage Builds](./10-deployment-dan-observability/10.1-docker-multi-stage-build.md)
  *Multi-stage Dockerfile yang aman (non-root execution), image size optimization, dan orchestration via Docker Compose.*
- [Modul 10.2: WSGI/ASGI Production Tuning, Nginx, & Static Asset Engine](./10-deployment-dan-observability/10.2-production-server-tuning.md)
  *Tuning worker model Gunicorn/Uvicorn, Nginx reverse proxy buffering/caching, dan penanganan static files menggunakan WhiteNoise atau AWS S3.*
- [Modul 10.3: Telemetry, Application Observability, & Centralized Logging](./10-deployment-dan-observability/10.3-observability-dan-monitoring.md)
  *Structured JSON logging, profiling via APM, integrasi Sentry untuk exception capture, dan Prometheus metrics exposure untuk traffic analysis.*

---

## 4. Spesifikasi Capstone Project Enterprise

### Judul Proyek
**"OmniCore: Scalable Multi-Tenant Enterprise B2B SaaS Order Management & Subscription Engine"**

### Gambaran Umum
Proyek akhir (Capstone) ini mengintegrasikan seluruh materi Bab 01 hingga Bab 10 dalam sebuah sistem riil berskala komersial. Peserta dituntut untuk membangun sebuah platform backend B2B SaaS yang mengelola multi-tenant isolation, pemrosesan pesanan bervolume tinggi, penagihan recurring langganan, dan pembaruan inventaris secara real-time.

### Persyaratan Arsitektur & Fungsional
1. **Multi-Tenancy & Data Isolation:**
   - Implementasi schema-based atau row-level tenant isolation dengan validasi identitas otomatis di layer ORM middleware.
   - Tidak diperkenankan terjadi kebocoran data (*data leakage*) antar-organisasi/perusahaan penyewa.

2. **Core Transaction Engine & Concurrency:**
   - Alur checkout pesanan yang tahan terhadap *race condition* (menggunakan `select_for_update` dengan context database transaction atomik).
   - Validasi ketersediaan stok inventaris secara real-time dengan status lock timeout.

3. **High-Performance Querying & Search:**
   - Seluruh endpoint analitik dan pencarian produk wajib bebas dari masalah query N+1 (diverifikasi via query logging/assertion test).
   - Indeks database komposit dan full-text search PostgreSQL pada katalog produk enterprise.

4. **Distributed Async Processing:**
   - Integrasi webhook provider eksternal (misal: Stripe/Midtrans) diproses secara asinkron menggunakan worker Celery dengan *idempotency keys*.
   - Ekspor laporan akuntansi (PDF/CSV) berjalan di background worker, dengan progress real-time yang disiarkan ke client melalui WebSockets (Django Channels).

5. **Security, Observability, & Resiliency:**
   - 100% lulus audit `check --deploy` dengan skor rating A+ pada header keamanan (CSP, HSTS, X-Content-Type-Options).
   - Rate limiting ketat pada endpoint otentikasi dan checkout API.
   - Sentry error tracking aktif, disertai exposure metrik aplikasi untuk Prometheus.

### Tech Stack Capstone
| Komponen | Teknologi |
| :--- | :--- |
| **Framework Utama** | Python 3.12+ / Django 5.x / Django REST Framework |
| **Database** | PostgreSQL 16+ (Connection Pooling via PgBouncer) |
| **Caching & Message Broker** | Redis 7+ |
| **Async & Realtime Worker** | Celery 5.x + Django Channels (daphne / uvicorn) |
| **Server WSGI / ASGI** | Gunicorn (Workers: sync/gevent) + Uvicorn |
| **Reverse Proxy & Web Server**| Nginx (HTTP/2, SSL Termination, Gzip/Brotli) |
| **Testing & Quality** | Pytest-django, Factory-Boy, Coverage (min. 85%), Ruff, Mypy |
| **Infrastruktur & Ops** | Docker Multi-stage, Docker Compose, Sentry, Prometheus/Grafana |

### Kriteria Kelulusan Code Review
- Seluruh kode harus lolos pemeriksaan static analysis (Ruff) dan type check (Mypy) tanpa warning/error.
- Cakupan unit & integration test minimal mencapai **85% code coverage**.
- Bebas dari celah keamanan kritis berdasarkan pemindaian keamanan static (Bandit).
- Dokumentasi API komprehensif yang dihasilkan otomatis melalui OpenAPI/Swagger (drf-spectacular).