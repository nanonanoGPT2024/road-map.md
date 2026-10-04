# BAB 05: Quiz, Challenge, & Knowledge Check
**Object-Oriented Deep Dive & Metaprogramming**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Siklus Hidup Alokasi Objek (`__new__` vs `__init__`):**
   Jelaskan secara mendalam perbedaan tanggung jawab operasional antara `__new__` dan `__init__` di level CPython runtime. Dalam skenario arsitektur apa developer *mutlak* harus meng-override `__new__` alih-alih `__init__`, dan apa konsekuensinya terhadap eksekusi `__init__` jika `__new__` tidak mengembalikan instance dari kelas yang sedang dikonstruksi?

2. **C3 Linearization Algorithm & MRO Resolution:**
   Bagaimana algoritma *C3 Linearization* bekerja dalam menyelesaikan *Method Resolution Order* (MRO) pada Multiple Inheritance hierarki intrik (seperti *diamond problem*)? Tuliskan skenario hierarki kelas yang valid secara sintaksis namun gagal dikompilasi oleh CPython runtime dengan exception `TypeError: Cannot create a consistent method resolution order (MRO)`.

3. **Protokol Resolusi Atribut (The Attribute Lookup Pipeline):**
   Uraikan urutan prioritas deterministik CPython ketika sebuah atribut diakses melalui ekspresi `instance.attribute`. Di mana posisi tepat *Data Descriptor*, *Instance Dictionary* (`__dict__`), *Non-Data Descriptor*, *Class Dictionary*, dan fallback method `__getattr__`?

4. **Karakteristik Komparatif: Class Decorators vs `__init_subclass__` vs Metaclass:**
   Bandingkan ketiga pendekatan metaprogramming ini berdasarkan waktu eksekusi (*evaluation phase*), kapabilitas intervensi namespace kelas, dan kompleksitas perawatannya. Kapan `__init_subclass__` (PEP 487) sudah mencukupi, dan batasan struktural apa yang memaksa arsitek sistem harus beralih ke pembuatan Metaclass kustom?

5. **Anatomi Memori: Optimasi `__slots__`:**
   Bagaimana deklarasi `__slots__` secara internal mengeliminasi overhead memori dari `__dict__` dan `__weakref__` pada CPython object representation (`PyObject`)? Apa implikasi struktural penggunaan `__slots__` terhadap *multiple inheritance* dan kapabilitas dinamis *monkey patching* atribut baru di runtime?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **State Leakage pada Descriptor Protocol:**
   Perhatikan potongan implementasi descriptor berikut:
   ```python
   class BrokenField:
       def __init__(self):
           self.value = None

       def __get__(self, instance, owner):
           if instance is None:
               return self
           return self.value

       def __set__(self, instance, value):
           self.value = value
   ```
   Jelaskan secara presisi mengapa implementasi di atas menyebabkan *catastrophic state leakage* di lingkungan multi-instance/multi-thread. Solusi arsitektur apa yang paling elegan: menggunakan `WeakKeyDictionary`, memanfaatkan `__set_name__` untuk mutasi internal instance `__dict__`, atau mengkombinasikannya dengan *private mangling*?

2. **Resolusi "Metaclass Conflict":**
   Diberikan dua base class yang memiliki metaclass berbeda:
   ```python
   class MetaA(type): pass
   class MetaB(type): pass
   class BaseA(metaclass=MetaA): pass
   class BaseB(metaclass=MetaB): pass

   class Derived(BaseA, BaseB): pass  # TypeError: metaclass conflict
   ```
   Jelaskan mengapa CPython melempar `TypeError: metaclass conflict`. Rancang implementasi *dynamic meta-merger class* yang secara otomatis menghitung dan memproduksi derived metaclass untuk mengeliminasi konflik hierarki tersebut tanpa modifikasi manual pada kelas basis.

3. **Namespace Interception via `__prepare__`:**
   Jelaskan peran method `@classmethod __prepare__(metacls, name, bases, **kwds)` pada metaclass. Bagaimana method ini memungkinkan framework declarative (seperti custom ORM atau serialization engine) merekam urutan deklarasi atribut secara deterministik sebelum namespace kelas dikonversi menjadi standard dictionary pada era Python pra-3.7, dan apa kegunaan utamanya di Python modern?

4. **Mekanika `super()` dan Dependency Injection pada Runtime:**
   Mengapa pemanggilan zero-argument `super()` di Python 3 bekerja secara implisit? Jelaskan variabel closure `__class__` yang di-injeksi oleh compiler ke dalam stack frame method dan apa implikasinya jika developer memanggil `super()` di dalam *list comprehension*, generator expression, atau dynamic method injection via `setattr` pada runtime?

5. **Bahaya Objek "Resurrection" melalui `__del__`:**
   Jelaskan bagaimana implementasi method `__del__` dapat menghidupkan kembali (*resurrect*) objek yang seharusnya dideallokasi oleh Cyclic Garbage Collector CPython. Mengapa penggunaan `__del__` sangat tidak disarankan pada kode enterprise modern, dan mekanisme apa (`weakref.finalize` / Context Manager) yang harus menggantikannya?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Memory Leak Tersembunyi pada Event Processing Engine
Sistem ingest event IoT memproses 50.000 payload/detik menggunakan CPython 3.11. Setiap pesan di-parsing ke dalam model kelas Python murni. Setelah 4 jam beroperasi, worker memory melesat dari 300MB ke 14GB dan memicu sistem dimatikan oleh Linux OOM Killer. Heap profiling via `tracemalloc` dan `objgraph` menunjukkan jutaan instance model tetap tersimpan di memori meskipun scope pemrosesan telah selesai. Investigasi kode menemukan:
1. Model kelas memiliki attribute callback yang menunjuk ke method instance lain, membentuk *cyclical references*.
2. Model kelas mengimplementasikan method `__del__` untuk logging debugging waktu hidup objek.
3. Model tidak mengimplementasikan `__slots__`.

* **Pertanyaan Diagnostik:**
  1. Analisis bagaimana kombinasi cyclical references dan method `__del__` melumpuhkan Cyclic Garbage Collector (terutama terkait generasi *uncollectable cycles*).
  2. Susun rencana refaktorisasi arsitektur komprehensif untuk menurunkan jejak memori secara radikal (>70%) dan menjamin deallokasi deterministik tanpa bergantung pada GC traversal.

### Skenario B: Cross-Tenant Data Contamination via Class-Level State
Platform SaaS B2B Multi-Tenant mengalami insiden keamanan kritis: Tenant B dapat membaca konfigurasi database privat milik Tenant A. Setelah audit forensik, akar masalah dilacak ke sebuah kustom *Caching Property Descriptor* yang dipasang pada service layer:
```python
class CachedTenantProperty:
    def __init__(self, fetcher):
        self.fetcher = fetcher
        self.cache = {}

    def __get__(self, instance, owner):
        if instance is None:
            return self
        if "data" not in self.cache:
            self.cache["data"] = self.fetcher(instance)
        return self.cache["data"]
```
Model `TenantService` diinstansiasi per-request di web framework async (FastAPI/Starlette):
```python
class TenantService:
    def __init__(self, tenant_id):
        self.tenant_id = tenant_id

    @CachedTenantProperty
    def db_config(self):
        return load_secure_config(self.tenant_id)
```

* **Pertanyaan Diagnostik:**
  1. Bedah secara mekanis mengapa implementasi di atas menyebabkan kontaminasi data lintas request dan lintas tenant.
  2. Implementasikan ulang decorator/descriptor tersebut agar *thread-safe*, *async-safe*, terisolasi strictly per-instance tenant, dan tidak menimbulkan memory leak saat lifecycle request instance berakhir.

### Skenario C: Dilema Arsitektur Framework: Migrasi Metaclass Kompleks ke `__init_subclass__`
Tim Core Engineering memelihara library internal Declarative RPC Protocol yang dibangun di era Python 3.5 menggunakan rantai metaclass berlapis (4 layer metaclass untuk dynamic validation, serialization hook, type-casting, dan auto-documentation). Rantai metaclass ini menimbulkan *maintenance nightmare*, sering memicu metaclass conflict saat tim integrasi mencoba menggabungkan library ini dengan Pydantic atau SQLAlchemy models, serta memperlambat waktu start-up service secara signifikan.

* **Pertanyaan Diagnostik:**
  1. Lakukan audit arsitektur: Fitur metaprogramming apa yang *secara mutlak* hanya bisa diselesaikan oleh Metaclass (tidak bisa digantikan oleh `__init_subclass__` dan Class Decorators)?
  2. Buatlah rencana migrasi bertahap (*strangler pattern*) untuk mengganti layer validasi dan auto-registration menjadi berbasis `__init_subclass__` dan Descriptor (PEP 487), sembari menjaga *backward compatibility* terhadap puluhan microservices yang mengonsumsi base class tersebut.

---

## 4. Chapter Challenge

**Tantangan Praktis: Membangun Micro-ORM Declarative Model Layer Berperforma Tinggi**

### Problem Statement
Anda ditugaskan merancang fondasi *Data Access Layer* deklaratif berbasis murni CPython modern (Python 3.10+) tanpa dependensi eksternal. Framework ini harus memvalidasi tipe data pada level runtime, mencegah mutasi tidak sah, melacak perubahan state entitas (*dirty tracking*), dan mengoptimalkan konsumsi memori secara ekstrem.

### Requirements
1. **Field Descriptors:**
   * Bangun base class `Field` yang mengimplementasikan *Data Descriptor Protocol*.
   * Gunakan `__set_name__` untuk mendeteksi nama atribut otomatis tanpa deklarasi redundan.
   * Buat turunan konkret: `StringField(min_length=1, max_length=255)`, `IntegerField(min_value=0)`, dan `BooleanField()`.
   * Validasi tipe data dan batasan wajib dieksekusi secara instan saat assignment (`__set__`). Berikan error deskriptif jika validasi gagal.
2. **Declarative Base via `__init_subclass__`:**
   * Buat base class `DeclarativeModel`.
   * Ketika kelas turunan dibuat, `__init_subclass__` harus menginspeksi seluruh atribut kelas, meregistrasikan semua instance `Field` ke dalam *immutable mapping* `_fields`, dan otomatis mengonstruksi dynamic `__init__` constructor yang menerima keyword arguments sesuai nama field.
   * Implementasikan mekanisme *Dirty Tracking*: Model harus mampu melaporkan field mana saja yang telah dimutasi nilainya sejak inisialisasi awal via method `.get_dirty_fields() -> dict[str, Any]`.
3. **Memory Optimization:**
   * Model yang diturunkan harus mengaktifkan optimasi layout memori setara `__slots__` secara otomatis atau semi-otomatis untuk menekan overhead dictionary, tanpa merusak fungsionalitas *Descriptor*.
4. **Immutability & Safety:**
   * Mencegah modifikasi atribut di luar deklarasi fields (mencegah arbitrary attribute assignment/typo pada runtime).

### Constraints
* Dilarang menggunakan external framework/library (Pydantic, attrs, SQLAlchemy, dll).
* Wajib kompatibel dengan *type hinting* standar.
* Wajib menangani edge-case inheritance: Jika `ModelB` mewarisi `ModelA`, `ModelB` harus mewarisi seluruh fields dari `ModelA` tanpa merusak metadata kelas induk.

### Expected Output
Kode harus dapat mengeksekusi skrip operasional berikut tanpa error:

```python
class User(DeclarativeModel):
    id = IntegerField(min_value=1)
    username = StringField(min_length=3, max_length=50)
    is_active = BooleanField()

# 1. Konstruksi Valid
user = User(id=1, username="enterprise_architect", is_active=True)
assert user.id == 1
assert user.username == "enterprise_architect"
assert user.get_dirty_fields() == {}

# 2. Mutasi & Dirty Tracking
user.username = "principal_engineer"
assert user.get_dirty_fields() == {"username": "principal_engineer"}

# 3. Validasi Runtime (Harus melempar TypeError / ValueError)
try:
    user.username = "ab"  # Terlalu pendek (< 3)
    assert False, "Harus gagal karena min_length=3"
except ValueError:
    pass

try:
    user.non_existent = 123  # Field tidak terdaftar
    assert False, "Harus gagal meng-assign field di luar deklarasi"
except AttributeError:
    pass
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme exact alokasi memori CPython: Hubungan antara `type.__call__`, `cls.__new__`, dan `cls.__init__`.
- [ ] Aturan C3 Linearization Algorithm dan bagaimana membedah method resolution order menggunakan `__mro__`.
- [ ] Perbedaan deterministik antara Data Descriptor (mengimplementasikan `__set__` dan/atau `__delete__`) dan Non-Data Descriptor (hanya mengimplementasikan `__get__`), serta dampaknya terhadap intercept `__dict__`.
- [ ] Peran method lifecycle metaprogramming Python 3.6+: `__set_name__`, `__init_subclass__`, dan `__prepare__`.
- [ ] Bagaimana implementasi `__slots__` memengaruhi `PyMemberDef` di C-level dan mengeliminasi dictionary instance.
- [ ] Konsekuensi pengabaian lifecycle GC saat menggunakan `__del__` bersamaan dengan circular references.

### Saya tidak perlu menghafal:
- [ ] Rumus matematika formal paper C3 Linearization (cukup pahami heuristik *monotonicity* dan *local precedence order*).
- [ ] C-API structure layout internal `PyTypeObject` secara byte-by-byte (cukup pahami abstraksi level Python).
- [ ] Kode implementasi library lama yang mengemulasi `__set_name__` pra-Python 3.6.

### Saya harus bisa melakukan:
- [ ] Membangun dynamic type validation system menggunakan Descriptor Pattern tanpa menyebabkan cross-instance state leakage.
- [ ] Melakukan debugging dan tracing `metaclass conflict` error pada enterprise legacy codebase dan menyelesaikannya secara elegan.
- [ ] Mengganti metaclass kompleks yang tidak efisien dengan kombinasi `__init_subclass__`, descriptor, dan dynamic class factory.
- [ ] Menggunakan heap profiler (`objgraph`, `tracemalloc`) untuk melacak memory leak akibat circular references yang melibatkan descriptor dan dynamic class tracking.
- [ ] Merancang arsitektur model domain data-layer enterprise yang efisien memori (`__slots__`-compatible) dengan dirty-checking dan invariant validation engine.