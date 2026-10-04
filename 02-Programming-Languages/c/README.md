# Kurikulum Rekayasa Sistem Berbasis C: Dari Bare-Metal hingga Sistem Konkuren Terdistribusi

Selamat datang di repositori resmi kurikulum **C Systems Engineering**. Silabus ini dirancang oleh Senior Technical Curriculum Architect untuk mentransformasi software engineer menjadi systems programmer tingkat lanjut dengan spesialisasi pada arsitektur sistem operasi, runtime internals, jaringan performa tinggi, dan komputasi deterministik.

---

## 1. Course Overview & Mindset

Bahasa C bukan sekadar bahasa pemrograman tingkat tinggi; C adalah bahasa pemrograman berstruktur abstrak tipis (*thin abstraction*) di atas arsitektur perangkat keras von Neumann. Dalam kurikulum ini, Anda tidak diperlakukan sebagai pengguna API, melainkan sebagai perancang tata letak memori, pengontrol register, dan arsitek efisiensi siklus instruksi CPU.

### Paradigma & Mental Model Inti:
- **Tunduk pada Hardware, Bukan Runtime**: Menghilangkan asumsi *garbage collection*, *runtime reflection*, atau *exception handling* otomatis. Anda bertanggung jawab penuh atas setiap byte yang dialokasikan, disejajarkan (*aligned*), dan dibebaskan.
- **Kesadaran Memori Total (*Memory-Centric Paradigm*)**: Memahami siklus hidup data dari Register $\to$ Cache L1/L2/L3 $\to$ RAM $\to$ Virtual Memory Subsystem (TLB & Paging). Mengoptimalkan struktur data untuk meminimalkan *cache miss*.
- **Disiplin Ketat terhadap Undefined Behavior (UB)**: Di C, kesalahan logika bukan sekadar melempar eksepsi; UB dapat memicu eksploitasi keamanan, optimasi kompiler yang merusak logika (*aggressive optimization pruning*), dan *kernel panic*.
- **Sistem POSIX & Kernel Interface**: Menguasai batas transisi dari *User Space* ke *Kernel Space* melalui System Calls, sinyal, virtual memory mapping, dan I/O non-blocking berbasis event.

---

## 2. Learning Roadmap

Berikut adalah peta jalan terstruktur dari 10 bab penguasaan bahasa C untuk rekayasa sistem enterprise:

```text
[C Systems Engineering Roadmap]
│
├── 01: Arsitektur Kompilasi, Linking, & Memory Layout
│   ├── Toolchain GCC/Clang, Preprocessing, & Tahapan Translasi
│   ├── Struktur Binary ELF, Object Files, & Linker Script
│   └── Layout Memori Proses: Stack, Heap, BSS, Data, & Text
│
├── 02: Tipe Data Primitif, Representasi Bit, & Aritmetika Biner
│   ├── Two's Complement, Sign Extension, & Integer Promotion Rules
│   ├── Floating Point IEEE 754, Precision Loss, & Bit Casting
│   └── Manipulasi Bitwise, Bitmasking, & Endianness Handling
│
├── 03: Aliran Kontrol, Stack Frame, & Rekursi Tingkat Assembly
│   ├── Percabangan, Jump Tables, & Analisis Assembly x86_64
│   ├── Mekanisme Call Stack, Calling Conventions, & ABI
│   └── Rekursi, Tail-Call Optimization, & Stack Overflow Hardening
│
├── 04: Pointer Mastery, Aritmetika Alamat, & Manipulasi Memori
│   ├── Model Virtual Address, De-referencing, & Pointer Decay
│   ├── Pointer Aritmetika, Multi-level Indirection, & Function Pointers
│   └── Type Punning, Strict Aliasing Rule, & Void Pointers
│
├── 05: Array, String Idiom, & Zero-Copy Buffer Processing
│   ├── Karakteristik Memori Kontigu, Array Multi-Dimensi, & Row-Major
│   ├── Kelemahan Keamanan String Null-Terminated & Mitigasi C11
│   └── Implementasi Custom Ring Buffer & Zero-Copy Parser
│
├── 06: Tipe Data Buatan: Struct, Union, Enum, & Memory Alignment
│   ├── Data Structure Alignment, Struct Padding, & Cache-Line Straddling
│   ├── Packed Structs, Bit-Fields, & Serialization Protokol Biner
│   └── Tagged Unions, Variant Patterns, & Safe Type Morphing
│
├── 07: Manajemen Memori Dinamis: Subalokator & Profiling
│   ├── Siklus Hidup Heap: malloc, calloc, realloc, & free Internals
│   ├── Fragmentasi Memori & Desain Custom Arena / Pool Allocator
│   └── Deteksi Memory Leak & Illegal Access (ASan, Valgrind)
│
├── 08: I/O Tingkat Rendah, File Descriptor, & POSIX Syscalls
│   ├── Abstraksi Kernel File Descriptor vs C Standard File Streams
│   ├── Direct File I/O, Zero-Copy Transfer via sendfile, & epoll
│   └── Memory-Mapped I/O Menggunakan sys/mman (mmap, munmap, msync)
│
├── 09: Konkurensi POSIX Threads, Sinkronisasi, & Model Atomics
│   ├── Lifecycle pthread, Thread Local Storage, & Context Switching
│   ├── Primitif Sinkronisasi: Mutex, Spinlock, RWLock, & Condition Variable
│   └── Memory Ordering, Barriers, & Atomic Operations (stdatomic.h)
│
└── 10: Rekayasa Software Defensif, Hardening, & Undefined Behavior
    ├── Taksonomi Undefined Behavior, Compiler Trap, & Exploit Vector
    ├── Static & Dynamic Code Analysis: UBSan, TSan, Clang-Tidy
    └── Panduan Standar MISRA C / CERT C untuk Sistem Misi Kritis
```

---

## 3. Navigasi Detail Modul (Bab 01 s/d Bab 10)

### [Bab 01: Arsitektur Kompilasi, Linking, & Memory Layout](./01-arsitektur-kompilasi-c/)
Memahami siklus hidup penerjemahan kode C ke machine code serta organisasi memori virtual pada platform modern.
- [01. Pipeline Kompilasi C: Preprocessing, Compilation, Assembly, dan Linking](./01-arsitektur-kompilasi-c/01-toolchain-pipeline.md)
- [02. Bedah Format Biner ELF, Relocation, Static vs Dynamic Libraries](./01-arsitektur-kompilasi-c/02-elf-binary-linking.md)
- [03. Anatomi Layout Memori Virtual Proses: Stack, Heap, Data Segments, dan Text](./01-arsitektur-kompilasi-c/03-memory-segments-layout.md)

### [Bab 02: Tipe Data Primitif, Representasi Bit, & Aritmetika Biner](./02-representasi-bit-dan-tipe/)
Mengeksplorasi representasi fisik data di dalam transistor dan register memori serta implikasi casting.
- [01. Representasi Integer: Two's Complement, Sign Extension, dan Integer Promotion Rule](./02-representasi-bit-dan-tipe/01-integer-promotion-twos-complement.md)
- [02. Arsitektur Floating-Point IEEE 754: Sign, Exponent, Mantissa, dan Denormal Number](./02-representasi-bit-dan-tipe/02-floating-point-ieee754.md)
- [03. Operasi Bitwise Tingkat Rendah, Bitmasking, dan Penanganan Endianness](./02-representasi-bit-dan-tipe/03-bitwise-and-endianness.md)

### [Bab 03: Aliran Kontrol, Stack Frame, & Rekursi Tingkat Assembly](./03-aliran-kontrol-assembly/)
Menganalisis bagaimana abstraksi kondisional dan fungsi diwujudkan dalam instruksi mesin x86_64/ARM.
- [01. Percabangan dan Analisis Alur Kontrol: If-Else, Jump Tables, dan Switch Optimization](./03-aliran-kontrol-assembly/01-branching-and-jump-tables.md)
- [02. Anatomi Call Stack, Frame Pointer, Calling Conventions (System V ABI), dan Red Zone](./03-aliran-kontrol-assembly/02-stack-frame-and-abi.md)
- [03. Rekursi, Tail-Call Optimization (TCO), dan Pencegahan Stack Overflow](./03-aliran-kontrol-assembly/03-recursion-and-tail-call.md)

### [Bab 04: Pointer Mastery, Aritmetika Alamat, & Manipulasi Memori](./04-pointer-dan-manipulasi-memori/)
Membangun kontrol tak terbatas terhadap penunjuk memori dengan tetap menjamin integritas memori.
- [01. Aritmetika Pointer, Skalar Alamat, Dereferensi, dan Pointer Decay](./04-pointer-dan-manipulasi-memori/01-pointer-arithmetic.md)
- [02. Pointer Multi-Tingkat (Pointer to Pointer) dan Dynamic Function Pointers Table](./04-pointer-dan-manipulasi-memori/02-multilevel-and-function-pointers.md)
- [03. Strict Aliasing Rules, Type Punning, dan Safe Pointer Casting dengan `void*`](./04-pointer-dan-manipulasi-memori/03-strict-aliasing-and-void-ptr.md)

### [Bab 05: Array, String Idiom, & Zero-Copy Buffer Processing](./05-array-string-dan-buffer/)
Mengoptimalkan throughput manipulasi array dan membedah risiko keamanan komputasi string klasik.
- [01. Layout Array Multi-Dimensi di Memori, Penjajaran Row-Major, dan Kontiguitas](./05-array-string-dan-buffer/01-array-layout-and-decay.md)
- [02. Anatomi String C-Style: Kelemahan Keamanan, Boundary Check, dan Fungsi Bounds-Checking C11](./05-array-string-dan-buffer/02-string-vulnerabilities-mitigation.md)
- [03. Desain Zero-Copy Ring Buffer dan Parser Streaming Performa Tinggi](./05-array-string-dan-buffer/03-zero-copy-ring-buffer.md)

### [Bab 06: Tipe Data Buatan: Struct, Union, Enum, & Memory Alignment](./06-struct-union-alignment/)
Menguasai rekayasa struktur data biner deterministik untuk interoperabilitas hardware dan protokol transmisi data.
- [01. Data Alignment, Hardware Memory Boundary, Padding, dan Cache-Line Packing](./06-struct-union-alignment/01-alignment-padding-packing.md)
- [02. Bit-Fields, Struktur Packed (`__attribute__((packed))`), dan Serialisasi Protokol Jaringan](./06-struct-union-alignment/02-bitfields-and-network-serialization.md)
- [03. Tagged Unions, Abstraksi Type Erasure, dan Mutasi Tipe Data Deterministik](./06-struct-union-alignment/03-tagged-unions-and-polymorphism.md)

### [Bab 07: Manajemen Memori Dinamis: Subalokator & Profiling](./07-dynamic-memory-allocator/)
Mempelajari arsitektur internal alokasi heap dan membangun pengelola alokasi memori khusus.
- [01. Arsitektur Dynamic Heap: Internals Alokator Glibc (ptmalloc), sbrk, dan mmap](./07-dynamic-memory-allocator/01-glibc-malloc-internals.md)
- [02. Rekayasa Custom Sub-Allocators: Linear/Arena Allocator dan Fixed-Size Pool Allocator](./07-dynamic-memory-allocator/02-custom-arena-pool-allocator.md)
- [03. Pendeteksian Kebocoran Memori, Heap Corruption, dan Profiling (Valgrind Massif, AddressSanitizer)](./07-dynamic-memory-allocator/03-memory-leak-profiling-asan.md)

### [Bab 08: I/O Tingkat Rendah, File Descriptor, & POSIX Syscalls](./08-low-level-io-posix/)
Berinteraksi langsung dengan subsistem kernel melalui sistem operasi abstractions untuk efisiensi I/O maksimal.
- [01. Abstraksi File Descriptor POSIX vs Buffer `FILE*` pada C Runtime Lib](./08-low-level-io-posix/01-file-descriptors-vs-stdio.md)
- [02. Pola I/O Terdesentralisasi: Event Demultiplexing Menggunakan Non-blocking `epoll`](./08-low-level-io-posix/02-nonblocking-io-epoll.md)
- [03. Pemetaan Memori Menggunakan `mmap`, Shared Memory, dan Zero-Copy Transmission](./08-low-level-io-posix/03-mmap-and-zero-copy.md)

### [Bab 09: Konkurensi POSIX Threads, Sinkronisasi, & Model Atomics](./09-posix-threads-dan-atomics/)
Mengeksekusi konkurensi skala masif multithreaded dengan jaminan konsistensi status dan bebas data-race.
- [01. Lifecycle POSIX Threads (pthread), Thread-Local Storage, dan Core Pinning (Affinity)](./09-posix-threads-dan-atomics/01-pthreads-and-core-affinity.md)
- [02. Primitif Sinkronisasi: Mutex, Condition Variables, Semaphore, dan Spinlocks](./09-posix-threads-dan-atomics/02-synchronization-primitives.md)
- [03. Memory Ordering, Atomics Terjadwal (`stdatomic.h`), dan Desain Lock-Free Ring Queue](./09-posix-threads-dan-atomics/03-lock-free-ring-queue-atomics.md)

### [Bab 10: Rekayasa Software Defensif, Hardening, & Undefined Behavior](./10-defensive-c-hardening/)
Memproteksi codebase C dari kesalahan runtime tak terduga, bug eksploitatif, dan optimasi agresif compiler.
- [01. Katalog Undefined Behavior (UB), Compiler Optimizations Assumptions, dan Trap Representation](./10-defensive-c-hardening/01-undefined-behavior-catalog.md)
- [02. Dynamic Sanitizers Suite (ASan, UBSan, TSan) dan Static Tooling (Clang-Tidy, Cppcheck)](./10-defensive-c-hardening/02-static-and-dynamic-analysis.md)
- [03. Standar Koding Kritis: Penerapan Prinsip MISRA-C dan CERT-C untuk Pencegahan Kerentanan](./10-defensive-c-hardening/03-misra-cert-c-hardening.md)

---

## 4. Spesifikasi Capstone Project Enterprise

### Judul Proyek:
**"AetherCache: In-Memory Key-Value Storage Engine Berperforma Tinggi dengan Custom Slab Allocator, Event-Driven POSIX Reactor, dan Protokol Biner Sinkron"**

### Ringkasan Eksekutif:
AetherCache adalah klon performa tinggi yang terinspirasi oleh arsitektur Redis dan Memcached, dibangun murni menggunakan standard C11 dan subsistem Linux/POSIX. Sistem ini melayani transaksi penyimpanan key-value secara *in-memory* dengan latency tingkat mikrodetik, menggunakan alokator memori berbasis *Slab Allocator* untuk meniadakan fragmentasi heap eksternal, dan arsitektur event loop berbasis Linux `epoll` untuk menangani puluhan ribu koneksi konkuren secara non-blocking.

### Arsitektur Sistem:
```text
                         [Client Applications]
                                  │
                                  ▼
           [Network Engine: Non-Blocking epoll() Event Loop]
                                  │
                                  ▼
          [Binary Protocol Parser / State Machine (Zero-Copy)]
                                  │
        ┌─────────────────────────┴─────────────────────────┐
        ▼                                                   ▼
[Hash Table Index]                              [Slab / Arena Allocator]
(MurmurHash3, Robin Hood Hashing)               (Preallocated Buckets, 
                                                 Zero External Fragmentation)
        │                                                   │
        └─────────────────────────┬─────────────────────────┘
                                  ▼
               [Storage Core: Mutex-Free / RWLock Read]
                                  │
                                  ▼
            [WAL Engine: mmap()-based Persistence Log]
```

### Spesifikasi Fungsional & Teknis:
1. **Memory Management Subsystem (Slab Allocator)**:
   - Mengalokasikan chunk memori tetap tersegregasi berdasarkan ukuran kelas logaritmik (misal: 64B, 128B, 256B, 512B, up to 1MB).
   - Menghindari pemanggilan `malloc()` dan `free()` secara langsung pada hot-path transaksi data.
   - Pemanfaatan *freelist* intra-slab untuk alokasi $O(1)$ dan de-alokasi deterministik.
2. **Indexing Subsystem (Concurrent Hash Table)**:
   - Implementasi tabel hash dinamis menggunakan strategi *Robin Hood Hashing* atau *Open Addressing with Linear Probing* yang ramah CPU cache lines.
   - Re-hashing inkremental di latar belakang tanpa memblokir thread operasi utama (*background worker*).
3. **I/O & Network Multiplexing**:
   - Single-threaded Reactor Loop atau Multi-Threaded Worker Pool terdistribusi via POSIX `epoll` (Edge-Triggered Mode).
   - Penanganan parsial read/write secara non-blocking dengan buffer sirkular internal.
4. **Protokol Biner Zero-Copy**:
   - Frame jaringan khusus yang memuat Header Ukuran (32-bit), Operasi (GET, SET, DEL, EXPIRE), Payload Key, dan Payload Value.
   - Parsing langsung memetakan pointer buffer tanpa alokasi memori heap baru.
5. **Daya Tahan Data (Persistence Layer)**:
   - Mekanisme Write-Ahead Log (WAL) menggunakan sinkronisasi `mmap` dan `msync` (ASYNC/SYNC) untuk menjamin pemulihan data setelah kegagalan (*crash recovery*).

### Kriteria Kelulusan Teknis (Acceptance Criteria):
- **Zero Leak & Zero UB Validation**: Lulus pengujian komprehensif di bawah lingkungan GCC/Clang dengan flags `-fsanitize=address,undefined -Wall -Wextra -Wpedantic -Werror`. Nol alokasi tertinggal di Valgrind Massif/Memcheck.
- **Concurrent Thread Safety**: Lulus pengujian multithreading di bawah LLVM ThreadSanitizer (TSan) tanpa satu pun status *data race*.
- **Throughput & Latency Target**: Mencapai minimal **150.000 QPS (Queries Per Second)** pada payload 128-byte melalui benchmark client lokal pada hardware x86_64 8-core, dengan *p99 latency* berada di bawah **1.5 milidetik**.
- **Integritas Kode**: 100% mengikuti standar defensive programming: tidak ada penggunaan fungsi-fungsi rentan (`gets`, `strcpy`, `sprintf`), memvalidasi batas array, dan pengujian boundary integer overflow.

---
*Kurikulum ini dipertahankan di bawah lisensi rekayasa sistem enterprise. Seluruh hak cipta modul, kode sumber, dan dokumentasi dilindungi.*