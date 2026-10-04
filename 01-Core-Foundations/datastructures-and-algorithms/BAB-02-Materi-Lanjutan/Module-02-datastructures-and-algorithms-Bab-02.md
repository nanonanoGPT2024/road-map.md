# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 01-Core-Foundations | **Bab 02:** BAB-02-Materi-Lanjutan

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan memiliki kompetensi mendalam untuk:
- Menganalisis karakteristik eksekusi algoritma dan struktur data pada tingkat mikroarsitektur CPU (*mechanical sympathy*), mencakup hierarki cache L1/L2/L3, *cache line*, dan *branch prediction*.
- Mengidentifikasi dan memitigasi anomali performa konkurensi tingkat rendah seperti *false sharing*, *cache line bouncing*, dan *memory ordering reordering*.
- Mengimplementasikan struktur data *lock-free* dan *wait-free* berbasis primitif atomik (*Compare-And-Swap*, *Memory Barriers/Fences*) yang aman dari bahaya *ABA Problem* dan kebocoran memori.
- Merekayasa ulang tata letak memori data (*Memory Layout*) dari *Array of Structures* (AoS) ke *Structure of Arrays* (SoA) guna memaksimalkan *throughput* SIMD (*Single Instruction, Multiple Data*) dan efisiensi *prefetcher* CPU.
- Merancang dan mengevaluasi arsitektur penyimpanan data tingkat lanjut (LSM-Tree vs. B+ Tree) untuk beban kerja *write-heavy* dan *read-heavy* pada skala jutaan operasi per detik (IOPS).

---

## 2. Prerequisite

Untuk mencerna materi ini secara komprehensif, engineer harus menguasai:
- **Arsitektur Sistem Komputer**: Model memori Von Neumann, konsep memori virtual, *paging*, dan register CPU.
- **Sistem Operasi**: *Context switching*, model *threading* OS (POSIX/Windows threads), dan primitif sinkronisasi kernel (*mutex*, *semaphore*).
- **Bahasa Tingkat Sistem**: Pemahaman pointer, alokasi heap vs. stack, dan model memori pada C++20, Rust, atau Go tingkat lanjut (manipulasi paket `unsafe` dan `sync/atomic`).
- **Analisis Asimptotik Tingkat Lanjut**: Pemahaman mengapa kompleksitas $\mathcal{O}(1)$ teoritis dapat kalah performa dibandingkan $\mathcal{O}(N)$ akibat faktor konstanta hardware (*hardware constant factors*).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 The Memory Wall & Mechanical Sympathy
Dalam sistem komputasi modern, kecepatan pemrosesan CPU tumbuh secara eksponensial lebih cepat dibandingkan latensi akses ke DRAM (*The Memory Wall*). Siklus instruksi CPU modern berada pada skala ~0.3 nanodetik (3-4 GHz), sedangkan latensi membaca *main memory* (DRAM) memakan waktu 50–100 nanodetik (~200-300 siklus CPU yang terbuang/stalled).

```
+-------------------------------------------------------------+
| CPU Core (ALU, Registers)                                    |
+-------------------------------------------------------------+
  | Latency: ~0.5 - 1 ns
  v
+-----------------------+
| L1 Data Cache (32 KB) | -> 64-byte Cache Lines
+-----------------------+
  | Latency: ~1 - 3 ns
  v
+-----------------------+
| L2 Cache (512 KB-1MB) |
+-----------------------+
  | Latency: ~3 - 10 ns
  v
+-------------------------------------------------------------+
| L3 Shared Cache (16 - 64 MB)                                |
+-------------------------------------------------------------+
  | Latency: ~10 - 20 ns
  v
+-------------------------------------------------------------+
| Main Memory (DRAM, 16 - 256 GB)                             |
| Latency: ~60 - 100 ns                                       |
+-------------------------------------------------------------+
```

Struktur data konvensional berbasis node terpisah (*Node-based Data Structures* seperti `std::list`, Pohon Biner, *Linked HashMaps*) menyebabkan dereferensi pointer acak (*pointer chasing*). Hal ini memicu rentetan *L1/L2 Cache Misses*, memaksa CPU menunggu data dari DRAM. Sebaliknya, struktur data kompak berbasis kontigu (*Contiguous Array-backed Structures*) mengeksploitasi *Hardware Spatial Prefetcher*, yang secara proaktif menarik blok 64-byte (*Cache Line*) berikutnya ke cache sebelum CPU memintanya.

### 3.2 False Sharing dan Protokol Koherensi Cache (MESI)
Pada lingkungan *multi-core*, setiap core memiliki cache L1/L2 privat. Protokol seperti **MESI** (*Modified, Exclusive, Shared, Invalid*) menjaga konsistensi state memori antar core.
- **Cache Line Granularity**: Memori selalu ditransfer dalam ukuran blok tetap (umumnya 64 byte).
- **False Sharing**: Terjadi ketika Thread A pada Core 1 memodifikasi variabel `X`, dan Thread B pada Core 2 memodifikasi variabel `Y`, di mana `X` dan `Y` terletak berdampingan dalam satu *cache line* 64-byte yang sama.
- **Dampak Arsitektural**: Meskipun `X` dan `Y` independen secara logika program, modifikasi pada Core 1 akan mentransisikan status *cache line* pada Core 2 menjadi **Invalid (I)** melalui bus komunikasi antar-core (*Cache Coherency Storm*). Core 2 terpaksa memuat ulang seluruh 64-byte dari L3 atau DRAM, merusak skalabilitas throughput konkurensi hingga hitungan magnitudo.

```
                  Cache Line (64 Bytes)
+-------------------------------------------------------+
|      Variable X (Core 1)    |   Variable Y (Core 2)   |
+-------------------------------------------------------+
                           ^
             State Coherency: INVALIDATED
       Core 2 terpaksa re-fetch walau hanya membaca Y
```

### 3.3 Model Memori & Memory Ordering
Pada eksekusi multi-core, instruksi mesin tidak selalu dieksekusi secara berurutan (*Out-of-Order Execution* oleh CPU dan penataan ulang oleh compiler). Untuk koordinasi *lock-free*, kita harus menentukan semantik urutan memori (*Memory Ordering*):
1. **Sequentially Consistent (`memory_order_seq_cst`)**: Model paling ketat. Ada urutan global tunggal yang disepakati semua thread. Membutuhkan instruksi *bus locking* mahal (misal: `MFENCE` pada x86).
2. **Acquire-Release (`memory_order_acquire`, `memory_order_release`)**:
   - **Release**: Menjamin bahwa seluruh operasi *write* sebelumnya (baik atomik maupun non-atomik) tidak dapat ditata ulang melewati *store-release* ini.
   - **Acquire**: Menjamin bahwa seluruh operasi *read* sesudahnya tidak dapat ditata ulang mendahului *load-acquire* ini.
   - Membentuk sinkronisasi *happens-before* antar thread tanpa memaksakan urutan global penuh pada variabel lain.
3. **Relaxed (`memory_order_relaxed`)**: Hanya menjamin sifat atomisitas operasi pada variabel tersebut, tanpa jaminan urutan (*ordering constraints*) terhadap operasi memori di sekitarnya. Latensi paling rendah, namun rawan *data race* logis jika salah digunakan.

### 3.4 Lock-Free Primitives, ABA Problem & Safe Memory Reclamation
Struktur data *lock-free* mengeliminasi *mutex* untuk menghindari *deadlock*, *priority inversion*, dan *thread suspension overhead*. Inti dari *lock-free* adalah instruksi hardware atomik **CAS** (*Compare-And-Swap*):

$$\text{CAS}(\&addr, expected, new\_val) \to \text{boolean}$$

#### Fenomena ABA Problem
1. Thread 1 membaca pointer top dari lock-free stack: bernilai $A$. Pointer ke node berikutnya adalah $B$.
2. Thread 1 diinterupsi oleh OS scheduler (*preempted*).
3. Thread 2 melakukan *pop* $A$, melakukan *pop* $B$, lalu mengalokasikan memori baru yang secara kebetulan mendapatkan alamat virtual yang sama persis dengan $A$ ($A'$), lalu melakukan *push* $A'$.
4. Thread 1 melanjutkan eksekusi dan mengeksekusi $\text{CAS}(\&top, A, B)$.
5. Evaluasi CAS berhasil karena alamatnya sama-sama $A$. Namun, node $B$ mungkin sudah didealokasi atau diubah, menyebabkan *dangling pointer* atau korupsi struktur internal pointer stack.

**Mitigasi Arsitektural**:
- **Tagged Pointers / Double-Word CAS (DWCAS)**: Menggabungkan pointer (64-bit) dengan sequence counter monotonic (64-bit). Operasi CAS memvalidasi total 128-bit secara atomik.
- **Hazard Pointers**: Thread mendaftarkan pointer yang sedang aktif dibaca ke dalam daftar global agar thread lain tidak mendealokasikan node tersebut sebelum pembacaan tuntas.
- **Epoch-Based Reclamation (EBR)**: Memori hanya dibebaskan ke sistem ketika seluruh thread telah melewati batas generasi waktu (*epoch*) tertentu.

---

## 4. Why & What

| Dimensi | Struktur Konvensional (Lock-Based / Heap Nodes) | Struktur Lanjutan Berorientasi Hardware (*Hardware-Aligned*) |
| :--- | :--- | :--- |
| **Penyimpanan Memori** | Dispersi acak pada heap via alokator standar (`malloc`/`new`). | Kontigu, ter-*align* pada batas kelipatan 64-byte (*Cache Line Aligned*). |
| **Sinkronisasi Thread** | Pemblokiran via kernel (*Pthreads mutex*, *critical section*). | Primitif atomik tingkat hardware (*Lock-free ring buffers*, *CAS loops*). |
| **Pemanfaatan Cache** | Tingkat *Cache Miss* tinggi akibat fragmentasi pointer. | *High Cache Locality*, ramah *Hardware Prefetcher* dan vektorisasi SIMD. |
| **Throughput Skala Beban**| Menurun drastis saat terjadi perebutan gembok (*lock contention*). | Linear scaling terhadap ketersediaan Core CPU fisik. |
| **Tail Latency (p99/p99.9)**| Fluktuatif dan tinggi akibat pemblokiran OS *thread scheduler*. | Deterministik dan berada pada rentang sub-mikrodetik. |

---

## 5. How (Workflow Detail)

Alur perancangan struktur data konkuren produksi:

```
[Kebutuhan Sistem]
       |
       v
1. Analisis Akses Memori -> Pola Threading: Single-Producer Single-Consumer (SPSC)
                            atau Multi-Producer Multi-Consumer (MPMC)?
       |
       v
2. Tata Letak Memori     -> Alokasikan Flat Memory Buffer.
                            Terapkan Cache-Line Padding (alignas(64))
                            antara Write-Pointer dan Read-Pointer.
       |
       v
3. Model Konsistensi     -> Tentukan Memory Ordering:
                            Producer: store(..., std::memory_order_release)
                            Consumer: load(..., std::memory_order_acquire)
       |
       v
4. Mitigasi Alokasi      -> Zero-Allocation di Jalur Panas (Hot-path).
                            Pre-alokasikan seluruh memori buffer di fase inisialisasi.
       |
       v
5. Eksekusi CAS & Retry  -> Gunakan Exponential Backoff jika terjadi tabrakan tinggi
                            untuk meredakan saturasi bus CPU.
```

---

## 6. Analogy & Diagram ASCII

Bayangkan dua kasir (Thread A dan Thread B) bekerja di meja kasir terpisah namun berbagi satu buku catatan transaksi yang sama:

```
TANPA CACHE PADDING (False Sharing Terjadi):
+-----------------------------------------------------------------+
|                   Buku Catatan yang Sama (64-byte)              |
|   [Bagian Kasir A: Saldo A]    |    [Bagian Kasir B: Saldo B]   |
+-----------------------------------------------------------------+
Kasir A ingin menulis Saldo A -> Harus merebut SELURUH buku fisik.
Kasir B terhenti total (stalled), tidak bisa menulis Saldo B walau datanya terpisah!

DENGAN CACHE LINE PADDING (alignas(64)):
+------------------------------------+      +------------------------------------+
|  Buku Catatan Kasir A (64-byte)    |      |  Buku Catatan Kasir B (64-byte)    |
|  [Saldo A] + [Kertas Kosong Pad]   |      |  [Saldo B] + [Kertas Kosong Pad]   |
+------------------------------------+      +------------------------------------+
Kedua kasir menulis di buku fisik terpisah. Nol konflik fisik. Nol siklus terbuang!
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Mendemonstrasikan Dampak False Sharing & Solusinya

Berikut implementasi dalam C++20 yang menunjukkan secara eksplisit perbedaan antara struktur yang rentan *false sharing* versus yang menggunakan mitigasi *cache alignment*.

```cpp
#include <iostream>
#include <thread>
#include <vector>
#include <chrono>
#include <new>

// STRUKTUR RENTAN: Dua variabel berada dalam satu cache line (64 bytes)
struct FalseSharingTarget {
    uint64_t counter_a{0}; // 8 byte
    uint64_t counter_b{0}; // 8 byte
    // Sisa 48 byte otomatis diisi elemen berikutnya jika dialokasikan berdampingan
};

// STRUKTUR AMAN: Dipisahkan secara eksplisit ke cache line independen
struct alignas(64) CacheAlignedTarget {
    alignas(64) uint64_t counter_a{0};
    alignas(64) uint64_t counter_b{0};
};

void run_benchmark() {
    constexpr uint64_t ITERATIONS = 500'000'000;

    // 1. Uji Kasus False Sharing
    FalseSharingTarget bad_target;
    auto start_bad = std::chrono::high_resolution_clock::now();
    
    std::thread t1([&]() {
        for (uint64_t i = 0; i < ITERATIONS; ++i) {
            bad_target.counter_a++;
        }
    });

    std::thread t2([&]() {
        for (uint64_t i = 0; i < ITERATIONS; ++i) {
            bad_target.counter_b++;
        }
    });

    t1.join();
    t2.join();
    auto end_bad = std::chrono::high_resolution_clock::now();
    auto duration_bad = std::chrono::duration_cast<std::chrono::milliseconds>(end_bad - start_bad).count();

    // 2. Uji Kasus Cache Aligned
    CacheAlignedTarget good_target;
    auto start_good = std::chrono::high_resolution_clock::now();
    
    std::thread t3([&]() {
        for (uint64_t i = 0; i < ITERATIONS; ++i) {
            good_target.counter_a++;
        }
    });

    std::thread t4([&]() {
        for (uint64_t i = 0; i < ITERATIONS; ++i) {
            good_target.counter_b++;
        }
    });

    t3.join();
    t4.join();
    auto end_good = std::chrono::high_resolution_clock::now();
    auto duration_good = std::chrono::duration_cast<std::chrono::milliseconds>(end_good - start_good).count();

    std::cout << "[False Sharing] Waktu Eksekusi: " << duration_bad << " ms\n";
    std::cout << "[Cache Aligned] Waktu Eksekusi: " << duration_good << " ms\n";
    std::cout << "Peningkatan Efisiensi: " << (float)duration_bad / (float)duration_good << "x lipat\n";
}
```

### 7.2 Practical Example: Production-Grade SPSC Lock-Free Ring Buffer

Implementasi industri *Single-Producer Single-Consumer (SPSC) Queue* bebas alokasi dinamis (*zero dynamic allocation* di jalur kritis) dengan *Acquire-Release Memory Barriers* dan mitigasi *False Sharing*.

```cpp
#pragma once
#include <atomic>
#include <cstddef>
#include <new>
#include <optional>
#include <vector>
#include <concepts>

#ifndef __cpp_lib_hardware_interference_size
namespace std {
    constexpr std::size_t hardware_destructive_interference_size = 64;
}
#endif

template <typename T, size_t Capacity>
requires (Capacity > 1 && ((Capacity & (Capacity - 1)) == 0)) // Wajib Power of Two
class SPSCRingBuffer {
public:
    SPSCRingBuffer() 
        : head_(0), tail_(0), cached_tail_(0), cached_head_(0) {
        buffer_ = static_cast<T*>(::operator new[](Capacity * sizeof(T)));
    }

    ~SPSCRingBuffer() {
        T discarded;
        while (pop(discarded)) {}
        ::operator delete[](buffer_);
    }

    // Producer side
    bool push(const T& item) {
        const size_t current_head = head_.load(std::memory_order_relaxed);
        
        // Optimasi: Hindari membaca atomic tail_ secara berulang menggunakan cached_tail_
        if ((current_head - cached_tail_) == Capacity) {
            cached_tail_ = tail_.load(std::memory_order_acquire);
            if ((current_head - cached_tail_) == Capacity) {
                return false; // Buffer penuh
            }
        }

        // Tulis objek langsung pada in-place buffer (menggunakan bitwise AND mask)
        new (&buffer_[current_head & BUFFER_MASK]) T(item);
        
        // Publikasikan write dengan urutan release
        head_.store(current_head + 1, std::memory_order_release);
        return true;
    }

    // Consumer side
    bool pop(T& value) {
        const size_t current_tail = tail_.load(std::memory_order_relaxed);

        // Optimasi: Hindari membaca atomic head_ secara berulang menggunakan cached_head_
        if (current_tail == cached_head_) {
            cached_head_ = head_.load(std::memory_order_acquire);
            if (current_tail == cached_head_) {
                return false; // Buffer kosong
            }
        }

        // Pindahkan data keluar dari buffer
        size_t index = current_tail & BUFFER_MASK;
        value = std::move(buffer_[index]);
        buffer_[index].~T();

        // Publikasikan konsumsi dengan urutan release
        tail_.store(current_tail + 1, std::memory_order_release);
        return true;
    }

    [[nodiscard]] size_t size() const noexcept {
        size_t head = head_.load(std::memory_order_relaxed);
        size_t tail = tail_.load(std::memory_order_relaxed);
        return (head >= tail) ? (head - tail) : (Capacity - (tail - head));
    }

    [[nodiscard]] bool empty() const noexcept {
        return head_.load(std::memory_order_relaxed) == tail_.load(std::memory_order_relaxed);
    }

private:
    static constexpr size_t BUFFER_MASK = Capacity - 1;
    T* buffer_;

    // Variabel milik Producer dipisahkan pada Cache Line terpisah
    alignas(std::hardware_destructive_interference_size) std::atomic<size_t> head_;
    alignas(std::hardware_destructive_interference_size) size_t cached_tail_;

    // Variabel milik Consumer dipisahkan pada Cache Line terpisah
    alignas(std::hardware_destructive_interference_size) std::atomic<size_t> tail_;
    alignas(std::hardware_destructive_interference_size) size_t cached_head_;
};
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Ultra-Low Latency Trading Matching Engine (LMAX Disruptor Pattern)
- **Konteks Masalah**: Sebuah bursa komoditas finansial global memproses pesanan beli/jual (*Limit Orders*) dengan target SLA $p99 < 5\ \mu\text{s}$ (mikrodetik). Arsitektur lama berbasis Queue thread-safe bawaan dengan *Mutex Locking* mengalami lonjakan latensi (*latency spikes*) hingga $40\ \text{ms}$ akibat *lock contention* dan penumpukan *thread scheduling context-switches*.
- **Penyebab Utama**:
  1. Kontensi penguncian memicu pembekuan thread pada level OS kernel.
  2. Alokasi objek pesanan dinamis di heap memicu fragmentasi memori dan siklus *Garbage Collection/Memory Compaction*.
  3. Lokasi memori antrean tidak kontigu, memicu *cache line bounce* di seluruh core CPU server NUMA.
- **Solusi Rekayasa Lanjutan**:
  1. **Migrasi ke Lock-Free Ring Buffer Arsitektur Deterministik**: Mengimplementasikan buffer melingkar berukuran biner ($2^{22}$ slot) yang dialokasikan di awal (*pre-allocated memory*).
  2. **Isolasi Core CPU (CPU Pinning/Core Affinity)**: Thread Producer (penerima koneksi WebSocket jaringan) dan Consumer (Matching Engine Logic) dipin secara eksklusif ke Core fisik tertentu (`pthread_setaffinity_np`) guna mengeliminasi biaya *context switching*.
  3. **Struktur Data Order Book SoA (Structure of Arrays)**: Merombak buku pesanan dari representasi array pointer objek ke flat arrays terpisah untuk `Prices`, `Quantities`, dan `OrderIDs`. Hal ini memungkinkan loop pemindaian harga mengeksekusi instruksi vektor SIMD AVX-512.
- **Dampak Terukur**:
  - *Throughput* sistem melonjak dari $85.000\ \text{ops/detik}$ menjadi $6.200.000\ \text{ops/detik}$.
  - Latensi $p99.9$ terpangkas dari $45\ \text{ms}$ menjadi $1.4\ \mu\text{s}$.
  - Alokasi memori saat runtime stabil di angka **0 bytes/sec** (*zero-allocation steady state*).

---

## 9. Trade-offs

```
                       PERFORMA MAKSIMAL
                             /\
                            /  \
                           /    \
                          /      \
  [Lock-Free RingBuffer] /________\ [SoA Data Layout]
                        \        /
                         \      /
                          \    /
                           \  /
                        KOMPLEKSITAS
```

| Pendekatan Rekayasa | Keuntungan Utama | Kerugian / Biaya | Pertimbangan Konteks |
| :--- | :--- | :--- | :--- |
| **Lock-Free (Atomics/CAS)** | Tidak ada resiko deadlock, zero context-switch, latensi p99 rendah. | Kode sangat sulit diverifikasi kebenarannya; rawan ABA problem; biaya kompilasi kognitif tinggi. | Gunakan pada jalur komunikasi antar-thread frekuensi sangat tinggi (*hot-path core*). |
| **Mutex-Based (Locking)** | Sederhana, aman secara mental model, didukung tooling analisis OS (*ThreadSanitizer*). | Terdegradasi fatal di bawah kontensi tinggi; rawan *priority inversion*. | Gunakan pada komponen *cold-path* atau operasi I/O bervolume rendah. |
| **Structure of Arrays (SoA)** | Efisiensi SIMD optimal, kompresi cache line maksimal saat scanning data agregasi. | Manipulasi data individual (tambah/hapus entitas utuh) memerlukan update ke banyak array terpisah. | Gunakan untuk pemrosesan analitik, game engines, physics, dan *order matching*. |
| **Array of Structures (AoS)**| Mudah dipetakan ke konsep OOP (`User`, `Order`), mutasi atomic entitas lebih intuitif. | Banyak data *garbage* terbawa ke cache line saat mengeksekusi query kolom spesifik. | Gunakan untuk pemodelan data domain umum (*business CRUD domains*). |

---

## 10. Common Mistakes & Troubleshooting

### Kesalahan Umum
1. **Mengabaikan Volatile vs. Atomic**: Berasumsi bahwa keyword `volatile` pada C/C++ menyediakan proteksi *thread-safe*. `volatile` hanya mencegah compiler mengoptimasi pembacaan register, namun **sama sekali tidak** menyuntikkan *memory barrier* CPU atau menjamin atomisitas.
2. **Kelebihan Menggunakan Memory Barrier Terketat**: Memaksakan penggunaan `memory_order_seq_cst` di setiap atomik. Pada arsitektur non-x86 (seperti ARM64), hal ini memicu instruksi pembersihan pipeline yang sangat mahal (`DMB ISH`).
3. **ABA Trap pada Lock-Free Pointer Recycling**: Mengembalikan memori node ke alokator (`free`/`delete`) langsung di dalam antrean *lock-free* sebelum memastikan tidak ada thread pembaca lain yang memegang referensi ke alamat pointer tersebut.

### Panduan Troubleshooting Terstruktur
- **Gejala: Penurunan Performa Saat Menambah Core CPU**.
  - *Diagnosa*: Jalankan profiler Linux `perf`:
    ```bash
    perf c2c record ./aplikasi_biner
    perf c2c report --stdio
    ```
  - *Analisis*: Cari metrik **HITM** (*Hit Modified Cache Line*). Tingginya angka HITM mengindikasikan adanya *False Sharing*.
  - *Solusi*: Terapkan `alignas(64)` pada variabel yang diakses thread terpisah.
- **Gejala: Memory Leak Sporadis pada Lock-Free Queue**.
  - *Diagnosa*: Jalankan AddressSanitizer (`-fsanitize=address`) dan ThreadSanitizer (`-fsanitize=thread`).
  - *Solusi*: Implementasikan *Epoch-Based Reclamation* atau *Hazard Pointer* untuk siklus hidup dekonstruksi node.

---

## 11. Best Practices (Production Checklist)

1. [ ] **Memory Padding**: Pastikan semua counter/pointer atomic yang dimutasi oleh thread berbeda dipisahkan minimal $64\ \text{byte}$ (`std::hardware_destructive_interference_size`).
2. [ ] **Zero Dynamic Allocation**: Seluruh buffer, node pool, dan stack dialokasikan saat fase *bootstrap* (startup). Larang keras `malloc`, `new`, atau instansiasi heap di dalam *event-loop*.
3. [ ] **Bounded Capacity**: Selalu gunakan antrean terbatas (*bounded queue*) dengan ukuran kelipatan dua ($2^n$) guna memanfaatkan optimasi operasi bitwise modulo (`index & (size - 1)`).
4. [ ] **Memory Order Minimization**: Gunakan `memory_order_relaxed` untuk penghitung statistik internal dan `acquire/release` untuk sinkronisasi transfer kepemilikan data antar thread.
5. [ ] **CPU Pinning**: Ikat thread kritis ke inti CPU terisolasi melalui *CPU Affinity* untuk mencegah migrasi core oleh OS scheduler.
6. [ ] **Stress Testing via Valgrind/TSan**: Validasi ketiadaan *race condition* tersembunyi menggunakan Clang ThreadSanitizer sebelum merge ke cabang produksi.

---

## 12. Hands-on Practice

Simpan seluruh file praktikum ini di dalam repositori lokal pada path: `hands-on/m02/`

### File: `hands-on/m02/Makefile`
```makefile
CXX = g++
CXXFLAGS = -O3 -std=c++20 -pthread -Wall -Wextra

all: benchmark

benchmark: main.cpp
	$(CXX) $(CXXFLAGS) main.cpp -o benchmark

run: benchmark
	./benchmark

clean:
	rm -f benchmark
```

### File: `hands-on/m02/main.cpp`
```cpp
#include <iostream>
#include <thread>
#include <chrono>
#include <vector>
#include <atomic>
#include <cassert>

// Mengimpor implementasi SPSC Queue
#include "spsc_queue.hpp"

constexpr size_t QUEUE_SIZE = 1024 * 64; // Power of two
constexpr size_t TOTAL_OPERATIONS = 10'000'000;

void benchmark_spsc() {
    SPSCRingBuffer<uint64_t, QUEUE_SIZE> ring_buffer;
    
    std::cout << "Memulai benchmark SPSC Ring Buffer (" << TOTAL_OPERATIONS << " operasi)...\n";
    auto start_time = std::chrono::high_resolution_clock::now();

    // Producer Thread
    std::thread producer([&]() {
        for (uint64_t i = 1; i <= TOTAL_OPERATIONS; ++i) {
            while (!ring_buffer.push(i)) {
                // Polling aktif (Spinning) untuk latensi terendah
                #if defined(__x86_64__) || defined(_M_X64)
                asm volatile("pause");
                #endif
            }
        }
    });

    // Consumer Thread
    std::thread consumer([&]() {
        uint64_t received_val = 0;
        for (uint64_t i = 1; i <= TOTAL_OPERATIONS; ++i) {
            while (!ring_buffer.pop(received_val)) {
                #if defined(__x86_64__) || defined(_M_X64)
                asm volatile("pause");
                #endif
            }
            assert(received_val == i);
        }
    });

    producer.join();
    consumer.join();

    auto end_time = std::chrono::high_resolution_clock::now();
    auto total_ms = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time).count();
    double ops_per_sec = (double)TOTAL_OPERATIONS / ((double)total_ms / 1000.0);

    std::cout << "Selesai dalam: " << total_ms << " ms\n";
    std::cout << "Throughput: " << ops_per_sec / 1'000'000.0 << " Juta Operasi/detik\n";
}

int main() {
    benchmark_spsc();
    return 0;
}
```

### File: `hands-on/m02/spsc_queue.hpp`
*(Salin kode implementasi dari Bagian 7.2 ke file ini)*.

**Langkah Eksekusi Praktikum**:
```bash
cd hands-on/m02/
make
make run
```

---

## 13. Exercise

### Tingkat: Easy
- **Tugas**: Diberikan sebuah struktur data `struct Particle { float x, y, z; float vx, vy, vz; float mass; };`. Ubah struktur data sekumpulan 1.000.000 partikel dari format *Array of Structures* (`std::vector<Particle>`) menjadi format *Structure of Arrays* (`struct ParticleSystemSoA`). Tulis fungsi untuk memperbarui posisi (`x += vx`, dst.) dan ukur perbedaan waktu eksekusinya.
- **Ekspektasi Output**: Kode mampu mengompilasi loop pembaruan posisi dengan eksekusi minimal 2x lebih cepat pada SoA karena CPU Prefetcher memuat koordinat tanpa memuat metadata massa.

### Tingkat: Medium
- **Tugas**: Implementasikan **Treiber Stack** (Lock-Free Stack berbasis CAS). Tambahkan mekanisme mitigasi bahaya *ABA Problem* dengan menggunakan *Tagged Pointer* (menggabungkan alamat pointer 64-bit dan counter urutan 64-bit ke dalam `std::atomic<__int128>`).
- **Validasi**: Lakukan tes multi-thread di mana thread melakukan *Push* dan *Pop* secara agresif tanpa mengalami kerusakan referensi memori (*segmentation fault*).

### Tingkat: Hard
- **Tugas**: Rancang struktur data **MPMC (Multi-Producer Multi-Consumer) Bounded Queue** berbasis array kontigu yang terisi penuh secara berurutan.
- **Spesifikasi**:
  - Gunakan sequence number pada setiap slot buffer untuk mengoordinasikan apakah slot siap ditulis (Turn of Producer) atau siap dibaca (Turn of Consumer).
  - Terapkan exponential backoff pada CAS loop untuk mencegah saturasi inter-core bus ketika terjadi tabrakan antar 16 core konkuren.

---

## 14. Challenge

### Studi Kasus Arsitektural: Ultra-Scale In-Memory Sliding Window Rate Limiter
Rancang komponen *sliding window rate limiter* in-memory murni untuk layer API Gateway berkinerja ekstrem dengan batasan:
1. **Beban**: Wajib menangani 10.000.000 permintaan per detik dengan batasan tail latency $p99.99 < 100\ \mu\text{s}$.
2. **Kapasitas**: Melacak 500.000 Tenant ID unik secara konkuren. Setiap tenant dibatasi maksimal 10.000 request per jendela geser (*sliding window*) 1 detik.
3. **Keterbatasan Hardware**: Memori dibatasi maksimum 1 GB RAM fisik. Larang keras pemanggilan alokasi dinamis saat runtime (*hot-path*).
4. **Persyaratan Ketahanan**: Desain harus thread-safe tanpa menggunakan OS Lock tingkat kernel (`std::mutex` atau pthread mutex dilarang keras).

**Deliverable Desain**:
- Jelaskan arsitektur struktur data internal representasi rentang waktu dan penghitung (*misal: Ring Buffer of Sub-windows vs. Compressed Bitmap Counters*).
- Susun pemetaan memori struktural byte demi byte untuk memastikan batas memori 1 GB tidak dilanggar.
- Jelaskan secara matematis dan arsitektural bagaimana sistem menangani mutasi atomik saat dua core CPU mengeksekusi operasi penambahan token untuk tenant yang sama di nanodetik yang identik.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Basic Level (Pilihan Ganda)
1. Berapa ukuran tipikal sebuah *Cache Line* pada arsitektur prosesor x86-64 modern?
   - A. 16 Byte
   - B. 32 Byte
   - C. 64 Byte
   - D. 128 Byte
2. Apa yang dimaksud dengan fenomena *False Sharing*?
   - A. Dua thread mencoba menulis ke variabel logika yang sama secara bersamaan tanpa mutex.
   - B. Dua thread memodifikasi variabel berbeda yang kebetulan berada dalam satu cache line fisik yang sama.
   - C. Thread membaca data kotor dari DRAM karena cache L1 mati.
   - D. Kesalahan instruksi atomik yang membaca memori yang telah didealokasi.
3. Instruksi CPU atomik mana yang menjadi fondasi utama dari algoritma *Lock-Free*?
   - A. Load-Link / Store-Conditional
   - B. Compare-And-Swap (CAS)
   - C. Fetch-And-Add (FAA)
   - D. Semua benar.
4. Manakah model memori (*Memory Ordering*) yang memberikan performa throughput tertinggi namun tanpa jaminan sinkronisasi urutan instruksi di sekitarnya?
   - A. `std::memory_order_seq_cst`
   - B. `std::memory_order_acquire`
   - C. `std::memory_order_release`
   - D. `std::memory_order_relaxed`
5. Mengapa struktur data berbasis pointer terpisah (*Node-based List*) buruk bagi cache CPU?
   - A. Karena node memakan memori terlalu besar.
   - B. Karena alokasi memori yang tidak kontigu memicu tingginya *Cache Miss* (*pointer chasing*).
   - C. Karena pointer tidak dapat dibaca oleh arsitektur 64-bit.
   - D. Karena compiler menolak melakukan inlining method node.

### 15.2 Intermediate Level (Pertanyaan Terbuka & Diagnostik)
6. Jelaskan siklus transisi state protokol **MESI** ketika Core 1 menulis ke sebuah variabel yang saat itu berada di state **Shared (S)** di Core 1 dan Core 2!
7. Dalam konteks arsitektur SPSC Ring Buffer, mengapa variabel `head_` dan `tail_` wajib dipisahkan menggunakan `alignas(64)`? Apa dampak performa terukurnya jika padding ini dihilangkan?
8. Uraikan bagaimana skenario kegagalan data dapat terjadi akibat **ABA Problem** pada sebuah implementasi Lock-Free Stack sederhana!
9. Jelaskan perbedaan mendasar antara semantik sinkronisasi memori **Acquire** dan **Release**. Kapan masing-masing harus dipasangkan?
10. Mengapa transformasi struktur data dari *Array of Structures* (AoS) ke *Structure of Arrays* (SoA) mempermudah compiler mengeksekusi instruksi SIMD (*Single Instruction Multiple Data*)?

### 15.3 Skenario Kasus Produksi
11. **Skenario A**: Tim Anda memindahkan aplikasi multi-threaded dari server berbasis arsitektur x86 ke server berbasis ARM64 (misal: AWS Graviton). Tiba-tiba terjadi *data corruption* intermiten pada modul antrean lock-free yang sebelumnya berjalan sempurna di x86 selama bertahun-tahun. Telusuri akar masalah arsitektural penyebab hal ini!
12. **Skenario B**: Profiling produksi menggunakan `perf` menunjukkan metrik IPC (*Instructions Per Cycle*) aplikasi Anda sangat rendah (0.4 IPC), dengan metrik `L1-dcache-load-misses` mencapai 35%. Namun penggunaan CPU berada di 100%. Jelaskan interpretasi Anda terhadap status mesin tersebut dan langkah arsitektural apa yang harus diambil pada struktur data utama!
13. **Skenario C**: Sebuah antrean MPMC Lock-Free mengalami penurunan performa drastis hingga 80% saat beban konkurensi dinaikkan dari 4 thread menjadi 64 thread pada mesin NUMA dual-socket. Seluruh thread berputar (*spinning*) pada operasi CAS yang sama. Identifikasi fenomena ini dan rancang solusi perbaikannya!

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Kunci Pilihan Ganda (Basic)
1. **C** (64 Byte adalah standar de facto mayoritas prosesor x86 modern).
2. **B** (Definisi tepat dari *False Sharing*).
3. **D** (Semua instruksi tersebut adalah primitif hardware untuk sinkronisasi lock-free).
4. **D** (`memory_order_relaxed` mengeksekusi operasi atomik dengan biaya instruksi paling murah tanpa menyuntikkan memory barrier).
5. **B** (Node tersebar di heap acak, membatalkan prediksi hardware prefetcher).

#### Panduan Jawaban (Intermediate)
6. **Jawaban**: Core 1 mengirimkan pesan broadcast *Invalidate* ke inter-core bus. Core 2 mengubah status cache line-nya dari **S** (*Shared*) menjadi **I** (*Invalid*). Core 1 mengubah statusnya menjadi **M** (*Modified*) setelah menerima konfirmasi, lalu mengeksekusi modifikasi data di L1-nya.
7. **Jawaban**: Producer memodifikasi `head_` sementara Consumer memodifikasi `tail_`. Tanpa padding 64 byte, kedua variabel berada dalam satu cache line. Setiap operasi `push` oleh Producer akan membatalkan cache line milik Consumer dan sebaliknya (*ping-pong cache line bouncing*), menyebabkan degradasi throughput drastis hingga 5x–10x lipat.
8. **Jawaban**: Terjadi saat alamat node yang baru dialokasikan persis sama dengan node yang baru saja dihapus. CAS mengevaluasi kesamaan nilai alamat pointer (misal: `0xDEADBEEF`), berasumsi kondisi data tidak berubah sama sekali, padahal node perantara di bawahnya telah bergeser atau didealokasi, merusak integritas pointer internal struktur.
9. **Jawaban**: Operasi **Release** menjamin mutasi memori sebelumnya telah disinkronisasikan ke cache sebelum penulisan nilai atomik selesai. Operasi **Acquire** menjamin pembacaan memori berikutnya hanya melihat data setelah pembacaan atomik valid. Keduanya membentuk relasi *happens-before* kontraktual dua thread.
10. **Jawaban**: SIMD memproses data kontigu dalam register vektor (128-bit, 256-bit, atau 512-bit). Dalam SoA, elemen data sejenis (misal koordinat `X`) terletak berdampingan di memori, sehingga dapat langsung dimuat ke register vektor dalam satu instruksi memori (`_mm256_load_ps`), tanpa membutuhkan instruksi manipulasi register yang boros siklus (*gather/scatter*).

#### Panduan Solusi (Skenario Produksi)
11. **Analisis Skenario A**: Arsitektur prosesor x86 memiliki model memori hardware yang sangat kuat (*Strongly Ordered / TSO - Total Store Order*), di mana penataan ulang instruksi (*hardware reordering*) sangat minimal secara default. Sebaliknya, prosesor ARM64 menganut model memori yang lemah (*Weakly Ordered Memory*). Jika kode antrean sebelumnya menggunakan atomic `memory_order_relaxed` yang tidak sengaja bekerja aman di x86 berkat garansi hardware, kode tersebut akan gagal total di ARM64 karena CPU ARM menata ulang operasi baca-tulis secara agresif. Solusinya: Pasang secara disiplin semantik `memory_order_acquire` dan `memory_order_release`.
12. **Analisis Skenario B**: Mesin mengalami kondisi *Memory Stalling / Memory-Bound*. Penggunaan CPU 100% adalah semu; core CPU tidak melakukan komputasi aktif melainkan menghabiskan ratusan siklus menunggu data dari DRAM akibat *cache misses* (IPC 0.4 sangat rendah). Solusi: Rombak struktur data menjadi kontigu (*flat array-based*), ubah model traversal data dari pointer-based menjadi block-based, dan alokasikan array pada batas memori halaman besar (*Huge Pages*) untuk mengurangi TLB misses.
13. **Analisis Skenario C**: Terjadi fenomena **CAS Saturation / Cache Line Bouncing** di atas inter-socket interconnect (UPI/QPI) akibat arsitektur NUMA. Ketika 64 thread melakukan CAS atomik loop secara simultan pada satu lokasi memori bersama, bus koherensi memori saturasi total. Solusi:
    - Ubah topologi dari satu antrean global menjadi arsitektur terpartisi (*Partitioned / Sharded Queues*) per NUMA Node.
    - Sisipkan instruksi penundaan adaptif (*Exponential Backoff* dengan instruksi CPU `pause`) di dalam CAS retry loop untuk meredakan perebutan bus hardware.

---

## 16. Summary

Menguasai struktur data dan algoritma pada tingkat sistem produksi memerlukan pergeseran paradigma: dari sekadar memperhitungkan kompleksitas asimptotik Big-O matematis menjadi **penyelarasan mikroarsitektural hardware (*Mechanical Sympathy*)**. Performa puncak sistem latensi rendah (*low-latency*) tidak ditentukan oleh penurunan jumlah baris instruksi semata, melainkan oleh efisiensi traversal data di sepanjang hierarki cache CPU (L1/L2/L3), ketiadaan fenomena *False Sharing*, pemanfaatan tata letak memori modern (SoA vs AoS), serta pemilihan model konsistensi atomik tingkat rendah (*Acquire-Release vs Sequential Consistency*). Penerapan prinsip-prinsip ini memisahkan kode akademis dengan sistem backend skala enterprise yang mampu beroperasi deterministik di skala jutaan transaksi per detik.