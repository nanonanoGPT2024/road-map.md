# Bab 07: Konkurensi Tingkat Tinggi, Model Memori C++, & Sistem Komputasi Bebas Kunci (Lock-Free)
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta mampu:
1. **Menganalisis** semantik model memori C++ (*Memory Orders*: `relaxed`, `consume`, `acquire`, `release`, `acq_rel`, `seq_cst`) hingga ke tingkat instruksi mesin (*assembly barriers* dan mikrarsitektur CPU).
2. **Mengidentifikasi dan Mencegah** anomali performa pada level silikon, khususnya *Cache Contention*, *False Sharing*, dan *Pipeline Stalls*, dengan memanfaatkan *cache line alignment* dan *hardware interference sizes*.
3. **Merancang dan Mengimplementasikan** struktur data bebas kunci (*lock-free*) dan bebas tunggu (*wait-free*) berstandar industri (misal: SPSC/MPSC Ring Buffer) yang deterministik dan *zero-allocation* pada jalur kritis (*hot-path*).
4. **Mengevaluasi** mitigasi *hazard memory deallocation* menggunakan teknik *Epoch-Based Reclamation* (EBR) dan *Hazard Pointers* untuk menyelesaikan masalah ABA tanpa *garbage collector*.
5. **Membangun** sistem konkurensi berbasis *pinned-thread*, *NUMA-aware*, dan *kernel-bypass architecture* untuk beban kerja *ultra-low latency* (HFT/FinTech, infrastruktur telekomunikasi, dan *game engine core*).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- **C++ Standar (C++17/C++20)**: Konsep *move semantics*, RAII, *templates*, dan *concepts*.
- **Dasar Primitif Konkurensi**: `std::thread`, `std::mutex`, `std::unique_lock`, dan `std::condition_variable`.
- **Mikroarsitektur Komputer Dasar**: Struktur hierarki *cache* (L1, L2, L3), siklus instruksi CPU, dan konsep *Virtual Memory*.
- **Tooling**: CMake (≥ 3.20), Clang/GCC modern yang mendukung C++20, GDB/LLDB, serta profil fundamental menggunakan `perf` atau Google Benchmark.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 C++ Memory Model & Hardware Realities

Bahasa C++ tidak lagi memandang komputer sebagai mesin sekuensial tunggal sejak revisi C++11. Standar C++ mendefinisikan *Abstract Machine* di mana operasi konkuren diatur oleh relasi **Happens-Before**, **Synchronizes-With**, dan **Carries-A-Dependency**.

Pada tingkat perangkat keras modern (x86-64, ARM64):
- **Compiler Reordering**: Pengompilasi menata ulang instruksi untuk memaksimalkan penggunaan *register* dan saturasi *instruction pipeline*.
- **Out-of-Order Execution (OoO)**: CPU mengeksekusi instruksi begitu operan tersedia, bukan berdasarkan urutan kode biner.
- **Store Buffers & Invalidate Queues**: Untuk menghindari *stall* saat menulis ke *cache* L1, inti prosesor (*core*) menulis data ke *Store Buffer* internal. Hal ini memicu fenomena *Store Buffering* (penulisan belum langsung terlihat oleh *core* lain).

```
[ CPU Core 0 ]                   [ CPU Core 1 ]
     │                                │
[ Store Buffer ]                 [ Store Buffer ]
     │                                │
[ L1 Data Cache ] <──MESI/MOESI──> [ L1 Data Cache ]
         └───[ L2 Cache ]     [ L2 Cache ]───┘
                    \         /
                   [ L3 Shared Cache ]
                            │
                      [ Main RAM ]
```

#### 3.2 Protokol Koherensi Cache (MESI/MOESI) & False Sharing

*Cache coherency hardware* menjaga konsistensi salinan data di seluruh *cache* privat CPU melalui protokol berbasis status:
- **M (Modified)**: Baris *cache* kotor, hanya ada di *cache* lokal, belum sinkron dengan RAM.
- **E (Exclusive)**: Baris *cache* bersih, hanya ada di *cache* lokal, sama dengan RAM.
- **S (Shared)**: Baris *cache* bersih, mungkin ada di beberapa *cache core* lain.
- **I (Invalid)**: Baris *cache* tidak valid (usang).

**False Sharing** terjadi ketika dua *thread* pada *core* yang berbeda memodifikasi dua variabel independen yang secara kebetulan berada dalam satu unit transfer memori yang sama (biasanya 64 bita, disebut **Cache Line**). 

Setiap kali Core 0 menulis ke Variabel A, seluruh baris *cache* milik Core 1 (yang memuat Variabel B) diubah statusnya menjadi **Invalid (I)** melalui bus memori (*cache invalidation traffic*). Core 1 terpaksa memuat ulang baris *cache* dari L3/RAM meskipun Variabel B tidak disentuh oleh Core 0.

#### 3.3 Relasi Sinkronisasi Memori (`std::memory_order`)

Operasi atomik C++ mengontrol penataan ulang instruksi oleh pengompilasi dan penyisipan instruksi pembatas (*memory barrier/fence*):

1. **`memory_order_relaxed`**:
   - Menjamin atomisitas (tidak ada data race parsial).
   - Tidak menjamin keterurutan (*no ordering constraints*). Operasi baca/tulis bebas ditata ulang melintasi titik ini.
2. **`memory_order_acquire`**:
   - Digunakan pada operasi pembacaan (*load*).
   - Menjamin bahwa semua operasi baca/tulis yang muncul **setelah** *acquire* dalam kode program tidak dapat ditata ulang **sebelum** operasi *acquire* ini.
3. **`memory_order_release`**:
   - Digunakan pada operasi penulisan (*store*).
   - Menjamin bahwa semua operasi baca/tulis yang muncul **sebelum** *release* dalam kode program tidak dapat ditata ulang **setelah** operasi *release* ini.
   - Pasangan *Release-Acquire* menciptakan relasi **Synchronizes-With**.
4. **`memory_order_seq_cst` (Sequential Consistency)**:
   - Standar bawaan. Memberikan jaminan *Acquire-Release* ditambah satu urutan eksekusi global tunggal (*single globally consistent order*) yang diamati oleh seluruh *core*.
   - Membutuhkan instruksi penahan bus (*bus locking* atau `MFENCE` pada x86) yang sangat mahal.

---

### 4. Why & What

| Dimensi | Pendekatan Berbasis Kunci (Lock-Based / `std::mutex`) | Pendekatan Bebas Kunci (Lock-Free / Atomic Engine) |
| :--- | :--- | :--- |
| **Prinsip Operasi** | Mutual Exclusion: Menghentikan eksekusi *thread* lain yang berkompetisi via OS Scheduler. | Optimistic Execution: Menggunakan instruksi CPU komparasi atomik (CAS) atau topologi antrean murni. |
| **Peluang Deadlock** | Tinggi, terutama pada penguncian berlapis (*nested locks*). | Secara teoritis mustahil jika dirancang tanpa *blocking primitives*. |
| **Jaminan Progres** | Tidak ada jaminan latensi; jika *thread* pemegang kunci mengalami *preemption*, sistem berhenti. | Menjamin minimal satu *thread* mengalami progres dalam rentang waktu terbatas (*system-wide progress*). |
| **Overhead OS Context Switch**| Signifikan (~1.000–10.000 siklus CPU per transisi *kernel-space* jika terjadi kontensi). | Nol transisi *kernel-space*; eksekusi tetap berada murni di *user-space*. |
| **Sensitivitas Terhadap Skala**| Degradasi drastis saat jumlah *thread* melebihi jumlah *core* fisik (kontensi tinggi). | Skalabilitas throughput tinggi jika *false sharing* dan kontensi CAS dieliminasi. |

Struktur data bebas kunci (**Lock-Free**) menjamin bahwa sistem secara keseluruhan terus membuat kemajuan (*system-wide progress*). Tingkatan yang lebih ketat adalah **Wait-Free**, di mana setiap operasi *thread* individu dijamin selesai dalam sejumlah langkah terhingga, apa pun perilaku *thread* lainnya.

---

### 5. How (Workflow Detail)

Untuk mengimplementasikan arsitektur konkurensi deterministik performa tinggi:

```
[Inisialisasi Producer/Consumer Thread]
                 │
                 ▼
[Konfigurasi Alinyemen Memori: alignas(hardware_destructive_interference_size)]
                 │
                 ▼
     ┌───────────────────────┐
     │ Producer Workflow     │
     └───────────────────────┘
                 │
  (1) Ambil Write Index Lokal
                 │
  (2) Evaluasi Kapasitas Antrean (Cek Read Index ter-koleksi dengan memory_order_relaxed)
                 │
      ├── Antrean Penuh? ───> [Backoff / Yield / Spin Strategis]
      │
      └── Ada Ruang Bebas?
                 │
  (3) Tulis Payload Objek ke Slot Penyangga (Non-Atomic Memory Write)
                 │
  (4) Majukan Write Index via std::atomic::store(..., memory_order_release)
                 │
                 ▼
     ┌───────────────────────┐
     │ Consumer Workflow     │
     └───────────────────────┘
                 │
  (1) Ambil Write Index Produsen via std::atomic::load(..., memory_order_acquire)
                 │
  (2) Evaluasi Ketersediaan Data (Bandingkan dengan Read Index Lokal)
                 │
      ├── Antrean Kosong? ──> [Backoff / Polling Cepat]
      │
      └── Data Tersedia?
                 │
  (3) Baca/Pindahkan Payload dari Slot Penyangga (Non-Atomic Memory Read)
                 │
  (4) Majukan Read Index via std::atomic::store(..., memory_order_release)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Meja Putar Gudang (Papan Putar Kanban)
Bayangkan dua operator gudang yang dibatasi dinding kaca tebal: **Operator P (Produsen)** dan **Operator C (Konsumen)**.
- Di antara mereka ada meja putar sirkular (*Ring Buffer*) berisi 8 nampan berlabel 0 hingga 7.
- Operator P memiliki bendera penunjuk angka: *Nampan terakhir yang terisi*.
- Operator C memiliki bendera penunjuk angka: *Nampan terakhir yang kosong*.

P tidak boleh meletakkan barang pada nampan jika nampan tersebut belum dikosongkan oleh C. P menulis barang secara fisik ke nampan, lalu mengubah nomor benderanya menggunakan sinyal tangan (*Release fence*). Operator C mengamati nomor bendera P (*Acquire fence*), mengambil barang, dan setelah nampan kosong, memperbarui nomor benderanya sendiri. Keduanya tidak pernah saling memegang tangan (bebas kunci).

```
               === Topologi Ring Buffer SPSC Modern ===

               Indeks Baca (Head)               Indeks Tulis (Tail)
               Diperbarui Konsumen              Diperbarui Produsen
                      │                                 │
                      ▼                                 ▼
               ┌─────────────┐                   ┌─────────────┐
               │ alignas(64) │                   │ alignas(64) │
               │ atomic<u64> │                   │ atomic<u64> │
               └─────────────┘                   └─────────────┘
                      │                                 │
                      │         Slot Memori Array       │
                      ▼    [0]   [1]   [2]   [3]   ...  ▼
              Buffer:   [Data][Data][Data][Empty] ... [Empty]
                        ▲                       ▲
                        │                       │
                  Read Pos (Consumer)     Write Pos (Producer)
              
   [Cache Line Core 0] <--- Jarak 64/128 Byte ---> [Cache Line Core 1]
   (Mencegah False Sharing / Invalidasi Jalur Bus L1 Antar-Core)
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Analisis Perbedaan `seq_cst` vs `acquire-release`

Contoh ini mendemonstrasikan bagaimana jaminan sinkronisasi data non-atomik ditegakkan menggunakan *Acquire-Release Semantics* tanpa memaksakan *Sequential Consistency*.

```cpp
#include <iostream>
#include <thread>
#include <atomic>
#include <cassert>
#include <string>

std::string shared_payload;
std::atomic<bool> ready_flag{false};

void producer_routine() {
    // 1. Tulis data non-atomik
    shared_payload = "ENGINE_TRANSACTION_PAYLOAD_HASH_0x7FFA";
    
    // 2. Publikasi data: semua penulisan sebelumnya harus selesai sebelum baris ini
    ready_flag.store(true, std::memory_order_release);
}

void consumer_routine() {
    // 3. Tunggu data dipublikasikan: pembacaan data di bawah tidak boleh ditata ulang mendahului load ini
    while (!ready_flag.load(std::memory_order_acquire)) {
        #if defined(__x86_64__) || defined(_M_X64)
        __builtin_ia32_pause(); // Mencegah CPU pipeline choke saat spinning
        #elif defined(__aarch64__)
        asm volatile("yield" ::: "memory");
        #endif
    }
    
    // 4. Terjamin aman membaca shared_payload tanpa data race
    assert(shared_payload == "ENGINE_TRANSACTION_PAYLOAD_HASH_0x7FFA");
    std::cout << "Data diverifikasi secara aman: " << shared_payload << '\n';
}

int main() {
    std::thread t1(producer_routine);
    std::thread t2(consumer_routine);
    t1.join();
    t2.join();
    return 0;
}
```

#### 7.2 Practical Example: Production-Grade SPSC Lock-Free Ring Buffer

Implementasi di bawah ini menggunakan konsep alinyemen instruksi modern C++20 (`std::hardware_destructive_interference_size`), alokasi penyangga statis/tetap tanpa alokasi dinamis pada *hot-path*, serta mitigasi *false sharing*.

```cpp
#include <iostream>
#include <atomic>
#include <new>
#include <cstddef>
#include <optional>
#include <array>
#include <thread>
#include <vector>
#include <chrono>

// Alinyemen Cache Line Standar Industri Modern (Fallback jika tidak didukung platform)
#ifdef __cpp_lib_hardware_interference_size
    using std::hardware_destructive_interference_size;
#else
    constexpr size_t hardware_destructive_interference_size = 64;
#endif

template <typename T, size_t Capacity>
class SPSCRingBuffer {
    static_assert((Capacity & (Capacity - 1)) == 0, "Capacity harus merupakan nilai perpangkatan dua (power of 2)!");
    static_assert(std::is_trivially_copyable_v<T>, "Payload wajib berkarakteristik trivially copyable!");

public:
    SPSCRingBuffer() : write_idx_(0), read_idx_(0) {}

    // Produsen: Mengembalikan false jika antrean penuh
    template <typename... Args>
    bool emplace(Args&&... args) noexcept {
        const size_t current_tail = write_idx_.load(std::memory_order_relaxed);
        
        // Optimasi: Gunakan cached read index lokal sebelum memuat atomic read_idx_
        if ((current_tail - cached_read_idx_) >= Capacity) {
            cached_read_idx_ = read_idx_.load(std::memory_order_acquire);
            if ((current_tail - cached_read_idx_) >= Capacity) {
                return false; // Penyangga penuh
            }
        }

        // Tulis elemen langsung ke lokasi buffer (in-place placement)
        new (&storage_[current_tail & BufferMask]) T(std::forward<Args>(args)...);

        // Publikasikan indeks tulis dengan semantik release
        write_idx_.store(current_tail + 1, std::memory_order_release);
        return true;
    }

    // Konsumen: Mengambil elemen dari buffer
    bool pop(T& val) noexcept {
        const size_t current_head = read_idx_.load(std::memory_order_relaxed);

        // Optimasi: Gunakan cached write index lokal
        if (current_head == cached_write_idx_) {
            cached_write_idx_ = write_idx_.load(std::memory_order_acquire);
            if (current_head == cached_write_idx_) {
                return false; // Penyangga kosong
            }
        }

        // Pindahkan data
        val = std::move(reinterpret_cast<T&>(storage_[current_head & BufferMask]));

        // Hancurkan objek secara eksplisit jika diperlukan (trivial type tidak strictly butuh)
        reinterpret_cast<T*>(&storage_[current_head & BufferMask])->~T();

        // Publikasikan indeks baca dengan semantik release
        read_idx_.store(current_head + 1, std::memory_order_release);
        return true;
    }

    [[nodiscard]] size_t size() const noexcept {
        const size_t head = read_idx_.load(std::memory_order_relaxed);
        const size_t tail = write_idx_.load(std::memory_order_relaxed);
        return (tail >= head) ? (tail - head) : 0;
    }

private:
    static constexpr size_t BufferMask = Capacity - 1;

    // Buffer mentah dengan alinyemen memori
    alignas(hardware_destructive_interference_size) 
    alignas(alignof(T)) std::byte storage_[sizeof(T) * Capacity];

    // Variabel state produsen: diletakkan di cache line tersendiri
    alignas(hardware_destructive_interference_size) 
    std::atomic<size_t> write_idx_;
    size_t cached_read_idx_{0}; // Hanya diakses oleh thread produsen

    // Variabel state konsumen: diletakkan di cache line terpisah untuk cegah False Sharing
    alignas(hardware_destructive_interference_size) 
    std::atomic<size_t> read_idx_;
    size_t cached_write_idx_{0}; // Hanya diakses oleh thread konsumen
};
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Ultra-Low Latency Market Data Dissemination (HFT Trading Gateway)
- **Konteks Masalah**: Sebuah bursa saham menerima pembaruan buku pesanan (*Order Book Updates*) sebanyak 15 juta pesan per detik. Setiap lonjakan latensi (*jitter*) melebihi 2 mikrodetik menyebabkan kegagalan arbitrase portofolio dan denda SLA finansial.
- **Implementasi Awal**: Menggunakan arsitektur `std::mutex` dan `std::condition_variable` untuk membagikan antrean transaksi dari penerima jaringan (I/O thread) ke mesin agregasi buku (*Matching Engine*).
- **Hasil Diagnostik Produksi**:
  - *Context Switches*: Rata-rata 250.000 transisi konteks per detik di tingkat kernel OS (`futex_wait`).
  - Latensi P99.9: Melonjak hingga 45 mikrodetik saat volatilitas pasar tinggi akibat fenomena *Lock Inversion* dan *Convoy Phenomenon*.
- **Solusi Rekayasa**:
  1. Mengganti antrean berbasis *mutex* dengan implementasi matriks antrean **SPSC Lock-Free Circular Buffer** terdedikasi per pasangan *worker-thread*.
  2. Menerapkan isolasi CPU (`isolcpus` pada *kernel boot args*) dan mengikat *thread* secara deterministik ke *core* fisik tertentu (`pthread_setaffinity_np`).
  3. Memasang instruksi atomik beralinyemen `alignas(64)` dengan semantik `memory_order_acquire`/`release`.
- **Hasil Akhir**:
  - *Context Switches*: Turun menjadi mendekati 0 selama operasi normal.
  - Throughput: Meningkat dari 3,8 juta msg/detik menjadi 24,5 juta msg/detik.
  - Latensi Rata-rata: Turun dari 4,2 mikrodetik menjadi 185 nanodetik.
  - Latensi P99.9: Terkompresi stabil di bawah 450 nanodetik.

---

### 9. Trade-offs

```
              ┌──────────────────────────────────────────────┐
              │           Trade-off Architecture             │
              └──────────────────────────────────────────────┘
                    ▲                                  ▲
                    │                                  │
    [ Lock-Free Circular Buffer ]            [ Mutex + Condition Var ]
    ─────────────────────────────            ─────────────────────────
    + Latensi Sub-Mikrodetik                 + Penggunaan CPU Efisien
    + Skalabilitas Tinggi                     + Implementasi Sederhana
    + Determinisme Ekstrem                   + Penanganan Kapasitas Luwes
    ─────────────────────────────            ─────────────────────────
    - 100% Core CPU Spinning                 - Latensi P99.9 Erat OS
    - Kompleksitas Kode Ekstrem              - Thread Preemption Trap
    - Alokasi Kapasitas Statis               - Context Switch Invalidation
```

| Kriteria | Mutex-Based Locking | Lock-Free CAS Loop (e.g., MPMC) | Lock-Free SPSC Ring Buffer | Actor / Message Queue |
| :--- | :--- | :--- | :--- | :--- |
| **P99 Latency** | Buruk (>10µs) | Sedang (1-5µs) | Superior (<200ns) | Cukup (5-50µs) |
| **Throughput** | Rendah (<5M ops/s) | Sedang (5-15M ops/s) | Sangat Tinggi (>40M ops/s) | Sedang (2-8M ops/s) |
| **Utilisasi CPU**| Sangat rendah saat idle | Tinggi (CPU burn via spin) | Tinggi jika di-spin murni | Rendah - Sedang |
| **Kompleksitas** | Rendah (Mudah di-debug)| Sangat Tinggi (Bahaya ABA) | Menengah-Tinggi | Menengah |
| **Infrastruktur**| Semua arsitektur | Sensitif arsitektur memori | Sangat efisien di x86 & ARM | Bergantung runtime |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 The ABA Problem pada Node-Based Data Structures
*Penyebab*: Thread T1 membaca pointer $A$. T1 tertunda (*preempted*). Thread T2 menghapus $A$, mengalokasikan memori baru yang kebetulan menggunakan alamat memori yang sama ($A$), memodifikasi struktur, lalu menyelesaikannya. T1 bangun dan mengeksekusi `compare_exchange_weak(A, ...)`. CAS berhasil karena alamatnya identik, padahal status internal data telah berubah drastis.
*Solusi*: Gunakan **Tagged Pointers** (menggabungkan *counter* 64-bit dengan alamat pointer via manipulasi bit atau `std::atomic<DoubleWord>`) atau mekanisme **Hazard Pointers / Epoch-Based Reclamation (EBR)**.

#### 10.2 Asumsi Arsitektur x86 Mengaburkan Bug di ARM (Strong vs Weak Ordering)
*Penyebab*: Arsitektur x86 mengimplementasikan model memori TSO (*Total Store Order*), di mana pemuatan (*loads*) tidak diacak melompati pemuatan lain, dan penyimpanan (*stores*) tidak diacak melompati penyimpanan lain. Jika pemrogram menggunakan `memory_order_relaxed` secara salah di x86, kode mungkin tampak berfungsi stabil. Namun, ketika kode yang sama dikompilasi untuk Apple Silicon (ARM64) yang memiliki arsitektur *Weakly Ordered*, sistem langsung mengalami korupsi data.
*Solusi*: Validasi semantik secara formal dan gunakan pengujian dinamis di lingkungan ARM menggunakan Clang ThreadSanitizer.

#### 10.3 Deteksi & Diagnostik dengan LLVM Sanitizer dan Linux Tooling
Gunakan opsi kompilasi berikut pada lingkungan pengujian integrasi:
```bash
# Kompilasi dengan detektor thread race
clang++ -std=c++20 -fsanitize=thread -g -O1 ring_buffer_test.cpp -o rb_tsan

# Profil cache invalidation dan false sharing
perf c2c record ./rb_benchmark
perf c2c report --stdio
```

Jika `perf c2c` menampilkan metrik *HITM* (Hit in Modified Cache) yang tinggi antar-*core*, ini merupakan indikator pasti terjadinya **False Sharing**.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Verifikasi Ukuran Jalur Cache**: Pastikan variabel atomik produsen dan konsumen dipisahkan minimal oleh `hardware_destructive_interference_size` byte menggunakan `alignas`.
2. [ ] **Eliminasi Alokasi Dinamis Jalur Critis**: Larang mutlak instruksi `malloc`, `new`, atau dealokasi memori pada loop utama pemrosesan data.
3. [ ] **Gunakan Relaxed Sejauh Mungkin**: Batasi pemakaian `acquire` dan `release` hanya pada titik publikasi status sinkronisasi. Jangan pernah menggunakan `seq_cst` kecuali terbukti wajib melalui verifikasi matematis.
4. [ ] **Terapkan Instruksi CPU Relaxation**: Selalu sertakan instruksi instruksional seperti `_mm_pause()` (x86) atau `yield` (ARM) dalam *spin-wait loop* untuk menghemat daya dan mencegah *pipeline starvation*.
5. [ ] **Validasi Thread Affinity**: Kunci *thread* pemrosesan kritis ke *core* fisik independen menggunakan API platform (`pthread_setaffinity_np` di Linux) guna mencegah migrasi *core* oleh OS scheduler.
6. [ ] **Auditor Assembly Output**: Buka output *compiler* via compiler explorer (Godbolt) untuk memastikan tidak ada instruksi `lock cmpxchg` atau `mfence` yang tidak terduga pada jalur kritis.

---

### 12. Hands-on Practice

Terapkan implementasi struktur direktori berikut untuk disimpan di `hands-on/m02/`:

```
hands-on/m02/
├── CMakeLists.txt
├── include/
│   └── spsc_queue.hpp
└── src/
    └── benchmark_main.cpp
```

#### Langkah 1: Buat berkas `hands-on/m02/include/spsc_queue.hpp`
Gunakan implementasi kode dari Bagian 7.2.

#### Langkah 2: Buat berkas `hands-on/m02/src/benchmark_main.cpp`
```cpp
#include "spsc_queue.hpp"
#include <iostream>
#include <thread>
#include <chrono>
#include <numeric>

constexpr size_t OPERATIONS_COUNT = 10'000'000;
constexpr size_t BUFFER_SIZE = 65536;

struct alignas(64) MarketTick {
    uint64_t sequence;
    double price;
    uint32_t volume;
};

int main() {
    SPSCRingBuffer<MarketTick, BUFFER_SIZE> ring_buffer;
    
    std::cout << "Memulai benchmark SPSC Ring Buffer dengan " << OPERATIONS_COUNT << " pesan...\n";

    auto start_time = std::chrono::high_resolution_clock::now();

    std::thread producer([&]() {
        for (uint64_t i = 0; i < OPERATIONS_COUNT; ++i) {
            MarketTick tick{i, 100.50 + (i % 10), static_cast<uint32_t>(i % 500)};
            while (!ring_buffer.emplace(tick)) {
                #if defined(__x86_64__) || defined(_M_X64)
                __builtin_ia32_pause();
                #endif
            }
        }
    });

    std::thread consumer([&]() {
        MarketTick received_tick{};
        for (uint64_t i = 0; i < OPERATIONS_COUNT; ++i) {
            while (!ring_buffer.pop(received_tick)) {
                #if defined(__x86_64__) || defined(_M_X64)
                __builtin_ia32_pause();
                #endif
            }
        }
    });

    producer.join();
    consumer.join();

    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(end_time - start_time).count();
    double seconds = duration_ns / 1'000'000'000.0;
    double throughput = OPERATIONS_COUNT / seconds;

    std::cout << "Selesai dalam: " << seconds << " detik.\n";
    std::cout << "Throughput: " << throughput / 1'000'000.0 << " Juta pesan/detik.\n";
    std::cout << "Rata-rata latensi transfer per pesan: " << static_cast<double>(duration_ns) / OPERATIONS_COUNT << " ns.\n";

    return 0;
}
```

#### Langkah 3: Buat berkas `hands-on/m02/CMakeLists.txt`
```cmake
cmake_minimum_required(VERSION 3.20)
project(LockFreeSPSCPerf LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if (CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
    add_compile_options(-O3 -march=native -Wall -Wextra -Werror)
endif()

include_directories(include)

add_executable(benchmark_spsc src/benchmark_main.cpp)
target_link_libraries(benchmark_spsc PRIVATE pthread)
```

#### Langkah 4: Kompilasi dan Eksekusi
```bash
cd hands-on/m02/
mkdir build && cd build
cmake ..
cmake --build .
./benchmark_spsc
```

---

### 13. Exercise

#### Tingkat: Mudah (Easy)
1. Periksa potongan kode berikut dan tunjukkan letak potensi kecacatan performanya:
```cpp
struct MetricsCollector {
    std::atomic<uint64_t> total_requests{0};
    std::atomic<uint64_t> total_errors{0};
};
// Thread A intensif menulis total_requests, Thread B intensif menulis total_errors.
```
*Tugas*: Refaktor struktur tersebut agar bebas dari masalah invalidasi performa tingkat silikon.

#### Tingkat: Menengah (Medium)
1. Modifikasi `SPSCRingBuffer` di Bagian 7.2 agar mampu mengembalikan status kegagalan terperinci menggunakan tipe enumerasi `enum class QueueError { BufferFull, BufferEmpty, Ok }` dan lengkapi dengan metode inspeksi `is_empty()` dan `is_full()` yang valid secara konkuren (*relaxed checks*).

#### Tingkat: Lanjut (Hard)
1. Rancang implementasi primitif **Spinlock Ticket-Based Lock** yang memiliki sifat *fair FIFO* menggunakan operasi atomik `std::atomic<uint32_t>::fetch_add`. Implementasi harus menggunakan urutan memori (*memory order*) minimum yang tepat (bukan `seq_cst`) serta menyediakan mekanisme *exponential backoff* berbasis `_mm_pause()` untuk meminimalkan saturasi *bus interconnect*.

---

### 14. Challenge (Tantangan Desain Industri Nyata)

**Skenario**: Anda adalah Lead Architect pada infrastruktur mesin pencocokan aset kripto (*Crypto Derivative Exchange*). Sistem Anda dituntut memproses pembatalan pesanan terdistribusi dari 4 *Gateway Thread* berbeda yang bermuara pada 1 *Single Engine Processing Thread* (Topologi MPSC - *Multi-Producer Single-Consumer*).
1. Rancang arsitektur antrean MPSC Bounded Lock-Free Ring Buffer yang:
   - Tidak menggunakan *lock* sama sekali.
   - Tidak menyebabkan *deadlock* saat *buffer* penuh.
   - Menggunakan atomik `compare_exchange_weak` yang optimal untuk produsen, sementara konsumen hanya memerlukan penarikan sekuensial bebas CAS.
   - Menyertakan mekanisme *failover sequence tracking* jika salah satu produsen terhenti di tengah alokasi reservasi slot antrean.
2. Analisis implikasi teoritis dan praktis jika antrean ini dialokasikan di atas blok memori bersama (*POSIX Shared Memory / `/dev/shm`*) yang melibatkan beberapa proses OS independen.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)
1. **Apakah operasi `std::atomic<int>::load(std::memory_order_relaxed)` menjamin bahwa data tidak mengalami *tearing* (pembacaan setengah nilai)?**
   - *Jawaban*: Ya. Semantik `relaxed` tetap menjamin atomisitas penuh atas nilai variabel tersebut, sehingga pembacaan nilai yang parsial (*torn read*) tidak akan terjadi. Namun, semantik ini tidak memberikan jaminan urutan (*ordering*) terhadap variabel lain di sekitarnya.
2. **Apa yang dimaksud dengan ukuran *Cache Line* dan berapa besaran standarnya pada sistem x86 dan ARM64 modern?**
   - *Jawaban*: *Cache Line* adalah unit transfer memori diskret terkecil antara memori utama (RAM) dan sistem *cache* CPU. Standar umumnya adalah 64 byte (pada beberapa arsitektur server tingkat tinggi seperti Apple M-series atau ARM Neoverse dapat mencapai 128 byte).
3. **Mengapa instruksi `alignas(64)` esensial dalam deklarasi variabel di pemrograman bebas kunci multithread?**
   - *Jawaban*: Untuk memastikan variabel dialokasikan tepat pada batas awal *cache line*, mencegahnya berbagi baris memori yang sama dengan variabel yang diakses *thread* lain, sehingga mengeliminasi fenomena *False Sharing*.
4. **Apa default `std::memory_order` yang digunakan apabila pemrogram tidak menyatakannya secara eksplisit pada metode atomik?**
   - *Jawaban*: `std::memory_order_seq_cst` (Sequential Consistency).
5. **Mengapa algoritma bebas kunci (*lock-free*) tidak selalu berarti sistem menjadi lebih cepat daripada arsitektur berbasis *mutex*?**
   - *Jawaban*: Karena jika terjadi kontensi tinggi pada satu alamat atomik tunggal (*CAS contention*), CPU akan menghabiskan banyak siklus untuk melakukan *spin*, membanjiri bus komunikasi memori (*interconnect saturation*), yang dapat menghasilkan performa lebih buruk daripada penangguhan *thread* tidur via *mutex*.

#### Bagian 2: Intermediate (5 Soal)
6. **Jelaskan perbedaan mendasar antara relasi *Happens-Before* dan *Synchronizes-With* pada C++ Memory Model!**
   - *Jawaban*: *Synchronizes-With* adalah relasi fisik langsung antar-thread yang dibangun melalui operasi atomik tertentu (misal: *Store Release* yang dibaca oleh *Load Acquire* pada atomik yang sama). Relasi *Happens-Before* adalah relasi transitif yang lebih luas; jika operasi A *synchronizes-with* B, dan di dalam thread yang sama B dieksekusi sebelum C (*sequenced-before*), maka A *happens-before* C.
7. **Pada arsitektur CPU x86-64, mengapa instruksi rakitan (*assembly*) untuk `std::memory_order_acquire` pada operasi pembacaan sering kali identik dengan instruksi `std::memory_order_relaxed`?**
   - *Jawaban*: Karena perangkat keras x86 mengimplementasikan model TSO (*Total Store Order*) yang secara alami melarang penataan ulang *Load-Load* dan *Load-Store*. Dengan demikian, batasan *acquire* telah dijamin secara otomatis oleh tingkat silikon tanpa memerlukan instruksi pembatas memori (*hardware memory fence*) tambahan.
8. **Kapan Anda harus menggunakan `compare_exchange_weak` dibandingkan `compare_exchange_strong`?**
   - *Jawaban*: Gunakan `compare_exchange_weak` ketika operasi CAS berada di dalam sebuah *loop* (*retry-loop*), karena varian *weak* dapat bekerja lebih cepat pada beberapa arsitektur (seperti LL/SC pada ARM) meskipun dapat gagal secara semu (*spurious failure*). Gunakan `compare_exchange_strong` jika operasi tidak berada di dalam loop atau kegagalan semu tidak dapat ditoleransi.
9. **Apa bahaya dari penggunaan `std::atomic<std::shared_ptr<T>>` tanpa pemahaman mendalam di jalur kritis (*hot-path*)?**
   - *Jawaban*: Mengontrol *atomic reference-counting* dari pointer bersama secara konkuren memerlukan alokasi kontrol blok internal dan sinkronisasi atomik ganda yang sangat mahal, sering kali melibatkan *internal spinlocks* yang merusak jaminan latensi konstan sistem.
10. **Bagaimana instruksi `_mm_pause()` atau `__builtin_ia32_pause()` membantu performa pada loop *busy-waiting*?**
    - *Jawaban*: Instruksi ini memberi sinyal ke *core* CPU bahwa kode sedang berada dalam *spin-loop*, menunda eksekusi pipeline selama beberapa siklus guna mencegah *memory order violation* pipeline stall saat keluar dari loop, serta menekan konsumsi energi prosesor.

#### Bagian 3: Skenario Kasus Produksi (3 Soal)
11. **Skenario A**: Dalam sebuah aplikasi pemrosesan telemetri, *latency profiling* menunjukkan bahwa throughput antrean SPSC anjlok hingga 80% saat aplikasi dipindahkan dari satu soket CPU ke mesin multi-soket (Dual AMD EPYC NUMA Nodes). Kedua *thread* berjalan pada *core* yang berbeda. Apa penyebabnya dan bagaimana mitigasi arsitekturalnya?
    - *Solusi Analitis*: Masalah ini dipicu oleh latensi lintas soket (*Cross-Socket Interconnect Traffic / AMD Infinity Fabric latency*) akibat komunikasi NUMA. Thread produsen dan konsumen kemungkinan dijadwalkan pada node NUMA yang berbeda secara fisik. Mitigasi: Ikat kedua *thread* ke inti-inti prosesor yang berada dalam satu domain NUMA fisik yang sama menggunakan alokasi memori lokal (`numactl --cpunodebind` atau API `libnuma`).

12. **Skenario B**: ThreadSanitizer (TSan) melaporkan *data-race* pada penulisan muatan data antrean non-atomik, padahal pemrogram merasa telah mempublikasikan data tersebut menggunakan `std::atomic<bool> flag` dengan urutan memori `memory_order_relaxed`. Mengapa hal ini terjadi dan bagaimana perbaikannya?
    - *Solusi Analitis*: Urutan `memory_order_relaxed` tidak menyediakan relasi *Synchronizes-With*. Pengompilasi maupun prosesor berhak menata ulang penyimpanan data non-atomik ke lokasi **setelah** operasi penulisan `flag` dilakukan. Akibatnya, konsumen melihat `flag == true` sebelum data sebenarnya selesai ditulis ke memori fisik. Solusinya: Ubah penulisan flag produsen menjadi `memory_order_release` dan pembacaan konsumen menjadi `memory_order_acquire`.

13. **Skenario C**: Pada struktur data antrean bebas kunci berbasis rantai simpul dinamis (*Linked List Lock-Free*), sistem mengalami *crash segmentation fault* secara acak setelah berjalan 48 jam di lingkungan beban produksi tinggi. Pengujian terisolasi selalu lulus. Masalah apa yang paling mungkin terjadi?
    - *Solusi Analitis*: Ini adalah manifestasi klasik dari **ABA Problem** yang berujung pada **Use-After-Free**. Sebuah *thread* menyimpan referensi ke pointer simpul memori yang dibebaskan (*freed/deallocated*) oleh *thread* lain dan dialokasikan ulang oleh sistem operasi untuk entitas baru, membuat pointer atomik menunjuk ke segmen memori yang korup atau tidak valid. Solusinya: Terapkan skema *Epoch-Based Reclamation* (EBR) atau *Hazard Pointers* untuk menunda dealokasi memori fisik hingga tidak ada satu pun *thread* aktif yang memegang referensi ke memori tersebut.

---

### 16. Summary

1. **Model Memori Formal**: Pemrograman tingkat rendah modern diatur oleh relasi matematis *Synchronizes-With* dan *Happens-Before*, bukan oleh urutan baris kode sumber teks.
2. **Karakteristik Silikon & Perangkat Keras**: Mengabaikan topologi perangkat keras (*Store Buffers*, *Cache Lines*, dan protokol MESI) akan merusak performa melalui *False Sharing* dan *Pipeline Stalls*, terlepas dari kebenaran logika algoritma.
3. **Optimasi Tingkat Akses**: Penggunaan `memory_order_acquire` dan `memory_order_release` adalah landasan utama interaksi antar-*thread* berkinerja tinggi, memberikan jaminan konsistensi data yang tepat tanpa menimbulkan penalti instruksi penahan bus (*bus serialization overhead*) seperti pada `memory_order_seq_cst`.
4. **Arsitektur Bebas Kunci Deterministik**: Sistem dengan batas performa ekstrem (*ultra-low latency*) mengeliminasi perebutan sumber daya dengan memadukan antrean sirkular statis beralinyemen memori (SPSC), afinitas CPU terisolasi, dan operasi tanpa intervensi *kernel space*.