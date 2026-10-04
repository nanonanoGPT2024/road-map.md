# MODUL AJAR: OBJECT-ORIENTED DESIGN MODERN (C++20)

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum**: Pemrograman Sistem & Bahasa Tingkat Tinggi (C++)
* **Kategori**: 02-Programming-Languages
* **Bab**: 03 — Paradigma Berorientasi Objek & Generik
* **Modul**: 01 — Object-Oriented Design Modern
* **Tingkat Kesulitan**: Tingkat Lanjut (Advanced)
* **Prasyarat**: 
  * Pemahaman mendalam tentang manajemen memori C++ (*stack* vs *heap*, *raw pointers*, referensi).
  * Semantik pemindahan C++11/14/17 (*Move Semantics*, *Rvalue References*, *Rule of Five*).
  * Penguasaan dasar *Templates* dan tipe utilitas C++ standar (`std::unique_ptr`, `std::shared_ptr`).
* **Toolchain Rekomendasi**:
  * Kompilator: Clang 16.0+ atau GCC 13.0+ (Mendukung penuh standar C++20/C++23)
  * Sistem Build: CMake 3.25+
  * Alat Analisis: Clang-Tidy, Clang-Format, Valgrind / LLVM AddressSanitizer (ASan), UndefinedBehaviorSanitizer (UBSan)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Mengevaluasi & Menganalisis Biaya Runtime**: Mengurai *overhead* dari *dynamic polymorphism* tradisional (*vtable lookup*, *indirection cache miss*, *inhibited inlining*) dan membandingkannya dengan pendekatan modern.
2. **Menguasai Semantik Nilai (*Value Semantics*) dalam OOP**: Mengabstraksikan antarmuka polimorfik tanpa memaksakan alokasi heap atau *pointer chasing*, menggunakan teknik *Type Erasure* modern.
3. **Menerapkan *Static Polymorphism***: Mengimplementasikan pola *Curiously Recurring Template Pattern* (CRTP) dan C++20 *Concepts* untuk mencapai polimorfisme pada fase kompilasi (*compile-time*) dengan nol *runtime overhead*.
4. **Mendesain Arsitektur Sistem dengan *Rule of Zero***: Membangun hierarki kelas yang aman secara memori (*exception-safe*) dengan meminimalisasi destruktor manual dan mengandalkan primitif RAII standar.
5. **Mencegah Antipola Klasik**: Menghindari *object slicing*, kebocoran memori virtual destructor, dan hierarki pewarisan yang terlalu dalam (*deep inheritance trees*) dengan memprioritaskan komposisi atas pewarisan.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Dari "Klasifikasi Ontologis" ke "Komposisi Perilaku"

Dalam Object-Oriented Programming (OOP) klasik ala C++ awal 1990-an (atau Java/C# awal), OOP dipandang sebagai model taksonomi dunia nyata:
$$\text{Animal} \rightarrow \text{Mammal} \rightarrow \text{Dog}$$
Pendekatan ini berfokus pada **identitas** dan **pewarisan struktural**, yang sering kali mengorbankan lokalitas memori (*cache locality*), mengaburkan kepemilikan memori (*ownership semantics*), dan memaksa alokasi dinamis via `new` dan *raw pointer*.

```
[Mental Model Klasik (Heap-Bound, Reference-Centric)]
Entity ---> Heap Allocation (new Derived) <--- Raw Pointer / Indirection (Polymorphic Slice Risk)

[Mental Model Modern C++ (Value-Oriented, Cache-Friendly)]
Value Object [ Concrete Data + RAII Ownership ] ===(Concept/Constraint)===> Inlined Operations
```

C++ Modern mendefinisikan ulang OOP melalui prinsip berikut:
1. **Objek adalah Pemilik Sumber Daya (*Resource Owners*)**: Setiap objek bertanggung jawab penuh atas masa hidup (*lifetime*) sumber dayanya melalui idiom RAII (*Resource Acquisition Is Initialization*).
2. **Semantik Nilai di atas Semantik Referensi (*Value Semantics by Default*)**: Prioritaskan tipe data yang dapat disalin (*copyable*), dipindahkan (*movable*), dan dialokasikan pada *stack* secara deterministik.
3. **Pemisahan Antarmuka dan Implementasi tanpa Penalti Runtime**: Jika polimorfisme dapat diselesaikan pada saat kompilasi, gunakan *Templates* dan *Concepts*. Jika polimorfisme runtime mutlak dibutuhkan, bungkus di balik batas nilai (*Value-based Type Erasure*), bukan mengekspos *pointer* mentah ke seluruh sistem.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Dynamic Polymorphism Tradisional vs Static Polymorphism (CRTP)

```
DYNAMIC DISPATCH (Virtual Table Mechanism)
========================================================================
Stack Frame                  Heap Memory
+-----------------------+    +-----------------------------------------+
| Base* ptr             |--->| Derived Object                          |
+-----------------------+    | +-------------------------------------+ |
                             | | vptr (Virtual Pointer)              | |
                             | +-------------------------------------+ |
                             | | Member Variables                    | |
                             | +-------------------------------------+ |
                             +-------------------|---------------------+
                                                 |
                                                 v
                             VTABLE (Static Data Segment)
                             +-----------------------------------------+
                             | Type Info Pointer (RTTI)                |
                             | &Derived::virtual_method_1()            |
                             | &Derived::virtual_method_2()            |
                             +-----------------------------------------+

STATIC DISPATCH (CRTP / C++20 Concepts)
========================================================================
Stack Frame (No Heap, No Vptr Indirection)
+----------------------------------------------------------------------+
| Derived Object Instance                                              |
| +------------------------------------------------------------------+ |
| | Direct Member Variables                                          | |
| +------------------------------------------------------------------+ |
| Method call: ConcreteClass::method() -> Inlined straight by compiler |
+----------------------------------------------------------------------+
```

### 2. Alur Eksekusi Polimorfisme Runtime vs Fase Kompilasi

```
DYNAMIC (Virtual Call)       STATIC (CRTP/Concepts)
      [ Caller ]                  [ Caller ]
          │                           │
          ▼ Direct Pointer            ▼ Direct Call
     (Load vptr)               (Compile-time Resolution)
          │                           │
          ▼ Offset Lookup             ▼ Inlined Assembly
     (Load Func Addr)          [ Target Function Body ]
          │                     (Zero branch penalty)
          ▼ Indirect Branch
   [ Target Function ]
(Branch mispredict risk)
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Layout Memori Objek Polimorfik (*ABI Breakdown*)

Ketika sebuah kelas di C++ mendeklarasikan setidaknya satu metode `virtual`, kompilator (misalnya System V AMD64 ABI pada Linux atau MSVC x64 ABI pada Windows) mengubah tata letak memori (*layout*) objek tersebut:

1. **Virtual Table Pointer (`vptr`)**:
   * Kompilator menyisipkan pointer tak terlihat (biasanya sebesar 8 byte pada arsitektur 64-bit) pada *offset 0* dari objek.
   * `vptr` mengarah ke tabel fungsi global hanya-baca (*read-only data segment* `.rodata`) yang disebut `vtable`.
2. **Virtual Table (`vtable`)**:
   * Array dari function pointer yang mengarah ke implementasi terkonkret dari masing-masing fungsi virtual.
   * Menyimpan metadata RTTI (*Run-Time Type Information*) pada offset negatif relatif terhadap *vtable entry point*.
3. **Thunk Functions & Multiple Inheritance**:
   * Jika kelas mewarisi lebih dari satu kelas dasar virtual, kompilator membuat tabel sekunder dan menyisipkan *adjustment thunk* (potongan assembly kecil) untuk menyesuaikan nilai pointer `this` (menambah atau mengurangi offset byte) sebelum melompat ke metode kelas turunan.

```
Layout Kelas Tunggal Polimorfik (Ukuran: 16 Byte pada Platform 64-bit):
Offset (Byte)   Ukuran   Deskripsi
+---------------+--------+------------------------------------------------+
| 0x00 - 0x07   | 8 byte | vptr (Pointer ke vtable Derived)               |
| 0x08 - 0x0B   | 4 byte | int m_id (Member data)                         |
| 0x0C - 0x0F   | 4 byte | Padding compiler (Penyelarasan batas 8-byte)   |
+---------------+--------+------------------------------------------------+
```

### Penalti Kinerja dari Virtual Dispatch

* **Indirection Overhead**: Pemanggilan metode virtual membutuhkan minimal dua *load* dereferensi:
  1. `load %rax, [this]` (memuat alamat vtable dari objek).
  2. `call [rax + offset]` (memuat alamat fungsi dan memanggilnya).
* **Penghambatan Optimasi Inlining**: Kompilator tidak dapat melakukan *function inlining* secara agresif terhadap pemanggilan tidak langsung (*indirect call*), kecuali jika kompilator dapat membuktikan tipe objek secara statis melalui *devirtualization*.
* **Penalti Branch Target Buffer (BTB)**: CPU modern mengandalkan prediktor cabang (*branch predictor*) untuk berspekulasi. Pemanggilan virtual via function pointer dinamis sering kali menghasilkan *BTB miss*, yang menyebabkan *pipeline stall* (terbuang 10-20 siklus CPU per panggilan yang salah prediksi).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Prinsip SOLID dalam Konteks C++ Modern

Prinsip SOLID klasik sering disalahartikan sebagai dorongan untuk membuat hierarki antarmuka berbasis pointer yang sangat dalam. C++ modern menerapkannya secara berbeda:

* **Single Responsibility Principle (SRP)**: Gunakan RAII wrapper. Sebuah kelas memegang satu sumber daya (koneksi database, socket, buffer memori), bukan mencampur logika domain dengan alokasi memori manual.
* **Open/Closed Principle (OCP)**: Dicapai bukan hanya lewat pewarisan hierarkis, melainkan melalui *Templates*, *Policy-Based Design*, dan *Type Erasure*. Sistem terbuka untuk penambahan tipe baru tanpa mengubah kode inti, tanpa dependensi pointer dasar.
* **Liskov Substitution Principle (LSP)**: Diperkuat oleh kontrak static via C++20 *Concepts*. Jika tipe `T` harus mensimulasikan `Reader`, pemenuhan kontrak diverifikasi pada waktu kompilasi, bukan crash pada waktu runtime akibat metode yang melempar exception `NotImplemented`.
* **Interface Segregation Principle (ISP)**: Gunakan *Mixin Classes* atau *Concepts* granular ketimbang antarmuka raksasa dengan lusinan metode virtual murni (`pure virtual`).
* **Dependency Inversion Principle (DIP)**: Modul tingkat tinggi tidak bergantung pada modul tingkat rendah secara langsung; keduanya bergantung pada abstraksi (antarmuka C++ murni atau batasan *concept*).

### 2. Aturan Tiga, Lima, dan Nol (*Rule of Zero/Three/Five*)

* **Rule of Zero**: Kelas yang tidak mengelola sumber daya secara langsung **tidak boleh** mendeklarasikan salah satu dari: destruktor, copy constructor, copy assignment operator, move constructor, atau move assignment operator. Gunakan tipe standar RAII (`std::string`, `std::vector`, `std::unique_ptr`).
* **Rule of Five**: Jika Anda mengelola sumber daya sistem mentah (*raw OS handle*, *custom pointer*), implementasikan kelima fungsi khusus tersebut secara eksplisit untuk menjamin keamanan pengecualian dan semantik pemindahan.
* **Virtual Destructor Mandate**: Jika sebuah kelas dirancang untuk dihapus secara polimorfik melalui pointer kelas dasar (misal `std::unique_ptr<Base>`), destruktor kelas dasar **wajib** dideklarasikan `virtual`:
  ```cpp
  virtual ~Base() = default;
  ```
  Kegagalan melakukan hal ini memicu **Undefined Behavior (UB)** saat `delete ptr` dipanggil karena destruktor kelas turunan tidak akan dieksekusi.

### 3. Type Erasure: Menjembatani Semantik Nilai & Polimorfisme

*Type Erasure* adalah teknik di mana kita mempertahankan keuntungan polimorfisme runtime (menyimpan koleksi heterogen dari tipe yang berbeda dalam satu kontainer) sambil mempertahankan manfaat semantik nilai (*copyable*, *movable*, alokasi stack tanpa kebocoran pointer mentah). Pendekatan ini adalah fondasi dari implementasi `std::function`, `std::any`, dan `std::move_only_function` (C++23).

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi perbandingan antara **Dynamic Polymorphism Tradisional** versus **Static Polymorphism via CRTP & C++20 Concepts**.

```cpp
#include <iostream>
#include <memory>
#include <vector>
#include <chrono>
#include <concepts>

// ============================================================================
// PENDEKATAN 1: MODERN RUNTIME DYNAMIC POLYMORPHISM
// Menggunakan virtual, smart pointers, override, dan final
// ============================================================================

class IRenderable {
public:
    virtual ~IRenderable() = default; // Rule of Zero/Five: Destruktor virtual wajib
    virtual void render() const = 0;   // Pure virtual interface
};

class ModernWidget : public IRenderable {
private:
    std::string m_name;

public:
    explicit ModernWidget(std::string name) : m_name(std::move(name)) {}

    // Dianotasi override untuk verifikasi compiler dan final jika tidak diturunkan lagi
    void render() const override final {
        std::cout << "[Dynamic] Rendering Widget: " << m_name << '\n';
    }
};

// ============================================================================
// PENDEKATAN 2: STATIC POLYMORPHISM DENGAN CRTP & C++20 CONCEPTS
// Nol runtime overhead, tidak ada vtable, inlining penuh dijamin oleh compiler
// ============================================================================

template <typename Derived>
class CRTPRenderer {
public:
    void draw() const {
        // Melakukan static cast this ke derived type untuk resolusi compile-time
        static_cast<const Derived*>(this)->draw_impl();
    }
};

class FastWidget : public CRTPRenderer<FastWidget> {
private:
    std::string m_name;

public:
    explicit FastWidget(std::string name) : m_name(std::move(name)) {}

    // Diimplementasikan secara langsung tanpa override vtable
    void draw_impl() const {
        std::cout << "[CRTP] Fast Drawing: " << m_name << '\n';
    }
};

// Validasi C++20 Concept untuk memvalidasi kontrak tanpa inheritance sama sekali
template <typename T>
concept DrawableConcept = requires(T t) {
    { t.draw_impl() } -> std::same_as<void>;
};

template <DrawableConcept T>
void execute_draw(const T& element) {
    element.draw_impl(); // Static dispatch langsung
}

// ============================================================================
// MAIN DRIVER
// ============================================================================
int main() {
    // 1. Uji Pendekatan Dinamis (Safe Dynamic Dispatch via std::unique_ptr)
    std::vector<std::unique_ptr<IRenderable>> dynamic_scene;
    dynamic_scene.push_back(std::make_unique<ModernWidget>("Panel-A"));
    dynamic_scene.push_back(std::make_unique<ModernWidget>("Dialog-B"));

    for (const auto& item : dynamic_scene) {
        item->render(); // Melalui vtable lookup
    }

    // 2. Uji Pendekatan Statis (Compile-time resolution, Zero Overhead)
    FastWidget static_widget("HighPerformance-Viewport");
    static_widget.draw(); // Di-inline langsung tanpa vptr

    // 3. Uji via C++20 Concepts
    execute_draw(static_widget);

    return 0;
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Mendalam Implementasi di Atas

1. `virtual ~IRenderable() = default;` (Baris 13):
   * **Mekanisme**: Menugaskan kompilator untuk menghasilkan implementasi destruktor default, namun menandainya sebagai slot virtual di `vtable`.
   * **Pencegahan**: Menghindari perilaku *undefined behavior* ketika instansi `ModernWidget` dialokasikan di heap dan dihancurkan melalui referensi atau pointer bertipe `IRenderable*`.
2. `void render() const override final` (Baris 24):
   * **Kata Kunci `override`**: Menginstruksikan kompilator untuk memverifikasi kecocokan tanda tangan fungsi persis dengan metode di kelas dasar. Mencegah bug senyap akibat *signature mismatch* (misalnya lupa qualifier `const`).
   * **Kata Kunci `final`**: Memberitahu optimizer kompilator bahwa kelas/metode ini tidak akan di-override lagi. Hal ini memungkinkan kompilator melakukan **Devirtualization**, mengubah *indirect virtual call* menjadi *direct function call* jika tipe konkret diketahui pada unit kompilasi tersebut.
3. `template <typename Derived> class CRTPRenderer` (Baris 34):
   * **Mekanisme CRTP**: Kelas dasar meminjam tipe kelas turunan sebagai parameter template. Melalui `static_cast<const Derived*>(this)`, pengalihan pemanggilan fungsi dilakukan pada fase analisis AST (*Abstract Syntax Tree*) oleh kompilator.
   * **Konsekuensi Assembly**: Tidak ada alokasi `vptr` sebesar 8 byte per instansi. Ukuran `sizeof(FastWidget)` identik dengan ukuran data anggotanya saja (`sizeof(std::string)`).
4. `template <typename T> concept DrawableConcept` (Baris 53-55):
   * **Sintaks C++20**: Mengevaluasi kemampuan struktural (*duck typing* yang divalidasi secara statis). Memastikan bahwa setiap tipe `T` yang diproses memiliki fungsi anggota `draw_impl()` yang mengembalikan `void`. Jika tidak terpenuhi, kompilator mengeluarkan pesan error diagnostik yang komprehensif, bukan error template yang sulit dibaca (*SFINAE failure cascades*).

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Sistem Pemrosesan Pesanan Perdagangan Frekuensi Tinggi (*Ultra-Low Latency Trading Engine*)

**Deskripsi Masalah**:
Sebuah institusi perdagangan kuantitatif membutuhkan mesin perutean eksekusi order (*Execution Order Router*) yang harus memproses ratusan juta pesan per detik dari protokol bursa yang berbeda-beda (misalnya: FIX Protocol, OUCH Protocol, dan Binary ITCH Protocol). 

**Tantangan Sistem**:
1. Menggunakan hierarki polimorfisme kelas dasar virtual murni (`class BaseOrderProcessor`) menyebabkan lonjakan latensi persentil P99.9 akibat *vtable pointer chasing* dan kegagalan kompilator melakukan *instruction pipeline optimization*.
2. Menggunakan template biasa tanpa abstraksi tipe menciptakan polusi dependensi (*code bloat*) dan membuat antarmuka koleksi heterogen tidak dapat disimpan dalam struktur *contiguous memory buffer* (seperti `std::vector`).

**Solusi Arsitektur Modern**:
Menerapkan teknik **Value-Based Type Erasure Pattern**. Pola ini membungkus variasi tipe konkret dalam sebuah wrapper bernilai (*value semantics*) yang mengalokasikan memori dalam batas buffer kecil internal (*Small Buffer Optimization - SBO*), menghindari alokasi heap baru, serta mengeliminasi kebocoran pointer mentah secara deterministik.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi sistem pemrosesan pesan bursa heterogen menggunakan prinsip **Modern C++ Type Erasure** dengan semantik nilai penuh (*Value Semantics*).

```cpp
#include <iostream>
#include <memory>
#include <string>
#include <vector>
#include <utility>
#include <array>
#include <cstdint>

// ============================================================================
// DOMAIN STRUCTS: Protokol-Protokol Berbeda (Tipe Konkret Independen)
// Perhatikan: Tipe-tipe ini TIDAK mewarisi kelas dasar yang sama!
// ============================================================================

struct FixOrder {
    uint64_t order_id;
    double price;
    uint32_t quantity;

    void process_execution() const {
        std::cout << "[FIX 4.4] Routing Order ID: " << order_id 
                  << " | Prc: " << price << " | Qty: " << quantity << '\n';
    }
};

struct OuchOrder {
    const char* token;
    uint32_t shares;

    void process_execution() const {
        std::cout << "[OUCH Protocol] Fast-Ack Token: " << token 
                  << " | Shares: " << shares << '\n';
    }
};

// ============================================================================
// MODERN TYPE ERASURE WRAPPER: OrderDispatcher
// Bertindak sebagai Value Object yang menyembunyikan detail tipe konkret
// ============================================================================

class OrderDispatcher {
private:
    // 1. Antarmuka Konsep Internal (Abstract Base)
    struct ExecutionConcept {
        virtual ~ExecutionConcept() = default;
        virtual void execute() const = 0;
        virtual std::unique_ptr<ExecutionConcept> clone() const = 0;
    };

    // 2. Model Generik Internal (Menjembatani Tipe Asli dengan Konsep)
    template <typename ConcreteOrderType>
    struct ExecutionModel final : public ExecutionConcept {
        ConcreteOrderType m_data;

        explicit ExecutionModel(ConcreteOrderType data) : m_data(std::move(data)) {}

        void execute() const override {
            m_data.process_execution();
        }

        std::unique_ptr<ExecutionConcept> clone() const override {
            return std::make_unique<ExecutionModel<ConcreteOrderType>>(*this);
        }
    };

    // Storage: Pointer ke antarmuka tersembunyi
    std::unique_ptr<ExecutionConcept> m_concept;

public:
    // Konstruktor Universal: Menerima tipe APA SAJA yang memiliki method process_execution()
    template <typename T>
    OrderDispatcher(T order) 
        : m_concept(std::make_unique<ExecutionModel<T>>(std::move(order))) {}

    // Aturan Lima (Rule of Five) untuk Memastikan Semantik Nilai
    ~OrderDispatcher() = default;
    
    // Copy Constructor: Polimorfisme Deep Copy
    OrderDispatcher(const OrderDispatcher& other) 
        : m_concept(other.m_concept ? other.m_concept->clone() : nullptr) {}

    // Copy Assignment Operator
    OrderDispatcher& operator=(const OrderDispatcher& other) {
        if (this != &other) {
            OrderDispatcher temp(other);
            std::swap(m_concept, temp.m_concept);
        }
        return *this;
    }

    // Move Operations (Default via std::unique_ptr)
    OrderDispatcher(OrderDispatcher&&) noexcept = default;
    OrderDispatcher& operator=(OrderDispatcher&&) noexcept = default;

    // Dispatcher API Utama: Pemanggilan Polimorfik
    void dispatch() const {
        if (m_concept) {
            m_concept->execute();
        }
    }
};

// ============================================================================
// SIMULASI PIPELINE EKSEKUSI
// ============================================================================

int main() {
    // Koleksi nilai heterogen tanpa raw pointers atau deklarasi pointer eksternal
    std::vector<OrderDispatcher> order_queue;

    // Memasukkan tipe konkret yang sama sekali berbeda ke dalam satu kontainer bernilai
    order_queue.emplace_back(FixOrder{10098234, 150.25, 500});
    order_queue.emplace_back(OuchOrder{"NASDAQ-ALPHA-09", 1200});
    order_queue.emplace_back(FixOrder{10098235, 3050.00, 50});

    std::cout << "--- MEMULAI PENGIRIMAN ORDER BATCH --- \n";
    for (const auto& order : order_queue) {
        // Pemanggilan terlihat seperti nilai murni, polimorfisme terjadi di dalam
        order.dispatch();
    }

    // Pembuktian Semantik Nilai (Copyable)
    std::cout << "\n--- MENGUJI SEMANTIK NILAI (COPY) --- \n";
    OrderDispatcher single_order = order_queue[1]; // Salinan penuh, bukan pointer sharing
    single_order.dispatch();

    return 0;
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Di bawah ini adalah perbandingan komprehensif antara tiga paradigma polimorfisme utama dalam C++ Modern:

| Metrik Evaluasi | Dynamic Polymorphism (Klasik) | Static Polymorphism (CRTP / Concepts) | Modern Type Erasure |
| :--- | :--- | :--- | :--- |
| **Beban Runtime Indirection** | **Tinggi**: 1-2 indirection dereferensi memori via `vtable`. | **Nol**: Direct call atau full inlining pada assembly. | **Sedang**: 1 indirection internal terisolasi. |
| **Overhead Ukuran Objek** | Bertambah 8 byte (`vptr`) per instansi. | **Nol**: Tidak ada data tersembunyi yang disisipkan. | Ukuran pointer wrapper (`sizeof(unique_ptr)`). |
| **Koleksi Heterogen** | **Bisa**: Memerlukan container of pointers (`vector<Base*>`). | **Mustahil**: Harus menggunakan tipe seragam atau `std::variant`. | **Bisa Penuh**: Menggunakan semantik nilai (`vector<ValueType>`). |
| **Lokalisasi Cache Memori** | **Buruk**: Elemen tersebar di berbagai heap allocation. | **Sangat Baik**: Buffer memori berkelanjutan (*contiguous*). | **Baik**: Kontainer flat, alokasi memori internal terkontrol. |
| **Waktu Kompilasi** | Cepat. | **Lambat**: Ledakan instansiasi kode template (*code bloat*). | Menengah. |
| **Batasan Ekstensi** | Hirarki tertutup (*Intrusive*): Kelas turunan harus mewarisi kelas dasar. | *Non-intrusive* via Concept, *Intrusive* via CRTP. | **Non-intrusive**: Kelas domain tidak perlu tahu pembungkusnya. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Object Slicing saat Melewatkan Parameter Berdasarkan Nilai
Jika fungsi menerima kelas dasar berdasarkan nilai (*pass-by-value*), bukan referensi atau pointer pintar, kompilator hanya menyalin bagian basis dari objek turunan:

```cpp
class Base { public: int x; virtual void run() {} };
class Derived : public Base { public: int y; void run() override {} };

void process(Base b) { // BAHAYA: Object Slicing!
    b.run(); // Selalu mengeksekusi Base::run(), data member 'y' terpotong habis!
}

Derived d;
process(d); // d di-slice menjadi Base
```

*Solusi*: Gunakan *pass-by-reference-to-const* (`const Base&`) atau bungkus dalam semantik nilai modern seperti *Type Erasure*.

### 2. Memanggil Metode Virtual dari Konstruktor atau Destruktor
Di C++, memanggil metode virtual dari dalam konstruktor atau destruktor **tidak** memicu resolusi polimorfik kelas turunan:

```cpp
class AbstractBase {
public:
    AbstractBase() { init(); } // BUG KRITIS
    virtual void init() = 0;
};
```

*Penyebab*: Saat konstruktor `AbstractBase` berjalan, sub-objek kelas turunan belum dibentuk (`vptr` saat itu masih menunjuk ke `vtable` milik `AbstractBase`). Memanggil metode pure virtual memicu pemanggilan instruksi `__cxa_pure_virtual`, yang berujung pada penghentian paksa aplikasi (*abrupt crash* via `std::terminate`).

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Penggunaan `std::shared_ptr` Tanpa Alasan yang Jelas
* **Kesalahan**: Menggunakan `std::shared_ptr` secara membabi buta sebagai pengganti pointer biasa karena menghindari manajemen memori manual.
* **Biaya**: `std::shared_ptr` mengalokasikan *control block* di heap dan menggunakan operasi atomik (*atomic increment/decrement*) untuk pemeliharaan *reference count*, yang sangat lambat pada arsitektur multi-core (karena terjadinya *cache-coherency bus-locking*).
* **Solusi**: Gunakan `std::unique_ptr` secara *default* untuk kepemilikan tunggal. Gunakan referensi mentah (`T&`) atau pengamat pointer (`T*`) jika fungsi hanya meminjam (*observing*) objek tanpa mengatur masa hidupnya.

### 2. Menghilangkan `virtual` pada Destruktor Kelas Polimorfik
* **Kesalahan**: Mendeklarasikan kelas dengan metode virtual tetapi lupa mendefinisikan destruktor virtual.
* **Dampak**: 
  ```cpp
  Base* obj = new Derived();
  delete obj; // Hanya memanggil ~Base(), memori/sumber daya pada Derived bocor seketika!
  ```
* **Solusi**: Jalankan analisis statis dengan Clang-Tidy mengaktifkan aturan `-Wnon-virtual-dtor`.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Prioritaskan Komposisi atas Pewarisan (*Composition over Inheritance*)**:
   Jangan gunakan pewarisan untuk berbagi kode logika murni. Gunakan pewarisan hanya untuk memodelkan hubungan substitusi antarmuka polimorfik sejati. Jika hanya membutuhkan fungsi pembantu, gunakan agregasi objek atau fungsi bebas (*free functions*) dalam namespace terisolasi.
2. **Keluarkan Aturan Final Secara Defensif**:
   Tandai kelas turunan konkret sebagai `final` secara default, kecuali jika kelas tersebut memang dirancang secara sengaja untuk diturunkan kembali. Ini memberikan petunjuk optimasi kepada kompilator untuk melakukan devirtualisasi metode.
3. **Animasikan Antarmuka Menggunakan `std::span` dan `std::string_view`**:
   Hindari mendesain antarmuka publik yang mengikat struktur data ke kontainer tertentu (seperti `const std::vector<T>&`). Gunakan `std::span<const T>` untuk urutan data berkelanjutan, sehingga antarmuka dapat menerima array C, `std::array`, maupun `std::vector` tanpa alokasi memori tambahan.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Devirtualization via `final`

Perhatikan transformasi rakitan (*assembly*) oleh kompilator ketika kata kunci `final` digunakan secara tepat:

```cpp
class Base {
public:
    virtual int compute(int x) const = 0;
};

class Multiplier final : public Base {
public:
    int compute(int x) const override final {
        return x * 4;
    }
};

int direct_invoke(const Multiplier& m, int val) {
    return m.compute(val);
}
```

Jika tidak menggunakan `final`, kompilator terpaksa membuat instruksi dereferensi memori tak langsung:
```assembly
# Tanpa devirtualization (Dynamic Virtual Lookup)
mov    rax, QWORD PTR [rdi]        # rax = vptr
mov    rax, QWORD PTR [rax]        # rax = vtable[0]
jmp    rax                         # indirect jump (berisiko branch misprediction)
```

Dengan spesifikasi `final` dan tipe konkret yang diketahui:
```assembly
# Dengan devirtualization (Compiler mengenali tipe mutlak)
mov    eax, esi
shl    eax, 2                      # Langsung dieksekusi via inlined bitwise shift!
ret
```

Optimasi ini sepenuhnya menghilangkan pemanggilan pointer fungsi dan memungkinkan operasi di-inline secara penuh.

---

## SEKSI 16 — KEAMANAN & HARDENING

### Mitigasi Vptr Corruption & Virtual Table Injection

Penyusupan memori klasik pada bahasa C++ sering menargetkan penulisan ulang (*overwrite*) terhadap pointer `vptr` melalui *buffer overflow* di heap, mengarahkan aliran eksekusi program ke *shellcode* penyerang saat metode virtual dipanggil.

**Langkah-Langkah Pengerasan Sistem**:

1. **Clang Control Flow Integrity (CFI)**:
   Aktifkan flag keamanan pada kompilator Clang saat melakukan build produksi:
   ```bash
   clang++ -fsanitize=cfi -fvisibility=hidden -flto -O2 main.cpp -o secure_binary
   ```
   Flag ini menyisipkan kode validasi sebelum dereferensi `vptr` untuk memverifikasi bahwa alamat tujuan pemanggilan benar-benar terdaftar di tabel resolusi biner yang valid.
2. **Kompilasi dengan Deteksi Sanitizer**:
   Wajibkan unit test melewati LLVM UndefinedBehaviorSanitizer:
   ```bash
   clang++ -fsanitize=undefined,address -g main.cpp
   ```
   Hal ini mendeteksi degradasi *downcasting* yang tidak valid yang melibatkan `static_cast` yang keliru dari kelas dasar ke kelas turunan.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### Menginspeksi Vtable dan Layout Memori Menggunakan GDB dan Clang Flag

Untuk memverifikasi secara langsung bagaimana arsitektur kelas disusun oleh kompilator, gunakan alat diagnosa bawaan kompilator:

```bash
# Cetak layout biner kelas lengkap menggunakan Clang
clang++ -cc1 -fdump-record-layouts main.cpp
```

Output diagnostik akan menampilkan representasi matematis struktur data internal:
```text
*** Memory Layout
   0 | class ModernWidget
   0 |   class IRenderable (primary base)
   0 |     (IRenderable vtable pointer)
   8 |   class std::string m_name
  40 | [sizeof=40, dsize=40, align=8]
```

### Melacak Pemanggilan Virtual di GDB
Saat program terhenti di *breakpoint*:
```text
(gdb) print *obj
$1 = {_vptr.IRenderable = 0x555555557d30 <vtable for ModernWidget+16>, m_name = "Panel-A"}
(gdb) info vtbl obj
vtable for 'ModernWidget' at 0x555555557d30:
  [0]: 0x555555556210 <ModernWidget::render() const>
```
Perintah ini membuktikan bahwa slot memori pertama dari objek merupakan penunjuk eksklusif ke tabel fungsi virtual.

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```
+-----------------------------------------------------------------------------------+
|                           PANDUAN MODERN C++ OOP                                  |
+-----------------------------------------------------------------------------------+
| Kebutuhan Desain        | Solusi yang Direkomendasikan   | Hindari                |
+-------------------------+--------------------------------+------------------------+
| Polimorfisme Statis     | C++20 Concepts / CRTP          | Virtual Functions      |
| Koleksi Heterogen       | Value-based Type Erasure       | std::vector<Base*>     |
| Resource Management     | Idiom RAII (Rule of Zero)      | new / delete manual    |
| Kepemilikan Eksklusif   | std::unique_ptr<T>             | std::shared_ptr<T>     |
| Akses Pengamat (Borrow) | const T& atau T* (non-owning)  | Smart pointer ref copy |
| Hierarki Taksonomi      | std::variant / Flat Structs    | Deep Inheritance Tree  |
+-------------------------+--------------------------------+------------------------+
```

* **Rule of Zero**: Serahkan masa hidup data kepada tipe RAII standar.
* **Rule of Five**: Tulis lima fungsi khusus hanya jika Anda memegang handle sistem operasi atau pointer mentah secara langsung.
* **Virtual Destructor**: Wajib ada jika kelas tersebut memiliki fungsi virtual dan akan dihapus via pointer basis.
* **Final Keyword**: Gunakan untuk membantu devirtualisasi kompilator.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Tingkat Dasar (Basic)

1. **Apa yang terjadi pada memori objek jika kita menambahkan satu fungsi virtual ke dalam kelas yang sebelumnya hanya berisi satu variabel `int` (4 byte) pada sistem 64-bit?**
   * A. Ukuran objek tetap 4 byte.
   * B. Ukuran objek bertambah menjadi 8 byte.
   * C. Ukuran objek bertambah menjadi 16 byte (8 byte untuk `vptr` + 4 byte integer + 4 byte padding).
   * D. Ukuran objek berlipat ganda menjadi 32 byte.

2. **Kapan destruktor sebuah kelas dasar wajib dideklarasikan dengan kata kunci `virtual`?**
   * A. Pada setiap kelas tanpa terkecuali.
   * B. Hanya jika kelas tersebut diinstansiasi di stack.
   * C. Ketika kelas memiliki setidaknya satu fungsi virtual dan instansinya akan dihancurkan melalui pointer kelas dasar.
   * D. Ketika kelas tidak memiliki variabel anggota.

3. **Apa arti kata kunci `override` dalam deklarasi metode kelas turunan di C++ modern?**
   * A. Mengubah visibilitas fungsi dari private menjadi public.
   * B. Menginstruksikan kompilator untuk memastikan metode dengan tanda tangan yang sama persis ada di kelas dasar; jika tidak cocok, lemparkan error kompilasi.
   * C. Memaksa fungsi di-inline oleh linker.
   * D. Menimpa hak akses memori kernel.

4. **Apa yang dimaksud dengan fenomena *Object Slicing*?**
   * A. Mengompresi array agar memakan lebih sedikit memori.
   * B. Terpotongnya data anggota dan fungsionalitas unik kelas turunan saat di-assign atau di-pass by value ke instansi kelas dasar.
   * C. Pemisahan kode program ke dalam beberapa unit kompilasi biner.
   * D. Menghapus memori sebelum destruktor selesai dieksekusi.

5. **Prinsip *Rule of Zero* menganjurkan perancang sistem untuk:**
   * A. Tidak menulis kode sama sekali dan membiarkan AI menyusunnya.
   * B. Menghindari deklarasi destruktor dan operasi copy/move khusus dengan mengandalkan anggota kelas berbasis RAII.
   * C. Selalu menginisialisasi integer ke nilai nol.
   * D. Menghapus semua referensi pointer dalam aplikasi.

### Tingkat Menengah (Intermediate)

6. **Mengapa pemanggilan fungsi virtual dapat menurunkan performa eksekusi pada aplikasi intensif komputasi (*high-frequency execution*)?**
   * A. Karena fungsi virtual selalu dialokasikan di thread yang berbeda.
   * B. Karena kompilator harus mengenkripsi alamat fungsi.
   * C. Karena adanya dereferensi ganda (*double indirection*) dan hilangnya peluang inlining yang memicu potensi *Branch Target Buffer (BTB) miss*.
   * D. Karena instruksi virtual membatasi frekuensi clock CPU.

7. **Bagaimana pola CRTP (*Curiously Recurring Template Pattern*) menghasilkan polimorfisme tanpa alokasi vtable?**
   * A. Menggunakan thread terpisah untuk mengevaluasi tipe data.
   * B. Menyelesaikan pemanggilan fungsi secara statis pada fase kompilasi dengan melakukan `static_cast` dari base template ke derived class.
   * C. Menyimpan pointer fungsi ke dalam array static lokal.
   * D. Meminta bantuan kernel untuk merute eksekusi instruksi.

8. **Perhatikan cuplikan kode berikut:**
   ```cpp
   class Node {
       virtual void compute() final;
   };
   ```
   **Apa keuntungan teknis menyematkan `final` pada fungsi anggota virtual tersebut?**
   * A. Mencegah fungsi tersebut dipanggil oleh thread lain.
   * B. Mengizinkan kompilator melakukan optimasi *devirtualization*, mengubah pemanggilan tidak langsung menjadi pemanggilan langsung jika tipe objek dapat dianalisis secara statis.
   * C. Mengunci alokasi memori agar tidak bisa diubah di heap.
   * D. Menghapus kebutuhan menyertakan header sistem.

9. **Apa perbedaan mendasar antara *Dynamic Polymorphism* konvensional dengan *Type Erasure* modern (seperti yang digunakan pada `std::function`)?**
   * A. *Type Erasure* sama sekali tidak menggunakan pointer internal.
   * B. *Type Erasure* menyajikan antarmuka dengan semantik nilai (*value semantics*), memungkinkan penyimpanan dan penyalinan heterogen tanpa mengekspos pointer mentah di sisi API pengguna.
   * C. *Dynamic Polymorphism* selalu lebih cepat dibandingkan *Type Erasure*.
   * D. *Type Erasure* hanya bekerja pada tipe data primitif seperti `int` dan `float`.

10. **Apa bahaya terbesar memanggil metode virtual dari dalam konstruktor kelas dasar di C++?**
    * A. Kompilator menolak mengompilasi program secara langsung.
    * B. Terjadinya memory leak sebesar ukuran vtable.
    * C. Metode kelas turunan belum diinisialisasi sehingga pemanggilan virtual hanya diselesaikan ke metode kelas dasar, atau memicu kegagalan sistem (*pure virtual call crash*).
    * D. Seluruh CPU core langsung terkunci (*deadlock*).

---

### KUNCI JAWABAN KUIS EVALUASI

1. **C** — Penambahan fungsi virtual menyisipkan 8-byte `vptr` pada platform 64-bit, ditambah 4-byte `int`, yang kemudian digenapkan oleh padding kompilator menjadi kelipatan 8 byte terdekat (16 byte).
2. **C** — Untuk mencegah *undefined behavior* dan kebocoran sumber daya saat instansi kelas turunan dihapus via pointer kelas dasar.
3. **B** — Kata kunci `override` meminta kompilator bertindak sebagai pemeriksa ketat kecocokan tanda tangan fungsi virtual.
4. **B** — Saat passing by value, kompilator hanya menyalin ukuran sebesar kelas dasar, memotong habis data dan implementasi kelas turunan.
5. **B** — Memanfaatkan primitif manajemen sumber daya modern sehingga tidak perlu menulis boilerplate destruktor atau copy/move constructor secara eksplisit.
6. **C** — Indireksi memori ganda menghambat inlining dan membuat CPU sulit berspekulasi pada *branch target buffer*.
7. **B** — CRTP mengalihkan resolusi ke waktu kompilasi (*static polymorphism*) menggunakan teknik template casting.
8. **B** — `final` memberikan kepastian analitis kepada kompilator bahwa implementasi tersebut tidak dapat diganti lagi, membuka jalur devirtualisasi.
9. **B** — *Type Erasure* menyembunyikan polimorfisme di balik dinding antarmuka bernilai murni (*value semantics*).
10. **C** — Pada saat konstruktor kelas dasar berjalan, vptr masih mengarah ke vtable kelas dasar; implementasi kelas turunan belum tercipta.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Project: Heterogeneous Pipeline Processor Menggunakan Value-Based Type Erasure

**Spesifikasi Proyek**:
Anda diminta untuk membangun sebuah subsistem pemrosesan sinyal data sensor heterogen (*Heterogeneous Sensor Engine*) untuk sistem IoT berkinerja tinggi tanpa menggunakan pointer telanjang (*zero raw pointers*).

**Kebutuhan Sistem**:
1. Buat tiga tipe sensor independen tanpa hierarki pewarisan sama sekali:
   * `TemperatureSensor`: Memiliki metode `std::string read_data() const` yang mengembalikan data suhu.
   * `PressureSensor`: Memiliki metode `std::string read_data() const` yang mengembalikan tekanan barometrik.
   * `RadiationSensor`: Memiliki metode `std::string read_data() const` yang mengembalikan satuan radiasi Sievert.
2. Buat kelas pembungkus bernilai (*Value-Semantic Wrapper*) bernama `AnySensor` yang mengimplementasikan teknik **Type Erasure**:
   * Mendukung alokasi nilai secara transparan (*construct from any matching structural type*).
   * Memiliki *Copy Constructor* dan *Move Constructor* yang aman secara memori (*deep cloning mechanism*).
   * Menerapkan *Rule of Zero* pada level konsumen API luar.
3. Simpan seluruh sensor dalam kontainer sekuensial standar C++:
   ```cpp
   std::vector<AnySensor> sensor_array;
   ```
4. Iterasi seluruh elemen array dan cetak seluruh telemetri data melalui pemanggilan tunggal:
   ```cpp
   for(const auto& sensor : sensor_array) {
       std::cout << sensor.read() << '\n';
   }
   ```

**Kriteria Keberhasilan Eksekusi (Acceptance Criteria)**:
* Program terbebas dari kebocoran memori (Validasi kelulusan: Jalankan di bawah pengawasan LLVM AddressSanitizer `-fsanitize=address` tanpa ada indikasi kebocoran byte).
* Tidak ada pemanggilan eksplisit kata kunci `new` atau `delete` di luar implementasi model Type Erasure (wajib menggunakan `std::make_unique`).
* Seluruh deklarasi fungsi pada antarmuka yang tidak memodifikasi internal state wajib ditandai secara ketat dengan kualifikasi `const`.