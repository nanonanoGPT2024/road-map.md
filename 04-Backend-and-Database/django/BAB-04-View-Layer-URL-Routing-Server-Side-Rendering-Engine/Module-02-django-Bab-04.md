# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 04: View Layer, URL Routing, & Server-Side Rendering Engine**  
**Kategori: 04-Backend-and-Database (Django Enterprise Track)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis dan Membedah Internal URL Dispatcher & View Engine**: Menguasai siklus hidup internal resolusi URL melalui `RegexURLResolver`, semantik closure `as_view()`, serta evaluasi C3 Linearization (MRO) pada Class-Based Views (CBVs) kompleks.
2. **Merancang Pipeline Asinkron Berkinerja Tinggi**: Mengimplementasikan `async def` views secara aman di bawah stack ASGI, memitigasi thread contention dan DB connection pooling leakage menggunakan primitif `asgiref.sync.sync_to_async`.
3. **Mengoptimalkan Streaming & Data Pipeline Layer**: Mengimplementasikan `StreamingHttpResponse` dan chunked iterator generation untuk data throughput besar (CSV/NDJSON/PDF) dengan footprint memori $O(1)$.
4. **Mengembangkan Ekstensi SSR Tingkat Lanjut**: Membangun custom template tags berbasis Abstract Syntax Tree (`Node`, `NodeList`, token parser) dengan fragment caching terisolasi, serta mengintegrasikan Jinja2 engine untuk throughput render ekstrem.
5. **Menerapkan Pola Routing Skala Enterprise**: Merancang custom path converters terenkripsi/tervalidasi, nested routing dinamis multi-tenant, dan optimasi reverse-lookup caching.

---

## 2. Prerequisite

Untuk menyerap materi ini secara maksimal, Anda wajib menguasai:
- **Python Lanjutan**: Model Objek Python, Metaclass, Descriptors, Method Resolution Order (C3 Linearization algorithm), dan `asyncio` event loop primitives.
- **Protokol Jaringan & Web Server**: Arsitektur WSGI vs ASGI, HTTP/1.1 Chunked Transfer Encoding vs HTTP/2 multiplexing, status code RFC 9110.
- **Django Core**: Request-Response Lifecycle dasar, ORM QuerySet lazy evaluation, Database connection handling, dan Django Middleware chain mechanics.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1. Internal URL Resolver: Kompilasi Regex & Tree Traversal

URL dispatcher Django tidak mengevaluasi routing secara flat/linier pada setiap request. Sebaliknya, routing diorganisir sebagai pohon resolusi rekursif (`URLResolver` nodes dan `URLPattern` leaves).

```
                 Root URLconf (URLResolver)
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
   "api/v1/" (URLResolver)            "web/" (URLResolver)
            │                                 │
     ┌──────┴──────┐                   ┌──────┴──────┐
     ▼             ▼                   ▼             ▼
"orders/"      "users/"           "login/"       "reports/"
(URLPattern)  (URLPattern)       (URLPattern)   (URLPattern)
```

1. **Inisialisasi & Caching**: Saat aplikasi Django boot melalui WSGI/ASGI handler, `django.urls.resolvers.get_resolver()` memuat modul root URLconf. Resolusi ekspresi reguler (baik via `path()` maupun `re_path()`) dikompilasi ke objek `re.Pattern` Python dan di-cache secara internal menggunakan `@functools.lru_cache`.
2. **Pattern Matching Lifecycle**:
   - `URLResolver.resolve(path)` menerima sub-string URI yang dinormalisasi.
   - Resolver mengiterasi `self.url_patterns`. Jika sebuah pattern adalah instance `URLResolver` (hasil dari `include()`), resolver memotong prefix yang cocok (`path[len(match):]`) dan secara rekursif memanggil `.resolve()` pada resolver turunan tersebut.
   - Jika kecocokan ditemukan pada instance `URLPattern`, resolver mengembalikan objek `ResolverMatch(func, args, kwargs, url_name, app_names, namespaces, route)`.
3. **Custom Path Converters**: Kelas converter meregistrasikan ekspresi reguler mentah via modul `django.urls.converters.register_converter()`. Converter memiliki dua metode siklus hidup:
   - `to_python(self, value)`: Mentransformasi token URI string menjadi tipe data Python konkret. Melempar `ValueError` jika validasi domain-level gagal (memicu resolver untuk melanjutkan evaluasi rute berikutnya).
   - `to_url(self, value)`: Digunakan oleh subsistem `reverse()` untuk memvalidasi dan mengonversi tipe Python kembali ke representasi path URI yang valid.

### 3.2. Class-Based Views (CBV): `as_view()` Closure & C3 Linearization

Sifat deklaratif CBV dicapai melalui abstraksi functional wrapper. Django View Layer pada level kernel HTTP *hanya* menerima callable dengan signature `view_func(request, *args, **kwargs)`.

```python
# Inti abstraksi as_view() (Konseptual Kernel Django)
@classonlymethod
def as_view(cls, **initkwargs):
    for key in initkwargs:
        if key in cls.http_method_names:
            raise TypeError(...)
        if not hasattr(cls, key):
            raise TypeError(...)

    def view(request, *args, **kwargs):
        self = cls(**initkwargs)
        self.setup(request, *args, **kwargs)
        if not hasattr(self, "request"):
            raise AttributeError("setup() must be called...")
        return self.dispatch(request, *args, **kwargs)

    view.view_class = cls
    view.view_initkwargs = initkwargs
    return update_wrapper(view, cls, updated=())
```

- **Thread-Safety via Instansiasi**: Setiap kali HTTP request masuk, closure `view()` mengeksekusi instansiasi kelas (`self = cls(**initkwargs)`). Hal ini menjamin bahwa mutasi state pada `self` terisolasi per-request dan mencegah *race condition* antar request concurrent.
- **Dispatching**: Method `dispatch()` melakukan validasi apakah method HTTP (dalam huruf kecil: `get`, `post`, `put`, `delete`, dll.) didefinisikan dalam `cls.http_method_names` dan diimplementasikan pada instance. Jika tidak diizinkan, dikembalikan response `HttpResponseNotAllowed`.
- **MRO (Method Resolution Order)**: Menggunakan algoritma C3 Linearization. Saat menggabungkan mixin, Mixin harus selalu diletakkan di sisi **kiri** dari class dasar generic view (`class MyView(AuditMixin, TenantMixin, View):`). Kegagalan menyusun hierarki MRO secara benar menyebabkan method `dispatch()`, `get_context_data()`, atau hooks lifecycle lainnya tidak memicu pemanggilan `super()` secara deterministik.

### 3.3. Asynchronous Views: ASGI, Event Loop & Thread Boundaries

Django 3.1+ memperkenalkan kapabilitas native asynchronous views:

```python
async def my_async_view(request):
    data = await fetch_remote_http_service()
    return JsonResponse(data)
```

```
[ASGI Server (Uvicorn/Daphne)]
        │
        ▼ (Async Event Loop Thread)
[Async Middleware Chain]
        │
        ├── View is async: Dieksekusi langsung pada Event Loop Thread
        │
        └── View is sync: Django membungkusnya via sync_to_async 
                          (Didelegasikan ke ThreadPoolExecutor)
```

- **Eksekusi Native**: Di bawah server ASGI (misal Uvicorn), jika view berupa coroutine function (`asyncio.iscoroutinefunction(view) == True`), view dieksekusi langsung di dalam loop event utama thread worker ASGI.
- **Hazard Sinkronisasi ORM**: Django ORM secara default adalah synchronous-blocking I/O. Memanggil atribut lazy QuerySet (seperti `[obj.name for obj in Model.objects.filter(...)]`) di dalam async view akan memicu exception `django.core.exceptions.SynchronousOnlyOperation`.
- **Eksekusi Concurrency Terisolasi**: Kode sinkronus harus dibungkus dengan primitif `asgiref.sync.sync_to_async(func, thread_sensitive=True)`. Opsi `thread_sensitive=True` memastikan kode tersebut dieksekusi di thread context yang sama dengan thread sub-sistem utama Django (penting untuk isolasi koneksi basis data SQLite atau transaksi DB yang mengandalkan thread-local variables).

### 3.4. Django Template Engine (DTE) Internals: AST & Compilation Phase

Django Template Engine memproses template dalam dua fase komputasi:

```
[Raw Template String]
         │
         ▼ (Lexer)
  [Token Stream]  (TOKEN_TEXT, TOKEN_VAR, TOKEN_BLOCK, TOKEN_COMMENT)
         │
         ▼ (Parser)
 [NodeList (AST)] (TextNode, VariableNode, IfNode, CustomNode)
         │
         ▼ (Render Context)
[Rendered String Output]
```

1. **Lexical Analysis (`Lexer`)**: String mentah template dipecah menjadi stream `Token`. Delimiter seperti `{% %}`, `{{ }}`, dan `{# #}` diidentifikasi sebagai token types: `TOKEN_BLOCK`, `TOKEN_VAR`, dan `TOKEN_COMMENT`.
2. **Parsing & Abstract Syntax Tree (`Parser`)**: `Parser` membaca token stream dan memetakan tag ke fungsi kompilasi tag (`@register.tag`). Fungsi kompilasi ini bertanggung jawab membaca parameter token dan mengembalikan instance subclass `django.template.Node`.
3. **Execution (`NodeList.render(context)`)**: Komputasi render mengiterasi pohon nodes secara rekursif. Context bertindak seperti stack dictionary bertingkat (`django.template.Context`). Nilai diresolusi menggunakan nested lookup traversal (attribute lookup $\to$ dictionary key lookup $\to$ index lookup).
4. **Caching Subsystem (`Cached Loader`)**: `django.template.loaders.cached.Loader` menyimpan instance AST `Template` di memori proses worker. Ketika aktif, template *hanya diparsing dan dikompilasi satu kali*; rendering request berikutnya hanya mengeksekusi pohon AST terhadap context baru, memangkas CPU time hingga >80%.

---

## 4. Why & What

| Dimensi | Pendekatan Monolitik / Naif | Arsitektur Lanjutan (Enterprise) | Keuntungan Bisnis & Rekayasa |
| :--- | :--- | :--- | :--- |
| **URL Dispatching** | Hardcoded regex flat pada satu modul `urls.py`. Konversi manual via runtime casting di dalam view (`int(request.GET['id'])`). | Pohon resolver modular, custom bidirectionally-validated converters, dynamic multi-tenant prefix isolation. | Kegagalan parsing input divalidasi sebelum menyentuh View layer; URL decoupling mempermudah refactoring domain mikrolit. |
| **View Architecture** | Functional Views duplikatif atau Fat CBVs dengan multiple inheritance acak. | Mixin composition deterministik dengan strict MRO compliance, lifecycle isolation hooks. | DRY code, kemudahan unit testing terisolasi per behavior (Mixin), audit tracking seragam di tingkat kernel view. |
| **Concurrency / I/O** | 100% blocking sync views. Panggilan API pihak ketiga memblokir worker thread WSGI. | Async views (`async def`) native terintegrasi dengan HTTP client async (`httpx`), isolasi DB calls via `sync_to_async`. | Peningkatan throughput concurrency per instance server hingga 10x pada operasi I/O bound tanpa thread exhaustion. |
| **Output Buffering** | Seluruh dataset (misal: 100.000 records export) ditarik ke RAM, dirender ke string, baru di-dispatch ke HTTP client. | `StreamingHttpResponse` menggunakan generator ter-chunk dan DB server-side cursors. | Footprint memori worker konstan ($O(1)$) berapapun volume data; eliminasi risiko crash OOM (Out Of Memory). |
| **Template Engine** | Pure sync standard loader, render-blocking tags, evaluasi sub-queries langsung di template context. | `cached.Loader`, custom Nodes AST-compiled dengan fragment cache tagging, integrasi Jinja2 pada route traffic tinggi. | Mengurangi TTFB (Time to First Byte) secara drastis, meminimalkan CPU cycle pada server SSR rendering. |

---

## 5. How: Workflow Detail

Diagram state-machine berikut mendeskripsikan secara presisi jalur resolusi HTTP request internal dari ingress hingga egress melalui view and rendering pipeline:

```
[Inbound HTTP/2 or HTTP/1.1 Request]
                  │
                  ▼
         [ASGI/WSGI Handler]
                  │
                  ▼
         [Security Middleware]
                  │
                  ▼
        [Base URLResolver] 
                  │
      [Traverse Node Tree / Match Pattern]
                  │
         ├── Tidak Cocok ───────────────► [Raise Http404]
         │
         ▼ Cocok
[Execute Custom Path Converter .to_python()]
                  │
         ├── Exception (ValueError) ────► [Lanjut Evaluasi Rute Berikutnya]
         │
         ▼ Berhasil
   [Instantiate ResolverMatch]
                  │
                  ▼
      [Execute View Middleware Chain]
                  │
                  ▼
        [Execute View Target]
                  │
         ┌────────┴────────┐
         │                 │
         ▼ (Sync CBV)      ▼ (Async View)
   [Call as_view()]    [Evaluate Coroutine]
         │                 │
   [setup() hooks]         │
         │                 ├── [Async External I/O (httpx)]
   [dispatch() MRO]        │
         │                 └── [sync_to_async(ORM Query)]
   [HTTP Method Handler]   │
         │                 ▼
         └────────┬────────┘
                  │
                  ▼
       [Data Render Strategy]
                  │
         ┌────────┴──────────────────────────┐
         │                                   │
         ▼ (Streaming Dynamic Data)          ▼ (Server-Side Render Engine)
  [Instantiate StreamingHttpResponse]  [Load AST Template (cached.Loader)]
         │                                   │
  [Iterate chunk via cursor]           [Context Processor Injection]
         │                                   │
         │                             [AST NodeList.render(context)]
         │                                   │
         │                             [Return standard HttpResponse]
         │                                   │
         └────────────────┬──────────────────┘
                          │
                          ▼
            [Execute Response Middleware]
                          │
                          ▼
             [Flush to Network Socket]
```

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem Logistik Paket (URL Resolver, CBV, & Streaming)

Bayangkan sebuah pusat logistik multinasional:
1. **URL Resolver = Sistem Pemilah Kode Pos Otomatis**:
   Surat masuk diperiksa label alamatnya. Resolver membaca kode pos digit demi digit (hierarki resolver). `Path Converter` adalah mesin timbang presisi yang memastikan paket tidak mengandung material ilegal dan mengubah label mentah menjadi barcode terstruktur sebelum paket diarahkan ke ban berjalan.
2. **CBV & MRO = Perakitan Jalur Modular**:
   Setiap stasiun pemrosesan paket (View) dirakit dari komponen modular (Mixins). Aturan C3 Linearization adalah manual SOP mutlak yang menentukan modul mana yang memeriksa paket terlebih dahulu: verifikasi keamanan (AuthMixin) harus selalu sebelum inspeksi konten (DataMixin).
3. **StreamingHttpResponse = Pipa Konveyor Berkelanjutan**:
   Bukannya menunggu seluruh 1.000 kontainer ditumpuk di gudang hingga penuh (yang bisa meruntuhkan lantai gudang / OOM), sistem membuka katup ban berjalan kontinu: begitu satu kontainer siap, langsung didorong keluar ke truk logistik.

```
+-----------------------------------------------------------------------------------+
|                            DJANGO URL & VIEW PIPELINE                             |
+-----------------------------------------------------------------------------------+
                                          
[Incoming Path: /tenant-acme/metrics/stream/]
                      |
                      v
    +------------------------------------+
    | Resolver: TenantConverter          |  --> Validasi slug & Query DB Tenant
    | to_python('tenant-acme')           |  --> Menghasilkan Instance: Tenant(id=42)
    +------------------------------------+
                      |
                      v
    +------------------------------------+
    | CBV Inheritance Pipeline (MRO)     |
    |                                    |
    | 1. [AuditLogMixin.dispatch]        |  --> Catat access time & actor
    | 2. [TenantScopeMixin.dispatch]     |  --> Ikat thread context ke Tenant(42)
    | 3. [AsyncStreamView.dispatch]      |  --> Eksekusi business handler
    +------------------------------------+
                      |
                      v
    +------------------------------------+
    | Yield Generation Phase             |
    | Chunk 01: [Records 001 - 100]      |  ==> Pushed to Client (Transfer-Encoding: chunked)
    | Chunk 02: [Records 101 - 200]      |  ==> Pushed to Client
    | Chunk 03: [Records 201 - 300]      |  ==> Pushed to Client
    +------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Custom Path Converter Terenkripsi & Validasi Kuat

Kasus: Mengamankan resource identifier publik menggunakan Hashids (agar sequential primary keys integer tidak diekspos ke publik) langsung pada routing layer.

```python
# app_core/converters.py
from hashids import Hashids
from django.conf import settings

# Inisialisasi hashids salt dari project settings
hashids_instance = Hashids(
    salt=getattr(settings, "HASHID_SALT", "enterprise-core-salt"),
    min_length=8
)

class HashIdConverter:
    regex = r"[a-zA-Z0-9]{8,}"

    def to_python(self, value: str) -> int:
        decoded = hashids_instance.decode(value)
        if not decoded:
            # Melempar ValueError menandakan kegagalan matching converter;
            # Django akan lanjut mengevaluasi rute alternatif atau raise 404
            raise ValueError(f"Payload ID '{value}' tidak dapat didekode.")
        return decoded[0]

    def to_url(self, value: int) -> str:
        return hashids_instance.encode(value)
```

```python
# app_core/urls.py
from django.urls import path, register_converter
from .converters import HashIdConverter
from .views import TransactionDetailView

register_converter(HashIdConverter, "hashid")

app_name = "transactions"

urlpatterns = [
    # URI: /transactions/x9B2aK8w/
    path(
        "<hashid:transaction_id>/",
        TransactionDetailView.as_view(),
        name="detail"
    ),
]
```

### 7.2. Practical Example: Production-Grade Async Streaming View & Custom AST Template Engine Node

Kasus: Modul real-time analytics auditing. View layer streaming data berkapasitas masif dalam format NDJSON (Newline Delimited JSON) langsung dari async cursor, sedangkan template rendering menggunakan high-performance custom AST Node dengan dynamic micro-caching.

#### Komponen 1: Async Streaming View dengan Bounded Memory Consumption

```python
# analytics/views.py
import json
from typing import AsyncGenerator
from django.http import StreamingHttpResponse, HttpRequest, HttpResponseBadRequest
from django.views import View
from django.utils.decorators import classonlymethod
from asgiref.sync import sync_to_async
from .models import SecurityAuditLog

class AsyncSecurityLogStreamView(View):
    """
    Menyediakan data log sekuritas ter-chunk melalui transfer chunked HTTP
    menggunakan Django Async View engine. Mengeliminasi pemakaian buffer memori
    berskala besar.
    """
    
    # Memastikan view ini hanya dapat dipanggil via runner ASGI
    @classonlymethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        view._is_coroutine = True
        return view

    async def get(self, request: HttpRequest, *args, **kwargs) -> StreamingHttpResponse:
        severity_filter = request.GET.get("severity", "HIGH")
        if severity_filter not in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            return HttpResponseBadRequest("Parameter severity tidak valid.")

        response = StreamingHttpResponse(
            streaming_content=self.stream_log_payloads(severity_filter),
            content_type="application/x-ndjson"
        )
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["X-Accel-Buffering"] = "no"  # Disable proxy buffering di NGINX
        return response

    async def stream_log_payloads(self, severity: str) -> AsyncGenerator[bytes, None]:
        """
        Query database menggunakan Django ORM asinkron iterator untuk membatasi 
        pengambilan ke memory buffer (Server-Side Cursor pattern).
        """
        # Yield metadata awal stream
        yield json.dumps({"stream_status": "START", "severity": severity}).encode("utf-8") + b"\n"

        # Menggunakan ORM Async Iterable (.iterator() mengeksekusi server cursor di driver Postgres)
        logs_queryset = (
            SecurityAuditLog.objects
            .filter(severity=severity)
            .order_by("-timestamp")
            .values("id", "timestamp", "actor_id", "ip_address", "event_payload")
            .iterator(chunk_size=1000)
        )

        async for log_entry in logs_queryset:
            # Transformasikan timestamp objek ke format ISO string
            log_entry["timestamp"] = log_entry["timestamp"].isoformat()
            encoded_row = json.dumps(log_entry).encode("utf-8") + b"\n"
            yield encoded_row

        # Yield metadata penutupan stream
        yield json.dumps({"stream_status": "END"}).encode("utf-8") + b"\n"
```

#### Komponen 2: Custom AST Node Template Tag dengan Multi-Tier Fragment Cache

```python
# analytics/templatetags/custom_cache_tags.py
from django import template
from django.core.cache import caches
from django.template.base import (
    Node,
    NodeList,
    Parser,
    Token,
    TemplateSyntaxError,
    Variable,
)

register = template.Library()

class EnterpriseCacheNode(Node):
    def __init__(self, nodelist: NodeList, expire_time_var: Variable, fragment_name: str, vary_on_vars: list[Variable]):
        self.nodelist = nodelist
        self.expire_time_var = expire_time_var
        self.fragment_name = fragment_name
        self.vary_on_vars = vary_on_vars

    def render(self, context: template.Context) -> str:
        try:
            expire_time = self.expire_time_var.resolve(context)
            resolved_expire = int(expire_time)
        except (template.VariableDoesNotExist, ValueError, TypeError) as err:
            raise TemplateSyntaxError(f"Error parsing cache ttl variable: {err}")

        # Bangun dynamic composite key
        resolved_vary = []
        for var in self.vary_on_vars:
            try:
                resolved_vary.append(str(var.resolve(context)))
            except template.VariableDoesNotExist:
                resolved_vary.append("None")

        cache_key = f"template_node:{self.fragment_name}:{':'.join(resolved_vary)}"
        
        # Eksekusi Cache Backend Layer
        cache_backend = caches["template_fragments"]
        cached_content = cache_backend.get(cache_key)

        if cached_content is not None:
            return cached_content

        # Render AST jika cache miss
        rendered_content = self.nodelist.render(context)
        cache_backend.set(cache_key, rendered_content, timeout=resolved_expire)
        return rendered_content

@register.tag("enterprise_cache")
def do_enterprise_cache(parser: Parser, token: Token) -> EnterpriseCacheNode:
    """
    Sintaks: 
    {% enterprise_cache ttl 'fragment_name' var1 var2 %}
        ... HTML Block to compile ...
    {% end_enterprise_cache %}
    """
    tokens = token.split_contents()
    if len(tokens) < 3:
        raise TemplateSyntaxError("tag 'enterprise_cache' membutuhkan argumen: ttl, fragment_name, dan optional vary vars")

    expire_time_var = Variable(tokens[1])
    fragment_name = tokens[2].strip("'\"")
    vary_on_vars = [Variable(v) for v in tokens[3:]]

    # Parse stream hingga penutup
    nodelist = parser.parse(("end_enterprise_cache",))
    parser.delete_first_token()  # Flush tag end_enterprise_cache

    return EnterpriseCacheNode(nodelist, expire_time_var, fragment_name, vary_on_vars)
```

---

## 8. Real World Case Study: Arsitektur Export Pelaporan Finansial Multi-Tenant

### 8.1. Konteks Masalah
Sebuah platform fintech B2B SaaS memproses audit transaksi bulanan untuk institusi perbankan.
- **Beban Data**: 1 tenant dapat memiliki 2.500.000 record transaksi per bulan (~1.2 GB payload CSV mentah).
- **Infrastruktur Eksisting**: Menggunakan standard Class-Based Views (`View`) dan synchronous CSV generation via `HttpResponse`.
- **Dampak Kegagalan**: Terjadi crash OOM (Out-of-Memory) masif pada worker Kubernetes, API Gateway (Kong) mengalami HTTP 504 Gateway Timeout karena worker WSGI memblokir execution thread selama 45 detik, serta koneksi database pool habis seketika.

### 8.2. Solusi Arsitektural Terintegrasi
1. **Dynamic Tenant Router**: Menggunakan Custom Path Converter yang membedah identitas tenant melalui dynamic subdomain context dan meregistrasikan runtime database schema isolation.
2. **Backpressure-Aware Streaming View Layer**: Mengganti response sync dengan `StreamingHttpResponse` yang mengonsumsi PostgreSQL Server-Side Cursor via Django ORM iterator chunks.
3. **Chunked Memory Buffer Wrapper**: Mengimplementasikan thread-safe pseudo-buffer file object yang mengonversi tuple database mentah menjadi serialized CSV buffer tanpa menyimpan list objek di RAM.

### 8.3. Implementasi Kode Produksi

```python
# finance/export_engine.py
import csv
from typing import Generator
from django.views import View
from django.http import StreamingHttpResponse, Http404
from django.db import connection, transaction
from django.utils.timezone import now
from .models import LedgerTransaction

class EchoPseudoBuffer:
    """
    Objek perantara yang mengimplementasikan interface 'write' 
    untuk csv.writer, tetapi langsung mengembalikan nilai string
    secara langsung (echoing) alih-alih melakukan akumulasi data di buffer memori.
    """
    def write(self, value: str) -> str:
        return value

class EnterpriseLedgerExportView(View):
    CHUNK_SIZE = 5000

    def get(self, request, tenant_slug: str, fiscal_year: int):
        # 1. Validasi tenant isolation context
        if not hasattr(request, "tenant") or request.tenant.slug != tenant_slug:
            raise Http404("Tenant context tidak valid.")

        filename = f"ledger_{tenant_slug}_{fiscal_year}_{now().strftime('%Y%m%d%H%M%S')}.csv"
        
        # 2. Definisikan Generator Data Pipeline
        csv_generator = self.generate_ledger_csv(request.tenant.id, fiscal_year)

        # 3. Setup Streaming Response dengan Content-Disposition yang tepat
        response = StreamingHttpResponse(
            streaming_content=csv_generator,
            content_type="text/csv"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Cache-Control"] = "no-store"
        return response

    def generate_ledger_csv(self, tenant_id: int, year: int) -> Generator[str, None, None]:
        pseudo_buffer = EchoPseudoBuffer()
        writer = csv.writer(pseudo_buffer, dialect="excel")

        # Emit CSV Header
        yield writer.writerow([
            "Transaction ID",
            "Posting Date",
            "Account Number",
            "Debit Amount",
            "Credit Amount",
            "Currency",
            "Reference Memo"
        ])

        # Eksekusi Query menggunakan Server-Side Cursor Postgres
        # Membungkus pembacaan di atomic transaction wajib untuk Postgres named cursors
        with transaction.atomic():
            queryset = (
                LedgerTransaction.objects
                .filter(tenant_id=tenant_id, posting_date__year=year)
                .order_by("posting_date", "id")
                .values_list(
                    "reference_uuid",
                    "posting_date",
                    "account__account_number",
                    "debit",
                    "credit",
                    "currency",
                    "memo"
                )
                .iterator(chunk_size=self.CHUNK_SIZE)
            )

            for record in queryset:
                # Transform data jika dibutuhkan dan stream per row
                yield writer.writerow(record)
```

### 8.4. Metrik Keberhasilan Arsitektur

| Metrik | Sebelum Optimasi | Pasca Arsitektur Streaming | Dampak Sistem |
| :--- | :--- | :--- | :--- |
| **Worker Peak RAM** | 2.1 GB (OOM Crash di pod 1.5GB) | **48 MB (Stabil)** | 97.7% Reduksi Beban RAM |
| **Time to First Byte (TTFB)**| 42.5 Detik | **180 Milidetik** | Eliminasi Gateway Timeout (504) |
| **Concurrent Export Support**| Max 2 requests per instance | **> 120 requests per node** | 60x Kapasitas Skalabilitas |

---

## 9. Trade-offs

Ketika merancang arsitektur View dan Rendering di level enterprise, setiap keputusan memiliki konsekuensi teknis:

```
                  [Keputusan Arsitektur View & Template]
                                    │
       ┌────────────────────────────┴────────────────────────────┐
       ▼                                                         ▼
[Async Def Views]                                     [Streaming Responses]
  ├── (+) Concurrency I/O Ekstrem                       ├── (+) RAM Statis O(1)
  ├── (-) Sync ORM DB Overhead                          ├── (-) Middleware Modifikasi Header Gagal
  └── (-) Debugging Execution Trace Sulit               └── (-) DB Connection Terkunci Lama
```

| Desain Arsitektural | Keuntungan Utama | Kerugian / Risiko Tersembunyi | Kapan Digunakan | Kapan Dihindari |
| :--- | :--- | :--- | :--- | :--- |
| **Async Views (`async def`)** | Membuka I/O non-blocking native. Menangani ribuan koneksi idle/SSE/long-polling per pod. | Memerlukan dependensi driver database async atau wrapping `sync_to_async`. Kesalahan wrapping memicu *event loop starvation*. | Aggregator calls ke 3rd-party microservices, Webhooks, SSE. | Aplikasi internal monolitik CRUD sederhana yang 100% operasinya terikat transaksi sync DB. |
| **`StreamingHttpResponse`** | Memori penggunaan konstan ($O(1)$) terlepas dari volume data yang dikirim ke client. | Respon HTTP header dikirim seketika; middleware yang memodifikasi isi response (misal `Content-Length`, GZip, caching) menjadi tidak berfungsi. | File export masif (CSV/Parquet), stream JSON/video, real-time logging. | Response reguler yang membutuhkan validasi payload menyeluruh atau operasi REST standar. |
| **Django Template Engine (DTE)** | Built-in integrasi keamanan (Auto-escaping, CSRF, Django Form parsing, Localization). | AST parsing lambat jika cached loader mati; kapabilitas manipulasi data logic rendah. | Dashboard standar internal enterprise, view monolitik dengan caching terstruktur. | Halaman dengan rendering komputasi tinggi (>10.000 iterasi kompleks per request). |
| **Jinja2 Backend Integration** | Kecepatan render string hingga 10-20x lipat lebih kencang dibanding DTE. Eksekusi Pythonic. | Hilangnya akses native ke custom templatetag library bawaan Django (e.g. `{% static %}`, admin integration). | Micro-frontends, high-frequency report generation, template rendering untuk email batch. | Mengandalkan Django Admin atau ekosistem package template pihak ketiga. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Common Mistakes

#### 1. SynchronousOnlyOperation Exception di Dalam Async View
```python
# KODE SALAH:
async def report_summary(request):
    # CRASH: Memanggil ORM synchronous secara langsung di thread context async!
    users = User.objects.filter(is_active=True)
    count = users.count() # Melempar SynchronousOnlyOperation
    return JsonResponse({"count": count})

# KODE BENAR:
from asgiref.sync import sync_to_async

async def report_summary(request):
    # Bungkus eksekusi sync ORM secara eksplisit
    user_count_func = sync_to_async(lambda: User.objects.filter(is_active=True).count())
    count = await user_count_func()
    return JsonResponse({"count": count})
```

#### 2. C3 Linearization MRO Broken Chain pada Mixins
```python
# KODE SALAH:
class BaseCustomView:
    def dispatch(self, request, *args, **kwargs):
        # Tidak memanggil super().dispatch()
        return HttpResponse("Base")

class LoggingMixin:
    def dispatch(self, request, *args, **kwargs):
        log_access(request)
        return super().dispatch(request, *args, **kwargs)

class BrokenView(BaseCustomView, LoggingMixin, View):
    pass # LoggingMixin tidak akan PERNAH terpanggil karena BaseCustomView memotong rantai MRO!

# KODE BENAR:
class LoggingMixin:
    def dispatch(self, request, *args, **kwargs):
        log_access(request)
        return super().dispatch(request, *args, **kwargs)

class ProperView(LoggingMixin, View): # Mixin diletakkan di sebelah kiri base View
    def get(self, request):
        return HttpResponse("Success")
```

#### 3. Database Connection Exhaustion pada `StreamingHttpResponse`
Membiarkan transaksi DB terbuka sepanjang streaming client mengonsumsi byte data. Jika client mengalami slow connection (network throttling), koneksi database backend akan tertahan sepanjang transfer jaringan berlangsung.
*Solusi*: Tarik data ke generator buffer thread-safe atau lakukan streaming per partisi atomic yang segera merilis koneksi basis data.

### 10.2. Troubleshooting Runbook: View & Template Layer

1. **Investigasi Route Resolution Terjebak / Matching Salah**:
   Gunakan internal Django shell untuk memeriksa rute mana yang sebenarnya memproses URI:
   ```python
   python manage.py shell
   >>> from django.urls import resolve
   >>> match = resolve('/api/v1/customers/10293/')
   >>> print(match.func, match.view_name, match.route, match.kwargs)
   ```
2. **Mendeteksi Template Rendering CPU Spikes**:
   Aktifkan profiling pada loader template untuk mengonfirmasi apakah `cached.Loader` berjalan:
   ```python
   # settings.py
   TEMPLATES = [{
       'BACKEND': 'django.template.backends.django.DjangoTemplates',
       'OPTIONS': {
           'loaders': [
               ('django.template.loaders.cached.Loader', [
                   'django.template.loaders.filesystem.Loader',
                   'django.template.loaders.app_directories.Loader',
               ]),
           ],
       },
   }]
   ```
3. **Memeriksa C3 MRO Hierarchy**:
   Jalankan inspeksi class langsung melalui CLI jika mixin gagal bertindak:
   ```python
   >>> from app.views import MyComplexView
   >>> [cls.__name__ for cls in MyComplexView.mro()]
   ['MyComplexView', 'SecurityAuditMixin', 'TenantContextMixin', 'TemplateView', 'TemplateResponseMixin', 'ContextMixin', 'View', 'object']
   ```

---

## 11. Best Practices (Production Checklist)

### Security Checklist
- [ ] Nonaktifkan `DEBUG = False` di production; verifikasi bahwa generic 500 handler tidak membocorkan local context variables via Traceback.
- [ ] Sanitasi seluruh argument pada Custom Path Converters menggunakan strict RegEx (`^[a-zA-Z0-9_-]+$`) guna memitigasi Injection Attacks sebelum view parsing.
- [ ] Atur security headers terisolasi pada `StreamingHttpResponse` (`X-Content-Type-Options: nosniff`).

### Performance & Concurrency Checklist
- [ ] Konfigurasikan template rendering menggunakan `django.template.loaders.cached.Loader` pada mode production.
- [ ] Jangan pernah mengeksekusi operasi evaluasi ORM N+1 di dalam template tag rendering context. Lakukan `select_related` atau `prefetch_related` di View level.
- [ ] Bila menggunakan `sync_to_async`, tentukan `thread_sensitive=True` untuk operasi interaksi database, dan `thread_sensitive=False` untuk komputasi murni CPU-bound/File I/O disk non-database.

### Maintenance & Observability Checklist
- [ ] Gunakan semantic namespacing di semua `include()` URL declarations: `path('users/', include(('users.urls', 'users'), namespace='users'))`.
- [ ] Terapkan custom logging handler di tingkat `dispatch()` view utama untuk melacak request execution time (TTFB).

---

## 12. Hands-on Practice: Membangun Production Chunked Data Exporter & Custom Compiler

Tujuan: Membangun pipeline hands-on terisolasi di folder project: `hands-on/m02/`.

### Struktur Direktori
```
hands-on/m02/
├── manage.py
├── core_project/
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── export_system/
    ├── __init__.py
    ├── apps.py
    ├── converters.py
    ├── models.py
    ├── templatetags/
    │   ├── __init__.py
    │   └── stream_tags.py
    ├── urls.py
    └── views.py
```

### Langkah 1: Inisialisasi Environment & Base Project
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
python -m venv venv
source venv/bin/activate
pip install django asgiref
django-admin startproject core_project .
python manage.py startapp export_system
```

### Langkah 2: Daftarkan Setting & Inisialisasi Cache
Perbarui file `core_project/settings.py`:
```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'export_system.apps.ExportSystemConfig',
]

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}
```

### Langkah 3: Implementasikan Model Data
Edit file `export_system/models.py`:
```python
from django.db import models

class SystemMetrics(models.Model):
    node_identifier = models.CharField(max_length=64, db_index=True)
    cpu_utilization = models.FloatField()
    memory_utilization = models.FloatField()
    logged_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-logged_at']
```

Jalankan migrasi basis data:
```bash
python manage.py makemigrations export_system
python manage.py migrate
```

### Langkah 4: Buat Custom UUID Path Converter
Edit file `export_system/converters.py`:
```python
import uuid

class StrictNodeIDConverter:
    regex = r"node-[a-f0-9]{8}"

    def to_python(self, value: str) -> str:
        # Format input: node-1234abcd
        token = value.split("-")[1]
        return token.lower()

    def to_url(self, value: str) -> str:
        return f"node-{value}"
```

### Langkah 5: Implementasikan Streaming Controller View
Edit file `export_system/views.py`:
```python
import time
from typing import Generator
from django.views import View
from django.http import StreamingHttpResponse, HttpResponse
from .models import SystemMetrics

class MetricsStreamView(View):
    def get(self, request, node_token: str):
        response = StreamingHttpResponse(
            streaming_content=self.stream_raw_metrics(node_token),
            content_type="text/event-stream"
        )
        response['Cache-Control'] = 'no-cache'
        return response

    def stream_raw_metrics(self, node_token: str) -> Generator[str, None, None]:
        # Emulasi generator SSE (Server-Sent Events)
        for idx in range(1, 6):
            time.sleep(0.5) # Simulasi interval
            payload = f"data: Node: {node_token} | Chunk: {idx} | Status: Processing\n\n"
            yield payload
        yield f"data: Node: {node_token} | Stream Completed.\n\n"
```

### Langkah 6: Registrasi Converter dan Route URLs
Edit file `export_system/urls.py`:
```python
from django.urls import path, register_converter
from .converters import StrictNodeIDConverter
from .views import MetricsStreamView

register_converter(StrictNodeIDConverter, "node_id")

app_name = "exports"

urlpatterns = [
    path("stream/<node_id:node_token>/", MetricsStreamView.as_view(), name="metrics_stream"),
]
```

Daftarkan ke file `core_project/urls.py`:
```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('system/', include('export_system.urls', namespace='system')),
]
```

### Langkah 7: Pengujian Eksekusi Streaming
Jalankan server pengembangan:
```bash
python manage.py runserver 127.0.0.1:8000
```
Buka terminal terpisah dan uji koneksi menggunakan `curl` flag unbuffered:
```bash
curl -N http://127.0.0.1:8000/system/stream/node-12ab34cd/
```
Output akan dialirkan per 0.5 detik secara interaktif tanpa pemutusan buffer response.

---

## 13. Exercise

### Level Easy
**Tugas**: Buat custom path converter dengan nama `YearConverter` yang hanya mencocokkan integer tahun 4 digit antara `1900` hingga `2099`.
- **Constraint**: Jika user mengakses `/archive/1899/`, converter harus memicu penolakan (mengembalikan `ValueError` pada `to_python`) sehingga menghasilkan `404 Not Found`.
- **Lokasi Kode**: `export_system/converters.py`.

### Level Medium
**Tugas**: Implementasikan Mixin bernama `ETagPreconditionMixin` untuk Class-Based View.
- **Mekanisme**:
  - Tangkap atribut `get_last_modified()` dari view turunan.
  - Periksa header incoming request: `If-None-Match`.
  - Jika ETag cocok dengan computed hash, hentikan eksekusi processing view dan langsung kembalikan `HttpResponseNotModified()` (HTTP 304).

### Level Hard
**Tugas**: Rancang Async View `AsyncExternalAggregatorView` yang mengeksekusi 3 HTTP call ke API publik mock secara bersamaan (concurrent) menggunakan library `httpx` (async client), kemudian menggabungkan hasilnya dan me-render template HTML Django melalui engine DTE tanpa memblokir thread context ASGI.
- **Constraint**: Wajib menggunakan `sync_to_async` secara aman saat berinteraksi dengan rendering context template DTE jika template tag mengakses thread database context.

---

## 14. Challenge: Arsitektur Dynamic Tenant Routing & Inverted Engine Loader

Rancang blueprint arsitektur (disertai implementasi kode modul) untuk kebutuhan sistem SaaS berskala global berikut:
1. **Dynamic URL Dispatching**: URL pattern tidak boleh di-hardcode di file teks; sistem harus memuat rute dari database tenant routing table secara runtime saat pertama kali domain tenant baru diinisiasi tanpa merestart pod worker web.
2. **Hybrid SSR Engine**: Sistem harus mendukung dual-engine: jika tenant mengaktifkan flag "Enterprise Ultra", template di-render menggunakan mesin **Jinja2** yang dioptimalkan; sebaliknya, fallback ke **Django Template Engine (DTE)** standar dengan fragment caching.
3. **Graceful Failover**: Bila template loader Jinja2 gagal menemukan file template kustom penyewa, engine harus otomatis fallback melakukan lookup ke default shared-template milik DTE tanpa melempar exception 500.
4. **Zero Buffer Leak**: Pastikan seluruh lifecycle view request isolation tidak membocorkan data tenant satu ke tenant lain akibat re-use memory thread pool worker.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Soal)
1. **Apa tipe callable sebenarnya yang dikembalikan oleh pemanggilan method `MyClassView.as_view()`?**
   - A. Instance dari kelas `MyClassView`
   - B. Fungsi closure lokal Python `view(request, *args, **kwargs)`
   - C. Generator iterator
   - D. Objek WSGI handler mentah

2. **Kapan method `to_python` pada Custom Path Converter dieksekusi oleh Django?**
   - A. Setelah middleware view selesai dijalankan
   - B. Sebelum incoming request diproses oleh middleware manapun
   - C. Pada saat proses URL traversal matching oleh `URLResolver.resolve()`
   - D. Di dalam method `dispatch()` pada CBV

3. **Exception apa yang dilempar Django ORM jika QuerySet synchronous diakses langsung di dalam `async def` view?**
   - A. `RuntimeError`
   - B. `BlockingIOError`
   - C. `SynchronousOnlyOperation`
   - D. `ImproperlyConfigured`

4. **Apa fungsi utama dari `django.template.loaders.cached.Loader`?**
   - A. Menyimpan context database di Redis
   - B. Menyimpan token parser AST hasil kompilasi template di RAM untuk render berulang
   - C. Meng-cache seluruh output string HTML ke browser client
   - D. Mengubah sintaks Django template menjadi Jinja2

5. **Header response apa yang secara otomatis dihapus atau tidak dapat dihitung dengan pasti oleh Django ketika menggunakan `StreamingHttpResponse`?**
   - A. `Content-Type`
   - B. `Content-Length`
   - C. `X-Frame-Options`
   - D. `Set-Cookie`

---

### Bagian 2: Intermediate (5 Soal)
6. **Diberikan hierarki CBV: `class OrderView(MixinA, MixinB, View): pass`. Jika kedua mixin mengimplementasikan method `dispatch()`, urutan eksekusi manakah yang benar sesuai C3 Linearization?**
   - A. `View.dispatch` $\to$ `MixinB.dispatch` $\to$ `MixinA.dispatch`
   - B. `MixinA.dispatch` $\to$ `MixinB.dispatch` $\to$ `View.dispatch`
   - C. Dieksekusi secara paralel di thread terpisah
   - D. `MixinB.dispatch` $\to$ `MixinA.dispatch` $\to$ `View.dispatch`

7. **Mengapa pemanggilan `super().dispatch()` wajib diterapkan pada setiap custom View Mixin?**
   - A. Untuk mengalokasikan memori baru di heap Python
   - B. Untuk memastikan alur resolusi method berlanjut ke class berikutnya dalam rantai MRO
   - C. Agar view dapat diubah menjadi thread async secara dinamis
   - D. Untuk membersihkan CSRF token context

8. **Apa implikasi penggunaan flag `thread_sensitive=True` pada helper `asgiref.sync.sync_to_async`?**
   - A. Kode dieksekusi di random thread dari `ThreadPoolExecutor`
   - B. Kode dieksekusi di main thread/single dedicated context thread yang sama dengan request pipeline Django
   - C. Menjamin operasi synchronous tidak akan pernah melempar Exception
   - D. Mematikan fitur multi-threading pada server web

9. **Kapan sebaiknya kita menolak menggunakan `StreamingHttpResponse` untuk pengiriman file statis atau media?**
   - A. Ketika ukuran file di atas 10 MB
   - B. Selalu; web server tingkat depan (NGINX/Apache/CDN) via `X-Sendfile` atau object storage direct URLs jauh lebih efisien
   - C. Ketika file memiliki format PDF
   - D. Jika memori RAM server tersisa sedikit

10. **Pada kompilasi Custom Template Tag, method `parser.parse()` membaca token stream dan mengembalikan struktur data apa?**
    - A. Dictionary flat berisi raw tokens
    - B. File HTML terkompilasi
    - C. Objek `NodeList` yang memuat representasi AST dari blok template
    - D. Bytecode Python `.pyc`

---

### Bagian 3: Production Case Scenarios (3 Soal)

11. **Skenario 1**: Sebuah tim teknis meluncurkan async view berikut untuk sistem notifikasi instan:
    ```python
    async def push_stream(request):
        async def event_generator():
            while True:
                data = await sync_to_async(get_latest_notification, thread_sensitive=False)()
                if data:
                    yield f"data: {data}\n\n"
                await asyncio.sleep(1)
        return StreamingHttpResponse(event_generator(), content_type="text/event-stream")
    ```
    Setelah dijalankan di server produksi dengan 2.000 concurrent client, koneksi ke PostgreSQL pool macet seketika (*connection pool exhaustion*) dan pod mengalami hang total. Apa akar penyebab arsitekturalnya?
    - A. Server ASGI Uvicorn tidak mendukung protocol SSE.
    - B. Penggunaan `thread_sensitive=False` memicu pembuatan thread acak di pool yang masing-masing membuka dan menggantung koneksi DB independen tanpa mekanisme penutupan yang deterministik.
    - C. `asyncio.sleep(1)` mematikan event loop worker ASGI secara global.
    - D. Parameter `content_type` salah menurut standar RFC.

12. **Skenario 2**: Anda mengonfigurasi `Cached Loader` untuk Django template engine. Tim konten mengubah file template `dashboard_base.html` langsung di server staging tanpa melakukan restart process worker Gunicorn. Dampak apa yang terjadi pada aplikasi?
    - A. Aplikasi melempar `TemplateDoesNotExist` error.
    - B. Perubahan langsung ter-render otomatis dalam waktu 5 detik.
    - C. Aplikasi tetap menyajikan struktur template lama yang tersimpan dalam AST memory cache hingga proses Gunicorn di-restart/reload.
    - D. Memory proses worker langsung mengalami corrupt.

13. **Skenario 3**: Sebuah view mewarisi `TenantContextMixin` dan `RateLimitMixin`. Muncul insiden sekuritas di mana rate limit gagal diaplikasikan pada request tertentu:
    ```python
    class BrokenSecureView(RateLimitMixin, TenantContextMixin, View):
        def dispatch(self, request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseForbidden()
            return super().dispatch(request, *args, **kwargs)
    ```
    Ternyata `RateLimitMixin` melakukan kalkulasi berdasarkan IP pada method `setup()` bukan `dispatch()`. Sementara `TenantContextMixin` mengoverride `setup()` tanpa memanggil `super().setup()`. Bagaimana perbaikan yang tepat?
    - A. Memindahkan seluruh logika rate limiting ke dalam function view biasa.
    - B. Mengubah urutan class inheritance menjadi `(View, RateLimitMixin, TenantContextMixin)`.
    - C. Menambahkan pemanggilan `super().setup(request, *args, **kwargs)` secara disiplin di seluruh implementasi override lifecycle method pada semua Mixin.
    - D. Mengganti Django CBV dengan ExpressJS microservice.

---

### Kunci Jawaban & Rasionalisasi Singkat

1. **B**: `as_view()` membuat closure functional `view()` yang menginstansiasi class per request baru.
2. **C**: `to_python` dipanggil oleh `URLResolver` saat mengevaluasi path URL matching.
3. **C**: ORM guards melempar `SynchronousOnlyOperation` saat pemanggilan blocking terdeteksi pada thread async.
4. **B**: `cached.Loader` menyimpan compiled `NodeList` (AST) di heap memory worker untuk menghindari pembacaan I/O disk dan lexing/parsing ulang.
5. **B**: Karena konten di-stream secara bertahap (chunked), ukuran total data tidak diketahui di awal sehingga header `Content-Length` ditiadakan.
6. **B**: Algoritma C3 Linearization mengevaluasi urutan kiri-ke-kanan: `MixinA` $\to$ `MixinB` $\to$ `View`.
7. **B**: Tanpa `super()`, method matching pada class turunan berikutnya dalam daftar linearisasi MRO akan terputus.
8. **B**: `thread_sensitive=True` memastikan eksekusi diarahkan ke thread konteks Django yang mengelola state penting seperti transactional database connections.
9. **B**: Serving file statis/media via streaming runtime Python menghabiskan computing resources; web server terdepan (NGINX/CDN) jauh lebih efisien menggunakan kernel zero-copy transfer.
10. **C**: Parser mengonversi token stream menjadi `NodeList` (Abstract Syntax Tree / AST).
11. **B**: `thread_sensitive=False` memicu ThreadPool spawn masif; setiap thread mengalokasikan koneksi DB baru ke Postgres hingga pool DB kolaps seketika.
12. **C**: `Cached Loader` menyimpan instance AST di RAM worker proses. Jika worker tidak di-reload, disk update tidak akan dievaluasi ulang.
13. **C**: Aturan dasar MRO Python mewajibkan pemanggilan `super().method()` di setiap tingkatan lifecycle agar rantai eksekusi terdistribusi sempurna ke semua mixin.

---

## 16. Summary

1. **URL Resolution Engine**: Routing Django beroperasi sebagai pohon hierarkis (`URLResolver`). Pemanfaatan *Custom Path Converters* memungkinkan validasi data domain terisolasi langsung di ingress layer URL sebelum request dialirkan ke View logic.
2. **Class-Based Views Mechanics**: CBV membungkus instance terisolasi per-request melalui closure `as_view()`. Kunci perancangan Mixin yang tangguh terletak pada pematuhan algoritma **C3 Linearization (MRO)** dengan selalu memanggil `super()` pada lifecycle hooks (`setup()`, `dispatch()`, `get_context_data()`).
3. **Async View Boundary**: View `async def` berjalan native pada thread loop ASGI. Komunikasi dengan Django ORM synchronous memerlukan boundary safety via `sync_to_async(..., thread_sensitive=True)` guna mencegah runtime blocking dan kebocoran pool koneksi.
4. **Zero-Memory Streaming**: Operasi export masif wajib menerapkan `StreamingHttpResponse` yang dipasangkan dengan server-side database cursors (`.iterator()`). Pola ini mempertahankan kompleksitas footprint memori pada level $O(1)$.
5. **Template Engine AST Compilation**: Optimasi SSR dicapai dengan memahami fase *Lexing* $\to$ *Parsing* $\to$ *Execution*. Mengaktifkan `django.template.loaders.cached.Loader` menghilangkan overhead parsing disk berulang, sementara Custom AST `Node` classes memungkinkan fragment caching yang granular dan performan.