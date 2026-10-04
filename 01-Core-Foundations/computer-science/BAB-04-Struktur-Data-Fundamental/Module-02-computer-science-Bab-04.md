# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 01-Core-Foundations | **Bab 04:** BAB-04-Materi-Lanjutan

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Membedah Model Memori Perangkat Keras (Hardware Memory Models):** Memahami perbedaan mendasar antara model *Sequential Consistency*, *Total Store Order* (TSO pada x86-64), dan *Weakly-Ordered Systems* (ARM64/POWER), serta bagaimana instruksi CPU direorganisasi oleh *out-of-order execution engine*.
2. **Menguasai Semantik Atomics dan Memory Ordering:** Mengimplementasikan operasi atomik tingkat rendah menggunakan *relaxed*, *acquire-release*, dan *sequentially consistent memory ordering* untuk meminimalkan *pipeline stalls* tanpa menimbulkan *data race*.
3. **Merancang dan Membangun Struktur Data Lock-Free Berkinerja Ekstrem:** Membangun *bounded lock-free single-producer single-consumer* (SPSC) dan *multi-producer multi-consumer* (MPMC) *ring buffers* yang kebal terhadap *false sharing* dan masalah ABA (*ABA Problem*).
4. **Menerapkan *Mechanical Sympathy* pada Akses Cache:** Memanfaatkan hierarki cache CPU (L1/L2/L3), *cache line alignment* (64-byte padding), *cache prefetching*, serta mitigasi *cache thrashing* untuk menjaga latensi tetap deterministik di bawah sub-mikrodetik.
5. **Mengintegrasikan Pola Zero-Copy dan I/O Kernel-Bypass:** Menghilangkan *context-switch overhead* dan *buffer copying* di jalur transmisi data menggunakan primitive OS modern seperti `io_uring` dan *shared memory buffers*.

---

## 2. Prerequisite

Peserta wajib menguasai:

* **Sistem Komputer & Arsitektur CPU Dasar:** Siklus fetch-decode-execute, *pipelining*, register, stack vs heap, pointer arithmetic.
* **Dasar Multithreading & Konkurensi:** Pemahaman tentang POSIX threads (`pthreads`), race conditions, deadlocks, dan sinkronisasi standar berbasis mutual exclusion (`mutex`, `semaphore`).
* **Bahasa Pemrograman Tingkat Sistem:** Kemampuan membaca dan menulis C++ modern (C++17/C++20) atau C11, dengan pemahaman mendalam tentang manipulasi memori mentah, casting pointer, dan instruksi compiler intrinsik (`volatile`, `atomic`).

---

## 3. Concept & Internal Architecture

### 3.1 Hierarki Memori dan Protokol Cache Coherency (MESI)

Dalam arsitektur multiprosesor simetris (SMP), setiap *CPU core* memiliki register internal dan cache L1 (terpisah antara L1 *Instruction* dan L1 *Data*), cache L2 privat, serta berbagi cache L3 (*Last Level Cache* / LLC) sebelum mencapai *Main Memory* (DRAM).

```
+-------------------------------------------------------------------------+
|                              MAIN MEMORY (DRAM)                         |
+-------------------------------------------------------------------------+
                                    ^
                                    | 60-100 ns
                                    v
+-------------------------------------------------------------------------+
|                         SHARED L3 CACHE (LLC)                           |
+-------------------------------------------------------------------------+
               ^                                           ^
               | 10-20 ns                                  | 10-20 ns
               v                                           v
+-----------------------------+             +-----------------------------+
|        CORE 0 PRIVATE       |             |        CORE 1 PRIVATE       |
| +-------------------------+ |             | +-------------------------+ |
| |        L2 CACHE         | |             | |        L2 CACHE         | |
| +-------------------------+ |             | +-------------------------+ |
|              ^ 3-5 ns       |             |              ^ 3-5 ns       |
|              v              |             |              v              |
| +-------------------------+ |             | +-------------------------+ |
| |   L1 DATA / L1 INST     | |             | |   L1 DATA / L1 INST     | |
| +-------------------------+ |             | +-------------------------+ |
|              ^ ~1 ns        |             |              ^ ~1 ns        |
|              v              |             |              v              |
| [ALU / Execution Engine]   |             | [ALU / Execution Engine]   |
+-----------------------------+             +-----------------------------+
```

Unit transfer data terkecil antara DRAM dan cache adalah **Cache Line** (standar arsitektur modern: 64 byte). Untuk menjaga konsistensi data di seluruh core, CPU mengimplementasikan protokol **MESI**:
* **Modified (M):** Cache line hanya ada di cache lokal core saat ini dan nilainya *dirty* (berbeda dari DRAM).
* **Exclusive (E):** Cache line hanya ada di cache lokal core saat ini dan nilainya *clean* (sama dengan DRAM).
* **Shared (S):** Cache line ada di beberapa cache core sekaligus; nilainya *clean*.
* **Invalid (I):** Cache line tidak memuat data yang valid.

Ketika Core 0 menulis ke cache line yang berstatus *Shared*, Core 0 harus mengirimkan sinyal *Read For Ownership* (RFO) atau *Invalidation Message* melalui *interconnect bus* ke semua core lain. Core 1 harus menandai cache line miliknya sebagai *Invalid* sebelum Core 0 dapat menyelesaikan penulisan. Hal ini memicu latensi tinggi jika terjadi perebutan berulang (*cache line bouncing*).

### 3.2 Out-of-Order Execution, Store Buffers, & Memory Barriers

Untuk menyembunyikan latensi memori yang lambat, CPU tidak menunggu operasi store selesai masuk ke cache L1. CPU meletakkan penulisan tersebut ke dalam **Store Buffer** internal dan melanjutkan eksekusi instruksi berikutnya (*Out-of-Order Execution* / *Speculative Execution*).

* Pada **x86-64 (TSO - Total Store Order)**:
  * Store tidak di-reorder dengan Store lain (`Store-Store` aman).
  * Load tidak di-reorder dengan Load lain (`Load-Load` aman).
  * Load tidak di-reorder dengan Store sebelumnya (`Load-Store` aman).
  * **Pengecualian:** CPU dapat me-reorder `Store` diikuti `Load` ke alamat berbeda (`Store-Load` reordering).
* Pada **ARM64 / POWER (Weakly Ordered)**:
  * Hampir seluruh permutasi reordering diperbolehkan (`Store-Store`, `Load-Load`, `Store-Load`, `Load-Store`) kecuali jika ada dependensi data langsung atau dihalangi oleh instruksi **Memory Barrier** (*Fence*).

### 3.3 Tingkatan C++ Memory Ordering

1. **`memory_order_relaxed`**: Tidak ada jaminan sinkronisasi antar-thread; hanya menjamin bahwa operasi atomik pada variabel tersebut bersifat atomik (tidak terjadi pembacaan setengah jalan / *torn read*).
2. **`memory_order_release`**: Menjamin bahwa semua pembacaan dan penulisan memori yang dilakukan thread sebelum operasi ini tidak dapat di-reorder *melewati* batas penulisan release ini.
3. **`memory_order_acquire`**: Menjamin bahwa semua pembacaan dan penulisan memori yang dilakukan thread setelah operasi ini tidak dapat di-reorder *sebelum* batas pembacaan acquire ini.
4. **`memory_order_seq_cst` (Sequential Consistency)**: Memberikan jaminan *acquire-release* ditambah jaminan satu urutan eksekusi global yang identik (*single globally agreed order*) yang dilihat oleh seluruh thread di sistem. Merupakan opsi default namun paling mahal secara komputasi.

---

## 4. Why & What

| Pendekatan Konkurensi | Latensi Rata-rata | Skalabilitas (Core Count) | Karakteristik Performa | Alasan Mutlak Digunakan |
| :--- | :--- | :--- | :--- | :--- |
| **Mutex / Lock-Based** | 1.000 – 10.000 ns (1–10 µs) | Degradasi eksponensial akibat *contention* | Melibatkan intervensi OS Kernel (futex/syscall), *thread descheduling*, *context switch*. | Transaksi kompleks yang menyentuh multi-komponen dengan read/write ratio stabil tanpa kebutuhan sub-mikrodetik. |
| **Spinlock** | 50 – 500 ns | Sangat buruk pada *oversubscription* (CPU 100%) | Tetap berada di *user-space*, tetapi membuang siklus CPU dan membakar bus memori via *cache line bouncing*. | Critical section mikro (< 20 siklus CPU) di mana thread dipastikan berjalan di core terdedikasi tanpa context switch. |
| **Lock-Free (Atomics/CAS)** | 5 – 50 ns | Skalabilitas tinggi linear mendekati batas bus saturasi | Tidak pernah melakukan *block/sleep*; mengeksekusi instruksi perangkat keras atomik (`CMPXCHG`, `LDREX`/`STREX`). | Jalur ultra-low-latency (HFT, *financial matching engines*, gateway telemetri real-time, packet processing). |

### Mengapa Perlu Lock-Free?
Pada sistem skala enterprise berperforma tinggi, batas komputasi dipindahkan dari CPU cycles ke **Memory Wall** dan **Kernel Overhead**. Ketika sebuah thread terblokir oleh Mutex:
1. Thread beralih dari mode *User* ke mode *Kernel* (~1.500 siklus CPU).
2. OS mengeksekusi *scheduler*, menyimpan register thread, dan memuat state thread lain.
3. Cache L1 dan L2 menjadi tercemar (*cache pollution*).
4. Ketika lock dibuka, thread harus di-*wake up*, memicu *inter-processor interrupt* (IPI).

Total biaya context-switch dapat melampaui rentang **5.000 hingga 15.000 siklus CPU**. Arsitektur *Lock-Free* dan *Mechanical Sympathy* menjamin bahwa algoritma tetap membuat progres secara global (*system-wide progress guarantee*) tanpa pernah menyerahkan kendali ke OS scheduler.

---

## 5. How (Workflow Detail)

### 5.1 Siklus Hidup Lock-Free Single Producer Single Consumer (SPSC) Ring Buffer

```
[Producer Thread]                              [Consumer Thread]
      |                                                |
1. Hitung tail_next = (tail + 1) & mask                |
2. Baca head dengan memory_order_relaxed               |
3. Bandingkan tail_next == cached_head?                |
   |                                                   |
   +-- [Penuh?]                                        |
   |     |                                             |
   |     +-- Refresh cached_head dari head aktual      |
   |         menggunakan memory_order_acquire          |
   |                                                   |
   +-- [Tersedia Slot]                                 |
         |                                             |
4. Tulis payload ke buffer[tail]                       |
5. tail.store(tail_next, memory_order_release)         |
         |                                             |
         +=========== (Memory Barrier Release) =======>+
                                                       |
                                               6. Baca tail dengan memory_order_acquire
                                               7. Baca head dengan memory_order_relaxed
                                               8. Bandingkan head == tail?
                                                  |
                                                  +-- [Kosong?] Polling / Backoff
                                                  |
                                                  +-- [Ada Data]
                                                        |
                                               9. Baca data dari buffer[head]
                                              10. head.store((head + 1) & mask,
                                                             memory_order_release)
```

1. **Producer Writing:** Menulis data langsung ke slot memory pre-alokasi tanpa acquire lock.
2. **Release Visibility:** Store pada indeks `tail` menggunakan `memory_order_release`. Instruksi ini menjamin bahwa seluruh data payload *sudah tercommit ke cache line* sebelum nilai `tail` baru terlihat oleh core lain.
3. **Consumer Polling:** Consumer membaca indeks `tail` dengan `memory_order_acquire`.
4. **Data Acquisition:** Terbentuk hubungan *Synchronizes-With*. Pembacaan memori payload dijamin melihat data mutakhir yang ditulis oleh producer.

---

## 6. Analogy & Diagram ASCII

### Analogi: Meja Pertukaran Dokumen Dua Pegawai
Bayangkan dua pegawai, **P (Producer)** dan **C (Consumer)**, bekerja di ruangan terpisah yang dihubungkan oleh sebuah meja bundar berputar dengan 8 slot bernomor.
* **Dengan Mutex:** Setiap kali P ingin meletakkan map, P harus memanggil satpam, mengunci seluruh pintu ruangan, berjalan ke meja, meletakkan map, membuka kunci pintu, dan memanggil satpam kembali untuk memberi tahu C. Latensi tinggi dihabiskan untuk interaksi dengan satpam (OS Kernel).
* **Lock-Free (Mechanical Sympathy):** Meja bundar memiliki dua penunjuk jarum jam di dinding: jarum P (indeks penulisan) dan jarum C (indeks pembacaan). P hanya menulis di slot kosong yang ditunjuk jarumnya sendiri, lalu menggeser jarumnya satu strip. C hanya membaca dari slot yang ditinggalkan jarum P, lalu menggeser jarumnya sendiri. Keduanya tidak pernah menyentuh jarum yang sama secara bersamaan, menghilangkan kebutuhan satpam sepenuhnya.

### Diagram: False Sharing vs Cache Line Padding

#### Kondisi Rusak (False Sharing Terjadi):
Kedua atomik berada dalam satu Cache Line (64-byte). Perubahan pada Core 0 membatalkan seluruh cache line di Core 1!

```
+---------------------------------------------------------------+
|                      CACHE LINE (64 Byte)                     |
|  +-----------------------------+----------------------------+ |
|  | head (Core 0 R/W) (8 byte)  | tail (Core 1 R/W) (8 byte) | |
|  +-----------------------------+----------------------------+ |
+---------------------------------------------------------------+
                ^                               ^
                | Invalidation Storm!           |
          Core 0 (Producer)               Core 1 (Consumer)
```

#### Kondisi Optimal (Cache Line Padded):
Setiap variabel atomik ditempatkan pada cache line terpisah menggunakan padding atau `alignas(64)`.

```
CACHE LINE A (64 Byte):
+--------------------------------+------------------------------+
| head (Core 0 R/W) (8 byte)     | Dead Padding (56 byte)       |
+--------------------------------+------------------------------+

CACHE LINE B (64 Byte):
+--------------------------------+------------------------------+
| tail (Core 1 R/W) (8 byte)     | Dead Padding (56 byte)       |
+--------------------------------+------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Memverifikasi Reordering dengan CPU Atomics

Contoh dasar demonstrasi pentingnya pemahaman memori ordering pada operasi *relaxed* vs *acquire/release*.

```cpp
#include <atomic>
#include <thread>
#include <cassert>
#include <iostream>

// Demonstrasi relasi synchronization antar-thread
std::atomic<int> payload{0};
std::atomic<bool> ready{false};

void producer() {
    payload.store(42, std::memory_order_relaxed);
    // release fence: menjamin payload.store selesai sebelum ready.store disiarkan
    ready.store(true, std::memory_order_release);
}

void consumer() {
    // acquire fence: menjamin pembacaan payload terjadi SETELAH ready bernilai true
    while (!ready.load(std::memory_order_acquire)) {
        // CPU hint untuk mengurangi konsumsi daya dan pipeline clearing latency
        #if defined(__x86_64__) || defined(_M_X64)
            __builtin_ia32_pause();
        #elif defined(__aarch64__)
            asm volatile("yield" ::: "memory");
        #endif
    }
    // Assertion dijamin SELALU BENAR di semua arsitektur CPU
    assert(payload.load(std::memory_order_relaxed) == 42);
    std::cout << "Data synchronized successfully: " << payload.load(std::memory_order_relaxed) << "\n";
}

int main() {
    std::thread t2(consumer);
    std::thread t1(producer);
    t1.join();
    t2.join();
    return 0;
}
```

### 7.2 Practical Example: Enterprise-Grade Bounded Lock-Free SPSC Ring Buffer

Berikut adalah implementasi *Single-Producer Single-Consumer FIFO Queue* dengan ukuran *power-of-two*, mitigasi penuh terhadap *false sharing*, dan semantik *acquire-release*.

```cpp
#ifndef SPSC_RING_BUFFER_HPP
#define SPSC_RING_BUFFER_HPP

#include <atomic>
#include <cstddef>
#include <new>
#include <utility>
#include <type_traits>
#include <vector>

// Standar ukuran cache line x86 dan ARM64 modern
#if defined(__cpp_lib_hardware_interference_size)
    using std::hardware_destructive_interference_size;
#else
    constexpr size_t hardware_destructive_interference_size = 64;
#endif

template <typename T, size_t Capacity>
class SPSCRingBuffer {
    static_assert((Capacity >= 2) && ((Capacity & (Capacity - 1)) == 0), 
                  "Capacity harus berupa bilangan kuadrat 2 (power-of-two).");
    static_assert(std::is_nothrow_destructible<T>::value, 
                  "Tipe data T harus no-throw destructible.");

public:
    SPSCRingBuffer() 
        : buffer_(reinterpret_cast<StorageType*>(new std::byte[sizeof(StorageType) * Capacity])) {
        head_.store(0, std::memory_order_relaxed);
        tail_.store(0, std::memory_order_relaxed);
        cached_tail_.store(0, std::memory_order_relaxed);
        cached_head_.store(0, std::memory_order_relaxed);
    }

    ~SPSCRingBuffer() {
        T discarded;
        while (pop(discarded)) {}
        delete[] reinterpret_cast<std::byte*>(buffer_);
    }

    // Non-copyable, Non-movable untuk alasan keamanan konkurensi memori fisik
    SPSCRingBuffer(const SPSCRingBuffer&) = delete;
    SPSCRingBuffer& operator=(const SPSCRingBuffer&) = delete;

    template <typename... Args>
    bool emplace(Args&&... args) noexcept(std::is_nothrow_constructible<T, Args...>::value) {
        const size_t current_tail = tail_.load(std::memory_order_relaxed);
        const size_t next_tail = (current_tail + 1) & BufferMask;

        // Optimasi: Gunakan cached_head lokal untuk menghindari pembacaan atomik global L3/Bus
        if (next_tail == cached_head_.load(std::memory_order_relaxed)) {
            // Ambil head aktual via acquire untuk sinkronisasi mutakhir
            cached_head_.store(head_.load(std::memory_order_acquire), std::memory_order_relaxed);
            if (next_tail == cached_head_.load(std::memory_order_relaxed)) {
                return false; // Queue penuh
            }
        }

        // Construct object in-place (placement new)
        ::new (static_cast<void*>(&buffer_[current_tail])) T(std::forward<Args>(args)...);

        // Publikasikan pointer baru ke Consumer
        tail_.store(next_tail, std::memory_order_release);
        return true;
    }

    bool push(const T& item) noexcept(std::is_nothrow_copy_constructible<T>::value) {
        return emplace(item);
    }

    bool push(T&& item) noexcept(std::is_nothrow_move_constructible<T>::value) {
        return emplace(std::move(item));
    }

    bool pop(T& value) noexcept {
        const size_t current_head = head_.load(std::memory_order_relaxed);

        // Optimasi: Periksa cached_tail sebelum menyentuh variabel atomik tail_
        if (current_head == cached_tail_.load(std::memory_order_relaxed)) {
            cached_tail_.store(tail_.load(std::memory_order_acquire), std::memory_order_relaxed);
            if (current_head == cached_tail_.load(std::memory_order_relaxed)) {
                return false; // Queue kosong
            }
        }

        // Ambil elemen dari buffer
        T* slot = reinterpret_cast<T*>(&buffer_[current_head]);
        value = std::move(*slot);
        slot->~T(); // Explicit destructor invocation

        // Publikasikan head baru ke Producer
        head_.store((current_head + 1) & BufferMask, std::memory_order_release);
        return true;
    }

    [[nodiscard]] bool empty() const noexcept {
        return head_.load(std::memory_order_relaxed) == tail_.load(std::memory_order_relaxed);
    }

    [[nodiscard]] size_t capacity() const noexcept {
        return Capacity - 1; // 1 slot dikorbankan untuk membedakan status full vs empty
    }

private:
    static constexpr size_t BufferMask = Capacity - 1;
    using StorageType = typename std::aligned_storage<sizeof(T), alignof(T)>::type;

    StorageType* const buffer_;

    // Variabel yang diakses oleh Producer diletakkan dalam Cache Line sendiri
    alignas(hardware_destructive_interference_size) std::atomic<size_t> tail_{0};
    std::atomic<size_t> cached_head_{0}; // Hanya diakses Producer

    // Variabel yang diakses oleh Consumer diletakkan dalam Cache Line terpisah
    alignas(hardware_destructive_interference_size) std::atomic<size_t> head_{0};
    std::atomic<size_t> cached_tail_{0}; // Hanya diakses Consumer

    // Padding penutup untuk mencegah interferensi dengan variabel heap terdekat
    char padding_[hardware_destructive_interference_size - sizeof(std::atomic<size_t>)];
};

#endif // SPSC_RING_BUFFER_HPP
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: LMAX Disruptor Pattern pada High-Frequency Trading (HFT) Matching Engine

#### Konteks
Sebuah bursa perdagangan derivatif multi-aset global memproses lebih dari 6 juta pesan order per detik (*orders/sec*) per instrumen. Implementasi awal berbasis Java/C++ Concurrency dengan `std::mutex` dan `std::condition_variable` mengalami degradasi performa:
* **Latensi P50:** 4,2 mikrodetik.
* **Latensi P99:** 820 mikrodetik (terjadi *jitter spikes* ekstrem).
* **Akar Masalah:** *Thread contention* pada queue terpusat menyebabkan antrean eksekusi OS terganggu, *cache lines bouncing* di antara 32 socket CPU, serta OS context switches saat sistem mengalami beban puncak (*burst*).

```
[Gateway Transaksi] (Inbound Orders)
         |
         v
+-------------------------------------------------------+
|  PRE-ALLOCATED CIRCULAR RING BUFFER (Disruptor)       |
|  - Ukuran: 1,048,576 slots (Power of Two)             |
|  - Alokasi contiguous memory mlock() (No Paging)      |
+-------------------------------------------------------+
         |                                |
         v                                v
+------------------+             +--------------------+
| Journalling Node |             | Replikator Jaringan|
| (Core 2, No lock)|             | (Core 4, No lock)  |
+------------------+             +--------------------+
         \                                /
          \                              /
           v                            v
      +---------------------------------------+
      |  Business Logic Matching Engine       |
      |  (Core 6, Pinning & Busy Polling)     |
      +---------------------------------------+
```

#### Arsitektur Solusi
1. **Pola Ring Buffer Tunggal:** Mengganti seluruh message broker internal dan queue mutex dengan *Lock-Free Ring Buffer Array* tunggal yang telah dialokasikan sejak inisialisasi (*zero runtime memory allocation*).
2. **CPU Pinning (*Core Affinity*):** Producer (Jaringan/NIC thread), Journaller (Disk Persistence), Replikator (High Availability), dan Matching Engine masing-masing dikunci (*affinity-pinned*) ke Core CPU fisik individual menggunakan `pthread_setaffinity_np`.
3. **Penyelarasan Cache:** Setiap penunjuk sequence dilindungi dengan *padding* 64 byte untuk mengisolasi core L1/L2 cache.
4. **Busy-Spin Polling:** Pada core Matching Engine, thread tidak pernah beralih ke mode tidur (*blocking/sleeping*). Ketika tidak ada transaksi, thread mengeksekusi assembly `PAUSE` loop berlatensi deterministik.

#### Hasil Produksi
* **Throughput:** Meningkat dari 800.000 tx/sec menjadi **8.500.000 tx/sec**.
* **Latensi P50:** Berkurang dari 4,2 µs menjadi **120 nanodetik**.
* **Latensi P99:** Berkurang dari 820 µs menjadi **850 nanodetik** (Zero-Jitter Engine).

---

## 9. Trade-offs

Setiap keputusan optimasi ke tingkat arsitektur perangkat keras membawa konsekuensi sistemik:

| Parameter | Lock-Free Concurrency | Mutex-Based Concurrency | Actor / Channel Model (e.g. Go/Erlang) |
| :--- | :--- | :--- | :--- |
| **Throughput** | **Ekstrem** (10M - 50M ops/sec) | Sedang (1M - 3M ops/sec) | Sedang - Tinggi (2M - 8M ops/sec) |
| **Latensi (Tail P99.9)** | **Deterministik Sub-Mikrodetik** | Variatif (Rentan lonjakan OS context switch) | Tergantung pada runtime scheduler (Go runtime/BEAM) |
| **Kompleksitas Kode** | **Ekstrem Tinggi** (Rentan bug konkurensi memori tak terlacak) | Rendah - Menengah (Alur berpikir linier terlindungi lock) | Rendah (Kanal pesan terisolasi) |
| **Beban Konsumsi CPU** | **Sangat Tinggi** jika menggunakan busy-spin (100% utilitas satu core) | Rendah saat menganggur (*thread sleep*) | Efisien (Scheduler memarkir goroutine/green thread) |
| **Portabilitas** | Rentan bug arsitektur jika pindah dari x86 ke ARM64 (membutuhkan audit memori) | Portabel universal | Portabel universal (Abstraksi runtime) |
| **Biaya Hardware** | Memerlukan core CPU fisik terdedikasi (Isolasi core OS via `isolcpus`) | Murah (Bisa berbagi core/oversubscription) | Murah - Menengah |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 False Sharing
* **Gejala:** Kode multithreaded berjalan lebih lambat ketika jumlah core/thread dinaikkan, meskipun data antar-thread tidak saling bertumpukan.
* **Akar Masalah:** Dua variabel yang dimutasi oleh core yang berbeda berada pada rentang alamat fisik 64-byte yang sama. Protokol MESI memaksa cache line di-invalidasi terus-menerus.
* **Deteksi:**
  ```bash
  perf c2c record ./aplikasi_biner
  perf c2c report --stdio
  ```
  Periksa metrik *HITM* (Hit Modified cacheline in another core).
* **Solusi:** Terapkan `alignas(64)` pada masing-masing variabel atomik kritis.

### 10.2 The ABA Problem (pada Struktur Data CAS Multi-Consumer / Stacks)
* **Gejala:** Memory corruption dan segfault pada linked-list berbasis CAS saat dereferensi pointer node yang telah dibebaskan (*use-after-free*).
* **Penyebab:** Thread 1 membaca nilai A. Thread 2 mengubah A -> B -> membebaskan memori A -> mengalokasikan memori baru di alamat fisik A yang sama. Thread 1 mengeksekusi CAS(A, new); CAS berhasil padahal state internal telah hancur.
* **Solusi:**
  1. Gunakan *Tagged Pointers* (Double-Word CAS / `std::atomic<TaggedNode>` menggabungkan pointer 64-bit dan counter urutan 64-bit).
  2. Implementasikan teknik *Hazard Pointers* atau *Epoch-Based Reclamation* (EBR).

### 10.3 Asumsi Implicit Sequential Consistency pada Weak Memory (ARM)
* **Gejala:** Algoritma lolos unit testing di mesin developer (Intel Core i9/x86), tetapi mengalami data corruption secara acak ketika di-deploy ke server cloud berbasis ARM64 (AWS Graviton / Ampere).
* **Penyebab:** Developer menggunakan `std::memory_order_relaxed` di mana x86 tetap mempertahankan urutan pembacaan/penulisan secara perangkat keras (TSO), sedangkan core ARM secara agresif melakukan out-of-order store.
* **Solusi:** Jalankan unit testing di bawah *ThreadSanitizer* (`-fsanitize=thread`) dan audit seluruh atomik agar menggunakan relasi *Acquire-Release* eksplisit.

---

## 11. Best Practices (Production Checklist)

1. [ ] **Gunakan `alignas(64)` pada Atomics Independen:** Cegah *destructive interference* (False Sharing) antar-core.
2. [ ] **Hindari Alokasi Heap Dinamis di Jalur Kritis (Hot-Path):** Lakukan pre-alokasi seluruh node atau slot memory pada fase *bootstrap* aplikasi.
3. [ ] **Konfigurasi Power-of-Two Ring Buffers:** Selalu gunakan ukuran modulo berbasis bitwise bit-masking `(index & (size - 1))` menggantikan operasi pembagian/modulo matematika `(index % size)` yang mahal di ALU.
4. [ ] **Eksploitasi Cache Prefetching:** Tambahkan instruksi compiler built-in `__builtin_prefetch(ptr, 0, 3)` untuk memuat data ke cache L1 sebelum eksekusi traversal data berikutnya.
5. [ ] **Nonaktifkan CPU Throttling & Dynamic Scaling:** Di tingkat OS produksi, atur mode governor ke performa:
   ```bash
   cpupower frequency-set --governor performance
   ```
6. [ ] **Gunakan Kernel Parameter `isolcpus`:** Isolasi core CPU tertentu dari OS scheduler agar thread hot-path memegang 100% kendali tanpa preemption.
7. [ ] **Validasi Beban Kerja Thread Sanitizer:** Bangun build CI pipeline khusus dengan parameter compiler:
   ```bash
   clang++ -O2 -g -fsanitize=thread -Wall -Wextra main.cpp
   ```

---

## 12. Hands-on Practice

Dalam praktikum ini, Anda akan menyusun direktori kerja, mengompilasi kode benchmarking, dan mengevaluasi latensi serta cache misses secara real-time.

### Langkah 1: Struktur Proyek
Buat direktori dan berkas berikut:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
```

### Langkah 2: Buat File Implementasi Benchmarking (`hands-on/m02/benchmark.cpp`)

```cpp
#include <iostream>
#include <chrono>
#include <thread>
#include <vector>
#include "spsc_queue.hpp" // Menggunakan implementasi pada Seksi 7.2

constexpr size_t ITERATIONS = 10'000'000;
constexpr size_t QUEUE_CAPACITY = 65536;

SPSCRingBuffer<uint64_t, QUEUE_CAPACITY> ring_buffer;

void producer_thread() {
    for (uint64_t i = 1; i <= ITERATIONS; ++i) {
        while (!ring_buffer.push(i)) {
            #if defined(__x86_64__) || defined(_M_X64)
                __builtin_ia32_pause();
            #endif
        }
    }
}

void consumer_thread() {
    uint64_t value = 0;
    for (uint64_t i = 1; i <= ITERATIONS; ++i) {
        while (!ring_buffer.pop(value)) {
            #if defined(__x86_64__) || defined(_M_X64)
                __builtin_ia32_pause();
            #endif
        }
        if (value != i) {
            std::cerr << "Data Race Detected! Expected " << i << " but got " << value << "\n";
            std::exit(1);
        }
    }
}

int main() {
    std::cout << "Memulai benchmarking SPSC Ring Buffer Lock-Free...\n";
    std::cout << "Total items yang diproses: " << ITERATIONS << " elemen.\n";

    auto start_time = std::chrono::high_resolution_clock::now();

    std::thread producer(producer_thread);
    std::thread consumer(consumer_thread);

    producer.join();
    consumer.join();

    auto end_time = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double, std::milli> duration = end_time - start_time;

    double seconds = duration.count() / 1000.0;
    double throughput = static_cast<double>(ITERATIONS) / seconds;

    std::cout << "Selesai dalam: " << duration.count() << " ms\n";
    std::cout << "Throughput: " << throughput / 1'000'000.0 << " Juta pesan/detik\n";
    std::cout << "Rata-rata Latensi per Transmisi: " << (duration.count() * 1'000'000.0) / ITERATIONS << " ns\n";

    return 0;
}
```

Salin implementasi pada Seksi 7.2 ke dalam `hands-on/m02/spsc_queue.hpp`.

### Langkah 3: Kompilasi dengan Optimasi Tertinggi
```bash
g++ -O3 -std=c++17 -pthread -march=native -Wall -Wextra benchmark.cpp -o benchmark_spsc
```

### Langkah 4: Analisis Performa Cache Coherency Menggunakan Linux `perf`
Jalankan profiler perangkat keras untuk membuktikan tidak adanya cache stalls:
```bash
perf stat -e cache-misses,cache-references,L1-dcache-load-misses,instructions,cycles ./benchmark_spsc
```

---

## 13. Exercise

### Level Easy: Adaptive Backoff Policy
* **Tugas:** Pada implementasi loop antrean di mana buffer sedang kosong atau penuh, penggantian `__builtin_ia32_pause()` sederhana terkadang menghabiskan daya CPU jika antrean terhenti lama. Modifikasi bagian polling pada consumer agar mengimplementasikan strategi *Exponential/Adaptive Backoff*:
  1. Iterasi 1–16: Eksekusi instruksi CPU `PAUSE`.
  2. Iterasi 17–64: Panggil `std::this_thread::yield()`.
  3. Iterasi > 64: Gunakan `std::this_thread::sleep_for(std::chrono::microseconds(50))`.
* **Kriteria Sukses:** Penggunaan utilitas CPU turun drastis saat producer tidak mengirim data, namun latensi kembali sub-mikrodetik seketika data mulai dialirkan.

### Level Medium: Lock-Free Stack dengan Tagged Pointer
* **Tugas:** Implementasikan struktur data LIFO (*Treiber Stack*) Lock-Free berbasis *Compare-And-Swap* (`std::atomic::compare_exchange_weak`). 
* **Syarat:** Buat skenario reproduksi *ABA Problem*, lalu atasi kerentanan tersebut dengan mengintegrasikan struktur data tagged pointer (`struct TaggedPointer { Node* ptr; uint64_t tag; }`) menggunakan instruksi CAS 128-bit (`CMPXCHG16B` pada x86-64 / C++ `std::atomic<TaggedPointer>`).
* **Kriteria Sukses:** ThreadSanitizer tidak melaporkan peringatan *Data Race* atau *Heap Corruption* ketika dijalankan serentak oleh minimal 8 thread yang saling melakukan push dan pop.

### Level Hard: Multi-Producer Multi-Consumer (MPMC) Bounded Queue
* **Tugas:** Rancang dan bangun *Bounded MPMC Queue* berbasis array sirkular yang aman diakses oleh banyak producer dan banyak consumer tanpa menggunakan mutex tunggal.
* **Arsitektur:** Terapkan teknik algoritma Dmitry Vyukov (D.Vyukov MPMC):
  * Setiap slot di dalam array memiliki nomor sekuens atomik (`std::atomic<size_t> sequence`).
  * Producer bersaing memperebutkan tiket slot menggunakan atomic `fetch_add` pada posisi tail.
  * Consumer bersaing memperebutkan tiket slot menggunakan atomic `fetch_add` pada posisi head.
* **Kriteria Sukses:** Mencapai throughput di atas 5.000.000 ops/detik dalam pengujian konkurensi 4 producer threads dan 4 consumer threads.

---

## 14. Challenge

### Studi Kasus Produksi: Real-Time Tick-Data Aggregator dengan Zero-Allocation dan Zero-Copy

#### Deskripsi Masalah
Sebuah platform broker analitik pasar modal menerima data *tick feeds* (level-1 quotes) dari 4 bursa saham global yang berbeda secara paralel. Setiap bursa memompa paket data mentah melalui interface socket UDP multicast dengan volume puncak mencapai **15.000.000 pesan per detik** (rata-rata ukuran payload 128 byte). 

#### Batasan Arsitektur & Kendala Sistem
1. **Zero Heap Allocation:** Sistem dilarang memanggil `malloc`, `free`, `new`, atau `delete` selama proses feed runtime aktif berjalan. Seluruh memori penampung harus dipetakan sejak awal (*bootstrap phase*).
2. **Kekebalan Overwrite vs Drop:** Jika pipeline analitik di hilir (*downstream consumer*) mengalami perlambatan, pipeline penerimaan UDP tidak boleh memicu buffer bloat atau socket kernel drop. Anda harus memilih strategi: *Overwrite Oldest* (Lossy Ring Buffer) atau *Backpressure Signaling*.
3. **Penyimpanan Multi-Tier Cache-Aware:** Data harus tersedia untuk konsumsi real-time analitik (Core CPU 1-4) dan secara simultan ditulis ke dalam storage engine persisten berbasis disk via API asynchronous Linux `io_uring` tanpa mengganggu thread penerima jaringan utama.

#### Tugas Rekayasa
Rancang dokumen arsitektur komprehensif dan cetak biru implementasi (*skeleton C++*) yang mencakup:
* Tata letak struktur memori fisik *shared memory ring buffer* lengkap dengan pemetaan segmentasi cache line.
* Penggunaan model memori atomik pada setiap gerbang transisi data.
* Desain thread pinout ke core prosesor fisik (NUMA domain consideration).
* Mekanisme sinkronisasi data antar-thread tanpa *deadlock* dan tanpa OS context switch.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)

1. **Berapa ukuran umum dari satu *Cache Line* pada mikroprosesor modern x86-64 dan ARM64?**
   * A. 16 Byte
   * B. 32 Byte
   * C. 64 Byte
   * D. 128 Byte

2. **Perilaku *False Sharing* terjadi ketika...**
   * A. Dua thread mencoba mengunci mutex yang sama pada waktu bersamaan.
   * B. Dua thread memodifikasi variabel berbeda yang secara kebetulan berada dalam cache line 64-byte yang sama.
   * C. Dua thread membaca data dari soket memori fisik (NUMA) yang berjauhan.
   * D. CPU gagal mengeksekusi instruksi atomik karena saturasi DRAM.

3. **Operasi memori atomik dengan ordering `std::memory_order_relaxed` menjamin...**
   * A. Sinkronisasi urutan instruksi di seluruh core CPU.
   * B. Data aman dari context-switch sistem operasi.
   * C. Hanya keterjagaan atomisitas operasi lokal variabel tersebut tanpa jaminan urutan eksekusi memori lain.
   * D. Variabel langsung ditulis ke hard drive secara synchron.

4. **Dalam protokol MESI, status apakah yang menunjukkan bahwa salinan data di dalam cache telah dimodifikasi dan berbeda dengan yang ada di DRAM?**
   * A. Shared (S)
   * B. Exclusive (E)
   * C. Invalid (I)
   * D. Modified (M)

5. **Apa fungsi mendasar dari instruksi intrinsik `__builtin_ia32_pause()` atau assembly `PAUSE` pada core CPU x86 saat berada di dalam tight spinloop?**
   * A. Mematikan CPU core untuk menghemat energi secara total.
   * B. Menghindari terjadinya *memory order violation* dan mengurangi penalti *pipeline stalls* saat keluar dari loop.
   * C. Memaksa sistem operasi melakukan pergantian context switch thread.
   * D. Menghapus seluruh isi cache L1.

---

### Bagian 2: Intermediate (5 Pertanyaan)

6. **Mengapa pada arsitektur perangkat keras x86-64 (TSO), instruksi `memory_order_acquire` dan `memory_order_release` biasanya tidak menghasilkan assembly fence tambahan (seperti `mfence`) pada operasi load dan store standar?**
   * A. Karena CPU x86-64 sudah menjamin secara perangkat keras bahwa Store-Store dan Load-Load tidak pernah di-reorder.
   * B. Karena compiler mengabaikan instruksi tersebut pada sistem Linux.
   * C. Karena seluruh core x86 berbagi satu unit L1 Cache yang sama.
   * D. Karena instruksi tersebut otomatis ditangani oleh sistem operasi kernel secara asinkron.

7. **Pada kasus implementasi SPSC (Single Producer Single Consumer) Ring Buffer, mengapa kapasitas buffer paling optimal dirancang menggunakan angka berbasis kuadrat 2 (*power-of-two*)?**
   * A. Agar kapasitas muat tepat di dalam satu blok RAM DRAM.
   * B. Memungkinkan operasi modulo indeks pembagian `(i % N)` diganti menjadi operasi logika bitwise `(i & (N - 1))` yang membutuhkan biaya komputasi jauh lebih rendah.
   * C. Menghindari batasan jumlah thread pada platform 64-bit.
   * D. Mencegah terjadinya fenomena *integer overflow* pada penunjuk head dan tail.

8. **Masalah apa yang dipecahkan oleh penggunaan *Hazard Pointers* atau *Epoch-Based Reclamation* pada struktur data lock-free?**
   * A. Masalah penguncian resource hardware yang terbengkalai (*deadlock*).
   * B. Masalah dereferensi memori tak valid (*Use-After-Free*) saat menghapus node yang mungkin masih dibaca oleh thread lain.
   * C. Keterbatasan kapasitas penyimpanan pada shared memory.
   * D. Masalah lambatnya eksekusi instruksi pembagian bitwise.

9. **Jika Core A memegang cache line berstatus *Exclusive (E)* dan Core B mencoba membaca cache line yang sama melalui interconnect bus, status cache line pada Core A akan berubah menjadi...**
   * A. Modified (M)
   * B. Invalid (I)
   * C. Shared (S)
   * D. Tetap Exclusive (E)

10. **Apa perbedaan fungsional antara `compare_exchange_weak` dan `compare_exchange_strong` pada C++ standard library?**
    * A. `compare_exchange_weak` dapat gagal secara semu (*spurious failure*) meski nilainya sama, namun lebih efisien di dalam loop pada arsitektur tertentu (seperti ARM LL/SC).
    * B. `compare_exchange_strong` tidak dapat mendeteksi memory corruption.
    * C. `compare_exchange_weak` tidak mendukung semantik memory ordering.
    * D. `compare_exchange_strong` mengunci seluruh bus memori motherboard selama 1 milidetik.

---

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario:** Anda mengamati bahwa microservice pencocokan order berbasis SPSC queue mengalami penurunan performa drastis setiap kali dipindahkan dari lingkungan virtualisasi lokal (KVM) ke Bare-Metal Server 128 Core Dual-Socket (NUMA). Profiling menunjukkan metrik interconnect bus (*QPI/UPI Links*) mengalami saturasi 95%.
    * **Pertanyaan:** Apa penyebab paling mendasar dari fenomena ini dan tindakan rekayasa apa yang harus dieksekusi?
    * A. Terjadi thread preemption oleh OS; solusinya adalah menaikkan priority thread via `nice -20`.
    * B. Thread Producer berjalan pada Node Socket NUMA 0 sementara Consumer berjalan pada Node Socket NUMA 1, menyebabkan transfer cache line melintasi interconnect fisik antar-socket; solusinya adalah melakukan NUMA core binding (`numactl --cpunodebind`).
    * C. Memory RAM fisik mengalami degradasi kecepatan; solusinya adalah mengganti modul memori dari DDR4 ke DDR5.
    * D. Ukuran queue terlalu besar sehingga meluap keluar dari L3 cache; solusinya adalah mengecilkan kapasitas queue ke 16 elemen.

12. **Skenario:** Tim backend Anda melaporkan bahwa sebuah aplikasi web service multithreaded dengan throughput sangat tinggi secara misterius mengalami crash *Segmentation Fault* setiap 3 minggu sekali pada mesin Linux ARM64 AWS Graviton. Unit test selalu lulus 100% pada laptop MacBook M-series atau laptop x86 Intel. Audit awal menemukan penggunaan struktur data *Lock-Free Treiber Stack* tanpa garbage collection.
    * **Pertanyaan:** Kemungkinan anomali terbesar yang terjadi pada level instruksi mesin adalah...
    * A. Arsitektur ARM64 tidak mendukung operasi pointer 64-bit secara penuh.
    * B. Terjadi fenomena ABA Problem di mana pointer node yang telah dibebaskan dialokasikan kembali dan di-dereferensi oleh thread lain yang mengalami interupsi panjang.
    * C. Terjadi overheating pada core prosesor Graviton yang memicu bit-flip pada register memori.
    * D. Compiler secara salah mengompilasi instruksi `relaxed` atomics menjadi instruksi terkunci (`mutex lock`).

13. **Skenario:** Sebuah gateway jaringan memproses packet logging dengan menulis ke file log lokal. Developer membuat sistem logging di mana 16 thread worker memasukkan string log ke dalam sebuah `std::queue<std::string>` global yang dilindungi oleh sebuah `std::mutex`. Latensi HTTP request endpoint melonjak tinggi dan tidak stabil (*unpredictable jitter*).
    * **Pertanyaan:** Desain refactoring arsitektur manakah yang paling tepat untuk mengeliminasi jitter ini secara tuntas?
    * A. Mengganti `std::mutex` dengan `std::shared_mutex` (Read-Write Lock) untuk semua operasi enqueue.
    * B. Mengalokasikan 16 SPSC Lock-Free Ring Buffer independen (satu untuk setiap worker thread) dan satu thread dedicated Background Disk Writer yang melakukan drain secara sequensial ke file log via batch direct I/O.
    * C. Menaikkan batas ukuran file descriptor OS via `ulimit -n 65535`.
    * D. Membungkus operasi push ke dalam block asynchronous `std::async(std::launch::async, ...)`.

---

### Kunci Jawaban Quiz

#### Bagian 1: Basic
1. **C** — Standar ukuran cache line prosesor komputasi modern (Intel, AMD, ARM Neoverse) adalah 64 byte.
2. **B** — False sharing terjadi ketika dua core memodifikasi data independen yang tinggal di cache line fisik yang sama.
3. **C** — `relaxed` hanya memastikan keterjagaan sifat atomik pembacaan/penulisan variabel itu sendiri tanpa efek sinkronisasi instruksi lain.
4. **D** — Status *Modified* pada MESI merepresentasikan cache line yang dirty dan eksklusif di core tersebut.
5. **B** — Instruksi `PAUSE` memberikan sinyal ke pipeline prosesor untuk menunda instruksi berikutnya guna mencegah penalti memory order violation.

#### Bagian 2: Intermediate
6. **A** — x86 mengadopsi model Total Store Order (TSO) yang secara perangkat keras melarang reordering antar-Store atau antar-Load.
7. **B** — Operasi bitwise AND jauh lebih murah secara siklus clock CPU (~1 cycle) dibanding instruksi integer division / modulo IDIV (~10-40 cycles).
8. **B** — Hazard pointers dan Epoch-based reclamation memastikan memori tidak dibebaskan selama masih ada thread yang menyimpan pointer lokal ke memori tersebut.
9. **C** — Transisi protokol MESI dari *Exclusive* ke *Shared* terjadi saat core lain meminta pembacaan (*bus read*) terhadap line data yang sama.
10. **A** — `weak` diizinkan gagal semu pada arsitektur load-linked/store-conditional (seperti ARM), sehingga performanya lebih optimal saat digunakan dalam loop berulang.

#### Bagian 3: Skenario Kasus Produksi
11. **B** — Akses memori lintas NUMA node memaksa data melewati QPI/UPI link yang lambat dibanding L3 internal. Mengunci thread ke core pada socket yang sama via thread/numa affinity adalah solusi mutlak.
12. **B** — ABA problem pada linked list lock-free yang tidak memproteksi siklus hidup alokasi pointer (misalnya tanpa Tagged Pointer atau EBR) menyebabkan akses ke alamat memori yang telah di-free (*dangling pointer dereference*).
13. **B** — Mencegah perkelahian lock antar 16 worker dengan memberikan struktur data SPSC terisolasi per-worker, memindahkan proses I/O lambat ke background thread tunggal (*Batching I/O*).

---

## 16. Summary

1. **Mechanical Sympathy:** Menulis kode berkinerja tinggi pada tingkat enterprise menuntut pemahaman terhadap batasan fisik perangkat keras: *Cache Lines*, *Store Buffers*, dan protokol *Cache Coherency (MESI)*.
2. **Biaya Sinkronisasi Klasik:** Mutex dan Primitive OS Blocking memicu intervensi kernel, alokasi konteks, serta invalidasi L1/L2 cache yang menghabiskan ribuan siklus CPU dan merusak prediktabilitas latensi (*jitter spikes*).
3. **Kekuatan Lock-Free:** Melalui penerapan model memori *Acquire-Release*, algoritma bebas kunci mampu menjamin progres eksekusi sistemik di tingkat *user-space* murni dengan latensi deterministik di rentang puluhan nanodetik.
4. **Disiplin Akses Memori:** Optimasi konkurensi tidak bermakna tanpa pencegahan terhadap **False Sharing** (via cache line padding `alignas(64)`), **ABA Problem** (via Hazard Pointers / EBR), dan saturasi **NUMA Interconnect**. Arsitektur ring buffer modern yang pre-allocated dan contiguous adalah fondasi performa sistem real-time masa kini.