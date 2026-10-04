# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori**: `01-Core-Foundations` | **Bab**: `07 - Materi Lanjutan`

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Menganalisis dan mengeliminasi degradasi performa pada level CPU cache hierarchy (*L1/L2/L3 cache miss*, *false sharing*, dan *cache line bouncing*).
- Merancang serta mengimplementasikan struktur data *lock-free* dan *wait-free* berbasis *atomic primitives* dan *memory ordering semantics* (`memory_order_relaxed`, `acquire`, `release`, `seq_cst`).
- Membangun *high-throughput, ultra-low-latency ingestion engine* berbasis pola *Ring Buffer* (*Disruptor Pattern*) dan I/O *zero-copy*.
- Menerapkan mitigasi produksi terhadap masalah memori tingkat rendah seperti *memory fragmentation*, *ABA problem*, dan penumpukan latensi *tail* ($p99$ / $p99.9$).

---

## 2. Prerequisite
Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- **Arsitektur Komputer Dasar**: Siklus instruksi CPU, register, virtual memory, paging, dan TLB (*Translation Lookaside Buffer*).
- **Sistem Operasi**: Thread lifecycle, kernel vs user space context switching, syscall overhead, dan mekanisme sinkronisasi primitif (mutex, semaphore, condition variable).
- **Bahasa Pemrograman Sistem**: Pemahaman pointer, referensi memori, dan kompilasi pada C/C++, Rust, atau Go runtime internals.
- **Kompleksitas Algoritma**: Notasi Big-O, amortized time complexity, dan cache-oblivious algorithms dasar.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Hardware Memory Subsystem & Protokol Koherensi Cache
Pada arsitektur sistem modern Multi-Core (SMP/NUMA), interaksi antara register CPU, cache ($L1$, $L2$, $L3$), dan *Main Memory* (DRAM) didasarkan pada satuan unit diskret bernama **Cache Line** (umumnya berukuran 64 byte). 

```
+-------------------------------------------------------------------------+
|                               CPU Core 0                                |
|  [Registers] <---> [L1 Data Cache (32KB)] <---> [L2 Cache (512KB)]      |
+-------------------------------------------------------------------------+
                                    |
+-------------------------------------------------------------------------+
|                               CPU Core 1                                |
|  [Registers] <---> [L1 Data Cache (32KB)] <---> [L2 Cache (512KB)]      |
+-------------------------------------------------------------------------+
                                    |
                    +-------------------------------+
                    |     Shared L3 Cache (16-32MB) |
                    +-------------------------------+
                                    |
                 +-------------------------------------+
                 | Interconnect (Mesh / UPI / QPI Bus) |
                 +-------------------------------------+
                                    |
                  +-----------------------------------+
                  |        DRAM (Main Memory)         |
                  +-----------------------------------+
```

Setiap core CPU memiliki salinan data lokal di cache. Untuk menjaga konsistensi data di seluruh core, CPU mengeksekusi protokol koherensi cache berbasis bus-snooping, seperti **MESI** (*Modified, Exclusive, Shared, Invalid*):
- **Modified (M)**: Data pada cache line hanya valid di core saat ini dan nilainya *dirty* (berbeda dari DRAM).
- **Exclusive (E)**: Data hanya ada di core saat ini dan sama (*clean*) dengan DRAM.
- **Shared (S)**: Data tersimpan di beberapa cache core dalam kondisi *read-only*.
- **Invalid (I)**: Salinan data usang dan tidak boleh dibaca langsung.

#### False Sharing
Fenomena ini terjadi saat Thread $A$ pada Core 0 memodifikasi variabel `X`, dan Thread $B$ pada Core 1 memodifikasi variabel `Y`. Jika `X` dan `Y` dialokasikan bersebelahan di memori sehingga menempati satu *cache line* 64-byte yang sama, protokol MESI memvalidasi ulang seluruh *cache line* secara bergantian antara Core 0 dan Core 1. Ini memicu *cache line invalidation storm* dan merusak throughput aplikasi meskipun kedua thread tidak mengakses data yang sama secara logis.

### 3.2 Memory Ordering & Fences
Compiler dan CPU out-of-order execution engine secara bebas mengatur ulang urutan instruksi (*instruction reordering*) demi memaksimalkan utilisasi *instruction pipeline*, selama semantik single-thread tidak terganggu. Pada aplikasi multi-threaded, reordering ini menghasilkan pembacaan memori yang anomali.

Model memori modern (C++11 / C11 / Rust) mendefinisikan batas sinkronisasi eksplisit melalui enam tingkat *Memory Ordering*:
1. **`memory_order_relaxed`**: Menjamin atomisitas operasi, tetapi bebas dari ordering constraint relatif terhadap operasi memori lain.
2. **`memory_order_consume`**: Sinkronisasi data-dependency (jarang digunakan langsung; sering kali dipromosikan ke acquire oleh compiler).
3. **`memory_order_acquire`**: Operasi read. Menjamin bahwa seluruh operasi pembacaan dan penulisan memori berikutnya dalam thread yang sama **tidak dapat** di-reorder sebelum operasi acquire ini.
4. **`memory_order_release`**: Operasi write. Menjamin bahwa seluruh operasi pembacaan dan penulisan memori sebelumnya dalam thread yang sama **tidak dapat** di-reorder setelah operasi release ini.
5. **`memory_order_acq_rel`**: Mengombinasikan efek `acquire` dan `release` pada satu operasi Atomic Read-Modify-Write (RMW).
6. **`memory_order_seq_cst`** (*Sequential Consistency*): Model default terketat. Memberikan total sequential order global yang disepakati oleh seluruh thread, membutuhkan *full memory fence/barrier* pada arsitektur tertentu (seperti `MFENCE` di x86).

---

## 4. Why & What

### Mengapa Pendekatan Tradisional (Mutex/Lock) Gagal pada Skala Ekstrim?
- **Pessimistic Locking Overhead**: Penggunaan primitive `pthread_mutex_t` memerlukan transisi *user-space* ke *kernel-space* (melalui `futex` syscall pada Linux) saat terjadi *lock contention*. Biaya context switch berkisar antara 1.000 hingga 1.500 nanodetik per transisi.
- **Priority Inversion**: Thread berprioritas rendah yang memegang lock dapat menghambat thread berprioritas kritis jika thread rendah tersebut ter-preempt oleh OS scheduler.
- **Convoying**: Jika thread pemegang lock ditunda (misal karena page fault atau context switch timeout), thread lain yang mengantre akan terhenti total secara beruntun.

### Apa Solusinya?
- **Lock-Free Concurrency**: Menjamin setidaknya satu thread terus membuat progres (*system-wide progress*) dalam jumlah step tertentu, biasanya menggunakan instruksi CPU atomic hardware seperti Compare-And-Swap (`CAS` / `CMPXCHG`).
- **Wait-Free Concurrency**: Jaminan yang lebih ketat, di mana *setiap* thread dipastikan membuat progres dalam batas operasi tertentu, tanpa memedulikan thread lain.
- **Cache-Aligned Data Structures**: Struktur data yang diselaraskan dengan batas 64 byte menggunakan compiler directives (`alignas(64)`), memisahkan data write-heavy antar-thread untuk mengeliminasi false sharing.
- **Single-Producer Single-Consumer (SPSC) Ring Buffers**: Pola antrean circular bebas lock yang memanfaatkan memory fence acquire-release untuk komunikasi deterministik antar thread.

---

## 5. How (Workflow Detail)

### Workflow Transaksi Lock-Free Ring Buffer (SPSC / Disruptor Pattern)

```
Proses Producer                             Proses Consumer
       |                                           |
       v                                           v
[1. Hitung Next Tail Index]                 [1. Hitung Next Head Index]
       |                                           |
       v                                           v
[2. Baca Head via Relaxed Load]             [2. Baca Tail via Relaxed Load]
       |                                           |
       v                                           v
[3. Apakah Slot Tersedia?]                 [3. Apakah Data Siap?]
   |               |                           |               |
  (Full)         (Tersedia)                  (Empty)         (Tersedia)
   |               |                           |               |
   +-- Spin/Wait   v                           +-- Spin/Wait   v
       [4. Write Data Payload]                     [4. Read Data Payload]
                   |                                           |
                   v                                           v
       [5. Store Tail Atomic]                      [5. Store Head Atomic]
       (memory_order_release)                      (memory_order_release)
```

1. **Producer Head/Tail Invariant**: Producer mempertahankan salinan lokal dari index `head` konsumen untuk meminimalkan pembacaan lintas cache line.
2. **Buffer Capacity Constraints**: Ukuran buffer harus bernilai pangkat dua ($2^n$). Operasi modulo dieksekusi menggunakan bitwise AND mask: `index & (Capacity - 1)` (jauh lebih cepat daripada instruksi CPU `DIV`/`MOD`).
3. **Payload Insertion**: Producer menulis data ke slot array secara langsung tanpa lock.
4. **Publish Barrier**: Nilai atomic pointer/index diperbarui menggunakan store operasi bersemantik `memory_order_release`. Ini memastikan payload data selesai ditulis ke memori fisik sebelum index baru terlihat oleh konsumen.
5. **Consumption Barrier**: Consumer membaca index producer menggunakan `memory_order_acquire`. Data yang terbaca dipastikan valid dan sinkron dengan status saat producer mengeksekusi commit release.

---

## 6. Analogy & Diagram ASCII

### Analogi: Konveyor Pabrik Presisi Tinggi (Lock-Free) vs. Ruang Brankas Satu Kunci (Mutex)
- **Mutex (Ruang Brankas Satu Kunci)**: Pekerja yang ingin meletakkan kotak harus menunggu satpam memberikan kunci tunggal. Jika pekerja di dalam pingsan, pekerja lain berbaris di luar tanpa bisa melakukan apa pun.
- **Lock-Free Ring Buffer (Konveyor Pabrik Berpembatas)**: Konveyor melingkar dengan nomor slot tetap. Operator Masuk (Producer) hanya menaruh barang di slot bernomor urut berikutnya selama slot itu kosong. Operator Keluar (Consumer) mengambil barang dari slot yang sudah terisi. Mereka tidak pernah bersinggungan langsung atau berebut kunci; keduanya hanya melihat posisi penunjuk mekanis masing-masing.

### Diagram: Layout Cache Alignment Ring Buffer
```
+---------------------------------------------------------------+
| CACHE LINE 0 (64 Bytes)                                       |
| - head_index: std::atomic<size_t> (8 bytes)                   |
| - local_tail_cache: size_t        (8 bytes)                   |
| - padding: uint8_t[48]            (48 bytes)                  |
+---------------------------------------------------------------+
| CACHE LINE 1 (64 Bytes)                                       |
| - tail_index: std::atomic<size_t> (8 bytes)                   |
| - local_head_cache: size_t        (8 bytes)                   |
| - padding: uint8_t[48]            (48 bytes)                  |
+---------------------------------------------------------------+
| CACHE LINE 2 ... N                                            |
| - Array of Elements (Diselaraskan per boundary)               |
+---------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Deteksi dan Eliminasi False Sharing (C++20)

```cpp
#include <iostream>
#include <thread>
#include <vector>
#include <chrono>
#include <new>

// STRUKTUR RENTAN: Dua counter berada pada Cache Line yang sama (False Sharing)
struct VulnerableCounters {
    uint64_t counter_a{0}; // 8 byte
    uint64_t counter_b{0}; // 8 byte (Bersebelahan, total 16 byte < 64 byte cache line)
};

// STRUKTUR OPTIMAL: Dipisahkan secara eksplisit ke cache line yang berbeda
struct OptimizedCounters {
    alignas(hardware_destructive_interference_size) uint64_t counter_a{0};
    alignas(hardware_destructive_interference_size) uint64_t counter_b{0};
};

void run_benchmark() {
    constexpr uint64_t ITERATIONS = 500'000'000;

    VulnerableCounters vc;
    auto start = std::chrono::high_resolution_clock::now();
    std::thread t1([&]() {
        for (uint64_t i = 0; i < ITERATIONS; ++i) vc.counter_a++;
    });
    std::thread t2([&]() {
        for (uint64_t i = 0; i < ITERATIONS; ++i) vc.counter_b++;
    });
    t1.join();
    t2.join();
    auto elapsed_vulnerable = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::high_resolution_clock::now() - start).count();

    OptimizedCounters oc;
    start = std::chrono::high_resolution_clock::now();
    std::thread t3([&]() {
        for (uint64_t i = 0; i < ITERATIONS; ++i) oc.counter_a++;
    });
    std::thread t4([&]() {
        for (uint64_t i = 0; i < ITERATIONS; ++i) oc.counter_b++;
    });
    t3.join();
    t4.join();
    auto elapsed_optimized = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::high_resolution_clock::now() - start).count();

    std::cout << "False Sharing Duration: " << elapsed_vulnerable << " ms\n";
    std::cout << "Cache-Aligned Duration: " << elapsed_optimized << " ms\n";
}
```

### 7.2 Practical Example: Production-Ready Lock-Free SPSC Ring Buffer (C++20)

```cpp
#pragma once
#include <atomic>
#include <cstddef>
#include <optional>
#include <vector>
#include <new>
#include <cassert>

template <typename T, size_t Capacity>
class LockFreeSPSCQueue {
    static_assert((Capacity & (Capacity - 1)) == 0, "Kapasitas harus berupa pangkat dua (Power of Two)");
    static_assert(Capacity >= 2, "Kapasitas minimal bernilai 2");

    // Menghindari False Sharing antar thread producer dan consumer
    static constexpr size_t CACHE_LINE_SIZE = 64;

    struct alignas(CACHE_LINE_SIZE) Slot {
        T storage;
    };

    Slot* buffer_;
    static constexpr size_t BUFFER_MASK = Capacity - 1;

    // Cache line milik Producer
    alignas(CACHE_LINE_SIZE) std::atomic<size_t> tail_{0};
    size_t local_head_cache_{0};

    // Cache line milik Consumer
    alignas(CACHE_LINE_SIZE) std::atomic<size_t> head_{0};
    size_t local_tail_cache_{0};

public:
    LockFreeSPSCQueue() : buffer_(new Slot[Capacity]) {}

    ~LockFreeSPSCQueue() {
        delete[] buffer_;
    }

    LockFreeSPSCQueue(const LockFreeSPSCQueue&) = delete;
    LockFreeSPSCQueue& operator=(const LockFreeSPSCQueue&) = delete;

    // Dipanggil secara eksklusif oleh Producer Thread
    template <typename... Args>
    bool emplace(Args&&... args) {
        const size_t current_tail = tail_.load(std::memory_order_relaxed);

        // Periksa apakah antrean penuh menggunakan local_head_cache
        if ((current_tail - local_head_cache_) >= Capacity) {
            // Refresh salinan lokal head_ dari atomic memory
            local_head_cache_ = head_.load(std::memory_order_acquire);
            if ((current_tail - local_head_cache_) >= Capacity) {
                return false; // Antrean penuh
            }
        }

        // Tulis data ke array slot
        new (&buffer_[current_tail & BUFFER_MASK].storage) T(std::forward<Args>(args)...);

        // Publikasikan index ekor baru ke consumer
        tail_.store(current_tail + 1, std::memory_order_release);
        return true;
    }

    // Dipanggil secara eksklusif oleh Consumer Thread
    bool pop(T& destination) {
        const size_t current_head = head_.load(std::memory_order_relaxed);

        // Periksa apakah antrean kosong menggunakan local_tail_cache
        if (current_head == local_tail_cache_) {
            // Refresh salinan lokal tail_ dari atomic memory
            local_tail_cache_ = tail_.load(std::memory_order_acquire);
            if (current_head == local_tail_cache_) {
                return false; // Antrean kosong
            }
        }

        // Baca data dari slot
        destination = std::move(buffer_[current_head & BUFFER_MASK].storage);

        // Publikasikan index kepala baru ke producer
        head_.store(current_head + 1, std::memory_order_release);
        return true;
    }

    [[nodiscard]] size_t size() const noexcept {
        const size_t h = head_.load(std::memory_order_relaxed);
        const size_t t = tail_.load(std::memory_order_relaxed);
        return (t >= h) ? (t - h) : 0;
    }
};
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Arsitektur Matching Engine pada Ultra-Low Latency Crypto/Equities Exchange
- **Skala**: $1.000.000$ order per detik dengan SLA target latency $p99.9 < 15\,\mu\text{s}$.
- **Bottleneck Tradisional**: Desain berbasis Go Channel atau Java ConcurrentLinkedQueue memicu *Garbage Collection Pauses* ($> 5\,\text{ms}$) dan contention lock pada level memory bus, menyebabkan *slippage* harga dan order drop saat volume pasar melonjak tajam (*market rally*).

### Arsitektur Rekayasa Produksi
1. **Network Ingestion (Kernel Bypass)**: Paket jaringan UDP didorong ke ring buffer menggunakan **DPDK (Data Plane Development Kit)** atau **Solarflare OpenOnload**, memotong *kernel TCP/IP stack* dan meniadakan context switch OS.
2. **Threading Topology**:
   - **Core 1 (Pinned)**: *Sequencer / Network Ingestion*. Menulis order mentah ke SPSC Ring Buffer 1.
   - **Core 2 (Pinned)**: *Order Matching Engine*. Mengambil transaksi dari SPSC Ring Buffer 1, mengeksekusi pencocokan di memori L1/L2 secara single-threaded murni tanpa concurrency lock, dan menulis hasil pencocokan (*Execution Reports*) ke SPSC Ring Buffer 2.
   - **Core 3 (Pinned)**: *Journaler / Event Logger*. Mengambil event dari Ring Buffer 2 dan mempersistensikannya ke NVMe drive via `io_uring` dengan flag `O_DIRECT`.

```
[Network Card (NIC)]
         | (Kernel-Bypass via DPDK)
         v
  [Core 1: Ingestion]
         |
         | Lock-Free SPSC Ring Buffer 1 (alignas(64))
         v
  [Core 2: Matching Engine (Deterministic, Single-Threaded)]
         |
         | Lock-Free SPSC Ring Buffer 2 (alignas(64))
         v
  [Core 3: Async Persistence (io_uring O_DIRECT)]
         |
         v
   [NVMe Storage]
```

- **Hasil Pengujian**:
  - $p50$ latency turun dari $42\,\mu\text{s}$ menjadi $1.8\,\mu\text{s}$.
  - $p99.9$ latency terpangkas dari $18\,\text{ms}$ (efek OS interrupt dan lock stall) menjadi $8.4\,\mu\text{s}$.
  - CPU utilization stabil 100% pada core yang di-*pin* (active polling mode tanpa thread sleeping).

---

## 9. Trade-offs

| Parameter | Mutex-Based Queue | Lock-Free CAS Queue (MPMC) | Single-Producer Single-Consumer (SPSC) Ring Buffer |
| :--- | :--- | :--- | :--- |
| **Throughput** | Rendah ($< 5\text{M ops/sec}$) | Menengah ($10-30\text{M ops/sec}$) | Sangat Tinggi ($> 120\text{M ops/sec}$) |
| **Latency Jitter ($p99.9$)** | Sangat Buruk (Tergantung penjadwalan OS Kernel) | Menengah (Tergantung retries loop CAS akibat tabrakan) | Deterministik & Sangat Rendah ($< 1\,\mu\text{s}$) |
| **Penggunaan CPU saat Idle** | Sangat Rendah (Thread masuk status `sleep`/`blocked`) | Bergantung Implementasi (Spin-wait vs Yield) | Tinggi (Active busy-polling mengonsumsi 100% 1 Core) |
| **Kompleksitas Desain** | Sangat Rendah (Primitif bawaan OS/Language) | Ekstrim (Masalah ABA, Memory Reclamation Hazard) | Menengah (Terbatas 1 Thread Prod / 1 Thread Cons) |
| **Skalabilitas Topologi** | Skala Arbitrer | Skala Arbitrer | Harus dipecah menjadi topologi Pipeline / Multi-Ring |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 The ABA Problem pada Desain Lock-Free Node-Based
- **Masalah**: Thread 1 membaca pointer $A$. Thread 2 menyela, membebaskan memory $A$, mengalokasikan memory baru yang kebetulan mendapat alamat fisik sama ($A$), memodifikasi isinya, lalu meletakkan $B$. Thread 1 kembali melanjutkan eksekusi `CAS(pointer, A, New)` dan mendapati nilainya masih $A$. Operasi CAS sukses, tetapi referensi internal struktur memori rusak (*corrupted memory state*).
- **Troubleshooting & Mitigasi**:
  1. Hindari alokasi pointer dinamis pada data path kritis. Gunakan fixed-size pre-allocated Ring Buffers berbasis index integer 64-bit yang berputar (*monotonic counter*), bukan dynamic node pointer.
  2. Gunakan **Double-Word CAS** (DW-CAS) dengan *ABA counter* / tagged pointers (menggabungkan pointer 64-bit dan version counter 64-bit).
  3. Terapkan teknik **Hazard Pointers** atau **Epoch-Based Reclamation (EBR)** sebelum membebaskan memori pada struktur data dinamis lock-free.

### 10.2 Cache Line Bouncing akibat Spin-Wait yang Naif
- **Masalah**: Producer/Consumer memutar CPU pada shared atomic index secara ketat: `while(tail.load(relaxed) == head.load(relaxed)) {}`.
- **Troubleshooting**: Looping terus menerus membanjiri shared bus dengan traffic probe koherensi. Gunakan instruksi intrinsic CPU pause:
  ```cpp
  #if defined(_MSC_VER)
      _mm_pause();
  #elif defined(__GNUC__) || defined(__clang__)
      __builtin_ia32_pause();
  #endif
  ```
  Instruksi `PAUSE` meredam konsumsi daya core, menghindari pipeline clear saat keluar dari loop, serta mengurangi interferensi memory bus.

---

## 11. Best Practices (Production Checklist)

- [ ] **Alokasi Selaras Cache Line**: Pastikan semua shared atomic control variable dipisahkan dengan `alignas(64)` atau compiler attribute `__attribute__((aligned(64)))`.
- [ ] **Bebas Alokasi Memori Dinamis pada Critical Path**: Nol pemanggilan `malloc`, `free`, `new`, atau resizing array dinamis saat thread pemrosesan transaksi berjalan. Alokasikan seluruh buffer di muka (*pre-allocation* saat startup).
- [ ] **CPU Core Pinning (Thread Affinity)**: Gunakan `pthread_setaffinity_np` (Linux) untuk mengunci execution thread pada core fisik mandiri guna mematikan penalti TLB flush dan cache eviction akibat context switch.
- [ ] **Batas Ring Buffer Berpangkat Dua**: Pastikan ukuran array selalu berukuran $2^n$ sehingga pergeseran index memanfaatkan bitwise masking (`& (N - 1)`), menghindari operasi division integer CPU yang memakan 20-40 siklus.
- [ ] **Strict Memory Fences**: Verifikasi bahwa seluruh shared access membaca memori menggunakan `memory_order_acquire` dan mempublikasikan data menggunakan `memory_order_release`. Jangan gunakan `memory_order_seq_cst` di mana tidak diperlukan untuk menghindari full fence instruction overhead (`MFENCE`).
- [ ] **Non-Blocking OS Configuration**: Set flag file descriptor soket jaringan ke `O_NONBLOCK` dan nonaktifkan Nagle's Algorithm via `TCP_NODELAY`.

---

## 12. Hands-on Practice
File pengerjaan disimpan pada direktori: `hands-on/m02/`

### File: `hands-on/m02/spsc_ring_buffer_perf.cpp`

```cpp
#include <iostream>
#include <thread>
#include <vector>
#include <chrono>
#include <atomic>
#include <cassert>

// IMPLEMENTASI MANDIRI: Cache-Aligned Lock-Free Queue
template <typename T, size_t Capacity>
class ProductionSPSCQueue {
    static_assert((Capacity & (Capacity - 1)) == 0, "Capacity must be power of 2");

    alignas(64) T ring_[Capacity];
    
    alignas(64) std::atomic<uint64_t> tail_{0};
    uint64_t local_head_{0};

    alignas(64) std::atomic<uint64_t> head_{0};
    uint64_t local_tail_{0};

public:
    bool push(const T& item) {
        const uint64_t t = tail_.load(std::memory_order_relaxed);
        if ((t - local_head_) >= Capacity) {
            local_head_ = head_.load(std::memory_order_acquire);
            if ((t - local_head_) >= Capacity) {
                return false;
            }
        }
        ring_[t & (Capacity - 1)] = item;
        tail_.store(t + 1, std::memory_order_release);
        return true;
    }

    bool pop(T& item) {
        const uint64_t h = head_.load(std::memory_order_relaxed);
        if (h == local_tail_) {
            local_tail_ = tail_.load(std::memory_order_acquire);
            if (h == local_tail_) {
                return false;
            }
        }
        item = ring_[h & (Capacity - 1)];
        head_.store(h + 1, std::memory_order_release);
        return true;
    }
};

struct MarketData {
    uint64_t order_id;
    double price;
    uint32_t quantity;
};

int main() {
    constexpr size_t CAPACITY = 65536; // 2^16
    constexpr uint64_t TOTAL_MESSAGES = 10'000'000;
    
    auto* queue = new ProductionSPSCQueue<MarketData, CAPACITY>();
    
    std::cout << "Memulai pengujian throughput SPSC Ring Buffer..." << std::endl;
    auto start_time = std::chrono::high_resolution_clock::now();

    std::thread producer([&]() {
        for (uint64_t i = 1; i <= TOTAL_MESSAGES; ++i) {
            MarketData md{i, 100.50 + (i % 10), static_cast<uint32_t>(i % 500)};
            while (!queue->push(md)) {
                #if defined(__x86_64__) || defined(_M_X64)
                __builtin_ia32_pause();
                #endif
            }
        }
    });

    std::thread consumer([&]() {
        uint64_t received = 0;
        MarketData md{};
        while (received < TOTAL_MESSAGES) {
            if (queue->pop(md)) {
                assert(md.order_id == received + 1);
                received++;
            } else {
                #if defined(__x86_64__) || defined(_M_X64)
                __builtin_ia32_pause();
                #endif
            }
        }
    });

    producer.join();
    consumer.join();

    auto end_time = std::chrono::high_resolution_clock::now();
    auto total_ms = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time).count();
    
    double ops_per_sec = (static_cast<double>(TOTAL_MESSAGES) / total_ms) * 1000.0;

    std::cout << "Pengujian Selesai.\n"
              << "Total Pesan: " << TOTAL_MESSAGES << "\n"
              << "Durasi     : " << total_ms << " ms\n"
              << "Throughput : " << static_cast<uint64_t>(ops_per_sec) << " ops/second\n";

    delete queue;
    return 0;
}
```

### Instruksi Kompilasi dan Eksekusi
```bash
# Buat direktori praktikum
mkdir -p hands-on/m02/
cd hands-on/m02/

# Kompilasi dengan optimization flag maksimum (-O3) dan native architecture
g++ -O3 -march=native -std=c++20 spsc_ring_buffer_perf.cpp -o spsc_perf -lpthread

# Jalankan benchmark
./spsc_perf
```

---

## 13. Exercise

### Level Easy
Modifikasi implementasi `LockFreeSPSCQueue` pada contoh praktis di atas agar memiliki method `[[nodiscard]] bool empty() const noexcept` dan `[[nodiscard]] bool full() const noexcept` yang thread-safe dan lock-free tanpa mengubah semantik state internal.

### Level Medium
Kembangkan SPSC Ring Buffer menjadi struktur data **Single-Producer Multi-Consumer (SPMC)**. 
- Petunjuk: Producer tetap menulis secara serial, namun consumer harus bersaing secara aman menggunakan operasi `atomic_compare_exchange_weak` pada index `head`. Analisis dampaknya terhadap performa dibandingkan varian SPSC murni.

### Level Hard
Implementasikan sebuah **Epoch-Based Memory Reclamation (EBR)** manager minimalis untuk struktur data Lock-Free Linked Stack (Treiber Stack).
- Sistem harus mengelola tiga epoch global ($0, 1, 2$) dan mendaftarkan active reader thread ke epoch saat ini.
- Memory node yang di-`pop` tidak boleh langsung di-`delete`, melainkan dimasukkan ke dalam *limbo list* dan hanya di-dealokasi secara fisik ketika seluruh thread telah melewati epoch di mana node tersebut dihapus.

---

## 14. Challenge
**Rancang Arsitektur Multi-Producer Multi-Consumer (MPMC) Disruptor Ring Buffer dengan Dukungan Batch Processing (Open-Ended Architectural Design).**

### Spesifikasi:
1. **Arsitektur Tanpa Dynamic Node**: Buffer harus berupa array flat alokasi tunggal berukuran tetap.
2. **Batch Claims**: Beberapa producer harus dapat memesan (*claim*) rentang indeks secara atomik ($N$ slot sekaligus) menggunakan satu instruksi `fetch_add` pada sequence producer.
3. **Commit Ordering Protocol**: Karena Producer $B$ bisa selesai menulis slot $5-8$ mendahului Producer $A$ yang sedang menulis slot $1-4$, tentukan protokol bagaimana Consumer mengetahui bahwa slot $1-4$ belum valid tanpa blocking OS primitive, sehingga sequence read tidak pernah membaca data yang *stale* (*out-of-order writes resolution*).
4. **Deliverables**:
   - Sketsa Diagram State Transisi Sequence Index.
   - Analisis skenario terburuk (*worst-case contention overhead*) ketika salah satu producer mengalami thread termination di tengah-tengah rentang reservasi.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic
1. Apa ukuran tipikal sebuah *cache line* pada arsitektur prosesor x86/ARM server modern?
2. Mengapa operasi bitwise AND (`index & (Capacity - 1)`) hanya dapat menggantikan operasi modulo (`index % Capacity`) jika ukuran kapasitas merupakan bilangan pangkat dua ($2^n$)?
3. Pada protokol MESI, apa arti status cache line **Invalid (I)**?
4. Apa perbedaan mendasar antara *lock-free* dan *wait-free*?
5. Instruksi assembler CPU apakah yang umumnya dieksekusi oleh mesin x86 untuk mengimplementasikan operasi Atomic Compare-And-Swap?

### 15.2 Pertanyaan Intermediate
1. Mengapa compiler directive `alignas(64)` efektif untuk mengeliminasi fenomena *False Sharing*?
2. Jelaskan bahaya penggunaan model sinkronisasi `std::memory_order_relaxed` ketika memperbarui index flag antrean yang memiliki data payload terkait!
3. Bagaimana instruksi CPU `PAUSE` pada arsitektur x86 mengoptimalkan performa spin-wait loop?
4. Mengapa antrean lock-free tipe MPMC (Multi-Producer Multi-Consumer) umumnya memiliki latensi dan throughput yang jauh lebih inferior dibandingkan dengan SPSC?
5. Mengapa teknik kernel bypass (seperti DPDK/Solarflare OpenOnload) meniadakan *OS context switch overhead*?

### 15.3 Skenario Kasus Produksi
1. **Kasus A**: Sebuah matching engine lock-free memproses $500.000$ event per detik dengan mulus, namun monitor APM mendeteksi lonjakan tail latency ($p99.9$) hingga $50\,\text{ms}$ setiap kali memori sistem menyentuh batas 80%. Setelah diselidiki, swap space tidak aktif. Analisis akar penyebab arsitektural yang mungkin terjadi di level virtual memory dan allocator!
2. **Kasus B**: Dua buah thread di-pin ke Core 0 dan Core 1 pada arsitektur prosesor Dual-Socket NUMA. Thread Core 0 sering membaca memori yang dialokasikan oleh Thread Core 1. Terjadi penurunan performa hingga 300% dibandingkan ketika kedua thread berjalan di Core 0 dan Core 2 (pada soket CPU fisik yang sama). Mekanisme hardware apa yang menjadi bottleneck di sini?
3. **Kasus C**: Seorang engineer menulis implementasi Queue Lock-Free berbasis linked list pointer. Aplikasi berjalan stabil pada unit test lokal, namun saat diuji beban stress-test multi-core 64 thread, sistem mengalami segfault acak pada alamat memori yang valid beberapa mikrodetik sebelumnya. Bug konkurensi klasik apa yang sedang terjadi?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### 15.1 Jawaban Basic
1. 64 byte.
2. Karena jika $C = 2^n$, representasi biner dari $C - 1$ adalah deretan bit $1$ sebanyak $n$ kali (masking penuh untuk sisa bagi rentang $0$ hingga $2^n - 1$).
3. Salinan data di cache line lokal core tersebut sudah usang (*stale*) karena telah dimodifikasi oleh core lain, sehingga core lokal harus membaca ulang dari cache level lebih tinggi atau DRAM.
4. *Lock-free* menjamin setidaknya *satu* thread dari keseluruhan sistem membuat progres (*system-wide progress*), sedangkan *wait-free* menjamin *setiap* thread menyelesaikan operasinya dalam batas step terhingga (*per-thread progress guarantee*).
5. `CMPXCHG` (atau `LOCK CMPXCHG` jika beroperasi lintas core).

#### 15.2 Jawaban Intermediate
1. `alignas(64)` memaksa alamat memori variabel ditempatkan tepat pada kelipatan batas 64 byte, sehingga variabel independen milik thread lain tidak akan berbagi cache line yang sama.
2. `memory_order_relaxed` tidak menyediakan instruction ordering barrier. CPU/compiler dapat memindahkan penulisan data payload *setelah* penulisan index flag antrean, sehingga consumer melihat index baru sebelum data payload selesai ditulis ke memori fisik.
3. Mengurangi latensi de-pipelining loop CPU saat keluar dari spin-wait, meredam konsumsi daya core, dan mencegah interferensi pembebanan memory bus koherensi berlebih.
4. Karena MPMC memicu *cache-coherence thrashing* yang masif: beberapa producer dan consumer terus-menerus memperebutkan atomic update pada head dan tail pointer yang sama via CAS loop retries.
5. Karena adapter card (NIC) memetakan ring buffer paketnya langsung ke *user-space memory* via DMA (Direct Memory Access); aplikasi melakukan polling langsung tanpa melibatkan system call interrupts atau transisi ring-3 ke ring-0.

#### 15.3 Panduan Solusi Skenario Kasus Produksi
1. **Akar Masalah**: Pemicu utamanya adalah **Kernel Page Faults / Page Allocation Stalls**. Ketika memori tersisa sedikit, OS kernel memicu background memory compaction atau zero-page synchronous clearing saat aplikasi meminta page baru secara implisit. Solusi: Gunakan **HugePages (2MB atau 1GB)** yang di-*lock* di memori RAM fisik menggunakan `mlockall()` saat inisialisasi aplikasi untuk mencegah intervensi kernel page reclamation.
2. **Akar Masalah**: **NUMA Interconnect Saturation (QPI / UPI Bottleneck)**. Mengakses memori yang menempel pada memory controller socket fisik CPU lain membutuhkan perjalanan lintas Interconnect Bus (Non-Uniform Memory Access penalty). Solusi: Terapkan alokasi memori lokal NUMA (misal menggunakan API `numactl` atau `libnuma` dengan policy `MPOL_BIND` / `MPOL_PREFERRED`) agar thread hanya memproses data yang dialokasikan di bank DRAM lokal soketnya sendiri.
3. **Akar Masalah**: **The ABA Problem** atau **Dangling Pointer via Race Hazard / Use-After-Free**. Node yang di-pop oleh sebuah thread langsung dibebaskan menggunakan `free()` atau `delete`, sementara thread lain masih memegang pointer lokal ke node tersebut sebelum eksekusi CAS. Solusi: Hentikan alokasi node dinamis; beralih ke fixed-size array Ring Buffer atau terapkan *Epoch-Based Reclamation* (EBR) / *Hazard Pointers*.

---

## 16. Summary
- Pemahaman arsitektur hardware modern (L1/L2/L3 cache, cache line 64-byte, protokol MESI) adalah fondasi mutlak dalam membangun sistem berlatensi sangat rendah (*ultra-low latency*).
- **False Sharing** terjadi ketika variabel mandiri berada dalam satu cache line 64-byte yang sama, memicu degradasi performa drastis akibat cache-invalidation storm.
- Primitive mutex/lock konvensional memperkenalkan degradasi performa signifikan pada skala industri akibat context switch kernel space overhead dan potensi thread convoying.
- Model memori C++11 / modern systems (`memory_order_acquire`, `memory_order_release`) memungkinkan sinkronisasi data payload deterministik pada struktur data *lock-free* tanpa memerlukan instruction fence hardware penuh (`seq_cst`).
- Pola **Single-Producer Single-Consumer (SPSC) Ring Buffer** yang diselaraskan dengan batas memori cache line (`alignas(64)`) menghasilkan struktur pengiriman pesan berkinerja paling optimal di tingkat industri, memproses ratusan juta transaksi per detik dengan latensi sub-mikrodetik.