# BAB-03-QuerySet-Mastery-Database-Performance-Optimization: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang sebagai instrumen evaluasi komprehensif, validasi konseptual, dan pengujian keterampilan praktis terkait evaluasi QuerySet, eliminasi problem $N+1$, optimasi memori via lazy loading / chunking, indeks database, serta eksekusi kueri agregasi tingkat lanjut di Django ORM.

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1.1: Karakteristik Evaluasi QuerySet
**Pertanyaan:** Kapan persisnya sebuah `QuerySet` di Django ORM dievaluasi dan mengeksekusi perintah SQL `SELECT` ke database engine?
- A. Saat method chaining dilakukan, seperti `Order.objects.filter(status='PAID').order_by('-created_at')`.
- B. Hanya saat memanggil method `.all()`.
- C. Saat QuerySet diiterasi (`for item in qs`), dipotong dengan slice bernilai step (`qs[::2]`), dipanggil fungsi `len(qs)`, `list(qs)`, `bool(qs)`, atau saat serialisasi cache/pickle.
- D. Tepat saat model class diimpor di `views.py`.

**Kunci Jawaban:** **C**  
**Pembahasan Teknis:**  
Django QuerySet bersifat *lazy* (tertunda). QuerySet hanya merepresentasikan pohon ekspresi SQL (`django.db.models.sql.query.Query`) sampai terjadi aksi yang memerlukan evaluasi nyata (*iteration*, pemanggilan `len()`, pengecekan kebenaran `bool()`, `repr()`, atau casting eksplisit seperti `list()`). Method chaining seperti `.filter()` atau `.exclude()` hanya mengembalikan salinan objek QuerySet baru dengan klausa `WHERE` yang dimutasi tanpa menyentuh soket koneksi database.

---

### Soal 1.2: Perbedaan Fundamental `select_related` vs `prefetch_related`
**Pertanyaan:** Kapan Anda **wajib** menggunakan `prefetch_related` alih-alih `select_related`?
- A. Ketika relasi yang diambil berupa `ForeignKey` non-nullable (One-to-Many dari sisi anak).
- B. Ketika relasi bertipe `OneToOneField`.
- C. Ketika relasi berupa `ManyToManyField` atau relasi balik `ForeignKey` (reverse relation / reverse Many-to-One).
- D. Ketika database engine yang digunakan adalah PostgreSQL.

**Kunci Jawaban:** **C**  
**Pembahasan Teknis:**  
`select_related` bekerja melalui mekanisme SQL `JOIN` (biasanya `INNER JOIN` atau `LEFT OUTER JOIN`) langsung di query tunggal. Ini efisien hanya untuk relasi bertipe *single-valued relationship* (`ForeignKey` forward dan `OneToOneField`). Sebaliknya, untuk relasi bernilai banyak (multi-valued) seperti `ManyToManyField` dan *reverse ForeignKey*, penggunaan SQL `JOIN` akan melipatgandakan baris hasil secara kartesian (*Cartesian product*). Oleh karena itu, `prefetch_related` digunakan untuk mengeksekusi kueri terpisah (menggunakan operator `IN (...)`) dan menyatukan hasilnya di level Python memory space.

---

### Soal 1.3: Proyeksi Kolom dengan `only()` dan `defer()`
**Pertanyaan:** Apa dampak performa dan perilaku runtime jika sebuah field yang di-`defer()` kemudian diakses di dalam loop template/Python?
- A. Muncul exception `AttributeError`.
- B. Django ORM mengeksekusi satu kueri SQL tambahan secara sinkron untuk setiap akses field per instance (*deferred loading penalty*), memicu pola $N+1$ terselubung.
- C. Field tersebut otomatis mengembalikan nilai `None` tanpa query database.
- D. Django mengabaikan `defer()` dan langsung memuat seluruh kolom saat evaluasi pertama.

**Kunci Jawaban:** **B**  
**Pembahasan Teknis:**  
`defer(*fields)` menginstruksikan ORM untuk mengecualikan kolom tertentu (misal kolom `TextField` berukuran gigantis seperti `payload_json` atau log) dari klausa `SELECT`. Namun, instance model tetap menyimpan proxy atribut. Jika atribut tersebut diakses di runtime, Django secara otomatis melakukan query `SELECT "field" FROM "table" WHERE "id" = %s` secara ad-hoc per baris. Jika dipanggil di dalam loop, ini memicu degradasi performa $N+1$.

---

### Soal 1.4: Efisiensi Pengecekan Eksistensi Data
**Pertanyaan:** Potongan kode mana yang paling optimal untuk memeriksa apakah setidaknya ada satu transaksi dengan status `FAILED` di database?
- A. `if len(Transaction.objects.filter(status='FAILED')) > 0:`
- B. `if Transaction.objects.filter(status='FAILED').count() > 0:`
- C. `if Transaction.objects.filter(status='FAILED').exists():`
- D. `if bool(Transaction.objects.filter(status='FAILED')):`

**Kunci Jawaban:** **C**  
**Pembahasan Teknis:**  
- `len(qs)` memuat seluruh baris transaksi yang gagal ke dalam memory cache Python sebelum menghitung panjang list.
- `bool(qs)` memuat cache seluruh baris atau mengeksekusi evaluasi penuh.
- `.count()` mengeksekusi `SELECT COUNT(*) FROM table WHERE status = 'FAILED'`, yang mengharuskan database engine memindai seluruh indeks atau baris yang cocok.
- `.exists()` mengeksekusi `SELECT (1) AS "a" FROM table WHERE status = 'FAILED' LIMIT 1`. Engine database langsung berhenti mencari begitu menemukan baris pertama yang cocok, menghasilkan cost I/O dan eksekusi minimal.

---

### Soal 1.5: Batch Ingestion via `bulk_create`
**Pertanyaan:** Apa batasan arsitektural yang terjadi secara default saat mengeksekusi `Model.objects.bulk_create(instances)` di Django ORM standar?
- A. Tidak mendukung penyimpanan lebih dari 100 baris.
- B. Sinyal `pre_save` dan `post_save` serta custom method `Model.save()` tidak dipicu (*bypassed*).
- C. Data otomatis di-commit tanpa bisa dibungkus dalam blok `transaction.atomic()`.
- D. Tidak dapat bekerja pada tabel yang memiliki primary key tipe `UUIDField`.

**Kunci Jawaban:** **B**  
**Pembahasan Teknis:**  
`bulk_create` dirancang untuk throughput tinggi dengan mentranslasikan ratusan atau ribuan objek menjadi satu query SQL `INSERT INTO ... VALUES (...), (...), (...)`. Demi efisiensi dan eliminasi overhead iterasi Python, Django secara eksplisit melewati siklus lifecycle `instance.save()`, sehingga sinyal `pre_save` dan `post_save` tidak pernah dipanggil. Jika aplikasi mengandalkan sinyal untuk auditing atau pembuatan relasi sekunder, logika tersebut harus dijalankan manual.

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 2.1: Mengontrol Filter Prefetch dengan `Prefetch()` Object
Perhatikan model dan skenario kueri berikut:

```python
class Store(models.Model):
    name = models.CharField(max_length=100)

class Product(models.Model):
    store = models.ForeignKey(Store, related_name='products', on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
```

**Pertanyaan:** Kita ingin memuat semua toko (`Store`), namun pada masing-masing toko kita hanya ingin memuat produk aktif (`is_active=True`) dengan urutan `price` termurah ke termahal, dan menyimpannya dalam atribut kustom `active_products`. Bagaimana sintaksis Django ORM yang presisi dan efisien?

- A.
  ```python
  Store.objects.prefetch_related(
      Prefetch(
          'products',
          queryset=Product.objects.filter(is_active=True).order_by('price'),
          to_attr='active_products'
      )
  )
  ```
- B.
  ```python
  Store.objects.filter(products__is_active=True).select_related('products')
  ```
- C.
  ```python
  Store.objects.prefetch_related('products').filter(products__is_active=True)
  ```
- D.
  ```python
  Store.objects.annotate(
      active_products=FilteredRelation('products', condition=Q(products__is_active=True))
  )
  ```

**Kunci Jawaban:** **A**  
**Pembahasan Teknis:**  
Menggunakan objek `django.db.models.Prefetch` memungkinkan kustomisasi QuerySet prefetch secara granular: menyaring hanya produk yang aktif, menentukan order eksekusi SQL kueri kedua, dan memetakan hasilnya ke list terpisah di memori Python via `to_attr='active_products'` tanpa memutasi cache default `store.products.all()`.

---

### Soal 2.2: Mitigasi Out-Of-Memory (OOM) via `iterator()`
Perhatikan potongan kode untuk pemrosesan 2.000.000 data log audit:

```python
# Kode Bermasalah
logs = AuditLog.objects.filter(is_archived=False)
for log in logs:
    process_audit(log)
```

Server mengalami crash dengan error kernel *Linux OOM Killer*. Mengapa kode di atas memicu OOM, dan bagaimana implementasi perbaikan menggunakan `iterator()` dengan chunking?

**Jawaban & Analisis Mendalam:**
1. **Penyebab OOM:**  
   Ketika objek `logs` diiterasi tanpa `iterator()`, Django ORM mengisi internal cache QuerySet (`logs._result_cache`) dengan seluruh 2 juta instance model Python yang diinisialisasi sekaligus. Setiap instance model Django memiliki overhead memori signifikan (atribut internal, tracking state, descriptor). Akumulasi memori untuk jutaan objek melebihi kapasitas RAM container/server.
2. **Solusi Optimasi:**  
   Gunakan `.iterator(chunk_size=N)`. Method ini menggunakan server-side database cursor (atau fetch streaming per batch sesuai kapabilitas driver DB) dan **tidak menyimpan objek ke `_result_cache`**.
   ```python
   # Kode Optimal
   logs = AuditLog.objects.filter(is_archived=False).iterator(chunk_size=5000)
   for log in logs:
       process_audit(log)
   ```
   Setelah objek `log` diproses dan keluar dari scope iterasi, Python Garbage Collector dapat langsung merebut kembali (*reclaim*) memori tersebut.

---

### Soal 2.3: Atomic Update vs Race Condition menggunakan `F()` Expression
Dua worker Celery memproses pengurangan stok produk secara bersamaan untuk `Product.objects.get(id=1)` yang memiliki `stock = 10`.

Worker A:
```python
p = Product.objects.get(id=1)
p.stock -= 2
p.save()
```
Worker B:
```python
p = Product.objects.get(id=1)
p.stock -= 3
p.save()
```

**Pertanyaan:** Jelaskan race condition yang terjadi di tingkat SQL, dan tuliskan perbaikan kodenya menggunakan `F()` expression serta validasi batas minimum stok!

**Jawaban & Analisis Mendalam:**
1. **Analisis Masalah (Lost Update Anomaly):**  
   Kedua worker membaca snapshot nilai yang sama dari DB (`stock = 10`). Worker A menghitung di memori Python `10 - 2 = 8` lalu mengeksekusi `UPDATE product SET stock = 8 WHERE id = 1`. Worker B menghitung di memori Python `10 - 3 = 7` lalu mengeksekusi `UPDATE product SET stock = 7 WHERE id = 1`. Hasil akhir adalah 7, padahal total pengurangan adalah 5 (stok seharusnya 5). Terjadi kehilangan mutasi data (*lost update*).
2. **Solusi Menggunakan `F()` Expression:**  
   Ekspresi `F()` mendelegasikan kalkulasi langsung ke database engine pada level atomic row-lock saat write:
   ```python
   from django.db.models import F

   # Update atomik pada level database engine
   updated_rows = Product.objects.filter(id=1, stock__gte=qty_to_deduct).update(
       stock=F('stock') - qty_to_deduct
   )
   if updated_rows == 0:
       raise OutOfStockError("Stok tidak mencukupi atau produk tidak ditemukan.")
   ```
   Query yang dieksekusi: `UPDATE product SET stock = stock - 2 WHERE id = 1 AND stock >= 2;`. Ini mengeliminasi race condition tanpa overhead distributed lock jika kondisinya sederhana.

---

### Soal 2.4: Agregasi Bersyarat Menggunakan `Conditional Aggregation`
**Pertanyaan:** Diberikan model `Invoice(customer, amount, status)`. Bagaimana cara mengambil daftar seluruh customer beserta dua nilai anotasi dalam **satu kueri SQL tunggal**: total nominal invoice yang berstatus `'PAID'` dan total nominal invoice yang berstatus `'PENDING'`?

**Jawaban & Kode Solusi:**
Gunakan fungsi `Sum` yang dikombinasikan dengan argumen `filter=Q(...)`:

```python
from django.db.models import Sum, Q, DecimalField
from django.db.models.functions import Coalesce
from decimal import Decimal

customers_summary = Customer.objects.annotate(
    total_paid=Coalesce(
        Sum('invoices__amount', filter=Q(invoices__status='PAID')),
        Decimal('0.00'),
        output_field=DecimalField()
    ),
    total_pending=Coalesce(
        Sum('invoices__amount', filter=Q(invoices__status='PENDING')),
        Decimal('0.00'),
        output_field=DecimalField()
    )
)
```
**SQL Terjemahan:**
```sql
SELECT "customer"."id", "customer"."name",
       COALESCE(SUM(CASE WHEN "invoices"."status" = 'PAID' THEN "invoices"."amount" ELSE NULL END), 0.00) AS "total_paid",
       COALESCE(SUM(CASE WHEN "invoices"."status" = 'PENDING' THEN "invoices"."amount" ELSE NULL END), 0.00) AS "total_pending"
FROM "customer"
LEFT OUTER JOIN "invoice" AS "invoices" ON ("customer"."id" = "invoices"."customer_id")
GROUP BY "customer"."id", "customer"."name";
```

---

### Soal 2.5: Composite Indexing vs Ordering Query
Perhatikan model berikut:

```python
class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', '-created_at'], name='idx_status_created'),
        ]
```

**Pertanyaan:** Kueri ORM mana di bawah ini yang **dijamin** memanfaatkan indeks `idx_status_created` secara optimal tanpa melakukan in-memory sort (`Using filesort` pada MySQL atau `Sort` node di PostgreSQL)?
- A. `Order.objects.filter(created_at__gte=start_date).order_by('status')`
- B. `Order.objects.filter(status='COMPLETED').order_by('-created_at')`
- C. `Order.objects.filter(user=request.user).order_by('-created_at')`
- D. `Order.objects.all().order_by('status', 'created_at')`

**Kunci Jawaban:** **B**  
**Pembahasan Teknis:**  
B-Tree composite index mengevaluasi kolom dari kiri ke kanan (*leftmost prefix rule*). Indeks di atas diindeks berdasarkan `status` (equality check), lalu subtree terurut berdasarkan `created_at DESC`. Kueri B memfilter `status = 'COMPLETED'` (memilih node spesifik) kemudian membaca data yang sudah terurut secara descending pada field `created_at`, menghasilkan operasi `Index Scan` murni tanpa alokasi memori untuk sorting.

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Skenario)

### Skenario 3.1: Insiden Dashboard Analytics "Database Connection Pool Exhaustion"
* **Konteks:** Sistem e-commerce memiliki endpoint `/api/v1/merchant/dashboard/` yang dipanggil 500 merchant setiap menit. Rata-rata latency melonjak dari 150ms menjadi 12.500ms, dan PgBouncer melaporkan error: `FATAL: remaining connection slots are reserved for non-replication superuser connections`.
* **Investigasi Masalah:**
  Ditemukan method serializer Django REST Framework berikut:
  ```python
  class MerchantDashboardView(APIView):
      def get(self, request):
          merchants = Merchant.objects.filter(is_active=True)[:50]
          data = []
          for m in merchants:
              data.append({
                  "id": m.id,
                  "name": m.name,
                  "total_orders": m.orders.count(),
                  "total_revenue": m.orders.filter(status='COMPLETED').aggregate(total=Sum('grand_total'))['total'] or 0,
                  "latest_order_date": m.orders.order_by('-created_at').first().created_at if m.orders.exists() else None,
              })
          return Response(data)
  ```
* **Akar Masalah (Root Cause):**
  Untuk 50 merchant, perulangan di atas mengeksekusi minimal:
  - 1 kueri utama untuk mengambil `Merchant`.
  - 50 kueri `COUNT(*)` untuk `total_orders`.
  - 50 kueri `SUM(grand_total)` untuk `total_revenue`.
  - 50 kueri `EXISTS` untuk pengecekan keberadaan order.
  - 50 kueri `SELECT ... ORDER BY created_at DESC LIMIT 1` untuk `latest_order_date`.  
  Total kueri yang dieksekusi per request adalah $1 + (50 \times 4) = 201$ kueri. Ketika 500 pengguna mengakses secara serempak, database menerima 100.500 kueri/menit, menghabiskan pool koneksi database.
* **Solusi Arsitektural & Refactoring:**
  Gunakan agregasi beranotasi dan `Subquery` / `OuterRef` untuk mereduksinya menjadi **1 kueri SQL tunggal**:

  ```python
  from django.db.models import Count, Sum, Q, Subquery, OuterRef, DecimalField
  from django.db.models.functions import Coalesce

  latest_order_subquery = Order.objects.filter(
      merchant=OuterRef('pk')
  ).order_by('-created_at').values('created_at')[:1]

  merchants_optimized = Merchant.objects.filter(is_active=True)[:50].annotate(
      annotated_total_orders=Count('orders', distinct=True),
      annotated_total_revenue=Coalesce(
          Sum('orders__grand_total', filter=Q(orders__status='COMPLETED')),
          0,
          output_field=DecimalField()
      ),
      annotated_latest_order_date=Subquery(latest_order_subquery)
  ).values('id', 'name', 'annotated_total_orders', 'annotated_total_revenue', 'annotated_latest_order_date')
  ```
  **Hasil:** Eksekusi berkurang dari 201 kueri menjadi 1 kueri. Latency turun dari 12.5 detik ke 42ms.

---

### Skenario 3.2: Batch Worker OOM Crash saat Ekspor Laporan Bulanan
* **Konteks:** Sebuah background task Celery bertugas membuat file CSV rekap seluruh transaksi bulanan (berkisar 1.500.000 record) untuk finance. Task ini selalu mati dengan status `WorkerLostError: Process exited prematurely: signal 9 (SIGKILL)`.
* **Investigasi Masalah:**
  Kode task implementasi awal:
  ```python
  @shared_task
  def generate_monthly_report_csv(month, year):
      transactions = Transaction.objects.filter(
          created_at__year=year,
          created_at__month=month
      ).select_related('customer', 'payment_method')

      csv_path = f"/tmp/report_{year}_{month}.csv"
      with open(csv_path, 'w', newline='') as f:
          writer = csv.writer(f)
          writer.writerow(['ID', 'Customer', 'Amount', 'Date'])
          for tx in transactions:
              writer.writerow([tx.id, tx.customer.email, tx.amount, tx.created_at.isoformat()])
      return csv_path
  ```
* **Akar Masalah (Root Cause):**
  1. `transactions` mengevaluasi 1,5 juta baris sekaligus dan menyimpannya di internal memory cache Django.
  2. `select_related('customer', 'payment_method')` menginstansiasi 3 objek model Python (`Transaction`, `Customer`, `PaymentMethod`) per baris data, mengonsumsi lebih dari 4.500.000 objek di memori RAM (~3.2 GB RAM). Container Celery memiliki limit memori 1.5 GB, sehingga langsung di-terminate oleh kernel Linux via SIGKILL.
* **Solusi Arsitektural & Refactoring:**
  Gunakan pemangkasan atribut via `values_list()` yang mengembalikan tuple Python primitif (tanpa overhead class Model Django), dikombinasikan dengan `iterator(chunk_size=10000)`:

  ```python
  @shared_task
  def generate_monthly_report_csv(month, year):
      transactions = Transaction.objects.filter(
          created_at__year=year,
          created_at__month=month
      ).values_list(
          'id', 'customer__email', 'amount', 'created_at'
      ).iterator(chunk_size=10000)

      csv_path = f"/tmp/report_{year}_{month}.csv"
      with open(csv_path, 'w', newline='', buffering=65536) as f:
          writer = csv.writer(f)
          writer.writerow(['ID', 'Customer', 'Amount', 'Date'])
          for row in transactions:
              writer.writerow([row[0], row[1], row[2], row[3].isoformat()])
      return csv_path
  ```
  **Hasil:** Penggunaan memori konstan stabil pada ~45 MB RAM sepanjang pemrosesan 1,5 juta baris data tanpa crash.

---

### Skenario 3.3: Deadlock pada High-Concurrency Flash Sale Checkout
* **Konteks:** Saat flash sale dimulai, sistem menerima 2.000 checkout per detik pada 10 produk unggulan. Database PostgreSQL mencatat lonjakan lonjakan exception: `django.db.utils.OperationalError: deadlock detected`.
* **Investigasi Masalah:**
  Ditemukan logika checkout berikut:
  ```python
  @transaction.atomic
  def checkout(cart_items, user):
      order = Order.objects.create(user=user)
      for item in cart_items:
          # Lock baris produk untuk update stok
          product = Product.objects.select_for_update().get(id=item.product_id)
          if product.stock < item.quantity:
              raise InsufficientStockError()
          product.stock -= item.quantity
          product.save()
          OrderItem.objects.create(order=order, product=product, quantity=item.quantity)
  ```
* **Akar Masalah (Root Cause):**
  `cart_items` yang dikirim pengguna memiliki urutan produk acak.
  - Transaksi 1 mengunci Product A, lalu meminta lock Product B.
  - Transaksi 2 mengunci Product B, lalu meminta lock Product A.  
  Kondisi siklus tunggu (*circular wait*) ini memicu database mendeteksi deadlock dan memutus salah satu transaksi secara paksa.
* **Solusi Arsitektural & Refactoring:**
  1. Lakukan pengurutan deterministik ID produk (`order_by('id')`) sebelum melakukan `select_for_update()`, sehingga semua transaksi mengunci baris dalam urutan yang identik secara universal di seluruh thread.
  2. Lakukan batch locking untuk semua produk di keranjang belanja dalam 1 statement SQL.

  ```python
  @transaction.atomic
  def checkout(cart_items, user):
      # 1. Ekstrak dan urutkan ID produk secara deterministik
      item_map = {item.product_id: item.quantity for item in cart_items}
      sorted_product_ids = sorted(item_map.keys())

      # 2. Batch lock produk secara terurut (menghilangkan circular wait)
      locked_products = list(
          Product.objects.select_for_update()
          .filter(id__in=sorted_product_ids)
          .order_by('id')
      )

      # 3. Validasi stok untuk semua item
      for product in locked_products:
          qty = item_map[product.id]
          if product.stock < qty:
              raise InsufficientStockError(f"Stok produk {product.name} tidak mencukupi.")

      # 4. Update stok secara atomik
      for product in locked_products:
          qty = item_map[product.id]
          product.stock -= qty
          product.save(update_fields=['stock'])

      # 5. Buat order dan relasi item secara bulk
      order = Order.objects.create(user=user)
      order_items = [
          OrderItem(order=order, product=product, quantity=item_map[product.id])
          for product in locked_products
      ]
      OrderItem.objects.bulk_create(order_items)
      return order
  ```
  **Hasil:** Deadlock tereliminasi 100% karena semua transaksi mengikuti protokol hierarki penguncian resource searah.

---

## Bagian 4: Practical Chapter Challenge (1 Tantangan)

### Judul Tantangan: Real-Time High-Performance Ledger Audit & Reconciliation Engine

#### Latar Belakang & Masalah
Sebuah platform fintech memiliki tabel ledger transaksi `Account` dan `LedgerEntry`. Sistem memerlukan modul audit harian untuk memvalidasi saldo rekening nasabah terhadap mutasi debit dan kredit secara real-time. Jika dihitung menggunakan model loop biasa, sistem membutuhkan waktu 45 menit untuk 500.000 rekening dan sering mengalami timeout.

#### Spesifikasi Model
```python
from django.db import models

class Account(models.Model):
    account_number = models.CharField(max_length=32, unique=True, db_index=True)
    current_balance = models.DecimalField(max_digits=18, decimal_places=4)
    status = models.CharField(max_length=20, default='ACTIVE')
    last_reconciled_at = models.DateTimeField(null=True, blank=True)

class LedgerEntry(models.Model):
    account = models.ForeignKey(Account, related_name='entries', on_delete=models.CASCADE)
    entry_type = models.CharField(max_length=6, choices=[('DEBIT', 'Debit'), ('CREDIT', 'Credit')])
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    is_settled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

#### Persyaratan Tantangan (Requirements)
Anda diminta menulis fungsi `reconcile_active_accounts()` dengan kriteria ketat berikut:
1. **Zero N+1 Query:** Seluruh verifikasi rekonsiliasi untuk 50.000 akun aktif batch pertama harus dieksekusi dengan maksimal **2 kueri SQL** (1 kueri verifikasi agregasi beranotasi, 1 kueri batch update).
2. **Kalkulasi Akurat di DB:** Saldo rekonsiliasi dihitung di dalam DB engine menggunakan rumus:  
   $$\text{Calculated Balance} = \sum(\text{CREDIT}) - \sum(\text{DEBIT})$$  
   hanya untuk entry yang `is_settled=True`.
3. **Deteksi Anomali:** Identifikasi akun yang mengalami perbedaan antara `current_balance` dan `calculated_balance` (selisih $\neq 0$). Kembalikan dictionary akun anomali tersebut tanpa memuat seluruh instance model ke memori.
4. **Batch Update Timestamp:** Untuk akun yang valid (tidak anomali), perbarui field `last_reconciled_at` dengan timestamp saat ini menggunakan operasi batch update.

#### Solusi Implementasi Lengkap

```python
from django.db import models
from django.db.models import Sum, Q, F, Case, When, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from decimal import Decimal

def reconcile_active_accounts(batch_size=50000):
    now = timezone.now()
    
    # Kueri 1: Hitung calculated balance di level database menggunakan Conditional Aggregation
    # dan hitung discrepancy (current_balance - calculated_balance) secara inline.
    reconciliation_qs = Account.objects.filter(status='ACTIVE')[:batch_size].annotate(
        calculated_balance=Coalesce(
            Sum(
                Case(
                    When(entries__entry_type='CREDIT', then=F('entries__amount')),
                    When(entries__entry_type='DEBIT', then=-F('entries__amount')),
                    default=Decimal('0.0000'),
                    output_field=DecimalField(max_digits=18, decimal_places=4)
                ),
                filter=Q(entries__is_settled=True)
            ),
            Decimal('0.0000'),
            output_field=DecimalField(max_digits=18, decimal_places=4)
        )
    ).annotate(
        balance_discrepancy=F('current_balance') - F('calculated_balance')
    ).values(
        'id', 'account_number', 'current_balance', 'calculated_balance', 'balance_discrepancy'
    )

    anomalous_accounts = []
    valid_account_ids = []

    # Iterasi hasil values() (kamus data ringan, konsumsi memori minimal)
    for record in reconciliation_qs.iterator(chunk_size=5000):
        if record['balance_discrepancy'] != Decimal('0.0000'):
            anomalous_accounts.append({
                'account_number': record['account_number'],
                'current_balance': record['current_balance'],
                'calculated_balance': record['calculated_balance'],
                'discrepancy': record['balance_discrepancy']
            })
        else:
            valid_account_ids.append(record['id'])

    # Kueri 2: Batch update timestamp hanya untuk akun yang tervalidasi cocok
    if valid_account_ids:
        Account.objects.filter(id__in=valid_account_ids).update(last_reconciled_at=now)

    return {
        "processed_count": len(valid_account_ids) + len(anomalous_accounts),
        "valid_count": len(valid_account_ids),
        "anomalies_count": len(anomalous_accounts),
        "anomalies": anomalous_accounts
    }
```

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan matriks checklist ini untuk memverifikasi kesiapan operasional Anda sebelum mendeploy kode berbasis Django ORM ke staging/production:

| Konsep & Keterampilan Optimasi | Status Pemahaman | Target Verifikasi Mandiri |
| :--- | :---: | :--- |
| **Lazy Evaluation Mechanics** | [ ] | Paham kapan QuerySet memicu SQL I/O dan kapan hanya membangun representasi query internal. |
| **Eliminasi N+1 via `select_related`** | [ ] | Mampu mengidentifikasi relasi foreign key/one-to-one dan menggabungkannya via SQL `JOIN`. |
| **Eliminasi N+1 via `prefetch_related`** | [ ] | Mampu menggunakan objek `Prefetch` dengan kustomisasi queryset berfilter untuk relasi reverse dan M2M. |
| **Memory Optimization (`only` & `defer`)** | [ ] | Mampu memangkas beban transmisi kolom berukuran besar seperti text payload/JSON. |
| **Large Dataset Streaming (`iterator`)** | [ ] | Menggunakan `iterator(chunk_size=...)` untuk mencegah memori OOM pada batch processing skala jutaan baris. |
| **Atomic Row Operations (`F` Expressions)** | [ ] | Menghindari race condition (lost update) tanpa blocking lock yang berat. |
| **Kueri Terfilter & Agregasi Kompleks** | [ ] | Mampu mengombinasikan `Sum`/`Count` dengan klausa `filter=Q(...)` dan `Coalesce` dalam satu kueri. |
| **Composite Indexing & Query Alignment** | [ ] | Memastikan klausa `filter()` dan `order_by()` sejalan dengan urutan index B-Tree (*leftmost prefix rule*). |
| **Deadlock Prevention Protocol** | [ ] | Mengurutkan pemanggilan `select_for_update()` secara deterministik pada transaksi bersamaan. |
| **Batch Ingestion & Mutation** | [ ] | Menguasai penggunaan `bulk_create`, `bulk_update`, dan `.update()` massal tanpa iterasi loop model. |
