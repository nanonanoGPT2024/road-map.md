# C++ Modern Engineering
## Kurikulum Komprehensif — Standar GEMINI.md

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GEMINI CURRICULUM STANDARD v2.1 | TRACK: Systems Engineering | LANG: C++20/23
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 📋 DAFTAR ISI

- [Course Overview](#-course-overview)
- [Profil Peserta](#-profil-peserta)
- [Technology Stack](#-technology-stack)
- [Learning Roadmap — Pohon ASCII](#-learning-roadmap--pohon-ascii-10-bab)
- [Navigasi Detail Bab 01–10](#-navigasi-detail-bab)
- [Capstone Project Enterprise](#-spesifikasi-capstone-project-enterprise)
- [Assessment & Sertifikasi](#-assessment--sertifikasi)
- [Referensi Standar](#-referensi-standar)

---

## 🎯 COURSE OVERVIEW

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    C++ MODERN ENGINEERING — COURSE BRIEF                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  Kode Kurikulum  : GEMINI-CPP-2024-ENT                                      │
│  Versi Standar   : C++20 (primer) / C++23 (advanced track)                  │
│  Total Durasi    : 320 Jam Pembelajaran Efektif                              │
│  Level           : Intermediate → Expert (Industry-Grade)                   │
│  Metodologi      : Project-Based Learning + Systems Thinking                │
│  Sertifikasi     : GEMINI Certified C++ Systems Engineer (GCCSE)            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Deskripsi Kurikulum

Kurikulum **C++ Modern Engineering** dirancang mengikuti jalur resmi [roadmap.sh/cpp](https://roadmap.sh/cpp) dengan ekstensi enterprise-grade yang mencakup rekayasa sistem nyata. Program ini membangun kompetensi dari fondasi bahasa C++ modern hingga arsitektur sistem terdistribusi berperforma tinggi, mencakup paradigma pemrograman kontemporer yang digunakan di industri teknologi kelas dunia (Google, Meta, Bloomberg, NVIDIA, Qualcomm).

Peserta akan menguasai **zero-cost abstractions**, **compile-time programming**, **concurrent systems**, dan **memory-safe engineering** — pilar utama C++ modern yang membedakan engineer junior dari senior systems architect.

### Kompetensi Akhir (Terminal Objectives)

| # | Kompetensi | Indikator Pencapaian |
|---|-----------|---------------------|
| K1 | **Language Mastery** | Menulis kode C++20/23 idiomatik, type-safe, dan zero-UB |
| K2 | **Memory Engineering** | Mengelola sumber daya dengan RAII, smart pointers, dan custom allocators |
| K3 | **Template Metaprogramming** | Merancang library generik dengan concepts, variadic templates, dan SFINAE |
| K4 | **Concurrent Systems** | Membangun sistem multithreaded lock-free dengan memory model yang benar |
| K5 | **Performance Engineering** | Melakukan profiling, benchmarking, dan optimasi cache-aware |
| K6 | **Systems Architecture** | Merancang komponen enterprise: engine, runtime, middleware |
| K7 | **Modern Toolchain** | Menguasai CMake, Conan/vcpkg, sanitizers, dan CI/CD pipeline |
| K8 | **Capstone Delivery** | Mengimplementasi sistem enterprise end-to-end dengan dokumentasi teknis |

---

## 👥 PROFIL PESERTA

```
┌──────────────────────────────────────────────────────────────────┐
│  PRASYARAT MASUK                                                  │
├──────────────────────────────────────────────────────────────────┤
│  ✅ Pemahaman dasar C atau C++ (sintaks, pointer, fungsi)         │
│  ✅ Familiar dengan terminal Linux/macOS atau WSL2                │
│  ✅ Pemahaman dasar struktur data (array, linked list, tree)      │
│  ✅ Konsep OOP minimal satu bahasa (Java/Python/C# diterima)      │
│                                                                   │
│  PROFIL IDEAL                                                     │
├──────────────────────────────────────────────────────────────────┤
│  🎯 Software Engineer yang ingin migrasi ke systems programming   │
│  🎯 Embedded/firmware engineer yang ingin naik ke modern C++      │
│  🎯 Game developer yang ingin memahami engine internals           │
│  🎯 CS graduate yang mempersiapkan karir di FAANG/systems roles   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🛠 TECHNOLOGY STACK

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  COMPILER & STANDARD                                                         │
│  ├── GCC 13+ / Clang 17+ / MSVC 2022+                                       │
│  ├── C++20 (wajib) → C++23 (Bab 8–10)                                       │
│  └── Compiler flags: -std=c++20 -Wall -Wextra -Wpedantic -fsanitize=address │
│                                                                               │
│  BUILD SYSTEM                                                                 │
│  ├── CMake 3.28+ (primary)                                                   │
│  ├── Ninja (build backend)                                                   │
│  └── Conan 2.x / vcpkg (package management)                                 │
│                                                                               │
│  TOOLING                                                                      │
│  ├── clang-format, clang-tidy (static analysis)                              │
│  ├── Valgrind, AddressSanitizer, ThreadSanitizer                             │
│  ├── Google Benchmark, Catch2/GTest (testing)                                │
│  ├── Perf, VTune, Heaptrack (profiling)                                      │
│  └── Doxygen + Sphinx (documentation)                                        │
│                                                                               │
│  LIBRARIES (Capstone)                                                         │
│  ├── Boost.Asio (async networking)                                           │
│  ├── {fmt} library (formatting)                                              │
│  ├── spdlog (logging)                                                        │
│  ├── nlohmann/json (serialization)                                           │
│  └── Protocol Buffers / FlatBuffers (binary serialization)                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🗺 LEARNING ROADMAP — POHON ASCII 10 BAB

```
C++ MODERN ENGINEERING — LEARNING TREE
════════════════════════════════════════════════════════════════════════════════

                    ┌─────────────────────────────┐
                    │   C++ MODERN ENGINEERING     │
                    │   Enterprise Curriculum      │
                    └──────────────┬──────────────┘
                                   │
          ╔════════════════════════╧════════════════════════╗
          ║           FOUNDATION LAYER (Bab 1–3)            ║
          ╚════════════════════════╤════════════════════════╝
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
┌───────┴────────┐       ┌─────────┴──────────┐    ┌─────────┴──────────┐
│   BAB 01       │       │   BAB 02            │    │   BAB 03           │
│ C++ Modern     │       │ Memory Management   │    │ Object-Oriented    │
│ Fundamentals   │       │ & Resource Safety   │    │ Design Modern      │
│                │       │                     │    │                    │
│ • Type System  │       │ • Stack vs Heap      │    │ • Classes & RAII   │
│ • Value Cat.   │       │ • Smart Pointers     │    │ • Inheritance      │
│ • Move Sem.    │       │ • RAII Pattern       │    │ • Polymorphism     │
│ • References   │       │ • Custom Allocators  │    │ • Design Patterns  │
│ • auto/decltype│       │ • Memory Model       │    │ • SOLID Principles │
│                │       │                     │    │                    │
│ ⏱ 28 Jam      │       │ ⏱ 32 Jam            │    │ ⏱ 30 Jam          │
└───────┬────────┘       └─────────┬──────────┘    └─────────┬──────────┘
        │                          │                          │
        └──────────────────────────┼──────────────────────────┘
                                   │
          ╔════════════════════════╧════════════════════════╗
          ║         INTERMEDIATE LAYER (Bab 4–6)            ║
          ╚════════════════════════╤════════════════════════╝
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
┌───────┴────────┐       ┌─────────┴──────────┐    ┌─────────┴──────────┐
│   BAB 04       │       │   BAB 05            │    │   BAB 06           │
│ Generic        │       │ Standard Library    │    │ Concurrent &       │
│ Programming &  │       │ Mastery (STL+)      │    │ Parallel Systems   │
│ Templates      │       │                     │    │                    │
│                │       │ • Containers        │    │ • Thread Model     │
│ • Function TMP │       │ • Iterators/Ranges  │    │ • Mutex/Atomics    │
│ • Class TMP    │       │ • Algorithms        │    │ • Memory Ordering  │
│ • Concepts     │       │ • std::ranges       │    │ • Async/Futures    │
│ • Variadic     │       │ • std::views        │    │ • Lock-free DS     │
│ • SFINAE/if    │       │ • String/IO/FS      │    │ • Coroutines       │
│   constexpr    │       │ • Chrono/Random     │    │                    │
│                │       │                     │    │                    │
│ ⏱ 36 Jam      │       │ ⏱ 30 Jam            │    │ ⏱ 38 Jam          │
└───────┬────────┘       └─────────┬──────────┘    └─────────┬──────────┘
        │                          │                          │
        └──────────────────────────┼──────────────────────────┘
                                   │
          ╔════════════════════════╧════════════════════════╗
          ║           ADVANCED LAYER (Bab 7–9)              ║
          ╚════════════════════════╤════════════════════════╝
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
┌───────┴────────┐       ┌─────────┴──────────┐    ┌─────────┴──────────┐
│   BAB 07       │       │   BAB 08            │    │   BAB 09           │
│ Compile-Time   │       │ Performance         │    │ Systems            │
│ Programming    │       │ Engineering         │    │ Programming        │
│                │       │                     │    │                    │
│ • constexpr    │       │ • CPU Architecture  │    │ • File I/O & mmap  │
│ • consteval    │       │ • Cache Optimization│    │ • Networking Async │
│ • constinit    │       │ • SIMD Intrinsics   │    │ • IPC Mechanisms   │
│ • TMP Advanced │       │ • Profiling Tools   │    │ • Plugin Systems   │
│ • Reflection   │       │ • Benchmarking      │    │ • FFI & C Interop  │
│   (C++23)      │       │ • Compiler Hints    │    │ • OS Abstractions  │
│ • Code Gen     │       │ • Allocator Tuning  │    │                    │
│                │       │                     │    │                    │
│ ⏱ 36 Jam      │       │ ⏱ 34 Jam            │    │ ⏱ 32 Jam          │
└───────┬────────┘       └─────────┬──────────┘    └─────────┬──────────┘
        │                          │                          │
        └──────────────────────────┼──────────────────────────┘
                                   │
          ╔════════════════════════╧════════════════════════╗
          ║          MASTERY LAYER (Bab 10)                 ║
          ╚════════════════════════╤════════════════════════╝
                                   │
                         ┌─────────┴──────────┐
                         │   BAB 10            │
                         │ Enterprise          │
                         │ Architecture &      │
                         │ Capstone Project    │
                         │                     │
                         │ • Library Design    │
                         │ • API Stability     │
                         │ • CI/CD Pipeline    │
                         │ • Documentation     │
                         │ • Code Review       │
                         │ • Capstone: HFT     │
                         │   Order Book Engine │
                         │                     │
                         │ ⏱ 44 Jam           │
                         └─────────┬──────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │  🏆 GCCSE CERTIFICATION      │
                    │  GEMINI Certified C++        │
                    │  Systems Engineer            │
                    └─────────────────────────────┘

════════════════════════════════════════════════════════════════════════════════
 TOTAL: 320 JAM  |  10 BAB  |  3 LAYER  |  1 CAPSTONE ENTERPRISE PROJECT
════════════════════════════════════════════════════════════════════════════════
```

---

## 📚 NAVIGASI DETAIL BAB

---

### 📘 BAB 01 — C++ Modern Fundamentals

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 01: C++ MODERN FUNDAMENTALS                                             │
│  Durasi: 28 Jam  |  Layer: Foundation  |  Prasyarat: Sintaks C++ Dasar      │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 🎯 Tujuan Pembelajaran Bab

Setelah menyelesaikan bab ini, peserta mampu menulis kode C++20 yang idiomatik dengan pemahaman mendalam tentang sistem tipe, kategori nilai, dan semantik move — fondasi yang membedakan C++ modern dari C++98/03.

#### 📖 Materi Pembelajaran

**Modul 1.1 — Evolusi C++ dan Philosophy Modern** *(3 Jam)*
```
├── Sejarah standar: C++11 → C++14 → C++17 → C++20 → C++23
├── Zero-overhead abstraction principle (Bjarne Stroustrup)
├── The C++ Core Guidelines — mengapa dan bagaimana
├── Undefined Behavior (UB): definisi, konsekuensi, deteksi
└── Setup toolchain: GCC/Clang + CMake + sanitizers
```

**Modul 1.2 — Type System Modern** *(5 Jam)*
```
├── Fundamental types: ukuran, alignment, representasi
├── Fixed-width integers: <cstdint> dan penggunaannya
├── Type aliases: using vs typedef — kapan menggunakan mana
├── auto type deduction: aturan, edge cases, pitfalls
├── decltype dan decltype(auto): perbedaan dan use cases
├── Structured bindings (C++17): destructuring types
└── std::optional, std::variant, std::any — sum types
```

**Modul 1.3 — Value Categories** *(4 Jam)*
```
├── lvalue, rvalue, xvalue, prvalue, glvalue — taksonomi lengkap
├── Mengapa value categories penting untuk performance
├── Reference collapsing rules
├── std::move: apa yang sebenarnya dilakukan (dan tidak dilakukan)
├── std::forward dan perfect forwarding
└── Guaranteed copy elision (C++17): RVO dan NRVO
```

**Modul 1.4 — Move Semantics Deep Dive** *(5 Jam)*
```
├── Copy constructor vs move constructor: kapan dipanggil
├── Rule of Zero, Rule of Three, Rule of Five
├── Noexcept dan move semantics: mengapa kritis untuk STL
├── Implementing move-only types (unique ownership)
├── std::exchange: idiom untuk move implementation
└── Return value optimization vs explicit std::move
```

**Modul 1.5 — Modern Control Flow & Expressions** *(4 Jam)*
```
├── if constexpr: compile-time branching
├── if dengan initializer (C++17)
├── Range-based for: detail implementasi dan pitfalls
├── Lambdas: capture modes, generic lambdas, recursive lambdas
├── Immediately Invoked Lambda Expression (IILE)
└── Spaceship operator <=> dan three-way comparison
```

**Modul 1.6 — Namespaces, Modules & Linkage** *(4 Jam)*
```
├── Namespace best practices: inline namespace, nested namespace
├── Anonymous namespace vs static: internal linkage
├── C++20 Modules: module units, import, export
│   ├── Named modules vs header units
│   ├── Module partitions
│   └── Interoperability dengan header tradisional
└── ODR (One Definition Rule): aturan dan pelanggaran umum
```

**Modul 1.7 — Error Handling Modern** *(3 Jam)*
```
├── Exception safety: basic, strong, nothrow guarantees
├── std::expected (C++23): functional error handling
├── Error codes vs exceptions: kapan menggunakan mana
├── noexcept specification: dampak pada optimasi
└── RAII sebagai error handling mechanism
```

#### 🔬 Lab & Praktikum

| Lab | Judul | Durasi | Deliverable |
|-----|-------|--------|-------------|
| L1.1 | **Type Deduction Detective** | 2 Jam | Program analisis type deduction dengan `typeid` dan `__PRETTY_FUNCTION__` |
| L1.2 | **Move Semantics Profiler** | 3 Jam | Class dengan move semantics + benchmark copy vs move |
| L1.3 | **Lambda Expression Library** | 2 Jam | Mini functional library: map, filter, reduce dengan lambdas |
| L1.4 | **Module Migration** | 2 Jam | Konversi header-based library ke C++20 modules |

#### ✅ Assessment Bab 01

```
Quiz Teori          : 20 soal pilihan ganda (30 menit)
Coding Challenge    : Implementasi string_view wrapper dengan move semantics
Peer Code Review    : Review kode sesama peserta dengan checklist Core Guidelines
Passing Score       : 75% (teori) + Functional (praktik)
```

#### 📚 Referensi Bab 01

- Stroustrup, B. — *A Tour of C++, 3rd Edition* (Ch. 1–6)
- Meyers, S. — *Effective Modern C++* (Items 1–17)
- cppreference.com — Value categories, Type deduction
- CppCon 2022: "Back to Basics: Move Semantics" — Andreas Fertig

---

### 📘 BAB 02 — Memory Management & Resource Safety

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 02: MEMORY MANAGEMENT & RESOURCE SAFETY                                 │
│  Durasi: 32 Jam  |  Layer: Foundation  |  Prasyarat: Bab 01                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 🎯 Tujuan Pembelajaran Bab

Peserta mampu merancang sistem manajemen memori yang aman, efisien, dan bebas dari memory leaks, dangling pointers, dan undefined behavior terkait memori — menggunakan RAII sebagai paradigma utama.

#### 📖 Materi Pembelajaran

**Modul 2.1 — Memory Architecture** *(4 Jam)*
```
├── Stack memory: layout, growth direction, stack frame
├── Heap memory: allocator internals, fragmentation
├── Static/global storage: initialization order fiasco
├── Thread-local storage (TLS)
├── Virtual memory: pages, TLB, page faults
└── Memory alignment: alignof, alignas, std::aligned_storage
```

**Modul 2.2 — Raw Pointer Mastery (dan Mengapa Menghindarinya)** *(3 Jam)*
```
├── Pointer arithmetic: rules dan undefined behavior
├── Pointer vs reference: kapan menggunakan mana
├── Null pointer: nullptr vs NULL vs 0
├── Dangling pointer: penyebab dan deteksi
├── Wild pointer dan use-after-free
└── Pointer aliasing dan strict aliasing rule
```

**Modul 2.3 — RAII: Resource Acquisition Is Initialization** *(5 Jam)*
```
├── RAII philosophy: resource lifetime = object lifetime
├── Destructor guarantees: stack unwinding dan exception safety
├── Implementing RAII wrappers: file handle, mutex, socket
├── ScopeGuard pattern: defer-like mechanism
├── RAII vs garbage collection: trade-offs
└── Common RAII anti-patterns dan cara memperbaikinya
```

**Modul 2.4 — Smart Pointers** *(8 Jam)*
```
├── std::unique_ptr
│   ├── Ownership semantics: single owner
│   ├── Custom deleters: lambda, functor, function pointer
│   ├── unique_ptr<T[]>: array ownership
│   └── make_unique vs new: mengapa make_unique lebih aman
│
├── std::shared_ptr
│   ├── Reference counting internals: control block
│   ├── Thread safety: reference count vs pointed object
│   ├── make_shared: single allocation optimization
│   ├── enable_shared_from_this: safe this sharing
│   └── Circular reference problem
│
├── std::weak_ptr
│   ├── Breaking circular references
│   ├── Observer pattern implementation
│   └── lock() dan expired(): safe access pattern
│
└── Smart pointer guidelines
    ├── Passing smart pointers ke fungsi: by value vs by ref
    ├── Returning smart pointers dari fungsi
    └── Raw pointer sebagai non-owning observer
```

**Modul 2.5 — Custom Allocators** *(6 Jam)*
```
├── std::allocator interface: requirements dan concepts
├── Pool allocator: fixed-size block allocation
├── Arena/bump allocator: linear allocation
├── Stack allocator: LIFO allocation
├── Allocator-aware containers: PMR (Polymorphic Memory Resources)
│   ├── std::pmr::memory_resource
│   ├── std::pmr::monotonic_buffer_resource
│   ├── std::pmr::pool_options
│   └── std::pmr::vector, map, string
└── Benchmarking allocator performance
```

**Modul 2.6 — Memory Safety Tools** *(4 Jam)*
```
├── AddressSanitizer (ASan): heap/stack overflow, use-after-free
├── MemorySanitizer (MSan): uninitialized memory reads
├── UndefinedBehaviorSanitizer (UBSan): UB detection
├── Valgrind Memcheck: leak detection
├── Heaptrack: heap allocation profiling
└── Static analysis: clang-tidy memory checks
```

**Modul 2.7 — C++20 Memory Features** *(2 Jam)*
```
├── std::span: non-owning view atas contiguous memory
├── std::bit_cast: type-safe reinterpretation
├── constexpr new/delete (C++20)
└── Destroying delete (C++20)
```

#### 🔬 Lab & Praktikum

| Lab | Judul | Durasi | Deliverable |
|-----|-------|--------|-------------|
| L2.1 | **Memory Leak Hunter** | 3 Jam | Perbaiki 10 program bermasalah menggunakan ASan + Valgrind |
| L2.2 | **Smart Pointer Zoo** | 3 Jam | Implementasi graph dengan shared/weak_ptr, deteksi cycle |
| L2.3 | **Custom Pool Allocator** | 4 Jam | Pool allocator dengan benchmark vs std::allocator |
| L2.4 | **PMR Container Benchmark** | 2 Jam | Perbandingan PMR vs standard containers dalam hot loop |

#### ✅ Assessment Bab 02

```
Quiz Teori          : 25 soal (memory model, smart pointer semantics)
Coding Challenge    : Implementasi unique_ptr dari scratch
Memory Audit        : Analisis program legacy dengan sanitizers
Passing Score       : 75% (teori) + Zero leaks (praktik)
```

---

### 📘 BAB 03 — Object-Oriented Design Modern

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 03: OBJECT-ORIENTED DESIGN MODERN                                       │
│  Durasi: 30 Jam  |  Layer: Foundation  |  Prasyarat: Bab 01–02              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 🎯 Tujuan Pembelajaran Bab

Peserta mampu merancang hierarki kelas yang bersih, extensible, dan maintainable menggunakan prinsip OOP modern C++ — melampaui sintaks menuju arsitektur yang sesungguhnya.

#### 📖 Materi Pembelajaran

**Modul 3.1 — Class Design Mastery** *(5 Jam)*
```
├── Class vs struct: konvensi dan semantik
├── Member initialization: MIL (Member Initializer List) vs assignment
├── Delegating constructors (C++11)
├── Inherited constructors (C++11): using Base::Base
├── Explicit constructors dan conversion operators
├── Aggregate initialization (C++20): designated initializers
└── Class layout: padding, packing, #pragma pack
```

**Modul 3.2 — Inheritance & Polymorphism** *(6 Jam)*
```
├── Public vs protected vs private inheritance
├── Virtual functions: vtable internals, vptr overhead
├── Pure virtual functions dan abstract classes
├── Override dan final: compile-time safety
├── Virtual destructor: mengapa wajib untuk polymorphic base
├── Covariant return types
├── Multiple inheritance: diamond problem, virtual inheritance
└── Non-virtual interface (NVI) pattern
```

**Modul 3.3 — SOLID Principles dalam C++** *(5 Jam)*
```
├── Single Responsibility Principle
│   └── Contoh: memisahkan parsing, validation, storage
├── Open/Closed Principle
│   └── Extension via templates vs virtual dispatch
├── Liskov Substitution Principle
│   └── Behavioral subtyping dalam C++
├── Interface Segregation Principle
│   └── Pure abstract classes sebagai interfaces
└── Dependency Inversion Principle
    └── Dependency injection patterns dalam C++
```

**Modul 3.4 — Design Patterns dalam C++ Modern** *(8 Jam)*
```
├── Creational Patterns
│   ├── Factory Method: virtual constructor idiom
│   ├── Abstract Factory: family of objects
│   ├── Builder: fluent interface dengan method chaining
│   └── Singleton: thread-safe dengan std::call_once
│
├── Structural Patterns
│   ├── CRTP (Curiously Recurring Template Pattern): static polymorphism
│   ├── Mixin: multiple inheritance tanpa diamond problem
│   ├── Pimpl (Pointer to Implementation): ABI stability
│   └── Adapter: wrapping legacy interfaces
│
└── Behavioral Patterns
    ├── Observer: event system dengan std::function
    ├── Strategy: policy-based design
    ├── Command: undo/redo dengan lambdas
    └── Visitor: std::visit dengan std::variant
```

**Modul 3.5 — Type Erasure** *(4 Jam)*
```
├── Mengapa type erasure: decoupling concrete types
├── std::function: implementasi internal
├── std::any: type-safe void*
├── Manual type erasure: small buffer optimization
└── Concept-based polymorphism (Sean Parent style)
```

**Modul 3.6 — C++20 OOP Features** *(2 Jam)*
```
├── Concepts sebagai interface contracts
├── Aggregate improvements
└── Designated initializers untuk class-like structs
```

#### 🔬 Lab & Praktikum

| Lab | Judul | Durasi | Deliverable |
|-----|-------|--------|-------------|
| L3.1 | **CRTP Static Polymorphism** | 3 Jam | Shape hierarchy dengan CRTP vs virtual — benchmark perbandingan |
| L3.2 | **Event System** | 3 Jam | Observer pattern dengan type erasure dan std::function |
| L3.3 | **Plugin Architecture** | 4 Jam | Pimpl + factory pattern untuk plugin system |
| L3.4 | **Design Pattern Refactoring** | 2 Jam | Refactor legacy code ke modern C++ patterns |

#### ✅ Assessment Bab 03

```
Quiz Teori          : 20 soal (OOP concepts, pattern recognition)
Design Challenge    : Rancang class hierarchy untuk domain tertentu
Code Review         : Identifikasi SOLID violations dalam kode yang diberikan
Passing Score       : 75% (teori) + Design approval (praktik)
```

---

### 📘 BAB 04 — Generic Programming & Templates

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 04: GENERIC PROGRAMMING & TEMPLATES                                     │
│  Durasi: 36 Jam  |  Layer: Intermediate  |  Prasyarat: Bab 01–03            │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 🎯 Tujuan Pembelajaran Bab

Peserta mampu merancang dan mengimplementasi library generik yang type-safe, efisien, dan ekspresif menggunakan template C++ modern — dari function templates sederhana hingga template metaprogramming tingkat lanjut.

#### 📖 Materi Pembelajaran

**Modul 4.1 — Function Templates** *(4 Jam)*
```
├── Template argument deduction: aturan lengkap
├── Explicit template arguments: kapan diperlukan
├── Template overloading vs specialization
├── Abbreviated function templates (C++20): auto parameters
├── Forwarding references vs rvalue references
└── Perfect forwarding: std::forward deep dive
```

**Modul 4.2 — Class Templates** *(5 Jam)*
```
├── Class template syntax dan instantiation
├── Member function templates
├── Template template parameters
├── Default template arguments
├── Partial class template specialization
├── Full specialization: pitfalls dan best practices
└── CTAD (Class Template Argument Deduction, C++17)
    ├── Deduction guides: user-defined
    └── CTAD dengan aggregates (C++20)
```

**Modul 4.3 — C++20 Concepts** *(8 Jam)*
```
├── Mengapa Concepts: masalah dengan SFINAE
├── Concept syntax: requires clause dan requires expression
├── Built-in concepts: <concepts> header
│   ├── std::same_as, std::derived_from, std::convertible_to
│   ├── std::integral, std::floating_point, std::arithmetic
│   ├── std::invocable, std::predicate, std::relation
│   └── std::ranges concepts
├── Defining custom concepts
│   ├── Simple type constraints
│   ├── Compound requirements
│   ├── Nested requirements
│   └── Type requirements
├── Concept subsumption: ordering dan overload resolution
├── Abbreviated templates dengan concepts
└── Concepts sebagai dokumentasi dan error messages
```

**Modul 4.4 — Variadic Templates** *(6 Jam)*
```
├── Parameter packs: syntax dan expansion
├── sizeof... operator
├── Fold expressions (C++17): unary dan binary
├── Recursive variadic templates: base case pattern
├── Variadic class templates: tuple-like structures
├── Index sequences: std::index_sequence
├── Implementing std::tuple dari scratch
└── Variadic CRTP: mixin composition
```

**Modul 4.5 — SFINAE & Type Traits** *(6 Jam)*
```
├── SFINAE: Substitution Failure Is Not An Error
├── std::enable_if: enabling/disabling overloads
├── Type traits: <type_traits> lengkap
│   ├── Type categories: is_integral, is_class, etc.
│   ├── Type properties: is_const, is_volatile, etc.
│   ├── Type relationships: is_same, is_base_of, etc.
│   └── Type transformations: remove_cv, add_pointer, etc.
├── void_t: detection idiom
├── std::conditional: compile-time if-else untuk types
├── Custom type traits: implementing dari scratch
└── if constexpr sebagai SFINAE replacement (C++17)
```

**Modul 4.6 — Template Metaprogramming (TMP)** *(5 Jam)*
```
├── Compile-time computation: factorial, fibonacci
├── Type lists: cons, head, tail operations
├── Compile-time sorting dan searching
├── Policy-based design: Alexandrescu style
├── Expression templates: lazy evaluation
└── Boost.Hana style: heterogeneous programming
```

**Modul 4.7 — Template Best Practices** *(2 Jam)*
```
├── Explicit instantiation: controlling compilation
├── Extern templates: reducing compilation time
├── Template compilation model: inclusion vs export
├── Readable error messages dengan Concepts
└── Template debugging techniques
```

#### 🔬 Lab & Praktikum

| Lab | Judul | Durasi | Deliverable |
|-----|-------|--------|-------------|
| L4.1 | **Concept-Constrained Algorithms** | 4 Jam | Library algoritma dengan Concepts (sort, search, transform) |
| L4.2 | **Tuple dari Scratch** | 4 Jam | Implementasi std::tuple dengan variadic templates |
| L4.3 | **Type-Safe Units Library** | 4 Jam | Dimensional analysis library (meter, second, kilogram) |
| L4.4 | **Static Reflection Lite** | 3 Jam | Struct field enumeration dengan TMP |

#### ✅ Assessment Bab 04

```
Quiz Teori          : 25 soal (template deduction, concepts, SFINAE)
Coding Challenge    : Implementasi std::optional dari scratch dengan concepts
Template Puzzle     : Debug 5 template error messages
Passing Score       : 75% (teori) + Functional + Concept-constrained (praktik)
```

---

### 📘 BAB 05 — Standard Library Mastery (STL+)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 05: STANDARD LIBRARY MASTERY (STL+)                                     │
│  Durasi: 30 Jam  |  Layer: Intermediate  |  Prasyarat: Bab 01–04            │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 🎯 Tujuan Pembelajaran Bab

Peserta mampu memilih dan menggunakan container, algoritma, dan utilitas standard library secara optimal — memahami kompleksitas, trade-off, dan implementasi internal untuk keputusan engineering yang tepat.

#### 📖 Materi Pembelajaran

**Modul 5.1 — Containers Deep Dive** *(7 Jam)*
```
├── Sequence Containers
│   ├── std::vector: amortized growth, reallocation, reserve
│   ├── std::deque: segmented memory, iterator invalidation
│   ├── std::list: cache unfriendly, splice operations
│   ├── std::forward_list: minimal overhead linked list
│   └── std::array: stack-allocated, constexpr-friendly
│
├── Associative Containers
│   ├── std::map/set: Red-Black tree internals
│   ├── std::multimap/multiset: duplicate keys
│   ├── std::unordered_map/set: hash table internals
│   │   ├── Hash functions: std::hash, custom hash
│   │   ├── Load factor dan rehashing
│   │   └── Collision resolution: chaining
│   └── Container selection guide: decision tree
│
└── Container Adapters
    ├── std::stack, std::queue, std::priority_queue
    └── Underlying container customization
```

**Modul 5.2 — Iterators & Ranges (C++20)** *(6 Jam)*
```
├── Iterator categories: input, output, forward, bidirectional, random
├── Iterator traits dan iterator_category
├── C++20 Ranges: range concepts
│   ├── std::ranges::range, std::ranges::view
│   ├── std::ranges::input_range, output_range, etc.
│   └── Range-based algorithms: std::ranges::sort, find, etc.
├── Views: lazy evaluation pipeline
│   ├── std::views::filter, transform, take, drop
│   ├── std::views::zip (C++23), enumerate (C++23)
│   ├── std::views::iota, repeat (C++23)
│   └── Composing views dengan pipe operator |
├── Custom range adaptors
└── Sentinels: unbounded ranges
```

**Modul 5.3 — Algorithms Mastery** *(5 Jam)*
```
├── Non-modifying: find, count, all_of, any_of, none_of
├── Modifying: copy, move, transform, replace, fill
├── Sorting: sort, stable_sort, partial_sort, nth_element
├── Binary search: lower_bound, upper_bound, equal_range
├── Set operations: set_union, set_intersection, set_difference
├── Numeric: accumulate, reduce, transform_reduce, inclusive_scan
├── Parallel algorithms (C++17): execution policies
│   ├── std::execution::seq, par, par_unseq
│   └── Thread safety requirements
└── Algorithm composition dengan ranges
```

**Modul 5.4 — String & Text Processing** *(3 Jam)*
```
├── std::string: SSO (Small String Optimization) internals
├── std::string_view: non-owning, zero-copy
├── std::string_view pitfalls: lifetime issues
├── String formatting: std::format (C++20)
│   ├── Format specifiers: width, precision, fill
│   ├── Custom formatters: std::formatter specialization
│   └── std::print (C++23)
└── Regular expressions: std::regex (dan alternatifnya)
```

**Modul 5.5 — Time, Random & Filesystem** *(4 Jam)*
```
├── <chrono>: clocks, time points, durations
│   ├── std::chrono::system_clock, steady_clock, high_resolution_clock
│   ├── Duration literals: 1s, 500ms, 100us
│   └── Calendar dan timezone (C++20)
├── <random>: proper random number generation
│   ├── Engines: mt19937, random_device
│   ├── Distributions: uniform, normal, bernoulli
│   └── Mengapa rand() berbahaya
└── <filesystem>: portable file operations
    ├── std::filesystem::path
    ├── Directory iteration
    └── File status dan permissions
```

**Modul 5.6 — Functional Utilities** *(3 Jam)*
```
├── std::function: type erasure untuk callables
├── std::bind vs lambdas: kapan menggunakan mana
├── std::invoke: uniform callable invocation
├── std::apply: tuple unpacking
├── std::transform_reduce: map-reduce pattern
└── Ranges functional composition
```

**Modul 5.7 — I/O Streams & Modern Alternatives** *(2 Jam)*
```
├── iostream: kelebihan dan kekurangan
├── std::format sebagai pengganti printf/cout
├── File I/O: fstream, binary mode
└── Memory-mapped I/O preview (detail di Bab 09)
```

#### 🔬 Lab & Praktikum

| Lab | Judul | Durasi | Deliverable |
|-----|-------|--------|-------------|
| L5.1 | **Container Benchmark Suite** | 3 Jam | Benchmark semua containers untuk operasi insert/lookup/iterate |
| L5.2 | **Ranges Pipeline Builder** | 3 Jam | Data processing pipeline dengan views composition |
| L5.3 | **Custom Formatter Library** | 2 Jam | std::formatter untuk custom types |
| L5.4 | **File System Explorer** | 2 Jam | CLI tool dengan std::filesystem |

#### ✅ Assessment Bab 05

```
Quiz Teori          : 20 soal (container selection, algorithm complexity)
Coding Challenge    : Implementasi word frequency counter dengan ranges
Performance Task    : Optimasi kode yang menggunakan container yang salah
Passing Score       : 75% (teori) + Optimal container choice (praktik)
```

---

### 📘 BAB 06 — Concurrent & Parallel Systems

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 06: CONCURRENT & PARALLEL SYSTEMS                                       │
│  Durasi: 38 Jam  |  Layer: Intermediate  |  Prasyarat: Bab 01–05            │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 🎯 Tujuan Pembelajaran Bab

Peserta mampu merancang dan mengimplementasi sistem concurrent yang benar, efisien, dan bebas dari data races, deadlocks, dan undefined behavior terkait threading — menggunakan C++ memory model sebagai fondasi.

#### 📖 Materi Pembelajaran

**Modul 6.1 — C++ Memory Model** *(6 Jam)*
```
├── Mengapa memory model diperlukan: hardware reordering
├── Sequential consistency: model ideal vs realitas
├── Happens-before relationship
├── Synchronizes-with relationship
├── Memory orders: relaxed, acquire, release, acq_rel, seq_cst
│   ├── std::memory_order_relaxed: counter tanpa sync
│   ├── std::memory_order_acquire/release: producer-consumer
│   ├── std::memory_order_acq_rel: read-modify-write
│   └── std::memory_order_seq_cst: total order (default)
├── Data race: definisi formal dan konsekuensi
└── Fence operations: std::atomic_thread_fence
```

**Modul 6.2 — Thread Management** *(4 Jam)*
```
├── std::thread: creation, join, detach
├── Thread lifecycle dan RAII wrapper
├── std::jthread (C++20): cooperative cancellation
│   ├── std::stop_token dan std::stop_source
│   └── Automatic join on destruction
├── Thread local storage: thread_local keyword
├── Hardware concurrency: std::thread::hardware_concurrency
└── Thread affinity dan NUMA awareness (platform-specific)
```

**Modul 6.3 — Synchronization Primitives** *(6 Jam)*
```
├── std::mutex: basic mutual exclusion
├── std::recursive_mutex: reentrant locking
├── std::timed_mutex: timeout-based locking
├── std::shared_mutex (C++17): reader-writer lock
├── Lock guards: RAII locking
│   ├── std::lock_guard: simple scoped lock
│   ├── std::unique_lock: flexible locking
│   ├── std::shared_lock: shared (read) locking
│   └── std::scoped_lock (C++17): multi-mutex deadlock-free
├── Condition variables
│   ├── std::condition_variable: wait/notify
│   ├── Spurious wakeups: mengapa predicate diperlukan
│   └── std::condition_variable_any
└── Semaphores (C++20): counting dan binary
    ├── std::counting_semaphore
    └── std::binary_semaphore
```

**Modul 6.4 — Atomic Operations** *(5 Jam)*
```
├── std::atomic<T>: lock-free guarantee
├── Atomic operations: load, store, exchange, compare_exchange
├── compare_exchange_weak vs compare_exchange_strong
├── Atomic arithmetic: fetch_add, fetch_sub, fetch_and, etc.
├── std::atomic_flag: simplest atomic type
├── Lock-free programming patterns
│   ├── Spinlock implementation
│   ├── Seqlock (sequence lock)
│   └── Hazard pointers preview
└── ABA problem: penyebab dan solusi
```

**Modul 6.5 — Async Programming** *(5 Jam)*
```
├── std::async: launching async tasks
│   ├── std::launch::async vs std::launch::deferred
│   └── Pitfalls: blocking destructor
├── std::future dan std::promise
│   ├── Shared state dan lifetime
│   ├── std::shared_future: multiple consumers
│   └── Exception propagation melalui future
├── std::packaged_task: wrapping callables
├── Task-based vs thread-based parallelism
└── Thread pool implementation dari scratch
```

**Modul 6.6 — C++20 Coroutines** *(6 Jam)*
```
├── Coroutine concepts: suspend, resume, destroy
├── co_await, co_yield, co_return
├── Promise type: customization point
├── Coroutine handle: std::coroutine_handle
├── Awaitable types: operator co_await
├── Generator: lazy sequence dengan co_yield
├── Async task: coroutine-based future
├── Coroutine vs thread: kapan menggunakan mana
└── Integration dengan Boost.Asio / networking
```

**Modul 6.7 — Lock-Free Data Structures** *(4 Jam)*
```
├── Lock-free queue: Michael-Scott queue
├── Lock-free stack: Treiber stack
├── Memory reclamation: epoch-based reclamation
├── Mengapa lock-free bukan selalu lebih cepat
└── Testing concurrent code: ThreadSanitizer
```

**Modul 6.8 — Parallel Algorithms & Patterns** *(2 Jam)*
```
├── Fork-join pattern
├── Pipeline pattern
├── Map-reduce dengan parallel algorithms
└── Work stealing: konsep dasar
```

#### 🔬 Lab & Praktikum

| Lab | Judul | Durasi | Deliverable |
|-----|-------|--------|-------------|
| L6.1 | **Memory Order Visualizer** | 3 Jam | Program demonstrasi memory ordering dengan atomic |
| L6.2 | **Thread Pool Implementation** | 4 Jam | Generic thread pool dengan work queue |
| L6.3 | **Lock-Free Queue** | 4 Jam | Michael-Scott queue dengan TSan verification |
| L6.4 | **Coroutine Generator** | 3 Jam | Lazy range generator dengan co_yield |
| L6.5 | **Concurrent Hash Map** | 3 Jam | Sharded hash map dengan reader-writer locks |

#### ✅ Assessment Bab 06

```
Quiz Teori          : 30 soal (memory model, synchronization, atomics)
Concurrency Audit   : Identifikasi data races dalam kode yang diberikan
Coding Challenge    : Producer-consumer dengan bounded buffer
ThreadSanitizer Run : Kode harus clean dari TSan reports
Passing Score       : 75% (teori) + Zero TSan errors (praktik)
```

---

### 📘 BAB 07 — Compile-Time Programming

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 07: COMPILE-TIME PROGRAMMING                                            │
│  Durasi: 36 Jam  |  Layer: Advanced  |  Prasyarat: Bab 01–06                │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 🎯 Tujuan Pembelajaran Bab

Peserta mampu memindahkan komputasi dari runtime ke compile-time, menghasilkan kode yang lebih cepat, lebih aman, dan lebih ekspresif — menggunakan seluruh arsenal compile-time programming C++20.

#### 📖 Materi Pembelajaran

**Modul 7.1 — constexpr Evolution** *(6 Jam)*
```
├── constexpr C++11: fungsi sederhana
├── constexpr C++14: local variables, loops, conditionals
├── constexpr C++17: if constexpr, lambdas
├── constexpr C++20
│   ├── constexpr virtual functions
│   ├── constexpr try-catch
│   ├── constexpr new/delete
│   ├── constexpr std::string dan std::vector
│   └── constexpr algorithms
├── consteval (C++20): immediate functions
│   ├── Perbedaan constexpr vs consteval
│   └── std::is_constant_evaluated()
└── constinit (C++20): initialization order guarantee
```

**Modul 7.2 — Compile-Time Data Structures** *(5 Jam)*
```
├── constexpr array: fixed-size compile-time arrays
├── Compile-time string: string literal processing
├── Compile-time hash map: perfect hashing
├── Compile-time sorting: constexpr sort
├── Compile-time regex: pattern matching
└── Lookup tables: sin/cos/log precomputed
```

**Modul 7.3 — Advanced Template Metaprogramming** *(8 Jam)*
```
├── Type lists: Loki/Boost.MPL style
│   ├── TypeList definition
│   ├── Length, At, IndexOf operations
│   └── Append, Erase, Replace operations
├── Compile-time algorithms
│   ├── Compile-time map/filter/reduce
│   └── Type transformation pipelines
├── CRTP advanced patterns
│   ├── Static interface checking
│   └── Mixin composition
├── Expression templates
│   ├── Lazy evaluation
│   ├── Matrix expression templates
│   └── Avoiding temporaries
└── Boost.Hana concepts: heterogeneous programming
```

**Modul 7.4 — Code Generation Techniques** *(5 Jam)*
```
├── X-Macros: repetitive code generation
├── Enum reflection dengan macros
├── Compile-time dispatch tables
├── String interning at compile time
└── Protocol buffer-like code generation
```

**Modul 7.5 — C++23 Reflection Preview** *(4 Jam)*
```
├── Static reflection proposal: P2996
├── ^T syntax: reflection operator
├── std::meta namespace
├── Iterating over struct members
├── Generating code from reflection
└── Current compiler support status
```

**Modul 7.6 — Compile-Time Testing** *(4 Jam)*
```
├── static_assert: compile-time assertions
├── Concept-based testing
├── constexpr unit tests
└── Compile-time fuzzing concepts
```

**Modul 7.7 — Build Time Optimization** *(4 Jam)*
```
├── Precompiled headers (PCH)
├── Unity builds
├── Explicit template instantiation
├── Modules vs headers: compilation speed
└── Measuring build time: ninja -t deps
```

#### 🔬 Lab & Praktikum

| Lab | Judul | Durasi | Deliverable |
|-----|-------|--------|-------------|
| L7.1 | **Compile-Time JSON Parser** | 4 Jam | constexpr JSON parser untuk config files |
| L7.2 | **Static Dispatch Table** | 3 Jam | Compile-time command dispatch dengan TMP |
| L7.3 | **Units Library (Compile-Time)** | 4 Jam | Dimensional analysis dengan zero runtime overhead |
| L7.4 | **Enum Reflection** | 3 Jam | Automatic enum-to-string dengan X-Macros + constexpr |

#### ✅ Assessment Bab 07

```
Quiz Teori          : 25 soal (constexpr rules, TMP, code generation)
Coding Challenge    : Compile-time state machine
Performance Proof   : Benchmark compile-time vs runtime computation
Passing Score       : 75% (teori) + Zero runtime overhead (praktik)
```

---

### 📘 BAB 08 — Performance Engineering

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 08: PERFORMANCE ENGINEERING                                             │
│  Durasi: 34 Jam  |  Layer: Advanced  |  Prasyarat: Bab 01–07                │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 🎯 Tujuan Pembelajaran Bab

Peserta mampu mengidentifikasi bottleneck performa secara sistematis, memahami hardware-software interaction, dan menerapkan optimasi yang terukur — dengan mindset "measure first, optimize second."

#### 📖 Materi Pembelajaran

**Modul 8.1 — CPU Architecture untuk Programmer C++** *(5 Jam)*
```
├── Pipeline: stages, hazards, branch prediction
├── Out-of-order execution: reorder buffer
├── Cache hierarchy: L1/L2/L3, cache lines (64 bytes)
├── Cache misses: cold, capacity, conflict
├── TLB: translation lookaside buffer
├── NUMA: non-uniform memory access
├── Prefetching: hardware dan software prefetch
└── Branch prediction: bimodal predictor, BTB
```

**Modul 8.2 — Cache-Friendly Data Structures** *(5 Jam)*
```
├── AoS vs SoA: Array of Structs vs Struct of Arrays
├── Cache line padding: false sharing prevention
├── Data-Oriented Design (DOD) principles
├── Hot/cold data splitting
├── Flat data structures vs pointer-heavy trees
├── Cache-oblivious algorithms
└── Memory access pattern analysis dengan perf
```

**Modul 8.3 — Profiling & Benchmarking** *(6 Jam)*
```
├── Profiling tools
│   ├── perf: Linux performance counters
│   ├── Intel VTune: microarchitecture analysis
│   ├── Valgrind Callgrind: call graph profiling
│   └── Heaptrack: heap allocation profiling
├── Google Benchmark library
│   ├── Basic benchmark setup
│   ├── Benchmark fixtures
│   ├── Template benchmarks
│   ├── Custom counters dan statistics
│   └── Microbenchmark pitfalls: dead code elimination
├── Flame graphs: visualization
├── Compiler Explorer (godbolt.org): assembly analysis
└── Benchmark methodology: statistical significance
```

**Modul 8.4 — Compiler Optimizations** *(5 Jam)*
```
├── Optimization levels: -O0, -O1, -O2, -O3, -Os, -Oz
├── Link-time optimization (LTO): -flto
├── Profile-guided optimization (PGO)
├── Inlining: __attribute__((always_inline)), [[likely]]
├── Branch hints: [[likely]], [[unlikely]] (C++20)
├── Restrict keyword: pointer aliasing hints
├── __builtin_expect: legacy branch hints
└── Reading assembly output: understanding compiler decisions
```

**Modul 8.5 — SIMD & Vectorization** *(6 Jam)*
```
├── SIMD concepts: SSE, AVX, AVX-512
├── Auto-vectorization: compiler requirements
├── Intrinsics: _mm256_add_ps, etc.
├── SIMD wrapper libraries: xsimd, highway
├── Vectorization-friendly code patterns
├── Alignment requirements untuk SIMD
└── Benchmarking SIMD vs scalar
```

**Modul 8.6 — Allocator Performance Tuning** *(4 Jam)*
```
├── malloc internals: glibc ptmalloc, jemalloc, tcmalloc
├── Replacing global allocator: operator new/delete
├── jemalloc vs tcmalloc: use cases
├── Memory pool tuning untuk hot paths
└── Allocation-free programming: object pools
```

**Modul 8.7 — I/O Performance** *(3 Jam)*
```
├── Buffered vs unbuffered I/O
├── Memory-mapped files: mmap performance
├── io_uring (Linux): async I/O
├── Zero-copy techniques: sendfile, splice
└── Network I/O optimization preview
```

#### 🔬 Lab & Praktikum

| Lab | Judul | Durasi | Deliverable |
|-----|-------|--------|-------------|
| L8.1 | **Cache Miss Detective** | 3 Jam | Analisis cache misses dengan perf + optimasi AoS→SoA |
| L8.2 | **Benchmark Suite** | 3 Jam | Google Benchmark untuk 5 algoritma berbeda |
| L8.3 | **SIMD Matrix Multiply** | 4 Jam | Matrix multiplication: scalar vs auto-vec vs intrinsics |
| L8.4 | **Allocator Shootout** | 2 Jam | Benchmark default vs jemalloc vs pool allocator |

#### ✅ Assessment Bab 08

```
Quiz Teori          : 25 soal (CPU architecture, profiling, optimization)
Performance Task    : Optimasi program dari 100ms ke <10ms
Benchmark Report    : Laporan tertulis dengan flame graph dan analysis
Passing Score       : 75% (teori) + 10x speedup achieved (praktik)
```

---

### 📘 BAB 09 — Systems Programming

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 09: SYSTEMS PROGRAMMING                                                 │
│  Durasi: 32 Jam  |  Layer: Advanced  |  Prasyarat: Bab 01–08                │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 🎯 Tujuan Pembelajaran Bab

Peserta mampu membangun komponen sistem tingkat rendah: networking, IPC, plugin systems, dan OS abstractions — menggunakan C++ sebagai bahasa systems programming yang sesungguhnya.

#### 📖 Materi Pembelajaran

**Modul 9.1 — Advanced File I/O** *(4 Jam)*
```
├── POSIX file operations: open, read, write, close
├── Memory-mapped files: mmap, munmap, msync
│   ├── Read-only mapping: shared file access
│   ├── Read-write mapping: in-place modification
│   └── Anonymous mapping: IPC shared memory
├── File locking: flock, fcntl
├── Async file I/O: io_uring basics
└── Cross-platform abstraction: std::filesystem + platform layer
```

**Modul 9.2 — Network Programming dengan Boost.Asio** *(8 Jam)*
```
├── Networking fundamentals: sockets, TCP/UDP
├── Boost.Asio architecture: io_context, executor
├── Synchronous I/O: blocking operations
├── Asynchronous I/O: async_read, async_write
├── Coroutine-based networking (C++20 + Asio)
│   ├── co_await dengan Asio
│   └── Structured concurrency
├── TCP server: acceptor, session management
├── TCP client: connection, reconnection
├── UDP: datagram operations
├── SSL/TLS: Boost.Asio SSL layer
└── HTTP/1.1 parser implementation
```

**Modul 9.3 — Inter-Process Communication** *(5 Jam)*
```
├── Pipes: anonymous dan named pipes
├── Shared memory: POSIX shm_open, mmap
├── Message queues: POSIX mq_open
├── Unix domain sockets: local IPC
├── Signals: signal handling dalam C++
└── Semaphores: POSIX sem_open
```

**Modul 9.4 — Plugin System Architecture** *(5 Jam)*
```
├── Dynamic loading: dlopen/dlsym (POSIX), LoadLibrary (Windows)
├── Plugin interface design: stable ABI requirements
├── Versioning: plugin API versioning
├── Hot reloading: unload dan reload plugins
├── Cross-platform abstraction layer
└── Security considerations: sandboxing plugins
```

**Modul 9.5 — C/C++ Interoperability** *(4 Jam)*
```
├── extern "C": name mangling dan linkage
├── Calling C dari C++: wrapping C libraries
├── Calling C++ dari C: C-compatible API design
├── ABI compatibility: what breaks ABI
├── Python bindings: pybind11 basics
└── WebAssembly: Emscripten basics
```

**Modul 9.6 — OS Abstractions** *(4 Jam)*
```
├── Process management: fork, exec, waitpid
├── Thread scheduling: priority, affinity
├── Memory management: mprotect, madvise
├── System calls: syscall interface
└── Cross-platform: Windows vs POSIX abstraction
```

**Modul 9.7 — Embedded & Bare-Metal C++** *(2 Jam)*
```
├── Freestanding C++: no standard library
├── Placement new: custom memory management
├── Volatile: hardware register access
├── Interrupt handlers dalam C++
└── RTOS integration basics
```

#### 🔬 Lab & Praktikum

| Lab | Judul | Durasi | Deliverable |
|-----|-------|--------|-------------|
| L9.1 | **Memory-Mapped Database** | 4 Jam | Key-value store dengan mmap persistence |
| L9.2 | **Async TCP Server** | 4 Jam | Echo server dengan Boost.Asio coroutines |
| L9.3 | **Plugin System** | 4 Jam | Hot-reloadable plugin system dengan dlopen |
| L9.4 | **IPC Benchmark** | 2 Jam | Latency comparison: pipe vs shm vs socket |

#### ✅ Assessment Bab 09

```
Quiz Teori          : 20 soal (networking, IPC, systems calls)
Systems Project     : Implementasi simple HTTP server
Cross-Platform Test : Kode harus compile di Linux dan macOS
Passing Score       : 75% (teori) + Functional server (praktik)
```

---

### 📘 BAB 10 — Enterprise Architecture & Capstone

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 10: ENTERPRISE ARCHITECTURE & CAPSTONE PROJECT                          │
│  Durasi: 44 Jam  |  Layer: Mastery  |  Prasyarat: Bab 01–09                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 🎯 Tujuan Pembelajaran Bab

Peserta mampu merancang, mengimplementasi, mendokumentasi, dan men-deliver sistem C++ enterprise-grade yang siap produksi — mengintegrasikan seluruh kompetensi dari Bab 01–09 dalam proyek nyata.

#### 📖 Materi Pembelajaran

**Modul 10.1 — Library & API Design** *(5 Jam)*
```
├── API design principles: minimal, complete, orthogonal
├── ABI stability: what breaks ABI, versioning strategies
├── Header-only vs compiled libraries: trade-offs
├── Semantic versioning: MAJOR.MINOR.PATCH
├── Deprecation strategies: [[deprecated]] attribute
├── Documentation-driven development
└── API review checklist
```

**Modul 10.2 — Modern CMake Mastery** *(5 Jam)*
```
├── Modern CMake: target-based approach
│   ├── add_library, add_executable
│   ├── target_include_directories
│   ├── target_link_libraries
│   └── target_compile_options
├── CMake presets: CMakePresets.json
├── Package management: find_package, FetchContent
├── Conan 2.x integration
├── vcpkg integration
├── Installing dan exporting: cmake install
└── CPack: packaging dan distribution
```

**Modul 10.3 — Testing Strategy** *(5 Jam)*
```
├── Unit testing: Catch2 / Google Test
│   ├── Test fixtures dan setup/teardown
│   ├── Parameterized tests
│   └── Mock objects: Google Mock
├── Integration testing
├── Fuzz testing: libFuzzer, AFL++
├── Property-based testing: RapidCheck
├── Mutation testing: concepts
├── Code coverage: gcov, llvm-cov
└── Test-driven development (TDD) workflow
```

**Modul 10.4 — CI/CD Pipeline untuk C++** *(4 Jam)*
```
├── GitHub Actions untuk C++
│   ├── Multi-platform matrix: Linux, macOS, Windows
│   ├── Compiler matrix: GCC, Clang, MSVC
│   └── Sanitizer runs dalam CI
├── Docker untuk C++ build environments
├── Artifact management: binary caching
├── Static analysis dalam CI: clang-tidy, cppcheck
└── Release automation: tagging, changelog
```

**Modul 10.5 — Code Quality & Review** *(3 Jam)*
```
├── C++ Core Guidelines enforcement
├── clang-format: style consistency
├── clang-tidy: static analysis rules
├── Code review checklist untuk C++
├── Technical debt management
└── Refactoring patterns untuk legacy C++
```

**Modul 10.6 — Documentation Engineering** *(2 Jam)*
```
├── Doxygen: API documentation
├── Sphinx + Breathe: documentation site
├── Architecture Decision Records (ADR)
└── README engineering: technical writing
```

**Modul 10.7 — Capstone Project Execution** *(20 Jam)*
```
└── [Lihat Spesifikasi Capstone Project Enterprise]
```

#### ✅ Assessment Bab 10

```
Architecture Review : Presentasi desain sistem (30 menit)
Code Review         : Senior engineer review seluruh codebase
Documentation Audit : Completeness dan accuracy check
CI/CD Verification  : Pipeline harus green di semua platform
Capstone Demo       : Live demonstration dengan load testing
Passing Score       : Semua kriteria capstone terpenuhi
```

---

## 🏆 SPESIFIKASI CAPSTONE PROJECT ENTERPRISE

```
┌─────────────────────────────────────────────────────────────────────────────┐
│           CAPSTONE PROJECT: HIGH-FREQUENCY TRADING ORDER BOOK ENGINE         │
│           "Nexus Order Book" — Enterprise C++ Systems Project                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 📋 Project Brief

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Nama Proyek    : Nexus Order Book Engine                                    │
│  Domain         : Financial Technology (FinTech) — High-Frequency Trading    │
│  Durasi         : 20 Jam (dalam Bab 10) + 4 Jam review                      │
│  Tim            : Individual atau tim 2 orang                                │
│  Repository     : GitHub dengan CI/CD pipeline aktif                         │
│  Deliverable    : Production-ready C++ library + CLI tool + dokumentasi      │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 🎯 Problem Statement

Sebuah perusahaan trading membutuhkan **order book engine** berperforma ultra-tinggi yang mampu memproses jutaan order per detik dengan latensi sub-microsecond. Engine ini harus menjadi fondasi sistem matching engine untuk exchange cryptocurrency atau saham.

**Tantangan Teknis Utama:**
- Latensi P99 < 1 microsecond untuk operasi order book
- Throughput > 5 juta order/detik pada single core
- Zero dynamic allocation pada hot path
- Thread-safe untuk concurrent market data consumers
- Persistent order book state dengan recovery capability

### 🏗 Arsitektur Sistem

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    NEXUS ORDER BOOK ENGINE — ARCHITECTURE                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        CLIENT LAYER                                  │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │    │
│  │  │  CLI Tool    │  │  C API       │  │  Network Feed (FIX/UDP)  │  │    │
│  │  │  (nexus-cli) │  │  (C wrapper) │  │  (Boost.Asio)            │  │    │
│  │  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘  │    │
│  └─────────┼─────────────────┼──────────────────────┼─────────────────┘    │
│            └─────────────────┼──────────────────────┘                       │
│                              │                                               │
│  ┌───────────────────────────▼─────────────────────────────────────────┐    │
│  │                      ENGINE CORE LAYER                               │    │
│  │                                                                       │    │
│  │  ┌─────────────────────────────────────────────────────────────┐    │    │
│  │  │                  OrderBook<Instrument>                       │    │    │
│  │  │  ┌─────────────────────┐  ┌──────────────────────────────┐  │    │    │
│  │  │  │   BidSide           │  │   AskSide                    │  │    │    │
│  │  │  │   (Price Desc)      │  │   (Price Asc)                │  │    │    │
│  │  │  │                     │  │                              │  │    │    │
│  │  │  │  PriceLevel[]       │  │  PriceLevel[]                │  │    │    │
│  │  │  │  ├── price          │  │  ├── price                   │  │    │    │
│  │  │  │  ├── total_qty      │  │  ├── total_qty               │  │    │    │
│  │  │  │  └── Order[]        │  │  └── Order[]                 │  │    │    │
│  │  │  └─────────────────────┘  └──────────────────────────────┘  │    │    │
│  │  └─────────────────────────────────────────────────────────────┘    │    │
│  │                                                                       │    │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │    │
│  │  │  MatchingEngine  │  │  OrderManager    │  │  EventPublisher  │  │    │
│  │  │  (FIFO matching) │  │  (ID → Order)    │  │  (lock-free)     │  │    │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    INFRASTRUCTURE LAYER                               │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │    │
│  │  │MemoryPool    │  │ Logger       │  │  Persistence (mmap WAL)  │  │    │
│  │  │(Pool Alloc.) │  │(spdlog/lock- │  │  Write-Ahead Log         │  │    │
│  │  │              │  │ free)        │  │                          │  │    │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 📦 Komponen Wajib

#### Komponen 1: Core Order Book Library (`libnexus`)

```cpp
// Contoh API yang harus diimplementasi

namespace nexus {

// Concepts untuk type safety
template<typename T>
concept Instrument = requires {
    typename T::price_type;
    typename T::quantity_type;
    { T::symbol } -> std::convertible_to<std::string_view>;
};

// Order types
enum class Side : uint8_t { Buy, Sell };
enum class OrderType : uint8_t { Limit, Market, IOC, FOK };
enum class OrderStatus : uint8_t { New, PartialFill, Filled, Cancelled, Rejected };

struct Order {
    uint64_t    order_id;
    uint64_t    timestamp_ns;   // nanosecond timestamp
    int64_t     price;          // fixed-point: price * 1e8
    uint64_t    quantity;
    uint64_t    remaining_qty;
    Side        side;
    OrderType   type;
    OrderStatus status;
};

struct Trade {
    uint64_t trade_id;
    uint64_t buy_order_id;
    uint64_t sell_order_id;
    int64_t  price;
    uint64_t quantity;
    uint64_t timestamp_ns;
};

// Event system
struct OrderBookEvent {
    enum class Type { OrderAdded, OrderCancelled, OrderFilled, TradeExecuted };
    Type    type;
    Order   order;
    Trade   trade;  // valid jika type == TradeExecuted
};

// Main order book interface
template<Instrument I>
class OrderBook {
public:
    // O(log n) untuk limit orders
    [[nodiscard]] std::expected<uint64_t, OrderError>
    add_order(Side side, int64_t price, uint64_t quantity, OrderType type) noexcept;

    // O(1) dengan order ID index
    [[nodiscard]] std::expected<void, OrderError>
    cancel_order(uint64_t order_id) noexcept;

    // O(1) amortized
    [[nodiscard]] std::expected<void, OrderError>
    modify_order(uint64_t order_id, uint64_t new_quantity) noexcept;

    // Market data queries — O(1)
    [[nodiscard]] std::optional<int64_t> best_bid() const noexcept;
    [[nodiscard]] std::optional<int64_t> best_ask() const noexcept;
    [[nodiscard]] int64_t spread() const noexcept;
    [[nodiscard]] uint64_t bid_depth(int64_t price) const noexcept;
    [[nodiscard]] uint64_t ask_depth(int64_t price) const noexcept;

    // Top-N levels — O(N)
    [[nodiscard]] std::span<const PriceLevel> top_bids(size_t n) const noexcept;
    [[nodiscard]] std::span<const PriceLevel> top_asks(size_t n) const noexcept;

    // Event subscription (lock-free)
    void subscribe(std::function<void(const OrderBookEvent&)> handler);

    // Statistics
    [[nodiscard]] OrderBookStats stats() const noexcept;
};

} // namespace nexus
```

#### Komponen 2: Matching Engine

```
Persyaratan Matching Engine:
├── FIFO (Price-Time Priority) matching algorithm
├── Market order: match against best available price
├── Limit order: add to book jika tidak match
├── IOC (Immediate-or-Cancel): match atau cancel
├── FOK (Fill-or-Kill): fill completely atau cancel
├── Partial fills: update remaining quantity
└── Trade generation: setiap match menghasilkan Trade event
```

#### Komponen 3: Memory Pool Allocator

```
Persyaratan Memory Pool:
├── Fixed-size block pool untuk Order objects
├── Zero dynamic allocation pada hot path
├── Thread-safe dengan lock-free free list
├── Configurable pool size (compile-time atau runtime)
├── Overflow handling: fallback ke heap atau error
└── Statistics: allocated, free, peak usage
```

#### Komponen 4: Persistence Layer (WAL)

```
Write-Ahead Log Requirements:
├── Memory-mapped file untuk zero-copy writes
├── Binary format: compact, versioned
├── Recovery: replay WAL untuk rebuild order book
├── Checkpointing: periodic snapshot
├── CRC32 checksums untuk integrity
└── Configurable sync policy: sync, async, none
```

#### Komponen 5: Network Feed (FIX-lite Protocol)

```
Network Requirements:
├── UDP multicast untuk market data broadcast
├── TCP untuk order entry (reliable)
├── Custom binary protocol (FIX-lite):
│   ├── Header: magic, version, msg_type, length, seq_num
│   ├── New Order: order_id, side, price, qty, type
│   ├── Cancel: order_id
│   ├── Trade: trade_id, buy_id, sell_id, price, qty
│   └── Snapshot: full order book state
├── Boost.Asio coroutines untuk async I/O
└── Sequence number gap detection
```

#### Komponen 6: CLI Tool (`nexus-cli`)

```
CLI Commands:
├── nexus-cli start --symbol BTCUSDT --port 8080
├── nexus-cli order add --side buy --price 50000 --qty 1.5
├── nexus-cli order cancel --id 12345
├── nexus-cli book show --symbol BTCUSDT --depth 10
├── nexus-cli stats --symbol BTCUSDT
├── nexus-cli replay --wal-file nexus.wal
└── nexus-cli bench --orders 1000000 --threads 4
```

### 📊 Kriteria Penilaian Capstone

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  RUBRIK PENILAIAN CAPSTONE — NEXUS ORDER BOOK ENGINE                         │
├────────────────────────────┬────────┬────────────────────────────────────────┤
│  Kriteria                  │  Bobot │  Indikator                             │
├────────────────────────────┼────────┼────────────────────────────────────────┤
│  Correctness               │  25%   │  Semua unit test pass, matching        │
│                            │        │  algorithm benar, edge cases handled   │
├────────────────────────────┼────────┼────────────────────────────────────────┤
│  Performance               │  25%   │  P99 latency < 1μs, throughput        │
│                            │        │  > 5M orders/sec, zero alloc hot path  │
├────────────────────────────┼────────┼────────────────────────────────────────┤
│  Code Quality              │  20%   │  Core Guidelines compliant, clang-tidy │
│                            │        │  clean, zero sanitizer errors          │
├────────────────────────────┼────────┼────────────────────────────────────────┤
│  Architecture              │  15%   │  Clean separation of concerns, SOLID,  │
│                            │        │  extensible design, proper abstractions │
├────────────────────────────┼────────┼────────────────────────────────────────┤
│  Testing                   │  10%   │  >80% coverage, fuzz tests, benchmark  │
│                            │        │  suite, integration tests              │
├────────────────────────────┼────────┼────────────────────────────────────────┤
│  Documentation             │  5%    │  Doxygen API docs, README, ADR,        │
│                            │        │  architecture diagram                  │
├────────────────────────────┼────────┼────────────────────────────────────────┤
│  TOTAL                     │  100%  │  Minimum passing: 75%                  │
└────────────────────────────┴────────┴────────────────────────────────────────┘
```

### 🎖 Bonus Challenges (Nilai Tambah)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BONUS CHALLENGES — Opsional untuk Nilai Distinction                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  🥇 GOLD   (+15%)  SIMD-accelerated price level scanning                    │
│             Implementasi AVX2 untuk mencari best bid/ask                     │
│                                                                               │
│  🥈 SILVER (+10%)  Lock-free event bus                                       │
│             SPSC/MPSC queue untuk event publishing tanpa mutex               │
│                                                                               │
│  🥉 BRONZE (+5%)   Python bindings                                           │
│             pybind11 wrapper untuk nexus library                             │
│                                                                               │
│  ⭐ SPECIAL (+10%) WebAssembly port                                          │
│             Compile ke WASM dengan Emscripten, demo di browser               │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 📁 Struktur Repository Wajib

```
nexus-order-book/
├── CMakeLists.txt                    # Root CMake
├── CMakePresets.json                 # Build presets
├── conanfile.py                      # Dependencies
├── README.md                         # Project documentation
├── ARCHITECTURE.md                   # System design document
├── CHANGELOG.md                      # Version history
│
├── include/
│   └── nexus/
│       ├── order_book.hpp            # Main public API
│       ├── order.hpp                 # Order types
│       ├── matching_engine.hpp       # Matching interface
│       ├── event.hpp                 # Event types
│       └── concepts.hpp              # C++20 concepts
│
├── src/
│   ├── order_book.cpp
│   ├── matching_engine.cpp
│   ├── memory_pool.cpp
│   ├── persistence/
│   │   ├── wal.cpp
│   │   └── snapshot.cpp
│   └── network/
│       ├── feed_server.cpp
│       └── order_gateway.cpp
│
├── cli/
│   └── nexus_cli.cpp                 # CLI tool
│
├── tests/
│   ├── unit/
│   │   ├── test_order_book.cpp
│   │   ├── test_matching.cpp
│   │   └── test_memory_pool.cpp
│   ├── integration/
│   │   └── test_full_system.cpp
│   └── fuzz/
│       └── fuzz_order_book.cpp
│
├── benchmarks/
│   ├── bench_order_book.cpp
│   ├── bench_matching.cpp
│   └── bench_memory_pool.cpp
│
├── docs/
│   ├── Doxyfile
│   ├── adr/
│   │   ├── 001-memory-pool-design.md
│   │   ├── 002-matching-algorithm.md
│   │   └── 003-persistence-strategy.md
│   └── diagrams/
│       └── architecture.puml
│
└── .github/
    └── workflows/
        ├── ci.yml                    # Main CI pipeline
        ├── sanitizers.yml            # Sanitizer runs
        └── benchmarks.yml            # Performance regression
```

### 🔄 CI/CD Pipeline Specification

```yaml
# .github/workflows/ci.yml — Spesifikasi Pipeline

Pipeline Stages:
├── 1. Build Matrix
│   ├── OS: ubuntu-22.04, macos-13, windows-2022
│   ├── Compiler: GCC-13, Clang-17, MSVC-2022
│   └── Standard: C++20, C++23
│
├── 2. Static Analysis
│   ├── clang-tidy (semua warnings sebagai errors)
│   └── cppcheck
│
├── 3. Test Suite
│   ├── Unit tests (Catch2)
│   ├── Integration tests
│   └── Code coverage (minimum 80%)
│
├── 4. Sanitizer Runs (Linux/Clang only)
│   ├── AddressSanitizer + LeakSanitizer
│   ├── ThreadSanitizer
│   └── UndefinedBehaviorSanitizer
│
├── 5. Benchmarks (Linux only)
│   ├── Google Benchmark run
│   ├── Performance regression check
│   └── Benchmark results sebagai CI artifact
│
└── 6. Documentation
    ├── Doxygen generation
    └── Deploy ke GitHub Pages
```

---

## 📊 ASSESSMENT & SERTIFIKASI

### Struktur Penilaian Keseluruhan

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SISTEM PENILAIAN KURIKULUM C++ MODERN ENGINEERING                           │
├──────────────────────────────────────┬────────┬────────────────────────────┤
│  Komponen                            │  Bobot │  Keterangan                │
├──────────────────────────────────────┼────────┼────────────────────────────┤
│  Quiz Teori (10 Bab × 10%)          │  20%   │  Rata-rata semua quiz      │
│  Lab & Praktikum (10 Bab)           │  25%   │  Semua lab harus pass      │
│  Mid-Course Project (Bab 5)         │  15%   │  STL-based data processor  │
│  Capstone Project (Bab 10)          │  35%   │  Nexus Order Book Engine   │
│  Peer Code Review                   │  5%    │  Kualitas review diberikan │
├──────────────────────────────────────┼────────┼────────────────────────────┤
│  TOTAL                               │  100%  │  Minimum lulus: 75%        │
└──────────────────────────────────────┴────────┴────────────────────────────┘
```

### Grade Scale

```
┌──────────────────────────────────────────────────────┐
│  GRADE  │  SKOR    │  PREDIKAT                        │
├─────────┼──────────┼──────────────────────────────────┤
│  A+     │  95–100% │  Distinction — Expert Level      │
│  A      │  90–94%  │  Excellent — Senior Engineer     │
│  B+     │  85–89%  │  Very Good — Mid-Senior Engineer │
│  B      │  80–84%  │  Good — Mid-Level Engineer       │
│  C+     │  75–79%  │  Satisfactory — Junior Engineer  │
│  C      │  70–74%  │  Pass (tanpa sertifikasi penuh)  │
│  F      │  < 70%   │  Fail — Remedial required        │
└──────────────────────────────────────────────────────┘
```

### Sertifikasi GCCSE

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  🏆 GEMINI CERTIFIED C++ SYSTEMS ENGINEER (GCCSE)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  Persyaratan:                                                                 │
│  ✅ Skor keseluruhan ≥ 75%                                                   │
│  ✅ Capstone project approved oleh senior reviewer                           │
│  ✅ Semua lab praktikum diselesaikan                                         │
│  ✅ Zero sanitizer errors pada submission akhir                              │
│  ✅ CI/CD pipeline green di semua platform                                   │
│                                                                               │
│  Sertifikat mencakup:                                                         │
│  📜 Digital certificate dengan verifiable credential                         │
│  🔗 GitHub badge untuk profil                                                │
│  📋 Transcript nilai per bab                                                 │
│  🎯 Capstone project showcase di GEMINI portfolio                            │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📚 REFERENSI STANDAR

### Buku Wajib

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 1 — WAJIB DIBACA                                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  [1] Stroustrup, B. (2022). A Tour of C++, 3rd Ed. Addison-Wesley           │
│  [2] Meyers, S. (2014). Effective Modern C++. O'Reilly                      │
│  [3] Williams, A. (2019). C++ Concurrency in Action, 2nd Ed. Manning        │
│  [4] Josuttis, N. (2022). C++20: The Complete Guide. NicoJosuttis           │
│                                                                               │
│  TIER 2 — SANGAT DIREKOMENDASIKAN                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  [5] Galowicz, J. (2017). C++17 STL Cookbook. Packt                         │
│  [6] Iglberger, K. (2022). C++ Software Design. O'Reilly                    │
│  [7] Alexandrescu, A. (2001). Modern C++ Design. Addison-Wesley             │
│  [8] Grimm, R. (2021). C++ Core Guidelines Explained. Leanpub               │
│                                                                               │
│  TIER 3 — REFERENSI LANJUTAN                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  [9]  Vandevoorde, D. et al. (2017). C++ Templates, 2nd Ed. Addison-Wesley  │
│  [10] Abrahams, D. & Gurtovoy, A. (2004). C++ Template Metaprogramming      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Online Resources

```
Standar & Referensi:
├── https://cppreference.com          — Referensi standar terlengkap
├── https://isocpp.org                — ISO C++ committee
├── https://isocpp.github.io/CppCoreGuidelines — Core Guidelines
└── https://roadmap.sh/cpp            — Official learning roadmap

Komunitas & Konferensi:
├── https://cppcon.org                — CppCon talks (YouTube)
├── https://meetingcpp.com            — Meeting C++ talks
├── https://reddit.com/r/cpp          — Community discussions
└── https://stackoverflow.com/questions/tagged/c%2B%2B

Tools Online:
├── https://godbolt.org               — Compiler Explorer
├── https://quick-bench.com           — Online benchmarking
├── https://cppinsights.io            — Template instantiation viewer
└── https://wandbox.org               — Online C++ compiler
```

---

## 📅 TIMELINE PEMBELAJARAN

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIMELINE REKOMENDASI — FULL-TIME (40 Jam/Minggu)                           │
├──────┬──────────────────────────────────────────────────────────────────────┤
│ Minggu│ Aktivitas                                                            │
├──────┼──────────────────────────────────────────────────────────────────────┤
│  1   │ Bab 01: C++ Modern Fundamentals (28 Jam)                             │
│  2   │ Bab 02: Memory Management (32 Jam)                                   │
│  3   │ Bab 03: OOP Modern (30 Jam)                                          │
│  4   │ Bab 04: Generic Programming (36 Jam) — Week 1                        │
│  5   │ Bab 04 lanjutan + Bab 05: STL (30 Jam)                              │
│  6   │ Bab 05 lanjutan + Mid-Course Project                                 │
│  7   │ Bab 06: Concurrent Systems (38 Jam) — Week 1                         │
│  8   │ Bab 06 lanjutan + Bab 07: Compile-Time (36 Jam)                     │
│  9   │ Bab 07 lanjutan + Bab 08: Performance (34 Jam)                      │
│  10  │ Bab 08 lanjutan + Bab 09: Systems (32 Jam)                          │
│  11  │ Bab 09 lanjutan + Bab 10: Architecture + Capstone Start              │
│  12  │ Capstone Development + Review + Sertifikasi                          │
├──────┼──────────────────────────────────────────────────────────────────────┤
│      │ TOTAL: 12 Minggu Full-Time / 24 Minggu Part-Time (20 Jam/Minggu)    │
└──────┴──────────────────────────────────────────────────────────────────────┘
```

---

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  GEMINI CURRICULUM STANDARD v2.1
  Kurikulum: C++ Modern Engineering | Kode: GEMINI-CPP-2024-ENT
  Versi Dokumen: 1.0.0 | Terakhir Diperbarui: 2024
  Lisensi: Creative Commons BY-NC-SA 4.0
  
  "C++ is a language for people who want to get things done."
  — Bjarne Stroustrup
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```