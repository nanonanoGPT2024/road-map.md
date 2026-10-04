# BAB 02: Memory Management & Resource Safety
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengimplementasikan idiom RAII tingkat lanjut dengan Custom Deleters pada `std::unique_ptr` dan mengendalikan siklus hidup resource non-memory (File Descriptor, Socket, GPU Context, Mutex Locks).
- Menganalisis dan membedah struktur internal Control Block pada `std::shared_ptr` dan `std::weak_ptr`, termasuk trade-off antara `std::make_shared` versus konstruksi eksplisit serta mitigasi memory leak akibat *circular reference*.
- Merancang dan membangun arsitektur alokasi memori deterministik berbasis C++17 Polymorphic Memory Resources (`std::pmr`), Monotonic Buffers, dan Custom Arena Allocators untuk sistem *ultra-low latency*.
- Mengeliminasi *cache contention* dan *false sharing* menggunakan alignment eksplisit (`alignas`), padding, dan `std::hardware_destructive_interference_size`.
- Menerapkan *Move Semantics* zero-overhead dengan garansi `noexcept` dan *Perfect Forwarding* guna menjamin *Strong Exception Safety Guarantee*.
- Mengoperasikan tooling audit memori tingkat lanjut (LLVM AddressSanitizer, LeakSanitizer, UndefinedBehaviorSanitizer, dan Valgrind Massif) dalam pipeline CI/CD produksi.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib memahami:
- Sintaksis dasar C++ (pointer mentah, dereferencing, referensi, stack vs. heap allocation).
- Konsep dasar Object-Oriented Programming (Constructor, Destructor, Copy Constructor, Copy Assignment).
- Pengenalan dasar template metaprogramming dan compile-time type deduction (`auto`, `decltype`).
- Kompilasi program C++ menggunakan modern compiler (GCC 11+, Clang 13+, atau MSVC 2019+) dengan flag `-std=c++20`.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Anatomi Internal `std::shared_ptr` dan Control Block
Saat objek dikelola oleh `std::shared_ptr`, runtime C++ mengelola dua komponen: objek itu sendiri dan sebuah **Control Block**.

```
std::shared_ptr<Widget> ptr
   │
   ├──> [ Pointer to T (Widget) ] ──────────┐
   │                                        │
   └──> [ Pointer to Control Block ] ─┐      │
                                     │      │
┌────────────────────────────────────┘      │
▼                                           ▼
Control Block Layout:                 Managed Memory:
┌──────────────────────────────┐     ┌──────────────┐
│ Strong Reference Count (int) │     │  Widget      │
├──────────────────────────────┤     │  Data...     │
│ Weak Reference Count (int)   │     └──────────────┘
├──────────────────────────────┤
│ Custom Allocator (optional)  │
├──────────────────────────────┤
│ Custom Deleter (type-erased) │
├──────────────────────────────┤
│ Virtual Method Table (Deleter)│
└──────────────────────────────┘
```

1. **Dual Reference Counters**:
   - `Strong Reference Count`: Melacak berapa banyak instance `std::shared_ptr` yang memiliki kepemilikan aktif atas objek. Ketika nilai ini mencapai angka nol (`0`), destruktor dari objek `Widget` **langsung dipanggil**.
   - `Weak Reference Count`: Melacak berapa banyak instance `std::weak_ptr` yang mengamati control block tersebut. Memori fisik Control Block **hanya akan dibebaskan** jika Strong Count bernilai 0 *dan* Weak Count bernilai 0.

2. **`std::make_shared` vs `explicit construction`**:
   - `std::make_shared<T>()`: Mengalokasikan objek `T` dan `Control Block` dalam **satu blok memori kontigu tunggal** (single chunk heap allocation). Ini meningkatkan *cache locality* dan mengurangi overhead pemanggilan alokator kernel (`malloc`/`brk`). Namun, jika ada `std::weak_ptr` yang masih hidup setelah objek didestruksi, memori untuk objek `T` tidak dapat dikembalikan ke sistem operasi karena menempel pada Control Block.
   - `std::shared_ptr<T>(new T())`: Melakukan dua alokasi terpisah: pertama untuk `T`, kedua untuk Control Block. Mengizinkan deallokasi memori `T` secara instan saat strong count nol, meskipun `std::weak_ptr` masih hidup, namun mengorbankan performa heap alokasi ganda dan fragmentasi memori.

#### B. C++17 Polymorphic Memory Resources (`std::pmr`)
Alokator C++ klasik mendefinisikan tipe alokator sebagai bagian dari tipe data container (contoh: `std::vector<int, MyAllocator<int>>` tidak kompatibel tipenya dengan `std::vector<int>`). C++17 memperkenalkan `std::pmr` yang menggunakan virtual dynamic dispatch untuk memisahkan implementasi strategi alokasi dari tipe container:

```
           std::pmr::vector<T>
                   │
                   ▼ (Uses non-owning pointer)
        std::pmr::memory_resource (Abstract Base Interface)
                   ▲
   ┌───────────────┼────────────────────────┐
   │               │                        │
┌───────────────┐ ┌──────────────────────┐ ┌─────────────────────────┐
│ monotonic_    │ │ unsynchronized_pool_ │ │ synchronized_pool_      │
│ buffer_       │ │ resource             │ │ resource                │
│ resource      │ │ (Thread-unsafe pool) │ │ (Thread-safe pool)      │
└───────────────┘ └──────────────────────┘ └─────────────────────────┘
```

- **`std::pmr::monotonic_buffer_resource`**: Mengalokasikan memori menggunakan strategi *bump pointer*. Alokasi memori instan dilakukan hanya dengan menambahkan offset pointer. Deallokasi individu bernilai *no-op*. Seluruh blok memori dibebaskan sekaligus saat objek arena dihancurkan (ideal untuk siklus hidup pemrosesan request berbasis arena).

#### C. False Sharing dan Cache Line Alignment
Pada arsitektur x86-64 modern, *cache line* berukuran 64 byte. Apabila dua thread pada core CPU berbeda memodifikasi dua variabel berbeda yang berada pada cache line yang sama, mekanisme cache coherency protocol (seperti MESI/MOESI) akan memaksa sinkronisasi cache line antar core. Fenomena ini disebut **False Sharing**, yang dapat menurunkan performa hingga 90% pada aplikasi multi-threaded intensif.

```
Core 1 Cache (L1)                        Core 2 Cache (L1)
┌──────────────────────────────────────┐ ┌──────────────────────────────────────┐
│ Cache Line (64 Bytes)                │ │ Cache Line (64 Bytes)                │
│ [ Thread 1 Variable ] [ Thread 2 Var]│ │ [ Thread 1 Variable ] [ Thread 2 Var]│
└──────────────────────────────────────┘ └──────────────────────────────────────┘
         ▲                                        ▲
         └────────── Hardware Cache Bus ──────────┘
             (Invalidation Traffic Bottleneck)
```

Mitigasi mutlak di tingkat produksi adalah menerapkan alignment:
```cpp
alignas(std::hardware_destructive_interference_size) std::atomic<uint64_t> thread_counter;
```

---

### 4. Why & What

| Dimensi | Alokasi Konvensional (`new` / `malloc`) | Modern Resource Safety & PMR |
| :--- | :--- | :--- |
| **Determinizm** | Non-deterministik. Latensi memanggil kernel allocator (`sys_brk`/`mmap`) fluktuatif (OS lock contention). | Deterministik. Mengambil memori dari pre-allocated arena (Bump-pointer: $O(1)$). |
| **Exception Safety** | Rawan kebocoran memori (leak) jika terjadi exception di antara titik `new` dan `delete`. | Garansi Exception Safety (RAII). Destruktor otomatis mengeksekusi *cleanup sequence*. |
| **Cache Locality** | Memori tersebar acak di address space heap (tinggi *cache misses*). | Memori dialokasikan secara sequential/kontigu di L1/L2 data cache. |
| **Overhead Metadata** | Setiap blok alokasi menyimpan header malloc (8-16 bytes metadata overhead). | Zero overhead per alokasi individual pada skema Arena/Monotonic. |

Mengapa arsitektur ini krusial? Pada sistem high-frequency trading (HFT), networking core, atau sistem embedded misi kritis, alokasi memori dinamis di dalam *critical execution path* dilarang karena non-deterministic latency spikes (jitter) dan heap fragmentation.

---

### 5. How (Workflow Detail)

Alur penanganan siklus hidup resource produksi modern:

```
[ Inisialisasi ] ──> Pre-alokasi Memory Buffer (Stack / Static Arena)
                           │
                           ▼
[ Ingestion Phase ] ──> Bungkus resource via std::pmr / Custom Smart Pointer
                           │
                           ▼
[ Execution Phase ] ──> Proses data via Hot Path (Zero System Calls, No Malloc)
                           │
                           ├── Error Terjadi? ──> Unwind Stack ──> RAII Auto Cleanup
                           │
                           ▼
[ Retirement Phase ] ──> Release pointer / Reset bump-pointer Arena sekaligus (O(1))
```

1. **Pre-Allocation**: Memori dialokasikan sekali saat proses bootstrap (Cold Path).
2. **Deterministic Slicing**: Setiap permintaan memori memotong arena yang sudah disiapkan tanpa meminta lock global kernel.
3. **Scoped Ownership**: Kepemilikan objek dibatasi secara ketat melalui `std::unique_ptr`. Pemindahan kepemilikan hanya diizinkan via `std::move`.
4. **Instant Teardown**: Memori dilepas secara massal dengan mereset alokator induk, mengeliminasi ribuan traversal traversal pointer destruksi satu per satu.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Hotel vs Rumah Sewa Kontrak
- **Konvensional Heap (`malloc`/`free`)**: Seperti menyewa rumah individual melalui notaris untuk setiap tamu. Setiap kedatangan tamu membutuhkan tanda tangan kontrak, verifikasi dokumen, pencatatan sipil (kernel calls, metadata management, lock contention), dan saat pulang rumah harus diperiksa dan dibongkar satu per satu.
- **Arena Allocator (`std::pmr::monotonic_buffer_resource`)**: Seperti menyewa satu lantai hotel sekaligus selama satu malam. Tamu yang datang tinggal masuk ke kamar berikutnya yang kosong (bump pointer). Saat acara selesai, seluruh lantai dikosongkan sekaligus tanpa perlu inspeksi perabotan per kamar secara individual.

```
Standard Heap Allocator (Fragmented):
[ In-Use (8B) ][ Free (16B) ][ In-Use (64B) ][ Free (8B) ][ In-Use (32B) ]
^ Fragmentasi tinggi, non-contiguous, cache misses tinggi

Monotonic Arena Allocator (Contiguous):
┌──────────────────────────────────────────────────────────────┐
│ Chunk 1 (32B) │ Chunk 2 (64B) │ Chunk 3 (16B) │ Unused Space │
└──────────────────────────────────────────────────────────────┘
▲                                               ▲
Base Address                                    Bump Pointer (Next Free)
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: POSIX File Descriptor RAII Wrapper via `std::unique_ptr`
Menunjukkan bagaimana `std::unique_ptr` mengelola resource non-memori dengan stateless custom deleter tanpa overhead runtime.

```cpp
#include <iostream>
#include <memory>
#include <unistd.h>
#include <fcntl.h>

struct FileDescriptorCloser {
    using pointer = int; // Mendefinisikan representasi type handle internal
    void operator()(int fd) const noexcept {
        if (fd >= 0) {
            std::cout << "[RAII] Closing native File Descriptor: " << fd << "\n";
            ::close(fd);
        }
    }
};

// Alias tipe untuk safety wrapper
using ScopedFD = std::unique_ptr<int, FileDescriptorCloser>;

void write_audit_log(const std::string& message) {
    ScopedFD fd(::open("/tmp/audit.log", O_WRONLY | O_CREAT | O_APPEND, 0644));
    
    if (fd.get() < 0) {
        throw std::system_error(errno, std::generic_category(), "Gagal membuka file");
    }

    ::write(fd.get(), message.data(), message.size());
    // Destruktor dipanggil otomatis saat scope berakhir, bahkan jika write gagal
}

int main() {
    try {
        write_audit_log("AUDIT: Node-01 initial boot sequence verified.\n");
    } catch (const std::exception& e) {
        std::cerr << "Fatal Error: " << e.what() << "\n";
    }
    return 0;
}
```

#### B. Practical Example: Ultra-High-Performance Ring/Arena PMR Allocator
Implementasi container pipeline produksi C++20 yang menjamin zero heap-allocation dalam loop pemrosesan data menggunakan PMR.

```cpp
#include <iostream>
#include <vector>
#include <memory_resource>
#include <array>
#include <chrono>
#include <string_view>

struct MarketTick {
    uint64_t timestamp;
    uint32_t symbol_id;
    double bid_price;
    double ask_price;
    uint32_t volume;
};

// Simulasi Hot-Path Trading Engine Processor
class OrderExecutionEngine {
public:
    explicit OrderExecutionEngine(std::pmr::memory_resource* upstream_resource)
        : buffer_resource_(upstream_resource) {}

    void process_batch(const std::vector<MarketTick>& incoming_ticks) {
        // Alokasikan memori lokal batch langsung dari stack-backed arena
        // Tidak ada syscall malloc/free di dalam loop ini
        std::pmr::vector<MarketTick> local_pipeline(&buffer_resource_);
        local_pipeline.reserve(incoming_ticks.size());

        for (const auto& tick : incoming_ticks) {
            if (tick.ask_price - tick.bid_price > 0.01) {
                local_pipeline.push_back(tick);
            }
        }

        std::cout << "[Engine] Processed: " << local_pipeline.size() 
                  << " orders across pipeline without system heap allocation.\n";
    }

private:
    std::pmr::monotonic_buffer_resource buffer_resource_;
};

int main() {
    // Siapkan 512KB pre-allocated buffer pada Stack frame (Zero Kernel Heap Hit)
    std::array<std::byte, 524288> stack_memory_pool;

    // Upstream resource menggunakan monotonic buffer diikat ke stack space
    std::pmr::monotonic_buffer_resource mem_pool(
        stack_memory_pool.data(), 
        stack_memory_pool.size(),
        std::pmr::null_memory_resource() // Menolak fallback ke OS Heap (Deterministic Fail-Fast)
    );

    OrderExecutionEngine engine(&mem_pool);

    std::vector<MarketTick> mock_market_data = {
        {1708890001, 101, 150.20, 150.25, 1000},
        {1708890002, 102, 2800.10, 2800.11, 50},
        {1708890003, 101, 150.21, 150.30, 2500}
    };

    engine.process_batch(mock_market_data);
    return 0;
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario:
Sebuah payment processing engine memproses hingga **150.000 transaksi per detik (TPS)** pada event *Flash Sale*. Sistem eksisting mengalami bottleneck: terjadi *latency spikes* p99.9 hingga **450 milidetik** yang mengakibatkan transaction timeout.

#### Investigasi Teknis:
Melalui profiler Linux `perf` dan `eBPF/bcc tools`, tim engineering menemukan bahwa core processor menghabiskan **42% total CPU time** pada lock internal glibc runtime: `pthread_mutex_lock` di dalam `malloc` dan `free` (heap contention global antar 64 thread worker).

#### Solusi Arsitektur:
1. **Thread-Local PMR Arena**: Setiap thread worker diberikan pre-allocated `std::pmr::monotonic_buffer_resource` sebesar 8 MB.
2. **Recycled Pool Strategy**: Mengubah serialisasi JSON/Payload dari `std::string` dan `std::vector` standar ke `std::pmr::string` dan `std::pmr::vector`.
3. **Batch Reclaim**: Reset bump pointer di akhir setiap siklus payload transaksi.

```cpp
// Arsitektur Thread-Safe Scratchpad Memory Context
class WorkerRequestContext {
public:
    static constexpr size_t SCRATCHPAD_SIZE = 8 * 1024 * 1024; // 8MB

    WorkerRequestContext() 
        : arena_memory_(std::make_unique<std::byte[]>(SCRATCHPAD_SIZE)),
          monotonic_pool_(arena_memory_.get(), SCRATCHPAD_SIZE, std::pmr::null_memory_resource()) {}

    void reset_arena() noexcept {
        monotonic_pool_.release(); // Instant O(1) deallocation: reset bump pointer
    }

    std::pmr::memory_resource* get_resource() noexcept {
        return &monotonic_pool_;
    }

private:
    std::unique_ptr<std::byte[]> arena_memory_;
    std::pmr::monotonic_buffer_resource monotonic_pool_;
};

// Implementasi Worker Loop:
void transaction_worker_loop(int thread_id) {
    WorkerRequestContext context;

    while (true) {
        // Ambil payload dari queue lock-free...
        {
            // Semua dynamic memory string dan collection terisolasi di thread arena
            std::pmr::string payload(context.get_resource());
            payload = "{\"transaction_id\": \"987654321\", \"amount\": 1500000}";
            
            // Proses decoding & validasi bisnis...
        }
        
        // Bersihkan memori satu batch dalam 0 siklus overhead malloc/free
        context.reset_arena();
    }
}
```

#### Hasil Metrik Produksi:
- **Throughput**: Naik dari 150.000 TPS menjadi **380.000 TPS**.
- **Latency p99.9**: Terpangkas dari **450ms** menjadi **1.2ms**.
- **CPU System Time (Kernel Overhead)**: Turun drastis dari **42%** ke **1.8%**.

---

### 9. Trade-offs

| Pendekatan Alokasi | Latency (Hot Path) | Memory Overhead | Kompleksitas Kode | Keamanan Terhadap Fragmentasi |
| :--- | :--- | :--- | :--- | :--- |
| **Global Heap (`malloc` / `new`)** | Tinggi (Non-deterministik, ada lock global) | Rendah (Metadata ~8-16 bytes per chunk) | Sangat Rendah (Default language standard) | Buruk (Dapat terfragmentasi dalam jangka panjang) |
| **`std::shared_ptr` + `make_shared`** | Sedang (Perlu update atomic counter) | Sedang (Control block 16-24 bytes) | Rendah | Mengikat lifetime memori data ke weak reference |
| **Monotonic PMR (`std::pmr`)** | Ekstrem Rendah ($O(1)$ pointer increment) | Sedang-Tinggi (Memori di-reserve di awal) | Tinggi (Harus mengalirkan pointer context) | Sempurna (Bebas fragmentasi internal) |
| **Object Pooling (Free-list)** | Sangat Rendah ($O(1)$ pop/push stack) | Rendah (Hanya ukuran pointer per slot) | Tinggi (Manajemen recycle manual & re-init) | Terisolasi pada fixed-size object type |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Circular Reference Memory Leak pada `std::shared_ptr`
- **Gejala**: Memori heap terus merangkak naik (leak), meskipun objek induk keluar dari scope.
- **Root Cause**: Dua objek menyimpan `std::shared_ptr` yang saling mereferensikan satu sama lain, sehingga reference counter tidak pernah mencapai 0.
- **Solusi**: Pecah kepemilikan siklik dengan mengganti salah satu link menjadi `std::weak_ptr`.

#### 2. False Sharing pada Struktur Data Paralel
- **Gejala**: Menambah jumlah core/thread CPU justru menurunkan throughput komputasi.
- **Deteksi**: Jalankan Linux profiler: `perf c2c record -- ./my_binary` lalu `perf c2c report`. Perhatikan metrik "HITM" (Hit Modified Cacheline).
- **Solusi**: Terapkan alignment isolasi:
```cpp
struct alignas(64) ThreadData {
    uint64_t processed_counter{0}; // Terisolasi penuh pada satu cache line unik
};
```

#### 3. Dangling Reference pada Monotonic Buffer Reuse
- **Gejala**: Terjadi *undefined behavior*, korupsi data acak, atau crash `SIGSEGV`.
- **Root Cause**: Objek yang dialokasikan oleh memory resource masih diakses setelah method `.release()` dipanggil pada resource tersebut.
- **Troubleshooting**: Kompilasi dengan AddressSanitizer (ASan) untuk pinpointing seketika:
```bash
g++ -std=c++20 -fsanitize=address,undefined -g -O1 main.cpp -o main
./main
# ASan akan memunculkan laporan visual: "AddressSanitizer: heap-use-after-free"
```

---

### 11. Best Practices (Production Checklist)

1. [ ] **Rule of Zero/Five**: Jika kelas Anda mengelola raw resource, implementasikan Rule of Five secara eksplisit (Destructor, Copy Constructor, Copy Assignment, Move Constructor, Move Assignment). Jika tidak mengelola resource secara manual, patuhi Rule of Zero.
2. [ ] **Declare `noexcept` on Move**: Selalu tandai Move Constructor dan Move Assignment Operator dengan keyword `noexcept` agar `std::vector` menggunakan pemindahan cepat saat resizing, alih-alih fallback ke expensive deep-copy.
3. [ ] **Prefer `std::unique_ptr` over `std::shared_ptr`**: Default-kan kepemilikan resource bersifat eksklusif. Konversi ke `std::shared_ptr` hanya jika kepemilikan terdistribusi benar-benar dibutuhkan secara arsitektural.
4. [ ] **Enforce Fast-PMR Constraints**: Saat menggunakan `std::pmr::monotonic_buffer_resource`, gunakan `std::pmr::null_memory_resource()` sebagai fallback resource downstream jika Anda ingin menjamin zero heap memory allocations pada critical SLA blocks.
5. [ ] **Hardware Destructive Interference**: Pisahkan atomic counters yang diakses oleh thread paralel ke cache-line yang berbeda dengan `alignas(std::hardware_destructive_interference_size)`.
6. [ ] **Enable Sanitizers in CI Pipeline**: Jalankan unit test dan integration test suite minimal dengan flag kompilator `-fsanitize=address,undefined,leak`.

---

### 12. Hands-on Practice

Buat struktur direktori untuk praktikum module ini:
```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
```

#### Langkah 1: Buat `CMakeLists.txt`
```cmake
cmake_minimum_required(VERSION 3.20)
project(ModernMemoryArchitecture LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Compile flags untuk deteksi dini bugs
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra -Wpedantic -fsanitize=address,undefined -g")

add_executable(arena_pipeline src/main.cpp)
```

#### Langkah 2: Buat Source Code `src/main.cpp`
Implementasikan custom fixed-size memory arena allocator yang melacak metrik penggunaan byte tanpa overhead virtual dynamic dispatch.

```cpp
#include <iostream>
#include <cstddef>
#include <memory>
#include <vector>
#include <span>

class LinearArenaAllocator {
public:
    explicit LinearArenaAllocator(size_t capacity)
        : total_capacity_(capacity),
          buffer_(std::make_unique<std::byte[]>(capacity)),
          offset_(0) {}

    ~LinearArenaAllocator() = default;

    // Larang copy semantic
    LinearArenaAllocator(const LinearArenaAllocator&) = delete;
    LinearArenaAllocator& operator=(const LinearArenaAllocator&) = delete;

    // Izinkan move semantic
    LinearArenaAllocator(LinearArenaAllocator&& other) noexcept
        : total_capacity_(other.total_capacity_),
          buffer_(std::move(other.buffer_)),
          offset_(other.offset_) {
        other.total_capacity_ = 0;
        other.offset_ = 0;
    }

    void* allocate(size_t bytes, size_t alignment = alignof(std::max_align_t)) {
        // Hitung padding alignment
        size_t current_address = reinterpret_cast<size_t>(buffer_.get() + offset_);
        size_t padding = (alignment - (current_address % alignment)) % alignment;

        if (offset_ + padding + bytes > total_capacity_) {
            throw std::bad_alloc(); // Alokasi melebihi batas arena
        }

        offset_ += padding;
        void* allocated_ptr = buffer_.get() + offset_;
        offset_ += bytes;

        return allocated_ptr;
    }

    void reset() noexcept {
        offset_ = 0; // O(1) deallocation: reset pointer penanda
    }

    [[nodiscard]] size_t bytes_allocated() const noexcept {
        return offset_;
    }

    [[nodiscard]] size_t remaining_capacity() const noexcept {
        return total_capacity_ - offset_;
    }

private:
    size_t total_capacity_;
    std::unique_ptr<std::byte[]> buffer_;
    size_t offset_;
};

struct ExecutionReport {
    uint64_t execution_id;
    double fill_price;
    uint32_t filled_quantity;
    char client_tag[16];
};

int main() {
    std::cout << "[Step 1] Inisialisasi Arena Allocator sebesar 1KB...\n";
    LinearArenaAllocator arena(1024);

    std::cout << "Available bytes: " << arena.remaining_capacity() << "\n";

    // Alokasikan beberapa instance ExecutionReport ke dalam arena
    std::cout << "\n[Step 2] Alokasi data transaksi secara sequential...\n";
    for (int i = 0; i < 5; ++i) {
        void* raw_mem = arena.allocate(sizeof(ExecutionReport), alignof(ExecutionReport));
        auto* report = new (raw_mem) ExecutionReport{
            .execution_id = static_cast<uint64_t>(1000 + i),
            .fill_price = 105.50 + (i * 0.1),
            .filled_quantity = static_cast<uint32_t>(50 * (i + 1)),
            .client_tag = "CLIENT-ALPHA"
        };
        std::cout << "Allocated ExecutionReport ID: " << report->execution_id 
                  << " at address: " << raw_mem 
                  << " | Current Arena Usage: " << arena.bytes_allocated() << " bytes\n";
    }

    std::cout << "\n[Step 3] Reset Arena Allocator (O(1) Tear Down)...\n";
    arena.reset();
    std::cout << "Arena reset berhasil. Digunakan saat ini: " << arena.bytes_allocated() << " bytes.\n";

    return 0;
}
```

#### Langkah 3: Build dan Run
```bash
cmake -B build
cmake --build build
./build/arena_pipeline
```

---

### 13. Exercise

#### Level Easy
- **Topik**: Type-Safe Linux Socket Wrapper.
- **Tugas**: Buat kelas RAII `ScopedSocket` menggunakan idiom custom deleter pada `std::unique_ptr`. Kelas harus mampu menutup file descriptor socket menggunakan fungsi POSIX `::close(sock_fd)` secara otomatis saat instance keluar dari scope. Pastikan operator assignment mencegah kebocoran file descriptor yang telah terbuka sebelumnya.

#### Level Medium
- **Topik**: Thread-Safe High-Performance Ring Buffer Pool.
- **Tugas**: Bangun implementasi Object Pool fixed-capacity yang menggunakan `std::vector` terisolasi dan *free-list* internal berbasis index. Ambil objek menggunakan return type `std::unique_ptr<T, CustomPoolDeleter>` di mana pemanggilan deleter mengembalikan slot memori objek ke free-list pool tanpa memanggil OS `free()`.

#### Level Hard
- **Topik**: Heterogeneous PMR Frame Allocator with Metric Tracker.
- **Tugas**: Implementasikan subclass custom dari `std::pmr::memory_resource` bernama `MonitoredMemoryResource`. Subclass ini harus membungkus instance `monotonic_buffer_resource` yang mendasarinya.
  - Implementasikan `do_allocate` dan `do_deallocate`.
  - Catat *High-Water Mark* (puncak pemakaian memori) dan total hitungan pemanggilan alokasi.
  - Jika alokasi melebihi batas buffer yang disediakan, throw `std::bad_alloc` tanpa fallback ke heap alokator global.

---

### 14. Challenge

#### Sistem Ingestion Telemetri Jaringan Zero-Allocation (High-Throughput Hot-Path)

**Konteks Masalah**:
Anda sedang membangun sistem ingestion telemetri untuk gateway gateway jaringan 100-Gbps. Gateway ini membedah paket biner mentah (`RawPacket`), mengekstrak metrik, dan menaruhnya ke ring-buffer. Persyaratan latensi sangat ketat: **P99.99 Latency < 5 mikrodetik per paket**.

**Spesifikasi Desain & Batasan**:
1. **Zero Heap Allocation**: Tidak boleh ada pemanggilan runtime kernel allocator (`malloc`, `free`, `new`, `delete`) selama siklus hot-path eksekusi.
2. **Dynamic Elements**: Setiap paket memiliki sub-komponen header dengan panjang bervariasi (variable-length headers) yang harus disimpan dalam struktur dinamis (`std::pmr::vector` atau `std::pmr::string`).
3. **Multi-Thread Contention Free**: Setiap thread worker memiliki arena memorinya sendiri yang disejajarkan dengan ukuran cache line (`alignas(64)`), mencegah fenomena cache contention / false sharing antar worker threads.
4. **Resiliency**: Jika ada paket rusak atau ukurannya melebihi kapasitas arena, sistem harus melakukan fail-fast, mencatat metrik error, dan mereset buffer arena tanpa mengakibatkan *memory leak* atau *undefined behavior*.

**Tugas Anda**:
Rancang arsitektur memory pool lengkap beserta class wrapper RAII dan buktikan ketiadaan alokasi heap global dengan meng-override operator global `new` dan `new[]` untuk melempar `std::runtime_error` jika dipanggil di dalam hot path testing loop.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. **Mengapa pemanggilan `std::make_shared` lebih efisien daripada konstruksi manual `std::shared_ptr<T>(new T())`?**
   - *Jawaban*: `std::make_shared` melakukan satu alokasi memori tunggal yang menampung objek `T` sekaligus Control Block secara kontigu. Konstruksi manual membutuhkan dua alokasi memori heap terpisah (satu untuk objek `T`, satu untuk Control Block), meningkatkan fragmentasi dan overhead syscall.
2. **Kapan destruktor objek yang dikelola oleh `std::shared_ptr` dieksekusi?**
   - *Jawaban*: Destruktor objek dieksekusi seketika saat *Strong Reference Count* mencapai angka 0, tidak bergantung pada apakah *Weak Reference Count* masih bernilai lebih dari 0 atau tidak.
3. **Mengapa Custom Deleter pada `std::unique_ptr` mempengaruhi ukuran footprint tipenya (`sizeof`), sedangkan pada `std::shared_ptr` tidak?**
   - *Jawaban*: Pada `std::unique_ptr`, Custom Deleter menjadi bagian dari parameter template tipe data tersebut dan disimpan langsung di dalam instance (jika bukan Empty Base Optimization). Pada `std::shared_ptr`, deleter di-*type-erase* dan disimpan secara dinamis di dalam heap Control Block, sehingga ukuran `std::shared_ptr` konstan sebesar 2 pointer.
4. **Apa fungsi dari `std::pmr::null_memory_resource()`?**
   - *Jawaban*: Sebagai upstream resource pemutus yang selalu melempar exception `std::bad_alloc` jika alokasi diminta. Digunakan untuk mencegah alokator arena fallback secara diam-diam ke alokasi global heap OS.
5. **Bagaimana cara mencegah kebocoran memori akibat circular reference antara dua objek yang saling berbagi `std::shared_ptr`?**
   - *Jawaban*: Memutus salah satu arah kepemilikan siklik dengan mengubah tipe referensi menjadi `std::weak_ptr` (non-owning reference).

#### Intermediate (5 Soal)
1. **Apa perbedaan teknis antara `alignas(std::hardware_destructive_interference_size)` dan `alignas(std::hardware_constructive_interference_size)`?**
   - *Jawaban*: *Destructive interference size* memberikan padding/alignment minimum untuk menghindari **False Sharing** (memastikan dua variabel tidak berada di cache line 64-byte yang sama). *Constructive interference size* memberikan ukuran batasan maksimum untuk memaksimalkan **True Sharing** (memastikan dua variabel muat di dalam satu cache line yang sama demi memaksimalkan efisiensi prefetching CPU).
2. **Mengapa destruktor dari memory arena (`std::pmr::monotonic_buffer_resource`) tidak memanggil destruktor objek bertipe non-trivially destructible secara individual?**
   - *Jawaban*: Monotonic buffer hanya membebaskan memory footprint arena secara massal dengan melepaskan buffer byte. Ia tidak melacak tipe data individual atau siklus hidup objek yang telah dibuat di dalamnya. Objek non-trivial harus didestruksi secara manual (misal via direct call `ptr->~T()`) jika memiliki resource eksternal yang harus dibersihkan sebelum arena dibebaskan.
3. **Mengapa Move Constructor yang didefinisikan secara kustom harus ditandai dengan keyword `noexcept`?**
   - *Jawaban*: Kontainer standar seperti `std::vector` mengutamakan *Strong Exception Safety Guarantee*. Jika move constructor tidak ditandai `noexcept`, `std::vector` akan melakukan deep copy yang mahal saat proses realokasi memori internal daripada memindahkan (*move*) elemen, untuk mencegah hilangnya data jika terjadi exception di tengah operasi.
4. **Apa bahaya dari penggunaan `std::weak_ptr::lock()` di dalam lingkungan multi-threaded frekuensi tinggi?**
   - *Jawaban*: Operasi `lock()` memicu atomic increment pada Strong Reference Counter di Control Block. Pada thread concurrency tinggi, ini memicu cache bouncing dan contention bus antar core, mereduksi keunggulan latensi.
5. **Jelaskan perbedaan lifetime memori antara objek `T` dan Control Block ketika menggunakan `std::make_shared` jika masih terdapat `std::weak_ptr` aktif!**
   - *Jawaban*: Karena `std::make_shared` menggabungkan alokasi memori objek `T` dan Control Block dalam satu chunk kontigu, memori fisik untuk `T` tidak dapat di-*free* ke OS saat destruktor `T` selesai dipanggil. Seluruh chunk memori baru benar-benar dikembalikan ke heap sistem setelah Weak Reference Counter terakhir pada Control Block mencapai 0.

#### Skenario Kasus Produksi (3 Soal)
1. **Skenario 1**: Aplikasi real-time market data Anda mengalami crash acak *Segmentation Fault* (`SIGSEGV`) setelah berjalan 3 hari di production environment. Log menunjukkan error terjadi di dalam method traversal `std::pmr::vector`. Saat dianalisis dengan AddressSanitizer, tercatat error `heap-use-after-free`.
   - *Analisis Akar Masalah*: Upstream `std::pmr::monotonic_buffer_resource` didestruksi atau di-`.release()`, sementara instance `std::pmr::vector` yang menggunakan buffer tersebut masih hidup dan mencoba mengakses memori yang sudah di-reset.
   - *Solusi Perbaikan*: Pastikan lifetime container selalu lebih pendek daripada lifetime arena resource induknya (patuhi scoping stack bertingkat), atau buat container berada di scope lokal sebelum fungsi arena release dipanggil.

2. **Skenario 2**: Dua thread worker mengakses dua variabel atomic counter yang didefinisikan bersebelahan di dalam memori global (`std::atomic<uint64_t> g_counter_a; std::atomic<uint64_t> g_counter_b;`). Saat benchmark 1 thread berjalan cepat, namun saat dijalankan pada 32 core CPU paralel, latency melonjak 15x lipat.
   - *Analisis Akar Masalah*: Terjadi fenomena *False Sharing*. Meskipun dua atomic counter tersebut secara logika independen, keduanya berada pada 64-byte L1 Cache Line yang sama, sehingga modifikasi pada salah satu core secara berulang-ulang menginvalidasi cache line di 31 core lainnya via protokol cache coherency.
   - *Solusi Perbaikan*: Terapkan pemisahan alignment eksplisit:
     ```cpp
     struct alignas(std::hardware_destructive_interference_size) IsolatedCounter {
         std::atomic<uint64_t> value{0};
     };
     IsolatedCounter g_counter_a;
     IsolatedCounter g_counter_b;
     ```

3. **Skenario 3**: Anda merefaktor kode warisan (legacy) dari raw pointer `Socket* s = new Socket()` menjadi `std::shared_ptr<Socket>`. Namun, setelah refaktor ke deployment cluster, penggunaan memori (Resident Set Size / RSS) melonjak dua kali lipat dan CPU load naik 20%.
   - *Analisis Akar Masalah*: Penggunaan `std::shared_ptr` yang berlebihan menambahkan alokasi dinamis Control Block tambahan untuk setiap objek (jika tidak menggunakan `std::make_shared`), serta menambahkan atomic reference counting increments/decrements setiap kali pointer dipassing secara *pass-by-value* ke dalam sub-rutin internal pemrosesan.
   - *Solusi Perbaikan*: Kembalikan kepemilikan menjadi tunggal dengan `std::unique_ptr`. Ganti signature pemanggilan method internal yang hanya membutuhkan akses observasi read-only menjadi *raw reference* (`const Socket&`) atau raw pointer (`Socket*`), mengeliminasi atomic overhead sama sekali.

---

### 16. Summary

1. **Deterministic Resource Ownership**: RAII modern melampaui sekadar dealokasi memori; ia merupakan kerangka manajemen siklus hidup terpadu untuk kernel locks, socket, descriptor, dan GPU state. Hindari raw pointer manual untuk ownership semantics.
2. **Smart Pointer Internals**: `std::unique_ptr` memiliki zero overhead jika digunakan dengan stateless lambda/struct deleter. Pahami biaya tersembunyi `std::shared_ptr` (alokasi control block, atomic increments) dan hindari circular references menggunakan `std::weak_ptr`.
3. **High-Performance Memory Resources (`std::pmr`)**: Mengalihkan manajemen alokasi hot path dari global kernel heap ke memory arena bertipe Monotonic atau Pool menghasilkan determinisme latensi tinggi ($O(1)$) dan performa cache yang optimal.
4. **Cache Architecture Awareness**: Arsitektur concurrent memory modern menuntut pemahaman mendalam tentang batasan fisik CPU (Cache Lines, False Sharing, dan Alignment). Pengabaian terhadap destructive interference akan mengorbankan skalabilitas multi-core throughput.
5. **Tooling as Safety Gate**: Validasi runtime audit menggunakan sanitizers (ASan, LSan, UBSan) adalah standar industri wajib untuk mendeteksi memory leaks, use-after-free, dan buffer overflows sebelum kode masuk ke lingkungan produksi enterprise.