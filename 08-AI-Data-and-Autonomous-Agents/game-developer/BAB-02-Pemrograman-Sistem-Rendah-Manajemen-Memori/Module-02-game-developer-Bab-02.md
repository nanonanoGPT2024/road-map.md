# Kurikulum Enterprise Game Engine Systems: Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

**Kategori:** 08-AI-Data-and-Autonomous-Agents / Game Systems Engineering  
**Bab 02:** Pemrograman Sistem Rendah & Manajemen Memori Tingkat Lanjut  
**Modul:** Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi  
**Target Platform:** x86_64 / ARM64 (Bare-metal, Console, PC AAA Runtime)  
**Standar Bahasa:** Modern C++20/C++23  

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan memiliki kompetensi produksi untuk:
1. **Mendiagnosis dan Mengeliminasi Latensi Alokator Standar:** Memahami batasan deterministik dari `malloc`/`free` bawaan glibc/MSVCRT, kontensi mutex pada heap multi-threaded, serta fragmentasi eksternal pada beban kerja 60–120 FPS.
2. **Merancang Custom Memory Allocator Tingkat Rendah:** Mengimplementasikan *Linear/Arena Allocator*, *Stack Allocator*, *Free-List Allocator* (dengan *Boundary Tags* dan coalescing), serta *Thread-Safe Fixed-Size Block Pool Allocator* yang sadar batas cache (*cache-line aware*).
3. **Mengoptimalkan Hardware Cache & Penyelarasan Memori (Memory Alignment):** Menguasai interaksi CPU Cache L1/L2/L3, eliminasi *false sharing* menggunakan padding `std::hardware_destructive_interference_size`, dan penyelarasan alamat memori untuk vektorisasi SIMD (AVX-512/NEON).
4. **Menerapkan Arsitektur Memori Data-Oriented (DOD):** Mengonversi struktur *Array of Structures* (AoS) menjadi *Structure of Arrays* (SoA) / *Array of Structures of Arrays* (AoSoA) guna memaksimalkan *hardware prefetcher* dan meminimalkan *cache misses* (TLB misses).
5. **Mengintegrasikan Instrumentasi Produksi:** Memasang pelacak jejak memori internal (*memory tracking tags*), deteksi *leakage*, *canary values* untuk *buffer overrun*, dan integrasi profiler performa tinggi (Tracy Memory Profiler).

---

## 2. Prerequisite

Peserta wajib menguasai:
* **Bahasa C++:** Tingkat lanjut (C++17/C++20), mencakup *pointer arithmetic*, *placement new*, *explicit destruction*, *templates*, rvalue references, dan konsep *RAII*.
* **Arsitektur Komputer Dasar:** Pemahaman tentang hierarki register, cache line (standar 64-byte), Translation Lookaside Buffer (TLB), Virtual Memory (Page Size 4KB / Huge Pages 2MB).
* **Konkurensi Dasar:** Operasi atomik (`std::atomic`), model memori C++ (`memory_order_relaxed`, `acquire`, `release`), thread synchronization primitives.
* **Toolchain:** CMake (>= 3.22), GCC 12+ / Clang 15+ / MSVC 2022, GDB/LLDB, dan Linux AddressSanitizer (ASan).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Masalah Alokasi Heap Konvensional (`malloc` / `operator new`)
Manajer memori bawaan OS (seperti `ptmalloc` pada glibc atau HeapAlloc pada Win32) dirancang untuk penggunaan umum (*general-purpose*). Karakteristik intinya berlawanan dengan kebutuhan rendering dan simulasi real-time:
* **Non-deterministik:** Operasi alokasi dapat memicu traversal linked-list yang kompleks untuk mencari chunk yang cocok (*first-fit*, *best-fit*) atau melakukan transisi *kernel-space* (`brk` / `mmap`) saat memori habis.
* **Kontensi Kunci (Lock Contention):** Heap global menggunakan *mutex* atau *fine-grained bucket locks*. Ketika puluhan thread game worker mencoba mengalokasikan entitas pada saat bersamaan, thread mengalami *stall*.
* **Fragmentasi Memori (External Fragmentation):** Pola alokasi dan dealokasi objek dengan rentang hidup (*lifetime*) yang acak memecah memori fisik menjadi blok-blok kecil yang tidak berdekatan.

```
Initial State:
[       Free Chunk: 64 KB        ]

After random allocations and deallocations:
[ Alloc: 8KB ][ Free: 4KB ][ Alloc: 16KB ][ Free: 8KB ][ Alloc: 28KB ]

Problem:
Permintaan alokasi 10 KB akan GAGAL meskipun total memori bebas = 12 KB!
```

### 3.2 Hirarki Memori Fisik, Cache Line, dan Alignment
CPU modern tidak pernah membaca data byte-per-byte dari DRAM. Data selalu dibaca dalam unit **Cache Line** (umumnya 64 byte).

```
+---------------+---------+-------------------+-----------------+
| Tingkat Cache | Ukuran  | Latensi (Siklus)  | Latensi (Nano)  |
+---------------+---------+-------------------+-----------------+
| L1 Data Cache | 32-48 KB| 4 - 5 cycles      | ~1.0 ns         |
| L2 Cache      | 512KB-1M| 12 - 14 cycles    | ~3.0 ns         |
| L3 Cache      | 16-96 MB| 40 - 75 cycles    | ~15-20 ns       |
| Main DRAM     | 16-64 GB| 200+ cycles       | ~60-100 ns      |
+---------------+---------+-------------------+-----------------+
```

#### Memory Alignment (Penyelarasan Memori)
Sebuah tipe data ukuran $N$ byte harus dialokasikan pada alamat memori yang merupakan kelipatan dari $N$:
$$\text{Address} \pmod N = 0$$
Jika pointer memori melintasi batas *cache line* (*unaligned access*), CPU harus melakukan dua transaksi memori untuk membaca satu variabel, yang memicu degradasi performa hingga 200%. Lebih lanjut, instruksi SIMD (misalnya `_mm256_load_ps` pada AVX2) mewajibkan penyelarasan 32-byte; jika dilanggar, CPU akan melemparkan interupsi *General Protection Fault* (GPF / SIGSEGV).

Formula kalkulasi padding penyelarasan:
$$\text{Padding} = (\text{Alignment} - (\text{RawAddress} \pmod{\text{Alignment}})) \pmod{\text{Alignment}}$$

### 3.3 Taksonomi Custom Allocator
Sistem game modern mengklasifikasikan data berdasarkan **Lifetime Strategy**:

```
+-------------------------------------------------------------------------+
|                        Game Engine Memory Architecture                  |
+-------------------------------------------------------------------------+
                                     |
       +-----------------------------+----------------------------+
       |                                                          |
[ Static / Persistent ]                                  [ Transient / Dynamic ]
(Game Lifetime)                                          (Frame-based or Subsystem)
       |                                                          |
  +----+----+                                        +------------+------------+
  |         |                                        |            |            |
Boot/OS   Root Allocator                        Frame Allocator Pool Allocator Free-List
Heap      VirtualAlloc/mmap                     (Linear/Arena)  (Particles,    (Audio, Level
          (Virtual Reserve)                     (Resets at EOF)  Projectiles)   Streaming)
```

1. **Linear / Arena Allocator:** Alokasi hanya menggeser offset penunjuk (`head += size`). Tidak ada operasi *individual free*. Seluruh arena dibersihkan sekaligus dengan mengatur `head = 0`. Kompleksitas: $O(1)$ alokasi, $O(1)$ *bulk free*.
2. **Stack / Double-Buffered Allocator:** Alokasi menggeser penunjuk; dealokasi harus dilakukan secara terbalik (LIFO) menggunakan *marker*. Sangat ideal untuk struktur hirarkis seperti *scene graph traversal* atau pemrosesan frame rendering.
3. **Pool Allocator:** Membagi blok memori besar menjadi slot-slot berukuran seragam ($S$). Menggunakan internal *freelist singly-linked* yang berada di dalam slot memori itu sendiri (*in-situ metadata*). Kompleksitas alokasi dan dealokasi: murni $O(1)$, tanpa fragmentasi eksternal.
4. **Free-List Allocator:** Mengelola blok dengan ukuran variabel. Tiap blok menyertakan header ukuran dan status alokasi. Mendukung *coalescing* (penggabungan blok bebas bersebelahan) untuk memerangi fragmentasi.

---

## 4. Why & What

| Dimensi | General Heap (`malloc` / `new`) | Game Engine Custom Allocators |
| :--- | :--- | :--- |
| **Determinisasi Latensi** | Buruk ($O(N)$ worst case, OS syscall) | Ketat $O(1)$ untuk Arena dan Pool |
| **Overhead Metadata** | 8 - 16 byte per alokasi | 0 byte (Pool/Arena), minimal pada Free-List |
| **Multithreading** | Terhambat contention lock global | Thread-Local Arena (Zero Lock) / Lock-Free |
| **Lokalitas Cache** | Fragmented, objek tersebar di memori | Kontigu, data dikelompokkan rapat |
| **Debuggability** | Terbatas pada OS tool | Memantau memory budget per subsystem secara real-time |

### Mengapa Pendekatan Tradisional Gagal dalam Skala AAA?
Dalam game 60 FPS, frame budget total adalah **16.67 milidetik** (atau **8.33 ms** pada 120 FPS). Jika sebuah loop simulasi fisika atau sistem partikel memicu 10.000 alokasi kecil dinamis per frame melalui heap global:
1. Overhead lock heap OS dapat mengonsumsi 2–4 ms hanya untuk manajemen pointer.
2. Fragmentasi memori menyebabkan *cache misses* masif. Waktu tunggu DRAM membuat thread prosesor mengalami *idle stall* hingga 40–60% dari siklus eksekusi game loop.

---

## 5. How (Workflow Detail)

### Alur Kerja Alokasi Frame Tingkat Tinggi (Frame-Based Memory Lifecycle)

```
[ Awal Frame N ]
      |
      v
+--------------------------------------------------------+
| 1. Reset Frame Linear Allocator (Head Offset = 0)      |
+--------------------------------------------------------+
      |
      v
+--------------------------------------------------------+
| 2. Gameplay & AI Tick                                  |
|    - String transient, pathfinding node, raycast temp  |
|      mengambil memori dari Frame Allocator             |
|    - Entitas dinamis (Spawn) dialokasikan via Pool     |
+--------------------------------------------------------+
      |
      v
+--------------------------------------------------------+
| 3. Render Extraction & Command Bucket Generation       |
|    - Matriks transformasi & material packet masuk ke   |
|      Double-Buffered Render Allocator                  |
+--------------------------------------------------------+
      |
      v
+--------------------------------------------------------+
| 4. Dispatch Render Thread / GPU Upload                 |
+--------------------------------------------------------+
      |
      v
+--------------------------------------------------------+
| 5. Akhir Frame N:                                      |
|    - Frame Allocator direset (No destructors needed    |
|      untuk POD/Trivially Destructible types)           |
|    - Pool Allocator mengeksekusi deferred free         |
+--------------------------------------------------------+
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Meja Kasir Khusus vs. Lapangan Parkir Fleksibel
* **`malloc`:** Seperti lapangan parkir umum di tengah kota. Mobil dengan beragam ukuran masuk dan keluar sembarangan. Petugas parkir harus terus berjalan memutari lapangan mencari celah kosong yang pas. Setelah beberapa jam, lapangan dipenuhi celah kecil yang tidak bisa memuat bus, meski secara total masih ada ruang kosong.
* **Pool Allocator:** Seperti rak parkir khusus sepeda motor. Setiap petak memiliki ukuran yang identik persis. Ketika motor keluar, nomor petak langsung dicatat di papan tulis (Free List). Motor berikutnya langsung parkir di nomor teratas papan tulis dalam hitungan detik.
* **Arena Allocator:** Seperti gulungan kertas struk kasir. Kasir mencetak baris per baris ke bawah secara berurutan. Saat transaksi selesai (akhir frame), kertas disobek dan dibuang sekaligus; tidak ada upaya menghapus tulisan baris per baris.

### Diagram Arsitektur Memory Pool Internal

```
+--------------------------------------------------------------------------+
|                  Chunk Memory Buffer (64-byte aligned)                   |
+--------------------------------------------------------------------------+
| Block 0 (32B)    | Block 1 (32B)    | Block 2 (32B)    | Block 3 (32B)   |
| [NextPtr: Block1]| [NextPtr: Block2]| [NextPtr: Block3]| [NextPtr: nullptr]
+--------------------------------------------------------------------------+
 ^
 |--- FreeListHead
 
 ALOKASI:
 1. Return current FreeListHead (Block 0)
 2. FreeListHead = FreeListHead->NextPtr (Block 1)
 
 DEALOKASI (Objek pada Block 1):
 1. Block1->NextPtr = FreeListHead
 2. FreeListHead = Block1
 (Zero fragmentation, strictly O(1))
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: High-Performance Linear Arena Allocator
Alokator ini tidak mengeksekusi individual deallocation. Sangat ideal untuk alokasi temporer per-frame (*scratchpad*).

```cpp
#include <cstdint>
#include <cstddef>
#include <new>
#include <utility>
#include <cassert>

class LinearArenaAllocator {
public:
    LinearArenaAllocator(void* startMemory, size_t totalSizeBytes) noexcept
        : m_buffer(static_cast<uint8_t*>(startMemory)),
          m_capacity(totalSizeBytes),
          m_offset(0) {}

    ~LinearArenaAllocator() = default;

    LinearArenaAllocator(const LinearArenaAllocator&) = delete;
    LinearArenaAllocator& operator=(const LinearArenaAllocator&) = delete;

    [[nodiscard]] void* Allocate(size_t size, size_t alignment) noexcept {
        assert((alignment & (alignment - 1)) == 0 && "Alignment must be power of 2");

        const uintptr_t currentAddress = reinterpret_cast<uintptr_t>(m_buffer + m_offset);
        const size_t padding = (alignment - (currentAddress & (alignment - 1))) & (alignment - 1);

        if (m_offset + padding + size > m_capacity) {
            return nullptr; // Out of memory
        }

        m_offset += padding;
        void* const allocatedPtr = static_cast<void*>(m_buffer + m_offset);
        m_offset += size;

        return allocatedPtr;
    }

    template <typename T, typename... Args>
    [[nodiscard]] T* Create(Args&&... args) {
        void* const mem = Allocate(sizeof(T), alignof(T));
        if (!mem) return nullptr;
        return new (mem) T(std::forward<Args>(args)...);
    }

    void Reset() noexcept {
        m_offset = 0;
    }

    [[nodiscard]] size_t GetAllocatedBytes() const noexcept { return m_offset; }
    [[nodiscard]] size_t GetRemainingBytes() const noexcept { return m_capacity - m_offset; }

private:
    uint8_t* const m_buffer;
    const size_t   m_capacity;
    size_t         m_offset;
};
```

---

### 7.2 Practical Example: Lock-Free Thread-Safe Fixed-Size Block Pool Allocator
Implementasi industri C++20 untuk komponen partikel/peluru berevolusi tinggi, dilengkapi *cache-line boundary protection* dan ABA problem mitigation menggunakan pointer berindeks (*tagged/index-based linked list*).

```cpp
#include <iostream>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <new>
#include <utility>
#include <cassert>
#include <vector>

#if defined(_WIN32)
#include <malloc.h>
#define ALIGNED_ALLOC(alignment, size) _aligned_malloc(size, alignment)
#define ALIGNED_FREE(ptr) _aligned_free(ptr)
#else
#include <stdlib.h>
#define ALIGNED_ALLOC(alignment, size) aligned_alloc(alignment, size)
#define ALIGNED_FREE(ptr) free(ptr)
#endif

// Cache line alignment to prevent false sharing
constexpr size_t SYSTEM_CACHE_LINE_SIZE = 64;

class alignas(SYSTEM_CACHE_LINE_SIZE) LockFreeFixedPoolAllocator {
private:
    union Node {
        Node* next;
        alignas(std::max_align_t) uint8_t storage[1]; // Flexible array placeholder
    };

    struct alignas(SYSTEM_CACHE_LINE_SIZE) HeadPtr {
        Node* pointer{nullptr};
        uint64_t counter{0}; // ABA Mitigation tag
    };

public:
    LockFreeFixedPoolAllocator(size_t objectSize, size_t alignment, size_t objectCount)
        : m_blockCount(objectCount) 
    {
        // Object size minimal harus mampu menampung pointer Node* untuk Free-List in-situ
        size_t actualSize = std::max(objectSize, sizeof(Node));
        m_actualObjectSize = (actualSize + (alignment - 1)) & ~(alignment - 1);
        
        m_totalMemorySize = m_actualObjectSize * m_blockCount;
        m_rawBuffer = static_cast<uint8_t*>(ALIGNED_ALLOC(SYSTEM_CACHE_LINE_SIZE, m_totalMemorySize));
        
        assert(m_rawBuffer != nullptr && "OS failed to allocate aligned buffer");

        // Build contiguous free-list
        for (size_t i = 0; i < m_blockCount - 1; ++i) {
            Node* current = reinterpret_cast<Node*>(m_rawBuffer + (i * m_actualObjectSize));
            Node* next = reinterpret_cast<Node*>(m_rawBuffer + ((i + 1) * m_actualObjectSize));
            current->next = next;
        }
        
        // Terminating node
        Node* last = reinterpret_cast<Node*>(m_rawBuffer + ((m_blockCount - 1) * m_actualObjectSize));
        last->next = nullptr;

        HeadPtr initialHead;
        initialHead.pointer = reinterpret_cast<Node*>(m_rawBuffer);
        initialHead.counter = 0;
        m_head.store(initialHead, std::memory_order_release);
    }

    ~LockFreeFixedPoolAllocator() {
        if (m_rawBuffer) {
            ALIGNED_FREE(m_rawBuffer);
            m_rawBuffer = nullptr;
        }
    }

    LockFreeFixedPoolAllocator(const LockFreeFixedPoolAllocator&) = delete;
    LockFreeFixedPoolAllocator& operator=(const LockFreeFixedPoolAllocator&) = delete;

    [[nodiscard]] void* Allocate() noexcept {
        HeadPtr currentHead = m_head.load(std::memory_order_relaxed);
        HeadPtr nextHead;

        do {
            if (currentHead.pointer == nullptr) {
                return nullptr; // Pool Depleted
            }
            nextHead.pointer = currentHead.pointer->next;
            nextHead.counter = currentHead.counter + 1;
        } while (!m_head.compare_exchange_weak(
            currentHead, 
            nextHead, 
            std::memory_order_acquire, 
            std::memory_order_relaxed));

        return static_cast<void*>(currentHead.pointer);
    }

    void Deallocate(void* ptr) noexcept {
        if (!ptr) return;

        assert(ptr >= m_rawBuffer && ptr < (m_rawBuffer + m_totalMemorySize) && 
               "Pointer out of allocator bounds!");

        Node* newFreeNode = static_cast<Node*>(ptr);
        HeadPtr currentHead = m_head.load(std::memory_order_relaxed);
        HeadPtr nextHead;

        do {
            newFreeNode->next = currentHead.pointer;
            nextHead.pointer = newFreeNode;
            nextHead.counter = currentHead.counter + 1;
        } while (!m_head.compare_exchange_weak(
            currentHead, 
            nextHead, 
            std::memory_order_release, 
            std::memory_order_relaxed));
    }

private:
    uint8_t* m_rawBuffer{nullptr};
    size_t m_actualObjectSize{0};
    size_t m_blockCount{0};
    size_t m_totalMemorySize{0};

    alignas(SYSTEM_CACHE_LINE_SIZE) std::atomic<HeadPtr> m_head;
};
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Open-World Entity-Streaming Stall pada MMORPG / AAA Engine
* **Konteks:** Sebuah game engine open-world berbasis multi-threaded PC/Konsol mengalami degradasi performa (*stuttering*) parah: frame drops dari 60 FPS ke 14 FPS secara acak setiap kali karakter melintasi batas sub-level/chunk dunia (*streaming barrier*).
* **Diagnostik Telemetri:**
  * Profiling menggunakan Superluminal/Tracy menunjukkan fungsi `malloc` di dalam thread *World Streamer* menunggu kepemilikan global mutex selama **48.2 ms**.
  * Tingkat TLB Cache Miss melonjak hingga **340%** saat streaming chunk berlangsung bersamaan dengan pertempuran intensif.
  * Heap fragmentation mencapai 41%, di mana OS menolak pemesanan contiguous 128 MB untuk terrain chunk meshing meskipun kapasitas RAM bebas tersisa 4.2 GB.

```
SEBELUM OPTIMASI:
Streaming Thread  --> [malloc] ---> (GLOBAL HEAP LOCK) <--- [malloc] <-- Physics Thread
                                           |
                                  Thread Stalled! (48ms)

SETELAH OPTIMASI:
Streaming Thread  --> [Ring-Buffer Chunk Allocator (Contiguous Pages)] -> Zero Lock
Entity Lifecycle  --> [Per-Worker Subsystem Pool Allocator]           -> Local O(1)
Physics Temp      --> [Linear Frame Scratchpad]                      -> Local Reset
```

* **Solusi Rekayasa Sistem:**
  1. **Virtual Address Space Reservation:** Engine memesan 2 GB Virtual Address Space di muka menggunakan `mmap` (`MAP_NORESERVE` di POSIX atau `VirtualAlloc` dengan flag `MEM_RESERVE` di Windows) untuk Terrain Chunk Streaming.
  2. **Physical Page Committing Berkelanjutan:** Mengubah hak komit halaman fisik memori secara dinamis menggunakan `MEM_COMMIT` dan `MEM_DECOMMIT` hanya pada chunk aktif tanpa menyentuh alokator C runtime.
  3. **Generational Entity Pool Allocator:** 150.000 entitas gameplay dipecah ke dalam slot array statis bertipe *Structure of Arrays* (SoA). Akses entitas menggunakan *Entity Handles* (32-bit Index + 32-bit Generation) untuk mencegah bug *dangling pointer* akibat use-after-free tanpa rely pada `std::shared_ptr`.
* **Hasil:**
  * Penghapusan 100% *heap lock contention*.
  * Waktu streaming terrain per-chunk terpangkas dari **52.4 ms** menjadi **3.1 ms** (stabil di target 60 FPS).
  * Penghematan total memori residen sebesar 680 MB akibat eliminasi alokasi metadata per-objek.

---

## 9. Trade-offs

Setiap strategi manajemen memori melibatkan kompromi teknik:

```
+---------------------+-------------------+---------------------+---------------------+
| Allocator Type      | Throughput        | Memory Overhead     | Fleksibilitas       |
+---------------------+-------------------+---------------------+---------------------+
| Linear / Arena      | Ekstrim (~1-2 ns) | 0 bytes per alloc   | Nol (Hanya Reset)   |
| Fixed Pool          | Ekstrim (~3-5 ns) | 0 (in-situ pointer) | Rendah (Fixed Size) |
| Free-List           | Sedang (~20-50 ns)| 8-16 bytes (Header) | Tinggi (Arbitrary)  |
| OS Heap (malloc)    | Rendah (~50-200ns)| 16-32 bytes + Locks | Maksimal            |
+---------------------+-------------------+---------------------+---------------------+
```

### Analisis Skenario:
* **Throughput vs. Fleksibilitas:** Linear Allocator memberikan throughput maksimum karena alokasi hanyalah sebuah instruksi pergeseran register (`add`). Namun, alokator ini tidak fleksibel karena dealokasi parsial tidak dimungkinkan. Jika satu objek memiliki siklus hidup panjang, seluruh arena tidak dapat dibebaskan.
* **Overhead Memori vs. Fragmentasi:** Free-list dengan algoritma *coalescing* meminimalkan pemborosan RAM akibat alokasi acak, tetapi menyisipkan metadata header/footer per-blok (overhead $N \times 16\text{ byte}$) dan rentan terhadap *pointer chasing* yang merusak performa cache.
* **Latency vs. Resource Contention:** Lock-free Pool Allocator menghilangkan stalls antar thread, namun operasi atomik berulang (`compare_exchange_weak`) pada kondisi kontensi tinggi dapat memicu *cache coherency storm* melintasi interkoneksi CPU socket.

---

## 10. Common Mistakes & Troubleshooting

### 1. False Sharing pada Struktur Multithreaded
* **Gejala:** Menambahkan thread pekerja game justru memperlambat performa simulasi secara drastis (*negative scaling*).
* **Penyebab:** Dua variabel independen yang dimodifikasi oleh dua thread berbeda berada pada satu cache line (64-byte) yang sama. Protokol *MESI cache coherency* memaksa cache line di-invalidasi terus-menerus bolak-balik antar core CPU.
* **Solusi:** Gunakan specifier `alignas(std::hardware_destructive_interference_size)` pada counter atau struktur data per-thread.

### 2. Misalignment Crash pada Instruksi SIMD (AVX / Neon)
* **Gejala:** Engine mengalami crash fatal instan pada instruksi perakitan seperti `vmovaps` dengan sinyal `SIGSEGV` / `STATUS_ACCESS_VIOLATION`.
* **Penyebab:** Alamat memori yang dikirimkan ke intrinsik vektorisasi tidak diselaraskan ke batas 32-byte atau 64-byte (misalnya alokasi langsung menggunakan `malloc` standar C yang umumnya hanya menjamin penyelarasan 8-byte atau 16-byte).
* **Solusi:** Terapkan formula padding penyelarasan pada seluruh custom allocator dan gunakan alokasi biner OS terikat penyelarasan (`posix_memalign` atau `_aligned_malloc`).

### 3. Destruction Bypass (Memory Leaks Sumber Daya Non-RAII)
* **Gejala:** Kebocoran file handle, socket, atau GPU descriptor saat entitas dihapus melalui `LinearArenaAllocator::Reset()`.
* **Penyebab:** Arena alokator hanya mereset offset memori tanpa memanggil destruktor kelas (`~T()`).
* **Solusi:** Gunakan static assert `std::is_trivially_destructible_v<T>` pada metode Arena, atau pelihara array fungsi destruktor terdaftar (*destructor chain*) jika tipe non-trivial diizinkan masuk ke arena.

---

## 11. Best Practices (Production Checklist)

| Tahap | Parameter Checklist Produksi | Tindakan Verifikasi |
| :---: | :--- | :--- |
| [ ] | **Zero Heap Dynamic Allocation in Loop** | Pastikan tidak ada panggilan `malloc`, `free`, `new`, atau `delete` di dalam siklus loop utama game (`Update`, `Render`, `Tick`). |
| [ ] | **Pre-allocation Budgeting** | Seluruh subsistem (AI, Audio, Physic, Rendering) mengalokasikan memori pool mereka pada tahap boot/inisialisasi game. |
| [ ] | **Cache Line Alignment Verification** | Struktur data per-thread diverifikasi terpisah oleh minimal 64-byte untuk memblokir fenomena *false sharing*. |
| [ ] | **SIMD Type Alignment** | Struktur vektor matematika (Matrix4x4, Quat, Transform) menggunakan deklarasi `alignas(16)` atau `alignas(32)`. |
| [ ] | **Memory Canary / Guard Pages** | Setiap blok alokasi pada mode *Debug/Profile* menyertakan byte pembatas (`0xDEADBEEF`) untuk mendeteksi *buffer overflow*. |
| [ ] | **ASan & UBSan CI Pipeline** | Menjalankan *automated regression test* engine menggunakan AddressSanitizer dan UndefinedBehaviorSanitizer pada pipeline CI. |
| [ ] | **Tracy / Telemetry Instrumentation** | Setiap macro alokasi engine diikat ke *profiler zone tracking* untuk observasi *live memory distribution*. |

---

## 12. Hands-on Practice

Buat dan implementasikan proyek benchmarker performa memori modular dengan struktur direktori berikut:

```
hands-on/m02/
├── CMakeLists.txt
├── include/
│   ├── ArenaAllocator.hpp
│   └── PoolAllocator.hpp
└── src/
    └── main.cpp
```

### File: `hands-on/m02/CMakeLists.txt`
```cmake
cmake_minimum_required(VERSION 3.22)
project(LowLevelMemorySystems LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if (MSVC)
    add_compile_options(/W4 /WX /O2 /permissive-)
else()
    add_compile_options(-Wall -Wextra -Werror -pedantic -O3 -march=native)
endif()

include_directories(include)

add_executable(memory_benchmark 
    src/main.cpp
)
```

### File: `hands-on/m02/include/ArenaAllocator.hpp`
```cpp
#pragma once
#include <cstddef>
#include <cstdint>
#include <new>
#include <cassert>
#include <type_traits>

class ArenaAllocator {
public:
    ArenaAllocator(size_t capacityBytes)
        : m_capacity(capacityBytes), m_offset(0) {
        m_buffer = new uint8_t[m_capacity];
    }

    ~ArenaAllocator() {
        delete[] m_buffer;
    }

    ArenaAllocator(const ArenaAllocator&) = delete;
    ArenaAllocator& operator=(const ArenaAllocator&) = delete;

    [[nodiscard]] void* Allocate(size_t size, size_t alignment = alignof(std::max_align_t)) noexcept {
        const uintptr_t currentAddress = reinterpret_cast<uintptr_t>(m_buffer + m_offset);
        const size_t mask = alignment - 1;
        const size_t misalignment = currentAddress & mask;
        const size_t padding = (misalignment == 0) ? 0 : (alignment - misalignment);

        if (m_offset + padding + size > m_capacity) {
            return nullptr;
        }

        m_offset += padding;
        void* ptr = m_buffer + m_offset;
        m_offset += size;
        return ptr;
    }

    template <typename T, typename... Args>
    [[nodiscard]] T* Create(Args&&... args) {
        static_assert(std::is_trivially_destructible_v<T>, 
            "ArenaAllocator directly destroys objects without calling destructors. Type T must be trivially destructible.");
        void* mem = Allocate(sizeof(T), alignof(T));
        if (!mem) return nullptr;
        return new (mem) T(std::forward<Args>(args)...);
    }

    void Reset() noexcept {
        m_offset = 0;
    }

    [[nodiscard]] size_t GetUsedMemory() const noexcept { return m_offset; }

private:
    uint8_t* m_buffer{nullptr};
    size_t m_capacity{0};
    size_t m_offset{0};
};
```

### File: `hands-on/m02/include/PoolAllocator.hpp`
```cpp
#pragma once
#include <cstddef>
#include <cstdint>
#include <cassert>
#include <algorithm>

class PoolAllocator {
private:
    union FreeNode {
        FreeNode* next;
    };

public:
    PoolAllocator(size_t objectSize, size_t alignment, size_t capacity)
        : m_capacity(capacity) 
    {
        m_actualBlockSize = std::max(objectSize, sizeof(FreeNode));
        m_actualBlockSize = (m_actualBlockSize + (alignment - 1)) & ~(alignment - 1);
        
        m_memory = new uint8_t[m_actualBlockSize * m_capacity];
        Reset();
    }

    ~PoolAllocator() {
        delete[] m_memory;
    }

    PoolAllocator(const PoolAllocator&) = delete;
    PoolAllocator& operator=(const PoolAllocator&) = delete;

    [[nodiscard]] void* Allocate() noexcept {
        if (!m_freeListHead) return nullptr;
        
        FreeNode* node = m_freeListHead;
        m_freeListHead = m_freeListHead->next;
        return static_cast<void*>(node);
    }

    void Deallocate(void* ptr) noexcept {
        if (!ptr) return;
        FreeNode* node = static_cast<FreeNode*>(ptr);
        node->next = m_freeListHead;
        m_freeListHead = node;
    }

    void Reset() noexcept {
        m_freeListHead = reinterpret_cast<FreeNode*>(m_memory);
        FreeNode* current = m_freeListHead;
        for (size_t i = 0; i < m_capacity - 1; ++i) {
            uint8_t* nextBlockAddress = m_memory + ((i + 1) * m_actualBlockSize);
            current->next = reinterpret_cast<FreeNode*>(nextBlockAddress);
            current = current->next;
        }
        current->next = nullptr;
    }

private:
    uint8_t* m_memory{nullptr};
    size_t m_actualBlockSize{0};
    size_t m_capacity{0};
    FreeNode* m_freeListHead{nullptr};
};
```

### File: `hands-on/m02/src/main.cpp`
```cpp
#include <iostream>
#include <chrono>
#include <vector>
#include "ArenaAllocator.hpp"
#include "PoolAllocator.hpp"

struct alignas(16) SimulationParticle {
    float posX, posY, posZ, life;
    float velX, velY, velZ, mass;
};

constexpr size_t ITERATIONS = 1'000'000;

void BenchmarkSystemHeap() {
    auto start = std::chrono::high_resolution_clock::now();
    std::vector<SimulationParticle*> ptrs;
    ptrs.reserve(ITERATIONS);

    for (size_t i = 0; i < ITERATIONS; ++i) {
        ptrs.push_back(new SimulationParticle{1.0f, 2.0f, 3.0f, 100.0f, 0.1f, 0.2f, 0.3f, 1.0f});
    }
    for (size_t i = 0; i < ITERATIONS; ++i) {
        delete ptrs[i];
    }
    auto end = std::chrono::high_resolution_clock::now();
    std::cout << "[System Heap malloc/new] Time: " 
              << std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count() 
              << " ms\n";
}

void BenchmarkPoolAllocator() {
    PoolAllocator pool(sizeof(SimulationParticle), alignof(SimulationParticle), ITERATIONS);
    std::vector<void*> ptrs;
    ptrs.reserve(ITERATIONS);

    auto start = std::chrono::high_resolution_clock::now();
    for (size_t i = 0; i < ITERATIONS; ++i) {
        ptrs.push_back(pool.Allocate());
    }
    for (size_t i = 0; i < ITERATIONS; ++i) {
        pool.Deallocate(ptrs[i]);
    }
    auto end = std::chrono::high_resolution_clock::now();
    std::cout << "[Fixed Pool Allocator  ] Time: " 
              << std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count() 
              << " ms\n";
}

void BenchmarkArenaAllocator() {
    ArenaAllocator arena(ITERATIONS * sizeof(SimulationParticle) + 1024);

    auto start = std::chrono::high_resolution_clock::now();
    for (size_t i = 0; i < ITERATIONS; ++i) {
        arena.Create<SimulationParticle>();
    }
    arena.Reset();
    auto end = std::chrono::high_resolution_clock::now();
    std::cout << "[Linear Arena Allocator] Time: " 
              << std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count() 
              << " ms\n";
}

int main() {
    std::cout << "--- MEMORY MANAGEMENT PERFORMANCE BENCHMARK ---\n";
    std::cout << "Running iterations: " << ITERATIONS << " objects (" << sizeof(SimulationParticle) << " bytes each)\n\n";

    BenchmarkSystemHeap();
    BenchmarkPoolAllocator();
    BenchmarkArenaAllocator();

    return 0;
}
```

#### Langkah Menjalankan Praktikum:
```bash
cd hands-on/m02/
mkdir build && cd build
cmake ..
cmake --build . --config Release
./memory_benchmark
```

---

## 13. Exercise

### Level Easy
Modifikasi kelas `ArenaAllocator`:
Tambahkan fitur penanda (*marker*) untuk mengubahnya menjadi **Stack Allocator**. Tipe data marker didefinisikan sebagai `using Marker = size_t;`. Implementasikan metode:
* `Marker GetMarker() const noexcept;`
* `void FreeToMarker(Marker marker) noexcept;`
Pastikan alokasi yang terjadi setelah pengambilan marker dapat dibebaskan tanpa menghapus seluruh blok arena yang dialokasikan sebelumnya.

### Level Medium
Implementasikan **Thread-Local Frame Allocator Registry**:
Buat subsistem pembungkus di mana setiap thread sistem runtime game secara otomatis mendapatkan arena alokasi frame 16 MB independen yang tidak saling mengunci (*zero lock contention*). Gunakan keyword `thread_local`. Sediakan API global:
* `void* EngineFrameAlloc(size_t bytes, size_t alignment);`
* `void EngineFrameResetAllThreads();`

### Level Hard
Rancang **Free-List Allocator** yang mendukung **Immediate Coalescing**:
* Setiap alokasi memiliki *Allocation Header* (16 byte) yang menyimpan ukuran chunk dan flag status (`is_free`).
* Setiap chunk memori bebas dihubungkan menggunakan *Doubly-Linked List*.
* Ketika fungsi `Deallocate(void* ptr)` dipanggil, periksa secara fisik apakah blok tetangga kiri dan blok tetangga kanan berstatus bebas (`is_free == true`). Jika ya, satukan (*coalesce*) kedua atau ketiga blok tersebut secara instan menjadi satu blok kontigu raksasa untuk memusnahkan fragmentasi eksternal.

---

## 14. Challenge

### Studi Kasus: Heterogeneous Generational ECS Memory Arena
Rancang dan bangun arsitektur penyimpanan memori untuk subsistem **Entity Component System (ECS)** berkinerja tinggi yang menangani 1.000.000 entitas aktif dengan spesifikasi berikut:

1. **Komposisi Heterogen Non-Uniform:** Entitas dapat memiliki kombinasi komponen arbitrary (misal: `Transform` [32 byte], `RigidBody` [48 byte], `MeshRenderData` [64 byte]).
2. **Kompaksi Memori Terfragmentasi (Defragmentasi Instan):** Ketika entitas hancur secara acak di tengah eksekusi, struktur data harus menggunakan teknik penataan *Sparse Set* atau *Archetype Chunk Array* (seperti Unreal Engine / Unity DOTS), di mana elemen terakhir dalam memori dipindahkan menempati posisi elemen yang terhapus (*Swap-and-Pop*), mempertahankan array padat kontigu 100% tanpa adanya celah (*gapless packed memory*).
3. **Generational Safety Check:** Implementasikan tipe pointer/handle `EntityHandle { uint32_t index; uint32_t generation; }`. Jika suatu entitas telah dihancurkan, dan index-nya digunakan ulang oleh entitas baru, handle lama yang mencoba mengakses komponen dari entitas tersebut wajib menghasilkan nilai `nullptr` atau melempar assertion deterministik tanpa memicu *segmentation fault*.
4. **Metrik Evaluasi:** Sistem harus mampu melakukan proses iterasi pembaruan (*system tick*) pada 1.000.000 komponen `Transform` dengan instruksi pemrosesan SIMD dalam durasi **kurang dari 1.2 milidetik** pada arsitektur modern (x86_64 AVX2).

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic
1. Mengapa alokasi dinamis via `malloc` atau `new` tidak boleh dipanggil di dalam game render loop frame aktif?
2. Berapakah ukuran default sebuah *Cache Line* pada mayoritas prosesor x86_64 dan ARM64 modern?
3. Apa konsekuensi fatal jika pointer yang tidak selaras (*unaligned address*) dilewatkan ke instruksi pemrosesan data SIMD seperti `_mm256_load_ps`?
4. Mengapa Linear/Arena Allocator memiliki efisiensi komputasi $O(1)$ untuk operasi dealokasi?
5. Jelaskan perbedaan mendasar antara *Internal Fragmentation* dan *External Fragmentation*.

### 5 Pertanyaan Intermediate
6. Bagaimana cara kerja penyimpanan pointer pada *Free-List Allocator* yang menggunakan teknik *in-situ metadata*?
7. Apa yang dimaksud dengan fenomena *False Sharing*, dan bagaimana cara mencegahnya menggunakan standar C++17/C++20?
8. Mengapa konversi susunan data dari *Array of Structures* (AoS) menjadi *Structure of Arrays* (SoA) secara signifikan meningkatkan kinerja *Hardware Prefetcher* CPU?
9. Jelaskan masalah konkurensi **ABA Problem** pada implementasi *Lock-Free Pool Allocator* berbasis Atomic Pointer dan bagaimana tag generasi (*tagged counter*) mengatasinya.
10. Kapan destruktor (`~T()`) harus dipanggil secara eksplisit sebelum memori dikembalikan ke dalam custom allocator?

### 3 Skenario Kasus Produksi
11. **Skenario A:** Tim QA melaporkan bahwa game berjalan mulus 60 FPS pada 15 menit pertama, namun setelah 2 jam pengujian eksplorasi dunia terbuka, performa merosot ke 25 FPS dan alokasi memori heap OS membengkak secara permanen meskipun jumlah entitas di layar bernilai konstan. Profiler menunjukkan total alokasi byte tidak bertambah, tetapi waktu fungsi `malloc` meroket. Analisis akar masalah teknisnya dan tentukan solusi arsitekturalnya!
12. **Skenario B:** Sistem simulasi partikel menggunakan `std::vector<Particle>` dan thread worker parallel loop (`#pragma omp parallel for`). Di core i9 (16 Cores), pengujian menunjukkan eksekusi 8 thread berjalan **lebih lambat** dibandingkan eksekusi 1 thread (single core). Variabel apa di level memori hardware yang paling berpotensi menyebabkan anomali ini, dan bagaimana pembuktiannya melalui memory counters?
13. **Skenario C:** Anda diminta merancang sistem manajemen memori untuk UI Engine game console yang mengalokasikan ribuan string teks kecil, ikon vektor, dan elemen tata letak per frame, lalu menghancurkannya seketika pada akhir frame. Jelaskan kombinasi allocator yang paling tepat dan aman untuk menangani kebutuhan tersebut tanpa menyebabkan fragmentasi sistem operasi!

---

## 16. Summary

* **Determinisasi adalah Prioritas Utama:** Rekayasa sistem game mengutamakan konsistensi waktu eksekusi dibandingkan fleksibilitas tak terbatas. Custom allocator menghilangkan latensi acak yang melekat pada manajer memori bawaan OS.
* **Sesuaikan Pola dengan Lifetime:**
  * Gunakan **Linear / Arena Allocator** untuk data sementara yang berumur per-frame atau per-tahapan rendering.
  * Gunakan **Fixed-Size Pool Allocator** untuk kumpulan objek homogen yang sering dibuat dan dihancurkan secara asinkron (misalnya: peluru, proyektil, partikel, node jaringan).
  * Gunakan **Free-List Allocator** untuk alokasi dinamis ukuran variabel yang membutuhkan fleksibilitas jangka menengah (misalnya: audio buffers, level streaming segments).
* **Hardware-Aware Memory Layout:** Pahami bahwa performa kode modern sangat ditentukan oleh interaksi dengan hierarki cache CPU. Penataan data yang padat (*cache locality*), eliminasi pemborosan data via *Structure of Arrays* (SoA), pencegahan *false sharing*, dan keselarasan alamat (*memory alignment*) merupakan pondasi wajib dari arsitektur game engine modern berkinerja tinggi.