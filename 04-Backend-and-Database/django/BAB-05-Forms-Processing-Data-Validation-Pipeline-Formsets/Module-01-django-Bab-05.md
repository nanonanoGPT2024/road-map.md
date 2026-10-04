# Kurikulum Django: Forms Processing, Data Validation Pipeline, & Formsets

---

## Seksi 01: Identitas Modul
* **Kategori:** 04-Backend-and-Database
* **Topik:** Django Web Framework
* **Bab:** 05
* **Module:** 01
* **Judul Modul:** Forms Processing, Data Validation Pipeline, & Formsets
* **Tingkat Kesulitan:** Advanced / Production-Grade
* **Prasyarat:** Django Models (ORM), Class-Based Views (CBV), Python OOP, HTTP Protocol (POST/GET/CSRF).

---

## Seksi 02: Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
1. Membedah siklus hidup *data cleaning* dan validasi pada Django Forms (`to_python`, `validate`, `run_validators`, `clean_<field>`, `clean`).
2. Mengimplementasikan validasi multi-field yang kompleks dan dependensi state data database pada level form.
3. Membangun abstraksi form dinamis menggunakan `BaseFormSet`, `modelformset_factory`, dan `inlineformset_factory`.
4. Mencegah kerentanan keamanan web seperti Cross-Site Request Forgery (CSRF), Mass Assignment, dan Dynamic Formset Tampering.
5. Menulis unit tests komprehensif untuk formsets, validation pipeline, dan custom field validators.

---

## Seksi 03: Concept Map Diagram ASCII
```
+-------------------------------------------------------------------------------+
|                       DJANGO FORM VALIDATION PIPELINE                         |
+-------------------------------------------------------------------------------+
                                      |
                               [ POST Request ]
                                      |
                                      v
                        +---------------------------+
                        | Form Instantiation        |
                        | Form(data=request.POST,   |
                        |      files=request.FILES) |
                        +---------------------------+
                                      |
                                      v
                        +---------------------------+
                        | form.is_valid() Dipanggil |
                        +---------------------------+
                                      |
                                      v
                        +---------------------------+
                        | form.errors Property      |
                        | Memanggil form.full_clean |
                        +---------------------------+
                                      |
         +----------------------------+----------------------------+
         |                                                         |
         v                                                         v
+------------------+                                      +------------------+
| Field Validation |                                      | Form Validation  |
| (_clean_fields)  |                                      | (_clean_form)    |
+------------------+                                      +------------------+
         |                                                         ^
         +---> 1. Field.to_python()                                |
         |     (Casting tipe data dasar)                           |
         |                                                         |
         +---> 2. Field.validate()                                 |
         |     (Pemeriksaan required/empty)                        |
         |                                                         |
         +---> 3. Field.run_validators()                           |
         |     (Regex, Min/Max, Custom validators)                 |
         |                                                         |
         +---> 4. Form.clean_<fieldname>()                         |
               (Validasi spesifik field & ORM check)               |
               (Menghasilkan cleaned_data[field])                  |
                                                                   |
                               +-----------------------------------+
                               |
                               v
               +--------------------------------+
               | Form.clean()                   |
               | (Cross-field validation logic) |
               +--------------------------------+
                               |
                               v
               +--------------------------------+
               | Post-Clean (_post_clean)       |
               | (ModelForm instance generation)|
               +--------------------------------+
                               |
        +----------------------+----------------------+
        |                                             |
   [Errors Ada?]                                 [Errors Kosong?]
        |                                             |
        v                                             v
+-----------------------+                    +------------------+
| form.errors Populated |                    | cleaned_data Siap|
| Return False          |                    | Return True      |
+-----------------------+                    +------------------+
```

---

## Seksi 04: Mengapa Relevan
Form engine Django bukan sekadar generator HTML `<form>`, melainkan subsistem *data-cleansing* dan *defensive boundary* untuk backend. Model validation saja tidak cukup untuk menangani interaksi pengguna yang dinamis, logika kondisional berbasis konteks request, otorisasi field, atau manipulasi batch data hierarkis (seperti Invoice Header dan Invoice Items). 

Penguasaan mendalam atas validation pipeline dan formset engine memungkinkan arsitektur aplikasi yang bersih: memisahkan protokol parsing transport HTTP dari business layer, mencegah eksploitasi parameter tampering, dan menyederhanakan mutasi transaksi database multi-tabel atomik.

---

## Seksi 05: Anatomi Konsep Inti

### 1. The Validation Execution Order
Proses validasi dijalankan saat `form.is_valid()` atau `form.errors` diakses:
* **`Field.to_python(value)`:** Mengubah string HTTP mentah menjadi tipe data Python primitif/kompleks (misal: ISO string menjadi `datetime.date`).
* **`Field.validate(value)`:** Memvalidasi constraint dasar spesifik field (misal: mengecek apakah nilai kosong diperbolehkan melalui `required=True`).
* **`Field.run_validators(value)`:** Mengeksekusi list `validators` yang didefinisikan pada deklarasi field.
* **`Form.clean_<fieldname>()`:** Metode custom pada subclass form untuk memvalidasi atribut spesifik setelah dikonversi ke tipe Python. Output harus selalu dikembalikan via `return value`.
* **`Form.clean()`:** Validasi tingkat form untuk membandingkan dependensi antar field (misal: `password` vs `password_confirmation`, atau `start_date` vs `end_date`). Mengembalikan dictionary `cleaned_data`.

### 2. Formsets Architecture
Formset adalah lapisan abstraksi di atas beberapa instance form. 
* **`management_form`:** Menyimpan metadata kritis berupa input tersembunyi:
  * `TOTAL_FORMS`: Jumlah form yang dikirim oleh client.
  * `INITIAL_FORMS`: Jumlah form yang sudah ada di database/initial state.
  * `MIN_NUM_FORMS` & `MAX_NUM_FORMS`: Batasan jumlah form yang valid.
* **`BaseFormSet`:** Digunakan untuk form standar non-model.
* **`BaseModelFormSet` & `BaseInlineFormSet`:** Menangani siklus query ORM, sinkronisasi relasi foreign key, dan auto-deletion via field boolean `DELETE`.

---

## Seksi 06: Panduan Implementasi Step-by-Step

### Step 1: Definisikan Custom Validator
Buat callable reusable yang melempar `django.core.exceptions.ValidationError` dengan error code.

### Step 2: Implementasi Custom ModelForm dengan Sanitasi Field
Definisikan field-level clean (`clean_fieldname`) dan multi-field clean (`clean`).

### Step 3: Implementasi Custom Inline FormSet Factory
Konfigurasikan formset untuk menangani relasi Parent-Child (1-to-N) dengan verifikasi keamanan jumlah form.

### Step 4: Integrasi Database Transaction Atomic
Bungkus proses validasi dan penyimpanan formset ke dalam `transaction.atomic()` untuk memastikan integritas data (ACID).

---

## Seksi 07: Contoh Kasus Sederhana

Validasi Form Registrasi Pengguna Sederhana:

```python
# forms.py
from django import forms
from django.core.exceptions import ValidationError

class SimpleRegistrationForm(forms.Form):
    username = forms.CharField(max_length=50, min_length=4)
    email = forms.EmailField()
    age = forms.IntegerField(min_value=18)

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if "admin" in username.lower():
            raise ValidationError(
                "Username tidak boleh mengandung kata 'admin'.",
                code="invalid_username"
            )
        return username
```

---

## Seksi 08: Implementasi Production-Grade Lengkap Kode

Kasus: **Sistem Order Processing & Multi-Item Line Items (Inline Formset) dengan Validasi Stok dan Limit Kredit.**

### 1. Models Layer (`orders/models.py`)
```python
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator

class Customer(models.Model):
    name = models.CharField(max_length=255)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return self.name

class Product(models.Model):
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    stock = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.name} (Stock: {self.stock})"

class Order(models.Model):
    STATUS_CHOICES = (
        ('DRAFT', 'Draft'),
        ('CONFIRMED', 'Confirmed'),
    )
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='orders')
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['order', 'product'], name='unique_order_product')
        ]
```

### 2. Forms and Formset Engine Layer (`orders/forms.py`)
```python
from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory, BaseInlineFormSet
from .models import Order, OrderItem, Product

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['customer', 'status']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer'].empty_label = "Pilih Customer"

class BaseOrderItemFormSet(BaseInlineFormSet):
    """
    Custom FormSet untuk memvalidasi business rules level kolektif (Aggregates):
    1. Duplikasi produk dalam baris formset yang berbeda.
    2. Ketersediaan stok fisik real-time.
    3. Pengecekan limit kredit customer terhadap total kalkulasi formset.
    """
    def clean(self):
        super().clean()
        
        # Hentikan jika ada form individual yang sudah mengandung error sintaksis/tipe data
        if any(self.errors):
            return

        products_seen = set()
        total_order_cost = Decimal('0.00')

        for form in self.forms:
            # Lewati form kosong yang tidak diisi atau form yang ditandai untuk dihapus (DELETE)
            if not form.cleaned_data or form.cleaned_data.get('DELETE', False):
                continue

            product = form.cleaned_data.get('product')
            quantity = form.cleaned_data.get('quantity')
            
            if not product or not quantity:
                continue

            # Rule 1: Mencegah duplikasi produk di payload
            if product.id in products_seen:
                form.add_error('product', ValidationError("Produk ini sudah dipilih di baris lain.", code='duplicate_product'))
            products_seen.add(product.id)

            # Rule 2: Validasi stok fisik
            if quantity > product.stock:
                form.add_error('quantity', ValidationError(
                    f"Stok tidak mencukupi. Tersedia: {product.stock}, Diminta: {quantity}",
                    code='insufficient_stock'
                ))

            # Auto-assign harga unit saat validasi untuk konsistensi database
            unit_price = product.price
            form.cleaned_data['unit_price'] = unit_price
            total_order_cost += (unit_price * quantity)

        # Rule 3: Validasi limit kredit customer
        customer = None
        if hasattr(self, 'instance') and self.instance.customer_id:
            customer = self.instance.customer
        elif self.data.get('customer'):
            # Fallback jika form parent belum tersimpan
            from .models import Customer
            try:
                customer = Customer.objects.get(pk=self.data.get('customer'))
            except (Customer.DoesNotExist, ValueError):
                customer = None

        if customer and total_order_cost > customer.credit_limit:
            raise ValidationError(
                f"Total transaksi (Rp {total_order_cost:,.2f}) melebihi limit kredit customer (Rp {customer.credit_limit:,.2f}).",
                code='credit_limit_exceeded'
            )

OrderItemFormSet = inlineformset_factory(
    parent_model=Order,
    model=OrderItem,
    fields=['product', 'quantity'],
    formset=BaseOrderItemFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)
```

### 3. Controller Layer (`orders/views.py`)
```python
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.db import transaction
from django.contrib import messages
from .models import Order
from .forms import OrderForm, OrderItemFormSet

class OrderCreateUpdateView(View):
    template_name = 'orders/order_form.html'

    def get_object(self, pk=None):
        if pk:
            return get_object_or_404(Order, pk=pk)
        return Order()

    def get(self, request, pk=None):
        order = self.get_object(pk)
        form = OrderForm(instance=order)
        formset = OrderItemFormSet(instance=order)
        return render(request, self.template_name, {'form': form, 'formset': formset, 'order': order})

    def post(self, request, pk=None):
        order = self.get_object(pk)
        form = OrderForm(request.POST, instance=order)
        formset = OrderItemFormSet(request.POST, instance=order)

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    # Simpan parent object
                    saved_order = form.save(commit=False)
                    saved_order.save()
                    
                    # Hubungkan formset dengan parent instance
                    formset.instance = saved_order
                    
                    # Simpan children formset instances
                    items = formset.save(commit=False)
                    total_amount = 0
                    
                    for item in items:
                        # Re-assign unit price dari referensi product terupdate
                        item.unit_price = item.product.price
                        item.save()
                        total_amount += (item.unit_price * item.quantity)
                    
                    # Tangani objek yang dihapus via checkbox can_delete
                    for obj in formset.deleted_objects:
                        obj.delete()
                    
                    # Update agregat parent
                    saved_order.total_amount = total_amount
                    saved_order.save(update_fields=['total_amount'])

                messages.success(request, "Order berhasil disimpan secara konsisten.")
                return redirect('order_detail', pk=saved_order.pk)

            except Exception as e:
                messages.error(request, f"Gagal memproses transaksi: {str(e)}")
        
        return render(request, self.template_name, {'form': form, 'formset': formset, 'order': order})
```

---

## Seksi 09: Diagram Alur Kerja ASCII

```
[ Client Submit POST Formset ]
             |
             v
[ Management Form Validation ]
  - TOTAL_FORMS Tampering Check
  - INITIAL_FORMS Integrity Check
             |
             +---> [ Gagal ] -> Raise ValidationError("ManagementForm tampered")
             |
             v [ Berhasil ]
[ Iterate Sub-Forms Validation ]
  - Loop setiap form di formset:
    - Run Field Validations (product, quantity)
    - Run Form-level Clean
             |
             +---> [ Ada Error Field? ] -> Append to formset.errors
             |
             v [ Lolos ]
[ Execute BaseFormSet.clean() ]
  - Cross-form Validation (Duplicate check)
  - Business Aggregate Rules (Credit limit vs Total price)
  - Real-time DB Checks (Physical Stock Availability)
             |
             +---> [ Gagal ] -> Raise Non-Field ValidationError
             |
             v [ Berhasil ]
[ Execute views.py Logic ]
  - Open DB Transaction (Atomic)
  - form.save() (Parent)
  - formset.save() (Children)
  - Commit DB Transaction
```

---

## Seksi 10: Analisis Trade-offs

| Pendekatan | Keuntungan | Kerugian | Skenario Penggunaan Terbaik |
|---|---|---|---|
| **Form/Formset Validation Layer** | Memisahkan context HTTP dengan database; Error mapping langsung ke UI; Menangani nested state dinamis. | Memerlukan mapping ganda jika model sudah memiliki constraint spesifik. | Web interfaces dengan formulir dinamis & complex user feedback. |
| **Model Validation (`Model.clean()`)** | DRY; Dieksekusi otomatis di Django Admin dan shared views. | Tidak menyadari context request (e.g., Session data, current logged-in user); Parsing nested inline sulit. | Validasi data domain murni yang mutlak berlaku di seluruh entry point sistem. |
| **Database Constraints (Check/Unique)** | Integritas absolut di level storage engine; Terlindungi dari race conditions. | Pesan error sulit di-*parse* menjadi form visual yang user-friendly; Kurang fleksibel untuk logic kompleks. | Validasi integritas tingkat akhir (Hard Safety Guard). |

---

## Seksi 11: Best Practices & Antipatterns

### Best Practices
* **Manfaatkan `add_error(field, error)`:** Gunakan method ini di dalam `clean()` untuk mengikat error langsung ke input field spesifik, bukan menjadikannya generic non-field error.
* **Selalu Validasi Ulang di Transaction Block:** Periksa stok atau status finansial di dalam `transaction.atomic()` bersamaan dengan `select_for_update()` jika beban konkuensi tinggi.
* **Gunakan `form.has_changed()`:** Menghemat operasi database I/O saat update data parsial.

### Antipatterns
* **Direct Database Mutation di `clean()`:** Melakukan `item.save()` di dalam metode validasi `clean()` atau `clean_<field>()`. Validasi hanya boleh membaca state dan melempar exception, bukan menghasilkan side-effects.
* **Mengabaikan Management Form:** Menghapus atau tidak me-render `formset.management_form` di template HTML, yang menyebabkan Django gagal mengenali ukuran batch array data yang dikirim.
* **Menghilangkan `return cleaned_data`:** Lupa mengembalikan nilai field pada `clean_<field>` atau dictionary pada `clean()`, menyebabkan data field terkait menjadi `None`.

---

## Seksi 12: Security Hardening

```
                +------------------------------------+
                |  ATTACK VECTOR: FORM MANIPULATION  |
                +------------------------------------+
                   |                              |
                   v                              v
    +------------------------------+   +------------------------------+
    | 1. Management Form Tampering |   | 2. CSRF Token Injection      |
    +------------------------------+   +------------------------------+
    | Attacker memanipulasi        |   | Eksploitasi session state    |
    | TOTAL_FORMS untuk memicu     |   | tanpa verifikasi token unik. |
    | Denial of Service (DoS) Loop |   +------------------------------+
    +------------------------------+                  |
                   |                                  v
                   v                   +------------------------------+
    +------------------------------+   | Mitigasi: Strict Middleware  |
    | Mitigasi: Set Hard Limits    |   | {% csrf_token %} Enforcement |
    | FormSet(max_num=50)          |   +------------------------------+
    +------------------------------+
```

1. **Mass Assignment Prevention:** Hindari mendefinisikan `fields = '__all__'` di `ModelForm`. Selalu deklarasikan list field eksplisit (whitelist) untuk mencegah injeksi field terproteksi (seperti `is_staff`, `role`, `balance`).
2. **Dynamic Formset Size DoS Protection:** Django membatasi alokasi memori form via parameter internal `DATA_UPLOAD_MAX_NUMBER_FIELDS` (default: 1000). Pasang `max_num` eksplisit pada `inlineformset_factory` untuk mencegah alokasi form tak terbatas dari client payload yang dimanipulasi.
3. **Cross-Site Request Forgery (CSRF):** Pastikan middleware `django.middleware.csrf.CsrfViewMiddleware` aktif dan deklarasikan tag `{% csrf_token %}` di dalam setiap tag `<form method="post">`.

---

## Seksi 13: Observabilitas & Debugging

Gunakan custom logging wrapper untuk menginspeksi mutasi `cleaned_data` dan melacak error validasi yang gagal tanpa membocorkan PII (Personally Identifiable Information) ke log publik:

```python
import logging

logger = logging.getLogger('django.forms.validation')

class ObservabilityFormMixin:
    def is_valid(self):
        valid = super().is_valid()
        if not valid:
            logger.warning(
                "Form Validation Failed",
                extra={
                    "form_class": self.__class__.__name__,
                    "errors": self.errors.as_json(),
                    "non_field_errors": self.non_field_errors().as_json(),
                }
            )
        else:
            logger.info(
                "Form Validation Succeeded",
                extra={"form_class": self.__class__.__name__}
            )
        return valid
```

---

## Seksi 14: Benchmarking & Performance

Saat menggunakan `inlineformset_factory` dengan ModelForm, masalah performa utama adalah query `N+1` pada field ForeignKey di masing-masing baris formset (contoh: rendering `<select>` option Product).

### Optimasi Query Rendering Formset
```python
# Buruk: Memicu SELECT * FROM Product per row
formset = OrderItemFormSet(instance=order)

# Optimal: Pre-fetch queryset dengan cache limitasi field
class OptimizedOrderItemForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.only('id', 'name', 'price', 'stock')

OrderItemFormSet = inlineformset_factory(
    Order, OrderItem,
    form=OptimizedOrderItemForm,
    formset=BaseOrderItemFormSet,
    extra=1
)
```

---

## Seksi 15: Hands-on Lab Mini-Project

### Objective
Implementasikan validasi batas total alokasi persentase portofolio investasi. Total item alokasi portofolio tidak boleh melebihi 100%.

### Kode Lab Starter
```python
# lab/forms.py
from django import forms
from django.forms import BaseFormSet, formset_factory
from django.core.exceptions import ValidationError

class AssetAllocationForm(forms.Form):
    asset_name = forms.CharField(max_length=50)
    percentage = forms.DecimalField(max_value=100, min_value=0)

class BaseAllocationFormSet(BaseFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        
        total_percentage = 0
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get('DELETE', False):
                continue
            total_percentage += form.cleaned_data.get('percentage', 0)
        
        if total_percentage != 100:
            raise ValidationError(
                f"Total alokasi harus persis 100%. Total saat ini: {total_percentage}%",
                code='invalid_total_allocation'
            )

AllocationFormSet = formset_factory(
    AssetAllocationForm,
    formset=BaseAllocationFormSet,
    extra=2,
    can_delete=True
)
```

---

## Seksi 16: Automated Testing & Verification

Gunakan TestCase bawaan Django untuk memverifikasi validation execution pipeline:

```python
# orders/tests/test_forms.py
from decimal import Decimal
from django.test import TestCase
from orders.models import Customer, Product
from orders.forms import OrderItemFormSet, OrderForm

class OrderFormValidationTestCase(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name="PT Maju Bersama", credit_limit=Decimal('5000.00'))
        self.product_a = Product.objects.create(sku="PROD-A", name="Widget A", price=Decimal('100.00'), stock=10)
        self.product_b = Product.objects.create(sku="PROD-B", name="Widget B", price=Decimal('200.00'), stock=2)

    def test_formset_duplicate_product_invalid(self):
        """Memverifikasi bahwa memilih produk yang sama dua kali akan menghasilkan error validasi."""
        data = {
            'items-TOTAL_FORMS': '2',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '1',
            'items-MAX_NUM_FORMS': '10',
            'items-0-product': str(self.product_a.id),
            'items-0-quantity': '1',
            'items-1-product': str(self.product_a.id),
            'items-1-quantity': '2',
            'customer': str(self.customer.id),
        }
        formset = OrderItemFormSet(data=data, prefix='items')
        self.assertFalse(formset.is_valid())
        self.assertIn('Produk ini sudah dipilih di baris lain.', formset.errors[1]['product'])

    def test_formset_stock_exhaustion_invalid(self):
        """Memverifikasi bahwa kuantitas yang melebihi stok fisik akan ditolak."""
        data = {
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '1',
            'items-MAX_NUM_FORMS': '10',
            'items-0-product': str(self.product_b.id),
            'items-0-quantity': '5',  # Stok hanya 2
            'customer': str(self.customer.id),
        }
        formset = OrderItemFormSet(data=data, prefix='items')
        self.assertFalse(formset.is_valid())
        self.assertIn('Stok tidak mencukupi', formset.errors[0]['quantity'][0])

    def test_formset_credit_limit_exceeded(self):
        """Memverifikasi bahwa non-field error dilempar jika kalkulasi total melebihi limit kredit."""
        data = {
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '1',
            'items-MAX_NUM_FORMS': '10',
            'items-0-product': str(self.product_a.id),
            'items-0-quantity': '60',  # 60 * 100 = 6000 > 5000 (Limit)
            'customer': str(self.customer.id),
        }
        # Inject custom stock for test
        self.product_a.stock = 100
        self.product_a.save()

        formset = OrderItemFormSet(data=data, prefix='items')
        self.assertFalse(formset.is_valid())
        self.assertTrue(any('melebihi limit kredit' in error for error in formset.non_form_errors()))
```

---

## Seksi 17: Troubleshooting Guide

| Gejala Error | Akar Masalah | Solusi Perbaikan |
|---|---|---|
| `ValidationError: ['ManagementForm data is missing or has been tampered with']` | Formset HTML tidak menyertakan `{{ formset.management_form }}` di dalam form element. | Tambahkan `{{ formset.management_form }}` langsung setelah tag pembuka `<form>` di template. |
| Field bernilai `None` di `clean()` | Field level validation (`clean_<field>`) tidak mengembalikan `return value`. | Pastikan seluruh method `clean_<fieldname>()` selalu diakhiri dengan `return self.cleaned_data.get('fieldname')` atau data yang telah dimodifikasi. |
| Error `KeyError` saat mengakses `self.cleaned_data['field']` | Field gagal pada tahap `to_python` atau `Field.validate` awal sehingga dihapus dari dictionary `cleaned_data`. | Gunakan metode `self.cleaned_data.get('field')` yang aman, dan cek `if field:` sebelum eksekusi logic downstream. |

---

## Seksi 18: Checklist Produksi

- [ ] Semua `ModelForm` mendefinisikan whitelist `fields = [...]` secara eksplisit, bukan `__all__`.
- [ ] Tag `{{ formset.management_form }}` dirender pada template antarmuka inline.
- [ ] Mutasi database yang dihasilkan oleh formset dibungkus dalam blok `transaction.atomic()`.
- [ ] Setiap method `clean_<fieldname>()` mengembalikan nilai valid (`return value`).
- [ ] Validasi formset memiliki unit test yang memvalidasi skenario batas min/max form dan business aggregates.
- [ ] Seluruh input teks yang lolos sanitasi telah terproteksi dari input formatting XSS via Django template escaping standar.

---

## Seksi 19: Ringkasan Eksekutif
Django Forms Pipeline menyediakan pemisahan tanggung jawab yang terstruktur antara penanganan protokol transport web dan domain integrity. Melalui tahapan sekuensial yang ketat (`to_python` -> `validate` -> `run_validators` -> `clean_<field>` -> `clean`), Django memastikan data yang masuk ke model ORM berada dalam kondisi valid dan aman. Formsets mengabstraksi kompleksitas manipulasi multi-rekord secara dinamis, memungkinkan eksekusi transaksi terpadu di backend melalui integrasi yang konsisten dengan transaction layer database.

---

## Seksi 20: Referensi & Bacaan Lanjutan
* Django Official Documentation: *The Forms API & Formsets Reference*.
* James Bennett: *Working with Django Forms* (Core Developer Guide).
* Django Source Code Inspection: `django.forms.forms.BaseForm` & `django.forms.formsets.BaseFormSet`.
* OWASP Top 10 Web Application Security Risks: *Mass Assignment & Input Validation Defense*.