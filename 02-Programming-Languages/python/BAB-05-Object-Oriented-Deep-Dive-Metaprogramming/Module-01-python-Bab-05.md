# Bab 05 Module 01: Object-Oriented Deep Dive & Metaprogramming

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** 02-Programming-Languages
* **Topik Inti:** Python Advanced Internals
* **Modul:** Bab 05 Module 01 — Object-Oriented Deep Dive & Metaprogramming
* **Tingkat Kesulitan:** Advanced / Expert
* **Prasyarat:** Pemahaman solid mengenai OOP Python dasar (Inheritance, Polymorphism, Encapsulation), Magic Methods umum (`__str__`, `__repr__`, `__eq__`), First-class functions, dan Closures.
* **Alokasi Waktu Belajar:** 8 - 10 Jam Pembelajaran Terfokus

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Mendekonstruksi Lifecycle Instansiasi Objek:** Menguraikan peran deterministik `type.__call__`, `__new__`, dan `__init__` dalam pembentukan objek pada tingkat runtime CPython.
2. **Menguasai Descriptor Protocol:** Mengimplementasikan Data Descriptors (`__set__`, `__get__`) dan Non-Data Descriptors (`__get__`) untuk mengabstraksi atribusi properti, enkapsulasi mutasi, dan optimasi lazy-loading.
3. **Menganalisis dan Memprediksi MRO via Algoritma C3 Linearization:** Menghitung urutan resolusi method dalam skenario *diamond problem* yang kompleks secara manual dan programatis.
4. **Merancang Metakelas Kustom (`type` derivation):** Mengontrol pembuatan kelas melalui intercepting fase `__prepare__`, `__new__`, dan `__init__` guna memvalidasi, memodifikasi, dan mendaftarkan namespace secara deklaratif.
5. **Mengevaluasi Alternatif Modern Metaprogramming:** Memilih secara tepat antara Metaclasses, `__init_subclass__` (PEP 487), dan Class Decorators berdasarkan trade-off kompleksitas dan performa.
6. **Membangun Mini-Framework Deklaratif Berstandar Produksi:** Membangun *schema validator* atau ORM ringan berbasis descriptor dan metaclass/`__init_subclass__` yang aman terhadap kebocoran memori (*memory-leak-safe*).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: "Everything is an Object, and Classes are Instances"
Dalam Python, kelas bukanlah sekadar blueprint pasif yang dikompilasi ke bytecode statis. Kelas adalah objek hidup (*first-class citizens*) yang diinstansiasi pada saat runtime. 
* Objek `10` adalah instansiasi dari kelas `int`.
* Objek `"Halo"` adalah instansiasi dari kelas `str`.
* Kelas `int`, `str`, dan `MyClass` Anda sendiri adalah instansiasi dari metakelas `type`.

```
+--------------------+
|       type         | <----+ (Metakelas: Menciptakan Kelas)
+--------------------+      |
      ^         ^           |
      |         |           | (Instansiasi)
+-----+----+  +-+--------+  |
|  class   |  |  class   |--+
| Customer |  | Product  |
+----------+  +----------+
      ^             ^
      |             | (Instansiasi)
+-----+------+  +---+--------+
| customer_1 |  | product_A  | (Objek / Instansiasi Biasa)
+------------+  +------------+
```

### Mental Model Metaprogramming: "The Code that Writes Code"
Bayangkan metaprogramming seperti sistem manufaktur:
* Objek adalah produk akhir (misal: mobil).
* Kelas adalah pabrik yang mencetak mobil.
* Metakelas adalah pabrik yang membangun pabrik tersebut (*the factory that builds the factory*).
Jika Anda perlu memastikan bahwa setiap pabrik mobil wajib memiliki sensor pemadam kebakaran sebelum mulai beroperasi, Anda tidak memodifikasi setiap mobil; Anda mendefinisikan aturan tersebut pada pabrik pembuat pabrik (*Metaclass*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Siklus Hidup Instansiasi Objek

Ketika sintaks `obj = MyClass(*args, **kwargs)` dieksekusi, kontrol runtime diatur melalui chain interaksi berikut:

```
               [ User Call: MyClass(*args, **kwargs) ]
                                  |
                                  v
                  [ type.__call__(MyClass, *args, **kwargs) ]
                                  |
            +---------------------+---------------------+
            |                                           |
            v                                           v
[ MyClass.__new__(cls, *args) ]              [ Apakah hasil __new__ ]
(Alokasi memori objek baru)                  [ instansiasi MyClass? ]
            |                                           |
            +-------------------+-----------------------+
                                |
                                | (Ya)
                                v
                [ MyClass.__init__(self, *args) ]
                (Inisialisasi atribut internal)
                                |
                                | (Tidak -> Bypass __init__)
                                v
                        [ Return Object ]
```

### 2. Siklus Hidup Pembentukan Kelas (Metaclass Lifecycle)

Ketika Python menemukan blok `class TargetClass(metaclass=Meta):`:

```
1. Identifikasi Metakelas -> Meta
2. Meta.__prepare__(name, bases, **kwds) -> Mengembalikan mapping dict/OrderedDict
3. Eksekusi Class Body -> Populasi namespace dictionary
4. Meta.__new__(mcls, name, bases, namespace, **kwds) -> Alokasi objek Class di heap
5. Meta.__init__(cls, name, bases, namespace, **kwds) -> Finalisasi konfigurasi Class
6. Return Class Object
```

### 3. Diagram Alur Resolusi Atribut (Descriptor Protocol)

Saat eksekusi `instance.attribute`:

```
                 Mulai pencarian instance.attr
                               |
            +------------------v------------------+
            | Apakah attr ada di Class(instance)  |
            | dan merupakan Data Descriptor?       |
            | (memiliki __get__ DAN __set__)      |
            +------------------+------------------+
                               |
                      +--------+--------+
                     Ya                Tidak
                      |                 |
                      v                 v
          [ Panggil Data ]      +-------------------------------+
          [ Descriptor   ]      | Apakah attr ada di            |
          [ __get__      ]      | instance.__dict__?            |
                                +---------------+---------------+
                                                |
                                       +--------+--------+
                                      Ya                Tidak
                                       |                 |
                                       v                 v
                                [ Ambil dari    ]  +--------------------+
                                [ instance.__dict] | Apakah attr di     |
                                                   | Class(instance) &  |
                                                   | Non-Data Descriptor|
                                                   | (hanya __get__)?   |
                                                   +---------+----------+
                                                             |
                                                    +--------+--------+
                                                   Ya                Tidak
                                                    |                 |
                                                    v                 v
                                            [ Panggil Non-Data ] [ Lookup Class ]
                                            [ Descriptor __get__] [ __dict__ biasa]
                                                                      |
                                                                   (Jika nihil)
                                                                      v
                                                               [ Panggil        ]
                                                               [ __getattr__    ]
                                                               [ jika ada       ]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### A. Anatomi Bytecode Class Construction
Ketika Python mengeksekusi definisi kelas, kompiler mentranslasikan blok kelas menjadi fungsi sementara yang dieksekusi dengan opcode khusus:

```python
# Disassembly dari: class A: x = 1
# Terlihat pemanggilan LOAD_BUILD_CLASS
import dis

code = compile("class A:\n    x = 1", "<string>", "exec")
dis.dis(code)
```

Output disassembly menghasilkan:
1. `LOAD_BUILD_CLASS`: Memasukkan fungsi bawaan `__build_class__` ke stack runtime.
2. `LOAD_CONST` (kode bodi kelas): Menempatkan closure bodi kelas.
3. `MAKE_FUNCTION`: Mengompilasi bodi kelas menjadi callable runtime.
4. `CALL_FUNCTION`: Menjalankan `__build_class__(body_func, 'A', ...)` yang memanggil alur metaclass.

### B. CPython Internal Struct: `PyTypeObject`
Di dalam CPython runtime (berkas `Include/cpython/object.h`), tipe data (kelas) direpresentasikan oleh struktur C `PyTypeObject`.
* `tp_new`: Implementasi native level C dari `__new__`.
* `tp_init`: Implementasi level C dari `__init__`.
* `tp_descr_get` & `tp_descr_set`: Function pointers yang mendefinisikan descriptor behavior.
* `tp_mro`: Pointer ke tuple yang menyimpan Method Resolution Order.

### C. `__dict__` vs `__slots__`
Secara default, setiap instansiasi kelas Python memiliki atribut `__dict__` (berupa `PyDictObject`) yang mengalokasikan memori dinamis di heap untuk menyimpan atribut instans.
* **Overhead `__dict__`:** Alokasi minimum sebuah hash table Python adalah 104-152 byte, bertumbuh seiring tabulasi hash.
* **Mekanisme `__slots__`:** Menginstruksikan CPython untuk meniadakan `__dict__` dan `__weakref__` dari instans, menggantikannya dengan array pointer berukuran statis (mirip struct C). Atribut yang didefinisikan dalam `__slots__` diakses melalui **Descriptor internal (Member Descriptors)** yang bekerja pada offset memori mentah instans.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. C3 Linearization Algorithm (MRO)
Python menggunakan algoritma C3 Linearization untuk menyelesaikan pewarisan berganda (*multiple inheritance*). C3 Linearization menjamin dua properti fundamental:
1. **Local Precedence Order (LPO):** Urutan kelas basis yang dideklarasikan dalam tanda kurung inheritance harus dipertahankan.
2. **Monotonicity:** Jika kelas $A$ mendahului kelas $B$ pada resolusi kelas $C_1$, maka $A$ tidak boleh muncul setelah $B$ pada resolusi subkelas mana pun dari $C_1$.

Rumus Formil C3:
$$L(C) = [C] + \text{merge}(L(B_1), L(B_2), \dots, L(B_n), [B_1, B_2, \dots, B_n])$$

Aturan `merge()`:
Pilih *head* (elemen pertama) dari list pertama yang sedang diperiksa. Jika *head* tersebut tidak muncul di bagian *tail* (seluruh elemen setelah elemen pertama) dari list-list lainnya dalam operasi merge:
* Tambahkan elemen tersebut ke MRO.
* Hapus elemen tersebut dari seluruh list pada parameter `merge`.
* Ulangi proses hingga semua list kosong. Jika sebuah elemen muncul di tail dari salah satu list, lewati ke list berikutnya. Jika tidak ada head yang valid dan list belum kosong, Python melempar `TypeError: Cannot create a consistent method resolution order (MRO)`.

### 2. Descriptor Protocol Internals
Descriptor adalah sembarang objek Python yang mengimplementasikan setidaknya satu method dari protokol berikut:
* `__get__(self, instance, owner=None) -> Any`
* `__set__(self, instance, value) -> None`
* `__delete__(self, instance) -> None`
* `__set_name__(self, owner, name) -> None` (Ditambahkan di PEP 487)

**Data Descriptor vs Non-Data Descriptor:**
* **Data Descriptor:** Mengimplementasikan `__set__` dan/atau `__delete__`. Memiliki preseden lebih tinggi daripada `instance.__dict__`.
* **Non-Data Descriptor:** Hanya mengimplementasikan `__get__` (contoh tipikal: method standar, `@staticmethod`, `@classmethod`). Kalah prioritas dibandingkan `instance.__dict__`.

### 3. Metaclass: `__prepare__`, `__new__`, dan `__init__`
Metakelas bertanggung jawab memproduksi objek kelas:
1. `__prepare__(mcls, name, bases, **kwargs) -> Mapping`: Mengembalikan mapping yang digunakan sebagai namespace lokal selama evaluasi class body. Berguna jika ingin menangkap atribut berdasarkan urutan deklarasinya (menggunakan `collections.OrderedDict`) sebelum Python 3.7, atau melarang duplikasi atribut.
2. `__new__(mcls, name, bases, namespace, **kwargs) -> type`: Mengalokasikan objek kelas di memori. Tempat transformasi atribut, injeksi method, atau validasi struktur kelas sebelum objek kelas terbentuk secara utuh.
3. `__init__(cls, name, bases, namespace, **kwargs) -> None`: Menginisialisasi objek kelas setelah terbentuk.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi validasi berbasis Data Descriptor yang memanfaatkan hook `__set_name__` dari PEP 487:

```python
from typing import Any, Type


class ValidationError(TypeError):
    """Custom exception untuk kegagalan validasi atribut."""
    pass


class TypedField:
    """Data Descriptor untuk memastikan type-safety pada atribut instans."""

    def __init__(self, expected_type: Type[Any]) -> None:
        self.expected_type = expected_type
        self.storage_name: str = ""

    def __set_name__(self, owner: Type[Any], name: str) -> None:
        # Menghindari benturan nama dengan menyimpan atribut langsung di dict instans
        # menggunakan private attribute name
        self.storage_name = f"_{name}"

    def __get__(self, instance: Any, owner: Type[Any]) -> Any:
        if instance is None:
            # Akses dipanggil dari Class level (e.g., Person.age)
            return self
        return getattr(instance, self.storage_name, None)

    def __set__(self, instance: Any, value: Any) -> None:
        if not isinstance(value, self.expected_type):
            raise ValidationError(
                f"Field '{self.storage_name[1:]}' harus bertipe {self.expected_type.__name__}, "
                f"didapatkan {type(value).__name__}."
            )
        setattr(instance, self.storage_name, value)

    def __delete__(self, instance: Any) -> None:
        raise AttributeError("Penghapusan atribut dilarang untuk field ini.")


class Person:
    name = TypedField(str)
    age = TypedField(int)

    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age


if __name__ == "__main__":
    p = Person("Alice", 30)
    print(f"Instansiasi Sukses: {p.name}, {p.age}")
    
    try:
        p.age = "Tiga Puluh"  # Harus melempar ValidationError
    except ValidationError as err:
        print(f"Validasi Berhasil Menangkap Error: {err}")
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Kelas `TypedField`
* **Baris 10-12 (`__init__`):** Menerima `expected_type` untuk disimpan sebagai metadata. Variabel `self.storage_name` diinisialisasi kosong karena nama field belum diketahui saat descriptor diinstansiasi.
* **Baris 14-17 (`__set_name__`):** Dijalankan secara otomatis oleh runtime CPython ketika kelas yang menggunakan descriptor ini (`Person`) selesai dibuat. `owner` adalah `Person`, dan `name` adalah `"name"` atau `"age"`. Kami menyimpan nama internal berupa `_{name}` untuk menghindari rekursi tak terbatas.
* **Baris 19-23 (`__get__`):**
  * `if instance is None:`: Ini menangani evaluasi saat descriptor diakses via namespace kelas (misal `Person.name`). Pola standar menuntut pengembalian objek descriptor itu sendiri agar dapat diinspeksi.
  * Mengembalikan nilai dari `instance.__dict__` melalui `getattr(instance, self.storage_name)`.
* **Baris 25-31 (`__set__`):** Menjadikan kelas ini **Data Descriptor**.
  * Dilakukan pengecekan `isinstance(value, self.expected_type)`. Jika gagal, lemparkan custom error `ValidationError`.
  * Jika validasi lolos, simpan ke instans: `setattr(instance, self.storage_name, value)`. Karena `self.storage_name` adalah string seperti `_age`, ini tidak akan memicu loop rekursif ke `__set__` dari descriptor `age`.
* **Baris 33-34 (`__delete__`):** Memblokir ekspresi `del p.age`, memperkuat prinsip imutabilitas parsial.

---

## SEKSI 09 — STUDI KASUS NYATA (Production Scenario)

### Skenario: Arsitektur Entity Engine untuk Micro-ORM Enterprise
Sebuah tim platform data enterprise memerlukan deklarasi model entitas basis data yang:
1. **Otomatis mendaftarkan skema model** ke dalam `ModelRegistry` terpusat untuk keperluan eksekusi migrasi otomatis.
2. **Memaksa pendefinisian primary key tunggal** pada setiap model pada saat class definition time (bukan runtime instansiasi).
3. **Mencegah mutasi nama tabel ilegal** (SQL injection prevention via safe identifier naming).
4. **Mendukung serialisasi otomatis ke dictionary** dengan memetakan descriptor field secara efisien tanpa inspeksi reflektif berulang pada setiap panggilan API.

Kita akan membangun sistem ini menggunakan kombinasi **Metakelas Kustom**, **Data Descriptors**, dan **Hook Class Building**.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

```python
from __future__ import annotations
import re
from typing import Any, Dict, Tuple, Type, Optional


class ModelRegistry:
    """Registry terpusat untuk menyimpan semua model aktif."""
    _registry: Dict[str, Type[Model]] = {}

    @classmethod
    def register(cls, model_cls: Type[Model]) -> None:
        table_name = model_cls._meta.get("table_name")
        if table_name in cls._registry:
            raise ValueError(f"Tabel '{table_name}' sudah terdaftar oleh {cls._registry[table_name]}.")
        cls._registry[table_name] = model_cls

    @classmethod
    def get_models(cls) -> Dict[str, Type[Model]]:
        return dict(cls._registry)


class Field:
    """Base Descriptor untuk semua Field ORM."""
    def __init__(self, primary_key: bool = False, nullable: bool = False) -> None:
        self.primary_key = primary_key
        self.nullable = nullable
        self.name: str = ""
        self.storage_name: str = ""

    def __set_name__(self, owner: Type[Any], name: str) -> None:
        self.name = name
        self.storage_name = f"__orm_{name}"

    def __get__(self, instance: Optional[Model], owner: Type[Any]) -> Any:
        if instance is None:
            return self
        return instance.__dict__.get(self.storage_name, None)

    def __set__(self, instance: Model, value: Any) -> None:
        if value is None and not self.nullable:
            raise ValueError(f"Field '{self.name}' tidak boleh bernilai None (nullable=False).")
        self.validate(value)
        instance.__dict__[self.storage_name] = value

    def validate(self, value: Any) -> None:
        """Hook method untuk validasi turunan."""
        pass


class StringField(Field):
    def __init__(self, max_length: int = 255, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.max_length = max_length

    def validate(self, value: Any) -> None:
        if value is not None:
            if not isinstance(value, str):
                raise TypeError(f"Field '{self.name}' harus berupa string.")
            if len(value) > self.max_length:
                raise ValueError(f"Panjang string untuk '{self.name}' melebihi batas {self.max_length}.")


class IntegerField(Field):
    def validate(self, value: Any) -> None:
        if value is not None and not isinstance(value, int):
            raise TypeError(f"Field '{self.name}' harus berupa integer.")


class ModelMeta(type):
    """
    Metaclass yang mengabstraksi pembentukan skema Model.
    Memvalidasi integritas Primary Key dan mendaftarkan kelas ke Registry.
    """
    def __new__(
        mcls, 
        name: str, 
        bases: Tuple[Type[Any], ...], 
        namespace: Dict[str, Any], 
        **kwargs: Any
    ) -> ModelMeta:
        # Jangan validasi kelas dasar 'Model' itu sendiri
        if not bases:
            return super().__new__(mcls, name, bases, namespace)

        # 1. Ekstrak dan isolasi semua Field descriptors
        fields: Dict[str, Field] = {}
        primary_keys: list[str] = []

        for key, value in list(namespace.items()):
            if isinstance(value, Field):
                fields[key] = value
                if value.primary_key:
                    primary_keys.append(key)

        # 2. Aturan Invarian: Harus memiliki tepat satu Primary Key
        if len(primary_keys) != 1:
            raise SyntaxError(
                f"Model '{name}' harus memiliki tepat satu Primary Key. "
                f"Ditemukan {len(primary_keys)}: {primary_keys}"
            )

        # 3. Ekstrak atau buat table_name otomatis
        custom_table = namespace.get("__table__")
        if custom_table:
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", custom_table):
                raise ValueError(f"Nama tabel '{custom_table}' tidak valid!")
            table_name = custom_table
        else:
            table_name = name.lower() + "s"

        # 4. Tambahkan metadata internal ke kelas
        namespace["_fields"] = fields
        namespace["_meta"] = {
            "table_name": table_name,
            "pk_name": primary_keys[0]
        }

        # 5. Bangun kelas secara nyata
        new_class = super().__new__(mcls, name, bases, namespace)

        # 6. Registrasi otomatis
        ModelRegistry.register(new_class)  # type: ignore[arg-type]

        return new_class


class Model(metaclass=ModelMeta):
    """Base class untuk domain logic entitas."""
    def __init__(self, **kwargs: Any) -> None:
        # Mengisi nilai default dan nilai input
        for field_name, field_obj in self._fields.items():
            if field_name in kwargs:
                setattr(self, field_name, kwargs[field_name])
            else:
                setattr(self, field_name, None)

    def to_dict(self) -> Dict[str, Any]:
        """Serialisasi model menjadi dict secara deterministik."""
        return {
            field_name: getattr(self, field_name)
            for field_name in self._fields
        }

    def __repr__(self) -> str:
        pk_field = self._meta["pk_name"]
        pk_val = getattr(self, pk_field, None)
        return f"<{self.__class__.__name__} {pk_field}={pk_val}>"


# --- Pembuktian Eksekusi Produksi ---

if __name__ == "__main__":
    class User(Model):
        __table__ = "app_users"
        
        id = IntegerField(primary_key=True)
        username = StringField(max_length=50)
        email = StringField(max_length=100)

    # 1. Uji Registrasi Otomatis & Metadata
    print("Models terdaftar:", ModelRegistry.get_models())
    assert "app_users" in ModelRegistry.get_models()

    # 2. Uji Instansiasi Valid
    user = User(id=1, username="admin_sys", email="admin@enterprise.internal")
    print(f"Instansiasi: {user}")
    print("Serialisasi:", user.to_dict())

    # 3. Uji Pelanggaran Aturan Invarian Primary Key
    try:
        class BrokenModel(Model):
            # Error: Tidak ada primary_key
            title = StringField()
    except SyntaxError as err:
        print(f"Tertangkap kegagalan validasi PK (Sesuai Desain): {err}")

    # 4. Uji Pelanggaran Tipe Data via Descriptor
    try:
        user.username = 12345  # Type mismatch
    except TypeError as err:
        print(f"Tertangkap validasi tipe runtime: {err}")

    # 5. Uji Batas Karakter
    try:
        user.username = "a" * 51  # Melebihi max_length=50
    except ValueError as err:
        print(f"Tertangkap validasi panjang string: {err}")
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Dalam merancang abstraksi tingkat lanjut, seorang software architect harus memilih teknik metaprogramming yang paling tepat:

| Metrik Pembanding | Metaclass (`type`) | PEP 487 (`__init_subclass__`) | Class Decorators | Monkey Patching |
| :--- | :--- | :--- | :--- | :--- |
| **Titik Intersepsi** | Paling awal: sebelum & saat pembuatan kelas | Pasca pembuatan kelas (inheritance lifecycle) | Pasca pembuatan kelas (instansiasi kelas selesai) | Runtime sembarang (Ad-hoc) |
| **Kontrol Namespace** | **Penuh** (dapat mengubah namespace via `__prepare__`) | **Nol** (namespace sudah menjadi mapping final) | **Nol** (namespace sudah final) | Parsial / Tidak terstruktur |
| **Keterbacaan Kode** | Sangat Rendah (Mental overhead tinggi) | Tinggi (Clean Pythonic OOP) | Tinggi (Eksplisit di atas kelas) | Sangat Buruk (Spaghetti) |
| **Risiko Konflik** | **Tinggi** (Metaclass Conflict saat Multiple Inheritance) | **Rendah** (Didukung native cooperative inheritance) | **Nol** (Independen antar dekorator) | Sangat Tinggi (Collision) |
| **Overhead Runtime** | Hanya saat *import-time* / startup | Hanya saat *import-time* / startup | Hanya saat *import-time* / startup | Rendah tetapi fluktuatif |
| **Kebutuhan Kasus** | Framework tingkat dalam (ORM, dynamic code generation) | Registrasi plugin, validasi konfigurasi turunan | Modifikasi wrapper method, penambahan mixin | Hot-patching darurat, Mocking testing |

### Rules of Thumb Pengambilan Keputusan:
1. **Gunakan Class Decorator:** Jika Anda hanya butuh membungkus method atau menambahkan metadata sederhana tanpa mengganggu hierarki pewarisan.
2. **Gunakan `__init_subclass__`:** Sebagai opsi *default* Anda jika ingin melakukan validasi kelas anak atau auto-registration.
3. **Gunakan Metaclass:** HANYA JIKA Anda wajib mengontrol pembuatan namespace (`__prepare__`), mengubah tuple kelas basis secara dinamis, atau membuat antarmuka tipe kustom yang tidak dapat dicapai melalui inheritance standar.

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Dreaded Metaclass Conflict
Jika Anda mencoba mewarisi dari dua kelas yang masing-masing memiliki metakelas independen yang berbeda:

```python
class MetaA(type): pass
class MetaB(type): pass

class BaseA(metaclass=MetaA): pass
class BaseB(metaclass=MetaB): pass

# Akan melempar: TypeError: metaclass conflict: the metaclass of a derived class
# must be a (weak) subclass of the metaclasses of all its bases
class Derived(BaseA, BaseB): pass
```

**Solusi Arsitektural:** Bentuk metakelas gabungan secara eksplisit.
```python
class CombinedMeta(MetaA, MetaB): pass

class Derived(BaseA, BaseB, metaclass=CombinedMeta): pass
```

### 2. Descriptor Memory Leaks dengan `WeakKeyDictionary`
Ketika membuat descriptor yang harus menyimpan state secara eksternal (tidak boleh menyentuh `instance.__dict__`), pengembang pemula sering menggunakan `dict` standar:

```python
# BAHAYA MEMORY LEAK!
class LeakyDescriptor:
    def __init__(self):
        self.values = {}  # instance -> value

    def __set__(self, instance, value):
        self.values[instance] = value  # Hard reference mencegah Garbage Collection instance!
```

**Solusi:** Gunakan `weakref.WeakKeyDictionary`:
```python
from weakref import WeakKeyDictionary

class SafeDescriptor:
    def __init__(self):
        self.values = WeakKeyDictionary()

    def __set__(self, instance, value):
        self.values[instance] = value  # Bebas memory leak saat instance out-of-scope
```

### 3. Rekursi Tanpa Batas pada `__getattr__` dan `__getattribute__`
`__getattribute__` dipanggil secara **inkondisional** untuk setiap akses atribut. Memanggil `self.attribute` di dalam `__getattribute__` memicu loop rekursi tak terbatas hingga terjadi `RecursionError`.
* **Solusi Wajib:** Panggil selalu implementasi kelas basis: `super().__getattribute__(name)`.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Mutasi Argumen pada `__new__` Tanpa Meneruskannya ke `__init__`
```python
# SALAH
class SubInt(int):
    def __new__(cls, val: int):
        return super().__new__(cls, abs(val))

    def __init__(self, val: int):
        # Python otomatis memanggil __init__ dengan argumen ASLI ('val')
        # Jika signature berbeda dengan __new__, TypeError terjadi.
        pass
```

### Kesalahan 2: Menyimpan Atribut Descriptor pada Level Descriptor Instans
```python
# SALAH FATAL (Shared State Bug)
class BadField:
    def __init__(self):
        self.val = None  # Variabel ini berada di INSTANS DESCRIPTOR (berbagi ke semua instans kelas!)

    def __get__(self, instance, owner):
        return self.val

    def __set__(self, instance, value):
        self.val = value

class User:
    age = BadField()

u1 = User()
u2 = User()
u1.age = 20
u2.age = 40
print(u1.age)  # Menghasilkan 40! State bocor antar instance!
```
* **Pencegahan:** Selalu simpan nilai di dalam instans target (`instance.__dict__`), atau gunakan `WeakKeyDictionary`.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Prinsip Tim Peters:** *"Metaclasses are deeper magic than 99% of users should ever worry about. If you wonder whether you need them, you don't."* Selalu eksplorasi `__init_subclass__` dan decorators sebelum memilih metaclass.
2. **Gunakan PEP 487 `__set_name__`:** Jangan melakukan hardcode nama atribut di dalam descriptor constructor. Serahkan pada Python untuk menginjeksi nama binding via `__set_name__`.
3. **Dokumentasikan Perubahan Dynamic Namespace:** Jika metakelas menginjeksi method secara otomatis ke dalam kelas, sediakan file `.pyi` (Stub File) agar LSP (*Language Server Protocol*) dan IDE dapat mendeteksi metode tersebut secara autocomplete.
4. **Bypass Method Resolution Saat Perlu Kecepatan Maksimum:** Hindari metaprogramming dinamis di dalam critical-path loop; gunakan fungsi terisolasi atau generator.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Benchmarking Descriptors vs Property vs Slot Access
CPython mengoptimalkan akses atribut berdasarkan lokasi penyimpanannya.

```python
import timeit

setup_code = """
class NormalObject:
    def __init__(self):
        self.x = 100

class SlottedObject:
    __slots__ = ('x',)
    def __init__(self):
        self.x = 100

class FastDescriptor:
    __slots__ = ('name',)
    def __init__(self, name):
        self.name = name
    def __get__(self, instance, owner):
        return instance.__dict__[self.name]
    def __set__(self, instance, value):
        instance.__dict__[self.name] = value

class DescriptorObject:
    x = FastDescriptor('x')
    def __init__(self):
        self.x = 100

normal = NormalObject()
slotted = SlottedObject()
desc = DescriptorObject()
"""

# Benchmark Waktu Akses Pembacaan (Read Latency)
t_normal = timeit.timeit("normal.x", setup=setup_code, number=10_000_000)
t_slotted = timeit.timeit("slotted.x", setup=setup_code, number=10_000_000)
t_desc = timeit.timeit("desc.x", setup=setup_code, number=10_000_000)

print(f"Normal Dict Lookup : {t_normal:.4f}s")
print(f"Slotted Member Descr: {t_slotted:.4f}s")
print(f"Custom Data Descr  : {t_desc:.4f}s")
```

### Analisis Hasil & Optimasi Memori:
1. `__slots__` secara konsisten ~20-30% lebih cepat daripada `__dict__` lookup reguler karena `MemberDescriptor` langsung melakukan C-level pointer arithmetic (`offset`), melompati tahapan hashing dict.
2. Descriptors membawa fungsi overhead (`Python function call overhead`), menjadikannya sedikit lebih lambat dari direct lookup, namun memberikan abstraksi validasi mutlak.
3. Untuk sistem high-throughput (pemrosesan jutaan event per detik), terapkan `__slots__` bersamaan dengan Descriptor yang dirancang ringkas.

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Mencegah Polusi Namespace:** Saat membangun metakelas yang menerima atribut arbitrary dari luar (seperti deserialisasi schema JSON), jangan pernah langsung memasukkannya tanpa validasi sanitasi regex:
   ```python
   def sanitize_field_name(name: str) -> None:
       if not name.isidentifier() or name.startswith("_"):
           raise SecurityError(f"Percobaan polusi nama field mencurigakan: '{name}'")
   ```
2. **Immutability Hardening via Descriptors:** Untuk mencegah modifikasi konfigurasi runtime security yang kritis, matikan method `__set__` secara permanen dengan melempar pengecualian:
   ```python
   class FrozenSecurityAttribute:
       def __init__(self, value: Any) -> None:
           self._value = value
       def __get__(self, instance: Any, owner: Type[Any]) -> Any:
           return self._value
       def __set__(self, instance: Any, value: Any) -> None:
           raise PermissionError("Modifikasi Security Context dilarang pada runtime!")
   ```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Metaprogramming dapat membuat *stack trace* menjadi ambigu karena kode dieksekusi secara implisit.

### Diagnostic Tracer untuk Class Construction
Gunakan decorator metaclass logging untuk mendeteksi pembentukan kelas selama fasa *import*:

```python
import logging
import sys

logging.basicConfig(level=logging.DEBUG, format="[METADEBUG] %(message)s")

class ObservableMeta(type):
    def __new__(mcls, name, bases, namespace, **kwargs):
        logging.debug(f"Mengalokasikan Kelas: {name} dengan bases: {bases}")
        return super().__new__(mcls, name, bases, namespace, **kwargs)

    def __init__(cls, name, bases, namespace, **kwargs):
        logging.debug(f"Inisialisasi Kelas Selesai: {name} (Attributes: {list(namespace.keys())})")
        super().__init__(name, bases, namespace, **kwargs)

    def __call__(cls, *args, **kwargs):
        logging.debug(f"Menginstansiasi Objek dari: {cls.__name__} dengan args={args}")
        instance = super().__call__(*args, **kwargs)
        logging.debug(f"Instansiasi Selesai untuk ID: {hex(id(instance))}")
        return instance
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### 1. Urutan Resolusi Atribut Python
1. Data Descriptor pada kelas (dan kelas basis MRO).
2. `instance.__dict__` (Namespace instans).
3. Non-Data Descriptor pada kelas (dan basis MRO).
4. Standard Class Attributes pada kelas (dan basis MRO).
5. `__getattr__` (Hanya dieksekusi jika langkah 1-4 gagal total).

### 2. Method Hook Pembuatan Kelas
```python
class Meta(type):
    @classmethod
    def __prepare__(mcls, name, bases, **kwargs):
        # 1. Mengembalikan dict-like object untuk menampung namespace
        return dict()

    def __new__(mcls, name, bases, namespace, **kwargs):
        # 2. Bertanggung jawab mengalokasikan memori objek kelas
        return super().__new__(mcls, name, bases, namespace)

    def __init__(cls, name, bases, namespace, **kwargs):
        # 3. Bertanggung jawab menginisialisasi kelas yang sudah dialokasikan
        super().__init__(name, bases, namespace)
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

**Q1: Apa perbedaan mendasar antara `__new__` dan `__init__` pada instansiasi objek Python?**  
*Jawaban:* `__new__` adalah static method (meskipun dideklarasikan tanpa `@staticmethod`) yang bertanggung jawab untuk *mengalokasikan memori* dan *mengembalikan objek instans baru*. Sedangkan `__init__` adalah method inisialisasi yang menerima objek yang sudah dibuat tersebut (`self`) untuk *mengisi atribut awal* dan tidak mengembalikan nilai apa pun (`None`).

**Q2: Mengapa metode biasa yang didefinisikan dalam sebuah kelas bertindak sebagai descriptor?**  
*Jawaban:* Karena fungsi Python mengimplementasikan protokol Non-Data Descriptor via method `__get__`. Ketika method diakses melalui instans (`inst.func`), method `__get__` pada objek fungsi mengembalikan *bound method* yang secara otomatis mengikat instans tersebut ke parameter pertama (`self`).

**Q3: Kapan kita harus mengembalikan `self` pada pemanggilan `__get__(self, instance, owner)`?**  
*Jawaban:* Saat parameter `instance` bernilai `None`. Ini menandakan bahwa akses dilakukan melalui level kelas (misal: `MyClass.my_field`), bukan melalui instans (`my_inst.my_field`).

**Q4: Apa yang dimaksud dengan C3 Linearization dalam Python?**  
*Jawaban:* Algoritma deterministik yang digunakan CPython untuk menghitung Method Resolution Order (MRO) pada hierarki *multiple inheritance*, memastikan prinsip *Local Precedence Order* dan *Monotonicity* terpenuhi tanpa ambiguitas.

**Q5: Mengapa Data Descriptor memiliki prioritas lookup yang lebih tinggi dibandingkan dictionary lokal `instance.__dict__`?**  
*Jawaban:* Desain CPython sengaja mengutamakan Data Descriptor (yang memiliki `__set__`) agar enkapsulasi dan aturan mutasi atribut yang didefinisikan pembuat kelas/library tidak dapat di-bypass atau di-shadow secara sengaja maupun tidak sengaja oleh penulisan langsung ke `instance.__dict__`.

---

### Soal Tingkat Menengah (Intermediate)

**Q6: Perhatikan kode berikut. Apa output pemanggilan `D.mro()`?**
```python
class O: pass
class F(O): pass
class E(O): pass
class D(O): pass
class C(D, F): pass
class B(E, D): pass
class A(B, C): pass
```
*Jawaban:*  
Hitung C3 Linearization:  
$L(D) = [D, O]$  
$L(E) = [E, O]$  
$L(F) = [F, O]$  
$L(B) = [B] + \text{merge}([E, O], [D, O], [E, D]) = [B, E, D, O]$  
$L(C) = [C] + \text{merge}([D, O], [F, O], [D, F]) = [C, D, F, O]$  
$L(A) = [A] + \text{merge}([B, E, D, O], [C, D, F, O], [B, C])$  
1. Ambil $B$: $[A, B] + \text{merge}([E, D, O], [C, D, F, O], [C])$  
2. Ambil $E$: $[A, B, E] + \text{merge}([D, O], [C, D, F, O], [C])$  
3. Periksa $D$: $D$ ada di tail list berikutnya (`[C, D, F, O]`), lewati!  
4. Ambil $C$: $[A, B, E, C] + \text{merge}([D, O], [D, F, O])$  
5. Ambil $D$: $[A, B, E, C, D] + \text{merge}([O], [F, O])$  
6. Periksa $O$: $O$ ada di tail list berikutnya (`[F, O]`), lewati!  
7. Ambil $F$: $[A, B, E, C, D, F] + \text{merge}([O], [O])$  
8. Ambil $O$: $[A, B, E, C, D, F, O]$  
MRO Akhir: `[A, B, E, C, D, F, O, object]`.

**Q7: Apa kelemahan spesifik penggunaan Metaclass yang diatasi oleh pengenalan `__init_subclass__` pada PEP 487?**  
*Jawaban:* Metaclass sering memicu *metaclass conflict* saat pewarisan ganda jika basis kelas menggunakan metaclass yang berbeda. `__init_subclass__` bekerja menggunakan mekanisme cooperative inheritance standar (`super()`), secara radikal menyederhanakan kustomisasi subkelas tanpa memerlukan instansiasi metakelas baru.

**Q8: Mengapa kode berikut menghasilkan `RecursionError`?**
```python
class RecursiveTrap:
    def __init__(self):
        self.data = {}
    def __setattr__(self, name, value):
        self.data[name] = value
```
*Jawaban:* Di dalam `__init__`, pernyataan `self.data = {}` mencoba menetapkan atribut `data`. Ini memanggil `__setattr__`. Di dalam `__setattr__`, pernyataan `self.data[name] = value` harus membaca `self.data` terlebih dahulu, dan jika penugasan atribut dilakukan, memanggil `__setattr__` kembali secara tak terbatas. Solusinya: gunakan `self.__dict__[name] = value` atau panggil `super().__setattr__(name, value)`.

**Q9: Apa perbedaan perilaku Non-Data Descriptor saat nilainya diakses langsung dibandingkan saat ditimpa via `instance.attr = val`?**  
*Jawaban:* Saat diakses, method `__get__` dieksekusi. Namun, karena tidak memiliki method `__set__`, penugasan `instance.attr = val` akan memasukkan nilai `val` secara langsung ke dalam `instance.__dict__['attr']`. Pada akses berikutnya, Python akan mengambil nilai dari `instance.__dict__` mendahului Non-Data Descriptor tersebut (*shadowing*).

**Q10: Bagaimana cara kerja `__prepare__` dalam Metaclass dan berikan satu use-case konkretnya?**  
*Jawaban:* `__prepare__` dieksekusi sebelum bodi kelas dievaluasi. Method ini mengembalikan sebuah mapping object. Seluruh definisi method dan variabel di bodi kelas kemudian dimasukkan ke mapping ini. *Use case:* Mengembalikan custom dict yang melempar error saat ada method yang didefinisikan dua kali (*prevent duplicate methods*) atau mengembalikan dictionary yang mencatat urutan deklarasi field skema basis data secara deterministik.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: Declarative Type-Enforced Configuration Engine

### Spesifikasi Kebutuhan Teknis:
Bangun sistem pembaca konfigurasi berbasis *Metaprogramming* dengan kriteria ketat berikut:
1. **Kelas Basis Deklaratif (`BaseConfig`):** Seluruh kelas konfigurasi turunan harus diinisialisasi melalui mapping dictionary atau *environment variables*.
2. **Validasi Strict Type Descriptors:**
   * Bangun descriptor `EnvVar(type, default=None, required=True)`.
   * Mendukung parsing otomatis dari string environment variable ke tipe target (`int`, `bool`, `str`, `float`).
   * Jika nilai tidak dapat di-parse atau `required=True` namun tidak ditemukan nilai input, lempar pengecualian kustom `ConfigValidationError`.
3. **Immutability Locking:**
   * Konfigurasi bersifat *Read-Only* setelah diinisialisasi.
   * Setiap upaya modifikasi atribut (`config.DATABASE_URL = "new"`) harus melempar `PermissionError`.
4. **Metaclass / `__init_subclass__` Enforcement:**
   * Semua nama konfigurasi (nama atribut) wajib berhuruf kapital penuh (*UPPERCASE*).
   * Jika subkelas mendefinisikan atribut berhuruf kecil (*lowercase*), proses class loading harus **gagal saat runtime deklarasi** dengan melempar `NameError`.

### Panduan Eksekusi:
* Tulis kode dalam satu modul terisolasi: `engine_config.py`.
* Hindari library eksternal (hanya gunakan Standard Library Python: `os`, `sys`, `typing`, `re`).
* Sertakan serangkaian test assertion di bagian bawah skrip untuk menguji:
  * Keberhasilan instansiasi dengan input valid.
  * Pelemparan `NameError` saat atribut lowercase dideklarasikan.
  * Pelemparan `PermissionError` saat instans dicoba diubah nilainya.
  * Penanganan nilai default parsing secara benar.