# Kurikulum Enterprise C++: Standard Library Mastery (STL+)
## Bab 05: Standard Library Mastery (STL+)
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, *Systems/Software Engineer* mampu:
1. **Mengeliminasi Dynamic Allocation Overhead**: Menguasai arsitektur *Polymorphic Memory Resources* (`std::pmr`) dan mendesain *custom memory resource* (arena, monotonic, pool) untuk mencapai alokasi memori berlatensi deterministik $O(1)$ pada *hot path*.
2. **Mengeksploitasi Cache Locality & Data Layout**: Memilih dan menstrukturkan kontainer STL berdasarkan layout memori fisik CPU (L1/L2/L3 cache lines), memahami implikasi *node-based* vs *contiguous containers*, serta mengeliminasi *false sharing* dengan `alignas(std::hardware_destructive_interference_size)`.
3. **Membangun Pipeline Data Zero-Cost**: Mengimplementasikan *Ranges* (`std::ranges`, `std::views`) dan non-owning views (`std::span`, `std::string_view`) dengan abstraksi *zero-copy* tanpa mengorbankan keamanan *memory lifecycle*.
4. **Menerapkan Error Handling Monadik Modern**: Menggantikan alur exception tradisional pada *critical path* menggunakan `std::expected` (C++23) dan `std::optional` untuk mencapai *monadic error handling* yang deterministik dan *branch predictor friendly*.
5. **Menjamin Thread Safety Tingkat Rendah**: Memanfaatkan primitif konkurensi STL modern (`std::atomic`, `std::atomic_ref`, `std::barrier`, `std::latch`) dengan pemahaman model memori formal (*sequential consistency*, *acquire-release semantics*).

---

### 2. Prerequisite
Untuk mengikuti modul ini dengan optimal, peserta wajib menguasai:
- **C++ Core Language**: Rvalue references, *perfect forwarding* (`std::forward`), Move Semantics, Variadic Templates, dan Concepts (C++20).
- **Computer Architecture Fundamentals**: Hirarki memori CPU (L1/L2/L3 Cache, TLB, Cache Lines 64 bytes), *instruction pipelining*, *branch prediction*, dan *virtual memory paging*.
- **Operating System Primitives**: POSIX `mmap`, `brk`, `mprotect`, virtual address space layout, page faults, dan *kernel-level context switching*.
- **Tools**: GCC 13+ atau Clang 16+, CMake 3.25+, GDB/LLDB, Valgrind/ASan, dan Linux Perf profiler.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. STL Allocator Mechanics & std::pmr (Polymorphic Memory Resources)
Secara historis (C++98 hingga C++14), alokator pada STL merupakan bagian dari sistem *type identity*:
```cpp
std::vector<int, MyAllocator<int>> vec; // Tipe berbeda secara kompilasi dari std::vector<int>
```
Hal ini menyebabkan *template bloat* dan ketidakmampuan mengubah strategi alokasi secara dinamis saat *runtime*. 

C++17 memperkenalkan `std::pmr`, yang memisahkan antarmuka alokasi melalui *dynamic dispatch* (vtable) berbasis kelas abstrak dasar: `std::pmr::memory_resource`.

```
                    +--------------------------------+
                    |  std::pmr::memory_resource     |
                    +--------------------------------+
                    | + allocate(bytes, align)       |
                    | + deallocate(p, bytes, align)  |
                    | + is_equal(other)              |
                    +---------------+----------------+
                                    |
            +-----------------------+-----------------------+
            |                                               |
+-----------v---------------------+       +-----------------v--------------------+
| monotonic_buffer_resource       |       | unsynchronized_pool_resource         |
+---------------------------------+       +--------------------------------------+
| - Alokasi linier cepat ($O(1)$) |       | - Pool berbasis chunk (fixed-size)   |
| - Tanpa individual deallocate   |       | - Mengeliminasi fragmentasi memori   |
| - Deallokasi masal pada dtor    |       | - Didesain khusus thread-local       |
+---------------------------------+       +--------------------------------------+
```

Mekanisme kerja internal `std::pmr::monotonic_buffer_resource`:
1. Menerima buffer statis (misalnya di stack) atau alokasi awal via *upstream allocator*.
2. Mempertahankan offset pointer internal: `uintptr_t current_ptr`.
3. Pada pemanggilan `do_allocate(bytes, alignment)`:
   - Menghitung padding alignment: $\Delta = (\text{align} - (\text{current\_ptr} \pmod{\text{align}})) \pmod{\text{align}}$.
   - Memverifikasi apakah $\text{current\_ptr} + \Delta + \text{bytes} \le \text{buffer\_end}$.
   - Menggeser pointer `current_ptr += \Delta + bytes`.
   - Kompleksitas: ~3-5 instruksi assembly x86-64, tanpa *system call*, tanpa penguncian mutex (`lock cmpxchg`).
4. `do_deallocate()` adalah operasi *no-op*. Memori hanya dikembalikan ke *upstream* ketika instance resource dihancurkan.

#### B. Cache Locality: Contiguous vs Node-Based Containers
Karakteristik performa kontainer STL ditentukan oleh layout fisiknya dalam *cache line* (umumnya 64 bytes):
- **Contiguous (`std::vector`, `std::array`, `std::span`)**: Elemen dialokasikan berdampingan. Ketika elemen index `0` diakses, CPU *hardware prefetcher* memuat elemen `1` hingga `N` ke L1 Data Cache secara spekulatif. Cache miss rate $\to 0$ untuk iterasi linier.
- **Node-Based (`std::list`, `std::map`, `std::unordered_map`)**: Setiap penambahan elemen mengalokasikan node terpisah:
  ```cpp
  struct __tree_node {
      __tree_node* parent;
      __tree_node* left;
      __tree_node* right;
      bool color;
      Value value; // Padding & alignment overhead signifikan
  };
  ```
  Setiap *dereference* pointer menghasilkan *pointer chasing* yang berpotensi memicu *LLC (Last Level Cache) miss* (~200 siklus CPU vs 4 siklus CPU L1 hit).

#### C. Lazy Evaluation Pipeline: Ranges & Views (C++20)
`std::ranges::views` menerapkan *lazy evaluation* murni melalui *expression templates* dan konsep iterator modern (*sentinel*).
- Sebuah View tidak memiliki kepemilikan (*non-owning*) atas data.
- Pipeline operator (`|`) menyusun komposisi tipe pembungkus (*wrapper types*):
  `vec | views::filter(p) | views::transform(f)`
  menghasilkan tipe konkret:
  `ranges::transform_view<ranges::filter_view<ranges::ref_view<vector<int>>, decltype(p)>, decltype(f)>`.
- Eksekusi komputasi hanya terjadi saat iterator view di-*dereference* (`operator*()`). Tidak ada alokasi buffer sementara (*intermediate vectors*).

---

### 4. Why & What

| Fitur / Komponen | What (Definisi & Mekanisme) | Why (Alasan Penggunaan di Enterprise) |
| :--- | :--- | :--- |
| **`std::pmr`** | Abstraksi alokator polimorfik berbasis runtime resource. | Mengeliminasi biaya `malloc`/`free` OS, fragmentasi memori, serta lock contention heap pada sistem multi-core berkecepatan tinggi. |
| **`std::span`** | Non-owning view berukuran kontinu atas array/buffer memori. | Menggantikan pasangan pointer + ukuran mentah (`T* ptr, size_t sz`). Mencegah decay array dan *bounds-checking bugs* tanpa *heap allocation*. |
| **`std::ranges`** | Abstraksi algoritma dan views berbasis *concepts* dengan *lazy evaluation*. | Menghindari pembuatan buffer temporer pada transformasi data berantai, menghasilkan kode lebih deklaratif dan bebas alokasi. |
| **`std::expected`** | Kontainer serikat diskriminan (*discriminated union*) untuk nilai atau error. | Mengeliminasi biaya unwinding stack dari C++ exceptions pada alur sistem deterministik berlatensi rendah (*zero overhead error path*). |
| **`std::flat_map` (C++23)** | Adaptor kontainer asosiatif yang menyimpan keys & values dalam vektor terpisah/kontinu. | Menawarkan performa look-up yang jauh lebih cepat daripada `std::map` berbasis node (Red-Black Tree) karena mengeksploitasi cache locality dan SIMD search. |

---

### 5. How (Workflow Detail)

Arsitektur siklus hidup alokasi memori berlatensi ultra-rendah menggunakan PMR dan Ranges:

```
[ Request Masuk / Network Packet ]
              │
              ▼
[ Stack Memory Reservation: std::byte buffer[65536] ]
              │
              ▼
[ std::pmr::monotonic_buffer_resource (Buffer Stack) ]
              │
              ▼
[ PMR Vectors / Maps dialokasikan di dalam Buffer ]
              │
              ├── Operasi Eksekusi & Transformasi
              │   (Menggunakan std::ranges & std::span)
              │
              ├── Serialisasi / Dispatching Hasil
              │
              ▼
[ Scope Selesai (RAII) ]
              │
              ▼
[ Monotonic Buffer Direset Tanpa System Call ]
              │
              ▼
[ Memory Siap Digunakan untuk Request Berikutnya ]
```

1. **Inisialisasi**: Alokasikan *pre-allocated buffer* pada stack lokal thread atau *huge page shared memory*.
2. **Koneksi PMR**: Bungkus buffer menggunakan `std::pmr::monotonic_buffer_resource`. Tentukan *fallback upstream* (misal: `std::pmr::get_default_resource()`).
3. **Penyimpanan Struktur Data**: Instansiasi kontainer PMR (`std::pmr::vector`, `std::pmr::string`) dengan menyuntikkan resource tersebut via konstruktor.
4. **Transformasi Data**: Terapkan algoritma modern melalui `std::views` dan `std::span` untuk memproses data secara *in-place*.
5. **Teardown**: Biarkan scope berakhir. Destruktor monotonic resource mereset offset alokasi secara instan ($O(1)$) tanpa memanggil `free()` satu per satu pada tiap elemen.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Hotel vs Kontainer Pengiriman Kontinu
- **Node-based Allocator (`std::map`, `std::list`)**: Seperti menyewa 1.000 kamar hotel di seluruh penjuru kota secara acak untuk 1.000 karyawan. Setiap kali manajer ingin memeriksa pekerjaan mereka, ia harus berkendara melintasi kemacetan kota dari satu gedung ke gedung lain (*pointer chasing & cache misses*).
- **Contiguous PMR Vector**: Seperti menyewa satu aula konvensi besar (*pre-allocated buffer*). Semua 1.000 karyawan duduk berjejer di meja yang bersambungan. Manajer cukup melirik satu baris untuk melihat semuanya dalam satu kedipan mata (*L1 Cache line prefetching*).

#### Layout Memori Cache Line (64 Bytes)
```
Kasus A: std::vector<uint32_t> (Contiguous Buffer)
Cache Line 0 (64 Bytes):
+------+------+------+------+------+------+------+------+------+------+------+------+------+------+------+------+
|Val 0 |Val 1 |Val 2 |Val 3 |Val 4 |Val 5 |Val 6 |Val 7 |Val 8 |Val 9 |Val 10|Val 11|Val 12|Val 13|Val 14|Val 15|
+------+------+------+------+------+------+------+------+------+------+------+------+------+------+------+------+
^ Satu fetch memori memuat 16 nilai integer 32-bit secara bersamaan.

Kasus B: std::list<uint32_t> (Node-Based Heap Fragmentation)
Memory Addr: 0x1000                    Addr: 0x48A0                    Addr: 0x9020
+-------------------------+            +-------------------------+     +-------------------------+
| Prev | Next | Val 0     | ---------> | Prev | Next | Val 1     | --> | Prev | Next | Val 2     |
+-------------------------+            +-------------------------+     +-------------------------+
[Cache Line Hit: 1 node]               [Cache Line Miss: fetch]        [Cache Line Miss: fetch]
(Overhead pointer: 16 bytes overhead per 4 bytes payload pada arsitektur 64-bit).
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: PMR Stack-Allocated Vector vs Default Heap Vector
Memperlihatkan eliminasi alokasi heap via `monotonic_buffer_resource`.

```cpp
#include <iostream>
#include <vector>
#include <memory_resource>
#include <array>
#include <chrono>

void simple_pmr_demonstration() {
    // Buffer memori lokal stack 1 KiB
    std::array<std::byte, 1024> stack_mem;

    // Resource monotonic yang menggunakan stack memory di atas
    std::pmr::monotonic_buffer_resource mem_pool(
        stack_mem.data(), 
        stack_mem.size(), 
        std::pmr::null_memory_resource() // Error jika kehabisan memori, jangan lempar ke heap
    );

    // Vector yang terikat secara polimorfik ke stack mem_pool
    std::pmr::vector<int> pmr_vec(&mem_pool);

    for (int i = 0; i < 100; ++i) {
        pmr_vec.push_back(i * 10);
    }

    std::cout << "PMR Vector size: " << pmr_vec.size() << '\n';
    std::cout << "Element ke-5: " << pmr_vec[5] << '\n';
    // Selesai scope: Nol panggilan ke free()/OS heap deallocation
}
```

#### B. Practical Example: High-Throughput Market Data Tick Engine (C++20/C++23)
Menerapkan `std::pmr`, `std::span`, `std::ranges`, dan `std::expected` pada pipeline pemrosesan order financial trading.

```cpp
#include <iostream>
#include <vector>
#include <string_view>
#include <memory_resource>
#include <span>
#include <ranges>
#include <expected>
#include <chrono>
#include <cstdint>

enum class EngineError : uint8_t {
    BufferOverflow,
    InvalidPriceTick,
    CorruptedHeader
};

struct alignas(32) MarketTick {
    uint64_t timestamp_ns;
    uint32_t symbol_id;
    double price;
    uint32_t volume;
    char flags;
};

class OrderExecutionEngine {
public:
    explicit OrderExecutionEngine(std::pmr::memory_resource* upstream)
        : arena_resource_(buffer_.data(), buffer_.size(), upstream) {}

    // Zero-allocation processing pipeline
    std::expected<double, EngineError> process_batch(std::span<const MarketTick> ticks) noexcept {
        if (ticks.empty()) {
            return std::unexpected(EngineError::CorruptedHeader);
        }

        // Alokasikan scratchpad vector sementara di stack buffer PMR
        std::pmr::vector<MarketTick> filtered_ticks(&arena_resource_);
        filtered_ticks.reserve(ticks.size());

        // Range-based filter pipeline (eksekusi zero-copy)
        auto high_volume_filter = ticks 
            | std::views::filter([](const MarketTick& t) noexcept { 
                return t.volume > 1000 && t.price > 0.0; 
              });

        for (const auto& tick : high_volume_filter) {
            filtered_ticks.push_back(tick);
        }

        if (filtered_ticks.empty()) {
            return std::unexpected(EngineError::InvalidPriceTick);
        }

        // Kalkulasi VWAP (Volume Weighted Average Price)
        double total_value = 0.0;
        uint64_t total_volume = 0;

        for (const auto& t : filtered_ticks) {
            total_value += (t.price * t.volume);
            total_volume += t.volume;
        }

        arena_resource_.release(); // Reset pointer monotonic buffer instan $O(1)$
        return total_value / static_cast<double>(total_volume);
    }

private:
    alignas(64) std::array<std::byte, 128 * 1024> buffer_; // 128 KiB scratchpad L2/L3 target
    std::pmr::monotonic_buffer_resource arena_resource_;
};

int main() {
    alignas(64) std::array<MarketTick, 4> raw_ticks = {{
        {1672531199000000000ULL, 101, 150.25, 500, 0x01},
        {1672531199000001000ULL, 101, 150.50, 2500, 0x01},
        {1672531199000002000ULL, 102, 2800.10, 1200, 0x01},
        {1672531199000003000ULL, 101, -5.00, 5000, 0x02} // Invalid price
    }};

    OrderExecutionEngine engine(std::pmr::null_memory_resource());
    auto result = engine.process_batch(raw_ticks);

    if (result.has_value()) {
        std::cout << "Batch VWAP calculated: " << *result << '\n';
    } else {
        std::cerr << "Processing failure: " << static_cast<int>(result.error()) << '\n';
    }

    return 0;
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Problem
Sistem *Ultra-Low Latency Order Routing Gateway* di bursa berjangka global mengalami *latency spikes* (P99.99 > 850 mikrosekon) saat volume transaksi melonjak (*market open*).
Investigasi menggunakan profiler Linux `perf` dan `eBPF` mengungkap akar masalah:
1. `glibc malloc` mengalami *lock contention* antar-*worker threads* di dalam fungsi `ptmalloc` saat memvalidasi *chunks*.
2. Parsing pesan FIX (*Financial Information eXchange*) membuat ratusan ribu instansiasi `std::string` dan `std::vector` sementara.
3. *Cache invalidation* terjadi secara masif akibat fragmentasi heap di memori virtual.

#### Solusi Arsitektur
1. **Thread-Isolated Monotonic PMR Buffers**: Setiap core CPU di-*pin* (*core pinning via pthread_setaffinity_np*) ke thread parsing mandiri. Setiap thread memiliki alokasi 16 MiB *HugePages* (2 MiB pages via `mmap(MAP_HUGETLB)`) yang dibungkus oleh `std::pmr::monotonic_buffer_resource`.
2. **Zero-Copy Parser dengan `std::string_view` & `std::span`**: Data paket jaringan dari antarmuka Kernel-Bypass (Solarflare OpenOnload) dialirkan langsung tanpa penyalinan byte payload. Struktur pesan dianalisis menggunakan tokenisasi `std::string_view`.
3. **No-Throw Guarantee via Monadic `std::expected`**: Menghilangkan kompilasi tabel DWARF stack unwind (`-fno-exceptions`) di *hot path*, mengganti seluruh propagasi kesalahan parsing menggunakan `std::expected`.

```
[ NIC Ring Buffer (Solarflare EF_VI) ]
               │ (Zero-Copy Kernel-Bypass)
               ▼
[ std::span<const uint8_t> Raw Packet Frame ]
               │
               ▼
[ Parser Thread (Pinned Core 2) ] ── (Siklus Parsing Monotonik)
               │
               ├── Tokenisasi FIX Tag: std::string_view (No Alloc)
               ├── Objek Order: std::pmr::vector<OrderLeg> (PMR Arena)
               ├── Validasi Aturan: std::expected<ParsedOrder, ParseError>
               │
               ▼
[ Output: Lock-Free SPSC Ring Buffer ]
               │
               ▼
[ Memory Resource Reset (O(1) release()) ]
```

#### Hasil Metrik Produksi
- **P99 Latency**: Turun dari **850 µs** ke **1.8 µs**.
- **P99.99 Latency (Tail)**: Turun dari **4.2 ms** ke **4.1 µs**.
- **Throughput**: Meningkat dari **120.000 msgs/detik** menjadi **2.400.000 msgs/detik** per core tanpa degradasi memori.

---

### 9. Trade-offs

| Pendekatan / Fitur | Trade-off Positif (Keuntungan) | Trade-off Negatif (Konsekuensi & Kerugian) |
| :--- | :--- | :--- |
| **`std::pmr::monotonic_buffer_resource`** | Kecepatan alokasi $O(1)$ instan, saturasi cache maksimum, nol fragmentasi heap OS. | Memori terikat hingga masa hidup resource selesai; memori tidak dapat direklamasi per-elemen (*high high-water mark memory footprint*). |
| **`std::span` & `std::string_view`** | Mengeliminasi alokasi heap kloning buffer (*zero-copy*), overhead transfer register sangat kecil. | *Dangling reference risk*: Sangat rentan terhadap masalah *lifetime* jika data rujukan asli dihancurkan sebelum view selesai diproses. |
| **`std::ranges` (Lazy Views)** | Bebas alokasi sementara (*intermediate storage*), komposabilitas tinggi, keterbacaan deklaratif. | Waktu kompilasi (*compile-time*) meningkat signifikan; *stack trace error* templat sangat panjang jika konsep gagal dipenuhi. |
| **Node Containers (`std::map`, `std::list`)** | Tidak ada invalidasi iterator saat penambahan/penghapusan elemen di posisi lain; *stable memory address*. | Lokalitas cache terburuk; overhead pointer memakan 2x-4x kapasitas payload; beban berat pada memori subsistem CPU. |
| **`std::expected` (Monadic Error)** | Deterministik murni, tidak ada *performance drop* saat terjadi error branch; ramah sistem tanpa exception (`-fno-exceptions`). | Menambah ukuran return type pada register CPU; memerlukan kedisiplinan monadic composition code flow. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Dangling `std::string_view` dari Objek Temporer
*Kasus Salah*:
```cpp
std::string_view get_sub_token() {
    std::string temp = "INSTRUMENT_AAPL_TICK"; 
    return std::string_view(temp).substr(0, 10); // BUG: temp hancur saat keluar scope, view dangling!
}
```
*Solusi*: Pastikan kepemilikan string dasar melampaui lifetime view, atau jadikan view hanya sebagai parameter input, bukan tipe kembalian dari data lokal temporer.

#### 2. PMR Lifetime Inversion (Resource Terhancurkan Sebelum Kontainer)
*Kasus Salah*:
```cpp
std::pmr::vector<int>* create_leaky_vector() {
    std::array<std::byte, 512> buf;
    std::pmr::monotonic_buffer_resource mem_pool(buf.data(), buf.size());
    auto vec = new std::pmr::vector<int>(&mem_pool);
    vec->push_back(42);
    return vec; // FATAL: mem_pool dan buf hancur di sini! Pengaksesan vec memicu Undefined Behavior.
}
```
*Troubleshooting*: Gunakan AddressSanitizer (`-fsanitize=address`). Pastikan memori resource selalu diinstansiasi pada scope yang lebih luar (*outer scope*) daripada kontainer yang menggunakannya.

#### 3. Undefined Behavior pada PMR Monotonic Exhaustion
*Kasus Salah*:
Menggunakan `std::pmr::null_memory_resource()` sebagai upstream untuk mencegah fallback ke heap, namun ukuran buffer tidak diperhitungkan terhadap reallokasi kontainer (`vector::push_back` melipatgandakan kapasitas secara eksponensial).
*Gejala*: Program melempar `std::bad_alloc` secara tiba-tiba di dalam *critical loop*.
*Troubleshooting*: Selalu panggil `.reserve()` pada kontainer jika kapasitas maksimal dapat diprediksi, atau ukur *maximum high-water mark* saat *load test*.

#### 4. Range View Caching Mismatch
Beberapa view seperti `std::views::filter` bersifat non-const iterable cache:
```cpp
const auto evens = vec | std::views::filter(is_even);
// Error kompilasi jika memanggil begin() pada objek const di beberapa implementasi compiler C++20 standard library
```
*Solusi*: Pahami kapan views memerlukan mutasi status internal untuk iterator caching, dan hindari menandai views komposit sebagai `const`.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Explicit Reserve**: Selalu panggil `vec.reserve(N)` sebelum mengisi kontainer dinamis, termasuk pada PMR vectors.
2. [ ] **Hardware Alignment**: Gunakan `alignas(64)` pada buffer statis PMR untuk menjamin alignment tepat pada batas *Cache Line* CPU x86/ARM64.
3. [ ] **Upstream Isolation**: Untuk sistem *hard real-time*, konfigurasikan *upstream memory resource* ke `null_memory_resource()` guna memvalidasi bahwa tidak ada *spillover* alokasi ke heap OS.
4. [ ] **Pass-by-Value Views**: Operkan `std::span` dan `std::string_view` secara *value* (bukan *const reference*), karena ukurannya hanya 16 bytes (pointer + size), yang muat dalam dua register CPU 64-bit (`RDI`/`RSI`).
5. [ ] **No-Discard Everywhere**: Tandai fungsi yang mengembalikan `std::expected` atau pointer alokasi dengan `[[nodiscard]]`.
6. [ ] **No Unchecked Iteration**: Gunakan `std::span` dengan bounded checking di area batas (*boundary*), namun gunakan akses unchecked direct pointer (`data()`) di dalam *inner processing loop* setelah validasi awal lolos.
7. [ ] **Zero-Allocation Assertion**: Tambahkan unit test berbasis custom tracking memory resource untuk memverifikasi bahwa *hot path* melakukan tepat 0 kali alokasi heap.

---

### 12. Hands-on Practice

Buat dan implementasikan praktikum berikut pada direktori kerja: `hands-on/m02/`

#### Struktur Proyek
```text
hands-on/m02/
├── CMakeLists.txt
├── include/
│   ├── memory_tracker.hpp
│   └── ring_pipeline.hpp
└── src/
    └── main.cpp
```

#### File: `hands-on/m02/CMakeLists.txt`
```cmake
cmake_minimum_required(VERSION 3.25)
project(EnterpriseSTL_PMR CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_compile_options(-Wall -Wextra -Wpedantic -Werror -O3 -march=native)

include_directories(include)

add_executable(pmr_pipeline src/main.cpp)
```

#### File: `hands-on/m02/include/memory_tracker.hpp`
```cpp
#pragma once
#include <memory_resource>
#include <atomic>
#include <iostream>

class TrackingMemoryResource : public std::pmr::memory_resource {
public:
    explicit TrackingMemoryResource(std::pmr::memory_resource* upstream = std::pmr::get_default_resource())
        : upstream_(upstream), allocated_bytes_(0), allocation_count_(0) {}

    [[nodiscard]] size_t total_allocated() const noexcept { return allocated_bytes_.load(); }
    [[nodiscard]] size_t total_allocations() const noexcept { return allocation_count_.load(); }

    void reset_counters() noexcept {
        allocated_bytes_.store(0);
        allocation_count_.store(0);
    }

protected:
    void* do_allocate(size_t bytes, size_t alignment) override {
        allocated_bytes_.fetch_add(bytes, std::memory_order_relaxed);
        allocation_count_.fetch_add(1, std::memory_order_relaxed);
        return upstream_->allocate(bytes, alignment);
    }

    void do_deallocate(void* p, size_t bytes, size_t alignment) override {
        upstream_->deallocate(p, bytes, alignment);
    }

    bool do_is_equal(const std::pmr::memory_resource& other) const noexcept override {
        return this == &other;
    }

private:
    std::pmr::memory_resource* upstream_;
    std::atomic<size_t> allocated_bytes_;
    std::atomic<size_t> allocation_count_;
};
```

#### File: `hands-on/m02/src/main.cpp`
```cpp
#include "memory_tracker.hpp"
#include <vector>
#include <numeric>
#include <ranges>
#include <span>
#include <chrono>

struct Transaction {
    uint64_t id;
    double amount;
    uint32_t account_id;
};

void run_hotpath(std::span<const Transaction> txs, std::pmr::memory_resource* mem_res) {
    // Alokasi menggunakan PMR yang di-track
    std::pmr::vector<double> high_value_amounts(mem_res);
    high_value_amounts.reserve(txs.size());

    auto filter_transform = txs 
        | std::views::filter([](const Transaction& t) { return t.amount > 50000.0; })
        | std::views::transform([](const Transaction& t) { return t.amount * 1.02; }); // Biaya surcharge 2%

    for (double val : filter_transform) {
        high_value_amounts.push_back(val);
    }

    double sum = std::accumulate(high_value_amounts.begin(), high_value_amounts.end(), 0.0);
    std::cout << "Sum processed: " << sum << ", Total entries: " << high_value_amounts.size() << '\n';
}

int main() {
    TrackingMemoryResource heap_tracker;
    
    // Inisialisasi dataset pengujian
    std::vector<Transaction> input_data;
    input_data.reserve(10000);
    for (uint64_t i = 0; i < 10000; ++i) {
        input_data.push_back({i, static_cast<double>((i % 100) * 1000), static_cast<uint32_t>(i % 50)});
    }

    std::cout << "=== SCENARIO 1: Tracking Default Heap Allocations ===\n";
    heap_tracker.reset_counters();
    run_hotpath(input_data, &heap_tracker);
    std::cout << "Heap Alloc Count: " << heap_tracker.total_allocations() 
              << ", Bytes: " << heap_tracker.total_allocated() << " bytes\n\n";

    std::cout << "=== SCENARIO 2: Stack Monotonic Arena PMR ===\n";
    alignas(64) std::array<std::byte, 1024 * 1024> stack_arena; // 1 MB stack buffer
    std::pmr::monotonic_buffer_resource monotonic_res(
        stack_arena.data(), stack_arena.size(), &heap_tracker
    );

    heap_tracker.reset_counters();
    run_hotpath(input_data, &monotonic_res);
    std::cout << "Heap Allocations during Arena execution (Must be 0): " 
              << heap_tracker.total_allocations() << " bytes: " 
              << heap_tracker.total_allocated() << '\n';

    return 0;
}
```

#### Langkah Eksekusi Praktikum
```bash
cd hands-on/m02/
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
./build/pmr_pipeline
```

---

### 13. Exercise

#### Level Easy
Ubah implementasi `std::string` tradisional dalam loop parser CSV menjadi `std::string_view` dan hitung zero alokasi heap-nya dengan `TrackingMemoryResource`. Pastikan parser menangani string dengan whitespace di awal dan akhir tanpa menciptakan copy byte.

#### Level Medium
Implementasikan Circular Ring Buffer yang kompatibel dengan alokator PMR:
```cpp
template <typename T>
class PmrRingBuffer;
```
Struktur harus menerima `std::pmr::memory_resource*` pada konstruktor, tidak menggunakan *dynamic allocation* saat elemen di-*push*, dan mengekspos view berkelanjutan melalui method `std::span<const T> contiguous_slice()`.

#### Level Hard
Rancang kelas `UnsynchronizedFixedArenaResource` turunan dari `std::pmr::memory_resource` dengan karakteristik:
1. Mengelola buffer statis fixed-size tanpa alokasi upstream fallback (throw `std::bad_alloc` jika penuh).
2. Memiliki metode `.rewind()` untuk mengembalikan pointer alokasi ke titik awal tanpa destruksi elemen trivial.
3. Mendukung kalkulasi alignment manual untuk semua tipe data hingga AVX-512 (`alignas(64)`).
4. Tulis unit test untuk membuktikan alokasi $O(1)$ konsisten berada di bawah 8 nanosekon pada hardware target.

---

### 14. Challenge

**Skenario**:
Sebuah platform *High-Frequency Trading* (HFT) menerima feed order book multikast bursa L3 ITCH protocol. Gateway mengalami penurunan throughput drastis saat terjadi ledakan volatilitas pasar (*market-wide liquidation*). Profiler menunjukkan bottleneck berada pada penghancuran dan alokasi `std::map<uint64_t, OrderBookLevel>` di thread trading.

**Instruksi Penugasan**:
1. Rancang arsitektur pengganti `std::map` berbasis kontainer kontinu dengan alokasi PMR arena.
2. Buat prototipe `FlatOrderBook` yang menggunakan 2 buah flat buffer kontigu (`std::pmr::vector` yang disortir) untuk Bid dan Ask.
3. Terapkan algoritma pencarian biner menggunakan `std::ranges::lower_bound` berbasis *projection* ke `price`.
4. Buktikan melalui benchmark Google Benchmark (atau chrono high-resolution):
   - Latensi mutasi dan lookup 100 level buku order 5x lebih cepat dibanding `std::map`.
   - Terjadi **0 kali alokasi heap OS** pada interval waktu 1 menit streaming data simulasi.
   - P99.9 latensi di bawah 250 nanosekon per pembaruan buku.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. **Apa perbedaan mendasar antara `std::allocator<T>` tradisional dengan `std::pmr::polymorphic_allocator<T>`?**
   - *Jawaban*: `std::allocator<T>` mendefinisikan tipe alokator sebagai bagian dari tipe kelas kontainer pada saat kompilasi (misal: `vector<T, Alloc1>` berbeda tipe dengan `vector<T, Alloc2>`), sedangkan `std::pmr::polymorphic_allocator<T>` menggunakan polimorfisme runtime berbasis pointer ke `std::pmr::memory_resource`, sehingga tipe kontainernya seragam terlepas dari sumber memori yang digunakan.
2. **Mengapa `std::span` tidak memiliki kepemilikan atas memori yang dirujuknya?**
   - *Jawaban*: Karena `std::span` didesain murni sebagai abstraksi view (*non-owning reference*) berupa pasangan pointer dan panjang data (`[ptr, size]`) untuk menghindari overhead alokasi, salinan memori, dan overhead destruksi.
3. **Kapan pemanggilan `do_deallocate()` pada `std::pmr::monotonic_buffer_resource` membebaskan memori kembali ke sistem operasi?**
   - *Jawaban*: `monotonic_buffer_resource` mengabaikan panggilan deallokasi individu (*no-op*). Memori hanya dibebaskan ke *upstream resource* atau OS saat method `.release()` dipanggil atau saat instance destruktor monotonic resource tersebut dieksekusi.
4. **Apa kompleksitas ruang (memory overhead) dari sebuah node pada `std::list<uint64_t>` di arsitektur 64-bit?**
   - *Jawaban*: Minimal 24 bytes (pointer `prev` 8 bytes, pointer `next` 8 bytes, dan data payload 8 bytes), ditambah padding alignment allocator yang seringkali membulatkannya menjadi 32 bytes pada heap glibc ptmalloc.
5. **Bagaimana `std::views::filter` mengeksekusi predikat pengecekan elemen?**
   - *Jawaban*: Secara *lazy* (tertunda). Predikat hanya dievaluasi saat iterator view digeser (`operator++()`) dan di-dereference (`operator*()`), bukan saat pembuatan statement view pipeline.

#### Intermediate (5 Pertanyaan)
1. **Bagaimana cara mencegah `std::pmr::vector` melakukan fallback ke heap sistem saat buffer stack lokal penuh?**
   - *Jawaban*: Buat memory resource dengan menyuplai `std::pmr::null_memory_resource()` sebagai parameter `upstream`. Jika kapasitas buffer habis, alokator akan langsung melempar exception `std::bad_alloc` alih-alih mengalokasikan memori via heap OS.
2. **Jelaskan perbedaan mendasar antara `std::views::transform` dan `std::transform` algoritma klasik!**
   - *Jawaban*: `std::transform` adalah algoritma eager yang langsung mengeksekusi fungsi pada seluruh rentang elemen dan menuliskan hasilnya ke buffer tujuan (memerlukan alokasi memori tujuan). `std::views::transform` adalah adaptor yang bersifat *lazy* dan non-owning; komputasi dilakukan secara *on-the-fly* tanpa memerlukan buffer output.
3. **Mengapa `std::string_view` rentan terhadap masalah *missing null-terminator* saat berinteraksi dengan legacy C-API?**
   - *Jawaban*: Karena `std::string_view` hanya menyimpan pointer dan panjang karakter, bukan representasi null-terminated string (`\0`). Substring view tidak menambahkan `\0` pada akhir range, sehingga mem-passing `view.data()` ke fungsi C API seperti `strcmp` atau `printf("%s")` dapat membaca memori tak berizin (*buffer over-read*).
4. **Apa fungsi dari `std::pmr::unsynchronized_pool_resource` dan bagaimana performanya dibanding monotonic buffer?**
   - *Jawaban*: Kelas ini mengelola memori menggunakan sekumpulan *pools* dengan fixed chunk sizes untuk mengeliminasi fragmentasi akibat alokasi dan dealokasi objek berukuran bervariasi. Performanya sedikit lebih lambat dibanding monotonic buffer karena ada lookup chunk pool, namun mampu me-recycle memori yang dideallokasi dalam thread yang sama tanpa overhead penguncian thread-safe.
5. **Apa keunggulan arsitektural `std::flat_map` dibandingkan `std::map` tradisional pada iterasi berulang?**
   - *Jawaban*: `std::flat_map` menyimpan data dalam kontainer kontinu (secara default dua `std::vector`, satu untuk keys dan satu untuk values). Hal ini memberikan lokalitas cache optimal, memungkinkan CPU hardware prefetcher bekerja efisien, dan mengurangi ukuran footprint memori karena tidak adanya overhead pointer Red-Black Tree.

#### Kasus Produksi Enterprise (3 Skenario)
1. **Skenario 1**: Sebuah microservice perbankan mengalami degradasi performa berkala setiap kali throughput mencapai 50.000 req/detik. Profiling menunjukkan 45% CPU cycles dihabiskan di dalam kernel space `sys_brk` dan `pthread_mutex_lock` di dalam `malloc_consolidate`. Bagaimana Anda merancang ulang arsitektur memori microservice ini menggunakan PMR?
   - *Solusi Analitis*: Ganti penggunaan alokator global heap dengan arsitektur pool per-thread. Sediakan `thread_local std::pmr::unsynchronized_pool_resource` yang diinisialisasi di awal thread worker dengan blok buffer besar yang dipetakan via `mmap(MAP_ANONYMOUS | MAP_PRIVATE)`. Untuk penanganan request individual, gunakan `std::pmr::monotonic_buffer_resource` berbasis stack frame (misal 64 KiB) dengan fallback ke thread-local pool tadi. Setiap akhir request, panggil `.release()` pada monotonic buffer. Ini mengeliminasi 100% *system call* `sys_brk` dan *lock contention* antar thread worker.
2. **Skenario 2**: Sebuah modul deep-packet inspection (DPI) menggunakan pipeline `std::ranges` untuk menyaring frame jaringan. Saat beban puncak, terjadi lonjakan latensi yang tidak konsisten. Tim mendapati bahwa pipeline view menyertakan beberapa chaining bertingkat: `views::filter | views::transform | views::filter`. Mengapa chaining view ini bisa memicu latensi tinggi pada skenario tertentu dan bagaimana solusinya?
   - *Solusi Analitis*: `views::filter` tidak memiliki kompleksitas iterasi $O(1)$ yang stabil karena iterator harus mencari elemen berikutnya yang memenuhi predikat; chaining beberapa filter dapat memicu *branch misprediction cascades* pada level CPU pipeline instruction. Selain itu, iterator caching pada filter view dapat memicu overhead komputasi ulang jika iterator disalin. Solusinya: Gabungkan beberapa predikat filter menjadi satu lambda tunggal (`views::filter([](auto&& x){ return pred1(x) && pred2(x); })`) dan lakukan *loop unrolling* manual menggunakan `std::span` jika pipeline berada pada *innermost ultra-low-latency core*.
3. **Skenario 3**: Sistem telemetry trading memproses order status event dan mengirimkannya ke ring buffer. Developer menggunakan `std::variant<OrderAck, OrderReject, OrderFill>` yang disimpan di dalam `std::pmr::vector`. Saat diuji, memory throughput tidak mencapai batas bus bandwidth. Pemeriksaan struct menunjukkan `sizeof(OrderReject)` adalah 256 bytes (karena field teks alasan error), sementara `OrderAck` hanya 16 bytes. Apa masalah layout memori di sini dan bagaimana arsitektur STL diperbaiki?
   - *Solusi Analitis*: Ukuran `std::variant` ditentukan oleh ukuran elemen terbesarnya ditambah alignment dan discriminator. Akibatnya, setiap elemen vector berukuran $\ge 256$ bytes, menyebabkan *cache pollution* yang parah ketika sebagian besar pesan adalah `OrderAck` (efisiensi payload hanya ~6%). Solusi: Normalisasi layout data. Simpan detail string teks `OrderReject` di luar ring buffer (misal di arena alokator terpisah) dan jadikan field reject di dalam variant hanya berisi pointer/view atau error code integer (16 bytes). Alternatif lain: Pisahkan antrean menjadi struktur data terpisah (*Struct of Arrays* daripada *Array of Structs*) sehingga pemrosesan event mayoritas (`OrderAck`) berjalan contiguous pada cache-line padat.

---

### 16. Summary

1. **Evolusi Alokasi Modern**: `std::pmr` mentransformasi manajemen memori C++ dari keputusan statis kompilasi menjadi strategi operasional dinamis di level runtime, memisahkan logika algoritma dari alokator fisik.
2. **Mekanisme Monotonic Arena**: Menggunakan arena linier stack-backed atau mmap-backed (`monotonic_buffer_resource`) memangkas biaya alokasi dinamis menjadi hanya beberapa siklus register CPU ($O(1)$) dan membebaskan memori secara instan.
3. **Infrastruktur Zero-Copy**: Penggunaan `std::span` dan `std::string_view` secara tepat menghapus duplikasi buffer di antarmuka sistem; namun, manajemen *lifetime ownership* data dasar menjadi tanggung jawab mutlak engineer.
4. **Hardware-Conscious Data Layout**: Menghindari kontainer node-based (`std::list`, `std::map`) untuk alur pemrosesan data volume tinggi adalah mandat arsitektur modern demi menghindari *cache misses* dan mengeksploitasi fitur *CPU instruction prefetching*.
5. **Keandalan Deterministik**: Kombinasi C++20 Ranges untuk pemrosesan deklaratif *lazy* dan C++23 `std::expected` untuk error handling tanpa pengecualian (*no-throw guarantee*) memberikan performa puncak yang stabil, terprediksi, dan siap untuk lingkungan produksi skala *enterprise*.