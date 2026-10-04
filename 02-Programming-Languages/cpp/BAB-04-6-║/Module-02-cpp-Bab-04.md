# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 04: Sistem Berperforma Ekstrem, Concurrency Lanjutan, dan Hardware-Aware Architecture (C++20/C++23)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik enterprise diharapkan mampu:
1. **Menganalisis dan Memitigasi Cache Thrashing & False Sharing**: Mengidentifikasi dampak struktur data terhadap arsitektur CPU multicore dan menerapkan memory alignment berbasis `std::hardware_destructive_interference_size`.
2. **Merancang Struktur Data Lock-Free Berkinerja Tinggi**: Mengimplementasikan algoritma concurrent lock-free berstandar industri dengan memanfaatkan *C++ Memory Model*, *Atomic Operations*, dan *Acquire-Release Semantics*.
3. **Mengoptimalkan Jalur Eksekusi Zero-Copy Memory Management**: Memanfaatkan custom memory arena, fixed-size block allocators, serta teknik *placement new* untuk meminimalkan beban heap allocation pada hot-path transaksi berkecepatan tinggi.
4. **Menerapkan Profiling Hardware-Level**: Melakukan audit performa mikro-arsitektur menggunakan Linux `perf`, `perf c2c`, dan ThreadSanitizer (TSan) untuk mendeteksi *instruction stall*, *branch misprediction*, serta *cache miss contention*.

---

## 2. Prerequisite

Sebelum menempuh materi ini, peserta diwajibkan telah menguasai:
* Pemahaman mendalam tentang **C++ Memory Layout** (Stack, BSS, Data, Heap, Memory Alignment, Padding).
* Konsep dasar multithreading C++11/17/20 (`std::jthread`, `std::mutex`, `std::unique_lock`, `std::condition_variable`).
* Prinsip dasar arsitektur x86-64 / ARMv8 (Registers, CPU Caches L1/L2/L3, Translation Lookaside Buffer / TLB).
* Semantik Move C++11 (`std::move`, *rvalue reference*, *perfect forwarding*).
* Kemampuan membaca assembly x86-64 tingkat dasar (instruksi `mov`, `lock xadd`, `mfence`, `cmpxchg`).

---

## 3. Concept & Internal Architecture

### 3.1 Hardware-Aware Architecture & Cache Hierarchy

Mikroprosesor modern tidak berinteraksi langsung dengan Random Access Memory (RAM) pada setiap instruksi memori. Transfer data terjadi melalui hierarki cache dalam satuan blok berukuran tetap yang disebut **Cache Line** (umumnya 64 byte pada x86-64 dan Apple Silicon/ARMv8):

```
+-------------------------------------------------------------------------+
|                              CPU SOCKET                                 |
|                                                                         |
|  +-----------------------------+       +-----------------------------+  |
|  |           CORE 0            |       |           CORE 1            |  |
|  |  +-------+       +-------+  |       |  +-------+       +-------+  |  |
|  |  | L1-I  |       | L1-D  |  |       |  | L1-I  |       | L1-D  |  |  |
|  |  | 32 KB |       | 32 KB |  |       |  | 32 KB |       | 32 KB |  |  |
|  |  +-------+       +-------+  |       |  +-------+       +-------+  |  |
|  |              |              |       |              |              |  |
|  |      +---------------+      |       |      +---------------+      |  |
|  |      |   L2 Cache    |      |       |      |   L2 Cache    |      |  |
|  |      |    512 KB     |      |       |      |    512 KB     |      |  |
|  |      +---------------+      |       |      +---------------+      |  |
|  +--------------|--------------+       +--------------|--------------+  |
|                 +----------------------+--------------+                 |
|                                        |                                |
|                        +-------------------------------+                |
|                        |      L3 Cache (Shared LLC)    |                |
|                        |             16-64 MB          |                |
|                        +-------------------------------+                |
+----------------------------------------|--------------------------------+
                                         |
                             +-----------------------+
                             |   Main Memory (DRAM)  |
                             +-----------------------+
```

### 3.2 False Sharing dan MESI / MOESI Cache Invalidation

Ketika dua thread yang dieksekusi di dua core berbeda memodifikasi variabel independen yang kebetulan berada di dalam **cache line yang sama**, protokol koherensi cache hardware (seperti MESI: *Modified, Exclusive, Shared, Invalid*) akan memaksa invalidasi cache line tersebut secara bolak-balik antar core. 

Fenomena ini disebut **False Sharing**:
1. Core 0 memodifikasi `var_A` $\rightarrow$ Cache line ditandai *Modified* di Core 0; salinan di L1/L2 Core 1 di-*invalidate*.
2. Core 1 ingin memodifikasi `var_B` (yang satu cache line dengan `var_A`) $\rightarrow$ Terjadi cache miss, Core 1 memaksa Core 0 melakukan flush/write-back ke L3/RAM.
3. Terjadi *cache bouncing* konstan yang menurunkan throughput eksekusi paralel hingga puluhan kali lipat.

### 3.3 C++ Memory Model & Atomics

C++11 memperkenalkan standard formal memory model. Pada sistem multicore, kompiler dan CPU dapat melakukan *instruction reordering* kecuali kita membatasinya secara eksplisit menggunakan *memory ordering*:

* **`std::memory_order_relaxed`**: Hanya menjamin operasi atomik (tidak ada *torn read/write*). Tidak ada batasan reordering terhadap instruksi memori lain.
* **`std::memory_order_acquire`**: Digunakan saat operasi read/load. Menjamin operasi baca/tulis memori setelahnya dalam program order **tidak dapat direorder sebelum** instruksi acquire ini.
* **`std::memory_order_release`**: Digunakan saat operasi write/store. Menjamin operasi baca/tulis memori sebelumnya **tidak dapat direorder setelah** instruksi release ini.
* **`std::memory_order_acq_rel`**: Kombinasi acquire dan release pada operasi Read-Modify-Write (RMW) seperti `compare_exchange`.
* **`std::memory_order_seq_cst`** (Sequential Consistency): Default. Menjamin ada *total global execution order* yang disepakati oleh semua thread, namun menimbulkan overhead memory barrier (`mfence`) yang sangat mahal pada arsitektur tertentu.

---

## 4. Why & What

| Dimensi | Sinkronisasi Berbasis Mutex (`std::mutex`) | Sinkronisasi Lock-Free (`std::atomic` Acquire-Release) |
| :--- | :--- | :--- |
| **Mekanisme** | Blokade via kernel scheduler (futex di Linux) | Spin/CAS langsung pada hardware register/cache line |
| **Karakteristik Latensi** | P99 tidak terprediksi (context switch overhead: ~1.5 - 5 $\mu$s) | Sangat konsisten dan deterministik (latensi sub-mikrodetik) |
| **Overhead Deadlock** | Rentan jika lock ordering tidak dijaga | Bebas dari masalah deadlock |
| **Priority Inversion** | Rentan terjadi jika thread berprioritas rendah memegang lock | Bebas dari priority inversion |
| **Kompleksitas Kode** | Rendah - Moderat | Sangat Tinggi (rawan race conditions, ABA problem, reordering) |
| **Kasus Penggunaan** | Sistem Enterprise CRUD, operasi I/O-bound | HFT (High-Frequency Trading), Game Engine core loop, Audio DSP |

---

## 5. How (Workflow Detail)

Alur kerja implementasi Single-Producer Single-Consumer (SPSC) Lock-Free Queue berkecepatan tinggi:

```
[ Producer Thread ]                              [ Consumer Thread ]
        |                                                |
        | 1. Periksa ketersediaan slot (Load Head/Tail)  |
        |    -> tail.load(relaxed)                       |
        |    -> head.load(acquire)                       |
        |                                                |
        | 2. Tulis data ke Buffer[tail] (In-place)       |
        |    -> Zero-copy write via reference/pointer    |
        |                                                |
        | 3. Publikasikan data ke Consumer              |
        |    -> tail.store(new_tail, release) ---------->| 4. Deteksi slot baru via tail
        |                                                |    -> tail.load(acquire)
        |                                                |
        |                                                | 5. Baca data dari Buffer[head]
        |                                                |    -> Zero-copy read / move
        |                                                |
        | 7. Deteksi slot kosong                         | 6. Perbarui slot yang kosong
        |<-- head.store(new_head, release) <-------------+    -> head.store(new_head, release)
```

1. **Step 1 (Allocation & Padding)**: Alokasikan ring buffer dengan kapasitas berpangkat dua ($2^n$) untuk optimasi modulo bitwise (`index & (size - 1)`). Setiap index pointer (`head` dan `tail`) dialokasikan pada cache line terpisah menggunakan `alignas(hardware_destructive_interference_size)`.
2. **Step 2 (Memory Ordering Coordination)**:
   - Producer memperbarui buffer payload, lalu melakukan `tail.store(..., std::memory_order_release)`.
   - Consumer membaca `tail.load(std::memory_order_acquire)`, memastikan payload telah selesai ditulis sebelum dikonsumsi.
3. **Step 3 (Zero-Copy Transfer)**: Hindari alokasi heap saat transfer item. Gunakan objek *in-place* atau swap pointer.

---

## 6. Analogy & Diagram ASCII

### Analogi: Dua Operator Ban Berjalan Terpisah

Bayangkan sebuah pabrik ban berjalan melingkar dengan 8 kotak penyimpanan.
* **Producer (Operator Pemasok)** hanya memegang tongkat penunjuk **Tail**.
* **Consumer (Operator Pengepak)** hanya memegang tongkat penunjuk **Head**.
* Jika Tail dan Head berada di meja yang sama (satu cache line), setiap kali Producer menggeser tongkatnya, ia menyenggol Consumer sehingga Consumer harus berhenti sejenak dan menata ulang posisinya (*False Sharing*).
* Dengan menempatkan papan penunjuk Producer di dinding barat dan papan penunjuk Consumer di dinding timur (*Cache Line Alignment*), keduanya dapat bekerja pada kecepatan penuh tanpa saling menyenggol, berkoordinasi hanya melalui sinyal lampu hijau/merah (*Acquire-Release Semantics*).

```
================================ CACHE LINE SEPARATION ================================
Cache Line 0 (64 Bytes)                  Cache Line 1 (64 Bytes)
+---------------------------------------+ +---------------------------------------+
|  atomic<size_t> tail;                 | |  atomic<size_t> head;                 |
|  char padding1[64 - sizeof(tail)];    | |  char padding2[64 - sizeof(head)];    |
+---------------------------------------+ +---------------------------------------+
                   |                                         |
                   v                                         v
   +-------+-------+-------+-------+-------+-------+-------+-------+
   | Slot 0| Slot 1| Slot 2| Slot 3| Slot 4| Slot 5| Slot 6| Slot 7|   <-- Ring Buffer Data
   +-------+-------+-------+-------+-------+-------+-------+-------+
                       ^                               ^
                       | (Write: Producer)             | (Read: Consumer)
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Membuktikan Dampak False Sharing

Contoh berikut menunjukkan bagaimana dua thread yang menulis data pada cache line yang sama menyebabkan degradasi performa drastis.

```cpp
#include <iostream>
#include <thread>
#include <chrono>
#include <new>

// Struktur yang menyebabkan False Sharing:
// x dan y berada dalam satu 64-byte cache line yang sama.
struct FalseSharingTarget {
    uint64_t x{0};
    uint64_t y{0};
};

// Struktur yang terlindungi dari False Sharing:
// x dan y berada pada cache line yang independen.
struct alignas(64) CacheAlignedTarget {
    alignas(64) uint64_t x{0};
    alignas(64) uint64_t y{0};
};

constexpr uint64_t ITERATIONS = 500'000'000;

template <typename T>
void benchmark_contention(const std::string& label) {
    T target;
    auto start = std::chrono::steady_clock::now();

    std::jthread t1([&]() {
        for (uint64_t i = 0; i < ITERATIONS; ++i) {
            target.x += 1;
        }
    });

    std::jthread t2([&]() {
        for (uint64_t i = 0; i < ITERATIONS; ++i) {
            target.y += 1;
        }
    });

    t1.join();
    t2.join();

    auto end = std::chrono::steady_clock::now();
    auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();
    std::cout << "[" << label << "] Total Waktu Eksekusi: " << elapsed << " ms\n";
}

int main() {
    std::cout << "Starting False Sharing Benchmark (" << ITERATIONS << " iterasi)...\n";
    benchmark_contention<FalseSharingTarget>("Terkena False Sharing");
    benchmark_contention<CacheAlignedTarget>("Cache-Line Aligned   ");
    return 0;
}
```

---

### 7.2 Practical Example: Enterprise-Grade Lock-Free SPSC Ring Buffer (C++20)

Berikut adalah implementasi queue Single-Producer Single-Consumer (SPSC) tanpa lock (*lock-free* dan *wait-free*) yang memenuhi standar produksi: zero-allocation saat runtime, cache-line aware, bitwise wrapping, dan acquire-release semantics.

```cpp
#pragma once

#include <atomic>
#include <cstddef>
#include <new>
#include <optional>
#include <concepts>
#include <vector>
#include <span>

#ifdef __cpp_lib_hardware_interference_size
    using std::hardware_destructive_interference_size;
#else
    // Fallback standar arsitektur x86-64 / modern ARM
    constexpr size_t hardware_destructive_interference_size = 64;
#endif

template <typename T, size_t Capacity>
    requires (Capacity >= 2) && ((Capacity & (Capacity - 1)) == 0) // Wajib kelipatan 2 (Power of Two)
class SpscLockFreeQueue {
public:
    static_assert(std::is_nothrow_destructible_v<T>, "T wajib memiliki nothrow destructor");

    SpscLockFreeQueue() 
        : buffer_(static_cast<T*>(::operator new[](sizeof(T) * Capacity))) {}

    ~SpscLockFreeQueue() {
        T discarded;
        while (pop(discarded)) {}
        ::operator delete[](buffer_);
    }

    // Larang copy dan move semantics untuk menjaga integritas memory address
    SpscLockFreeQueue(const SpscLockFreeQueue&) = delete;
    SpscLockFreeQueue& operator=(const SpscLockFreeQueue&) = delete;
    SpscLockFreeQueue(SpscLockFreeQueue&&) = delete;
    SpscLockFreeQueue& operator=(SpscLockFreeQueue&&) = delete;

    template <typename... Args>
    bool emplace(Args&&... args) noexcept(std::is_nothrow_constructible_v<T, Args...>) {
        const size_t current_tail = tail_.load(std::memory_order_relaxed);
        
        // Cek apakah buffer penuh. 
        // Menggunakan head_cache_ untuk menghindari sinkronisasi inter-core yang tidak perlu.
        if ((current_tail - head_cache_) >= Capacity) {
            head_cache_ = head_.load(std::memory_order_acquire);
            if ((current_tail - head_cache_) >= Capacity) {
                return false; // Queue penuh
            }
        }

        // Penulisan in-place ke buffer (Zero-Copy)
        new (&buffer_[current_tail & BufferMask]) T(std::forward<Args>(args)...);

        // Publikasikan ke consumer dengan release semantics
        tail_.store(current_tail + 1, std::memory_order_release);
        return true;
    }

    bool push(const T& item) noexcept(std::is_nothrow_copy_constructible_v<T>) {
        return emplace(item);
    }

    bool push(T&& item) noexcept(std::is_nothrow_move_constructible_v<T>) {
        return emplace(std::move(item));
    }

    bool pop(T& val) noexcept(std::is_nothrow_move_assignable_v<T>) {
        const size_t current_head = head_.load(std::memory_order_relaxed);

        // Cek apakah buffer kosong
        if (current_head == tail_cache_) {
            tail_cache_ = tail_.load(std::memory_order_acquire);
            if (current_head == tail_cache_) {
                return false; // Queue kosong
            }
        }

        T* slot = &buffer_[current_head & BufferMask];
        val = std::move(*slot);
        slot->~T(); // Jalankan destruktor item yang dikonsumsi

        // Beri tahu producer bahwa slot telah dibebaskan
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

    T* const buffer_;

    // Variabel Producer ditempatkan pada cache line terpisah
    alignas(hardware_destructive_interference_size) std::atomic<size_t> tail_{0};
    size_t head_cache_{0};

    // Variabel Consumer ditempatkan pada cache line terpisah
    alignas(hardware_destructive_interference_size) std::atomic<size_t> head_{0};
    size_t tail_cache_{0};
};
```

---

## 8. Real World Case Study: High-Frequency Trading Market Data Dispatcher

### Konteks Kasus
Sebuah institusi High-Frequency Trading (HFT) menerima pesan order book via multicast UDP (NASDAQ ITCH Protocol) dengan throughput mencapai 15 juta paket per detik pada jam pembukaan pasar (*market open*). 

### Masalah Arsitektur Lama
Arsitektur awal menggunakan `std::queue<MarketTick>` yang dilindungi oleh `std::mutex` dan `std::condition_variable`.
* **Gejala Masalah**: Latensi P99.9 membengkak hingga $280\,\mu\text{s}$. Terjadi jutaan paket UDP *drop* pada kernel network buffer (`netstat -s` mencatat receive buffer errors).
* **Akar Masalah**:
  1. *Context Switch Saturation*: Mutex lock contention memicu thread context switch ke OS kernel ribuan kali per detik.
  2. *Dynamic Allocation Thrashing*: Setiap event `MarketTick` dialokasikan secara dinamis (`malloc`), memicu memory fragmentation dan LLC (L3) miss tinggi.

### Solusi Arsitektur Produksi (Hardware-Aware Modern C++)
1. **Network I/O Thread Pinning**: Thread network reader di-pin ke Core 2 (NUMA Node 0) menggunakan `pthread_setaffinity_np`.
2. **Strategy Engine Thread Pinning**: Thread kalkulasi pricing di-pin ke Core 3 (berada di L3 cache yang sama dengan Core 2).
3. **Lock-Free SPSC Inter-Core Communication**: Mengganti mutex queue dengan `SpscLockFreeQueue<MarketTick, 65536>`.
4. **Huge Pages Memory Backing**: Mengalokasikan array penyimpan data menggunakan *HugePages 2MB* (`mmap` dengan flag `MAP_HUGETLB`) untuk meniadakan TLB miss.

### Hasil Metrik Performa

```
+------------------------------------+--------------------+--------------------+
| Metrik Produksi                    | Arsitektur Mutex   | Lock-Free SPSC     |
+------------------------------------+--------------------+--------------------+
| Throughput Maksimal                | 1.2 Juta msg/sec   | 22.4 Juta msg/sec  |
| Latensi Rata-rata (P50)            | 3.20 us            | 0.045 us (45 ns)   |
| Latensi Ekor (P99.9)               | 285.00 us          | 0.120 us (120 ns)  |
| Paket Drop (Kernel Drops)          | 4.12%              | 0.00%              |
| Context Switches per Detik         | ~450,000           | ~0 (Pure Polling)  |
+------------------------------------+--------------------+--------------------+
```

---

## 9. Trade-offs

| Pendekatan Arsitektur | Keuntungan | Kerugian & Konsekuensi | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **Lock-Free SPSC Queue** | * Deterministic latency (O(1))<br>* Nol context switch<br>* Skalabilitas vertikal maksimal | * Hanya mendukung 1 Producer & 1 Consumer<br>* Kapasitas fixed (bounded)<br>* Boros daya jika menggunakan polling | Pipeline hot-path (HFT, Audio Processing, Network Gateway). |
| **Lock-Free MPMC Queue** | * Fleksibel (banyak producer & consumer)<br>* Tidak memblokir kernel scheduler | * Kompleksitas tinggi (rawan ABA)<br>* Penurunan performa drastis akibat CAS loop retry saat contention tinggi | Worker pool pemrosesan umum di mana producer tidak dapat diprediksi. |
| **Pthread Spinlock** | * Lebih cepat dari mutex standar jika critical section sangat pendek | * Dapat memonopoli 100% core CPU<br>* Rentan starvation jika thread preempted oleh OS | Operasi embedded low-level tanpa OS interrupt. |
| **Standard `std::mutex`** | * Sederhana dan aman<br>* Hemat daya (thread tidur saat idle)<br>* Tidak rentan terhadap reordering bug | * Latensi ekor tinggi (P99/P99.9 buruk)<br>* Kemungkinan priority inversion | Control plane, inisialisasi aplikasi, data transfer dengan I/O-bound. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 The ABA Problem pada Desain Lock-Free
* **Gejala**: Thread A membaca nilai pointer $P$ (berisi alamat objek $A$). Thread B mengosongkan objek $A$, mengalokasikan objek baru $B$, lalu mengalokasikan objek $C$ yang kebetulan dialokasikan OS pada alamat memori yang persis sama dengan $A$. Thread A melakukan `compare_exchange_weak(P, A, new_val)`. CAS sukses padahal state data sudah berubah total!
* **Troubleshooting**: Gunakan *Double-Word Compare and Swap* (DWCAS) dengan tagging generasi versi (misalnya `std::atomic<TaggedPointer>`), atau gunakan hazard pointers / `std::atomic<std::shared_ptr<T>>`.

### 10.2 Asumsi Keliru Bahwa `volatile` Menjamin Atomicitas
* **Kesalahan Fatal**: Menggunakan `volatile bool flag = false;` untuk sinkronisasi antar-thread.
* **Fakta Teknis**: Kata kunci `volatile` dalam C++ **bukanlah atomic barrier**. `volatile` hanya melarang optimasi register caching oleh kompiler, namun **tidak menerbitkan memory barrier** pada hardware CPU, sehingga CPU instruction reordering tetap terjadi.
* **Solusi**: Gunakan selalu `std::atomic<T>`.

### 10.3 Mendeteksi Contention Menggunakan Profiler Linux
Jalankan perintah berikut untuk mengaudit *cache line contention* di lingkungan Linux:

```bash
# Record hardware cache-to-cache bouncing
perf c2c record -F 60000 -- ./production_app_binary

# Analisis hasil rekaman
perf c2c report --stdio
```
*Jika kolom `HITM` (Hit in Modified Cache) menunjukkan angka tinggi pada offset struktur tertentu, variabel tersebut menderita **False Sharing** dan wajib diberikan padding.*

---

## 11. Best Practices (Production Checklist)

- [ ] **Gunakan `alignas` untuk Variabel Multithreading**: Pisahkan state write antar thread minimal sejauh `hardware_destructive_interference_size` byte.
- [ ] **Hindari Dynamic Allocation pada Hot Path**: Semua alokasi buffer harus dialokasikan secara statis di muka (*pre-allocated*) saat aplikasi booting.
- [ ] **Pilih Memory Order yang Paling Longgar namun Aman**: Gunakan `memory_order_relaxed` jika koordinasi antar-variabel tidak diperlukan; gunakan `memory_order_acquire` / `release` untuk transfer state data; hindari `memory_order_seq_cst` kecuali mutlak diperlukan.
- [ ] **Aktifkan ThreadSanitizer pada Pipeline CI/CD**: Kompilasi unit test menggunakan flag `-fsanitize=thread -g` pada GCC/Clang untuk menangkap *data races* terselubung.
- [ ] **Periksa `is_lock_free()`**: Berikan static assert untuk memverifikasi bahwa tipe atomic didukung langsung secara hardware tanpa internal lock OS:
  ```cpp
  static_assert(std::atomic<size_t>::is_always_lock_free, "Hardware tidak mendukung lock-free size_t");
  ```
- [ ] **Implementasikan CPU Core Pinning**: Pasang *thread affinity* (`pthread_setaffinity_np`) untuk thread kritis guna meminimalkan cache eviction akibat migrasi core oleh OS scheduler.

---

## 12. Hands-on Practice

Buat dan jalankan modul praktikum ini pada direktori `hands-on/m02/`.

### Struktur File
```
hands-on/m02/
├── CMakeLists.txt
├── include/
│   └── spsc_queue.hpp
└── src/
    └── main.cpp
```

### File: `hands-on/m02/include/spsc_queue.hpp`
Gunakan implementasi kode `SpscLockFreeQueue` dari Seksi 7.2.

### File: `hands-on/m02/src/main.cpp`
```cpp
#include <iostream>
#include <thread>
#include <chrono>
#include <vector>
#include "spsc_queue.hpp"

struct ExecutionReport {
    uint64_t order_id;
    double price;
    uint32_t quantity;
    char side; // 'B' = Buy, 'S' = Sell
};

constexpr size_t TOTAL_MESSAGES = 10'000'000;
constexpr size_t QUEUE_CAPACITY = 65536;

int main() {
    std::cout << "Starting High-Throughput SPSC Benchmark...\n";
    auto queue = std::make_unique<SpscLockFreeQueue<ExecutionReport, QUEUE_CAPACITY>>();

    auto start_time = std::chrono::steady_clock::now();

    // Producer: Mensimulasikan Gateway Eksekusi Pasar
    std::jthread producer([&]() {
        for (uint64_t i = 1; i <= TOTAL_MESSAGES; ++i) {
            ExecutionReport report{
                .order_id = i,
                .price = 150.25 + (i % 100),
                .quantity = static_cast<uint32_t>((i % 10) * 100),
                .side = (i % 2 == 0) ? 'B' : 'S'
            };
            while (!queue->emplace(report)) {
                // Backoff ringan saat ring buffer penuh
                #if defined(__x86_64__) || defined(_M_X64)
                __builtin_ia32_pause();
                #endif
            }
        }
    });

    // Consumer: Mensimulasikan Accounting & Risk Management Engine
    uint64_t consumed_count = 0;
    uint64_t check_sum_orders = 0;

    std::jthread consumer([&]() {
        ExecutionReport report;
        while (consumed_count < TOTAL_MESSAGES) {
            if (queue->pop(report)) {
                check_sum_orders += report.order_id;
                consumed_count++;
            } else {
                #if defined(__x86_64__) || defined(_M_X64)
                __builtin_ia32_pause();
                #endif
            }
        }
    });

    producer.join();
    consumer.join();

    auto end_time = std::chrono::steady_clock::now();
    auto total_duration_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(end_time - start_time).count();
    double duration_sec = static_cast<double>(total_duration_ns) / 1e9;
    double throughput = static_cast<double>(TOTAL_MESSAGES) / duration_sec;

    std::cout << "Benchmarking Selesai.\n";
    std::cout << "Total Pesan Terproses : " << consumed_count << "\n";
    std::cout << "Checksum Order ID     : " << check_sum_orders << "\n";
    std::cout << "Waktu Eksekusi        : " << duration_sec << " detik\n";
    std::cout << "Throughput            : " << (throughput / 1e6) << " Juta pesan/detik\n";
    std::cout << "Rata-rata Latensi     : " << (static_cast<double>(total_duration_ns) / TOTAL_MESSAGES) << " ns/pesan\n";

    return 0;
}
```

### File: `hands-on/m02/CMakeLists.txt`
```cmake
cmake_minimum_required(VERSION 3.20)
project(spsc_lockfree_benchmark CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Optimization Flags untuk Low-Latency C++
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -march=native -Wall -Wextra -pthread")

# Tambahkan opsi Sanitizer untuk Debug build
if (CMAKE_BUILD_TYPE STREQUAL "ThreadSanitizer")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fsanitize=thread -g")
endif()

include_directories(include)
add_executable(spsc_benchmark src/main.cpp)
```

### Instruksi Kompilasi & Eksekusi:
```bash
cd hands-on/m02
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j$(nproc)
./spsc_benchmark
```

---

## 13. Exercise

### Level Easy
Modifikasi implementasi `SpscLockFreeQueue` agar memiliki metode `std::optional<T> front()` yang melakukan inspeksi (*peek*) elemen terdepan tanpa mengeluarkannya dari queue.
* **Kriteria**: Metode harus *wait-free* dan tidak memodifikasi `head_`.

### Level Medium
Kembangkan program benchmark pada `hands-on/m02/src/main.cpp` untuk mengukur **Latensi Distribusi (Percentile Latency P50, P90, P99, P99.9)**.
* **Instruksi**: Gunakan hardware instruction timer (`__rdtsc` pada x86-64) untuk mengukur durasi interval antara saat Producer selesai memanggil `emplace` hingga Consumer berhasil menyelesaikan operasi `pop` untuk item yang sama.

### Level Hard
Buat implementasi **Multi-Producer Single-Consumer (MPSC) Bounded Queue** berbasis array statis berkapasitas $2^n$.
* **Kriteria Teknis**:
  - Gunakan `std::atomic<size_t>` untuk koordinasi alokasi tiket producer (`fetch_add`).
  - Selesaikan masalah *hole slot* (ketika producer A mendapatkan tiket namun terhambat sebelum selesai menulis payload, sementara consumer sudah siap membaca slot tersebut).
  - Pastikan bebas dari *data race* saat dites menggunakan ThreadSanitizer.

---

## 14. Challenge

### Arsitektur Shared-Memory Ring Buffer Antar-Proses (IPC Zero-Copy)

**Deskripsi Masalah Kasus Nyata:**
Di sistem operasi Linux, dua proses independen—**Proses Ingestion** (membaca feed data jaringan) dan **Proses Risk Engine**—perlu berkomunikasi dengan latensi di bawah 1 mikrodetik tanpa melibatkan network socket atau OS pipe overhead.

**Tugas Tantangan Arsitektur:**
1. Rancang modul **Shared Memory Lock-Free SPSC Ring Buffer** menggunakan sistem POSIX `shm_open()` dan `mmap()`.
2. Struktur data ring buffer harus dialokasikan langsung di dalam shared memory segment:
   - Data header dan atomic index harus aman diakses oleh dua proses dengan ruang alamat memori virtual (virtual address space) yang berbeda.
   - Pointer mentah (`T*`) tidak boleh digunakan di dalam header shared memory; gunakan relative offset alignment.
3. Terapkan proteksi crash recovery: Jika proses Producer crash saat menulis, proses Consumer harus mendeteksi inkonsistensi menggunakan mekanisme heartbeat/epoch timer atomic tanpa mengalami starvation tak berujung (*deadlock recovery*).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda / Analisis Singkat)
1. Berapa ukuran tipikal cache line pada prosesor arsitektur x86-64 modern?
   - A. 16 Byte
   - B. 32 Byte
   - C. 64 Byte
   - D. 128 Byte
   *Jawaban yang benar:* **C**. Sebagian besar arsitektur desktop dan server modern (Intel Core, AMD Zen, ARM Neoverse) menggunakan ukuran cache line 64 byte.

2. Mengapa kapasitas Ring Buffer lock-free sering kali disyaratkan berupa angka perpangkatan dua ($2^n$)?
   - A. Supaya memori otomatis dialokasikan di L1 cache.
   - B. Agar operasi modulo (`index % Capacity`) dapat diganti menjadi operasi bitwise AND (`index & (Capacity - 1)`) yang hanya memakan 1 clock cycle CPU.
   - C. Agar thread consumer tidak perlu membaca pointer producer.
   - D. Mengikuti batas spesifikasi C++20.
   *Jawaban yang benar:* **B**. Operasi pembagian/modulo integer (`div`/`idiv`) membutuhkan 10-40 cycle CPU, sedangkan bitwise AND hanya membutuhkan 1 cycle CPU.

3. Apa konsekuensi teknis dari penggunaan atribut `alignas(std::hardware_destructive_interference_size)` pada variabel?
   - A. Variabel tersebut otomatis menjadi thread-safe.
   - B. Kompiler akan memberikan padding byte tambahan agar variabel berada pada boundary cache line yang independen, mencegah False Sharing.
   - C. Menjamin variabel tidak akan pernah di-swap out ke disk/swap partition.
   - D. Membatasi ukuran variabel agar maksimal bernilai 64.
   *Jawaban yang benar:* **B**. Padding ini mengisolasi variabel dari cache line yang digunakan oleh thread lain.

4. Mana urutan performa sinkronisasi dari yang paling deterministik (cepat) hingga yang paling lambat?
   - A. Mutex $\rightarrow$ Acquire-Release $\rightarrow$ Relaxed
   - B. Relaxed $\rightarrow$ Acquire-Release $\rightarrow$ Sequential Consistency $\rightarrow$ Mutex
   - C. Sequential Consistency $\rightarrow$ Relaxed $\rightarrow$ Mutex $\rightarrow$ Spinlock
   - D. Mutex $\rightarrow$ Sequential Consistency $\rightarrow$ Acquire-Release $\rightarrow$ Relaxed
   *Jawaban yang benar:* **B**. Relaxed hanya memerlukan atomicitas register; Acquire-Release mengatur visibilitas inter-core; Sequential Consistency menambahkan bus locking/memory barrier total; Mutex melibatkan transition ke OS kernel.

5. Apakah kata kunci `volatile` pada C++ menjamin eksekusi instruksi aman dari reordering oleh CPU?
   - A. Ya, itu adalah standar C++ sejak C++11.
   - B. Tidak. `volatile` hanya melarang optimasi compiler, tidak mencegah out-of-order execution hardware.
   *Jawaban yang benar:* **B**.

---

### Bagian 2: Intermediate (Analisis Kode & Konsep)
1. **Analisis Potensi Bug**: Perhatikan potongan kode berikut:
   ```cpp
   std::atomic<bool> ready{false};
   int data = 0;

   // Thread 1
   data = 42;
   ready.store(true, std::memory_order_relaxed);

   // Thread 2
   if (ready.load(std::memory_order_relaxed)) {
       assert(data == 42); // Apakah assert ini dijamin tidak akan pernah gagal? Jelaskan!
   }
   ```
   *Jawaban Evaluasi:* **Assert DAPAT GAGAL**. Karena kedua operasi atomic menggunakan `std::memory_order_relaxed`, CPU dan kompiler diizinkan untuk mereorder penulisan `ready = true` mendahului `data = 42`, atau thread 2 membaca `data` sebelum membaca `ready`. Untuk menjamin sinkronisasi, Thread 1 harus menggunakan `std::memory_order_release` dan Thread 2 harus menggunakan `std::memory_order_acquire`.

2. Apa perbedaan fungsional antara `compare_exchange_weak` dan `compare_exchange_strong`? Kapan kita wajib memilih `compare_exchange_weak`?
   *Jawaban Evaluasi:* `compare_exchange_weak` dapat mengalami *spurious failure* (gagal meskipun nilainya cocok, biasanya akibat interupsi hardware/cache eviction pada arsitektur LL/SC seperti ARM), namun performanya lebih cepat. `weak` wajib digunakan ketika CAS berada di dalam **loop perulangan** (`while (!cas(...))`), karena loop tersebut akan otomatis mencoba kembali saat terjadi spurious failure. `compare_exchange_strong` dipilih jika CAS dilakukan tanpa loop pengulangan.

3. Jelaskan apa yang dimaksud dengan fenomena **Cache Thrashing** dan bagaimana cara membedakannya dengan **False Sharing**!
   *Jawaban Evaluasi:* **Cache Thrashing** terjadi ketika data yang diakses program secara berulang bersaing untuk menempati set cache yang sama (misalnya pada array yang ukurannya persis kelipatan set associativity cache), sehingga data saling meng-evict secara berulang meskipun hanya berjalan pada *single-thread*. Sedangkan **False Sharing** adalah fenomena *multithreading* di mana thread pada core berbeda memodifikasi variabel berbeda yang kebetulan berada dalam satu cache line yang sama.

4. Mengapa pada implementasi `SpscLockFreeQueue` (Seksi 7.2), kita menggunakan variabel bantuan lokal `head_cache_` dan `tail_cache_`?
   *Jawaban Evaluasi:* Untuk mengurangi frekuensi operasi pembacaan atomik lintas core (`head_.load(...)` atau `tail_.load(...)`). Dengan menyimpan nilai terakhir yang diketahui secara lokal, thread hanya perlu mengontak cache line milik core lain ketika buffer terindikasi penuh atau kosong. Ini mengurangi traffic inter-core interconnect (QPI/UPI/Infinity Fabric) secara signifikan.

5. Jika objek bertipe `T` yang disimpan di dalam Ring Buffer memiliki konstruktor yang melempar exception (*throwing constructor*), bagaimana dampaknya terhadap jaminan exception safety pada method `emplace`?
   *Jawaban Evaluasi:* Jika konstruksi `new (&buffer_[...]) T(...)` melempar exception, atomic `tail_` belum diperbarui (karena pembaruan index dilakukan setelah in-place new berhasil). Dengan demikian integritas queue tetap terjaga (*Strong Exception Safety*), namun slot memori yang gagal terisi tidak boleh mengalami leak jika payload sebagian telah teralokasi.

---

### Bagian 3: Skenario Kasus Produksi
1. **Skenario A (Investigasi Latensi Spike)**:
   Aplikasi pemrosesan video streaming real-time menggunakan pipeline Producer-Consumer lock-free. Pada saat diuji pada server lokal dengan 8 core (1 socket CPU), latensi transmisi antar frame sangat stabil di angka $80\,\text{ns}$. Namun ketika aplikasi di-deploy pada server enterprise bare-metal 64 core (Dual-Socket Intel Xeon), latensi P99.9 melonjak drastis hingga $12\,\mu\text{s}$. 
   *Audit masalah teknis yang terjadi dan berikan rekomendasi solusinya!*
   *Solusi Audit:* Server Dual-Socket memiliki arsitektur **NUMA (Non-Uniform Memory Access)**. Jika OS scheduler menjadwalkan Producer Thread di CPU Socket 0 dan Consumer Thread di CPU Socket 1, setiap pembaruan atomic index harus melintasi bus UPI (Ultra Path Interconnect) antar-soket fisik yang memiliki latensi jauh lebih tinggi dibanding inter-core L3 cache. 
   *Rekomendasi*: Ikat (*pin*) kedua thread ke core fisik yang berada di soket CPU dan NUMA node yang sama menggunakan `numactl --cpunodebind=0` atau `pthread_setaffinity_np`.

2. **Skenario B (Audit Bug Concurrency)**:
   Sebuah tim engineer membuat bounded queue lock-free berbasis *Multiple-Producer Multiple-Consumer* (MPMC). Saat diuji beban berat, sesekali data yang diterima oleh consumer berisi data korup (sebagian field berisi nilai acak). Kode producer menulis data menggunakan:
   ```cpp
   size_t idx = global_tail.fetch_add(1, std::memory_order_relaxed);
   slots[idx & MASK].payload = input_data;
   slots[idx & MASK].is_ready.store(true, std::memory_order_relaxed);
   ```
   *Jelaskan letak kelemahan fatal arsitektur memori pada kode tersebut!*
   *Solusi Audit:* Penggunaan `std::memory_order_relaxed` pada penyimpanan status `is_ready` mengizinkan arsitektur hardware prosesor untuk mereorder eksekusi instruksi: penulisan `is_ready.store(true)` dapat dipublikasikan ke core consumer **sebelum** penulisan `payload = input_data` selesai ditulis ke cache/RAM. Akibatnya Consumer membaca payload yang belum selesai diinisialisasi. Solusi: Ubah menjadi `slots[idx & MASK].is_ready.store(true, std::memory_order_release);` dan di sisi consumer gunakan `is_ready.load(std::memory_order_acquire);`.

3. **Skenario C (Memory Exhaustion & Destructor Leak)**:
   Dalam implementasi custom ring buffer, elemen dihapus hanya dengan memajukan atomic `head_` tanpa memanggil eksplisit destructor `slot->~T()`. Mengapa ini menjadi celah arsitektur enterprise yang kritis, terutama jika `T` adalah kelas yang mengelola dynamic resource seperti `std::string` atau buffer database?
   *Solusi Audit:* Jika tipe `T` mengalokasikan resource heap internal (seperti buffer dinamis pada `std::string` atau file descriptor), memajukan index tanpa memanggil destructor objek akan menyebabkan alokasi internal heap tersebut tertinggal tanpa pernah dibebaskan (*memory leak* akumulatif). Meskipun slot ring buffer itu sendiri dapat ditimpa di kemudian hari oleh *placement new*, data lama yang ditimpa tanpa didestruksi terlebih dahulu akan memicu kebocoran memori instan pada hot path sistem.

---

## 16. Summary

1. **Mechanical Sympathy adalah Kunci Utama**: Menulis kode performa tinggi tidak hanya seputar kompleksitas algoritma teoritis $O(1)$, melainkan pemahaman mendalam tentang bagaimana hardware mengeksekusi instruksi, mengatur pergerakan cache line 64-byte, dan menangani invalidasi cache antar core.
2. **False Sharing Menghancurkan Skalabilitas**: Variabel atomic yang sering diperbarui oleh thread berbeda wajib diisolasi menggunakan padding boundary `alignas(hardware_destructive_interference_size)` untuk mencegah cache thrashing internal prosesor.
3. **Memory Order adalah Kontrak Eksplisit**: Hindari asumsi implisit Sequential Consistency (`seq_cst`). Desain modern enterprise memanfaatkan sinkronisasi berpasangan: **`memory_order_release`** pada sisi writer dan **`memory_order_acquire`** pada sisi reader untuk memaksimalkan throughput eksekusi out-of-order CPU tanpa mengorbankan konsistensi state data.
4. **Zero-Copy & Zero-Allocation**: Pada hot path pemrosesan data real-time, seluruh alokasi memori wajib dialokasikan di muka (*pre-allocated*). Setiap operasi pertukaran pesan harus dilakukan secara in-place melalui teknik *placement new* dan move semantics untuk menjaga latensi P99.9 pada skala nanodetik.