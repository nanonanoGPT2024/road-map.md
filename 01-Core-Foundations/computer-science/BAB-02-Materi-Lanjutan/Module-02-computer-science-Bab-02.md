# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 01-Core-Foundations | **Topik:** Computer Science | **Bab:** 02 (BAB-02-Materi-Lanjutan)

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis Arsitektur Mikroprosesor Modern:** Menjelaskan secara mendalam hierarki memori fisik (L1/L2/L3 cache), protokol koherensi cache (*MESI/MOESI*), *cache line bouncing*, dan implikasi arsitektur *Non-Uniform Memory Access* (NUMA) terhadap latensi sistem.
2. **Menguasai Semantik Memori & Concurrency Primitives:** Mengimplementasikan algoritma bebas kunci (*lock-free*) dan bebas tunggu (*wait-free*) menggunakan operasi atomik (*Compare-And-Swap/CAS*), memahami *Memory Ordering* (Sequential Consistency, Acquire-Release, Relaxed), serta mengeliminasi bahaya *ABA Problem* dan *False Sharing*.
3. **Mendiagnosis & Mengeliminasi Kernel Overhead:** Menganalisis biaya *context switching*, *system calls*, dan *TLB misses*, serta merancang arsitektur berperforma tinggi berbasis *Kernel Bypass* (*io_uring*, eBPF, DPDK).
4. **Membangun Komponen Produksi Berskala Enterprise:** Mengembangkan struktur data antrean *Single-Producer Single-Consumer* (SPSC) *Lock-Free Ring Buffer* yang mematuhi prinsip *Mechanical Sympathy* dengan latensi sub-mikrodetik.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda harus memahami:
- Konsep dasar struktur data (Array, Linked List, Queue, Binary Tree) dan kompleksitas asimptotik ($O(n)$, $O(\log n)$).
- Pemrograman dasar multithreading: *Thread lifecycle*, *Race Conditions*, *Deadlocks*, dan primitif sinkronisasi dasar (*Mutex*, *Semaphore*).
- Konseptual dasar OS: Ruang memori virtual (*Virtual Memory*), *Paging*, dan siklus instruksi CPU dasar (*Fetch-Decode-Execute*).
- Kemampuan membaca dan menulis kode tingkat menengah dalam bahasa pemrograman sistem seperti modern C++ (C++17/20), Rust, atau Go.

---

## 3. Concept & Internal Architecture

Rekayasa perangkat lunak enterprise modern pada skala jutaan transaksi per detik (*ultra-low latency* dan *high-throughput*) tidak dapat lagi memperlakukan perangkat keras sebagai abstraksi kotak hitam (*black box*). Konsep ini dipopulerkan oleh Martin Thompson sebagai **Mechanical Sympathy**—pemahaman mendalam tentang bagaimana perangkat keras yang mendasarinya beroperasi agar perangkat lunak dapat dirancang selaras dengan mesin fisik.

```
+-----------------------------------------------------------------------+
|                             CPU SOCKET                                |
|                                                                       |
|  +-------------------------+             +-------------------------+  |
|  |         CORE 0          |             |         CORE 1          |  |
|  |  +-------------------+  |             |  +-------------------+  |  |
|  |  | Registers (~0.5ns)|  |             |  | Registers (~0.5ns)|  |  |
|  |  +-------------------+  |             |  +-------------------+  |  |
|  |  | L1 D-Cache (32KB) |  |             |  | L1 D-Cache (32KB) |  |  |
|  |  | (~1ns latensi)    |  |             |  | (~1ns latensi)    |  |  |
|  |  +-------------------+  |             |  +-------------------+  |  |
|  |  | L2 Cache (512KB)  |  |             |  | L2 Cache (512KB)  |  |  |
|  |  | (~3-4ns latensi)  |  |             |  | (~3-4ns latensi)  |  |  |
|  |  +-------------------+  |             |  +-------------------+  |  |
|  +-------------|-----------+             +-------------|-----------+  |
|                +-------------------+-------------------+              |
|                                    |                                  |
|                    +-------------------------------+                  |
|                    |   L3 Unified Cache (16-64MB)  |                  |
|                    |   (~10-20ns latensi)          |                  |
|                    +---------------+---------------+                  |
+------------------------------------|----------------------------------+
                                     | Interconnect Bus (UPI / Infinity Fabric)
                    +----------------+---------------+
                    |     Main Memory / DRAM (DDR4/5)|
                    |     (~60-100ns latensi)        |
                    +--------------------------------+
```

### A. Hierarki Memori & Cache Coherence (MESI)

Data dipindahkan antara *Main Memory* dan CPU bukan dalam bentuk *byte* tunggal, melainkan dalam blok berukuran tetap yang disebut **Cache Line** (standar arsitektur x86_64 dan ARM modern adalah **64 byte**).

Ketika beberapa *core* CPU membaca dan memodifikasi *memory address* yang sama, konsistensi data dijamin oleh perangkat keras melalui protokol **Cache Coherence**, salah satunya adalah **MESI**:
- **Modified (M):** Cache line hanya ada di cache saat ini dan bernilai kotor (*dirty*—berbeda dari data di DRAM). Core memiliki hak eksklusif untuk menulis.
- **Exclusive (E):** Cache line hanya ada di cache saat ini, tetapi bersih (*clean*—identik dengan data di DRAM).
- **Shared (S):** Cache line ada di cache saat ini dan mungkin ada di cache core lain. Data bersih. Hanya boleh dibaca (*read-only*).
- **Invalid (I):** Cache line tidak berisi data valid; pembacaan akan memicu *cache miss*.

#### Cache Line Bouncing & False Sharing
Jika Core 0 memperbarui variabel $A$, dan Core 1 memperbarui variabel $B$, namun $A$ dan $B$ berada di dalam blok 64-byte yang sama (*Cache Line* yang sama):
1. Core 0 ingin menulis ke $A$: Mengirim sinyal invalidasi melalui interkoneksi CPU bus ke Core 1. Cache line Core 1 berubah menjadi **Invalid (I)**.
2. Core 1 ingin menulis ke $B$: Mengalami *cache miss*, meminta saluran memori memuat ulang cache line dari Core 0, dan mengubah statusnya menjadi **Invalid** di Core 0.
Fenomena bolak-balik kepemilikan cache line antar core ini disebut **Cache Line Bouncing** akibat **False Sharing**, yang dapat menurunkan throughput komputasi multithreaded hingga 90-95%.

### B. Memory Ordering & Semantik Atomics

Kompilator (*compiler*) dan CPU melakukan optimasi agresif seperti *out-of-order execution*, *store buffering*, dan *speculative execution*. Akibatnya, urutan eksekusi instruksi perakitan (*assembly*) tidak selalu sama dengan urutan penulisan kode sumber.

Dalam sistem konkurensi enterprise, kita mengandalkan **Memory Ordering Guarantees**:
1. **Sequential Consistency (`memory_order_seq_cst`):** Standar bawaan. Memaksa urutan total yang identik di semua thread. Aman, namun membutuhkan *memory fence* tingkat perangkat keras yang mahal.
2. **Acquire-Release Semantics (`memory_order_acquire`, `memory_order_release`):**
   - **Store-Release:** Menjamin semua operasi pembacaan/penulisan memori sebelum rilis tidak dapat disusun ulang (*reordered*) setelah titik rilis.
   - **Load-Acquire:** Menjamin semua operasi pembacaan/penulisan memori setelah akuisisi tidak dapat disusun ulang sebelum titik akuisisi.
   - Pola ini membentuk sinkronisasi antar-thread langsung secara *peer-to-peer* tanpa overhead *global synchronization*.
3. **Relaxed Semantics (`memory_order_relaxed`):** Hanya menjamin atomisitas modifikasi variabel itu sendiri, tanpa sinkronisasi urutan memori terhadap variabel lain.

### C. Kernel Space vs. User Space & Abstraksi Kernel Bypass

Eksekusi perangkat lunak tradisional melalui OS kernel memiliki batas biaya (*overhead*):
- **System Call Overhead:** Transisi CPU privilege ring dari Ring 3 (User Space) ke Ring 0 (Kernel Space) menghabiskan ratusan siklus CPU.
- **Context Switch:** Pergantian thread melibatkan penyimpanan register arsitektural, manipulasi *scheduler runqueue*, dan flusing sebagian atau seluruh *Translation Lookaside Buffer* (TLB).
- **Arsitektur Kernel Bypass (Modern Solution):** Untuk menghindari interupsi kernel, aplikasi intensif I/O (seperti perbankan frekuensi tinggi dan telekomunikasi) menggunakan teknologi seperti:
  - **`io_uring`:** Ring buffer asinkron bersama antara User Space dan Kernel Space di Linux.
  - **eBPF:** Program terverifikasi yang berjalan langsung di dalam kernel tanpa overhead modul eksternal.
  - **DPDK / SPDK:** Driver level User Space yang melakukan polling langsung ke NIC (Network Interface Card) atau NVMe, memotong subsistem kernel TCP/IP atau blok secara penuh.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional (Lock-based / Mutex) | Pendekatan Rekayasa Performa Tinggi (Lock-Free & Mechanical Sympathy) |
| :--- | :--- | :--- |
| **Mekanisme Sinkronisasi** | `pthread_mutex`, `std::sync::Mutex`, Java `synchronized`. Menidurkan thread (*futex wait*) saat terjadi kontensi. | Primitif atomik CPU (`CMPXCHG`, `LDREX/STREX`), Memory Barries, Ring Buffers. |
| **Latensi P99.9** | **Tinggi & Tidak Stabil (Unbounded):** Bergantung pada waktu bangun OS Scheduler (bisa $5\mu s - 10ms$). | **Rendah & Deterministik:** Latensi konstan berskala sub-mikrodetik ($< 100ns$). |
| **CPU Utilization** | Sering berada pada status `iowait` atau siklus terbuang saat *context switching*. | Core beroperasi pada performa maksimal (100% throughput murni) atau mode polling adaptif. |
| **Resistensi Deadlock** | Rentan terhadap *deadlock*, *livelock*, dan *priority inversion*. | Secara matematis kebal terhadap *deadlock* (*Non-blocking guarantees*). |
| **Cache Efficiency** | Buruk. *Lock metadata* sering berbagi ruang dengan data struktural, memicu *False Sharing*. | Optimal. Data dialokasikan dengan *explicit alignment* dan *padding* 64-byte sesuai arsitektur cache line. |

---

## 5. How (Workflow detail)

Berikut alur kerja atomik pada operasi pembacaan dan penulisan dalam sebuah buffer antrean bebas-kunci (*Lock-Free SPSC Ring Buffer*) dengan semantik memori *Acquire-Release*:

```
[Producer Thread (Core 0)]                      [Consumer Thread (Core 1)]
           |                                                |
1. Baca 'tail' (local register)                  1. Baca 'head' (local register)
2. Baca 'cached_head'                            2. Baca 'cached_tail'
   - Jika penuh:                                    - Jika kosong:
     Muat 'head' atomik (Acquire)                     Muat 'tail' atomik (Acquire)
     Evaluasi ulang kapasitas                         Evaluasi ketersediaan
           |                                                |
3. Tulis data ke slots[tail & mask]                         |
   (Operasi Memori Biasa)                                   |
           |                                                |
4. Komit 'tail' atomik (Release)                            |
   - Memori Flush / Store Buffer Drain                      |
   - Nilai baru tampak bagi Core 1                          |
           |                                                |
           +------------ Interconnect Bus Cache Inval ------>
                                                            |
                                                 3. Muat 'tail' atomik (Acquire)
                                                    - Melihat slot aman dibaca
                                                 4. Baca data dari slots[head & mask]
                                                 5. Komit 'head' atomik (Release)
```

1. **Inisialisasi Buffer:** Mengalokasikan array melingkar berukuran $2^n$ untuk memungkinkan operasi modulo berbasis *bitwise AND* (`index & (size - 1)` alih-alih `index % size` yang memakan belasan siklus instruksi CPU).
2. **Dekorasi Cache Line Padding:** Meletakkan struktur penunjuk (*pointer/index*) `head` dan `tail` pada blok memori terpisah dengan `alignas(64)` agar berada pada *cache line* independen.
3. **Eksekusi Penulisan Produsen:**
   - Menghitung kapasitas yang tersisa tanpa interupsi OS.
   - Menulis elemen muatan (*payload*) ke dalam array buffer slot.
   - Memperbarui variabel posisi `tail` menggunakan instruksi *Atomic Store* dengan `std::memory_order_release`.
4. **Eksekusi Pembacaan Konsumen:**
   - Membaca posisi `tail` menggunakan *Atomic Load* dengan `std::memory_order_acquire`.
   - Mengambil data dari slot array yang valid.
   - Memperbarui variabel posisi `head` dengan `std::memory_order_release`.

---

## 6. Analogy & Diagram ASCII

### Analogi: Meja Administrasi Dua Sisi vs Pintu Putar Berbayar

Bayangkan sebuah loket administrasi berkas:
- **Lock-based (Mutex):** Terdapat sebuah pintu masuk tunggal yang dikunci dengan satu kunci fisik. Siapapun yang ingin memproses berkas harus mengantre merebut kunci tersebut. Jika petugas di dalam pingsan (*thread unscheduled/preempted* oleh OS), semua orang di luar harus berhenti menunggu tanpa kepastian batas waktu.
- **Lock-Free SPSC (Prinsip Ring Buffer):** Terdapat meja bundar berputar di antara dua ruangan terpisah dinding kaca.
  - Petugas A (Produsen) hanya menaruh dokumen ke kotak bernomor dan memutar papan nomor dokumen terakhir yang ia letakkan.
  - Petugas B (Konsumen) di seberang kaca melihat papan nomor berputar, mengambil berkas, dan memutar penanda dokumen yang sudah selesai ia ambil.
  - Tidak ada satupun yang saling menyentuh, tidak ada kunci fisik, dan keduanya dapat bekerja secara kontinu pada kecepatan penuh masing-masing.

### Diagram Arsitektur Memory Layout: False Sharing vs Cache-Aligned

```
SKENARIO 1: FALSE SHARING TERJADI (Performa Anjlok)
===================================================================
Cache Line Core 0 & Core 1 (64 Bytes yang dibagi bersama)
+------------------------------------+----------------------------+
|  head_index (8B) [Core 0 Modifies] | tail_index (8B) [Core 1]   |
+------------------------------------+----------------------------+
       |                                          |
       V                                          V
Core 0 Invalidate Line! ------------> Core 1 Cache Stalled! (Reload)

SKENARIO 2: CACHE-ALIGNED DENGAN PADDING (Mechanical Sympathy)
===================================================================
Cache Line A (Core 0 - 64 Bytes)
+------------------------------------+----------------------------+
|  head_index (8B)                   | Explicit Padding (56B)     |
+------------------------------------+----------------------------+
[Core 0 menulis ke Cache Line A tanpa interupsi ke Cache Line B]

Cache Line B (Core 1 - 64 Bytes)
+------------------------------------+----------------------------+
|  tail_index (8B)                   | Explicit Padding (56B)     |
+------------------------------------+----------------------------+
[Core 1 menulis ke Cache Line B secara independen tanpa Cache Bouncing]
```

---

## 7. Simple Example & Practical Example

### Simple Example: Demonstrasi Biaya False Sharing (Benchmark Pattern)

Berikut adalah pengujian minimal dalam modern C++20 yang mendemonstrasikan degradasi performa akibat *False Sharing* dibandingkan dengan struktur yang terisolasi menggunakan *cache-line padding* (`alignas(64)`).

```cpp
#include <iostream>
#include <thread>
#include <chrono>
#include <vector>

// Struktur rentan: Kedua variabel berada pada 64-byte chunk yang sama
struct FalseSharingTarget {
    uint64_t core0_counter{0};
    uint64_t core1_counter{0};
};

// Struktur optimal: Variabel diisolasi ke cache line masing-masing
struct AlignedTarget {
    alignas(64) uint64_t core0_counter{0};
    alignas(64) uint64_t core1_counter{0};
};

constexpr uint64_t ITERATIONS = 500'000'000;

template <typename T>
void run_benchmark(const std::string& label) {
    T target;
    auto start = std::chrono::high_resolution_clock::now();

    std::thread t1([&]() {
        for (uint64_t i = 0; i < ITERATIONS; ++i) {
            target.core0_counter++;
        }
    });

    std::thread t2([&]() {
        for (uint64_t i = 0; i < ITERATIONS; ++i) {
            target.core1_counter++;
        }
    });

    t1.join();
    t2.join();

    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double, std::milli> elapsed = end - start;
    std::cout << "[" << label << "] Waktu Eksekusi: " << elapsed.count() << " ms\n";
}

int main() {
    run_benchmark<FalseSharingTarget>("False Sharing Contended");
    run_benchmark<AlignedTarget>("Cache-Aligned Padded");
    return 0;
}
```

### Practical Example: Production-Grade SPSC Lock-Free Ring Buffer

Implementasi *Single-Producer Single-Consumer* (SPSC) Ring Buffer ultra-low latency siap produksi menggunakan modern C++20 dengan optimasi *cache-line alignment* dan semantik *Acquire-Release*.

```cpp
#ifndef SPSC_RING_BUFFER_HPP
#define SPSC_RING_BUFFER_HPP

#include <atomic>
#include <cstddef>
#include <new>
#include <utility>
#include <optional>
#include <vector>
#include <stdexcept>

#if defined(__cpp_lib_hardware_interference_size)
    using std::hardware_destructive_interference_size;
#else
    // Standar de-facto ukuran x86/ARM64 cache line
    constexpr size_t hardware_destructive_interference_size = 64;
#endif

template <typename T>
class SPSCRingBuffer {
public:
    explicit SPSCRingBuffer(size_t capacity)
        : capacity_(round_up_to_power_of_two(capacity)),
          mask_(capacity_ - 1),
          ring_buffer_(static_cast<T*>(::operator new[](sizeof(T) * capacity_))) {
        if (capacity < 2) {
            throw std::invalid_argument("Kapasitas buffer minimal 2");
        }
    }

    ~SPSCRingBuffer() {
        // Membersihkan elemen yang belum terkonsumsi
        size_t head = head_.load(std::memory_order_relaxed);
        size_t tail = tail_.load(std::memory_order_relaxed);
        while (head != tail) {
            ring_buffer_[head & mask_].~T();
            head++;
        }
        ::operator delete[](ring_buffer_);
    }

    // Larang operasi copy untuk menghindari duplikasi status buffer
    SPSCRingBuffer(const SPSCRingBuffer&) = delete;
    SPSCRingBuffer& operator=(const SPSCRingBuffer&) = delete;

    template <typename... Args>
    bool emplace(Args&&... args) {
        const size_t current_tail = tail_.load(std::memory_order_relaxed);
        
        // Optimasi: Hindari membaca atomic head_ jika kita tahu masih ada ruang dari cache lokal
        if ((current_tail - cached_head_) >= capacity_) {
            cached_head_ = head_.load(std::memory_order_acquire);
            if ((current_tail - cached_head_) >= capacity_) {
                return false; // Buffer penuh
            }
        }

        new (&ring_buffer_[current_tail & mask_]) T(std::forward<Args>(args)...);
        
        // Mempublikasikan slot baru dengan store-release
        tail_.store(current_tail + 1, std::memory_order_release);
        return true;
    }

    std::optional<T> pop() {
        const size_t current_head = head_.load(std::memory_order_relaxed);

        // Optimasi: Evaluasi apakah antrean kosong menggunakan cached_tail
        if (current_head == cached_tail_) {
            cached_tail_ = tail_.load(std::memory_order_acquire);
            if (current_head == cached_tail_) {
                return std::nullopt; // Buffer kosong
            }
        }

        T* value_ptr = &ring_buffer_[current_head & mask_];
        std::optional<T> result(std::move(*value_ptr));
        value_ptr->~T();

        // Mengabarkan pembebasan slot dengan store-release
        head_.store(current_head + 1, std::memory_order_release);
        return result;
    }

    [[nodiscard]] size_t capacity() const noexcept {
        return capacity_;
    }

private:
    static size_t round_up_to_power_of_two(size_t val) {
        size_t res = 1;
        while (res < val) res <<= 1;
        return res;
    }

    const size_t capacity_;
    const size_t mask_;
    T* const ring_buffer_;

    // Isolasi state produsen ke dalam satu cache line khusus
    alignas(hardware_destructive_interference_size) std::atomic<size_t> tail_{0};
    size_t cached_head_{0}; // Hanya diakses oleh Produsen

    // Isolasi state konsumen ke dalam cache line terpisah
    alignas(hardware_destructive_interference_size) std::atomic<size_t> head_{0};
    size_t cached_tail_{0}; // Hanya diakses oleh Konsumen
};

#endif
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Matching Engine Ultra-Low-Latency Financial Exchange (Bursa Saham)

* **Skala Sistem:** 5.000.000 transaksi pesanan per detik (*orders/sec*) dengan SLA latensi P99.99 berada di bawah $2.5\mu s$.
* **Masalah Awal Arsitektur:** Arsitektur lama berbasis Java/C++ konvensional dengan *Thread Pool* yang menggunakan antrean `std::mutex` atau `BlockingQueue`. Terjadi lonjakan latensi (*latency jitter*) acak mencapai $50ms$ saat lonjakan volume pasar (*market surge*), menyebabkan kegagalan eksekusi arbitrase keuangan.
* **Akar Masalah:**
  1. *Futex lock contention* menyebabkan core CPU memasuki status tidur (*kernel sleep*) dan context switch.
  2. Fragmentasi memori dan garbage collection pauses (pada node tertentu).
  3. *Cache-line bouncing* pada status penunjuk antrean pesanan global.

```
ARSITEKTUR LOKET TRANSAKSI BURSA KEUANGAN:
[Network Interface Card (NIC)]
           |
      DPDK Poll-Mode Driver (Core 1 - Kernel Bypass)
           |
    [SPSC Lock-Free Ring Buffer 1] (Isolasi Cache Line 64-byte)
           V
[Order Validation Engine] (Core 2 - Pinned)
           |
    [SPSC Lock-Free Ring Buffer 2]
           V
[Order Book Matching Engine] (Core 3 - Pinned, Single Writer)
           |
    [SPSC Lock-Free Ring Buffer 3]
           V
[Market Data Publisher Engine] (Core 4 - Multicast UDP)
```

* **Solusi Arsitektur Baru:**
  1. **Thread-per-Core Pinning:** Setiap komponen arsitektur diikat ke core fisik tertentu menggunakan `pthread_setaffinity_np()`, mengeliminasi biaya context switch dan menjaga L1/L2 data cache tetap *warm*.
  2. **Pipeline SPSC Disruptor Pattern:** Antar core hanya berkomunikasi melalui satu arah menggunakan *SPSC Lock-Free Ring Buffer* yang telah diselaraskan dengan ukuran cache.
  3. **Kernel Bypass Network I/O:** Menerapkan DPDK (*Data Plane Development Kit*) sehingga *Core 1* langsung membaca frame Ethernet dari *ring buffer* hardware NIC ke user-space memory tanpa system call `recv()`.
* **Hasil:**
  - Throughput naik dari 350.000 ops/sec menjadi 7.800.000 ops/sec.
  - Latensi P99.99 turun secara drastis dari $48.2ms$ menjadi $1.8\mu s$.
  - Biaya konsumsi CPU turun 40% karena peniadaan lock contention dan system calls.

---

## 9. Trade-offs

| Pendekatan / Keputusan Arsitektur | Keuntungan Utama | Kerugian / Konsekuensi Negatif | Kasus Penggunaan Tepat |
| :--- | :--- | :--- | :--- |
| **Lock-Free SPSC / MPMC** | Menghilangkan latensi OS kernel switch; throughput sangat tinggi; bebas deadlock. | Sangat rumit untuk dirawat dan diuji (*race conditions* halus); rentan membuang daya jika polling agresif. | High-Frequency Trading, Sistem Telemetri Game Engine, Media Streaming Real-Time. |
| **Lock-Based (Mutex / RWLock)** | Sederhana, aman secara semantik, CPU tidak mengonsumsi daya saat status idle (*blocked*). | Latensi P99.9 tidak menentu; throughput terbatas di bawah kontensi tinggi; rawan deadlock. | Aplikasi web skala umum, pemrosesan batch tradisional, I/O database standar. |
| **Core Pinning (`taskset`)** | L1/L2 cache hit rasio mendekati 100%; isolasi latensi deterministik. | Menghilangkan fleksibilitas OS scheduler; core terikat tidak dapat dimanfaatkan proses lain. | Core engine transaksi, pemrosesan audio ultra-low latency, gateway jaringan. |
| **Kernel Bypass (DPDK/io_uring)** | Memotong *overhead* system call dan salinan data memori ganda (*zero-copy*). | Kehilangan proteksi keamanan bawaan kernel; debugging sulit; hardware vendor-dependent. | Infrastruktur Cloud Provider, Packet Inspection, Storage Engine NVMe tingkat lanjut. |

---

## 10. Common Mistakes & Troubleshooting

### 1. The ABA Problem pada Desain CAS (Compare-And-Swap)
* **Penyebab:** Thread 1 membaca nilai $A$ dari pointer. Thread 2 menyela, mengubah nilai menjadi $B$, membebaskan memori objek $A$, mengalokasikan objek baru yang kebetulan menempati alamat memori yang sama persis, dan mengubahnya kembali menjadi nilai $A$. Thread 1 melanjutkan eksekusi, menjalankan instruksi `atomic_compare_exchange_weak(&ptr, A, C)`, dan berhasil secara keliru karena alamatnya masih tampak sama, meskipun status logis internal objek telah berubah total.
* **Gejala:** Kerusakan struktur memori (*memory corruption*), *use-after-free*, atau pointer liar (*dangling pointer*).
* **Solusi Enterprise:** Gunakan struktur *Tagged Pointer* / *Double-Word CAS* (DWCAS) dengan menambahkan counter modifikasi 64-bit pada pointer, atau terapkan *Hazard Pointers* / *Epoch-Based Reclamation* (EBR).

### 2. Penggunaan Semantik Memori `std::memory_order_relaxed` yang Ceroboh
* **Penyebab:** Menganggap instruksi `relaxed` aman hanya karena bersifat atomik. Padahal, kompiler dan CPU bebas memindahkan operasi pembacaan/penulisan data non-atomik di sekitar instruksi tersebut.
* **Gejala:** Konsumen membaca data setengah jadi (*garbage/partial state*) yang belum selesai ditulis produsen meskipun flag penanda sudah bernilai `true`.
* **Solusi:** Selalu gunakan pasangan `memory_order_release` saat mempublikasikan data dan `memory_order_acquire` saat membaca flag ketersediaan data.

### 3. Profiling False Sharing Menggunakan Linux `perf c2c`
Ketika performa multithreaded anjlok saat beban kerja bertambah, jangan menebak lokasi masalah. Gunakan subsistem profiling perangkat keras:
```bash
# 1. Rekam jejak Cache-to-Cache (c2c) akses memori pada aplikasi target
perf c2c record -F 60000 -- ./high_throughput_service

# 2. Analisis laporan visual kontensi cache line
perf c2c report --stdio
```
**Analisis Output:**
Cari metrik `HITM` (*Hit Modified Cache Line*). Jika sebuah *data offset* menghasilkan angka `Remote HITM` atau `Local HITM` yang tinggi, variabel tersebut sedang mengalami *Cache Line Bouncing* akibat *False Sharing*.

---

## 11. Best Practices (Production Checklist)

### Development Phase
- [ ] Terapkan *alignment* minimum 64-byte (`alignas(64)`) pada variabel antrean yang diakses oleh thread berbeda guna mencegah False Sharing.
- [ ] Gunakan ukuran buffer berorde kelipatan dua ($2^n$) untuk menggantikan operasi pembagian/modulo `%` dengan operator bitwise `&`.
- [ ] Hindari alokasi memori dinamis (`malloc`, `new`) di dalam *hot execution path*. Alokasikan seluruh memori di muka (*pre-allocation/memory pool*) saat fase inisialisasi aplikasi.
- [ ] Hindari dependensi pada `std::memory_order_seq_cst` kecuali benar-benar diperlukan untuk memvalidasi konsistensi global mutlak; gunakan `acquire-release` secara cermat.

### Deployment & Infrastructure Phase
- [ ] **CPU Isolation:** Konfigurasikan kernel parameter pada file `/etc/default/grub` dengan instruksi `isolcpus=2-7 nohz_full=2-7 rcu_nocbs=2-7` untuk mendedikasikan core CPU khusus aplikasi tanpa interupsi OS timer tick.
- [ ] **Thread Pinning:** Pastikan konfigurasi *affinity* mengikat thread kritis ke NUMA node yang memiliki bus memori lokal yang sama.
- [ ] **HugePages Allocation:** Aktifkan *Transparent Huge Pages* (THP) atau alokasikan *1GB/2MB Static HugePages* untuk meminimalkan *TLB misses* pada alokasi buffer berukuran besar.

---

## 12. Hands-on Practice

Buat dan simpan seluruh kode pengujian ini di dalam direktori `hands-on/m02/` pada environment pengembangan Anda.

### Langkah 1: Persiapan Struktur Direktori
```bash
mkdir -p hands-on/m02
cd hands-on/m02
```

### Langkah 2: Buat File `main.cpp`
Tuliskan implementasi benchmark interaktif yang menguji performa throughput antara SPSC Ring Buffer dan Mutex-based Queue:

```cpp
// hands-on/m02/main.cpp
#include <iostream>
#include <thread>
#include <chrono>
#include <queue>
#include <mutex>
#include <condition_variable>
#include <atomic>
#include <vector>

constexpr size_t TOTAL_OPS = 10'000'000;
constexpr size_t BUFFER_SIZE = 65536;

// --- 1. Lock-based Queue ---
template <typename T>
class MutexQueue {
public:
    void push(T val) {
        std::unique_lock<std::mutex> lock(mtx_);
        q_.push(val);
        cv_.notify_one();
    }

    T pop() {
        std::unique_lock<std::mutex> lock(mtx_);
        cv_.wait(lock, [&]() { return !q_.empty(); });
        T val = q_.front();
        q_.pop();
        return val;
    }
private:
    std::queue<T> q_;
    std::mutex mtx_;
    std::condition_variable cv_;
};

// --- 2. Ultra-Fast SPSC Cache-Aligned Ring Buffer ---
template <typename T, size_t Size>
class SimpleSPSC {
    static_assert((Size & (Size - 1)) == 0, "Size harus kelipatan pangkat 2");
public:
    bool push(const T& val) {
        const size_t t = tail_.load(std::memory_order_relaxed);
        if ((t - head_.load(std::memory_order_acquire)) == Size) {
            return false;
        }
        buffer_[t & (Size - 1)] = val;
        tail_.store(t + 1, std::memory_order_release);
        return true;
    }

    bool pop(T& val) {
        const size_t h = head_.load(std::memory_order_relaxed);
        if (h == tail_.load(std::memory_order_acquire)) {
            return false;
        }
        val = buffer_[h & (Size - 1)];
        head_.store(h + 1, std::memory_order_release);
        return true;
    }

private:
    T buffer_[Size];
    alignas(64) std::atomic<size_t> tail_{0};
    alignas(64) std::atomic<size_t> head_{0};
};

int main() {
    std::cout << "Memulai Komparasi: Mutex Queue vs SPSC Lock-Free (" 
              << TOTAL_OPS << " operasi)...\n";

    // Benchmark Mutex Queue
    {
        MutexQueue<int64_t> mq;
        auto start = std::chrono::high_resolution_clock::now();
        std::thread prod([&]() {
            for (int64_t i = 0; i < TOTAL_OPS; ++i) mq.push(i);
        });
        std::thread cons([&]() {
            for (int64_t i = 0; i < TOTAL_OPS; ++i) mq.pop();
        });
        prod.join();
        cons.join();
        auto end = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double> dur = end - start;
        std::cout << "Mutex Queue Time: " << dur.count() << " detik | Throughput: " 
                  << (TOTAL_OPS / dur.count()) / 1e6 << " M ops/sec\n";
    }

    // Benchmark Lock-Free SPSC
    {
        SimpleSPSC<int64_t, BUFFER_SIZE> spsc;
        auto start = std::chrono::high_resolution_clock::now();
        std::thread prod([&]() {
            for (int64_t i = 0; i < TOTAL_OPS; ++i) {
                while (!spsc.push(i)) {
                    #if defined(__x86_64__) || defined(_M_X64)
                    __builtin_ia32_pause();
                    #endif
                }
            }
        });
        std::thread cons([&]() {
            int64_t val = 0;
            for (int64_t i = 0; i < TOTAL_OPS; ++i) {
                while (!spsc.pop(val)) {
                    #if defined(__x86_64__) || defined(_M_X64)
                    __builtin_ia32_pause();
                    #endif
                }
            }
        });
        prod.join();
        cons.join();
        auto end = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double> dur = end - start;
        std::cout << "Lock-Free SPSC Time: " << dur.count() << " detik | Throughput: " 
                  << (TOTAL_OPS / dur.count()) / 1e6 << " M ops/sec\n";
    }

    return 0;
}
```

### Langkah 3: Kompilasi dengan Optimasi Maksimal
Gunakan flag optimasi tinggi `-O3` dan instruksi native CPU:
```bash
g++ -O3 -std=c++20 -march=native -pthread main.cpp -o benchmark_runner
```

### Langkah 4: Jalankan dan Analisis Hasil
```bash
./benchmark_runner
```

**Ekspektasi Output Terminal:**
```text
Memulai Komparasi: Mutex Queue vs SPSC Lock-Free (10000000 operasi)...
Mutex Queue Time: 3.4215 detik | Throughput: 2.9226 M ops/sec
Lock-Free SPSC Time: 0.1284 detik | Throughput: 77.8816 M ops/sec
```

---

## 13. Exercise

### Level Easy
1. Modifikasi kode implementasi `SPSCRingBuffer` di atas agar dapat melaporkan apakah antrean dalam status `empty()` atau `size()` secara atomik menggunakan semantik memori `relaxed`.
   * **Kriteria Keberhasilan:** Fungsi `size()` tidak menghasilkan data balikan bernilai negatif ketika produsen dan konsumen berjalan pada thread paralel.

### Level Medium
2. Tambahkan strategi back-off adaptif pada produsen ketika buffer penuh. Jika penulisan gagal setelah 100 kali iterasi CPU pause (`_mm_pause()`), thread produsen harus melakukan *exponential backoff* singkat sebelum melakukan `std::this_thread::yield()`.
   * **Kriteria Keberhasilan:** Penggunaan konsumsi CPU thread yang terhambat dapat ditekan tanpa mengorbankan rata-rata latensi saat buffer kembali memiliki ruang.

### Level Hard
3. Buat program benchmarking yang mengevaluasi performa pengiriman pesan lintas NUMA node menggunakan utilitas `numactl`. Ukur rasio latensi transfer memori ketika Thread Produsen dan Thread Konsumen dialokasikan pada satu *NUMA Node* lokal yang sama, dibandingkan dialokasikan pada dua *NUMA Node* fisik yang berbeda.
   * **Kriteria Keberhasilan:** Mahasiswa menyajikan visualisasi data yang membuktikan adanya penalti latensi sebesar 2x hingga 3x akibat transit interkoneksi bus UPI/Infinity Fabric antar-soket prosesor.

---

## 14. Challenge

Rancang arsitektur struktur antrean **Multi-Producer Multi-Consumer (MPMC) Bounded Lock-Free Queue** yang mengimplementasikan algoritma Dmitri Vyukov:
1. Antrean harus menggunakan array berukuran tetap $2^n$.
2. Setiap sel dalam array slot harus memiliki status urutan (*sequence atomic variable*) tersendiri untuk mengoordinasikan hak baca dan hak tulis bagi beberapa producer dan consumer sekaligus.
3. Seluruh slot array dan kontrol pointer harus dilindungi dari *ABA Problem* dan terisolasi dari *False Sharing*.
4. **Batasan Ketat:** Tidak boleh ada satupun *System Call* atau primitif *Mutex/Futex* yang digunakan. Lakukan verifikasi throughput hingga 8 Produsen dan 8 Konsumen secara simultan.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic (5 Pertanyaan)
1. Berapakah ukuran standar satu *Cache Line* pada arsitektur CPU x86_64 dan ARM64 modern?
   - A. 16 Byte
   - B. 32 Byte
   - C. 64 Byte
   - D. 128 Byte
2. Kondisi di mana dua variabel independen terletak pada cache line yang sama dan dimodifikasi oleh core CPU berbeda sehingga performa menurun drastis disebut:
   - A. Cache Miss Inevitability
   - B. False Sharing
   - C. Race Hazarding
   - D. Pipeline Stall
3. Status apa dalam protokol koherensi MESI yang mengindikasikan bahwa data cache line bersifat valid, hanya dimiliki oleh satu core, dan identik dengan data di memori utama?
   - A. Modified (M)
   - B. Exclusive (E)
   - C. Shared (S)
   - D. Invalid (I)
4. Mengapa operasi modulo `index % capacity` dihindari dalam jalur komputasi performa tinggi (*hot path*)?
   - A. Karena kapasitas array tidak boleh bernilai ganjil.
   - B. Karena instruksi pembagian hardware (`DIV`) memakan belasan hingga puluhan siklus CPU dibandingkan bitwise AND (`&`).
   - C. Karena bitwise AND secara otomatis mengunci memori core.
   - D. Modulo menyebabkan fragmentasi heap memory.
5. Manakah fungsi dari instruksi assembly `PAUSE` (`_mm_pause` / `__builtin_ia32_pause`) dalam *spin-wait loop* pada prosesor Intel/AMD?
   - A. Mematikan daya core untuk menghemat baterai secara permanen.
   - B. Mengalihkan eksekusi thread ke kernel scheduler.
   - C. Mencegah *memory order violation* dan mengurangi konsumsi daya pipa eksekusi saat CPU melakukan polling konstan.
   - D. Menghapus seluruh isi L1 cache.

---

### Bagian B: Intermediate (5 Pertanyaan)
6. Manakah konfigurasi semantik pengurutan memori (*memory ordering*) yang benar saat menerapkan pola Produsen-Konsumen pada variabel atomik agar data yang dipublikasikan tampak utuh?
   - A. Produsen menulis dengan `relaxed`, Konsumen membaca dengan `relaxed`.
   - B. Produsen menulis dengan `release`, Konsumen membaca dengan `acquire`.
   - C. Produsen menulis dengan `acquire`, Konsumen membaca dengan `release`.
   - D. Produsen menulis dengan `consume`, Konsumen membaca dengan `relaxed`.
7. Apa penyebab utama terjadinya *ABA Problem* pada algoritma antrean bebas-kunci (*lock-free*) berbasis *Linked List* yang menggunakan operasi Compare-And-Swap (CAS)?
   - A. Compiler menghapus pointer karena optimasi dead-code elimination.
   - B. Sistem kehabisan alokasi ruang swap pada hard disk.
   - C. Alokator memori mengalokasikan ulang memori pada alamat yang sama persis untuk node baru setelah node lama di-deallocate.
   - D. Ukuran pointer melebihi lebar register 64-bit CPU.
8. Apa dampak negatif yang paling nyata terhadap performa CPU saat terjadi perpindahan thread (*context switch*) secara masif dalam frekuensi tinggi?
   - A. Terjadinya invalidasi total pada Translation Lookaside Buffer (TLB) dan hilangnya lokalitas data pada L1/L2 Cache (*Cold Cache*).
   - B. Register CPU kehilangan integritas bit data sehingga harus di-reset.
   - C. DRAM bus controller mengalami overheating dan menurunkan frekuensi clock.
   - D. Thread otomatis mengalami *Deadlock*.
9. Dalam perancangan arsitektur berorientasi data (*Data-Oriented Design*), mengapa representasi *Structure of Arrays* (SoA) seringkali jauh lebih ramah terhadap performa cache CPU dibandingkan *Array of Structures* (AoS)?
   - A. SoA membutuhkan kapasitas hard disk yang lebih kecil.
   - B. SoA memungkinkan hardware prefetcher memuat data sejenis secara berurutan (*contiguous*) ke cache line tanpa membuang bandwidth untuk membaca field yang tidak relevan.
   - C. AoS tidak dapat dibaca oleh arsitektur CPU 64-bit.
   - D. SoA secara otomatis mengeliminasi kebutuhan memory barrier.
10. Apa keunggulan arsitektur subsistem I/O Linux `io_uring` dibandingkan pemanggilan *System Call* tradisional berbasis `epoll` atau `select`?
    - A. `io_uring` menghapus kebutuhan partisi hard disk.
    - B. Komunikasi dilakukan melalui dua antrean ring buffer bersama di user-space memory, mengeliminasi kebutuhan transisi privilege kernel ring untuk setiap operasi submission dan completion.
    - C. `io_uring` bekerja pada firmware BIOS secara langsung.
    - D. `io_uring` mematikan sistem proteksi memory paging Linux.

---

### Bagian C: Skenario Kasus Produksi (3 Pertanyaan)
11. **Skenario Kasus 1:**
    Sebuah aplikasi *crypto trading engine* yang berjalan di Linux multi-socket Xeon menunjukkan fenomena aneh: Pada Core 0-3, latensi eksekusi order berada di kisaran $800ns$, namun secara acak melonjak menjadi $3.2\mu s$ ketika thread pemrosesan dipindahkan oleh scheduler ke Core 16-20. 
    *Pertanyaan:* Berdasarkan analisis arsitektur internal komputer, apa diagnosis paling logis terhadap akar masalah tersebut, dan konfigurasi apa yang harus diterapkan untuk menstabilkannya?

12. **Skenario Kasus 2:**
    Sebuah tim software engineer mengimplementasikan metrik penghitung global atomik (`std::atomic<uint64_t> metrics_counter`) yang di-increment secara serentak oleh 64 worker threads di bawah beban trafik ekstrim. Meskipun mereka menggunakan operasi `fetch_add(1, std::memory_order_relaxed)` yang sangat cepat, performa CPU utilization mencapai 100% sementara throughput transaksi anjlok parah.
    *Pertanyaan:* Fenomena tingkat perangkat keras apa yang sedang terjadi di antara core-core prosesor, dan arsitektur data apa yang seharusnya digunakan untuk mengatasi masalah tersebut?

13. **Skenario Kasus 3:**
    Dalam audit sistem komunikasi perbankan berbasis kernel-bypass, ditemukan bahwa thread konsumsi data jaringan (*Consumer Loop*) melakukan *spin-polling* terus menerus pada slot memori NIC tanpa jeda. Ketika server mengalami peningkatan suhu mendadak (*thermal throttling*), latensi pengolahan transaksi justru memburuk hingga dua kali lipat.
    *Pertanyaan:* Mengapa teknik spin-polling agresif tanpa strategi back-off/pause dapat merusak latensi saat menghadapi kondisi saturasi termal, dan langkah perbaikan apa yang harus dimasukkan ke dalam loop eksekusi?

---

### Kunci Jawaban & Pembahasan Quiz

#### Kunci Jawaban Bagian A
1. **C (64 Byte):** Pada prosesor x86-64 dan ARMv8/v9 umum, ukuran standar satu cache line adalah 64 byte.
2. **B (False Sharing):** Terjadi ketika variabel independen berada pada cache line 64-byte yang sama, memicu invalidasi cache bolak-balik.
3. **B (Exclusive - E):** Status E menandakan bahwa core ini adalah satu-satunya pemilik salinan data tersebut di seluruh cache, dan datanya identik dengan DRAM.
4. **B:** Instruksi pembagian hardware (`idiv`) memiliki latensi komputasi tinggi (10-40 cycle), sedangkan operasi bitwise AND hanya memakan 1 cycle.
5. **C:** Instruksi `PAUSE` menginstruksikan CPU untuk menunda pemuatan spekulatif di pipeline, menghemat daya dan menghindari penalti *memory order violation* saat keluar dari loop.

#### Kunci Jawaban Bagian B
6. **B (Produsen Store-Release, Konsumen Load-Acquire):** Ini adalah fondasi formalisasi sinkronisasi memori (happens-before relationship) untuk memastikan semua penulisan data sebelum rilis terlihat utuh oleh thread yang melakukan akuisisi.
7. **C:** Alokasi ulang memori di alamat yang sama membuat operasi CAS berpikir bahwa objek tidak pernah dimodifikasi, padahal status logisnya sudah berbeda.
8. **A:** Context switch memaksa OS menyimpan state register, mengganti tabel halaman memori, dan memicu invalidasi TLB yang menyebabkan pembacaan memori berikutnya menjadi lambat (*cold cache misses*).
9. **B:** SoA menjaga array data yang sedang diproses secara batch berada rapat bersebelahan di memori, memaksimalkan efisiensi *hardware prefetcher* dan kapasitas tampung tiap cache line.
10. **B:** `io_uring` mengandalkan sepasang *Submission Queue* (SQ) dan *Completion Queue* (CQ) yang dipetakan (*mmap*) ke user-space, meniadakan *context switch overhead* ke kernel space.

#### Kunci Jawaban & Analisis Bagian C (Skenario Kasus Produksi)
11. **Diagnosis & Solusi Kasus 1:**
    - **Akar Masalah:** Sistem mengalami penalti latensi **NUMA (Non-Uniform Memory Access)**. Core 16-20 berada pada Socket CPU 1, sedangkan alokasi memori buffer/data transaksi dialokasikan oleh Core 0-3 yang berada pada Socket CPU 0. Akses memori jarak jauh harus melintasi interkoneksi UPI/QPI, yang memiliki latensi 3x-4x lebih lambat daripada akses memori lokal (*Cross-Socket Traversal*).
    - **Solusi Produksi:** Gunakan `numactl --cpunodebind=0 --membind=0 ./trading_engine` atau ikat thread secara programatik menggunakan `pthread_setaffinity_np()` ke core pada soket fisik yang sama dengan node memori tempat data dialokasikan.
12. **Diagnosis & Solusi Kasus 2:**
    - **Akar Masalah:** Terjadi **Atomic Contention Extreme & Cache Line Bouncing Massal**. Meskipun semantiknya `relaxed`, penulisan nilai baru ke alamat memori tunggal oleh 64 core secara terus menerus memaksa interkoneksi CPU bus membombardir sinyal invalidasi MESI ke seluruh 63 core lainnya secara berulang-ulang, melumpuhkan interkoneksi bus prosesor.
    - **Solusi Produksi:** Ubah arsitektur metrik menjadi pola **Thread-Local Storage / Striped Counters** (seperti konsep `LongAdder` di Java atau array counter independen per-thread yang dialokasikan dengan padding 64-byte). Masing-masing thread hanya memodifikasi counter lokalnya sendiri tanpa kontensi. Saat metrik global ingin dibaca, jalankan agregasi penjumlahan (*gather read*) secara periodik.
13. **Diagnosis & Solusi Kasus 3:**
    - **Akar Masalah:** Spin-polling loop murni (tanpa instruksi jeda) membanjiri unit eksekusi CPU dengan eksekusi spekulatif yang salah, memaksa CPU bekerja pada temperatur maksimum sehingga memicu algoritma perlindungan hardware berupa *Thermal Throttling* (penurunan drastis frekuensi MHz CPU).
    - **Solusi Produksi:** 
      1. Sisipkan instruksi assembly `_mm_pause()` di setiap iterasi loop yang kosong untuk mendinginkan jalur pipa instruksi CPU.
      2. Terapkan strategi adaptif: Lakukan spin-polling selama sejumlah siklus mikro (misal $10\mu s$), jika belum ada paket data, turunkan agresivitas menggunakan sleep presisi mikrodetik atau tunggu event interupsi kernel secara elegan.

---

## 16. Summary

```
+-------------------------------------------------------------------------------+
|                       RINGKASAN ARSITEKTUR CORE CS TINGKAT LANJUT            |
+===============================================================================+
| 1. Mechanical Sympathy : Rancang software selaras dengan arsitektur hardware  |
|                          (Cache Line 64B, Branch Predictor, Prefetcher).      |
| ----------------------------------------------------------------------------- |
| 2. Cache Coherence     : Protokol MESI mengoordinasikan status antar-core;    |
|                          Cegah 'False Sharing' menggunakan explicit padding.  |
| ----------------------------------------------------------------------------- |
| 3. Memory Ordering     : Kuasai semantik Acquire-Release untuk performa       |
|                          optimal tanpa overhead 'Sequential Consistency'.     |
| ----------------------------------------------------------------------------- |
| 4. Lock-Free Design    : Gunakan SPSC / MPMC Ring Buffer untuk transmisi      |
|                          data antar-thread dengan determinisme sub-mikrodetik.|
| ----------------------------------------------------------------------------- |
| 5. OS Overhead Bypass  : Minimalkan System Calls, Context Switch, dan TLB     |
|                          misses menggunakan io_uring, DPDK, dan isolcpus.     |
+-------------------------------------------------------------------------------+
```

Memahami abstraksi perangkat lunak adalah syarat untuk membangun sistem, namun memahami **ketiadaan abstraksi pada lapisan fisik perangkat keras** adalah prasyarat mutlak untuk membangun sistem berskala enterprise yang tangguh, deterministik, dan berkinerja tinggi. Selalu ukur menggunakan alat profiling perangkat keras (*hardware counters/perf*) dan jangan mendasarkan keputusan optimasi latensi pada asumsi teoritis semata.