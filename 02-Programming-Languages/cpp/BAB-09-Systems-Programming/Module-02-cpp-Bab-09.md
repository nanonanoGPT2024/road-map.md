# BAB 09: Systems Programming
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Memitigasi Overhead Kernel Transition:** Mengidentifikasi latensi transisi *user-space* ke *kernel-space* (syscall overhead, TLB shootdown, register saving/restoring) dan merancang mitigasi menggunakan antarmuka asinkronus modern (`io_uring`, *kernel bypass*).
- **Merancang Arsitektur Zero-Copy I/O:** Mengimplementasikan alur transfer data berkecepatan tinggi tanpa redundansi duplikasi data di *memory space* menggunakan kombinasi `mmap`, POSIX shared memory, dan *scatter-gather* vector I/O.
- **Mengembangkan Struktur Data Lock-Free Berbasis Hardware Memory Model:** Mengimplementasikan *Single-Producer Single-Consumer* (SPSC) dan *Multi-Producer Multi-Consumer* (MPMC) *ring buffer* dengan memanfaatkan C++20 atomics, *explicit memory ordering* (`acquire-release`), serta pencegahan *false sharing* berbasis *cache-line alignment*.
- **Mengoptimalkan Determinisme Sistem Terdistribusi/Real-Time:** Mengonfigurasi *NUMA-aware memory allocation*, *CPU pinning/core affinity*, *real-time thread scheduling policies* (`SCHED_FIFO`/`SCHED_DEADLINE`), dan penanganan sinyal asinkronus yang *thread-safe* serta *signal-safe*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **C++20 Fundamentals:** Concepts, Ranges, `std::span`, `std::bit_cast`, dan Modern Move Semantics.
- **Computer Architecture:** Hierarchy Cache (L1/L2/L3), *Cache Coherency Protocols* (MESI/MOESI), *Memory Barrier/Fences*, Page Table, TLB, NUMA nodes, dan Hardware Interrupt Handling.
- **POSIX & Linux Core APIs:** Basic file descriptors, virtual memory primitives (`mmap`, `mprotect`, `munmap`), POSIX threads (`pthread`), dan I/O multiplexing dasar (`epoll`).

---

### 3. Concept & Internal Architecture

#### Virtual Memory Subsystem, Syscall Overhead, dan TLB Dynamics
Pada sistem operasi modern, isolasi memori antara ruang pengguna (*user space*) dan ruang kernel (*kernel space*) dipaksakan melalui tingkat hak akses perangkat keras (*Ring 0* vs *Ring 3* pada arsitektur x86-64).

```
Ring 3 (User Space):    [ Application Execution ]
                                 |  Syscall (e.g., read, write)
---------------------------------|---------------------------------
Trap / Hardware Context Switch   v  (Save RIP, RSP, Flags; Switch CR3/Page Tables)
---------------------------------|---------------------------------
Ring 0 (Kernel Space):   [ System Call Handler ]
                                 |
                         [ VFS / Page Cache ]
                                 |  Direct Memory Access (DMA)
                         [ Hardware Device / NVMe / NIC ]
```

Ketika proses melakukan eksekusi instruksi sistem tradisional (misalnya `read()` atau `write()`):
1. **CPU Trap/Context Switch:** Instruksi `syscall` memicu transisi hak akses dari Ring 3 ke Ring 0. CPU menyimpan registers (RSP, RIP, RFLAGS) ke *kernel stack*, mengganti tumpukan (*stack switching*), dan menjalankan kode handler interrupt.
2. **Double Buffering:** Kernel membaca data dari perangkat keras melalui DMA ke dalam *Kernel Page Cache*, lalu menyalin (*deep copy*) data tersebut melintasi batas ruang alamat ke buffer memori *user space* yang disediakan oleh aplikasi.
3. **TLB Pollution & Cache Invalidation:** Eksekusi kode kernel membuang jalur instruksi dan data pada L1/L2 Cache aplikasi. Jika terjadi *context switch* ke thread kernel lain, *Translation Lookaside Buffer* (TLB) berpotensi mengalami invalidasi parsial, meningkatkan *TLB miss penalty* saat eksekusi kembali ke *user space*.

#### Zero-Copy Architecture & Asynchronous I/O (`io_uring`)
Untuk menembus batas saturasi I/O POSIX standar, Linux memperkenalkan arsitektur Zero-Copy dan antarmuka non-blocking berkinerja tinggi:

1. **Memory-Mapped I/O (`mmap`):** Memetakan file atau perangkat I/O langsung ke ruang alamat virtual proses. Halaman kernel dibagi pakai (*shared*) langsung ke aplikasi, meniadakan duplikasi data antara kernel dan user space buffer.
2. **Linux `io_uring`:** Dirancang untuk meniadakan overhead `syscall` per operasi I/O. `io_uring` menggunakan dua struktur data berbasis antrean *ring buffer* yang dibagi pakai (*shared memory circular buffer*) antara kernel dan aplikasi:
   - **Submission Queue (SQ):** Aplikasi menulis *Submission Queue Entry* (SQE) yang mendeskripsikan operasi I/O tanpa memicu syscall langsung.
   - **Completion Queue (CQ):** Kernel memproses SQE secara asinkron dan menulis *Completion Queue Entry* (CQE) ke antrean selesai.
   - **SQPOLL Mode:** Fitur kernel thread independen yang melakukan *polling* langsung pada SQ. Hasilnya: aplikasi dapat mengirimkan jutaan request I/O dengan **0 kali syscall runtime overhead**.

#### Hardware Memory Model, MESI Protocol, dan False Sharing
Pada sistem Multi-core, setiap *core* memiliki cache L1/L2 lokal, sedangkan L3 dibagi bersama. Untuk menjaga integritas data antar-cache, digunakan protokol *Cache Coherency* seperti MESI (*Modified, Exclusive, Shared, Invalid*).

- **False Sharing:** Terjadi ketika dua thread pada core yang berbeda memodifikasi variabel independen yang berada di dalam satu *Cache Line* fisik yang sama (umumnya 64 byte pada x86-64/ARM64). Modifikasi dari Core A memaksa invalidasi (*Invalid state*) seluruh Cache Line pada Core B, menyebabkan *bus traffic storm* dan degradasi latensi hingga hitungan orde magnitudo.
- **Pencegahan:** Penggunaan direktif *alignment* compiler C++ modern:
  ```cpp
  alignas(std::hardware_destructive_interference_size) std::atomic<uint64_t> write_head;
  ```

---

### 4. Why & What

| Dimensi | Pendekatan POSIX Konvensional (`read`/`write`/`epoll`) | Pendekatan Enterprise Systems Programming Modern |
| :--- | :--- | :--- |
| **Mekanisme Eksekusi** | Sinkron/Reaktif berbasis event notification (`epoll_wait` + `syscall`) | Proaktif berbasis asynchronous completion ring (`io_uring`) / Memory Sharing |
| **Data Copying** | Minimal 2x copy (Hardware -> Kernel Buffer -> User Buffer) | **Zero-Copy** (Direct User DMA / Mapped Ring Buffer) |
| **Syscall Overhead** | 1 syscall per batch/buffer data ($O(N)$ interupsi kernel) | Amortisasi syscall mendekati nol ($O(1)$ atau polling murni via `IORING_SETUP_SQPOLL`) |
| **Memory Locality** | Arbitrary memory allocation, rentan *cross-node NUMA traversal* | NUMA-pinned memory, HugePages pre-allocated (2MB/1GB pages) |
| **Sinkronisasi Antar Thread** | OS-level Mutex / Semaphores (Block, sleep, context switch) | Lock-Free Atomics (`std::memory_order_acquire/release`), Wait-Free Ring Buffers |

---

### 5. How (Workflow detail)

```
[ Producer Thread (Core 1) ]             [ Shared Ring Buffer (NUMA Node 0) ]            [ Consumer Thread (Core 2) ]
              |                                        |                                        |
  1. Load tail (Acquire)                               |                                        |
              |--------------------------------------->|                                        |
  2. Reserve slots (Local CAS/Compute)                 |                                        |
              |                                        |                                        |
  3. Write data payloads                               |                                        |
              |=======================================>| [Slot Index X]                         |
              |                                        |                                        |
  4. Advance head (Release)                            |                                        |
              |--------------------------------------->|                                        |
                                                       |                                1. Load head (Acquire)
                                                       |<---------------------------------------|
                                                       |                                2. Read data payloads
                                                       |<=======================================|
                                                       |                                3. Advance tail (Release)
                                                       |<---------------------------------------|
```

1. **Inisialisasi Shared Topology:** Alokasikan memori terkelola menggunakan `mmap` dengan flag `MAP_SHARED | MAP_ANONYMOUS | MAP_HUGETLB`.
2. **Affinity Mapping:** Kunci affinity thread produsen ke Core 1 dan konsumen ke Core 2 menggunakan `pthread_setaffinity_np()`.
3. **Data Reservation:** Produsen memvalidasi ketersediaan ruang antrean menggunakan pointer lokal untuk meminimalkan beban baca variabel atomik.
4. **Memory Barrier Publishing:** Saat muatan data (*payload*) selesai ditulis, update pointer `head` menggunakan `std::memory_order_release`. Ini memastikan penulisan data dijamin terlihat oleh core lain sebelum pointer indeks terbarui.
5. **Consumption Synchronization:** Konsumen membaca pointer `head` menggunakan `std::memory_order_acquire`, memproses payload, lalu memperbarui pointer `tail` dengan `std::memory_order_release`.

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
Bayangkan mekanisme I/O konvensional sebagai loket kantor pos manual: Setiap kali Anda ingin mengirim surat (data), Anda harus mengantre, meminta petugas stempel (kernel trap), petugas menyalin dokumen Anda ke formulir internal mereka (kernel copy), lalu mengirimkannya.

Sebaliknya, arsitektur modern berbasis Shared Ring Buffer dan `io_uring` diibaratkan sebagai ban berjalan (*conveyor belt*) mekanis privat: Anda meletakkan paket langsung ke atas ban berjalan yang melintas antara gedung Anda dan terminal kargo. Tanpa perlu berbicara dengan petugas atau meminta izin berulang kali, ban berjalan berputar secara independen.

#### Diagram Arsitektur: Dual-Ring Low Latency Subsystem

```
+=============================================================================+
|                                USER SPACE                                   |
|                                                                             |
|  +--------------------+                     +--------------------+          |
|  |  Producer Process  |                     |  Consumer Process  |          |
|  |  (Core Pin: CPU 2) |                     |  (Core Pin: CPU 4) |          |
|  +---------+----------+                     +----------^---------+          |
|            |                                           |                    |
|            | Write Data                                | Read Data          |
|            v                                           |                    |
|  +-----------------------------------------------------+-----------------+  |
|  |           Lock-Free Circular Ring Buffer (Shared Memory)              |  |
|  |                                                                       |  |
|  |  [Slot 0] [Slot 1] [Slot 2] [Slot 3] ... [Slot N-1]                   |  |
|  |                                                                       |  |
|  |  alignas(64) std::atomic<uint64_t> head; // Cache Line A              |  |
|  |  alignas(64) std::atomic<uint64_t> tail; // Cache Line B              |  |
|  +-----------------------------------------------------------------------+  |
|            |                                           ^                    |
|            | io_uring_enter (Optional / SQPOLL)        | Kernel Completions |
+============|===========================================|====================+
|            v                                           |                    |
|  +-------------------+                       +-------------------+          |
|  |  io_uring SQ Ring |                       |  io_uring CQ Ring |          |
|  |  (Submission)     |                       |  (Completion)     |          |
|  +---------+---------+                       +---------^---------+          |
|            |                                           |                    |
|            +------------------->[ KERNEL ]-------------+                    |
|                                (NVMe / NIC)                                 |
+=============================================================================+
```

---

### 7. Simple Example & Practical Example

#### Simple Example: RAII POSIX Shared Memory Wrapper
Contoh dasar yang mengkapsulasi alokasi POSIX Shared Memory secara deterministik menggunakan paradigma RAII dan C++20.

```cpp
#include <iostream>
#include <string_view>
#include <system_error>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <span>

class SharedMemorySegment {
public:
    SharedMemorySegment(std::string_view name, size_t size, bool create = false)
        : name_(name), size_(size) {
        int flags = create ? (O_CREAT | O_RDWR | O_TRUNC) : O_RDWR;
        fd_ = ::shm_open(name_.data(), flags, 0660);
        if (fd_ == -1) {
            throw std::system_error(errno, std::generic_category(), "shm_open failed");
        }

        if (create) {
            if (::ftruncate(fd_, static_cast<off_t>(size_)) == -1) {
                ::close(fd_);
                ::shm_unlink(name_.data());
                throw std::system_error(errno, std::generic_category(), "ftruncate failed");
            }
        }

        void* addr = ::mmap(nullptr, size_, PROT_READ | PROT_WRITE, MAP_SHARED, fd_, 0);
        if (addr == MAP_FAILED) {
            ::close(fd_);
            if (create) ::shm_unlink(name_.data());
            throw std::system_error(errno, std::generic_category(), "mmap failed");
        }

        data_ = static_cast<std::byte*>(addr);
    }

    ~SharedMemorySegment() {
        if (data_ && data_ != MAP_FAILED) {
            ::munmap(data_, size_);
        }
        if (fd_ != -1) {
            ::close(fd_);
        }
    }

    SharedMemorySegment(const SharedMemorySegment&) = delete;
    SharedMemorySegment& operator=(const SharedMemorySegment&) = delete;

    SharedMemorySegment(SharedMemorySegment&& other) noexcept 
        : name_(other.name_), size_(other.size_), fd_(other.fd_), data_(other.data_) {
        other.fd_ = -1;
        other.data_ = nullptr;
    }

    [[nodiscard]] std::span<std::byte> AsSpan() noexcept {
        return {data_, size_};
    }

private:
    std::string_view name_;
    size_t size_;
    int fd_{-1};
    std::byte* data_{nullptr};
};

int main() {
    try {
        constexpr size_t SHM_SIZE = 4096;
        SharedMemorySegment shm("/demo_shm_block", SHM_SIZE, true);
        auto span = shm.AsSpan();
        span[0] = static_cast<std::byte>(0xAB);
        std::cout << "Successfully allocated and wrote to SHM. Byte 0: " 
                  << std::hex << static_cast<int>(span[0]) << '\n';
        ::shm_unlink("/demo_shm_block");
    } catch (const std::exception& ex) {
        std::cerr << "Fatal Error: " << ex.what() << '\n';
        return 1;
    }
    return 0;
}
```

#### Practical Example: High-Throughput Lock-Free SPSC Ring Buffer
Implementasi antrean circular ring buffer deterministik ultra-low latency, bebas lock (*lock-free*), terhindar dari *false sharing*, dan memanfaatkan arsitektur C++20 standard atomics dengan *explicit memory barrier*.

```cpp
#include <iostream>
#include <array>
#include <atomic>
#include <optional>
#include <thread>
#include <vector>
#include <new>
#include <cstdint>
#include <cassert>

#if defined(__cpp_lib_hardware_interference_size)
    using std::hardware_destructive_interference_size;
#else
    constexpr size_t hardware_destructive_interference_size = 64;
#endif

template <typename T, size_t Capacity>
requires (Capacity > 1) && ((Capacity & (Capacity - 1)) == 0) // Validasi bitwise: Wajib perpangkatan 2
class LockFreeSPSCQueue {
public:
    static constexpr size_t BufferMask = Capacity - 1;

    LockFreeSPSCQueue() : head_(0), tail_(0), cached_tail_(0), cached_head_(0) {}

    ~LockFreeSPSCQueue() = default;
    LockFreeSPSCQueue(const LockFreeSPSCQueue&) = delete;
    LockFreeSPSCQueue& operator=(const LockFreeSPSCQueue&) = delete;

    template <typename... Args>
    bool Emplace(Args&&... args) noexcept(std::is_nothrow_constructible_v<T, Args...>) {
        const size_t current_head = head_.load(std::memory_order_relaxed);
        
        // Optimasi: Validasi ruang menggunakan cached tail untuk menghindari cross-core bus transaction
        if ((current_head - cached_tail_) == Capacity) {
            cached_tail_ = tail_.load(std::memory_order_acquire);
            if ((current_head - cached_tail_) == Capacity) {
                return false; // Queue Penuh
            }
        }

        buffer_[current_head & BufferMask] = T(std::forward<Args>(args)...);
        
        // Publikasikan item ke konsumen: Release memaksakan operasi store data selesai sebelum head bertambah
        head_.store(current_head + 1, std::memory_order_release);
        return true;
    }

    bool Pop(T& out_value) noexcept(std::is_nothrow_move_assignable_v<T>) {
        const size_t current_tail = tail_.load(std::memory_order_relaxed);

        // Optimasi: Validasi ketersediaan menggunakan cached head
        if (current_tail == cached_head_) {
            cached_head_ = head_.load(std::memory_order_acquire);
            if (current_tail == cached_head_) {
                return false; // Queue Kosong
            }
        }

        out_value = std::move(buffer_[current_tail & BufferMask]);
        
        // Rilis slot ke produsen
        tail_.store(current_tail + 1, std::memory_order_release);
        return true;
    }

    [[nodiscard]] size_t ApproximateSize() const noexcept {
        const size_t h = head_.load(std::memory_order_relaxed);
        const size_t t = tail_.load(std::memory_order_relaxed);
        return (h >= t) ? (h - t) : (Capacity - (t - h));
    }

private:
    // Slot memori penyimpanan
    std::array<T, Capacity> buffer_{};

    // Alokasikan variabel atomik pada cache line terpisah untuk membasmi False Sharing
    alignas(hardware_destructive_interference_size) std::atomic<size_t> head_;
    alignas(hardware_destructive_interference_size) size_t cached_tail_;

    alignas(hardware_destructive_interference_size) std::atomic<size_t> tail_;
    alignas(hardware_destructive_interference_size) size_t cached_head_;
};

struct MarketTick {
    uint64_t timestamp_ns;
    uint32_t symbol_id;
    double price;
    uint32_t volume;
};

int main() {
    constexpr size_t QUEUE_CAPACITY = 1024; // Power of two
    static LockFreeSPSCQueue<MarketTick, QUEUE_CAPACITY> tick_queue;
    constexpr size_t TOTAL_MESSAGES = 1'000'000;

    std::thread producer([]() {
        for (size_t i = 0; i < TOTAL_MESSAGES; ++i) {
            MarketTick tick{1690000000000ULL + i, 101, 150.25 + (i % 10), static_cast<uint32_t>(i * 5)};
            while (!tick_queue.Emplace(tick)) {
                // Bus loop-back / PAUSE instruction to prevent pipeline flush
                #if defined(__x86_64__) || defined(_M_X64)
                __builtin_ia32_pause();
                #endif
            }
        }
    });

    std::thread consumer([]() {
        size_t consumed_count = 0;
        MarketTick received_tick{};
        while (consumed_count < TOTAL_MESSAGES) {
            if (tick_queue.Pop(received_tick)) {
                ++consumed_count;
            } else {
                #if defined(__x86_64__) || defined(_M_X64)
                __builtin_ia32_pause();
                #endif
            }
        }
        std::cout << "Consumer finished processing " << consumed_count 
                  << " ticks. Last price: " << received_tick.price << '\n';
    });

    producer.join();
    consumer.join();

    return 0;
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Ultra-Low Latency Market Data Gateway (HFT)
- **Konteks:** Perusahaan prop trading memproses data feed L2 dari Bursa Efek (UDP Multicast) dengan kecepatan rata-rata 12 juta pesan/detik pada jam sibuk, dengan SLA latensi P99.99 di bawah 800 nanodetik.
- **Masalah:** Pendekatan arsitektur socket BSD POSIX tradisional (`epoll` + `recvmsg`) mengalami degradasi kinerja parah. Latensi P99 melonjak hingga 45 mikrodetik selama volatilitas pasar tinggi. Analisis `perf` menunjukkan:
  - 42% siklus CPU terbuang untuk kernel execution, TLB shootdown, dan *spin-lock contention* pada socket buffer internal OS.
  - *Context switching* sukarela mencapai 450.000 kali per detik.
- **Solusi Arsitektur:**
  1. **Kernel-Bypass Networking:** Migrasi ke solarflare Onload / DPDK framework dengan ring buffer memori bersama yang dipetakan melalui *huge pages* (2MB allocation).
  2. **Core Isolation & Pinning:** Mengisolasi Core CPU 2, 4, 6 menggunakan isolcpus di kernel Linux boot parameter (`isolcpus=2,4,6 nohz_full=2,4,6 rcu_nocbs=2,4,6`), memastikan tidak ada *timer interrupt tick* kernel yang mengganggu eksekusi pemrosesan data feed.
  3. **Zero-Allocation SPSC Pipeline:** Data mentah langsung diparsing pada buffer DMA RX ring hardware, dipindahkan ke Lock-Free SPSC Ring Buffer berbasis zero-copy, dan langsung dievaluasi oleh *algorithmic execution engine*.
- **Hasil Terukur:** Latensi P99.99 terpangkas secara konstan menjadi **620 nanodetik**, dengan penurunan *packet drop rate* menjadi **0.00%** pada beban puncak data feed 15 juta paket/detik.

---

### 9. Trade-offs

| Pendekatan / Pola | Keuntungan | Kerugian & Batasan | Rekomendasi Penggunaan |
| :--- | :--- | :--- | :--- |
| **Traditional Syscalls (`read`/`write`/`epoll`)** | Sederhana, portabel antar standar POSIX, *memory footprint* minimal pada beban rendah. | Syscall overhead masif, *context-switch penalties*, duplikasi data memori kernel-user. | Aplikasi umum berorientasi throughput standar (<100K IOPS) atau koneksi I/O masif bertipe idle. |
| **Asynchronous I/O (`io_uring`)** | Throughput sangat masif (>1.5M IOPS), minim context switch, kapabilitas *zero-copy* native. | Kompleksitas debugging tinggi, dependensi kernel Linux modern (>= 5.10+), rentan *security exploits* jika konfigurasi unprivileged salah. | Server penyimpanan data terdistribusi berkecepatan tinggi, database engines, event loop jaringan performa tinggi. |
| **Lock-Free Atomic Queues** | Determinisme nanodetik, tidak ada thread suspensi (*zero OS scheduling delay*). | Sulit diimplementasikan dengan benar (rentan bugs *ABA*, *memory reordering*), keterbatasan struktur (*fixed capacity* atau SPSC). | Alur komunikasi intra-host berlatensi rendah, sistem audio real-time, High-Frequency Trading. |
| **Kernel Bypass (DPDK/Solarflare EF_VI)** | Menghilangkan perantara kernel sepenuhnya (0 context switch overhead, direct PCI access). | Memerlukan hardware kartu jaringan khusus (NIC), konsumsi 100% core CPU akibat *continuous polling*, stack TCP/IP harus ditulis/dikelola mandiri di *user-space*. | Ultra-Low Latency Trading, Deep Packet Inspection (DPI) skala Telekomunikasi. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Masalah: False Sharing pada Alokasi Kontigu
- **Penyebab:** Mendeklarasikan variabel sinkronisasi antar-thread secara berdampingan dalam satu struktur tanpa penyelarasan batas memori (*cache-line boundary*).
- **Deteksi:** Jalankan profiler perangkat keras:
  ```bash
  perf c2c record -- ./binary_target
  perf c2c report --stdio
  ```
  Jika metrik `HITM` (Hit Modified Cache) tinggi, terjadi *false sharing*.
- **Solusi:** Selaraskan variabel secara eksplisit menggunakan `alignas(hardware_destructive_interference_size)`.

#### 2. Masalah: Kerusakan Memori Akibat `SIGBUS` pada File Terpangkas (`mmap`)
- **Penyebab:** Membaca atau menulis alamat virtual yang dipetakan via `mmap` setelah file underlying dipangkas (*truncated*) oleh proses eksternal.
- **Deteksi:** Program *crash* seketika dengan sinyal fatal `SIGBUS (Bus error - core dumped)`.
- **Solusi:** Pasang penanganan sinyal `SIGBUS` menggunakan `sigaction` dengan flag `SA_SIGINFO` untuk mengisolasi alamat pelanggaran (`si_addr`), atau pastikan validasi ketat `posix_fallocate()` dilakukan sebelum mapping.

#### 3. Masalah: Memory Reordering Bugs Akibat Salah Penggunaan `std::memory_order_relaxed`
- **Penyebab:** Menggunakan `memory_order_relaxed` untuk menerbitkan pointer ke data yang baru diisi. Perangkat keras memori out-of-order (misalnya ARM64) berhak menukar urutan penulisan data payload dan variabel publish pointer.
- **Deteksi:** Konsumen sesekali membaca data null atau data sampah (*garbage values*) meskipun penanda status mengindikasikan data sudah siap.
- **Solusi:** Selalu pasangkan `std::memory_order_release` pada pihak produsen (*store*) dan `std::memory_order_acquire` pada pihak konsumen (*load*).

---

### 11. Best Practices (Production Checklist)

- [ ] **Hardware Alignment:** Seluruh struktur data lock-free dan pointer yang diakses bersama antar-core telah divalidasi memiliki alignment `64 bytes` (atau sesuai `std::hardware_destructive_interference_size`).
- [ ] **Zero-Allocation Execution Path:** Runtime loop utama tidak memanggil `malloc`, `free`, `new`, atau `delete`. Semua alokasi memori diselesaikan pada fase startup sistem.
- [ ] **Memory Locking (`mlock`):** Halaman memori kritis di-*pin* menggunakan `mlockall(MCL_CURRENT | MCL_FUTURE)` untuk mencegah OS menukar (*swap out*) halaman memori ke disk.
- [ ] **Explicit Memory Ordering:** Tidak menggunakan operasi atomik *default* (`std::memory_order_seq_cst`) secara serampangan. Terapkan `acquire-release semantics` untuk memangkas *bus synchronization penalty*.
- [ ] **CPU Pinning & NUMA Interleaving:** Setiap thread pemrosesan terikat pada core CPU fisik terisolasi melalui `pthread_setaffinity_np()`, dan alokasi memori lokal terikat pada NUMA node yang bersangkutan (`numactl --membind` / `numa_alloc_onnode`).
- [ ] **Proper Signal Masking:** Sinyal asynchronous OS (misal `SIGINT`, `SIGTERM`, `SIGHUP`) diblokir pada seluruh *worker threads* menggunakan `pthread_sigmask()`, dan ditangani secara tersentralisasi pada thread *dedicated* melalui `sigwaitinfo()`.
- [ ] **HugePages Enforcement:** Alokasikan buffer data masif menggunakan `MAP_HUGETLB` (2MB atau 1GB HugePages) untuk mereduksi footprint *Page Table* dan meminimalkan *TLB misses*.

---

### 12. Hands-on Practice

Berikut panduan langkah demi langkah implementasi *Zero-Copy Shared Memory Ring Buffer IPC Engine* antar dua proses independen.

#### Struktur Direktori
```text
hands-on/m02/
├── CMakeLists.txt
├── include/
│   └── shared_ring.hpp
└── src/
    ├── consumer.cpp
    └── producer.cpp
```

#### File: `hands-on/m02/include/shared_ring.hpp`
```cpp
#pragma once
#include <atomic>
#include <cstdint>
#include <cstddef>
#include <new>

#if defined(__cpp_lib_hardware_interference_size)
    using std::hardware_destructive_interference_size;
#else
    constexpr size_t hardware_destructive_interference_size = 64;
#endif

constexpr size_t RING_CAPACITY = 2048; // Must be power of 2
constexpr size_t RING_MASK = RING_CAPACITY - 1;

struct alignas(64) IPCEvent {
    uint64_t sequence;
    uint64_t timestamp;
    char payload[112];
};

struct alignas(hardware_destructive_interference_size) SharedControlBlock {
    alignas(hardware_destructive_interference_size) std::atomic<uint64_t> head;
    alignas(hardware_destructive_interference_size) std::atomic<uint64_t> tail;
    alignas(hardware_destructive_interference_size) std::atomic<bool> is_running;
    IPCEvent slots[RING_CAPACITY];
};
```

#### File: `hands-on/m02/src/producer.cpp`
```cpp
#include "shared_ring.hpp"
#include <iostream>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <chrono>
#include <cstring>

int main() {
    const char* shm_name = "/enterprise_ipc_ring";
    int fd = ::shm_open(shm_name, O_CREAT | O_RDWR | O_TRUNC, 0666);
    if (fd == -1) {
        perror("shm_open");
        return 1;
    }

    size_t total_size = sizeof(SharedControlBlock);
    if (::ftruncate(fd, total_size) == -1) {
        perror("ftruncate");
        return 1;
    }

    void* addr = ::mmap(nullptr, total_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (addr == MAP_FAILED) {
        perror("mmap");
        return 1;
    }

    auto* scb = new (addr) SharedControlBlock();
    scb->head.store(0, std::memory_order_relaxed);
    scb->tail.store(0, std::memory_order_relaxed);
    scb->is_running.store(true, std::memory_order_relaxed);

    std::cout << "[Producer] Engine ready. Commencing 5,000,000 zero-copy events pipeline...\n";

    constexpr uint64_t TOTAL_EVENTS = 5'000'000;
    auto start_time = std::chrono::steady_clock::now();

    for (uint64_t i = 1; i <= TOTAL_EVENTS; ++i) {
        uint64_t current_head = scb->head.load(std::memory_order_relaxed);
        
        while ((current_head - scb->tail.load(std::memory_order_acquire)) == RING_CAPACITY) {
            #if defined(__x86_64__)
            __builtin_ia32_pause();
            #endif
        }

        IPCEvent& event = scb->slots[current_head & RING_MASK];
        event.sequence = i;
        event.timestamp = std::chrono::steady_clock::now().time_since_epoch().count();
        std::memcpy(event.payload, "DATA_PACKET_ENTERPRISE_STREAM", 30);

        scb->head.store(current_head + 1, std::memory_order_release);
    }

    auto end_time = std::chrono::steady_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time).count();
    std::cout << "[Producer] Emitted " << TOTAL_EVENTS << " events in " << duration << " ms.\n";

    while (scb->tail.load(std::memory_order_acquire) < TOTAL_EVENTS) {
        usleep(1000);
    }

    scb->is_running.store(false, std::memory_order_release);
    ::munmap(addr, total_size);
    ::close(fd);
    return 0;
}
```

#### File: `hands-on/m02/src/consumer.cpp`
```cpp
#include "shared_ring.hpp"
#include <iostream>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <chrono>

int main() {
    const char* shm_name = "/enterprise_ipc_ring";
    int fd = -1;
    
    std::cout << "[Consumer] Waiting for shared memory region to be established...\n";
    while ((fd = ::shm_open(shm_name, O_RDWR, 0666)) == -1) {
        usleep(50000);
    }

    size_t total_size = sizeof(SharedControlBlock);
    void* addr = ::mmap(nullptr, total_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (addr == MAP_FAILED) {
        perror("mmap");
        return 1;
    }

    auto* scb = reinterpret_cast<SharedControlBlock*>(addr);
    uint64_t processed_events = 0;

    std::cout << "[Consumer] Attached to shared region. Reading events...\n";

    while (scb->is_running.load(std::memory_order_acquire) || 
           (scb->tail.load(std::memory_order_relaxed) < scb->head.load(std::memory_order_relaxed))) {
        
        uint64_t current_tail = scb->tail.load(std::memory_order_relaxed);
        
        if (current_tail == scb->head.load(std::memory_order_acquire)) {
            #if defined(__x86_64__)
            __builtin_ia32_pause();
            #endif
            continue;
        }

        const IPCEvent& event = scb->slots[current_tail & RING_MASK];
        if (event.sequence != (processed_events + 1)) {
            std::cerr << "[Consumer] Sequence mismatch detected! Expected " 
                      << processed_events + 1 << " but got " << event.sequence << '\n';
        }

        ++processed_events;
        scb->tail.store(current_tail + 1, std::memory_order_release);
    }

    std::cout << "[Consumer] Successfully received and verified " << processed_events << " events.\n";

    ::munmap(addr, total_size);
    ::close(fd);
    ::shm_unlink(shm_name);
    return 0;
}
```

#### File: `hands-on/m02/CMakeLists.txt`
```cmake
cmake_minimum_required(VERSION 3.20)
project(HighPerformanceIPC CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -Wall -Wextra -Wpedantic -pthread")

include_directories(include)

add_executable(producer src/producer.cpp)
target_link_libraries(producer rt pthread)

add_executable(consumer src/consumer.cpp)
target_link_libraries(consumer rt pthread)
```

#### Instruksi Eksekusi
```bash
# 1. Navigasi ke direktori hands-on
cd hands-on/m02

# 2. Build aplikasi
mkdir build && cd build
cmake ..
make -j$(nproc)

# 3. Jalankan Consumer di terminal pertama (atau background)
./consumer &

# 4. Jalankan Producer di terminal utama
./producer
```

---

### 13. Exercise

#### Level Easy
- **Tugas:** Modifikasi `LockFreeSPSCQueue` pada contoh praktis agar mendukung metode `bool Flush()` yang mengosongkan seluruh antrean saat ini dan mengembalikan jumlah item yang dibuang.
- **Batasan:** Tetap pertahankan prinsip strictly thread-safe bagi satu produsen dan satu konsumen tanpa menambahkan mutex.

#### Level Medium
- **Tugas:** Tambahkan dukungan *Scatter-Gather Vectorized I/O* pada modul producer IPC menggunakan sistem panggilan `vmsplice()` atau `process_vm_writev()` untuk mentransfer data memori arbitrer ke proses target tanpa melalui mapping file berulang.
- **Kriteria Evaluasi:** Nilai P99 latency transfer payload 64KB tidak boleh melebihi 3 mikrodetik pada pengujian lokal.

#### Level Hard
- **Tugas:** Kembangkan arsitektur *Multi-Producer Single-Consumer (MPSC)* Ring Buffer berkapasitas tetap menggunakan C++20 atomics.
- **Batasan:** Produsen majemuk harus menyelesaikan konflik pemesanan slot indeks circular buffer menggunakan instruksi `atomic_compare_exchange_weak` pada `head`, namun penulisan data payload dan publikasi ketersediaan data tidak boleh menyebabkan pembacaan data parsial (*torn reads*) oleh konsumen tunggal.

---

### 14. Challenge

**Skenario Rekayasa:** Anda ditugaskan membangun komponen *Write-Ahead Logging (WAL) Storage Subsystem* untuk mesin database terdistribusi berbasis C++20 yang mampu menulis transaksi secara persisten ke NVMe Storage dengan target throughput 2.000.000 IOPS pada latency sub-15 mikrodetik.

**Kebutuhan Sistem & Spesifikasi Teknis:**
1. **Direct NVMe Access:** Wajib menggunakan Linux `io_uring` dengan registrasi buffer statis (`io_uring_register_buffers`) dan registrasi fixed file descriptors (`IORING_REGISTER_FILES`) untuk meniadakan mapping page kernel di setiap I/O write.
2. **Crash-Consistency Determinism:** Gunakan flag `O_DIRECT | O_SYNC` untuk memotong OS Page Cache sepenuhnya.
3. **Double-Buffering Circular Pipeline:** Rancang pipeline pengisian buffer log in-memory dan submission async-write ke drive sehingga thread transaksi tidak pernah terblokir menunggu *NVMe write acknowledgement*.
4. **Deteksi Hardware Tear-Down:** Implementasikan validasi *checksum block integrity* (CRC32C menggunakan SSE4.2/AVX hardware intrinsics) pada setiap sektor 4KB sebelum operasi asynchronous submit dipicu.

*Tantangan ini menuntut arsitektur tingkat rendah tanpa framework pembungkus pihak ketiga; hanya menggunakan C++20 standard library dan interface Linux native `liburing`.*

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Questions
1. Mengapa operasi `mmap()` jauh lebih efisien untuk transfer file masif berulang dibandingkan rangkaian sistem panggilan `read()` dan `write()`?
2. Berapa ukuran tipikal satu *Cache Line* pada arsitektur x86-64 kontemporer, dan mengapa konstanta ini krusial saat merancang struktur data atomik bersama?
3. Apa konsekuensi fatal jika aplikasi memodifikasi buffer memori yang baru saja diserahkan ke antrean `io_uring` sebelum *Completion Queue Entry* (CQE) diterima?
4. Apa fungsi dari instruksi `mlock()` dalam komputasi sistem real-time?
5. Mengapa tipe data `std::atomic<T>` belum tentu berstatus *lock-free* secara hardware untuk sembarang tipe data `T`?

#### Intermediate Questions
1. Jelaskan perbedaan mendasar antara *Memory Ordering* `std::memory_order_relaxed`, `std::memory_order_acquire`, dan `std::memory_order_release` dalam kaitannya dengan pipeline instruksi CPU dan visibilitas cache.
2. Bagaimana mekanisme kerja `io_uring` dengan opsi `IORING_SETUP_SQPOLL` dapat mengeliminasi transisi *Ring 3 -> Ring 0* sepenuhnya selama runtime I/O aktif?
3. Mengapa teknik isolasi *CPU Core Pinning* (`sched_setaffinity`) dapat meningkatkan performa secara drastis pada sistem *Low-Latency*, dan apa trade-off yang harus dibayar dari perspektif OS thread scheduling?
4. Jelaskan apa yang dimaksud dengan fenomena *False Sharing*, jelaskan bagaimana hal tersebut dapat dideteksi via hardware counters, dan sebutkan teknik pencegahannya di C++20.
5. Bagaimana implementasi alokasi *HugePages* (2MB/1GB) secara langsung memengaruhi efisiensi kerja *Translation Lookaside Buffer* (TLB) pada beban pemrosesan Big Data in-memory?

#### Production Scenarios
1. **Skenario:** Mesin trading Anda mengalami spike latensi mendadak (hingga puluhan milidetik) setiap 5 menit sekali, bertepatan dengan OS melakukan *page flushing* data kotor ke disk. Bagaimana Anda mengonfigurasi memori sistem dan parameter kernel Linux untuk mengisolasi proses kritis Anda dari interupsi OS dirty-page writeback?
2. **Skenario:** Sebuah aplikasi SPSC IPC Ring Buffer yang berjalan lancar di workstation Intel x86-64 mengalami korupsi data intermiten ketika di-deploy ke server komputasi berbasis ARM64 (misalnya AWS Graviton). Tidak ada error kompilasi yang muncul. Apa akar penyebab hardware-level masalah ini dan bagaimana memperbaikinya di kode C++?
3. **Skenario:** Service consumer membaca data dari shared memory yang dipetakan oleh proses producer. Tiba-tiba proses producer mengalami crash fatal (`SIGKILL`). Konsumen mengalami deadlock/infinite loop saat memproses data transaksi terakhir. Rancang mekanisme recovery deterministik yang tahan terhadap crash produsen seketika tanpa menggunakan lock OS mutex tradisional.

---

### Kunci Jawaban & Evaluasi Teknis Quiz

#### Jawaban Basic
1. `mmap()` memetakan halaman virtual memori langsung ke kernel file cache (*Zero-Copy*), meniadakan alokasi buffer ganda dan mengeliminasi proses *copying* data eksplisit antara ruang kernel dan user space via memory bus.
2. **64 byte**. Konstanta ini krusial karena CPU mengambil dan memvalidasi koherensi data antar core dalam blok kelipatan cache line. Memisahkan variabel yang ditulis secara bersamaan ke cache line yang berbeda mencegah degradasi performa akibat *false sharing*.
3. Modifikasi buffer sebelum CQE diterima menyebabkan kondisi **Data Race** nondeterministik dengan DMA controller/kernel subsystem, yang mengakibatkan penulisan data parsial (*corrupted write*) ke disk atau socket.
4. `mlock()` mengunci rentang alamat memori virtual proses ke dalam RAM fisik, mencegah kernel OS melakukan *paging out* atau *swapping* memori ke storage, menjamin latensi akses data deterministik.
5. `std::atomic<T>` hanya dijamin lock-free jika arsitektur perangkat keras target mendukung instruksi atomik native (seperti CAS/LL-SC) untuk ukuran dan alignment dari tipe data `T` tersebut (dapat diverifikasi via `std::atomic<T>::is_lock_free()`). Jika tidak, implementasi akan fallback ke internal OS mutex.

#### Jawaban Intermediate
1. - `relaxed`: Menjamin operasi baca/tulis variabel atomik itu sendiri tidak terpecah (*atomic*), tetapi mengizinkan CPU/kompiler menukar urutan instruksi memori lain di sekitarnya.
   - `release`: Tidak mengizinkan pembacaan/penulisan memori yang terjadi **sebelum** operasi release untuk digeser melampaui titik release ini.
   - `acquire`: Tidak mengizinkan pembacaan/penulisan memori yang terjadi **setelah** operasi acquire untuk digeser mendahului titik acquire ini.
2. Pada mode `IORING_SETUP_SQPOLL`, kernel mengalokasikan satu utas kernel independen (*kernel thread*) yang secara terus-menerus mem-polling Submission Queue di shared memory. Aplikasi cukup menulis langsung ke ring buffer user-space tanpa memanggil instruksi `io_uring_enter()` (menghilangkan syscall overhead).
3. Core pinning membatasi eksekusi thread ke CPU core fisik tertentu, memaksimalkan penggunaan *L1/L2 cache locality* dan mengeliminasi overhead context-switch akibat migrasi thread antar-core oleh scheduler OS. Kelemahannya: Core tersebut didedikasikan secara eksklusif, mengurangi kapasitas komputasi thread OS lain dan berpotensi menyebabkan utilisasi CPU tidak seimbang (*load imbalance*).
4. *False Sharing* terjadi saat dua thread pada core berbeda memodifikasi variabel independen yang berada pada baris cache fisik yang sama (64 byte), memicu invalidasi cache bolak-balik via protokol MESI (*cache bounce*). Dideteksi menggunakan hardware event `HITM` via `perf c2c`. Diatasi dengan memberi padding atau anotasi `alignas(64)` pada variabel terkait.
5. HugePages mengganti ukuran page virtual default (4KB) menjadi 2MB atau 1GB. Dengan ukuran page yang jauh lebih besar, satu entri TLB dapat mencakup area memori ratusan kali lipat lebih luas. Hal ini memangkas probabilitas *TLB miss* drastis dan mengurangi kedalaman traversal *Page Table Walk* oleh MMU hardware.

#### Solusi Skenario Produksi
1. **Solusi:**
   - Kunci halaman memori aplikasi menggunakan `mlockall(MCL_CURRENT | MCL_FUTURE)`.
   - Modifikasi parameter kernel Linux dirty-writeback: Turunkan `vm.dirty_background_ratio` (misal 5%) dan `vm.dirty_ratio` (misal 10%) agar flusher kernel mencicil penulisan secara periodik tanpa memicu *synchronous I/O throttling*.
   - Isolasi I/O disk aplikasi log ke NVMe terpisah dari disk OS root/swap, dan set I/O priority aplikasi menggunakan scheduler `ionice -c 1` (Real-time).
2. **Solusi:** Arsitektur x86-64 memiliki model memori yang kuat (*Strongly Ordered / TSO - Total Store Order*), di mana penulisan memori implisit memiliki aturan urutan tertentu yang ketat. Sebaliknya, ARM64 menggunakan model memori yang lemah (*Weakly Ordered*). Kode tersebut dipastikan menggunakan `memory_order_relaxed` yang tidak valid pada publishing boundary. Solusinya: Ubah operasi store pointer data produsen menjadi `std::memory_order_release` dan load konsumen menjadi `std::memory_order_acquire`. Ini memaksakan barrier instruksi memori DMB (*Data Memory Barrier*) pada ARM64.
3. **Solusi:**
   - Gunakan pendekatan *Epoch-based Heartbeat* atomik di dalam Shared Control Block, di mana producer wajib memperbarui variabel `std::atomic<uint64_t> heartbeat_epoch` secara periodik via cycle counter (`rdtsc`).
   - Konsumen mengamati selisih siklus waktu (timeout detection). Jika timeout tercapai dan producer mati mendadak, konsumen melakukan transisi state atomik ke `RECOVERY_MODE`, membaca indeks tail yang valid terakhir, dan menggunakan `robust futex` (`pthread_mutexattr_setrobust`) jika ada komponen mutex, atau mengklaim kepemilikan tail pointer untuk menguras sisa slot yang tertulis utuh sebelum melakukan unlink pada shared memory region.

---

### 16. Summary

Systems Programming C++ modern pada tingkat enterprise menuntut pemahaman mekanika komputasi perangkat keras:
1. **Eliminasi Abstraksi Berbiaya Tinggi:** Peniadaan overhead transisi kernel melalui *Zero-Copy architecture*, memori bersama (*Shared Memory*), dan *asynchronous I/O pipelines* seperti `io_uring`.
2. **Determinisme Hardware-Software:** Memaksimalkan efisiensi *Cache Lines*, eliminasi *False Sharing*, pencegahan *TLB misses* via HugePages, serta pemanfaatan *Core Isolation* dan *CPU Affinity*.
3. **Model Memori Formal:** Penerapan sinkronisasi bebas lock (*Lock-Free*) yang benar bergantung sepenuhnya pada penerapan *C++20 Atomics* dan *Acquire-Release Memory Ordering Semantics* yang disiplin guna menjamin reliabilitas mutlak pada arsitektur perangkat keras multi-core kontemporer.