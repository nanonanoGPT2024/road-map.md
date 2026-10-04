# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 01-Core-Foundations | **Topik:** Computer Science | **Bab:** 09 - Materi Lanjutan

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** interaksi antara arsitektur CPU multicore, hierarki *cache* (L1/L2/L3), dan bus interkoneksi hardware melalui protokol *Cache Coherency* (MESI/MOESI).
- **Mengevaluasi** dampak *instruction reordering* oleh compiler dan CPU *Out-of-Order Execution* terhadap integritas memori pada sistem konkuren berskala nanodetik.
- **Mengimplementasikan** struktur data *lock-free* dan *wait-free* berstandar produksi menggunakan C++20/C11 *atomic primitives* dengan semantik *Acquire-Release Memory Order*.
- **Merancang** subsistem I/O asinkron performa tinggi berbasis *kernel-bypass* dan *zero-copy queue ring* (mirip dengan arsitektur `io_uring` dan LMAX Disruptor).
- **Mengeliminasi** degradasi latensi produksi yang disebabkan oleh *False Sharing*, *TLB misses*, dan *Context Switch Overhead* melalui teknik *hardware-aware programming*.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, peserta wajib memahami:
1. **Representasi Memori Tingkat Rendah:** Struktur segmen memori (Stack, Heap, Data/BSS, Text), alokasi memori virtual via paging, dan *Translation Lookaside Buffer* (TLB).
2. **Bahasa Pemrograman Tingkat Sistem:** Kemampuan membaca dan menulis sintaks modern C++ (C++17/20) atau C11, manipulasi *raw pointers*, dan *pointer arithmetic*.
3. **Konkurensi Dasar:** Teori *race condition*, *deadlock*, penggunaan *POSIX threads* (`pthread`), serta mekanisme sinkronisasi primitif tingkat OS (*mutex*, *semaphore*, *condition variable*).
4. **Assembly Primitif:** Pemahaman dasar instruksi x86-64/ARM64 terkait atomic ops (`LOCK CMPXCHG`, `LDREX`/`STREX`, `MFENCE`).

---

## 3. Concept & Internal Architecture

Dalam rekayasa sistem terdistribusi dan komputasi ultra-low latency, perangkat lunak tidak lagi dapat dipisahkan dari arsitektur fisik silikon. Desain perangkat lunak tingkat produksi menuntut sinkronisasi mekanis antara instruksi kode dan mikroarsitektur CPU modern.

```
+-------------------------------------------------------------------------+
|                              CPU SOCKET                                 |
|                                                                         |
|  +------------------------+                 +------------------------+  |
|  |        CORE 0          |                 |        CORE 1          |  |
|  |  +------------------+  |                 |  +------------------+  |  |
|  |  | Store Buffer     |  |                 |  | Store Buffer     |  |  |
|  |  +--------+---------+  |                 |  +--------+---------+  |  |
|  |           |            |                 |           |            |  |
|  |  +--------v---------+  |                 |  +--------v---------+  |  |
|  |  | L1 Data Cache    |  |                 |  | L1 Data Cache    |  |  |
|  |  | (32KB, 64B line) |  |                 |  | (32KB, 64B line) |  |  |
|  |  +--------+---------+  |                 |  +--------+---------+  |  |
|  |           |            |                 |           |            |  |
|  |  +--------v---------+  |                 |  +--------v---------+  |  |
|  |  | Invalidate Queue |  |                 |  | Invalidate Queue |  |  |
|  |  +--------+---------+  |                 |  +--------+---------+  |  |
|  |           |            |                 |           |            |  |
|  |  +--------v---------+  |                 |  +--------v---------+  |  |
|  |  | L2 Cache (512KB) |  |                 |  | L2 Cache (512KB) |  |  |
|  |  +--------+---------+  |                 |  +--------+---------+  |  |
|  +-----------|------------+                 +-----------|------------+  |
|              +----------------------+-------------------+               |
|                                     |                                   |
|                        +------------v------------+                      |
|                        | Shared L3 Cache (16MB+) |                      |
|                        +------------+------------+                      |
+-------------------------------------|-----------------------------------+
                                      | Bus (UPI / Infinity Fabric)
                         +------------v------------+
                         |    Main Memory (DRAM)   |
                         +-------------------------+
```

### A. Protokol Cache Coherency (MESI & MOESI)
CPU mentransfer data dari DRAM ke cache dalam ukuran blok diskrit sebesar **64 byte** yang disebut **Cache Line**. Protokol MESI mengelola konsistensi cache line antar core:
- **Modified (M):** Cache line hanya ada di cache saat ini dan bernilai kotor (*dirty* terhadap DRAM).
- **Exclusive (E):** Cache line hanya ada di cache saat ini dan identik dengan DRAM (*clean*).
- **Shared (S):** Cache line mungkin diduplikasi di cache core lain dan identik dengan DRAM.
- **Invalid (I):** Cache line tidak memiliki data yang valid.

Ketika Core 0 menulis ke alamat memori yang berstatus *Shared*, CPU harus mengirim sinyal *Invalidate* melalui interkoneksi bus ke seluruh core lain sebelum commit. Keterlambatan propagasi ini memicu lahirnya optimasi perangkat keras: **Store Buffers** dan **Invalidate Queues**.

### B. Hardware Reordering & Memory Barriers
1. **Store Buffer:** Menyimpan data tulis sementara Core 0 agar eksekusi instruksi berikutnya tidak tertahan menunggu balasan *Invalidate Acknowledge* dari core lain. Konsekuensi: core lain membaca nilai lama (*Store-Load reordering*).
2. **Invalidate Queue:** Mengakui sinyal *Invalidate* secara instan tanpa langsung menghapus data dari L1/L2 cache, menundanya hingga pipeline CPU longgar. Konsekuensi: pembacaan memori lokal membaca data usang.

Untuk mengendalikan reordering ini pada tingkat kompilator dan hardware, arsitektur CPU menyediakan instruksi pembatas memori (*Memory Fence/Barrier*):
- **Full Barrier (`MFENCE` / DMB ISH):** Menjamin seluruh operasi baca dan tulis yang dideklarasikan sebelum fence selesai diproses sebelum instruksi setelah fence dieksekusi.
- **Acquire-Release Barrier:** Mengikat operasi tulis (*Release*) dengan operasi baca pasangannya (*Acquire*) tanpa menanggung overhead sinkronisasi global dari *Full Sequentially Consistent* (`std::memory_order_seq_cst`).

### C. Teori Formal: Lock-Free vs Wait-Free
- **Blocking:** Operasi dapat ditahan tanpa batas oleh thread lain (contoh: pemegang mutex tersuspensi oleh OS scheduler).
- **Lock-Free:** Setidaknya satu thread dijamin membuat kemajuan (*system-wide progress*) dalam jumlah langkah terhingga, meskipun thread individu mungkin mengalami *starvation*.
- **Wait-Free:** Setiap thread dijamin membuat kemajuan (*per-thread progress guarantee*) dalam jumlah langkah terhingga, terlepas dari konkurensi thread lain.

---

## 4. Why & What

| Dimensi | Pendekatan Tradisional (Mutex / Lock) | Pendekatan Modern (Lock-Free / Mechanical Sympathy) |
| :--- | :--- | :--- |
| **Prinsip Operasi** | Pesimis: Berasumsi konflik selalu terjadi, meminta proteksi kernel via *futex*. | Optimis: Eksekusi langsung di register/L1 via atomics (*CAS* loop) atau *Single-Producer Single-Consumer (SPSC)* ring. |
| **Overhead Siklus CPU** | ~1.000 – 10.000 siklus jika terjadi kontensi (biaya *context switch* & penjadwalan ulang OS). | ~10 – 50 siklus (latensi interkoneksi hardware cache-coherence). |
| **Prediktabilitas Latensi** | P99.99 buruk; rentan terhadap *Priority Inversion* dan *Convoy Phenomenon*. | P99.99 stabil; jitter deterministik pada skala sub-mikrodetik. |
| **I/O Handling** | Blocking Syscall (`read`, `write`) memicu transisi ring-3 (User) ke ring-0 (Kernel). | Non-blocking ring buffer bersama (Shared Memory Ring Buffer, seperti `io_uring` atau DPDK ring). |

Mekanisme ini esensial bagi arsitektur berdaya tampung jutaan transaksi per detik (*ultra-high throughput*):
1. **Menghapus System Call Overhead:** Setiap *context switch* kernel membuang isi TLB register dan merusak L1 Instruction/Data Cache (*cache thrashing*).
2. **Mengeksploitasi Kemampuan Hardware Penuh:** Menyelaraskan struktur data dengan batas cache line 64-byte untuk menghindari transmisi bus yang redundan.

---

## 5. How (Workflow Detail)

Alur kerja sinkronisasi data antar Core CPU menggunakan semantik *Acquire-Release* pada Ring Buffer:

```
[PRODUCER CORE (Core A)]                       [CONSUMER CORE (Core B)]
        |                                                 |
1. Tulis payload ke data buffer                           |
   (Plain memory write)                                   |
        |                                                 |
2. Eksekusi Atomic Store Release                          |
   pada Head Index                                        |
   -> Menguras Store Buffer Core A                        |
   -> Mengirim sinyal kepemilikan data                    |
        |                                                 |
        +========== Hardware Cache Invalidation =========>+
                                                          |
                                          3. Eksekusi Atomic Load Acquire
                                             pada Head Index
                                             -> Menguras Invalidate Queue Core B
                                             -> Menjamin payload di data buffer
                                                terbaca utuh sesuai urutan Core A
                                                          |
                                          4. Baca payload dari data buffer
                                             (Plain memory read)
                                                          |
                                          5. Perbarui Tail Index (Atomic Release)
```

1. **Producer Writing:** Data ditulis ke slot ring buffer array tanpa instruksi atomic mahal.
2. **Publishing (Release):** Producer mengeksekusi operasi penulisan `head` index menggunakan `std::memory_order_release`. Pada level hardware x86, ini menahan compiler reordering; pada ARM, instruksi `DMB ISHLD/ISH` disisipkan untuk memastikan data buffer telah ter-commit sebelum pointer dipublikasikan.
3. **Polling/Consuming (Acquire):** Consumer membaca `head` index menggunakan `std::memory_order_acquire`. Operasi ini menjamin bahwa seluruh pembacaan memori setelah instruksi ini tidak dapat di-reorder oleh hardware/compiler mendahului pembacaan `head`.
4. **Processing:** Consumer mengekstrak data dari buffer secara konsisten tanpa race condition.

---

## 6. Analogy & Diagram ASCII

### A. Analogi Papan Pengumuman & False Sharing
Bayangkan dua orang akuntan (Core 0 dan Core 1) bekerja di meja bersebelahan. Masing-masing memiliki buku catatan terpisah, tetapi manajemen meletakkan kedua buku tersebut di dalam satu baki fisik yang sama (*1 Cache Line = 64 byte*). 
Setiap kali Akuntan 0 ingin menulis di bukunya, protokol keamanan mewajibkannya mengambil seluruh baki fisik tersebut, menguncinya, sehingga Akuntan 1 terpaksa berhenti bekerja dan menunggu baki dikembalikan—meskipun Akuntan 1 sama sekali tidak menyentuh buku milik Akuntan 0.

```
                    KASUS FALSE SHARING (BURUK)
          Alamat Memori: 0x1000                Alamat Memori: 0x1008
      +--------------------------------------------------------------+
      |  Variable A (milik Core 0)   |  Variable B (milik Core 1)    |
      +--------------------------------------------------------------+
      <-------------------- 1 Cache Line (64 Byte) ------------------>
      Efek: Core 0 mengupdate A => Core 1 terpaksa invalidate cache L1!


             KASUS PADDING TERISOLASI (ARSITEKTUR BENAR)
      +-------------------------------+------------------------------+
      | Variable A |  Padding 56 Byte | Variable B |  Padding 56 Byte|
      +-------------------------------+------------------------------+
      <------ Cache Line 0 (64B) -----><------ Cache Line 1 (64B) ----->
      Efek: Core 0 dan Core 1 bekerja 100% paralel tanpa interkoneksi bus.
```

---

## 7. Simple & Practical Code Examples

### A. Simple Example: Demonstrasi Penanggulangan False Sharing
Program benchmark modern C++20 yang mendemonstrasikan degradasi performa akibat false sharing vs performa setelah penerapan `alignas(hardware_destructive_interference_size)`.

```cpp
// compile: g++ -std=c++20 -O3 false_sharing_demo.cpp -pthread -o fs_demo
#include <iostream>
#include <thread>
#include <vector>
#include <chrono>
#include <new>

#ifdef __cpp_lib_hardware_interference_size
    using std::hardware_destructive_interference_size;
#else
    // Standar de-facto arsitektur x86-64 & modern ARM64
    constexpr size_t hardware_destructive_interference_size = 64;
#endif

// Struktur rentan False Sharing: data berada di cacheline yang sama
struct ContendedCounters {
    uint64_t counter_a{0}; // 8 byte
    uint64_t counter_b{0}; // 8 byte (offset +8, berbagi 64-byte line yang sama)
};

// Struktur bebas False Sharing: diisolasi ke cacheline independen
struct AlignedCounters {
    alignas(hardware_destructive_interference_size) uint64_t counter_a{0};
    alignas(hardware_destructive_interference_size) uint64_t counter_b{0};
};

template <typename T>
void run_benchmark(const std::string& label, T& state) {
    constexpr uint64_t ITERATIONS = 500'000'000;
    
    auto start = std::chrono::high_resolution_clock::now();
    
    std::thread t1([&]() {
        for (uint64_t i = 0; i < ITERATIONS; ++i) {
            state.counter_a++;
        }
    });

    std::thread t2([&]() {
        for (uint64_t i = 0; i < ITERATIONS; ++i) {
            state.counter_b++;
        }
    });

    t1.join();
    t2.join();

    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double, std::milli> duration = end - start;
    
    std::cout << "[" << label << "] Durasi: " << duration.count() << " ms\n";
}

int main() {
    std::cout << "Hardware Cacheline Size: " << hardware_destructive_interference_size << " bytes\n";
    
    ContendedCounters contended;
    run_benchmark("FALSE SHARING DETECTED", contended);

    AlignedCounters aligned;
    run_benchmark("ISOLATED CACHELINES   ", aligned);

    return 0;
}
```

---

### B. Practical Example: Single-Producer Single-Consumer (SPSC) Lock-Free Ring Buffer Standar Produksi

Implementasi ring buffer ultra-low latency berbasis circular FIFO queue tanpa penggunaan mutex, menggunakan semantik atomik C++20 yang mematuhi restriksi hardware alignment.

```cpp
#ifndef SPSC_RING_BUFFER_HPP
#define SPSC_RING_BUFFER_HPP

#include <atomic>
#include <cstddef>
#include <new>
#include <optional>
#include <vector>
#include <cassert>

#ifdef __cpp_lib_hardware_interference_size
    using std::hardware_destructive_interference_size;
#else
    constexpr size_t hardware_destructive_interference_size = 64;
#endif

template <typename T, size_t Capacity>
class SPSCRingBuffer {
    static_assert((Capacity & (Capacity - 1)) == 0, "Kapasitas harus berupa nilai perpangkatan 2!");
    static_assert(std::is_trivially_copyable_v<T>, "T harus trivially copyable untuk determinisme latensi");

public:
    SPSCRingBuffer() : storage_(Capacity) {}

    // Method produsen: Dipanggil HANYA dari thread Producer
    bool try_enqueue(const T& item) noexcept {
        const size_t current_head = head_.load(std::memory_order_relaxed);
        const size_t current_tail = tail_cached_for_producer_;

        // Kapasitas penuh jika jarak head dan tail melampaui buffer limit
        if ((current_head - current_tail) >= Capacity) {
            // Ambil state tail terbaru yang dipublikasikan oleh Consumer
            tail_cached_for_producer_ = tail_.load(std::memory_order_acquire);
            if ((current_head - tail_cached_for_producer_) >= Capacity) {
                return false; // Queue penuh
            }
        }

        // Tulis data ke memory buffer (tanpa operasi atomik mahal)
        storage_[current_head & BUFFER_MASK] = item;

        // Publikasikan index head baru kepada consumer dengan Release semantic
        head_.store(current_head + 1, std::memory_order_release);
        return true;
    }

    // Method konsumen: Dipanggil HANYA dari thread Consumer
    std::optional<T> try_dequeue() noexcept {
        const size_t current_tail = tail_.load(std::memory_order_relaxed);
        const size_t current_head = head_cached_for_consumer_;

        // Queue kosong jika tail mengejar head
        if (current_tail == current_head) {
            // Ambil state head terbaru yang dipublikasikan oleh Producer
            head_cached_for_consumer_ = head_.load(std::memory_order_acquire);
            if (current_tail == head_cached_for_consumer_) {
                return std::nullopt; // Queue kosong
            }
        }

        // Baca payload secara aman
        T item = storage_[current_tail & BUFFER_MASK];

        // Publikasikan index tail baru kepada producer dengan Release semantic
        tail_.store(current_tail + 1, std::memory_order_release);
        return item;
    }

private:
    static constexpr size_t BUFFER_MASK = Capacity - 1;

    // Buffer penyimpanan data
    std::vector<T> storage_;

    // Variabel tulis milik Producer, diisolasi pada cacheline tersendiri
    alignas(hardware_destructive_interference_size) std::atomic<size_t> head_{0};
    size_t tail_cached_for_producer_{0}; // Cache lokal producer untuk mengurangi cross-core invalidation

    // Variabel tulis milik Consumer, diisolasi pada cacheline tersendiri
    alignas(hardware_destructive_interference_size) std::atomic<size_t> tail_{0};
    size_t head_cached_for_consumer_{0}; // Cache lokal consumer untuk mengurangi cross-core invalidation
};

#endif // SPSC_RING_BUFFER_HPP
```

---

## 8. Real World Case Study: High-Frequency Trading Matching Engine

### Konteks & Skala Arsitektur
Sebuah bursa kripto/ekuitas global memproses rata-rata 3.500.000 pesanan per detik (*orders/sec*) pada jam pembukaan pasar. Target arsitektur adalah menjaga latensi ujung-ke-ujung (Gateway parsing hingga matching book) di bawah **1.2 mikrodetik (p99.9)**.

### Titik Kegagalan Desain Awal (Legacy Architecture)
Desain awal menggunakan pendekatan thread pool konvensional:
1. Thread jaringan (`epoll`) menerima order byte, mengalokasikannya ke heap (`new Order()`), lalu memasukkannya ke dalam `std::queue<Order*>` global yang diproteksi oleh `std::mutex` dan `std::condition_variable`.
2. Matching Engine Thread menunggu di `condvar.wait()`.
3. Hasil: 
   - **Contention Collapse:** Pada beban 800.000 order/detik, CPU 64-core menghabiskan 65% waktu siklusnya di kernel space (`sys_futex`) menangani lock starvation.
   - **Latensi Spike:** P99.9 melonjak hingga 45 milidetik akibat preemption OS dan memory allocation fragmentation.

```
ARUS DATA TRADISIONAL (BURUK)
[NIC] -> [Kernel Network Stack] -> [epoll] -> [User Heap Alloc] -> [Mutex Locked Queue] -> [Engine Core]
Overhead: 2x Context Switch + Lock Contention + Heap Allocation Latency = ~35 us

ARUS DATA MODERN (HIGH FREQUENCY TRADING ARCHITECTURE)
[NIC DPDK/io_uring] -> [Zero-Copy Ring Buffer] -> [Pinned Core Lock-Free SPSC] -> [Pinned Core Matching Engine]
Overhead: 0 Context Switch + 0 Mutex + Cache Local Memory = ~450 ns
```

### Solusi Rekayasa Produksi
1. **CPU Pinning (`pthread_setaffinity_np`):** Mengisolasi thread Gateway ke CPU Core 2, dan thread Matching Engine ke CPU Core 4. Kedua core berada dalam NUMA node yang sama untuk meminimalkan latensi bus antarsoket.
2. **Lock-Free SPSC Ring Buffer:** Menghubungkan Gateway dan Matching Engine via struktur SPSC Ring Buffer seperti pada seksi 7.
3. **Zero Dynamic Allocation (Object Pooling):** Alokasi array pesanan dilakukan sekali saat *startup* engine (*pre-allocated memory slab*).
4. **Busy-Wait Polling Mode:** Menghilangkan `sleep`/`yield`. Matching Engine menjalankan instruksi assembly `_mm_pause()` dalam loop konstan untuk merespons order seketika tanpa jeda context switch.

---

## 9. Trade-offs & Analysis

```
Pendekatan Desain            Throughput        P99 Latensi     Beban Siklus CPU    Kompleksitas Kode
------------------------------------------------------------------------------------------------------
Mutex & CondVar              Rendah-Sedang     Buruk (ms)      Rendah saat Idle    Sederhana
Lock-Free (CAS Loop MPMC)    Tinggi            Cukup (us)      Tinggi (Spinning)   Tinggi
Lock-Free SPSC + Pinning     Maksimal          Sangat Rendah   100% Core Saturasi  Sangat Tinggi
```

### Analisis Parameter:
1. **Performance & Latency vs CPU Utilization:**
   Struktur lock-free dengan *busy-wait polling* menjamin latensi nanodetik, namun mengorbankan utilitas CPU sebesar 100% pada core yang di-*pin*. Hal ini tidak cocok untuk aplikasi cloud multi-tenant biasa, namun menjadi mandatori pada sistem *financial exchange* dan *packet processing* telekomunikasi.
2. **Skalabilitas vs Kompleksitas Kode:**
   Arsitektur *Single-Producer Single-Consumer* (SPSC) memiliki performa jauh lebih cepat dibandingkan *Multiple-Producer Multiple-Consumer* (MPMC). MPMC membutuhkan loop *Compare-And-Swap* (CAS) yang rentan mengalami *contention storms* pada cache bus ketika puluhan core mencoba mengubah atomic pointer yang sama secara simultan.

---

## 10. Common Mistakes & Troubleshooting

### 1. Masalah ABA pada Struktur Data CAS
- **Gejala:** Memory corruption dan *segmentation fault* acak pada Stack/Queue berbasis pointer lock-free.
- **Penyebab:** Thread 1 membaca pointer $A$. Thread 2 memodifikasi pointer menjadi $B$, lalu mengalokasikan kembali memori baru yang kebetulan memperoleh alamat $A$ lagi, lalu menulisnya kembali. Thread 1 mengeksekusi `compare_exchange_strong(A, C)` dan berhasil, padahal struktur data internal di bawah pointer $A$ telah berubah total.
- **Solusi:** Gunakan teknik *Tagged Pointers* (menggabungkan bit versi counter dan pointer memori dalam 128-bit atomic `std::atomic<TaggedPtr>`) atau *Hazard Pointers / Epoch-Based Reclamation (EBR)*.

### 2. Menganggap Kata Kunci `volatile` Bersifat Atomik
- **Gejala:** Data korup pada sistem multicore meskipun variabel telah dideklarasikan `volatile`.
- **Penyebab:** Dalam spesifikasi standar C dan C++, `volatile` HANYA melarang kompilator melakukan optimasi register caching (selalu fetch dari memori). `volatile` **TIDAK** membangkitkan instruksi atomic hardware dan **TIDAK** mencegah *Out-of-Order execution* oleh CPU.
- **Solusi:** Gunakan tipe formal `std::atomic<T>` dengan semantik *memory order* yang tepat.

### 3. Melupakan Memory Reclamation pada Dynamic Lock-Free Node
- **Gejala:** Terjadinya *Use-After-Free* ketika sebuah node dihapus dari daftar lock-free oleh Thread 1 sementara Thread 2 masih berada di tengah proses pembacaan pointer node tersebut.
- **Solusi:** Terapkan skema *Epoch-Based Reclamation* (EBR). Memori fisik sebuah node hanya boleh dibebaskan (*deallocated*) ke pool saat seluruh thread aktif telah menyelesaikan fase siklus eksekusinya (*global epoch grace period*).

---

## 11. Best Practices & Production Checklist

### Checklist Desain Arsitektur Sistem Produksi

- [ ] **Hardware Topology Mapping:** Verifikasi NUMA node menggunakan `lscpu` atau `numactl -H`. Pastikan thread-thread yang saling berkomunikasi berada pada soket fisik yang sama.
- [ ] **Thread Pinning:** Eksekusi `pthread_setaffinity_np` secara eksplisit pada inisialisasi thread untuk mengunci thread pada *isolated core* (gunakan isolasi boot kernel `isolcpus`).
- [ ] **Cacheline Separation:** Pastikan seluruh state yang ditulis oleh core berbeda memiliki atribut `alignas(64)` guna mengeliminasi False Sharing.
- [ ] **Zero-Allocation Data Path:** Tidak ada pemanggilan fungsi `malloc`, `free`, `new`, atau mutasi dynamic vector di jalur kritis (*hot path*) transaksi.
- [ ] **Compiler Sanitizers:** Wajib lolos pengujian menggunakan `-fsanitize=thread` (TSan) dan `-fsanitize=address` (ASan) pada unit test konkurensi.
- [ ] **Profiling Verifikasi Hardware Counter:** Audit metrik hardware menggunakan Linux `perf`:
  - Periksa `cache-misses` (harus $< 1\%$ pada hot path).
  - Periksa `context-switches` (harus mendekati 0 untuk polling threads).

---

## 12. Hands-on Practice

Implementasikan verifikasi hardware-aware programming pada lingkungan Linux:

### Struktur Direktori
```
hands-on/m02/
├── CMakeLists.txt
├── include/
│   └── spsc_queue.hpp
└── src/
    ├── benchmark.cpp
    └── main.cpp
```

### Langkah 1: Siapkan `CMakeLists.txt`
```cmake
cmake_minimum_required(VERSION 3.20)
project(HighPerformanceCS LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -Wall -Wextra -pthread -march=native")

include_directories(include)

add_executable(ring_buffer_perf src/benchmark.cpp)
```

### Langkah 2: Buat File `src/benchmark.cpp`
Salin kode dari Seksi 7B ke dalam `include/spsc_queue.hpp`. Buat modul pengujian multi-thread di `src/benchmark.cpp` yang mengirimkan $50.000.000$ pesan bilangan bulat 64-bit dan mencatat metrik *Throughput* (ops/sec).

### Langkah 3: Kompilasi dan Profiling Kernel Counter
Jalankan perintah berikut di terminal Linux:
```bash
mkdir -p build && cd build
cmake ..
make -j$(nproc)

# Eksekusi profiling menggunakan Linux perf
perf stat -e task-clock,context-switches,cpu-migrations,page-faults,cycles,instructions,cache-references,cache-misses ./ring_buffer_perf
```

### Langkah 4: Evaluasi Output
Analisis output terminal. Pastikan nilai `context-switches` berada di bawah angka 50 untuk keseluruhan eksekusi 50 juta pesan, membuktikan bahwa pipeline eksekusi berjalan murni di tingkat pengguna (*userspace data plane*) tanpa intervensi scheduler kernel.

---

## 13. Exercises

### Level Easy
1. Ubah struktur SPSC Ring Buffer pada Seksi 7B agar dapat mengembalikan persentase keterisian antrean saat ini (`occupancy_percentage()`) secara non-blocking dan thread-safe.
   - *Petunjuk:* Pikirkan semantik `std::memory_order_relaxed` untuk pembacaan metrik telemetri yang toleran terhadap ketidakakuratan seketika.

### Level Medium
2. Rancang struktur data **Lock-Free Stack (Treiber Stack)** menggunakan pointer atomik C++20 (`std::atomic<Node*>`). Implementasikan fungsi `push(T val)` dan `pop()` menggunakan perulangan `compare_exchange_weak`.
   - *Petunjuk:* Tangani kegagalan CAS secara elegan dan jelaskan mengapa `compare_exchange_weak` lebih optimal dibanding `strong` pada arsitektur ARM/RISC.

### Level Hard
3. Buat implementasi **Bounded MPMC (Multi-Producer Multi-Consumer) Queue** berbasis array siklis menggunakan teknik alokasi sekuensial (mirip dengan implementasi Dmitry Vyukov). Setiap sel/slot array harus memiliki nomor *turn sequence* atomik untuk mengontrol giliran write dan read antar thread secara serentak.

---

## 14. Challenges

### Tantangan Arsitektur: "The Sub-Microsecond Market Data Gateway"
Sebuah perusahaan Tier-1 High-Frequency Trading menugaskan Anda merancang modul ingestion market data parser dengan spesifikasi:
- **Throughput Target:** Mampu memproses 20.000.000 paket/detik.
- **Tail Latency Target:** P99.99 $< 600\text{ ns}$.
- **Spesifikasi Input:** Stream biner raw network bytes (UDP Multicast) dialirkan langsung via kernel bypass ring.

**Persyaratan Desain:**
1. Rancang cetak biru arsitektur data plane pipeline dari parsing paket, validasi checksum, pembentukan internal tick, hingga pengiriman tick ke matching core.
2. Tuliskan analisis teknis mengenai bagaimana Anda menangani skenario saat matching core mengalami *backpressure* tanpa memicu alokasi memori dinamis dan tanpa membuat thread UDP gateway kehilangan paket (*packet drops*).
3. Buktikan secara matematis dan mikroskopik bagaimana skema isolasi cacheline, TLB HugePages (2MB/1GB), dan pemilihan semantik memori Anda meminimalisasi *stalls* pada pipeline instruction decoder CPU x86.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)

#### Soal 1
Berapa ukuran umum sebuah *cache line* pada prosesor modern berarsitektur x86-64 dan ARM64?
- A. 16 Byte
- B. 32 Byte
- C. 64 Byte
- D. 128 Byte

#### Soal 2
Status apakah dalam protokol MESI yang menunjukkan bahwa suatu cache line bersifat valid, hanya ada di cache lokal core tersebut, dan isinya identik dengan DRAM?
- A. Modified (M)
- B. Exclusive (E)
- C. Shared (S)
- D. Invalid (I)

#### Soal 3
Apa perbedaan utama antara kata kunci `volatile` dan pustaka `<atomic>` dalam standar C++ modern?
- A. `volatile` lebih cepat daripada `atomic`.
- B. `volatile` mencegah compiler register optimization, sedangkan `atomic` menjamin operasi CPU bus/register yang atomic dan memory visibility order.
- C. `volatile` hanya untuk pointer, sedangkan `atomic` untuk tipe data primitif.
- D. Tidak ada perbedaan fungsional; keduanya dapat dipertukarkan.

#### Soal 4
Fenomena di mana dua thread pada core berbeda memodifikasi variabel berbeda yang kebetulan berada di dalam satu cache line fisik yang sama disebut:
- A. True Sharing
- B. Cache Poisoning
- C. False Sharing
- D. Thread Thrashing

#### Soal 5
Pada operasi pengiriman data Single-Producer Single-Consumer, semantik *memory order* apa yang paling efisien namun aman digunakan saat producer mempublikasikan nilai `head_index` baru ke consumer?
- A. `std::memory_order_relaxed`
- B. `std::memory_order_release`
- C. `std::memory_order_seq_cst`
- D. `std::memory_order_consume`

---

### Bagian 2: Intermediate (Pilihan Ganda & Analisis Pendek)

#### Soal 6
Mengapa instruksi `compare_exchange_weak` umumnya lebih disukai dalam sebuah loop CAS (*Compare-And-Swap*) pada arsitektur ARM dibandingkan `compare_exchange_strong`?
- A. Karena `compare_exchange_weak` tidak memerlukan memori.
- B. Karena arsitektur ARM menggunakan mekanisme LL/SC (Load-Linked/Store-Conditional) yang rentan terhadap *spurious failure*, sehingga implementasi *strong* memerlukan overhead loop instruksi assembly tambahan.
- C. Karena `compare_exchange_weak` selalu bersifat *wait-free*.
- D. Karena `compare_exchange_strong` telah didepresiasi dalam C++20.

#### Soal 7
Manakah kondisi berikut yang secara formal mengkategorikan suatu algoritma sebagai **Wait-Free**?
- A. Tidak ada mutex yang digunakan dalam implementasi.
- B. Setiap thread dijamin menyelesaikan operasinya dalam jumlah langkah eksekusi yang terbatas, terlepas dari kecepatan atau penundaan thread lain.
- C. Program tidak pernah mengalami *segmentation fault*.
- D. Setidaknya ada satu thread yang membuat kemajuan (*progress*) pada sistem global.

#### Soal 8
Apa tujuan utama menyematkan *padding* menggunakan `alignas(hardware_destructive_interference_size)` di antara variabel atomik dalam antrean lock-free?
- A. Mempercepat kompilasi kode.
- B. Memastikan kompilator tidak menata ulang kode sumber.
- C. Mengisolasi variabel ke cache line mandiri guna mencegah invalidasi cache lintas-core yang tidak diperlukan.
- D. Membatasi ukuran variabel agar pas di dalam register CPU.

#### Soal 9
Apa konsekuensi arsitektur dari penggunaan semantik `std::memory_order_seq_cst` pada prosesor x86?
- A. Mengakibatkan instruksi `MFENCE` atau operasi `LOCK` dipanggil, yang membekukan store buffer lokal dan memicu latensi transfer bus yang tinggi.
- B. Mematikan fitur Hyper-Threading secara dinamis.
- C. Menghapus data dari memory swap.
- D. Memaksa context switch ke thread kernel.

#### Soal 10
Pada arsitektur CPU multicore, apa fungsi utama dari komponen **Store Buffer**?
- A. Menyimpan log instruksi yang gagal dieksekusi.
- B. Mengizinkan core CPU melanjutkan eksekusi instruksi berikutnya tanpa harus terhenti menunggu konfirmasi invalidasi cache dari core lain.
- C. Menghubungkan prosesor langsung ke media penyimpanan NVMe SSD.
- D. Menggandakan kapasitas memori L3 cache secara virtual.

---

### Bagian 3: Skenario Kasus Produksi

#### Skenario 1: The P99 Jitter Mystery
Sebuah tim arsitek meluncurkan service pemrosesan transaksi berbasis *Lock-Free Ring Buffer*. Berdasarkan pengetesan, throughput mencapai 15.000.000 pesan/detik. Namun, pada monitoring di lingkungan produksi, terjadi lonjakan latensi ekstrem (P99.9 melonjak dari 400 ns ke 28 ms) setiap beberapa detik secara periodik. 
Setelah dianalisis, thread produsen dan konsumen tidak menggunakan thread pinning, dan mesin server memiliki 2 Soket CPU fisik (NUMA architecture). 
**Pertanyaan Kasus:** Jelaskan akar masalah perangkat keras apa yang terjadi dan bagaimana perbaikan komprehensifnya!

#### Skenario 2: Crash Pasca Alokasi Ulang (The ABA Breakdown)
Sebuah sistem database in-memory mengimplementasikan *Lock-Free Stack* untuk mengelola koneksi pool objek memori bebas. Saat pengujian beban berat (*stress test*) selama 4 jam, proses tiba-tiba mengalami *Segmentation Fault* pada pointer reference di dalam operasi `pop()`. Pemeriksaan dump file menunjukkan bahwa alamat memori yang dituju telah dialokasikan ulang untuk keperluan lain.
**Pertanyaan Kasus:** Identifikasi kerentanan konkurensi apa yang terjadi, mengapa pengujian singkat tidak mendeteksinya, dan berikan solusi perbaikannya!

#### Skenario 3: The False Sharing Diagnostic
Seorang software engineer membuat sistem monitoring telemetri dengan mendeklarasikan metrik array global:
```cpp
uint64_t worker_events_processed[8]; // Dipetakan ke 8 worker threads
```
Setiap thread $i$ melakukan inkrementasi `worker_events_processed[i]++` secara independen. Meskipun setiap thread bekerja pada variabel elemen array yang berbeda tanpa saling berbagi data (*no data sharing*), engineer mendapati bahwa penambahan jumlah thread dari 1 ke 8 tidak meningkatkan throughput, melainkan menurunkan performa hingga 70%.
**Pertanyaan Kasus:** Analisis kejadian tersebut dari perspektif pergerakan *Cache Line State* (MESI) antar core dan perbaiki deklarasi kodenya!

---

### Kunci Jawaban & Pembahasan Quiz

#### Bagian 1: Basic
1. **C** — Standar ukuran cache line untuk prosesor x86-64 dan ARM64 desktop/server modern adalah 64 Byte.
2. **B** — Status *Exclusive* (E) menandakan data hanya ada di cache lokal, belum dimodifikasi (*clean*), dan konsisten dengan DRAM.
3. **B** — `volatile` hanya mengontrol optimasi compiler (mencegah register caching). Hanya `atomic` yang menangani hardware instruction ordering, bus lock, dan CPU-level memory visibility.
4. **C** — *False Sharing* terjadi saat dua thread memodifikasi variabel berbeda yang berada di dalam 1 cache line (64 byte) yang sama.
5. **B** — Semantik `memory_order_release` memastikan semua store operasi sebelumnya ter-commit sebelum pointer index dipublikasikan, tanpa overhead mahal `seq_cst`.

#### Bagian 2: Intermediate
6. **B** — Arsitektur ARM mengandalkan primitive LL/SC. `compare_exchange_weak` dapat gagal secara spurious jika terjadi context switch atau cache-eviction, sehingga ideal dibungkus dalam loop yang sudah ada tanpa overhead pengecekan ganda.
7. **B** — Syarat formal *Wait-Free* adalah jaminan kemajuan tingkat *per-thread* dalam jumlah siklus yang terbatas tanpa bergantung pada thread lain.
8. **C** — Padding memaksa kompilator menaruh variabel pada alamat batas kelipatan 64 byte baru, sehingga variabel tidak akan berada pada cache line yang sama dengan variabel lain.
9. **A** — `seq_cst` memerlukan total global order, yang pada arsitektur x86 memicu instruksi pengurasan pipeline store buffer (`MFENCE` atau prefix `LOCK`), memperlambat hot-path throughput.
10. **B** — Store buffer didesain untuk decoupling proses pipeline penulisan core dari latensi propagasi invalidasi bus cache-coherence.

#### Bagian 3: Skenario Kasus Produksi
- **Skenario 1:**
  *Akar Masalah:* OS scheduler memindahkan thread secara dinamis antar core yang berbeda soket fisik (Cross-NUMA node migration). Ketika thread berpindah soket, L1/L2 cache menjadi dingin (*cold cache miss*), dan setiap pembacaan/penulisan pointer harus menyeberangi interkoneksi lambat antar-soket (misal: Intel UPI / AMD Infinity Fabric) yang meningkatkan latensi ratusan kali lipat.
  *Solusi:* Terapkan CPU core isolation di level kernel (`isolcpus`), kunci thread ke core tertentu dengan `pthread_setaffinity_np`, alokasikan memori lokal pada NUMA node yang bersangkutan (`numactl --membind` atau `numa_alloc_onnode`).
- **Skenario 2:**
  *Akar Masalah:* Masalah klasik ABA (*ABA Problem*). Node stack $A$ diambil, dibebaskan (*freed*), dialokasikan ulang pada alamat yang persis sama, lalu dipasang kembali ke stack. CAS memeriksa nilai pointer yang identik sehingga mengira tidak ada perubahan state, padahal `next` pointer dari node $A$ telah menunjuk ke memori acak.
  *Solusi:* Implementasikan skema *Epoch-Based Reclamation* (EBR) atau *Hazard Pointers* untuk menahan pembebasan memori selama masih ada pembaca aktif, atau gunakan *Tagged Pointers* (menyematkan 64-bit sequence counter di sebelah 64-bit pointer menggunakan instruksi atomic 128-bit `CMPXCHG16B`).
- **Skenario 3:**
  *Akar Masalah:* Array `uint64_t worker_events_processed[8]` memakan total memori $8 \times 8 = 64\text{ byte}$, yang berada persis di dalam **satu cache line**. Ketika Thread 0 melakukan update, status cache line di L1 core 1-7 diubah menjadi *Invalid* (I). Ketika Core 1 ingin mengupdate variabelnya, ia mengalami L1 miss dan harus meminta transfer data dari Core 0 via interconnect bus, lalu membatalkan cache milik Core 0. Bus CPU mengalami *cache-line ping-pong*.
  *Perbaikan:*
  ```cpp
  struct alignas(64) PaddedMetric {
      uint64_t value{0};
  };
  PaddedMetric worker_events_processed[8];
  ```

---

## 16. Summary

1. **Simetri Mekanis (Mechanical Sympathy):** Pembuatan perangkat lunak berskala latensi rendah membutuhkan pemahaman komprehensif terhadap keterbatasan dan arsitektur silikon fisik (hierarki cache 64-byte, store buffers, invalidate queues, dan topologi NUMA).
2. **Protokol Cache & False Sharing:** Menempatkan data yang sering diubah oleh thread yang berbeda dalam satu blok 64-byte memicu invalidasi cache L1/L2 yang destruktif (*False Sharing*). Solusinya adalah penggunaan isolasi eksplisit via `alignas(64)`.
3. **Memory Order Semantics:** Penggunaan `std::memory_order_seq_cst` secara membabi buta membunuh performa sistem multicore. Pola Producer-Consumer modern cukup mengandalkan pasangan `std::memory_order_release` (pada saat menulis/mempublikasi) dan `std::memory_order_acquire` (pada saat membaca/mengkonsumsi) untuk menjamin integritas data dengan overhead perangkat keras minimal.
4. **Lock-Free Zero-Allocation Architecture:** Menghilangkan lock/mutex dan syscall di jalur kritis adalah fondasi dari sistem transaksi throughput ultra-tinggi. Pola antrean circular SPSC berbasis *atomic head/tail index* yang dipadukan dengan *thread pinning* menghasilkan transmisi data sub-mikrodetik yang stabil dan bebas dari jitter OS.