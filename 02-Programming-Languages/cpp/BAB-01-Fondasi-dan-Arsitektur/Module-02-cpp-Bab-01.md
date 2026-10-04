# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 02-Programming-Languages | **Topik:** C++ | **Bab:** 01 - Fondasi dan Arsitektur

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Membedah** tata letak memori internal (*memory layout*) pada C++, termasuk segmentasi proses, *virtual table* (`vtable`/`vptr`), *object slicing*, dan *memory alignment/padding*.
- **Menguasai Mekanika Tingkat Rendah System** terkait sistem kategori nilai (*value categories*: lvalue, prvalue, xvalue) serta mengimplementasikan *Move Semantics* dan *Perfect Forwarding* tanpa menimbulkan *dangling reference* atau *unintended copies*.
- **Merancang Arsitektur Zero-Allocation / Low-Latency** berbasis kustom memori alokator (*Arena/Monotonic Allocator*, *Pool Allocator*) untuk menghindari fragmentasi *heap* dan latensi deterministik pada level mikrodetik.
- **Mengoptimalkan Simpati Mekanikal (*Mechanical Sympathy*)** terhadap arsitektur CPU modern: meminimalkan *cache misses* (L1/L2/L3), mitigasi *false sharing*, dan memanfaatkan *SIMD/cache-line alignment* (`alignas`, `std::hardware_destructive_interference_size`).
- **Membangun Sistem Produksi Enterprise** dengan kepatuhan C++20, *RAII (Resource Acquisition Is Initialization)* yang ketat, pencegahan *Undefined Behavior* (UB), dan integrasi *tooling* instrumentasi modern (ASan, UBSan, TSan, Compiler Explorer/Compiler AST inspection).

---

## 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib menguasai:
1. **Sintaks Dasar C++ dan Pemrograman Berorientasi Objek**: Pewarisan (*inheritance*), polimorfisme, *pointer*, *reference*, dan *templates* dasar.
2. **Model Eksekusi OS & Arsitektur Komputer**: Paging memori virtual, *registers*, tumpukan eksekusi (*stack frame*), serta interaksi dasar *kernel space* vs *user space*.
3. **Toolchain**: CMake (>= 3.20), Clang/GCC yang mendukung C++20, GDB/LLDB, dan pemahaman dasar representasi assembly x86-64 (AT&T atau Intel syntax).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Tata Letak Memori Objek dan Polimorfisme Dinamis

Di tingkat kompilasi x86-64, sebuah objek C++ tidak lebih dari blok *bytes contiguous* pada memori. Ketika kelas memiliki fungsi virtual, kompilator menyematkan pointer tersembunyi yang disebut **`vptr` (virtual table pointer)**, umumnya diletakkan pada offset 0 dari objek tersebut.

```
Layout Objek Tunggal dengan Virtual Method:
+------------------------------------+
| vptr (8 bytes pada x86-64)        |  ---> Menunjuk ke VTable di segmen .rodata
+------------------------------------+
| Member Variables (Aligned/Padded)  |
+------------------------------------+
```

Setiap kelas turunan yang melakukan *override* terhadap *virtual function* memiliki *vtable* tersendiri di segmen `.rodata`. Pemanggilan metode virtual mengeksekusi dereferensi ganda (*indirect branch*):
1. Membaca `vptr` dari instansiasi objek: `movq (%rdi), %rax`
2. Membaca alamat fungsi dari slot tabel virtual tertentu: `movq 8(%rax), %rax`
3. Melompat ke alamat fungsi: `callq *%rax`

Konsekuensi arsitektural: *Indirect branch* ini berpotensi menyebabkan *Branch Target Buffer (BTB) miss* pada CPU pipeline jika tipe objek bervariasi secara dinamis dalam satu *loop* ketat.

### 3.2 Memory Alignment, Padding, dan Cache Lines

CPU modern tidak membaca memori per bita secara independen, melainkan dalam kelipatan *word* atau *cache lines* (umumnya 64 byte). Untuk mencegah instruksi membaca melintasi batas *word* (*unaligned memory access* yang berbiaya komputasi ganda), kompilator menyisipkan *padding*.

Struktur data:
```cpp
struct Unoptimized {
    char a;    // 1 byte
               // 7 bytes padding
    double b;  // 8 bytes (alignment 8)
    int c;     // 4 bytes
               // 4 bytes padding
};             // Total: 24 bytes! Rasio guna: 13/24 (~54%)
```
Setelah reorganisasi (menyusun variabel dari alignment terbesar ke terkecil):
```cpp
struct Optimized {
    double b;  // 8 bytes
    int c;     // 4 bytes
    char a;    // 1 byte
               // 3 bytes padding
};             // Total: 16 bytes! Rasio guna: 13/16 (~81%)
```

### 3.3 Anatomi Taksonomi Kategori Nilai (Value Categories)

C++11 merevolusi model ekspresi dengan taksonomi C++ standar ISO/IEC 14882:

```
                  Expressions (glvalue)
                     /           \
                    /             \
             lvalue                rvalue
                                   /    \
                                  /      \
                             xvalue     prvalue
```

- **glvalue (generalized lvalue)**: Evaluasi yang menentukan identitas objek/fungsi.
- **lvalue**: Objek yang memiliki identitas persisten dan alamat memorinya dapat diambil (`&obj`).
- **prvalue (pure rvalue)**: Komputasi sementara (*ephemeral*) tanpa identitas memori langsung (misal: literal numerik `42`, nilai kembalian fungsi non-referensi `Point(1, 2)`).
- **xvalue (eXpiring value)**: Objek yang memiliki identitas, namun memorinya aman untuk "dijarah" atau dialihkan (*move-eligible*), dihasilkan umumnya via `std::move()` (yang pada dasarnya adalah *static_cast<T&&>*).

### 3.4 Mekanisme Move Semantics dan Universal/Forwarding References

Move semantics tidak memindahkan bita secara fisik di memori secara ajaib; move semantics adalah pengalihan kepemilikan (*transfer of ownership*) atas pointer internal atau *handle* sumber daya dari objek *expiring* ke objek baru, disusul penataan ulang sumber daya asal ke kondisi *valid but unspecified* (biasanya `nullptr` atau `0`).

```cpp
template <typename T>
void Process(T&& param); // Forwarding Reference (bukan rvalue reference biasa)
```
Mengikuti **Reference Collapsing Rules**:
- `&` + `&` $\rightarrow$ `&`
- `&` + `&&` $\rightarrow$ `&`
- `&&` + `&` $\rightarrow$ `&`
- `&&` + `&&` $\rightarrow$ `&&`

`std::forward<T>(val)` memanfaatkan aturan ini untuk mengembalikan rvalue hanya jika parameter aslinya di-*pass* sebagai rvalue, menjaga efisiensi transfer data (*Perfect Forwarding*).

---

## 4. Why & What

| Problem Domain | Pendekatan Naif (Traditional C++) | Solusi Produksi Enterprise (Modern C++) |
| :--- | :--- | :--- |
| **Alokasi Dinamis** | Alokasi global heap via `new`/`malloc` tersebar di mana-mana. Mengakibatkan *lock contention* pada multi-threading dan fragmentasi heap parah. | Kustom Monotonic/Arena Allocator atau Pool Allocator. O(1) deterministik alokasi tanpa *system-call overhead*. |
| **Siklus Hidup Sumber Daya** | Manual `delete`, raw pointers, raw file descriptors (`FILE*`, `socket fd`). Rentan *memory leak* dan *double-free*. | RAII mutlak, *Move-only Types* (`std::unique_ptr`, custom zero-cost resource wrappers), Rule of Five/Zero. |
| **Polimorfisme** | Deep virtual inheritance hierarchies (`A -> B -> C -> D`). *Pointer chasing* dan destruksi performa cache CPU. | *Data-Oriented Design* (DOD), Type Erasure datar, atau Static Polymorphism via CRTP (*Curiously Recurring Template Pattern*) dan C++20 `concepts`. |
| **Pengiriman Objek** | *Pass-by-value* menghasilkan *deep-copy* tak terkontrol atau *pass-by-const-reference* yang membatasi pemanfaatan memori rvalue. | Move Semantics, *Perfect Forwarding*, dan `std::span`/`std::string_view` untuk *non-owning zero-copy abstractions*. |

---

## 5. How (Workflow Detail)

Berikut adalah alur transformasi kode C++20 enterprise dari kode sumber hingga eksekusi instruksi mesin dengan alokasi khusus:

```
[Source Code (.cpp/.hpp)]
         │
         ▼
[Clang/GCC Front-End] ───> Parsing & AST Construction
         │                 Type Checking & Template Instantiation
         ▼
[Intermediate Representation (LLVM IR / GIMPLE)]
         │                 Optimization Passes (-O3):
         │                 - Inlining virtual functions (Devirtualization)
         │                 - Dead Code Elimination & Loop Unrolling
         │                 - Auto-vectorization (SIMD)
         ▼
[Machine Code Generation] ──> Aligned Stack Allocations & Instruction Scheduling
         │
         ▼
[Linker (LLD/Gold)] ────────> Resolves Global Symbols, Merges VTables, Strips Dead Strips
         │
         ▼
[OS Loader & Runtime Initialization]
         │ 1. Mapping ELF binary (.text, .rodata, .data, .bss)
         │ 2. Dynamic Linking (ld.so)
         │ 3. Executing __libc_start_main -> global constructors
         ▼
[Application Heap/Arena Init]
         │ Memesan Virtual Address Space besar (mmap / VirtualAlloc)
         ▼
[Deterministic Execution Loop]
         │ Zero allocation pada hot-path
         ▼
[RAII Stack Unwinding / Arena Reset]
```

---

## 6. Analogy & Diagram ASCII

### 6.1 Analogi: Perpindahan Kepemilikan (Move vs Copy)
- **Copy Semantics**: Anda ingin meminjam buku ensiklopedia 1000 halaman dari rekan Anda. Anda memfotokopi seluruh 1000 halaman tersebut lembar demi lembar (biaya besar, lambat), lalu menaruh fotokopi tersebut di meja Anda.
- **Move Semantics**: Rekan Anda sudah tidak butuh lagi ensiklopedia tersebut. Alih-alih memfotokopi, ia langsung menyerahkan buku aslinya ke meja Anda dan mengosongkan rak bukunya. Anda langsung memilikinya dengan biaya transfer nyaris nol (hanya memindahkan kepemilikan fisik seketika).

### 6.2 Diagram: Memory Layout & VTable Dispatch

```
Heap / Stack Memory                         Read-Only Data Segment (.rodata)
===================                         ================================
Instance Object 'Derived':                  VTable for 'Derived':
+-----------------------+                   +-----------------------------------+
| 0x00: vptr            | ----------------> | 0x00: type_info for Derived       |
+-----------------------+                   +-----------------------------------+
| 0x08: Base::data_     | (int64_t = 8B)    | 0x08: &Derived::Execute() (Func*) |
+-----------------------+                   +-----------------------------------+
| 0x10: Derived::value_ | (int32_t = 4B)    | 0x10: &Derived::~Derived() (Destr)|
+-----------------------+                   +-----------------------------------+
| 0x14: [Padding]       | (4B padding)
+-----------------------+
Ukuran Total: 24 Bytes (Teralignasi 8 bytes)
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Memahami Rvalue Reference & Rule of Five

Implementasi *string buffer* mini yang mengilustrasikan Rule of Five secara eksplisit dan idiomatis:

```cpp
#include <iostream>
#include <cstring>
#include <utility>

class RawBuffer {
private:
    char*  data_{nullptr};
    size_t size_{0};

public:
    // 1. Constructor
    RawBuffer(const char* str = "") {
        size_ = std::strlen(str);
        data_ = new char[size_ + 1];
        std::memcpy(data_, str, size_ + 1);
    }

    // 2. Destructor
    ~RawBuffer() noexcept {
        delete[] data_;
    }

    // 3. Copy Constructor (Deep Copy)
    RawBuffer(const RawBuffer& other) : size_(other.size_) {
        data_ = new char[size_ + 1];
        std::memcpy(data_, other.data_, size_ + 1);
    }

    // 4. Copy Assignment Operator
    RawBuffer& operator=(const RawBuffer& other) {
        if (this != &other) {
            char* new_data = new char[other.size_ + 1];
            std::memcpy(new_data, other.data_, other.size_ + 1);
            delete[] data_;
            data_ = new_data;
            size_ = other.size_;
        }
        return *this;
    }

    // 5. Move Constructor (Steal resources - Noexcept is mandatory for STL safety)
    RawBuffer(RawBuffer&& other) noexcept 
        : data_(std::exchange(other.data_, nullptr)),
          size_(std::exchange(other.size_, 0)) {}

    // 6. Move Assignment Operator
    RawBuffer& operator=(RawBuffer&& other) noexcept {
        if (this != &other) {
            delete[] data_;
            data_ = std::exchange(other.data_, nullptr);
            size_ = std::exchange(other.size_, 0);
        }
        return *this;
    }

    [[nodiscard]] const char* c_str() const noexcept { return data_ ? data_ : ""; }
    [[nodiscard]] size_t size() const noexcept { return size_; }
};
```

### 7.2 Practical Example: Arena / Linear Allocator Kelas Industri (Zero-Allocation Loop)

Di lingkungan produksi berbasis sistem *low-latency* (misal: *game engine*, *high-frequency trading*), pemanggilan `malloc`/`free` di dalam putaran komputasi utama adalah anti-pola. Berikut adalah implementasi Arena Allocator yang memenuhi alignment memori CPU modern:

```cpp
#include <cstddef>
#include <cstdint>
#include <new>
#include <utility>
#include <concepts>
#include <memory>
#include <stdexcept>

class LinearArenaAllocator {
private:
    std::byte* buffer_{nullptr};
    size_t capacity_{0};
    size_t offset_{0};

public:
    explicit LinearArenaAllocator(size_t capacity) 
        : capacity_(capacity), offset_(0) {
        // Alokasi memori blok besar teralignasi 64-byte (Cache Line boundary)
        buffer_ = static_cast<std::byte*>(::operator new[](capacity, std::align_val_t{64}));
    }

    ~LinearArenaAllocator() noexcept {
        ::operator delete[](buffer_, std::align_val_t{64});
    }

    // Non-copyable, Non-movable untuk integritas memori deterministik
    LinearArenaAllocator(const LinearArenaAllocator&) = delete;
    LinearArenaAllocator& operator=(const LinearArenaAllocator&) = delete;
    LinearArenaAllocator(LinearArenaAllocator&&) = delete;
    LinearArenaAllocator& operator=(LinearArenaAllocator&&) = delete;

    template <typename T, typename... Args>
    requires std::constructible_from<T, Args...>
    [[nodiscard]] T* Create(Args&&... args) {
        void* current_ptr = static_cast<void*>(buffer_ + offset_);
        size_t space_remaining = capacity_ - offset_;

        // Menyelaraskan pointer sesuai kebutuhan tipe data T
        void* aligned_ptr = std::align(alignof(T), sizeof(T), current_ptr, space_remaining);

        if (!aligned_ptr) {
            throw std::bad_alloc();
        }

        // Hitung ulang offset baru
        offset_ = capacity_ - space_remaining + sizeof(T);

        // Construct object di in-place memory menggunakan placement-new
        return ::new (aligned_ptr) T(std::forward<Args>(args)...);
    }

    // Operasi O(1) untuk menghapus seluruh objek secara instan
    void Reset() noexcept {
        offset_ = 0;
    }

    [[nodiscard]] size_t BytesAllocated() const noexcept { return offset_; }
    [[nodiscard]] size_t Capacity() const noexcept { return capacity_; }
};
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Ultra-Low Latency Market Data Order Book Feed-Handler

**Konteks Arsitektur:**
Sebuah bursa finansial memancarkan order market data (Level 2/3 depth) dengan intensitas 500.000 pesan/detik melalui protokol UDP Multicast. Sistem lama mengalami lonjakan tail latency ($P_{99.9}$) hingga 45 milidetik akibat aktivitas default memory manager glibc (karena heap fragmentation dan contention mutex thread).

**Desain Arsitektur Baru:**
1. **Thread Pinning**: Utas alur pemrosesan jaringan dipasangi afinitas CPU core tertentu (`pthread_setaffinity_np`), terisolasi dari *OS scheduler tick*.
2. **Ring Buffer Lock-Free Single-Producer Single-Consumer (SPSC)**: Antrian transfer paket antara thread parsing jaringan dan thread agregasi order book.
3. **PMR (Polymorphic Memory Resources) / Pre-allocated Arena**: Parsing JSON/Binary flatbuffer langsung ke blok memori yang dialokasikan sebelumnya.

```
[NIC Kernel Bypass: DPDK / Solarflare ef_vi]
               │
               ▼
   [Network Ingestion Core (Pinned)]
               │ (Zero-copy raw packet)
               ▼
   [Ring Buffer SPSC (Cache-line aligned, 64-byte padded)]
               │
               ▼
   [Matching / Parsing Core (Pinned)]
        ├──> Menggunakan Local Frame Arena Allocator (10 MB pool)
        ├──> Placement-New OrderStruct langsung di L1/L2 Cache
        └──> Reset Frame Arena setiap siklus 100ms selesai
```

**Dampak Performa:**
- $P_{99.9}$ latency turun dari 45 ms menjadi **1.8 mikrodetik**.
- Mutex lock contention berkurang 100% pada *hot-path*.
- *Cache misses* (L3) berkurang sebesar 87% berkat pencegahan fragmentasi memori.

---

## 9. Trade-offs

| Pendekatan / Fitur | Keuntungan | Kerugian & Konsekuensi |
| :--- | :--- | :--- |
| **Virtual Functions (Dynamic Dispatch)** | Polimorfisme modular, pemisahan antarmuka (*interface decoupling*) yang bersih, kemudahan ekstensi kode tanpa kompilasi ulang seluruh basis kode. | Mengakibatkan *vtable overhead* (penambahan ukuran pointer per instans), *indirect jumps* merusak prediksi cabang (*branch prediction*), mematikan peluang kompilator melakukan optimasi *inlining*. |
| **CRTP (Compile-Time / Static Dispatch)** | Menghasilkan performa maksimum setara pemanggilan fungsi langsung, mendukung *inlining* penuh tanpa biaya runtime. | *Code bloat* biner membengkak jika template diinstansiasi dengan banyak tipe, pesan error compiler panjang dan sulit didebug, tidak mendukung koleksi heterogen yang dinamis di runtime. |
| **Arena/Bump Allocator** | Alokasi berkecepatan tinggi $O(1)$ hanya dengan menggeser pointer penunjuk (*bump pointer*), sangat ramah CPU cache (*spatial locality*). | Tidak mendukung dealokasi parsial objek individual; destruktor objek tidak dipanggil secara otomatis kecuali dilacak secara manual (*manual destruction tracking*). |
| **Pass-by-value + std::move** | Mengurangi beban penulisan *overload* fungsi ganda (antara `const T&` dan `T&&`), menyederhanakan kode. | Menyebabkan satu alokasi tambahan atau konstruksi move ekstra yang dapat dihindari jika menggunakan *perfect forwarding* murni. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Mengakses Objek Setelah Dipindahkan (Use-After-Move)

**Kesalahan:**
```cpp
std::vector<std::string> names;
std::string user = "Enterprise-User";
names.push_back(std::move(user));

// BUG: 'user' sekarang dalam kondisi "valid but unspecified".
// Membaca nilainya memicu perilaku yang tidak terprediksi secara logis.
if (user.empty()) { 
    std::cout << "User is empty\n"; // Bisa benar, tapi jangan jadikan asumsi desain!
}
std::cout << user.length() << '\n'; // Bahaya dependensi logika bisnis
```

**Solusi:**
Anggap objek yang telah dikenai `std::move` berada di ambang kematian (*tombstone*). Jangan pernah memanggil metode selain destruktor atau operasi penugasan ulang (`operator=`). Gunakan Clang-Tidy dengan flag `-Wbugprone-use-after-move`.

### 10.2 Object Slicing saat Menangkap atau Mengoper Turunan Kelas

**Kesalahan:**
```cpp
class Base { public: virtual void Action() { std::cout << "Base"; } };
class Derived : public Base { public: void Action() override { std::cout << "Derived"; } };

void Execute(Base b) { // BUG: Pass-by-value mengiris (slice) Derived menjadi Base!
    b.Action();
}

Derived d;
Execute(d); // Mencetak: "Base", implementasi Derived terpotong!
```

**Solusi:**
Gunakan selalu *pass-by-reference-to-const* atau *smart pointer*:
```cpp
void Execute(const Base& b) {
    b.Action(); // Menjalankan vtable dispatch dengan benar -> "Derived"
}
```

### 10.3 False Sharing pada Pemrograman Multithreading

**Kesalahan:**
Dua variabel atomic yang diakses oleh dua thread berbeda berada dalam satu *cache line* 64-byte yang sama.

```cpp
struct ThreadCounters {
    std::atomic<uint64_t> core1_counter{0}; // Berada di byte 0-7
    std::atomic<uint64_t> core2_counter{0}; // Berada di byte 8-15 (1 cache line!)
};
```
CPU L1 cache coherency protocol (MESI) akan saling membatalkan (*invalidate*) cache line bolak-balik antara Core 1 dan Core 2 (*cache bouncing*), menghancurkan throughput pemrosesan paralel.

**Solusi:**
Gunakan instruksi alignment modern C++17/C++20:
```cpp
#include <new>

struct ThreadCounters {
    alignas(std::hardware_destructive_interference_size) 
        std::atomic<uint64_t> core1_counter{0};
    alignas(std::hardware_destructive_interference_size) 
        std::atomic<uint64_t> core2_counter{0};
};
```

---

## 11. Best Practices (Production Checklist)

| Komponen | Status Wajib | Kriteria Evaluasi Produksi |
| :--- | :--- | :--- |
| **Move Noexcept** | **MANDATORY** | Semua move constructor & move assignment *harus* ditandai `noexcept`. Jika tidak, `std::vector` akan melakukan *fallback* ke deep-copy saat ekspansi kapasitas memori demi menjaga *strong exception guarantee*. |
| **Virtual Destructor** | **MANDATORY** | Setiap kelas dasar (*base class*) yang memiliki fungsi virtual wajib mendeklarasikan `virtual ~Base() = default;` untuk mencegah *resource leak* parsial saat menghapus pointer *base*. |
| **Explicit Constructors** | **MANDATORY** | Konstruktor dengan satu argumen (atau yang dapat dipanggil dengan satu argumen) wajib ditandai `explicit` untuk mencegah konversi implisit yang memicu pembuatan objek temporer tersembunyi. |
| **Zero Raw Ownership** | **MANDATORY** | Dilarang menggunakan raw pointer (`T*`) untuk mengelola *lifetime* kepemilikan memori. Gunakan `std::unique_ptr` untuk kepemilikan eksklusif atau RAII wrapper khusus. |
| **Sanitizers On CI** | **MANDATORY** | Pipeline build produksi CI/CD wajib mengompilasi unit test dengan AddressSanitizer (`-fsanitize=address`), UndefinedBehaviorSanitizer (`-fsanitize=undefined`), dan ThreadSanitizer (`-fsanitize=thread`). |

---

## 12. Hands-on Practice

Struktur direktori praktikum yang harus dibangun:
```
hands-on/m02/
├── CMakeLists.txt
├── include/
│   ├── MemoryPool.hpp
│   └── Packet.hpp
└── src/
    └── main.cpp
```

### Langkah 1: Buat file `hands-on/m02/CMakeLists.txt`
```cmake
cmake_minimum_required(VERSION 3.20)
project(CppMemoryArchitectureProduction LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Warning flags ketat untuk standar produksi
if (MSVC)
    add_compile_options(/W4 /WX /permissive-)
else()
    add_compile_options(-Wall -Wextra -Wpedantic -Werror -Wshadow -Wnon-virtual-dtor)
endif()

include_directories(include)

add_executable(memory_benchmark 
    src/main.cpp
)

# Aktifkan AddressSanitizer jika build type Debug
if(CMAKE_BUILD_TYPE STREQUAL "Debug" AND NOT MSVC)
    target_compile_options(memory_benchmark PRIVATE -fsanitize=address,undefined)
    target_link_options(memory_benchmark PRIVATE -fsanitize=address,undefined)
endif()
```

### Langkah 2: Buat file `hands-on/m02/include/Packet.hpp`
```cpp
#pragma once
#include <cstdint>
#include <string_view>
#include <cstring>
#include <iostream>

struct PacketHeader {
    uint32_t sequence_id;
    uint16_t payload_size;
    uint16_t packet_type;
};

class alignas(64) TelemetryPacket {
private:
    PacketHeader header_;
    char payload_[120]; // Total struct = 8 + 120 = 128 bytes (Tepat 2 Cache Lines)

public:
    TelemetryPacket() noexcept {
        std::memset(&header_, 0, sizeof(PacketHeader));
        std::memset(payload_, 0, sizeof(payload_));
    }

    TelemetryPacket(uint32_t seq, uint16_t type, std::string_view data) noexcept {
        header_.sequence_id = seq;
        header_.packet_type = type;
        const size_t copy_len = std::min(data.size(), sizeof(payload_) - 1);
        std::memcpy(payload_, data.data(), copy_len);
        payload_[copy_len] = '\0';
        header_.payload_size = static_cast<uint16_t>(copy_len);
    }

    [[nodiscard]] uint32_t GetSequence() const noexcept { return header_.sequence_id; }
    [[nodiscard]] std::string_view GetPayload() const noexcept { return {payload_, header_.payload_size}; }
};
```

### Langkah 3: Buat file `hands-on/m02/include/MemoryPool.hpp`
```cpp
#pragma once
#include <cstddef>
#include <cstdint>
#include <utility>
#include <concepts>
#include <new>
#include <vector>

template <typename T, size_t BlockCount>
class FixedObjectPool {
private:
    union Node {
        alignas(alignof(T)) std::byte storage[sizeof(T)];
        Node* next;
    };

    Node* free_list_head_{nullptr};
    std::byte* raw_memory_{nullptr};

public:
    FixedObjectPool() {
        // Alokasikan memori teralignasi
        const size_t total_size = sizeof(Node) * BlockCount;
        raw_memory_ = static_cast<std::byte*>(::operator new[](total_size, std::align_val_t{alignof(Node)}));
        
        // Inisialisasi linked-list internal (Free-List)
        Node* pool = reinterpret_cast<Node*>(raw_memory_);
        for (size_t i = 0; i < BlockCount - 1; ++i) {
            pool[i].next = &pool[i + 1];
        }
        pool[BlockCount - 1].next = nullptr;
        free_list_head_ = &pool[0];
    }

    ~FixedObjectPool() noexcept {
        ::operator delete[](raw_memory_, std::align_val_t{alignof(Node)});
    }

    FixedObjectPool(const FixedObjectPool&) = delete;
    FixedObjectPool& operator=(const FixedObjectPool&) = delete;

    template <typename... Args>
    [[nodiscard]] T* Allocate(Args&&... args) {
        if (!free_list_head_) {
            throw std::bad_alloc();
        }

        Node* node = free_list_head_;
        free_list_head_ = free_list_head_->next;

        // Construct objek di memory buffer
        T* object_ptr = reinterpret_cast<T*>(node->storage);
        ::new (static_cast<void*>(object_ptr)) T(std::forward<Args>(args)...);
        return object_ptr;
    }

    void Deallocate(T* ptr) noexcept {
        if (!ptr) return;

        // Panggil destruktor objek secara manual
        ptr->~T();

        // Kembalikan node ke head free list secara O(1)
        Node* node = reinterpret_cast<Node*>(ptr);
        node->next = free_list_head_;
        free_list_head_ = node;
    }
};
```

### Langkah 4: Buat file `hands-on/m02/src/main.cpp`
```cpp
#include "MemoryPool.hpp"
#include "Packet.hpp"
#include <chrono>
#include <vector>
#include <iostream>

constexpr size_t ITERATIONS = 1'000'000;
constexpr size_t POOL_CAPACITY = 2'000'000;

void BenchmarkStandardHeap() {
    auto start = std::chrono::high_resolution_clock::now();
    std::vector<TelemetryPacket*> container;
    container.reserve(ITERATIONS);

    for (size_t i = 0; i < ITERATIONS; ++i) {
        container.push_back(new TelemetryPacket(static_cast<uint32_t>(i), 1, "SYSTEM_METRIC_DATA_POINT"));
    }

    for (auto* ptr : container) {
        delete ptr;
    }

    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double, std::milli> duration = end - start;
    std::cout << "[Standard Heap] Time taken: " << duration.count() << " ms\n";
}

void BenchmarkCustomMemoryPool() {
    auto start = std::chrono::high_resolution_clock::now();
    
    // Alokasi FixedObjectPool di luar hot loop
    auto pool = std::make_unique<FixedObjectPool<TelemetryPacket, POOL_CAPACITY>>();
    std::vector<TelemetryPacket*> container;
    container.reserve(ITERATIONS);

    for (size_t i = 0; i < ITERATIONS; ++i) {
        container.push_back(pool->Allocate(static_cast<uint32_t>(i), 1, "SYSTEM_METRIC_DATA_POINT"));
    }

    for (auto* ptr : container) {
        pool->Deallocate(ptr);
    }

    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double, std::milli> duration = end - start;
    std::cout << "[Fixed Object Pool] Time taken: " << duration.count() << " ms\n";
}

int main() {
    std::cout << "Starting Memory Architecture & Allocator Benchmark...\n";
    std::cout << "Packet size: " << sizeof(TelemetryPacket) << " bytes\n";
    std::cout << "Alignment  : " << alignof(TelemetryPacket) << " bytes\n\n";

    BenchmarkStandardHeap();
    BenchmarkCustomMemoryPool();

    return 0;
}
```

### Langkah 5: Kompilasi dan Eksekusi
```bash
cd hands-on/m02
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
cmake --build .
./memory_benchmark
```

---

## 13. Exercises

### Level Easy
Terdapat deklarasi struct berikut:
```cpp
struct DataEvent {
    bool is_valid;
    double timestamp;
    uint32_t event_id;
    char source_tag;
};
```
1. Hitung berapa besar memori (`sizeof(DataEvent)`) pada target arsitektur x86-64 secara manual dengan mempertimbangkan padding.
2. Atur ulang (*reorder*) member variabel dari struct tersebut untuk meminimalkan *padding overhead*.
3. Tuliskan verifikasi menggunakan static assertion (`static_assert`) untuk memastikan ukuran struct hasil rekonstruksi Anda berada pada ukuran paling ringkas.

### Level Medium
Rancang dan implementasikan smart pointer kustom bertipe *Move-Only* bernama `UniqueRef<T>` yang mereplikasi perilaku `std::unique_ptr<T>`:
1. Wajib menghapus (*delete*) *copy constructor* dan *copy assignment operator*.
2. Mengimplementasikan *move constructor* dan *move assignment operator* berlabel `noexcept`.
3. Memastikan pemanggilan destruktor objek tepat satu kali saat *out of scope*.
4. Menyediakan operator `*` (*dereference*) dan `->` (*member access*).

### Level Hard
Implementasikan sebuah ringkas idiom **Type Erasure** modern untuk menggantikan antarmuka virtual (`vtable`) dengan performa tinggi:
1. Buat kelas `FunctionView<void()>` non-alokasi (*zero heap allocation*).
2. Kelas ini mampu menerima sembarang *callable object* (fungsi bebas, lambda tanpa capture, atau lambda dengan capture) menggunakan *function pointer* dan *internal object pointer* tanpa memanggil operator `new`.
3. Demonstrasikan pemanggilannya dalam pipeline eksekusi berbasis *batch processing*.

---

## 14. Challenge

**Skenario Sistem:**
Anda ditunjuk sebagai Principal Engineer di sebuah perusahaan IoT Cloud Gateway. Gateway ini menerima 100.000 metrik per detik per perangkat. Setiap pembacaan metrik harus disimpan ke dalam sebuah ring-buffer circular berkapasitas 10.000.000 objek.

**Spesifikasi Masalah:**
- Dilarang keras melakukan alokasi heap (`new`, `malloc`, `std::vector::push_back` tanpa reservasi awal) setelah fase inisialisasi aplikasi selesai (*steady state zero-allocation guarantee*).
- Objek metrik memiliki ukuran bervariasi tergantung jenis metrik (string payload, telemetry array, boolean status).
- Penggunaan dynamic polymorphism berbasis `vtable` dilarang pada jalur pemrosesan data utama karena overhead *cache-line invalidation*.

**Misi Arsitektur:**
1. Rancang arsitektur buffer heterogen tanpa alokasi heap baru, memanfaatkan `std::variant` atau custom *Flat-Memory Tagged Buffer*.
2. Implementasikan pola **Static Polymorphism** (CRTP atau C++20 `std::visit` / function table terstruktur) untuk melakukan serialisasi data ke format biner secara deterministik.
3. Berikan analisis performa profiling menggunakan *hardware performance counters* (instruksi, cycles, cache-misses) yang membuktikan nihilnya *heap allocation overhead* dan minimnya latensi eksekusi.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: 5 Pertanyaan Basic
1. Apa fungsi utama dari kata kunci `alignas` pada deklarasi struktur data di C++?
   - A. Menentukan urutan inisialisasi variabel di dalam kelas.
   - B. Memaksa kompilator menempatkan variabel pada kelipatan alamat memori tertentu.
   - C. Mengonversi tipe data secara eksplisit pada saat kompilasi.
   - D. Mencegah pemanggilan fungsi secara rekursif.
2. Mengapa move constructor sebaiknya selalu ditandai dengan spesifikasi `noexcept`?
   - A. Agar kompilator mengabaikan konstruktor tersebut saat terjadi error sintaks.
   - B. Agar kontainer standar seperti `std::vector` menggunakannya secara aman saat realokasi kapasitas tanpa melanggar *strong exception guarantee*.
   - C. Karena move constructor tidak pernah mengonsumsi memori stack.
   - D. Wajib secara sintaksis menurut standar C++20.
3. Di segmen memori mana *Virtual Method Table (vtable)* umumnya ditempatkan oleh kompilator?
   - A. Stack Segment
   - B. Heap Segment
   - C. Read-Only Data Segment (`.rodata`)
   - D. Uninitialized Data Segment (`.bss`)
4. Apa yang terjadi secara mekanis ketika ekspresi `std::move(x)` dieksekusi?
   - A. Data pada variabel `x` langsung dipindahkan ke alamat memori lain.
   - B. Memori variabel `x` dihapus dari RAM secara instan.
   - C. Kompilator melakukan *unconditional cast* dari tipe asal menjadi *rvalue reference* (`T&&`).
   - D. Utas pemanggil berhenti (*suspend*) sampai data disalin.
5. Apa dampak dari *Object Slicing* di C++?
   - A. Memori program mengalami fragmentasi permanen.
   - B. Bagian turunan dari objek kelas turunan hilang saat di-assign atau di-pass by-value ke variabel tipe kelas dasar (*base class*).
   - C. Pointer `vptr` terduplikasi secara liar.
   - D. Terjadi kegagalan kompilasi secara instan (*compile error*).

### Bagian B: 5 Pertanyaan Intermediate
6. Misalkan terdapat fungsi: `template<typename T> void Forwarder(T&& arg);`. Jika parameter yang dioper adalah lvalue bertipe `int&`, tipe apakah `T` yang diinferensikan oleh kompilator?
   - A. `int`
   - B. `int&&`
   - C. `int&`
   - D. `const int&`
7. Mengapa array dari kelas polimorfik (kelas yang memiliki pointer vtable) tidak boleh dimanipulasi melalui pointer ke kelas dasar secara aritmetika pointer (`base_ptr++`)?
   - A. Karena `sizeof(Derived)` umumnya lebih besar dari `sizeof(Base)`, sehingga pointer arithmetic akan melompat ke offset memori yang salah (UB).
   - B. Karena pointer kelas dasar tidak memiliki hak akses memori heap.
   - C. Karena vtable akan otomatis terhapus pada elemen kedua.
   - D. Karena kompilator akan menghasilkan *syntax error*.
8. Manakah pernyataan yang paling akurat mengenai fenomena *False Sharing* pada arsitektur multi-core?
   - A. Dua utas mencoba menulis ke variabel yang sama persis tanpa sinkronisasi mutex.
   - B. Dua utas yang dieksekusi di core berbeda memodifikasi variabel independen yang kebetulan berada pada satu *cache line* (64-byte) yang sama.
   - C. Memori RAM kehabisan alokasi sehingga swapping ke disk terjadi tanpa disengaja.
   - D. Instruksi CPU membaca instruksi lama akibat prediksi cabang yang meleset.
9. Kapan kita wajib menerapkan **Rule of Five** alih-alih mengandalkan **Rule of Zero**?
   - A. Ketika kelas kita memiliki lebih dari lima variabel anggota primitif.
   - B. Ketika kelas kita mengelola kepemilikan sumber daya tingkat rendah secara langsung (*raw resources/handles*) yang memerlukan penanganan alokasi dan dealokasi eksplisit.
   - C. Ketika sebuah kelas mengimplementasikan minimal satu fungsi `template`.
   - D. Ketika kita menggunakan antarmuka grafis atau framework GUI pihak ketiga.
10. Pada modern C++, apa perbedaan struktural mendasar antara `prvalue` dan `xvalue`?
    - A. Keduanya identik dan tidak dapat dibedakan.
    - B. `prvalue` memiliki identitas memori yang valid, sedangkan `xvalue` tidak memiliki alamat.
    - C. `xvalue` memiliki identitas objek yang memorinya dapat dialihkan (*move-eligible*), sedangkan `prvalue` adalah komputasi nilai sementara tanpa identitas memori persisten.
    - D. `prvalue` selalu dialokasikan di heap, sedangkan `xvalue` selalu di stack.

### Bagian C: 3 Skenario Kasus Produksi
11. **Skenario 1**: Sebuah microservice gateway berbasis C++20 mengalami lonjakan CPU 100% dan penurunan throughput drastis setiap beberapa jam sekali. Analisis heap dump menunjukkan bahwa memory footprint aplikasi tetap stabil pada 200 MB, namun `glibc malloc` menghabiskan 85% waktu siklus CPU saat melayani *request*. Apa diagnosis arsitektural yang paling logis dan bagaimana langkah perbaikannya?
12. **Skenario 2**: Dalam sebuah framework jaringan multi-threaded, class `ConnectionSession` diimplementasikan dengan destructor biasa (non-virtual). Komponen lain menghapus pointer sesi ini melalui interface pointer `IConnection*`. Pengujian unit dasar lolos, namun pengujian longevity (24 jam) di staging menunjukkan memory leak konstan sebesar puluhan gigabytes. Mengapa hal ini terjadi dan bagaimana mekanisme mekanikalnya?
13. **Skenario 3**: Sebuah modul algoritma trading mengeksekusi kalkulasi matematis terhadap jutaan struct `QuoteData` dalam sebuah vector. Meskipun compiler flag `-O3` diaktifkan, eksekusi kode berjalan 4 kali lebih lambat dibanding ekspektasi spesifikasi hardware. Saat dianalisis dengan `perf stat`, angka metrik `L1-dcache-load-misses` sangat tinggi. Diketahui struct `QuoteData` berukuran 48 bytes dengan komposisi variabel acak. Apa langkah audit dan restrukturisasi yang harus Anda terapkan?

---

### Kunci Jawaban & Pembahasan Quiz

#### Kunci Bagian A:
1. **B** — `alignas` digunakan secara eksplisit untuk menyelaraskan alamat variabel/tipe data pada batas kelipatan bita tertentu demi kepatuhan arsitektur hardware atau optimasi instruksi SIMD.
2. **B** — STL container (seperti `std::vector`) mengecek *type-trait* `std::is_nothrow_move_constructible_v`. Jika false, vector akan menduplikasi via copy demi menjaga *strong exception safety* (jika terjadi error di tengah proses, state lama tidak rusak).
3. **C** — Vtable bersifat read-only dan berlaku konstan untuk seluruh instansiasi kelas tersebut sepanjang *lifecycle* aplikasi, sehingga diletakkan di segmen memori `.rodata`.
4. **C** — `std::move` adalah fungsi utilitas yang pada dasarnya merupakan `static_cast<T&&>(var)`. Move tidak mengeksekusi instruksi pergerakan data di runtime secara langsung.
5. **B** — Mengoper objek turunan secara *by-value* ke tipe kelas dasar hanya akan menyalin ukuran bita kelas dasar; member dan perilaku khusus turunan terpotong (*sliced away*).

#### Kunci Bagian B:
6. **C** — Berdasarkan *reference collapsing rule*: lvalue reference `int&` yang bertemu dengan universal reference `&&` akan tereduksi menjadi `int&`.
7. **A** — Operasi `ptr++` mengeksekusi lompatan alamat berbasis `sizeof(Type)`. Jika `ptr` bertipe `Base*`, CPU akan melompat sebesar `sizeof(Base)` bita, jatuh tepat di tengah-tengah memori `Derived[0]` dan mengakibatkan *Undefined Behavior* saat membaca elemen berikutnya.
8. **B** — False sharing terjadi ketika thread yang berbeda pada core yang berbeda memodifikasi variabel berbeda yang berada di dalam satu cache line 64-byte yang sama, memaksa cache coherency bus saling menginvalidasi baris cache secara konstan.
9. **B** — Jika mengelola low-level handles (seperti OS file descriptor, custom dynamic array, network socket raw), Anda wajib mendefinisikan Destructor, Copy Constructor, Copy Assignment, Move Constructor, dan Move Assignment. Jika hanya menggunakan smart pointers/STL, terapkan Rule of Zero.
10. **C** — Sesuai taksonomi ISO C++, `xvalue` adalah *glvalue* (memiliki identitas) yang juga merupakan *rvalue* (sumber dayanya dapat diambil alih). Sebaliknya, `prvalue` tidak memiliki representasi identitas alamat yang dapat diambil.

#### Kunci Bagian C (Analisis Skenario Produksi):
11. **Diagnosis**: Terjadi fragmentasi eksternal memori heap yang parah (*Heap Fragmentation*) disertai *Lock Contention* pada allocator global `glibc` akibat alokasi/dealokasi jutaan objek kecil secara acak dan berulang.
    **Solusi**: Ganti alokator global pada hot-path dengan *Custom Memory Arena / Pool Allocator* atau alokator produksi multi-thread berperforma tinggi seperti `jemalloc` / `tcmalloc`. Gunakan model zero-allocation di dalam *request handling loop*.
12. **Diagnosis**: Menghapus objek kelas turunan melalui pointer kelas dasar yang memiliki destruktor non-virtual menghasilkan *Undefined Behavior*. Secara mekanis, compiler hanya meng-generate pemanggilan instruksi destruktor `IConnection::~IConnection()`, sedangkan destruktor kelas implementasi `ConnectionSession::~ConnectionSession()` tidak pernah dieksekusi. Akibatnya, seluruh alokasi internal (seperti socket handle, memory buffers, string) di `ConnectionSession` bocor (*leaked*).
    **Solusi**: Deklarasikan `virtual ~IConnection() = default;` pada antarmuka dasar.
13. **Diagnosis**: Ukuran data 48 bytes yang tidak teratur menyebabkan *strided memory access* yang tidak ramah cache line (64 bytes). Beberapa data melintasi batas dua *cache line* (*cache-line splitting*). Selain itu, tata letak data kemungkinan besar berorientasi OOP (*Array of Structures* - AoS), padahal algoritma hanya memproses 1 atau 2 field kalkulasi saja.
    **Solusi**: 
    1. Lakukan padding atau penyelarasan eksplisit sehingga ukuran struct pas membagi atau mengisi baris cache (misal: 64 bytes).
    2. Ubah paradigma desain dari AoS (*Array of Structures*) ke SoA (*Structure of Arrays*): alih-alih `std::vector<QuoteData>`, buat `struct Quotes { std::vector<double> prices; std::vector<uint32_t> volumes; };` sehingga komputasi loop membaca array kontigu tanpa interupsi cache misses (*spatial locality* optimal) dan membuka jalan bagi auto-vectorization SIMD.

---

## 16. Summary

- **Tata Letak Objek & Polymorphism**: Memahami bahwa polimorfisme dinamis memiliki konsekuensi riil pada runtime: *indirection overhead* melalui `vptr`/`vtable` dan potensi rusaknya struktur data akibat *object slicing* jika tidak dikelola via pointer/referensi.
- **Value Categories & Move Mechanics**: Kategori nilai (`lvalue`, `prvalue`, `xvalue`) adalah landasan optimasi zero-copy di modern C++. Menandai `noexcept` pada move operations adalah kewajiban arsitektural untuk menjamin integrasi aman dengan standard library.
- **Simpati Mekanikal & Memori Determinisme**: Performa software modern tidak hanya diukur dari notasi Big-O, melainkan bagaimana data diletakkan di memori fisik. Penyelarasan memori (`alignment`), penataan struktur untuk meminimalkan *padding*, eliminasi *false sharing*, dan substitusi alokasi heap dengan *Memory Pool/Arena* adalah pembeda utama antara software enterprise amatir dan sistem berdaya tahan tinggi (*mission-critical systems*).