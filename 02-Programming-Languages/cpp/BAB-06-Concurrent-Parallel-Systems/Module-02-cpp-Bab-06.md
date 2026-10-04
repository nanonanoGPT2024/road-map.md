# BAB 06: Concurrent & Parallel Systems
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Memilih Model Memori C++ (*Memory Model*)**: Menentukan penggunaan `memory_order_relaxed`, `memory_order_acquire`/`release`, dan `memory_order_seq_cst` secara presisi guna meminimalkan penalti sinkronisasi pada arsitektur modern (x86-64 dan ARM64).
2. **Mengeliminasi Fenomena *Hardware Invalidation* & *False Sharing***: Menerapkan perataan *cache line* (*cache-line alignment*) menggunakan `std::hardware_destructive_interference_size` untuk menekan latensi akses memori multi-core.
3. **Mengonstruksi Struktur Data *Lock-Free* Produksi**: Merancang dan mengimplementasikan struktur data *Single-Producer Single-Consumer* (SPSC) dan *Multi-Producer Multi-Consumer* (MPMC) *Ring Buffer* bebas alokasi dinamis (*zero-allocation runtime*).
4. **Mengembangkan *Work-Stealing Thread Pool* Terdesentralisasi**: Membangun orkestrator beban komputasi berbasis *task-stealing deque* untuk meminimalkan *thread contention* dan *thread starvation*.
5. **Menerapkan *Hardware Thread Affinity* dan NUMA-Aware Scheduling**: Memetakan *worker thread* secara langsung ke inti CPU fisik guna mengoptimalkan *CPU cache locality* dan memangkas biaya *inter-socket interconnect traversal*.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib menguasai:
*   **Fondasi Concurrency C++**: `std::thread`, `std::jthread`, `std::mutex`, `std::unique_lock`, dan `std::condition_variable`.
*   **Arsitektur Komputer Lanjutan**: Hierarki *Cache* (L1i, L1d, L2, L3/LLC), protokol koherensi *cache* (MESI/MOESI), *Store Buffers*, serta *Memory Invalidation Queues*.
*   **Modern C++ Idioms**: C++20 Concepts, Templates, Rvalue References, Perfect Forwarding, serta RAII (*Resource Acquisition Is Initialization*).
*   **Tooling Diagnostik**: ThreadSanitizer (`-fsanitize=thread`), Valgrind/Helgrind, dan Linux Perf Profiler.

---

### 3. Concept & Internal Architecture

#### 3.1 C++ Memory Model & Hardware Memory Reordering
Kompilator modern dan CPU *out-of-order execution* (OoO) melakukan penataan ulang instruksi (*instruction reordering*) untuk memaksimalkan utilisasi *pipeline*. Dalam sistem multi-thread, penataan ulang ini dapat merusak konsistensi data jika tidak diatur secara eksplisit.

```
+-------------------------------------------------------------------------+
|                              CPU Pipeline                               |
|        [Program Order: Write A -> Write B]                              |
+------------------------------------+------------------------------------+
                                     |
                          Compiler Optimizations
                          (Dead Store Elimination,
                           Store Hoisting/Sinking)
                                     |
                                     v
+-------------------------------------------------------------------------+
|                         Out-of-Order Execution                          |
|    Instruction Scheduler membalik eksekusi jika tidak ada dependensi    |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                              Store Buffer                               |
|  Write B di-*flush* ke Cache L1 sebelum Write A selesai propagasi      |
+------------------------------------+------------------------------------+
                                     | (Store Buffer Drain)
                                     v
+-------------------------------------------------------------------------+
|                         L1/L2 Cache Coherency                           |
|       (Protokol MESI mendistribusikan invalidasi antar-inti)            |
+-------------------------------------------------------------------------+
```

1. **Sequentially Consistent (`std::memory_order_seq_cst`)**:
   *   Model default pada C++.
   *   Menjamin adanya total urutan (*globally consistent total order*) di seluruh thread.
   *   Mengharuskan penempatan instruksi *memory barrier* penuh (contoh: `MFENCE` pada x86, `DMB ISH` pada ARM), yang menghentikan eksekusi *pipeline* CPU hingga *store buffer* benar-benar kosong.
2. **Acquire-Release (`memory_order_acquire`, `memory_order_release`, `memory_order_acq_rel`)**:
   *   Menghilangkan kebutuhan total urutan global; sinkronisasi hanya ditegakkan antara thread yang melakukan *release* dan thread yang melakukan *acquire* pada variabel atomik yang sama.
   *   **Store-Release**: Mencegah operasi *load* atau *store* sebelumnya dipindahkan ke setelah operasi *store* ini.
   *   **Load-Acquire**: Mencegah operasi *load* atau *store* setelahnya dipindahkan ke sebelum operasi *load* ini.
   *   Pada arsitektur x86-64 (TSO - *Total Store Order*), operasi *store* normal sudah memiliki semantik *release*, dan operasi *load* normal sudah memiliki semantik *acquire*. Penggunaan *Acquire-Release* di x86 bersifat *zero-cost* pada tingkat instruksi mesin, namun mencegah optimasi instruksi kompilator yang tidak diinginkan. Pada arsitektur ARM64/POWER, instruksi satu arah (`LDAR`/`STLR`) dipancarkan secara spesifik.
3. **Relaxed (`std::memory_order_relaxed`)**:
   *   Hanya menjamin integritas atomisitas akses memori (bebas dari fenomena *torn reads/writes*).
   *   Tidak menyediakan relasi *synchronizes-with* atau batasan *happens-before*.
   *   Operasi di sekitar memori atomik bebas ditata ulang oleh CPU maupun kompilator. Cocok untuk operasi seperti penambahan metrik (*counter aggregation*).

#### 3.2 Cache Line Invalidation & False Sharing
Arsitektur prosesor mengelola memori dalam satuan blok berukuran diskrit yang disebut *cache line* (umumnya bernilai 64 byte pada x86-64 dan ARM64).

*   **Cache Line Bouncing**: Ketika dua atau lebih inti CPU menulis ke *cache line* yang sama, protokol koherensi (seperti MESI) harus menandai salinan *cache line* pada inti lain sebagai *Invalid* (I). Inti lain tersebut kemudian terpaksa memuat ulang seluruh baris 64 byte dari L3 atau memori utama (RAM).
*   **False Sharing**: Terjadi ketika dua thread pada inti yang berbeda memodifikasi variabel independen yang secara fisik berada dalam satu *cache line* 64-byte yang sama. Hal ini memicu serialisasi tersembunyi pada bus memori antar-inti CPU, menurunkan skala throughput secara eksponensial.
*   **Mitigasi**: Menyelaraskan struktur data ke batas *cache line* menggunakan atribut `alignas(std::hardware_destructive_interference_size)`.

#### 3.3 Anatomi ABA Problem & Hazard Pointers
Pada manipulasi struktur data dinamis *lock-free* (seperti *Treiber Stack* atau antrean berbasis pointer), modifikasi konkuren rentan terhadap *ABA Problem*:
1. Thread T1 membaca pointer `A` dari *head*.
2. T1 diputus (*preempted*) oleh penjadwal OS sebelum menjalankan `compare_exchange_weak`.
3. Thread T2 menghapus `A`, mengalokasikan node baru `B`, menghapus node lain, lalu mengalokasikan kembali memori pada alamat yang kebetulan identik dengan `A`, lalu memasukkannya ke *head*.
4. T1 kembali aktif, mengevaluasi bahwa pointer *head* saat ini bernilai sama dengan `A`. Instruksi *Compare-And-Swap* (CAS) berhasil, namun rantai pointer di balik node `A` telah rusak (*dangling pointer/memory corruption*).

**Penyelesaian Produksi**:
*   *Tagging / Tagged Pointers* (Pointer 64-bit yang digabungkan dengan counter versi 16/32-bit melalui manipulasi bit atau instruksi `CMPXCHG16B` pada x86-64).
*   *Hazard Pointers*: Thread mendaftarkan pointer yang sedang dibaca ke array global hazard pointers. Thread penghapus tidak boleh membebaskan memori selama pointer masih terdaftar.
*   *Epoch-Based Reclamation (EBR)*: Mengelompokkan siklus hidup memori ke dalam fase epoch; memori baru dideallocasi jika seluruh thread telah melewati batas epoch terkait.

---

### 4. Why & What

| Pendekatan | Mekanisme Sinkronisasi | Latensi Kasus Terburuk | Karakteristik Throughput | Biaya Resource |
| :--- | :--- | :--- | :--- | :--- |
| **Mutex Tradisional (`std::mutex`)** | *Kernel-level blocking*, *futex*, *context-switch* | Tinggi (> 1.5 - 5 $\mu s$) saat terjadi kontensi | Runtuh secara drastis saat thread bertambah | Overhead OS scheduler, saturasi register CPU |
| **Spinlock Naif** | Polling sibuk (*busy-wait loop*) pada flag atomik | Sangat Buruk (jika pemegang kunci di-*preempt*) | Membakar siklus CPU 100%, menghancurkan efisiensi daya | Latensi ekstrem akibat *priority inversion* |
| **Lock-Free (Acquire-Release)** | Hardware CAS loop (`atomic_compare_exchange`) | Menengah ke Rendah (< 100 $ns$) | Tetap stabil di bawah beban tinggi | Kompleksitas logika, rentan terhadap starvation |
| **Wait-Free Ring Buffer (SPSC)** | Pemisahan indeks baca/tulis atomik terisolasi | Deterministik (< 15 $ns$) | Memaksimalkan saturasi kapasitas pipa memori | Memori tetap dialokasikan di awal (*pre-allocated*) |

**Mengapa Beralih ke Lock-Free & Concurrency Lanjutan?**
Aplikasi berskala enterprise (seperti *financial order execution engines*, *telemetry ingestion gateways*, atau *game servers*) tidak dapat mentoleransi *tail latency* (p99.99) yang disebabkan oleh *thread preemption* dan pemanggilan sistem operasi (*syscall*). Penggunaan pendekatan *lock-free* yang presisi memangkas *context switch*, mencegah *deadlock*, dan menjamin aliran data deterministik pada sistem multi-inti.

---

### 5. How (Workflow Detail)

Alur kerja perancangan sistem konkurensi performa tinggi:
1. **Penetapan Topologi Sistem & Domain NUMA**:
   Identifikasi jumlah *socket*, *core*, dan tata letak *cache hierarchy* host produksi via `lstopo` atau `hwloc`.
2. **Pemberian Afinitas Thread (*Thread Pinning*)**:
   Ikat setiap alur kerja spesifik ke inti komputasi tunggal menggunakan `pthread_setaffinity_np` untuk memastikan data tetap berada di cache L1/L2 lokal thread tersebut.
3. **Pengalokasian Buffer Sirkular Bounded (*Zero-Allocation*)**:
   Inisialisasi buffer melingkar berkapasitas pangkat dua ($2^n$) di awal siklus hidup program. Hindari eksekusi `malloc`/`free` atau pemanggilan heap C++ di dalam *hot execution path*.
4. **Isolasi Indeks Penulisan & Pembacaan**:
   Tempatkan pointer baca (*head*) dan pointer tulis (*tail*) pada *cache line* terpisah dengan memberikan *padding* struktural.
5. **Eksekusi Komunikasi Memori Melalui *Memory Barriers***:
   *   Penulis memperbarui payload, lalu mempublikasikan indeks tulis dengan `memory_order_release`.
   *   Pembaca membaca indeks tulis dengan `memory_order_acquire`. Data payload dijamin terlihat dan valid tanpa memerlukan *lock* sistem operasi.

---

### 6. Analogy & Diagram ASCII

#### 6.1 Protokol Acquire-Release sebagai Jabat Tangan Kontrak Tertulis
Bayangkan Producer menyusun laporan rahasia (Data Payload) di atas meja. Setelah dokumen selesai disusun, Producer menandatangani buku ekspedisi (Operasi *Store-Release* pada Indeks). Consumer terus memantau buku ekspedisi. Ketika tanda tangan Producer muncul, Consumer menandatangani validasi penerimaan (Operasi *Load-Acquire* pada Indeks). Protokol ini menjamin bahwa seluruh isi dokumen di atas meja telah lengkap dan valid saat Consumer mulai membacanya.

```
THREAD 1 (Producer)                      THREAD 2 (Consumer)
====================                      ====================
[Tulis data: Buffer[idx] = Payload]
           |
     (Store-Release)
           |
[Atomic Write: Head.store(idx, release)] 
           |                                       |
           +======= (Synchronizes-With) ===========> (Load-Acquire)
                                                   |
                                 [Atomic Read: Head.load(acquire)]
                                                   |
                                 [Baca data: Payload = Buffer[idx]]
```

#### 6.2 Topologi Cache Line & False Sharing
```
                          64-BYTE CACHE LINE
+------------------------------------+------------------------------------+
|         Variable A (8 Byte)        |        Variable B (8 Byte)         |
|        Diakses oleh Core 1         |        Diakses oleh Core 2         |
+------------------------------------+------------------------------------+
                   |                                    |
                   v                                    v
            +--------------+                     +--------------+
            |  CPU CORE 1  |                     |  CPU CORE 2  |
            +--------------+                     +--------------+
                   ^                                    ^
                   |                                    |
     [Core 1 Menulis Variable A]         [Core 2 Menulis Variable B]
     [Mengirim Sinyal Invalidasi] =====> [L1 Cache Core 2 Terpaksa Flush]
     
     HASIL: Penurunan throughput akibat Cache Line Bouncing berkepanjangan!
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Spinlock Berbasis *Exponential Backoff* & Acquire-Release
Contoh ini mendemonstrasikan implementasi *mutual exclusion* primitif berperforma tinggi untuk seksi kritis mikro (< 50 nanodetik).

```cpp
#include <atomic>
#include <thread>
#include <chrono>

#if defined(_M_X64) || defined(__x86_64__)
#include <immintrin.h> // _mm_pause
#define CPU_PAUSE() _mm_pause()
#elif defined(__aarch64__)
#define CPU_PAUSE() asm volatile("yield" ::: "memory")
#else
#define CPU_PAUSE() std::this_thread::yield()
#endif

class BackoffSpinlock {
public:
    void lock() noexcept {
        int backoff_iterations = 1;
        while (true) {
            // Optimistic read: Hindari memodifikasi cache line jika kunci sedang dipegang
            if (!lock_state_.load(std::memory_order_relaxed)) {
                // Mencoba mengambil hak akses eksklusif
                if (!lock_state_.exchange(true, std::memory_order_acquire)) {
                    return;
                }
            }

            // Exponential backoff untuk mereduksi beban inter-core bus
            for (int i = 0; i < backoff_iterations; ++i) {
                CPU_PAUSE();
            }

            if (backoff_iterations < MAX_BACKOFF) {
                backoff_iterations <<= 1; // Lipat gandakan waktu tunggu
            } else {
                std::this_thread::yield(); // Relinquish quantum ke OS scheduler
            }
        }
    }

    void unlock() noexcept {
        lock_state_.store(false, std::memory_order_release);
    }

private:
    static constexpr int MAX_BACKOFF = 64;
    std::atomic<bool> lock_state_{false};
};
```

#### 7.2 Practical Example: Enterprise Lock-Free Bounded SPSC Queue
Implementasi antrean circular ring-buffer deterministik C++20 tanpa alokasi memori dinamis runtime, bebas *false sharing*, dan memanfaatkan pembatas modulo berbasis bitwise (*power-of-two size*).

```cpp
#include <cstddef>
#include <new>
#include <atomic>
#include <optional>
#include <span>
#include <vector>
#include <concepts>
#include <utility>
#include <stdexcept>

// Gunakan konstanta platform atau fallback standar jika destructive interference size tidak didefinisikan
#ifdef __cpp_lib_hardware_interference_size
    using std::hardware_destructive_interference_size;
#else
    constexpr size_t hardware_destructive_interference_size = 64;
#endif

template <typename T, size_t Capacity>
requires (Capacity >= 2) && ((Capacity & (Capacity - 1)) == 0) // Kapasitas wajib Power of Two
class LockFreeSPSCQueue {
public:
    LockFreeSPSCQueue() : read_idx_cached_(0), write_idx_cached_(0) {
        static_assert(alignof(LockFreeSPSCQueue<T, Capacity>) >= hardware_destructive_interference_size,
                      "Struktur data wajib terisolasi dalam batas cache line.");
    }

    ~LockFreeSPSCQueue() {
        T discarded;
        while (pop(discarded)) {}
    }

    LockFreeSPSCQueue(const LockFreeSPSCQueue&) = delete;
    LockFreeSPSCQueue& operator=(const LockFreeSPSCQueue&) = delete;
    LockFreeSPSCQueue(LockFreeSPSCQueue&&) = delete;
    LockFreeSPSCQueue& operator=(LockFreeSPSCQueue&&) = delete;

    template <typename... Args>
    bool emplace(Args&&... args) {
        const size_t current_tail = write_idx_.load(std::memory_order_relaxed);
        
        // Cek kapasitas menggunakan salinan lokal (cached) indeks read untuk menghindari invalidasi L1
        if ((current_tail - read_idx_cached_) >= Capacity) {
            read_idx_cached_ = read_idx_.load(std::memory_order_acquire);
            if ((current_tail - read_idx_cached_) >= Capacity) {
                return false; // Queue Penuh
            }
        }

        // Konstruksi objek secara in-place via placement new
        new (get_slot_address(current_tail)) T(std::forward<Args>(args)...);

        // Publikasikan item baru kepada Consumer menggunakan semantik Release
        write_idx_.store(current_tail + 1, std::memory_order_release);
        return true;
    }

    bool push(const T& item) {
        return emplace(item);
    }

    bool push(T&& item) {
        return emplace(std::move(item));
    }

    bool pop(T& value) {
        const size_t current_head = read_idx_.load(std::memory_order_relaxed);

        // Cek ketersediaan elemen menggunakan salinan lokal (cached) indeks write
        if (current_head == write_idx_cached_) {
            write_idx_cached_ = write_idx_.load(std::memory_order_acquire);
            if (current_head == write_idx_cached_) {
                return false; // Queue Kosong
            }
        }

        // Ambil elemen dari storage dan hancurkan objek aslinya
        T* element_ptr = reinterpret_cast<T*>(get_slot_address(current_head));
        value = std::move(*element_ptr);
        element_ptr->~T();

        // Publikasikan konsumsi slot kepada Producer menggunakan semantik Release
        read_idx_.store(current_head + 1, std::memory_order_release);
        return true;
    }

    [[nodiscard]] size_t size() const noexcept {
        const size_t current_tail = write_idx_.load(std::memory_order_relaxed);
        const size_t current_head = read_idx_.load(std::memory_order_relaxed);
        return (current_tail >= current_head) ? (current_tail - current_head) : 0;
    }

    [[nodiscard]] bool empty() const noexcept {
        return size() == 0;
    }

private:
    static constexpr size_t INDEX_MASK = Capacity - 1;

    void* get_slot_address(size_t index) noexcept {
        return static_cast<void*>(&storage_[(index & INDEX_MASK) * sizeof(StorageSlot)]);
    }

    // Alokasi memori uninitialized dengan perataan struktur internal
    struct alignas(alignof(T)) StorageSlot {
        std::byte data[sizeof(T)];
    };

    // Alokasi memori internal statis
    alignas(hardware_destructive_interference_size) StorageSlot storage_[Capacity];

    // Isolasi penuh State Producer pada baris Cache tersendiri
    alignas(hardware_destructive_interference_size) std::atomic<size_t> write_idx_{0};
    size_t read_idx_cached_{0};

    // Isolasi penuh State Consumer pada baris Cache tersendiri
    alignas(hardware_destructive_interference_size) std::atomic<size_t> read_idx_{0};
    size_t write_idx_cached_{0};
};
```

---

### 8. Real World Case Study: Ultra-Low Latency Market Ingestion Pipeline

#### Skenario Kasus Produksi
Platform perdagangan frekuensi tinggi (*High-Frequency Trading* / HFT) menerima pembaruan feed pasar finansial NASDAQ ITCH melalui interkoneksi jaringan serat optik Kernel-Bypass (Solarflare Onload). Sistem dituntut memproses $10.000.000$ pesan per detik dengan latensi *p99.9* di bawah $800$ nanodetik. Jika antrean menggunakan mutex tradisional, *context-switching* kernel memicu *jitter* latensi hingga $25$ mikrodetik, menyebabkan keterlambatan kalkulasi harga eksekusi (*slippage*).

#### Solusi Arsitektur
1. **Network Ingress Core (Core 2)**: Menggunakan alur kerja *polling* terus menerus (*busy-polling*) dari socket UDP langsung ke ring buffer tanpa *system call*.
2. **Ring Buffer Komunikasi Inter-Thread**: Menghubungkan Network Core dengan Order Book Matching Core via SPSC Queue tanpa *lock*, menggunakan memory ordering *Acquire-Release*.
3. **Execution Core (Core 4)**: Mengonsumsi data order, memperbarui L3 Local Order Book, dan mengeksekusi strategi tanpa interupsi OS (`isolcpus=2,4` pada konfigurasi kernel Linux).

```cpp
#include <iostream>
#include <thread>
#include <chrono>
#include <atomic>
#include <cstring>
#include <pthread.h>

struct MarketUpdateMessage {
    uint64_t timestamp_nanos;
    uint32_t symbol_id;
    uint32_t volume;
    double price;
    char side; // 'B' = Buy, 'S' = Sell
};

// Fungsi utility untuk memetakan afinitas core pada Linux
void pin_thread_to_core(pthread_t thread, int core_id) {
    cpu_set_t cpuset;
    CPU_ZERO(&cpuset);
    CPU_SET(core_id, &cpuset);
    int rc = pthread_setaffinity_np(thread, sizeof(cpu_set_t), &cpuset);
    if (rc != 0) {
        throw std::runtime_error("Gagal melakukan thread pinning ke core!");
    }
}

void run_hft_pipeline() {
    constexpr size_t RING_BUFFER_CAPACITY = 1048576; // 2^20
    static LockFreeSPSCQueue<MarketUpdateMessage, RING_BUFFER_CAPACITY> market_data_bus;
    std::atomic<bool> pipeline_running{true};

    // Thread 1: Network Ingress Engine (Produsen Data Pasar)
    std::jthread ingress_worker([&](std::stop_token stoken) {
        pin_thread_to_core(pthread_self(), 2);

        uint64_t sequence_id = 0;
        MarketUpdateMessage msg;
        msg.symbol_id = 42; // e.g. NVDA
        msg.price = 125.50;
        msg.volume = 100;
        msg.side = 'B';

        while (!stoken.stop_requested()) {
            msg.timestamp_nanos = std::chrono::duration_cast<std::chrono::nanoseconds>(
                std::chrono::high_resolution_clock::now().time_since_epoch()
            ).count();

            // Push tanpa henti (spin-retry jika buffer penuh)
            while (!market_data_bus.push(msg)) {
                CPU_PAUSE();
            }
            ++sequence_id;
        }
    });

    // Thread 2: Execution Matching Engine (Konsumen Analitik Buku Order)
    std::jthread matching_worker([&](std::stop_token stoken) {
        pin_thread_to_core(pthread_self(), 4);

        MarketUpdateMessage received_msg;
        uint64_t processed_count = 0;

        while (!stoken.stop_requested()) {
            if (market_data_bus.pop(received_msg)) {
                // Pemrosesan Order Book deterministik
                processed_count++;
            } else {
                CPU_PAUSE(); // Jangan sleep; pertahankan warm cache pada CPU core
            }
        }
        std::cout << "Matching Engine Berhasil Memproses: " << processed_count << " pesan.\n";
    });

    // Jalankan pipeline selama 500 milidetik untuk evaluasi profil performa
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    ingress_worker.request_stop();
    matching_worker.request_stop();
}
```

---

### 9. Trade-offs

```
                  +-----------------------------------+
                  |   Kompleksitas & Portabilitas     |
                  |     (Debugging, Sanitasi)         |
                  +-----------------+-----------------+
                                    |
                                    |
      Tinggi (Lock-Free)           / \            Rendah (Mutex-Based)
                                  /   \
                                 /     \
                                /       \
+------------------------------+         +-------------------------------+
|     Throughput Maksimum      |---------|   Deterministik Latensi Rendah|
|     (MPMC / Work-Stealing)   |         |      (SPSC Pinned Affinity)   |
+------------------------------+         +-------------------------------+
```

| Desain Pilihan | Metrik Positif | Konsekuensi Negatif | Skenario Ideal |
| :--- | :--- | :--- | :--- |
| **`memory_order_seq_cst`** | Mudah dipahami, bebas bug reordering kompilator | *Pipeline stall* di x86/ARM, latensi transaksi memori tinggi | Flag inisialisasi state konfigurasi global |
| **`memory_order_acq_rel`** | Mengeliminasi instruksi pembatas memori penuh | Membutuhkan audit manual ketergantungan relasi variabel | Antrean transfer pesan, transfer token kepemilikan data |
| **Lock-Free Bounded Ring Buffer** | Nol alokasi, latensi konstan, throughput tinggi | Kapasitas buffer kaku, memori dialokasikan penuh di awal | Ingest feed data real-time, audio DSP, low-latency trading |
| **Dynamic Work-Stealing Deque** | Seimbang (*load-balancing*) otomatis antar-inti CPU | Risiko kontensi pada operasi pencurian (*steal*), alokasi dinamis | Pemrosesan tugas graf, rendering engine fisik paralel |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Spurious CAS Failure
**Kesalahan Fatal**: Menggunakan `compare_exchange_strong` di dalam perulangan *spin-wait* pada arsitektur RISC/ARM, yang memicu pemborosan siklus CPU secara masif saat terjadi *spurious failure*.
```cpp
// SALAH: Penggunaan strong CAS di dalam loop pada sistem load-linked/store-conditional
while (!atomic_head.compare_exchange_strong(expected, desired, std::memory_order_acq_rel)) {
    // Loop berputar lebih lama dari yang dibutuhkan karena overhead komparasi ganda internal
}

// BENAR: Gunakan weak CAS dalam loop
while (!atomic_head.compare_exchange_weak(expected, desired,
                                         std::memory_order_release,
                                         std::memory_order_relaxed)) {
    // Loop mentoleransi kegagalan spurious akibat interupsi hardware
}
```

#### 10.2 Relaxed Atomic yang Melindungi State Non-Atomik
**Kesalahan Fatal**: Menganggap pengubahan flag berbasis `memory_order_relaxed` sudah cukup untuk memvalidasi ketersediaan data payload biasa.
```cpp
// Skenario Error
int payload_data = 0;
std::atomic<bool> is_ready{false};

// Producer Thread:
payload_data = 42;
is_ready.store(true, std::memory_order_relaxed); // SALAH! payload_data bisa ditata ulang melewati titik ini

// Consumer Thread:
while (!is_ready.load(std::memory_order_relaxed)) {}
assert(payload_data == 42); // ERROR: Nilai bisa terbaca 0 karena CPU me-reorder pembacaan payload!
```
**Solusi Troubleshooting**: Pasangkan `store(true, std::memory_order_release)` dengan `load(std::memory_order_acquire)`.

#### 10.3 Sanitasi Concurrency Melalui TSAN
Gunakan Clang atau GCC dengan instruksi kompilasi berikut untuk mendeteksi *data race* tersembunyi:
```bash
g++ -std=c++20 -fsanitize=thread -O2 -g main.cpp -lpthread -o hft_app_profiled
```
Jika terdeteksi `WARNING: ThreadSanitizer: data race`, analisis *call stack trace* untuk memverifikasi apakah terjadi *read/write* tanpa relasi sinkronisasi yang valid.

---

### 11. Best Practices (Production Checklist)

- [ ] **Alignment Hardware-Interference**: Seluruh variabel atomic indeks produsen dan konsumen harus memiliki pemisah minimum `hardware_destructive_interference_size` byte.
- [ ] **Kapasitas Buffer Berbasis Pangkat Dua (*Power of Two*)**: Gunakan operator `index & (Capacity - 1)` sebagai pengganti operator modulo (`%`) yang membutuhkan komputasi divisi hardware puluhan siklus CPU.
- [ ] **Pre-allocation & Zero-Heap**: Tidak ada pemanggilan operator `new`, `malloc`, atau instansiasi pointer dinamis di dalam *hot path* pemrosesan pesan transaksi.
- [ ] **CPU Core Affinity Strategy**: Pisahkan thread I/O kernel, thread kalkulasi analitik, dan OS background workers ke ID CPU yang berbeda menggunakan *mask affinity*.
- [ ] **No Raw Spin-Wait**: Selalu sisipkan instruksi pereda tekanan pipeline CPU (`_mm_pause()` pada x86 atau `yield` pada ARM) di dalam perulangan *spin*.
- [ ] **Gunakan `std::jthread`**: Manfaatkan `std::jthread` untuk manajemen thread RAII dan terminasi kooperatif melalui `std::stop_token` guna mencegah pemanggilan `std::terminate()` saat *stack unwinding*.

---

### 12. Hands-on Practice

Buat dan simpan praktikum ini di direktori: `hands-on/m02/`

#### Langkah 1: Persiapan Struktur Proyek
```bash
mkdir -p hands-on/m02/{src,include,bench}
cd hands-on/m02
```

#### Langkah 2: Buat File `CMakeLists.txt`
```cmake
cmake_minimum_required(VERSION 3.20)
project(CppAdvancedConcurrency LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Opsi tuning performa tinggi
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -Wall -Wextra -Wpedantic -march=native -pthread")

include_directories(include)

add_executable(spsc_benchmark bench/main_bench.cpp)
target_link_libraries(spsc_benchmark PRIVATE pthread)
```

#### Langkah 3: Implementasi File Header `include/LockFreeSPSC.hpp`
Salin kode dari **Seksi 7.2 (LockFreeSPSCQueue)** ke dalam berkas `include/LockFreeSPSC.hpp`.

#### Langkah 4: Implementasi Program Benchmark `bench/main_bench.cpp`
```cpp
#include "LockFreeSPSC.hpp"
#include <iostream>
#include <thread>
#include <chrono>
#include <vector>
#include <numeric>

constexpr size_t TEST_OPERATIONS = 10'000'000;
constexpr size_t QUEUE_SIZE = 65536; // 2^16

int main() {
    std::cout << "Menginisialisasi Benchmark SPSC Lock-Free (" << TEST_OPERATIONS << " operasi)...\n";
    
    LockFreeSPSCQueue<uint64_t, QUEUE_SIZE> queue;

    auto start_time = std::chrono::high_resolution_clock::now();

    std::jthread producer([&]() {
        for (uint64_t i = 1; i <= TEST_OPERATIONS; ++i) {
            while (!queue.push(i)) {
                CPU_PAUSE();
            }
        }
    });

    std::jthread consumer([&]() {
        uint64_t received_val = 0;
        uint64_t checksum = 0;
        for (uint64_t i = 1; i <= TEST_OPERATIONS; ++i) {
            while (!queue.pop(received_val)) {
                CPU_PAUSE();
            }
            checksum += received_val;
        }
        std::cout << "Validasi Selesai. Checksum Terkumpul: " << checksum << "\n";
    });

    producer.join();
    consumer.join();

    auto end_time = std::chrono::high_resolution_clock::now();
    auto elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time).count();
    double operations_per_sec = (static_cast<double>(TEST_OPERATIONS) / elapsed_ms) * 1000.0;

    std::cout << "Durasi Eksekusi: " << elapsed_ms << " ms\n";
    std::cout << "Throughput Rata-Rata: " << static_cast<uint64_t>(operations_per_sec) << " ops/sec\n";

    return 0;
}
```

#### Langkah 5: Kompilasi dan Eksekusi
```bash
mkdir build && cd build
cmake ..
make -j$(nproc)
./spsc_benchmark
```

---

### 13. Exercise

#### 13.1 Level Easy: Implementasi Flag Pembatas Sinkronisasi Sederhana
*   **Instruksi**: Tulis kelas sinkronisasi satu kali tembak (*one-shot event latch*) `OneShotLatch` menggunakan satu variabel `std::atomic<bool>`. Sediakan method `wait()` dan `set()`. Pastikan thread pemanggil `wait()` terblokir secara efisien menggunakan `std::atomic::wait` dan `std::atomic::notify_all` (fitur C++20).
*   **Batas Kebutuhan**: Larang penggunaan `std::mutex` dan `std::condition_variable`.

#### 13.2 Level Medium: Multiple-Producer Single-Consumer (MPSC) Turnstile
*   **Instruksi**: Kembangkan queue berbasis ring buffer terikat (*bounded ring-buffer*) di mana banyak thread producer dapat memasukkan data secara bersamaan (*multi-producer*), namun hanya ada satu consumer yang mengambil data (*single-consumer*).
*   **Batas Kebutuhan**:
    *   Producer mengamankan slot tulis menggunakan `fetch_add` atomik pada variabel `write_idx_`.
    *   Tiap slot harus dilengkapi state flag atomik (`EMPTY`, `WRITING`, `READY`) untuk mencegah Consumer membaca payload sebelum Producer selesai menulis data.

#### 13.3 Level Hard: NUMA-Aware Work-Stealing Task Scheduler
*   **Instruksi**: Bangun *Work-Stealing Task Scheduler* multi-worker mini.
    *   Setiap inti CPU memiliki *Lock-Free Double-Ended Queue* (Deque) lokal tersendiri.
    *   Worker memproses tugas (*tasks*) dari ujung bawah (*tail*) Deque miliknya secara eksklusif menggunakan operasi cepat tanpa lock.
    *   Jika worker kehabisan tugas, worker tersebut mencoba mencuri (*steal*) tugas dari ujung atas (*head*) Deque milik worker lain secara atomic via CAS.

---

### 14. Challenge: Fault-Tolerant Shared Memory Ring Buffer Bus (Zero-Copy IPC)
Rancang arsitektur komunikasi *Inter-Process Communication* (IPC) berperforma tinggi untuk sistem perdagangan derivatif keuangan dengan kriteria ketat berikut:
1. **Media Memori Terbagi (*POSIX Shared Memory*)**: Komunikasi antar dua proses independen berjalan di atas *memory-mapped file* (`shm_open`, `mmap`) tanpa melalui lapisan socket kernel.
2. **Crash Resilience & Deadlock Free**: Jika proses Producer tiba-tiba mati (*crash / SIGSEGV*) di tengah penulisan transaksi, proses Consumer tidak boleh mengalami *hang*, *infinite spin*, atau *undefined memory state*.
3. **Epoch Reclamation Guard**: Buat mekanisme validasi *in-line heartbeat* dan penandaan versi buffer (*generational ticket counter*) untuk mendeteksi pesan yang tertinggal atau korup tanpa menggunakan lock kernel sistem operasi.
4. **Target Throughput**: Wajib melampaui $15.000.000$ transaksi 64-byte per detik dengan *jitter p99.99* di bawah $2$ mikrodetik.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. Apa perbedaan mendasar antara `std::memory_order_relaxed` dan `std::memory_order_seq_cst`?
2. Mengapa struktur `alignas(64)` lazim digunakan pada implementasi atomik multi-threaded?
3. Apa perbedaan fungsional antara `compare_exchange_weak` dan `compare_exchange_strong`? Kapan kita wajib memilih versi *weak*?
4. Apa yang menyebabkan fenomena *False Sharing*, dan pada lapisan subsistem komputer mana permasalahan ini terjadi?
5. Mengapa pemanggilan `std::this_thread::yield()` lebih disarankan daripada perulangan kosong (*empty while loop*) saat melakukan *busy-waiting* jangka panjang?

#### Bagian 2: Intermediate (5 Pertanyaan)
1. Tinjau potongan kode berikut:
   ```cpp
   // Thread 1
   val = 100;
   flag.store(true, std::memory_order_release);
   // Thread 2
   while (!flag.load(std::memory_order_relaxed)) {}
   print(val);
   ```
   Apakah pemanggilan `print(val)` dijamin selalu mencetak angka `100` di semua arsitektur prosesor? Jelaskan mekanismenya secara teknis!
2. Mengapa arsitektur prosesor x86-64 secara hardware tidak membedakan instruksi mesin antara operasi `load(acquire)` dengan pembacaan memori biasa?
3. Apa peran instruksi intrinsik CPU `_mm_pause()` dalam perulangan spinlock atomik?
4. Bagaimana algoritma *modulo bitwise* (`index & (Capacity - 1)`) bekerja menggantikan operasi pembagian aritmatika, dan apa syarat mutlak kapasitas buffer yang harus dipenuhi?
5. Mengapa teknik alokasi memori dinamis (`malloc` atau `new`) dihindari pada sistem komputasi *hard real-time* dan *low latency*?

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan Kasus)
1. **Skenario Kasus Jitter Latensi HFT**:
   Sebuah aplikasi *crypto-trading* mengalami lonjakan latensi ekstrim (hingga $50$ mikrodetik) setiap kali volume transaksi pasar melonjak tajam, meskipun kode sudah menggunakan *atomic spinlock*. Tim infrastruktur mendeteksi beban CPU pada semua inti mencapai 100%. Jelaskan akar masalahnya dan bagaimana arsitektur antrean harus dirombak untuk mengatasinya!
2. **Skenario Kasus Memory Leak pada Treiber Stack**:
   Sebuah implementasi antrean berbasis *linked-list lock-free* mengalami penambahan konsumsi memori (*memory bloat*) secara konstan hingga kehabisan memori (*OOM Crash*). Developer tidak berani memanggil instruksi `delete node` langsung di dalam fungsi `pop()` karena takut memicu *Segmentation Fault* pada thread pembaca lain. Solusi teknis apa yang harus diintegrasikan untuk menangani pembersihan memori node secara aman tanpa memblokir thread?
3. **Skenario Bug Migrasi Arsitektur (x86 ke ARM64)**:
   Aplikasi backend trading Anda berjalan stabil dan bebas masalah selama 3 tahun di server Intel Xeon (x86-64). Namun, ketika dikompilasi dan dijalankan pada server AWS Graviton (ARM64), sistem mengalami insiden korupsi data (*data corruption*) secara sporadis, meskipun kode C++ yang digunakan identik dan menggunakan `memory_order_relaxed` pada sejumlah checkpoint. Analisis penyebab ilmiah dari kegagalan ini!

---

### Kunci Jawaban & Solusi Quiz

#### Jawaban Bagian 1: Basic
1. `memory_order_relaxed` hanya menjamin integritas atomisitas variabel itu sendiri tanpa sinkronisasi instruksi di sekitarnya. Sebaliknya, `memory_order_seq_cst` menegakkan total urutan instruksi memori secara global di seluruh CPU dengan menyisipkan pembatas memori penuh (*full hardware memory barrier*).
2. Untuk memastikan variabel berada pada baris cache (*cache line*) 64-byte yang terisolasi secara mandiri, sehingga memodifikasi nilai variabel tersebut tidak memicu invalidasi cache line data lain yang berada di sekitarnya (*false sharing*).
3. `compare_exchange_weak` dapat menghasilkan kegagalan semu (*spurious failure*) akibat interupsi hardware atau *context switch* meskipun nilainya cocok. Versi *weak* wajib digunakan di dalam perulangan (`while loop`) karena menghasilkan instruksi yang lebih ringkas dan optimal pada arsitektur ARM/LL-SC. Versi *strong* digunakan jika kita hanya perlu melakukan percobaan CAS tepat satu kali tanpa perulangan.
4. Terjadi ketika dua thread pada CPU core yang berbeda memodifikasi variabel berbeda yang kebetulan berbagi baris memori *cache line* 64-byte yang sama. Fenomena ini terjadi pada subsistem Cache L1/L2 dan interkoneksi koherensi prosesor (*cache coherency bus*).
5. Karena perulangan kosong (*tight infinite loop*) memonopoli pipeline CPU 100%, memanaskan silikon core prosesor, membuang energi, dan menghambat OS dalam mengeksekusi thread prioritas lain. `yield()` mengembalikan jatah quantum eksekusi kembali ke OS scheduler.

#### Jawaban Bagian 2: Intermediate
1. **Tidak dijamin**. Penggunaan `memory_order_relaxed` pada Thread 2 tidak membangun relasi sinkronisasi formal (*synchronizes-with*) dengan Thread 1. Akibatnya, kompilator atau prosesor OoO diizinkan membaca `val` dari cache atau register lokal sebelum evaluasi `flag` selesai dilakukan, yang berpotensi menghasilkan pembacaan memori sampah (*uninitialized/stale data*).
2. Arsitektur x86-64 mengadopsi model *Total Store Order* (TSO) secara hardware. Pada TSO, instruksi pembacaan (*reads*) tidak akan ditata ulang melewati pembacaan lain maupun penulisan sebelumnya. Karakteristik alami hardware ini secara otomatis memenuhi kontrak semantik dari operasi *Acquire* tanpa membutuhkan instruksi assembly *fence* tambahan.
3. Menginstruksikan CPU untuk menunda alur eksekusi sementara (*pipeline delay* sekitar 10-140 siklus clock), mencegah CPU dari dugaan salah prediksi percabangan (*memory order violation*), serta menurunkan konsumsi daya pada inti eksekusi selama fase *spin-wait*.
4. Operasi `index & (Capacity - 1)` hanya bekerja secara matematis jika nilai `Capacity` bernilai bilangan biner tunggal berpangkat dua ($2^n$). Pada bilangan berpangkat dua, representasi biner `Capacity - 1` berupa rentetan bit 1 penuh (`0001'1111`), yang bertindak sebagai *bitmask* pemotong indeks identik dengan operasi modulo, namun dieksekusi dalam 1 siklus CPU clock.
5. Pemanggilan alokasi heap dinamis mengandalkan *lock internal allocator* (pbrk/mmap), rentan terhadap fragmentasi memori, serta memiliki variansi durasi eksekusi algoritma yang tidak deterministik, sehingga dapat merusak *worst-case latency* sistem.

#### Jawaban Bagian 3: Solusi Skenario Kasus Produksi
1. **Analisis Akar Masalah**: Peningkatan volume data memicu kontensi ekstrem pada atomic spinlock. Ketika thread pemegang spinlock terkena interupsi atau *preempt* oleh sistem operasi, thread-thread lain terus berputar (*spinning*) secara liar dan membuang siklus komputasi CPU secara sia-sia (*priority inversion & lock convoying*).
   **Solusi Desain Ulang**: Ganti atomic spinlock dengan antrean Lock-Free Bounded SPSC/MPMC Ring Buffer tanpa penguncian, isolasi core worker menggunakan *thread affinity* (`pthread_setaffinity_np`), dan aktifkan isolasi kernel Linux (`isolcpus`) agar core pemrosesan transaksi bersih dari interupsi thread sistem operasi lainnya.
2. **Solusi Pembersihan Memori**: Terapkan teknik *Epoch-Based Memory Reclamation* (EBR) atau *Hazard Pointers*. Dengan EBR, siklus operasional dibagi menjadi fase epoch global (misal: Epoch 1, 2, 3). Node yang dilepas dari antrean dimasukkan ke dalam daftar tunggu deallocasi (*limbo list*) yang diberi label epoch saat itu. Memori fisik node baru boleh dipanggil `delete` hanya ketika seluruh thread worker telah mengonfirmasi bahwa mereka telah berpindah meninggalkan epoch tersebut, menjamin tidak ada satupun thread yang memegang pointer referensi fisik lama.
3. **Analisis Akar Masalah**: Arsitektur prosesor x86-64 memiliki model memori terurut ketat (*strongly ordered TSO*), yang menyamarkan kesalahan penggunaan `memory_order_relaxed` karena CPU x86 secara hardware mencegah penataan ulang instruksi *Store-Store* dan *Load-Load*. Namun, ARM64 menerapkan model memori *Weakly Ordered Architecture*. Pada arsitektur ARM64, CPU diizinkan menata ulang urutan instruksi baca/tulis memori secara agresif demi performa.
   **Solusi Teknis**: Tinjau ulang seluruh checkpoint sinkronisasi atomik, hilangkan penggunaan `relaxed` pada jalur transfer kepemilikan variabel, dan terapkan pasangan sinkronisasi semantik eksplisit menggunakan `memory_order_release` pada thread produsen serta `memory_order_acquire` pada thread konsumen.

---

### 16. Summary

1. **Prinsip Dasar Konkurensi Modern**: Pemrograman performa tinggi dalam C++ berakar pada interaksi intim antara kode mesin, kompilator, dan arsitektur hierarki memori CPU (L1/L2/L3, MESI, Write Buffers).
2. **Kekuatan Model Memori Acquire-Release**: Pendekatan sinkronisasi *Acquire-Release* merupakan fondasi industri untuk merancang struktur data konkuren karena memangkas latensi instruksi *full memory barrier* (`seq_cst`) tanpa mengorbankan integritas aliran data transaksi.
3. **Pemberantasan Bottleneck Cache**: Penataan data atomik menggunakan `alignas(hardware_destructive_interference_size)` secara efektif mengeliminasi fenomena *False Sharing*, memastikan throughput sistem berskala linear terhadap penambahan inti prosesor.
4. **Desain Deterministik Tanpa Alokasi Dynamic**: Sistem produksi berkategori *ultra-low latency* wajib beroperasi dengan memori teralokasi di awal (*pre-allocated bounded ring buffer*) guna memastikan eksekusi runtime berjalan bebas dari jitter alokasi heap dan bebas *blocking context switch*.