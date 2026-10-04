# Kurikulum Rekayasa Perangkat Lunak: Python Tingkat Lanjut
## Bab 10: Metaprogramming, Dynamic Internals, dan Desain Framework
### Modul 01: The Descriptor Protocol, Attribute Lookup Mechanics, dan Metaclass Runtime

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, *software engineer* mampu:
*   Menganalisis dan merekonstruksi urutan prioritas resolusi atribut CPython (*Attribute Lookup Precedence Chain*) dari *slot wrappers* hingga fallback `__getattr__`.
*   Mengimplementasikan protokol descriptor lengkap (`__get__`, `__set__`, `__delete__`, dan `__set_name__`) sesuai standar PEP 487 untuk mengisolasi logika validasi, serialisasi, dan state management.
*   Membangun declarative framework engine (setara arsitektur internal Pydantic/SQLAlchemy) yang mengombinasikan *Data Descriptors* dan *Metaclasses* tanpa mengorbankan performa *attribute access*.
*   Mendiagnosis dan memperbaiki *memory leak* serta *race condition* yang disebabkan oleh penyimpanan state instans yang salah pada *descriptor instance*.

---

### 2. Prerequisite
*   Pemahaman mendalam tentang OOP Python: *Method Resolution Order* (C3 Linearization) dan Dunder Methods (`__init__`, `__new__`, `__repr__`).
*   Penguasaan *First-Class Functions*, Closures, dan Custom Decorators dengan parameter.
*   Pemahaman dasar arsitektur CPython: Struktur `PyObject`, alokasi memori heap, dan referensi dictionary (`__dict__`).

---

### 3. Concept
Pada CPython, operasi pengaksesan atribut `obj.attr` bukan sekadar pembacaan hash map sederhana dari `obj.__dict__['attr']`. Akses tersebut diatur secara internal oleh fungsi level-C `PyObject_GenericGetAttr` yang mengimplementasikan protokol delegasi bernama **Descriptor Protocol**.

Descriptor adalah objek Python yang mengikat perilaku akses atribut melalui implementasi minimal satu dari metode protokol:
*   `__get__(self, instance, owner=None) -> Any`
*   `__set__(self, instance, value) -> None`
*   `__delete__(self, instance) -> None`
*   `__set_name__(self, owner, name) -> None` (PEP 487)

CPython membedakan descriptor ke dalam dua kelas fundamental:
1.  **Data Descriptors**: Objek yang mendefinisikan `__set__` dan/atau `__delete__` (biasanya bersama dengan `__get__`). Data descriptor memiliki preseden lebih tinggi daripada `__dict__` instans itu sendiri.
2.  **Non-Data Descriptors**: Objek yang hanya mendefinisikan `__get__` (contoh klasik: reguler functions/methods, `@classmethod`, `@staticmethod`). Jika sebuah nama ada di `__dict__` instans, instans tersebut menimpa (*shadows*) non-data descriptor.

Metaclass (`type`) berada satu tingkat di atas class, bertindak sebagai cetak biru dari class itu sendiri. Ketika Python mengeksekusi blok `class MyClass:`, Python mengumpulkan namespace ke dalam mapping, kemudian memanggil `Metaclass.__new__(mcs, name, bases, namespace)` dan `Metaclass.__init__(cls, name, bases, namespace)`. Ini menyediakan titik intersepsi kompilasi runtime untuk memanipulasi descriptor sebelum instans dibuat.

---

### 4. Why
*   **Enkapsulasi Reusable Logic**: Menghindari redundansi `@property`. Jika suatu sistem memiliki 50 field yang membutuhkan validasi boundary integer, menggunakan property biasa menghasilkan duplikasi kode yang masif. Descriptor mengabstraksi properti menjadi komponen modular yang *reusable*.
*   **Pondasi Framework Modern**: Semua framework kritis Python—Django ORM (`models.Field`), SQLAlchemy (`Column`), Pydantic (`FieldInfo`), dan Celery Tasks—dibangun di atas Descriptor Protocol untuk memetakan deklarasi class menjadi aksi runtime kompleks (database mapping, validation engine, RPC serialization).
*   **Optimasi Memori dan Performa**: Memungkinkan implementasi *lazy evaluation* (deferred computational cost), caching terdistribusi, dan sinkronisasi thread yang transparan bagi pemanggil API.

---

### 5. What
Komponen inti arsitektur descriptor dan metaprogramming:
*   **Descriptor Instance**: Instans dari kelas descriptor yang dideklarasikan pada *class level* dari kelas target (*owner class*), bukan di dalam `__init__`.
*   **Owner Class**: Kelas yang menampung descriptor instance sebagai atribut level kelasnya.
*   **Client Instance**: Instans konkret dari *owner class* tempat data unik per objek disimpan.
*   **`__set_name__` Hook**: Mekanisme introspeksi otomatis yang dipanggil saat *owner class* diinisialisasi, mengeliminasi kebutuhan manual passing nama atribut ke konstruktor descriptor.
*   **`__getattribute__` vs `__getattr__`**: `__getattribute__` adalah gerbang mutlak untuk setiap akses atribut tanpa syarat. `__getattr__` adalah fallback absolut yang hanya dipanggil jika `__getattribute__` memicu `AttributeError`.

---

### 6. How
Alur Resolusi Algoritmik Evaluasi Akses `instance.attr`:

```
                 +---------------------------+
                 |    Mulai: instance.attr   |
                 +-------------+-------------+
                               |
                               v
            +------------------------------------+
            | Periksa type(instance).__mro__     |
            | Apakah 'attr' ditemukan di Class?  |
            +------------------+-----------------+
                               |
                +--------------+--------------+
                | Ya                          | Tidak
                v                             v
     +---------------------+        +--------------------+
     | Apakah 'attr' Data  |        | Periksa Dictionary |
     |    Descriptor?      |        |  instance.__dict__ |
     +----------+----------+        +---------+----------+
                |                             |
         +------+------+               +------+------+
         | Ya          | Tidak         | Ada         | Tidak
         v             v               v             v
  +--------------+  +--------------+  +-----------+  +--------------------+
  | Panggil:     |  | Periksa      |  | Ambil     |  | Periksa Class MRO  |
  | desc.__get__|  | instance.    |  | nilai dari|  | Non-Data Descriptor|
  |              |  | __dict__     |  | __dict__  |  | / Normal Attribute |
  +--------------+  +-------+------+  +-----------+  +---------+----------+
                            |                                  |
                     +------+------+                    +------+------+
                     | Ada         | Tidak              | Ada         | Tidak
                     v             v                    v             v
              +-----------+  +--------------------+  +-----------+  +-------------+
              | Ambil     |  | Periksa Non-Data   |  | Panggil   |  | Panggil     |
              | nilai dari|  | Descriptor di MRO  |  | desc.     |  | __getattr__ |
              | __dict__  |  | (e.g. Method)      |  | __get__   |  | jika ada,   |
              +-----------+  +---------+----------+  +-----------+  | else raise  |
                                       |                            | AttribError |
                                +------+------+                     +-------------+
                                | Ada         | Tidak
                                v             v
                         +-----------+  +-------------+
                         | Panggil   |  | Panggil     |
                         | desc.     |  | __getattr__ |
                         | __get__   |  +-------------+
                         +-----------+
```

1. Jalankan `type(instance).__mro__` untuk mencari simbol atribut pada level class.
2. Jika ditemukan dan merupakan **Data Descriptor** (memiliki `__set__` atau `__delete__`), evaluasi method `__get__` descriptor tersebut. Hasilnya langsung dikembalikan.
3. Jika bukan data descriptor, cek `instance.__dict__`. Jika atribut ditemukan di level instans, kembalikan nilai tersebut.
4. Jika tidak ada di `instance.__dict__`, cek kembali hasil pencarian class MRO:
   * Jika merupakan **Non-Data Descriptor**, evaluasi `__get__`.
   * Jika merupakan atribut kelas biasa, kembalikan nilai objek tersebut.
5. Jika langkah 1-4 gagal menemukan atribut, delegasikan eksekusi ke method fallback `__getattr__(self, name)`.
6. Jika `__getattr__` tidak didefinisikan atau memicu `AttributeError`, hentikan eksekusi dan lemparkan exception `AttributeError`.

---

### 7. Analogy
Bayangkan proses pengurusan berkas di kantor imigrasi:
*   **Data Descriptor (Petugas Imigrasi Resmi)**: Memiliki hak mutlak (`__set__` dan `__get__`). Meskipun Anda membawa paspor pribadi Anda sendiri di saku (`instance.__dict__`), Anda tidak bisa melewatinya secara langsung; Anda wajib mematuhi protokol validasi yang ditentukan petugas imigrasi.
*   **Instance Dictionary (Saku Pribadi Anda)**: Tempat penyimpanan barang bawaan Anda sendiri. Jika tidak ada petugas imigrasi yang secara aktif menahan hak akses Anda, Anda langsung mengambil barang dari saku Anda.
*   **Non-Data Descriptor (Brosur Panduan di Meja Informasi)**: Memberikan informasi standar (`__get__` saja), tetapi jika Anda memiliki catatan panduan pribadi Anda sendiri di dalam saku (`instance.__dict__`), Anda akan menggunakan catatan pribadi Anda ketimbang brosur umum tersebut.
*   **Fallback `__getattr__` (Meja Pengaduan Barang Hilang)**: Hanya didatangi jika barang sama sekali tidak ada pada pemeriksaan petugas, tidak ada di saku Anda, dan tidak ada di brosur meja informasi.

---

### 8. Diagram
Diagram interaksi pemanggilan komponen CPython:

```
+-----------------------------------------------------------------------------------+
| USER SPACE: result = user_entity.email                                            |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| CPYTHON INTERNAL: PyObject_GenericGetAttr                                         |
|                                                                                   |
|  1. cls = user_entity.__class__                                                   |
|  2. desc = lookup_mro(cls, "email")                                               |
|                                                                                   |
|  [Is desc a Data Descriptor?]                                                     |
|         |                                                                         |
|         +--- YES ---> [Execute: desc.__get__(user_entity, cls)] --------> Return  |
|         |                                                                         |
|         v NO                                                                      |
|  [Is "email" in user_entity.__dict__?]                                            |
|         |                                                                         |
|         +--- YES ---> [Read directly from dictionary] ------------------> Return  |
|         |                                                                         |
|         v NO                                                                      |
|  [Is desc a Non-Data Descriptor?]                                                 |
|         |                                                                         |
|         +--- YES ---> [Execute: desc.__get__(user_entity, cls)] --------> Return  |
|         |                                                                         |
|         v NO                                                                      |
|  [Is "email" in cls.__dict__?]                                                    |
|         |                                                                         |
|         +--- YES ---> [Return cls.__dict__["email"]] -------------------> Return  |
|         |                                                                         |
|         v NO                                                                      |
|  [Call user_entity.__getattr__("email")]                                          |
|         |                                                                         |
|         +--- DEFINED -----> [Execute fallback logic] -------------------> Return  |
|         +--- NOT DEFINED -> [Raise AttributeError] ---------------------> Crash   |
+-----------------------------------------------------------------------------------+
```

---

### 9. Simple Example
Implementasi data descriptor dasar yang mengunci tipe data integer murni:

```python
from typing import Any

class StrictlyTypedInteger:
    def __init__(self, default: int = 0) -> None:
        self._default = default
        self.storage_name: str = ""

    def __set_name__(self, owner: type, name: str) -> None:
        # Dipanggil otomatis pada class creation (PEP 487)
        self.storage_name = f"_field_{name}"

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            # Akses via Class level: MyClass.field -> kembalikan descriptor itu sendiri
            return self
        return getattr(instance, self.storage_name, self._default)

    def __set__(self, instance: Any, value: Any) -> None:
        if not isinstance(value, int):
            raise TypeError(
                f"Field '{self.storage_name}' harus bernilai int, "
                f"diterima: {type(value).__name__}"
            )
        # Menulis langsung ke instance namespace dengan dynamic storage_name
        setattr(instance, self.storage_name, value)


class InventoryItem:
    # Registrasi descriptor pada level Class
    stock = StrictlyTypedInteger(default=0)
    reorder_threshold = StrictlyTypedInteger(default=10)

    def __init__(self, name: str, stock: int, threshold: int) -> None:
        self.name = name
        self.stock = stock                      # Memanggil StrictlyTypedInteger.__set__
        self.reorder_threshold = threshold      # Memanggil StrictlyTypedInteger.__set__


item = InventoryItem("Database Server", 50, 5)
print(f"Stock: {item.stock}")  # Mengakses via StrictlyTypedInteger.__get__ -> 50

try:
    item.stock = "InvalidStock"  # Memicu TypeError secara instan
except TypeError as exc:
    print(f"Intercepted: {exc}")
```

---

### 10. Practical Example
Engine validasi skema deklaratif produksi yang mendukung *dirty-state tracking*, *type enforcement*, dan komparasi state mutasi:

```python
from __future__ import annotations
from typing import Any, Dict, Type, get_type_hints


class Field:
    """Production Data Descriptor for Model Attributes."""
    def __init__(self, default: Any = None, nullable: bool = False) -> None:
        self.default = default
        self.nullable = nullable
        self.field_name: str = ""
        self.expected_type: Type[Any] | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        self.field_name = name

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        
        # Ekstraksi dari internal state instance dictionary
        return instance._field_values.get(self.field_name, self.default)

    def __set__(self, instance: Any, value: Any) -> None:
        if instance is None:
            raise AttributeError("Akses mutasi tidak valid via class level.")

        if value is None:
            if not self.nullable:
                raise ValueError(f"Field '{self.field_name}' tidak boleh bernilai None.")
        elif self.expected_type and not isinstance(value, self.expected_type):
            raise TypeError(
                f"Field '{self.field_name}' mengharapkan tipe data {self.expected_type.__name__}, "
                f"tetapi menerima tipe {type(value).__name__}."
            )

        # Dirty checking engine
        current_value = instance._field_values.get(self.field_name)
        if current_value != value:
            instance._is_dirty = True
            instance._dirty_fields.add(self.field_name)

        instance._field_values[self.field_name] = value

    def __delete__(self, instance: Any) -> None:
        if self.field_name in instance._field_values:
            del instance._field_values[self.field_name]
            instance._is_dirty = True
            instance._dirty_fields.add(self.field_name)


class ModelMeta(type):
    """Metaclass untuk mengikat type annotations ke Field Descriptors."""
    def __new__(mcs, name: str, bases: tuple[type, ...], namespace: dict[str, Any]) -> ModelMeta:
        cls = super().__new__(mcs, name, bases, namespace)
        
        # Ekstraksi type hints runtime
        hints = get_type_hints(cls) if "__annotations__" in namespace else {}
        
        # Scan dan konfigurasi setiap descriptor pada level class
        for attr_name, attr_val in namespace.items():
            if isinstance(attr_val, Field):
                if attr_name in hints:
                    attr_val.expected_type = hints[attr_name]

        return cls


class EntityModel(metaclass=ModelMeta):
    def __init__(self, **kwargs: Any) -> None:
        # Inisialisasi isolated private namespaces
        self.__dict__["_field_values"] = {}
        self.__dict__["_dirty_fields"] = set()
        self.__dict__["_is_dirty"] = False

        for key, value in kwargs.items():
            if hasattr(self.__class__, key):
                setattr(self, key, value)
            else:
                raise AttributeError(f"Atribut '{key}' tidak terdefinisi pada schema model {self.__class__.__name__}")

    @property
    def is_dirty(self) -> bool:
        return self._is_dirty

    @property
    def modified_fields(self) -> set[str]:
        return set(self._dirty_fields)

    def mark_clean(self) -> None:
        self._dirty_fields.clear()
        self._is_dirty = False


# Declarative Client Domain Schema
class UserEntity(EntityModel):
    id: int = Field()
    username: str = Field()
    email: str = Field()
    is_active: bool = Field(default=True)


if __name__ == "__main__":
    user = UserEntity(id=101, username="alex_dev", email="alex@company.internal")
    print(f"Instansiasi User: {user.username}, Active: {user.is_active}")
    print(f"Is Dirty State: {user.is_dirty}")  # False (setelah init)
    user.mark_clean()

    # Mutasi via Descriptors
    user.email = "alex_updated@company.internal"
    print(f"Is Dirty Pasca Mutasi: {user.is_dirty}")           # True
    print(f"Fields yang bermutasi: {user.modified_fields}")     # {'email'}

    try:
        user.id = "bukan_integer"  # Runtime Type Validation Interception
    except TypeError as e:
        print(f"Validation Guard Berhasil: {e}")
```

---

### 11. Real World Example
#### Arsitektur Deserializer dan Engine Mapping: Django ORM & SQLAlchemy
Di framework skala enterprise seperti SQLAlchemy atau Django ORM, ketika seorang software architect mendeklarasikan:

```python
class PaymentTransaction(Model):
    transaction_id = UUIDField(primary_key=True)
    amount = DecimalField(max_digits=12, decimal_places=2)
```

Pada level sistem arsitektur, apa yang terjadi di balik layar adalah:
1.  **Metaclass Collection**: Metaclass mengiterasi seluruh atribut kelas saat definisi modul dimuat ke memori CPython. Objek `UUIDField` dan `DecimalField` diidentifikasi sebagai data descriptors.
2.  **Delayed Query Evaluation**: Ketika developer mengeksekusi `PaymentTransaction.amount`, descriptor mendeteksi pemanggilan melalui class-level (`instance=None`) dan mengembalikan objek `BinaryExpression` (SQL Abstract Syntax Tree) untuk merangkai string `WHERE payment_transactions.amount > 100`.
3.  **Hydration Engine**: Ketika database record ditarik via network socket, ORM membuat instans model kosong tanpa memanggil `__init__` standard (menggunakan `Model.__new__`), kemudian menempatkan raw tuple array ke internal array `_field_values`.
4.  **On-Demand Type Casting**: Akses `transaction.amount` via descriptor mengonversi raw string PostgreSQL (`"100.50"`) menjadi objek Python murni `decimal.Decimal('100.50')` secara lazy, mencegah computational overhead yang tidak diperlukan jika atribut tersebut tidak pernah disentuh dalam execution context tertentu.

---

### 12. Trade-offs

| Aspek | Data Descriptors & Metaclasses | Standard OOP & `@property` Pattern | Dictionary DTOs (`dict` / `TypedDict`) |
| :--- | :--- | :--- | :--- |
| **Advantages** | Arsitektur DRY absolut; validasi dan reaktivitas decoupled dari kelas; declarative APIs. | Sederhana, native, mudah dipahami developer level junior tanpa kurva belajar internal. | Zero lookup overhead; serialisasi JSON sangat cepat tanpa transformasi layer. |
| **Disadvantages** | *Debugging complexity* meningkat; stack traces melewati protokol internal CPython. | Boilerplate repetitif jika logika validasi digunakan di lusinan model. | Tidak ada runtime schema enforcement; rentan silent bug type mutation. |
| **Complexity** | **Tinggi (O(1)** algorithmic, tetapi kognitif tinggi). | **Rendah**. | **Sangat Rendah**. |
| **Performance** | Terdapat sedikit overhead pada `PyObject_GenericGetAttr` dibanding raw `dict` access. | Identik dengan Descriptor (karena `@property` adalah Data Descriptor di CPython). | Performa tercepat (Direct C Hash Table Lookup). |
| **Cost** | Biaya maintenance kognitif tim tinggi; risiko arsitektur jika terjadi bug memory leak. | Biaya waktu penulisan kode repetitif (*boilerplate code burden*). | Biaya tinggi pada *data integrity failure* di runtime production. |

---

### 13. When To Use
*   Ketika membangun reusable enterprise layer seperti core SDK libraries, internal domain validation framework, atau custom Database ORM/ODM mapper.
*   Ketika mengimplementasikan *Lazy Evaluation* atau *Deferred Loading* untuk properti yang memakan resource I/O atau memori masif (misal: parsing connection socket, cache warming).
*   Ketika membutuhkan audit trail, change tracking (*dirty attributes tracking*), atau *side-effect reactivity* seragam di seluruh layer Domain Models tanpa repetisi kode.

---

### 14. When NOT To Use
*   Aplikasi scripting kasual atau *micro-service utility pipeline* sederhana. Penggunaan descriptor dan metaclass adalah bentuk *over-engineering* untuk kebutuhan operasional standar.
*   Jika sebuah validasi hanya berlaku spesifik untuk satu dan hanya satu atribut dalam seluruh sistem; gunakan decorator `@property` standar.
*   Pada *critical computational path* algoritma numerik intensif (e.g., tight-loop computational rendering) di mana setiap nanodetik pemanggilan fungsi dihindari (prioritaskan penggunaan `__slots__` atau raw array Cython/C-extensions).

---

### 15. Common Mistakes
#### 1. Menyimpan State Per-Instans di Dalam Objek Descriptor
Kesalahan paling fatal yang menyebabkan data leak antar HTTP session:

```python
# CODE BROKEN (Rentan State Collision Bug)
class BrokenField:
    def __init__(self):
        self.val = None  # State disimpan di level descriptor instance!

    def __get__(self, instance, owner):
        return self.val

    def __set__(self, instance, value):
        self.val = value  # MUTASI GLOBAL UNTUK SEMUA INSTANCE!

class Account:
    balance = BrokenField()

acc1 = Account()
acc2 = Account()
acc1.balance = 500
print(acc2.balance)  # Output: 500 (CRITICAL BUG: State bocor antar-instans!)
```

#### 2. Lupa Menangani Pemanggilan Class-Level pada `__get__`
Jika `instance` adalah `None`, descriptor harus mengembalikan dirinya sendiri (`self`), bukan melempar crash `AttributeError` karena mencoba mengakses `instance.__dict__`.

```python
# Penanganan yang benar
def __get__(self, instance, owner=None):
    if instance is None:
        return self
    return instance.__dict__.get(self.name)
```

#### 3. Rekursi Tanpa Batas pada `__getattribute__`
Menggunakan `self.attr` di dalam `__getattribute__` akan memanggil kembali `__getattribute__`, menyebabkan `RecursionError`. Selalu delegasikan ke `super().__getattribute__(name)`.

---

### 16. Best Practices (Production Checklist)
*   [ ] **Gunakan PEP 487 `__set_name__`**: Jangan meminta developer menuliskan nama variabel secara manual di dalam argumen instansiasi descriptor.
*   [ ] **Gunakan Isolated Internal Storage**: Simpan state instans di dalam `instance.__dict__` menggunakan nama privat (e.g., `_field_{name}`) atau dictionary tersentralisasi terisolasi.
*   [ ] **Amankan Thread-Safety saat Mutasi**: Jika state disimpan pada container terpusat, pastikan tidak ada race condition saat konkurensi multi-threading.
*   [ ] **Dukung `__slots__`**: Jika owner class mendefinisikan `__slots__`, pastikan descriptor membaca dan menulis ke private slot name yang kompatibel, bukan berasumsi `instance.__dict__` selalu ada.
*   [ ] **Return Self di Class Level**: Selalu sediakan cabang logika `if instance is None: return self` di awal method `__get__`.

---

### 17. Troubleshooting
*   **Gejala**: Mengubah nilai atribut pada `instance_a` mengakibatkan nilai berubah pada `instance_b`.
    *   *Root Cause*: State atribut disimpan sebagai atribut instans descriptor (`self.value = val`).
    *   *Solusi*: Pindahkan penyimpanan nilai ke `instance.__dict__[self.storage_name] = val`.
*   **Gejala**: `AttributeError: 'Field' object has no attribute 'x'` saat mengakses via class model langsung.
    *   *Root Cause*: Method `__get__` mencoba mendereferensikan atribut dari `instance` yang bernilai `None`.
    *   *Solusi*: Evaluasi guard clause `if instance is None: return self`.
*   **Gejala**: `RecursionError: maximum recursion depth exceeded while calling a Python object`.
    *   *Root Cause*: Implementasi custom `__getattribute__` atau `__setattr__` memanggil kembali dirinya sendiri via `self.<name>`.
    *   *Solusi*: Bypass via method base class: `super().__getattribute__(name)` atau `super().__setattr__(name, value)`.

---

### 18. Exercise
Implementasikan sebuah **`TTLMemoizedProperty`** descriptor:
1.  Descriptor ini berperilaku sebagai non-data descriptor atau caching property.
2.  Menerima parameter `ttl_seconds: float`.
3.  Ketika method yang didekorasi dipanggil untuk pertama kali, simpan hasilnya dan catat timestamp eksekusinya.
4.  Panggilan berikutnya dalam rentang jendela waktu TTL harus mengembalikan data cache tanpa mengeksekusi kembali method aslinya.
5.  Jika rentang waktu TTL terlampaui (*expired*), eksekusi ulang method, perbarui timestamp, dan kembalikan nilai baru.

---

### 19. Challenge
Bangun sebuah micro-framework ORM bernama **`MicroSchemaEngine`** dengan spesifikasi arsitektur:
1.  **Metaclass `SchemaMeta`**:
    *   Secara otomatis mengabstraksi semua class attributes turunan `BaseField` menjadi schema registry internal.
    *   Menyediakan dynamic immutability enforcement: Jika class didefinisikan dengan parameter `frozen=True` (contoh: `class User(Model, frozen=True):`), cegah segala bentuk mutasi field setelah `__init__`.
2.  **Descriptors**:
    *   Buat `StringField(min_len: int, max_len: int)` dan `IntegerField(positive_only: bool)`.
    *   Implementasikan deteksi siklus referensi memori menggunakan `weakref` jika descriptor mengikat cache tracking instance.
3.  **Metode Serialization**:
    *   Implementasikan method `.to_json()` pada base class `Model` yang mengekstraksi nilai riil dari seluruh descriptor tanpa memicu side effects atau query evaluation ulang.
    *   Pastikan seluruh test edge-case (type violation, length violation, immutability bypass attempt) ditangani dengan eksepsi custom domain yang presisi.

---

### 20. Summary
*   Akses atribut pada CPython diorkestrasi oleh **Descriptor Protocol** yang dievaluasi di level-C via `PyObject_GenericGetAttr`.
*   **Data Descriptors** mendefinisikan `__set__` atau `__delete__`, memiliki hak preseden mutlak melampaui `__dict__` instans.
*   **Non-Data Descriptors** hanya mendefinisikan `__get__`, dan perilakunya dapat ditimpa (*shadowed*) oleh atribut instans yang memiliki key serupa pada `__dict__`.
*   PEP 487 memperkenalkan **`__set_name__`**, menyederhanakan inisialisasi descriptor tanpa memerlukan intervensi metaclass kompleks hanya untuk membaca nama variabel deklaratif.
*   Penggabungan terukur antara **Metaclass** dan **Descriptors** merupakan fondasi arsitektur di balik framework Python modern kelas industri yang menyediakan declarative API, dynamic validation, dan automated state synchronization.