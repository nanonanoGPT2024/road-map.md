# BAB 10: Materi Lanjutan
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
### Topik: Hardware-Conscious Concurrency, Memory Models, dan Lock-Free Data Structures

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Memitigasi Cache Invalidation Overhead**: Mengidentifikasi fenomena *False Sharing* dan mengoptimalkan penataan memori (*memory alignment & padding*) berbasis arsitektur *cache line* L1/L2/L3 prosesor x86-64 dan ARM64.
2. **Menerapkan Primitif Dekonstruksi Memori (*Memory Models*)**: Mengimplementasikan sinkronisasi konkuren menggunakan semantik *Sequential Consistency*, *Acquire-Release*, dan *Relaxed Ordering* secara tepat tanpa *undefined behavior*.
3. **Mengonstruksi Struktur Data *Lock-Free***: Merancang, menguji, dan memverifikasi struktur data *Single-Producer Single-Consumer* (SPSC) dan *Multi-Producer Multi-Consumer* (MPMC) *Bounded Queue* berbasis algoritma *Compare-And-Swap* (CAS) yang tahan terhadap *ABA Problem*.
4. **Menerapkan Pola Arsitektur *Zero-Copy* & I/O Ring**: Merancang arsitektur pipeline data throughput tinggi yang memanfaatkan teknik bypass *kernel-to-user space copying* via memory mapping dan antrean ring buffer berbasis perangkat keras.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
* Konsep dasar struktur data dan algoritma (Stack, Queue, Pointer Arithmetic, Time/Space Complexity).
* Dasar concurrency: Thread, Mutex, Deadlock, Race Condition, dan Critical Section.
* Arsitektur komputer dasar: Register, ALU, Cache Memory, RAM, dan Operating System Virtual Memory (Paging).
* Pengetahuan sintaksis bahasa tingkat sistem (C++20, Rust, atau Go dengan pemahaman terhadap *pointer* dan *atomic primitive*).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Hierarki Memori, Cache Lines, dan Koherensi (MESI/MOESI)

Modern Symmetric Multiprocessing (SMP) bergantung pada hierarki memori hierarkis bertingkat. Akses ke register CPU membutuhkan ~0.5 ns, L1 Cache (~1 ns), L2 Cache (~3–4 ns), L3 Shared Cache (~10–20 ns), sementara Main Memory (DRAM) membutuhkan ~60–100 ns (*Latency Gap* mencapai 2 orde magnitudo).

```
+-------------------------------------------------------------------------+
|                              CPU DIE                                    |
|                                                                         |
|  +---------------------------+             +--------------------------+ |
|  |          CORE 0           |             |          CORE 1          | |
|  |  +---------------------+  |             |  +--------------------+  | |
|  |  | Registers (~0.5ns)  |  |             |  | Registers (~0.5ns) |  | |
|  |  +---------------------+  |             |  +--------------------+  | |
|  |  | L1 D-Cache (64B)    |  |             |  | L1 D-Cache (64B)   |  | |
|  |  | (~1ns, Private)     |  |             |  | (~1ns, Private)    |  | |
|  |  +---------------------+  |             |  +--------------------+  | |
|  |  | L2 Cache (512KB)    |  |             |  | L2 Cache (512KB)   |  | |
|  |  | (~3-4ns, Private)   |  |             |  | (~3-4ns, Private)  |  | |
|  |  +---------------------+  |             |  +--------------------+  | |
|  +-------------+-------------+             +-------------+------------+ |
|                |                                         |              |
|                +--------------------+--------------------+              |
|                                     |                                   |
|                      +-----------------------------+                    |
|                      |  L3 Shared Cache (16-64MB)  |                    |
|                      |  (~10-20ns, All Cores)      |                    |
|                      +--------------+--------------+                    |
+-------------------------------------|-----------------------------------+
                                      | Interconnect (QPI/UPI/Infinity)
                       +--------------+--------------+
                       |      Main Memory (DRAM)     |
                       |         (~60-100ns)         |
                       +-----------------------------+
```

Unit transfer terkecil antara DRAM dan hierarki cache bukan berupa byte tunggal, melainkan **Cache Line** (umumnya 64 byte pada arsitektur x86-64 dan ARM modern). 

Untuk mempertahankan pandangan memori yang seragam pada seluruh *core*, sistem menggunakan protokol **Cache Coherence**, paling umum adalah varian protokol **MESI**:
* **M (Modified)**: Cache line hanya ada di cache lokal dan bersifat *dirty* (berbeda dari DRAM). Core ini memiliki hak eksklusif untuk menulis.
* **E (Exclusive)**: Cache line hanya ada di cache lokal, bersifat *clean* (sama dengan DRAM).
* **S (Shared)**: Cache line mungkin ada di cache milik core lain dan bersifat *clean*.
* **I (Invalid)**: Isi cache line tidak valid dan tidak boleh dibaca atau ditulis.

Ketika Core 0 menulis ke variabel dalam cache line berstatus `Shared`, Core 0 harus mengirim sinyal *Read-For-Ownership* (RFO) atau *Invalidate Queue* melalui bus interkoneksi ke seluruh core lain. Semua core lain memindahkan status cache line tersebut ke `Invalid`. Fenomena ini memicu tingginya inter-core latency bus contention.

#### 3.2. Hardware False Sharing

*False Sharing* terjadi ketika dua thread yang berjalan pada core berbeda memodifikasi variabel independen yang secara fisik berada pada *cache line* (64-byte boundary) yang sama. 

```
                64-Byte Cache Line Chunk
+-------------------------------------------------------+
|  Variabel A (Core 0 sering nulis) | Variabel B (Core 1 sering nulis) |
+-------------------------------------------------------+
        ^                                   ^
        |                                   |
     Core 0                              Core 1
```

Secara logika program, Variabel A dan B tidak memiliki keterikatan data (*no race condition*). Namun, pada tingkat silikon, setiap penulisan oleh Core 0 memaksa pembatalan (*cache invalidation*) seluruh baris 64 byte di Core 1, menghasilkan siklus *cache miss bouncing* bolak-balik yang menghancurkan skalabilitas multithreading linear.

#### 3.3. CPU Reordering, Memory Barriers, dan Memory Consistency Models

Prosesor modern menerapkan eksekusi spekulatif dan *out-of-order execution* (OoO), serta menyertakan *Store Buffers* dan *Invalidation Queues* untuk menyembunyikan latensi tulis. Akibatnya, urutan instruksi yang dieksekusi prosesor bisa berbeda dengan urutan instruksi dalam *source code*.

* **x86-64 (Strong Memory Model / TSO - Total Store Order)**:
  * Memori menjamin: *Store-Load* dapat di-*reorder*, tetapi *Store-Store*, *Load-Load*, dan *Load-Store* tidak akan dibalik urutannya.
* **ARM64 / POWER (Weakly Ordered Memory Model)**:
  * Bebas me-reorder hampir semua pasangan operasi read/write kecuali ada batasan *data dependency* atau eksplisit *Memory Barrier* (Memory Fence).

Tingkatan Semantik Memori Standar (C++20 / Rust):
1. **`memory_order_relaxed`**: Hanya menjamin operasi atomik (tidak ada *torn reads/writes*). Tidak ada garansi urutan sinkronisasi dengan operasi memori lain.
2. **`memory_order_acquire`** (Digunakan pada Operasi Baca/Load): Mencegah pembacaan atau penulisan memori setelah operasi ini dipindahkan mendahului operasi acquire ini.
3. **`memory_order_release`** (Digunakan pada Operasi Tulis/Store): Mencegah pembacaan atau penulisan memori sebelum operasi ini dipindahkan ke setelah operasi release ini. Segala mutasi sebelum *release* terlihat oleh thread lain yang melakukan *acquire* pada atomic variable yang sama.
4. **`memory_order_seq_cst`** (Sequential Consistency): Tingkat terketat; menerapkan *global total order* di seluruh core. Sangat mahal karena menyisipkan full barrier (e.g., instruksi `MFENCE` pada x86-64).

#### 3.4. Lock-Free Primitives: CAS dan ABA Problem

Struktur data *Lock-Free* menjamin bahwa dari sekian banyak thread yang mencoba menyelesaikan operasi, minimal satu thread dipastikan mengalami kemajuan (*system-wide progress guarantee*). Kunci dari primitif ini adalah instruksi atomik perangkat keras: **Compare-And-Swap (CAS)** (misalnya, `CMPXCHG` pada arsitektur x86).

```
bool CAS(T* address, T expected_value, T new_value) {
    // Dieksekusi secara atomik di tingkat perangkat keras
    if (*address == expected_value) {
        *address = new_value;
        return true;
    }
    return false;
}
```

##### The ABA Problem
Skenario klasik pada struktur data berbasis node seperti stack atau linked-list tanpa garbage collector:
1. Thread 1 membaca pointer $Top$ bernilai node $A$. Node $A$ mengarah ke node $B$.
2. Thread 1 bersiap melakukan `CAS(&Top, A, B)`, namun tertunda (*preempted* oleh OS scheduler).
3. Thread 2 berjalan:
   * Me-pop $A$.
   * Me-pop $B$ (memori $B$ didealokasikan).
   * Mendorong node baru $C$.
   * Mendorong kembali node $A$ yang ditarik dari memory pool recycle ke tumpukan.
4. $Top$ sekarang kembali bernilai $A$.
5. Thread 1 melanjutkan eksekusi: Memeriksa apakah $Top == A$. Nilainya cocok!
6. Thread 1 mengeksekusi CAS: `$Top` diarahkan ke `$B$`. Padahal memori `$B$` sudah didealokasikan atau rusak. Kerusakan memori (*heap corruption*) terjadi.

Solusi:
* **Tagged Pointer (Double-Word CAS / DWCAS)**: Menggabungkan pointer memori dengan integer version counter (misal, 64-bit pointer + 64-bit counter menggunakan instruksi `CMPXCHG16B` pada x86-64).
* **Hazard Pointers**: Mempertahankan daftar baca aktif per thread yang mencegah deallokasi memori sebelum thread pembaca selesai.
* **Epoch-Based Reclamation (EBR)**: Membagi alokasi memori ke dalam fase siklik (*epoch*); node hanya dimusnahkan jika seluruh thread telah melewati batas epoch tersebut.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Lock-Based / Mutex) | Pendekatan Hardware-Conscious (Lock-Free / Cache-Aware) |
| :--- | :--- | :--- |
| **Mekanisme** | OS Primitives (Futex, Mutex, Condition Variables) | Perangkat Keras Atomik (CAS, Load-Linked/Store-Conditional, Fences) |
| **Karakteristik Latensi** | P99 tidak terprediksi; rentan *Thread Preemption*, *Priority Inversion*, & *Context Switch Overhead* (~1-5 µs) | Latensi ultra-rendah dan deterministik (Sub-mikrodetik, ~10-50 ns) |
| **Cache Behavior** | Kerap mengabaikan alignment; rentan *False Sharing* antar thread | Isolasi ketat pada batas *Cache Line* 64-byte dengan padding eksplisit |
| **Deadlock Safety** | Rawan *Deadlock*, *Livelock*, dan *Lock Convoy* | Secara matematis bebas dari *Deadlock* (karena ketiadaan mutual exclusion lock) |
| **Kompleksitas Kode** | Rendah hingga Menengah | Sangat Tinggi; membutuhkan pemahaman mendalam tentang *memory model* dan *reordering* |

#### Kapan Menggunakan Pendekatan Ini?
* **Financial Trading Platforms (HFT / Low Latency Exchanges)**: Antrean order buku (*order book*) di mana latensi P99.99 di atas 1 mikrodetik menghasilkan kerugian finansial.
* **Network Packet Processing Engines**: Frame processing pada kernel-bypass framework (misal: DPDK, OpenOnload).
* **High-Throughput Telemetry & Logging Ingestion**: Ingesti jutaan metrik/event per detik per node tanpa membebani alokator GC atau OS context switcher.

---

### 5. How (Workflow detail)

Alur perancangan struktur data berkinerja tinggi berbasis *Single-Producer Single-Consumer (SPSC) Lock-Free Ring Buffer*:

```
[Producer Thread]
       |
       v
1. Baca 'tail' lokal (posisi tulis saat ini)
       |
       v
2. Muat 'cached_head' (menghindari pembacaan atomic bus 'head' yang sering)
       |
       +---> [Apakah Buffer Penuh? (tail + 1 == cached_head)]
                 |
                 +--- YA ---> 2a. Muat nilai aktual 'head' (atomic acquire)
                 |                 |
                 |                 +--> Masih Penuh? -> Kembalikan 'false' (Buffer Overflow/Drop)
                 |
                 +--- TIDAK -> Lanjut
                                   |
3. Tulis data ke array pada slot (tail & mask) [Plain Write]
       |
       v
4. Perbarui 'tail' dengan atomic store (memory_order_release)
       |
       v
   [Data Tersedia untuk Consumer]
```

```
[Consumer Thread]
       |
       v
1. Baca 'head' lokal (posisi baca saat ini)
       |
       v
2. Muat 'cached_tail'
       |
       +---> [Apakah Buffer Kosong? (head == cached_tail)]
                 |
                 +--- YA ---> 2a. Muat nilai aktual 'tail' (atomic acquire)
                 |                 |
                 |                 +--> Masih Kosong? -> Kembalikan 'false' (No Data)
                 |
                 +--- TIDAK -> Lanjut
                                   |
3. Ambil data dari array pada slot (head & mask) [Plain Read]
       |
       v
4. Perbarui 'head' dengan atomic store (memory_order_release)
       |
       v
   [Slot Memori Tersedia Kembali untuk Producer]
```

Aturan Operasional Eksekusi:
1. Producer hanya boleh menulis ke index `tail`. Consumer hanya boleh menulis ke index `head`.
2. Penggunaan ukuran ring buffer berbasis kelipatan dua ($2^N$) memungkinkan subtitusi operasi modulo (`%`) yang mahal dengan operasi bitwise AND (`index & (Capacity - 1)`).
3. Penempatan `head` dan `tail` dipisahkan secara fisik dengan *cache-line padding* minimal 64 byte untuk mengeliminasi *False Sharing*.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Meja Putar Restoran vs. Pintu Putar Manual
* **Lock-based (Mutex)**: Seperti satu kamar mandi umum dengan satu kunci fisik di kasir. Jika ada 10 orang yang ingin masuk, 9 orang harus mengantre di luar, berhenti melakukan pekerjaan apa pun (state: `BLOCKED/SLEEPING`), dan menunggu OS membangunkan mereka saat kunci dikembalikan. Proses membangunkan orang tidur (*context switch*) membutuhkan waktu dan tenaga besar.
* **Lock-free Ring Buffer**: Seperti ban berjalan sushi (*sushi conveyer belt*). Koki (Producer) meletakkan piring di zona penaruhannya sendiri, dan penikmat sushi (Consumer) mengambil piring di zona pengambilannya. Selama piring belum menumpuk penuh dan ban berjalan tidak kosong, koki dan pelanggan tidak pernah saling bertegur sapa, tidak berebut kuncian, dan bekerja pada segmen ruang masing-masing tanpa hambatan.

```
       PRODUCER CORE                               CONSUMER CORE
   [Writes at 'tail']                          [Reads at 'head']
           |                                           |
           v                                           v
+-----------------------+                   +-----------------------+
| Cache Line 0 (64-byte)|                   | Cache Line 1 (64-byte)|
| - tail_               |                   | - head_               |
| - cached_head_        |                   | - cached_tail_        |
| - padding[48 bytes]   |                   | - padding[48 bytes]   |
+-----------------------+                   +-----------------------+
           |                                           |
           +--------------------+----------------------+
                                |
                                v
           +-----------------------------------------+
           |      Ring Buffer Storage Array          |
           | [Slot 0] [Slot 1] [Slot 2] ... [Slot N] |
           +-----------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Demonstrasi dan Mitigasi False Sharing (C++20)

```cpp
#include <iostream>
#include <thread>
#include <vector>
#include <chrono>
#include <new>

// STRUKTUR DATA TANPA PADDING (Rentan False Sharing)
struct VulnerableData {
    uint64_t counter_a{0}; // Berdampingan langsung
    uint64_t counter_b{0}; // Berada pada cache line yang sama (64 byte)
};

// STRUKTUR DATA DENGAN CACHE-LINE PADDING (Terisolasi)
struct AlignedData {
    alignas(hardware_destructive_interference_size) uint64_t counter_a{0};
    alignas(hardware_destructive_interference_size) uint64_t counter_b{0};
};

void run_benchmark() {
    const uint64_t ITERATIONS = 500'000'000;

    // Test 1: False Sharing
    VulnerableData v_data;
    auto start = std::chrono::high_resolution_clock::now();
    
    std::thread t1([&]() {
        for (uint64_t i = 0; i < ITERATIONS; ++i) v_data.counter_a++;
    });
    std::thread t2([&]() {
        for (uint64_t i = 0; i < ITERATIONS; ++i) v_data.counter_b++;
    });
    t1.join();
    t2.join();
    
    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double, std::milli> vulnerable_dur = end - start;
    std::cout << "[False Sharing] Waktu Eksekusi: " << vulnerable_dur.count() << " ms\n";

    // Test 2: Cache-Line Aligned
    AlignedData a_data;
    start = std::chrono::high_resolution_clock::now();
    
    std::thread t3([&]() {
        for (uint64_t i = 0; i < ITERATIONS; ++i) a_data.counter_a++;
    });
    std::thread t4([&]() {
        for (uint64_t i = 0; i < ITERATIONS; ++i) a_data.counter_b++;
    });
    t3.join();
    t4.join();
    
    end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double, std::milli> aligned_dur = end - start;
    std::cout << "[Padded/Aligned] Waktu Eksekusi: " << aligned_dur.count() << " ms\n";
    std::cout << "Speedup Factor: " << vulnerable_dur.count() / aligned_dur.count() << "x\n";
}

int main() {
    run_benchmark();
    return 0;
}
```

#### 7.2. Practical Example: Production-Grade SPSC Lock-Free Ring Buffer

Implementasi di bawah ini dirancang dengan:
* `std::hardware_destructive_interference_size` untuk isolasi *cache-line*.
* Power-of-two capacity optimization via bitmasking.
* Explicit memory ordering (`acquire-release`) untuk performa optimal di x86 dan ARM.

```cpp
#pragma once
#include <atomic>
#include <cstddef>
#include <memory>
#include <new>
#include <optional>
#include <vector>

#if defined(__cpp_lib_hardware_interference_size)
    using std::hardware_destructive_interference_size;
#else
    // Fallback umum untuk x86-64 dan ARM64 modern
    constexpr size_t hardware_destructive_interference_size = 64;
#endif

template <typename T, size_t Capacity>
class SPSCRingBuffer {
    static_assert((Capacity && ((Capacity & (Capacity - 1)) == 0)), 
                  "Capacity harus bernilai kelipatan 2^N.");

public:
    SPSCRingBuffer() 
        : storage_(static_cast<T*>(::operator new(sizeof(T) * Capacity))) {}

    ~SPSCRingBuffer() {
        T discarded;
        while (pop(discarded));
        ::operator delete(storage_);
    }

    // Disable copy and move semantics
    SPSCRingBuffer(const SPSCRingBuffer&) = delete;
    SPSCRingBuffer& operator=(const SPSCRingBuffer&) = delete;
    SPSCRingBuffer(SPSCRingBuffer&&) = delete;
    SPSCRingBuffer& operator=(SPSCRingBuffer&&) = delete;

    template <typename... Args>
    bool emplace(Args&&... args) {
        const size_t current_tail = tail_.load(std::memory_order_relaxed);
        
        // Cek kapasitas: jika tail mengejar head dari belakang sebesar Capacity
        if ((current_tail - cached_head_) == Capacity) {
            cached_head_ = head_.load(std::memory_order_acquire);
            if ((current_tail - cached_head_) == Capacity) {
                return false; // Buffer penuh
            }
        }

        // Konstruksi objek secara in-place di raw memory
        new (&storage_[current_tail & BUFFER_MASK]) T(std::forward<Args>(args)...);

        // Publikasikan index tail baru kepada Consumer
        tail_.store(current_tail + 1, std::memory_order_release);
        return true;
    }

    bool push(const T& item) {
        return emplace(item);
    }

    bool push(T&& item) {
        return emplace(std::move(item));
    }

    bool pop(T& value) {
        const size_t current_head = head_.load(std::memory_order_relaxed);

        // Cek ketersediaan item: jika head menyamai tail
        if (current_head == cached_tail_) {
            cached_tail_ = tail_.load(std::memory_order_acquire);
            if (current_head == cached_tail_) {
                return false; // Buffer kosong
            }
        }

        // Ambil data dan jalankan destruktor eksplisit
        T* slot = &storage_[current_head & BUFFER_MASK];
        value = std::move(*slot);
        slot->~T();

        // Publikasikan index head baru kepada Producer
        head_.store(current_head + 1, std::memory_order_release);
        return true;
    }

    [[nodiscard]] bool empty() const noexcept {
        return head_.load(std::memory_order_relaxed) == tail_.load(std::memory_order_relaxed);
    }

    [[nodiscard]] size_t size() const noexcept {
        size_t head = head_.load(std::memory_order_relaxed);
        size_t tail = tail_.load(std::memory_order_relaxed);
        return (tail >= head) ? (tail - head) : (Capacity - (head - tail));
    }

private:
    static constexpr size_t BUFFER_MASK = Capacity - 1;
    T* const storage_;

    // Variabel yang sering dimodifikasi oleh Producer
    alignas(hardware_destructive_interference_size) std::atomic<size_t> tail_{0};
    size_t cached_head_{0}; // Hanya diakses oleh Producer thread

    // Variabel yang sering dimodifikasi oleh Consumer
    alignas(hardware_destructive_interference_size) std::atomic<size_t> head_{0};
    size_t cached_tail_{0}; // Hanya diakses oleh Consumer thread

    // Padding penutup untuk mencegah interferensi dengan variabel eksternal di stack/heap
    char padding_[hardware_destructive_interference_size - sizeof(size_t)];
};
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Ultra-Low-Latency Order Execution Gateway (Bursa Kripto / HFT)

* **Skala Sistem**:
  * Throughput: 5.000.000 order/detik.
  * Budget Latensi End-to-End: Max 5 mikrodetik pada P99.9.
  * Engine: Arsitektur Single-Writer Event Loop (mengadopsi LMAX Disruptor pattern).

* **Arsitektur Produksi**:

```
                       +----------------------------------+
                       |    Network Interface Card (NIC)  |
                       +-----------------+----------------+
                                         |
                                (Kernel Bypass / DPDK)
                                         |
                                         v
                       +----------------------------------+
                       |     Core 1: Network Ingestion    |
                       +-----------------+----------------+
                                         |
                       [SPSC Ring Buffer 1 - Lock-Free]
                                         |
                                         v
                       +----------------------------------+
                       |   Core 2: Matching Engine (ME)   |
                       |      - Single Threaded           |
                       |      - No Locks, No Dynamic Alloc|
                       |      - Pre-allocated Ring Memory |
                       +--------+----------------+--------+
                                |                |
      [SPSC Ring Buffer 2]      |                |      [SPSC Ring Buffer 3]
               |                |                |               |
               v                                                 v
+-------------------------------+              +-------------------------------+
|  Core 3: Market Data Publisher|              | Core 4: WAL / Audit Logger    |
|       (Zero-Copy UDP)         |              |       (io_uring Zero-Copy)    |
+-------------------------------+              +-------------------------------+
```

* **Permasalahan Sistem Awal**:
  * Implementasi awal menggunakan `std::mutex` dan `std::condition_variable` pada antrean input.
  * Hasil: Pada load 1,2 juta event/detik, latensi P99 membengkak ke 850 mikrodetik karena *thread context switching*, *priority inversion*, dan perebutan mutex lock antar core.
  * CPU Utilization menunjukkan 45% waktu habis pada `sys_futex` (kernel-space wait).

* **Solusi Rekayasa**:
  1. **Thread-to-Core Pinning (CPU Affinity)**:
     Setiap thread kritis dipasangi instruksi `pthread_setaffinity_np` ke Core CPU fisik non-isolasi terpisah (mengabaikan hyper-threaded logical core untuk mencegah resource sharing L1 cache).
  2. **Inter-Thread Communication via SPSC Lock-Free Queues**:
     Komunikasi antara Gateway Thread dan Matching Engine dialihkan sepenuhnya ke SPSC Lock-Free Queues yang dipisahkan oleh isolasi *64-byte alignment*.
  3. **Busy-Polling Spin Strategy**:
     Mengeliminasi *sleep/wake cycle*. Consumer tidak memanggil `futex()` saat antrean kosong; melainkan melakukan CPU spin-wait menggunakan instruksi `_mm_pause()` (x86 intrinsic) untuk menurunkan latensi deteksi data baru ke skala ~12 nanodetik.

* **Hasil Evaluasi Produksi**:
  * Throughput melonjak hingga 6.800.000 order/detik per instance.
  * Latensi P99.9 turun dari **850 µs** menjadi **2.4 µs**.
  * Penggunaan CPU berada dalam mode 100% user-space deterministik tanpa interupsi OS kernel.

---

### 9. Trade-offs

| Parameter | Lock-Based Concurrency | Lock-Free Concurrency | Busy-Spinning Lock-Free |
| :--- | :--- | :--- | :--- |
| **CPU Core Utilization** | Efisien saat *idle* (thread masuk status *sleep/blocked*). | Efisien hingga sedang (bergantung pada *backoff strategy*). | Ekstrem (100% konsumsi core secara konstan, bahkan tanpa beban). |
| **Power Consumption (Watts)** | Rendah; CPU masuk ke mode C-States hemat energi. | Sedang. | Sangat Tinggi; menghasilkan panas thermal tinggi (membutuhkan pendingin enterprise). |
| **P99 Latency Profile** | Buruk; rentan lonjakan ribuan mikrodetik akibat *scheduling OS*. | Sangat Baik; deterministik pada skala sub-mikrodetik. | Sempurna; *instantaneous response* tanpa wake-up latency. |
| **Complexity & Maintainability** | Sederhana; mudah diaudit menggunakan profiler umum. | Sangat Kompleks; membutuhkan verifikator formal (TSan, Loom). | Kompleks; memerlukan infrastruktur isolasi core khusus. |
| **Throughput Scaling** | Terhambat saat *contention* thread bertambah banyak. | Skalabilitas tinggi (*wait-free* atau *progress guarantee*). | Skalabilitas maksimal per thread pasangan (1-to-1). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan: Menggunakan `volatile` untuk Sinkronisasi Thread
* **Gejala**: Kode tetap mengalami *data race*, pembacaan nilai usang (*stale read*), atau crash acak pada arsitektur ARM64 / multi-socket.
* **Akar Masalah**: Dalam standar C++ dan Java, keyword `volatile` **bukan** primitif konkurensi. `volatile` hanya memberi tahu compiler bahwa variabel dapat berubah di luar pengetahuan compiler (misal memory-mapped hardware register), tetapi **tidak menghasilkan Memory Barrier** atau menghentikan reordering CPU.
* **Solusi**: Gunakan tipe atomik standar (`std::atomic<T>` di C++, `sync/atomic` di Go, atau `AtomicReference` di Java).

#### 2. Kesalahan: Abaikan Instruksi Pause pada Spin-Wait Loops
* **Gejala**: Core CPU mengalami *thermal throttling*, dan thread lain pada Hyper-Thread core yang sama mengalami starvation performa parah.
* **Akar Masalah**: Loop kosong seperti `while(!ready.load());` membanjiri pipeline CPU dengan spekulasi percabangan memori, memicu *memory-order violation pipeline flushes*.
* **Solusi**: Sisipkan hardware pause intrinsic di dalam spin-wait loop.
  ```cpp
  #if defined(__x86_64__) || defined(_M_X64)
      #include <immintrin.h>
      #define CPU_PAUSE() _mm_pause()
  #elif defined(__aarch64__)
      #define CPU_PAUSE() asm volatile("yield" ::: "memory")
  #else
      #define CPU_PAUSE() ((void)0)
  #endif

  while (!ready.load(std::memory_order_relaxed)) {
      CPU_PAUSE();
  }
  ```

#### 3. Kesalahan: ABA Problem Akibat Daftaran Ulang Alokasi Pointer (Memory Reuse)
* **Gejala**: Node pada lock-free linked list atau stack tiba-tiba terputus, data hilang, atau segment fault terjadi di lingkungan multi-threaded yang padat.
* **Akar Masalah**: Penunjuk memori yang dialokasikan oleh `malloc`/`new` sering kali mendapatkan alamat fisik heap yang sama dengan memori yang baru saja didealokasikan (*freelist reuse*).
* **Solusi**: Gunakan *Double-Word CAS* (Tagged Pointer) dengan *Version Counter* 64-bit yang berinkremen setiap modifikasi, atau implementasikan *Hazard Pointers* / *Epoch-Based Reclamation*.

---

### 11. Best Practices (Production Checklist)

| No | Kategori | Item Pemeriksaan Produksi | Status Verifikasi |
| :--- | :--- | :--- | :--- |
| 1 | **Architecture** | Apakah seluruh thread kritis diisolasi ke Core fisik mandiri menggunakan *Core Pinning / CPU Affinity*? | [ ] |
| 2 | **Memory** | Apakah setiap variabel status yang diakses oleh thread berbeda telah dipisahkan oleh padding setara `hardware_destructive_interference_size`? | [ ] |
| 3 | **Semantics** | Apakah ada verifikasi bahwa tidak ada sinkronisasi implisit yang mengandalkan `memory_order_seq_cst` kecuali benar-benar dibutuhkan? | [ ] |
| 4 | **Capacity** | Apakah ukuran circular ring buffer didefinisikan dalam kelipatan $2^N$ untuk mengeliminasi operasi modulo pembagian hardware? | [ ] |
| 5 | **Memory Allocation** | Apakah seluruh alokasi memori internal disiapkan di awal (*pre-allocation*) saat startup untuk mencegah alokasi heap (`malloc`/`new`) pada *hot path*? | [ ] |
| 6 | **Instrumentation**| Apakah profiler hardware counter (`perf stat -e cache-misses,L1-dcache-load-misses`) telah dijalankan di pipeline pengujian beban (*load testing*)? | [ ] |
| 7 | **Sanitizers** | Apakah *ThreadSanitizer (TSan)* dan *AddressSanitizer (ASan)* dijalankan bersih pada unit & stress test tanpa memunculkan peringatan race condition? | [ ] |

---

### 12. Hands-on Practice

Berikut adalah panduan pembuatan proyek praktikum untuk menguji dan membuktikan performa ring buffer lock-free terhadap false sharing dan mutex bottleneck. 

Struktur folder yang akan dibuat:
```
hands-on/m02/
├── Makefile
├── src/
│   ├── main.cpp
│   └── spsc_queue.hpp
└── scripts/
    └── benchmark.sh
```

#### Langkah 1: Siapkan Header Struktur Data
Simpan berkas implementasi `SPSCRingBuffer` di `hands-on/m02/src/spsc_queue.hpp` menggunakan kode dari **Seksi 7.2**.

#### Langkah 2: Buat Program Pengujian Kinerja Komparatif
Simpan kode berikut pada `hands-on/m02/src/main.cpp`:

```cpp
#include <iostream>
#include <thread>
#include <vector>
#include <mutex>
#include <queue>
#include <chrono>
#include "spsc_queue.hpp"

constexpr size_t TEST_ELEMENTS = 10'000'000;
constexpr size_t QUEUE_SIZE = 65536; // 2^16

void test_mutex_queue() {
    std::queue<uint64_t> q;
    std::mutex mtx;
    std::atomic<bool> done{false};

    auto start = std::chrono::high_resolution_clock::now();

    std::thread producer([&]() {
        for (uint64_t i = 1; i <= TEST_ELEMENTS; ++i) {
            while (true) {
                std::lock_guard<std::mutex> lock(mtx);
                if (q.size() < QUEUE_SIZE) {
                    q.push(i);
                    break;
                }
            }
        }
    });

    std::thread consumer([&]() {
        uint64_t consumed = 0;
        while (consumed < TEST_ELEMENTS) {
            std::lock_guard<std::mutex> lock(mtx);
            if (!q.empty()) {
                uint64_t val = q.front();
                q.pop();
                consumed++;
            }
        }
    });

    producer.join();
    consumer.join();

    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double, std::milli> dur = end - start;
    std::cout << "[Mutex Queue] Waktu: " << dur.count() << " ms | Throughput: " 
              << (TEST_ELEMENTS / dur.count()) * 1000.0 << " ops/sec\n";
}

void test_lockfree_spsc() {
    SPSCRingBuffer<uint64_t, QUEUE_SIZE> ring_buffer;

    auto start = std::chrono::high_resolution_clock::now();

    std::thread producer([&]() {
        for (uint64_t i = 1; i <= TEST_ELEMENTS; ++i) {
            while (!ring_buffer.push(i)) {
                // Spin wait
            }
        }
    });

    std::thread consumer([&]() {
        uint64_t consumed = 0;
        uint64_t val = 0;
        while (consumed < TEST_ELEMENTS) {
            if (ring_buffer.pop(val)) {
                consumed++;
            }
        }
    });

    producer.join();
    consumer.join();

    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double, std::milli> dur = end - start;
    std::cout << "[Lock-Free SPSC] Waktu: " << dur.count() << " ms | Throughput: " 
              << (TEST_ELEMENTS / dur.count()) * 1000.0 << " ops/sec\n";
}

int main() {
    std::cout << "Memulai Evaluasi 10 Juta Pesan...\n";
    test_mutex_queue();
    test_lockfree_spsc();
    return 0;
}
```

#### Langkah 3: Konfigurasi Makefile Otomatis
Simpan berkas `hands-on/m02/Makefile`:

```makefile
CXX = g++
CXXFLAGS = -std=c++20 -O3 -pthread -Wall -Wextra -march=native

TARGET = queue_benchmark
SRCS = src/main.cpp

all: $(TARGET)

$(TARGET): $(SRCS)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(SRCS)

clean:
	rm -f $(TARGET)

run: $(TARGET)
	./$(TARGET)

profile-cache: $(TARGET)
	perf stat -e cache-misses,L1-dcache-load-misses,instructions,cycles ./$(TARGET)
```

#### Langkah 4: Eksekusi dan Verifikasi
Jalankan di terminal Linux:
```bash
make
make run
```
Analisis perbedaan throughput antara kedua pola tersebut. Anda akan melihat peningkatan throughput lock-free ring buffer sebesar 5x hingga 20x dibandingkan antrean berbasis mutex.

---

### 13. Exercise

#### Tingkat Easy
Modifikasi kelas `SPSCRingBuffer` pada seksi praktikum agar mendukung metode `capacity()` yang mengembalikan kapasitas maksimum buffer tanpa memblokir thread.
* **Indikator Keberhasilan**: Program dapat mencetak kapasitas statis secara aman dan konstan ($O(1)$ time complexity) tanpa race condition.

#### Tingkat Medium
Implementasikan fungsi *batch pop* (`pop_batch(std::vector<T>& dest, size_t max_items)`) ke dalam `SPSCRingBuffer`.
* **Indikator Keberhasilan**: Mengambil hingga $N$ elemen dalam satu operasi update pointer sinkronisasi atomik tunggal (`head_.store`), bukan memperbarui head di setiap elemen, guna mereduksi atomic write cycles pada bus memori.

#### Tingkat Hard
Konstruksi struktur data **Lock-Free Treiber Stack** yang dilengkapi dengan mekanisme mitigasi **ABA Problem** menggunakan teknik *Tagged Pointers* (Double-Word CAS via `std::atomic<Node*>`).
* **Indikator Keberhasilan**: Lolos stress-test konkurensi ekstrem dari 16 thread paralel dengan ThreadSanitizer aktif tanpa laporan data-race atau pointer corruption.

---

### 14. Challenge

#### Skenario Kasus Produksi
Anda ditugaskan mendesain subsistem **Matching Engine Ingestion Bus** untuk platform perdagangan bursa multiaset berkinerja tinggi. 

**Batasan & Persyaratan Sistem**:
1. Terdapat 8 thread Gateway Penerima Order (*Multi-Producer*) yang menerima sinyal FIX protocol dari berbagai socket jaringan.
2. Terdapat 1 Core Matching Engine (*Single-Consumer*) yang mencocokkan order secara deterministik.
3. Anda tidak diperbolehkan menggunakan library pihak ketiga, tidak boleh memakai kunci (`std::mutex`, `pthread_mutex`, spinlocks), dan dilarang mengalokasikan memori dinamis (`malloc`, `new`) pada saat runtime order berjalan.
4. Desainlah struktur data **Lock-Free Multi-Producer Single-Consumer (MPSC) Bounded Ring Buffer**.
5. Wajib menyelesaikan persaingan multi-producer atomik menggunakan `compare_exchange_weak` atau `fetch_add` tanpa menyebabkan starvation berkepanjangan pada thread gateway lain ketika salah satu thread mengalami OS descheduling saat menulis data.

Ujilah performa engine Anda untuk memproses minimal **20.000.000 order bertingkat** dan laporkan metrik latensi persentil P50, P99, dan P99.99!

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Berapakah ukuran byte tipikal satu *Cache Line* pada arsitektur prosesor x86-64 modern?
2. Mengapa operasi modulus (`%`) sering dihindari dalam circular buffer berkecepatan tinggi, dan apa alternatif penggantinya?
3. Apa perbedaan mendasar antara sifat `atomic` dan kata kunci `volatile` pada kompilator C++?
4. Manakah di antara tingkatan memory ordering berikut yang menawarkan eksekusi hardware paling efisien dan longgar: `memory_order_seq_cst`, `memory_order_relaxed`, atau `memory_order_acquire`?
5. Mengapa penempatan dua variabel atomik yang sering dimutasi oleh dua thread berbeda ke dalam satu cache line yang sama dapat menurunkan performa sistem secara dramatis?

#### B. Pertanyaan Intermediate
6. Jelaskan apa yang dimaksud dengan protokol koherensi cache *MESI* dan apa konsekuensi bus hardware saat status berpindah ke `Invalid`!
7. Pada arsitektur yang menggunakan *Weak Memory Ordering* (seperti ARM64), apa bahaya dari mempublikasikan data ke consumer menggunakan operasi store biasa tanpa `std::memory_order_release`?
8. Bagaimana fenomena *ABA Problem* dapat terjadi pada struktur data Lock-Free Stack, dan bagaimana Tagged Pointer menyelesaikannya?
9. Mengapa instruksi `_mm_pause()` sangat penting disisipkan pada implementasi loop berputar (*busy spin-wait*)?
10. Apa keuntungan performa dari pola membaca variabel atomik ke cache lokal (`cached_head`) dibandingkan membaca langsung dari `atomic<size_t> head_` di setiap iterasi perulangan?

#### C. Skenario Kasus Produksi
11. Sebuah microservice telemetri performa tinggi mengalami lonjakan CPU 100% pada sistem monitoring Linux, namun throughput data yang tercatat rendah. Hasil trace menunjukkan miliaran instruksi `futex(FUTEX_WAIT)` terpanggil. Apa diagnosa arsitektural Anda, dan bagaimana strategi eliminasi akar masalahnya?
12. Anda mereview implementasi SPSC Queue dari tim junior engineer. Mereka meletakkan `head` dan `tail` berdampingan dalam satu `struct` tanpa padding tambahan. Pada environment unit test (1 core / single CPU testing environment), performa sangat cepat. Namun saat dideploy ke bare-metal server 64-core AMD EPYC, throughput turun hingga 80%. Mengapa hal ini terjadi?
13. Dalam sistem low-latency processing, mengapa arsitektur Single-Producer Single-Consumer (SPSC) yang dipadukan dengan teknik *Thread-to-Core Pinning* selalu menghasilkan latensi P99 yang jauh lebih stabil dibandingkan model thread pool worker bersama?

---

### Kunci Jawaban Singkat & Petunjuk Evaluasi Quiz

#### Bagian A (Basic)
1. **64 byte**.
2. Modulus melibatkan instruksi pembagian mesin (`IDIV`) yang memakan puluhan siklus CPU; penggantinya adalah operasi bitwise AND (`index & (Capacity - 1)`) yang hanya membutuhkan 1 siklus CPU (berlaku jika kapasitas bernilai $2^N$).
3. `atomic` menyediakan operasi atomik read-modify-write dan memory ordering barriers. `volatile` hanya mencegah optimasi register caching oleh compiler tanpa memberikan jaminan atomic bus atau reordering CPU.
4. `memory_order_relaxed`.
5. Karena memicu fenomena *False Sharing*, di mana penulisan pada satu variabel oleh Core A membatalkan cache line Core B secara terus-menerus, membebani interkoneksi cache antar core.

#### Bagian B (Intermediate)
6. MESI adalah protokol status cache line (Modified, Exclusive, Shared, Invalid). Transisi ke status `Invalid` memaksa core lain membuang salinan lokalnya dan mengambil ulang data dari L3 cache atau DRAM melalui interkoneksi bus.
7. CPU ARM64 dapat menukar urutan penulisan payload data dan penulisan flag/pointer. Akibatnya, consumer dapat membaca flag pointer baru sebelum data di balik pointer tersebut selesai ditulis secara fisik ke memori (*garbage/uninitialized data read*).
8. Terjadi ketika pointer berubah dari A ke B lalu kembali ke A. CAS mengira pointer tidak berubah, padahal node A mungkin menunjuk ke node rusak karena alokasi ulang. Tagged pointer menambahkan integer counter yang selalu berinkremen, sehingga deteksi kegagalan CAS tetap berjalan (`A(v1) != A(v2)`).
9. Mencegah pipeline stall akibat spekulasi percabangan memori yang salah, menghemat konsumsi energi inti CPU, dan memberikan resource eksekusi thread ke core hyper-threading pasangannya.
10. Mengurangi lalu lintas cache line invalidation request pada interkoneksi bus prosesor. Pembacaan nilai lokal hanya membebani cache L1 private.

#### Bagian C (Skenario Kasus Produksi)
11. Terjadi *lock contention* berlebihan antar ratusan worker thread yang memperebutkan lock bersama; thread sering diblokir dan dibangunkan oleh kernel (konteks switch tinggi). Solusi: Ubah arsitektur menjadi antrean non-blocking lock-free atau gunakan partisi data Sharded/Partitioned Actors.
12. Pada environment unit test 1 core, tidak ada konkurensi core riil pada bus cache line. Pada AMD EPYC 64-core, thread producer dan consumer dialokasikan pada core fisik (CCX) yang terpisah jauh; penempatan `head` dan `tail` pada satu cache line memicu *False Sharing* antar core/socket dengan penalti cache-coherence bus yang masif.
13. SPSC dengan CPU Affinity menghilangkan overhead perebutan lock (tidak ada mutual exclusion contention), mencegah OS preemptive context switching, dan menjaga *L1/L2 cache locality* tetap panas (*warm*) secara eksklusif.

---

### 16. Summary

1. **Hardware Awareness Adalah Kunci**: Pemrograman sistem konkurensi modern pada level enterprise menuntut pemahaman terhadap arsitektur fisik silikon prosesor: hirarki cache, ukuran cache line 64-byte, dan protokol koherensi (MESI).
2. **False Sharing Menghancurkan Skalabilitas**: Pemisahan memori yang tidak hati-hati antara thread yang berbeda dapat melumpuhkan performa multiprosesor secara drastis. Penataan memori berbasis *cache-line padding* (`alignas(64)`) mutlak diperlukan pada struktur data berkinerja tinggi.
3. **Pahami Memory Models**: Hindari ketergantungan buta pada `memory_order_seq_cst`. Memahami pola semantik pasangan `memory_order_release` dan `memory_order_acquire` memungkinkan kode berjalan dengan performa maksimal dan aman di seluruh variasi arsitektur silikon (x86, ARM, RISC-V).
4. **Lock-Free Bukan Sekadar Bebas Mutex**: Struktur data lock-free menjamin kemajuan sistem (*system-wide progress*), mengeliminasi *priority inversion*, dan mereduksi latensi P99 ekstrem, menjadikannya fondasi esensial untuk sistem berkecepatan tinggi seperti bursa finansial, pemrosesan jaringan real-time, dan engine telemetri skala masif.