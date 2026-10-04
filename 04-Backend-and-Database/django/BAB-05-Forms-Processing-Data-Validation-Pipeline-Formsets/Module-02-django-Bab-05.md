# Bab 05: Forms Processing, Data Validation Pipeline & Formsets
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Menguasai lifecycle internal dan *execution flow* dari Django Form validation pipeline (`full_clean`, `_clean_fields`, `clean_<field>`, `_clean_form`, `_post_clean`).
- Mengimplementasikan validasi lintas-field (*cross-field validation*) dan sanitasi tingkat lanjut menggunakan decoupling arsitektur (Services/Validators).
- Mendesain dan mengoperasikan Formsets serta Inline Formsets dinamis untuk relasi one-to-many/composite aggregate di lingkungan produksi.
- Mencegah kerentanan keamanan dan data tampering yang berkaitan dengan `ManagementForm`, manipulated POST payloads, dan CSRF injection.
- Mengoptimalkan performa I/O dan ORM pada mutasi data berbasis Formset menggunakan atomic transactions, bulk operations (`bulk_create`, `bulk_update`), serta concurrency control (Optimistic/Pessimistic Locking).

---

### 2. Prerequisite
- Pemahaman mendalam tentang siklus Request/Response HTTP di Django (WSGI/ASGI handler).
- Penguasaan ORM lanjutan: Transactions (`atomic`), QuerySet optimization (`select_related`, `prefetch_related`), dan Database Constraints.
- Pemahaman tentang Python OOP: Metaclasses, Descriptors, Dynamic Attribute Resolution (`__getattr__`), dan Exceptions context.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Metaclass Construction: `DeclarativeFieldsMetaclass`
Form pada Django bukan sekadar kelas Python standar. Ketika form didefinisikan, `DeclarativeFieldsMetaclass` mengintersepsi definisi kelas:
1. Membaca semua atribut kelas yang mewarisi `django.forms.fields.Field`.
2. Mengekstrak deklarasi field tersebut dan menyimpannya dalam dictionary `base_fields`.
3. Memastikan inheritance hierarchy terjaga sehingga subclass form mewarisi field dari parent form tanpa menduplikasi instansiasi memori secara redundan.
4. Ketika sebuah form diinstansiasi (`Form(data=request.POST)`), form melakukan shallow/deep copy dari `base_fields` ke `self.fields` spesifik untuk instans tersebut. Ini mencegah *state leakage* antar-thread atau antar-request.

#### B. The Validation Pipeline Deep Dive (`is_valid()` Under the Hood)
Pemanggilan `form.is_valid()` merupakan wrapper deterministik terhadap parsing cache internal `form.errors`:

```python
# Sederhananya, alur internal BaseForm:
def is_valid(self):
    return self.is_bound and not self.errors
```

Ketika property `self.errors` diakses pertama kali, Django mengeksekusi `self.full_clean()`. Pipeline ini berjalan dalam 4 tahap sekuensial yang ketat:

```
[Raw HTTP Payload]
       │
       ▼
1. self._clean_fields()
   ├─ Field.clean() -> To Python conversion + Field Validators
   └─ Form.clean_<fieldname>() -> Custom Per-Field Sanitation
       │
       ▼
2. self._clean_form()
   └─ Form.clean() -> Cross-Field / Multi-Field Co-validation
       │
       ▼
3. self._post_clean() (Khusus ModelForm)
   └─ Model.clean() via ModelForm._post_clean()
   └─ Model instance field population & Model validation
       │
       ▼
[Population of self._errors & self.cleaned_data]
```

1. **`_clean_fields()`**:
   - Melakukan iterasi pada setiap key di `self.fields`.
   - Mengambil data mentah via `field.widget.value_from_datadict(self.data, self.files, self.add_prefix(name))`.
   - Menjalankan `field.clean(value)`:
     - Mengubah representasi teks menjadi native Python object (`to_python()`).
     - Memvalidasi nilai kosong jika field memiliki `required=True` (`validate()`).
     - Mengeksekusi list callable validator bawaan/eksternal (`run_validators()`).
   - Jika `field.clean()` sukses, Django mencari method hook bernama `clean_<fieldname>()` pada Form instance. Jika ada, method ini dieksekusi. Return value dari method ini **wajib** berupa nilai yang telah dibersihkan, yang kemudian disimpan ke `self.cleaned_data[name]`.
   - Jika terjadi `ValidationError`, error dimasukkan ke `self._errors[name]` dan key tersebut dihapus dari `self.cleaned_data`.

2. **`_clean_form()`**:
   - Hanya dijalankan jika tidak ada error fatal yang menghentikan eksekusi form secara keseluruhan.
   - Mengeksekusi `Form.clean()`. Di sinilah logika *Cross-Field Validation* dijalankan (misal: membandingkan `password` dan `password_confirm`, atau rentang tanggal `start_date` dan `end_date`).
   - Method ini harus mengembalikan dictionary `cleaned_data` secara utuh. Jika terjadi error di level form (non-field error), dilemparkan `ValidationError` yang ditangkap dan dimasukkan ke dalam `NON_FIELD_ERRORS` (`self._errors['__all__']`).

3. **`_post_clean()` (Spesifik untuk `ModelForm`)**:
   - Mengaitkan field yang lolos validasi ke instance model internal (`self.instance`).
   - Memanggil `self.instance.full_clean(exclude=exclude_list)` untuk mengeksekusi validasi level model (misal: database unique constraints, `unique_together`, validators pada model field).
   - Mengintegrasikan error model ke dalam dictionary `self._errors` milik form.

#### C. Formsets Architecture & State Machine
`BaseFormSet` dan `BaseInlineFormSet` adalah pengelola koleksi form homogen. Arsitekturnya berpusat pada:
- **`ManagementForm`**: Form tersembunyi yang mengontrol state koleksi melalui 4 parameter kunci:
  - `TOTAL_FORMS`: Total form yang dikirim oleh client (eksisting + baru + kosong).
  - `INITIAL_FORMS`: Jumlah form yang berasal dari database/initial data.
  - `MIN_NUM_FORMS`: Batas minimum form valid yang wajib disubmit.
  - `MAX_NUM_FORMS`: Batas maksimum form yang diizinkan untuk mencegah DoS payload memory injection.
- **Prefix Isolation**: Setiap field dalam formset memiliki prefix unik terotomasi, contoh: `form-0-id`, `form-0-quantity`, `form-1-id`, `form-1-quantity`. Ini mencegah collision namespace di dalam single POST body.
- **Formset Validation**: `BaseFormSet.is_valid()` memicu `ManagementForm.is_valid()`. Jika tampering terjadi pada `TOTAL_FORMS` atau form count tidak cocok dengan payload aktual, formset melempar `ValidationError` secara global dan menghentikan pemrosesan form individu.

---

### 4. Why & What

| Dimensi | Native Django Forms & Formsets | DRF Serializers / Pydantic Manual |
| :--- | :--- | :--- |
| **Arsitektur Utama** | Server-Side Rendering (SSR) & Monolithic Clean Pipeline. Mengelola binding state HTML widget dan parsing type secara native. | Data Serialization/Deserialization API murni. Terpisah dari rendering state HTML. |
| **Integrasi ORM** | Native 2-way sync (`ModelForm.save()`, `save_m2m()`, `construct_instance()`). Mencegah bypass validasi constraint database. | Membutuhkan explicit ORM bridge logic atau penanganan nested ORM instance secara manual. |
| **Manajemen State Nested** | Formsets menyediakan state tracking terstruktur via `ManagementForm` out-of-the-box (Add/Delete/Order). | Membutuhkan nested array handling manual atau custom list serializers dengan atomic transactions. |
| **Anti-Corruption Layer** | Mengisolasi data HTTP yang rentan manipulasi sebelum menyentuh entity database/domain model. | Berfungsi sebagai contract API, membutuhkan lapisan service tambahan untuk isolasi form. |

Form validation pipeline di level enterprise bukan sekadar utility parsing; ia bertindak sebagai **Gatekeeper Domain Integrity** pertama yang menyaring, menormalisasi, dan memastikan bahwa payload mutasi memenuhi invariabel bisnis sebelum payload tersebut didelegasikan ke ORM atau Domain Services.

---

### 5. How (Workflow Detail)

Berikut adalah algoritma eksekusi dari input request mentah hingga commit ke persistent storage:

```
[Incoming POST Request]
       │
       ▼
Instantiate Formset/Form with data=request.POST, files=request.FILES
       │
       ▼
Formset.is_valid() ──► Clean ManagementForm
       │                       │
     [Pass]                  [Fail] ──► Raise ValidationError (Tampering)
       │
       ▼
Iterate individual form instances:
   ┌───────────────────────────────────────────────┐
   │ 1. Form.full_clean()                          │
   │    a. Convert to Python via Widget & Field    │
   │    b. Field validators (Regex, Min/Max)       │
   │    c. clean_<field>() execution               │
   │    d. Form.clean() for cross-field integrity  │
   │    e. ModelForm._post_clean() Model validation│
   └───────────────────────────────────────────────┘
       │
       ├─── Apakah ada error di form manapun?
       │        ├─ Ya ──► Rollback, kumpulkan formset.errors, render form dengan error tags
       │        └─ Tidak
       ▼
Formset.clean() (Cross-form validation: total amount checks, uniqueness across forms)
       │
       ├─── Lolos validasi?
       │        ├─ Tidak ──► Raise ValidationError (Non-field formset error)
       │        └─ Ya
       ▼
transaction.atomic() Block:
   1. Iterasi form yang valid
   2. Pisahkan Form: Delete vs Update vs Create
   3. Eksekusi batch database operations (Bulk Insert/Update/Delete)
   4. Eksekusi save_m2m()
       │
       ▼
[Redirect ke Success URL / Render Respon 200 OK]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Lini Perakitan Kontrol Kualitas Industri
Bayangkan sebuah pabrik perakitan mobil (Form Pipeline):
1. **Penerimaan Material Mentah (`request.POST`)**: Kotak suku cadang masuk dari supplier tanpa jaminan standar.
2. **Sensor Individual (`_clean_fields` & `clean_<field>`)**: Setiap baut, ban, dan kabel diperiksa dimensinya. Baut 10mm harus pas 10mm (konversi tipe data). Jika cacat, komponen ditandai reject (`ValidationError`).
3. **Pemeriksaan Kompatibilitas Sistem (`_clean_form` / `clean()`)**: Mesin dan transmisi diperiksa bersamaan. Mesin bensin 2000cc tidak boleh dipasangkan dengan tangki baterai EV (Cross-field validation).
4. **Inspeksi Integritas Struktural Rangka (`_post_clean`)**: Mobil dicek terhadap standar keselamatan tabrakan sasis secara menyeluruh (Model Constraints).
5. **Supervisor Batch (`ManagementForm`)**: Sebelum mobil-mobil dikirim, supervisor menghitung apakah jumlah mobil di trailer persis sama dengan manifest pengiriman. Jika manifest dipalsukan, trailer ditahan seluruhnya.

#### Diagram Arsitektur Internal Lifecycle

```
========================================================================================
                          DJANGO FORM VALIDATION PIPELINE
========================================================================================

             request.POST / request.FILES
                          │
                          ▼
            ┌───────────────────────────┐
            │   BaseForm.__init__()     │ ◄── Clones base_fields to self.fields
            └─────────────┬─────────────┘
                          │
                          ▼
                form.is_valid()
                          │
                          ▼
            ┌───────────────────────────┐
            │     form.full_clean()     │
            └─────────────┬─────────────┘
                          │
        ┌─────────────────┴─────────────────┐
        ▼                                   ▼
 ┌───────────────┐                  ┌───────────────┐
 │ If is_bound=F │                  │ If is_bound=T │
 └──────┬────────┘                  └───────┬───────┘
        │ (Do nothing)                      │
        ▼                                   ▼
   Return False             ┌───────────────────────────────┐
                            │      self._clean_fields()     │
                            └───────────────┬───────────────┘
                                            │
                     ┌──────────────────────┴──────────────────────┐
                     ▼                                             ▼
          ┌─────────────────────┐                       ┌─────────────────────┐
          │    Field.clean()    │                       │  clean_<fieldname>()│
          │ 1. to_python()      │                       │ (Custom Per-Field   │
          │ 2. validate()       │                       │  Sanitization logic)│
          │ 3. run_validators() │                       └──────────┬──────────┘
          └──────────┬──────────┘                                  │
                     │                                             ▼
                     └──────────────────────┬──────────────────────┘
                                            │ (If Valid: update cleaned_data)
                                            ▼
                            ┌───────────────────────────────┐
                            │       self._clean_form()      │
                            │  Executes Form.clean() for    │
                            │  cross-field integrity        │
                            └───────────────┬───────────────┘
                                            │
                                            ▼
                            ┌───────────────────────────────┐
                            │      self._post_clean()       │
                            │ (ModelForm only: Model checks,│
                            │  unique_together constraints) │
                            └───────────────┬───────────────┘
                                            │
                     ┌──────────────────────┴──────────────────────┐
                     ▼                                             ▼
          ┌─────────────────────┐                       ┌─────────────────────┐
          │  self._errors is    │                       │  self._errors is    │
          │      POPULATED      │                       │        EMPTY        │
          └──────────┬──────────┘                       └──────────┬──────────┘
                     │                                             │
                     ▼                                             ▼
               Return False                                   Return True
========================================================================================
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Strict Cross-Field Validation & Sanitasi
Validasi custom field dan kombinasi aturan bisnis (misal: pendaftaran shift kerja).

```python
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import time

class ShiftScheduleForm(forms.Form):
    employee_code = forms.CharField(max_length=10, strip=True)
    start_time = forms.TimeField()
    end_time = forms.TimeField()
    allow_overtime = forms.BooleanField(required=False)

    def clean_employee_code(self) -> str:
        code: str = self.cleaned_data.get('employee_code', '').upper()
        if not code.startswith('EMP-'):
            raise ValidationError(
                "Format kode karyawan harus diawali dengan 'EMP-'.",
                code='invalid_employee_prefix'
            )
        return code

    def clean(self) -> dict:
        cleaned_data = super().clean()
        start: time | None = cleaned_data.get('start_time')
        end: time | None = cleaned_data.get('end_time')
        allow_overtime: bool = cleaned_data.get('allow_overtime', False)

        if start and end:
            if start >= end:
                raise ValidationError(
                    "Jam selesai shift harus lebih besar daripada jam mulai shift.",
                    code='invalid_time_range'
                )
            
            # Hitung selisih jam
            duration_hours = (
                (timezone.datetime.combine(timezone.now().date(), end) - 
                 timezone.datetime.combine(timezone.now().date(), start))
                .total_seconds() / 3600
            )

            if duration_hours > 8 and not allow_overtime:
                self.add_error(
                    'allow_overtime',
                    ValidationError(
                        f"Shift berdurasi {duration_hours:.1f} jam melebihi batas 8 jam. "
                        "Centang 'Izinkan Lembur' untuk melanjutkan.",
                        code='overtime_required'
                    )
                )

        return cleaned_data
```

#### B. Practical Example: Enterprise Production Pattern (Order & OrderItems)
Implementasi ModelForm + Inline Formset dinamis dengan sanitasi mutasi, pengecekan ketersediaan stok, transaksi database terisolasi, dan optimasi query via bulk operations.

##### 1. Model Definition (`models.py`)
```python
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator

class Order(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
    ]
    reference_code = models.CharField(max_length=32, unique=True, db_index=True)
    customer_email = models.EmailField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

class Product(models.Model):
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    stock = models.PositiveIntegerField(default=0)

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='order_items')
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['order', 'product'], name='unique_order_product')
        ]
```

##### 2. Formset & Form Logic (`forms.py`)
```python
from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory, BaseInlineFormSet
from .models import Order, OrderItem, Product

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['reference_code', 'customer_email']

    def clean_reference_code(self) -> str:
        code = self.cleaned_data.get('reference_code', '').strip().upper()
        if len(code) < 6:
            raise ValidationError("Reference code minimal 6 karakter alfanumerik.")
        return code

class OrderItemForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ['product', 'quantity', 'unit_price']

    def clean_quantity(self) -> int:
        quantity = self.cleaned_data.get('quantity')
        if quantity is not None and quantity <= 0:
            raise ValidationError("Kuantitas harus lebih besar dari 0.")
        return quantity

class BaseOrderItemFormSet(BaseInlineFormSet):
    def clean(self) -> None:
        super().clean()
        if any(self.errors):
            # Jika ada error individual field, hentikan validasi cross-form
            return

        products_seen: set[int] = set()
        total_items_count: int = 0

        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get('DELETE', False):
                continue

            product: Product = form.cleaned_data.get('product')
            quantity: int = form.cleaned_data.get('quantity', 0)

            if not product:
                continue

            # Invariabel 1: Validasi duplikasi produk di formset
            if product.id in products_seen:
                form.add_error(
                    'product',
                    ValidationError(
                        "Produk ini telah ditambahkan pada baris lain. "
                        "Gabungkan kuantitas pada satu baris.",
                        code='duplicate_product'
                    )
                )
            products_seen.add(product.id)

            # Invariabel 2: Validasi stok terkini
            if product.stock < quantity:
                form.add_error(
                    'quantity',
                    ValidationError(
                        f"Stok tidak mencukupi. Tersedia: {product.stock}, Diminta: {quantity}.",
                        code='insufficient_stock'
                    )
                )

            total_items_count += quantity

        # Invariabel 3: Batasan bisnis agregat
        if total_items_count > 1000:
            raise ValidationError(
                "Total kuantitas item dalam satu transaksi tidak boleh melebihi 1.000 unit.",
                code='max_order_quantity_exceeded'
            )

        if len(products_seen) == 0:
            raise ValidationError(
                "Minimal satu produk wajib disertakan dalam pesanan.",
                code='empty_order'
            )

OrderItemFormSet = inlineformset_factory(
    parent_model=Order,
    model=OrderItem,
    form=OrderItemForm,
    formset=BaseOrderItemFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)
```

##### 3. Atomic Service Transaction Execution (`services.py` & `views.py`)
```python
from django.db import transaction
from django.shortcuts import render, redirect
from django.http import HttpRequest, HttpResponse
from .forms import OrderForm, OrderItemFormSet
from .models import Order, Product

def process_order_creation_service(order_form: OrderForm, formset: OrderItemFormSet) -> Order:
    """
    Eksekusi penyimpanan Form dan Formset secara atomik dengan row-locking 
    untuk mencegah race condition pengurangan stok.
    """
    with transaction.atomic():
        # 1. Simpan Parent Order
        order: Order = order_form.save()

        # 2. Lock baris produk yang terlibat untuk mencegah race-condition concurrency
        instances = formset.save(commit=False)
        product_ids = [item.product_id for item in instances]
        
        # Ambil dan lock baris produk dengan select_for_update
        locked_products = {
            p.id: p for p in Product.objects.select_for_update().filter(id__in=product_ids)
        }

        # 3. Handle deletions
        for deleted_obj in formset.deleted_objects:
            deleted_obj.delete()

        # 4. Validasi ulang stok dengan locked records & simpan items
        for item in instances:
            locked_prod = locked_products[item.product_id]
            if locked_prod.stock < item.quantity:
                raise ValueError(f"Stok untuk {locked_prod.name} mendadak tidak mencukupi.")
            
            # Kurangi stok
            locked_prod.stock -= item.quantity
            locked_prod.save(update_fields=['stock'])

            item.order = order
            item.save()

        formset.save_m2m()
        return order

def order_create_view(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        order_form = OrderForm(request.POST, prefix='order')
        formset = OrderItemFormSet(request.POST, prefix='items')

        if order_form.is_valid() and formset.is_valid():
            try:
                order = process_order_creation_service(order_form, formset)
                return redirect('order_detail', pk=order.pk)
            except ValueError as e:
                order_form.add_error(None, str(e))
    else:
        order_form = OrderForm(prefix='order')
        formset = OrderItemFormSet(prefix='items')

    return render(request, 'orders/order_form.html', {
        'order_form': order_form,
        'formset': formset
    })
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario Kasus: Portal E-Procurement B2B Global (PT Logistik Global Solusi)
- **Tantangan Arsitektur**: Sistem procurement menerima upload Purchase Order (PO) multi-vendor yang terdiri dari 200–500 line items per order. Setiap item memiliki variasi mata uang, split tax rules, serta validasi dynamic discount hierarkis.
- **Masalah Produksi**:
  1. Penggunaan standard `formset.save()` memicu masalah $N+1$ queries database (500 insert queries terpisah per request).
  2. Ketika 10 user mengunggah item yang menargetkan alokasi vendor quota yang sama secara bersamaan, terjadi race condition (*negative vendor allocation quota*).
  3. POST payload body berukuran masif sering kali terpotong akibat setting batas `DATA_UPLOAD_MAX_NUMBER_FIELDS` Django bawaan (1.000 field), yang menyebabkan silent drop form item.
- **Solusi Rekayasa Terapan**:
  1. **Konfigurasi Parameter Parsing**: Menaikkan batas security field dengan mitigasi DoS via reverse-proxy rate limiting:
     ```python
     DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000
     DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
     ```
  2. **Bulk Ingestion via Formset Parsing**: Formset hanya bertindak sebagai Validation & Transformation Engine. Data tervalidasi diekstrak dari `formset.cleaned_data` dan dieksekusi via `bulk_create` berukuran batch 100:
     ```python
     items_to_create = [
         OrderItem(
             order=order,
             product=form.cleaned_data['product'],
             quantity=form.cleaned_data['quantity'],
             unit_price=form.cleaned_data['unit_price']
         )
         for form in formset.forms
         if form.cleaned_data and not form.cleaned_data.get('DELETE', False)
     ]
     OrderItem.objects.bulk_create(items_to_create, batch_size=100)
     ```
  3. **Concurrency Guard**: Menggunakan PostgreSQL row-level locks (`select_for_update()`) pada level Vendor Allocation record untuk menjamin transaksi serializable selama eksekusi validasi Formset.
- **Hasil**: Latensi checkout menurun dari 4.800ms menjadi 320ms pada 500 lines items per PO, dengan rasio integritas alokasi vendor mencapai 100% tanpa race condition.

---

### 9. Trade-offs

| Parameter | Django Formset Pipeline | Pure REST API (DRF/Ninja) + DB Bulk Service |
| :--- | :--- | :--- |
| **Throughput & Latency** | **Lebih Rendah**. Overhead instansiasi puluhan objek Form Python, parsing field, dan error dictionary mengonsumsi CPU clock yang signifikan. | **Tinggi**. Serializer ringan atau skema validasi Pydantic berbasis C/Rust-core (Pydantic v2) memiliki eksekusi deserialisasi jauh lebih cepat. |
| **Memory Footprint** | **Tinggi**. Setiap baris pada Formset memegang pointer widget, field instances, translation tables, dan error list di RAM selama proses request. | **Rendah**. Memory parsing stream-based/generator murni, memori lekas dibebaskan setelah deserialisasi. |
| **Developer Velocity** | **Sangat Cepat** untuk aplikasi berbasis server-rendered templates (Django templates, HTMX, AlpineJS) tanpa perlu menulis kode sinkronisasi state REST terpisah. | **Moderat**. Membutuhkan sinkronisasi skema frontend, DTO backend, dan orchestration parsing JSON. |
| **Maintenance Cost** | **Rendah**. Ekosistem internal Django menangani CSRF, validasi integritas field models, dan handling context rendering secara serempak. | **Tinggi**. Membutuhkan pengujian integrasi manual untuk memastikan payload validasi API inline dengan database constraints. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Tampering Data `ManagementForm`
* **Gejala**: Melempar exception `django.forms.utils.ValidationError: ['ManagementForm data is missing or has been tampered with']`.
* **Akar Masalah**: Frontend developer merender field custom menggunakan loop tanpa menyertakan `{{ formset.management_form }}` di dalam tag `<form>`, atau form prefix pada formset tidak match dengan POST payload.
* **Solusi**: Pastikan `{{ formset.management_form }}` dirender di dalam form template:
  ```html
  <form method="post">
      {% csrf_token %}
      {{ formset.management_form }}
      {% for form in formset %}
          {{ form.as_p }}
      {% endfor %}
      <button type="submit">Simpan</button>
  </form>
  ```

#### 2. Akses Key pada `cleaned_data` yang Mengalami Kegagalan Validasi
* **Gejala**: `KeyError: 'target_field'` saat dieksekusi di method `clean()`.
* **Akar Masalah**: Jika field gagal di level `Field.clean()` atau `clean_<fieldname>()`, Django otomatis membuang key tersebut dari `self.cleaned_data`.
* **Solusi**: Gunakan defensif `.get()` pattern pada dictionary:
  ```python
  def clean(self):
      cleaned_data = super().clean()
      # JANGAN: field_val = cleaned_data['my_field']
      field_val = cleaned_data.get('my_field')
      if field_val is not None:
          # Proses logika validasi cross-field
          pass
      return cleaned_data
  ```

#### 3. Kehilangan Return Value pada `clean_<fieldname>()` atau `clean()`
* **Gejala**: Field bernilai `None` di database meskipun pengguna mengisi input dengan benar.
* **Akar Masalah**: Engineer lupa menyertakan statement `return cleaned_value` di akhir method `clean_<fieldname>()`.
* **Solusi**: Selalu kembalikan nilai tervalidasi:
  ```python
  def clean_sku(self):
      sku = self.cleaned_data.get('sku')
      if sku:
          sku = sku.strip().upper()
      return sku  # Wajib dikembalikan
  ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Prefixing**: Selalu berikan parameter `prefix` unik saat menginstansiasi Form/Formset jika terdapat multiple forms dalam satu halaman HTML.
- [ ] **Transaction Atomicity**: Bungkus mutasi database dari formset dalam blok `with transaction.atomic():`.
- [ ] **Decouple Complex Validations**: Ekstrak validasi yang mengakses I/O atau external service ke dalam file `validators.py` atau Service Layer khusus, jangan hardcode di view.
- [ ] **Sanitasi Whitespace**: Tambahkan argumen `strip=True` (default pada `forms.CharField`) dan lakukan normalisasi casing di `clean_<field>()`.
- [ ] **Optimistic/Pessimistic Concurrency**: Gunakan `select_for_update()` atau version fields untuk model yang dimutasi serentak oleh banyak pengguna melalui Formset.
- [ ] **Bulk Saving Strategy**: Untuk formset dengan volume baris $> 50$, gunakan `formset.save(commit=False)` diikuti oleh `Model.objects.bulk_create()` dan `Model.objects.bulk_update()`.
- [ ] **Render Hidden PKs**: Pastikan formset loop merender hidden input untuk Primary Key (PK) agar Django mengidentifikasi baris update vs insert: `{{ form.id }}`.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

#### Struktur Direktori
```text
hands-on/m02/
├── manage.py
├── core/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── billing/
    ├── __init__.py
    ├── models.py
    ├── forms.py
    ├── views.py
    ├── urls.py
    └── templates/
        └── billing/
            └── invoice_form.html
```

#### Langkah 1: Setup Models (`billing/models.py`)
```python
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator

class Invoice(models.Model):
    invoice_number = models.CharField(max_length=50, unique=True)
    recipient_name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.invoice_number} - {self.recipient_name}"

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    rate = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])

    @property
    def subtotal(self) -> Decimal:
        return Decimal(self.quantity) * self.rate
```

#### Langkah 2: Setup Forms & Formsets (`billing/forms.py`)
```python
from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory, BaseInlineFormSet
from .models import Invoice, InvoiceItem

class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['invoice_number', 'recipient_name']

    def clean_invoice_number(self) -> str:
        inv_num = self.cleaned_data.get('invoice_number', '').strip().upper()
        if not inv_num.startswith('INV-'):
            raise ValidationError("Nomor invoice harus diawali dengan 'INV-'.")
        return inv_num

class BaseInvoiceItemFormSet(BaseInlineFormSet):
    def clean(self) -> None:
        super().clean()
        if any(self.errors):
            return

        total_invoice_amount = Decimal('0.00')
        valid_items_count = 0

        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get('DELETE', False):
                continue

            qty = form.cleaned_data.get('quantity', 0)
            rate = form.cleaned_data.get('rate', Decimal('0.00'))
            total_invoice_amount += Decimal(qty) * rate
            valid_items_count += 1

        if valid_items_count == 0:
            raise ValidationError("Minimal harus ada satu item dalam invoice.")

        if total_invoice_amount > Decimal('50000000.00'):
            raise ValidationError("Nilai total invoice tidak boleh melampaui Rp 50.000.000,00.")

InvoiceItemFormSet = inlineformset_factory(
    parent_model=Invoice,
    model=InvoiceItem,
    fields=['description', 'quantity', 'rate'],
    formset=BaseInvoiceItemFormSet,
    extra=2,
    can_delete=True
)
```

#### Langkah 3: Setup View (`billing/views.py`)
```python
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from .models import Invoice
from .forms import InvoiceForm, InvoiceItemFormSet

def manage_invoice_view(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    invoice = get_object_or_404(Invoice, pk=pk) if pk else None

    if request.method == 'POST':
        form = InvoiceForm(request.POST, instance=invoice, prefix='inv')
        formset = InvoiceItemFormSet(request.POST, instance=invoice, prefix='items')

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                saved_invoice = form.save()
                formset.instance = saved_invoice
                formset.save()
            return redirect('billing:invoice_success', pk=saved_invoice.pk)
    else:
        form = InvoiceForm(instance=invoice, prefix='inv')
        formset = InvoiceItemFormSet(instance=invoice, prefix='items')

    return render(request, 'billing/invoice_form.html', {
        'form': form,
        'formset': formset,
        'invoice': invoice
    })

def invoice_success_view(request: HttpRequest, pk: int) -> HttpResponse:
    invoice = get_object_or_404(Invoice, pk=pk)
    return HttpResponse(f"Invoice {invoice.invoice_number} berhasil disimpan dengan {invoice.items.count()} items.")
```

#### Langkah 4: Template Implementation (`billing/templates/billing/invoice_form.html`)
```html
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <title>Enterprise Invoice Manager</title>
    <style>
        .error { color: #dc3545; font-size: 0.875rem; }
        .form-row { margin-bottom: 1rem; border-bottom: 1px solid #ccc; padding-bottom: 0.5rem; }
    </style>
</head>
<body>
    <h1>{% if invoice %}Edit{% else %}Buat{% endif %} Invoice</h1>
    
    <form method="post">
        {% csrf_token %}
        
        <fieldset>
            <legend>Informasi Utama</legend>
            {{ form.non_field_errors }}
            <div>
                {{ form.invoice_number.label_tag }}
                {{ form.invoice_number }}
                {{ form.invoice_number.errors }}
            </div>
            <div>
                {{ form.recipient_name.label_tag }}
                {{ form.recipient_name }}
                {{ form.recipient_name.errors }}
            </div>
        </fieldset>

        <fieldset>
            <legend>Line Items</legend>
            {{ formset.management_form }}
            {{ formset.non_form_errors }}

            {% for item_form in formset %}
                <div class="form-row">
                    {{ item_form.id }}
                    {{ item_form.non_field_errors }}
                    
                    <span>Deskripsi:</span> {{ item_form.description }}
                    <span>Qty:</span> {{ item_form.quantity }}
                    <span>Rate:</span> {{ item_form.rate }}
                    
                    {% if formset.can_delete and item_form.instance.pk %}
                        <span>Hapus:</span> {{ item_form.DELETE }}
                    {% endif %}

                    {{ item_form.description.errors }}
                    {{ item_form.quantity.errors }}
                    {{ item_form.rate.errors }}
                </div>
            {% endfor %}
        </fieldset>

        <button type="submit" style="margin-top: 1rem;">Simpan Transaksi</button>
    </form>
</body>
</html>
```

---

### 13. Exercise

#### Level Easy
Buat sebuah `ProfileForm` berbasis `ModelForm` dengan field `birth_date`. Implementasikan method `clean_birth_date()` yang melempar `ValidationError` jika tanggal lahir yang dimasukkan berada di masa depan atau usia kurang dari 13 tahun dari tanggal hari ini.
- **Kriteria Penerimaan**: Menggunakan `django.utils.timezone.now().date()`, melempar error code `underage_user` atau `future_date`.

#### Level Medium
Buat sebuah inline formset untuk model `HotelReservation` dan `GuestDetail`.
- **Kriteria Penerimaan**:
  - Validasi bahwa setidaknya ada 1 tamu yang berstatus `is_primary=True`.
  - Validasi cross-form: Lempar `ValidationError` jika terdapat dua tamu yang memiliki nomor identitas (`id_card_number`) yang sama dalam reservasi yang sama.
  - Formset harus membatasi maksimal 4 tamu per reservasi.

#### Level Hard
Rancang dynamic Formset pipeline untuk sistem inventory transfer antar-gudang (`WarehouseTransfer` dan `TransferItem`).
- **Kriteria Penerimaan**:
  - Gunakan `select_for_update()` untuk memvalidasi stok di gudang asal secara akurat.
  - Implementasikan optimasi database mutasi dengan `bulk_update` untuk pengurangan stok di gudang sumber dan penambahan stok di gudang tujuan.
  - Jika salah satu item gagal validasi stok saat locking, batalkan transaksi dan lempar error yang diarahkan ke field `quantity` dari form item yang bermasalah.

---

### 14. Challenge

**Skenario**: Anda memimpin tim rekayasa finansial di sebuah bank digital. Sistem sedang mengalami anomali saat memproses formset *Multi-Party Split Payment Settlement*. 
- Di bawah kondisi beban tinggi (1.200 request settlement per detik), ditemukan anomali pembulatan matematis di mana jumlah total alokasi desimal split-payment dari baris-baris formset (`AllocationItem`) tidak identik dengan nominal transaksi master (`MasterSettlement`).
- Pengguna nakal mampu mengeksploitasi race condition via tampering `ManagementForm` (mengurangi `TOTAL_FORMS`) sambil tetap menyuntikkan payload child via raw post data yang tidak terikat validasi formset.

**Tugas Arsitektur**:
1. Buat arsitektur formset custom yang mengimplementasikan **Zero-Tolerance Cent-Precision Verification** menggunakan Python `Decimal` (`quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)`).
2. Terapkan mekanisme kriptografis HMAC signature pada field metadata `ManagementForm` untuk memvalidasi bahwa payload yang dikirim dari browser tidak mengalami *parameter pollution* atau pengurangan baris form secara ilegal.
3. Rancang mekanisme recovery rollback secara otomatis tanpa meninggalkan *dangling uncommitted records* di database engine PostgreSQL.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Basic Questions
1. Pada urutan eksekusi manakah `clean_<fieldname>()` dijalankan dalam validation pipeline Django Form?
   - **Jawaban**: Dijalankan di dalam method `_clean_fields()` segera setelah konversi data bawaan field (`Field.clean()`) dan validator individual field berhasil dieksekusi tanpa error.
2. Apa fungsi fundamental dari `ManagementForm` dalam sebuah Django Formset?
   - **Jawaban**: Menyimpan metadata penting (`TOTAL_FORMS`, `INITIAL_FORMS`, `MIN_NUM_FORMS`, `MAX_NUM_FORMS`) untuk memetakan, mengontrol batasan jumlah, dan mengisolasi namespace form saat parsing POST payload.
3. Mengapa sebuah method `clean_<fieldname>()` harus selalu mengembalikan nilai (`return value`)?
   - **Jawaban**: Karena Django mengganti data mentah di dictionary `cleaned_data[fieldname]` dengan nilai kembalian eksplisit dari method tersebut. Jika lupa mengembalikan nilai, key field tersebut akan bernilai `None`.
4. Kapan method `_post_clean()` dieksekusi dan kelas apa yang mengimplementasikannya?
   - **Jawaban**: Dieksekusi setelah `_clean_fields()` dan `_clean_form()`. Didefinisikan secara khusus pada kelas `ModelForm` untuk sinkronisasi nilai ke model instance dan menjalankan validasi model (`Model.full_clean()`).
5. Apa perbedaan mendasar antara `form.errors` dan `form.non_field_errors()`?
   - **Jawaban**: `form.errors` mengembalikan dictionary seluruh error (baik per-field maupun global), sedangkan `form.non_field_errors()` hanya mengembalikan list error tingkat form/global yang diasosiasikan dengan key `'__all__'`.

#### B. Intermediate Questions
1. Mengapa memodifikasi `self.cleaned_data` di dalam `Form.clean()` tidak membatalkan eksekusi jika terjadi `ValidationError` yang dilempar sebelumnya pada `clean_<fieldname>()`?
   - **Jawaban**: Karena field yang gagal pada `clean_<fieldname>()` telah dihapus dari `cleaned_data` dan dicatat ke `self._errors`. Pemanggilan `Form.clean()` tetap berjalan untuk mengevaluasi field lain yang tersisa, kecuali jika view memutus alur eksekusi berdasarkan flag error.
2. Bagaimana cara kerja internal `formset.save(commit=False)` saat memproses foreign key parent model yang belum tersimpan di database?
   - **Jawaban**: `save(commit=False)` menginstansiasi objek model anak tanpa memicu query INSERT ke DB. Foreign key ke parent belum diisi jika parent belum memiliki PK, sehingga developer harus mengisinya secara manual (`child.parent = saved_parent`) sebelum melakukan `child.save()`.
3. Mengapa operasi penghapusan item pada Formset (`can_delete=True`) tidak mengeksekusi method `clean()` dari individual form yang ditandai untuk dihapus?
   - **Jawaban**: Karena Django Formset mendeteksi nilai checkbox `DELETE` pada step awal validasi form. Form yang ditandai dihapus diabaikan dari validasi data wajib dan field validation untuk mencegah error yang tidak relevan bagi data yang akan dibuang.
4. Apa potensi bahaya keamanan dari tidak menyetel `MAX_NUM_FORMS` secara eksplisit pada publik endpoint Formset?
   - **Jawaban**: Potensi serangan DoS (Denial of Service) via *HashDOS* atau *Memory Exhaustion*. Penyerang dapat mengirimkan ribuan baris form dalam satu POST payload besar yang memaksa CPU server menginstansiasi ribuan objek Form Python secara bersamaan hingga server crash (OOM).
5. Bagaimana cara menyuntikkan parameter konteks dinamis (misal: user yang sedang login) ke dalam Form individual yang berada di dalam sebuah Inline Formset?
   - **Jawaban**: Melalui overriding constructor `__init__` pada custom form, dan mengoper parameter tersebut dari BaseFormSet via custom method `get_form_kwargs(self, index)`.

#### C. Skenario Kasus Produksi
1. **Skenario 1**: Sebuah tim engineering mendapati bahwa unit testing mereka pada `MyForm.is_valid()` selalu mengembalikan `True`, padahal data input yang dikirim salah. Setelah diinspeksi, ternyata view mereka memanggil `form.full_clean()` secara manual sebelum memanggil `if form.is_valid():`. Jelaskan anomali internal yang terjadi!
   - **Analisis & Solusi**: Pemanggilan `full_clean()` secara manual membersihkan dan mengisi `self._errors`. Namun, jika pengujian melakukan manipulasi terhadap state form atau menggunakan mock yang me-reset status `is_bound` atau salah mereset attribute `_errors`, pengecekan `is_valid()` dapat terganggu. Yang lebih umum: jika form tidak diberikan data binding (`data=None`), form berstatus unbound (`is_bound=False`), sehingga `is_valid()` selalu mengembalikan `False`. Jika test me-mock `errors` menjadi kosong secara eksplisit, kondisi `not self.errors` mengevaluasi ke `True`.
2. **Skenario 2**: Pada sistem e-commerce berskala besar, pengguna melaporkan error intermiten `IntegrityError (UNIQUE constraint failed: order_item.order_id, order_item.product_id)` saat mengklik tombol submit berkali-kali secara cepat pada checkout formset. Bagaimana arsitektur validasi dan storage layer harus diperbaiki?
   - **Analisis & Solusi**: Error ini terjadi akibat double-submission request yang menembus validasi `is_valid()` secara simultan sebelum transaksi pertama di-commit (Race Condition). Perbaikan: (1) Pasang Idempotency-Key header berbasis token unik per submission di Redis/Cache. (2) Gunakan database-level lock atau locking row parent `Order` via `select_for_update()`. (3) Gunakan database upsert pattern (`bulk_create` dengan `update_conflicts=True` atau `on_conflict_do_update`).
3. **Skenario 3**: Sebuah formset dengan 300 form items memerlukan validasi apakah masing-masing SKU yang dimasukkan pengguna terdaftar di microservice Warehouse eksternal via REST API. Jika divalidasi per-form di method `clean_sku()`, waktu respon mencapai 45 detik (300 HTTP round-trips). Bagaimana mendesain ulang alur validasi Formset agar selesai di bawah 1 detik?
   - **Analisis & Solusi**: Hindari validasi I/O di dalam method `clean_sku()` individu ($N$ call network latency). Pindahkan validasi ke method `BaseFormSet.clean()`. Ekstrak seluruh SKU unik dari semua sub-form yang valid: `sku_set = {f.cleaned_data['sku'] for f in self.forms if ...}`. Lakukan single batch HTTP POST request ke microservice (`/api/v1/skus/batch-validate/`) mengirimkan seluruh array SKU sekaligus. Setelah respon diterima, petakan hasilnya kembali ke masing-masing form menggunakan `form.add_error('sku', ...)` jika ada SKU yang invalid. Ini mereduksi 300 network calls menjadi 1 single round-trip.

---

### 16. Summary
- **Validation Pipeline Mechanics**: Validasi Django Form adalah proses multi-tahap deterministik yang bergerak dari widget level, konversi tipe data (`to_python`), field validation (`validate` & `run_validators`), sanitasi spesifik field (`clean_<fieldname>`), validasi silang model (`Form.clean`), hingga persistensi integrasi constraint model (`_post_clean`).
- **State Integrity via ManagementForm**: Formset mengelola state kumpulan form homogen melalui namespace prefixing dan token kontrol `ManagementForm`. Keamanan data formset bergantung pada validasi jumlah form untuk mencegah manipulasi struktur array data dari sisi client.
- **Enterprise-Grade Data Mutex**: Pada lingkungan dengan konkurensi dan volume data tinggi, Django Formset harus dikombinasikan dengan Database Transactions (`transaction.atomic`), row-locking (`select_for_update`), dan bulk execution (`bulk_create`/`bulk_update`) guna mencegah masalah performa $N+1$ queries dan anomali race condition.