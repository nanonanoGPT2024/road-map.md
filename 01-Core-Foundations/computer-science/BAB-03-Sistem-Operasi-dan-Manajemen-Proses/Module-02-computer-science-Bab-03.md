# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 01-Core-Foundations | **Topik:** Computer Science | **Bab:** BAB-03-Materi-Lanjutan

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Menganalisis dan Memitigasi Bottleneck Hardware-Software Boundary**: Mendiagnosis degradasi performa akibat *cache misses*, *false sharing*, dan *context switching overhead* pada tingkat CPU microarchitecture dan OS kernel.
2. **Merancang Struktur Data Lock-Free & Cache-Conscious**: Mengimplementasikan struktur data konkuren tingkat lanjut (seperti Single-Producer Single-Consumer/SPSC Ring Buffer) dengan explicit memory barriers/atomics dan cache-line padding.
3. **Menerapkan Paradigma I/O Berperforma Tinggi**: Memahami dan mengimplementasikan mekanisme asynchronous event loop berbasis OS primitives (`epoll`, `kqueue`, `io_uring`) dan konsep dasar *Zero-Copy* serta *Kernel-Bypass networking*.
4. **Mengevaluasi Trade-off Arsitektur Sistem**: Menyeimbangkan antara latensi p99/p99.9, kompleksitas kode, utilisasi resource CPU/Memory, dan keandalan sistem pada skala jutaan operasi per detik (*high-throughput, ultra-low latency*).

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
* Konsep dasar arsitektur komputer (Von Neumann architecture, register, memory hierarchy: L1/L2/L3 cache, RAM).
* Pemrograman sistem dasar (C, C++, atau Rust: pointer arithmetic, dynamic memory allocation, threading via POSIX threads/std::thread).
* Dasar-dasar sistem operasi: Process vs Thread, Virtual Memory, Paging, System Calls (`read`, `write`, `fork`), dan interrupt handling.
* Primitif sinkronisasi dasar: Mutex, Semaphore, Condition Variable, serta masalah konkurensi (Race Condition, Deadlock).

---

## 3. Concept & Internal Architecture

Dalam rekayasa sistem terdistribusi dan sistem berbasis *ultra-low latency*, abstraksi perangkat keras yang disediakan oleh compiler dan sistem operasi tidak lagi sepenuhnya transparan. Untuk mengekstrak performa maksimal, *software architecture* harus dirancang selaras dengan *hardware topology* (*hardware-software co-design*).

### 3.1 Hierarki Memori, Cache Lines, dan Cache Coherency (Protokol MESI)
CPU modern tidak membaca memori per bita atau per kata, melainkan dalam blok berukuran tetap yang disebut **Cache Line** (umumnya 64 byte pada x86-64 dan ARM64).

```
+-------------------------------------------------------------------+
|                        CPU Core 0 (L1/L2)                         |
|  [Cache Line: Core 0 Modified (M)] -> Memegang pointer Head       |
+-------------------------------------------------------------------+
                                  | Interconnect Bus (Snooping/QPI)
+-------------------------------------------------------------------+
|                        CPU Core 1 (L1/L2)                         |
|  [Cache Line: Core 1 Invalid (I)]  -> Ingin membaca pointer Tail  |
+-------------------------------------------------------------------+
```

1. **Prinsip Lokalitas**:
   * *Temporal Locality*: Data yang diakses saat ini kemungkinan besar akan diakses kembali dalam waktu dekat.
   * *Spatial Locality*: Data yang berada dekat secara fisik di memori dengan data yang sedang diakses kemungkinan besar akan segera diakses.
2. **Protokol MESI (Modified, Exclusive, Shared, Invalid)**:
   * Setiap cache line diberi label status. Jika Core 0 menulis ke variabel yang berada pada satu cache line bersama dengan variabel yang dibaca Core 1, sinyal *bus invalidation* dipancarkan. Hal ini memicu fenomena **False Sharing**: dua core saling menganulir cache line satu sama lain meskipun memodifikasi variabel logis yang berbeda, mengakibatkan degradasi performa drastis akibat *cache line bouncing*.

### 3.2 Model Memori Hardware & Compiler (Memory Ordering)
CPU modern mengeksekusi instruksi secara *Out-of-Order* (OoO) dan compiler melakukan optimasi agresif yang dapat mengubah urutan instruksi program (*Instruction Reordering*).
* **Sequential Consistency (SC)**: Urutan eksekusi persis sama dengan urutan kode sumber. Model ini paling intuitif namun paling lambat karena mematikan optimasi hardware pipelining.
* **Relaxed Memory Models (Acquire-Release)**:
  * **Acquire semantics** (`std::memory_order_acquire`): Mencegah pembacaan dan penulisan memori setelah operasi acquire di-*reorder* mendahului acquire tersebut.
  * **Release semantics** (`std::memory_order_release`): Mencegah pembacaan dan penulisan memori sebelum operasi release di-*reorder* melewati release tersebut.

### 3.3 Evolusi I/O: Blocking, Non-Blocking, Event-Driven, hingga io_uring
Interaksi standar I/O melalui *system call* tradisional (`read`/`write`) melibatkan pergantian konteks (*context switch*) dari User Space ke Kernel Space, serta penyalinan data berganda (*multiple copies*):

1. **System Call Overhead**: CPU beralih dari Ring 3 (User) ke Ring 0 (Kernel) via interrupt handler / `syscall` instruction, membersihkan TLB (*Translation Lookaside Buffer*) dan mencemari cache CPU.
2. **Reactive I/O (epoll/kqueue)**: Menghilangkan model *thread-per-connection*. Kernel memberitahu thread ketika sebuah File Descriptor (FD) siap dibaca/ditulis tanpa memblokir thread.
3. **True Asynchronous I/O (Linux `io_uring`)**: Menggunakan sepasang *circular ring buffers* (Submission Queue & Completion Queue) yang dibagi antara kernel dan user space (*shared memory*). Menghilangkan overhead system call untuk setiap event I/O, mendekati performa *Kernel-Bypass*.

---

## 4. Why & What

### Mengapa Pendekatan Tradisional Gagal di Skala Enterprise?
Pada beban transaksi ekstrem (misalnya sistem lelang iklan, payment gateway berkapasitas 500k TPS, atau order execution engine):
* **Mutex & Lock Contention**: Mutex memaksa thread tidur (*park*) via OS scheduler (`futex`). Operasi *sleep & wake up* membutuhkan waktu antara 1 hingga 5 mikrodetik—waktu yang fatal bagi sistem yang membutuhkan latensi sub-mikrodetik.
* **Overhead Garbage Collection (GC)**: Pada bahasa managed (Java, Go, C#), alokasi memori berlebih memicu siklus GC yang menciptakan *stop-the-world pauses*. Arsitektur berorientasi produksi harus mengontrol *mechanical sympathy* dengan menghindari alokasi dinamis pada jalur data kritis (*hot path*).

### Apa Solusinya?
* Mengadopsi struktur data **Lock-Free** yang mengandalkan instruksi atomik CPU (seperti `CMPXCHG` / Compare-And-Swap).
* Mengorganisir memori menggunakan **Cache-Line Alignment** (`alignas(64)`) untuk mengeliminasi false sharing.
* Menggunakan **Zero-Copy** (seperti memory-mapped files `mmap`, `sendfile`, atau buffer pool berbasis arena).

---

## 5. How (Workflow Detail)

Alur eksekusi transfer data tanpa kunci (*Lock-Free Inter-Thread Communication*) via Ring Buffer:

```
[Producer Thread (Core A)]                           [Consumer Thread (Core B)]
         |                                                       |
 1. Cek Ruang Kosong                                             |
    (Read tail atomik, mem_order_relaxed)                        |
         |                                                       |
 2. Tulis Data Langsung ke Buffer Slot                           |
    (Tanpa lock; slot terisolasi secara memori)                  |
         |                                                       |
 3. Commit Head Counter                                          |
    (Write head atomik, mem_order_release)                      |
         | -------- [Memory Bus Synchronization] --------------->|
                                                                 |
                                                     4. Deteksi Ada Data Baru
                                                        (Read head atomik, mem_order_acquire)
                                                                 |
                                                     5. Baca Data dari Buffer Slot
                                                                 |
                                                     6. Commit Tail Counter
                                                        (Write tail atomik, mem_order_release)
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Meja Putar Restoran vs. Pintu Tunggal Berpenjaga
* **Sistem Locking Berbasis Mutex**: Seperti kamar pas belanja dengan satu kunci fisik. Siapa pun yang ingin masuk harus meminta kunci, mengunci pintu, menggunakannya, keluar, dan mengembalikan kunci. Jika antrean panjang, pelanggan tertidur di kursi tunggu (context switch overhead).
* **Lock-Free Cache-Padded Ring Buffer**: Seperti meja putar hidangan di restoran. Koki (Producer) meletakkan piring di slot bernomor ganjil, penikmat hidangan (Consumer) mengambil dari slot tersebut. Keduanya tidak pernah menyentuh slot yang sama pada waktu bersamaan. Meja diberi jarak fisik selebar 64 cm (Cache-line padding) sehingga tangan koki tidak pernah sengaja menyenggol siku konsumen (menghindari False Sharing).

### Diagram: False Sharing vs. Explicit Cache Line Padding

```
KONDISI 1: FALSE SHARING (BURUK)
Satu Cache Line 64 Byte menampung Head dan Tail bersamaan:
+---------------------------------------------------------------+
| Byte 0..7: Head (Core 0) | Byte 8..15: Tail (Core 1) | Unused |
+---------------------------------------------------------------+
       ^                               ^
       |                               |
Core 0 menulis Head            Core 1 menulis Tail
[Core 0 membatalkan cache Core 1] <---> [Core 1 membatalkan cache Core 0]
(Hasil: Bus Contention masif, throughput anjlok hingga 80-90%)

-----------------------------------------------------------------

KONDISI 2: CACHE-LINE ISOLATION DENGAN PADDING (OPTIMAL)
Cache Line 0 (64 Byte):
+---------------------------------------------------------------+
| Byte 0..7: Head          | Byte 8..63: PADDING (56 Byte)      |
+---------------------------------------------------------------+
       ^
       | Core 0 memodifikasi Cache Line miliknya sendiri secara eksklusif.

Cache Line 1 (64 Byte):
+---------------------------------------------------------------+
| Byte 0..7: Tail          | Byte 8..63: PADDING (56 Byte)      |
+---------------------------------------------------------------+
       ^
       | Core 1 memodifikasi Cache Line miliknya sendiri secara eksklusif.
(Hasil: Zero cache bouncing, near-linear scale execution)
```

---

## 7. Simple Example & Practical Example

### Practical Example: Production-Grade Lock-Free Single-Producer Single-Consumer (SPSC) Ring Buffer (C++20)

Kode ini mengimplementasikan SPSC Queue berbasis array melingkar statis, menggunakan `std::atomic` dengan *Acquire-Release semantics*, serta `alignas(64)` untuk mencegah *false sharing*.

```cpp
#include <iostream>
#include <atomic>
#include <vector>
#include <optional>
#include <thread>
#include <chrono>
#include <cassert>

constexpr size_t HARDWARE_DESTRUCTIVE_INTERFERENCE_SIZE = 64; // Standard Cache Line size

template <typename T, size_t Capacity>
class LockFreeSPSCQueue {
    static_assert((Capacity & (Capacity - 1)) == 0, "Capacity harus merupakan nilai power of 2");

public:
    LockFreeSPSCQueue() : head_(0), tail_(0) {}

    ~LockFreeSPSCQueue() = default;

    // Produser: Menambahkan elemen ke dalam queue
    bool push(const T& item) {
        const size_t current_head = head_.load(std::memory_order_relaxed);
        const size_t current_tail = tail_.load(std::memory_order_acquire);

        // Periksa kapasitas (Ring Buffer penuh jika jaraknya sama dengan Capacity)
        if ((current_head - current_tail) >= Capacity) {
            return false; // Queue Penuh
        }

        buffer_[current_head & BUFFER_MASK] = item;

        // Release: Menjamin penulisan buffer selesai sebelum head diperbarui
        head_.store(current_head + 1, std::memory_order_release);
        return true;
    }

    // Konsumen: Mengambil elemen dari dalam queue
    std::optional<T> pop() {
        const size_t current_tail = tail_.load(std::memory_order_relaxed);
        const size_t current_head = head_.load(std::memory_order_acquire);

        // Periksa apakah antrean kosong
        if (current_tail == current_head) {
            return std::nullopt; // Queue Kosong
        }

        T item = buffer_[current_tail & BUFFER_MASK];

        // Release: Menjamin pembacaan buffer selesai sebelum tail diperbarui
        tail_.store(current_tail + 1, std::memory_order_release);
        return item;
    }

    [[nodiscard]] size_t size() const noexcept {
        const size_t current_tail = tail_.load(std::memory_order_relaxed);
        const size_t current_head = head_.load(std::memory_order_relaxed);
        return (current_head >= current_tail) ? (current_head - current_tail) : 0;
    }

private:
    static constexpr size_t BUFFER_MASK = Capacity - 1;

    // Buffer penyimpanan data
    T buffer_[Capacity];

    // Isolasi Head pada Cache Line tersendiri
    alignas(HARDWARE_DESTRUCTIVE_INTERFERENCE_SIZE) std::atomic<size_t> head_;

    // Isolasi Tail pada Cache Line tersendiri guna mencegah False Sharing
    alignas(HARDWARE_DESTRUCTIVE_INTERFERENCE_SIZE) std::atomic<size_t> tail_;
};

int main() {
    constexpr size_t QUEUE_CAPACITY = 1024; // Harus 2^n
    constexpr size_t TOTAL_MESSAGES = 10'000'000;

    auto queue = std::make_unique<LockFreeSPSCQueue<uint64_t, QUEUE_CAPACITY>>();

    auto start_time = std::chrono::high_resolution_clock::now();

    // Producer Thread
    std::thread producer([&]() {
        for (uint64_t i = 1; i <= TOTAL_MESSAGES; ++i) {
            while (!queue->push(i)) {
                // Polling aktif (spin-wait) untuk meminimalkan latensi
                #if defined(__x86_64__) || defined(_M_X64)
                __builtin_ia32_pause();
                #endif
            }
        }
    });

    // Consumer Thread
    std::thread consumer([&]() {
        uint64_t received_count = 0;
        while (received_count < TOTAL_MESSAGES) {
            auto item = queue->pop();
            if (item.has_value()) {
                received_count++;
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
    std::chrono::duration<double> elapsed = end_time - start_time;

    std::cout << "Selesai memproses " << TOTAL_MESSAGES << " pesan dalam: " 
              << elapsed.count() << " detik.\n";
    std::cout << "Throughput: " << (TOTAL_MESSAGES / elapsed.count()) / 1'000'000.0 
              << " Juta pesan/detik (MOps/sec)\n";

    return 0;
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Ultra-Low Latency Matching Engine pada Bursa Keuangan (Tier-1 Financial Exchange)

* **Skala & Kebutuhan**:
  * Volume: 50.000 order/detik saat normal, lonjakan (burst) hingga 2.000.000 order/detik saat rilis berita ekonomi.
  * Target SLA Latensi: P99.9 < 15 mikrodetik; max jitter < 50 mikrodetik.
  * Kehilangan data = zero tolerance (ACID streaming audit trail).

* **Arsitektur Awal (Legacy Architecture)**:
  * Menggunakan thread pool berbasis Java dengan messaging via Kafka, disinkronkan dengan standard `ReentrantLock`.
  * *Hasil*: Pada saat burst, garbage collector memicu pause sebesar 12 milidetik (800x toleransi batas SLA), dan thread contention pada shared queue memicu 40% CPU spend hanya untuk OS context switches.

* **Desain Solusi Tingkat Lanjut (Target State Architecture)**:
  1. **Thread Affinitization (Core Pinning)**: Memetakan critical thread (Network ingress, Matching engine, Journaling) ke CPU core tertentu secara statis menggunakan `pthread_setaffinity_np` untuk mencegah *L1/L2 cache evictions*.
  2. **Disruptor / SPSC Ring Buffer Matrix**: Mengganti lock-based queue dengan matriks lock-free SPSC circular ring buffers.
  3. **Kernel Bypass Networking**: Mengganti socket TCP konvensional dengan *Solarflare OpenOnload* atau *DPDK (Data Plane Development Kit)*, memindahkan packet processing langsung dari Network Interface Card (NIC) ke User Space memory via DMA (*Direct Memory Access*).

* **Dampak Bisnis & Teknis**:
  * P99 latensi terpangkas dari 14.2 milidetik ke **3.8 mikrodetik**.
  * Throughput naik 12x lipat pada footprint hardware yang sama (penurunan kebutuhan server dari 32 bare-metal nodes menjadi 4 high-spec bare-metal nodes).
  * Penghematan biaya infrastruktur (TCO) mencapai $1.8 Juta USD per tahun.

---

## 9. Trade-offs

| Parameter Arsitektur | Lock-Based (Tradisional) | Lock-Free / Low-Level Atomics | Kernel Bypass (DPDK/io_uring) |
| :--- | :--- | :--- | :--- |
| **Throughput** | Rendah - Sedang (terhambat contention) | Sangat Tinggi (jutaan ops/sec) | Ekstrem (saturasi hardware line-rate) |
| **Latensi (p99/p99.9)** | Fluktuatif (jitter tinggi akibat sleep/wake) | Sangat stabil (sub-mikrodetik) | Deterministik murni (< 1 mikrodetik) |
| **Utilisasi CPU saat Idle** | 0% (Thread tertidur via OS wait) | Dapat mencapai 100% jika busy-spinning | 100% (Polled-Mode Driver terus berputar) |
| **Kompleksitas Kode** | Rendah (mudah dipahami dan diuji) | Ekstrem (rawan ABA problem, memory reordering bugs) | Sangat Tinggi (harus mengelola hardware langsung) |
| **Biaya Pemeliharaan & Debugging** | Standar (stack trace jelas saat hang) | Berat (perlu hardware tracer, sanitizer khusus) | Sangat Berat (memerlukan engineer spesialis OS kernel) |

---

## 10. Common Mistakes & Troubleshooting

### 1. The ABA Problem pada Desain Lock-Free
* **Gejala**: Thread 1 membaca nilai $A$. Thread 2 mengubah $A \to B \to A$. Thread 1 melakukan `Compare-And-Swap` (CAS), mengira data tidak pernah berubah padahal struktur referensinya telah berganti.
* **Solusi**: Gunakan tagged pointers (*double-word CAS*) yang menyertakan sequence versioning 64-bit pada pointer, atau gunakan pustaka hazard pointers / epoch-based memory reclamation.

### 2. Mengabaikan CPU Instruction Reordering
* **Gejala**: Program berfungsi normal pada arsitektur x86-64 (yang memiliki model *Strong Memory Ordering* secara hardware), tetapi crash atau membaca data korup saat di-deploy ke arsitektur ARM64 / Apple Silicon (yang bertipe *Weakly-Ordered Memory*).
* **Solusi**: Selalu spesifikasikan `std::memory_order` secara eksplisit alih-alih mengandalkan `memory_order_seq_cst` default secara implisit atau menganggap relax access selalu aman.

### 3. Busy Spinning Membakar CPU Tanpa Instruksi PAUSE
* **Gejala**: Core CPU mencapai 100%, sistem menghasilkan panas tinggi dan memicu CPU thermal throttling, menurunkan core frequency.
* **Troubleshooting / Solusi**: Letakkan instruksi assembly CPU pause (`__builtin_ia32_pause()` atau asm `yield`) di dalam tight spin loop. Ini memberi tahu pipeline prosesor bahwa loop tersebut adalah spin-wait, mencegah pipeline clears dan menghemat daya.

### Diagnosis Menggunakan Perangkat Standar Industri:
```bash
# Pantau L1-dcache-load-misses dan L1-dcache-loads
perf stat -e L1-dcache-loads,L1-dcache-load-misses,cache-misses ./engine_binary

# Deteksi False Sharing pada binary yang sedang berjalan
perf c2c record ./engine_binary
perf c2c report --stdio
```

---

## 11. Best Practices (Production Checklist)

- [ ] **Alokasi Memori Statis (Hot Path Zero-Allocation)**: Tidak ada alokasi memori dinamis (`malloc`, `new`, atau resizing container) pada alur transaksi aktif. Semua memori harus di-*pre-allocate* saat proses startup (*cold path*).
- [ ] **Data Alignment Validated**: Semua variabel sinkronisasi antar-thread yang rentan ditulis bersamaan diberi anotasi `alignas(64)` guna mengunci variabel pada batas cache line unik.
- [ ] **Cache Topology Aware**: Pastikan ukuran ring buffer memiliki panjang $2^n$ sehingga modulasi indeks digantikan oleh bitwise AND (`index & (size - 1)`).
- [ ] **Affinity & Isolation**: Isolasi core pemrosesan utama dari Linux scheduler menggunakan kernel boot parameter `isolcpus=<list>` dan sematkan process thread via `pthread_set_affinity`.
- [ ] **Disable Dynamic Frequency Scaling**: Matikan CPU throttling (`cpufreq governor = performance`) untuk memastikan latensi instruksi konsisten tanpa fase ramp-up clock speed.

---

## 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

### File: `hands-on/m02/false_sharing_benchmark.cpp`
Praktikum pembuktian dampak false sharing secara empiris pada arsitektur multi-core.

```cpp
#include <iostream>
#include <thread>
#include <vector>
#include <chrono>

constexpr uint64_t ITERATIONS = 500'000'000;

// Skenario 1: Struktur dengan False Sharing
struct BadCounter {
    uint64_t value{0}; // Bersebelahan langsung di memori
};

// Skenario 2: Struktur dengan Cache-Line Padding
struct GoodCounter {
    alignas(64) uint64_t value{0}; // Dipisahkan sejauh 64 byte
};

template <typename T>
void run_benchmark(const std::string& label) {
    std::vector<T> counters(2);

    auto start = std::chrono::high_resolution_clock::now();

    std::thread t1([&]() {
        for (uint64_t i = 0; i < ITERATIONS; ++i) {
            counters[0].value++;
        }
    });

    std::thread t2([&]() {
        for (uint64_t i = 0; i < ITERATIONS; ++i) {
            counters[1].value++;
        }
    });

    t1.join();
    t2.join();

    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double, std::milli> ms = end - start;

    std::cout << "[" << label << "] Durasi Eksekusi: " 
              << ms.count() << " ms\n";
}

int main() {
    std::cout << "Menjalankan Pengujian Hardware Destructive Interference...\n";
    run_benchmark<BadCounter>("Dengan False Sharing (Non-Padded)");
    run_benchmark<GoodCounter>("Bebas False Sharing (Padded 64B)");
    return 0;
}
```

### Instruksi Kompilasi dan Eksekusi:
```bash
# 1. Masuk ke direktori
mkdir -p hands-on/m02 && cd hands-on/m02

# 2. Kompilasi dengan optimasi release
g++ -O3 -std=c++20 false_sharing_benchmark.cpp -lpthread -o fs_benchmark

# 3. Eksekusi pengujian
./fs_benchmark
```
*Ekspektasi Hasil*: Versi dengan padding umumnya selesai 2x hingga 6x lebih cepat dibanding versi non-padded tergantung arsitektur CPU Anda.

---

## 13. Exercise

### Level Easy
Modifikasi kelas `LockFreeSPSCQueue` pada Bagian 7 agar method `size()` mengembalikan estimasi ukuran antrean yang aman tanpa memicu deadlock, dan jelaskan mengapa data yang dikembalikan pada sistem konkuren selalu bersifat perkiraan (*point-in-time estimate*).

### Level Medium
Buat sebuah pool memori berbasis fixed-size arena (`ObjectPool`) berkapasitas 4096 item yang dapat mengalokasikan dan mendealokasikan buffer berukuran 512 byte tanpa pernah memanggil `malloc` atau `free` pada saat eksekusi berjalan. Pastikan pool tersebut aman digunakan oleh thread produser dan konsumen tanpa memicu heap fragmentation.

### Level Hard
Implementasikan skema ring buffer Multi-Producer Single-Consumer (MPSC). Anda harus menangani kontensi multi-producer menggunakan instruksi `atomic_compare_exchange_weak` pada index producer tail, sementara index consumer head tetap diproses oleh thread tunggal. Uji ketahanan implementasi terhadap bahaya data overwrite di bawah beban 8 producer thread secara simultan.

---

## 14. Challenge

Rancang arsitektur internal sebuah **In-Memory Streaming Log Broker** (serupa Kafka, namun murni in-memory dan hardware-conscious) yang harus mampu melayani transfer data sebesar **100 Juta event per detik** dengan ukuran payload rata-rata 128 byte pada sebuah server bare-metal berspesifikasi 16-Core CPU dan 64GB RAM.

**Batasan Masalah**:
1. Tidak diizinkan menggunakan mutex, spinlock, atau thread-sleep berbasis kernel synchronization.
2. Tidak boleh ada alokasi heap (`malloc`/`free`) setelah fase inisialisasi awal.
3. Desain harus meminimalkan *cache invalidation traffic* pada bus memori dan mengeliminasi proses *descheduling* thread.

**Tugas Anda**:
Tuliskan cetak biru desain teknis (*Architecture Blueprint*) yang mencakup layout memori data structure, penetapan core CPU (*core isolation topology*), alur kerja read/write path, serta analisis teoretis mengenai batas maksimum transfer memori (Memory Bandwidth Saturation) pada server tersebut.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Pertanyaan Basic (5 Soal)
1. Berapakah ukuran tipikal dari sebuah *Cache Line* pada arsitektur prosesor modern modern x86 dan ARM64?
2. Apa yang dimaksud dengan fenomena *False Sharing* dalam pemrograman sistem multi-core?
3. Mengapa operasi bitwise `index & (capacity - 1)` jauh lebih disukai daripada operasi modulo `index % capacity` pada ring buffer hot-path?
4. Apa perbedaan fundamental antara model `std::memory_order_relaxed` dan `std::memory_order_seq_cst`?
5. Mengapa pemanggilan *system call* (seperti standard POSIX I/O) memiliki penalti performa yang signifikan terhadap latensi?

### Bagian B: Pertanyaan Intermediate (5 Soal)
1. Jelaskan bagaimana protokol MESI menangani cache line saat salah satu core melakukan operasi penulisan pada alamat memori yang berstatus *Shared (S)*.
2. Bagaimana instruksi CPU `pause` (atau `yield` pada ARM) membantu mereduksi konsumsi daya dan mencegah memory pipeline stalls saat melakukan busy-spin polling?
3. Pada struktur antrean SPSC (Single-Producer Single-Consumer), mengapa kita tidak membutuhkan operasi CAS (`Compare-And-Swap`) dan cukup menggunakan atomic increment dengan *Acquire-Release semantics*?
4. Mengapa teknik *Thread Pinning* (*CPU Affinity*) efektif meningkatkan performa sistem berlatensi rendah? Apa dampak negatifnya terhadap penjadwalan OS secara umum?
5. Jelaskan mekanisme dasar Linux `io_uring` dalam mengeliminasi kebutuhan context switch antara user space dan kernel space saat memproses I/O masif.

### Bagian C: Skenario Kasus Produksi (3 Soal)
1. **Skenario 1**: Tim Anda memindahkan aplikasi matching engine berbasis C++ dari server Intel Xeon ke server AWS Graviton (ARM64). Tanpa ada perubahan kode, sistem mengalami race condition acak yang merusak data saldo rekening. Kode tersebut menggunakan `std::memory_order_relaxed` pada sejumlah flag status data. Apa akar masalah arsitekturalnya dan bagaimana perbaikan permanennya?
2. **Skenario 2**: Profiler sistem (`perf`) menunjukkan bahwa fungsi critical hot-path Anda memiliki tingkat `L1-dcache-load-misses` sebesar 45%. Struktur data Anda saat ini adalah `std::vector<Transaction*>` (Array of Pointers). Bagaimana Anda merekayasa ulang arsitektur memori ini untuk memangkas cache miss rate hingga di bawah 5%?
3. **Skenario 3**: Sebuah microservice gateway memproses koneksi WebSocket dari 100.000 user yang sebagian besar idle. Ketika diimplementasikan dengan paradigma *Thread-per-Connection*, server kehabisan memori (*Out-of-Memory*) dan CPU load melonjak drastis meskipun throughput pesan sangat rendah. Jelaskan analisis penyebab kegagalannya dari sudut pandang alokasi stack kernel, context switching, dan sebutkan arsitektur pengganti yang tepat.

---

## 16. Summary

1. **Hardware-Conscious Software Engineering**: Performa puncak pada komputasi enterprise tidak hanya ditentukan oleh notasi algoritma Big-O, melainkan oleh keselarasan antara instruksi perangkat lunak dengan topologi mikroarsitektur prosesor (*Mechanical Sympathy*).
2. **Eliminasi Overhead Cache**: Memahami ukuran cache line (64 byte) dan isolasi variabel lintas thread via padding adalah pembeda fundamental antara sistem dengan konkurensi buruk versus sistem berkemampuan konkurensi linear.
3. **Atomics over Locks**: Mengganti lock primitif dengan model *lock-free* berbasis atomic acquire-release semantics memangkas biaya context-switching OS secara drastis, mentransformasikan latensi dari milidetik menjadi sub-mikrodetik.
4. **I/O Modern**: Evolusi dari blocking system call ke event-driven (`epoll`) dan *shared-memory circular submission queues* (`io_uring`) memungkinkan arsitektur perangkat lunak memproses jutaan operasi I/O per detik tanpa membebani scheduler sistem operasi.