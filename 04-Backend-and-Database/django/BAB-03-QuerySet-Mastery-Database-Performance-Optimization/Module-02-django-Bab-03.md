# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Kategori: 04-Backend-and-Database
### Topik: Django
#### BAB-03: QuerySet Mastery & Database Performance Optimization
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Menguasai arsitektur internal Django ORM, termasuk kompilasi `QuerySet`, siklus hidup `SQLCompiler`, alokasi `_result_cache`, dan eksekusi kueri pada level DBAPI driver.
- Mengeliminasi masalah $N+1$ query secara deterministik menggunakan kombinasi `select_related`, `prefetch_related`, dan objek kustom `Prefetch` dengan `to_attr`.
- Mengimplementasikan teknik komputasi berbasis database engine menggunakan `Subquery`, `OuterRef`, `Exists`, `F()`, `Case-When`, dan Window Functions guna meminimalkan alokasi memori di level Python runtime.
- Mendesain arsitektur database multi-node dengan *Database Routers* kustom untuk pemisahan *Read/Write* (*Primary-Replica*), penanganan *replication lag*, dan manajemen *persistent connections*.
- Menerapkan mekanisme proteksi konkurensi tingkat lanjut menggunakan *Pessimistic Locking* (`select_for_update`) dan *Optimistic Locking* untuk mencegah anomali *Lost Updates* dan *Race Conditions* pada transaksi finansial throughput tinggi.
- Mendiagnosis dan mengoptimalkan kueri lambat secara langsung dari Django menggunakan `EXPLAIN ANALYZE`, pembuatan indeks komposit/fungsional (*Partial Indexes*, *GIN*, *BRIN*), serta strategi *chunked streaming* via `.iterator()`.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda harus memahami:
- Siklus hidup request-response standar Django dan konfigurasi dasar `settings.py`.
- Sintaks dasar Django Models (`models.Model`, tipe field relasional: `ForeignKey`, `ManyToManyField`, `OneToOneField`).
- Dasar relational database (PostgreSQL direkomendasikan): ACID transactions, isolation levels, locking mechanisms, B-Tree index fundamentals.
- Konsep dasar konkurensi Python (GIL, threads, asynchronous event loop) dan interaksi DBAPI (psycopg2/psycopg3).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Anatomi Internal QuerySet dan Siklus Kompilasi SQL
Sebuah `QuerySet` di Django bersifat *lazy*. Instansiasi `QuerySet` tidak memicu I/O ke database. Secara internal, `QuerySet` membungkus sebuah instance dari kelas `django.db.models.sql.query.Query`.

```
[ Developer Code ]
       |
       v
QuerySet(model=Order)
       |  .filter(...) / .annotate(...)
       v
Cloned QuerySet (Immutability Pattern)
       |  Memodifikasi internal self.query (django.db.models.sql.Query)
       v
Evaluasi Terjadi (Iterasi, Len, Slicing konkret, repr, bool)
       |
       +--> Cek self._result_cache
       |      |-- [HIT]  --> Kembalikan data dari Python memory
       |      +-- [MISS] --> Lanjutkan ke Engine Kompilasi
       v
SQLCompiler Pipeline (django.db.models.sql.compiler.SQLCompiler)
       |-- as_sql() -> Membangun string SQL mentah + parameter binding (mencegah SQL Injection)
       |-- get_converters() -> Konversi tipe data native database ke tipe Python (UUID, Datetime, Decimal)
       v
Database Backend (django.db.backends.<engine>.base.DatabaseWrapper)
       |-- Mendapatkan connection cursor (menggunakan pool atau persistent socket)
       |-- cursor.execute(sql, params) via DBAPI driver (misal: psycopg)
       v
Materialisasi Model Instantiation
       |-- Model._base_manager.model(*row) -> Instansiasi objek Python per baris
       +-- Menyimpan array model ke self._result_cache
```

1. **Immutability via Cloning**: Setiap kali method mutator (`.filter()`, `.exclude()`, `.annotate()`) dipanggil, Django tidak memodifikasi `QuerySet` asli. Method `_clone()` dipanggil, menyalin referensi `self.query` melalui deep copy terstruktur untuk mencegah *side-effects* lintas thread atau fungsi.
2. **Kompilasi SQL (`SQLCompiler`)**: Ketika evaluasi dipicu, kelas `SQLCompiler` mentransformasikan pohon ekspresi `WhereNode`, `Join`, dan agregasi menjadi dialek SQL spesifik target (misal: PostgreSQL vs MySQL). Pada tahap ini, alias tabel (`T1`, `T2`) ditetapkan secara deterministik.
3. **Konversi Tipe Data Database ke Python**: `SQLCompiler.get_converters()` menentukan converter per kolom (misal: memetakan tipe PostgreSQL `timestamptz` ke `datetime.datetime` dengan `zoneinfo`).
4. **Memory Footprint & Result Cache**: Saat baris dikembalikan, Django menginstansiasi objek model untuk setiap baris data dan menyimpannya di `_result_cache`. Jika kueri mengembalikan 100.000 baris, seluruh 100.000 instansiasi model Python akan ditahan dalam heap memory, yang berpotensi memicu Out-Of-Memory (OOM) error jika tidak ditangani dengan streaming iterator.

#### B. Mekanisme Prefetching: Join vs Two-Phase Batch Fetch
Django membedakan optimasi eager-loading menjadi dua strategi arsitektural:

1. **`select_related` (SQL JOIN Injection)**:
   - Berlaku untuk relasi `single-valued` (`ForeignKey`, `OneToOneField`).
   - `SQLCompiler` memodifikasi klausa `FROM` dengan menambahkan `INNER JOIN` atau `LEFT OUTER JOIN`.
   - Mengambil seluruh kolom model terkait dalam **satu panggilan round-trip database tunggal**.
   - Menghasilkan payload data tabular yang lebar (duplikasi kolom jika struktur relasional denormalisasi).

2. **`prefetch_related` (Normalized Two-Phase Batch Fetching)**:
   - Berlaku untuk relasi `multi-valued` (`ManyToManyField`, reverse `ForeignKey`) maupun `single-valued`.
   - Melakukan **minimal 2 kueri terpisah**:
     1. Kueri pertama mengambil entitas induk (misal: `SELECT * FROM orders WHERE ...`).
     2. Django mengekstrak seluruh primary key dari entitas induk ke dalam memori Python: `[101, 102, 103, ...]`.
     3. Kueri kedua mengeksekusi batch fetch menggunakan klausa `IN`: `SELECT * FROM order_items WHERE order_id IN (101, 102, 103, ...)`.
     4. Objek Python `Prefetch` memetakan baris anak kembali ke atribut masing-masing objek induk dalam memori menggunakan struktur data dictionary lookup $O(1)$.

---

### 4. Why & What

| Fitur / Pola | Apa itu? (*What*) | Mengapa Diperlukan? (*Why*) |
| :--- | :--- | :--- |
| **`select_related`** | SQL-level `JOIN` eager loading untuk relasi 1:1 dan M:1. | Menghilangkan latency $N$ kali network round-trip saat mengakses atribut relasional langsung. |
| **`prefetch_related`** | Application-level multi-phase fetching untuk relasi 1:M dan M:M. | Mencegah ledakan data (*Cartesian Product explosion*) yang terjadi jika relasi M:M dipaksakan menggunakan SQL `JOIN`. |
| **`Prefetch(..., to_attr=...)`** | Konstruktor prefetch kustom yang menyaring queryset anak dan menyimpannya ke atribut list baru. | Memungkinkan filtering child record tanpa merusak cache internal relasi bawaan dan menghindari re-querying database. |
| **`Subquery` & `OuterRef`** | Penanaman SQL subquery berkorelasi langsung ke dalam klausa `SELECT` atau `WHERE`. | Memungkinkan agregasi dan kalkulasi inline per-baris langsung pada database engine tanpa harus memuat seluruh dataset anak ke aplikasi. |
| **`F()` Expressions** | Representasi referensi kolom database langsung dalam kueri. | Memindahkan komputasi atomik ke server database (mencegah race condition read-then-write) dan menghemat bandwidth. |
| **Database Router** | Komponen infrastruktur Django untuk menentukan targeting koneksi SQL (Read vs Write). | Skalabilitas horizontal beban read melalui replikasi PostgreSQL tanpa mengubah struktur service layer kode aplikasi. |

---

### 5. How (Workflow Detail)

#### Workflow Eksekusi Advanced QuerySet dengan Subquery & Locking
Berikut urutan operasi dari instansiasi query hingga komit transaksi tingkat produksi:

```
[ Application Layer ]
        |
   1. Buat Subquery & OuterRef
        |
   2. Pasang Filter, F-Expressions, dan Annotations
        |
   3. Inisiasi Transaksi Atomik: transaction.atomic()
        |
   4. Terapkan select_for_update(nowait=False, of=('self',))
        |
[ Django ORM Engine ]
        |
   5. SQLCompiler menghasilkan string SQL tunggal berkorelasi
        |
[ Database Engine (PostgreSQL) ]
        |
   6. Parse, Analyze, & Optimize Execution Plan
        |
   7. Eksekusi Index Scan / Bitmap Heap Scan
        |
   8. Mengakuisisi Row-Level Exclusive Lock (FOR UPDATE)
        |
   9. Return tuple hasil ke Driver DBAPI
        |
[ Python Runtime ]
        |
   10. Deserialisasi native byte buffers -> Objek Model Python
        |
   11. Manipulasi Atribut di Memori
        |
   12. Model.save(update_fields=[...]) -> SQL UPDATE
        |
   13. Transaksi Commit -> Row Locks Dilepaskan
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Perpustakaan dan Sistem Peminjaman
- **Query Dasar ($N+1$ Trap)**: Anda mengambil 10 buku dari rak. Untuk setiap buku, Anda berjalan ke meja pustakawan 10 kali secara terpisah hanya untuk menanyakan nama belakang penulis buku tersebut. (10 network round-trips).
- **`select_related`**: Anda meminta pustakawan membawakan 10 buku dengan kartu identitas penulis yang sudah diikat langsung pada masing-masing buku menggunakan satu troli. (1 Query dengan `JOIN`).
- **`prefetch_related`**: Anda mengambil 10 buku sekaligus. Pustakawan mencatat seluruh 10 ID buku tersebut, pergi ke arsip data penulis dalam satu kali jalan, mengambil seluruh data penulis yang relevan, lalu mencocokkannya ke buku Anda di atas meja. (2 Queries terpisah yang efisien).

#### Diagram Arsitektur Database Router & Replication Lag Mitigation

```
                         [ Django Application Tier ]
                                      |
                     +---------------------------------+
                     | Custom Database Router          |
                     | - db_for_write() -> 'default'   |
                     | - db_for_read()  -> Dynamic     |
                     +---------------------------------+
                                      |
                  +-------------------+-------------------+
                  |                                       |
           (Writes & Pinned Reads)                   (Bulk Reads)
                  |                                       |
                  v                                       v
         +-----------------+                     +-----------------+
         | Primary (Write) |                     | Replica (Read)  |
         | PostgreSQL Node |                     | PostgreSQL Node |
         +-----------------+                     +-----------------+
                  |                                       ^
                  |-------- WAL Streaming Replication ----|
                  |         (Asynchronous - Lag ~50ms)    |
                  v                                       |
          [ Critical Write ]                              |
                  |                                       |
                  +-- Cookie/Cache: Set Pinning Window ---+
                      (Arahkan user read ke Primary selama
                       2 detik pasca-write untuk mencegah
                       stale read akibat replikasi)
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Demonstrasi $N+1$ vs Optimasi `select_related` & `prefetch_related`

```python
# models.py
from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=100)

class Product(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    price = models.DecimalField(max_digits=12, decimal_places=2)

class Tag(models.Model):
    name = models.CharField(max_length=50)
    products = models.ManyToManyField(Product, related_name='tags')
```

```python
# bad_practices.py
# N+1 Trap: Menghasilkan 1 + N + (N * M) kueri SQL
def render_catalog_naive():
    products = Product.objects.all()  # 1 kueri
    catalog_data = []
    for product in products:
        # Menghasilkan 1 kueri per iterasi loop untuk category (N kueri)
        cat_name = product.category.name 
        # Menghasilkan 1 kueri per iterasi loop untuk tags (N kueri)
        tags = [tag.name for tag in product.tags.all()] 
        catalog_data.append({'name': product.name, 'category': cat_name, 'tags': tags})
    return catalog_data

# good_practices.py
# Optimized: Menghasilkan tepat 2 kueri SQL, berapapun jumlah baris data
def render_catalog_optimized():
    products = Product.objects.select_related('category').prefetch_related('tags')
    catalog_data = []
    for product in products:
        # Mengambil dari _result_cache internal, 0 network call
        cat_name = product.category.name
        # Mengambil dari prefetch cache internal, 0 network call
        tags = [tag.name for tag in product.tags.all()]
        catalog_data.append({'name': product.name, 'category': cat_name, 'tags': tags})
    return catalog_data
```

#### B. Practical Enterprise Example: Financial Ledger & Order Processing Pipeline
Contoh arsitektur produksi untuk sistem pemrosesan saldo dompet digital (*Fintech*) dengan locking database deterministik, `Subquery`, dan conditional aggregation.

```python
# models.py
import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone

class Account(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account_number = models.CharField(max_length=32, unique=True, db_index=True)
    balance = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['account_number', 'is_active']),
        ]

class TransactionType(models.TextChoices):
    CREDIT = 'CREDIT', 'Credit'
    DEBIT = 'DEBIT', 'Debit'

class LedgerEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='ledger_entries')
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    entry_type = models.CharField(max_length=10, choices=TransactionType.choices)
    idempotency_key = models.CharField(max_length=128, unique=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-created_at']
```

```python
# services.py
from decimal import Decimal
from django.db import transaction, DatabaseError
from django.db.models import Subquery, OuterRef, Sum, Case, When, Value, DecimalField, Q
from .models import Account, LedgerEntry, TransactionType

class InsufficientFundsException(Exception):
    pass

class ConcurrencyLockException(Exception):
    pass

class LedgerService:
    @staticmethod
    def post_transaction(
        account_id: str,
        amount: Decimal,
        entry_type: TransactionType,
        idempotency_key: str
    ) -> LedgerEntry:
        """
        Mengeksekusi mutasi saldo secara thread-safe menggunakan Pessimistic Locking.
        Memanfaatkan select_for_update dengan update_fields atomik.
        """
        if amount <= Decimal('0.0000'):
            raise ValueError("Amount transaksi harus bernilai positif.")

        try:
            with transaction.atomic():
                # Kunci baris akun pada level database (SELECT ... FOR UPDATE)
                account = (
                    Account.objects
                    .select_for_update(nowait=False)
                    .get(id=account_id, is_active=True)
                )

                # Validasi proteksi saldo minus pada operasi debit
                if entry_type == TransactionType.DEBIT and account.balance < amount:
                    raise InsufficientFundsException(
                        f"Saldo tidak mencukupi. Saldo saat ini: {account.balance}, Dibutuhkan: {amount}"
                    )

                # Catat mutasi ledger
                entry = LedgerEntry.objects.create(
                    account=account,
                    amount=amount,
                    entry_type=entry_type,
                    idempotency_key=idempotency_key
                )

                # Mutasi nilai saldo menggunakan F expression untuk mengeliminasi in-memory race condition
                from django.db.models import F
                if entry_type == TransactionType.DEBIT:
                    account.balance = F('balance') - amount
                else:
                    account.balance = F('balance') + amount
                
                account.save(update_fields=['balance'])
                account.refresh_from_db(fields=['balance'])

                return entry

        except DatabaseError as e:
            # Mengisolasi deadlock atau lock wait timeout dari RDBMS
            raise ConcurrencyLockException("Gagal memperoleh row-level lock pada database.") from e

    @staticmethod
    def get_account_audit_report(account_qs):
        """
        Menghasilkan audit analitik performa tinggi menggunakan Subquery & Aggregasi Bersyarat
        tanpa memuat seluruh baris ledger ke dalam heap Python.
        """
        latest_entry_subquery = LedgerEntry.objects.filter(
            account=OuterRef('pk')
        ).order_by('-created_at').values('amount')[:1]

        return account_qs.annotate(
            latest_transaction_amount=Subquery(
                latest_entry_subquery, 
                output_field=DecimalField(max_digits=18, decimal_places=4)
            ),
            calculated_turnover=Sum(
                Case(
                    When(ledger_entries__entry_type=TransactionType.CREDIT, then='ledger_entries__amount'),
                    When(ledger_entries__entry_type=TransactionType.DEBIT, then=-F('ledger_entries__amount')),
                    default=Value(Decimal('0.0000')),
                    output_field=DecimalField(max_digits=18, decimal_places=4)
                )
            )
        ).filter(Q(calculated_turnover__isnull=False))
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Platform E-Commerce B2B dengan beban throughput transaksi tinggi:
- 10.000 request per detik (RPS) pada event Flash Sale.
- Volume database: 45 juta records baris pesanan (`orders`) dan 180 juta data item detail (`order_items`).
- Arsitektur Database: 1 Node Primary (Writer), 3 Node Read Replicas (Streaming Replication, delay 50-100ms).

#### Masalah (Root Cause Analysis)
1. **Cartesian Product OOM Crash**: Endpoint inventaris menggunakan kueri dengan nested `prefetch_related` tanpa batasan kolom (`only()` atau `defer()`), mengambil 50 relasi M:M, menyebabkan node Gunicorn kehabisan memori (OOMKilled oleh kernel Linux).
2. **Replication Stale Reads**: Pembeli yang baru saja checkout dialihkan oleh load balancer ke *Read Replica*. Karena latensi replikasi asynchronous 80ms, data pesanan belum muncul di replica, memicu komplain tiket "Pesanan Hilang".
3. **Deadlock Database**: Pengurangan stok serentak mengeksekusi urutan pembaruan `Stock` dengan urutan ID yang tidak seragam, menghasilkan PostgreSQL transaction deadlock.

#### Solusi Arsitektur Terintegrasi

```python
# routers.py
# Solusi Masalah 2: Database Router Cerdas dengan Dukungan Pinning
import threading
from django.conf import settings

_local = threading.local()

def set_write_execution_marker():
    """Tandai thread saat ini bahwa mutasi baru saja dieksekusi."""
    _local.primary_pinned = True

def clear_write_execution_marker():
    _local.primary_pinned = getattr(_local, 'primary_pinned', False)

class PrimaryReplicaLagAwareRouter:
    """
    Router yang secara cerdas mendistribusikan read traffic ke replica,
    tetapi memaksa rute ke primary jika thread yang sama baru melakukan write.
    """
    def db_for_read(self, model, **hints):
        if getattr(_local, 'primary_pinned', False):
            return 'default'  # Pin ke Primary Node
        return 'replica_1'

    def db_for_write(self, model, **hints):
        set_write_execution_marker()
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, **hints):
        return db == 'default'
```

```python
# inventory_service.py
# Solusi Masalah 1 & 3: Optimasi Penguncian Terurut & Prefetching Ringan
from decimal import Decimal
from django.db import transaction
from django.db.models import Prefetch
from .models import Order, OrderItem, ProductStock

class ProductionOrderProcessor:
    @staticmethod
    def secure_stock_allocation(order_id: int, items_map: dict[int, int]):
        """
        items_map: {product_id: requested_quantity}
        Mencegah deadlock dengan mengurutkan ID produk sebelum lock akuisisi.
        """
        sorted_product_ids = sorted(items_map.keys())

        with transaction.atomic():
            # Mencegah deadlock: Mengunci baris selalu dengan urutan ID produk terurut (ID ASC)
            locked_stocks = list(
                ProductStock.objects
                .select_for_update(nowait=False)
                .filter(product_id__in=sorted_product_ids)
                .order_by('product_id')
            )

            # Validasi ketersediaan stok
            stocks_dict = {stock.product_id: stock for stock in locked_stocks}
            for prod_id, qty in items_map.items():
                stock_record = stocks_dict.get(prod_id)
                if not stock_record or stock_record.available_units < qty:
                    raise ValueError(f"Stok habis untuk Product ID {prod_id}")

            # Alokasi atomik
            for prod_id, qty in items_map.items():
                stock_record = stocks_dict[prod_id]
                stock_record.available_units -= qty
                stock_record.save(update_fields=['available_units'])

    @staticmethod
    def get_lightweight_order_summary(user_id: int):
        """
        Solusi Masalah 1: Prefetch ringkas dengan pembatasan field ketat
        """
        optimized_prefetch = Prefetch(
            'items',
            queryset=OrderItem.objects.only('id', 'order_id', 'product_name', 'price', 'quantity'),
            to_attr='cached_items'
        )

        return (
            Order.objects
            .filter(user_id=user_id)
            .only('id', 'order_number', 'total_amount', 'created_at')
            .prefetch_related(optimized_prefetch)
            .order_by('-created_at')[:20]
        )
```

---

### 9. Trade-offs

| Pendekatan / Pola | Keuntungan (*Pros*) | Konsekuensi & Batasan (*Cons / Trade-offs*) | Biaya & Latensi (*Cost / Latency*) |
| :--- | :--- | :--- | :--- |
| **`select_for_update()`** (Pessimistic Lock) | Menjamin konsistensi transaksi secara mutlak; tidak ada anomali race condition. | Mengurangi throughput database. Jika transaksi lambat memegang kunci, connection pool dapat jenuh (*connection starvation*). | Latensi naik seiring antrean concurrency; Risiko tinggi terjadi DB Timeout jika tidak memakai `nowait=True`. |
| **Optimistic Locking** (`version` field) | Tidak ada row-level lock pada DB; performa read/write non-conflicting sangat tinggi. | Aplikasi harus menangani exception saat terjadi konflik mutasi; membutuhkan logika *retry-loop*. | Latensi rendah pada kondisi normal; CPU spike di aplikasi jika terjadi conflict-retry berkali-kali. |
| **`.iterator(chunk_size=N)`** | Mencegah heap memory membengkak; memory footprint konstan $O(chunk\_size)$. | Mematikan `_result_cache`. Melakukan iterasi kedua pada QuerySet yang sama akan memicu eksekusi ulang kueri SQL ke database. | Menghemat biaya memori pod container; Menambah latency jika dataset kecil dievaluasi berulang kali. |
| **Pemisahan Read/Write (Replica Router)** | Skalabilitas pembacaan data horizontal hampir linear. Mengurangi beban I/O node Primary. | Kompleksitas arsitektur; Masalah *Eventual Consistency* dan risiko membaca stale-data (*replication lag*). | Biaya server/infra bertambah; Latensi pembacaan data sangat rendah di level regional edge replica. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Perangkap Evaluasi Ganda pada `.iterator()`
*Masalah*: Memanggil iterator lalu mencoba memeriksa panjang koleksi atau mengevaluasi ulang.
```python
# KODE SALAH
orders = Order.objects.filter(status='PENDING').iterator(chunk_size=2000)
count = len(list(orders)) # Seluruh data dimuat ke memori, tujuan iterator hangus!
for order in orders:      # KOSONG! Iterator telah habis terkonsumsi
    process(order)

# KODE BENAR
# Lakukan penghitungan via SQL COUNT, lalu streaming data murni
base_query = Order.objects.filter(status='PENDING')
total = base_query.count() # SQL: SELECT COUNT(*) FROM ...

for order in base_query.iterator(chunk_size=2000):
    process(order)
```

#### 2. Ketidaksengajaan Re-Querying Menggunakan Method Relasi Bawaan
*Masalah*: Mengabaikan `to_attr` pada kueri prefetch, lalu menyaring child relationship menggunakan `.filter()`, yang memicu pembatalan prefetch cache.
```python
# KODE SALAH
orders = Order.objects.prefetch_related('items')
for order in orders:
    # PERINGATAN: Memanggil .filter() di sini akan MEMBUANG hasil prefetch
    # dan mengeksekusi SQL SELECT baru ke database untuk setiap baris! (N+1 kembali terjadi)
    active_items = order.items.filter(is_active=True)

# KODE BENAR
from django.db.models import Prefetch

orders = Order.objects.prefetch_related(
    Prefetch(
        'items',
        queryset=OrderItem.objects.filter(is_active=True),
        to_attr='active_items_list'  # Disimpan sebagai Python List murni
    )
)
for order in orders:
    active_items = order.active_items_list  # Membaca dari memory list (0 DB query)
```

#### 3. Transaction Deadlock pada Konkurensi Mutasi
*Gejala*: Muncul `django.db.utils.OperationalError: deadlock detected` pada PostgreSQL log.
*Penyebab*: Dua thread mengunci baris-baris data yang sama namun dengan urutan terbalik.
- Thread A: Mengunci Model A ID 1, lalu mencoba mengunci Model A ID 2.
- Thread B: Mengunci Model A ID 2, lalu mencoba mengunci Model A ID 1.
*Solusi*: Wajib mengurutkan ID entitas menggunakan `.order_by('id')` sebelum menerapkan `.select_for_update()`.

---

### 11. Best Practices (Production Checklist)

- [ ] **Selalu Definisikan `update_fields`**: Ketika memanggil `instance.save()`, tentukan kolom yang dimodifikasi secara eksplisit (`instance.save(update_fields=['status', 'updated_at'])`). Mencegah penulisan kolom tidak sengaja dan menurunkan beban I/O replication stream.
- [ ] **Cegah N+1 dengan CI Automated Assertion**: Tuliskan unit test menggunakan assertion query count pada critical endpoints:
  ```python
  with self.assertNumQueries(2):
      response = self.client.get('/api/v1/dashboard/')
  ```
- [ ] **Indeks Berbasis Pola Filter**: Tambahkan indeks komposit pada pasangan foreign-key dan status:
  ```python
  models.Index(fields=['tenant_id', 'status', 'created_at'])
  ```
- [ ] **Terapkan Functional & Partial Indexes**: Kurangi beban penyimpanan index PostgreSQL dengan partial indexing:
  ```python
  class Meta:
      indexes = [
          models.Index(
              fields=['created_at'],
              name='idx_unprocessed_orders',
              condition=models.Q(status='PENDING')
          )
      ]
  ```
- [ ] **Gunakan `exists()` daripada `count() > 0`**: Memanggil `.count()` akan memindai seluruh row matching di database. `.exists()` menghasilkan SQL `SELECT 1 ... LIMIT 1` yang berhenti memindai pada row pertama yang ditemukan.
- [ ] **Gunakan Connection Pooling**: Pasang PgBouncer atau aktifkan parameter `CONN_MAX_AGE` (misal: 60 detik) untuk menghindari biaya latensi handshake TCP/TLS berulang ke database PostgreSQL pada setiap request lifecycle.

---

### 12. Hands-on Practice

Buat dan susun direktori pengujian mandiri di: `hands-on/m02/`

#### Langkah 1: Setup Lingkungan & Database Sandbox
Jalankan perintah shell berikut untuk menginisialisasi modul pengujian:
```bash
mkdir -p hands-on/m02/benchmark
cd hands-on/m02
python -m venv venv
source venv/bin/activate
pip install django psycopg[binary] django-debug-toolbar
django-admin startproject performance_lab .
python manage.py startapp telemetry
```

#### Langkah 2: Buat Model dengan Indeks Komposit
Tuliskan model berikut ke dalam `telemetry/models.py`:
```python
from django.db import models

class Device(models.Model):
    serial_number = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)

class MetricRecord(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='metrics')
    metric_type = models.CharField(max_length=32, db_index=True)
    value = models.FloatField()
    recorded_at = models.DateTimeField(db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['device', 'metric_type', '-recorded_at']),
        ]
```

#### Langkah 3: Script Seeder dan Benchmark Evaluasi
Buat file `benchmark/run_benchmarks.py`:
```python
import os
import sys
import time
import django
from django.utils import timezone
from datetime import timedelta
import random

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'performance_lab.settings')
django.setup()

from django.db import connection, reset_queries
from telemetry.models import Device, MetricRecord
from django.db.models import Prefetch, Subquery, OuterRef

def seed_data(device_count=50, records_per_device=200):
    print("Mengeksekusi database seeding...")
    MetricRecord.objects.all().delete()
    Device.objects.all().delete()
    
    devices = [Device(serial_number=f"DEV-{i:05d}") for i in range(device_count)]
    Device.objects.bulk_create(devices)
    
    all_devices = list(Device.objects.all())
    records = []
    base_time = timezone.now()
    
    for dev in all_devices:
        for j in range(records_per_device):
            records.append(MetricRecord(
                device=dev,
                metric_type=random.choice(['CPU', 'MEMORY', 'TEMPERATURE']),
                value=random.uniform(10.0, 99.0),
                recorded_at=base_time - timedelta(minutes=j)
            ))
    MetricRecord.objects.bulk_create(records, batch_size=2000)
    print("Database seeding selesai.")

def run_performance_test():
    reset_queries()
    
    # Kueri Tidak Optimal (N+1 Scenario)
    start = time.perf_counter()
    devices = list(Device.objects.filter(is_active=True))
    bad_payload = []
    for d in devices:
        bad_payload.append({
            'serial': d.serial_number,
            'recent_metric': list(d.metrics.filter(metric_type='CPU')[:1])
        })
    duration_bad = time.perf_counter() - start
    queries_bad = len(connection.queries)

    # Kueri Teroptimasi (Subquery Injection)
    reset_queries()
    start = time.perf_counter()
    
    latest_cpu_metric = MetricRecord.objects.filter(
        device=OuterRef('pk'),
        metric_type='CPU'
    ).order_by('-recorded_at').values('value')[:1]

    optimized_devices = list(
        Device.objects.filter(is_active=True)
        .annotate(latest_cpu_val=Subquery(latest_cpu_metric))
    )
    
    good_payload = [{'serial': d.serial_number, 'cpu': d.latest_cpu_val} for d in optimized_devices]
    duration_good = time.perf_counter() - start
    queries_good = len(connection.queries)

    print("\n" + "="*50)
    print("HASIL PENGUJIAN PERFORMA QUERYSET")
    print("="*50)
    print(f"Metode Naive     : {duration_bad:.4f} detik | Query Count: {queries_bad}")
    print(f"Metode Subquery  : {duration_good:.4f} detik | Query Count: {queries_good}")
    print(f"Efisiensi Query  : Pengurangan {(queries_bad - queries_good) / queries_bad * 100:.1f}% panggilan database!")
    print("="*50)

if __name__ == '__main__':
    seed_data(30, 100)
    run_performance_test()
```

Jalankan pengujian:
```bash
python manage.py makemigrations telemetry
python manage.py migrate
python benchmark/run_benchmarks.py
```

---

### 13. Exercise

#### Level Easy
Ubah kueri berikut agar mengeksekusi operasi secara eager-loading tanpa menghasilkan kueri SQL tambahan saat field `author.profile.bio` diakses:
```python
# Kueri Naive
posts = Post.objects.all()
for p in posts:
    print(p.author.profile.bio)
```
*Tugas*: Tuliskan perbaikan kode menggunakan metode Chained `select_related`.

#### Level Medium
Diberikan model `Company` dan `Employee`. Setiap perusahaan memiliki ribuan karyawan dengan kolom `salary` (Decimal).
*Tugas*: Buat kueri yang mengembalikan daftar seluruh perusahaan yang dianotasi dengan dua kolom baru:
1. `max_salary`: Gaji tertinggi di perusahaan tersebut.
2. `median_proxy_salary`: Rata-rata dari 10% gaji tertinggi di perusahaan tersebut menggunakan kombinasi subquery dan `Window` function atau aggregation bersyarat. Dilarang melakukan komputasi menggunakan loop Python.

#### Level Hard
Buat implementasi context manager bernama `query_debugger` yang mencegat compiler Django:
1. Menghitung total waktu eksekusi SQL mentah.
2. Merekam kueri yang identik (*duplicate queries*).
3. Melemparkan exception custom `NPlusOneDetectedException` jika kueri yang identik dieksekusi lebih dari 3 kali berturut-turut dalam satu context block.

---

### 14. Challenge

#### Skenario Kasus Kompleks: Real-Time Ledger Reconciliation Engine
Anda ditugaskan mendesain mesin rekonsiliasi data mutasi bank untuk payment gateway skala enterprise.
- **Karakteristik Data**: Tabel `BankStatementRow` dan `InternalLedgerRow` masing-masing memiliki 50 juta records.
- **Tantangan**:
  1. Anda harus mencocokkan baris data kedua tabel tersebut berdasarkan kriteria: `reference_number` yang sama ATAU (`amount` yang persis sama DAN rentang waktu transaksi berada dalam toleransi $\pm 60$ detik).
  2. Status rekonsiliasi yang dihasilkan harus ditandai: `MATCHED`, `DISCREPANCY`, atau `ORPHAN`.
  3. Sistem dijalankan pada worker Kubernetes dengan batasan hard-memory limit RAM 512MB per Pod. Jika proses mencoba memuat seluruh baris ke Python list, pod akan mengalami *Out-Of-Memory Crash*.
  4. Database berjalan pada arsitektur PostgreSQL Read-Write Cluster. Proses rekonsiliasi tidak boleh memblokir transaksi baru yang sedang masuk ke tabel `InternalLedgerRow`.

*Keluaran yang Diharapkan*:
- Tuliskan arsitektur query Django ORM lengkap yang mengoptimalkan cursor processing (`.iterator()`), partial indexing, ekspresi database native (`ExpressionWrapper`, `Q`), serta hindari lock blocking pada row ledger.
- Sediakan rancangan penanganan migrasi skema tabel tanpa downtime (*zero downtime migration plan*).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)

1. Kapan tepatnya sebuah `QuerySet` di Django mengeksekusi kueri SQL ke database?
   - A. Saat method `.filter()` dipanggil.
   - B. Saat method `.annotate()` dipanggil.
   - C. Saat instance `QuerySet` dievaluasi (misal: diiterasi, di-cast ke `list()`, atau dipanggil `len()`).
   - D. Saat model selesai didefinisikan di `models.py`.

2. Apa perbedaan utama fungsi antara `select_related` dan `prefetch_related`?
   - A. `select_related` untuk M:M, `prefetch_related` untuk O:1.
   - B. `select_related` menggunakan SQL `JOIN`, `prefetch_related` menggunakan query SQL terpisah di-batching via memori aplikasi.
   - C. `prefetch_related` selalu lebih cepat daripada `select_related`.
   - D. `select_related` tidak mendukung filtering.

3. Apa efek samping arsitektural dari penggunaan method `.iterator()` pada QuerySet?
   - A. Kueri dijalankan pada thread terpisah secara asynchronous.
   - B. Hasil kueri tidak akan disimpan ke dalam `_result_cache`, sehingga iterasi berulang akan memicu I/O ulang ke database.
   - C. Data dikembalikan dalam format dictionary bukan objek Model.
   - D. Mengunci seluruh tabel dari operasi penulisan.

4. Manakah ekspresi berikut yang digunakan untuk mereferensikan field dari outer query di dalam sebuah Subquery Django ORM?
   - A. `F()`
   - B. `OuterRef()`
   - C. `Value()`
   - D. `SubRef()`

5. Apa tujuan utama menetapkan parameter `update_fields` saat memanggil method `.save()` pada objek Django Model?
   - A. Menghapus field yang tidak disebutkan dari skema database.
   - B. Memaksa Django menggunakan trigger database daripada logic Python.
   - C. Menghasilkan SQL UPDATE yang hanya menimpa kolom-kolom yang ditentukan secara presisi.
   - D. Mempercepat validasi data model clean methods.

---

#### Bagian 2: Intermediate (Pilihan Ganda)

6. Pada PostgreSQL, bagaimana perilaku dari `select_for_update(nowait=False)` ketika baris yang ditargetkan sedang dikunci oleh transaksi lain?
   - A. Segera melemparkan exception `OperationalError`.
   - B. Melompati baris yang terkunci dan membaca baris berikutnya.
   - C. Thread aplikasi akan tertahan (block/wait) sampai transaksi pemegang lock selesai melakukan commit atau rollback.
   - D. Mengubah isolasi transaksi secara otomatis menjadi `READ UNCOMMITTED`.

7. Diberikan kode:
   ```python
   qs = Order.objects.prefetch_related(
       Prefetch('items', queryset=OrderItem.objects.filter(price__gt=100), to_attr='expensive_items')
   )
   for o in qs:
       res = o.items.filter(price__gt=100)
   ```
   Berapa banyak kueri database yang dieksekusi jika `qs` mengembalikan 50 objek `Order`?
   - A. 2 kueri.
   - B. 51 kueri.
   - C. 52 kueri.
   - D. 1 kueri.

8. Bagaimana cara paling optimal untuk memodifikasi nilai integer counter di database pada kondisi konkurensi multi-worker tanpa menggunakan lock baris eksplisit (`select_for_update`)?
   - A. Menggunakan `instance.counter = instance.counter + 1` diikuti `instance.save()`.
   - B. Menggunakan `instance.update(counter=F('counter') + 1)`.
   - C. Mengambil data menggunakan `select_related()` terlebih dahulu.
   - D. Menggunakan library global Python lock seperti `threading.Lock`.

9. Saat mengonfigurasi Database Routing untuk Read/Write Split di Django, mengapa penting untuk menerapkan strategi "Pin to Primary After Write"?
   - A. Karena Read Replica tidak memiliki indeks database yang valid.
   - B. Untuk mencegah pengguna membaca data lama (*stale data*) sesaat setelah melakukan write akibat adanya jeda replikasi (*replication lag*).
   - C. Karena Django ORM tidak mendukung eksekusi SQL SELECT pada Read Replica.
   - D. Untuk menghindari deadlock pada koneksi Read Replica.

10. Apa keuntungan performa utama dari pembuatan *Partial Index* di PostgreSQL menggunakan Django ORM?
    - A. Mengindeks seluruh tabel tanpa memakan ruang swap.
    - B. Mengurangi ukuran file indeks secara signifikan di disk dan mempercepat I/O pencarian kueri hanya pada subset data yang sering disaring.
    - C. Mengizinkan index scan tanpa menggunakan B-Tree.
    - D. Menjamin integritas data lintas database engine.

---

#### Bagian 3: Skenario Kasus Produksi (Analisis & Esai Jawaban Singkat)

11. **Skenario 1**: API Dashboard Analytic Anda mengalami degradasi latensi parah (response time naik dari 200ms menjadi 8500ms). Setelah mengevaluasi kueri dengan `connection.queries`, Anda mendapati bahwa baris berikut dieksekusi:
    ```python
    active_users = User.objects.filter(is_active=True)
    payload = [{'id': u.id, 'total_spent': sum(o.amount for o in u.orders.all())} for u in active_users]
    ```
    Terdapat 20.000 `active_users` dan total 400.000 `orders`. Jelaskan secara terstruktur arsitektur kueri pengganti terbaik menggunakan fasilitas Django ORM untuk memangkas respon kembali di bawah 150ms!

12. **Skenario 2**: Anda mengimplementasikan multi-threaded Celery worker untuk memproses antrean pesanan:
    ```python
    @app.task
    def process_ticket(ticket_id):
        with transaction.atomic():
            ticket = SupportTicket.objects.select_for_update().get(id=ticket_id)
            if ticket.status == 'OPEN':
                ticket.status = 'PROCESSING'
                # Simulasi integrasi I/O lambat ke pihak ketiga (Payment Gateway)
                call_external_third_party_gateway(ticket)
                ticket.status = 'COMPLETED'
                ticket.save(update_fields=['status'])
    ```
    Under heavy load, seluruh database pool kehabisan koneksi (*Connection Starvation*), dan transaksi web service umum menjadi timeout. Identifikasi kesalahan desain arsitektur transaksi di atas dan berikan solusinya!

13. **Skenario 3**: Sebuah tabel log partisi transaksi bulanan berukuran 200GB (`AuditLog`) perlu di-stream untuk diekspor ke format Parquet di AWS S3. Worker Celery mengalami error `MemoryError: Out of Memory (OOM)` saat mengeksekusi `AuditLog.objects.filter(created_at__year=2023)`. Mengapa `iterator()` standar kadang tetap dapat memicu konsumsi RAM tinggi jika konfigurasi driver PostgreSQL DBAPI tidak tepat, dan bagaimana cara mengatasi arsitektur data retrieval streaming ini?

---

### Kunci Jawaban & Panduan Pembahasan Quiz

#### Bagian 1: Basic
1. **C** — `QuerySet` bersifat *lazy*. Instansiasi awal tidak mengeksekusi SQL. Eksekusi I/O ke RDBMS hanya dipicu ketika hasil evaluasi diminta secara konkret (iterasi `for`, evaluasi ekspresi logika `bool()`, `list()`, `len()`).
2. **B** — `select_related` menambahkan klausul `JOIN` SQL ke dalam query tunggal (cocok untuk 1:1 dan M:1). `prefetch_related` melakukan pengambilan batch data terpisah melalui klausul SQL `WHERE id IN (...)` lalu menyatukannya di layer memori aplikasi (cocok untuk 1:M dan M:M).
3. **B** — `.iterator()` mematikan mekanisme penyimpanan internal `_result_cache`. Keuntungannya memori RAM hemat, namun konsekuensinya data tidak disimpan di memori Python, sehingga evaluasi kedua kali harus memanggil query SQL baru ke database.
4. **B** — `OuterRef` menginstruksikan Django compiler untuk meneruskan referensi kolom milik kueri luar (*outer query*) ke dalam subquery berkorelasi (*correlated subquery*).
5. **C** — Secara default, Django mengeksekusi SQL `UPDATE table SET col1=val1, col2=val2...` mencakup seluruh field tabel. `update_fields` membatasi modifikasi SQL tepat hanya pada kolom yang didefinisikan, mencegah penimpaan data yang tidak disengaja dan menghemat bandwidth WAL PostgreSQL.

#### Bagian 2: Intermediate
6. **C** — Parameter default `nowait=False` pada locking engine RDBMS memerintahkan worker thread untuk menunggu (antre secara blocking) hingga transaksi yang memegang lock baris saat ini melepaskan lock-nya (via COMMIT atau ROLLBACK).
7. **C** — Kueri awal mengambil 50 orders (1 kueri). Prefetch data awal mengambil items batching (1 kueri). Namun, di dalam perulangan `for`, developer memanggil `o.items.filter(...)` dan BUKAN atribut hasil kueri prefetch `o.expensive_items`. Memanggil method manager `.filter()` membatalkan cache prefetch dan menerbitkan 1 SQL query baru per order. Total query: $1 + 1 + 50 = 52$ kueri.
8. **B** — Ekspresi `F()` menghasilkan instruksi SQL langsung: `UPDATE table SET counter = counter + 1 WHERE ...`. Database engine menyelesaikan kalkulasi penambahan nilai secara atomik tanpa memuat data ke memori aplikasi, sehingga aman dari *race condition* konkurensi tanpa perlu row lock blocking.
9. **B** — Replikasi database asinkron memperkenalkan jeda waktu propagasi data (propagation lag). Pola "Pinning to Primary" memastikan klien yang baru saja mengirimkan mutasi (POST/PUT) langsung membaca data dari Primary database selama jendela waktu singkat (misal: 2-5 detik) agar tidak melihat kondisi data sebelum mutasi (stale data).
10. **B** — Partial Index menggunakan klausa `WHERE` pada pembuatan indeks (contoh: `WHERE status = 'PENDING'`). Indeks hanya menyimpan pointer baris data yang memenuhi kondisi tersebut, menghasilkan ukuran index tree jauh lebih kecil, hemat memory buffer cache, dan meningkatkan kecepatan transversing.

#### Bagian 3: Skenario Kasus Produksi
11. **Solusi Skenario 1**:
    Kode naive menghasilkan $1 + 20.000 = 20.001$ kueri database (masalah $N+1$). Solusinya adalah memindahkan proses komputasi penjumlahan secara agregat ke database engine menggunakan `annotate()` dan `Coalesce`:
    ```python
    from django.db.models import Sum, Value, DecimalField
    from django.db.models.functions import Coalesce

    optimized_users = (
        User.objects.filter(is_active=True)
        .annotate(
            total_spent=Coalesce(
                Sum('orders__amount'), 
                Value(0, output_field=DecimalField())
            )
        )
        .values('id', 'total_spent')
    )
    payload = list(optimized_users)
    ```
    Pendekatan ini memangkas eksekusi menjadi **1 kueri SQL tunggal** berkecepatan tinggi dengan pemanfaatan aggregate join atau temporary table PostgreSQL.

12. **Solusi Skenario 2**:
    *Kesalahan Arsitektur*: Melakukan panggilan jaringan eksternal (Third-Party I/O: `call_external_third_party_gateway`) di dalam blok atomik database yang sedang memegang *Pessimistic Lock* (`select_for_update`). Latensi jaringan eksternal (biasanya 500ms - 3000ms) menahan lock baris database dan menahan koneksi database worker dari pool, menyebabkan antrean connection pool jenuh (*starvation*).
    *Solusi*: Ekstrak panggilan eksternal keluar dari blok transaksi database atomik:
    ```python
    # Langkah 1: Kunci, verifikasi, dan tandai status awal secara cepat
    with transaction.atomic():
        ticket = SupportTicket.objects.select_for_update().get(id=ticket_id)
        if ticket.status != 'OPEN':
            return
        ticket.status = 'PENDING_GATEWAY'
        ticket.save(update_fields=['status'])

    # Langkah 2: Panggilan eksternal di luar transaksi DB (Lock telah dilepas)
    gateway_success = call_external_third_party_gateway(ticket)

    # Langkah 3: Buka transaksi baru yang singkat untuk mencatat hasil
    with transaction.atomic():
        ticket = SupportTicket.objects.select_for_update().get(id=ticket_id)
        ticket.status = 'COMPLETED' if gateway_success else 'FAILED'
        ticket.save(update_fields=['status'])
    ```

13. **Solusi Skenario 3**:
    Secara default, library DBAPI seperti `psycopg2` menggunakan *client-side cursors*. Meskipun developer memanggil `.iterator()`, driver DBAPI tetap menarik seluruh row data dari server PostgreSQL ke dalam memori klien Python seketika, baru kemudian method generator membacanya secara lokal.
    *Solusi Arsitektur*:
    1. Pastikan server-side cursor aktif pada Django settings dengan memastikan iterasi berada dalam konteks transaksi atomik (`with transaction.atomic():`), yang menginstruksikan driver DBAPI untuk membuat named cursor PostgreSQL (`DECLARE cursor_name CURSOR FOR SELECT...`).
    2. Atur ukuran `chunk_size` secara terukur:
    ```python
    with transaction.atomic():
        logs_stream = AuditLog.objects.filter(created_at__year=2023).iterator(chunk_size=5000)
        for log_entry in logs_stream:
            serialize_and_append_to_parquet_buffer(log_entry)
    ```
    Langkah ini membatasi transfer stream data dari server database hanya sebesar 5.000 baris per round-trip jaringan, menstabilkan penggunaan RAM worker pada batas absolut di bawah 100MB terlepas dari ukuran tabel 200GB.

---

### 16. Summary

Menguasai arsitektur query Django ORM pada level enterprise membedakan antara sistem yang runtuh di bawah beban transaksi tinggi dan sistem yang memiliki skalabilitas tinggi. Memahami siklus kompilasi SQL, peran mutlak `_result_cache`, serta implikasi memori dari instansiasi model Python memungkinkan perancangan aplikasi yang deterministik.

Poin Kunci:
1. **Eager Loading Deterministik**: Gunakan `select_related` untuk relasi single-valued (SQL JOIN) dan `prefetch_related` dengan parameter `to_attr` untuk relasi multi-valued guna mengeliminasi masalah $N+1$ tanpa menciptakan *Cartesian Product Memory Bloat*.
2. **Database Engine Compute**: Manfaatkan `Subquery`, `OuterRef`, dan `F()` expressions untuk mengeksekusi logika kalkulasi data langsung pada CPU database, meminimalisasi alokasi objek model Python dan latensi jaringan.
3. **Konkurensi Aman**: Lindungi data finansial menggunakan *Pessimistic Locking* (`select_for_update`) dengan urutan ID terurut untuk mencegah *Deadlock*, dan pisahkan proses I/O pihak ketiga di luar batas transaksi atomik database.
4. **Skalabilitas Baca/Tulis**: Terapkan *Custom Database Routers* yang sadar latensi replikasi data (*replication lag-aware*) guna mengalirkan beban bacaan secara merata ke PostgreSQL Read Replicas dengan proteksi pinning konsistensi pasca-mutasi.