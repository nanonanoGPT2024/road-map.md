# BAB 07: RESTful API Engineering dengan Django REST Framework
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menguasai *lifecycle* internal eksekusi request-response pada Django REST Framework (DRF) dari routing hingga serialisasi akhir.
- Mengimplementasikan arsitektur *Nested Serializer* berkemampuan *writable* dengan jaminan konsistensi transaksional ACID (*Atomic, Consistent, Isolated, Durable*).
- Mendesain sistem otorisasi tingkat lanjut berbasis atribut (*Attribute-Based Access Control* / ABAC) dan peran (*Role-Based Access Control* / RBAC) menggunakan *custom permission classes*.
- Mengeliminasi anomali performa $N+1$ query melalui orkestrasi lanjutan `select_related`, `prefetch_related`, dan subquery expressions pada layer *DRF Serializer*.
- Mengimplementasikan strategi paginasi skala besar (*Cursor-based Pagination*) untuk meminimalkan beban I/O database pada dataset berjumlah puluhan juta baris.
- Mengonfigurasi arsitektur standardisasi respons kesalahan produksi sesuai standar RFC 7807 (*Problem Details for HTTP APIs*).
- Membangun strategi *caching* berlapis pada tingkat *view* dan *serializer representation* dengan Redis serta mekanisme *cache invalidation* berbasis sinyal.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib memahami:
- Arsitektur dasar Django REST Framework (Serializers, APIView, ViewSets, Routers).
- Relational Database Management System (RDBMS) tingkat lanjut: Transaction Isolation Levels, Database Locks (`FOR UPDATE`), Composite Indexing.
- Django ORM Optimization: Evaluasi *lazy queryset*, `select_related`, `prefetch_related`, `annotate`, dan `F` expressions.
- Konsep dasar protokol HTTP/1.1 dan HTTP/2: Idempotency, HTTP Methods, Safe Methods, Status Codes, dan Caching Headers (`ETag`, `Cache-Control`).

---

### 3. Concept & Internal Architecture

#### 3.1 DRF Request-Response Lifecycle
Ketika sebuah HTTP request masuk ke aplikasi Django yang menggunakan DRF, alur eksekusinya melintasi serangkaian abstraksi berlapis:

```
[HTTP Request] 
      │
      ▼
[Django WSGI/ASGI Handler] ──> [Security/Common Middlewares]
      │
      ▼
[URL Resolver (urls.py)] ──> Memanggil ViewSet/APIView.as_view()
      │
      ▼
[APIView.dispatch()]
      │
      ├──> 1. initialize_request()
      │         Konversi WSGIRequest standar ke DRF Request instance.
      │         (Lazy evaluation: request.data, request.user, request.auth)
      │
      ├──> 2. initial()
      │         ├──> format_kwarg resolution
      │         ├──> perform_authentication() [Iterasi AUTHENTICATION_CLASSES]
      │         ├──> check_permissions()      [Iterasi PERMISSION_CLASSES]
      │         └──> check_throttles()        [Iterasi THROTTLE_CLASSES]
      │
      ├──> 3. HTTP Method Handler (get, post, put, patch, delete)
      │         ├──> get_queryset() (Optimized ORM)
      │         ├──> get_serializer() -> Serializer Engine
      │         │       ├──> to_internal_value() / validate()
      │         │       └──> save() -> create() / update() [DB Transaction]
      │         └──> to_representation() [Data Serialization]
      │
      ├──> 4. handle_exception()
      │         Menangkap APIException / unhandled exceptions,
      │         memetakan ke custom exception handler (RFC 7807).
      │
      ▼
[APIView.finalize_response()]
      │
      ├──> Content Negotiation (Renderer classes: JSONRenderer, etc.)
      └──> Menambahkan HTTP Headers (Pagination, Throttle, CORS)
      │
      ▼
[HTTP Response]
```

1. **`initialize_request()`**: Membungkus objek `HttpRequest` bawaan Django ke dalam objek `rest_framework.request.Request`. DRF melakukan *lazy-parsing* terhadap *request body* (`request.data`) dan *lazy-authentication* (`request.user`), yang berarti kredensial dan body hanya didekode saat pertama kali diakses.
2. **`initial()` Engine**:
   - **`perform_authentication()`**: Menjalankan iterator kelas autentikasi secara berurutan. Jika salah satu kelas mengembalikan *tuple* `(user, auth)`, status terautentikasi terkunci. Jika terjadi kegagalan fatal (misal token kedaluwarsa), `AuthenticationFailed` (HTTP 401) dilemparkan.
   - **`check_permissions()`**: Mengeksekusi method `has_permission(request, view)` pada setiap kelas di `permission_classes`. Jika salah satu kelas mengembalikan `False`, eksekusi diputus seketika via `PermissionDenied` (HTTP 403).
   - **`check_throttles()`**: Memeriksa batasan laju request (*rate limits*) menggunakan cache storage (seperti Redis) via implementasi Leaky Bucket atau Token Bucket. Jika *rate limit* terlampaui, `Throttled` (HTTP 429) dilemparkan.
3. **Execution & Object Permissions**: Pada detail endpoint, method `get_object()` dipanggil. Method ini secara eksplisit memicu `check_object_permissions(request, obj)`, yang memanggil `has_object_permission(request, view, obj)` pada setiap kelas izin.
4. **Serializer Pipeline**:
   - *Deserialisasi/Validasi*: `run_validation()` $\rightarrow$ `to_internal_value()` $\rightarrow$ Field-level `validate_<field_name>()` $\rightarrow$ Object-level `validate()`.
   - *Serialisasi*: `to_representation()`, mengubah instance model atau primitif Python menjadi dictionary data murni sebelum diproses oleh Content Negotiator/Renderer.

#### 3.2 Dynamic Query Filtering & Index Alignment
Di lingkungan enterprise, endpoint API tidak boleh memproses filtering di memori Python. Queryset harus dibangun sedemikian rupa sehingga filter langsung diterjemahkan ke SQL klausa `WHERE` yang didukung oleh *B-Tree* atau *Hash Index* pada database:

```
Request URL: GET /api/v1/orders/?status=PAID&created_after=2023-01-01
                             │
                             ▼
                 [DjangoFilterBackend / FilterSet]
                             │
                             ▼
   [Query Optimization Layer: select_related & prefetch_related]
                             │
                             ▼
         [PostgreSQL: Index Scan on orders_status_created_idx]
```

---

### 4. Why & What

| Dimensi | Pola Dasar DRF (Naive) | Pola Arsitektur Enterprise DRF |
| :--- | :--- | :--- |
| **Data Serialization** | Menggunakan nested serializer standar dengan relasi foreign key tak terbatas. Memicu ratusan query ($N+1$). | Serialisasi hierarkis terkontrol dengan optimasi query eksplisit (`Prefetch` objects, queryset annotations), membatasi kedalaman serialisasi. |
| **Nested Writes** | Melakukan update model terkait secara manual tanpa transaksi. Rentan terhadap inkonsistensi data jika proses gagal di tengah jalan. | Menggunakan `transaction.atomic()`, `select_for_update()` untuk mencegah *race condition*, dan delegasi service layer. |
| **Pagination** | `PageNumberPagination` (`OFFSET / LIMIT`). Performa degradasi secara kuadratik pada halaman besar (misal: halaman 10.000). | `CursorPagination` berbasis indeks terurut (keyset pagination). Performa konstan $O(1)$ berapapun kedalaman dataset. |
| **Access Control** | Logika akses bercampur di dalam controller/view method (`if user.role == ...`). Sulit diuji dan rawan kebocoran data. | Otorisasi terisolasi berbasis deklaratif (*Policy-based / ABAC*) melalui subclassing `BasePermission` yang modular. |
| **Error Handling** | Mengembalikan stack trace HTML di production atau format error standar DRF yang tidak seragam antar endpoint. | Menggunakan format baku RFC 7807 (*Problem Details*) di seluruh layer aplikasi dengan *tracking ID* unik. |

---

### 5. How (Workflow Detail)

Alur perancangan endpoint enterprise DRF:

1. **Definisikan Kontrak DTO & Domain Logic**: Tentukan model data, relasi antar-entitas, dan aturan integritas.
2. **Desain Layer Query Engine**:
   - Tulis `get_queryset()` yang secara ketat memanfaatkan `select_related` untuk relasi 1-to-1 dan 1-to-Many (*forward*).
   - Gunakan `prefetch_related` dengan objek `Prefetch` yang difilter untuk relasi Many-to-Many atau Many-to-1 (*reverse*).
   - Implementasikan agregasi di tingkat DB menggunakan `annotate()` untuk menghindari penggunaan `SerializerMethodField` yang tidak efisien.
3. **Konstruksi Serializer Architecture**:
   - Terapkan validasi berlapis: Type-checking, Field-level validator, dan Cross-field conditional validation.
   - Override `create()` dan `update()` dengan isolasi database transaction (`transaction.atomic`).
4. **Implementasikan Otorisasi ABAC/RBAC**:
   - Bangun `BasePermission` kustom yang membaca konteks subjek (user/claims) dan objek (resource attributes).
5. **Konfigurasi Rate Limiting & Cursor Pagination**:
   - Pasang cursor pagination berbasis field yang terindeks (misal `created_at` atau `id`).
6. **Integrasikan RFC 7807 Error Interceptor**:
   - Daftarkan handler kustom pada `EXCEPTION_HANDLER` di settings DRF.

---

### 6. Analogy & Diagram ASCII

#### 6.1 Analogi Jalur Produksi & Pemeriksaan Keamanan
Bayangkan sebuah bandara internasional:
- **`initialize_request`**: Penumpang mendaftar di gerbang masuk; tiket fisik ditukar menjadi identitas digital terstandarisasi.
- **`perform_authentication`**: Petugas imigrasi memverifikasi paspor (mengecek siapa Anda).
- **`check_permissions`**: Pengecekan tiket kelas penerbangan (apakah Anda boleh masuk ke *Lounge First Class*).
- **`check_throttles`**: Pengatur antrean; jika terlalu banyak orang masuk sekaligus, pintu ditahan.
- **`Serializer`**: Staf bagasi. Saat barang masuk (deserialisasi), koper dibongkar dan diperiksa kepatuhan isinya (validasi). Saat barang keluar (serialisasi), barang dibungkus rapi sesuai standar maskapai.

#### 6.2 Siklus Validasi & Persistensi Serializer (Nested Writes)

```
Client Payload (JSON)
       │
       ▼
 [Serializer.is_valid()]
       │
       ├─► to_internal_value() ─── Validasi Tipe Data (e.g. Integer, UUID)
       │
       ├─► validate_<field>()  ─── Validasi Spesifik Field (e.g. qty > 0)
       │
       └─► validate()          ─── Validasi Kompleks Lintas Field/Relasional
                                   (e.g. cek stok inventaris saat ini)
       │
       ▼
 [Serializer.save()]
       │
       ▼
 [Database Transaction Boundary: BEGIN]
       │
       ├─► Parent Model Creation (e.g. Order) [Locks Applied if Update]
       │
       ├─► Iterasi Child Entities (e.g. OrderItem)
       │         │
       │         ├──► Validasi Integritas State
       │         └──► Bulk Create / Update Child Objects
       │
       ├─► Domain Events Emitted (Optional)
       │
 [Database Transaction Boundary: COMMIT] (Rollback jika terjadi kegagalan)
       │
       ▼
 [to_representation()] ─── Mengonversi Model instance ke Python Dict/JSON
```

---

### 7. Practical Example (Production-Ready Architecture)

Berikut adalah implementasi sistem pemrosesan pesanan enterprise (*Enterprise Order Management*) yang melibatkan:
1. *Writable Nested Serializers* dengan proteksi race condition (`transaction.atomic`, `select_for_update`).
2. *Dynamic Query Optimization* untuk mengatasi $N+1$ query.
3. *Custom Dynamic Role & Attribute-Based Permission* (ABAC).
4. Standardisasi Error berbasis RFC 7807.

#### 7.1 Domain Models (`models.py`)

```python
import uuid
from django.conf import settings
from django.db import models


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, db_index=True)
    sku = models.CharField(max_length=64, unique=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "products"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
        db_index=True,
    )
    status = models.CharField(
        max_length=32, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "orders"
        ordering = ["-created_at"]


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "order_items"
        constraints = [
            models.UniqueConstraint(fields=["order", "product"], name="unique_order_product")
        ]
```

#### 7.2 RFC 7807 Problem Details Handler (`exceptions.py`)

```python
from typing import Any, Dict, Optional
import uuid
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler


def rfc7807_exception_handler(exc: Exception, context: Dict[str, Any]) -> Optional[Response]:
    """Mengubah seluruh pengecualian API menjadi format standar RFC 7807 Problem Details."""
    # Ubah exception standar Django ke format DRF terlebih dahulu
    if isinstance(exc, Http404):
        exc = APIException("Resource not found")
        exc.status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, DjangoPermissionDenied):
        exc = APIException("Permission denied")
        exc.status_code = status.HTTP_403_FORBIDDEN

    response = exception_handler(exc, context)

    if response is not None:
        correlation_id = context["request"].headers.get("X-Correlation-ID", str(uuid.uuid4()))
        error_title = exc.__class__.__name__
        detail = response.data

        # Ekstraksi representasi error
        if isinstance(detail, dict) and "detail" in detail:
            detail_message = detail["detail"]
            invalid_params = None
        elif isinstance(detail, (dict, list)):
            detail_message = "Validation error occurred."
            invalid_params = detail
        else:
            detail_message = str(detail)
            invalid_params = None

        problem_data = {
            "type": f"https://api.domain.com/errors/{response.status_code}",
            "title": error_title,
            "status": response.status_code,
            "detail": detail_message,
            "instance": context["request"].build_absolute_uri(),
            "correlation_id": correlation_id,
        }

        if invalid_params:
            problem_data["invalid_params"] = invalid_params

        response.data = problem_data
        response["Content-Type"] = "application/problem+json"

    return response
```

#### 7.3 Advanced Permissions (`permissions.py`)

```python
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView
from .models import Order


class IsOrderOwnerOrElevatedStaff(BasePermission):
    """Otorisasi ABAC: Hanya pemilik pesanan atau staf operasional yang dapat mengakses objek."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        if not isinstance(obj, Order):
            return False

        # Staff dengan role admin memiliki akses absolut
        if request.user.is_staff or request.user.groups.filter(name="Operations").exists():
            return True

        # Konsumen hanya memiliki akses membaca dan membuat pada datanya sendiri
        if obj.customer_id == request.user.id:
            # Tidak diperbolehkan membatalkan jika status sudah COMPLETED
            if request.method in ["PUT", "PATCH"] and obj.status == Order.Status.COMPLETED:
                return False
            return True

        return False
```

#### 7.4 Advanced Writable Serializers (`serializers.py`)

```python
from decimal import Decimal
from typing import Any, Dict, List
from django.db import transaction
from rest_framework import serializers
from .models import Order, OrderItem, Product


class OrderItemInputSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)


class OrderItemOutputSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product_id", "product_name", "product_sku", "quantity", "unit_price"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemOutputSerializer(many=True, read_only=True)
    input_items = OrderItemInputSerializer(many=True, write_only=True, required=True)
    customer_email = serializers.EmailField(source="customer.email", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "customer_id",
            "customer_email",
            "status",
            "total_amount",
            "created_at",
            "updated_at",
            "items",
            "input_items",
        ]
        read_only_fields = ["id", "customer_id", "status", "total_amount", "created_at", "updated_at"]

    def validate_input_items(self, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not value:
            raise serializers.ValidationError("An order must contain at least one item.")
        
        # Deteksi duplikasi payload item
        product_ids = [item["product_id"] for item in value]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError("Duplicate products detected in order payload.")
        
        return value

    def create(self, validated_data: Dict[str, Any]) -> Order:
        items_data = validated_data.pop("input_items")
        customer = self.context["request"].user

        with transaction.atomic():
            # Kunci baris database produk terkait untuk mencegah race condition (Pessimistic Locking)
            product_ids = [item["product_id"] for item in items_data]
            products = (
                Product.objects.select_for_update()
                .filter(id__in=product_ids)
                .in_bulk(field_name="id")
            )

            # Validasi ketersediaan produk dan stok
            calculated_total = Decimal("0.00")
            order_items_to_create: List[OrderItem] = []

            for item in items_data:
                product_id = item["product_id"]
                qty = item["quantity"]
                product = products.get(product_id)

                if not product:
                    raise serializers.ValidationError(
                        {"input_items": f"Product {product_id} does not exist."}
                    )

                if product.stock_quantity < qty:
                    raise serializers.ValidationError(
                        {"input_items": f"Insufficient stock for product {product.name} (SKU: {product.sku}). Available: {product.stock_quantity}"}
                    )

                # Deduct Stock
                product.stock_quantity -= qty
                product.save(update_fields=["stock_quantity"])

                item_subtotal = product.price * qty
                calculated_total += item_subtotal

                order_items_to_create.append(
                    OrderItem(
                        product=product,
                        quantity=qty,
                        unit_price=product.price,
                    )
                )

            # Persistensi Order Induk
            order = Order.objects.create(
                customer=customer,
                total_amount=calculated_total,
                status=Order.Status.PROCESSING,
            )

            # Persistensi Many-to-One Child menggunakan Bulk Insert
            for order_item in order_items_to_create:
                order_item.order = order

            OrderItem.objects.bulk_create(order_items_to_create)

        return order
```

#### 7.5 Production ViewSet & Pagination (`views.py`)

```python
from django.db.models import Prefetch
from rest_framework import viewsets, mixins
from rest_framework.pagination import CursorPagination
from .models import Order, OrderItem
from .serializers import OrderSerializer
from .permissions import IsOrderOwnerOrElevatedStaff


class OrderCursorPagination(CursorPagination):
    page_size = 50
    ordering = "-created_at"
    cursor_query_param = "cursor"


class OrderViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrderSerializer
    pagination_class = OrderCursorPagination
    permission_classes = [IsOrderOwnerOrElevatedStaff]

    def get_queryset(self):
        """
        Query engine teroptimasi dengan eliminasi total N+1 Query.
        Data customer di-select via JOIN. Data items dan items.product
        di-prefetch secara deterministik.
        """
        user = self.request.user
        base_queryset = Order.objects.all()

        # Data Isolation Scoping
        if not (user.is_staff or user.groups.filter(name="Operations").exists()):
            base_queryset = base_queryset.filter(customer=user)

        return (
            base_queryset.select_related("customer")
            .prefetch_related(
                Prefetch(
                    "items",
                    queryset=OrderItem.objects.select_related("product"),
                )
            )
        )
```

---

### 8. Real World Case Study: Flash Sale Concurrency & Millions of Records

#### Kasus
Platform e-commerce B2B mengalami kegagalan sistem pada event *Flash Sale*. Endpoint pemesanan menerima 5.000 req/s. Terjadi *overselling* (stok inventaris menjadi negatif), query database mengalami *spiking* ke angka 150.000 QPS, dan latensi melambung hingga 18 detik per request.

#### Masalah Utama
1. **N+1 Query Explosion**: `OrderSerializer` memiliki `SerializerMethodField` yang menjalankan query `order.items.count()` dan mengecek status logistik satu per satu untuk setiap data di list.
2. **Paginasi OFFSET/LIMIT**: Database Postgres menghabiskan resource tinggi saat mengeksekusi `OFFSET 50000 LIMIT 20` karena harus melakukan scan terhadap ribuan index leaf.
3. **Race Condition pada Inventaris**: Tidak ada proteksi *row-level locking*. Dua thread membaca `stock_quantity = 1` secara paralel, keduanya mengeksekusi update, menghasilkan stok `-1`.

#### Solusi Arsitektural Terapan
1. Mengubah seluruh paginasi list API ke `CursorPagination`.
2. Menerapkan `select_for_update()` di dalam transaksi atomik saat validasi kuantitas produk.
3. Menghapus seluruh `SerializerMethodField` yang bersifat I/O-bound dan menggantinya dengan agregasi `annotate()` langsung di ORM queryset:
   ```python
   queryset = queryset.annotate(total_item_count=models.Count('items'))
   ```
4. Membungkus *cache hit* untuk katalog produk menggunakan Redis, memperbarui database hanya lewat antrean (Message Broker) untuk decoupled write processing pada event lonjakan ekstrem.

---

### 9. Trade-offs

```
              [Architectural Trade-offs Matrix]

      High Concurrency / Low Latency
                    ▲
                    │        ● Cursor Pagination + ORM Annotation
                    │        
                    │        ● Redis Representation Caching
                    │
                    │                  ● Pessimistic Locking (select_for_update)
                    │
                    │        ● Naive Serializers / Offset Pagination
                    └────────────────────────────────────────► Operational Complexity
```

- **Pessimistic Locking (`select_for_update`) vs. Optimistic Locking (Version Field)**:
  - *Pessimistic*: Menjamin pencegahan *race conditions* secara mutlak di DB; mengunci baris data hingga transaksi selesai. Trade-off: Risiko *deadlock* lebih tinggi dan konkurensi puncak menurun.
  - *Optimistic*: Menggunakan kolom versi tanpa lock fisik. Bagus untuk skenario *read-heavy*. Trade-off: Mengharuskan mekanisme retry pada client/worker ketika terjadi konkurensi write tinggi (*stale data failure*).
- **Cursor Pagination vs. Offset/Limit (`PageNumberPagination`)**:
  - *Cursor*: Performa konstan $O(1)$, ramah memori database, tidak terpengaruh penyisipan data baru. Trade-off: Tidak bisa melompat ke nomor halaman tertentu secara acak (e.g. tidak bisa langsung ke "Page 42").
  - *Offset/Limit*: Navigasi arbitrary page mudah dilakukan. Trade-off: Kompleksitas $O(N)$ pada database, performa memburuk secara signifikan pada dataset besar.
- **Nested Serializers vs. Flat Endpoints**:
  - *Nested Writes*: Menjaga kemudahan konsumsi API bagi client (1 request menyelesaikan seluruh form/transaksi). Trade-off: Meningkatkan kompleksitas serializer dan beban memori Python.
  - *Flat Endpoints*: Pemisahan endpoint (misal `POST /orders/` lalu `POST /order-items/`). Trade-off: Menggeser manajemen integritas transaksi atomik ke sisi client, memperbesar risiko data gantung (*orphaned records*).

---

### 10. Common Mistakes & Troubleshooting

#### 1. Melakukan Query Database di dalam `SerializerMethodField`
```python
# ANTI-PATTERN (CRITICAL BUG PERFORMA)
class OrderListSerializer(serializers.ModelSerializer):
    store_name = serializers.SerializerMethodField()

    def get_store_name(self, obj):
        # Memicu 1 query tambahan untuk SETIAP baris di dalam page (N+1 query)
        return obj.customer.merchant.store.name
```
*Solusi*: Gunakan ORM traversal via double-underscore (`customer__merchant__store__name`) di `select_related` atau gunakan anotasi ORM, kemudian petakan via `CharField(source=...)`.

#### 2. Mutasi `request.data` Secara Langsung
Objek `request.data` pada DRF bersifat immutable (bertipe `QueryDict` atau copy-protected dictionary).
```python
# ANTI-PATTERN
request.data["user"] = request.user.id  # Melempar AttributeError / ValueError
```
*Solusi*: Masukkan data kontekstual melalui `serializer.save(user=request.user)` atau manfaatkan `serializer.context`.

#### 3. Kebocoran Data Multi-Tenant (Insecure Direct Object Reference / IDOR)
Mengandalkan lookup URL (`/api/orders/<uuid:pk>/`) tanpa membatasi queryset model.
*Solusi*: Pastikan `get_queryset()` selalu melakukan scoping berdasarkan identitas pengguna (`filter(tenant=request.user.tenant)`). Jangan hanya mengandalkan permission class.

#### 4. Memory Exhaustion Akibat Serialisasi Dataset Raksasa
Memanggil `.all()` pada jutaan data tanpa streaming atau paginasi dapat membebani memori server hingga memicu *Out of Memory* (OOM) killer.
*Solusi*: Wajibkan global paginasi di `REST_FRAMEWORK` settings:
```python
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.CursorPagination",
    "PAGE_SIZE": 100,
}
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Indeks Basis Data**: Pastikan field yang digunakan untuk sorting (`-created_at`), foreign keys, dan filter unik memiliki indeks gabungan (*composite indexes*) yang tepat di database.
- [ ] **N+1 Query Assertion**: Tulis automated test yang mengeksekusi assertion `assertNumQueries` untuk memastikan jumlah query tidak bertambah seiring membesarnya ukuran batch data.
- [ ] **Gunakan `select_for_update(nowait=False, skip_locked=False)` dengan Tepat**: Tentukan batas *timeout* transaksi agar thread DB tidak terkunci permanen saat terjadi lonjakan antrean transaksi.
- [ ] **Gunakan `bulk_create` / `bulk_update`**: Hindari iterasi pemanggilan `.save()` di dalam perulangan loop serializer.
- [ ] **Atomic Writes**: Bungkus seluruh manipulasi write bertingkat (parent-child) ke dalam blok `with transaction.atomic():`.
- [ ] **Isolasi Serializer Baca dan Tulis**: Buat serializer terpisah untuk payload input (*request*) dan representasi output (*response*) untuk menghindari payload pollution dan logic branching berlebih.
- [ ] **Penyembunyian ID Internal Auto-Increment**: Gunakan UUIDv4, NanoID, atau HashID untuk ID publik di endpoint URL guna mencegah teknik *enumeration attacks*.
- [ ] **Standardisasi Error RFC 7807**: Terapkan exception handler global agar client menerima format error seragam, termasuk `correlation_id` untuk kemudahan penelusuran log di OpenSearch/Datadog.

---

### 12. Hands-on Practice

Buat dan simpan struktur praktikum ini pada direktori:
`hands-on/m02/`

#### Langkah 1: Inisialisasi Lingkungan & Struktur Folder
```bash
mkdir -p hands-on/m02/project/core hands-on/m02/project/orders
cd hands-on/m02
python -m venv venv
source venv/bin/activate  # atau venv\Scripts\activate pada Windows
pip install django djangorestframework psycopg2-binary
```

#### Langkah 2: Konfigurasi Core Settings & DRF Engine
Tulis pada file `hands-on/m02/project/core/settings.py`:
```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-enterprise-production-grade-secret-key"
DEBUG = False
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "rest_framework",
    "orders",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "core.urls"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",  # Gunakan sqlite3 in-memory untuk simplifikasi hands-on lokal
        "NAME": BASE_DIR / "production_simulation.sqlite3",
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.BasicAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "EXCEPTION_HANDLER": "orders.exceptions.rfc7807_exception_handler",
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
```

#### Langkah 3: Setup App Implementasi
Salin kode dari **Seksi 7 (Practical Example)** ke file-file berikut di dalam `hands-on/m02/project/orders/`:
- `models.py`
- `exceptions.py`
- `permissions.py`
- `serializers.py`
- `views.py`

Buat `hands-on/m02/project/orders/urls.py`:
```python
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet

router = DefaultRouter()
router.register(r"orders", OrderViewSet, basename="order")

urlpatterns = router.urls
```

Buat `hands-on/m02/project/core/urls.py`:
```python
from django.urls import path, include

urlpatterns = [
    path("api/v1/", include("orders.urls")),
]
```

#### Langkah 4: Automated Verification Test (Validasi Anti N+1 & Race Condition)
Buat file `hands-on/m02/project/orders/tests.py`:
```python
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from .models import Order, OrderItem, Product


class EnterpriseOrderTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="client1", password="password123")
        self.staff_user = User.objects.create_superuser(username="admin", password="password123")
        self.client.force_authenticate(user=self.user)

        self.p1 = Product.objects.create(name="CPU", sku="CPU-01", price=Decimal("300.00"), stock_quantity=10)
        self.p2 = Product.objects.create(name="RAM", sku="RAM-01", price=Decimal("100.00"), stock_quantity=20)

    def test_order_creation_with_transactional_stock_deduction(self):
        url = reverse("order-list")
        payload = {
            "input_items": [
                {"product_id": str(self.p1.id), "quantity": 2},
                {"product_id": str(self.p2.id), "quantity": 3},
            ]
        }

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Refresh database state
        self.p1.refresh_from_db()
        self.p2.refresh_from_db()

        self.assertEqual(self.p1.stock_quantity, 8)
        self.assertEqual(self.p2.stock_quantity, 17)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Order.objects.first().total_amount, Decimal("900.00"))

    def test_stock_out_of_bounds_rollback(self):
        url = reverse("order-list")
        payload = {
            "input_items": [
                {"product_id": str(self.p1.id), "quantity": 50},  # Melebihi stock
            ]
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Pastikan tidak ada data order yang tersimpan akibat rollback
        self.assertEqual(Order.objects.count(), 0)
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.stock_quantity, 10)

    def test_n_plus_one_elimination_in_list_view(self):
        # Buat 5 pesanan
        for _ in range(5):
            o = Order.objects.create(customer=self.user, total_amount=Decimal("100.00"))
            OrderItem.objects.create(order=o, product=self.p1, quantity=1, unit_price=Decimal("100.00"))

        url = reverse("order-list")
        
        # Eksekusi pengecekan budget query:
        # 1 query: Auth/Session
        # 1 query: Select Orders + Customer (JOIN via select_related)
        # 1 query: Prefetch OrderItems + Product (JOIN via Prefetch/select_related)
        with self.assertNumQueries(3):
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
```

Jalankan test suite:
```bash
python manage.py makemigrations orders
python manage.py migrate
python manage.py test orders
```

---

### 13. Exercise

#### Level: Easy
1. Tambahkan validasi pada `OrderItemInputSerializer` untuk mencegah pemesanan kuantitas melebihi angka 100 unit per item.
2. Konfigurasikan response header pada `OrderViewSet` untuk menyertakan `X-Server-Time` (ISO 8601) pada response akhir menggunakan override method `finalize_response`.

#### Level: Medium
1. Implementasikan mekanisme *Soft Delete* pada `Order` (kolom `is_deleted` dan `deleted_at`).
2. Pastikan pemanggilan HTTP `DELETE` memicu soft delete, dan seluruh endpoint `get_queryset()` secara otomatis mengecualikan entitas yang telah dihapus tanpa merusak paginasi atau prefetch relations.

#### Level: Hard
1. Buat sistem *Dynamic Field Filtering* serializer. Klien dapat mengirimkan query parameter `?fields=id,status,total_amount`. Serializer harus mengeliminasi field yang tidak diminta saat serialisasi `to_representation` untuk menghemat bandwidth dan alokasi memori secara dinamis tanpa mengorbankan fungsionalitas caching.

---

### 14. Challenge

**Skenario**: Anda memimpin tim rekayasa backend untuk sistem *Core Banking Ledger* berbasis DRF yang menangani mutasi transaksi antar-rekening nasabah dengan volume transaksi tinggi.

**Spesifikasi Persyaratan**:
1. Buat endpoint idempotent: `POST /api/v1/ledger/transfers/`.
2. Jika client mengalami *timeout* dan mengirimkan request ulang dengan `Idempotency-Key` pada HTTP Header yang sama, server tidak boleh mendebit ulang saldo, melainkan harus mengembalikan respons yang sama persis seperti request awal yang tersimpan.
3. Kunci transaksi harus diamankan di tingkat database agar tidak terjadi *deadlock* saat dua nasabah saling mentransfer dana secara bersamaan di milidetik yang sama (Account A $\rightarrow$ Account B bersamaan dengan Account B $\rightarrow$ Account A).
4. Buat benchmark test yang menguji 50 concurrent request menggunakan akun yang sama tanpa terjadi selisih saldo (*zero-balance discrepancy*).

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1. Kapan tepatnya method `perform_authentication` pada DRF dieksekusi di dalam siklus penanganan request?
2. Mengapa penggunaan `SerializerMethodField` sering kali menjadi penyebab utama masalah performa $N+1$ query pada endpoint list?
3. Apa perbedaan fundamental antara method `validate_<field_name>` dan method `validate` pada kelas Serializer?
4. Apa fungsi dari parameter `source='*'` pada field serialisasi DRF?
5. Mengapa `PageNumberPagination` tidak disarankan untuk dataset berskala puluhan juta baris?

#### Pertanyaan Intermediate
6. Bagaimana cara membatasi eksekusi query pada nested serializer jika data child hanya dibutuhkan saat kondisi tertentu (misal: hanya untuk pengguna bertipe admin)?
7. Apa perbedaan mendasar antara implementasi `has_permission` dan `has_object_permission` pada `BasePermission`, dan mengapa `has_object_permission` tidak otomatis terpanggil pada request berjenis `POST` (create)?
8. Di layer mana sebaiknya isolasi transaksi database `transaction.atomic()` diletakkan: di dalam View, Serializer, atau Service Layer? Berikan landasan teknisnya.
9. Jelaskan bagaimana `django.db.models.Prefetch` dapat digunakan untuk melakukan filtering lanjutan pada relasi yang di-prefetch!
10. Bagaimana DRF mengelola parsing payload untuk method `PATCH` vs `PUT` melalui parameter `partial=True` pada proses instansiasi serializer?

#### Skenario Kasus Produksi
11. **Skenario 1**: Endpoint `GET /api/v1/users/me/notifications/` mengalami degradasi performa drastis ketika jumlah notifikasi seorang pengguna mencapai 500.000 data. Indeks database pada `user_id` dan `created_at` sudah aktif. Apa akar permasalahannya jika endpoint masih menggunakan `PageNumberPagination`, dan bagaimana rancangan solusinya?
12. **Skenario 2**: Log server menunjukkan ribuan error HTTP 500 dengan pesan `TransactionManagementError: An error occurred in the current transaction department... You can't execute queries until the end of the 'atomic' block`. Apa kesalahan implementasi yang terjadi pada view/serializer tersebut dan bagaimana cara memulihkannya?
13. **Skenario 3**: Sebuah microservice DRF memproses webhook pembayaran masuk secara asynchronous dari payment gateway. Terjadi insiden di mana status pesanan terupdate menjadi `PAID`, namun item log pengiriman barang tidak terbentuk karena eksekusi terputus sebelum baris create selesai. Bagaimana Anda merancang mitigasi arsitektural berbasis ACID pada Serializer method tersebut?

---

### 16. Summary

1. **Architecture Lifecycle**: Memahami lifecycle internal `APIView` (`dispatch` $\rightarrow$ `initialize_request` $\rightarrow$ `initial` $\rightarrow$ `handle_exception`) memungkinkan rekayasa kontrol akses, validasi, dan penanganan error terpusat yang tangguh.
2. **Query Optimization**: Serializer tidak boleh dipisahkan dari arsitektur Queryset. Eliminasi query $N+1$ wajib menggunakan `select_related` untuk relasi tunggal (*forward*) dan `prefetch_related` dengan objek `Prefetch` terisolasi untuk relasi jamak (*reverse/M2M*).
3. **Integritas Writable Serializer**: Operasi mutasi data nested wajib diisolasi di dalam blok `transaction.atomic()`, didukung oleh mekanisme *pessimistic locking* (`select_for_update()`) untuk mengeliminasi race conditions dan anomali inkonsistensi data.
4. **Skalabilitas Pagination**: Tinggalkan pagination berbasis `OFFSET / LIMIT` (`PageNumberPagination`) untuk tabel berskala masif; gunakan *keyset/cursor pagination* (`CursorPagination`) untuk menjaga kestabilan latensi database pada kompleksitas $O(1)$.
5. **Observabilitas & Standar Produksi**: Selalu gunakan arsitektur exception terpusat berbasis standar industri seperti **RFC 7807 (Problem Details)** untuk memfasilitasi debugging sistem terdistribusi melalui pelacakan *Correlation ID*.