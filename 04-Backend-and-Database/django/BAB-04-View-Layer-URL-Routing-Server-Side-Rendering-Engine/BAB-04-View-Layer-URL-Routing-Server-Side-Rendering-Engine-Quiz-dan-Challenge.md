# BAB-04-View-Layer-URL-Routing-Server-Side-Rendering-Engine: Quiz, Challenge, & Knowledge Check

Uji kompetensi teknis, pemahaman arsitektur request-response lifecycle, URL resolver dispatcher, Class-Based Views (CBV) lifecycle, serta Server-Side Rendering (SSR) Django Template Engine (DTL).

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1.1: Request-Response Lifecycle & View Callable
Jelaskan siklus hidup (*lifecycle*) sebuah HTTP request di Django dari saat payload tiba di WSGI/ASGI handler hingga response dikirimkan kembali ke client. Apa peran `django.core.handlers.wsgi.WSGIHandler`, `URLResolver`, dan callable view object?

<details>
<summary>Jawaban & Pembahasan</summary>

1. **WSGI/ASGI Entry Point:** Request HTTP diterima oleh web server (misal Nginx) dan diteruskan ke worker (Gunicorn/Uvicorn) yang menginisialisasi `WSGIHandler` / `ASGIHandler`.
2. **Request Construction:** Objek `HttpRequest` dibangun dari `environ` dictionary WSGI (berisi HTTP headers, request body stream, method, path, remote IP).
3. **Middleware Chain (Request phase):** Request dilewatkan secara berurutan melalui middleware stack yang dikonfigurasi pada `settings.MIDDLEWARE` (metode `process_request` / interceptor sebelum `get_response`).
4. **URL Resolving:** `WSGIHandler` memanggil resolver utama (`ROOT_URLCONF`). `URLResolver` mencocokkan `request.path_info` terhadap pola regex/path converter. Jika cocok, resolver mengembalikan tuple: `(view_func, args, kwargs)`.
5. **View Execution:** Callable view dipanggil dengan parameter `(request, *args, **kwargs)`. Jika callable adalah CBV (`MyView.as_view()`), method closure `view()` mengeksekusi `dispatch()` untuk me-route request ke handler HTTP method (`get()`, `post()`, dsb.).
6. **Response Generation:** View merender template atau mengembalikan instance `HttpResponse` / `JsonResponse` / `StreamingHttpResponse`.
7. **Middleware Chain (Response phase):** Response melewati middleware stack dalam urutan terbalik (`process_response` / baris setelah `get_response(request)`), menangani gzip compression, CSRF cookie setting, cache header injection.
8. **Transport:** `WSGIHandler` mengonversi `HttpResponse` menjadi status code, headers list, dan iterable byte stream ke WSGI server.
</details>

---

### Soal 1.2: Path Converters vs Regex Routing
Apa perbedaan mendasar antara `django.urls.path` dengan standar path converters (`int`, `str`, `slug`, `uuid`, `path`) dibandingkan `django.urls.re_path`? Kapan Anda wajib menggunakan custom path converter?

<details>
<summary>Jawaban & Pembahasan</summary>

- `path()` menggunakan path converter modular yang secara otomatis memvalidasi format string URL dan melakukan *type-casting* langsung ke tipe data Python (misal: `<int:user_id>` otomatis di-cast menjadi `int` Python, `<uuid:uid>` di-cast menjadi instance `uuid.UUID`).
- `re_path()` menggunakan POSIX regular expression manual dengan named captured groups `(?P<name>pattern)`. Nilai yang diekstrak selalu bertipe `str` mentah dan memerlukan validasi / type-casting manual di dalam view layer.
- **Custom Path Converter** digunakan ketika ada pola URL spesifik domain yang berulang di banyak route dan memerlukan validasi regex sekaligus konversi dua arah (`to_python(value)` saat parsing URL dan `to_url(value)` saat reverse resolution via `reverse()`):
  ```python
  class FourDigitYearConverter:
      regex = r"[0-9]{4}"

      def to_python(self, value):
          return int(value)

      def to_url(self, value):
          return f"{value:04d}"
  ```
</details>

---

### Soal 1.3: Method Resolution Order (MRO) pada CBV Mixin
Bagaimana urutan penulisan inheritance class saat menggabungkan Mixins dengan generic Class-Based Views (misal `LoginRequiredMixin`, `PermissionRequiredMixin`, `UpdateView`), dan mengapa peletakan mixin di posisi paling kiri (*leftmost*) sangat krusial?

<details>
<summary>Jawaban & Pembahasan</summary>

Python menggunakan algoritma **C3 Linearization** untuk menentukan Method Resolution Order (MRO). Pada Django CBV:
```python
class ArticleUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Article
    form_class = ArticleForm
```
- Mixins harus ditempatkan **sebelum** base view (`UpdateView`) dari kiri ke kanan.
- Saat request masuk, `as_view()` memanggil `dispatch()`. Resolusi method mencari implementasi `dispatch()` dari class paling kiri.
- `LoginRequiredMixin.dispatch()` dieksekusi terlebih dahulu untuk memverifikasi autentikasi user. Jika lolos, ia memanggil `super().dispatch(...)` yang mendelegasikan ke `PermissionRequiredMixin.dispatch()`. Jika otorisasi lolos, delegasi berlanjut hingga mencapai `UpdateView.dispatch()` -> `ProcessFormView.post()`.
- Jika `UpdateView` diletakkan di sebelah kiri mixin, `UpdateView.dispatch()` akan dieksekusi duluan tanpa perlindungan middleware autentikasi/izin mixin, menyebabkan kebocoran akses data (vulnerability bypass).
</details>

---

### Soal 1.4: Context Processors Engine
Apa itu `context_processors` dalam konfigurasi `TEMPLATES` Django, kapan ia dieksekusi, dan apa dampak negatifnya terhadap latency jika context processor melakukan query database yang tidak di-cache?

<details>
<summary>Jawaban & Pembahasan</summary>

- **Definisi:** Context processor adalah callable Python yang menerima parameter `request` dan mengembalikan dictionary variabel yang diinjeksi secara global ke dalam context setiap kali `RequestContext` diinisialisasi (misal saat memanggil `render(request, ...)`).
- **Waktu Eksekusi:** Dieksekusi *just-in-time* pada saat rendering template yang menggunakan `RequestContext`.
- **Dampak Latency:** Jika sebuah context processor mengeksekusi query database lambat atau unindexed (misal `SiteConfiguration.objects.get(active=True)` atau menghitung unread notifications `request.user.notifications.filter(read=False).count()`):
  1. Query tersebut akan berjalan di **setiap single view** yang merender HTML, bahkan untuk view statis sederhana.
  2. Menghasilkan beban I/O database berlebih (*N+1 overhead pada layer rendering*).
  3. Mengakibatkan *render blocking*. Best practice: data global dinamis wajib di-cache di Redis atau dievaluasi secara lazy menggunakan helper wrapper.
</details>

---

### Soal 1.5: Template Security: Auto-escaping & Safe Filter
Bagaimana mekanisme Cross-Site Scripting (XSS) prevention bawaan Django Template Engine (DTL), dan apa risiko arsitektural dari penggunaan filter `|safe` atau tag `{% autoescape off %}`?

<details>
<summary>Jawaban & Pembahasan</summary>

- DTL secara default menerapkan **HTML auto-escaping** pada semua output variabel ekspresi `{{ var }}`. Karakter sensitif di-encode: `<` menjadi `&lt;`, `>` menjadi `&gt;`, `&` menjadi `&amp;`, `"` menjadi `&quot;`, `'` menjadi `&#x27;`.
- String yang ditandai aman menggunakan `mark_safe()` atau filter `|safe` membungkus string dalam instance `django.utils.safestring.SafeString`. DTL mempercayai string tersebut dan merendernya mentah tanpa escaping.
- **Risiko:** Jika input user yang belum disanitasi secara ketat (misal Markdown editor / rich text HTML input) dilewatkan langsung ke `|safe`, script berbahaya (`<script>alert(document.cookie)</script>` atau `<img src=x onerror=... />`) akan tereksekusi di browser korban, menyebabkan Session Hijacking atau credential leakage.
</details>

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 2.1: Reverse Resolution & Namespace Isolation
Mengapa penggunaan hardcoded string URL (misal: `action="/products/checkout/"`) dilarang dalam arsitektur Django skala enterprise? Jelaskan cara kerja `app_name` (app namespace) dan `namespace` (instance namespace) pada nested URL patterns.

<details>
<summary>Jawaban & Pembahasan</summary>

- **Anti-pattern Hardcoding:** Mengunci routing ke path absolut. Perubahan struktur URL akan mematahkan link di ratusan template dan view redirects, serta melanggar prinsip *Single Source of Truth* (SSOT).
- **URL Namespaces:**
  1. `app_name`: Mengidentifikasi aplikasi secara logis di file URLconf modul lokal (misal `app_name = "billing"`).
  2. `namespace`: Ditetapkan saat melakukan `include()` di root routing untuk mendukung multi-instansiasi app yang sama:
     ```python
     # urls.py
     path("eu/billing/", include("billing.urls", namespace="billing_eu")),
     path("us/billing/", include("billing.urls", namespace="billing_us")),
     ```
  3. Reverse lookup di template menggunakan `{% url 'billing_eu:invoice-detail' pk=invoice.id %}` atau di Python `reverse('billing_us:invoice-detail', kwargs={'pk': invoice.id})`. Resolver mencari konfigurasi spesifik instance tersebut, memisahkan rute multi-tenant/multi-region tanpa duplikasi view.
</details>

---

### Soal 2.2: Deep-dive View Lifecycle: `get_context_data`, `form_valid`, dan `get_queryset`
Pada `UpdateView`, runutkan urutan eksekusi method berikut ketika HTTP `POST` dikirimkan oleh browser:
`dispatch()`, `get_object()`, `get_form_class()`, `get_form()`, `post()`, `form_valid()`, `form_invalid()`, `get_success_url()`. Kapan `get_context_data()` dipanggil jika form tidak valid?

<details>
<summary>Jawaban & Pembahasan</summary>

Alur eksekusi saat request `POST`:
1. `as_view()` -> memanggil `dispatch(request, *args, **kwargs)`.
2. `dispatch()` memeriksa method HTTP dan memanggil `post(request, *args, **kwargs)`.
3. `post()` memanggil `self.object = self.get_object()` untuk mengambil model instance target dari database berdasarkan slug/pk di URL.
4. `post()` memanggil `get_form_class()`, lalu `get_form()` untuk menginisialisasi form dengan binding `data=request.POST`, `files=request.FILES`, dan `instance=self.object`.
5. Form divalidasi via `form.is_valid()`.
6. **Jika Valid:**
   - `post()` memanggil `form_valid(form)`.
   - `form_valid()` memanggil `form.save()` (menyimpan perubahan instance).
   - Menghitung target URL via `get_success_url()`.
   - Mengembalikan `HttpResponseRedirect(success_url)`.
7. **Jika Invalid:**
   - `post()` memanggil `form_invalid(form)`.
   - `form_invalid()` memanggil `render_to_response(self.get_context_data(form=form))`. Di sinilah `get_context_data()` dieksekusi untuk merender kembali template beserta pesan error form dengan status code HTTP 200.
</details>

---

### Soal 2.3: Atomic Transaction pada `form_valid`
Dalam skenario pembuatan pesanan e-commerce (`OrderCreateView(CreateView)`), proses checkout wajib mengurangi stok barang (`InventoryItem`), membuat record `Order`, dan membuat multiple record `OrderItem`. Bagaimana cara menjamin konsistensi database di layer view?

<details>
<summary>Jawaban & Pembahasan</summary>

Gunakan decorator atau context manager `django.db.transaction.atomic` di dalam method `form_valid()`:

```python
from django.db import transaction
from django.views.generic import CreateView


class OrderCreateView(LoginRequiredMixin, CreateView):
    model = Order
    form_class = OrderForm
    template_name = "orders/order_form.html"

    def form_valid(self, form):
        context = self.get_context_data()
        order_items_formset = context["order_items_formset"]

        if not order_items_formset.is_valid():
            return self.form_invalid(form)

        try:
            with transaction.atomic():
                # 1. Simpan order header
                form.instance.customer = self.request.user
                self.object = form.save()

                # 2. Simpan order items
                order_items_formset.instance = self.object
                items = order_items_formset.save(commit=False)

                for item in items:
                    # 3. Kunci dan potong inventory menggunakan select_for_update
                    inventory = InventoryItem.objects.select_for_update().get(
                        product=item.product
                    )
                    if inventory.stock < item.quantity:
                        raise ValueError(f"Stok tidak cukup untuk {item.product.name}")
                    inventory.stock -= item.quantity
                    inventory.save()
                    item.save()

                order_items_formset.save_m2m()
        except ValueError as err:
            form.add_error(None, str(err))
            return self.form_invalid(form)

        return super().form_valid(form)
```
Jika terjadi kegagalan/exception di salah satu proses, transaksi di-rollback secara utuh tanpa ada order yatim (*orphaned records*).
</details>

---

### Soal 2.4: Template Inheritance vs Inclusion Tags vs Simple Tags
Bandingkan ketiga teknik modularitas template berikut:
1. `{% extends %}` + `{% block %}`
2. `{% include %}`
3. Custom Inclusion Tag (`@register.inclusion_tag`)

Kapan Anda wajib menggunakan custom inclusion tag daripada sekadar `{% include %}`?

<details>
<summary>Jawaban & Pembahasan</summary>

| Mekanisme | Karakteristik Utama | Scope Data / Context | Best Use Case |
| :--- | :--- | :--- | :--- |
| `{% extends %}` & `{% block %}` | Inverted control (Template Inheritance). Base layout mendefinisikan skeleton kerangka aplikasi. | Mewarisi context view induk secara penuh. | Master layout, dashboard frame, multi-column wrapper. |
| `{% include %}` | Merender partial template statis/semi-statis ke posisi pemanggilan saat ini. | Mewarisi context view induk secara penuh (kecuali diproteksi `only`). Tidak dapat query data baru. | Tombol partial, alert banner, nav items sederhana. |
| Custom Inclusion Tag | Menerima parameter, menjalankan logic Python independen, dan merender template komponen khusus. | Memiliki context independen hasil komputasi fungsi Python tag tersebut. | Komponen kompleks mandiri: sidebar cart summary, recent comments widget, dynamic user notifications. |

**Kapan Wajib Menggunakan Inclusion Tag:**
Gunakan inclusion tag ketika komponen visual membutuhkan querying data independen atau komputasi Python tersendiri tanpa harus memaksa setiap View di seluruh proyek memasukkan variabel data tersebut ke dalam `get_context_data()`.
</details>

---

### Soal 2.5: StreamingHttpResponse & Server-Sent Events (SSE)
Kapan seorang Software Architect harus memilih `StreamingHttpResponse` daripada standar `HttpResponse`? Apa implikasinya terhadap WSGI synchronous workers vs ASGI asynchronous workers?

<details>
<summary>Jawaban & Pembahasan</summary>

- **Use Case:**
  1. Mentransfer file berukuran sangat besar (misal ekspor CSV jutaan baris, log audit gigabytes) langsung dari generator chunk tanpa memuat seluruh konten ke RAM.
  2. Implementasi real-time stream seperti Server-Sent Events (SSE) atau LLM token-by-token streaming.
- **Dampak Arsitektural Worker:**
  - **Pada WSGI (Sync):** Satu worker process/thread (misal worker Gunicorn tipe `sync`) akan **terkunci penuh (*blocked*)** sepanjang durasi transmisi streaming client yang lambat (*slowloris effect*). 20 concurrent streaming request dapat melumpuhkan server 20-worker secara total.
  - **Pada ASGI (Async):** Menggunakan `StreamingHttpResponse` dengan asynchronous generator stream (`async for chunk in generator()`) tidak memblokir event loop. Ribuan streaming client dapat dilayani secara non-blocking oleh satu worker ASGI (seperti Uvicorn/Daphne).
</details>

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Skenario)

### Skenario 3.1: Insiden CPU Spike Akibat N+1 Query pada ListView Pagination
**Konteks Masalah:**
Aplikasi portal media berita mengalami lonjakan CPU 100% dan connection pool exhaustion di database PostgreSQL saat traffic mencapai 2.500 req/sec pada halaman `/articles/`.
Kode view eksisting:
```python
# views.py
from django.views.generic import ListView
from .models import Article


class ArticleListView(ListView):
    model = Article
    template_name = "articles/list.html"
    paginate_by = 25
```
Di dalam template `articles/list.html`:
```html
{% for article in object_list %}
  <h2>{{ article.title }}</h2>
  <p>Penulis: {{ article.author.profile.full_name }}</p>
  <p>Kategori: {{ article.category.name }}</p>
  <span>Tags: {% for tag in article.tags.all %}{{ tag.name }}, {% endfor %}</span>
{% endfor %}
```

**Tugas Anda:**
1. Analisis akar masalah query profiling pada kode di atas.
2. Refactor `ArticleListView` menggunakan optimasi ORM di method `get_queryset()`.
3. Jelaskan mengapa optimasi ini drastis memangkas latensi rendering DTL.

<details>
<summary>Solusi & Kode Refactor</summary>

#### 1. Analisis Akar Masalah (N+1 Query Explosion)
Untuk setiap batch halaman berisi 25 artikel:
- 1 query awal untuk mengambil list 25 artikel.
- 25 query untuk `article.author` (Foreign Key).
- 25 query untuk `author.profile` (OneToOne field).
- 25 query untuk `article.category` (Foreign Key).
- 25 query untuk `article.tags.all` (ManyToMany relation).
Total query: $1 + 25 + 25 + 25 + 25 = 101\text{ queries per page render}$. Pada 2.500 req/sec, database menerima lebih dari 250.000 QPS yang mengakibatkan DB exhaustion.

#### 2. Kode Refactor
```python
# views.py
from django.views.generic import ListView
from .models import Article


class ArticleListView(ListView):
    model = Article
    template_name = "articles/list.html"
    paginate_by = 25

    def get_queryset(self):
        return (
            Article.objects.filter(is_published=True)
            .select_related("author__profile", "category")
            .prefetch_related("tags")
            .only(
                "id",
                "title",
                "slug",
                "author__id",
                "author__profile__full_name",
                "category__name",
            )
            .order_by("-published_at")
        )
```

#### 3. Dampak Terhadap DTL Rendering
- `select_related('author__profile', 'category')` melakukan single SQL `INNER/LEFT JOIN` pada query utama (mengeliminasi 75 query ke 0).
- `prefetch_related('tags')` mengeksekusi tepat 1 query tambahan untuk menarik seluruh tags yang berelasi dengan 25 artikel menggunakan SQL `WHERE id IN (...)` di memori Python.
- Total query terpangkas dari **101 queries menjadi 2 queries tetap (O(1) complexity)** per pagination. Latensi template rendering turun drastis karena DTL tidak lagi melakukan I/O round-trip synchronous ke PostgreSQL saat loop variabel dievaluasi.
</details>

---

### Skenario 3.2: Race Condition pada Form Processing & Idempotency Key
**Konteks Masalah:**
Aplikasi pinjaman peer-to-peer (P2P Lending) mendapati anomali saldo pengguna terpotong ganda saat tombol "Bayar Cicilan" diklik berulang kali (*double-clicking*) oleh nasabah dengan koneksi lambat. Request pertama dan kedua masuk ke worker pool Gunicorn yang berbeda dalam selisih 15 milidetik.

Kode eksisting:
```python
class RepaymentView(LoginRequiredMixin, FormView):
    form_class = RepaymentForm
    template_name = "loans/repay.html"

    def form_valid(self, form):
        loan = form.cleaned_data["loan"]
        amount = form.cleaned_data["amount"]
        if self.request.user.wallet.balance >= amount:
            self.request.user.wallet.balance -= amount
            self.request.user.wallet.save()
            loan.record_payment(amount)
            return redirect("loan:success")
        return self.form_invalid(form)
```

**Tugas Anda:**
Rancang arsitektur proteksi di View Layer yang menggabungkan:
1. Idempotency Key token submission verification menggunakan cache/database.
2. Optimistic/Pessimistic locking pada wallet model.

<details>
<summary>Solusi & Kode Refactor</summary>

#### Arsitektur Solusi:
1. **Idempotency Token:** Inject unique token (UUIDv4) ke form context via hidden input. Saat form di-submit, View melakukan atomic check-and-set token ke Redis dengan TTL pendek (misal 60 detik). Jika token sudah berstatus `PROCESSING` atau `COMPLETED`, request duplikat langsung di-reject.
2. **Database Locking:** Terapkan `select_for_update()` pada row wallet nasabah di dalam blok transaksi atomic untuk mencegah race condition lintas worker threads.

```python
import uuid
from django.core.cache import cache
from django.db import transaction
from django.shortcuts import redirect
from django.views.generic import FormView
from .forms import RepaymentForm
from .models import Wallet


class RepaymentView(LoginRequiredMixin, FormView):
    form_class = RepaymentForm
    template_name = "loans/repay.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Generate idempotency token baru saat form dirender pertama kali
        context["idempotency_token"] = uuid.uuid4().hex
        return context

    def post(self, request, *args, **kwargs):
        token = request.POST.get("idempotency_token")
        if not token:
            return redirect("loan:error_invalid_request")

        # Atomic acquire lock via Redis Cache (Key, Value, timeout)
        lock_acquired = cache.add(
            f"idemp:{token}", "LOCKED", timeout=60
        )  # NX: set if not exists
        if not lock_acquired:
            # Request duplikat terdeteksi
            return redirect("loan:payment_already_in_progress")

        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        amount = form.cleaned_data["amount"]
        loan_id = form.cleaned_data["loan_id"]

        try:
            with transaction.atomic():
                # Lock row wallet pada level DB (SELECT ... FOR UPDATE)
                wallet = Wallet.objects.select_for_update().get(user=self.request.user)
                if wallet.balance < amount:
                    form.add_error(None, "Saldo tidak mencukupi.")
                    return self.form_invalid(form)

                loan = Loan.objects.select_for_update().get(
                    id=loan_id, borrower=self.request.user
                )

                # Eksekusi mutasi
                wallet.balance -= amount
                wallet.save(update_fields=["balance"])
                loan.record_payment(amount)

                # Tandai idempotency token sukses permanen
                token = self.request.POST.get("idempotency_token")
                cache.set(f"idemp:{token}", "COMPLETED", timeout=3600)

            return redirect("loan:success")
        except Exception as exc:
            # Lepas lock jika crash
            token = self.request.POST.get("idempotency_token")
            cache.delete(f"idemp:{token}")
            form.add_error(None, f"Transaksi gagal: {str(exc)}")
            return self.form_invalid(form)
```
</details>

---

### Skenario 3.3: SSR Memory Leak pada File Export View
**Konteks Masalah:**
Fitur export data transaksi finansial `/admin/export-transactions/` menghasilkan Out-Of-Memory (OOM) error dan membunuh instance Kubernetes Pod setiap kali finance team mengunduh data bulanan (>1.500.000 baris data).
Kode eksisting memuat seluruh query queryset ke dalam memori Python lalu merender string template DTL ke dalam `HttpResponse`:
```python
def export_csv_view(request):
    transactions = Transaction.objects.all().order_by("-created_at")
    content = render_to_string(
        "reports/transactions.csv", {"transactions": transactions}
    )
    response = HttpResponse(content, content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="all_transactions.csv"'
    return response
```

**Tugas Anda:**
Gantikan view tersebut dengan arsitektur asynchronous memory-safe iterator menggunakan `StreamingHttpResponse` dan generator batching (`iterator(chunk_size=...)`).

<details>
<summary>Solusi & Kode Refactor</summary>

#### Masalah Fundamental:
1. `Transaction.objects.all()` memuat jutaan instansiasi model Python ke RAM.
2. `render_to_string` membangun seluruh string CSV gigabytes di dalam RAM sebelum mengirim byte pertama.

#### Solusi Memory-Safe Streaming:
```python
import csv
from django.http import StreamingHttpResponse


class EchoBuffer:
    """Buffer semu yang mengembalikan byte yang baru saja ditulis oleh csv.writer."""

    def write(self, value):
        return value


def stream_transactions_csv_generator():
    pseudo_buffer = EchoBuffer()
    writer = csv.writer(pseudo_buffer)

    # 1. Yield header baris pertama
    yield writer.writerow(
        ["Transaction ID", "User ID", "Amount", "Currency", "Status", "Timestamp"]
    )

    # 2. Gunakan ORM .values_list() agar tidak membuat overhead instance Model
    # dan .iterator(chunk_size=2000) untuk streaming cursor Postgres
    queryset = (
        Transaction.objects.all()
        .order_by("-created_at")
        .values_list("id", "user_id", "amount", "currency", "status", "created_at")
        .iterator(chunk_size=2000)
    )

    for row in queryset:
        yield writer.writerow(row)


def export_csv_view(request):
    if not request.user.is_staff:
        raise PermissionDenied

    response = StreamingHttpResponse(
        stream_transactions_csv_generator(), content_type="text/csv"
    )
    response["Content-Disposition"] = (
        'attachment; filename="transactions_export.csv"'
    )
    response["X-Accel-Buffering"] = "no"  # Disable buffering jika di balik Nginx
    return response
```
Penggunaan memori pod stabil di bawah 50MB berapapun jumlah baris data yang diekspor.
</details>

---

## Bagian 4: Practical Chapter Challenge (1 Tantangan Hands-On)

### Judul Proyek: "Multi-Role SaaS Analytics Engine with Secure CBVs & Dynamic Rendering"

### Deskripsi Skenario
Bangun modular subsystem Django View Layer untuk aplikasi analitik B2B multi-tenant dengan ketentuan berikut:

1. **Role Access Specification:**
   - Role `ADMIN`: Akses penuh ke report builder, delete, dan export data.
   - Role `ANALYST`: Akses baca, create draft, dan update report.
   - Role `VIEWER`: Akses read-only ke published reports.
2. **Arsitektur CBV & URL Routing:**
   - Implementasikan reusable Mixin: `TenantAccessMixin` (memastikan data query selalu terisolasi pada `request.user.tenant`) dan `RoleRequiredMixin` (memeriksa role hierarchy).
   - Buat generic view: `AnalyticsDashboardView(TemplateView)`, `ReportListView(ListView)`, `ReportCreateView(CreateView)`, `ReportUpdateView(UpdateView)`.
3. **Template & SSR Tag Layer:**
   - Buat Custom Inclusion Tag `render_metric_card` yang menerima judul metrik, target model query, dan warna tema (`primary`, `success`, `danger`).
   - Buat Custom Filter `human_readable_currency` yang mengonversi angka mentah `15400000` menjadi format lokal `Rp 15,40 Jt` atau `$ 15.4M`.
4. **Verifikasi Keamanan:**
   - Tidak boleh ada kebocoran data antar tenant (*cross-tenant leakage* via URL slug injection).
   - Form handling wajib CSRF-protected dan bebas dari SQL injection / XSS rendering.

---

### Solusi Referensi Implementasi

#### 1. Mixins Keamanan (`mixins.py`)
```python
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied


class TenantAccessMixin:
    """Menjamin bahwa queryset otomatis terfilter berdasarkan tenant pengguna."""

    def get_queryset(self):
        qs = super().get_queryset()
        if not hasattr(self.request.user, "tenant"):
            raise PermissionDenied("User tidak memiliki asosiasi tenant.")
        return qs.filter(tenant=self.request.user.tenant)


class RoleRequiredMixin(AccessMixin):
    """Memverifikasi level role user terhadap daftar permitted_roles."""

    permitted_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        user_role = getattr(request.user, "role", None)
        if user_role not in self.permitted_roles:
            raise PermissionDenied(
                f"Role {user_role} tidak diizinkan mengakses resource ini."
            )

        return super().dispatch(request, *args, **kwargs)
```

#### 2. Views Implementation (`views.py`)
```python
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, TemplateView, UpdateView
from .forms import ReportForm
from .mixins import RoleRequiredMixin, TenantAccessMixin
from .models import Report


class AnalyticsDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "analytics/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.user.tenant
        context["total_reports"] = Report.objects.filter(tenant=tenant).count()
        context["recent_reports"] = Report.objects.filter(tenant=tenant).order_by(
            "-created_at"
        )[:5]
        return context


class ReportListView(LoginRequiredMixin, TenantAccessMixin, ListView):
    model = Report
    template_name = "analytics/report_list.html"
    context_object_name = "reports"
    paginate_by = 10

    def get_queryset(self):
        # Filtering aman terhadap URL injection slug
        qs = super().get_queryset()
        category = self.request.GET.get("category")
        if category:
            qs = qs.filter(category=category)
        return qs.order_by("-created_at")


class ReportCreateView(
    LoginRequiredMixin, RoleRequiredMixin, TenantAccessMixin, CreateView
):
    model = Report
    form_class = ReportForm
    template_name = "analytics/report_form.html"
    permitted_roles = ["ADMIN", "ANALYST"]
    success_url = reverse_lazy("analytics:report-list")

    def form_valid(self, form):
        # Bind tenant dan author secara programmatic
        form.instance.tenant = self.request.user.tenant
        form.instance.author = self.request.user
        return super().form_valid(form)


class ReportUpdateView(
    LoginRequiredMixin, RoleRequiredMixin, TenantAccessMixin, UpdateView
):
    model = Report
    form_class = ReportForm
    template_name = "analytics/report_form.html"
    permitted_roles = ["ADMIN", "ANALYST"]
    success_url = reverse_lazy("analytics:report-list")
```

#### 3. Custom Template Tags & Filters (`templatetags/analytics_tags.py`)
```python
from django import template

register = template.Library()


@register.inclusion_tag("analytics/tags/metric_card.html", takes_context=True)
def render_metric_card(context, title, value, theme="primary", change_pct=None):
    """Menampilkan card metrik KPI dengan status persentase."""
    return {
        "title": title,
        "value": value,
        "theme": theme,
        "change_pct": change_pct,
        "request": context.get("request"),
    }


@register.filter(name="human_readable_currency")
def human_readable_currency(value, currency="Rp"):
    """Mengonversi 15000000 menjadi Rp 15,00 Jt atau format ringkas."""
    try:
        val = float(value)
    except (ValueError, TypeError):
        return value

    if abs(val) >= 1_000_000_000:
        formatted = f"{val / 1_000_000_000:.2f} M"
    elif abs(val) >= 1_000_000:
        formatted = f"{val / 1_000_000:.2f} Jt"
    elif abs(val) >= 1_000:
        formatted = f"{val / 1_000:.2f} Rb"
    else:
        formatted = f"{val:,.2f}"

    return f"{currency} {formatted}"
```

#### 4. Template Komponen (`templates/analytics/tags/metric_card.html`)
```html
<div class="card border-left-{{ theme }} shadow h-100 py-2">
  <div class="card-body">
    <div class="row no-gutters align-items-center">
      <div class="col mr-2">
        <div class="text-xs font-weight-bold text-{{ theme }} text-uppercase mb-1">{{ title }}</div>
        <div class="h5 mb-0 font-weight-bold text-gray-800">{{ value }}</div>
        {% if change_pct is not None %}
          <small class="{% if change_pct >= 0 %}text-success{% else %}text-danger{% endif %}">
            {{ change_pct }}% dari bulan lalu
          </small>
        {% endif %}
      </div>
    </div>
  </div>
</div>
```

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan checklist ini untuk memverifikasi kesiapan arsitektur sebelum memindahkan kode View Layer ke tahap staging/production:

- [ ] **Request-Response Flow:** Memahami titik intervensi request di WSGI/ASGI handler, urutan eksekusi middleware chain, resolver, dan handler methods.
- [ ] **URLconf Decoupling:** Seluruh endpoint menggunakan `path()` ber-namespace (`app_name:pattern_name`), tidak ada string hardcoded di view maupun template.
- [ ] **Class-Based View MRO:** Mixin otentikasi (`LoginRequiredMixin`, custom tenant mixin) selalu diposisikan di paling kiri (*leftmost*) sebelum generic view.
- [ ] **Data Scoping & Anti-Leakage:** Setiap generic view (`ListView`, `UpdateView`, `DetailView`) membatasi `get_queryset()` pada tenant/user yang sedang aktif, tidak mengandalkan filter manual yang rawan terlewat.
- [ ] **Database Optimization:** View bebas dari problem N+1 Query; pemanggilan `select_related()` dan `prefetch_related()` telah diaudit dengan Django Debug Toolbar atau Silk.
- [ ] **Idempotent Write Operations:** View yang mengeksekusi operasi finansial atau pemesanan mengimplementasikan transactional atomic lock (`select_for_update()`) dan idempotency token submission.
- [ ] **Memory Management:** File export berskala besar menggunakan `StreamingHttpResponse` bersama iterator generator, mencegah RAM pod melonjak melebihi limit.
- [ ] **Template Sanitization & Safety:** Filter `|safe` hanya digunakan setelah proses sanitasi (misal via library `bleach`); autoescape DTL tetap aktif secara default.
- [ ] **Context Processors Audited:** Tidak ada query database synchronous berat yang dieksekusi di dalam global context processor tanpa mekanisme caching layer.
