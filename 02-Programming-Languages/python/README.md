# Kurikulum Rekayasa Perangkat Lunak Python Modern (Enterprise-Grade)

Selamat datang di repositori kurikulum komprehensif **Python Enterprise Engineering**. Silabus ini dirancang untuk menjembatani kesenjangan antara pemahaman sintaksis tingkat menengah dan keahlian rekayasa sistem tingkat produksi (production-grade software engineering). Mengacu langsung pada standar industri dan taksonomi resmi **roadmap.sh/python**, kurikulum ini mengeksplorasi ekosistem Python 3.12+ dari perspektif internal runtime, performa sistem, skalabilitas terdistribusi, serta rekayasa perangkat lunak modern.

---

## 1. Course Overview & Mindset

### Visi & Pendekatan Teknis
Python sering disalahpahami sebagai bahasa skrip yang lambat dan hanya cocok untuk prototipe atau manipulasi data sederhana. Faktanya, arsitektur Python modern adalah landasan dari infrastruktur berskala masif di perusahaan teknologi terkemuka dunia. Kurikulum ini menolak pendekatan tutorial sintaksis dasar dan berfokus pada:
- **Runtime Transparency:** Memahami secara mendalam cara CPython mengeksekusi kode Anda: AST compilation, bytecode, frame evaluation loop, memory arenas, dan mekanisme Cyclic Garbage Collection.
- **Type-Safe Python:** Mengadopsi paradigma rekayasa tipe statis modern (*gradual typing*) menggunakan PEP 484/585/604/695 untuk membangun arsitektur perangkat lunak skala enterprise yang deterministik dan mudah dipelihara.
- **Concurrency & Parallelism Mastery:** Membedah batasan Global Interpreter Lock (GIL), pemanfaatan subinterpreters (PEP 684), arsitektur *event-driven* asinkron melalui `asyncio`, dan komputasi paralel terdistribusi.
- **Production Readiness & Zero-Downtime:** Dari profiling memori tingkat rendah (*low-overhead profiling*) hingga standardisasi *containerization*, instrumentasi OpenTelemetry, dan implementasi arsitektur microservices berbasis ASGI.

### Pola Pikir (The Pythonic Engineering Mindset)
1. **Explicit is better than implicit:** Kode harus transparan, terprediksi, dan terdokumentasi melalui kontrak tipe data yang ketat.
2. **Ketahui Abstraksi Anda:** Jangan hanya mengonsumsi library pihak ketiga tanpa memahami kompleksitas asimtotik waktu dan ruang ($O(n)$ time & space complexity) dari primitif data di baliknya.
3. **Optimasi Berbasis Metrik:** Menolak optimasi prematur; setiap intervensi performa harus divalidasi melalui profiling deterministik dan CPU/Memory flame graphs.

---

## 2. Learning Roadmap

```plaintext
Python Enterprise Engineering Roadmap
├── Bab 01: Fondasi Runtime & Arsitektur CPython Internals
│   ├── 01-cpython-execution-model-and-bytecode.md
│   ├── 02-memory-layout-and-variable-references.md
│   └── 03-lexical-scoping-namespaces-and-leaks.md
├── Bab 02: Advanced Type System & Static Analysis
│   ├── 01-pep-standards-and-gradual-typing.md
│   ├── 02-generics-protocols-and-duck-typing.md
│   └── 03-static-analysis-pipeline-mypy-pyright.md
├── Bab 03: Struktur Data Lanjutan & Memory Management
│   ├── 01-under-the-hood-built-in-collections.md
│   ├── 02-pymalloc-arenas-and-cyclic-gc.md
│   └── 03-memory-optimization-slots-and-weakref.md
├── Bab 04: Functional Programming, Iterators & Generator Pipeline
│   ├── 01-iterator-protocol-and-generators.md
│   ├── 02-coroutine-pipelines-and-itertools.md
│   └── 03-functools-closures-and-immutability.md
├── Bab 05: Object-Oriented Deep Dive & Metaprogramming
│   ├── 01-c3-linearization-mro-and-descriptors.md
│   ├── 02-metaclasses-and-class-instantiation-hooks.md
│   └── 03-abstract-syntax-tree-and-code-generation.md
├── Bab 06: Concurrency & Parallelism: GIL, Threads & Multiprocessing
│   ├── 01-gil-internals-and-threading-realities.md
│   ├── 02-multiprocessing-shared-memory-and-ipc.md
│   └── 03-subinterpreters-and-free-threaded-python.md
├── Bab 07: Asynchronous Programming Lanjutan dengan Asyncio
│   ├── 01-event-loop-internals-and-future-task-api.md
│   ├── 02-structured-concurrency-and-taskgroups.md
│   └── 03-non-blocking-io-protocols-and-transports.md
├── Bab 08: Interoperabilitas Sistem & C-Extensions
│   ├── 01-c-extensions-api-and-abi-stability.md
│   ├── 02-ffi-with-ctypes-and-cffi.md
│   └── 03-modern-native-extensions-with-pyo3-rust.md
├── Bab 09: Testing Strategy, Profiling & Performance Tuning
│   ├── 01-deterministic-and-property-testing.md
│   ├── 02-cpu-and-memory-profiling-flamegraphs.md
│   └── 03-bytecode-optimization-and-vectorization.md
└── Bab 10: Production-Ready Engineering & Microservices
    ├── 01-modern-packaging-and-dependency-isolation.md
    ├── 02-asgi-architecture-and-high-throughput-apis.md
    └── 03-cloud-native-deployment-observability.md
```

---

## 3. Navigasi Detail Bab 01 s/d Bab 10

### [Bab 01: Fondasi Runtime & Arsitektur CPython Internals](./bab-01)
Mempelajari secara mendalam arsitektur kompilasi dan eksekusi CPython, representasi internal objek, serta manajemen frame memori.
- [Modul 01: CPython Execution Model, Compilation Pipeline, dan Virtual Machine Bytecode](./bab-01/01-cpython-execution-model-and-bytecode.md)
  - Analisis parsing AST, kompilasi ke bytecode, dekompilasi via modul `dis`, struktur opcode, dan evaluation loop di dalam `ceval.c`.
- [Modul 02: Memory Layout Objek, Pointer References, dan Object Invalidation](./bab-01/02-memory-layout-and-variable-references.md)
  - Membedah struct `PyObject` dan `PyVarObject`, reference counting, pointer overhead, mutability semantics, dan optimasi *interning* (string/integer).
- [Modul 03: Lexical Scoping, Symtable, Frame Allocations, dan Variable Leakage](./bab-01/03-lexical-scoping-namespaces-and-leaks.md)
  - Aturan pencarian LEGB (Local, Enclosing, Global, Built-in), analisis symbol table waktu kompilasi, penanganan variabel closure, dan bahaya namespace leakage.

### [Bab 02: Advanced Type System & Static Analysis](./bab-02)
Menguasai typing deklaratif modern untuk mengeliminasi kecacatan runtime dalam basis kode berukuran besar.
- [Modul 01: Standarisasi Tipe Python Modern (PEP 484, 585, 604, 695)](./bab-02/01-pep-standards-and-gradual-typing.md)
  - Implementasi sintaks generic terbaru, union syntax (`|`), `TypeAlias`, tipe primitif bawaan tanpa modul `typing`, dan varians tipe (*covariance/contravariance*).
- [Modul 02: Structural Subtyping (Protocols), Generic Collections, dan TypeVar](./bab-02/02-generics-protocols-and-duck-typing.md)
  - Desain kontrak antarmuka statis dengan `typing.Protocol`, pembuatan generic reusable dengan bound constraints, `ParamSpec`, dan `TypeVarTuple`.
- [Modul 03: Integrasi Pipeline Validasi Statis: Mypy Strict Mode dan Pyright](./bab-02/03-static-analysis-pipeline-mypy-pyright.md)
  - Konfigurasi linting dan *type-checking* dalam mode restriktif, penulisan stub files (`.pyi`), serta eliminasi `Any` dalam CI/CD pipeline enterprise.

### [Bab 03: Struktur Data Lanjutan & Memory Management](./bab-03)
Eksplorasi mendalam atas struktur data bawaan dari sisi arsitektur memori dan algoritma internalnya.
- [Modul 01: Arsitektur Internal Dict, Set, List, dan Tuple](./bab-03/01-under-the-hood-built-in-collections.md)
  - Membedah algoritma hash table compact/ordered dictionary, penanganan tabrakan hash (*open addressing*), dynamic array resize strategies, dan amortisasi kompleksitas waktu.
- [Modul 02: Alokasi Memori Tingkat Rendah: PyMalloc, Arenas, Pools, dan Cyclic Garbage Collection](./bab-03/02-pymalloc-arenas-and-cyclic-gc.md)
  - Mekanisme alokasi memori untuk objek kecil ($\le 512$ bytes), generasi GC (Gen 0, 1, 2), algoritma pendeteksi *cyclical reference*, dan modul `gc`.
- [Modul 03: Memory Optimization: `__slots__`, Zero-Copy Arrays, dan Weakref](./bab-03/03-memory-optimization-slots-and-weakref.md)
  - Pengurangan footprint memori instansiasi kelas dengan membuang `__dict__`, manipulasi buffer biner menggunakan `memoryview`, dan referensi non-retaining dengan `weakref`.

### [Bab 04: Functional Programming, Iterators & Generator Pipeline](./bab-04)
Membangun pemrosesan data berbasis aliran (*streaming/lazy evaluation*) dengan efisiensi memori tingkat tinggi.
- [Modul 01: Protokol Iterator, Generators Internals, dan Yield Semantics](./bab-04/01-iterator-protocol-and-generators.md)
  - Implementasi dunder methods `__iter__` dan `__next__`, suspensi dan resume eksekusi stack frame, serta siklus hidup generator.
- [Modul 02: Coroutine Pipelines, Bidirectional Generators, dan Modul Itertools](./bab-04/02-coroutine-pipelines-and-itertools.md)
  - Mengalirkan data via delegasi generator (`yield from`), pertukaran nilai dengan `.send()`, `.throw()`, `.close()`, dan manipulasi stream dengan `itertools`.
- [Modul 03: Functools, Closures, Currying, dan Immutable Patterns](./bab-04/03-functools-closures-and-immutability.md)
  - Analisis cell objects pada closures, partial application, dynamic dispatching dengan `singledispatch`, memoization efisien via `lru_cache`, dan persistent data structures.

### [Bab 05: Object-Oriented Deep Dive & Metaprogramming](./bab-05)
Mekanisme internal sistem objek CPython, resolusi hierarki pewarisan, dan abstraksi *runtime metaprogramming*.
- [Modul 01: C3 Linearization (MRO), Super Deep Dive, dan Descriptor Protocol](./bab-05/01-c3-linearization-mro-and-descriptors.md)
  - Perhitungan Method Resolution Order pada *multiple inheritance*, resolving delegasi `super()`, dan implementasi protokol data/non-data descriptor (`__get__`, `__set__`, `__delete__`).
- [Modul 02: Metaclasses, Class Construction Lifecycle, dan `__init_subclass__`](./bab-05/02-metaclasses-and-class-instantiation-hooks.md)
  - Mengontrol instansiasi kelas melalui meta-tipe `type`, manipulasi class dictionary, validasi deklaratif berbasis PEP 487 tanpa metaclass overhead.
- [Modul 03: Dynamic Code Generation, AST Manipulation, dan Code Objects](./bab-05/03-abstract-syntax-tree-and-code-generation.md)
  - Inspeksi runtime, parsing kode ke pohon sintaksis menggunakan modul `ast`, modifikasi node syntax, dan kompilasi runtime dinamis secara aman.

### [Bab 06: Concurrency & Parallelism: GIL, Threads & Multiprocessing](./bab-06)
Membedah batas fisik komputasi konkruen pada Python dan strategi mengatasi hambatan CPU-bound.
- [Modul 01: Global Interpreter Lock (GIL): Mekanisme, Dampak, dan Threading](./bab-06/01-gil-internals-and-threading-realities.md)
  - Mengapa GIL ada: thread safety, periodic tick/eval breaker, context switching overhead, dan kapan threading efektif untuk I/O-bound tasks.
- [Modul 02: Multiprocessing, IPC, dan Alokasi Shared Memory](./bab-06/02-multiprocessing-shared-memory-and-ipc.md)
  - Pemisahan ruang memori proses, teknik IPC (pipes, queues), data sharing tanpa serialisasi berlebih via modul `multiprocessing.shared_memory`.
- [Modul 03: Subinterpreters (PEP 684) dan Evolusi Free-Threaded Python](./bab-06/03-subinterpreters-and-free-threaded-python.md)
  - Mengeksplorasi arsitektur per-interpreter GIL di Python 3.12+, modul `_xxsubinterpreters`, dan masa depan Python tanpa GIL (PEP 703).

### [Bab 07: Asynchronous Programming Lanjutan dengan Asyncio](./bab-07)
Membangun arsitektur event-driven non-blocking yang mampu menangani puluhan ribu koneksi konkuren secara simultan.
- [Modul 01: Event Loop Internals, Generators to Coroutines, dan Futures/Tasks](./bab-07/01-event-loop-internals-and-future-task-api.md)
  - Cara kerja engine epoll/kqueue di balik event loop, transisi state machine pada coroutine object, dan lifecycle orchestration pada `asyncio.Future` & `Task`.
- [Modul 02: Structured Concurrency, Exception Groups, dan TaskGroups](./bab-07/02-structured-concurrency-and-taskgroups.md)
  - Mengadopsi paradigma *structured concurrency* dengan `asyncio.TaskGroup` (Python 3.11+), integrasi `ExceptionGroup` / `except*`, serta pencegahan *task leakage*.
- [Modul 03: High-Performance Network Protocols, Transports, dan Streams](./bab-07/03-non-blocking-io-protocols-and-transports.md)
  - Membangun server TCP/UDP kustom tingkat rendah menggunakan abstraksi low-level `Transport` & `Protocol` berbanding high-level `asyncio.StreamReader` / `StreamWriter`.

### [Bab 08: Interoperabilitas Sistem & C-Extensions](./bab-08)
Menembus batas performa Python murni dengan menghubungkan runtime ke bahasa pemrograman sistem level rendah.
- [Modul 01: Python C-API, Refcounting Manual, dan Stable ABI (PEP 384)](./bab-08/01-c-extensions-api-and-abi-stability.md)
  - Menulis modul ekstensi C langsung: alokasi `PyObject*`, registrasi method table, manajemen `Py_INCREF`/`Py_DECREF`, dan kompatibilitas binary lintas rilis Python.
- [Modul 02: Foreign Function Interface: ctypes vs CFFI](./bab-08/02-ffi-with-ctypes-and-cffi.md)
  - Memanggil pustaka dinamis *shared libraries* (`.so` / `.dll`), passing pointer, konversi tipe data C secara deterministik, dan perbandingan performa ABI vs API mode pada CFFI.
- [Modul 03: Modern Native Extensions: Integrasi Rust Menggunakan PyO3 dan Maturin](./bab-08/03-modern-native-extensions-with-pyo3-rust.md)
  - Mengembangkan modul ekstensi berkecepatan tinggi dan *memory-safe* menggunakan ekosistem Rust: mapping tipe, pelepasan GIL eksplisit, dan packaging via Maturin.

### [Bab 09: Testing Strategy, Profiling & Performance Tuning](./bab-09)
Metodologi jaminan kualitas perangkat lunak dan observabilitas mendalam performa eksekusi kode.
- [Modul 01: Deterministic Testing, Mocking Boundaries, dan Property-Based Testing](./bab-09/01-deterministic-and-property-testing.md)
  - Arsitektur pengujian tingkat lanjut dengan `pytest` (fixtures lifecycle, hooks, parametrization) dan pencarian *edge cases* otomatis menggunakan `Hypothesis`.
- [Modul 02: CPU & Memory Profiling, Tracing, dan Visualisasi Flamegraphs](./bab-09/02-cpu-and-memory-profiling-flamegraphs.md)
  - Profiling deterministik (`cProfile`) dan sampling-based (`py-spy`), pendeteksian kebocoran memori dengan `memray` dan `tracemalloc`, serta interpretasi flamegraph.
- [Modul 03: Bytecode Optimization, Specialized Adaptive Interpreter, dan Vectorization](./bab-09/03-bytecode-optimization-and-vectorization.md)
  - Analisis *Specializing Adaptive Interpreter* (PEP 659) pada Python 3.11+, eksekusi loop unrolling, serta teknik vektorisasi data dengan NumPy arrays/BLAS integration.

### [Bab 10: Production-Ready Engineering & Microservices](./bab-10)
Standardisasi pengiriman perangkat lunak skala besar: dari arsitektur layanan mikro hingga orkestrasi cloud-native.
- [Modul 01: Modern Dependency Management, PyProject.toml, dan Package Distribution](./bab-10/01-modern-packaging-and-dependency-isolation.md)
  - Pengemasan berstandar PEP 517/518/621, manajemen dependensi deterministik menggunakan UV / Poetry, dan isolasi lingkungan build (*hermetic builds*).
- [Modul 02: ASGI Specification, Uvicorn Internals, dan High-Throughput APIs](./bab-10/02-asgi-architecture-and-high-throughput-apis.md)
  - Anatomi antarmuka ASGI, lifecycle event loop di bawah server worker model (Uvicorn/Gunicorn), arsitektur zero-allocation JSON parsing, dan framework modern FastAPI/Litestar.
- [Modul 03: Cloud-Native Containerization, OpenTelemetry, dan Observability](./bab-10/03-cloud-native-deployment-observability.md)
  - Minimal footprint multi-stage Docker builds, mitigasi memory fragmentation di container Linux (glibc vs jemalloc), instrumentasi OpenTelemetry traces/metrics, dan graceful shutdown orchestration.

---

## 4. Spesifikasi Capstone Project Enterprise

### Nama Proyek: **AURA-Engine (Autonomous Ultra-low-latency Risk Analytics Engine)**

#### 1. Deskripsi Sistem
AURA-Engine adalah platform microservices analitik risiko portofolio keuangan dan deteksi anomali transaksi pasar *real-time*. Sistem ini dirancang untuk memproses aliran data (*streaming*) order book frekuensi tinggi dengan beban jutaan event per detik, menghitung metrik Value-at-Risk (VaR) dinamis, dan mengeksekusi validasi aturan risiko dalam ambang batas sub-milidetik.

#### 2. Arsitektur Teknis
Sistem mengadopsi arsitektur event-driven hibrida yang menggabungkan:
- **Core Async Event Ingestion Layer:** Berbasis `asyncio.TaskGroup` dan custom TCP stream protocols untuk menangani koneksi masuk dari bursa derivatif tanpa memblokir I/O loop.
- **High-Performance Math Kernel:** Modul komputasi matriks kustom yang dibangun menggunakan kombinasi **Rust (PyO3)** dan ekstensifikasi native C/Cython untuk mengeksekusi simulasi Monte Carlo tanpa hambatan Python GIL.
- **Shared-Memory State Store:** State ring-buffer dalam memori menggunakan `multiprocessing.shared_memory` yang memungkinkan worker proses independen mengakses order book secara zero-copy.
- **Control Plane & Client Gateway:** Antarmuka REST & WebSocket tingkat tinggi berbasis FastAPI dan spesifikasi ASGI, terisolasi dari proses worker komputasi data.

```plaintext
+-------------------------------------------------------------------------------+
|                       AURA-Engine Enterprise Architecture                     |
+-------------------------------------------------------------------------------+
                                        |
                            [ Ingress Market Feeds ]
                                        |
                                        v
                 +---------------------------------------------+
                 | Asyncio Custom Ingress Engine (Bab 07)       |
                 | - StreamReader / Non-blocking Raw Sockets   |
                 | - Structured Concurrency (TaskGroup)        |
                 +---------------------------------------------+
                                        |
                                        v
                 +---------------------------------------------+
                 | Shared Memory Ring Buffer (Bab 03, 06)      |
                 | - Zero-copy memoryview / mmap               |
                 | - Subinterpreters / Multi-core isolation    |
                 +---------------------------------------------+
                                        |
                        +---------------+---------------+
                        |                               |
                        v                               v
         +-----------------------------+ +-----------------------------+
         | Risk Worker Process 1       | | Risk Worker Process N       |
         | - Metaprogrammed Validation | | - Descriptors Pipeline      |
         | - PyO3 Rust Kernel (Monte   | | - CFFI Native Math Engine   |
         |   Carlo Simulation)         | |   (Vectorized Analytics)    |
         |   (Bab 05, 08)              | |   (Bab 08, 09)              |
         +-----------------------------+ +-----------------------------+
                        |                               |
                        +---------------+---------------+
                                        |
                                        v
                 +---------------------------------------------+
                 | Control Plane Gateway (ASGI / FastAPI)      |
                 | - OpenTelemetry Distributed Tracing (Bab 10)|
                 | - Strict Type Annotations Validation (Bab 02)|
                 | - Real-Time Prometheus Metrics Export       |
                 +---------------------------------------------+
```

#### 3. Standar Implementasi & Kriteria Kelayakan (Production Readiness)
Untuk menyelesaikan kursus ini, implementasi proyek akhir harus memenuhi kriteria non-fungsional berikut:
- **100% Strict Type Verification:** Basis kode divalidasi penuh menggunakan `mypy --strict` dan `pyright` tanpa adanya anotasi `Any` implisit atau penekanan `# type: ignore` yang tidak berjustifikasi tertulis.
- **Zero-Allocation Core Loop:** Pemrosesan event pada hot-path harus memanfaatkan memory recycling via `memoryview` dan kelas berbasis `__slots__` tanpa memicu alokasi memori dinamis di PyMalloc secara berlebihan.
- **Comprehensive Testing Suite:**
  - Coverage pengujian unit $\ge 90\%$ menggunakan `pytest`.
  - Property-based testing via `Hypothesis` untuk menguji invariansi numerik pada algoritma analitik portofolio terhadap input acak ekstrim.
- **Observabilitas Lengkap:** Setiap proses dan request tracing terinstrumentasi dengan OpenTelemetry SDK, terintegrasi ke Jaeger untuk distributed tracing dan Prometheus untuk metriks performa (latency p99, memory RSS footprint, frame execution time).
- **Hermetic Build & Containerization:** Proyek dikemas secara terisolasi menggunakan spesifikasi `pyproject.toml` modern, dipaketkan dalam container Docker berbasis distroless/minimal multi-stage build, dengan optimasi alokator memori `jemalloc` untuk mencegah fragmentasi memori Linux.