# BAB 02: Quiz, Challenge, & Knowledge Check
**Advanced Type System & Static Analysis**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Variansi dan Liskov Substitution Principle (LSP)
Dalam sistem tipe formal Python (PEP 484), jelaskan mengapa tipe kontainer generik yang *mutable* seperti `list[T]` harus bersifat **Invariant**, sedangkan tipe kontainer yang *immutable* seperti `Sequence[T]` dapat bersifat **Covariant** (`+T_co`). Berikan bukti berbasis pelanggaran *Liskov Substitution Principle* (LSP) yang akan terjadi pada *runtime heap memory* jika Python mengizinkan `list[Dog]` diperlakukan secara kovarian sebagai subtitusi dari `list[Animal]`.

### Soal 1.2: Nominal Subtyping vs Structural Subtyping
Bedakan arsitektur evaluasi tipe antara *Nominal Subtyping* (`abc.ABC` / inheritance konvensional) dan *Structural Subtyping* (`typing.Protocol` / PEP 544). Bagaimana *type checker* (seperti Mypy atau Pyright) memverifikasi kompatibilitas tipe pada level AST tanpa mengeksekusi kode, dan apa implikasi komputasional serta batasan runtime saat menggunakan decorator `@runtime_checkable` pada sebuah `Protocol`?

### Soal 1.3: Top Type, Bottom Type, dan Type Lattice Semantics
Gambarkan posisi semantik dari `object`, `typing.Any`, dan `typing.Never` (atau `typing.NoReturn`) dalam *Type Lattice* (teori hierarki tipe) Python. Mengapa penggunaan `Any` mengaburkan batasan matematis sistem tipe (*gradual typing escape hatch*), sedangkan `object` mempertahankan *type-safety*? Berikan satu skenario konkret di mana *static type checker* secara otomatis menyimpulkan sebuah variabel bertipe `Never`.

### Soal 1.4: Evaluasi Tipe Runtime vs Statis: PEP 563 vs PEP 649
Jelaskan perubahan mendasar penanganan anotasi tipe dari PEP 563 (`from __future__ import annotations` / *stringized annotations*) menuju PEP 649 (*deferred evaluation via synthetic functions* pada Python 3.14). Mengapa pendekatan PEP 563 menimbulkan komplikasi fatal bagi library ekosistem yang bertumpu pada *runtime type reflection* (seperti Pydantic v1/v2, Cattrs, atau FastAPI dynamic dependency injection)?

### Soal 1.5: Signature Preservation pada Higher-Order Functions
Ketika membuat dekorator logging atau retry generik, mengapa anotasi tipe tradisional `Callable[..., Any]` merusak seluruh kemampuan *type inference* pada *call-site* fungsi target? Jelaskan bagaimana kombinasi `typing.ParamSpec` (PEP 612) dan `typing.Concatenate` bekerja secara mekanistik untuk mempertahankan dependensi parameter input (posisional, kata kunci, opsional) dan tipe kembalian (*return type*) dari fungsi yang dibungkus.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Soundness Divergence: `TypeGuard` vs `TypeIs`
Perhatikan kode berikut:
```python
from typing import TypeGuard, TypeIs

def is_str_guard(val: object) -> TypeGuard[str]:
    return isinstance(val, str)

def is_str_typeis(val: object) -> TypeIs[str]:
    return isinstance(val, str)
```
Secara teknis, jelaskan perbedaan semantik penyempitan tipe (*type narrowing*) antara PEP 647 (`TypeGuard`) dan PEP 742 (`TypeIs`) ketika diterapkan pada blok percabangan `else` (kondisi negatif). Mengapa `TypeGuard` dinilai *unsound* (tidak aman secara formal) untuk operasi penyempitan tipe komplementer pada tipe gabungan (*Union types*), dan bagaimana `TypeIs` menyelesaikan celah *type safety* tersebut?

### Soal 2.2: Overload Ordering and Ambiguity Resolution
Pada kode berikut yang menggunakan `@typing.overload`:
```python
from typing import overload

@overload
def process_data(data: list[int]) -> list[str]: ...
@overload
def process_data(data: Sequence[int]) -> Sequence[str]: ...

def process_data(data: Sequence[int]) -> Sequence[str]:
    return [str(x) for x in data]
```
Mengapa *order of definition* (urutan deklarasi) dari blok `@overload` sangat menentukan hasil inferensi pada static analysis? Apa yang akan terjadi jika urutan kedua overload di atas dibalik ketika sebuah argumen bertipe literal `list[int]` dioper ke `process_data`? Jelaskan bagaimana algoritma evaluasi Mypy/Pyright memilih signature yang cocok saat terjadi *overlapping types*.

### Soal 2.3: Recursive Type Aliases & Memory Explosion pada AST Parser
Diberikan recursive type alias untuk validasi arbitrary JSON payload:
```python
type JSONValue = str | int | float | bool | None | dict[str, "JSONValue"] | list["JSONValue"]
```
Bagaimana *type checker engine* memproses struktur pohon rekursif ini tanpa mengalami infinite recursion atau stack overflow saat menguraikan nested dictionary yang kompleks? Bagaimana tipe baru ini (menggunakan sintaks PEP 695 `type`) diisolasi dalam scope internal dibandingkan deklarasi lama `JSONValue = Union[...]`?

### Soal 2.4: Cyclic Dependency Breakdown via `TYPE_CHECKING` Guard
Dalam arsitektur domain-driven design, Entity `Order` membutuhkan type hint ke `Customer`, dan `Customer` membutuhkan type hint ke `list[Order]`. Jelaskan secara mendalam:
1. Apa yang terjadi pada level bytecode Python VM saat modul-modul ini saling mengimpor secara sirkular saat runtime tanpa mitigasi.
2. Bagaimana konstanta `typing.TYPE_CHECKING` dievaluasi oleh Python Interpreter saat *module load time* versus saat *static analysis pass*.
3. Masalah baru apa yang muncul jika modul tersebut menggunakan `pydantic` atau `get_type_hints()` tanpa penanganan namespace `typing.forwardref` yang tepat?

### Soal 2.5: Method Chaining Polymorphism via `typing.Self`
Sebelum diperkenalkannya `typing.Self` (PEP 673), developer menggunakan generic invariant `TypeVar` terikat (`T = TypeVar('T', bound='BaseBuilder')`) untuk memvalidasi *fluent builder pattern*.
1. Tunjukkan kelemahan arsitektur tipe jika builder turunan hanya mengembalikan instance kelas dasar (`BaseBuilder`) pada method chaining.
2. Analisis bagaimana `typing.Self` secara internal menyederhanakan inferensi subtype pada *derived class* tanpa perlu mendeklarasikan TypeVar eksplisit di tingkat kelas atau metode.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: CI Pipeline Timeout & Memory Exhaustion pada Monorepo Scale
Sebuah monorepo berskala *enterprise* dengan 2,5 juta baris kode Python (berisi lebih dari 15.000 modul) mengalami degradasi performa CI/CD ekstrem: eksekusi `mypy --strict` membutuhkan waktu 48 menit dan sering kali mengalami crash akibat `Out-Of-Memory (OOM) Killer` pada worker container dengan alokasi RAM 16 GB.

Setelah audit awal, ditemukan pola luas penggunaan *deep generic union types* bertingkat (`Union[A, Union[B, Union[C, ...]]]`), inferensi tipe implisit pada variabel global, serta penggunaan ekstensif library eksternal tanpa deklarasi *stub files* (`.pyi`) resmi, yang memaksa type checker melakukan *fallback* ke evaluasi AST yang tidak terbatas.

**Pertanyaan Diagnostik:**
1. Pendekatan arsitektural apa yang harus diambil untuk mengonfigurasi Mypy daemon (`dmypy`) dan modularisasi dependensi (*fine-grained cache*) guna menekan waktu eksekusi type checking inkremental?
2. Bagaimana Anda mendeteksi dan merestrukturisasi *type-level combinator explosion* (misalnya eksponensial union resolution) pada core types sistem untuk mengurangi footprint alokasi memori Mypy?
3. Rancang strategi integrasi *stub packages* (`types-*`) dan isolasi modul legacy menggunakan konfigurasi per-modul Mypy (`mypy.ini` overrides) agar tidak mengorbankan strictness kode baru.

---

### Skenario B: Silent Production Corruption Akibat Dynamic Serialization & Unchecked Casting
Platform pemrosesan pembayaran real-time mengonsumsi event JSON berkecepatan tinggi dari Apache Kafka menggunakan library worker kustom. Developer menggunakan `typing.cast()` secara agresif untuk memetakan payload mentah ke `TypedDict` domain internal:

```python
payload = json.loads(kafka_message.value)
event_data = cast(PaymentAuthorizedEvent, payload)
process_payment(event_data["account_id"], event_data["amount_cents"])
```

Di production, terjadi insiden finansial: event dari gateway pembayaran pihak ketiga mengalami perubahan skema minor di mana field `"amount_cents"` dikirimkan sebagai string format desimal `"1500.50"` alih-alih integer `150050`. Static analysis (`pyright`) lulus 100% tanpa warning karena `cast` menonaktifkan mekanisme type safety, namun runtime memproses data korup yang berakibat pada kegagalan perhitungan ledger dan database constraint rollback pada ribuan transaksi.

**Pertanyaan Diagnostik:**
1. Mengapa `typing.cast()` merupakan antipattern dalam boundary layer sistem I/O eksternal, dan apa dampak semantiknya terhadap eksekusi runtime CPython?
2. Rancang pola arsitektur *Zero-Cost/Low-Overhead Parsing Boundary* menggunakan kombinasi `TypeGuard`/`TypeIs`, `Protocol`, atau validation engine (seperti Pydantic v2 core berbasis Rust) untuk menggantikan ilusi tipe dari `cast()`.
3. Tunjukkan implementasi pengujian regresi tipe (*type-level testing*) menggunakan `pytest` dan `typing.assert_type` / `mypy testing API` untuk memastikan type narrowing pada event handler benar-benar memvalidasi dan membedakan tipe input eksternal yang *malformed*.

---

### Skenario C: Plugin Architecture Trade-Off: Metaprogramming vs Static Analysis
Divisi infrastruktur sedang mendesain ulang arsitektur Database Repository Layer untuk mendukung multi-tenancy. Dua arsitektur diusulkan:

*   **Proposal 1 (Dynamic Magic):** Menggunakan `__getattr__` dan metaprogramming dinamis (`type.__new__`) untuk secara otomatis menghasilkan query methods saat runtime berdasarkan konvensi nama (misal: `find_by_email_and_status()`). Keuntungan: *Boilerplate-free*, pembuatan fitur sangat cepat.
*   **Proposal 2 (Generic Protocol-Driven):** Menggunakan generic abstract protocols `Repository[TEntity, TKey]` yang diimplementasikan secara eksplisit dengan decorators dan stub interfaces (`.pyi`). Keuntungan: Full static validation, deterministic IDE auto-completion, refactoring tooling support.

Tim bisnis menolak Proposal 2 karena dianggap "menulis terlalu banyak kode redundan (*verbosity*)", sementara tim SRE mendukung Proposal 2 karena insiden production akibat salah ketik field di masa lalu.

**Pertanyaan Diagnostik:**
1. Bedah trade-off teknis antara kedua pendekatan tersebut dengan metrik: *Cycle Time*, *Mean Time To Detection (MTTD)* untuk runtime bug, *Static Analysis Performance*, dan *Developer Cognitive Load*.
2. Jika Proposal 1 tetap dipilih sebagian, bagaimana cara memitigasi hilangnya static analysis capabilities secara elegan menggunakan mekanisme Mypy Plugin API kustom atau integrasi file stub generator otomatis?
3. Rancang arsitektur kompromi berbasis PEP 695 / PEP 544 yang meminimalkan *verbosity* (mengeliminasi boilerplate berlebih) tanpa mengorbankan invariant static checking pada enterprise data pipeline tersebut.

---

## 4. Chapter Challenge

### Tantangan Praktis: Type-Safe Event Bus Engine dengan Static Narrowing & Metaprogramming Decoupling

#### Problem Statement
Dalam arsitektur micro-framework modular berkinerja tinggi, komponen-komponen independen saling berkomunikasi menggunakan Event Bus terpusat. Masalah klasik Python adalah hilangnya konteks tipe payload ketika event didistribusikan: subscriber sering kali menerima payload sebagai generic `dict` atau `Any`, yang memicu runtime error jika skema event berubah.

Anda ditugaskan membangun **Core Type-Safe In-Memory Event Bus Engine** yang menjamin keamanan tipe secara mutlak mulai dari registrasi subscriber, publikasi event, hingga eksekusi handler, tanpa mengorbankan decoupling arsitektur dan tanpa runtime overhead validasi yang berlebihan.

#### Requirements
1. **Strongly-Typed Domain Events:**
   * Definisikan generic base protocol/class untuk `Event` di mana setiap subclass mendefinisikan payload spesifik yang bersifat immutable.
2. **Generic Event Bus Subscription:**
   * Buat method `subscribe` yang mengikat `Event` spesifik dengan callable `EventHandler`.
   * Type checker **harus menolak** jika sebuah handler didaftarkan untuk event tipe $A$, namun fungsi handler tersebut memiliki type hint parameter yang menerima event tipe $B$.
3. **ParamSpec-Preserved Middleware:**
   * Implementasikan sistem interceptor/middleware (misal: transaction wrapper, execution timing) yang membungkus handler event menggunakan `ParamSpec` dan `Concatenate`. Middleware harus transparan secara tipe dan tidak boleh melenyapkan tipe argumen handler asli.
4. **Discriminator Type Narrowing Engine:**
   * Buat mekanisme dispatching yang menggunakan fungsi berbasis `TypeIs` (PEP 742) atau `TypeGuard` (PEP 647) untuk menyempitkan tipe payload heterogen yang masuk dari external queue (misalnya generic union of events) ke tipe event konkret sebelum diproses oleh handler yang sesuai.
5. **Strict Type-Level Tests:**
   * Sertakan serangkaian test assertion menggunakan `typing.assert_type` untuk membuktikan bahwa static type inference bekerja presisi pada skenario passing dan failing.

#### Constraints
* **Runtime:** Python 3.12+ (Wajib memanfaatkan native generics syntax PEP 695 jika relevan).
* **Strict Typing:** Kode harus lulus validasi `mypy --strict` dan `pyright --level error` dengan zero warnings.
* **Prohibited Constructs:** Dilarang keras menggunakan `typing.Any`, `type: ignore`, `cast()`, atau `getattr()` dinamis tanpa type boundary.
* **Overhead Constraint:** Jalur eksekusi dispatch utama tidak boleh melakukan parsing schema serialisasi yang mahal (seperti re-validasi runtime Pydantic penuh) jika event object sudah terinstansiasi di memori.

#### Expected Output
Implementasi source code lengkap dalam satu file mandiri (`event_bus.py`) yang mencakup:
* Konstruk tipe generik (`Event`, `Payload`, `EventHandler`).
* Implementasi `EventBus` class dengan container thread-safe internal registry.
* Contoh implementasi event konkret (`OrderPlaced`, `UserBanned`).
* Type-level test assertions yang memvalidasi bahwa compiler/static checker mendeteksi type mismatch pada saat proses type checking statis dijalankan.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Aturan matematis variansi: Kapan harus mendesain tipe sebagai Covariant (`+T_co`), Contravariant (`-T_contra`), atau Invariant (`T`).
- [ ] Perbedaan internal antara `typing.TypeGuard` (PEP 647) dan `typing.TypeIs` (PEP 742) dalam kaitannya dengan narrowability pada cabang branch negatif (`else`).
- [ ] Mekanisme resolusi type signature pada `@typing.overload` dan batasan implementasi runtime-nya.
- [ ] Dampak arsitektural dari deferred type evaluation (PEP 563 vs PEP 649) terhadap ekosistem framework Python modern.
- [ ] Anatomi Type Lattice Python: Peran fungsional `object` sebagai Top Type, `Never`/`NoReturn` sebagai Bottom Type, dan `Any` sebagai bypass gradual typing.
- [ ] Cara kerja `typing.ParamSpec` dan `typing.Concatenate` dalam merepresentasikan signature fungsi arbitrer pada higher-order constructs.

### Saya tidak perlu menghafal:
- [ ] Kode numerik atau pesan teks error Mypy/Pyright secara spesifik (misal: `[arg-type]`, `reportGeneralTypeIssues`).
- [ ] Implementasi internal C-extension dari library static analyzer pihak ketiga (misal: arsitektur Rust di balik Ruff atau Pytype internals).
- [ ] Seluruh mapping tipe legacy Python 3.8 ke bawah (`typing.List`, `typing.Dict`, `typing.Tuple` vs native types `list`, `dict`, `tuple`).

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi dan mengoptimasi pipeline static analysis (`mypy.ini` / `pyrightconfig.json`) berskala jutaan baris kode agar terbebas dari OOM dan degradasi CI time.
- [ ] Merefaktor kode legacy yang bergantung pada dynamic duck-typing menjadi `typing.Protocol` yang aman secara statis dan dapat diverifikasi via static analysis.
- [ ] Membangun generic abstraction kompleks (seperti Repository, Service Bus, Command Handler) menggunakan modern generics syntax (PEP 695) yang lolos standardisasi `mypy --strict`.
- [ ] Menghilangkan penggunaan `cast()` dan `type: ignore` dari codebase enterprise dengan menggantinya menggunakan dynamic type-narrowing constructs yang valid.
- [ ] Menulis type-level unit tests menggunakan `typing.assert_type` untuk memverifikasi kontrak antarmuka API publik pada library atau micro-framework internal.