# BAB-02-Data-Modeling-Engine-Skema-Database-Tingkat-Lanjut: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang sebagai instrumen evaluasi komprehensif untuk menguji pemahaman arsitektur pemodelan data, integritas relasional, teknik indexing, constraint level engine, serta migrasi skema tingkat lanjut pada Django ORM dan PostgreSQL.

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1.1: Perilaku On-Delete Cascade vs Protect vs Do Nothing
Jelaskan perbedaan mendasar pada level database engine dan Django ORM antara opsi relasi ForeignKey: `models.CASCADE`, `models.PROTECT`, dan `models.DO_NOTHING`. Kapan penggunaan `models.DO_NOTHING` menimbulkan bahaya fatal `IntegrityError`?

**Jawaban Teknis:**
*   `models.CASCADE`: Menghapus baris referensi secara berantai. Django melakukan emulasi kaskade di layer aplikasi secara default atau mengandalkan constraint `ON DELETE CASCADE` di database engine, sehingga objek turunan terhapus otomatis saat parent terhapus.
*   `models.PROTECT`: Mencegah penghapusan objek parent dengan melempar pengecualian `django.db.models.ProtectedError` pada tingkat runtime aplikasi sebelum query delete dikirim ke database.
*   `models.DO_NOTHING`: Menginstruksikan Django ORM untuk tidak mengambil tindakan pencegahan atau cascading apa pun di sisi aplikasi.
*   *Bahaya Fatal*: Jika foreign key pada database engine memiliki foreign key constraint aktif, operasi delete pada tabel parent akan ditolak langsung oleh RDBMS dan memicu fatal exception `django.db.utils.IntegrityError` (`violates foreign key constraint`). Jika database tidak memiliki foreign key constraint, hal ini menghasilkan *orphaned records* (data yatim/rusak integritas referensialnya).

---

### Soal 1.2: Perbedaan Abstrak Model vs Multi-Table Inheritance vs Proxy Model
Sebutkan implikasi skema fisik DDL database antara:
1. `class Meta: abstract = True`
2. Multi-Table Inheritance (subclass dari model konkrit)
3. `class Meta: proxy = True`

**Jawaban Teknis:**
1. **Abstract Model**: Tidak menghasilkan tabel fisik database baru. Semua field yang didefinisikan disuntikkan (*inlined*) langsung ke skema tabel kelas turunan masing-masing saat migrasi.
2. **Multi-Table Inheritance**: Membuat tabel fisik terpisah untuk child model dan parent model. Django mengaitkan keduanya secara implisit via `OneToOneField` (relasi pointer join ber-indeks otomatis). Setiap read/write query ke child memicu operasi `JOIN` implisit yang menambah overhead I/O query.
3. **Proxy Model**: Tidak membuat tabel baru, kolom baru, ataupun foreign key. Menggunakan tabel fisik yang identik dengan model target, tetapi memungkinkan modifikasi perilaku Python-level (seperti default ordering, custom Manager, method baru).

---

### Soal 1.3: Definisi dan Mekanisme `db_index=True`
Apa yang sebenarnya terjadi di level storage engine database saat Anda menambahkan argumen `db_index=True` pada sebuah field `CharField` di Django?

**Jawaban Teknis:**
Engine database (misalnya PostgreSQL) akan mengeksekusi DDL `CREATE INDEX` untuk membangun struktur pohon B-Tree (default) pada kolom bersangkutan. B-Tree menyimpan nilai kunci kolom secara berurut beserta pointer fisik (`TID`/`ctid`) ke heap tuple/halaman data. Hal ini memangkas kompleksitas pencarian dari $O(N)$ (Sequential/Full Table Scan) menjadi $O(\log N)$ (Index Scan / Index Cond). Namun, hal ini menambah biaya *write amplification* saat operasi `INSERT`, `UPDATE`, dan `DELETE` karena engine wajib memperbarui struktur index tree secara atomik.

---

### Soal 1.4: Peran `through` Model pada Relasi ManyToManyField
Mengapa best practice arsitektur sistem enterprise mewajibkan penentuan model perantara eksplisit via parameter `through` pada relasi `ManyToManyField`?

**Jawaban Teknis:**
Secara default, Django membuat tabel perantara implisit dengan hanya dua kolom foreign key. Menentukan model `through` eksplisit memungkinkan:
1. Menyimpan metadata transaksional relasi (misalnya `created_at`, `status`, `role`, `audit_actor_id`).
2. Menambahkan constraint khusus seperti `UniqueConstraint` komposit multi-kolom atau conditional index.
3. Mengontrol penamaan tabel dan auditability data historis tanpa perlu refactor skema destruktif di masa mendatang.

---

### Soal 1.5: Atomic Migration & Flag `atomic`
Apa fungsi dari atribut `atomic = True` (default) pada class `Migration` Django, dan kapan developer harus secara eksplisit mengubahnya menjadi `atomic = False`?

**Jawaban Teknis:**
Atribut `atomic = True` membungkus seluruh operasi migrasi (DDL dan data manipulation) ke dalam satu transaksi database (`BEGIN ... COMMIT`). Jika salah satu operasi gagal, seluruh skema di-rollback secara otomatis ke state sebelumnya.
Developer **wajib** mengubahnya menjadi `atomic = False` saat:
*   Mengeksekusi DDL concurrent pada PostgreSQL (seperti `CREATE INDEX CONCURRENTLY` atau `DROP INDEX CONCURRENTLY`), yang tidak diizinkan dieksekusi di dalam transaction block.
*   Menggunakan database storage engine non-transaksional DDL.
*   Melakukan migrasi data masif (*batch processing*) yang berpotensi menyebabkan *table bloat* atau *lock table timeout* jika dieksekusi dalam satu transaksi raksasa.

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 2.1: Implementasi dan Karakteristik Partial / Conditional Indexes
Bagaimana mendefinisikan partial index di Django menggunakan `models.Index` dan class `Q`? Apa keuntungan performanya dibanding index standar?

**Jawaban Teknis:**
Contoh implementasi:
```python
from django.db import models

class Order(models.Model):
    user = models.ForeignKey('User', on_delete=models.CASCADE)
    status = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=['user', 'created_at'],
                name='idx_order_user_pending',
                condition=models.Q(status='PENDING'),
            )
        ]
```
**Keuntungan Performa:**
1. **Reduksi Ukuran Index (Footprint I/O)**: Hanya mengindeks baris yang match `status='PENDING'`. Jika 95% data berstatus `COMPLETED`, ukuran file index hanya 5% dari ukuran index reguler, menjaga index tetap muat di RAM (Buffer Pool/Shared Buffers).
2. **Minimalisir Write Overhead**: Operasi `INSERT`/`UPDATE` pada data non-pending tidak akan menyentuh atau memicu penulisan ulang node pada partial index tree.

---

### Soal 2.2: Composite UniqueConstraint dengan Kondisi (Partial Unique Constraint)
Bagaimana menangani kasus *soft-delete* di mana kolom `email` harus unik untuk user yang aktif, tetapi diperbolehkan duplikat untuk user yang sudah dihapus (`is_deleted=True`)?

**Jawaban Teknis:**
Alih-alih menggunakan parameter `unique=True` pada field `email` (yang memaksakan keunikan global di seluruh baris tabel), gunakan `models.UniqueConstraint` dengan filter `condition`:
```python
class AccountUser(models.Model):
    email = models.EmailField()
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['email'],
                condition=models.Q(is_deleted=False),
                name='unique_active_user_email'
            )
        ]
```
Engine PostgreSQL akan menghasilkan DDL: `CREATE UNIQUE INDEX unique_active_user_email ON table_name (email) WHERE is_deleted = false;`.

---

### Soal 2.3: CheckConstraint vs Validasi Model `clean()`
Jelaskan perbedaan arsitektural mendalam antara validasi yang diletakkan pada method `clean()` model Django versus `models.CheckConstraint`.

**Jawaban Teknis:**
*   `Model.clean()` adalah validasi tingkat aplikasi Python. Method ini hanya berjalan jika dipanggil eksplisit oleh Django Form, Serializer, atau manual calling (`full_clean()`). Method ini **dilewati total** oleh operasi bulk ORM seperti `bulk_create()`, `bulk_update()`, `update()`, atau raw SQL statement.
*   `models.CheckConstraint` diterjemahkan langsung ke constraint DDL database engine (`ALTER TABLE ADD CONSTRAINT CHECK (...)`). Validasi ini dijamin 100% konsisten oleh kernel database ACID terlepas dari jalur input data (baik via ORM, direct SQL connection, background worker celery, maupun migrasi skema eksternal).

---

### Soal 2.4: Mengapa `GenericForeignKey` (ContentType) Sering Dianggap Anti-Pattern Performa?
Sebutkan 3 problem fundamental arsitektur database saat menggunakan framework `django.contrib.contenttypes` (`GenericForeignKey`) pada tabel dengan volume data jutaan baris.

**Jawaban Teknis:**
1. **Absennya Referential Integrity (Foreign Key Constraints Fisik)**: Engine database tidak dapat membuat foreign key constraint ke tabel target karena target tabel ditentukan secara dinamis via kolom integer `content_type_id`. Baris parent bisa dihapus tanpa memicu cascade/protect, memicu inkonsistensi data.
2. **Inefisiensi Query Join (Impedance Mismatch)**: ORM tidak bisa melakukan direct SQL `INNER JOIN` satu langkah. Pengambilan relasi generik sering berujung pada eksekusi multi-query terpisah atau kompleksitas scanning skema heterogen.
3. **Komplikasi Partial Indexing dan Sharding**: Sulit mengoptimalkan index gabungan `(content_type_id, object_id)` untuk selektivitas query analitik spesifik, serta mematikan kemampuan partitioning tabel berbasis relasi relasional native.

---

### Soal 2.5: Zero-Downtime Safe Column Addition
Mengapa menambahkan kolom baru bertipe `NOT NULL` tanpa `DEFAULT` atau dengan `default` yang dihitung secara dinamis (misalnya fungsi Python) dapat menyebabkan downtime/lockup pada database produksi berskala besar? Bagaimana strategi mitigasinya?

**Jawaban Teknis:**
*   **Penyebab Masalah**: Pada versi database tertentu (atau saat default memerlukan komputasi runtime), penambahan kolom `NOT NULL` memaksa database melakukan *exclusive table lock* (`ACCESS EXCLUSIVE`) dan menulis ulang seluruh tuple tabel pada disk (*full table rewrite*), mengunci seluruh antrean query read/write lain hingga timeout.
*   **Mitigasi Tiga Langkah (Expand-Contract Pattern)**:
    1. *Langkah 1*: Tambahkan kolom baru sebagai `nullable` (`null=True, blank=True`). Operasi metadata DDL ini instan (tanpa write lock panjang).
    2. *Langkah 2*: Jalankan background worker/script batch untuk mempopulasi data default pada kolom tersebut secara bertahap (per 5.000 batch).
    3. *Langkah 3*: Tambahkan constraint `NOT NULL` melalui migrasi berikutnya setelah 100% data terisi (di Postgres: tambahkan check constraint `NOT VALID`, lalu `VALIDATE CONSTRAINT` untuk meminimalisir lock window).

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Skenario)

### Skenario 3.1: Double Booking Transaksi Kamar Hotel (Race Condition & Exclusion Constraint)
*   **Konteks**: Sistem pemesanan hotel sering menerima reservasi kamar yang sama pada rentang tanggal yang tumpang tindih ketika dua user checkout di detik yang sama. Validasi Python `if not Booking.objects.filter(...).exists():` gagal mencegah data ganda akibat konkurensi request.
*   **Pertanyaan**: Bagaimana mendesain model Django dengan PostgreSQL `ExclusionConstraint` dan ekstensi `btree_gist` untuk memblokir reservasi yang overlap secara mutlak pada level kernel storage engine?
*   **Solusi Desain**:

```python
from django.db import models
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeOperators
from django.contrib.postgres.operations import BtreeGistExtension
from django.db.migrations import Migration

# Migrasi awal wajib mengaktifkan ekstensi PostgreSQL btree_gist:
# operations = [BtreeGistExtension()]

class HotelRoom(models.Model):
    room_number = models.CharField(max_length=16, unique=True)
    is_active = models.BooleanField(default=True)

class RoomReservation(models.Model):
    room = models.ForeignKey(HotelRoom, on_delete=models.PROTECT, related_name='reservations')
    guest_name = models.CharField(max_length=128)
    booking_period = DateRangeField(help_text="Rentang tanggal [check-in, check-out)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            ExclusionConstraint(
                name='exclude_overlapping_room_bookings',
                expressions=[
                    ('room', RangeOperators.EQUAL),
                    ('booking_period', RangeOperators.OVERLAPS),
                ],
                condition=models.Q(room__is_active=True),
            )
        ]
```
*Analisis Engine*: Saat request konkuren mencoba melakukan commit transaksi dengan rentang tanggal bertabrakan pada `room_id` yang sama, index GiST mendeteksi violasi overlap operator `&&` dan melempar database exception, menjamin integritas reservasi tanpa race condition.

---

### Skenario 3.2: Arsitektur Multi-Tenancy Isolasi Data E-Commerce
*   **Konteks**: Platform SaaS E-commerce melayani ratusan tenant merchant dalam satu database terpusat (*shared database, shared schema*). Kebocoran data antar-tenant akibat developer lupa menyertakan filter `.filter(merchant_id=current_merchant)` pada query ORM adalah insiden keamanan kritikal kategori P0.
*   **Pertanyaan**: Rancang strategi modeling data menggunakan custom model inheritance, custom manager/queryset, dan audit field yang menjamin isolasi data tenant secara ketat.
*   **Solusi Desain**:

```python
from django.db import models
from django.core.exceptions import PermissionDenied

class Tenant(models.Model):
    name = models.CharField(max_length=128)
    subdomain = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)

class TenantQuerySet(models.QuerySet):
    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)

class TenantManager(models.Manager):
    def get_queryset(self):
        # Basis Queryset reguler
        return TenantQuerySet(self.model, using=self._db)

    def for_current_tenant(self, tenant):
        if not tenant:
            raise PermissionDenied("Akses data ditolak: Tenant context tidak ditemukan.")
        return self.get_queryset().for_tenant(tenant)

class TenantScopedModel(models.Model):
    """Abstract Base Class wajib untuk seluruh entitas milik Tenant"""
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_records",
        db_index=True
    )

    objects = TenantManager()

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['tenant', 'id']),
        ]

class ProductCatalog(TenantScopedModel):
    sku = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta(TenantScopedModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'sku'],
                name='unique_sku_per_tenant'
            )
        ]
```

---

### Skenario 3.3: Degradasi Performa Query JSONB pada Data Audit Log Finansial
*   **Konteks**: Tabel `AuditLog` menyimpan mutasi transaksi finansial dengan volume 25 juta baris. Field `payload = models.JSONField()` menampung data dinamis seperti `{"user_id": 402, "ip": "10.0.0.1", "metadata": {"auth_source": "mfa_app"}}`. Pencarian query `AuditLog.objects.filter(payload__metadata__auth_source='mfa_app')` membutuhkan waktu 18 detik (*full sequential scan*).
*   **Pertanyaan**: Bagaimana merestrukturisasi model dan index Django PostgreSQL untuk memangkas latency query tersebut menjadi < 15 milidetik?
*   **Solusi Desain**:

```python
from django.db import models
from django.contrib.postgres.indexes import GinIndex

class FinancialAuditLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    event_type = models.CharField(max_length=64, db_index=True)
    payload = models.JSONField(default=dict)

    class Meta:
        indexes = [
            # 1. GIN index dengan operator jsonb_path_ops untuk efisiensi containment query
            GinIndex(
                fields=['payload'],
                name='idx_gin_audit_payload_ops',
                opclasses=['jsonb_path_ops']
            ),
            # 2. Atau B-Tree Expression Index jika query hanya berfokus pada field spesifik path
            # models.Index(
            #     models.F('payload__metadata__auth_source'),
            #     name='idx_btree_auth_source'
            # )
        ]
```
*Analisis Engine*: Operator class `jsonb_path_ops` membangun hash index tree dari setiap path-hash key/value JSONB. Ukuran indeks 60% lebih ramping dibanding default `jsonb_ops` dan mengubah full table scan menjadi GIN Bitmap Index Scan, memangkas latency ke < 10 ms pada dataset 25+ juta baris.

---

## Bagian 4: Practical Chapter Challenge (Tantangan Implementasi Nyata)

### Judul Tantangan: "Sistem Dompet Multi-Mata Uang & Buku Kas Ganda (Double-Entry Ledger Engine)"

#### Latar Belakang & Kebutuhan Bisnis:
Anda ditunjuk sebagai Arsitek Database untuk merancang backend core-banking/fintech berbasis Django ORM dengan PostgreSQL engine. Sistem tidak boleh mengizinkan saldo negatif, tidak boleh ada selisih mutasi debit dan kredit, dan dilarang keras kehilangan jejak audit saat terjadi kegagalan sistem.

#### Spesifikasi Wajib:
1. **Model `Wallet`**:
   * Memiliki `uuid` sebagai primary key.
   * `currency`: Enum code ISO (USD, IDR, EUR, dll).
   * `balance`: `DecimalField(max_digits=18, decimal_places=4)`.
   * Harus memiliki database constraint: `balance >= 0.0000` (tidak boleh minus di level database).
   * Harus memiliki composite unique constraint: `(user_id, currency)` (satu user hanya punya satu dompet per mata uang).

2. **Model `LedgerTransaction`**:
   * ID transaksi transaksi (UUID).
   * Status (`PENDING`, `POSTED`, `REJECTED`).
   * Timestamp waktu rekonsiliasi.

3. **Model `LedgerEntry` (Mutasi Debet/Kredit)**:
   * Relasi `ForeignKey` ke `LedgerTransaction` dan `Wallet`.
   * `entry_type`: `DEBIT` atau `CREDIT`.
   * `amount`: `DecimalField(max_digits=18, decimal_places=4)`. Harus strictly positive (`amount > 0`).

4. **Persyaratan Integritas Tingkat Lanjut**:
   * Implementasikan custom Django Migration untuk menambahkan trigger atau validasi database level agar total `SUM(DEBIT) == SUM(CREDIT)` pada saat status transaksi menjadi `POSTED`.
   * Seluruh operasi mutasi wajib berada dalam `transaction.atomic()` dengan mekanisme `select_for_update()` untuk mencegah *lost updates*.

#### Kode Solusi Acuan (Reference Implementation):

```python
import uuid
from decimal import Decimal
from django.db import models, transaction
from django.conf import settings
from django.core.exceptions import ValidationError

class CurrencyEnum(models.TextChoices):
    IDR = 'IDR', 'Indonesian Rupiah'
    USD = 'USD', 'US Dollar'
    SGD = 'SGD', 'Singapore Dollar'

class Wallet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='wallets')
    currency = models.CharField(max_length=3, choices=CurrencyEnum.choices)
    balance = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'currency'],
                name='unique_user_currency_wallet'
            ),
            models.CheckConstraint(
                check=models.Q(balance__gte=Decimal('0.0000')),
                name='wallet_balance_non_negative'
            )
        ]

class TransactionStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Validation'
    POSTED = 'POSTED', 'Posted / Committed'
    REJECTED = 'REJECTED', 'Rejected'

class LedgerTransaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_number = models.CharField(max_length=64, unique=True)
    status = models.CharField(
        max_length=16,
        choices=TransactionStatus.choices,
        default=TransactionStatus.PENDING
    )
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

class EntryType(models.TextChoices):
    DEBIT = 'DEBIT', 'Debit'
    CREDIT = 'CREDIT', 'Credit'

class LedgerEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(
        LedgerTransaction,
        on_delete=models.PROTECT,
        related_name='entries'
    )
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.PROTECT,
        related_name='ledger_entries'
    )
    entry_type = models.CharField(max_length=8, choices=EntryType.choices)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=Decimal('0.0000')),
                name='ledger_entry_amount_positive'
            )
        ]

# Service Layer untuk Eksekusi Atomic & Pessimistic Locking
class LedgerService:
    @staticmethod
    def execute_transfer(source_wallet_id: uuid.UUID, target_wallet_id: uuid.UUID, amount: Decimal, ref: str):
        if amount <= Decimal('0.0000'):
            raise ValidationError("Nominal transfer wajib bernilai positif.")

        with transaction.atomic():
            # Mencegah Deadlock: Urutkan penguncian baris berdasarkan ID secara konsisten
            wallet_ids = sorted([source_wallet_id, target_wallet_id])
            locked_wallets = {
                w.id: w for w in Wallet.objects.select_for_update().filter(id__in=wallet_ids)
            }

            source_wallet = locked_wallets[source_wallet_id]
            target_wallet = locked_wallets[target_wallet_id]

            if source_wallet.currency != target_wallet.currency:
                raise ValidationError("Mata uang dompet pengirim dan penerima harus sama.")

            if source_wallet.balance < amount:
                raise ValidationError("Saldo dompet tidak mencukupi.")

            # Buat Dokumen Transaksi Induk
            ledger_tx = LedgerTransaction.objects.create(
                reference_number=ref,
                description=f"Transfer {amount} {source_wallet.currency}",
                status=TransactionStatus.POSTED
            )

            # Buat Mutasi Buku Kas Ganda (Debit & Kredit Seimbang)
            LedgerEntry.objects.create(
                transaction=ledger_tx,
                wallet=source_wallet,
                entry_type=EntryType.DEBIT,
                amount=amount
            )
            LedgerEntry.objects.create(
                transaction=ledger_tx,
                wallet=target_wallet,
                entry_type=EntryType.CREDIT,
                amount=amount
            )

            # Mutasi Saldo
            source_wallet.balance -= amount
            source_wallet.save(update_fields=['balance', 'updated_at'])

            target_wallet.balance += amount
            target_wallet.save(update_fields=['balance', 'updated_at'])

            return ledger_tx
```

---

## Bagian 5: Checklist Pemahaman (Self-Assessment)

Gunakan checklist di bawah ini untuk mengukur kesiapan teknis sebelum melangkah ke Bab 3. Tandai setiap poin yang telah Anda kuasai secara mendalam:

- [ ] **Constraint Tingkat Database**: Saya memahami cara kerja dan implementasi `CheckConstraint`, `UniqueConstraint`, serta PostgreSQL `ExclusionConstraint` tanpa bergantung semata-mata pada validasi model `clean()`.
- [ ] **Strategi Indexing**: Saya memahami perbedaan use case antara B-Tree, GIN, GiST, serta mampu menerapkan Partial Index (`condition=models.Q(...)`) untuk mengoptimalkan query I/O dan footprint memory RAM.
- [ ] **Inheritance Trade-offs**: Saya menguasai trade-off performa antara Abstract Base Class, Multi-Table Inheritance (dengan hidden OneToOneField JOIN), dan Proxy Models.
- [ ] **Integritas Relasional**: Saya memahami konsekuensi dari `on_delete` (`CASCADE`, `PROTECT`, `RESTRICT`, `DO_NOTHING`) dan implikasi model perantara `through` pada Many-to-Many fields.
- [ ] **Migrasi Zero-Downtime**: Saya memahami risiko lockup DDL pada tabel produksi besar dan tahu cara menjalankan migrasi `atomic = False` untuk perintah non-blocking seperti `CREATE INDEX CONCURRENTLY`.
- [ ] **PostgreSQL JSONB Optimization**: Saya memahami perbedaan operator class `jsonb_ops` vs `jsonb_path_ops` saat mengindeks field `JSONField`.
- [ ] **Pencegahan Race Condition**: Saya dapat mengombinasikan `select_for_update()`, pessimistic locking, dan transaction atomicity untuk menjaga konsistensi data finansial/inventaris di lingkungan request multi-thread/multi-proses.
