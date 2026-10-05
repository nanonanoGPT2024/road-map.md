# BAB-05-Forms-Processing-Data-Validation-Pipeline-Formsets: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang sebagai instrumen evaluasi teknis, pengujian pemahaman mendalam, dan sarana uji kompetensi praktis terhadap pipeline pemrosesan form, validasi data berlapis, manipulasi `ModelForm`, serta orkestrasi `Formsets` dan `InlineFormsets` pada arsitektur Django web framework.

---

## Bagian 1: 5 Pertanyaan Dasar (Basic Questions)

### Pertanyaan 1: Alur Kerja Eksekusi Validasi Form
Bagaimana siklus hidup internal saat metode `form.is_valid()` dipanggil pada sebuah bound form Django? Sebutkan urutan metode privat/publik yang dieksekusi secara kronologis di dalam engine Django Forms.

<details>
<summary><b>Kunci Jawaban & Pembahasan Mendalam</b></summary>

Ketika `form.is_valid()` dipanggil, Django menjalankan alur berikut:
1. Memeriksa apakah form bersifat *bound* (`is_bound == True`). Jika form unbound, method langsung mengembalikan `False`.
2. Mengecek apakah atribut `_errors` sudah terisi (caching). Jika belum, memanggil `form.errors`, yang secara internal memicu eksekusi `form.full_clean()`.
3. Di dalam `full_clean()`:
   - Inisialisasi struktur `_errors = ErrorDict()` dan `cleaned_data = {}`.
   - **Field-level Cleaning (`_clean_fields`)**: Untuk setiap field terdaftar, mengambil raw input dari `data`/`files`. Jika kosong dan field `required=True`, melempar `ValidationError('This field is required.')`. Jika ada data, memanggil `field.clean(value)` yang mengeksekusi `to_python()` (konversi tipe data bawaan) disusul validasi validator bawaan field (`run_validators()`). Nilai yang lolos dimasukkan ke `cleaned_data`.
   - **Custom Field Cleaning (`clean_<fieldname>`)**: Memeriksa apakah subclass mendefinisikan method `clean_<fieldname>()`. Jika ada, method ini dieksekusi untuk validasi field spesifik dan mengembalikan nilai yang telah disanitasi.
   - **Cross-Field Validation (`_clean_form`)**: Memanggil method `clean()` tingkat form. Pada tahap ini, seluruh field yang valid telah berada di `cleaned_data`. Di sini dilakukan validasi relasi antar-kolom.
   - **Post-cleaning Hooks (`_post_clean`)**: Khusus pada `ModelForm`, tahap ini mengonstruksi instance model sementara via `construct_instance()` dan memanggil validasi model seperti `instance.full_clean()` (termasuk `validate_unique()` untuk enforce unique constraints di level form).
4. `is_valid()` mengembalikan `True` jika `form.errors` kosong (`bool(self.errors) == False`).

</details>

---

### Pertanyaan 2: Perbedaan Fundamental `forms.Form` vs `forms.ModelForm`
Jelaskan perbedaan struktural antara `forms.Form` dan `forms.ModelForm`. Mengapa penggunaan `fields = '__all__'` pada `ModelForm` di lingkungan produksi dianggap sebagai *anti-pattern* dan pelanggaran keamanan?

<details>
<summary><b>Kunci Jawaban & Pembahasan Mendalam</b></summary>

- **`forms.Form`**: Kelas form independen di mana setiap field dideklarasikan secara eksplisit. Form ini tidak memiliki keterikatan langsung ke database schema/model ORM dan cocok untuk alur non-CRUD (misal: contact form, wizard pencarian, kalkulator, form autentikasi OTP).
- **`forms.ModelForm`**: Turunan dari `BaseModelForm` yang secara otomatis mengintrospeksi metadata model Django (`Model._meta`) untuk mengonversi model fields menjadi form fields, menyertakan validasi constraint model (tipe data, `max_length`, `unique_together`), serta menyediakan metode persistensi `save()`.

**Bahaya `fields = '__all__' (Mass Assignment Vulnerability)**:
Jika model mengalami migrasi struktural di masa depan (misal: penambahan kolom sensitif seperti `is_staff`, `account_balance`, `tenant_id`, `verified_status`), penggunaan `__all__` akan secara otomatis mengekspos field tersebut ke form publik. Penyerang dapat melakukan injeksi payload HTTP POST dengan menambahkan atribut tersebut pada form body, sehingga nilainya masuk ke database tanpa proteksi. Best practice adalah **selalu mendeklarasikan tuple/list field secara eksplisit** menggunakan `fields = ('nama', 'email', ...)` dan tidak mengandalkan `exclude`.

</details>

---

### Pertanyaan 3: Mekanisme Proteksi CSRF pada Penanganan Form POST
Bagaimana Django memproteksi form terhadap serangan *Cross-Site Request Forgery (CSRF)* melalui template tag `{% csrf_token %}` dan middleware `CsrfViewMiddleware`?

<details>
<summary><b>Kunci Jawaban & Pembahasan Mendalam</b></summary>

Mekanisme proteksi CSRF di Django mengadopsi pola *Double-Submit Cookie Pattern* yang diperkuat dengan kriptografi berbasis secret salt:
1. **Cookie Penjelajah**: Middleware `CsrfViewMiddleware` menetapkan cookie bernama `csrftoken` pada browser klien yang berisi token pseudorandom unik terenkripsi/teracak.
2. **Form Payload Token**: Ketika template dirender menggunakan tag `{% csrf_token %}`, Django menyisipkan elemen input tersembunyi (`<input type="hidden" name="csrfmiddlewaretoken" value="...">`). Nilai ini diturunkan dari token internal melalui masking algoritma XOR berbasis salt untuk mencegah serangan BREACH/CRIME.
3. **Verifikasi Server-side**: Ketika form dikirim melalui metode HTTP yang tidak aman (`POST`, `PUT`, `DELETE`, `PATCH`), `CsrfViewMiddleware` mengekstrak token dari payload form (atau header HTTP `X-CSRFToken` jika AJAX/Fetch) dan membandingkannya dengan token yang ada pada cookie penjelajah pengguna.
4. **Enforcement**: Jika token tidak cocok, tidak ada, atau secret HMAC invalid, Django segera memutus pemrosesan dan mengembalikan HTTP response `403 Forbidden` (`CSRF verification failed. Request aborted.`), sebelum view atau form processing logic sempat dieksekusi.

</details>

---

### Pertanyaan 4: Perbedaan Mengakses `request.POST` vs `form.cleaned_data`
Mengapa seorang software engineer dilarang keras mengambil nilai langsung dari dictionary `request.POST['field_name']` setelah form berhasil melewati `form.is_valid()`, dan wajib menggunakan `form.cleaned_data['field_name']`?

<details>
<summary><b>Kunci Jawaban & Pembahasan Mendalam</b></summary>

Perbedaan kritis terletak pada sanitasi, validasi, dan konversi tipe data:
1. **Raw String vs Python Primitive**: Data pada `request.POST` murni merupakan raw data string (`str`) atau list of string (dari `QueryDict`). Nilai numerik adalah string `"123"`, checkbox bernilai `"on"` atau `"true"`, dan tanggal bernilai `"2026-10-05"`. Sebaliknya, `form.cleaned_data` telah dikonversi (`to_python`) menjadi objek asli Python: `int(123)`, `bool(True)`, dan instance `datetime.date(2026, 10, 5)`.
2. **Sanitasi XSS & Normalisasi**: Custom cleaning method (`clean_<field>`) melakukan normalisasi format (misalnya strip whitespace, lowercase email, canonical format). Mengakses `request.POST` mengabaikan seluruh transformasi pembersihan ini.
3. **Foreign Key & Model References**: Pada `ModelChoiceField`, `request.POST['category']` hanya berisi string ID (`"42"`), sedangkan `form.cleaned_data['category']` telah di-resolve secara aman oleh Django ORM menjadi instance objek model `Category.objects.get(pk=42)`.
4. **Integritas Alur**: `cleaned_data` hanya eksis dan terisi jika data lolos seluruh aturan validasi. Mengakses `request.POST` memotong lapisan validasi dan berpotensi memasukkan data kotor atau malformed langsung ke sistem.

</details>

---

### Pertanyaan 5: Konsep Dasar dan Anatomi Formset
Apa itu `Formset` dalam Django, dan apa fungsi dari elemen `ManagementForm` (`TOTAL_FORMS`, `INITIAL_FORMS`, `MIN_NUM_FORMS`, `MAX_NUM_FORMS`)?

<details>
<summary><b>Kunci Jawaban & Pembahasan Mendalam</b></summary>

`Formset` adalah abstraction layer di Django yang mengelola kumpulan (*collection*) dari beberapa form pada satu halaman web yang sama secara terkoordinasi (misalnya: baris entri multi-transaksi, daftar upload banyak file, atau dynamic row items).

**Peran `ManagementForm`**:
`ManagementForm` adalah form internal yang dirender secara otomatis (`{{ formset.management_form }}`) menjadi field input tersembunyi dengan prefix tertentu:
- `form-TOTAL_FORMS`: Jumlah total form yang dikirimkan oleh browser (termasuk form awal dan form ekstra baru yang ditambahkan secara dinamis via JavaScript).
- `form-INITIAL_FORMS`: Jumlah form yang memuat data awal yang telah tersimpan sebelumnya dari database.
- `form-MIN_NUM_FORMS`: Batas minimum form yang diizinkan untuk dikirimkan.
- `form-MAX_NUM_FORMS`: Batas maksimum form yang diizinkan untuk dikirimkan (mencegah DoS injection).

**Konsekuensi Keamanan**: Jika `ManagementForm` tidak disertakan dalam template atau dimanipulasi secara ilegal oleh klien, validasi `formset.is_valid()` akan memunculkan exception `ValidationError('ManagementForm data is missing or has been tampered with')`.

</details>

---

## Bagian 2: 5 Pertanyaan Menengah (Intermediate Questions)

### Pertanyaan 1: Isolasi `clean_<field>` vs Form-level `clean()`
Kapan sebuah aturan validasi harus diletakkan pada `clean_<fieldname>()` dan kapan harus diletakkan pada `clean()` tingkat form? Jelaskan penanganan `ValidationError` untuk non-field errors vs field-specific errors pada `clean()`.

<details>
<summary><b>Kunci Jawaban & Pembahasan Mendalam</b></summary>

- **Gunakan `clean_<fieldname>()`**: Saat validasi hanya bergantung pada nilai field tersebut secara mandiri.
  *Contoh:* Memeriksa apakah format nomor telepon lokal valid, mengubah huruf nama menjadi Title Case, atau memastikan email tidak menggunakan disposable domain.
  ```python
  def clean_email(self):
      email = self.cleaned_data.get('email', '').strip().lower()
      if email.endswith('@temp-mail.org'):
          raise forms.ValidationError('Domain email sementara tidak diperbolehkan.')
      return email
  ```
- **Gunakan Form-level `clean()`**: Saat validasi membutuhkan korelasi/komparasi antara dua field atau lebih (*cross-field validation*).
  *Contoh:* Memastikan `password` identik dengan `confirm_password`, atau memastikan rentang `start_date` lebih awal daripada `end_date`.

**Penanganan `ValidationError`**:
Jika error terjadi pada `clean()`, default exception akan masuk ke dalam `non_field_errors()`:
```python
raise forms.ValidationError('Tanggal selesai harus lebih besar dari tanggal mulai.')
```
Namun, jika engineer ingin menautkan error spesifik ke field tertentu dari dalam method `clean()` (agar error muncul tepat di bawah widget input terkait di template), gunakan dictionary argument pada `ValidationError` atau method `self.add_error()`:
```python
def clean(self):
    cleaned_data = super().clean()
    start_date = cleaned_data.get('start_date')
    end_date = cleaned_data.get('end_date')

    if start_date and end_date and end_date < start_date:
        # Menautkan error langsung ke field end_date
        self.add_error('end_date', 'Tanggal akhir tidak boleh mendahului tanggal mulai.')
    return cleaned_data
```

</details>

---

### Pertanyaan 2: Dynamic Argument Injection ke Form Constructor (`__init__`)
Bagaimana cara meneruskan data konteks runtime (misalnya `request.user` atau `tenant_id`) ke dalam instance `Form` atau `ModelForm`, dan bagaimana cara menggunakannya untuk memfilter queryset dropdown widget secara dinamis?

<details>
<summary><b>Kunci Jawaban & Pembahasan Mendalam</b></summary>

Pola arsitektur standar adalah mengekstrak argumen kustom dari `*args` dan `**kwargs` di method `__init__` form sebelum memanggil `super().__init__()`:

```python
class ProjectTaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ('title', 'assigned_to', 'priority')

    def __init__(self, *args, current_user=None, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_user = current_user
        self.tenant = tenant

        if self.tenant is not None:
            # Memfilter queryset ModelChoiceField hanya untuk user di tenant yang sama
            self.fields['assigned_to'].queryset = User.objects.filter(
                organization=self.tenant,
                is_active=True
            ).order_by('first_name', 'last_name')
```

Di sisi View (FBV atau CBV):
```python
# Function-Based View
def create_task_view(request):
    if request.method == 'POST':
        form = ProjectTaskForm(
            request.POST, 
            current_user=request.user, 
            tenant=request.user.organization
        )
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            task.save()
            return redirect('task-detail', pk=task.pk)
    else:
        form = ProjectTaskForm(
            current_user=request.user, 
            tenant=request.user.organization
        )
    return render(request, 'tasks/task_form.html', {'form': form})
```
Hal ini mencegah kebocoran data (*data leakage*) di mana pengguna dapat melihat anggota tenant lain pada widget dropdown.

</details>

---

### Pertanyaan 3: Manajemen `commit=False` dan Relasi Many-to-Many (`save_m2m`)
Jelaskan implikasi teknis saat memanggil `form.save(commit=False)`. Mengapa dan kapan method `form.save_m2m()` wajib dieksekusi secara manual?

<details>
<summary><b>Kunci Jawaban & Pembahasan Mendalam</b></summary>

Saat method `form.save(commit=False)` dipanggil:
1. Django membuat objek instance model di memori dengan atribut yang sudah diisi dari `cleaned_data`.
2. Django **tidak langsung mengirimkan query `INSERT`/`UPDATE` ke database**, memberikan kesempatan bagi developer untuk menyuntikkan data tambahan ke instance yang belum ada di input form (misalnya: `instance.author = request.user`, atau kalkulasi hash/status).
3. Karena record instance utama belum memiliki primary key permanen yang tersimpan di database pada saat itu, relasi **Many-to-Many (M2M)** tidak dapat disimpan ke tabel junction/perantara (intermediate table).
4. Ketika developer akhirnya memanggil `instance.save()` secara manual, data model utama tersimpan di database, tetapi field Many-to-Many **belum otomatis tersambung**.
5. Developer wajib memanggil `form.save_m2m()` setelah pemanggilan `instance.save()` untuk memerintahkan form membaca data relasi M2M dari `cleaned_data` dan mengeksekusi operasi `add()` pada tabel pivot M2M terkait.

*Contoh Alur Lengkap:*
```python
if form.is_valid():
    article = form.save(commit=False)
    article.author = request.user
    article.published_ip = request.META.get('REMOTE_ADDR')
    article.save()  # Menghasilkan primary key (article.pk) di database
    form.save_m2m() # Wajib: Menyimpan tags/categories relasi Many-to-Many
    return redirect('article-list')
```

</details>

---

### Pertanyaan 4: Inline Formset Factory dan Siklus Penghapusan Data
Bagaimana fungsi `inlineformset_factory` menyederhanakan pengelolaan relasi One-to-Many (Master-Detail)? Bagaimana siklus hidup pembersihan instance yang ditandai untuk dihapus (`can_delete=True`) bekerja saat formset disimpan?

<details>
<summary><b>Kunci Jawaban & Pembahasan Mendalam</b></summary>

`inlineformset_factory(parent_model, model, form=..., fields=..., extra=..., can_delete=True)` adalah pembungkus deklaratif yang mengotomatisasi pembuatan `ModelFormSet` yang terikat pada ForeignKey dari `parent_model`.

**Fitur & Alur Kerja**:
1. Menghubungkan setiap child form dengan parent instance secara otomatis tanpa mengharuskan field ForeignKey dirender di UI.
2. Ketika `can_delete=True`, setiap sub-form menyertakan field boolean tersembunyi/checkbox bernama `DELETE` (misal: `items-0-DELETE`).
3. Saat `formset.save()` dipanggil:
   - Formset memeriksa sub-form yang memiliki input `DELETE=True`.
   - Objek database yang bersesuaian dengan sub-form tersebut tidak diperbarui, melainkan langsung dieksekusi query `DELETE` dari database (`instance.delete()`).
   - Objek baru yang ditandai `DELETE` bahkan tidak akan pernah disimpan ke database.
4. Jika menggunakan `formset.save(commit=False)`:
   - Django mengembalikan list objek yang diupdate/dibuat, namun **tidak menghapus** objek yang ditandai `DELETE`. Developer harus mengiterasi `formset.deleted_objects` dan memanggil `obj.delete()` secara manual:
   ```python
   instances = formset.save(commit=False)
   for instance in instances:
       instance.invoice = invoice_obj
       instance.save()
   for deleted_obj in formset.deleted_objects:
       deleted_obj.delete()
   ```

</details>

---

### Pertanyaan 5: Sanitasi dan Validasi File Upload (`FileField`/`ImageField`)
Mengapa memeriksa ekstensi nama file (misal `file.name.endswith('.png')`) tidak mencukupi untuk validasi keamanan file upload di Django? Bagaimana pipeline validasi berkas yang aman terhadap *extension spoofing* dan eksploitasi file berukuran masif (DoS)?

<details>
<summary><b>Kunci Jawaban & Pembahasan Mendalam</b></summary>

Ekstensi nama file hanyalah string metadata yang dikirim oleh klien dan dapat dimanipulasi dengan mudah oleh penyerang (misalnya: script PHP/executable berbahaya dinamai `malware.png`).

**Pipeline Validasi Berkas Standar Produksi**:
1. **Pemeriksaan Ukuran Berkas (`file.size`)**: Mencegah serangan Denial of Service (DoS) yang menghabiskan memori RAM dan disk I/O.
2. **Pemeriksaan Magic Bytes / MIME Type Asli**: Membaca header biner pertama dari stream data file menggunakan pustaka parser berkas independen seperti `python-magic` atau modul `PIL` / `pillow` untuk gambar, bukan hanya membaca header `file.content_type` bawaan browser.
3. **Penyimpanan Aman**: Menggunakan upload handler yang tepat (`MemoryUploadedFile` vs `TemporaryUploadedFile`) dan menyimpannya dengan penamaan hashing UUID acak untuk mencegah penimpaan file sistem atau eksekusi path traversal.

*Implementasi Validasi Custom File:*
```python
import magic
from django import forms
from django.core.exceptions import ValidationError

MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_MIMETYPES = ['application/pdf', 'image/jpeg', 'image/png']

class SecureDocumentUploadForm(forms.Form):
    document = forms.FileField()

    def clean_document(self):
        file = self.cleaned_data.get('document')
        if not file:
            raise ValidationError('Berkas tidak ditemukan.')

        # 1. Batasi ukuran file
        if file.size > MAX_UPLOAD_SIZE:
            raise ValidationError('Ukuran berkas melebihi batas maksimum 5 MB.')

        # 2. Baca magic byte biner untuk identifikasi MIME asli
        header_sample = file.read(2048)
        file.seek(0) # Reset pointer agar stream file tidak rusak saat disimpan
        mime_type = magic.from_buffer(header_sample, mime=True)

        if mime_type not in ALLOWED_MIMETYPES:
            raise ValidationError(f'Tipe berkas tidak diizinkan ({mime_type}). Unggah PDF/JPEG/PNG.')

        return file
```

</details>

---

## Bagian 3: 3 Skenario Kasus Nyata Produksi (Production Scenarios)

### Skenario 1: Penanganan Race Condition & Double Submit pada Form Checkout E-Commerce

**Latar Belakang Kasus**:
Sebuah platform e-commerce dengan trafik tinggi mengalami insiden integritas transaksi keuangan: beberapa pengguna menekan tombol "Submit Pembayaran" berulang kali dalam jeda milidetik akibat koneksi internet yang lambat. Server memproses kedua request POST secara paralel, melewati validasi saldo/stok, dan menciptakan dua pesanan berbeda dengan nomor invoice identik atau pengurangan saldo ganda.

**Analisis Masalah**:
Validasi form standar (`is_valid()`) tidak memiliki statefulness antar-thread/proses. Jika dua request masuk bersamaan, keduanya membaca saldo yang sama dari database sebelum transaksi pertama sempat melakukan commit. Validasi aplikasi lolos di kedua proses.

**Arsitektur Solusi Terintegrasi**:
1. **Client-side**: Disable submit button via JavaScript seketika saat event `submit` terjadi, serta tampilkan loader spinner.
2. **Idempotency Token di Level Form**: Buat hidden field `idempotency_key` (UUID4) pada form. Nilai ini disimpan sementara di Redis dengan atomic operation `SETNX` (Set if Not Exists) bertenggang waktu (TTL). Jika key sudah ada, tolak request kedua secara instan.
3. **Database-level Pessimistic Locking**: Gunakan `select_for_update()` di dalam blok `transaction.atomic()` saat memproses data form untuk mengunci baris database akun/stok.

*Implementasi Kode:*
```python
import uuid
from django import forms
from django.db import transaction
from django.core.cache import cache
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Wallet, Order

class CheckoutForm(forms.Form):
    idempotency_key = forms.CharField(widget=forms.HiddenInput())
    shipping_address = forms.CharField(max_length=255, widget=forms.Textarea)

    def clean_idempotency_key(self):
        key = self.cleaned_data.get('idempotency_key')
        # Gunakan Redis cache untuk atomic locking idempotency key selama 60 detik
        is_acquired = cache.add(f"checkout_lock:{key}", "in_progress", timeout=60)
        if not is_acquired:
            raise forms.ValidationError("Permintaan sedang diproses. Jangan mengirim ulang formulir.")
        return key

def process_checkout_view(request):
    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            idempotency_key = form.cleaned_data['idempotency_key']
            try:
                with transaction.atomic():
                    # Kunci wallet pengguna untuk mencegah balapan thread
                    wallet = Wallet.objects.select_for_update().get(user=request.user)
                    total_amount = calculate_cart_total(request.user)

                    if wallet.balance < total_amount:
                        raise forms.ValidationError("Saldo dompet tidak mencukupi.")

                    # Potong saldo dan buat order
                    wallet.balance -= total_amount
                    wallet.save()

                    order = Order.objects.create(
                        user=request.user,
                        address=form.cleaned_data['shipping_address'],
                        amount=total_amount,
                        idempotency_token=idempotency_key
                    )
                    return redirect('order-success', order_id=order.id)
            except Exception as exc:
                # Lepas lock jika terjadi crash agar user bisa mencoba lagi
                cache.delete(f"checkout_lock:{idempotency_key}")
                form.add_error(None, str(exc))
    else:
        # Generate token unik untuk form baru
        initial_token = str(uuid.uuid4())
        form = CheckoutForm(initial={'idempotency_key': initial_token})

    return render(request, 'checkout/payment.html', {'form': form})
```

---

### Skenario 2: Cross-Tenant Data Leakage pada `ModelChoiceField` Multi-Tenant SaaS

**Latar Belakang Kasus**:
Aplikasi B2B Multi-Tenant SaaS mencatat insiden keamanan kategori *High Vulnerability*: saat admin dari Perusahaan A membuat tiket pekerjaan (`Ticket`), dropdown `Assigned Member` menampilkan seluruh daftar karyawan dari Perusahaan B dan C. Selain itu, penyerang dari Perusahaan A dapat mengirimkan payload POST manipulatif berisi ID karyawan milik Perusahaan B, dan Django `ModelForm` menyimpannya tanpa error.

**Analisis Masalah**:
Secara default, saat field dideklarasikan pada `ModelForm`:
```python
assigned_member = forms.ModelChoiceField(queryset=Employee.objects.all())
```
Queryset dievaluasi secara global saat modul pertama kali diimpor, sehingga tidak menyaring data berdasarkan konteks tenant pengguna yang sedang login. Validasi bawaan `ModelChoiceField` hanya memeriksa apakah ID yang dikirim ada di dalam `queryset`, yang mengakibatkan data tenant lain lolos validasi jika global queryset digunakan.

**Arsitektur Solusi Terintegrasi**:
1. Lakukan override method `__init__` pada form untuk menerima parameter `tenant`.
2. Batasi `self.fields['assigned_member'].queryset` secara ketat hanya pada lingkup record milik tenant terkait.
3. Tambahkan validasi eksplisit di method `clean_assigned_member()` sebagai lapisan pertahanan mendalam (*defense-in-depth*).

*Implementasi Kode:*
```python
from django import forms
from django.core.exceptions import ValidationError
from .models import Ticket, Employee

class TenantAwareTicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ('title', 'description', 'priority', 'assigned_member')

    def __init__(self, *args, tenant=None, **kwargs):
        if tenant is None:
            raise ValueError("Konteks tenant wajib disertakan pada TenantAwareTicketForm.")
        super().__init__(*args, **kwargs)
        self.tenant = tenant

        # 1. Batasi pilihan dropdown hanya untuk karyawan tenant aktif
        self.fields['assigned_member'].queryset = Employee.objects.filter(
            company=self.tenant,
            is_active=True
        ).select_related('user')
        self.fields['assigned_member'].empty_label = "-- Pilih Anggota Tim --"

    def clean_assigned_member(self):
        member = self.cleaned_data.get('assigned_member')
        # 2. Defense-in-depth: Pastikan instance yang dikirim benar-benar milik tenant terkait
        if member and member.company_id != self.tenant.id:
            raise ValidationError("Pelanggaran Keamanan: Karyawan yang dipilih bukan bagian dari organisasi Anda.")
        return member
```

---

### Skenario 3: Mass Assignment Bypass & Tampering pada Dynamic Inline Formset

**Latar Belakang Kasus**:
Sebuah sistem faktur B2B memungkinkan pengguna membuat `Invoice` sekaligus mengisi baris detail item (`InvoiceItem`) melalui dynamic inline formset. Ditemukan celah bahwa pengguna dapat menambahkan field `price` bernilai negatif (`-500000`) atau mengubah baris item milik invoice pelanggan lain dengan memodifikasi ID tersembunyi `items-0-id` pada payload form HTTP POST.

**Analisis Masalah**:
1. Formset mengandalkan field primary key tersembunyi (`id`) untuk mengenali baris yang sudah ada vs baris baru. Jika query formset tidak dibatasi pada relasi parent instance, pengiriman ID arbitrary dapat menyebabkan manipulasi baris milik relasi lain.
2. Tidak adanya validasi kuantitas dan harga satuan minimum (`MinValueValidator`) di level form memungkinkan nilai negatif lolos dan mengurangi total tagihan.

**Arsitektur Solusi Terintegrasi**:
1. Gunakan custom `BaseInlineFormSet` untuk memvalidasi seluruh formset secara kolektif: pastikan minimal 1 baris item valid terisi, hitung total akumulatif, dan tolak nilai negatif.
2. Validasi integritas primary key melalui relasi parent binding bawaan `inlineformset_factory`.

*Implementasi Kode:*
```python
from decimal import Decimal
from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from django.core.exceptions import ValidationError
from .models import Invoice, InvoiceItem

class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ('product_name', 'quantity', 'unit_price')

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if qty is None or qty <= 0:
            raise ValidationError("Kuantitas barang harus lebih besar dari 0.")
        return qty

    def clean_unit_price(self):
        price = self.cleaned_data.get('unit_price')
        if price is None or price <= Decimal('0.00'):
            raise ValidationError("Harga satuan tidak boleh nol atau negatif.")
        return price

class BaseInvoiceItemFormSet(BaseInlineFormSet):
    """Custom Formset Validation untuk Business Logic Kolektif"""
    def clean(self):
        super().clean()
        if any(self.errors):
            # Jika ada error individual di sub-form, abaikan validasi kolektif
            return

        active_items_count = 0
        total_invoice_amount = Decimal('0.00')

        for form in self.forms:
            # Lewati form yang ditandai untuk dihapus atau form kosong yang tidak diubah
            if self.can_delete and self._should_delete_form(form):
                continue
            if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                continue

            active_items_count += 1
            qty = form.cleaned_data.get('quantity', 0)
            price = form.cleaned_data.get('unit_price', Decimal('0.00'))
            total_invoice_amount += (Decimal(qty) * price)

        # 1. Enforce business rule: Minimal harus ada 1 item per faktur
        if active_items_count == 0:
            raise ValidationError("Faktur wajib memiliki minimal 1 (satu) baris item yang valid.")

        # 2. Enforce business rule: Total nominal minimum
        if total_invoice_amount < Decimal('10000.00'):
            raise ValidationError("Total nominal faktur tidak boleh kurang dari Rp 10.000,00.")

# Instansiasi factory aman
InvoiceItemFormSet = inlineformset_factory(
    parent_model=Invoice,
    model=InvoiceItem,
    form=InvoiceItemForm,
    formset=BaseInvoiceItemFormSet,
    extra=1,
    can_delete=True
)
```

---

## Bagian 4: Practical Chapter Challenge

### Judul Tantangan:
**"Membangun Engine Faktur Multi-Baris (Purchase Invoice & Dynamic Item Formset) dengan Enkapsulasi Validasi Finansial dan Transaction Atomic"**

### 1. Spesifikasi Persyaratan Teknis
Bangun arsitektur modul Django lengkap yang menangani pembuatan dan pembaruan faktur pesanan (`PurchaseOrder`) beserta baris barang (`OrderItem`) dengan ketentuan teknis berikut:

1. **Model Relasional**:
   - `PurchaseOrder`: Menyimpan `order_number` (string unik), `vendor_name`, `created_at`, `status` (DRAFT, CONFIRMED, CANCELLED), `tax_rate` (persentase desimal, default 11%), `subtotal`, dan `grand_total`.
   - `OrderItem`: Menyimpan Foreign Key ke `PurchaseOrder` (`related_name='items'`), `item_code`, `description`, `quantity` (integer positif), `unit_cost` (desimal), dan `line_total` (terhitung otomatis).

2. **Lapisan Validasi Form & Formset**:
   - `PurchaseOrderForm`: Memastikan `order_number` diawali prefix `"PO-"` dengan 6 digit numerik (contoh: `"PO-100203"`).
   - `OrderItemForm`: Memastikan `quantity >= 1` dan `unit_cost >= 1000`.
   - `OrderItemInlineFormSet`:
     * Minimal harus ada 1 baris aktif.
     * Tidak boleh ada `item_code` duplikat dalam satu formset faktur yang sama (deteksi item kembar).
     * Hitung akumulasi `subtotal`, kalkulasi pajak berdasarkan `tax_rate`, dan tetapkan `grand_total` secara otomatis sebelum commit ke database.

3. **Integritas Database (Transaction Management)**:
   - Simpan `PurchaseOrder` dan seluruh `OrderItem` dalam satu blok `transaction.atomic()`. Jika salah satu item gagal disimpan, batalkan (*rollback*) seluruh transaksi.

---

### 2. Implementasi Lengkap (Reference Implementation)

#### File: `models.py`
```python
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator

class PurchaseOrder(models.Model):
    STATUS_CHOICES = (
        ('DRAFT', 'Draft'),
        ('CONFIRMED', 'Confirmed'),
        ('CANCELLED', 'Cancelled'),
    )

    order_number = models.CharField(max_length=20, unique=True, db_index=True)
    vendor_name = models.CharField(max_length=150)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('11.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def calculate_totals(self):
        """Menghitung ulang subtotal dan grand_total dari relasi items"""
        lines = self.items.all()
        calculated_subtotal = sum(item.line_total for item in lines)
        calculated_tax = calculated_subtotal * (self.tax_rate / Decimal('100.00'))
        self.subtotal = calculated_subtotal
        self.grand_total = calculated_subtotal + calculated_tax
        self.save(update_fields=['subtotal', 'grand_total', 'updated_at'])

    def __str__(self):
        return f"{self.order_number} - {self.vendor_name}"


class OrderItem(models.Model):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    item_code = models.CharField(max_length=50)
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_cost = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('1000.00'))]
    )
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    def save(self, *args, **kwargs):
        self.line_total = Decimal(self.quantity) * self.unit_cost
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.item_code} ({self.quantity} x {self.unit_cost})"
```

#### File: `forms.py`
```python
import re
from decimal import Decimal
from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from django.core.exceptions import ValidationError
from .models import PurchaseOrder, OrderItem

class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ('order_number', 'vendor_name', 'tax_rate', 'status')
        widgets = {
            'order_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'PO-100001'}),
            'vendor_name': forms.TextInput(attrs={'class': 'form-control'}),
            'tax_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean_order_number(self):
        order_num = self.cleaned_data.get('order_number', '').strip().upper()
        # Enforce format: PO- diikuti 6 digit angka
        if not re.match(r'^PO-\d{6}$', order_num):
            raise ValidationError("Format Nomor PO harus diawali 'PO-' dan diikuti 6 digit angka (contoh: PO-100203).")
        return order_num


class OrderItemForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ('item_code', 'description', 'quantity', 'unit_cost')
        widgets = {
            'item_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'SKU-001'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'unit_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '100.00'}),
        }

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if qty is None or qty < 1:
            raise ValidationError("Kuantitas minimal adalah 1 unit.")
        return qty

    def clean_unit_cost(self):
        cost = self.cleaned_data.get('unit_cost')
        if cost is None or cost < Decimal('1000.00'):
            raise ValidationError("Biaya satuan barang tidak boleh kurang dari Rp 1.000,00.")
        return cost


class BaseOrderItemInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        seen_codes = set()
        valid_items_count = 0

        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue
            if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                continue

            item_code = form.cleaned_data.get('item_code', '').strip().upper()

            # Deteksi item_code ganda pada satu PO
            if item_code in seen_codes:
                form.add_error('item_code', f"Kode barang '{item_code}' tercatat lebih dari sekali pada faktur ini.")
            seen_codes.add(item_code)
            valid_items_count += 1

        if valid_items_count == 0:
            raise ValidationError("Faktur Pembelian wajib memiliki minimal 1 (satu) baris item barang.")


OrderItemFormSet = inlineformset_factory(
    parent_model=PurchaseOrder,
    model=OrderItem,
    form=OrderItemForm,
    formset=BaseOrderItemInlineFormSet,
    extra=1,
    can_delete=True
)
```

#### File: `views.py`
```python
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.contrib import messages
from .models import PurchaseOrder
from .forms import PurchaseOrderForm, OrderItemFormSet

def purchase_order_create_or_update(request, pk=None):
    if pk:
        order = get_object_or_404(PurchaseOrder, pk=pk)
        page_title = f"Ubah Faktur Pembelian: {order.order_number}"
    else:
        order = None
        page_title = "Buat Faktur Pembelian Baru"

    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST, instance=order)
        formset = OrderItemFormSet(request.POST, instance=order)

        if form.is_valid() and formset.is_valid():
            try:
                # Bungkus operasi master-detail ke dalam database atomic transaction
                with transaction.atomic():
                    saved_order = form.save()
                    formset.instance = saved_order
                    formset.save()

                    # Kalkulasi ulang total finansial setelah items tersimpan
                    saved_order.calculate_totals()

                messages.success(request, f"Faktur {saved_order.order_number} berhasil disimpan dengan total Rp {saved_order.grand_total:,.2f}.")
                return redirect('po-detail', pk=saved_order.pk)
            except Exception as err:
                messages.error(request, f"Terjadi kesalahan saat menyimpan transaksi: {err}")
    else:
        form = PurchaseOrderForm(instance=order)
        formset = OrderItemFormSet(instance=order)

    return render(request, 'purchasing/po_form.html', {
        'form': form,
        'formset': formset,
        'title': page_title,
    })
```

---

### 3. Rubrik Penilaian & Evaluasi (Assessment Rubric)

| Aspek Penilaian | Skor Maksimal | Kriteria Evaluasi |
| :--- | :---: | :--- |
| **Pipeline Validasi Form** | 25% | Mengimplementasikan validasi regex order number, isolasi field-level validation, konversi tipe data decimal & integer, serta pesan error terstruktur. |
| **Orkestrasi Formset** | 25% | Menangani sub-form dinamis, mendeteksi duplikasi `item_code` antar baris via `BaseInlineFormSet`, dan memastikan minimal satu item valid. |
| **Manajemen Transaksi & Integritas Data** | 20% | Menggunakan `transaction.atomic()` untuk menjamin seluruh data baris dan header tersimpan secara atomik tanpa menyisakan *orphan records*. |
| **Kalkulasi Finansial Presisi** | 15% | Penggunaan tipe data `Decimal` (bukan `float`) untuk seluruh kalkulasi mata uang, penanganan pajak persentase akurat, dan pembaruan field agregasi. |
| **Penanganan Deletion & Edge Cases** | 15% | Penghapusan baris via `can_delete` bekerja mulus tanpa merusak formula hitung ulang subtotal dan grand total faktur. |

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan daftar periksa berikut untuk memverifikasi kesiapan penguasaan materi Bab 05 sebelum melanjutkan ke bab berikutnya:

- [ ] **Siklus Form Lifecycle**: Mampu menjelaskan urutan pemanggilan `is_valid()` -> `full_clean()` -> `_clean_fields()` -> `clean_<field>()` -> `clean()` -> `_post_clean()`.
- [ ] **ModelForm Integrity**: Memahami bahaya keamanan `fields = '__all__'` dan selalu mendefinisikan whitelist fields secara eksplisit pada class `Meta`.
- [ ] **Cross-field Validation**: Mampu menggunakan `self.add_error()` di dalam method `clean()` untuk menautkan error spesifik ke widget form yang sesuai di template.
- [ ] **Dependency Injection**: Terbiasa meng-override method `__init__` pada form untuk menerima parameter dinamis seperti `request.user` dan memfilter `ModelChoiceField.queryset`.
- [ ] **M2M Operations**: Memahami kapan dan mengapa `form.save_m2m()` wajib dipanggil setelah `form.save(commit=False)`.
- [ ] **Formset Management**: Memahami fungsi krusial 4 input tersembunyi `ManagementForm` (`TOTAL_FORMS`, `INITIAL_FORMS`, `MIN_NUM_FORMS`, `MAX_NUM_FORMS`).
- [ ] **Custom Inline Formset**: Mampu membuat subclass `BaseInlineFormSet` untuk menerapkan validasi kolektif lintas form (misal: validasi duplikasi item dan batas kuota).
- [ ] **Database Concurrency**: Mengetahui cara menggabungkan validasi form dengan `transaction.atomic()` dan `select_for_update()` untuk mencegah race condition.
- [ ] **Secure File Upload**: Mampu memvalidasi berkas upload menggunakan pemeriksaan Magic Bytes biner dan pembatasan ukuran berkas, bukan sekadar memeriksa ekstensi nama file.
- [ ] **CSRF Protection**: Memahami pola Double-Submit Cookie yang digunakan Django dan pentingnya token form pada setiap mutasi POST/PUT/DELETE.
