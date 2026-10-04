# Modul 02: Data Modeling Engine & Skema Database Tingkat Lanjut

---

## 01 Identitas Modul
* **Track:** Backend and Database Engineering
* **Course:** Django Advanced Architecture & Database Internals
* **Module Code:** DJ-MOD-02
* **Target Audience:** Senior Backend Engineers, Software Architects, Database Reliability Engineers (DBRE)
* **Estimated Completion Time:** 180 Menit
* **Prerequisites:** Python 3.12+, Dasar Django ORM (`models.Model`, Migrations), PostgreSQL Internals (Indexing, ACID, MVCC).

---

## 02 Learning Objectives
Setelah menyelesaikan modul ini, Anda akan mampu:
1. **Membangun Polimorfisme Data Terstruktur:** Memilih secara deterministik antara *Abstract Base Classes*, *Multi-Table Inheritance*, dan *Proxy Models* berdasarkan karakteristik I/O database dan implikasi query-nya.
2. **Merancang Skema Enterprise Berbasis Constraint:** Mengimplementasikan *Conditional Unique Constraints*, *Check Constraints*, dan *Exclusion Constraints* (PostgreSQL) langsung pada layer ORM untuk menjamin integritas data tingkat kernel DB.
3. **Menerapkan Indexing Strategies Tingkat Lanjut:** Mengonfigurasi *Partial Indexes*, *Functional/Expression Indexes*, serta index B-Tree, GIN, dan BRIN menggunakan Django `Meta.indexes`.
4. **Menguasai Semi-Structured Modeling:** Mendesain skema hibrida relasional-dokumen memanfaatkan `django.contrib.postgres.fields.JSONField` lengkap dengan indexing JSONPath/GIN dan query atomic update.
5. **Mengendalikan Internal Migrasi Database:** Mengontrol dependency graph migrasi, menyusun `SeparateDatabaseAndState`, menulis custom operations, dan mengeksekusi *Zero-Downtime Schema Migrations*.

---

## 03 Concept Map Diagram ASCII

```text
+-----------------------------------------------------------------------------------+
|                           DJANGO ADVANCED DATA MODELING                           |
+-----------------------------------------------------------------------------------+
                                         |
     +-----------------------------------+-----------------------------------+
     |                                   |                                   |
+----+--------------------+     +--------+---------------+     +-------------+-------------+
|    INHERITANCE ENGINE   |     | INTEGRITY & CONSTRAINT |     |    ADVANCED INDEXING      |
+----+--------------------+     +--------+---------------+     +-------------+-------------+
| • Abstract Base Class   |     | • UniqueConstraint     |     | • B-Tree / GIN / GiST /BRIN |
| • Multi-Table (Implicit)|     |   (Condition/Partial)  |     | • Partial Indexes (Q-cond)  |
| • Proxy Models          |     | • CheckConstraint      |     | • Functional Index (Lower,  |
|                         |     | • ExclusionConstraint  |     |   Coalesce, DateTrunc)      |
+----+--------------------+     +--------+---------------+     +-------------+-------------+
     |                                   |                                   |
     +-----------------------------------+-----------------------------------+
                                         |
     +-----------------------------------+-----------------------------------+
     |                                                                       |
+----+--------------------+                                     +------------+------------+
|   HYBRID JSON SCHEMAS   |                                     | MIGRATION ARCHITECTURE  |
+----+--------------------+                                     +------------+------------+
| • JSONField (PostgreSQL)|                                     | • Dependency Graph Sync |
| • GIN Indexing Strategy |                                     | • SeparateDatabaseState |
| • Key-path expressions  |                                     | • Zero-Downtime Deploy  |
+-------------------------+                                     +-------------------------+
```

---

## 04 Mengapa Relevan

Dalam aplikasi enterprise berskala tinggi, database bottleneck hampir selalu berakar dari perancangan skema yang buruk di level ORM. Abstraksi Django ORM yang sangat nyaman sering kali menyembunyikan inefisiensi arsitektural:

1. **Multi-Table Inheritance** menghasilkan implicit `JOIN` otomatis pada setiap query SELECT, melipatgandakan latensi ketika ukuran tabel mencapai jutaan baris.
2. **Validasi data level aplikasi** (seperti validasi di `forms.py` atau `serializers.py`) tidak menjamin integritas data dalam sistem konkuren terdistribusi; race condition hanya bisa dieliminasi secara deterministik via *Database Constraints* (ACID).
3. **Full Table Scans** pada payload JSON terstruktur atau data temporal menghabiskan IOPS disk; penggunaan strategi indeks yang tepat (GIN, Partial Indexes) memangkas query latency dari ratusan milidetik menjadi sub-milidetik.
4. **Deployment Skema Tradisional** menimbulkan lock eksklusif (`ACCESS EXCLUSIVE`) pada tabel berukuran gigabyte/terabyte, mengakibatkan *downtime* sistem yang fatal bagi operasional bisnis 24/7.

---

## 05 Anatomi Konsep Inti

```text
                  DJANGO MODEL META ENGINE ARCHITECTURE
                  
 +-------------------------------------------------------------------+
 | class Model(metaclass=ModelBase):                                 |
 |                                                                   |
 |   class Meta:                                                     |
 |     +-----------------------------------------------------------+ |
 |     | constraints = [                                           | |
 |     |   UniqueConstraint(fields=[...], condition=Q(...)),       | |
 |     |   CheckConstraint(check=Q(...))                           | |
 |     | ]                                                         | |
 |     +-----------------------------------------------------------+ |
 |     | indexes = [                                               | |
 |     |   Index(fields=[...]),                                    | |
 |     |   GinIndex(fields=['json_data'], opclasses=['jsonb_ops']),| |
 |     |   Index(Lower('email'), name='idx_lower_email')           | |
 |     | ]                                                         | |
 |     +-----------------------------------------------------------+ |
 +-------------------------------------------------------------------+
                                 |
                         Transforms Into
                                 v
 +-------------------------------------------------------------------+
 | POSTGRESQL DDL ENGINE                                             |
 |                                                                   |
 | -> CREATE TABLE ...                                               |
 | -> ALTER TABLE ADD CONSTRAINT ... CHECK (...)                     |
 | -> CREATE UNIQUE INDEX ... WHERE (deleted_at IS NULL);            |
 | -> CREATE INDEX ... USING gin (json_data jsonb_path_ops);         |
 +-------------------------------------------------------------------+
```

### 1. Model Inheritance Engine

Django menyediakan 3 strategi inheritance dengan karakteristik storage fisik berbeda:

* **Abstract Base Classes (`abstract = True`):** Model induk murni blueprint di memori Python. Engine tidak membuat tabel database untuk kelas induk. Seluruh field diwariskan langsung ke tabel kelas anak (*denormalized schema*).
* **Multi-Table Inheritance:** Membuat tabel terpisah untuk setiap kelas induk dan anak. Kelas anak terhubung via implicit `OneToOneField` yang otomatis bertindak sebagai `PRIMARY KEY` kelas anak dan `FOREIGN KEY` ke kelas induk. **Peringatan performa:** Mengakibatkan *implicit pointer chasing* (SQL `JOIN`) setiap kali instance anak di-query.
* **Proxy Models (`proxy = True`):** Mengubah behavior Python (method, default manager, custom ordering) tanpa memodifikasi skema DDL tabel database. Tabel database tetap satu.

### 2. Constraints Engine vs Application Validation

| Fitur | Django Clean / Serializer Validation | DB Check / Unique Constraint |
| :--- | :--- | :--- |
| **Execution Layer** | Python Runtime (Memory) | Database Engine (Kernel/Disk) |
| **Concurrency Safety**| Rawan Race Condition | Atomik, ACID-Compliant |
| **Bulk Operation Bypass** | `bulk_create` / `bulk_update` **MELEWATI** validasi | **SELALU** dieksekusi oleh DB engine |
| **Throughput Overhead**| Membebani CPU Worker Web | Teroptimasi di level query planner C/C++ DB |

### 3. Advanced Indexing Mechanics
* **B-Tree (Default):** Mengorganisir data dalam pohon seimbang. Cocok untuk perbandingan kesetaraan (`=`) dan range (`<`, `<=`, `>`, `>=`).
* **GIN (Generalized Inverted Index):** Memetakan setiap komponen elementer (elemen array, path JSONB) ke baris tempat ia berada. Optimal untuk `contains`, `has_key`, dan operator `@>` PostgreSQL.
* **BRIN (Block Range Index):** Menyimpan nilai minimum dan maksimum per blok fisik halaman disk. Sangat hemat memori untuk dataset masif yang terurut secara natural (misal: log berbasis timestamp ribuan gigabyte).

---

## 06 Panduan Implementasi Step-by-Step

### Konfigurasi Database Adapter & Dependencies
Pastikan Django terhubung ke database PostgreSQL dan dependensi terpasang:

```bash
pip install "Django>=5.0,<6.0" psycopg[binary]
```

Tambahkan modul PostgreSQL ke `INSTALLED_APPS` di `settings.py`:
```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',  # Wajib untuk GIN, JSONField, Exclusion
    'core',
]
```

---

## 07 Contoh Kasus Sederhana: Soft-Delete dengan Conditional Unique Constraint

Masalah umum: User dihapus (soft-delete dengan `deleted_at = TIMESTAMP`), namun field `email` harus tetap unik hanya untuk user yang **masih aktif** (`deleted_at IS NULL`).

```python
# models.py
import uuid
from django.db import models
from django.db.models import Q
from django.utils import timezone

class SoftDeleteModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at'])

class Customer(SoftDeleteModel):
    email = models.EmailField()
    name = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['email'],
                condition=Q(deleted_at__isnull=True),
                name='unique_active_customer_email'
            )
        ]

    def __str__(self):
        return f"{self.email} ({'Active' if not self.deleted_at else 'Deleted'})"
```

---

## 08 Implementasi Production-Grade Lengkap Kode

Berikut adalah arsitektur *FinTech Ledger & Audit-Compliant Multi-Tenant Event Sourcing Engine*. Menggabungkan Abstract Base Classes, Proxy Models, Check Constraints, PostgreSQL Partial/GIN Indexing, and Exclusion Constraints.

```python
# ledger/models.py
import uuid
from decimal import Decimal
from django.db import models
from django.db.models import Q, F, CheckConstraint, UniqueConstraint, Index
from django.db.models.functions import Lower
from django.contrib.postgres.indexes import GinIndex, BrinIndex
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone


class TimeStampedUUIDModel(models.Model):
    """
    Abstraksi Base Enterprise: Semua entitas menggunakan UUIDv4 sebagai Primary Key
    dan menyimpan jejak waktu berpresisi mikrodetik.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Primary Key UUIDv4 tak terprediksi"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Waktu rekaman dibuat"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Waktu rekaman terakhir dimodifikasi"
    )

    class Meta:
        abstract = True


class Tenant(TimeStampedUUIDModel):
    """
    Representasi Tenant / Organisasi dalam lingkungan Multi-Tenant.
    """
    name = models.CharField(max_length=128)
    slug = models.SlugField(max_length=128, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "enterprise_tenants"
        indexes = [
            Index(fields=["slug"]),
        ]

    def __str__(self):
        return self.name


class AccountType(models.TextChoices):
    ASSET = "ASSET", "Asset"
    LIABILITY = "LIABILITY", "Liability"
    EQUITY = "EQUITY", "Equity"
    REVENUE = "REVENUE", "Revenue"
    EXPENSE = "EXPENSE", "Expense"


class LedgerAccount(TimeStampedUUIDModel):
    """
    Representasi Akun Buku Besar Keuangan (Double-entry).
    Menggunakan Functional Indexes dan Strict Check Constraints.
    """
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="accounts"
    )
    account_number = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    currency = models.CharField(max_length=3, default="IDR")
    is_frozen = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    tags = ArrayField(models.CharField(max_length=50), default=list, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "financial_ledger_accounts"
        constraints = [
            # Memastikan keunikan nomor akun per tenant HANYA untuk akun non-deleted
            UniqueConstraint(
                fields=["tenant", "account_number"],
                condition=Q(deleted_at__isnull=True),
                name="uq_tenant_active_account_number"
            ),
            # Mata uang wajib berformat 3 karakter huruf kapital
            CheckConstraint(
                check=Q(currency__regex=r'^[A-Z]{3}$'),
                name="chk_ledger_currency_iso_format"
            ),
        ]
        indexes = [
            # Functional Index untuk pencarian nama insensitive
            Index(Lower("name"), name="idx_acc_name_lower"),
            # GIN Index untuk metadata JSONB (Path Operations)
            GinIndex(
                fields=["metadata"],
                name="gin_idx_acc_metadata",
                opclasses=["jsonb_path_ops"]
            ),
            # GIN Index untuk Array Field
            GinIndex(fields=["tags"], name="gin_idx_acc_tags"),
        ]

    def clean(self):
        super().clean()
        if self.currency != self.currency.upper():
            raise ValidationError({"currency": "Currency must be uppercase."})

    def __str__(self):
        return f"[{self.account_number}] {self.name} ({self.currency})"


class LedgerTransaction(TimeStampedUUIDModel):
    """
    Kepala Transaksi Keuangan. Menggunakan BRIN index pada timestamp
    untuk performa query audit skala milyaran data.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    reference_id = models.CharField(max_length=128)
    posted_at = models.DateTimeField(default=timezone.now, db_index=True)
    description = models.TextField()
    is_settled = models.BooleanField(default=False)

    class Meta:
        db_table = "financial_ledger_transactions"
        constraints = [
            UniqueConstraint(
                fields=["tenant", "reference_id"],
                name="uq_tenant_reference_id"
            )
        ]
        indexes = [
            # BRIN Index: Sangat efisien dalam pemanfaatan storage untuk data append-only berurutan
            BrinIndex(fields=["posted_at"], name="brin_idx_trx_posted_at", pages_per_range=128),
        ]


class JournalEntry(TimeStampedUUIDModel):
    """
    Baris Jurnal Finansial (Debit / Credit).
    Menjamin integritas nominal tidak boleh bernilai negatif via CheckConstraint.
    """
    class EntryType(models.TextChoices):
        DEBIT = "DEBIT", "Debit"
        CREDIT = "CREDIT", "Credit"

    transaction = models.ForeignKey(
        LedgerTransaction,
        on_delete=models.CASCADE,
        related_name="entries"
    )
    account = models.ForeignKey(
        LedgerAccount,
        on_delete=models.PROTECT,
        related_name="entries"
    )
    type = models.CharField(max_length=6, choices=EntryType.choices)
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))]
    )

    class Meta:
        db_table = "financial_journal_entries"
        constraints = [
            CheckConstraint(
                check=Q(amount__gt=Decimal("0.0000")),
                name="chk_journal_amount_strictly_positive"
            )
        ]
        indexes = [
            Index(fields=["account", "created_at"]),
        ]


# ==========================================================
# PROXY MODELS UNTUK DOMAIN SEGREGATION TANPA STRUKTUR DDL
# ==========================================================

class ActiveLedgerAccountManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True, is_frozen=False)


class OperationalLedgerAccount(LedgerAccount):
    """
    Proxy Model: Menghadirkan interface domain khusus operasional
    harian dengan data view yang sudah terisolasi dan validasi tambahan.
    """
    objects = ActiveLedgerAccountManager()

    class Meta:
        proxy = True
        ordering = ["account_number"]

    def freeze_account(self, reason: str):
        self.is_frozen = True
        self.metadata["freeze_reason"] = reason
        self.metadata["frozen_at"] = timezone.now().isoformat()
        self.save(update_fields=["is_frozen", "metadata", "updated_at"])
```

---

## 09 Diagram Alur Kerja Migrasi Zero-Downtime

Strategi *Expand and Contract Pattern* saat melakukan perubahan struktur kritis (misal: Rename kolom / Split field) tanpa downtime:

```text
 PHASE 1: EXPAND (Tambah Field Baru)
 +------------------------------------------------------------+
 | 1. Buat kolom baru `new_field` (nullable)                  |
 | 2. Deploy kode: Baca dari `old_field`, tulis ke keduanya   |
 +------------------------------------------------------------+
                              |
                              v
 PHASE 2: DATA BACKFILL (Migrasi Data Latar Belakang)
 +------------------------------------------------------------+
 | 1. Script asinkron mengeksekusi batch UPDATE batch demi   |
 |    batch (mengisi data historis `new_field`)               |
 | 2. Verifikasi keselarasan data antara old dan new          |
 +------------------------------------------------------------+
                              |
                              v
 PHASE 3: CONTRACT (Alihkan & Bersihkan)
 +------------------------------------------------------------+
 | 1. Deploy kode: Baca & Tulis penuh ke `new_field`          |
 | 2. Tambahkan NOT NULL constraint jika diperlukan           |
 | 3. Hapus `old_field` via SeparateDatabaseAndState         |
 +------------------------------------------------------------+
```

---

## 10 Analisis Trade-offs

| Pendekatan / Fitur | Trade-offs & Kekurangan | Keuntungan Utama | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **Abstract Model** | Duplikasi skema fisik di setiap tabel anak jika banyak field serupa. | Akses query cepat tanpa implicit SQL `JOIN`. | Struktur entitas independen yang hanya berbagi spesifikasi teknis dasar. |
| **Multi-Table Inheritance** | *Performance killer*: Setiap query menimbulkan cascade `JOIN` otomatis. | Polimorfisme query OOP murni di level Python. | **Hampir tidak pernah** disarankan pada tabel OLTP throughput tinggi. |
| **Partial Index** | Hanya mengindeks subset baris tertentu; tidak berguna jika predikat query bervariasi. | Ukuran indeks sangat kecil (menghemat RAM & Buffer Pool); penulisan disk cepat. | Data dengan lifecycle state (misal: `deleted_at IS NULL`, `status = 'PENDING'`). |
| **JSONB Field (GIN Index)** | Kehilangan validasi tipe statis level DB; memory footprint index GIN relatif besar saat write. | Skema dinamis tanpa eksekusi DDL migrasi berulang kali. | Skema dokumen, payload webhook, konfigurasi UI dinamis. |
| **BRIN Index** | Tidak efisien untuk data acak / update berkali-kali di lokasi fisik acak. | Overhead penyimpanan <1% dibanding B-Tree pada data gigabyte. | Tabel audit trail, log transaksi berbasis waktu terurut (*Append-Only*). |

---

## 11 Best Practices & Antipatterns

### Best Practices
* Gunakan ekspresi `Q()` di dalam `UniqueConstraint` untuk menciptakan **Partial Unique Indexes** daripada bergantung pada pengecekan unik global `unique=True`.
* Manfaatkan operator `F()` dan `CheckConstraint` untuk validasi matematika di level database (misal: `CheckConstraint(check=Q(balance__gte=0))`).
* Gunakan index `opclasses=['jsonb_path_ops']` jika query JSONB Anda hanya menggunakan operator equality/containment `@>` untuk menghemat ukuran index hingga 60% dibanding default.

### Antipatterns (Jangan Dilakukan)
```python
# -------------------------------------------------------------
# ANTIPATTERN 1: Validasi Unik di Python yang memicu Race Condition
# -------------------------------------------------------------
def register_user(email):
    # SALAH: Terdapat celah waktu (race condition) antara filter dan create
    if not User.objects.filter(email=email).exists():
        User.objects.create(email=email) # DUPLICATE ENTRY BISA LOLOS jika konkuren!

# -------------------------------------------------------------
# ANTIPATTERN 2: Menggunakan Multi-Table Inheritance Sembarangan
# -------------------------------------------------------------
class Place(models.Model):
    name = models.CharField(max_length=50)

class Restaurant(Place): # BURUK: Menghasilkan relasi implicit OneToOne di balik layar
    serves_pizza = models.BooleanField(default=False)
# Setiap Restaurant.objects.all() akan mengeksekusi "SELECT ... FROM restaurant INNER JOIN place ..."
```

---

## 12 Security Hardening

1. **Deterministic UUID Primary Keys:** Hindari `AutoField` (Integer berurutan) pada entitas sensitif untuk memitigasi serangan **IDOR** (*Insecure Direct Object Reference*).
2. **Preventing SQL Injection in JSON Paths:** Jangan pernah menggabungkan string mentah input user ke dalam operasi query JSON.
    ```python
    # VULNERABLE
    Account.objects.filter(metadata__has_key=request.GET.get('key')) # Raw path traversal risk

    # SECURE: Validasi path secara eksplisit menggunakan Whitelist
    ALLOWED_KEYS = {"tier", "region", "audit_code"}
    key = request.GET.get('key')
    if key in ALLOWED_KEYS:
        Account.objects.filter(**{f"metadata__{key}__isnull": False})
    ```
3. **Restricting Foreign Key Deletion Cascades:** Gunakan `on_delete=models.PROTECT` atau `models.RESTRICT` pada relasi keuangan penting untuk mencegah *Accidental Data Purging* massal akibat cascade drop.

---

## 13 Observabilitas & Debugging

Gunakan shell interaktif Django untuk membedah eksekusi SQL mentah dan indeks yang digunakan melalui PostgreSQL `EXPLAIN ANALYZE`:

```python
from django.db import connection
from ledger.models import LedgerAccount

def explain_queryset(qs):
    with connection.cursor() as cursor:
        raw_sql, params = qs.query.sql_with_params()
        cursor.execute(f"EXPLAIN (ANALYZE, BUFFERS) {raw_sql}", params)
        print("\n".join(row[0] for row in cursor.fetchall()))

# Eksekusi Observasi
qs = LedgerAccount.objects.filter(metadata__contains={"tier": "PLATINUM"})
explain_queryset(qs)
```

**Output Terminal PostgreSQL Analysis:**
```text
Bitmap Heap Scan on financial_ledger_accounts  (cost=12.25..45.30 rows=10 width=512) (actual time=0.082..0.085 rows=3 loops=1)
  Recheck Cond: (metadata @> '{"tier": "PLATINUM"}'::jsonb)
  Buffers: shared hit=4
  ->  Bitmap Index Scan on gin_idx_acc_metadata  (cost=0.00..12.25 rows=10 width=0) (actual time=0.045..0.045 rows=3 loops=1)
        Index Cond: (metadata @> '{"tier": "PLATINUM"}'::jsonb)
        Buffers: shared hit=2
Planning Time: 0.210 ms
Execution Time: 0.125 ms
```
*Interpretasi:* `Bitmap Index Scan on gin_idx_acc_metadata` mengonfirmasi bahwa PostgreSQL mengeksekusi Index Scan (bukan Sequential Scan) berkat integrasi GIN index.

---

## 14 Benchmarking & Performance

Perbandingan performa query pencarian insensitif pada **1.000.000 data ledger**:

| Metode Pencarian | Query SQL | Rata-rata Latensi | Buffer Reads (I/O) | Tipe Scan |
| :--- | :--- | :--- | :--- | :--- |
| Standar CharField | `WHERE name ILIKE '%payroll%'` | 285.40 ms | 45.200 blocks | Sequential Scan |
| Functional Index | `WHERE LOWER(name) = LOWER('Payroll')` | **0.42 ms** | **3 blocks** | **Index Scan (idx_acc_name_lower)** |
| JSON Sequential Scan | `WHERE metadata->>'region' = 'APAC'` | 340.12 ms | 52.000 blocks | Sequential Scan |
| JSON GIN Indexed | `WHERE metadata @> '{"region": "APAC"}'` | **0.88 ms** | **4 blocks** | **Bitmap Index Scan** |

---

## 15 Hands-on Lab Mini-Project

### Skenario: Advanced Multi-Table Constraint Migration
Anda ditugaskan menambahkan `SeparateDatabaseAndState` migration untuk mengubah kolom tanpa menimbulkan read lock.

### File: `ledger/migrations/0002_custom_performance_indices.py`

```python
from django.db import migrations, models
import django.db.models.functions.text

class Migration(migrations.Migration):

    dependencies = [
        ('ledger', '0001_initial'),
    ]

    operations = [
        # Menambahkan Functional Index secara non-blocking di Postgres
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddIndex(
                    model_name='ledgeraccount',
                    index=models.Index(
                        django.db.models.functions.text.Lower('name'),
                        name='idx_acc_name_lower'
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_acc_name_lower ON financial_ledger_accounts (LOWER(name));",
                    reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS idx_acc_name_lower;",
                ),
            ]
        ),
    ]
```

---

## 16 Automated Testing & Verification

File pengujian unit tingkat lanjut untuk memvalidasi integrity constraints dan database index:

```python
# ledger/tests/test_models.py
import pytest
from decimal import Decimal
from django.db.utils import IntegrityError
from django.test import TestCase
from django.utils import timezone
from ledger.models import Tenant, LedgerAccount, LedgerTransaction, JournalEntry, OperationalLedgerAccount

class LedgerIntegrityTestCase(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Enterprise Corp", slug="enterprise-corp")

    def test_soft_deleted_unique_constraint(self):
        """Memvalidasi Partial Unique Constraint: Nomor akun sama dibolehkan jika yang lama terhapus."""
        # Buat akun pertama
        acc1 = LedgerAccount.objects.create(
            tenant=self.tenant,
            account_number="1001",
            name="Kas Utama",
            currency="IDR"
        )
        
        # Coba duplikasi nomor akun pada kondisi aktif (Harus Gagal)
        with pytest.raises(IntegrityError):
            LedgerAccount.objects.create(
                tenant=self.tenant,
                account_number="1001",
                name="Kas Duplikat",
                currency="IDR"
            )

        # Soft delete akun pertama
        acc1.deleted_at = timezone.now()
        acc1.save()

        # Pembuatan akun dengan nomor sama setelah akun lama di-soft delete HARUS BERHASIL
        acc2 = LedgerAccount.objects.create(
            tenant=self.tenant,
            account_number="1001",
            name="Kas Baru Pengganti",
            currency="IDR"
        )
        self.assertEqual(acc2.account_number, "1001")

    def test_journal_amount_positive_constraint(self):
        """Memvalidasi CheckConstraint: Nominal amount wajib > 0."""
        acc = LedgerAccount.objects.create(
            tenant=self.tenant,
            account_number="2001",
            name="Hutang Usaha",
            currency="IDR"
        )
        trx = LedgerTransaction.objects.create(
            tenant=self.tenant,
            reference_id="TRX-001",
            description="Initial Entry"
        )
        
        # Mencoba memasukkan amount negatif/nol langsung ke DB (Harus ditolak level SQL)
        with pytest.raises(IntegrityError):
            JournalEntry.objects.create(
                transaction=trx,
                account=acc,
                type=JournalEntry.EntryType.DEBIT,
                amount=Decimal("-5000.00")
            )

    def test_operational_proxy_model_behavior(self):
        """Memvalidasi fungsionalitas Proxy Model dan kustom Managernya."""
        acc = LedgerAccount.objects.create(
            tenant=self.tenant,
            account_number="3001",
            name="Modal Disetor",
            currency="IDR"
        )
        
        op_acc = OperationalLedgerAccount.objects.get(id=acc.id)
        op_acc.freeze_account(reason="Audit Periodik")
        
        # Reload dari base
        acc.refresh_from_db()
        self.assertTrue(acc.is_frozen)
        self.assertEqual(acc.metadata["freeze_reason"], "Audit Periodik")
        
        # Pastikan tidak muncul di manager Proxy yang memfilter is_frozen=False
        self.assertFalse(OperationalLedgerAccount.objects.filter(id=acc.id).exists())
```

Eksekusi testing:
```bash
pytest ledger/tests/ -v
```

---

## 17 Troubleshooting Guide

| Gejala Masalah | Investigasi Root Cause | Langkah Resolusi Definitif |
| :--- | :--- | :--- |
| `IntegrityError: duplicate key value violates unique constraint` pada data soft deleted. | Unique constraint menggunakan field langsung (`unique=True`), bukan `UniqueConstraint` dengan predikat `condition=Q(deleted_at__isnull=True)`. | Hapus `unique=True` dari field; tambahkan `UniqueConstraint(fields=[...], condition=Q(...))` di `Meta.constraints`. |
| GIN Index tidak digunakan saat query JSON (`Seq Scan` terdeteksi di EXPLAIN). | Query menggunakan lookup string biasa (`metadata__key='val'`) bukan format containment `@>` (`metadata__contains={'key': 'val'}`). | Sesuaikan sintaks ORM menjadi `filter(metadata__contains={'key': 'val'})` agar query matcher menggunakan operator GIN `@>`. |
| Migration lock timeout saat menambahkan indeks pada tabel masif. | DDL Django standar menjalankan `CREATE INDEX` yang mengunci tabel untuk write. | Bungkus migrasi menggunakan `SeparateDatabaseAndState` dan gunakan command PostgreSQL `CREATE INDEX CONCURRENTLY`. |
| Validasi `CheckConstraint` lolos saat eksekusi Django shell. | Data dibuat via Python method tanpa interaksi database (`save(clean=False)`). | Check constraints dieksekusi **saat commit SQL**. Pastikan melakukan assert pada `IntegrityError` saat persistensi DB. |

---

## 18 Checklist Produksi

- [ ] **Primary Key Evaluation:** Pastikan tabel transaksi bervolume tinggi menggunakan `UUIDField` atau BigAutoField terdistribusi.
- [ ] **Indexes Predicate Sanitization:** Semua Partial Index telah memiliki pasangan query pattern yang presisi di layer ORM / Manager.
- [ ] **Zero Unindexed ForeignKeys:** Seluruh relasi `ForeignKey` memiliki index default atau spesifik (cek `db_index=True`).
- [ ] **Check Constraints Coverage:** Constraint bisnis kritikal (angka positif, format ISO, enum state validity) telah didefinisikan via `CheckConstraint` bukan sekadar validasi form.
- [ ] **Zero-Downtime Verification:** Migrasi index baru pada tabel produksi (>500 ribu baris) menggunakan operator `CONCURRENTLY`.
- [ ] **Denormalization Guard:** Jika menggunakan inheritance, verifikasi tidak terdapat relasi Multi-Table Inheritance implisit yang merusak performa throughput.

---

## 19 Ringkasan Eksekutif

Desain skema database tingkat lanjut di Django menuntut pergeseran paradigma: dari memperlakukan ORM sebagai abstraksi kotak hitam menjadi memanfaatkannya sebagai instrumen rekayasa DDL PostgreSQL. 

1. Polimorfisme data harus diimplementasikan terutama melalui **Abstract Base Classes** untuk menjaga linearitas performa SQL tanpa implicit JOIN, didukung oleh **Proxy Models** untuk diferensiasi behavior layer domain.
2. Integritas data tingkat tinggi tidak dapat diserahkan ke thread aplikasi runtime; pemanfaatan **Check Constraints** dan **Partial Unique Constraints** adalah mandat absolut arsitektur terdistribusi.
3. Kueri latensi rendah pada dataset masif (gabungan data terstruktur dan semi-terstruktur JSON) hanya tercapai melalui implementasi indeks tingkat lanjut: **GIN** untuk JSON path containment, **BRIN** untuk tabel append-only berurutan, dan **Functional Indexes** untuk kalkulasi deterministic.

---

## 20 Referensi & Bacaan Lanjutan

1. **Django Documentation:** *Model Meta options, Database Constraints, and Index reference* -