# BAB 05: Object-Oriented Deep Dive & Metaprogramming
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta mampu:
1. **Menganalisis dan Membedah CPython Type System**: Memahami representasi internal tipe data, `PyTypeObject`, *dictionary layout*, dan resolusi atribut pada level C-API.
2. **Menguasai Descriptor Protocol**: Mengimplementasikan *data* dan *non-data descriptors* tingkat lanjut (`__get__`, `__set__`, `__delete__`, `__set_name__`) untuk membangun *framework-level abstractions* seperti *custom ORM*, validasi tipe deklaratif, dan *lazy computed fields*.
3. **Menerapkan Metaprogramming Skala Produksi**: Memilih secara presisi antara `__init_subclass__`, Class Decorator, dan kustom `metaclass` (`type.__new__`, `type.__init__`, `type.__call__`) untuk manipulasi *class construction life-cycle*.
4. **Menerapkan C3 Linearization Algorithm**: Menghitung, mendiagnosis, dan memitigasi konflik *Method Resolution Order* (MRO) pada arsitektur pewarisan berganda (*multiple inheritance*) kompleks.
5. **Mengoptimalkan Jejak Memori dan Kinerja**: Memanfaatkan `__slots__` secara deterministik pada sistem ber throughput tinggi untuk mereduksi *memory footprint* hingga 60% dan mengeliminasi *allocation overhead*.

---

### 2. Prerequisite

Untuk menyerap materi ini secara optimal, peserta wajib menguasai:
- **Object-Oriented Programming (OOP) Dasar**: Deklarasi `class`, `self`, `__init__`, inheritance, encapsulation, dan polymorphism.
- **Python Data Model Dasar**: Magic methods umum (`__repr__`, `__str__`, `__eq__`, `__call__`, `__len__`, `__getitem__`).
- **First-Class Functions & Closures**: Higher-Order Functions, closure scopes (`nonlocal`), dan implementasi decorator standar (`@functools.wraps`).
- **Struktur Memori Dasar CPython**: Konsep *reference counting*, Garbage Collection (GC) *cyclic references*, dan pointers (konseptual level C).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. CPython Type System Internals
Di dalam runtime CPython, setiap objek adalah representasi dari struktur C bernama `PyObject` atau `PyVarObject`:

```c
// Representasi konseptual Include/object.h CPython
typedef struct _object {
    _PyObject_HEAD_EXTRA // Double linked-list untuk tracking GC
    Py_ssize_t ob_refcnt;
    struct _typeobject *ob_type;
} PyObject;
```

Ketika Anda mengeksekusi `class User: pass`, Anda sebenarnya menginstansiasi sebuah *instance* dari *metaclass* bawaan, yaitu `type` (yang di level C direpresentasikan oleh `PyType_Type` bertipe `PyTypeObject`). 

`PyTypeObject` berisi tabel *function pointers* (dikenal sebagai *slots* di level C) yang mendefinisikan seluruh perilaku objek, seperti:
- `tp_alloc`: Alokasi memori heap.
- `tp_new`: Konstruksi objek.
- `tp_init`: Inisialisasi state.
- `tp_getattro` dan `tp_setattro`: Mekanisme resolusi pencarian atribut.
- `tp_descr_get` dan `tp_descr_set`: Slot untuk *Descriptor Protocol*.

#### B. The Attribute Lookup Resolution Precedence
Ketika Anda mengakses atribut `instance.attribute`, runtime CPython mengeksekusi fungsi level-C `_PyObject_GenericGetAttrWithDict`. Algoritma prioritas resolusi atribut berlangsung dengan aturan kaku:

1. **Class MRO Lookup**: Cari nama atribut di `instance.__class__.__mro__`.
2. **Data Descriptor**: Jika atribut ditemukan pada Class/MRO dan mengimplementasikan `__set__` atau `__delete__` (selain `__get__`), panggil `type(descriptor).__get__(descriptor, instance, type(instance))` dan kembalikan hasilnya. Langkah ini **mengabaikan** apa pun yang ada di `instance.__dict__`.
3. **Instance Dictionary**: Jika bukan *data descriptor*, CPython memeriksa `instance.__dict__['attribute']`. Jika ada, nilainya langsung dikembalikan.
4. **Non-Data Descriptor**: Jika tidak ada di `instance.__dict__`, tetapi ditemukan di class/MRO sebagai objek yang hanya mengimplementasikan `__get__` (misalnya method standar atau `@functools.cached_property`), panggil `type(descriptor).__get__(descriptor, instance, type(instance))`.
5. **Class Attribute Biasa**: Jika ada di class/MRO tetapi bukan descriptor, kembalikan nilai atribut class tersebut.
6. **Fallback `__getattr__`**: Jika seluruh langkah di atas gagal (menghasilkan `AttributeError`), panggil `instance.__getattr__('attribute')` jika didefinisikan. Jika tidak, raise `AttributeError`.

```
                  [ instance.attr Access ]
                             |
                             v
           [ Cari di Class MRO: Apakah ada? ]
                     /                \
                  (Ya)               (Tidak)
                  /                     \
       [ Is Data Descriptor? ]           v
         (Has __set__/__delete__)   [ Check instance.__dict__ ]
            /          \               /          \
         (Ya)         (Tidak)       (Ada)      (Tidak Ada)
         /              \            /              \
[ Call __get__ ]   [ Check inst.__dict__ ]      [ Call __getattr__ ]
                      /         \                      \
                   (Ada)     (Tidak Ada)         (Raise AttributeError)
                   /               \
         [ Return Value ]    [ Is Non-Data Desc? ]
                                (Has __get__ only)
                                 /          \
                              (Ya)         (Tidak)
                              /              \
                     [ Call __get__ ]   [ Return Class Attr ]
```

#### C. Descriptor Protocol Lifecycle: `__set_name__` (PEP 487)
Sebelum Python 3.6, sebuah descriptor tidak mengetahui nama atribut target tempat ia di-assign di dalam class tanpa *boilerplate metaclass*. Dengan penambahan `__set_name__(self, owner, name)` pada runtime CPython, urutan konstruksinya menjadi:
1. Class body dieksekusi dalam *namespace mapping* sementara (`dict`).
2. Metaclass membangun class object (`type.__new__`).
3. Runtime CPython melakukan iterasi terhadap seluruh atribut baru di class.
4. Jika atribut mengimplementasikan `__set_name__`, runtime memanggil `descriptor.__set_name__(owner_class, attribute_name)`.

#### D. C3 Superclass Linearization
Python menggunakan algoritma **C3 Linearization** untuk membangun MRO:
Untuk sebuah class $C$ dengan base classes $B_1, B_2, ..., B_n$:
$$L[C] = C + \text{merge}(L[B_1], L[B_2], ..., L[B_n], B_1 B_2 ... B_n)$$
Operasi $\text{merge}$ mengambil head dari list pertama yang bukan merupakan proper tail dari list lainnya. Jika head valid, ia ditarik keluar dan ditambahkan ke MRO, lalu proses diulang hingga semua list kosong atau terjadi kontradiksi (yang memicu `TypeError: Cannot create a consistent method resolution order (MRO)`).

---

### 4. Why & What

| Pendekatan | Apa Itu? | Mengapa Dipilih? (Use Case) | Kapan Dihindari? |
| :--- | :--- | :--- | :--- |
| **`__slots__`** | Direktif class level yang menginstruksikan CPython mengalokasikan array pointer tetap, bukan `__dict__`. | Reduksi konsumsi memori ekstrim untuk instansiasi jutaan objek (misal: read-heavy data pipelines). | Multiple inheritance dengan slot bentrok; kebutuhan dynamic monkey patching atribut. |
| **Descriptors** | Objek yang mengontrol akses pembacaan/penulisan atribut lain via binding protocol. | Reusable validation logic, lazy evaluations, ORM schema field mappings. | Logika atribut sederhana yang cukup ditangani oleh `@property` bawaan. |
| **`__init_subclass__`**| Hook resmi PEP 487 yang otomatis dipanggil saat sebuah class mewarisi base class. | Registrasi plugin otomatis, validasi skema turunan ringan tanpa overhead metaclass. | Kebutuhan memodifikasi namespace class *sebelum* class tersebut dibuat. |
| **Metaclasses** | "Class of a class" (`type`). Mengontrol alokasi (`__new__`) dan inisialisasi (`__init__`) class. | Modifikasi AST/Namespace class sebelum instansiasi, injeksi API deep-level framework. | Solusi problem tingkat aplikasi umum; berisiko memicu metaclass conflict jika over-engineered. |

---

### 5. How (Workflow Detail)

Berikut adalah siklus hidup evaluasi kode Python saat membaca definisi class dan membuat instance:

```
[ Parsing & Code Object Compilation ]
                 |
                 v
   [ 1. Metaclass Identification ]
(Cari metaclass=... di base, inheritance, atau fallback ke type)
                 |
                 v
   [ 2. Namespace Preparation ]
(Metaclass.__prepare__(name, bases) -> return mapping dict)
                 |
                 v
   [ 3. Class Body Execution ]
(Eksekusi kode dalam namespace mapping)
                 |
                 v
   [ 4. Metaclass Instantiation ]
(Metaclass.__new__(meta, name, bases, namespace))
                 |
                 v
   [ 5. Descriptor Initialization Callback ]
(Loop namespace -> call __set_name__(class, name) jika ada)
                 |
                 v
   [ 6. Subclass Notification ]
(Panggil __init_subclass__ pada parent classes)
                 |
                 v
   [ 7. Class Construction Done ]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Pabrik Mobil dan Standar Blueprint

- **Instance (`PyObject`)**: Mobil fisik yang berjalan di jalan raya.
- **Class**: Blueprint perakitan spesifik (misal: Seri Sedan X).
- **Descriptor**: Modul komponen khusus (misal: Unit Pengereman ABS). Setiap kali pedal rem ditekan (`__set__`), modul ABS mengambil alih kontrol tekanan rem alih-alih pengemudi menekan kawat rem secara langsung.
- **Metaclass (`type`)**: Arsitek yang merancang mesin pembuat *blueprint*. Metaclass dapat menolak blueprint jika blueprint tersebut tidak menyertakan fitur keamanan standar sebelum mobil pertama sempat diproduksi.

```
+-----------------------------------------------------------+
|                      METACLASS (type)                     |
|  - Mengatur pembuatan class                               |
|  - Memvalidasi atribut class saat boot-time               |
+-----------------------------+-----------------------------+
                              | Menginstansiasi
                              v
+-----------------------------------------------------------+
|                       CLASS OBJECT                        |
|  - Memegang __dict__ class & MRO                          |
|  - Mengandung instance descriptor: Field(), Property()   |
+-----------------------------+-----------------------------+
                              | Menginstansiasi
                              v
+-----------------------------------------------------------+
|                     INSTANCE OBJECT                       |
|  - Objek runtime yang berinteraksi dengan request         |
|  - Mengakses descriptor lewat delegasi Class              |
+-----------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Advanced Typed Descriptor (`__set_name__` & Type Enforcing)

```python
from typing import Any

class ValidatedString:
    def __init__(self, min_length: int = 0) -> None:
        self.min_length = min_length
        self.storage_name: str = ""

    def __set_name__(self, owner: type, name: str) -> None:
        # CPython runtime mengisi name secara otomatis via PEP 487
        self.storage_name = f"_validated_{name}"

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self  # Diakses dari class level
        return getattr(instance, self.storage_name, None)

    def __set__(self, instance: Any, value: Any) -> None:
        if not isinstance(value, str):
            raise TypeError(f"Atribut '{self.storage_name}' harus bertipe str, diterima: {type(value).__name__}")
        if len(value) < self.min_length:
            raise ValueError(f"Panjang minimal untuk '{self.storage_name}' adalah {self.min_length}")
        setattr(instance, self.storage_name, value)


class UserProfile:
    username = ValidatedString(min_length=3)
    display_name = ValidatedString(min_length=1)

    def __init__(self, username: str, display_name: str) -> None:
        self.username = username
        self.display_name = display_name


# Verifikasi
profile = UserProfile("johndoe", "John")
print(profile.username)  # johndoe
# profile.username = 42  # Memicu TypeError
# profile.display_name = ""  # Memicu ValueError
```

#### B. Practical Example: Zero-Overhead Memory Optimized Event Engine (`__slots__` + Weakref)

```python
import weakref
from typing import Callable, Any

class EventHandlerSlot:
    """Non-data descriptor yang mengelola dynamic binding listener dengan safe weak reference."""
    def __init__(self) -> None:
        self._name: str = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        # Menyediakan wrapper dispatch pemanggilan aman
        return lambda *args, **kwargs: instance._dispatch(self._name, *args, **kwargs)


class MicroEventSystem:
    # Memaksa CPython tidak membuat __dict__ & __weakref__ kecuali dideklarasikan eksplisit
    __slots__ = ("_listeners", "__weakref__")

    publish = EventHandlerSlot()

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable[..., Any]]] = {}

    def subscribe(self, event_name: str, callback: Callable[..., Any]) -> None:
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)

    def _dispatch(self, event_type: str, *args: Any, **kwargs: Any) -> None:
        for listener in self._listeners.get(event_type, []):
            listener(*args, **kwargs)


# Memory Profiling Verifikasi
event_bus = MicroEventSystem()
event_bus.subscribe("publish", lambda msg: print(f"Event Received: {msg}"))
event_bus.publish("Message: System Up")

assert not hasattr(event_bus, "__dict__"), "Memory leak! __dict__ tidak boleh terbentuk."
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Desain Core ORM Engine: Declarative Entity Schema dengan Registry Hook Metaclass
Sebuah enterprise fintech service membutuhkan validasi field deklaratif yang aman tanpa bergantung pada library eksternal (seperti Pydantic/SQLAlchemy) pada sistem low-latency processing gateway.

```python
from __future__ import annotations
import re
from typing import Any, Dict, Tuple, Type


# 1. BASE FIELD DESCRIPTORS
class Field:
    def __init__(self, primary_key: bool = False, nullable: bool = False) -> None:
        self.primary_key = primary_key
        self.nullable = nullable
        self.name: str = ""

    def __set_name__(self, owner: Type[Any], name: str) -> None:
        self.name = name

    def __get__(self, instance: Any, owner: Type[Any] | None = None) -> Any:
        if instance is None:
            return self
        return instance.__dict__.get(self.name, None)

    def __set__(self, instance: Any, value: Any) -> None:
        if value is None and not self.nullable:
            raise ValueError(f"Constraint Violation: Field '{self.name}' tidak boleh bernilai None.")
        self.validate(value)
        instance.__dict__[self.name] = value

    def validate(self, value: Any) -> None:
        pass


class StringField(Field):
    def __init__(self, max_length: int = 255, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.max_length = max_length

    def validate(self, value: Any) -> None:
        if value is not None:
            if not isinstance(value, str):
                raise TypeError(f"Field '{self.name}' harus berupa string. Diterima: {type(value)}")
            if len(value) > self.max_length:
                raise ValueError(f"Field '{self.name}' melampaui max_length {self.max_length}")


class DecimalField(Field):
    def validate(self, value: Any) -> None:
        if value is not None and not isinstance(value, (int, float)):
            raise TypeError(f"Field '{self.name}' harus numerik.")
        if value is not None and value < 0:
            raise ValueError(f"Field '{self.name}' tidak boleh negatif.")


# 2. METACLASS REGISTRY & VALIDATOR
class EntityMeta(type):
    """
    Metaclass yang:
    1. Mengumpulkan semua instance Field ke dalam `_fields` dictionary.
    2. Menegakkan aturan bahwa setiap entity wajib memiliki tepat 1 primary_key.
    3. Mendaftarkan entity ke registry global untuk sinkronisasi runtime engine.
    """
    REGISTRY: Dict[str, Type[Entity]] = {}

    def __new__(
        mcs, 
        name: str, 
        bases: Tuple[Type[Any], ...], 
        namespace: Dict[str, Any]
    ) -> EntityMeta:
        fields: Dict[str, Field] = {}
        pk_count = 0

        # Tarik field dari namespace
        for attr_name, attr_value in list(namespace.items()):
            if isinstance(attr_value, Field):
                fields[attr_name] = attr_value
                if attr_value.primary_key:
                    pk_count += 1

        # Proteksi inheritance: abaikan base entity
        if bases:
            if pk_count != 1:
                raise TypeError(
                    f"Entity '{name}' harus memiliki tepat SATU primary_key. Ditemukan: {pk_count}"
                )

        namespace["_fields"] = fields
        cls = super().__new__(mcs, name, bases, namespace)

        if bases:
            mcs.REGISTRY[name] = cls

        return cls


# 3. BASE ENTITY
class Entity(metaclass=EntityMeta):
    def __init__(self, **kwargs: Any) -> None:
        for field_name, field_obj in self._fields.items():
            if field_name in kwargs:
                setattr(self, field_name, kwargs.pop(field_name))
            else:
                # Default init fallback
                if not field_obj.nullable and not field_obj.primary_key:
                    raise ValueError(f"Missing mandatory field: {field_name}")
                setattr(self, field_name, None)
        
        if kwargs:
            raise AttributeError(f"Attribut tidak terdaftar pada schema: {list(kwargs.keys())}")

    def serialize(self) -> Dict[str, Any]:
        return {name: getattr(self, name) for name in self._fields}


# 4. IMPLEMENTASI ENTITY DOMAIN
class TransactionLedger(Entity):
    txn_id = StringField(max_length=64, primary_key=True)
    sender_account = StringField(max_length=34, nullable=False)
    receiver_account = StringField(max_length=34, nullable=False)
    amount = DecimalField(nullable=False)


# --- RUNTIME EXECUTION & VERIFICATION ---
if __name__ == "__main__":
    # Sukses Case
    txn = TransactionLedger(
        txn_id="TXN-9988231",
        sender_account="ID-ACC-01",
        receiver_account="ID-ACC-02",
        amount=1500000.00
    )
    print("Serialization Valid:", txn.serialize())

    # Metadata Inspection
    assert "TransactionLedger" in EntityMeta.REGISTRY

    # Fail Case 1: Primary Key Absen saat Schema Definition
    try:
        class InvalidLedger(Entity):
            temp_id = StringField()
    except TypeError as e:
        print("Expected Error Captured:", e)
```

---

### 9. Trade-offs

```
                       COMPLEXITY VS CONTROL
                                 ^
        Metaclass                |  Tinggi (Deep AST/Class interception,
        (Custom type engine)     |  risiko MRO & Meta conflict)
                                 |
        Descriptors              |  Menengah-Tinggi (Fine-grained memory & 
        (Protocol hooks)         |  attribute access delegation)
                                 |
        __init_subclass__        |  Menengah (Sederhana, Pythonic, 
        (PEP 487)                |  tanpa meta-class conflicts)
                                 |
        @property / Decorator    |  Rendah (Mudah di-debug, non-intrusif)
                                 +--------------------------------------->
                                              ABSTRACTION POWER
```

| Mekanisme | Performance Impact | Latency Impact | Scalability Impact | Complexity / Maintenance Cost |
| :--- | :--- | :--- | :--- | :--- |
| **`__slots__`** | Alokasi memori berkurang signifikan (30-60%). | Mengurangi cache misses pada CPU L1/L2. | Sangat Tinggi (jutaan objek per node). | Menengah (pewarisan antar kelas berslot membutuhkan koordinasi ketat). |
| **Descriptors** | Menambah 1 layer function invocation pada lookup. | Mikro-overhead pada CPython call dispatch (`tp_descr_get`). | Tinggi (enkapsulasi validasi reusable). | Rendah - Menengah. |
| **Metaclasses** | Overhead eksekusi hanya saat import time / boot-up class creation. | **Nol** pada instance runtime access. | Sangat Tinggi untuk framework builders. | Sangat Tinggi (kolega junior akan kesulitan men-debug traceback). |
| **`__init_subclass__`**| Overhead saat import time / subclassing. | **Nol** pada instance runtime access. | Tinggi (alternatif 90% metaclass use-cases). | Rendah (standard Pythonic code). |

---

### 10. Common Mistakes & Troubleshooting

#### Kasus 1: Menyimpan Instance State di dalam Descriptor Instance
```python
# ANTI-PATTERN (BUG KRITIS: Shared State antar instance)
class BrokenField:
    def __init__(self):
        self.value = None  # Variabel ini dimiliki oleh DESCRIPTOR, bukan objek pemilik!

    def __get__(self, instance, owner):
        return self.value

    def __set__(self, instance, value):
        self.value = value

class Profile:
    name = BrokenField()

p1 = Profile()
p2 = Profile()
p1.name = "Alice"
p2.name = "Bob"
print(p1.name)  # Output: Bob! (Data p1 tertimpa p2)
```
*Solusi*: Simpan state di dalam instance mapping: `instance.__dict__[self.name] = value` atau menggunakan `WeakKeyDictionary(self)`.

#### Kasus 2: Metaclass Conflict pada Multiple Inheritance
```python
class MetaA(type): pass
class MetaB(type): pass

class BaseA(metaclass=MetaA): pass
class BaseB(metaclass=MetaB): pass

# ERROR: TypeError: metaclass conflict: the metaclass of a derived class 
# must be a (non-strict) subclass of the metaclasses of all its bases
class SystemNode(BaseA, BaseB): pass
```
*Troubleshooting Rule*: Turunan harus memiliki metaclass yang merupakan subclass dari semua metaclass parent:
```python
class ResolvedMeta(MetaA, MetaB): pass
class SystemNode(BaseA, BaseB, metaclass=ResolvedMeta): pass
```

#### Kasus 3: Multiple Inheritance Diamond Problem dengan Broken Signature
*Penyebab*: Penggunaan `super().__init__()` tanpa passing `*args, **kwargs` secara konsisten pada seluruh chain.
*Solusi*: Selalu gunakan teknik *Cooperative Multiple Inheritance*:
```python
class BaseNode:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Base class menutup rantai MRO ke object
        super().__init__()

class LeftNode(BaseNode):
    def __init__(self, val_a: int, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.val_a = val_a

class RightNode(BaseNode):
    def __init__(self, val_b: str, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.val_b = val_b

class ConcreteNode(LeftNode, RightNode):
    def __init__(self, val_a: int, val_b: str, *args: Any, **kwargs: Any) -> None:
        super().__init__(val_a=val_a, val_b=val_b, *args, **kwargs)
```

---

### 11. Best Practices (Production Checklist)

1. [ ] **Prinsip YAGNI**: Jangan gunakan `metaclass` jika masalah dapat diselesaikan dengan `__init_subclass__` atau Class Decorator.
2. [ ] **Descriptor State Separation**: Selalu isolasi state ke `instance.__dict__` atau gunakan `__slots__` pada instance target, jangan pernah simpan di dalam `self` descriptor.
3. [ ] **Implementasikan `__set_name__`**: Wajib mengimplementasikan `__set_name__` pada kustom descriptor untuk mengikat atribut target otomatis tanpa konfigurasi manual.
4. [ ] **Evaluasi `__slots__` Inheritance**: Jika mewarisi class yang memiliki `__slots__`, class anak harus mendefinisikan `__slots__ = ()` jika tidak menambah atribut baru, atau deklarasikan `__slots__ = ('attr_baru',)` untuk mencegah CPython membuatkan `__dict__` baru secara diam-diam.
5. [ ] **C3 Super Compliance**: Pastikan seluruh class dalam multiple inheritance memanggil `super().__init__(*args, **kwargs)` secara kooperatif.
6. [ ] **Performance Validation**: Lakukan profiling memori menggunakan `sys.getsizeof` atau `tracemalloc` ketika menerapkan optimasi `__slots__`.

---

### 12. Hands-on Practice

Buat struktur direktori di mesin Anda:
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

Simpan file berikut sebagai `hands-on/m02/lazy_property_engine.py`:

```python
"""
Hands-on Module 02: Building a Thread-Safe Lazy Computed Property with Invalidation
Menggunakan Non-Data/Data Descriptor Dual-Mode & Reentrant Lock.
"""

from __future__ import annotations
import threading
import time
from typing import Any, Callable, Generic, TypeVar, overload

T = TypeVar("T")

class ComputedField(Generic[T]):
    def __init__(self, func: Callable[[Any], T]) -> None:
        self._func = func
        self._name: str = ""
        self._lock = threading.RLock()

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    @overload
    def __get__(self, instance: None, owner: type) -> ComputedField[T]: ...

    @overload
    def __get__(self, instance: Any, owner: type | None = None) -> T: ...

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self

        # Double-checked locking pattern untuk thread-safe computed caching
        storage_attr = f"_cache_{self._name}"
        if storage_attr not in instance.__dict__:
            with self._lock:
                if storage_attr not in instance.__dict__:
                    computed_value = self._func(instance)
                    instance.__dict__[storage_attr] = computed_value
                    return computed_value

        return instance.__dict__[storage_attr]

    def __delete__(self, instance: Any) -> None:
        """Memungkinkan cache invalidation dengan perintah: del instance.attribute"""
        storage_attr = f"_cache_{self._name}"
        with self._lock:
            if storage_attr in instance.__dict__:
                del instance.__dict__[storage_attr]


# =========================================================================
# Eksekusi Verifikasi
# =========================================================================
class AnalyticsPayload:
    def __init__(self, raw_data: list[int]) -> None:
        self.raw_data = raw_data

    @ComputedField
    def heavy_metric(self) -> int:
        print("[Engine] Menghitung metrik kompleks (Heavy Computation)...")
        time.sleep(0.5)  # Simulasi latency CPU
        return sum(x ** 2 for x in self.raw_data)


if __name__ == "__main__":
    payload = AnalyticsPayload([1, 2, 3, 4, 5])
    
    print("1. Pembacaan Pertama (Harus Hitung):")
    val1 = payload.heavy_metric
    print(f"Hasil: {val1}")

    print("\n2. Pembacaan Kedua (Harus Ambil dari Cache):")
    val2 = payload.heavy_metric
    print(f"Hasil: {val2}")

    print("\n3. Invalidate Cache via __delete__ protocol:")
    del payload.heavy_metric

    print("\n4. Pembacaan Ketiga Pasca Invalidasi (Harus Re-compute):")
    val3 = payload.heavy_metric
    print(f"Hasil: {val3}")
```

Jalankan script:
```bash
python lazy_property_engine.py
```

---

### 13. Exercise

#### Level: Easy
Buatlah data descriptor bernama `PositiveInteger` yang memverifikasi bahwa nilai yang dimasukkan ke atribut bertipe `int` dan bernilai $> 0$. Jika tidak valid, throw `TypeError` atau `ValueError`.

#### Level: Medium
Implementasikan class decorator `@enforce_types` yang membaca *type annotations* dari class yang didekorasi, dan secara dinamis mengganti semua tipe data primitif yang dianotasi menjadi instance `ValidatedField` (descriptor) tanpa merubah deklarasi asli pengguna.

#### Level: Hard
Selesaikan kasus **MRO Diamond Pattern Conflict**: Diberikan class `Stream`, `EncryptedStream(Stream)`, `BufferedStream(Stream)`, dan `CompressStream(Stream)`. 
1. Buat hierarki di mana sebuah class `SecureTransformedStream` mewarisi ketiganya dengan urutan eksekusi data transformation yang kooperatif menggunakan `super().write(data)`.
2. Urutan eksekusi harus: Kompresi $\rightarrow$ Enkripsi $\rightarrow$ Buffering $\rightarrow$ Penulisan Stream Akhir.
3. Hindari kegagalan serialisasi MRO dengan memodifikasi base declaration secara deterministik.

---

### 14. Challenge

**Skenario**: Anda ditugaskan membangun **High-Frequency Trading Configuration Engine** (HFT-Config).
*Kebutuhan Arsitektur*:
1. **Zero Dynamic Allocation**: Semua class konfigurasi harus menerapkan `__slots__` secara mutlak untuk mencegah memory footprint membengkak.
2. **Immutable Runtime Config**: Ketika instance konfigurasi dibuat, seluruh atribut bersifat *Read-Only*. Modifikasi atribut apa pun harus melempar `FrozenInstanceError`.
3. **Auto-Coercion Protocol**: Terapkan Metaclass bernama `StrictConfigMeta` yang menginspeksi schema. Jika schema mendefinisikan field `port: int`, dan saat runtime dimasukkan string `"8080"`, konfigurasi otomatis melakukan konversi ke `8080`. Jika gagal konversi, lempar kegagalan pada saat instansiasi.
4. **No Third-Party Libraries**: Dilarang mengimpor library di luar standard library Python bawaan.
5. **No `__dict__` leakage**: `hasattr(instance, '__dict__')` harus bernilai `False`.

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Mengapa sebuah *Data Descriptor* memiliki preseden resolusi lebih tinggi daripada *Instance Dictionary* (`instance.__dict__`)?
2. Kapan method `__set_name__` dieksekusi oleh runtime CPython?
3. Apa perbedaan fundamental antara method `__new__` dan `__init__` pada Metaclass?
4. Mengapa class yang mendefinisikan `__slots__ = ()` memiliki konsumsi memori lebih kecil dibanding class biasa?
5. Apa return value bawaan dari method `type.__prepare__`?

#### 5 Pertanyaan Intermediate
6. Jika sebuah class mendefinisikan `__slots__ = ('id',)`, tetapi parent-nya **tidak** mendefinisikan `__slots__`, apakah objek tersebut menghemat memori? Jelaskan mekanismenya!
7. Kapan algoritma C3 Linearization melempar eksepsi `TypeError`?
8. Bagaimana implementasi `@property` bawaan Python bekerja di bawah kap mesin? Apakah ia Data Descriptor atau Non-Data Descriptor?
9. Jelaskan perbedaan use-case di mana `__init_subclass__` **tidak dapat** menggantikan peran `metaclass`!
10. Apa yang terjadi secara internal pada CPython jika descriptor hanya mengimplementasikan `__get__` dan kita mencoba meng-assign nilai baru via `instance.attr = 100`?

#### 3 Skenario Kasus Produksi
11. **Skenario A (Memory Spike)**: Sebuah microservice yang memproses ingest jutaan record transaksi per menit mengalami OOM (Out Of Memory). Developer telah menambahkan `__slots__ = ('id', 'amount')` pada class `TransactionRecord`. Namun saat di-profiling, memori tidak berkurang sama sekali. Analisis apa kemungkinan kesalahan struktural inheritance-nya!
12. **Skenario B (Concurrency Bug)**: Tim analitika data menggunakan custom lazy-descriptor pada sebuah multithreaded web server (Gunicorn dengan worker gthread). Sesekali, fungsi lambat yang di-cache berjalan 2 kali pada waktu bersamaan untuk satu request. Bagian manakah dari descriptor pattern mereka yang defektif?
13. **Skenario C (Dynamic Plugin Injection)**: Sebuah sistem core perbankan memerlukan arsitektur plugin terisolasi. Developer menggunakan `metaclass` untuk mencatat setiap plugin yang diinstal. Namun, plugin dari pihak ketiga yang mewarisi class GUI framework PyQt/PySide gagal diimpor dengan pesan error: `metaclass conflict`. Bagaimana tim Anda menyelesaikan benturan hierarki C-extension type tersebut?

---

### 16. Summary

- **CPython Object Model** membedakan entitas berdasarkan *slots C-level*. Atribut lookup tidak sesederhana membaca dictionary; ia tunduk pada aturan hierarki ketat: Data Descriptor $\rightarrow$ Instance Dict $\rightarrow$ Non-Data Descriptor $\rightarrow$ Class MRO $\rightarrow$ `__getattr__`.
- **Descriptor Protocol** (`__get__`, `__set__`, `__delete__`, `__set_name__`) adalah fondasi utama dari hampir seluruh fitur abstraksi modern Python, termasuk method binding, `@property`, `@classmethod`, `@staticmethod`, dan enterprise ORM.
- **`__slots__`** mengeliminasi `__dict__` dan `__weakref__`, mengalokasikan array C fixed-size untuk pointer atribut, menurunkan jejak memori secara radikal pada komputasi skala besar.
- **Metaprogramming Lifecycle** memberikan titik kontrol:
  - `type.__prepare__`: Menentukan struktur namespace (misal: pengurutan deklarasi).
  - `type.__new__`: Mengalokasikan class object sebelum terbentuk.
  - `type.__init__`: Konfigurasi class pasca pembuatan.
  - `__init_subclass__`: Interface modern (PEP 487) untuk ekstensibilitas kelas turunan tanpa kompleksitas *metaclass conflict*.