# BAB 02: Data Modeling Engine & Skema Database Tingkat Lanjut
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Membedah & Menguasai Engine Internal Django ORM**: Menganalisis siklus hidup model dari evaluasi metakelas (`ModelBase`), konstruksi state `Options` (`_meta`), kompilasi ekspresi SQL melalui `django.db.models.sql.compiler`, hingga eksekusi driver database (`psycopg3`).
2. **Merancang Skema Relasional Kompleks & Konstrain Tingkat Lanjut**: Mengimplementasikan `CheckConstraint`, `UniqueConstraint` kondisional berbasis ekspresi (`F()`, `Q()`, `Lower()`), serta *exclusion constraints* menggunakan kapabilitas mesin PostgreSQL.
3. **Mengoptimalkan Strategi Pewarisan Model (Model Inheritance)**: Memilih dan mengimplementasikan secara tepat antara *Abstract Base Classes*, *Multi-Table Inheritance* (termasuk implikasi *implicit pointer* `OneToOneField` dan performa I/O), serta *Proxy Models* untuk manipulasi representasi data tanpa overhead I/O.
4. **Menerapkan Zero-Downtime Migrations**: Merancang strategi migrasi skema tanpa *exclusive table lock* pada tabel berskala puluhan juta baris, menggunakan indeks konkuren (`AddIndexConcurrently`), ekspansi bertahap (*expand-contract pattern*), dan isolasi state migrasi.
5. **Mengintegrasikan Tipe Data Native & Partisi Mesin Basis Data**: Membangun skema enterprise menggunakan tipe data native (`JSONB`, `ArrayField`, `GeneratedField`) serta partisi tabel deklaratif PostgreSQL (*Declarative Partitioning*) yang terintegrasi penuh ke dalam siklus hidup Django ORM.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib memiliki pemahaman mendalam tentang:

*   **Python Metaprogramming**: Pemahaman solid mengenai Metaclasses (`type.__new__`, `__init__`), Descriptors (`__get__`, `__set__`), dan Dynamic Attribute Resolution (`__getattr__`).
*   **Django Dasar & Menengah**: Pembuatan model standar, relasi dasar (`ForeignKey`, `ManyToManyField`), queryset API, dan perintah dasar migrasi skema.
*   **Database Relasional Tingkat Lanjut (khususnya PostgreSQL)**: Konsep ACID, tingkat isolasi transaksi (*Read Committed*, *Repeatable Read*, *Serializable*), struktur indeks B-Tree, GIN, GiST, serta mekanisme *lock contention* (`ACCESS EXCLUSIVE`, `SHARE UPDATE EXCLUSIVE`).
*   **Sistem Jaringan & Concurrency**: Memahami *connection pooling*, *thread-safety*, dan pipeline I/O asinkron/sinkron pada driver database.

---

### 3. Concept & Internal Architecture

Django ORM bukan sekadar pemetaan tabel-ke-kelas (*Active Record* murni), melainkan sebuah mesin kompilasi *Domain-Specific Language* (DSL) deklaratif berbasis Python yang mengabstraksikan kalkulus relasional menjadi SQL teroptimasi.

```
+-------------------------------------------------------------------------------+
|                             Model Definition (Python)                         |
|   class Transaction(models.Model): ...                                        |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                      Metaclass: django.db.models.base.ModelBase               |
|  - Ekstraksi atribut kelas (Fields, Managers, Constraints)                    |
|  - Instansiasi `django.db.models.options.Options` (tersimpan di `_meta`)      |
|  - Registrasi Model ke App Registry (`django.apps.apps`)                      |
|  - Penyusunan Reverse Relations & Inheritance Tree                            |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                            Query Construction Layer                           |
|   Transaction.objects.filter(...).annotate(...)                               |
|  - Pembangunan `django.db.models.query.QuerySet`                              |
|  - Clone tree via `QuerySet._clone()` (Immutability guarantee)                |
|  - Alokasi `django.db.models.sql.query.Query` instance                        |
|  - Resolusi Node Ekspresi via `resolve_expression()`                          |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                         SQL Compilation & Dialect Engine                      |
|  - `SQLCompiler.as_sql()` -> Delegasi ke Database Backend Engine              |
|  - Pemetaan Tipe Python ke DB Types via `Field.db_type()`                     |
|  - Query Optimization: JOIN folding, alias quoting, parameter substitution    |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                        Database Backend (e.g., psycopg3)                      |
|  - Eksekusi Raw SQL + Params tuple melalui DatabaseWrapper.cursor()           |
|  - Engine Level Lock & Transaction Management (Atomicity / Savepoints)        |
+-------------------------------------------------------------------------------+
```

#### 3.1. Anatomi Inisialisasi Model: Metaclass `ModelBase`
Ketika file Python yang mendefinisikan model dimuat, Django tidak langsung membuat kelas Python biasa. Metaclass `ModelBase` mengintersepsi pembuatan kelas:
1. Memisahkan atribut field dari fungsi helper atau properti biasa. Field dipindahkan ke objek `_meta` (`Options`), yang menyimpan metadata tabel.
2. Memproses inheritance:
   * **Abstract Base Classes**: Field dari kelas induk disalin langsung ke kelas anak. Kelas induk tidak menghasilkan tabel database.
   * **Multi-Table Inheritance**: Field dari kelas induk tetap berada di kelas induk. Kelas anak otomatis disuntikkan field `OneToOneField(parent_model, parent_link=True, on_delete=models.CASCADE)`.
   * **Proxy Models**: Menggunakan struktur `_meta` kelas induk secara identik, tetapi dengan interface/manager yang dapat dioverride.
3. Mendaftarkan model ke *global application registry* (`apps.register_model()`).

#### 3.2. Lifecycle Migrasi: State vs Database Schema
Mesin migrasi Django beroperasi pada dua bidang terpisah:
* **Project State**: Pohon struktur memori (`ProjectState`) yang merekonstruksi bagaimana semua model terlihat pada titik migrasi tertentu tanpa mengakses database nyata.
* **Database Schema**: Struktur fisik database nyata yang dimanipulasi oleh backend spesifik via `BaseDatabaseSchemaEditor`.

Ketika `makemigrations` dijalankan, Django membandingkan State saat ini dengan State sebelumnya menggunakan algoritma `MigrationAutodetector`, menyusun graph dependensi (`MigrationGraph`), dan menghasilkan serangkaian operasi migrasi (`django.db.migrations.operations.base.Operation`).

---

### 4. Why & What

| Fitur / Komponen | Apa Itu? | Mengapa Digunakan? (Masalah yang Dipecahkan) |
| :--- | :--- | :--- |
| **Metaclass `ModelBase`** | Mesin introspeksi internal yang mentranslasikan atribut kelas menjadi relasi basis data. | Mencegah redundansi konfigurasi skema dan menyediakan aksesibilitas relasional runtime via `_meta`. |
| **Database Constraints** (`CheckConstraint`, `UniqueConstraint`) | Validasi skema native yang dieksekusi di level mesin SQL database (bukan runtime Python). | Menghindari *race conditions* dan inkonsistensi data pada sistem konkuren tinggi di mana validasi `model.clean()` Python tidak mampu menjamin atomisitas data. |
| **Multi-Table Inheritance vs Abstract** | MTI: Normalisasi tabel dengan relasi One-to-One implisit. Abstract: Salin skema tanpa redundansi tabel. | Mengurangi I/O bottleneck. Abstract dipilih untuk skalabilitas tinggi guna menghindari JOIN otomatis yang memperlambat query baca. |
| **GeneratedField (Django 5.0+)** | Kolom yang nilainya dihitung otomatis oleh database dari kolom lain (*VIRTUAL* atau *STORED*). | Menghilangkan kebutuhan komputasi ulang agregasi di level aplikasi serta memungkinkan *indexing* langsung pada nilai hasil kalkulasi. |
| **Declarative Table Partitioning** | Pembagian fisik tabel raksasa menjadi partisi-partisi yang lebih kecil berdasarkan rentang nilai kunci tertentu. | Mengoptimalkan *Index Scan*, membatasi I/O disk saat eksekusi query (*partition pruning*), dan mempercepat purging data lawas (`DROP TABLE` vs `DELETE`). |

---

### 5. How (Workflow Detail)

Berikut adalah tahapan teknis implementasi model tingkat enterprise:

```
[Definisi Model Kompleks]
        |
        v
[Penerapan Database Constraints (Q, F, Func)]
        |
        v
[Konfigurasi PostgreSQL Native Types & Indexes (GIN/B-Tree)]
        |
        v
[Perumusan Zero-Downtime Migration Graph]
        |
        +---> Step 1: Tambah Kolom/Indeks Konkuren (Tanpa Lock)
        +---> Step 2: Dual-Writing / Data Backfill
        +---> Step 3: Switch Constraint / Hapus Kolom Usang
        |
        v
[Validasi State Migration via `squashmigrations` / CI Pipeline]
```

1. **Definisi Deklaratif**: Bangun model mewarisi `models.Model`, perjelas relasi, tentukan tipe native via `django.contrib.postgres.fields` atau tipe inti.
2. **Deklarasi Konstrain Mesin**: Hindari penulisan validasi integritas kritis pada metode `clean()` semata. Tempatkan validasi pada `Meta.constraints` untuk memastikan integritas tetap ditegakkan meski operasi dilakukan via `bulk_create` atau SQL eksternal.
3. **Optimasi Indeksasi**: Gunakan indeks parsial (`condition=Q(...)`) untuk mengurangi ukuran B-Tree disk footprint dan indeks GIN/GiST untuk tipe non-skalar (`JSONB`, `ArrayField`).
4. **Penerapan Migrasi Konkuren**: Override operasi migrasi standar menggunakan `SeparateDatabaseAndState` untuk migrasi kolom/indeks tanpa downtime pada sistem *high-traffic*.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Model Inheritance

*   **Abstract Base Class**: Ibarat **blueprint cetak biru digital**. Anda mendesain cetak biru mobil balap. Ketika pabrik memproduksi Mobil A dan Mobil B, setiap mobil memiliki sasis fisik masing-masing secara utuh. Blueprint itu sendiri tidak memakan tempat di garasi (tidak ada tabel tersendiri di database).
*   **Multi-Table Inheritance (MTI)**: Ibarat **sistem modular berbasis loker terpisah**. Tubuh mobil diletakkan di Loker 1, mesin di Loker 2. Setiap kali Anda ingin mengendarai mobil, Anda dipaksa membuka dua loker sekaligus dan merakitnya (`JOIN`). Ini memakan energi dan waktu operasi.
*   **Proxy Model**: Ibarat **pemberian seragam atau lencana berbeda pada orang yang sama**. Fisik orangnya (tabel DB) tetap satu, namun perilakunya berubah tergantung apakah dia sedang bertindak sebagai warga sipil atau sebagai petugas keamanan.

#### Diagram: Perbandingan Model Inheritance

```
1. ABSTRACT BASE CLASS (Zero Cost, No DB Join)
+--------------------------------------------------------+
|             Abstract Model: CoreAuditedModel           |  <-- Tidak ada tabel di DB
+--------------------------------------------------------+
            ^                                ^
            | (Inherit)                      | (Inherit)
+--------------------------+    +--------------------------+
|  Table: "order_invoice"  |    |  Table: "user_profile"   |  <-- Tabel mandiri menyimpan
| - id                     |    | - id                     |      seluruh kolom core + kolom
| - created_at, updated_at |    | - created_at, updated_at |      spesifik
| - total_amount           |    | - full_name              |
+--------------------------+    +--------------------------+

2. MULTI-TABLE INHERITANCE (Cost: Implicit Pointer + Foreign Key Join)
+--------------------------------------------------------+
|               Table: "payment_transaction"             |
| - id (PK)                                              |
| - created_at, amount, status                           |
+--------------------------------------------------------+
            ^
            |  Implicit OneToOneField (JOIN overhead pada SELECT)
+--------------------------------------------------------+
|            Table: "crypto_payment_transaction"         |
| - transaction_ptr_id (PK, FK -> payment_transaction)   |
| - wallet_address, tx_hash                              |
+--------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Skema Dasar dengan Constraint & Generated Field
Contoh berikut memperlihatkan validasi level mesin dan penggunaan `GeneratedField` (Django 5.0+):

```python
# models.py
from decimal import Decimal
from django.db import models
from django.db.models import F


class OrderItem(models.Model):
    sku = models.CharField(max_length=64, db_index=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=4)
    quantity = models.PositiveIntegerField(default=1)

    # GeneratedField: Komputasi langsung di layer database engine
    subtotal = models.GeneratedField(
        expression=F("unit_price") * F("quantity"),
        output_field=models.DecimalField(max_digits=14, decimal_places=4),
        db_persist=True,  # Disimpan secara fisik (STORED) di database
    )

    class Meta:
        db_table = "order_items"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=Decimal("0.0000")),
                name="chk_orderitem_unit_price_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="chk_orderitem_quantity_strictly_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.sku} ({self.quantity} x {self.unit_price})"
```

#### 7.2. Practical Example: Advanced Enterprise Schema Engine
Berikut adalah implementasi skala industri yang menggabungkan Postgres-specific JSONB, GIN indexing, conditional constraints, dan UUID v7 / CUID strategy:

```python
# models/advanced_ledger.py
import uuid
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex, OpClass
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import CheckConstraint, F, Index, Q, UniqueConstraint
from django.db.models.functions import Lower


class TimeStampedUUIDModel(models.Model):
    """
    Kelas abstrak penyedia identitas UUID dan metadata penanggalan
    tanpa overhead multi-table inheritance.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AccountLedger(TimeStampedUUIDModel):
    class AccountType(models.TextChoices):
        ASSET = "ASSET", "Asset"
        LIABILITY = "LIABILITY", "Liability"
        EQUITY = "EQUITY", "Equity"
        REVENUE = "REVENUE", "Revenue"
        EXPENSE = "EXPENSE", "Expense"

    account_number = models.CharField(max_length=32)
    normalized_code = models.CharField(max_length=32)
    account_type = models.CharField(max_length=16, choices=AccountType.choices)
    is_active = models.BooleanField(default=True, db_index=True)
    tags = ArrayField(
        models.CharField(max_length=32),
        default=list,
        blank=True,
        help_text="Metadata auditing tags",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Struktur fleksibel untuk konfigurasi vendor/eksternal",
    )

    class Meta:
        db_table = "account_ledgers"
        constraints = [
            # Memastikan account_number unik secara case-insensitive
            UniqueConstraint(
                Lower("account_number"),
                name="unique_case_insensitive_account_number",
            ),
            # Rekening yang aktif wajib memiliki panjang kode minimal 5 karakter
            CheckConstraint(
                condition=Q(is_active=False) | Q(account_number__regex=r"^[A-Z0-9]{5,32}$"),
                name="chk_valid_active_account_code_format",
            ),
        ]
        indexes = [
            # Indeks GIN pada kolom ArrayField untuk pencarian tag yang cepat
            GinIndex(fields=["tags"], name="gin_idx_account_tags"),
            # Indeks GIN pada kolom JSONB menggunakan jsonb_path_ops untuk efisiensi ukuran
            GinIndex(
                fields=["metadata"],
                name="gin_idx_account_metadata_ops",
                opclasses=["jsonb_path_ops"],
            ),
            # Indeks Parsial (hanya mencakup entitas aktif)
            Index(
                fields=["account_type"],
                name="idx_active_acc_type",
                condition=Q(is_active=True),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.account_number} [{self.account_type}]"
```

---

### 8. Real World Case Study: High-Volume Multi-Tenant Financial Transaction Engine

#### 8.1. Masalah
Sebuah platform fintech memproses lebih dari 30 juta transaksi mutasi per bulan. Skema awal menggunakan multi-table inheritance untuk membedakan transaksi debit, kredit, dan settlement, menyebabkan query analitik terhenti (*deadlock* dan lonjakan I/O) karena proses `JOIN` yang masif. 

Selain itu, migrasi penambahan kolom baru `fee_deducted` mengunci tabel utama selama 45 menit (*AccessExclusiveLock*), mengakibatkan *outage* total aplikasi.

#### 8.2. Solusi Arsitektur
1. **Denormalisasi Terkendali**: Menghapus Multi-Table Inheritance dan menggantinya dengan pendekatan *Single Table with Polymorphic Discriminator* yang dilindungi oleh *PostgreSQL Declarative Partitioning* berbasis rentang tanggal (`RANGE(created_at)`).
2. **Zero-Downtime Migration Pattern**: Melakukan penambahan skema baru menggunakan safe-migration contract (memisahkan migrasi state Django dari eksekusi DDL non-blocking).

#### 8.3. Implementasi Skema Partisi & Zero-Downtime

##### A. Konfigurasi Model Terpartisi
```python
# models/partitioned_transaction.py
from django.db import models


class TransactionPartitionManager(models.Manager):
    """Custom manager untuk mengarahkan query dengan partition pruning."""
    def for_period(self, start_date, end_date):
        return self.filter(created_at__gte=start_date, created_at__lt=end_date)


class FinancialTransaction(models.Model):
    """
    Model ini memetakan ke tabel PostgreSQL yang dipartisi.
    Primary Key WAJIB mencakup partisi key (created_at).
    """
    id = models.UUIDField()
    created_at = models.DateTimeField(db_index=True)
    tenant_id = models.UUIDField(db_index=True)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=20, default="PENDING")

    objects = TransactionPartitionManager()

    class Meta:
        db_table = "partitioned_financial_transactions"
        # Komposit PK: PostgreSQL mengharuskan kunci partisi dimasukkan dalam constraint unik/PK
        constraints = [
            models.UniqueConstraint(
                fields=["id", "created_at"],
                name="pk_partitioned_tx",
            )
        ]

    def __str__(self) -> str:
        return f"TX-{self.id} | {self.amount} {self.currency}"
```

##### B. Migrasi Aman Tanpa Lock (Zero-Downtime Index & Table Injection)
```python
# migrations/0002_create_partitioned_table_safely.py
from django.db import migrations


class Migration(migrations.Migration):
    atomic = False  # WAJIB dimatikan untuk statement konkuren seperti CREATE INDEX CONCURRENTLY

    dependencies = [
        ("billing", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS "partitioned_financial_transactions" (
                "id" uuid NOT NULL,
                "created_at" timestamp with time zone NOT NULL,
                "tenant_id" uuid NOT NULL,
                "amount" numeric(18, 4) NOT NULL,
                "currency" varchar(3) NOT NULL,
                "status" varchar(20) NOT NULL,
                CONSTRAINT "pk_partitioned_tx" PRIMARY KEY ("id", "created_at")
            ) PARTITION BY RANGE ("created_at");

            -- Membuat partisi bulan berjalan secara eksplisit
            CREATE TABLE IF NOT EXISTS "partitioned_tx_y2026m01"
                PARTITION OF "partitioned_financial_transactions"
                FOR VALUES FROM ('2026-01-01 00:00:00+00') TO ('2026-02-01 00:00:00+00');
            
            CREATE TABLE IF NOT EXISTS "partitioned_tx_y2026m02"
                PARTITION OF "partitioned_financial_transactions"
                FOR VALUES FROM ('2026-02-01 00:00:00+00') TO ('2026-03-01 00:00:00+00');
            """,
            reverse_sql="""
            DROP TABLE IF EXISTS "partitioned_financial_transactions" CASCADE;
            """,
        ),
        # Pemasangan index secara konkuren untuk mencegah read/write locking
        migrations.RunSQL(
            sql="""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS "idx_fin_tx_tenant_created"
            ON "partitioned_financial_transactions" ("tenant_id", "created_at");
            """,
            reverse_sql="""
            DROP INDEX CONCURRENTLY IF EXISTS "idx_fin_tx_tenant_created";
            """,
        ),
    ]
```

---

### 9. Trade-offs: Analisis Arsitektur

```
+------------------------------------+-------------------------------------------+
|          Strategi Desain           |                Trade-Offs                 |
+------------------------------------+-------------------------------------------+
| Multi-Table Inheritance (MTI)      | [+] Ekstensi skema bersih berorientasi    |
|                                    |     objek.                                |
|                                    | [-] Performa query anjlok drastis (JOIN   |
|                                    |     tersembunyi).                         |
|                                    | [-] Write amplify (2 insert terpisah per  |
|                                    |     record).                              |
+------------------------------------+-------------------------------------------+
| Abstract Base Class                | [+] Zero overhead query/join.             |
|                                    | [+] DDL tabel independen.                 |
|                                    | [-] Duplikasi skema fisik di setiap model |
|                                    |     anak.                                 |
|                                    | [-] Query lintas turunan membutuhkan      |
|                                    |     eksplisit UNION.                      |
+------------------------------------+-------------------------------------------+
| GeneratedField (STORED)            | [+] Read latency sangat rendah (nilai     |
|                                    |     sudah dikomputasi sebelumnya).        |
|                                    | [+] Dapat langsung dipasangi B-Tree Index.|
|                                    | [-] Write penalty: komputasi dieksekusi   |
|                                    |     tiap INSERT/UPDATE.                   |
|                                    | [-] Memperbesar ukuran disk & backup.     |
+------------------------------------+-------------------------------------------+
| PostgreSQL GIN Index pada JSONB    | [+] Pencarian containment (@>) instan     |
|                                    |     (sub-milidetik).                      |
|                                    | [-] Overhead write sangat mahal (rebuild  |
|                                    |     GIN tokens).                          |
|                                    | [-] Konsumsi RAM maintenance (work_mem)   |
|                                    |     meningkat signifikan saat migrasi.    |
+------------------------------------+-------------------------------------------+
```

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Menggunakan Model Validasi Python Tanpa Engine Constraints
*   **Kesalahan Fatal**: Menaruh logika seperti `if self.balance < 0: raise ValidationError(...)` hanya pada metode `clean()`.
*   **Dampak**: Ketika dua request konkurensi masuk secara simultan (*Race Condition*), kedua request melewati validasi `clean()`, lalu kedua worker mengeksekusi `save()`. Saldo rekening menjadi minus di database.
*   **Solusi**:
    ```python
    # models.py
    class Wallet(models.Model):
        balance = models.DecimalField(max_digits=12, decimal_places=2)

        class Meta:
            constraints = [
                models.CheckConstraint(
                    condition=models.Q(balance__gte=0),
                    name="chk_wallet_balance_never_negative",
                )
            ]
    ```

#### 10.2. N+1 Trap yang Tersembunyi pada Multi-Table Inheritance
*   **Kesalahan Fatal**: Mengambil record model induk yang diwarisi oleh puluhan model anak tanpa mitigasi polimorfisme.
*   **Gejala**: Django mengeksekusi satu query untuk mengambil entitas induk, kemudian saat aplikasi mencoba mengakses atribut model anak (`parent_instance.childmodel`), Django memicu 1 query tambahan untuk **setiap baris iterasi** via implicit pointer.
*   **Troubleshooting**: Hindari MTI jika query sering kali melibatkan pembacaan tipe heterogen. Gunakan pola *Single Table Design* dengan atribut JSONB opsional atau implementasikan *Explicit Generic Relations*.

#### 10.3. Penambahan Kolom dengan `default` Non-Null Tanpa Safe Migration pada Django Lama
*   **Masalah**: Pada PostgreSQL versi < 11 atau konfigurasi migration non-optimized, menambahkan kolom dengan `NOT NULL DEFAULT 'value'` akan menulis ulang seluruh tabel fisik (*Table Rewrite*), memicu `AccessExclusiveLock`, memblokir seluruh operasi baca/tulis aplikasi, dan menyebabkan downtime.
*   **Solusi Modern**: Django 4.2+ menangani ini dengan aman pada PostgreSQL modern. Namun, jika menggunakan ekspresi komputasi runtime (seperti fungsi mutable), ikuti langkah aman:
    1. Tambahkan kolom sebagai `null=True`.
    2. Jalankan migrasi.
    3. Backfill data secara bertahap (*batching*).
    4. Ubah kolom menjadi `null=False` via migrasi terpisah.

---

### 11. Best Practices & Production Checklist

1. [ ] **Non-Blocking Indexing**: Pastikan seluruh indeks baru pada tabel produksi yang sudah memuat jutaan baris menggunakan deklarasi indeks konkuren via modul `django.contrib.postgres.operations.AddIndexConcurrently` dengan setting `atomic = False`.
2. [ ] **Enforce DB-Level Integrity**: Seluruh field yang memuat dependensi bisnis mutlak (seperti kuantitas positif, masa berlaku valid, format SKU unik) **wajib** dilindungi via `CheckConstraint` atau `UniqueConstraint`.
3. [ ] **Explicit Relationship Deletion Strategy**: Selalu tentukan parameter `on_delete` secara eksplisit pada relasi (`PROTECT`, `RESTRICT`, atau `CASCADE`). Jangan pernah membiarkan cascading delete tidak terkontrol pada tabel transaksional agregat raksasa.
4. [ ] **Use db_index Parsial**: Jangan membuat indeks B-Tree penuh pada kolom yang didominasi oleh satu variasi nilai (misal: status `is_deleted` bernilai `False` sebesar 99%). Buatlah indeks parsial dengan `condition=Q(is_deleted=False)`.
5. [ ] **Avoid GenericForeignKeys in Critical Paths**: Relasi berbasis generic foreign key (GFK) mengabaikan penegakan integritas referensial level database dan melumpuhkan optimalisasi JOIN oleh database query planner.
6. [ ] **Connection & Migration Isolation**: Uji skema menggunakan linting otomatis melalui `django-migration-linter` pada pipeline CI/CD untuk mencegah DDL backward-incompatible.

---

### 12. Hands-on Practice

Implementasi modul ini akan dibangun pada direktori praktikum `hands-on/m02/`.

#### Struktur Direktori Hands-on
```
hands-on/m02/
├── manage.py
├── core/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── asgi.py
└── billing_engine/
    ├── __init__.py
    ├── apps.py
    ├── models.py
    ├── migrations/
    │   ├── 0001_initial.py
    │   └── __init__.py
    └── tests/
        ├── __init__.py
        └── test_constraints.py
```

#### Langkah 1: Setup Lingkungan & Settings

```bash
mkdir -p hands-on/m02/billing_engine/tests hands-on/m02/core
cd hands-on/m02
python -m venv .venv
source .venv/bin/activate  # atau .venv\Scripts\activate pada Windows
pip install django psycopg[binary]
```

Buat file konfigurasi `hands-on/m02/core/settings.py`:

```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "django-insecure-enterprise-production-grade-mock-key"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.postgres",
    "billing_engine.apps.BillingEngineConfig",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "enterprise_db"),
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
```

Inisialisasi aplikasi pada `hands-on/m02/billing_engine/apps.py`:

```python
from django.apps import AppConfig


class BillingEngineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "billing_engine"
```

#### Langkah 2: Implementasi Model Tingkat Lanjut

Tulis kode model pada `hands-on/m02/billing_engine/models.py`:

```python
import uuid
from decimal import Decimal
from django.contrib.postgres.indexes import GinIndex
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import CheckConstraint, F, Q, UniqueConstraint
from django.db.models.functions import Lower


class EnterpriseSubscription(models.Model):
    class PlanTier(models.TextChoices):
        STARTER = "STARTER", "Starter"
        BUSINESS = "BUSINESS", "Business"
        ENTERPRISE = "ENTERPRISE", "Enterprise"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization_slug = models.SlugField(max_length=100)
    tier = models.CharField(max_length=20, choices=PlanTier.choices)
    seat_capacity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    price_per_seat = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    
    # Generated field untuk recurring revenue bulanan
    monthly_run_rate = models.GeneratedField(
        expression=F("seat_capacity") * F("price_per_seat"),
        output_field=models.DecimalField(max_digits=12, decimal_places=2),
        db_persist=True,
    )

    feature_flags = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "enterprise_subscriptions"
        constraints = [
            # Satu org hanya boleh memiliki 1 subscription aktif pada satu waktu
            UniqueConstraint(
                fields=["organization_slug"],
                condition=Q(is_active=True),
                name="unique_active_subscription_per_org",
            ),
            # Harga per seat minimal $5.00
            CheckConstraint(
                condition=Q(price_per_seat__gte=Decimal("5.00")),
                name="chk_minimum_seat_price",
            ),
            # Organization slug harus huruf kecil murni
            CheckConstraint(
                condition=Q(organization_slug=Lower("organization_slug")),
                name="chk_slug_strictly_lowercase",
            ),
        ]
        indexes = [
            GinIndex(
                fields=["feature_flags"],
                name="gin_idx_sub_feature_flags",
                opclasses=["jsonb_path_ops"],
            )
        ]

    def __str__(self) -> str:
        return f"{self.organization_slug} - {self.tier}"
```

#### Langkah 3: Eksekusi Migrasi & Validasi Integritas

Pastikan PostgreSQL aktif, lalu eksekusi migrasi:

```bash
python manage.py makemigrations billing_engine
python manage.py migrate
```

#### Langkah 4: Pengujian Constraint Database
Tulis test case pada `hands-on/m02/billing_engine/tests/test_constraints.py` untuk membuktikan penegakan aturan di layer database:

```python
from decimal import Decimal
from django.db import IntegrityError
from django.test import TestCase
from billing_engine.models import EnterpriseSubscription


class SubscriptionConstraintTestCase(TestCase):
    def test_database_enforces_minimum_seat_price(self):
        """Memvalidasi CheckConstraint chk_minimum_seat_price."""
        with self.assertRaises(IntegrityError):
            EnterpriseSubscription.objects.create(
                organization_slug="acme-corp",
                tier=EnterpriseSubscription.PlanTier.STARTER,
                seat_capacity=10,
                price_per_seat=Decimal("4.99"),  # Pelanggaran: di bawah $5.00
                is_active=True,
            )

    def test_database_enforces_single_active_subscription_unique_constraint(self):
        """Memvalidasi UniqueConstraint kondisional."""
        EnterpriseSubscription.objects.create(
            organization_slug="fintech-ltd",
            tier=EnterpriseSubscription.PlanTier.BUSINESS,
            seat_capacity=50,
            price_per_seat=Decimal("15.00"),
            is_active=True,
        )

        # Mencoba membuat langganan aktif kedua untuk org yang sama
        with self.assertRaises(IntegrityError):
            EnterpriseSubscription.objects.create(
                organization_slug="fintech-ltd",
                tier=EnterpriseSubscription.PlanTier.ENTERPRISE,
                seat_capacity=100,
                price_per_seat=Decimal("12.00"),
                is_active=True,  # Pelanggaran UniqueConstraint
            )

    def test_generated_field_calculation_accuracy(self):
        """Memvalidasi GeneratedField terhitung tepat secara presisten di DB."""
        sub = EnterpriseSubscription.objects.create(
            organization_slug="scale-co",
            tier=EnterpriseSubscription.PlanTier.BUSINESS,
            seat_capacity=20,
            price_per_seat=Decimal("10.50"),
            is_active=True,
        )
        sub.refresh_from_db()
        self.assertEqual(sub.monthly_run_rate, Decimal("210.00"))
```

Jalankan test:
```bash
python manage.py test billing_engine.tests
```

---

### 13. Exercise

#### Level Easy
Ubah model `EnterpriseSubscription` dengan menambahkan kolom `cancellation_reason` bertipe `CharField(max_length=255, null=True, blank=True)`. Tambahkan `CheckConstraint` bernama `chk_reason_required_when_inactive` yang memastikan bahwa jika `is_active` bernilai `False`, maka `cancellation_reason` tidak boleh bernilai `NULL`.

#### Level Medium
Buat model `AuditLog` menggunakan teknik **Abstract Base Model** yang mengimplementasikan metadata penelusuran (IP Address, User Agent, Timestamp). Turunkan model ini ke dua model konkrit: `SecurityAuditLog` dan `BillingAuditLog`. Tambahkan indeks parsial pada `SecurityAuditLog` hanya untuk aksi yang berstatus `FAILURE`. Pastikan tidak ada tabel perantara yang dibuat.

#### Level Hard
Rancang skema model `SeatAllocation` yang menghubungkan entitas `User` dan `EnterpriseSubscription`. 
Terapkan batasan:
1. Satu user tidak boleh dialokasikan ke subscription yang sama lebih dari satu kali.
2. Gunakan `UniqueConstraint` komposit.
3. Cegah alokasi kursi melebihi kapasitas `seat_capacity` menggunakan PostgreSQL **Exclusion Constraint** (`django.contrib.postgres.constraints.ExclusionConstraint`) atau kombinasi F-expression locking untuk menjamin konkurensi aman dari *over-allocation*.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Database Engineer di sebuah startup logistik global. Sistem melacak status paket secara *real-time* yang menerima 5.000 ping status per detik.

**Spesifikasi Persyaratan**:
1. Buat model `PackageLocationUpdate` yang mencakup kolom:
   * `package_tracking_number` (String)
   * `coordinates` (PostGIS `PointField` atau kombinasi Float Latitude/Longitude yang divalidasi ketat)
   * `recorded_at` (DateTimeField)
   * `telemetry_data` (JSONB)
2. **Kebutuhan Partisi**: Skema tabel wajib menggunakan PostgreSQL *Declarative Range Partitioning* mingguan (*weekly*).
3. **Integritas Konkurensi**: Tambahkan constraint yang melarang input ping status yang waktu `recorded_at`-nya lebih dari 10 menit ke masa depan (*prevent clock drift corruption*) langsung di level database engine.
4. **Indeksasi Spesifik**: Susun indeks majemuk yang memungkinkan eksekusi query pencarian: *Ambil ping terbaru untuk resi X dalam 2 jam terakhir* berjalan di bawah **5 milidetik**.
5. **Zero-Downtime Rule**: Tuliskan arsitektur migrasi penuh dalam file migrasi native Django tanpa menggunakan `RunPython` yang memuat baris data ke memori Django worker.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda & Konseptual Singkat)
1. **Kapan metakelas `ModelBase` mengeksekusi introspeksi atribut model?**
   * A. Saat query pertama dieksekusi melalui `QuerySet`.
   * B. Saat Django mengompilasi migrasi menjadi skema SQL.
   * C. Saat modul Python yang mendefinisikan kelas Model diimpor oleh Python runtime.
   * D. Saat method `save()` pertama kali dipanggil.

2. **Apa dampak arsitektural utama dari Multi-Table Inheritance (MTI) pada operasi baca (`SELECT`)?**
   * A. Tidak ada dampak, setara dengan model biasa.
   * B. Django ORM secara otomatis menambahkan operasi `LEFT OUTER JOIN` atau `INNER JOIN` ke tabel induk.
   * C. Django ORM mengeksekusi dua query terpisah secara serial.
   * D. Operasi SELECT dilarang secara otomatis oleh database engine.

3. **Apa perbedaan mendasar antara `db_persist=True` dan `db_persist=False` pada `GeneratedField`?**
   * A. `True` menyimpannya di file log, `False` di tabel.
   * B. `True` membuat kolom STORED (disimpan di disk database), `False` membuat kolom VIRTUAL (dihitung saat dibaca).
   * C. `True` divalidasi oleh Python, `False` divalidasi oleh Database.
   * D. Tidak ada perbedaan pada PostgreSQL.

4. **Mengapa `atomic = False` wajib diatur pada migrasi yang memanggil `CREATE INDEX CONCURRENTLY`?**
   * A. Karena transaksi Django tidak mendukung syntax SQL raw.
   * B. PostgreSQL secara arsitektural melarang pembuatan indeks konkuren di dalam blok transaksi transaksional (transaction block).
   * C. Agar operasi migrasi dapat dibatalkan (*rollback*) jika gagal.
   * D. Memaksa migrasi dijalankan pada multi-threading engine.

5. **Apa fungsi dari atribut `opclasses` saat mendefinisikan `GinIndex` untuk kolom JSONB?**
   * A. Menentukan skema validasi JSON.
   * B. Menentukan operator classes PostgreSQL (seperti `jsonb_path_ops`) guna mengoptimalkan ukuran indeks dan operator query containment (`@>`).
   * C. Mengubah encoding JSON dari UTF-8 menjadi ASCII.
   * D. Menjamin konkurensi aman saat proses update JSONB.

#### Bagian 2: Intermediate (Analisis Kasus & Algoritma ORM)
6. Sebuah tim mengalami deadlock pada sistem antrean tugas berulang kali saat mengeksekusi migrasi penambahan kolom baru. Tabel berukuran 80GB. Apa penyebab mekanis di level PostgreSQL dan bagaimana penanganannya melalui deklarasi model Django?
7. Analisis potongan kode berikut. Apakah aman dari *race condition* konkurensi? Jelaskan alasannya:
   ```python
   def transfer_credits(sender_id, receiver_id, amount):
       sender = Wallet.objects.get(id=sender_id)
       if sender.balance >= amount:
           sender.balance -= amount
           sender.save()
   ```
8. Jelaskan perbedaan mendalam antara pemanfaatan `Proxy Model` dibandingkan dengan meng-override instance `Manager` standar pada model konkrit yang sama!
9. Mengapa penggunaan `Index(fields=['created_at'], condition=Q(is_deleted=False))` lebih superior dibanding `Index(fields=['created_at', 'is_deleted'])` pada kasus *soft-delete* di mana 95% data berstatus aktif?
10. Bagaimana cara Django `MigrationAutodetector` mengetahui bahwa sebuah kolom telah diubah namanya (*renamed*) dan bukan dihapus lalu dibuat baru (*dropped and recreated*)?

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario 1 (Partitioning Failure)**:
    Anda memiliki model transaksional dengan 500 juta baris data yang menggunakan Django declarative partitioning pada field `created_at`. Seorang developer baru mencoba menambahkan relasi `ForeignKey(User, on_delete=models.CASCADE)` biasa ke model tersebut, dan menambahkan constraint `UniqueConstraint(fields=['id'])`. PostgreSQL melempar error penolakan DDL. Analisis penyebab struktural error tersebut dan berikan solusi perbaikannya!
12. **Skenario 2 (Lock Contention saat Peak Traffic)**:
    Pada jam sibuk, Anda harus menerapkan migrasi penambahan field status audit:
    `alter table user_sessions add column is_compromised boolean not null default false;`
    Bagaimana Anda mendesain file migrasi Django native yang membagi operasi tersebut menjadi langkah-langkah yang meminimalisir waktu penguncian tabel (*lock queue*) ke nol detik?
13. **Skenario 3 (JSONB Schema Drift)**:
    Sistem Anda menggunakan kolom `metadata = models.JSONField(default=dict)`. Setelah dua tahun, terdapat inkonsistensi struktur JSON di mana field `metadata['tax_identifier']` terkadang berupa integer, string, atau bahkan tidak ada. Anda ditugaskan untuk menambahkan database check constraint guna memastikan bahwa ke depannya: "Jika `metadata` memiliki key `tax_identifier`, nilainya WAJIB berupa teks numerik 16 digit". Tuliskan implementasi constraint Django ORM tersebut!

---

### 16. Summary

1. **Metaclass & Models Internal**: Model Django adalah deklarasi berbasis metakelas `ModelBase` yang mengabstraksi representasi skema ke dalam `_meta`. Pemahaman internal ini memungkinkan manipulasi skema dinamis dan optimasi kompilasi query SQL.
2. **Model Inheritance Cost**: Hindari Multi-Table Inheritance (MTI) pada aplikasi dengan beban throughput tinggi karena implicit `OneToOneField` memicu penalti query `JOIN` yang berat. Utamakan **Abstract Base Classes** untuk *code reuse* dan **Proxy Models** untuk diferensiasi perilaku.
3. **Database-Level Invariance**: Mengandalkan validasi di tingkat aplikasi (`Model.clean()`) meninggalkan celah terhadap *race conditions*. Selalu dorong aturan integritas ke dalam database engine menggunakan `CheckConstraint` dan `UniqueConstraint` kondisional.
4. **Modem PostgreSQL Power**: Maksimalkan fitur database modern seperti `GeneratedField` (STORED/VIRTUAL), GIN Indexing dengan `jsonb_path_ops`, dan ArrayFields untuk menggabungkan fleksibilitas NoSQL dengan garansi ACID relasional.
5. **Zero-Downtime Lifecycle**: Di skala produksi, eksekusi DDL harus memperhitungkan hierarki penguncian database. Penggunaan `atomic = False` yang dikombinasikan dengan pembuatan indeks konkuren (`AddIndexConcurrently`) serta pemisahan migrasi state/database adalah standar wajib rekayasa perangkat lunak enterprise.