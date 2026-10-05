# BAB-07-RESTful-API-Engineering-dengan-Django-REST-Framework: Quiz, Challenge, & Knowledge Check

Selamat datang di instrumen evaluasi dan pengujian kompetensi untuk **BAB-07: RESTful API Engineering dengan Django REST Framework (DRF)**. Dokumen ini dirancang untuk menguji pemahaman teoritis, kemampuan arsitektur backend, penyelesaian insiden produksi, serta implementasi praktis berbasis kode standar industri.

---

## Bagian 1: Basic Questions (5 Pertanyaan Dasar)

### Pertanyaan 1: DRF Serializer vs Django Form
**Pertanyaan:**  
Jelaskan perbedaan mendasar antara `django.forms.Form` bawaan Django dan `rest_framework.serializers.Serializer` dalam siklus request-response! Mengapa DRF memerlukan lapisan serializer tersendiri alih-alih menggunakan Django Forms?

#### Jawaban & Pembahasan:
- **Tujuan Utama:**
  - `Django Forms` dirancang untuk interaksi berbasis Server-Side Rendering (SSR) HTML. Forms bertugas memvalidasi data form POST (`application/x-www-form-urlencoded` atau `multipart/form-data`) dan me-render widget HTML ke dalam template.
  - `DRF Serializer` dirancang untuk API nir-antarmuka (decoupled client-server). Serializer memiliki fungsi ganda simetris:
    1. **Serialization:** Mengonversi objek kompleks (model queryset, instance model) menjadi format native Python primitive dictionary yang dapat langsung di-parse menjadi JSON/XML/MessagePack oleh Renderer.
    2. **Deserialization & Validation:** Mem-parse incoming parser data (seperti raw JSON body) ke Python dictionary, memvalidasi integritas data melalui skema field, dan mengonversinya menjadi objek valid atau menyimpan langsung ke database via `.save()`.
- **Content Negotiation & Content-Type:**
  - DRF Serializer beroperasi seamlessly dengan DRF Parsers (`JSONParser`) dan Renderers (`JSONRenderer`), mendukung negosiasi konten otomatis (`Accept` header). Django Form terikat erat pada request standard HTTP POST standard browser.

---

### Pertanyaan 2: Siklus Validasi Serializer (`is_valid()`)
**Pertanyaan:**  
Uraikan urutan eksekusi method validasi yang dijalankan DRF ketika kita memanggil `serializer.is_valid(raise_exception=True)`! Kapan `validate_<field_name>()` dan `validate()` dipanggil?

#### Jawaban & Pembahasan:
Ketika `is_valid()` dipanggil pada serializer:
1. `to_internal_value(data)` dijalankan:
   - Nilai tiap field di-cast dari tipe data input (misal JSON string) ke tipe data native Python (misal `datetime.date`, `int`).
2. Validasi per field tingkat bawaan:
   - Mengecek `required`, `allow_null`, `max_length`, regex, dan validator level field bawaan (misal `EmailValidator`).
3. Method kustom `validate_<field_name>(self, value)`:
   - Dijalankan untuk setiap field yang memiliki method validasi khusus. Method ini menerima nilai field yang telah dikonversi, dan wajib mengembalikan nilai (yang telah ditransformasi atau orisinal) atau melempar `serializers.ValidationError`.
4. Method kustom `validate(self, attrs)` (Object-level validation):
   - Dipanggil setelah seluruh validasi per-field selesai. Menerima dictionary `attrs` yang berisi semua field yang valid. Bagian ini digunakan untuk validasi ketergantungan silang antar field (misal: `password` vs `confirm_password`, atau `start_date` vs `end_date`). Wajib melempar `serializers.ValidationError` jika melanggar invariant bisnis atau mengembalikan `attrs`.
5. Jika ada exception dan `raise_exception=True`, DRF melempar `ValidationError` yang ditangkap otomatis oleh DRF exception handler dan mengembalikan HTTP status `400 Bad Request` dengan payload error terstruktur.

---

### Pertanyaan 3: Perbedaan APIView, Generic Views, dan ViewSets
**Pertanyaan:**  
Jelaskan hierarki abstraksi view dalam DRF: kapan software engineer harus memilih `APIView`, `GenericAPIView` (bersama Mixins), dan `ModelViewSet`?

#### Jawaban & Pembahasan:
- **`APIView`:**
  - Level abstraksi paling rendah di atas Django standard view.
  - Memberikan kontrol manual penuh atas HTTP verbs (`get()`, `post()`, `put()`, `delete()`).
  - **Kapan Digunakan:** Endpoint RPC, integrasi webhook pihak ketiga (Stripe, Midtrans), trigger workflow asynchronously, atau endpoint agregasi laporan kompleks yang tidak memetakan resource CRUD database langsung.
- **`GenericAPIView` + Mixins (atau Concrete Generic Views seperti `ListCreateAPIView`):**
  - Menggabungkan logic reusable: memetakan `queryset` dan `serializer_class` dengan perilaku CRUD umum melalui mixins (`ListModelMixin`, `CreateModelMixin`, dll.).
  - **Kapan Digunakan:** Resource RESTful eksplisit yang membutuhkan endpoint terpisah (misal `/articles/` dan `/articles/<id>/`) dengan kontrol routing URL eksplisit tanpa magic router, atau saat pola CRUD memerlukan sedikit kustomisasi hook (`perform_create`, `get_queryset`).
- **`ModelViewSet` / `ReadOnlyModelViewSet`:**
  - Level abstraksi tertinggi yang menggabungkan seluruh aksi standar (`list`, `create`, `retrieve`, `update`, `partial_update`, `destroy`) ke dalam satu class controller.
  - Menggunakan `DefaultRouter` atau `SimpleRouter` untuk menghasilkan URL routing secara otomatis sesuai konvensi RESTful.
  - **Kapan Digunakan:** Resource standar yang mengikuti konvensi CRUD RESTful penuh untuk meminimalkan duplikasi kode (DRY) dan mempercepat standarisasi API.

---

### Pertanyaan 4: Autentikasi vs Permission pada DRF
**Pertanyaan:**  
Jelaskan perbedaan mendasar antara Authentication (`authentication_classes`) dan Permissions (`permission_classes`) di DRF! Mana yang dieksekusi lebih dulu oleh `initial()` handler?

#### Jawaban & Pembahasan:
- **Authentication:**
  - Bertugas mengidentifikasi **siapa** klien yang melakukan request (menentukan *Identity*).
  - Mengekstrak kredensial dari header (misal: `Authorization: Bearer <token>` atau session cookie), lalu mengisi `request.user` dengan objek model User (atau `AnonymousUser` jika gagal/tanpa kredensial) dan `request.auth` dengan objek token/payload terkait.
- **Permissions:**
  - Bertugas memutuskan **apakah** identitas yang sudah terotentikasi berhak mengakses aksi atau resource yang diminta (menentukan *Authorization*).
  - Mengevaluasi method `has_permission(request, view)` untuk view-level permission dan `has_object_permission(request, view, obj)` saat mengakses objek tunggal.
- **Urutan Eksekusi:**
  - Authentication selalu dieksekusi terlebih dahulu. DRF menjalankan `request.user` (yang memicu autentikasi lazy/eager) sebelum memanggil `check_permissions(request)`. Tanpa penentuan `request.user`, permission checker tidak memiliki identitas untuk dievaluasi.

---

### Pertanyaan 5: Solusi N+1 Query pada Serializer Relasional
**Pertanyaan:**  
Apa yang menyebabkan timbulnya N+1 Problem saat melakukan serialisasi data relasional (Foreign Key / Many-to-Many) menggunakan nested serializer, dan bagaimana cara mengatasinya secara elegan di tingkat queryset?

#### Jawaban & Pembahasan:
- **Penyebab:**
  - Jika serializer parent memiliki nested serializer untuk field relasi (misalnya `OrderSerializer` memiliki nested `CustomerSerializer` atau `OrderItemSerializer`), serializer akan memanggil atribut relasi pada setiap instance loop parent.
  - Tanpa pre-fetching, Django ORM akan mengeksekusi 1 query SQL untuk mengambil list parent (N baris), lalu mengeksekusi 1 query tambahan untuk *setiap* baris relasi yang diakses saat serialisasi, menghasilkan total $1 + N$ (atau bahkan lebih banyak) query database ke server database.
- **Solusi:**
  - Terapkan optimasi pada method `get_queryset()` di View/ViewSet:
    - Gunakan `select_related('foreign_key_field')` untuk relasi `ForeignKey` dan `OneToOneField` (melakukan SQL `JOIN`).
    - Gunakan `prefetch_related('many_to_many_or_reverse_fk')` untuk relasi `ManyToManyField` atau reverse `ForeignKey` (melakukan batch query terpisah dengan SQL `IN (...)`).

---

## Bagian 2: Intermediate Questions (5 Pertanyaan Menengah)

### Pertanyaan 1: Idempotensi PUT vs PATCH dalam DRF Serializer
**Pertanyaan:**  
Berdasarkan RFC 9110 dan standar DRF, jelaskan perbedaan semantik HTTP `PUT` dan `PATCH`! Bagaimana implementasi internal `partial_update` pada `UpdateModelMixin` DRF menangani perbedaan ini?

#### Jawaban & Pembahasan:
- **Semantik:**
  - `PUT`: Menggantikan seluruh state resource secara utuh (full replacement). Idempoten. Seluruh field non-read-only yang wajib harus disertakan. Jika suatu field opsional tidak dikirimkan, nilai field tersebut biasanya di-reset ke nilai default atau null.
  - `PATCH`: Mengubah sebagian state resource (partial modification). Tidak dijamin idempoten secara teori umum, namun dalam implementasi DRF resource-state umumnya idempoten. Hanya field yang ingin dimodifikasi yang dikirimkan dalam payload.
- **Implementasi DRF:**
  - Pada `UpdateModelMixin`, action `update()` memanggil:
    ```python
    serializer = self.get_serializer(instance, data=request.data, partial=partial)
    ```
  - Untuk HTTP `PUT`, `partial = False`. Serializer akan memvalidasi semua field bertanda `required=True`. Jika ada field yang hilang, validasi akan gagal dengan pesan error *“This field is required.”*
  - Untuk HTTP `PATCH`, `partial_update()` memanggil `update()` dengan argumen `partial=True`. Ketika `partial=True`, serializer melewati pengecekan keberadaan field (`required=True` hanya divalidasi jika key field tersebut secara eksplisit ada di dictionary payload).

---

### Pertanyaan 2: Dynamic Fields Serializer Pattern
**Pertanyaan:**  
Dalam arsitektur API skala besar, client sering kali hanya membutuhkan subset field tertentu dari resource (sparse fieldsets / field filtering). Bagaimana cara mendesain sebuah Base Serializer class yang dapat membatasi field secara dinamis berdasarkan parameter query string `?fields=id,name,email`?

#### Jawaban & Pembahasan:
Kita dapat meng-override method `__init__` pada `serializers.ModelSerializer`:

```python
from rest_framework import serializers

class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """
    ModelSerializer yang menerima argumen 'fields' opsional
    untuk mengontrol field apa saja yang di-output ke JSON.
    """
    def __init__(self, *args, **kwargs):
        # Ambil argumen 'fields' jika dioper via context atau kwargs langsung
        fields = kwargs.pop('fields', None)

        super().__init__(*args, **kwargs)

        if fields is not None:
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)
```
Pada ViewSet atau view, kita bisa menginisialisasi serializer dengan memanfaatkan `request.query_params`:
```python
def get_serializer(self, *args, **kwargs):
    serializer_class = self.get_serializer_class()
    kwargs.setdefault('context', self.get_serializer_context())
    
    fields_param = self.request.query_params.get('fields')
    if fields_param:
        kwargs['fields'] = fields_param.split(',')
        
    return serializer_class(*args, **kwargs)
```

---

### Pertanyaan 3: Keamanan Eksekusi Token JWT (Access Token vs Refresh Token)
**Pertanyaan:**  
Ketika menggunakan library `djangorestframework-simplejwt`, mengapa Access Token memiliki umur sangat pendek (misal 5-15 menit) sedangkan Refresh Token memiliki umur lebih panjang (misal 1-7 hari)? Bagaimana mekanisme rotasi token (Token Rotation) dan Blacklisting mencegah penyalahgunaan saat Refresh Token dicuri?

#### Jawaban & Pembahasan:
- **Alasan Perbedaan Masa Aktif:**
  - Access Token dikirimkan pada setiap HTTP request (`Authorization: Bearer <token>`). Ini membuatnya lebih rentan terhadap MITM, logging proxy, atau leakage client. Karena bersifat *stateless* (diverifikasi via signature kriptografis publik/privat tanpa query database), Access Token yang bocor tidak dapat dibatalkan seketika tanpa overhead blacklist terpusat. Oleh karena itu, masa aktifnya dibuat sangat singkat.
  - Refresh Token hanya dikirimkan ke endpoint `/api/token/refresh/` saat access token kadaluarsa. Refresh token disimpan secara lebih aman (misalnya di HttpOnly secure cookie atau secure enclave).
- **Token Rotation & Blacklisting:**
  - **Rotation:** Setiap kali refresh token digunakan untuk meminta access token baru, SimpleJWT menerbitkan access token baru DAN refresh token baru, serta mematikan refresh token lama.
  - **Blacklisting:** Hash dari refresh token lama yang sudah dipakai dicatat ke database (tabel `OutstandingToken` / `BlacklistedToken`) atau cache Redis. Jika penyerang mencoba menggunakan refresh token lama yang sudah di-rotate, sistem mendeteksi *token reuse anomaly*, segera mem-blacklist seluruh rangkaian token family milik pengguna tersebut, dan memaksa re-autentikasi lengkap.

---

### Pertanyaan 4: Throttling & Rate Limiting Granular di DRF
**Pertanyaan:**  
Bagaimana mekanisme kerja DRF Throttling (`ScopedRateThrottle` dan `UserRateThrottle`)? Jika backend menggunakan Redis sebagai cache backend, bagaimana cara membedakan rate limit antara endpoint publik (unauthenticated) dan endpoint VIP tier berbayar?

#### Jawaban & Pembahasan:
- **Mekanisme Kerja DRF Throttle:**
  - Mengimplementasikan algoritma sliding window atau fixed time window berbasis cache backend (seperti Redis).
  - DRF mengekstrak *identifier/cache key*:
    - Untuk user terotentikasi: `throttle_user_<user_id>`
    - Untuk anonim: `throttle_anon_<ip_address>`
  - DRF memanggil `throttle.allow_request(request, view)`. Setiap request mencatat timestamp di cache list. Jika jumlah request dalam jangka waktu tertentu (`num_requests / duration`) melampaui limit, method mengembalikan `False` dan melempar `Throttled(wait=wait_seconds)` menghasilkan HTTP `429 Too Many Requests`.
- **Kustomisasi VIP Tier Throttle:**
  Buat subclass dari `UserRateThrottle`:
  ```python
  from rest_framework.throttling import UserRateThrottle

  class TieredUserRateThrottle(UserRateThrottle):
      def get_rate(self):
          if self.request.user and self.request.user.is_authenticated:
              tier = getattr(self.request.user, 'subscription_tier', 'free')
              if tier == 'enterprise':
                  return '10000/hour'
              elif tier == 'pro':
                  return '2000/hour'
              return '200/hour'
          return '30/hour' # anonim
  ```

---

### Pertanyaan 5: Custom Pagination & Cursor vs PageNumber Pagination
**Pertanyaan:**  
Mengapa `PageNumberPagination` (`?page=5000`) mengalami degradasi performa drastis pada dataset tabel PostgreSQL berisi puluhan juta baris? Kapan software engineer harus beralih ke `CursorPagination`, dan apa trade-off fungsionalitasnya bagi antarmuka frontend?

#### Jawaban & Pembahasan:
- **Penyebab Degradasi:**
  - `PageNumberPagination` menggunakan SQL `LIMIT n OFFSET m`. Ketika user meminta halaman ke-5000 dengan page size 20, database mengeksekusi `OFFSET 100000`. PostgreSQL harus membaca dan memindai 100.020 baris indeks/tabel, lalu membuang 100.000 baris pertama. Ini menimbulkan disk I/O tinggi dan response time lambat.
  - Selain itu, `PageNumberPagination` selalu menjalankan query `SELECT COUNT(*)` di awal untuk menghitung total item, yang sangat lambat pada tabel raksasa PostgreSQL tanpa approximate count.
- **Keunggulan `CursorPagination`:**
  - Menggunakan teknik Keyset Pagination berbasis pointer terenkripsi (misalnya timestamp atau sequence ID terurut: `WHERE created_at < :cursor ORDER BY created_at DESC LIMIT 20`).
  - Kompleksitas query selalu konstan $O(\log N)$ karena menggunakan index seek langsung tanpa memindai baris-baris sebelumnya (`OFFSET 0`).
  - Menghindari duplikasi/pergeseran baris saat ada penambahan data baru secara real-time (infinite scroll feed).
- **Trade-off:**
  - Klien tidak bisa melompat langsung ke halaman acak (misal "Ke Halaman 17").
  - Klien tidak mengetahui total halaman dan total jumlah record.
  - UI frontend dibatasi pada tombol navigasi *Previous* / *Next* atau infinite scroll.

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Real-World Incidents)

### Skenario 1: Memory Leak & OOM Killer pada Endpoint Export JSON Masif
**Konteks Masalah:**  
Sebuah startup logistik memiliki endpoint `GET /api/v1/shipments/export/` yang dibangun menggunakan DRF `APIView`. Pada akhir bulan, ketika tim operasional mengekspor 250.000 data pengiriman untuk laporan audit, worker Gunicorn tiba-tiba mati terbunuh oleh Linux OS OOM (Out Of Memory) Killer dengan status `SIGKILL (Signal 9)`.

**Analisis Masalah:**
1. Method `get()` mengeksekusi `Shipment.objects.filter(...)` yang langsung di-evaluasi menjadi list Python objek raksasa dalam memory RAM.
2. Queryset dioper ke `ShipmentExportSerializer(shipments, many=True)`. DRF menginstansiasi serializer dan menghasilkan dictionary Python untuk 250.000 objek beserta nested customer and driver data.
3. Response JSON dikonstruksi secara in-memory melalui `Response(serializer.data)`, menyebabkan alokasi memori meledak hingga beberapa Gigabyte sebelum HTTP stream terkirim.

**Solusi Rekayasa:**
Gunakan pagination streaming atau Django `StreamingHttpResponse` bersama iterator ORM (`iterator(chunk_size=2000)`) dan parser stream JSON:

```python
import json
from django.http import StreamingHttpResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .models import Shipment

class ShipmentStreamingExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = (
            Shipment.objects
            .filter(organization=request.user.organization)
            .select_related('customer', 'driver')
            .order_by('id')
            .iterator(chunk_size=2000)
        )

        def stream_generator():
            yield '{"data": ['
            first = True
            for item in queryset:
                if not first:
                    yield ','
                first = False
                record = {
                    "id": item.id,
                    "tracking_number": item.tracking_number,
                    "status": item.status,
                    "customer_name": item.customer.name,
                    "driver_name": item.driver.name if item.driver else None,
                    "cost": str(item.cost),
                    "created_at": item.created_at.isoformat()
                }
                yield json.dumps(record)
            yield ']}'

        response = StreamingHttpResponse(
            stream_generator(),
            content_type="application/json"
        )
        response['Content-Disposition'] = 'attachment; filename="shipments_export.json"'
        return response
```

---

### Skenario 2: Race Condition pada Endpoint Transaksi Saldo Dompet Digital
**Konteks Masalah:**  
Sebuah aplikasi e-wallet menyediakan endpoint API `POST /api/v1/wallet/transfer/`. Saat beban sistem tinggi atau ada serangan terdistribusi menggunakan bot concurrency (mengirimkan 10 request transfer dalam milidetik yang sama), saldo user pengirim berkurang tidak konsisten dan user dapat mentransfer uang melebihi saldo yang dimilikinya (double-spending vulnerability).

**Analisis Masalah:**
1. Kode serializer atau view melakukan:
   ```python
   # KODE BERBAHAYA
   wallet = Wallet.objects.get(user=request.user)
   if wallet.balance >= amount:
       wallet.balance -= amount
       wallet.save()
   ```
2. Ketika 10 request tiba bersamaan pada multi-thread/multi-process worker Gunicorn, kesepuluh thread membaca `wallet.balance` yang sama sebelum salah satu thread berhasil melakukan `wallet.save()`.

**Solusi Rekayasa:**
Gunakan isolasi transaksi ACID database dengan pessimistic locking via `select_for_update()` dan atomic transaction block:

```python
from django.db import transaction
from rest_framework import serializers, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Wallet, TransactionLedger

class TransferSerializer(serializers.Serializer):
    recipient_wallet_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)

class SecureWalletTransferView(APIView):
    def post(self, request):
        serializer = TransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        amount = serializer.validated_data['amount']
        recipient_id = serializer.validated_data['recipient_wallet_id']

        # Kunci baris database secara deterministik untuk mencegah deadlocks
        sender_id = request.user.wallet.id
        if sender_id == recipient_id:
            return Response(
                {"error": "Tidak dapat mentransfer ke dompet sendiri."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        ids_to_lock = sorted([sender_id, recipient_id])

        with transaction.atomic():
            # Kunci kedua row dompet secara berurutan sesuai sorted ID
            wallets = {
                w.id: w for w in Wallet.objects.select_for_update().filter(id__in=ids_to_lock)
            }
            
            sender_wallet = wallets.get(sender_id)
            recipient_wallet = wallets.get(recipient_id)

            if not recipient_wallet:
                return Response(
                    {"error": "Dompet penerima tidak ditemukan."}, 
                    status=status.HTTP_404_NOT_FOUND
                )

            if sender_wallet.balance < amount:
                return Response(
                    {"error": "Saldo tidak mencukupi."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Mutasi saldo
            sender_wallet.balance -= amount
            sender_wallet.save(update_fields=['balance', 'updated_at'])

            recipient_wallet.balance += amount
            recipient_wallet.save(update_fields=['balance', 'updated_at'])

            # Catat mutasi ledger
            TransactionLedger.objects.create(
                sender=sender_wallet,
                recipient=recipient_wallet,
                amount=amount,
                status='COMPLETED'
            )

        return Response(
            {"message": "Transfer berhasil.", "new_balance": str(sender_wallet.balance)}, 
            status=status.HTTP_200_OK
        )
```

---

### Skenario 3: Kebocoran Data Multi-Tenant melalui Broken Object Level Authorization (BOLA/IDOR)
**Konteks Masalah:**  
Sebuah aplikasi SaaS B2B memiliki endpoint `GET /api/v1/invoices/<id>/` yang di-handle oleh `ModelViewSet`. Seorang user dari Tenant Alpha (`organization_id = 10`) dapat mengunduh invoice rahasia milik Tenant Beta (`organization_id = 25`) hanya dengan mengganti path parameter ID invoice pada URL (contoh: dari `/invoices/104/` ke `/invoices/105/`). OWASP API Security Top 1 mengkategorikan ini sebagai Broken Object Level Authorization (BOLA).

**Analisis Masalah:**
ViewSet menggunakan implementasi bawaan yang tidak memfilter `queryset` berdasarkan tenant user yang sedang login:
```python
class InvoiceViewSet(viewsets.ModelViewSet):
    # CELAH KEAMANAN KRITIS: Membuka seluruh database ke siapapun yang memiliki token valid
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]
```

**Solusi Rekayasa:**
Terapkan pertahanan berlapis:
1. Batasi queryset global tenant pada `get_queryset()`.
2. Pasang Custom Object-Level Permission (`BasePermission`).

```python
from rest_framework import permissions, viewsets
from .models import Invoice
from .serializers import InvoiceSerializer

class IsInvoiceTenantOwner(permissions.BasePermission):
    """
    Memastikan invoice hanya dapat diakses oleh user yang berada
    dalam organisasi yang sama dengan pembuat invoice.
    """
    def has_object_permission(self, request, view, obj):
        return obj.organization_id == request.user.organization_id

class SecureInvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated, IsInvoiceTenantOwner]

    def get_queryset(self):
        # Defensif 1: Isolasi data pada level query SQL langsung
        user = self.request.user
        if not user.is_authenticated:
            return Invoice.objects.none()
            
        return (
            Invoice.objects
            .filter(organization_id=user.organization_id)
            .select_related('customer', 'organization')
        )

    def perform_create(self, serializer):
        # Pastikan data yang dibuat otomatis terikat pada organisasi user
        serializer.save(
            organization_id=self.request.user.organization_id,
            created_by=self.request.user
        )
```

---

## Bagian 4: Practical Chapter Challenge

### Tantangan: "Sistem Manajemen Inventaris Multi-Gudang dengan Validasi Stok Ketat & Audit Trail"

#### Spesifikasi Proyek:
Anda diminta membangun arsitektur endpoint RESTful API untuk modul transfer stok barang antar gudang (`StockTransfer`) pada sistem enterprise.

#### Persyaratan Fungsional:
1. **Model Relasi:**
   - `Warehouse` (`id`, `name`, `code`, `is_active`)
   - `Product` (`id`, `sku`, `name`, `price`)
   - `WarehouseStock` (`warehouse` [FK], `product` [FK], `quantity`) -> *Unique Together (`warehouse`, `product`)*
   - `StockTransfer` (`id`, `source_warehouse` [FK], `target_warehouse` [FK], `product` [FK], `quantity`, `status` [PENDING, COMPLETED, REJECTED], `requested_by` [FK User], `created_at`)
2. **Acceptance Criteria Endpoint `POST /api/v1/stock-transfers/`:**
   - Payload JSON wajib menyertakan `source_warehouse_id`, `target_warehouse_id`, `product_id`, dan `quantity`.
   - Validasi ketat:
     - `source_warehouse_id` dan `target_warehouse_id` tidak boleh sama.
     - `quantity` harus bilangan bulat positif $> 0$.
     - `source_warehouse` harus memiliki stok `WarehouseStock` yang cukup untuk produk tersebut (`quantity_available >= requested_quantity`).
   - Eksekusi transaksi database atomic:
     - Kurangi stok pada `source_warehouse`.
     - Tambahkan stok pada `target_warehouse` (gunakan `get_or_create` jika record belum ada).
     - Buat record `StockTransfer` dengan status `COMPLETED`.
   - Gunakan serialized output standar HTTP `201 Created`.
   - Response time wajib terlindungi dari race-condition concurrent requests (gunakan row locking).

---

### Solusi Referensi Implementasi:

#### 1. `serializers.py`
```python
from rest_framework import serializers
from .models import StockTransfer, Warehouse, Product, WarehouseStock

class StockTransferCreateSerializer(serializers.Serializer):
    source_warehouse_id = serializers.IntegerField()
    target_warehouse_id = serializers.IntegerField()
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        if attrs['source_warehouse_id'] == attrs['target_warehouse_id']:
            raise serializers.ValidationError({
                "target_warehouse_id": "Gudang tujuan tidak boleh sama dengan gudang asal."
            })
        
        # Validasi eksistensi entitas aktif
        try:
            attrs['source_warehouse'] = Warehouse.objects.get(
                id=attrs['source_warehouse_id'], is_active=True
            )
        except Warehouse.DoesNotExist:
            raise serializers.ValidationError({"source_warehouse_id": "Gudang asal tidak valid atau nonaktif."})

        try:
            attrs['target_warehouse'] = Warehouse.objects.get(
                id=attrs['target_warehouse_id'], is_active=True
            )
        except Warehouse.DoesNotExist:
            raise serializers.ValidationError({"target_warehouse_id": "Gudang tujuan tidak valid atau nonaktif."})

        try:
            attrs['product'] = Product.objects.get(id=attrs['product_id'])
        except Product.DoesNotExist:
            raise serializers.ValidationError({"product_id": "Produk tidak ditemukan."})

        return attrs

class StockTransferDetailSerializer(serializers.ModelSerializer):
    source_warehouse_name = serializers.CharField(source='source_warehouse.name', read_only=True)
    target_warehouse_name = serializers.CharField(source='target_warehouse.name', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)

    class Meta:
        model = StockTransfer
        fields = [
            'id',
            'source_warehouse',
            'source_warehouse_name',
            'target_warehouse',
            'target_warehouse_name',
            'product',
            'product_name',
            'product_sku',
            'quantity',
            'status',
            'created_at',
        ]
```

#### 2. `views.py`
```python
from django.db import transaction
from rest_framework import viewsets, status, mixins
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import StockTransfer, WarehouseStock
from .serializers import StockTransferCreateSerializer, StockTransferDetailSerializer

class StockTransferViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    queryset = StockTransfer.objects.select_related(
        'source_warehouse', 'target_warehouse', 'product', 'requested_by'
    ).all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return StockTransferCreateSerializer
        return StockTransferDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        source_wh = data['source_warehouse']
        target_wh = data['target_warehouse']
        product = data['product']
        transfer_qty = data['quantity']

        with transaction.atomic():
            # 1. Kunci baris stok sumber menggunakan select_for_update
            source_stock = (
                WarehouseStock.objects
                .select_for_update()
                .filter(warehouse=source_wh, product=product)
                .first()
            )

            if not source_stock or source_stock.quantity < transfer_qty:
                return Response(
                    {
                        "error": "Stok tidak mencukupi pada gudang sumber.",
                        "available_quantity": source_stock.quantity if source_stock else 0
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 2. Mutasi stok sumber
            source_stock.quantity -= transfer_qty
            source_stock.save(update_fields=['quantity'])

            # 3. Kunci dan perbarui stok gudang tujuan
            target_stock, _ = (
                WarehouseStock.objects
                .select_for_update()
                .get_or_create(
                    warehouse=target_wh,
                    product=product,
                    defaults={'quantity': 0}
                )
            )
            target_stock.quantity += transfer_qty
            target_stock.save(update_fields=['quantity'])

            # 4. Buat audit record transfer
            transfer_record = StockTransfer.objects.create(
                source_warehouse=source_wh,
                target_warehouse=target_wh,
                product=product,
                quantity=transfer_qty,
                status='COMPLETED',
                requested_by=request.user
            )

        output_serializer = StockTransferDetailSerializer(
            transfer_record, context=self.get_serializer_context()
        )
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
```

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan daftar periksa ini untuk mengevaluasi kesiapan arsitektur API Anda sebelum melangkah ke tahap deployment produksi:

- [ ] **Serializer Performance:** Apakah Anda sudah memastikan tidak ada evaluasi query relasional berulang di dalam property method serializer (`SerializerMethodField` yang memanggil ORM)?
- [ ] **Database Pre-fetching:** Apakah seluruh ViewSet dan APIView sudah menerapkan `select_related` untuk One-to-One / Foreign Key dan `prefetch_related` untuk Many-to-Many / Reverse FK?
- [ ] **Idempotensi & Validasi:** Apakah endpoint mutasi state (PUT, POST, PATCH) sudah menerapkan validasi field-level (`validate_<field>`) dan object-level (`validate`) secara lengkap?
- [ ] **Otorisasi Ketat (Anti-BOLA):** Apakah seluruh query pada `get_queryset()` sudah terisolasi sesuai identitas tenant/user aktif (`request.user`)?
- [ ] **Concurrency & Locking:** Apakah operasi transfer finansial, mutasi inventaris, dan pengurangan kuota sudah dibungkus dalam blok `transaction.atomic()` serta diproteksi dengan `select_for_update()`?
- [ ] **Pagination Scalability:** Apakah tabel dengan jutaan data sudah beralih menggunakan `CursorPagination` untuk menghindari bottleneck `OFFSET` PostgreSQL?
- [ ] **Throttling & Abuse Prevention:** Apakah endpoint publik sensitif (login, register, reset password, OTP) sudah dibatasi dengan `ScopedRateThrottle` atau custom cache-based throttles?
- [ ] **Error Handling Standar:** Apakah payload error format konsisten dan tidak membocorkan stack trace mentah atau kredensial database ke klien luar?
