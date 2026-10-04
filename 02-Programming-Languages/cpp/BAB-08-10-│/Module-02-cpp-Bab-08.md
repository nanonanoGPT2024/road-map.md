# Bab 08: Lock-Free Concurrency, Cache-Conscious Architectures, & C++20 Memory Model
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, *Systems/Software Engineer* mampu:
1. Membedah mekanika C++20 Memory Model, transisi *atomic cache-line*, dan *instruction reordering* pada arsitektur x86-64 dan ARM64 (aarch64).
2. Mendesain dan mengimplementasikan struktur data *lock-free* berkategori *wait-free single-producer single-consumer* (SPSC) dan *multi-producer multi-consumer* (MPMC) *bounded queue* tanpa *data race* atau *undefined behavior*.
3. Mengeliminasi fenomena *false sharing* dan mengontrol *cache-line bouncing* melalui penataan tata letak memori berbasis `std::hardware_destructive_interference_size` dan teknik *alignment*.
4. Mengembangkan strategi alokasi memori deterministik menggunakan *NUMA-aware memory arena allocator* untuk komputasi berlatensi ultra-rendah (*sub-microsecond execution*).
5. Mendiagnosis dan menyelesaikan masalah kongkurensi tingkat rendah seperti *ABA Problem*, *stale cache invalidation*, dan *pipeline stall* menggunakan *memory reclamation techniques* (Epoch-Based Reclamation/Hazard Pointers).

---

### 2. Prerequisite
Untuk menyerap materi secara optimal, Anda wajib menguasai:
- **C++ Core Foundation**: Sintaksis C++20 (*Concepts*, *Three-way Comparison*, *Templates metaprogramming* dasar).
- **Sistem Operasi & Arsitektur Komputer**: Konsep hirarki *cache* (L1, L2, L3), *virtual memory*, *page fault*, dan *preemptive multithreading*.
- **Dasar Primitif Sinkronisasi**: Memahami kelemahan `std::mutex`, `std::condition_variable`, serta konsep *critical section* dan *deadlock*.
- **Tooling**: Terbiasa menggunakan GCC 13+ / Clang 17+, CMake 3.25+, GDB/LLDB, serta profiler seperti `perf` dan Address/Thread Sanitizer (`-fsanitize=thread,address`).

---

### 3. Concept & Internal Architecture (Mendalam)

#### Arsitektur Fisik Mikroprosesor dan Model Koherensi Cache
Pada sistem multiprosesor modern, *core* CPU tidak berinteraksi langsung dengan memori utama (DRAM) saat mengeksekusi instruksi baca/tulis (*load/store*). Setiap *core* memiliki hirarki *cache* internal yang privat (L1i/L1d dan L2) serta *cache* terdistribusi/berbagi (L3 / Last Level Cache).

```
+-----------------------------------------------------------------------+
|                             DRAM (Memory)                             |
+-----------------------------------------------------------------------+
                                   ▲
                                   │
+-----------------------------------------------------------------------+
|                           L3 Cache (Shared)                           |
+-----------------------------------------------------------------------+
             ▲                                             ▲
             │                                             │
+-------------------------+                   +-------------------------+
|     L2 Cache (Core 0)   |                   |     L2 Cache (Core 1)   |
+-------------------------+                   +-------------------------+
             ▲                                             ▲
             │                                             │
+-------------------------+                   +-------------------------+
|    L1d Cache (Core 0)   |                   |    L1d Cache (Core 1)   |
+-------------------------+                   +-------------------------+
             ▲                                             ▲
             │                                             │
+-------------------------+                   +-------------------------+
|  Store Buffer | Invalidate |                   |  Store Buffer | Invalidate |
|      Queue (Core 0)     |                   |      Queue (Core 1)     |
+-------------------------+                   +-------------------------+
             ▲                                             ▲
             │                                             │
+-------------------------+                   +-------------------------+
|      Execution Core 0   |                   |      Execution Core 1   |
+-------------------------+                   +-------------------------+
```

Protokol koherensi *cache* (misal: **MESI** - *Modified, Exclusive, Shared, Invalid*) menjamin setiap *core* melihat status data yang valid. Namun, performa perangkat keras ditingkatkan menggunakan dua komponen asinkron:
1. **Store Buffers**: Menampung eksekusi *store* secara langsung agar instruksi berikutnya tidak memblokir pipeline eksekusi saat menunggu transmisi bus *cache*.
2. **Invalidate Queues**: Menampung pesan *cache-invalidation* dari core lain untuk diproses kemudian.

Dampaknya adalah **Memory Reordering**: urutan eksekusi instruksi assembly pada level CPU dapat berbeda dengan urutan instruksi pada kode sumber program C++.

#### C++20 Memory Orders & Formal Semantics
C++ tidak menggunakan arsitektur perangkat keras tertentu, melainkan model abstrak mesin memori (*Abstract Machine Memory Model*). Terdapat 6 model pemesanan memori (`std::memory_order`):

```cpp
enum class memory_order : /* unspecified */ {
    relaxed,
    consume, // Catatan: Implementasi saat ini dikonversi ke acquire
    acquire,
    release,
    acq_rel,
    seq_cst
};
```

1. **`memory_order_relaxed`**:
   - Menjamin sifat operasi *atomic* (tidak ada *torn read/write*).
   - **Tidak memberikan garansi sinkronisasi urutan** (*happens-before relationship*) terhadap memori di sekitarnya. Instruksi bebas ditata ulang oleh *compiler* dan prosesor.

2. **`memory_order_release` & `memory_order_acquire`**:
   - **Acquire-Release Semantics**.
   - Operasi *Store* dengan `memory_order_release` memastikan seluruh operasi *load* dan *store* **sebelumnya** pada *thread* yang sama tidak dapat digeser melewati titik *store* ini.
   - Operasi *Load* dengan `memory_order_acquire` memastikan seluruh operasi *load* dan *store* **setelahnya** pada *thread* yang sama tidak dapat dipindahkan mendahului titik *load* ini.
   - Pasangan ini membentuk relasi *synchronizes-with* antar-*thread* yang berbeda.

3. **`memory_order_seq_cst` (Sequentially Consistent)**:
   - Model *default* C++.
   - Mengimplementasikan seluruh aturan *Acquire-Release* ditambah penjaminan adanya **urutan global total** (*single globally observed total order*) atas seluruh operasi `seq_cst` lintas seluruh *thread*.
   - Membutuhkan instruksi *heavyweight barrier* (misal: `mfence` pada x86 atau `dmb ish` pada ARM), yang berdampak drastis pada degradasi *throughput* siklus CPU.

#### Fenomena False Sharing & Inter-core Cache Thrashing
Ketika dua variabel independen diakses oleh dua *core* berbeda berada dalam satu garis memori fisik yang sama (biasanya berukuran **64 bytes**, disebut *Cache Line*), modifikasi pada variabel A oleh Core 0 akan memaksa Core 1 membatalkan (*invalidate*) seluruh isi *cache line* tempat variabel B berada. Fenomena ini disebut **False Sharing**.
Solusinya: Mengalokasikan variabel pada batas *alignment* kelipatan ukuran *cache line* melalui `alignas(std::hardware_destructive_interference_size)`.

---

### 4. Why & What

| Dimensi | Mutex-Based Concurrency | Lock-Free Concurrency |
| :--- | :--- | :--- |
| **Mekanisme Proteksi** | OS-managed blocking (futex, context-switch, OS scheduler yield). | Hardware-assisted atomic instructions (`CMPXCHG`, `LDREX`/`STREX`). |
| **Worst-case Latency** | Tidak deterministik (bergantung pada *scheduling quanta*, resiko *priority inversion*). | Deterministik (*bounded-step guarantees* pada algoritma *Wait-Free*). |
| **Overhead Sistem** | Transisi *user-to-kernel space*, *cache misses* akibat *thread descheduling*. | Murni *user-space*, saturasi interkoneksi bus prosesor jika terjadi *CAS retry loop*. |
| **Deadlock Vulnerability** | Tinggi jika terdapat perolehan kunci asimetris atau terminasi mendadak. | Nol (Secara matematis kebal terhadap *deadlock* struktural). |
| **Tingkat Kompleksitas** | Relatif rendah, alur linier, mudah diinspeksi. | Sangat tinggi, rentan terhadap masalah *memory visibility*, *ABA*, dan *compiler optimizations*. |

**Kapan menggunakan Lock-Free?**
Gunakan arsitektur *lock-free* hanya saat:
- Sistem Anda memiliki *budget* latensi ketat (misal: *Matching Engine*, *High-Frequency Trading*, *Audio Processing DSP*, *Driver Network DPDK*).
- Operasi dijalankan dalam konteks sinyal (*signal handlers*) atau interupsi *kernel* di mana operasi tidur (*blocking*) dilarang keras.

---

### 5. How (Workflow Detail)

Implementasi struktur data *Lock-Free Ring Buffer* (SPSC) yang aman mengikuti prosedur deterministik berikut:

```
[PRODUCER THREAD]                                 [CONSUMER THREAD]
       │                                                 │
       ▼                                                 ▼
1. Muat head_idx privat                           1. Muat tail_idx privat
       │                                                 │
       ▼                                                 ▼
2. Muat cached_tail_idx                           2. Muat cached_head_idx
       │                                                 │
       ▼                                                 ▼
3. Apakah buffer penuh?                            3. Apakah buffer kosong?
   ├── YA: Muat tail_idx (Acquire)                   ├── YA: Muat head_idx (Acquire)
   │       Update cached_tail_idx                    │       Update cached_head_idx
   │       Jika masih penuh: Return false            │       Jika masih kosong: Return false
   └── TIDAK: Lanjut                                 └── TIDAK: Lanjut
       │                                                 │
       ▼                                                 ▼
4. Tulis payload ke slot [head_idx % Cap]         4. Baca payload dari slot [tail_idx % Cap]
       │                                                 │
       ▼                                                 ▼
5. head_idx.store(next_head, Release)             5. tail_idx.store(next_tail, Release)
       │                                                 │
       ▼                                                 ▼
   [Publish Data]                                   [Reclaim Slot]
```

1. **Alokasi Slot**: Ruang penyimpanan *ring-buffer* dialokasikan secara kontigu dengan kapasitas bernilai kelipatan $2^n$ untuk mengganti operasi modulo (`%`) yang mahal dengan operasi bitwise AND (`& (Capacity - 1)`).
2. **Pemberian Padding**: Pointer/Indeks `head` dan `tail` dipisahkan menggunakan *alignment* minimum sebesar ukuran *destructive interference* perangkat keras untuk mencegah *false sharing*.
3. **Penerbitan Memori (Release)**: *Producer* memodifikasi data muatan (payload) terlebih dahulu secara bebas, kemudian menggeser `head` menggunakan `std::memory_order_release`.
4. **Konsumsi Memori (Acquire)**: *Consumer* membaca `head` menggunakan `std::memory_order_acquire`. Ini menjamin payload telah sepenuhnya di-*commit* ke *cache hierarchy* sebelum dibaca oleh konsumen.

---

### 6. Analogy & Diagram ASCII

Bayangkan dua petugas pos: **Petugas A (Producer)** dan **Petugas B (Consumer)**, bekerja pada lemari loker bundar bernomor 0-7.

```
       Kondisi False Sharing (BURUK):
       +-------------------------------------------------------------+
       |                  Satu Cache Line (64 Bytes)                 |
       |  [Indeks Head (8B)] [Indeks Tail (8B)] [Padding Tak Terpakai] |
       +-------------------------------------------------------------+
               ▲                         ▲
          Core 0 Write              Core 1 Write
          (Invalidasi)              (Invalidasi) <--- Bouncing!

       Kondisi Cache Line Padded (IDEAL):
       +------------------------------------+
       |  Cache Line 0 (64 Bytes)           |
       |  [Indeks Head (8B)] [Padding 56B]  |
       +------------------------------------+
                         ▲
                    Core 0 Write (Independen)

       +------------------------------------+
       |  Cache Line 1 (64 Bytes)           |
       |  [Indeks Tail (8B)] [Padding 56B]  |
       +------------------------------------+
                         ▲
                    Core 1 Write (Independen)
```

Jika indeks loker ditulis pada buku catatan yang sama (*cache line* yang sama), setiap kali Petugas A menulis nomor loker baru, ia merebut buku tersebut dari tangan Petugas B. Akibatnya, Petugas B harus menunggu (*cache-line invalidation stall*), meski loker yang mereka kelola sebenarnya berbeda. Memisahkan catatan ke dalam dua buku terpisah (*padding 64 bytes*) melenyapkan friksi ini.

---

### 7. Simple Example & Practical Example

#### Simple Example: Mengamati Efek Reordering & Memory Barriers
Kode dasar berikut mendemonstrasikan bagaimana interaksi *Acquire-Release* bekerja mengamankan transfer kepemilikan variabel non-atomik.

```cpp
#include <atomic>
#include <cassert>
#include <string>
#include <thread>

std::string g_payload;
std::atomic<bool> g_ready{false};

void producer_routine() {
    // 1. Modifikasi non-atomic state
    g_payload = "CRITICAL_PAYLOAD_DATA_OK";
    
    // 2. Publish: Operasi store dengan memory_order_release.
    // Menjamin payload selesai ditulis sebelum flag ready di-set true.
    g_ready.store(true, std::memory_order_release);
}

void consumer_routine() {
    // 3. Acquire: Menunggu hingga flag ready bernilai true.
    // Membaca flag dengan memory_order_acquire mengimpor state
    // yang dipublikasikan oleh release-store producer.
    while (!g_ready.load(std::memory_order_acquire)) {
        // Spin-wait / cpu relax
        #if defined(__x86_64__) || defined(_M_X64)
        __builtin_ia32_pause();
        #endif
    }
    
    // 4. Akses aman ke non-atomic state tanpa data race
    assert(g_payload == "CRITICAL_PAYLOAD_DATA_OK");
}

int main() {
    std::thread t2(consumer_routine);
    std::thread t1(producer_routine);
    
    t1.join();
    t2.join();
    return 0;
}
```

#### Practical Example: High-Throughput Wait-Free SPSC Ring Buffer
Implementasi *production-ready* dari antrean sirkular *single-producer single-consumer* yang aman, bebas alokasi dinamis saat berjalan (*zero runtime allocations*), dan terlindungi dari *false sharing*.

```cpp
#pragma once

#include <atomic>
#include <cstddef>
#include <concepts>
#include <new>
#include <optional>
#include <utility>
#include <type_traits>
#include <array>

#if defined(__cpp_lib_hardware_interference_size)
    using std::hardware_destructive_interference_size;
#else
    // Fallback arsitektur umum x86-64 / modern ARM
    constexpr std::size_t hardware_destructive_interference_size = 64;
#endif

template <typename T, std::size_t Capacity>
    requires std::is_nothrow_destructible_v<T> && 
             ((Capacity >= 2) && ((Capacity & (Capacity - 1)) == 0)) // Wajib Power of Two
class SPSCRingBuffer {
public:
    SPSCRingBuffer() : m_head(0), m_tail(0), m_cached_tail(0), m_cached_head(0) {
        // Alokasi memori mentah tanpa mengkonstruksi objek terlebih dahulu
    }

    ~SPSCRingBuffer() {
        T discarded;
        while (pop(discarded)) {
            // Drain seluruh isi dan panggil destruktor
        }
    }

    SPSCRingBuffer(const SPSCRingBuffer&) = delete;
    SPSCRingBuffer& operator=(const SPSCRingBuffer&) = delete;
    SPSCRingBuffer(SPSCRingBuffer&&) = delete;
    SPSCRingBuffer& operator=(SPSCRingBuffer&&) = delete;

    template <typename... Args>
        requires std::constructible_from<T, Args...>
    bool emplace(Args&&... args) noexcept(std::is_nothrow_constructible_v<T, Args...>) {
        const std::size_t current_head = m_head.load(std::memory_order_relaxed);
        
        // Optimasi: Cek terhadap cached_tail terlebih dahulu untuk meminimalkan inter-core cache snooping
        if ((current_head - m_cached_tail) == Capacity) {
            m_cached_tail = m_tail.load(std::memory_order_acquire);
            if ((current_head - m_cached_tail) == Capacity) {
                return false; // Queue Penuh
            }
        }

        // Penempatan konstruksi in-place pada buffer internal
        auto* slot_ptr = reinterpret_cast<T*>(&m_storage[current_head & BUFFER_MASK]);
        ::new (static_cast<void*>(slot_ptr)) T(std::forward<Args>(args)...);

        // Terbitkan kepemilikan data ke consumer
        m_head.store(current_head + 1, std::memory_order_release);
        return true;
    }

    bool push(const T& item) noexcept(std::is_nothrow_copy_constructible_v<T>) {
        return emplace(item);
    }

    bool push(T&& item) noexcept(std::is_nothrow_move_constructible_v<T>) {
        return emplace(std::move(item));
    }

    bool pop(T& value) noexcept(std::is_nothrow_move_assignable_v<T>) {
        const std::size_t current_tail = m_tail.load(std::memory_order_relaxed);

        // Optimasi: Cek terhadap cached_head
        if (current_tail == m_cached_head) {
            m_cached_head = m_head.load(std::memory_order_acquire);
            if (current_tail == m_cached_head) {
                return false; // Queue Kosong
            }
        }

        auto* slot_ptr = reinterpret_cast<T*>(&m_storage[current_tail & BUFFER_MASK]);
        value = std::move(*slot_ptr);
        slot_ptr->~T(); // Panggil destruktor eksplisit

        // Reklamasi slot untuk produsen
        m_tail.store(current_tail + 1, std::memory_order_release);
        return true;
    }

    [[nodiscard]] bool empty() const noexcept {
        return m_tail.load(std::memory_order_relaxed) == m_head.load(std::memory_order_relaxed);
    }

    [[nodiscard]] std::size_t capacity() const noexcept {
        return Capacity;
    }

private:
    static constexpr std::size_t BUFFER_MASK = Capacity - 1;

    // Buffer penyimpanan mentah dengan alignment yang benar
    struct alignas(alignof(T)) StorageSlot {
        std::byte data[sizeof(T)];
    };
    std::array<StorageSlot, Capacity> m_storage;

    // Head Zone (Dimiliki secara eksklusif oleh Producer untuk Store)
    alignas(hardware_destructive_interference_size) std::atomic<std::size_t> m_head;
    std::size_t m_cached_tail; // Thread-local producer cache

    // Tail Zone (Dimiliki secara eksklusif oleh Consumer untuk Store)
    alignas(hardware_destructive_interference_size) std::atomic<std::size_t> m_tail;
    std::size_t m_cached_head; // Thread-local consumer cache
};
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Ultra-Low-Latency Order Execution Gateway (HFT)
Sebuah firma *High-Frequency Trading* menghadapi lonjakan *tail latency* (p99.99) dari $1.2\,\mu\text{s}$ menjadi $85\,\mu\text{s}$ saat memproses ledakan paket pasar (*market bursts*).

#### Investigasi Masalah
Profil menggunakan Linux `perf` menemukan degradasi bersumber dari:
1. Pemanggilan sistem operasi melalui `pthread_mutex_lock` saat antrean jaringan mentransfer paket ke antrean eksekusi order.
2. Penurunan performa drastis akibat alokasi memori dinamis (`malloc`/`free`) di dalam *hot path* transaksi.
3. Terjadinya penggusuran *cache* (*L1/L2 cache invalidations*) akibat *false sharing* antara thread penerima DPDK dan thread pengirim FIX Engine.

#### Solusi Rekayasa Terpadu
Arsitektur didesain ulang menggunakan pendekatan *Cache-Conscious Zero-Copy*:
1. Mengganti antrean berbasis mutex dengan **SPSC Lock-Free Circular Ring Buffer** beralamat tetap.
2. Setiap thread dikunci secara statis (*CPU core pinning*) ke *core* NUMA node yang identik dengan kartu jaringan (*NIC PCIe affinity*).
3. Menggunakan **NUMA-Local Arena Allocator** yang memesan satu blok memori berukuran 2MB (*HugePages*) pada fase inisialisasi aplikasi.

```
+-----------------------------------------------------------------------------------+
| NUMA Node 0 (Isolated Cores via isolcpus & taskset)                               |
|                                                                                   |
|  +---------------------+      Zero-Copy        +-------------------------------+  |
|  | Core 2: NIC Poller  | ──Lock-Free Ring────> | Core 4: Order Matching Engine |  |
|  | (DPDK Raw Frame Rx) |    Buffer (SPSC)      | (Evaluasi Signal & Risk)      |  |
|  +---------------------+                       +-------------------------------+  |
|            │                                                  │                   |
|     Local Arena Alloc                                  Local Arena Alloc          |
|      (HugePages 2MB)                                    (HugePages 2MB)           |
+-----------------------------------------------------------------------------------+
```

#### Hasil Metrik Produksi
- **P99.99 Execution Latency**: Turun dari $85\,\mu\text{s}$ menjadi **$780\,\text{ns}$** secara stabil.
- **CPU Context Switches**: Turun drastis hingga mendekati **0 context switch/sec** pada *hot core*.
- **Throughput Transaksi**: Meningkat dari $1.8 \times 10^6$ pesan/detik menjadi $14.2 \times 10^6$ pesan/detik per instance mesin.

---

### 9. Trade-offs

```
                  Latensi Rendah & Deterministik
                               ▲
                              / \
                             /   \
                            /     \
   (Lock-Free Data Struct) /       \ (NUMA-pinned Dedicated Cores)
                          /         \
                         /           \
                        ▼─────────────▼
    Kemudahan Pemeliharaan &    Efisiensi Utilisasi Hardware
      Portabilitas Kode             (Multi-Tenant Server)
```

1. **Throughput vs. CPU Utilization (Busy-Wait Penalty)**:
   - Pendekatan *lock-free wait-free* sering kali mengadopsi loop *spin-wait* (`pause` instruction).
   - *Trade-off*: Menghilangkan latensi *wake-up* kernel ($2\text{--}10\,\mu\text{s}$), tetapi memakan konsumsi daya dan siklus CPU 100% pada *core* tersebut secara terus-menerus.

2. **Kapasitas Bounded vs. Fleksibilitas Alokasi**:
   - Struktur data *lock-free* yang paling cepat adalah *bounded* (ukuran statis tetap).
   - *Trade-off*: Mengeliminasi alokasi dinamis runtime, tetapi jika antrean penuh, produsen dipaksa membuang pesan (*drop data*) atau beralih ke strategi *backpressure* yang kompleks.

3. **Kompleksitas Verifikasi vs. Kecepatan Operasi**:
   - Menghindari model sekuensial konsisten `std::memory_order_seq_cst` demi `acquire`/`release` memangkas siklus instruksi bus CPU.
   - *Trade-off*: Membuka peluang *subtle race conditions* yang mustahil dideteksi dengan pengujian fungsional biasa, requiring verifikasi formal melalui model *TLA+* atau *CDSChecker*.

---

### 10. Common Mistakes & Troubleshooting

#### 1. The Broken Spinlock (Relaxed Order Violation)
*Kesalahan*: Menggunakan `relaxed` untuk implementasi penguncian atau proteksi data.
```cpp
// SALAH: Undefined synchronization behavior!
std::atomic<bool> locked{false};
void lock() {
    while (locked.exchange(true, std::memory_order_relaxed)) {} // BUG: Data load/store dapat digeser melewati titik ini!
}
void unlock() {
    locked.store(false, std::memory_order_relaxed); // BUG: Modifikasi data bisa bocor ke luar lock!
}
```
*Solusi*: Gunakan minimal `std::memory_order_acquire` pada *exchange* dan `std::memory_order_release` pada *store*.

#### 2. False Sharing Akibat Pengabaian Padding
*Kesalahan*: Menaruh dua variabel atomik yang sering diakses bersama dalam sebuah *struct* tanpa instruksi penyelarasan (*alignment*).
```cpp
// SALAH: Dua thread akan saling membatalkan cache line masing-masing
struct MetricCounters {
    std::atomic<uint64_t> ingress_packets{0};
    std::atomic<uint64_t> egress_packets{0};
};
```
*Solusi*: Terapkan `alignas(hardware_destructive_interference_size)`.

#### 3. Aba-Problem pada CAS (Compare-And-Swap) Pointer
*Masalah*: Thread 1 membaca pointer $A$. Thread 2 menyela, mengubah $A \to B$, menghapus objek yang ditunjuk $A$, lalu mengalokasikan objek baru yang secara kebetulan mendapatkan alamat memori $A$ kembali, lalu mengubah pointer menjadi $A$. Thread 1 kembali mengeksekusi `compare_exchange_strong` dan mengira data tidak pernah berubah.
*Troubleshooting*:
- Gunakan *Tagged Pointers* (Pointer 64-bit yang digabungkan dengan counter modifikasi generasi 16-bit).
- Terapkan mekanisme *Epoch-Based Memory Reclamation* (EBR) atau `std::shared_ptr` dengan manipulasi atomic (`atomic_load` / `atomic_store`).

---

### 11. Best Practices (Production Checklist)

- [ ] **Alignment Enforced**: Pastikan variabel atomik yang dimodifikasi oleh thread yang berbeda dipisahkan oleh batas `hardware_destructive_interference_size`.
- [ ] **Bounded Allocations**: Tidak ada pemanggilan `new`, `malloc`, atau metode yang memicu realokasi dinamis (`std::vector::push_back`) di dalam *hot path*.
- [ ] **Non-Virtual Hot-Path**: Seluruh komponen infrastruktur antrean divalidasi tidak memuat fungsi virtual guna mencegah *vtable indirection overhead* dan memfasilitasi *inlining*.
- [ ] **Thread Sanitizer Clean**: Kode bersih tanpa peringatan saat dikompilasi dengan `-fsanitize=thread -O2`.
- [ ] **Compiler Fencing Verification**: Hasil kompilasi assembly divalidasi melalui Compiler Explorer (Godbolt) untuk mengonfirmasi ketiadaan instruksi penghalang berlebih (misal: instruksi `mfence` tak terduga pada x86-64).
- [ ] **Exception Specifications**: Metode *lock-free* ditandai eksplisit dengan kualifikasi `noexcept` untuk memandu optimasi register oleh compiler.
- [ ] **Warm-up & Page Pinning**: Alokasi buffer besar dieksekusi saat start-up, disentuh secara fisik (*pre-faulting*) untuk memicu alokasi page table, dan dikunci ke RAM menggunakan `mlock()`.

---

### 12. Hands-on Practice

Buat struktur direktori praktikum berikut pada terminal Anda:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
```

Simpan kode konfigurasi build berikut ke dalam berkas `hands-on/m02/CMakeLists.txt`:

```cmake
cmake_minimum_required(VERSION 3.25)
project(LockFreeProductionArchitecture CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Enable aggressive warnings and sanitize targets
add_compile_options(-Wall -Wextra -pedantic -Wconversion -Wshadow -O3)

add_executable(lock_free_benchmark main.cpp)
target_link_libraries(lock_free_benchmark PRIVATE pthread)

# Target sanitasi khusus untuk deteksi race conditions
add_executable(tsan_verifier main.cpp)
target_compile_options(tsan_verifier PRIVATE -fsanitize=thread -g -O1)
target_link_options(tsan_verifier PRIVATE -fsanitize=thread)
```

Simpan implementasi uji komprehensif ke dalam berkas `hands-on/m02/main.cpp`:

```cpp
#include <iostream>
#include <thread>
#include <vector>
#include <chrono>
#include <numeric>
#include <cassert>
#include <atomic>
#include <memory>
#include <array>
#include <span>

#if defined(__cpp_lib_hardware_interference_size)
    using std::hardware_destructive_interference_size;
#else
    constexpr std::size_t hardware_destructive_interference_size = 64;
#endif

// Implementasi Ring Buffer SPSC Produksi
template <typename T, std::size_t Capacity>
class ProductionSPSCQueue {
    static_assert((Capacity & (Capacity - 1)) == 0, "Capacity harus merupakan power of two!");
public:
    ProductionSPSCQueue() : m_head(0), m_tail(0), m_cached_tail(0), m_cached_head(0) {}

    template <typename... Args>
    bool try_emplace(Args&&... args) noexcept {
        const std::size_t head = m_head.load(std::memory_order_relaxed);
        if ((head - m_cached_tail) == Capacity) {
            m_cached_tail = m_tail.load(std::memory_order_acquire);
            if ((head - m_cached_tail) == Capacity) {
                return false;
            }
        }

        ::new (static_cast<void*>(&m_buffer[head & BUFFER_MASK].storage)) T(std::forward<Args>(args)...);
        m_head.store(head + 1, std::memory_order_release);
        return true;
    }

    bool try_pop(T& out_value) noexcept {
        const std::size_t tail = m_tail.load(std::memory_order_relaxed);
        if (tail == m_cached_head) {
            m_cached_head = m_head.load(std::memory_order_acquire);
            if (tail == m_cached_head) {
                return false;
            }
        }

        auto* item_ptr = reinterpret_cast<T*>(&m_buffer[tail & BUFFER_MASK].storage);
        out_value = std::move(*item_ptr);
        item_ptr->~T();
        m_tail.store(tail + 1, std::memory_order_release);
        return true;
    }

private:
    static constexpr std::size_t BUFFER_MASK = Capacity - 1;
    struct Node {
        alignas(alignof(T)) std::byte storage[sizeof(T)];
    };

    std::array<Node, Capacity> m_buffer;

    alignas(hardware_destructive_interference_size) std::atomic<std::size_t> m_head;
    std::size_t m_cached_tail;

    alignas(hardware_destructive_interference_size) std::atomic<std::size_t> m_tail;
    std::size_t m_cached_head;
};

// Pengujian Skala Produksi
constexpr std::size_t TOTAL_OPERATIONS = 10'000'000;
constexpr std::size_t QUEUE_CAPACITY = 65536; // 64K slots

struct TelemetryEvent {
    uint64_t timestamp_ns;
    uint64_t sequence_id;
    double payload_value;
};

int main() {
    std::cout << "[SYSTEM] Memulai Benchmark Produksi Lock-Free SPSC...\n";
    std::cout << "[SYSTEM] Cache Line Destructive Interference Size: " 
              << hardware_destructive_interference_size << " bytes.\n";

    auto queue = std::make_unique<ProductionSPSCQueue<TelemetryEvent, QUEUE_CAPACITY>>();

    const auto start_time = std::chrono::high_resolution_clock::now();

    // PRODUCER THREAD
    std::thread producer([&queue]() {
        for (uint64_t i = 0; i < TOTAL_OPERATIONS; ++i) {
            TelemetryEvent event{
                .timestamp_ns = static_cast<uint64_t>(i * 10),
                .sequence_id = i,
                .payload_value = static_cast<double>(i) * 1.5
            };
            while (!queue->try_emplace(event)) {
                #if defined(__x86_64__) || defined(_M_X64)
                __builtin_ia32_pause();
                #endif
            }
        }
    });

    // CONSUMER THREAD
    std::thread consumer([&queue]() {
        TelemetryEvent received_event{};
        for (uint64_t i = 0; i < TOTAL_OPERATIONS; ++i) {
            while (!queue->try_pop(received_event)) {
                #if defined(__x86_64__) || defined(_M_X64)
                __builtin_ia32_pause();
                #endif
            }
            assert(received_event.sequence_id == i);
        }
    });

    producer.join();
    consumer.join();

    const auto end_time = std::chrono::high_resolution_clock::now();
    const auto elapsed_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(end_time - start_time).count();
    const double elapsed_seconds = static_cast<double>(elapsed_ns) / 1e9;
    const double ops_per_sec = static_cast<double>(TOTAL_OPERATIONS) / elapsed_seconds;

    std::cout << "[RESULT] Berhasil mentransfer " << TOTAL_OPERATIONS << " elemen.\n";
    std::cout << "[RESULT] Waktu Total   : " << elapsed_seconds << " detik.\n";
    std::cout << "[RESULT] Throughput    : " << (ops_per_sec / 1e6) << " Juta pesan/detik.\n";
    std::cout << "[RESULT] Rata-rata Latensi: " << (static_cast<double>(elapsed_ns) / TOTAL_OPERATIONS) << " ns/operasi.\n";

    return 0;
}
```

Jalankan pengujian dan verifikasi thread-safety:
```bash
cmake -B build -S .
cmake --build build --config Release
./build/lock_free_benchmark

# Jalankan pengujian sanitasi thread
./build/tsan_verifier
```

---

### 13. Exercise

#### Level Easy
Ubah implementasi `ProductionSPSCQueue` pada bab Hands-on agar memiliki method `[[nodiscard]] std::size_t size() const noexcept;`.
*Kriteria Penerimaan*:
- Method harus aman dipanggil secara kongkuren oleh thread manapun tanpa mengunci.
- Gunakan memory order yang tepat agar tidak menimbulkan *pipeline stall* yang tidak perlu (relaksasi pembacaan).

#### Level Medium
Kembangkan sebuah **Thread-Safe Fixed Object Pool (Free-List)** *Lock-Free* berukuran tetap untuk tipe data `T` tanpa alokasi dinamis saat runtime, menggunakan `std::atomic<Node*>` dan algoritma CAS (`compare_exchange_weak`).
*Kriteria Penerimaan*:
- Metode `allocate()` dan `deallocate(T* ptr)` memiliki kompleksitas waktu $O(1)$.
- Mengatasi masalah konkurensi dasar saat multithread serentak memanggil alokasi dan dealokasi.

#### Level Hard
Rancang dan implementasikan struktur data **MPMC (Multi-Producer Multi-Consumer) Bounded Queue** berbasis array berukuran tetap mengikuti algoritma Dmitry Vyukov.
*Kriteria Penerimaan*:
- Setiap slot dalam array memiliki nomor sekuensial tersendiri (`std::atomic<size_t> sequence`).
- Bebas dari *deadlock* dan tidak memanggil OS blocking primitif apapun.
- Tulis pengujian unit yang memvalidasi integritas data dengan 4 thread produsen dan 4 thread konsumen yang berjalan simultan.

---

### 14. Challenge

**Skenario Sistem Distribusi: Ultra-Low Latency Market Data Arbitrage Dispatcher**
Perusahaan Anda sedang membangun mesin arbitrase pasar keuangan terdistribusi. Anda menerima tugas untuk merancang komponen sentral bernama `ArbitrageDispatcher`:

1. **Spesifikasi Beban Kerja**:
   - Komponen menerima frame data pasar dari 2 thread I/O jaringan (menerima umpan harga UDP Multicast).
   - Data harus disebarkan (*fan-out*) ke 8 thread kalkulasi strategi perdagangan independen secara serentak.
2. **Karakteristik & Batasan**:
   - **Zero-Allocation**: Alokasi memori pada fase eksekusi dilarang keras ($0$ bytes heap allocation).
   - **Zero-Drop Policy**: Data tidak boleh hilang, tetapi thread pengirim kalkulasi strategi tidak boleh memperlambat kinerja penerimaan thread I/O (*Non-blocking broadcast*).
   - **Hardware Pinning**: Sistem berjalan pada server Dual-Socket AMD EPYC dengan 64-core per soket. Pengiriman pesan antar soket NUMA menimbulkan penalti latensi hingga $300\%$.
3. **Persyaratan Solusi Arsitektural**:
   - Tulis spesifikasi arsitektur memori (deskripsi teknis struktur ring buffer, manajemen NUMA nodes, penyusunan cache line).
   - Definisikan strategi *wait-free single-writer multiple-reader ring buffer* di mana satu thread menulis dan banyak thread membaca indeksnya sendiri secara independen.
   - Sertakan mekanisme penanganan jika salah satu thread strategi tertinggal (*slow consumer detection & mitigation*).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. Apa arti semantik dari operasi atomik dengan `std::memory_order_relaxed`?
2. Mengapa ukuran `sizeof(std::atomic<T>)` terkadang lebih besar daripada `sizeof(T)`?
3. Apa perbedaan fundamental antara algoritma kongkurensi bertipe *Lock-Free* dan *Wait-Free*?
4. Apa fungsi dari instruksi assembly `PAUSE` pada arsitektur prosesor x86 saat berada di dalam loop *spin-wait*?
5. Mengapa struktur `alignas(64)` sering digunakan pada implementasi antrean multi-core?

#### Bagian 2: Intermediate (5 Pertanyaan)
6. Jelaskan bagaimana pasangan `memory_order_release` pada thread A dan `memory_order_acquire` pada thread B membangun relasi *happens-before*!
7. Mengapa operasi `compare_exchange_weak` disarankan untuk digunakan di dalam sebuah perulangan (*loop*), dibandingkan `compare_exchange_strong`?
8. Pada arsitektur x86 (TSO - *Total Store Order*), apakah operasi *Store* dapat digeser mendahului operasi *Load* sebelumnya secara perangkat keras?
9. Apa yang dimaksud dengan fenomena *ABA Problem* dalam struktur data *lock-free stack* berbasis pointer, dan pada operasi CPU apa masalah ini muncul?
10. Mengapa membaca variabel atomik dengan `load(std::memory_order_relaxed)` sebelum melakukan modifikasi atomik dapat meningkatkan performa secara keseluruhan pada *hot-cache*?

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)
11. **Skenario A**: Dalam sebuah aplikasi pemrosesan audio berlatensi rendah, seorang *engineer* menggunakan antrean *lock-free* untuk mentransfer data sampel dari *audio rendering thread* (real-time priority) ke *logging thread* (normal priority). Ketika logging thread mengalami *page fault* atau terhenti sejenak oleh OS, audio rendering thread sesekali mengalami *glitch* (drop output). Telusuri penyebab interaksi ini pada level arsitektur antrean dan tentukan solusinya!
12. **Skenario B**: Tim Anda mendapati kode antrean berbasis `std::atomic<uint64_t>` berjalan sangat cepat pada mesin uji Intel x86-64, namun saat diuji pada server ARM64 Ampere Altra, terjadi inkonsistensi data parah (*assertion failure*). Kode tersebut menggunakan `std::memory_order_relaxed` untuk seluruh operasi penulisan payload dan indeks. Mengapa perbedaan arsitektur perangkat keras ini memicu *bug* tersebut?
13. **Skenario C**: Pada profiling server web throughput tinggi, ditemukan metrik CPU menunjukkan penggunaan 100% pada 16 core, namun throughput transmisi paket jaringan sangat rendah. Alat profiling `perf c2c` (cache-to-cache) mendeteksi jutaan kejadian `HITM` (*Hit Modified Cache Line*). Masalah struktural apa yang terjadi pada kode sistem tersebut, dan bagaimana rencana perbaikannya?

---

### Kunci Jawaban & Rationale Quiz

#### Jawaban Bagian 1: Basic
1. **Semantik `memory_order_relaxed`**: Hanya menjamin atomisitas (modifikasi terjadi secara utuh tanpa terjadi kerusakan bit / *torn-read-write*), tetapi sama sekali tidak memberikan batasan urutan eksekusi memori (*no synchronization or ordering constraints*) terhadap operasi memori lain di sekitarnya.
2. **Ukuran `std::atomic<T>`**: Terjadi jika tipe data `T` tidak didukung langsung oleh instruksi atomik perangkat keras prosesor (biasanya lebih besar dari 64-bit atau 128-bit), sehingga runtime menyertakan struktur *internal lock table/mutex* di dalam objek atomik tersebut.
3. **Lock-Free vs. Wait-Free**: Sistem *Lock-Free* menjamin bahwa secara sistemik minimal ada **satu thread** yang membuat kemajuan (*progress*) dalam sejumlah langkah terbatas. Sistem *Wait-Free* menjamin bahwa **setiap thread** dipastikan membuat kemajuan dalam sejumlah langkah deterministik tanpa bergantung pada thread lain.
4. **Fungsi instruksi `PAUSE`**: Menunda eksekusi pipeline prosesor untuk mencegah penalti *memory order violation* saat keluar dari loop *spin*, serta menurunkan konsumsi daya siklus *core* CPU saat melakukan *busy-waiting*.
5. **Fungsi `alignas(64)`**: Memaksa alamat memori variabel berada pada batas awal garis *cache line* (64 byte), mencegah dua variabel yang dimodifikasi oleh core berbeda berada dalam satu *cache line* yang sama (*eliminasi false sharing*).

#### Jawaban Bagian 2: Intermediate
6. **Relasi Happens-Before**: Ketika Store-Release pada Thread A menulis nilai yang kemudian dibaca oleh Load-Acquire pada Thread B, seluruh operasi penulisan memori (baik atomik maupun non-atomik) yang terjadi sebelum Store-Release pada Thread A dijamin secara mutlak terlihat (*visible*) oleh Thread B setelah operasi Load-Acquire berhasil dieksekusi.
7. **`compare_exchange_weak` vs `strong`**: Pada mesin berbasis *Load-Linked/Store-Conditional* (seperti ARM, RISC-V), `compare_exchange_weak` dapat gagal secara semu (*spurious failure*) akibat interupsi konteks, tetapi menghasilkan instruksi assembly yang lebih ringkas dan cepat dibanding `strong`. Dalam loop rekursif, kegagalan semu dapat langsung diulang tanpa penalti ganda.
8. **Reordering Store-Load pada x86**: Ya. Arsitektur TSO pada x86 secara perangkat keras mengizinkan operasi *Store* yang tertunda di dalam *Store Buffer* dilewati oleh operasi *Load* berikutnya (*Store-Load reordering*). Reordering jenis lain (Store-Store, Load-Load, Load-Store) dilarang secara perangkat keras.
9. **ABA Problem**: Muncul pada operasi atomic *Compare-And-Swap* (CAS). Jika nilai lokasi memori berubah dari A ke B lalu kembali ke A, instruksi CAS akan mengevaluasi kondisi sebagai tidak berubah (sukses), padahal konteks logika atau struktur penunjuk internal telah mengalami modifikasi atau dealokasi.
10. **Manfaat Early Relaxed Load**: Membaca via `relaxed` memeriksa kondisi saat ini di dalam *cache* lokal L1. Jika kondisi belum terpenuhi, CPU tidak perlu memancarkan instruksi CAS yang memicu transmisi bus koherensi (*broadcast invalidation*), sehingga menghemat *bandwidth* bus interkoneksi *cache*.

#### Jawaban Bagian 3: Skenario Kasus Produksi
11. **Analisis Kasus A**:
    - *Penyebab*: Logging thread kemungkinan menahan pembaruan indeks baca (`tail`), menyebabkan ring buffer terisi penuh. Saat buffer penuh, audio thread real-time beralih ke kondisi *spin-wait* berkepanjangan atau memblokir, yang menghancurkan determinisme rendering audio real-time.
    - *Solusi Arsitektural*: Gunakan teknik *Overwriting Ring Buffer* (Drop-oldest pattern) khusus untuk telemetri log di mana audio thread selalu berhasil menulis dengan menimpa data log terlama, atau tingkatkan alokasi buffer kapasitas serta pisahkan thread logging menggunakan thread isolator khusus.
12. **Analisis Kasus B**:
    - *Penyebab*: x86 adalah arsitektur *Strong Memory Ordering* (TSO) di mana perangkat keras secara otomatis memberlakukan aturan *acquire/release* pada hampir semua instruksi beban/simpan biasa. Sebaliknya, ARM64 adalah arsitektur *Weakly-Ordered Memory*.
    - *Solusi*: Seluruh sinkronisasi yang mengandalkan keterlihatan data lintas core wajib dikonversi menggunakan sinkronisasi eksplisit: ubah penulisan flag/indeks dari `relaxed` menjadi `release`, dan pembacaan menjadi `acquire`.
13. **Analisis Kasus C**:
    - *Penyebab*: Metrik `HITM` yang sangat masif menandakan terjadinya **False Sharing parah** atau perebutan (*contention*) satu baris memori yang sama oleh seluruh 16 core secara simultan (*Cache Line Bouncing*).
    - *Solusi*: Identifikasi variabel global bersama melalui laporan `perf c2c`. Berikan jarak pembatas memori menggunakan `alignas(hardware_destructive_interference_size)` pada setiap struktur data individual milik worker thread, atau ubah arsitektur pemrosesan menjadi model *sharded / share-nothing partition per-core*.

---

### 16. Summary

1. Arsitektur performa tinggi modern didorong oleh pemahaman mendalam atas batas fisik perangkat keras: hirarki *cache*, saluran interkoneksi, dan implikasi mikroarsitektur dari protokol koherensi (seperti MESI).
2. Model Memori C++20 menyediakan abstraksi tingkat rendah yang memungkinkan rekayasawan mengarahkan compiler dan prosesor secara presisi melalui urutan memori: dari `relaxed` yang cepat namun bebas sinkronisasi, model pasangan `acquire-release` yang efisien, hingga `seq_cst` yang deterministik secara global namun mahal.
3. Kunci performa *lock-free* berskala enterprise terletak pada pencegahan *false sharing* menggunakan penataan memori terpadu (`hardware_destructive_interference_size`) serta penghapusan total alokasi memori dinamis pada *hot execution paths*.
4. Algoritma non-blocking bukan obat mujarab untuk semua masalah kongkurensi; penerapannya membutuhkan kompromi teknis yang matang, verifikasi mendalam melalui *sanitizer*, pembacaan assembly tingkat rendah, dan pengujian beban produksi yang ketat.