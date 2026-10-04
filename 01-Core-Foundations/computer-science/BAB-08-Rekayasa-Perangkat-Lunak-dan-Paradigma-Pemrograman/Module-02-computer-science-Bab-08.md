# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 01-Core-Foundations | **Bab 08:** Materi Lanjutan  
**Fokus Topik:** *High-Performance Lock-Free Concurrency, Cache-Conscious Memory Architecture, & Kernel-Bypass Primitives*

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Mendiagnosis dan Mengeliminasi Bottleneck Cache:** Mengidentifikasi fenomena *False Sharing* dan *Cache Thrashing* pada arsitektur SMP (*Symmetric Multiprocessing*) menggunakan profiler perangkat keras tingkat rendah (`perf c2c`).
2. **Menguasai Model Memori Perangkat Keras:** Membedakan semantik *Sequential Consistency*, *Acquire-Release*, dan *Relaxed Memory Ordering* pada arsitektur x86 (TSO - *Total Store Order*) dan ARM (Weakly Ordered).
3. **Mengimplementasikan Struktur Data Lock-Free Standar Industri:** Membangun *Single-Producer Single-Consumer* (SPSC) dan *Multi-Producer Multi-Consumer* (MPMC) *bounded queue* tanpa *mutex primitives*, bebas dari *data race*, dan terhindar dari *ABA Problem*.
4. **Mendesain Subsistem Zero-Copy Berkinerja Tinggi:** Menerapkan teknik *ring-buffer pinning*, *memory alignment* berorientasi *cache line*, dan pemanfaatan instruksi atomik CPU (CAS, LL/SC) untuk mencapai latensi sub-mikrodetik (*p99.99 < 1μs*).

---

## 2. Prerequisite
Untuk menyerap materi ini secara optimal, peserta wajib menguasai:
- **Arsitektur Komputer Dasar:** Register CPU, virtual memory, paging, interupsi hardware, dan hierarki memori (Register $\to$ L1/L2/L3 Cache $\to$ DRAM).
- **Sistem Operasi:** Thread scheduling, konteks switching cost, *POSIX threads* (`pthread`), dan *system call overhead* (`futex`, `read`, `write`).
- **Bahasa Pemrograman Tingkat Sistem:** Pemahaman mendalam tentang C++ (C++17/C++20) atau Rust mengenai *pointers*, *references*, memory layout (`sizeof`, `alignof`), dan pustaka `<atomic>` / `std::sync::atomic`.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Hierarki Cache & Cache Coherency (MESI Protocol)
Pada arsitektur prosesor modern, CPU tidak membaca data langsung dari DRAM per bita atau word, melainkan dalam satuan blok berukuran tetap yang disebut **Cache Line** (umumnya 64 byte pada x86-64 dan ARM64).

Ketika banyak *core* mengeksekusi thread yang memodifikasi data pada area memori yang berdekatan, koherensi antar-cache lokal (L1/L2) dipertahankan oleh protokol hardware berbasis bus snooping/directory, salah satunya adalah protokol **MESI**:
- **M (Modified):** Cache line hanya ada di cache lokal saat ini dan kotor (*dirty* - berbeda dari DRAM). Core memiliki hak eksklusif untuk menulis.
- **E (Exclusive):** Cache line hanya ada di cache lokal saat ini dan bersih (*clean* - identik dengan DRAM).
- **S (Shared):** Cache line ada di cache lokal ini dan mungkin ada di cache core lain. Berstatus *read-only*.
- **I (Invalid):** Isi cache line tidak valid dan tidak boleh dibaca.

```
+-------------------------------------------------------------+
|                      DRAM (Main Memory)                     |
+-------------------------------------------------------------+
                              ^
                              | (Bus Traffic / QPI / UPI)
+-------------------------------------------------------------+
|                        L3 Cache (LLC)                       |
+-------------------------------------------------------------+
          ^                                       ^
          |                                       |
+-------------------+                   +-------------------+
|   L2 Cache (Core 0)|                   |   L2 Cache (Core 1)|
+-------------------+                   +-------------------+
          ^                                       ^
          |                                       |
+-------------------+                   +-------------------+
|   L1 D-Cache (C0) |                   |   L1 D-Cache (C1) |
+-------------------+                   +-------------------+
          ^                                       ^
          | MESI: Invalidate Broadcast            | MESI: S -> I
+-------------------+                   +-------------------+
|      Core 0       |                   |      Core 1       |
|  [atomic_store]   |                   |  [stalled read]   |
+-------------------+                   +-------------------+
```

Jika Core 0 menulis ke variabel `A` dan Core 1 menulis ke variabel `B`, namun keduanya berada di dalam satu *cache line* 64-byte yang sama, Core 0 akan memancarkan sinyal *Invalidate* ke Core 1. Core 1 terpaksa membuang seluruh cache line miliknya (*state transition: Shared $\to$ Invalid*). Fenomena degradasi performa destruktif ini disebut **False Sharing**.

### 3.2 Hardware Memory Model & Memory Barriers
Kompiler modern dan CPU melakukan *instruction reordering* untuk memaksimalkan *Instruction-Level Parallelism* (ILP).

```
Instruksi Program (Program Order):
Store A = 1;
Store B = 1;

Kemungkinan Eksekusi CPU / Visibilitas Core Lain:
Core 1 melihat: Store B = 1 terlebih dahulu SEBELUM Store A = 1
```

Arsitektur prosesor memiliki model konsistensi memori yang berbeda:
- **x86/x64 (Strongly Ordered / TSO - Total Store Order):** Bebas dari *Store-Store Reordering*, *Load-Load Reordering*, dan *Load-Store Reordering*. Hanya satu reordering yang diizinkan oleh hardware: **Store-Load Reordering** (sebuah operasi write dapat ditunda di dalam *Store Buffer* lokal Core sementara operasi read berikutnya dieksekusi duluan).
- **ARM / POWER (Weakly Ordered):** Segala jenis reordering diizinkan secara default, kecuali jika dibatasi secara eksplisit menggunakan instruksi barrier/fence (`DMB`, `DSB`, `ISB`).

### 3.3 Formalisme C++11 Memory Ordering
Standardisasi C++11 mendefinisikan hubungan sinkronisasi memori matematika formal (*Happens-Before Relationship*):
1. **`memory_order_relaxed`:** Hanya menjamin atomisitas operasi pembacaan/penulisan variabel itu sendiri. Tidak ada jaminan ordering terhadap memori di sekitarnya.
2. **`memory_order_acquire`:** Tidak ada pembacaan atau penulisan dalam thread saat ini yang dapat di-reorder *sebelum* operasi ini. Digunakan saat operasi *read/lock*.
3. **`memory_order_release`:** Tidak ada pembacaan atau penulisan dalam thread saat ini yang dapat di-reorder *sesudah* operasi ini. Memastikan seluruh store sebelumnya terlihat oleh thread lain yang melakukan *acquire*. Digunakan saat operasi *write/unlock*.
4. **`memory_order_acq_rel`:** Kombinasi *acquire* dan *release* (umum digunakan untuk *Read-Modify-Write* / CAS).
5. **`memory_order_seq_cst` (Sequential Consistency):** Jaminan terketat. Memberlakukan *globally consistent total order* di seluruh core. Sangat mahal karena memaksa pengurasan (*flushing*) Store Buffer hardware menggunakan instruksi berat (contoh: `MFENCE` atau `LOCK CMPXCHG` pada x86).

---

## 4. Why & What

### Mengapa Pendekatan Tradisional (Mutex/Lock) Gagal di Skala Enterprise?
Penggunaan primitif sinkronisasi berbasis kernel (`std::mutex`, `pthread_mutex_t`) membawa sejumlah konsekuensi laten:
- **Konteks Switching Penalty:** Ketika thread mengalami kontensi pada *lock*, thread diubah statusnya menjadi suspended via syscall `futex`. Transisi User-to-Kernel space menghabiskan 1.000 hingga 3.000 siklus CPU (~1-5 mikrodetik), merusak cache TLB (*Translation Lookaside Buffer*), dan mencemari L1 cache.
- **Priority Inversion:** Thread berprioritas rendah yang memegang lock dapat menahan thread berprioritas ultra-tinggi jika thread berprioritas rendah tersebut di-preempt oleh OS.
- **Deadlock & Convoying:** Jika sebuah thread crash saat memegang lock, seluruh sistem akan terhenti (*hang*). *Lock convoying* terjadi ketika beberapa thread dengan kecepatan eksekusi sama terjebak dalam antrean lock yang sama secara periodik.

### Apa Solusinya?
**Lock-Free Programming** menjamin bahwa *setidaknya satu thread* dalam sistem selalu membuat kemajuan (*system-wide progress guarantee*) dalam jumlah langkah eksekusi yang terbatas, terlepas dari status thread lain.

Tingkatan jaminan konkurensi non-blocking:
1. **Obstruction-Free:** Sebuah thread dijamin melangkah maju jika dieksekusi secara terisolasi dari thread lain.
2. **Lock-Free:** Setidaknya satu thread dijamin membuat kemajuan secara global pada interval waktu apa pun.
3. **Wait-Free:** *Setiap* thread dijamin menyelesaikan operasinya dalam sejumlah langkah terbatas, tanpa mempedulikan contention (paling ideal untuk sistem *Hard Real-Time*).

---

## 5. How (Workflow Detail)

Alur kerja sinkronisasi data antar-thread menggunakan semantik Acquire-Release pada lock-free ring-buffer:

```
[ Thread 1: Producer ]                           [ Thread 2: Consumer ]
         |                                                 |
1. Tulis data ke Buffer Index X                            |
   (Plain Store: buffer[head] = data)                     |
         |                                                 |
2. Eksekusi Store-Release pada Head Pointer                |
   head.store(next, memory_order_release)                 |
         |                                                 |
   ==================== [ MEMORY FENCE ] ====================
   Semua instruksi data store (langkah 1) dipaksa selesai 
   dan terlihat oleh core lain sebelum langkah 2 dipublikasi.
   ==========================================================
         |                                                 |
         |         Hardware Inter-Core Link Bus            |
         +------------------------------------------------>|
                                                           |
                                      3. Eksekusi Load-Acquire pada Head Pointer
                                         current_head = head.load(memory_order_acquire)
                                                           |
                                      ==================== [ MEMORY FENCE ] ====================
                                      Data buffer di langkah 4 dipastikan HANYA dibaca
                                      SETELAH pembacaan head berhasil divalidasi.
                                      ==========================================================
                                                           |
                                      4. Konsumsi data dari Buffer Index X
                                         data = buffer[tail]
```

---

## 6. Analogy & Diagram ASCII

### Analogi Papan Tulis Kantor (MESI & Cache Line)
Bayangkan sebuah kantor dengan 4 orang analis (Core CPU). Di tengah ruangan ada buku besar (DRAM). Setiap analis memiliki papan tulis kecil di mejanya (L1 Cache). Papan tulis hanya bisa memuat 1 lembar kertas formulir yang terdiri dari 4 baris data (Cache line 64 byte).

- **Mutex:** Setiap kali seorang analis ingin melihat/mengubah satu baris, mereka mengunci pintu kantor, membuat 3 analis lain berhenti bekerja total dan keluar dari ruangan.
- **False Sharing:** Analis 1 menulis pada Baris A formulir miliknya. Protokol kantor mewajibkan jika ada coretan pada formulir, seluruh formulir di meja analis lain harus langsung dihapus (Invalidated). Akibatnya, Analis 2 yang sedang fokus membaca Baris B di formulir yang sama dipaksa berhenti, membuang kertasnya, dan meminta salinan baru dari buku besar, meskipun ia sama sekali tidak peduli pada Baris A!
- **Cache-Line Alignment:** Kita memisahkan Baris A dan Baris B ke lembar kertas terpisah (Padding). Analis 1 dan Analis 2 kini bisa mencoret lembar masing-masing secara bersamaan dengan kecepatan penuh tanpa saling mengganggu.

### Diagram Arsitektur Kontensi Cache Line vs Padded Cache Line

```
KASUS A: FALSE SHARING (Unpadded)
Memory Offset: 0x00                 0x08                                0x40 (64 Bytes)
              +--------------------+-----------------------------------+
Cache Line 0: | Core 0: Head (8B)  | Core 1: Tail (8B) | Unused Padding|
              +--------------------+-----------------------------------+
              [<-------------------- 1 Cache Line -------------------->]
Result: Core 0 memodifikasi 'Head' ---> Cache Line di Core 1 INVALID.
        Core 1 memodifikasi 'Tail' ---> Cache Line di Core 0 INVALID.
        Efek: Memory Bus Flooding, latensi melonjak 20x-50x.

----------------------------------------------------------------------------------

KASUS B: HARDWARE-ALIGNED (Cache-Conscious Architecture)
Memory Offset: 0x00                                                     0x40
              +--------------------------------------------------------+
Cache Line 0: | Core 0: Head (8B)  | Explicit Padding (56 Bytes)        |
              +--------------------------------------------------------+
              [<-------------------- Line 0 (Exclusive to Core 0) ---->]

Memory Offset: 0x40                                                     0x80
              +--------------------------------------------------------+
Cache Line 1: | Core 1: Tail (8B)  | Explicit Padding (56 Bytes)        |
              +--------------------------------------------------------+
              [<-------------------- Line 1 (Exclusive to Core 1) ---->]
Result: Zero invalidation cross-core. Operasi atomic berjalan pada L1/L2 Cache speed.
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Mutex CAS vs std::atomic CAS
Kode dasar yang mendemonstrasikan perbandingan operasi pembaruan nilai secara aman.

```cpp
#include <iostream>
#include <atomic>
#include <thread>
#include <vector>

// Implementasi Lock-Free Counter menggunakan Compare-And-Swap (CAS)
class LockFreeCounter {
private:
    std::atomic<uint64_t> value_{0};

public:
    void increment() {
        uint64_t current = value_.load(std::memory_order_relaxed);
        // CAS Loop: Nilai diperbarui hanya jika nilai saat ini masih sama dengan ekspektasi.
        // Jika gagal (diubah thread lain), 'current' di-reload otomatis secara atomik.
        while (!value_.compare_exchange_weak(current, current + 1,
                                             std::memory_order_release,
                                             std::memory_order_relaxed)) {
            // Spin-wait / retry loop
        }
    }

    uint64_t get() const {
        return value_.load(std::memory_order_acquire);
    }
};

int main() {
    LockFreeCounter counter;
    std::vector<std::thread> workers;

    for (int i = 0; i < 4; ++i) {
        workers.emplace_back([&counter]() {
            for (int j = 0; j < 100'000; ++j) {
                counter.increment();
            }
        });
    }

    for (auto& t : workers) {
        t.join();
    }

    std::cout << "Final Counter Value: " << counter.get() << std::endl;
    return 0;
}
```

### 7.2 Practical Example: Enterprise-Grade SPSC Lock-Free Circular Queue
Berikut adalah implementasi antrean sirkular *Single-Producer Single-Consumer* (SPSC) tanpa lock, *zero-allocation*, terlindung dari *false-sharing* menggunakan memory alignment eksplisit, dan memanfaatkan semantik *Acquire-Release*.

```cpp
#pragma once

#include <atomic>
#include <cstddef>
#include <new>
#include <optional>
#include <type_traits>
#include <utility>

// Menentukan ukuran cache-line standar prosesor modern (x86_64 / ARM64)
#if defined(__cpp_lib_hardware_interference_size)
    using std::hardware_destructive_interference_size;
#else
    // Fallback konstan jika compiler macro belum terdefinisi
    constexpr size_t hardware_destructive_interference_size = 64;
#endif

template <typename T, size_t Capacity>
class SPSCQueue {
    static_assert((Capacity & (Capacity - 1)) == 0, "Kapasitas harus berupa pangkat dua (Power of 2).");
    static_assert(std::is_nothrow_destructible_v<T>, "Tipe T harus nothrow destructible.");

public:
    SPSCQueue() : head_(0), tail_(0), head_cached_(0), tail_cached_(0) {
        // Alokasi memori mentah yang belum diinisialisasi
        storage_ = static_cast<Node*>(::operator new[](sizeof(Node) * Capacity, std::align_val_t{alignof(Node)}));
    }

    ~SPSCQueue() {
        T discarded;
        while (pop(discarded)) {
            // Hancurkan semua sisa objek yang belum dikonsumsi
        }
        ::operator delete[](storage_, std::align_val_t{alignof(Node)});
    }

    // Disable copy & move semantics
    SPSCQueue(const SPSCQueue&) = delete;
    SPSCQueue& operator=(const SPSCQueue&) = delete;
    SPSCQueue(SPSCQueue&&) = delete;
    SPSCQueue& operator=(SPSCQueue&&) = delete;

    template <typename... Args>
    bool emplace(Args&&... args) noexcept(std::is_nothrow_constructible_v<T, Args...>) {
        const size_t current_head = head_.load(std::memory_order_relaxed);

        // Optimasi: Gunakan cached copy dari tail untuk menghindari polling cache line konsumen
        if ((current_head - tail_cached_) == Capacity) {
            tail_cached_ = tail_.load(std::memory_order_acquire);
            if ((current_head - tail_cached_) == Capacity) {
                return false; // Queue Penuh
            }
        }

        // Konstruksi objek secara in-place di slot memori mentah
        new (&storage_[current_head & IndexMask].storage) T(std::forward<Args>(args)...);

        // Publikasikan head baru dengan semantik release
        head_.store(current_head + 1, std::memory_order_release);
        return true;
    }

    bool push(const T& item) noexcept(std::is_nothrow_copy_constructible_v<T>) {
        return emplace(item);
    }

    bool push(T&& item) noexcept(std::is_nothrow_move_constructible_v<T>) {
        return emplace(std::move(item));
    }

    bool pop(T& val) noexcept(std::is_nothrow_move_assignable_v<T>) {
        const size_t current_tail = tail_.load(std::memory_order_relaxed);

        // Optimasi: Gunakan cached copy dari head untuk menghindari polling cache line produsen
        if (current_tail == head_cached_) {
            head_cached_ = head_.load(std::memory_order_acquire);
            if (current_tail == head_cached_) {
                return false; // Queue Kosong
            }
        }

        Node& node = storage_[current_tail & IndexMask];
        T* item_ptr = reinterpret_cast<T*>(&node.storage);
        
        // Pindahkan data ke output parameter
        val = std::move(*item_ptr);
        item_ptr->~T(); // Jalankan destruktor manual

        // Publikasikan tail baru dengan semantik release
        tail_.store(current_tail + 1, std::memory_order_release);
        return true;
    }

    [[nodiscard]] bool empty() const noexcept {
        return tail_.load(std::memory_order_relaxed) == head_.load(std::memory_order_relaxed);
    }

    [[nodiscard]] size_t size() const noexcept {
        size_t h = head_.load(std::memory_order_relaxed);
        size_t t = tail_.load(std::memory_order_relaxed);
        return (h >= t) ? (h - t) : (Capacity - (t - h));
    }

private:
    static constexpr size_t IndexMask = Capacity - 1;

    struct Node {
        alignas(alignof(T)) std::byte storage[sizeof(T)];
    };

    // ALIGNMENT STRATEGY UNTUK MENCEGAH FALSE SHARING:
    // Setiap variabel yang dimodifikasi oleh thread yang berbeda diisolasi dalam 64-byte boundary terpisah.
    
    // Variabel milik Producer Thread
    alignas(hardware_destructive_interference_size) std::atomic<size_t> head_;
    size_t tail_cached_; // Hanya diakses oleh Producer

    // Variabel milik Consumer Thread
    alignas(hardware_destructive_interference_size) std::atomic<size_t> tail_;
    size_t head_cached_; // Hanya diakses oleh Consumer

    // Pointer ke buffer data (konstan setelah inisialisasi)
    alignas(hardware_destructive_interference_size) Node* storage_;
};
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Ultra Low-Latency Electronic Trading Matching Engine (LMAX Disruptor Pattern)
- **Konteks Masalah:** Sebuah bursa derivatif multinasional menghadapi lonjakan volume pasar saat rilis suku bunga Federal Reserve. Sistem *Order Matching Engine* warisan menggunakan arsitektur antrean multi-thread berbasis *Priority Blocking Queue* (Java Concurrency/Mutex locking).
- **Insiden Produksi:** Saat traffic mencapai 850.000 pesanan per detik, latensi rata-rata melompat dari 15 mikrodetik menjadi 180 milidetik (*p99* > 1,2 detik). Analisis profiler menunjukkan 82% waktu siklus CPU dihabiskan dalam status kernel `futex_wait` dan `lock_contention` akibat ribuan thread bersaing mengambil alih antrean buku pesanan.
- **Arsitektur Solusi:** Tim rekayasa mendesain ulang sistem menggunakan prinsip **Single-Writer Principle** dan **Ring-Buffer Lock-Free**:
  1. **Thread Affinity (CPU Pinning):** Thread *Network Ingestion Engine*, *Disruptor Sequencer*, dan *Order Execution Engine* masing-masing di-*pin* secara permanen ke satu core CPU fisik terisolasi (via `pthread_setaffinity_np` pada Linux dengan parameter kernel `isolcpus=2,4,6`).
  2. **Cache-Aligned Circular Ring-Buffer:** Seluruh antrean pesanan diganti menjadi *lock-free ring-buffer pre-allocated* 64MB tanpa garbage collection / dynamic allocation.
  3. **Zero-Copy Memory Semantics:** *Socket kernel bypass* (menggunakan Solarflare OpenOnload / DPDK) menulis data packet pasar langsung ke memori ring buffer userspace.
- **Hasil Metrik:**
  - Throughput stabil naik menjadi **6,2 juta transaksi per detik**.
  - Latensi *Deterministic Mean* terpangkas menjadi **650 nanodetik** ($0,65\ \mu\text{s}$).
  - Latensi *p99.99* ditekan di bawah **2,1 mikrodetik**, mengeliminasi *long tail latency* total di bawah kondisi beban ekstrim.

---

## 9. Trade-offs

| Parameter | Lock-Based Concurrency (`std::mutex`) | Lock-Free Concurrency (`CAS / Atomics`) | Single-Writer Pinned Architecture (Disruptor) |
|---|---|---|---|
| **P99.9 Latency** | Buruk ($> 500\ \mu\text{s}$ saat contention tinggi) | Menengah ($1 - 10\ \mu\text{s}$) | Ekstrem Rendah ($< 1\ \mu\text{s}$ deterministik) |
| **Throughput** | Terbatas oleh OS context-switch ceiling | Sangat tinggi, bergantung pada kontensi CAS | Maksimal (Mencapai batas teoritis bus memori CPU) |
| **CPU Utilization** | Rendah saat thread idle (tidur via interrupt OS) | Sangat tinggi jika menggunakan *spin-wait CAS* | 100% konsisten (Core dikorbankan khusus untuk polling terus-menerus) |
| **Kompleksitas Kode** | Rendah (Mudah dipelajari, dilindungi RAII) | Ekstrem Tinggi (Rentan race condition halus, memory ordering) | Menengah - Tinggi (Memerlukan restrukturisasi arsitektur sistem) |
| **Kebutuhan Hardware** | General hardware apa pun | Arsitektur CPU harus mendukung CAS/LL-SC | NUMA architecture, CPU isolation support, L3 unified cache |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 The ABA Problem
- **Gejala:** Thread A membaca nilai pointer `A`. Thread B menginterupsi, mengubah pointer menjadi `B`, menghancurkan `A`, mengalokasikan node baru yang kebetulan memiliki alamat memori yang sama persis (`A`), lalu menaruhnya kembali. Thread A kembali berjalan, mengeksekusi CAS: memori tampak sama, namun struktur internal node sebenarnya telah korup.
- **Solusi Produksi:** Gunakan **Tagged Pointers** (Pointer yang dibundel dengan counter 64-bit menggunakan operasi *double-word CAS* seperti `CMPXCHG16B` pada x86-64) atau gunakan mekanisme memori reklamasi canggih seperti **Hazard Pointers** atau **RCU (Read-Copy Update)**.

### 10.2 Relaxed Ordering Overuse
- **Gejala:** Developer berasumsi bahwa karena variabel bertipe `std::atomic`, maka seluruh operasi di sekitarnya aman menggunakan `memory_order_relaxed`.
- **Dampak:** Data race struktural. Variabel data dibaca sebelum pointer yang mempublikasikan data tersebut selesai ditulis oleh CPU pengirim akibat pipeline reordering.
- **Deteksi:** Jalankan program di bawah **ThreadSanitizer** (`-fsanitize=thread` pada Clang/GCC) di arsitektur non-x86 (seperti ARM64 atau simulator TSO) untuk mendeteksi *happens-before violations*.

### 10.3 Spin-Wait Thermal Throttling & Core Starvation
- **Gejala:** Melakukan *infinite while-loop* mengecek atomik tanpa henti.
- **Solusi:** Selalu sertakan instruksi penenang CPU di dalam spin loop:
  ```cpp
  while (!flag.load(std::memory_order_relaxed)) {
      #if defined(__x86_64__) || defined(_M_X64)
          _mm_pause(); // Mengurangi konsumsi daya dan mencegah memory pipeline clear penalty
      #elif defined(__aarch64__)
          asm volatile("yield");
      #endif
  }
  ```

---

## 11. Best Practices (Production Checklist)

- [ ] **Alokasi Padded:** Selalu lakukan verifikasi bahwa variabel yang dimodifikasi oleh thread berbeda terpisah dengan batas minimal `hardware_destructive_interference_size` (64 byte atau 128 byte).
- [ ] **Static Size Assertion:** Validasi ukuran dan perataan data menggunakan `static_assert(sizeof(MyStruct) == EXPECTED)` dan `static_assert(alignof(MyStruct) == 64)`.
- [ ] **Zero Heap Allocation di Hot-Path:** Jangan pernah memanggil `malloc`, `free`, `new`, atau resizing kontainer di dalam path eksekusi latensi kritis lock-free.
- [ ] **Gunakan Minimal Memory Order:** Mulai dari `memory_order_relaxed` jika benar-benar hanya butuh atomisitas variabel; gunakan `acquire-release` untuk publikasi data; **hindari** `seq_cst` kecuali terbukti matematis dibutuhkan untuk meminimalkan beban *full memory fence*.
- [ ] **Sanitizer Pipeline:** Wajibkan integrasi `-fsanitize=thread` (TSan) dan `-fsanitize=undefined` (UB-San) dalam test suite CI/CD.
- [ ] **Verifikasi Profiler Hardware:** Lakukan profiling beban kerja dengan perintah Linux:
  ```bash
  perf c2c record -F 60000 -- ./my_lock_free_binary
  perf c2c report --stdio
  ```
  Pastikan metrik *HITM (Hit in Modified Cache)* mendekati nol.

---

## 12. Hands-on Practice

Buatlah struktur folder praktikum di workspace Anda: `hands-on/m02/`.

### Langkah 1: Eksperimen Demonstrasi Dampak False Sharing
Simpan kode berikut sebagai `hands-on/m02/false_sharing_bench.cpp`:

```cpp
#include <iostream>
#include <thread>
#include <vector>
#include <chrono>

struct UnpaddedCounters {
    uint64_t counter_a{0};
    uint64_t counter_b{0}; // Berada di cache-line yang sama dengan counter_a
};

struct alignas(64) PaddedCounters {
    alignas(64) uint64_t counter_a{0};
    alignas(64) uint64_t counter_b{0}; // Terisolasi di cache-line yang berbeda
};

template <typename T>
void run_benchmark(const char* name) {
    T counters;
    constexpr uint64_t ITERATIONS = 1'000'000'000;

    auto start = std::chrono::high_resolution_clock::now();

    std::thread t1([&]() {
        for (uint64_t i = 0; i < ITERATIONS; ++i) {
            counters.counter_a++;
        }
    });

    std::thread t2([&]() {
        for (uint64_t i = 0; i < ITERATIONS; ++i) {
            counters.counter_b++;
        }
    });

    t1.join();
    t2.join();

    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double, std::milli> elapsed = end - start;
    std::cout << "[" << name << "] Waktu Eksekusi: " << elapsed.count() << " ms\n";
}

int main() {
    std::cout << "Memulai Cache Interference Benchmark...\n";
    run_benchmark<UnpaddedCounters>("Unpadded (False Sharing)");
    run_benchmark<PaddedCounters>("Padded (Hardware Aligned)");
    return 0;
}
```

### Langkah 2: Kompilasi dan Eksekusi
Jalankan kompilasi dengan optimasi release penuh:
```bash
cd hands-on/m02/
g++ -O3 -std=c++17 -pthread false_sharing_bench.cpp -o false_sharing_bench
./false_sharing_bench
```
*Observasi:* Perhatikan bahwa versi Padded berjalan **2x hingga 6x lebih cepat** dibandingkan versi Unpadded murni karena eliminasi *cache line invalidation storm*.

---

## 13. Exercise

### 13.1 Level Easy
Jelaskan mengapa kode berikut menghasilkan *undefined behavior* atau hasil data yang tidak deterministik, dan perbaiki tanpa menggunakan mutex:
```cpp
int data = 0;
std::atomic<bool> ready{false};

void producer() {
    data = 42;
    ready.store(true, std::memory_order_relaxed);
}

void consumer() {
    while (!ready.load(std::memory_order_relaxed));
    std::cout << data << std::endl;
}
```
*Kriteria Penerimaan:* Gunakan kombinasi `memory_order_release` dan `memory_order_acquire` pada posisi yang tepat dan jelaskan alasan formal pemilihannya.

### 13.2 Level Medium
Ubah implementasi `SPSCQueue` dari Bagian 7.2 agar mendukung metode `bulk_push` dan `bulk_pop` (memungkinkan penyisipan dan pengambilan array data secara bersamaan hingga sejumlah $N$ item).
*Kriteria Penerimaan:* 
- Operasi bulk tidak boleh memanggil `store` atau `load` atomik di dalam loop per item.
- Operasi pembaruan pointer atomik hanya boleh dieksekusi **satu kali** per operasi bulk untuk meminimalkan beban memori bus.

### 13.3 Level Hard
Implementasikan sebuah **Lock-Free Treiber Stack** yang tahan terhadap *ABA Problem* menggunakan prinsip **Tagged Pointer** (operasi `std::atomic<std::pair<Node*, uint64_t>>` atau struktur packed 128-bit atomic) yang berjalan mulus pada platform x86-64.
*Kriteria Penerimaan:*
- Harus lolos uji coba multi-thread agresif (minimal 8 thread serentak, 10 juta operasi push/pop).
- Tidak boleh mengalami *memory leak* (desain strategi *safe node reclamation* sederhana).

---

## 14. Challenge

**Skenario Rekayasa Produksi:**
Anda adalah Principal Architect pada perusahaan platform streaming real-time analytics. Sistem Anda menerima aliran telemetri IoT berukuran paket kecil (128 byte) dengan volume agregat sebesar **20 juta paket per detik** pada sebuah server bare-metal berspesifikasi Dual-Socket AMD EPYC (total 128 Core, 256 Thread, arsitektur NUMA multi-node).

**Tantangan Arsitektur:**
1. Desainlah arsitektur penanganan paket data dari NIC menuju ring-buffer hingga tahap pemrosesan parser internal dengan ketentuan:
   - Tidak boleh terjadi kontensi memori lintas Socket/NUMA node (*Cross-NUMA node penalty* mematikan performa).
   - Seluruh aliran data wajib bebas dari alokasi memori dinamis (`malloc`/`free`) setelah *bootstrap phase*.
   - Antrean data internal harus bertipe *Lock-Free/Wait-Free*.
2. Tuliskan dokumen spesifikasi teknis dan modul inti C++ (ringkasan kelas arsitektur utama) yang mengilustrasikan:
   - Pola *Per-Core NUMA-Local SPSC ring buffers*.
   - Strategi migrasi data work-stealing non-blocking jika terjadi ketidakseimbangan beban (*load imbalance*) antar core lokal.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic (5 Soal)
1. **Berapa ukuran umum satu baris cache (*cache line*) pada sebagian besar prosesor modern x86 dan ARM?**
   - A. 16 Byte
   - B. 32 Byte
   - C. 64 Byte
   - D. 128 Byte
   - *Jawaban & Penjelasan:* **C**. Standar industri de-facto untuk desktop dan server prosesor modern adalah 64 byte.

2. **Apa arti status 'I' dalam protokol koherensi cache MESI?**
   - A. Interrupted
   - B. Invalid
   - C. Isolated
   - D. Interleaved
   - *Jawaban & Penjelasan:* **B**. *Invalid* menandakan data pada cache line tersebut sudah basi (stale) akibat modifikasi di core lain dan tidak boleh dibaca.

3. **Manakah memory order berikut yang memberlakukan jaminan konsistensi global terketat namun membawa penalti performa tertinggi?**
   - A. `memory_order_relaxed`
   - B. `memory_order_consume`
   - C. `memory_order_acquire`
   - D. `memory_order_seq_cst`
   - *Jawaban & Penjelasan:* **D**. *Sequential Consistency* (`seq_cst`) memastikan seluruh thread melihat eksekusi dalam urutan global yang sama persis, mengharuskan *full memory barrier*.

4. **Operasi CPU atomik mendasar manakah yang menjadi pondasi utama sebagian besar algoritma lock-free?**
   - A. Read-After-Write (RAW)
   - B. Compare-And-Swap (CAS)
   - C. Test-Without-Set (TWS)
   - D. Context-Switch-Save (CSS)
   - *Jawaban & Penjelasan:* **B**. Operasi CAS secara atomik membandingkan nilai memori dengan ekspektasi dan mengubahnya ke nilai baru hanya jika cocok.

5. **Apa yang dimaksud dengan kondisi False Sharing?**
   - A. Dua thread mencoba mengunci mutex yang berbeda secara bersamaan.
   - B. Dua thread memodifikasi variabel independen yang terletak pada cache line yang sama.
   - C. Thread membaca data yang telah dihapus oleh garbage collector.
   - D. Hardware memalsukan kapasitas DRAM yang tersedia untuk kernel.
   - *Jawaban & Penjelasan:* **B**. False sharing adalah penurunan performa ketika core saling membatalkan cache line akibat variabel independen berada pada blok 64-byte yang sama.

### Bagian B: Intermediate (5 Soal)
6. **Mengapa instruksi `_mm_pause()` penting diletakkan di dalam spin-wait loop pada arsitektur Intel x86?**
   - A. Menghentikan program seketika untuk debugging.
   - B. Menghindari *memory order violation* dan menghemat daya komputasi core dengan memberi jeda siklus pipeline.
   - C. Memaksa context switch ke thread lain di level OS.
   - D. Membatalkan instruksi penulisan yang belum selesai di Store Buffer.
   - *Jawaban & Penjelasan:* **B**. `_mm_pause()` memberi petunjuk ke CPU bahwa thread sedang spinning, mencegah CPU merekam spekulasi eksekusi loop yang salah sehingga menghindari *pipeline flush penalty*.

7. **Pada antrean SPSC (Single Producer Single Consumer), apakah kita membutuhkan operasi CAS (Compare-And-Swap) untuk memperbarui pointer Head dan Tail?**
   - A. Ya, CAS selalu wajib untuk segala struktur data concurrent.
   - B. Tidak, cukup gunakan operasi *Load-Acquire* dan *Store-Release* biasa karena hanya ada satu thread penulis pada masing-masing pointer.
   - C. Ya, karena jika tidak menggunakan CAS, memori DRAM akan korup.
   - D. Tidak, operasi non-atomic tanpa pembungkus apa pun sudah cukup aman.
   - *Jawaban & Penjelasan:* **B**. Pada SPSC, 'head' hanya diubah oleh produsen dan 'tail' hanya diubah oleh konsumen. Maka mutasi tunggal tidak membutuhkan CAS komparasi majemuk; semantik *acquire-release load/store* sudah memberikan jaminan sinkronisasi formal penuh.

8. **Masalah konkurensi apa yang dapat muncul jika kita menggunakan tagged pointer namun siklus counter 8-bit wrap-around terlalu cepat?**
   - A. Deadlock
   - B. Priority Inversion
   - C. Re-emergence ABA Problem
   - D. Livelock total pada kernel scheduler
   - *Jawaban & Penjelasan:* **C**. Jika tag/counter terlalu kecil (misal hanya 8-bit / 256 siklus), probabilitas sebuah pointer kembali ke nilai tag yang sama dalam beban kontensi masif sangat tinggi, memicu kembali bug ABA. Oleh sebab itu minimal tag adalah 32-bit atau 64-bit.

9. **Apa perbedaan mendasar antara jaminan Lock-Free dan Wait-Free?**
   - A. Lock-Free menggunakan semaphore, Wait-Free menggunakan spinlock.
   - B. Lock-Free menjamin kemajuan sistem secara global, sementara Wait-Free menjamin setiap thread individual menyelesaikan tugas dalam batas langkah terhingga.
   - C. Wait-Free hanya berlaku untuk single-core processor.
   - D. Tidak ada perbedaan, keduanya sinonim.
   - *Jawaban & Penjelasan:* **B**. Wait-free adalah superset dari lock-free yang memberikan jaminan determinisme paling ketat tanpa kemungkinan thread tertentu mengalami starvation.

10. **Apa fungsi utama dari tool analitik Linux `perf c2c`?**
    - A. Mengukur kecepatan koneksi antar server Cloud to Cloud.
    - B. Menganalisis utilisasi memori swap.
    - C. Mendeteksi fenomena Cache-to-Cache transfer dan mengidentifikasi metrik False Sharing (HITM) pada level instruksi kode sumber.
    - D. Menghitung jumlah thread yang dialokasikan oleh kernel.
    - *Jawaban & Penjelasan:* **C**. `perf c2c` (Cache-to-Cache) secara spesifik dirancang untuk melacak akses memori yang menyebabkan invalidasi cache line antar core CPU (HITM - Hit in Modified Cache).

### Bagian C: Skenario Kasus Produksi (3 Kasus)
11. **Skenario 1:** Sebuah tim merekayasa payment gateway berlatensi rendah. Mereka melaporkan bahwa implementasi lock-free queue mereka berjalan sempurna saat diuji pada laptop pengembang (Intel Core i9 x86-64), namun saat di-deploy ke server staging berbasis AWS Graviton (ARM64 Neoverse), antrean data mengalami korupsi data acak dan pembacaan nilai null.  
    **Pertanyaan:** Analisis penyebab arsitektural dari anomali ini dan berikan diagnosa perbaikannya.  
    *Jawaban & Analisis Rekayasa:* x86-64 menggunakan model memori **TSO (Total Store Order)** yang secara hardware mencegah reordering Store-Store dan Load-Load bahkan jika programmer teledor menggunakan `memory_order_relaxed`. Sebaliknya, prosesor ARM64 menggunakan model memori **Weakly Ordered** di mana hardware bebas mereorder pembacaan dan penulisan memori. Di x86, kelalaian ordering tertutupi oleh ketatnya hardware; di ARM, kelemahan ini langsung mengekspos race condition. Solusi: Ganti semua akses store relasional dengan `memory_order_release` dan load relasional dengan `memory_order_acquire`.

12. **Skenario 2:** Anda menjalankan profiler `perf c2c` pada matching engine internal dan menemukan metrik `HITM` sangat tinggi terpusat pada variabel penanda `sequence_number_` yang diakses oleh 16 thread worker concurrently. Setiap worker mengeksekusi fetch_add atomik pada variabel ini. Latensi transaksi memburuk seiring penambahan jumlah core thread.  
    **Pertanyaan:** Solusi arsitektur konkurensi apa yang tepat untuk menyelesaikan kontensi global ini?  
    *Jawaban & Analisis Rekayasa:* Fenomena ini adalah **True Sharing Contention** (*atomic variable cache line bouncing*). Karena 16 thread memperebutkan hak tulis (*Exclusive/Modified state*) pada satu cache line yang sama, inter-core interconnect bus tersaturasi penuh. Solusi: Ubah arsitektur dari *shared counter global* menjadi teknik terdistribusi, seperti **Striped Counters / LongAdder pattern** (setiap thread menulis ke counter independen beralas cache-line terpisah, dan agregasi hanya dilakukan saat pembacaan total), atau beralih ke pola arsitektur **Single Sequencer Dispatcher** berbasis ring-buffer (Disruptor pattern).

13. **Skenario 3:** Sebuah aplikasi perbankan menggunakan struktur data lock-free stack. Saat pengujian *stress test* jangka panjang, penggunaan memori (RSS) server terus meningkat hingga menyentuh batas OOM (Out Of Memory) killer, meskipun jumlah data aktif di stack konstan. Seluruh alokasi node dibuat via `new` dan dihapus via `delete` seketika di dalam loop `pop`.  
    **Pertanyaan:** Apa problem mendasar dari manajemen memori manual pada arsitektur lock-free tersebut dan pola arsitektur apa yang wajib diintegrasikan?  
    *Jawaban & Analisis Rekayasa:* Terjadi masalah **Unsafe Memory Reclamation (Concurrent Deletion)**. Pada sistem lock-free, sebuah node yang di-pop oleh Thread A tidak bisa langsung di-`delete` begitu saja, karena bisa jadi Thread B sedang memegang pointer ke node tersebut untuk persiapan validasi CAS. Jika Thread A menghancurkan node tersebut seketika, Thread B akan mengalami *Segmentation Fault / Use-After-Free*. Namun jika penghapusan ditunda tanpa sistem terstruktur, memori bocor. Solusi: Terapkan algoritma **Epoch-Based Reclamation (EBR)** atau **Hazard Pointers** yang menjamin node hanya dideallokasi secara fisik jika sudah dipastikan tidak ada satupun thread di seluruh sistem yang masih memegang referensi ke objek tersebut.

---

## 16. Summary
1. **Hardware-Conscious Paradigm:** Performa konkurensi puncak bukan sekadar masalah kompleksitas algoritma ($O(1)$ vs $O(N)$), melainkan kepatuhan terhadap hukum fisik hardware prosesor: *cache lines* (64B), *MESI coherency protocol*, dan pemisahan memori antar-core untuk mencegah *False Sharing*.
2. **Beyond Mutexes:** Mutex adalah abstraksi OS yang mahal karena membawa penalti context switching ke kernel space via `futex`. *Lock-free programming* menghindari interupsi OS dengan mengandalkan instruksi atomik CPU secara in-situ.
3. **Formal Memory Ordering:** Pahami konsekuensi arsitektural x86 (TSO) versus ARM (Weak Memory Model). Penggunaan C++ atomics dengan kombinasi presisi `memory_order_release` dan `memory_order_acquire` menjamin data konsisten tanpa overhead pengurasan Store Buffer yang diakibatkan oleh `memory_order_seq_cst`.
4. **Clean Engineering:** Struktur data lock-free produksi wajib didesain dengan pertimbangan eliminasi kontensi (*alignment padding*), mitigasi *ABA Problem* (via Hazard Pointers atau Tagged Pointers), dan arsitektur *Zero Dynamic Allocation* pada *hot-path*.