# BAB 03: Object-Oriented Design Modern
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik enterprise engine architecture diharapkan mampu:
- **Menganalisis dan Membongkar** representasi memori tingkat rendah (*ABI layout*) dari objek polimorfik, meliputi kalkulasi offset `vptr`, resolusi `vtable`, penyesuaian pointer `this` pada pewarisan ganda (*multiple inheritance*), serta *virtual base table* (*vbtable*).
- **Menerapkan Desain Polimorfisme Statis dan Hibrida** menggunakan *Curiously Recurring Template Pattern* (CRTP), *C++20 Concepts*, dan *Manual Type Erasure* dengan *Small Buffer Optimization* (SBO) untuk mengeliminasi alokasi *heap* dan overhead *pointer chasing*.
- **Merancang Arsitektur Berorientasi Data Berdampingan dengan OOP (DOD-OOP Hybrid)** guna mengatasi masalah performa *cache line thrashing* yang inheren pada hierarki kelas tradisional.
- **Mengidentifikasi dan Mencegah** cacat fatal produksi seperti *object slicing*, *undefined behavior* pada konversi pointer multipel, dan kebocoran sumber daya pada implementasi *Pimpl Idiom* modern yang berbasis *cache-aligned fast storage*.

---

### 2. Prerequisite
Untuk memahami modul ini secara komprehensif, engineer wajib menguasai:
- **C++ Memory Model:** Perbedaan semantik *stack*, *heap*, *data segment*, segmentasi alignment memori (`alignas`, `alignof`), dan mekanisme padding compiler.
- **Modern C++ Basics:** *Move semantics* (`std::move`, `std::forward`), *perfect forwarding*, *smart pointers* (`std::unique_ptr`, `std::shared_ptr`), dan prinsip RAII (*Resource Acquisition Is Initialization*).
- **Templates Dasar:** *Class templates*, *function templates*, dan evaluasi compile-time dasar (`constexpr`, `if constexpr`).
- **Assembly X86-64 Dasar:** Pemahaman tentang instruksi dereferensi memori (`mov`), register pointer panggilan fungsi (`rax`, `rdi`), dan *indirect call branch target* (`call qword ptr [...]`).

---

### 3. Concept & Internal Architecture

#### 3.1 Anatomi Memori: Vptr, Vtable, dan Dynamic Dispatch
Dynamic polymorphism dalam standar C++ secara konseptual diimplementasikan oleh sebagian besar vendor compiler (Itanium ABI untuk GCC/Clang dan MSVC ABI) menggunakan *virtual table* (`vtable`) dan *virtual pointer* (`vptr`).

Ketika sebuah kelas mendeklarasikan minimal satu fungsi virtual:
1. Compiler menyisipkan *hidden pointer* (`vptr`) sebagai anggota data tersembunyi pertama dari objek (biasanya pada offset 0 untuk Itanium ABI).
2. Compiler memvalidasi dan mengompilasi sebuah *array of function pointers* konstan (`vtable`) per kelas konkret di dalam segmen memori read-only (`.rodata`).
3. Objek nyata membawa `vptr` yang menunjuk secara absolut ke segmen `vtable` yang relevan.

```
Eksekusi: Base* ptr = new Derived(); ptr->Execute();

1. Load pointer:        mov   rax, qword ptr [rdi]        ; Ambil nilai vptr dari objek Derived
2. Resolve function:    mov   rax, qword ptr [rax + 8]    ; Ambil pointer Execute() dari slot vtable
3. Indirect invocation: call  rax                         ; Panggil fungsi secara dinamis
```

Overhead dynamic dispatch bukan semata-mata latency instruksi dereferensi ekstra (sekitar 2–3 cycle), melainkan degradasi throughput CPU instruction pipeline:
- **Branch Target Buffer (BTB) Misprediction:** CPU speculative execution engine tidak dapat secara pasti memprediksi target lompatan instruksi tidak langsung (*indirect branch*).
- **Inlining Invalidation:** Compiler tidak dapat melakukan *inlining* kode secara agresif melintasi batasan modul kecuali *devirtualization pass* berhasil membuktikan tipe final secara statis.

#### 3.2 Multiple Inheritance & Thunk Mechanics
Pada skenario *Multiple Inheritance* (MI), sebuah kelas turunan mewarisi beberapa kelas basis yang masing-masing memiliki fungsi virtual independen. Objek turunan harus menyematkan beberapa `vptr` untuk mempertahankan kompatibilitas *sub-object*.

```
   +---------------------------------------+
   | Derived Object Layout in Memory       |
   +---------------------------------------+
   | [offset 0]  BaseA Sub-object         |
   |             - vptr_BaseA (offset 0)   |
   |             - BaseA data members      |
   +---------------------------------------+
   | [offset N]  BaseB Sub-object         |
   |             - vptr_BaseB (offset N)   |
   |             - BaseB data members      |
   +---------------------------------------+
   | [offset M]  Derived Specific Data     |
   +---------------------------------------+
```

Jika pointer dikonversi secara implisit dari `Derived*` ke `BaseB*`, compiler menyisipkan aritmatika pointer:
$$\text{Address}(BaseB) = \text{Address}(Derived) + \text{sizeof}(BaseA\_subobject)$$

Ketika fungsi virtual `BaseB` di-override oleh `Derived` dan dipanggil via `BaseB*`, fungsi tersebut membutuhkan konteks pointer `this` dari instansiasi `Derived` penuh. Compiler menyelesaikan ketidaksesuaian ini menggunakan **Thunk** (bagian kecil kode perantara perakitan) yang melakukan penyesuaian pointer register `this` (mengurangi offset) sebelum melompat ke badan fungsi `Derived::Function`.

#### 3.3 Type Erasure Architecture (Manual vs Template)
*Type Erasure* adalah paradigma arsitektur yang menjembatani polimorfisme statis (kinerja, tanpa alokasi memori dinamis) dengan polimorfisme dinamis (penyimpanan heterogen di kontainer STL). Implementasi industri (seperti yang digunakan dalam `std::function` atau `std::any`) mengabaikan hierarki kelas klasik dan mengandalkan struktur internal berbasis:
1. **Storage Unit:** Blok buffer memori mentah (*raw aligned storage*) yang dialokasikan di dalam stack objek untuk Small Buffer Optimization (SBO), fallback ke heap jika kapasitas terlampaui.
2. **Concept Base / Vtable Manual:** Struktur penunjuk fungsi manual statis yang memetakan operasi siklus hidup (`copy`, `move`, `destroy`, `invoke`).
3. **Templated Model Constructor:** Memetakan tipe konkret arbitrer ke dalam buffer memori tanpa memaksa tipe tersebut mewarisi antarmuka eksplisit (*duck typing at runtime*).

---

### 4. Why & What
- **Why Naive OOP Fails in High-Performance Systems:** Naive OOP mengasumsikan representasi model mental domain (*domain entities*) selalu linier dengan representasi memori. Pada kenyataannya, hierarki kelas yang dalam melahirkan alokasi objek berbasis pointer acak (`std::vector<std::unique_ptr<Base>>`). Pola ini mengakibatkan **Pointer Chasing**—setiap kali iterasi dilakukan, CPU harus mengambil data dari memori utama karena alamat yang terfragmentasi, memicu *L1/L2 data-cache misses* masif.
- **What Modern C++ OOP Delivers:**
  - Menggantikan *runtime indirection* dengan *compile-time contracts* menggunakan **C++20 Concepts** dan **CRTP**.
  - Menggantikan hierarki warisan pointer mentah dengan **Type Erasure** bernilai (*value semantic-based polymorphism*), memastikan kontinuitas alokasi memori dan semantik kepemilikan yang deterministik.
  - Memisahkan antarmuka fungsional dari representasi data memori (*Separation of Data from Behavior*) guna mendukung model eksekusi SIMD/cache-friendly tanpa merusak prinsip abstraksi.

---

### 5. How (Workflow detail)

Alur perancangan antarmuka enterprise modern C++ mengikuti pipeline:

```
[ Domain Interface Definition ]
             │
             ▼
[ Static Contract Verification (C++20 Concept) ]
             │
             ├── Mengizinkan Runtime Heterogeneity? ──┐
             │                                        │
            TIDAK                                     YA
             │                                        │
             ▼                                        ▼
   [ CRTP / Pure Concept ]                  [ Evaluasi Ukuran Objek ]
(Zero-cost, static dispatch,                          │
 inlining enabled)                     ┌──────────────┴──────────────┐
                                       ▼                             ▼
                               [ Size <= SBO Buffer ]      [ Size > SBO Buffer ]
                                       │                             │
                                       ▼                             ▼
                              [ Local In-situ Storage ]   [ Dynamic Allocation ]
                                       │                             │
                                       └──────────────┬──────────────┘
                                                      │
                                                      ▼
                                       [ Type-Erased Wrapper Class ]
                                       (Deterministic SBO Layout)
```

1. **Definisikan Kontrak Fungsional:** Menggunakan `concept` untuk memvalidasi *syntactic requirements* dan ekspresi yang valid pada waktu kompilasi.
2. **Tentukan Kebutuhan Polimorfisme:**
   - Gunakan **CRTP / Concepts** secara murni jika variasi tipe diketahui saat kompilasi (*pipeline/processor nodes*).
   - Gunakan **Type Erasure with SBO** jika objek heterogen perlu dikelompokkan secara runtime di dalam struktur data (*event queues, task schedulers*).
3. **Stabilkan ABI:** Isolasi data privat internal yang rentan berubah menggunakan *Fast Pimpl Pattern* yang memadukan pointer opasitas dengan buffer memori statis lokal untuk mencegah overhead indirection sekunder.

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem Transaksi Real-time
Bayangkan sistem loket teller bank tradisional (Dynamic OOP): Setiap nasabah membawa map dokumen tebal yang di dalamnya terdapat kartu instruksi khusus; teller harus membaca kartu tersebut, berjalan ke lemari arsip pusat untuk melihat metode penanganan arsip, baru memproses transaksi. Ini merepresentasikan *cache miss* dan *pointer chasing*.

Sebaliknya, pada Type Erasure Modern dengan SBO: Setiap nasabah membawa amplop terstandarisasi yang pas dimasukkan ke slot mesin pemroses di meja teller. Instruksi dieksekusi secara instan dari amplop tanpa teller perlu meninggalkan posisinya.

```
+-------------------------------------------------------------------------------+
|                      VIRTUAL TABLE DISPATCH LAYOUT                            |
+-------------------------------------------------------------------------------+
                                                                Memory: .rodata
Heap Object (Derived)                                         +-----------------+
+-----------------------+                                     |  Derived Vtable |
| vptr (8 bytes)        |====================================>| +-------------+ |
| --------------------- |                                     | | TypeInfo    | |
| Data: int a (4 bytes) |                                     | | FuncA() ptr | |
| Padding (4 bytes)     |                                     | | FuncB() ptr | |
| Data: double b (8B)   |                                     | +-------------+ |
+-----------------------+                                     +-----------------+

+-------------------------------------------------------------------------------+
|                    TYPE ERASURE WITH SBO (IN-SITU BUFFER)                     |
+-------------------------------------------------------------------------------+
TypeErasedWrapper (Stack Allocated)
+---------------------------------------------------------------+
| Storage Buffer (e.g., 32 bytes inline storage)               |
| +-----------------------------------------------------------+ |
| | Actual Concrete Object Data resides here directly         | |
| | [No heap allocation, contiguous memory execution]         | |
| +-----------------------------------------------------------+ |
| Invoker/Function Pointer Table (Static vtable alternative)    |
| +-----------------------------------------------------------+ |
| | invoke_fn*   | delete_fn*   | copy_fn*   | move_fn*       | |
| +-----------------------------------------------------------+ |
+---------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Static vs Dynamic Polymorphism (Assembly Indirection Test)
Komparasi arsitektural antara dynamic virtual method call vs CRTP devirtualization.

```cpp
#include <iostream>
#include <chrono>

// --- Dynamic Polymorphism ---
struct DynamicBase {
    virtual ~DynamicBase() = default;
    virtual void Process(int& val) = 0;
};

struct DynamicDerived final : public DynamicBase {
    void Process(int& val) override {
        val += 2;
    }
};

// --- Static Polymorphism (CRTP) ---
template <typename Derived>
struct CRTPBase {
    void Process(int& val) {
        static_cast<Derived*>(this)->ProcessImpl(val);
    }
};

struct CRTPDerived : public CRTPBase<CRTPDerived> {
    void ProcessImpl(int& val) {
        val += 2;
    }
};

// Pengujian Devirtualisasi
void InvokeDynamic(DynamicBase& obj, int& val) {
    obj.Process(val); // Assembly: call qword ptr [rax + offset] -> Indirect call
}

template <typename T>
void InvokeCRTP(CRTPBase<T>& obj, int& val) {
    obj.Process(val); // Assembly: add dword ptr [rsi], 2 -> Fully inlined
}
```

#### 7.2 Practical Example: Custom Type-Erased Event Handler with Small Buffer Optimization (SBO)
Implementasi enterprise-grade abstraksi callable tanpa overhead heap allocation untuk payload berukuran $\le 32$ byte.

```cpp
#include <iostream>
#include <new>
#include <utility>
#include <type_traits>
#include <array>
#include <cstdint>

template <size_t StorageSize = 32>
class FixedExecutionHandler {
public:
    constexpr FixedExecutionHandler() noexcept : invoker_(nullptr), manager_(nullptr) {}

    // Constructor templated menerima sembarang Callable
    template <typename F>
    requires (!std::is_same_v<std::decay_t<F>, FixedExecutionHandler> && std::is_invocable_v<F>)
    FixedExecutionHandler(F&& callable) {
        using RawF = std::decay_t<F>;
        static_assert(sizeof(RawF) <= StorageSize, 
                      "Target callable melebihi batas SBO! Gunakan custom dynamic wrapper.");
        static_assert(alignof(RawF) <= alignof(std::max_align_t), 
                      "Alignment melampaui kapasitas storage mentah.");

        new (storage_.data()) RawF(std::forward<F>(callable));
        
        invoker_ = [](void* storage) {
            (*reinterpret_cast<RawF*>(storage))();
        };

        manager_ = [](void* src, void* dest, Action action) {
            switch (action) {
                case Action::Destroy:
                    reinterpret_cast<RawF*>(src)->~RawF();
                    break;
                case Action::Move:
                    new (dest) RawF(std::move(*reinterpret_cast<RawF*>(src)));
                    reinterpret_cast<RawF*>(src)->~RawF();
                    break;
            }
        };
    }

    ~FixedExecutionHandler() {
        Reset();
    }

    FixedExecutionHandler(const FixedExecutionHandler&) = delete;
    FixedExecutionHandler& operator=(const FixedExecutionHandler&) = delete;

    FixedExecutionHandler(FixedExecutionHandler&& other) noexcept {
        MoveFrom(std::move(other));
    }

    FixedExecutionHandler& operator=(FixedExecutionHandler&& other) noexcept {
        if (this != &other) {
            Reset();
            MoveFrom(std::move(other));
        }
        return *this;
    }

    void operator()() const {
        if (invoker_) {
            invoker_(const_cast<void*>(static_cast<const void*>(storage_.data())));
        }
    }

    explicit operator bool() const noexcept {
        return invoker_ != nullptr;
    }

    void Reset() noexcept {
        if (manager_) {
            manager_(storage_.data(), nullptr, Action::Destroy);
            invoker_ = nullptr;
            manager_ = nullptr;
        }
    }

private:
    enum class Action { Destroy, Move };
    using InvokerFn = void(*)(void*);
    using ManagerFn = void(*)(void*, void*, Action);

    void MoveFrom(FixedExecutionHandler&& other) noexcept {
        if (other.manager_) {
            other.manager_(other.storage_.data(), storage_.data(), Action::Move);
            invoker_ = other.invoker_;
            manager_ = other.manager_;
            other.invoker_ = nullptr;
            other.manager_ = nullptr;
        } else {
            invoker_ = nullptr;
            manager_ = nullptr;
        }
    }

    alignas(std::max_align_t) std::array<std::byte, StorageSize> storage_;
    InvokerFn invoker_{nullptr};
    ManagerFn manager_{nullptr};
};

int main() {
    int counter = 0;
    
    // Lambdas capture state yang muat di dalam 32 bytes SBO
    FixedExecutionHandler<32> handler([&counter]() {
        counter += 42;
    });

    handler();
    std::cout << "Stateful SBO Executed. Counter: " << counter << '\n';

    FixedExecutionHandler<32> movedHandler = std::move(handler);
    movedHandler();
    std::cout << "Stateful SBO Executed post-move. Counter: " << counter << '\n';

    return 0;
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Pada arsitektur mesin *Ultra-Low-Latency Order Execution Engine* di bursa finansial, arsitektur awal mengandalkan hierarki virtual murni:
```cpp
class OrderValidator {
    virtual bool Validate(const Order& order) = 0;
};
```
Sistem memproses variasi 30 format pesanan yang ditransmisikan عبر berbagai feed (*FIX, ITCH, OUCH, Binary Proprietary*).

#### Permasalahan (Root Cause Analysis)
1. **Cache Misses:** Pemrosesan 50 juta pesanan/detik menyebabkan throughput tersendat di kisaran 12 juta pesanan/detik. Analisis perangkat keras via `perf stat -e L1-dcache-load-misses,branch-misses` menunjukkan:
   - Branch misprediction rate pada virtual call: **18.4%**.
   - L1 Data Cache load miss: **24.2%** akibat representasi objek validator tersebar di berbagai alamat heap secara tidak beraturan.
2. **Latensi Non-deterministik:** Pada persentil p99.99, latensi melonjak dari $85\text{ ns}$ ke $1.4\ \mu\text{s}$ akibat CPU pipeline flushing saat devirtualisasi runtime gagal dilakukan secara spekulatif.

#### Transformasi Arsitektur
Engine dirancang ulang menggunakan pola hibrida: **Static CRTP Pipeline + Type-Erased Variant Envelope**.

```
[ Inbound Wire Buffer ] 
          │
          ▼
[ Variant-based Static Decoded Stream: std::variant<LimitOrder, MarketOrder, IcebergOrder> ]
          │ (Zero-Heap Allocation)
          ▼
[ Pipeline Execution via C++20 Templated Visitor Pattern ]
          │
          ├──> CRTP Static Validator <RiskCheckPolicy>
          ├──> CRTP Static Validator <RegulatoryCompliancePolicy>
          └──> CRTP Static Matcher Engine Core
```

#### Hasil Benchmark Pasca Refactoring
- **Throughput:** Meningkat secara stabil ke **54.8 juta pesanan/detik** (peningkatan ~356%).
- **Branch Mispredictions:** Turun drastis ke **0.3%**.
- **Latensi p99.99:** Terkompresi menjadi **62 nanodetik** secara konsisten deterministik.

---

### 9. Trade-offs

| Pendekatan Arsitektur | Keuntungan | Kerugian & Batasan | Use-case Optimal |
| :--- | :--- | :--- | :--- |
| **Traditional Dynamic Polymorphism (`virtual`)** | Implementasi intuitif, decoupled translation units, waktu kompilasi cepat, polymorphic collections standar. | *Pointer chasing*, inlining terhambat, memory overhead per instance (`vptr`), branch misprediction. | UI frameworks, high-level business workflow, plugin modules dinamis via DLL/.so. |
| **Static Polymorphism (CRTP / Concepts)** | Eksekusi deterministik, *zero runtime overhead*, aggressively inlined, eliminasi `vptr`. | *Code bloat* (ekspansi biner berlebih), tidak dapat disimpan dalam homogen STL container tanpa variant/erasure. | HFT Core Engine, Math/Matrix libraries, Network packet protocol parsing. |
| **Type Erasure with SBO** | Semantik nilai (*Value Semantics*), tidak ada pewarisan antarmuka eksplisit, alokasi heap nol jika $\le$ buffer. | Implementasi internal kompleks, limitasi buffer storage statis membatasi fleksibilitas payload. | Enterprise Event Loop, Thread-safe Task Queues, Heterogeneous modern callback frameworks. |
| **`std::variant` Polymorphism** | Value semantics, alokasi memori datar (*flat contiguous memory*), devirtualisasi via `std::visit`. | Closed-set polymorphism (tipe variasi harus diketahui saat kompilasi), ukuran varian = ukuran tipe terbesar + diskriminan. | Finite State Machines, AST Compiler Nodes, Protocol parsers dengan varian terdefinisi. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Object Slicing
**Gejala:** Mengirimkan objek derived berdasarkan nilai (*by-value*) ke dalam parameter bertipe base interface. Anggota data dan method derived terpotong secara permanen.
```cpp
void Register(DynamicBase base); // KESALAHAN FATAL: Menginisialisasi parsial sub-object Base
```
**Solusi Produksi:** Gunakan modifier referensi konstan atau rvalue, dan hapus copy-constructor pada Base class non-final.
```cpp
class DynamicBase {
public:
    DynamicBase(const DynamicBase&) = delete;
    DynamicBase& operator=(const DynamicBase&) = delete;
    virtual ~DynamicBase() = default;
};
```

#### 10.2 Undefined Behavior: Non-Virtual Base Destructors
**Gejala:** Deallokasi instance derived via pointer base interface `delete ptr;` hanya mengeksekusi destructor kelas base. Sumber daya OS di kelas derived (file handles, heap buffers, socket locks) bocor seketika.
**Troubleshooting:** Kompilasi dengan `-Wnon-virtual-dtor` (GCC/Clang) atau enforce interface guidelines modern: Destructor pada base class wajib berstatus `public and virtual` ATAU `protected and non-virtual`.

#### 10.3 Broken Casts pada Multiple Inheritance Layouts
**Gejala:** Memanipulasi pointer kelas derived melalui `reinterpret_cast` ke kelas basis sekunder.
```cpp
Derived* d = new Derived();
BaseB* b = reinterpret_cast<BaseB*>(d); // UB: Pointer tidak digeser ke offset BaseB sub-object!
```
**Mitigasi:** Wajib menggunakan `static_cast` untuk downcast deterministik yang dikompilasi dengan offset offset adjustment terhitung, atau `dynamic_cast` jika pemeriksaan tipe runtime diperlukan.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Eliminasi Raw Destructors:** Jadikan destructors dari polymorphic base classes `public virtual` atau `protected non-virtual`.
2. [ ] **Gunakan Modifier `final` Secara Agresif:** Tandai kelas daun (*leaf classes*) dan method penutup dengan `final` guna memicu kemampuan compiler melakukan devirtualisasi optimistik.
3. [ ] **Terapkan Rule of Zero/Five Secara Disiplin:** Jika mendeklarasikan custom virtual destructor, definisikan atau hapus secara eksplisit *Copy/Move constructors* dan *Copy/Move assignment operators*.
4. [ ] **Audit Aligment & Padding Struktur Objek:** Urutkan anggota data dari ukuran terbesar ke terkecil guna meminimalkan padding byte di antara anggota polimorfik.
5. [ ] **Pertahankan SBO Alignment:** Pastikan memori mentah pada manual type erasure dialokasikan dengan spesifikasi `alignas(std::max_align_t)`.
6. [ ] **Preferensi Value Semantics:** Utamakan pengembalian objek by-value memanfaatkan RVO (*Return Value Optimization*) daripada return pointer interface dinamis.
7. [ ] **Gunakan C++20 Concepts sebagai Filter:** Terapkan concept constraints sebelum melompat ke Dynamic Interface guna menolak tipe yang salah pada *compile-time phase*.

---

### 12. Hands-on Practice
Simpan praktikum berikut di direktori target: `hands-on/m02/`

#### Struktur Direktori
```
hands-on/m02/
├── Makefile
├── include/
│   ├── FastPimpl.hpp
│   └── PipelineNode.hpp
└── src/
    └── main.cpp
```

#### `hands-on/m02/include/FastPimpl.hpp`
```cpp
#pragma once
#include <cstddef>
#include <utility>
#include <new>

template <typename T, size_t Size, size_t Alignment>
class FastPimpl {
public:
    template <typename... Args>
    explicit FastPimpl(Args&&... args) {
        static_assert(sizeof(T) <= Size, "FastPimpl Size buffer terlalu kecil!");
        static_assert(Alignment % alignof(T) == 0, "FastPimpl Alignment tidak valid!");
        new (storage_) T(std::forward<Args>(args)...);
    }

    ~FastPimpl() {
        Ptr()->~T();
    }

    T* operator->() noexcept { return Ptr(); }
    const T* operator->() const noexcept { return Ptr(); }
    T& operator*() noexcept { return *Ptr(); }
    const T& operator*() const noexcept { return *Ptr(); }

private:
    T* Ptr() noexcept { return reinterpret_cast<T*>(storage_); }
    const T* Ptr() const noexcept { return reinterpret_cast<const T*>(storage_); }

    alignas(Alignment) std::byte storage_[Size];
};
```

#### `hands-on/m02/include/PipelineNode.hpp`
```cpp
#pragma once
#include <iostream>
#include <string_view>

// CRTP Node Interface
template <typename Derived>
class ProcessingNode {
public:
    void Execute(std::string_view payload) {
        // Enforce static polymorphic call
        static_cast<Derived*>(this)->ProcessImplementation(payload);
    }
};

class LoggingNode : public ProcessingNode<LoggingNode> {
public:
    void ProcessImplementation(std::string_view payload) {
        std::cout << "[LoggingNode] Payload diproses: " << payload << '\n';
    }
};

class CompressionNode : public ProcessingNode<CompressionNode> {
public:
    void ProcessImplementation(std::string_view payload) {
        std::cout << "[CompressionNode] Payload dikompresi (Size: " << payload.size() << ")\n';
    }
};
```

#### `hands-on/m02/src/main.cpp`
```cpp
#include "PipelineNode.hpp"
#include "FastPimpl.hpp"
#include <vector>
#include <variant>

// Implementasi Pimpl Data Internal
struct MetricsCollectorInternal {
    uint64_t operationsProcessed{0};
    void Record() { operationsProcessed++; }
};

class MetricsCollector {
public:
    MetricsCollector();
    ~MetricsCollector();
    void Increment() { pimpl_->Record(); }
    uint64_t GetOps() const { return pimpl_->operationsProcessed; }
private:
    FastPimpl<MetricsCollectorInternal, 8, 8> pimpl_;
};

MetricsCollector::MetricsCollector() : pimpl_() {}
MetricsCollector::~MetricsCollector() = default;

int main() {
    LoggingNode logger;
    CompressionNode compressor;

    // Direct Static Invocations (Devirtualized, Zero Indirection)
    logger.Execute("TRANSACTION_ID_88491");
    compressor.Execute("TRANSACTION_ID_88491");

    // Decoupled ABI using Fast Pimpl
    MetricsCollector metrics;
    metrics.Increment();
    std::cout << "[Metrics] Total Operasi: " << metrics.GetOps() << '\n';

    return 0;
}
```

#### `hands-on/m02/Makefile`
```makefile
CXX = g++
CXXFLAGS = -std=c++20 -O3 -Wall -Wextra -Wpedantic -Iinclude

TARGET = bin/pipeline_runner

all: $(TARGET)

$(TARGET): src/main.cpp
	@mkdir -p bin
	$(CXX) $(CXXFLAGS) src/main.cpp -o $(TARGET)

clean:
	rm -rf bin

run: $(TARGET)
	./$(TARGET)
```

---

### 13. Exercise

#### Level Easy
- **Tugas:** Definisikan kelas antarmuka `SensorReader` dengan method virtual murni `Read()`. Turunkan dua kelas konkret `TemperatureReader` dan `PressureReader`.
- **Target Pembuktian:** Buktikan adanya `vptr` pada kedua kelas derived menggunakan operator `sizeof` (tunjukkan bahwa `sizeof` objek lebih besar dari representasi anggotanya saja).

#### Level Medium
- **Tugas:** Bangun pola pemrosesan polimorfik untuk sistem parser protokol jaringan menggunakan `std::variant` dan `std::visit`. Buat minimal tiga jenis paket data (*HandshakePacket*, *HeartbeatPacket*, *DataPacket*).
- **Target Pembuktian:** Implementasikan visitor yang memproses paket tanpa menggunakan deklarasi `virtual` sama sekali dan validasikan eksekusi melalui iterator serial `std::vector<std::variant<...>>`.

#### Level Hard
- **Tugas:** Kembangkan *Intrusive Small Object Allocator* yang membatasi heap overhead untuk Type-Erased Invoker.
- **Syarat Ketat:**
  1. Batas maksimal ukuran storage internal: 64 bytes.
  2. Implementasikan deep-copying jika payload mendukung Copy-Constructible.
  3. Berikan proteksi kompilasi menggunakan C++20 Concept jika invoker diinstansiasi dengan objek yang tidak memenuhi pemanggilan `operator()`.

---

### 14. Challenge
**Studi Kasus:** Ultra-Low Latency In-Memory Cache Event Broker.
Sebuah engine perpesanan mengharuskan dispatching heterogen dari 100 jenis event audit berbeda dengan frekuensi hingga 10 juta event per detik. Menggunakan pointer `std::shared_ptr<EventInterface>` memicu kemacetan bus memori karena atomic reference counting overhead dan dynamic heap allocation. Menggunakan `std::variant` langsung tidak dimungkinkan karena arsitektur engine bersifat *open-ended* (modul audit pihak ketiga dapat mendaftarkan tipe event baru secara dinamis tanpa kompilasi ulang core engine).

**Misi Arsitektur Anda:**
1. Rancang modul **Polymorphic Ring-Buffer** yang menyimpan objek event heterogen secara bersebelahan (*contiguous chunk of memory*) tanpa alokasi heap per-event dan tanpa memicu *Undefined Behavior* alignment memori.
2. Mekanisme dispatching dilarang menggunakan dynamic `vtable` pointer chasing tradisional; Anda harus mengimplementasikan skema dispatching berbasis *offset indexing* atau manual function-pointer tables terkompilasi rapat.
3. Seluruh skema harus menjamin bahwa siklus hidup objek (konstruksi dan destruksi) dieksekusi secara tepat tanpa kebocoran resource native.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. **Berapa ukuran penambahan memori yang diperkenalkan oleh pointer `vptr` pada arsitektur sistem operasi 64-bit standar?**
   - A. 4 bytes
   - B. 8 bytes
   - C. 16 bytes
   - D. Bergantung pada jumlah fungsi virtual di kelas tersebut
   *Jawaban:* **B**. Pada sistem 64-bit, setiap pointer berukuran 8 byte. Banyaknya method virtual hanya menambah entri pada `vtable`, bukan ukuran objek fisik.

2. **Kapan *devirtualization pass* pada compiler modern dapat secara otomatis mengubah pemanggilan virtual function menjadi pemanggilan fungsi statis?**
   - A. Setiap kali fungsi ditandai dengan keyword `inline`.
   - B. Jika kelas yang dituju ditandai dengan keyword `final` atau tipe instansiasi objek konkret dapat dianalisis secara statis pada translation unit yang sama.
   - C. Jika kelas dasar tidak memiliki anggota data.
   - D. Devirtualisasi tidak mungkin dilakukan dalam C++.
   *Jawaban:* **B**. Compiler dapat membuktikan bahwa fungsi tidak mungkin di-override jika kelas/metode ditandai `final`, atau objek dialokasikan langsung di stack lokal.

3. **Apa konsekuensi memori jika sebuah kelas mewarisi dua basis yang masing-masing memiliki fungsi virtual (Multiple Inheritance non-virtual)?**
   - A. Objek turunan memiliki satu `vtable` gabungan dan satu `vptr`.
   - B. Objek turunan menyematkan dua pointer `vptr` yang berbeda dalam layout memorinya.
   - C. Objek turunan tidak memerlukan `vptr`.
   - D. Terjadi kegagalan kompilasi jika kedua interface memiliki nama method berbeda.
   *Jawaban:* **B**. Multiple inheritance menyematkan sub-object dari masing-masing base class, sehingga membutuhkan `vptr` mandiri untuk masing-masing pointer view.

4. **Apa tujuan utama penerapan Small Buffer Optimization (SBO) pada manual Type Erasure?**
   - A. Mempercepat waktu kompilasi source code.
   - B. Menyimpan data langsung di dalam stack memori pembungkus (wrapper) untuk mengeliminasi pemanggilan alokasi memori dinamis (`heap allocation`).
   - C. Memungkinkan data di-kompresi secara realtime menggunakan CPU hardware instructions.
   - D. Mengubah pemanggilan indirect call menjadi direct inlined assembly.
   *Jawaban:* **B**. SBO mengalokasikan array byte lokal untuk objek yang ukurannya berada di bawah ambang batas, menghindari degradasi alokasi dinamis.

5. **Apa bahaya melakukan `delete` pada pointer `Base* ptr = new Derived();` jika kelas `Base` tidak memiliki virtual destructor?**
   - A. Terjadi error kompilasi: *missing virtual destructor*.
   - B. Compiler otomatis mengoreksi dan memanggil destructor derived.
   - C. Destructor derived tidak dieksekusi, berujung pada kebocoran sumber daya dan *Undefined Behavior*.
   - D. Alokasi memori stack akan rusak (*stack corruption*).
   *Jawaban:* **C**. Standar C++ menegaskan penghapusan polymorphic object melalui pointer base tanpa virtual destructor adalah *Undefined Behavior*.

#### Intermediate (5 Soal)
6. **Pada arsitektur Multiple Inheritance, apa fungsi spesifik dari sebuah assembly "Thunk"?**
   - A. Mengalokasikan memori darurat di heap saat stack penuh.
   - B. Mengoreksi dan menggeser register pointer `this` sebelum melompat ke alamat aktual method yang meng-override.
   - C. Menghitung branch prediction index pada CPU core.
   - D. Menghapus objek derived saat destructor dasar dipanggil.
   *Jawaban:* **B**. Thunk menyesuaikan offset pointer `this` agar titik awal memori sesuai dengan layout kelas derived yang mengimplementasikan method tersebut.

7. **Mengapa pola CRTP (Curiously Recurring Template Pattern) mampu menghasilkan kinerja yang jauh lebih tinggi dibanding Dynamic Polymorphism tradisional?**
   - A. CRTP menyimpan data di register CPU secara permanen.
   - B. Resolusi fungsi terjadi saat compile-time melalui instansiasi template, memungkinkan compiler melakukan *inlining* instruksi dan mengeliminasi pointer chasing.
   - C. CRTP mem-bypass pemanggilan kernel OS.
   - D. CRTP mengompresi ukuran biner hingga 50%.
   *Jawaban:* **B**. Karena resolusi berbasis tipe statis pada waktu kompilasi, tidak ada lompatan fungsi pointer tidak langsung (*indirect branch*), membuka potensi optimasi compiler penuh.

8. **Perhatikan skenario: Kelas `Derived` mewarisi `Base` secara polimorfik. Mengapa operasi `reinterpret_cast<Base*>(derived_ptr)` dianggap sangat berbahaya dibandingkan `static_cast`?**
   - A. `reinterpret_cast` lebih lambat dibandingkan `static_cast`.
   - B. `reinterpret_cast` tidak melakukan penyesuaian (*pointer offset adjustment*) saat melintasi hierarki memori pewarisan berganda.
   - C. `reinterpret_cast` menghapus seluruh anggota data kelas Derived secara acak.
   - D. `reinterpret_cast` tidak dapat dikompilasi pada standar C++20.
   *Jawaban:* **B**. `reinterpret_cast` hanya menginterpretasikan ulang bit alamat memori secara mentah tanpa menghitung perbedaan offset memori sub-object.

9. **Apa masalah mekanis mendasar pada penggunaan `std::vector<std::unique_ptr<BaseInterface>>` di lingkungan aplikasi pemrosesan throughput tinggi?**
   - A. Pointer `std::unique_ptr` tidak aman secara memori (*memory unsafe*).
   - B. Mengakibatkan *Spatial Cache Locality* yang sangat buruk karena payload data konkret tersebar secara acak di heap memori (*pointer chasing*).
   - C. Menghabiskan thread pool OS.
   - D. Menghalangi eksekusi loop multi-core.
   *Jawaban:* **B**. Meskipun vektor menyimpan smart pointer secara kontigu, pointer tersebut menunjuk ke lokasi heap yang terfragmentasi, menyebabkan *cache line miss* konstan pada CPU.

10. **Bagaimana Fast Pimpl Idiom memitigasi kekurangan utama dari Pimpl Idiom tradisional?**
    - A. Menyembunyikan nama kelas dari debugger OS.
    - B. Menghilangkan alokasi heap ekstra untuk *Implementation class* dengan mengalokasikan storage biner bertipe mentah langsung di stack header menggunakan alignment yang terverifikasi.
    - C. Menolak penggunaan pointer secara keseluruhan.
    - D. Menjamin backward compatibility secara lintas bahasa ke platform C.
    *Jawaban:* **B**. Pimpl tradisional memicu `new` pada konstruksi, sedangkan Fast Pimpl menyediakan array statis `std::byte` beraligned di dalam kelas luar untuk instansiasi placement-new lokal.

#### Production Scenarios (3 Soal)
11. **Skenario:** Tim Anda mendeteksi lonjakan latency p99 secara periodik pada microservice gateway perdagangan aset. Analisis profiler menunjukkan pemanggilan polimorfik `TaskHandler::Process()` menyebabkan lonjakan CPU *Branch Misprediction*. Kode terstruktur sebagai berikut:
```cpp
std::vector<std::unique_ptr<ITask>> task_queue;
// Di dalam hot loop:
for (auto& task : task_queue) {
    task->Process();
}
```
Variasi `ITask` di sistem hanya berjumlah tepat empat jenis konkrit yang diketahui secara komprehensif saat kompilasi.
**Keputusan Arsitektur Apa yang Harus Segera Diambil?**
    - A. Mengganti CPU server dengan core yang memiliki clock rate lebih tinggi.
    - B. Mengonversi `std::vector<std::unique_ptr<ITask>>` menjadi flat continuous container `std::vector<std::variant<TypeA, TypeB, TypeC, TypeD>>` dan mengeksekusi hot loop via `std::visit`.
    - C. Menambahkan keyword `volatile` pada antarmuka `ITask::Process()`.
    - D. Membungkus `task_queue` di dalam thread pool mutex terkunci.
    *Jawaban:* **B**. Menggunakan `std::variant` merestrukturisasi memori menjadi array kontinu datar (menghilangkan heap fragmentasi) dan resolusi via `std::visit` memungkinkan lompatan instruksi terstruktur tanpa overhead pointer allocation dinamis.

12. **Skenario:** Anda membangun library infrastruktur enterprise C++20 yang didistribusikan ke ribuan node klien perbankan via shared object (`.so`). Jika Anda menambahkan variabel anggota data `private` baru ke dalam implementasi kelas C++ konvensional, ABI akan rusak total dan mengharuskan seluruh kode aplikasi klien di-recompile.
**Solusi arsitektural mana yang paling menjamin stabilitas ABI tanpa mengorbankan alokasi heap performa tinggi secara berlebihan?**
    - A. Membuka seluruh variabel privat menjadi variabel global.
    - B. Menggunakan Fast Pimpl Idiom dengan alokasi buffer cadangan statis (*padding reserved buffer*) dan validasi statis ukuran memori saat waktu kompilasi.
    - C. Menghapus seluruh variabel anggota dan hanya menggunakan local static variables.
    - D. Memaksa klien untuk selalu menggunakan dynamic link loader (`dlopen`) runtime.
    *Jawaban:* **B**. Fast Pimpl mengisolasi layout internal kelas privat dari konsumsi header publik, memelihara kompatibilitas ukuran biner dan ABI layout tanpa alokasi heap ekstra.

13. **Skenario:** Di dalam trading loop sub-mikrodetik, ditemukan bahwa kelas derived mewarisi dua basis abstrak: `class ExecutionEngine : public MarketDataListener, public OrderLifecycleManager`. Saat memanggil method `OrderLifecycleManager::OnFill()`, CPU menghabiskan tambahan 4 siklus instruksi karena instruksi compiler `sub rdi, offset` (Thunk pointer adjustment).
**Bagaimana cara mendesain ulang arsitektur kelas tersebut guna meniadakan penalti offset adjustment register `this` pada interface kritis tersebut?**
    - A. Gunakan keyword `virtual` inheritance pada seluruh antarmuka basis.
    - B. Reorganisasi urutan deklarasi kelas turunan sehingga interface yang paling berorientasi latensi-kritis (`OrderLifecycleManager`) ditempatkan sebagai **kelas basis pertama (first base class)** pada baris deklarasi pewarisan.
    - C. Gunakan `const_cast` pada pointer objek saat pemanggilan method.
    - D. Bungkus kedua base class di dalam template parameter ganda.
    *Jawaban:* **B**. Pada compiler yang mematuhi Itanium/MSVC ABI, sub-object dari kelas basis pertama ditempatkan pada offset 0 dari objek derived. Oleh karena itu, konversi ke kelas basis pertama tidak memerlukan pergeseran (*shift pointer adjustment*) dan mengeksekusi direct call tanpa thunk trampoline.

---

### 16. Summary
- Pemahaman dynamic polymorphism modern menuntut transparansi mekanisme tingkat mesin: pointer `vptr`, tabel `vtable`, penyesuaian layout memori pada multiple inheritance, dan konsekuensi destruksi virtual.
- Naive OOP yang menempatkan objek polimorfik sembarangan di heap memory merupakan anti-pattern utama dalam arsitektur modern karena menghancurkan performa CPU data-cache dan mempersulit kompilator mengeksekusi optimasi devirtualisasi.
- Pergeseran modern menuju **Zero-Cost Abstractions** mengedepankan evaluasi compile-time: mengutamakan `C++20 Concepts` dan `CRTP` untuk skenario performa deterministik statis, serta `Type Erasure with SBO` dan `std::variant` untuk heterogenitas runtime berbasis *value semantics*.
- Menguasai manajemen objek tingkat lanjut—mulai dari pengendalian *ABI slicing*, optimasi isolasi *Fast Pimpl*, hingga arsitektur *DOD-OOP Hybrid*—adalah fondasi utama seorang Staff/Principal Systems Architect dalam merekayasa perangkat lunak berskala besar yang efisien, terukur, dan bebas dari *undefined behaviors*.