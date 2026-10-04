# SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `CPP-ENG-B10M01`
* **Jalur Pembelajaran**: *High-Performance & Low-Latency Enterprise Systems Engineering*
* **Kategori**: `02-Programming-Languages`
* **Mata Pelajaran**: Modern C++ (C++20/C++23)
* **Tingkat Kemahiran**: Advanced / Enterprise Architect
* **Prasyarat**:
  * Penguasaan mendalam memori C++ (pointer, referensi, *lifetimes*, *move semantics*, RAII).
  * Pemahaman tentang model konkurensi C++ (*multithreading*, `std::atomic`, *memory fences*, *memory orders*).
  * Pemahaman arsitektur perangkat keras modern (x86_64/ARM cache hierarchy L1/L2/L3, *cache line*, *branch predictor*).
  * Familiaritas dengan OOP, generic programming (*templates*, C++20 *concepts*), dan desain pola perangkat lunak (*design patterns*).
* **Alat & Lingkungan Pengembangan**:
  * Kompiler: GCC 13+ atau Clang 16+ (dukungan penuh C++20)
  * Build System: CMake 3.25+
  * Diagnostic Tools: Valgrind (Memcheck, Massif), LLVM Sanitizers (ASan, TSan, UBSan), Perf, GDB.
  * Standar Bahasa: `-std=c++20` atau `-std=c++23`

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik memiliki kemampuan untuk:

1. **Mendesain Arsitektur Enterprise Berkinerja Tinggi (Architectural Mastery)**: Mengintegrasikan prinsip *Hexagonal Architecture (Ports & Adapters)* dan *Clean Architecture* ke dalam ekosistem C++ dengan mempertahankan karakteristik zero-cost abstraction tanpa membebani *hot-path* oleh dynamic dispatch.
2. **Menguasai Mekanika Zero-Allocation Hot Path (Memory Determinism)**: Mengeliminasi alokasi dinamis (*runtime heap allocation*) pada alur eksekusi kritis menggunakan *Arena Allocators*, *Fixed-size Ring Buffers*, dan *Static Object Pools*.
3. **Mengimplementasikan Pola Konkurensi Lock-Free (Concurrency Engineering)**: Membangun struktur data bebas-kunci (*lock-free*) SPSC (*Single-Producer Single-Consumer*) berbasis instruksi atomik dengan *memory ordering* eksplisit (`acquire-release semantics`) untuk throughput jutaan pesan per detik.
4. **Mencegah Masalah Mikroarsitektur Hardware (Mechanical Sympathy)**: Memitigasi *false sharing* menggunakan padding eksplisit berbasis `std::hardware_destructive_interference_size`, memaksimalkan *cache locality*, dan mereduksi *instruction cache misses* melalui static polymorphism (CRTP).
5. **Mengintegrasikan Sistem End-to-End (Capstone Execution)**: Menghasilkan implementasi teruji produksi dari sistem pengolahan order finansial (*matching engine/event processor*) yang modular, dapat diobservasi, berlatensi rendah (< 1 mikrosekon p99), dan *thread-safe*.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Academic C++ vs Enterprise Low-Latency C++

Dalam C++ akademik atau aplikasi korporat konvensional (misal Java/C# yang ditranslasi ke C++), fokus utama umumnya adalah abstraksi berlapis, hierarki kelas polimorfik murni (`virtual functions`), penggunaan pointer cerdas universal (`std::shared_ptr`), dan alokasi dinamis bebas via `std::make_shared` atau `new`. 

Pada skala **Enterprise Low-Latency C++**, mental model tersebut bergeser secara fundamental:

```
[ Academic / Conventional Model ]
Business Logic -> Polymorphic Abstraction (vptr/vtable) -> Dynamic Heap Allocation -> OS Paging/GC/Locking

[ Enterprise Mechanical Sympathy Model ]
Hardware Topology (NUMA/Caches) -> Cache Line Packing (64B) -> Zero-Allocation Core -> Static Dispatch (CRTP/Concepts) -> Predictable Assembly
```

### Fondasi Mental Model:
1. **Mechanical Sympathy**: Tulislah kode yang selaras dengan arsitektur CPU dan memori. Memori utama (DRAM) adalah perangkat lambat (50-100 ns); CPU L1 cache sangat cepat (1 ns). Memori harus diproses secara berurutan (*contiguous memory arrays*) untuk memaksimalkan *hardware prefetcher*.
2. **Determinisme Latensi Mengalahkan Rata-rata Throughput**: Sistem enterprise finansial dan misi kritis tidak hanya menuntut kecepatan rata-rata tinggi, melainkan batas variansi (*tail latency*) terkontrol: p99 dan p99.99 harus seketat p50. Jauhi *locks*, *mutexes*, *system calls*, dan *unbounded dynamic memory allocations* pada jalur kritis.
3. **Pemisahan Jalur Komputasi (Hot-Path vs Cold-Path)**:
   * **Hot-Path**: Dilarang melakukan I/O, alokasi heap (`malloc`/`free`), *context switch*, pengecualian (`exceptions`), dan *dynamic dispatch* tak terprediksi.
   * **Cold-Path**: Tempat manajemen konfigurasi, setup koneksi, reporting, deserialisasi lambat, penanganan error fatal, dan alokasi memori awal (*pre-allocation*).

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Arsitektur aplikasi enterprise C++ modern berkinerja tinggi mengawinkan kebersihan modular dari **Hexagonal Architecture** dengan kecepatan ekstrem dari **LMAX-style Ring Buffer Architecture**.

### Diagram Tingkat Tinggi: Hexagonal + Lock-Free Event Pipeline

```
           INBOUND ADAPTERS (Cold/Warm Path)
     +------------------------------------------+
     | TCP/IP Network Gateway (Epoll/io_uring)  |
     +------------------------------------------+
                          |
                          v  (Zero-Copy Parse)
     +------------------------------------------+
     |        Inbound Normalizer Port           |
     +------------------------------------------+
                          |
                          v  (Enqueue: Non-blocking)
====================================================== [MEMORY BOUNDARY]
          LOCK-FREE SPSC RING BUFFER (Hot-Path)
          (Zero Allocations, Contiguous Array)
====================================================== [MEMORY BOUNDARY]
                          |
                          v  (Batch Dequeue / Spinlock-free)
     +------------------------------------------+
     |       CORE DOMAIN ENGINE (Hot Path)      |
     |  - Pinned to Isolated CPU Core          |
     |  - Custom Arena Allocator Lifecycle      |
     |  - Matching / Rule Engine (CRTP Models)  |
     |  - Zero System Calls, Zero Dynamic Heap  |
     +------------------------------------------+
             |                              |
             v                              v
     (Direct Emit)                  (Direct Emit)
===========================    ===========================
  OUTBOUND SPSC JOURNAL RING     OUTBOUND SPSC CLIENT RING
===========================    ===========================
             |                              |
             v                              v
   +--------------------+        +--------------------+
   | Journaler Adapter  |        | TCP Publisher Port |
   | (Asynchronous I/O) |        | (Direct Network)   |
   +--------------------+        +--------------------+
             |                              |
             v                              v
     NVMe Raw Ledger                 Clients / Consumers
```

### Diagram Siklus Hidup Alokasi Memori: Arena/Linear Allocator

```
+-----------------------------------------------------------------------+
| Single Pre-allocated Buffer (Misal: 64 MegaBytes diinisialisasi saat Boot)|
+-----------------------------------------------------------------------+
  ^                     ^                                       ^
  |                     |                                       |
  [Offset A]            [Offset B]                              [Capacity Limit]
  (Frame 1: 0..4KB)     (Frame 2: 4KB..12KB)                    (Reset per putaran)
  * Alokasi = Geser pointer (Offset += bytes) -> O(1) deterministik
  * Dealokasi = Reset pointer ke awal (Offset = 0) -> Tanpa fragmentasi
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur Cache Line & False Sharing Prevention
Pada arsitektur modern (x86_64, ARM64), data ditransfer antara L3/L2/L1 cache dan core CPU dalam unit **Cache Line** berukuran 64 byte. 

Jika variabel atomik `head` (yang ditulis oleh Core A) dan `tail` (yang ditulis oleh Core B) berada dalam satu cache line 64-byte yang sama, protokol koherensi cache (misal: MESI/MOESI) akan memaksa invalidasi cache line bolak-balik antar core, mengakibatkan **Cache-Bouncing** dan melumpuhkan latensi.

```
Pola Salah (False Sharing):
+------------------------------------+------------------------------------+
| Variable: Head (Core A menulis)    | Variable: Tail (Core B menulis)    |  <-- 1 Cache Line (64 Bytes)
+------------------------------------+------------------------------------+
* Result: Terjadi perebutan hak kepemilikan cache line antar core terus-menerus.

Pola Benar (Explicit Alignment):
+-------------------------------------------------------------------------+
| Variable: Head (Core A) + alignas(hardware_destructive_interference_size)|  <-- Cache Line 1 (64 Bytes)
+-------------------------------------------------------------------------+
+-------------------------------------------------------------------------+
| Variable: Tail (Core B) + alignas(hardware_destructive_interference_size)|  <-- Cache Line 2 (64 Bytes)
+-------------------------------------------------------------------------+
```

### 2. Atomics & Memory Ordering Semantics
Penggunaan atomik tanpa pengaturan eksplisit akan menggunakan `std::memory_order_seq_cst` secara default. Hal ini menghasilkan instruksi serialisasi perangkat keras yang mahal (misalnya, `MFENCE` atau `LOCK CMPXCHG` pada x86). 
Untuk antrean SPSC (Single-Producer Single-Consumer):
* **Producer write index (`tail`)**: Menggunakan `std::memory_order_release` untuk memastikan semua penulisan payload transaksi sebelum pembaruan index telah selesai dan terbaca oleh thread pembaca.
* **Consumer read index (`head`)**: Menggunakan `std::memory_order_acquire` untuk menjamin operasi pembacaan payload transaksi di belakang index tersebut tidak dieksekusi sebelum index baru tervalidasi.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Clean Architecture Berbasis Zero-Cost Abstraction
Clean Architecture menuntut dependensi mengalir ke dalam: Domain tidak boleh bergantung pada Inbound/Outbound adapters. Pada sistem konvensional, dependensi dibalikkan menggunakan Interface polimorfik dinamis (`virtual` function table / `vtable`).

Namun, pointer vtable (`vptr`) memiliki konsekuensi:
1. Dereferensi ganda: membaca lokasi vtable, lalu memanggil fungsi pointer.
2. Pencegahan *inlining* oleh kompiler: Optimasi analisis statis menjadi terbatas.
3. Potensi Branch Target Buffer (BTB) miss pada CPU jika implementasi berganti dinamis.

Sebagai solusinya, kita memanfaatkan **C++20 Concepts** dan **CRTP (Curiously Recurring Template Pattern)** untuk menghasilkan polimorfisme statis (*Static Polymorphism*):

```cpp
// Static Interface Definition
template <typename T>
concept OrderProcessor = requires(T processor, const Order& order) {
    { processor.on_order(order) } noexcept -> std::same_as<void>;
};
```

Kompiler membongkar tipe konkret pada *compile-time*. Pemanggilan kode langsung di-*inline* menjadi instruksi assembly monolitik tanpa overhead eksekusi runtime sama sekali.

### Model Memori SPSC Lock-Free Ring Buffer
Kunci dari performa buffer melingkar berkapasitas daya-dua (*power-of-two capacity*) $N = 2^k$:
Operasi modulo aritmetika:
$$\text{Index} = \text{Sequence} \pmod N$$
dapat dioptimalkan menjadi operasi bitwise AND yang tereksekusi dalam 1 cycle CPU:
$$\text{Index} = \text{Sequence} \ \& \ (N - 1)$$

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi fondasi arsitektur enterprise: **Lock-Free Cache-Aligned Single-Producer Single-Consumer (SPSC) Queue** yang menggunakan memori yang sudah dialokasikan di awal (*pre-allocated*), bebas alokasi dinamis pada operasi kritis, serta terlindungi dari *false sharing*.

Simpan sebagai `SpscRingBuffer.hpp`:

```cpp
#pragma once

#include <atomic>
#include <cstddef>
#include <new>
#include <optional>
#include <span>
#include <type_traits>
#include <utility>
#include <vector>

#if defined(__cpp_lib_hardware_interference_size)
    using std::hardware_destructive_interference_size;
#else
    constexpr size_t hardware_destructive_interference_size = 64;
#endif

template <typename T, size_t Capacity>
class SpscRingBuffer {
    static_assert((Capacity & (Capacity - 1)) == 0, "Kapasitas harus berupa perpangkatan dua (power-of-two).");
    static_assert(std::is_nothrow_move_assignable_v<T> || std::is_nothrow_copy_assignable_v<T>,
                  "Elemen T harus noexcept assignable.");

public:
    SpscRingBuffer() : storage_(Capacity) {}

    ~SpscRingBuffer() = default;
    SpscRingBuffer(const SpscRingBuffer&) = delete;
    SpscRingBuffer& operator=(const SpscRingBuffer&) = delete;
    SpscRingBuffer(SpscRingBuffer&&) = delete;
    SpscRingBuffer& operator=(SpscRingBuffer&&) = delete;

    template <typename... Args>
    bool emplace(Args&&... args) noexcept {
        const size_t current_tail = tail_.load(std::memory_order_relaxed);
        const size_t current_head = head_cached_;

        if ((current_tail - current_head) >= Capacity) {
            // Buffer penuh, perbarui cache head dari variabel atomik consumer
            head_cached_ = head_.load(std::memory_order_acquire);
            if ((current_tail - head_cached_) >= Capacity) {
                return false; // Buffer benar-benar penuh
            }
        }

        // Simpan objek pada slot
        storage_[current_tail & BufferMask] = T(std::forward<Args>(args)...);

        // Publikasikan tail ke consumer dengan release semantics
        tail_.store(current_tail + 1, std::memory_order_release);
        return true;
    }

    bool pop(T& destination) noexcept {
        const size_t current_head = head_.load(std::memory_order_relaxed);
        const size_t current_tail = tail_cached_;

        if (current_head == current_tail) {
            // Buffer kosong, perbarui cache tail dari variabel atomik producer
            tail_cached_ = tail_.load(std::memory_order_acquire);
            if (current_head == tail_cached_) {
                return false; // Buffer benar-benar kosong
            }
        }

        destination = std::move(storage_[current_head & BufferMask]);

        // Publikasikan head ke producer dengan release semantics
        head_.store(current_head + 1, std::memory_order_release);
        return true;
    }

    [[nodiscard]] size_t size() const noexcept {
        const size_t head = head_.load(std::memory_order_relaxed);
        const size_t tail = tail_.load(std::memory_order_relaxed);
        return (tail >= head) ? (tail - head) : 0;
    }

    [[nodiscard]] bool empty() const noexcept {
        return head_.load(std::memory_order_relaxed) == tail_.load(std::memory_order_relaxed);
    }

private:
    static constexpr size_t BufferMask = Capacity - 1;

    // Alokasi storage internal
    std::vector<T> storage_;

    // Variabel tulis Producer (diisolasi ke Cache Line terpisah)
    alignas(hardware_destructive_interference_size) std::atomic<size_t> tail_{0};
    size_t head_cached_{0};

    // Variabel tulis Consumer (diisolasi ke Cache Line terpisah)
    alignas(hardware_destructive_interference_size) std::atomic<size_t> head_{0};
    size_t tail_cached_{0};
};
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanika internal implementasi `SpscRingBuffer.hpp`:

* **Baris 11-15**: Penentuan batasan ukuran cache line arsitektur target. Menggunakan `std::hardware_destructive_interference_size` (standar C++17 ke atas) untuk memastikan isolasi antar variabel atomik pada blok memori fisik yang independen.
* **Baris 18**: Kompilasi statis `static_assert((Capacity & (Capacity - 1)) == 0)`. Validasi compile-time bahwa ukuran adalah kelipatan perpangkatan dua (misal: 1024, 2048, 65536). Ini memungkinkan substitusi operator modulo `%` yang mahal menjadi bitwise `& BufferMask`.
* **Baris 24-28**: Menonaktifkan *Copy* dan *Move constructors* serta *Assignment operators*. Queue ini memiliki kepemilikan eksklusif atas jalurnya dan tidak boleh disalin atau dipindahkan demi integritas pointer thread.
* **Baris 32**: `tail_.load(std::memory_order_relaxed)`. Producer adalah satu-satunya entitas yang menulis ke `tail_`. Oleh karena itu, Producer dapat membaca nilai `tail_` miliknya sendiri tanpa sinkronisasi hardware tambahan (`relaxed`).
* **Baris 35-40**: Pola **Cached Indices Optimization**. Thread Producer menyimpan salinan lokal nilai index milik consumer (`head_cached_`). Producer hanya menyinkronkan nilai `head_` riil dari variabel atomik consumer saat kapasitas lokal terdeteksi penuh. Ini mengeliminasi pembacaan memori lintas-core (inter-core cache snooping) pada sebagian besar operasi penulisan.
* **Baris 43**: Penulisan payload ke dalam elemen array `storage_[current_tail & BufferMask]`.
* **Baris 46**: `tail_.store(current_tail + 1, std::memory_order_release)`. Memory order `release` bertindak sebagai dinding pembatas (*memory barrier*). Instruksi ini memastikan perakitan hardware menyelesaikan penulisan objek ke memory cell array sebelum index `tail_` dinaikkan dan terlihat oleh Consumer.
* **Baris 50-67**: Operasi `pop` oleh Consumer mengimplementasikan mekanisme cermin: Consumer membaca index `head_` miliknya dengan `memory_order_relaxed`, mengecek ketersediaan data via `tail_cached_`, mengambil objek menggunakan move semantic `std::move`, dan memperbarui `head_` menggunakan `memory_order_release`.
* **Baris 79-84**: Padding eksplisit dengan `alignas(hardware_destructive_interference_size)` memisahkan field milik domain Producer (`tail_`, `head_cached_`) dan domain Consumer (`head_`, `tail_cached_`) ke dalam blok cache 64-byte yang berbeda secara absolut.

---

# SEKSI 09 — STUDI KASUS NYATA

### Konteks: Ultra-Low Latency Order Ingestion & Matching Gateway
Sebuah institusi pertukaran aset keuangan memproses rata-rata 5.000.000 transaksi limit order per detik (5M ops/sec).
Permasalahan yang dihadapi sistem lama (arsitektur monolitik berbasis antrean `std::mutex` + `std::queue` dan hierarki pewarisan virtual):
1. **Latency Spikes**: p99 menyentuh 150 mikrosekon akibat perebutan mutex OS dan page faults dari dynamic memory allocations (`new Order`).
2. **Cache Thrashing**: Alokasi `Order` yang terpencar di heap mengakibatkan L1/L2 data cache misses mencapai 38%.

### Sasaran Arsitektur Baru:
* Desain Zero-Allocation: Tidak ada alokasi heap saat *hot path* pemrosesan order. Seluruh order diproses melalui fixed memory footprint.
* Mengisolasi Core Logika Domain melalui pemisahan thread producer (Inbound Parser) dan consumer (Matching Core Engine) yang dihubungkan melalui *Zero-Copy Ring Buffer*.
* Latensi tail p99.99 terpangkas di bawah level < 1.5 mikrosekon.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah arsitektur produksi lengkap yang menyatukan Inbound Adapter, Lock-Free Ring Buffer, Domain Core Engine, dan Outbound Persistence/Journaling Port dalam satu unit C++20 yang runnable dan modular.

Simpan sebagai `EnterpriseOrderProcessor.cpp`:

```cpp
#include <iostream>
#include <string_view>
#include <chrono>
#include <thread>
#include <atomic>
#include <array>
#include <vector>
#include <cstdint>
#include <memory>
#include <span>

#include "SpscRingBuffer.hpp"

// ==========================================
// 1. DOMAIN MODELS (Tightly Packed Structs)
// ==========================================
enum class Side : uint8_t { Buy = 0, Sell = 1 };
enum class OrderType : uint8_t { Limit = 0, Market = 1 };

struct alignas(32) OrderCommand {
    uint64_t order_id{0};
    uint64_t timestamp_ns{0};
    uint32_t instrument_id{0};
    uint32_t quantity{0};
    double   price{0.0};
    Side     side{Side::Buy};
    OrderType type{OrderType::Limit};
    char     padding[6]; // Explicit padding to reach 32 bytes exact
};
static_assert(sizeof(OrderCommand) == 32, "OrderCommand must be exactly 32 bytes.");

struct ExecutionReport {
    uint64_t order_id{0};
    uint64_t match_timestamp_ns{0};
    uint32_t executed_quantity{0};
    double   execution_price{0.0};
    bool     is_filled{false};
};

// ==========================================
// 2. PORTS (C++20 Concepts Definition)
// ==========================================
template <typename T>
concept ExecutionListener = requires(T listener, const ExecutionReport& report) {
    { listener.on_execution(report) } noexcept -> std::same_as<void>;
};

// ==========================================
// 3. ADAPTERS (Outbound Fast Journaler)
// ==========================================
class FastAuditJournaler {
public:
    void on_execution(const ExecutionReport& report) noexcept {
        // Pada skenario produksi nyata: Tulis ke Lock-Free Memory-Mapped File (mmap)
        // Di sini kita catat mutasi tanpa interupsi stream lambat
        sink_executions_count_++;
    }

    [[nodiscard]] size_t total_recorded() const noexcept {
        return sink_executions_count_;
    }

private:
    size_t sink_executions_count_{0};
};
static_assert(ExecutionListener<FastAuditJournaler>);

// ==========================================
// 4. CORE ENGINE (Clean Architecture Domain)
// ==========================================
template <ExecutionListener ListenerAdapter>
class MatchingEngineCore {
public:
    explicit MatchingEngineCore(ListenerAdapter& listener) noexcept
        : listener_(listener) {}

    // Deterministic Hot-path Execution
    void process_command(const OrderCommand& cmd) noexcept {
        // Simulasi internal matching logic
        const uint64_t now = std::chrono::steady_clock::now().time_since_epoch().count();
        
        ExecutionReport report{
            .order_id = cmd.order_id,
            .match_timestamp_ns = now,
            .executed_quantity = cmd.quantity,
            .execution_price = cmd.price,
            .is_filled = true
        };

        // Static dispatch via concept/templates -> Zero runtime overhead
        listener_.on_execution(report);
        processed_count_++;
    }

    [[nodiscard]] size_t get_processed_count() const noexcept {
        return processed_count_;
    }

private:
    ListenerAdapter& listener_;
    size_t processed_count_{0};
};

// ==========================================
// 5. APPLICATION ORCHESTRATOR & BENCHMARK
// ==========================================
constexpr size_t RING_BUFFER_CAPACITY = 1048576; // 2^20 entries (~32 MB preallocated)
constexpr size_t TOTAL_MESSAGES = 2000000;

int main() {
    std::cout << "[Enterprise Capstone] Booting Low-Latency Core...\n";

    // Setup Shared IPC / In-Memory Inter-thread Ring Buffer
    auto inbound_ring_buffer = std::make_unique<SpscRingBuffer<OrderCommand, RING_BUFFER_CAPACITY>>();
    std::atomic<bool> is_running{true};

    FastAuditJournaler journaler_adapter;
    MatchingEngineCore<FastAuditJournaler> engine(journaler_adapter);

    // THREAD 1: Consumer (Domain Engine Core pinned to logical processing)
    std::thread consumer_thread([&]() {
        OrderCommand cmd;
        size_t consumed = 0;

        while (is_running.load(std::memory_order_relaxed) || !inbound_ring_buffer->empty()) {
            if (inbound_ring_buffer->pop(cmd)) {
                engine.process_command(cmd);
                consumed++;
            } else {
                // Yield thread cycle briefly jika buffer kosong
                #if defined(__x86_64__) || defined(_M_X64)
                __builtin_ia32_pause();
                #elif defined(__aarch64__)
                asm volatile("yield");
                #endif
            }
        }
    });

    // THREAD 2: Producer (Network/Gateway Inbound Adapter simulator)
    std::cout << "[Producer] Emitting " << TOTAL_MESSAGES << " structured orders...\n";
    const auto start_time = std::chrono::high_resolution_clock::now();

    for (uint64_t i = 1; i <= TOTAL_MESSAGES; ++i) {
        OrderCommand cmd{
            .order_id = i,
            .timestamp_ns = static_cast<uint64_t>(i * 100),
            .instrument_id = 42,
            .quantity = 10,
            .price = 1500.50,
            .side = Side::Buy,
            .type = OrderType::Limit,
            .padding = {0}
        };

        // Busy spin jika buffer sementara penuh
        while (!inbound_ring_buffer->emplace(cmd)) {
            #if defined(__x86_64__) || defined(_M_X64)
            __builtin_ia32_pause();
            #elif defined(__aarch64__)
            asm volatile("yield");
            #endif
        }
    }

    // Tunggu data dikuras oleh consumer
    while (!inbound_ring_buffer->empty()) {
        std::this_thread::yield();
    }

    is_running.store(false, std::memory_order_release);
    consumer_thread.join();

    const auto end_time = std::chrono::high_resolution_clock::now();
    const auto duration_us = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time).count();
    const double throughput_ops = (static_cast<double>(TOTAL_MESSAGES) / static_cast<double>(duration_us)) * 1000000.0;

    std::cout << "====================================================\n";
    std::cout << "Execution Completed Successfully.\n";
    std::cout << "Total Processed : " << engine.get_processed_count() << " orders\n";
    std::cout << "Journal Recorded: " << journaler_adapter.total_recorded() << " executions\n";
    std::cout << "Elapsed Time    : " << duration_us << " microseconds\n";
    std::cout << "Throughput      : " << static_cast<uint64_t>(throughput_ops) << " ops/sec\n";
    std::cout << "Average Latency : " << (static_cast<double>(duration_us) * 1000.0 / TOTAL_MESSAGES) << " ns/op\n";
    std::cout << "====================================================\n";

    return 0;
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Dimensi Arsitektural | Dynamic OOP Approach (Java/Classic C++) | Static Clean Architecture (Modern C++ Capstone) | Analisis Trade-Off & Justifikasi Rekayasa |
| :--- | :--- | :--- | :--- |
| **Abstraksi Dependensi** | Polymorphic Interfaces via `virtual` table | C++20 Concepts & Static Dispatch (Templates) | Virtual functions mengaburkan target instruksi bagi CPU branch predictor. Konsep static dispatch menuntut waktu kompilasi lebih lama, tetapi menghasilkan eksekusi direct call 0 ns. |
| **Penyimpanan Data** | `std::queue<std::unique_ptr<T>>` | Lock-Free Pre-allocated `SpscRingBuffer` | Dynamic Queue mengalokasikan node terpisah di OS heap secara terus-menerus, memicu heap fragmentation. Ring buffer deterministik mengisolasi memori statis ke sequential cache blocks. |
| **Sinkronisasi Thread** | Mutex & Condition Variable (`std::unique_lock`) | Atomic Variables (`Acquire-Release Semantics`) | Mutex memerlukan intervensi kernel OS (sleep/wakeup context switch ~1-5 µs). Atomics diselesaikan langsung pada sirkuit bus level hardware (~10-40 ns). |
| **Kemudahan Debugging** | Mudah ditrace via stacktrace debugger standar | Memerlukan pemahaman perakitan & memory fences | Pendekatan atomik mempersulit pelacakan race condition tanpa tool analisis formal seperti ThreadSanitizer (TSan). |

---

# SEKSI 12 — EDGE CASES & PITFALLS

1. **Integer Overflow pada Sequence Index Ring Buffer**:
   * *Bahaya*: Jika `tail_` dan `head_` bertipe data `uint32_t`, variabel akan wrap-around kembali ke `0` setelah 4,29 miliar operasi.
   * *Solusi*: Gunakan variabel unsigned 64-bit (`uint64_t`). Pada kecepatan proses 10 juta event per detik, `uint64_t` membutuhkan waktu lebih dari 58.000 tahun sebelum mencapai titik limit overflow.
2. **Buffer Saturated Spikiness**:
   * *Bahaya*: Producer yang menghasilkan pesan jauh melampaui kemampuan serap consumer akan membuat ring buffer jenuh. Jika producer memblokir dengan *busy-wait*, thread producer akan membakar 100% core CPU dan berisiko mengalami *starvation* di level sistem operasi.
   * *Mitigasi*: Sisipkan instruksi low-overhead hardware pause (seperti `_mm_pause()` pada arsitektur x86) di dalam loop pengecekan kondisi.
3. **ABA Problem pada Struktur Data Lock-Free Berbasis Pointer**:
   * *Catatan*: Pola SPSC Index Ring Buffer yang digunakan di atas kebal terhadap ABA problem karena indeks bertambah secara monotonik (`monotonically increasing`) tanpa melakukan pertukaran alamat pointer mentah via CAS (`compare_and_swap`).

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Defaulting to `memory_order_seq_cst`
* **Kesalahan**: Menggunakan `std::atomic<size_t>` secara langsung tanpa menyertakan argumen memory order pada fungsi `load()` dan `store()`.
* **Dampak**: Kompiler menyisipkan instruksi memory fence hardware lengkap (misal `MFENCE` pada arsitektur Intel x86) yang memaksa invalidasi pipeline eksekusi instruksi CPU.
* **Solusi**: Tentukan secara eksplisit `std::memory_order_acquire`, `std::memory_order_release`, atau `std::memory_order_relaxed`.

### 2. Mengabaikan Alignment Data Struct
* **Kesalahan**: Mendefinisikan struct transaksi dengan urutan tipe data acak:
  ```cpp
  struct BadOrder {
      char c;       // 1 byte
      double price; // 8 bytes (terdapat padding tersembunyi 7 bytes)
      int id;       // 4 bytes
  }; // Total 24 bytes, memicu pemborosan cache line footprint.
  ```
* **Solusi**: Susun field variabel dari ukuran terbesar ke ukuran terkecil atau tentukan batas ukuran secara terstruktur via `alignas(N)` dan verifikasi ukurannya menggunakan `static_assert(sizeof(...) == TargetSize)`.

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Prinsip "Zero-Allocation in Processing"**: Larang pemanggilan `malloc`, `free`, `new`, `delete`, serta metode mutasi kontainer dinamis (seperti `std::vector::push_back` yang melebihi batas reservasi) setelah fase *initialization/bootstrapping* sistem selesai.
2. **CPU Core Affinity (Thread Pinning)**: Lakukan isolasi core CPU runtime pada level sistem operasi menggunakan `pthread_setaffinity_np` (Linux). Hal ini mencegah thread OS berpindah-pindah antar core (*core migration*) yang dapat memicu pembongkaran konteks cache L1/L2 secara mendadak.
3. **Optimasi Kompiler Tingkat Tinggi**:
   * Kompilasi sistem selalu menyertakan flag: `-O3 -march=native -fno-omit-frame-pointer`.
   * Aktifkan Link-Time Optimization (LTO) via flag `-flto` untuk memungkinkan inlining fungsi melintasi unit translasi `.cpp` yang berbeda.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Hardware Instruction Pre-fetching & Loop Unrolling
Ketika memproses batch perintah beruntun dari ring buffer, CPU prefetcher dapat dipandu secara manual untuk memuat blok memori sebelum giliran instruksi dieksekusi:

```cpp
void prefetch_memory(const void* ptr) noexcept {
    #if defined(__GNUC__) || defined(__clang__)
    __builtin_prefetch(ptr, 0 /* 0 = Read */, 3 /* 3 = High Temporal Locality */);
    #endif
}
```

### Eliminasi Cabang Condisional Tak Terduga via C++20 Attributes
Gunakan atribut `[[likely]]` dan `[[unlikely]]` untuk memandu penataan blok assembly kompiler:

```cpp
if (ring_buffer.pop(cmd)) [[likely]] {
    engine.process(cmd);
} else [[unlikely]] {
    // Jalur cold-path saat buffer kosong
    handle_idle_cycles();
}
```

---

# SEKSI 16 — KEAMANAN & HARDENING

1. **Sanitizer Harnessing dalam Pipeline CI/CD**:
   * Setiap commit kode enterprise wajib lulus uji kompilasi trio Clang/GCC Sanitizers:
     * **AddressSanitizer (ASan)**: Memvalidasi ketiadaan *buffer overflow* dan *out-of-bounds access*.
     * **ThreadSanitizer (TSan)**: Menangkap *data race* dan pelanggaran *memory order synchronization*.
     * **UndefinedBehaviorSanitizer (UBSan)**: Memastikan tidak ada pergeseran bit ilegal, unaligned pointer access, atau integer overflow.
2. **Bounds Checking pada Ring Buffer Masking**:
   Pola bitwise mask `current_tail & BufferMask` secara matematis menjamin bahwa indeks komputasi tidak akan pernah menunjuk ke alamat di luar ukuran kapasitas array storage (`buffer bounds`).

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Sistem enterprise berlatensi rendah tidak diperkenankan menggunakan logging synchronous berbasis I/O disk (seperti `std::cout` atau penulisan teks file konvensional) pada hot-path karena system call kernel `write()` memakan latensi ribuan nanodetik.

### Arsitektur Zero-Allocation Asynchronous Ring-Buffer Logging:
1. Thread Hot-path hanya menulis representasi biner terstruktur (misal: ID status, parameter numerik) ke Outbound Logging SPSC Ring Buffer.
2. Thread latar belakang terpisah (*Cold-Path Logger Daemon*) mengambil data dari ring buffer, memformat data biner tersebut menjadi representasi string atau format JSON, lalu melakukan *flush* data ke disk/SSD secara periodik.

```
[ Domain Hot-Path Thread ] 
      |  (Write Binary Event)  O(1) < 20 ns
      v
[ SPSC Logging Ring Buffer ]
      |  (Batch Drain)
      v
[ Background Logger Thread ] ---> Disk Storage / Network Socket
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

* **Cache Line Rule**: Variabel atomik multithread yang saling berseberangan wajib dipisahkan jarak minimal 64 bytes (`hardware_destructive_interference_size`) untuk menghindari *False Sharing*.
* **Memory Orders Rule**:
  * Menulis indeks untuk diteruskan ke thread lain: Gunakan `std::memory_order_release`.
  * Membaca indeks yang dipublikasikan thread lain: Gunakan `std::memory_order_acquire`.
  * Membaca atau memodifikasi variabel privat kepemilikan thread sendiri: Gunakan `std::memory_order_relaxed`.
* **Performance Rule**: Hindari dynamic memory dispatch (`virtual`) dan dynamic memory allocation (`new`/`malloc`) pada hot path eksekusi. Gantikan polimorfisme runtime dengan C++20 Concepts dan Static Dispatch.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)
1. **Mengapa kapasitas Ring Buffer pada antrean lock-free umumnya diwajibkan berupa angka perpangkatan dua (*power of two*)?**
   * *Jawaban*: Agar operasi modulo matematika yang lambat (`index % Capacity`) dapat digantikan oleh instruksi operasi logika biner hardware yang cepat (`index & (Capacity - 1)`).
2. **Apa yang dimaksud dengan fenomena *False Sharing* pada aplikasi multithreading?**
   * *Jawaban*: Kondisi ketika dua thread pada core CPU berbeda memodifikasi variabel independen yang kebetulan berada di dalam satu baris cache memori (*cache line*) 64-byte yang sama, memicu invalidasi cache bolak-balik antar core CPU secara terus-menerus.
3. **Mengapa penggunaan `std::shared_ptr` dihindari pada hot-path aplikasi real-time low-latency?**
   * *Jawaban*: `std::shared_ptr` melakukan manipulasi atomic reference counting (`increment`/`decrement`) di OS heap setiap kali disalin, yang mengakibatkan lonjakan latensi eksekusi memori hardware.
4. **Apa implikasi dari atribut C++ `alignas` terhadap footprint memori?**
   * *Jawaban*: `alignas` memaksa kompilator menaruh alamat offset awal suatu struktur data pada kelipatan byte yang ditentukan, menyisipkan padding kosong jika diperlukan agar selaras dengan arsitektur hardware.
5. **Kapan kita harus menggunakan `std::memory_order_relaxed`?**
   * *Jawaban*: Ketika operasi atomik yang dilakukan tidak memerlukan sinkronisasi urutan instruksi baca/tulis memori terhadap variabel lain di thread yang berbeda.

### Soal Tingkat Menengah (Intermediate)
6. **Jelaskan perbedaan mekanika hardware antara `std::memory_order_seq_cst` dan `std::memory_order_acquire/release` pada arsitektur x86_64!**
   * *Jawaban*: Arsitektur x86_64 secara hardware sudah menerapkan model konsistensi TSO (*Total Store Order*). Instruksi load memiliki karakteristik acquire secara implisit, dan store memiliki karakteristik release secara implisit. Penambahan `seq_cst` pada x86_64 memaksa disisipkannya instruksi serialisasi memori penuh (`lock` prefix atau `mfence`), sedangkan `acquire-release` tidak menghasilkan instruksi pagar tambahan, sehingga jauh lebih efisien.
7. **Bagaimana C++20 Concepts membantu eliminasi overhead latensi jika dibandingkan dengan *Abstract Interface Class* murni?**
   * *Jawaban*: Abstract Interface menggunakan virtual function table (*vtable*) yang diselesaikan secara dinamis pada saat program berjalan (*runtime*), mencegah inlining oleh kompiler. C++20 Concepts melakukan verifikasi interface pada saat kompilasi (*compile-time*), memungkinkan kompiler memanggil fungsi secara langsung (*direct dispatch*) dan melakukan *inline optimization*.
8. **Mengapa `head_cached_` dan `tail_cached_` disimpan secara lokal di dalam class SPSC Ring Buffer?**
   * *Jawaban*: Untuk meminimalkan frekuensi pembacaan variabel atomik antar-core CPU. Index cache lokal memungkinkan thread memeriksa kapasitas tanpa memicu protokol koherensi cache (cache snoop) ke core sebelah sampai buffer terdeteksi benar-benar penuh atau kosong.
9. **Apa risiko arsitektural jika pengecualian (*C++ Exceptions*) dilempar di dalam alur hot-path?**
   * *Jawaban*: Penanganan exception memerlukan pembongkaran stack (*stack unwinding*) dan pembacaan tabel metadata landing pad yang kompleks oleh OS runtime, menyebabkan lonjakan latensi (*jitter*) hingga skala milidetik.
10. **Bagaimana cara menjamin objek yang diproses melalui ring buffer tidak memicu realokasi memori internal?**
    * *Jawaban*: Dengan mewajibkan tipe data berupa *Plain Old Data* (POD), tipe data bernilai tetap (*Trivially Copyable*), atau memastikan kelas objek memiliki move constructor berpredikat `noexcept` tanpa heap internal.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: Ultra-High-Throughput Financial Order-Book Engine

#### Deskripsi Spesifikasi Proyek:
Kembangkan modul implementasi penuh dari mesin pencocokan transaksi finansial (*Order Book Matching Core*) dengan spesifikasi enterprise:

1. **Struktur Data Limit Order Book**:
   * Buat struktur data buku order *bids* (beli) dan *asks* (jual) yang menampung level harga hingga 1.000 kedalaman harga (*price levels*).
   * Dilarang menggunakan alokasi dinamis (`std::map`, `new`, atau `std::list`) pada saat proses order matching berjalan. Gunakan array statis atau circular flat-arrays.
2. **Pipeline Pemrosesan Terisolasi**:
   * Implementasikan thread parser terpisah yang membaca data *streaming command* order dan mendorongnya ke dalam antrean `SpscRingBuffer`.
   * Implementasikan thread matching engine yang memproses order dari ring buffer tersebut dan mencocokkan logika transaksi:
     * Jika limit order beli $\ge$ harga limit order jual terendah: Eksekusi transaksi (*match*).
     * Jika tidak: Catat pesanan pada antrean buku order.
3. **Persyaratan Metrik & Benchmarking**:
   * Bangun harness pengujian menggunakan simulasi minimal **5.000.000 Order Message**.
   * Hitung dan visualisasikan profil latensi komprehensif pada konsol terminal:
     * Min Latency
     * Median (p50) Latency
     * 99th Percentile (p99) Latency
     * Max Latency
   * Target kinerja sistem: Tail latency p99 **wajib di bawah 1.000 nanodetik (1 mikrosekon)** per operasi pada kompilasi rilis (`-O3`).
4. **Verifikasi Kualitas**:
   * Kompilasi program dengan seluruh flag keamanan berikut:
     ```bash
     g++ -std=c++20 -O3 -Wall -Wextra -Wpedantic -Werror -fsanitize=thread -pthread main.cpp
     ```
   * Pastikan output eksekusi tidak memicu warning dan bersih dari thread race conditions (TSan: `0 data races detected`).